# AIDSTATION — Session Handoff

**Date:** 2026-05-03
**Latest session branch:** `claude/review-handoff-ePQXO` (merging into `main` at end of session)

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

**Tables scheduled for drop in Session 2** (only referenced in `init_db.py`,
no live consumers):
- `equipment_matrix` — superseded by per-user `locale_equipment`
- `recommended_purchases` — minimal Andy-specific seed; rebuild parked as
  shared catalog + per-user wishlist layer

**New table arriving in Session 0:**
- `feedback_log(id, source, source_ref_id, raw_content, captured_at)` —
  verbatim feedback storage paired with a normalize pass that writes
  cleaned `coaching_preferences` rows.

---

## What Was Done This Session

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

### DB Access
```python
db = get_db()
row = db.execute('SELECT * FROM table WHERE id=?', (id,)).fetchone()
dict(row)  # row_factory gives sqlite3.Row (dict-like); access by column name
```
The codebase uses `?` placeholders everywhere — works for SQLite locally and
the Vercel deployment is also SQLite-shaped. Don't introduce `%s`. The
Postgres adapter (`database.py:_PgConn`) translates `?` → `%s` on the fly.

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
- **TrueNAS `.env`** — needs `ANTHROPIC_API_KEY` and `SECRET_KEY` set, then
  run `docker compose up -d` from that directory to recreate the container.
  Watchtower won't reload `.env` on its own. Vercel side is already done.
- **Stale workflow trigger** — `.github/workflows/docker-publish.yml` still
  triggers on a long-gone branch (`claude/review-handoff-file-CDi71`).
  Should be `branches: [main]` only. One-line cleanup, ship anytime.
- **Neon `DATABASE_URL`** — to be wired into Vercel and TrueNAS env at the
  start of Session 1.

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

### Session 0 — Coaching capture + context awareness

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

### Session 1 — Auth foundation + lock the app

**Goal:** add auth + login gate. App still has unscoped queries, but
registration is closed and only Andy has an account, so the single-user
assumption holds.

**Deliverables:**
- `users(id, username, email, password_hash, display_name, created_at,
  last_login)` — both SQLite + Postgres migrations
- `routes/auth.py` blueprint: `/auth/login`, `/auth/logout`,
  `/auth/register` (registration gated by env-var `ALLOW_REGISTRATION`
  until Session 2 ships)
- `templates/auth/login.html`, `templates/auth/register.html`
- `current_user_id()` helper, `@login_required` decorator (or
  `before_request` hook checking `flask_session['user_id']`)
- One-time bootstrap: when no users exist, prompt to create the first one
  (Andy) on first request
- Apply login gate globally in `app.py` (allowlist `/auth/*` and static)
- Add `bcrypt` to `requirements.txt`

**Out of scope:** user_id columns on domain tables, query scoping,
profile UI.

**Verification:** Andy can register/log in; logged-out requests redirect
to `/auth/login`; existing routes still render his data when logged in;
register without `ALLOW_REGISTRATION=1` returns 403.

### Session 2 — Per-user scoping + drop dead tables (the big one)

**Goal:** add `user_id` to every per-user table, backfill existing rows
to user_id=1, update every query to scope by current user. Drop
`equipment_matrix` and `recommended_purchases`. Open registration after
this lands.

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
