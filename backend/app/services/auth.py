import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    password_needs_rehash,
    verify_password,
    verify_token,
    get_token_hash,
)
from app.db.models.user import User, RefreshToken, OAuthAccount, OnboardingProgress
from app.db.models.email_token import EmailToken
from app.db.models.auth_event import (
    EVENT_EMAIL_VERIFIED,
    EVENT_PASSWORD_CHANGED,
    EVENT_REFRESH_REUSE,
    EVENT_RESET_COMPLETED,
)
from app.models.user import UserCreate, TokenResponse, normalize_email
from app.services.auth_audit import record_auth_event
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

        # Transparent upgrade: re-hash legacy (bcrypt) hashes with the current
        # default (argon2id) on successful login. No forced mass reset.
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            await self.db.commit()

        return user

    async def _issue_tokens(
        self,
        user: User,
        device_info: str | None,
        family_id: str | None,
    ) -> tuple[TokenResponse, RefreshToken]:
        """Mint an access + refresh token pair and persist the refresh row.

        ``family_id`` links a refresh token to its rotation lineage; a fresh
        login starts a new family, a rotation carries the existing one.
        """
        access_token = create_access_token(user.id)
        refresh_token, token_hash = create_refresh_token(user.id)

        expires_at = datetime.utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )

        record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            family_id=family_id or str(uuid4()),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        return (
            TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_expire_minutes * 60,
            ),
            record,
        )

    async def create_tokens(
        self, user: User, device_info: str | None = None
    ) -> TokenResponse:
        """Create access and refresh tokens for a user (new session/family)."""
        token_response, _ = await self._issue_tokens(user, device_info, None)
        return token_response

    async def _revoke_family(self, record: RefreshToken) -> None:
        """Revoke every refresh token in a token's rotation family."""
        if record.family_id:
            result = await self.db.execute(
                select(RefreshToken).where(
                    RefreshToken.family_id == record.family_id
                )
            )
            for token in result.scalars().all():
                token.revoked = True
        else:
            record.revoked = True
        await self.db.commit()

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

        # Legacy JWTs issued before the hardening deploy carry a 16-char jti
        # (prefix of the stored hash); new JWTs carry the full 64-char hash.
        # Accept the legacy prefix for one TTL period so existing sessions
        # don't get mass-signed-out on deploy.
        predicate = (
            RefreshToken.token_hash == jti
            if len(jti) == 64
            else RefreshToken.token_hash.like(f"{jti}%")
        )
        try:
            result = await asyncio.wait_for(
                self.db.execute(
                    select(RefreshToken).where(
                        RefreshToken.user_id == user_id,
                        predicate,
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

        if token_record.revoked:
            # Refresh-token reuse: revoke the whole family and force re-login.
            logger.warning(
                "auth.refresh: reuse detected, revoking family user_id=%s", user_id
            )
            await self._revoke_family(token_record)
            await record_auth_event(
                self.db, EVENT_REFRESH_REUSE, user_id=str(user_id)
            )
            return None

        if token_record.expires_at <= datetime.utcnow():
            return None

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

        # Atomic rotation: conditionally revoke the presented token only if
        # it is still active. If a concurrent request already revoked it,
        # the UPDATE affects 0 rows — treat that as reuse/theft.
        atomically_revoked = await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.id == token_record.id,
                RefreshToken.revoked == False,  # noqa: E712
            )
            .values(revoked=True)
        )
        if atomically_revoked.rowcount == 0:  # type: ignore[attr-defined]
            # Another request beat us to it — revoke the family and bail.
            logger.warning(
                "auth.refresh: concurrent rotation detected, revoking family "
                "user_id=%s",
                user_id,
            )
            await self._revoke_family(token_record)
            await record_auth_event(
                self.db, EVENT_REFRESH_REUSE, user_id=str(user_id)
            )
            return None

        # Issue the successor in the same family, linked via replaced_by_id.
        token_response, new_record = await self._issue_tokens(
            user, token_record.device_info, token_record.family_id
        )
        token_record.replaced_by_id = new_record.id
        await self.db.commit()
        return token_response

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token."""
        payload = verify_token(refresh_token)

        if payload is None or payload.get("type") != "refresh":
            return False

        jti = payload.get("jti")
        user_id = payload.get("sub")

        if jti is None or user_id is None:
            return False

        # Accept legacy 16-char prefix jti as well as the new full-hash jti.
        predicate = (
            RefreshToken.token_hash == jti
            if len(jti) == 64
            else RefreshToken.token_hash.like(f"{jti}%")
        )
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                predicate,
            )
        )
        token_record = result.scalar_one_or_none()

        if token_record:
            token_record.revoked = True
            await self.db.commit()
            return True

        return False

    async def revoke_all_refresh_tokens(self, user_id: str) -> None:
        """Revoke every active refresh token for a user (sign out everywhere)."""
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .values(revoked=True)
        )
        await self.db.commit()

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
        email = normalize_email(email)
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

    async def get_user_id_by_email(self, email: str) -> str | None:
        """Resolve a normalized email to its user_id for audit logging.

        Used to associate login-failure events with the user even when
        authentication fails, so admin auth-event queries can find them.
        """
        result = await self.db.execute(
            select(User.id).where(User.email == normalize_email(email))
        )
        row = result.scalar_one_or_none()
        return str(row) if row else None

    async def update_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """Update user password."""
        if user.password_hash is None:
            return False

        if not verify_password(current_password, user.password_hash):
            return False

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.utcnow()
        await self.db.commit()
        # Sign out everywhere: a password change invalidates existing sessions.
        await self.revoke_all_refresh_tokens(user.id)
        await record_auth_event(self.db, EVENT_PASSWORD_CHANGED, user_id=user.id)
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
        sent = await send_verification_email(
            user.email, user.first_name or "", verification_url
        )
        if not sent:
            logger.error(
                "auth.email.send_failed event=verify_email user_id=%s", user.id
            )

    async def resend_verification(self, email: str) -> None:
        """Re-send the verification email if the account exists and is
        unverified. Enumeration-safe: returns silently otherwise."""
        result = await self.db.execute(
            select(User).where(User.email == normalize_email(email))
        )
        user = result.scalar_one_or_none()
        if user is None or user.email_verified:
            return
        await self.send_email_verification(user)

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
        if user:
            await record_auth_event(
                self.db, EVENT_EMAIL_VERIFIED, user_id=user.id
            )
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
        sent = await send_password_reset_email(
            user.email, user.first_name or "", reset_url
        )
        if not sent:
            logger.error(
                "auth.email.send_failed event=password_reset user_id=%s", user.id
            )

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

        # Invalidate all other outstanding password-reset tokens for this user.
        await self.db.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == email_token.user_id,
                EmailToken.token_type == "password_reset",
                EmailToken.used_at.is_(None),
            )
            .values(used_at=datetime.utcnow())
        )

        # Update user password
        result = await self.db.execute(
            select(User).where(User.id == email_token.user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.password_hash = hash_password(new_password)
            user.password_changed_at = datetime.utcnow()

        await self.db.commit()

        # Sign out everywhere after a reset.
        if user:
            await self.revoke_all_refresh_tokens(user.id)
            await record_auth_event(
                self.db, EVENT_RESET_COMPLETED, user_id=user.id
            )

        return True, "Password reset successfully"
