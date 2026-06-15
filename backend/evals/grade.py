"""Grading + dataset loading for the migration eval harness.

Pure standard library on purpose: this module carries the load-bearing
correctness logic (did the model route correctly? call the right tool with
valid args?), and keeping it dependency-free means it can be verified offline
with a bare ``python evals/grade.py`` and unit-tested in CI without installing
the whole backend.

Two graded capabilities, both load-bearing for the migration:

1. Routing accuracy  — does ``plan_workflow`` pick the right specialist(s)?
2. Tool-call accuracy — does a specialist call the expected tool with
   schema-valid, non-placeholder arguments? (The 90% success bar.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Vague references the prompts explicitly tell the model NOT to pass as a
# concrete address/location. A required arg whose value is one of these is a
# failure even though the field is technically populated — it means the model
# fabricated a placeholder instead of using a real value or asking for one.
PLACEHOLDER_TERMS: frozenset[str] = frozenset(
    {
        "the property",
        "this property",
        "the location",
        "this location",
        "the address",
        "this address",
        "the site",
        "this site",
        "here",
        "it",
        "n/a",
        "unknown",
        "tbd",
        "",
    }
)


# --- Dataset records -------------------------------------------------------


@dataclass(frozen=True)
class RoutingCase:
    """One ``plan_workflow`` routing case."""

    id: str
    message: str
    expected: list[str]
    acceptable: list[list[str]] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class ToolCase:
    """One specialist tool-selection case.

    ``expected_tool=None`` is an *abstain* case: the correct behavior is to ask
    the user for specifics rather than call a tool with a fabricated argument.
    """

    id: str
    specialist: str
    message: str
    expected_tool: str | None
    required_args: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class CaseResult:
    """The graded outcome of running one case against a model."""

    id: str
    passed: bool
    detail: str
    kind: str  # "routing" | "tool_call"


def load_jsonl(path: str | Path) -> list[dict]:
    """Load a JSONL file into a list of dicts, skipping blank lines."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e
    return rows


def load_routing_cases(path: str | Path) -> list[RoutingCase]:
    return [
        RoutingCase(
            id=r["id"],
            message=r["message"],
            expected=r["expected"],
            acceptable=r.get("acceptable", []),
            context=r.get("context", {}),
            note=r.get("note", ""),
        )
        for r in load_jsonl(path)
    ]


def load_tool_cases(path: str | Path) -> list[ToolCase]:
    return [
        ToolCase(
            id=r["id"],
            specialist=r["specialist"],
            message=r["message"],
            expected_tool=r.get("expected_tool"),
            required_args=r.get("required_args", []),
            context=r.get("context", {}),
            note=r.get("note", ""),
        )
        for r in load_jsonl(path)
    ]


# --- Grading ---------------------------------------------------------------


def grade_routing(predicted: list[str], case: RoutingCase) -> tuple[bool, str]:
    """Pass if the predicted specialist set equals the expected set or any
    listed acceptable alternative.

    Routing is legitimately fuzzy (``scout`` vs ``scout, analyst`` can both be
    defensible), so we grade on *set* membership and let each case enumerate
    acceptable alternatives, rather than demanding an exact ordered match.
    """
    pset = set(predicted)
    for candidate in [case.expected, *case.acceptable]:
        if pset == set(candidate):
            return True, "match"
    return False, f"got {predicted}, expected {case.expected}"


def looks_like_placeholder(value: object) -> bool:
    """True if a string arg is a vague placeholder rather than a real value."""
    if not isinstance(value, str):
        return False
    return value.strip().lower() in PLACEHOLDER_TERMS


def grade_tool_call(
    tool_calls: list[dict], case: ToolCase
) -> tuple[bool, str]:
    """Grade a specialist's tool selection for one case.

    ``tool_calls`` is the normalized list the orchestrator returns:
    ``[{"name": str, "input": dict}, ...]``.
    """
    names = [tc.get("name") for tc in tool_calls]

    # Abstain case: success means the model did NOT reach for a tool.
    if case.expected_tool is None:
        if not tool_calls:
            return True, "correctly abstained (no tool call)"
        return False, f"expected abstain, but called {names}"

    if case.expected_tool not in names:
        return False, f"expected {case.expected_tool!r}, called {names or 'nothing'}"

    call = next(tc for tc in tool_calls if tc.get("name") == case.expected_tool)
    args = call.get("input") or {}

    missing = [a for a in case.required_args if not str(args.get(a, "")).strip()]
    if missing:
        return False, f"called {case.expected_tool!r} but missing/empty args {missing}"

    placeholders = [a for a in case.required_args if looks_like_placeholder(args.get(a))]
    if placeholders:
        return False, f"called {case.expected_tool!r} with placeholder args {placeholders}"

    return True, f"ok ({case.expected_tool})"


def summarize(results: list[CaseResult]) -> dict:
    """Aggregate pass rates overall and per kind."""
    out: dict = {"total": len(results), "passed": 0, "by_kind": {}}
    for r in results:
        out["passed"] += int(r.passed)
        k = out["by_kind"].setdefault(r.kind, {"total": 0, "passed": 0})
        k["total"] += 1
        k["passed"] += int(r.passed)
    out["pass_rate"] = (out["passed"] / out["total"]) if out["total"] else 0.0
    for k in out["by_kind"].values():
        k["pass_rate"] = (k["passed"] / k["total"]) if k["total"] else 0.0
    return out


# --- Offline self-check ----------------------------------------------------
#
# Runnable with a bare interpreter (no backend deps, no network):
#     python evals/grade.py
# Proves the grading logic before we ever spend a token on a live model.


def _selftest() -> None:
    rc = RoutingCase(id="r", message="m", expected=["scout"], acceptable=[["scout", "analyst"]])
    assert grade_routing(["scout"], rc)[0] is True
    assert grade_routing(["analyst", "scout"], rc)[0] is True  # set, order-insensitive
    assert grade_routing(["matchmaker"], rc)[0] is False

    tc = ToolCase(
        id="t",
        specialist="scout",
        message="m",
        expected_tool="business_search",
        required_args=["location"],
    )
    assert grade_tool_call([{"name": "business_search", "input": {"location": "Tucson, AZ"}}], tc)[0] is True
    assert grade_tool_call([{"name": "demographics_analysis", "input": {}}], tc)[0] is False  # wrong tool
    assert grade_tool_call([], tc)[0] is False  # no call
    assert grade_tool_call([{"name": "business_search", "input": {}}], tc)[0] is False  # missing arg
    assert grade_tool_call(
        [{"name": "business_search", "input": {"location": "the property"}}], tc
    )[0] is False  # placeholder

    abstain = ToolCase(id="a", specialist="scout", message="m", expected_tool=None)
    assert grade_tool_call([], abstain)[0] is True
    assert grade_tool_call([{"name": "business_search", "input": {"location": "x"}}], abstain)[0] is False

    summary = summarize(
        [
            CaseResult(id="1", passed=True, detail="", kind="routing"),
            CaseResult(id="2", passed=False, detail="", kind="tool_call"),
            CaseResult(id="3", passed=True, detail="", kind="tool_call"),
        ]
    )
    assert summary["total"] == 3 and summary["passed"] == 2
    assert abs(summary["pass_rate"] - 2 / 3) < 1e-9
    assert summary["by_kind"]["tool_call"]["passed"] == 1

    print("grade.py self-check: OK (all assertions passed)")


if __name__ == "__main__":
    _selftest()
