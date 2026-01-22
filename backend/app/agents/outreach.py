"""
Outreach Agent

Handles email outreach campaigns based on void analysis results.
This is the "game changer" feature that automates manual spreadsheet + mail merge workflow.

Capabilities:
- Create campaigns from void analysis results
- Preview email content before sending
- Send campaigns via Gmail API or SMTP
- Report on campaign status
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.base import BaseAgent
from app.core.config import settings
from app.db.models.outreach import (
    CampaignStatus,
    OutreachCampaign,
    OutreachRecipient,
    RecipientStatus,
)
from app.models.chat import AgentType, Message, MessageRole
from app.services.email_blast import (
    render_template,
    generate_default_subject,
    generate_void_outreach_body,
    EmailResult,
)


class OutreachAgent(BaseAgent):
    """Agent for managing email outreach campaigns."""

    agent_type = AgentType.OUTREACH
    name = "Outreach Agent"
    description = "Creates and sends email outreach campaigns to tenants identified by void analysis"

    def __init__(self, db: AsyncSession | None = None):
        super().__init__()
        self.db = db

    async def can_handle(self, task: str) -> bool:
        """Can handle outreach-related tasks."""
        task_lower = task.lower()
        keywords = [
            "outreach",
            "email",
            "blast",
            "send email",
            "contact tenant",
            "reach out",
            "campaign",
            "mail merge",
        ]
        return any(word in task_lower for word in keywords)

    async def execute(self, task: str, context: dict[str, Any]) -> Message:
        """
        Execute outreach-related tasks.

        Supported tasks:
        - create_campaign: Create a new campaign from void analysis
        - preview_email: Preview email for a recipient
        - send_campaign: Send emails to all recipients
        - campaign_status: Get status of a campaign
        """
        action = context.get("action", "create_campaign")

        if action == "create_campaign":
            return await self._create_campaign(context)
        elif action == "preview_email":
            return await self._preview_email(context)
        elif action == "send_campaign":
            return await self._send_campaign(context)
        elif action == "campaign_status":
            return await self._campaign_status(context)
        else:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=f"Unknown outreach action: {action}",
            )

    async def _create_campaign(self, context: dict[str, Any]) -> Message:
        """
        Create a new outreach campaign from void analysis results.

        Context:
        - void_results: List of void opportunities with tenant info
        - property_address: Address of the property
        - property_name: Name of the property (optional)
        - user_id: User ID
        - from_name: Sender name
        - from_email: Sender email
        """
        void_results = context.get("void_results", [])
        property_address = context.get("property_address", "")
        property_name = context.get("property_name", property_address)
        user_id = context.get("user_id")
        from_name = context.get("from_name", "")
        from_email = context.get("from_email", "")

        if not void_results:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=(
                    "**No void analysis results found**\n\n"
                    "To create an outreach campaign, I need void analysis results with "
                    "tenant information. Please run a void analysis first."
                ),
            )

        # Filter to only tenants with contact emails
        contactable_tenants = [
            t for t in void_results if t.get("contact_email")
        ]

        if not contactable_tenants:
            # List tenants without contacts
            tenant_names = [t.get("tenant_name", "Unknown") for t in void_results[:10]]
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=(
                    "**No tenant contacts found**\n\n"
                    "The void analysis identified opportunities, but I don't have "
                    "contact emails for these tenants yet:\n\n"
                    + "\n".join(f"- {name}" for name in tenant_names)
                    + "\n\nI can help you find contact information for these tenants. "
                    "Would you like me to search for their real estate contacts?"
                ),
            )

        # Create campaign (in-memory for now, will persist if DB available)
        campaign_id = str(uuid.uuid4())
        recipients_summary = []

        for tenant in contactable_tenants[:20]:  # Limit to 20 for now
            recipients_summary.append({
                "tenant_name": tenant.get("tenant_name", "Unknown"),
                "contact_email": tenant.get("contact_email"),
                "category": tenant.get("category", ""),
                "match_score": tenant.get("match_score", 0),
            })

        # Generate preview
        preview_tenant = contactable_tenants[0]
        preview_body = render_template(
            generate_void_outreach_body(),
            tenant_name=preview_tenant.get("tenant_name", "Tenant"),
            property_name=property_name,
            property_address=property_address,
            user_name=from_name or "Your Name",
            user_email=from_email or "your@email.com",
        )

        # Build response
        lines = [
            "## Outreach Campaign Ready",
            "",
            f"**Property:** {property_name}",
            f"**Address:** {property_address}",
            "",
            f"### Recipients ({len(contactable_tenants)} tenants with contacts)",
            "",
            "| Tenant | Category | Match Score |",
            "|--------|----------|-------------|",
        ]

        for r in recipients_summary[:10]:
            score = f"{r['match_score']:.0f}%" if r.get("match_score") else "-"
            lines.append(f"| {r['tenant_name']} | {r['category']} | {score} |")

        if len(recipients_summary) > 10:
            lines.append(f"| ... and {len(recipients_summary) - 10} more | | |")

        lines.extend([
            "",
            "### Email Preview",
            "",
            "**Subject:** " + generate_default_subject(property_name),
            "",
            "---",
            "",
            "*Preview of email to first recipient:*",
            "",
            preview_body[:500] + "..." if len(preview_body) > 500 else preview_body,
            "",
            "---",
            "",
            "**Ready to send?** Reply with:",
            "- \"Send campaign\" to send all emails now",
            "- \"Edit template\" to customize the email",
            "- \"Remove [tenant]\" to exclude specific recipients",
        ])

        # Store campaign data in context for follow-up
        campaign_data = {
            "campaign_id": campaign_id,
            "property_address": property_address,
            "property_name": property_name,
            "recipients": recipients_summary,
            "subject": generate_default_subject(property_name),
            "body_template": generate_void_outreach_body(),
            "from_name": from_name,
            "from_email": from_email,
        }

        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content="\n".join(lines),
            # Store campaign data for persistence
        )

    async def _preview_email(self, context: dict[str, Any]) -> Message:
        """Preview an email for a specific recipient."""
        tenant_name = context.get("tenant_name", "Tenant")
        property_name = context.get("property_name", "Property")
        property_address = context.get("property_address", "")
        subject_template = context.get("subject", generate_default_subject(property_name))
        body_template = context.get("body_template", generate_void_outreach_body())
        from_name = context.get("from_name", "Your Name")
        from_email = context.get("from_email", "your@email.com")

        subject = render_template(
            subject_template,
            tenant_name=tenant_name,
            property_name=property_name,
            property_address=property_address,
            user_name=from_name,
            user_email=from_email,
        )

        body = render_template(
            body_template,
            tenant_name=tenant_name,
            property_name=property_name,
            property_address=property_address,
            user_name=from_name,
            user_email=from_email,
        )

        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content=(
                f"## Email Preview\n\n"
                f"**To:** {tenant_name} Real Estate Team\n"
                f"**From:** {from_name} <{from_email}>\n"
                f"**Subject:** {subject}\n\n"
                f"---\n\n{body}"
            ),
        )

    async def _send_campaign(self, context: dict[str, Any]) -> Message:
        """
        Send a campaign to all recipients.

        This triggers the actual email sending process.
        """
        campaign_id = context.get("campaign_id")
        recipients = context.get("recipients", [])
        property_name = context.get("property_name", "")
        property_address = context.get("property_address", "")
        subject = context.get("subject", "")
        body_template = context.get("body_template", "")
        from_name = context.get("from_name", "")
        from_email = context.get("from_email", "")
        gmail_tokens = context.get("gmail_tokens")  # For Gmail API
        user_id = context.get("user_id")

        if not recipients:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content="No recipients found for this campaign.",
            )

        # Check email configuration
        has_gmail = gmail_tokens is not None
        has_smtp = bool(settings.smtp_host)

        if not has_gmail and not has_smtp:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=(
                    "**Email not configured**\n\n"
                    "To send outreach emails, please configure either:\n\n"
                    "1. **Gmail API** (Recommended)\n"
                    "   - Go to Settings > Connections\n"
                    "   - Connect your Gmail account\n\n"
                    "2. **SMTP Server**\n"
                    "   - Configure SMTP settings in your .env file\n\n"
                    "Would you like help setting up email?"
                ),
            )

        # Send emails
        results: list[EmailResult] = []
        successful = 0
        failed = 0

        if has_gmail:
            # Use Gmail API
            from app.services.gmail import GmailService, GmailTokens

            gmail_service = GmailService(GmailTokens.from_dict(gmail_tokens))

            for recipient in recipients:
                tenant_name = recipient.get("tenant_name", "")
                contact_email = recipient.get("contact_email", "")

                if not contact_email:
                    continue

                # Render email
                rendered_subject = render_template(
                    subject,
                    tenant_name=tenant_name,
                    property_name=property_name,
                    property_address=property_address,
                    user_name=from_name,
                    user_email=from_email,
                )
                rendered_body = render_template(
                    body_template,
                    tenant_name=tenant_name,
                    property_name=property_name,
                    property_address=property_address,
                    user_name=from_name,
                    user_email=from_email,
                )

                result = await gmail_service.send_email_async(
                    to_email=contact_email,
                    subject=rendered_subject,
                    body_html=rendered_body,
                    from_name=from_name,
                )

                if result.success:
                    successful += 1
                else:
                    failed += 1

        else:
            # Use SMTP
            from app.services.email_blast import send_campaign_emails

            recipients_data = [
                {
                    "tenant_name": r.get("tenant_name", ""),
                    "contact_email": r.get("contact_email", ""),
                }
                for r in recipients
                if r.get("contact_email")
            ]

            summary = await send_campaign_emails(
                recipients=recipients_data,
                subject_template=subject,
                body_template=body_template,
                property_name=property_name,
                property_address=property_address,
                from_name=from_name,
                from_email=from_email,
            )

            successful = summary.successful
            failed = summary.failed

        # Build response
        total = successful + failed
        success_rate = (successful / total * 100) if total > 0 else 0

        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content=(
                f"## Campaign Sent!\n\n"
                f"**Property:** {property_name}\n\n"
                f"### Results\n"
                f"- **Total Sent:** {successful} emails\n"
                f"- **Failed:** {failed} emails\n"
                f"- **Success Rate:** {success_rate:.0f}%\n\n"
                f"I'll notify you when recipients open or respond to your emails.\n\n"
                f"*View campaign details at [Outreach](/outreach)*"
            ),
        )

    async def _campaign_status(self, context: dict[str, Any]) -> Message:
        """Get status of a campaign."""
        campaign_id = context.get("campaign_id")

        if not self.db:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content="Database not available for campaign lookup.",
            )

        # Look up campaign
        result = await self.db.execute(
            select(OutreachCampaign)
            .options(selectinload(OutreachCampaign.recipients))
            .where(OutreachCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=f"Campaign {campaign_id} not found.",
            )

        # Calculate stats
        opened_pct = (
            (campaign.opened_count / campaign.sent_count * 100)
            if campaign.sent_count > 0
            else 0
        )
        clicked_pct = (
            (campaign.clicked_count / campaign.sent_count * 100)
            if campaign.sent_count > 0
            else 0
        )

        # Get recent opens
        recent_opens = [
            r for r in campaign.recipients if r.opened_at
        ][:5]

        lines = [
            f"## Campaign: {campaign.name}",
            "",
            f"**Property:** {campaign.property_name or campaign.property_address}",
            f"**Status:** {campaign.status}",
            f"**Sent:** {campaign.sent_at.strftime('%Y-%m-%d %H:%M') if campaign.sent_at else 'Not sent'}",
            "",
            "### Performance",
            f"- **Sent:** {campaign.sent_count} / {campaign.total_recipients}",
            f"- **Opened:** {campaign.opened_count} ({opened_pct:.0f}%)",
            f"- **Clicked:** {campaign.clicked_count} ({clicked_pct:.0f}%)",
            f"- **Replied:** {campaign.replied_count}",
            f"- **Bounced:** {campaign.bounced_count}",
        ]

        if recent_opens:
            lines.extend([
                "",
                "### Recent Opens",
            ])
            for r in recent_opens:
                lines.append(
                    f"- {r.tenant_name} - {r.opened_at.strftime('%Y-%m-%d %H:%M')}"
                )

        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content="\n".join(lines),
        )


async def create_outreach_from_void(
    void_results: list[dict],
    property_address: str,
    property_name: str | None,
    user_id: str,
    from_name: str,
    from_email: str,
    db: AsyncSession | None = None,
) -> Message:
    """
    Convenience function to create outreach from void analysis.

    Called by the orchestrator when user asks to reach out after void analysis.
    """
    agent = OutreachAgent(db=db)
    return await agent.execute(
        "create_campaign",
        {
            "action": "create_campaign",
            "void_results": void_results,
            "property_address": property_address,
            "property_name": property_name,
            "user_id": user_id,
            "from_name": from_name,
            "from_email": from_email,
        },
    )
