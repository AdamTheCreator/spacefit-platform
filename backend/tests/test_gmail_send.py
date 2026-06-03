"""Unit tests for connected-Gmail outreach sending (Phase 3a).

The only piece that is cleanly testable without a live Gmail account is the
token loader ``get_user_gmail_tokens``: its branching is pure decision logic
over (a) whether the platform Google client is configured and (b) whether the
user has a usable ``OAuthAccount`` row.

Following the established convention (``test_memory_facts.py`` /
``test_ai_config.py``) these tests use stubbed ``AsyncSession`` objects via
``unittest.mock`` so they run in <1s without touching a real database.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import gmail as gmail_module
from app.services.gmail import GmailTokens, get_user_gmail_tokens


def _stub_db_returning(scalar_value) -> MagicMock:
    """AsyncSession-like mock whose ``execute`` yields a single result.

    The result's ``scalar_one_or_none`` returns ``scalar_value`` — mirroring
    the shape ``get_user_gmail_tokens`` consumes.
    """
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _make_oauth_account() -> SimpleNamespace:
    """A minimal stand-in for an ``OAuthAccount`` row (google provider)."""
    return SimpleNamespace(
        user_id="u1",
        provider="google",
        provider_account_id="acct-1",
        access_token="stored-access-token",
        refresh_token="stored-refresh-token",
        expires_at=datetime(2026, 6, 3, 12, 0, 0),
    )


@pytest.fixture
def configured_google(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the platform Google client credentials are configured."""
    monkeypatch.setattr(gmail_module.settings, "google_client_id", "cid")
    monkeypatch.setattr(gmail_module.settings, "google_client_secret", "secret")


@pytest.fixture
def unconfigured_google(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the platform Google client credentials are missing."""
    monkeypatch.setattr(gmail_module.settings, "google_client_id", "")
    monkeypatch.setattr(gmail_module.settings, "google_client_secret", "")


async def test_returns_none_when_no_matching_oauth_account(
    configured_google: None,
) -> None:
    # Credentials are configured, but the user has no connected Google
    # account -> the query yields no row -> ``None``.
    db = _stub_db_returning(None)

    tokens = await get_user_gmail_tokens(db, "u1")

    assert tokens is None
    db.execute.assert_awaited_once()


async def test_returns_none_when_google_client_not_configured(
    unconfigured_google: None,
) -> None:
    # Without platform Google credentials, no refresh/send could succeed, so
    # we short-circuit to ``None`` and never even hit the database.
    db = _stub_db_returning(_make_oauth_account())

    tokens = await get_user_gmail_tokens(db, "u1")

    assert tokens is None
    db.execute.assert_not_called()


async def test_builds_tokens_from_account_and_settings(
    configured_google: None,
) -> None:
    # Configured creds + a usable OAuthAccount -> a fully populated
    # ``GmailTokens``: access/refresh from the row, client id/secret from
    # settings, the constant Google token URI, and expiry from ``expires_at``.
    account = _make_oauth_account()
    db = _stub_db_returning(account)

    tokens = await get_user_gmail_tokens(db, "u1")

    assert isinstance(tokens, GmailTokens)
    assert tokens.access_token == "stored-access-token"
    assert tokens.refresh_token == "stored-refresh-token"
    assert tokens.client_id == "cid"
    assert tokens.client_secret == "secret"
    assert tokens.token_uri == gmail_module.GOOGLE_TOKEN_URI
    assert tokens.expiry == account.expires_at
