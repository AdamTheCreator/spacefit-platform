"""Tests for BYOKGateway.

These exercise the gateway's side-effect behavior without touching the
DB: resolution is mocked (the DB path is tested via an integration test
later), but decrypt/cache/cooldown/circuit-breaker/scope are all real.

The ``call(api_key)`` argument of :meth:`BYOKGateway.run_chat` is a
test-controlled async callable, so we can inject happy paths, 401s,
429s, and token counts without any real HTTP traffic.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.byok import crypto
from app.byok.errors import BYOKError, BYOKErrorCode
from app.byok.gateway import BYOKGateway, ResolvedCredential
from app.byok.scope import Scope


# ---- fixtures ---------------------------------------------------------------


@pytest.fixture
def plaintext_key() -> str:
    return "sk-test-gateway-abcdefghijklmnop"


@pytest.fixture
def bundle(plaintext_key: str) -> crypto.EnvelopeBundle:
    return crypto.encrypt_api_key(plaintext_key)


@pytest.fixture
def cred(bundle: crypto.EnvelopeBundle) -> ResolvedCredential:
    return ResolvedCredential(
        id="cred-1",
        user_id="user-1",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        base_url=None,
        specialist_models_json=None,
        key_fingerprint="fp-1",
        scope=Scope(),
        ciphertext=bundle.ciphertext,
        ciphertext_iv=bundle.iv,
        ciphertext_tag=bundle.auth_tag,
        encrypted_dek=bundle.encrypted_dek,
        kek_id=bundle.kek_id,
    )


@pytest.fixture
def fake_db() -> AsyncMock:
    """AsyncSession stand-in. execute/commit/rollback are AsyncMocks; the
    gateway only calls update(...) and fires detached audit writes
    (stubbed in the tests below)."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def stub_detached_audit(monkeypatch):
    """Never let the gateway actually schedule detached audit tasks
    during unit tests — the event loop closes between tests and would
    leave pending coroutines warnings."""
    # The gateway calls schedule_audit(entry). Replace with a sink that
    # records calls for assertions.
    calls: list = []
    monkeypatch.setattr(
        "app.byok.gateway.schedule_audit",
        lambda entry: calls.append(entry),
    )
    return calls


# ---- decrypt + cache --------------------------------------------------------


class TestDecryptAndCache:
    async def test_decrypt_roundtrip(self, cred, plaintext_key) -> None:
        gw = BYOKGateway()
        assert await gw.decrypt(cred) == plaintext_key

    async def test_second_decrypt_hits_cache(self, cred, plaintext_key, monkeypatch) -> None:
        gw = BYOKGateway()
        # First call populates the cache.
        await gw.decrypt(cred)

        # Now sabotage the crypto module; a second call should NOT re-call
        # the crypto primitives if the cache hit path is working.
        def boom(*args, **kwargs):
            raise AssertionError("crypto.decrypt_api_key called despite cache hit")

        monkeypatch.setattr("app.byok.gateway.crypto.decrypt_api_key", boom)
        assert await gw.decrypt(cred) == plaintext_key

    async def test_invalidate_cache_forces_redecrypt(self, cred) -> None:
        gw = BYOKGateway()
        await gw.decrypt(cred)
        gw.invalidate_cache(cred.id)
        # A second call succeeds — proves invalidation didn't wedge anything.
        assert await gw.decrypt(cred) is not None

    async def test_decrypt_tampered_ciphertext_raises_decrypt_failed(self, cred) -> None:
        tampered = ResolvedCredential(**{**cred.__dict__, "ciphertext": b"\x00" * len(cred.ciphertext)})
        gw = BYOKGateway()
        with pytest.raises(BYOKError) as info:
            await gw.decrypt(tampered)
        assert info.value.code == BYOKErrorCode.CREDENTIAL_DECRYPT_FAILED

    async def test_cache_ttl_zero_disables_cache(self, cred, monkeypatch, plaintext_key) -> None:
        monkeypatch.setattr("app.byok.gateway.settings.byok_decrypt_cache_ttl_seconds", 0)
        gw = BYOKGateway()
        await gw.decrypt(cred)
        # TTL=0 means the cache was never populated.
        assert gw._get_cached_key(cred.id) is None


# ---- cooldown ---------------------------------------------------------------


class TestCooldown:
    async def test_cooldown_short_circuits_before_call(self, fake_db, cred) -> None:
        gw = BYOKGateway()
        gw._set_cooldown(cred.id, seconds=30.0)

        async def call(api_key: str):
            raise AssertionError("should not be called during cooldown")

        with pytest.raises(BYOKError) as info:
            await gw.run_chat(fake_db, cred, call, model=cred.model or "")
        assert info.value.code == BYOKErrorCode.CREDENTIAL_RATE_LIMITED
        assert info.value.retry_after_seconds is not None

    async def test_cooldown_expires(self, cred) -> None:
        gw = BYOKGateway()
        gw._set_cooldown(cred.id, seconds=30.0)
        # Rewind the stamp to the past to simulate expiry without sleep.
        gw._cooldown_until[cred.id] = time.monotonic() - 1.0
        # Should not raise.
        gw._check_cooldown(cred.id)

    async def test_provider_429_sets_cooldown(self, fake_db, cred) -> None:
        gw = BYOKGateway()

        async def call(api_key: str):
            raise BYOKError.rate_limited(retry_after_seconds=42.0)

        with pytest.raises(BYOKError) as info:
            await gw.run_chat(fake_db, cred, call, model=cred.model or "")
        assert info.value.code == BYOKErrorCode.CREDENTIAL_RATE_LIMITED

        # Next call should be blocked by cooldown before reaching `call`.
        async def call2(api_key: str):
            raise AssertionError("cooldown not applied")

        with pytest.raises(BYOKError):
            await gw.run_chat(fake_db, cred, call2, model=cred.model or "")


# ---- circuit breaker --------------------------------------------------------


class TestCircuitBreaker:
    async def test_mark_invalid_after_threshold(
        self, fake_db, cred, monkeypatch, stub_detached_audit
    ) -> None:
        monkeypatch.setattr("app.byok.gateway.settings.byok_invalid_circuit_breaker_threshold", 3)
        gw = BYOKGateway()

        async def failing_call(api_key: str):
            raise BYOKError.credential_invalid()

        # 3 consecutive 401s. The third should trip the breaker.
        for _ in range(3):
            with pytest.raises(BYOKError):
                await gw.run_chat(fake_db, cred, failing_call, model=cred.model or "")

        # UPDATE user_ai_configs SET status='invalid' must have fired.
        assert fake_db.execute.await_count >= 1
        # An AUTO_INVALIDATE audit entry was scheduled.
        assert any(e.action == "credential.auto_invalidate" for e in stub_detached_audit)

    async def test_success_resets_streak(self, fake_db, cred, monkeypatch) -> None:
        monkeypatch.setattr("app.byok.gateway.settings.byok_invalid_circuit_breaker_threshold", 5)
        gw = BYOKGateway()

        async def failing(api_key: str):
            raise BYOKError.credential_invalid()

        # Two failures — not yet at threshold.
        for _ in range(2):
            with pytest.raises(BYOKError):
                await gw.run_chat(fake_db, cred, failing, model=cred.model or "")
        assert gw._invalid_streak.get(cred.id) == 2

        async def ok(api_key: str):
            return SimpleNamespace(input_tokens=10, output_tokens=20)

        await gw.run_chat(fake_db, cred, ok, model=cred.model or "")
        # Success resets the counter.
        assert cred.id not in gw._invalid_streak


# ---- scope ------------------------------------------------------------------


class TestScopeEnforcement:
    async def test_allowed_model_runs(self, fake_db, cred) -> None:
        cred_with_scope = ResolvedCredential(**{
            **cred.__dict__,
            "scope": Scope(allowed_models=[cred.model or ""]),
        })
        gw = BYOKGateway()

        async def ok(api_key: str):
            return SimpleNamespace(input_tokens=1, output_tokens=1)

        resp = await gw.run_chat(fake_db, cred_with_scope, ok, model=cred.model or "")
        assert getattr(resp, "input_tokens", None) == 1

    async def test_denied_model_raises_model_not_allowed(self, fake_db, cred) -> None:
        cred_with_scope = ResolvedCredential(**{
            **cred.__dict__,
            "scope": Scope(denied_models=[cred.model or ""]),
        })
        gw = BYOKGateway()

        async def call(api_key: str):
            raise AssertionError("dispatched despite scope deny")

        with pytest.raises(BYOKError) as info:
            await gw.run_chat(fake_db, cred_with_scope, call, model=cred.model or "")
        assert info.value.code == BYOKErrorCode.MODEL_NOT_ALLOWED

    async def test_model_not_in_allowlist_raises(self, fake_db, cred) -> None:
        cred_with_scope = ResolvedCredential(**{
            **cred.__dict__,
            "scope": Scope(allowed_models=["some-other-model"]),
        })
        gw = BYOKGateway()

        async def call(api_key: str):
            raise AssertionError("dispatched despite scope deny")

        with pytest.raises(BYOKError) as info:
            await gw.run_chat(fake_db, cred_with_scope, call, model=cred.model or "")
        assert info.value.code == BYOKErrorCode.MODEL_NOT_ALLOWED


# ---- happy path + audit -----------------------------------------------------


class TestHappyPath:
    async def test_run_chat_emits_use_audit_with_usage(
        self, fake_db, cred, stub_detached_audit
    ) -> None:
        gw = BYOKGateway()

        async def call(api_key: str):
            assert api_key  # decrypted plaintext reached the adapter
            return SimpleNamespace(input_tokens=100, output_tokens=50)

        resp = await gw.run_chat(fake_db, cred, call, model=cred.model or "")
        assert getattr(resp, "input_tokens") == 100

        use_entries = [e for e in stub_detached_audit if e.action == "credential.use"]
        assert len(use_entries) == 1
        assert use_entries[0].success is True
        assert use_entries[0].metadata["input_tokens"] == 100
        assert use_entries[0].metadata["output_tokens"] == 50
        assert use_entries[0].metadata["model"] == cred.model

    async def test_run_chat_emits_use_failed_audit_on_error(
        self, fake_db, cred, stub_detached_audit
    ) -> None:
        gw = BYOKGateway()

        async def call(api_key: str):
            raise BYOKError(
                code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
                http_status=502,
                retryable=True,
            )

        with pytest.raises(BYOKError):
            await gw.run_chat(fake_db, cred, call, model=cred.model or "")

        failed = [e for e in stub_detached_audit if e.action == "credential.use_failed"]
        assert len(failed) == 1
        assert failed[0].error_code == BYOKErrorCode.PROVIDER_SERVER_ERROR

    async def test_per_credential_semaphore_is_used(self, fake_db, cred) -> None:
        gw = BYOKGateway()
        sem_a = gw._semaphore_for(cred.id)
        sem_b = gw._semaphore_for(cred.id)
        # Same id → same semaphore object.
        assert sem_a is sem_b

        sem_other = gw._semaphore_for("different-cred")
        assert sem_other is not sem_a
