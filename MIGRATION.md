# MIGRATION.md — Self-hosted, fine-tuned models on Baseten

> A running log of the migration of Space Goose's chat from the Anthropic API to
> self-hosted open models on Baseten. Written to be **studied**, not just executed:
> every decision records the *why* and the tradeoffs, so this doubles as a learning
> notebook for inference engineering and the Baseten platform.
>
> Audience: the project owner, learning to be a Baseten/inference SA.
> Status keys: ✅ done · 🔄 in progress · ⏳ pending · ❓ open decision

---

## 0. The one-paragraph version

Today every model call goes through a small in-house abstraction (`backend/app/llm/`)
that already speaks two dialects: **Anthropic** and **OpenAI-compatible**. Baseten
serves models over an OpenAI-compatible API. That means the *seam already exists* — we
can point the existing `openai_compatible` provider at a Baseten endpoint and the whole
chat path (streaming, tool calls) works with near-zero protocol code. The migration is
therefore less about plumbing and more about: (a) proving a small open model is "good
enough" with a real eval set *before* switching, (b) fine-tuning one model on the
owner's human-written void analyses / investment memos, and (c) deploying on an L4 GPU
with scale-to-zero economics.

---

## 1. How the system works today (baseline architecture)

### The chat request lifecycle (`backend/app/api/chat.py`, over WebSocket)

1. **Resolve the model for this user** — `resolve_user_llm()`
   (`app/services/user_llm.py`). Priority: BYOK (user's own key) → paid tier gets
   platform Claude Haiku → **free tier gets Gemini 2.0 Flash** via the
   OpenAI-compatible client. The platform is *already* multi-provider in production.
2. **Guardrails** (`app/services/guardrails.py`) — cheap regex first; ambiguous
   messages get a one-word LLM topic classification ("CRE" / "OFF_TOPIC"). Then a
   token-budget check (skipped for BYOK).
3. **Plan the turn** — `plan_workflow()` (`app/services/orchestrator.py`): a tiny
   (≤50 token) LLM call returns a comma-separated list of specialists to run, e.g.
   `scout, analyst, matchmaker`. Parse failure → `["scout"]`.
4. **Run each specialist in order, streaming** — each specialist = a system prompt +
   a *filtered tool subset* + prior specialists' outputs as context. Tool calls run
   through the MCP gateway (timeouts, circuit breaker, audit). **Tool results are fed
   back as plain text in a user message**, not native tool-result blocks (more
   forgiving for small models). Max 3 tool round-trips/turn.
5. **Synthesize** — if >1 specialist ran, one final LLM pass merges outputs.
6. **Post-turn, fire-and-forget** — conversation-title generation (first message) and
   fact extraction (≤200 token strict-JSON call). Never block the stream.

Any failure in the specialist branch falls back to a legacy single-model path
(`get_orchestrator_response`).

### Key mental-model correction

- **"Main assistant"** = the orchestrator (planner call + synthesis call + legacy
  fallback).
- **The four "specialists"** (`scout`, `analyst`, `matchmaker`, `outreach` in
  `app/agents/specialists/`) are **prompts + tool allowlists, NOT separate models**.
  They all run on whatever model the user resolved to. A dormant tier map
  (`MODEL_TIER_MAP` in `base.py`) exists but is bypassed because the chat path always
  passes a resolved LLM. **"Specialist" = persona, not model.**
- **"Traffic" and "demographic" assistants are TOOLS, not models.**
  `demographics_analysis` → Census ACS API. `traffic_counts` → DOT vehicle counts.
  `business_search` → Google Places. No LLM inside them. Exactly **two tools are
  LLM-backed**: `void_analysis` (structured JSON gap analysis) and `draft_outreach`
  (email drafting).

### Per-specialist model overrides already exist

BYOK users can set `specialist_models_json`; `_build_specialist_request`
(`orchestrator.py`) honors it. **Our migration reuses this mechanism** — we populate
it with our Baseten endpoints rather than inventing new routing.

### Complete LLM call-site inventory

The Anthropic SDK is imported in exactly **one** file
(`app/llm/providers/anthropic_client.py`). Everything else speaks the internal
`LLMChatRequest` dialect (plain system string + user/assistant text + optional
function-calling). No prompt caching, no extended thinking, no multi-block content —
very portable.

| Call site | Task | Output | Difficulty for a small model |
|---|---|---|---|
| `plan_workflow` | route to specialists | comma list (+ fallback) | trivial |
| `guardrails._classify_with_haiku` | topic gate | one word | trivial |
| `generate_conversation_title` | chat titles | 3–6 words | trivial |
| `fact_extractor` | personal facts | strict JSON → `[]` on fail | easy |
| specialists (scout/analyst/matchmaker/outreach) | the core chat | prose + tool calls | **the real test** |
| `synthesize_specialist_outputs` + legacy orchestrator | final answer | long prose | quality bar |
| `void_analysis` | gap analysis | structured JSON report | **fine-tune target** |
| `listing_match` | score listings 0–100 vs buy-box | JSON | easy–medium |
| `outreach_ai` | email drafts | prose | medium |
| `document_parser` (vision) | parse flyers/OMs from PDF images | structured JSON | **hardest — OUT OF SCOPE** |

### What makes this easy

- The `openai_compatible` provider seam already exists (could BYOK-test a Baseten
  endpoint *today*, zero backend code). A `huggingface` provider already points at
  `Qwen/Qwen2.5-7B-Instruct` — someone already explored open models here.
- Per-specialist model overrides exist.
- Feature flags + graceful fallbacks everywhere (`LLM_PROVIDER`,
  `enable_specialist_routing`, fallback-to-scout, fallback-to-legacy) → reversible,
  incremental cutover.
- Tool results fed as plain text, not strict tool-result protocol.
- Per-specialist metrics (tokens, latency, success) already recorded → ready baseline.

### What makes this hard / risky

- **Tool-calling quality** is the load-bearing risk for 7–8B models. Eval must measure
  it before any swap.
- **Vision document parsing** is Anthropic-only by design (`vision_document()` raises
  "not supported" on the OpenAI-compatible client). → **Out of scope; stays on
  Anthropic.**
- **Cost inverts at low traffic.** A dedicated GPU is a fixed monthly cost vs.
  pay-per-token Haiku/Gemini-Flash (already near the cheapest options). Scale-to-zero
  mitigates but trades money for cold-start latency.
- **Mixed client/model config bug.** Some call sites take the *client* from the
  resolved LLM but the *model ID* from a setting (e.g. the guardrail classifier would
  send `claude-3-5-haiku` as the model name to a non-Anthropic endpoint). Per-call-site
  model selection must become provider-aware.
- **Stale Anthropic model IDs.** Configured defaults (`claude-3-5-haiku-20241022`,
  `claude-3-5-sonnet-latest`) are retired/aliased; a "deprecated alias" map rewrites
  the current Haiku 4.5 ID *back* to the retired 3.5 one. Must verify prod isn't
  404ing — the baseline we benchmark against has to be real and working.
- **BYOK invariants.** The "zero platform tokens for BYOK" guarantee + usage accounting
  assume per-token billing; self-hosted GPU-hours need a deliberate accounting decision.

---

## 2. Decisions locked in (from the kickoff Q&A, 2026-06-14)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Scope = easy wins** (text calls): planner, classifier, title, facts, specialists, synthesis, `listing_match`, `outreach_ai`. | Highest value / lowest risk. |
| D2 | **Vision document parsing stays on Anthropic.** | Needs a VLM + new client method; out of scope. |
| D3 | **Fine-tune one model for void analysis + investment memos.** Corpus = human-written docs in OneDrive. | This is the domain-specialization payoff; human-written → true SFT, not distillation. |
| D4 | **Baseten models become the new platform default. BYOK stays** as the "bring your own frontier model" path, unchanged. | Preserves user choice; we own the default. |
| D5 | **Target GPU = L4 (24 GB).** No beefy GPU until alpha users. | Cost; L4 comfortably fits a quantized 7–8B model. |
| D6 | **Scale-to-zero by default + a quick toggle to always-on** for onboarding/demos. | Cheap when idle; warm when it matters. (See latency note in §4.) |
| D7 | **Fine-tune on Baseten IF cost-competitive; otherwise cheapest option.** Cost analysis required before committing. | Owner wants Baseten learning, not at a large premium. |
| D8 | **Success bar: ≥90% tool-call accuracy; P95 latency at chat-app industry norm.** All other targets default to industry standard. | Owner-set quality floor + latency target. |

### Leading architectural recommendation (to confirm in Phase 1)

**One shared base model on a single L4, serving every persona via different system
prompts (exactly how the code already works), plus a LoRA adapter for the
void/memo fine-tune** — rather than N separate model deployments. This is the
cheapest L4-friendly shape and the most scale-to-zero-friendly (one cold start, not
five). Utility calls (planner/classifier/title/facts) either reuse the base model or,
if we want them faster/cheaper, a small 1–3B model as a second deployment — decided by
eval + cost, not assumed.

---

## 3. Phase map

| Phase | Name | Goal | Exit criteria |
|---|---|---|---|
| **0** | Baseline & evals | Lock a working baseline + a real eval set; smoke-test Baseten with zero backend code. | Eval harness runs; baseline (current models) scored; stale model IDs verified/fixed; one Baseten endpoint answered a request through the existing provider. |
| **1** | Base-model selection + cost | Pick the smallest open model that clears the eval bar on an L4; price Baseten L4 inference. | A chosen base model + quantization, justified against the eval scores and a written GPU cost model. |
| **2** | Fine-tuning data prep | Turn OneDrive void analyses / investment memos into clean SFT training pairs. | A versioned, inspected train/val dataset + a data card. |
| **3** | Fine-tune | Produce a LoRA (or full) fine-tune for void/memo; pick the cheapest adequate training venue. | Trained adapter that beats the base model on the void/memo eval slice; training-cost comparison written. |
| **4** | Deploy on Baseten (Truss) | Package + deploy base (and adapter) on L4 with scale-to-zero + always-on toggle. | Live endpoint; cold-start + warm latency measured; toggle works. |
| **5** | Cutover behind flags | Route real call sites to Baseten incrementally: utilities → specialists → void/memo. Each behind a flag, reversible. | Each call site swappable per-env; rollback verified; BYOK + accounting invariants intact. |
| **6** | Benchmark vs baseline | Compare cost / latency / quality against the Anthropic baseline from Phase 0. | A decision-grade report: where the small model wins, ties, loses. |

The owner's original draft phasing is preserved; the only additions are **Phase 0's
zero-code Baseten smoke test** and **the stale-model-ID baseline fix**.

---

## 4. Success criteria & industry-standard targets (Phase 0 defines these precisely)

- **Tool-call accuracy ≥ 90%** (owner-set). Measured on a replayed-turns suite: did the
  model pick the right tool and emit valid, schema-correct arguments?
- **Latency — the metric that matters for streaming chat is TTFT (time-to-first-token),
  not full-response P95.** Industry reference points (to verify with live measurement,
  not asserted as fact):
  - Hosted frontier APIs: ~0.2–0.5 s TTFT.
  - Self-hosted 7–8B on L4, warm: target sub-second TTFT; throughput ~30–80 tok/s
    single-stream (to be measured).
  - **P95 caveat:** *with scale-to-zero, P95 is dominated by cold starts* (tens of
    seconds to minutes), which is fundamentally incompatible with a good P95. The D6
    toggle resolves this: **report P95 in always-on mode; treat cold-start requests as
    a separate, labeled outlier class.** This is the central latency tradeoff of the
    whole project.
- **Quality:** LLM-as-judge preference of small-vs-baseline outputs on void/memo and
  general-chat slices; target ≥ parity (tie-or-better) on a majority of cases. Exact
  threshold set in Phase 0.

---

## 5. Open decisions / analyses still owed (❓)

- ❓ **GPU cost model** (Phase 1): Baseten L4 $/hr, scale-to-zero idle behavior,
  cold-start time, $/1M tokens equivalent vs current Haiku/Gemini-Flash spend.
- ❓ **Training venue cost** (Phase 3): Baseten training vs. alternatives (e.g. managed
  fine-tune services, rented GPUs). D7 says cheapest-adequate wins.
- ❓ **One model vs. two** (Phase 1): shared base for everything, or a tiny 1–3B for
  utility calls. Decide on eval + cost.
- ❓ **LoRA vs. full fine-tune** (Phase 3): LoRA is cheaper, adapter-swappable, L4-fit;
  full FT only if quality demands.
- ❓ **BYOK token-accounting** for self-hosted GPU-hours (Phase 5).

---

## 6. Concept glossary (learning notes)

- **OpenAI-compatible API** — a de-facto standard request/response shape
  (`/chat/completions`). Baseten, vLLM, TGI, Together, etc. all speak it, which is why
  one client class can target many backends.
- **Truss** — Baseten's open-source packaging format: a model + its serving code +
  config, deployed as a container. Phase 4.
- **Scale-to-zero** — autoscale min-replicas to 0 when idle (pay nothing) and spin up
  on demand (cold start). The cost/latency lever behind D6.
- **TTFT vs throughput** — time-to-first-token (responsiveness) vs tokens/sec
  (how fast the rest streams). Chat UX lives or dies on TTFT.
- **LoRA (Low-Rank Adaptation)** — fine-tune a small set of added weights instead of
  the whole model. Cheap to train, small to store, swappable at serve time on a shared
  base. The likely shape of the void/memo fine-tune.
- **Quantization (FP8/INT8/AWQ/GPTQ)** — store/run weights at lower precision to fit a
  bigger model in 24 GB and speed inference, at a small quality cost. How a 7–8B (or
  even a quantized larger model) fits an L4.
- **SFT (supervised fine-tuning)** — train on (input → ideal output) pairs. Human-written
  memos make this real SFT rather than distillation (training on another model's output).

---

## 7. Changelog

- **2026-06-14** — Orientation complete. Baseline architecture documented (§1).
  Kickoff decisions locked (§2, D1–D8). Phase map drafted (§3). Doc created. No code
  changes yet. Next: owner green-light on the phase map, then execute Phase 0.
