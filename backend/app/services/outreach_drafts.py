"""Outreach draft service — generates email drafts for tenant outreach.

Extracted from agents/outreach.py so it can be called as a tool
without depending on the legacy BaseAgent hierarchy.
"""

import logging
from dataclasses import dataclass

from app.services.email_blast import (
    generate_default_subject,
    generate_void_outreach_body,
    render_template,
)

logger = logging.getLogger(__name__)


@dataclass
class OutreachDraft:
    tenant_name: str
    recipient_email: str | None
    subject: str
    body: str
    rationale: str


async def draft_outreach_emails(
    property_address: str,
    vacancy_description: str,
    target_tenants: list[dict],
    from_name: str = "",
    from_email: str = "",
    property_name: str | None = None,
) -> list[OutreachDraft]:
    """Generate personalized outreach email drafts for a list of target tenants.

    Args:
        property_address: Address of the property with the vacancy.
        vacancy_description: Suite/SF/use type of the vacancy.
        target_tenants: List of dicts with keys: name, contact_email (optional),
            rationale (optional).
        from_name: Sender display name.
        from_email: Sender email address.
        property_name: Optional property name (falls back to address).

    Returns:
        List of OutreachDraft objects ready for user review.
    """
    prop_name = property_name or property_address
    subject_template = generate_default_subject(prop_name)
    body_template = generate_void_outreach_body()

    drafts: list[OutreachDraft] = []
    for tenant in target_tenants[:20]:  # cap at 20
        tenant_name = tenant.get("name", "Tenant")
        contact_email = tenant.get("contact_email")
        rationale = tenant.get("rationale", "")

        subject = render_template(
            subject_template,
            tenant_name=tenant_name,
            property_name=prop_name,
            property_address=property_address,
            user_name=from_name or "Your Name",
            user_email=from_email or "your@email.com",
        )

        body = render_template(
            body_template,
            tenant_name=tenant_name,
            property_name=prop_name,
            property_address=property_address,
            user_name=from_name or "Your Name",
            user_email=from_email or "your@email.com",
        )

        # Append vacancy details to the body
        vacancy_note = (
            f"\n<p><strong>Available Space:</strong> {vacancy_description}</p>"
        )
        body = body.replace("</body>", f"{vacancy_note}\n</body>")

        drafts.append(OutreachDraft(
            tenant_name=tenant_name,
            recipient_email=contact_email,
            subject=subject,
            body=body,
            rationale=rationale,
        ))

    logger.info(
        "Generated %d outreach drafts for %s", len(drafts), property_address,
    )
    return drafts
