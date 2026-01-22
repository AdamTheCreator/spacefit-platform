from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSession
from app.db.models.subscription import SubscriptionTier, SubscriptionStatus
from app.services.subscription import SubscriptionService

router = APIRouter(prefix="/subscription", tags=["subscription"])


class PlanResponse(BaseModel):
    id: str
    tier: str
    name: str
    description: str | None
    price_monthly: int
    chat_sessions_per_month: int
    void_analyses_per_month: int
    demographics_reports_per_month: int
    emails_per_month: int
    documents_per_month: int
    team_members: int
    has_placer_access: bool
    has_siteusa_access: bool
    has_costar_access: bool
    has_email_outreach: bool
    has_api_access: bool


class SubscriptionResponse(BaseModel):
    id: str
    tier: str
    status: str
    plan: PlanResponse
    current_period_start: str | None
    current_period_end: str | None
    cancel_at_period_end: bool


class UsageResponse(BaseModel):
    chat_session: int
    void_analysis: int
    demographics_report: int
    email_sent: int
    document_parsed: int


class SubscriptionWithUsageResponse(BaseModel):
    subscription: SubscriptionResponse
    usage: UsageResponse
    limits: UsageResponse


@router.get("/plans", response_model=list[PlanResponse])
async def get_plans(db: DBSession) -> list[PlanResponse]:
    """Get all available subscription plans."""
    # Ensure default plans exist
    await SubscriptionService.ensure_default_plans(db)

    plans = await SubscriptionService.get_plans(db)
    return [
        PlanResponse(
            id=p.id,
            tier=p.tier.value,
            name=p.name,
            description=p.description,
            price_monthly=p.price_monthly,
            chat_sessions_per_month=p.chat_sessions_per_month,
            void_analyses_per_month=p.void_analyses_per_month,
            demographics_reports_per_month=p.demographics_reports_per_month,
            emails_per_month=p.emails_per_month,
            documents_per_month=p.documents_per_month,
            team_members=p.team_members,
            has_placer_access=p.has_placer_access,
            has_siteusa_access=p.has_siteusa_access,
            has_costar_access=p.has_costar_access,
            has_email_outreach=p.has_email_outreach,
            has_api_access=p.has_api_access,
        )
        for p in plans
    ]


@router.get("/current", response_model=SubscriptionWithUsageResponse)
async def get_current_subscription(
    db: DBSession,
    user: CurrentUser,
) -> SubscriptionWithUsageResponse:
    """Get current user's subscription and usage."""
    subscription = await SubscriptionService.get_or_create_subscription(db, user)
    usage = await SubscriptionService.get_all_usage(db, subscription)
    plan = subscription.plan

    return SubscriptionWithUsageResponse(
        subscription=SubscriptionResponse(
            id=subscription.id,
            tier=plan.tier.value,
            status=subscription.status.value,
            plan=PlanResponse(
                id=plan.id,
                tier=plan.tier.value,
                name=plan.name,
                description=plan.description,
                price_monthly=plan.price_monthly,
                chat_sessions_per_month=plan.chat_sessions_per_month,
                void_analyses_per_month=plan.void_analyses_per_month,
                demographics_reports_per_month=plan.demographics_reports_per_month,
                emails_per_month=plan.emails_per_month,
                documents_per_month=plan.documents_per_month,
                team_members=plan.team_members,
                has_placer_access=plan.has_placer_access,
                has_siteusa_access=plan.has_siteusa_access,
                has_costar_access=plan.has_costar_access,
                has_email_outreach=plan.has_email_outreach,
                has_api_access=plan.has_api_access,
            ),
            current_period_start=subscription.current_period_start.isoformat()
            if subscription.current_period_start
            else None,
            current_period_end=subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None,
            cancel_at_period_end=subscription.cancel_at_period_end,
        ),
        usage=UsageResponse(
            chat_session=usage.get("chat_session", 0),
            void_analysis=usage.get("void_analysis", 0),
            demographics_report=usage.get("demographics_report", 0),
            email_sent=usage.get("email_sent", 0),
            document_parsed=usage.get("document_parsed", 0),
        ),
        limits=UsageResponse(
            chat_session=plan.chat_sessions_per_month,
            void_analysis=plan.void_analyses_per_month,
            demographics_report=plan.demographics_reports_per_month,
            email_sent=plan.emails_per_month,
            document_parsed=plan.documents_per_month,
        ),
    )
