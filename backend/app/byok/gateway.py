"""BYOK gateway: the single entry point for using a user's API key.

Everything that wants to make an LLM call on behalf of a user goes
through :class:`BYOKGateway`. The gateway owns:

    resolve   — look up the single active credential row for a user
    decrypt   — unwrap the envelope (with a ≤60s plaintext cache)
    scope     — enforce allowed_models / spend / request caps
    backpressure — per-credential semaphore + 429 cooldown
    circuit   — auto-invalidate after N consecutive `credential_invalid`
    audit     — write credential_audit_log rows fire-and-forget

The gateway is stateless across requests except for process-local
maps (cache, cooldowns, semaphores, invalid-counters). With multiple
Uvicorn workers each has its own maps; limits are under-enforced by a
factor of N workers, which is the same tradeoff the existing
`MessageRateLimiter` takes and is acceptable for the scales involved.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.byok import crypto
from app.byok.audit import AuditAction, AuditEntry, schedule_audit
from app.byok.errors import BYOKError, BYOKErrorCode
from app.byok.scope import Scope, enforce_scope, estimate_cost_usd
from app.core.config import settings
from app.db.models.credential import UserAIConfig

logger = logging.getLogger(__name__)


# ---- resolved-credential container -----------------------------------------


@dataclass
class ResolvedCredential:
    """Snapshot of a credential row + everything the caller needs to
    dispatch a chat request. The plaintext API key is *not* held here —
    callers ask the gateway to decrypt on demand so the cache is the
    only place it lives."""

    id: str
    user_id: str
    provider: str
    model: str | None
    base_url: str | None
    specialist_models_json: str | None
    key_fingerprint: str | None
    scope: Scope

    # Envelope bundle fields, needed for decrypt.
    ciphertext: bytes
    ciphertext_iv: bytes
    ciphertext_tag: bytes
    encrypted_dek: bytes
    kek_id: str

    # Legacy columns, used by the decrypt fallback for pre-029 rows.
    legacy_ciphertext: bytes | None = None
    legacy_salt: bytes | None = None


# ---- LLM client protocol (duck-typed, avoids a circular import) ------------


class _SupportsChat(Protocol):
    async def chat(self, request: object) -> object: ...


# ---- the gateway ------------------------------------------------------------


class BYOKGateway:
    """Process-singleton gateway. Instantiate once at app start."""

    def __init__(self) -> None:
        # plaintext cache: credential_id -> (plaintext, expires_at_epoch)
        self._key_cache: dict[str, tuple[str, float]] = {}
        # per-credential concurrency
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        # cooldown (after provider 429): credential_id -> epoch_until
        self._cooldown_until: dict[str, float] = {}
        # consecutive credential_invalid counter: credential_id -> count
        self._invalid_streak: dict[str, int] = {}

    # ---- resolution ---------------------------------------------------------

    async def resolve_credential(
        self,
        db: AsyncSession,
        user_id: str,
        provider: str | None = None,
    ) -> ResolvedCredential | None:
        """Find the single active BYOK credential for a user.

        Returns ``None`` if the user has no active row or only has a
        ``platform_default`` row (i.e. they've explicitly opted out of
        BYOK). Callers should then fall through to the platform-default
        resolution path in :mod:`app.services.user_llm`.
        """
        stmt = (
            select(UserAIConfig)
            .where(UserAIConfig.user_id == user_id)
            .where(UserAIConfig.scope_level == "user")
            .where(UserAIConfig.status == "active")
        )
        if provider is not None:
            stmt = stmt.where(UserAIConfig.provider == provider)

        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if row.provider == "platform_default":
            return None
        # Without envelope columns populated this row either hasn't been
        # through migration 029 yet or was explicitly unset; don't try
        # to decrypt it from the gateway — let the caller fall back.
        envelope_ready = (
            row.api_key_encrypted is not None
            and row.ciphertext_iv is not None
            and row.ciphertext_tag is not None
            and row.encrypted_dek is not None
            and row.kek_id is not None
        )
        legacy_ready = row.api_key_encrypted is not None and row.encryption_salt is not None
        if not envelope_ready and not legacy_ready:
            return None

        return ResolvedCredential(
            id=row.id,
            user_id=row.user_id,
            provider=row.provider,
            model=row.model,
            base_url=row.base_url,
            specialist_models_json=row.specialist_models_json,
            key_fingerprint=row.key_fingerprint,
            scope=Scope.from_json(row.scope),
            ciphertext=row.api_key_encrypted or b"",
            ciphertext_iv=row.ciphertext_iv or b"",
            ciphertext_tag=row.ciphertext_tag or b"",
            encrypted_dek=row.encrypted_dek or b"",
            kek_id=row.kek_id or "",
            legacy_ciphertext=row.api_key_encrypted if not envelope_ready else None,
            legacy_salt=row.encryption_salt if not envelope_ready else None,
        )

    # ---- decrypt + cache ----------------------------------------------------

    def _cache_ttl(self) -> float:
        # Cap at 60s regardless of what's configured — per the plan.
        return float(min(60, max(0, settings.byok_decrypt_cache_ttl_seconds)))

    def _get_cached_key(self, credential_id: str) -> str | None:
        entry = self._key_cache.get(credential_id)
        if entry is None:
            return None
        plaintext, expires_at = entry
        if time.monotonic() >= expires_at:
            # Lazy eviction.
            self._key_cache.pop(credential_id, None)
            return None
        return plaintext

    def _set_cached_key(self, credential_id: str, plaintext: str) -> None:
        ttl = self._cache_ttl()
        if ttl <= 0:
            return
        self._key_cache[credential_id] = (plaintext, time.monotonic() + ttl)

    def invalidate_cache(self, credential_id: str) -> None:
        """Drop the cached plaintext key. Called on rotate, revoke, or
        auth failure. Safe to call for a credential that isn't cached."""
        self._key_cache.pop(credential_id, None)

    async def decrypt(self, cred: ResolvedCredential) -> str:
        """Return the plaintext API key for a resolved credential.

        Uses the TTL cache when populated. Raises
        :class:`BYOKError.decrypt_failed` on any crypto error — callers
        should surface a generic user-facing message and never leak the
        underlying exception.
        """
        cached = self._get_cached_key(cred.id)
        if cached is not None:
            return cached

        try:
            if cred.encrypted_dek and cred.kek_id:
                plaintext = crypto.decrypt_api_key(
                    crypto.EnvelopeBundle(
                        ciphertext=cred.ciphertext,
                        iv=cred.ciphertext_iv,
                        auth_tag=cred.ciphertext_tag,
                        encrypted_dek=cred.encrypted_dek,
                        kek_id=cred.kek_id,
                    )
                )
            elif cred.legacy_ciphertext is not None and cred.legacy_salt is not None:
                # Pre-029 legacy row — decrypt via the old Fernet primitive.
                # Imported lazily so the gateway can be imported in test
                # contexts that don't pull in the full security module.
                from app.core.security import decrypt_credential

                plaintext = decrypt_credential(cred.legacy_ciphertext, cred.legacy_salt)
            else:
                raise BYOKError.decrypt_failed()
        except BYOKError:
            raise
        except Exception as e:
            logger.error(
                "decrypt failed for credential %s (provider=%s): %s",
                cred.id,
                cred.provider,
                e.__class__.__name__,
            )
            raise BYOKError.decrypt_failed() from e

        self._set_cached_key(cred.id, plaintext)
        return plaintext

    # ---- concurrency, cooldown, circuit breaker ----------------------------

    def _semaphore_for(self, credential_id: str) -> asyncio.Semaphore:
        sem = self._semaphores.get(credential_id)
        if sem is None:
            sem = asyncio.Semaphore(max(1, settings.byok_per_key_max_concurrency))
            self._semaphores[credential_id] = sem
        return sem

    def _check_cooldown(self, credential_id: str) -> None:
        until = self._cooldown_until.get(credential_id)
        if until is None:
            return
        remaining = until - time.monotonic()
        if remaining <= 0:
            self._cooldown_until.pop(credential_id, None)
            return
        raise BYOKError.rate_limited(retry_after_seconds=remaining)

    def _set_cooldown(self, credential_id: str, seconds: float) -> None:
        if seconds <= 0:
            return
        self._cooldown_until[credential_id] = time.monotonic() + seconds

    def _bump_invalid_streak(self, credential_id: str) -> int:
        n = self._invalid_streak.get(credential_id, 0) + 1
        self._invalid_streak[credential_id] = n
        return n

    def _reset_invalid_streak(self, credential_id: str) -> None:
        self._invalid_streak.pop(credential_id, None)

    async def _mark_invalid(
        self,
        db: AsyncSession,
        cred: ResolvedCredential,
        reason: str,
    ) -> None:
        """Flip a credential to ``status='invalid'`` and clear caches.

        Fired by the circuit breaker when the upstream has rejected the
        key N times in a row. Users see a Revalidate prompt in the UI.
        """
        try:
            await db.execute(
                update(UserAIConfig)
                .where(UserAIConfig.id == cred.id)
                .values(
                    status="invalid",
                    is_key_valid=False,
                    key_error_message=reason[:200],
                )
            )
            await db.commit()
        except Exception as e:
            logger.error(
                "failed to flip credential %s to invalid: %s", cred.id, e
            )
        self.invalidate_cache(cred.id)
        self._reset_invalid_streak(cred.id)

        # Fire-and-forget audit of the auto-invalidation. Uses a fresh
        # session because `db` may be closed by the time this runs.
        schedule_audit(
            AuditEntry(
                user_id=cred.user_id,
                action=AuditAction.AUTO_INVALIDATE,
                success=True,
                credential_id=cred.id,
                credential_fingerprint=cred.key_fingerprint,
                provider=cred.provider,
                error_code=BYOKErrorCode.CREDENTIAL_INVALID,
                metadata={"reason": reason[:200]},
            )
        )

    # ---- last_used_at bump --------------------------------------------------

    async def _touch_last_used(self, db: AsyncSession, credential_id: str) -> None:
        try:
            await db.execute(
                update(UserAIConfig)
                .where(UserAIConfig.id == credential_id)
                .values(last_used_at=datetime.now(timezone.utc))
            )
            await db.commit()
        except Exception:
            # Usage timestamp is hygiene, not business-critical. Swallow.
            pass

    # ---- the hot path -------------------------------------------------------

    async def run_chat(
        self,
        db: AsyncSession,
        cred: ResolvedCredential,
        call: Callable[[str], Awaitable[object]],
        *,
        model: str,
        request_id: str | None = None,
        actor_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> object:
        """Dispatch a chat call through all gateway guards.

        ``call(api_key)`` is an async callable the caller provides — it
        gets the plaintext key and should return whatever the adapter
        returned (an ``LLMResponse``, a stream iterator, etc.). Keeping
        the actual dispatch outside this module means the gateway
        doesn't need to know the adapter's type signatures or own the
        client registry; it just wraps the call with guards.

        Guards applied, in order:
          1. cooldown check (short-circuits if the credential is on a
             429 Retry-After cooldown)
          2. scope check (model allowlist, quota)
          3. per-credential semaphore acquisition
          4. the actual call
          5. error classification + circuit breaker + audit write
          6. last_used_at bump on success
        """
        req_id = request_id or uuid.uuid4().hex

        self._check_cooldown(cred.id)
        await enforce_scope(db, scope=cred.scope, user_id=cred.user_id, model=model)

        try:
            api_key = await self.decrypt(cred)
        except BYOKError as e:
            await self._emit_use_audit(
                db, cred, req_id, actor_id, ip_address, user_agent,
                success=False, error_code=e.code,
            )
            raise

        sem = self._semaphore_for(cred.id)
        input_tokens = 0
        output_tokens = 0

        async with sem:
            try:
                response = await call(api_key)
            except BYOKError as e:
                await self._handle_byok_failure(db, cred, e)
                await self._emit_use_audit(
                    db, cred, req_id, actor_id, ip_address, user_agent,
                    success=False, error_code=e.code,
                    retry_after=e.retry_after_seconds,
                )
                raise
            except Exception as e:
                # Adapter raised something un-normalized. Treat as server
                # error but still write the audit so operators can see it.
                logger.exception(
                    "gateway: unexpected exception from adapter for cred=%s: %s",
                    cred.id, e,
                )
                await self._emit_use_audit(
                    db, cred, req_id, actor_id, ip_address, user_agent,
                    success=False, error_code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
                )
                raise BYOKError(
                    code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
                    http_status=502,
                    retryable=False,
                ) from e

            # Pull token counts if the adapter exposes them (LLMResponse
            # from app.llm.types does; duck-typed here to avoid importing).
            input_tokens = int(getattr(response, "input_tokens", 0) or 0)
            output_tokens = int(getattr(response, "output_tokens", 0) or 0)

        # Success path: reset the breaker, touch timestamp, audit.
        self._reset_invalid_streak(cred.id)
        await self._touch_last_used(db, cred.id)
        await self._emit_use_audit(
            db, cred, req_id, actor_id, ip_address, user_agent,
            success=True, error_code=None,
            input_tokens=input_tokens, output_tokens=output_tokens,
            model=model,
        )
        return response

    # ---- failure handling helpers ------------------------------------------

    async def _handle_byok_failure(
        self,
        db: AsyncSession,
        cred: ResolvedCredential,
        err: BYOKError,
    ) -> None:
        """Apply gateway-level side effects for a normalized failure.

        * 401 ``credential_invalid`` -> bump invalid streak, trip circuit
          breaker if threshold reached (marks row invalid + clears cache).
        * 429 ``credential_rate_limited`` -> set cooldown so the next few
          requests for this credential short-circuit rather than hammer
          the provider.
        """
        if err.code == BYOKErrorCode.CREDENTIAL_INVALID:
            n = self._bump_invalid_streak(cred.id)
            threshold = max(1, settings.byok_invalid_circuit_breaker_threshold)
            if n >= threshold:
                await self._mark_invalid(
                    db,
                    cred,
                    f"provider rejected the key {n} consecutive times",
                )
            else:
                # Still below threshold — but don't let a cached invalid
                # key keep getting reused.
                self.invalidate_cache(cred.id)
        elif err.code == BYOKErrorCode.CREDENTIAL_RATE_LIMITED:
            # Honor Retry-After if given, otherwise 30s default.
            seconds = err.retry_after_seconds if err.retry_after_seconds is not None else 30.0
            self._set_cooldown(cred.id, seconds)

    async def _emit_use_audit(
        self,
        db: AsyncSession,
        cred: ResolvedCredential,
        request_id: str,
        actor_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
        *,
        success: bool,
        error_code: str | None,
        retry_after: float | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {}
        if input_tokens or output_tokens:
            metadata["input_tokens"] = input_tokens
            metadata["output_tokens"] = output_tokens
            if model:
                metadata["model"] = model
                metadata["estimated_cost_usd"] = round(
                    estimate_cost_usd(model, input_tokens, output_tokens), 6
                )
        if retry_after is not None:
            metadata["retry_after_seconds"] = retry_after

        entry = AuditEntry(
            user_id=cred.user_id,
            action=AuditAction.USE if success else AuditAction.USE_FAILED,
            success=success,
            credential_id=cred.id,
            credential_fingerprint=cred.key_fingerprint,
            actor_user_id=actor_id,
            provider=cred.provider,
            request_id=request_id,
            error_code=error_code,
            metadata=metadata or None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        # Fire-and-forget with a fresh session so the write can outlive
        # the request's own AsyncSession (FastAPI closes that on handler
        # return). Audit failures never bubble up to the user.
        schedule_audit(entry)


# Process-singleton. Routers and services import this.
gateway = BYOKGateway()
