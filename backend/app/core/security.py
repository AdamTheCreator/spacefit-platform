import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from jose import JWTError, jwt
from passlib.context import CryptContext
import base64

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """Create a refresh token and return (token, token_hash) tuple."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    expires = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    to_encode = {
        "sub": str(user_id),
        "exp": expires,
        "type": "refresh",
        "jti": token_hash[:16],
    }
    encoded_token = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
    )

    return encoded_token, token_hash


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return the payload if valid."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


def get_token_hash(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _get_encryption_key(user_salt: bytes | None = None) -> bytes:
    """Derive an encryption key from the master key and optional user salt."""
    master_key = settings.encryption_master_key.encode()

    if user_salt:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=user_salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key))
    else:
        key = base64.urlsafe_b64encode(master_key[:32].ljust(32, b"0"))

    return key


def encrypt_credential(plaintext: str, user_salt: bytes | None = None) -> bytes:
    """Encrypt a credential using AES-256 (Fernet)."""
    key = _get_encryption_key(user_salt)
    f = Fernet(key)
    return f.encrypt(plaintext.encode())


def decrypt_credential(ciphertext: bytes, user_salt: bytes | None = None) -> str:
    """Decrypt a credential."""
    key = _get_encryption_key(user_salt)
    f = Fernet(key)
    return f.decrypt(ciphertext).decode()


def generate_user_salt() -> bytes:
    """Generate a random salt for user-specific encryption."""
    return secrets.token_bytes(16)
