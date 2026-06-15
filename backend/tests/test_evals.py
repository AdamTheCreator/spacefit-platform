"""Offline tests for the migration eval grader (Phase 0).

These do NOT hit a model — they exercise the pure grading + dataset-loading
logic in ``evals.grade`` so the eval instrument itself is trustworthy and the
seed datasets stay well-formed. Safe for CI (no network, no API key).
"""

from __future__ import annotations

from pathlib import Path

from evals.grade import (
    RoutingCase,
    ToolCase,
    grade_routing,
    grade_tool_call,
    load_routing_cases,
    load_tool_cases,
    looks_like_placeholder,
    summarize,
    CaseResult,
)

_CASES = Path(__file__).resolve().parent.parent / "evals" / "cases"


def test_routing_set_match_is_order_insensitive():
    case = RoutingCase(id="r", message="m", expected=["scout", "analyst"])
    assert grade_routing(["analyst", "scout"], case)[0] is True
    assert grade_routing(["scout"], case)[0] is False


def test_routing_accepts_listed_alternatives():
    case = RoutingCase(id="r", message="m", expected=["scout"], acceptable=[["scout", "analyst"]])
    assert grade_routing(["scout", "analyst"], case)[0] is True


def test_tool_call_happy_path():
    case = ToolCase(
        id="t", specialist="scout", message="m",
        expected_tool="business_search", required_args=["location"],
    )
    ok, _ = grade_tool_call([{"name": "business_search", "input": {"location": "Tucson, AZ"}}], case)
    assert ok is True


def test_tool_call_rejects_wrong_tool_missing_and_placeholder_args():
    case = ToolCase(
        id="t", specialist="scout", message="m",
        expected_tool="demographics_analysis", required_args=["address"],
    )
    assert grade_tool_call([{"name": "business_search", "input": {"location": "x"}}], case)[0] is False
    assert grade_tool_call([{"name": "demographics_analysis", "input": {}}], case)[0] is False
    assert grade_tool_call(
        [{"name": "demographics_analysis", "input": {"address": "the property"}}], case
    )[0] is False


def test_abstain_case_passes_only_when_no_tool_called():
    case = ToolCase(id="a", specialist="scout", message="m", expected_tool=None)
    assert grade_tool_call([], case)[0] is True
    assert grade_tool_call([{"name": "business_search", "input": {"location": "x"}}], case)[0] is False


def test_placeholder_detection():
    assert looks_like_placeholder("the property") is True
    assert looks_like_placeholder("THE PROPERTY ") is True
    assert looks_like_placeholder("123 Main St, Fairfield, CT") is False
    assert looks_like_placeholder(42) is False  # non-string args are not placeholders


def test_summarize_counts_by_kind():
    summary = summarize(
        [
            CaseResult(id="1", passed=True, detail="", kind="routing"),
            CaseResult(id="2", passed=True, detail="", kind="tool_call"),
            CaseResult(id="3", passed=False, detail="", kind="tool_call"),
        ]
    )
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["by_kind"]["tool_call"]["total"] == 2
    assert summary["by_kind"]["tool_call"]["passed"] == 1


def test_seed_datasets_parse_and_reference_real_tools():
    from app.services.tools import SPACEGOOSE_TOOLS
    from app.agents.specialists.registry import SPECIALIST_REGISTRY

    tool_names = {t["name"] for t in SPACEGOOSE_TOOLS}

    routing = load_routing_cases(_CASES / "routing.jsonl")
    tools = load_tool_cases(_CASES / "tool_calls.jsonl")
    assert routing and tools  # non-empty seed set

    for c in routing:
        for plan in [c.expected, *c.acceptable]:
            for name in plan:
                assert name in SPECIALIST_REGISTRY, f"{c.id}: unknown specialist {name!r}"

    for c in tools:
        assert c.specialist in SPECIALIST_REGISTRY, f"{c.id}: unknown specialist {c.specialist!r}"
        if c.expected_tool is not None:
            assert c.expected_tool in tool_names, f"{c.id}: unknown tool {c.expected_tool!r}"
            # The expected tool must actually be allowed for that specialist,
            # or the case is unsatisfiable.
            allowed = set(SPECIALIST_REGISTRY[c.specialist].allowed_tools)
            assert c.expected_tool in allowed, (
                f"{c.id}: {c.expected_tool!r} not in {c.specialist}'s allowed_tools"
            )
