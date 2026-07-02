"""Standalone advisory eval for the v1 LoRA — no app.* imports (fresh container).

Replicates run_advisory.py's exact request construction (ADVISORY_SYSTEM,
build_candidate_user_prompt, max_tokens=900, temperature omitted; judge =
claude-sonnet-4-6, max_tokens=700) so scores are directly comparable to the
baseline scorecards in evals/results/. Three configs on the same Baseten L4:

    base-reanchor  Qwen/Qwen2.5-7B-Instruct   (re-anchors the judge vs the 2.80 baseline)
    v1-raw         spacegoose-advisor          (honest comparable — same treatment as baselines)
    v1-fp07        spacegoose-advisor + frequency_penalty=0.7  (the serving mitigation)

    BASETEN_API_KEY=... ANTHROPIC_API_KEY=... python -m evals._run_advisory_v1
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from evals.judge import (
    ADVISORY_SYSTEM,
    JUDGE_SYSTEM,
    RUBRIC,
    build_candidate_user_prompt,
    build_judge_user_prompt,
    load_advisory_cases,
    parse_judge_json,
    score_from_judge,
)

BASETEN_URL = "https://model-3m50kp6w.api.baseten.co/environments/production/sync/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
JUDGE_MODEL = "claude-sonnet-4-6"

CONFIGS = [
    ("base-reanchor", "Qwen/Qwen2.5-7B-Instruct", {}),
    ("v1-raw", "spacegoose-advisor", {}),
    ("v1-fp07", "spacegoose-advisor", {"frequency_penalty": 0.7}),
]


def _post(url: str, headers: dict, payload: dict, tries: int = 3) -> dict:
    last = None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=180)
            if r.status_code == 200:
                return r.json()
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


def candidate(model: str, case, extra: dict, bt_key: str) -> tuple[str, str]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ADVISORY_SYSTEM},
            {"role": "user", "content": build_candidate_user_prompt(case)},
        ],
        "max_tokens": 900,
        **extra,
    }
    d = _post(BASETEN_URL, {"Authorization": f"Bearer {bt_key}"}, payload)
    ch = d["choices"][0]
    return ch["message"]["content"], ch.get("finish_reason", "?")


def judge(case, answer: str, ant_key: str) -> str:
    # 1400, not the baseline's 700: Sonnet 4.6 writes long rubric notes and 700
    # truncates the JSON mid-object on long candidate answers (judge_parse errors).
    # max_tokens is a stop condition, not a sampling param, so raising it cannot
    # change any judgment that already fit — it only rescues truncated ones.
    payload = {
        "model": JUDGE_MODEL,
        "max_tokens": 1400,
        "system": JUDGE_SYSTEM,
        "messages": [{"role": "user", "content": build_judge_user_prompt(case, answer)}],
    }
    d = _post(
        ANTHROPIC_URL,
        {"x-api-key": ant_key, "anthropic-version": "2023-06-01"},
        payload,
    )
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")


def main() -> int:
    bt_key = os.environ.get("BASETEN_API_KEY", "")
    ant_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not bt_key or not ant_key:
        print("set BASETEN_API_KEY and ANTHROPIC_API_KEY", file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent
    cases = load_advisory_cases(here / "cases" / "advisory.jsonl")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (here / "results").mkdir(exist_ok=True)

    summary_rows = []
    for label, model, extra in CONFIGS:
        print(f"\n===== {label} ({model}{' ' + str(extra) if extra else ''}) =====")
        results = []
        for case in cases:
            try:
                answer, finish = candidate(model, case, extra, bt_key)
                payload = parse_judge_json(judge(case, answer, ant_key))
                if payload is None:
                    results.append({"id": case.id, "scores": {}, "overall_pass": False,
                                    "avg_score": 0.0, "summary": "judge returned unparseable JSON",
                                    "answer": answer, "finish_reason": finish, "error": "judge_parse"})
                    print(f"  {case.id:18s}     --   ERR  judge_parse")
                    continue
                scores, avg, passed, summ = score_from_judge(payload)
                results.append({"id": case.id, "scores": scores, "overall_pass": passed,
                                "avg_score": avg, "summary": summ, "answer": answer,
                                "finish_reason": finish, "error": None})
                print(f"  {case.id:18s} {avg:6.2f} {('Y' if passed else 'N'):>5s} [{finish}] {summ[:70]}")
            except Exception as e:  # noqa: BLE001
                results.append({"id": case.id, "scores": {}, "overall_pass": False,
                                "avg_score": 0.0, "summary": "", "answer": "",
                                "finish_reason": "?", "error": f"{type(e).__name__}: {e}"})
                print(f"  {case.id:18s}     --   ERR  {e}")

        graded = [r for r in results if r["error"] is None]
        overall = (sum(r["avg_score"] for r in graded) / len(graded)) if graded else 0.0
        pass_n = sum(1 for r in graded if r["overall_pass"])
        print(f"  -> mean {overall:.2f}/5, {pass_n}/{len(graded)} send-to-client pass")
        for name in RUBRIC:
            vals = [r["scores"][name] for r in graded if name in r["scores"]]
            if vals:
                print(f"     {name:24s} {sum(vals)/len(vals):.2f}/5")

        out = here / "results" / f"{stamp}_advisory_{label}.json"
        out.write_text(json.dumps({"candidate": model, "judge": JUDGE_MODEL, "config": extra,
                                   "overall_avg": overall, "results": results}, indent=2))
        summary_rows.append((label, overall, pass_n, len(graded)))

    print("\n===== SUMMARY (judge = claude-sonnet-4-6; baselines: base Qwen 2.80, Haiku 4.35) =====")
    for label, overall, pass_n, n in summary_rows:
        print(f"  {label:16s} {overall:.2f}/5   pass {pass_n}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
