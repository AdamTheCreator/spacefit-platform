# Fine-tuning data curation (Phase 2)

Turns the drive of raw broker documents into an SFT dataset for the advisory
fine-tune — **without hand-labelling**. A strong model (Claude) reads each doc,
classifies it, keeps only the strong void analyses / investment memos,
reconstructs the training *input*, preserves the human *output*, and redacts all
PII. You skim a report + samples; the model does the labelling.

See `MIGRATION.md` §4.7 (data strategy, Gap 2) and the decisions D13 (strategy) /
D19 (this pipeline) / PII = redact-all.

## The flow

```
raw docs (PDF/Word/CSV)  ──►  extract text  ──►  Claude curation  ──►  train.jsonl
  (Google Drive / local)        (per file)       (classify, gate,        heldout.jsonl
                                                   build pair, redact)    report.md
```

Each kept document becomes one chat-format SFT record:
`{"messages": [{system: advisory persona}, {user: reconstructed input}, {assistant: human analysis}]}`
— the same advisory system prompt used by the eval, so training/eval/serving stay consistent.

## Run it

Offline structural self-check (no API, no docs):

```bash
cd backend
python -m finetune.curate --selftest
```

Real curation pass over a directory of docs:

```bash
cd backend
CURATE_API_KEY=sk-ant-...  python -m finetune.curate \
  --input-dir /path/to/docs \
  --out-dir finetune/dataset \
  --max-docs 10            # start small to validate, then drop the cap
```

Outputs `finetune/dataset/{train.jsonl, heldout.jsonl, report.md}`. **Read
`report.md`** (kept vs dropped, reject reasons, quality mix, and sample pairs)
before trusting the set. The dataset dir is git-ignored — it's derived + may
contain (redacted) client material.

## Getting the docs here

The corpus is being ported to **Google Drive**. Two paths:
1. **Pull via the Drive connector** (preferred): once the folder is shared, the
   files are downloaded into a local dir, then `--input-dir` points at it.
2. **Run locally**: the script is just Python + an Anthropic key — it can run
   wherever the files already sit (keeps sensitive docs on your machine).

We validate on ~10 docs first (confirm the pairs come out clean), then run the
whole drive.

## Notes / knobs

- **Curation model** (`--model`, default `claude-sonnet-4-6`): strong enough for
  classify/extract/redact; the human output is preserved, not generated, so we
  don't need the most expensive model. One-time cost is a few cents per doc.
- **`had_source_data`** in the report tells us, per doc, whether real underlying
  data was present — that's the Strategy-1 vs Strategy-2 split (answers the
  open question automatically).
- **Held-out** (`--heldout-frac`, default 0.15) is stratified by type, never
  enters training, and seeds new advisory eval cases (Gap 3).
- Supported: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.tsv`. Legacy `.doc` →
  convert to `.docx` first. Requires `pypdf` + `python-docx`.
- **Redaction is mandatory** and built into the curation prompt (owner decision).
  Still spot-check the report's `pii_redacted` lists to confirm coverage before
  training on real client material.
