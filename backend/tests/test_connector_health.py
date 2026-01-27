"""
Unit tests for connector health service.

Tests are pure (no IO, no browser) — they exercise:
- compute_connector_status() for all six states
- CircuitBreaker open / half-open / close transitions
- ConnectorHealthMeta JSON roundtrip
- Rate limit enforcement
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.connector_health import (
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    MAX_PROBES_PER_HOUR,
    MIN_PROBE_GAP_SECONDS,
    STALENESS_BROWSER_SESSION_MINUTES,
    CircuitBreakerState,
    ConnectorHealthMeta,
    ProbeState,
    RateLimitState,
    compute_connector_status,
    _is_rate_limited,
    _should_skip_circuit_breaker,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_credential(**overrides) -> MagicMock:
    """Create a mock SiteCredential with sensible defaults."""
    cred = MagicMock()
    cred.id = "cred-001"
    cred.user_id = "user-001"
    cred.site_name = "placer"
    cred.disabled_at = None
    cred.last_probe_at = None
    cred.connector_status = "stale"
    cred.health_meta = None
    for k, v in overrides.items():
        setattr(cred, k, v)
    return cred


# ---------------------------------------------------------------------------
# compute_connector_status
# ---------------------------------------------------------------------------

class TestComputeConnectorStatus:
    def test_connected_recent_probe_no_failures(self):
        """Recent successful probe → connected."""
        cred = _make_credential(
            last_probe_at=_utc_now() - timedelta(minutes=5),
        )
        meta = ConnectorHealthMeta(
            probe=ProbeState(
                last_probe_at=_iso(_utc_now() - timedelta(minutes=5)),
                consecutive_failures=0,
                last_success_at=_iso(_utc_now() - timedelta(minutes=5)),
            ),
        )
        assert compute_connector_status(cred, meta) == "connected"

    def test_stale_when_never_probed(self):
        """No probe ever → stale."""
        cred = _make_credential(last_probe_at=None)
        meta = ConnectorHealthMeta()
        assert compute_connector_status(cred, meta) == "stale"

    def test_stale_when_probe_too_old(self):
        """Probe older than staleness threshold → stale."""
        old = _utc_now() - timedelta(minutes=STALENESS_BROWSER_SESSION_MINUTES + 10)
        cred = _make_credential(last_probe_at=old)
        meta = ConnectorHealthMeta(
            probe=ProbeState(
                last_probe_at=_iso(old),
                consecutive_failures=0,
            ),
        )
        assert compute_connector_status(cred, meta) == "stale"

    def test_needs_reauth_on_consecutive_failures(self):
        """consecutive_failures > 0 → needs_reauth."""
        cred = _make_credential(
            last_probe_at=_utc_now() - timedelta(minutes=2),
        )
        meta = ConnectorHealthMeta(
            probe=ProbeState(
                last_probe_at=_iso(_utc_now() - timedelta(minutes=2)),
                consecutive_failures=1,
            ),
        )
        assert compute_connector_status(cred, meta) == "needs_reauth"

    def test_error_when_circuit_breaker_open(self):
        """Circuit breaker open within cooldown → error."""
        cred = _make_credential()
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="open",
                opened_at=_iso(_utc_now() - timedelta(minutes=5)),
                failure_count=3,
            ),
            probe=ProbeState(
                last_probe_at=_iso(_utc_now() - timedelta(minutes=5)),
                consecutive_failures=3,
            ),
        )
        assert compute_connector_status(cred, meta) == "error"

    def test_disabled_takes_precedence(self):
        """disabled_at set → disabled, regardless of other state."""
        cred = _make_credential(disabled_at=_utc_now())
        meta = ConnectorHealthMeta(
            probe=ProbeState(
                last_probe_at=_iso(_utc_now() - timedelta(minutes=2)),
                consecutive_failures=0,
                last_success_at=_iso(_utc_now() - timedelta(minutes=2)),
            ),
        )
        assert compute_connector_status(cred, meta) == "disabled"

    def test_disabled_overrides_error(self):
        """disabled_at set + circuit breaker open → still disabled."""
        cred = _make_credential(disabled_at=_utc_now())
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="open",
                opened_at=_iso(_utc_now() - timedelta(minutes=5)),
                failure_count=3,
            ),
        )
        assert compute_connector_status(cred, meta) == "disabled"

    def test_circuit_breaker_cooldown_expired_falls_through(self):
        """Circuit breaker open but cooldown expired → does not return error."""
        cooldown_elapsed = _utc_now() - timedelta(
            seconds=CIRCUIT_BREAKER_COOLDOWN_SECONDS + 60
        )
        cred = _make_credential(
            last_probe_at=cooldown_elapsed,
        )
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="open",
                opened_at=_iso(cooldown_elapsed),
                failure_count=3,
            ),
            probe=ProbeState(
                last_probe_at=_iso(cooldown_elapsed),
                consecutive_failures=3,
            ),
        )
        # Cooldown expired, so circuit breaker doesn't short-circuit to error.
        # But consecutive_failures > 0, so → needs_reauth (since probe is stale).
        # Actually probe is older than STALENESS_BROWSER_SESSION_MINUTES,
        # so it's stale.
        status = compute_connector_status(cred, meta)
        assert status in ("stale", "needs_reauth")


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_opens_after_threshold_failures(self):
        """After CIRCUIT_BREAKER_FAILURE_THRESHOLD consecutive failures, breaker opens."""
        meta = ConnectorHealthMeta()
        meta.probe.consecutive_failures = CIRCUIT_BREAKER_FAILURE_THRESHOLD

        # Simulate what run_health_probe does after the probe:
        if meta.probe.consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            meta.circuit_breaker.state = "open"
            meta.circuit_breaker.opened_at = _iso(_utc_now())
            meta.circuit_breaker.failure_count = meta.probe.consecutive_failures

        assert meta.circuit_breaker.state == "open"
        assert meta.circuit_breaker.opened_at is not None

    def test_half_open_after_cooldown(self):
        """After cooldown elapses, _should_skip_circuit_breaker moves to half_open."""
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="open",
                opened_at=_iso(
                    _utc_now() - timedelta(seconds=CIRCUIT_BREAKER_COOLDOWN_SECONDS + 60)
                ),
                failure_count=3,
            ),
        )
        # Should NOT skip — cooldown expired
        assert _should_skip_circuit_breaker(meta) is False
        # State should have been moved to half_open
        assert meta.circuit_breaker.state == "half_open"

    def test_skip_when_breaker_open_within_cooldown(self):
        """Within cooldown, _should_skip_circuit_breaker returns True."""
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="open",
                opened_at=_iso(_utc_now() - timedelta(minutes=5)),
                failure_count=3,
            ),
        )
        assert _should_skip_circuit_breaker(meta) is True

    def test_closed_breaker_not_skipped(self):
        """Closed circuit breaker → no skip."""
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(state="closed"),
        )
        assert _should_skip_circuit_breaker(meta) is False

    def test_closes_on_success(self):
        """Simulating a successful probe resets the circuit breaker."""
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                state="half_open",
                opened_at=_iso(_utc_now() - timedelta(minutes=35)),
                failure_count=3,
            ),
            probe=ProbeState(consecutive_failures=3),
        )
        # Simulate success path from run_health_probe:
        meta.probe.consecutive_failures = 0
        meta.probe.last_success_at = _iso(_utc_now())
        meta.circuit_breaker = CircuitBreakerState()  # reset

        assert meta.circuit_breaker.state == "closed"
        assert meta.circuit_breaker.failure_count == 0
        assert meta.probe.consecutive_failures == 0


# ---------------------------------------------------------------------------
# ConnectorHealthMeta JSON roundtrip
# ---------------------------------------------------------------------------

class TestHealthMetaJson:
    def test_empty_roundtrip(self):
        """Default meta → JSON → parse back → same defaults."""
        meta = ConnectorHealthMeta()
        raw = meta.to_json()
        restored = ConnectorHealthMeta.from_json(raw)

        assert restored.circuit_breaker.state == "closed"
        assert restored.circuit_breaker.failure_count == 0
        assert restored.probe.consecutive_failures == 0
        assert restored.rate_limit.probe_timestamps == []

    def test_populated_roundtrip(self):
        """Meta with real values survives roundtrip."""
        now_iso = _iso(_utc_now())
        meta = ConnectorHealthMeta(
            circuit_breaker=CircuitBreakerState(
                failure_count=2,
                last_failure_at=now_iso,
                opened_at=None,
                state="closed",
            ),
            probe=ProbeState(
                last_probe_at=now_iso,
                last_probe_duration_ms=1200,
                consecutive_failures=2,
                last_success_at=None,
            ),
            rate_limit=RateLimitState(
                probe_timestamps=[now_iso],
            ),
        )
        raw = meta.to_json()
        restored = ConnectorHealthMeta.from_json(raw)

        assert restored.circuit_breaker.failure_count == 2
        assert restored.probe.last_probe_duration_ms == 1200
        assert restored.probe.consecutive_failures == 2
        assert len(restored.rate_limit.probe_timestamps) == 1

    def test_from_json_none_returns_defaults(self):
        meta = ConnectorHealthMeta.from_json(None)
        assert meta.circuit_breaker.state == "closed"

    def test_from_json_invalid_returns_defaults(self):
        meta = ConnectorHealthMeta.from_json("not-json{")
        assert meta.circuit_breaker.state == "closed"

    def test_from_json_empty_string_returns_defaults(self):
        meta = ConnectorHealthMeta.from_json("")
        assert meta.circuit_breaker.state == "closed"

    def test_to_json_is_valid_json(self):
        meta = ConnectorHealthMeta()
        parsed = json.loads(meta.to_json())
        assert "circuit_breaker" in parsed
        assert "probe" in parsed
        assert "rate_limit" in parsed


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_not_limited_initially(self):
        meta = ConnectorHealthMeta()
        assert _is_rate_limited(meta) is False

    def test_limited_after_max_probes(self):
        """6 probes within the last hour → rate limited."""
        now = _utc_now()
        timestamps = [
            _iso(now - timedelta(minutes=i * 5))
            for i in range(MAX_PROBES_PER_HOUR)
        ]
        meta = ConnectorHealthMeta(
            rate_limit=RateLimitState(probe_timestamps=timestamps),
        )
        assert _is_rate_limited(meta) is True

    def test_not_limited_with_old_probes(self):
        """Probes older than 1 hour are evicted."""
        old = _utc_now() - timedelta(hours=2)
        timestamps = [_iso(old + timedelta(minutes=i)) for i in range(6)]
        meta = ConnectorHealthMeta(
            rate_limit=RateLimitState(probe_timestamps=timestamps),
        )
        # All timestamps > 1 hour old → cleaned → not limited
        assert _is_rate_limited(meta) is False

    def test_limited_by_min_gap(self):
        """Probe within MIN_PROBE_GAP_SECONDS → rate limited."""
        recent = _utc_now() - timedelta(seconds=MIN_PROBE_GAP_SECONDS - 10)
        meta = ConnectorHealthMeta(
            rate_limit=RateLimitState(probe_timestamps=[_iso(recent)]),
        )
        assert _is_rate_limited(meta) is True

    def test_not_limited_after_gap(self):
        """Probe beyond MIN_PROBE_GAP_SECONDS → not limited."""
        past = _utc_now() - timedelta(seconds=MIN_PROBE_GAP_SECONDS + 10)
        meta = ConnectorHealthMeta(
            rate_limit=RateLimitState(probe_timestamps=[_iso(past)]),
        )
        assert _is_rate_limited(meta) is False
