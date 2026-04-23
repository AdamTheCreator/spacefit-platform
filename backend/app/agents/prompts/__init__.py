"""Specialist system prompts for the Space Goose multi-agent orchestrator."""

from app.agents.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT
from app.agents.prompts.scout import SCOUT_SYSTEM_PROMPT
from app.agents.prompts.analyst import ANALYST_SYSTEM_PROMPT
from app.agents.prompts.matchmaker import MATCHMAKER_SYSTEM_PROMPT
from app.agents.prompts.outreach import OUTREACH_SYSTEM_PROMPT

__all__ = [
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "SCOUT_SYSTEM_PROMPT",
    "ANALYST_SYSTEM_PROMPT",
    "MATCHMAKER_SYSTEM_PROMPT",
    "OUTREACH_SYSTEM_PROMPT",
]
