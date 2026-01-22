import stripe
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    SubscriptionTier,
)
from app.db.models.user import User

# Configure Stripe
stripe.api_key = settings.stripe_secret_key


class StripeService:
    """Service for handling Stripe payments and subscriptions."""

    @staticmethod
    async def create_customer(user: User) -> str:
        """Create a Stripe customer for a user."""
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={"user_id": user.id},
        )
        return customer.id

    @staticmethod
    async def create_checkout_session(
        db: AsyncSession,
        user: User,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout session for subscription."""
        # Get the plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == tier)
        )
        plan = result.scalar_one_or_none()
        if not plan or not plan.stripe_price_id:
            raise ValueError(f"No Stripe price configured for tier: {tier}")

        # Get or create Stripe customer
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = result.scalar_one_or_none()

        customer_id = subscription.stripe_customer_id if subscription else None
        if not customer_id:
            customer_id = await StripeService.create_customer(user)

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user.id,
                "plan_id": plan.id,
                "tier": tier.value,
            },
            subscription_data={
                "metadata": {
                    "user_id": user.id,
                    "plan_id": plan.id,
                },
            },
        )

        return session.url

    @staticmethod
    async def create_billing_portal_session(
        subscription: Subscription,
        return_url: str,
    ) -> str:
        """Create a Stripe billing portal session for subscription management."""
        if not subscription.stripe_customer_id:
            raise ValueError("No Stripe customer ID found")

        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    @staticmethod
    async def handle_checkout_completed(
        db: AsyncSession,
        session: stripe.checkout.Session,
    ) -> None:
        """Handle successful checkout completion."""
        user_id = session.metadata.get("user_id")
        plan_id = session.metadata.get("plan_id")
        customer_id = session.customer
        subscription_id = session.subscription

        if not user_id or not plan_id:
            return

        # Get or create subscription record
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.plan_id = plan_id
            subscription.stripe_customer_id = customer_id
            subscription.stripe_subscription_id = subscription_id
            subscription.status = SubscriptionStatus.ACTIVE
        else:
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                status=SubscriptionStatus.ACTIVE,
            )
            db.add(subscription)

        await db.commit()

    @staticmethod
    async def handle_subscription_updated(
        db: AsyncSession,
        stripe_subscription: stripe.Subscription,
    ) -> None:
        """Handle subscription update events."""
        subscription_id = stripe_subscription.id

        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        # Update status
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "canceled": SubscriptionStatus.CANCELED,
            "past_due": SubscriptionStatus.PAST_DUE,
            "trialing": SubscriptionStatus.TRIALING,
            "paused": SubscriptionStatus.PAUSED,
        }
        subscription.status = status_map.get(
            stripe_subscription.status, SubscriptionStatus.ACTIVE
        )

        # Update period dates
        subscription.current_period_start = datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=timezone.utc
        )
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=timezone.utc
        )
        subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end

        await db.commit()

    @staticmethod
    async def handle_subscription_deleted(
        db: AsyncSession,
        stripe_subscription: stripe.Subscription,
    ) -> None:
        """Handle subscription cancellation."""
        subscription_id = stripe_subscription.id

        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        # Get free plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.FREE)
        )
        free_plan = result.scalar_one_or_none()

        if free_plan:
            subscription.plan_id = free_plan.id
            subscription.status = SubscriptionStatus.CANCELED
            subscription.stripe_subscription_id = None

        await db.commit()

    @staticmethod
    async def cancel_subscription(subscription: Subscription) -> None:
        """Cancel a subscription at period end."""
        if not subscription.stripe_subscription_id:
            raise ValueError("No active Stripe subscription")

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
        """Construct and verify a webhook event."""
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
