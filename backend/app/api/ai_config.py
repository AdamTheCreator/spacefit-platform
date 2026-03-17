"""BYOK (Bring Your Own Key) AI configuration API endpoints."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.core.security import encrypt_credential, decrypt_credential, generate_user_salt
from app.db.models.credential import UserAIConfig
from app.services.user_llm import PROVIDER_DEFAULT_MODELS

router = APIRouter(prefix="/ai-config", tags=["ai-config"])
logger = logging.getLogger(__name__)

# Supported providers with metadata
SUPPORTED_PROVIDERS = [
    {
        "id": "platform_default",
        "name": "Platform Default",
        "description": "Uses SpaceFit's built-in AI (Gemini Flash for free, Claude for paid)",
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
        "default_model": "claude-3-haiku-20240307",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
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


# --- Endpoints ---

@router.get("", response_model=AIConfigResponse)
async def get_ai_config(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIConfigResponse:
    """Get current AI model configuration."""
    result = await db.execute(
        select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

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
) -> AIConfigResponse:
    """Update AI model configuration (provider, model, API key)."""
    # Validate provider
    valid_ids = {p["id"] for p in SUPPORTED_PROVIDERS}
    if payload.provider not in valid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {payload.provider}",
        )

    result = await db.execute(
        select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

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
        result = await db.execute(
            select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
        )
        config = result.scalar_one_or_none()
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
        result = await db.execute(
            select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
        )
        config = result.scalar_one_or_none()
        if config:
            config.is_key_valid = False
            config.key_error_message = error_msg
            await db.commit()

        return ValidateKeyResponse(valid=False, error=error_msg, model_tested=model)


@router.delete("/key", status_code=status.HTTP_200_OK)
async def remove_byok_key(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIConfigResponse:
    """Remove BYOK key and revert to platform default."""
    result = await db.execute(
        select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

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
