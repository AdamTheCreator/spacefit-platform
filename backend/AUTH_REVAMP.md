# Auth & User-Management Revamp — Design (Phase 2)

Status: **proposed, awaiting approval**. No production behavior changes until approved.
Scope: authentication + user management only. Incident fixes already shipped in Phase 1
(email normalization, non-silent sends, migration `040`).

---

## 1. Recommendation: harden in-house (do **not** adopt a managed provider)

### Path A — Managed provider (Clerk / Auth0 / Supabase Auth / WorkOS)
Offloads email delivery, sessions, recovery. **Rejected for this stack** because:
- `users.id` is a first-class foreign key across ~15 tables (subscriptions, BYOK
  `user_ai_configs`, chat, documents, contacts, deals, memory, refresh tokens…). A
  provider owns identity in *their* store, forcing either a permanent id-mapping shim or
  a full data migration.
- Google OAuth **and** Gmail-send OAuth already flow through `app/api/auth.py` +
  `app/services/gmail.py` (tokens stored on `oauth_accounts`). A provider would fork
  identity from the Gmail-outreach token store.
- BYOK's zero-platform-tokens guarantee and per-user encryption (`app/byok/crypto.py`)
  are bespoke and stay ours regardless.
- Net: provider migration is weeks of coupling work to replace a codebase that is
  already ~80% of a correct in-house implementation.

### Path B — Harden in-house (**recommended**)
The current design is close: JWT access + rotating refresh, hashed single-use reset
tokens, 1h expiry, enumeration-safe reset response. The real gaps are: weak hash
(bcrypt, no rehash path), no rate-limit/lockout, no audit log, no email-send alerting,
and an OAuth callback that ships tokens in the URL. All are additive, feature-flaggable
hardening. **This is the plan below.**

---

## 2. Design

### 2.1 Password hashing — argon2id + transparent rehash-on-login
- Switch `pwd_context` to `CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")`.
  New hashes are argon2id; legacy bcrypt hashes still **verify**.
- Add `argon2-cffi` to `pyproject.toml`.
- Rehash-on-login: after a successful `verify_password`, if `pwd_context.needs_update(hash)`
  is true, re-hash the plaintext and persist. No forced mass reset.
- Fixes the latent bcrypt 72-byte silent-truncation by moving default to argon2 (and we
  already enforce an 8-char min at the schema).

### 2.2 Sessions — keep short-lived JWT + rotating refresh (justified), harden it
Chosen over httpOnly cookies **for this stack**: the SPA authenticates the chat
**WebSocket** with a bearer token and the axios interceptor already implements silent
refresh; cookie-only auth would need CSRF tokens, a cookie-capable WS handshake, and a
rewrite of `src/lib/axios.ts` + `useChat.ts`. Bearer JWT + refresh rotation is the
lower-risk, in-grain choice. Hardening:
- **Refresh reuse detection:** refresh tokens already rotate (old marked `revoked`). Add:
  if a *revoked* refresh token is presented, treat it as theft → revoke the whole family
  (all of that user's refresh tokens) and force re-login. (Requires a `family_id` /
  `replaced_by` column.)
- Store the **full** token hash for lookup (today lookup is by `jti = hash[:16]`
  prefix-match; move to exact hash match to remove any prefix-collision surface).
- **Fix OAuth callback token leak:** `google_callback` currently 302-redirects with
  `?access_token=…&refresh_token=…` in the URL (lands in browser history / referrer /
  server logs). Replace with a short-lived one-time `auth_code` the SPA exchanges via a
  `POST /auth/oauth/exchange` for tokens. (Flagged as a security issue — see §6.)

### 2.3 Password reset flow (mostly correct today; close the gaps)
- Keep: `secrets.token_urlsafe(32)`, store only SHA-256 hash, 1h expiry, single-use,
  enumeration-safe `202`.
- Add: on reset **and** on any password change, invalidate *all* outstanding
  `password_reset` tokens for that user + revoke all refresh tokens (log the user out
  everywhere).
- Add: per-email **and** per-IP rate limit on `forgot-password` (see §2.5).

### 2.4 Email verification on signup
- Verification already exists. Do **not** hard-block login initially (would strand
  existing unverified accounts). Instead:
  - Add `POST /auth/resend-verification` (rate-limited, enumeration-safe).
  - Surface an unverified banner in the SPA; gate only sensitive actions later.
  - Config flag `require_verified_email_for_login` (default `false`) so we can flip to a
    hard gate once the base is verified.

### 2.5 Rate limiting + progressive lockout
- Reuse the existing in-memory sliding-window pattern (`MessageRateLimiter` /
  `_IPRateLimiter`) — consistent with the repo; **note: per-process memory, swap for
  Redis when we scale horizontally** (same caveat already documented for sales/BYOK).
- **Login:** per-IP and per-account counters. After N failures (default 5 / 15 min),
  return `429` with `Retry-After` and a progressive backoff. Lockout returns a
  **distinct 429** ("too many attempts, try again in N min"), never a masked
  `401 invalid credentials`, so it can't be confused for a wrong password (this was an
  explicit incident-diagnosis item).
- **Reset / resend-verification:** per-email + per-IP cap (default 3 / 15 min).

### 2.6 Observability — audit log + alerting (never silent-fail again)
- New table `auth_events` (see §3): append-only rows for `login`, `login_failed`,
  `reset_requested`, `reset_completed`, `password_changed`, `email_verified`,
  `account_locked`, `refresh_reuse_detected`. Columns: user_id (nullable), event,
  ip, user_agent, request_id, detail (free-form text), created_at. **Never** stores passwords,
  tokens, or reset links.
- Structured logger events on the same actions (already added `auth.email.send_failed`
  / `auth.email.not_configured` in Phase 1).
- Email-send failure is now `logger.error`; add an optional alert sink (Sentry/webhook)
  behind `AUTH_ALERT_WEBHOOK_URL` (no-op if unset).

### 2.7 UI error states
- Reset/forgot already show "if an account exists…". Add: login lockout message
  (429 → "Too many attempts, try again in N minutes"), unverified-email banner + resend
  button, and a "you were signed out everywhere" note after password change.

### 2.8 Secrets / config
- All secrets stay in env (`.env` local, Render dashboard prod). No secrets committed.
- Boot-time warning if `resend_api_key` is empty while `debug=false` (prod misconfig is
  loud, not silent).
- Documented required vars per environment in the runbook (§5 of Phase 3).

---

## 3. Data model changes (new Alembic migrations, forward-only)
1. `auth_events` table (append-only audit log; indexed on `user_id`, `event`, `created_at`).
2. `refresh_tokens`: add `family_id` + `replaced_by_id` (nullable) for reuse detection.
3. `users`: add `password_changed_at` (nullable timestamp) for audit + "logout everywhere"
   correctness.
- All additive/nullable. `email_tokens` already fits reset + verify.
- **Prereq:** resolve the pre-existing duplicate `039` revision id before running any of
  these (flagged in Phase 1).

## 4. Migration plan for existing users
- **Hashes:** no forced reset. argon2 becomes default; bcrypt kept in the verify list;
  users transparently upgraded on next login via `needs_update`.
- **Emails:** already normalized by migration `040`.
- **Sessions:** existing refresh tokens keep working (new columns nullable; a null
  `family_id` is treated as its own family).
- **Verification:** existing unverified users are unaffected (login not hard-gated).

## 5. Rollback plan
- **Hashing:** rollback = flip the *default* scheme back to bcrypt **but keep argon2 in
  the schemes list** so any argon2 hashes written during the window still verify. (Never
  remove argon2 from schemes once shipped, or those users lock out.)
- **Rate limit / lockout / verification gate:** all behind config flags
  (`auth_login_rate_limit`, `require_verified_email_for_login`, etc.) — set to disabled to
  revert behavior instantly, no deploy.
- **OAuth exchange:** ship behind a flag; if the SPA exchange path regresses, flip back to
  the legacy redirect temporarily.
- **Audit table + admin endpoints:** purely additive; rollback = stop reading/writing,
  leave the table in place.

## 6. Security issues flagged (some out of the strict scope, surfaced per guardrails)
1. **OAuth callback leaks tokens in the redirect URL** (`app/api/auth.py::google_callback`)
   — access + refresh tokens land in browser history / referrer headers / any proxy log.
   Fix in §2.2 (one-time code exchange). **High priority.**
2. **JWT `secret_key` / `encryption_master_key` default to dev placeholders** in
   `config.py`. Add a boot-time assertion that they are non-default when `debug=false`.
3. Refresh-token lookup uses a **16-char prefix match** (`jti = hash[:16]`) rather than the
   full hash — tighten to exact match (§2.2).
4. Tokens are stored in `localStorage` (XSS-exposed). Accepted for now given the WS/axios
   coupling; documented as the tradeoff for keeping bearer auth.

## 7. Implementation order (Phase 3, small reviewable commits)
1. argon2 + rehash-on-login (+ dep, unit tests).
2. `auth_events` table + audit writes + login/reset rate-limit & lockout.
3. Refresh reuse detection + exact-hash lookup + password-change "logout everywhere".
4. Resend-verification endpoint + config flags + boot-time secret/RESEND assertions.
5. OAuth one-time-code exchange (SPA + backend).
6. Admin/debug endpoints: user status lookup, resend verification, manually issue reset,
   recent auth events (built on existing `AdminUser` dep + `app/api/admin.py`).
7. Frontend error/verify/lockout states.
8. Runbook: required env vars per env, Resend setup, "user can't log in" triage.
