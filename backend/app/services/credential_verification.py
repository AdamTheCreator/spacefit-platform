"""
Credential verification service.
Tests login before accepting credentials and validates sessions on startup.

Handles CAPTCHA-protected sites like Placer.ai by:
1. Detecting CAPTCHA challenges during login
2. Returning specific error codes for CAPTCHA blocking
3. Supporting manual session refresh workflow for CAPTCHA-protected sites
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
from app.scrapers.base import ProgressUpdate, LoginResult


@dataclass
class VerificationResult:
    """Result of a credential verification."""

    success: bool
    message: str
    session_valid: bool = False
    requires_login: bool = True
    # CAPTCHA-specific fields
    captcha_detected: bool = False
    captcha_type: str | None = None
    requires_manual_session: bool = False
    error_type: str | None = None  # "captcha", "invalid_credentials", "network", etc.
    screenshot_path: str | None = None


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

    For sites that require manual login (e.g., Placer.ai with CAPTCHA),
    this will detect the CAPTCHA and return appropriate information.
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

    # Check if this site typically requires manual login
    if scraper.requires_manual_login:
        # For CAPTCHA-protected sites, check if we have an existing valid session
        storage_path = manager._get_storage_path(user_id, site_name)
        from app.services.browser.session import is_session_valid

        if is_session_valid(storage_path):
            # We have a valid session - verify it works
            async with manager.get_context(user_id, site_name, load_session=True) as context:
                if await scraper.is_logged_in(context):
                    return VerificationResult(
                        success=True,
                        message="Existing session is valid. Credentials accepted.",
                        session_valid=True,
                        requires_login=False,
                    )

        # No valid session - try login with CAPTCHA detection
        await manager.clear_session(user_id, site_name)

        async with manager.get_context(user_id, site_name, load_session=False) as context:
            # Use CAPTCHA-aware login method
            login_result: LoginResult = await scraper.login_with_captcha_detection(
                context, username, password
            )

            if login_result.success:
                return VerificationResult(
                    success=True,
                    message="Credentials verified successfully",
                    session_valid=True,
                    requires_login=False,
                )

            if login_result.captcha_detected:
                return VerificationResult(
                    success=False,
                    message=login_result.message,
                    session_valid=False,
                    requires_login=True,
                    captcha_detected=True,
                    captcha_type=login_result.captcha_type,
                    requires_manual_session=True,
                    error_type="captcha",
                    screenshot_path=login_result.screenshot_path,
                )

            return VerificationResult(
                success=False,
                message=login_result.message,
                session_valid=False,
                requires_login=True,
                error_type=login_result.error_type,
                screenshot_path=login_result.screenshot_path,
            )

    # Standard login flow for non-CAPTCHA sites
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
                error_type="invalid_credentials",
            )


async def validate_existing_session(
    credential: SiteCredential,
    db: AsyncSession,
    progress_callback: Callable[[ProgressUpdate], None] | None = None,
) -> VerificationResult:
    """
    Validate that an existing session is still working.

    Called on application startup or before using a scraper.

    For CAPTCHA-protected sites, this will NOT attempt automatic re-login
    if the session is expired, as it would likely fail due to CAPTCHA.
    Instead, it returns a result indicating manual session refresh is needed.
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
            # Session expired or invalid
            # For CAPTCHA-protected sites, don't attempt automatic re-login
            if scraper.requires_manual_login:
                credential.session_status = "expired"
                credential.session_error_message = (
                    f"Session expired. {scraper.display_name} requires manual login "
                    "due to CAPTCHA protection."
                )
                credential.session_last_checked = datetime.utcnow()
                await db.commit()

                return VerificationResult(
                    success=False,
                    message=f"Session expired. {scraper.display_name} requires manual session refresh due to CAPTCHA.",
                    session_valid=False,
                    requires_login=True,
                    captcha_detected=False,  # We didn't detect it, we just know it's likely
                    requires_manual_session=True,
                    error_type="session_expired_captcha_site",
                )

            # For non-CAPTCHA sites, try to re-login automatically
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
                    error_type="decryption_error",
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
                    error_type="invalid_credentials",
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
    Returns session metadata including CAPTCHA site status.
    """
    manager = await BrowserManager.get_instance()
    storage_path = manager._get_storage_path(user_id, site_name)

    from app.services.browser.session import get_session_info, is_session_valid

    # Check if site requires manual login
    scraper = get_scraper(site_name)
    requires_manual_login = scraper.requires_manual_login if scraper else False

    info = get_session_info(storage_path)

    if info is None:
        return {
            "has_session": False,
            "status": "no_session",
            "requires_manual_login": requires_manual_login,
            "site_display_name": scraper.display_name if scraper else site_name,
        }

    is_valid = is_session_valid(storage_path)

    return {
        "has_session": True,
        "status": "valid" if is_valid else "expired",
        "age_hours": info.get("age_hours"),
        "last_modified": info.get("last_modified"),
        "requires_manual_login": requires_manual_login,
        "site_display_name": scraper.display_name if scraper else site_name,
    }


def site_requires_manual_login(site_name: str) -> bool:
    """Check if a site requires manual login due to CAPTCHA."""
    try:
        scraper = get_scraper(site_name)
        return scraper.requires_manual_login if scraper else False
    except Exception:
        return False


async def accept_credentials_for_manual_site(
    site_name: str,
    username: str,
    password: str,
    user_id: str,
    progress_callback: Callable[[ProgressUpdate], None] | None = None,
) -> VerificationResult:
    """
    Accept credentials for a CAPTCHA-protected site without verifying login.

    For sites like Placer.ai that require manual CAPTCHA solving:
    1. Store the credentials (they can be verified later via manual session)
    2. Return success with a message indicating manual session is needed

    The user will then need to use the manual session refresh flow to
    actually log in and establish a session.
    """
    scraper = get_scraper(site_name)

    if not scraper:
        return VerificationResult(
            success=False,
            message=f"No scraper available for site: {site_name}",
            session_valid=False,
            requires_login=True,
        )

    if not scraper.requires_manual_login:
        # For non-CAPTCHA sites, use normal verification
        return await verify_credentials(
            site_name, username, password, user_id, progress_callback
        )

    # For CAPTCHA sites, accept credentials without login verification
    # The credentials will be stored, but session won't be established
    return VerificationResult(
        success=True,
        message=(
            f"Credentials saved for {scraper.display_name}. "
            "Please use 'Refresh Session' to log in manually and solve the CAPTCHA."
        ),
        session_valid=False,
        requires_login=True,
        requires_manual_session=True,
    )


async def import_manual_session(
    user_id: str,
    site_name: str,
    session_file_path: str,
) -> VerificationResult:
    """
    Import a manually-created session file.

    This is used after the user completes the manual login flow
    (e.g., via debug_placer_login.py script).
    """
    import json
    import shutil
    from pathlib import Path

    manager = await BrowserManager.get_instance()
    scraper = get_scraper(site_name)

    if not scraper:
        return VerificationResult(
            success=False,
            message=f"No scraper available for site: {site_name}",
        )

    source_path = Path(session_file_path)
    if not source_path.exists():
        return VerificationResult(
            success=False,
            message=f"Session file not found: {session_file_path}",
        )

    # Validate the session file
    try:
        with open(source_path) as f:
            session_data = json.load(f)

        if "cookies" not in session_data:
            return VerificationResult(
                success=False,
                message="Invalid session file: missing cookies",
            )

        cookie_count = len(session_data.get("cookies", []))
        if cookie_count == 0:
            return VerificationResult(
                success=False,
                message="Invalid session file: no cookies found",
            )

    except json.JSONDecodeError:
        return VerificationResult(
            success=False,
            message="Invalid session file: not valid JSON",
        )

    # Copy to the correct location
    target_path = manager._get_storage_path(user_id, site_name)
    try:
        shutil.copy2(source_path, target_path)
    except Exception as e:
        return VerificationResult(
            success=False,
            message=f"Failed to import session: {str(e)}",
        )

    # Verify the session works
    async with manager.get_context(user_id, site_name, load_session=True) as context:
        if await scraper.is_logged_in(context):
            return VerificationResult(
                success=True,
                message=f"Session imported successfully for {scraper.display_name}",
                session_valid=True,
                requires_login=False,
            )
        else:
            return VerificationResult(
                success=False,
                message="Session imported but login verification failed. The session may be expired.",
                session_valid=False,
                requires_login=True,
            )
