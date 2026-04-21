"""
Perigee Guardrail System

Five layers of defense against abuse while preserving full CRE utility:
1. Message size validation
2. Per-user rate limiting (in-memory sliding window)
3. Topic classification (regex tiers + Haiku fallback)
4. Subscription limit enforcement
5. Token budget tracking
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.user_llm import ResolvedLLM

logger = logging.getLogger(__name__)

CRE_REJECTION_MESSAGE = (
    "I'm specialized for commercial real estate analysis. I can help with "
    "property analysis, void studies, demographics, tenant research, and market "
    "insights. What CRE question can I help with?"
)


# ---------------------------------------------------------------------------
# 5a) Message size validator
# ---------------------------------------------------------------------------

def validate_message_size(
    content: str,
    max_chars: int | None = None,
) -> tuple[bool, str | None]:
    """Return (ok, error_message). Instant check, no DB."""
    limit = max_chars if max_chars is not None else settings.guardrail_max_message_chars
    if len(content) > limit:
        return False, f"Message too long ({len(content):,} chars). Please keep messages under {limit:,} characters."
    return True, None


# ---------------------------------------------------------------------------
# 5b) Rate limiter — in-memory sliding window per user
# ---------------------------------------------------------------------------

class MessageRateLimiter:
    """Sliding-window rate limiter. Resets on process restart (acceptable for single-process)."""

    def __init__(
        self,
        max_messages: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self._max = max_messages or settings.guardrail_rate_limit_messages
        self._window = window_seconds or settings.guardrail_rate_limit_window_seconds
        self._timestamps: dict[str, list[float]] = {}

    def check(self, user_id: str) -> tuple[bool, str | None]:
        now = time.monotonic()
        window_start = now - self._window

        timestamps = self._timestamps.get(user_id, [])
        # Prune old entries
        timestamps = [t for t in timestamps if t > window_start]
        timestamps.append(now)
        self._timestamps[user_id] = timestamps

        if len(timestamps) > self._max:
            return False, f"Rate limit exceeded. Please wait a moment before sending more messages (limit: {self._max} per {self._window}s)."
        return True, None


# Singleton instance
rate_limiter = MessageRateLimiter()


# ---------------------------------------------------------------------------
# 5c) Topic classifier — three-tier
# ---------------------------------------------------------------------------

# Tier 1: instant BLOCK patterns (obvious off-topic)
_BLOCK_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        # Code / programming
        r"\b(write|generate|create|build|code|implement|debug)\b.{0,30}\b(python|javascript|java|html|css|react|sql|api|function|class|script|program|code|app)\b",
        r"\b(def |class |import |from .+ import|function\s*\(|const |let |var )\b",
        r"```",
        # Homework / academic
        r"\b(homework|essay|assignment|thesis|exam|quiz|test question|solve this equation)\b",
        r"\b(calculate|compute|derive)\b.{0,20}\b(integral|derivative|equation|formula|theorem)\b",
        # Creative writing
        r"\b(write|compose|create)\b.{0,20}\b(poem|song|story|novel|joke|limerick|haiku|screenplay)\b",
        # Recipes / cooking
        r"\b(recipe|cook|bake|ingredient)\b.{0,30}\b(cake|soup|pasta|chicken|bread|dinner|meal)\b",
        # Medical / legal advice
        r"\b(diagnose|symptoms|medication|dosage|prescription|treatment plan)\b",
        r"\b(legal advice|sue|lawsuit|attorney|court filing|legal strategy)\b",
        # General assistant / roleplay
        r"\b(pretend|roleplay|act as|you are now|ignore previous|ignore your instructions)\b",
        r"\b(translate|translation)\b.{0,20}\b(from|to|into)\b.{0,20}\b(english|spanish|french|chinese|japanese|german)\b",
    ]
]

# Tier 2: instant ALLOW patterns (CRE terminology)
_ALLOW_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(mall|shopping center|retail|strip mall|outlet|plaza|center)\b",
        r"\b(tenant|lease|vacancy|occupancy|anchor|inline|endcap|pad site)\b",
        r"\b(cap rate|noi|nnn|gross lease|net lease|cam charges)\b",
        r"\b(demographics|trade area|population|median income|household)\b",
        r"\b(void analysis|gap analysis|tenant mix|co-tenancy)\b",
        r"\b(foot traffic|visitor traffic|vehicle traffic|vpd|aadt)\b",
        r"\b(property|commercial|real estate|cre|brokerage|leasing)\b",
        r"\b(square feet|square footage|\bsf\b|sqft)\b",
        r"\b(zoning|entitlement|site plan|parking ratio)\b",
        r"\b(rent per|psf|price per|asking rent|market rent)\b",
        r"\b(placer|costar|siteusa|loopnet|crexi)\b",
        r"\b(gla|nra|far|far\b|floor area ratio)\b",
        r"\b(drive[- ]?time|radius|isochrone|catchment)\b",
        r"\b(outreach|prospect|broker|landlord|deal|pipeline)\b",
    ]
]


def _classify_instant(content: str) -> str:
    """Return 'ALLOW', 'BLOCK', or 'AMBIGUOUS' using regex tiers."""
    # Tier 2 first — if CRE terms present, always allow
    for pattern in _ALLOW_PATTERNS:
        if pattern.search(content):
            return "ALLOW"

    # Tier 1 — obvious off-topic
    for pattern in _BLOCK_PATTERNS:
        if pattern.search(content):
            return "BLOCK"

    return "AMBIGUOUS"


async def _classify_with_haiku(
    content: str,
    resolved_llm: "ResolvedLLM | None" = None,
) -> str:
    """Use a cheap Haiku call to classify ambiguous messages. Returns 'CRE' or 'OFF_TOPIC'.

    If `resolved_llm` is provided and represents a BYOK config, routes the classifier
    call through the user's own key so that BYOK users incur zero platform-side tokens.
    """
    try:
        from app.llm import get_llm_client, LLMChatRequest, LLMChatMessage

        if resolved_llm is not None and resolved_llm.is_byok:
            llm = resolved_llm.client
        else:
            llm = get_llm_client()
        response = await llm.chat(
            LLMChatRequest(
                system="Classify if this message is related to commercial real estate (CRE). Reply with exactly one word: CRE or OFF_TOPIC",
                messages=[LLMChatMessage(role="user", content=content[:500])],
                model=settings.guardrail_classifier_model,
                max_tokens=10,
            )
        )
        result = response.content.strip().upper()
        if "CRE" in result:
            return "CRE"
        return "OFF_TOPIC"
    except Exception:
        logger.exception("Guardrail classifier failed, allowing message through")
        return "CRE"  # Fail open


async def classify_message(
    content: str,
    resolved_llm: "ResolvedLLM | None" = None,
) -> tuple[bool, str | None]:
    """
    Three-tier topic classification.
    Returns (allowed, error_message).

    `resolved_llm` is forwarded to the tier-3 Haiku classifier so BYOK users
    do not consume platform tokens for topic classification.
    """
    verdict = _classify_instant(content)

    if verdict == "ALLOW":
        return True, None
    if verdict == "BLOCK":
        logger.info("Guardrail: blocked off-topic message (regex)")
        return False, CRE_REJECTION_MESSAGE

    # Ambiguous → Haiku fallback
    haiku_result = await _classify_with_haiku(content, resolved_llm=resolved_llm)
    if haiku_result == "CRE":
        return True, None

    logger.info("Guardrail: blocked off-topic message (classifier)")
    return False, CRE_REJECTION_MESSAGE


# ---------------------------------------------------------------------------
# 5d) Subscription limit check
# ---------------------------------------------------------------------------

async def check_subscription_limit(
    user_id: str,
) -> tuple[bool, str | None]:
    """Check if user can start/continue a chat session."""
    from app.core.database import async_session_factory
    from app.db.models.subscription import Subscription, UsageType
    from app.services.subscription import SubscriptionService

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.plan))
                .where(Subscription.user_id == user_id)
            )
            subscription = result.scalar_one_or_none()
            if not subscription:
                # No subscription = treat as free tier; allow for now (handled by budget)
                return True, None

            can_use, msg = await SubscriptionService.check_can_use(
                db, subscription, UsageType.CHAT_SESSION
            )
            return can_use, msg if not can_use else None
    except Exception:
        logger.exception("Subscription check failed, allowing through")
        return True, None  # Fail open


async def increment_session_usage(user_id: str) -> None:
    """Increment the chat session usage counter for this billing period."""
    from app.core.database import async_session_factory
    from app.db.models.subscription import Subscription, UsageType
    from app.services.subscription import SubscriptionService

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.plan))
                .where(Subscription.user_id == user_id)
            )
            subscription = result.scalar_one_or_none()
            if subscription:
                await SubscriptionService.increment_usage(
                    db, subscription, UsageType.CHAT_SESSION
                )
    except Exception:
        logger.exception("Failed to increment session usage")


# ---------------------------------------------------------------------------
# 5e) Token budget check
# ---------------------------------------------------------------------------

def _current_period_start() -> datetime:
    """Return the first day of the current month at midnight UTC."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def check_token_budget(
    user_id: str,
    is_byok: bool = False,
) -> tuple[bool, str | None]:
    """Check if user has exhausted their monthly token budget.

    When `is_byok=True` the user is paying for their own API usage on their own
    provider key, so the platform's subscription-level token budget does not apply.
    """
    if is_byok:
        return True, None

    from app.core.database import async_session_factory
    from app.db.models.subscription import Subscription, TokenUsage

    try:
        async with async_session_factory() as db:
            # Get subscription + plan
            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.plan))
                .where(Subscription.user_id == user_id)
            )
            subscription = result.scalar_one_or_none()

            if subscription and subscription.plan:
                budget = subscription.plan.monthly_token_budget
            else:
                budget = settings.guardrail_free_monthly_token_budget

            # -1 = unlimited
            if budget == -1:
                return True, None

            # Sum tokens for current period
            period_start = _current_period_start()
            result = await db.execute(
                select(TokenUsage).where(
                    and_(
                        TokenUsage.user_id == user_id,
                        TokenUsage.period_start == period_start,
                    )
                )
            )
            usage = result.scalar_one_or_none()
            if not usage:
                return True, None

            total = usage.input_tokens + usage.output_tokens
            if total >= budget:
                return False, "You've reached your monthly token budget. Please upgrade your plan or wait until next month."

            return True, None
    except Exception:
        logger.exception("Token budget check failed, allowing through")
        return True, None  # Fail open


# ---------------------------------------------------------------------------
# 5f) Token recording
# ---------------------------------------------------------------------------

async def record_token_usage(
    user_id: str,
    input_tokens: int,
    output_tokens: int,
    is_byok: bool = False,
) -> None:
    """Upsert token counts into the TokenUsage table for the current month.

    When `is_byok=True`, the user is using their own provider API key, so we do
    NOT attribute these tokens to the platform's per-user quota. The user can
    track real usage in their own provider dashboard (Anthropic console,
    OpenAI platform, etc.). This keeps BYOK users free of platform-side token
    accounting and prevents double-counting against their subscription limits.
    """
    if is_byok:
        return
    if input_tokens == 0 and output_tokens == 0:
        return

    from app.core.database import async_session_factory
    from app.db.models.subscription import TokenUsage

    try:
        async with async_session_factory() as db:
            period_start = _current_period_start()
            result = await db.execute(
                select(TokenUsage).where(
                    and_(
                        TokenUsage.user_id == user_id,
                        TokenUsage.period_start == period_start,
                    )
                )
            )
            usage = result.scalar_one_or_none()

            if usage:
                usage.input_tokens += input_tokens
                usage.output_tokens += output_tokens
                usage.llm_calls += 1
            else:
                import uuid
                usage = TokenUsage(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    period_start=period_start,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    llm_calls=1,
                )
                db.add(usage)

            await db.commit()
    except Exception:
        logger.exception("Failed to record token usage")
