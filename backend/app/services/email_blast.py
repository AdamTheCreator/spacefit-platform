"""
Email Blast Service

Handles sending outreach emails to tenants based on void analysis.
Supports multiple email providers (SendGrid, Mailgun, AWS SES, SMTP).

For now, uses a simple SMTP backend. Can be extended to use
transactional email services for better deliverability and tracking.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import asyncio

from app.core.config import settings


@dataclass
class EmailResult:
    """Result of sending an email."""
    success: bool
    recipient_email: str
    message_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None


@dataclass
class CampaignSummary:
    """Summary of a campaign send operation."""
    total_recipients: int
    successful: int
    failed: int
    results: list[EmailResult]


def render_template(
    template: str,
    tenant_name: str,
    property_name: str,
    property_address: str,
    user_name: str,
    user_email: str,
    user_phone: str | None = None,
    **extra_vars: Any,
) -> str:
    """
    Render an email template with variable substitution.

    Supported placeholders:
    - {{tenant_name}} - The tenant's company name
    - {{property_name}} - The property/shopping center name
    - {{property_address}} - The property address
    - {{user_name}} - The sender's name
    - {{user_email}} - The sender's email
    - {{user_phone}} - The sender's phone (optional)
    """
    result = template
    replacements = {
        "{{tenant_name}}": tenant_name,
        "{{property_name}}": property_name,
        "{{property_address}}": property_address,
        "{{user_name}}": user_name,
        "{{user_email}}": user_email,
        "{{user_phone}}": user_phone or "",
    }

    # Add any extra variables
    for key, value in extra_vars.items():
        replacements[f"{{{{{key}}}}}"] = str(value)

    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    from_name: str,
    from_email: str,
    reply_to: str | None = None,
    tracking_id: str | None = None,
    tracking_base_url: str | None = None,
) -> EmailResult:
    """
    Send a single email.

    For production, this should use a transactional email service
    like SendGrid, Mailgun, or AWS SES for better deliverability.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body_html: HTML body content
        from_name: Display name for sender
        from_email: Sender email address
        reply_to: Reply-to address (optional)
        tracking_id: Unique tracking ID for open/click tracking (optional)
        tracking_base_url: Base URL for tracking endpoints (optional)
    """
    # Add tracking if configured
    if tracking_id and tracking_base_url:
        from app.api.tracking import add_tracking_pixel, wrap_links_for_tracking

        body_html = wrap_links_for_tracking(body_html, tracking_id, tracking_base_url)
        body_html = add_tracking_pixel(body_html, tracking_id, tracking_base_url)

    # Check if email is configured
    if not settings.smtp_host:
        # Development mode - just log the email
        print(f"[EMAIL] Would send to {to_email}:")
        print(f"  Subject: {subject}")
        print(f"  From: {from_name} <{from_email}>")
        print(f"  Body preview: {body_html[:200]}...")

        return EmailResult(
            success=True,
            recipient_email=to_email,
            message_id=f"dev-{datetime.now().timestamp()}",
            sent_at=datetime.utcnow(),
        )

    # Production mode - send via SMTP
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to

        # Add HTML body
        html_part = MIMEText(body_html, "html")
        msg.attach(html_part)

        # Send via SMTP (in a thread to avoid blocking)
        def send_sync():
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)

        await asyncio.get_event_loop().run_in_executor(None, send_sync)

        return EmailResult(
            success=True,
            recipient_email=to_email,
            message_id=msg.get("Message-ID"),
            sent_at=datetime.utcnow(),
        )

    except Exception as e:
        return EmailResult(
            success=False,
            recipient_email=to_email,
            error=str(e),
        )


async def send_campaign_emails(
    recipients: list[dict],
    subject_template: str,
    body_template: str,
    property_name: str,
    property_address: str,
    from_name: str,
    from_email: str,
    reply_to: str | None = None,
    batch_size: int = 10,
    delay_between_batches: float = 1.0,
) -> CampaignSummary:
    """
    Send emails to a list of recipients.

    Args:
        recipients: List of dicts with tenant_name, contact_email, etc.
        subject_template: Subject line template with placeholders
        body_template: Email body template with placeholders
        property_name: Property name for substitution
        property_address: Property address for substitution
        from_name: Sender name
        from_email: Sender email
        reply_to: Reply-to address (optional)
        batch_size: Number of emails to send in parallel
        delay_between_batches: Seconds to wait between batches

    Returns:
        CampaignSummary with results
    """
    results: list[EmailResult] = []

    # Process in batches to avoid overwhelming the email server
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i + batch_size]

        # Send batch in parallel
        batch_tasks = []
        for recipient in batch:
            # Render templates for this recipient
            subject = render_template(
                subject_template,
                tenant_name=recipient["tenant_name"],
                property_name=property_name,
                property_address=property_address,
                user_name=from_name,
                user_email=from_email,
            )

            body = render_template(
                body_template,
                tenant_name=recipient["tenant_name"],
                property_name=property_name,
                property_address=property_address,
                user_name=from_name,
                user_email=from_email,
            )

            task = send_email(
                to_email=recipient["contact_email"],
                subject=subject,
                body_html=body,
                from_name=from_name,
                from_email=from_email,
                reply_to=reply_to,
            )
            batch_tasks.append(task)

        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)

        # Delay between batches (except for last batch)
        if i + batch_size < len(recipients):
            await asyncio.sleep(delay_between_batches)

    # Calculate summary
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    return CampaignSummary(
        total_recipients=len(recipients),
        successful=successful,
        failed=failed,
        results=results,
    )


def generate_default_subject(property_name: str) -> str:
    """Generate a default email subject line."""
    return f"Retail Opportunity at {property_name}"


def generate_default_body(include_signature: bool = True) -> str:
    """
    Generate a default email body template.

    Uses professional tone appropriate for commercial real estate outreach.
    """
    body = """<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">

<p>Hi {{tenant_name}} Real Estate Team,</p>

<p>I'm reaching out regarding a retail opportunity that may align with your expansion criteria.</p>

<p><strong>Property:</strong> {{property_name}}<br>
<strong>Location:</strong> {{property_address}}</p>

<p>Based on our market analysis, this location shows strong potential for your brand with favorable demographics, traffic patterns, and limited competition in the immediate trade area.</p>

<p>I'd welcome the opportunity to share more details about this site and discuss how it might fit your growth plans. Would you have time for a brief call this week?</p>

<p>Looking forward to connecting.</p>
"""

    if include_signature:
        body += """
<p>Best regards,<br>
{{user_name}}<br>
{{user_email}}<br>
{{user_phone}}</p>
"""

    body += """
</body>
</html>"""

    return body


def generate_void_outreach_body() -> str:
    """
    Generate an email body specifically for void analysis outreach.

    More detailed template that emphasizes the market opportunity.
    """
    return """<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">

<p>Hi {{tenant_name}} Real Estate Team,</p>

<p>I wanted to bring to your attention a compelling retail opportunity in a market where {{tenant_name}} currently has limited presence.</p>

<p><strong>Property:</strong> {{property_name}}<br>
<strong>Location:</strong> {{property_address}}</p>

<p>Our analysis indicates this location represents a potential void for your brand, with strong market fundamentals including:</p>
<ul>
  <li>Favorable demographic profile matching your target customer</li>
  <li>High traffic counts and visibility</li>
  <li>Limited direct competition in the immediate trade area</li>
  <li>Strong co-tenancy with complementary retailers</li>
</ul>

<p>I have detailed market data, demographic analysis, and site specifications available to share. Would you be open to a brief conversation to explore whether this opportunity aligns with your expansion strategy?</p>

<p>I'm happy to work around your schedule. Please let me know what works best.</p>

<p>Best regards,<br>
{{user_name}}<br>
{{user_email}}<br>
{{user_phone}}</p>

</body>
</html>"""
