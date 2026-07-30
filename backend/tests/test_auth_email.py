"""Phase 1 auth-incident regressions.

Two behaviours guarded here, both root causes of the tester lockout:

1. Email normalization — signup/login/reset must canonicalize email
   identically (trim + lowercase) so a differing casing can't silently
   fail to match the stored record.
2. Email sends must never fail silently — a failed provider send logs a
   structured error, and the reset path stays enumeration-safe (no send,
   no raise) for unknown addresses.

DB is stubbed (mirroring test_memory_facts.py) so these run in <1s.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import (
    ForgotPasswordRequest,
    LoginRequest,
    UserCreate,
    normalize_email,
)
from app.services.auth import AuthService


class TestNormalizeEmail:
    def test_lowercases_and_trims(self) -> None:
        assert normalize_email("  Tester@Example.COM ") == "tester@example.com"

    def test_idempotent(self) -> None:
        once = normalize_email("User@Host.com")
        assert normalize_email(once) == once


class TestSchemaNormalization:
    def test_user_create_normalizes(self) -> None:
        u = UserCreate(email="Tester@Example.com", password="password123")
        assert u.email == "tester@example.com"

    def test_login_request_normalizes(self) -> None:
        # Login casing differs from signup casing -> must still match.
        assert LoginRequest(email="TESTER@EXAMPLE.COM", password="x").email == (
            "tester@example.com"
        )

    def test_forgot_password_normalizes(self) -> None:
        assert ForgotPasswordRequest(email="  Tester@Example.com ").email == (
            "tester@example.com"
        )


def _stub_db(user: object | None) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


class TestSendPasswordResetObservability:
    @pytest.mark.asyncio
    async def test_logs_error_when_send_fails(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = SimpleNamespace(id="u1", email="tester@example.com", first_name="Tess")
        db = _stub_db(user)
        send = AsyncMock(return_value=False)
        monkeypatch.setattr("app.services.auth.send_password_reset_email", send)

        service = AuthService(db)
        with caplog.at_level(logging.ERROR):
            await service.send_password_reset("tester@example.com")

        send.assert_awaited_once()
        assert any("auth.email.send_failed" in r.message for r in caplog.records)
        assert any("event=password_reset" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_no_leak_of_token_or_email_in_logs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = SimpleNamespace(id="u1", email="tester@example.com", first_name="Tess")
        db = _stub_db(user)
        monkeypatch.setattr(
            "app.services.auth.send_password_reset_email",
            AsyncMock(return_value=False),
        )

        service = AuthService(db)
        with caplog.at_level(logging.ERROR):
            await service.send_password_reset("tester@example.com")

        for record in caplog.records:
            assert "tester@example.com" not in record.message
            assert "token=" not in record.message

    @pytest.mark.asyncio
    async def test_unknown_email_is_enumeration_safe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = _stub_db(None)
        send = AsyncMock(return_value=True)
        monkeypatch.setattr("app.services.auth.send_password_reset_email", send)

        service = AuthService(db)
        # No user -> returns silently, no send, no raise.
        await service.send_password_reset("nobody@example.com")

        send.assert_not_awaited()
        db.add.assert_not_called()
