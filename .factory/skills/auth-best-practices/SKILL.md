---
name: auth-best-practices
description: Auth, user-management, and email-delivery standards for this repo. Use when touching login, password reset, email verification, session tokens, rate limiting, or the users table. Includes a pre-merge checklist and a login/reset triage runbook.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Execute
version: 1.0.0
---

# Auth Best Practices

Standards for any change touching authentication, user management, email
delivery, or the `users` table in this repository. Apply these whenever you
add or modify login, password reset, email verification, session tokens,
rate limiting, or audit logging.

## 1. Password hashing

- **Default: argon2id.** `passlib.CryptContext(schemes=["argon2", "bcrypt"],
  deprecated="auto")` in `app/core/security.py`. New hashes are argon2id.
- **Never remove bcrypt from the schemes list** or pre-argon2 accounts lock
  out. Bcrypt hashes still verify and are transparently upgraded.
- **Rehash-on-login:** after a successful `verify_password`, call
  `password_needs_rehash(hash)`. If true, re-hash the plaintext with the
  current default and persist. No forced mass password resets.
- Minimum password length is 8 (enforced at the Pydantic schema level).

## 2. Email normalization

- All email inputs are normalized via `normalize_email()` (trim + lowercase)
  at the API boundary using Pydantic `field_validator(mode="after")` on
  `UserBase`, `LoginRequest`, `ForgotPasswordRequest`, and
  `ResendVerificationRequest`.
- OAuth emails are normalized in `AuthService.get_or_create_oauth_user`.
- Signup and login must apply the same normalization or a casing mismatch
  silently fails to match the stored record.

## 3. Session management (JWT + rotating refresh)

- Short-lived JWT access token (15 min) + rotating refresh token (7 days).
  Bearer tokens in `localStorage` (accepted tradeoff for the WebSocket +
  axios silent-refresh coupling; cookies would need CSRF + WS-handshake rewrite).
- **Refresh rotation:** each use revokes the presented token and issues a
  successor in the same `family_id`, linked via `replaced_by_id`.
- **Reuse detection:** if a revoked refresh token is presented again, revoke
  the entire family and force re-login. Record `refresh_reuse_detected` in
  the audit log.
- **Exact-hash lookup:** the JWT `jti` carries the full SHA-256 token hash;
  the DB lookup is an exact match, never a prefix match.
- **Password change / reset revokes all sessions:** `revoke_all_refresh_tokens`
  is called on both `update_password` and `reset_password_with_token`.

## 4. Password reset flow

- Token: `secrets.token_urlsafe(32)`, store only SHA-256 hash in
  `email_tokens.token_hash`. Never store or log the raw token.
- Expiry: 1 hour. Single-use (`used_at` stamped on redemption).
- On use: invalidate all other outstanding reset tokens for that user.
- Identical `202` response whether or not the email exists (no enumeration).
- Link URL built from `settings.frontend_url` (must match the environment).

## 5. Email verification

- Token generation and storage identical to reset tokens (hashed, 24h expiry,
  single-use).
- `POST /auth/resend-verification` is enumeration-safe and rate-limited.
- Login hard-gate behind `require_verified_email_for_login` config flag
  (default `false` so existing unverified users are not stranded).

## 6. Rate limiting + progressive lockout

- In-memory sliding-window pattern (per-process; swap for Redis when scaling
  horizontally — same caveat as the sales/BYOK limiters).
- **Login:** per-email AND per-IP. After N failures (default 5 / 15 min),
  lock the key out with progressive backoff (doubles up to a cap).
- **Lockout returns 429 + Retry-After**, never a masked 401, so it cannot
  be confused with a wrong password.
- **Reset / resend-verification:** per-email + per-IP cap (default 3 / 15 min).
- All behind `auth_rate_limit_enabled` config flag (instant rollback).

## 7. Account enumeration prevention

- `forgot-password` and `resend-verification` always return the same neutral
  message regardless of whether the account exists.
- Login returns a generic "Invalid email or password" (never "user not found"
  vs "wrong password").
- Rate-limited endpoints return the same response shape whether or not the
  limit was hit (the send is skipped but the 202 is identical).

## 8. Observability (never silent-fail)

- **Email sends:** the boolean return of `send_verification_email` /
  `send_password_reset_email` is checked. On `False`, emit a structured
  `logger.error("auth.email.send_failed event=… user_id=…")`. The missing-key
  branch logs `auth.email.not_configured` at ERROR level (not a quiet warning).
- **Audit log:** `auth_events` table records: `login`, `login_failed`,
  `reset_requested`, `reset_completed`, `password_changed`, `email_verified`,
  `account_locked`, `refresh_reuse_detected`. Columns: user_id (nullable),
  event, ip_address, user_agent, request_id, detail, created_at.
- **Never** log passwords, tokens, reset links, or full email addresses in
  audit rows or log lines. Use `user_id` for correlation.
- **Boot-time config check:** `check_auth_config()` in `app/core/config.py`
  logs CRITICAL if `SECRET_KEY` / `ENCRYPTION_MASTER_KEY` are at dev defaults
  in prod, and WARNING if `RESEND_API_KEY` is unset.

## 9. OAuth security

- Google callback uses a **one-time code exchange** (`oauth_code_store`):
  the callback redirects with a single-use code, and the SPA exchanges it
  via `POST /auth/oauth/exchange`. Tokens never appear in the URL.
- Legacy redirect path is kept behind `oauth_code_exchange_enabled` flag
  for rollback.
- OAuth email is normalized via `normalize_email()`.

## 10. Frontend auth-endpoint error handling

- The axios interceptor must **not** run the refresh-and-redirect dance for
  auth endpoints themselves (`/auth/login`, `/auth/register`, etc.). A 401
  from login is a real error to display, not an expired session. The
  `isAuthEndpoint` regex check in `src/lib/axios.ts` guards this.
- Both `access_token`/`refresh_token` and `auth-storage` (zustand persist)
  must be cleared together on auth failure (see CLAUDE.md auth-flow gotcha).

---

## Pre-merge checklist

Run through this list for any PR touching auth, email delivery, or user
records. If any item is unchecked, do not merge.

- [ ] Passwords hashed with argon2id (or bcrypt kept in verify list for legacy).
- [ ] No passwords, tokens, or reset links logged anywhere (audit rows, log
      lines, error messages, exception details).
- [ ] Email inputs normalized (trim + lowercase) at the API boundary.
- [ ] Reset/verification tokens are single-use, short-expiry, hash-only storage.
- [ ] Forgot-password / resend-verification return identical responses
      regardless of account existence (no enumeration).
- [ ] Email send failures are logged at ERROR level (never silent / warning-only).
- [ ] Auth events written to `auth_events` audit table for login, failed login,
      reset, password change, lockout.
- [ ] Rate limiting applied to login and reset/resend endpoints.
- [ ] Lockout returns 429 + Retry-After (never a masked 401).
- [ ] Password change/reset revokes all refresh tokens for the user.
- [ ] New config flags have sensible defaults (feature can be instantly rolled
      back without a deploy).
- [ ] No secrets committed (API keys, JWT secrets, encryption keys are env-only).
- [ ] If a new migration was added: forward-only, never edit a committed
      migration, collision-safe if touching unique columns.
- [ ] `ruff check .` introduces zero new violations on touched files.
- [ ] `mypy app` introduces zero new errors on touched files.
- [ ] `pytest tests/` passes (including the auth tests in
      `test_auth_email.py`, `test_auth_hardening.py`, `test_auth_flow_db.py`).
- [ ] `npm run build` (frontend) passes with no new type errors.

---

## Triage runbook: "user can't log in"

1. **Look up the account** (admin):
   `GET /api/v1/admin/users/lookup?email=<email>`.
   Check `is_active`, `email_verified`, `has_password`, `oauth_providers`,
   `active_sessions`, `password_changed_at`.
   - No record → different environment or never registered.
   - `has_password=false` + OAuth provider → must use "Sign in with Google".
   - `is_active=false` → account disabled.

2. **Reset email never arrived:** check server logs for
   `auth.email.send_failed` or `auth.email.not_configured`. If configured,
   check the Resend dashboard for bounces, sandbox restrictions, or unverified
   recipient. Verify the sender domain (SPF/DKIM/DMARC) in Resend. Confirm
   `RESEND_API_KEY` is set and `RESEND_FROM_EMAIL` is on a verified domain.

3. **Password rejected:** email is normalized (trim + lowercase) at signup
   and login, so casing is not the cause. Legacy bcrypt hashes upgrade to
   argon2id transparently on the next successful login. Check
   `password_changed_at` to see if a recent reset changed the password.

4. **Locked out:** repeated failures return 429 + Retry-After. Inspect
   `GET /api/v1/admin/users/{id}/auth-events` for `login_failed` /
   `account_locked`. Lockout state is in-memory and clears after the window
   or on a process restart.

5. **Unblock actions (admin):**
   - `POST /api/v1/admin/users/{id}/issue-reset` — emails a reset link
     (the link is emailed to the user only; never returned or logged).
   - `POST /api/v1/admin/users/{id}/resend-verification` — re-sends
     verification email.

---

## Key files

| File | Purpose |
| --- | --- |
| `app/core/security.py` | Hashing (argon2id + bcrypt), JWT creation/verification, `password_needs_rehash` |
| `app/services/auth.py` | AuthService: register, authenticate, token rotation, reset, verification, session revocation |
| `app/services/email_service.py` | Resend-based verification + reset email sends (non-silent) |
| `app/services/auth_audit.py` | `record_auth_event` — best-effort audit log writes |
| `app/services/auth_rate_limit.py` | `LoginLockout` (progressive) + `SlidingWindowLimiter` (reset/resend) |
| `app/services/oauth_exchange.py` | One-time OAuth code store |
| `app/api/auth.py` | Auth endpoints (login, register, reset, verify, resend, OAuth exchange) |
| `app/api/admin.py` | Admin debug endpoints (user lookup, auth status, auth events, issue reset, resend verification) |
| `app/db/models/auth_event.py` | `AuthEvent` audit table model + event name constants |
| `app/db/models/user.py` | `User`, `RefreshToken` (with `family_id`/`replaced_by_id`), `OAuthAccount` |
| `app/db/models/email_token.py` | `EmailToken` (verification + reset tokens, hash-only) |
| `app/core/config.py` | Auth config flags + `check_auth_config()` boot-time check |
| `alembic/versions/040_lowercase_user_emails.py` | Email normalization backfill migration |
| `alembic/versions/041_auth_hardening.py` | Audit table + refresh lineage + password_changed_at migration |
| `AUTH_REVAMP.md` | Design doc for the revamp |
| `AUTH_RUNBOOK.md` | Operational runbook (env vars, Resend setup, triage) |
