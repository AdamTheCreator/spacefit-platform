# Spec: Rate-limit the public chat WebSocket endpoint

**Status:** Draft (awaiting approval)
**Owner:** backend
**Target endpoint:** `WebSocket /api/v1/chat/ws` (`app/api/chat.py::websocket_chat_endpoint`)
**Scope:** backend-only; no frontend changes required

## Problem

The repo has two chat WebSocket endpoints with inconsistent abuse protection:

| Endpoint | Location | Guardrails applied |
| --- | --- | --- |
| `/api/v1/chat/ws/{session_id}` | `websocket_endpoint` (line ~759) | size → **rate limit** → topic classifier → subscription limit → token budget |
| `/api/v1/chat/ws` (public / ChatGPT-style) | `websocket_chat_endpoint` (line ~1978) | **none** — straight from `receive_text` to orchestrator |

The public `/ws` endpoint is authenticated (it closes with `4001 Unauthorized` when the token query param is missing/invalid), but once connected a user can drive the orchestrator with no per-user throttle. A user can also sidestep the session-scoped endpoint's rate limit simply by using `/ws`, since the two endpoints do not share quota. This exposes the platform to message flooding and unbounded LLM spend.

## Goal

Add per-user rate limiting to `/api/v1/chat/ws` so the public endpoint is at least as protected as the session-scoped one, and so both endpoints share a single per-user quota.

## Non-goals

- IP-based limiting (the endpoint is authenticated; `user_id` is the correct key).
- Re-implementing the rate limiter. Reuse the existing `MessageRateLimiter` singleton.
- Adding the full guardrail stack (topic classifier, subscription, token budget) to `/ws` in this change. A companion "align guardrails" change is called out below as optional.
- Frontend changes — the existing system-message render path already displays rate-limit messages.

## Design

### Reuse the shared `rate_limiter` singleton

`app/services/guardrails.py` already exposes a process-wide `rate_limiter = MessageRateLimiter()` (in-memory sliding window, keyed by `user_id`, defaults from `settings.guardrail_rate_limit_messages` = 30 / `settings.guardrail_rate_limit_window_seconds` = 60). It is already imported in `chat.py` (line 31) and used by the session-scoped endpoint.

**Use the same singleton for `/ws`.** This guarantees one shared per-user window across both endpoints, so a user cannot bypass the session-scoped limit by switching to `/ws`. The limiter is in-memory / per-process — acceptable for the current single-uvicorn deployment, and already the accepted tradeoff elsewhere (sales-lead limiter, MCP gateway limiter, BYOK gateway). When we scale horizontally, all of these move to Redis together.

### Placement

Insert the check inside the `while True` receive loop in `websocket_chat_endpoint`, **after** the JSON parse and the `if not user_content.strip(): continue` guard, and **before** the "Create new session if needed" block. Concretely, right after `user_content = message_data.get("content", "")` and the empty-check.

Rationale:
- Before session creation: a rate-limited message must not create a `ChatSession` row or trigger the `generate_conversation_title` LLM call (both are wasted work + DB churn for a rejected message).
- Before the orchestrator: a rate-limited message must not spend any tokens.
- After the empty-check: empty messages already short-circuit, so the limiter only counts real attempts.

### Behavior on limit exceeded

Mirror the session-scoped endpoint exactly:

```python
ok, err = rate_limiter.check(user_id)
if not ok:
    await send_ws_message(
        websocket, "message",
        Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"),
    )
    continue
```

- **Do not close the socket.** The client stays connected and can retry after the window slides. Closing would force a reconnect and re-auth round-trip.
- **Do not run the orchestrator.** `continue` skips the rest of the loop body.
- The message is a normal `type: "message"` / `role: "system"` frame, so `useChat.handleWebSocketMessage` renders it with no frontend changes.

### Companion: message-size guardrail (recommended, in-scope)

While we are touching this spot, also add the cheap `validate_message_size(user_content)` check immediately before the rate-limit check — the public endpoint currently has no size cap, while the session-scoped one caps at `settings.guardrail_max_message_chars`. This is a one-line addition using an already-imported helper and closes a trivial DoS vector (giant payloads hitting the orchestrator). Same on-reject behavior: system message + `continue`.

If you want to keep this change strictly minimal, the size check can be dropped — but it is low-risk and high-value to include.

## Changes

### 1. `backend/app/api/chat.py` — `websocket_chat_endpoint`

In the receive loop, after:

```python
user_content = message_data.get("content", "")
if not user_content.strip():
    continue
```

add:

```python
# --- Guardrail checks (pre-LLM) ---
# 1. Message size (cheap DoS cap; mirrors /ws/{session_id})
ok, err = validate_message_size(user_content)
if not ok:
    await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
    continue

# 2. Rate limit — shared singleton with /ws/{session_id} so a user
#    cannot bypass the session-scoped limit by using /ws.
ok, err = rate_limiter.check(user_id)
if not ok:
    await send_ws_message(websocket, "message", Message(role=MessageRole.SYSTEM, content=err).model_dump(mode="json"))
    continue
```

Confirm imports already present: `rate_limiter` (line 31), `validate_message_size` (verify it is imported; if not, add `from app.services.guardrails import validate_message_size, rate_limiter`).

### 2. `backend/tests/test_chat_ws_rate_limit.py` — new

Regression test that the public endpoint refuses to run the orchestrator once the per-user limit is exceeded. Approach:

- Unit-test `MessageRateLimiter` directly: `(max+1)`th `check(user_id)` returns `(False, ...)`. (Likely already covered — confirm and skip if so.)
- Endpoint-level: use `fastapi.testclient.TestClient` `websocket_connect("/api/v1/chat/ws?token=…")`. Seed the limiter to near-capacity, send one more message, assert the received frame is a `type: "message"` / `role: "system"` frame whose content contains "Rate limit", and assert the orchestrator was **not** invoked (mock `get_orchestrator_response` / `_stream_orchestrator_to_ws` and assert call count 0).

If the endpoint is hard to exercise in-process because of the auth + DB session setup, extract the guardrail block into a tiny pure helper (`_pre_orchestrator_guardrails(user_id, content) -> tuple[bool, str | None]`) and unit-test that directly, then call it from both endpoints. This mirrors the existing `_stream_orchestrator_to_ws` extraction-for-testability pattern.

### 3. (Optional) `backend/app/core/config.py`

If a separate, tighter limit for the public endpoint is ever wanted (e.g. lower than the session-scoped one), add `public_ws_rate_limit_messages` / `public_ws_rate_limit_window_seconds` and construct a second `MessageRateLimiter` instance for `/ws`. **Default: do not add this** — sharing the singleton is the correct first step and is what this spec implements.

## Verification

1. `cd backend && ruff check . && mypy app && pytest tests/` — all green.
2. New test passes.
3. Manual: connect to `/ws` with a valid token, send `guardrail_rate_limit_messages + 1` messages in under 60s, confirm the (N+1)th returns a system "Rate limit exceeded" message and the socket stays open; confirm a subsequent message after the window slides succeeds.
4. Cross-endpoint: confirm a user who exhausts the limit on `/ws` is also blocked on `/ws/{session_id}` (shared singleton) and vice versa.

## Risks / notes

- **In-memory limiter resets on process restart** and is per-worker. Already the accepted tradeoff across the codebase; flag for Redis when we go multi-worker.
- **No IP keying.** The endpoint is authenticated, so `user_id` is correct. If we ever add an unauthenticated public chat surface, that would need IP keying (like `app/api/sales.py::_IPRateLimiter`) — out of scope here.
- **BYOK users are not exempt.** Rate limiting protects the platform from abuse regardless of whose key funds the tokens. This matches the session-scoped endpoint. (The subscription/token-budget guards are the BYOK-aware ones; rate limiting is not, and should not be.)
- **Frontend:** none required. The system message renders through the existing path. No new WS event type.
