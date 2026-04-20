"""Specialist registry — name -> SpecialistConfig lookup."""

from app.agents.specialists.base import SpecialistConfig
from app.agents.specialists.scout import SCOUT
from app.agents.specialists.analyst import ANALYST
from app.agents.specialists.matchmaker import MATCHMAKER
from app.agents.specialists.outreach import OUTREACH

SPECIALIST_REGISTRY: dict[str, SpecialistConfig] = {
    "scout": SCOUT,
    "analyst": ANALYST,
    "matchmaker": MATCHMAKER,
    "outreach": OUTREACH,
}


def get_specialist(name: str) -> SpecialistConfig:
    """Get a specialist config by name. Raises KeyError if not found."""
    spec = SPECIALIST_REGISTRY.get(name)
    if spec is None:
        raise KeyError(f"Unknown specialist: {name!r}. Available: {list(SPECIALIST_REGISTRY.keys())}")
    return spec


def list_specialists() -> list[SpecialistConfig]:
    """Return all registered specialists."""
    return list(SPECIALIST_REGISTRY.values())
