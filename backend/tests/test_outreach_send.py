"""End-to-end-ish tests for the campaign send handler (the outreach on-ramp).

These drive the real ``send_campaign`` endpoint function directly with a
stubbed ``AsyncSession`` and monkeypatched transport (mirroring the
``test_memory_facts.py`` / ``test_outreach_replies.py`` convention) so they run
in <1s without Postgres or a live email provider. They exercise the full
sequence a manually-composed campaign now goes through: status guardrails →
send → recipient status updates → Deal-card creation → ``deal_id`` in the
response (the "close the loop with the Workflow board" step).
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api import outreach as outreach_module
from app.api.outreach import send_campaign
from app.db.models.deal import Deal, DealStage
from app.db.models.outreach import CampaignStatus, RecipientStatus
from app.services import email_blast
from app.services.email_blast import send_email


def _recipient(
    *,
    contact_email: str = "acme@example.com",
    status: str = RecipientStatus.PENDING.value,
    is_excluded: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="r1",
        tenant_name="Acme Retail",
        contact_email=contact_email,
        status=status,
        is_excluded=is_excluded,
        tracking_id=None,
        sent_at=None,
        error_message=None,
    )


def _campaign(
    *,
    status: str = CampaignStatus.DRAFT.value,
    recipients: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    recips = recipients if recipients is not None else [_recipient()]
    return SimpleNamespace(
        id="c1",
        user_id="u1",
        name="Harper & Ninth outreach",
        property_address="123 Main St, Charlotte, NC",
        property_name="Harper & Ninth",
        subject="Opportunity",
        body_template="<p>Hi {{tenant_name}}</p>",
        from_name="Broker",
        from_email="broker@example.com",
        reply_to=None,
        status=status,
        sent_at=None,
        completed_at=None,
        total_recipients=len(recips),
        sent_count=0,
        bounced_count=0,
        recipients=recips,
    )


def _db_returning(campaign: SimpleNamespace | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=campaign)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)
    db._added = added  # inspected by the tests
    return db


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    successful: int,
    failed: int,
    results: list[SimpleNamespace],
) -> None:
    async def _no_gmail(db, user_id):  # noqa: ANN001, ARG001
        return None

    async def _send(**kwargs):  # noqa: ANN003, ARG001
        return SimpleNamespace(successful=successful, failed=failed, results=results)

    monkeypatch.setattr(outreach_module, "get_user_gmail_tokens", _no_gmail)
    monkeypatch.setattr(outreach_module, "send_campaign_emails", _send)


async def test_send_creates_deal_and_returns_deal_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign = _campaign()
    db = _db_returning(campaign)
    _patch_transport(
        monkeypatch,
        successful=1,
        failed=0,
        results=[
            SimpleNamespace(
                success=True,
                recipient_email="acme@example.com",
                error=None,
                sent_at=datetime(2026, 7, 3, 12, 0, 0),
            )
        ],
    )

    resp = await send_campaign("c1", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]

    # Response carries a usable deal_id (regression: the PK default only fires
    # at flush, so it must be assigned explicitly before commit).
    assert resp.success is True
    assert resp.total_sent == 1
    assert resp.deal_id is not None
    UUID(resp.deal_id)  # parses as a real UUID

    # A Deal card was dropped onto the pipeline in INTAKE, tagged as outreach,
    # with its id matching the returned deal_id and one initial history row.
    deals = [obj for obj in db._added if isinstance(obj, Deal)]
    assert len(deals) == 1
    deal = deals[0]
    assert deal.id == resp.deal_id
    assert deal.stage == DealStage.INTAKE.value
    assert deal.source == "outreach"
    assert deal.user_id == "u1"
    assert len(deal.stage_history) == 1
    assert deal.stage_history[0].to_stage == DealStage.INTAKE.value

    # Campaign + recipient converged to sent state.
    assert campaign.status == CampaignStatus.SENT.value
    assert campaign.sent_count == 1
    assert campaign.recipients[0].status == RecipientStatus.SENT.value
    assert db.commit.await_count >= 1


async def test_send_all_failed_reverts_and_stays_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A total failure (e.g. no email transport) must not fake a send: it 400s,
    # reverts the campaign to its pre-send status, leaves recipients PENDING so
    # it can be re-sent, and creates no deal card.
    campaign = _campaign()
    db = _db_returning(campaign)
    _patch_transport(
        monkeypatch,
        successful=0,
        failed=1,
        results=[
            SimpleNamespace(
                success=False,
                recipient_email="acme@example.com",
                error=(
                    "No email transport configured. Connect Gmail or set "
                    "SMTP_HOST to send campaigns."
                ),
                sent_at=None,
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await send_campaign("c1", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]

    assert exc.value.status_code == 400
    assert "transport" in exc.value.detail
    # Reverted + retryable, no deal.
    assert campaign.status == CampaignStatus.DRAFT.value
    assert campaign.sent_at is None
    assert campaign.recipients[0].status == RecipientStatus.PENDING.value
    assert [obj for obj in db._added if isinstance(obj, Deal)] == []


async def test_scheduled_campaign_can_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Backend accepts SCHEDULED (mirrors the CampaignDetail guardrail that now
    # shows Send for scheduled campaigns too).
    campaign = _campaign(status=CampaignStatus.SCHEDULED.value)
    db = _db_returning(campaign)
    _patch_transport(
        monkeypatch,
        successful=1,
        failed=0,
        results=[
            SimpleNamespace(
                success=True,
                recipient_email="acme@example.com",
                error=None,
                sent_at=datetime(2026, 7, 3, 12, 0, 0),
            )
        ],
    )

    resp = await send_campaign("c1", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]

    assert resp.success is True
    assert resp.deal_id is not None


async def test_send_with_no_pending_recipients_400() -> None:
    # An excluded-only recipient list yields nothing to send.
    campaign = _campaign(recipients=[_recipient(is_excluded=True)])
    db = _db_returning(campaign)

    with pytest.raises(HTTPException) as exc:
        await send_campaign("c1", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert "No recipients" in exc.value.detail


async def test_send_already_sent_400() -> None:
    campaign = _campaign(status=CampaignStatus.SENT.value)
    db = _db_returning(campaign)

    with pytest.raises(HTTPException) as exc:
        await send_campaign("c1", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert "already" in exc.value.detail


async def test_send_campaign_not_found_404() -> None:
    db = _db_returning(None)

    with pytest.raises(HTTPException) as exc:
        await send_campaign("missing", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


async def test_send_email_reports_failure_when_no_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No connected Gmail (gmail_tokens=None) and no SMTP host must be an honest
    # failure, not a synthetic success — otherwise campaigns look "sent" while
    # nothing leaves the machine.
    monkeypatch.setattr(email_blast.settings, "smtp_host", "")

    result = await send_email(
        to_email="me@example.com",
        subject="Hi",
        body_html="<p>Hi</p>",
        from_name="Broker",
        from_email="broker@example.com",
        gmail_tokens=None,
    )

    assert result.success is False
    assert result.error is not None
    assert "transport" in result.error.lower()
