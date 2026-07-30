from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.llm.exceptions import LLMConfigurationError
from app.llm.providers.anthropic_client import AnthropicLLMClient
from app.llm.providers.openai_compatible_client import OpenAICompatibleLLMClient
from app.llm.types import (
    LLMChatRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMVisionRequest,
)


class LLMClient(Protocol):
    async def chat(self, request: LLMChatRequest) -> LLMResponse: ...
    def chat_stream(
        self, request: LLMChatRequest
    ) -> AsyncIterator[LLMStreamChunk]: ...
    async def vision_document(self, request: LLMVisionRequest) -> str: ...
    async def aclose(self) -> None: ...


# ---- Hash-keyed client cache (supports per-user BYOK clients) ----
_client_cache: dict[str, LLMClient] = {}


def _cache_key(provider: str, api_key: str, base_url: str) -> str:
    """Deterministic cache key from provider config. Hashes the API key for safety."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return f"{provider}:{key_hash}:{base_url}"


def _build_client(
    *,
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    provider_norm = (provider or "anthropic").lower().strip()

    timeout_seconds = float(settings.llm_timeout_seconds)
    max_retries = int(settings.llm_max_retries)
    max_concurrency = int(settings.llm_max_concurrency)

    if provider_norm == "anthropic":
        return AnthropicLLMClient(
            api_key=api_key or settings.anthropic_api_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_concurrency=max_concurrency,
        )

    if provider_norm in (
        "openai_compatible",
        "openai",
        "google",
        "deepseek",
        "huggingface",
        "baseten",
    ):
        # Resolve the default key and base_url independently so an explicit
        # base_url never suppresses the provider's default key (and vice-versa).
        if provider_norm == "google":
            default_key = settings.google_gemini_api_key
            default_url = settings.google_gemini_base_url
        elif provider_norm == "deepseek":
            default_key = settings.openai_api_key
            default_url = "https://api.deepseek.com/v1"
        elif provider_norm == "openai":
            default_key = settings.openai_api_key
            default_url = "https://api.openai.com/v1"
        elif provider_norm == "huggingface":
            # Serverless router that fronts every HF inference provider and
            # speaks the OpenAI chat-completions dialect.
            default_key = settings.huggingface_api_key
            default_url = settings.huggingface_base_url
        elif provider_norm == "baseten":
            # Self-hosted Qwen2.5-7B + advisor LoRAs on a Baseten L4 via
            # vLLM's OpenAI-compatible /v1 endpoint. No default URL — it is
            # deployment-specific (contains the Baseten model id), so the
            # operator (LLM_PROVIDER=baseten) or the BYOK user must supply it.
            default_key = settings.baseten_api_key
            default_url = settings.baseten_base_url
        else:  # openai_compatible
            default_key = settings.openai_api_key
            default_url = settings.openai_base_url
        resolved_key = api_key or default_key
        resolved_url = base_url or default_url
        return OpenAICompatibleLLMClient(
            api_key=resolved_key,
            base_url=resolved_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_concurrency=max_concurrency,
        )

    raise LLMConfigurationError(
        f"Unsupported LLM provider={provider!r}. Expected 'anthropic', "
        "'openai', 'google', 'deepseek', 'huggingface', 'baseten', or "
        "'openai_compatible'."
    )


def get_or_create_client(
    provider: str,
    api_key: str,
    base_url: str = "",
) -> LLMClient:
    """Get a cached LLM client or create a new one. Thread-safe for async."""
    key = _cache_key(provider, api_key, base_url)
    if key not in _client_cache:
        _client_cache[key] = _build_client(
            provider=provider,
            api_key=api_key,
            base_url=base_url or None,
        )
    return _client_cache[key]


# ---- Backward-compatible singletons (platform key) ----

@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Platform default chat client."""
    return _build_client(provider=settings.llm_provider)


@lru_cache(maxsize=1)
def get_vision_llm_client() -> LLMClient:
    """Platform vision client.

    Only the Anthropic provider implements ``vision_document`` today; every
    OpenAI-compatible provider (including baseten) raises. When the primary
    provider cannot serve vision, fall back to Anthropic using
    ``settings.anthropic_api_key`` so document parsing keeps working even when
    ``LLM_PROVIDER=baseten`` is set globally.
    """
    provider = (
        settings.llm_vision_provider or settings.llm_provider or "anthropic"
    ).lower().strip()
    if provider != "anthropic":
        provider = "anthropic"
    return _build_client(provider=provider)


async def aclose_llm_client() -> None:
    """Close cached clients. Safe to call multiple times."""
    # Close lru_cache singletons
    for getter in (get_llm_client, get_vision_llm_client):
        if getter.cache_info().currsize == 0:
            continue
        client = getter()
        await client.aclose()
        getter.cache_clear()

    # Close hash-keyed BYOK clients
    for client in _client_cache.values():
        try:
            await client.aclose()
        except Exception:
            pass
    _client_cache.clear()
