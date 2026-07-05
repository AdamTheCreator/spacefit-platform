"""Background fact extractor.

After each chat turn (user message + assistant reply), this service
asks a small LLM to extract durable facts about the user from the
exchange. Candidates are stored as ``UserFact`` rows in ``pending``
status and surfaced in the UI for approve/reject.

Design rules:
  - Fire-and-forget: never block the streaming response.
  - Cap candidates per turn to avoid noise (3 by default).
  - Token budget: 200 max_tokens on the extractor call so cost is
    bounded.
  - Dedupe near-identical text against existing approved + pending
    facts so the same fact isn't re-surfaced every turn.
  - BYOK-aware: use the user's BYOK provider if present; otherwise
    fall back to the platform default. Tokens recorded the same way
    as chat (skip on BYOK).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory
from app.db.models.user_fact import UserFact
from app.llm import LLMChatMessage, LLMChatRequest, get_llm_client
from app.llm.redaction import redact_secrets
from app.services.user_llm import ResolvedLLM

logger = logging.getLogger(__name__)


_EXTRACTOR_SYSTEM = """You extract durable facts about a real-estate \
professional user from a single exchange.

Return ONLY valid JSON of the form:
[{"text": "...", "category": "...", "confidence": 0.0-1.0}, ...]

Rules:
- Maximum 3 facts. Fewer is better.
- A fact must be DURABLE (still true next week), not a transient question.
- Use one of these categories: deal_prefs, geography, business_model, personal, other.
- Skip generic statements ("user asked a question"); skip property details \
specific to one analysis.
- text must be a single sentence in the user's voice ("prefers Texas \
multifamily, $5-15M deals", "works in Charlotte trade area").
- confidence is your honest estimate of how durable + accurate the fact is.

If no durable facts can be extracted, return [].
"""


_MAX_FACTS_PER_TURN = 3
_MAX_FACT_TEXT_CHARS = 240
_DEDUPE_SIMILARITY_THRESHOLD = 0.85
_EXTRACTOR_MAX_TOKENS = 200


def _normalize_for_dedupe(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _jaccard_similarity(a: str, b: str) -> float:
    """Cheap token-overlap similarity, good enough for near-duplicate suppression."""
    set_a = set(_normalize_for_dedupe(a).split())
    set_b = set(_normalize_for_dedupe(b).split())
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _parse_fact_payload(raw: str) -> list[dict[str, Any]]:
    """Parse a JSON list out of an LLM response.

    Models sometimes wrap their JSON in prose or code fences. We strip
    common wrappers and look for the first ``[ ... ]`` block.
    """
    cleaned = raw.strip()
    # Strip markdown code fences.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return []

    # Find the first top-level JSON list.
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    candidate = cleaned[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        text = text[:_MAX_FACT_TEXT_CHARS]
        category = str(entry.get("category") or "other").strip().lower()
        if category not in ("deal_prefs", "geography", "business_model", "personal", "other"):
            category = "other"
        try:
            confidence = float(entry.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        out.append({"text": text, "category": category, "confidence": confidence})
    return out[:_MAX_FACTS_PER_TURN]


async def _existing_fact_texts(db, user_id: str) -> list[str]:
    """Return texts of pending + approved facts for dedupe."""
    result = await db.execute(
        select(UserFact.text).where(
            UserFact.user_id == user_id,
            UserFact.status.in_(("pending", "approved")),
        )
    )
    return [row[0] for row in result.all()]


async def extract_facts_from_turn(
    *,
    user_id: str,
    user_message: str,
    assistant_response: str,
    session_id: str | None = None,
    message_id: str | None = None,
    resolved_llm: ResolvedLLM | None = None,
) -> list[UserFact]:
    """Extract candidate facts from one chat turn and persist them as pending.

    Returns the list of persisted ``UserFact`` rows (may be empty).
    Safe to call concurrently — each invocation opens its own session.
    Never raises into the caller; logs and returns [] on any error.
    """
    if not user_message.strip() or not assistant_response.strip():
        return []

    llm = resolved_llm.client if resolved_llm else get_llm_client()
    model = (
        resolved_llm.model
        if resolved_llm
        else None
    )
    if not model:
        from app.core.config import settings

        model = settings.anthropic_model or "claude-haiku-4-5"

    user_payload = (
        "User message:\n"
        + redact_secrets(user_message)
        + "\n\nAssistant reply:\n"
        + redact_secrets(assistant_response)
    )

    try:
        response = await llm.chat(
            LLMChatRequest(
                system=_EXTRACTOR_SYSTEM,
                messages=[LLMChatMessage(role="user", content=user_payload)],
                model=model,
                max_tokens=_EXTRACTOR_MAX_TOKENS,
                request_id=uuid.uuid4().hex[:8],
            )
        )
    except Exception as e:
        logger.warning("[fact_extractor] LLM call failed: %s", e)
        return []

    candidates = _parse_fact_payload(response.content)
    if not candidates:
        return []

    async with async_session_factory() as db:
        existing = await _existing_fact_texts(db, user_id)

        persisted: list[UserFact] = []
        for cand in candidates:
            # Dedupe against everything the user already has.
            if any(
                _jaccard_similarity(cand["text"], existing_text)
                >= _DEDUPE_SIMILARITY_THRESHOLD
                for existing_text in existing
            ):
                continue
            fact = UserFact(
                user_id=user_id,
                text=cand["text"],
                category=cand["category"],
                confidence=cand["confidence"],
                source_session_id=session_id,
                source_message_id=message_id,
                status="pending",
            )
            db.add(fact)
            persisted.append(fact)
            existing.append(cand["text"])

        if persisted:
            await db.commit()
            for fact in persisted:
                await db.refresh(fact)

    if persisted:
        logger.info(
            "[fact_extractor] user=%s persisted=%d candidates=%d",
            user_id,
            len(persisted),
            len(candidates),
        )
    return persisted


def schedule_fact_extraction(
    *,
    user_id: str,
    user_message: str,
    assistant_response: str,
    session_id: str | None = None,
    message_id: str | None = None,
    resolved_llm: ResolvedLLM | None = None,
) -> asyncio.Task:
    """Fire-and-forget wrapper that returns the asyncio.Task.

    The caller doesn't await it; the task is logged at debug if it
    raises so we still notice extraction bugs in dev.
    """

    async def _run() -> None:
        try:
            await extract_facts_from_turn(
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                session_id=session_id,
                message_id=message_id,
                resolved_llm=resolved_llm,
            )
        except Exception:
            logger.exception("[fact_extractor] background task failed")

    return asyncio.create_task(_run())
