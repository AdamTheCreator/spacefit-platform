"""Phase 3a — build the human-gold memo dataset (section-sliced).

We have ~6 distinct investment-memo deals (heavily versioned; we take one clean
version each). Six examples is too thin for a LoRA, so we *section-slice* each
rich memo into multiple input->output pairs — the full thesis plus one pair per
substantive section (recommendation, trade-area, comps, pro forma, risks…).
That turns ~6 memos into ~40 pairs, all in the broker's own voice (no synthetic
content), which is what a style/disposition LoRA needs.

Held-out is split at the DEAL level (a whole deal the fine-tune never sees), not
the pair level — otherwise the model would have seen the deal and the eval would
leak. See MIGRATION.md §4.9 (D20) for the rationale.

Run:
    cd backend
    CURATE_API_KEY=sk-ant-...  python -m finetune.build_memo_dataset \
        --input-dir /tmp/memos --out-dir finetune/dataset/memos

Offline self-check (no API):
    python -m finetune.build_memo_dataset --selftest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
from pathlib import Path

from finetune.curate import advisory_system, extract_text, parse_curation_json

MAX_MEMO_CHARS = 80_000  # memos run long; the slicer needs to see the whole thing

SLICE_SYSTEM = """You are building fine-tuning examples from ONE real commercial-real-estate investment memo written by an expert broker. The goal is to teach a model the broker's advisory VOICE and JUDGMENT: read a property + data, reason about fit and returns, and give a clear, calibrated go/no-go.

From this single memo, produce MULTIPLE training pairs (input -> ideal output):
1. ONE "full" pair: input = a realistic request to a CRE advisor (the property, the key data/economics the memo had, the objective/client profile); output = the memo's complete thesis + recommendation, lightly cleaned, leading with the go/no-go.
2. SEVERAL "section" pairs — one per substantive section the memo ACTUALLY contains (e.g. recommendation/thesis, trade-area & demographics, market comparables, pro forma / returns, tenant strategy, risks). input = the property + the relevant data + a targeted question a broker would ask ("walk me through the comps", "what's the trade area and who's the customer?", "what are the returns and key risks?", "your recommendation?"); output = that section's content.

Rules:
- Use ONLY facts in the memo; invent nothing. Aim for 4-8 pairs total depending on how much the memo contains.
- DO NOT rewrite, improve, or restyle the analysis — preserve the broker's judgment and phrasing. Light cleanup only (strip letterhead, page numbers, image captions).
- REDACT all PII -> neutral placeholders: client/sponsor/firm identity, individual names, exact street addresses, and party-specific deal identifiers. KEEP city/market names and public tenant brand names (useful, not confidential).
- Output ONLY a JSON object, no prose, no code fences:
{
  "doc_type": "investment_memo" | "other",
  "usable": true | false,
  "reject_reason": "string (empty if usable)",
  "deal": "short neutral deal name (e.g. 'Chandler 2-pad QSR ground-up development')",
  "pairs": [ {"section": "...", "input": "...", "output": "..."} ]
}"""


def build_records(pairs: list[dict], deal: str) -> list[dict]:
    sys = advisory_system()
    out = []
    for p in pairs:
        inp, o = (p.get("input") or "").strip(), (p.get("output") or "").strip()
        if not inp or not o:
            continue
        out.append({
            "deal": deal,
            "section": p.get("section", ""),
            "record": {"messages": [
                {"role": "system", "content": sys},
                {"role": "user", "content": inp},
                {"role": "assistant", "content": o},
            ]},
        })
    return out


def split_by_deal(items: list[dict], n_heldout_deals: int, seed: int) -> tuple[list, list]:
    """Hold out whole DEALS (never seen in training), not individual pairs."""
    deals = sorted({it["deal"] for it in items})
    rng = random.Random(seed)
    rng.shuffle(deals)
    heldout_deals = set(deals[:max(0, min(n_heldout_deals, len(deals) - 1))])
    train = [it for it in items if it["deal"] not in heldout_deals]
    heldout = [it for it in items if it["deal"] in heldout_deals]
    return train, heldout, sorted(heldout_deals)


async def build(input_dir: str, out_dir: str, model: str, api_key: str,
                n_heldout_deals: int, seed: int) -> None:
    from app.llm.client import get_or_create_client
    from app.llm.types import LLMChatMessage, LLMChatRequest

    client = get_or_create_client("anthropic", api_key, "")
    files = [p for p in sorted(Path(input_dir).rglob("*")) if p.suffix.lower() in {".txt", ".pdf", ".docx", ".md"}]
    print(f"Found {len(files)} memo files in {input_dir}\n")

    all_items: list[dict] = []
    per_deal: dict[str, int] = {}
    rejects: list[tuple] = []
    for i, path in enumerate(files, 1):
        text = extract_text(path)
        if len(text.strip()) < 400:
            rejects.append((path.name, "empty/short"))
            print(f"  [{i}/{len(files)}] SKIP {path.name}")
            continue
        clipped = text[:MAX_MEMO_CHARS]
        try:
            resp = await client.chat(LLMChatRequest(
                system=SLICE_SYSTEM,
                messages=[LLMChatMessage(role="user", content=f"MEMO:\n\n{clipped}")],
                model=model, max_tokens=8000,
            ))
            data = parse_curation_json(resp.content)
        except Exception as e:
            rejects.append((path.name, f"error {type(e).__name__}"))
            print(f"  [{i}/{len(files)}] ERR  {path.name}: {e}")
            continue
        if not data or not data.get("usable") or not data.get("pairs"):
            reason = (data or {}).get("reject_reason", "unparseable/unusable")
            rejects.append((path.name, reason))
            print(f"  [{i}/{len(files)}] DROP {path.name} ({reason})")
            continue
        deal = data.get("deal") or path.stem
        recs = build_records(data["pairs"], deal)
        all_items.extend(recs)
        per_deal[deal] = per_deal.get(deal, 0) + len(recs)
        print(f"  [{i}/{len(files)}] KEEP {path.name} -> deal '{deal}', {len(recs)} pairs")

    await client.aclose()

    train, heldout, heldout_deals = split_by_deal(all_items, n_heldout_deals, seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "train.jsonl").write_text("\n".join(json.dumps(it["record"]) for it in train))
    (out / "heldout.jsonl").write_text("\n".join(json.dumps(it["record"]) for it in heldout))

    lines = [
        "# Memo dataset (human-gold, section-sliced)", "",
        f"- Deals kept: **{len(per_deal)}**  |  total pairs: **{len(all_items)}**",
        f"- Train pairs: {len(train)}  |  held-out pairs: {len(heldout)} (deals held out: {heldout_deals})",
        f"- Pairs per deal: {per_deal}",
        f"- Rejected files: {rejects}", "",
        "## Sample pairs (skim before training)", "",
    ]
    for it in all_items[:4]:
        m = it["record"]["messages"]
        lines.append(f"### {it['deal']} — section: {it['section']}")
        lines.append(f"**input:** {m[1]['content'][:300]}…")
        lines.append(f"**output:** {m[2]['content'][:300]}…\n")
    (out / "report.md").write_text("\n".join(lines))
    print("\n" + "\n".join(lines))
    print(f"\nWrote {out}/train.jsonl ({len(train)}), heldout.jsonl ({len(heldout)}), report.md")


def _selftest() -> None:
    recs = build_records(
        [{"section": "rec", "input": "in1", "output": "out1"},
         {"section": "comps", "input": "in2", "output": "out2"},
         {"section": "empty", "input": "", "output": "x"}],  # dropped
        deal="Deal A")
    assert len(recs) == 2
    assert recs[0]["record"]["messages"][1]["content"] == "in1"

    items = [{"deal": f"D{i}", "section": "s", "record": {}} for i in range(6) for _ in range(5)]
    tr, ho, hd = split_by_deal(items, n_heldout_deals=1, seed=3)
    assert len(hd) == 1
    assert all(it["deal"] not in hd for it in tr)
    assert all(it["deal"] in hd for it in ho)
    assert len(tr) + len(ho) == len(items)
    print("build_memo_dataset.py self-check: OK")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the section-sliced human-gold memo dataset.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--input-dir")
    ap.add_argument("--out-dir", default="finetune/dataset/memos")
    ap.add_argument("--model", default=os.environ.get("CURATE_MODEL", "claude-sonnet-4-6"))
    ap.add_argument("--heldout-deals", type=int, default=1)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if not args.input_dir:
        ap.error("--input-dir required (or --selftest)")
    key = os.environ.get("CURATE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        ap.error("set CURATE_API_KEY")
    asyncio.run(build(args.input_dir, args.out_dir, args.model, key, args.heldout_deals, args.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
