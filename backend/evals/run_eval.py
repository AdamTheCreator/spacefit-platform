"""CLI entry point for the migration eval harness.

Run the routing + tool-call suites against the model named by the EVAL_* env
vars and write a timestamped scorecard (JSON + Markdown) to ``evals/results/``.

Examples
--------
Score the current platform default (the Anthropic baseline)::

    cd backend
    EVAL_PROVIDER=anthropic EVAL_MODEL=claude-haiku-4-5 EVAL_API_KEY=sk-ant-... \\
        python -m evals.run_eval --label baseline-haiku

Score a candidate open model on a Baseten (OpenAI-compatible) endpoint::

    EVAL_PROVIDER=openai_compatible EVAL_MODEL=Qwen/Qwen2.5-7B-Instruct \\
        EVAL_API_KEY=$BASETEN_API_KEY EVAL_BASE_URL=https://model-xxxx.api.baseten.co/environments/production/sync/v1 \\
        python -m evals.run_eval --label qwen25-7b-baseten
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from evals.grade import (
    CaseResult,
    load_routing_cases,
    load_tool_cases,
    summarize,
)
from evals.harness import build_resolved_llm_from_env, run_routing_cases, run_tool_cases

_HERE = Path(__file__).resolve().parent
_CASES = _HERE / "cases"
_RESULTS = _HERE / "results"


def _render_markdown(label: str, model_desc: str, results: list[CaseResult], summary: dict) -> str:
    lines = [
        f"# Eval scorecard — {label}",
        "",
        f"- Model under test: `{model_desc}`",
        f"- Run at (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- **Overall: {summary['passed']}/{summary['total']} "
        f"({summary['pass_rate'] * 100:.1f}%)**",
        "",
        "| Kind | Passed | Total | Rate |",
        "| --- | --- | --- | --- |",
    ]
    for kind, k in sorted(summary["by_kind"].items()):
        lines.append(f"| {kind} | {k['passed']} | {k['total']} | {k['pass_rate'] * 100:.1f}% |")
    lines += ["", "## Failures", ""]
    failures = [r for r in results if not r.passed]
    if not failures:
        lines.append("_None._")
    else:
        for r in failures:
            lines.append(f"- `{r.id}` ({r.kind}): {r.detail}")
    lines.append("")
    return "\n".join(lines)


async def _main_async(label: str) -> int:
    resolved = build_resolved_llm_from_env()
    model_desc = f"{resolved.provider}:{resolved.model}"

    routing_cases = load_routing_cases(_CASES / "routing.jsonl")
    tool_cases = load_tool_cases(_CASES / "tool_calls.jsonl")

    print(f"Evaluating {model_desc} — {len(routing_cases)} routing + {len(tool_cases)} tool cases\n")

    results: list[CaseResult] = []
    results += await run_routing_cases(routing_cases, resolved)
    results += await run_tool_cases(tool_cases, resolved)

    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        print(f"  [{mark}] {r.id:28s} {r.detail}")

    summary = summarize(results)
    print(
        f"\nOverall: {summary['passed']}/{summary['total']} "
        f"({summary['pass_rate'] * 100:.1f}%) — tool-call bar is 90%."
    )

    _RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = label.replace("/", "-")
    payload = {
        "label": label,
        "model": model_desc,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "results": [r.__dict__ for r in results],
    }
    (_RESULTS / f"{stamp}_{safe_label}.json").write_text(json.dumps(payload, indent=2))
    (_RESULTS / f"{stamp}_{safe_label}.md").write_text(
        _render_markdown(label, model_desc, results, summary)
    )
    print(f"\nScorecard written to evals/results/{stamp}_{safe_label}.{{json,md}}")

    # Non-zero exit if the tool-call bar (90%) isn't met, so this can gate CI later.
    tool_rate = summary["by_kind"].get("tool_call", {}).get("pass_rate", 0.0)
    return 0 if tool_rate >= 0.90 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the model-migration eval suite.")
    parser.add_argument(
        "--label",
        default=os.environ.get("EVAL_MODEL", "model"),
        help="A short name for this run, used in the scorecard filename.",
    )
    args = parser.parse_args()
    return asyncio.run(_main_async(args.label))


if __name__ == "__main__":
    raise SystemExit(main())
