"""Unit tests for the Connect-Gmail OAuth flow (endpoints + signed state).

Following the established stubbed-``AsyncSession`` convention
(``test_gmail_send.py`` / ``test_outreach_send.py``) so these run in <1s
without Postgres or a live Google account.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api import auth as auth_module
from app.api.auth import (
    gmail_authorize,
    gmail_disconnect,
    gmail_status,
)
from app.core.security import create_oauth_state, verify_oauth_state


def _db_returning(scalar_value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


# --- signed state ----------------------------------------------------------


def test_oauth_state_roundtrips_user_id() -> None:
    token = create_oauth_state("user-123")
    assert verify_oauth_state(token) == "user-123"


def test_oauth_state_rejects_wrong_purpose() -> None:
    token = create_oauth_state("user-123", purpose="gmail_oauth")
    assert verify_oauth_state(token, purpose="something_else") is None


def test_oauth_state_rejects_garbage() -> None:
    assert verify_oauth_state("not-a-jwt") is None


# --- authorize -------------------------------------------------------------


async def test_authorize_501_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "is_gmail_configured", lambda: False)

    with pytest.raises(HTTPException) as exc:
        await gmail_authorize(SimpleNamespace(id="u1"))  # type: ignore[arg-type]
    assert exc.value.status_code == 501


async def test_authorize_returns_consent_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "is_gmail_configured", lambda: True)
    monkeypatch.setattr(
        auth_module.GmailService,
        "get_authorization_url",
        staticmethod(lambda state=None: ("https://consent.example/auth", state)),
    )

    resp = await gmail_authorize(SimpleNamespace(id="u1"))  # type: ignore[arg-type]
    assert resp.authorization_url == "https://consent.example/auth"


# --- status ----------------------------------------------------------------


async def test_status_not_connected() -> None:
    db = _db_returning(None)
    resp = await gmail_status(SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert resp.connected is False
    assert resp.email is None


async def test_status_connected_returns_email() -> None:
    account = SimpleNamespace(provider_account_id="broker@gmail.com")
    db = _db_returning(account)
    resp = await gmail_status(SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert resp.connected is True
    assert resp.email == "broker@gmail.com"


# --- disconnect ------------------------------------------------------------


async def test_disconnect_deletes_and_commits() -> None:
    db = _db_returning(None)
    await gmail_disconnect(SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
