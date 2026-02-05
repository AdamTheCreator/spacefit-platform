import re


_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # Common API key prefixes
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bAIzaSy[A-Za-z0-9_\-]{20,}\b"),  # Google API keys often start like this
]


def redact_secrets(text: str) -> str:
    """Redact obvious secrets from loggable text."""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted

