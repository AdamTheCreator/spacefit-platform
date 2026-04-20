from app.agents.specialists.base import SpecialistConfig
from app.agents.prompts.outreach import OUTREACH_SYSTEM_PROMPT

OUTREACH = SpecialistConfig(
    name="outreach",
    system_prompt=OUTREACH_SYSTEM_PROMPT,
    allowed_tools=["draft_outreach"],
    default_model_tier="balanced",
    description="Drafts personalized outreach emails once candidates are identified.",
)
