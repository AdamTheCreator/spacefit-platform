from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.customers import router as customers_router
from app.api.credentials import router as credentials_router
from app.api.browser_auth import router as browser_auth_router
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
from app.core.config import settings
from app.core.database import engine, async_session_factory
from app.llm.client import aclose_llm_client
from app.services.credential_verification import validate_all_sessions_on_startup

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Validate all stored connector sessions on startup
    try:
        async with async_session_factory() as db:
            results = await validate_all_sessions_on_startup(db)
            valid = sum(1 for v in results.values() if v)
            logger.info(f"Startup session validation: {valid}/{len(results)} connectors valid")
    except Exception as e:
        logger.warning(f"Startup session validation failed: {e}")

    yield
    await aclose_llm_client()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Commercial Real Estate Intelligence Platform",
    version="0.2.8.1",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(customers_router, prefix=settings.api_prefix)
app.include_router(credentials_router, prefix=settings.api_prefix)
app.include_router(browser_auth_router, prefix=settings.api_prefix)
app.include_router(onboarding_router, prefix=settings.api_prefix)
app.include_router(deals_router, prefix=settings.api_prefix)
app.include_router(properties_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(preferences_router, prefix=settings.api_prefix)
app.include_router(outreach_router, prefix=settings.api_prefix)
app.include_router(tracking_router, prefix=settings.api_prefix)
app.include_router(subscription_router, prefix=settings.api_prefix)
app.include_router(billing_router, prefix=settings.api_prefix)
app.include_router(connectors_router, prefix=settings.api_prefix)
app.include_router(memory_router, prefix=settings.api_prefix)
app.include_router(approvals_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)
app.include_router(feedback_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "SpaceFit AI API", "version": app.version}


@app.get("/health")
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
