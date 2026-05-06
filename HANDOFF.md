# AIDSTATION — Session Handoff

**Date:** 2026-05-06
**Last commit on `main`:** `9409d0d` — nav UX fix (Gear dropdown +
defensive toggler/overflow rules). Stacked on top of `8af8d29`
(auth-gate hardening), `2c2f312` (merge of the Neon de-risking +
purchases rebuild branch), and `32e8c38` (Sessions 0–4 multi-user
retrofit).

**Deploy state:**
- ✅ Vercel: `9409d0d` live at `https://aidstation-pro.vercel.app`,
  backed by Neon Postgres (`DATABASE_URL` wired during this session).
  Andy is bootstrapped (user 1) and using it in production.
- ✅ TrueNAS: GitHub Actions builds + Watchtower auto-pulls on every
  push to `main`. Should be on `9409d0d` within ~5 min of the latest
  push; verify with `docker images ghcr.io/ahorn885/exercise:latest
  --format '{{.CreatedAt}}'` if anything looks off.

The multi-user retrofit is fully shipped end-to-end. The Neon
cutover happened this session and resolved both carry-forward
warnings from the prior handoff (forward-FK + `RETURNING id`).
Single-user in practice today — operator just hasn't flipped
`ALLOW_REGISTRATION` yet.

---

## Next session — what's left for the operator

Most of the prior walkthrough's steps are done. Remaining:

### Step A — open registration (when ready for a second user)

Set `ALLOW_REGISTRATION=1` on **both** environments:

- **Vercel:** Project Settings → Environment Variables. Then click
  "Redeploy" on the latest production deployment (env-var changes
  don't auto-trigger a build).
- **TrueNAS:** edit `/mnt/storage/exercise/.env`, add
  `ALLOW_REGISTRATION=1`, then `cd /mnt/storage/exercise && docker
  compose up -d` to recreate the container with the new env
  baked in. (Watchtower image pulls do NOT reload `env_file`.)

### Step B — second-user smoke test

Register a second account from a private window or a different
machine. Pick a username unlike "andy" (e.g. `test`). Walk through:

- Dashboard, /training, /cardio, /body, /rx, /plans/, /injuries,
  /conditions, /garmin/, /log-natural/, **/locales** (under Gear),
  **/purchases** (under Gear), /profile/ — all should be empty /
  placeholder for the new user.
- Log a strength session against `Back Squat`. Confirm it goes into
  the new user's `current_rx`, not Andy's.
- Save a `home` locale with some equipment. Andy's home setup
  should be untouched.
- Mark a couple of `/purchases` items wanted/owned. Confirm Andy
  still sees his own statuses unchanged.
- Add a clothing value via `/conditions/new` — confirm Andy's
  conditions form doesn't show it.
- Generate a small plan via `/coaching/generate` (or import a JSON
  via `/plans/import`). Confirm Andy doesn't see it on his
  `/plans/`.

If all pass, log out, log in as Andy, do a final pass to confirm
his data is intact and he doesn't see the test user's stuff.

### Step C — clean up

- Delete the test user via direct DB query if you want a clean
  state, or leave it as a sanity safety net. (No UI for user
  deletion — would require an admin page.)
- If you opened registration just for the smoke test and want to
  re-close it, set `ALLOW_REGISTRATION=0` (or just unset). Existing
  users can still log in.

After Step B passes, multi-user is verified live in production.

---

## Carry-forward issues to watch

Both prior carry-forwards (`RETURNING id` and forward-FK) are
resolved on `main`. Things to keep in mind going forward:

1. **`RETURNING id` is the pattern.** Every existing INSERT whose
   new id is read back uses it, and the `_CompatCursor.lastrowid`
   wrapper already does `fetchone()` to surface it on Postgres.
   SQLite's native `lastrowid` ignores the unread RETURNING row.
   For new INSERTs: add `RETURNING id` to the SQL and `cur.lastrowid`
   reads work on both backends unchanged.

2. **Auth gate hydrates the user row.** `app.py:_require_login` does
   one `users` SELECT per authenticated request and stashes the row
   on `g.current_user_row`; the context processor reads from there
   instead of re-querying. If hydration fails (stale cookie, user
   deleted, DB error), the session is cleared and the request is
   bounced — no more "ghost user" admitted with no logout button.
   Hydration errors `print()` to stdout (visible in Vercel logs) so
   any failure surfaces instead of being silently swallowed.

3. **`/coaching/api/*` endpoints are login-gated.** External tooling
   (Claude Desktop, scripts) needs session-cookie auth (curl with
   `--cookie-jar` after a `/auth/login` POST) or a token-auth shim.
   Out of scope; flagged.

4. **Brand CSS overrides Bootstrap aggressively.** `.navbar` is
   forced to `var(--ink) !important`, `--bs-navbar-toggler-icon-bg`
   is set explicitly to a white-stroke SVG, and `body` clips
   `overflow-x` to defend against horizontal overflow trapping the
   user dropdown / toggler off-canvas. If you add navbar items, keep
   an eye on the total intrinsic width at ≥992px viewports — the
   `Gear` dropdown was added this session specifically to keep the
   top bar fitting after `Purchases` pushed it over the edge.

---

## What's next on the code side

Backlog in priority order (independent of the operator steps above):

1. **Multi-day wellness chart** on `/garmin/wellness` — 7-day
   trend complementing the per-day view. Smallest standalone
   left, ~2 hours. Last unfinished item from the original plan.
2. **Purchases catalog curation.** The seeded
   `PURCHASE_RECOMMENDATIONS` list in `init_db.py` is a starter
   (~18 items, AR-leaning). Cost ranges, copy, and priorities are
   easy to tune as you use the page; UPSERT-on-slug means edits
   propagate to existing rows on the next cold start without
   disturbing per-user state. New items just append to the list.
3. **`coaching.py:capture_and_normalize_feedback` payload size** —
   the Haiku call sends raw_content; if chat history grows long,
   prompt cost rises linearly. Worth profiling once there's real
   second-user data.

The full backlog (parked items, future ideas) is in the Backlog
section near the bottom.

---

## What shipped this session (on top of `32e8c38`)

Four commits on `main`, in order:

**`504445c` — Pre-empt Neon cutover.**
- `PG_SCHEMA` reordered: `training_plans` + `plan_items` precede
  `training_sessions` / `training_log` / `cardio_log`, so every
  forward FK resolves at CREATE TABLE time on Neon. SQLite-side
  `CREATE TABLE IF NOT EXISTS` makes it a no-op on existing DBs.
- `RETURNING id` sweep across 15 INSERT sites in `coaching.py` +
  `routes/{auth,cardio,garmin,natural_log,plans,training}.py`.

**`541207b` — Recommended-purchases rebuild.**
- `purchase_recommendations` (shared catalog, `slug` UNIQUE for
  UPSERT-on-cold-start re-seed; `equipment_id` FK to
  `equipment_items`) + `user_purchase_recommendations(user_id,
  purchase_id)` PK, status ∈ {wanted, owned, passed}.
- 18 seeded items targeting AR/endurance gear gaps (adjustable DBs,
  pull-up bar, KB, bands, foam roller, weighted vest, sandbag,
  hangboard, etc.).
- `/purchases` list (grouped by priority, locale-tag hint when the
  equipment is already in any of the user's locales, impacted-count
  via `exercise_equipment` join) + `/purchases/<id>` detail
  (live-derived "exercises this unlocks") + `POST .../status`
  cross-user-defended UPSERT.

**`8af8d29` — Auth gate hardening.**
- Closes a back-door surfaced during Neon cutover: a session cookie
  pointing at a nonexistent users row was silently admitted as a
  "ghost user" whose templates rendered with `current_user=None`,
  hiding the only logout button.
- Hydrate the row once per request in `_require_login`, stash on
  `g.current_user_row`. Stale cookies → `session.clear()` + bounce.
  Hydration failures `print()` to logs instead of being swallowed.
- Net side benefit: every auth'd request does one `users` SELECT
  total instead of two.

**`9409d0d` — Nav UX fix.**
- 11 top-level nav items overflowed the navbar at typical desktop
  widths after `Purchases` was added; the user dropdown / toggler
  ended up past the right edge of the navbar's dark background,
  against the white body bg, with the toggler's white icon
  invisible.
- Consolidated `Locales` + `Purchases` under a single `Gear`
  dropdown.
- Defensive CSS: `flex-wrap: wrap` on `.navbar > .container-fluid`,
  `body { overflow-x: hidden }`, explicit white-stroke
  `--bs-navbar-toggler-icon-bg` SVG (Bootstrap 5.3 deprecated
  `.navbar-dark`), `margin-left: auto` on the toggler.

---

## What's currently live

**Multi-user retrofit (Sessions 0–4):**
- Session 0 — coaching-feedback capture pipeline (`feedback_log` +
  `coaching_preferences.source_feedback_id`); chat / plan-review /
  natural-log / workout-note hooks; `get_coaching_context()`
  surfaces `deload_flags`, `recent_dispositions`, `wellness_summary`.
- Session 1 — auth foundation: `users` table, `routes/auth.py`,
  `before_request` login gate, bootstrap-aware register page,
  bcrypt password hashing.
- Session 2A — schema migrations: `user_id` columns on every
  per-user table (NULLABLE), backfill UPDATEs for user 1, dead
  tables dropped (`equipment_matrix`, `recommended_purchases`),
  composite `(user_id, date)` indexes for hot queries.
- Session 2B — INSERT pass: every write path threads `user_id`;
  hot-spot SELECTs scoped (5 highest-traffic queries +
  `garmin_auth` singleton); engine helpers gain `user_id=None`
  parameters so callers can thread it through.
- Session 2C — systematic per-route scoping: every remaining
  SELECT/UPDATE/DELETE in `routes/*.py` + the engine helpers
  (`coaching.py`, `rx_engine.py`, `plan_match.py`) is `user_id`
  scoped; fetch-by-id handlers gained `AND user_id = ?` so a
  crafted URL can't read or destroy another user's row; missed
  INSERTs from 2B (`wellness_log`, `garmin_workouts`) fixed.
- Session 2D — schema stabilization: composite UNIQUEs on
  `current_rx (user_id, exercise)`, `body_metrics (user_id, date)`,
  `wellness_log (user_id, timestamp_ms)`. Postgres `SET NOT NULL`
  on `user_id` for 18 tables. Per-user `current_rx` seed flow:
  `_seed_current_rx_for_user` invoked inline from `auth.register`
  so a new user's `/rx` populates immediately.
- Session 3 — clothing & locales per-user: `clothing_options`
  becomes `UNIQUE(user_id, category, value)`; the global
  `_CLOTHING_SEEDS` list is dropped (values accumulate from user
  input). `locale_profiles` PK becomes composite `(user_id,
  locale)`; `locale_equipment` gains denormalized `user_id` with
  composite FK. Two users can each own a "home" / "hotel" locale.
- Session 4 — athlete profile + coach memory UI: new
  `athlete_profile` table; `/profile` page with three tabs
  (Athlete / Coach memory / Account). Coach memory shows
  preferences with provenance ("Captured from chat on 2026-04-30 ·
  view original" or "Added manually"). Manual-add + delete on
  preferences. Change-password flow. `get_coaching_context` adds
  `ctx['athlete_profile']`; `_BASE_PROMPT` documents how Claude
  should use it.

**Standalone improvements (in the original `32e8c38` batch):**
- Plan-match window widened to -3 / +2 days with deduped resolve
  dropdowns.
- Per-row swap/addition resolve UI on Garmin sync preview.
- One-click deload button on `/rx` flagged rows — drops the primary
  progression dimension 10%, re-projects `next_*`, resets both
  plateau and failure counters; bodyweight exercises drop reps
  instead. Banner appears whenever any row crosses the
  `DELOAD_THRESHOLD`.
- Bulk plan-item editor on `/plans/<id>`: toggle "Bulk edit",
  select scheduled items via checkboxes, apply one of four
  actions in a floating action bar — `shift_date` (±N days),
  `intensity_step` (raise/drop one notch), `duration_scale`
  (multipliers 0.7 / 0.85 / 1.15 / 1.3), `mark_skipped`. For
  strength items, `duration_scale` appends a `[Load scaled to N%
  — adjust weights]` note instead of touching the clock; idempotent
  (re-runs replace, don't stack).

### Verification harnesses

Disposable scripts under `/tmp/verify_*.py` (recreate as needed
from git history). Last sweep: all green.

| Harness | Coverage |
|---|---|
| `verify_2c.py` | 2nd-user data isolation across 9 hot routes + `/coaching/context` |
| `verify_2d.py` | UNIQUE migration on populated DB; user 2 logs seeded exercise; both users on same date |
| `verify_3.py` | Pre-3 DB upgrade preserves Andy's data; per-user clothing + locale isolation |
| `verify_4.py` | Profile round-trip; coach memory provenance; `/feedback/<id>` view; cross-user defenses; password change |
| `verify_deload.py` | Deload math; counter resets; cross-user POST defense; bodyweight fallback |
| `verify_bulk.py` | All 4 bulk actions; cross-user + cross-plan defenses |
| `verify_strength_load.py` | Strength load-note: idempotent replacement, "increase"/"reduce" wording, mult=1.0 no-op |

---

## What The App Is

**AIDSTATION** — a personal training log / coach web app for an
adventure racer, scoped to be multi-user since this batch. Flask +
SQLite (local) / Postgres (Neon-targeted production). No build step;
pure server-rendered Jinja2 + Bootstrap 5 with an AIDSTATION-branded
CSS layer. Deployed two ways: TrueNAS via Docker + Watchtower
(`docker-compose.yml`) and Vercel via `@vercel/python`
(`vercel.json`).

Key capabilities:
- Strength training log with per-set tracking, performance-tracked
  baseline progression (Family A 2× kicker, Family B baseline
  promotion), and injury awareness
- Cardio log (runs, bike, hike, paddle, swim, etc.)
- Natural-language log entry via Claude API — handles cardio, body
  metrics, and multi-exercise strength sessions (`/log-natural`)
- Training plan generation + review via Claude coaching system
- Plan item in-place editing for scheduled items + bulk-edit floating
  action bar
- Garmin FIT file auto-match to scheduled plan items (fuzzy date+sport
  scoring, four-option resolve UI when no match), with disposition
  tracking. Both manual FIT upload and bulk Garmin sync support
  per-row swap/addition resolve.
- Deload flag at 5 sessions without PROGRESS per exercise + one-click
  deload action
- Wellness chart view (`/garmin/wellness`)
- Garmin Connect sync (OAuth, activity pull) — single shared OAuth
  token; per-user OAuth is parked
- Conditions / clothing log, body metrics, injury log with per-exercise
  modifications, locale profiles
- Athlete profile + coach memory UI on `/profile`

---

## Architecture

```
app.py              — Flask app; registers blueprints; runs DB init on startup
database.py         — get_db() helper; supports both SQLite row_factory and psycopg2
init_db.py          — SQLITE_SCHEMA, PG_SCHEMA, _SQLITE_MIGRATIONS, _PG_MIGRATIONS.
                      Migrations run on every cold start — must be idempotent.
                      Callable migrations supported (Session 2D rebuilds).
                      _seed_current_rx_for_user is called from auth.register on
                      every successful registration.
calculations.py     — Pure progression rules: calculate_outcome_from_sets(),
                      calculate_next_rx() (2× kicker on significance, REPEAT
                      resets failures), project_next_from_current() (manual
                      edits + FIT bootstrap), compute_deload_baseline() (Session 2C
                      deload helper), calculate_1rm(), calculate_volume().
rx_engine.py        — apply_session_outcome(): single source of truth for writing
                      a logged session into current_rx + training_log. Implements
                      baseline semantics, UPSERTs scoped on (user_id, exercise),
                      bootstrap mode for target-less FIT imports,
                      sessions_since_progress / DELOAD_THRESHOLD plateau counter.
plan_match.py       — Auto-match logged activities to scheduled plan items.
                      sport_compatible(), score_match(), find_best_match()
                      (Tier 1 same-day → Tier 2 -3/+2 days), record_disposition(),
                      candidate_plan_items(). All scoped by user_id (resolved
                      from current_user_id() if not passed explicitly).
coaching.py         — Claude API calls. Sport-adaptive system prompt
                      (_BASE_PROMPT + sport module). Anthropic prompt caching.
                      get_coaching_context() surfaces athlete_profile,
                      coaching_preferences, deload_flags, recent_dispositions,
                      wellness_summary, all scoped to current user.
athlete.py          — get_athlete_profile / upsert_athlete_profile helpers
                      backed by a PROFILE_FIELDS allowlist.
garmin_fit_parser.py — parse_fit() (activity), parse_wellness_fit(), _dump_fit()
garmin_connect.py   — Garmin Connect OAuth + activity fetch via garth library.
                      garmin_auth singleton SELECTs all scoped by user_id; the
                      /tmp/garth_session file caching is process-shared (parked).
fit_workout_generator.py — generate_activity_fit() → bytes (manual log FIT export)
routes/
  dashboard.py      — homepage (brand hero), weather (wttr.in), today's plan
  training.py       — /training, /training/new, /training/session (POST)
  cardio.py         — /cardio CRUD, FIT download per entry
  natural_log.py    — /log-natural NLP entry
  garmin.py         — /garmin/* (import FIT, sync, wellness, debug, auth)
  coaching.py       — /coaching/* (generate, review, chat, preferences)
  plans.py          — /plans/* (list, import, detail, push to Garmin,
                      PATCH /items/<id>, POST /<plan>/items/bulk for the
                      Session 2C bulk editor)
  rx.py             — /rx (list + manual edit + POST /<id>/deload)
  body.py, conditions.py, injuries.py, locales.py, references.py
  profile.py        — /profile/ (Session 4): edit + preference add/delete +
                      feedback/<id> view + change password
  purchases.py      — /purchases (list, grouped by priority) + /<id> detail
                      (live exercises-unlocked join) + POST /<id>/status.
                      Shared catalog seeded via _seed_purchase_recommendations.
  auth.py           — /auth/login, /auth/logout, /auth/register
templates/          — Jinja2 per blueprint
static/             — AIDSTATION brand system (style.css, logo/, favicon, og-preview)
```

---

## Database Tables

| Table | Purpose |
|---|---|
| `users` | Auth: id, username, email, password_hash, display_name, created_at, last_login. Bcrypt hashes. |
| `athlete_profile` | Per-user `(user_id PK)`: DOB, sex, height_cm, primary_sport, target_event_name, target_event_date, weekly_hours_target, training_window, notes. Surfaced in coaching context. |
| `exercise_inventory` | Master exercise list with metadata. **Shared catalog.** |
| `current_rx` | Per-exercise prescribed baseline. **`current_*` is the baseline, not last performance.** Includes `consecutive_failures`, `sessions_since_progress`, `next_*`. `UNIQUE(user_id, exercise)`. |
| `training_sessions` | Groups sets from one workout session |
| `training_log` | Per-exercise entries (targets, actuals, outcome, RPE, next_*) |
| `training_log_sets` | Individual set rows for training_log entries (denormalized `user_id`) |
| `cardio_log` | Cardio entries with full Garmin metrics |
| `body_metrics` | Weight, body fat, VO2max, resting HR. `UNIQUE(user_id, date)`. |
| `conditions_log` | Weather + clothing per activity |
| `injury_log` | Active/resolved injuries |
| `injury_exercise_modifications` | Per-exercise overrides for an injury (parent-JOIN scoped via `injury_log`) |
| `training_plans` | Claude-generated plans |
| `plan_items` | Individual scheduled workouts within a plan. `status` ∈ {`scheduled`, `completed`, `skipped`, `swapped`}. Denormalized `user_id`. |
| `plan_item_disposition` | Auto-match / swap audit trail. `(plan_item_id, log_type, log_id, disposition, reason)` where disposition ∈ {`completed`, `swapped_for`}. **`in_addition_to` does NOT create a row** — that path leaves the log standalone with `plan_item_id=NULL`. Denormalized `user_id`. |
| `plan_reviews` | Tier 1/2/3 review records (parent-JOIN scoped) |
| `plan_travel` | Travel periods linked to a plan (parent-JOIN scoped) |
| `coaching_chat` | Per-plan conversation history (denormalized `user_id`) |
| `coaching_preferences` | Persistent coach preferences. `source_feedback_id` FK back to `feedback_log` for provenance. |
| `feedback_log` | Verbatim feedback storage. Source values: `chat`, `plan_review`, `natural_log`, `workout_note_strength`, `workout_note_cardio`. |
| `wellness_log` | Per-second Garmin wellness data. `UNIQUE(user_id, timestamp_ms)`. |
| `garmin_auth` | Garmin Connect OAuth session (scoped per-user — but file caching at `/tmp/garth_session` is process-shared, see Parked) |
| `garmin_workouts` | Garmin workout IDs pushed for scheduled plan items |
| `locale_profiles` | Home/hotel/travel/airport equipment profiles. **PK is composite `(user_id, locale)`.** |
| `locale_equipment` | Many-to-many locale↔equipment. `(user_id, locale, equipment_id)` PK + composite FK to `locale_profiles`. |
| `equipment_items` | Equipment catalog. **Shared.** |
| `exercise_equipment` | Many-to-many exercise↔equipment with option groups. **Shared junction (between two shared tables).** |
| `training_modalities` | Activity types with AR carryover ratings. **Shared catalog.** |
| `clothing_options` | Per-user clothing values (`UNIQUE(user_id, category, value)`). New users start empty; values accumulate as they type into the conditions form. |
| `purchase_recommendations` | Shared catalog of recommended gear purchases. **`slug` UNIQUE** for idempotent UPSERT re-seed. `equipment_id` FK to `equipment_items` lets "exercises this unlocks" be derived live via `exercise_equipment`. Seeded by `_seed_purchase_recommendations` on every cold start. |
| `user_purchase_recommendations` | Per-user state on each recommendation. PK `(user_id, purchase_id)`. `status` ∈ {`wanted`, `owned`, `passed`}; clearing the status deletes the row. |

**Tables dropped during the retrofit** (no live consumers):
`equipment_matrix`, `recommended_purchases` (the latter has since been
rebuilt as `purchase_recommendations` + `user_purchase_recommendations`,
described above).

**Reference: child table scoping decisions.** Tables queried by id
get a denormalized `user_id` so the scope check doesn't require a
JOIN every time. Tables only ever read through their parent stay
parent-scoped.

| Child table | Parent | Scope decision |
|---|---|---|
| `training_log_sets` | `training_log` | denormalized `user_id` |
| `injury_exercise_modifications` | `injury_log` | parent-JOIN |
| `plan_items` | `training_plans` | denormalized `user_id` |
| `plan_item_disposition` | `plan_items` | denormalized `user_id` |
| `plan_reviews` | `training_plans` | parent-JOIN |
| `coaching_chat` | `training_plans` | denormalized `user_id` |
| `plan_travel` | `training_plans` | parent-JOIN |
| `locale_equipment` | `locale_profiles` | denormalized `user_id` (composite key) |
| `exercise_equipment` | shared catalog | shared, no scope |

---

## Key Patterns / Gotchas

### Auth + per-user scoping

- Every non-`/auth/*` non-static route is gated by a global
  `before_request` hook in `app.py`. The gate hydrates the
  user row from `users` and stashes it on `g.current_user_row`;
  if the row doesn't exist (stale cookie pointing at a deleted /
  not-yet-existent user), the session is cleared and the request
  is bounced. By the time a route handler runs, both
  `flask_session['user_id']` and `g.current_user_row` are valid.
- Use `from routes.auth import current_user_id` — returns
  `int | None`. `None` only happens pre-bootstrap or in tests.
- Templates have `current_user` available via context processor
  (`app.py:_inject_current_user`); it reads from `g.current_user_row`
  so it does not double-query. The base nav uses it for the
  signed-in dropdown.
- Schema: every per-user table has a `user_id` column. Postgres
  enforces `NOT NULL`; SQLite is NULLABLE because the rebuild cost
  isn't worth it given the runtime defenses (every write path
  threads `user_id`, every read path scopes on it).
- The `coaching_chat` and `routes/coaching.py:chat` flow routes
  user messages through `feedback_log` first; chat-extracted prefs
  carry `source_feedback_id` provenance back to the raw message.
  Surfaced on `/profile` with a "view original" link.

### DB Access

```python
db = get_db()
row = db.execute('SELECT * FROM table WHERE id=?', (id,)).fetchone()
dict(row)  # row_factory gives sqlite3.Row (dict-like); access by column name
```

The codebase uses `?` placeholders everywhere — works for SQLite
locally and for the Postgres adapter (`database.py:_PgConn`)
translates `?` → `%s` on the fly. Don't introduce `%s` directly.

⚠ `cur.lastrowid` works on `sqlite3.Cursor` directly, and on the
`_CompatCursor` PG wrapper via a `fetchone()` against the cursor —
**but only if the INSERT included `RETURNING id`**. Every existing
INSERT whose new id is read back carries `RETURNING id` as of this
session's pre-Neon sweep. **Pattern for new INSERTs:** add
`RETURNING id` to the SQL and access `cur.lastrowid` as usual; both
backends behave identically.

### Migrations

New columns/tables go in BOTH `_SQLITE_MIGRATIONS` and
`_PG_MIGRATIONS`. The runner supports either SQL strings or
callable migrations (added in Session 2D for table-rebuild needs
SQLite can't do via ALTER). Migrations run on every cold start —
must be idempotent.

Postgres runner now commits each statement individually; a failed
`SET NOT NULL` (e.g. on a fresh DB pre-bootstrap) doesn't roll back
prior successful migrations.

### Rx engine

- `rx_engine.apply_session_outcome(db, exercise, date, sets,
  targets..., rx_source, user_id=None)` is the **only** way to
  write a session into `current_rx` + `training_log`. UPSERT scoped
  on `(user_id, exercise)`.
- `current_rx.current_*` is the **prescribed baseline**, not last
  performance. For historical snapshots, query `training_log`.
- `next_*` is the prescription for the next session. Always
  projected from the (possibly Family-B-promoted) baseline.
- Deload action (`/rx/<id>/deload`): drops the primary progression
  dimension 10% via `compute_deload_baseline`, re-projects `next_*`
  via `project_next_from_current`, resets both
  `consecutive_failures` and `sessions_since_progress` to 0,
  stamps `rx_source='Auto-deload'`. Bodyweight exercises drop reps;
  Plyo drops sets.

### Plan matching

- `plan_match.find_best_match(db, activity, user_id=None)` searches
  days `(0, -1, 1, -2, 2, -3)` in order; closer days win on ties.
  Returns `None` when no candidate scores ≥ 0.5; callers fall
  through to the user prompt.
- "In addition to" is **not** a disposition value. The disposition
  table tracks `completed` and `swapped_for` only. The user-facing
  radio includes "in addition to" as friendly framing, but the
  import handler routes that case to a standalone log with
  `plan_item_id=NULL` and writes no disposition row.

### Bulk plan editor

- `POST /plans/<plan_id>/items/bulk` with
  `{item_ids, action, value}`. Four actions: `shift_date`,
  `intensity_step`, `duration_scale`, `mark_skipped`. Only operates
  on items where `status='scheduled'` AND the parent plan is owned
  by the current user.
- `duration_scale` skips strength items (their load lives in the
  description, not the clock) — instead it appends a marked note
  `[Load scaled to N% — reduce/increase weights ~M% from prescribed]`
  to the description. Idempotent: a regex anchored at end-of-string
  strips any prior load-scale note before appending the new one,
  so re-running with a different multiplier replaces (no stacking).
  `mult=1.0` is a clean no-op.

### Brand system

- **CSS tokens** are in `static/style.css` `:root`. Colours in
  OKLCH; never hardcode brand colours in templates — use
  `var(--ink)`, `var(--orange)`, etc.
- **The logo IS the wordmark + mark.** Use the inline-SVG lockup
  pattern shown in `templates/base.html` and
  `templates/dashboard.html`.
- **Numerals** must render in JetBrains Mono with `tabular-nums`.
- **Voice rules**: real numbers, short declarative sentences, no
  decorative emoji, no exclamation marks. Functional icons (✓ / ✕)
  stay.
- **Reserve orange.** Signal colour only — CTAs, live state,
  alerts, PRs.

### fit_tool Library Units

- `total_elapsed_time` / `total_timer_time` — **seconds**
- `start_time` / `timestamp` on typed messages — **Unix milliseconds**
- `total_distance` — **meters**
- `avg_speed` — **m/s**

### Flask Session Size

Cookie-based session, 4 KB limit. Wellness FIT import sidesteps
this by spooling parsed rows to `/tmp/wellness_*.json` and storing
only the path in `flask_session['wellness_tmp']`. Garmin
sync_preview strips per-row `nearby` candidates from the session
blob before storage. Use the same patterns for any other large
transient data flow.

### Anthropic API key plumbing

- Both `coaching.py` and `routes/natural_log.py` read
  `os.environ['ANTHROPIC_API_KEY']`. No fallback. Plan: stays
  shared key managed by app owner; BYOK per-user is parked.
- **Vercel:** set in Project → Settings → Environment Variables
  (Production scope). Vercel does NOT auto-redeploy on env-var
  changes — push a commit or hit "Redeploy" on the latest deployment.
- **TrueNAS / Docker Compose:** lives in `.env` next to
  `docker-compose.yml` on the host. Watchtower image updates do
  **not** reload `env_file` — after editing `.env`, run
  `docker compose up -d` from that directory to recreate the
  container with the new env baked in.

---

## Deployment

### Vercel (`vercel.json`)

Builds on every push to `main` via `@vercel/python`. All routes go
through `app.py`. Env vars come from Vercel's project settings.
**Storage is Neon Postgres** in production via `DATABASE_URL` (wired
this session). Without `DATABASE_URL` the app falls back to SQLite at
`/tmp/training.db` — ephemeral across cold starts; useful for preview
deployments only.

The Vercel build emits a warning about the `builds` block in
`vercel.json` overriding Project Settings. That's intentional — the
`builds` block is the source of truth here. Harmless; can be cleaned
up later by removing the (now-unused) Project Settings overrides.

### TrueNAS via Docker + Watchtower (`docker-compose.yml`)

On every push to `main`, `.github/workflows/docker-publish.yml` builds
and publishes `ghcr.io/ahorn885/exercise:latest`. Watchtower polls
every 300 s, pulls the new image, and recreates the `web` container.
Andy's data lives at `/mnt/storage/exercise/` (persistent SQLite at
`instance/training.db` inside the volume).

### Branching workflow

- Develop on a feature branch, push, merge to `main` with `--no-ff`
  (or a squash commit, as this batch did).
- `init_db.py` runs migrations on app startup — no manual step.
- `git push origin main` is what triggers both deploys.

---

## Backlog

### Standalone improvements (no roadmap dependency)

- **Multi-day wellness chart** — 7-day trend on `/garmin/wellness`,
  complementing the per-day view. Smallest standalone left.
- **Purchases catalog curation** — the seeded `PURCHASE_RECOMMENDATIONS`
  list in `init_db.py` is a starter (~18 items, AR-leaning). Cost
  ranges, copy, and priorities are easy to tune as the user's needs
  evolve; UPSERT-on-slug means edits propagate without disturbing
  per-user state. New items just append to the list.

### Parked

- **Garmin per-user OAuth** — `garmin_auth` is scoped per-user, but
  `/tmp/garth_session` file caching is process-shared. Includes
  401 refresh handling and shared-state cleanup. Blocked per Andy.
- **MFA (TOTP)** — `pyotp` + setup flow on the profile page.
- **Passkeys / WebAuthn** — Andy's preference; deferred because the
  WebAuthn flow is non-trivial (use the `webauthn` Python pkg).
- **BYOK Anthropic API key** — per-user override of the shared
  key in env.
- **Password reset / email verification** — depends on email infra.
- **Custom user-authored exercises** — would migrate
  `exercise_inventory` to `user_id NULL = system, NOT NULL =
  user-custom`. Not needed today.

---

## Multi-User Retrofit Roadmap (all sessions ✅ shipped)

For posterity. The retrofit was planned as five sessions; all are
on `main`.

- **Session 0 ✅** — coaching capture + context awareness:
  `feedback_log` table, normalize-via-Haiku pipeline, hooks on chat
  / plan-review / natural-log / workout-notes; `get_coaching_context`
  surfaces `deload_flags`, `recent_dispositions`, `wellness_summary`.
- **Session 1 ✅** — auth foundation: `users` table, login gate,
  bootstrap-aware register, bcrypt.
- **Session 2A ✅** — schema migrations: `user_id` columns added
  (NULLABLE), backfill UPDATEs, dead tables dropped, composite
  indexes.
- **Session 2B ✅** — INSERT pass: every write threads `user_id`;
  hot-spot SELECTs scoped; engine helpers gain `user_id=None`.
- **Session 2C ✅** — systematic per-route scoping: every remaining
  read scoped; fetch-by-id handlers defended; missed 2B INSERTs
  fixed.
- **Session 2D ✅** — composite UNIQUEs; Postgres NOT NULL on 18
  tables; per-user `current_rx` seed flow; rx_engine UPSERT scoped.
- **Session 3 ✅** — `clothing_options` per-user; `locale_profiles`
  composite PK; `locale_equipment` denormalized `user_id`.
- **Session 4 ✅** — `athlete_profile` table; `/profile` page with
  three tabs; coach memory UI with provenance; change-password.

### End-to-end verification recipe

The harnesses in `/tmp/verify_*.py` cover this programmatically;
recreate from git history as needed. Manual smoke-test:

1. Register two users (A and B) via `/auth/register`.
2. As A: log a strength session against a seeded exercise (Back
   Squat), log a cardio activity, fill out `/profile`, give
   plan-review feedback ("I hate burpees"), confirm the
   normalized pref shows up in coach memory.
3. Log out, log in as B. Confirm: empty dashboard, training log,
   cardio, body metrics, plans, coaching, Garmin status, profile,
   coach memory, feedback log, clothing options, locales,
   wellness summary.
4. As B, create separate data, generate a plan, confirm Claude's
   prompt uses B's profile + memory, not A's.
5. Log back in as A (user_id=1), confirm all original data intact.
6. Confirm cookie session size stays under 4 KB.
