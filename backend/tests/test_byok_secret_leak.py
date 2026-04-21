"""Proves BYOK key material never reaches logs.

The test installs the secret-scrubbing filter, feeds a test key through
every code path that could plausibly log it — the crypto primitives,
the error mappers, the gateway's decrypt + run_chat wrappers, even the
regex redactor directly — and asserts that the key substring appears
nowhere in captured log output.

If this test ever fails, *stop and investigate before merging*. A leak
into a production log aggregator is hard to roll back — everything the
aggregator indexed may have to be rotated.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.byok import crypto
from app.byok.errors import BYOKError, BYOKErrorCode, map_anthropic_exception
from app.byok.gateway import BYOKGateway, ResolvedCredential
from app.byok.scope import Scope
from app.core.scrubbing import install_scrubbing_filter
from app.llm.redaction import redact_secrets


# A distinctive test key that wouldn't appear anywhere else in this codebase.
# Uses the Anthropic prefix so the redaction regex recognises it.
LEAK_PROBE = "sk-ant-byok-leak-probe-ZZZZZZZZZZZZZZZZZZZZZZZZZZ"


@pytest.fixture
def captured_logs(caplog, monkeypatch):
    """Ensure the scrubbing filter is installed and every log record is
    funnelled through :func:`redact_secrets` before ``caplog`` sees it.

    Pytest's caplog attaches its own handler; we attach the filter to
    that handler explicitly so the captured records reflect what any
    real handler would see.
    """
    install_scrubbing_filter()
    from app.core.scrubbing import _SecretScrubFilter

    caplog.handler.addFilter(_SecretScrubFilter())
    caplog.set_level(logging.DEBUG)
    return caplog


def _assert_no_leak(captured_logs, *extra_strings: str) -> None:
    """Fail if the probe (or any other forbidden string) appears in
    captured log text. Central so the assertion message is consistent."""
    combined = captured_logs.text
    for forbidden in (LEAK_PROBE, *extra_strings):
        assert forbidden not in combined, (
            f"Secret leaked into logs: {forbidden!r} appeared in captured output.\n"
            f"Full captured log:\n{combined}"
        )


# --- direct primitives ---------------------------------------------------------


def test_redact_secrets_masks_probe() -> None:
    """Sanity check: the regex actually recognises our probe shape."""
    masked = redact_secrets(f"got key {LEAK_PROBE} from env")
    assert LEAK_PROBE not in masked
    assert "[REDACTED]" in masked


def test_crypto_roundtrip_does_not_log_plaintext(captured_logs) -> None:
    logger = logging.getLogger("byok.test")
    logger.info("encrypting key=%s", LEAK_PROBE)  # simulated accidental log
    bundle = crypto.encrypt_api_key(LEAK_PROBE)
    assert crypto.decrypt_api_key(bundle) == LEAK_PROBE
    _assert_no_leak(captured_logs)


def test_crypto_tamper_error_does_not_log_plaintext(captured_logs) -> None:
    logger = logging.getLogger("byok.test")
    bundle = crypto.encrypt_api_key(LEAK_PROBE)
    tampered = crypto.EnvelopeBundle(
        ciphertext=b"\x00" * len(bundle.ciphertext),
        iv=bundle.iv,
        auth_tag=bundle.auth_tag,
        encrypted_dek=bundle.encrypted_dek,
        kek_id=bundle.kek_id,
    )
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_api_key(tampered)
    logger.exception("envelope tamper (probe=%s)", LEAK_PROBE)
    _assert_no_leak(captured_logs)


# --- provider error mapping ---------------------------------------------------


def test_anthropic_error_mapper_does_not_surface_plaintext(captured_logs) -> None:
    # Build a fake SDK exception whose message embeds the probe.
    logger = logging.getLogger("byok.test")
    FakeAuth = type("AuthenticationError", (Exception,), {})
    exc = FakeAuth(f"401: bad key {LEAK_PROBE}")
    exc.status_code = 401  # type: ignore[attr-defined]

    mapped = map_anthropic_exception(exc)
    assert mapped.code == BYOKErrorCode.CREDENTIAL_INVALID
    # The user-facing message must be the safe default, not the
    # provider string that had the key in it.
    assert LEAK_PROBE not in mapped.message

    logger.exception("provider returned %s", exc)
    _assert_no_leak(captured_logs)


# --- gateway wrapper ----------------------------------------------------------


@pytest.fixture
def cred_with_probe() -> ResolvedCredential:
    bundle = crypto.encrypt_api_key(LEAK_PROBE)
    return ResolvedCredential(
        id="cred-leak",
        user_id="user-1",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        base_url=None,
        specialist_models_json=None,
        key_fingerprint=crypto.fingerprint(LEAK_PROBE),
        scope=Scope(),
        ciphertext=bundle.ciphertext,
        ciphertext_iv=bundle.iv,
        ciphertext_tag=bundle.auth_tag,
        encrypted_dek=bundle.encrypted_dek,
        kek_id=bundle.kek_id,
    )


@pytest.fixture
def fake_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def stub_detached_audit(monkeypatch):
    monkeypatch.setattr("app.byok.gateway.schedule_audit", lambda entry: None)


async def test_gateway_successful_chat_does_not_log_plaintext(
    captured_logs, fake_db, cred_with_probe
) -> None:
    gw = BYOKGateway()

    seen_key: list[str] = []

    async def adapter_call(api_key: str):
        # Confirm the plaintext key did reach the adapter — that's the
        # whole point of the envelope — then swallow.
        seen_key.append(api_key)
        return SimpleNamespace(input_tokens=3, output_tokens=4)

    await gw.run_chat(
        fake_db,
        cred_with_probe,
        adapter_call,
        model=cred_with_probe.model or "",
    )
    assert seen_key == [LEAK_PROBE]  # delivered to adapter…
    _assert_no_leak(captured_logs)  # …but never to logs.


async def test_gateway_failed_chat_does_not_log_plaintext(
    captured_logs, fake_db, cred_with_probe
) -> None:
    gw = BYOKGateway()

    async def adapter_call(api_key: str):
        # Adapter raises; gateway catches and classifies. The exception
        # str includes the probe to simulate a careless adapter.
        raise BYOKError(
            code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
            http_status=502,
            retryable=False,
            message=f"boom (key={LEAK_PROBE})",  # careless but possible
        )

    with pytest.raises(BYOKError):
        await gw.run_chat(
            fake_db,
            cred_with_probe,
            adapter_call,
            model=cred_with_probe.model or "",
        )
    _assert_no_leak(captured_logs)


async def test_gateway_decrypt_failure_scrubbed(
    captured_logs, fake_db
) -> None:
    gw = BYOKGateway()

    # Construct a credential that will fail envelope decryption.
    bundle = crypto.encrypt_api_key(LEAK_PROBE)
    broken = ResolvedCredential(
        id="cred-broken",
        user_id="user-1",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        base_url=None,
        specialist_models_json=None,
        key_fingerprint=None,
        scope=Scope(),
        ciphertext=b"\x00" * len(bundle.ciphertext),  # tampered
        ciphertext_iv=bundle.iv,
        ciphertext_tag=bundle.auth_tag,
        encrypted_dek=bundle.encrypted_dek,
        kek_id=bundle.kek_id,
    )
    with pytest.raises(BYOKError):
        await gw.decrypt(broken)
    _assert_no_leak(captured_logs)
