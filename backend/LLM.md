# LLM Architecture (Backend)

## Goals

- Centralize all model calls behind a small interface (`app/llm`) so we can:
  - Swap providers/models via env vars
  - Apply consistent timeouts, retries, concurrency limits
  - Avoid leaking secrets/PII via logs

## Configuration

All settings are in `backend/app/core/config.py` and documented in `backend/.env.example`.

### Common

- `LLM_PROVIDER`: `anthropic` (default) or `openai_compatible`
- `LLM_MODEL`: model name/id (required for `openai_compatible`, optional override for `anthropic`)
- `LLM_TIMEOUT_SECONDS`: request timeout (default `60`)
- `LLM_MAX_RETRIES`: provider retry attempts (default `2`)
- `LLM_MAX_CONCURRENCY`: in-process concurrency limit for LLM calls (default `4`)
- `LLM_TOOL_RESULT_MAX_CHARS`: truncation limit when feeding tool outputs back to the model (default `12000`)

### Vision / Document Parsing

Document parsing uses a vision-capable model via `get_vision_llm_client()`:

- `LLM_VISION_PROVIDER`: optional provider override for vision tasks (defaults to `LLM_PROVIDER`)
- `LLM_VISION_MODEL`: optional vision model override

Note: `openai_compatible` currently does **not** implement `vision_document()`; document parsing requires `anthropic`.

### Anthropic

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` (used when `LLM_MODEL` is not set)

### OpenAI-compatible

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (default `https://api.openai.com/v1`)

## Code Layout

- `backend/app/llm/client.py`
  - `get_llm_client()` for chat/orchestrator calls
  - `get_vision_llm_client()` for document parsing
  - provider selection via `LLM_PROVIDER` / `LLM_VISION_PROVIDER`
- `backend/app/llm/providers/anthropic_client.py`
- `backend/app/llm/providers/openai_compatible_client.py`

## Adding a New Provider

1. Implement a new provider class in `backend/app/llm/providers/`.
2. Ensure it implements:
   - `chat(request: LLMChatRequest) -> LLMResponse`
   - `vision_document(request: LLMVisionRequest) -> str` (or raise a clear configuration error)
   - `aclose()`
3. Register it in `backend/app/llm/client.py` `_build_client()`.

## Safety Notes

- The orchestrator redacts obvious API keys from user/tool text before sending it to providers.
- Tool outputs are treated as **untrusted data** and are truncated before synthesis to reduce prompt injection surface and runaway token usage.
- Replaced `print()`-style logging in chat/tool paths with `logging` to avoid leaking sensitive inputs.

