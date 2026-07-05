# Space Goose

**Space Goose** (`spacegoose.ai`) is an AI-driven commercial real estate workbench.
The product is a chat: brokers talk to a specialist-routed agent that analyzes
properties, surfaces tenant gaps, pulls comps, and drafts outreach.

For the full architecture, agent loop, BYOK rules, memory system, and document Q&A
pipeline, see [`CLAUDE.md`](./CLAUDE.md). Contributor guardrails live in
[`AGENTS.md`](./AGENTS.md), and the design system is documented in
[`frontend/DESIGN.md`](./frontend/DESIGN.md).

## Repository shape

```
frontend/   React 19 + TS + Vite 7 + Tailwind v4 SPA
backend/    FastAPI + Python 3.11 + PostgreSQL 16
docker-compose.yml    local dev (db + backend + frontend)
render.yaml           Render blueprint
```

No workspace tooling. `npm` runs inside `frontend/`, `uv`/`pip` inside `backend/`.

## Common commands

### Frontend (`cd frontend`)

```
npm install
npm run dev      # vite dev server on :5173
npm run build    # tsc -b && vite build  (type-check + production bundle)
npm run lint     # eslint .
```

`npm run build` is the only frontend type-check gate; a failing `tsc -b` is a blocker.

### Backend (`cd backend`)

```
uv pip install -e .
playwright install --with-deps chromium
alembic upgrade head
uvicorn app.main:app --reload --port 8000
pytest tests/
ruff check .
mypy app
```

### Full stack

```
docker compose up --build
```

The `backend` container runs `alembic upgrade head` on boot, so a fresh DB
converges to latest schema automatically.

## Document Freshness & Re-indexing

Every project document is chunked into `document_chunks` for tsvector search
(see the "Project document Q&A" section of `CLAUDE.md`). The freshness feature
tracks *when* each document was last chunked and exposes an operator-triggered
re-index so stale chunks can be refreshed on demand.

- **DB column:** `parsed_documents.indexed_at` (nullable timestamp; added in
  migration `040_document_indexed_at.py`).
- **Auto-stamping:** `app/services/document_chunker.py::index_document` sets
  `indexed_at` in the same transaction as the chunk delete+insert, so the
  automatic upload path, `POST /documents/{id}/reprocess`, and the new
  `/reindex` endpoint all populate the field.
- **Endpoint:** `POST /api/v1/documents/{id}/reindex` (user-scoped).
  - `200 OK` → `{ id, indexed_at, chunk_count }` on a completed, owned doc.
  - `404` if the document does not exist or is owned by another user.
  - `409` if `document.status != completed` (only completed docs are re-indexable).

```http
POST /api/v1/documents/6f2b.../reindex
Authorization: Bearer <token>

200 OK
{
  "id": "6f2b...",
  "indexed_at": "2026-07-04T18:22:11Z",
  "chunk_count": 42
}
```

- **UI:** the Project sidebar's Documents rail renders a `Fresh` / `Stale`
  badge on each `DocumentCard` (stale after 7 days without a re-index) and a
  `Re-index` item in the kebab menu that fires the endpoint, disables itself
  while the mutation is pending, and surfaces success/error via a sonner toast.
