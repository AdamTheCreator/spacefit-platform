"""
Connectors API — health status, probing, enable/disable.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DBSession
from app.db.models.credential import SiteCredential
from app.models.credential import ConnectorProbeResponse, ConnectorStatusResponse
from app.services.connector_health import (
    get_all_connector_statuses,
    refresh_stale_connectors,
    run_health_probe,
)

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("/status", response_model=list[ConnectorStatusResponse])
async def get_connector_status(
    user: CurrentUser,
    db: DBSession,
    background_tasks: BackgroundTasks,
) -> list[ConnectorStatusResponse]:
    """
    Return health status for all of the user's connectors.

    This is a fast DB-only read. Stale connectors are refreshed in the
    background so subsequent calls return up-to-date statuses.
    """
    statuses = await get_all_connector_statuses(user.id, db)

    # Kick off background refresh for any stale connectors
    has_stale = any(s.connector_status == "stale" for s in statuses)
    if has_stale:
        background_tasks.add_task(refresh_stale_connectors, user.id, db)

    return statuses


@router.post("/{credential_id}/probe", response_model=ConnectorProbeResponse)
async def probe_connector(
    credential_id: str,
    user: CurrentUser,
    db: DBSession,
) -> ConnectorProbeResponse:
    """Run an on-demand health probe for a specific connector."""
    credential = await _get_user_credential(credential_id, user.id, db)
    return await run_health_probe(credential, db)


@router.post("/{credential_id}/disable", response_model=ConnectorStatusResponse)
async def disable_connector(
    credential_id: str,
    user: CurrentUser,
    db: DBSession,
) -> ConnectorStatusResponse:
    """Disable a connector. It will not be used for analysis until re-enabled."""
    credential = await _get_user_credential(credential_id, user.id, db)
    now = datetime.now(timezone.utc)

    await db.execute(
        update(SiteCredential)
        .where(SiteCredential.id == credential.id)
        .values(
            connector_status="disabled",
            disabled_at=now,
            disabled_reason="Disabled by user",
        )
    )
    await db.commit()

    # Re-fetch to return up-to-date status
    statuses = await get_all_connector_statuses(user.id, db)
    match = next((s for s in statuses if str(s.credential_id) == credential_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Connector not found after update")
    return match


@router.post("/{credential_id}/enable", response_model=ConnectorStatusResponse)
async def enable_connector(
    credential_id: str,
    user: CurrentUser,
    db: DBSession,
) -> ConnectorStatusResponse:
    """Re-enable a disabled connector. Resets to stale so a probe will run."""
    credential = await _get_user_credential(credential_id, user.id, db)

    await db.execute(
        update(SiteCredential)
        .where(SiteCredential.id == credential.id)
        .values(
            connector_status="stale",
            disabled_at=None,
            disabled_reason=None,
        )
    )
    await db.commit()

    statuses = await get_all_connector_statuses(user.id, db)
    match = next((s for s in statuses if str(s.credential_id) == credential_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Connector not found after update")
    return match


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_user_credential(
    credential_id: str,
    user_id: str,
    db: AsyncSession,
) -> SiteCredential:
    result = await db.execute(
        select(SiteCredential).where(
            SiteCredential.id == credential_id,
            SiteCredential.user_id == user_id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    return credential
