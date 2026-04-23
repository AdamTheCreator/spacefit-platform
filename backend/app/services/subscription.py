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

        # -1 means unlimited
        if limit == -1:
            return True, ""

        # Check if feature is disabled (0 limit)
        if limit == 0:
            return False, f"This feature requires an Individual or Enterprise subscription."

        # Check current usage
        current = await SubscriptionService.get_usage(db, subscription, usage_type)

        if current >= limit:
            return False, f"You've reached your monthly limit of {limit} {usage_type.value.replace('_', ' ')}s. Upgrade to increase your limit."

        return True, ""

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
        """Create default subscription plans if they don't exist."""
        # Check if plans exist
        result = await db.execute(select(SubscriptionPlan))
        if result.scalars().first():
            return

        plans = [
            SubscriptionPlan(
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
            ),
            SubscriptionPlan(
                tier=SubscriptionTier.INDIVIDUAL,
                name="Individual",
                description="For growing CRE professionals",
                price_monthly=4900,  # $49.00
                chat_sessions_per_month=-1,  # Unlimited
                void_analyses_per_month=50,
                demographics_reports_per_month=-1,
                emails_per_month=500,
                documents_per_month=50,
                team_members=3,
                has_placer_access=True,
                has_siteusa_access=True,
                has_costar_access=False,
                has_email_outreach=True,
                has_api_access=False,
            ),
            SubscriptionPlan(
                tier=SubscriptionTier.ENTERPRISE,
                name="Enterprise",
                description="For teams that need everything",
                price_monthly=19900,  # $199.00
                chat_sessions_per_month=-1,
                void_analyses_per_month=-1,
                demographics_reports_per_month=-1,
                emails_per_month=5000,
                documents_per_month=-1,
                team_members=-1,
                has_placer_access=True,
                has_siteusa_access=True,
                has_costar_access=True,
                has_email_outreach=True,
                has_api_access=True,
            ),
        ]

        for plan in plans:
            db.add(plan)

        await db.commit()
