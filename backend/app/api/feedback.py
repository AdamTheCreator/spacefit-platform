"""
Feedback API — Store user corrections on tenant suggestions.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.db.models.feedback import TenantFeedback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


class TenantFeedbackRequest(BaseModel):
    session_id: str
    suggestion: str
    feedback: str  # "positive" or "negative"
    correction_text: str | None = None


class TenantFeedbackResponse(BaseModel):
    id: str
    suggestion: str
    feedback: str

    model_config = {"from_attributes": True}


@router.post("/tenant", response_model=TenantFeedbackResponse, status_code=201)
async def submit_tenant_feedback(
    body: TenantFeedbackRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit feedback on a tenant suggestion (thumbs up/down with optional correction)."""
    fb = TenantFeedback(
        session_id=body.session_id,
        user_id=current_user.id,
        suggestion=body.suggestion,
        feedback=body.feedback,
        correction_text=body.correction_text,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    return TenantFeedbackResponse.model_validate(fb)
