# AidStation — Session Handoff

**Date:** 2026-05-02
**Branch merged:** `claude/review-handoff-file-CDi71` → `main`

---

## What The App Is

**AidStation** — a personal training log / coach web app for an adventure racer. Flask + SQLite (local) / Postgres (production). No build step; pure server-rendered Jinja2 + Bootstrap 5. Deployed somewhere with `DATABASE_URL` env var; locally runs with SQLite at `instance/training.db`.

Key capabilities:
- Strength training log with per-set tracking, progression logic, and injury awareness
- Cardio log (runs, bike, hike, paddle, swim, etc.)
- Natural-language log entry via Claude API (`/` — the homepage)
- Training plan generation + review via Claude coaching system
- Garmin FIT file import (activity FIT → cardio/strength logs; wellness FIT → HR/stress/body battery)
- Garmin Connect sync (OAuth, activity pull)
- Conditions / clothing log
- Body metrics tracking
- Injury log with per-exercise modification tracking
- Locale profiles (home gym, hotel, travel) that filter available exercises

---

## Architecture

```
app.py              — Flask app factory; registers blueprints; runs DB init on startup
database.py         — get_db() helper; supports both SQLite row_factory and psycopg2
init_db.py          — SQLITE_SCHEMA, PG_SCHEMA, _SQLITE_MIGRATIONS, _PG_MIGRATIONS
                      Also seeds exercises, equipment catalog, clothing options.
                      Run migrations on every cold start (all IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
calculations.py     — calculate_outcome_from_sets(), calculate_1rm(), calculate_next_rx()
coaching.py         — Claude API calls: get_coaching_context(), generate_plan(), run_review()
                      Sport-adaptive system prompt (_BASE_PROMPT + sport module).
garmin_fit_parser.py — parse_fit() (activity), parse_wellness_fit(), _dump_fit()
garmin_connect.py   — Garmin Connect OAuth + activity fetch via garth library
fit_workout_generator.py — generate_activity_fit() → bytes (for manual log FIT export)
routes/
  dashboard.py      — homepage, weather (wttr.in), today's plan
  training.py       — /training, /training/new, /training/session (POST), FIT download
  cardio.py         — /cardio CRUD, FIT download per entry
  natural_log.py    — / (homepage), /parse (Claude NLP), /save
  garmin.py         — /garmin/* (import FIT, wellness, sync, debug, auth)
  coaching.py       — /coaching/* (generate, review, chat, preferences)
  plans.py          — /plans/* (list, import, detail, push to Garmin)
  rx.py             — /rx (exercise list + current Rx)
  body.py, conditions.py, injuries.py, locales.py, references.py
templates/          — Jinja2 per blueprint; base.html has Bootstrap 5 nav
```

---

## Database Tables

| Table | Purpose |
|---|---|
| `exercise_inventory` | Master exercise list with metadata |
| `current_rx` | Per-exercise current prescription (sets/reps/weight + next) |
| `training_sessions` | Groups sets from one workout session |
| `training_log` | Per-exercise entries (targets, actuals, outcome, RPE) |
| `training_log_sets` | Individual set rows for training_log entries |
| `cardio_log` | Cardio entries with full Garmin metrics |
| `body_metrics` | Weight, body fat, VO2max, resting HR |
| `conditions_log` | Weather + clothing per activity |
| `injury_log` | Active/resolved injuries |
| `injury_exercise_modifications` | Per-exercise overrides for an injury |
| `training_plans` | Claude-generated plans |
| `plan_items` | Individual scheduled workouts within a plan |
| `plan_reviews` | Tier 1/2/3 review records |
| `coaching_chat` | Per-plan conversation history |
| `coaching_preferences` | Persistent coach preferences |
| `wellness_log` | Per-second Garmin wellness data (HR, stress, body battery, respiration, steps) |
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

## What Was Done In Recent Sessions

### Wellness FIT Import (this session)
- `garmin_fit_parser.parse_wellness_fit(fit_bytes) -> list` — parses:
  - `MonitoringMessage` → steps, active_calories, active_time_s, distance_m, activity_type
  - `StressLevelMessage` → stress_level (1–100; -2/-1 filtered)
  - `GenericMessage[233]` → heart_rate (bpm)
  - `GenericMessage[279]` → respiration_rate (breaths/min)
  - `GenericMessage[297]` → body_battery (0–100)
  - Readings merged by second-level timestamp (≤1 row/second)
  - `_fit_ts_to_unix_ms()` handles FIT epoch seconds, Unix seconds, and Unix ms from both typed and raw GenericMessage fields
- `wellness_log` table added (UNIQUE on timestamp_ms for idempotent re-import)
- Routes: `GET/POST /garmin/import-wellness` → parse → spools rows to temp JSON file (avoids cookie session 4KB limit) → preview. `POST /garmin/import-wellness/confirm` → bulk INSERT OR IGNORE. `GET /garmin/wellness` → log view with date filter.
- Templates: `import_wellness.html` (upload + preview with per-type counts + 8-row sample), `wellness_log.html` (colour-coded stress/body-battery columns)
- Dashboard: added "Wellness FIT Import" card alongside existing Activity FIT and Training Plans cards

### Activity FIT Generation (previous session)
- `fit_workout_generator.generate_activity_fit(entry) -> bytes` — generates a minimal valid FIT file from a cardio or strength log entry
- After saving a cardio entry (natural log or training session), a "Generate Activity FIT?" prompt card appears — user opts in before download
- Cardio list has a "FIT" button per row with confirm dialog
- Strength session (`/training/session/<id>/activity-fit`) generates a strength FIT

### FIT Debug Dump Improvements (previous session)
- `_dump_fit()` now correctly extracts GenericMessage fields via typed `msg.fields` list (field_id → name mapping)
- GenericMessages keyed as `GenericMessage[<global_id>]` in all_message_samples
- Keeps richest sample (most non-null fields) per message type

### Sport-Adaptive Coaching (earlier session — fully merged)
- `coaching.py` split `_SYSTEM_PROMPT` into `_BASE_PROMPT` + 5 sport modules (AR, Triathlon, Marathon, Ultra, Generic)
- `_detect_sport_module()` picks module from race_disciplines string
- Generate form: 4 new fields (weekly_hours, rest_day, race_philosophy, experience_level)
- `get_coaching_context()`: no LIMIT on current_rx; 90-day log lookback; body metrics trend (4 rows); training modalities; prior plans; Garmin performance fields in cardio
- Dynamic nutrition block from actual body metrics
- Planned-vs-actual delta in Tier 1/2 reviews
- Clothing recommendations for upcoming outdoor sessions

---

## Key Patterns / Gotchas

### DB Access
```python
db = get_db()
row = db.execute('SELECT * FROM table WHERE id=?', (id,)).fetchone()
dict(row)  # row_factory gives sqlite3.Row (dict-like); access by column name
```
Postgres uses `%s` placeholders; SQLite uses `?`. The code uses `?` everywhere since it targets SQLite locally and Postgres via `DATABASE_URL` in production. **Wait — this is wrong for Postgres.** The routes all use `?` which only works in SQLite. Production must be SQLite too, or there's an ORM shim not visible here. Don't introduce `%s` placeholders.

### Migrations
New columns/tables go in BOTH `_SQLITE_MIGRATIONS` and `_PG_MIGRATIONS`. SQLite uses bare `ALTER TABLE ... ADD COLUMN`; Postgres uses `ADD COLUMN IF NOT EXISTS`. CREATE TABLE migrations should use `CREATE TABLE IF NOT EXISTS` in both. Migrations run on every cold start — must be idempotent.

### fit_tool Library Units
- `total_elapsed_time` / `total_timer_time` — **seconds** (not ms)
- `start_time` / `timestamp` on typed messages — **Unix milliseconds**
- `total_distance` — **meters**
- `avg_speed` — **m/s**
- GenericMessage field_id=253 (timestamp) via `field.get_value(0)` — may be FIT epoch seconds; use `_fit_ts_to_unix_ms()` to normalize

### Flask Session Size
Cookie-based session; 4KB limit. The wellness FIT import sidesteps this by writing parsed rows to a temp JSON file in `/tmp` and storing only the file path in `flask_session['wellness_tmp']`. Same pattern should be used for any other large data flows.

### Claude API (coaching)
`coaching.py` uses Anthropic's prompt caching (`cache_control: ephemeral`) on the system prompt. The cache key is the content hash — same sport module + base prompt = cache hit. Coaching context is assembled in `get_coaching_context()` and injected as a user-turn block.

---

## Development Workflow

- Feature branches: `claude/review-handoff-file-<id>`
- Always develop on a named branch, push, then merge to main
- `git push -u origin <branch>` for new branches
- Merge with `--no-ff` to preserve branch history
- `init_db.py` runs automatically on app startup — no manual migration step

---

## Pending / Ideas

- **Wellness log visualisation** — the `/garmin/wellness` view is a raw table. A chart (HR, stress, body battery over time for a selected day) would be much more useful. Chart.js is already loaded via CDN in base.html.
- **Wellness → coaching context** — `get_coaching_context()` doesn't yet pull from `wellness_log`. Average HRV/stress/body battery over the last 7 days would be a good recovery signal for the coach.
- **Natural log: strength sessions** — the natural language parser (`/parse`) handles cardio entries well but doesn't parse multi-exercise strength sessions. Extending it would close the last manual gap.
- **Plan item editing** — individual plan items can be marked complete/skipped but not edited in-place (description, target duration, etc.).
- **Garmin workout push** — `plans.py` can push workouts to Garmin Connect but it's fragile with auth token expiry. The token refresh flow could be more robust.
