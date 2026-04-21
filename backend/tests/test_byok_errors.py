"""Tests for BYOK error normalization.

Covers the three mapper functions and the ``Retry-After`` parser. The
provider exception classes are duck-typed by name, so these tests use
stand-in exception subclasses rather than importing vendor SDKs.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.byok.errors import (
    BYOKError,
    BYOKErrorCode,
    map_anthropic_exception,
    map_openai_exception,
    map_openai_http_response,
    parse_retry_after,
)

# --- Anthropic mapping -------------------------------------------------------


def _fake_sdk_exc(name: str, *, status_code: int | None = None, request_id: str | None = None,
                  retry_after: str | None = None) -> Exception:
    """Build an exception that looks enough like the anthropic SDK types
    for the mapper to dispatch on class name + attributes."""
    cls = type(name, (Exception,), {})
    exc = cls("synthetic")
    if status_code is not None:
        exc.status_code = status_code  # type: ignore[attr-defined]
    if request_id:
        exc.request_id = request_id  # type: ignore[attr-defined]
    if retry_after is not None:
        exc.response = SimpleNamespace(headers={"retry-after": retry_after})  # type: ignore[attr-defined]
    return exc


class TestAnthropicMapper:
    def test_401_maps_to_credential_invalid(self) -> None:
        mapped = map_anthropic_exception(_fake_sdk_exc("AuthenticationError", status_code=401))
        assert mapped.code == BYOKErrorCode.CREDENTIAL_INVALID
        assert mapped.http_status == 401
        assert mapped.retryable is False

    def test_403_maps_to_forbidden(self) -> None:
        mapped = map_anthropic_exception(_fake_sdk_exc("PermissionDeniedError", status_code=403))
        assert mapped.code == BYOKErrorCode.CREDENTIAL_FORBIDDEN

    def test_429_maps_to_rate_limited_with_retry_after(self) -> None:
        mapped = map_anthropic_exception(
            _fake_sdk_exc("RateLimitError", status_code=429, retry_after="15")
        )
        assert mapped.code == BYOKErrorCode.CREDENTIAL_RATE_LIMITED
        assert mapped.retryable is True
        assert mapped.retry_after_seconds == 15.0

    def test_timeout_maps_to_provider_timeout(self) -> None:
        mapped = map_anthropic_exception(_fake_sdk_exc("APITimeoutError"))
        assert mapped.code == BYOKErrorCode.PROVIDER_TIMEOUT
        assert mapped.retryable is True

    def test_connection_error_maps_to_provider_unavailable(self) -> None:
        mapped = map_anthropic_exception(_fake_sdk_exc("APIConnectionError"))
        assert mapped.code == BYOKErrorCode.PROVIDER_UNAVAILABLE

    def test_400_maps_to_invalid_request(self) -> None:
        mapped = map_anthropic_exception(_fake_sdk_exc("BadRequestError", status_code=400))
        assert mapped.code == BYOKErrorCode.INVALID_REQUEST

    def test_500_maps_to_server_error_retryable(self) -> None:
        mapped = map_anthropic_exception(_fake_sdk_exc("InternalServerError", status_code=500))
        assert mapped.code == BYOKErrorCode.PROVIDER_SERVER_ERROR
        assert mapped.retryable is True

    def test_unknown_exception_falls_back_to_server_error(self) -> None:
        mapped = map_anthropic_exception(RuntimeError("who knows"))
        assert mapped.code == BYOKErrorCode.PROVIDER_SERVER_ERROR

    def test_extracts_request_id(self) -> None:
        mapped = map_anthropic_exception(
            _fake_sdk_exc("AuthenticationError", status_code=401, request_id="req_abc123")
        )
        assert mapped.provider_request_id == "req_abc123"


# --- OpenAI-compatible mapper ------------------------------------------------


def _response(status_code: int, *, retry_after: str | None = None, request_id: str | None = None) -> httpx.Response:
    headers: dict[str, str] = {}
    if retry_after is not None:
        headers["retry-after"] = retry_after
    if request_id:
        headers["x-request-id"] = request_id
    return httpx.Response(status_code, headers=headers)


class TestOpenAIResponseMapper:
    def test_200_returns_none(self) -> None:
        assert map_openai_http_response(_response(200)) is None

    def test_204_returns_none(self) -> None:
        assert map_openai_http_response(_response(204)) is None

    def test_401_maps_to_credential_invalid(self) -> None:
        mapped = map_openai_http_response(_response(401))
        assert mapped is not None
        assert mapped.code == BYOKErrorCode.CREDENTIAL_INVALID

    def test_403_maps_to_forbidden(self) -> None:
        mapped = map_openai_http_response(_response(403))
        assert mapped is not None
        assert mapped.code == BYOKErrorCode.CREDENTIAL_FORBIDDEN

    def test_429_honors_retry_after(self) -> None:
        mapped = map_openai_http_response(_response(429, retry_after="8"))
        assert mapped is not None
        assert mapped.code == BYOKErrorCode.CREDENTIAL_RATE_LIMITED
        assert mapped.retry_after_seconds == 8.0

    def test_429_without_retry_after(self) -> None:
        mapped = map_openai_http_response(_response(429))
        assert mapped is not None
        assert mapped.retry_after_seconds is None

    def test_400_maps_to_invalid_request(self) -> None:
        mapped = map_openai_http_response(_response(400))
        assert mapped is not None
        assert mapped.code == BYOKErrorCode.INVALID_REQUEST

    def test_500_maps_to_server_error(self) -> None:
        mapped = map_openai_http_response(_response(500))
        assert mapped is not None
        assert mapped.code == BYOKErrorCode.PROVIDER_SERVER_ERROR
        assert mapped.retryable is True

    def test_extracts_request_id(self) -> None:
        mapped = map_openai_http_response(_response(401, request_id="req_xyz"))
        assert mapped is not None
        assert mapped.provider_request_id == "req_xyz"


class TestOpenAIExceptionMapper:
    def test_timeout_exception(self) -> None:
        # httpx.TimeoutException is the base for read/connect/write timeouts.
        mapped = map_openai_exception(httpx.ReadTimeout("timed out"))
        assert mapped.code == BYOKErrorCode.PROVIDER_TIMEOUT
        assert mapped.retryable is True

    def test_connect_error(self) -> None:
        mapped = map_openai_exception(httpx.ConnectError("refused"))
        assert mapped.code == BYOKErrorCode.PROVIDER_UNAVAILABLE

    def test_http_status_error_delegates_to_response_mapper(self) -> None:
        resp = _response(429, retry_after="3")
        exc = httpx.HTTPStatusError("429", request=httpx.Request("POST", "http://x"), response=resp)
        mapped = map_openai_exception(exc)
        assert mapped.code == BYOKErrorCode.CREDENTIAL_RATE_LIMITED
        assert mapped.retry_after_seconds == 3.0

    def test_unknown_exception_falls_back_to_server_error(self) -> None:
        mapped = map_openai_exception(RuntimeError("surprise"))
        assert mapped.code == BYOKErrorCode.PROVIDER_SERVER_ERROR


# --- Retry-After parser ------------------------------------------------------


class TestRetryAfterParser:
    def test_integer_seconds(self) -> None:
        assert parse_retry_after("42") == 42.0

    def test_float_seconds(self) -> None:
        assert parse_retry_after("1.5") == 1.5

    def test_whitespace_tolerated(self) -> None:
        assert parse_retry_after("  10  ") == 10.0

    def test_none_or_empty(self) -> None:
        assert parse_retry_after(None) is None
        assert parse_retry_after("") is None

    def test_http_date_not_supported(self) -> None:
        # HTTP-date form is legal in the spec but unsupported here.
        assert parse_retry_after("Wed, 21 Oct 2025 07:28:00 GMT") is None

    def test_negative_clamped_to_zero(self) -> None:
        # Shouldn't happen in the wild but don't let a bad header
        # produce negative sleeps.
        assert parse_retry_after("-5") is None  # regex rejects the '-'

    def test_huge_value_clamped(self) -> None:
        # Providers sometimes send minutes or hours — we cap at 5 minutes.
        assert parse_retry_after("10000") == 300.0


# --- BYOKError constructors -------------------------------------------------


class TestBYOKErrorConstructors:
    def test_default_message_by_code(self) -> None:
        err = BYOKError(code=BYOKErrorCode.CREDENTIAL_INVALID, http_status=401, retryable=False)
        assert "rejected" in err.message.lower()

    def test_credential_not_found_includes_provider(self) -> None:
        err = BYOKError.credential_not_found("anthropic")
        assert "anthropic" in err.message

    def test_model_not_allowed_includes_model(self) -> None:
        err = BYOKError.model_not_allowed("gpt-4o")
        assert "gpt-4o" in err.message

    def test_rate_limited_carries_retry_after(self) -> None:
        err = BYOKError.rate_limited(10.0)
        assert err.retry_after_seconds == 10.0
        assert err.retryable is True

    def test_exception_is_raisable(self) -> None:
        with pytest.raises(BYOKError) as info:
            raise BYOKError.decrypt_failed()
        assert info.value.code == BYOKErrorCode.CREDENTIAL_DECRYPT_FAILED
