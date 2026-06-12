# Layer 0 ETL Specification — v7

**Version:** 7.0 (file revision); schema version v3 (unchanged — v7 closes the last open `\d`/schema-dump deferral against Neon)
**Status:** Revised 2026-05-13 (FC-4b). v7 closes D-21 (`health_condition_categories` deployed column name is `category_name`; the §6.2 validation note referencing `system_category` as a column was the stale half of the v3 split-reference; full 6-column schema + 2 constraints now documented in §4.14). **Layer 0 spec is now fully self-consistent against deployed Neon schema across every enumerated table.** No new cleanup items surfaced; D-47 still queued for next Layer 2D touch.
**Supersedes:** `Layer0_ETL_Spec_v6.md` (FC-4a, 2026-05-13).
**Sources:**
- `Sports_Framework_v10.xlsx` (0A) — schema reference for sport/discipline/phase data
- `AR_Exercise_Database_v19.xlsx` (0B) — exercise master (v17 in v3; bumped v17→v18→v19 across FC-1a/FC-1b for column structural cleanup and movement_components prep)
- `Vocabulary_Audit_v3.md` (0C) — canonical vocabularies (body parts: 51 tokens; equipment categories; health condition system enum)
- `D22_Curation_Reference_v2.md` — `exercises.movement_components` curation reference (159 rows, 11 canonical tokens)
- `D23_Curation_Reference_v1.md` — `disciplines.body_parts_at_risk` curation reference (31 rows, 28-of-51 body parts referenced)
- `Supplement_Vocabulary_Spec.md` — `supplement_vocabulary` table seed data (25 entries, 8-cat enum + 4-tier evidence)

---

## What changed in v7 vs v6

v7 is a narrow revision closing the last open Neon schema-dump deferral from FC-2 (D-21 `health_condition_categories` column name). After v7, every Layer 0 table has been enumerated against deployed Postgres via `information_schema.columns` + `pg_constraint` queries; the spec is fully self-consistent against deployed reality.

**Schema enumeration completed:**

1. **§4.14 `health_condition_categories` 6-column schema enumerated.** Deployed shape: `id` (SERIAL PK), `category_name` (TEXT NOT NULL), `description` (TEXT nullable), plus the standard `etl_version` / `etl_run_at` / `superseded_at` envelope. One UNIQUE constraint on `(category_name, etl_version)`. The v3 spec had a split reference — §4.14 said `category_name`, §6.2 validation said `system_category` — and the FC-1a drift report flagged the table as "no drift" without reconciling which was correct. Deployed answer: **`category_name`**. D-21 closed.

**Stale-reference cleanup:**

2. **§6.2 Phase-3 step-18 validation note corrected.** The validation line previously read "verify each entry exists in `layer0.health_condition_categories.system_category`"; corrected to `.category_name`. This is the only SQL-column reference to the table elsewhere in the spec — every other `system_category` mention in v6/v7 (and in Layer 2D / 2E specs) is a Python dataclass field name on `HealthConditionRecord`, which is independent of the SQL column and stays as `system_category`. **No consumer change required.**

**Milestone — Layer 0 spec consistency:**

After v7, every Neon-enumerated Layer 0 table either matches the spec verbatim or has its drift-correction committed in v4 / v5 / v6 / v7. Remaining open items in Layer 0 (`D-03` / `D-07` ETL parser fixes; `D-47` Layer 2D rationale-comment fix) are code-side and consumer-side respectively — neither blocks query-layer implementation or Layer 3 design.

**Out of scope for v7 (carried forward):**

- **D-03 / D-07** ETL parser fixes pending v20 re-run (CC tasks, unaffected by FC-4b).
- **D-47** Layer 2D §5.2 rationale-comment update — fold into next Layer 2D revision (`Layer2D_Spec` → v2). Comment-only; functional behavior already correct.
- **Layer 2D / 2E open-items housekeeping.** Both specs carry a "D-21 deferred" open-items row (Layer 2D row 2D-5; Layer 2E row 2E-16). These resolve cleanly on next 2D / 2E touch — no spec bump required just for the row update; piggyback when D-47 is folded in.

---

## What changed in v6 vs v5

v6 is a narrow revision closing the two FC-3 carry-forward items (D-41 `terrain_types` schema retry, D-46 `sport_name_aliases` multi-mapping audit) and surfacing one new cleanup item from the audit findings.

**Schema enumeration completed:**

1. **§4.14 `terrain_types` 9-column schema enumerated.** Deployed shape: `canonical_name` (NOT NULL), `notes`, plus 7 enrichment columns (`terrain_id`, `category`, `requires_elevation`, `technical_surface`, `environment`, `simulatable`, `simulation_note`). Two UNIQUE constraints: `(canonical_name, etl_version)` and `(terrain_id, etl_version)`. **Drift report correction:** §2.10 of the drift report listed `simulatable` as `BOOLEAN`; deployed is `TEXT`. The TEXT shape permits values like 'yes', 'no', 'partial', 'conditional' — useful for nuanced simulation labels rather than binary flags. `terrain_id` is nullable; with Postgres NULL-distinct semantics in UNIQUE, multiple `terrain_id IS NULL` rows per `etl_version` are permitted (matches the 16-superseded-of-31 hand-curation history pattern). D-41 closed.

**Audit findings documented:**

2. **§4.16 / §4.11 `sport_name_aliases` multi-mapping audit complete.** Neon COUNT query against active alias rows returned 21 multi-mapped `exercise_db_sport` values. Pattern confirmed **intentional** for framework sub-format splitting — e.g., "Triathlon" (exercise-DB) maps to 5 framework sub-formats (Sprint/Standard/70.3/Ironman/Aquathlon-style); "Swimming" (exercise-DB) maps to 11 framework swim contexts (pool/OW/marathon/swimrun/triathlon-swim/etc.); "General Conditioning" maps to 38 framework sports (broadly applicable). **Curation is correct as-is**; no `sport_name_aliases.py` tightening required. D-46 closed.

3. **§4.11 `sport_discipline_bridge` row-multiplication property documented.** Direct consequence of D-46 closure: when an `exercise_db_sport` maps to multiple `framework_sport` values, bridge derivation produces one row per `(exercise_db_sport, framework_sport, discipline_id)` triple — which means joins through the bridge can return **multiple rows for the same `(exercise_id, discipline_id)` pair** when a discipline is shared across the multi-mapped framework sports. Consumer-side dedup is required. Layer 2D §5.2 already does post-query dedup by `exercise_id`, so functional behavior is correct — but the explanatory comment in that spec attributes dedup to the multi-discipline path only and should also cite the framework-mapping path. Tracked as D-47.

**New cleanup item:**

4. **D-47 added:** Layer 2D §5.2 SQL rationale-comment update — note the framework-mapping multiplication path as a second reason post-query `exercise_id` dedup is required. Low priority (functional behavior already correct); fix at next Layer 2D revision. Any other future consumer that joins through `sport_discipline_bridge` must also dedup.

**Out of scope for v6 (carried forward):**

- **D-21** `health_condition_categories` column name uncertainty (`category_name` vs `system_category`). FC-2 grouped it with the terrain_types schema-dump session; the actual table is different and needs its own `information_schema.columns` query. Held for FC-4b.
- **D-03 / D-07** ETL parser fixes pending v20 re-run (CC tasks, unaffected by FC-4a).
- **§5.2 Layer 3 family + Layer 5 family** forward-looking stubs in v5 carry forward unchanged.

---

## What changed in v5 vs v4

v5 is a narrow revision driven by Neon schema verification (FC-3 schema-dump pass) and the §5 query-layer narrative refresh that v4 deferred.

**Schema corrections from FC-3 Neon dumps:**

1. **§4.8 `cross_sport_properties.confidence` type** corrected from `NUMERIC` (v4 spec) to `TEXT` (deployed). D-42 closed. No semantic change — the column carries qualitative confidence labels, not numeric scores. v4 §4.8 column list was otherwise correct; Batch D v2 §3's proposed `property_type`/`value`/`unit`/`applies_to_sports`/`applies_to_disciplines` columns confirmed not deployed.

2. **§4.16 `sport_name_aliases` UNIQUE constraint** corrected from 2-column `(exercise_db_sport, etl_version)` (v4 spec) to 3-column `(exercise_db_sport, framework_sport, etl_version)` (deployed). The v4 "one-to-one enforced inversely" claim is **retracted** — deployed permits one `exercise_db_sport` to map to multiple `framework_sport` values at a given `etl_version`. D-44 opened and closed in FC-3. Consumer impact: §4.11 `sport_discipline_bridge` derivation should treat the alias join as one-to-many, not one-to-one. Investigate at next bridge re-derivation whether any active aliases multiply rows.

3. **§4.17 `terrain_gap_rules` placeholder replaced** with full deployed schema. 12 functional columns enumerated: `target_terrain_id`, `target_terrain_name`, `proxy_terrain_id` (nullable), `proxy_terrain_name` (nullable), `gap_severity`, `adaptation_weeks_low/high`, `proxy_fidelity`, `proxy_methods TEXT[]`, `uncoverable_stimulus TEXT[]`, `prescription_note`, `audit_log`. UNIQUE: `(target_terrain_id, proxy_terrain_id, etl_version)`. Nullable `proxy_terrain_id` permits multiple "uncoverable" rows per target. D-40 closed.

**Schema verification deferred (carried forward):**

4. **§4.14 `terrain_types` 7-column enumeration** still pending — FC-3 Neon query failed on a client-side `\d` quoting artifact. Retry uses `information_schema.columns` form (see `Project_Backlog_v8` D-41).

**§5 query-layer narrative refresh:**

5. **§5.2 function signatures rewritten to mirror per-layer specs verbatim.** v4 §5.2 listed 2A–2E signatures that diverged from the per-layer spec for each function, including the FC-2 "corrections" for 2C/2D which mis-modeled input shape. v5 takes per-layer spec as authoritative per §6.6 and mirrors each signature with "Mirror of LayerXX_Spec §3" attribution. This formalizes the spec-of-spec relationship and prevents the FC-2-style misreading from recurring.

6. **§5.3 Layer 4 canonical payload** updated for FC-1b column promotions:
   - Discipline-level: `injury_patterns` → `common_injury_patterns` (column rename per §4.3); new `body_parts_at_risk` field surfaces the structured 51-token list for plan-gen prompting.
   - Exercise-pool level: new `movement_components` field surfaces the structured 11-token constraint vocabulary alongside the biomechanical `movement_patterns` (these are different things: pattern vs constraint).
   - Input record type alignment: `active_conditions` annotated as `HealthConditionRecord` (matches Onboarding §B.4 + Layer 2D §3).

7. **§5.1 architecture decisions** touched lightly: `_filter_exercise_pool` primitive note updated to reflect structured `movement_components` matching (D-22) rather than heuristic keyword-match. `_resolve_substitutes` param name aligned with §5.4.

8. **§5.4 substitution resolution** annotated with D-15 variant-key semantics: function returns all variants in `candidates[]` (no `(target_id, substitute_id)` deduplication); plan-gen picks by athlete context.

**Out of scope for v5 (carried forward):**

- §4.14 `terrain_types` schema dump retry (D-41).
- §4.18 `supplement_vocabulary` schema reproduction in v5 §4.18 — still a pointer placeholder to `Supplement_Vocabulary_Spec.md`. Reproduce when entries stabilize beyond seed set.
- Layer 3 family stub in §5.2 (Layer 3 design not started). Revise §5.2 3D entry when Layer 3 spec lands.
- Layer 5 family stubs in §5.2 (no 5A/5B/5C per-layer specs yet). 5B will consume `supplement_vocabulary`; revise when 5B spec is written.

---

## What changed in v4 vs v3

This is a consolidation revision. The Layer 0 schema as deployed in Neon differs from `Layer0_ETL_Spec_v3.md` §4 in several places — some intentional drift (deployed adds columns the spec didn't anticipate, all kept), some bug-fixes (column renames, aggregator-row filtering), some genuine omissions (whole tables not documented in v3). v4 reconciles spec to deployed across all 15+ tables and adds three FC-promoted columns that didn't exist when v3 was drafted.

**New tables documented in §4 (not in v3):**
1. `discipline_technique_foci` (§4.15) — added Batch B; structured technique-focus pointers per discipline
2. `sport_name_aliases` (§4.16) — added Batch D; alias resolution for sport name normalization
3. `terrain_gap_rules` (§4.17) — surfaced by drift report §2.12; populates from Sheet 7
4. `supplement_vocabulary` (§4.18) — added FC-1 (D-26) as Layer 0 reference data for §2E supplement coaching

**Schema additions to existing tables:**
5. `exercises.movement_components TEXT[]` (§4.12, D-22, FC-1b 2026-05-12) — structured 11-token vocabulary replacing heuristic keyword-match against `injury_flags_text` for Layer 2D set-intersect. 159 active rows populated. GIN index `idx_exercises_movement_components`.
6. `disciplines.body_parts_at_risk TEXT[]` (§4.3, D-23, FC-1b 2026-05-12) — structured 51-token vocabulary enabling direct set-intersect against athlete `Injury Record.body_part`. 31 disciplines populated. GIN index `idx_disciplines_body_parts_at_risk`.

**Schema corrections to existing tables (FC-1a):**
7. `phase_load_allocation` — `phase_` prefix removed from band columns (D-04, idempotent rename verified deployed-state-matches-target).
8. `phase_load_weekly_totals` — `weekly_low_hours/high_hours` renamed to `hours_low/hours_high` to match spec (D-06).
9. `cross_sport_properties.source_text` column dropped (D-14, duplicated `source_evidence` semantically).
10. `cross_sport_properties` retains 3 extra cols vs v3 spec: `source_evidence`, `notes`, `confidence` (post-D-14 cleanup).
11. `discipline_substitutes` UNIQUE clarified to include `substitute_name` as variant key (D-15 — deliberate, preserves coaching-signal variants).
12. `exercises.primary_muscles` / `secondary_muscles` confirmed as `TEXT[]` with ETL transform `string_to_array(value, ', ')` (D-16).
13. `disciplines` — `injury_patterns` → `common_injury_patterns`, `preceding_behaviors` → `injury_preceding_behaviors` (D-02 deployed-naming retained).
14. `exercises` comprehensive schema correction — 7 missing cols added to v4 §4.12, 4 renames applied (D-01 / Batch B detail).
15. `phase_load_allocation` ETL aggregator-row filter — 33 WEEKLY TOTAL TARGET rows excluded from active set (D-05, partial: code patch pending CC).
16. `sport_discipline_map` — sub-format-collapsing UNIQUE behavior documented (D-08, AR-safe).
17. `terrain_types` — 7 enrichment columns + secondary UNIQUE documented in §4.x (D-10).
18. `discipline_technique_foci` — `source_exercise_ids TEXT[]` + `audit_log TEXT` (D-13, deployed shape matches Batch B Correction).

**Pending implementation (spec-ahead-of-deployed):**
19. `phase_load_allocation` — `is_conditional BOOLEAN` and `vertical_gain_notes TEXT` (D-03 decision: BUILD; pending v20 ETL re-run; CC task).
20. `phase_load_weekly_totals` — parser fixes for multi-sub-format / km-based / percentage-cut TAPER (D-07; CC task, decisions locked in FC-1a).

**Process change:**
21. **§6.6 new process note: "Code is authoritative; spec catches up."** Going forward, intentional schema drift between v3 spec and deployed Neon state is treated as "spec lag" not "code bug" — the spec is updated in a periodic FC pass, not blocking ETL or query-layer work. The single source of truth is the deployed schema verified via `\d layer0.<table>`. This revision applies the principle retroactively.

**Vocabulary references:**
22. `Vocabulary_Audit` reference bumped to v3 (51 canonical body parts after Collarbone addition, D-39).

**Out of scope for v4 (carried forward):**
- v3 schema is *not* renamed to v4 schema. The schema version stays at v3 — this is a documentation revision only. When the schema does fork (e.g., a real breaking change), a new schema version (v4 schema) gets a fresh `Layer0_ETL_Spec_v5` cut.
- Project Backlog (`Project_Backlog_v9`) is the active cross-layer tracker; spec catches up to backlog decisions as they land.

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

### 4.3 `layer0.disciplines` (from 0A Sheet 2 — "Discipline Library") — UPDATED v4

One row per discipline. Universal facts — not sport-specific. v4 reflects deployed shape:
- Column renames vs v3 spec (D-02): `injury_patterns` → `common_injury_patterns`, `preceding_behaviors` → `injury_preceding_behaviors`. Deployed names retained as authoritative.
- New v4 column (D-23, FC-1b 2026-05-12): `body_parts_at_risk TEXT[]` — structured 51-token vocabulary populated by hand-curation from `common_injury_patterns` text. Replaces in-code keyword map in Layer 2D §5.5.
- `stimulus_components` curation completed in FC-1a → FC-1b. See §"Stimulus components" below.

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
  common_injury_patterns          TEXT[],               -- renamed v4 (was injury_patterns in v3 spec)
  injury_preceding_behaviors      TEXT[],               -- renamed v4 (was preceding_behaviors in v3 spec)
  recovery_modalities             TEXT[],
  evidence_quality_text           TEXT,                 -- builder reference, not in prompt payloads

  -- v3-promoted: stimulus decomposition for substitute composition
  stimulus_components             TEXT[],               -- multi-value enum (see below)

  -- v4-promoted: body-part-at-risk vocabulary for Layer 2D set-intersect (D-23, FC-1b)
  body_parts_at_risk              TEXT[],               -- canonical 51-token body part vocabulary

  -- versioning
  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,

  UNIQUE (discipline_id, etl_version)
);

-- v4 indexes (deployed FC-1b)
CREATE INDEX idx_disciplines_body_parts_at_risk
  ON layer0.disciplines USING GIN (body_parts_at_risk);
```

**`stimulus_components` enum (starter set, expandable):**
```
aerobic_low ; aerobic_high ; muscular_endurance_legs ; muscular_endurance_upper ;
pack_carry_load ; vertical_gain ; technical_descent ; technical_handwork ;
grip_strength ; balance_dynamic ; cold_exposure ; fueling_practice
```

**`body_parts_at_risk` vocabulary (51 tokens):** drawn from `Vocabulary_Audit_v3.md` Section 1 (Head/Neck, Shoulder including Collarbone, Arm, Back, Hip, Upper leg, Knee, Lower leg, Foot/Ankle, Trunk). 31 disciplines populated; 28 of 51 canonical body parts are referenced across the baseline. Curation reference: `D23_Curation_Reference_v1.md` (house rules 1–7, synonym table, inheritance log, 31 mappings). Migration: `migrate_disciplines_add_body_parts_at_risk_v1.sql`. Population mechanics: hand-curation pass at FC-1b, regenerable from curation markdown via `etl/sources/generate_body_parts_at_risk_migration.py`.

**Stimulus components population:** completed in FC-1 era. No NULLs remain on active rows. Layer 2C / 2E / 4 consumers read structured, not text. Re-curation triggers: new discipline added to library; existing discipline's training profile substantively changes.

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

### 4.5 `layer0.phase_load_allocation` (from 0A Sheet 5 — "Phase Load Allocation") — UPDATED v4

One row per sport × discipline. v4 reflects deployed shape:
- **D-04 (resolved FC-1a):** Band columns are deployed WITHOUT `phase_` prefix. Idempotent rename migration `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` confirmed deployed = target (no-op verify). v3 spec showed `phase_base_pct_low` etc.; deployed has `base_pct_low` etc.
- **D-03 (decision locked FC-1a, implementation pending v20 ETL re-run):** `is_conditional BOOLEAN` and `vertical_gain_notes TEXT` are defined in v4 §4.5 and consumers should code against them, BUT they are **not yet deployed** as of v4 draft. Marked with `[NOT-YET-DEPLOYED]` below; tracked in Project_Backlog v6 as CC task. Do not query as available until v20 ETL ships.
- **D-05 standing rule (FC-1a):** Every Layer 2 query node spec MUST include a defensive `discipline_name NOT LIKE '%WEEKLY TOTAL TARGET%' AND discipline_name NOT LIKE '%TOTAL%'` filter when reading from this table. Retire the standing rule only after CC code-side filter lands and one clean ETL run verifies no regression.
- **D-17 design item (deferred):** Sport naming convention mismatch between Sheet 3 (top-level sport names) and Sheet 5 (sub-format-expanded names) is plan-gen design territory — sport_name in this table uses sub-format expansion (e.g., "Triathlon (Standard / Olympic)") for plan-gen scaling. Resolved via athlete race-format selection at Layer 1 onboarding.

```sql
CREATE TABLE layer0.phase_load_allocation (
  id                        SERIAL PRIMARY KEY,
  sport_name                TEXT NOT NULL,        -- sub-format-expanded per D-17 (e.g., "Triathlon (Standard / Olympic)")
  discipline_id             TEXT NOT NULL,
  discipline_name           TEXT NOT NULL,
  role                      TEXT NOT NULL,
  is_conditional            BOOLEAN,              -- [NOT-YET-DEPLOYED] D-03 build decision locked; CC task for v20

  -- band columns (deployed names, post-D-04, no phase_ prefix)
  base_pct_low              NUMERIC,
  base_pct_high             NUMERIC,
  build_pct_low             NUMERIC,
  build_pct_high            NUMERIC,
  peak_pct_low              NUMERIC,
  peak_pct_high             NUMERIC,
  taper_pct_low             NUMERIC,
  taper_pct_high            NUMERIC,

  vertical_gain_notes       TEXT,                 -- [NOT-YET-DEPLOYED] D-03; parsed from Notes when sport in {Skimo, Mountain Running, XC Skiing, Fell Running}

  -- v3: Notes split into two outputs (per §3.4)
  prescription_note         TEXT,                 -- athlete-facing short text
  audit_log                 TEXT,                 -- internal: sources, citations, math, conditional markers
  raw_notes                 TEXT,                 -- original Notes cell preserved verbatim as fallback

  -- v3: default_inclusion field
  default_inclusion         TEXT NOT NULL,        -- enum: included / excluded / prompt_required

  -- versioning
  etl_version               TEXT NOT NULL,
  etl_run_at                TIMESTAMPTZ NOT NULL,
  superseded_at             TIMESTAMPTZ,

  UNIQUE (sport_name, discipline_id, etl_version)
);
```

**ETL row filtering (D-05 standing rule):**
1. **Aggregator filter (REQUIRED):** Skip rows where `discipline_name LIKE '%WEEKLY TOTAL TARGET%'` OR `discipline_name LIKE '%TOTAL%'`. As of FC-1a all 33 aggregator rows were already in `superseded_at IS NOT NULL` state, but ETL code patch (CC pending) is required to prevent reintroduction on next clean ETL run. Until both code patch and verification land, every query-layer node MUST apply this filter defensively. Verified safe for AR.
2. Skip rows flagged `PENDING SUB-FORMAT EXPANSION` in notes. (As of v10, none remain.)
3. Skip rows where applicability flag (joined from Sheet 3) is `EXCLUDED`.

**ETL field derivation:**
- `is_conditional` (D-03): TRUE if `Role` contains `(*Conditional)` OR `Notes / Conditions` starts with `*CONDITIONAL`. *Pending CC parser addition for v20 ETL re-run.*
- `prescription_note` / `audit_log`: split per §3.4.
- `raw_notes`: full original Notes cell preserved verbatim.
- `default_inclusion`: read directly from new column. Validate against enum (`included`, `excluded`, `prompt_required`).
- `vertical_gain_notes` (D-03): parsed from Notes when sport in {Skimo, Mountain Running, XC Skiing, Fell Running}; null otherwise. *Pending CC parser addition for v20 ETL re-run.*

---

### 4.5.1 `layer0.phase_load_weekly_totals` (NEW v2 carryover, refined v3, parser fixes pending v20)

One row per sport per phase. Derived from Sheet 5 `WEEKLY TOTAL TARGET` aggregator rows.

**D-06 (resolved FC-1a):** Column names match spec — `hours_low`, `hours_high`. Rename migration `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql` applied.

**D-07 (resolved with decisions FC-1a, parser fix pending CC):** Source xlsx has 4 sports under-represented due to three distinct parser failure modes. Decisions locked at FC-1a; full spec in `FC1a_Closing_Handoff_v1.md` §5.2:
1. **Multi-sub-format hours per phase** (Off-Road / Adventure Multisport (Non-Nav), Swimrun): collapse to (min low, max high) range — Option 7.1A.
2. **km-based volume not hrs** (Open Water 10km, 25km): convert km→hrs at parse time at ~20 min/km marathon swim pace — Option 7.2B.
3. **Percentage-cut TAPER** (Swimrun): derive TAPER hours = PEAK midpoint × (1 − taper_pct_midpoint) — Option 7.3A.

```sql
CREATE TABLE layer0.phase_load_weekly_totals (
  id                  SERIAL PRIMARY KEY,
  sport_name          TEXT NOT NULL,
  phase               TEXT NOT NULL,            -- Base / Build / Peak / Taper
  hours_low           NUMERIC,                  -- post-D-06 deployed name
  hours_high          NUMERIC,                  -- post-D-06 deployed name
  weekly_target_text  TEXT,                     -- raw cell preserved as fallback

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (sport_name, phase, etl_version)
);
```

**ETL extraction rule:** for each sport's WEEKLY TOTAL TARGET row, apply parser from §3.3. Emit four rows (one per phase). Three parser-failure modes above handled per D-07 decisions; CC task.

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

### 4.8 `layer0.cross_sport_properties` (from 0A Sheet 8 — "Cross-Sport Properties") — UPDATED v5

**D-14 (resolved FC-1a):** Deployed shape adds 3 columns vs v3 spec: `source_evidence TEXT`, `notes TEXT`, `confidence TEXT`. v3 had drift report showing 4 extra columns, but investigation 2026-05-11 revealed `source_text` was a semantic duplicate of `source_evidence` (identical content on single deployed row). Dropped via `migrate_cross_sport_properties_drop_source_text_v1.sql`. Net: 3 extra cols vs v3 spec.

**D-42 (resolved FC-3, 2026-05-13):** Neon schema dump confirmed v4 §4.8 column list correct, with one type correction: `confidence` is `TEXT`, not `NUMERIC` as v4 spec had it. Column carries qualitative labels, not numeric scores. Batch D v2 §3's proposed alternate column set (`property_type`, `value`, `unit`, `applies_to_sports`, `applies_to_disciplines`) confirmed not deployed — drift report was authoritative.

```sql
CREATE TABLE layer0.cross_sport_properties (
  id                  SERIAL PRIMARY KEY,
  property_id         TEXT NOT NULL,
  property_name       TEXT NOT NULL,
  description         TEXT,
  scope               TEXT,
  ranking_text        TEXT,
  estimated_values    TEXT,

  -- v4: deployed adds these (NOT in v3 spec)
  source_evidence     TEXT,                            -- citation/study reference for the property
  notes               TEXT,                            -- free-text builder notes
  confidence          TEXT,                            -- v5 type-correction (D-42): qualitative confidence label (e.g. "High", "Medium", "Low"), not numeric score

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (property_id, etl_version)
);
```

**Deployed physical column order** places `confidence` after `superseded_at`. Functionally irrelevant; spec presents logical ordering for readability.

**Dropped column:** `source_text` (v3 had no entry; deployed had it; D-14 dropped it post-investigation).

---

### 4.9 `layer0.discipline_substitutes` (from 0A Discipline Substitution Map sheet) — UPDATED v4

One row per (target discipline, substitute discipline) pair. 91 entries in v10. Sport-agnostic for v1.

**D-15 (resolved with explanation FC-1a):** UNIQUE constraint includes `substitute_name` as a deliberate variant key. Two confirmed conflict rows (whitewater vs flat-water packrafting; sustained downhill vs rolling trail running) are deliberately-authored sub-format variants with distinct Fidelity ratings. Loose UNIQUE is preserved; Layer 2D substitution logic queries all variants and picks by fidelity given athlete context (locale terrain, equipment, etc.).

```sql
CREATE TABLE layer0.discipline_substitutes (
  id                  SERIAL PRIMARY KEY,
  target_id           TEXT NOT NULL,                   -- e.g. D-016
  target_name         TEXT NOT NULL,                   -- denormalized for query convenience
  substitute_id       TEXT NOT NULL,                   -- e.g. D-007
  substitute_name     TEXT NOT NULL,                   -- denormalized; acts as variant key (D-15)
  fidelity            NUMERIC NOT NULL,                -- 0.0 – 1.0
  constraints         TEXT,                            -- free text: what's covered, what's lost
  category            TEXT,                            -- e.g. "Family — vertical foot", "Cross-discipline — equipment shift"

  -- v3-promoted: which target stimuli this substitute claims to cover
  substitute_covers   TEXT[],                          -- subset of target.stimulus_components

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  -- v4: deliberate loose UNIQUE per D-15 — substitute_name acts as variant key
  UNIQUE (target_id, substitute_id, substitute_name, etl_version)
);
```

**ETL parsing rules:**
- Direct extraction from Discipline Substitution Map sheet. Schema mirrors sheet columns 1:1.
- Validate `target_id` and `substitute_id` exist in `layer0.disciplines`. Fail row + warn on broken FK.
- Validate `fidelity` ∈ [0.0, 1.0]. Reject row + warn on out-of-range.
- `substitute_covers`: read column if present; validate each element is in target's `stimulus_components`.

**Consumer guidance for Layer 2D / Layer 4 (D-15):** When multiple `(target_id, substitute_id)` rows exist with different `substitute_name`, query all and pick the variant whose context best matches athlete locale / equipment / terrain. Do not deduplicate by `(target_id, substitute_id)` alone — that destroys real coaching signal.

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

### 4.11 `layer0.sport_discipline_bridge` (derived from Sheet 3 + alias map) — UPDATED v4

**D-09 (resolved FC-1a):** Deployed shape has 8 functional columns vs v3 spec's 4. Spec missing: `discipline_name`, `role`, `default_race_time_pct_low`, `default_race_time_pct_high` — all denormalized from `sport_discipline_map` for query convenience. UNIQUE shape also differs: deployed is `(framework_sport, discipline_id, etl_version)` (not including `exercise_db_sport`).

```sql
CREATE TABLE layer0.sport_discipline_bridge (
  id                            SERIAL PRIMARY KEY,
  framework_sport               TEXT NOT NULL,
  discipline_id                 TEXT NOT NULL,
  discipline_name               TEXT NOT NULL,            -- v4: denormalized for query convenience
  exercise_db_sport             TEXT NOT NULL,            -- maps to 0B vocabulary
  role                          TEXT NOT NULL,            -- v4: denormalized from sport_discipline_map
  default_race_time_pct_low     NUMERIC,                  -- v4: denormalized
  default_race_time_pct_high    NUMERIC,                  -- v4: denormalized

  etl_version                   TEXT NOT NULL,
  etl_run_at                    TIMESTAMPTZ NOT NULL,
  superseded_at                 TIMESTAMPTZ,

  UNIQUE (framework_sport, discipline_id, etl_version)    -- v4: corrected from v3 spec
);
```

Derivation: Sheet 3 sport × discipline pairings + `sport_name_aliases.py` map (per `Post_ETL_Onboarding_Handoff.md` Round 1). The alias table `layer0.sport_name_aliases` is loaded via §4.16. Denormalized columns sourced from the parent `sport_discipline_map` row at bridge build time.

**Multiplication property (v6, post-D-46 audit):** Because §4.16 `sport_name_aliases` is intentionally one-to-many (one `exercise_db_sport` may map to multiple `framework_sport` values for sub-format splitting), the bridge produces **one row per `(framework_sport, discipline_id)` pair** for each multi-mapped `exercise_db_sport`. Consequence for consumers joining exercises through the bridge:

```
exercises (sport_exercise_map.sport_name = sdb.exercise_db_sport)
  ↓ JOIN sport_discipline_bridge sdb
  ↓ WHERE sdb.discipline_id = ANY(...)
```

When the filtered `discipline_id` exists in multiple framework sports that share the same `exercise_db_sport` (e.g., D-001 Trail Running appears under both "Adventure Racing" and "Off-Road Multisport (Nav)", both of which receive aliases from "Trail Running" exercise-DB sport), the join returns the **same exercise multiple times** — once per `(framework_sport, discipline_id)` bridge row.

**Consumer dedup requirement.** Any query that joins `sport_exercise_map` × `sport_discipline_bridge` × `exercises` and surfaces `exercise_id` to a downstream consumer must dedup post-query by `exercise_id` (or `(exercise_id, discipline_id)` when discipline attribution is tracked). This is **not** an indexing or DB-level fix — it's a contract on every consumer of the bridge.

**Known compliant consumer:** Layer 2D §5.2 dedups by `exercise_id` post-query; its rationale comment cites **both** the multi-discipline path and this framework-mapping path as co-causes (D-47 resolved 2026-05-30 — `layer2d/builder.py` §5.2 docstring expanded).

**Pattern for new consumers:**
```sql
SELECT DISTINCT ON (e.exercise_id) e.exercise_id, ...
FROM layer0.sport_discipline_bridge sdb
JOIN layer0.sport_exercise_map sxm ON sxm.sport_name = sdb.exercise_db_sport
JOIN layer0.exercises e ON e.exercise_id = sxm.exercise_id
WHERE sdb.discipline_id = ANY(%(included_discipline_ids)s)
  AND sdb.etl_version = %(version_0a)s
  AND ...;
```

Or in Python: `dedup = {row["exercise_id"]: row for row in cur.fetchall()}.values()`.

---

### 4.12 `layer0.exercises` (from 0B Exercise Master) — UPDATED v4

One row per exercise. **v3 spec at §4.12 had diverged materially from production.** v4 captures deployed shape verified 2026-05-10 (Batch B) and 2026-05-12 (D-22 promotion).

**Drift summary:**
- 4 column renames (D-01, Batch B): `equipment`→`equipment_required`, `injury_flag`→`injury_flags_text`, `progression_id`→`progression_exercise_id`, `regression_id`→`regression_exercise_id`.
- 1 column structure change (D-01, Batch B): the v3-spec split `equipment_substitutes_standard` + `equipment_substitutes_improvised` was never deployed — both live inside `equipment_substitutes JSONB`. The 🏠 prefix marker travels inside the JSONB structure.
- 1 column removed (D-01, Batch B): `novelty_text` never created (col 7 "Novelty" was excluded from prompt payloads per spec §4.10).
- 7 columns added beyond v3 spec (D-01, Batch B + B-Correction): `primary_muscles TEXT[]`, `secondary_muscles TEXT[]`, `progression_exercise_name`, `regression_exercise_name`, `sport_count INTEGER`, `terrain_required TEXT[]`, `equipment_substitutes_structured JSONB`.
- 1 NEW column added v4 (D-22, FC-1b 2026-05-12): `movement_components TEXT[]` — structured movement-constraint vocabulary for Layer 2D set-intersect.
- 1 UNIQUE contradiction resolved (D-01, Batch B): v3 spec declared column-level UNIQUE on `exercise_id` AND table-level UNIQUE on `(exercise_id, etl_version)`. The column-level was never materialized; only table-level deployed.
- Type vocabulary update (Batch B): `exercise_type = 'Technical / Skill'` is **deprecated** as of `0B-v19.B`. Pure-technique entries live in `layer0.discipline_technique_foci` (§4.15) instead.

```sql
CREATE TABLE layer0.exercises (
  id                                  SERIAL PRIMARY KEY,
  exercise_id                         TEXT NOT NULL,            -- column-level UNIQUE removed (Batch B); only table-level UNIQUE (exercise_id, etl_version)
  exercise_name                       TEXT NOT NULL,
  exercise_type                       TEXT NOT NULL,            -- 'Technical / Skill' deprecated as of 0B-v19.B (Batch B)

  movement_patterns                   TEXT[],
  primary_muscles                     TEXT[],                   -- v4: confirmed TEXT[] (D-16, Batch B Correction). ETL: string_to_array(value, ', '). Empty cells → '{}'.
  secondary_muscles                   TEXT[],                   -- v4: same shape as primary_muscles (D-16).

  equipment_required                  TEXT[],                   -- renamed from `equipment` (Batch B / D-01)
  injury_flags_text                   TEXT,                     -- renamed from `injury_flag` (Batch B / D-01). v4: retained as REFERENCE data; movement_components below is source of truth for Layer 2D.

  contraindicated_parts               TEXT[],                   -- body parts only; systemic tokens stripped during transform
  contraindicated_conditions          TEXT[],                   -- v3: derived from systemic tokens at ETL time via split_contraindicated_string()

  equipment_substitutes               JSONB,                    -- single JSONB; v3-spec split standard/improvised was never deployed. 🏠 prefix marker lives inside JSONB.
  equipment_substitutes_structured    JSONB,                    -- added by `migrate_exercises_substitutes_structured.sql` (Batch B / D-01)
  physical_proxies                    JSONB,                    -- [{id, name}, ...]

  progression_exercise_id             TEXT,                     -- renamed from `progression_id` (Batch B / D-01)
  progression_exercise_name           TEXT,                     -- added v4 (Batch B / D-01); name alongside ID
  regression_exercise_id              TEXT,                     -- renamed from `regression_id` (Batch B / D-01)
  regression_exercise_name            TEXT,                     -- added v4 (Batch B / D-01); name alongside ID

  sport_count                         INTEGER,                  -- added v4 (Batch B / D-01); denormalized from sport_exercise_map cardinality
  coaching_cues                       TEXT,                     -- excluded from plan-gen prompts; surfaced per-exercise in UI
  terrain_required                    TEXT[],                   -- added by `migrate_exercises_terrain_required.sql` (Batch B / D-01)

  movement_components                 TEXT[],                   -- v4 NEW (D-22, FC-1b 2026-05-12); canonical 11-token vocabulary. Source of truth for Layer 2D §5.3.3 set-intersect.

  etl_version                         TEXT NOT NULL,
  etl_run_at                          TIMESTAMPTZ NOT NULL,
  superseded_at                       TIMESTAMPTZ,

  UNIQUE (exercise_id, etl_version)
);

-- v4 indexes (deployed FC-1b)
CREATE INDEX idx_exercises_movement_components
  ON layer0.exercises USING GIN (movement_components);
```

**Canonical column set (24 columns total + PK `id`):**

```
exercise_id, exercise_name, exercise_type,
movement_patterns, primary_muscles, secondary_muscles,
equipment_required, injury_flags_text,
contraindicated_parts, contraindicated_conditions,
equipment_substitutes, equipment_substitutes_structured, physical_proxies,
progression_exercise_id, progression_exercise_name,
regression_exercise_id, regression_exercise_name,
sport_count, coaching_cues, terrain_required,
movement_components,
etl_version, etl_run_at, superseded_at
```

Use this as the reference when writing any future migration that touches `layer0.exercises` by column name.

**`movement_components` vocabulary (11 tokens):** mirrors Onboarding §B.3 athlete-side movement constraint enum (no anatomical fuzz). Curation reference: `D22_Curation_Reference_v2.md` (Rules 1–11 Pass 1 + Calibrations 12–15 Pass 2 + EX024/EX119 consistency precedent). 159/159 active rows populated. Migration: `migrate_exercises_add_movement_components_v1.sql`. Generator: `etl/sources/generate_movement_components_migration.py`. Known sub-threshold gap: wrist deviation (D-38), force-mapped to `Pain above specific joint angle` in 2 cases; track for v2 vocabulary review.

**Type vocabulary:**

> **Rule:** `exercise_type = 'Technical / Skill'` is **deprecated** as of `0B-v19.B`. New exercises must be typed against the load-bearing vocabulary: `Aerobic / Endurance`, `Strength`, `Power`, `Plyometric`, `Core / Stability`, `Mobility / Recovery`, `Activation / Primer`, `Interval / Tempo`, `Loaded Carry`. Pure-technique entries belong in `layer0.discipline_technique_foci` (§4.15), not `layer0.exercises`.

**Critical ETL transform (v2 carryover):**

`split_contraindicated_string()` parses the raw col 13 cell:
- Body parts → `contraindicated_parts[]`
- Systemic tokens (Cardiac, Lungs/Respiratory, GI, Skin, Core Temperature/Thermoregulation, Cognitive/Neurological) → `contraindicated_conditions[]`
- Excluded tokens (Saddle, Goggle, Blister, Grip) → dropped
- "Spine" → "Spine (general)" (rename rule)

Source xlsx is NOT modified. Derivation happens at ETL time. The xlsx may show systemic tokens in col 13 alongside body parts — this is expected and correct.

**ETL field transforms (cols 5, 6, Batch B Correction):**

The source xlsx cells for `Primary Muscles` and `Secondary Muscles` are comma-separated strings. ETL applies `string_to_array(value, ', ')` to produce the deployed `TEXT[]` column shape. Empty cells produce empty arrays (`'{}'`), not NULL.

**Process lesson (added to lessons-learned log):**

For any script that touches a live table by column name, **dump the deployed schema first**; if it disagrees with spec, deployed wins for the script and spec gets a correction patch. The pre-flight introspection block now in `update_retype_keeper_exercises.sql` (v2) is the pattern for future migrations. See §6.6 "Code is authoritative; spec catches up."

**Related drift items (D-37):** `injury_flags_text` source-data hygiene audit revealed flag-text content beyond movement constraints (cardiac, cognitive, surface-tissue, recovery-state, equipment-criticism). Carries real signal, but doesn't fit the 11-token movement-components enum. Two-part future scope: (1) classify the non-movement flag categories; (2) populate appropriate structured Layer 0 columns (e.g., `physiological_flags`, `surface_tissue_flags`). Tracked in Project_Backlog v6.

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

### 4.14 Vocabulary tables (from 0C — `Vocabulary_Audit_v3.md`) — UPDATED v6

Five tables: `layer0.body_parts`, `layer0.health_condition_categories`, `layer0.equipment_items`, `layer0.terrain_types`, `layer0.sport_specific_gear_toggles`. Schemas per v2 spec §4.12 unless flagged below.

**Source bump v2 → v3:** `Vocabulary_Audit_v3.md` reflects D-39 closure — Collarbone added to canonical body parts (51 total, was 41 in v2 header / 50 enumerated). Body parts table re-seeds at next ETL run.

**Drift notes (D-10, D-19):**

- **`terrain_types` (D-41 resolved FC-4a, 2026-05-13):** Neon `information_schema.columns` query enumerated 9 functional columns + 2 UNIQUE constraints. **Drift report correction:** §2.10 listed `simulatable` as `BOOLEAN`; deployed is `TEXT` (permits 'yes' / 'no' / 'partial' / 'conditional' / etc.). `terrain_id` is nullable; UNIQUE on `(terrain_id, etl_version)` permits multiple `terrain_id IS NULL` rows per `etl_version` (matches the 16-superseded-of-31 hand-curation history).

```sql
CREATE TABLE layer0.terrain_types (
  id                    SERIAL PRIMARY KEY,
  canonical_name        TEXT NOT NULL,            -- per Vocabulary_Audit_v3 §3 terrain subsection
  notes                 TEXT,

  -- Enrichment columns (drift report §2.10; deployed but absent from v2 spec)
  terrain_id            TEXT,                     -- canonical TRN-xxx; nullable for unlabeled rows
  category              TEXT,                     -- e.g. 'foot', 'water', 'mixed'
  requires_elevation    BOOLEAN,
  technical_surface     BOOLEAN,
  environment           TEXT,                     -- e.g. 'outdoor', 'indoor', 'mixed'
  simulatable           TEXT,                     -- v6 type-correction (was BOOLEAN in drift report): 'yes'/'no'/'partial'/'conditional'/etc.
  simulation_note       TEXT,

  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (canonical_name, etl_version),
  UNIQUE (terrain_id, etl_version)
);
```

  Active row count after superseded-filter: 15 of 31 total (16 superseded). Hand-curation provenance likely tied to `terrain_gap_rules` curation re-runs (§4.17). The dual UNIQUE constraints permit a row to lack a `terrain_id` while retaining a unique `canonical_name` — useful during curation when a terrain is added before being assigned a canonical TRN-xxx code.

- **`health_condition_categories` (D-21 resolved FC-4b, 2026-05-13):** Neon `information_schema.columns` query enumerated 6 columns + 2 constraints. **Deployed column name is `category_name`** (matching v3 §4.14 / v2 §4.12.2); the v3 §6.2 validation reference to `system_category` as a column name was the stale half of the v3 split-reference and is corrected in v7 §6.2 below. The FC-1a drift report's "no drift" claim on this table is now verified correct in shape — the deployed schema matches v2 §4.12.2 exactly, plus the standard ETL envelope. Note: `system_category` continues as a Python dataclass field name on `HealthConditionRecord` in Layer 2D / 2E (independent of SQL column name); only column-read references were stale.

```sql
CREATE TABLE layer0.health_condition_categories (
  id              SERIAL      PRIMARY KEY,
  category_name   TEXT        NOT NULL,        -- the canonical category enum (11 values per Vocabulary_Audit_v3 §2.2 / Athlete_Onboarding_Data_Spec_v2 §B.4.1)
  description     TEXT,                        -- nullable; human-readable expansion

  etl_version     TEXT        NOT NULL,
  etl_run_at      TIMESTAMPTZ NOT NULL,
  superseded_at   TIMESTAMPTZ,

  UNIQUE (category_name, etl_version)
);
```

  Active row count matches the 11-value enum (Musculoskeletal, Cardiac, Respiratory, Metabolic, Neurological, Gastrointestinal, Dermatological, Auditory, Visual, Mental Health, Other — per Vocabulary_Audit_v3 §2.2). The `description` column is populated during seed but not consumed by Layer 2D / 2E matching logic, which is symbol-based on the enum value itself.

- **`sport_specific_gear_toggles` (drift report §2.11):** matches spec ✓. No action needed.

`body_parts` and `equipment_items` schemas remain per v2 §4.12.

---

### 4.15 `layer0.discipline_technique_foci` (NEW in v4 — Batch B + B-Correction)

One row per technique focus. A focus is a coaching emphasis applied during a session — it is not a session-creating training stimulus on its own. Foci were extracted from v19 `Technical / Skill` exercises that lacked measurable load, progression, or equipment-substitution semantics.

**D-13 (resolved with Batch B Correction):** `source_exercise_ids TEXT[]` (array, not singular) and `audit_log TEXT` columns are present in deployed. The original Batch B patch described singular + missing audit_log, both incorrect.

```sql
CREATE TABLE layer0.discipline_technique_foci (
  id                          SERIAL      PRIMARY KEY,

  focus_id                    TEXT        NOT NULL,
  focus_name                  TEXT        NOT NULL,
  description                 TEXT        NOT NULL,

  -- Selection criteria
  discipline_ids              TEXT[]      NOT NULL,    -- e.g. {'D-007','D-008a'}
  applicable_session_types    TEXT[],                  -- NULL = all session types
  applicable_terrain_ids      TEXT[],                  -- NULL = all terrains
  required_equipment          TEXT[],                  -- canonical_name in equipment_items
  required_gear_toggle        TEXT,                    -- canonical_name in sport_specific_gear_toggles

  -- Coaching metadata
  athlete_level               TEXT        NOT NULL DEFAULT 'any',  -- 'beginner'|'intermediate'|'advanced'|'any'
  priority                    TEXT        NOT NULL,                -- 'Critical'|'Standard'|'Optional'
  when_to_emphasize           TEXT,
  source_exercise_ids         TEXT[],                              -- v4: array (corrected from singular in Batch B); traceability to v19 exercises
  audit_log                   TEXT,                                -- v4: added (omitted in Batch B); curation rationale

  etl_version                 TEXT        NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (focus_id, etl_version)
);

CREATE INDEX idx_dtf_disciplines ON layer0.discipline_technique_foci USING GIN (discipline_ids);
CREATE INDEX idx_dtf_active      ON layer0.discipline_technique_foci (etl_version) WHERE superseded_at IS NULL;
```

**Selection model (consumed by Layer 4):**

```
filter foci where:
  session.discipline ∈ discipline_ids
  AND (applicable_session_types IS NULL OR session.type    ∈ list)
  AND (applicable_terrain_ids   IS NULL OR session.terrain ∈ list)
  AND (required_equipment       IS NULL OR required_equipment       ⊆ session.locale.equipment)
  AND (required_gear_toggle     IS NULL OR athlete.toggles[gate]   = TRUE)
  AND athlete.level ∈ (focus.athlete_level, 'any')
selected = top 0–2 by priority, rotating across plan-week
```

**Population:** initial 35 rows at `etl_version = '0B-v19.B'`, derived from 52 dropped technique exercises (some collapsed multi-cue). One documented gap: TF-033 (Rowing) carries empty `discipline_ids` because Sports Framework v10 has no Rowing discipline. Resolve in framework v11 or re-tag the focus.

**ETL note:** Foci are not produced by ETL from a source spreadsheet. They are populated by hand-curated SQL (Batch B and successors). They participate in the standard versioning pattern (etl_version + superseded_at) but do not have an ETL pipeline source. Future foci edits live in SQL alongside curation rationale.

**Layer 4 substitution semantics:** foci are not substituted for, and they don't substitute for exercises. They are an orthogonal data type — coaching emphasis on top of an existing scheduled session.

---

### 4.16 `layer0.sport_name_aliases` (NEW in v4 — Batch D / D-12; UPDATED v5)

Bridge table aliasing between exercise-DB sport names (`AR_Exercise_Database_v19.xlsx` style) and Sports Framework canonical names (`Sports_Framework_v10.xlsx` style). Populated from `sport_name_aliases.py` map (not from xlsx). Consumed by `sport_discipline_bridge` derivation (§4.11).

**D-44 (resolved FC-3, 2026-05-13):** Neon `pg_constraint` query revealed deployed UNIQUE is `(exercise_db_sport, framework_sport, etl_version)` — three columns, not two as v4 spec had it. The v4 "one-to-one enforced inversely" claim is retracted: deployed permits one `exercise_db_sport` to map to multiple `framework_sport` values at a given `etl_version`. Per §6.6, deployed wins.

```sql
CREATE TABLE layer0.sport_name_aliases (
  id                  SERIAL PRIMARY KEY,
  exercise_db_sport   TEXT NOT NULL,            -- e.g. "Adventure Racing" (as it appears in 0B sheets)
  framework_sport     TEXT NOT NULL,            -- e.g. "Off-Road / Adventure Multisport (Nav)" (canonical in 0A Sheet 1)

  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  -- v5: deployed-verified 3-col UNIQUE (D-44 correction from v4's 2-col claim)
  UNIQUE (exercise_db_sport, framework_sport, etl_version)
);
```

**ETL loading rules:**
- Source: `etl/layer0/sport_name_aliases.py` (Python dict literal, not xlsx).
- One row per (exercise_db_sport, framework_sport) pair.
- Many-to-many allowed at a given `etl_version`. An exercise-DB sport can map to multiple framework sports, and a framework sport can receive multiple exercise-DB aliases. The 3-col UNIQUE prevents duplicate (exercise_db_sport, framework_sport) pairings within a single `etl_version`, but does **not** enforce one-to-one in either direction.
- Validate `framework_sport` exists in `layer0.sports.sport_name`. Fail row + warn on broken FK.

**Consumer impact (D-44 finding, D-46 audit complete FC-4a 2026-05-13):**

The 3-col UNIQUE permits one `exercise_db_sport` to map to multiple `framework_sport` values, and the D-46 audit confirms this is the **intentional curation pattern**. Of active alias rows, 21 distinct `exercise_db_sport` values have multi-mappings; the pattern aligns with framework sub-format splitting:

| exercise_db_sport | framework_sport mappings | Reason |
|---|---:|---|
| General Conditioning | 38 | Broadly applicable across the framework |
| Swimming | 11 | Pool / OW / marathon / swimrun / triathlon-swim / etc. |
| SkiMo | 5 | Sub-format variants (vertical/individual/sprint/team/classic) |
| Rowing | 5 | Sweep / scull / indoor erg / marathon / ocean variants |
| Triathlon | 5 | Sprint / Standard / 70.3 / Ironman / Aquathlon-style |
| XC Skiing | 4 | Classic / skate / marathon / sprint |
| Kayaking | 4 | Flat-water / whitewater / sea / sprint |
| Trail Running | 4 | Short / marathon / ultra / vertical |
| Marathon, Mountaineering, Long Distance Paddle Racing, Rock Climbing, Fixed Rope / Via Ferrata, Canoeing | 3 each | Sub-format pairs |
| 8 others (Road Cycling, MTB, Ultramarathon, Snowshoeing, SUP, Rappelling, Rope Climbing variants, etc.) | 2 each | Direct sub-format pair |

**No `sport_name_aliases.py` tightening required.** The curation is correct as-is.

**Downstream consequence (D-47, surfaced FC-4a 2026-05-13):** Because `sport_discipline_bridge` derivation (§4.11) joins through this table one-to-many, the bridge produces multiple rows for the same `(exercise_id, discipline_id)` pair when a discipline is shared across the multi-mapped framework sports. Consumer queries that join through `sport_discipline_bridge` **must dedup post-query by `exercise_id`** (or `(exercise_id, discipline_id)` when discipline attribution matters). See §4.11 for the multiplication property write-up. Layer 2D §5.2 already dedups by `exercise_id` (functional behavior correct); rationale comment in that spec is being updated to cite the framework-mapping path as a co-cause. Tracked as D-47 in `Project_Backlog_v8`.

**Consumers:**
- §4.11 `sport_discipline_bridge` ETL — joins exercise-DB sport rows to framework sport rows via this table.
- Query layer — occasional alias resolution when an athlete's onboarding answer uses an exercise-DB phrasing rather than a Sports Framework canonical name.

---

### 4.17 `layer0.terrain_gap_rules` (NEW in v4 — drift report §2.12; UPDATED v5)

**D-40 (resolved FC-3, 2026-05-13):** Neon `\d` enumerated 12 functional columns. v4 placeholder replaced with deployed schema. Earlier `ETL_Spec_v3_Corrections_2ABC_v2.md` §4.10a proposal (5 cols) is confirmed not deployed.

**Source:** Sports Framework v10 Sheet 7 (Terrain Gap Rules). Curation pairs terrain types with discipline-relevant gap implications — when an athlete lacks access to a target terrain, the table specifies whether (and how) a proxy terrain covers the training stimulus, or whether the gap is uncoverable.

```sql
CREATE TABLE layer0.terrain_gap_rules (
  id                       SERIAL      PRIMARY KEY,

  -- Target: the terrain the athlete needs but lacks
  target_terrain_id        TEXT        NOT NULL,        -- canonical TRN-xxx
  target_terrain_name      TEXT        NOT NULL,        -- denormalized for query convenience

  -- Proxy: a terrain that partially or fully covers the target stimulus
  -- Nullable: when proxy_terrain_id IS NULL, the gap is uncoverable (no acceptable proxy)
  proxy_terrain_id         TEXT,
  proxy_terrain_name       TEXT,

  -- Severity classification
  gap_severity             TEXT        NOT NULL,        -- e.g. 'Minor', 'Moderate', 'Severe', 'Uncoverable'

  -- Time to adapt when proxy is used (band; nullable when gap is uncoverable)
  adaptation_weeks_low     INTEGER,
  adaptation_weeks_high    INTEGER,

  -- Fidelity of the proxy (nullable when uncoverable). 0.0 – 1.0.
  proxy_fidelity           NUMERIC,

  -- How to make the proxy work
  proxy_methods            TEXT[]      NOT NULL,        -- non-empty array (empty for uncoverable rows)
  uncoverable_stimulus     TEXT[]      NOT NULL,        -- non-empty when proxy_terrain_id IS NULL; lists target stimuli the proxy fails to cover

  -- Coaching surfacing
  prescription_note        TEXT        NOT NULL,        -- athlete-facing short text
  audit_log                TEXT,                        -- curation rationale, citations, internal flags

  -- Versioning
  etl_version              TEXT        NOT NULL,
  etl_run_at               TIMESTAMPTZ NOT NULL,
  superseded_at            TIMESTAMPTZ,

  UNIQUE (target_terrain_id, proxy_terrain_id, etl_version)
);
```

**UNIQUE semantics:** `(target_terrain_id, proxy_terrain_id, etl_version)`. Postgres treats NULL as distinct in UNIQUE constraints, so multiple rows with `proxy_terrain_id IS NULL` for the same `target_terrain_id` are permitted. This is by design — a single uncoverable target may have multiple uncovered-stimulus rows surfacing different aspects of the gap.

**ETL parsing rules:**
- Direct extraction from Sheet 7. Schema mirrors sheet columns 1:1.
- Validate `target_terrain_id` and (when non-NULL) `proxy_terrain_id` exist in `layer0.terrain_types`. Fail row + warn on broken FK.
- When `proxy_terrain_id IS NULL`: `gap_severity` should be 'Uncoverable' (or comparable); `uncoverable_stimulus` MUST be non-empty; `proxy_methods` should be empty array (or single placeholder).
- When `proxy_terrain_id IS NOT NULL`: `proxy_fidelity` should be in [0.0, 1.0]; `adaptation_weeks_low/high` should both be populated or both NULL.

**Population:** 12 active rows in v10 baseline (per drift report §2.12). Investigate provenance of `terrain_types` 16 superseded rows alongside next curation pass — likely tied to ETL re-runs of this table's curation logic.

**Consumers:**
- Layer 2B (Terrain Classifier) — surfaces gap rows for any locale terrain ID absent from the athlete's `locale_terrain_ids`.
- Layer 4 (Plan Generation) — consumes proxy methods and prescription notes when prescribing terrain-adapted sessions.

---

### 4.18 `layer0.supplement_vocabulary` (NEW in v4 — D-26, FC-1)

Layer 0 reference data for §2E supplement coaching. 8-category enum + 4-tier evidence rating + 25 seed entries. Reference: `Supplement_Vocabulary_Spec.md`. Deployed FC-1 (2026-05-11) at `etl_version = 'supp_vocab.v1.FC1'`.

```sql
-- Schema per Supplement_Vocabulary_Spec.md; canonical columns include:
-- supplement_id, canonical_name, category (8-enum), evidence_tier (4-enum),
-- mechanism_text, dosing_protocol, timing_protocol, contraindications,
-- interactions_text, sources_citation_list, audit_log, plus versioning.

-- See Supplement_Vocabulary_Spec.md for the authoritative schema block.
```

**Cross-reference:** `Supplement_Vocabulary_Spec.md` is the spec document for this table; reproduce its schema block here in a future FC pass once finalized for stability (current entries are 25 seed rows; expansion to ~80 expected through FC-2/FC-3). Until then, this entry serves as the §4 catalog placeholder so consumers know the table exists.

**Consumer:** Layer 2E (Nutrition / Supplement query node) and Layer 5 (supplemental outputs) — both consume from this table at plan-gen time.

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
- `_filter_exercise_pool(disciplines, equipment, injuries, conditions)` — sport- and constraint-filtered exercise list. **v5:** injury matching is via structured `exercises.movement_components` set-intersect against athlete `InjuryRecord.movement_constraints` (D-22, FC-1b), per Layer2D_Spec_v1 §5.3.3. `injury_flags_text` retained as reference data, not matched against.
- `_resolve_pairing_matrix(disciplines)` — pairwise pairing ratings
- `_resolve_substitutes(target_id, available_discipline_ids)` — substitution lookup; returns all variant rows per D-15
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

Eleven typed functions, one per downstream consumer in §8. Names follow `q_layerX_consumer_payload(...)` pattern.

**Spec-of-spec rule (v5):** Where a per-layer spec document exists for a consumer (Layer 2A–2E, Layer 4, Layer 4.5), that per-layer spec is the **authoritative** source for the function signature. The signatures below mirror the per-layer spec verbatim, with "Mirror of LayerXX_Spec §3" attribution. When a per-layer spec is revised, this §5.2 block is re-synced to match. Where no per-layer spec yet exists (Layer 3 sub-prompts, Layer 5 sub-consumers), the entry is a forward-looking stub flagged accordingly; revise when the consumer spec is written.

This formalizes §6.6 ("code is authoritative; spec catches up") at the function-signature level — v4's §5.2 listed signatures that diverged from each per-layer spec, including the FC-2 "corrections" for 2C/2D which mis-modeled input shape; v5 closes that gap.

```python
# ─── Layer 2 family ──────────────────────────────────────────────────────────

# Mirror of Layer2A_Spec §3
q_layer2a_discipline_classifier_payload(
    framework_sport: str,
    athlete_discipline_overrides: dict[str, dict] | None,
    estimated_race_duration_hours: float | None,
    team_format: str | None,
    etl_version_set: dict[str, str]
) -> Layer2APayload

# Mirror of Layer2B_Spec §3
q_layer2b_terrain_classifier_payload(
    race_terrain: list[RaceTerrainEntry],
    locale_terrain_ids: list[str],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer2BPayload

# Mirror of Layer2C_Spec §3
# Inputs are locale-keyed (not flat athlete-equipment lists). Cluster fields
# carry sibling locale state for multi-locale athletes.
q_layer2c_equipment_mapper_payload(
    locale_id: str,
    locale_equipment_pool: list[str],
    cluster_locale_ids: list[str],
    cluster_gear_toggle_states: dict[str, bool],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer2CPayload

# Mirror of Layer2D_Spec_v1 §3
# Status partition (current vs resolved injuries; current vs history conditions)
# is INTERNAL to 2D (§5.1) — callers pass flat lists.
q_layer2d_injury_risk_profile_payload(
    injuries: list[InjuryRecord],
    conditions: list[HealthConditionRecord],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer2DPayload

# Mirror of Layer2E_Spec §3
q_layer2e_nutrition_baseline_payload(
    athlete_demographics: AthleteDemographics,
    health_records: HealthRecords,
    target_events: list[TargetEvent],
    lifestyle_recovery: LifestyleRecovery,
    included_disciplines: list[IncludedDiscipline],
    framework_sport: str,
    plan_management_state: PlanManagementState,
    etl_version_set: dict[str, str]
) -> Layer2EPayload

# ─── Layer 3 family ──────────────────────────────────────────────────────────
# STUB — Layer 3 design not yet started. Signature here is provisional and
# will be revised against the Layer 3 spec when it lands.
q_layer3d_injury_analysis_payload(
    exercise_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer3DPayload

# ─── Layer 4 family ──────────────────────────────────────────────────────────
# §5.3 below shows the canonical full payload shape (input + output).
# Most other consumers are subsets of this.
q_layer4_plan_generation_payload(
    framework_sport: str,
    disciplines: list[str],
    training_phase: str,
    athlete_age: int,
    equipment_available: list[str],
    active_injuries: list[InjuryRecord],
    active_conditions: list[HealthConditionRecord],
    locale_type: str,
    discipline_weighting_overrides: dict | None,
    include_exercise_pool: bool,
    max_exercises: int,
    etl_version_set: dict[str, str]
) -> Layer4Payload

q_layer4_5_validator_payload(
    framework_sport: str,
    training_phase: str,
    etl_version_set: dict[str, str]
) -> Layer45Payload

# ─── Layer 5 family ──────────────────────────────────────────────────────────
# STUBS — no Layer 5A/5B/5C per-layer specs yet. 5B will consume
# layer0.supplement_vocabulary (§4.18); signature revised when 5B spec written.
# 5A and 5C currently receive nothing directly from Layer 0 but are exposed
# for symmetry / future extension.
q_layer5a_nutrition_payload(etl_version_set: dict[str, str]) -> Layer5APayload
q_layer5b_supplements_payload(etl_version_set: dict[str, str]) -> Layer5BPayload
q_layer5c_clothing_payload(etl_version_set: dict[str, str]) -> Layer5CPayload
```

**Input record shapes** (`InjuryRecord`, `HealthConditionRecord`, `RaceTerrainEntry`, `AthleteDemographics`, `HealthRecords`, `TargetEvent`, `LifestyleRecovery`, `IncludedDiscipline`, `PlanManagementState`) are defined in `Athlete_Onboarding_Data_Spec_v2.md` and referenced verbatim by the per-layer specs. The query layer imports them; this spec does not redefine them.

**Reconciliation log (v4 → v5):**

| Function | v4 §5.2 had | v5 mirrors per-layer spec |
|---|---|---|
| 2A | 2 params | 6 params (Layer2A_Spec §3) — added overrides, race_duration, navigation, team_format |
| 2B | 1 param | 4 params (Layer2B_Spec §3) — added race_terrain, locale_terrain_ids, included_discipline_ids |
| 2C | 6 params, flat athlete-equipment shape (FC-2 form) | 6 params, locale-keyed shape (Layer2C_Spec §3) |
| 2D | 6 params with external status partition (FC-2 form) | 4 params with internal status partition (Layer2D_Spec_v1 §3) |
| 2E | 2 params | 8 params (Layer2E_Spec §3) |
| 3D, 4, 4.5, 5A/B/C | unchanged | unchanged |

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
    {"body_part": "Wrist", "side": "Left", "severity": "Recovering", "movement_constraints": ["Pain with wrist extension"]}
  ],
  "active_conditions": [
    {"name": "Mild EIB", "system_category": "Respiratory", "status": "Current"}
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
      "common_injury_patterns": ["IT band syndrome", "plantar fasciitis"],
      "body_parts_at_risk": ["Knee", "Foot/Ankle", "Hip"],
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
      "movement_components": ["Loaded squat to depth", "Single-leg balance under load"],
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

**D-15 variant-key semantics (v5 explicit).** `layer0.discipline_substitutes` UNIQUE includes `substitute_name` as a deliberate variant key (§4.9). Two confirmed conflict cases exist in v10 (whitewater vs flat-water packrafting; sustained downhill vs rolling trail running). `_resolve_substitutes` returns **all** variant rows in `candidates[]` — it does **not** deduplicate by `(target_id, substitute_id)`. Plan-gen picks the variant whose `constraints` / `category` best fit athlete locale, terrain, and equipment. Deduplicating upstream would destroy real coaching signal.

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
- For each exercise's `contraindicated_conditions[]`, verify each entry exists in `layer0.health_condition_categories.category_name`. Log mismatches as warnings.

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

### 6.6 Code is authoritative; spec catches up (NEW v4)

**Principle.** When the deployed Neon schema diverges from this spec on a live table, the deployed schema wins. Spec drift is treated as "spec lag" — to be reconciled in a periodic FC pass — not as "code bug" requiring an emergency migration. The single source of truth is the deployed schema verified via `\d layer0.<table>` and `pg_constraint` introspection.

**Rationale.** Schema drift accumulated across Batch A through D + B-Correction because each batch optimized for ship-velocity: ETL code adapted to source data shape as discovered, columns got added by migrations driven by Layer-1/2 needs, and the v3 spec was a stable document that didn't get re-cut after every change. Forcing the spec to be the source of truth would require either blocking ETL/query work on spec updates (slow) or accepting that spec edits land out-of-band (current state but unmanaged).

**Process.**

1. **For any script that touches a live table by column name:** dump the deployed schema first. If it disagrees with spec, deployed wins for the script. Pre-flight introspection block pattern: see `update_retype_keeper_exercises.sql` (v2).

2. **For new tables added by a batch:** the batch's patch document describes the new table's intent and rationale. The spec catches up at the next FC pass that revisits §4 — v4 here.

3. **For column renames or drops on existing tables:** the migration SQL is authoritative. A patch document records the rename rationale; spec catches up.

4. **For uncertainty cases** (e.g., a UNIQUE constraint shape inferred but not verified): write a "pre-v4-lock verification" block in the spec patch with the `pg_constraint` introspection query. Run it before lock; update if deployed differs.

**What this is not.**

- This is **not** a license to skip spec maintenance indefinitely. FC passes exist precisely to consolidate drift. Spec being "behind" by one batch is acceptable; being behind by 5+ batches creates fog (which is the state v3 → v4 was correcting).
- This is **not** a license to mutate deployed schema without writing a migration + patch doc. Every column add/rename/drop on a live table needs a migration SQL file in the repo and a patch markdown describing the intent. The "spec catches up" half follows; the "code is authoritative" half does not skip documentation discipline at point-of-change.

**Sign of spec catching up:** every drift item in `Project_Backlog` Cleanup category is closed with a "Resolved (FC-X)" status note and a pointer to the FC's spec revision file. v4 closes the FC-1a, FC-1, and FC-1b drift items; v5 will close whatever accumulates between now and the next consolidated pass.

---

## 7. Open items

**Active tracker:** `Project_Backlog_v9.md` is the single source of truth for cross-layer drift items, blockers, deferred work, and cleanup. This section preserves the v3 enumeration for historical continuity but does not maintain a parallel live list. Refer to the backlog for current state.

**v4 reconciliation summary — items closed since v3:**

| v3 item # | Status as of v4 | Notes |
|---|---|---|
| 5 | RESOLVED — alias map in `sport_name_aliases` table (§4.16) | Was "monitoring only" at v3; now table-of-record |
| 8 | RESOLVED — vocabulary transforms deployed | Carried forward from v3 |
| 9 | RESOLVED — `stimulus_components` populated FC-1a → FC-1b | 31/31 disciplines |
| 10 | RESOLVED — `substitute_covers` populated alongside #9 | All 91 substitution rows |
| 19 | Sub-ID naming established (D-008a/b precedent) | Process note only |

**v4 reconciliation summary — items now in `Project_Backlog_v9.md`:**

D-01 through D-47 — drift items surfaced and tracked across FC-1a / FC-1 / FC-1b / FC-2 / FC-3 / FC-4a / FC-4b. After FC-4b, all Layer 0 schema-vs-deployed reconciliation items are resolved against deployed Neon. Remaining open items are either code-side (`D-03` / `D-07` ETL parser fixes pending v20 re-run) or consumer-side / out-of-Layer-0-scope (`D-09`, `D-10`, `D-11` legacy doc-cleanup notes superseded by v4-v7 §4 rewrites; `D-17` plan-gen design; `D-47` Layer 2D rationale-comment fold-in). See backlog for canonical status.

**Original v3 open items (carried forward to backlog where still active):**

| # | Item | Status |
|---|------|--------|
| 1 | Governing Bodies (Sheet 1) | Carryover; FAQ feature deferred |
| 2 | Race / Event Formats (Sheet 1) | Carryover; Layer 1 design dependency |
| 3 | Discipline Pairing Matrix gap (D-018+) | Carryover; long-term Sheet 4 extension |
| 4 | Vertical Gain field in Layer 1 | Carryover; Layer 1 design |
| 6 | Sheet 3 col 7 deprecation | Carryover; pairs with #3 |
| 7 | Cross-Sport Properties extension | Carryover; Sheet 8 has 1 substantive row |
| 11 | Multi-substitute composition algorithm | Plan-gen design; not Layer 0 work |
| 12 | Pairing matrix D-008b values review | Not blocking; external reviewer |
| 13 | AR D-008b phase load percentage tuning | Not blocking; external validation |
| 14 | Sport-context substitution overrides | Deferred until plan-gen testing signal |
| 15 | Health Conditions UI gap | Launch-blocker; app team |
| 16, 17, 18 | Training gaps (Alpine Descent / Fencing / Swimrun) | Captured in `discipline_training_gaps`; plan-gen handles |
| 20 | Caching layer | Deferred until launch query >500ms |

**New items in v4:**

| # | Item | Action required | Owner | Status |
|---|------|-----------------|-------|--------|
| 21 | `terrain_gap_rules` schema dump | Run `\d layer0.terrain_gap_rules` in Neon; enumerate 12 functional columns + UNIQUE; rewrite §4.17 with full schema block | Next FC pass | D-10 in backlog |
| 22 | `terrain_types` 7 enrichment columns | Run `\d layer0.terrain_types`; enumerate; rewrite §4.14 sub-block | Next FC pass | D-10 in backlog |
| 23 | `sport_name_aliases` UNIQUE verification | Run `pg_constraint` query per §4.16; confirm or correct | Pre-v4-lock | D-12 in backlog |
| 24 | `cross_sport_properties` deployed-columns reconciliation | Drift report §2.7 says v3 baseline cols + 3 extras post-D-14; Batch D v2 §3 listed different functional columns. Spot-verify against Neon. | Pre-v4-lock | Open inconsistency between Batch D v2 §3 and drift report §2.7; drift report taken as authoritative |
| 25 | Batch A and Batch C patch documents | Not in project knowledge at v4 draft time; substance reconstructed from drift report. If found in repo, archive for audit history. | Audit history | Documentation cleanup |

**Patch chain documentation note (v4):** Batch A, Batch B, Batch B-Correction, Batch C, Batch D v1, Batch D v2 are the consolidated patches between v3 lock and v4. Batch B, B-Correction, D-v1, D-v2 are in project knowledge. Batch A and Batch C were not at v4 draft time; their substance was inferred from `Layer0_Deployed_Schema_and_Drift_Report.md` v2 which catalogs the same drift items table-by-table. If Batch A/C documents are recovered, they should be archived in repo for audit history but no new spec change is expected.

---

## 8. Downstream prompt consumption reference

What Layer 0 context each layer receives and from which tables. v4 reflects corrections from `ETL_Spec_v3_Corrections_2ABC_v2.md` + Batch B + Layer 2D `v1` reads.

| Layer | Receives from Layer 0 | Tables queried |
|-------|----------------------|----------------|
| 2A (Discipline Classifier) | Sport classifications + planning flags + discipline list with roles & race-time bands | sports, disciplines, **sport_discipline_bridge** |
| 2B (Terrain Classifier) | Terrain vocabulary + gap rules | terrain_types, **terrain_gap_rules** |
| 2C (Equipment Mapper) | Equipment vocabulary, gear toggles, exercise pool filtered by discipline only; structured substitutes for Tier 2 resolution | equipment_items, sport_specific_gear_toggles, sport_exercise_map, exercises (`equipment_substitutes_structured`), **sport_discipline_bridge** |
| 2D (Injury Risk Profile) | Per-exercise `movement_components` + `contraindicated_parts/conditions`; per-discipline `body_parts_at_risk`; substitution candidates; body part vocabulary | exercises (`movement_components`, `contraindicated_*`), disciplines (`body_parts_at_risk`, `common_injury_patterns`), discipline_substitutes, body_parts |
| 2E (Nutrition Baseline) | Supplement vocabulary | **supplement_vocabulary** |
| 3D (Injury Analysis) | Contraindicated parts AND conditions; injury flags per exercise; vocabularies | exercises, body_parts, health_condition_categories |
| 4 (Plan Generation) | Full sport context + classifications + exercise pool (equipment + injury + condition filtered) + phase load bands + weekly hour targets + training gaps + substitution candidates + technique foci eligible for each scheduled session | All tables via query layer + **discipline_technique_foci** |
| 4.5 (Validator) | Sport rule sets: ramp rates, phase durations, pairing rules, taper norms, cross-sport properties | sports, disciplines, discipline_pairing, phase_load_allocation, cross_sport_properties |
| 5A (Nutrition) | None — operates on plan output + athlete data | — |
| 5B (Supplements) | Supplement vocabulary | **supplement_vocabulary** |
| 5C (Clothing) | None — operates on weather + athlete history | — |

**v4 changes vs v3:**
- 2A: added `sport_discipline_bridge` (per corrections doc).
- 2B: added `terrain_gap_rules` (per corrections doc + §4.17 new table).
- 2C: added `sport_discipline_bridge` and `equipment_substitutes_structured` column reference (per corrections doc + Open Item H/K resolution).
- 2D: full revision — `movement_components` + `body_parts_at_risk` set-intersect path per Layer2D_Spec_v1; replaces v3's keyword-heuristic narrative.
- 2E: added `supplement_vocabulary` (per §4.18 new table).
- 4: added `discipline_technique_foci` (per Batch B).
- 5B: added `supplement_vocabulary` (per §4.18).

---

## 9. Future work

- **Plan-gen consumer build.** Substitution composition algorithm built in plan-gen, reading populated `stimulus_components` + `substitute_covers`.
- **Caching layer.** When latency demands it.
- **Sport-context substitution overrides.** v2 if plan-gen testing shows v1 too coarse.
- **Sheet 4 pairing matrix expansion** to D-018+. Long-term, deprecates Sheet 3 col 7 fallback.
- **Cross-sport properties expansion.** ECCENTRIC_LOAD, STRENGTH_PRIMACY, TECHNICAL_TERRAIN_DIFFICULTY, NAVIGATION_DEMAND noted in Sheet 8 as candidates.
- **D-37: `injury_flags_text` non-movement signal extraction.** Cardiac, cognitive, surface-tissue, recovery-state, equipment-criticism content currently lives in free text; future work classifies and promotes to structured columns.
- **D-38: 12th movement-components token (wrist deviation).** Promote when threshold of ≥5 affected exercises surfaces in future curation.

---

*End of v4 spec. Successor: when v5 lands, supersede this doc with what changed. Don't overwrite.*

