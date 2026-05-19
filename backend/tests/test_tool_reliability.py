"""Tests for the tool reliability envelope (Initiative 2).

Covers:
  - ``call_with_reliability`` returns ``ToolError(timeout)`` when the
    wrapped function exceeds its deadline.
  - The circuit breaker trips OPEN after the configured failure burst,
    short-circuits subsequent calls, and recovers via HALF_OPEN ->
    CLOSED on a probe success.
  - Retry policy honors ``is_retryable`` and counts attempts.
  - Classification maps common error shapes to known ``kind`` strings.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.mcp.reliability import (
    DEFAULT_RETRY_POLICY,
    RetryPolicy,
    ToolCircuitBreaker,
    ToolError,
    call_with_reliability,
    classify_exception,
    is_retryable,
    user_message_for,
)


@pytest.mark.asyncio
async def test_timeout_returns_tool_error_quickly():
    async def slow():
        await asyncio.sleep(2.0)
        return "never"

    breaker = ToolCircuitBreaker()
    t0 = time.monotonic()
    result = await call_with_reliability(
        "business_search",
        slow,
        timeout_seconds=0.05,
        retry_policy=RetryPolicy(max_attempts=1),
        breaker=breaker,
    )
    elapsed = time.monotonic() - t0
    assert isinstance(result, ToolError)
    assert result.kind == "timeout"
    assert elapsed < 1.0
    assert "responding slowly" in result.user_message


@pytest.mark.asyncio
async def test_retry_then_success():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise asyncio.TimeoutError("first attempt slow")
        return "ok"

    breaker = ToolCircuitBreaker()
    result = await call_with_reliability(
        "demographics_analysis",
        flaky,
        timeout_seconds=0.5,
        retry_policy=RetryPolicy(
            max_attempts=2, base_delay_seconds=0.0, max_delay_seconds=0.0
        ),
        breaker=breaker,
    )
    assert result == "ok"
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_circuit_breaker_trips_and_short_circuits():
    breaker = ToolCircuitBreaker(failure_threshold=3, cooloff_seconds=10.0)

    async def boom():
        raise ConnectionError("upstream connection refused")

    for _ in range(3):
        result = await call_with_reliability(
            "tenant_roster",
            boom,
            timeout_seconds=0.1,
            retry_policy=RetryPolicy(
                max_attempts=1, base_delay_seconds=0.0, max_delay_seconds=0.0
            ),
            breaker=breaker,
        )
        assert isinstance(result, ToolError)

    assert breaker.state_of("tenant_roster") == "open"

    # Subsequent call should be short-circuited without touching the function.
    sentinel = {"hit": 0}

    async def should_not_run():
        sentinel["hit"] += 1
        return "nope"

    result = await call_with_reliability(
        "tenant_roster",
        should_not_run,
        timeout_seconds=0.1,
        breaker=breaker,
    )
    assert isinstance(result, ToolError)
    assert result.kind == "circuit_open"
    assert sentinel["hit"] == 0


@pytest.mark.asyncio
async def test_circuit_breaker_recovers_after_cooloff():
    breaker = ToolCircuitBreaker(failure_threshold=2, cooloff_seconds=0.05)

    async def boom():
        raise ConnectionError("dns failure")

    async def good():
        return "fine"

    for _ in range(2):
        await call_with_reliability(
            "void_analysis",
            boom,
            timeout_seconds=0.1,
            retry_policy=RetryPolicy(
                max_attempts=1, base_delay_seconds=0.0, max_delay_seconds=0.0
            ),
            breaker=breaker,
        )
    assert breaker.state_of("void_analysis") == "open"
    await asyncio.sleep(0.07)

    result = await call_with_reliability(
        "void_analysis",
        good,
        timeout_seconds=0.5,
        retry_policy=RetryPolicy(
            max_attempts=1, base_delay_seconds=0.0, max_delay_seconds=0.0
        ),
        breaker=breaker,
    )
    assert result == "fine"
    assert breaker.state_of("void_analysis") == "closed"


def test_classify_exception_maps_known_kinds():
    assert classify_exception(asyncio.TimeoutError()) == "timeout"
    assert classify_exception(ConnectionError("refused")) == "network"
    assert classify_exception(Exception("HTTP 401 Unauthorized")) == "upstream_4xx"
    assert classify_exception(Exception("HTTP 503 service unavailable")) == "upstream_5xx"
    assert classify_exception(Exception("429 rate limited")) == "rate_limited"


def test_is_retryable_filters_auth_errors():
    assert is_retryable("timeout") is True
    assert is_retryable("network") is True
    assert is_retryable("rate_limited") is True
    assert is_retryable("upstream_4xx") is False
    assert is_retryable("unknown") is False


def test_user_message_contains_tool_name():
    msg = user_message_for("business_search", "circuit_open")
    assert "business_search" in msg
    assert "unstable" in msg


@pytest.mark.asyncio
async def test_non_retryable_aborts_immediately():
    attempts = {"n": 0}

    async def auth_fail():
        attempts["n"] += 1
        raise Exception("HTTP 401 Unauthorized")

    breaker = ToolCircuitBreaker()
    result = await call_with_reliability(
        "business_search",
        auth_fail,
        timeout_seconds=0.5,
        retry_policy=RetryPolicy(
            max_attempts=3, base_delay_seconds=0.0, max_delay_seconds=0.0
        ),
        breaker=breaker,
    )
    assert isinstance(result, ToolError)
    assert result.kind == "upstream_4xx"
    assert attempts["n"] == 1
