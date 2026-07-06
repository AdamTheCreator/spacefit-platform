# Handoff: Agent Thinking Indicator — "Work Log Card" (Option B)

## Overview
A chat "assistant is working" indicator for Perigee. When a user sends a message, a compact **work log card** appears in the message stream showing (1) the current high-level phase, (2) a live elapsed timer, and (3) one row per step/subagent with live status. When the run completes, the card is removed and the answer message appears with a quiet one-line **receipt** above it. This replaces any full-width progress bars / stacked status chrome; it must be implemented in **every chat surface** of the product (free-form chat, project chats, and any other place the assistant answers).

## About the Design Files
The files in this bundle are **design references created in HTML/JSX with Babel-in-browser** — prototypes showing intended look and behavior, **not production code to copy directly**. Recreate them in the target codebase's existing environment (framework, state management, streaming/agent event system) using its established patterns. The simulated phase timer in the prototype should be replaced by real agent lifecycle events.

## Fidelity
**High-fidelity.** Colors, typography, spacing, radii, and motion are final. Recreate pixel-perfectly using your design-token system.

## Reference files in this bundle
- `thinking-indicator.jsx` — the production-intent component (`ThinkingIndicator` with `variant="log"`, plus `ThinkingReceipt`). **Option B is the `TILog` component in this file.**
- `chat.jsx` — the chat screen showing integration: send flow, indicator placement, Stop generating, receipt on the answer message.
- `Thinking Indicators.html` + `thinking-options.jsx` — the original 3-option exploration (A whisper line / **B work log card — CHOSEN** / C orbit badge). For context only.
- `styles.css` — Perigee design tokens (`:root` variables) and the `.ti-*` animation keyframes.

## Anatomy (Option B — work log card)
Rendered in the message list, aligned like an assistant message:

1. **Avatar** — 28px circle, Perigee logo image, flush left.
2. **Card** — to the right of avatar. White `#FFFFFF`, 1px border `var(--line)`, border-radius 12px, padding `11px 14px 8px`, max-width 460px.
3. **Header row** (the whole header is a button that toggles collapse):
   - Spinner: 13px circular arc spinner, track `var(--line)` (3px stroke), arc `var(--orange)`, 0.9s linear infinite rotation.
   - Title: current phase label + "…", 12.5px, weight 600, color `var(--navy)`. Phase labels: "Reading your question", "Planning the approach", "Researching the trade area", "Analyzing tenant gaps", "Matching tenants", "Drafting your answer". (In production, drive from real agent events.)
   - Elapsed timer: right-aligned, 11px, color `var(--gray)`, `font-variant-numeric: tabular-nums`, counts whole seconds.
   - Chevron: 12px, `var(--gray)`, rotates 180° when expanded, 0.2s transition.
4. **Rows** (when expanded): separated from header by 1px top border `var(--line)`, each row `7px 0` padding, 9px gap:
   - Status glyph (16px column): live → spinner (subagent rows use the subagent's color for the arc); done → 13px green check `#2F7A3B` (2.6 stroke); queued → 7px dot `var(--line-strong)`.
   - Label: 12.5px; live → weight 600 `var(--navy)`; done → weight 500 `var(--slate)`; queued → `var(--gray)`.
   - Row set: "Understanding the request", then one row per subagent as it joins — `"{Agent} · {task}"` (e.g. "Scout · pulling nearby businesses & demographics"), finally "Drafting your answer".
   - New rows animate in: 0.3s ease, from `opacity 0 / translateY(4px)` (`.ti-rise`).

### Subagents (sample identities — replace with real agent registry)
- Scout `#3A5BA0` — research/data pulls
- Analyst `#C25E1F` — analysis
- Matchmaker `#2F7A3B` — scoring/matching

### Completion receipt
When the run finishes, remove the card and render the answer message with a receipt line above the bubble:
- 11px, color `var(--gray)`, left padding 40px (aligns past the avatar), 6px bottom margin.
- Content: small check icon + `Worked with {agent names} · {elapsed}s` (e.g. "Worked with Scout, Analyst & Matchmaker · 12s").

## Interactions & Behavior
- **Send** → append user bubble, show work log card immediately (never leave a dead gap between send and first token).
- **Header click** → collapse/expand rows; header (spinner + phase + timer) always visible while running.
- **Stop generating** — centered ghost button above the composer while running: 12px text `var(--slate)`, 9px square stop glyph `var(--deep)` (2px radius). Clicking aborts the run; whatever answer exists is shown with the receipt.
- **Composer while running**: input placeholder becomes "Perigee is working…", Send disabled at 50% opacity; Enter (without Shift) sends when idle.
- **Reduced motion**: all `.ti-*` animations disabled under `prefers-reduced-motion: reduce`; spinner may be replaced by a static glyph; shimmer text falls back to solid `var(--slate)`.
- Phase/row transitions come from agent lifecycle events: `phase_changed`, `subagent_started`, `subagent_finished`, `run_finished`. Elapsed timer starts at send.

## State Management
- `running: boolean` — a run is in flight for this thread.
- `phaseLabel: string` — current high-level phase.
- `steps: Array<{ id, label, status: 'queued'|'active'|'done', color? }>` — ordered log rows.
- `elapsedSec: number` — ticks every 1s while running.
- `collapsed: boolean` — per-card UI state (default expanded).
- On completion: append assistant message with `receipt = { agents: string[], seconds: number }`.

## Design Tokens (Perigee)
- `--navy: #0F1B2D` (primary text), `--deep: #1F3556`, `--orbit: #3A5BA0`, `--mist: #A7C7F7`
- `--orange: #FF8A3D` (accent / spinner arc)
- `--slate` (secondary text), `--gray` (tertiary), `--line` (hairline borders), `--line-strong`, `--cream`, `--moonlight` — see `styles.css` for exact values
- Success green: `#2F7A3B`
- Fonts: Sora (display), Inter (UI) — indicator uses Inter throughout
- Radii: card 12px; receipt/none. Spinner 0.9s linear; row entrance 0.3s ease.

## Assets
- Perigee logo avatar (`assets/perigee-logo.png` in the prototype) — use the production logo/avatar component.
- All icons are inline SVG (spinner, check, chevron, stop) — reproduce with your icon system.

## Acceptance checklist
- [ ] Card appears instantly on send in ALL chat surfaces
- [ ] One row per subagent with per-agent colored spinner, ticking to green check
- [ ] Elapsed timer, tabular numerals
- [ ] Collapsible via header; state per message
- [ ] On finish: card removed, answer rendered with "Worked with … · Ns" receipt
- [ ] Stop generating aborts and still shows a receipt
- [ ] Honors `prefers-reduced-motion`
