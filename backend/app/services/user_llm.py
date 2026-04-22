"""User-aware LLM resolution service.

Routes chat requests to the correct LLM provider based on:
  1. BYOK config (user's own key) — highest priority
  2. Subscription tier (paid → Claude Haiku, free → Gemini Flash)
  3. Platform default fallback

Vision (document parsing) always uses the platform Anthropic key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_credential
from app.db.models.credential import UserAIConfig
from app.llm.client import LLMClient, get_llm_client, get_or_create_client

logger = logging.getLogger(__name__)

# Default models per provider (used when user doesn't specify a model)
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "openai_compatible": "",
}

# Models used to probe a freshly-entered API key. Validation only needs to
# confirm the key is alive, so we pick the cheapest / highest-RPM model
# each provider offers — the user's preferred model may be on a tier
# they haven't unlocked yet (e.g., gpt-4o on a new OpenAI key is rate
# limited well below 3 RPM, so validating against it fails even when
# the key itself is perfectly valid).
#
# Providers intentionally omitted:
#   - openai_compatible: custom endpoint, only the user knows which
#     models it accepts — fall through to whatever the user supplied.
#   - platform_default: nothing to validate; this entry never reaches
#     the validator.
VALIDATION_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash-lite",
    "deepseek": "deepseek-chat",
}


def select_validation_model(provider: str, user_model: str | None) -> str:
    """Return the model to use when validating an API key.

    Prefers the dedicated validation model when available; falls back to
    the user's requested model (e.g. for ``openai_compatible`` where we
    can't assume model names), and finally to the provider's default.
    Returns an empty string if nothing is configured — callers must
    check and reject validation in that case.
    """
    if provider in VALIDATION_MODELS:
        return VALIDATION_MODELS[provider]
    return user_model or PROVIDER_DEFAULT_MODELS.get(provider, "")


@dataclass(frozen=True)
class ResolvedLLM:
    """The resolved LLM client + model for a given user request."""

    client: LLMClient
    model: str
    provider: str
    is_byok: bool
    specialist_models: dict[str, str] | None = None  # e.g. {"scout": "claude-haiku-4-5-..."}


def _resolve_platform_default(tier: str) -> ResolvedLLM:
    """Resolve platform-owned LLM based on subscription tier."""
    if tier in ("individual", "enterprise"):
        # Paid tiers → Claude Haiku on platform key
        return ResolvedLLM(
            client=get_llm_client(),
            model=settings.llm_model or settings.anthropic_model,
            provider=settings.llm_provider,
            is_byok=False,
        )

    # Free tier → Gemini Flash via OpenAI-compatible endpoint (cheap)
    if settings.google_gemini_api_key:
        client = get_or_create_client(
            provider="google",
            api_key=settings.google_gemini_api_key,
            base_url=settings.google_gemini_base_url,
        )
        return ResolvedLLM(
            client=client,
            model=settings.google_gemini_model,
            provider="google",
            is_byok=False,
        )

    # Fallback if no Gemini key configured — use platform Anthropic
    return ResolvedLLM(
        client=get_llm_client(),
        model=settings.llm_model or settings.anthropic_model,
        provider=settings.llm_provider,
        is_byok=False,
    )


async def resolve_user_llm(
    db: AsyncSession,
    user_id: str,
    user_tier: str = "free",
) -> ResolvedLLM:
    """Resolve which LLM client + model to use for a user's chat request.

    Resolution priority:
      1. BYOK config with a valid key → user's chosen provider
      2. Paid tier without BYOK → Claude Haiku (platform key)
      3. Free tier without BYOK → Gemini Flash (platform key)
    """
    # Check for BYOK config. Filter to the single live row — after migration
    # 028 this table can hold multiple rows per user (revoked history +
    # active + rotating), so a naked user_id match would raise on rotation.
    result = await db.execute(
        select(UserAIConfig)
        .where(UserAIConfig.user_id == user_id)
        .where(UserAIConfig.status == "active")
    )
    ai_config = result.scalar_one_or_none()

    if ai_config and ai_config.provider != "platform_default" and ai_config.is_key_valid:
        try:
            api_key = decrypt_credential(
                ai_config.api_key_encrypted,
                ai_config.encryption_salt,
            )
            model = ai_config.model or PROVIDER_DEFAULT_MODELS.get(ai_config.provider, "")
            client = get_or_create_client(
                provider=ai_config.provider,
                api_key=api_key,
                base_url=ai_config.base_url or "",
            )
            # Parse per-specialist model overrides if set
            specialist_models: dict[str, str] | None = None
            if ai_config.specialist_models_json:
                import json
                try:
                    specialist_models = json.loads(ai_config.specialist_models_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            return ResolvedLLM(
                client=client,
                model=model,
                provider=ai_config.provider,
                is_byok=True,
                specialist_models=specialist_models,
            )
        except Exception:
            logger.warning(
                "Failed to decrypt BYOK key for user %s, falling back to platform default",
                user_id,
            )

    # No BYOK — use platform default based on tier
    return _resolve_platform_default(user_tier)
