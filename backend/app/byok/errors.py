"""Normalized error surface for the BYOK subsystem.

Every provider-call failure — from Anthropic, the OpenAI-compatible adapter
covering OpenAI/Gemini/DeepSeek/custom endpoints, or the gateway itself —
ends up as a :class:`BYOKError` with a stable code from
:class:`BYOKErrorCode`. That code is what:

    * the chat handler uses to decide which message to send over the
      WebSocket (so the UI can distinguish "your key is invalid" from
      "the provider is down");
    * the HTTP API uses to set the correct status code and body;
    * the gateway uses to decide whether to retry, auto-invalidate the
      credential, or pass the error through untouched.

The mapper functions below are deliberately defensive: they inspect
``status_code`` first (cheap and stable), then the exception class name
(works without importing vendor SDKs), then the message substring (last
resort). That layering means the mapper keeps working if a vendor ships
a new error subtype between SDK versions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

__all__ = [
    "BYOKError",
    "BYOKErrorCode",
    "map_anthropic_exception",
    "map_openai_exception",
    "map_openai_http_response",
    "parse_retry_after",
]


class BYOKErrorCode:
    """String constants used as ``BYOKError.code``.

    Not an :class:`enum.Enum` so callers can compare against plain strings
    coming from JSON payloads without coercion. All values are namespaced
    under these prefixes for grep-ability:

    ``credential_*``  — something about this user's credential
    ``model_*``       — the requested model isn't allowed
    ``provider_*``    — the upstream provider failed us
    ``invalid_request``, ``unsupported_provider`` — platform-side validation
    """

    CREDENTIAL_NOT_FOUND = "credential_not_found"
    CREDENTIAL_INVALID = "credential_invalid"
    CREDENTIAL_FORBIDDEN = "credential_forbidden"
    CREDENTIAL_RATE_LIMITED = "credential_rate_limited"
    CREDENTIAL_QUOTA_EXCEEDED = "credential_quota_exceeded"
    CREDENTIAL_DECRYPT_FAILED = "credential_decrypt_failed"
    CREDENTIAL_DUPLICATE = "credential_duplicate"
    MODEL_NOT_ALLOWED = "model_not_allowed"
    PROVIDER_SERVER_ERROR = "provider_server_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_PROVIDER = "unsupported_provider"


# User-facing messages. The exceptions carry the detail; these are the
# short, human-safe strings the UI shows. Never include the provider's
# raw error text here — that's the scrubbing boundary.
_DEFAULT_MESSAGES: dict[str, str] = {
    BYOKErrorCode.CREDENTIAL_NOT_FOUND: "No API key is configured for this provider.",
    BYOKErrorCode.CREDENTIAL_INVALID: "Your API key was rejected by the provider. It may have been revoked or rotated — try validating again or enter a new key.",
    BYOKErrorCode.CREDENTIAL_FORBIDDEN: "Your API key doesn't have access to the requested model. Check your provider account's model access settings.",
    BYOKErrorCode.CREDENTIAL_RATE_LIMITED: "Your provider rate-limited this request. Wait a moment and try again.",
    BYOKErrorCode.CREDENTIAL_QUOTA_EXCEEDED: "This credential has hit its configured monthly cap.",
    BYOKErrorCode.CREDENTIAL_DECRYPT_FAILED: "We couldn't decrypt the stored credential. Please re-enter your API key.",
    BYOKErrorCode.CREDENTIAL_DUPLICATE: "That API key is already stored on your account.",
    BYOKErrorCode.MODEL_NOT_ALLOWED: "The requested model isn't allowed for this credential.",
    BYOKErrorCode.PROVIDER_SERVER_ERROR: "The provider returned a server error. This is usually transient.",
    BYOKErrorCode.PROVIDER_TIMEOUT: "The provider didn't respond in time.",
    BYOKErrorCode.PROVIDER_UNAVAILABLE: "We couldn't reach the provider.",
    BYOKErrorCode.INVALID_REQUEST: "The request was malformed.",
    BYOKErrorCode.UNSUPPORTED_PROVIDER: "This provider isn't supported.",
}


@dataclass
class BYOKError(Exception):
    """Normalized BYOK failure.

    :param code: one of :class:`BYOKErrorCode` string values.
    :param http_status: HTTP status the REST layer should return.
    :param retryable: whether the gateway should retry this class of
        failure. The gateway caps total attempts regardless.
    :param message: user-facing message. Callers should prefer the
        default from ``_DEFAULT_MESSAGES`` unless they have a specific,
        safe reason to override. **Never** put provider raw text here.
    :param provider_request_id: upstream request id if one was returned,
        useful for support/debugging. Safe to log.
    :param retry_after_seconds: hint from the provider's ``Retry-After``
        header on 429s. Cooldown logic in the gateway honors this.
    """

    code: str
    http_status: int
    retryable: bool
    message: str = ""
    provider_request_id: str | None = None
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.message:
            self.message = _DEFAULT_MESSAGES.get(self.code, "Request failed.")
        super().__init__(self.message)

    @classmethod
    def credential_not_found(cls, provider: str) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.CREDENTIAL_NOT_FOUND,
            http_status=404,
            retryable=False,
            message=f"No API key is configured for {provider}.",
        )

    @classmethod
    def credential_invalid(cls, message: str | None = None) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.CREDENTIAL_INVALID,
            http_status=401,
            retryable=False,
            message=message or _DEFAULT_MESSAGES[BYOKErrorCode.CREDENTIAL_INVALID],
        )

    @classmethod
    def model_not_allowed(cls, model: str) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.MODEL_NOT_ALLOWED,
            http_status=403,
            retryable=False,
            message=f"Model {model!r} is not allowed for this credential.",
        )

    @classmethod
    def quota_exceeded(cls, detail: str) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.CREDENTIAL_QUOTA_EXCEEDED,
            http_status=402,
            retryable=False,
            message=detail,
        )

    @classmethod
    def rate_limited(cls, retry_after_seconds: float | None) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.CREDENTIAL_RATE_LIMITED,
            http_status=429,
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )

    @classmethod
    def decrypt_failed(cls) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.CREDENTIAL_DECRYPT_FAILED,
            http_status=500,
            retryable=False,
        )

    @classmethod
    def duplicate(cls) -> "BYOKError":
        return cls(
            code=BYOKErrorCode.CREDENTIAL_DUPLICATE,
            http_status=409,
            retryable=False,
        )


# --- Retry-After parsing -----------------------------------------------------


_RETRY_AFTER_INT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")


def parse_retry_after(value: str | None) -> float | None:
    """Parse an HTTP ``Retry-After`` header into seconds.

    Supports the seconds form (``"30"``, ``"3.5"``). The HTTP-date form
    is not honored — we'd need the server clock to be in sync with
    ``Date:``, which we can't assume across providers. Returns ``None``
    when absent or unparseable.
    """
    if not value:
        return None
    m = _RETRY_AFTER_INT.match(value)
    if not m:
        return None
    try:
        seconds = float(m.group(1))
    except ValueError:
        return None
    # Clamp to a sensible range. Providers occasionally send very large
    # values; we don't want to stall a credential for hours on one 429.
    return max(0.0, min(seconds, 300.0))


# --- Anthropic SDK mapper ----------------------------------------------------


# These are the class names from the ``anthropic`` SDK. Duck-typed rather
# than imported so the mapper survives SDK upgrades / partial installs.
_ANTHROPIC_401_NAMES = {"AuthenticationError"}
_ANTHROPIC_403_NAMES = {"PermissionDeniedError"}
_ANTHROPIC_429_NAMES = {"RateLimitError"}
_ANTHROPIC_TIMEOUT_NAMES = {"APITimeoutError"}
_ANTHROPIC_CONN_NAMES = {"APIConnectionError"}
_ANTHROPIC_400_NAMES = {"BadRequestError", "UnprocessableEntityError"}
_ANTHROPIC_5XX_NAMES = {"InternalServerError", "APIStatusError"}


def _extract_provider_request_id(exc: Any) -> str | None:
    """Try to pull an upstream request id off an Anthropic SDK exception.

    The SDK exposes this under different attribute names across versions
    (``request_id``, ``response.headers['request-id']``); both are
    probed. Returns ``None`` on any failure — this is a best-effort hint
    for operators, never a hard requirement.
    """
    rid = getattr(exc, "request_id", None)
    if rid:
        return str(rid)
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", {}) or {}
    try:
        return headers.get("request-id") or headers.get("x-request-id")
    except Exception:
        return None


def _retry_after_from_exc(exc: Any) -> float | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", {}) or {}
    try:
        return parse_retry_after(headers.get("retry-after"))
    except Exception:
        return None


def map_anthropic_exception(exc: BaseException) -> BYOKError:
    """Map an exception from the Anthropic SDK into a :class:`BYOKError`.

    Order of checks:
      1. ``status_code`` attribute (most reliable).
      2. class name (covers cases where ``status_code`` is absent).
      3. fallthrough: treat as a generic provider server error.
    """
    cls_name = exc.__class__.__name__
    status_code = getattr(exc, "status_code", None)
    request_id = _extract_provider_request_id(exc)
    retry_after = _retry_after_from_exc(exc)

    if status_code == 401 or cls_name in _ANTHROPIC_401_NAMES:
        return BYOKError(
            code=BYOKErrorCode.CREDENTIAL_INVALID,
            http_status=401,
            retryable=False,
            provider_request_id=request_id,
        )
    if status_code == 403 or cls_name in _ANTHROPIC_403_NAMES:
        return BYOKError(
            code=BYOKErrorCode.CREDENTIAL_FORBIDDEN,
            http_status=403,
            retryable=False,
            provider_request_id=request_id,
        )
    if status_code == 429 or cls_name in _ANTHROPIC_429_NAMES:
        return BYOKError(
            code=BYOKErrorCode.CREDENTIAL_RATE_LIMITED,
            http_status=429,
            retryable=True,
            provider_request_id=request_id,
            retry_after_seconds=retry_after,
        )
    if cls_name in _ANTHROPIC_TIMEOUT_NAMES:
        return BYOKError(
            code=BYOKErrorCode.PROVIDER_TIMEOUT,
            http_status=504,
            retryable=True,
            provider_request_id=request_id,
        )
    if cls_name in _ANTHROPIC_CONN_NAMES:
        return BYOKError(
            code=BYOKErrorCode.PROVIDER_UNAVAILABLE,
            http_status=503,
            retryable=True,
            provider_request_id=request_id,
        )
    if (isinstance(status_code, int) and 400 <= status_code < 500) or cls_name in _ANTHROPIC_400_NAMES:
        return BYOKError(
            code=BYOKErrorCode.INVALID_REQUEST,
            http_status=400,
            retryable=False,
            provider_request_id=request_id,
        )
    # Anything else (5xx or an unrecognized exception class) → transient.
    return BYOKError(
        code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
        http_status=502,
        retryable=True,
        provider_request_id=request_id,
    )


# --- OpenAI-compatible HTTP mapper ------------------------------------------


def map_openai_http_response(response: Any) -> BYOKError | None:
    """Inspect an httpx response and return a :class:`BYOKError` if it
    represents a failure. Returns ``None`` for 2xx — the caller proceeds
    normally.

    This is called before ``resp.raise_for_status()`` so we can read
    headers (notably ``Retry-After``) and map cleanly. If the adapter
    already raised, use :func:`map_openai_exception` instead.
    """
    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or status_code < 400:
        return None

    headers = getattr(response, "headers", {}) or {}
    try:
        request_id = headers.get("x-request-id") or headers.get("request-id")
    except Exception:
        request_id = None
    try:
        retry_after = parse_retry_after(headers.get("retry-after"))
    except Exception:
        retry_after = None

    if status_code == 401:
        return BYOKError(
            code=BYOKErrorCode.CREDENTIAL_INVALID,
            http_status=401,
            retryable=False,
            provider_request_id=request_id,
        )
    if status_code == 403:
        return BYOKError(
            code=BYOKErrorCode.CREDENTIAL_FORBIDDEN,
            http_status=403,
            retryable=False,
            provider_request_id=request_id,
        )
    if status_code == 429:
        return BYOKError(
            code=BYOKErrorCode.CREDENTIAL_RATE_LIMITED,
            http_status=429,
            retryable=True,
            provider_request_id=request_id,
            retry_after_seconds=retry_after,
        )
    if 400 <= status_code < 500:
        return BYOKError(
            code=BYOKErrorCode.INVALID_REQUEST,
            http_status=status_code,
            retryable=False,
            provider_request_id=request_id,
        )
    # 5xx
    return BYOKError(
        code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
        http_status=502,
        retryable=True,
        provider_request_id=request_id,
    )


def map_openai_exception(exc: BaseException) -> BYOKError:
    """Map an ``httpx``-level exception (connection error, timeout) or an
    already-raised ``HTTPStatusError`` into a BYOKError.

    Prefer :func:`map_openai_http_response` when you still have the raw
    response object — it catches ``Retry-After`` and request ids, this
    function can't.
    """
    cls_name = exc.__class__.__name__
    # httpx exception hierarchy, duck-typed by name.
    if cls_name in {"TimeoutException", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout"}:
        return BYOKError(
            code=BYOKErrorCode.PROVIDER_TIMEOUT,
            http_status=504,
            retryable=True,
        )
    if cls_name in {"ConnectError", "NetworkError", "RemoteProtocolError"}:
        return BYOKError(
            code=BYOKErrorCode.PROVIDER_UNAVAILABLE,
            http_status=503,
            retryable=True,
        )
    # HTTPStatusError carries the response; let the response-based mapper
    # do the work so we pick up Retry-After and request id.
    response = getattr(exc, "response", None)
    if response is not None:
        mapped = map_openai_http_response(response)
        if mapped is not None:
            return mapped
    return BYOKError(
        code=BYOKErrorCode.PROVIDER_SERVER_ERROR,
        http_status=502,
        retryable=True,
    )
