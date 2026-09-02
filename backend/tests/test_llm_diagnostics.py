"""Diagnostics for the "I'm having trouble connecting to my AI backend" path.

Covers the pieces added while diagnosing a production chat outage:

* the 5xx / 529 / unknown fallthrough in the BYOK error mapper now carries
  ``upstream_status`` and a status-aware message (and logs a breadcrumb);
* ``describe_llm_failure`` names provider / model / key source so the chat
  bubble is actionable instead of a bare generic string;
* ``decrypt_ai_config_key`` handles both envelope (v2) and legacy (Fernet)
  rows — envelope rows used to raise and silently downgrade to the
  platform key;
* per-specialist model overrides go through the same alias map as the
  top-level model.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.api.chat import describe_llm_failure
from app.byok.errors import BYOKError, BYOKErrorCode, map_anthropic_exception
from app.services.user_llm import (
    ResolvedLLM,
    byok_skip_reason,
    decrypt_ai_config_key,
)


def _sdk_exc(name: str, status_code: int | None = None, request_id: str | None = None):
    cls = type(name, (Exception,), {})
    exc = cls("boom")
    if status_code is not None:
        exc.status_code = status_code
    if request_id is not None:
        exc.request_id = request_id
    return exc


# --- mapper fallthrough ----------------------------------------------------


class TestServerErrorMapping:
    def test_529_overloaded_is_labelled_and_carries_status(self, caplog) -> None:
        with caplog.at_level("WARNING", logger="app.byok.errors"):
            mapped = map_anthropic_exception(
                _sdk_exc("APIStatusError", status_code=529, request_id="req_1")
            )
        assert mapped.code == BYOKErrorCode.PROVIDER_SERVER_ERROR
        assert mapped.upstream_status == 529
        assert mapped.upstream_error == "APIStatusError"
        assert mapped.provider_request_id == "req_1"
        assert "overloaded" in mapped.message.lower()
        assert "529" in mapped.message
        # Breadcrumb lands in the logs, without the exception text.
        assert "upstream_status=529" in caplog.text
        assert "boom" not in caplog.text

    def test_500_message_includes_status(self) -> None:
        mapped = map_anthropic_exception(
            _sdk_exc("InternalServerError", status_code=500)
        )
        assert mapped.upstream_status == 500
        assert "HTTP 500" in mapped.message

    def test_unknown_exception_is_flagged_as_not_transient(self) -> None:
        mapped = map_anthropic_exception(RuntimeError("who knows"))
        assert mapped.code == BYOKErrorCode.PROVIDER_SERVER_ERROR
        assert mapped.upstream_status is None
        assert mapped.upstream_error == "RuntimeError"
        assert "unexpectedly" in mapped.message
        assert "RuntimeError" in mapped.message
        # Never the raw exception text.
        assert "who knows" not in mapped.message


# --- user-facing description -----------------------------------------------


def _resolved(
    provider="anthropic", model="claude-sonnet-4-6", is_byok=True
) -> ResolvedLLM:
    return ResolvedLLM(client=object(), model=model, provider=provider, is_byok=is_byok)


class TestDescribeLLMFailure:
    def test_byok_error_names_provider_model_and_key_source(self) -> None:
        err = BYOKError(
            code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
            http_status=502,
            retryable=True,
            message="The provider is overloaded right now (HTTP 529).",
            provider_request_id="req_abc",
            upstream_status=529,
        )
        text = describe_llm_failure(err, _resolved())
        assert "Anthropic" in text
        assert "claude-sonnet-4-6" in text
        assert "your own API key" in text
        assert "overloaded" in text
        assert "code=provider_server_error" in text
        assert "upstream_status=529" in text
        assert "request_id=req_abc" in text

    def test_platform_key_is_called_out(self) -> None:
        err = BYOKError(
            code=BYOKErrorCode.CREDENTIAL_INVALID, http_status=401, retryable=False
        )
        text = describe_llm_failure(
            err, _resolved(model="claude-haiku-4-5", is_byok=False)
        )
        assert "the platform key" in text
        assert "rejected" in text.lower()

    def test_raw_exception_never_leaks_its_text(self) -> None:
        text = describe_llm_failure(ValueError("sk-ant-SECRET"), _resolved())
        assert "sk-ant-SECRET" not in text
        assert "ValueError" in text
        assert "diagnose" in text

    def test_no_resolved_llm_falls_back_to_platform_wording(self) -> None:
        text = describe_llm_failure(RuntimeError("x"), None)
        assert "platform default provider" in text


# --- decrypt: envelope vs legacy -------------------------------------------


class TestDecryptAIConfigKey:
    def test_envelope_row_uses_envelope_crypto(self) -> None:
        row = SimpleNamespace(
            api_key_encrypted=b"ct",
            ciphertext_iv=b"iv",
            ciphertext_tag=b"tag",
            encrypted_dek=b"dek",
            kek_id="kek-1",
            encryption_salt=None,
        )
        with (
            patch(
                "app.services.user_llm.byok_crypto.decrypt_api_key",
                return_value="sk-env",
            ) as env,
            patch("app.services.user_llm.decrypt_credential") as legacy,
        ):
            assert decrypt_ai_config_key(row) == "sk-env"
        bundle = env.call_args.args[0]
        assert (
            bundle.ciphertext,
            bundle.iv,
            bundle.auth_tag,
            bundle.encrypted_dek,
            bundle.kek_id,
        ) == (b"ct", b"iv", b"tag", b"dek", "kek-1")
        legacy.assert_not_called()

    def test_legacy_row_uses_fernet(self) -> None:
        row = SimpleNamespace(
            api_key_encrypted=b"fernet-token",
            ciphertext_iv=None,
            ciphertext_tag=None,
            encrypted_dek=None,
            kek_id=None,
            encryption_salt=b"salt",
        )
        with (
            patch("app.services.user_llm.byok_crypto.decrypt_api_key") as env,
            patch(
                "app.services.user_llm.decrypt_credential", return_value="sk-legacy"
            ) as legacy,
        ):
            assert decrypt_ai_config_key(row) == "sk-legacy"
        legacy.assert_called_once_with(b"fernet-token", b"salt")
        env.assert_not_called()

    def test_empty_row_raises(self) -> None:
        row = SimpleNamespace(api_key_encrypted=None, encrypted_dek=None, kek_id=None)
        with pytest.raises(ValueError):
            decrypt_ai_config_key(row)


# --- eligibility gate --------------------------------------------------------


class TestByokSkipReason:
    def test_none_row(self) -> None:
        assert byok_skip_reason(None) == "no active ai_config row"

    def test_platform_default(self) -> None:
        row = SimpleNamespace(
            provider="platform_default", api_key_encrypted=b"x", is_key_valid=True
        )
        assert "platform_default" in byok_skip_reason(row)

    def test_unvalidated_key_includes_stored_error(self) -> None:
        row = SimpleNamespace(
            provider="anthropic",
            api_key_encrypted=b"x",
            is_key_valid=False,
            key_error_message="401 authentication_error",
        )
        reason = byok_skip_reason(row)
        assert "is_key_valid=false" in reason
        assert "401 authentication_error" in reason

    def test_eligible_row(self) -> None:
        row = SimpleNamespace(
            provider="anthropic", api_key_encrypted=b"x", is_key_valid=True
        )
        assert byok_skip_reason(row) is None


# --- specialist override normalization ----------------------------------------


def test_specialist_override_is_alias_mapped() -> None:
    from app.services.orchestrator import _build_specialist_request

    resolved = ResolvedLLM(
        client=object(),
        model="claude-sonnet-4-6",
        provider="anthropic",
        is_byok=True,
        specialist_models={"scout": "claude-sonnet-4-6-20260320"},
    )
    _request, _llm, effective_model = _build_specialist_request(
        "scout",
        [{"role": "user", "content": "hi"}],
        resolved_llm=resolved,
        project_context=None,
        document_context=None,
        request_id="test",
    )
    assert effective_model == "claude-sonnet-4-5"
