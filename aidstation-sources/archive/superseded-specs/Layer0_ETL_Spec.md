# Layer 0 ETL Specification
## Training Plan App — Reference Data Pipeline
**Version:** 1.0  
**Status:** Draft — pending discipline pairing matrix completion  
**Sources:** Sports_Framework_v3.xlsx (0A) · AR_Exercise_Database_v17.xlsx (0B)

---

## 1. Purpose

This document defines the extraction, transformation, and loading process for Layer 0 reference data — the platform-level sport rule sets and exercise library that feed every downstream prompt. This data is static and versioned. It does not change per user. It changes only when the app team releases an updated version of the source xlsx files.

Layer 0 data is **not generated at runtime.** It is extracted once (or on each version update), stored in PostgreSQL, and injected selectively into prompts by a query layer that filters by sport, discipline, equipment, and injury constraints.

---

## 2. Source Files

| File | Layer | Sheets Used | Sheets Excluded |
|------|-------|-------------|-----------------|
| Sports_Framework_v3.xlsx | 0A | 1, 2, 3, 4, 5, 6 | 7 (Layer 1 territory) |
| AR_Exercise_Database_v17.xlsx | 0B | Exercise Master, Sport-Exercise Map | Sport Summary (human use only), Legend (human use only) |

---

## 3. Target Database Schema

All Layer 0 tables live in a dedicated `layer0` schema in PostgreSQL. Every table carries version tracking fields. No row is ever overwritten — a new ETL run inserts new rows and sets `superseded_at` on the prior version.

### 3.1 Versioning Pattern (applied to all tables)

```sql
-- Applied to every Layer 0 table
etl_version        TEXT NOT NULL,        -- e.g. "0A-v3.2" or "0B-v17"
etl_run_at         TIMESTAMPTZ NOT NULL,
superseded_at      TIMESTAMPTZ           -- NULL = current version
```

Queries always filter `WHERE superseded_at IS NULL` to get current data.

---

### 3.2 Table: `layer0.sports` (from 0A Sheet 1)

One row per sport.

```sql
CREATE TABLE layer0.sports (
  id                        SERIAL PRIMARY KEY,
  sport_name                TEXT NOT NULL,        -- join key used across all tables
  typical_duration_range    TEXT,                 -- e.g. "24–200+ hours"
  team_vs_solo              TEXT,                 -- e.g. "Team (2–5) or Solo"
  flag_navigation           BOOLEAN NOT NULL,
  flag_sleep_deprivation    BOOLEAN NOT NULL,
  flag_pack_carry           BOOLEAN NOT NULL,
  pack_weight_lbs           NUMERIC,              -- NULL if flag_pack_carry = false
  flag_transition_training  BOOLEAN NOT NULL,
  primary_discipline_count  INTEGER,
  secondary_discipline_count INTEGER,

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (sport_name, etl_version)
);
```

**Excluded columns from Sheet 1:**
- `Governing Bodies` — tabled for future FAQ feature (see Open Items)
- `Race/Event Formats` — tabled pending Layer 1 review (see Open Items)
- `Status` — all rows are ACTIVE; not useful downstream

---

### 3.3 Table: `layer0.disciplines` (from 0A Sheet 2)

One row per discipline. Universal discipline facts — not sport-specific.

```sql
CREATE TABLE layer0.disciplines (
  id                              SERIAL PRIMARY KEY,
  discipline_id                   TEXT NOT NULL,    -- D-001, D-002, etc.
  discipline_name                 TEXT NOT NULL,
  discipline_category             TEXT,
  min_base_phase_weeks            INTEGER,
  periodization_phases            JSONB,            -- {phase: {duration_weeks, focus}}
  max_weekly_ramp_pct             NUMERIC,          -- standard ramp rate
  age_ramp_40_44_pct              NUMERIC,          -- age-adjusted ramp
  age_ramp_45_54_pct              NUMERIC,
  age_ramp_55_plus_pct            NUMERIC,
  taper_norms                     TEXT,
  common_injury_patterns          TEXT[],
  injury_preceding_behaviors      TEXT[],
  recovery_priority               TEXT,
  key_recovery_modalities         TEXT[],
  evidence_quality                TEXT,             -- stored, not injected into prompts

  -- versioning
  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,

  UNIQUE (discipline_id, etl_version)
);
```

**Excluded columns from Sheet 2:**
- `Sports It Appears In` (col 4) — replaced by `layer0.sport_discipline_bridge`

**Note on evidence_quality:** Stored for internal builder reference and future audit tooling. Not injected into any prompt payload.

---

### 3.4 Table: `layer0.sport_discipline_map` (from 0A Sheet 3)

One row per sport × discipline pairing. Sport-specific context layered on top of universal discipline facts.

```sql
CREATE TABLE layer0.sport_discipline_map (
  id                    SERIAL PRIMARY KEY,
  sport_name            TEXT NOT NULL,          -- FK to layer0.sports
  discipline_id         TEXT NOT NULL,          -- FK to layer0.disciplines
  discipline_name       TEXT NOT NULL,          -- denormalized for query convenience
  role                  TEXT NOT NULL,          -- Primary / Secondary / Minor / Technical
  race_time_pct         NUMERIC,
  sport_specific_context TEXT,                  -- the highest-value field: why this discipline matters for this sport
  phase_load_base_pct   NUMERIC,
  phase_load_build_pct  NUMERIC,
  phase_load_peak_pct   NUMERIC,
  phase_load_taper_pct  NUMERIC,

  -- versioning
  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_id, etl_version)
);
```

**Excluded columns from Sheet 3:**
- `B2B Pairing Rule` (col 7) — consolidated into `layer0.discipline_pairing`. This column should be used to complete the pairing matrix (Sheet 4) before that sheet is ETL'd, then deprecated.

---

### 3.5 Table: `layer0.discipline_pairing` (from 0A Sheet 4)

One row per discipline pair. Authoritative source for same-day training pairing decisions.

```sql
CREATE TABLE layer0.discipline_pairing (
  id                    SERIAL PRIMARY KEY,
  discipline_id_a       TEXT NOT NULL,          -- FK to layer0.disciplines
  discipline_id_b       TEXT NOT NULL,          -- FK to layer0.disciplines
  pairing_rating        TEXT NOT NULL,          -- PREFERRED / ACCEPTABLE / AVOID / N/A
  rationale             TEXT,
  source                TEXT NOT NULL,          -- 'matrix' (Sheet 4) or 'b2b_rule' (Sheet 3 col 7 fallback)

  -- versioning
  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (discipline_id_a, discipline_id_b, etl_version)
);
```

**ETL logic:** Extract Sheet 4 (D-001 through D-017, source = 'matrix') first. Then extract Sheet 3 col 7 for D-018 through D-031 where matrix entries are absent (source = 'b2b_rule'). Once the matrix is fully populated, Sheet 3 col 7 is deprecated as an ETL source.

**Status:** Gap exists for D-018 through D-031. See Open Items.

---

### 3.6 Table: `layer0.phase_load_allocation` (from 0A Sheet 5)

One row per sport × discipline per phase. Stores absolute hour targets and supplemental notes beyond what Sheet 3 provides.

```sql
CREATE TABLE layer0.phase_load_allocation (
  id                        SERIAL PRIMARY KEY,
  sport_name                TEXT NOT NULL,
  discipline_id             TEXT NOT NULL,
  discipline_name           TEXT NOT NULL,
  role                      TEXT NOT NULL,
  phase_base_pct            NUMERIC,
  phase_build_pct           NUMERIC,
  phase_peak_pct            NUMERIC,
  phase_taper_pct           NUMERIC,
  weekly_hours_base         NUMERIC,            -- absolute targets from total rows
  weekly_hours_build        NUMERIC,
  weekly_hours_peak         NUMERIC,
  weekly_hours_taper        NUMERIC,
  vertical_gain_notes       TEXT,               -- populated for Skimo, Mountain Running, XC Skiing only
  additional_notes          TEXT,

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_id, etl_version)
);
```

**Relationship to Sheet 3:** Sheet 3 carries phase load percentages in context with sport-specific notes. Sheet 5 adds absolute hour targets and vertical gain tables. Both are stored; prompts use them for different purposes (percentages for proportion decisions, hour targets for volume ceilings).

---

### 3.7 Table: `layer0.team_formats` (from 0A Sheet 6)

One row per sport × team format paradigm.

```sql
CREATE TABLE layer0.team_formats (
  id                        SERIAL PRIMARY KEY,
  sport_name                TEXT NOT NULL,
  format_paradigm           TEXT NOT NULL,      -- UNIFIED_TEAM / RELAY / DOUBLES / AGGREGATE
  description               TEXT,
  training_implications     TEXT,
  special_notes             TEXT,               -- non-obvious cases, e.g. biathlon relay note

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (sport_name, format_paradigm, etl_version)
);
```

---

### 3.8 Table: `layer0.sport_discipline_bridge` (generated at ETL time)

Derived from Sheet 3. Maps framework sport names to exercise database sport vocabulary. Many-to-many. This is the join key between 0A and 0B.

```sql
CREATE TABLE layer0.sport_discipline_bridge (
  id                        SERIAL PRIMARY KEY,
  framework_sport           TEXT NOT NULL,      -- e.g. "Adventure Racing"
  discipline_id             TEXT NOT NULL,      -- e.g. "D-001"
  discipline_name           TEXT NOT NULL,      -- e.g. "Trail Running"
  exercise_db_sport         TEXT NOT NULL,      -- e.g. "Trail Running" (0B vocabulary)
  role                      TEXT NOT NULL,      -- Primary / Secondary / Minor
  default_race_time_pct     NUMERIC,

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (framework_sport, discipline_id, etl_version)
);
```

**ETL logic:** Generated by reading Sheet 3 and writing one bridge row per sport × discipline combination. The `exercise_db_sport` field must be manually confirmed to match the Sport-Exercise Map vocabulary in 0B — this is a one-time alignment task. Where vocabulary differs (e.g., "XC / AR Cycling" in 0A vs. "XC / AR Cycling" in 0B), the bridge table is the explicit reconciliation point.

---

### 3.9 Table: `layer0.exercises` (from 0B Exercise Master)

One row per exercise.

```sql
CREATE TABLE layer0.exercises (
  id                        SERIAL PRIMARY KEY,
  exercise_id               TEXT NOT NULL,      -- EX001–EX245, permanent key
  exercise_name             TEXT NOT NULL,
  exercise_type             TEXT NOT NULL,
  movement_patterns         TEXT[],             -- parsed from comma-separated
  primary_muscles           TEXT[],
  secondary_muscles         TEXT[],
  equipment_required        TEXT[],             -- parsed from comma-separated
  injury_flags_text         TEXT,               -- free text, col 9 — for coaching explanations
  contraindicated_parts     TEXT[],             -- structured list, col 13 — for programmatic filtering
  equipment_substitutes     JSONB,              -- {standard: [...], improvised: [...]} split on 🏠 prefix
  physical_proxies          JSONB,              -- [{exercise_id, exercise_name}, ...]
  progression_exercise_id   TEXT,              -- single EX ID, nullable
  progression_exercise_name TEXT,
  regression_exercise_id    TEXT,              -- single EX ID, nullable
  regression_exercise_name  TEXT,
  sport_count               INTEGER,           -- computed at ETL time from sport_exercise_map rows
  coaching_cues             TEXT,              -- stored but NOT injected into plan generation prompts

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (exercise_id, etl_version)
);
```

**Excluded columns from Exercise Master:**
- `Novelty` (col 8) — excluded entirely; no athlete preference signal to act on it
- `Notes / Coaching Cues` (col 10) — stored as `coaching_cues` but excluded from plan generation prompt payloads. Surfaced per-exercise in the app UI via a separate lightweight API call when an athlete taps an exercise for detail.

**ETL note on equipment_substitutes:** The raw column contains mixed entries. ETL must split on the 🏠 prefix:
- Entries without 🏠 → `equipment_substitutes.standard[]`
- Entries with 🏠 → `equipment_substitutes.improvised[]` (strip the 🏠 prefix, store the description)

**ETL note on physical_proxies:** Raw format is `EX117 — Loaded Step-Down (Eccentric Box); EX020 — Nordic Hamstring Curl`. Parse on semicolons, then split each entry on ` — ` to extract ID and name.

---

### 3.10 Table: `layer0.sport_exercise_map` (from 0B Sport-Exercise Map)

One row per exercise × sport pairing.

```sql
CREATE TABLE layer0.sport_exercise_map (
  id                    SERIAL PRIMARY KEY,
  exercise_id           TEXT NOT NULL,          -- FK to layer0.exercises
  exercise_name         TEXT NOT NULL,          -- denormalized
  exercise_type         TEXT NOT NULL,          -- denormalized
  sport_name            TEXT NOT NULL,          -- 0B sport vocabulary
  sport_relevance_note  TEXT NOT NULL,          -- highest value field — mechanism of transfer
  priority              TEXT NOT NULL,          -- Critical / High / Medium / Low

  -- versioning
  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (exercise_id, sport_name, etl_version)
);
```

---

## 4. Query Layer Specification

The query layer sits between the database and the prompts. It accepts structured parameters, runs filtered queries, and returns a JSON payload the prompt consumes. The LLM never writes SQL.

### 4.1 Input Parameters

```json
{
  "framework_sport": "Adventure Racing",
  "disciplines": ["Trail Running", "Mountain Biking", "Packrafting"],
  "training_phase": "Base",
  "athlete_age": 42,
  "equipment_available": ["Barbell", "Dumbbells", "Pull-up bar", "Kettlebells"],
  "active_injuries": [
    {"body_part": "Wrist", "side": "Left", "severity": "Recovering"}
  ],
  "locale_type": "home",
  "include_exercise_pool": true,
  "max_exercises": 40
}
```

### 4.2 Query Logic

**Step 1 — Sport context**
Pull from `layer0.sports` where `sport_name = framework_sport`.

**Step 2 — Discipline context**
- Resolve disciplines via `layer0.sport_discipline_bridge` where `framework_sport` matches
- Pull matching rows from `layer0.disciplines` and `layer0.sport_discipline_map`
- Pull `layer0.phase_load_allocation` rows for the sport + discipline set
- Select age-adjusted ramp rate based on `athlete_age`:
  - < 40 → standard ramp
  - 40–44 → `age_ramp_40_44_pct`
  - 45–54 → `age_ramp_45_54_pct`
  - 55+ → `age_ramp_55_plus_pct`

**Step 3 — Pairing rules**
Pull `layer0.discipline_pairing` for all pairs within the athlete's discipline set.

**Step 4 — Exercise pool** (only when `include_exercise_pool = true`)
- Get exercise DB sport names from `layer0.sport_discipline_bridge`
- Pull from `layer0.sport_exercise_map` where `sport_name IN (resolved exercise db sports)`
- Join to `layer0.exercises` on `exercise_id`
- **Filter 1 — Equipment:** Include exercise if ANY of `equipment_required[]` is in `equipment_available[]`, OR `equipment_substitutes.standard` contains available equipment, OR `equipment_substitutes.improvised` is non-empty (improvised option exists)
- **Filter 2 — Injury:** Exclude exercise if ANY element of `contraindicated_parts[]` matches ANY `body_part` in `active_injuries` where severity is 'Acute'. For severity 'Recovering', flag rather than exclude.
- **Sort:** By priority (Critical → High → Medium → Low), then by sport_count descending (cross-sport anchors first)
- **Limit:** `max_exercises` (default 40 for plan generation; 1 for UI detail calls)

### 4.3 Output Payload

```json
{
  "sport_context": {
    "sport": "Adventure Racing",
    "planning_flags": {
      "navigation": true,
      "sleep_deprivation": true,
      "pack_carry": true,
      "pack_weight_lbs": 35,
      "transitions": true
    },
    "disciplines": [
      {
        "id": "D-001",
        "name": "Trail Running",
        "role": "Primary",
        "race_time_pct": 30,
        "sport_specific_context": "...",
        "phase_load": {
          "base_pct": 25,
          "build_pct": 30,
          "peak_pct": 30,
          "taper_pct": 15
        },
        "weekly_hours": {
          "base": 3.5,
          "build": 4.5,
          "peak": 5.0,
          "taper": 2.0
        },
        "weekly_ramp_pct": 8,
        "min_base_weeks": 4,
        "taper_norms": "2-3 weeks, 40-60% volume cut",
        "injury_patterns": ["IT band syndrome", "plantar fasciitis"],
        "pairing_rules": {
          "D-006": {"rating": "PREFERRED", "rationale": "..."},
          "D-007": {"rating": "ACCEPTABLE", "rationale": "..."}
        }
      }
    ]
  },
  "exercise_pool": [
    {
      "exercise_id": "EX021",
      "name": "Bulgarian Split Squat",
      "type": "Strength",
      "movement_patterns": ["Single-Leg", "Squat"],
      "equipment_required": ["Dumbbells"],
      "equipment_status": "available",
      "priority": "Critical",
      "sport_relevance": "Best single lower body exercise for trail running; mimics single-leg descent braking mechanics",
      "contraindicated_parts": ["Knee"],
      "injury_flag": null,
      "progression": {"id": "EX089", "name": "Hollow Body Hold"},
      "regression": {"id": "EX216", "name": "Plank (Front)"},
      "physical_proxies": [
        {"id": "EX117", "name": "Loaded Step-Down (Eccentric Box)"}
      ],
      "improvised_options": []
    }
  ]
}
```

**`equipment_status` values:**
- `available` — athlete has required equipment
- `substitute_available` — standard substitute matches athlete's equipment
- `improvised_available` — no equipment match but improvised option exists
- `proxy_only` — no equipment match, no improvised option; physical proxy is the prescription

**`injury_flag` values:**
- `null` — no conflict
- `excluded` — acute injury; exercise removed from pool entirely
- `flagged` — recovering injury; exercise included with flag for prompt to handle

---

## 5. What Is Not ETL'd and Why

| Data | Source | Decision | Reason |
|------|--------|----------|--------|
| Sport Summary (Sheet 3, exercise DB) | 0B | Excluded | Human navigation only; LLM queries Sport-Exercise Map directly |
| Legend (Sheet 4, exercise DB) | 0B | Excluded | Human reference only; vocabulary defined in schema |
| Sheet 7 (Sports Framework) | 0A | Excluded | Layer 1 territory — athlete onboarding schema |
| Governing Bodies (Sheet 1 col 2) | 0A | Tabled | Future FAQ feature — see Open Items |
| Race/Event Formats (Sheet 1 col 3) | 0A | Tabled | Review after Layer 1 design — see Open Items |
| Sports It Appears In (Sheet 2 col 4) | 0A | Eliminated | Replaced by sport_discipline_bridge |
| Novelty (Exercise Master col 8) | 0B | Eliminated | No athlete preference signal to act on |
| B2B Pairing Rule (Sheet 3 col 7) | 0A | Consolidated | Use to complete Sheet 4, then deprecated as ETL source |
| Evidence Quality (Sheet 2 col 13) | 0A | Stored, not injected | Builder reference only; not in prompt payloads |
| Coaching Cues (Exercise Master col 10) | 0B | Stored, not injected | Surfaced per-exercise in UI; excluded from plan generation prompts |

---

## 6. ETL Run Process

### 6.1 Trigger Conditions
- New xlsx version released by app team
- Manual override by admin (e.g., critical data correction)
- Never triggered by user action or plan generation

### 6.2 Run Order
Order matters due to foreign key dependencies and bridge table derivation.

```
1. layer0.sports                  (Sheet 1, 0A)
2. layer0.disciplines             (Sheet 2, 0A)
3. layer0.sport_discipline_map    (Sheet 3, 0A)
4. layer0.discipline_pairing      (Sheet 4 primary, Sheet 3 col 7 fallback)
5. layer0.phase_load_allocation   (Sheet 5, 0A)
6. layer0.team_formats            (Sheet 6, 0A)
7. layer0.sport_discipline_bridge (derived from Sheet 3 — runs after step 3)
8. layer0.exercises               (Exercise Master, 0B)
9. layer0.sport_exercise_map      (Sport-Exercise Map, 0B)
```

### 6.3 Versioning on Each Run
1. Read current `etl_version` from most recent run
2. Assign new version string (e.g., `0A-v3.3`)
3. Insert all new rows with new `etl_version` and current timestamp
4. Set `superseded_at = NOW()` on all prior rows where `superseded_at IS NULL`
5. All queries filter `WHERE superseded_at IS NULL` — no migration needed, rollback is trivial

---

## 7. Open Items

| # | Item | Action Required | Owner |
|---|------|-----------------|-------|
| 1 | Governing Bodies | Table for future athlete FAQ feature; revisit when FAQ is scoped | App team |
| 2 | Race/Event Formats | Review after Layer 1 prompt design is complete; bring handoffs together to confirm if this field serves any prompt | Cross-chat review |
| 3 | Discipline Pairing Matrix gap (D-018–D-031) | Complete Sheet 4 using Sheet 3 col 7 data before ETL runs | Other chat / app team |
| 4 | Vertical Gain field in Layer 1 | Ensure athlete onboarding captures current vertical gain capacity so Layer 0A vertical gain rules have an athlete baseline to work against | Layer 1 design |
| 5 | exercise_db_sport vocabulary alignment | Manually confirm that framework discipline names (0A) match exercise DB sport names (0B) exactly; resolve any mismatches in bridge table | ETL build |
| 6 | Sheet 3 col 7 deprecation | Once Sheet 4 is complete and ETL'd, remove col 7 from ETL source list and note deprecation in sheet | Other chat / app team |

---

## 8. Downstream Prompt Consumption Reference

Quick reference for prompt authors: what Layer 0 context each layer receives and from which tables.

| Layer | Receives from Layer 0 | Tables queried |
|-------|----------------------|----------------|
| 2A (Discipline Classifier) | Sport planning flags, discipline list with roles and race time % | sports, sport_discipline_map, sport_discipline_bridge |
| 2B (Terrain Classifier) | None directly — terrain is athlete + race input | — |
| 2C (Equipment Mapper) | Exercise pool filtered by discipline only (no equipment filter yet — this layer identifies gaps) | sport_exercise_map, exercises |
| 2D (Injury Risk Profile) | Injury patterns and preceding behaviors per discipline | disciplines |
| 2E (Nutrition Baseline) | None directly — nutrition baseline is sport type + athlete input | — |
| 3D (Injury Analysis) | Contraindicated parts and injury flags per exercise | exercises |
| 4 (Plan Generation) | Full sport context + exercise pool (equipment + injury filtered) | All tables via query layer |
| 4.5 (Validator) | Sport rule sets: ramp rates, phase durations, pairing rules, taper norms | sports, disciplines, discipline_pairing, phase_load_allocation |
| 5A (Nutrition) | None — operates on plan output + athlete data | — |
| 5B (Supplements) | None — operates on plan output + athlete data | — |
| 5C (Clothing) | None — operates on weather + athlete history | — |
