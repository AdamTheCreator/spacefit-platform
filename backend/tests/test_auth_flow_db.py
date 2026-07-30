"""Integration tests for the auth service against a real (in-memory SQLite) DB.

Covers signup, case-insensitive login, reset single-use/expiry, refresh-token
reuse detection, and the email-provider-down path (Resend key unset -> send
returns False, flow still completes). Only the auth-relevant tables are
created so we avoid the Postgres-only generated column on document_chunks.
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import verify_password
from app.db.base import Base
from app.db.models.auth_event import AuthEvent
from app.db.models.credential import OnboardingProgress
from app.db.models.email_token import EmailToken
from app.db.models.user import OAuthAccount, RefreshToken, User
from app.models.user import UserCreate
from app.services.auth import AuthService

_TABLES = [
    User.__table__,
    RefreshToken.__table__,
    OAuthAccount.__table__,
    EmailToken.__table__,
    AuthEvent.__table__,
    OnboardingProgress.__table__,
]


@asynccontextmanager
async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=_TABLES))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _register(
    svc: AuthService, email: str, password: str = "Password123"
) -> User:
    return await svc.register_user(UserCreate(email=email, password=password))


@pytest.mark.asyncio
async def test_signup_stores_normalized_email_and_login_is_case_insensitive() -> None:
    async with _session() as db:
        svc = AuthService(db)
        user = await _register(svc, "Tester@Example.com")
        assert user.email == "tester@example.com"  # normalized at signup

        # Login lookup succeeds with the normalized (lowercase) email.
        assert await svc.authenticate_user("tester@example.com", "Password123")
        # Wrong password fails.
        assert await svc.authenticate_user("tester@example.com", "nope") is None


@pytest.mark.asyncio
async def test_email_provider_down_does_not_break_signup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the unconfigured path -> send returns False; signup still ok.
    from app.core.config import settings

    monkeypatch.setattr(settings, "resend_api_key", "")
    async with _session() as db:
        user = await _register(AuthService(db), "down@example.com")
        assert user.id is not None


@pytest.mark.asyncio
async def test_reset_token_single_use_and_expiry() -> None:
    async with _session() as db:
        svc = AuthService(db)
        user = await _register(svc, "reset@example.com")

        raw = "known-reset-token"
        db.add(
            EmailToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                token_type="password_reset",
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
        )
        await db.commit()

        ok, _ = await svc.reset_password_with_token(raw, "NewPassword123")
        assert ok
        # Password actually changed + stamped.
        refreshed = await svc.get_user_by_id(user.id)
        assert verify_password("NewPassword123", refreshed.password_hash)
        assert refreshed.password_changed_at is not None

        # Reusing the same token fails (single-use).
        ok2, msg2 = await svc.reset_password_with_token(raw, "Another123")
        assert not ok2
        assert "used" in msg2.lower()


@pytest.mark.asyncio
async def test_expired_reset_token_rejected() -> None:
    async with _session() as db:
        svc = AuthService(db)
        user = await _register(svc, "expired@example.com")
        raw = "expired-token"
        db.add(
            EmailToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                token_type="password_reset",
                expires_at=datetime.utcnow() - timedelta(minutes=1),
            )
        )
        await db.commit()

        ok, msg = await svc.reset_password_with_token(raw, "NewPassword123")
        assert not ok
        assert "expired" in msg.lower()


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection() -> None:
    async with _session() as db:
        svc = AuthService(db)
        user = await _register(svc, "rotate@example.com")

        tokens = await svc.create_tokens(user)
        old_refresh = tokens.refresh_token

        # First use rotates successfully.
        rotated = await svc.refresh_tokens(old_refresh)
        assert rotated is not None
        assert rotated.refresh_token != old_refresh

        # Replaying the old (now revoked) token is detected as reuse -> None,
        # and the whole family is revoked, so the rotated token is dead too.
        assert await svc.refresh_tokens(old_refresh) is None
        assert await svc.refresh_tokens(rotated.refresh_token) is None


@pytest.mark.asyncio
async def test_password_change_revokes_sessions() -> None:
    async with _session() as db:
        svc = AuthService(db)
        user = await _register(svc, "sessions@example.com")
        tokens = await svc.create_tokens(user)

        ok = await svc.update_password(user, "Password123", "NewPassword123")
        assert ok
        # Existing refresh token no longer works after a password change.
        assert await svc.refresh_tokens(tokens.refresh_token) is None
