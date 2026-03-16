from datetime import datetime, timezone
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.core.security import encrypt_credential, decrypt_credential
from app.db.models.credential import SiteCredential, AgentConnection
from app.models.credential import (
    SiteCredentialCreate,
    SiteCredentialUpdate,
    SiteCredentialResponse,
    AgentConnectionResponse,
    VerifyCredentialResponse,
)
from app.scrapers import list_all_sites

router = APIRouter(prefix="/credentials", tags=["credentials"])
logger = logging.getLogger(__name__)


@router.get("/sites", response_model=list[dict])
async def list_available_sites() -> list[dict]:
    """List all available sites that can be connected."""
    return list_all_sites()


@router.get("", response_model=list[SiteCredentialResponse])
async def list_credentials(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SiteCredentialResponse]:
    """List all credentials for current user (passwords not included)."""
    from app.services.credential_verification import site_requires_manual_login

    result = await db.execute(
        select(SiteCredential)
        .where(SiteCredential.user_id == current_user.id)
        .order_by(SiteCredential.site_name)
    )
    credentials = result.scalars().all()

    return [
        SiteCredentialResponse(
            id=c.id,
            site_name=c.site_name,
            site_url=c.site_url,
            username=decrypt_credential(c.username_encrypted),
            is_verified=c.is_verified,
            last_verified_at=c.last_verified_at,
            created_at=c.created_at,
            updated_at=c.updated_at,
            session_status=c.session_status or "unknown",
            session_last_checked=c.session_last_checked,
            session_error_message=c.session_error_message,
            last_used_at=c.last_used_at,
            total_uses=c.total_uses or 0,
            requires_manual_login=site_requires_manual_login(c.site_name),
        )
        for c in credentials
    ]


@router.post("", response_model=SiteCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    credential_data: SiteCredentialCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> SiteCredentialResponse:
    """Create a new site credential.

    For non-CAPTCHA sites (e.g. SiteUSA), verification is triggered
    automatically as a background task so the user doesn't have to
    separately click "Verify".
    """
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.user_id == current_user.id,
            SiteCredential.site_name == credential_data.site_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Credential for {credential_data.site_name} already exists",
        )

    additional_config_encrypted = None
    if credential_data.additional_config:
        import json
        additional_config_encrypted = encrypt_credential(
            json.dumps(credential_data.additional_config)
        )

    credential = SiteCredential(
        user_id=current_user.id,
        site_name=credential_data.site_name,
        site_url=credential_data.site_url,
        username_encrypted=encrypt_credential(credential_data.username),
        password_encrypted=encrypt_credential(credential_data.password),
        additional_config_encrypted=additional_config_encrypted,
    )

    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    # Auto-verify in the background for non-CAPTCHA sites
    from app.services.credential_verification import site_requires_manual_login

    if not site_requires_manual_login(credential_data.site_name):
        background_tasks.add_task(
            _background_verify_credential,
            credential_id=str(credential.id),
            user_id=current_user.id,
            site_name=credential_data.site_name,
            username=credential_data.username,
            password=credential_data.password,
        )

    return SiteCredentialResponse(
        id=credential.id,
        site_name=credential.site_name,
        site_url=credential.site_url,
        username=credential_data.username,
        is_verified=credential.is_verified,
        last_verified_at=credential.last_verified_at,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


async def _background_verify_credential(
    credential_id: str,
    user_id: str,
    site_name: str,
    username: str,
    password: str,
) -> None:
    """Run browser-based credential verification in the background."""
    from app.core.database import async_session_factory
    from app.services.credential_verification import verify_credentials

    logger.info("[bg-verify] Starting background verification (site=%s)", site_name)

    try:
        result = await verify_credentials(
            site_name=site_name,
            username=username,
            password=password,
            user_id=user_id,
        )

        logger.info("[bg-verify] Result (site=%s, success=%s)", site_name, result.success)

        async with async_session_factory() as db:
            db_result = await db.execute(
                select(SiteCredential).where(SiteCredential.id == credential_id)
            )
            credential = db_result.scalar_one_or_none()
            if credential:
                if result.success:
                    credential.is_verified = True
                    credential.session_status = "valid"
                    credential.session_error_message = None
                else:
                    credential.is_verified = False
                    credential.session_status = "error"
                    credential.session_error_message = result.message
                credential.last_verified_at = datetime.now(timezone.utc)
                credential.session_last_checked = datetime.now(timezone.utc)
                await db.commit()
    except Exception as e:
        logger.exception("[bg-verify] Error during background verification (site=%s)", site_name)
        try:
            async with async_session_factory() as db:
                db_result = await db.execute(
                    select(SiteCredential).where(SiteCredential.id == credential_id)
                )
                credential = db_result.scalar_one_or_none()
                if credential:
                    credential.session_status = "error"
                    credential.session_error_message = f"Verification error: {str(e)}"
                    credential.session_last_checked = datetime.now(timezone.utc)
                    await db.commit()
        except Exception:
            pass


@router.put("/{credential_id}", response_model=SiteCredentialResponse)
async def update_credential(
    credential_id: UUID,
    credential_data: SiteCredentialUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SiteCredentialResponse:
    """Update a credential."""
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    if credential_data.site_url is not None:
        credential.site_url = credential_data.site_url

    if credential_data.username is not None:
        credential.username_encrypted = encrypt_credential(credential_data.username)

    if credential_data.password is not None and credential_data.password.strip():
        credential.password_encrypted = encrypt_credential(credential_data.password)
        credential.is_verified = False

    if credential_data.additional_config is not None:
        import json
        credential.additional_config_encrypted = encrypt_credential(
            json.dumps(credential_data.additional_config)
        )

    await db.commit()
    await db.refresh(credential)

    return SiteCredentialResponse(
        id=credential.id,
        site_name=credential.site_name,
        site_url=credential.site_url,
        username=decrypt_credential(credential.username_encrypted),
        is_verified=credential.is_verified,
        last_verified_at=credential.last_verified_at,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a credential."""
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    await db.delete(credential)
    await db.commit()


@router.post("/{credential_id}/verify", response_model=VerifyCredentialResponse)
async def verify_credential(
    credential_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyCredentialResponse:
    """
    Verify a credential by testing the connection.

    This performs an actual browser-based login to verify the credentials work.
    Note: This can take 15-30 seconds.

    For CAPTCHA-protected sites (e.g., Placer.ai), this will detect the CAPTCHA
    and return information about manual session refresh requirements.
    """
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    # Import and run verification
    from app.services.credential_verification import verify_credentials, site_requires_manual_login
    from app.scrapers import list_available_scrapers

    site_name = credential.site_name.lower()

    # Check if we have a scraper for this site
    if site_name not in list_available_scrapers():
        # No scraper available - just mark as verified without testing
        credential.is_verified = True
        credential.last_verified_at = datetime.now(timezone.utc)
        credential.session_status = "unknown"
        await db.commit()

        return VerifyCredentialResponse(
            success=True,
            message="Credential saved (verification not available for this site)",
        )

    # Decrypt credentials for verification
    username = decrypt_credential(credential.username_encrypted)
    password = decrypt_credential(credential.password_encrypted)

    logger.info("[verify] Starting browser verification (site=%s)", site_name)

    # Run actual browser verification
    verification_result = await verify_credentials(
        site_name=site_name,
        username=username,
        password=password,
        user_id=current_user.id,
    )

    logger.info(
        "[verify] Result (site=%s success=%s captcha=%s requires_manual=%s)",
        site_name,
        verification_result.success,
        verification_result.captcha_detected,
        verification_result.requires_manual_session,
    )

    # Update credential status based on result
    if verification_result.captcha_detected or verification_result.requires_manual_session:
        # CAPTCHA detected - credentials may be valid, but we can't verify automatically
        # Store credentials anyway but mark as needing manual session
        credential.is_verified = False  # Not verified yet, but stored
        credential.last_verified_at = datetime.now(timezone.utc)
        credential.session_status = "requires_manual_login"
        credential.session_last_checked = datetime.now(timezone.utc)
        credential.session_error_message = verification_result.message
    elif verification_result.success:
        credential.is_verified = True
        credential.last_verified_at = datetime.now(timezone.utc)
        credential.session_status = "valid"
        credential.session_last_checked = datetime.now(timezone.utc)
        credential.session_error_message = None
    else:
        credential.is_verified = False
        credential.last_verified_at = datetime.now(timezone.utc)
        credential.session_status = "error"
        credential.session_last_checked = datetime.now(timezone.utc)
        credential.session_error_message = verification_result.message

    await db.commit()

    return VerifyCredentialResponse(
        success=verification_result.success,
        message=verification_result.message,
        captcha_detected=verification_result.captcha_detected,
        requires_manual_session=verification_result.requires_manual_session,
    )


@router.post("/{credential_id}/accept-for-manual-login", response_model=VerifyCredentialResponse)
async def accept_credential_for_manual_login(
    credential_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyCredentialResponse:
    """
    Accept a credential for a CAPTCHA-protected site without verifying login.

    For sites like Placer.ai that require manual CAPTCHA solving:
    1. Stores the credentials without attempting login
    2. Marks the credential as needing manual session refresh

    The user should then use the manual session refresh flow to log in.
    """
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    from app.services.credential_verification import site_requires_manual_login
    from app.scrapers import get_scraper

    site_name = credential.site_name.lower()
    scraper = get_scraper(site_name)

    if scraper and not scraper.requires_manual_login:
        # Site doesn't require manual login - use normal verification
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{scraper.display_name} does not require manual login. Use /verify instead.",
        )

    # Accept the credential without login verification
    credential.is_verified = False  # Will be True after manual session refresh
    credential.last_verified_at = datetime.now(timezone.utc)
    credential.session_status = "requires_manual_login"
    credential.session_last_checked = datetime.now(timezone.utc)
    credential.session_error_message = "Awaiting manual session refresh"

    await db.commit()

    display_name = scraper.display_name if scraper else credential.site_name

    return VerifyCredentialResponse(
        success=True,
        message=f"Credentials saved for {display_name}. Please use 'Refresh Session' to log in manually and solve the CAPTCHA.",
        captcha_detected=False,
        requires_manual_session=True,
    )


@router.get("/{credential_id}/manual-session-info")
async def get_manual_session_info(
    credential_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Get information for manual session refresh.

    Returns:
    - Login URL for the site
    - Instructions for manual login
    - Session file path where the session should be saved
    """
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    from app.scrapers import get_scraper
    from app.services.browser.manager import BrowserManager

    site_name = credential.site_name.lower()
    scraper = get_scraper(site_name)

    if scraper is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No scraper available for {credential.site_name}",
        )

    manager = await BrowserManager.get_instance()
    session_path = manager._get_storage_path(current_user.id, site_name)

    # Decrypt username to show in instructions (password hidden)
    username = decrypt_credential(credential.username_encrypted)

    return {
        "credential_id": credential.id,
        "site_name": credential.site_name,
        "site_display_name": scraper.display_name,
        "login_url": f"{scraper.site_url}/auth/signin",
        "requires_manual_login": scraper.requires_manual_login,
        "username_hint": username,
        "session_file_path": str(session_path),
        "instructions": [
            f"1. Run the manual login script: python scripts/debug_placer_login.py --user-id {current_user.id}",
            f"2. Enter your credentials in the browser window",
            "3. Solve the CAPTCHA when it appears",
            "4. Complete the login process",
            "5. The script will automatically save your session",
            "6. Return here and click 'Verify Session' to confirm",
        ],
        "script_command": f"python scripts/debug_placer_login.py --user-id {current_user.id}",
    }


@router.post("/{credential_id}/verify-manual-session", response_model=VerifyCredentialResponse)
async def verify_manual_session(
    credential_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyCredentialResponse:
    """
    Verify that a manually-created session is working.

    Call this after completing the manual login flow to confirm
    the session was saved correctly and is valid.
    """
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    from app.scrapers import get_scraper
    from app.services.browser.manager import BrowserManager
    from app.services.browser.session import is_session_valid

    site_name = credential.site_name.lower()
    scraper = get_scraper(site_name)

    if scraper is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No scraper available for {credential.site_name}",
        )

    manager = await BrowserManager.get_instance()
    storage_path = manager._get_storage_path(current_user.id, site_name)

    # Check if session file exists and is valid
    if not is_session_valid(storage_path):
        return VerifyCredentialResponse(
            success=False,
            message="No valid session found. Please complete the manual login process first.",
            requires_manual_session=True,
        )

    # Try to verify the session actually works
    async with manager.get_context(current_user.id, site_name, load_session=True) as context:
        is_logged_in = await scraper.is_logged_in(context)

        if is_logged_in:
            # Session is valid!
            credential.is_verified = True
            credential.last_verified_at = datetime.now(timezone.utc)
            credential.session_status = "valid"
            credential.session_last_checked = datetime.now(timezone.utc)
            credential.session_error_message = None

            await db.commit()

            return VerifyCredentialResponse(
                success=True,
                message=f"Session verified successfully for {scraper.display_name}!",
            )
        else:
            # Session file exists but doesn't work
            credential.session_status = "error"
            credential.session_last_checked = datetime.now(timezone.utc)
            credential.session_error_message = "Session file exists but login verification failed"

            await db.commit()

            return VerifyCredentialResponse(
                success=False,
                message="Session file found but login verification failed. Please try the manual login process again.",
                requires_manual_session=True,
            )


@router.get("/{credential_id}/session-status")
async def get_session_status(
    credential_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get the current session status for a credential."""
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == str(credential_id),
            SiteCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    # Also check file-based session status
    from app.services.credential_verification import check_session_status

    file_status = await check_session_status(
        current_user.id,
        credential.site_name,
    )

    return {
        "credential_id": credential.id,
        "site_name": credential.site_name,
        "session_status": credential.session_status or "unknown",
        "is_verified": credential.is_verified,
        "last_verified_at": credential.last_verified_at,
        "session_last_checked": credential.session_last_checked,
        "session_error_message": credential.session_error_message,
        "file_session": file_status,
    }


@router.get("/connections", response_model=list[AgentConnectionResponse])
async def list_agent_connections(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AgentConnectionResponse]:
    """List all agent connections for current user."""
    result = await db.execute(
        select(AgentConnection)
        .where(AgentConnection.user_id == current_user.id)
        .order_by(AgentConnection.agent_type)
    )
    connections = result.scalars().all()

    return [AgentConnectionResponse.model_validate(c) for c in connections]
