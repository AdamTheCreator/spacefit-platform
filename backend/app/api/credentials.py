from datetime import datetime, timezone
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
        )
        for c in credentials
    ]


@router.post("", response_model=SiteCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    credential_data: SiteCredentialCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SiteCredentialResponse:
    """Create a new site credential."""
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
    from app.services.credential_verification import verify_credentials
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

    print(f"[VERIFY] Starting browser verification for {site_name}")
    print(f"[VERIFY] Username: {username}, Password length: {len(password)}")

    # Run actual browser verification
    verification_result = await verify_credentials(
        site_name=site_name,
        username=username,
        password=password,
        user_id=current_user.id,
    )

    print(f"[VERIFY] Result: success={verification_result.success}, message={verification_result.message}")

    # Update credential status based on result
    credential.is_verified = verification_result.success
    credential.last_verified_at = datetime.now(timezone.utc)
    credential.session_status = "valid" if verification_result.success else "error"
    credential.session_last_checked = datetime.now(timezone.utc)
    credential.session_error_message = (
        None if verification_result.success else verification_result.message
    )

    await db.commit()

    return VerifyCredentialResponse(
        success=verification_result.success,
        message=verification_result.message,
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
