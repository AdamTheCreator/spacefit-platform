# QLoRA learning track — fine-tuning a small model for Space Goose (CRE)

> **Status: learning / experiment.** Nothing in this folder is imported by the
> app or runs in CI. It's an isolated sandbox for learning the QLoRA +
> inference-engineering loop end-to-end, using Space Goose's real data shape as
> the example. Adopting any result is a *config change* in the app (a BYOK
> `base_url`), never a code change.

---

## Is this overkill for the project? (honest answer)

**For shipping to users right now: yes, mostly.** A strong open base model +
your existing RAG (`document_search` / tsvector) + good system prompts already
gets you ~90% of "sounds like a CRE expert," and it stays fresh and keeps the
base model's tool-calling intact. Fine-tuning *injects behavior, not facts* —
so it won't make the model "know more CRE," and done naively it can **degrade
function-calling**, which is the one thing your chat can't lose.

**When it actually pays off:** you have a *repeatable* format / voice /
tool-routing pattern the base keeps getting wrong, **and** a few hundred clean
examples from your own logs, **and** you'll maintain an eval to catch
regressions. That's a real bar — and the point of this track is to teach you to
judge it for real.

**As a way to learn QLoRA + inference engineering: 100% worth it.** The
byproducts are useful even if you never ship the adapter: a clean SFT dataset
built from `tool_call_log` + `chat_messages`, a tool-calling regression eval
harness, and a reproducible managed-endpoint deploy.

So this is set up as a **side track**: learn the mechanics on the bundled
sample, optionally point it at your real logs, and only consider shipping if the
eval says the adapter beats the plain base model on *your* tasks **without**
losing tool-calling.

---

## The pipeline

```
prepare_dataset.py   chat_messages + tool_call_log  ─┐         (or bundled sample)
                                                      ├─►  train.jsonl / eval.jsonl
                                                      │     (OpenAI-style "messages")
train_qlora.py       4-bit NF4 base (frozen)  +  LoRA adapters (bf16, trained)
                                                      │
evaluate.py          held-out eval + TOOL-CALLING REGRESSION SLICES
                                                      │
merge_and_push.py    merge adapter → base, push to the HF Hub
                                                      │
HF Inference Endpoint (managed, OpenAI-compatible /v1)
                                                      │
Space Goose BYOK     provider=openai_compatible, base_url=<endpoint>/v1
```

The base model defaults to **`Qwen/Qwen2.5-7B-Instruct`** — Apache-2.0, ungated,
strong tool use, and it fits in 4-bit on a single 16–24 GB GPU (a free Colab/T4
works for the sample). It's also the same model you defaulted the outreach
generator to, so the tool-call format here matches.

---

## The QLoRA mental model (the part worth understanding)

Full fine-tuning updates all ~7B weights — too much VRAM, and it overwrites the
general skills you want to keep. **QLoRA** sidesteps both:

1. **Quantize the base to 4-bit (NF4)** and **freeze** it. The big weight matrix
   `W` never changes; it just sits in memory cheaply (~5 GB for a 7B).
   `NF4` = a 4-bit datatype shaped for the normal distribution of LLM weights;
   **double quantization** even quantizes the quantization constants to shave a
   bit more.
2. **Train tiny low-rank adapters.** For a layer `W (d×k)`, instead of editing
   `W` you learn `A (d×r)` and `B (r×k)` with **rank `r` ≪ d,k**, and the layer
   computes `W·x + (B·A)·x`. Only `A,B` (kept in bf16) get gradients — often
   **<1%** of params. That's why a 7B trains on one consumer GPU.
3. **Paged optimizer + gradient checkpointing** keep the optimizer state and
   activations from blowing the VRAM budget.

The knobs you'll actually tune (see `config.yaml`):

| Knob | What it does | Sane start |
|---|---|---|
| `lora_r` (rank) | adapter capacity. Higher = more it can learn, more VRAM/overfit risk | 16 |
| `lora_alpha` | scales the adapter's contribution; effective scale ≈ `alpha/r` | 32 (≈2×r) |
| `lora_dropout` | regularization on the adapter | 0.05 |
| `target_modules` | which projections get adapters. All attn+MLP = strongest | q,k,v,o,gate,up,down |
| `learning_rate` | LoRA likes higher LR than full FT | 2e-4 |
| `epochs` | passes over data; small data overfits fast | 1–3 |
| `max_seq_length` | truncation/packing length | 2048 |

> **Form, not facts.** Train this on *how you want it to respond* — your tone,
> your output structure, your tool-routing conventions — not on facts that
> change weekly (those belong in RAG).

---

## Setup

```bash
cd ml/qlora-cre
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # needs a CUDA GPU for train/eval
```

> CPU-only? You can still run `prepare_dataset.py` and read the code, but
> `train_qlora.py` / `evaluate.py` need a GPU (Colab T4 is enough for the sample).

---

## Step 1 — Build the dataset

**From the bundled sample (no DB needed):**

```bash
python prepare_dataset.py --source sample
# → data/train.jsonl, data/eval.jsonl  (copied + validated from sample_data/)
```

**From your real Space Goose logs** (run anywhere that can reach the DB):

```bash
export DATABASE_URL='postgresql://spacegoose:...@host:5432/spacegoose'
python prepare_dataset.py --source db --eval-frac 0.1 --min-turns 2
```

What the DB exporter does (see the docstring for the exact joins):
- Pulls each `chat_sessions` thread, ordered `chat_messages.created_at`, keeping
  `visible` user/assistant turns.
- Joins `tool_call_log` rows (by `session_id` + timestamp) and re-inserts each
  successful call as an assistant `<tool_call>{...}</tool_call>` turn, so the
  model learns **your** tool-routing (`void_analysis`, `document_search`, …).
- Emits OpenAI-style `{"messages": [...]}` JSONL and a random eval split.

Each line looks like:

```json
{"messages": [
  {"role": "system", "content": "You are Space Goose, a CRE analyst. Tools: void_analysis, document_search."},
  {"role": "user", "content": "Any tenant gaps near 900 Harper St, Austin?"},
  {"role": "assistant", "content": "<tool_call>\n{\"name\": \"void_analysis\", \"arguments\": {\"property_address\": \"900 Harper St, Austin TX\", \"use_case\": \"leasing\"}}\n</tool_call>"}
]}
```

The `<tool_call>` convention is Qwen2.5's native tool format — keep it if you
keep the default base; change it to match the template if you swap models.

---

## Step 2 — Train

```bash
python train_qlora.py --config config.yaml
# → outputs/qlora-cre/adapter/   (just the LoRA adapter — a few MB)
```

On the sample this is a couple of minutes on a T4. On a few hundred real
examples, a single 24 GB GPU is ~minutes-to-an-hour and a few dollars.

---

## Step 3 — Evaluate (do not skip)

```bash
python evaluate.py --config config.yaml --adapter outputs/qlora-cre/adapter
```

This is the most important file to read. It runs the held-out set and reports:
- **Tool-call accuracy** — did the model emit the *expected tool name* with
  *parseable JSON arguments*? This is your **regression slice**: run it against
  the **base model with no adapter** too (`--adapter ""`) and make sure the
  adapter didn't make tool-calling *worse*. Catastrophic forgetting shows up
  here first.
- **Response sanity** — light checks on the non-tool answers.

Rule of thumb: **ship only if the adapter ≥ base on tool-call accuracy AND wins
on the thing you trained it for.** If tool-calling drops, lower `lora_r`/epochs,
add general+tool examples back into the mix, or don't ship.

---

## Step 4 — Merge + push, then deploy (managed)

```bash
python merge_and_push.py --config config.yaml \
  --adapter outputs/qlora-cre/adapter \
  --repo your-hf-username/spacegoose-cre-qwen7b   # omit --repo to just merge locally
```

Deploy on **Hugging Face Inference Endpoints** (managed, autoscaling, you picked
this): New Endpoint → your merged repo → a GPU (e.g. L4/A10) → it serves a
**TGI** server with an OpenAI-compatible `/v1` route.

Wire it into Space Goose with **zero code** — it's just a BYOK config:

- Settings → AI Model → provider **Custom (OpenAI-Compatible)**
- **Base URL:** `https://<your-endpoint>.endpoints.huggingface.cloud/v1`
- **API key:** your `hf_…` token · **Model:** the merged repo id

(Your `openai_compatible` provider already accepts a custom `base_url`, so a
fine-tuned model drops straight into chat + property flows. You can A/B it
against the platform model per-user via BYOK.)

---

## Files

| File | Purpose |
|---|---|
| `config.yaml` | base model, LoRA + training hyperparameters |
| `prepare_dataset.py` | build `messages` JSONL from the sample or your DB |
| `train_qlora.py` | 4-bit base + LoRA adapter SFT (TRL `SFTTrainer`) |
| `evaluate.py` | tool-calling regression eval + response checks |
| `merge_and_push.py` | merge adapter → base, optional Hub push |
| `sample_data/` | a dozen CRE examples (incl. tool calls) to run the loop now |

## Glossary

- **PEFT** — Parameter-Efficient Fine-Tuning; the family LoRA belongs to.
- **LoRA** — Low-Rank Adaptation; trains small `A·B` adapters, freezes the base.
- **QLoRA** — LoRA on a **4-bit quantized** base (NF4 + double-quant + paged
  optimizer) so a 7B trains on one consumer GPU.
- **SFT** — Supervised Fine-Tuning on (prompt → desired response) pairs.
- **Catastrophic forgetting** — the model loses prior skills (e.g. tool-calling)
  while learning the new task. The eval's regression slice is how you catch it.
- **TGI** — Text Generation Inference; HF's serving stack, exposes OpenAI `/v1`.

## Version note

`requirements.txt` pins known-good versions — the TRL/PEFT APIs move fast. If
you bump them, re-check the `SFTTrainer` / `SFTConfig` signature in
`train_qlora.py`.
