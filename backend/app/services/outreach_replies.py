"""Outreach reply detection (Phase 3b).

Scans a user's connected Gmail inbox for inbound replies from the contacts
they have emailed via outreach campaigns, and records the reply on the
matching ``OutreachRecipient`` so the dashboard triage queue can show real
replied threads instead of a ``replied_count`` placeholder.

This path is Gmail-dependent and cannot be exercised in the sandbox / CI
(there is no live Google account or OAuth token). It is structured so that
the only branch reachable without Gmail — ``get_user_gmail_tokens`` returning
``None`` — is a clean, side-effect-free ``return 0``, which the unit test in
``tests/test_outreach_replies.py`` covers. Everything that touches the Gmail
API is wrapped in ``run_in_executor`` (the Google client is synchronous) and
guarded per-recipient so a single failed lookup never aborts the run.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.outreach import (
    OutreachCampaign,
    OutreachRecipient,
    RecipientStatus,
)
from app.db.models.user import User
from app.services.gmail import (
    GmailService,
    GmailTokens,
    get_user_gmail_tokens,
)

logger = logging.getLogger(__name__)

# How far back to look for inbound replies.
REPLY_LOOKBACK = "30d"


def _find_reply_message(
    service,
    email: str,
) -> dict | None:
    """Search the inbox for a recent message from ``email``.

    Synchronous (Gmail's Python client is sync) — call via ``run_in_executor``.
    Returns the message dict (with ``id``, ``threadId``, ``snippet``,
    ``internalDate``) for the most recent match, or ``None`` when there is no
    reply / on any API error (best-effort, never raises).
    """
    query = f"from:{email} newer_than:{REPLY_LOOKBACK}"
    try:
        listing = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=1)
            .execute()
        )
    except Exception:
        logger.exception("[outreach_replies] list failed for %s", email)
        return None

    messages = listing.get("messages") or []
    if not messages:
        return None

    msg_id = messages[0]["id"]
    try:
        return (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="metadata")
            .execute()
        )
    except Exception:
        logger.exception("[outreach_replies] get failed for %s", msg_id)
        return None


def _received_at(message: dict) -> datetime:
    """Best-effort received timestamp from a Gmail ``internalDate`` (ms)."""
    raw = message.get("internalDate")
    if raw:
        try:
            return datetime.utcfromtimestamp(int(raw) / 1000)
        except (ValueError, TypeError, OverflowError):
            pass
    return datetime.utcnow()


async def sync_replies_for_user(db: AsyncSession, user: User) -> int:
    """Detect inbound replies for ``user`` and mark recipients as replied.

    Returns the number of newly-detected replies. Returns ``0`` (and does no
    Gmail work) when the user has no usable connected Gmail account — i.e.
    when ``get_user_gmail_tokens`` yields ``None`` (Gmail not connected or the
    platform Google client is unconfigured).
    """
    tokens: GmailTokens | None = await get_user_gmail_tokens(db, user.id)
    if tokens is None:
        return 0

    # Load this user's not-yet-replied recipients that have an email to match.
    result = await db.execute(
        select(OutreachRecipient)
        .join(
            OutreachCampaign,
            OutreachRecipient.campaign_id == OutreachCampaign.id,
        )
        .where(
            OutreachCampaign.user_id == user.id,
            OutreachRecipient.status != RecipientStatus.REPLIED.value,
            OutreachRecipient.contact_email.is_not(None),
        )
    )
    recipients = list(result.scalars().all())
    if not recipients:
        return 0

    # Group recipients by email so we make one Gmail search per address even
    # if the same tenant appears across several campaigns.
    by_email: dict[str, list[OutreachRecipient]] = {}
    for recipient in recipients:
        email = (recipient.contact_email or "").strip()
        if email:
            by_email.setdefault(email.lower(), []).append(recipient)

    if not by_email:
        return 0

    service = GmailService(tokens)._get_service()
    loop = asyncio.get_event_loop()

    new_replies = 0
    for email, group in by_email.items():
        try:
            message = await loop.run_in_executor(
                None, _find_reply_message, service, email
            )
            if message is None:
                continue

            received = _received_at(message)
            snippet = message.get("snippet") or None
            message_id = message.get("id")
            thread_id = message.get("threadId")

            for recipient in group:
                recipient.status = RecipientStatus.REPLIED.value
                recipient.replied_at = datetime.utcnow()
                recipient.reply_received_at = received
                recipient.reply_snippet = snippet
                recipient.reply_message_id = message_id
                recipient.reply_thread_id = thread_id
                # Bump the parent campaign's replied counter.
                campaign = await db.get(
                    OutreachCampaign, recipient.campaign_id
                )
                if campaign is not None:
                    campaign.replied_count = (campaign.replied_count or 0) + 1
                new_replies += 1
        except Exception:
            # Best-effort: one bad recipient must not abort the whole run.
            logger.exception(
                "[outreach_replies] reply sync failed for %s", email
            )

    if new_replies:
        await db.commit()

    return new_replies
