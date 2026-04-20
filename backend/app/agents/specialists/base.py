"""Specialist agents — function-shaped, not class-shaped.

Each specialist is a (system_prompt, tool_names, default_model, runner_fn) tuple.
The orchestrator routes to a specialist by name, which produces a single
LLM response (possibly with tool calls) that the orchestrator either uses
directly or loops back through synthesis.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialistConfig:
    name: str
    system_prompt: str
    allowed_tools: list[str]
    default_model_tier: str  # "fast" | "balanced" | "deep"
    description: str  # shown to orchestrator for routing


# Model tier -> concrete model, respecting BYOK override when available.
# These are verified against the Anthropic API as of 2026-04.
MODEL_TIER_MAP: dict[str, str] = {
    "fast": "claude-haiku-4-5-20251001",
    "balanced": "claude-sonnet-4-20250514",
    "deep": "claude-sonnet-4-20250514",
}


def resolve_model_for_tier(tier: str) -> str:
    """Return the concrete model ID for a tier name."""
    return MODEL_TIER_MAP.get(tier, MODEL_TIER_MAP["balanced"])
