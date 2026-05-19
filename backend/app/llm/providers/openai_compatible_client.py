from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.byok.errors import (
    BYOKError,
    map_openai_exception,
    map_openai_http_response,
)
from app.llm.exceptions import LLMConfigurationError, LLMProviderError
from app.llm.types import (
    LLMChatRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMToolCall,
    LLMVisionRequest,
)


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        max_concurrency: int,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError(
                "Missing OPENAI_API_KEY (required when LLM_PROVIDER=openai_compatible)."
            )
        if not base_url:
            raise LLMConfigurationError(
                "Missing OPENAI_BASE_URL (required when LLM_PROVIDER=openai_compatible)."
            )

        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        self._max_retries = max(0, max_retries)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def chat(self, request: LLMChatRequest) -> LLMResponse:
        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system}]
        messages.extend(
            {"role": m.role, "content": m.content}
            for m in request.messages
        )

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        if request.tools is not None:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in request.tools
            ]
            if request.tool_choice is not None:
                # Best-effort mapping:
                # Anthropic uses {"type": "any"} to force tool usage.
                if request.tool_choice.get("type") == "any":
                    payload["tool_choice"] = "required"
                else:
                    payload["tool_choice"] = "auto"

        url = f"{self._base_url}/chat/completions"

        last_error: Exception | None = None
        async with self._semaphore:
            for attempt in range(self._max_retries + 1):
                try:
                    resp = await self._client.post(url, json=payload)
                except Exception as e:
                    # Network-level failure (no response object). Map to
                    # timeout / unavailable / generic based on exception
                    # class and retry if the classification says so.
                    last_error = e
                    mapped = map_openai_exception(e)
                    if attempt >= self._max_retries or not mapped.retryable:
                        raise mapped from e
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue

                mapped = map_openai_http_response(resp)
                if mapped is None:
                    data = resp.json()
                    break
                # Got a response but it's an error. If it's retryable
                # (429 with Retry-After, 5xx), honor the cooldown hint
                # on retries but only if we have budget left.
                last_error = mapped
                if attempt >= self._max_retries or not mapped.retryable:
                    raise mapped
                sleep_for = mapped.retry_after_seconds or min(2 ** attempt, 8)
                await asyncio.sleep(sleep_for)
            else:  # pragma: no cover — loop always breaks or raises
                if isinstance(last_error, BYOKError):
                    raise last_error
                raise LLMProviderError("OpenAI-compatible request failed") from last_error

        try:
            choice0 = data["choices"][0]
            message = choice0["message"]
        except Exception as e:
            # 2xx body that doesn't match the chat-completions schema. Treat
            # as a provider-side bug rather than a user-fixable issue.
            raise BYOKError(
                code="provider_server_error",
                http_status=502,
                retryable=False,
                message="Provider returned an unexpected response shape.",
            ) from e

        content = message.get("content") or ""
        stop_reason = choice0.get("finish_reason")

        tool_calls: list[LLMToolCall] = []
        for tc in message.get("tool_calls") or []:
            func = tc.get("function") or {}
            name = func.get("name") or ""
            args_raw = func.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except Exception:
                args = {"_raw_arguments": args_raw}
            tool_calls.append(
                LLMToolCall(
                    id=tc.get("id") or "",
                    name=name,
                    input=args,
                )
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )

    async def chat_stream(
        self, request: LLMChatRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream an OpenAI-compatible chat completion.

        OpenAI streams arrive as ``data: {…}\\n\\n`` SSE frames; tool calls
        come back as ``message.tool_calls[i].function.arguments`` JSON
        fragments that we accumulate per tool-call index, mirroring the
        Anthropic path so the orchestrator sees the same chunk shapes
        regardless of provider.
        """
        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system}]
        messages.extend(
            {"role": m.role, "content": m.content} for m in request.messages
        )

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": True,
            # Ask for token usage on the terminal chunk where the
            # provider supports it (OpenAI 2024+, DeepSeek). Providers
            # that don't honor this option simply ignore it.
            "stream_options": {"include_usage": True},
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.tools is not None:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in request.tools
            ]
            if request.tool_choice is not None:
                if request.tool_choice.get("type") == "any":
                    payload["tool_choice"] = "required"
                else:
                    payload["tool_choice"] = "auto"

        url = f"{self._base_url}/chat/completions"

        # Per-index tool accumulators. OpenAI keys tool_calls by index
        # within choices[0].delta.tool_calls; arguments stream as a
        # series of partial JSON strings under the same index.
        tool_accum: dict[int, dict[str, Any]] = {}
        announced_indices: set[int] = set()
        stop_reason: str | None = None
        input_tokens = 0
        output_tokens = 0

        async with self._semaphore:
            try:
                async with self._client.stream("POST", url, json=payload) as resp:
                    mapped = map_openai_http_response(resp)
                    if mapped is not None:
                        # Eagerly consume body so the error has a useful
                        # detail for the caller's log line.
                        await resp.aread()
                        raise mapped

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Usage frame (final, no choices on some providers).
                        usage = event.get("usage")
                        if usage:
                            input_tokens = usage.get("prompt_tokens", input_tokens) or 0
                            output_tokens = (
                                usage.get("completion_tokens", output_tokens) or 0
                            )

                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}
                        finish_reason = choice.get("finish_reason")
                        if finish_reason:
                            stop_reason = finish_reason

                        content = delta.get("content")
                        if content:
                            yield LLMStreamChunk(
                                kind="text_delta", text=content
                            )

                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            func = tc.get("function") or {}
                            entry = tool_accum.setdefault(
                                idx, {"id": "", "name": "", "json": ""}
                            )
                            tool_id = tc.get("id")
                            if tool_id:
                                entry["id"] = tool_id
                            name = func.get("name")
                            if name:
                                entry["name"] = name
                            args_frag = func.get("arguments") or ""
                            if args_frag:
                                entry["json"] += args_frag

                            # Emit a single tool_use_start the first time
                            # we see this index with both an id and a name.
                            if (
                                idx not in announced_indices
                                and entry["id"]
                                and entry["name"]
                            ):
                                announced_indices.add(idx)
                                yield LLMStreamChunk(
                                    kind="tool_use_start",
                                    tool_id=entry["id"],
                                    tool_name=entry["name"],
                                )
                            if args_frag and entry["id"]:
                                yield LLMStreamChunk(
                                    kind="tool_use_delta",
                                    tool_id=entry["id"],
                                    partial_json=args_frag,
                                )
            except BYOKError:
                raise
            except Exception as e:
                raise map_openai_exception(e) from e

        # Emit terminal tool_use_end events in stable index order, then
        # the message_stop.
        for idx in sorted(tool_accum.keys()):
            entry = tool_accum[idx]
            if not entry["id"]:
                # Server stopped emitting before completing this tool
                # call; surface to the caller as a no-op rather than
                # synthesizing a malformed LLMToolCall.
                continue
            try:
                parsed = json.loads(entry["json"]) if entry["json"] else {}
            except json.JSONDecodeError:
                parsed = {"_raw_arguments": entry["json"]}
            yield LLMStreamChunk(
                kind="tool_use_end",
                tool_id=entry["id"],
                tool_name=entry["name"],
                tool_call=LLMToolCall(
                    id=entry["id"], name=entry["name"], input=parsed
                ),
            )

        yield LLMStreamChunk(
            kind="message_stop",
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def vision_document(self, request: LLMVisionRequest) -> str:
        raise LLMConfigurationError(
            "Vision document extraction is not supported for LLM_PROVIDER=openai_compatible. "
            "Use LLM_PROVIDER=anthropic for document parsing."
        )
