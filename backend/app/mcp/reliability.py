"""Per-tool reliability primitives: timeouts, circuit breakers, retries.

Initiative 2 — Tool Reliability. The gateway decorator composes these
into a single envelope around every MCP tool so a slow Placer call can
never freeze a chat, and so repeated failures don't drag every user
into the same timeout.

Design notes:
  - Circuit breaker is in-memory + per-process. That's fine while we run
    a single uvicorn worker; the swap to Redis is documented as the
    upgrade path when we add background workers.
  - Errors are returned as ``ToolError`` instances rather than raised so
    the orchestrator's synthesis call can decide what to tell the user
    ("the X service is slow, here's what I have") instead of bubbling
    a stack trace.
  - Retries are conservative: 2 attempts for network-class errors,
    single attempt for 429 honoring Retry-After, no retries for 4xx.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


# Per-tool soft deadline. The wall-clock cap on a single attempt;
# retries multiply this. Tuned to be generous on imports + tight on
# everything else. Override in tests via monkeypatch.
TOOL_TIMEOUTS: dict[str, float] = {
    "business_search": 5.0,
    "demographics_analysis": 10.0,
    "tenant_roster": 8.0,
    "traffic_counts": 12.0,
    "void_analysis": 15.0,
    "costar_import": 20.0,
    "placer_import": 20.0,
    "siteusa_import": 20.0,
    "draft_outreach": 8.0,
}
DEFAULT_TOOL_TIMEOUT_SECONDS = 8.0


# Retry budget per tool kind. Network class errors get a couple
# retries with backoff; auth / validation errors get zero.
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    base_delay_seconds: float = 0.2
    max_delay_seconds: float = 1.6


DEFAULT_RETRY_POLICY = RetryPolicy()


@dataclass
class ToolError:
    """A normalized failure surface.

    ``kind`` is one of ``timeout | circuit_open | network | upstream_5xx
    | upstream_4xx | rate_limited | unknown``. ``user_message`` is what
    the chat surface should show ("the Placer service is responding
    slowly — I'll keep going with what I have"); ``detail`` is the raw
    error retained for logs / audit.
    """

    tool: str
    kind: str
    user_message: str
    detail: str = ""
    elapsed_ms: int = 0


# --- Circuit breaker --------------------------------------------------------


@dataclass
class _BreakerState:
    state: str = "closed"  # closed | open | half_open
    failures: list[float] = field(default_factory=list)
    opened_at: float = 0.0


class ToolCircuitBreaker:
    """Per-tool circuit breaker with a sliding failure window.

    Trips when 5 or more failures land within the last 60s. Stays open
    for 30s, then enters ``half_open`` and lets a single probe through.
    If the probe succeeds the breaker closes; if it fails the cool-off
    restarts.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        window_seconds: float = 60.0,
        cooloff_seconds: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._window = window_seconds
        self._cooloff = cooloff_seconds
        self._states: dict[str, _BreakerState] = {}
        self._lock = asyncio.Lock()

    async def before(self, tool: str) -> bool:
        """Return True if the call should proceed, False if circuit is open.

        Probes during half_open are allowed through (the caller's result
        is reported back via :meth:`record_success` /
        :meth:`record_failure`).
        """
        async with self._lock:
            st = self._states.setdefault(tool, _BreakerState())
            now = time.monotonic()
            if st.state == "open":
                if now - st.opened_at >= self._cooloff:
                    st.state = "half_open"
                    logger.info(
                        "[breaker:%s] cooloff elapsed; entering half_open", tool
                    )
                    return True
                return False
            return True

    async def record_success(self, tool: str) -> None:
        async with self._lock:
            st = self._states.get(tool)
            if not st:
                return
            if st.state == "half_open":
                logger.info("[breaker:%s] probe succeeded; closing", tool)
            st.state = "closed"
            st.failures.clear()
            st.opened_at = 0.0

    async def record_failure(self, tool: str) -> None:
        async with self._lock:
            st = self._states.setdefault(tool, _BreakerState())
            now = time.monotonic()
            st.failures = [t for t in st.failures if now - t < self._window]
            st.failures.append(now)
            if st.state == "half_open":
                logger.warning(
                    "[breaker:%s] probe failed; re-opening for %.0fs",
                    tool,
                    self._cooloff,
                )
                st.state = "open"
                st.opened_at = now
                return
            if len(st.failures) >= self._failure_threshold:
                logger.warning(
                    "[breaker:%s] threshold=%d reached in window=%ds; opening",
                    tool,
                    self._failure_threshold,
                    int(self._window),
                )
                st.state = "open"
                st.opened_at = now

    # Test/inspection hooks ---------------------------------------------------

    def state_of(self, tool: str) -> str:
        return self._states.get(tool, _BreakerState()).state


# Process-wide singleton breaker. Swap to Redis when we add workers.
GLOBAL_TOOL_BREAKER = ToolCircuitBreaker()


# --- Retry classification ---------------------------------------------------


def classify_exception(e: BaseException) -> str:
    """Map a raised exception to a ToolError ``kind`` discriminator.

    Walking the cause chain because the gateway re-raises generic
    ``Exception`` in some legacy paths.
    """
    cls = type(e).__name__.lower()
    msg = str(e).lower()
    if isinstance(e, asyncio.TimeoutError) or "timeout" in cls or "timed out" in msg:
        return "timeout"
    if "rate" in msg or "429" in msg:
        return "rate_limited"
    if "5" in msg and ("server" in msg or "bad gateway" in msg or "service" in msg):
        return "upstream_5xx"
    if "connect" in cls or "network" in cls or "dns" in msg or "refused" in msg:
        return "network"
    if "401" in msg or "403" in msg or "unauthor" in msg or "forbidden" in msg:
        return "upstream_4xx"
    return "unknown"


_USER_MESSAGES: dict[str, str] = {
    "timeout": "The {tool} service is responding slowly — I'll continue without it.",
    "circuit_open": "The {tool} service has been unstable recently; I'm holding off "
    "for a moment and will work with what I have.",
    "network": "I couldn't reach the {tool} service. I'll continue without it.",
    "upstream_5xx": "The {tool} service is having problems on their end. I'll continue without it.",
    "upstream_4xx": "The {tool} service rejected my request. Check the input and try again.",
    "rate_limited": "We've hit the {tool} rate limit. I'll back off and continue with what I have.",
    "unknown": "Something went wrong calling {tool}. I'll continue without it.",
}


def user_message_for(tool: str, kind: str) -> str:
    template = _USER_MESSAGES.get(kind, _USER_MESSAGES["unknown"])
    return template.format(tool=tool)


def is_retryable(kind: str) -> bool:
    return kind in ("timeout", "network", "upstream_5xx", "rate_limited")


# --- The envelope -----------------------------------------------------------


async def call_with_reliability(
    tool: str,
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    timeout_seconds: float | None = None,
    retry_policy: RetryPolicy | None = None,
    breaker: ToolCircuitBreaker | None = None,
    **kwargs: Any,
) -> Any:
    """Run ``fn(*args, **kwargs)`` under per-tool reliability guards.

    Returns whatever ``fn`` returns on success, or a :class:`ToolError`
    on failure (timeout, circuit open, exhausted retries). The caller
    is responsible for serializing ``ToolError`` into the conversation
    so Claude can explain to the user what's unavailable.
    """
    deadline = (
        timeout_seconds
        if timeout_seconds is not None
        else TOOL_TIMEOUTS.get(tool, DEFAULT_TOOL_TIMEOUT_SECONDS)
    )
    policy = retry_policy or DEFAULT_RETRY_POLICY
    breaker = breaker or GLOBAL_TOOL_BREAKER

    if not await breaker.before(tool):
        return ToolError(
            tool=tool,
            kind="circuit_open",
            user_message=user_message_for(tool, "circuit_open"),
            detail="circuit_breaker_open",
            elapsed_ms=0,
        )

    last_error: ToolError | None = None
    for attempt in range(policy.max_attempts):
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=deadline)
            await breaker.record_success(tool)
            return result
        except Exception as e:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            kind = (
                "timeout"
                if isinstance(e, asyncio.TimeoutError)
                else classify_exception(e)
            )
            await breaker.record_failure(tool)
            last_error = ToolError(
                tool=tool,
                kind=kind,
                user_message=user_message_for(tool, kind),
                detail=f"{type(e).__name__}: {e}",
                elapsed_ms=elapsed_ms,
            )
            logger.warning(
                "[reliability:%s] attempt=%d kind=%s elapsed_ms=%d detail=%s",
                tool,
                attempt + 1,
                kind,
                elapsed_ms,
                last_error.detail[:200],
            )
            if attempt + 1 >= policy.max_attempts or not is_retryable(kind):
                break
            # Backoff with light jitter so concurrent retries don't
            # stampede the upstream when it recovers.
            delay = min(
                policy.base_delay_seconds * (2 ** attempt), policy.max_delay_seconds
            )
            delay = delay * (0.8 + 0.4 * random.random())
            await asyncio.sleep(delay)

    return last_error
