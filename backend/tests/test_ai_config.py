"""Regression tests for the /ai-config router.

Covers the two root causes of the Settings-page 500s:

1. ``_get_active_ai_config`` swallowing SQLAlchemy errors (e.g., a missing
   ``status`` column on legacy databases) instead of 500ing the request.
2. ``_effective_provider_model`` returning sensible tier defaults without
   relying on a live DB session — so the handler doesn't need to lazy-load
   ``current_user.subscription`` mid-response.

These are pure unit tests — no live DB, no FastAPI TestClient. The handler
path is covered indirectly by exercising both helpers directly.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.api.ai_config import _effective_provider_model, _get_active_ai_config

# --- _effective_provider_model ---------------------------------------------


class TestEffectiveProviderModel:
    def test_no_config_free_tier_defaults_to_google(self) -> None:
        provider, model = _effective_provider_model(None, "free")
        assert provider == "google"
        assert model == "gemini-2.0-flash"

    def test_no_config_individual_tier_defaults_to_anthropic(self) -> None:
        provider, model = _effective_provider_model(None, "individual")
        assert provider == "anthropic"
        assert model

    def test_no_config_enterprise_tier_defaults_to_anthropic(self) -> None:
        provider, model = _effective_provider_model(None, "enterprise")
        assert provider == "anthropic"
        assert model

    def test_valid_byok_config_wins_over_tier_default(self) -> None:
        config = SimpleNamespace(
            provider="openai",
            model="gpt-4o",
            is_key_valid=True,
        )
        provider, model = _effective_provider_model(config, "free")
        assert provider == "openai"
        assert model == "gpt-4o"

    def test_byok_config_without_model_falls_back_to_provider_default(self) -> None:
        """When a BYOK config sets provider but no explicit model, the
        helper should look up the provider's default model rather than
        returning an empty string."""
        config = SimpleNamespace(
            provider="anthropic",
            model=None,
            is_key_valid=True,
        )
        provider, model = _effective_provider_model(config, "free")
        assert provider == "anthropic"
        assert model  # non-empty default

    def test_invalid_byok_key_ignores_config_and_returns_tier_default(self) -> None:
        """An un-validated BYOK key must NOT be returned as the effective
        provider — otherwise the orchestrator would try to call a key that
        we know doesn't work."""
        config = SimpleNamespace(
            provider="openai",
            model="gpt-4o",
            is_key_valid=False,
        )
        provider, model = _effective_provider_model(config, "free")
        assert provider == "google"
        assert model == "gemini-2.0-flash"

    def test_platform_default_config_returns_tier_default(self) -> None:
        config = SimpleNamespace(
            provider="platform_default",
            model=None,
            is_key_valid=False,
        )
        provider, model = _effective_provider_model(config, "free")
        assert provider == "google"


# --- _get_active_ai_config hardening ---------------------------------------


@pytest.mark.asyncio
async def test_get_active_ai_config_returns_none_on_sqlalchemy_error() -> None:
    """If the underlying SELECT fails (e.g., ``status`` column is missing
    because migration 028 hasn't run on this environment), the helper must
    swallow the error and return None so the handler can fall back to the
    platform-default response shape instead of 500ing."""
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=OperationalError(
            "SELECT ...", {}, Exception("column status does not exist")
        )
    )
    db.rollback = AsyncMock()

    result = await _get_active_ai_config(db, "user-123")

    assert result is None
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_active_ai_config_returns_row_on_happy_path() -> None:
    """Sanity check that the success path still works after wrapping the
    query in try/except."""
    expected = SimpleNamespace(
        id="config-1",
        user_id="user-123",
        provider="anthropic",
        status="active",
    )
    scalars = MagicMock()
    scalars.first = MagicMock(return_value=expected)
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars)

    db = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)

    result = await _get_active_ai_config(db, "user-123")

    assert result is expected


@pytest.mark.asyncio
async def test_get_active_ai_config_returns_none_when_no_row() -> None:
    """Empty result set (no active config for this user) should yield None
    without raising."""
    scalars = MagicMock()
    scalars.first = MagicMock(return_value=None)
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars)

    db = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)

    result = await _get_active_ai_config(db, "user-without-config")

    assert result is None
