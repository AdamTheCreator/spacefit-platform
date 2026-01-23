"""
Credential verification service.
Tests login before accepting credentials and validates sessions on startup.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.credential import SiteCredential
from app.core.security import decrypt_credential
from app.services.browser.manager import BrowserManager
from app.scrapers import get_scraper, list_available_scrapers
from app.scrapers.base import ProgressUpdate


@dataclass
class VerificationResult:
    """Result of a credential verification."""

    success: bool
    message: str
    session_valid: bool = False
    requires_login: bool = True


async def verify_credentials(
    site_name: str,
    username: str,
    password: str,
    user_id: str,
    progress_callback: Callable[[ProgressUpdate], None] | None = None,
) -> VerificationResult:
    """
    Verify credentials by attempting to log in.

    This is called when a user saves new credentials.
    Creates a fresh browser context and attempts login.
    """
    if site_name.lower() not in list_available_scrapers():
        return VerificationResult(
            success=False,
            message=f"No scraper available for site: {site_name}",
            session_valid=False,
            requires_login=True,
        )

    manager = await BrowserManager.get_instance()
    scraper = get_scraper(site_name, progress_callback=progress_callback)

    # Clear any existing session for fresh verification
    await manager.clear_session(user_id, site_name)

    async with manager.get_context(user_id, site_name, load_session=False) as context:
        success = await scraper.login(context, username, password)

        if success:
            return VerificationResult(
                success=True,
                message="Credentials verified successfully",
                session_valid=True,
                requires_login=False,
            )
        else:
            return VerificationResult(
                success=False,
                message="Login failed. Please check your credentials.",
                session_valid=False,
                requires_login=True,
            )


async def validate_existing_session(
    credential: SiteCredential,
    db: AsyncSession,
    progress_callback: Callable[[ProgressUpdate], None] | None = None,
) -> VerificationResult:
    """
    Validate that an existing session is still working.

    Called on application startup or before using a scraper.
    """
    site_name = credential.site_name.lower()

    if site_name not in list_available_scrapers():
        return VerificationResult(
            success=False,
            message=f"No scraper available for site: {site_name}",
            session_valid=False,
            requires_login=True,
        )

    manager = await BrowserManager.get_instance()
    scraper = get_scraper(site_name, progress_callback=progress_callback)

    async with manager.get_context(
        credential.user_id,
        site_name,
        load_session=True,
    ) as context:
        if await scraper.is_logged_in(context):
            # Update session status
            credential.session_status = "valid"
            credential.session_last_checked = datetime.utcnow()
            credential.session_error_message = None
            await db.commit()

            return VerificationResult(
                success=True,
                message="Session is valid",
                session_valid=True,
                requires_login=False,
            )
        else:
            # Session expired, try to re-login
            try:
                username = decrypt_credential(credential.username_encrypted)
                password = decrypt_credential(credential.password_encrypted)
            except Exception as e:
                credential.session_status = "error"
                credential.session_error_message = f"Failed to decrypt credentials: {str(e)}"
                credential.session_last_checked = datetime.utcnow()
                await db.commit()

                return VerificationResult(
                    success=False,
                    message="Failed to decrypt stored credentials",
                    session_valid=False,
                    requires_login=True,
                )

            success = await scraper.login(context, username, password)

            if success:
                credential.session_status = "valid"
                credential.session_last_checked = datetime.utcnow()
                credential.session_error_message = None
                credential.is_verified = True
                credential.last_verified_at = datetime.utcnow()
                await db.commit()

                return VerificationResult(
                    success=True,
                    message="Session refreshed",
                    session_valid=True,
                    requires_login=False,
                )
            else:
                credential.session_status = "error"
                credential.session_error_message = "Re-login failed"
                credential.session_last_checked = datetime.utcnow()
                credential.is_verified = False
                await db.commit()

                return VerificationResult(
                    success=False,
                    message="Session expired and re-login failed. Please update your credentials.",
                    session_valid=False,
                    requires_login=True,
                )


async def get_valid_session(
    credential: SiteCredential,
    db: AsyncSession,
    progress_callback: Callable[[ProgressUpdate], None] | None = None,
) -> tuple[bool, str | None]:
    """
    Ensure we have a valid session for the credential.
    Returns (success, error_message).

    This is the main entry point for agents that need to use browser automation.
    """
    result = await validate_existing_session(credential, db, progress_callback)

    if result.success:
        # Update usage stats
        credential.last_used_at = datetime.utcnow()
        credential.total_uses = (credential.total_uses or 0) + 1
        await db.commit()
        return True, None

    return False, result.message


async def validate_all_sessions_on_startup(db: AsyncSession) -> dict[str, bool]:
    """
    Validate all stored sessions on application startup.

    Returns dict of credential_id -> is_valid
    """
    result = await db.execute(
        select(SiteCredential).where(SiteCredential.is_verified == True)
    )
    credentials = result.scalars().all()

    validation_results = {}

    for credential in credentials:
        try:
            result = await validate_existing_session(credential, db)
            validation_results[credential.id] = result.success
        except Exception:
            validation_results[credential.id] = False
            credential.session_status = "error"
            credential.session_error_message = "Validation failed on startup"
            credential.session_last_checked = datetime.utcnow()

    await db.commit()
    return validation_results


async def check_session_status(
    user_id: str,
    site_name: str,
) -> dict:
    """
    Quick check of session status without full validation.
    Returns session metadata.
    """
    manager = await BrowserManager.get_instance()
    storage_path = manager._get_storage_path(user_id, site_name)

    from app.services.browser.session import get_session_info, is_session_valid

    info = get_session_info(storage_path)

    if info is None:
        return {
            "has_session": False,
            "status": "no_session",
        }

    return {
        "has_session": True,
        "status": "valid" if is_session_valid(storage_path) else "expired",
        "age_hours": info.get("age_hours"),
        "last_modified": info.get("last_modified"),
    }
