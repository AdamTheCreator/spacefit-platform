"""Format-diversity augmentation for the v2 advisory LoRA (the v1 lesson).

v1 (r=64 Together defaults, single input surface) learned the task but overfit
the *shape* of the training inputs: in-format it answers and stops cleanly;
off-format (the sectioned ## Property / ## Data eval + product shape) it
degenerates into repetition loops. Fix: teach format invariance by ADDING a
sectioned rendering of half the training pairs — same facts, same gold output,
different input surface. Content is preserved (curate.py's reconstruct-the-input
philosophy); the reformatter may not invent facts.

    export ANTHROPIC_API_KEY=...
    python -m finetune.diversify_formats            # writes train_v2.jsonl
    python -m finetune.diversify_formats --check    # dry-run: show one rendering

Then: python -m finetune.together_submit submit --train finetune/dataset/memos/train_v2.jsonl
(lora_r 16 / lora_alpha 32 are now the submit defaults.)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

TRAIN = Path("finetune/dataset/memos/train.jsonl")
OUT = Path("finetune/dataset/memos/train_v2.jsonl")
REFORMAT_MODEL = "claude-haiku-4-5"  # mechanical, content-preserving reformat

REFORMAT_SYSTEM = (
    "You restructure a commercial-real-estate broker's request into a sectioned "
    "format. Preserve every fact from the original verbatim where possible. Do NOT "
    "add facts, numbers, names, or geography that are not in the original. If the "
    "original carries no explicit client profile, write the minimal client line the "
    "request itself implies (e.g. 'Yield-focused investor evaluating de-risked "
    "development deals') — nothing more specific than the original supports.\n\n"
    "Output exactly this shape and nothing else:\n"
    "## Property\n<one-to-three sentence property/site description>\n\n"
    "## Data available\n<the facts, figures, tenants, demographics from the original>\n\n"
    "## Client (from the broker's book of business)\n<client profile>\n\n"
    "## The broker's question\n<the actual ask, one sentence>"
)


def _reformat(text: str, key: str, tries: int = 3) -> str:
    payload = {
        "model": REFORMAT_MODEL,
        "max_tokens": 1200,
        "system": REFORMAT_SYSTEM,
        "messages": [{"role": "user", "content": text}],
    }
    last: Exception | None = None
    for i in range(tries):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json=payload,
                timeout=120,
            )
            if r.status_code == 200:
                d = r.json()
                return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="reformat one pair and print it, write nothing")
    args = ap.parse_args()

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("set ANTHROPIC_API_KEY", file=sys.stderr)
        return 2

    recs = [json.loads(l) for l in TRAIN.open()]
    print(f"loaded {len(recs)} train pairs")

    if args.check:
        u = next(m["content"] for m in recs[0]["messages"] if m["role"] == "user")
        print("=== original ===\n", u[:400], "\n=== sectioned ===\n", _reformat(u, key))
        return 0

    out: list[dict] = list(recs)  # originals always kept, order preserved
    added = 0
    for i, rec in enumerate(recs):
        if i % 2 != 0:  # deterministic half — no RNG, reproducible
            continue
        msgs = rec["messages"]
        u_idx = next(j for j, m in enumerate(msgs) if m["role"] == "user")
        original = msgs[u_idx]["content"]
        if original.lstrip().startswith("## Property"):
            continue  # already sectioned
        sectioned = _reformat(original, key)
        if not sectioned.lstrip().startswith("## Property"):
            print(f"  [skip {i}] reformat did not return the sectioned shape")
            continue
        variant = json.loads(json.dumps(rec))  # deep copy
        variant["messages"][u_idx]["content"] = sectioned
        out.append(variant)
        added += 1
        print(f"  [{i}] +sectioned variant ({len(sectioned)} chars)")

    OUT.write_text("".join(json.dumps(r) + "\n" for r in out))
    print(f"\nwrote {OUT} — {len(recs)} originals + {added} sectioned variants = {len(out)} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
