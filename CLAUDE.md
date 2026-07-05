# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**Space Goose** (domain `spacegoose.ai`) — an AI-driven commercial real estate workbench. Rename history: "Spacefit" → "Perigee" → "Space Goose." Most brand-owned strings, service names, and domains have been migrated; a few legacy touchpoints (e.g. the orphaned `backend/spacefit.db` SQLite file, the `-industrial` CSS class names) are intentionally preserved and called out below. The core motion is conversational: the user talks to a specialist-routed agent that can analyze properties, surface tenant gaps, pull comps, and draft outreach. Dashboards and kanban boards exist, but the chat is the product.

## Repository shape

```
frontend/   React 19 + TS + Vite 7 + Tailwind v4 SPA
backend/    FastAPI + Python 3.11 + PostgreSQL 16
docker-compose.yml    local dev (db + backend + frontend)
render.yaml           Render blueprint (spacegoose-api on Starter, spacegoose-db on Free)
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
alembic upgrade head                                  # apply migrations (latest is 038)
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
- `byok_verify.py` — end-to-end BYOK verification helper. Given `SPACEGOOSE_API` + `SPACEGOOSE_TOKEN` env vars, snapshots `/ai-config/usage` before + after a user-triggered chat and reports a PASS/FAIL verdict on whether platform token counters stayed flat (the BYOK zero-platform-tokens guarantee).

### Continuous integration (`.github/workflows/ci.yml`)

CI runs on every PR into `master` and on pushes to `master`, two jobs:

- **`frontend`** — `npm ci` + `npm run build` (tsc -b + vite). **Hard gate.**
- **`backend`** — `pip install -e ".[dev]"` against a **Postgres 16 service** + `alembic upgrade head` (mirrors the container boot), then `pytest tests/`. **Hard gate.** Only `DATABASE_URL` is overridden to the service; every other setting uses its `app/core/config.py` default. The one PG-only test (`test_document_search`) runs for real here.
- **`eslint` and `ruff` are informational** (`continue-on-error: true`) — they each have a large pre-existing baseline (~34 / ~1.3k), so a blocking `check .` would be red on every PR. Hold the **"zero *new* violations"** bar when you touch a file; flip `continue-on-error` off once the backlogs are cleared (or move to a line-scoped reporter).

## Architecture

### Frontend

- **Routing:** `react-router-dom` v7. Top-level routes are defined in `src/App.tsx`; each page is lazily imported. All protected routes are nested inside `<ProtectedRoute />` which reads from `authStore`. Public root `/` is the `LandingPage` (redirects to `/dashboard` when authenticated).
- **State:** Zustand stores in `src/stores/` for cross-cutting concerns (auth, chat session, connection status). React Query owns server state — avoid duplicating server data into Zustand. Query defaults are set in `main.tsx`: `refetchOnWindowFocus: false`, `staleTime: 5min`, `retry: 2` with exponential backoff. **Do not re-enable refetch-on-focus** — it caused a request storm every time users came back to Settings while the backend was cold-starting.
- **Layout:** `components/Layout/AppLayout.tsx` wraps every protected page. It owns the Space Goose sidebar (WORKSPACE + STATES sections), the topbar, and the mobile-drawer behavior. Page components compose `<AppLayout><PageContent/></AppLayout>` rather than being routed through a parent layout element — intentional, gives per-page control over scroll containers.
- **Sidebar conventions:**
  - The legacy duplicate `Projects` nav entry and standalone `Account` section were removed; account-related actions (Settings, Admin) live in the avatar dropdown.
  - The `Demo` link is dev-only (gated on `import.meta.env.DEV`), so production users never see it.
  - The `History` section header only renders when there is at least one chat session — no empty-state "History" label sitting alone.
  - When you add a new admin-only entry, put it in the avatar dropdown (not the main nav). The dropdown's `focusedIndex` shifts based on whether `is_admin` is true; preserve that pattern.
  - **Collapsible rails:** both the left nav and the project right rail support an icon-only collapsed mode. State is persisted in `localStorage` via the shared `hooks/useCollapsedPreference.ts` hook (keys `spacegoose:sidebar:collapsed` and `spacegoose:projectsidebar:collapsed`). The left rail collapses to `w-16` (icon-only `SidebarLink`s with `title` tooltips, demo section hidden, history hidden, upgrade card → circular mascot button) and toggles via the footer button or `Cmd/Ctrl+\`. The right rail collapses to `w-14` with quick-launch icons (Instructions, Documents + count badge, Data Imports) — clicking any icon expands the rail. Mobile keeps the existing full-drawer behavior; `isCollapsed` is gated on `!isMobile`.
- **Pages that exist today:** Dashboard, Chat (+ per-session), Search, Analytics, Insights, Workflow (Space Goose-design kanban at `/workflow` — distinct from legacy `/pipeline`), Projects + ProjectDetail + ProjectChat, PropertyDetail (`/property/:id`), Contacts (Directory + CompanyDetail + ContactDetail), Customers (legacy), Outreach, Archive, Settings, Connections, Profile, Admin, Pricing, Welcome (lightweight onboarding gate), Login/Register/ResetPassword/VerifyEmail, Landing, AuthCallback. The legacy `OnboardingPage` 4-step wizard was removed in favor of a `WelcomePage` + dashboard `SetupCards` (see "Onboarding" below).
- **Design system is monolithic:** `src/index.css` is a single ~1.4k-line file that holds the entire theme (Tailwind v4 `@theme` block, CSS variables for light/dark, and dozens of utility classes like `btn-industrial`, `card-industrial`, `input-industrial`, `nav-industrial`). The class names are **legacy from the Spacefit era and intentionally preserved** — components still reference them across the codebase. The Space Goose rebrand was done by swapping the underlying tokens (colors, fonts, radii), not by renaming classes. Don't rename `-industrial` classes without a coordinated migration.
- **Fonts:** Sora (display/headings) + Inter (UI) + JetBrains Mono (data). Loaded via Google Fonts in `index.html`.
- **Mascots:** `public/mascots/*.webp` (the "goose crew": planner, engineer, welder, mechanic, carriers, launch, solar, planet). **Placement is rule-governed, not decorative**:
  - ✅ Onboarding tour steps, 404/empty states, sidebar upgrade card, Dashboard welcome hero, Insights cards, Workflow closing-column empty slot, Property detail thesis-note card.
  - ❌ Chat message bodies, data tables, analytics charts, dense kanban rows. The existing `DESIGN.md` is mandatory reading and calls this out as "quiet-first."
- **Pre-warm ping:** `main.tsx` fires a fire-and-forget `GET /health` on SPA mount to nudge a sleepy backend awake before the user navigates to an authenticated page. If you add a cheaper health endpoint, update the URL here.

### Backend

- **Entry point:** `app/main.py`. FastAPI app mounts REST routers under `/api/v1/*`, serves OAuth callbacks, and exposes an MCP (Model Context Protocol) endpoint aliased as `spacegoose_mcp`.
- **Database:** SQLAlchemy 2.0 async with `asyncpg`. Models live in `app/db/models/`. Migrations in `backend/alembic/versions/` follow numeric prefixes (001..038 currently); there is one hash-named migration `5c7681bfc694` wedged between 004 and 005 due to a historical branch. **Never edit a committed migration** — fix forward with a new one (see `030_rebrand_perigee_to_spacegoose.py` or `031_foundry_pricing_tiers.py` for the pattern).
- **Enum columns are NOT native Postgres ENUMs.** Migration 005 created `subscription_plans.tier`, `subscriptions.status`, `usage_records.usage_type` etc. as plain `VARCHAR`. The SQLAlchemy models must therefore declare these columns with `Enum(MyEnum, native_enum=False, length=N, values_callable=lambda e: [v.value for v in e])` — otherwise asyncpg tries to cast bind parameters to a nonexistent PG type (`type "subscriptiontier" does not exist`) and every query by enum value 500s. Same rule applies to the new `sales_leads.status`. When adding a new enum-backed column, either (a) create a real PG ENUM in the migration AND drop `native_enum=False`, or (b) keep VARCHAR and keep the `native_enum=False` declaration consistent.
- **Agents & LLM:** the chat orchestrator uses **specialist agents** behind a feature flag (introduced mid-project; see the `phase-3-specialist-agents` commits). All LLM tools route through the **MCP gateway** for audit logging + rate limiting — don't call Claude directly from new code, register a tool with the gateway.
- **BYOK (Bring Your Own Key):** users configure provider + key via `/api/v1/ai-config`. Providers supported: Anthropic, OpenAI, Google Gemini, DeepSeek, openai_compatible. Per-specialist model overrides stored as JSON in `user_ai_configs.specialist_models_json`. Key resolution runs through `app/services/user_llm.py::resolve_user_llm()` which returns a `ResolvedLLM { client, provider, model, is_byok, specialist_models }`. **Zero-platform-tokens guarantee:** when `is_byok=True`, the orchestrator routes through the user's client AND `app/services/guardrails.py` skips the classifier fallback (`_classify_with_haiku` honors `resolved_llm`) AND skips `record_token_usage` + `check_token_budget`. Any new code path that calls Claude/OpenAI must accept and honor a `resolved_llm` — otherwise it'll leak tokens to the platform key.
- **Subscriptions / pricing (Foundry-style tiers):** `SubscriptionTier` carries `free` / `starter` / `pro` / `max` / `enterprise` plus the legacy `individual` value (retained so historical `subscriptions.plan_id` rows still resolve through the enum coercion — migration 031 marks the individual plan inactive and backfills its subscribers onto `pro`). Plan rows live in `subscription_plans`; each paid tier has `price_monthly` + `price_yearly` (cents, full annual total at 20% off monthly × 12) and matching `stripe_price_id` / `stripe_price_id_yearly` columns. **`app/services/subscription.py::ensure_default_plans` is the source of truth for plan specs** — it upserts every tier on app boot from the spec dict, so changes to limits/prices/feature flags should be made there rather than via ad-hoc SQL. Stripe price IDs are read from per-tier settings (`stripe_starter_monthly_price_id`, `stripe_starter_yearly_price_id`, `stripe_pro_*`, `stripe_max_*`), all defaulting to empty so dev can boot without Stripe configured. The pricing API surfaces `is_purchasable` (true when at least one Stripe price ID exists) so the frontend hides checkout buttons for unconfigured tiers instead of routing users to a guaranteed 4xx. `POST /billing/checkout` takes an `interval: "monthly" | "yearly"` field; enterprise is quote-based and explicitly rejected from checkout.
- **BYOK-aware free tier:** the free plan's `chat_sessions_per_month` is 10 by default, but `SubscriptionService.effective_chat_session_limit(plan, has_valid_byok)` lifts it to 50 when the user has a validated BYOK key (`UserAIConfig.provider != "platform_default" AND is_key_valid AND api_key_encrypted` populated). The lift is applied inside `check_can_use` for `UsageType.CHAT_SESSION` only — paid tiers and other usage types are untouched. Any new chat-cap check should call `check_can_use` rather than reading `plan.chat_sessions_per_month` directly, or the BYOK lift gets bypassed.
- **Sales leads (enterprise contact form):** `POST /api/v1/sales/leads` is a **public** endpoint (no auth required) backing the pricing-page "Talk to sales" modal. It writes a `sales_leads` row (email + optional company / team_size / current_tools / use_case) and fires a Resend notification to `SALES_LEAD_NOTIFY_TO` (comma-separated; falls back to `RESEND_FROM_EMAIL`). Rate-limited in-process by IP via a sliding-window deque in `app/api/sales.py::_IPRateLimiter` (`SALES_LEAD_RATE_LIMIT` per `SALES_LEAD_RATE_WINDOW_SECONDS`, defaults 3 / 600s). The limiter is per-worker memory — fine for single-uvicorn dev; **swap for Redis when we scale horizontally**, otherwise each worker enforces its own quota. Authenticated users automatically have `user_id` populated on the lead row.
- **Email:** transactional mail via Resend (`RESEND_API_KEY`, `RESEND_FROM_EMAIL`). Outbound open/click tracking lives in `app/api/tracking.py` (pixel + link wrapping). Outreach campaigns are throttled in the sender worker.
- **Imports:** CoStar / Placer / SiteUSA ingest lives under `app/services/` and `connector_manifests/`. Playwright is used for authenticated scrapes; install browsers once with `playwright install --with-deps chromium` or the imports will hang.

## Onboarding

The old 4-step `OnboardingPage` wizard (3 of the 4 steps were non-functional) was deleted. The current flow is:

1. **`/welcome`** — `pages/WelcomePage.tsx`. Lightweight gate shown once after registration. `ProtectedRoute` redirects users with `onboarding_completed = false` here; `RegisterPage` also navigates here on success. A single "Continue to dashboard" CTA marks onboarding complete and routes to `/dashboard`.
2. **Dashboard setup cards** — `components/Dashboard/SetupCards.tsx` driven by `hooks/useSetupCards.ts`. Cards (connect Gmail, add AI key, upload first document, etc.) derive from live hooks (subscription, connectors, projects). Each card is dismissible via localStorage (`spacegoose:setup-cards:dismissed`); dismissals are scoped per-card so users can hide cards they've actively chosen to skip without losing the rest.

Backend onboarding state lives in `onboarding_progress`. `app/api/onboarding.py` uses tz-aware UTC datetimes (`datetime.now(UTC)`) and JSON-encodes the `completed_steps` / `skipped_steps` text columns on write, JSON-decoding on read. Don't revert to `datetime.utcnow()` or to raw comma-separated strings — the migration left the columns as `TEXT` and we rely on JSON parsing.

## Dashboard

`pages/DashboardPage.tsx` is the post-login landing page. It's deliberately oriented around **outreach triage as the primary action** rather than being an analytics dashboard. The page renders four sections in this order:

1. **Hero** — date eyebrow + greeting + a one-line summary computed from real campaign data (e.g. "3 replies waiting · 5 follow-ups due" or, when both are zero, "All caught up — nothing waiting on you."). Single CTA "Review outreach queue" → `/outreach`.
2. **Triage queue** (`TriagePanel`) — follow-ups derived from `/outreach/campaigns`, and replies from `/outreach/threads` (real replied-recipient rows, since Phase 3b). Replies are sorted ahead of follow-ups because a human reply is the freshest signal. Capped at 8 rows with a "See all →" overflow when more exist. **No mock rows ever** — the previous `pe-1` Harper & Ninth diligence row and the demo-data staleness row were removed.
3. **Active projects** (`ActiveProjectsRail`) — top 6 unarchived projects by `updated_at`, each with a real meta strip (`{docs} docs · {chats} chats · updated {relativeTime}`) and a derived stage badge from `getProjectStage(project, campaigns)`:
   - `Drafting`     — 0 documents AND 0 sessions
   - `Researching`  — has documents or sessions, no linked campaign
   - `In outreach`  — a campaign's `property_name` matches `project.name` (case-insensitive, trimmed) — this is the cheapest match we can make until the campaign model carries a `project_id` foreign key. If you add that FK, switch the match to ID-based here.
   - `Stalled`      — `updated_at` > 30 days ago (takes precedence over the above)
   The old `pct = docs * 14 + sessions * 6` progress bar was removed; it was a vibe-number that looked like real progress.
4. **Pipeline placeholder** (`PipelinePlaceholder`) — quiet dashed-border card explaining that deal-stage tracking will land here once backend supports it. Includes a "Preview workflow board →" link to the existing `/workflow` route. **The previous `PIPELINE_STAGES` hardcoded funnel (3/2/2/1/1 with "+1 wk" deltas) was removed.** If you wire up a real pipeline-summary endpoint, replace this component with a live strip — do not bring back the static array.
5. **Setup cards** (`components/Dashboard/SetupCards.tsx`) — moved to the bottom because they're a one-time-per-account concern, not day-to-day chrome. Untouched by the consolidation.

**Dashboard rule:** every number, count, badge, and row on this page must trace to a real API response. If the data doesn't exist yet, render a soft placeholder (like `PipelinePlaceholder`) rather than seeding mock values — the previous version had hardcoded pipeline counts, a fake calendar event, and demo-data tile counts living next to real numbers, and it made the whole page feel fake. The four "At a glance" tiles (`GlanceTiles` / `glance` useMemo) were also removed because they duplicated the triage list they sat next to.

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

- **render.yaml now matches the Space Goose brand** (`spacegoose-api`, `spacegoose-db`, frontend service `spacegoose`). Deploying the rename to an existing Render account is **not automatic** — the blueprint will provision a new database named `spacegoose-db` alongside the old `spacefit-db` rather than renaming it. Cutover requires: (a) `pg_dump` the old `spacefit-db` and restore into `spacegoose-db` before promoting the new `spacegoose-api`; (b) GCP OAuth console: add the new redirect URIs `https://spacegoose-api.onrender.com/api/v1/auth/{google,gmail}/callback` and keep the old `spacefit-api.onrender.com` ones until the DNS flip is verified; (c) Resend: verify the `spacegoose.ai` sender domain before `RESEND_FROM_EMAIL=noreply@spacegoose.ai` starts actually sending.
- **Plans:** `spacegoose-api` is on Starter ($7/mo, always-on, no cold starts). The database is still on Free (90-day expiry, limited resources). Bump the DB separately when it becomes a bottleneck.
- **`backend/spacefit.db`** is a leftover local SQLite file from the original Spacefit era — `.gitignore` covers it going forward, but the committed file is orphaned. Do not write new code that targets SQLite; Postgres async is the supported path.
- **Local Postgres for dev:** install via Homebrew (`brew install postgresql@16 && brew services start postgresql@16`), create the role + DB (`createuser -s spacegoose && createdb -O spacegoose spacegoose`), then run `alembic upgrade head`. Backend reads `DATABASE_URL` from `backend/.env`; the canonical dev value is `postgresql+asyncpg://spacegoose:spacegoose_dev_password@localhost:5432/spacegoose` plus a `SECRET_KEY` and `ENCRYPTION_MASTER_KEY`. The seeded admin used during development is `goose@spacegoose.com` / `goosygoo`.
- **Pricing env vars (Render + local `.env`):** `STRIPE_STARTER_MONTHLY_PRICE_ID`, `STRIPE_STARTER_YEARLY_PRICE_ID`, `STRIPE_PRO_MONTHLY_PRICE_ID`, `STRIPE_PRO_YEARLY_PRICE_ID`, `STRIPE_MAX_MONTHLY_PRICE_ID`, `STRIPE_MAX_YEARLY_PRICE_ID`. All optional; tiers without a configured price ID surface `is_purchasable: false` and the pricing UI hides their checkout button. Sales-lead delivery uses `SALES_LEAD_NOTIFY_TO` (comma-separated emails), with `SALES_LEAD_RATE_LIMIT` / `SALES_LEAD_RATE_WINDOW_SECONDS` controlling the per-IP submission cap.
- **Domain:** `spacegoose.ai` is the canonical email domain (`sales@`, `noreply@`, `api.`). Any new copy should use it. The legacy `perigee.ai` and `spacefit.app` domains are no longer referenced in code; the CORS allowlist only accepts `spacegoose.ai` hosts.
- **OAuth:** Google sign-in + Gmail (for Outreach) both require authorized redirect URIs registered in the GCP console. `render.yaml` owns the env-var mapping; the production client must have the `spacegoose-api.onrender.com` callbacks added before the new service goes live.

## Chat streaming protocol

The chat WebSocket emits a small set of streaming events when the orchestrator is replying token-by-token:

- `message_start` — `{msg_id, role: "agent", agent_type: "orchestrator"}` opens a new streaming bubble.
- `text_delta` — `{msg_id, delta}` is appended to the in-flight bubble's content. Many of these per turn.
- `tool_use_start` — `{msg_id, tool_id, tool_name}` announces that Claude wants to invoke a tool (frontend can render an inline "calling …" chip).
- `message_end` — `{msg_id, content, stop_reason, tool_calls, error?}` finalizes the turn. `content` is the full accumulated text; `stop_reason` includes the standard `end_turn`/`tool_use` plus our own `stream_error`/`cancelled`/`max_chunks`.

The legacy `message` event still fires for system messages, errors, history hydration, and the user echo so the protocol is fully backward compatible. Frontend state lives in `useChat.handleWebSocketMessage`; the streaming bubble is keyed by `msg_id` in `streamingMessageIdsRef`, and `chatStore.appendToMessage(id, delta)` performs the actual concat.

Cancellation: the client sends `{"type": "cancel"}` and the server cancels the in-flight `asyncio.Task` wrapping `_stream_orchestrator_to_ws`. Streaming is gated by `settings.streaming_enabled` (env: `STREAMING_ENABLED`, default true); when false, the helper falls back to `get_orchestrator_response` and emits no streaming events. Runaway streams are capped at `settings.streaming_max_chunks` (default 4000).

## Tool reliability envelope

Every MCP tool runs through `app.mcp.reliability.call_with_reliability`, which wraps the call in three layers:

1. **Per-tool timeout** from `TOOL_TIMEOUTS` (default 8s, overrides in `reliability.py`).
2. **Circuit breaker** (`ToolCircuitBreaker`) — trips OPEN when 5+ failures land in a 60s sliding window; stays open for 30s; enters HALF_OPEN for a single probe.
3. **Retry policy** — up to 2 attempts with exponential backoff + jitter; auth-class errors (`upstream_4xx`) never retry.

Failures surface as `ToolError(kind, user_message, detail, elapsed_ms)`. The gateway emits a sentinel string `[TOOL_ERROR kind=…] user_message` so `_build_orchestrator_request` can wrap it as `### tool_name [FAILED: kind]` in the synthesis prompt. Claude then explains the unavailability to the user instead of pretending the tool worked. Frontend renders the new `WorkflowStepStatus` values (`timed_out`, `circuit_open`) with distinct chips.

The circuit breaker is in-memory + per-process; swap to Redis when we add background workers.

## Specialist agent loop

The modern `/ws` chat endpoint routes through specialist agents when `settings.enable_specialist_routing` is true (default). **The user only ever sees a single "Space Goose Assistant" bubble per turn** — specialists run silently under the hood, mainstream-assistant style (ChatGPT / Claude / Gemini). Orchestration is an implementation detail; the progress strip is the only surface that hints at it.

Flow per turn:

1. **Clarification gate** — `app/services/orchestrator.py::needs_clarification` runs first: a tiny BYOK-aware LLM triage call (max_tokens=10, READY/CLARIFY). Vague input (bare "Analyze property" with no address, greetings, "help") returns CLARIFY, and `_run_specialist_routing_turn` skips specialist routing entirely — no `workflow_init`, no fan-out. The orchestrator streams one clarifying question and that's the whole turn. Any LLM error defaults to READY so a flaky triage call never blocks a real request.
2. **Plan** — `plan_workflow` asks a small LLM to return a comma-separated list drawn from the keys in `app/agents/specialists/registry.py::SPECIALIST_REGISTRY` (`scout`, `analyst`, `matchmaker`, …). Parse failures and LLM errors both fall back to `["scout"]` so a single specialist always runs.
3. **Workflow init** — the WS emits a `workflow_init` event with one step per planned specialist so the frontend's `AgentActivityPanel` can render the progress strip and highlight the active node. This is the ONLY user-visible signal that multiple agents are working.
4. **Silent specialist streaming** — `_stream_specialist_to_ws` (in `app/api/chat.py`) is called with `stream_to_client=False`. It runs `call_specialist_stream` for each name in order (carrying prior specialists' outputs as assistant context), executes their tool calls, buffers their content — but emits **no** `message_start` / `text_delta` / `message_end` / `tool_use_start` frames to the client. Only `workflow_update` running/completed events fire.
5. **Always synthesize** — after all specialists finish, the orchestrator ALWAYS runs a final streaming synthesis pass through `_stream_orchestrator_to_ws`, even for single-specialist plans. This is the ONLY user-facing bubble. Per-specialist content is treated as intermediate work product and is NOT persisted to the transcript; only the final orchestrator synthesis is `save_message_to_db`'d.
6. **Fallback** — any exception inside the routing branch falls through to the legacy monolithic `_stream_orchestrator_to_ws`, so a bad plan or a flaky specialist never breaks the chat surface.

**Cost note:** always-synthesize adds one orchestrator call per delegated turn, and the clarification gate adds one tiny call per turn — but the gate short-circuits the whole specialist fan-out for vague inputs (net neutral or cheaper for the common starter-card flow).

**Frontend starter cards** (`components/Chat/ChatContainer.tsx`) don't send the bare card title anymore. Clicking "Analyze property" prefills the composer with `"Analyze property: "` and focuses it (via `draft` + `draftNonce` props on `ChatInput`), forcing the user to add the address/tenant/detail before sending. This is the frontend half of the two-layer validation gate the backend clarification check completes.

Per-specialist model overrides come from `ResolvedLLM.specialist_models[name]` (BYOK setting); `_build_specialist_request` picks the override first, then the resolved default. Tools are filtered per specialist via `SPECIALIST_REGISTRY[name].allowed_tools`. When you add a specialist:

1. Register it in `SPECIALIST_REGISTRY` with `system_prompt`, `allowed_tools`, and a tier hint.
2. Add the literal name to `AgentType` in both `backend/app/models/chat.py` and `frontend/src/types/chat.ts` (plus the `AGENTS` map for the human-readable label — this only surfaces in the progress strip now, not in message bubbles).
3. Extend `_SPECIALIST_TO_AGENT_TYPE` in `app/api/chat.py` — the test `test_specialist_agent_type_map_is_complete` enforces this so a missing entry fails CI before it ships.
4. Add an SVG icon + color entry + `idle` initial state in `frontend/src/components/Chat/AgentActivityPanel.tsx` (all three `Record<AgentType, …>` maps must stay complete or `tsc` fails).

**Do not surface specialist content as its own chat bubble.** If you need a genuinely multi-persona experience (which we deliberately do not have), do it by extending the progress strip, not by re-enabling `stream_to_client=True` on `_stream_specialist_to_ws`. The single-voice contract is enforced by `tests/test_specialist_routing.py` — any change that starts persisting per-specialist rows or emitting specialist `message_end` frames will break those tests.

## Memory + personalization

User-level memory has two layers:

- **Structured memory** (`user_memory` table, since migration 014) — JSONB blobs for analyzed properties, book-of-business summary, inferred preferences. Surfaced via `app/api/memory.py` and assembled by `app/services/memory_service.py::get_context_block`.
- **Personal facts** (`user_facts` table, migration 033) — free-form sentences the AI infers about the user, with explicit approval before they get injected into the system prompt.

Lifecycle: `pending` → user approves → `approved` (eligible for prompt injection) OR user rejects → `rejected`. Approved facts can be archived later (`archived`). The `app/db/models/user_fact.py::UserFact` model carries `text`, `category` (`deal_prefs` / `geography` / `business_model` / `personal` / `other`), `confidence`, source linkage, and `last_used_at` for the rolling window.

Extraction: `app/services/fact_extractor.py::extract_facts_from_turn` fires after each turn (called from `_extract_and_notify_facts` in `app/api/chat.py`) and:

- Asks Haiku (or the user's BYOK model, with 200 max_tokens) to return a strict JSON list of up to 3 facts.
- Tolerates markdown code fences + prose around the JSON; bad payloads degrade to `[]`.
- Dedupes by Jaccard similarity ≥ 0.85 against existing `pending` + `approved` rows so the same fact doesn't get re-surfaced every turn.
- Persists candidates as `status="pending"`. Always fire-and-forget — never block the streaming response.

UI surface: `frontend/src/components/Memory/MemoryFactsPanel.tsx` renders approve/reject/archive controls; `frontend/src/hooks/useUserFacts.ts` owns the React Query hooks (`useUserFacts`, `useApproveFact`, `useRejectFact`, `useArchiveFact`). The Settings page shows two panels — "Pending facts to review" and "Approved facts" — inside the existing `MemorySection`. The chat WS emits a `fact_candidates` event after each turn that yields new pending rows; `useChat` invalidates the `['userFacts']` query cache so the sidebar refreshes live.

Prompt injection: `MemoryService.get_context_block` appends up to 10 approved facts ordered by `last_used_at DESC NULLS LAST`, then `approved_at DESC`, under a `## What you should remember about me` heading. It bumps `last_used_at` on every injected fact so the rolling window stays fresh as the conversation evolves. The block is returned even when structured memory is empty if facts exist (so a brand-new user who only has facts still gets personalization).

REST endpoints (under `/api/v1/users/me/memory`):

- `GET /facts?status_filter=pending|approved|rejected|archived` — defaults to everything except archived.
- `POST /facts/{id}/approve` — sets status to approved + stamps `approved_at`.
- `POST /facts/{id}/reject` — sets status to rejected (excluded from future dedupe-by-text-equality but Jaccard still suppresses near-rephrases on re-extraction).
- `DELETE /facts/{id}` — archives (soft delete; `204 No Content`).

When you add a new extraction signal (e.g. extracting from outreach replies, not just chat turns), reuse `extract_facts_from_turn` so the dedupe + cap + redaction logic stays in one place. The Jaccard threshold and `_MAX_FACTS_PER_TURN` are constants at the top of `fact_extractor.py` — tune there.

## Project document Q&A (chunking + tsvector search)

Project chats (`/projects/{id}/chat/{session}`) can now answer "what does the OM say about the loan covenant?" with actual quotes. Before Initiative 5 the chat only saw the parser's structured `extracted_data` summary; now every successfully-parsed document gets sliced into searchable chunks.

Pipeline (per document):

1. **Parser commits** in `app/api/documents.py::_process_document` (sets `status=COMPLETED` and stores `extracted_data`).
2. **Chunker runs immediately after** as a best-effort step inside the same task. A chunker failure rolls back only the chunk attempt; the parse stays committed.
3. **`document_chunks` rows** carry the slice text, page number, chunk index, denormalized `user_id`/`project_id` (so the auth + scope filter on the search tool is a single indexed lookup), and a `GENERATED ALWAYS AS to_tsvector('english', text) STORED` column for full-text search. There's also a `BYTEA embedding` placeholder — when we switch to pgvector, alter that column to `vector(N)` without changing anything else.

`app/services/document_chunker.py` is the chunker:

- `extract_raw_text(path, mime)` → `[(page_number, text), ...]`. PDFs via `pypdf` (declared in `pyproject.toml`); plain text / markdown / json read verbatim. Returns `[]` on any failure — never raises.
- `chunk_text(pages, target_tokens=800, overlap=100)` → token-aware sliding window using `len(text)//4` as the tokenizer-free heuristic. **Chunks never span page boundaries** so citations are unambiguous. Hard cap: `MAX_CHUNKS_PER_DOCUMENT = 600` per doc.
- `index_document(db, document_id)` wipes old chunks for the doc, persists new ones, commits. Idempotent — re-running replaces.

`app/services/document_search.py` is the retrieval primitive:

- `search_document_chunks(db, query, project_id, user_id, document_id?, limit?)` returns ranked `SearchHit` rows. Uses `func.plainto_tsquery` + `func.ts_rank`; hard limit clamp at 15. **Always filtered by `user_id`** — that's the auth boundary, the gateway shouldn't be the only line of defense.
- `format_hits_for_chat(hits)` renders results as a markdown block with `[source:<doc_id>:<page>]` citation tags. The chat surface should promote those into clickable chips.

`app/mcp/server.py` exposes the tool as `document_search(query, project_id, document_id="", limit=5)` under the standard gateway envelope (rate limiting, audit log, circuit breaker). Listed in `SPACEGOOSE_TOOLS` and added to `scout` + `analyst` specialists' `allowed_tools`.

Prompt rendering: `format_project_context_block` now appends a "Document search" instruction block with the hard-coded `project_id` — but only when at least one of the project's documents has indexed chunks. Without that gate the LLM would call the tool and always get "no matches", which is worse than not knowing the tool exists.

When you add a new document type or extend the chunker:

1. Add the MIME / extension handling inside `extract_raw_text`.
2. Make sure `MIN_CHUNK_CHARS` / `MAX_CHUNKS_PER_DOCUMENT` still make sense for the new format.
3. Backfill existing documents with `python -m scripts.reindex_documents` (per-user or per-doc flags supported; the script opens a fresh session per doc so a single failure doesn't poison the run).
4. The smoke test at `scripts/smoke_project_chat.py` is the fastest way to verify a chunker change end-to-end without booting the chat UI.

Known gotcha: the `Computed(persisted=True)` declaration on `DocumentChunk.search_vector` works at runtime but `alembic revision --autogenerate` will think the column drifted. Delete that hunk from any autogenerated migration — the column was created by migration 034 as a Postgres generated column and isn't ORM-managed.

## Project right rail

The right-hand panel on `/projects/:id` and `/projects/:id/chat/:sessionId` is `components/Projects/ProjectSidebar.tsx`. It accepts an optional `collapsed` + `onToggleCollapsed` pair so the host page controls width (`w-80` ↔ `w-14`) — see `pages/ProjectChatPage.tsx` and `pages/ProjectDetailPage.tsx`, which both read the same `spacegoose:projectsidebar:collapsed` localStorage key via `useCollapsedPreference`.

Data Imports moved off the three large stacked `ImportUploadCard`s and onto a single collapsible `components/Imports/DataImportsSection.tsx`:

- One dropzone, one segmented source picker (CoStar / Placer.ai / SiteUSA) at the top. PDFs auto-route to Placer; CSV/TSV default to CoStar unless the user picks SiteUSA.
- Upload + polling logic lives in `hooks/useImportUpload.ts` (`upload(file, source, onComplete?)`) so the same primitive is reusable outside the project sidebar. It keeps per-source state (`idle` / `uploading` / `parsing` / `ready` / `error`), polls `/imports/{id}` every 2s for up to 120s, and reports errors via the returned state map rather than throwing.
- A small disclosure header shows an active-job count badge so the user sees parsing progress even when the section is collapsed.
- The old `components/Imports/ImportUploadCard.tsx` is no longer referenced — leave it alone unless you're consolidating; it's a candidate for removal in a later cleanup.

When you add a new import source: extend `ImportSource` in `hooks/useImportUpload.ts`, add a `SOURCE_META` entry in `DataImportsSection.tsx`, and (if the file-extension heuristic in `detectImportSource` can't disambiguate) make sure the segmented picker covers the new format. The backend `/imports/{source}` endpoint contract is unchanged.

## When adding a new page

1. Add a lazy import in `src/App.tsx` and a `<Route>` inside the `<ProtectedRoute />` block.
2. Add the nav entry to `WORKSPACE_NAV` or `STATES_NAV` in `AppLayout.tsx`. Include `matchPrefixes` if the page has sub-routes so the active-state dot tracks correctly.
3. Wrap the page component in `<AppLayout>…</AppLayout>` — it owns the sidebar + topbar.
4. For scrollable pages, wrap body content in `<div className="h-full overflow-y-auto">` — AppLayout's main region is `flex-1 overflow-hidden`, so pages without this can't scroll (a Settings-page bug caught in April 2026).
5. Reuse existing design-system classes (`btn-industrial-primary`, `card-industrial`, `input-industrial`). For tokens, use `var(--accent)`, `var(--bg-secondary)`, `var(--border-subtle)`, `var(--color-neutral-900)` (space navy), `var(--color-mist)` (mist blue), `var(--color-orbit)` (orbit blue).
6. For tiny charts reuse `components/Dashboard/MiniCharts.tsx` (`LineChart`, `BarChart`). For heavier viz use Recharts — a small shared chart-color palette lives in `components/Chat/MarkdownRenderer.tsx` (Space Goose-aligned).
7. Handle loading + error states explicitly: when a section depends on a React Query fetch, use `if (isError && !data) → SectionError` rather than `if (isError)`. This keeps cached UI visible through transient errors instead of falling to the error card. See `pages/SettingsPage.tsx::AIModelSection` for the pattern.

## Built since the initial roadmap (Phases 1–5)

The post-V1 feature build. `ROADMAP.md` tracks status + what's still open. Key subsystems, files, and gotchas:

- **Contacts directory (real, replaced the mock).** Tables `companies` / `contacts` / `contact_interactions` (`app/db/models/contact.py`, migration `035`); API `app/api/contacts.py` exposes `/api/v1/companies` + `/api/v1/contacts` (CRUD, search, interaction timeline, CSV/XLSX bulk import at `/contacts/import` — modeled on the customers importer). Frontend hooks in `hooks/useContacts.ts` (timestamp→relative-days adapter); `pages/contacts/data.ts` is now **types + pure formatters only — no mock rows**. `Company` carries the client **buy-box**: explicit `sector`/`sf_min`/`sf_max`/`target_markets`/`is_expanding` columns **plus** a flexible `criteria` JSON (`asset_types`/`budget_min`/`budget_max`/`cap_rate_max`/`geographies`/`free_form`). `user_id` is denormalized on every row. (Legacy `customers` is now redundant — slated to migrate onto this.)

- **Outreach, end-to-end.** Campaign send (`app/services/email_blast.py::send_email`) picks a transport in priority order: the user's connected **Gmail** (`get_user_gmail_tokens` in `app/services/gmail.py`, tokens from the google `OAuthAccount`) → **SMTP** → **dev-log**. Open/click **tracking** (`OutreachRecipient.tracking_id` + pixel/link wrapping in `app/api/tracking.py`) is applied *before* transport selection, so it works on every path; set `API_BASE_URL` in prod so the links resolve. **Reply triage:** `app/services/outreach_replies.py::sync_replies_for_user` (Gmail-backed, best-effort; no-op without Gmail) + `GET /outreach/threads` + `POST /outreach/sync-replies` (migration `036` added `reply_*` fields to `outreach_recipients`); the Dashboard reply rows read `/outreach/threads`. The Contacts directory's "Send to Outreach" pre-fills the existing `EmailComposer` via its `initialRecipients` prop (passed through router state). **Deps gotcha:** `gmail.py` imports `google.auth` / `google_auth_oauthlib` / `googleapiclient` at module load, and `main.py → api/outreach.py → services/gmail.py` runs that chain at **boot** — so `google-auth`, `google-auth-oauthlib`, and `google-api-python-client` **must stay declared in `pyproject.toml`** or the app fails to start (`ModuleNotFoundError: No module named 'google'`).

- **Void-analysis depth.** `void_analysis` (MCP tool + `app/services/void_analysis.py`) takes `use_case` (`leasing` → recruitable targets; `investment_memo` → demand signals + risk) and `tenant_focus`. A deterministic `affordability_tier(median_income)` drives **demographic scrubbing** — the model returns an `excluded_suggestions` list (what it filtered + why) so the broker can override. The analyst/matchmaker prompts ask the "specific tenant types/sizes?" follow-up and enforce the scrub.

- **Client-fit Search (the matcher, replaced the mock grid).** `property_listings` table (`app/db/models/listing.py`, migration `037`); API `app/api/listings.py` = CRUD + CSV/XLSX import + **`POST /listings/match`**. `app/services/listing_match.py::match_listings_for_client` LLM-scores each listing 0–100 against a client `Company`'s buy-box (the inverse of matchmaker) — BYOK-aware, pure helpers unit-tested in `tests/test_listing_match.py`. Frontend: `hooks/useListings.ts` + the rebuilt `pages/SearchPage.tsx` (pick a client → ranked matches with fit badge + rationale + flags). A CREXi/listing API is a business-track feed; CSV import is the interim source and the scoring is feed-agnostic.

- **Workflow kanban (real, replaced the mock).** `pages/WorkflowPage.tsx` renders real deals from the deals API grouped by `DealStage`, with native HTML5 **drag-to-move** → `PUT /deals/{id}` (records `DealStageHistory`). Reuses `hooks/useDeals.ts` + `types/deal.ts`.

- **void → Contacts promotion (the spine's other leg).** A void/matchmaker chat result can be saved straight into the Contacts directory. `app/services/tenant_promotion.py` holds the three pieces: `extract_promotable_tenants(analysis)` (pure — flattens the `void_analysis` JSON's `is_void` `categories[].suggested_tenants` into a deduped, score-ranked list); `promote_tenants_to_contacts(db, user_id, tenants, source)` (writes `Company` rows, de-duped by name like the CSV importer, `is_expanding=True`, provenance in the `criteria` buy-box JSON); and a per-turn **capture sink** behind a `ContextVar` (`begin_tenant_capture` / `record_promotable_tenants`). The exact tenants a void run produces are surfaced with **no second LLM call**: `analyze_voids_for_property` appends them to the sink (gated — a no-op for report/test callers), and the chat WS handler drains it into a **`tenant_candidates`** event after the turn (mirrors the `fact_candidates` pattern; emitted at the specialist + legacy paths in `app/api/chat.py`). Endpoint `POST /api/v1/contacts/from-void` (`PromoteTenantsRequest`) takes the explicit captured list. Frontend: the event lands in `chatStore.tenantCandidates`; `components/Chat/TenantSavePanel.tsx` renders a quiet "save these N tenants" panel under the analysis; `hooks/useContacts.ts::usePromoteTenantsFromVoid` posts it; saved brands then flow into the existing "Send to Outreach" on-ramp. Only the `void_analysis` *tool* is wired so far — the matchmaker specialist's prose output isn't structured-captured yet.

- **Traffic counts (vehicles/day, AADT).** "How many cars drive past this property a day," from **free public state-DOT ArcGIS layers** — no API key, no CSV upload, synchronous. `app/services/traffic_counts.py` is a **provider abstraction**: each `AadtProvider` = a state-DOT ArcGIS AADT layer URL + field mapping + state coverage, seeded with **CA (Caltrans), NC (NCDOT), VA (VDOT)** (fields confirmed against each live layer). `get_traffic_count(lat, lng, state)` resolves coords via `location_resolver`, runs an expanding point-buffer ArcGIS query, and returns the nearest count (vehicles/day + road + year + distance) — or `None`, in which case the caller says "not covered yet" / "no nearby station" (**never a fabricated number**). Add a state by dropping a provider into `_PROVIDERS`; the national HPMS layer is the natural next one. Per-state field quirks live in config (NC uses per-year `AADT_YYYY` columns → latest; VA uses `ADT`, *not* the weekday-only `AAWDT`). Surfaced three ways: the **`traffic_counts` MCP tool** (live in chat — scout + analyst; registered in `mcp/server.py` + `services/tools.py` schema + `reliability.TOOL_TIMEOUTS` + `api/chat.py` location-enrichment + workflow badge), **`void_analysis` backfills** real VPD into the report when there's no SiteUSA upload, and **`GET /api/v1/traffic/counts?address=`** (`app/api/traffic.py`, powers the property card). NOTE: TomTom Traffic Stats was rejected — it reports speed/congestion, not counts; Placer.ai (foot-traffic *visits*) is a different, complementary metric and stays a dormant stub until keyed.

**Reinforced rules:** the **"no mock data"** rule now also covers Search, Contacts, and Workflow (all real) — keep every row/count traceable to a real API. Any new LLM path must thread `resolved_llm` (BYOK zero-platform-tokens). New enum-backed columns stay `VARCHAR` + Pydantic `Literal` (no native PG enum). `API_BASE_URL` is a settings/env var: the public backend base URL used to build outreach tracking links.

## Model migration: self-hosted, fine-tuned inference (in progress)

Active effort to move the chat off the Anthropic API onto a self-hosted, fine-tuned open model. **`MIGRATION.md` (repo root) is the running log + decision record (D1–D21) — read it first.** Status: baseline + evals ✅, model selected & L4-validated ✅, data curation ✅, and **three LoRA rounds trained/served/judged (§4.10–§4.12), all on the same re-anchored judge vs base Qwen 2.80 / Haiku 4.35: v1 (human-gold only, Together's unpinned r=64 defaults) = 2.50; v2 (r=16 + sectioned-format augmentation) = 2.35; v3 (Phase 3b teacher augmentation: 29 human-gold + 110 label-blind Claude-teacher pairs over controlled GO/PASS/UNCERTAIN scenarios, `finetune/teacher_augment.py`) = 3.05 — first fine-tune above base, first 2/4 send-to-client passes, grounding slide reversed (1.75→2.50) while tone hit 3.75.** The v1/v2 lesson stands: small human-gold corpora teach the memo voice, not the input→disposition mapping — teacher-scale mapping data is what bent the curve. Remaining gap to Haiku: detail misreads + fabricated specifics under elaboration (e.g. invented land comps in the held-out probe). Base + all three adapters co-serve on the one L4 (`--enable-lora`, three `--lora-modules` entries; adapters in the git-ignored Truss `data/`). Next levers: scale teacher data 2-3× with misread-targeting scenarios + a no-unsupplied-comps teacher rule; D18 (14B) if understanding plateaus. Caveat to keep honest: the teacher is also the judge (Sonnet 4.6) — read deltas, not absolutes.

- **Why it's tractable:** every model call already goes through `app/llm/`, which speaks both `anthropic` and `openai_compatible`. Baseten / Together / HF all serve an OpenAI-compatible API, so the seam already exists — point the `openai_compatible` provider at the endpoint and the whole chat path works.
- **The model is an ADVISOR, not a tool-picker.** This is the core product framing and what the fine-tune targets: given a property + the user's book of business, it must reason in a conversational broker voice about *what the property is*, *which of the client's tenants/clients it fits*, and *a clear pursue-vs-pass recommendation* ("is it worth your time?"). Tool-calling is necessary but not the value; advisory quality is.
- **Eval harness — `backend/evals/`** (deliberately NOT in the CI unit-test gate; it hits live models). Two dimensions, both provider-agnostic via `EVAL_*` env vars (`EVAL_PROVIDER` / `EVAL_MODEL` / `EVAL_API_KEY` / `EVAL_BASE_URL`) so the same suite scores Anthropic / Gemini / HF / Baseten / Together on equal footing:
  - `run_eval.py` + `harness.py` — tool-calling + routing accuracy against the real `plan_workflow` / `call_specialist`. Grading in `grade.py` (pure stdlib; offline self-check: `python evals/grade.py`). 90% tool-call bar; cases in `cases/*.jsonl`. `tests/test_evals.py` unit-tests the grader.
  - `run_advisory.py` + `judge.py` — **advisory quality** via LLM-as-judge across 5 criteria (`property_understanding`, `client_fit_reasoning`, `recommendation_clarity`, `grounded`, `tone`). The `ADVISORY_SYSTEM` persona is reused verbatim as the SFT system prompt so train/serve prompts don't skew.
  - Seed cases are synthetic but grounded in the real tool schemas; real dogfood prompts live in the orphaned `backend/spacefit.db` (to be folded in).
- **Model: `Qwen/Qwen2.5-7B-Instruct`** (Apache-2.0, fits a 24 GB L4, strong tool caller). Served via a config-only Truss at `backend/baseten/qwen25-7b-instruct/` (vLLM image, `--tool-call-parser hermes --enable-auto-tool-choice`, scale-to-zero; deployed model `3m50kp6w`). Controlled-serving benchmark vs the Haiku baseline: tool-calling **92.9%** (beats Haiku, clears the bar) + ~0.9 s warm TTFT, **but advisory quality 2.80/5 vs 4.35 → never ship BASE Qwen; closing the advisory gap is the fine-tune's whole job.**
- **Diagnosis gate (before spending on a fine-tune):** we classified *why* base Qwen scores 2.80. The gap is **voice / format / disposition** — it hedges instead of committing to a pursue-vs-pass call, and misses the broker register — **not a reasoning ceiling**, so it's LoRA-fixable from a small human-gold corpus. (A 14B-in-FP8 fallback is documented as D18 in case a true ceiling surfaces; not expected.)
- **Data pipeline — `backend/finetune/`** (LLM-assisted curation, no hand-labeling):
  - `curate.py` — the `CURATION_SYSTEM` prompt classifies each source doc, quality-gates it, *reconstructs the user input* that would have produced it, *preserves the human output verbatim*, and **redacts all PII + client identity** (keeps public tenant brands + cities). `extract_text` handles pdf/docx/txt/csv.
  - `build_memo_dataset.py` — the `SLICE_SYSTEM` prompt section-slices each investment memo into multiple focused input→output pairs; `split_by_deal(items, n_heldout_deals, seed)` holds out **whole deals** (not random rows) so eval has zero training leakage.
  - **Findings that reshaped the plan:** the void analyses turned out to be raw Sites USA data dumps, not prose advice (low SFT value as-is); the **investment memos are the gold** (~6 distinct deals). Current human-gold dataset = **36 pairs across 5 deals**, one deal held out for the advisory eval (~29 train pairs). Lever 2 — voice-steered teacher augmentation over the void data — is on standby only if the human-gold LoRA underfits.
  - Datasets are **git-ignored** (`finetune/dataset/`, `finetune/training/data/`) — client-derived, never committed.
- **Training venue (D21): train-venue ≠ serve-venue, by design.** Baseten Training requires a separate entitlement the account doesn't have (`truss train push` → 403), so we **train on Together AI** and still **serve the adapter on the Baseten L4** (vLLM `--enable-lora`). `finetune/together_submit.py` uploads the chat-format JSONL (already Together's format) and launches the LoRA (`train_on_inputs="auto"` to mask inputs / learn only the advisory outputs). The Axolotl config `finetune/training/qwen_lora.yaml` is venue-agnostic (lora_r 16 / alpha 32 over q,k,v,o,gate,up,down_proj, bf16, chat-template, external held-out deal so `val_set_size: 0.0`) — it runs unchanged on Baseten Training (`finetune/training/config.py` + `run.sh`) or a rented GPU if we ever need to move.
- **Gotchas:**
  - HF serverless router is unreliable for tool-calling (heterogeneous providers 400 on `tool_choice`) → use controlled serving.
  - Together's job *finalization* (adapter compress/upload) is flaky on a job this tiny — two attempts (`ft-c0060f33-bf9f` and an earlier one) errored at the upload step with an auto-refund before `ft-0a9cfffd-ba02` went through cleanly. Just resubmit; the dataset/config was never the problem.
  - The configured `anthropic_model` default `claude-3-5-haiku-20241022` is **retired (404s)**; fix-forward to `claude-haiku-4-5` is owed (see MIGRATION.md §4.1).
  - Vision document parsing stays on Anthropic (out of scope). BYOK stays the "bring your own frontier model" path; the fine-tuned Qwen becomes the platform default.
- **File map:** evals `backend/evals/`; serving Truss `backend/baseten/qwen25-7b-instruct/`; data + training `backend/finetune/` (`curate.py`, `build_memo_dataset.py`, `together_submit.py`, `training/`).

### Local serving on Mac Mini (alternative to Baseten)

The fine-tuned Qwen2.5-7B can be served locally on the Mac Mini via **Ollama** instead of Baseten. This is viable for dev and light prod traffic — 7B Q4 needs ~6 GB RAM, so 16 GB+ is comfortable.

**Setup:**

```bash
brew install ollama
ollama pull qwen2.5:7b-instruct     # base model; for LoRA adapter see below
ollama serve                         # auto-starts on localhost:11434
```

**To load a fine-tuned LoRA adapter**, create a `Modelfile`:

```
FROM qwen2.5:7b-instruct
ADAPTER /path/to/adapter/gguf
```

Then `ollama create spacegoose-advisor -f Modelfile`.

**Backend env vars** (in `.env` or Render dashboard):

```
LLM_PROVIDER=openai_compatible
LLM_MODEL=spacegoose-advisor        # or qwen2.5:7b-instruct for base
OPENAI_BASE_URL=http://<mac-mini-ip>:11434/v1
OPENAI_API_KEY=ollama                # Ollama ignores this but the client requires non-empty
```

This works because `app/llm/client.py` routes `openai_compatible` through `OpenAICompatibleLLMClient`, which speaks the same OpenAI-format API that Ollama exposes at `/v1`. No code changes needed — only env vars.

**Current prod status (2026-07-05):** `render.yaml` declares `LLM_PROVIDER=baseten` + `LLM_MODEL=spacegoose-advisor-v3` but `BASETEN_API_KEY` / `BASETEN_BASE_URL` are not set in Render, so **prod LLM calls are failing silently**. Either set the Baseten credentials, point to the Mac Mini Ollama endpoint, or revert to `LLM_PROVIDER=anthropic` until self-hosted serving is ready.
