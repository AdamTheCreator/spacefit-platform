"""Unit tests for outreach-send -> pipeline-deal wiring.

``ensure_deal_for_campaign`` is exercised against a stubbed ``AsyncSession``
(the established convention — see ``test_tenant_promotion.py``) so the
idempotence + field-mapping logic is pinned without a real DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.db.models.deal import Deal, DealStage, DealType
from app.services.deal_from_campaign import ensure_deal_for_campaign

_GENERATED_DEAL_ID = "generated-deal-id"


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


def _db(existing_deal_id: str | None = None, *, claim_rowcount: int = 1) -> MagicMock:
    """Stub session.

    ``existing_deal_id`` is what the id-lookup SELECT returns; ``claim_rowcount``
    is the guarded-UPDATE rowcount (1 = this call won the link, 0 = a concurrent
    send claimed it first). ``flush`` assigns a real (non-null) id to any created
    ``Deal`` so tests can assert on concrete identifiers, mirroring the DB's
    server-side/uuid default.
    """
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_deal_id
    result.rowcount = claim_rowcount
    db.execute = AsyncMock(return_value=result)

    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)
    db.delete = AsyncMock()

    async def _flush() -> None:
        for obj in added:
            if isinstance(obj, Deal) and getattr(obj, "id", None) is None:
                obj.id = _GENERATED_DEAL_ID

    db.flush = AsyncMock(side_effect=_flush)
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
        # Linked back onto the campaign + returned, with a concrete id.
        assert deal.id == _GENERATED_DEAL_ID
        assert deal_id == _GENERATED_DEAL_ID
        assert campaign.deal_id == _GENERATED_DEAL_ID
        assert isinstance(deal_id, str) and deal_id

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
        assert campaign.deal_id == new_deal.id == deal_id == _GENERATED_DEAL_ID
        assert deal_id != "stale-deal"

    async def test_lost_race_discards_deal_and_reuses_winner(self):
        # A concurrent send claimed the link first: the guarded UPDATE matches no
        # row (rowcount 0), so we must drop our just-created deal and reuse the
        # winner's — never leaving a second, orphaned pipeline deal behind.
        db = _db(claim_rowcount=0)
        winner = MagicMock()
        winner.scalar_one_or_none.return_value = "winner-deal"
        # First execute = guarded UPDATE (rowcount 0); second = winner re-read.
        update_result = MagicMock()
        update_result.rowcount = 0
        db.execute = AsyncMock(side_effect=[update_result, winner])
        campaign = _campaign()

        deal_id = await ensure_deal_for_campaign(db, campaign)

        assert deal_id == "winner-deal"
        assert campaign.deal_id == "winner-deal"
        # Exactly one deal was created and it was the one discarded.
        assert db.add.call_count == 1
        db.delete.assert_awaited_once()
        discarded = db.delete.call_args.args[0]
        assert isinstance(discarded, Deal)
