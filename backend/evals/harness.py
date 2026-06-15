"""Model driver for the migration eval harness.

Runs the eval cases against a model **through the real ``app.llm`` abstraction**
— the same ``plan_workflow`` and ``call_specialist`` code paths the live chat
uses. That's the point: whatever we measure here is what production would see.

Provider-agnostic. The model under test is chosen entirely by environment
variables, so the identical eval scores Anthropic, Gemini, a Baseten endpoint,
or any OpenAI-compatible server on equal footing:

    EVAL_PROVIDER   anthropic | openai | google | deepseek | huggingface | openai_compatible
    EVAL_MODEL      the model id to send (e.g. "claude-haiku-4-5", "Qwen/Qwen2.5-7B-Instruct")
    EVAL_API_KEY    key for that provider/endpoint
    EVAL_BASE_URL   (openai_compatible only) the endpoint base url, e.g. a Baseten deploy

Requires the backend deps installed (``uv pip install -e .``) and a reachable
model. The grading logic it calls lives in ``grade.py`` and is dependency-free.
"""

from __future__ import annotations

import os

from evals.grade import (
    CaseResult,
    RoutingCase,
    ToolCase,
    grade_routing,
    grade_tool_call,
)


def build_resolved_llm_from_env():
    """Construct a ``ResolvedLLM`` for the model under test from env vars.

    ``is_byok=True`` so the call routes through this explicit client and never
    touches platform token accounting — the harness is a measurement tool, not
    a billed user.
    """
    from app.llm.client import get_or_create_client
    from app.services.user_llm import ResolvedLLM

    provider = os.environ.get("EVAL_PROVIDER", "anthropic")
    model = os.environ.get("EVAL_MODEL")
    if not model:
        raise SystemExit("EVAL_MODEL is required (the model id to evaluate).")
    api_key = os.environ.get("EVAL_API_KEY", "")
    base_url = os.environ.get("EVAL_BASE_URL", "")

    client = get_or_create_client(provider, api_key, base_url)
    return ResolvedLLM(
        client=client,
        model=model,
        provider=provider,
        is_byok=True,
    )


def _routing_context(flags: dict) -> dict | None:
    """Translate the dataset's readable context flags into the shape
    ``plan_workflow`` actually inspects."""
    if not flags:
        return None
    ctx: dict = {}
    if flags.get("document_context"):
        # plan_workflow keys off an address + available_spaces to decide it can
        # skip the discovery (scout) step.
        ctx["document_context"] = {
            "property_address": "100 Greyrock Pl, Stamford, CT",
            "available_spaces": [{"suite_number": "A1"}],
        }
    return ctx or None


async def run_routing_cases(cases: list[RoutingCase], resolved) -> list[CaseResult]:
    from app.services.orchestrator import plan_workflow

    results: list[CaseResult] = []
    for case in cases:
        try:
            predicted = await plan_workflow(
                case.message,
                context=_routing_context(case.context),
                resolved_llm=resolved,
            )
            passed, detail = grade_routing(predicted, case)
        except Exception as e:  # one bad call must not abort the whole run
            passed, detail = False, f"ERROR: {type(e).__name__}: {e}"
        results.append(CaseResult(id=case.id, passed=passed, detail=detail, kind="routing"))
    return results


async def run_tool_cases(cases: list[ToolCase], resolved) -> list[CaseResult]:
    from app.services.orchestrator import call_specialist

    results: list[CaseResult] = []
    for case in cases:
        try:
            result = await call_specialist(
                name=case.specialist,
                messages=[{"role": "user", "content": case.message}],
                resolved_llm=resolved,
                project_context=case.context.get("project_context"),
            )
            passed, detail = grade_tool_call(result.get("tool_calls", []), case)
        except Exception as e:
            passed, detail = False, f"ERROR: {type(e).__name__}: {e}"
        results.append(CaseResult(id=case.id, passed=passed, detail=detail, kind="tool_call"))
    return results
