from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select, case

from app.api.deps import AdminUser, DBSession
from app.db.models.user import User
from app.db.models.chat import ChatSession, ChatMessage
from app.db.models.deal import Deal
from app.db.models.document import ParsedDocument
from app.db.models.project import Project
from app.db.models.subscription import Subscription, TokenUsage
from app.models.admin import (
    AdminAbuse,
    AdminOverview,
    AdminUsage,
    AdminUserDetail,
    AdminUserList,
    AdminUserSummary,
    AbuseFlag,
    RecentSession,
    SignupBucket,
    TokenUsageSummary,
    TopConsumer,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
async def get_overview(admin: AdminUser, db: DBSession):
    now = datetime.utcnow()
    ago_7d = now - timedelta(days=7)
    ago_30d = now - timedelta(days=30)
    ago_90d = now - timedelta(days=90)

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    active_users_30d = (
        await db.execute(
            select(func.count(func.distinct(ChatSession.user_id))).where(
                ChatSession.created_at >= ago_30d
            )
        )
    ).scalar() or 0

    new_users_7d = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= ago_7d)
        )
    ).scalar() or 0

    new_users_30d = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= ago_30d)
        )
    ).scalar() or 0

    total_sessions = (await db.execute(select(func.count(ChatSession.id)))).scalar() or 0
    total_documents = (await db.execute(select(func.count(ParsedDocument.id)))).scalar() or 0
    total_deals = (await db.execute(select(func.count(Deal.id)))).scalar() or 0
    total_projects = (await db.execute(select(func.count(Project.id)))).scalar() or 0

    # Signup trend — daily buckets for last 90 days
    signup_rows = (
        await db.execute(
            select(
                func.date(User.created_at).label("day"),
                func.count(User.id).label("cnt"),
            )
            .where(User.created_at >= ago_90d)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
    ).all()
    signups_over_time = [
        SignupBucket(date=str(row.day), count=row.cnt) for row in signup_rows
    ]

    return AdminOverview(
        total_users=total_users,
        active_users_30d=active_users_30d,
        new_users_7d=new_users_7d,
        new_users_30d=new_users_30d,
        total_sessions=total_sessions,
        total_documents=total_documents,
        total_deals=total_deals,
        total_projects=total_projects,
        signups_over_time=signups_over_time,
    )


@router.get("/users", response_model=AdminUserList)
async def list_users(
    admin: AdminUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
):
    base = select(User)
    if search:
        pattern = f"%{search}%"
        base = base.where(User.email.ilike(pattern))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    users: list[AdminUserSummary] = []
    for u in rows:
        session_count = (
            await db.execute(
                select(func.count(ChatSession.id)).where(ChatSession.user_id == u.id)
            )
        ).scalar() or 0
        document_count = (
            await db.execute(
                select(func.count(ParsedDocument.id)).where(ParsedDocument.user_id == u.id)
            )
        ).scalar() or 0
        deal_count = (
            await db.execute(
                select(func.count(Deal.id)).where(Deal.user_id == u.id)
            )
        ).scalar() or 0
        project_count = (
            await db.execute(
                select(func.count(Project.id)).where(Project.user_id == u.id)
            )
        ).scalar() or 0

        last_session = (
            await db.execute(
                select(ChatSession.created_at)
                .where(ChatSession.user_id == u.id)
                .order_by(ChatSession.created_at.desc())
                .limit(1)
            )
        ).scalar()

        users.append(
            AdminUserSummary(
                id=u.id,
                email=u.email,
                first_name=u.first_name,
                last_name=u.last_name,
                tier=u.tier,
                is_active=u.is_active,
                session_count=session_count,
                document_count=document_count,
                deal_count=deal_count,
                project_count=project_count,
                created_at=u.created_at,
                last_active=last_session,
            )
        )

    return AdminUserList(users=users, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(user_id: str, admin: AdminUser, db: DBSession):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    session_count = (
        await db.execute(
            select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
        )
    ).scalar() or 0
    document_count = (
        await db.execute(
            select(func.count(ParsedDocument.id)).where(ParsedDocument.user_id == user_id)
        )
    ).scalar() or 0
    deal_count = (
        await db.execute(
            select(func.count(Deal.id)).where(Deal.user_id == user_id)
        )
    ).scalar() or 0
    project_count = (
        await db.execute(
            select(func.count(Project.id)).where(Project.user_id == user_id)
        )
    ).scalar() or 0

    # Token usage history
    token_rows = (
        await db.execute(
            select(TokenUsage)
            .where(TokenUsage.user_id == user_id)
            .order_by(TokenUsage.period_start.desc())
            .limit(6)
        )
    ).scalars().all()
    token_usage = [
        TokenUsageSummary(
            period_start=t.period_start,
            input_tokens=t.input_tokens,
            output_tokens=t.output_tokens,
            llm_calls=t.llm_calls,
        )
        for t in token_rows
    ]

    # Recent sessions with message counts
    session_rows = (
        await db.execute(
            select(
                ChatSession.id,
                ChatSession.title,
                ChatSession.created_at,
                func.count(ChatMessage.id).label("msg_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.created_at.desc())
            .limit(10)
        )
    ).all()
    recent_sessions = [
        RecentSession(
            id=r.id,
            title=r.title,
            message_count=r.msg_count,
            created_at=r.created_at,
        )
        for r in session_rows
    ]

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        tier=user.tier,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        session_count=session_count,
        document_count=document_count,
        deal_count=deal_count,
        project_count=project_count,
        token_usage=token_usage,
        recent_sessions=recent_sessions,
    )


@router.get("/usage", response_model=AdminUsage)
async def get_usage(admin: AdminUser, db: DBSession):
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_label = period_start.strftime("%B %Y")

    totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("inp"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("out"),
                func.coalesce(func.sum(TokenUsage.llm_calls), 0).label("calls"),
            ).where(TokenUsage.period_start >= period_start)
        )
    ).one()

    top_rows = (
        await db.execute(
            select(
                TokenUsage.user_id,
                User.email,
                func.sum(TokenUsage.input_tokens).label("inp"),
                func.sum(TokenUsage.output_tokens).label("out"),
                func.sum(TokenUsage.llm_calls).label("calls"),
            )
            .join(User, User.id == TokenUsage.user_id)
            .where(TokenUsage.period_start >= period_start)
            .group_by(TokenUsage.user_id, User.email)
            .order_by(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens).desc())
            .limit(10)
        )
    ).all()

    top_consumers = [
        TopConsumer(
            user_id=r.user_id,
            email=r.email,
            input_tokens=r.inp,
            output_tokens=r.out,
            llm_calls=r.calls,
            total_tokens=r.inp + r.out,
        )
        for r in top_rows
    ]

    return AdminUsage(
        period_label=period_label,
        total_input_tokens=totals.inp,
        total_output_tokens=totals.out,
        total_llm_calls=totals.calls,
        top_consumers=top_consumers,
    )


@router.get("/abuse", response_model=AdminAbuse)
async def get_abuse(admin: AdminUser, db: DBSession):
    now = datetime.utcnow()
    ago_7d = now - timedelta(days=7)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    flags: list[AbuseFlag] = []

    # 1) Token usage > 2x average this month
    avg_result = (
        await db.execute(
            select(func.avg(TokenUsage.input_tokens + TokenUsage.output_tokens)).where(
                TokenUsage.period_start >= period_start
            )
        )
    ).scalar()
    avg_tokens = avg_result or 0

    if avg_tokens > 0:
        heavy_users = (
            await db.execute(
                select(
                    TokenUsage.user_id,
                    User.email,
                    func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens).label("total"),
                )
                .join(User, User.id == TokenUsage.user_id)
                .where(TokenUsage.period_start >= period_start)
                .group_by(TokenUsage.user_id, User.email)
                .having(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens) > avg_tokens * 2)
            )
        ).all()

        for r in heavy_users:
            flags.append(
                AbuseFlag(
                    user_id=r.user_id,
                    email=r.email,
                    reason="High token usage",
                    severity="medium",
                    detail=f"{r.total:,} tokens this month (avg {int(avg_tokens):,})",
                )
            )

    # 2) >50 sessions in last 7 days
    session_heavy = (
        await db.execute(
            select(
                ChatSession.user_id,
                User.email,
                func.count(ChatSession.id).label("cnt"),
            )
            .join(User, User.id == ChatSession.user_id)
            .where(ChatSession.created_at >= ago_7d)
            .group_by(ChatSession.user_id, User.email)
            .having(func.count(ChatSession.id) > 50)
        )
    ).all()

    for r in session_heavy:
        flags.append(
            AbuseFlag(
                user_id=r.user_id,
                email=r.email,
                reason="Excessive sessions",
                severity="low",
                detail=f"{r.cnt} sessions in the last 7 days",
            )
        )

    # 3) Free-tier users with high token usage (>50k tokens this month)
    free_heavy = (
        await db.execute(
            select(
                TokenUsage.user_id,
                User.email,
                func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens).label("total"),
            )
            .join(User, User.id == TokenUsage.user_id)
            .outerjoin(Subscription, Subscription.user_id == User.id)
            .where(
                TokenUsage.period_start >= period_start,
                Subscription.id.is_(None),
            )
            .group_by(TokenUsage.user_id, User.email)
            .having(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens) > 50_000)
        )
    ).all()

    for r in free_heavy:
        flags.append(
            AbuseFlag(
                user_id=r.user_id,
                email=r.email,
                reason="Free-tier over-budget",
                severity="high",
                detail=f"{r.total:,} tokens on free tier this month",
            )
        )

    return AdminAbuse(flags=flags)
