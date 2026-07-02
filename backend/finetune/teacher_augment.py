"""Phase 3b: voice-steered teacher augmentation (MIGRATION.md §4.9 / §4.11).

Two LoRA rounds proved the human-gold corpus (29–44 pairs) teaches the memo
VOICE but not the input→disposition MAPPING — v2 flips GO/PASS on identical
facts depending on phrasing. This pipeline manufactures the mapping signal:
~100–200 pairs where a strong teacher writes grounded GO/PASS/uncertain
recommendations over DIVERSE, CONTROLLED inputs, few-shot-anchored on the real
human memos so the house voice stays the anchor.

Key separations (they are the design):
  * The SCENARIO generator is told the intended disposition and constructs
    facts that imply it. The TEACHER never sees the label — it derives the
    verdict from the facts alone. A disagreement means the scenario was
    ambiguous; the gate drops it (unless intended=uncertain).
  * Teacher output is gated: disposition stated, no degeneration, and a
    fabrication scan (material claims in the output absent from the input).
  * The pair's system prompt is evals.judge.ADVISORY_SYSTEM verbatim —
    train/serve parity, same as the human-gold pairs.

Caveat, documented on purpose: the teacher (claude-sonnet-4-6) is also the
advisory-eval judge. Scores of a model trained on this data carry a
same-model-taste bias; the Haiku baseline shares lineage too, so the yardstick
is not neutral in an absolute sense — treat deltas, not absolutes, as the signal.

    export ANTHROPIC_API_KEY=...
    python -m finetune.teacher_augment gen --n 132          # scenarios + teacher + gate
    python -m finetune.teacher_augment gen --n 6 --dry      # 6 pairs, print, write nothing
    python -m finetune.teacher_augment build                # merge with human gold -> train_v3.jsonl
    python -m finetune.teacher_augment stats                # disposition/format mix of v3

Real void/Sites-USA docs can be added later: `gen --void-dir <dir>` composes
scenario inputs from local files (extract_text from curate.py) instead of
synthesizing facts; everything downstream is identical.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.judge import ADVISORY_SYSTEM  # noqa: E402  (train/serve parity)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
TEACHER_MODEL = "claude-sonnet-4-6"
GATE_MODEL = "claude-haiku-4-5"

HUMAN_TRAIN = Path("finetune/dataset/memos/train.jsonl")
OUT_DIR = Path("finetune/dataset/teacher")
PAIRS = OUT_DIR / "teacher_pairs.jsonl"
REJECTS = OUT_DIR / "teacher_rejects.jsonl"
TRAIN_V3 = Path("finetune/dataset/memos/train_v3.jsonl")

# ---------------------------------------------------------------- recipe grid
FORMATS = ["terse", "bullet_brief", "sectioned", "conversational"]
ASSETS = [
    "multi-tenant retail strip with one vacancy",
    "single-tenant NNN pad (existing lease in place)",
    "ground-up QSR drive-thru build-to-suit pad",
    "grocery-anchored neighborhood center in-line suite",
    "medical office condo near a hospital campus",
    "small-bay flex/industrial multi-tenant building",
    "junior-anchor box (15-30k SF) backfill opportunity",
    "mixed-use ground-floor retail under new apartments",
]
CLIENTS = [
    "an expanding regional QSR franchisee (needs drive-thru, 2-3k SF pads)",
    "a yield-focused NNN investor (national credit only, 10+ yr term, 6%+ cap)",
    "a value-add syndicator (below-market rents, fixable vacancy, 3-5 yr hold)",
    "a 1031-exchange buyer on a 45-day clock (stabilized, passive, credit tenant)",
    "a regional fitness operator (12-20k SF boxes, dense rooftops, cheap rent)",
    "a discount grocer (18-30k SF, value-oriented trade areas, field-of-play states)",
    "a drive-thru coffee chain (endcaps/pads 1.5-3k SF, morning commuter traffic)",
    "an urgent-care operator (2-4k SF, high visibility, insured-population demos)",
]
DISPOSITIONS = ["GO", "PASS", "GO", "PASS", "UNCERTAIN"]  # 40/40/20 weighting
WRINKLES = [
    "clean case — most criteria clearly point one way",
    "one real negative that must be weighed and explicitly addressed",
    "headline metric looks great but a second-order detail cuts against it",
    "size or rent is at the edge of the client's box",
    "strong demographics but for the WRONG customer profile for this client",
    "a data conflict between two supplied figures the advisor should flag",
]

SCENARIO_SYSTEM = (
    "You construct SYNTHETIC commercial-real-estate scenario inputs used to train "
    "an advisory model. You will be given: an asset type, a client profile, an "
    "intended disposition (GO, PASS, or UNCERTAIN), a wrinkle, and an input format. "
    "Invent a realistic property with concrete, internally-consistent facts "
    "(location city/state, sizes, rents, occupancy, tenants, traffic counts, "
    "demographics, pricing/cap rates where relevant) such that a competent broker "
    "reading ONLY your facts would reach the intended disposition:\n"
    "- GO: the facts genuinely support pursuing for THIS client.\n"
    "- PASS: at least two material criteria clearly fail for THIS client.\n"
    "- UNCERTAIN: plausible surface fit but 2-3 decision-critical data points are "
    "absent (do NOT state them), so the right answer is 'here is what I would need'.\n"
    "CRITICAL: the wrinkle adds texture but must NOT flip the verdict. After "
    "honestly weighing the wrinkle, a competent broker still lands on the intended "
    "disposition. For GO the negative must be real but clearly survivable (no "
    "recorded restrictions, use clauses, or structural blockers that a prudent "
    "advisor would treat as disqualifying). For PASS the failing criteria must "
    "dominate any positives. For UNCERTAIN, the withheld data must make a firm "
    "GO or PASS genuinely impossible.\n"
    "Rules: invented brands must be plausible-but-generic (no real client names); "
    "real cities are fine but do NOT use Stamford CT. Do not state the disposition "
    "or any conclusion in the input — facts only, plus the broker's question. "
    "Format the input as instructed:\n"
    "- terse: 2-4 sentences mashing the facts together, ending with the ask.\n"
    "- bullet_brief: a short intro line, 5-9 fact bullets, then the ask.\n"
    "- sectioned: '## Property', '## Data available', '## Client (from the broker's "
    "book of business)', '## The broker's question'.\n"
    "- conversational: how a broker actually types mid-chat — informal, a little "
    "unordered, the ask embedded.\n"
    "Return ONLY the scenario input text. No preamble, no labels, no commentary."
)

TEACHER_SYSTEM_TMPL = (
    "You write gold-standard training outputs for a commercial-real-estate advisory "
    "model. Given a broker's scenario, write the reply an elite broker-advisor would "
    "send: read the property, connect it to THIS client's box and customers, and "
    "commit to a clear disposition — open with 'GO —', 'PASS —', or, when decision-"
    "critical data is missing, say plainly that you can't call it yet and list "
    "exactly what you'd need. Ground EVERY claim in the scenario's own facts; never "
    "invent numbers, tenants, or geography; quote the input's figures when you use "
    "them. Weigh negatives honestly instead of cheerleading. 150-350 words, "
    "conversational broker register, no bullet-list-only answers, no markdown "
    "headers.\n\nMatch the voice of these two excerpts from the firm's real memos "
    "(style anchor only — their facts are irrelevant here):\n\n"
    "=== VOICE EXCERPT 1 ===\n{ex1}\n\n=== VOICE EXCERPT 2 ===\n{ex2}"
)

GATE_SYSTEM = (
    "You audit a CRE advisory training pair for fabrication. Compare the ANSWER "
    "against the INPUT. Report JSON only:\n"
    '{"material_fabrications": [string, ...], "degenerate": boolean}\n'
    "material_fabrications lists ONLY claims in the answer (numbers, tenants, "
    "places, lease terms, restrictions) that are absent from the input AND not "
    "derivable from it AND would change a broker's read if false. Paraphrases, "
    "softened restatements, derived arithmetic (PSF, caps, percentages computed "
    "from supplied figures), and reasonable characterizations of supplied facts "
    "are NOT fabrications — do not list them, do not list 'checks' that passed. "
    "If everything is supported, return an empty list. degenerate is true only "
    "if the answer repeats sentences/paragraphs or trails off unfinished."
)


def _anthropic(system: str, user: str, model: str, max_tokens: int, key: str,
               tries: int = 3, temperature: float | None = None) -> str:
    payload = {"model": model, "max_tokens": max_tokens, "system": system,
               "messages": [{"role": "user", "content": user}]}
    if temperature is not None:
        payload["temperature"] = temperature
    last: Exception | None = None
    for i in range(tries):
        try:
            r = requests.post(ANTHROPIC_URL, json=payload, timeout=180,
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
            if r.status_code == 200:
                d = r.json()
                return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()
            if r.status_code == 429:
                time.sleep(15 * (i + 1))
                continue
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 * (i + 1))
    raise last  # type: ignore[misc]


def _voice_excerpts() -> list[str]:
    """Longest human-gold outputs = the fullest expressions of the house voice."""
    recs = [json.loads(l) for l in HUMAN_TRAIN.open()]
    outs = sorted((m["content"] for r in recs for m in r["messages"] if m["role"] == "assistant"),
                  key=len, reverse=True)
    return [o[:2400] for o in outs[:8]]


UNCERTAIN_WRINKLE = (
    "every STATED fact is consistent with a plausible fit — the 2-3 WITHHELD "
    "decision-critical data points (e.g. no asking price/rent, no lease term, no "
    "traffic or demo figures) are what make a firm call impossible"
)


def _recipe(i: int) -> dict:
    dispo = DISPOSITIONS[i % len(DISPOSITIONS)]
    return {
        "format": FORMATS[i % len(FORMATS)],
        "asset": ASSETS[i % len(ASSETS)],
        "client": CLIENTS[(i * 3 + 1) % len(CLIENTS)],   # stride so asset/client decorrelate
        "disposition": dispo,
        # disposition-flavored wrinkles sabotage UNCERTAIN scenarios (the
        # generator injects a disqualifier instead of withholding data)
        "wrinkle": UNCERTAIN_WRINKLE if dispo == "UNCERTAIN" else WRINKLES[i % len(WRINKLES)],
    }


def _parse_gate(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _answer_verdict(answer: str) -> str:
    """The teacher is instructed to open 'GO —' / 'PASS —'; anything else
    (can't-call-it phrasing) reads as UNCERTAIN. Regex, not an LLM — the
    opener is a contract, and Haiku extraction added pure noise."""
    head = answer.lstrip().upper()
    if head.startswith("GO"):
        return "GO"
    if head.startswith("PASS"):
        return "PASS"
    return "UNCERTAIN"


def _make_pair(i: int, excerpts: list[str], key: str) -> dict:
    rec = _recipe(i)
    scen_user = (
        f"Asset type: {rec['asset']}\nClient: {rec['client']}\n"
        f"Intended disposition: {rec['disposition']}\nWrinkle: {rec['wrinkle']}\n"
        f"Input format: {rec['format']}\nScenario seed number: {i}"
    )
    scenario = _anthropic(SCENARIO_SYSTEM, scen_user, TEACHER_MODEL, 900, key)
    teacher_system = TEACHER_SYSTEM_TMPL.format(
        ex1=excerpts[i % len(excerpts)], ex2=excerpts[(i + 3) % len(excerpts)])
    answer = _anthropic(teacher_system, scenario, TEACHER_MODEL, 700, key)
    gate_user = f"### INPUT\n{scenario}\n\n### ANSWER\n{answer}"
    gate = _parse_gate(
        _anthropic(GATE_SYSTEM, gate_user, GATE_MODEL, 500, key, temperature=0.0)) or {}

    verdict = _answer_verdict(answer)
    fabs = gate.get("material_fabrications", []) or []
    degenerate = bool(gate.get("degenerate", False))
    # Strict agreement, UNCERTAIN included: an UNCERTAIN scenario where the
    # teacher committed to GO/PASS is ambiguous either way — exactly the
    # mapping noise §4.11 says to keep out of the corpus.
    ok = not degenerate and len(fabs) == 0 and verdict == rec["disposition"]
    return {
        "i": i, "recipe": rec, "gate": {"verdict": verdict, "fabrications": fabs,
                                        "degenerate": degenerate}, "ok": ok,
        "messages": [
            {"role": "system", "content": ADVISORY_SYSTEM},
            {"role": "user", "content": scenario},
            {"role": "assistant", "content": answer},
        ],
    }


def gen(args) -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise SystemExit("set ANTHROPIC_API_KEY")
    excerpts = _voice_excerpts()
    print(f"{len(excerpts)} voice excerpts loaded; generating {args.n} pairs "
          f"({'DRY RUN' if args.dry else 'live'}) …")

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(lambda i: _make_pair(i, excerpts, key), range(args.n)):
            results.append(res)
            tag = "ok " if res["ok"] else "REJ"
            print(f"  [{res['i']:3d}] {tag} {res['recipe']['disposition']:9s} "
                  f"{res['recipe']['format']:14s} gate={res['gate']['verdict'] or '?':9s} "
                  f"fabs={len(res['gate']['fabrications'])}")

    kept = [r for r in results if r["ok"]]
    if args.dry:
        for r in results[:3]:
            print("=" * 88)
            print("--- input ---\n", r["messages"][1]["content"][:700])
            print("--- answer ---\n", r["messages"][2]["content"][:700])
        print(f"\nDRY RUN: {len(kept)}/{len(results)} would pass the gate. Nothing written.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with PAIRS.open("w") as f:
        for r in kept:
            f.write(json.dumps({"messages": r["messages"], "recipe": r["recipe"]}) + "\n")
    with REJECTS.open("w") as f:
        for r in results:
            if not r["ok"]:
                f.write(json.dumps(r) + "\n")
    print(f"\nwrote {PAIRS} ({len(kept)} pairs) + {REJECTS} ({len(results) - len(kept)} rejects)")


def build(args) -> None:
    human = [json.loads(l) for l in HUMAN_TRAIN.open()]
    teacher = [json.loads(l) for l in PAIRS.open()]
    merged = []
    for i, r in enumerate(human):
        merged.append((f"h{i:03d}", {"messages": r["messages"]}))
    for i, r in enumerate(teacher):
        merged.append((f"t{i:03d}", {"messages": r["messages"]}))
    # deterministic interleave (no RNG): sort by md5 of the stable key
    import hashlib
    merged.sort(key=lambda kv: hashlib.md5(kv[0].encode()).hexdigest())
    TRAIN_V3.write_text("".join(json.dumps(r) + "\n" for _, r in merged))
    print(f"wrote {TRAIN_V3}: {len(human)} human-gold + {len(teacher)} teacher = {len(merged)} pairs")


def stats(args) -> None:
    recs = [json.loads(l) for l in TRAIN_V3.open()]
    dispo: dict[str, int] = {}
    for r in recs:
        a = next(m["content"] for m in r["messages"] if m["role"] == "assistant")
        head = a.lstrip()[:60].upper()
        k = "GO" if head.startswith("GO") else "PASS" if head.startswith("PASS") else "OTHER/UNCERTAIN"
        dispo[k] = dispo.get(k, 0) + 1
    print(f"{len(recs)} pairs — disposition of first token: {dispo}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 3b teacher augmentation.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--n", type=int, default=132)
    g.add_argument("--dry", action="store_true")
    g.add_argument("--void-dir", default="", help="(later) compose inputs from local void docs")
    g.set_defaults(func=gen)
    sub.add_parser("build").set_defaults(func=build)
    sub.add_parser("stats").set_defaults(func=stats)
    args = ap.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
