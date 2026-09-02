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

from app.byok import crypto as byok_crypto
from app.core.config import settings
from app.core.security import decrypt_credential
from app.db.models.credential import UserAIConfig
from app.llm.client import LLMClient, get_llm_client, get_or_create_client

logger = logging.getLogger(__name__)

# Default models per provider (used when user doesn't specify a model)
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": settings.anthropic_model or "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "huggingface": settings.huggingface_model or "Qwen/Qwen2.5-7B-Instruct",
    "baseten": settings.baseten_model or "Qwen/Qwen2.5-7B-Instruct",
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
    "anthropic": settings.anthropic_model or "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash-lite",
    "deepseek": "deepseek-chat",
    "huggingface": settings.huggingface_model or "Qwen/Qwen2.5-7B-Instruct",
    # Baseten: validate against base Qwen — it is always loaded on the L4
    # alongside the advisor LoRA adapters, so it is the safest probe.
    "baseten": "Qwen/Qwen2.5-7B-Instruct",
}

# Previously-shipped model ids that can return provider-side 404s on some keys,
# plus fully retired Anthropic ids (Claude 3.x line) that 404 on every key —
# earlier builds offered these in the BYOK picker, so existing user configs
# may still carry them.
_ANTHROPIC_DEPRECATED_MODEL_ALIASES: dict[str, str] = {
    "claude-haiku-4-5-20251001": settings.anthropic_model or "claude-haiku-4-5",
    "claude-sonnet-4-6-20260320": "claude-sonnet-4-5",
    "claude-sonnet-4-20250514": "claude-sonnet-4-5",
    "claude-3-5-haiku-latest": "claude-haiku-4-5",
    "claude-3-5-haiku-20241022": "claude-haiku-4-5",
    "claude-3-5-sonnet-latest": "claude-sonnet-4-5",
    "claude-3-5-sonnet-20241022": "claude-sonnet-4-5",
    "claude-3-5-sonnet-20240620": "claude-sonnet-4-5",
    "claude-3-opus-latest": "claude-opus-4-8",
    "claude-3-opus-20240229": "claude-opus-4-8",
}

# Tier values that should route to paid-tier platform LLMs when the user
# has no BYOK key. ``individual`` is the legacy single paid tier kept for
# any subscriptions that lingered through migration 031; ``starter``,
# ``pro``, ``max``, and ``enterprise`` are the Foundry-style tiers from
# migration 031 onwards. Anything not in this set (i.e. ``free``) falls
# through to the cheap Gemini Flash path.
PAID_TIERS: frozenset[str] = frozenset(
    {"starter", "pro", "max", "enterprise", "individual"}
)


def is_paid_tier(tier: str) -> bool:
    """Whether the given tier value should be treated as a paid plan."""
    return tier in PAID_TIERS


def normalize_provider_model(provider: str, model: str | None) -> str | None:
    """Map deprecated provider model ids to stable aliases."""
    if model is None:
        return None
    if provider == "anthropic":
        return _ANTHROPIC_DEPRECATED_MODEL_ALIASES.get(model, model)
    return model


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
    candidate = user_model or PROVIDER_DEFAULT_MODELS.get(provider, "")
    return normalize_provider_model(provider, candidate) or ""


@dataclass(frozen=True)
class ResolvedLLM:
    """The resolved LLM client + model for a given user request."""

    client: LLMClient
    model: str
    provider: str
    is_byok: bool
    specialist_models: dict[str, str] | None = None


def resolved_or_platform_model(resolved_llm: "ResolvedLLM | None") -> str:
    """Pick a model id that matches the client that will receive the request.

    Priority:
      1. ``resolved_llm.model`` when a ResolvedLLM is supplied (covers both BYOK
         and non-BYOK platform-default resolutions the caller has already done).
      2. Provider-appropriate platform default keyed off ``settings.llm_provider``:
         ``settings.baseten_model`` for baseten, ``settings.google_gemini_model``
         for google, ``settings.anthropic_model`` otherwise.

    Kept centralized so utility LLM call sites (fact_extractor, listing_match,
    outreach_ai, void_analysis) never send a hardcoded Anthropic model id to a
    Baseten-served client.
    """
    if resolved_llm is not None and resolved_llm.model:
        return resolved_llm.model

    provider = (settings.llm_provider or "").lower()
    if provider == "baseten":
        return settings.baseten_model
    if provider == "google":
        return settings.google_gemini_model
    return settings.anthropic_model


def platform_llm_summary() -> dict[str, str]:
    """Secret-free description of the platform (non-BYOK) LLM target.

    Used by the boot log and ``GET /ai-config/diagnose`` so operators can
    see at a glance that, e.g., ``LLM_PROVIDER=openai_compatible`` is
    pointing at a self-hosted host that has since gone away — the Render
    dashboard can override ``render.yaml`` and nothing else surfaces that.
    """
    from urllib.parse import urlparse

    provider = (settings.llm_provider or "anthropic").lower().strip()
    if provider == "baseten":
        model = settings.llm_model or settings.baseten_model
        base_url = settings.baseten_base_url
    elif provider == "google":
        model = settings.llm_model or settings.google_gemini_model
        base_url = settings.google_gemini_base_url
    elif provider == "huggingface":
        model = settings.llm_model or settings.huggingface_model
        base_url = settings.huggingface_base_url
    elif provider == "anthropic":
        model = settings.llm_model or settings.anthropic_model
        base_url = "https://api.anthropic.com"
    else:  # openai / deepseek / openai_compatible
        model = settings.llm_model
        base_url = settings.openai_base_url
    host = urlparse(base_url or "").netloc or (base_url or "")
    return {"provider": provider, "model": model or "", "endpoint_host": host}


def _resolve_platform_default(tier: str) -> ResolvedLLM:
    """Resolve platform-owned LLM based on subscription tier."""
    # Operator opt-in: when ``LLM_PROVIDER=baseten`` is set globally, route
    # every non-BYOK user (paid and free) through the self-hosted Baseten
    # L4. This bypasses the tier split because we own the inference and
    # want a single fine-tuned advisor model everywhere.
    if (settings.llm_provider or "").lower() == "baseten":
        return ResolvedLLM(
            client=get_or_create_client(
                provider="baseten",
                api_key=settings.baseten_api_key,
                base_url=settings.baseten_base_url,
            ),
            model=settings.llm_model or settings.baseten_model,
            provider="baseten",
            is_byok=False,
        )

    if is_paid_tier(tier):
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


def decrypt_ai_config_key(ai_config: UserAIConfig) -> str:
    """Return the plaintext API key for a ``UserAIConfig`` row.

    Two on-disk formats coexist:

    * **Envelope rows** (written by ``ai_config_v2`` when
      ``BYOK_REBUILD_ENABLED`` is on, migration 029+): ``api_key_encrypted``
      holds AES-GCM ciphertext and ``ciphertext_iv`` / ``ciphertext_tag`` /
      ``encrypted_dek`` / ``kek_id`` are populated.
    * **Legacy rows** (v1 ``PUT /ai-config``): ``api_key_encrypted`` is a
      Fernet token keyed off ``encryption_salt``.

    Before this helper existed the chat resolver only knew the legacy
    Fernet path, so an envelope row raised ``InvalidToken`` and the user
    was silently downgraded to the platform key — while Settings kept
    reporting their BYOK key as valid. Mirrors ``BYOKGateway.decrypt``.
    """
    if not ai_config.api_key_encrypted:
        raise ValueError("no encrypted key on row")
    if ai_config.encrypted_dek and ai_config.kek_id:
        return byok_crypto.decrypt_api_key(
            byok_crypto.EnvelopeBundle(
                ciphertext=ai_config.api_key_encrypted,
                iv=ai_config.ciphertext_iv or b"",
                auth_tag=ai_config.ciphertext_tag or b"",
                encrypted_dek=ai_config.encrypted_dek,
                kek_id=ai_config.kek_id,
            )
        )
    return decrypt_credential(
        ai_config.api_key_encrypted,
        ai_config.encryption_salt,
    )


async def get_active_ai_config(
    db: AsyncSession, user_id: str
) -> UserAIConfig | None:
    """Fetch the user's live BYOK row (most recently updated ``active`` row).

    After migration 028 the table can hold multiple rows per user (revoked
    history + active + rotating). Legacy environments occasionally carry
    more than one ``active`` row too, so we order + take the first instead
    of ``scalar_one_or_none`` — the latter raised ``MultipleResultsFound``
    at WebSocket connect, which the chat handler swallowed into a silent
    platform-key fallback.
    """
    result = await db.execute(
        select(UserAIConfig)
        .where(UserAIConfig.user_id == user_id)
        .where(UserAIConfig.status == "active")
        .order_by(UserAIConfig.updated_at.desc())
    )
    return result.scalars().first()


def byok_skip_reason(ai_config: UserAIConfig | None) -> str | None:
    """Explain why a BYOK row is *not* eligible for chat, or ``None`` if it is.

    Shared by ``resolve_user_llm`` and the ``/ai-config/diagnose`` endpoint
    so the diagnostic reports the exact gate the resolver applies.
    """
    if ai_config is None:
        return "no active ai_config row"
    if ai_config.provider == "platform_default":
        return "provider is platform_default"
    if not ai_config.api_key_encrypted:
        return "no API key stored on the row"
    if not ai_config.is_key_valid:
        return "key not validated (is_key_valid=false)" + (
            f": {ai_config.key_error_message}" if ai_config.key_error_message else ""
        )
    return None


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
    ai_config = await get_active_ai_config(db, user_id)

    skip_reason = byok_skip_reason(ai_config)
    if ai_config is not None and skip_reason is None:
        try:
            api_key = decrypt_ai_config_key(ai_config)
            model = normalize_provider_model(ai_config.provider, ai_config.model)
            if not model:
                model = PROVIDER_DEFAULT_MODELS.get(ai_config.provider, "")
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
            logger.info(
                "[llm-resolve] user=%s → BYOK provider=%s model=%s key=…%s",
                user_id,
                ai_config.provider,
                model,
                ai_config.key_last_four or "????",
            )
            return ResolvedLLM(
                client=client,
                model=model,
                provider=ai_config.provider,
                is_byok=True,
                specialist_models=specialist_models,
            )
        except Exception as e:
            # Log the class only — never the exception text, which for a
            # crypto error can echo ciphertext and for a client-build
            # error could mention the key.
            logger.warning(
                "[llm-resolve] user=%s BYOK row unusable (%s), falling back "
                "to platform default — Settings will still show the key as "
                "valid; run GET /ai-config/diagnose",
                user_id,
                e.__class__.__name__,
            )
    elif ai_config is not None:
        logger.info(
            "[llm-resolve] user=%s BYOK row skipped: %s", user_id, skip_reason
        )

    # No BYOK — use platform default based on tier
    resolved = _resolve_platform_default(user_tier)
    logger.info(
        "[llm-resolve] user=%s → platform provider=%s model=%s tier=%s",
        user_id,
        resolved.provider,
        resolved.model,
        user_tier,
    )
    return resolved
