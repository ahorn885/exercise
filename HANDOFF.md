# AIDSTATION — Session Handoff

**Date:** 2026-05-06
**Last commit on `main`:** `0f6bb36` — DATABASE.md merge. Stacked on top
of `aa404ae` (email + password reset), `9de0268` (admin dashboard +
cascade-delete user), `c353f52` (coaching payload optimisation), and
`1b5216a` (transparent logo SVGs). Multi-user is fully shipped and
verified live; today's session was follow-on polish + foundation work.

**Deploy state:**
- ✅ Vercel: `0f6bb36` building/live at `https://aidstation-pro.vercel.app`,
  Neon Postgres backed. Andy is bootstrapped (user 1). Registration is
  open by default; `ALLOW_REGISTRATION=0/false/no/off` would close it.
- ✅ TrueNAS: GitHub Actions builds + Watchtower auto-pulls on every
  push to `main`. Should be on `0f6bb36` within ~5 min of the latest
  push. SQLite-backed; data at `/mnt/storage/exercise/`.

**Next focus (per Andy):** **Security.** The multi-user retrofit ships
the data isolation half but not the perimeter half. Section below
("Next session — security focus") enumerates the concrete items
worth auditing first.

---

## Next session — security focus

The multi-user retrofit defended at the SQL layer (every read scoped by
`user_id`, fetch-by-id handlers carry `AND user_id = ?`, composite
UNIQUEs on `(user_id, ...)` for UPSERT idempotency, etc.). What it
explicitly didn't address:

### Hard problems worth reviewing first

1. **`SECRET_KEY` has a hardcoded default.** `app.py:8` has
   `secret_key = os.environ.get('SECRET_KEY', 'ar-training-2026')`.
   If `SECRET_KEY` isn't set in env, every Flask session cookie is
   trivially forgeable by anyone who reads the source. Should
   require the env var and fail loudly on boot if missing.
2. **No CSRF protection.** Flask doesn't ship CSRF defense; nothing in
   the app uses Flask-WTF or CSRFProtect. Every form POST (including
   `/auth/login`, `/auth/register`, `/auth/reset/<token>`,
   `/admin/users/<id>/delete`) is reachable via cross-site form
   submissions. **The admin delete-user route is the highest-risk
   surface here** — a logged-in admin clicking a malicious link could
   delete a user without confirmation.
3. **No rate limiting.** Login, password reset request, and
   registration all accept unlimited POST attempts. Flask-Limiter
   would be the standard answer; even a coarse "10 attempts per 5 min
   per IP" on `/auth/login` and `/auth/forgot` would close the
   biggest brute-force window.
4. **Session cookie hardening.** Defaults are fine for HTTPS but worth
   making explicit:
   - `SESSION_COOKIE_SECURE=True` (HTTPS-only)
   - `SESSION_COOKIE_HTTPONLY=True` (default already, but confirm)
   - `SESSION_COOKIE_SAMESITE='Lax'` (defends most CSRF vectors that
     #2 above misses)
5. **Password policy is minimal.** `routes/auth.py` enforces only "≥ 8
   characters." No complexity, no breach-list check, no zxcvbn.
   Acceptable for a single-operator + invited-friends app, but worth
   flagging to anyone who'll be onboarding strangers.

### Softer items

6. **Admin actions aren't audited.** `_delete_user_and_data` runs in
   one transaction with no log. After a delete, there's no record of
   who deleted whom. Could write to a small `admin_audit` table.
7. **`/coaching/api/*` (and other JSON endpoints) are session-cookie
   gated.** No token auth. External tooling needs cookie-jar
   gymnastics. Parked from the prior handoff; not strictly a security
   issue but worth revisiting if you build any out-of-app integration.
8. **File upload paths don't sanitize filenames.** FIT-file imports
   under `/garmin/import` and `/garmin/import-wellness` accept
   user-supplied names. The current code routes parsing through
   `garmin_fit_parser.parse_fit` which doesn't write to disk
   uncontrolled, so this is mostly hygiene — worth auditing as we
   add more upload surfaces.
9. **`SECRET_KEY` rotation has no drain mechanism.** Rotating the key
   invalidates every active session and there's no operator UI to do
   it cleanly. Out of scope today but worth flagging.
10. **No security headers.** No `Content-Security-Policy`,
    `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
    set. Bootstrap CDN currently loaded inline; CSP would make adding
    one tricky and is worth its own session.

My pick for the first-pass security PR: **#1 + #2 + #3 + #4** —
hardcoded secret, CSRF on the high-blast-radius forms, rate limiting
on auth endpoints, cookie hardening. That covers the headline
"someone-could-impersonate-or-brute-force-Andy" risk in one go without
chasing the long tail.

---

## Carry-forward operator items

### Tabled — pending operator action

**SendGrid setup** — PR #8 shipped the email helper + password reset
code; live deploy currently logs reset links to stdout instead of
emailing them. To turn that on:

1. Sign up at sendgrid.com (free tier: 100/day forever).
2. Verify a sender (Single Sender or Domain Authentication —
   walkthrough in chat history of the session that shipped PR #8).
3. Create a Restricted-Access API key with Mail Send → Full Access.
4. Set on Vercel + TrueNAS env: `SENDGRID_API_KEY=...`,
   `EMAIL_FROM_ADDRESS=...` (and optionally `EMAIL_FROM_NAME`).
5. Vercel → Redeploy. TrueNAS → `cd /mnt/storage/exercise && docker
   compose up -d` (Watchtower image pulls don't reload `env_file`).

Smoke test: `/auth/login` → "Forgot password?" → submit verified
email → reset email arrives → click → set new password → sign in.

Until this is configured, the password-reset flow is functionally
unavailable to anyone who doesn't have shell access to read Vercel
function logs.

### Optional spot-checks on the live site

- Admin dashboard `/admin/` (only visible in user dropdown for user 1).
  Confirm row counts look right; create + delete a throwaway user.
- Coaching cache hits in Vercel logs after a 4-5-turn chat: the 2nd
  `[coaching:chat]` line should show `cache_read >> 0`.
- Transparent lockup on `/auth/login` / `/auth/register`: blends into
  paper bg, no white box.
- "Create an account" link on `/auth/login` lands on `/auth/register`
  cleanly; "Forgot password?" lands on `/auth/forgot`.

### Tabled — code work blocked on the above

- **Email invites flow** — was the natural follow-on to PR #8 but
  needs SendGrid live first. Plan: admin form → invite token → email
  with `/auth/register?invite=<token>` link that bypasses
  `ALLOW_REGISTRATION=0`.
- **Email verification on signup** — same blocker.

---

## Documentation

This handoff covers operator state and roadmap. For data-layer
specifics, see **`DATABASE.md`** at the repo root (shipped this
session, ~1050 lines). It documents:

- All 33 tables, grouped by domain, with columns, indexes,
  constraints, and read/write call sites.
- The `database.py` two-backend abstraction (`?`-placeholder
  rewriting, `_CompatCursor.lastrowid`, row-access shims).
- Multi-user scoping pattern (denormalized vs parent-JOIN, composite
  UNIQUEs, cross-user defenses).
- Common patterns and gotchas (`RETURNING id`, portable upserts, the
  `INSERT OR IGNORE` / `datetime('now')` SQLite-only trap, datetime
  template-slicing on Postgres, `_AUTH_EXEMPT_ENDPOINTS`).
- End-to-end lifecycle traces of six common flows (strength session,
  plan generation, Garmin auto-match, coach chat, admin user delete,
  password reset).

Pair this handoff with `DATABASE.md` when starting a new session.

---

## What shipped this session

Six PRs merged on top of `9409d0d` (the start point for this session,
which itself capped the multi-user retrofit batch).

**`559fe01` — Open registration + Postgres compat sweep + cardio pace
derive (PR #3, merge of `claude/enable-multiple-users-zBNlI`).**
- `routes/auth.py` flips `ALLOW_REGISTRATION` default to open;
  closing requires explicit `0/false/no/off`. First-user bootstrap
  unaffected.
- Postgres compat: replaced SQLite-only `INSERT OR IGNORE`,
  `INSERT OR REPLACE`, and `datetime('now')` across `routes/locales`,
  `routes/conditions`, `routes/natural_log`, `routes/garmin`,
  `garmin_connect`. These were 500'ing locale + conditions saves on
  Neon (failed statement aborts the txn, follow-up writes also fail).
- `routes/cardio.py` derives `avg_pace` server-side from
  `moving_time_min` (or `duration_min`) and `distance_mi` when the
  field is left blank. Sanity ceiling at 100 min/mi.

**`ece6be3` — Locale → Location user-visible rename + datetime-slicing
fix.** Direct-to-main hotfix while debugging the locale 500.
- Templates: every visible "Locale"/"locales" → "Location"/"locations"
  across nav, page titles, headings, blurbs, form labels.
  URLs (`/locales/...`), DB tables, Python identifiers untouched.
- The actual locale-page 500: `templates/locales/list.html` and
  `templates/profile/edit.html` were slicing `[:10]` on TIMESTAMP
  columns to extract a date prefix. Works on SQLite (TEXT), crashes
  on Postgres (datetime). Wrapped with `|string`.

**`d5e25dc` — Login page polish (PR #4).**
- Auth shell swapped from inline-SVG lockup (which inherits Bootstrap's
  `--bs-navbar-brand-color: var(--paper)` token globally and rendered
  white-on-white on the paper bg) to the standalone `lockup-light.svg`
  with hardcoded ink colors. The earlier "orange dot only" symptom was
  the inline mark's strokes going white while the orange `<rect>`
  retained its hex fill.
- Dropped the redundant `<h1>Sign in</h1>` from `login.html`.

**`1b5216a` — Transparent background on lockup SVGs (PR #5).**
- `static/logo/lockup-light.svg` and `lockup-dark.svg` had a
  full-canvas background `<rect>` (`#FFFFFF` / `#0E0F11`) for OG-image
  use. The light variant's white square stood out as a visible box
  against the paper-tinted body bg. Dropped the rect; mark + wordmark
  carry their own hex colors so the lockup renders cleanly anywhere.

**`c353f52` — Coaching API payload optimisation (PR #6).**
- `chat_with_coach`: split system into two cached blocks. Static
  base+sport prompt at 1h TTL (unchanged) plus a new per-session
  coaching-context block at 5m TTL. Subsequent turns within a chat
  hit cache on the context block instead of re-sending the JSON dump.
- `extract_preferences`: `_FEEDBACK_EXTRACT_PROMPT` now lives in a
  cached system block. Runs of feedback extracts for the same source
  reuse the prompt cache.
- `extract_preferences`: short-circuits on question-shaped messages
  (leading/trailing `?`, leading question word). Skips ~30% of Haiku
  calls during chat use.
- `capture_and_normalize_feedback` + the chat route's pref-save:
  defer `feedback_log` insert until at least one preference was
  extracted. Pure conversational chatter no longer leaves rows.
- `extract_preferences`: logs token usage on the Haiku call so the
  savings show up in stdout / Vercel logs.

**`9de0268` — Admin dashboard with cascade-delete (PR #7).**
- New `/admin/` (gated to `user_id == 1`) lists every user with row
  counts (strength, cardio, plans) and a Delete button on every row
  except the admin's own.
- `routes/admin.py:_delete_user_and_data` walks the FK-safe DELETE
  chain in one transaction — same order as the manual SQL block
  used to clean up the first test user.
- Admin link in the user dropdown shown only when
  `current_user.id == 1`. `_require_admin()` returns 403 for any
  other user.
- Admin can't delete itself (route refuses; template hides the
  button).

**`aa404ae` — Email helper (SendGrid) + password reset (PR #8).**
- `email_helper.py` — single `send_email(to, subject, text, html=None)`
  entry point. POSTs SendGrid's `/v3/mail/send` directly via
  `requests`. Without `SENDGRID_API_KEY` set, falls back to logging
  the message to stdout so dev / unconfigured deploys still surface
  the link. `email_configured()` lets routes branch cleanly.
- New `password_resets` table on both backends (token PK, user_id
  FK, expires_at, used_at). 30-min TTL.
- `GET/POST /auth/forgot` — request reset; always renders the same
  generic success message regardless of whether the email matched
  (defends against enumeration).
- `GET/POST /auth/reset/<token>` — single-use, time-limited.
  bcrypt-rehash, mark token used, clear session, redirect to login.
- "Forgot password?" link added to `/auth/login`.
- Operator setup (verifying a sender, creating an API key, wiring
  env vars) is the unblocking task.

**`0f6bb36` — DATABASE.md (PR #9).**
- ~1050-line reference doc covering schema, scoping pattern, table
  catalog, UI ↔ table interaction map, engine-helper responsibilities,
  patterns + gotchas, lifecycle examples. Pair with this handoff
  going forward.

---

## What's currently live

All shipped from the multi-user retrofit (Sessions 0–4, see git
history for `32e8c38`) plus this session's work above:

- Multi-user auth (login/logout/register/forgot/reset), bcrypt,
  bootstrap-aware register page, `g.current_user_row` hydration on
  every authed request, stale-cookie defense.
- Per-user data isolation across 25 scoped tables. Composite UNIQUEs
  on `(user_id, exercise/date/timestamp/...)` for UPSERT idempotency.
  Postgres enforces `NOT NULL` on `user_id`; SQLite allows NULL but
  every read/write threads it through.
- Strength training pipeline: `rx_engine.apply_session_outcome` as
  single source of truth, Family-A 2× kicker + Family-B baseline
  promotion, per-set storage in `training_log_sets`, deload on
  `consecutive_failures` plateau.
- Cardio log with full Garmin metric set, server-side pace derivation
  on manual entries.
- Conditions log with weather + 11 clothing categories, per-user
  accumulating autocomplete.
- Plans + plan items with auto-match (`plan_match.find_best_match`,
  −3/+2 day window), four-option resolve UI, bulk editor with four
  actions.
- Coaching: sport-adaptive system prompt, prompt-cached system
  + 5m-cached context, get_coaching_context surfaces deload flags,
  recent dispositions, wellness summary, prefs, profile, injuries,
  active locale equipment.
- Garmin Connect OAuth + activity / wellness FIT import. Per-user
  `garmin_auth` row but file caching at `/tmp/garth_session` is
  process-shared (parked).
- Athlete profile (`/profile`) with three tabs (athlete / coach memory
  with provenance / account), change password.
- Admin dashboard for user-deletion with cascade.
- Password reset flow (email-blocked).
- Recommended-purchases catalog + per-user state.
- Locations (`/locales` URL route, "Location" user-facing) with
  composite-PK profiles + denormalized `locale_equipment`.

---

## Code backlog

### Standalone, no dependencies

- **Multi-day wellness chart** on `/garmin/wellness` — 7-day trend
  complementing the per-day view. Smallest standalone left, ~2h.
  Top of the original handoff backlog.
- **Purchases catalog curation** — tune cost ranges, copy, priorities
  on `init_db.py:PURCHASE_RECOMMENDATIONS`. UPSERT-on-slug means edits
  propagate to existing rows on next cold start without disturbing
  per-user state. Iterative content work, easier to do as the user
  hits friction in the page than as a session task.

### Dependent on SendGrid

- **Email invites flow.** Admin form → invite token → emailed
  registration link that bypasses `ALLOW_REGISTRATION=0`. Schema
  sketch: `invites (token, email, created_by, created_at,
  expires_at, accepted_at)`.
- **Email verification on signup.** Verify owns-email-claimed before
  fully activating account.
- **Password reset is functionally tabled until SendGrid is live**
  (currently logs links to stdout — not user-accessible).

### Parked

- **Garmin per-user OAuth.** `garmin_auth` rows are scoped per-user but
  `/tmp/garth_session` file caching is process-shared. Includes 401
  refresh handling and shared-state cleanup. Blocked per Andy.
- **MFA (TOTP).** `pyotp` + setup flow on `/profile`.
- **Passkeys / WebAuthn.** Andy's preference; deferred because the
  WebAuthn flow is non-trivial (use the `webauthn` Python pkg).
- **BYOK Anthropic API key.** Per-user override of the shared key.
- **Custom user-authored exercises.** Would migrate
  `exercise_inventory` to `user_id NULL = system, NOT NULL =
  user-custom`. Not needed today.
- **`/coaching/api/*` token auth.** External tooling (Claude Desktop,
  scripts) needs session-cookie auth (curl with `--cookie-jar` after
  a `/auth/login` POST). Out of scope; flagged.
- **SMS / WhatsApp invites.** Discussed; deferred. SMS via Twilio is
  ~30 lines but costs ~$0.0079/msg + $1.15/mo phone rental.
  WhatsApp needs Meta Business API approval — weeks of setup.

---

## Carry-forward issues to watch

1. **`RETURNING id` is the pattern.** Every existing INSERT whose new
   id is read back uses `RETURNING id`; the `_CompatCursor.lastrowid`
   wrapper does `fetchone()` to surface it on Postgres. SQLite's
   native `lastrowid` ignores the unread RETURNING row, so the same
   SQL works on both backends. New INSERTs that need the id must add
   `RETURNING id`.

2. **Auth gate hydrates the user row.** `app.py:_require_login` does
   one `users` SELECT per authed request and stashes the row on
   `g.current_user_row`; the context processor reads from there
   instead of re-querying. If hydration fails (stale cookie, deleted
   user, DB error), the session is cleared and the request bounced.
   Hydration errors `print()` to stdout so failures surface.

3. **`/coaching/api/*` endpoints are login-gated.** External tooling
   needs session-cookie auth or a token-auth shim. Flagged in
   security backlog above.

4. **Brand CSS overrides Bootstrap aggressively.** `.navbar` is forced
   to `var(--ink) !important`, `--bs-navbar-toggler-icon-bg` is set
   explicitly, `body` clips `overflow-x` to defend against horizontal
   overflow trapping the user dropdown / toggler off-canvas. Adding
   navbar items: keep an eye on intrinsic width at ≥992px viewports.
   Outside-navbar use of `.navbar-brand` was the cause of the
   white-on-white logo bug fixed this session.

5. **`INSERT OR IGNORE`, `INSERT OR REPLACE`, and `datetime('now')`
   are SQLite-only.** Using them in route code that hits Postgres
   500s the request — psycopg2 enters `InFailedSqlTransaction` after
   the first bad statement and aborts the rest of the request even
   if the bad statement was wrapped in `try/except`. Use
   `ON CONFLICT … DO NOTHING/UPDATE` and `CURRENT_TIMESTAMP`. See
   `DATABASE.md` "Common patterns and gotchas" for the table.

6. **Postgres TIMESTAMP columns return `datetime`; SQLite's are TEXT.**
   Templates that slice `[:10]` to extract the date prefix work on
   SQLite and crash on Postgres. Wrap with `|string`. Three sites
   know this today (`templates/locales/list.html`,
   `templates/profile/edit.html`); any new TIMESTAMP-into-template
   needs the same.

7. **SendGrid not configured yet.** Password reset link goes to
   stdout. See "Carry-forward operator items" above for the unblocking
   walkthrough.

8. **`SECRET_KEY` defaults to a hardcoded string** (see security
   focus section). Make this a hard requirement before audit.

---

## Architecture quick reference

For full detail see `DATABASE.md`. Quick file-by-file:

```
app.py              — Flask app; registers blueprints; runs DB init on
                      startup. Auth gate (_require_login) hydrates user
                      row once per request. Adds new auth endpoints to
                      _AUTH_EXEMPT_ENDPOINTS.
database.py         — get_db() helper; supports both SQLite row_factory
                      and psycopg2. _PgConn translates ?-→%s, _CompatCursor
                      surfaces lastrowid via RETURNING id.
init_db.py          — SQLITE_SCHEMA, PG_SCHEMA, _SQLITE_MIGRATIONS,
                      _PG_MIGRATIONS. Migrations idempotent, run on
                      cold start. Callable migrations supported.
                      _seed_current_rx_for_user invoked from auth.register.
calculations.py     — Pure progression math. Outcome computation, 2×
                      kicker on significance, REPEAT-resets-failures,
                      project_next_from_current, compute_deload_baseline.
rx_engine.py        — apply_session_outcome — only sanctioned writer
                      to current_rx + training_log + training_log_sets.
plan_match.py       — Auto-match logged activities to scheduled plan
                      items. find_best_match, record_disposition.
coaching.py         — Claude API. Sport-adaptive system prompt with
                      cache_control. get_coaching_context surfaces
                      everything Claude needs. extract_preferences
                      runs Haiku on free-text feedback; capture_and
                      _normalize_feedback writes feedback_log only on
                      non-empty extraction.
athlete.py          — get/upsert_athlete_profile with PROFILE_FIELDS
                      allowlist. Backend-aware updated_at.
email_helper.py     — send_email (SendGrid HTTP API). Falls back to
                      stdout when SENDGRID_API_KEY isn't set.
garmin_fit_parser.py — parse_fit (activity), parse_wellness_fit, _dump_fit.
garmin_connect.py   — Garmin Connect OAuth + activity fetch via garth.
fit_workout_generator.py — generate_activity_fit (manual log FIT export).
routes/
  dashboard.py      — homepage (brand hero), weather, today's plan
  training.py       — /training, /training/new, /training/session
  cardio.py         — /cardio CRUD, server-side avg_pace derivation
  natural_log.py    — /log-natural NLP entry
  garmin.py         — /garmin/* (import FIT, sync, wellness, debug, auth)
  coaching.py       — /coaching/* (generate, review, chat, preferences)
  plans.py          — /plans/* (list, import, detail, push to Garmin,
                      PATCH /items/<id>, POST /<plan>/items/bulk)
  rx.py             — /rx (list + manual edit + POST /<id>/deload)
  body.py, conditions.py, injuries.py, references.py
  locales.py        — /locales (URL still under "locales/", UI says "Location")
  profile.py        — /profile/ (Athlete / Coach memory / Account)
  purchases.py      — /purchases (list + detail + status UPSERT)
  auth.py           — /auth/login, logout, register, forgot, reset
  admin.py          — /admin/ (gated to user_id == 1) + cascade-delete user
templates/          — Jinja2 per blueprint
static/             — AIDSTATION brand system (style.css, logo/, favicon,
                      og-preview)
DATABASE.md         — full data-layer reference (this session)
HANDOFF.md          — this file
```
