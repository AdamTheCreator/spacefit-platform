# SpaceFit Design System — Minimalist AI Assistant

> **Mandatory reading for any agent touching the frontend.**
> Violating these principles will be reverted. When in doubt, do less.

---

## Product Role

SpaceFit is an AI-driven commercial real estate workbench. The UI follows the UX patterns of modern AI interfaces (ChatGPT, Claude) — not traditional SaaS dashboards. The conversation *is* the product.

---

## Design Philosophy

### 1. Low Friction, High Signal
Strip ornamental complexity. Use space and typography to create hierarchy — not heavy borders, not saturated backgrounds, not excessive chrome.

### 2. Neutral-First Palette
Base: clean near-white and soft gray (`#ffffff`, `#f9f9fb`). Keep the user focused on data and conversation, not the UI itself.

### 3. Restrained Green Accent — `#10b981`
Used **exclusively** for:
- Connected/live states
- Primary CTA actions
- Brand identification (Sparkles icon, logo)

Do not use green decoratively. Do not introduce other accent colors.

### 4. Quiet Interaction
Animations are purposeful:
- Slow pulse (`animate-pulse-slow`, 3s) → thinking/connecting states
- Subtle fade-in → message continuity
No bouncing, no flashy transitions, no attention-grabbing motion.

---

## Core Component Specs

| Component | Spec |
|-----------|------|
| **App Shell** | Centered "Chat Stage", `max-width: 840px`, optimal readability |
| **Sidebar** | Clean, `border-subtle` navigation. Chat is primary; Pipeline/Documents are secondary |
| **Messages** | Full-width layout — **no bubbles**. Role distinction via subtle background shifts (assistant: `#f9f9fb/50`) + icon-based avatars |
| **Input** | Centered floating textarea, `border-radius: 2xl`, high-contrast action button |
| **Typography** | Manrope for all UI. Sentence case preferred — not UPPERCASE, not Title Case Everywhere |

---

## Operational Rules

### ✅ Do
- Use CSS variables: `--bg-primary`, `--accent`, `--radius-md`, etc. (defined in `index.css`)
- Keep data views integrated into the chat flow
- Use semantic colors (`--color-success`, `--color-error`) only for critical states
- Keep new features (Outreach, Documents, Pipeline) in the same quiet assistant-first feel

### ❌ Don't
- Introduce "boxed-in" dashboard layouts
- Add heavy borders, card shadows, or panel chrome
- Use saturated or decorative colors
- Add uppercase labels, badge counts, or noisy status indicators unless critical
- Regress toward legacy SaaS template aesthetics

---

## Tech Stack
- React 19
- Tailwind 4
- Lucide React (icons)
- Manrope (Google Fonts) + IBM Plex Mono

---

## When Adding New Features

Ask: *"Does this feel like a quiet assistant or a busy dashboard?"*

If it feels like a dashboard → simplify. Strip the chrome. Let the content breathe.

*Authored from Gemini design review — 2026-03-08*
