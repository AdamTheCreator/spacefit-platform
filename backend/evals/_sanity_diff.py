"""Throwaway: base Qwen vs the advisory LoRA on the same advisory case(s),
both served by the SAME Baseten L4 (different `model` field). No judge — this
just confirms the adapter loaded and the voice/disposition actually changed.

    cd backend
    BASETEN_API_KEY=... python -m evals._sanity_diff
"""
import asyncio
import os
import sys
from pathlib import Path

from evals.judge import ADVISORY_SYSTEM, build_candidate_user_prompt, load_advisory_cases
from app.llm.client import get_or_create_client
from app.llm.types import LLMChatMessage, LLMChatRequest

BASE = "https://model-3m50kp6w.api.baseten.co/environments/production/sync/v1"
KEY = os.environ.get("BASETEN_API_KEY", "")
MODELS = ["Qwen/Qwen2.5-7B-Instruct", "spacegoose-advisor"]
N = int(os.environ.get("SANITY_N", "1"))


async def gen(model: str, case) -> str:
    client = get_or_create_client("openai_compatible", KEY, BASE)
    resp = await client.chat(
        LLMChatRequest(
            system=ADVISORY_SYSTEM,
            messages=[LLMChatMessage(role="user", content=build_candidate_user_prompt(case))],
            model=model,
            max_tokens=700,
            temperature=0.3,
        )
    )
    return resp.content


async def main() -> int:
    if not KEY:
        print("set BASETEN_API_KEY", file=sys.stderr)
        return 2
    cases = load_advisory_cases(Path("evals/cases/advisory.jsonl"))[:N]
    for case in cases:
        print("=" * 90)
        print("CASE:", case.id, "—", case.question)
        for model in MODELS:
            print(f"\n---------- {model} ----------")
            try:
                print(await gen(model, case))
            except Exception as e:
                print(f"ERROR: {type(e).__name__}: {e}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
