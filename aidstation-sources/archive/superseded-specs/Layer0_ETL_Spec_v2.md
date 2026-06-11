# Layer 0 ETL Specification — v2

**Version:** 2.0
**Status:** Ready for build
**Supersedes:** `Layer0_ETL_Spec.md` (v1)
**Sources:**
- `Sports_Framework_v6.xlsx` (0A) — was v3 in spec v1; structural changes since
- `AR_Exercise_Database_v17.xlsx` (0B) — unchanged
- `Vocabulary_Audit_v2.md` (0C) — NEW source: canonical vocabularies

---

## What changed in v2 vs v1

1. **Source bump v3 → v6** for Sports Framework. v6 adds Sheet 8 (Cross-Sport Properties) and includes audit notes for Phase Load Allocation including the AR taper feasibility patch and Group A audit (rows A.4–A.7).
2. **Phase Load Allocation column structure changed.** v1 spec assumed single `phase_*_pct NUMERIC` columns. Reality: each phase has Low % AND High % (8 numeric columns total) plus a `Notes / Conditions` text column. Schema updated.
3. **Sheet 8 (Cross-Sport Properties) added** as a new Layer 0 source. New table `layer0.cross_sport_properties`.
4. **Vocabulary tables added** as a third Layer 0 source from `Vocabulary_Audit_v2.md`: body parts (50), health condition categories (21), equipment items (143), terrain types (15), sport-specific gear toggles (12).
5. **Pre-ETL cleanup tasks documented.** Vocab Audit Section 5 lists rename and rollup tasks that must be applied to the source xlsx (or as ETL-time transforms) before/during ingestion.
6. **Parsing rules clarified** for compound-text columns where v1 spec assumed simple numerics: pack weight, age-adjusted ramps, race time %, Sport × Discipline phase load string.
7. **Discipline Pairing Matrix gap confirmed unchanged** in v6: matrix covers D-001 through D-017 only; fallback to Sheet 3 col 7 (B2B Pairing Rule) for D-018+ remains required.

---

## 1. Purpose

Define the extraction, transformation, and loading process for Layer 0 reference data — the platform-level sport rule sets, exercise library, and canonical vocabularies that feed every downstream prompt. This data is static and versioned. It does not change per user. It changes only when the app team releases an updated version of any source.

Layer 0 data is **not generated at runtime.** It is extracted once (or on each version update), stored in PostgreSQL, and injected selectively into prompts by a query layer that filters by sport, discipline, equipment, and injury constraints.

---

## 2. Source files

| File | Layer | Sheets / sections used | Excluded |
|------|-------|---|---|
| `Sports_Framework_v6.xlsx` | 0A | Sheets 1, 2, 3, 4, 5, 6, 8 | Sheet 7 (Layer 1 territory — athlete profile data points) |
| `AR_Exercise_Database_v17.xlsx` | 0B | Exercise Master, Sport-Exercise Map | Sport Summary (human nav only), Legend (human reference only) |
| `Vocabulary_Audit_v2.md` | 0C | Sections 1, 2, 3, 4 | Section 5 (cleanup tasks — applied as transforms, not loaded as data); Sections 6–8 (commentary) |

**Sheet 8 (Cross-Sport Properties)** in v6 currently has one substantive property defined (LIT_RATIO_001) plus extension notes. The schema is built to receive future properties without re-spec.

**Sheet 7 (Athlete Profile Data Points)** is excluded from Layer 0. It feeds Layer 1 athlete onboarding spec and lives in different tables.

---

## 3. Pre-ETL data preparation

Before running the ETL, two preparation passes must occur:

### 3.1 Vocabulary cleanup against exercise DB (from Vocab Audit Section 5)

`Vocabulary_Audit_v2.md` Section 5 enumerates rename and rollup tasks for the AR Exercise DB col 7 (Equipment) — bringing exercise-DB equipment strings into alignment with the canonical equipment vocabulary in Section 3 of the audit. Examples: "Kayak / Packraft" → split into atomic items; sub-component sport-specific items (rope, harness, belay device) → rolled up to single category tokens (e.g., `Climbing kit`).

Two implementation options:
- **(a) Apply to source xlsx** before ETL (one-time data correction).
- **(b) Apply as ETL-time transforms** (rules in code, source xlsx untouched).

Option (b) is preferred — it keeps the source files audit-clean and makes the transforms inspectable and reversible. A `vocabulary_transforms.py` module should hold the rename/rollup rules and apply them inside the `layer0.exercises` ETL step.

### 3.2 Discipline Pairing Matrix gap fallback

Sheet 4 covers only D-001 through D-017 (the 17 AR-relevant disciplines). For D-018 through D-031+ (sports beyond AR — Triathlon, Mountain Running, etc.), pairing data must be reconstructed from Sheet 3 col 7 (`B2B Pairing Rule`). Each `B2B Pairing Rule` cell contains text like `→ Hiking: PREFERRED \n → XC Cycling: PREFERRED (standard brick) \n → Packraft/Kayak: ACCEPTABLE`. Parse each line into a per-pairing row. ETL logic in §6.3.

---

## 4. Target database schema

All Layer 0 tables live in a dedicated `layer0` schema in PostgreSQL. Every table carries version tracking fields. No row is ever overwritten — a new ETL run inserts new rows and sets `superseded_at` on the prior version.

### 4.1 Versioning pattern (applied to every table)

```sql
etl_version    TEXT NOT NULL,        -- e.g. "0A-v6.1", "0B-v17.0", "0C-v2.0"
etl_run_at     TIMESTAMPTZ NOT NULL,
superseded_at  TIMESTAMPTZ           -- NULL = current version
```

Queries always filter `WHERE superseded_at IS NULL` for current data.

---

### 4.2 `layer0.sports` (from 0A Sheet 1 — "Sports Index")

One row per sport.

```sql
CREATE TABLE layer0.sports (
  id                          SERIAL PRIMARY KEY,
  sport_name                  TEXT NOT NULL,           -- join key across all 0A tables
  typical_duration_range      TEXT,                    -- e.g. "4 hrs – 14 days"
  team_vs_solo                TEXT,                    -- full descriptive text (col 4)

  -- Parsed booleans + retained narrative text (col 5–8 are "YES/NO — explanation")
  flag_navigation             BOOLEAN NOT NULL,
  navigation_notes            TEXT,
  flag_sleep_deprivation      BOOLEAN NOT NULL,
  sleep_deprivation_notes     TEXT,
  flag_pack_carry             BOOLEAN NOT NULL,
  pack_carry_notes            TEXT,                    -- includes pack weight context
  pack_weight_lbs_low         NUMERIC,                 -- parsed from notes (NULL if not pack carry)
  pack_weight_lbs_high        NUMERIC,                 -- parsed from notes
  flag_transition_training    BOOLEAN NOT NULL,
  transition_training_notes   TEXT,

  primary_discipline_count    INTEGER,
  secondary_discipline_count  INTEGER,
  status_label                TEXT,                    -- e.g. "ACTIVE — Full detail"

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (sport_name, etl_version)
);
```

**ETL parsing rules:**
- `flag_*`: parse first token of column (before the first ` —` or `\n`). If first token is "YES", `TRUE`; "NO", `FALSE`. Anything else → log warning, default `FALSE`.
- `*_notes`: full original text including the YES/NO prefix.
- `pack_weight_lbs_low/_high`: regex on `pack_carry_notes` for patterns like `"25–35 lb"` or `"25-35 lb"`. If single value (`"35 lb"`), low=high. If absent, both NULL.

**Excluded columns:**
- `Governing Bodies` (col 1) — tabled for future FAQ feature; Open Item #1
- `Race / Event Formats` (col 2) — tabled pending Layer 1 review; Open Item #2

---

### 4.3 `layer0.disciplines` (from 0A Sheet 2 — "Discipline Library")

One row per discipline. Universal facts — not sport-specific.

```sql
CREATE TABLE layer0.disciplines (
  id                              SERIAL PRIMARY KEY,
  discipline_id                   TEXT NOT NULL,        -- D-001, D-002, etc.
  discipline_name                 TEXT NOT NULL,
  discipline_category             TEXT,                 -- e.g. "Foot / Running"
  min_base_phase_text             TEXT,                 -- col 4 free text (e.g. "4–6 weeks easy aerobic ...")
  min_base_phase_weeks_low        INTEGER,              -- parsed from text
  min_base_phase_weeks_high       INTEGER,              -- parsed from text
  periodization_text              TEXT,                 -- col 5 free text — multi-phase narrative
  ramp_text                       TEXT,                 -- col 6 free text — ACWR + heuristic + evidence
  age_adjusted_ramp_text          TEXT,                 -- col 7 free text — three age bands
  age_ramp_40_44_pct              NUMERIC,              -- parsed if present (e.g. "Max 8%/week")
  age_ramp_45_54_pct              NUMERIC,
  age_ramp_55_plus_pct            NUMERIC,
  taper_norms_text                TEXT,                 -- col 8 free text
  common_injury_patterns          TEXT[],               -- col 9 split on " · "
  injury_preceding_behaviors      TEXT[],               -- col 10 split on " · "
  recovery_priority_text          TEXT,                 -- col 11 numbered list as text
  recovery_modalities             TEXT[],               -- col 11 parsed list of modality phrases
  evidence_quality_text           TEXT,                 -- col 12 — stored, not injected into prompts

  -- versioning
  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,

  UNIQUE (discipline_id, etl_version)
);
```

**ETL parsing rules:**
- `min_base_phase_weeks_low/_high`: regex on `min_base_phase_text` for `\d+–\d+ weeks` or `\d+ weeks`. Single value → low=high.
- `age_ramp_*_pct`: regex on `age_adjusted_ramp_text` for each age band. The text is structured like `"40–44: Standard ramp; ...\n45–54: Max 8%/week. ...\n55+: ..."`. Extract the `\d+%` from each band's section. NULL if not parseable (some disciplines say "Standard ramp" — store NULL).
- `common_injury_patterns`, `injury_preceding_behaviors`: split on ` · ` (middle dot, surrounded by spaces). Trim each entry.
- `recovery_modalities`: parse the numbered list in col 11 — extract each item after the digit-and-period prefix.

**Excluded columns:**
- `Sports It Appears In` (col 3) — replaced by `layer0.sport_discipline_bridge`

**Notes:**
- Both raw text AND parsed values are stored. Prompts can use either. The text is the safety net.
- `evidence_quality_text` is stored for builder reference and audit tooling. Not injected into any prompt payload.

---

### 4.4 `layer0.sport_discipline_map` (from 0A Sheet 3 — "Sport × Discipline Map")

One row per sport × discipline pairing. Sport-specific context layered on universal discipline facts.

```sql
CREATE TABLE layer0.sport_discipline_map (
  id                          SERIAL PRIMARY KEY,
  sport_name                  TEXT NOT NULL,           -- FK-style to layer0.sports
  discipline_id               TEXT NOT NULL,           -- FK-style to layer0.disciplines
  discipline_name             TEXT NOT NULL,           -- denormalized for query convenience
  applicability               TEXT NOT NULL,           -- "INCLUDED" / other; col 3
  role                        TEXT NOT NULL,           -- "Primary" / "Secondary" / "Minor" / "Technical"
  race_time_pct_text          TEXT,                    -- col 5 raw, e.g. "15–25%" or "30%"
  race_time_pct_low           NUMERIC,                 -- parsed
  race_time_pct_high          NUMERIC,                 -- parsed; same as low if single value
  sport_specific_context      TEXT,                    -- col 6 — highest-value field for prompts
  b2b_pairing_rule_text       TEXT,                    -- col 7 raw; consumed into discipline_pairing
  phase_load_text             TEXT,                    -- col 8 raw, e.g. "Base: 12–15% / Build: ..."

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_id, etl_version)
);
```

**ETL parsing rules:**
- `race_time_pct_low/_high`: regex `(\d+)(?:[–-](\d+))?%` on `race_time_pct_text`. Single value → low=high. Missing → both NULL.
- `phase_load_text` is stored as raw text only. The structured per-phase percentages with low/high bands live in `layer0.phase_load_allocation` (Sheet 5), which is the canonical structured source. Sheet 3 col 8 is narrative redundancy, kept for inspection.

**Excluded columns:**
- `Applicability` rows where value ≠ "INCLUDED" — load as-is; query layer filters to `applicability = 'INCLUDED'`.

**Notes:**
- `b2b_pairing_rule_text` stays on this table for traceability. The ETL also parses it into `layer0.discipline_pairing` rows for D-018+ where Sheet 4 doesn't cover (see §4.6).

---

### 4.5 `layer0.phase_load_allocation` (from 0A Sheet 5 — "Phase Load Allocation") — STRUCTURE CHANGED FROM v1

One row per sport × discipline. Holds phase load **bands** (low/high per phase) and audit notes.

```sql
CREATE TABLE layer0.phase_load_allocation (
  id                  SERIAL PRIMARY KEY,
  sport_name          TEXT NOT NULL,
  discipline_id       TEXT,                            -- nullable for accessory rows like Strength/Mobility
  discipline_name     TEXT NOT NULL,                   -- e.g. "Trail Running" or "Strength"
  role                TEXT NOT NULL,                   -- "Primary" / "Secondary" / "Minor" / "Accessory" / "Foundation" — and "(*Conditional)" suffix preserved
  base_pct_low        NUMERIC,
  base_pct_high       NUMERIC,
  build_pct_low       NUMERIC,
  build_pct_high      NUMERIC,
  peak_pct_low        NUMERIC,
  peak_pct_high       NUMERIC,
  taper_pct_low       NUMERIC,
  taper_pct_high      NUMERIC,
  notes_conditions    TEXT,                            -- col 12 — includes audit notes

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_name, etl_version)
);
```

**Why this changed:** v1 spec assumed single percentage per phase. v6 actually stores bands (e.g., Trail Running BASE: 12–15%) which are essential for prompt generation — the band represents legitimate variability and the prompt selects within it based on athlete profile. Single-value collapse loses this signal.

**ETL parsing rules:**
- All 8 percentage columns are read directly as numbers. Empty → NULL.
- `discipline_id`: lookup against `layer0.disciplines` by `discipline_name`. NULL for accessory rows (`Strength`, `Mobility`, `Weekly Total Target`).
- `role`: preserve full string including `(*Conditional)` suffix where present.
- `notes_conditions`: full text from col 12. Includes `[AUDIT 2026-05-06]` blocks, conditional flags, and any explanatory notes. Do NOT strip or restructure.

**Special row: `Weekly Total Target`** — every sport has a "Weekly Total Target" summary row at the bottom of its sport block. This is the per-phase weekly hour target band. Schema accommodates it but the role differs from disciplines. Query layer should treat it specially (it's the target ceiling, not a discipline allocation).

---

### 4.6 `layer0.discipline_pairing` (from 0A Sheet 4 + Sheet 3 col 7 fallback)

One row per discipline pair. Authoritative source for same-day training pairing decisions.

```sql
CREATE TABLE layer0.discipline_pairing (
  id                  SERIAL PRIMARY KEY,
  discipline_id_a     TEXT NOT NULL,                   -- "FROM" discipline
  discipline_id_b     TEXT NOT NULL,                   -- "TO" discipline
  pairing_rating      TEXT NOT NULL,                   -- PREFERRED / ACCEPTABLE / AVOID / IMPRACTICAL / N/A
  rationale           TEXT,
  source              TEXT NOT NULL,                   -- 'matrix' (Sheet 4) or 'b2b_rule' (Sheet 3 col 7)

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (discipline_id_a, discipline_id_b, etl_version)
);
```

**ETL logic:**

1. **Sheet 4 matrix** is the primary source. Read rows R10 (header) through R27 (last discipline row). Columns 1–17 correspond to disciplines D-001 through D-017. Each cell contains a rating value (PREFERRED / ACCEPTABLE / AVOID / IMPRACTICAL / N/A). For each non-empty cell at (row_i, col_j), insert one row with `discipline_id_a = R{row_i}.D-id`, `discipline_id_b = C{col_j}.D-id`, `pairing_rating = cell_value`, `source = 'matrix'`. Stop at R27 — rows R29+ are commentary, not data.

2. **Sheet 4 rationale rows (R29–R37)** contain narrative context for select pairings ("Any Paddle → Climbing", etc.). Parse into a separate optional column `rationale` if a matching pair exists. If no exact discipline-pair match is identifiable, store as commentary (skip — these are mostly multi-pair generalizations).

3. **Sheet 3 col 7 fallback** for pairs not in the matrix: iterate every Sheet 3 row, parse the multi-line `b2b_pairing_rule_text`. Each line is `→ {discipline_name}: {RATING}` or `→ {discipline_name}: {RATING} ({rationale})`. For each parsed entry, look up the destination discipline_id by name. Insert row with `discipline_id_a = source_row.discipline_id`, `discipline_id_b = parsed_destination_id`, `pairing_rating = parsed_rating`, `rationale = parsed_rationale_or_NULL`, `source = 'b2b_rule'`. Skip if `(discipline_id_a, discipline_id_b)` already exists with `source = 'matrix'` — matrix wins.

**Status:** Gap remains for D-018 through D-031 in Sheet 4. Fallback logic is required. Open Item #3.

---

### 4.7 `layer0.team_formats` (from 0A Sheet 6 — "Team Format Cross-Reference")

One row per sport. Note: header is on **R3** (R1–R2 are banner/key text — skip).

```sql
CREATE TABLE layer0.team_formats (
  id                              SERIAL PRIMARY KEY,
  sport_name                      TEXT NOT NULL,
  formats_available               TEXT,                -- col 1 — multi-line list of available formats
  team_format_types               TEXT,                -- col 2 — paradigm code(s): UNIFIED_TEAM / RELAY / DOUBLES / AGGREGATE
  unified_team_description        TEXT,                -- col 3
  relay_specialist_description    TEXT,                -- col 4
  training_implication_unified    TEXT,                -- col 5
  training_implication_relay      TEXT,                -- col 6
  key_distinctions_notes          TEXT,                -- col 7

  -- versioning
  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,

  UNIQUE (sport_name, etl_version)
);
```

**ETL parsing rules:**
- Skip rows R1, R2 (banner + format key). Header on R3. Data begins at R4 — but R4 itself may be a paradigm separator row ("PARADIGM 1 — UNIFIED TEAM..."). Skip rows where `sport_name` cell starts with "PARADIGM" or "FORMAT KEY" or "TRAINING IMPLICATION" prefix. Only ingest rows with a valid sport name in col 0.
- `team_format_types`: may be multiple paradigm codes (e.g., "UNIFIED_TEAM, RELAY"). Store as comma-separated text; downstream consumers split if needed.

---

### 4.8 `layer0.cross_sport_properties` (from 0A Sheet 8 — "Cross-Sport Properties") — NEW

One row per cross-sport comparative property. Currently 1 row (LIT_RATIO_001); schema accommodates additions without re-spec.

```sql
CREATE TABLE layer0.cross_sport_properties (
  id                  SERIAL PRIMARY KEY,
  property_id         TEXT NOT NULL,                   -- e.g. "LIT_RATIO_001"
  property_name       TEXT NOT NULL,
  description         TEXT,
  scope               TEXT,                            -- e.g. "Running family"
  ranking_text        TEXT,                            -- "high to low" comparative ordering text
  estimated_values    TEXT,                            -- per-sport estimates as text (e.g. "UltraR ~85-90% | ...")
  source_evidence     TEXT,                            -- col 6+ may contain source citations
  notes               TEXT,                            -- col 7+

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (property_id, etl_version)
);
```

**ETL parsing rules:**
- Read R2 onwards. Skip rows where `property_id` is empty or starts with `EXTENSION NOTES:` (those are commentary at R4–R7).
- All fields stored as raw text. Parsing per-sport values into structured form is deferred until a downstream consumer needs it.

---

### 4.9 `layer0.sport_discipline_bridge` (generated at ETL time, derived from Sheet 3)

Derived bridge. Maps framework sport names to exercise database sport vocabulary.

```sql
CREATE TABLE layer0.sport_discipline_bridge (
  id                          SERIAL PRIMARY KEY,
  framework_sport             TEXT NOT NULL,           -- e.g. "Adventure Racing"
  discipline_id               TEXT NOT NULL,           -- e.g. "D-001"
  discipline_name             TEXT NOT NULL,           -- e.g. "Trail Running"
  exercise_db_sport           TEXT NOT NULL,           -- 0B sport vocabulary
  role                        TEXT NOT NULL,
  default_race_time_pct_low   NUMERIC,
  default_race_time_pct_high  NUMERIC,

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (framework_sport, discipline_id, etl_version)
);
```

**ETL logic:** Generated by reading Sheet 3 (`layer0.sport_discipline_map`). One bridge row per `(sport_name, discipline_id)` where `applicability = 'INCLUDED'`. The `exercise_db_sport` field must be confirmed against the Sport-Exercise Map vocabulary in 0B — vocabulary alignment is a one-time human verification (Open Item #5).

---

### 4.10 `layer0.exercises` (from 0B Exercise Master — header on R2)

One row per exercise.

```sql
CREATE TABLE layer0.exercises (
  id                          SERIAL PRIMARY KEY,
  exercise_id                 TEXT NOT NULL,           -- EX001–EX247, permanent key
  exercise_name               TEXT NOT NULL,
  exercise_type               TEXT NOT NULL,           -- e.g. "Strength", "Conditioning", "Mobility"
  movement_patterns           TEXT[],                  -- parsed from comma-separated col 3
  primary_muscles             TEXT[],                  -- col 4 split on ", "
  secondary_muscles           TEXT[],                  -- col 5 split on ", "
  equipment_required          TEXT[],                  -- col 6 split on ", "
  injury_flags_text           TEXT,                    -- col 8 free text — coaching explanations
  contraindicated_parts       TEXT[],                  -- col 12 split on ", " — programmatic injury filter
  equipment_substitutes       JSONB,                   -- {standard: [...], improvised: [...]} split on 🏠 prefix
  physical_proxies            JSONB,                   -- [{exercise_id, exercise_name}, ...]
  progression_exercise_id     TEXT,                    -- single EX ID, nullable; col 13
  progression_exercise_name   TEXT,
  regression_exercise_id      TEXT,                    -- single EX ID, nullable; col 14
  regression_exercise_name    TEXT,
  sport_count                 INTEGER,                 -- col 15
  coaching_cues               TEXT,                    -- col 9 — stored, NOT injected into plan generation prompts

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (exercise_id, etl_version)
);
```

**ETL parsing rules:**
- Header on R2. Data from R3 onward.
- `equipment_substitutes` (col 10): split on ";" then on each entry test for 🏠 prefix:
  - Without 🏠 → `equipment_substitutes.standard[]`
  - With 🏠 → `equipment_substitutes.improvised[]` (strip the prefix and trim)
- `physical_proxies` (col 11): raw format `EX117 — Loaded Step-Down (Eccentric Box); EX020 — Nordic Hamstring Curl`. Split on `";"`, then split each on ` — ` to extract `{exercise_id, exercise_name}`.
- `progression_exercise_*` and `regression_exercise_*` (cols 13, 14): single `EX### — Name` cell, parse same way.
- `equipment_required`: apply vocabulary cleanup transforms from `vocabulary_transforms.py` (see §3.1) — rename / split / rollup per Vocab Audit Section 5 before storing.
- `contraindicated_parts` (col 12): split on ", " then trim. Each entry should match a canonical body part from `layer0.body_parts.canonical_name`. ETL warns on mismatches (don't fail — log and continue).

**Excluded columns:**
- `Novelty` (col 7) — excluded entirely; no athlete preference signal to act on
- `Notes / Coaching Cues` (col 9) — stored as `coaching_cues` but excluded from plan generation prompt payloads. Surfaced per-exercise in app UI via separate lightweight query.

---

### 4.11 `layer0.sport_exercise_map` (from 0B Sport-Exercise Map — header on R2)

One row per exercise × sport pairing.

```sql
CREATE TABLE layer0.sport_exercise_map (
  id                  SERIAL PRIMARY KEY,
  exercise_id         TEXT NOT NULL,                   -- FK-style to layer0.exercises
  exercise_name       TEXT NOT NULL,                   -- denormalized
  exercise_type       TEXT NOT NULL,                   -- denormalized
  sport_name          TEXT NOT NULL,                   -- 0B sport vocabulary
  sport_relevance_note TEXT NOT NULL,                  -- highest-value field — mechanism of transfer
  priority            TEXT NOT NULL,                   -- Critical / High / Medium / Low

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (exercise_id, sport_name, etl_version)
);
```

ETL: header on R2, data from R3.

---

### 4.12 Vocabulary tables (from 0C `Vocabulary_Audit_v2.md`) — NEW

Five tables for canonical vocabularies.

#### 4.12.1 `layer0.body_parts`

```sql
CREATE TABLE layer0.body_parts (
  id                  SERIAL PRIMARY KEY,
  canonical_name      TEXT NOT NULL,                   -- e.g. "Knee", "Achilles", "IT band"
  body_region         TEXT NOT NULL,                   -- "Head/Neck", "Shoulder", "Arm", "Back", "Hip", "Upper leg", "Knee", "Lower leg", "Foot/Ankle", "Trunk"
  source_origin       TEXT,                            -- "proposed", "col 13", "both" (audit traceability)
  notes               TEXT,

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (canonical_name, etl_version)
);
```

Source: Vocab Audit Section 1, ~50 entries across 10 body regions.

#### 4.12.2 `layer0.health_condition_categories`

```sql
CREATE TABLE layer0.health_condition_categories (
  id                  SERIAL PRIMARY KEY,
  category_name       TEXT NOT NULL,                   -- system category enum (21 values)
  description         TEXT,

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (category_name, etl_version)
);
```

Source: Vocab Audit Section 2.2, 21 categories. The Health Condition Record substructure (§2.1) defines the runtime record schema (athlete-specific, Layer 1) — not loaded as Layer 0.

#### 4.12.3 `layer0.equipment_items`

```sql
CREATE TABLE layer0.equipment_items (
  id                  SERIAL PRIMARY KEY,
  canonical_name      TEXT NOT NULL,                   -- e.g. "Barbell", "Adjustable bench", "Kayak"
  equipment_category  TEXT NOT NULL,                   -- e.g. "Barbells & Bars", "Machines — Lower Body"
  is_universal        BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE for assumed-universal items (Wall, Doorway, Floor, etc.)
  notes               TEXT,

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (canonical_name, etl_version)
);
```

Source: Vocab Audit Section 3, ~143 items across 17 categories. Mark "Assumed Universal" entries with `is_universal = TRUE`.

#### 4.12.4 `layer0.terrain_types`

```sql
CREATE TABLE layer0.terrain_types (
  id                  SERIAL PRIMARY KEY,
  canonical_name      TEXT NOT NULL,                   -- e.g. "Singletrack", "Tarmac road", "Steep mountain trail"
  notes               TEXT,

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (canonical_name, etl_version)
);
```

Source: Vocab Audit Section 3 (subsection "Terrain") — 15 entries. Kept separate from `equipment_items` per the audit decision.

#### 4.12.5 `layer0.sport_specific_gear_toggles`

```sql
CREATE TABLE layer0.sport_specific_gear_toggles (
  id                  SERIAL PRIMARY KEY,
  toggle_name         TEXT NOT NULL,                   -- e.g. "Climbing kit", "Classic XC ski setup"
  display_label       TEXT,                            -- athlete-facing label
  description         TEXT,                            -- what the toggle includes
  paired_equipment_categories TEXT[],                  -- for cross-reference if needed

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (toggle_name, etl_version)
);
```

Source: Vocab Audit Section 4.1, the 12 canonical toggles.

---

## 5. Query layer specification

The query layer sits between the database and the prompts. It accepts structured parameters, runs filtered queries, and returns a JSON payload the prompt consumes. The LLM never writes SQL.

### 5.1 Input parameters

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

### 5.2 Query logic

**Step 1 — Sport context.** Pull from `layer0.sports` where `sport_name = framework_sport`.

**Step 2 — Discipline context.**
- Resolve disciplines via `layer0.sport_discipline_bridge` where `framework_sport` matches.
- Pull matching rows from `layer0.disciplines` and `layer0.sport_discipline_map`.
- Pull `layer0.phase_load_allocation` rows for the sport + discipline set.
- Select age-adjusted ramp based on `athlete_age`:
  - `< 40` → standard ramp (none of the age fields apply; use `ramp_text` heuristic or default 10%/week)
  - `40–44` → `age_ramp_40_44_pct` (NULL → fall back to standard)
  - `45–54` → `age_ramp_45_54_pct`
  - `55+` → `age_ramp_55_plus_pct`
- For phase load: select `{phase}_pct_low` and `{phase}_pct_high` for the requested `training_phase`. Both are returned to the prompt — the prompt selects within the band.

**Step 3 — Pairing rules.** Pull `layer0.discipline_pairing` for all pairs within the athlete's discipline set. Both directions (a→b and b→a) returned; they may differ.

**Step 4 — Cross-sport properties.** Pull `layer0.cross_sport_properties` where `scope` matches the family of `framework_sport` (e.g., "Running family" applies to Trail/Road/Mountain Running etc.). Used by validator for sanity-checking generated plans against family norms.

**Step 5 — Exercise pool** (only when `include_exercise_pool = true`):
- Get exercise DB sport names from `layer0.sport_discipline_bridge`.
- Pull from `layer0.sport_exercise_map` where `sport_name IN (resolved exercise db sports)`.
- Join to `layer0.exercises` on `exercise_id`.
- **Filter 1 — Equipment.** Include exercise if ANY of `equipment_required[]` matches `equipment_available[]` (canonical-name comparison via `layer0.equipment_items`), OR `equipment_substitutes.standard` contains an available item, OR `equipment_substitutes.improvised` is non-empty.
- **Filter 2 — Injury.** Exclude exercise if ANY element of `contraindicated_parts[]` matches ANY `body_part` in `active_injuries` where `severity = 'Acute'`. For severity `'Recovering'`, flag rather than exclude.
- **Sort.** By priority (Critical → High → Medium → Low), then by `sport_count` descending (cross-sport anchors first).
- **Limit.** `max_exercises` (default 40 for plan generation; 1 for UI detail calls).

### 5.3 Output payload

```json
{
  "sport_context": {
    "sport": "Adventure Racing",
    "planning_flags": {
      "navigation": true,
      "sleep_deprivation": true,
      "pack_carry": true,
      "pack_weight_lbs_low": 25,
      "pack_weight_lbs_high": 35,
      "transitions": true
    },
    "disciplines": [
      {
        "id": "D-001",
        "name": "Trail Running",
        "role": "Primary",
        "race_time_pct_low": 15,
        "race_time_pct_high": 25,
        "sport_specific_context": "...",
        "phase_load": {
          "base_pct_low": 12, "base_pct_high": 15,
          "build_pct_low": 12, "build_pct_high": 15,
          "peak_pct_low": 10, "peak_pct_high": 14,
          "taper_pct_low": 12, "taper_pct_high": 15
        },
        "weekly_ramp_pct": 8,
        "min_base_weeks_low": 4, "min_base_weeks_high": 6,
        "taper_norms": "2-3 weeks, 40-60% volume cut",
        "injury_patterns": ["IT band syndrome", "plantar fasciitis"],
        "pairing_rules": {
          "D-006": {"rating": "PREFERRED", "rationale": "..."},
          "D-007": {"rating": "ACCEPTABLE", "rationale": "..."}
        }
      }
    ],
    "cross_sport_properties": [
      {
        "property_id": "LIT_RATIO_001",
        "property_name": "LIT Ratio — mid-prep",
        "scope": "Running family",
        "ranking_text": "...",
        "estimated_values": "..."
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
      "sport_relevance": "Best single lower body exercise for trail running ...",
      "contraindicated_parts": ["Knee"],
      "injury_flag": null,
      "progression": {"id": "EX089", "name": "..."},
      "regression": {"id": "EX216", "name": "..."},
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
- `excluded` — acute injury; exercise removed from pool entirely (won't appear in payload)
- `flagged` — recovering injury; exercise included with flag

---

## 6. ETL run process

### 6.1 Trigger conditions
- New version of any source file released
- Manual override by admin (e.g., critical data correction)
- Never triggered by user action or plan generation

### 6.2 Run order

Order matters due to derived tables and validation dependencies.

```
PHASE 1 — Vocabularies (no dependencies, load first so other ETLs can validate against them)
  1. layer0.body_parts                       (Vocab Audit §1)
  2. layer0.health_condition_categories      (Vocab Audit §2.2)
  3. layer0.equipment_items                  (Vocab Audit §3)
  4. layer0.terrain_types                    (Vocab Audit §3 terrain subsection)
  5. layer0.sport_specific_gear_toggles      (Vocab Audit §4.1)

PHASE 2 — 0A core
  6. layer0.sports                           (Sheet 1)
  7. layer0.disciplines                      (Sheet 2)
  8. layer0.sport_discipline_map             (Sheet 3)
  9. layer0.discipline_pairing               (Sheet 4 primary, Sheet 3 col 7 fallback)
  10. layer0.phase_load_allocation           (Sheet 5)
  11. layer0.team_formats                    (Sheet 6, header on R3)
  12. layer0.cross_sport_properties          (Sheet 8)

PHASE 3 — Bridge and 0B
  13. layer0.sport_discipline_bridge         (derived from Sheet 3 — runs after step 8)
  14. layer0.exercises                       (Exercise Master, header on R2; apply vocab transforms)
  15. layer0.sport_exercise_map              (Sport-Exercise Map, header on R2)
```

### 6.3 Versioning on each run
1. Read current `etl_version` from most recent run for each source family.
2. Assign new version strings: `0A-vN`, `0B-vN`, `0C-vN` (independent versioning per source).
3. Insert all new rows with new `etl_version` and current timestamp.
4. Set `superseded_at = NOW()` on all prior rows where `superseded_at IS NULL` AND `etl_version` is the prior version of the same source family.
5. All queries filter `WHERE superseded_at IS NULL` — no migration needed, rollback is trivial (reset `superseded_at = NULL` on prior version, drop new version).

### 6.4 Validation passes (run after each phase)

After Phase 1: vocabularies loaded. No validation needed.

After Phase 2 step 10 (`phase_load_allocation`): run sum-to-100 check per sport per phase using the audit logic from `Phase_Load_Allocation_Audit_Log.md`. Adjusted stack (conditionals zeroed, one paddle discipline) must reach 100% high-band on all phases. Log warnings on any sport that fails; do NOT abort ETL — sports framework owns this validation, ETL just surfaces.

After Phase 3 step 14 (`exercises`): for each exercise's `contraindicated_parts[]`, verify each entry exists in `layer0.body_parts.canonical_name`. Log mismatches as warnings.

After Phase 3 step 15 (`sport_exercise_map`): for each `sport_name`, verify it exists in `layer0.sport_discipline_bridge.exercise_db_sport`. Log mismatches as warnings (resolves Open Item #5).

---

## 7. What is NOT ETL'd and why

| Data | Source | Decision | Reason |
|------|--------|----------|--------|
| Sport Summary (Sheet 3, exercise DB) | 0B | Excluded | Human navigation only; LLM queries Sport-Exercise Map directly |
| Legend (Sheet 4, exercise DB) | 0B | Excluded | Human reference only; vocabulary defined in schema |
| Sheet 7 (Sports Framework) | 0A | Excluded | Layer 1 territory — athlete onboarding schema |
| Vocab Audit §5 (cleanup tasks) | 0C | Applied as transforms | Renames/rollups applied during ETL via `vocabulary_transforms.py`, not stored as data |
| Vocab Audit §6–§8 (commentary) | 0C | Excluded | UX flow notes, spec changes, fallback logic — informational, not data |
| Governing Bodies (Sheet 1 col 1) | 0A | Tabled | Future FAQ feature — Open Item #1 |
| Race / Event Formats (Sheet 1 col 2) | 0A | Tabled | Review after Layer 1 design — Open Item #2 |
| Sports It Appears In (Sheet 2 col 3) | 0A | Eliminated | Replaced by `sport_discipline_bridge` |
| Novelty (Exercise Master col 7) | 0B | Eliminated | No athlete preference signal to act on |
| Coaching Cues (Exercise Master col 9) | 0B | Stored, not injected into plan generation prompts | Surfaced per-exercise in UI via separate query |
| Evidence Quality (Discipline Library col 12) | 0A | Stored, not injected | Builder reference only |
| Health Condition Record substructure (Vocab Audit §2.1) | 0C | Excluded | Athlete-specific record schema, lives in Layer 1 |
| AR Schema 2.2 cleanup tasks (Vocab Audit §5) | 0C | Excluded | Tasks for the Layer 1 onboarding spec, not Layer 0 |

---

## 8. Open items

| # | Item | Action required | Owner |
|---|------|-----------------|-------|
| 1 | Governing Bodies (Sheet 1) | Table for future athlete FAQ feature; revisit when FAQ is scoped | App team |
| 2 | Race / Event Formats (Sheet 1) | Review after Layer 1 prompt design; confirm if any prompt uses this field | Cross-chat review |
| 3 | Discipline Pairing Matrix gap (D-018–D-031) | Sheet 4 still covers D-001–D-017 only. ETL fallback logic to Sheet 3 col 7 is required and specified in §4.6. Long-term fix: extend Sheet 4 matrix | Other chat / app team |
| 4 | Vertical Gain field in Layer 1 | Ensure athlete onboarding captures current vertical gain capacity | Layer 1 design |
| 5 | exercise_db_sport vocabulary alignment | ETL validation pass in §6.4 surfaces mismatches; manual reconciliation expected on first run | ETL build |
| 6 | Sheet 3 col 7 deprecation | Once Sheet 4 covers D-018+, remove col 7 from ETL source list and note deprecation | Other chat / app team |
| 7 | Cross-Sport Properties extension | Sheet 8 has 1 substantive row; future properties (ECCENTRIC_LOAD, STRENGTH_PRIMACY, TECHNICAL_TERRAIN_DIFFICULTY, NAVIGATION_DEMAND) noted in sheet for future addition | Other chat |
| 8 | Vocabulary cleanup transforms | `vocabulary_transforms.py` module needs to be built containing the Vocab Audit §5 rename/rollup rules. ETL step 14 depends on it | ETL build |

---

## 9. Downstream prompt consumption reference

Quick reference: what Layer 0 context each layer receives and from which tables.

| Layer | Receives from Layer 0 | Tables queried |
|-------|----------------------|----------------|
| 2A (Discipline Classifier) | Sport planning flags, discipline list with roles + race time bands | sports, sport_discipline_map, sport_discipline_bridge |
| 2B (Terrain Classifier) | Terrain vocabulary | terrain_types |
| 2C (Equipment Mapper) | Equipment vocabulary, exercise pool filtered by discipline only (no equipment filter) | equipment_items, sport_specific_gear_toggles, sport_exercise_map, exercises |
| 2D (Injury Risk Profile) | Injury patterns + preceding behaviors per discipline; body part vocabulary | disciplines, body_parts |
| 2E (Nutrition Baseline) | None directly | — |
| 3D (Injury Analysis) | Contraindicated parts and injury flags per exercise; body part vocabulary | exercises, body_parts |
| 4 (Plan Generation) | Full sport context + exercise pool (equipment + injury filtered) + phase load bands | All tables via query layer |
| 4.5 (Validator) | Sport rule sets: ramp rates, phase durations, pairing rules, taper norms, cross-sport properties | sports, disciplines, discipline_pairing, phase_load_allocation, cross_sport_properties |
| 5A (Nutrition) | None — operates on plan output + athlete data | — |
| 5B (Supplements) | None — operates on plan output + athlete data | — |
| 5C (Clothing) | None — operates on weather + athlete history | — |
