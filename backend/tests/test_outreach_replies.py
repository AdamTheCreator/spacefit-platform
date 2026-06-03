"""Unit tests for outreach reply detection (Phase 3b).

The reply-sync path (``sync_replies_for_user``) is Gmail-dependent and cannot
be exercised without a live Google account / OAuth token, so it can't be
driven end-to-end in CI. The one branch that *is* cleanly testable without
Gmail is the early return: when ``get_user_gmail_tokens`` yields ``None``
(Gmail not connected, or the platform Google client is unconfigured) the
service must short-circuit to ``0`` and never touch the database or the
Gmail API.

Following the established convention (``test_gmail_send.py`` /
``test_ai_config.py``) this uses a stubbed ``AsyncSession`` via
``unittest.mock`` plus ``monkeypatch``, under ``asyncio_mode = "auto"``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import outreach_replies as replies_module
from app.services.outreach_replies import sync_replies_for_user


async def test_returns_zero_and_does_no_work_without_gmail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No connected/usable Gmail account -> token loader yields ``None``.
    async def _no_tokens(db, user_id):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(replies_module, "get_user_gmail_tokens", _no_tokens)

    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    user = SimpleNamespace(id="u1")

    new_replies = await sync_replies_for_user(db, user)

    # Clean, side-effect-free early return: no recipient query, no commit.
    assert new_replies == 0
    db.execute.assert_not_called()
    db.commit.assert_not_called()
