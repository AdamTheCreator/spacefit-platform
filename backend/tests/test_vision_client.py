"""Tests for the platform vision LLM client fallback.

Only the Anthropic provider implements ``vision_document`` today (the
OpenAI-compatible client, which includes Baseten, raises). So when
``LLM_PROVIDER`` is set to any OpenAI-compatible variant,
``get_vision_llm_client`` must transparently fall back to Anthropic — otherwise
document parsing would break for every non-BYOK user once the platform default
flips to Baseten.
"""

from __future__ import annotations

import app.llm.client as llm_client
from app.llm.providers.anthropic_client import AnthropicLLMClient


def _reset_vision_cache() -> None:
    llm_client.get_vision_llm_client.cache_clear()


def test_vision_client_falls_back_to_anthropic_when_provider_is_baseten(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.llm_provider", "baseten")
    monkeypatch.setattr("app.core.config.settings.llm_vision_provider", "")
    monkeypatch.setattr(
        "app.core.config.settings.anthropic_api_key", "anthropic-key"
    )
    _reset_vision_cache()

    client = llm_client.get_vision_llm_client()

    assert isinstance(client, AnthropicLLMClient)
    _reset_vision_cache()


def test_vision_client_falls_back_for_all_openai_compatible_variants(monkeypatch):
    """Every non-Anthropic provider must fall back to Anthropic for vision."""
    for provider in (
        "openai_compatible",
        "openai",
        "google",
        "deepseek",
        "huggingface",
        "baseten",
    ):
        monkeypatch.setattr("app.core.config.settings.llm_provider", provider)
        monkeypatch.setattr("app.core.config.settings.llm_vision_provider", "")
        monkeypatch.setattr(
            "app.core.config.settings.anthropic_api_key", "anthropic-key"
        )
        _reset_vision_cache()

        client = llm_client.get_vision_llm_client()

        assert isinstance(client, AnthropicLLMClient), (
            f"provider={provider} must fall back to Anthropic for vision"
        )
    _reset_vision_cache()


def test_vision_client_uses_anthropic_directly_when_provider_is_anthropic(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.llm_provider", "anthropic")
    monkeypatch.setattr("app.core.config.settings.llm_vision_provider", "")
    monkeypatch.setattr(
        "app.core.config.settings.anthropic_api_key", "anthropic-key"
    )
    _reset_vision_cache()

    client = llm_client.get_vision_llm_client()

    assert isinstance(client, AnthropicLLMClient)
    _reset_vision_cache()


def test_vision_client_honors_explicit_anthropic_vision_override(monkeypatch):
    """LLM_VISION_PROVIDER=anthropic keeps working even when primary is Baseten."""
    monkeypatch.setattr("app.core.config.settings.llm_provider", "baseten")
    monkeypatch.setattr("app.core.config.settings.llm_vision_provider", "anthropic")
    monkeypatch.setattr(
        "app.core.config.settings.anthropic_api_key", "anthropic-key"
    )
    _reset_vision_cache()

    client = llm_client.get_vision_llm_client()

    assert isinstance(client, AnthropicLLMClient)
    _reset_vision_cache()
