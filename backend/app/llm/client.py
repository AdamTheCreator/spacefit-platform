from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.llm.exceptions import LLMConfigurationError
from app.llm.providers.anthropic_client import AnthropicLLMClient
from app.llm.providers.openai_compatible_client import OpenAICompatibleLLMClient
from app.llm.types import LLMChatRequest, LLMResponse, LLMVisionRequest


class LLMClient(Protocol):
    async def chat(self, request: LLMChatRequest) -> LLMResponse: ...
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

    if provider_norm in ("openai_compatible", "openai", "google", "deepseek"):
        resolved_key = api_key or settings.openai_api_key
        resolved_url = base_url or settings.openai_base_url
        # Provider-specific defaults for base_url
        if not base_url:
            if provider_norm == "google":
                resolved_key = api_key or settings.google_gemini_api_key
                resolved_url = settings.google_gemini_base_url
            elif provider_norm == "deepseek":
                resolved_url = "https://api.deepseek.com/v1"
            elif provider_norm == "openai":
                resolved_url = "https://api.openai.com/v1"
        return OpenAICompatibleLLMClient(
            api_key=resolved_key,
            base_url=resolved_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_concurrency=max_concurrency,
        )

    raise LLMConfigurationError(
        f"Unsupported LLM provider={provider!r}. "
        "Expected 'anthropic', 'openai', 'google', 'deepseek', or 'openai_compatible'."
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
    """Platform vision client (always Anthropic)."""
    provider = settings.llm_vision_provider or settings.llm_provider
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
