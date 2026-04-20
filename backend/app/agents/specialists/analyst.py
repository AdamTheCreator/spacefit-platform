from app.agents.specialists.base import SpecialistConfig
from app.agents.prompts.analyst import ANALYST_SYSTEM_PROMPT

ANALYST = SpecialistConfig(
    name="analyst",
    system_prompt=ANALYST_SYSTEM_PROMPT,
    allowed_tools=["demographics_analysis", "void_analysis", "costar_import", "placer_import"],
    default_model_tier="deep",
    description="Scores trade area fit, reads CoStar and Placer imports, produces quantitative analysis.",
)
