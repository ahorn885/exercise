# AIDSTATION — Session Handoff

**Date:** 2026-05-02
**Branch merged:** `claude/review-handoff-gE8iH` → `main` (merge commit `9e9bb92`)

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
  (completed / swapped_for / in_addition_to)
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
                      ±2/+1 days), record_disposition() (completed | swapped_for),
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
                      four-option resolve UI when not.
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
| `coaching_preferences` | Persistent coach preferences |
| `wellness_log` | Per-second Garmin wellness data |
| `garmin_auth` | Garmin Connect OAuth session |
| `garmin_workouts` | Garmin workout IDs pushed for scheduled plan items |
| `locale_profiles` | Home/hotel/travel equipment profiles |
| `plan_travel` | Travel periods linked to a plan |
| `equipment_items` | Equipment catalog |
| `exercise_equipment` | Many-to-many exercise↔equipment with option groups |
| `locale_equipment` | Many-to-many locale↔equipment |
| `training_modalities` | Activity types with AR carryover ratings |
| `clothing_options` | Seeded clothing picklist values |

---

## What Was Done This Session

### Rx progression rewrite (commit `7a7464f`)

Complete rebuild of how `current_rx` updates from logged sessions, per
Andy's spec. Three duplicated call sites (`training.py` + 2 in `garmin.py`)
collapsed into one `rx_engine.apply_session_outcome()` helper.

**Baseline semantics:** `current_rx.current_*` is now the prescribed
baseline, not a snapshot of last performance. It only moves up on
PROGRESS (Family B promotes overshoot to baseline) and only moves down
after 3 consecutive REDUCEs. REPEAT and isolated REDUCE leave baseline
alone — bad days no longer overwrite hard-won gains.

**Outcome rules (`calculate_outcome_from_sets`):**
- `PROGRESS ↑` — every set met target reps + weight (or duration)
- `REPEAT →` — any failed set, total volume ≥ 75% of target
- `REDUCE ↓` — any failed set, total volume < 75% of target

**Family A — 2× kicker** on the progressing dimension. Trigger:
- 2+ sets at ≥ ceil(target × 1.10) on reps OR duration, OR
- A qualifying extra set (logged > target_sets and met target reps + weight)

Effect by progression dimension:
- Weight-progressing → `next_weight = current + 2 × increment`
- Rep-progressing → `next_reps = max(current + rep_incr, ceil(current × 1.10))`
- Duration-progressing → `next_duration = max(current + d_incr, ceil(current × 1.10))`

**Family B — performance-tracked baseline.** If 2+ sets exceeded target on
a dimension, that dimension's baseline promotes to the **min over-target
value** ("the level they hit twice") before next is projected. Captures
overshoots without drifting on outliers.

**Failure counter:** REPEAT now resets to 0 (was: freeze) so "consecutive"
means strictly consecutive REDUCEs. Regression also resets to 0 so the
user gets a fresh window at the lower target.

**FIT bootstrap mode:** when there are no targets (FIT import without a
plan-item match), `apply_session_outcome` seeds `current_*` and `next_*`
from min-across-sets actuals and UPSERTs a current_rx row for first-time
exercises. Initial profile creation now produces real Rx values from a
single FIT upload.

**Manual `/rx` edits** call `project_next_from_current()` so editing
`current_*` re-derives `next_*` — prescription never goes stale.

Adds `next_duration` columns to `current_rx` and `training_log` (was
being computed but silently dropped — UPDATE statements never wrote it).

### Deload suggestion at 5 plateau sessions (commit `530d589`)

New `current_rx.sessions_since_progress` counter. Increments on REPEAT or
REDUCE, resets on PROGRESS, untouched in FIT bootstrap mode. Catches the
plateau hole the regression machinery missed: a stuck exercise that
alternates REPEAT and REDUCE never trips 3-in-a-row to fire regression
but is clearly stalled.

At ≥ 5 the `/rx` list shows a `deload` badge suggesting a 10–20% drop and
rebuild. The system flags; the user (or coach) decides — no auto-deload.

Manual rx edit form gains a "reset plateau counter" checkbox alongside
the existing "reset failure counter."

`DELOAD_THRESHOLD = 5` lives in `rx_engine.py`.

### FIT auto-match + swap/addition resolve (commit `829c83b`)

New `plan_match.py` module replaces the in-file `_find_plan_match` /
`_sports_compatible` / `_compute_compliance` helpers in `routes/garmin.py`.
Used by both manual FIT upload and Garmin sync — single source of truth.

**Match flow:**
- Tier 1 — same day, fuzzy on duration + distance (±50% window)
- Tier 2 — nearby days (-2 / +1), same scoring
- Tier 3 — no match: ask the user via four radio options on the preview page

**Scoring:**
- Sport compatibility is a hard gate. Activity name (e.g., "Trail Running")
  → plan sport_type ("running") via `_ACTIVITY_TO_PLAN_SPORT`. Sport groups
  in `_SPORT_GROUPS` make hike↔walk and similar interchangeable.
- Duration / distance: ratio in [0.5, 1.5] scored as `1 - abs(1 - ratio)`;
  outside the window → hard reject (score 0).
- Sport-only (no metric targets on the plan) → `SCORE_SPORT_ONLY = 0.6`,
  enough to auto-match a strength session against an unstructured plan item.
- `SCORE_AUTO_MATCH = 0.5` is the floor for silent auto-attach.

**Strength sessions match too.** The session's summed set duration is fed
to the matcher; sport-only matching covers planned strength items with no
duration target. A user who bailed early or swapped one exercise still
matches the slot.

**Manual FIT upload preview:**
- If matched: green "Auto-matched to X (87% match)" banner, hidden
  `disposition=completed` + `plan_item_id`, user just clicks Save.
- If not matched: four-option resolve block:
  1. **Standalone** — no plan link
  2. **This was the planned workout** — completed
  3. **Did this instead of** — swapped_for + reason textarea
  4. **Did this in addition to** — standalone log, plan item stays scheduled,
     reason captured for context only

**Disposition tracking** via the new `plan_item_disposition` table.
`plan_items.status` gains a `swapped` value distinct from `completed`.

**"In addition to" creates no DB link** per Andy: it's friendly framing for
"log it standalone, don't touch the plan item." The standalone log row is
the only artifact. `plan_match.record_disposition()` raises ValueError if
called with `'in_addition_to'` to enforce this.

**Garmin sync path** (`_build_preview` / `_import_activity`) uses the new
matcher and writes disposition rows on auto-match too. The two import
paths now share one code path.

---

## Key Patterns / Gotchas

### DB Access
```python
db = get_db()
row = db.execute('SELECT * FROM table WHERE id=?', (id,)).fetchone()
dict(row)  # row_factory gives sqlite3.Row (dict-like); access by column name
```
The codebase uses `?` placeholders everywhere — works for SQLite locally and
the Vercel deployment is also SQLite-shaped. Don't introduce `%s`.

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
- `plan_match.find_best_match()` returns `None` when no candidate scores
  ≥ 0.5. Callers fall through to the user prompt. Don't lower the floor
  without thinking through what false-positive matches do to disposition.
- "In addition to" is **not** a disposition value. The disposition table
  tracks `completed` and `swapped_for` only. The user-facing radio includes
  "in addition to" as friendly framing, but the import handler routes that
  case to a standalone log with `plan_item_id=NULL` and writes no
  disposition row.
- The Garmin sync path doesn't currently surface the four-option resolve UI
  — it only auto-matches. If the user wants per-row swap/addition during
  bulk sync, that's the next iteration.

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
in `flask_session['wellness_tmp']`. Use the same pattern for any other
large transient data flow.

### Anthropic API key plumbing
- Both `coaching.py` and `routes/natural_log.py` read
  `os.environ['ANTHROPIC_API_KEY']`. No fallback.
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
`app.py`. Env vars come from Vercel's project settings.

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
  Should be `branches: [main]` only.

### Follow-ups from this session

- **Coaching context awareness of dispositions.** `coaching.py`'s
  `get_coaching_context()` doesn't yet read `plan_item_disposition` or the
  new `plan_items.status='swapped'` value. The coach can't reason about
  "Andy swapped Tuesday's run for a bike ride because he was tired" until
  it sees those rows. Worth a thin pass over the coaching prompt to surface
  recent swap reasons and `sessions_since_progress` deload flags.

- **Sync preview swap/addition UI.** Garmin sync (`/garmin/sync`) only
  auto-matches today; no per-row swap or "in addition to" prompts during
  bulk sync. If multiple activities arrive that need user resolution, the
  user has to manually edit them after import. Natural extension: the
  resolve block from `import_preview.html` reused inline per row in
  `sync_preview.html`.

- **Plan-item dropdown layering on import preview.** The "Nearby (-2 to
  +1 days)" optgroup and "All scheduled" optgroup may both contain the
  same item. If a near-future plan item shows up in both, the user sees
  it twice. Easy fix: dedupe IDs from the wider list when populating the
  optgroups.

### Parked / planned rebuilds

- **Wellness → coaching context.** `get_coaching_context()` doesn't pull
  from `wellness_log` yet. Andy explicitly wants this **rebuilt from the
  ground up** rather than bolted onto the existing function — leave the
  current shape alone and design fresh.
- **Garmin auth refresh** — `plans.py` workout push is fragile around
  Garmin OAuth token expiry; surfaces as confusing 401s. Lower priority
  unless it actively bites.

### Ideas
- A multi-day wellness chart (7-day trend) would complement the per-day
  view at `/garmin/wellness`.
- Plan-item editing is currently per-item; a week-view bulk edit would be
  a natural follow-up.
- Auto-deload action button next to the `deload` badge — one click to
  drop weight 10% and reset the plateau counter, as a faster alternative
  to manually editing the Rx.
