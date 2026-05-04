# AIDSTATION — Session Handoff

**Date:** 2026-05-04
**Latest session branch (merged into `main`):** `claude/review-handoff-doc-gNJdO`
**Deploy state:** TrueNAS (Docker) + Vercel both shipped post-merge. First-run
bootstrap user (user_id=1) is registered on both. TrueNAS `.env` has
`SECRET_KEY` and `ANTHROPIC_API_KEY`. Session 2A backfill verified on
TrueNAS — all real data scoped to user 1.

---

## Session 2B kickoff — read this first

Sessions 0, 1, and 2A landed on `main` last session. Schema is fully
multi-user-shaped: every per-user table has a nullable `user_id` column,
backfilled to user 1, with composite `(user_id, date)` indexes. The app
is login-gated. **No query sites have been scoped yet** — that's 2B's
job.

### 2B scope (in priority order)

1. **The five hot-spot SELECTs** flagged in the multi-user roadmap
   below. These are the queries that would leak data the moment a
   second user registers, so they go first:
   - `routes/dashboard.py:84` — recent training log (no WHERE today)
   - `routes/cardio.py:30` — `WHERE 1=1` defaults to all users
   - `routes/training.py:27` — same pattern
   - `routes/body.py:13` — body metrics list, unscoped
   - `coaching.py:358` — body metrics in AI context, unscoped
2. **`garmin_connect.py` singleton** — `SELECT * FROM garmin_auth LIMIT 1`
   → `WHERE user_id = ?`. Process-shared `/tmp/garth_session` collision
   risk stays accepted until the parked Garmin per-user OAuth work
   unblocks; this is just the row-level scope fix.
3. **Every INSERT gains `user_id`.** New rows must be scoped from this
   point forward, even if the SELECT scoping for that table waits for
   2C. Otherwise 2D's NOT NULL won't be reachable. Touch every route
   that writes — list in the "Pattern: every INSERT site" section
   below.
4. **Helper import path.** Settle on `from routes.auth import current_user_id`.
   Returns `int | None`. Use directly in queries; trust that the
   `before_request` gate has populated the session before any
   non-`/auth/*` route runs.

### Out of scope for 2B (saved for 2C)

The remaining ~140 query sites across all the other `routes/*.py`
files, `coaching.py:get_coaching_context()`, `rx_engine.py`,
`plan_match.py`. SELECTs that don't appear in the hot-spot list keep
returning everything for now — until 2C finishes, the user 2 isolation
guarantee isn't there. Don't open `ALLOW_REGISTRATION` until 2D ships.

### Pattern reference for 2B

**Helper import:**
```python
from routes.auth import current_user_id
uid = current_user_id()  # int when logged in, None pre-login
```

**Pattern: scope a SELECT (no existing WHERE):**
```python
# Before
db.execute('SELECT * FROM cardio_log ORDER BY date DESC')
# After
db.execute('SELECT * FROM cardio_log WHERE user_id = ? ORDER BY date DESC',
           (current_user_id(),))
```

**Pattern: scope a SELECT (with existing WHERE):**
```python
# Before
db.execute('SELECT * FROM training_log WHERE date = ?', (d,))
# After
db.execute('SELECT * FROM training_log WHERE user_id = ? AND date = ?',
           (current_user_id(), d))
```

**Pattern: scope a SELECT with `WHERE 1=1`:**
```python
# Before
query = 'SELECT * FROM cardio_log WHERE 1=1'
# After
query = 'SELECT * FROM cardio_log WHERE user_id = ?'
params = [current_user_id()]
```

**Pattern: every INSERT site:**
```python
# Before
db.execute('INSERT INTO cardio_log (date, activity) VALUES (?, ?)', (d, a))
# After
db.execute('INSERT INTO cardio_log (user_id, date, activity) VALUES (?, ?, ?)',
           (current_user_id(), d, a))
```

For denormalized children (`plan_items`, `plan_item_disposition`,
`coaching_chat`, `training_log_sets`), pass `user_id` to the INSERT
explicitly — don't rely on inheriting from the parent at write time.
The 2A backfill walked parents because rows were already inserted; new
rows from 2B onward should write the column directly.

**Pattern: helpers that do INSERTs need a `user_id` parameter.**
`coaching.capture_feedback`, `coaching.save_preferences_from_feedback`,
`coaching.capture_and_normalize_feedback` all currently INSERT without
`user_id` — extend their signatures and update every call site (5
sites: `routes/coaching.py:chat` and `:review`, `routes/training.py:save_session`,
`routes/cardio.py:_save`, `routes/natural_log.py:save`).

`rx_engine.apply_session_outcome` writes to `current_rx` and
`training_log` — it'll need `user_id` plumbed in (callers pass it; no
session-context reach inside the engine).

`plan_match.record_disposition` writes `plan_item_disposition` — pass
`user_id` from the route layer.

`garmin_connect.py` writes `garmin_auth` (singleton today) and reads
`wellness_log`, `cardio_log` — INSERTs need user_id; the singleton SELECT
needs scope.

### 2B verification gate

Don't merge 2B without confirming:
- New strength session, cardio entry, body metric, conditions entry
  all save with `user_id=1` (run a quick `SELECT user_id FROM x ORDER
  BY id DESC LIMIT 1` on each)
- The five hot-spot routes still render correctly
- Coach chat / plan review / natural-log all complete and the new
  `feedback_log` rows have `user_id=1`
- `current_rx` updates from `apply_session_outcome` carry user_id
- App boot still 200s on `/`, `/training`, `/cardio`, `/body`, `/rx`,
  `/plans`

### Open issue worth investigating in 2B

A 500 was observed on Vercel **immediately after** the first-run
`/auth/register` POST — the account was created (login worked on
reload), but the post-register redirect to `/` rendered an error.
TrueNAS didn't repro. Could be a dashboard query that doesn't tolerate
a brand-new user state, or the wttr.in fetch timing out, or something
specific to Vercel's SQLite-on-/tmp ephemerality. Worth a glance at
Vercel function logs and at `routes/dashboard.py` while you're already
in the scoping pass.

### Known UNIQUE constraint debt for 2D

These are single-column UNIQUE constraints that prevent two users
from having parallel rows. Not a problem with one user, blocks 2D's
second-user verification:
- `current_rx.exercise UNIQUE` → `UNIQUE(user_id, exercise)`
- `body_metrics.date UNIQUE` → `UNIQUE(user_id, date)`
- `wellness_log.timestamp_ms UNIQUE` → `UNIQUE(user_id, timestamp_ms)`
- `clothing_options UNIQUE(category, value)` becomes per-user via
  Session 3's clothing_options redesign

SQLite can't easily change UNIQUE in place — table rebuild required.
Postgres can DROP CONSTRAINT + ADD. Plan to handle these in 2D
(or earlier if 2C's testing surfaces a real bite).

---

> The product is branded **AIDSTATION** (per Claude Design's brand handoff
> v0.1 + v0.2). The repo and the codebase still go by `exercise` / `AidStation`
> in places — that's fine, the customer-facing surface is what carries the
> rename.

---

## What The App Is

**AIDSTATION** — a personal training log / coach web app for an adventure
racer. Flask + SQLite (local) / Postgres (production-capable). No build step;
pure server-rendered Jinja2 + Bootstrap 5 with an AIDSTATION-branded CSS layer
on top. Deployed two ways: TrueNAS via Docker + Watchtower (`docker-compose.yml`)
and Vercel via `@vercel/python` (`vercel.json`).

Single-user today. Multi-user retrofit is the next major thrust — see the
**Multi-User Retrofit Roadmap** section near the bottom of this doc.

Key capabilities:
- Strength training log with per-set tracking, **performance-tracked baseline
  progression** (Family A 2× kicker, Family B baseline promotion), and
  injury awareness
- Cardio log (runs, bike, hike, paddle, swim, etc.)
- Natural-language log entry via Claude API — handles cardio, body metrics,
  and multi-exercise strength sessions (`/log-natural`)
- Training plan generation + review via Claude coaching system
- Plan item in-place editing for scheduled items
- **Garmin FIT file auto-match** to scheduled plan items (fuzzy date+sport
  scoring, four-option resolve UI when no match), with disposition tracking
  (completed / swapped_for / in_addition_to). Both manual FIT upload and
  bulk Garmin sync now support per-row swap/addition resolve.
- **Deload flag** at 5 sessions without PROGRESS per exercise
- Wellness chart view (`/garmin/wellness`)
- Garmin Connect sync (OAuth, activity pull)
- Conditions / clothing log, body metrics, injury log with per-exercise
  modifications, locale profiles

---

## Architecture

```
app.py              — Flask app; registers blueprints; runs DB init on startup
database.py         — get_db() helper; supports both SQLite row_factory and psycopg2
init_db.py          — SQLITE_SCHEMA, PG_SCHEMA, _SQLITE_MIGRATIONS, _PG_MIGRATIONS
                      Seeds exercises, equipment catalog, clothing options.
                      Migrations run on every cold start — must be idempotent.
calculations.py     — Pure progression rules: calculate_outcome_from_sets()
                      (returns outcome + exceeded_significantly + working values),
                      calculate_next_rx() (2× kicker on significance, REPEAT
                      resets failures), project_next_from_current() (manual
                      edits + FIT bootstrap), calculate_1rm(), calculate_volume().
rx_engine.py        — apply_session_outcome(): single source of truth for
                      writing a logged session into current_rx + training_log.
                      Implements baseline semantics, UPSERTs for first-time
                      exercises, bootstrap mode for target-less FIT imports,
                      sessions_since_progress / DELOAD_THRESHOLD plateau counter.
plan_match.py       — Auto-match logged activities to scheduled plan items.
                      sport_compatible(), score_match() (closeness in ±50%
                      window), find_best_match() (Tier 1 same-day → Tier 2
                      -3/+2 days), record_disposition() (completed | swapped_for),
                      candidate_plan_items() (nearby list for resolve dropdown).
coaching.py         — Claude API calls. Sport-adaptive system prompt
                      (_BASE_PROMPT + sport module). Anthropic prompt caching.
garmin_fit_parser.py — parse_fit() (activity), parse_wellness_fit(), _dump_fit()
garmin_connect.py   — Garmin Connect OAuth + activity fetch via garth library
fit_workout_generator.py — generate_activity_fit() → bytes (manual log FIT export)
routes/
  dashboard.py      — homepage (brand hero), weather (wttr.in), today's plan
  training.py       — /training, /training/new, /training/session (POST)
  cardio.py         — /cardio CRUD, FIT download per entry
  natural_log.py    — /log-natural NLP entry
  garmin.py         — /garmin/* (import FIT, sync, wellness, debug, auth).
                      import_preview shows auto-match banner when matched,
                      four-option resolve UI when not. sync_preview now has
                      per-row resolve UI matching the manual upload flow.
  coaching.py       — /coaching/* (generate, review, chat, preferences)
  plans.py          — /plans/* (list, import, detail, push to Garmin, PATCH /items/<id>)
  rx.py             — /rx (list + manual edit; manual edit re-derives next_*
                      via project_next_from_current; reset checkboxes for
                      consecutive_failures and sessions_since_progress)
  body.py, conditions.py, injuries.py, locales.py, references.py
templates/          — Jinja2 per blueprint
static/             — AIDSTATION brand system (style.css, logo/, favicon, og-preview)
```

---

## Database Tables

| Table | Purpose |
|---|---|
| `exercise_inventory` | Master exercise list with metadata |
| `current_rx` | Per-exercise prescribed baseline. **`current_*` is the baseline, not last performance.** Includes `consecutive_failures`, `sessions_since_progress`, `next_sets/reps/weight/duration`. |
| `training_sessions` | Groups sets from one workout session |
| `training_log` | Per-exercise entries (targets, actuals, outcome, RPE, next_*) |
| `training_log_sets` | Individual set rows for training_log entries |
| `cardio_log` | Cardio entries with full Garmin metrics |
| `body_metrics` | Weight, body fat, VO2max, resting HR |
| `conditions_log` | Weather + clothing per activity |
| `injury_log` | Active/resolved injuries |
| `injury_exercise_modifications` | Per-exercise overrides for an injury |
| `training_plans` | Claude-generated plans |
| `plan_items` | Individual scheduled workouts within a plan. `status` ∈ {`scheduled`, `completed`, `swapped`} |
| `plan_item_disposition` | Auto-match / swap audit trail. `(plan_item_id, log_type, log_id, disposition, reason)` where disposition ∈ {`completed`, `swapped_for`}. **`in_addition_to` does NOT create a row** — that path leaves the log standalone with `plan_item_id=NULL`. |
| `plan_reviews` | Tier 1/2/3 review records |
| `coaching_chat` | Per-plan conversation history |
| `coaching_preferences` | Persistent coach preferences. **Multi-user roadmap Session 0 will add `source_feedback_id` FK** linking each pref back to the originating `feedback_log` row. |
| `wellness_log` | Per-second Garmin wellness data |
| `garmin_auth` | Garmin Connect OAuth session |
| `garmin_workouts` | Garmin workout IDs pushed for scheduled plan items |
| `locale_profiles` | Home/hotel/travel equipment profiles. **Multi-user roadmap Session 3 changes PK to composite `(user_id, locale)`.** |
| `plan_travel` | Travel periods linked to a plan |
| `equipment_items` | Equipment catalog |
| `exercise_equipment` | Many-to-many exercise↔equipment with option groups |
| `locale_equipment` | Many-to-many locale↔equipment |
| `training_modalities` | Activity types with AR carryover ratings |
| `clothing_options` | Seeded clothing picklist values. **Multi-user roadmap Session 3 makes this per-user; new users start with an empty list.** |

**Tables dropped in Session 2A** (no live consumers, only referenced in
`init_db.py`):
- `equipment_matrix` — superseded by per-user `locale_equipment`
- `recommended_purchases` — minimal Andy-specific seed; rebuild parked
  as shared catalog + per-user wishlist layer

**Session 0 schema additions (landed in this branch):**
- `feedback_log(id, source, source_ref_id, raw_content, captured_at)` —
  verbatim feedback storage. Source values currently in use: `chat`,
  `plan_review`, `natural_log`, `workout_note_strength`,
  `workout_note_cardio`.
- `coaching_preferences.source_feedback_id` — FK back to `feedback_log(id)`,
  populated on every new pref so provenance is preserved.

---

## What Was Done This Session

### Workflow trigger cleanup (commit `969c2c6`)

Dropped the long-gone `claude/review-handoff-file-CDi71` branch from
`.github/workflows/docker-publish.yml`. The Docker image now publishes only
on pushes to `main`.

### Session 2A — Schema migrations + table drops

The skeleton for per-user scoping. No query sites changed; all `user_id`
columns are nullable and unread for now, so existing single-user
behaviour is preserved. Sessions 2B/2C wire the WHEREs and INSERTs;
2D adds NOT NULL after backfill is provably complete.

**Tables that gained `user_id INTEGER REFERENCES users(id)`:**

*Parent-scoped (13):* `training_sessions`, `training_log`, `current_rx`,
`cardio_log`, `body_metrics`, `conditions_log`, `injury_log`,
`training_plans`, `feedback_log`, `coaching_preferences`, `garmin_auth`,
`garmin_workouts`, `locale_profiles`, `wellness_log`.

*Denormalized children (4):* `training_log_sets` (parent: `training_log`),
`plan_items` (parent: `training_plans`), `plan_item_disposition`
(parent: `plan_items`), `coaching_chat` (parent: `training_plans`).

*Untouched (shared catalog or parent-JOIN scoped):*
`exercise_inventory`, `training_modalities`, `training_methods`,
`equipment_items`, `exercise_equipment`, `clothing_options`,
`plan_reviews`, `plan_travel`, `locale_equipment`,
`injury_exercise_modifications`.

**Tables dropped** (no live consumers, only referenced in `init_db.py`):
`equipment_matrix`, `recommended_purchases`. Removed from both
SQLITE_SCHEMA and PG_SCHEMA, plus `DROP TABLE IF EXISTS` migrations to
reclaim them on existing databases.

**Backfill strategy.** All UPDATEs are guarded so the migration is safe
to run before user 1 has registered (e.g., when 2A deploys ahead of the
first-run bootstrap):
- Parents: `UPDATE x SET user_id = 1 WHERE user_id IS NULL AND EXISTS
  (SELECT 1 FROM users WHERE id = 1)` — no-op pre-bootstrap, fires
  cleanly on the next cold start after registration.
- Denormalized children: pull from parent
  (`UPDATE child SET user_id = (SELECT user_id FROM parent ...)`).
  Safe before the parent is backfilled (sets NULL = NULL, harmless).
  Postgres uses the `UPDATE ... FROM ... WHERE` form for the same
  result.

**Composite indexes added** for the date-filtered hot paths:
`idx_tl_user_date`, `idx_cl_user_date`, `idx_bm_user_date`,
`idx_cond_user_date`, `idx_ts_user_date`, `idx_wl_user_date`,
`idx_pi_user_date`.

**Schema reorder.** `users` is now the FIRST table created in both
schemas so subsequent `REFERENCES users(id)` clauses resolve on fresh
installs.

**Verification covered.**
1. Fresh SQLite install — schema applies, every per-user table has
   `user_id`, dead tables absent, composite indexes present.
2. Simulated pre-2A upgrade — migrations on a manually-built old-shape
   DB drop the dead tables and backfill all 13 parents + 4 denormalized
   children to `user_id=1` from sample rows that started with NULL.
3. Pre-bootstrap upgrade — when no users exist yet, parent backfills
   are no-ops; running migrations again after user 1 registers
   completes the backfill cleanly.
4. App boot — all routes (`/`, `/training`, `/cardio`, `/body`, `/rx`,
   `/plans`) still return 200 after the migrations. Single-user flows
   continue to work because queries are still unscoped.

**Known follow-ups for 2B/2C/2D:**
- 2B: scope the 5 hot-spots (`dashboard.py:84`, `cardio.py:30`,
  `training.py:27`, `body.py:13`, `coaching.py:358`) plus
  `garmin_connect.py` singleton SELECT, and add `user_id` to every
  INSERT.
- 2C: systematic per-route scoping pass + `coaching.py` context
  gathering, `rx_engine.py`, `plan_match.py`.
- 2D: Postgres `ALTER COLUMN ... SET NOT NULL` after backfill;
  end-to-end second-user verification; open `ALLOW_REGISTRATION`.

**UNIQUE constraint debt** to handle alongside 2D (or earlier if
Andy's tooling needs it before then):
- `current_rx.exercise UNIQUE` should become `UNIQUE(user_id, exercise)`
- `body_metrics.date UNIQUE` should become `UNIQUE(user_id, date)`
- `wellness_log.timestamp_ms UNIQUE` should become
  `UNIQUE(user_id, timestamp_ms)`
- `clothing_options UNIQUE(category, value)` becomes per-user via
  Session 3's `clothing_options` redesign

**Fresh-install Postgres caveat.** PG_SCHEMA contains pre-existing
forward FK references (e.g., `training_sessions.plan_item_id REFERENCES
plan_items(id)` is declared before `plan_items` is created). This was
present before Session 2A and isn't something we introduced; verify a
fresh Neon install applies cleanly during 2D verification, ahead of
opening registration. If PG rejects it, the fix is reordering CREATEs
or dropping the inline FK in favour of an `ALTER TABLE ADD CONSTRAINT`
migration after both tables exist.

### Session 1 — auth foundation + lock the app

The app is now login-gated. Single-user assumption still holds — domain
queries are unscoped, registration is closed except for the first-user
bootstrap, and only Andy will have an account until Session 2 ships
per-user scoping.

**New table.** `users(id, username, email, password_hash, display_name,
created_at, last_login)` — both SQLITE_SCHEMA / PG_SCHEMA and both
migration lists.

**`requirements.txt`** gains `bcrypt>=4.1`.

**`routes/auth.py`** (new blueprint, prefix `/auth`):
- `/auth/login` GET/POST — bcrypt verify, sets `session['user_id']`,
  updates `last_login`, honours `?next=` (rejects non-relative URLs)
- `/auth/logout` GET/POST — clears session
- `/auth/register` GET/POST — gated by env var `ALLOW_REGISTRATION` in
  (`1`, `true`, `yes`, `on`); always open when zero users exist
  (first-run bootstrap); validates uniqueness, password length (≥ 8),
  password match
- Helpers: `current_user_id()`, `current_user(db)` for use in routes

**`app.py`**:
- Registers `auth_bp`
- `@app.before_request` gate: redirects unauthenticated GETs to
  `/auth/login?next=<path>`, returns 401 on unauth POST. Allowlist:
  `auth.login`, `auth.logout`, `auth.register`, anything ending in
  `.static`, and any path under `/static/`.
- `@app.context_processor` injects `current_user` into all templates
  so the nav can show the signed-in user.

**Templates:**
- `templates/auth/_shell.html` — minimal brand-only layout (no nav)
- `templates/auth/login.html`
- `templates/auth/register.html` — switches header to "First-run setup"
  when `is_bootstrap=True`

**`templates/base.html`** gets a right-aligned dropdown showing
`current_user.display_name` with a sign-out form button.

**Verification covered.** Test client confirmed: anonymous → login,
no-users → bootstrap register, register POST creates user and lands on
dashboard, logout clears session, second register without
`ALLOW_REGISTRATION` returns 403, bad-password renders form with error,
good-password redirects to `?next=` (with off-site URLs rejected),
`/static/*` reachable while logged out.

**Known caveats / follow-ups:**
- The `/coaching/api/*` headless endpoints are now also gated. They'll
  need either session-cookie auth (curl with `--cookie-jar` after a
  POST to `/auth/login`) or a token-auth shim. Out of scope for
  Session 1 — flagged as a follow-up.
- `garmin_connect.py` has a singleton `SELECT FROM garmin_auth LIMIT 1`
  pattern that's fine while there's only one user, but will need
  `WHERE user_id = ?` in Session 2.
- `/tmp/garth_session` file caching is process-shared; collision risk
  is accepted until the parked Garmin per-user OAuth work unblocks.

### Session 0 — coaching capture + context awareness

The full coaching memory + context awareness layer landed in this branch.

**New table.** `feedback_log(id, source, source_ref_id, raw_content,
captured_at)` plus `coaching_preferences.source_feedback_id` FK back to it.
Schema added to both `SQLITE_SCHEMA`/`PG_SCHEMA` (with `feedback_log` placed
ahead of `coaching_preferences` so the FK declaration resolves on fresh
Postgres installs) and to both migration lists for upgrades.

**New helpers in `coaching.py`** (around line 940 onward):
- `extract_preferences(raw_text, source) → list[{category, content, permanent}]`
  — Haiku-backed normalizer with a deliberately conservative prompt that
  skips performance commentary, weather notes, and one-off facts.
- `capture_feedback(db, source, raw_content, source_ref_id=None) → fb_id`
  — raw insert into `feedback_log`. No commit.
- `save_preferences_from_feedback(db, fb_id, prefs) → count`
  — writes prefs with `source_feedback_id` back-link. No commit.
- `capture_and_normalize_feedback(db, source, raw_content, source_ref_id=None)
  → (fb_id, saved_count)` — full pipeline.
- `get_wellness_summary(db, lookback_days=14) → dict` — daily aggregates
  from `wellness_log` (resting HR, stress, body battery, respiration,
  steps) plus 3-day vs prior-3-day deltas. Returns `{}` when no data.

**Hook sites** (all four feedback surfaces now flow through the pipeline):
1. `routes/coaching.py:chat` — user message captured into `feedback_log`,
   then chat-extracted prefs are written via
   `save_preferences_from_feedback` so each carries provenance back to the
   originating message. The chat call still does the smart extraction (it
   has full conversation context); only the storage path changed.
2. `routes/coaching.py:review` — review notes captured + normalized
   *before* the AI review call, so any extracted prefs are visible in the
   context the reviewer sees.
3. `routes/natural_log.py:save` — concatenated user-role messages from the
   parse session captured + normalized after entries are written. Client
   payload (`templates/natural_log/index.html`) was extended to include
   `history` on the save POST.
4. `routes/training.py:save_session` (session-level notes only) and
   `routes/cardio.py:_save` — workout notes captured under
   `workout_note_strength` / `workout_note_cardio` source values with
   `source_ref_id` pointing at the session/cardio_log row.

**`get_coaching_context()` extensions** (`coaching.py:272`):
- `current_rx` SELECT now exposes `sessions_since_progress`
- `deload_flags`: list of `{exercise, sessions_since_progress}` for any
  exercise at or above the threshold (≥ 5)
- `recent_plans` aggregate now also counts `swapped` plan items
- `recent_dispositions`: last-30-days `plan_item_disposition` rows
  joined to `plan_items` (planned date / workout / sport, plus the
  athlete's `reason` text)
- `wellness_summary`: read via `get_wellness_summary(db, lookback_days)`

**`_BASE_PROMPT` addition.** New "Athlete Signals" section at the bottom
of the base prompt tells Claude how to use `deload_flags`,
`recent_dispositions`, `wellness_summary`, and `coaching_preferences`.
Lives inside the prompt-cached system block so it costs nothing on warm
calls.

**Source values used.** `chat`, `plan_review`, `natural_log`,
`workout_note_strength`, `workout_note_cardio`. Session 4's coach-memory
UI will surface these as the provenance label on each pref row.

**Verification covered.** Schema applies cleanly to a fresh SQLite DB
(`feedback_log` and `coaching_preferences.source_feedback_id` present);
helpers round-trip with provenance; `get_coaching_context` returns the
new keys; app boots with all 13 blueprints registered. End-to-end Claude
extraction paths weren't exercised in this environment — there's no
`ANTHROPIC_API_KEY` available — but `extract_preferences` is defensive
about that (returns `[]` and the route flows continue normally).

### Plan-match window widened to -3 / +2 + dedupe (commit `b5ee4d2`)

`plan_match.find_best_match` Tier 2 offsets are now `(0, -1, 1, -2, 2, -3)`
and `candidate_plan_items` defaults are `days_back=3, days_forward=2`. The
auto-match window and the user-prompt candidate dropdown are unified so
the dropdown surfaces more options without diverging from what the matcher
considers.

`routes/garmin.py:import_preview` now excludes IDs already in the "Nearby"
optgroup from the wider "All scheduled" optgroup so a near-future plan item
no longer appears twice in the dropdown.

`templates/garmin/import_preview.html` got new banner labels for `-3` /
`+2` day offsets and an updated "Nearby (-3 to +2 days)" optgroup label.

### Per-row swap/addition resolve UI on Garmin sync preview (commit `239ec69`)

`templates/garmin/sync_preview.html`: each preview row now has a "Resolve"
toggle button that expands an inline panel with the four-option disposition
radio (standalone / completed / swapped_for / in_addition_to), a per-row
plan-item picker (per-row Nearby optgroup + deduped All scheduled
fallback), and a reason textarea. Defaults preserve the prior auto-match-
as-completed behavior, so rows the user doesn't touch import exactly as
before.

`routes/garmin.py`:
- `_import_activity` refactored to accept `disposition` /
  `raw_plan_item_id` / `reason` and route through the shared
  `_record_disposition_for_import` helper. When the user picks a plan item
  different from the auto-match, the chosen item is fetched so notes and
  compliance reflect the actual target.
- `sync_confirm` reads per-row form fields (`disposition_<gid>`,
  `plan_item_id_<gid>`, `swap_reason_<gid>`) and reports matched / swapped
  / added counts separately in the flash message.
- `_build_preview` adds per-row `nearby` candidates; the route passes a
  shared `all_scheduled` list. Per-row `nearby` is stripped from the
  Flask-session blob before storage to keep the cookie under the 4 KB
  limit.
- `api_sync` was left unchanged (uses defaults — same behavior as before).

### Multi-user retrofit roadmap planned

The big one: this session's product conversation produced a phased
multi-user retrofit plan with Andy's explicit decisions captured. Full
detail lives in the **Multi-User Retrofit Roadmap** section below.
Headline decisions:
- Storage: **Neon Postgres** in production (SQLite stays for local).
- **Five sessions, in order:** (0) coaching capture + context awareness,
  (1) auth foundation + lock the app, (2) per-user scoping + table drops,
  (3) clothing_options + locale_profiles shape changes, (4) athlete
  profile + coach memory UI.
- All Garmin per-user OAuth work is **parked** (blocked).
- New users start with **empty** clothing options (no seed copy).
- Child tables get **denormalized `user_id`** where they're queried
  directly by id (`plan_items`, `plan_item_disposition`, `coaching_chat`,
  `training_log_sets`); others stay parent-scoped.
- `equipment_matrix` and `recommended_purchases` get **dropped** in
  Session 2 (dead code today).
- Feedback gets a **normalization pipeline**: raw text into `feedback_log`,
  Claude pass turns it into clean `coaching_preferences` rows linked
  back to the source row for audit.

---

## Recent Prior Work (carry-forward summary)

For full detail on these, see commit messages.

- **Rx progression rewrite** (`7a7464f`) — `current_rx.current_*` is the
  prescribed baseline, not last performance. Family A 2× kicker, Family B
  baseline promotion, FIT bootstrap mode, single-source-of-truth
  `rx_engine.apply_session_outcome()`.
- **Deload flag at 5 plateau sessions** (`530d589`) —
  `current_rx.sessions_since_progress` counter, `deload` badge on `/rx`.
- **FIT auto-match + swap/addition resolve** (`829c83b`) — `plan_match.py`
  module, four-option resolve UI on import preview, `plan_item_disposition`
  table, `plan_items.status='swapped'` value.

---

## Key Patterns / Gotchas

### Auth + per-user scoping (Sessions 1 + 2A landed)

- Every non-`/auth/*` non-static route is gated by a global
  `before_request` hook in `app.py`. By the time a route handler runs,
  `flask_session['user_id']` is set.
- Use `from routes.auth import current_user_id` — returns `int | None`.
  `None` only happens pre-bootstrap or in tests; production routes can
  treat it as guaranteed-int.
- Templates have `current_user` available via context processor
  (`app.py:_inject_current_user`). The base nav uses it for the
  signed-in dropdown.
- Schema: every per-user table has a nullable `user_id INTEGER
  REFERENCES users(id)` column. **Backfill is done; query scoping
  isn't.** SELECTs still return all rows (single-user app, so this
  works); 2B/2C wire `WHERE user_id = ?`. INSERTs writing user_id
  start in 2B.
- The `coaching_chat` and `routes/coaching.py:chat` flow now routes
  user messages through `feedback_log` first; chat-extracted prefs
  carry `source_feedback_id` provenance back to the raw message.
- Andy's `current_rx` rows from before Session 0 had
  `rx_source='Needs initial setup'` for the seeded exercises (107
  rows). His real progress is in the FIT-bootstrapped or actively-used
  rows. Plan-only usage is the dominant pattern today (no manual
  strength/cardio logging).

### DB Access
```python
db = get_db()
row = db.execute('SELECT * FROM table WHERE id=?', (id,)).fetchone()
dict(row)  # row_factory gives sqlite3.Row (dict-like); access by column name
```
The codebase uses `?` placeholders everywhere — works for SQLite locally and
the Vercel deployment is also SQLite-shaped. Don't introduce `%s`. The
Postgres adapter (`database.py:_PgConn`) translates `?` → `%s` on the fly.

⚠ `cur.lastrowid` works on `sqlite3.Cursor` but the `_CompatCursor` PG
wrapper does a `fetchone()` against the cursor — it returns `None`
unless the INSERT used `RETURNING id`. Most existing INSERTs (including
`routes/auth.py:register`) don't have RETURNING, so they work on
current SQLite-backed production but will silently break when Neon
ships in 2D. Fix path: add `RETURNING id` to every INSERT that needs
the new id, or wrap the helper to detect dialect.

### Migrations
New columns/tables go in BOTH `_SQLITE_MIGRATIONS` and `_PG_MIGRATIONS`.
Migrations run on every cold start — must be idempotent (`IF NOT EXISTS`,
`ADD COLUMN IF NOT EXISTS` on Postgres; bare `ALTER TABLE ADD COLUMN` on
SQLite, which silently no-ops on duplicates because the migration runner
swallows exceptions).

### Rx engine
- `rx_engine.apply_session_outcome(db, exercise, date, sets, targets..., rx_source)`
  is the **only** way to write a session into `current_rx` + `training_log`.
  Don't reach into `current_rx` directly from new routes — go through the
  helper so semantics, UPSERT, and bootstrap mode stay consistent.
- `current_rx.current_*` values are the **prescribed baseline**. Don't
  read them as "what the user did last time." For the historical snapshot,
  query `training_log`.
- `next_*` is the prescription for the next session. Always projected from
  the (possibly Family-B-promoted) baseline — never stale after manual edits.
- For exercises that have a row in `exercise_inventory` but no `current_rx`,
  the helper UPSERTs from the inventory metadata and the FIT actuals.

### Plan matching
- `plan_match.find_best_match()` searches days `(0, -1, 1, -2, 2, -3)` in
  order; closer days win on ties. Returns `None` when no candidate scores
  ≥ 0.5; callers fall through to the user prompt. Don't lower the floor
  without thinking through what false-positive matches do to disposition.
- "In addition to" is **not** a disposition value. The disposition table
  tracks `completed` and `swapped_for` only. The user-facing radio includes
  "in addition to" as friendly framing, but the import handler routes that
  case to a standalone log with `plan_item_id=NULL` and writes no
  disposition row.
- Both manual FIT upload and Garmin sync now surface the four-option
  resolve UI per row. The disposition routing flows through
  `_record_disposition_for_import` in either path so semantics stay aligned.

### Brand system
- **CSS tokens** are in `static/style.css` `:root`. Colours in OKLCH; never
  hardcode brand colours in templates — use `var(--ink)`, `var(--orange)`, etc.
- **The logo IS the wordmark + mark.** Use the inline-SVG lockup pattern
  shown in `templates/base.html` and `templates/dashboard.html`.
- **Numerals** must render in JetBrains Mono with `tabular-nums`.
- **Voice rules**: real numbers, short declarative sentences, no decorative
  emoji, no exclamation marks. Functional icons (✓ / ✕) stay.
- **Reserve orange.** Signal colour only — CTAs, live state, alerts, PRs.

### fit_tool Library Units
- `total_elapsed_time` / `total_timer_time` — **seconds**
- `start_time` / `timestamp` on typed messages — **Unix milliseconds**
- `total_distance` — **meters**
- `avg_speed` — **m/s**

### Flask Session Size
Cookie-based session, 4 KB limit. Wellness FIT import sidesteps this by
spooling parsed rows to `/tmp/wellness_*.json` and storing only the path
in `flask_session['wellness_tmp']`. Garmin sync_preview strips per-row
`nearby` candidates from the session blob before storage. Use the same
patterns for any other large transient data flow.

### Anthropic API key plumbing
- Both `coaching.py` and `routes/natural_log.py` read
  `os.environ['ANTHROPIC_API_KEY']`. No fallback. Plan: stays shared key
  managed by app owner; BYOK per-user is parked.
- **Vercel:** set in Project → Settings → Environment Variables (Production
  scope). Vercel does NOT auto-redeploy on env-var changes — push a commit
  or hit "Redeploy" on the latest deployment.
- **TrueNAS / Docker Compose:** lives in `.env` next to `docker-compose.yml`
  on the host. Watchtower image updates do **not** reload `env_file` —
  after editing `.env`, run `docker compose up -d` from that directory to
  recreate the container with the new env baked in.

---

## Deployment

### Vercel (`vercel.json`)
Builds on every push to `main` via `@vercel/python`. All routes go through
`app.py`. Env vars come from Vercel's project settings. **Storage will
move to Neon Postgres** when Session 1 lands (set `DATABASE_URL` to the
Neon connection string; the app already supports Postgres via
`database.py`).

### TrueNAS via Docker + Watchtower (`docker-compose.yml`)
On every push to `main`, `.github/workflows/docker-publish.yml` builds and
publishes `ghcr.io/ahorn885/exercise:latest`. Watchtower polls every
300 s, pulls the new image, and recreates the `web` container.

### Branching workflow
- Feature branches: `claude/review-handoff-<id>` (the harness assigns one
  per session)
- Develop on the branch, push, merge to `main` with `--no-ff`
- `init_db.py` runs migrations on app startup — no manual step
- `git push origin main` is what triggers both deploys

---

## Pending / Open

### Carry-forward to-dos

**Deploy state confirmed at end of last session:**
- TrueNAS at `/mnt/storage/exercise/` running Docker compose with the
  merged `main`. `.env` has `SECRET_KEY` + `ANTHROPIC_API_KEY`. User 1
  bootstrapped. Session 2A backfill verified — all real rows scoped:
  `current_rx 107/107`, `training_plans 1/1`, `plan_items 28/28`,
  `body_metrics 1/1`, `injury_log 1/1`, `garmin_auth 1/1`. Empty
  tables (training_log, cardio_log, wellness_log, etc.) stay empty —
  not a problem, just where the user is in their logging today.
- Vercel running the merged `main`. User 1 bootstrapped. `SECRET_KEY`
  + `ANTHROPIC_API_KEY` already configured. **Known issue**: 500 on
  the post-register redirect (account got created — login on reload
  worked). Repro and root-cause as part of 2B; see "Open issue worth
  investigating" in the kickoff section above.

**Still pending:**
- **Investigate the Vercel post-register 500** (above). Vercel SQLite
  is `/tmp`-ephemeral so don't expect persistent data there until
  Neon ships in 2D.
- **Neon `DATABASE_URL`** — wire into Vercel and TrueNAS env before
  opening registration in Session 2D. Verify migrations run cleanly
  against a fresh Neon DB at that point (forward-FK caveat in the 2A
  notes — `training_sessions.plan_item_id REFERENCES plan_items(id)`
  is a forward ref in PG_SCHEMA, present before Session 2A; if PG
  rejects it, fix is reordering CREATEs or moving FKs to ALTER TABLE
  migrations).
- **`/coaching/api/*` headless endpoints are now login-gated.** If
  the remote-control flow is in use, either authenticate via session
  cookie (curl with `--cookie-jar` after a POST to `/auth/login`) or
  add a token-auth shim. Out of scope for 2B unless it's actively
  blocking something.

### Standalone ideas (no roadmap dependency)
- A multi-day wellness chart (7-day trend) would complement the per-day
  view at `/garmin/wellness`.
- Plan-item editing is currently per-item; a week-view bulk edit would be
  a natural follow-up.
- Auto-deload action button next to the `deload` badge — one click to
  drop weight 10% and reset the plateau counter, as a faster alternative
  to manually editing the Rx.

> Most prior follow-ups (coaching context awareness of dispositions,
> wellness → coaching rebuild, sync preview swap/addition UI, plan-item
> dropdown layering) were either shipped this session or folded into the
> Multi-User Retrofit Roadmap — see below.

---

## Multi-User Retrofit Roadmap

AIDSTATION is single-user today. Andy decided to make it multi-user — built
**properly now** so there are no leaky intermediate states where one user
can see another's data. Registration, MFA, passkeys, BYOK API keys, and
WebAuthn are explicitly parked for later sessions.

The retrofit spans 29 tables, ~150 query sites across 18 files, an
athlete-profile feature, a coach-memory UI, and a coaching capture +
context awareness layer. Too large for one session — split into the five
sessions below. Each session must land cleanly so the app is never sitting
in a half-scoped state where new accounts could leak data.

### Storage decision (lands with Session 1)

**Production becomes Neon Postgres.** SQLite on Vercel is ephemeral and
can't hold user accounts across cold starts. The codebase already supports
Postgres dual-mode via `database.py` (translates `?` → `%s`), so no code
rewrite — just point `DATABASE_URL` at Neon. Local dev keeps SQLite.

Verify migrations run cleanly against a fresh Neon DB before any user-id
work lands.

### Session 0 — Coaching capture + context awareness  ✅ shipped

Landed last session. See "What Was Done This Session — Session 0" above
for the full delta. The detailed scope below is preserved as historical
context for the design decisions.

**Why first:** the multi-user foundation is mechanical schema + scoping.
The coaching memory layer is product design — what gets captured, how it
surfaces — and Andy wants it solid as a single-user feature now so that
when multi-user lands, every query just gains a `user_id` filter and
everything still works. Doing it after multi-user means retrofitting
capture hooks into newly-scoped routes, more churn.

**Scope:**

1. **Extend preference auto-extraction beyond `/coaching/chat`.** Today
   `routes/coaching.py:508` runs a Claude call that returns a
   `preferences_to_save` array, written into `coaching_preferences`.
   Replicate that hook on:
   - `/coaching/review` (plan feedback)
   - `/log-natural` (natural-log entries)
   - Free-text notes on workout logging (training/cardio `notes`) — lighter
     pass, just scan for explicit preference signals
   Factor the extraction Claude-call shape into a reusable helper
   (`coaching.py:extract_preferences(text, context) → list[dict]`) before
   adding new call sites.

2. **Surface dispositions in `get_coaching_context()`.** Add to the dict:
   - Recent `plan_item_disposition` rows (last 30 days), joined to plan
     item + log, including `disposition`, `reason`, dates
   - `plan_items.status='swapped'` count in the `prior_plans` aggregate
     (today it counts `completed` and `skipped` only)
   - `current_rx.sessions_since_progress` per exercise + a deload flag
     list (exercises ≥ 5 plateau sessions)
   - Brief mention in `coaching.py:_BASE_PROMPT` so Claude is told to use
     these signals when reviewing/replanning

3. **Wellness → coaching context rebuild.** Per Andy's prior direction,
   design fresh rather than bolt onto `get_coaching_context()`. Likely
   shape: a new helper `get_wellness_summary(db, lookback_days=14)` that
   pulls from `wellness_log` and returns aggregates the coach can reason
   about (avg HR resting trend, body battery trend, stress trend, sleep
   if available). Wire into `get_coaching_context()` under
   `ctx['wellness_summary']` and surface in the prompt.

4. **Feedback log + normalization pipeline.** New `feedback_log` table
   captures every free-text feedback submission verbatim; a normalize
   pass turns it into clean, machine-actionable preference rows.

   Schema:
   ```
   feedback_log(
     id INTEGER PRIMARY KEY,
     source TEXT NOT NULL,          -- 'chat' | 'plan_review' | 'natural_log' | 'workout_note'
     source_ref_id INTEGER,         -- optional FK-ish to the originating row
     raw_content TEXT NOT NULL,
     captured_at TEXT DEFAULT (datetime('now'))
   )
   -- coaching_preferences gains a backlink so we can show provenance:
   ALTER TABLE coaching_preferences ADD COLUMN source_feedback_id INTEGER
     REFERENCES feedback_log(id);
   ```

   Workflow (one helper, one Claude call):
   1. Free-text enters via chat / review / natural-log / workout note
   2. Insert raw into `feedback_log` → get `fb_id`
   3. `normalize_feedback(raw_text, source) → list[{category, content, permanent}]`
      runs a Claude prompt that turns *"screw burpees never tell me to do
      them again"* into `{category: 'exercise_dislikes', content: 'Burpees
      excluded at user request', permanent: true}`. One feedback can
      produce multiple prefs.
   4. For each normalized item:
      `INSERT INTO coaching_preferences (category, content, permanent, source_feedback_id)
       VALUES (..., fb_id)`
   5. UI in Session 4 shows "Burpees excluded at user request — from chat
      on 2026-05-02 (view original)" so Andy can correct
      misinterpretations.

   Session 2 adds `user_id` to `feedback_log` and any new tables like
   every other per-user table.

**Out of scope this session:**
- Auth / multi-user / scoping (Sessions 1–2)
- Athlete profile (Session 4)
- Coach memory **UI** — capture/awareness is backend; UI lands in Session 4
  paired with the profile page

**Risks / mitigations:**
- *Risk:* preference extraction generates noise (Claude over-eager).
  *Mitigation:* tune prompt to be conservative; manual delete in
  Session 4's UI is the safety valve.
- *Risk:* wellness rebuild scope creep. *Mitigation:* commit to a
  read-only summary helper; don't redesign the wellness storage layer.

**Verification:** Andy gives feedback on a plan review, types preferences
into a natural-log, logs a workout with notes — confirm relevant prefs
land in `coaching_preferences` with source links. Generate a plan;
confirm the prompt context includes recent dispositions, deload flags,
and wellness summary. Existing flows (chat, generate, review) keep
working.

### Session 1 — Auth foundation + lock the app  ✅ shipped

Landed in `claude/review-handoff-doc-gNJdO`. See "What Was Done This
Session — Session 1" for the full delta. Headlines:
- `users` table on both schemas + migrations; `bcrypt` dep added
- `routes/auth.py` blueprint with login / logout / bootstrap-aware
  register
- Global `before_request` login gate in `app.py`; allowlist `/auth/*`
  and static
- Right-aligned signed-in user dropdown in `templates/base.html`

Carry-forward from this session:
- `/coaching/api/*` are gated — token-auth shim is a follow-up
- Open `ALLOW_REGISTRATION=1` only after Session 2 lands per-user
  scoping (the first additional user would otherwise see Andy's data)

### Session 2 — Per-user scoping + drop dead tables (the big one)

Split into 4 sub-sessions for tractability. **2A shipped** in this
branch (see "What Was Done This Session"); 2B/2C/2D remain.

#### Session 2A ✅ shipped — schema migrations + table drops

- All `user_id` columns added (NULLABLE for now); backfilled to user 1
- `equipment_matrix` and `recommended_purchases` dropped
- Composite `(user_id, date)` indexes added
- No query sites changed — single-user flows continue unmodified

#### Session 2B — query scoping, hot-spots first

- HANDOFF top-5 hot-spots: `dashboard.py:84`, `cardio.py:30`,
  `training.py:27`, `body.py:13`, `coaching.py:358`
- `garmin_connect.py` singleton `SELECT FROM garmin_auth LIMIT 1` →
  `WHERE user_id = ?`
- Add `user_id` to every INSERT so new rows are scoped from this point
  forward (denormalized children get user_id from `current_user_id()`
  too, not derived from parent)
- Settle the helper import path: `from routes.auth import current_user_id`

#### Session 2C — systematic per-route scoping

The remaining ~150 query sites across 18 files: `routes/*.py`
(13 files), `coaching.py`, `rx_engine.py`, `plan_match.py`,
`garmin_connect.py`. Every WHERE prefixes `user_id = ?`; multi-table
joins scope the parent only (children flow via FK unless they were
denormalized in 2A — those scope directly).

#### Session 2D — NOT NULL constraints + verification

- Postgres: `ALTER COLUMN user_id SET NOT NULL` on each table (run
  after all backfills are confirmed clean and all routes write user_id
  on INSERT)
- Composite UNIQUE constraints (debt list in 2A above)
- Create test user_id=2; verify empty dashboard/training/cardio/body/
  plans/coaching/Garmin/coach memory; log back in as Andy, confirm
  data intact
- Run schema migrations against a fresh Neon Postgres DB to verify
  forward-FK references (the caveat called out in 2A) — fix if needed
- Open `ALLOW_REGISTRATION`

**Tables gaining `user_id INTEGER NOT NULL REFERENCES users(id)`:**
`current_rx`, `training_sessions`, `training_log`, `cardio_log`,
`body_metrics`, `conditions_log`, `injury_log`, `training_plans`,
`coaching_preferences`, `feedback_log` (new from Session 0),
`wellness_log`, `garmin_auth`, `garmin_workouts`, `locale_profiles` (PK
becomes composite `(user_id, locale)`).

**Stay shared (catalog, no user_id):** `exercise_inventory`,
`equipment_items`, `exercise_equipment`, `training_modalities`,
`training_methods`.

**Tables to drop in this session** (dead, only referenced in `init_db.py`):
- `equipment_matrix` — superseded by per-user `locale_equipment`
- `recommended_purchases` — minimal Andy-specific; rebuild parked

**Child tables — denormalization decision:**
- **Denormalize `user_id`** (queried directly by id, leak risk on bare
  `SELECT * FROM x WHERE id = ?`): `plan_items`, `plan_item_disposition`,
  `coaching_chat`, `training_log_sets`
- **Parent-JOIN scope** (only read through their parent):
  `injury_exercise_modifications`, `plan_reviews`, `plan_travel`,
  `locale_equipment`
- **Strict junction stays shared:** `exercise_equipment`

**Migration approach (per table):**
1. Postgres: `ALTER TABLE x ADD COLUMN user_id INTEGER REFERENCES users(id)`
2. SQLite: `ALTER TABLE x ADD COLUMN user_id INTEGER`
3. Backfill: for parent tables `UPDATE x SET user_id = 1 WHERE user_id IS NULL`;
   for denormalized children, `UPDATE child SET user_id = (SELECT user_id
   FROM parent WHERE parent.id = child.parent_fk)`
4. Postgres: `ALTER TABLE x ALTER COLUMN user_id SET NOT NULL`
5. Composite index where queries filter by date:
   `CREATE INDEX IF NOT EXISTS idx_x_user_date ON x(user_id, date)`

**Query updates** touch `routes/*.py` (13 files), `coaching.py`,
`rx_engine.py`, `plan_match.py`, `garmin_connect.py`. Pattern: import
`current_user_id()`, prefix every WHERE with `user_id = ?` (or add it
for queries with no WHERE today). For multi-table joins, scope the
parent table only — children flow via FK *unless* they were denormalized,
in which case scope the child directly.

**Top 5 hot-spots to verify first** (unscoped queries that would leak data):
1. `routes/dashboard.py:84` — recent training log without WHERE
2. `routes/cardio.py:30` — `WHERE 1=1` defaults to all users
3. `routes/training.py:27` — same pattern
4. `routes/body.py:13` — body metrics list unscoped
5. `coaching.py:358` — body metrics in AI context unscoped

Also: `garmin_connect.py` singleton `SELECT FROM garmin_auth LIMIT 1` must
become `WHERE user_id = ?`. Note: `/tmp/garth_session` file caching is
process-shared; collision risk between simultaneous users is **accepted**
until the parked Garmin OAuth-per-user work unblocks.

**Verification:** create test user_id=2 via direct DB insert, log in,
confirm empty dashboard / training log / cardio / body metrics / plans /
coaching / Garmin / coach memory. Log back in as Andy, confirm everything
still there. Then open `ALLOW_REGISTRATION`.

### Session 3 — `clothing_options` per-user + `locale_profiles` cleanup

These two tables need shape changes beyond a simple `user_id` add.

**`clothing_options` redesign.** Today: one shared seeded list. Andy:
**values are per-user; only category names are universal. New users
start empty (no seed copy on registration)** — they accumulate as they
type into the conditions form. New shape:
```
clothing_options(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  category TEXT NOT NULL,
  value TEXT NOT NULL,
  UNIQUE(user_id, category, value)
)
```
Category list (`headwear`, `face_neck`, `upper_shell`, …) stays
hardcoded — already implied by `conditions_log` columns.
`_load_clothing_options()` in `routes/conditions.py` becomes
`SELECT category, value FROM clothing_options WHERE user_id = ?`.

**`locale_profiles` cleanup.** PK becomes composite `(user_id, locale)`.
`locale_equipment` child gets the extended FK. Routes in
`routes/locales.py` need scope updates.

**Verification:** test user_id=2 sees no clothing values until they enter
some; their entries don't bleed into Andy's; locales are independent
per user.

### Session 4 — Athlete profile + coach-memory UI

**`athlete_profile` table** (minimal placeholder — full field list
intentionally parked, will grow over time):
```
athlete_profile(
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  date_of_birth TEXT,
  sex TEXT,
  height_cm REAL,
  primary_sport TEXT,
  target_event_name TEXT,
  target_event_date TEXT,
  weekly_hours_target REAL,
  training_window TEXT,    -- 'morning' | 'midday' | 'evening' | 'flexible'
  notes TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
)
```

**New code:**
- `routes/profile.py` blueprint at `/profile`
- `templates/profile/edit.html` with three sections:
  1. **Profile** — form fields above
  2. **Coach memory** — list `coaching_preferences` with delete buttons
     + manual-add form. Each row shows provenance ("from chat on
     2026-05-02 — view original") linking back to its `feedback_log`
     source row. Pairs with the auto-capture work from Session 0.
  3. **Account** — display username, change-password form
- Helpers in `athlete.py`:
  - `get_athlete_profile(db, user_id) → dict`
  - `upsert_athlete_profile(db, user_id, **fields)`
- Read into `get_coaching_context()` (`coaching.py:272`) under
  `ctx['athlete_profile']`
- Mention in `_BASE_PROMPT` so Claude uses it for plan generation/review

**Verification:** Andy fills out profile, generates a plan, confirms the
coach prompt references his target event date / weekly hours; second
test user has empty profile, doesn't see Andy's data; coach memory list
shows auto-captured prefs from Session 0 plus manually added entries.

### Parked for later sessions (don't lose these)

- **All Garmin per-user OAuth work** — was a planned session; parked
  entirely per Andy. Includes `/tmp/garth_session` per-user-aware file
  caching, 401 refresh handling, and any `garmin_connect.py`
  shared-state cleanup. Blocked for now. The `garmin_auth` table itself
  still gains `user_id` in Session 2 so the row is scoped — but the
  file-caching collision risk is accepted until this unblocks.
- **MFA (TOTP)** — `pyotp` + setup flow on the profile page
- **Passkeys / WebAuthn** — Andy's preference; deferred because the
  WebAuthn flow is non-trivial (use the `webauthn` Python pkg)
- **BYOK Anthropic API key** — per-user override of the shared key in env
- **Password reset / email verification** — depends on email infra
- **Recommended purchases rebuild** — design and seed a robust shared
  reference catalog of equipment recommendations (cost, what it unlocks,
  exercises impacted, priority defaults), then add a per-user
  `user_purchase_recommendations(user_id, purchase_id, status, notes)`
  layer where `status` ∈ {wanted, owned, passed}. Worth its own session;
  catalog content design is the heaviest part.
- **Custom user-authored exercises** — would migrate `exercise_inventory`
  to `user_id NULL = system, NOT NULL = user-custom`. Not needed today.

### Reference: why each catalog table stays shared

| Table | Why shared | Migrate-to-per-user trigger |
|---|---|---|
| `exercise_inventory` | Taxonomic facts about exercises (muscles, movement pattern, recovery cost). Per-user data lives in `current_rx` / `training_log`. | User-authored custom exercises |
| `equipment_items` | Catalog nouns. User's ownership lives in `locale_equipment`. | (none expected) |
| `exercise_equipment` | Junction between two shared tables. | Custom exercises |
| `training_modalities` | Activity-type taxonomy with AR carryover. | (none expected) |
| `training_methods` | Reference content. | (none expected) |

**Removed from catalog (Session 2):** `equipment_matrix`, `recommended_purchases`.

### Reference: child table scoping map

| Child table | Parent | Scope | Session 2 treatment |
|---|---|---|---|
| `training_log_sets` | `training_log` | per-user | denormalize `user_id` |
| `injury_exercise_modifications` | `injury_log` | per-user | parent JOIN |
| `plan_items` | `training_plans` | per-user | denormalize `user_id` |
| `plan_item_disposition` | `plan_items` → `training_plans` | per-user | denormalize `user_id` |
| `plan_reviews` | `training_plans` | per-user | parent JOIN |
| `coaching_chat` | `training_plans` | per-user | denormalize `user_id` |
| `plan_travel` | `training_plans` | per-user | parent JOIN |
| `locale_equipment` | `locale_profiles` | per-user (S3) | parent JOIN (composite key) |
| `exercise_equipment` | shared catalog | shared | no change |

Denormalization rule: tables queried directly by id (e.g.,
`SELECT * FROM plan_items WHERE id = ?`) get their own `user_id` so the
scope check doesn't require a JOIN every time. Tables only ever read
through their parent stay parent-scoped.

### End-to-end verification (after all sessions)

1. Register two test users (A and B) via `/auth/register`.
2. As A, create a workout, log a cardio activity, sync a Garmin FIT,
   fill out profile, give plan-review feedback ("I hate burpees"),
   confirm the normalized pref shows up in coach memory.
3. Log out, log in as B. Confirm: empty dashboard, training log, cardio,
   body metrics, plans, coaching, Garmin status, profile, coach memory,
   feedback log, clothing options, locales, wellness summary.
4. As B, create separate data, generate a plan, confirm it uses B's
   profile + memory not A's.
5. Log back in as Andy (user_id=1), confirm all original data intact.
6. Run schema migrations against a fresh Neon Postgres DB; confirm clean.
7. Confirm cookie session size stays under 4 KB.
