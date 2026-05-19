"""Sales lead capture for enterprise inquiries.

Public endpoint that anyone can hit from the pricing page; rate-limited
by client IP to keep the form from being weaponized. Successful
submissions persist a ``SalesLead`` row and fire a notification email
via Resend (best-effort — we still return 201 if email fails so the
prospect doesn't get a misleading error).
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession, OptionalUser, get_db
from app.core.config import settings
from app.db.models.sales_lead import SalesLead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sales", tags=["sales"])


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(value: str | None) -> str:
    if not value:
        return ""
    return _HTML_TAG_RE.sub("", value)


class _IPRateLimiter:
    """Tiny in-memory sliding-window rate limiter, keyed by IP.

    Good enough for a public marketing form on a single uvicorn worker;
    if/when we scale horizontally we'll swap this for Redis. Keeps at
    most ``limit`` timestamps per IP and trims aggressively on each
    call so memory growth stays bounded.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}

    def check(self, ip: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = self._buckets.setdefault(ip, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_rate_limiter = _IPRateLimiter()


class SalesLeadRequest(BaseModel):
    email: EmailStr
    company_name: str | None = Field(default=None, max_length=255)
    team_size: str | None = Field(default=None, max_length=20)
    current_tools: list[str] | None = Field(default=None)
    use_case: str | None = Field(default=None, max_length=2000)


class SalesLeadResponse(BaseModel):
    ok: bool = True
    message: str = "Thanks — we'll be in touch shortly."


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _send_sales_notification(lead: SalesLead) -> None:
    """Best-effort Resend notification. Falls back to logging on any
    failure; we never want a flaky email provider to lose us a lead."""
    if not settings.resend_api_key:
        logger.info(
            "Sales lead captured (Resend not configured): %s", lead.email
        )
        return

    notify_to = settings.sales_lead_notify_to or settings.resend_from_email
    if not notify_to:
        logger.warning("No sales notification address configured; lead %s only persisted", lead.id)
        return

    recipients = [addr.strip() for addr in notify_to.split(",") if addr.strip()]
    tools = _strip_tags(lead.current_tools) or "(none)"
    use_case = _strip_tags(lead.use_case) or "(not provided)"
    body = f"""
<!DOCTYPE html>
<html><body style="font-family: -apple-system, sans-serif;">
<h2>New enterprise lead</h2>
<table cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
  <tr><td><b>Email</b></td><td>{lead.email}</td></tr>
  <tr><td><b>Company</b></td><td>{lead.company_name or "(not provided)"}</td></tr>
  <tr><td><b>Team size</b></td><td>{lead.team_size or "(not provided)"}</td></tr>
  <tr><td><b>Current tools</b></td><td>{tools}</td></tr>
  <tr><td><b>Use case</b></td><td>{use_case}</td></tr>
  <tr><td><b>Source</b></td><td>{lead.source}</td></tr>
  <tr><td><b>User ID</b></td><td>{lead.user_id or "(anonymous)"}</td></tr>
</table>
</body></html>
"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                    "to": recipients,
                    "reply_to": lead.email,
                    "subject": f"[Space Goose] New enterprise lead: {lead.email}",
                    "html": body,
                },
            )
            if resp.status_code >= 400:
                logger.error(
                    "Resend sales notify failed: %s %s",
                    resp.status_code,
                    resp.text,
                )
    except Exception:
        logger.exception("Failed to send sales lead notification email")


@router.post(
    "/leads",
    status_code=status.HTTP_201_CREATED,
    response_model=SalesLeadResponse,
)
async def submit_sales_lead(
    payload: SalesLeadRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: OptionalUser,
) -> SalesLeadResponse:
    ip = _client_ip(request)
    if not _rate_limiter.check(
        ip,
        settings.sales_lead_rate_limit,
        settings.sales_lead_rate_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests — please try again later.",
        )

    tools_str = (
        ", ".join(t.strip() for t in payload.current_tools if t.strip())
        if payload.current_tools
        else None
    )

    lead = SalesLead(
        email=str(payload.email),
        company_name=payload.company_name,
        team_size=payload.team_size,
        current_tools=tools_str,
        use_case=payload.use_case,
        source="pricing_page",
        user_id=user.id if user else None,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    await _send_sales_notification(lead)

    return SalesLeadResponse()
