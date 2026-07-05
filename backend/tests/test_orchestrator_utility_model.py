"""Regression tests for orchestrator utility calls that must send the resolved
model on the outgoing request.

Covers:
  * ``synthesize_specialist_outputs`` (final synthesis pass at the end of a
    multi-specialist turn)
  * ``generate_conversation_title`` (auto-title on the first user turn)

These call sites were audited alongside ``fact_extractor`` /
``listing_match`` / ``outreach_ai`` / ``void_analysis`` in the platform-default
Baseten mission. They already selected the model from ``resolved_llm``; these
tests lock down that behavior so a future refactor can't regress it.
"""

from __future__ import annotations

from typing import Any

from app.llm.types import LLMResponse
from app.services.orchestrator import (
    generate_conversation_title,
    synthesize_specialist_outputs,
)
from app.services.user_llm import ResolvedLLM


class _FakeClient:
    def __init__(self, content: str = "OK") -> None:
        self._content = content
        self.calls: list[Any] = []

    async def chat(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        return LLMResponse(content=self._content, tool_calls=[], stop_reason="end_turn")

    async def aclose(self) -> None:  # pragma: no cover
        pass


def _resolved_baseten(client: Any) -> ResolvedLLM:
    return ResolvedLLM(
        client=client,
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=False,
    )


async def test_synthesize_specialist_outputs_uses_resolved_baseten_model() -> None:
    fake = _FakeClient(content="Synthesis body here.")
    resolved = _resolved_baseten(fake)

    result = await synthesize_specialist_outputs(
        user_message="Analyze 337 W Mariposa Rd for a coffee tenant.",
        specialist_outputs=[
            {"specialist": "scout", "content": "Nearby demographics look good."},
            {
                "specialist": "analyst",
                "content": "Trade-area supports specialty coffee.",
            },
        ],
        conversation_history=[
            {
                "role": "user",
                "content": "Analyze 337 W Mariposa Rd for a coffee tenant.",
            },
        ],
        resolved_llm=resolved,
    )

    assert result["content"] == "Synthesis body here."
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request.model == "spacegoose-advisor-v3"
    assert "haiku" not in request.model.lower()
    assert "claude" not in request.model.lower()


async def test_generate_conversation_title_uses_resolved_baseten_model() -> None:
    fake = _FakeClient(content="Mariposa Coffee Analysis")
    resolved = _resolved_baseten(fake)

    title = await generate_conversation_title(
        first_message="Analyze 337 W Mariposa Rd for a coffee tenant.",
        resolved_llm=resolved,
    )

    assert title == "Mariposa Coffee Analysis"
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request.model == "spacegoose-advisor-v3"
    assert "haiku" not in request.model.lower()
    assert "claude" not in request.model.lower()
