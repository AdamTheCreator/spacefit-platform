from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    SubscriptionTier,
    UsageRecord,
    UsageType,
)
from app.db.models.user import User


class SubscriptionService:
    """Service for managing subscriptions and usage tracking."""

    @staticmethod
    async def get_or_create_subscription(
        db: AsyncSession, user: User
    ) -> Subscription:
        """Get user's subscription or create a free one."""
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.user_id == user.id)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            return subscription

        # Get free plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.FREE)
        )
        free_plan = result.scalar_one_or_none()

        if not free_plan:
            # Create free plan if it doesn't exist
            free_plan = SubscriptionPlan(
                tier=SubscriptionTier.FREE,
                name="Free",
                description="Get started with Space Goose",
                price_monthly=0,
                chat_sessions_per_month=10,
                void_analyses_per_month=3,
                demographics_reports_per_month=5,
                emails_per_month=0,
                documents_per_month=5,
                team_members=1,
                has_placer_access=False,
                has_siteusa_access=False,
                has_costar_access=False,
                has_email_outreach=False,
                has_api_access=False,
            )
            db.add(free_plan)
            await db.flush()

        # Create subscription for user
        subscription = Subscription(
            user_id=user.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        # Load the plan relationship
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.id == subscription.id)
        )
        return result.scalar_one()

    @staticmethod
    def _get_current_period() -> tuple[datetime, datetime]:
        """Get the current billing period (monthly)."""
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = (period_start + relativedelta(months=1)) - relativedelta(seconds=1)
        return period_start, period_end

    @staticmethod
    async def get_usage(
        db: AsyncSession,
        subscription: Subscription,
        usage_type: UsageType,
    ) -> int:
        """Get current usage count for a specific type."""
        period_start, period_end = SubscriptionService._get_current_period()

        result = await db.execute(
            select(UsageRecord).where(
                and_(
                    UsageRecord.subscription_id == subscription.id,
                    UsageRecord.usage_type == usage_type,
                    UsageRecord.period_start == period_start,
                )
            )
        )
        record = result.scalar_one_or_none()

        return record.count if record else 0

    @staticmethod
    async def get_all_usage(
        db: AsyncSession,
        subscription: Subscription,
    ) -> dict[str, int]:
        """Get all current usage counts."""
        period_start, _ = SubscriptionService._get_current_period()

        result = await db.execute(
            select(UsageRecord).where(
                and_(
                    UsageRecord.subscription_id == subscription.id,
                    UsageRecord.period_start == period_start,
                )
            )
        )
        records = result.scalars().all()

        usage = {t.value: 0 for t in UsageType}
        for record in records:
            usage[record.usage_type.value] = record.count

        return usage

    @staticmethod
    async def increment_usage(
        db: AsyncSession,
        subscription: Subscription,
        usage_type: UsageType,
        amount: int = 1,
    ) -> UsageRecord:
        """Increment usage for a specific type."""
        period_start, period_end = SubscriptionService._get_current_period()

        result = await db.execute(
            select(UsageRecord).where(
                and_(
                    UsageRecord.subscription_id == subscription.id,
                    UsageRecord.usage_type == usage_type,
                    UsageRecord.period_start == period_start,
                )
            )
        )
        record = result.scalar_one_or_none()

        if record:
            record.count += amount
        else:
            record = UsageRecord(
                subscription_id=subscription.id,
                usage_type=usage_type,
                count=amount,
                period_start=period_start,
                period_end=period_end,
            )
            db.add(record)

        await db.commit()
        return record

    @staticmethod
    def get_limit_for_usage_type(
        plan: SubscriptionPlan, usage_type: UsageType
    ) -> int:
        """Get the limit for a specific usage type from the plan."""
        limits = {
            UsageType.CHAT_SESSION: plan.chat_sessions_per_month,
            UsageType.VOID_ANALYSIS: plan.void_analyses_per_month,
            UsageType.DEMOGRAPHICS_REPORT: plan.demographics_reports_per_month,
            UsageType.EMAIL_SENT: plan.emails_per_month,
            UsageType.DOCUMENT_PARSED: plan.documents_per_month,
        }
        return limits.get(usage_type, 0)

    @staticmethod
    async def check_can_use(
        db: AsyncSession,
        subscription: Subscription,
        usage_type: UsageType,
    ) -> tuple[bool, str]:
        """Check if user can use a feature based on their subscription."""
        # Load plan if not loaded
        if not subscription.plan:
            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.plan))
                .where(Subscription.id == subscription.id)
            )
            subscription = result.scalar_one()

        plan = subscription.plan
        limit = SubscriptionService.get_limit_for_usage_type(plan, usage_type)

        # Lift the free-tier chat cap when the user has a valid BYOK key
        # (their LLM cost is on them, so the platform isn't on the hook).
        if (
            usage_type == UsageType.CHAT_SESSION
            and plan.tier == SubscriptionTier.FREE
        ):
            has_byok = await SubscriptionService._has_valid_byok(
                db, subscription.user_id
            )
            limit = SubscriptionService.effective_chat_session_limit(plan, has_byok)

        # -1 means unlimited
        if limit == -1:
            return True, ""

        # Check if feature is disabled (0 limit)
        if limit == 0:
            return False, "This feature requires a paid Space Goose plan."

        # Check current usage
        current = await SubscriptionService.get_usage(db, subscription, usage_type)

        if current >= limit:
            return False, f"You've reached your monthly limit of {limit} {usage_type.value.replace('_', ' ')}s. Upgrade to increase your limit."

        return True, ""

    @staticmethod
    async def _has_valid_byok(db: AsyncSession, user_id: str) -> bool:
        """Best-effort lookup of whether the user has a validated BYOK
        key. Returns False on any error so callers fall back to the
        platform-default chat cap rather than 500ing."""
        try:
            from app.db.models.credential import UserAIConfig

            result = await db.execute(
                select(UserAIConfig).where(UserAIConfig.user_id == user_id)
            )
            for cfg in result.scalars().all():
                if (
                    cfg.provider != "platform_default"
                    and cfg.is_key_valid
                    and cfg.api_key_encrypted
                ):
                    return True
        except Exception:
            return False
        return False

    @staticmethod
    async def check_feature_access(
        db: AsyncSession,
        subscription: Subscription,
        feature: str,
    ) -> tuple[bool, str]:
        """Check if user has access to a specific feature."""
        if not subscription.plan:
            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.plan))
                .where(Subscription.id == subscription.id)
            )
            subscription = result.scalar_one()

        plan = subscription.plan
        features = {
            "placer": plan.has_placer_access,
            "siteusa": plan.has_siteusa_access,
            "costar": plan.has_costar_access,
            "email_outreach": plan.has_email_outreach,
            "api": plan.has_api_access,
        }

        has_access = features.get(feature, False)
        if not has_access:
            return False, f"Access to {feature} requires a higher subscription tier."

        return True, ""

    @staticmethod
    async def get_plans(db: AsyncSession) -> list[SubscriptionPlan]:
        """Get all active subscription plans."""
        result = await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active == True)
            .order_by(SubscriptionPlan.price_monthly)
        )
        return list(result.scalars().all())

    @staticmethod
    async def ensure_default_plans(db: AsyncSession) -> None:
        """Create / refresh the Foundry-style tier plans.

        Idempotent: each tier is upserted on its unique ``tier`` value so
        running this on a fresh DB seeds everything, and running it on a
        DB that already has the new plans is a no-op. The pricing /
        flag values here are the source of truth; the SQL migration only
        backfills legacy ``individual`` rows.
        """
        from app.core.config import settings

        desired_plans: list[dict] = [
            {
                "tier": SubscriptionTier.FREE,
                "name": "Free",
                "description": "Get started with Space Goose",
                "price_monthly": 0,
                "price_yearly": 0,
                "stripe_price_id": None,
                "stripe_price_id_yearly": None,
                "billing_interval_default": "monthly",
                "chat_sessions_per_month": 10,
                "void_analyses_per_month": 3,
                "demographics_reports_per_month": 5,
                "emails_per_month": 0,
                "documents_per_month": 5,
                "team_members": 1,
                "monthly_token_budget": 500_000,
                "has_placer_access": False,
                "has_siteusa_access": False,
                "has_costar_access": False,
                "has_email_outreach": False,
                "has_api_access": False,
                "has_pipeline_reports": False,
                "is_active": True,
            },
            {
                "tier": SubscriptionTier.STARTER,
                "name": "Starter",
                "description": "For solo brokers kicking the tires",
                "price_monthly": 2000,  # $20.00
                "price_yearly": 19_200,  # $192.00 = 20% off $240
                "stripe_price_id": settings.stripe_starter_monthly_price_id or None,
                "stripe_price_id_yearly": settings.stripe_starter_yearly_price_id
                or None,
                "billing_interval_default": "monthly",
                "chat_sessions_per_month": 200,
                "void_analyses_per_month": 20,
                "demographics_reports_per_month": 50,
                "emails_per_month": 200,
                "documents_per_month": 50,
                "team_members": 1,
                "monthly_token_budget": 2_000_000,
                "has_placer_access": False,
                "has_siteusa_access": False,
                "has_costar_access": False,
                "has_email_outreach": True,
                "has_api_access": False,
                "has_pipeline_reports": False,
                "is_active": True,
            },
            {
                "tier": SubscriptionTier.PRO,
                "name": "Pro",
                "description": "For active CRE pros who chat all day",
                "price_monthly": 10_000,  # $100.00
                "price_yearly": 96_000,  # $960.00 = 20% off $1200
                "stripe_price_id": settings.stripe_pro_monthly_price_id or None,
                "stripe_price_id_yearly": settings.stripe_pro_yearly_price_id
                or None,
                "billing_interval_default": "monthly",
                "chat_sessions_per_month": 1000,
                "void_analyses_per_month": -1,
                "demographics_reports_per_month": -1,
                "emails_per_month": 2000,
                "documents_per_month": 200,
                "team_members": 1,
                "monthly_token_budget": 10_000_000,
                "has_placer_access": True,
                "has_siteusa_access": True,
                "has_costar_access": False,
                "has_email_outreach": True,
                "has_api_access": False,
                "has_pipeline_reports": True,
                "is_active": True,
            },
            {
                "tier": SubscriptionTier.MAX,
                "name": "Max",
                "description": "For high-volume teams who live in chat",
                "price_monthly": 20_000,  # $200.00
                "price_yearly": 192_000,  # $1920.00 = 20% off $2400
                "stripe_price_id": settings.stripe_max_monthly_price_id or None,
                "stripe_price_id_yearly": settings.stripe_max_yearly_price_id
                or None,
                "billing_interval_default": "monthly",
                "chat_sessions_per_month": 5000,
                "void_analyses_per_month": -1,
                "demographics_reports_per_month": -1,
                "emails_per_month": 10_000,
                "documents_per_month": -1,
                "team_members": 1,
                "monthly_token_budget": 25_000_000,
                "has_placer_access": True,
                "has_siteusa_access": True,
                "has_costar_access": True,
                "has_email_outreach": True,
                "has_api_access": True,
                "has_pipeline_reports": True,
                "is_active": True,
            },
            {
                "tier": SubscriptionTier.ENTERPRISE,
                "name": "Enterprise",
                "description": "Custom plans for teams that need more",
                "price_monthly": 0,  # quote-based
                "price_yearly": 0,
                "stripe_price_id": settings.stripe_enterprise_price_id or None,
                "stripe_price_id_yearly": None,
                "billing_interval_default": "yearly",
                "chat_sessions_per_month": -1,
                "void_analyses_per_month": -1,
                "demographics_reports_per_month": -1,
                "emails_per_month": -1,
                "documents_per_month": -1,
                "team_members": -1,
                "monthly_token_budget": -1,
                "has_placer_access": True,
                "has_siteusa_access": True,
                "has_costar_access": True,
                "has_email_outreach": True,
                "has_api_access": True,
                "has_pipeline_reports": True,
                "is_active": True,
            },
        ]

        for spec in desired_plans:
            tier = spec["tier"]
            result = await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.tier == tier)
            )
            existing = result.scalar_one_or_none()
            if existing:
                # Refresh the source-of-truth fields. We deliberately do
                # not touch ``id`` or ``created_at``.
                for key, value in spec.items():
                    if key == "tier":
                        continue
                    setattr(existing, key, value)
            else:
                db.add(SubscriptionPlan(**spec))

        # Deactivate the legacy individual plan if it lingered through
        # migration 031 (e.g. a fresh dev DB with no migration history).
        result = await db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.tier == SubscriptionTier.INDIVIDUAL
            )
        )
        legacy = result.scalar_one_or_none()
        if legacy and legacy.is_active:
            legacy.is_active = False

        await db.commit()

    @staticmethod
    def effective_chat_session_limit(
        plan: SubscriptionPlan, has_valid_byok: bool
    ) -> int:
        """Resolve the per-month chat-session cap for a plan, taking
        BYOK into account.

        Free-tier users with a validated BYOK key pay no platform LLM
        cost, so we lift their cap from 10 to 50 to make Space Goose
        meaningfully useful even before they're ready to pay. Paid
        tiers are returned unchanged.
        """
        if plan.tier == SubscriptionTier.FREE and has_valid_byok:
            return max(plan.chat_sessions_per_month, 50)
        return plan.chat_sessions_per_month
