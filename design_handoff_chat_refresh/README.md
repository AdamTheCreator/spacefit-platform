# Handoff: Chat Thread Refresh + Sidebar Connection Status

## Suggested Claude Code prompt
> Implement the design in `design_handoff_chat_refresh/README.md`. The bundled JSX/CSS files are HTML design references, not production code — recreate the changes in our codebase using our existing components and tokens.

## Overview
Three targeted changes to the app chrome and chat surface:
1. **Denser chat thread** — smaller, tighter message bubbles; kill the large blocky message cards.
2. **User messages carry the user's real profile avatar** — same avatar rendered in the sidebar account block.
3. **Connection status + account move out of the top bar** — the top bar carries no avatar or "Connected" indicator; both live in the left nav's account footer.

## About the Design Files
Files in this bundle are **design references created in HTML/JSX (Babel-in-browser)** — prototypes showing intended look and behavior, not production code. Recreate them in the target codebase's environment using its established patterns, components, and design tokens.

## Fidelity
**High-fidelity.** Colors, sizes, spacing and typography are final. Tokens referenced below are defined in `styles.css` (`:root`).

## 1. Chat thread (see `chat.jsx`, `FFMessage` + message list)
Message list: max-width 780px, centered, vertical grid with **12px gap** between messages (was 18px).

**User message** — right-aligned row, 10px gap:
- Bubble: background `var(--navy)`, white text, padding `9px 14px`, border-radius `14px 14px 4px 14px`, font-size 13.5px, line-height 1.5, max-width 70%.
- Avatar to the RIGHT of the bubble: **26px** circle, the user's profile avatar (initials fallback: gradient `linear-gradient(135deg, var(--orbit), var(--mist))`, white Sora 10px initials). MUST be the same avatar component/source used in the sidebar account block — never a generic "U" placeholder.

**Assistant message** — left-aligned row, 10px gap:
- Avatar: 26px circle, product logo image.
- Bubble: white background, 1px border `var(--line)`, border-radius `14px 14px 14px 4px`, padding `10px 14px`, font-size 13.5px, line-height 1.55, max-width 82%.
- Citation pills (when present): 6px gap row, 9px top margin, existing `pill` style at 10px font.

No full-width message cards, no sender-name headers inside the thread — role is communicated by alignment, color, and avatar.

## 2. Sidebar account footer (see `shell.jsx`, bottom of `Sidebar`)
Pinned to the sidebar bottom above nothing (last element), 10px gap row:
- **Avatar with presence dot**: 34px profile avatar; overlapping status dot bottom-right — 10px circle, `#2F7A3B` (connected green), 2px white border. Position `right:-1px; bottom:-1px`.
- **Name**: 13px, weight 600, `var(--navy)`.
- **Status line** under name: 11px `var(--slate)`, inline 6px green dot (`#2F7A3B`) + "Connected". Disconnected state: dot `var(--gray)` + "Offline" (both dots).
- **Settings icon**: 16px, right-aligned, opens settings.

## 3. Top bar (see `shell.jsx`, `Topbar`)
Contains ONLY: page title/subtitle (left), global search field, notifications bell, help — plus optional per-page action buttons. **No user avatar, no connection indicator, no settings entry.** Remove them if present; their functionality moves to the sidebar account footer.

## State Management
- `connectionStatus: 'connected' | 'offline'` — drives both the avatar presence dot and the status line text/color in the sidebar.
- User profile (name, initials/photo) — single source consumed by BOTH the sidebar account block and chat user-message avatars.

## Design Tokens
- `--navy: #0F1B2D`, `--orbit: #3A5BA0`, `--mist: #A7C7F7`, `--line` (hairline), `--slate`, `--gray` — see `styles.css`
- Connected green: `#2F7A3B`
- Fonts: Inter (UI text), Sora (avatar initials, display)

## Files
- `chat.jsx` — chat screen reference (see `FFMessage`, message list container, composer)
- `shell.jsx` — sidebar (account footer w/ presence) and top bar reference
- `styles.css` — design tokens

## Acceptance checklist
- [ ] Chat bubbles at the new compact metrics (26px avatars, 12px message gap, 13.5px text)
- [ ] User message avatar === profile avatar everywhere (no placeholder initial)
- [ ] Sidebar footer shows avatar + presence dot + "Connected" line + settings
- [ ] Top bar has no avatar/connection/settings
- [ ] Disconnected state styled (gray dot, "Offline")
