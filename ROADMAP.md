# Space Goose — Roadmap to the next version

> Source: partner call (Jun 2, 2026) + a full read of the codebase.
> This doc is the plan of record. Phase 0 is already shipped on branch
> `claude/eloquent-shannon-zMQPx`; everything below it is sequenced, not built.

---

## The one idea that ties it all together

Everything we circled on the call — void analysis, contacts, bulk import, outreach,
campaigns — is **one connected flow that doesn't connect yet**. The pieces exist as
islands; the next version is mostly about wiring them together and deleting the mock
data between them.

```
Void / tenant-gap analysis  →  discovered tenants become Contacts  →
   build a Campaign (recipient list + AI-drafted email)  →
      bulk send (tracked)  →  replies land in a triage queue
```

And the app actually serves **both sides of a brokerage** off the same fuel
(Contacts + their stored preferences):

| Motion | Direction | Engine |
| --- | --- | --- |
| **Landlord / leasing** | I have a property → who's missing? → outreach those tenants | void analysis |
| **Tenant / buyer rep** | I have clients → which listings fit them? → pursue the best | **client-fit search** (new) |

**Contacts is the keystone** — two major features depend on it, which is why it's
sequenced first.

---

## Reality check: what's actually built (the big surprise)

On the call we said "outreach isn't built." The code says otherwise — it's **~70% built**,
it just isn't connected to anything, so it feels missing.

| Surface | Verdict | Notes |
| --- | --- | --- |
| Project chat + void/tenant-gap analysis | ✅ Real | The strongest feature. Specialists: scout / analyst / matchmaker. |
| Outreach page, campaign list, email composer | ✅ Real | `OutreachPage.tsx`, `EmailComposer.tsx` (Tiptap). |
| Campaign backend (11 endpoints + models) | ✅ Real | create / list / send / templates in `api/outreach.py`. |
| AI email drafting from a property | ✅ Real | `draft_outreach` tool + Outreach specialist. |
| Batched bulk send | ✅ Real | `email_blast.py`, batches of 10. |
| Open/click tracking | ⚠️ Was broken | Model was missing `tracking_id` → every lookup crashed. **Fixed in Phase 0.** |
| Real sending (Gmail / Resend) | ⚠️ Not wired | Both exist; campaigns fall back to a dev SMTP log. |
| Reply reading / triage queue | ❌ Stub | `gmail_monitor.py` watches for flyers, not replies. Dashboard fakes it off `replied_count`. |
| Contacts directory | ❌ Mock | 100% hardcoded in `pages/contacts/data.ts`. No model, no API. |
| "Find properties" / Search | ❌ Mock | Hardcoded grid in `SearchPage.tsx`. |
| Workflow / kanban board | ❌ Mock | Hardcoded columns that don't even match the real `DealStage` enum. |

**Cross-cutting theme — purge the mock data.** Our own `CLAUDE.md` rule says every number
must trace to a real API. Three surfaces still violate it: **Search, Contacts, Workflow** —
exactly the ones that made the app feel fake on the call.

---

## Decisions locked

1. **New-project form** — free-form *"What are you looking for?"* **+** optional focus chips
   (void / demographics / traffic / investment memo). Best of both. *(shipped, Phase 0)*
2. **Sending** — per-user **Gmail OAuth** as default (broker's own address, best
   deliverability), **Resend** as fallback.
3. **Search** — becomes a **client-fit matching engine** (see below), not a dumb address lookup.
4. **Contacts vs legacy Customers** — **unify** onto the new Contacts model; build the client
   "buy box" there; deprecate + migrate legacy Customers. *(proceeding on this assumption)*

---

## Phase plan

| Phase | Scope | Status |
| --- | --- | --- |
| **0 — Quick wins** | Contacts sidebar fix · project chat suggestions + renamed goal field · tracking_id bug · (cleanup) | ✅ **Shipped** (this branch) |
| **1 — Real Contacts** | `Contact` + `Company` models, CSV bulk import + one-by-one, **client buy-box schema** | Next |
| **2 — Connect the spine** | "Create campaign from void/contacts" on-ramp; promote discovered tenants → Contacts | After P1 |
| **3 — Finish sending** | Gmail send + wire tracking IDs into send path + reply triage (`/outreach/threads`) | After P2 |
| **4 — Void depth** | leasing vs investment-memo modes · follow-up Qs · demographic list-scrubbing · intersections | Parallel-able |
| **5 — Search & kanban real** | client-fit matching engine · wire Workflow to real deals | Gated on data + P1 |

---

## Phase 0 — shipped on this branch

1. **Contacts shows the side nav.** `ContactsPage.tsx` was the only protected page not wrapped
   in `<AppLayout>`. Wrapped it (matches the `ProjectsPage` idiom). One-line root cause.
2. **Property projects show suggestions like chat.** Project chats now pass `chatContext="project"`
   and get a tailored suggestion set (void analysis / demographics / investment memo / draft outreach)
   instead of generic chips.
3. **New-project field reworked.** "Description" → **"What are you looking for?"** with example
   text and optional focus-area chips. Critically, it now writes to `instructions` (the field the
   agent actually reads + that's editable later in the project sidebar) — previously the text went
   to `description`, a dead field the LLM never saw.
4. **Fixed broken email tracking.** `OutreachRecipient.tracking_id` existed in migration 004 but
   was missing from the SQLAlchemy model, so every `/tracking/open|click` lookup raised. Added the
   mapped column (indexed, auto-populated) so new recipients are trackable.

---

## The 5 priorities (detail)

### 1) Property projects show suggestions — ✅ done (Phase 0)
Plus a future option: have the backend generate 3 *AI-tailored* next-questions from the project
context, rather than static chips.

### 2) Side nav on Contacts — ✅ done (Phase 0)

### 3) Bulk import of contacts — **Phase 1 (foundation)**
- **Backend:** `Contact` + `Company` models, `/contacts` CRUD, `/contacts/import` (CSV). Model it
  on the existing `customers.py` + `useCustomers.ts` import pattern.
- **Frontend:** `useContacts` hooks, replace mock `data.ts`, wire "Add contact" (one-by-one) and a
  CSV dropzone (reuse `useImportUpload`).
- **Design the schema with a client "buy box" from day one** (asset type, size range, target
  markets, budget / cap rate, tenant credit, demographics) — the Search matching engine depends on it.

### 4) Outreach overhaul (bulk email) — **Phase 3 (finish, don't build)**
- Wire **Gmail OAuth** send (Resend fallback); replace the dev-log SMTP path.
- Generate + inject `tracking_id` in the send path (pixel + link wrapping already exist).
- Build **reply triage**: `/outreach/threads`, map `gmail_monitor` replies to campaigns, replace
  the dashboard's `replied_count` hack.
- Let recipients come from the new Contacts store, not just void output.

### 5) Campaign overhaul — **Phase 2**
A campaign, concretely (the code already supports this shape):

> **A campaign = a property you're pursuing + a recipient list + an AI-drafted email + a send + tracked results.**

The missing piece is the **on-ramp**: a "Create campaign / Start outreach" action from a project or
a void-analysis result that pre-fills recipients (discovered tenants + Contacts) and a drafted email,
then drops the user into the existing composer. That single action is what makes campaigns feel real.

---

## Search → a client-fit matching engine (expanded vision)

Search stops being a mock grid and becomes a **recommender**. Pull listings from a property database
(CREXi first), and for each listing the LLM produces a **fit score = how likely this specific client
is to want it**, scored against that client's stored buy-box. Ranked results show the score, *which
client(s)* match, and *why*.

```
for each listing from the property feed:
   score, rationale = LLM( listing details  ×  client's buy-box )
   → "92 — fits Acme Capital: matches 20–40k SF / Sun Belt / value-add; flag: rent ~8% over target"
rank listings; surface top matches per client
```

- Reuses the existing `matchmaker` specialist (which scores *tenants for a vacancy*) **inverted** to
  score *listings for a client*.
- **Depends on:** Contacts + buy-box (Phase 1) and a property feed.
- **Data feed:** CREXi is the first bet (we know the owner; beta/partnership is the realistic API
  unlock). Build against a **provider abstraction**; LoopNet/CoStar stay locked. **Interim with no
  API:** ingest a CREXi listing export as a CSV (like the CoStar importer) and score those — the
  scoring is the valuable part and is API-independent.

---

## Void-analysis depth (the differentiator) — Phase 4

- **Leasing vs investment-memo modes** — same tool, two output shapes (today it's one-size-fits-all).
- **Follow-up question** before running a leasing void — "any specific tenant types or sizes?"
- **Demographic-aware list scrubbing** — filter suggestions against trade-area income/profile (the
  "no Neiman Marcus in a low-income area" problem), with a human-in-the-loop review.
- **Intersection / cross-streets input** — brokers often have no address (ground-up dev), just
  "Main & 5th." Geocoding handles it; small input change.

---

## Other nuggets & cleanup

- **"Find properties" vs "Properties"** — keep the conceptual split: Find = any listing (matching
  engine); Properties = my uploaded projects.
- **Document staleness** — add a freshness indicator / re-index on project docs.
- **Vehicle/traffic counts** — needs a real source (Placer.ai is already stubbed and closest;
  StreetLight or Caltrans/DOT are alternatives).
- **Kanban (Workflow)** — wire to the real `Deal` / `DealStage` model so "start an outreach sequence"
  drops a card; today it's pure mock with mismatched stage names.
- **Cleanup** — remove the stale SiteUSA "connect" remnant in recommendations and the dead
  `scripts/debug_siteusa_login.py` Playwright scraper.
- **BYOK direction validated** — partner endorsed "connect to what you already pay for" (TLO,
  ZoomInfo, …). Natural extension: let users plug their own *data* subscriptions, not just LLM keys.

---

## Business / API track (non-code, runs in parallel)

These unblock real data but aren't code-gated; the connector interface is ready to plug them in.

- **Placer.ai** — get an API key (stub is in place). Fastest unlock for traffic + visitor data.
- **SiteUSA** — API via the rep; paid but standard.
- **CREXi** — beta/partnership via the owner contact. The key unlock for the matching engine.
- **CoStar** — realistically a no; plan around its absence.

---

## Open decisions still to make

- New-project: keep populating `description` for project-card subtitles, or let cards fall back to
  showing `instructions`? (Today new projects set only `instructions`, so cards have no subtitle.)
- Reply triage: thread model granularity — per-recipient vs per-campaign threads.
- Matching engine: score listings per-client on demand, or precompute nightly per client buy-box?
