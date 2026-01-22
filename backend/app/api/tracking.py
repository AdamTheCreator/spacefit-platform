"""
Email Tracking API Endpoints

Handles tracking pixels for open tracking and link wrapping for click tracking.
These endpoints are called by email clients when emails are opened/clicked.
"""

import base64
import hashlib
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.outreach import (
    OutreachCampaign,
    OutreachRecipient,
    RecipientStatus,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])

# 1x1 transparent GIF for tracking pixel
TRACKING_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/open/{tracking_id}")
async def track_open(
    tracking_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """
    Track email open via tracking pixel.

    This endpoint returns a 1x1 transparent GIF and records the open event.
    Called when an email client loads the tracking pixel image.
    """
    now = datetime.now(timezone.utc)

    # Find recipient by tracking ID
    result = await db.execute(
        select(OutreachRecipient).where(OutreachRecipient.tracking_id == tracking_id)
    )
    recipient = result.scalar_one_or_none()

    if recipient:
        # Only update if not already opened (track first open)
        if recipient.status in [RecipientStatus.SENT.value, RecipientStatus.DELIVERED.value]:
            recipient.status = RecipientStatus.OPENED.value
            recipient.opened_at = now

            # Update campaign stats
            campaign_result = await db.execute(
                select(OutreachCampaign).where(
                    OutreachCampaign.id == recipient.campaign_id
                )
            )
            campaign = campaign_result.scalar_one_or_none()
            if campaign:
                campaign.opened_count += 1

            await db.commit()

    # Return tracking pixel
    return Response(
        content=TRACKING_PIXEL,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/click/{tracking_id}/{link_hash}")
async def track_click(
    tracking_id: str,
    link_hash: str,
    url: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """
    Track link click and redirect to actual URL.

    This endpoint records the click event and redirects to the original link.
    Called when a recipient clicks a tracked link in the email.

    Args:
        tracking_id: Recipient tracking ID
        link_hash: Hash of the original URL (for verification)
        url: The original URL (base64 encoded)
    """
    now = datetime.now(timezone.utc)

    # Decode the original URL
    try:
        original_url = base64.urlsafe_b64decode(url.encode()).decode("utf-8")
    except Exception:
        original_url = unquote(url)

    # Find recipient by tracking ID
    result = await db.execute(
        select(OutreachRecipient).where(OutreachRecipient.tracking_id == tracking_id)
    )
    recipient = result.scalar_one_or_none()

    if recipient:
        # Update click status if not already clicked
        if recipient.clicked_at is None:
            recipient.clicked_at = now
            if recipient.status not in [
                RecipientStatus.CLICKED.value,
                RecipientStatus.REPLIED.value,
            ]:
                recipient.status = RecipientStatus.CLICKED.value

            # Update campaign stats
            campaign_result = await db.execute(
                select(OutreachCampaign).where(
                    OutreachCampaign.id == recipient.campaign_id
                )
            )
            campaign = campaign_result.scalar_one_or_none()
            if campaign:
                campaign.clicked_count += 1

            await db.commit()

    # Redirect to original URL
    return RedirectResponse(url=original_url, status_code=302)


def generate_tracking_id() -> str:
    """Generate a unique tracking ID for a recipient."""
    import uuid
    return str(uuid.uuid4())


def generate_link_hash(url: str) -> str:
    """Generate a hash for a URL (for verification)."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def wrap_links_for_tracking(
    html_body: str,
    tracking_id: str,
    base_url: str,
) -> str:
    """
    Wrap all links in an email body with tracking URLs.

    Args:
        html_body: Original HTML email body
        tracking_id: Recipient's tracking ID
        base_url: Base URL for the tracking server (e.g., https://api.spacefit.ai)

    Returns:
        HTML body with wrapped links
    """
    import re

    def replace_link(match):
        original_url = match.group(1)
        # Don't wrap mailto: links or tracking URLs
        if original_url.startswith("mailto:") or "/tracking/" in original_url:
            return match.group(0)

        # Encode URL and generate hash
        encoded_url = base64.urlsafe_b64encode(original_url.encode()).decode()
        link_hash = generate_link_hash(original_url)

        tracking_url = f"{base_url}/api/v1/tracking/click/{tracking_id}/{link_hash}?url={encoded_url}"
        return f'href="{tracking_url}"'

    # Match href attributes
    return re.sub(r'href="([^"]+)"', replace_link, html_body)


def add_tracking_pixel(
    html_body: str,
    tracking_id: str,
    base_url: str,
) -> str:
    """
    Add a tracking pixel to an email body.

    Args:
        html_body: Original HTML email body
        tracking_id: Recipient's tracking ID
        base_url: Base URL for the tracking server

    Returns:
        HTML body with tracking pixel added
    """
    pixel_url = f"{base_url}/api/v1/tracking/open/{tracking_id}"
    pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none" alt="" />'

    # Insert before </body> if exists, otherwise append
    if "</body>" in html_body.lower():
        return html_body.replace("</body>", f"{pixel_html}</body>")
    else:
        return html_body + pixel_html
