# AGENTS.md

## Project Overview
Space Goose is an AI CRE workbench for brokers — the product is a chat, backed by
specialist agents (scout, analyst, matchmaker, outreach) routed by an orchestrator.
Three services: FastAPI backend (Python 3.11), React 19 + Vite frontend, Postgres 16.
The critical thing: chat flows through app/services/orchestrator.py and the agent
registry in app/agents/ — new capabilities are agents/tools, not new endpoints.

## Build & Commands
- Full stack: `docker-compose up` (db + backend :8000 + frontend :5173)
- Backend tests: `cd backend && pytest` (asyncio_mode=auto; fixtures in tests/fixtures/)
- Backend lint/type: `ruff check .` (line-length 88) and `mypy --strict` — both must pass
- Frontend: `npm run dev` / `npm run build` (tsc -b && vite build) / `npm run lint`
- DB migrations: alembic; applied automatically on deploy via `alembic upgrade head`

## Project Layout
- `backend/app/api/` — FastAPI routes; `app/services/` — domain logic (~45 services)
- `backend/app/agents/` — specialist agents + prompts; `app/llm/` — provider-agnostic client
- `backend/evals/` — LLM eval harness. NOT part of pytest; hits live models. Never mix with tests/.
- `frontend/src/` — feature-domain folders; Zustand stores + TanStack Query; DESIGN.md is required reading for UI work

## Development Patterns
- Provider-agnostic LLM access only — use `get_llm_client()`, never import a vendor SDK directly
- New DB changes = new alembic migration. NEVER edit a committed migration (037 is latest)
- Follow the closest existing service/agent as the pattern for new ones

## Testing Expectations
- New backend logic needs pytest coverage; bug fixes need a regression test
- Don't weaken failing tests to pass; evals (90% routing gate) are advisory-run separately

## Git Workflow
- Feature branches → PR into `master`. CI hard gates: frontend build + backend pytest

## Security & Data
- BYOK keys are encrypted (app/byok/crypto.py) — never log or echo key material
- Never commit real customer documents or PII

## Things That Will Bite You
- `VITE_API_URL`/`VITE_WS_URL` are HOST-ONLY — frontend appends /api/v1 itself (full URL ⇒ /api/v1/api/v1 404s)
- `backend/spacefit.db` and a PDF in `backend/uploads/` are committed legacy artifacts — don't "clean them up" casually and don't add more
- Vision/document parsing is Anthropic-only; the Qwen/Baseten path has no vision_document()
- Two ai_config API modules coexist mid-migration — check ROADMAP.md before touching either
