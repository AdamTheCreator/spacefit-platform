import re


_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # Anthropic API keys
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}\b"),
    # OpenAI API keys (sk-proj-, sk-...)
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}\b"),
    # Google API keys
    re.compile(r"\bAIzaSy[A-Za-z0-9_\-]{20,}\b"),
    # DeepSeek API keys
    re.compile(r"\bsk-[a-f0-9]{32,}\b"),
    # OpenRouter keys
    re.compile(r"\bsk-or-[A-Za-z0-9_\-]{16,}\b"),
    # Generic bearer-style long tokens (catch-all for misc providers)
    re.compile(r"\b(?:api[_-]?key|token)[=:]\s*['\"]?[A-Za-z0-9_\-]{32,}['\"]?", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact obvious secrets from loggable text."""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
