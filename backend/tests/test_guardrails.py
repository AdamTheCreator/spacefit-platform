"""Unit tests for the topic-classification guardrail (`app.services.guardrails`).

These lock down the fix that keeps ``_classify_with_haiku`` from unconditionally
sending the retired ``claude-3-5-haiku-*`` model id to whichever LLM client is
active. In particular:

  * When the caller passes a ``ResolvedLLM`` (BYOK or non-BYOK platform default),
    the outgoing ``LLMChatRequest.model`` must equal ``resolved_llm.model`` so a
    Baseten client never receives an Anthropic model id.
  * When no ``ResolvedLLM`` is supplied, the classifier falls back to a provider-
    appropriate default (``settings.baseten_model`` / ``settings.google_gemini_model``
    / ``settings.anthropic_model``) rather than the legacy
    ``settings.guardrail_classifier_model`` string.
  * Regex tiers still short-circuit — clearly-CRE and clearly-off-topic messages
    never invoke the LLM.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import settings
from app.llm import types as llm_types
from app.llm.types import LLMResponse
from app.services import guardrails as guardrails_module
from app.services.guardrails import (
    _classifier_model,
    _classify_with_haiku,
    classify_message,
)
from app.services.user_llm import ResolvedLLM


class _FakeClient:
    """Minimal LLMClient stand-in that records the ``LLMChatRequest`` it receives."""

    def __init__(self, content: str = "CRE") -> None:
        self._content = content
        self.calls: list[Any] = []

    async def chat(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        return LLMResponse(
            content=self._content,
            tool_calls=[],
            stop_reason="end_turn",
        )

    async def aclose(self) -> None:  # pragma: no cover
        pass


class _RaisingClient:
    """Blows up if the guardrail unexpectedly invokes the LLM."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def chat(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        raise AssertionError(
            "LLM classifier was called for a regex-decidable message"
        )

    async def aclose(self) -> None:  # pragma: no cover
        pass


def _resolved(client: Any, *, model: str, provider: str, is_byok: bool) -> ResolvedLLM:
    return ResolvedLLM(
        client=client,
        model=model,
        provider=provider,
        is_byok=is_byok,
    )


_AMBIGUOUS_MESSAGE = "Can you double-check that number for me before I send it?"


async def test_classify_with_haiku_uses_resolved_baseten_model() -> None:
    fake = _FakeClient(content="CRE")
    resolved = _resolved(
        fake,
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=True,
    )

    result = await _classify_with_haiku(_AMBIGUOUS_MESSAGE, resolved_llm=resolved)

    assert result == "CRE"
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert isinstance(request, llm_types.LLMChatRequest)
    assert request.model == "spacegoose-advisor-v3"
    assert "haiku" not in request.model.lower()
    assert "claude" not in request.model.lower()


async def test_classify_with_haiku_uses_resolved_anthropic_model() -> None:
    fake = _FakeClient(content="CRE")
    resolved = _resolved(
        fake,
        model="claude-haiku-4-5",
        provider="anthropic",
        is_byok=True,
    )

    result = await _classify_with_haiku(_AMBIGUOUS_MESSAGE, resolved_llm=resolved)

    assert result == "CRE"
    assert len(fake.calls) == 1
    assert fake.calls[0].model == "claude-haiku-4-5"


async def test_classify_message_regex_allow_never_invokes_llm(monkeypatch) -> None:
    fake = _RaisingClient()

    def _boom() -> Any:  # pragma: no cover - only fires on regression
        raise AssertionError(
            "get_llm_client should not be reached when regex tiers ALLOW"
        )

    monkeypatch.setattr(guardrails_module, "logger", guardrails_module.logger)
    monkeypatch.setattr("app.llm.get_llm_client", _boom)

    resolved = _resolved(
        fake,
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=True,
    )

    ok, err = await classify_message(
        "What's the cap rate on this shopping center lease?",
        resolved_llm=resolved,
    )

    assert ok is True
    assert err is None
    assert fake.calls == []


async def test_classify_message_regex_block_never_invokes_llm(monkeypatch) -> None:
    fake = _RaisingClient()

    def _boom() -> Any:  # pragma: no cover - only fires on regression
        raise AssertionError(
            "get_llm_client should not be reached when regex tiers BLOCK"
        )

    monkeypatch.setattr("app.llm.get_llm_client", _boom)

    resolved = _resolved(
        fake,
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=True,
    )

    ok, err = await classify_message(
        "Write me a python function that computes the fibonacci sequence.",
        resolved_llm=resolved,
    )

    assert ok is False
    assert err is not None
    assert fake.calls == []


def test_classifier_model_prefers_resolved_over_default() -> None:
    resolved = _resolved(
        _FakeClient(),
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=False,
    )
    assert _classifier_model(resolved) == "spacegoose-advisor-v3"


def test_classifier_model_falls_back_to_baseten_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "baseten")
    monkeypatch.setattr(settings, "baseten_model", "spacegoose-advisor-v3")
    assert _classifier_model(None) == "spacegoose-advisor-v3"


def test_classifier_model_falls_back_to_google_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "google")
    monkeypatch.setattr(settings, "google_gemini_model", "gemini-2.0-flash")
    assert _classifier_model(None) == "gemini-2.0-flash"


def test_classifier_model_falls_back_to_anthropic_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_model", "claude-haiku-4-5")
    assert _classifier_model(None) == "claude-haiku-4-5"


async def test_classify_with_haiku_non_byok_uses_platform_client(monkeypatch) -> None:
    """A non-BYOK ``ResolvedLLM`` still routes through the process-wide platform
    client (as before), but the outgoing model id now matches ``resolved_llm.model``
    instead of the retired ``guardrail_classifier_model`` string."""
    platform_client = _FakeClient(content="CRE")
    monkeypatch.setattr(
        "app.llm.get_llm_client",
        lambda: platform_client,
    )

    resolved = _resolved(
        _FakeClient(),
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=False,
    )

    result = await _classify_with_haiku(_AMBIGUOUS_MESSAGE, resolved_llm=resolved)

    assert result == "CRE"
    assert len(platform_client.calls) == 1
    assert platform_client.calls[0].model == "spacegoose-advisor-v3"


@pytest.mark.parametrize(
    "content",
    [
        "Tell me about the tenant mix at the Main St shopping center.",
        "What's the void analysis for this strip mall?",
        "Compare cap rates and NOI for these two properties.",
    ],
)
async def test_classify_message_cre_terms_short_circuit_allow(content: str) -> None:
    ok, err = await classify_message(content, resolved_llm=None)
    assert ok is True
    assert err is None


@pytest.mark.parametrize(
    "content",
    [
        "Write a python function that solves an integral.",
        "Diagnose my symptoms please, my knee hurts.",
        "Pretend you are a pirate and roleplay a treasure hunt.",
    ],
)
async def test_classify_message_off_topic_short_circuits_block(content: str) -> None:
    ok, err = await classify_message(content, resolved_llm=None)
    assert ok is False
    assert err is not None
