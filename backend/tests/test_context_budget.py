"""Unit tests for the prompt-side context budgeter (fit_messages_to_budget).

Small self-hosted models (--max-model-len 16384 on the L4) reject over-long
prompts with HTTP 400, which surfaced to users as "The request was malformed".
The budgeter trims oldest history first and never drops the trailing message
(the live question / tool-results block).
"""

from __future__ import annotations

from app.llm.types import LLMChatMessage
from app.services.orchestrator import _estimate_tokens, fit_messages_to_budget


def _msg(role: str, chars: int) -> LLMChatMessage:
    return LLMChatMessage(role=role, content="x" * chars)


def test_under_budget_is_untouched():
    msgs = [_msg("user", 400), _msg("assistant", 400), _msg("user", 400)]
    fitted, dropped = fit_messages_to_budget(
        msgs, fixed_tokens=100, budget_tokens=10_000
    )
    assert dropped == 0
    assert [m.content for m in fitted] == [m.content for m in msgs]


def test_drops_oldest_first_and_keeps_trailing_message():
    # 5 messages x 1000 tokens (4000 chars) each; fixed 1000; budget 3500
    # -> must drop from the FRONT until it fits, never the trailing message.
    msgs = [
        _msg("user", 4000),
        _msg("assistant", 4000),
        _msg("user", 4000),
        _msg("assistant", 4000),
        _msg("user", 4000),
    ]
    fitted, dropped = fit_messages_to_budget(
        msgs, fixed_tokens=1000, budget_tokens=3500
    )
    assert dropped == 3
    assert len(fitted) == 2
    # trailing message survives verbatim (it fits: 1000 fixed + 2000 msgs <= 3500)
    assert fitted[-1].content == msgs[-1].content
    assert fitted[0].content == msgs[3].content


def test_single_oversized_message_is_truncated_with_marker():
    msgs = [_msg("user", 200_000)]  # ~50k tokens on its own
    fitted, dropped = fit_messages_to_budget(
        msgs, fixed_tokens=2000, budget_tokens=10_000
    )
    assert dropped == 0
    assert len(fitted) == 1
    assert fitted[0].content.endswith("[TRUNCATED to fit the model's context window]")
    # allowed chars = (budget - fixed) * 4 = 32_000 (+ marker)
    assert len(fitted[0].content) < 33_000
    assert _estimate_tokens(fitted[0].content) + 2000 <= 10_100  # small marker slack


def test_zero_budget_disables_trimming():
    msgs = [_msg("user", 1_000_000)]
    fitted, dropped = fit_messages_to_budget(msgs, fixed_tokens=0, budget_tokens=0)
    assert dropped == 0
    assert fitted[0].content == msgs[0].content


def test_role_preserved_on_truncation():
    msgs = [_msg("assistant", 100_000), _msg("user", 100_000)]
    fitted, _ = fit_messages_to_budget(msgs, fixed_tokens=0, budget_tokens=5_000)
    assert fitted[-1].role == "user"
