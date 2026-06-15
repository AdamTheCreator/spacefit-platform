"""CLI for the advisory-quality (LLM-as-judge) eval.

Runs each scenario through the *candidate* model (the advisor under test), then
has a strong *judge* model score the answer against the rubric in judge.py.

Candidate is chosen by the EVAL_* env vars (same as run_eval.py). The judge is a
separate, strong model (default Claude Sonnet 4.6) so it isn't grading itself:

    cd backend
    # Baseline advisor = Haiku, judged by Sonnet
    EVAL_PROVIDER=anthropic EVAL_MODEL=claude-haiku-4-5 EVAL_API_KEY=sk-ant-... \\
    JUDGE_PROVIDER=anthropic JUDGE_MODEL=claude-sonnet-4-6 JUDGE_API_KEY=sk-ant-... \\
        python -m evals.run_advisory --label baseline-haiku

The judge defaults to reusing EVAL_API_KEY if JUDGE_API_KEY is unset.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from evals.judge import (
    ADVISORY_SYSTEM,
    AdvisoryResult,
    JUDGE_SYSTEM,
    RUBRIC,
    build_candidate_user_prompt,
    build_judge_user_prompt,
    load_advisory_cases,
    parse_judge_json,
    score_from_judge,
)

_HERE = Path(__file__).resolve().parent
_CASES = _HERE / "cases" / "advisory.jsonl"
_RESULTS = _HERE / "results"


def _client(provider_env: str, key_env: str, base_env: str, fallback_key: str = ""):
    from app.llm.client import get_or_create_client

    provider = os.environ.get(provider_env, "anthropic")
    api_key = os.environ.get(key_env, "") or fallback_key
    base_url = os.environ.get(base_env, "")
    return get_or_create_client(provider, api_key, base_url)


async def _run() -> int:
    from app.llm.types import LLMChatMessage, LLMChatRequest

    cand_client = _client("EVAL_PROVIDER", "EVAL_API_KEY", "EVAL_BASE_URL")
    cand_model = os.environ.get("EVAL_MODEL")
    if not cand_model:
        raise SystemExit("EVAL_MODEL is required.")

    judge_client = _client(
        "JUDGE_PROVIDER", "JUDGE_API_KEY", "JUDGE_BASE_URL",
        fallback_key=os.environ.get("EVAL_API_KEY", ""),
    )
    judge_model = os.environ.get("JUDGE_MODEL", "claude-sonnet-4-6")

    cases = load_advisory_cases(_CASES)
    print(
        f"Advisory eval: candidate={os.environ.get('EVAL_PROVIDER','anthropic')}:{cand_model} "
        f"judge={os.environ.get('JUDGE_PROVIDER','anthropic')}:{judge_model} "
        f"— {len(cases)} scenarios\n"
    )

    results: list[AdvisoryResult] = []
    for case in cases:
        try:
            cand_resp = await cand_client.chat(
                LLMChatRequest(
                    system=ADVISORY_SYSTEM,
                    messages=[LLMChatMessage(role="user", content=build_candidate_user_prompt(case))],
                    model=cand_model,
                    max_tokens=900,
                )
            )
            answer = cand_resp.content
            judge_resp = await judge_client.chat(
                LLMChatRequest(
                    system=JUDGE_SYSTEM,
                    messages=[LLMChatMessage(role="user", content=build_judge_user_prompt(case, answer))],
                    model=judge_model,
                    max_tokens=700,
                )
            )
            payload = parse_judge_json(judge_resp.content)
            if payload is None:
                results.append(AdvisoryResult(case.id, {}, False, 0.0, "judge returned unparseable JSON", answer, error="judge_parse"))
                continue
            scores, avg, passed, summary = score_from_judge(payload)
            results.append(AdvisoryResult(case.id, scores, passed, avg, summary, answer))
        except Exception as e:
            results.append(AdvisoryResult(case.id, {}, False, 0.0, "", "", error=f"{type(e).__name__}: {e}"))

    # Report
    print(f"{'case':18s} {'avg/5':>6s} {'pass':>5s}  summary")
    graded = [r for r in results if r.error is None]
    for r in results:
        if r.error:
            print(f"  {r.id:18s} {'--':>6s} {'ERR':>5s}  {r.error[:80]}")
        else:
            print(f"  {r.id:18s} {r.avg_score:6.2f} {('Y' if r.overall_pass else 'N'):>5s}  {r.summary[:80]}")

    overall_avg = (sum(r.avg_score for r in graded) / len(graded)) if graded else 0.0
    pass_n = sum(1 for r in graded if r.overall_pass)
    print(
        f"\nAdvisory baseline: mean rubric {overall_avg:.2f}/5 across {len(graded)} graded; "
        f"{pass_n}/{len(graded)} 'send-to-client' pass."
    )
    # Per-criterion means
    print("Per-criterion mean:")
    for name in RUBRIC:
        vals = [r.scores[name] for r in graded if name in r.scores]
        if vals:
            print(f"  {name:24s} {sum(vals)/len(vals):.2f}/5")

    _RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = args_label.replace("/", "-")
    (_RESULTS / f"{stamp}_advisory_{label}.json").write_text(
        json.dumps({"candidate": cand_model, "judge": judge_model,
                    "overall_avg": overall_avg, "results": [r.__dict__ for r in results]}, indent=2)
    )
    print(f"\nScorecard -> evals/results/{stamp}_advisory_{label}.json")
    return 0


def main() -> int:
    global args_label
    parser = argparse.ArgumentParser(description="Advisory-quality LLM-as-judge eval.")
    parser.add_argument("--label", default=os.environ.get("EVAL_MODEL", "model"))
    args_label = parser.parse_args().label
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
