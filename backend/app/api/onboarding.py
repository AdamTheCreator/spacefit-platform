from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.db.models.credential import OnboardingProgress

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingProgressResponse(BaseModel):
    current_step: int
    completed_steps: list[int]
    skipped_steps: list[int]
    is_complete: bool

    model_config = {"from_attributes": True}


class OnboardingProgressUpdate(BaseModel):
    current_step: int | None = None
    completed_steps: list[int] | None = None
    skipped_steps: list[int] | None = None


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
        completed_steps=progress.completed_steps or [],
        skipped_steps=progress.skipped_steps or [],
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
        progress.completed_steps = progress_data.completed_steps
    if progress_data.skipped_steps is not None:
        progress.skipped_steps = progress_data.skipped_steps

    await db.commit()
    await db.refresh(progress)

    return OnboardingProgressResponse(
        current_step=progress.current_step,
        completed_steps=progress.completed_steps or [],
        skipped_steps=progress.skipped_steps or [],
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

    progress.completed_at = datetime.utcnow()
    await db.commit()
