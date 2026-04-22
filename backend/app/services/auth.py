import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
    get_token_hash,
)
from app.db.models.user import User, RefreshToken, OAuthAccount, OnboardingProgress
from app.db.models.email_token import EmailToken
from app.models.user import UserCreate, TokenResponse
from app.services.email_service import send_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user with email and password."""
        result = await self.db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise ValueError("Email already registered")

        user = User(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
        )
        self.db.add(user)

        onboarding = OnboardingProgress(user=user)
        self.db.add(onboarding)

        await self.db.commit()
        await self.db.refresh(user)

        # Send verification email (non-blocking - failure does not block registration)
        try:
            await self.send_email_verification(user)
        except Exception as e:
            logger.warning(f"Failed to send verification email for {user.email}: {e}")

        return user

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """Authenticate user with email and password."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            return None

        if user.password_hash is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    async def create_tokens(
        self, user: User, device_info: str | None = None
    ) -> TokenResponse:
        """Create access and refresh tokens for a user."""
        access_token = create_access_token(user.id)
        refresh_token, token_hash = create_refresh_token(user.id)

        expires_at = datetime.utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )

        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
        )
        self.db.add(refresh_token_record)
        await self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse | None:
        """Refresh access token using refresh token.

        Wraps the two DB lookups in ``asyncio.wait_for`` so a cold or
        saturated Postgres doesn't hold the request long enough for the
        frontend's axios interceptor to give up and bounce the user to
        /login. 5s is well above the warm p99 and well below the user's
        perception of "stuck".
        """
        payload = verify_token(refresh_token)

        if payload is None or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        jti = payload.get("jti")

        if user_id is None or jti is None:
            return None

        try:
            result = await asyncio.wait_for(
                self.db.execute(
                    select(RefreshToken).where(
                        RefreshToken.user_id == user_id,
                        RefreshToken.token_hash.startswith(jti),
                        RefreshToken.revoked == False,
                        RefreshToken.expires_at > datetime.utcnow(),
                    )
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "auth.refresh_tokens: db lookup timed out user_id=%s", user_id
            )
            return None
        token_record = result.scalar_one_or_none()

        if token_record is None:
            return None

        token_record.revoked = True

        try:
            result = await asyncio.wait_for(
                self.db.execute(
                    select(User).where(User.id == user_id, User.is_active == True)
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "auth.refresh_tokens: user lookup timed out user_id=%s", user_id
            )
            return None
        user = result.scalar_one_or_none()

        if user is None:
            return None

        return await self.create_tokens(user, token_record.device_info)

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token."""
        payload = verify_token(refresh_token)

        if payload is None or payload.get("type") != "refresh":
            return False

        jti = payload.get("jti")
        user_id = payload.get("sub")

        if jti is None or user_id is None:
            return False

        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash.startswith(jti),
            )
        )
        token_record = result.scalar_one_or_none()

        if token_record:
            token_record.revoked = True
            await self.db.commit()
            return True

        return False

    async def get_or_create_oauth_user(
        self,
        provider: str,
        provider_account_id: str,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        avatar_url: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
    ) -> User:
        """Get or create a user from OAuth provider data."""
        result = await self.db.execute(
            select(OAuthAccount)
            .options(selectinload(OAuthAccount.user))
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
        oauth_account = result.scalar_one_or_none()

        if oauth_account:
            user = oauth_account.user
            oauth_account.access_token = access_token
            oauth_account.refresh_token = refresh_token
            oauth_account.expires_at = expires_at
            await self.db.commit()
            return user

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                email_verified=True,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
            )
            self.db.add(user)

            onboarding = OnboardingProgress(user=user)
            self.db.add(onboarding)

        oauth_account = OAuthAccount(
            user=user,
            provider=provider,
            provider_account_id=provider_account_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        self.db.add(oauth_account)

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def get_user_by_id(self, user_id: UUID | str) -> User | None:
        """Get user by ID."""
        user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
        result = await self.db.execute(select(User).where(User.id == user_id_str))
        return result.scalar_one_or_none()

    async def update_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """Update user password."""
        if user.password_hash is None:
            return False

        if not verify_password(current_password, user.password_hash):
            return False

        user.password_hash = hash_password(new_password)
        await self.db.commit()
        return True

    async def send_email_verification(self, user: User) -> None:
        """Generate verification token and send verification email."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        email_token = EmailToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type="verify_email",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        self.db.add(email_token)
        await self.db.commit()

        verification_url = f"{settings.frontend_url}/verify-email?token={raw_token}"
        await send_verification_email(user.email, user.first_name or "", verification_url)

    async def verify_email_token(self, token: str) -> tuple[bool, str]:
        """Verify email token and mark user's email as verified.

        Returns (success, message) tuple.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = await self.db.execute(
            select(EmailToken).where(
                EmailToken.token_hash == token_hash,
                EmailToken.token_type == "verify_email",
            )
        )
        email_token = result.scalar_one_or_none()

        if email_token is None:
            return False, "Invalid verification token"

        if email_token.used_at is not None:
            return False, "Token has already been used"

        if email_token.expires_at < datetime.utcnow():
            return False, "Token has expired"

        # Mark token as used
        email_token.used_at = datetime.utcnow()

        # Mark user email as verified
        result = await self.db.execute(
            select(User).where(User.id == email_token.user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.email_verified = True

        await self.db.commit()
        return True, "Email verified successfully"

    async def send_password_reset(self, email: str) -> None:
        """Generate password reset token and send reset email.

        Silently returns if user not found (prevents email enumeration).
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        email_token = EmailToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type="password_reset",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        self.db.add(email_token)
        await self.db.commit()

        reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
        await send_password_reset_email(user.email, user.first_name or "", reset_url)

    async def reset_password_with_token(
        self, token: str, new_password: str
    ) -> tuple[bool, str]:
        """Reset password using token.

        Returns (success, message) tuple.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = await self.db.execute(
            select(EmailToken).where(
                EmailToken.token_hash == token_hash,
                EmailToken.token_type == "password_reset",
            )
        )
        email_token = result.scalar_one_or_none()

        if email_token is None:
            return False, "Invalid reset token"

        if email_token.used_at is not None:
            return False, "Token has already been used"

        if email_token.expires_at < datetime.utcnow():
            return False, "Token has expired"

        # Mark token as used
        email_token.used_at = datetime.utcnow()

        # Update user password
        result = await self.db.execute(
            select(User).where(User.id == email_token.user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.password_hash = hash_password(new_password)

        await self.db.commit()
        return True, "Password reset successfully"
