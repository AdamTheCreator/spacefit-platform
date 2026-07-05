"""AI outreach-email generation — drafts subject + body in the user's voice.

This is the LLM-backed counterpart to the template path in
``app.services.outreach_drafts``. Given a property/tenant context and an
optional :class:`~app.db.models.outreach_voice.OutreachVoiceProfile`, it asks
the resolved LLM for a short, site-specific email written in the user's voice
and returns ``{subject, body}`` ready to drop into the composer.

BYOK-aware: it routes through ``resolved_llm.client`` / ``resolved_llm.model``
when provided (mirrors ``listing_match`` / ``void_analysis``), so a configured
key keeps the zero-platform-tokens guarantee — we never record token usage
here. Any LLM failure (timeout, bad key, unparseable output) degrades to the
deterministic template path so the composer always gets a usable draft.

The prompt builders + JSON parser are pure functions so they can be unit-tested
without a live DB or LLM.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.llm import LLMChatMessage, LLMChatRequest, get_llm_client
from app.services.email_blast import (
    generate_default_subject,
    generate_void_outreach_body,
    render_template,
)
from app.services.user_llm import ResolvedLLM, resolved_or_platform_model

logger = logging.getLogger(__name__)

# Short-form B2B emails — keep the call cheap and the output tight.
_MAX_TOKENS = 900
# A touch of warmth/variation reads more human than greedy decoding.
_TEMPERATURE = 0.7
# Clamp a runaway subject line; real ones are well under this.
_MAX_SUBJECT_CHARS = 160


@dataclass
class GeneratedEmail:
    subject: str
    body: str
    used_voice_id: str | None
    model: str
    is_byok: bool
    # True when the LLM path failed and we fell back to the static template.
    fallback_used: bool


def build_voice_block(voice: Any | None) -> str:
    """Render the user's voice profile into a prompt fragment.

    Pulls ``instructions`` (the "write like me" prompt), an optional ``tone``
    hint, and an optional ``sample`` email used as a style anchor. Returns a
    neutral-professional default when no profile is supplied. Pure +
    deterministic so it is unit-testable without a DB.
    """
    if voice is None:
        return (
            "VOICE: No saved voice profile. Write in a warm, concise, "
            "professional tone — like a thoughtful broker, not a marketer."
        )

    lines: list[str] = ["VOICE — write the email exactly in this person's voice:"]
    instructions = (getattr(voice, "instructions", "") or "").strip()
    if instructions:
        lines.append(instructions)

    tone = (getattr(voice, "tone", "") or "").strip()
    if tone:
        lines.append(f"Tone: {tone}")

    sample = (getattr(voice, "sample", "") or "").strip()
    if sample:
        lines.append(
            "Here is a real email this person wrote — match its rhythm, "
            "vocabulary, and level of formality (do NOT copy its specifics):\n"
            f'"""\n{sample[:1500]}\n"""'
        )
    return "\n".join(lines)


def build_context_block(
    *,
    property_name: str = "",
    property_address: str = "",
    vacancy_description: str = "",
    tenant_name: str = "",
    recipient_company: str = "",
    extra_notes: str = "",
) -> str:
    """Render the property/tenant context the model writes about. Pure."""
    rows: list[str] = []
    if tenant_name:
        rows.append(f"Recipient / target tenant: {tenant_name}")
    if recipient_company:
        rows.append(f"Recipient company: {recipient_company}")
    if property_name:
        rows.append(f"Property: {property_name}")
    if property_address:
        rows.append(f"Address: {property_address}")
    if vacancy_description:
        rows.append(f"Available space / vacancy: {vacancy_description}")
    if extra_notes:
        rows.append(f"Notes from the sender to work in: {extra_notes}")
    if not rows:
        return "No specific property details were provided."
    return "\n".join(rows)


def parse_email_json(response_text: str) -> tuple[str, str] | None:
    """Parse a ``{"subject", "body"}`` object, tolerating fences / prose.

    Returns ``(subject, body)`` or ``None`` if nothing usable is found. Pure +
    deterministic so it is unit-testable without an LLM.
    """
    text = (response_text or "").strip()
    if not text:
        return None

    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()

    parsed: Any = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Slice out the outermost object if it's wrapped in prose.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return None

    subject = str(parsed.get("subject", "")).strip()
    body = str(parsed.get("body", "")).strip()
    if not body:
        return None
    return subject, body


def _normalize_body_html(body: str) -> str:
    """Ensure the body is composer-ready HTML (TipTap + the email sender both
    consume HTML). If the model returned plain text, wrap paragraphs in
    ``<p>`` tags; otherwise pass the markup through."""
    if "<" in body and ">" in body:
        return body
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs) or f"<p>{body}</p>"


def _append_signature(body: str, voice: Any | None) -> str:
    """Append the voice's signature (verbatim) if set and not already present."""
    if voice is None:
        return body
    signature = (getattr(voice, "signature", "") or "").strip()
    if not signature or signature in body:
        return body
    sig_html = signature.replace("\n", "<br>")
    return f"{body}\n<p>{sig_html}</p>"


_SYSTEM_PROMPT_BASE = (
    "You are an expert commercial real estate broker drafting a SHORT cold "
    "outreach email to a prospective tenant about a specific property. "
    "Rules:\n"
    "- 90–150 words. One clear ask (a brief call or reply).\n"
    "- Lead with a specific, relevant hook tied to the property/tenant — never "
    "generic filler.\n"
    "- Do NOT invent availability data, square footage, rents, or demographics "
    "that were not provided. If a detail is missing, write around it.\n"
    "- No spammy phrasing, no ALL CAPS, no exclamation spam.\n"
    "- The body must be simple HTML using <p> paragraphs (and <br> for line "
    "breaks). Do NOT include <html>, <head>, or <body> tags.\n\n"
    'Return ONLY a JSON object, no prose:\n'
    '{"subject": "concise subject line", "body": "<p>…</p>"}'
)


def _template_fallback(
    *,
    property_name: str,
    property_address: str,
    vacancy_description: str,
    tenant_name: str,
    from_name: str,
    from_email: str,
) -> tuple[str, str]:
    """Deterministic draft used when the LLM path is unavailable."""
    prop = property_name or property_address or "the property"
    subject = generate_default_subject(prop)
    body = render_template(
        generate_void_outreach_body(),
        tenant_name=tenant_name or "there",
        property_name=prop,
        property_address=property_address or "",
        user_name=from_name or "",
        user_email=from_email or "",
    )
    if vacancy_description:
        snippet = f"\n<p><strong>Available Space:</strong> {vacancy_description}</p>\n"
        body = body.replace("</body>", f"{snippet}</body>")
    return subject, body


async def generate_outreach_email(
    *,
    resolved_llm: ResolvedLLM | None,
    voice: Any | None = None,
    property_name: str = "",
    property_address: str = "",
    vacancy_description: str = "",
    tenant_name: str = "",
    recipient_company: str = "",
    extra_notes: str = "",
    from_name: str = "",
    from_email: str = "",
) -> GeneratedEmail:
    """Draft an outreach email's subject + body in the user's voice.

    Routes through ``resolved_llm`` when provided (BYOK-aware); on any failure
    or unparseable output, returns the deterministic template draft so the
    caller always has something to show.
    """
    voice_id = getattr(voice, "id", None) if voice is not None else None

    llm = resolved_llm.client if resolved_llm else get_llm_client()
    model = resolved_or_platform_model(resolved_llm)
    is_byok = bool(resolved_llm and resolved_llm.is_byok)

    system = f"{_SYSTEM_PROMPT_BASE}\n\n{build_voice_block(voice)}"
    context = build_context_block(
        property_name=property_name,
        property_address=property_address,
        vacancy_description=vacancy_description,
        tenant_name=tenant_name,
        recipient_company=recipient_company,
        extra_notes=extra_notes,
    )
    user_content = (
        f"{context}\n\n"
        "Write the outreach email now. Return the JSON object only."
    )

    try:
        response = await llm.chat(
            LLMChatRequest(
                model=model,
                max_tokens=_MAX_TOKENS,
                temperature=_TEMPERATURE,
                system=system,
                messages=[LLMChatMessage(role="user", content=user_content)],
            )
        )
        parsed = parse_email_json(response.content)
    except Exception:  # noqa: BLE001 - never block the composer on LLM failure
        logger.warning("AI outreach generation failed; using template", exc_info=True)
        parsed = None

    if parsed is None:
        subject, body = _template_fallback(
            property_name=property_name,
            property_address=property_address,
            vacancy_description=vacancy_description,
            tenant_name=tenant_name,
            from_name=from_name,
            from_email=from_email,
        )
        return GeneratedEmail(
            subject=subject,
            body=body,
            used_voice_id=voice_id,
            model=model,
            is_byok=is_byok,
            fallback_used=True,
        )

    subject, body = parsed
    subject = subject.replace("\n", " ").strip()[:_MAX_SUBJECT_CHARS]
    if not subject:
        subject = generate_default_subject(property_name or property_address or "")
    body = _append_signature(_normalize_body_html(body), voice)

    return GeneratedEmail(
        subject=subject,
        body=body,
        used_voice_id=voice_id,
        model=model,
        is_byok=is_byok,
        fallback_used=False,
    )
