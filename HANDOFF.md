# AIDSTATION — Session Handoff

> **Note (2026-05-16, PR13):** This is the 2026-05-06 v1-maintenance
> handoff, kept for historical context. The v2 LLM-pipeline build has
> been in flight since 2026-05-08; current state lives in
> `aidstation-sources/CLAUDE.md` + the latest handoff in
> `aidstation-sources/handoffs/`. Notably out-of-date here: the
> TrueNAS/Docker deployment was retired 2026-05-16 (PR13) — Vercel is
> now the only deploy target, and Postgres (Neon) is the only DB
> backend.

**Date:** 2026-05-06
**Last commit on `main`:** `fc961eb` (rx_engine_spec.md merge, PR #19).
The previous handoff (`24f52c4`, PR #18) merged in the same session;
this refresh captures everything that's now live on main, including
the new spec doc.

**Two-line summary:**
1. The 10-item security backlog from the prior handoff shipped as
   PRs #11–#17, and all eight session PRs (#11–#18) merged.
2. A v2 rebuild of the app is on the horizon — schema, routes, and
   most code will be thrown out. To preserve the one piece of earned
   domain knowledge, `rx_engine_spec.md` (PR #19) was written as a
   standalone, language-agnostic spec for the strength progression
   algorithm.

**Deploy state:**
- ✅ Vercel: now on `fc961eb` post-merge. Neon Postgres backed.
- ✅ TrueNAS: Watchtower auto-pulls on every push to `main`. Should
  catch up within ~5 min of the most recent merge.

**Next focus (per Andy):** **v2 rebuild scoping.** Security and the
algorithm spec are both done. The current app is in maintenance mode
unless something live breaks. Suggested order: kick off the v2
rebuild plan, do the post-merge live smoke checks below, and roll
the small remaining items into v2 rather than retrofitting v1.

---

## ⚠️ Pre-rebuild reading order

The v2 rebuild has three pieces of canonical context. Read in this
order:

1. **`HANDOFF.md`** (this doc) — operational state, what's live, what's
   parked.
2. **`DATABASE.md`** (~1050 lines) — schema reference. **Caveat:** it
   pre-dates the two new tables added in this session (`admin_audit`
   and `api_tokens`); see "Database state" below for canonical
   definitions until the doc gets a sync.
3. **`rx_engine_spec.md`** (NEW this session, ~900 lines) — the
   strength progression algorithm. This is the only piece of domain
   knowledge worth preserving verbatim into v2; everything else is
   reasonable to redesign.

---

## ⚠️ Database state on `main`

35 tables total. Two added this session:

### `admin_audit` (PR #12, merged `5f834f4`)

```
admin_audit
  id              INTEGER / SERIAL  PK
  actor_user_id   INTEGER          REFERENCES users(id) — NULL if actor was later deleted
  action          TEXT             e.g. 'delete_user'
  target_user_id  INTEGER          plain INT (no FK) so the row survives target deletion
  target_username TEXT             snapshotted at delete time
  details         TEXT             optional JSON / freetext payload
  created_at      TIMESTAMP        default NOW() / datetime('now')

  INDEX admin_audit_created_at_idx ON admin_audit(created_at DESC)
```

Currently written from `routes/admin.delete_user` in the same
transaction as the cascade-delete. **Convention:** any new admin
mutation should add a row with a fresh `action` string. **Don't add
the FK** to `target_user_id` — the row's whole point is to survive
target deletion. Audit rows are intentionally **not** in
`_delete_user_and_data`'s cascade chain.

### `api_tokens` (PR #15, merged `83df664`)

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

**Hashing convention:** plaintext is shown to the user **once** at
creation (passed through one-shot `flask_session['new_api_token_plaintext']`)
and never persisted. We store SHA-256 of `aid_<base64url(32)>`.
SHA-256 (not bcrypt) is fine — tokens are 32 bytes of cryptographic
random, no brute-force surface. Verification = SHA-256 the inbound
header value, look up by `token_hash`, check `revoked_at IS NULL`.

**Cascade-delete:** `routes/admin._delete_user_and_data` picks up
`api_tokens` before `users` (added in PR #15). Any new user-scoped
table added in v2 (or a follow-on retrofit) **must** be added to
this chain.

### `DATABASE.md` ↔ code drift to sync

Two minor inaccuracies in `DATABASE.md` flagged by `rx_engine_spec.md`
during the audit. **Code is the source of truth.**

- `training_log.outcome` literally holds `'PROGRESS ↑'`, `'REPEAT →'`,
  `'REDUCE ↓'` (arrows are part of the value), or `NULL` on
  bootstrap-mode imports. `DATABASE.md` paraphrases as
  `{PROGRESS, REPEAT, FAIL}` — incorrect.
- NLP entries (`routes/natural_log.py:/log-natural/save`) **do not**
  flow through `rx_engine.apply_session_outcome`. They insert
  `training_log` / `training_log_sets` directly with
  `outcome=NULL` and don't update `current_rx`. `DATABASE.md`
  states the opposite.

Worth a short doc-only sync PR before the v2 rebuild starts, or
fold into v2's fresh schema doc.

---

## What shipped this session

Nine PRs merged on top of `aebb6b1` (the prior handoff merge).

### Security stack — PRs #11 through #17

| PR | Merge | Title |
| :---: | :---: | :--- |
| #11 | `d503dc0` | Security pass: SECRET_KEY required, CSRF, rate limits, cookie hardening |
| #12 | `5f834f4` | Easy headers, admin audit log, FIT filename sanitization |
| #13 | `45817d9` | Password policy: enforce zxcvbn score ≥ 3 |
| #14 | `fe1761e` | CSP baseline (with `unsafe-inline` initially) |
| #15 | `83df664` | API tokens: bearer auth on `/coaching/api/*` |
| #16 | `e626f65` | `SECRET_KEY_FALLBACK` env var for graceful key rotation |
| #17 | `0ea755d` | CSP nonces: drop `'unsafe-inline'` from script-src |

The previous handoff (PR #18, merge `24f52c4`) covers each PR's
detail in full — what code changed, the rationale, the operator
notes. That doc is preserved at the previous commit if you need to
diff back; this handoff is the current snapshot.

### `rx_engine_spec.md` — PR #19, merge `fc961eb`

~900-line standalone spec for the strength-training progression
algorithm. Written from the brief: "produce a single markdown file
that documents the algorithm completely enough for a developer to
reimplement it from scratch in a different language without reading
the existing Python."

Sections covered:
1. Inputs / outputs of `apply_session_outcome`.
2. Outcome computation (`PROGRESS ↑` / `REPEAT →` / `REDUCE ↓`,
   the 0.75 volume threshold).
3. Family A vs Family B + the full `PROGRESSION_RULES` table.
4. The 2× kicker on significance (1.10 multiplier, ≥ 2 sets).
5. Family-B baseline promotion (`min(over-target)` over ≥ 2 sets).
6. Counter logic — including the explicit REPEAT-resets-failures
   rule.
7. Deload trigger and baseline (`compute_deload_baseline`).
8. Next-session projection (`calculate_next_rx` with kicker vs
   `project_next_from_current` without).
9. Per-set storage and aggregation up to `training_log`.
10. UPSERT semantics on `(user_id, exercise)`.
11. Bootstrap mode (FIT import / first-time exercise).
12. Edge cases (11 sub-sections).

Plus a constants at-a-glance table, an ASCII flow diagram, and an
**"Open items flagged for the rebuild"** section calling out the
five rules whose rationale isn't captured in code comments
(REPEAT-resets-failures, regression-vs-progression dimension
priority, NLP bypass, FIT-without-targets, no concurrency control).

---

## Carry-forward operator items

### ✅ SendGrid email — live in production (2026-06-21)

Resolved (was tabled across the prior handoffs). Live email send is
configured and verified in prod, so password reset **and** the
plan-ready / plan-failed notifications (#260) now deliver real email.

**Production setup (done):**

1. SendGrid account (free tier: 100/day).
2. **Sending domain verified** in SendGrid — authorizes any
   `From: …@that-domain` address (a single verified sender also works).
3. Restricted-access API key, Mail Send → Full Access.
4. Prod env (Vercel) set: `SENDGRID_API_KEY`, `EMAIL_FROM_ADDRESS`
   (`noreply@<verified-domain>`), optional `EMAIL_FROM_NAME` (defaults
   to `AIDSTATION`). Mirror the same vars on TrueNAS if run there.

**Operating notes:**

- Vercel applies env-var changes only to **new** deployments — redeploy
  (or push) after changing any of these. TrueNAS: `cd
  /mnt/storage/exercise && docker compose up -d`.
- The From-address must be on the verified domain / a verified sender,
  or SendGrid 4xx-rejects (`[email:sendgrid_rejected]` in the function
  logs). `email_configured()` only checks the vars are *set*, not that
  the sender is verified.
- Per-send outcome is observable in logs: `email_helper` prints
  `[email:sent]` / `[email:sendgrid_rejected]` / `[email:unconfigured]`,
  and `notify_plan_terminal` logs `email_sent=<bool>` per plan (#853).
- Unset any var → silent stdout fallback (no email): the intended
  local-dev / preview behavior.

### Optional spot-checks on the post-merge live site

These were listed in PR #18's body and are still the right post-deploy
sanity checks:

- Sign in / sign out: confirm the Sign-out form still works (the
  CSRF hidden input added in PR #11).
- Browser devtools console on every section after the CSP-nonces
  merge: should be **zero CSP violations**. If any fire, set
  `CSP_REPORT_ONLY=1` while debugging.
- `/admin/`: delete a throwaway user, then `SELECT * FROM admin_audit
  ORDER BY id DESC LIMIT 1` — confirm a row landed with
  `actor_user_id=1`, `action='delete_user'`.
- `/profile/` API access tab: create a token. Confirm the plaintext
  is shown exactly once and is empty after page reload.
- `curl -X POST .../coaching/api/generate -H "Authorization: Bearer aid_..."`
  with the new token — confirm the plan generates.
- Try a deliberately weak password on `/profile/password` (e.g.
  `password`) — should get rejected with the zxcvbn warning string.
- Auth rate-limit: deliberately mistype the login password 11 times —
  should get a 429 on the 11th.

---

## What's currently live

Everything from prior handoffs plus this session's security stack
(PRs #11–#17), all on `main` as of `fc961eb`:

- **Multi-user** auth, bcrypt, per-request user-row hydration. 35
  scoped tables; composite UNIQUEs for UPSERT idempotency.
- **Strength training pipeline:** `rx_engine.apply_session_outcome`
  as single source of truth, Family-A 2× kicker on significance,
  Family-B baseline promotion, per-set storage in
  `training_log_sets`, deload on `consecutive_failures` plateau.
  **Spec:** `rx_engine_spec.md`.
- **Cardio log** (Garmin metric set, server-side `avg_pace`
  derivation).
- **Conditions log** with weather + 11 clothing categories.
- **Plans + plan items + auto-match** (`plan_match.find_best_match`,
  -3/+2 day window), four-option resolve UI.
- **Coaching:** sport-adaptive system prompt, prompt-cached
  system + 5m-cached context, Haiku-extracted feedback.
- **Garmin Connect** OAuth + activity / wellness FIT import.
- **Athlete profile** (`/profile`) — three tabs, change-password,
  plus a fourth **API access** tab as of PR #15.
- **Admin dashboard** for cascade-delete user, plus `admin_audit`
  trail since PR #12.
- **Password reset** + **plan-ready / plan-failed emails** (#260) — SendGrid live in prod (2026-06-21).
- **Recommended-purchases catalog** + per-user state.
- **Locations** (`/locales` URL, "Location" UI).
- **Per-user API tokens** (`api_tokens`) for headless access to
  `/coaching/api/*`.
- **Security baseline (NEW):** mandatory `SECRET_KEY` with rotation
  drain, CSRF on every form, rate limits on auth, hardened session
  cookies, defensive HTTP headers (X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy, Permissions-Policy), CSP with
  per-request nonces (no `'unsafe-inline'` on `script-src`), zxcvbn
  password policy, `secure_filename` on uploads, admin audit log.

---

## Code backlog

### v1 maintenance (pick up only if v2 doesn't ship soon)

- **`DATABASE.md` sync.** Add `admin_audit` and `api_tokens` to the
  table catalog; correct the `outcome`-string and NLP-bypass entries
  (see "DATABASE.md ↔ code drift" above). 30-min doc-only PR.
- **CSP `style-src` nonces.** Drop `'unsafe-inline'` from style-src.
  Touches every template with an inline `style="..."` attribute,
  several hundred occurrences. Lower priority than the script-src
  pass that already shipped — XSS surface for inline styles is
  narrower.
- **Token expiry on `api_tokens`.** Currently no `expires_at`
  enforcement; revocation is the only invalidation path. Add
  optional TTL on creation if desired.
- **`/admin/audit` view.** Write-only today; build a read view when
  the log accumulates anything interesting.

### Standalone, no dependencies

- **Multi-day wellness chart** on `/garmin/wellness` (~2h, top of the
  original code backlog). Still tabled.
- **Purchases catalog curation** in `init_db.py:PURCHASE_RECOMMENDATIONS`.
  Iterative content work.

### Dependent on SendGrid *(now unblocked — SendGrid live in prod)*

- **Email invites flow** — admin form → invite token → emailed
  registration link bypassing `ALLOW_REGISTRATION=0`.
- **Email verification** on signup.

_Password reset and plan-ready / plan-failed emails (#260) are already
live — see "✅ SendGrid email" under Carry-forward operator items._

### Parked

- **Garmin per-user OAuth.** `provider_auth` rows scoped per-user (moved
  off `garmin_auth` 2026-07-01, T-5.1/#249) but `/tmp/garth_session`
  file caching is still process-shared.
- **MFA (TOTP).** `pyotp` + setup on `/profile`.
- **Passkeys / WebAuthn.**
- **BYOK Anthropic API key** per-user.
- **Custom user-authored exercises** (`exercise_inventory.user_id`
  nullable).
- **SMS / WhatsApp invites.**

### Expected to be redesigned in v2

- The whole stack. Per the v2 brief: "schema, routes, and most code
  will be thrown out." The one thing to preserve verbatim is the
  progression algorithm, captured in `rx_engine_spec.md`.

---

## Carry-forward issues to watch

These are invariants v1 still expects. If v2 reuses any of this code,
they apply; if v2 rewrites from scratch, they're informational.

1. **`RETURNING id` is the pattern.** Every INSERT whose new id is
   read back uses `RETURNING id`; `_CompatCursor.lastrowid`
   `fetchone()`s to surface it on Postgres. SQLite's native
   `lastrowid` ignores the unread RETURNING row, so the same SQL
   works on both backends.

2. **Auth gate hydrates the user row.** `app.py:_require_login` does
   one `users` SELECT per authed request and stashes on
   `g.current_user_row`. Bearer tokens are tried before the session
   cookie; on a hit the gate sets `g.api_user_id` and
   `g.api_authed = True` so `current_user_id()` resolves the same
   way as a session-authed request.

3. **`/coaching/api/*` accepts bearer tokens.** No more cookie-jar
   dance for external tooling. CSRF is exempted on those two
   endpoints (`api_generate`, `api_review`); CSRF still required
   on every other state-changing form.

4. **`INSERT OR IGNORE`, `INSERT OR REPLACE`, and `datetime('now')`
   are SQLite-only.** Use `ON CONFLICT … DO NOTHING/UPDATE` and
   `CURRENT_TIMESTAMP` / `NOW()` instead.

5. **Postgres `TIMESTAMP` columns return `datetime`; SQLite's are
   TEXT.** Wrap `[:10]`-slicing with `|string` in templates.

6. **Brand CSS overrides Bootstrap aggressively.** `.navbar` is
   forced to `var(--ink) !important`, `--bs-navbar-toggler-icon-bg`
   is set explicitly, `body` clips `overflow-x` to defend against
   horizontal-overflow trapping the toggler off-canvas.

7. **`SECRET_KEY` is required at boot.** App raises `RuntimeError`
   if unset. Rotation has a graceful drain via
   `SECRET_KEY_FALLBACK` (comma-separated for multi-step rotations).

8. **CSP enforces nonces on `<script>`.** Any new template that
   inlines a `<script>` block **must** render
   `nonce="{{ csp_nonce() }}"` on the tag. Inline event handlers
   (`onclick`, `onsubmit`, `onchange`, etc.) are blocked — use
   `addEventListener` from inside a nonce'd `<script>`, or one of
   the delegated patterns in `static/app.js`:
   - `<form data-confirm="...">` for submit-time prompts.
   - `<button|a data-confirm="...">` for click-time prompts.
   - `<input|select data-autosubmit>` to submit the enclosing form
     on change.
   Inline handlers injected via `innerHTML` template literals (see
   `training/session_form.html`) similarly do **not** inherit the
   page nonce; wire them with `addEventListener` after the
   `innerHTML =` assignment.

9. **CSRF tokens on every state-changing form.** Every
   `<form method="post">` template needs
   `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
   JS `fetch` POSTs to same-origin pick up `X-CSRFToken` from the
   `<meta name="csrf-token">` automatically via the `static/app.js`
   wrapper.

10. **Rate limits on auth endpoints.** `/auth/login` 10/5min,
    `/auth/register` 10/hr, `/auth/forgot` 5/15min, `/auth/reset`
    10/15min. Returns 429 once the budget's gone.

11. **`api_tokens` are SHA-256, not bcrypt.** Tokens are 32 bytes of
    crypto random — no brute-force surface, no need for slow
    hashing. Plaintext is shown once, then the user copies it.
    Don't switch to bcrypt; it would break verification (which
    needs a deterministic hash for lookup).

12. **`admin_audit.target_user_id` is FK-less by design.** Don't
    add the FK; the row's job is to outlive the target.

13. **rx_engine outcome strings include arrows.** `'PROGRESS ↑'`,
    `'REPEAT →'`, `'REDUCE ↓'`. Or `NULL` on bootstrap-mode FIT
    imports. See `rx_engine_spec.md` §1.4.

14. **NLP entries bypass `rx_engine`.** `routes/natural_log.py`
    inserts `training_log` / `training_log_sets` directly without
    calling `apply_session_outcome`. Outcome is `NULL`; `current_rx`
    is not updated. Documented in `rx_engine_spec.md` §12.7 as an
    open item — possibly intentional (NLP as journal-only),
    possibly oversight; v2 should make a deliberate call.

---

## Architecture quick reference

For full data-layer detail see `DATABASE.md` (note: pre-dates
`admin_audit` and `api_tokens`). For the strength progression math
see `rx_engine_spec.md`.

```
app.py              — Flask app; registers blueprints; runs DB init.
                      Hosts CSRFProtect, Limiter, before_request
                      (CSP nonce + bearer-token auth path),
                      after_request (defensive headers + CSP).
database.py         — get_db(); SQLite + psycopg2; ?→%s; lastrowid
                      via RETURNING.
init_db.py          — SQLITE_SCHEMA, PG_SCHEMA, _SQLITE_MIGRATIONS,
                      _PG_MIGRATIONS. Migrations idempotent, run on
                      cold start. admin_audit and api_tokens added
                      this session.
calculations.py     — Pure progression math. Outcome computation,
                      2× kicker on significance, REPEAT-resets-
                      failures, project_next_from_current,
                      compute_deload_baseline. SPECIFIED IN
                      rx_engine_spec.md.
rx_engine.py        — apply_session_outcome — only sanctioned writer
                      to current_rx + training_log_sets path.
                      SPECIFIED IN rx_engine_spec.md.
plan_match.py       — Auto-match logged activities to scheduled plan
                      items.
coaching.py         — Claude API. Sport-adaptive system prompt with
                      cache_control. get_coaching_context surfaces
                      everything Claude needs. Haiku-extracted
                      feedback into coaching_preferences.
athlete.py          — get/upsert_athlete_profile.
email_helper.py     — send_email (SendGrid HTTP API). Falls back to
                      stdout when SENDGRID_API_KEY isn't set.
garmin_fit_parser.py — parse_fit, parse_wellness_fit, _dump_fit.
garmin_connect.py   — Garmin Connect OAuth + activity fetch.
fit_workout_generator.py — generate_activity_fit (manual log FIT).
routes/
  auth.py           — /auth/login, logout, register, forgot, reset,
                      + zxcvbn _password_strength_errors,
                      + generate_api_token, verify_bearer_token,
                      + rate-limit decorators on auth endpoints.
  admin.py          — /admin/ (gated to user_id == 1) +
                      cascade-delete + admin_audit write.
  coaching.py       — /coaching/* (generate, review, chat, prefs)
                      + api_generate, api_review (CSRF-exempt,
                      bearer-authed).
  garmin.py         — /garmin/* (FIT import, sync, wellness, debug,
                      auth) + secure_filename on every upload read.
  profile.py        — /profile/ (Athlete / Coach memory / Account /
                      API access). zxcvbn check on
                      change_password.
  …other routes (training, cardio, body, conditions, injuries,
   references, locales, plans, rx, purchases, natural_log,
   dashboard) unchanged this session.
templates/
  base.html         — <meta name="csrf-token">, <script> tags with
                      nonce="{{ csp_nonce() }}", logout-form CSRF.
  auth/_shell.html  — same.
  *every form*      — hidden csrf_token input.
  *templates with inline handlers* — refactored to data-confirm /
                      data-autosubmit / addEventListener.
  profile/edit.html — API access tab.
static/app.js       — fetch wrapper for X-CSRFToken; delegated
                      handlers for data-confirm, data-autosubmit.
DATABASE.md         — full data-layer reference; pending sync for
                      admin_audit, api_tokens, outcome strings,
                      NLP bypass.
HANDOFF.md          — this file.
rx_engine_spec.md   — NEW this session. Standalone spec for the
                      progression algorithm, intended to survive
                      the v2 rebuild.
```

---

## Env vars (current)

| Name                       | Required | Purpose                                                                          | Default                                |
| :------------------------- | :------- | :------------------------------------------------------------------------------- | :------------------------------------- |
| `SECRET_KEY`               | **yes**  | Flask session signing. App refuses to boot without it.                           | (none — must be set)                   |
| `SECRET_KEY_FALLBACK`      | no       | Comma-separated old keys used for cookie verification during rotation.           | unset                                  |
| `SESSION_COOKIE_SECURE`    | no       | Override the auto-on-when-`DATABASE_URL`-set behavior.                           | on if `DATABASE_URL` set, else off     |
| `RATELIMIT_STORAGE_URI`    | no       | Swap Flask-Limiter's storage from in-memory to e.g. `redis://...`.               | `memory://`                            |
| `CSP_REPORT_ONLY`          | no       | Set to `1` to ship CSP as `Content-Security-Policy-Report-Only`.                 | unset (enforced)                       |
| `ALLOW_REGISTRATION`       | no       | Close registration with `0/false/no/off`.                                        | open                                   |
| `SENDGRID_API_KEY`         | yes for email | Live email send via SendGrid HTTP API. Unset → mail logs to stdout (local/preview). | set in prod                  |
| `EMAIL_FROM_ADDRESS`       | yes for email | From-address; must be a SendGrid-verified sender or on a verified sending domain.   | set in prod (`noreply@<domain>`) |
| `EMAIL_FROM_NAME`          | no            | Friendly From-name on outgoing email.                                              | `AIDSTATION`                 |
| `ANTHROPIC_API_KEY`        | yes for AI | Coaching / generation.                                                         | unset (AI features disabled)           |
| `DATABASE_URL`             | yes for prod | Postgres connection string. Absence selects SQLite (local / TrueNAS).        | unset (SQLite at `/instance/training.db`) |

---

## Pair this handoff with

- **`DATABASE.md`** — schema reference (pending sync for the two
  new tables; meanwhile `init_db.py` is canonical).
- **`rx_engine_spec.md`** (NEW) — the strength progression
  algorithm, specified to survive a language change.
- **PRs #11–#19** for per-change rationale and test plans
  (all merged on `main` between `aebb6b1` and `fc961eb`).
