"""Tests for the envelope crypto primitives.

These tests must not depend on any external service (no DB, no network).
The crypto module is the security foundation for BYOK — any regression
here would leak or lose key material, so the roundtrip + tamper checks
must always pass.
"""

from __future__ import annotations

import pytest

from app.byok import crypto
from app.byok.crypto import (
    CryptoError,
    EnvelopeBundle,
    UnknownKEKError,
    decrypt_api_key,
    encrypt_api_key,
    fingerprint,
    last_four,
    rewrap_dek,
)


class TestRoundtrip:
    def test_simple_key_roundtrip(self) -> None:
        plaintext = "sk-test-abcdefghijklmnopqrstuvwx"
        bundle = encrypt_api_key(plaintext)
        recovered = decrypt_api_key(bundle)
        assert recovered == plaintext

    def test_empty_key_rejected(self) -> None:
        with pytest.raises(CryptoError):
            encrypt_api_key("")

    def test_long_key_roundtrip(self) -> None:
        plaintext = "sk-ant-" + "A" * 1000  # far larger than realistic keys
        bundle = encrypt_api_key(plaintext)
        assert decrypt_api_key(bundle) == plaintext

    def test_unicode_key_roundtrip(self) -> None:
        # No real provider uses non-ASCII but the primitive must be utf-8 safe.
        plaintext = "sk-测试-🔑-test"
        bundle = encrypt_api_key(plaintext)
        assert decrypt_api_key(bundle) == plaintext


class TestBundleFields:
    def test_bundle_has_all_fields(self) -> None:
        bundle = encrypt_api_key("sk-test-zzzzzzzzzzzzzzzzzzzzzz")
        assert len(bundle.iv) == 12, "AES-GCM requires a 12-byte IV"
        assert len(bundle.auth_tag) == 16, "AES-GCM auth tag is 16 bytes"
        assert len(bundle.ciphertext) > 0
        assert len(bundle.encrypted_dek) > 0
        assert bundle.kek_id  # some non-empty id

    def test_encryption_is_non_deterministic(self) -> None:
        # Two encryptions of the same plaintext must produce different
        # ciphertexts (different DEK + IV each time).
        plaintext = "sk-test-abcdefghijklmnopqrstuvwx"
        a = encrypt_api_key(plaintext)
        b = encrypt_api_key(plaintext)
        assert a.ciphertext != b.ciphertext
        assert a.iv != b.iv
        assert a.encrypted_dek != b.encrypted_dek


class TestTamperDetection:
    def _base(self) -> tuple[str, EnvelopeBundle]:
        plaintext = "sk-test-abcdefghijklmnopqrstuvwx"
        return plaintext, encrypt_api_key(plaintext)

    def test_ciphertext_tamper_detected(self) -> None:
        _, bundle = self._base()
        bad = EnvelopeBundle(
            ciphertext=b"\x00" + bundle.ciphertext[1:],
            iv=bundle.iv,
            auth_tag=bundle.auth_tag,
            encrypted_dek=bundle.encrypted_dek,
            kek_id=bundle.kek_id,
        )
        with pytest.raises(CryptoError):
            decrypt_api_key(bad)

    def test_auth_tag_tamper_detected(self) -> None:
        _, bundle = self._base()
        bad = EnvelopeBundle(
            ciphertext=bundle.ciphertext,
            iv=bundle.iv,
            auth_tag=b"\x00" * 16,
            encrypted_dek=bundle.encrypted_dek,
            kek_id=bundle.kek_id,
        )
        with pytest.raises(CryptoError):
            decrypt_api_key(bad)

    def test_iv_tamper_detected(self) -> None:
        _, bundle = self._base()
        bad = EnvelopeBundle(
            ciphertext=bundle.ciphertext,
            iv=b"\x00" * 12,
            auth_tag=bundle.auth_tag,
            encrypted_dek=bundle.encrypted_dek,
            kek_id=bundle.kek_id,
        )
        with pytest.raises(CryptoError):
            decrypt_api_key(bad)

    def test_encrypted_dek_tamper_detected(self) -> None:
        _, bundle = self._base()
        bad = EnvelopeBundle(
            ciphertext=bundle.ciphertext,
            iv=bundle.iv,
            auth_tag=bundle.auth_tag,
            encrypted_dek=bundle.encrypted_dek[:-1] + bytes([bundle.encrypted_dek[-1] ^ 0x01]),
            kek_id=bundle.kek_id,
        )
        with pytest.raises(CryptoError):
            decrypt_api_key(bad)


class TestKEKRotation:
    def test_rewrap_preserves_plaintext(self, monkeypatch) -> None:
        # Arrange: encrypt under v1, then rotate to v2.
        monkeypatch.setattr(crypto.settings, "byok_kek_v1", "kek-one-secret-material")
        monkeypatch.setattr(crypto.settings, "byok_kek_v2", "kek-two-different-material")
        monkeypatch.setattr(crypto.settings, "byok_kek_primary_id", "v1")
        crypto._KEK_KEY_CACHE.clear()

        plaintext = "sk-test-rotation-abcdefghijklmno"
        bundle_v1 = encrypt_api_key(plaintext)
        assert bundle_v1.kek_id == "v1"

        bundle_v2 = rewrap_dek(bundle_v1, new_kek_id="v2")
        assert bundle_v2.kek_id == "v2"
        # Ciphertext/IV/tag unchanged — rotation only touches the DEK wrap.
        assert bundle_v2.ciphertext == bundle_v1.ciphertext
        assert bundle_v2.iv == bundle_v1.iv
        assert bundle_v2.auth_tag == bundle_v1.auth_tag
        assert bundle_v2.encrypted_dek != bundle_v1.encrypted_dek

        # Plaintext still recoverable after rotation.
        assert decrypt_api_key(bundle_v2) == plaintext

    def test_rewrap_noop_when_target_matches(self, monkeypatch) -> None:
        monkeypatch.setattr(crypto.settings, "byok_kek_primary_id", "v1")
        bundle = encrypt_api_key("sk-test-keep-same-kek-ab")
        same = rewrap_dek(bundle, new_kek_id=bundle.kek_id)
        assert same is bundle

    def test_decrypt_unknown_kek_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(crypto.settings, "byok_kek_v1", "")
        monkeypatch.setattr(crypto.settings, "byok_kek_v2", "")
        monkeypatch.setattr(crypto.settings, "byok_kek_primary_id", "v1")
        monkeypatch.setattr(crypto.settings, "encryption_master_key", "ok-fallback")
        crypto._KEK_KEY_CACHE.clear()

        bundle = encrypt_api_key("sk-test-abcdefghijklmnopqrstuvwx")
        nuked = EnvelopeBundle(
            ciphertext=bundle.ciphertext,
            iv=bundle.iv,
            auth_tag=bundle.auth_tag,
            encrypted_dek=bundle.encrypted_dek,
            kek_id="vDECOMMISSIONED",
        )
        with pytest.raises(UnknownKEKError):
            decrypt_api_key(nuked)


class TestFingerprintAndDisplay:
    def test_fingerprint_deterministic(self) -> None:
        k = "sk-test-abcdefghijklmnopqrstuvwx"
        assert fingerprint(k) == fingerprint(k)

    def test_fingerprint_differs_for_different_keys(self) -> None:
        assert fingerprint("sk-a") != fingerprint("sk-b")

    def test_fingerprint_hex_64_chars(self) -> None:
        fp = fingerprint("sk-test-abcdefghijklmnopqrstuvwx")
        assert len(fp) == 64
        int(fp, 16)  # should not raise

    def test_last_four(self) -> None:
        assert last_four("sk-test-abcdefgh1234") == "1234"
        assert last_four("abc") == "abc"  # shorter than 4 returns the whole thing
