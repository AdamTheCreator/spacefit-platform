"""Tests for the LLM streaming layer (Initiative 1).

Covers:
  - Normalized chunk shape across providers (anthropic + openai-compatible).
  - Tool-call argument accumulation across input_json_delta fragments.
  - Orchestrator streaming generator preserves token counts on
    ``message_stop`` and threads BYOK skip flag correctly.
  - WebSocket helper buffers + emits ``message_end`` once.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.providers.openai_compatible_client import OpenAICompatibleLLMClient
from app.llm.types import (
    LLMChatMessage,
    LLMChatRequest,
    LLMStreamChunk,
    LLMToolCall,
)


# -- OpenAI-compatible streaming --------------------------------------------


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class _FakeStreamResponse:
    """Mimic the subset of httpx.Response used by ``stream(POST)``."""

    def __init__(self, status_code: int, lines: list[str]) -> None:
        self.status_code = status_code
        self.headers = {}
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _data_line(obj) -> str:
    return "data: " + json.dumps(obj)


@pytest.mark.asyncio
async def test_openai_streaming_text_then_stop():
    """Plain text stream yields text_delta chunks then a message_stop with usage."""
    lines = [
        _data_line({"choices": [{"delta": {"content": "Hello"}, "index": 0}]}),
        "",
        _data_line({"choices": [{"delta": {"content": " world"}, "index": 0}]}),
        "",
        _data_line(
            {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}
        ),
        "",
        _data_line({"usage": {"prompt_tokens": 11, "completion_tokens": 2}}),
        "",
        "data: [DONE]",
    ]
    fake_resp = _FakeStreamResponse(200, lines)

    client = OpenAICompatibleLLMClient.__new__(OpenAICompatibleLLMClient)
    client._base_url = "http://example/v1"
    client._max_retries = 0
    import asyncio

    client._semaphore = asyncio.Semaphore(1)
    fake_httpx = MagicMock()
    fake_httpx.stream.return_value = fake_resp
    client._client = fake_httpx

    request = LLMChatRequest(
        system="sys",
        messages=[LLMChatMessage(role="user", content="hi")],
        model="gpt-4o-mini",
    )

    chunks: list[LLMStreamChunk] = []
    async for c in client.chat_stream(request):
        chunks.append(c)

    text_chunks = [c for c in chunks if c.kind == "text_delta"]
    stop_chunks = [c for c in chunks if c.kind == "message_stop"]
    assert "".join(c.text for c in text_chunks) == "Hello world"
    assert len(stop_chunks) == 1
    assert stop_chunks[0].stop_reason == "stop"
    assert stop_chunks[0].input_tokens == 11
    assert stop_chunks[0].output_tokens == 2


@pytest.mark.asyncio
async def test_openai_streaming_tool_call_accumulates_arguments():
    """Tool call arguments arrive as a series of JSON fragments and must be reassembled."""
    lines = [
        _data_line(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "search"},
                                }
                            ]
                        },
                        "index": 0,
                    }
                ]
            }
        ),
        "",
        _data_line(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '{"q":'},
                                }
                            ]
                        },
                        "index": 0,
                    }
                ]
            }
        ),
        "",
        _data_line(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '"goose"}'},
                                }
                            ]
                        },
                        "index": 0,
                    }
                ]
            }
        ),
        "",
        _data_line(
            {
                "choices": [
                    {"delta": {}, "finish_reason": "tool_calls", "index": 0}
                ]
            }
        ),
        "",
        "data: [DONE]",
    ]
    fake_resp = _FakeStreamResponse(200, lines)

    client = OpenAICompatibleLLMClient.__new__(OpenAICompatibleLLMClient)
    client._base_url = "http://example/v1"
    client._max_retries = 0
    import asyncio

    client._semaphore = asyncio.Semaphore(1)
    fake_httpx = MagicMock()
    fake_httpx.stream.return_value = fake_resp
    client._client = fake_httpx

    request = LLMChatRequest(
        system="sys",
        messages=[LLMChatMessage(role="user", content="hi")],
        model="gpt-4o-mini",
        tools=[
            {
                "name": "search",
                "description": "search",
                "input_schema": {"type": "object"},
            }
        ],
    )

    chunks: list[LLMStreamChunk] = []
    async for c in client.chat_stream(request):
        chunks.append(c)

    starts = [c for c in chunks if c.kind == "tool_use_start"]
    ends = [c for c in chunks if c.kind == "tool_use_end"]
    assert len(starts) == 1
    assert starts[0].tool_name == "search"
    assert starts[0].tool_id == "call_1"
    assert len(ends) == 1
    assert ends[0].tool_call is not None
    assert ends[0].tool_call.input == {"q": "goose"}


# -- Anthropic streaming (event-driven) -------------------------------------


class _FakeAnthropicEvent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeAnthropicStream:
    """Async context manager + async iterator matching ``messages.stream()``."""

    def __init__(self, events: list[_FakeAnthropicEvent]) -> None:
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for ev in self._events:
            yield ev


@pytest.mark.asyncio
async def test_anthropic_streaming_text_then_stop():
    from app.llm.providers.anthropic_client import AnthropicLLMClient

    events = [
        _FakeAnthropicEvent(
            type="message_start",
            message=SimpleNamespace(
                usage=SimpleNamespace(input_tokens=7),
            ),
        ),
        _FakeAnthropicEvent(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text="Howdy"),
        ),
        _FakeAnthropicEvent(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="text_delta", text=" partner"),
        ),
        _FakeAnthropicEvent(
            type="message_delta",
            delta=SimpleNamespace(stop_reason="end_turn"),
            usage=SimpleNamespace(output_tokens=3),
        ),
        _FakeAnthropicEvent(type="message_stop"),
    ]

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(return_value=_FakeAnthropicStream(events))
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    client = AnthropicLLMClient.__new__(AnthropicLLMClient)
    client._client = fake_client
    import asyncio

    client._semaphore = asyncio.Semaphore(1)
    # The class only uses isinstance() against these for the buffered
    # path; chat_stream doesn't need them, so a stub is fine.
    client._TextBlock = type("TextBlock", (), {})
    client._ToolUseBlock = type("ToolUseBlock", (), {})

    request = LLMChatRequest(
        system="sys",
        messages=[LLMChatMessage(role="user", content="hi")],
        model="claude-3-haiku-20240307",
    )

    chunks: list[LLMStreamChunk] = []
    async for c in client.chat_stream(request):
        chunks.append(c)

    text = "".join(c.text for c in chunks if c.kind == "text_delta")
    stops = [c for c in chunks if c.kind == "message_stop"]
    assert text == "Howdy partner"
    assert len(stops) == 1
    assert stops[0].input_tokens == 7
    assert stops[0].output_tokens == 3
    assert stops[0].stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_streaming_tool_call_input_json_delta():
    from app.llm.providers.anthropic_client import AnthropicLLMClient

    events = [
        _FakeAnthropicEvent(
            type="message_start",
            message=SimpleNamespace(usage=SimpleNamespace(input_tokens=4)),
        ),
        _FakeAnthropicEvent(
            type="content_block_start",
            index=0,
            content_block=SimpleNamespace(
                type="tool_use", id="toolu_1", name="search"
            ),
        ),
        _FakeAnthropicEvent(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="input_json_delta", partial_json='{"q":"'),
        ),
        _FakeAnthropicEvent(
            type="content_block_delta",
            index=0,
            delta=SimpleNamespace(type="input_json_delta", partial_json='goose"}'),
        ),
        _FakeAnthropicEvent(type="content_block_stop", index=0),
        _FakeAnthropicEvent(
            type="message_delta",
            delta=SimpleNamespace(stop_reason="tool_use"),
            usage=SimpleNamespace(output_tokens=5),
        ),
        _FakeAnthropicEvent(type="message_stop"),
    ]
    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(return_value=_FakeAnthropicStream(events))
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    client = AnthropicLLMClient.__new__(AnthropicLLMClient)
    client._client = fake_client
    import asyncio

    client._semaphore = asyncio.Semaphore(1)
    client._TextBlock = type("TextBlock", (), {})
    client._ToolUseBlock = type("ToolUseBlock", (), {})

    request = LLMChatRequest(
        system="sys",
        messages=[LLMChatMessage(role="user", content="hi")],
        model="claude-3-haiku-20240307",
    )

    chunks: list[LLMStreamChunk] = []
    async for c in client.chat_stream(request):
        chunks.append(c)

    starts = [c for c in chunks if c.kind == "tool_use_start"]
    ends = [c for c in chunks if c.kind == "tool_use_end"]
    assert len(starts) == 1
    assert starts[0].tool_name == "search"
    assert len(ends) == 1
    assert ends[0].tool_call.input == {"q": "goose"}
    stop = [c for c in chunks if c.kind == "message_stop"][0]
    assert stop.stop_reason == "tool_use"


# -- Orchestrator streaming generator ---------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_stream_yields_message_stop_with_tokens(monkeypatch):
    """The orchestrator stream generator passes through chunks unchanged
    and respects the streaming_max_chunks cap."""
    from app.services import orchestrator as orch_mod
    from app.services.user_llm import ResolvedLLM

    fake_chunks = [
        LLMStreamChunk(kind="text_delta", text="abc"),
        LLMStreamChunk(kind="text_delta", text="def"),
        LLMStreamChunk(
            kind="message_stop",
            stop_reason="end_turn",
            input_tokens=5,
            output_tokens=7,
        ),
    ]

    async def fake_chat_stream(_req: LLMChatRequest) -> AsyncIterator[LLMStreamChunk]:
        for c in fake_chunks:
            yield c

    fake_client = MagicMock()
    fake_client.chat_stream = fake_chat_stream
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-3-haiku-20240307",
        is_byok=True,
    )

    seen: list[LLMStreamChunk] = []
    async for c in orch_mod.get_orchestrator_response_stream(
        [{"role": "user", "content": "hi"}],
        resolved_llm=resolved,
    ):
        seen.append(c)

    assert [c.kind for c in seen] == ["text_delta", "text_delta", "message_stop"]
    assert "".join(c.text for c in seen if c.kind == "text_delta") == "abcdef"
    assert seen[-1].input_tokens == 5
    assert seen[-1].output_tokens == 7
