"""
Memory API

Endpoints for viewing and managing user memory.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
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
