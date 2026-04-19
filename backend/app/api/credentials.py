"""Credentials / Data Source preferences API.

DEPRECATED: Browser-credential flows have been removed. This module now
only exposes user data-source preference toggles (CoStar / Placer / SiteUSA)
that drive import CTAs in the frontend. Will be fully reworked in Phase 2.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.db.models.credential import SiteCredential, AgentConnection
from app.models.credential import (
    SiteCredentialResponse,
    AgentConnectionResponse,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])
logger = logging.getLogger(__name__)


DATA_SOURCES = [
    {"name": "costar", "display_name": "CoStar", "import_type": "csv"},
    {"name": "placer", "display_name": "Placer.ai", "import_type": "pdf"},
    {"name": "siteusa", "display_name": "SiteUSA", "import_type": "csv"},
]


@router.get("/sites", response_model=list[dict])
async def list_available_sites() -> list[dict]:
    """List available data sources."""
    return DATA_SOURCES


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
            username="",
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
