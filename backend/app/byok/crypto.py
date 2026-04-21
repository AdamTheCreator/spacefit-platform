"""Envelope encryption for BYOK credentials.

The shape is a classic two-tier envelope, implemented in-process because the
platform doesn't have AWS KMS in the stack today:

    plaintext api key
      ── AES-256-GCM(DEK, iv) ─→ ciphertext + auth_tag        (stored)
    DEK (random 32 bytes, per credential)
      ── Fernet(KEK_<id>) ──────→ encrypted_dek               (stored)
    KEK_<id>
      ── PBKDF2-SHA256(secret, salt=sha256('byok-kek-'+id)) → Fernet key

Each credential row therefore stores five fields:

    api_key_encrypted  — AES-GCM ciphertext of the API key (DEK-keyed)
    ciphertext_iv      — 12-byte random IV used for that encryption
    ciphertext_tag     — 16-byte GCM auth tag
    encrypted_dek      — DEK, wrapped with the KEK identified by kek_id
    kek_id             — identifier of the KEK that wrapped the DEK

Revocation = set all five to NULL in one UPDATE (crypto-shred per credential).
KEK rotation = publish a new `byok_kek_<new_id>` env var, flip
`byok_kek_primary_id`, and run a background job that re-wraps every DEK under
the new KEK. Old KEK env vars stay around until the job completes.

This module is stateless except for a tiny module-level KEK-key cache — the
PBKDF2 derivation is done once per kek_id at first use and memoized. Nothing
in this module logs plaintext key material.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Final

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

__all__ = [
    "EnvelopeBundle",
    "encrypt_api_key",
    "decrypt_api_key",
    "fingerprint",
    "last_four",
    "primary_kek_id",
    "rewrap_dek",
    "UnknownKEKError",
    "CryptoError",
]


# Matching the iteration count already used by app.core.security._get_encryption_key
# is a design choice: keeps the KDF cost consistent across the two systems
# during the migration window, and doesn't drop the security ceiling.
_PBKDF2_ITERATIONS: Final[int] = 200_000
# AES-GCM requires a 96-bit nonce for interoperability.
_GCM_IV_SIZE: Final[int] = 12
_DEK_SIZE: Final[int] = 32


class CryptoError(Exception):
    """Any envelope-crypto failure the gateway should surface as
    ``credential_decrypt_failed``."""


class UnknownKEKError(CryptoError):
    """Raised when a credential row references a kek_id that isn't
    configured (env var missing, typo, or decommissioned after rotation)."""


@dataclass(frozen=True)
class EnvelopeBundle:
    """All fields that together reconstruct a plaintext API key."""

    ciphertext: bytes
    iv: bytes
    auth_tag: bytes
    encrypted_dek: bytes
    kek_id: str


# --- KEK registry ------------------------------------------------------------


def _kek_secret(kek_id: str) -> str:
    """Return the raw secret material for a given KEK id.

    ``v1`` falls back to ``encryption_master_key`` when no explicit override
    is set, so deployments that haven't yet populated ``byok_kek_v1`` keep
    working on the same key material they used before the rebuild.
    """
    attr = f"byok_kek_{kek_id}"
    secret = getattr(settings, attr, "") or ""
    if secret:
        return secret
    if kek_id == "v1":
        return settings.encryption_master_key
    raise UnknownKEKError(
        f"KEK id {kek_id!r} is not configured (expected env var BYOK_KEK_{kek_id.upper()})"
    )


def _derive_kek_fernet_key(kek_id: str) -> bytes:
    """Derive a Fernet-compatible key from the named KEK.

    Salt is deterministic per kek_id so the same secret yields the same
    Fernet key every process startup; rotating the kek_id produces a
    different key from the same secret material. PBKDF2 is run once per
    kek_id per process (see ``_KEK_KEY_CACHE``).
    """
    secret = _kek_secret(kek_id)
    salt = hashlib.sha256(f"byok-kek-{kek_id}".encode("utf-8")).digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    raw = kdf.derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


_KEK_KEY_CACHE: dict[str, bytes] = {}


def _fernet_for_kek(kek_id: str) -> Fernet:
    key = _KEK_KEY_CACHE.get(kek_id)
    if key is None:
        key = _derive_kek_fernet_key(kek_id)
        _KEK_KEY_CACHE[kek_id] = key
    return Fernet(key)


def primary_kek_id() -> str:
    """The kek_id new credentials should be wrapped under right now."""
    return settings.byok_kek_primary_id


# --- public API --------------------------------------------------------------


def encrypt_api_key(api_key: str, kek_id: str | None = None) -> EnvelopeBundle:
    """Envelope-encrypt a plaintext API key.

    Generates a fresh 32-byte DEK and a fresh 12-byte IV, AES-GCM-encrypts
    the key under the DEK, and wraps the DEK under the configured KEK
    (defaulting to the current primary). Callers get back the five fields
    that must be persisted together.

    The plaintext ``api_key`` argument is not held by this module after the
    call returns. Callers should avoid logging it and drop references as
    soon as possible.
    """
    if not api_key:
        raise CryptoError("api_key must be non-empty")

    target_kek = kek_id or primary_kek_id()

    dek = secrets.token_bytes(_DEK_SIZE)
    iv = secrets.token_bytes(_GCM_IV_SIZE)
    aesgcm = AESGCM(dek)
    # AESGCM.encrypt returns ciphertext||tag (last 16 bytes). Split so the
    # DB schema can store the two fields separately, matching the spec.
    combined = aesgcm.encrypt(iv, api_key.encode("utf-8"), associated_data=None)
    ciphertext, tag = combined[:-16], combined[-16:]

    fernet = _fernet_for_kek(target_kek)
    encrypted_dek = fernet.encrypt(dek)

    # Best-effort scrub of the DEK from our local scope.
    dek = b"\x00" * _DEK_SIZE  # noqa: F841

    return EnvelopeBundle(
        ciphertext=ciphertext,
        iv=iv,
        auth_tag=tag,
        encrypted_dek=encrypted_dek,
        kek_id=target_kek,
    )


def decrypt_api_key(bundle: EnvelopeBundle) -> str:
    """Recover the plaintext API key from an envelope bundle.

    Raises :class:`CryptoError` on any tampering (GCM auth-tag mismatch,
    corrupt ciphertext, or unknown kek_id). Callers should treat this as
    ``credential_decrypt_failed`` and surface a generic error — never leak
    the exception message back to end users.
    """
    fernet = _fernet_for_kek(bundle.kek_id)
    try:
        dek = fernet.decrypt(bundle.encrypted_dek)
    except InvalidToken as exc:
        raise CryptoError("DEK unwrap failed (wrong KEK or tampered)") from exc

    aesgcm = AESGCM(dek)
    try:
        plaintext = aesgcm.decrypt(
            bundle.iv,
            bundle.ciphertext + bundle.auth_tag,
            associated_data=None,
        )
    except Exception as exc:  # includes InvalidTag
        # Best-effort DEK scrub before re-raising.
        dek = b"\x00" * _DEK_SIZE  # noqa: F841
        raise CryptoError("ciphertext decryption failed") from exc

    dek = b"\x00" * _DEK_SIZE  # noqa: F841
    return plaintext.decode("utf-8")


def rewrap_dek(bundle: EnvelopeBundle, new_kek_id: str | None = None) -> EnvelopeBundle:
    """Re-wrap an existing envelope's DEK under a new KEK without touching
    the ciphertext. Used by the KEK-rotation background job.

    This function unwraps the DEK with the current ``bundle.kek_id``, then
    re-wraps it with ``new_kek_id`` (or the current primary). The AES-GCM
    ciphertext, IV, and auth tag stay byte-identical — only
    ``encrypted_dek`` and ``kek_id`` change. Result: KEK rotation is O(N)
    in the number of credentials but doesn't re-run AES-GCM.
    """
    target = new_kek_id or primary_kek_id()
    if target == bundle.kek_id:
        return bundle

    old_fernet = _fernet_for_kek(bundle.kek_id)
    try:
        dek = old_fernet.decrypt(bundle.encrypted_dek)
    except InvalidToken as exc:
        raise CryptoError("cannot rewrap: old KEK unwrap failed") from exc

    new_fernet = _fernet_for_kek(target)
    new_encrypted_dek = new_fernet.encrypt(dek)

    dek = b"\x00" * _DEK_SIZE  # noqa: F841

    return EnvelopeBundle(
        ciphertext=bundle.ciphertext,
        iv=bundle.iv,
        auth_tag=bundle.auth_tag,
        encrypted_dek=new_encrypted_dek,
        kek_id=target,
    )


def fingerprint(api_key: str) -> str:
    """Deterministic SHA-256 fingerprint of a plaintext API key.

    Used for duplicate detection at submission time and for audit-log
    linkage after a credential row is deleted. Hex-encoded, 64 chars.
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def last_four(api_key: str) -> str:
    """Return the last 4 characters of the key for UI display.

    Safe to expose in responses — four characters of a random-looking
    secret don't meaningfully reduce entropy. Used on the Settings page
    to tell rotated keys apart.
    """
    if len(api_key) < 4:
        return api_key
    return api_key[-4:]
