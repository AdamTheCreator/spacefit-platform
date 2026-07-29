import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.core.config import settings
from app.db.models.auth_event import (
    EVENT_ACCOUNT_LOCKED,
    EVENT_LOGIN,
    EVENT_LOGIN_FAILED,
    EVENT_RESET_REQUESTED,
)
from app.models.user import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserPasswordUpdate,
    UserResponse,
    normalize_email,
)
from app.services.auth import AuthService
from app.services.auth_audit import client_ip, record_auth_event
from app.services.auth_rate_limit import login_lockout, reset_limiter
from app.services.oauth_exchange import oauth_code_store

logger = logging.getLogger(__name__)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return normalize_email(v)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class OAuthExchangeRequest(BaseModel):
    code: str


def _login_keys(email: str, ip: str | None) -> list[str]:
    # Pair-scoped so a third party can't lock a victim's account by
    # spraying wrong passwords from an unrelated host. IP-only key
    # still throttles brute-force from a single source.
    if ip:
        return [f"email+ip:{email}|{ip}", f"ip:{ip}"]
    return [f"email:{email}"]

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a new user account."""
    auth_service = AuthService(db)

    try:
        user = await auth_service.register_user(user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        email_verified=user.email_verified,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        has_completed_onboarding=False,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Login with email and password."""
    auth_service = AuthService(db)
    email = login_data.email  # normalized by the schema validator
    ip = client_ip(request)
    keys = _login_keys(email, ip)

    # Progressive lockout: a locked key returns a distinct 429 + Retry-After,
    # never a masked 401, so it can't be confused with a wrong password.
    if settings.auth_rate_limit_enabled:
        wait = max((login_lockout.retry_after(k) for k in keys), default=0)
        if wait > 0:
            await record_auth_event(
                db, EVENT_ACCOUNT_LOCKED, request=request, detail="pre-check"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again later.",
                headers={"Retry-After": str(wait)},
            )

    user = await auth_service.authenticate_user(email, login_data.password)

    if user is None:
        locked_for = 0
        if settings.auth_rate_limit_enabled:
            for k in keys:
                locked_for = max(locked_for, login_lockout.register_failure(k))
        # Resolve the user_id for audit while keeping the HTTP response
        # enumeration-safe (same 401 regardless of whether the email exists).
        failed_user_id = await auth_service.get_user_id_by_email(email)
        await record_auth_event(
            db, EVENT_LOGIN_FAILED, request=request, user_id=failed_user_id
        )
        if locked_for > 0:
            await record_auth_event(
                db, EVENT_ACCOUNT_LOCKED, request=request, detail="threshold"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again later.",
                headers={"Retry-After": str(locked_for)},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    if settings.require_verified_email_for_login and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before logging in.",
        )

    if settings.auth_rate_limit_enabled:
        for k in keys:
            login_lockout.reset(k)

    await record_auth_event(db, EVENT_LOGIN, request=request, user_id=user.id)
    device_info = request.headers.get("User-Agent")
    return await auth_service.create_tokens(user, device_info)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)

    tokens = await auth_service.refresh_tokens(token_data.refresh_token)

    if tokens is None:
        # Log at info (not warning) — this fires on any expired/invalidated
        # refresh token, which is normal. The request_id injected by the
        # logging filter is the key data point for correlating with the
        # frontend axios.ts refresh branch.
        logger.info("auth.refresh: rejected (invalid or expired refresh token)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    logger.info("auth.refresh: ok")
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Logout by revoking refresh token."""
    auth_service = AuthService(db)
    await auth_service.revoke_refresh_token(token_data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user information."""
    has_completed = False
    if current_user.onboarding_progress:
        has_completed = current_user.onboarding_progress.completed_at is not None

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        email_verified=current_user.email_verified,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        has_completed_onboarding=has_completed,
    )


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(
    password_data: UserPasswordUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Update current user's password."""
    auth_service = AuthService(db)

    success = await auth_service.update_password(
        current_user, password_data.current_password, password_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )


@router.get("/google")
async def google_auth() -> RedirectResponse:
    """Initiate Google OAuth flow."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured",
        )

    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.google_client_id}"
        f"&redirect_uri={settings.google_redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )

    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
    state: str | None = None,
) -> RedirectResponse:
    """Handle Google OAuth callback."""
    import logging

    import httpx
    logger = logging.getLogger(__name__)

    # Handle OAuth error from Google (e.g. user denied access)
    if error or not code:
        logger.warning(f"Google OAuth error: {error}")
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=google_auth_failed")

    try:
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Google OAuth not configured",
            )

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri,
                },
            )

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                return RedirectResponse(url=f"{settings.frontend_url}/login?error=google_token_failed")

            token_data = token_response.json()
            access_token = token_data.get("access_token")

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_response.status_code != 200:
                logger.error(f"Userinfo fetch failed: {userinfo_response.text}")
                return RedirectResponse(url=f"{settings.frontend_url}/login?error=google_userinfo_failed")

            userinfo = userinfo_response.json()

        auth_service = AuthService(db)
        user = await auth_service.get_or_create_oauth_user(
            provider="google",
            provider_account_id=userinfo.get("id"),
            email=userinfo.get("email"),
            first_name=userinfo.get("given_name"),
            last_name=userinfo.get("family_name"),
            avatar_url=userinfo.get("picture"),
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
        )

        tokens = await auth_service.create_tokens(user)

        if settings.oauth_code_exchange_enabled:
            # Hand the SPA a single-use code instead of putting tokens in the
            # URL (which leaks into history / referrer / logs).
            code = oauth_code_store.issue(
                tokens.access_token, tokens.refresh_token, tokens.expires_in
            )
            return RedirectResponse(
                url=f"{settings.frontend_url}/auth/callback?code={code}"
            )

        redirect_url = (
            f"{settings.frontend_url}/auth/callback"
            f"?access_token={tokens.access_token}"
            f"&refresh_token={tokens.refresh_token}"
        )

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=google_auth_failed")


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Request password reset email. Enumeration-safe + rate-limited."""
    auth_service = AuthService(db)
    email = body.email
    ip = client_ip(request)

    allowed = True
    if settings.auth_rate_limit_enabled:
        email_ok = reset_limiter.allow(
            f"reset:email:{email}",
            settings.auth_reset_max_attempts,
            settings.auth_reset_window_seconds,
        )
        ip_ok = (
            reset_limiter.allow(
                f"reset:ip:{ip}",
                settings.auth_reset_max_attempts,
                settings.auth_reset_window_seconds,
            )
            if ip
            else True
        )
        allowed = email_ok and ip_ok

    await record_auth_event(db, EVENT_RESET_REQUESTED, request=request)
    if allowed:
        await auth_service.send_password_reset(email)
    # Identical response whether or not the email exists / was rate-limited.
    return {"message": "If an account exists with this email, a reset link will be sent"}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Re-send the email-verification link. Enumeration-safe + rate-limited."""
    auth_service = AuthService(db)
    email = body.email
    ip = client_ip(request)

    allowed = True
    if settings.auth_rate_limit_enabled:
        email_ok = reset_limiter.allow(
            f"verify:email:{email}",
            settings.auth_reset_max_attempts,
            settings.auth_reset_window_seconds,
        )
        ip_ok = (
            reset_limiter.allow(
                f"verify:ip:{ip}",
                settings.auth_reset_max_attempts,
                settings.auth_reset_window_seconds,
            )
            if ip
            else True
        )
        allowed = email_ok and ip_ok

    if allowed:
        await auth_service.resend_verification(email)
    return {"message": "If an account exists and is unverified, a link will be sent"}


@router.post("/oauth/exchange", response_model=TokenResponse)
async def oauth_exchange(body: OAuthExchangeRequest) -> TokenResponse:
    """Exchange a single-use OAuth handoff code for tokens."""
    entry = oauth_code_store.redeem(body.code)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        )
    return TokenResponse(
        access_token=entry.access_token,
        refresh_token=entry.refresh_token,
        expires_in=entry.expires_in,
    )


@router.post("/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verify user email with token."""
    auth_service = AuthService(db)
    success, message = await auth_service.verify_email_token(request.token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return {"message": message}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Reset password with token."""
    auth_service = AuthService(db)
    success, message = await auth_service.reset_password_with_token(
        request.token, request.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return {"message": message}
