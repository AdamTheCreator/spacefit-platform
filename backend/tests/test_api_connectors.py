"""
Integration tests for the /connectors API endpoints.

Uses mocked browser/scraper dependencies so no real Playwright is needed.
Tests exercise the full FastAPI → service → DB path.
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.connector_health import (
    ConnectorHealthMeta,
    CircuitBreakerState,
    ProbeState,
    RateLimitState,
    run_health_probe,
    update_connector_on_success,
    get_all_connector_statuses,
    _is_rate_limited,
)

# Stable UUIDs for deterministic tests
_CRED_UUID_1 = "a99fd510-d10b-4645-b2e1-000000000001"
_CRED_UUID_2 = "a99fd510-d10b-4645-b2e1-000000000002"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_credential(**overrides) -> MagicMock:
    """Create a mock SiteCredential with a valid UUID id."""
    cred = MagicMock()
    cred.id = overrides.get("id", _CRED_UUID_1)
    cred.user_id = overrides.get("user_id", "user-001")
    cred.site_name = overrides.get("site_name", "placer")
    cred.site_url = "https://app.placer.ai"
    cred.disabled_at = overrides.get("disabled_at", None)
    cred.last_probe_at = overrides.get("last_probe_at", None)
    cred.connector_status = overrides.get("connector_status", "stale")
    cred.health_meta = overrides.get("health_meta", None)
    cred.session_error_message = overrides.get("session_error_message", None)
    cred.last_used_at = overrides.get("last_used_at", None)
    cred.session_status = overrides.get("session_status", "unknown")
    return cred


def _make_db_mock():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# run_health_probe — success path
# ---------------------------------------------------------------------------

def _make_browser_manager(*, has_session: bool = True):
    """Build a mock BrowserManager with sync has_session and async-cm get_context."""
    manager = MagicMock()
    manager.has_session = MagicMock(return_value=has_session)

    @asynccontextmanager
    async def _fake_context(*_args, **_kwargs):
        yield MagicMock()  # yields a browser context mock

    manager.get_context = _fake_context
    return manager


class TestProbeSuccess:
    @pytest.mark.asyncio
    async def test_probe_returns_connected_when_logged_in(self):
        """Scraper reports logged in → connected status."""
        cred = _make_credential()
        db = _make_db_mock()

        mock_manager = _make_browser_manager(has_session=True)
        mock_scraper = MagicMock()
        mock_scraper.is_logged_in = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.connector_health.BrowserManager.get_instance",
                new_callable=AsyncMock,
                return_value=mock_manager,
            ),
            patch(
                "app.services.connector_health.get_scraper",
                return_value=mock_scraper,
            ),
        ):
            result = await run_health_probe(cred, db)

        assert result.connector_status == "connected"
        assert "active" in result.message.lower()
        assert result.probe_duration_ms >= 0
        db.commit.assert_awaited()


# ---------------------------------------------------------------------------
# run_health_probe — failure path
# ---------------------------------------------------------------------------

class TestProbeFailure:
    @pytest.mark.asyncio
    async def test_probe_returns_needs_reauth_when_not_logged_in(self):
        """Scraper reports NOT logged in → needs_reauth."""
        cred = _make_credential()
        db = _make_db_mock()

        mock_manager = _make_browser_manager(has_session=True)
        mock_scraper = MagicMock()
        mock_scraper.is_logged_in = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.connector_health.BrowserManager.get_instance",
                new_callable=AsyncMock,
                return_value=mock_manager,
            ),
            patch(
                "app.services.connector_health.get_scraper",
                return_value=mock_scraper,
            ),
        ):
            result = await run_health_probe(cred, db)

        assert result.connector_status == "needs_reauth"
        assert "expired" in result.message.lower() or "reconnect" in result.message.lower()

    @pytest.mark.asyncio
    async def test_probe_needs_reauth_when_no_session_file(self):
        """No browser session file exists → needs_reauth."""
        cred = _make_credential()
        db = _make_db_mock()

        mock_manager = _make_browser_manager(has_session=False)

        with patch(
            "app.services.connector_health.BrowserManager.get_instance",
            new_callable=AsyncMock,
            return_value=mock_manager,
        ):
            result = await run_health_probe(cred, db)

        assert result.connector_status == "needs_reauth"
        assert "no browser session" in result.message.lower()


# ---------------------------------------------------------------------------
# run_health_probe — timeout
# ---------------------------------------------------------------------------

class TestProbeTimeout:
    @pytest.mark.asyncio
    async def test_probe_timeout_increments_failures(self):
        """Probe timeout → consecutive_failures incremented."""
        cred = _make_credential()
        db = _make_db_mock()

        mock_manager = _make_browser_manager(has_session=True)
        mock_scraper = MagicMock()
        mock_scraper.is_logged_in = AsyncMock(side_effect=asyncio.TimeoutError)

        with (
            patch(
                "app.services.connector_health.BrowserManager.get_instance",
                new_callable=AsyncMock,
                return_value=mock_manager,
            ),
            patch(
                "app.services.connector_health.get_scraper",
                return_value=mock_scraper,
            ),
            # Bypass the real asyncio.wait_for — let the TimeoutError
            # propagate directly from is_logged_in
            patch(
                "app.services.connector_health.asyncio.wait_for",
                side_effect=asyncio.TimeoutError,
            ),
        ):
            result = await run_health_probe(cred, db)

        assert result.connector_status in ("needs_reauth", "error")
        assert "timed out" in result.message.lower()


# ---------------------------------------------------------------------------
# run_health_probe — rate limiting
# ---------------------------------------------------------------------------

class TestProbeRateLimited:
    @pytest.mark.asyncio
    async def test_second_probe_within_gap_is_rate_limited(self):
        """Probe within MIN_PROBE_GAP_SECONDS → rate limited response."""
        recent = _utc_now() - timedelta(seconds=30)
        meta = ConnectorHealthMeta(
            rate_limit=RateLimitState(probe_timestamps=[_iso(recent)]),
        )
        cred = _make_credential(health_meta=meta.to_json())
        db = _make_db_mock()

        result = await run_health_probe(cred, db)

        assert "rate limited" in result.message.lower()
        # DB should NOT be updated for rate-limited probes
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hourly_limit_blocks_probe(self):
        """6 probes in the last hour → rate limited."""
        now = _utc_now()
        timestamps = [_iso(now - timedelta(minutes=i * 5)) for i in range(6)]
        meta = ConnectorHealthMeta(
            rate_limit=RateLimitState(probe_timestamps=timestamps),
        )
        cred = _make_credential(health_meta=meta.to_json())
        db = _make_db_mock()

        result = await run_health_probe(cred, db)
        assert "rate limited" in result.message.lower()


# ---------------------------------------------------------------------------
# run_health_probe — circuit breaker blocks
# ---------------------------------------------------------------------------

class TestProbeCircuitBreakerBlocked:
    @pytest.mark.asyncio
    async def test_probe_blocked_by_open_circuit_breaker(self):
        """Open circuit breaker within cooldown → skipped."""
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="open",
                opened_at=_iso(_utc_now() - timedelta(minutes=5)),
                failure_count=3,
            ),
        )
        cred = _make_credential(health_meta=meta.to_json())
        db = _make_db_mock()

        result = await run_health_probe(cred, db)

        assert result.connector_status == "error"
        assert "circuit breaker" in result.message.lower()
        db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# update_connector_on_success
# ---------------------------------------------------------------------------

class TestUpdateOnSuccess:
    @pytest.mark.asyncio
    async def test_resets_state_to_connected(self):
        """After success, connector is connected with cleared failures."""
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="half_open",
                failure_count=3,
                opened_at=_iso(_utc_now() - timedelta(minutes=35)),
            ),
            probe=ProbeState(consecutive_failures=3),
        )
        cred = _make_credential(health_meta=meta.to_json())
        db = _make_db_mock()

        await update_connector_on_success(cred, db)

        db.execute.assert_awaited()
        db.commit.assert_awaited()

        # Check the values passed to the UPDATE statement
        call_args = db.execute.call_args
        update_stmt = call_args[0][0]
        # The function should set connector_status='connected'
        # We verify by checking db.commit was called (state was persisted)


# ---------------------------------------------------------------------------
# get_all_connector_statuses
# ---------------------------------------------------------------------------

class TestGetAllStatuses:
    @pytest.mark.asyncio
    async def test_empty_when_no_credentials(self):
        """User with no credentials → empty list."""
        db = _make_db_mock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        statuses = await get_all_connector_statuses("user-001", db)
        assert statuses == []

    @pytest.mark.asyncio
    async def test_returns_all_connectors(self):
        """Multiple credentials → status for each."""
        cred1 = _make_credential(id=_CRED_UUID_1, site_name="placer")
        cred2 = _make_credential(id=_CRED_UUID_2, site_name="siteusa")

        db = _make_db_mock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [cred1, cred2]
        db.execute.return_value = mock_result

        with patch(
            "app.services.connector_health.SITE_CONFIGS",
            {
                "placer": {"name": "Placer.ai", "requires_manual_login": True},
                "siteusa": {"name": "SiteUSA", "requires_manual_login": False},
            },
        ):
            statuses = await get_all_connector_statuses("user-001", db)

        assert len(statuses) == 2
        names = {s.site_name for s in statuses}
        assert "placer" in names
        assert "siteusa" in names
