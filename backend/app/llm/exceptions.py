class LLMConfigurationError(RuntimeError):
    """Raised when LLM settings are invalid or incomplete."""


class LLMProviderError(RuntimeError):
    """Raised when the underlying provider request fails."""

