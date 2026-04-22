from collections.abc import AsyncGenerator
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.core.security import verify_token
from app.db.models.user import User
from app.db.models.subscription import Subscription, UsageType
from app.services.subscription import SubscriptionService

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.onboarding_progress),
            selectinload(User.subscription).selectinload(Subscription.plan),
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_optional_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> User | None:
    """Get current user if authenticated, otherwise return None."""
    if credentials is None:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    return user if user and user.is_active else None


DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]


async def get_current_user_ws(token: str, db: AsyncSession) -> User | None:
    """
    Get current user from a token for WebSocket connections.

    Unlike the HTTP dependency, this takes the token directly since
    WebSocket connections handle auth differently.
    """
    payload = verify_token(token)

    if payload is None or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    return user if user and user.is_active else None


async def get_user_subscription(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Subscription:
    """Get the current user's subscription."""
    return await SubscriptionService.get_or_create_subscription(db, user)


UserSubscription = Annotated[Subscription, Depends(get_user_subscription)]


def require_usage(usage_type: UsageType) -> Callable:
    """Dependency factory that checks usage limits and increments on success."""

    async def check_usage(
        db: Annotated[AsyncSession, Depends(get_db)],
        subscription: Annotated[Subscription, Depends(get_user_subscription)],
    ) -> Subscription:
        can_use, message = await SubscriptionService.check_can_use(
            db, subscription, usage_type
        )
        if not can_use:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=message,
            )
        return subscription

    return check_usage


def require_feature(feature: str) -> Callable:
    """Dependency factory that checks feature access."""

    async def check_feature(
        db: Annotated[AsyncSession, Depends(get_db)],
        subscription: Annotated[Subscription, Depends(get_user_subscription)],
    ) -> Subscription:
        has_access, message = await SubscriptionService.check_feature_access(
            db, subscription, feature
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=message,
            )
        return subscription

    return check_feature


# Pre-built usage dependencies
RequireChatSession = Depends(require_usage(UsageType.CHAT_SESSION))
RequireVoidAnalysis = Depends(require_usage(UsageType.VOID_ANALYSIS))
RequireDemographicsReport = Depends(require_usage(UsageType.DEMOGRAPHICS_REPORT))
RequireEmailSend = Depends(require_usage(UsageType.EMAIL_SENT))
RequireDocumentParse = Depends(require_usage(UsageType.DOCUMENT_PARSED))

# Pre-built feature dependencies
RequirePlacerAccess = Depends(require_feature("placer"))
RequireSiteUSAAccess = Depends(require_feature("siteusa"))
RequireCoStarAccess = Depends(require_feature("costar"))
RequireEmailOutreach = Depends(require_feature("email_outreach"))
RequireAPIAccess = Depends(require_feature("api"))
