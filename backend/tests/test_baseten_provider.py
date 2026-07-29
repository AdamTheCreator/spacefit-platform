"""Tests for the Baseten provider wiring.

Baseten hosts the self-tuned Qwen2.5-7B + advisor LoRAs on an L4 via vLLM's
OpenAI-compatible /v1 endpoint, so it reuses ``OpenAICompatibleLLMClient``.
These tests confirm the provider is registered end-to-end (settings -> client
builder -> BYOK resolution metadata -> frontend-visible provider list) without
needing a live deployment.
"""

from __future__ import annotations

import pytest

from app.api.ai_config import SUPPORTED_PROVIDERS
from app.llm.client import _build_client
from app.llm.exceptions import LLMConfigurationError
from app.llm.providers.openai_compatible_client import OpenAICompatibleLLMClient
from app.services.user_llm import PROVIDER_DEFAULT_MODELS, VALIDATION_MODELS


def test_baseten_builds_openai_compatible_client():
    """Baseten routes through the OpenAI-compatible client pointed at the L4."""
    client = _build_client(
        provider="baseten", api_key="baseten-key", base_url="https://model-x.api.baseten.co/v1"
    )
    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client._base_url == "https://model-x.api.baseten.co/v1"


def test_baseten_defaults_pull_from_settings(monkeypatch):
    """With no explicit key/url, the builder falls back to the Baseten settings."""
    monkeypatch.setattr("app.core.config.settings.baseten_api_key", "cfg-key")
    monkeypatch.setattr(
        "app.core.config.settings.baseten_base_url", "https://from-settings/v1"
    )
    client = _build_client(provider="baseten")
    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client._base_url == "https://from-settings/v1"


def test_baseten_registered_in_user_llm_defaults():
    """BYOK resolution knows Baseten's default + validation models."""
    assert "baseten" in PROVIDER_DEFAULT_MODELS
    assert "baseten" in VALIDATION_MODELS
    # Validation probes base Qwen (always loaded on the L4 alongside the LoRAs).
    assert VALIDATION_MODELS["baseten"] == "Qwen/Qwen2.5-7B-Instruct"


def test_baseten_listed_in_supported_providers():
    """The /ai-config/providers endpoint surfaces Baseten with the advisor models."""
    baseten = next(p for p in SUPPORTED_PROVIDERS if p["id"] == "baseten")
    assert baseten["requires_key"] is True
    assert baseten["requires_base_url"] is True
    assert baseten["default_model"] == "Qwen/Qwen2.5-7B-Instruct"
    models = baseten["models"]
    assert "Qwen/Qwen2.5-7B-Instruct" in models
    assert "spacegoose-advisor-v3" in models
    # The latest advisor LoRA is offered.
    assert any(m.startswith("spacegoose-advisor") for m in models)


def test_unknown_provider_still_rejected():
    with pytest.raises(LLMConfigurationError):
        _build_client(provider="not-a-real-provider")
