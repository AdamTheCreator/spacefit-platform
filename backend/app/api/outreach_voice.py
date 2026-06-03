"""Outreach voice profiles + AI draft generation.

Two concerns, one router (both live under ``/outreach``):

* **Voice CRUD** — a user keeps one or more named "write like me" prompts and
  marks one as the default. The default invariant (at most one per user) is
  enforced application-side here.
* **POST /outreach/draft-ai** — generate a subject + body for the composer,
  in the selected voice, via the user's resolved (BYOK-aware) LLM.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.db.models.outreach_voice import OutreachVoiceProfile
from app.services.outreach_ai import generate_outreach_email
from app.services.user_llm import resolve_user_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["outreach-voice"])

# Soft cap so a user can't balloon the table; well above any real workflow.
MAX_VOICES_PER_USER = 50


# ============= Pydantic schemas =============

class VoiceProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    instructions: str = Field(min_length=1)
    tone: str | None = Field(default=None, max_length=255)
    sample: str | None = None
    signature: str | None = None
    is_default: bool = False


class VoiceProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = Field(default=None, min_length=1)
    tone: str | None = Field(default=None, max_length=255)
    sample: str | None = None
    signature: str | None = None
    is_default: bool | None = None


class VoiceProfileResponse(BaseModel):
    id: str
    name: str
    instructions: str
    tone: str | None
    sample: str | None
    signature: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DraftRequest(BaseModel):
    voice_id: str | None = None
    property_name: str | None = None
    property_address: str | None = None
    vacancy_description: str | None = None
    tenant_name: str | None = None
    recipient_company: str | None = None
    extra_notes: str | None = None


class DraftResponse(BaseModel):
    subject: str
    body: str
    used_voice_id: str | None
    model: str
    is_byok: bool
    # True when the LLM path failed and a static template draft was returned.
    fallback_used: bool


# ============= Helpers =============

async def _get_owned_voice(
    db: AsyncSession, user_id: str, voice_id: str
) -> OutreachVoiceProfile:
    voice = (
        await db.execute(
            select(OutreachVoiceProfile).where(
                OutreachVoiceProfile.id == voice_id,
                OutreachVoiceProfile.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if voice is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return voice


async def _clear_other_defaults(
    db: AsyncSession, user_id: str, keep_id: str | None
) -> None:
    """Unset ``is_default`` on every other voice owned by the user."""
    stmt = (
        update(OutreachVoiceProfile)
        .where(
            OutreachVoiceProfile.user_id == user_id,
            OutreachVoiceProfile.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if keep_id is not None:
        stmt = stmt.where(OutreachVoiceProfile.id != keep_id)
    await db.execute(stmt)


async def _count_voices(db: AsyncSession, user_id: str) -> int:
    rows = (
        await db.execute(
            select(OutreachVoiceProfile.id).where(
                OutreachVoiceProfile.user_id == user_id
            )
        )
    ).scalars().all()
    return len(rows)


# ============= Voice CRUD =============

@router.get("/voices", response_model=list[VoiceProfileResponse])
async def list_voices(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OutreachVoiceProfile]:
    rows = (
        await db.execute(
            select(OutreachVoiceProfile)
            .where(OutreachVoiceProfile.user_id == current_user.id)
            .order_by(
                OutreachVoiceProfile.is_default.desc(),
                OutreachVoiceProfile.name.asc(),
            )
        )
    ).scalars().all()
    return list(rows)


@router.post(
    "/voices", response_model=VoiceProfileResponse, status_code=status.HTTP_201_CREATED
)
async def create_voice(
    data: VoiceProfileCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutreachVoiceProfile:
    count = await _count_voices(db, current_user.id)
    if count >= MAX_VOICES_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Voice profile limit reached ({MAX_VOICES_PER_USER}).",
        )

    # The first voice a user creates is their default regardless of the flag.
    make_default = data.is_default or count == 0

    voice = OutreachVoiceProfile(
        user_id=current_user.id,
        name=data.name,
        instructions=data.instructions,
        tone=data.tone,
        sample=data.sample,
        signature=data.signature,
        is_default=make_default,
    )
    db.add(voice)
    if make_default:
        await db.flush()
        await _clear_other_defaults(db, current_user.id, keep_id=voice.id)
    await db.commit()
    await db.refresh(voice)
    return voice


@router.get("/voices/{voice_id}", response_model=VoiceProfileResponse)
async def get_voice(
    voice_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutreachVoiceProfile:
    return await _get_owned_voice(db, current_user.id, voice_id)


@router.put("/voices/{voice_id}", response_model=VoiceProfileResponse)
async def update_voice(
    voice_id: str,
    data: VoiceProfileUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutreachVoiceProfile:
    voice = await _get_owned_voice(db, current_user.id, voice_id)

    fields = data.model_dump(exclude_unset=True)
    promote_default = fields.pop("is_default", None)
    for key, value in fields.items():
        setattr(voice, key, value)

    if promote_default is True:
        voice.is_default = True
        await db.flush()
        await _clear_other_defaults(db, current_user.id, keep_id=voice.id)
    elif promote_default is False:
        # Explicit demotion is allowed: the user may choose to have no default.
        # draft-ai then falls back to neutral generation when no voice is picked.
        voice.is_default = False

    await db.commit()
    await db.refresh(voice)
    return voice


@router.post("/voices/{voice_id}/default", response_model=VoiceProfileResponse)
async def set_default_voice(
    voice_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutreachVoiceProfile:
    voice = await _get_owned_voice(db, current_user.id, voice_id)
    voice.is_default = True
    await _clear_other_defaults(db, current_user.id, keep_id=voice.id)
    await db.commit()
    await db.refresh(voice)
    return voice


@router.delete("/voices/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice(
    voice_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    voice = await _get_owned_voice(db, current_user.id, voice_id)
    was_default = voice.is_default
    await db.delete(voice)
    await db.flush()

    # Keep a default alive: if we just removed it, promote the next newest.
    if was_default:
        successor = (
            await db.execute(
                select(OutreachVoiceProfile)
                .where(OutreachVoiceProfile.user_id == current_user.id)
                .order_by(OutreachVoiceProfile.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if successor is not None:
            successor.is_default = True
    await db.commit()


# ============= AI draft generation =============

@router.post("/draft-ai", response_model=DraftResponse)
async def draft_ai(
    data: DraftRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    """Generate an outreach email's subject + body in the user's voice.

    Picks the requested voice (or the user's default), resolves the user's LLM
    (BYOK-aware — same path as chat, so a configured key keeps the
    zero-platform-tokens guarantee), and returns a composer-ready draft.
    """
    # Resolve the voice: explicit id wins, else the user's default, else none.
    voice: OutreachVoiceProfile | None = None
    if data.voice_id:
        voice = await _get_owned_voice(db, current_user.id, data.voice_id)
    else:
        voice = (
            await db.execute(
                select(OutreachVoiceProfile).where(
                    OutreachVoiceProfile.user_id == current_user.id,
                    OutreachVoiceProfile.is_default.is_(True),
                )
            )
        ).scalar_one_or_none()

    # BYOK-aware resolution; never block drafting if it fails (mirrors listings).
    try:
        resolved_llm = await resolve_user_llm(
            db, current_user.id, current_user.tier
        )
    except Exception:  # noqa: BLE001
        resolved_llm = None

    result = await generate_outreach_email(
        resolved_llm=resolved_llm,
        voice=voice,
        property_name=data.property_name or "",
        property_address=data.property_address or "",
        vacancy_description=data.vacancy_description or "",
        tenant_name=data.tenant_name or "",
        recipient_company=data.recipient_company or "",
        extra_notes=data.extra_notes or "",
        from_name=current_user.full_name,
        from_email=current_user.email,
    )

    return DraftResponse(
        subject=result.subject,
        body=result.body,
        used_voice_id=result.used_voice_id,
        model=result.model,
        is_byok=result.is_byok,
        fallback_used=result.fallback_used,
    )
