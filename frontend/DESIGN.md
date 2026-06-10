# Space Goose Design System — AI Workbench

> **Mandatory reading for any agent touching the frontend.**
> Violating these principles will be reverted. When in doubt, follow the pattern that already ships.

This system is grounded in Eve Weinberg's _"Designing for AI Engineers: UI patterns and
principles you need to know"_ (UX Collective), adapted from a developer-tools audience to a
commercial-real-estate workbench. The article's pattern names are used verbatim below.

---

## Product Role

Space Goose is an AI-driven commercial real estate workbench. A specialist-routed agent analyzes
properties, finds tenant gaps, pulls comps, and drafts outreach. **The conversation is still the
spine** — but most surfaces around it are dense, data-rich tools, not a quiet marketing site.

---

## The core decision: hybrid by surface

The article pushes **data density** ("Reduce those margins!", dense sortable tables, parsed
metadata). Earlier Space Goose canon pushed the opposite ("quiet-first, let it breathe"). We
resolve the conflict **by surface, not globally**:

| Mode | Surfaces | Feel |
|------|----------|------|
| **Conversation mode** (quiet) | Chat, Project chat, Landing/Auth, Welcome | Calm, centered, generous whitespace, no chrome. A subtle "2nd layer of what's happening under the hood" (agent activity) is the only density. |
| **Workbench mode** (dense) | Contacts, Search, Pipeline/Workflow, Outreach, Analytics, Insights, Admin, **Playground** | Reduced margins, compact rows, sortable/filterable tables, parsed metadata, side-drawers for detail. Information-first. |

> Ask: _"Is the user **reading/thinking** here, or **operating** here?"_ Reading → quiet.
> Operating → dense. Never mix a marketing-grade hero into a workbench table view.

---

## Pattern library (article patterns → our surfaces)

### 1. Condensed information / Data density
**Where:** all workbench surfaces. **Do:** tighten vertical rhythm (rows ~36–44px, not card-padded),
right-align + `tabular-nums` for numerics, lean on hierarchy (weight/size/color) instead of borders
and shadows. **Don't:** wrap every row in a `card-industrial` with 20px padding.

### 2. Parsed metadata — tables, side-drawers, tagging
**Where:** Contacts, Search, Pipeline, Outreach, Admin. **Do:** extract the fields that matter into
columns; make them **sort/filter/search-able**; open detail in a **right side-drawer** (see
`Pipeline/DealDetailDrawer.tsx`) rather than navigating away; use `FilterChip` + `SegmentedControl`
for active filters and view modes. These are the primary design-system elements to refine.

### 3. Familiar patterns (Jakob's Law)
Follow conventions users already know from ChatGPT/Claude/Hugging Face/OpenAI. Reuse the shared
primitives (`ui/Button`, `ui/Slider`, `ui/SegmentedControl`) before inventing a control. If a
pattern is established and there's no strong reason to deviate, go with it.

### 4. Chat interface + the "under the hood" layer
Keep chat **as clean as a search engine** with a **subtle 2nd layer** of what the agent is doing:
`Chat/AgentActivityPanel.tsx`, `WorkflowProgress.tsx`, streaming `text_delta` bubbles, tool-call
chips. Quiet by default; the activity strip is the only permitted density. **No bubbles**, no
boxed-in dashboard chrome inside the chat stage (`max-width: 840px`).

### 5. Playground — _our property/project analysis console_
The flagship workbench surface. `components/Playground/AnalysisPlayground.tsx`, mounted on
`/projects/:id` and `/property/:id`. It is a **safe space to experiment with an AI analysis**:

- **Controls rail (left):** document picker · analysis type (`SegmentedControl`) · focus ·
  **parameter slider** (trade-area radius) · **model switcher** · instructions · Run.
- **Model switching** is real and **BYOK-gated**: with a valid key, a `<select>` of the active
  provider's models writes a per-specialist override (`useUpdateSpecialistModels`); without a key it
  shows the platform default + a link to add one. Never render a knob that doesn't change the run.
- **Usage visible** (the article's "pay-as-you-go"): a tokens/calls/24h strip from `useUsage`, with a
  "Your key" vs "Platform" badge.
- **Run area (right):** explainer + **run history** of prior analysis sessions.
- **Run** routes to the existing `/chat/:sessionId` stream — we reuse the real streaming surface,
  we don't reimplement it.

When you extend the Playground: every control must map to a real `start-analysis` parameter, and the
output must come from the real WS stream. No fabricated previews.

### 6. Search & filter
Model repositories/result grids (Search, Contacts) need real discoverability: a search input, sort,
and filter chips sitting **together** above a dense result list. Surface the metadata users sort by
(score, size, cap rate, last activity).

### 7. Documentation / code recipes / developer console
Largely N/A for this product (no public API console). If we add usage/billing dashboards, follow the
"developer console" pattern: org → usage → billing, dense and monitoring-first.

---

## Guiding principles (verbatim from the article)

1. **Speed is non-negotiable** — _"It's not fully shipped until it's fast."_ `npm run build` (tsc) is
   the gate; keep bundles lazy (see `App.tsx`).
2. **Minimalism** — _"Anything added dilutes everything else."_
3. **Practicality beats purity** — _"Half measures are as bad as nothing at all."_
4. **Approachable is better than simple.**
5. **Favor focus over features** — _"Encourage flow."_
6. **Information architecture by job-to-be-done** — organize by the user's workflow.

---

## Tokens (source of truth: `src/index.css`)

- **Palette:** Space Navy ramp (`--color-neutral-900 #0F1B2D`) · **Orbit Orange** accent
  (`--accent #FF8A3D`) · Mist Blue (`--color-mist`) · Orbit Blue (`--color-orbit`, links/charts).
  **Never hard-code hex in components** — use the CSS vars (`--bg-primary`, `--text-primary`,
  `--border-subtle`, `--accent`, `--radius-md`, semantic `--color-success|warning|error|info`).
- **Type:** Sora (display/headings) · Inter (UI) · JetBrains Mono (data/tabular). Sentence case —
  not UPPERCASE everywhere; reserve `.label-technical` uppercase for small technical labels.
- **Radius:** 8/12/16/24/28 scale. **Motion:** purposeful only — slow pulse for thinking, fade-in
  for continuity. No bouncing or attention-grabbing motion. Respect `prefers-reduced-motion`.
- **Dark mode** is a full `.dark` / `[data-theme="dark"]` override — test both when adding surfaces.

---

## Operational rules

### ✅ Do
- Pick the right **mode** (conversation vs workbench) for the surface, then commit to it.
- Reuse shared primitives: `ui/Button`, `ui/Slider`, `ui/SegmentedControl`, `AnalysisPlayground`,
  `Pipeline/DealDetailDrawer`, `FilterChip`/`SearchInput` (`pages/contacts/ui.tsx`).
- In workbench mode, prefer dense tables + a side-drawer over card grids + full-page navigation.
- Handle loading/error explicitly (`if (isError && !data)` → soft error, keep cached UI).

### ❌ Don't
- Mix marketing chrome into workbench tables, or densify the chat stage.
- Hard-code colors, add heavy shadows/borders where hierarchy would do, or invent a one-off control.
- Rename the legacy `-industrial` utility classes — they're brand-neutral tokens reused everywhere; a
  rename needs a coordinated migration.
- **Ship mock data.** Every row, count, badge, and Playground control must trace to a real API. If
  the data doesn't exist yet, render an honest empty/placeholder state — never a fabricated number.

---

## Rollout status

- ✅ **Playground** — shared `AnalysisPlayground` live on `/projects/:id` and `/property/:id`
  (PropertyDetailPage's old hardcoded stats/comps/timeline were removed as part of this).
- ⏳ **Workbench density pass** — Contacts, Search, Pipeline, Outreach, Analytics, Admin to adopt the
  data-density + parsed-metadata + side-drawer patterns. A shared `DataTable` + `FilterBar` primitive
  should be extracted during this pass.

*Originally authored from a Gemini design review (2026-03-08); rewritten 2026-06-10 to adopt the
"Designing for AI Engineers" pattern language and the hybrid-by-surface density model.*
