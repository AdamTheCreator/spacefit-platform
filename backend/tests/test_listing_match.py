"""Unit tests for the client-fit matching service pure helpers.

The two cleanly testable pieces of ``app.services.listing_match`` are pure +
deterministic, so they run in <1s without a live DB or LLM:

  * ``build_buybox_text`` — flattens a ``Company``'s buy-box (criteria JSON +
    structured columns) into the scoring prompt; asserts the key fields land.
  * ``parse_score_array`` — tolerates ```json fences / prose around the JSON
    and degrades garbage to ``[]``.

Following the established convention (``test_void_analysis.py`` /
``test_ai_config.py``) these use ``SimpleNamespace`` stand-ins rather than the
ORM model, so no DB/LLM wiring is needed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.core.config import settings
from app.llm.types import LLMResponse
from app.services import listing_match as listing_match_module
from app.services.listing_match import (
    build_buybox_text,
    format_listings_for_prompt,
    match_listings_for_client,
    parse_score_array,
)
from app.services.user_llm import ResolvedLLM


def _company(**kwargs) -> SimpleNamespace:
    """A minimal ``Company`` stand-in with sensible defaults."""
    base = {
        "name": None,
        "sector": None,
        "subsector": None,
        "sf_min": None,
        "sf_max": None,
        "target_markets": None,
        "is_expanding": None,
        "criteria": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


# --- build_buybox_text -----------------------------------------------------


class TestBuildBuyboxText:
    def test_includes_key_fields_from_criteria_and_columns(self) -> None:
        company = _company(
            name="Acme Capital",
            sector="Retail",
            subsector="QSR",
            sf_min=2000,
            sf_max=8000,
            target_markets=["NY", "NJ"],
            is_expanding=True,
            criteria={
                "asset_types": ["retail", "mixed-use"],
                "budget_min": 1_000_000,
                "budget_max": 5_000_000,
                "cap_rate_max": 6.5,
                "geographies": ["Northeast", "Mid-Atlantic"],
                "free_form": "Prefers grocery-anchored centers.",
            },
        )

        text = build_buybox_text(company)

        # Client + sector
        assert "Acme Capital" in text
        assert "Retail" in text
        assert "QSR" in text
        # Asset types (list flattened)
        assert "retail" in text
        assert "mixed-use" in text
        # Budget rendered as money range
        assert "$1,000,000" in text
        assert "$5,000,000" in text
        # Cap rate, size range, geographies, target markets, expanding, notes
        assert "6.5%" in text
        assert "2,000" in text
        assert "8,000" in text
        assert "Northeast" in text
        assert "NY" in text
        assert "yes" in text.lower()
        assert "grocery-anchored" in text

    def test_handles_string_asset_types_and_geographies(self) -> None:
        company = _company(
            name="Solo LLC",
            criteria={"asset_types": "office", "geographies": "Texas"},
        )
        text = build_buybox_text(company)
        assert "office" in text
        assert "Texas" in text

    def test_not_expanding_renders_no(self) -> None:
        company = _company(name="X", is_expanding=False)
        text = build_buybox_text(company)
        assert "Actively expanding: no" in text

    def test_empty_company_returns_placeholder(self) -> None:
        text = build_buybox_text(_company())
        assert "No explicit buy-box" in text

    def test_only_emits_present_fields(self) -> None:
        # No budget set -> the budget line must not appear.
        company = _company(name="Lean Co", sector="Industrial")
        text = build_buybox_text(company)
        assert "Budget" not in text
        assert "cap rate" not in text.lower()


# --- format_listings_for_prompt --------------------------------------------


class TestFormatListingsForPrompt:
    def test_leads_each_line_with_id_and_key_facts(self) -> None:
        listings = [
            SimpleNamespace(
                id="abc-1",
                address="100 Main St",
                city="Austin",
                state="TX",
                zip_code="78701",
                asset_type="retail",
                size_sf=5400,
                units=None,
                price=2_500_000,
                cap_rate=6.0,
                year_built=1998,
                description="Corner pad with drive-thru.",
            )
        ]
        block = format_listings_for_prompt(listings)
        assert block.startswith("[abc-1]")
        assert "Austin" in block
        assert "type=retail" in block
        assert "5,400 SF" in block
        assert "$2,500,000" in block
        assert "cap=6.0%" in block

    def test_caps_at_max_listings(self) -> None:
        listings = [
            SimpleNamespace(
                id=f"id-{i}",
                address=None,
                city=None,
                state=None,
                zip_code=None,
                asset_type="office",
                size_sf=None,
                units=None,
                price=None,
                cap_rate=None,
                year_built=None,
                description=None,
            )
            for i in range(80)
        ]
        block = format_listings_for_prompt(listings)
        # Only the first 50 should be rendered (one per line).
        assert len(block.splitlines()) == 50


# --- parse_score_array -----------------------------------------------------


class TestParseScoreArray:
    def test_parses_plain_json_array(self) -> None:
        raw = (
            '[{"listing_id": "a", "fit_score": 88, '
            '"rationale": "good fit", "flags": ["minor"]}]'
        )
        out = parse_score_array(raw)
        assert out == [
            {
                "listing_id": "a",
                "fit_score": 88,
                "rationale": "good fit",
                "flags": ["minor"],
            }
        ]

    def test_tolerates_json_code_fence(self) -> None:
        raw = (
            "Here you go:\n```json\n"
            '[{"listing_id": "x", "fit_score": 50, "rationale": "ok", '
            '"flags": []}]\n```\nThanks!'
        )
        out = parse_score_array(raw)
        assert len(out) == 1
        assert out[0]["listing_id"] == "x"
        assert out[0]["flags"] == []

    def test_tolerates_bare_fence(self) -> None:
        raw = '```\n[{"listing_id": "y", "fit_score": 10}]\n```'
        out = parse_score_array(raw)
        assert out[0]["listing_id"] == "y"
        # Missing rationale/flags default cleanly.
        assert out[0]["rationale"] == ""
        assert out[0]["flags"] == []

    def test_slices_array_out_of_prose(self) -> None:
        raw = 'Sure! [{"listing_id": "z", "fit_score": 73}] done.'
        out = parse_score_array(raw)
        assert out[0]["listing_id"] == "z"
        assert out[0]["fit_score"] == 73

    def test_clamps_score_to_0_100(self) -> None:
        raw = (
            '[{"listing_id": "hi", "fit_score": 250}, '
            '{"listing_id": "lo", "fit_score": -40}]'
        )
        out = parse_score_array(raw)
        assert out[0]["fit_score"] == 100
        assert out[1]["fit_score"] == 0

    def test_coerces_non_int_score_to_zero(self) -> None:
        raw = '[{"listing_id": "q", "fit_score": "high"}]'
        out = parse_score_array(raw)
        assert out[0]["fit_score"] == 0

    def test_skips_items_without_listing_id(self) -> None:
        raw = '[{"fit_score": 90}, {"listing_id": "keep", "fit_score": 5}]'
        out = parse_score_array(raw)
        assert len(out) == 1
        assert out[0]["listing_id"] == "keep"

    def test_non_list_payload_returns_empty(self) -> None:
        assert parse_score_array('{"listing_id": "a", "fit_score": 1}') == []

    def test_garbage_returns_empty(self) -> None:
        assert parse_score_array("not json at all") == []

    def test_empty_string_returns_empty(self) -> None:
        assert parse_score_array("") == []
        assert parse_score_array("   ") == []

    def test_non_list_flags_coerced_to_list(self) -> None:
        raw = '[{"listing_id": "a", "fit_score": 1, "flags": "over budget"}]'
        out = parse_score_array(raw)
        assert out[0]["flags"] == ["over budget"]


# --- match_listings_for_client (outgoing model under baseten) -------------


class _FakeClient:
    def __init__(self, content: str = "[]") -> None:
        self._content = content
        self.calls: list[Any] = []

    async def chat(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        return LLMResponse(content=self._content, tool_calls=[], stop_reason="end_turn")

    async def aclose(self) -> None:  # pragma: no cover
        pass


def _resolved(client: Any, *, model: str, provider: str, is_byok: bool) -> ResolvedLLM:
    return ResolvedLLM(
        client=client, model=model, provider=provider, is_byok=is_byok
    )


def _listing() -> SimpleNamespace:
    return SimpleNamespace(
        id="lid-1",
        address="1 Main St",
        city="Austin",
        state="TX",
        zip_code="78701",
        asset_type="retail",
        size_sf=4000,
        units=None,
        price=2_000_000,
        cap_rate=6.0,
        year_built=2000,
        description=None,
    )


class TestMatchListingsForClientOutgoingModel:
    async def test_uses_resolved_baseten_model(self) -> None:
        fake = _FakeClient(content="[]")
        resolved = _resolved(
            fake, model="spacegoose-advisor-v3", provider="baseten", is_byok=False
        )
        company = _company(name="Acme", criteria={"asset_types": ["retail"]})

        out = await match_listings_for_client(company, [_listing()], resolved)

        assert out == []
        assert len(fake.calls) == 1
        request = fake.calls[0]
        assert request.model == "spacegoose-advisor-v3"
        assert "haiku" not in request.model.lower()
        assert "claude" not in request.model.lower()

    async def test_falls_back_to_baseten_default_when_no_resolved_llm(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "llm_provider", "baseten")
        monkeypatch.setattr(settings, "baseten_model", "spacegoose-advisor-v3")

        fake = _FakeClient(content="[]")
        monkeypatch.setattr(listing_match_module, "get_llm_client", lambda: fake)

        company = _company(name="Acme")
        await match_listings_for_client(company, [_listing()], None)

        assert len(fake.calls) == 1
        assert fake.calls[0].model == "spacegoose-advisor-v3"

    async def test_empty_listings_skips_llm_call(self) -> None:
        fake = _FakeClient()
        resolved = _resolved(
            fake, model="spacegoose-advisor-v3", provider="baseten", is_byok=False
        )
        out = await match_listings_for_client(_company(name="Empty"), [], resolved)
        assert out == []
        assert fake.calls == []
