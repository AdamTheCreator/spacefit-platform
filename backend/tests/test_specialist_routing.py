"""Coverage for the ``/ws`` specialist routing branch.

The branch was extracted into ``_run_specialist_routing_turn`` (in
``app.api.chat``); this file drives that helper with a fake
``WebSocket`` and patched dependencies.

Behavior under test (current contract):

* The user only ever sees a single "Space Goose Assistant" bubble per
  turn. Specialists run silently (``stream_to_client=False``); only the
  final synthesized orchestrator message is persisted to the transcript.
* The clarification gate trips on vague input: ``needs_clarification``
  returns True -> no ``workflow_init``, no specialist streaming, one
  orchestrator clarifying turn, one persisted ``orchestrator`` row.
* Multi-specialist plan: emits a workflow_init with N pending steps,
  runs each specialist in order, threads earlier specialists' outputs
  into the next specialist's message history, runs the synthesis pass,
  persists only the synthesis transcript, and exposes
  ``synthesized=True``.
* Tool-call delegation: when a specialist returns ``tool_calls`` the
  helper hands them off to ``handle_tool_calls``; synthesis still runs.
* BYOK skip: ``record_token_usage`` is invoked with ``is_byok=True``
  when the resolved LLM is a BYOK provider.
* Empty plan: records zero tokens and skips streaming/synthesis.
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
# Single-specialist plan -> now always synthesizes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_specialist_plan_always_synthesizes():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    history: list[dict[str, str]] = [{"role": "user", "content": "hi"}]

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
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
    synth_mock = AsyncMock(
        return_value={
            "content": "Synthesized: 12 nearby grocery stores within 2 miles.",
            "input_tokens": 40,
            "output_tokens": 30,
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
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
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

    assert summary["specialist_plan"] == ["scout"]
    assert summary["synthesized"] is True
    assert summary["final_content"].startswith("Synthesized")
    # Tokens = specialist + synthesis
    assert summary["input_tokens"] == 220 + 40
    assert summary["output_tokens"] == 64 + 30

    # History gets the synthesis content (single assistant voice)
    assert history[-1] == {"role": "assistant", "content": summary["final_content"]}

    # Specialist ran silently
    stream_mock.assert_awaited_once()
    assert stream_mock.await_args.kwargs["stream_to_client"] is False

    # Synthesis always runs now
    synth_mock.assert_awaited_once()

    # Only the synthesis transcript is persisted (one row, orchestrator)
    save_mock.assert_awaited_once()
    persisted_args = save_mock.await_args
    assert persisted_args.args[0] == "s-1"
    assert persisted_args.args[1] == "agent"
    assert persisted_args.args[2].startswith("Synthesized")
    assert persisted_args.args[3] == "orchestrator"

    # Fact extraction scheduled with the synthesis content
    schedule_mock.assert_called_once()
    assert schedule_mock.call_args.kwargs["assistant_response"] == summary["final_content"]  # noqa: E501

    tools_mock.assert_not_called()
    plan_mock.assert_awaited_once()
    # Attached project context makes the turn self-evidently READY, so the
    # clarification LLM round-trip is skipped (a TTFT optimization).
    clarify_mock.assert_not_awaited()
    record_mock.assert_awaited_once()
    assert record_mock.await_args.args == ("u-1", 260, 94)
    assert record_mock.await_args.kwargs["is_byok"] is False

    # workflow_init + running/completed events still emitted
    types = _event_types(ws)
    assert "workflow_init" in types
    assert types.count("workflow_update") == 2


# ---------------------------------------------------------------------------
# Multi-specialist plan with synthesis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_specialist_plan_runs_synthesis_and_persists_only_synthesis():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    history: list[dict[str, str]] = []

    plan_mock = AsyncMock(return_value=["scout", "analyst"])
    clarify_mock = AsyncMock(return_value=False)

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
            "content": "Combined view: solid grocery competition; demographics support a mid-tier QSR.",  # noqa: E501
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
        patch("app.api.chat.needs_clarification", clarify_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", tools_mock),
        patch("app.services.orchestrator.plan_workflow", plan_mock, create=True),
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
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

    assert summary["specialist_plan"] == ["scout", "analyst"]
    assert summary["synthesized"] is True
    assert summary["final_content"].startswith("Combined view")
    assert summary["input_tokens"] == 100 + 120 + 200
    assert summary["output_tokens"] == 30 + 40 + 80

    assert stream_mock.await_count == 2
    for call in stream_mock.await_args_list:
        assert call.kwargs["stream_to_client"] is False

    # The 2nd specialist must receive the 1st's findings as carried context.
    carried = stream_mock.await_args_list[1].kwargs["conversation_history"]
    assert any("Scout findings" in (m.get("content") or "") for m in carried)

    synth_mock.assert_awaited_once()
    synth_history = synth_mock.await_args.kwargs["conversation_history"]
    assert "Synthesize the specialist findings" in synth_history[-1]["content"]
    assert "Scout findings" in synth_history[-1]["content"]
    assert "Analyst findings" in synth_history[-1]["content"]

    # Only the synthesis transcript is persisted (1 row, not 3)
    save_mock.assert_awaited_once()
    assert save_mock.await_args.args[3] == "orchestrator"

    assert history[-1] == {"role": "assistant", "content": summary["final_content"]}
    schedule_mock.assert_called_once()
    assert schedule_mock.call_args.kwargs["assistant_response"] == summary["final_content"]  # noqa: E501


# ---------------------------------------------------------------------------
# Tool-call delegation (synthesis still runs after)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_tool_calls_dispatch_to_handle_tool_calls():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
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
    synth_mock = AsyncMock(
        return_value={"content": "Here is what I found.", "input_tokens": 30, "output_tokens": 20}  # noqa: E501
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
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
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
    # Synthesis still runs after tool execution; one orchestrator row persisted.
    synth_mock.assert_awaited_once()
    save_mock.assert_awaited_once()
    assert save_mock.await_args.args[3] == "orchestrator"


# ---------------------------------------------------------------------------
# BYOK token-usage flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_byok_resolved_llm_passes_is_byok_true_to_token_usage():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    byok_llm = SimpleNamespace(is_byok=True)

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
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
    synth_mock = AsyncMock(
        return_value={"content": "ok synth", "input_tokens": 4, "output_tokens": 3}
    )
    save_mock = AsyncMock()
    record_mock = AsyncMock()
    schedule_mock = MagicMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch("app.api.chat.needs_clarification", clarify_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch("app.services.orchestrator.plan_workflow", plan_mock, create=True),
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
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
    # Token total includes synthesis
    assert record_mock.await_args.args == ("u-1", 14, 8)


# ---------------------------------------------------------------------------
# Empty plan: helper should still record zero tokens and skip streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_plan_records_zero_tokens_and_skips_streaming():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=[])
    clarify_mock = AsyncMock(return_value=False)
    stream_mock = AsyncMock()
    synth_mock = AsyncMock()
    record_mock = AsyncMock()
    save_mock = AsyncMock()
    schedule_mock = MagicMock()

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch("app.api.chat.needs_clarification", clarify_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", stream_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", record_mock),
        patch.object(chat_mod, "_schedule_fact_extraction", schedule_mock),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch("app.services.orchestrator.plan_workflow", plan_mock, create=True),
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
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
    synth_mock.assert_not_called()
    save_mock.assert_not_called()
    schedule_mock.assert_not_called()
    record_mock.assert_awaited_once()
    assert record_mock.await_args.args == ("u-1", 0, 0)


# ---------------------------------------------------------------------------
# Clarification gate: vague input skips specialists entirely
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clarification_gate_skips_specialists():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=["scout"])  # should NOT be called
    clarify_mock = AsyncMock(return_value=True)
    stream_mock = AsyncMock()  # should NOT be called
    synth_mock = AsyncMock(
        return_value={
            "content": "Sure - what property address would you like me to analyze?",
            "input_tokens": 60,
            "output_tokens": 18,
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
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="Analyze property",
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

    clarify_mock.assert_awaited_once()
    plan_mock.assert_not_called()
    stream_mock.assert_not_called()
    tools_mock.assert_not_called()

    # No workflow_init/progress strip on the clarification path
    types = _event_types(ws)
    assert "workflow_init" not in types
    assert "workflow_update" not in types

    # One orchestrator clarifying turn, persisted once
    synth_mock.assert_awaited_once()
    save_mock.assert_awaited_once()
    assert save_mock.await_args.args[1] == "agent"
    assert save_mock.await_args.args[3] == "orchestrator"

    assert summary["specialist_plan"] == []
    assert summary["synthesized"] is False
    assert summary["final_content"].startswith("Sure")
    assert summary["input_tokens"] == 60
    assert summary["output_tokens"] == 18

    schedule_mock.assert_called_once()
    assert schedule_mock.call_args.kwargs["assistant_response"] == summary["final_content"]  # noqa: E501
    record_mock.assert_awaited_once()
    assert record_mock.await_args.args == ("u-1", 60, 18)
    assert record_mock.await_args.kwargs["is_byok"] is False


# ---------------------------------------------------------------------------
# needs_clarification helper: READY default on error, BYOK client threading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_needs_clarification_helper_ready_default_on_error():
    from app.services import orchestrator as orch_mod

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=RuntimeError("boom"))

    with patch.object(orch_mod, "get_llm_client", return_value=fake_client):
        result = await orch_mod.needs_clarification("Analyze 123 Main St")

    assert result is False


@pytest.mark.asyncio
async def test_needs_clarification_helper_threads_byok_client():
    from app.services import orchestrator as orch_mod

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value=SimpleNamespace(content="CLARIFY\n")
    )
    byok_llm = SimpleNamespace(
        client=fake_client, model="custom-model", is_byok=True, specialist_models={}
    )

    with patch.object(orch_mod, "get_llm_client") as get_mock:
        result = await orch_mod.needs_clarification("hi", resolved_llm=byok_llm)

    assert result is True
    # BYOK path must NOT touch the platform client
    get_mock.assert_not_called()
    sent = fake_client.chat.await_args.args[0]
    assert sent.model == "custom-model"


# ---------------------------------------------------------------------------
# Platform-default resolution: LLM_PROVIDER=baseten cascades to both tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", ["free", "pro"])
def test_resolve_platform_default_baseten_routes_both_tiers(monkeypatch, tier):
    from app.core.config import settings
    from app.services import user_llm as user_llm_mod

    monkeypatch.setattr(settings, "llm_provider", "baseten")
    monkeypatch.setattr(settings, "llm_model", "spacegoose-advisor-v3")
    monkeypatch.setattr(settings, "baseten_api_key", "test-baseten-key")
    monkeypatch.setattr(
        settings,
        "baseten_base_url",
        "https://model-3m50kp6w.api.baseten.co/environments/production/sync/v1",
    )
    monkeypatch.setattr(settings, "baseten_model", "Qwen/Qwen2.5-7B-Instruct")

    sentinel_client = MagicMock(name="baseten_client")
    factory_mock = MagicMock(return_value=sentinel_client)
    monkeypatch.setattr(user_llm_mod, "get_or_create_client", factory_mock)

    resolved = user_llm_mod._resolve_platform_default(tier)

    assert resolved.provider == "baseten"
    assert resolved.model == "spacegoose-advisor-v3"
    assert resolved.is_byok is False
    assert resolved.client is sentinel_client
    factory_mock.assert_called_once_with(
        provider="baseten",
        api_key="test-baseten-key",
        base_url=(
            "https://model-3m50kp6w.api.baseten.co/environments/production/sync/v1"
        ),
    )


def test_resolve_platform_default_baseten_falls_back_to_baseten_model(monkeypatch):
    """When LLM_MODEL is unset, `model` falls back to settings.baseten_model."""
    from app.core.config import settings
    from app.services import user_llm as user_llm_mod

    monkeypatch.setattr(settings, "llm_provider", "baseten")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "baseten_api_key", "cfg-key")
    monkeypatch.setattr(settings, "baseten_base_url", "https://from-settings/v1")
    monkeypatch.setattr(settings, "baseten_model", "Qwen/Qwen2.5-7B-Instruct")

    monkeypatch.setattr(
        user_llm_mod, "get_or_create_client", MagicMock(return_value=MagicMock())
    )
    resolved = user_llm_mod._resolve_platform_default("free")
    assert resolved.provider == "baseten"
    assert resolved.model == "Qwen/Qwen2.5-7B-Instruct"


# ---------------------------------------------------------------------------
# Specialist cascade: platform default v3 propagates to all four specialists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "specialist_name", ["scout", "analyst", "matchmaker", "outreach"]
)
def test_build_specialist_request_cascades_platform_default_v3(specialist_name):
    from app.services.orchestrator import _build_specialist_request
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock(name="baseten_client")
    resolved = ResolvedLLM(
        client=fake_client,
        provider="baseten",
        model="spacegoose-advisor-v3",
        is_byok=False,
        specialist_models=None,
    )

    request, llm, effective_model = _build_specialist_request(
        name=specialist_name,
        messages=[{"role": "user", "content": "analyze 337 W Mariposa Rd"}],
        resolved_llm=resolved,
        project_context=None,
        document_context=None,
        request_id=f"req-{specialist_name}",
    )

    assert effective_model == "spacegoose-advisor-v3"
    assert request.model == "spacegoose-advisor-v3"
    assert llm is fake_client


def test_build_specialist_request_byok_override_wins_over_platform_default():
    """Per-specialist BYOK model override still beats the resolved default."""
    from app.services.orchestrator import _build_specialist_request
    from app.services.user_llm import ResolvedLLM

    fake_client = MagicMock(name="byok_client")
    resolved = ResolvedLLM(
        client=fake_client,
        provider="anthropic",
        model="claude-opus-4-6",
        is_byok=True,
        specialist_models={"analyst": "claude-sonnet-4-6"},
    )

    _, _, analyst_model = _build_specialist_request(
        name="analyst",
        messages=[{"role": "user", "content": "run the numbers"}],
        resolved_llm=resolved,
        project_context=None,
        document_context=None,
        request_id="req-analyst",
    )
    _, _, scout_model = _build_specialist_request(
        name="scout",
        messages=[{"role": "user", "content": "find sites"}],
        resolved_llm=resolved,
        project_context=None,
        document_context=None,
        request_id="req-scout",
    )

    assert analyst_model == "claude-sonnet-4-6"
    assert scout_model == "claude-opus-4-6"


# ---------------------------------------------------------------------------
# TTFT: concrete-target heuristic skips the clarification gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message, expected",
    [
        ("29 Lovell Ave Mill Valley CA find coffee shops", True),
        ("void analysis for 1842 Boston Post Rd", True),
        ("demographics for 90210", True),
        ("what are cap rates in Phoenix retail?", False),
        ("Analyze property", False),
        ("hi", False),
        ("", False),
    ],
)
def test_message_has_concrete_target(message, expected):
    from app.services.orchestrator import message_has_concrete_target

    assert message_has_concrete_target(message) is expected


@pytest.mark.asyncio
async def test_concrete_address_skips_clarification_gate():
    """A message that names a street address is self-evidently READY, so the
    clarification LLM call is skipped while planning + synthesis still run."""
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
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
    synth_mock = AsyncMock(
        return_value={"content": "Synthesized.", "input_tokens": 8, "output_tokens": 4}
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
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
    ):
        summary = await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="void analysis for 1842 Boston Post Rd",
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

    # The gate LLM call is skipped entirely on an obviously-ready message.
    clarify_mock.assert_not_awaited()
    # Planning + synthesis still happen.
    plan_mock.assert_awaited_once()
    synth_mock.assert_awaited_once()
    assert summary["synthesized"] is True


# ---------------------------------------------------------------------------
# Intermediate leak fix: internal tool execution stays off the transcript
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_tool_calls_internal_hides_results_and_skips_synthesis():
    """In ``internal=True`` mode raw tool outputs are neither emitted as
    ``message`` events nor persisted, and no competing orchestrator synthesis
    runs. The executed results are returned so the caller can fold them into
    its single synthesis."""
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    exec_mock = AsyncMock(return_value="RAW DEMOGRAPHICS DUMP")
    synth_mock = AsyncMock()
    save_mock = AsyncMock()

    with (
        patch.object(chat_mod, "execute_tool", exec_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
    ):
        results = await chat_mod.handle_tool_calls(
            websocket=ws,  # type: ignore[arg-type]
            tool_calls=[
                {
                    "id": "tu-1",
                    "name": "demographics_analysis",
                    "input": {"location": "1842 Boston Post Rd"},
                }
            ],
            session_id="s-1",
            user_id="u-1",
            conversation_history=[],
            user_context=None,
            internal=True,
        )

    # Raw results returned to the caller.
    assert isinstance(results, list)
    assert results[0]["tool_name"] == "demographics_analysis"
    assert results[0]["result"] == "RAW DEMOGRAPHICS DUMP"

    # No user-facing message bubble, no persistence, no competing synthesis.
    assert "message" not in _event_types(ws)
    save_mock.assert_not_awaited()
    synth_mock.assert_not_awaited()

    # The progress strip still gets a completion event for the tool step.
    assert ("workflow_update", {"step_id": "tu-1", "status": "completed"}) in ws.events


@pytest.mark.asyncio
async def test_handle_tool_calls_legacy_persists_hidden_result():
    """The legacy (``internal=False``) path still persists the raw tool row —
    but always hidden (``visible=False``) so it never renders, even for a tool
    that maps to no specific AgentType."""
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()

    exec_mock = AsyncMock(return_value="RAW DUMP")
    synth_mock = AsyncMock(
        return_value={"content": "answer", "tool_calls": [], "input_tokens": 1, "output_tokens": 1}  # noqa: E501
    )
    save_mock = AsyncMock()

    with (
        patch.object(chat_mod, "execute_tool", exec_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", save_mock),
        patch.object(chat_mod, "record_token_usage", AsyncMock()),
    ):
        await chat_mod.handle_tool_calls(
            websocket=ws,  # type: ignore[arg-type]
            tool_calls=[
                {"id": "tu-9", "name": "some_unmapped_tool", "input": {}}
            ],
            session_id="s-1",
            user_id="u-1",
            conversation_history=[],
            user_context=None,
        )

    # The raw tool row is persisted hidden (visible=False), never as a
    # visible transcript bubble.
    raw_saves = [
        c for c in save_mock.await_args_list if c.args[3] == "some_unmapped_tool"
    ]
    assert raw_saves, "raw tool result should still be persisted in legacy mode"
    assert raw_saves[0].kwargs["visible"] is False

# ---------------------------------------------------------------------------
# Conversation-aware routing: the gate/planner see prior turns, so follow-ups
# ("generate an investment memo") stop tripping CLARIFY on addresses the user
# already gave. Regression coverage for the in-conversation amnesia bug.
# ---------------------------------------------------------------------------


def test_recent_history_digest_drops_live_turn_and_truncates():
    from app.services.orchestrator import _recent_history_digest

    history = [
        {"role": "user", "content": "void analysis for 120 Post Rd W, Westport CT"},
        {"role": "assistant", "content": "x" * 1000},
        {"role": "user", "content": "generate an investment memo"},
    ]
    digest = _recent_history_digest(history, "generate an investment memo")

    # The live turn (passed separately to the triage call) is not repeated.
    assert "generate an investment memo" not in digest
    # Prior turns are present, long ones truncated.
    assert "120 Post Rd W" in digest
    assert "[…]" in digest
    assert digest.startswith("User: ")


def test_recent_history_digest_empty_without_prior_turns():
    from app.services.orchestrator import _recent_history_digest

    assert _recent_history_digest(None, "hi") == ""
    assert _recent_history_digest([], "hi") == ""
    # A history that only contains the live turn digests to nothing.
    live_only = [{"role": "user", "content": "hi"}]
    assert _recent_history_digest(live_only, "hi") == ""


@pytest.mark.asyncio
async def test_needs_clarification_includes_history_in_triage_prompt():
    from app.services import orchestrator as orch_mod

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value=SimpleNamespace(content="READY"))

    history = [
        {"role": "user", "content": "run a void analysis for 120 Post Rd W, Westport CT 06880"},  # noqa: E501
        {"role": "assistant", "content": "Here is the void analysis…"},
        {"role": "user", "content": "Can you generate an investment memo"},
    ]

    with patch.object(orch_mod, "get_llm_client", return_value=fake_client):
        result = await orch_mod.needs_clarification(
            "Can you generate an investment memo", history=history
        )

    assert result is False
    sent = fake_client.chat.await_args.args[0]
    # The triage call must see the property the conversation established.
    assert "120 Post Rd W" in sent.system
    assert "Recent conversation" in sent.system


@pytest.mark.asyncio
async def test_plan_workflow_includes_history_in_planning_prompt():
    from app.services import orchestrator as orch_mod

    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value=SimpleNamespace(content="analyst"))

    history = [
        {"role": "user", "content": "void analysis for 120 Post Rd W, Westport CT"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "generate the memo"},
    ]

    with patch.object(orch_mod, "get_llm_client", return_value=fake_client):
        plan = await orch_mod.plan_workflow("generate the memo", history=history)

    assert plan == ["analyst"]
    sent = fake_client.chat.await_args.args[0]
    assert "120 Post Rd W" in sent.system


@pytest.mark.asyncio
async def test_routing_turn_threads_history_into_gate_and_planner():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    history = [
        {"role": "user", "content": "tell me about the Westport office market"},
        {"role": "assistant", "content": "It is strong."},
        {"role": "user", "content": "generate an investment memo"},
    ]

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=False)
    stream_mock = AsyncMock(
        return_value={
            "specialist": "scout",
            "content": "ok",
            "tool_calls": [],
            "stop_reason": "end_turn",
            "input_tokens": 1,
            "output_tokens": 1,
        }
    )
    synth_mock = AsyncMock(
        return_value={"content": "memo", "input_tokens": 1, "output_tokens": 1}
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
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
    ):
        await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content="generate an investment memo",
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

    assert clarify_mock.await_args.kwargs["history"] is history
    assert plan_mock.await_args.kwargs["history"] is history


@pytest.mark.asyncio
async def test_clarify_path_folds_note_into_live_turn_without_duplication():
    """The clarify note is merged into the live user turn already present in
    history — previously the whole user message was appended a second time."""
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    user_content = "Analyze property"
    history = [{"role": "user", "content": user_content}]

    plan_mock = AsyncMock(return_value=["scout"])
    clarify_mock = AsyncMock(return_value=True)
    synth_mock = AsyncMock(
        return_value={"content": "Which property?", "input_tokens": 1, "output_tokens": 1}  # noqa: E501
    )

    with (
        patch("app.api.chat.plan_workflow", plan_mock, create=True),
        patch("app.api.chat.needs_clarification", clarify_mock, create=True),
        patch.object(chat_mod, "_stream_specialist_to_ws", AsyncMock()),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", synth_mock),
        patch.object(chat_mod, "save_message_to_db", AsyncMock()),
        patch.object(chat_mod, "record_token_usage", AsyncMock()),
        patch.object(chat_mod, "_schedule_fact_extraction", MagicMock()),
        patch.object(chat_mod, "handle_tool_calls", AsyncMock()),
        patch("app.services.orchestrator.plan_workflow", plan_mock, create=True),
        patch("app.services.orchestrator.needs_clarification", clarify_mock, create=True),  # noqa: E501
    ):
        await chat_mod._run_specialist_routing_turn(
            ws,  # type: ignore[arg-type]
            user_id="u-1",
            session_id="s-1",
            user_content=user_content,
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

    clar_history = synth_mock.await_args.kwargs["conversation_history"]
    user_turns = [m for m in clar_history if m["role"] == "user"]
    # One user turn only: the live message with the note folded in.
    assert len(user_turns) == 1
    assert user_turns[0]["content"].startswith(user_content)
    assert "(Note:" in user_turns[0]["content"]
    # The caller's history object is untouched by the note.
    assert history[0]["content"] == user_content


# ---------------------------------------------------------------------------
# Tool grounding: session-tracked address backfills vague location args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_tool_calls_fallback_address_grounds_vague_location():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    exec_mock = AsyncMock(return_value="RESULTS")

    with (
        patch.object(chat_mod, "execute_tool", exec_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", AsyncMock()),
        patch.object(chat_mod, "save_message_to_db", AsyncMock()),
    ):
        await chat_mod.handle_tool_calls(
            websocket=ws,  # type: ignore[arg-type]
            tool_calls=[
                {
                    "id": "tu-1",
                    "name": "business_search",
                    "input": {"query": "coffee shops", "location": "this address"},
                }
            ],
            session_id="s-1",
            user_id="u-1",
            conversation_history=[],
            user_context=None,
            internal=True,
            fallback_address="120 Post Rd W, Westport, CT 06880",
        )

    sent_input = exec_mock.await_args.args[1]
    assert sent_input["location"] == "120 Post Rd W, Westport, CT 06880"
    # Non-location args are preserved.
    assert sent_input["query"] == "coffee shops"


@pytest.mark.asyncio
async def test_handle_tool_calls_fallback_address_never_overrides_explicit():
    from app.api import chat as chat_mod

    ws = _FakeWebSocket()
    exec_mock = AsyncMock(return_value="RESULTS")

    with (
        patch.object(chat_mod, "execute_tool", exec_mock),
        patch.object(chat_mod, "_stream_orchestrator_to_ws", AsyncMock()),
        patch.object(chat_mod, "save_message_to_db", AsyncMock()),
    ):
        await chat_mod.handle_tool_calls(
            websocket=ws,  # type: ignore[arg-type]
            tool_calls=[
                {
                    "id": "tu-1",
                    "name": "business_search",
                    "input": {"query": "gyms", "location": "1842 Boston Post Rd, Milford CT"},  # noqa: E501
                }
            ],
            session_id="s-1",
            user_id="u-1",
            conversation_history=[],
            user_context=None,
            internal=True,
            fallback_address="120 Post Rd W, Westport, CT 06880",
        )

    sent_input = exec_mock.await_args.args[1]
    assert sent_input["location"] == "1842 Boston Post Rd, Milford CT"


def test_seed_address_from_history_prefers_latest_concrete_user_turn():
    from app.api.chat import _seed_address_from_history

    history = [
        {"role": "user", "content": "void analysis for 1842 Boston Post Rd"},
        {"role": "assistant", "content": "…analysis…"},
        {"role": "user", "content": "now look at 120 Post Rd W, Westport CT 06880"},
        {"role": "assistant", "content": "…contains 999 Fake St but is not a user turn…"},  # noqa: E501
        {"role": "user", "content": "thanks!"},
    ]
    seeded = _seed_address_from_history(history)
    assert seeded == "now look at 120 Post Rd W, Westport CT 06880"


def test_seed_address_from_history_returns_none_without_target():
    from app.api.chat import _seed_address_from_history

    assert _seed_address_from_history([]) is None
    assert (
        _seed_address_from_history(
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ]
        )
        is None
    )
