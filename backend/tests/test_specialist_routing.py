"""Coverage for the ``/ws`` specialist routing branch.

This was the biggest coverage gap of the multi-initiative push:
``plan_workflow``, ``call_specialist_stream`` and the synthesis path are
each unit tested in isolation, but the orchestration that wires them
together inside the WebSocket handler had no direct tests. To make that
testable without spinning up FastAPI + a real DB + JWT + an LLM, the
branch was extracted into ``_run_specialist_routing_turn`` (in
``app.api.chat``); this file drives that helper with a fake
``WebSocket`` and patched dependencies.

What we assert:

* Single-specialist plan: emits ``workflow_init`` + per-step
  ``workflow_update`` running/completed, calls
  ``_stream_specialist_to_ws`` exactly once with the carried history,
  appends the only specialist's content to ``conversation_history``,
  persists its transcript line via ``save_message_to_db``,
  short-circuits past the synthesis pass, schedules fact extraction,
  and records token usage (BYOK-aware).
* Multi-specialist plan: emits a workflow_init with N pending steps,
  runs each specialist in order, threads earlier specialists' outputs
  into the next specialist's message history, runs the synthesis
  pass, persists both per-specialist transcripts AND the synthesis
  transcript, and exposes ``synthesized=True``.
* Tool-call delegation: when a specialist returns ``tool_calls`` the
  helper hands them off to ``handle_tool_calls`` with the same
  session/user/context.
* BYOK skip: ``record_token_usage`` is invoked with
  ``is_byok=True`` when the resolved LLM is a BYOK provider.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeWebSocket:
    """Captures every ``send_json``/``send_text`` call as a tuple of (type, data).

    ``app.api.chat.send_ws_message`` calls ``websocket.send_json({type, data})``,
    so we capture in that shape.
    """

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    async def send_json(self, payload: dict) -> None:
        self.events.append((payload.get("type"), payload.get("data")))

    async def send_text(self, payload: str) -> None:  # pragma: no cover - unused
        self.events.append(("__raw_text__", payload))


def _event_types(ws: _FakeWebSocket) -> list[str]:
    return [t for t, _ in ws.events]


# ---------------------------------------------------------------------------
# Single-specialist plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_specialist_plan_streams_and_skips_synthesis():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    history: list[dict[str, str]] = [{"role": "user", "content": "hi"}]

    plan_mock = AsyncMock(return_value=["scout"])
    stream_mock = AsyncMock(
        return_value={
            "specialist": "scout",
            "content": "Found 12 nearby grocery stores within 2 miles.",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 220,
            "output_tokens": 64,
        }
    )
    synth_mock = AsyncMock()  # MUST NOT be called for a single-specialist plan
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()  # sync fire-and-forget in production
    tools_mock = AsyncMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", tools_mock),
        patch(
            "app.services.orchestrator.plan_workflow",
            plan_mock,
            create=True,
        ),
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="What grocery stores are nearby?",
            conversation_history=history,
            proj_context={"project_name": "Greenway"},
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id="MASTER_DEFAULT",
            s_analysis_type=None,
            user_resolved_llm=None,
        )

    # --- shape of the return value
    assert summary["specialist_plan"] == ["scout"]
    assert summary["synthesized"] is False
    assert summary["final_content"].startswith("Found 12")
    assert summary["input_tokens"] == 220
    assert summary["output_tokens"] == 64

    # --- mutations on caller-owned history
    assert history[-1] == {
        "role": "assistant",
        "content": "Found 12 nearby grocery stores within 2 miles.",
    }

    # --- emitted WS frames in order
    types = _event_types(ws)
    assert "workflow_init" in types
    assert types.count("workflow_update") == 2  # running + completed
    # The single-specialist path should NOT fire the synthesis stream.
    synth_mock.assert_not_called()
    # plan_workflow called once.
    plan_mock.assert_awaited_once()
    # The single specialist was streamed.
    stream_mock.assert_awaited_once()
    # Transcript persisted once for the specialist.
    save_mock.assert_awaited_once()
    persisted_args = save_mock.await_args
    assert persisted_args.args[0] == "s-1"
    assert persisted_args.args[1] == "agent"
    assert persisted_args.args[2].startswith("Found 12")
    assert persisted_args.args[3] == "scout"
    # Fact extraction scheduled with the final content.
    schedule_mock.assert_called_once()
    assert (
        schedule_mock.call_args.kwargs["assistant_response"]
        == "Found 12 nearby grocery stores within 2 miles."
    )
    # No tool calls => handle_tool_calls untouched.
    tools_mock.assert_not_called()
    # Token usage recorded; not BYOK.
    record_mock.assert_awaited_once()
    assert record_mock.await_args.args == ("u-1", 220, 64)
    assert record_mock.await_args.kwargs["is_byok"] is False


# ---------------------------------------------------------------------------
# Multi-specialist plan with synthesis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_specialist_plan_runs_synthesis_and_persists_both():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    history: list[dict[str, str]] = []

    plan_mock = AsyncMock(return_value=["scout", "analyst"])

    # Per-call specialist responses (in plan order).
    spec_returns = [
        {
            "specialist": "scout",
            "content": "Scout: 8 nearby grocery, 3 within 1mi.",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 100,
            "output_tokens": 30,
        },
        {
            "specialist": "analyst",
            "content": "Analyst: HHI $92k, growing 3.2%/yr.",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 120,
            "output_tokens": 40,
        },
    ]
    stream_mock = AsyncMock(side_effect=spec_returns)

    synth_mock = AsyncMock(
        return_value={
            "content": (
                "Combined view: solid grocery competition; demographics "
                "support a mid-tier QSR."
            ),
            "input_tokens": 200,
            "output_tokens": 80,
        }
    )
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()
    tools_mock = AsyncMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", tools_mock),
        patch(
            "app.services.orchestrator.plan_workflow",
            plan_mock,
            create=True,
        ),
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="Should we open here?",
            conversation_history=history,
            proj_context=None,
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id=None,
            s_analysis_type=None,
            user_resolved_llm=None,
        )

    # Plan + summary shape
    assert summary["specialist_plan"] == ["scout", "analyst"]
    assert summary["synthesized"] is True
    assert summary["final_content"].startswith("Combined view")

    # Token totals = sum of 2 specialists + synthesis
    assert summary["input_tokens"] == 100 + 120 + 200
    assert summary["output_tokens"] == 30 + 40 + 80

    # Both specialists were called in order.
    assert stream_mock.await_count == 2
    first_call_kwargs = stream_mock.await_args_list[0].kwargs
    second_call_kwargs = stream_mock.await_args_list[1].kwargs
    assert first_call_kwargs["name"] == "scout"
    assert second_call_kwargs["name"] == "analyst"

    # The 2nd specialist must receive the 1st's findings as carried context.
    carried = second_call_kwargs["conversation_history"]
    assert any(
        "Scout findings" in (m.get("content") or "")
        for m in carried
    ), "analyst should see scout's findings injected as an assistant message"

    # Synthesis ran exactly once after both specialists.
    synth_mock.assert_awaited_once()
    synth_history = synth_mock.await_args.kwargs["conversation_history"]
    assert "Synthesize the specialist findings" in synth_history[-1]["content"]
    assert "Scout findings" in synth_history[-1]["content"]
    assert "Analyst findings" in synth_history[-1]["content"]

    # Transcript persisted for each specialist AND the synthesis (3 rows).
    assert save_mock.await_count == 3
    persisted = [c.args for c in save_mock.await_args_list]
    assert persisted[0][3] == "scout"
    assert persisted[1][3] == "analyst"
    assert persisted[2][3] == "orchestrator"

    # Conversation history gets the synthesis content, not the per-specialist.
    assert history[-1] == {"role": "assistant", "content": summary["final_content"]}
    # Fact extraction scheduled once, on the synthesis output.
    schedule_mock.assert_called_once()
    assert (
        schedule_mock.call_args.kwargs["assistant_response"]
        == summary["final_content"]
    )


# ---------------------------------------------------------------------------
# Tool-call delegation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_tool_calls_dispatch_to_handle_tool_calls():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=["scout"])
    tool_calls_blob = [
        {"id": "tu-1", "name": "business_search", "input": {"query": "grocery"}}
    ]
    stream_mock = AsyncMock(
        return_value={
            "specialist": "scout",
            "content": "Let me look that up.",
            "tool_calls": tool_calls_blob,
            "stop_reason": "tool_use",
            "input_tokens": 50,
            "output_tokens": 12,
        }
    )
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()
    tools_mock = AsyncMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", tools_mock),
        patch(
            "app.services.orchestrator.plan_workflow",
            plan_mock,
            create=True,
        ),
    ):
        await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="grocery please",
            conversation_history=[],
            proj_context=None,
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id=None,
            s_analysis_type=None,
            user_resolved_llm=None,
        )

    tools_mock.assert_awaited_once()
    assert tools_mock.await_args.kwargs["tool_calls"] == tool_calls_blob
    assert tools_mock.await_args.kwargs["session_id"] == "s-1"
    assert tools_mock.await_args.kwargs["user_id"] == "u-1"


# ---------------------------------------------------------------------------
# BYOK token-usage flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_byok_resolved_llm_passes_is_byok_true_to_token_usage():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    byok_llm = SimpleNamespace(is_byok=True)

    plan_mock = AsyncMock(return_value=["scout"])
    stream_mock = AsyncMock(
        return_value={
            "specialist": "scout",
            "content": "ok",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 10,
            "output_tokens": 5,
        }
    )
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch(
            "app.services.orchestrator.plan_workflow",
            plan_mock,
            create=True,
        ),
    ):
        await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="hi",
            conversation_history=[],
            proj_context=None,
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id=None,
            s_analysis_type=None,
            user_resolved_llm=byok_llm,  # type: ignore[arg-type]
        )

    record_mock.assert_awaited_once()
    assert record_mock.await_args.kwargs["is_byok"] is True


# ---------------------------------------------------------------------------
# Mid-turn specialist failure: unfinished steps must be swept to "error"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_failure_sweeps_unfinished_steps_to_error():
    """The stuck-chip bug: a specialist leg dying mid-turn used to leave its
    workflow step 'running' forever (the caller's handler sends an error
    bubble but never finalizes steps). The helper must sweep every step that
    hasn't reached a terminal status to 'error' before re-raising."""
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=["scout", "analyst"])
    stream_mock = AsyncMock(
        side_effect=[
            {
                "specialist": "scout",
                "content": "Scout findings.",
                "tool_calls": [],
                "stop_reason": "end_turn",
                "input_tokens": 10,
                "output_tokens": 5,
            },
            RuntimeError("provider exploded mid-analyst"),
        ]
    )
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch(
            "app.services.orchestrator.plan_workflow",
            plan_mock,
            create=True,
        ),
    ):
        with pytest.raises(RuntimeError, match="provider exploded"):
            await chat_mod._run_specialist_routing_turn(
                ws,  # type: ignore[arg-type]
                user_id="u-1",
                session_id="s-1",
                user_content="Should we open here?",
                conversation_history=[],
                proj_context=None,
                doc_context=None,
                user_context=None,
                memory_context=None,
                has_imported_data={"costar": False, "placer": False},
                s_prompt_id=None,
                s_analysis_type=None,
                user_resolved_llm=None,
            )

    updates = [d for t, d in ws.events if t == "workflow_update"]
    by_step: dict[str, list[str]] = {}
    for u in updates:
        by_step.setdefault(u["step_id"], []).append(u["status"])

    # Scout finished normally and must NOT be swept.
    assert by_step["specialist-scout"] == ["running", "completed"]
    # Analyst was running when the leg died -> swept to error, not stranded.
    assert by_step["specialist-analyst"] == ["running", "error"]


# ---------------------------------------------------------------------------
# Empty plan: helper should still record zero tokens and emit nothing weird
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_plan_records_zero_tokens_and_skips_streaming():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=[])
    stream_mock = AsyncMock()
    record_mock = AsyncMock()
    save_mock = AsyncMock()
    schedule_mock = MagicMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch(
            "app.services.orchestrator.plan_workflow",
            plan_mock,
            create=True,
        ),
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="ambiguous question",
            conversation_history=[],
            proj_context=None,
            doc_context=None,
            user_context=None,
            memory_context=None,
            has_imported_data={"costar": False, "placer": False},
            s_prompt_id=None,
            s_analysis_type=None,
            user_resolved_llm=None,
        )

    assert summary["specialist_plan"] == []
    assert summary["synthesized"] is False
    assert summary["final_content"] == ""
    stream_mock.assert_not_called()
    save_mock.assert_not_called()
    schedule_mock.assert_not_called()
    record_mock.assert_awaited_once()
    assert record_mock.await_args.args == ("u-1", 0, 0)
