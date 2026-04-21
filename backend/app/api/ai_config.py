"""BYOK (Bring Your Own Key) AI configuration API endpoints.

The original (v1) handlers live in this file for backwards compatibility
and rollback. When ``settings.byok_rebuild_enabled`` is True, the
mutating routes delegate to ``app.api.ai_config_v2`` which implements
additive rotation, soft-delete revoke, governance scope, submission
rate limiting, audit logging, and normalized error codes. Read-only
routes and provider metadata stay in v1 because they don't benefit
from the rebuild.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import ai_config_v2 as v2
from app.api.deps import CurrentUser, get_db
from app.core.config import settings
from app.core.security import encrypt_credential, generate_user_salt
from app.db.models.credential import UserAIConfig
from app.services.user_llm import PROVIDER_DEFAULT_MODELS

router = APIRouter(prefix="/ai-config", tags=["ai-config"])
logger = logging.getLogger(__name__)

# Supported providers with metadata
SUPPORTED_PROVIDERS = [
    {
        "id": "platform_default",
        "name": "Platform Default",
        "description": "Uses Perigee's built-in AI (Gemini Flash for free, Claude for paid)",
        "requires_key": False,
        "requires_base_url": False,
        "default_model": "",
        "models": [],
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "description": "Claude models via Anthropic API",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": "claude-haiku-4-5-20251001",
        "models": [
            "claude-sonnet-4-6-20260320",
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "description": "GPT models via OpenAI API",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    {
        "id": "google",
        "name": "Google Gemini",
        "description": "Gemini models via Google AI API",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "description": "DeepSeek models",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    {
        "id": "openai_compatible",
        "name": "Custom (OpenAI-Compatible)",
        "description": "Any provider with an OpenAI-compatible API",
        "requires_key": True,
        "requires_base_url": True,
        "default_model": "",
        "models": [],
    },
]


# --- Pydantic schemas ---

class AIConfigResponse(BaseModel):
    provider: str
    model: str | None
    base_url: str | None
    has_byok_key: bool
    is_key_valid: bool
    key_validated_at: datetime | None
    key_error_message: str | None
    effective_provider: str
    effective_model: str

    model_config = {"from_attributes": True}


class AIConfigUpdate(BaseModel):
    provider: str = Field(description="Provider ID (anthropic, openai, google, deepseek, openai_compatible, platform_default)")
    model: str | None = Field(default=None, description="Model override")
    api_key: str | None = Field(default=None, description="API key (only sent when updating)")
    base_url: str | None = Field(default=None, description="Custom endpoint URL")


class ValidateKeyRequest(BaseModel):
    provider: str
    api_key: str
    model: str | None = None
    base_url: str | None = None


class ValidateKeyResponse(BaseModel):
    valid: bool
    error: str | None = None
    model_tested: str | None = None


class ProviderInfo(BaseModel):
    id: str
    name: str
    description: str
    requires_key: bool
    requires_base_url: bool
    default_model: str
    models: list[str]


# --- Helper ---

def _effective_provider_model(config: UserAIConfig | None, user_tier: str) -> tuple[str, str]:
    """Compute effective provider/model for display."""
    if config and config.provider != "platform_default" and config.is_key_valid:
        model = config.model or PROVIDER_DEFAULT_MODELS.get(config.provider, "")
        return config.provider, model

    if user_tier in ("individual", "enterprise"):
        from app.core.config import settings
        return "anthropic", settings.llm_model or settings.anthropic_model

    return "google", "gemini-2.0-flash"


async def _get_active_ai_config(db: AsyncSession, user_id: str) -> UserAIConfig | None:
    """Return the most recently updated active AI config for a user.

    Some legacy environments can contain multiple rows in ``active`` state
    (e.g., from old data before partial unique indexes were enforced).
    Using ``scalars().first()`` with an explicit ordering prevents
    ``MultipleResultsFound`` 500s on settings reads.
    """
    result = await db.execute(
        select(UserAIConfig)
        .where(UserAIConfig.user_id == user_id)
        .where(UserAIConfig.status == "active")
        .order_by(UserAIConfig.updated_at.desc(), UserAIConfig.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


# --- Endpoints ---

@router.get("", response_model=AIConfigResponse)
async def get_ai_config(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIConfigResponse:
    """Get current AI model configuration."""
    if settings.byok_rebuild_enabled:
        v2_resp = await v2.get_ai_config_v2(current_user, db)
        # v2 response has a richer shape (id/status/scope/key_last_four/label);
        # project down to the v1 shape the client expects.
        return AIConfigResponse(
            provider=v2_resp.provider,
            model=v2_resp.model,
            base_url=v2_resp.base_url,
            has_byok_key=v2_resp.has_byok_key,
            is_key_valid=v2_resp.is_key_valid,
            key_validated_at=v2_resp.key_validated_at,
            key_error_message=v2_resp.key_error_message,
            effective_provider=v2_resp.effective_provider,
            effective_model=v2_resp.effective_model,
        )

    config = await _get_active_ai_config(db, current_user.id)

    eff_provider, eff_model = _effective_provider_model(config, current_user.tier)

    if config is None:
        return AIConfigResponse(
            provider="platform_default",
            model=None,
            base_url=None,
            has_byok_key=False,
            is_key_valid=False,
            key_validated_at=None,
            key_error_message=None,
            effective_provider=eff_provider,
            effective_model=eff_model,
        )

    return AIConfigResponse(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        has_byok_key=config.api_key_encrypted is not None,
        is_key_valid=config.is_key_valid,
        key_validated_at=config.key_validated_at,
        key_error_message=config.key_error_message,
        effective_provider=eff_provider,
        effective_model=eff_model,
    )


@router.put("", response_model=AIConfigResponse)
async def update_ai_config(
    payload: AIConfigUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> AIConfigResponse:
    """Update AI model configuration (provider, model, API key)."""
    if settings.byok_rebuild_enabled:
        v2_payload = v2.AIConfigUpdate(
            provider=payload.provider,
            model=payload.model,
            api_key=payload.api_key,
            base_url=payload.base_url,
        )
        v2_resp = await v2.update_ai_config_v2(v2_payload, current_user, db, request)
        return AIConfigResponse(
            provider=v2_resp.provider,
            model=v2_resp.model,
            base_url=v2_resp.base_url,
            has_byok_key=v2_resp.has_byok_key,
            is_key_valid=v2_resp.is_key_valid,
            key_validated_at=v2_resp.key_validated_at,
            key_error_message=v2_resp.key_error_message,
            effective_provider=v2_resp.effective_provider,
            effective_model=v2_resp.effective_model,
        )

    # Validate provider
    valid_ids = {p["id"] for p in SUPPORTED_PROVIDERS}
    if payload.provider not in valid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {payload.provider}",
        )

    config = await _get_active_ai_config(db, current_user.id)

    if config is None:
        config = UserAIConfig(user_id=current_user.id)
        db.add(config)

    config.provider = payload.provider
    config.model = payload.model
    config.base_url = payload.base_url

    # Encrypt and store API key if provided
    if payload.api_key:
        salt = generate_user_salt()
        config.api_key_encrypted = encrypt_credential(payload.api_key, salt)
        config.encryption_salt = salt
        # Reset validation — user should validate after setting key
        config.is_key_valid = False
        config.key_validated_at = None
        config.key_error_message = None

    # If switching to platform_default, clear the key
    if payload.provider == "platform_default":
        config.api_key_encrypted = None
        config.encryption_salt = None
        config.is_key_valid = False
        config.key_validated_at = None
        config.key_error_message = None

    await db.commit()
    await db.refresh(config)

    eff_provider, eff_model = _effective_provider_model(config, current_user.tier)

    return AIConfigResponse(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        has_byok_key=config.api_key_encrypted is not None,
        is_key_valid=config.is_key_valid,
        key_validated_at=config.key_validated_at,
        key_error_message=config.key_error_message,
        effective_provider=eff_provider,
        effective_model=eff_model,
    )


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_key(
    payload: ValidateKeyRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ValidateKeyResponse:
    """Validate a BYOK API key by making a lightweight test call."""
    from app.llm.client import get_or_create_client
    from app.llm.types import LLMChatMessage, LLMChatRequest

    provider = payload.provider
    model = payload.model or PROVIDER_DEFAULT_MODELS.get(provider, "")

    if not model:
        return ValidateKeyResponse(valid=False, error="Model is required for this provider")

    try:
        client = get_or_create_client(
            provider=provider,
            api_key=payload.api_key,
            base_url=payload.base_url or "",
        )

        # Lightweight test: generate a single token
        response = await client.chat(
            LLMChatRequest(
                model=model,
                max_tokens=5,
                system="Reply with only the word 'ok'.",
                messages=[LLMChatMessage(role="user", content="test")],
            )
        )

        # If we got here, the key works. Update the config in DB.
        config = await _get_active_ai_config(db, current_user.id)
        if config and config.api_key_encrypted:
            config.is_key_valid = True
            config.key_validated_at = datetime.now(timezone.utc)
            config.key_error_message = None
            await db.commit()

        return ValidateKeyResponse(valid=True, model_tested=model)

    except Exception as e:
        error_msg = str(e)
        # Truncate long error messages
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."

        # Update config with error
        config = await _get_active_ai_config(db, current_user.id)
        if config:
            config.is_key_valid = False
            config.key_error_message = error_msg
            await db.commit()

        return ValidateKeyResponse(valid=False, error=error_msg, model_tested=model)


@router.delete("/key", status_code=status.HTTP_200_OK)
async def remove_byok_key(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> AIConfigResponse:
    """Remove BYOK key and revert to platform default."""
    if settings.byok_rebuild_enabled:
        v2_resp = await v2.remove_byok_key_v2(current_user, db, request)
        return AIConfigResponse(
            provider=v2_resp.provider,
            model=v2_resp.model,
            base_url=v2_resp.base_url,
            has_byok_key=v2_resp.has_byok_key,
            is_key_valid=v2_resp.is_key_valid,
            key_validated_at=v2_resp.key_validated_at,
            key_error_message=v2_resp.key_error_message,
            effective_provider=v2_resp.effective_provider,
            effective_model=v2_resp.effective_model,
        )

    config = await _get_active_ai_config(db, current_user.id)

    if config is None:
        eff_provider, eff_model = _effective_provider_model(None, current_user.tier)
        return AIConfigResponse(
            provider="platform_default",
            model=None,
            base_url=None,
            has_byok_key=False,
            is_key_valid=False,
            key_validated_at=None,
            key_error_message=None,
            effective_provider=eff_provider,
            effective_model=eff_model,
        )

    config.provider = "platform_default"
    config.model = None
    config.api_key_encrypted = None
    config.encryption_salt = None
    config.base_url = None
    config.is_key_valid = False
    config.key_validated_at = None
    config.key_error_message = None
    await db.commit()

    eff_provider, eff_model = _effective_provider_model(None, current_user.tier)

    return AIConfigResponse(
        provider="platform_default",
        model=None,
        base_url=None,
        has_byok_key=False,
        is_key_valid=False,
        key_validated_at=None,
        key_error_message=None,
        effective_provider=eff_provider,
        effective_model=eff_model,
    )


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(
    current_user: CurrentUser,
) -> list[ProviderInfo]:
    """List supported AI providers with their capabilities."""
    return [ProviderInfo(**p) for p in SUPPORTED_PROVIDERS]


# --- Usage endpoint ---


class UsageResponse(BaseModel):
    last_24h_input_tokens: int
    last_24h_output_tokens: int
    last_24h_total_tokens: int
    last_24h_llm_calls: int
    last_24h_cost_estimate_usd: float
    using_byok: bool
    current_period_input_tokens: int
    current_period_output_tokens: int


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UsageResponse:
    """Get token usage stats for the current user."""
    from datetime import timedelta

    from sqlalchemy import and_, func

    from app.db.models.subscription import TokenUsage
    from app.db.models.tool_call import ToolCallLog

    now = datetime.now(timezone.utc)

    # Current monthly period
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(TokenUsage).where(
            and_(
                TokenUsage.user_id == current_user.id,
                TokenUsage.period_start == period_start,
            )
        )
    )
    usage = result.scalar_one_or_none()

    period_input = usage.input_tokens if usage else 0
    period_output = usage.output_tokens if usage else 0

    # Last 24h tool calls (from audit log)
    day_ago = now - timedelta(hours=24)
    result = await db.execute(
        select(func.count(ToolCallLog.id)).where(
            and_(
                ToolCallLog.user_id == current_user.id,
                ToolCallLog.created_at >= day_ago,
            )
        )
    )
    tool_calls_24h = result.scalar() or 0

    # BYOK status
    ai_config = await _get_active_ai_config(db, current_user.id)
    using_byok = bool(
        ai_config
        and ai_config.provider != "platform_default"
        and ai_config.is_key_valid
    )

    # Rough cost estimate (Haiku pricing: ~$0.25/MTok input, ~$1.25/MTok output)
    total = period_input + period_output
    cost_estimate = (period_input * 0.25 + period_output * 1.25) / 1_000_000

    return UsageResponse(
        last_24h_input_tokens=period_input,  # approximate via monthly
        last_24h_output_tokens=period_output,
        last_24h_total_tokens=total,
        last_24h_llm_calls=tool_calls_24h,
        last_24h_cost_estimate_usd=round(cost_estimate, 4),
        using_byok=using_byok,
        current_period_input_tokens=period_input,
        current_period_output_tokens=period_output,
    )


# --- Specialist model overrides ---


class SpecialistModelsUpdate(BaseModel):
    specialist_models: dict[str, str] = Field(
        description='Map of specialist name to model ID, e.g. {"scout": "claude-haiku-4-5-20251001"}'
    )


class SpecialistModelsResponse(BaseModel):
    specialist_models: dict[str, str]


@router.get("/specialist-models", response_model=SpecialistModelsResponse)
async def get_specialist_models(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SpecialistModelsResponse:
    """Get per-specialist model overrides."""
    import json as _json

    config = await _get_active_ai_config(db, current_user.id)

    models: dict[str, str] = {}
    if config and config.specialist_models_json:
        try:
            models = _json.loads(config.specialist_models_json)
        except (ValueError, TypeError):
            pass

    return SpecialistModelsResponse(specialist_models=models)


@router.put("/specialist-models", response_model=SpecialistModelsResponse)
async def update_specialist_models(
    payload: SpecialistModelsUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SpecialistModelsResponse:
    """Update per-specialist model overrides."""
    import json as _json

    from app.agents.specialists.registry import SPECIALIST_REGISTRY

    # Validate specialist names
    valid_names = set(SPECIALIST_REGISTRY.keys()) | {"orchestrator"}
    for name in payload.specialist_models:
        if name not in valid_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown specialist: {name}. Valid: {sorted(valid_names)}",
            )

    config = await _get_active_ai_config(db, current_user.id)

    if config is None:
        config = UserAIConfig(user_id=current_user.id)
        db.add(config)

    config.specialist_models_json = _json.dumps(payload.specialist_models)
    await db.commit()

    return SpecialistModelsResponse(specialist_models=payload.specialist_models)


# ---- v2-only routes --------------------------------------------------------
#
# These exist only when the rebuild flag is on. We register them on the
# same router with a flag guard so the feature flag really is a single
# switch: flipping byok_rebuild_enabled=false makes the rebuild invisible
# (the routes exist but 404 to any client).


def _require_rebuild_enabled() -> None:
    if not settings.byok_rebuild_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.put("/scope", response_model=v2.AIConfigResponse)
async def update_scope(
    payload: v2.ScopeUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> v2.AIConfigResponse:
    """Update governance scope (allowed models, spend/request caps) on the
    user's active BYOK credential. v2-only."""
    _require_rebuild_enabled()
    return await v2.update_scope_v2(payload, current_user, db, request)


@router.get("/audit", response_model=list[v2.AuditLogEntry])
async def get_audit_log(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[v2.AuditLogEntry]:
    """Return the user's credential audit log (most recent first).
    v2-only."""
    _require_rebuild_enabled()
    return await v2.get_audit_log_v2(current_user, db, limit=limit)
