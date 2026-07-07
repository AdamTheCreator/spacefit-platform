from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.byok.errors import map_anthropic_exception

logger = logging.getLogger(__name__)
from app.llm.exceptions import LLMConfigurationError
from app.llm.types import (
    LLMChatRequest,
    LLMResponse,
    LLMStreamChunk,
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
            from anthropic.types import (  # type: ignore[import-not-found]
                TextBlock,
                ToolUseBlock,
            )
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

    @staticmethod
    def _sanitize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Enforce Anthropic's alternating-roles requirement.

        - Merge consecutive same-role messages.
        - Strip empty messages.
        - Ensure the first message is "user".
        """
        sanitized: list[dict[str, str]] = []
        for msg in messages:
            content = msg.get("content", "").strip()
            if not content:
                continue
            role = msg["role"]
            if sanitized and sanitized[-1]["role"] == role:
                sanitized[-1]["content"] += "\n\n" + content
            else:
                sanitized.append({"role": role, "content": content})
        # Anthropic requires the first message to be "user"
        if sanitized and sanitized[0]["role"] != "user":
            sanitized.insert(0, {"role": "user", "content": "(continuing conversation)"})
        return sanitized

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        raw_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]
        messages = self._sanitize_messages(raw_messages)
        create_kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": messages,
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
                # Route through the BYOK error mapper so 401/403/429/5xx
                # get distinct codes rather than a single generic failure.
                raise map_anthropic_exception(e) from e

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

    async def chat_stream(
        self, request: LLMChatRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream a chat response chunk-by-chunk.

        Yields normalized ``LLMStreamChunk`` events. Token counts on the
        terminal ``message_stop`` chunk come from Anthropic's
        ``message_delta`` and ``message_stop`` events. Tool-call argument
        JSON arrives in ``input_json_delta`` fragments that we accumulate
        per-tool so callers receive a fully-parsed dict on
        ``tool_use_end``.
        """
        raw_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]
        messages = self._sanitize_messages(raw_messages)
        create_kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": messages,
        }
        if request.temperature is not None:
            create_kwargs["temperature"] = request.temperature
        if request.tools is not None:
            create_kwargs["tools"] = request.tools
        if request.tool_choice is not None:
            create_kwargs["tool_choice"] = request.tool_choice

        # Per-block tool-call accumulators keyed by Anthropic's block index.
        # We need to track these to assemble the final tool_call payload
        # because input JSON arrives as a stream of ``input_json_delta``
        # fragments, not a single object.
        tool_blocks: dict[int, dict[str, Any]] = {}
        input_tokens = 0
        output_tokens = 0
        stop_reason: str | None = None

        async with self._semaphore:
            try:
                async with self._client.messages.stream(**create_kwargs) as stream:
                    async for event in stream:
                        event_type = getattr(event, "type", "")
                        if event_type == "message_start":
                            msg = getattr(event, "message", None)
                            usage = getattr(msg, "usage", None) if msg else None
                            if usage is not None:
                                input_tokens = getattr(
                                    usage, "input_tokens", 0
                                ) or 0
                        elif event_type == "content_block_start":
                            block = getattr(event, "content_block", None)
                            block_type = getattr(block, "type", "")
                            idx = getattr(event, "index", -1)
                            if block_type == "tool_use" and idx >= 0:
                                tool_id = getattr(block, "id", "") or ""
                                name = getattr(block, "name", "") or ""
                                tool_blocks[idx] = {
                                    "id": tool_id,
                                    "name": name,
                                    "json": "",
                                }
                                yield LLMStreamChunk(
                                    kind="tool_use_start",
                                    tool_id=tool_id,
                                    tool_name=name,
                                )
                        elif event_type == "content_block_delta":
                            delta = getattr(event, "delta", None)
                            delta_type = getattr(delta, "type", "")
                            idx = getattr(event, "index", -1)
                            if delta_type == "text_delta":
                                text = getattr(delta, "text", "") or ""
                                if text:
                                    yield LLMStreamChunk(
                                        kind="text_delta", text=text
                                    )
                            elif delta_type == "input_json_delta":
                                fragment = (
                                    getattr(delta, "partial_json", "") or ""
                                )
                                if idx in tool_blocks and fragment:
                                    tool_blocks[idx]["json"] += fragment
                                    yield LLMStreamChunk(
                                        kind="tool_use_delta",
                                        tool_id=tool_blocks[idx]["id"],
                                        partial_json=fragment,
                                    )
                        elif event_type == "content_block_stop":
                            idx = getattr(event, "index", -1)
                            if idx in tool_blocks:
                                block_info = tool_blocks.pop(idx)
                                # Anthropic gives us {} when the tool has
                                # no arguments — guard against that and
                                # also against accumulated bytes that
                                # never form a valid JSON object.
                                try:
                                    parsed = (
                                        json.loads(block_info["json"])
                                        if block_info["json"]
                                        else {}
                                    )
                                except json.JSONDecodeError:
                                    parsed = {
                                        "_raw_arguments": block_info["json"]
                                    }
                                tool_call = LLMToolCall(
                                    id=block_info["id"],
                                    name=block_info["name"],
                                    input=parsed,
                                )
                                yield LLMStreamChunk(
                                    kind="tool_use_end",
                                    tool_id=block_info["id"],
                                    tool_name=block_info["name"],
                                    tool_call=tool_call,
                                )
                        elif event_type == "message_delta":
                            delta = getattr(event, "delta", None)
                            sr = getattr(delta, "stop_reason", None)
                            if sr:
                                stop_reason = sr
                            usage = getattr(event, "usage", None)
                            if usage is not None:
                                output_tokens = (
                                    getattr(usage, "output_tokens", 0) or 0
                                )
                        elif event_type == "message_stop":
                            # Final event — fall through to the terminal
                            # chunk emit after the for-loop.
                            pass
            except Exception as e:
                # Surface the standard BYOK error shape; consumers will
                # see this as an exception out of the generator and can
                # short-circuit. We deliberately do not emit a
                # message_stop here because the orchestrator's finally:
                # block already handles the terminal token-recording
                # path.
                raise map_anthropic_exception(e) from e

        yield LLMStreamChunk(
            kind="message_stop",
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
                # Vision uses the same normalized error surface as chat.
                raise map_anthropic_exception(e) from e

        text_content = ""
        for block in getattr(response, "content", []):
            if isinstance(block, self._TextBlock):
                text_content += block.text
        return text_content
