from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class LLMChatMessage:
    role: Literal["user", "assistant"]
    content: str


# --- Streaming primitives --------------------------------------------------
#
# Providers emit a heterogeneous stream of events; we normalize them into
# a small union that the orchestrator + WebSocket layer can consume without
# caring whether the underlying provider was Anthropic, OpenAI, Gemini,
# or DeepSeek. Each event carries a discriminator (`kind`) plus the
# minimum payload required to render or aggregate it.
#
# Kinds:
#   text_delta      — partial assistant text. `text` is the new fragment.
#   tool_use_start  — Claude/OpenAI announced a tool call. `tool_id`/`name`.
#   tool_use_delta  — JSON arguments arriving in pieces (mostly Anthropic).
#                     `partial_json` holds the fragment; aggregate on close.
#   tool_use_end    — tool call complete. `tool_call` carries the parsed
#                     `LLMToolCall` so downstream code doesn't reassemble.
#   message_stop    — turn complete. `stop_reason` + final token counts.
#
# Producers should always emit a final `message_stop` even on error so
# consumers can decrement in-flight counters cleanly.


@dataclass(frozen=True)
class LLMStreamChunk:
    kind: Literal[
        "text_delta",
        "tool_use_start",
        "tool_use_delta",
        "tool_use_end",
        "message_stop",
    ]
    text: str = ""
    tool_id: str = ""
    tool_name: str = ""
    partial_json: str = ""
    tool_call: "LLMToolCall | None" = None
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


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
    input_tokens: int = 0
    output_tokens: int = 0


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
