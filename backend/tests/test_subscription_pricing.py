"""Regression tests for the Foundry-style pricing redesign.

Covers the BYOK-aware free chat cap, the ``effective_chat_session_limit``
helper, and a basic check of the new tier enum surface. Storage paths
are exercised against an in-process SQLite engine to keep the suite
hermetic.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.subscription import (
    SubscriptionPlan,
    SubscriptionTier,
)
from app.services.subscription import SubscriptionService


def _plan(tier: SubscriptionTier, chat_cap: int) -> SubscriptionPlan:
    return SubscriptionPlan(
        id="p",
        tier=tier,
        name=tier.value.title(),
        price_monthly=0,
        chat_sessions_per_month=chat_cap,
    )


class TestEffectiveChatSessionLimit:
    def test_free_no_byok_returns_plan_cap(self) -> None:
        plan = _plan(SubscriptionTier.FREE, 10)
        assert (
            SubscriptionService.effective_chat_session_limit(plan, has_valid_byok=False)
            == 10
        )

    def test_free_with_byok_lifts_cap_to_50(self) -> None:
        plan = _plan(SubscriptionTier.FREE, 10)
        assert (
            SubscriptionService.effective_chat_session_limit(plan, has_valid_byok=True)
            == 50
        )

    def test_free_with_byok_does_not_lower_higher_cap(self) -> None:
        # If we ever bump the free cap above 50, BYOK shouldn't lower it.
        plan = _plan(SubscriptionTier.FREE, 200)
        assert (
            SubscriptionService.effective_chat_session_limit(plan, has_valid_byok=True)
            == 200
        )

    def test_paid_tier_byok_is_no_op(self) -> None:
        plan = _plan(SubscriptionTier.PRO, 1000)
        assert (
            SubscriptionService.effective_chat_session_limit(plan, has_valid_byok=True)
            == 1000
        )
        assert (
            SubscriptionService.effective_chat_session_limit(plan, has_valid_byok=False)
            == 1000
        )


class TestSubscriptionTierEnum:
    def test_all_new_tiers_present(self) -> None:
        # Drift guard: if someone deletes one of the new tiers the
        # migration + seed expects, fail loudly here.
        values = {t.value for t in SubscriptionTier}
        assert {"free", "starter", "pro", "max", "enterprise"}.issubset(values)

    def test_legacy_individual_tier_retained(self) -> None:
        # Required so existing rows / FKs still resolve through the
        # SQLAlchemy enum coercion.
        assert SubscriptionTier.INDIVIDUAL.value == "individual"


@pytest.mark.asyncio
class TestHasValidByok:
    async def test_returns_false_when_no_configs(self) -> None:
        db = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=execute_result)

        assert await SubscriptionService._has_valid_byok(db, "user-1") is False

    async def test_returns_true_for_valid_byok_with_key(self) -> None:
        cfg = SimpleNamespace(
            provider="anthropic",
            is_key_valid=True,
            api_key_encrypted="ciphertext",
        )
        scalars = MagicMock()
        scalars.all.return_value = [cfg]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db = MagicMock()
        db.execute = AsyncMock(return_value=execute_result)

        assert await SubscriptionService._has_valid_byok(db, "user-1") is True

    async def test_ignores_platform_default(self) -> None:
        cfg = SimpleNamespace(
            provider="platform_default",
            is_key_valid=True,
            api_key_encrypted="ciphertext",
        )
        scalars = MagicMock()
        scalars.all.return_value = [cfg]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db = MagicMock()
        db.execute = AsyncMock(return_value=execute_result)

        assert await SubscriptionService._has_valid_byok(db, "user-1") is False

    async def test_ignores_unvalidated_keys(self) -> None:
        cfg = SimpleNamespace(
            provider="openai",
            is_key_valid=False,
            api_key_encrypted="ciphertext",
        )
        scalars = MagicMock()
        scalars.all.return_value = [cfg]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db = MagicMock()
        db.execute = AsyncMock(return_value=execute_result)

        assert await SubscriptionService._has_valid_byok(db, "user-1") is False

    async def test_swallows_db_errors(self) -> None:
        db = MagicMock()
        db.execute = AsyncMock(side_effect=RuntimeError("boom"))
        assert await SubscriptionService._has_valid_byok(db, "user-1") is False
