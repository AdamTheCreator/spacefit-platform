"""Best-effort auth audit logging.

Writes rows to ``auth_events`` and emits a structured log line. Never raises:
an audit failure must not break an auth flow. NEVER pass passwords, tokens, or
reset links in ``detail``.
"""

from __future__ import annotations

import logging

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth_event import AuthEvent

logger = logging.getLogger(__name__)


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Respect a single proxy hop (Render sits in front of the app).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None


async def record_auth_event(
    db: AsyncSession,
    event: str,
    *,
    user_id: str | None = None,
    request: Request | None = None,
    detail: str | None = None,
) -> None:
    ip = client_ip(request)
    user_agent = request.headers.get("user-agent") if request else None
    request_id = request.headers.get("x-request-id") if request else None

    logger.info(
        "auth.event event=%s user_id=%s ip=%s", event, user_id or "-", ip or "-"
    )

    try:
        db.add(
            AuthEvent(
                user_id=user_id,
                event=event,
                ip_address=ip,
                user_agent=(user_agent[:1000] if user_agent else None),
                request_id=(request_id[:64] if request_id else None),
                detail=detail,
            )
        )
        await db.commit()
    except Exception as exc:  # pragma: no cover - audit must never break auth
        logger.warning("auth.event.persist_failed event=%s err=%s", event, exc)
