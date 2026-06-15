"""Eval harness for the model migration (Phase 0).

This package is the *instrument* that lets us prove a smaller open model is
"good enough" before we switch the chat over to it. It is deliberately kept
separate from ``tests/`` because evals hit live models (cost money, are
non-deterministic) and are not part of the CI unit-test gate.

Layout:
  grade.py       Pure-stdlib grading + dataset loading. No app/network deps —
                 verifiable offline (``python evals/grade.py``).
  harness.py     Drives a model through the cases via the real ``app.llm``
                 abstraction. Provider-agnostic (Anthropic / Gemini / Baseten /
                 any OpenAI-compatible endpoint) so the *same* eval scores every
                 candidate on equal footing.
  run_eval.py    CLI entry point. Writes a timestamped scorecard to results/.
  cases/         The eval datasets (JSONL).
  results/       Scorecards (git-ignored; they are per-run, per-model evidence).
"""
