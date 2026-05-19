"""
Memory API

Endpoints for viewing and managing user memory and per-user facts.
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.db.models.user_fact import UserFact
from app.db.models.user_memory import UserMemory
from app.services.memory_service import get_memory_service

router = APIRouter(prefix="/users/me/memory", tags=["memory"])


class AnalyzedPropertyResponse(BaseModel):
    address: str
    asset_type: str
    analysis_date: str
    key_findings: list[str]
    void_count: int


class BookOfBusinessSummaryResponse(BaseModel):
    tenant_count: int
    top_categories: list[str]
    coverage_areas: list[str]
    last_import: str | None = None


class PreferencesResponse(BaseModel):
    preferred_asset_types: list[str] = []
    preferred_trade_areas: list[str] = []
    typical_sf_range: dict | None = None


class MemoryResponse(BaseModel):
    id: str
    total_analyses: int
    analyzed_properties: list[AnalyzedPropertyResponse]
    book_of_business_summary: BookOfBusinessSummaryResponse | None
    preferences: PreferencesResponse
    ai_profile_summary: str | None
    last_updated: str

    model_config = {"from_attributes": True}


class MemoryStatsResponse(BaseModel):
    total_analyses: int
    properties_count: int
    tenant_count: int
    has_memory: bool


@router.get("", response_model=MemoryResponse | None)
async def get_user_memory(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryResponse | None:
    """
    Get the current user's Space Goose memory.

    Returns null if no memory exists yet.
    """
    result = await db.execute(
        select(UserMemory).where(UserMemory.user_id == current_user.id)
    )
    memory = result.scalar_one_or_none()

    if memory is None:
        return None

    # Parse the stored data
    analyzed_props = []
    for prop in (memory.analyzed_properties or []):
        analyzed_props.append(
            AnalyzedPropertyResponse(
                address=prop.get("address", ""),
                asset_type=prop.get("asset_type", ""),
                analysis_date=prop.get("analysis_date", ""),
                key_findings=prop.get("key_findings", []),
                void_count=prop.get("void_count", 0),
            )
        )

    bob = memory.book_of_business_summary or {}
    bob_response = None
    if bob.get("tenant_count"):
        bob_response = BookOfBusinessSummaryResponse(
            tenant_count=bob.get("tenant_count", 0),
            top_categories=bob.get("top_categories", []),
            coverage_areas=bob.get("coverage_areas", []),
            last_import=bob.get("last_import"),
        )

    prefs = memory.preferences or {}
    prefs_response = PreferencesResponse(
        preferred_asset_types=prefs.get("preferred_asset_types", []),
        preferred_trade_areas=prefs.get("preferred_trade_areas", []),
        typical_sf_range=prefs.get("typical_sf_range"),
    )

    return MemoryResponse(
        id=memory.id,
        total_analyses=memory.total_analyses or 0,
        analyzed_properties=analyzed_props,
        book_of_business_summary=bob_response,
        preferences=prefs_response,
        ai_profile_summary=memory.ai_profile_summary,
        last_updated=memory.last_updated.isoformat() if memory.last_updated else "",
    )


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryStatsResponse:
    """Get summary stats about user's memory."""
    result = await db.execute(
        select(UserMemory).where(UserMemory.user_id == current_user.id)
    )
    memory = result.scalar_one_or_none()

    if memory is None:
        return MemoryStatsResponse(
            total_analyses=0,
            properties_count=0,
            tenant_count=0,
            has_memory=False,
        )

    bob = memory.book_of_business_summary or {}

    return MemoryStatsResponse(
        total_analyses=memory.total_analyses or 0,
        properties_count=len(memory.analyzed_properties or []),
        tenant_count=bob.get("tenant_count", 0),
        has_memory=True,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_user_memory(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Clear all Space Goose memory for the current user.

    This removes:
    - All analyzed property history
    - Book of business summary
    - Inferred preferences
    - AI profile summary
    """
    service = get_memory_service(db)
    await service.clear_memory(current_user.id)


# --- Personal facts (Initiative 4) -----------------------------------------

FactStatus = Literal["pending", "approved", "rejected", "archived"]


class UserFactResponse(BaseModel):
    id: str
    text: str
    category: str
    status: FactStatus
    confidence: float
    source_session_id: str | None = None
    source_message_id: str | None = None
    created_at: str
    approved_at: str | None = None
    last_used_at: str | None = None

    @classmethod
    def from_row(cls, row: UserFact) -> "UserFactResponse":
        return cls(
            id=row.id,
            text=row.text,
            category=row.category,
            status=row.status,  # type: ignore[arg-type]
            confidence=row.confidence,
            source_session_id=row.source_session_id,
            source_message_id=row.source_message_id,
            created_at=row.created_at.isoformat() if row.created_at else "",
            approved_at=row.approved_at.isoformat() if row.approved_at else None,
            last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
        )


@router.get("/facts", response_model=list[UserFactResponse])
async def list_facts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: FactStatus | None = None,
) -> list[UserFactResponse]:
    """List the current user's facts.

    Pass ``status_filter=pending`` to drive the review sidebar; default
    returns everything except archived for the Settings page.
    """
    stmt = select(UserFact).where(UserFact.user_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(UserFact.status == status_filter)
    else:
        stmt = stmt.where(UserFact.status != "archived")
    stmt = stmt.order_by(UserFact.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [UserFactResponse.from_row(r) for r in rows]


class FactStatusUpdate(BaseModel):
    status: Literal["approved", "rejected", "archived"]


async def _get_owned_fact(db: AsyncSession, user_id: str, fact_id: str) -> UserFact:
    fact = (
        await db.execute(
            select(UserFact).where(
                UserFact.id == fact_id, UserFact.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return fact


@router.post("/facts/{fact_id}/approve", response_model=UserFactResponse)
async def approve_fact(
    fact_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserFactResponse:
    fact = await _get_owned_fact(db, current_user.id, fact_id)
    fact.status = "approved"
    fact.approved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(fact)
    return UserFactResponse.from_row(fact)


@router.post("/facts/{fact_id}/reject", response_model=UserFactResponse)
async def reject_fact(
    fact_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserFactResponse:
    fact = await _get_owned_fact(db, current_user.id, fact_id)
    fact.status = "rejected"
    await db.commit()
    await db.refresh(fact)
    return UserFactResponse.from_row(fact)


@router.delete(
    "/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def archive_fact(
    fact_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    fact = await _get_owned_fact(db, current_user.id, fact_id)
    fact.status = "archived"
    await db.commit()
