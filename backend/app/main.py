import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.customers import router as customers_router
from app.api.credentials import router as credentials_router
from app.api.onboarding import router as onboarding_router
from app.api.deals import router as deals_router, properties_router, approvals_router
from app.api.documents import router as documents_router
from app.api.preferences import router as preferences_router
from app.api.outreach import router as outreach_router
from app.api.tracking import router as tracking_router
from app.api.subscription import router as subscription_router
from app.api.billing import router as billing_router
from app.api.connectors import router as connectors_router
from app.api.memory import router as memory_router
from app.api.reports import router as reports_router
from app.api.feedback import router as feedback_router
from app.api.projects import router as projects_router
from app.api.ai_config import router as ai_config_router
from app.api.admin import router as admin_router
from app.api.imports import router as imports_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import install_request_id_filter, request_id_var
from app.core.scrubbing import install_scrubbing_filter
from app.llm.client import aclose_llm_client
from app.mcp.server import mcp as spacegoose_mcp

import logging

# Install log filters before anything else has a chance to log. The
# scrubbing filter protects against accidental secret leakage; the
# request-ID filter attaches a per-request correlation ID that the
# middleware below populates on every HTTP request.
install_scrubbing_filter()
install_request_id_filter()

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Populate :data:`request_id_var` for every HTTP request and mirror
    the value back on the response as ``X-Request-ID``.

    If the client supplies an ``X-Request-ID`` we honor it (trimmed to a
    reasonable length to cap log bloat); otherwise we mint a fresh UUID.
    The ContextVar is reset on the way out so background tasks that
    outlive the request don't inherit a stale ID.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("x-request-id")
        rid = (incoming[:64] if incoming else uuid.uuid4().hex)
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await aclose_llm_client()
    await engine.dispose()


fastapi_app = FastAPI(
    title=settings.app_name,
    description="Commercial Real Estate Intelligence Platform",
    version="0.2.8.1",
    lifespan=lifespan,
)

fastapi_app.add_middleware(RequestIdMiddleware)


@fastapi_app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Any exception that reaches here is one a route handler did not
    # translate into an HTTPException. Log with the request ID so we
    # can correlate the generic 500 the client sees with the traceback.
    rid = request_id_var.get()
    logger.exception(
        "unhandled exception path=%s method=%s request_id=%s",
        request.url.path,
        request.method,
        rid,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": rid},
        headers={"X-Request-ID": rid},
    )


# Include routers
fastapi_app.include_router(auth_router, prefix=settings.api_prefix)
fastapi_app.include_router(chat_router, prefix=settings.api_prefix)
fastapi_app.include_router(customers_router, prefix=settings.api_prefix)
fastapi_app.include_router(credentials_router, prefix=settings.api_prefix)
fastapi_app.include_router(onboarding_router, prefix=settings.api_prefix)
fastapi_app.include_router(deals_router, prefix=settings.api_prefix)
fastapi_app.include_router(properties_router, prefix=settings.api_prefix)
fastapi_app.include_router(documents_router, prefix=settings.api_prefix)
fastapi_app.include_router(preferences_router, prefix=settings.api_prefix)
fastapi_app.include_router(outreach_router, prefix=settings.api_prefix)
fastapi_app.include_router(tracking_router, prefix=settings.api_prefix)
fastapi_app.include_router(subscription_router, prefix=settings.api_prefix)
fastapi_app.include_router(billing_router, prefix=settings.api_prefix)
fastapi_app.include_router(connectors_router, prefix=settings.api_prefix)
fastapi_app.include_router(memory_router, prefix=settings.api_prefix)
fastapi_app.include_router(approvals_router, prefix=settings.api_prefix)
fastapi_app.include_router(reports_router, prefix=settings.api_prefix)
fastapi_app.include_router(feedback_router, prefix=settings.api_prefix)
fastapi_app.include_router(projects_router, prefix=settings.api_prefix)
fastapi_app.include_router(ai_config_router, prefix=settings.api_prefix)
fastapi_app.include_router(admin_router, prefix=settings.api_prefix)
fastapi_app.include_router(imports_router, prefix=settings.api_prefix)

# Mount MCP HTTP+SSE transport -- external MCP clients (Claude Desktop, Cursor)
# can connect at /mcp.  Internal agents use SpacegooseMCPClient (in-process).
fastapi_app.mount("/mcp", spacegoose_mcp.sse_app())


@fastapi_app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Space Goose API", "version": fastapi_app.version}


@fastapi_app.get("/health")
async def health_check() -> dict[str, str | bool]:
    db_healthy = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_healthy = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": db_healthy,
    }


# Wrap the full ASGI app with CORS so even error responses generated by outer
# middleware layers (e.g., unhandled 500s) still include CORS headers.
app = CORSMiddleware(
    app=fastapi_app,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
