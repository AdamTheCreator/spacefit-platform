"""Unit tests for void-analysis helpers.

`affordability_tier` is pure + deterministic, so we can pin the demographic
"scrubbing" boundaries here without touching an LLM.

Also locks down the mixed client/model fix: a Baseten ``ResolvedLLM`` causes
``analyze_voids_for_property`` to send ``spacegoose-advisor-v3`` as the outgoing
model, and the no-``ResolvedLLM`` fallback under ``LLM_PROVIDER=baseten`` uses
``settings.baseten_model`` instead of the Anthropic default.
"""

from typing import Any

import pytest

from app.core.config import settings
from app.llm.types import LLMResponse
from app.services import void_analysis as void_analysis_module
from app.services.user_llm import ResolvedLLM
from app.services.void_analysis import affordability_tier, analyze_voids_for_property


@pytest.mark.parametrize(
    "income, expected",
    [
        (None, "unknown"),
        (0, "unknown"),
        (-5, "unknown"),
        (35_000, "value"),
        (49_999, "value"),
        (50_000, "moderate"),
        (89_999, "moderate"),
        (90_000, "affluent"),
        (149_999, "affluent"),
        (150_000, "luxury"),
        (250_000, "luxury"),
    ],
)
def test_affordability_tier_boundaries(income, expected):
    assert affordability_tier(income)["key"] == expected


def test_affordability_tier_always_has_label():
    # The label is interpolated into the scrub prompt, so it must be a
    # non-empty string for every tier.
    for income in (None, 30_000, 60_000, 120_000, 200_000):
        tier = affordability_tier(income)
        assert isinstance(tier["label"], str)
        assert tier["label"]


class _FakeClient:
    def __init__(self, content: str = "{}") -> None:
        self._content = content
        self.calls: list[Any] = []

    async def chat(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        return LLMResponse(content=self._content, tool_calls=[], stop_reason="end_turn")

    async def aclose(self) -> None:  # pragma: no cover
        pass


async def test_analyze_voids_uses_resolved_baseten_model() -> None:
    """A Baseten ``ResolvedLLM`` causes the outgoing request to carry the
    resolved model id, not a hardcoded Anthropic default."""
    fake = _FakeClient(
        content='{"categories": [], "summary": {"total_voids": 0, "high_priority": []}}'
    )
    resolved = ResolvedLLM(
        client=fake,  # type: ignore[arg-type]
        model="spacegoose-advisor-v3",
        provider="baseten",
        is_byok=False,
    )

    await analyze_voids_for_property(
        address="123 Main St",
        existing_tenants=[],
        demographics={"population": 25_000, "median_income": 65_000},
        resolved_llm=resolved,
    )

    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request.model == "spacegoose-advisor-v3"
    assert "haiku" not in request.model.lower()
    assert "claude" not in request.model.lower()


async def test_analyze_voids_falls_back_to_baseten_default_when_no_resolved_llm(
    monkeypatch,
) -> None:
    """No ``ResolvedLLM`` + ``LLM_PROVIDER=baseten`` → outgoing model is
    ``settings.baseten_model``."""
    monkeypatch.setattr(settings, "llm_provider", "baseten")
    monkeypatch.setattr(settings, "baseten_model", "spacegoose-advisor-v3")

    fake = _FakeClient(
        content='{"categories": [], "summary": {"total_voids": 0, "high_priority": []}}'
    )
    monkeypatch.setattr(void_analysis_module, "get_llm_client", lambda: fake)

    await analyze_voids_for_property(
        address="123 Main St",
        existing_tenants=[],
        demographics={"population": 25_000, "median_income": 65_000},
        resolved_llm=None,
    )

    assert len(fake.calls) == 1
    assert fake.calls[0].model == "spacegoose-advisor-v3"
