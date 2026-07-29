"""Unit tests for outreach-send -> pipeline-deal wiring.

``ensure_deal_for_campaign`` is exercised against a stubbed ``AsyncSession``
(the established convention — see ``test_tenant_promotion.py``) so the
idempotence + field-mapping logic is pinned without a real DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.db.models.deal import Deal, DealStage, DealType
from app.services.deal_from_campaign import ensure_deal_for_campaign


def _campaign(
    *,
    user_id: str = "u1",
    name: str = "Q3 Retail Blast",
    property_address: str = "100 Main St, Reno, NV",
    property_name: str | None = "Riverbend Center",
    deal_id: str | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = "camp1"
    c.user_id = user_id
    c.name = name
    c.property_address = property_address
    c.property_name = property_name
    c.deal_id = deal_id
    return c


def _db(existing_deal_id: str | None = None) -> MagicMock:
    """Stub session; ``existing_deal_id`` is what the id-lookup SELECT returns."""
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_deal_id
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestEnsureDealForCampaign:
    async def test_creates_intake_deal_and_links(self):
        db = _db()
        campaign = _campaign()

        deal_id = await ensure_deal_for_campaign(db, campaign)

        assert db.add.call_count == 1
        deal = db.add.call_args.args[0]
        assert isinstance(deal, Deal)
        assert deal.user_id == "u1"
        assert deal.name == "Riverbend Center"  # property_name wins
        assert deal.stage == DealStage.INTAKE.value
        assert deal.deal_type == DealType.LEASE.value
        assert deal.source == "outreach"
        # Initial stage-history row recorded.
        assert len(deal.stage_history) == 1
        history = deal.stage_history[0]
        assert history.from_stage is None
        assert history.to_stage == DealStage.INTAKE.value
        assert history.changed_by == "u1"
        # Linked back onto the campaign + returned.
        assert campaign.deal_id == deal.id == deal_id
        db.flush.assert_awaited_once()

    async def test_falls_back_to_address_when_no_property_name(self):
        db = _db()
        campaign = _campaign(property_name=None)

        await ensure_deal_for_campaign(db, campaign)

        deal = db.add.call_args.args[0]
        assert deal.name == "100 Main St, Reno, NV"

    async def test_idempotent_when_live_deal_already_linked(self):
        db = _db(existing_deal_id="existing-deal")
        campaign = _campaign(deal_id="existing-deal")

        deal_id = await ensure_deal_for_campaign(db, campaign)

        assert deal_id == "existing-deal"
        assert campaign.deal_id == "existing-deal"
        db.add.assert_not_called()
        db.flush.assert_not_awaited()

    async def test_recreates_when_linked_deal_was_deleted(self):
        # deal_id set on campaign, but the SELECT finds no matching row.
        db = _db(existing_deal_id=None)
        campaign = _campaign(deal_id="stale-deal")

        deal_id = await ensure_deal_for_campaign(db, campaign)

        assert db.add.call_count == 1
        new_deal = db.add.call_args.args[0]
        assert campaign.deal_id == new_deal.id == deal_id
        assert deal_id != "stale-deal"
