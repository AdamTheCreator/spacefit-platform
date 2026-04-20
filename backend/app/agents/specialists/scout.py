from app.agents.specialists.base import SpecialistConfig
from app.agents.prompts.scout import SCOUT_SYSTEM_PROMPT

SCOUT = SpecialistConfig(
    name="scout",
    system_prompt=SCOUT_SYSTEM_PROMPT,
    allowed_tools=["business_search", "tenant_roster", "demographics_analysis"],
    default_model_tier="fast",
    description="Finds properties, nearby businesses, and site characteristics. Fast, broad discovery.",
)
