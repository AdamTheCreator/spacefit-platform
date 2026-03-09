"""LOI (Letter of Intent) document generator.

Follows the same LLM-powered pattern as investment_memo.py.
Generates structured LOI documents from deal and property data.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.llm import LLMChatMessage, LLMChatRequest, get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class LOITerms:
    """Terms for an LOI."""
    purchase_price: float
    earnest_money: float
    earnest_money_type: str = "flat"  # "flat" or "percentage"
    due_diligence_days: int = 30
    closing_days: int = 60
    financing_contingency: bool = True
    financing_days: int = 45
    inspection_contingency: bool = True
    title_contingency: bool = True
    buyer_entity: str = ""
    buyer_contact_name: str = ""
    buyer_contact_email: str = ""
    additional_terms: str = ""


@dataclass
class LOIResult:
    """Generated LOI output."""
    markdown: str
    structured_data: dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "markdown": self.markdown,
            "structured_data": self.structured_data,
            "generated_at": self.generated_at.isoformat(),
        }


LOI_SYSTEM_PROMPT = """You are a commercial real estate LOI (Letter of Intent) generator.
Generate a professional, clean LOI document based on the provided property and deal information.

The LOI should follow standard CRE acquisition LOI format with these sections:
1. Property Description (address, type, size)
2. Purchase Price and Terms
3. Earnest Money Deposit
4. Due Diligence Period
5. Closing Timeline
6. Financing Contingency (if applicable)
7. Inspection Contingency (if applicable)
8. Title and Survey
9. Buyer Entity Information
10. Confidentiality
11. Non-Binding Nature (standard LOI disclaimer)
12. Expiration (typically 5-7 business days)

Output the LOI in clean markdown format suitable for PDF generation.
Also output a structured JSON summary of key terms.

Respond in this exact JSON format:
{
  "markdown": "# Letter of Intent\\n\\n...",
  "key_terms": {
    "property_address": "...",
    "purchase_price": 0,
    "earnest_money": 0,
    "dd_period_days": 30,
    "closing_days": 60,
    "financing_contingency": true,
    "buyer_entity": "...",
    "expiration_days": 5
  }
}"""


async def generate_loi(
    property_info: dict[str, Any],
    deal_terms: LOITerms,
    template_id: str | None = None,
) -> LOIResult:
    """Generate an LOI document using LLM.

    Args:
        property_info: Property details (address, type, size, asking_price, etc.)
        deal_terms: LOI terms and buyer info
        template_id: Optional template identifier for custom formats

    Returns:
        LOIResult with markdown and structured data
    """
    user_prompt = f"""Generate a Letter of Intent for the following property acquisition:

**Property Information:**
- Address: {property_info.get('address', 'N/A')}, {property_info.get('city', '')}, {property_info.get('state', '')} {property_info.get('zip_code', '')}
- Property Type: {property_info.get('property_type', 'Commercial')}
- Total SF: {property_info.get('total_sf', 'N/A'):,} if isinstance(property_info.get('total_sf'), (int, float)) else 'N/A'
- Asking Price: ${property_info.get('asking_price', 0):,.0f}
- Cap Rate: {property_info.get('cap_rate', 'N/A')}%
- NOI: ${property_info.get('noi', 0):,.0f}

**Proposed Terms:**
- Purchase Price: ${deal_terms.purchase_price:,.0f}
- Earnest Money: ${deal_terms.earnest_money:,.0f} ({deal_terms.earnest_money_type})
- Due Diligence Period: {deal_terms.due_diligence_days} days
- Closing Timeline: {deal_terms.closing_days} days from execution
- Financing Contingency: {"Yes, " + str(deal_terms.financing_days) + " days" if deal_terms.financing_contingency else "No (cash purchase)"}
- Inspection Contingency: {"Yes" if deal_terms.inspection_contingency else "No"}
- Title Contingency: {"Yes" if deal_terms.title_contingency else "No"}

**Buyer Information:**
- Entity: {deal_terms.buyer_entity or 'TBD'}
- Contact: {deal_terms.buyer_contact_name or 'TBD'}
- Email: {deal_terms.buyer_contact_email or 'TBD'}

{f"Additional Terms: {deal_terms.additional_terms}" if deal_terms.additional_terms else ""}

Generate the LOI in the format specified."""

    llm = get_llm_client()
    model = settings.llm_model or settings.anthropic_model

    response = await llm.chat(LLMChatRequest(
        model=model,
        max_tokens=4000,
        system=LOI_SYSTEM_PROMPT,
        messages=[LLMChatMessage(role="user", content=user_prompt)],
    ))

    try:
        # Parse the JSON response
        response_text = response.content
        # Handle potential markdown code blocks in response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(response_text)

        return LOIResult(
            markdown=parsed.get("markdown", ""),
            structured_data=parsed.get("key_terms", {}),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse LOI response: {e}")
        # Fallback: use raw response as markdown
        return LOIResult(
            markdown=response.content,
            structured_data={"error": "Failed to parse structured terms"},
        )
