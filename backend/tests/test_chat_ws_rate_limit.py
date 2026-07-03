"""Tests for the shared pre-orchestrator guardrails on the chat WS endpoints.

Covers ``app.api.chat._pre_orchestrator_guardrails`` (message-size + per-user
rate limit), which both ``/ws`` and ``/ws/{session_id}`` call before invoking
the orchestrator. Pure unit tests — no DB, LLM, or WebSocket needed. Each test
swaps in a fresh ``MessageRateLimiter`` so the module singleton's state never
leaks between tests.
"""

from __future__ import annotations

import pytest

from app.api.chat import _pre_orchestrator_guardrails
from app.core.config import settings
from app.services.guardrails import MessageRateLimiter


@pytest.fixture
def fresh_limiter(monkeypatch):
    """Replace the module-level singleton with an isolated limiter per test."""
    limiter = MessageRateLimiter(max_messages=3, window_seconds=60)
    monkeypatch.setattr("app.api.chat.rate_limiter", limiter)
    return limiter


def test_short_message_passes(fresh_limiter):
    ok, err = _pre_orchestrator_guardrails("user-1", "Tell me about the property.")
    assert ok is True
    assert err is None


def test_oversized_message_rejected(fresh_limiter):
    huge = "x" * (settings.guardrail_max_message_chars + 1)
    ok, err = _pre_orchestrator_guardrails("user-1", huge)
    assert ok is False
    assert err is not None
    assert "too long" in err.lower()


def test_rate_limit_exceeded_after_max(fresh_limiter):
    for _ in range(3):
        ok, err = _pre_orchestrator_guardrails("user-1", "hi")
        assert ok is True, err
    ok, err = _pre_orchestrator_guardrails("user-1", "hi")
    assert ok is False
    assert err is not None
    assert "rate limit" in err.lower()


def test_rate_limit_is_per_user(fresh_limiter):
    assert _pre_orchestrator_guardrails("user-a", "hi")[0] is True
    assert _pre_orchestrator_guardrails("user-a", "hi")[0] is True
    assert _pre_orchestrator_guardrails("user-a", "hi")[0] is True
    # user-a is at cap; user-b is unaffected.
    assert _pre_orchestrator_guardrails("user-b", "hi")[0] is True
    assert _pre_orchestrator_guardrails("user-a", "hi")[0] is False


def test_size_check_runs_before_rate_limit(monkeypatch):
    """An oversized message is rejected on size even when the user is at cap."""
    limiter = MessageRateLimiter(max_messages=1, window_seconds=60)
    monkeypatch.setattr("app.api.chat.rate_limiter", limiter)
    # Burn the single allowed message.
    assert _pre_orchestrator_guardrails("user-1", "hi")[0] is True
    # Now over both size and rate — size wins (returns first).
    huge = "x" * (settings.guardrail_max_message_chars + 1)
    ok, err = _pre_orchestrator_guardrails("user-1", huge)
    assert ok is False
    assert "too long" in (err or "").lower()
