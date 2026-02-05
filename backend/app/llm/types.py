from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class LLMChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[LLMToolCall]
    stop_reason: str | None


@dataclass(frozen=True)
class LLMChatRequest:
    system: str
    messages: list[LLMChatMessage]
    model: str
    max_tokens: int = 2048
    tools: list[dict[str, Any]] | None = None
    tool_choice: dict[str, Any] | None = None
    temperature: float | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class LLMVisionDocument:
    media_type: str
    data_base64: str


@dataclass(frozen=True)
class LLMVisionRequest:
    system: str
    model: str
    max_tokens: int
    document: LLMVisionDocument
    user_text: str
    request_id: str | None = None
