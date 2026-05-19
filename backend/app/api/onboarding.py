import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.db.models.credential import OnboardingProgress


def _decode_steps(raw: str | None) -> list[str]:
    """The `completed_steps` / `skipped_steps` columns are JSON-encoded
    strings (legacy: see seed_admin.py / seed_demo.py). Decode defensively —
    a malformed value should not 500 the settings page."""
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(decoded, list):
        return []
    return [str(s) for s in decoded]

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingProgressResponse(BaseModel):
    current_step: int
    # Steps are identified by string keys (e.g. "welcome", "import") in
    # the seed scripts and historical rows. Use `list[str]` so existing
    # data round-trips through the response model without coercion errors.
    completed_steps: list[str]
    skipped_steps: list[str]
    is_complete: bool

    model_config = {"from_attributes": True}


class OnboardingProgressUpdate(BaseModel):
    current_step: int | None = None
    completed_steps: list[str] | None = None
    skipped_steps: list[str] | None = None


@router.get("/progress", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingProgressResponse:
    """Get onboarding progress for current user."""
    result = await db.execute(
        select(OnboardingProgress).where(
            OnboardingProgress.user_id == current_user.id
        )
    )
    progress = result.scalar_one_or_none()

    if progress is None:
        progress = OnboardingProgress(user_id=current_user.id)
        db.add(progress)
        await db.commit()
        await db.refresh(progress)

    return OnboardingProgressResponse(
        current_step=progress.current_step,
        completed_steps=_decode_steps(progress.completed_steps),
        skipped_steps=_decode_steps(progress.skipped_steps),
        is_complete=progress.completed_at is not None,
    )


@router.put("/progress", response_model=OnboardingProgressResponse)
async def update_onboarding_progress(
    progress_data: OnboardingProgressUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingProgressResponse:
    """Update onboarding progress."""
    result = await db.execute(
        select(OnboardingProgress).where(
            OnboardingProgress.user_id == current_user.id
        )
    )
    progress = result.scalar_one_or_none()

    if progress is None:
        progress = OnboardingProgress(user_id=current_user.id)
        db.add(progress)

    if progress_data.current_step is not None:
        progress.current_step = progress_data.current_step
    if progress_data.completed_steps is not None:
        progress.completed_steps = json.dumps(progress_data.completed_steps)
    if progress_data.skipped_steps is not None:
        progress.skipped_steps = json.dumps(progress_data.skipped_steps)

    await db.commit()
    await db.refresh(progress)

    return OnboardingProgressResponse(
        current_step=progress.current_step,
        completed_steps=_decode_steps(progress.completed_steps),
        skipped_steps=_decode_steps(progress.skipped_steps),
        is_complete=progress.completed_at is not None,
    )


@router.post("/complete", status_code=status.HTTP_204_NO_CONTENT)
async def complete_onboarding(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Mark onboarding as complete."""
    result = await db.execute(
        select(OnboardingProgress).where(
            OnboardingProgress.user_id == current_user.id
        )
    )
    progress = result.scalar_one_or_none()

    if progress is None:
        progress = OnboardingProgress(user_id=current_user.id)
        db.add(progress)

    progress.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
