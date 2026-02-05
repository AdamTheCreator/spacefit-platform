"""
Browser-based authentication API endpoints.

Provides endpoints for interactive browser login for CAPTCHA-protected sites.
Uses WebSocket for real-time status updates during the login process.
"""

import asyncio
import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser, get_current_user_ws
from app.core.security import decrypt_credential
from app.db.models.credential import SiteCredential
from app.services.browser.interactive_login import (
    InteractiveLoginManager,
    LoginStatus,
    LoginStatusUpdate,
    get_site_login_config,
    start_interactive_login,
)
from app.services.connector_health import update_connector_on_success


router = APIRouter(prefix="/browser-auth", tags=["browser-auth"])
logger = logging.getLogger(__name__)


class BrowserLoginRequest(BaseModel):
    """Request to start a browser-based login session."""
    credential_id: str | None = None  # If provided, prefills credentials
    prefill_username: str | None = None
    prefill_password: str | None = None
    timeout_seconds: int = 300


class BrowserLoginResponse(BaseModel):
    """Response from starting a browser login."""
    session_id: str
    status: str
    message: str
    websocket_url: str


class LoginStatusResponse(BaseModel):
    """Status update response."""
    status: str
    message: str
    progress_pct: int
    timestamp: str


# Store active login sessions
_active_sessions: dict[str, InteractiveLoginManager] = {}


@router.get("/sites")
async def list_browser_login_sites() -> list[dict]:
    """List sites that support browser-based login."""
    from app.services.browser.interactive_login import SITE_LOGIN_CONFIGS

    return [
        {
            "site_name": name,
            "display_name": config["display_name"],
            "login_url": config["login_url"],
        }
        for name, config in SITE_LOGIN_CONFIGS.items()
    ]


@router.get("/sites/{site_name}")
async def get_browser_login_site_info(site_name: str) -> dict:
    """Get browser login info for a specific site."""
    config = get_site_login_config(site_name)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site '{site_name}' not found or doesn't support browser login",
        )

    return {
        "site_name": site_name,
        "display_name": config["display_name"],
        "login_url": config["login_url"],
        "requires_captcha": True,  # All browser-login sites have CAPTCHA
    }


@router.post("/start/{site_name}")
async def start_browser_login(
    site_name: str,
    request: BrowserLoginRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BrowserLoginResponse:
    """
    Start a browser-based login session.

    This opens a browser window for the user to complete login manually.
    Use the WebSocket endpoint to receive real-time status updates.

    Note: For cloud deployments, this requires browser streaming capability.
    For local/self-hosted, the browser window opens on the server machine.
    """
    config = get_site_login_config(site_name)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site '{site_name}' not configured for browser login",
        )

    # Get prefill credentials if credential_id provided
    prefill_username = request.prefill_username
    prefill_password = request.prefill_password

    if request.credential_id:
        result = await db.execute(
            select(SiteCredential).where(
                SiteCredential.id == request.credential_id,
                SiteCredential.user_id == current_user.id,
            )
        )
        credential = result.scalar_one_or_none()

        if credential:
            try:
                prefill_username = prefill_username or decrypt_credential(
                    credential.username_encrypted
                )
                prefill_password = prefill_password or decrypt_credential(
                    credential.password_encrypted
                )
            except Exception:
                pass  # Ignore decryption errors, just don't prefill

    # Generate session ID
    import uuid
    session_id = str(uuid.uuid4())

    # Create login manager (but don't start yet - that happens via WebSocket)
    manager = InteractiveLoginManager(
        site_name=site_name,
        user_id=current_user.id,
    )
    _active_sessions[session_id] = manager

    return BrowserLoginResponse(
        session_id=session_id,
        status="ready",
        message=f"Browser login session ready for {config['display_name']}. Connect to WebSocket to start.",
        websocket_url=f"/api/v1/browser-auth/ws/{session_id}",
    )


@router.websocket("/ws/{session_id}")
async def browser_login_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    WebSocket endpoint for browser login status updates.

    Connect to this WebSocket after calling /start/{site_name}.
    The browser window will open and status updates will be streamed here.

    Messages from server:
    - {"type": "status", "data": LoginStatusResponse}
    - {"type": "complete", "data": {"success": bool, "message": str}}

    Messages from client:
    - {"type": "cancel"} - Cancel the login process
    """
    await websocket.accept()

    # Get the login manager
    manager = _active_sessions.get(session_id)
    if not manager:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Invalid session ID"},
        })
        await websocket.close()
        return

    # Authenticate user from WebSocket
    try:
        # Try to get token from query params
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Authentication required. Pass token as query param."},
            })
            await websocket.close()
            return

        user = await get_current_user_ws(token, db)
        if not user:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Invalid authentication token"},
            })
            await websocket.close()
            return
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"message": f"Authentication error: {str(e)}"},
        })
        await websocket.close()
        return

    # Status callback that sends updates via WebSocket
    async def status_callback(update: LoginStatusUpdate):
        try:
            await websocket.send_json({
                "type": "status",
                "data": {
                    "status": update.status.value,
                    "message": update.message,
                    "progress_pct": update.progress_pct,
                    "timestamp": update.timestamp.isoformat(),
                },
            })
        except Exception:
            pass  # WebSocket may be closed

    manager.status_callback = status_callback

    # Get site config
    config = get_site_login_config(manager.site_name)
    if not config:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Site configuration not found"},
        })
        await websocket.close()
        return

    # Start login in background task
    login_task = asyncio.create_task(
        manager.start_login(
            login_url=config["login_url"],
            success_url_patterns=config["success_url_patterns"],
        )
    )

    try:
        # Listen for client messages while login is in progress
        while not login_task.done():
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=1.0,
                )

                if message.get("type") == "cancel":
                    manager.cancel()
                    await websocket.send_json({
                        "type": "status",
                        "data": {
                            "status": "cancelled",
                            "message": "Login cancelled by user",
                            "progress_pct": 100,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    })
                    break

            except asyncio.TimeoutError:
                continue  # No message, keep waiting
            except WebSocketDisconnect:
                manager.cancel()
                break

        # Get final result
        if not login_task.done():
            login_task.cancel()
            try:
                await login_task
            except asyncio.CancelledError:
                pass

        result = login_task.result() if login_task.done() else None

        if result:
            # Update credential status in database
            if result.status == LoginStatus.SUCCESS:
                # Find and update the credential
                db_result = await db.execute(
                    select(SiteCredential).where(
                        SiteCredential.user_id == user.id,
                        SiteCredential.site_name == manager.site_name,
                    )
                )
                credential = db_result.scalar_one_or_none()

                if credential:
                    credential.is_verified = True
                    credential.session_status = "valid"
                    credential.session_last_checked = datetime.utcnow()
                    credential.session_error_message = None
                    credential.last_verified_at = datetime.utcnow()
                    await db.commit()
                    # Update connector health state
                    await update_connector_on_success(credential, db)
                else:
                    logger.warning(
                        "[browser-auth] Login succeeded but no credential record found (site=%s)",
                        manager.site_name,
                    )
            elif result.status in (LoginStatus.FAILED, LoginStatus.TIMEOUT):
                # Update credential to reflect failure
                db_result = await db.execute(
                    select(SiteCredential).where(
                        SiteCredential.user_id == user.id,
                        SiteCredential.site_name == manager.site_name,
                    )
                )
                credential = db_result.scalar_one_or_none()
                if credential:
                    credential.session_status = "error"
                    credential.session_last_checked = datetime.utcnow()
                    credential.session_error_message = result.message
                    await db.commit()

            await websocket.send_json({
                "type": "complete",
                "data": {
                    "success": result.status == LoginStatus.SUCCESS,
                    "message": result.message,
                    "status": result.status.value,
                },
            })

    except WebSocketDisconnect:
        manager.cancel()
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"message": f"Error: {str(e)}"},
        })
    finally:
        # Cleanup
        _active_sessions.pop(session_id, None)
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/cancel/{session_id}")
async def cancel_browser_login(
    session_id: str,
    current_user: CurrentUser,
) -> dict:
    """Cancel an active browser login session."""
    manager = _active_sessions.get(session_id)
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    manager.cancel()
    _active_sessions.pop(session_id, None)

    return {"status": "cancelled", "message": "Login session cancelled"}
