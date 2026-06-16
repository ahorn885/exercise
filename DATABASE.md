# AIDSTATION — Database Reference

How the data layer is shaped, how the app talks to it, and how each table
participates in real user flows. Pair this with `HANDOFF.md` (which covers
the broader product state) when onboarding a new session.

> **Note (2026-05-16, PR13 + PR14 + PR17):** The app is Postgres-only
> (Neon). PR13 stripped the dual-backend SQLite path from the codebase;
> PR14 added the top-of-file marker + inline `[STALE]` flags on the
> four biggest historical-SQLite subsections; PR17 (this revision)
> finished the rewrite — every section now describes the PG path
> directly. Historical SQLite framing (`_SQLITE_MIGRATIONS`,
> `init_sqlite()`, `INSERT OR IGNORE`, `datetime('now')`, dual-syntax
> tables, "Postgres datetime vs SQLite TEXT" footguns) is gone from
> this file. Live source of truth: `init_db.py`'s `PG_SCHEMA` +
> `_PG_MIGRATIONS` list.
>
> For any "what does the schema actually look like right now?" question,
> read `init_db.py` directly. For any "why does this column exist?"
> question, search this file for the column name + any feature handoff
> in `aidstation-sources/handoffs/`.

---

## Contents
- [Overview](#overview)
- [Architecture](#architecture)
  - [Backends and where they live](#backends-and-where-they-live)
  - [The `database.py` compatibility layer](#the-databasepy-compatibility-layer)
  - [Connection lifecycle](#connection-lifecycle)
  - [Auth gate and per-request hydration](#auth-gate-and-per-request-hydration)
  - [Migration philosophy](#migration-philosophy)
  - [Init and seed flow](#init-and-seed-flow)
- [Multi-user scoping](#multi-user-scoping)
  - [Denormalized vs parent-JOIN scoping](#denormalized-vs-parent-join-scoping)
  - [Composite UNIQUE constraints](#composite-unique-constraints)
  - [Cross-user defenses on writes](#cross-user-defenses-on-writes)
- [Table reference](#table-reference)
  - [Identity and auth](#identity-and-auth)
  - [Strength training](#strength-training)
  - [Cardio](#cardio)
  - [Body and conditions](#body-and-conditions)
  - [Injuries](#injuries)
  - [Plans and scheduling](#plans-and-scheduling)
  - [Coaching](#coaching)
  - [Equipment, locations, and purchases](#equipment-locations-and-purchases)
  - [Garmin](#garmin)
  - [Shared catalogs](#shared-catalogs)
- [UI → table interaction map](#ui--table-interaction-map)
- [Engine helpers](#engine-helpers)
- [Common patterns and gotchas](#common-patterns-and-gotchas)
- [Lifecycle examples](#lifecycle-examples)

---

## Overview

AIDSTATION is a Flask app on **PostgreSQL (Neon)**. Both production
(Vercel `aidstation-pro.vercel.app`) and local dev point at Neon — local
work uses a Neon dev branch via `DATABASE_URL` in `.env`. The SQLite path
and the TrueNAS Docker deployment were retired 2026-05-16 (PR13).

`database.py` exposes a thin compatibility layer kept from the previous
dual-backend era: it accepts `?` placeholders, translates them to `%s`
inline, wraps psycopg2's `RealDictCursor` so `row['column']` and `row[0]`
both work, and surfaces a `lastrowid` shim that reads the first column
of the next fetched row (so INSERTs that need the new id must include
`RETURNING id`).

Schema is multi-user. Every per-user table carries a `user_id` column;
every read/write path scopes by it. Shared catalogs (exercises,
equipment, purchase recommendations, training modalities, locale
`gym_profiles`) have no `user_id`.

---

## Architecture

### Where the DB lives

| Deployment | Location | Persistence |
|------------|----------|-------------|
| Vercel (prod) | Neon (`DATABASE_URL`) | Persistent, managed |
| Local dev | Neon dev branch (`DATABASE_URL` in `.env`) | Persistent on Neon |

`get_db()` raises `RuntimeError` if `DATABASE_URL` is unset — the app
has no SQLite fallback path.

### Duplicate `DATABASE_URL` / `DATABASE_URL_UNPOOLED` in the Vercel env list

If the project's Environment Variables list shows `DATABASE_URL` (and its
Neon companion `DATABASE_URL_UNPOOLED`) repeated many times, nothing in this
repo is adding them — there is no `vercel env add` in any script, workflow, or
hook. They are **branch-scoped Preview variables** created by the Neon ↔ Vercel
integration, which provisions a Neon database branch plus a per-branch
`DATABASE_URL`/`DATABASE_URL_UNPOOLED` pair for **every preview deployment**.
Each PR — and each Claude Code web session, which opens a fresh `claude/*`
branch — spawns another pair, and they are never pruned when the branch/PR
closes, so they accumulate under the same names (each scoped to a different Git
branch). List them with `vercel env ls preview` (optionally per-branch:
`vercel env ls preview <branch>`).

The running app reads only the **unscoped** `DATABASE_URL` (`database.py:5`), so
deleting the stale branch-scoped copies is safe for prod and normal previews.

To stop the accrual and clean up:
- **Stop new ones** — in Neon Console → Integrations → Vercel (or Vercel →
  Project → Storage/Integrations → Neon → Settings): turn **off** per-preview
  branch creation, **and/or** turn **on** "delete the Neon branch when the Git
  branch is deleted" (prunes the branch and its env vars on PR close).
- **Clean up existing** — Vercel → Project → Settings → Environment Variables,
  filter to **Preview**, delete the stale branch-scoped `DATABASE_URL` /
  `DATABASE_URL_UNPOOLED` entries (keep Production + the active branch), then
  delete the matching orphaned branches in Neon → Branches.

### The `database.py` compatibility layer

```
Flask request ─▶ get_db() ─▶ stash on flask.g.db
                  └─ psycopg2.connect(DATABASE_URL) → _PgConn(raw)
                       └─ wraps execute() to ?→%s
                           and returns _CompatCursor
```

`_PgConn`:
- `execute(sql, params)` — translates `?` → `%s` on the fly. Routes use
  `?` placeholders; the wrapper does the rewrite so route code reads
  the same as it did under the historical dual-backend.
- Returns `_CompatCursor`, which provides `fetchone()`, `fetchall()`,
  and a `lastrowid` shim.

`_CompatCursor.lastrowid` has one wrinkle: psycopg2 doesn't populate
`lastrowid` natively. The wrapper does an extra `fetchone()` against the
cursor and returns the first column of that row. This works **only if
the INSERT statement included `RETURNING id`**. Every existing INSERT
that reads back the new id uses `RETURNING id`; new INSERTs must follow
the same pattern.

Row access: `_PgRow` is a dict subclass that supports `row['column']`
and `row[0]` interchangeably.

### Connection lifecycle

One connection per Flask request, stashed on `flask.g.db`. Released by
`close_db` (registered as `teardown_appcontext`). No pooling — Vercel
serverless invocations open a fresh psycopg2 connection per request, which
is fine at the operator's traffic level. If load grew, pgbouncer or
Neon's built-in pooler would be the next step.

### Auth gate and per-request hydration

`app.py:_require_login` (registered as `before_request`):

1. Allow if endpoint is in `_AUTH_EXEMPT_ENDPOINTS`
   (`auth.login`, `auth.logout`, `auth.register`, `auth.forgot`,
   `auth.reset`, the four `oauth_callbacks.*` stubs, `static`,
   blueprint-static).
2. **Bearer-token auth** is checked first (so an external script's
   Authorization header beats any stale cookie). `verify_bearer_token`
   in `routes/auth.py` SHA-256-hashes the inbound `Bearer <token>`
   value, looks up `api_tokens.token_hash`, refuses if `revoked_at`
   or `expires_at` (when set) is in the past, and on hit sets
   `g.api_user_id = row.user_id`, `g.api_authed = True`, and bumps
   `last_used_at`. `current_user_id()` resolves to this id the same
   way it would resolve a session id.
3. Otherwise read `session['user_id']`. If missing → redirect to
   `/auth/login`.
4. **Hydrate the user row once** via `current_user(get_db())` and
   stash on `g.current_user_row`. Two reasons:
   - The context processor and any route handler can read the user row
     without re-querying.
   - It defends against a stale session cookie pointing at a `users` row
     that no longer exists (e.g. after admin deletion or the SQLite→Neon
     cutover). Without hydration, the gate would admit a "ghost" user
     whose templates render with `current_user=None`, hiding the only
     logout button.
5. If hydration fails, `session.clear()` and bounce. Errors print to
   stdout (visible in Vercel logs) so failures surface instead of being
   silently swallowed.

`current_user_id()` (in `routes/auth.py`) returns `g.api_user_id` when
the request came in via bearer token, otherwise
`session.get('user_id')`. No DB hit — used by every route to scope
queries.

The context processor `_inject_current_user` makes `current_user`
available to every template, reading from `g.current_user_row` (no
double-query).

### Migration philosophy

`_PG_MIGRATIONS` lives in `init_db.py` — a list of SQL strings or
callables. Postgres-specific syntax throughout: `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS`, `DO $$ ... $$` blocks for conditional constraint
changes, `ALTER COLUMN ... SET NOT NULL`, `NOW()`, `ON CONFLICT(...)
DO NOTHING`, `ON CONFLICT(...) DO UPDATE SET ...`.

**Rules:**
- Migrations run on **every cold start**. They must be idempotent — every
  `CREATE TABLE` / `ADD COLUMN` / `CREATE INDEX` is `IF NOT EXISTS`.
- New columns or tables go in `_PG_MIGRATIONS`.
- Postgres runs each statement in its own commit so a single failure
  (e.g. `SET NOT NULL` on a column that still has nulls during bootstrap)
  doesn't roll back prior successful migrations.
- Callable migrations are available for patterns that can't be expressed
  as a single SQL string (used historically for `clothing_options` /
  `locale_profiles` PK rebuilds).

### Init and seed flow

`app.py` import time → `init_postgres()`. `get_db()` raises
`RuntimeError` if `DATABASE_URL` is unset. Five phases:

1. **Schema** — execute `PG_SCHEMA` (everything wrapped in
   `IF NOT EXISTS`, so re-running is a no-op).
2. **Migrations** — run `_PG_MIGRATIONS` in order.
3. **Catalog seeds** — populate `exercise_inventory`, `equipment_items`,
   `exercise_equipment`, `training_modalities`, `training_methods` from
   the Python lists at the top of `init_db.py`. Seeders are
   UPSERT-on-unique-key, so editing the lists propagates on next cold
   start without disturbing user data.
4. **Per-user `current_rx` seed** — `_seed_current_rx_for_user(user_id)`
   ensures every user's `current_rx` table has a baseline row for every
   exercise in `exercise_inventory`. Called from `auth.register` for new
   users; called for user 1 during init for existing installs.
5. **Purchase recommendations seed** — UPSERT-on-`slug` from the
   `PURCHASE_RECOMMENDATIONS` Python list.

---

## Multi-user scoping

Every per-user table carries a `user_id INTEGER REFERENCES users(id)`
column. **Postgres enforces `NOT NULL`** on every per-user `user_id`
(set in Session 2D). Runtime defenses are the second line of safety
(see below).

**Every read scopes by `user_id`.** Every write threads `user_id` from
`current_user_id()`. Fetch-by-id handlers add `AND user_id = ?` so a
crafted URL can't read another user's row.

### Denormalized vs parent-JOIN scoping

Child tables either carry their own `user_id` column ("denormalized") or
get scoped by JOIN through their parent ("parent-JOIN"). The decision
turned on whether a table is queried directly by id:

| Child table | Parent | Scoping |
|---|---|---|
| `training_log_sets` | `training_log` | denormalized `user_id` |
| `injury_exercise_modifications` | `injury_log` | parent-JOIN |
| `plan_items` | `training_plans` | denormalized `user_id` |
| `plan_item_disposition` | `plan_items` | denormalized `user_id` |
| `plan_reviews` | `training_plans` | parent-JOIN |
| `plan_travel` | `training_plans` | parent-JOIN |
| `coaching_chat` | `training_plans` | denormalized `user_id` |
| `locale_equipment` | `locale_profiles` | denormalized `user_id` (composite key) |
| `exercise_equipment` | shared catalogs | unscoped (shared) |

Tables queried by id (e.g. `plan_items` via `/plans/<plan_id>/items/<id>`)
get a denormalized `user_id` so the scope check is a column comparison
instead of a JOIN. Tables only ever read through their parent stay
parent-scoped.

### Composite UNIQUE constraints

A small set of tables enforce `UNIQUE (user_id, ...)` so two users can
each own their own version of the same logical row:

| Table | Constraint | Why |
|---|---|---|
| `current_rx` | `UNIQUE (user_id, exercise)` | Each user has one baseline per exercise. UPSERT target. |
| `body_metrics` | `UNIQUE (user_id, date)` | One body-metrics row per user per day. |
| `wellness_log` | `UNIQUE (user_id, timestamp_ms)` | Garmin re-syncs are idempotent. |
| `clothing_options` | `UNIQUE (user_id, category, value)` | User's clothing autocomplete accumulates without leaking across users. |
| `locale_profiles` | `PRIMARY KEY (user_id, locale)` | Two users can each own a "home" or "hotel" location. |
| `locale_equipment` | `PRIMARY KEY (user_id, locale, equipment_id)` + composite FK | Locked to its parent. |
| `user_purchase_recommendations` | `PRIMARY KEY (user_id, purchase_id)` | Per-user state on a shared catalog. |

### Cross-user defenses on writes

Update / delete / fetch-by-id handlers always include `AND user_id = ?` in
the WHERE clause. Even if a logged-in user crafts a URL pointing at
another user's row id, the query returns 0 rows and the route flashes
"not found" instead of silently leaking or destroying data.

The admin dashboard (`routes/admin.py`) is the one place that bypasses
the user-id check, gated by `_require_admin()` returning 403 unless
`current_user_id() == 1`.

---

## Table reference

Each entry covers: purpose, scope, columns of note, indexes, key
constraints, and where the table is read or written from. Backend
divergences are called out where they exist.

### Identity and auth

#### `users`

The auth root. Every per-user row in every other table FKs back here.

- Columns: `id` (SERIAL/INTEGER PK), `username` (TEXT NOT NULL UNIQUE),
  `email` (TEXT UNIQUE — nullable), `password_hash` (TEXT NOT NULL),
  `display_name` (TEXT), `created_at`, `last_login`.
- Indexes: PK, UNIQUE on `username`, UNIQUE on `email`.
- Types: `created_at`/`last_login` are `TIMESTAMP`. Templates that slice
  date strings should pass values through `|string` first — Jinja's
  default Python `datetime` `__str__` produces an ISO 8601 prefix that's
  safe to slice (`{{ row.created_at|string|truncate(10, end='') }}`).
- Writes: `routes/auth.py` (register, login last-login bump, password
  reset rehash); `routes/profile.py` (display name + email edit, change
  password); `routes/admin.py` (delete cascade ends with this row).
- Reads: `routes/auth.py:current_user`, `app.py:_require_login` hydration,
  `routes/admin.py` listing.

#### `password_resets`

Single-use, time-limited tokens issued by `/auth/forgot`.

- Columns: `token` (TEXT PK), `user_id` (FK), `created_at`, `expires_at`,
  `used_at` (NULL until consumed).
- Index: `(user_id)` for the rare admin lookup.
- TTL: 30 minutes (constant `PASSWORD_RESET_TTL_MIN` in
  `routes/auth.py`).
- Single-use: `used_at` is set on successful reset; the route refuses
  any token where `used_at IS NOT NULL`.
- Writes: `routes/auth.py` only (`forgot` inserts; `reset` marks used).

#### `athlete_profile`

Per-user stable facts surfaced to the coach (`get_coaching_context()`
includes `ctx['athlete_profile']`).

- Columns: `user_id` (PK + FK), `date_of_birth`, `sex`, `height_cm`,
  `primary_sport`, `weekly_hours_target`, `training_window`, `notes`,
  `updated_at`. (The legacy `target_event_name` + `target_event_date`
  columns were dropped in D-66 Layer 3B Scope B; target races now live
  in `race_events` as their sole source of truth — see the
  `race_events` section.)
- Helpers: `athlete.py:get_athlete_profile(db, user_id)` and
  `upsert_athlete_profile(db, user_id, **fields)`. `PROFILE_FIELDS`
  allowlist — unknown keys silently dropped, so `request.form` can be
  passed straight through.
- Timestamp: `upsert_athlete_profile` sets `updated_at = NOW()` on every
  UPDATE.
- Surfaced on: `/profile` (Athlete tab) and in every coaching API call's
  context block.

#### `admin_audit`

Append-only log of admin mutations. Added PR #12 alongside the cascade-
delete handler; surfaced for browsing by the read view added in the
2026-05-11 session.

- Columns: `id` (SERIAL/INTEGER PK), `actor_user_id` (INTEGER FK to
  `users(id)` — NULLABLE so the row survives if the admin who took the
  action is later deleted), `action` (TEXT — conventional values like
  `'delete_user'`; freeform, one string per admin mutation type),
  `target_user_id` (INTEGER, **deliberately FK-less** so the row also
  survives target deletion), `target_username` (TEXT — snapshotted at
  delete time), `details` (TEXT, optional JSON or freetext payload),
  `created_at`.
- Index: `(created_at DESC)` for the read view.
- Writes: `routes/admin.py:delete_user` only, **in the same transaction
  as the cascade delete** — both succeed or both roll back.
- Reads: `routes/admin.py:audit` (the read view at `/admin/audit`).
- **Convention:** every new admin-mutation handler should append a row
  with a fresh `action` string. Don't add the FK to `target_user_id` —
  the row's job is to outlive the target. Audit rows are intentionally
  not in `_delete_user_and_data`'s cascade chain.

#### `api_tokens`

Per-user bearer tokens for headless access to `/coaching/api/*`. Added
PR #15; `expires_at` column added in the 2026-05-11 session.

- Columns: `id` (SERIAL/INTEGER PK), `user_id` (INTEGER NOT NULL FK),
  `name` (TEXT — user-supplied label), `token_hash` (TEXT NOT NULL
  UNIQUE — SHA-256 hex digest of the plaintext), `created_at`,
  `last_used_at` (updated by `verify_bearer_token` on every hit),
  `revoked_at` (soft-revoke; preserves audit trail),
  `expires_at` (NULL = never expires; otherwise the verify path
  refuses the token when the timestamp is in the past).
- Index: `(user_id)`.
- **Hashing convention:** plaintext is `aid_<base64url(32)>` (32 bytes
  of cryptographic random with a stable prefix). Shown to the user
  exactly once at creation via one-shot session storage
  (`flask_session['new_api_token_plaintext']`) and never persisted.
  Verification = SHA-256 the inbound header value and look up by
  `token_hash`. **SHA-256, not bcrypt**: tokens are crypto-random with
  no brute-force surface, and the verify path needs a deterministic
  hash for index lookup.
- Writes: `routes/profile.py:create_api_token` (issue),
  `routes/profile.py:revoke_api_token` (soft-revoke),
  `routes/auth.py:verify_bearer_token` (`last_used_at` bump on hit).
- Reads: `routes/profile.py:edit` (token list on the API access tab),
  `routes/auth.py:verify_bearer_token` (the auth gate).
- Cascade-delete: `routes/admin._delete_user_and_data` picks up
  `api_tokens` before `users`. **Any new user-scoped table must be
  added to that chain.**

### Strength training

#### `training_sessions`

Wraps a single workout session — one row per "trip to the gym."
Aggregates the per-exercise rows in `training_log`.

- Columns: `id`, `user_id`, `date`, `notes`, `plan_item_id` (optional FK
  to the plan item this session was the completion of), `created_at`.
- Index: `(user_id, date)` for the daily view; `(date)` legacy.
- Writes: `routes/training.py` (form submission), `routes/garmin.py` (FIT
  import), `routes/natural_log.py` (NLP entry).

#### `training_log`

Per-exercise rows within a session. The richest table — carries the
prescription, the actuals, the computed outcome, and the projected next
session.

- Columns: `id`, `user_id`, `date`, `exercise` (TEXT — denormalized
  from `exercise_inventory` for stability across catalog edits),
  `exercise_id` (FK), `sub_group`, `recovery_cost`, `target_*`,
  `actual_*`, `rpe`, `rest_sec`, `outcome`, `est_1rm`, `volume`,
  `body_weight`, `next_*`, `progression_level`, `notes`,
  `garmin_activity_id`, `plan_item_id`, `session_id`, `created_at`.
- Indexes: `(user_id, date)`, `(date)`, `(exercise)`, `(session_id)`.
- Single source of truth for writing rows that should update `current_rx`:
  `rx_engine.apply_session_outcome()`. The training form (`routes/training.py`)
  and the FIT importer (`routes/garmin.py`) both route through it.
  **Exception:** `routes/natural_log.py:/log-natural/save` inserts
  `training_log` / `training_log_sets` directly with `outcome=NULL` and
  does **not** call `apply_session_outcome` or update `current_rx`. See
  `rx_engine_spec.md` §12.7 — flagged as an open item for v2 to decide
  (journal-only by design vs. unintended bypass).
- `outcome` literally holds `'PROGRESS ↑'`, `'REPEAT →'`, `'REDUCE ↓'`
  (the arrows are part of the value) or `NULL` on bootstrap-mode FIT
  imports and NLP entries. The arrowed strings drive the
  Family-B-promotion logic and the `consecutive_failures` /
  `sessions_since_progress` counters in `current_rx`. Templates that
  display the value should render it as-is.

#### `training_log_sets`

Per-set actuals. One row per set within a `training_log` entry.

- Columns: `id`, `user_id` (denormalized), `training_log_id` (FK with
  `ON DELETE CASCADE`), `set_number`, `reps`, `weight_lbs`,
  `duration_sec`.
- Index: `(training_log_id)`.
- Writes: same surfaces as `training_log` — anywhere a strength session
  lands.
- `ON DELETE CASCADE` on `training_log_id` is the only cascade in the
  schema; deleting a `training_log` row also drops its sets without an
  explicit DELETE in route code.

#### `current_rx`

The **prescribed baseline** for each exercise per user. Not last
performance — the recipe the next session is projected from.

- Columns: `id`, `user_id`, `exercise`, `exercise_id`, `discipline`,
  `type`, `movement_pattern`, `inventory_sugg_volume`, `current_sets`,
  `current_reps`, `current_weight`, `current_duration`,
  `last_performed`, `last_outcome`, `consecutive_failures`,
  `sessions_since_progress`, `rx_source`, `weight_increment`,
  `next_sets`, `next_reps`, `next_weight`, `next_duration`.
- Constraint: `UNIQUE (user_id, exercise)` — UPSERT target.
- Plateau detection: `sessions_since_progress >= 5` raises
  `deload_flags` in coaching context; the user can also one-click deload
  on `/rx`.
- Writes: `rx_engine.apply_session_outcome()` (UPSERT scoped on
  `(user_id, exercise)`), `routes/rx.py` (manual edits + deload),
  `routes/natural_log.py` (NLP edits flow through `rx_engine`).
- Seed: `init_db._seed_current_rx_for_user(user_id)` populates rows for
  every catalog exercise on registration. Idempotent via the
  composite UNIQUE.

### Cardio

#### `cardio_log`

One row per cardio activity. Holds the full Garmin metric set; manual
entries leave most cells NULL.

- Columns: `id`, `user_id`, `date`, `activity`, `activity_name`,
  `duration_min`, `moving_time_min`, `distance_mi`, `avg_pace`,
  `avg_speed`, `avg_hr`, `max_hr`, `calories`, `elev_gain_ft`,
  `elev_loss_ft`, `avg_cadence`, `max_cadence`, `avg_power`, `max_power`,
  `norm_power`, `aerobic_te`, `anaerobic_te`, `swolf`,
  `active_lengths`, `stride_length_m`, `vert_oscillation_cm`,
  `vert_ratio_pct`, `gct_ms`, `gct_balance`, `garmin_activity_id`,
  `plan_item_id`, `notes`, `created_at`.
- Indexes: `(user_id, date)`, `(date)` legacy.
- Pace derivation: `routes/cardio.py:_save` auto-derives `avg_pace` from
  `moving_time_min` (or `duration_min`) and `distance_mi` when the
  field is left blank.
- Writes: `routes/cardio.py` form, `routes/garmin.py` FIT import,
  `routes/natural_log.py` NLP.

### Body and conditions

#### `body_metrics`

Daily body-composition snapshot.

- Columns: `id`, `user_id`, `date`, `weight_lbs`, `body_fat_pct`,
  `vo2_max`, `resting_hr`, `notes`, `created_at`.
- Constraint: `UNIQUE (user_id, date)` — one snapshot per day. UPSERT
  target via `INSERT … ON CONFLICT (user_id, date) DO UPDATE SET ...`
  in `routes/body.py`.
- Index: `(user_id, date)`, `(date)` legacy.
- Writes: `routes/body.py`, `routes/natural_log.py` (NLP).

#### `wellness_self_report`

Per-day self-reported sleep / energy / soreness / mood. Added 2026-05-11
alongside the unified `/wellness` dashboard. Distinct from
`wellness_log` (Garmin-imported per-minute series) and `conditions_log`
(weather + clothing tied to a cardio session) — neither of those have a
spot for general daily wellness.

- Columns: `id`, `user_id`, `date`, `sleep_hours` (REAL, 0–24),
  `sleep_quality` / `energy` / `soreness` / `mood` (INTEGER 1–5,
  nullable), `notes`, `created_at`, `updated_at`.
- Constraint: `UNIQUE (user_id, date)` — one report per day. The
  `/wellness` POST does an existence-check + UPDATE-or-INSERT (manual
  UPSERT shape because the form doesn't always carry every column).
- Index: `(user_id, date)`.
- Writes: `routes/wellness.py:index` (POST handler) only.
- Reads: `routes/wellness.py:index` (charts the last N days where N is
  one of {7, 30, 90}).
- Cascade-delete: in `_delete_user_and_data` after `wellness_log`.
- **Scale convention:** for `sleep_quality`, `energy`, `mood` higher is
  better. For `soreness` higher is better too (5 = fresh, 1 = sore
  everywhere). The template makes this explicit so the user doesn't
  invert it.

#### `conditions_log`

Weather + clothing per activity. Optionally linked to a `cardio_log` row
via `cardio_log_id`.

- Columns: `id`, `user_id`, `date`, `activity`, `temp_f`,
  `feels_like_f`, `wind_mph`, `wind_dir`, `conditions`, eleven clothing
  category columns (`headwear`, `face_neck`, `upper_shell`,
  `upper_mid_layer`, `upper_base_layer`, `lower_outer`, `lower_under`,
  `gloves`, `arm_warmers`, `socks`, `footwear`), `comfort` (1–5),
  `comfort_notes`, `cardio_log_id`, `created_at`.
- Index: `(user_id, date)`.
- Writes: `routes/conditions.py` only.
- Side effect: each new clothing value the user types is auto-persisted
  to `clothing_options` via `ON CONFLICT DO NOTHING` so the autocomplete
  on the next form fills in.

#### `clothing_options`

Per-user accumulating autocomplete dictionary for the 11 clothing fields
on `/conditions/new`.

- Columns: `id`, `user_id`, `category`, `value`.
- Constraint: `UNIQUE (user_id, category, value)` — UPSERT target with
  `DO NOTHING`.
- Writes: `routes/conditions.py:_save` only (auto-persist as the user
  types).
- Seeds: none — values accumulate from real input.

### Injuries

#### `injury_log`

Active and resolved injuries per user.

- Columns: `id`, `user_id`, `start_date`, `body_part`, `description`,
  `severity` (1–5), `modifications_needed`, `status` (`Active` /
  `Resolved`), `resolved_date`, `created_at`.
- Surfaced in coaching context as a list of currently-active rows so
  Claude knows to apply substitutions.

#### `injury_exercise_modifications`

Per-exercise overrides while an injury is active.

- Columns: `id`, `injury_id` (FK), `exercise_id` (FK to
  `exercise_inventory`), `substitute_exercise_id` (FK, optional —
  swap target), `modification_type` (`modify` or `swap`),
  `modification_notes`, `created_at`.
- Scoping: parent-JOIN through `injury_log.user_id`. Routes that touch
  these rows always join: `injury_id IN (SELECT id FROM injury_log
  WHERE user_id = ?)`.

### Plans and scheduling

#### `training_plans`

A coach-generated or imported plan. One row per plan.

- Columns: `id`, `user_id`, `name`, `description`, `sport_focus`,
  `start_date`, `end_date`, `status` (active/archived), `source_json`
  (the raw Claude output for re-derivation), `race_goals`,
  `created_at`.

#### `plan_items`

The individual scheduled workouts within a plan. Denormalized `user_id`
for fast scoping without a JOIN to `training_plans`.

- Columns: `id`, `user_id`, `plan_id` (FK), `item_date`, `sport_type`,
  `workout_name`, `description`, `target_duration_min`,
  `target_distance_mi`, `intensity`, `garmin_workout_json`, `status`
  (`scheduled`/`completed`/`skipped`/`swapped`), `notes`,
  `calorie_target`, `macro_carb_pct`, `macro_protein_pct`,
  `macro_fat_pct`, `session_fueling`, `created_at`.
- Indexes: `(plan_id)`, `(item_date)`, `(user_id, item_date)`.
- Status transitions:
  - `scheduled` → `completed` when a `cardio_log` or `training_session`
    is auto-matched or manually linked.
  - `scheduled` → `swapped` when a different activity is logged "in
    place of" this item.
  - `scheduled` → `skipped` via the bulk editor or an explicit skip.
- Writes: `routes/plans.py` (CRUD + bulk editor), `routes/cardio.py` and
  `routes/training.py` (auto-match completion), `routes/garmin.py`
  (FIT-driven completion), `plan_match.py` (auto-match logic).

#### `plan_item_disposition`

Audit trail for auto-match / swap decisions.

- Columns: `id`, `user_id`, `plan_item_id` (FK), `log_type`
  (`cardio_log` / `training_log`), `log_id` (the log row that
  satisfied/swapped this item), `disposition` ∈
  {`completed`, `swapped_for`}, `reason`, `created_at`.
- Indexes: `(plan_item_id)`, `(log_type, log_id)`.
- **`in_addition_to` is not a disposition value.** That UI option leaves
  the log standalone (`plan_item_id=NULL`) and writes no disposition
  row. The disposition table only tracks the two values above.
- Surfaced in coaching context as `recent_dispositions` (last 30 days)
  so Claude sees what the user has been swapping or skipping.

#### `plan_reviews`

Tier 1/2/3 review records — when the user sat down with the coach to
review progress.

- Columns: `id`, `plan_id` (FK), `tier` (1/2/3), `sessions_reviewed`,
  `notes`, `created_at`.
- Scoping: parent-JOIN through `training_plans.user_id`.

#### `plan_travel`

Travel periods linked to a plan — date range + locale + city, used by
the coach to plan around hotel-gym constraints.

- Columns: `id`, `plan_id` (FK), `start_date`, `end_date`, `locale`
  (`home`/`hotel`/`partner`/`airport`), `city`, `notes`,
  `indoor_only`, `created_at`.
- Scoping: parent-JOIN.

### Coaching

#### `coaching_chat`

Per-plan conversation history with Claude.

- Columns: `id`, `user_id` (denormalized), `plan_id` (FK), `role`
  (`user`/`assistant`), `content`, `actions_json` (structured
  plan-patch / preference-save payload from the assistant),
  `created_at`.
- Surfaced in `chat_with_coach()` as last-10 turns of history, sent to
  Claude on every chat turn.

#### `coaching_preferences`

Persistent coach preferences extracted from chat / plan reviews / natural
logs / workout notes.

- Columns: `id`, `user_id`, `category`, `content`, `permanent` (0/1),
  `source_feedback_id` (FK back to `feedback_log` for provenance),
  `created_at`.
- Surfaced in coaching context as `coaching_preferences`. `permanent=1`
  rules are honoured strictly; `permanent=0` are advisory.
- Writes: `coaching.save_preferences_from_feedback()` (every entry
  point);  `routes/profile.py` (manual add / delete).

#### `feedback_log`

Verbatim raw text the user wrote, stored before normalization.

- Columns: `id`, `user_id`, `source` ∈ {`chat`, `plan_review`,
  `natural_log`, `workout_note_strength`, `workout_note_cardio`},
  `source_ref_id` (the row id in the originating table — plan id, log
  id, etc.), `raw_content`, `captured_at`.
- Pipeline: written by `coaching.capture_and_normalize_feedback()`
  **only when at least one preference is extracted** (deferred so pure
  conversational chatter doesn't pollute `/profile`'s feedback view).
- Surfaced via `coaching_preferences.source_feedback_id` → "view
  original" link on `/profile`.

### Equipment, locations, and purchases

#### `equipment_items`

Shared catalog of equipment items (DB, KB, pull-up bar, kayak, etc.).

- Columns: `id`, `tag` (machine key, UNIQUE), `label` (display),
  `category`.
- Seeded from `EQUIPMENT_CATEGORIES` Python list at the top of
  `init_db.py`. UPSERT-on-tag.

#### `exercise_equipment`

Many-to-many between `exercise_inventory` and `equipment_items`.
**Shared (no `user_id`).**

- Columns: `exercise_id` (FK), `equipment_id` (FK), `option_group` (an
  exercise can have alternative equipment options — same
  `option_group` means "one of these is enough"; different groups mean
  "you need at least one from each").
- Used to derive: "exercises this purchase unlocks" on `/purchases/<id>`,
  and "what exercises does this user's home setup support."

#### `locale_profiles`

Per-user equipment profiles for the 4 locale slots: `home`, `hotel`,
`partner`, `airport`.

- Columns: `user_id` + `locale` (composite PK), `equipment` (legacy
  serialized — unused since Session 3), `notes`, `city`, `updated_at`.
- Two users can each own a `home` row.
- Writes: `routes/locales.py` only. UPSERT on `(user_id, locale)` with
  `DO UPDATE SET notes=excluded.notes, city=excluded.city,
  updated_at=excluded.updated_at`.
- Note on the `equipment` TEXT column: legacy, replaced by
  `locale_equipment` rows. Never read or written by current code.

#### `locale_equipment`

Per-user, per-locale equipment selections — the actual joinable data.

- Columns: `user_id`, `locale`, `equipment_id` (FK to
  `equipment_items`).
- PK: `(user_id, locale, equipment_id)`. **Composite FK** to
  `locale_profiles(user_id, locale)` to keep referential integrity at
  the user level (so user A can't reference user B's `home` profile).
- Save flow: replace-all per locale (`DELETE FROM locale_equipment WHERE
  user_id=? AND locale=?` then INSERT each selected tag).

#### `purchase_recommendations`

**Shared catalog** of recommended gear purchases. UPSERT-on-`slug` so
edits to the seed list propagate without disturbing per-user state.

- Columns: `id`, `slug` (UNIQUE), `label`, `equipment_id` (FK to
  `equipment_items` — lets "exercises this unlocks" be derived live
  via `exercise_equipment`), `est_cost_low`, `est_cost_high`,
  `priority`, `rationale`, `sort_order`, `active`.
- Seeded from `PURCHASE_RECOMMENDATIONS` in `init_db.py` on every cold
  start.

#### `user_purchase_recommendations`

Per-user state on each recommendation.

- Columns: `user_id`, `purchase_id`, `status` ∈
  {`wanted`, `owned`, `passed`}, `user_notes`, `updated_at`.
- PK: `(user_id, purchase_id)`. UPSERT on POST; clearing status deletes
  the row.

### Garmin

#### `garmin_auth`

Garmin Connect OAuth session per user. Single row per user.

- Columns: `id`, `user_id`, `garmin_username`, `garth_session` (JSON
  blob from `garth`), `created_at`, `updated_at`.
- Writes: `routes/garmin.py:auth` flow, `garmin_connect.py:save_session`.
- **Parked carry-forward:** `/tmp/garth_session` file caching is
  process-shared. The DB row is per-user, but the in-memory garth
  session at `/tmp/garth_session` is whatever was last loaded —
  multi-user Garmin sync isn't safe yet. See the parked items in
  `HANDOFF.md`.

#### `garmin_workouts`

Records of plan items pushed to Garmin Connect as scheduled workouts.

- Columns: `id`, `user_id`, `plan_item_id` (FK), `garmin_workout_id`
  (Garmin's id), `workout_name`, `sport_type`, `scheduled_date`,
  `status`, `created_at`.
- Lets us avoid double-pushing the same plan item.

#### `wellness_log`

Per-second wellness data from Garmin wellness FIT files.

- Columns: `id`, `user_id`, `date`, `timestamp_ms`, `heart_rate`,
  `stress_level`, `body_battery`, `respiration_rate`, `steps`,
  `active_calories`, `active_time_s`, `distance_m`, `activity_type`,
  `source`.
- Constraint: `UNIQUE (user_id, timestamp_ms)` — re-imports are
  idempotent. Insert uses `ON CONFLICT DO NOTHING`.
- Indexes: `(user_id, date)`, `(date)` legacy.
- Surfaced in coaching context as `wellness_summary` — aggregated trends
  for the lookback window.

### Provider integrations

D-50 Phase 1 schema per `aidstation-sources/Athlete_Data_Integration_Spec_v3.md`
§4–§6. Tables exist; route wiring lands in a subsequent PR. Garmin
remains on the legacy `garmin_auth` table above (D-55 paused until
Garmin reopens API access; `provider_auth.session_blob` is the
designed destination once Garmin can be rebuilt).

#### `provider_auth`

Per-user, per-provider credentials and registration state. Replaces
the legacy `garmin_auth` shape for every non-Garmin provider; Garmin
will join when rebuilt onto `session_blob`.

- Columns: `id`, `user_id`, `provider` (slug matching
  `oauth_callbacks._PROVIDERS`), `access_token`, `refresh_token`,
  `token_expires_at`, `session_blob` (non-OAuth session JSON; Garmin
  only), `provider_user_id`, `scopes`, `webhook_token` (Wahoo —
  rotates per event), `status` (active / revoked / error /
  pending_backfill / migrating), `registered_at`, `created_at`,
  `updated_at`.
- Constraint: `UNIQUE (user_id, provider)`.
- Index: partial `provider_auth_status_idx` on `status` WHERE
  `status IN ('error', 'pending_backfill')` for error/backfill scans.

#### `webhook_events`

Append-only audit + dedup log for incoming provider pushes.

- Columns: `id`, `provider`, `event_type`, `provider_user_id`,
  `entity_id` (provider-side workout/exercise/route ID; dedup key),
  `user_id` (NULL while pending dispatch resolution), `payload`
  (raw JSON body as TEXT), `signature_ok`, `received_at`,
  `processed_at` (NULL = pending), `error`.
- Indexes: lookup `(provider, provider_user_id, entity_id, event_type)`;
  partial pending index on `received_at` WHERE `processed_at IS NULL`.

#### `polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_continuous_hr_samples`

Per-provider Polar tables. All user-scoped.

- `polar_sleep` — UNIQUE `(user_id, date)`; sleep stages in
  `stages_json`; UPSERT-capable per spec note (Polar re-analyzes
  post-sync).
- `polar_nightly_recharge` — ANS charge + HRV + recovery.
  UNIQUE `(user_id, date)`.
- `polar_cardio_load` — daily TRIMP + acute/chronic load.
  UNIQUE `(user_id, date)`. Polar's ACWR equivalent; treat as one
  input, not authoritative.
- `polar_continuous_hr_samples` — opt-in continuous HR.
  UNIQUE `(user_id, timestamp_ms)`; index `(user_id, timestamp_ms)`.

#### `wahoo_plans`

Outbound push log for Wahoo workout plans.

- Columns: `id`, `user_id`, `plan_item_id` (FK to `plan_items`),
  `wahoo_plan_id`, `wahoo_workout_id`, `external_id`,
  `provider_updated_at`, `status` (pushed / completed / cancelled /
  error), `push_payload`, `created_at`, `updated_at`.
- Index: `(plan_item_id)`.
- **Note:** inbound Wahoo activities flow into `cardio_log` via the
  new `cardio_log.wahoo_workout_id` column; no separate inbound table.

#### `coros_daily_summary`, `coros_hrv_samples`, `coros_plans`

Per-provider COROS tables.

- `coros_daily_summary` — daily wellness + sleep window.
  UNIQUE `(user_id, happen_day)`.
- `coros_hrv_samples` — per-sample HRV + HR.
  UNIQUE `(user_id, timestamp_s)`.
- `coros_plans` — outbound plan push log. FK `plan_items`.
  Index `(plan_item_id)`.

#### Foreign-id columns on existing tables

Provider dedup IDs added to existing app tables (see also `garmin_activity_id`
already present):

- `cardio_log` — `polar_exercise_id`, `wahoo_workout_id`, `coros_label_id`,
  `rwgps_trip_id`.
- `training_log` — `polar_exercise_id`, `wahoo_workout_id`,
  `coros_label_id`. (No `rwgps_trip_id` — RWGPS is cycling-only.)

`strava_activity_id` on `cardio_log` is deferred per spec §6 until
Strava integration design lands (D-48).

### Shared catalogs

These tables have **no `user_id`** column. Edits propagate to all users.
Seeded from Python lists in `init_db.py` on cold start (UPSERT on
unique key).

#### `exercise_inventory`

Master exercise list. Every exercise referenced in `current_rx`,
`training_log`, or anywhere else points back here via `exercise_id`
or by name.

- Columns: `id`, `exercise` (UNIQUE), `type`, `discipline`,
  `equipment`, `muscles_worked`, `skills_ar_carryover`,
  `where_available`, `source`, `suggested_volume`,
  `substitution_group`, `recovery_cost`, `movement_pattern`,
  `session_placement`, `form_cue`, `video_reference`,
  `weight_increment`.
- Adding a new exercise: append to `EXERCISE_INVENTORY` in `init_db.py`,
  cold start, then `_seed_current_rx_for_user` will add a baseline row
  per user on next bootstrap.

#### `training_modalities`

Activity types (Running, Treadmill, Road Cycling, etc.) with AR-carryover
ratings.

- Columns: `id`, `activity` (UNIQUE), `category`, `primary_benefits`,
  `equipment_needed`, `where_available`, `ar_carryover`.

#### `training_methods`

Coaching methods (e.g. interval structures, periodization patterns) for
optional reference.

- Columns: `id`, `method`, `description`, `apply_to`, `source`.

---

## UI → table interaction map

Where each table is read or written, derived from grep of every routes/
file plus the engine helpers. Read this as: "to find every code path
that touches X, look here."

| Table | Routes that touch it | Engine helpers |
|---|---|---|
| `users` | `auth`, `profile`, `admin` | — |
| `password_resets` | `auth` | — |
| `athlete_profile` | `profile`, `admin` (via cascade) | `athlete.py`, `coaching.py:get_coaching_context` |
| `exercise_inventory` | `injuries`, `natural_log`, `references`, `rx`, `training` | `rx_engine.py` |
| `training_sessions` | `garmin`, `natural_log`, `training`, `admin` | — |
| `training_log` | `dashboard`, `garmin`, `natural_log`, `training`, `admin` | `coaching.py`, `rx_engine.py` |
| `training_log_sets` | `garmin`, `natural_log`, `training`, `admin` | — |
| `current_rx` | `dashboard`, `natural_log`, `references`, `rx`, `training`, `admin` | `coaching.py`, `rx_engine.py` |
| `cardio_log` | `cardio`, `conditions`, `dashboard`, `garmin`, `natural_log`, `admin` | `coaching.py` |
| `body_metrics` | `body`, `dashboard`, `garmin`, `natural_log`, `training`, `admin` | `coaching.py` |
| `conditions_log` | `conditions`, `admin` | `coaching.py` |
| `wellness_self_report` | `wellness`, `admin` (cascade) | — |
| `clothing_options` | `conditions`, `admin` | — |
| `injury_log` | `dashboard`, `injuries`, `admin` | `coaching.py` |
| `injury_exercise_modifications` | `injuries`, `plans`, `training`, `admin` | `coaching.py` |
| `training_plans` | `coaching`, `dashboard`, `plans`, `admin` | `coaching.py` |
| `plan_items` | `cardio`, `coaching`, `dashboard`, `garmin`, `natural_log`, `plans`, `training`, `admin` | `coaching.py`, `plan_match.py` |
| `plan_item_disposition` | `admin` | `coaching.py`, `plan_match.py` |
| `plan_reviews` | `coaching`, `plans`, `admin` | — |
| `plan_travel` | `coaching`, `dashboard`, `plans`, `admin` | — |
| `coaching_chat` | `coaching`, `plans`, `admin` | — |
| `coaching_preferences` | `coaching`, `profile`, `admin` | `coaching.py` |
| `feedback_log` | `profile`, `admin` | `coaching.py` |
| `equipment_items` | `locales`, `purchases`, `references` | — |
| `exercise_equipment` | `purchases`, `references` | — |
| `locale_profiles` | `coaching`, `dashboard`, `locales`, `plans`, `references`, `rx` | `coaching.py` |
| `locale_equipment` | `locales`, `purchases`, `references`, `admin` | `coaching.py` |
| `purchase_recommendations` | `purchases` | — |
| `user_purchase_recommendations` | `purchases`, `admin` | — |
| `garmin_auth` | `garmin`, `admin` | `garmin_connect.py` |
| `garmin_workouts` | `plans`, `admin` | — |
| `wellness_log` | `garmin`, `admin` | `coaching.py` |
| `training_modalities` | — | `coaching.py` (reference only) |
| `training_methods` | — | (read in plan generation) |
| `admin_audit` | `admin` (write in `delete_user`, read in `audit`) | — |
| `api_tokens` | `auth` (verify), `profile` (issue, revoke, list), `admin` (cascade) | — |

---

## Engine helpers

Three modules outside `routes/` carry significant DB logic:

### `rx_engine.py` — single source of truth for strength session writes

`apply_session_outcome(db, exercise, date, sets, targets..., rx_source,
user_id=None)` is the **only** way to write a logged strength session.
Implements:

- The Family-A 2×-on-significance kicker and Family-B baseline
  promotion.
- UPSERT on `current_rx` scoped to `(user_id, exercise)`.
- Inserts the per-set rows in `training_log_sets`.
- Bumps `consecutive_failures` and `sessions_since_progress` based on
  the computed outcome; resets both on PROGRESS.
- Bootstrap mode for target-less FIT imports — picks the prescribed
  values from `current_rx` if the caller didn't supply them.

`compute_deload_baseline()` and `project_next_from_current()` are pure
helpers in `calculations.py` used by the deload route and by manual
edits on `/rx`.

### `plan_match.py` — auto-matching activities to plan items

`find_best_match(db, activity, user_id=None)` searches the user's
upcoming + recent `plan_items` (-3 to +2 days, closer wins on ties).
Returns `None` when no candidate scores ≥ 0.5; callers then prompt the
user.

`record_disposition(db, plan_item_id, log_type, log_id, disposition,
reason)` writes the audit row in `plan_item_disposition`.

### `coaching.py` — Claude API calls and context assembly

`get_coaching_context(db, plan_id, lookback_days, locale)` reads from a
broad swath of user-scoped tables to build the JSON context block sent
to Claude on every coaching call:
`current_rx` (deload flags), `plan_item_disposition` (recent_dispositions),
`wellness_log` (wellness_summary), `coaching_preferences`,
`athlete_profile`, `injury_log` + `injury_exercise_modifications`,
`locale_profiles` + `locale_equipment`, `body_metrics`, recent
`cardio_log` + `training_log`.

`capture_and_normalize_feedback()` runs Haiku-based preference
extraction on raw user text (chat / plan review / natural log /
workout notes) and writes `feedback_log` + `coaching_preferences`
**only when at least one preference is extracted**. Question-shaped
inputs short-circuit before the Haiku call.

### `athlete.py` — `athlete_profile` UPSERT

`get_athlete_profile(db, user_id)` and `upsert_athlete_profile(db,
user_id, **fields)` with a `PROFILE_FIELDS` allowlist. `updated_at`
is set to `NOW()` on every UPDATE.

### `garmin_connect.py` — OAuth via `garth`

`save_session(db, garth_session, garmin_username)` writes the Garmin
OAuth row to `garmin_auth`. Note the `/tmp/garth_session` file caching
is process-shared and per-user multi-tenancy isn't yet safe — see
parked items in `HANDOFF.md`.

---

## Common patterns and gotchas

### `?` placeholders only

Every SQL string uses `?` placeholders. The PG adapter rewrites them to
`%s` on the way out. **Never write raw `%s` placeholders in route
code** — the `?` → `%s` translation in `database.py` assumes the route
side is `?`-only; mixed forms in one statement will misparse.

### UPSERT patterns

Use these PG forms in route code:

| Operation | SQL |
|---|---|
| Insert-or-skip | `INSERT … ON CONFLICT(...) DO NOTHING` |
| Insert-or-replace | `INSERT … ON CONFLICT(...) DO UPDATE SET ...` |
| Current timestamp | `CURRENT_TIMESTAMP` or `NOW()` |

`INSERT … ON CONFLICT DO NOTHING` is preferred for idempotent inserts
where a failed row should not abort the transaction — psycopg2's
`InFailedSqlTransaction` 500s the next write in the same request
otherwise.

### `RETURNING id` for new INSERTs

If a code path needs `cur.lastrowid` after an INSERT, the SQL **must
include `RETURNING id`**. The `_CompatCursor.lastrowid` wrapper does a
`fetchone()` against the cursor and returns the first column — without
`RETURNING id` there's nothing to fetch and `lastrowid` is `None`.

### Datetime columns in templates

`TIMESTAMP` columns come back as Python `datetime` objects, not strings.
Templates that slice a date prefix must wrap with `|string` first:

```jinja
{{ (row.updated_at|string)[:10] }}
```

Three sites do this today: `templates/locales/list.html`,
`templates/profile/edit.html` (`fb_captured_at` and `created_at`).
Anywhere new that reads a TIMESTAMP into a template needs the same
treatment.

### Per-user scoping on every read

Every per-user table query includes `WHERE user_id = ?` (using
`current_user_id()`). Fetch-by-id handlers add it as `AND user_id = ?`
even when the route already has the id from the URL — defends against
crafted URLs pointing at other users' rows.

### Composite UNIQUEs as UPSERT targets

`current_rx`, `body_metrics`, `wellness_log`, `clothing_options`, and
`locale_profiles` rely on `UNIQUE (user_id, ...)` constraints as
UPSERT conflict targets. The constraints are added by Session-2D
`_PG_MIGRATIONS` entries. New per-user tables that need the same
idempotency story should follow the same pattern.

### Flask session size limit

Cookie-based session, 4 KB hard cap. Wellness FIT import sidesteps this
by spooling parsed rows to `/tmp/wellness_*.json` and storing only the
path in `flask_session['wellness_tmp']`. The Garmin sync_preview
flow strips `nearby` candidates from the in-session blob before
storage. Use the same patterns for any other large transient data
flow.

### `_AUTH_EXEMPT_ENDPOINTS`

Adding a new auth-related route (e.g. an SSO callback) means appending
its endpoint name to `_AUTH_EXEMPT_ENDPOINTS` in `app.py`. Otherwise
the gate redirects un-authed users back to `/auth/login` and the new
flow never runs.

As of 2026-05-11 the set also includes `oauth_callbacks.callback` —
the single parameterised endpoint that backs the per-provider stub
callbacks at `/auth/<slug>/callback`. The slug allowlist lives in
`routes/oauth_callbacks.py:_PROVIDERS` (currently 18 entries: Garmin,
Strava, Polar, Wahoo, COROS, Google Health, Apple Health, Whoop,
TrainingPeaks, Zwift, V.02, Nike Run Club, Ride With GPS, Decathlon,
adidas Running, Komoot, Final Surge, MyFitnessPal). All return 501
until the real OAuth exchange is implemented; the per-user token
storage table is still TBD. Adding the next provider is a one-line
tuple append — no change here.

### Admin gate

`routes/admin.py` is the one place where `user_id` scoping is
intentionally bypassed (to list / delete other users' rows). The
blueprint-wide `_require_admin()` returns 403 unless
`current_user_id() == 1`. Don't paste admin-style raw deletes
elsewhere.

---

## Lifecycle examples

End-to-end traces of common user flows. Use these to map a UI surface
back to the tables it touches.

### Logging a strength session via `/training/new`

1. User submits the form. `routes/training.py:new_entry` POST handler
   builds a `training_sessions` row.
2. For each exercise on the form, calls
   `rx_engine.apply_session_outcome(db, exercise, date, sets, targets,
   rx_source='Manual', user_id=current_user_id())`. That helper:
   - Inserts a `training_log` row with the prescription and actuals.
   - Computes outcome (PROGRESS / REPEAT / FAIL) from the sets.
   - UPSERTs `current_rx` for `(user_id, exercise)`: bumps or resets
     `consecutive_failures` / `sessions_since_progress`, projects
     `next_*`.
   - Inserts per-set rows into `training_log_sets`.
3. Cascade hooks:
   - If `plan_item_id` was provided, `routes/training.py` updates that
     plan item's `status='completed'` and writes a
     `plan_item_disposition` row.
   - If `notes` were entered, `coaching.capture_and_normalize_feedback(
     source='workout_note_strength', ...)` runs Haiku extraction. If
     it finds a preference, a `feedback_log` row is written and
     `coaching_preferences` rows are inserted with
     `source_feedback_id` pointing back.

### Generating a plan via `/coaching/generate`

1. User fills form. `routes/coaching.py:generate` POST handler.
2. `coaching.get_coaching_context()` reads from many tables to build
   the context block (see Engine helpers above).
3. `coaching.generate_plan(...)` calls the Claude API with the cached
   system prompt + the context block.
4. Response parsed → `routes/plans.py:_create_plan_from_dict` writes
   one `training_plans` row + N `plan_items` rows in a transaction.
5. Travel schedule from the form → N `plan_travel` rows.
6. `_log_usage(usage, 'generate')` prints token cost to stdout.

### Auto-matching a Garmin FIT to a scheduled plan item

1. User uploads FIT or runs `/garmin/sync`. Parsed activity dict
   produced by `garmin_fit_parser.py:parse_fit`.
2. `plan_match.find_best_match(db, activity, user_id)`:
   - Searches `plan_items` in days `(0, -1, +1, -2, +2, -3)` order,
     scoping to `user_id`.
   - Scores by sport-compatibility + date-distance.
   - Returns the best candidate or `None`.
3. UI shows a four-option resolve dialog (`completed` / `swapped` /
   `in_addition_to` / `skip`).
4. On confirmation:
   - `cardio_log` (or `training_log`) row inserted, `plan_item_id`
     set if `completed` or `swapped`.
   - `plan_items.status` updated.
   - `plan_match.record_disposition(...)` writes
     `plan_item_disposition` (skipped for the `in_addition_to` and
     pure-skip paths).

### Asking the coach a question via `/coaching/chat/<plan_id>`

1. User types message. `routes/coaching.py:chat` POST handler.
2. `coaching.chat_with_coach(db, plan_id, message, history, locale)`:
   - Builds two cached system blocks: static base prompt at 1h TTL,
     coaching context at 5m TTL.
   - Sends last 10 turns of `coaching_chat` history + new user
     message.
3. Response parsed → user + assistant rows written to `coaching_chat`.
4. If `result['preferences_to_save']` is non-empty, `feedback_log` row
   written, `coaching_preferences` rows inserted with
   `source_feedback_id`. **Empty preferences → no feedback_log row,
   no coaching_preferences row.**
5. If `result['plan_patches']` is non-empty and `confirm_required` is
   false, allowed fields on `plan_items` are UPDATEd in place
   (`description`, `intensity`, `target_*`, etc.).
6. `_log_usage(usage, 'chat')` logs cache_read / cache_write / in /
   out tokens. Subsequent turns in the same chat session show
   `cache_read >> 0` for the system blocks.

### Admin deletes a user

1. Admin (user 1) clicks Delete on `/admin/`.
2. `routes/admin.py:delete_user` runs `_require_admin()`, refuses if
   target is user 1.
3. `_delete_user_and_data(db, user_id)` walks the FK-safe DELETE
   chain in a single transaction:
   - Children first: `training_log_sets`, `plan_item_disposition`,
     `plan_items`, `plan_reviews` and `plan_travel` (parent-JOIN),
     `coaching_chat`, `training_plans`.
   - Then: `training_log`, `training_sessions`, `cardio_log`,
     `body_metrics`, `conditions_log`,
     `injury_exercise_modifications` (parent-JOIN), `injury_log`,
     `coaching_preferences`, `feedback_log`, `wellness_log`,
     `garmin_auth`, `garmin_workouts`, `wellness_self_report`,
     `locale_equipment`, `locale_profiles`, `clothing_options`,
     `current_rx`, `athlete_profile`, `user_purchase_recommendations`,
     `api_tokens`.
   - Finally: `users`.
4. **Same transaction:** an `admin_audit` row is inserted with
   `actor_user_id=current_user_id()`, `action='delete_user'`,
   `target_user_id`, and the snapshotted `target_username`. `details`
   is left NULL today; reserved for any payload future actions want
   to record. The audit row is intentionally **not** in the cascade
   chain so it survives target deletion.
5. Shared catalogs (`exercise_inventory`, `equipment_items`,
   `purchase_recommendations`, `training_modalities`, `training_methods`,
   `exercise_equipment`) untouched.
6. Commit; success flash. The deleted user's session cookie, if it
   still existed, gets cleared on the next request by
   `_require_login`'s hydration check.
7. The row is visible at `/admin/audit` (filter by action or actor).

### Resetting a forgotten password

1. User clicks "Forgot password?" on `/auth/login` →
   `routes/auth.py:forgot`.
2. POST with email. Route looks up `users` by lowercased email.
3. If found, generates `secrets.token_urlsafe(32)`, INSERTs a row in
   `password_resets` with `expires_at = now + 30 min`.
4. `_send_password_reset_email(...)` calls
   `email_helper.send_email(...)`. With SendGrid configured, the link
   is emailed; without, it's logged to stdout.
5. Generic flash regardless of whether the email matched (defends
   against enumeration).
6. User clicks link → `/auth/reset/<token>`. Token validated
   (exists, `used_at IS NULL`, `expires_at > now`). On POST, password
   bcrypt-rehashed in `users`, `used_at` set on the token,
   `session.clear()`.
