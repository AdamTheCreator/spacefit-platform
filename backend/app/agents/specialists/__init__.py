"""Specialist agents — function-shaped, not class-shaped.

Each specialist is a SpecialistConfig with a scoped prompt and tool subset.
The orchestrator routes to specialists by name.
"""

from app.agents.specialists.registry import get_specialist, list_specialists, SPECIALIST_REGISTRY

__all__ = ["get_specialist", "list_specialists", "SPECIALIST_REGISTRY"]
