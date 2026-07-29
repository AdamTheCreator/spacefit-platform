# Auth & User-Management Runbook

Operational reference for the hardened auth layer (Phases 1–3). Companion to
`AUTH_REVAMP.md` (design) and the `auth-best-practices` skill (standards).

## Required environment variables

| Var | Purpose | Local dev | Production (Render) |
| --- | --- | --- | --- |
| `SECRET_KEY` | JWT signing | any 32+ char string | **must be a strong random value** (boot logs `CRITICAL` if left default) |
| `ENCRYPTION_MASTER_KEY` | credential encryption | dev default OK | **must be non-default** (boot logs `CRITICAL` otherwise) |
| `RESEND_API_KEY` | transactional email (verify + reset) | optional (sends no-op, logs `auth.email.not_configured`) | **required** or reset/verify emails never send |
| `RESEND_FROM_EMAIL` | sender address | `noreply@spacegoose.ai` | must be on a **verified** Resend domain |
| `FRONTEND_URL` | base for links in emails + OAuth redirect | `http://localhost:5173` | `https://spacegoose.ai` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Google OAuth | optional | required for Google sign-in |

Optional tuning (sane defaults in `app/core/config.py`): `AUTH_RATE_LIMIT_ENABLED`,
`AUTH_LOGIN_MAX_ATTEMPTS` (5), `AUTH_LOGIN_WINDOW_SECONDS` (900),
`AUTH_LOGIN_LOCKOUT_SECONDS` (900), `AUTH_RESET_MAX_ATTEMPTS` (3),
`AUTH_RESET_WINDOW_SECONDS` (900), `REQUIRE_VERIFIED_EMAIL_FOR_LOGIN` (false),
`OAUTH_CODE_EXCHANGE_ENABLED` (true), `AUTH_ALERT_WEBHOOK_URL` (empty).

## Email provider (Resend) setup

1. Create the API key in Resend; set `RESEND_API_KEY` in the Render dashboard
   (it is `sync: false` in `render.yaml`, i.e. never committed).
2. **Verify the `spacegoose.ai` sender domain** in Resend and add the SPF, DKIM,
   and DMARC DNS records. Until verified, Resend only delivers to the account
   owner's own address (test mode) and silently drops everything else.
3. Confirm `RESEND_FROM_EMAIL` is on that verified domain and `FRONTEND_URL`
   matches the environment.
4. Verify: trigger `POST /auth/forgot-password` for a known address and confirm
   delivery. If it fails, the server logs `auth.email.send_failed` /
   `auth.email.not_configured` (they are no longer silent).

## Migrations

Run `alembic upgrade head` on deploy (the container does this on boot). Relevant:
- `040` — lowercases existing user emails (collision-safe; aborts listing any
  case-variant duplicates to merge first).
- `041` — `auth_events` audit table + `refresh_tokens.family_id/replaced_by_id`
  + `users.password_changed_at`.

> Prereq: resolve the duplicate `039` revision id (committed
> `039_document_indexed_at.py` vs untracked `039_add_campaign_deal_link.py`)
> before running migrations, or Alembic errors on multiple heads.

## Triage: "a user can't log in"

1. **Look up the account** (admin): `GET /api/v1/admin/users/by-email?email=<email>`.
   Check `is_active`, `email_verified`, `has_password`, `oauth_providers`,
   `active_sessions`, `password_changed_at`.
   - No record → they signed up in a different environment / never registered.
   - `has_password=false` + an OAuth provider → they must use "Sign in with Google".
   - `is_active=false` → account disabled.
2. **Reset email never arrived:** check logs for `auth.email.send_failed` /
   `auth.email.not_configured`. If configured, check the Resend dashboard for
   bounces / sandbox restrictions / unverified recipient. Verify the sender
   domain (SPF/DKIM/DMARC).
3. **Password rejected:** email is normalized (trim + lowercase) at signup and
   login, so casing is not the cause post-`040`. Legacy bcrypt hashes upgrade to
   argon2id transparently on the next successful login.
4. **Locked out:** repeated failures return `429` + `Retry-After` (a distinct
   lockout, never a masked 401). Inspect `GET /api/v1/admin/users/{id}/auth-events`
   for `login_failed` / `account_locked`. Lockout state is in-memory and clears
   after the window or on a process restart.
5. **Unblock actions (admin):**
   - `POST /api/v1/admin/users/{id}/issue-reset` — emails a reset link (the link
     is emailed to the user only; never returned or logged).
   - `POST /api/v1/admin/users/{id}/resend-verification` — re-sends verification.

## Security notes

- Never log passwords, tokens, or reset links. Audit rows in `auth_events` store
  only event name, IP, user-agent, request id, and a short non-sensitive detail.
- OAuth sign-in hands the SPA a single-use code (`/auth/oauth/exchange`) instead
  of putting tokens in the redirect URL.
- Refresh tokens rotate on use; replaying a rotated token revokes the whole
  family (`refresh_reuse_detected`). Password change/reset revokes all sessions.
- Rate-limit / lockout / OAuth-code state is per-process in-memory; **move to
  Redis when scaling to multiple workers.**
