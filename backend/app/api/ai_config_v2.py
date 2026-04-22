"""Rebuilt BYOK endpoint handlers.

v1 (``app.api.ai_config``) delegates to these functions when
``BYOK_REBUILD_ENABLED`` is true. The functions accept the same
route-handler arguments so the delegation is a one-line ``return await
v2.handler(...)``.

Differences vs v1:

    * Submission rate limit (5/min/user on PUT + POST /validate-key).
    * Syntactic regex pre-check per provider (fails fast before a
      network call; warning-only on unknown patterns).
    * Duplicate detection via ``key_fingerprint`` (sha256 of plaintext).
    * Additive rotation: a PUT with a new api_key creates a new row in
      ``status='rotating'``, validates it against the provider, then
      flips the new row to ``active`` and the old row to ``revoked``
      in a single transaction.
    * Soft-delete revoke: DELETE sets ``status='revoked'`` + revoked_at
      + revoked_by and zeroes the envelope columns (crypto-shred).
    * New scope CRUD (``PUT /ai-config/scope``).
    * New audit query (``GET /ai-config/audit``).
    * All errors flow through :class:`BYOKError`; the HTTP layer maps
      the normalized code to an HTTP status + JSON body.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.byok import crypto
from app.byok.audit import AuditAction, AuditEntry, write_audit
from app.byok.errors import BYOKError, BYOKErrorCode
from app.byok.gateway import gateway
from app.byok.scope import Scope
from app.core.config import settings
from app.db.models.credential import CredentialAuditLog, UserAIConfig

logger = logging.getLogger(__name__)


# ---- submission rate limiter ------------------------------------------------


class _SubmissionRateLimiter:
    """Sliding-window per-user rate limit for credential writes.

    Protects ``PUT /ai-config`` and ``POST /ai-config/validate-key`` from
    brute-force key probing. Mirrors the shape of
    :class:`app.services.guardrails.MessageRateLimiter` so operator
    muscle memory transfers.
    """

    def __init__(self) -> None:
        self._timestamps: dict[str, list[float]] = {}

    def check(self, user_id: str) -> None:
        now = time.monotonic()
        window = settings.byok_submission_window_seconds
        limit = settings.byok_submission_rate_limit

        window_start = now - window
        stamps = [t for t in self._timestamps.get(user_id, []) if t > window_start]
        stamps.append(now)
        self._timestamps[user_id] = stamps

        if len(stamps) > limit:
            raise BYOKError(
                code=BYOKErrorCode.INVALID_REQUEST,
                http_status=429,
                retryable=True,
                message=f"Too many credential submissions ({limit}/{window}s). Please wait.",
            )


_submission_limiter = _SubmissionRateLimiter()


# ---- syntactic pre-check ---------------------------------------------------


# Best-effort patterns. Vendors change formats — unknown shapes are
# logged and allowed through to live validation, which is the real
# authority. The point here is to fail fast on obviously-wrong input
# (empty string, mangled paste, wrong provider selected).
_SYNTAX: dict[str, re.Pattern] = {
    "anthropic": re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,}$"),
    "openai": re.compile(r"^sk-[A-Za-z0-9_\-]{20,}$"),
    "google": re.compile(r"^[A-Za-z0-9_\-]{35,50}$"),
    "deepseek": re.compile(r"^sk-[A-Za-z0-9_\-]{20,}$"),
}


def _syntax_ok(provider: str, api_key: str) -> bool:
    pattern = _SYNTAX.get(provider)
    if pattern is None:
        return True  # unknown provider (openai_compatible) → skip check
    ok = bool(pattern.match(api_key))
    if not ok:
        logger.info(
            "byok submission: syntax check missed for provider=%s (len=%d) — "
            "deferring to live validation",
            provider,
            len(api_key),
        )
    return ok


# ---- request/response schemas ----------------------------------------------


class AIConfigUpdate(BaseModel):
    provider: str = Field(
        description="Provider ID (anthropic, openai, google, deepseek, openai_compatible, platform_default)"
    )
    model: str | None = Field(default=None, description="Model override")
    api_key: str | None = Field(default=None, description="API key (only sent when updating)")
    base_url: str | None = Field(default=None, description="Custom endpoint URL")
    label: str | None = Field(default=None, max_length=100)


class AIConfigResponse(BaseModel):
    id: str | None
    provider: str
    model: str | None
    base_url: str | None
    label: str | None
    has_byok_key: bool
    is_key_valid: bool
    key_validated_at: datetime | None
    key_error_message: str | None
    key_last_four: str | None
    status: str
    scope: dict[str, Any]
    effective_provider: str
    effective_model: str

    model_config = {"from_attributes": True}


class ScopeUpdate(BaseModel):
    """Governance scope payload. Absent fields clear that dimension."""

    allowed_models: list[str] | None = None
    denied_models: list[str] | None = None
    monthly_spend_cap_usd: float | None = Field(default=None, ge=0)
    monthly_request_cap: int | None = Field(default=None, ge=0)


class AuditLogEntry(BaseModel):
    id: int
    action: str
    success: bool
    provider: str | None
    error_code: str | None
    request_id: str | None
    metadata: dict[str, Any]
    occurred_at: datetime

    model_config = {"from_attributes": True}


# ---- helpers ----------------------------------------------------------------


def _http_error_from_byok(err: BYOKError) -> HTTPException:
    """Map a BYOKError into a FastAPI HTTPException.

    Keeps the response-body shape consistent across v2 endpoints:
    ``{"error": "<code>", "message": "<safe user message>",
      "provider_request_id": "<optional>"}``. The BYOKError's message is
    already scrubbed (see :mod:`app.byok.errors`), so it's safe to
    return as-is.
    """
    detail: dict[str, Any] = {"error": err.code, "message": err.message}
    if err.provider_request_id:
        detail["provider_request_id"] = err.provider_request_id
    if err.retry_after_seconds is not None:
        detail["retry_after_seconds"] = err.retry_after_seconds
    return HTTPException(status_code=err.http_status, detail=detail)


def _effective_provider_model(config: UserAIConfig | None, user_tier: str) -> tuple[str, str]:
    """Compute effective provider/model for UI display.

    Replicates the v1 helper here rather than importing it so the v2
    module has no dependency on the v1 routing module — they're
    allowed to evolve independently.
    """
    if config and config.provider != "platform_default" and config.is_key_valid:
        from app.services.user_llm import PROVIDER_DEFAULT_MODELS

        model = config.model or PROVIDER_DEFAULT_MODELS.get(config.provider, "")
        return config.provider, model
    if user_tier in ("individual", "enterprise"):
        return "anthropic", settings.llm_model or settings.anthropic_model
    return "google", "gemini-2.0-flash"


def _row_to_response(
    row: UserAIConfig | None,
    eff_provider: str,
    eff_model: str,
) -> AIConfigResponse:
    if row is None:
        return AIConfigResponse(
            id=None,
            provider="platform_default",
            model=None,
            base_url=None,
            label=None,
            has_byok_key=False,
            is_key_valid=False,
            key_validated_at=None,
            key_error_message=None,
            key_last_four=None,
            status="active",
            scope={},
            effective_provider=eff_provider,
            effective_model=eff_model,
        )
    scope_obj = Scope.from_json(row.scope)
    return AIConfigResponse(
        id=row.id,
        provider=row.provider,
        model=row.model,
        base_url=row.base_url,
        label=row.label,
        has_byok_key=row.api_key_encrypted is not None,
        is_key_valid=row.is_key_valid,
        key_validated_at=row.key_validated_at,
        key_error_message=row.key_error_message,
        key_last_four=row.key_last_four,
        status=row.status,
        scope=_scope_to_dict(scope_obj),
        effective_provider=eff_provider,
        effective_model=eff_model,
    )


def _scope_to_dict(scope: Scope) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if scope.allowed_models:
        out["allowed_models"] = scope.allowed_models
    if scope.denied_models:
        out["denied_models"] = scope.denied_models
    if scope.monthly_spend_cap_usd is not None:
        out["monthly_spend_cap_usd"] = scope.monthly_spend_cap_usd
    if scope.monthly_request_cap is not None:
        out["monthly_request_cap"] = scope.monthly_request_cap
    return out


async def _fetch_active(db: AsyncSession, user_id: str) -> UserAIConfig | None:
    result = await db.execute(
        select(UserAIConfig)
        .where(UserAIConfig.user_id == user_id)
        .where(UserAIConfig.status == "active")
    )
    return result.scalar_one_or_none()


async def _run_live_validation(
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
) -> tuple[bool, str | None]:
    """Make a cheap, idempotent call to the provider to verify the key.

    ``model`` is the user's intended model and is stored by the caller
    regardless of whether we probe against it. For most providers we
    deliberately probe against the dedicated validation model (see
    ``user_llm.select_validation_model``) — validating a brand-new key
    against a premium model like gpt-4o rate-limits on the lowest tier
    before we can confirm the key is valid at all. Fallback to the
    user's model only for providers like ``openai_compatible`` where
    we don't know which models the endpoint exposes.

    Returns ``(ok, error_message)``. Never logs the api_key.
    """
    from app.llm.client import get_or_create_client
    from app.llm.types import LLMChatMessage, LLMChatRequest
    from app.services.user_llm import select_validation_model

    probe_model = select_validation_model(provider, model)

    try:
        client = get_or_create_client(
            provider=provider,
            api_key=api_key,
            base_url=base_url or "",
        )
        await client.chat(
            LLMChatRequest(
                model=probe_model,
                max_tokens=1,
                system="Reply with only the word 'ok'.",
                messages=[LLMChatMessage(role="user", content="test")],
            )
        )
        return True, None
    except BYOKError as e:
        # Pass through the normalized message — it's already user-safe.
        return False, e.message
    except Exception as e:
        # Unknown class. Truncate and return the raw string; the caller
        # stores this in key_error_message (also truncated to 200).
        msg = str(e)
        return False, (msg[:200] + "…") if len(msg) > 200 else msg


# ---- handlers ---------------------------------------------------------------


async def get_ai_config_v2(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIConfigResponse:
    """Return the user's current active credential row (or the default
    shell when none exists). Same contract as v1 plus ``status``,
    ``scope``, ``key_last_four``, and ``label`` fields."""
    row = await _fetch_active(db, current_user.id)
    eff_provider, eff_model = _effective_provider_model(row, current_user.tier)
    return _row_to_response(row, eff_provider, eff_model)


async def update_ai_config_v2(
    payload: AIConfigUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> AIConfigResponse:
    """Create or rotate the user's BYOK credential.

    Rotation semantics:

        * If ``api_key`` is provided: we live-validate, and if the check
          passes we insert a new ``active`` row and mark the previous
          active row ``revoked``. This is additive so in-flight requests
          using the old key aren't interrupted mid-flight.
        * If no ``api_key`` is provided: we update the provider / model /
          base_url / label on the existing active row in place. Used
          for swapping between providers that don't require a key
          (platform_default) or tweaking the model selection.
    """
    _submission_limiter.check(current_user.id)

    # Validate provider name.
    from app.api.ai_config import SUPPORTED_PROVIDERS

    valid_ids = {p["id"] for p in SUPPORTED_PROVIDERS}
    if payload.provider not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {payload.provider}")

    existing = await _fetch_active(db, current_user.id)

    # Rotation path requires a new key.
    if payload.api_key:
        if not _syntax_ok(payload.provider, payload.api_key):
            # Only warn; defer to live validation for the hard decision.
            logger.info("byok: syntax pre-check missed for user=%s", current_user.id)

        fp = crypto.fingerprint(payload.api_key)

        # Duplicate: same (user, provider, fingerprint) already active/rotating
        # blocks the submission. Revoked duplicates are fine; the user is
        # re-adding a historically-revoked key.
        dup = await db.execute(
            select(UserAIConfig)
            .where(UserAIConfig.user_id == current_user.id)
            .where(UserAIConfig.provider == payload.provider)
            .where(UserAIConfig.key_fingerprint == fp)
            .where(UserAIConfig.status.in_(["active", "rotating"]))
        )
        if dup.scalar_one_or_none() is not None:
            raise _http_error_from_byok(BYOKError.duplicate())

        # Default model if the caller didn't specify one.
        from app.services.user_llm import PROVIDER_DEFAULT_MODELS

        effective_model = payload.model or PROVIDER_DEFAULT_MODELS.get(payload.provider, "")

        # Live validation. Short-circuit on failure — nothing is written
        # to the DB, so the user can retry without accumulating junk rows.
        ok, err = await _run_live_validation(
            payload.provider, payload.api_key, effective_model, payload.base_url
        )
        if not ok:
            return_err = BYOKError.credential_invalid(err or "Validation failed")
            # Audit the failed validation so operators can see the
            # attempt (without the key material).
            await write_audit(
                db,
                AuditEntry(
                    user_id=current_user.id,
                    action=AuditAction.VALIDATE,
                    success=False,
                    credential_fingerprint=fp,
                    actor_user_id=current_user.id,
                    provider=payload.provider,
                    error_code=return_err.code,
                    metadata={"error_message": (err or "")[:200]},
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                ),
            )
            raise _http_error_from_byok(return_err)

        # Envelope-encrypt and insert the new row, then revoke the old.
        bundle = crypto.encrypt_api_key(payload.api_key)
        new_row = UserAIConfig(
            user_id=current_user.id,
            scope_level="user",
            provider=payload.provider,
            model=effective_model,
            base_url=payload.base_url,
            label=payload.label,
            api_key_encrypted=bundle.ciphertext,
            ciphertext_iv=bundle.iv,
            ciphertext_tag=bundle.auth_tag,
            encrypted_dek=bundle.encrypted_dek,
            kek_id=bundle.kek_id,
            key_fingerprint=fp,
            key_last_four=crypto.last_four(payload.api_key),
            scope=(existing.scope if existing else "{}"),  # carry scope forward
            status="active",
            is_key_valid=True,
            key_validated_at=datetime.now(timezone.utc),
            key_error_message=None,
            created_by=current_user.id,
        )
        db.add(new_row)

        if existing is not None:
            # Mark old row revoked and zero the envelope columns.
            # Done as an UPDATE in the same transaction so the partial
            # unique index on (user_id, provider) WHERE status IN
            # ('active','rotating') never sees two active rows.
            await db.execute(
                update(UserAIConfig)
                .where(UserAIConfig.id == existing.id)
                .values(
                    status="revoked",
                    revoked_at=datetime.now(timezone.utc),
                    revoked_by=current_user.id,
                    api_key_encrypted=None,
                    ciphertext_iv=None,
                    ciphertext_tag=None,
                    encrypted_dek=None,
                    kek_id=None,
                    encryption_salt=None,
                    is_key_valid=False,
                )
            )
            gateway.invalidate_cache(existing.id)
            await write_audit(
                db,
                AuditEntry(
                    user_id=current_user.id,
                    action=AuditAction.ROTATE_COMPLETE,
                    success=True,
                    credential_id=existing.id,
                    credential_fingerprint=existing.key_fingerprint,
                    actor_user_id=current_user.id,
                    provider=existing.provider,
                ),
            )

        await db.commit()
        await db.refresh(new_row)

        await write_audit(
            db,
            AuditEntry(
                user_id=current_user.id,
                action=AuditAction.CREATE,
                success=True,
                credential_id=new_row.id,
                credential_fingerprint=fp,
                actor_user_id=current_user.id,
                provider=payload.provider,
                metadata={"model": effective_model},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ),
        )

        eff_provider, eff_model = _effective_provider_model(new_row, current_user.tier)
        return _row_to_response(new_row, eff_provider, eff_model)

    # In-place update path (no new key).
    if existing is None:
        existing = UserAIConfig(user_id=current_user.id, scope_level="user")
        db.add(existing)

    existing.provider = payload.provider
    existing.model = payload.model
    existing.base_url = payload.base_url
    if payload.label is not None:
        existing.label = payload.label

    # Switching to platform_default clears any stored key material
    # (crypto-shred) so a later switch-back requires re-entry.
    if payload.provider == "platform_default":
        gateway.invalidate_cache(existing.id)
        existing.api_key_encrypted = None
        existing.ciphertext_iv = None
        existing.ciphertext_tag = None
        existing.encrypted_dek = None
        existing.kek_id = None
        existing.encryption_salt = None
        existing.key_fingerprint = None
        existing.key_last_four = None
        existing.is_key_valid = False
        existing.key_validated_at = None
        existing.key_error_message = None

    await db.commit()
    await db.refresh(existing)
    eff_provider, eff_model = _effective_provider_model(existing, current_user.tier)
    return _row_to_response(existing, eff_provider, eff_model)


async def remove_byok_key_v2(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> AIConfigResponse:
    """Soft-delete the user's BYOK credential.

    ``status='revoked'`` and the envelope columns are zeroed. The row
    stays for audit; the user's next chat falls through to the platform
    default. If the user wants to re-use the provider later, they have
    to re-enter the key.
    """
    _submission_limiter.check(current_user.id)

    existing = await _fetch_active(db, current_user.id)
    if existing is None:
        # Nothing to revoke — return the default shell.
        eff_provider, eff_model = _effective_provider_model(None, current_user.tier)
        return _row_to_response(None, eff_provider, eff_model)

    cred_id = existing.id
    fingerprint = existing.key_fingerprint
    provider = existing.provider

    await db.execute(
        update(UserAIConfig)
        .where(UserAIConfig.id == cred_id)
        .values(
            status="revoked",
            revoked_at=datetime.now(timezone.utc),
            revoked_by=current_user.id,
            api_key_encrypted=None,
            ciphertext_iv=None,
            ciphertext_tag=None,
            encrypted_dek=None,
            kek_id=None,
            encryption_salt=None,
            is_key_valid=False,
        )
    )
    await db.commit()
    gateway.invalidate_cache(cred_id)

    await write_audit(
        db,
        AuditEntry(
            user_id=current_user.id,
            action=AuditAction.REVOKE,
            success=True,
            credential_id=cred_id,
            credential_fingerprint=fingerprint,
            actor_user_id=current_user.id,
            provider=provider,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ),
    )

    eff_provider, eff_model = _effective_provider_model(None, current_user.tier)
    return _row_to_response(None, eff_provider, eff_model)


async def update_scope_v2(
    payload: ScopeUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> AIConfigResponse:
    """Update the governance scope on the active credential row.

    Unset fields (None) leave the dimension untouched. To clear a
    dimension explicitly, send an empty list or zero.
    """
    existing = await _fetch_active(db, current_user.id)
    if existing is None:
        raise _http_error_from_byok(BYOKError.credential_not_found("any"))

    current = Scope.from_json(existing.scope)
    if payload.allowed_models is not None:
        current.allowed_models = payload.allowed_models
    if payload.denied_models is not None:
        current.denied_models = payload.denied_models
    if payload.monthly_spend_cap_usd is not None:
        current.monthly_spend_cap_usd = payload.monthly_spend_cap_usd or None
    if payload.monthly_request_cap is not None:
        current.monthly_request_cap = payload.monthly_request_cap or None

    existing.scope = current.to_json()
    await db.commit()
    await db.refresh(existing)

    await write_audit(
        db,
        AuditEntry(
            user_id=current_user.id,
            action=AuditAction.SCOPE_UPDATE,
            success=True,
            credential_id=existing.id,
            credential_fingerprint=existing.key_fingerprint,
            actor_user_id=current_user.id,
            provider=existing.provider,
            metadata=_scope_to_dict(current),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ),
    )

    eff_provider, eff_model = _effective_provider_model(existing, current_user.tier)
    return _row_to_response(existing, eff_provider, eff_model)


async def get_audit_log_v2(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[AuditLogEntry]:
    """Return the user's audit log in reverse-chronological order.

    ``limit`` capped at 200 to prevent accidental large scans. Users
    only see their own rows; admin-scoped queries will gain a
    separate endpoint when RBAC arrives.
    """
    import json

    clamped = min(max(1, limit), 200)
    result = await db.execute(
        select(CredentialAuditLog)
        .where(CredentialAuditLog.user_id == current_user.id)
        .order_by(desc(CredentialAuditLog.occurred_at))
        .limit(clamped)
    )
    rows = result.scalars().all()

    out: list[AuditLogEntry] = []
    for r in rows:
        try:
            metadata = json.loads(r.metadata_json) if r.metadata_json else {}
        except Exception:
            metadata = {}
        out.append(
            AuditLogEntry(
                id=r.id,
                action=r.action,
                success=r.success,
                provider=r.provider,
                error_code=r.error_code,
                request_id=r.request_id,
                metadata=metadata if isinstance(metadata, dict) else {},
                occurred_at=r.occurred_at,
            )
        )
    return out
