# Inference Migration — Status Brief

*A portable snapshot for discussion. The full engineering log + decisions live in
`MIGRATION.md`; this is the shareable summary as of **2026-06-15**.*

---

## What we're doing & why

Space Goose is an AI commercial-real-estate workbench; the product *is* the chat — a
specialist-routed agent that analyzes properties, pulls data, and advises a broker on
whether a property fits their clients. Today every model call hits the **Anthropic API**.
We're moving the chat to **self-hosted, fine-tuned open models on Baseten** (an L4 GPU),
for control, domain specialization, and learning. BYOK (users' own frontier keys) stays;
Baseten becomes the platform default. Vision document parsing stays on Anthropic (out of
scope).

The bet that makes it worthwhile: open 7B models are competent at *gathering data* out of
the box, but the **advisory voice** — reading a property and judging fit-to-client — is
where they fall short, and that's exactly what fine-tuning on our own human-written **void
analyses + investment memos** should fix. Our own documents are the moat.

## Where we are

**Phase 0 (baseline + evals) ✅ and Phase 1 (pick + validate a model) ✅. Phase 2
(fine-tuning data prep) is next.**

We built a provider-agnostic **eval harness** that measures two things on equal footing
across any model (Anthropic, Baseten, etc.):
1. **Tool-calling** — does it gather the right data (pick the right tool, valid args)? 90% bar.
2. **Advisory quality** — graded by a strong "LLM-as-judge": does it reason about
   property→client fit and give a clear go/no-go? *This is the product.*

We picked **`Qwen/Qwen2.5-7B-Instruct`** (Apache-2.0, fits a 24 GB L4, strong tool-caller),
deployed it on Baseten via a config-only Truss (vLLM, scale-to-zero), and benchmarked it
against the current model (Claude Haiku 4.5).

## The key result (head-to-head)

| | Haiku 4.5 (today) | Qwen2.5-7B (our L4) | Read |
|---|---|---|---|
| Tool-calling | 85.7% | **92.9%** | Qwen **wins**, clears the bar |
| Advisory quality | **4.35/5**, 3/4 client-ready | 2.80/5, **0/4** client-ready | Qwen **regresses hard** |
| Warm time-to-first-token | — | **~0.9 s** | good chat UX |

**Verdict:** don't ship base Qwen as-is. Tool-calling and latency are solved; the advisory
gap is real — and is the whole reason to fine-tune. We now have a clean "before" number
(2.80/5) to prove the fine-tune's payoff against.

Two lessons worth keeping:
- **Controlling the serving stack matters.** The *same* Qwen threw random errors on Hugging
  Face's shared router but ran clean on our dedicated vLLM (with a pinned tool-call parser).
  That's the point of self-hosting.
- **Measuring the right thing matters.** Tool-calling alone (89%) looked shippable; the
  advisory dimension caught a regression that metric completely hid.

## Decisions locked

- Scope = the text chat path (tool-calling + advisory). Vision parsing stays on Anthropic.
- Hardware = a single **L4 (24 GB)**, **scale-to-zero** by default + an always-on toggle for demos.
- Gate = **non-regression vs the current model on BOTH dimensions** (not an arbitrary 90%).
- Candidate = **Qwen2.5-7B-Instruct**; fine-tune it (likely LoRA) on the void/memo corpus.

## Open questions worth discussing

1. **Fine-tuning data:** how to turn ~N OneDrive void analyses + investment memos into clean
   training pairs (input → ideal output)? What's the input side — a property + data prompt?
2. **LoRA vs full fine-tune** — LoRA is cheap, adapter-swappable, L4-friendly; full only if
   quality demands. Likely LoRA.
3. **Training venue + cost** — fine-tune on Baseten vs. a cheaper GPU rental / managed
   service? (A cost comparison is owed before committing.)
4. **One model or two** — one Qwen serving every persona, plus a tiny utility model for the
   cheap calls (routing, titles)? Decide on cost + eval.
5. **Quantization** — test FP8 on the L4 (frees VRAM/throughput) and re-eval to confirm
   quality holds; bf16 for now.
6. **Cold starts** — scale-to-zero means slow first wake (weights download). Add weight
   caching; measure the tradeoff vs the always-on toggle.
7. **Eval depth** — the suite is small (synthetic + a few scenarios). Fold in real dogfood
   prompts and grow it before trusting fine-tune deltas.

## Next step

Phase 2: get the OneDrive corpus (void analyses + investment memos), inspect it, and build a
versioned fine-tuning dataset aimed squarely at the advisory gap.
