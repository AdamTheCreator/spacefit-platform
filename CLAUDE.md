# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**Perigee** — an AI-driven commercial real estate workbench. Recently rebranded from "Spacefit." The core motion is conversational: the user talks to a specialist-routed agent that can analyze properties, surface tenant gaps, pull comps, and draft outreach. Dashboards and kanban boards exist, but the chat is the product.

## Repository shape

```
frontend/   React 19 + TS + Vite 7 + Tailwind v4 SPA
backend/    FastAPI + Python 3.11 + PostgreSQL 16
docker-compose.yml    local dev (db + backend + frontend)
render.yaml           Render blueprint (perigee-api on Starter, perigee-db on Free)
```

No workspace tooling. `npm` runs inside `frontend/`, `uv`/`pip` inside `backend/`.

## Common commands

### Frontend (`cd frontend`)

```
npm install
npm run dev      # vite dev server on :5173
npm run build    # tsc -b && vite build  (type-check + production bundle)
npm run lint     # eslint .
npm run preview  # preview the production bundle
```

There are **no frontend tests wired up.** `npm run build` doubles as the only type-check gate — treat a failing `tsc -b` as a blocker.

### Backend (`cd backend`)

```
uv pip install -e .                                   # or: pip install -e .
playwright install --with-deps chromium               # required once for scraping/imports
alembic upgrade head                                  # apply migrations (latest is 027)
alembic revision --autogenerate -m "description"      # new migration
uvicorn app.main:app --reload --port 8000             # dev server
pytest tests/                                         # run all tests
pytest tests/test_demographics.py::test_name -v       # single test
ruff check .                                          # lint (line-length 88, target py311)
mypy app                                              # strict type-check
```

### Full stack local dev

```
docker compose up --build                # everything in containers (preferred first-run)
```

The `backend` container runs `alembic upgrade head` on boot, so a fresh DB converges to latest schema automatically.

### Operational scripts (`cd backend/scripts`)

- `seed_admin.py` — create/promote an admin user from env vars.
- `seed_demo.py` — populate demo data.
- `byok_verify.py` — end-to-end BYOK verification helper. Given `PERIGEE_API` + `PERIGEE_TOKEN` env vars, snapshots `/ai-config/usage` before + after a user-triggered chat and reports a PASS/FAIL verdict on whether platform token counters stayed flat (the BYOK zero-platform-tokens guarantee).

## Architecture

### Frontend

- **Routing:** `react-router-dom` v7. Top-level routes are defined in `src/App.tsx`; each page is lazily imported. All protected routes are nested inside `<ProtectedRoute />` which reads from `authStore`. Public root `/` is the `LandingPage` (redirects to `/dashboard` when authenticated).
- **State:** Zustand stores in `src/stores/` for cross-cutting concerns (auth, chat session, connection status). React Query owns server state — avoid duplicating server data into Zustand. Query defaults are set in `main.tsx`: `refetchOnWindowFocus: false`, `staleTime: 5min`, `retry: 2` with exponential backoff. **Do not re-enable refetch-on-focus** — it caused a request storm every time users came back to Settings while the backend was cold-starting.
- **Layout:** `components/Layout/AppLayout.tsx` wraps every protected page. It owns the Perigee sidebar (WORKSPACE + STATES sections), the topbar, and the mobile-drawer behavior. Page components compose `<AppLayout><PageContent/></AppLayout>` rather than being routed through a parent layout element — intentional, gives per-page control over scroll containers.
- **Pages that exist today:** Dashboard, Chat (+ per-session), Search, Analytics, Insights, Workflow (Perigee-design kanban at `/workflow` — distinct from legacy `/pipeline`), Projects + ProjectDetail + ProjectChat, PropertyDetail (`/property/:id`), Contacts (Directory + CompanyDetail + ContactDetail), Customers (legacy), Outreach, Archive, Settings, Connections, Profile, Admin, Pricing, Onboarding, Login/Register/ResetPassword/VerifyEmail, Landing, AuthCallback.
- **Design system is monolithic:** `src/index.css` is a single ~1.4k-line file that holds the entire theme (Tailwind v4 `@theme` block, CSS variables for light/dark, and dozens of utility classes like `btn-industrial`, `card-industrial`, `input-industrial`, `nav-industrial`). The class names are **legacy from the Spacefit era and intentionally preserved** — components still reference them across the codebase. The Perigee rebrand was done by swapping the underlying tokens (colors, fonts, radii), not by renaming classes. Don't rename `-industrial` classes without a coordinated migration.
- **Fonts:** Sora (display/headings) + Inter (UI) + JetBrains Mono (data). Loaded via Google Fonts in `index.html`.
- **Mascots:** `public/mascots/*.webp` (the "goose crew": planner, engineer, welder, mechanic, carriers, launch, solar, planet). **Placement is rule-governed, not decorative**:
  - ✅ Onboarding tour steps, 404/empty states, sidebar upgrade card, Dashboard welcome hero, Insights cards, Workflow closing-column empty slot, Property detail thesis-note card.
  - ❌ Chat message bodies, data tables, analytics charts, dense kanban rows. The existing `DESIGN.md` is mandatory reading and calls this out as "quiet-first."
- **Pre-warm ping:** `main.tsx` fires a fire-and-forget `GET /health` on SPA mount to nudge a sleepy backend awake before the user navigates to an authenticated page. If you add a cheaper health endpoint, update the URL here.

### Backend

- **Entry point:** `app/main.py`. FastAPI app mounts REST routers under `/api/v1/*`, serves OAuth callbacks, and exposes an MCP (Model Context Protocol) endpoint aliased as `perigee_mcp`.
- **Database:** SQLAlchemy 2.0 async with `asyncpg`. Models live in `app/db/models/`. Migrations in `backend/alembic/versions/` follow numeric prefixes (001..027 as of the rebrand); there is one hash-named migration `5c7681bfc694` wedged between 004 and 005 due to a historical branch. **Never edit a committed migration** — fix forward with a new one (see `027_rebrand_plan_description_to_perigee.py` for the pattern).
- **Agents & LLM:** the chat orchestrator uses **specialist agents** behind a feature flag (introduced mid-project; see the `phase-3-specialist-agents` commits). All LLM tools route through the **MCP gateway** for audit logging + rate limiting — don't call Claude directly from new code, register a tool with the gateway.
- **BYOK (Bring Your Own Key):** users configure provider + key via `/api/v1/ai-config`. Providers supported: Anthropic, OpenAI, Google Gemini, DeepSeek, openai_compatible. Per-specialist model overrides stored as JSON in `user_ai_configs.specialist_models_json`. Key resolution runs through `app/services/user_llm.py::resolve_user_llm()` which returns a `ResolvedLLM { client, provider, model, is_byok, specialist_models }`. **Zero-platform-tokens guarantee:** when `is_byok=True`, the orchestrator routes through the user's client AND `app/services/guardrails.py` skips the classifier fallback (`_classify_with_haiku` honors `resolved_llm`) AND skips `record_token_usage` + `check_token_budget`. Any new code path that calls Claude/OpenAI must accept and honor a `resolved_llm` — otherwise it'll leak tokens to the platform key.
- **Email:** transactional mail via Resend (`RESEND_API_KEY`, `RESEND_FROM_EMAIL`). Outbound open/click tracking lives in `app/api/tracking.py` (pixel + link wrapping). Outreach campaigns are throttled in the sender worker.
- **Imports:** CoStar / Placer / SiteUSA ingest lives under `app/services/` and `connector_manifests/`. Playwright is used for authenticated scrapes; install browsers once with `playwright install --with-deps chromium` or the imports will hang.

## Auth flow (important gotcha)

Auth state is split across two localStorage keys:

1. `access_token` + `refresh_token` — raw JWTs read by the axios request interceptor.
2. `auth-storage` — zustand persist key holding `{ user, isAuthenticated }` for instant UI hydration.

**Both must be cleared together** whenever auth fails, or the user ping-pongs between `/dashboard` and the landing/login page:
- Axios interceptor wipes tokens → `window.location.href = '/login'`.
- `LoginPage` + `LandingPage` both read `isAuthenticated` from zustand. If `auth-storage` survives the token wipe, they immediately redirect to `/dashboard`.
- `/dashboard` fires `usePreferences` / `useChatSessions` → 401 (no token!) → interceptor → redirect → loop.

This is fixed in `src/lib/axios.ts` (both failure branches) and `src/hooks/useChat.ts` (WebSocket close code 4001) — all three spots now `localStorage.removeItem('auth-storage')` alongside the token wipe. Preserve this pattern in any new auth-failure handler.

## Design system rules (from `frontend/DESIGN.md`)

Treat `frontend/DESIGN.md` as canon for visual decisions. The summary:

- Use CSS variables (`--bg-primary`, `--accent`, `--radius-md`, etc.) from `index.css`. Don't hard-code hex colors in components.
- Keep data views integrated into the chat flow; avoid "boxed-in" dashboard chrome.
- No heavy borders, shadows, uppercase labels, or saturated colors unless they express a real state change.
- Dark mode is a full override via `.dark` / `[data-theme="dark"]`; test both when adding surfaces.

## Infrastructure caveats

- **render.yaml still references `spacefit-*` service names** (`spacefit-api`, `spacefit-db`, frontend service `spacefit`). The full rename lives on the unmerged branch `perigee/phase-4-infra` and is blocked on a coordinated DB dump/restore + GCP OAuth URI update. Do not casually merge a Render rename.
- **Plans:** `perigee-api` is on Starter ($7/mo, always-on, no cold starts). The database is still on Free (90-day expiry, limited resources). Bump the DB separately when it becomes a bottleneck.
- **`backend/spacefit.db`** is a leftover local SQLite file from early dev — `.gitignore` covers it going forward, but the committed file is orphaned. Do not write new code that targets SQLite; Postgres async is the supported path.
- **Domain:** `perigee.ai` is the canonical email domain (`sales@`, `noreply@`, `api.`). Any new copy should use it.
- **OAuth:** Google sign-in + Gmail (for Outreach) both require authorized redirect URIs registered in the GCP console. `render.yaml` owns the env-var mapping; the production client has been pre-configured with both spacefit-era and perigee-era callbacks during the rename transition.

## When adding a new page

1. Add a lazy import in `src/App.tsx` and a `<Route>` inside the `<ProtectedRoute />` block.
2. Add the nav entry to `WORKSPACE_NAV` or `STATES_NAV` in `AppLayout.tsx`. Include `matchPrefixes` if the page has sub-routes so the active-state dot tracks correctly.
3. Wrap the page component in `<AppLayout>…</AppLayout>` — it owns the sidebar + topbar.
4. For scrollable pages, wrap body content in `<div className="h-full overflow-y-auto">` — AppLayout's main region is `flex-1 overflow-hidden`, so pages without this can't scroll (a Settings-page bug caught in April 2026).
5. Reuse existing design-system classes (`btn-industrial-primary`, `card-industrial`, `input-industrial`). For tokens, use `var(--accent)`, `var(--bg-secondary)`, `var(--border-subtle)`, `var(--color-neutral-900)` (space navy), `var(--color-mist)` (mist blue), `var(--color-orbit)` (orbit blue).
6. For tiny charts reuse `components/Dashboard/MiniCharts.tsx` (`LineChart`, `BarChart`). For heavier viz use Recharts — a small shared chart-color palette lives in `components/Chat/MarkdownRenderer.tsx` (Perigee-aligned).
7. Handle loading + error states explicitly: when a section depends on a React Query fetch, use `if (isError && !data) → SectionError` rather than `if (isError)`. This keeps cached UI visible through transient errors instead of falling to the error card. See `pages/SettingsPage.tsx::AIModelSection` for the pattern.
