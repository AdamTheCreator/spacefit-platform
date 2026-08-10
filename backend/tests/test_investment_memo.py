"""Investment-memo flow: intent detection, prompt resolution, and routing.

Covers the dedicated memo path added so a memo request (typed or via a
memo-focused session) uses the INVESTMENT_MEMO system prompt and a
deterministic analyst-led plan instead of the generic Scout fan-out.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.orchestrator import is_investment_memo_request
from app.services.prompt_registry import (
    INVESTMENT_MEMO_PROMPT_ID,
    get_system_prompt,
    get_system_prompt_for_session,
)

# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "create an investment memo",
        "Create an investment memo for this property.",
        "draft a memo on 123 Main St",
        "can you build me an underwriting memo?",
        "write an acquisition memo",
        "generate the deal memo",
        "INVESTMENT MEMO please",
    ],
)
def test_is_investment_memo_request_true(text: str) -> None:
    assert is_investment_memo_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "analyze this property",
        "find coffee shops nearby",
        "what are the demographics here?",
        "memorable tenants in this center",  # 'memo' substring must not match
        "run a void analysis",
    ],
)
def test_is_investment_memo_request_false(text: str) -> None:
    assert is_investment_memo_request(text) is False


# ---------------------------------------------------------------------------
# Prompt resolution
# ---------------------------------------------------------------------------


def test_analysis_type_resolves_to_memo_prompt() -> None:
    prompt = get_system_prompt_for_session(None, "investment_memo")
    assert prompt.prompt_id == INVESTMENT_MEMO_PROMPT_ID


def test_memo_prompt_is_registered() -> None:
    prompt = get_system_prompt(INVESTMENT_MEMO_PROMPT_ID)
    assert "investment memo" in prompt.content.lower()
    # Leads with a recommendation and forbids fabrication.
    assert "Recommendation" in prompt.content
    assert "NEVER invent" in prompt.content


# ---------------------------------------------------------------------------
# Routing: memo intent -> deterministic analyst plan + memo synthesis prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memo_intent_uses_analyst_plan_and_memo_prompt() -> None:
    from app.api import chat as chat_mod

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.events: list[tuple[str, object]] = []

        async def send_json(self, payload: dict) -> None:
            self.events.append((payload.get("type"), payload.get("data")))

    ws = _FakeWebSocket()
    history: list[dict[str, str]] = []

    # plan_workflow must NOT be consulted for memo intent.
    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
    stream_mock = AsyncMock(
        return_value={
            "specialist": "analyst",
            "content": "Analyst: HHI $88k; 24k VPD on the frontage road.",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 200,
            "output_tokens": 60,
        }
    )
    synth_mock = AsyncMock(
        return_value={
            "content": "PURSUE WITH CONDITIONS — strong trade area, needs financials.",
            "input_tokens": 50,
            "output_tokens": 120,
        }
    )
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()
    tools_mock = AsyncMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch("app.api.chat.needs_clarification", clarify_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", tools_mock),
        patch("app.services.orchestrator.plan_workflow", plan_mock, create=True),
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="Create an investment memo for this property.",
            conversation_history=history,
            proj_context={"project_name": "Wendy's Tatum"},
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id="MASTER_DEFAULT",
            s_analysis_type=None,
            user_resolved_llm=None,
        )

    # Deterministic analyst-led plan; the LLM planner is never called.
    assert summary["specialist_plan"] == ["analyst"]
    plan_mock.assert_not_awaited()

    # The user-facing synthesis uses the investment-memo system prompt.
    synth_mock.assert_awaited_once()
    assert synth_mock.await_args.kwargs["system_prompt_id"] == INVESTMENT_MEMO_PROMPT_ID


@pytest.mark.asyncio
async def test_memo_session_analysis_type_forces_memo_prompt() -> None:
    from app.api import chat as chat_mod

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.events: list[tuple[str, object]] = []

        async def send_json(self, payload: dict) -> None:
            self.events.append((payload.get("type"), payload.get("data")))

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
    stream_mock = AsyncMock(
        return_value={
            "specialist": "analyst",
            "content": "Analyst findings.",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 10,
            "output_tokens": 10,
        }
    )
    synth_mock = AsyncMock(
        return_value={"content": "PASS.", "input_tokens": 5, "output_tokens": 5}
    )

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch("app.api.chat.needs_clarification", clarify_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", AsyncMock()),
        patch.object(chat_mod, "record_token_usage", AsyncMock()),
        patch.object(chat_mod, "_schedule_fact_extraction", MagicMock()),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch("app.services.orchestrator.plan_workflow", plan_mock, create=True),
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            # Note: no memo phrasing in the message — the session drives it.
            user_content="Go ahead.",
            conversation_history=[],
            proj_context={"project_name": "Wendy's Tatum"},
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id="MASTER_DEFAULT",
            s_analysis_type="investment_memo",
            user_resolved_llm=None,
        )

    assert summary["specialist_plan"] == ["analyst"]
    plan_mock.assert_not_awaited()
    assert synth_mock.await_args.kwargs["system_prompt_id"] == INVESTMENT_MEMO_PROMPT_ID
