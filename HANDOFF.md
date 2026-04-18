# Session Handoff Document

## Project

Flask/SQLite + Postgres training app for a 2026 adventure race athlete.
Repository: `ahorn885/exercise`
Working branch: `claude/merge-garmin-exercise-site-fSoYw`

---

## What Was Built This Session

### 1. Equipment M2M Refactor (commit `0091c23`)

Replaced the flat `exercise_inventory.equipment` text column with a proper relational model.

**New tables:**
- `equipment_items(id, tag, label, category)` — 52 items across 9 categories, seeded from `EQUIPMENT_CATEGORIES` in `init_db.py`
- `exercise_equipment(exercise_id, equipment_id, option_group)` — M2M with AND/OR logic: rows sharing the same `option_group` = AND (both required), different groups = OR (either works)
- `locale_equipment(locale, equipment_id)` — replaces `locale_profiles.equipment` text column

**Key files changed:**
- `init_db.py` — `EQUIPMENT_CATEGORIES` constant (single source of truth); seeding phases for all 3 tables; `EXERCISE_EQUIPMENT` dict mapping exercise names → equipment requirements
- `routes/locales.py` — rewrites `list_profiles()` and `edit_profile()` to use `locale_equipment JOIN equipment_items`
- `routes/references.py` — replaced string-based `_equipment_available()` with `_exercise_available(exercise_id, ex_eq_map, profile_equipment_ids)` using M2M IDs

**AND/OR logic (important):**
```python
def _exercise_available(exercise_id, ex_eq_map, profile_equipment_ids):
    reqs = ex_eq_map.get(exercise_id)
    if not reqs:
        return True  # bodyweight — always shown
    groups = defaultdict(set)
    for eq_id, grp in reqs:
        groups[grp].add(eq_id)
    return any(grp_ids.issubset(profile_equipment_ids) for grp_ids in groups.values())
```

---

### 2. Injury → Exercise Modification System (commit `41e7790`)

**New table:**
```sql
CREATE TABLE IF NOT EXISTS injury_exercise_modifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    injury_id INTEGER NOT NULL REFERENCES injury_log(id),
    exercise_id INTEGER NOT NULL REFERENCES exercise_inventory(id),
    substitute_exercise_id INTEGER REFERENCES exercise_inventory(id),
    modification_type TEXT NOT NULL DEFAULT 'modify',  -- avoid | substitute | reduce_load | modify
    modification_notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

**Three feedback touchpoints:**

1. **Injury list** (`/injuries`) — collapsible "Exercise Modifications" panel per Active/Managing injury. Inline add form (exercise + type + optional substitute + notes). JS shows/hides the substitute dropdown based on `modification_type`.

2. **Training form** (`/training/new`, `/training/<id>/edit`) — when exercise is selected, `loadRx()` JS (which calls `/api/rx/<exercise>`) now also fetches active injury mods and renders an amber warning banner inline.

3. **Plan view** (`/plans/<id>`) — amber alert banner at top listing all active modifications; ⚠️ badge on individual plan item rows where the workout name or description contains an affected exercise name (substring match, uses Jinja2 `namespace` trick since Jinja has no `break`).

**Key files changed:**
- `init_db.py` — table in both schemas + migrations
- `routes/injuries.py` — `MOD_TYPES` list; `add_modification()` and `delete_modification()` routes; `list_entries()` loads modifications dict
- `routes/training.py` — `/api/rx/<exercise>` extended to JOIN injury_exercise_modifications and return `injury_mods` list
- `routes/plans.py` — `view_plan()` queries active mods, passes `active_mods` + `affected_exercises` set
- `templates/injuries/list.html` — full redesign as Bootstrap cards with collapsible mods panel
- `templates/training/form.html` — `injury-warning` div + JS rendering logic
- `templates/plans/view.html` — banner + row badges

---

### 3. plan_item_id FK on cardio_log + training_log (commit `705f4ef`)

Links completed sessions back to the plan item they fulfilled.

**Column added:** `plan_item_id INTEGER REFERENCES plan_items(id)` (nullable) on both `cardio_log` and `training_log`.

**Behavior:** Saving a log entry with a `plan_item_id` automatically runs:
```sql
UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'
```

**Where the selector appears:**
- Manual cardio log form (`/cardio/new`, `/cardio/<id>/edit`)
- Manual training log form (`/training/new`, `/training/<id>/edit`)
- Garmin FIT import preview (`/garmin/import/preview`) for both cardio and strength imports

The selector shows all `scheduled` plan items (up to 60, ordered by date ascending). Hidden when there are no scheduled items.

**Key files changed:** `init_db.py`, `routes/cardio.py`, `routes/training.py`, `routes/garmin.py`, `templates/cardio/form.html`, `templates/training/form.html`, `templates/garmin/import_preview.html`

---

### 4. conditions_log.cardio_log_id FK (commit `f3647d9`)

Links conditions/clothing log entries to the cardio session they describe.

**Column added:** `cardio_log_id INTEGER REFERENCES cardio_log(id)` (nullable) on `conditions_log`.

**Behavior:** Optional dropdown on the conditions form showing the 60 most recent cardio sessions. Selecting one auto-fills the date and activity fields (only if currently empty).

**Key files changed:** `init_db.py`, `routes/conditions.py`, `templates/conditions/form.html`

---

## Current Database Relationship Map

```
training_plans
  └─ plan_items ─────────────────────────────── garmin_workouts
       │
       ├─▶ cardio_log ──[cardio_log_id]──▶ conditions_log
       │       │
       │  [plan_item_id] ← now wired
       │
       └─▶ training_log
               │
          [plan_item_id] ← now wired
               │
          [string: exercise] ──▶ exercise_inventory
                                       │
                               exercise_equipment (M2M)
                                       │
                               equipment_items
                                       │
                               locale_equipment (M2M)

injury_log ──▶ injury_exercise_modifications ──▶ exercise_inventory
   (feeds warnings to training form and plan view)
```

---

## Remaining Tasks (from the original plan)

### #3 — `exercise_id` FK on `training_log` + `current_rx`

**Gap:** Both tables link to `exercise_inventory` via `exercise TEXT` name string. Works because `exercise` is `UNIQUE`, but prevents efficient JOINs and is fragile if names ever change.

**Plan:**
1. Add `exercise_id INTEGER REFERENCES exercise_inventory(id)` (nullable) to both `training_log` and `current_rx` in both schemas + migrations
2. Backfill via: `UPDATE training_log SET exercise_id = (SELECT id FROM exercise_inventory WHERE exercise = training_log.exercise)`
3. Same backfill for `current_rx`
4. On new inserts/updates in `routes/training.py`, also write `exercise_id` alongside the name string
5. Keep the name column — used for display everywhere; don't break existing queries

**Files to change:** `init_db.py`, `routes/training.py`

### #4 — `locale_equipment.locale` formal FK to `locale_profiles`

**Gap:** `locale_equipment.locale` is a bare TEXT column that matches `locale_profiles.locale` by convention only.

**Plan:** Add `REFERENCES locale_profiles(locale)` to the column definition in both schemas + a migration. Trivial — one line each in SQLite and PG schemas, one migration line each.

**Note:** SQLite doesn't enforce FKs unless `PRAGMA foreign_keys = ON` is set per connection. The app uses `sqlite3.Row` row factory (see `database.py`) but doesn't enable FK enforcement. So this is mostly documentation/correctness rather than runtime enforcement.

---

## Key Architecture Notes

- **Dual DB:** `init_db.py` maintains both `SQLITE_SCHEMA` and `PG_SCHEMA`. Migrations live in `_SQLITE_MIGRATIONS` and `_PG_MIGRATIONS` (lists of SQL strings). Each migration runs inside a try/except so re-running is safe.
- **DB connection:** `database.py` → `get_db()` returns a `sqlite3.Row`-factory connection (or psycopg2 for Postgres). Column access by name works on all rows.
- **`EQUIPMENT_CATEGORIES`** is defined in `init_db.py` and imported by `routes/locales.py` (not the other way around — avoids circular imports during seeding).
- **Jinja2 has no `break`** — use `{% set ns = namespace(flagged=false) %}` + `{% set ns.flagged = true %}` pattern to short-circuit loops.
- **Idempotent seeding:** All seed INSERTs use `INSERT OR IGNORE` (SQLite) or `ON CONFLICT DO NOTHING` (PG).

---

## File Map (key files)

| File | Role |
|---|---|
| `init_db.py` | Both schemas, all migrations, all seed data (EXERCISES, EQUIPMENT_CATEGORIES, EXERCISE_EQUIPMENT) |
| `database.py` | `get_db()` — returns DB connection with Row factory |
| `app.py` | Flask app factory, blueprint registration |
| `routes/training.py` | Strength log CRUD + `/api/rx/<exercise>` (includes injury mods) |
| `routes/cardio.py` | Cardio log CRUD |
| `routes/plans.py` | Training plan + plan item CRUD, Garmin push |
| `routes/garmin.py` | FIT import (parse → preview → confirm), Garmin Connect auth |
| `routes/injuries.py` | Injury log CRUD + exercise modification add/delete |
| `routes/references.py` | Exercise inventory, locale equipment filtering |
| `routes/locales.py` | Locale profile view/edit (imports EQUIPMENT_CATEGORIES from init_db) |
| `routes/conditions.py` | Conditions/clothing log CRUD |
| `calculations.py` | `calculate_outcome()`, `calculate_next_rx()` with 3-strike regression |
| `garmin_fit_parser.py` | Parses `.fit` files into cardio or strength dicts |
| `garmin_connect.py` | Garmin Connect API (upload workout, schedule, auth) |
| `templates/base.html` | Nav, Bootstrap 5 |
| `templates/plans/view.html` | Plan view with injury mod banner + ⚠️ row badges |
| `templates/injuries/list.html` | Injury cards with collapsible modification panels |
| `templates/training/form.html` | Strength log form with injury warning JS |

---

## How to Resume

```bash
# Ensure you're on the right branch
git checkout claude/merge-garmin-exercise-site-fSoYw
git pull origin claude/merge-garmin-exercise-site-fSoYw

# Run migrations (safe to re-run)
python init_db.py

# Start dev server
flask run  # or python app.py
```

Start with task #3 (exercise_id FK) or #4 (locale FK). Both are straightforward migrations; #3 also requires updating the write path in `routes/training.py`.
