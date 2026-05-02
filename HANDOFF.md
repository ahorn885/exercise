# AIDSTATION — Session Handoff

**Date:** 2026-05-02
**Branch merged:** `claude/review-handoff-cTwRY` → `main` (commit `c41998c`)

> The product is now branded **AIDSTATION** (per Claude Design's brand handoff
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
- Strength training log with per-set tracking, progression logic, and injury awareness
- Cardio log (runs, bike, hike, paddle, swim, etc.)
- Natural-language log entry via Claude API — handles cardio, body metrics,
  **and now multi-exercise strength sessions** (`/log-natural`)
- Training plan generation + review via Claude coaching system
- **Plan item in-place editing** for scheduled items (workout name, description,
  target duration/distance, intensity, notes)
- Garmin FIT file import (activity FIT → cardio/strength logs; wellness FIT
  → HR/stress/body battery)
- **Wellness chart view** (`/garmin/wellness`) — Chart.js panels for HR,
  stress, body battery, respiration on a selected day
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
calculations.py     — calculate_outcome_from_sets(), calculate_1rm(), calculate_next_rx()
coaching.py         — Claude API calls: get_coaching_context(), generate_plan(), run_review()
                      Sport-adaptive system prompt (_BASE_PROMPT + sport module).
                      Uses Anthropic prompt caching (cache_control: ephemeral).
garmin_fit_parser.py — parse_fit() (activity), parse_wellness_fit(), _dump_fit()
garmin_connect.py   — Garmin Connect OAuth + activity fetch via garth library
fit_workout_generator.py — generate_activity_fit() → bytes (manual log FIT export)
routes/
  dashboard.py      — homepage (brand hero), weather (wttr.in), today's plan
  training.py       — /training, /training/new, /training/session (POST), FIT download
  cardio.py         — /cardio CRUD, FIT download per entry
  natural_log.py    — /log-natural NLP entry (cardio + body + strength), /parse, /save
  garmin.py         — /garmin/* (import FIT, wellness, sync, debug, auth)
  coaching.py       — /coaching/* (generate, review, chat, preferences)
  plans.py          — /plans/* (list, import, detail, push to Garmin, PATCH /items/<id>)
  rx.py             — /rx (exercise list + current Rx)
  body.py, conditions.py, injuries.py, locales.py, references.py
templates/          — Jinja2 per blueprint; base.html has the AIDSTATION lockup nav,
                      Inter + JetBrains Mono fonts, OG/Twitter meta tags.
static/
  style.css         — AIDSTATION brand system (tokens, type, Bootstrap overrides)
  favicon.svg       — Mark glyph (cup + terminal prompt + orange caret)
  og-preview.{png,svg} — 1280×640 GitHub social preview (Terminal direction)
  logo/             — mark + lockup SVGs (on-light, on-dark)
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

### AIDSTATION brand system v0.1 + v0.2 (this session)
- **v0.1** — full visual rebrand from the prior amber-terminal theme. Light
  Paper/Ink palette (OKLCH tokens) with Course Orange reserved as signal
  (60/30/10 rule). Inter for copy, JetBrains Mono for data. 1px hairline
  borders, 4px radius, no drop shadows. Bootstrap 5 token map applied across
  buttons, cards, alerts, forms, tables, badges, pagination, modals.
- **v0.2** — pictorial mark added (paper-cup silhouette with terminal prompt
  + orange caret block — the only colour). Three formats shipped:
  mark / horizontal lockup / stacked. Asset library at `static/logo/`.
  Favicon swapped to the real mark. OG + Twitter meta tags + 1280×640
  GitHub social preview at `static/og-preview.png`.
- Navbar is now the horizontal lockup (inline-SVG mark + CSS-typeset
  wordmark). Dashboard opens with a brand hero — display-size mark + the
  display-2 wordmark + lede.
- Voice pass: stripped emoji from nav, plan-link banner, wellness import
  badges. Per the brand, decorative emoji are out; functional icons (✓ / ✕
  on action buttons) stay.

### Navigation cleanup (this session)
- "Garmin" tab → **"Connections"**
- Dropdown items relabelled: "Garmin dashboard", "Settings" (was "Auth
  Settings"). "Import FIT file" removed from the dropdown — already on the
  Garmin dashboard page.

### Natural-log: strength sessions (this session)
- Added a strength entry schema to the system prompt (one entry per session,
  multiple `exercises[]`, sets with `reps`/`weight_lbs`/`duration_sec`).
- The user's `current_rx` exercise list is injected into the prompt so
  Claude can match free-text exercise names ("rdl 3x5 @ 185") to the
  inventory.
- Save handler creates `training_sessions` + per-exercise `training_log` +
  per-set `training_log_sets`. Skips next-Rx calculation — the regular
  Session Logger remains the source of truth for that.
- Preview UI renders strength entries with per-exercise blocks and
  editable set tables; cardio/body keep the flat-field rendering.
- Removed the "use Session Logger instead" punt from the prompt.
- Also: textarea is no longer disabled when `ANTHROPIC_API_KEY` is missing
  — input flows through, Send returns the same clear error.

### Plan item in-place editing (this session)
- Wired up the existing `PATCH /items/<int:item_id>` API
  (`routes/plans.py:257`) to an Edit toggle on the workout-details card.
- Editable fields: workout_name, description, target_duration_min,
  target_distance_mi, intensity, notes. Only shown for `status='scheduled'`
  items. Reload on save.

### Wellness chart view (this session)
- `/garmin/wellness` defaults to the most recent date with data so the
  chart panel has something to render on first visit.
- Four Chart.js line charts (HR, stress 0–100, body battery 0–100,
  respiration) with brand-styled axes (Ink lines, Orange for stress,
  JetBrains Mono ticks, hairline grid, Ink tooltip with mono body).
- Chart.js loaded only on this page, gated on `chart_data` so the script
  doesn't fire when there's no data.

### Wellness FIT Import (prior session — already shipped on `main`)
- `parse_wellness_fit(fit_bytes) -> list` — HR, stress, body battery,
  respiration, steps. `wellness_log` table with UNIQUE on `timestamp_ms`
  for idempotent re-import. Routes spool parsed rows to a temp JSON file
  to dodge the 4 KB cookie limit.

### Activity FIT Generation (earlier session — already shipped)
- `fit_workout_generator.generate_activity_fit(entry) -> bytes` — minimal
  valid FIT from a cardio or strength log entry. Generate-after-save
  prompt card; cardio list "FIT" button; strength session FIT export.

### Sport-Adaptive Coaching (earlier session — already shipped)
- `coaching.py` split `_SYSTEM_PROMPT` into `_BASE_PROMPT` + 5 sport
  modules (AR, Triathlon, Marathon, Ultra, Generic). `_detect_sport_module()`
  picks one from `race_disciplines`. `get_coaching_context()`: full
  current_rx, 90-day log lookback, body metrics trend, training modalities,
  prior plans, Garmin performance fields. Dynamic nutrition block.
  Planned-vs-actual delta in Tier 1/2 reviews. Clothing recommendations
  for upcoming outdoor sessions.

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
SQLite, which silently no-ops on duplicates).

### Brand system
- **CSS tokens** are in `static/style.css` `:root`. Colours in OKLCH; never
  hardcode brand colours in templates — use `var(--ink)`, `var(--orange)`, etc.
- **The logo IS the wordmark + mark.** Use the inline-SVG lockup pattern
  shown in `templates/base.html` and `templates/dashboard.html`. The mark
  uses `currentColor` for the strokes — only the orange caret block is
  hardcoded `#E8893A`. Do not recolour the caret.
- **Numerals** must render in JetBrains Mono (`var(--font-mono)`) with
  `tabular-nums`. The `.num`, `.stat`, `.table-num` utilities and
  `.mono-num` / `.mono-lbl` are pre-built. Numeric inputs (`type="number"`,
  `time`, `date`, `datetime-local`) auto-pick up the mono font from
  `style.css`.
- **Voice rules** (per Claude Design): real numbers, short declarative
  sentences, no emoji in product copy, no marketing-speak, no exclamation
  marks. Functional icons (action affordances) are OK.
- **Reserve orange.** It's a *signal* colour — CTAs, live state, alerts,
  PRs, the caret block. Don't use it decoratively.

### fit_tool Library Units
- `total_elapsed_time` / `total_timer_time` — **seconds**
- `start_time` / `timestamp` on typed messages — **Unix milliseconds**
- `total_distance` — **meters**
- `avg_speed` — **m/s**
- GenericMessage `field_id=253` (timestamp) via `field.get_value(0)` may be
  FIT epoch seconds; use `_fit_ts_to_unix_ms()` to normalize

### Flask Session Size
Cookie-based session, 4 KB limit. Wellness FIT import sidesteps this by
spooling parsed rows to `/tmp/wellness_*.json` and storing only the path
in `flask_session['wellness_tmp']`. Use the same pattern for any other
large transient data flow.

### Claude API (coaching)
`coaching.py` uses Anthropic prompt caching (`cache_control: ephemeral`,
1h TTL) on the system prompt. Cache key is content hash — same sport
module + base prompt = cache hit. Coaching context is assembled in
`get_coaching_context()` and injected as a user-turn block.

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
- `SECRET_KEY` (Flask session signing) has a hardcoded dev fallback
  (`'ar-training-2026'`) in `app.py` — replace it in prod via the same
  env-var paths.

---

## Deployment

### Vercel (`vercel.json`)
Builds on every push to `main` via `@vercel/python`. All routes go through
`app.py`. Env vars come from Vercel's project settings.

### TrueNAS via Docker + Watchtower (`docker-compose.yml`)
On every push to `main`, `.github/workflows/docker-publish.yml` builds and
publishes `ghcr.io/ahorn885/exercise:latest`. Watchtower polls every
300 s (`WATCHTOWER_POLL_INTERVAL=300`), pulls the new image, and recreates
the `web` container with the same runtime config. End-to-end ~10 min from
merge to live.

### Branching workflow
- Feature branches: `claude/review-handoff-<id>` (the harness assigns one
  per session)
- Develop on the branch, push, merge to `main` with `--no-ff`
- `init_db.py` runs migrations on app startup — no manual step
- `git push origin main` is what triggers both deploys

---

## Pending / Open

### Carry-forward to-dos
- **TrueNAS `.env`** — add `ANTHROPIC_API_KEY` and `SECRET_KEY` to the host
  `.env` (next to `docker-compose.yml`) and run `docker compose up -d`
  from that directory to recreate the container. Watchtower won't reload
  `.env` on its own. Vercel side is already done.
- **Stale workflow trigger** — `.github/workflows/docker-publish.yml` still
  triggers on a long-gone branch (`claude/review-handoff-file-CDi71`).
  Should be `branches: [main]` only, or update to whatever's the active
  dev branch.

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
