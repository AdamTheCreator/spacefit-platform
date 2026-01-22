import stripe
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.db.models.subscription import SubscriptionTier
from app.services.stripe_service import StripeService
from app.services.subscription import SubscriptionService

router = APIRouter(prefix="/billing", tags=["billing"])


class CreateCheckoutRequest(BaseModel):
    tier: str  # "pro" or "enterprise"
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    db: DBSession,
    user: CurrentUser,
    request: CreateCheckoutRequest,
) -> CheckoutResponse:
    """Create a Stripe Checkout session for subscription upgrade."""
    try:
        tier = SubscriptionTier(request.tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.tier}. Must be 'pro' or 'enterprise'.",
        )

    if tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot checkout for free tier.",
        )

    try:
        checkout_url = await StripeService.create_checkout_session(
            db=db,
            user=user,
            tier=tier,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CheckoutResponse(checkout_url=checkout_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/portal", response_model=PortalResponse)
async def create_billing_portal_session(
    db: DBSession,
    user: CurrentUser,
    return_url: str,
) -> PortalResponse:
    """Create a Stripe billing portal session for subscription management."""
    subscription = await SubscriptionService.get_or_create_subscription(db, user)

    if not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active paid subscription found.",
        )

    try:
        portal_url = await StripeService.create_billing_portal_session(
            subscription=subscription,
            return_url=return_url,
        )
        return PortalResponse(portal_url=portal_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/cancel")
async def cancel_subscription(
    db: DBSession,
    user: CurrentUser,
) -> dict[str, str]:
    """Cancel the current subscription at the end of the billing period."""
    subscription = await SubscriptionService.get_or_create_subscription(db, user)

    if not subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active paid subscription to cancel.",
        )

    try:
        await StripeService.cancel_subscription(subscription)
        return {"message": "Subscription will be canceled at the end of the billing period."}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: DBSession,
) -> dict[str, str]:
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    try:
        event = StripeService.construct_webhook_event(payload, sig_header)
    except stripe.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    # Handle the event
    if event.type == "checkout.session.completed":
        session = event.data.object
        await StripeService.handle_checkout_completed(db, session)

    elif event.type == "customer.subscription.updated":
        subscription = event.data.object
        await StripeService.handle_subscription_updated(db, subscription)

    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object
        await StripeService.handle_subscription_deleted(db, subscription)

    return {"status": "success"}


@router.get("/config")
async def get_stripe_config() -> dict[str, str]:
    """Get Stripe publishable key for frontend."""
    return {"publishable_key": settings.stripe_publishable_key}
