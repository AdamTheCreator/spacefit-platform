"""
Connector Health Service — proactive health checks, circuit breakers, and state machine.

Troubleshooting runbook:
- User reports "needs reauth" but claims they logged in:
  Check last_probe_at vs session_last_checked gap. Verify session file exists
  on disk (browser_sessions/{user_id}_{site}.json). Inspect health_meta JSON
  for circuit breaker state — if opened_at is set the breaker may be blocking probes.

- Connector stuck in "error":
  Inspect health_meta.circuit_breaker.opened_at. If older than 30 minutes and
  state is still "open", the half-open retry may be failing silently. Reset via:
    UPDATE site_credentials SET health_meta = NULL, connector_status = 'stale'
    WHERE id = '<credential_id>';

- Probes not running:
  Check _probe_semaphore saturation (max 3 concurrent). Check rate_limit in
  health_meta — max 6 probes/hour enforced. If the browser manager fails to
  initialise Playwright the probe will timeout after 15 s and increment failures.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.credential import SiteCredential
from app.models.credential import ConnectorProbeResponse, ConnectorStatusResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How long before a "connected" probe is considered stale
STALENESS_BROWSER_SESSION_MINUTES = 60
STALENESS_OAUTH_MINUTES = 120  # unused today; ready for future OAuth connectors

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 30 * 60  # 30 minutes

# Rate limiting
MAX_PROBES_PER_HOUR = 6
MIN_PROBE_GAP_SECONDS = 120  # 2 minutes between manual probes

# Probe timeout
PROBE_TIMEOUT_SECONDS = 15.0

# Max concurrent Playwright probes
_probe_semaphore = asyncio.Semaphore(3)


# ---------------------------------------------------------------------------
# health_meta dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CircuitBreakerState:
    failure_count: int = 0
    last_failure_at: str | None = None  # ISO timestamp
    opened_at: str | None = None  # ISO timestamp when breaker opened
    state: str = "closed"  # closed | open | half_open


@dataclass
class ProbeState:
    last_probe_at: str | None = None
    last_probe_duration_ms: int = 0
    consecutive_failures: int = 0
    last_success_at: str | None = None


@dataclass
class RateLimitState:
    probe_timestamps: list[str] = field(default_factory=list)  # ISO timestamps


@dataclass
class ConnectorHealthMeta:
    circuit_breaker: CircuitBreakerState = field(default_factory=CircuitBreakerState)
    probe: ProbeState = field(default_factory=ProbeState)
    rate_limit: RateLimitState = field(default_factory=RateLimitState)

    @classmethod
    def from_json(cls, raw: str | None) -> ConnectorHealthMeta:
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
            return cls(
                circuit_breaker=CircuitBreakerState(**data.get("circuit_breaker", {})),
                probe=ProbeState(**data.get("probe", {})),
                rate_limit=RateLimitState(**data.get("rate_limit", {})),
            )
        except (json.JSONDecodeError, TypeError):
            return cls()

    def to_json(self) -> str:
        return json.dumps(asdict(self))


# ---------------------------------------------------------------------------
# Pure status computation
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _minutes_since(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    # Handle naive datetimes by assuming UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 60.0


def compute_connector_status(
    credential: SiteCredential,
    meta: ConnectorHealthMeta,
) -> str:
    """
    Pure function: compute the connector status from current DB fields + meta.

    Returns one of: connected, stale, needs_reauth, degraded, error, disabled
    """
    # Disabled takes precedence
    if credential.disabled_at is not None:
        return "disabled"

    # Circuit breaker open → error
    if meta.circuit_breaker.state == "open":
        opened = _parse_iso(meta.circuit_breaker.opened_at)
        if opened:
            elapsed = _minutes_since(opened)
            if elapsed is not None and elapsed < (CIRCUIT_BREAKER_COOLDOWN_SECONDS / 60.0):
                return "error"
            # Cooldown expired → half_open (will be retried)

    # Never probed → stale
    last_probe = _parse_iso(meta.probe.last_probe_at) or credential.last_probe_at
    if last_probe is None:
        return "stale"

    # Probe too old → stale
    minutes = _minutes_since(last_probe)
    if minutes is not None and minutes > STALENESS_BROWSER_SESSION_MINUTES:
        return "stale"

    # Consecutive failures → needs_reauth
    if meta.probe.consecutive_failures > 0:
        return "needs_reauth"

    return "connected"


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------

def _is_rate_limited(meta: ConnectorHealthMeta) -> bool:
    """Check if probing is rate-limited."""
    now = datetime.now(timezone.utc)
    one_hour_ago = now.timestamp() - 3600

    # Clean old timestamps
    recent = []
    for ts in meta.rate_limit.probe_timestamps:
        parsed = _parse_iso(ts)
        if parsed and parsed.timestamp() > one_hour_ago:
            recent.append(ts)
    meta.rate_limit.probe_timestamps = recent

    if len(recent) >= MAX_PROBES_PER_HOUR:
        return True

    # Check minimum gap
    if recent:
        last = _parse_iso(recent[-1])
        if last:
            elapsed = (now - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else now - last).total_seconds()
            if elapsed < MIN_PROBE_GAP_SECONDS:
                return True

    return False


def _record_probe_attempt(meta: ConnectorHealthMeta) -> None:
    meta.rate_limit.probe_timestamps.append(_now_iso())


def _should_skip_circuit_breaker(meta: ConnectorHealthMeta) -> bool:
    """Return True if the circuit breaker is open and cooldown hasn't elapsed."""
    cb = meta.circuit_breaker
    if cb.state != "open":
        return False
    opened = _parse_iso(cb.opened_at)
    if not opened:
        return False
    elapsed = _minutes_since(opened)
    if elapsed is not None and elapsed < (CIRCUIT_BREAKER_COOLDOWN_SECONDS / 60.0):
        return True
    # Cooldown elapsed → move to half_open
    cb.state = "half_open"
    return False


async def run_health_probe(
    credential: SiteCredential,
    db: AsyncSession,
) -> ConnectorProbeResponse:
    """
    Run a lightweight health probe against a connector.

    Acquires the probe semaphore, loads the browser context, and checks
    is_logged_in() with a strict timeout.
    """
    meta = ConnectorHealthMeta.from_json(credential.health_meta)
    start_ms = int(time.monotonic() * 1000)

    # Circuit breaker check
    if _should_skip_circuit_breaker(meta):
        return ConnectorProbeResponse(
            credential_id=credential.id,
            connector_status="error",
            probe_duration_ms=0,
            message="Circuit breaker open — retrying after cooldown period.",
        )

    # Rate limit check
    if _is_rate_limited(meta):
        return ConnectorProbeResponse(
            credential_id=credential.id,
            connector_status=credential.connector_status or "stale",
            probe_duration_ms=0,
            message="Rate limited — please wait before probing again.",
        )

    _record_probe_attempt(meta)

    new_status = credential.connector_status or "stale"
    message = ""

    # TODO: Re-implement in Phase 2 (browser/scraper modules were removed)
    # Browser-based probing is disabled. Mark as stale until re-implemented.
    new_status = "stale"
    message = "Browser-based health probes are not available — pending re-implementation."

    # Circuit breaker logic
    if meta.probe.consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
        meta.circuit_breaker.state = "open"
        meta.circuit_breaker.opened_at = _now_iso()
        meta.circuit_breaker.failure_count = meta.probe.consecutive_failures
        new_status = "error"

    duration_ms = int(time.monotonic() * 1000) - start_ms
    meta.probe.last_probe_at = _now_iso()
    meta.probe.last_probe_duration_ms = duration_ms

    # Persist to DB. site_credentials columns are TIMESTAMP WITHOUT TIME
    # ZONE, so strip tzinfo to avoid asyncpg DataError on the adaptation.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(SiteCredential)
        .where(SiteCredential.id == credential.id)
        .values(
            connector_status=new_status,
            health_meta=meta.to_json(),
            last_probe_at=now,
            updated_at=now,
        )
    )
    await db.commit()

    logger.info(
        "connector.probe_completed",
        extra={
            "credential_id": credential.id,
            "site_name": credential.site_name,
            "status": new_status,
            "duration_ms": duration_ms,
            "consecutive_failures": meta.probe.consecutive_failures,
        },
    )

    return ConnectorProbeResponse(
        credential_id=credential.id,
        connector_status=new_status,
        probe_duration_ms=duration_ms,
        message=message,
    )


# ---------------------------------------------------------------------------
# Status queries
# ---------------------------------------------------------------------------

def _site_display_name(site_name: str) -> str:
    # TODO: Re-implement when scraper configs are restored
    return site_name.title()


def _site_requires_manual_login(site_name: str) -> bool:
    # TODO: Re-implement when scraper configs are restored
    return False


async def get_all_connector_statuses(
    user_id: str,
    db: AsyncSession,
) -> list[ConnectorStatusResponse]:
    """Fast DB query — returns computed status for every connector the user has."""
    result = await db.execute(
        select(SiteCredential).where(SiteCredential.user_id == user_id)
    )
    credentials = result.scalars().all()

    statuses = []
    for cred in credentials:
        meta = ConnectorHealthMeta.from_json(cred.health_meta)
        status = compute_connector_status(cred, meta)

        statuses.append(
            ConnectorStatusResponse(
                credential_id=cred.id,
                site_name=cred.site_name,
                site_display_name=_site_display_name(cred.site_name),
                connector_status=status,
                last_probe_at=cred.last_probe_at,
                last_used_at=cred.last_used_at,
                session_error_message=cred.session_error_message,
                requires_manual_login=_site_requires_manual_login(cred.site_name),
            )
        )
    return statuses


# ---------------------------------------------------------------------------
# Background refresh
# ---------------------------------------------------------------------------

async def refresh_stale_connectors(
    user_id: str,
    db: AsyncSession,
) -> None:
    """
    Background task: find stale connectors and probe them.

    Skips connectors probed within the last 10 minutes.
    """
    result = await db.execute(
        select(SiteCredential).where(SiteCredential.user_id == user_id)
    )
    credentials = result.scalars().all()

    for cred in credentials:
        meta = ConnectorHealthMeta.from_json(cred.health_meta)
        status = compute_connector_status(cred, meta)

        if status != "stale":
            continue

        # Skip if probed recently
        last = cred.last_probe_at
        if last is not None:
            minutes = _minutes_since(last)
            if minutes is not None and minutes < 10:
                continue

        try:
            await run_health_probe(cred, db)
        except Exception:
            logger.exception(
                "connector.background_probe_failed",
                extra={"credential_id": cred.id, "site_name": cred.site_name},
            )


# ---------------------------------------------------------------------------
# Success / failure hooks (called from other modules)
# ---------------------------------------------------------------------------

async def update_connector_on_success(
    credential: SiteCredential,
    db: AsyncSession,
) -> None:
    """
    Called after a successful browser login or scrape.

    Resets the circuit breaker and marks the connector as connected.
    """
    meta = ConnectorHealthMeta.from_json(credential.health_meta)
    meta.circuit_breaker = CircuitBreakerState()  # reset
    meta.probe.consecutive_failures = 0
    meta.probe.last_success_at = _now_iso()
    meta.probe.last_probe_at = _now_iso()

    # site_credentials columns are TIMESTAMP WITHOUT TIME ZONE — see
    # comment in run_health_probe above.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(SiteCredential)
        .where(SiteCredential.id == credential.id)
        .values(
            connector_status="connected",
            health_meta=meta.to_json(),
            last_probe_at=now,
            session_status="valid",
            session_last_checked=now,
            session_error_message=None,
            updated_at=now,
        )
    )
    await db.commit()
