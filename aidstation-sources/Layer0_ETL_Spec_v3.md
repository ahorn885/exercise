# Layer 0 ETL Specification — v3

**Version:** 3.0
**Status:** Drafted; pending xlsx populate (Sports_Framework v9 → v10) and ETL re-run
**Supersedes:** `Layer0_ETL_Spec_v2.md`
**Sources:**
- `Sports_Framework_v10.xlsx` (0A) — was v6 in spec v2; restructured + populated since
- `AR_Exercise_Database_v17.xlsx` (0B) — unchanged
- `Vocabulary_Audit_v2.md` (0C) — unchanged

---

## What changed in v3 vs v2

1. **Source bump v6 → v10** for Sports Framework. v10 includes:
   - **D-008 split** into D-008a (Kayaking — Flat-water) and D-008b (Kayaking — Whitewater) in Discipline Library, Sport × Discipline Map, Discipline Pairing Matrix, Phase Load Allocation, Athlete Profile Data Points
   - **D-030 Marathon Paddling removed** — folded into D-008a + D-009 with race-format notes on Canoe / Kayak Marathon sport rows
   - **D-031 OW Distance Swimming removed** — folded into D-004 with marathon-volume + cold-tolerance notes on OW Marathon Swimming sport rows
   - **Real D-008b values** in pairing matrix (whitewater-specific) and AR phase load (BASE 0% / BUILD 1–3% / PEAK 3–5% / TAPER 1–2%, conditional on race specifying whitewater)
   - **Discipline Substitution Map** (NEW sheet) — 91 substitution rows ready for ETL into `layer0.discipline_substitutes`
   - **Discipline Training Gaps** (NEW sheet) — 3 rows for D-018 Swimrun / D-020 Alpine Descent / D-024 Fencing
   - **Sports Index four classification columns** populated: `constituent_movements`, `endurance_profile`, `participation_format`, `multi_discipline`
   - **Phase Load Allocation `default_inclusion` column** populated per row
2. **Two new tables** in `layer0` schema: `discipline_substitutes`, `discipline_training_gaps`.
3. **Two new candidate columns** under contract preview (`stimulus_components` on disciplines; `substitute_covers` on substitutes) — see §4.3 and §4.X for current state.
4. **`layer0.sports` schema additions:** four classification columns (`constituent_movements`, `endurance_profile`, `participation_format`, `multi_discipline`).
5. **`layer0.phase_load_allocation` schema addition:** `default_inclusion` column.
6. **`layer0.exercises.contraindicated_conditions`** confirmed in schema. Derived at ETL time from systemic tokens in `contraindicated_parts` via `split_contraindicated_string()` (per `Post_ETL_Onboarding_Handoff.md` Round 2). Source xlsx has not changed; the derivation is the load mechanism.
7. **§5 Query Layer fully specified.** v2 had a working draft of the input/output payload but no formal interface decisions. v3 locks five structural decisions (typed per-consumer functions, version pinning, cache-friendly design, three filter additions, phase load shape) and specifies one function per downstream consumer (eleven total).
8. **Sheet 5 transforms added to pre-ETL prep:**
   - **Weekly Total Target free-text parsing** into structured `{base, build, peak, taper}` hour bands
   - **Notes column split** into `prescription_note` (athlete-facing short text) and `audit_log` (sources, citations, math, internal flags)

---

## 1. Purpose

Define the extraction, transformation, and loading process for Layer 0 reference data — the platform-level sport rule sets, exercise library, and canonical vocabularies that feed every downstream prompt. This data is static and versioned. It does not change per user. It changes only when the app team releases an updated version of any source.

Layer 0 data is **not generated at runtime.** It is extracted once (or on each version update), stored in PostgreSQL, and injected selectively into prompts by a query layer that filters by sport, discipline, equipment, injury, and health condition.

---

## 2. Source files

| File | Layer | Sheets / sections used | Excluded |
|------|-------|---|---|
| `Sports_Framework_v10.xlsx` | 0A | Sheets 1, 2, 3, 4, 5, 6, 8 + Discipline Substitution Map + Discipline Training Gaps | Sheet 7 (Layer 1 territory — athlete profile data points) |
| `AR_Exercise_Database_v17.xlsx` | 0B | Exercise Master, Sport-Exercise Map | Sport Summary (human nav only), Legend (human reference only) |
| `Vocabulary_Audit_v2.md` | 0C | Sections 1, 2, 3, 4 | Section 5 (cleanup tasks — applied as transforms, not loaded as data); Sections 6–8 (commentary) |

---

## 3. Pre-ETL data preparation

Before running the ETL, four preparation passes must occur.

### 3.1 Vocabulary cleanup against exercise DB (from Vocab Audit Section 5)

`Vocabulary_Audit_v2.md` Section 5 enumerates rename and rollup tasks for the AR Exercise DB col 7 (Equipment) — bringing exercise-DB equipment strings into alignment with the canonical equipment vocabulary in Section 3 of the audit. Examples: "Kayak / Packraft" → split into atomic items; sub-component sport-specific items (rope, harness, belay device) → rolled up to single category tokens (e.g., `Climbing kit`).

Implementation: applied as ETL-time transforms in a `vocabulary_transforms.py` module. Source xlsx untouched.

### 3.2 Discipline Pairing Matrix gap fallback

Sheet 4 covers only D-001 through D-017 (the 17 AR-relevant disciplines). For D-018 through D-031+ (sports beyond AR — Triathlon, Mountain Running, etc.), pairing data is reconstructed from Sheet 3 col 7 (`B2B Pairing Rule`). Each `B2B Pairing Rule` cell contains text like `→ Hiking: PREFERRED \n → XC Cycling: PREFERRED (standard brick) \n → Packraft/Kayak: ACCEPTABLE`. Parse each line into a per-pairing row. ETL logic in §4.6.

### 3.3 Weekly Total Target free-text parsing (Sheet 5C)

Each sport in Phase Load Allocation has a `WEEKLY TOTAL TARGET` row. The `Notes / Conditions` cell contains free text like:
```
Base: 8–10 hrs / Build: 10–14 hrs / Peak: 14–18 hrs / Taper: 6–9 hrs
```

**Parser rule:** regex `(\w+):\s*(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)\s*hrs?` against the text. Each match produces `(phase_label, hours_low, hours_high)`. Map phase_label to canonical phase name (`Base`/`Build`/`Peak`/`Taper`). Output: structured `{base: {low, high}, build: {low, high}, peak: {low, high}, taper: {low, high}}`.

**Fallback:** if regex match count < 4 (any phase missing), fail with structured warning. Original text retained in `weekly_target_text` column as fallback for query layer.

### 3.4 Notes column split (Sheet 5D)

The `Notes / Conditions` column on Phase Load Allocation rows currently mixes athlete-facing prescription cues with internal audit metadata (sources, citations, math, flags like `[TAPER feasibility patch — pending AR audit]`).

**Parser rule:** Split each Notes cell into two outputs:
- **`prescription_note`** — short, athlete-facing. Take the first sentence/clause that doesn't begin with `[`, `Source:`, `Audit:`, `*CONDITIONAL`, or `PENDING`. Cap at ~120 chars.
- **`audit_log`** — everything else. Sources, citations, math, internal flags, conditional markers. Stored verbatim.

**Fallback:** if no prescription_note can be extracted (e.g., Notes is purely metadata), `prescription_note = NULL`. Query layer returns prescription_note by default; consumers can request audit_log on demand.

---

## 4. Target database schema

All Layer 0 tables live in a dedicated `layer0` schema in PostgreSQL. Every table carries version tracking fields. No row is ever overwritten — a new ETL run inserts new rows and sets `superseded_at` on the prior version.

### 4.1 Versioning pattern (applied to every table)

```sql
etl_version    TEXT NOT NULL,        -- e.g. "0A-v10.0", "0B-v17.0", "0C-v2.0"
etl_run_at     TIMESTAMPTZ NOT NULL,
superseded_at  TIMESTAMPTZ           -- NULL = current version
```

Queries always filter `WHERE superseded_at IS NULL` for current data.

---

### 4.2 `layer0.sports` (from 0A Sheet 1 — "Sports Index") — UPDATED

One row per sport. v3 adds four classification columns.

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
  pack_carry_notes            TEXT,
  pack_weight_lbs_low         NUMERIC,                 -- parsed from notes
  pack_weight_lbs_high        NUMERIC,                 -- parsed from notes
  flag_transition_training    BOOLEAN NOT NULL,
  transition_training_notes   TEXT,

  primary_discipline_count    INTEGER,
  secondary_discipline_count  INTEGER,
  status_label                TEXT,

  -- NEW v3: classification columns (replaces single sport_family idea)
  constituent_movements       TEXT[] NOT NULL,         -- multi-value enum
  endurance_profile           TEXT NOT NULL,           -- enum: Pure endurance / Mixed / Technical-dominant
  participation_format        TEXT NOT NULL,           -- enum: Individual / Team / Both
  multi_discipline            BOOLEAN NOT NULL,        -- derived as cardinality(constituent_movements) > 1

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (sport_name, etl_version)
);
```

**ETL parsing rules (v2 carryover):**
- `flag_*`: parse first token of column (before the first ` —` or `\n`). YES → TRUE; NO → FALSE; otherwise warn + default FALSE.
- `*_notes`: full original text including the YES/NO prefix.
- `pack_weight_lbs_low/_high`: regex on `pack_carry_notes` for patterns like `"25–35 lb"` or `"35 lb"`. Single value → low=high. Absent → both NULL.

**ETL parsing rules (v3 NEW):**
- `constituent_movements`: read Sports Index col 13. Split on `;`, trim each token, validate against enum (`running`, `cycling`, `swimming`, `paddling`, `skiing`, `climbing`, `hiking`, `navigation`, `other_skill`). Reject unknown tokens with structured warning.
- `endurance_profile`: read col 14. Validate against enum (`Pure endurance`, `Mixed`, `Technical-dominant`). Reject unknowns.
- `participation_format`: read col 15. Validate against enum (`Individual`, `Team`, `Both`).
- `multi_discipline`: read col 16. If absent, derive as `cardinality(constituent_movements) > 1`. If present, validate against derived value; warn on mismatch (do not fail — Sheet authoritative).

**Excluded columns (carryover from v2):**
- `Governing Bodies` (col 1) — tabled for FAQ feature; Open Item #1
- `Race / Event Formats` (col 2) — tabled pending Layer 1 review; Open Item #2

---

### 4.3 `layer0.disciplines` (from 0A Sheet 2 — "Discipline Library") — UPDATED

One row per discipline. Universal facts — not sport-specific. v3 reflects the D-008 split, D-030/D-031 removal, and adds candidate `stimulus_components` column per contract-preview decision.

```sql
CREATE TABLE layer0.disciplines (
  id                              SERIAL PRIMARY KEY,
  discipline_id                   TEXT NOT NULL,        -- D-001, D-002, D-008a, D-008b, etc.
  discipline_name                 TEXT NOT NULL,
  discipline_category             TEXT,                 -- e.g. "Foot / Running"
  min_base_phase_text             TEXT,                 -- col 4 free text
  weekly_ramp_pct_text            TEXT,                 -- col 5 raw text
  weekly_ramp_pct_low             NUMERIC,              -- parsed
  weekly_ramp_pct_high            NUMERIC,              -- parsed
  age_ramp_40_44_pct              NUMERIC,
  age_ramp_45_54_pct              NUMERIC,
  age_ramp_55_plus_pct            NUMERIC,
  taper_norms_text                TEXT,
  injury_patterns                 TEXT[],
  preceding_behaviors             TEXT[],
  recovery_modalities             TEXT[],
  evidence_quality_text           TEXT,                 -- builder reference, not in prompt payloads

  -- NEW v3 candidate (per contract preview): stimulus decomposition for substitute composition
  stimulus_components             TEXT[],               -- multi-value enum: aerobic_low, aerobic_high, etc.

  -- versioning
  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,

  UNIQUE (discipline_id, etl_version)
);
```

**`stimulus_components` enum (starter set, expandable):**
```
aerobic_low ; aerobic_high ; muscular_endurance_legs ; muscular_endurance_upper ;
pack_carry_load ; vertical_gain ; technical_descent ; technical_handwork ;
grip_strength ; balance_dynamic ; cold_exposure ; fueling_practice
```

**Status of `stimulus_components`:** column is in the schema. Population is deferred to a follow-up step after v10 lands — the contract preview surfaced it as needed for plan-gen multi-substitute composition, but populating ~30 disciplines is a 60–90 min curation job that can run independently. ETL handles NULL gracefully; query layer returns NULL until populated. **See §7 Open Items.**

**D-008 split impact:**
- D-008a — Kayaking — Flat-water. Inherits most of D-008's prior data (touring, distance, K1/K2 race contexts).
- D-008b — Kayaking — Whitewater. New row. Brace, eddy, roll prerequisites; technical descent stimulus.
- D-005a (TT Variant of D-005) precedent confirmed in Discipline Library — sub-ID suffix style is the established convention.

**D-030 / D-031 removed:** rows do not exist in v10. Any consumer referencing these IDs will fail. ETL validation pass logs warning if any sport_discipline_map row references D-030 or D-031.

**Excluded columns (carryover):**
- `Sports It Appears In` (col 3) — replaced by `layer0.sport_discipline_bridge`

---

### 4.4 `layer0.sport_discipline_map` (from 0A Sheet 3 — "Sport × Discipline Map")

One row per sport × discipline pairing. Sport-specific context layered on universal discipline facts. v3 schema unchanged from v2; data reflects D-008 split + D-030/D-031 removal.

```sql
CREATE TABLE layer0.sport_discipline_map (
  id                          SERIAL PRIMARY KEY,
  sport_name                  TEXT NOT NULL,
  discipline_id               TEXT NOT NULL,
  discipline_name             TEXT NOT NULL,
  applicability               TEXT NOT NULL,           -- "INCLUDED" / "EXCLUDED"; col 3
  role                        TEXT NOT NULL,           -- Primary / Secondary / Minor / Technical
  race_time_pct_text          TEXT,                    -- col 5 raw, e.g. "15–25%"
  race_time_pct_low           NUMERIC,
  race_time_pct_high          NUMERIC,
  sport_specific_context      TEXT,                    -- col 6
  b2b_pairing_rule_text       TEXT,                    -- col 7 raw; consumed into discipline_pairing
  phase_load_text             TEXT,                    -- col 8 raw narrative summary

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_id, etl_version)
);
```

**ETL parsing rules:**
- `race_time_pct_low/_high`: regex `(\d+)(?:[–-](\d+))?%` on `race_time_pct_text`. Single value → low=high. Missing → both NULL.
- `phase_load_text` is stored as raw text only. Authoritative structured percentages are in `layer0.phase_load_allocation` (Sheet 5).

**ETL filter:** query layer filters to `applicability = 'INCLUDED'`. EXCLUDED rows loaded for documentation purposes; consumers should not see them by default.

---

### 4.5 `layer0.phase_load_allocation` (from 0A Sheet 5 — "Phase Load Allocation") — UPDATED

One row per sport × discipline. v3 adds `default_inclusion` column and splits Notes into two structured outputs.

```sql
CREATE TABLE layer0.phase_load_allocation (
  id                        SERIAL PRIMARY KEY,
  sport_name                TEXT NOT NULL,
  discipline_id             TEXT NOT NULL,
  discipline_name           TEXT NOT NULL,
  role                      TEXT NOT NULL,
  is_conditional            BOOLEAN NOT NULL,        -- TRUE when row marked *Conditional in Role or *CONDITIONAL in Notes

  phase_base_pct_low        NUMERIC,
  phase_base_pct_high       NUMERIC,
  phase_build_pct_low       NUMERIC,
  phase_build_pct_high      NUMERIC,
  phase_peak_pct_low        NUMERIC,
  phase_peak_pct_high       NUMERIC,
  phase_taper_pct_low       NUMERIC,
  phase_taper_pct_high      NUMERIC,

  vertical_gain_notes       TEXT,                    -- parsed from Notes when sport in {Skimo, Mountain Running, XC Skiing, Fell Running}; null otherwise

  -- v3: Notes split into two outputs (per §3.4)
  prescription_note         TEXT,                    -- athlete-facing short text
  audit_log                 TEXT,                    -- internal: sources, citations, math, conditional markers
  raw_notes                 TEXT,                    -- original Notes cell preserved verbatim as fallback

  -- v3: NEW default_inclusion field (per 5E and Tactical Populate Package §1b)
  default_inclusion         TEXT NOT NULL,           -- enum: included / excluded / prompt_required

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_id, etl_version)
);
```

**ETL row filtering (carryover):**
1. Skip aggregator rows where `discipline_name` contains `WEEKLY TOTAL TARGET`. Their notes are extracted into `layer0.phase_load_weekly_totals` (§4.5.1) instead.
2. Skip rows flagged `PENDING SUB-FORMAT EXPANSION` in notes. (As of v10, none remain — LDC sub-format expansion completed in v5/v8.)
3. Skip rows where applicability flag (joined from Sheet 3) is `EXCLUDED`.

**ETL field derivation:**
- `is_conditional`: TRUE if `Role` contains `(*Conditional)` OR `Notes / Conditions` starts with `*CONDITIONAL`.
- `prescription_note` / `audit_log`: split per §3.4.
- `raw_notes`: full original Notes cell preserved verbatim.
- `default_inclusion`: read directly from new column. Validate against enum (`included`, `excluded`, `prompt_required`).

---

### 4.5.1 `layer0.phase_load_weekly_totals` (NEW v2 carryover, refined v3)

One row per sport per phase. Derived from Sheet 5 `WEEKLY TOTAL TARGET` aggregator rows.

```sql
CREATE TABLE layer0.phase_load_weekly_totals (
  id                  SERIAL PRIMARY KEY,
  sport_name          TEXT NOT NULL,
  phase               TEXT NOT NULL,            -- Base / Build / Peak / Taper
  hours_low           NUMERIC,
  hours_high          NUMERIC,
  weekly_target_text  TEXT,                     -- raw cell preserved as fallback

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (sport_name, phase, etl_version)
);
```

**ETL extraction rule:** for each sport's WEEKLY TOTAL TARGET row, apply parser from §3.3. Emit four rows (one per phase).

---

### 4.6 `layer0.discipline_pairing` (from 0A Sheet 4 + Sheet 3 col 7 fallback)

One row per discipline pair. v3 schema unchanged from v2; data reflects D-008 split (D-008b row + col added with whitewater-specific values per `Phase_Load_Allocation_Handoff_v8.md`).

```sql
CREATE TABLE layer0.discipline_pairing (
  id                  SERIAL PRIMARY KEY,
  discipline_id_a     TEXT NOT NULL,                   -- "FROM" discipline
  discipline_id_b     TEXT NOT NULL,                   -- "TO" discipline
  pairing_rating      TEXT NOT NULL,                   -- PREFERRED / ACCEPTABLE / AVOID / IMPRACTICAL / N/A
  rationale           TEXT,
  source              TEXT NOT NULL,                   -- 'matrix' / 'b2b_rule'

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (discipline_id_a, discipline_id_b, etl_version)
);
```

**ETL logic (carryover from v2):**

1. **Sheet 4 matrix** is primary. Read R10 (header) through R27 (last discipline row, now extended for D-008a/b). Each non-empty cell at (row_i, col_j) → row with `source = 'matrix'`. Stop at R27.
2. **Sheet 4 rationale rows (R29–R37)** narrative for select pairings. Parse into `rationale` if a matching pair exists.
3. **Sheet 3 col 7 fallback** for pairs not in matrix (D-018+). Per existing logic. Skip if `(a, b)` exists with `source = 'matrix'` — matrix wins.

**v3 note on D-008b:** the v8 refinement applied real values to the D-008b row + column in Sheet 4. The "b" suffix added a row + column to the matrix. ETL must read R27 (last existing) PLUS any new rows added for D-008b. Cross-paddle fix R18 C10 (After D-008a → D-008b) was N/A in matrix default; corrected to AVO in v8.

**Status:** matrix gap remains for D-018 through D-031+ (D-030/D-031 removed; effectively D-018 through D-029 with sub-IDs). Fallback logic still required.

---

### 4.7 `layer0.team_formats` (from 0A Sheet 6 — "Team Format Cross-Reference")

Unchanged from v2.

```sql
CREATE TABLE layer0.team_formats (
  id                              SERIAL PRIMARY KEY,
  sport_name                      TEXT NOT NULL,
  formats_available               TEXT,
  team_format_types               TEXT,
  unified_team_description        TEXT,
  relay_specialist_description    TEXT,
  training_implication_unified    TEXT,
  training_implication_relay      TEXT,
  key_distinctions_notes          TEXT,

  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,

  UNIQUE (sport_name, etl_version)
);
```

---

### 4.8 `layer0.cross_sport_properties` (from 0A Sheet 8 — "Cross-Sport Properties")

Unchanged from v2.

```sql
CREATE TABLE layer0.cross_sport_properties (
  id                  SERIAL PRIMARY KEY,
  property_id         TEXT NOT NULL,
  property_name       TEXT NOT NULL,
  description         TEXT,
  scope               TEXT,
  ranking_text        TEXT,
  estimated_values    TEXT,

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (property_id, etl_version)
);
```

---

### 4.9 `layer0.discipline_substitutes` (from 0A Discipline Substitution Map sheet) — NEW v3

One row per (target discipline, substitute discipline) pair. 91 entries in v10. Sport-agnostic for v1.

```sql
CREATE TABLE layer0.discipline_substitutes (
  id                  SERIAL PRIMARY KEY,
  target_id           TEXT NOT NULL,                   -- e.g. D-016
  target_name         TEXT NOT NULL,                   -- denormalized for query convenience
  substitute_id       TEXT NOT NULL,                   -- e.g. D-007
  substitute_name     TEXT NOT NULL,                   -- denormalized
  fidelity            NUMERIC NOT NULL,                -- 0.0 – 1.0
  constraints         TEXT,                            -- free text: what's covered, what's lost
  category            TEXT,                            -- e.g. "Family — vertical foot", "Cross-discipline — equipment shift"

  -- v3 candidate (per contract preview): which target stimuli this substitute claims to cover
  substitute_covers   TEXT[],                          -- subset of target.stimulus_components

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (target_id, substitute_id, etl_version)
);
```

**ETL parsing rules:**
- Direct extraction from Discipline Substitution Map sheet. Schema mirrors sheet columns 1:1.
- Validate `target_id` and `substitute_id` exist in `layer0.disciplines`. Fail row + warn on broken FK.
- Validate `fidelity` ∈ [0.0, 1.0]. Reject row + warn on out-of-range.
- `substitute_covers`: read column if present; else NULL. Validate each element is in target's `stimulus_components` (warning only if `stimulus_components` not yet populated).

**Status of `substitute_covers`:** column is in schema. Population deferred until `stimulus_components` is populated. ~30 min increment beyond existing 91-row curation. **See §7 Open Items.**

**Asymmetric pairings allowed.** A → B at 0.6 and B → A at 0.45 are both legitimate, separate rows.

**Inclusion threshold ~0.3** soft rule. Cross-training fallbacks below 0.3 belong in plan-gen logic, not this table.

---

### 4.10 `layer0.discipline_training_gaps` (from 0A Discipline Training Gaps sheet) — NEW v3

One row per discipline that has no good single substitute. 3 entries in v10.

```sql
CREATE TABLE layer0.discipline_training_gaps (
  id                          SERIAL PRIMARY KEY,
  discipline_id               TEXT NOT NULL,           -- e.g. D-018
  discipline_name             TEXT NOT NULL,
  gap_type                    TEXT NOT NULL,           -- e.g. "no_single_substitute" / "no_off_environment_substitute"
  notes                       TEXT,                    -- free text describing why and what plan-gen should do
  multi_substitute_candidate  BOOLEAN,                 -- TRUE if multi-substitute composition is the documented answer

  -- versioning
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (discipline_id, etl_version)
);
```

**Current entries (v10):**
- D-018 Swimrun — `gap_type = 'no_single_substitute'`; `multi_substitute_candidate = TRUE`. Composing D-001 Trail Running + D-004 Swimming approximates.
- D-020 Alpine Descent — `gap_type = 'no_off_environment_substitute'`; `multi_substitute_candidate = FALSE`. No off-snow training transfers meaningfully to downhill ski skill.
- D-024 Épée Fencing — `gap_type = 'no_off_environment_substitute'`; `multi_substitute_candidate = FALSE`. Requires fencing coach + opponent.

**Plan-gen contract:** when athlete's discipline list includes any discipline with a row in this table, plan-gen surfaces a structured warning to the athlete. If `multi_substitute_candidate = TRUE`, plan-gen attempts composition and includes a note that the prescription is approximate.

---

### 4.11 `layer0.sport_discipline_bridge` (derived from Sheet 3 + alias map)

Unchanged from v2.

```sql
CREATE TABLE layer0.sport_discipline_bridge (
  id                  SERIAL PRIMARY KEY,
  framework_sport     TEXT NOT NULL,
  discipline_id       TEXT NOT NULL,
  exercise_db_sport   TEXT NOT NULL,                   -- maps to 0B vocabulary

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (framework_sport, discipline_id, exercise_db_sport, etl_version)
);
```

Derivation: Sheet 3 sport × discipline pairings + `sport_name_aliases.py` map (per `Post_ETL_Onboarding_Handoff.md` Round 1). The alias table `layer0.sport_name_aliases` is its own loaded source (see ETL phase 1).

---

### 4.12 `layer0.exercises` (from 0B Exercise Master) — UPDATED schema confirmation

One row per exercise. Schema unchanged from v2; v3 confirms `contraindicated_conditions` is in the deployed schema.

```sql
CREATE TABLE layer0.exercises (
  id                          SERIAL PRIMARY KEY,
  exercise_id                 TEXT NOT NULL UNIQUE,
  exercise_name               TEXT NOT NULL,
  exercise_type               TEXT NOT NULL,
  movement_patterns           TEXT[],
  equipment                   TEXT[],
  novelty_text                TEXT,                    -- excluded from prompt payloads
  injury_flag                 TEXT,
  coaching_cues               TEXT,                    -- excluded from plan-gen prompts; surfaced per-exercise in UI
  equipment_substitutes_standard    TEXT[],            -- entries without 🏠
  equipment_substitutes_improvised  TEXT[],            -- entries with 🏠 (prefix stripped)
  contraindicated_parts       TEXT[],                  -- body parts only; systemic tokens stripped during transform
  contraindicated_conditions  TEXT[],                  -- v3 confirmed: derived from systemic tokens during ETL
  progression_id              TEXT,
  regression_id               TEXT,
  physical_proxies            JSONB,                   -- [{id, name}, ...]

  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (exercise_id, etl_version)
);
```

**Critical ETL transform (v2 carryover, v3 confirmation):**

`split_contraindicated_string()` parses the raw col 13 cell:
- Body parts → `contraindicated_parts[]`
- Systemic tokens (Cardiac, Lungs/Respiratory, GI, Skin, Core Temperature/Thermoregulation, Cognitive/Neurological) → `contraindicated_conditions[]`
- Excluded tokens (Saddle, Goggle, Blister, Grip) → dropped
- "Spine" → "Spine (general)" (rename rule)

Source xlsx is NOT modified. Derivation happens at ETL time. The xlsx may show systemic tokens in col 13 alongside body parts — this is expected and correct.

---

### 4.13 `layer0.sport_exercise_map` (from 0B Sport-Exercise Map)

Unchanged from v2.

```sql
CREATE TABLE layer0.sport_exercise_map (
  id                    SERIAL PRIMARY KEY,
  exercise_id           TEXT NOT NULL,
  exercise_name         TEXT NOT NULL,
  exercise_type         TEXT NOT NULL,
  sport_name            TEXT NOT NULL,
  sport_relevance_note  TEXT NOT NULL,
  priority              TEXT NOT NULL,

  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (exercise_id, sport_name, etl_version)
);
```

---

### 4.14 Vocabulary tables (from 0C — Vocabulary_Audit_v2.md)

Unchanged from v2. Five tables: `layer0.body_parts`, `layer0.health_condition_categories`, `layer0.equipment_items`, `layer0.terrain_types`, `layer0.sport_specific_gear_toggles`. See v2 spec §4.12 for schema.

---

## 5. Query layer specification

The query layer sits between Postgres and the prompts. It accepts structured parameters, runs filtered queries, and returns typed JSON payloads the prompt consumes. The LLM never writes SQL.

### 5.1 Architecture — five locked decisions

#### Decision 1: Interface shape — per-consumer typed functions over shared primitives

One typed function per downstream consumer in §9 (eleven consumers). Each function:
- Accepts the parameters its consumer needs (athlete + plan + sport context)
- Returns a typed payload tailored to its consumer's prompt design
- Is a pure read — no side effects, deterministic given inputs

Underneath, shared primitives handle common operations:
- `_load_sport_context(sport)` — sport row + flags + classifications
- `_load_discipline_set(sport)` — disciplines + roles + race_time bands + phase load
- `_resolve_age_ramp(discipline, athlete_age)` — age-bracket ramp pct
- `_filter_exercise_pool(disciplines, equipment, injuries, conditions)` — sport- and constraint-filtered exercise list
- `_resolve_pairing_matrix(disciplines)` — pairwise pairing ratings
- `_resolve_substitutes(disciplines, available_disciplines)` — substitution lookup
- `_resolve_phase_load(sport, athlete_overrides)` — system defaults + athlete overrides

Rejected alternatives: stored procedures (deployment friction), single catch-all function (opaque, breaks blast radius isolation).

#### Decision 2: ETL version pinning — per plan-generation pin

When a plan starts generating, the system records `etl_version_set` in the plan row. Every subsequent query for that plan uses those versions, even if a newer ETL run lands. Required for:
- Consistency within a plan
- Reproducibility (can re-run plan generation from same inputs)
- Partial-update model (changing one section of a plan doesn't pull in a different Layer 0 version mid-flight)

`etl_version_set` is a JSONB blob:
```json
{
  "0A": "v10.0",
  "0B": "v17.0",
  "0C": "v2.0"
}
```

Pinning one source but not another would be a Frankenstein.

#### Decision 3: Caching — defer build, design cache-friendly

Caching not built at launch (handful-of-athletes scale, indexed Postgres queries are fast enough). But the query layer must be designed cache-friendly from day one:
- Same inputs → same outputs (deterministic)
- No side effects (pure read)
- All inputs explicit (no hidden time/state dependencies — no `NOW()`, no implicit "current athlete profile" reads)

When caching becomes necessary (real signal: launch query >500ms), add a thin wrapper layer that intercepts function calls. Two natural invalidation triggers:
- ETL refresh completes → discard old version-keyed entries
- Athlete profile mutates → discard athlete-keyed entries

No time-based expiration. Tracked as launch+later open item.

#### Decision 4: Missing filters — three additions

**4A — Health condition filter.** Mirrors injury filter. Uses `contraindicated_conditions` field on exercises. Simple yes/no filter for v1; severity nuance deferred. UI gap also tracked: there's no add/view UX for Health Conditions today (only injuries). Same UX surface, two database tables. Launch-blocker open item.

**4B — Sport classifications.** Replaces single `sport_family` field. Four columns on `layer0.sports`:
- `constituent_movements` (multi-select)
- `endurance_profile` (enum)
- `participation_format` (enum)
- `multi_discipline` (boolean, derived)

Per Andy: only classifications that "actually matter to the way our system works" — these four do. Race format, terrain type, season are per-event or per-locale, not per-sport.

**4C — Discipline Weighting.** Return both system defaults AND athlete-overridden values. Prompt resolves and can explain the override.

#### Decision 5: Phase Load shape — five sub-decisions

**A — Discipline rows return name/role/conditional flag/low-high % per phase.** Bands not points.

**B — Strength + Mobility return as separate `accessory_load` block, NOT in `disciplines[]` array.** Different consumers. Plan-gen wants disciplines for time-allocation; accessory work has its own placement logic.

**C — Weekly Total Target** parsed by ETL from free text into structured `{base, build, peak, taper}` hour bands (per §3.3). Original text retained in `weekly_target_text` as fallback.

**D — Notes column split** into `prescription_note` (short, athlete-facing) and `audit_log` (sources, citations, math, internal flags). Query returns prescription_note by default; audit_log on demand via parameter.

**E — Conditional disciplines flag** in payload. Plus `default_inclusion` per sport-discipline (three values: `included` / `excluded` / `prompt_required`). Substitution + race-driven resolution lives in plan-gen, NOT query layer.

**Math note for plan-gen:** discipline percentages don't sum to 100 (AR Build = 103–142%). Bands are intentionally flexible. Query returns honestly with a note; prompt resolves to weekly-hours target, not to 100%.

---

### 5.2 Per-consumer function signatures

Eleven typed functions, one per downstream consumer in §9. Names follow `q_layerX_consumer_payload(...)` pattern.

```python
# Layer 2 family
q_layer2a_discipline_classifier_payload(framework_sport: str, etl_version_set: dict) -> Layer2APayload
q_layer2b_terrain_classifier_payload(etl_version_set: dict) -> Layer2BPayload
q_layer2c_equipment_mapper_payload(framework_sport: str, disciplines: list[str], etl_version_set: dict) -> Layer2CPayload
q_layer2d_injury_risk_profile_payload(disciplines: list[str], etl_version_set: dict) -> Layer2DPayload
q_layer2e_nutrition_baseline_payload(framework_sport: str, etl_version_set: dict) -> Layer2EPayload

# Layer 3 family
q_layer3d_injury_analysis_payload(exercise_ids: list[str], etl_version_set: dict) -> Layer3DPayload

# Layer 4 family
q_layer4_plan_generation_payload(
    framework_sport: str,
    disciplines: list[str],
    training_phase: str,
    athlete_age: int,
    equipment_available: list[str],
    active_injuries: list[InjuryRecord],
    active_conditions: list[ConditionRecord],
    locale_type: str,
    discipline_weighting_overrides: dict | None,
    include_exercise_pool: bool,
    max_exercises: int,
    etl_version_set: dict
) -> Layer4Payload

q_layer4_5_validator_payload(framework_sport: str, training_phase: str, etl_version_set: dict) -> Layer45Payload

# Layer 5 family — three consumers, each receives nothing directly from Layer 0
# but the query layer still exposes stub functions for symmetry / future extension
q_layer5a_nutrition_payload(etl_version_set: dict) -> Layer5APayload
q_layer5b_supplements_payload(etl_version_set: dict) -> Layer5BPayload
q_layer5c_clothing_payload(etl_version_set: dict) -> Layer5CPayload
```

### 5.3 Layer 4 (Plan Generation) — the canonical full payload

Most other consumers are subsets. Layer 4 is the reference shape.

**Input:**

```json
{
  "framework_sport": "Adventure Racing",
  "disciplines": ["D-001", "D-005", "D-008a", "D-013"],
  "training_phase": "Base",
  "athlete_age": 42,
  "equipment_available": ["Barbell", "Dumbbells", "Pull-up bar", "Kettlebells"],
  "active_injuries": [
    {"body_part": "Wrist", "side": "Left", "severity": "Recovering"}
  ],
  "active_conditions": [
    {"category": "Respiratory", "name": "Mild EIB", "severity": "Managed"}
  ],
  "locale_type": "home",
  "discipline_weighting_overrides": {"D-005": 35, "D-008a": 15},
  "include_exercise_pool": true,
  "max_exercises": 40,
  "etl_version_set": {"0A": "v10.0", "0B": "v17.0", "0C": "v2.0"}
}
```

**Output:**

```json
{
  "sport_context": {
    "sport_name": "Adventure Racing",
    "classifications": {
      "constituent_movements": ["running", "cycling", "paddling", "hiking", "navigation", "climbing"],
      "endurance_profile": "Mixed",
      "participation_format": "Both",
      "multi_discipline": true
    },
    "planning_flags": {
      "navigation": true,
      "sleep_deprivation": true,
      "pack_carry": true,
      "pack_weight_lbs": [25, 35],
      "transitions": true
    },
    "weekly_total_target": {
      "base": {"low": 8, "high": 12},
      "build": {"low": 12, "high": 18},
      "peak": {"low": 18, "high": 26},
      "taper": {"low": 6, "high": 10}
    }
  },
  "disciplines": [
    {
      "id": "D-001",
      "name": "Trail Running",
      "role": "Primary",
      "is_conditional": false,
      "default_inclusion": "included",
      "race_time_pct": {"low": 25, "high": 35},
      "sport_specific_context": "...",
      "phase_load_pct": {"low": 22, "high": 28},
      "weekly_ramp_pct": 8,
      "min_base_weeks": 4,
      "taper_norms": "2-3 weeks, 40-60% volume cut",
      "injury_patterns": ["IT band syndrome", "plantar fasciitis"],
      "stimulus_components": ["aerobic_low", "aerobic_high", "muscular_endurance_legs", "vertical_gain"],
      "discipline_weighting": {"system_default": 30, "athlete_override": null, "resolved": 30},
      "prescription_note": "Build slow over 4 weeks; pack carry weeks alternate."
    }
  ],
  "accessory_load": {
    "strength": {
      "phase_load_pct": {"low": 8, "high": 12},
      "prescription_note": "Lower-body single-leg priority; pack-carry simulation."
    },
    "mobility": {
      "phase_load_pct": {"low": 4, "high": 6},
      "prescription_note": "Hip flexor + ankle daily; pre-paddle thoracic mobility."
    }
  },
  "pairing_matrix": [
    {"a": "D-001", "b": "D-005", "rating": "PREFERRED", "rationale": "Standard run-bike brick"},
    {"a": "D-005", "b": "D-008a", "rating": "ACCEPTABLE", "rationale": "..."},
    {"a": "D-008a", "b": "D-001", "rating": "AVOID", "rationale": "Paddle-shoulder fatigue impacts run form"}
  ],
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
      "contraindicated_conditions": [],
      "injury_flag": null,
      "condition_flag": null,
      "progression": {"id": "EX089", "name": "Hollow Body Hold"},
      "regression": {"id": "EX216", "name": "Plank (Front)"},
      "physical_proxies": [
        {"id": "EX117", "name": "Loaded Step-Down (Eccentric Box)"}
      ],
      "improvised_options": []
    }
  ],
  "training_gaps": [],
  "etl_version_set": {"0A": "v10.0", "0B": "v17.0", "0C": "v2.0"},
  "query_run_at": "2026-05-08T14:00:00Z"
}
```

**Field semantics:**

- `equipment_status`: `available` / `substitute_available` / `improvised_available` / `proxy_only`
- `injury_flag`: `null` / `excluded` / `flagged`
- `condition_flag`: `null` / `excluded` / `flagged` (mirrors injury_flag for `contraindicated_conditions`)
- `discipline_weighting.resolved` = athlete_override if non-null else system_default
- `training_gaps`: array of any disciplines in input that have rows in `discipline_training_gaps`. Plan-gen handles the warning surfacing.

### 5.4 Substitution resolution (called by plan-gen, not its own consumer)

When plan-gen needs to substitute a discipline (athlete lacks access), it calls a query layer primitive:

```python
_resolve_substitutes(
    target_id: str,
    available_discipline_ids: list[str],
    etl_version_set: dict
) -> SubstitutionResult
```

**Returns:**
```json
{
  "target_id": "D-016",
  "target_name": "Mountaineering / Scrambling",
  "candidates": [
    {
      "substitute_id": "D-007",
      "substitute_name": "Hiking (loaded)",
      "fidelity": 0.55,
      "constraints": "covers aerobic + pack carry; loses vertical-gain rate and technical handwork",
      "category": "Family — vertical foot",
      "available": true,
      "covers": ["aerobic_low", "pack_carry_load", "vertical_gain"]
    }
  ],
  "training_gap": {
    "is_gap": false,
    "gap_type": null,
    "multi_substitute_candidate": false
  }
}
```

If the target is in `discipline_training_gaps`, the `training_gap` block is populated. Plan-gen decides whether to surface the warning and/or attempt composition.

**Multi-substitute composition logic itself lives in plan-gen, not the query layer.** Layer 0 returns the candidate list with coverage data; plan-gen runs the set-cover algorithm.

---

## 6. ETL run process

### 6.1 Trigger conditions

Same as v2. New version of any source file released, or manual admin override. Never user-triggered.

### 6.2 Run order

```
PHASE 1 — Vocabularies (no dependencies)
  1. layer0.body_parts                       (Vocab Audit §1)
  2. layer0.health_condition_categories      (Vocab Audit §2.2)
  3. layer0.equipment_items                  (Vocab Audit §3)
  4. layer0.terrain_types                    (Vocab Audit §3 terrain subsection)
  5. layer0.sport_specific_gear_toggles      (Vocab Audit §4.1)
  6. layer0.sport_name_aliases               (sport_name_aliases.py)

PHASE 2 — 0A core
  7. layer0.sports                           (Sheet 1, with new classification cols)
  8. layer0.disciplines                      (Sheet 2, with D-008 split, D-030/D-031 removed, stimulus_components NULL-able)
  9. layer0.sport_discipline_map             (Sheet 3)
  10. layer0.discipline_pairing              (Sheet 4 + Sheet 3 col 7 fallback)
  11. layer0.phase_load_allocation           (Sheet 5, with default_inclusion + Notes split)
  12. layer0.phase_load_weekly_totals        (Sheet 5 aggregator rows, parsed per §3.3)
  13. layer0.team_formats                    (Sheet 6)
  14. layer0.cross_sport_properties          (Sheet 8)
  15. layer0.discipline_substitutes          (Discipline Substitution Map sheet) — NEW
  16. layer0.discipline_training_gaps        (Discipline Training Gaps sheet) — NEW

PHASE 3 — Bridge and 0B
  17. layer0.sport_discipline_bridge         (derived from Sheet 3 + alias map)
  18. layer0.exercises                       (Exercise Master; apply vocab transforms; split contraindicated string)
  19. layer0.sport_exercise_map              (Sport-Exercise Map)
```

### 6.3 Versioning on each run

1. Read current `etl_version` from most recent run for each source family.
2. Assign new version strings: `0A-vN`, `0B-vN`, `0C-vN` (independent versioning per source).
3. Insert all new rows with new `etl_version` and current timestamp.
4. Set `superseded_at = NOW()` on all prior rows where `superseded_at IS NULL` AND `etl_version` is the prior version of the same source family.
5. All queries filter `WHERE superseded_at IS NULL` — no migration, rollback is trivial.

### 6.4 Validation passes

After Phase 2 step 11 (`phase_load_allocation`): sum-to-100 check per sport per phase. Adjusted stack (conditionals zeroed, one paddle discipline) must reach 100% high-band on all phases. Log warnings; do not abort.

After Phase 2 step 15 (`discipline_substitutes`):
- Validate every `target_id` and `substitute_id` exists in `layer0.disciplines`. Log broken FKs as ERRORs.
- Validate `fidelity` ∈ [0.0, 1.0]. Reject row + log ERROR.
- If `substitute_covers` populated, validate each element appears in target's `stimulus_components` (warning only — `stimulus_components` may not be populated yet).

After Phase 2 step 16 (`discipline_training_gaps`): validate each `discipline_id` exists in `layer0.disciplines`.

After Phase 3 step 18 (`exercises`):
- For each exercise's `contraindicated_parts[]`, verify each entry exists in `layer0.body_parts.canonical_name`. Log mismatches as warnings.
- For each exercise's `contraindicated_conditions[]`, verify each entry exists in `layer0.health_condition_categories.system_category`. Log mismatches as warnings.

After Phase 3 step 19 (`sport_exercise_map`): for each `sport_name`, verify it exists in `layer0.sport_discipline_bridge.exercise_db_sport`. Log mismatches as warnings.

### 6.5 ETL re-run plan from current state

The current Postgres `layer0` schema reflects v2 spec + Round 1/Round 2 patches. The v3 ETL adds:
- New tables: `discipline_substitutes`, `discipline_training_gaps`
- New columns on existing tables: `sports.constituent_movements / endurance_profile / participation_format / multi_discipline`; `phase_load_allocation.default_inclusion / prescription_note / audit_log / raw_notes`; `disciplines.stimulus_components` (NULL-able); `discipline_substitutes.substitute_covers` (NULL-able)
- D-008 split + D-030/D-031 removal in `disciplines` data
- v8 D-008b values in `discipline_pairing` data

**Re-run sequence:**
1. Apply schema migration (new tables + new columns). `ALTER TABLE` with `IF NOT EXISTS` on cols.
2. Re-extract all 0A sheets from `Sports_Framework_v10.xlsx` and write with new `etl_version = "0A-v10.0"`.
3. Re-extract 0B unchanged but with new `etl_version = "0B-v17.0-r2"` (R2 marks the contraindicated_conditions derivation, even though source xlsx unchanged).
4. Re-extract 0C from `Vocabulary_Audit_v2.md` with new `etl_version = "0C-v2.0-r1"`.
5. Set `superseded_at = NOW()` on prior versions.
6. Run validation passes per §6.4.
7. Triage any new warnings (expected: zero from sum-to-100 since v10 passed audit; possible new warnings from substitution table FK validation if any sheet rows reference D-030/D-031 mistakenly).

**Effort estimate:**
- Schema migration: ~30 min in Claude Code session
- Re-run: ~5 min once code handles new sheets and columns
- New code for Sheet 5C parser (Weekly Total Target free-text) and Sheet 5D parser (Notes split): ~1–2 hrs
- Total: half a coding session

---

## 7. Open items

| # | Item | Action required | Owner | Status |
|---|------|-----------------|-------|--------|
| 1 | Governing Bodies (Sheet 1) | Table for future athlete FAQ feature; revisit when FAQ is scoped | App team | Carryover from v2 |
| 2 | Race / Event Formats (Sheet 1) | Review after Layer 1 prompt design | Cross-chat | Carryover from v2 |
| 3 | Discipline Pairing Matrix gap (D-018+) | Sheet 4 still covers D-001–D-017 (now also D-008a/b explicit). ETL fallback to Sheet 3 col 7 remains required. Long-term fix: extend Sheet 4 matrix | Other chat | Carryover from v2; gap still exists |
| 4 | Vertical Gain field in Layer 1 | Athlete onboarding captures current vertical gain capacity | Layer 1 design | Carryover from v2 |
| 5 | exercise_db_sport vocabulary alignment | Resolved Round 1; alias map in place. No ongoing action unless new exercise DB sport names land. | ETL build | RESOLVED — monitoring only |
| 6 | Sheet 3 col 7 deprecation | Once Sheet 4 covers D-018+, deprecate col 7 | Other chat | Carryover from v2 |
| 7 | Cross-Sport Properties extension | Sheet 8 has 1 substantive row (LIT_RATIO_001) | Other chat | Carryover from v2 |
| 8 | Vocabulary cleanup transforms | `vocabulary_transforms.py` built and deployed Round 2 | ETL build | RESOLVED |
| 9 | `stimulus_components` populate (v3 NEW) | ~30 disciplines × ~5 components each; ~60–90 min curation. Required for plan-gen multi-substitute composition. | Andy + Claude | NEW — not blocking ETL re-run; plan-gen consumer not built yet |
| 10 | `substitute_covers` populate (v3 NEW) | ~91 substitution rows × subset of target stimuli; ~30 min after #9 done. | Andy + Claude | NEW — pairs with #9 |
| 11 | Multi-substitute composition algorithm (plan-gen layer) | Plan-gen design; not Layer 0 work. Open Item documents the contract Layer 0 satisfies. | Plan-gen design | Deferred to plan-gen workstream |
| 12 | Pairing matrix D-008b values review | Refined with judgment in v8; would benefit from 30-min review by whitewater AR coach | External reviewer | Not blocking |
| 13 | AR D-008b phase load percentage tuning | Set conservatively (BASE 0% / BUILD 1–3% / PEAK 3–5% / TAPER 1–2%). Worth confirming with actual whitewater AR race data | External | Not blocking |
| 14 | Sport-context substitution overrides | Substitution sport-agnostic in v1. Add per-sport-context overrides in v2 if plan-gen testing shows too coarse | Plan-gen testing signal | Deferred until signal arrives |
| 15 | Health Conditions UI gap | No add/view UX for Health Conditions today (only injuries). Same UX surface, two database tables | App team | Launch-blocker |
| 16 | D-020 Alpine Descent training gap | Captured in `discipline_training_gaps`. Plan-gen surfaces warning when athlete has no snow access. | Plan-gen | Captured; no Layer 0 action |
| 17 | D-024 Épée Fencing training gap | Captured in `discipline_training_gaps`. Plan-gen surfaces warning when athlete cannot access fencing coach. | Plan-gen | Captured; no Layer 0 action |
| 18 | D-018 Swimrun training gap | Captured; multi-substitute composition is the answer. | Plan-gen | Captured; pairs with #11 |
| 19 | Sub-ID naming convention | Used `D-008a` / `D-008b` matching D-005a precedent. If more splits emerge, decide whether to keep suffix or assign sequential IDs (D-032+). | Architecture | Process note |
| 20 | Caching layer | Defer until launch query >500ms. Design cache-friendly from day 1 (per §5.1 Decision 3). | Implementation | Deferred |

---

## 8. Downstream prompt consumption reference

What Layer 0 context each layer receives and from which tables.

| Layer | Receives from Layer 0 | Tables queried |
|-------|----------------------|----------------|
| 2A (Discipline Classifier) | Sport classifications + planning flags + discipline list with roles & race-time bands | sports, sport_discipline_map, sport_discipline_bridge |
| 2B (Terrain Classifier) | Terrain vocabulary | terrain_types |
| 2C (Equipment Mapper) | Equipment vocabulary, gear toggles, exercise pool filtered by discipline only | equipment_items, sport_specific_gear_toggles, sport_exercise_map, exercises |
| 2D (Injury Risk Profile) | Injury patterns + preceding behaviors per discipline; body part vocabulary | disciplines, body_parts |
| 2E (Nutrition Baseline) | None directly | — |
| 3D (Injury Analysis) | Contraindicated parts AND conditions; injury flags per exercise; vocabularies | exercises, body_parts, health_condition_categories |
| 4 (Plan Generation) | Full sport context + classifications + exercise pool (equipment + injury + condition filtered) + phase load bands + weekly hour targets + training gaps + substitution candidates | All tables via query layer |
| 4.5 (Validator) | Sport rule sets: ramp rates, phase durations, pairing rules, taper norms, cross-sport properties | sports, disciplines, discipline_pairing, phase_load_allocation, cross_sport_properties |
| 5A (Nutrition) | None — operates on plan output + athlete data | — |
| 5B (Supplements) | None — operates on plan output + athlete data | — |
| 5C (Clothing) | None — operates on weather + athlete history | — |

---

## 9. Future work

- **Plan-gen consumer build.** Once plan-gen design starts, `stimulus_components` and `substitute_covers` get populated. Substitution composition algorithm built in plan-gen.
- **Caching layer.** When latency demands it.
- **Sport-context substitution overrides.** v2 if plan-gen testing shows v1 too coarse.
- **Sheet 4 pairing matrix expansion** to D-018+. Long-term, deprecates Sheet 3 col 7 fallback.
- **Cross-sport properties expansion.** ECCENTRIC_LOAD, STRENGTH_PRIMACY, TECHNICAL_TERRAIN_DIFFICULTY, NAVIGATION_DEMAND noted in Sheet 8 as candidates.

---

*End of v3 spec. Successor: when v4 lands, supersede this doc with what changed. Don't overwrite.*
