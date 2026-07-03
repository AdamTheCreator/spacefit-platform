# AGENTS.md

Guidance for coding agents in this repository. This file is the slim entry point; deeper
context lives in `CLAUDE.md` (full architecture, agent loop, BYOK, memory, document Q&A,
dashboard rules) and `frontend/DESIGN.md` (the design system, "quiet-first", mascot placement).
Read both before non-trivial work — they are canon and supersede any guess.

## Project Overview

Space Goose is an AI CRE workbench for brokers — the product is a chat, backed by
specialist agents (scout, analyst, matchmaker, outreach) routed by an orchestrator.
Three services: FastAPI backend (Python 3.11), React 19 + Vite frontend, Postgres 16.
The critical thing: chat flows through `app/services/orchestrator.py` and the agent
registry in `app/agents/` — new capabilities are agents/tools, not new endpoints.

## Build & Commands

- Full stack: `docker compose up --build` (db + backend :8000 + frontend :5173; backend auto-runs `alembic upgrade head` on boot)
- Backend dev: `cd backend && uvicorn app.main:app --reload --port 8000`
- Backend tests: `cd backend && pytest` (asyncio_mode=auto; fixtures in `tests/fixtures/`)
- Backend lint/type: `ruff check .` (line-length 88, py311) and `mypy app` (`--strict`) — both must pass
- Frontend: `cd frontend && npm run dev` / `npm run build` (tsc -b && vite build) / `npm run lint`
- DB migrations: `alembic upgrade head`; new one via `alembic revision --autogenerate -m "desc"`

`npm run build` is the **only** frontend type-check gate (no frontend test harness). A failing
`tsc -b` is a blocker. Do not re-enable React Query `refetchOnWindowFocus` (caused a request
storm against cold-starting backend).

## First-run local setup

```bash
brew install postgresql@16 && brew services start postgresql@16
createuser -s spacegoose
createdb -O spacegoose spacegoose
cd backend && uv pip install -e . && playwright install --with-deps chromium && alembic upgrade head
```

`backend/.env` needs a `DATABASE_URL` pointing at your local Postgres plus `SECRET_KEY` and
`ENCRYPTION_MASTER_KEY`. See committed `CLAUDE.md` for the canonical dev values.
Dev admin: `goose@spacegoose.com` / `goosygoo`.

## Project Layout

- `backend/app/api/` — FastAPI routes; `app/services/` — domain logic (~45 services)
- `backend/app/agents/` — specialist agents + prompts; `app/llm/` — provider-agnostic client (`get_llm_client()`)
- `backend/app/byok/` — BYOM/BYOK key encryption (`crypto.py`), audit, gateway, scope
- `backend/app/mcp/` — MCP gateway (reliability envelope: timeouts, circuit breaker, retry)
- `backend/evals/` — LLM eval harness. NOT part of pytest; hits live models. Never mix with `tests/`.
- `frontend/src/` — feature-domain folders; Zustand stores + TanStack Query; `DESIGN.md` is required reading for UI work

## Development Patterns

- Provider-agnostic LLM access only — use `get_llm_client()`, never import a vendor SDK directly.
  For user-scoped (BYOK) calls, resolve via `app/services/user_llm.py::resolve_user_llm()` and
  honor the returned `ResolvedLLM` (see BYOK rules below).
- New DB changes = new alembic migration. **NEVER edit a committed migration** — fix forward.
  (Check `alembic/versions/` for the current latest; one hash-named `5c7681bfc694` sits between 004 and 005.)
- Enum columns are plain VARCHAR, not native PG ENUMs. Models must declare
  `Enum(MyEnum, native_enum=False, length=N, values_callable=lambda e: [v.value for v in e])`,
  or asyncpg 500s with `type "..." does not exist`.
- Follow the closest existing service/agent as the pattern for new ones.

## BYOK rules (do not leak platform tokens)

- Any new code path that calls an LLM must accept and honor a `resolved_llm`. When `is_byok=True`,
  route through the user's client AND skip `record_token_usage` / `check_token_budget` AND skip the
  classifier fallback in `guardrails.py`. Ignoring this leaks tokens to the platform key and breaks
  the zero-platform-tokens guarantee.
- Chat-cap checks must call `SubscriptionService.check_can_use`, not `plan.chat_sessions_per_month`
  directly — `check_can_use` applies the BYOK free-tier lift (10 → 50 sessions).

## Testing Expectations

- New backend logic needs pytest coverage; bug fixes need a regression test
- Don't weaken failing tests to pass; evals (90% routing gate) are advisory — run separately

## Git Workflow

- Feature branches → PR into `master`. CI hard gates: frontend build + backend pytest
- Conventional Commits, scoped: `feat(dashboard): ...`, `fix(layout): ...`, `chore(...):`, `docs(...):`
- Run `npm run build` (frontend) and `ruff check . && mypy app && pytest tests/` (backend) before committing

## Security & Data

- BYOK keys are encrypted (`app/byok/crypto.py`) — never log or echo key material, JWTs, or `ENCRYPTION_MASTER_KEY`
- All LLM tool calls route through the MCP gateway (`app/mcp/reliability.py`) for audit logging + rate
  limiting + circuit breaker. Don't call Claude/OpenAI directly from new code — register a tool with the gateway.
- `document_search` (and any new retrieval tool) must filter by `user_id` at the query level — that indexed
  lookup is the auth boundary, not just the gateway.
- `POST /api/v1/sales/leads` is public/unauth; rate-limited per-IP in-process (per-worker memory — swap for
  Redis when scaling horizontally).
- Never commit real customer documents or PII

## Specialist agents — keep all four in sync

When adding a specialist, all of these must stay complete or CI/`tsc` fails:

1. Register in `app/agents/specialists/registry.py::SPECIALIST_REGISTRY` (`system_prompt`, `allowed_tools`, tier hint)
2. Add the literal name to `AgentType` in **both** `backend/app/models/chat.py` and `frontend/src/types/chat.ts` (+ `AGENTS` label map)
3. Extend `_SPECIALIST_TO_AGENT_TYPE` in `app/api/chat.py` (enforced by `test_specialist_agent_type_map_is_complete`)
4. Add SVG icon + color + `idle` state in `frontend/src/components/Chat/AgentActivityPanel.tsx` (all three `Record<AgentType, …>` maps)

## Operational scripts (`cd backend/scripts`)

- `seed_admin.py` — create/promote an admin user from env vars
- `seed_demo.py` — populate demo data
- `byok_verify.py` — end-to-end BYOK verification (PASS/FAIL on whether platform token counters stay flat across a chat)
- `reindex_documents.py` — backfill document chunks after chunker changes
- `smoke_project_chat.py` — fastest end-to-end check for project-chat / chunker changes without booting the UI

## Things That Will Bite You

- `VITE_API_URL`/`VITE_WS_URL` are HOST-ONLY — frontend appends `/api/v1` itself (full URL ⇒ `/api/v1/api/v1` 404s)
- `backend/spacefit.db` and a PDF in `backend/uploads/` are committed legacy artifacts — don't "clean them up" casually and don't add more
- Vision/document parsing is Anthropic-only; the Qwen/Baseten path has no `vision_document()`
- Two `ai_config` API modules coexist mid-migration (`ai_config.py` + `ai_config_v2.py`) — check `ROADMAP.md` before touching either
- Auth state is split across two localStorage keys: `access_token`/`refresh_token` (axios) and `auth-storage` (zustand). **Both must be cleared together** on auth failure, or the user ping-pongs `/dashboard` ↔ `/login`. Preserve the pattern in `src/lib/axios.ts` and `src/hooks/useChat.ts`
- Dashboard (`pages/DashboardPage.tsx`): no mock data. Every number/badge/row must trace to a real API response; if data doesn't exist yet, render a soft placeholder (`PipelinePlaceholder`), never hardcoded values
- Onboarding uses `datetime.now(UTC)` and JSON-encoded TEXT columns — don't revert to `datetime.utcnow()` or comma-separated strings
- `alembic revision --autogenerate` will flag `DocumentChunk.search_vector` as drifted — delete that hunk; it's a PG generated column (not ORM-managed)
- Don't rename `-industrial` CSS classes — they're legacy from the Spacefit era, intentionally preserved; the Space Goose rebrand swapped tokens, not class names
