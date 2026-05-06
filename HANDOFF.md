# AIDSTATION — Session Handoff

**Date:** 2026-05-06
**Last commit on `main`:** `0f6bb36` (DATABASE.md merge). The branch
`claude/csp-nonces` (PR #17, head `29bcae5`) is the tip of this
session's security stack. Stack base is the previous handoff merge
`aebb6b1`. Seven PRs on this stack, intended to merge in order.

**This session in one line:** the entire 10-item security backlog
from the previous handoff shipped as seven stacked PRs (#11–#17).

**Deploy state:**
- ✅ Vercel: still on `0f6bb36` until the security stack merges. Once
  it does, all seven preview deploys are already verified green
  (Vercel build success on each).
- ✅ TrueNAS: same — Watchtower will pull on push to `main`.

**Next focus (per Andy):** open question. Security is closed. Suggest
**HANDOFF.md → DATABASE.md sync** (this doc reflects new schema; the
DATABASE.md table catalog is now a session behind), and then either
the multi-day wellness chart from the original code backlog, or
content work on `init_db.py:PURCHASE_RECOMMENDATIONS`.

---

## ⚠️ Database changes this session

Two new tables and one altered cascade chain. Both schemas (SQLite
and Postgres) ship the additions; the migrations are
idempotent (`CREATE TABLE IF NOT EXISTS`) so existing deploys pick
them up on next cold start.

### New: `admin_audit` (PR #12)

Append-only log of admin actions. Currently written from
`routes/admin.delete_user`, captured in the same transaction as the
delete so the audit trail and the deletion succeed/fail together.

```
admin_audit
  id              INTEGER / SERIAL  PK
  actor_user_id   INTEGER          REFERENCES users(id) — NULL if actor was later deleted
  action          TEXT             e.g. 'delete_user'
  target_user_id  INTEGER          plain INT (no FK) so row survives target deletion
  target_username TEXT             snapshotted at delete time
  details         TEXT             optional JSON / freetext payload
  created_at      TIMESTAMP        default NOW() / datetime('now')

  INDEX admin_audit_created_at_idx ON admin_audit(created_at DESC)
```

**Convention:** any new admin route that mutates state should write a
row here with a fresh `action` string. Read access through a future
`/admin/audit` view; not built yet.

### New: `api_tokens` (PR #15)

Per-user bearer tokens for headless access to `/coaching/api/*`
(currently `/coaching/api/generate` and `/coaching/api/review`).

```
api_tokens
  id           INTEGER / SERIAL  PK
  user_id      INTEGER  NOT NULL  REFERENCES users(id)
  name         TEXT     NOT NULL  user-supplied label
  token_hash   TEXT     NOT NULL UNIQUE  SHA-256 hex of plaintext
  created_at   TIMESTAMP NOT NULL default NOW() / datetime('now')
  last_used_at TIMESTAMP          updated on every successful verify
  revoked_at   TIMESTAMP          soft-revoke; preserves audit trail

  INDEX api_tokens_user_id_idx ON api_tokens(user_id)
```

**Storage convention:** plaintext is shown to the user **once** at
creation (passed through one-shot `flask_session['new_api_token_plaintext']`)
and never persisted. We store SHA-256 of `aid_<base64url(32)>`.
SHA-256 (not bcrypt) is fine — tokens are 32 bytes of cryptographic
random, no brute-force surface. Verification: SHA-256 the inbound
header value, look up by `token_hash`, check `revoked_at IS NULL`.

### Updated cascade-delete chain (PR #15)

`routes/admin._delete_user_and_data` picks up `api_tokens` before
`users`. Other tables unchanged. New tables added in this session
(`api_tokens`) **must** also be added to this chain — `admin_audit`
intentionally is **not** in the chain because we want the audit row
to survive admin deletion (target_user_id is FK-less for the same
reason).

### What didn't change in the schema

No column additions, no index changes on existing tables, no new
constraints, no data migrations. `password_resets` (the previous
session's addition) is unchanged. The new tables add ~6 KB to the
schema and zero ongoing cost until they're written to.

---

## What shipped this session

Seven PRs on the security stack:

**`a379a8e` — PR #11 — Security pass: SECRET_KEY, CSRF, rate limits,
cookie hardening.**
- `SECRET_KEY` is now mandatory: `app.py` raises `RuntimeError` on
  boot if unset (no more `'ar-training-2026'` default). Both deploys
  already have it set.
- Flask-WTF `CSRFProtect` on every state-changing form. `<meta
  name="csrf-token">` in `base.html` + `auth/_shell.html`; hidden
  `csrf_token` input added to all 34 form templates. `static/app.js`
  wraps `fetch` to inject `X-CSRFToken` on same-origin
  POST/PUT/PATCH/DELETE.
- Flask-Limiter on the auth blueprint:
  - `/auth/login` — 10 / 5 min
  - `/auth/register` — 10 / hour
  - `/auth/forgot` — 5 / 15 min
  - `/auth/reset` — 10 / 15 min
  In-process memory store; swap in Redis via `RATELIMIT_STORAGE_URI`
  if scaling out.
- `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`.
  `SESSION_COOKIE_SECURE` defaults on when `DATABASE_URL` is set
  (proxy for the HTTPS-fronted Vercel deploy). Override via env var.

**`c4c3ff7` — PR #12 — Easy security headers + admin audit + FIT
filename sanitization.**
- `after_request` hook on every response:
  `X-Content-Type-Options=nosniff`, `X-Frame-Options=DENY`,
  `Referrer-Policy=strict-origin-when-cross-origin`,
  `Permissions-Policy` revoking geolocation/mic/camera/payment/usb.
  Set with `setdefault` so a route can still override.
- `admin_audit` table (see DB section above) + write on
  `delete_user`.
- `werkzeug.secure_filename` applied at every `request.files` read in
  `routes/garmin` (`debug_fit`, `import_fit`, `import_wellness`).

**`b25c8a6` — PR #13 — Password strength via zxcvbn.**
- `MIN_PASSWORD_SCORE = 3` (zxcvbn 0–4, "safely unguessable") on
  `/auth/register`, `/auth/reset`, and `/profile/password`.
- Username, email, and display name fed in as `user_inputs` so
  passwords incorporating the user's identifiers get penalized.
- zxcvbn's `feedback.warning` and `feedback.suggestions` surfaced via
  `flash()` so rejected users get useful guidance.
- Keeps the 8-char short-circuit lower bound as a fast-path.
- New dep: `zxcvbn>=4.4.28`.

**`780fe18` — PR #14 — Content-Security-Policy baseline (with
`'unsafe-inline'` initially).**
- Wires CSP into the same `after_request` hook. Operator escape
  hatch: `CSP_REPORT_ONLY=1` flips to
  `Content-Security-Policy-Report-Only`.
- Even with `'unsafe-inline'` on script-src/style-src, the rest of
  the directives close real exfiltration vectors (connect-src,
  img-src, form-action, frame-ancestors, base-uri, object-src,
  upgrade-insecure-requests on HTTPS).
- *Superseded by PR #17 for `script-src` — see below.*

**`721b770` — PR #15 — API tokens / bearer auth on `/coaching/api/*`.**
- New `api_tokens` table (see DB section).
- `app._require_login` tries `Authorization: Bearer <token>` before
  the session, short-circuits the gate on a hit, and updates
  `last_used_at` on every successful verify.
- `current_user_id()` reads `g.api_user_id` first, so token-authed
  callers see the same per-user scoping as session-authed ones.
- `/coaching/api/generate` and `/coaching/api/review` exempted from
  CSRFProtect — bearer auth isn't reachable from a cross-origin
  form.
- New "API access" tab on `/profile` for token CRUD; plaintext shown
  once on creation via a one-shot `flask_session` value.

**`7eace11` — PR #16 — `SECRET_KEY_FALLBACK` env var for graceful
rotation.**
- Reads `SECRET_KEY_FALLBACK` (comma-separated for multi-step
  rotations) from env and stashes the parsed list on
  `app.config['SECRET_KEY_FALLBACKS']`. Flask 2.3+ verifies cookies
  against any fallback; signs new ones with `SECRET_KEY`.
- Operator workflow:
  1. Set `SECRET_KEY=<new>` and `SECRET_KEY_FALLBACK=<old>`.
     Redeploy. Existing sessions stay valid.
  2. After drain window (24h or whatever), drop
     `SECRET_KEY_FALLBACK` and redeploy. Old cookies invalid.

**`29bcae5` — PR #17 — CSP nonces: drop `'unsafe-inline'` from
script-src.**
- `script-src 'self' 'nonce-<per-request>' https://cdn.jsdelivr.net`.
  Every inline `<script>` block in templates renders
  `nonce="{{ csp_nonce() }}"`; the `before_request` hook generates a
  fresh 16-byte base64url nonce per request.
- 33 inline event handlers (`onclick`, `onsubmit`, `onchange`)
  refactored across 22 templates:
  - 17× `onsubmit/onclick="return confirm('...')"` → `data-confirm="..."`
    with a delegated handler in `static/app.js`.
  - `onchange="this.form.submit()"` → `data-autosubmit` (also
    delegated).
  - Function-call handlers → `addEventListener` inside the
    template's existing nonce'd `<script>` block.
  - `training/session_form` had `onclick=...` injected via
    `innerHTML` template literal — those don't inherit the page
    nonce; rewrote to `data-exercise` + class-based delegation.
- `style-src` keeps `'unsafe-inline'` (inline `style="..."` is
  pervasive; refactor is its own session).

---

## Carry-forward operator items

### Tabled — pending operator action

**SendGrid setup** *(unchanged from previous handoff)* — PR #8
shipped the email helper + password reset code; live deploy still
logs reset links to stdout. Same setup steps:

1. sendgrid.com (free tier: 100/day).
2. Verify a sender.
3. Restricted-Access API key, Mail Send → Full Access.
4. `SENDGRID_API_KEY=...`, `EMAIL_FROM_ADDRESS=...` (and optionally
   `EMAIL_FROM_NAME`).
5. Vercel: redeploy. TrueNAS: `cd /mnt/storage/exercise && docker
   compose up -d`.

Until configured, password-reset is functionally unavailable to
anyone without shell access to the function logs.

### Optional spot-checks on the live site after the security stack lands

- Sign in / sign out: confirm the Sign-out form still works (CSRF
  hidden input added in PR #11).
- `/admin/`: delete a throwaway user, then `SELECT * FROM admin_audit
  ORDER BY id DESC LIMIT 1` — confirm a row landed with
  `actor_user_id=1`, `action='delete_user'`.
- `/profile/` API access tab: create a token. Confirm the plaintext
  is shown exactly once and is empty after page reload.
- `curl -X POST .../coaching/api/generate -H "Authorization: Bearer aid_..."`
  with the new token — confirm the plan generates.
- Browser devtools console on every section: should be **zero CSP
  violations**. If any fire, set `CSP_REPORT_ONLY=1` while
  debugging.
- Try a deliberately weak password on `/profile/password` (e.g.
  `password`) — should get rejected with the zxcvbn warning string.
- Auth rate-limiting: deliberately mistype the login password 11
  times — should get a 429 on the 11th.

---

## What's currently live

All shipped from the multi-user retrofit (Sessions 0–4) plus the
previous session's coaching/admin/email work, plus this session's
security stack:

- Multi-user auth, bcrypt, per-request user-row hydration.
- Per-user data isolation across 25+ scoped tables. Composite
  UNIQUEs for UPSERT idempotency.
- Strength training pipeline (`rx_engine.apply_session_outcome`),
  cardio log, conditions log, plans + auto-match, coaching with
  prompt cache, Garmin Connect import.
- Admin dashboard + cascade-delete + (post-merge) audit log.
- Password reset flow (email-blocked).
- Recommended-purchases catalog, locations, athlete profile.
- **Security baseline (post-merge of this session's stack):**
  mandatory `SECRET_KEY` with rotation drain, CSRF on every form,
  rate limits on auth, hardened session cookies, defensive HTTP
  headers, CSP with nonces (no `'unsafe-inline'` on script-src),
  zxcvbn password policy, secure_filename on uploads, admin audit
  log, per-user API tokens for `/coaching/api/*`.

---

## Code backlog

### Security tail (small, optional)

- **CSP `style-src` nonces.** Drop `'unsafe-inline'` from style-src.
  Touches every template with an inline `style="..."` attribute and
  is its own session. Lower priority than scripts because the XSS
  surface for inline styles is narrower.
- **Token expiry on `api_tokens`.** Currently no `expires_at`
  enforcement; revocation is the only way to invalidate. Add
  optional TTL on creation if desired.
- **`/admin/audit` view.** Write-only today; build a read view when
  the log accumulates anything interesting.

### Standalone, no dependencies

- **Multi-day wellness chart** on `/garmin/wellness` (~2h, top of the
  original backlog). Still tabled.
- **Purchases catalog curation** in `init_db.py:PURCHASE_RECOMMENDATIONS`.
  Iterative content work.

### Dependent on SendGrid

- **Email invites flow.** Admin form → invite token → emailed
  registration link bypassing `ALLOW_REGISTRATION=0`.
- **Email verification on signup.**
- **Password reset is functionally tabled until SendGrid is live.**

### Parked

- **Garmin per-user OAuth.** `garmin_auth` rows scoped per-user but
  `/tmp/garth_session` file caching is process-shared.
- **MFA (TOTP).** `pyotp` + setup on `/profile`.
- **Passkeys / WebAuthn.** Andy's preference; deferred for the
  WebAuthn flow complexity.
- **BYOK Anthropic API key.** Per-user override of the shared key.
- **Custom user-authored exercises.** Migrate `exercise_inventory`
  to nullable `user_id`.
- **SMS / WhatsApp invites.** Twilio is ~$1.15/mo + ~$0.008/msg.
  WhatsApp needs Meta Business API approval.

---

## Carry-forward issues to watch

1. **`RETURNING id` is the pattern.** Every INSERT whose new id is
   read back uses `RETURNING id`; `_CompatCursor.lastrowid`
   `fetchone()`s to surface it on Postgres.

2. **Auth gate hydrates the user row.** `app.py:_require_login` does
   one `users` SELECT per authed request and stashes on
   `g.current_user_row`. ⚠ **Updated this session:** the gate now
   tries `Authorization: Bearer <token>` first; on a hit it sets
   `g.api_user_id` and `g.api_authed = True` so `current_user_id()`
   resolves the same way as a session-authed request. New routes
   that need to know "session vs token" can read `g.api_authed`.

3. **`/coaching/api/*` endpoints accept bearer tokens now.** No more
   cookie-jar dance for external tooling.

4. **Brand CSS overrides Bootstrap aggressively.** Unchanged.

5. **`INSERT OR IGNORE`, `INSERT OR REPLACE`, and `datetime('now')`
   are SQLite-only.** Use `ON CONFLICT … DO NOTHING/UPDATE` and
   `CURRENT_TIMESTAMP` / `NOW()` instead. Unchanged.

6. **Postgres `TIMESTAMP` columns return `datetime`; SQLite's are
   TEXT.** Wrap `[:10]`-slicing with `|string`. Unchanged.

7. **SendGrid not configured yet.** Same status as previous handoff.

8. **`SECRET_KEY` is now required.** ✅ Done. Rotation has a drain
   mechanism via `SECRET_KEY_FALLBACK` (PR #16).

9. **CSP is enforced and uses nonces.** ⚠ **New:** any new template
   that inlines `<script>` content **must** render
   `nonce="{{ csp_nonce() }}"` on the tag. Inline event handlers
   (`onclick`, `onsubmit`, `onchange`, etc.) are blocked — use
   `addEventListener` from inside a nonce'd `<script>`, or one of
   the delegated patterns in `static/app.js`:
   - `<form data-confirm="...">` for submit-time prompts.
   - `<button data-confirm="...">` / `<a data-confirm="...">` for
     click-time prompts.
   - `<input data-autosubmit>` / `<select data-autosubmit>` to
     submit the enclosing form on change.
   Inline handlers injected via `innerHTML` template literals (see
   `training/session_form.html`) similarly do **not** inherit the
   page nonce; wire them with `addEventListener` after the
   `innerHTML =` assignment.

10. **CSRF tokens on every state-changing form.** ⚠ **New:** every
    `<form method="post">` template needs
    `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
    JS `fetch` POSTs to same-origin pick up `X-CSRFToken` from the
    `<meta name="csrf-token">` automatically via the `static/app.js`
    wrapper.

11. **Rate limits on auth endpoints.** ⚠ **New:** `/auth/login`
    (10/5min), `/auth/register` (10/hr), `/auth/forgot` (5/15min),
    `/auth/reset` (10/15min). Returns 429 once the budget's gone.
    Configured via `@_limit('...')` decorator in `routes/auth.py`;
    swap the storage backend with `RATELIMIT_STORAGE_URI`.

12. **`api_tokens` are SHA-256, not bcrypt.** Tokens are 32 bytes of
    crypto random — no brute-force surface, no need for slow
    hashing. Plaintext is shown once, then the user copies it.
    Don't change this to bcrypt; it would break verification (which
    needs a deterministic hash for lookup).

13. **`admin_audit` rows survive target deletion.** `target_user_id`
    is FK-less (plain INTEGER) by design. Don't add the FK.

---

## Architecture quick reference

For data-layer detail see `DATABASE.md` (note: pre-dates this
session's two new tables — `admin_audit` and `api_tokens` aren't in
the table catalog yet; the two definitions in `init_db.py` are the
source of truth until the doc is updated).

```
app.py              — Flask app; registers blueprints; runs DB init.
                      ⚠ NEW this session:
                        - SECRET_KEY required + SECRET_KEY_FALLBACKS
                        - SESSION_COOKIE_{SECURE,HTTPONLY,SAMESITE}
                        - CSRFProtect (Flask-WTF) + CSRFError handler
                        - Limiter (Flask-Limiter), in-memory by default
                        - before_request: per-request CSP nonce +
                          bearer-token auth path (g.api_user_id)
                        - after_request: defensive headers + CSP
database.py         — get_db(); SQLite + psycopg2; ?→%s; lastrowid via
                      RETURNING. Unchanged this session.
init_db.py          — SQLITE_SCHEMA, PG_SCHEMA, _SQLITE_MIGRATIONS,
                      _PG_MIGRATIONS. ⚠ NEW: admin_audit and
                      api_tokens tables added to both backends.
calculations.py     — Pure progression math. Unchanged.
rx_engine.py        — Single sanctioned writer to current_rx /
                      training_log / training_log_sets. Unchanged.
plan_match.py       — Auto-match + record_disposition. Unchanged.
coaching.py         — Claude API. Unchanged.
athlete.py          — get/upsert_athlete_profile. Unchanged.
email_helper.py     — send_email. Unchanged (still SendGrid-blocked).
garmin_fit_parser.py — parse_fit etc. Unchanged.
garmin_connect.py   — OAuth + activity fetch. Unchanged.
fit_workout_generator.py — generate_activity_fit. Unchanged.
routes/
  auth.py           — ⚠ NEW: zxcvbn _password_strength_errors,
                      generate_api_token, verify_bearer_token,
                      _hash_api_token. current_user_id reads
                      g.api_user_id first. Rate-limit decorators on
                      login/register/forgot/reset.
  admin.py          — ⚠ NEW: writes admin_audit row in delete_user
                      transaction. Cascade-delete picks up api_tokens.
  coaching.py       — ⚠ NEW: api_generate, api_review @csrf.exempt.
  garmin.py         — ⚠ NEW: secure_filename on every request.files
                      filename read.
  profile.py        — ⚠ NEW: API access tab + create_api_token,
                      revoke_api_token. zxcvbn check on
                      change_password.
  …rest unchanged.
templates/
  base.html         — ⚠ NEW: <meta name="csrf-token">; <script> tags
                      have nonce="{{ csp_nonce() }}"; logout form has
                      hidden csrf_token input.
  auth/_shell.html  — ⚠ NEW: <meta name="csrf-token"> + script nonce.
  *every form*      — ⚠ NEW: hidden csrf_token input.
  *templates with inline handlers* — ⚠ NEW: 33 inline event handlers
                      refactored to data-confirm/data-autosubmit
                      delegated handlers or addEventListener inside
                      nonce'd <script> blocks.
  profile/edit.html — ⚠ NEW: API access tab (token CRUD).
static/app.js       — ⚠ NEW: fetch wrapper for X-CSRFToken;
                      delegated handlers for data-confirm,
                      data-autosubmit.
DATABASE.md         — Full data-layer reference; needs a follow-up
                      append for admin_audit and api_tokens.
HANDOFF.md          — this file.
```

---

## Env vars introduced this session

| Name                       | Required | Purpose                                                                      | Default                                |
| :------------------------- | :------- | :--------------------------------------------------------------------------- | :------------------------------------- |
| `SECRET_KEY`               | **yes**  | Flask session signing. App refuses to boot without it.                       | (none — must be set)                   |
| `SECRET_KEY_FALLBACK`      | no       | Comma-separated old keys used for cookie verification during rotation.       | unset                                  |
| `SESSION_COOKIE_SECURE`    | no       | Override the auto-on-when-`DATABASE_URL`-set behavior.                       | on if `DATABASE_URL` set, else off     |
| `RATELIMIT_STORAGE_URI`    | no       | Swap Flask-Limiter's storage from in-memory to e.g. `redis://...`.           | `memory://`                            |
| `CSP_REPORT_ONLY`          | no       | Set to `1` to ship CSP as `Content-Security-Policy-Report-Only`.             | unset (enforced)                       |
| `ALLOW_REGISTRATION`       | no       | Existing — close registration with `0/false/no/off`.                         | open                                   |
| `SENDGRID_API_KEY`         | no       | Existing — enables real email sending.                                       | unset (logs to stdout)                 |
| `EMAIL_FROM_ADDRESS`       | no       | Existing — required for SendGrid.                                            | unset                                  |
| `ANTHROPIC_API_KEY`        | yes for AI | Existing — coaching / generation.                                          | unset (AI features disabled)           |

---

## Pair this handoff with

- `DATABASE.md` — schema reference (pending a sync for the two new
  tables; meanwhile the migration code in `init_db.py` is canonical).
- The seven security PRs (#11–#17) for per-change rationale and test
  plans. Stack base is `aebb6b1` (previous handoff merge).
