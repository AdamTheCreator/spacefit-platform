# Migration eval harness (Phase 0)

The instrument that lets us **prove a smaller open model is "good enough"
before** we switch the chat over to it. See `../../MIGRATION.md` for the full
project context.

## What it measures

Two capabilities that are load-bearing for the migration — if a small model
fails either, the chat regresses regardless of how good its prose is:

1. **Routing accuracy** — does `plan_workflow` pick the right specialist(s) for
   a user message? Graded on set membership (routing is legitimately fuzzy, so
   each case can list acceptable alternatives).
2. **Tool-call accuracy** — does a specialist call the *expected* tool with
   schema-valid, non-placeholder arguments? **This is the 90% success bar**
   (`run_eval.py` exits non-zero below it, so it can gate CI later). Includes
   *abstain* cases: when there's no concrete address, the right answer is to ask,
   not to call a tool with a fabricated `"the property"` argument.

A third slice — LLM-judged **void/memo quality** — is added in Phase 2 once the
fine-tuning corpus exists. Quality there is comparative (small model vs.
baseline), not pass/fail.

## Why it's structured this way

- **Separate from `tests/`** on purpose: evals hit live models (cost money,
  non-deterministic) and must not run in the CI unit-test gate.
- **`grade.py` is pure stdlib** so the correctness logic is verifiable offline
  (`python evals/grade.py`) and unit-tested without installing the backend
  (`tests/test_evals.py`).
- **`harness.py` drives the real `app.llm` abstraction** — the same
  `plan_workflow` / `call_specialist` code the live chat uses — so what we
  measure is what production would see.
- **Provider-agnostic by env var**: the identical suite scores Anthropic,
  Gemini, a Baseten endpoint, or any OpenAI-compatible server, so candidates are
  compared on equal footing.

## Running it

Offline grader self-check (no deps, no keys, no network):

```bash
cd backend
python evals/grade.py          # prints "self-check: OK"
```

Against a live model (needs `uv pip install -e .` + a key):

```bash
cd backend

# Baseline: the current Anthropic platform default
EVAL_PROVIDER=anthropic EVAL_MODEL=claude-haiku-4-5 EVAL_API_KEY=sk-ant-... \
  python -m evals.run_eval --label baseline-haiku

# Candidate: an open model on a Baseten (OpenAI-compatible) deploy
EVAL_PROVIDER=openai_compatible EVAL_MODEL=Qwen/Qwen2.5-7B-Instruct \
  EVAL_API_KEY=$BASETEN_API_KEY \
  EVAL_BASE_URL=https://model-xxxx.api.baseten.co/environments/production/sync/v1 \
  python -m evals.run_eval --label qwen25-7b-baseten
```

Each run prints per-case PASS/FAIL and writes a JSON + Markdown scorecard to
`results/` (git-ignored). Diff scorecards across models in Phase 6.

## Cases

- `cases/routing.jsonl` — `plan_workflow` routing cases.
- `cases/tool_calls.jsonl` — specialist tool-selection cases (incl. abstain).

These are a **seed set** grounded in the real tool schemas
(`app/services/tools.py`) and routing patterns (`plan_workflow`). Expand them as
real chat traffic arrives — the dataset is the eval's ceiling, so growing it is
ongoing work, not a one-time task. Each line is one case; see `grade.py` for the
field meanings (`RoutingCase`, `ToolCase`).
