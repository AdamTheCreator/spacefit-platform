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
# Platform policy: every tier runs on Claude Haiku 4.5 — the cheapest current
# Claude model ($1/$5 per MTok) — to keep non-BYOK costs minimal. The prior
# "balanced"/"deep" id (claude-sonnet-4-6-20260320) is deprecated and 404s
# (see _ANTHROPIC_DEPRECATED_MODEL_ALIASES in services/user_llm.py). BYOK
# users get stronger models via per-specialist overrides.
MODEL_TIER_MAP: dict[str, str] = {
    "fast": "claude-haiku-4-5",
    "balanced": "claude-haiku-4-5",
    "deep": "claude-haiku-4-5",
}


def resolve_model_for_tier(tier: str) -> str:
    """Return the concrete model ID for a tier name."""
    return MODEL_TIER_MAP.get(tier, MODEL_TIER_MAP["balanced"])
