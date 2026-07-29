"""Drop a pipeline card when an outreach sequence starts.

Sending an outreach campaign is the moment a broker commits to pursuing a
property, so it should surface as a `Deal` on the Kanban board. This helper is
idempotent (re-sending a campaign never spawns a second deal) and is invoked
best-effort from the send path — a failure here must never break the send.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.deal import Deal, DealStage, DealStageHistory, DealType
from app.db.models.outreach import OutreachCampaign

logger = logging.getLogger(__name__)


def _deal_name(campaign: OutreachCampaign) -> str:
    # property_address is NOT NULL, so this always resolves; campaign.name is an
    # unreachable final leg kept out deliberately.
    return campaign.property_name or campaign.property_address


async def ensure_deal_for_campaign(
    db: AsyncSession, campaign: OutreachCampaign
) -> str | None:
    """Ensure a `Deal` exists for a sent campaign; return its id.

    Idempotent: if ``campaign.deal_id`` already points at a live deal, returns
    it untouched. Otherwise creates an ``intake``-stage deal (with its initial
    stage-history row), links it back onto the campaign, and flushes. The caller
    owns the commit.
    """
    if campaign.deal_id:
        existing = await db.execute(
            select(Deal.id).where(Deal.id == campaign.deal_id)
        )
        if existing.scalar_one_or_none() is not None:
            return campaign.deal_id

    deal = Deal(
        user_id=campaign.user_id,
        name=_deal_name(campaign),
        stage=DealStage.INTAKE.value,
        deal_type=DealType.LEASE.value,
        source="outreach",
        notes=f"Auto-created from outreach campaign '{campaign.name}'.",
    )
    deal.stage_history.append(
        DealStageHistory(
            from_stage=None,
            to_stage=DealStage.INTAKE.value,
            changed_by=campaign.user_id,
            notes="Outreach sequence started.",
        )
    )
    db.add(deal)
    await db.flush()

    campaign.deal_id = deal.id
    return deal.id
