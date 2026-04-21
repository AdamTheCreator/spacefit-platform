"""Audit-log writer for the BYOK subsystem.

Every mutation of a credential row, every successful and unsuccessful
use of one, and every key-rotation / revocation emits a row to
``credential_audit_log``. Writes are fire-and-forget: we never want
audit overhead on the hot path of a chat request to delay the response
or, worse, cause the request to fail because the audit row couldn't be
written.

Action constants are centralised here so the UI's "recent activity"
subsection can map them to human strings without importing the writer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---- action constants -------------------------------------------------------


class AuditAction:
    """All legal values of ``credential_audit_log.action``."""

    CREATE: Final[str] = "credential.create"
    VALIDATE: Final[str] = "credential.validate"
    USE: Final[str] = "credential.use"
    USE_FAILED: Final[str] = "credential.use_failed"
    ROTATE_START: Final[str] = "credential.rotate_start"
    ROTATE_COMPLETE: Final[str] = "credential.rotate_complete"
    REVOKE: Final[str] = "credential.revoke"
    AUTO_INVALIDATE: Final[str] = "credential.auto_invalidate"
    VIEW_METADATA: Final[str] = "credential.view_metadata"
    SCOPE_UPDATE: Final[str] = "credential.scope_update"


# ---- audit entry payload ----------------------------------------------------


@dataclass
class AuditEntry:
    """In-memory representation of a row to be written.

    ``credential_id`` is optional because events can be emitted for
    credentials that have just been deleted (the row-level FK becomes
    NULL but the fingerprint preserves the logical linkage).
    """

    user_id: str
    action: str
    success: bool
    credential_id: str | None = None
    credential_fingerprint: str | None = None
    actor_user_id: str | None = None
    provider: str | None = None
    request_id: str | None = None
    error_code: str | None = None
    metadata: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None


# ---- writer -----------------------------------------------------------------


_INSERT_SQL = text(
    """
    INSERT INTO credential_audit_log (
        credential_id, credential_fingerprint,
        user_id, actor_user_id,
        action, provider, request_id,
        success, error_code,
        metadata_json, ip_address, user_agent
    ) VALUES (
        :credential_id, :credential_fingerprint,
        :user_id, :actor_user_id,
        :action, :provider, :request_id,
        :success, :error_code,
        :metadata_json, :ip_address, :user_agent
    )
    """
)


def _bind_params(entry: AuditEntry) -> dict[str, Any]:
    try:
        metadata_json = json.dumps(entry.metadata or {}, separators=(",", ":"))
    except Exception:
        # Non-serializable metadata shouldn't break the audit write.
        metadata_json = "{}"

    # Truncate long UA strings so pathological headers can't blow up a row.
    ua = (entry.user_agent or "")[:1024] or None

    return {
        "credential_id": entry.credential_id,
        "credential_fingerprint": entry.credential_fingerprint,
        "user_id": entry.user_id,
        "actor_user_id": entry.actor_user_id,
        "action": entry.action,
        "provider": entry.provider,
        "request_id": entry.request_id,
        "success": entry.success,
        "error_code": entry.error_code,
        "metadata_json": metadata_json,
        "ip_address": entry.ip_address,
        "user_agent": ua,
    }


async def write_audit(db: AsyncSession, entry: AuditEntry) -> None:
    """Append a single audit row using an already-open session.

    Prefer this when the caller is going to await before the session
    closes (e.g. inside a request handler that's finishing its own
    commit). For fire-and-forget from a long-lived task, use
    :func:`write_audit_detached` instead — it opens a fresh session so
    the write can complete after the caller's session is gone.

    Raw ``INSERT`` via :func:`sqlalchemy.text` rather than ORM
    ``db.add(...)`` to avoid a flush/refresh round-trip and sidestep a
    potential circular import from the models package.
    """
    try:
        await db.execute(_INSERT_SQL, _bind_params(entry))
        await db.commit()
    except Exception as e:
        # Audit writes must never raise up the call stack — that would
        # turn "your request succeeded but we couldn't log it" into a
        # hard failure for the user. Log and swallow.
        logger.warning(
            "audit write failed for user=%s action=%s: %s",
            entry.user_id,
            entry.action,
            e,
        )
        try:
            await db.rollback()
        except Exception:
            pass


async def write_audit_detached(entry: AuditEntry) -> None:
    """Open a fresh session, write the row, close.

    Used by the gateway for post-request ``credential.use`` audits that
    need to outlive the request's own ``AsyncSession`` (which FastAPI
    closes as soon as the handler returns). Imported lazily so a test
    can swap ``async_session_factory`` without side effects at import
    time.
    """
    try:
        from app.core.database import async_session_factory
    except Exception:
        logger.warning("audit: async_session_factory unavailable; dropping entry")
        return

    try:
        async with async_session_factory() as session:
            await session.execute(_INSERT_SQL, _bind_params(entry))
            await session.commit()
    except Exception as e:
        logger.warning(
            "detached audit write failed for user=%s action=%s: %s",
            entry.user_id,
            entry.action,
            e,
        )


def schedule_audit(entry: AuditEntry) -> None:
    """Fire-and-forget audit write. Non-blocking.

    Schedules :func:`write_audit_detached` on the running event loop;
    if there is no running loop (e.g. called during a blocking sync
    context), falls back to a logged drop. Safe to call from anywhere
    inside an async request handler.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(
            "audit: no running event loop; dropping entry action=%s", entry.action
        )
        return
    loop.create_task(write_audit_detached(entry))
