"""
Follow-Up Cadence Service

Creates and manages follow-up activities for deals after LOI submission.
Schedules reminders at configurable day intervals and surfaces overdue items.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.deal import DealActivity, ActivityType

logger = logging.getLogger(__name__)

# Days after LOI submission to schedule follow-ups
FOLLOWUP_SCHEDULE = [3, 5, 7]


async def create_followup_activities(
    deal_id: str,
    user_id: str,
    db: AsyncSession,
) -> list[str]:
    """
    Create follow-up DealActivity records for a deal.

    Schedules follow-up notes at 3, 5, and 7 days from now (based on
    FOLLOWUP_SCHEDULE). Each activity is created with activity_type="note"
    and a title like "Follow-up #1".

    Args:
        deal_id: The Deal ID to create follow-ups for.
        user_id: The user ID who owns the activities.
        db: Async database session.

    Returns:
        List of created DealActivity IDs.
    """
    created_ids: list[str] = []
    now = datetime.utcnow()

    for idx, days in enumerate(FOLLOWUP_SCHEDULE, start=1):
        activity_id = str(uuid.uuid4())
        scheduled_at = now + timedelta(days=days)

        activity = DealActivity(
            id=activity_id,
            deal_id=deal_id,
            user_id=user_id,
            activity_type=ActivityType.NOTE.value,
            title=f"Follow-up #{idx}",
            description=(
                f"Scheduled follow-up {days} days after LOI submission. "
                f"Check in on deal status and next steps."
            ),
            scheduled_at=scheduled_at,
            completed_at=None,
        )
        db.add(activity)
        created_ids.append(activity_id)

        logger.info(
            "[followup] Created follow-up #%d for deal %s, scheduled at %s",
            idx,
            deal_id,
            scheduled_at.isoformat(),
        )

    await db.commit()

    logger.info(
        "[followup] Created %d follow-up activities for deal %s",
        len(created_ids),
        deal_id,
    )

    return created_ids


async def get_overdue_followups(
    user_id: str,
    db: AsyncSession,
) -> list[dict]:
    """
    Find DealActivity records that are overdue (scheduled_at < now and
    completed_at is None) for a given user.

    Args:
        user_id: The user ID to check follow-ups for.
        db: Async database session.

    Returns:
        List of dicts with keys: id, deal_id, title, description,
        scheduled_at, days_overdue.
    """
    now = datetime.utcnow()

    result = await db.execute(
        select(DealActivity)
        .where(
            DealActivity.user_id == user_id,
            DealActivity.scheduled_at < now,
            DealActivity.completed_at.is_(None),
        )
        .order_by(DealActivity.scheduled_at.asc())
    )
    activities = result.scalars().all()

    overdue: list[dict] = []
    for activity in activities:
        days_overdue = (now - activity.scheduled_at).days

        overdue.append(
            {
                "id": activity.id,
                "deal_id": activity.deal_id,
                "title": activity.title,
                "description": activity.description,
                "scheduled_at": activity.scheduled_at.isoformat(),
                "days_overdue": days_overdue,
            }
        )

    logger.info(
        "[followup] Found %d overdue follow-ups for user %s",
        len(overdue),
        user_id,
    )

    return overdue
