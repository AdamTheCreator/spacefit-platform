"""Seed reproducible test users for the chat orchestration deep-dive.

Creates:
  - pro@spacegoose.test  / protest1234  → Pro tier subscription
  - byok@spacegoose.test / byoktest1234 → Free tier + validated BYOK row

The BYOK row points at Anthropic with a fake (but valid-shaped) key so the
routing branch is exercised end-to-end; it is NOT expected to actually
call Anthropic. Seed is idempotent — re-running upserts the rows.

Usage:
    backend/.venv/bin/python -m scripts.seed_test_users
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import encrypt_credential, hash_password
from app.db.models.credential import UserAIConfig
from app.db.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionTier,
)
from app.db.models.user import User

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def _upsert_user(
    db, *, email: str, password: str, first_name: str, last_name: str
) -> User:
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user:
        # Reset password on each run so the seed is reproducible.
        user.password_hash = hash_password(password)
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.email_verified = True
        await db.flush()
        logger.info("  user reused: %s (%s)", email, user.id)
        return user
    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    logger.info("  user created: %s (%s)", email, user.id)
    return user


async def _set_subscription_tier(db, user: User, tier: SubscriptionTier) -> None:
    plan = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == tier)
        )
    ).scalar_one()
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalar_one_or_none()
    if sub:
        sub.plan_id = plan.id
        sub.status = "active"
    else:
        sub = Subscription(user_id=user.id, plan_id=plan.id, status="active")
        db.add(sub)
    await db.flush()
    logger.info("  subscription set: %s -> %s", user.email, tier.value)


async def _upsert_byok_row(db, user: User) -> None:
    # A real fake key shape; never actually called.
    fake_key = "sk-ant-fake-test-key-for-routing-only-NOT-LIVE"
    ciphertext = encrypt_credential(fake_key)

    existing = (
        await db.execute(
            select(UserAIConfig).where(UserAIConfig.user_id == user.id)
        )
    ).scalars().all()
    for row in existing:
        # Crypto-shred existing rows so the "at most one active per
        # (user, provider)" partial unique index doesn't reject our insert.
        row.status = "revoked"
        row.api_key_encrypted = None

    cfg = UserAIConfig(
        user_id=user.id,
        provider="anthropic",
        model="claude-3-haiku-20240307",
        api_key_encrypted=ciphertext,
        is_key_valid=True,
        key_last_four="-LIVE",
        label="seed-test BYOK (fake key)",
        status="active",
        scope="{}",
    )
    db.add(cfg)
    await db.flush()
    logger.info("  byok config seeded: provider=anthropic is_key_valid=True")


async def main() -> None:
    async with async_session_factory() as db:
        logger.info("[pro@spacegoose.io]")
        pro_user = await _upsert_user(
            db,
            email="pro@spacegoose.io",
            password="protest1234",
            first_name="Pro",
            last_name="Tester",
        )
        await _set_subscription_tier(db, pro_user, SubscriptionTier.PRO)

        logger.info("\n[byok@spacegoose.io]")
        byok_user = await _upsert_user(
            db,
            email="byok@spacegoose.io",
            password="byoktest1234",
            first_name="Byok",
            last_name="Tester",
        )
        await _set_subscription_tier(db, byok_user, SubscriptionTier.FREE)
        await _upsert_byok_row(db, byok_user)

        await db.commit()
        logger.info("\nDone. Logins:")
        logger.info("  pro@spacegoose.io  / protest1234   (Pro tier)")
        logger.info("  byok@spacegoose.io / byoktest1234  (Free tier + validated BYOK)")


if __name__ == "__main__":
    asyncio.run(main())
