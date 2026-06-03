"""Unit tests for the AI outreach-email generator's pure helpers.

The prompt builders + JSON parser in ``app.services.outreach_ai`` are pure +
deterministic, so they run in <1s without a live DB or LLM. Following the
established convention (``test_listing_match.py`` / ``test_void_analysis.py``)
these use ``SimpleNamespace`` voice stand-ins rather than the ORM model.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.llm.types import LLMResponse
from app.services.outreach_ai import (
    _append_signature,
    _normalize_body_html,
    build_context_block,
    build_voice_block,
    generate_outreach_email,
    parse_email_json,
)
from app.services.user_llm import ResolvedLLM


def _voice(**kwargs) -> SimpleNamespace:
    base = {
        "id": "v1",
        "instructions": None,
        "tone": None,
        "sample": None,
        "signature": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


# --- build_voice_block -----------------------------------------------------


class TestBuildVoiceBlock:
    def test_none_voice_returns_neutral_default(self) -> None:
        block = build_voice_block(None)
        assert "No saved voice profile" in block

    def test_includes_instructions_tone_and_sample(self) -> None:
        voice = _voice(
            instructions="Be punchy and warm. No corporate fluff.",
            tone="Direct, friendly",
            sample="Hey Sam — saw your new store, loved it. Quick idea...",
        )
        block = build_voice_block(voice)
        assert "punchy and warm" in block
        assert "Tone: Direct, friendly" in block
        # Sample is anchored as a style reference.
        assert "saw your new store" in block
        assert "match its rhythm" in block

    def test_truncates_long_sample(self) -> None:
        voice = _voice(instructions="x", sample="A" * 5000)
        block = build_voice_block(voice)
        # Sample is clamped to 1500 chars in the block.
        assert "A" * 1500 in block
        assert "A" * 1501 not in block

    def test_omits_absent_optional_fields(self) -> None:
        block = build_voice_block(_voice(instructions="Just the instructions."))
        assert "Tone:" not in block
        assert "real email" not in block


# --- build_context_block ---------------------------------------------------


class TestBuildContextBlock:
    def test_renders_provided_fields(self) -> None:
        block = build_context_block(
            property_name="Harper & Ninth",
            property_address="900 Harper St, Austin TX",
            vacancy_description="2,400 SF end-cap with patio",
            tenant_name="Blue Bottle",
            recipient_company="Blue Bottle Coffee",
            extra_notes="Mention the new transit stop.",
        )
        assert "Blue Bottle" in block
        assert "Harper & Ninth" in block
        assert "900 Harper St" in block
        assert "2,400 SF end-cap" in block
        assert "transit stop" in block

    def test_empty_returns_placeholder(self) -> None:
        assert "No specific property details" in build_context_block()

    def test_only_emits_present_fields(self) -> None:
        block = build_context_block(tenant_name="Acme")
        assert "Acme" in block
        assert "Property:" not in block
        assert "Address:" not in block


# --- parse_email_json ------------------------------------------------------


class TestParseEmailJson:
    def test_parses_plain_object(self) -> None:
        raw = '{"subject": "Hi", "body": "<p>Hello there</p>"}'
        out = parse_email_json(raw)
        assert out == ("Hi", "<p>Hello there</p>")

    def test_tolerates_json_fence(self) -> None:
        raw = 'Here:\n```json\n{"subject": "S", "body": "<p>B</p>"}\n```\ndone'
        assert parse_email_json(raw) == ("S", "<p>B</p>")

    def test_tolerates_bare_fence(self) -> None:
        raw = '```\n{"subject": "S2", "body": "B2"}\n```'
        assert parse_email_json(raw) == ("S2", "B2")

    def test_slices_object_out_of_prose(self) -> None:
        raw = 'Sure! {"subject": "Z", "body": "zz"} hope that helps'
        assert parse_email_json(raw) == ("Z", "zz")

    def test_missing_body_returns_none(self) -> None:
        assert parse_email_json('{"subject": "only subject"}') is None

    def test_missing_subject_is_allowed(self) -> None:
        # A body with no subject is still usable; caller backfills the subject.
        assert parse_email_json('{"body": "<p>hi</p>"}') == ("", "<p>hi</p>")

    def test_garbage_returns_none(self) -> None:
        assert parse_email_json("not json") is None

    def test_empty_returns_none(self) -> None:
        assert parse_email_json("") is None
        assert parse_email_json("   ") is None

    def test_non_object_returns_none(self) -> None:
        assert parse_email_json('["a", "b"]') is None


# --- _normalize_body_html --------------------------------------------------


class TestNormalizeBodyHtml:
    def test_passes_through_existing_html(self) -> None:
        html = "<p>already</p><p>html</p>"
        assert _normalize_body_html(html) == html

    def test_wraps_plain_text_paragraphs(self) -> None:
        out = _normalize_body_html("First para.\n\nSecond para.")
        assert out == "<p>First para.</p><p>Second para.</p>"

    def test_single_line_plain_text(self) -> None:
        assert _normalize_body_html("Just one line") == "<p>Just one line</p>"


# --- _append_signature -----------------------------------------------------


class TestAppendSignature:
    def test_appends_signature_with_br(self) -> None:
        out = _append_signature("<p>Body</p>", _voice(signature="Jane Doe\nBroker"))
        assert "<p>Jane Doe<br>Broker</p>" in out

    def test_no_signature_is_noop(self) -> None:
        assert _append_signature("<p>Body</p>", _voice()) == "<p>Body</p>"

    def test_none_voice_is_noop(self) -> None:
        assert _append_signature("<p>Body</p>", None) == "<p>Body</p>"

    def test_does_not_duplicate_existing_signature(self) -> None:
        body = "<p>Body</p>\n<p>Jane Doe</p>"
        out = _append_signature(body, _voice(signature="Jane Doe"))
        assert out.count("Jane Doe") == 1


# --- generate_outreach_email (async orchestration) -------------------------


class _FakeClient:
    """Minimal LLMClient stand-in capturing the request it was handed."""

    def __init__(self, content: str = "", raise_exc: bool = False) -> None:
        self._content = content
        self._raise = raise_exc
        self.calls: list = []

    async def chat(self, request) -> LLMResponse:  # type: ignore[no-untyped-def]
        self.calls.append(request)
        if self._raise:
            raise RuntimeError("boom")
        return LLMResponse(
            content=self._content, tool_calls=[], stop_reason="end_turn"
        )

    async def aclose(self) -> None:  # pragma: no cover - never called in tests
        pass


def _resolved(client: _FakeClient, is_byok: bool = True) -> ResolvedLLM:
    return ResolvedLLM(
        client=client,  # type: ignore[arg-type]
        model="Qwen/Qwen2.5-7B-Instruct",
        provider="huggingface",
        is_byok=is_byok,
    )


class TestGenerateOutreachEmail:
    async def test_happy_path_parses_and_injects_voice(self) -> None:
        fake = _FakeClient('{"subject": "Space at Harper", "body": "<p>Hi Sam</p>"}')
        voice = _voice(instructions="Be warm and brief.", signature="Jane Doe")
        out = await generate_outreach_email(
            resolved_llm=_resolved(fake),
            voice=voice,
            property_name="Harper & Ninth",
            tenant_name="Sam",
        )
        assert out.fallback_used is False
        assert out.subject == "Space at Harper"
        assert "<p>Hi Sam</p>" in out.body
        # Signature is appended.
        assert "Jane Doe" in out.body
        assert out.is_byok is True
        assert out.used_voice_id == "v1"
        # The voice instructions made it into the system prompt.
        assert "Be warm and brief." in fake.calls[0].system
        # Context (property/tenant) made it into the user message.
        assert "Harper & Ninth" in fake.calls[0].messages[0].content

    async def test_falls_back_to_template_on_llm_error(self) -> None:
        fake = _FakeClient(raise_exc=True)
        out = await generate_outreach_email(
            resolved_llm=_resolved(fake),
            voice=None,
            property_name="Harper & Ninth",
            tenant_name="Acme",
            vacancy_description="2,000 SF end-cap",
        )
        assert out.fallback_used is True
        # Template draft still carries the real context.
        assert "Harper & Ninth" in out.body
        assert "2,000 SF end-cap" in out.body
        assert out.subject  # non-empty

    async def test_falls_back_on_unparseable_output(self) -> None:
        fake = _FakeClient(content="sorry, I can't do that")
        out = await generate_outreach_email(
            resolved_llm=_resolved(fake),
            voice=None,
            property_name="Maple Plaza",
        )
        assert out.fallback_used is True
        assert "Maple Plaza" in out.body

    async def test_byok_flag_reflects_resolved_llm(self) -> None:
        fake = _FakeClient('{"subject": "S", "body": "<p>B</p>"}')
        out = await generate_outreach_email(
            resolved_llm=_resolved(fake, is_byok=False),
            voice=None,
        )
        assert out.is_byok is False

    async def test_blank_subject_is_backfilled(self) -> None:
        fake = _FakeClient('{"subject": "", "body": "<p>Body only</p>"}')
        out = await generate_outreach_email(
            resolved_llm=_resolved(fake),
            voice=None,
            property_name="Cedar Commons",
        )
        assert out.fallback_used is False
        # Subject backfilled from the property name.
        assert "Cedar Commons" in out.subject
