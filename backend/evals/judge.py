"""Advisory-quality eval: judging the *advisor*, not the tool-picker.

The tool-call eval (grade.py) measures whether the model gathers the right data.
This module measures the capability that actually delivers value: given a property
+ data + a specific client's book of business, does the model produce a sound,
grounded, conversational "pursue or pass — and is it worth your time?" recommendation?

That is a quality judgment, not a pass/fail match, so we grade it with
**LLM-as-judge**: a strong model scores each candidate answer against a rubric.
This file holds the rubric, the prompt construction, and lenient JSON parsing —
all pure stdlib so it's inspectable and testable offline. The actual LLM calls
(candidate + judge) live in run_advisory.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

# The persona under test. Phrased to elicit exactly the advisory behavior the
# product needs — fit-to-client reasoning + an explicit go/no-go — so the eval
# rewards that, not generic property description.
ADVISORY_SYSTEM = (
    "You are a commercial real estate advisor helping a broker decide whether a "
    "property is worth pursuing for a specific client in their book of business. "
    "Given the property, the available data, and the client's profile, give a clear, "
    "conversational recommendation: does this property fit the client, how would the "
    "client's customers/clientele benefit, and is it worth the broker's time to pursue? "
    "Be direct about go vs. no-go. Ground every claim in the data provided; if key data "
    "is missing, say so and state what you'd need. Write like an experienced broker "
    "advising a colleague — professional but conversational, not robotic, no invented facts."
)

# Each criterion is scored 1–5 by the judge (5 = excellent). These are the five
# things that separate a useful recommendation from a plausible-sounding one.
RUBRIC: dict[str, str] = {
    "property_understanding": "Reads the supplied property + data correctly (size, vacancy, tenants, demographics, traffic, financials).",
    "client_fit_reasoning": "Explicitly connects the property to THIS client's box / clientele — why it does or doesn't fit their customers.",
    "recommendation_clarity": "Gives a clear pursue-vs-pass call and answers 'is it worth the broker's time', with reasons.",
    "grounded": "Uses only the supplied data; no fabricated tenants/numbers; flags missing data instead of guessing.",
    "tone": "Professional but conversational broker-advisor voice — helpful, direct, not robotic or salesy.",
}

JUDGE_SYSTEM = (
    "You are a strict senior managing broker grading a junior advisor's written property "
    "recommendation. Score each rubric criterion from 1 to 5 (5 = genuinely excellent; "
    "reserve it). Be critical and specific. A confident recommendation that misreads the "
    "data or ignores the client's box should score low on the relevant criteria. "
    "Return ONLY a JSON object, no prose, no code fences."
)


@dataclass(frozen=True)
class AdvisoryCase:
    id: str
    property: str
    data: str
    client_book: str
    question: str
    note: str = ""


@dataclass(frozen=True)
class AdvisoryResult:
    id: str
    scores: dict[str, int]
    overall_pass: bool
    avg_score: float
    summary: str
    answer: str = ""
    error: str | None = None


def load_advisory_cases(path) -> list[AdvisoryCase]:
    cases: list[AdvisoryCase] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cases.append(
                AdvisoryCase(
                    id=r["id"],
                    property=r["property"],
                    data=r["data"],
                    client_book=r["client_book"],
                    question=r["question"],
                    note=r.get("note", ""),
                )
            )
    return cases


def build_candidate_user_prompt(case: AdvisoryCase) -> str:
    return (
        f"## Property\n{case.property}\n\n"
        f"## Data available\n{case.data}\n\n"
        f"## Client (from the broker's book of business)\n{case.client_book}\n\n"
        f"## The broker's question\n{case.question}"
    )


def build_judge_user_prompt(case: AdvisoryCase, answer: str) -> str:
    rubric_lines = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    keys = ", ".join(f'"{k}"' for k in RUBRIC)
    return (
        "Grade the advisor's recommendation below.\n\n"
        f"### Scenario given to the advisor\n"
        f"PROPERTY: {case.property}\nDATA: {case.data}\n"
        f"CLIENT: {case.client_book}\nQUESTION: {case.question}\n\n"
        f"### The advisor's answer\n{answer}\n\n"
        f"### Rubric (score each 1-5)\n{rubric_lines}\n\n"
        "### Output format (JSON only)\n"
        "{\n"
        f'  "criteria": {{ {keys} : each an object {{"score": int 1-5, "note": str}} }},\n'
        '  "overall_pass": boolean (would a competent broker be comfortable sending this to the client?),\n'
        '  "summary": string (one sentence)\n'
        "}"
    )


def parse_judge_json(text: str) -> dict | None:
    """Lenient parse: strip code fences / prose, extract the JSON object."""
    if not text:
        return None
    t = text.strip()
    if "```" in t:
        # take the content of the first fenced block
        parts = t.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                t = p
                break
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(t[start : end + 1])
    except json.JSONDecodeError:
        return None


def score_from_judge(payload: dict) -> tuple[dict[str, int], float, bool, str]:
    """Extract per-criterion scores, average, pass flag, summary from judge JSON."""
    crit = payload.get("criteria", {}) or {}
    scores: dict[str, int] = {}
    for name in RUBRIC:
        entry = crit.get(name)
        if isinstance(entry, dict) and isinstance(entry.get("score"), (int, float)):
            scores[name] = int(entry["score"])
    avg = (sum(scores.values()) / len(scores)) if scores else 0.0
    return scores, avg, bool(payload.get("overall_pass", False)), str(payload.get("summary", ""))


def _selftest() -> None:
    sample = '```json\n{"criteria": {"property_understanding": {"score": 4, "note": "x"}}, "overall_pass": true, "summary": "ok"}\n```'
    p = parse_judge_json(sample)
    assert p and p["overall_pass"] is True
    scores, avg, passed, summ = score_from_judge(p)
    assert scores["property_understanding"] == 4 and passed and summ == "ok"
    assert parse_judge_json("not json at all") is None
    print("judge.py self-check: OK")


if __name__ == "__main__":
    _selftest()
