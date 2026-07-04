import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.core.config import settings
from app.core.security import create_oauth_state, verify_oauth_state
from app.db.models.user import OAuthAccount
from app.services.gmail import GmailService, is_gmail_configured
from pydantic import BaseModel, Field

from app.models.user import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    UserPasswordUpdate,
)
from app.services.auth import AuthService

logger = logging.getLogger(__name__)


class VerifyEmailRequest(BaseModel):
    token: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

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

    user = await auth_service.authenticate_user(login_data.email, login_data.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

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
    import httpx
    import logging
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

        redirect_url = (
            f"{settings.frontend_url}/auth/callback"
            f"?access_token={tokens.access_token}"
            f"&refresh_token={tokens.refresh_token}"
        )

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        return RedirectResponse(url=f"{settings.frontend_url}/login?error=google_auth_failed")


GMAIL_PROVIDER = "gmail"


class GmailAuthorizeResponse(BaseModel):
    authorization_url: str


class GmailStatusResponse(BaseModel):
    connected: bool
    email: str | None = None


@router.get("/gmail/authorize", response_model=GmailAuthorizeResponse)
async def gmail_authorize(current_user: CurrentUser) -> GmailAuthorizeResponse:
    """Return the Google consent URL to connect a Gmail account for sending.

    The frontend redirects the browser to this URL. We can't 302 straight from
    here because a top-level navigation wouldn't carry the Bearer token, so the
    initiating user is round-tripped through a signed ``state`` param instead.
    """
    if not is_gmail_configured():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Gmail integration is not configured on the server.",
        )

    state = create_oauth_state(current_user.id)
    authorization_url, _ = GmailService.get_authorization_url(state=state)
    return GmailAuthorizeResponse(authorization_url=authorization_url)


@router.get("/gmail/callback")
async def gmail_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the Gmail OAuth callback and store the connection for the user."""
    connections_url = f"{settings.frontend_url}/connections"

    if error or not code or not state:
        logger.warning("Gmail OAuth callback error: %s", error or "missing code/state")
        return RedirectResponse(url=f"{connections_url}?gmail=error")

    user_id = verify_oauth_state(state)
    if not user_id:
        logger.warning("Gmail OAuth callback with invalid/expired state")
        return RedirectResponse(url=f"{connections_url}?gmail=error")

    try:
        tokens = await asyncio.to_thread(GmailService.exchange_code, code)
        email = await asyncio.to_thread(GmailService(tokens).get_user_email)
        if not email:
            raise ValueError("Could not read the connected Gmail address")

        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == GMAIL_PROVIDER,
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = OAuthAccount(
                user_id=user_id,
                provider=GMAIL_PROVIDER,
                provider_account_id=email,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                expires_at=tokens.expiry,
            )
            db.add(account)
        else:
            account.provider_account_id = email
            account.access_token = tokens.access_token
            # Google only returns a refresh token on the first consent; keep the
            # existing one if this exchange didn't include a fresh value.
            if tokens.refresh_token:
                account.refresh_token = tokens.refresh_token
            account.expires_at = tokens.expiry

        await db.commit()
    except Exception:
        logger.exception("Gmail OAuth callback failed")
        return RedirectResponse(url=f"{connections_url}?gmail=error")

    return RedirectResponse(url=f"{connections_url}?gmail=connected")


@router.get("/gmail/status", response_model=GmailStatusResponse)
async def gmail_status(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> GmailStatusResponse:
    """Report whether the current user has a Gmail account connected for sending."""
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == GMAIL_PROVIDER,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        return GmailStatusResponse(connected=False)
    return GmailStatusResponse(connected=True, email=account.provider_account_id)


@router.delete("/gmail", status_code=status.HTTP_204_NO_CONTENT)
async def gmail_disconnect(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect the user's Gmail account (campaigns fall back to SMTP/dev)."""
    await db.execute(
        delete(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == GMAIL_PROVIDER,
        )
    )
    await db.commit()


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Request password reset email."""
    auth_service = AuthService(db)
    await auth_service.send_password_reset(request.email)
    return {"message": "If an account exists with this email, a reset link will be sent"}


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
