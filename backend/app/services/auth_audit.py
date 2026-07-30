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
    # Use the direct peer address by default. Only trust x-forwarded-for
    # when the request comes from a known proxy (Render's load balancer).
    # This prevents clients from spoofing the header to bypass IP-based
    # rate limits.
    peer = request.client.host if request.client else None
    if peer is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Take the leftmost entry (closest to the client) but only when
        # the direct peer is a private/local address (i.e. behind a proxy).
        _is_private = peer.startswith(("10.", "172.16.", "172.17.", "172.18.",
            "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
            "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.",
            "172.31.", "192.168.", "127.", "::1"))
        if _is_private:
            return forwarded.split(",")[0].strip()[:64]
    return peer[:64]


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
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001 - nothing further we can do
            logger.warning("auth.event.rollback_failed event=%s", event)
