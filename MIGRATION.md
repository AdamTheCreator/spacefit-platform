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
| D9 | **Migration gate = non-regression vs the Anthropic baseline (parity-or-better), not a hard absolute 90%.** The incumbent (Haiku 4.5) itself scores 85.7% tool-call on the seed eval, so an absolute-90% gate would reject a Haiku-equivalent open model. 90% stays a stretch goal we reach by fixing the real gaps the eval surfaced. | Industry-standard migration framing; measured 2026-06-15, see §4.1. |
| D10 | **Candidate base model = `Qwen/Qwen2.5-7B-Instruct`** (to be eval-validated before commit). | Apache-2.0 (clean commercial license), best-in-class 7B tool-caller, fits L4 (≈15 GB bf16 / ≈8 GB quantized), first-class vLLM/Truss serving + LoRA ecosystem, and already the repo's configured `huggingface_model` default. Alternatives: Qwen3-8B (level-up if it misses), Llama-3.1-8B (license fallback). |
| D11 | **The eval has TWO dimensions: tool-calling (can it gather the right data?) AND advisory quality (can it reason about property-to-client fit and give a go/no-go?).** The advisory dimension is graded by LLM-as-judge on a 5-criterion rubric; the void/memo fine-tune primarily targets it. "Good enough" = parity-or-better on **both**. | Owner: "this is an agent… conversational… is it a good property to proceed on" — the advisory voice is the product value, not tool-picking. |
| D12 | **Proceed with LoRA fine-tuning** (Gap 1). The diagnosis (§4.6) shows base Qwen's advisory failures are (a) voice/disposition + (b) calibration — *in-corpus, fixable by SFT* — with **no hard reasoning ceiling (c)**. | A fine-tune can move voice/format/disposition and knowledge that lives in the training data; it can't add raw reasoning capacity. The failures are the former. |
| D13 | **Data strategy = human-memo gold set with inputs templated to the live advisory format; use real source-data reconstruction where it exists; teacher-generated data only for input-distribution augmentation, never as the voice source** (Gap 2, §4.7). | The human memos are the irreplaceable voice/judgment asset (the moat). We control the input format, so we kill train/serve skew by templating rather than by replacing human outputs with the teacher's. |
| D14 | **Build a held-out advisory test set the fine-tune never sees, grow the eval with real dogfood prompts, add human spot-checks — before trusting any fine-tune delta** (Gap 3). | LLM-as-judge on a tiny suite is gameable; an untainted held-out set + human eyes is how we avoid overfitting to the judge. |
| D15 | **Fine-tune in bf16 first, lock quality, THEN quantize to FP8 and re-run both evals** (Gap 5). Never fine-tune and quantize in the same step. | Two simultaneous changes make a quality delta unattributable. Separate them to know what caused what. |
| D16 | **Serving architecture = one smart fine-tuned Qwen (LoRA adapters per persona if voices differ) + a cheap workhorse** for routing/titles/classification (tiny model or stay on Haiku), decided on cost + eval (Gap 6). | Don't pay 7B advisory inference for a one-word classifier; route cheap calls cheaply via the existing `specialist_models` seam. |
| D17 | **Serving policy = business-hours always-on + overnight scale-to-zero + weight caching; measure cached-cold vs always-on and choose deliberately** (Gap 7). | A slow cold start mid client-meeting is unacceptable; scale-to-zero stays for off-hours cost. The two are reconciled by schedule + caching, with the tradeoff measured, not guessed. |
| D18 | **Contingency: fine-tuned Qwen2.5-14B in FP8 (~14 GB) fits the 24 GB L4** where bf16 14B (~28 GB) would not (Gap 4). On standby only — invoked if Phase 3 reveals a reasoning ceiling. | The diagnosis (D12) says we likely won't need it, but it's documented now so it isn't a late surprise. |
| D19 | **Phase-2 data prep = an LLM-assisted curation pipeline (`backend/finetune/curate.py`), not hand-labelling.** Claude classifies + quality-gates each doc, reconstructs the input in the advisory format, preserves the human output verbatim, and **redacts all PII / client identity (owner-confirmed)**. | Owner has many mixed docs and can't hand-label; a fine-tune amplifies its data, so the model must triage + gate, not blindly convert. Validated end-to-end 2026-06-15 (§4.8). |
| D21 | **Train on Baseten Training (managed LoRA SFT) — resolves D7.** At our scale (~40 pairs, 7B LoRA) every venue is **<~$10/run**, so cost doesn't separate them. Baseten wins on alignment: you own the weights, train→deploy is integrated onto the L4 we already built, and it's the platform we're learning. Fallbacks if Baseten Training doesn't fit Qwen2.5-7B LoRA: a rented A100 + Unsloth (~$1–2/run, most control) or Together AI ($0.48/1M tokens, training-only — skip their $6.49/hr hosting, download the adapter to our L4). | Cost analysis 2026-06-15 (web-sourced). The real risk at ~40 examples is *data size, not cost*, so pick for fit + learning, not pennies. (D20 = the §4.9 validation findings.) |

### Leading architectural recommendation (to confirm in Phase 1)

**One shared base model on a single L4, serving every persona via different system
prompts (exactly how the code already works), plus a LoRA adapter for the
void/memo fine-tune** — rather than N separate model deployments. This is the
cheapest L4-friendly shape and the most scale-to-zero-friendly (one cold start, not
five). Utility calls (planner/classifier/title/facts) either reuse the base model or,
if we want them faster/cheaper, a small 1–3B model as a second deployment — decided by
eval + cost, not assumed.

### 2.1 Model-selection rubric — and why two tempting models don't fit

Every candidate is filtered through four constraints **before** the eval; the eval then
decides among survivors. Leaderboard rank and launch hype are deliberately *not* on the
list — they answer questions we aren't asking.

1. **Fits the hardware budget** (L4 / 24 GB → ~7–8B dense, or a small MoE whose *total*
   params fit in 24 GB — MoE saves compute, not memory; all experts stay resident).
2. **Strong at the load-bearing capability — tool-calling — proven on *our* eval**, not on
   academic benchmarks.
3. **Clean commercial license.**
4. **First-class serving (vLLM/Truss) + fine-tuning (LoRA) support** — we fine-tune it
   ourselves for void/memo, so we want a clean, well-understood base.

Two models the owner raised, rejected for *opposite* reasons (a useful teaching pair):

- **GLM-5.1** (z.ai, Apr 2026) — 744B-param MoE (~40B active), MIT, open weights, SOTA
  agentic / SWE-Bench. Genuinely excellent — but **~15–30× too big for an L4**: MoE cuts
  compute, not memory, so all 744B weights must be resident (~370–400 GB even at 4-bit → a
  multi-H100 node, thousands/mo). Wrong *cost/size class* for a cheap self-hosted default.
  Keep as a possible **BYOK / premium-tier / distillation-teacher** option, not an L4 target.
- **Qwen2.5-RomboTiesTest-7B** (community TIES merge; the name literally says "Test") —
  right *size* (7B) but optimized for the **Open LLM Leaderboard** (MMLU/MATH/IFEval), which
  does **not** measure tool-calling. Merges are known to break the base's tool-call chat
  template (reports of `<function_call>` vs `<tool_call>`, `finish_reason=stop`); license
  inheritance from merge parents is murky; and it's a worse fine-tune base than the clean
  instruct model. Fine to run through the eval as a *challenger*, not as a foundation.

Net: **primary candidate stays `Qwen/Qwen2.5-7B-Instruct`** (D10) — validate on the eval
before committing; optionally eval RomboTies head-to-head and let the tool-call score decide.

---

## 3. Phase map

**Revised 2026-06-15 after the plan review (Gaps 1–7, §8).** The big structural changes:
a diagnosis *gate* before fine-tuning (Gap 1, done — §4.6); eval hardening moved *ahead* of
training (Gap 3); quantization split into its own phase *after* quality is locked (Gap 5);
and serving architecture + cold-start policy made explicit (Gaps 6–7).

| Phase | Name | Goal | Exit criteria |
|---|---|---|---|
| **0** | Baseline & evals | ✅ done | harness + baseline scored; Baseten smoke test |
| **1** | Model selection + L4 validation | ✅ done | Qwen2.5-7B picked, deployed, benchmarked (§4.5) |
| **1.5** | **Diagnosis gate (Gap 1)** | ✅ done — classify *why* base Qwen fails advisory | §4.6: failures are voice/disposition + calibration, no hard reasoning ceiling → **LoRA is the right tool** |
| **2** | **Eval hardening + data construction** (Gaps 2, 3) | Build an un-gameable eval *and* a training set whose input distribution matches production. | Held-out test set the fine-tune never sees; eval grown with real dogfood prompts + human spot-check rubric; versioned SFT dataset (human-memo gold, inputs templated to the live advisory format) + data card. |
| **3** | **LoRA fine-tune in bf16** (Gap 5a) | Train the adapter on the gold set; measure on held-out. | Adapter moves advisory toward parity on the held-out set **with no tool-calling regression**, confirmed by human spot-check. If a reasoning ceiling appears, branch to the 14B-FP8 contingency (Gap 4 / D18). |
| **4** | **Quantize to FP8 + re-eval** (Gap 5b) | Quantize the *finished* fine-tune; confirm quality survives. | Both eval dimensions re-run bf16 vs FP8; quality delta within tolerance, VRAM/throughput gain measured. |
| **5** | **Serving architecture** (Gap 6) | One smart fine-tuned Qwen (LoRA adapters per persona if voices differ) + a cheap workhorse for routing/titles/classification (tiny model or stay on Haiku). | Architecture chosen on measured cost + eval; per-persona routing wired behind the existing `specialist_models` seam. |
| **6** | **Serving policy + flagged cutover** (Gap 7) | Business-hours always-on / overnight scale-to-zero / weight caching; route real call sites over incrementally. | Cached-cold vs always-on latency measured + a deliberate schedule chosen; cutover utilities → specialists → advisory, each behind a reversible flag; BYOK + accounting invariants intact. |
| **7** | Final benchmark vs baseline | Decision-grade cost / latency / quality vs the Anthropic baseline. | Report on the **held-out** set: where the fine-tuned model wins, ties, loses. |

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

### 4.1 Phase 0 baseline (measured 2026-06-15)

First live run of the harness, against the current Anthropic Haiku — the model
the paid-tier chat is meant to use, and therefore the thing a self-hosted model
must not regress against.

**Stale-ID check — CONFIRMED BROKEN.** A one-call probe:

| Model id | Result |
|---|---|
| `claude-3-5-haiku-20241022` (the repo's configured `anthropic_model` default) | **404 `not_found_error`** — retired Feb 2026 |
| `claude-haiku-4-5` (current) | OK |

So any platform path that falls through to the code default (rather than a prod
env override) is 404-ing today. Fix is owed before this baseline reflects a
real running config — tracked as a Phase 0 task.

**Baseline scores — `claude-haiku-4-5`, 27-case seed suite:**

| Slice | Score | Notes |
|---|---|---|
| Routing | 13/13 = **100%** | `plan_workflow` picks specialists reliably |
| Tool-call | 12/14 = **85.7%** | below the 90% stretch bar — see failures |
| Overall | 25/27 = **92.6%** | |

**The two failures are real system gaps, not eval artifacts:**

1. `tool-out-draft-01` — outreach specialist asked to draft outreach to two
   named tenants **called no tool** (expected `draft_outreach`). The
   `should_force_tool_use` heuristic doesn't catch "draft outreach …" phrasing,
   so the model is free to answer in prose instead of invoking its one tool.
2. `tool-scout-abstain-01` — scout, given a vague "I'm looking at a site, where
   do we start?" with **no address**, called `demographics_analysis` instead of
   asking for the address. Over-eager tool-calling on under-specified input.

Both are fixable in prompts / forcing logic and improve the product regardless
of the migration — a concrete example of the eval earning its keep before we've
swapped a single model.

**Caveats:** N=27 is small (each case ≈ 3.7%); scores are directional. Grow the
seed set as real chat traffic arrives.

### 4.2 Real eval material discovered (2026-06-15)

The orphaned `backend/spacefit.db` (flagged in CLAUDE.md as a leftover) turned out to hold
**real dogfooding chat data**: 7 sessions / 22 messages / **7 user turns (4 distinct
prompts)** from Jan 2026. The seed eval cases (§3, Phase 0) are **synthetic** — hand-authored
from the tool schemas + routing patterns, *not* from these conversations (the harness was
built before this DB was found). The real prompts are messier than the synthetic ones, in
instructive ways:

- "coffee shops … in a **20 min driving radius** of downtown san francisco" — radius given
  in *time*, but the tool takes miles.
- "Get **foot traffic** data for 525 N Lamar Blvd, Austin TX" — *no tool serves foot traffic*
  without a Placer upload → correct behavior is to ask for the upload, not call a tool.
- "analyze demographics for **Westfield Mall**" (×4) — *ambiguous, non-unique* location
  (which Westfield?) → arguably should clarify, not geocode a guess.
- "Please **research** downtown westport" — vague verb; routes to scout but the tool is unclear.

Lesson: **synthetic evals flatter models** — they're cleaner than reality. Folding these real
prompts in (pending owner sign-off on the ambiguous labels) makes the baseline more honest;
real-world tool-call accuracy is likely *below* the 85.7% measured on the clean set.

### 4.3 Candidate smoke test — Qwen2.5-7B-Instruct on the HF router (2026-06-15)

Scored `Qwen/Qwen2.5-7B-Instruct` on the same suite via Hugging Face's serverless router
(zero Baseten cost). Headline numbers looked bad (81.5%, then 66.7%) — **but the gap is the
measurement instrument, not the model.** Most "failures" were `BYOKError: malformed request`,
and they **move between runs**:

| Run | Tool cases that errored `malformed` |
|---|---|
| auto-router | biz, traffic, abstain (3, scattered) |
| diagnostic (each ×3) | biz failed 2/3; traffic 0/3; abstain 1/3 |
| pinned `:together` | the first 6 tool cases, then clean |

Non-determinism ⇒ infrastructure. The HF router multiplexes across third-party providers with
**inconsistent OpenAI tool-calling support** (some 400 on `tools`/`tool_choice:"required"`),
and a free token hits **rate limits** mid-run. Even pinning a provider didn't fix it.

**The model signal, separated from the noise:**
- On every cleanly-served case, Qwen picked the **correct** tool — `business_search`,
  `demographics_analysis`, `tenant_roster`, `traffic_counts`, `document_search`,
  `void_analysis`, `costar_import`, `placer_import`, `draft_outreach` all observed correct.
- It **passed `tool-out-draft-01`** (`draft_outreach`) — the case the **Haiku baseline
  failed**.
- Its one genuine miss is `tool-scout-abstain-01` (over-eager: calls 3 tools on a vague,
  address-less prompt) — the **same** weakness Haiku showed.
- Routing: 11/13 — slightly looser than Haiku (13/13); the 2 misses are *over-routing*
  (adding an extra specialist), not wrong picks.

**Verdict:** Qwen2.5-7B-Instruct is **at parity-or-better with Haiku on tool-calling** (D10
holds). But a trustworthy benchmark needs a **controlled serving stack** — the whole point of
self-hosting. Next real number comes from Baseten (single vLLM, known tool-call parser, our
own rate limits), not a shared router.

**Two harness improvements this surfaced (next increments):** (a) classify infra errors
(`malformed`/429) separately from model failures in the scorecard, so the headline % reflects
quality; (b) fold in the §4.2 real prompts.

### 4.4 Advisory-quality eval + baseline (2026-06-15)

Tool-calling is necessary but it isn't the product. The owner's point: the model is an
*advisor* — it should read a property, connect it to *this broker's client and their book of
business*, and say whether it's worth pursuing. So we added a second eval dimension graded by
**LLM-as-judge** (`evals/judge.py`, `evals/run_advisory.py`): the candidate writes a
recommendation for a property + data + client scenario; a strong, *separate* model (Claude
Sonnet 4.6, so it isn't grading itself) scores it 1–5 on five criteria — property
understanding, client-fit reasoning, recommendation clarity, groundedness, tone.

**Baseline — Haiku 4.5 advisor, 4 scenarios: mean 4.35/5, 3/4 'send-to-client' pass.**

| Criterion | Mean /5 |
|---|---|
| recommendation_clarity | 5.00 |
| tone | 4.75 |
| client_fit_reasoning | 4.25 |
| property_understanding | 4.00 |
| **grounded** | **3.75** (lowest) |

Two insights that shape the project:
- **`grounded` is the weakest criterion** — claims beyond the supplied data, the failure mode
  that erodes broker trust. Watch it on every candidate.
- **The one scenario that failed the send-to-client bar was `adv-memo-invest`** — the
  investment-memo case (cap rate vs target, rollover risk). That is *exactly* the domain the
  owner's human-written memos will fine-tune. Direct evidence the fine-tune has real work to
  do, and a built-in way to measure its payoff: we expect the memo scenario to improve most.

Qwen (and later the fine-tuned model) get scored on this same dimension — "good enough" now
means parity-or-better on **both** tool-calling and advisory quality.

### 4.5 Controlled benchmark — Qwen2.5-7B on Baseten L4 (2026-06-15)

Re-ran BOTH eval dimensions against the dedicated vLLM deployment. The tool-call
infrastructure flakiness from the HF router (§4.3) is **gone** — a clean run, zero
`malformed` errors — confirming the serving-control thesis.

| Dimension | Haiku 4.5 (baseline) | Qwen2.5-7B (Baseten L4) |
|---|---|---|
| **Tool-calling** | 12/14 = 85.7% | **13/14 = 92.9%** — ✓ beats baseline, clears the 90% bar |
| Routing | 13/13 = 100% | 11/13 = 84.6% (2 over-routes) |
| Overall tool/routing | 25/27 = 92.6% | 24/27 = 88.9% |
| **Advisory quality** | **4.35/5, 3/4 pass** | **2.80/5, 0/4 pass** — ✗ big regression |
| Warm TTFT | n/a (hosted) | **~0.6–1.3 s (median ~0.9 s)** — ✓ good chat UX |

**The decisive finding:** base Qwen **matches/beats Haiku at *gathering data* but is much
weaker at the *advisory reasoning + voice*** — the exact dimension that is the product. It
drops across every criterion (client-fit 2.5 vs 4.25, recommendation clarity 3.0 vs 5.0,
tone 2.5 vs 4.75); the judge flagged factual slips, indecisiveness, and glossing the memo's
rollover risk. **0 of 4 scenarios were 'send-to-client'.**

**Conclusion: do NOT ship base Qwen as-is — it would regress the advisory experience.**
Tool-calling is solved (controlled serving + `hermes` parser); latency is good (~0.9 s warm
TTFT on an L4). The one remaining gap is advisory quality — which is *precisely* what the
void/memo fine-tune (Phases 2–3) targets. And the two-dimension eval (D11) earned its keep:
tool-calling alone (88.9%) would have looked shippable; the advisory dimension caught the
real regression. That gap is the project's reason for existing.

Deployment is scale-to-zero — the L4 sleeps automatically after ~15 min idle (no action
needed; flip `min_replica` to 1 for a demo).

**Phase status:** Phase 0 (baseline + evals) ✅ and Phase 1 (model selected + validated on an
L4) ✅. Next: **Phase 2 — fine-tuning data prep** from the OneDrive void analyses / memos, to
close the advisory gap.

### 4.6 Advisory failure diagnosis — the pre-fine-tune gate (Gap 1, 2026-06-15)

Read all four of base Qwen's advisory transcripts (saved in the scorecard) and labelled each
failure: **(a) voice/format/disposition** (LoRA fixes), **(b) domain knowledge/calibration**
(LoRA fixes *iff* it's in the memos), **(c) reasoning ceiling** (fine-tuning will NOT fix).

| Case | Directional call | Dominant failure | Evidence from the transcript |
|---|---|---|---|
| adv-fit-coffee | ✅ correct (pursue) | **(a)** + minor (b) | Right analysis, but "Hey [Broker's Name]… Good luck! Cheers!", "Absolutely. Yes, absolutely." — eager-assistant voice, over-bullish; *did* list missing data. |
| adv-pass-bigbox | ✅ correct (pass) | **(a)** + (b) slip | Correct pass, but a grounding slip ("8,000 SF… fits the property size" — it's a 40,000 SF box) and a hedged, garbled close ("a go-to-no-go situation"). |
| adv-uncertain | ✅ correct (investigate) | **(a)** + (b) | Flags missing data correctly, but "reads like a templated AI checklist," indecisive, surface-level client tie-in. |
| adv-memo-invest | ⚠️ wrong emphasis | **(b)** + (a) | **Saw** "30% rolls over in 24 months" **and** the client's "limited rollover risk" criterion, then called it "manageable" — positivity bias + a domain-threshold miss, not an inability to reason the steps. |

**Breakdown: predominantly (a) voice/disposition, with meaningful (b) calibration; no clear (c).**
The single most common pattern is **RLHF positivity bias / sycophancy** — base instruct models
are tuned to be agreeable, but a broker memo demands calibrated skepticism (willing to say "that
30% rollover kills it for your risk-averse client"). In every case the directional reasoning was
*correct*; what's missing is the disciplined voice, the critical disposition, and a few domain
thresholds — exactly what human memos carry.

**Verdict: proceed with LoRA (D12).** The gap is the kind fine-tuning fixes. The memo case is the
one to watch in Phase 3 (closest to a calibration/reasoning concern); if a true ceiling shows up
there post-fine-tune, branch to the 14B-FP8 contingency (D18). Teaching note: this gate is *why*
we diagnose before training — a fine-tune can't add reasoning capacity, so spending one on a (c)
failure would burn time and money for no gain.

### 4.7 Fine-tuning data construction (Gap 2, 2026-06-15)

A training pair is *input → ideal output*. We have the ideal outputs (the human memos); we're
missing inputs that match what the **live app** actually sends the advisory step (a property
context + tool-result blocks + the user's question). Three strategies, compared:

| Strategy | Input fidelity vs production | Voice/judgment source | Volume | Cost/effort | Risk |
|---|---|---|---|---|---|
| 1. Reverse-construct inputs from each memo (strong model) | Medium — *but we control the format, so we can template it to match* | **Human memo (gold)** | = #memos | Low | Synthetic input drift (mitigated by templating) |
| 2. Reconstruct the *real* app input from source data | **Highest** | **Human memo (gold)** | Limited to memos with recoverable source data | High | Many memos may be standalone |
| 3. Teacher-assisted (Claude writes outputs on real inputs) | **Highest** | **Claude's voice, not the broker's** | High | Medium | **Wrong voice** (defeats the purpose); distillation ceiling; Anthropic commercial-terms consideration |

**Recommendation — a hybrid that protects the human memos as the irreplaceable asset:**
- **Anchor on Strategy 1**: pair every human memo with a reverse-constructed input, **rendered
  through the same formatter the live app uses** for the advisory step. Because we own that
  format, the usual "synthetic-input drift" risk is engineered away — the input *is* in the
  production shape; only its contents are reconstructed.
- **Upgrade to Strategy 2 wherever a memo has recoverable source data** — run the real CSV/property
  data through the app formatter for highest-fidelity pairs, and use those to *validate* that the
  Strategy-1 reconstructed inputs look realistic.
- **Use Strategy 3 sparingly, for input-distribution *augmentation* only — never as the voice
  source.** The whole point is the broker's voice + critical judgment; teacher data would teach
  Claude's instead, and Gap 1 says the broker voice is precisely what's missing. (Also flag the
  Anthropic commercial-terms angle before training a competing model on Claude outputs.)

Coherence with Gap 1: the diagnosis (gap = human voice + calibration) *demands* human-memo-sourced
outputs, which rules Strategy 3 out as the foundation. The deciding dependency: **how many memos
arrive with their source data** (Strategy 2 share) vs. standalone (Strategy 1) — see the open
clarifying question.

### 4.8 Curation pipeline built + validated (Gap 2 execution, 2026-06-15)

`backend/finetune/curate.py` implements the Gap-2 strategy as a runnable pipeline: extract text
(PDF / Word / CSV) → Claude curation (classify, quality-gate, reconstruct the input in the advisory
format, **preserve the human output verbatim**, **redact all PII** — owner decision) → stratified
train/held-out JSONL + a `report.md`. **No hand-labelling** — the owner skims the report + samples.

Validated end-to-end on synthetic docs: a junk template was dropped; a memo with *planted* fake PII
(client name, family office, street address, property name) was kept and turned into a clean SFT
pair — a production-style reconstructed input, the human verdict preserved (incl. the
rollover-vs-mandate judgment), and **every planted PII string redacted (0 leaks in `train.jsonl`)**.

The report's per-doc `had_source_data` field answers the Strategy-1-vs-2 split automatically, so the
earlier clarifying question is resolved by the pipeline rather than by hand. Corpus is being ported
to Google Drive; plan: validate on ~10 real docs, then run the whole drive. Curation model defaults
to Sonnet 4.6 (classify/extract/redact doesn't need the priciest model since the human output is
preserved, not generated); one-time cost is a few cents per doc.

### 4.9 Validation on REAL ASI docs — two plan-changing findings (2026-06-15)

Ran the pipeline on 9 real docs from the "ASI Documents" Drive (4 void analyses, 2 investment
memos, the xlsx void, + a flyer & an LOI as drop-tests). Results: gate works (flyer + LOI
correctly dropped); **both investment memos kept as "high" quality with excellent pairs** — the
reconstructed outputs lead with a calibrated go/no-go ("GO — with eyes open on second-pad leasing
execution risk") — i.e. already the skeptical broker disposition base Qwen lacked.

**Finding 1 — void analyses are raw Sites USA DATA exports, not advisory prose.** All 5 sampled
voids were dropped: "raw Sites USA data export… no prose advisory narrative, no recommendation"
(and they're large: 55–111 KB of tables). So the void docs are the *input a broker reads*, not a
written recommendation — they can't directly teach the advisory voice. Reframes their role from
"output gold" to "input data."

**Finding 2 — the investment-memo gold is rich but THIN in unique examples.** A title search shows
the memos cluster into ~5 distinct *deals* (Chandler/Warner-McQueen, 8300 Firestone Downey,
Craig-Rancho LV, Tempe Caffenio, Vallarta Avondale), each **heavily versioned** (a dozen+ Chandler
copies across Sept-2023 → Jul-2025). Unique advisory examples are single digits, not hundreds.

**Refined data plan (D20):**
- **Dedup memo versions** by deal (don't train on 12 Chandler copies → overfit) and pick the
  latest/cleanest per deal. (curate.py needs a dedup pass.)
- **Section-slice** each rich memo into multiple human-gold pairs (full memo + per-section:
  objective, comps, recommendation) → multiplies ~8 deals into ~40–80 pairs, all human voice.
- **Augment only if needed:** use the human memos as voice exemplars to *steer a teacher* (Claude)
  to generate advisory recommendations on the abundant void DATA → many pairs matching production
  inputs + the broker voice. Measure-first: try the human-gold LoRA, augment if the held-out
  advisory score doesn't move. (A nuanced revision of D13: for voids we have no human output, so
  some voice-steered generation is the pragmatic path.)

**Redaction:** scrubbed the real PII — client/sponsor identity (ASÍ), the investor name (Cedric),
and exact street addresses all gone. What remained: city names (Chandler/Tempe — general market
geography, useful to keep) and a *public* tenant brand (Caffenio/FEMSA). Low sensitivity; final
aggressiveness on tenant brands is an owner call.

**Count + approach (owner-confirmed 2026-06-15):** walking the "Investment Memo(s)" folders adds
one deal (337 W Mariposa Rd) → **~6 distinct investment-memo deals total**. Owner confirms: **no
prose void conclusions exist** (the Sites USA export is always the deliverable), and **redact
client/sponsor identity** (cities + public tenant brands may stay). So the human advisory gold is
~6 rich memos — too few to train directly. **Approach = human-gold-first (measure before importing
teacher output):**
- **Phase 3a:** dedup to the ~6 deals (latest/cleanest version each) + **section-slice** each memo
  into ~5–8 pairs (full memo + per-section: recommendation, trade-area, comps, pro forma) → ~40
  human-voice pairs. Train LoRA, measure on the held-out advisory eval.
- **Phase 3b (only if 3a underfits):** add **voice-steered teacher** pairs — Claude few-shot-prompted
  with the real memos, writing recommendations over the abundant void DATA → ~100+ pairs matching
  production inputs + the house voice. The human memos stay the voice anchor.
This protects the moat (the broker voice) and only spends teacher tokens if the eval says we must.

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

- **2026-06-15 — 🚀 First LoRA fine-tune LAUNCHED on Together (job `ft-c0060f33-bf9f`).** Qwen2.5-7B
  + the 29-pair human-gold advisory dataset, 4 epochs, LoRA (`train_on_inputs=auto`). The earlier
  402s were credit-purchase *propagation lag* to Together's training-billing service, not a real
  shortfall ($20 purchased credits). Training now; next: download adapter → deploy on the Baseten L4
  (vLLM `--enable-lora`) → held-out advisory eval vs base Qwen 2.80 / Haiku 4.35.
- **2026-06-15 — Pivot: train on Together AI (Baseten Training inaccessible to the account).**
  Owner couldn't get Baseten Training enabled (403), so D21 pivots: **train the LoRA on Together
  AI, still serve the adapter on the existing Baseten L4** (train-venue ≠ serve-venue, by design).
  Wrote `finetune/together_submit.py` (upload → LoRA create → status → download). Our dataset is
  already Together's chat-JSONL format, so nothing about the data changes; `train_on_inputs="auto"`
  trains only on the advisory outputs. Same hyperparameters as the Axolotl config. Blocked on the
  owner's Together API key to run; after training we download the adapter and deploy it on the L4.
- **2026-06-15 — Phase 3 launch BLOCKED: Baseten Training not authorized (403).** Wrote +
  validated the training config (`finetune/training/`: `config.py` truss_train job, Axolotl
  `qwen_lora.yaml`, `run.sh`), placed the dataset (29 train / 7 held-out), redaction clean.
  But `truss train push` → **403 "not authorized for Baseten training"** (team `wp7ndew`).
  Inference works on this account; **Training is a separate entitlement it lacks.** The
  Axolotl YAML is venue-agnostic, so the fork is: (a) request Baseten Training access → push
  the ready config, or (b) fallback — train via Together AI API (~pennies) or rented A100 +
  Unsloth using the same `qwen_lora.yaml`, then deploy the adapter on the existing L4 (D21
  fallbacks). Adapter deploys to Baseten regardless of where it's trained. Awaiting owner choice.
- **2026-06-15 — Phase 3a human-gold dataset built (`finetune/build_memo_dataset.py`).**
  Section-slicer produced **34 human-gold training pairs from 5 deals** (Chandler, Craig-Rancho,
  Downey, Nogales/Mariposa, Vallarta-Avondale), 27 train / 7 held-out — the whole **Chandler deal
  held out** for leakage-free eval. **Redaction clean** (0 client-identity leaks in train.jsonl).
  Tempe Caffenio transient-failed (BYOKError) → recoverable, would make 6 deals/~41 pairs. Pairs
  read like real broker memos (calibrated "GO", preserved underwriting, grounded comps). Dataset is
  git-ignored (derived + client-derived). Next: recover Tempe → training-venue cost (D7) → LoRA (bf16).
- **2026-06-15 — Real-doc validation: two plan-changing findings (§4.9, D20).** Ran the pipeline
  on 9 real ASI docs. Investment memos → excellent advisory pairs (calibrated voice). But (1) void
  analyses are raw Sites USA data exports, not advisory prose (all dropped) → input data, not output
  gold; and (2) the memo gold is ~5 distinct deals, heavily versioned → unique examples are single
  digits. Plan: dedup + section-slice memos (~40–80 human pairs), augment with voice-steered teacher
  pairs on void data only if needed. Redaction scrubbed real PII (client/investor/address); cities +
  public tenant brands remained. Open Qs to owner: more distinct memos? prose void conclusions?
- **2026-06-15 — Phase 2 curation pipeline built + validated (§4.8, D19).**
  `backend/finetune/curate.py` — LLM-assisted curation (classify, quality-gate, reconstruct the
  advisory input, preserve the human output, **redact all PII**). Owner confirmed redact-all; corpus
  being ported to Google Drive. Validated end-to-end on synthetic docs (junk dropped, memo kept,
  planted PII fully redacted). No hand-labelling. Awaiting the real corpus → validate ~10 → run drive.
- **2026-06-15 — Plan review (Gaps 1–7) integrated; roadmap revised.** Gap-1 diagnosis done
  (§4.6): base Qwen's advisory failures are voice/disposition + calibration (positivity bias),
  **no hard reasoning ceiling → LoRA is the right tool** (D12). Gap-2 data strategy chosen
  (§4.7, D13): human-memo gold set + inputs templated to the live format, real-source
  reconstruction where it exists, teacher data for input augmentation only. New decisions
  D12–D18 (held-out eval D14, bf16-then-quantize D15, smart+workhorse arch D16, business-hours
  serving policy D17, 14B-FP8 contingency D18). Phase map rewritten: diagnosis gate (1.5),
  eval hardening ahead of training (2), quantization as its own phase (4). No training code yet.
- **2026-06-15 — Controlled benchmark complete (§4.5). Phase 0 + Phase 1 done.** Qwen2.5-7B
  on the Baseten L4: tool-calling **92.9%** (beats Haiku's 85.7%, clears the bar; serving
  control eliminated the router flakiness), warm TTFT **~0.9 s**, but advisory quality
  **2.80/5 vs Haiku 4.35** (0/4 send-to-client). Verdict: don't ship base Qwen — the advisory
  gap is real and is the fine-tune's job. **Next: Phase 2, fine-tuning data prep (OneDrive).**
- **2026-06-15 — Qwen2.5-7B deployed to Baseten L4 (building).** `truss push` of the
  config-only vLLM Truss (`backend/baseten/qwen25-7b-instruct/`). Model `3m50kp6w`,
  endpoint `https://model-3m50kp6w.api.baseten.co`; scale-to-zero confirmed (min 0 / max 1,
  one L4). Controlled serving stack (single `--tool-call-parser hermes`) replaces the flaky
  HF router. Next: on ACTIVE, re-run BOTH eval dimensions + measure cold-start / warm TTFT.
- **2026-06-15 — Advisory-quality eval added (§4.4, D11).** New LLM-as-judge dimension
  measures the *advisor*, not just the tool-picker (property→client-fit reasoning + go/no-go).
  Haiku baseline 4.35/5 (3/4 pass); weakest on groundedness; the investment-memo scenario is
  the one that fails the bar — validating the void/memo fine-tune target. Baseten key received;
  controlled deploy is the next step.
- **2026-06-15 — Candidate smoke-tested on HF router (§4.3).** Qwen2.5-7B-Instruct picks the
  correct tool on every cleanly-served case and even passes the `draft_outreach` case Haiku
  failed; its only genuine miss (over-eager on a vague prompt) is shared with Haiku. Headline
  router scores (81.5%/66.7%) were depressed by non-deterministic `malformed`/rate-limit
  errors — an instrument problem, not the model. Verdict: parity-or-better on tool-calling;
  trustworthy benchmark needs controlled serving → **Baseten next** (needs Baseten key).
- **2026-06-15 — Candidate model selected + real eval material found.** Primary candidate
  `Qwen/Qwen2.5-7B-Instruct` (D10) via a 4-point selection rubric (§2.1). Vetted two
  owner-raised models and rejected both as the self-host default: GLM-5.1 (744B MoE — ~15–30×
  too big for an L4) and RomboTiesTest-7B (leaderboard merge — measures the wrong thing +
  tool-template risk). Found real dogfooding prompts in `spacefit.db` (§4.2) to fold into the
  eval. Next: HF-router eval of the candidate (needs an HF token).
- **2026-06-15 — Phase 0 baseline measured (§4.1).** Ran the harness live against
  `claude-haiku-4-5`: routing 100%, tool-call 85.7%, overall 92.6%. Confirmed the
  stale `anthropic_model` default 404s. Locked D9 (gate = parity-or-better vs
  baseline). Two real system gaps surfaced (outreach tool not triggering; scout
  over-calling on vague input). Remaining Phase 0: stale-ID fix; Baseten smoke test.
- **2026-06-15 — Phase 0 started: eval harness landed (`backend/evals/`).** The
  instrument that lets us prove "good enough" before switching. Built:
  - `grade.py` — pure-stdlib grading (routing set-match; tool-call = right tool +
    schema-valid, non-placeholder args; abstain cases). Verifiable offline
    (`python evals/grade.py`).
  - `harness.py` — drives the **real** `app.llm` path (`plan_workflow` /
    `call_specialist`); provider-agnostic via `EVAL_*` env vars, so the same suite
    scores Anthropic / Gemini / Baseten on equal footing.
  - `run_eval.py` — CLI; writes timestamped JSON+MD scorecards; exits non-zero
    below the 90% tool-call bar (CI-gateable later).
  - Seed datasets: 13 routing + 14 tool cases (incl. 2 abstain), grounded in the
    real tool schemas + routing patterns. `tests/test_evals.py` unit-tests the
    grader offline.
  - **Verified here (no deps/keys needed):** grader self-check passes; datasets
    parse; every tool case is satisfiable (expected tool ∈ specialist allowlist);
    all modules compile. **Not yet run against a live model** — needs
    `uv pip install -e .` + an API key.
  - Remaining Phase 0: (a) run the baseline scorecard against the current models;
    (b) verify/fix the stale Anthropic model IDs so that baseline is real;
    (c) zero-code Baseten smoke test (needs Baseten API key).
- **2026-06-14** — Orientation complete. Baseline architecture documented (§1).
  Kickoff decisions locked (§2, D1–D8). Phase map drafted (§3). Doc created. No code
  changes yet. Next: owner green-light on the phase map, then execute Phase 0.
