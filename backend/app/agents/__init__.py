"""Space Goose agents — specialist-based multi-agent orchestration.

The old BaseAgent/OutreachAgent class hierarchy has been removed.
New agents live in agents/specialists/ and use SpecialistConfig.
Outreach email drafting is now in services/outreach_drafts.py.
"""

from app.agents.specialists import get_specialist, list_specialists, SPECIALIST_REGISTRY

__all__ = ["get_specialist", "list_specialists", "SPECIALIST_REGISTRY"]
