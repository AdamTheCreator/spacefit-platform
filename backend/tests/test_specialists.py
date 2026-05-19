"""Tests for the specialist agent loop (Initiative 3).

Covers:
  - ``plan_workflow`` falls back to scout on parse failure and on LLM error.
  - ``_build_specialist_request`` selects the right model/tools/prompt
    based on the specialist registry and resolved LLM overrides.
  - ``call_specialist_stream`` yields chunks correctly when the
    underlying client streams.
  - The ``_SPECIALIST_TO_AGENT_TYPE`` mapping covers every registered
    specialist (no UI badge will silently fall back to orchestrator).
"""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.specialists.registry import SPECIALIST_REGISTRY
from app.llm.types import (
    LLMChatMessage,
    LLMChatRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMToolCall,
)


@pytest.mark.asyncio
async def test_plan_workflow_falls_back_on_unparseable_response():
    from app.services import orchestrator as orch_mod
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value=LLMResponse(
            content="I do not know, please try again",
            tool_calls=[],
            stop_reason="end_turn",
        )
    )
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
        is_byok=False,
    )
    plan = await orch_mod.plan_workflow("hello", resolved_llm=resolved)
    assert plan == ["scout"]


@pytest.mark.asyncio
async def test_plan_workflow_falls_back_on_llm_error():
    from app.services import orchestrator as orch_mod
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=RuntimeError("boom"))
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
        is_byok=False,
    )
    plan = await orch_mod.plan_workflow("hello", resolved_llm=resolved)
    assert plan == ["scout"]


@pytest.mark.asyncio
async def test_plan_workflow_parses_specialist_list():
    from app.services import orchestrator as orch_mod
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value=LLMResponse(
            content="scout, analyst, matchmaker",
            tool_calls=[],
            stop_reason="end_turn",
        )
    )
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
        is_byok=False,
    )
    plan = await orch_mod.plan_workflow(
        "find me tenants for 123 main st and draft emails",
        resolved_llm=resolved,
    )
    assert plan == ["scout", "analyst", "matchmaker"]


def test_build_specialist_request_uses_registry_prompt_and_tools():
    from app.services.orchestrator import _build_specialist_request
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock()
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-sonnet-4-x",
        is_byok=False,
    )
    request, llm, model = _build_specialist_request(
        name="scout",
        messages=[{"role": "user", "content": "find me a property"}],
        resolved_llm=resolved,
        project_context=None,
        document_context=None,
        request_id="testreq",
    )
    spec = SPECIALIST_REGISTRY["scout"]
    assert spec.system_prompt[:40] in request.system
    # Tools list must be a subset of the specialist's allowed tools.
    tool_names = {t["name"] for t in (request.tools or [])}
    assert tool_names.issubset(set(spec.allowed_tools))
    # ResolvedLLM model wins over the tier default when provided.
    assert model == "claude-sonnet-4-x"


def test_build_specialist_request_per_specialist_override():
    from app.services.orchestrator import _build_specialist_request
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock()
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="default-model",
        is_byok=True,
        specialist_models={"matchmaker": "user-picked-model"},
    )
    _, _, model = _build_specialist_request(
        name="matchmaker",
        messages=[{"role": "user", "content": "match candidates"}],
        resolved_llm=resolved,
        project_context=None,
        document_context=None,
        request_id="req",
    )
    assert model == "user-picked-model"


@pytest.mark.asyncio
async def test_call_specialist_stream_yields_chunks():
    from app.services import orchestrator as orch_mod
    from app.services.user_llm import ResolvedLLM

    expected = [
        LLMStreamChunk(kind="text_delta", text="Found "),
        LLMStreamChunk(kind="text_delta", text="3 sites."),
        LLMStreamChunk(
            kind="message_stop",
            stop_reason="end_turn",
            input_tokens=12,
            output_tokens=4,
        ),
    ]

    async def fake_stream(_req: LLMChatRequest) -> AsyncIterator[LLMStreamChunk]:
        for c in expected:
            yield c

    fake_client = MagicMock()
    fake_client.chat_stream = fake_stream
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
        is_byok=False,
    )

    seen: list[LLMStreamChunk] = []
    async for c in orch_mod.call_specialist_stream(
        name="scout",
        messages=[{"role": "user", "content": "find sites near 123 main"}],
        resolved_llm=resolved,
    ):
        seen.append(c)

    assert [c.kind for c in seen] == [c.kind for c in expected]
    assert "".join(c.text for c in seen if c.kind == "text_delta") == "Found 3 sites."
    assert seen[-1].input_tokens == 12
    assert seen[-1].output_tokens == 4


def test_specialist_agent_type_map_is_complete():
    # If a specialist is added without a UI badge mapping, the workflow
    # strip will silently fall back to the orchestrator color. Catch
    # that early by asserting the map covers every registered name.
    from app.api.chat import _SPECIALIST_TO_AGENT_TYPE

    for name in SPECIALIST_REGISTRY.keys():
        assert name in _SPECIALIST_TO_AGENT_TYPE, (
            f"Specialist {name!r} has no AgentType mapping in chat.py — "
            f"workflow strip would render it as 'orchestrator'."
        )
