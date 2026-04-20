from app.agents.specialists.base import SpecialistConfig
from app.agents.prompts.matchmaker import MATCHMAKER_SYSTEM_PROMPT

MATCHMAKER = SpecialistConfig(
    name="matchmaker",
    system_prompt=MATCHMAKER_SYSTEM_PROMPT,
    allowed_tools=["business_search", "void_analysis", "costar_import"],
    default_model_tier="deep",
    description="Produces ranked tenant shortlists for a specific vacancy.",
)
