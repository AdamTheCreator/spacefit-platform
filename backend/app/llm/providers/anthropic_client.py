from __future__ import annotations

import asyncio
from typing import Any

from app.llm.exceptions import LLMConfigurationError, LLMProviderError
from app.llm.types import (
    LLMChatRequest,
    LLMResponse,
    LLMToolCall,
    LLMVisionRequest,
)


class AnthropicLLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        max_retries: int,
        max_concurrency: int,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError(
                "Missing ANTHROPIC_API_KEY (required when LLM_PROVIDER=anthropic)."
            )

        try:
            from anthropic import AsyncAnthropic  # type: ignore[import-not-found]
            from anthropic.types import ToolUseBlock, TextBlock  # type: ignore[import-not-found]
        except Exception as e:  # pragma: no cover - depends on optional install
            raise LLMConfigurationError(
                "Anthropic provider selected but the 'anthropic' package is not installed."
            ) from e

        self._TextBlock = TextBlock
        self._ToolUseBlock = ToolUseBlock
        self._client: Any = AsyncAnthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        create_kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
        }
        if request.temperature is not None:
            create_kwargs["temperature"] = request.temperature
        if request.tools is not None:
            create_kwargs["tools"] = request.tools
        if request.tool_choice is not None:
            create_kwargs["tool_choice"] = request.tool_choice

        async with self._semaphore:
            try:
                response = await self._client.messages.create(**create_kwargs)
            except Exception as e:
                raise LLMProviderError("Anthropic request failed") from e

        text_content = ""
        tool_calls: list[LLMToolCall] = []
        stop_reason: str | None = getattr(response, "stop_reason", None)

        # Extract token usage
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

        for block in getattr(response, "content", []):
            if isinstance(block, self._TextBlock):
                text_content += block.text
            elif isinstance(block, self._ToolUseBlock):
                tool_calls.append(
                    LLMToolCall(id=block.id, name=block.name, input=block.input)
                )

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def aclose(self) -> None:
        # Anthropic SDK versions vary; close if available.
        close_fn = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
        if close_fn is None:
            return
        result = close_fn()
        if asyncio.iscoroutine(result):
            await result

    async def vision_document(self, request: LLMVisionRequest) -> str:
        create_kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": request.document.media_type,
                                "data": request.document.data_base64,
                            },
                        },
                        {"type": "text", "text": request.user_text},
                    ],
                }
            ],
        }

        async with self._semaphore:
            try:
                response = await self._client.messages.create(**create_kwargs)
            except Exception as e:
                raise LLMProviderError("Anthropic vision request failed") from e

        text_content = ""
        for block in getattr(response, "content", []):
            if isinstance(block, self._TextBlock):
                text_content += block.text
        return text_content
