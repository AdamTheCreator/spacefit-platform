from __future__ import annotations

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


def _build_client(*, provider: str) -> LLMClient:
    provider_norm = (provider or "anthropic").lower().strip()

    timeout_seconds = float(settings.llm_timeout_seconds)
    max_retries = int(settings.llm_max_retries)
    max_concurrency = int(settings.llm_max_concurrency)

    if provider_norm == "anthropic":
        return AnthropicLLMClient(
            api_key=settings.anthropic_api_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_concurrency=max_concurrency,
        )

    if provider_norm == "openai_compatible":
        if not settings.llm_model:
            raise LLMConfigurationError(
                "LLM_MODEL is required when LLM_PROVIDER=openai_compatible."
            )
        return OpenAICompatibleLLMClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_concurrency=max_concurrency,
        )

    raise LLMConfigurationError(
        f"Unsupported LLM_PROVIDER={provider!r}. Expected 'anthropic' or 'openai_compatible'."
    )


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return _build_client(provider=settings.llm_provider)


@lru_cache(maxsize=1)
def get_vision_llm_client() -> LLMClient:
    provider = settings.llm_vision_provider or settings.llm_provider
    return _build_client(provider=provider)


async def aclose_llm_client() -> None:
    # Close cached clients if present; safe to call multiple times.
    for getter in (get_llm_client, get_vision_llm_client):
        if getter.cache_info().currsize == 0:
            continue
        client = getter()
        await client.aclose()
        getter.cache_clear()
