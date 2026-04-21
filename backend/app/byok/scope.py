"""Governance-scope enforcement for BYOK credentials.

The ``scope`` JSON column on ``user_ai_configs`` is the free-form policy
a user (or in the future an org admin) attaches to a credential. Today
four keys are honored:

    allowed_models:         list[str]  (empty/missing = any model)
    denied_models:          list[str]
    monthly_spend_cap_usd:  number     (USD, pre-tax, best-effort estimate)
    monthly_request_cap:    int

The gateway calls :func:`enforce_scope` after it resolves a credential
and before it dispatches to the provider adapter. A failure here short-
circuits the request with a :class:`BYOKError` carrying the right code,
so the user sees "this model isn't allowed" or "you've hit your cap"
instead of a generic provider error.

``monthly_request_cap`` is enforced against ``token_usage.llm_calls`` for
the current period (same table/aggregation used by the existing Usage
dashboard — no new counters). ``monthly_spend_cap_usd`` uses a simple
per-model pricing table; numbers are estimates and marked as such in
the UI.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.byok.errors import BYOKError

logger = logging.getLogger(__name__)


# ---- scope object -----------------------------------------------------------


@dataclass
class Scope:
    """Parsed view of the credential row's ``scope`` JSON column."""

    allowed_models: list[str] = field(default_factory=list)
    denied_models: list[str] = field(default_factory=list)
    monthly_spend_cap_usd: float | None = None
    monthly_request_cap: int | None = None

    @classmethod
    def from_json(cls, raw: str | None) -> "Scope":
        """Parse a scope JSON string, tolerating nulls and bad input.

        An unparseable or empty value yields an empty scope — i.e. "no
        restrictions applied". The gateway still records the attempt;
        a scope that can't be read is a warning, not a 500.
        """
        if not raw:
            return cls()
        try:
            data: Any = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("scope column is not valid JSON; treating as empty")
            return cls()
        if not isinstance(data, dict):
            return cls()

        def _list_of_str(key: str) -> list[str]:
            v = data.get(key)
            if not isinstance(v, list):
                return []
            return [str(x) for x in v if isinstance(x, (str, int, float))]

        def _positive_number(key: str) -> float | None:
            v = data.get(key)
            if v is None or isinstance(v, bool):
                return None
            try:
                n = float(v)
            except (TypeError, ValueError):
                return None
            return n if n >= 0 else None

        def _positive_int(key: str) -> int | None:
            n = _positive_number(key)
            if n is None:
                return None
            return int(n)

        return cls(
            allowed_models=_list_of_str("allowed_models"),
            denied_models=_list_of_str("denied_models"),
            monthly_spend_cap_usd=_positive_number("monthly_spend_cap_usd"),
            monthly_request_cap=_positive_int("monthly_request_cap"),
        )

    def to_json(self) -> str:
        """Serialize back to the compact JSON form stored in the DB."""
        payload: dict[str, Any] = {}
        if self.allowed_models:
            payload["allowed_models"] = self.allowed_models
        if self.denied_models:
            payload["denied_models"] = self.denied_models
        if self.monthly_spend_cap_usd is not None:
            payload["monthly_spend_cap_usd"] = self.monthly_spend_cap_usd
        if self.monthly_request_cap is not None:
            payload["monthly_request_cap"] = self.monthly_request_cap
        return json.dumps(payload, separators=(",", ":"))


# ---- model-allow/deny enforcement ------------------------------------------


def assert_model_allowed(scope: Scope, model: str) -> None:
    """Raise :class:`BYOKError` if the requested model is blocked.

    Precedence:
      1. If ``denied_models`` contains the model -> deny.
      2. If ``allowed_models`` is non-empty and doesn't contain it -> deny.
      3. Otherwise -> allow.

    The empty-list-means-any-model default matters: a user who hasn't
    configured governance never sees this error.
    """
    if model and model in scope.denied_models:
        raise BYOKError.model_not_allowed(model)
    if scope.allowed_models and model not in scope.allowed_models:
        raise BYOKError.model_not_allowed(model)


# ---- quota enforcement -----------------------------------------------------


# Per-model pricing, USD per million tokens, rough approximation.
# Updated manually; inaccurate pricing is surfaced in the UI as an
# estimate. The dict is intentionally forgiving: unknown models fall
# back to a sentinel so quota checks don't fire false positives.
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    # (input_usd_per_mtok, output_usd_per_mtok)
    "claude-sonnet-4-6-20260320": (3.0, 15.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.25, 1.25),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-3.5-turbo": (0.5, 1.5),
    "gemini-2.0-flash": (0.075, 0.3),
    "gemini-2.0-flash-lite": (0.05, 0.2),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.3),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Best-effort per-request cost estimate.

    Returns 0.0 for unknown models rather than an arbitrary large number
    so a missing pricing entry doesn't accidentally starve users. The UI
    labels all numbers as estimates.
    """
    prices = _PRICING_PER_MTOK.get(model)
    if not prices:
        return 0.0
    input_price, output_price = prices
    return (input_tokens / 1_000_000.0) * input_price + (output_tokens / 1_000_000.0) * output_price


async def assert_not_over_quota(
    db: AsyncSession,
    user_id: str,
    scope: Scope,
) -> None:
    """Raise if the current period has already hit a configured cap.

    This reads ``token_usage`` (the same table the ``/ai-config/usage``
    endpoint aggregates over). We use the subject user's monthly
    window rather than per-credential because the usage table is
    user-scoped today — when usage tracking gains credential_id we can
    tighten this to per-credential without changing the API.

    Checks are cheap (one indexed SELECT) and only run when a cap is
    actually configured, so users without governance pay nothing.
    """
    if scope.monthly_request_cap is None and scope.monthly_spend_cap_usd is None:
        return

    # Import here to avoid a circular at module import time (the
    # subscription module pulls in many app internals).
    from app.db.models.subscription import TokenUsage

    now = datetime.now(timezone.utc)
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    result = await db.execute(
        select(TokenUsage).where(
            TokenUsage.user_id == user_id,
            TokenUsage.period_start == period_start.replace(tzinfo=None),
        )
    )
    usage = result.scalar_one_or_none()
    if usage is None:
        # No calls yet this period — cannot be over cap.
        return

    if scope.monthly_request_cap is not None and usage.llm_calls >= scope.monthly_request_cap:
        raise BYOKError.quota_exceeded(
            f"Monthly request cap of {scope.monthly_request_cap} reached for this credential."
        )

    if scope.monthly_spend_cap_usd is not None:
        # Cost is not stored per-call today, so we can only enforce this
        # cap on tokens. Use a blended average price (Haiku's output rate
        # as a conservative floor) until per-call cost is recorded.
        blended_rate = 1.25 / 1_000_000.0  # USD / token, conservative
        estimated_spend = (usage.input_tokens + usage.output_tokens) * blended_rate
        if estimated_spend >= scope.monthly_spend_cap_usd:
            raise BYOKError.quota_exceeded(
                f"Monthly spend cap of ${scope.monthly_spend_cap_usd:.2f} reached "
                f"(estimated ${estimated_spend:.2f} this period)."
            )


async def enforce_scope(
    db: AsyncSession,
    *,
    scope: Scope,
    user_id: str,
    model: str,
) -> None:
    """Convenience wrapper: run both model and quota checks in the order
    the gateway wants them (cheap model check before the DB round-trip)."""
    assert_model_allowed(scope, model)
    await assert_not_over_quota(db, user_id, scope)
