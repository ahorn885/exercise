# FC-1a Pass 1 Bundle — v1

**Date:** 2026-05-11
**Session:** FC-1a — ETL bug fixes batch
**Predecessor:** `D26_Done_D22_Pass1_Done_FC1a_Kickoff_Handoff.md`

This bundle is the consolidated output of the FC-1a pass: new versioning rule, spec patches, investigation queries, decisions, and mechanically-applicable file edits. SQL migrations ship as separate files:
- `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` (D-04)
- `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql` (D-06)
- `cleanup_phase_load_allocation_aggregators_v1.sql` (D-05 cleanup half)

---

## §0. New rule — file versioning convention

### The problem this solves
When two files share the same name in project knowledge, retrieval picks one without telling Claude or Andy which. This produced the IJKL-drift event resolved last session, and a smaller version of the same problem this session (Andy had to delete a conflicting Project_Backlog duplicate before the post-cleanup state matched the handoff's claims).

### Rule text (proposed)

> **Rule #12 — File versioning convention.** Every materially revised file is saved with a numeric version suffix before the extension: `<base_name>_v<N>.md`, `<base_name>_v<N>.sql`. The current authoritative version is the highest `N`. Prior versions remain in project knowledge as the read-only history; they are never deleted in the same session they are superseded. Cross-references in spec docs cite the **base filename without version** as a logical pointer; Claude resolves the pointer to the highest-`N` file present on each access. Handoff docs may cite specific versioned filenames when the precise historical state matters (e.g., "applied per `Layer0_ETL_Spec_v3_Patch_Batch_B_v1.md`"). This rule is companion to rules #9 (session-start verification) and #10 (session-end verification).

### Recommended adds

**Memory rule #12** — exact text:
```
File versioning convention — every materially revised file saves with a numeric version suffix (Control_Spec_v1.md, _v2.md, etc.). Current authoritative = highest N. Old versions stay in project knowledge as read-only history; never deleted in the supersession session. Cross-references cite the unversioned base name as a logical pointer.
```

**Control_Spec §10 — new bullet:**
```
- **File versioning convention.** Every materially revised file is saved with a numeric version suffix: `<base_name>_v<N>.md` / `<base_name>_v<N>.sql`. Current authoritative = highest N. Old versions stay in project knowledge until intentionally archived. Spec docs cross-reference the unversioned base name as a logical pointer; handoff docs may cite specific versions when historical state matters. Rule #12; companion to #9 / #10 / #11.
```

### Decisions surfaced — see §X.1 below
The rule has four sub-decisions Andy needs to confirm before it becomes binding. Surfaced in §X (Decisions) at the end of this doc.

---

## §1. FC-1a item status

| ID | Status | Deliverable | Blocks on |
|---|---|---|---|
| D-12 | ✅ Drafted | Spec patch (§2 below) | Andy review |
| D-16 | ✅ Drafted | Spec patch (§4 below) | Andy review |
| D-04 | ✅ Drafted | `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` | Andy runs in Neon |
| D-06 | ✅ Drafted | `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql` | Andy runs in Neon |
| D-05 | ✅ Partial — cleanup SQL drafted, ETL code patch specified | `cleanup_phase_load_allocation_aggregators_v1.sql` + §6 ETL code patch | Andy runs SQL; CC applies ETL code patch |
| D-13 | ✅ Drafted | Spec patch correction (§3 below) | Andy review |
| D-07 | ⏳ Investigation queries drafted | §7 below | Andy runs queries → results back to Claude |
| D-08 | ⏳ Investigation queries drafted | §8 below | Andy runs queries → results back to Claude |
| D-14 | ⏳ Investigation query + decision proposal | §9 below | Andy runs query + makes decision |
| D-15 | ⏳ Investigation query + decision proposal | §10 below | Andy runs query + makes decision |
| D-03 | ⏳ Decision proposal | §11 below | Andy decision |

Items 1–6 are concrete deliverables ready for review/deploy. Items 7–11 surface things Andy needs to either run or decide. Recommended flow: review §2/§3/§4 spec patches → run the 3 SQL migrations (D-04, D-06, D-05 cleanup) → run the 4 investigation queries (D-07, D-08, D-14, D-15) → make the 4 decisions at end of doc → CC applies D-05 ETL code patch.

---

## §2. D-12 — `sport_name_aliases` schema block for v4

**Patch target:** Insert as new §4.x in `Layer0_ETL_Spec_v4.md`. For interim use, this content lives in a new patch doc (`Layer0_ETL_Spec_v3_Patch_Batch_D_v1.md`) that FC-2 folds into v4.

**Sourcing:** Drift Report §2.13 + spec v3 §6.2 mention.

### 4.x `layer0.sport_name_aliases` (NEW in v4 — was undocumented in v3)

Bridge table aliasing between exercise-DB sport names (`AR_Exercise_Database_v17.xlsx` style) and Sports Framework canonical names (`Sports_Framework_v10.xlsx` style). Populated from `sport_name_aliases.py` map (not from xlsx). Consumed by `sport_discipline_bridge` derivation (§4.11).

```sql
CREATE TABLE layer0.sport_name_aliases (
  id                  SERIAL PRIMARY KEY,
  exercise_db_sport   TEXT NOT NULL,            -- e.g. "Adventure Racing"  (as it appears in 0B sheets)
  framework_sport     TEXT NOT NULL,            -- e.g. "Off-Road / Adventure Multisport (Nav)"  (canonical in 0A Sheet 1)

  -- versioning
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,

  UNIQUE (exercise_db_sport, etl_version)
);
```

**ETL loading rules:**
- Source: `etl/layer0/sport_name_aliases.py` (Python dict literal, not xlsx)
- One row per (exercise_db_sport, framework_sport) pair
- Many-to-one allowed: one framework_sport may receive multiple exercise_db_sport aliases
- One-to-one enforced in the other direction by UNIQUE constraint — an exercise_db_sport at a given etl_version maps to exactly one framework_sport (no ambiguity)

**Consumers:**
- §4.11 `sport_discipline_bridge` ETL — joins exercise-DB sport rows to framework sport rows via this table
- Query-layer: occasional alias resolution when an athlete's onboarding answer uses an exercise-DB phrasing

**Open assumption flagged:** the UNIQUE clause is inferred from the deployed schema description ("2 functional columns + versioning"). Should be verified against the deployed `CREATE TABLE` statement before v4 lock. Query to confirm:
```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'layer0.sport_name_aliases'::regclass
  AND contype IN ('u','p');
```
If the deployed UNIQUE clause differs, update the spec block to match deployed (deployed wins per the "spec catches up to code" pattern in `Layer0_ETL_Spec_v3_Patch_Batch_B_v1.md`).

---

## §3. D-13 — Batch B patch correction (`discipline_technique_foci`)

**Patch target:** Apply as a correction patch doc (`Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md`) that FC-2 reads alongside the original Batch B patch when writing v4.

**Sourcing:** Drift Report §2.14.

### Corrections to apply when folding Batch B into v4

Batch B patch §4.15 declares the column as singular `source_exercise_id TEXT`. Deployed shape is **array** `source_exercise_ids TEXT[]`. Batch B also omits the `audit_log TEXT NULL` column that exists in the deployed table.

### Corrected schema block (use this for v4)

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
  athlete_level               TEXT        NOT NULL DEFAULT 'any',
  priority                    TEXT        NOT NULL,
  when_to_emphasize           TEXT,
  source_exercise_ids         TEXT[],                  -- ★ ARRAY (was singular in Batch B patch)
  audit_log                   TEXT,                    -- ★ ADDED (missing from Batch B patch)

  etl_version                 TEXT        NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (focus_id, etl_version)
);
```

Two delta tokens vs Batch B patch:
1. `source_exercise_ids TEXT[]` — plural, array. (Batch B patch said `source_exercise_id TEXT`.)
2. `audit_log TEXT` — present.

Indexes from Batch B carry over unchanged.

**Population note:** the 35 rows at `etl_version = '0B-v19.B'` already match this corrected shape on disk. Correction is purely a documentation patch — no migration needed.

---

## §4. D-16 — `exercises.primary_muscles` / `secondary_muscles` in v4 §4.12

**Patch target:** Folds into the §4.12 rewrite that's already happening in `Layer0_ETL_Spec_v3_Patch_Batch_B_v1.md`. This patch adds the missing **type confirmation** and **transform rule**.

**Sourcing:** Drift Report §1 (Open Item R resolved) + §2.1.

### Confirmation: both columns are `TEXT[]`

The Batch B patch §4.12 "Columns added" table currently lists:
| `primary_muscles` | TEXT (or TEXT[]) | source col 5 |
| `secondary_muscles` | TEXT (or TEXT[]) | source col 6 |

The "or TEXT[]" hedge is resolved by Drift Report §1: **both are `TEXT[]`**. v20 xlsx keeps cells as comma-separated strings (`"Quadriceps, Glutes"`); ETL splits via `string_to_array(value, ', ')`.

### Replacement rows for Batch B patch §4.12 "Columns added" table

| Deployed | Type | Notes |
|---|---|---|
| `primary_muscles` | `TEXT[]` | Source col 5. ETL transform: `string_to_array(value, ', ')`. xlsx keeps comma-separated string per cell. |
| `secondary_muscles` | `TEXT[]` | Source col 6. ETL transform: `string_to_array(value, ', ')`. Same shape as primary_muscles. |

### Addendum to Batch B patch §4.12 "Canonical column set (deployed)"

No change — the list at line 116–125 already names `primary_muscles, secondary_muscles` in the correct order. The 24-column total is correct.

### v4 §4.12 transform documentation

When the v4 §4.12 schema block is written, add an explicit transform note:

> **ETL field transforms (cols 5, 6):** the source xlsx cells for `Primary Muscles` and `Secondary Muscles` are comma-separated strings (e.g., `"Quadriceps, Glutes, Adductors"`). ETL applies `string_to_array(value, ', ')` to produce the deployed `TEXT[]` column shape. Empty cells produce empty arrays (`'{}'`), not NULL.

---

## §5. D-04 and D-06 — pure-rename migrations

Both items are pure schema renames with no data impact. SQL files ship as standalone:

- `migrate_phase_load_allocation_rename_phase_prefix_v1.sql`
- `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql`

Both files use the house style: `BEGIN` / `COMMIT`, pre-flight introspection that determines what state the table is in, conditional `RENAME COLUMN` only if needed, verify block with `RAISE EXCEPTION` on failure. Idempotent — safe to re-run.

**Andy's deploy steps:**
1. Upload both SQL files to `etl/sources/` in the repo (CC commits).
2. Open Neon SQL editor, paste each file in turn, run.
3. Confirm NOTICE messages indicate "already at target state" or "rename complete". If `RAISE EXCEPTION` fires, paste the error message back and we'll diagnose.

**Spec impact:**
- D-04: spec v3 §4.5 currently declares `phase_base_pct_low`, ..., `phase_taper_pct_high` (8 cols with `phase_` prefix). v4 spec rewrite drops the prefix. Until v4 lands, the rename in Batch D patch (§2 above) is the working reference. Spec patch text: see §13 file-edits below.
- D-06: spec v3 §4.5.1 declares `hours_low`, `hours_high` — already matches the post-rename target. No spec change needed.

---

## §6. D-05 — Aggregator-row filter promoted into ETL

D-05 has two halves: the deployed cleanup (one-shot SQL, already drafted) and the ETL code change (described here for CC).

### Half 1: Cleanup SQL

`cleanup_phase_load_allocation_aggregators_v1.sql` soft-supersedes the 33 misrouted aggregator rows currently in `phase_load_allocation`. Active queries (`WHERE superseded_at IS NULL`) will stop returning them; history is preserved. **Andy runs in Neon.**

### Half 2: ETL code patch (for Claude Code to apply)

**Target file (most likely):** `etl/layer0/extract_phase_load_allocation.py` or whatever module loads Sheet 5 into `phase_load_allocation`. CC will need to locate the actual file in the repo.

**Patch description:**

Spec v3 §4.5 ETL rule 1 says: *"Skip aggregator rows where `discipline_name` contains `WEEKLY TOTAL TARGET`. Their notes are extracted into `layer0.phase_load_weekly_totals` (§4.5.1) instead."*

The current extractor does not apply this filter. The rule needs to land at the row-emission stage, before the row is inserted into `phase_load_allocation`. The same rule already exists implicitly in the `phase_load_weekly_totals` extractor (which DOES filter to aggregator rows only) — we just need the inverse filter in the discipline-row extractor.

**Pseudocode insertion (CC adapts to actual module style):**

```python
# After parsing each row from Sheet 5:
discipline_name = row.get('Discipline')  # or whatever the source column is
if discipline_name and 'WEEKLY TOTAL TARGET' in discipline_name:
    continue  # routed to phase_load_weekly_totals, not phase_load_allocation
```

CC should add a unit test that confirms a fixture row containing `'WEEKLY TOTAL TARGET'` in its discipline_name is not emitted into the `phase_load_allocation` row stream.

### Half 3: Retire the query-layer defensive filter

Per Control_Spec §8.2, the standing rule "D-05 aggregator filter until ETL fix lands" is in effect across the query layer. Once both halves above land, the existing defensive filters (`AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`) become redundant but are harmless. **Recommendation:** leave them in place until FC-2 spec rewrite. Cost of removal: low. Cost of keeping: zero, plus protection if the ETL fix regresses. Control_Spec §8.2 should be updated to flip "until ETL fix lands" to "removed — ETL now drops at load time."

Mechanically-applicable §8.2 edit text is in §13 below.

---

## §7. D-07 — 4 sports missing `phase_load_weekly_totals` rows

**Problem:** 33 source aggregator rows × 4 phases = 132 expected. Deployed has 116 = 29 sports × 4 phases. **4 sports' worth of weekly_totals are missing.**

Drift Report §2.4 names them as **plausible candidates** (from the rerun-triage handoff): Off-Road / Adventure Multisport (Non-Nav), Open Water Marathon Swimming (10km), Open Water Marathon Swimming (25km), Swimrun. Need to confirm.

### Investigation queries

**Query 1 — which sports are PRESENT in weekly_totals:**
```sql
SELECT sport_name, COUNT(*) AS phase_count
FROM layer0.phase_load_weekly_totals
WHERE superseded_at IS NULL
GROUP BY sport_name
ORDER BY sport_name;
```
Expected: ~29 sports, each with phase_count=4. Any sport with phase_count<4 indicates a partial parse.

**Query 2 — which sports SHOULD have weekly_totals (per phase_load_allocation source data):**
```sql
SELECT DISTINCT sport_name
FROM layer0.phase_load_allocation
WHERE superseded_at IS NULL   -- after D-05 cleanup, this excludes the 33 aggregator rows
ORDER BY sport_name;
```
Run this **after** D-05 cleanup. Result is the set of sports that have discipline rows. Compare to query 1 result — the diff is the missing sports.

**Query 3 — direct comparison (post-D-05):**
```sql
WITH expected AS (
  SELECT DISTINCT sport_name FROM layer0.phase_load_allocation WHERE superseded_at IS NULL
),
present AS (
  SELECT DISTINCT sport_name FROM layer0.phase_load_weekly_totals WHERE superseded_at IS NULL
)
SELECT 'MISSING' AS status, e.sport_name
FROM expected e LEFT JOIN present p ON e.sport_name = p.sport_name
WHERE p.sport_name IS NULL
UNION ALL
SELECT 'UNEXPECTED' AS status, p.sport_name
FROM present p LEFT JOIN expected e ON p.sport_name = e.sport_name
WHERE e.sport_name IS NULL
ORDER BY status, sport_name;
```

**Once we have the 4 sport names back, next step is** look at their `WEEKLY TOTAL TARGET` rows in `Sports_Framework_v10.xlsx` Sheet 5 directly. Three possible causes for parse failure:
1. The `Notes / Conditions` cell uses formatting the §3.3 regex doesn't match (e.g., different dash character, missing "hrs" suffix, ranges in different units).
2. The sport doesn't actually have a `WEEKLY TOTAL TARGET` row — it was omitted from the source.
3. The row exists but the discipline_name spelling differs (e.g., trailing whitespace, case mismatch).

Cause 1 is a parser-rule extension. Cause 2 is a source-data fix. Cause 3 is a normalizer fix. Decision branches once we know which.

---

## §8. D-08 — 3 missing `sport_discipline_map` rows

**Problem:** Source xlsx Sheet 3 has 73 data rows (72 `INCLUDED` + 1 `EXCLUDED`). Deployed has 70. **3 rows missing.**

The discrepancy can't be all "EXCLUDED dropped" since the source only has 1 EXCLUDED row. Drift Report §2.5 notes the same.

Handoff names the candidates: Long Distance / Endurance Cycling (-2), Triathlon (-1). Confirm.

### Investigation queries

**Query 1 — row counts per sport:**
```sql
SELECT sport_name, COUNT(*) AS discipline_count
FROM layer0.sport_discipline_map
WHERE superseded_at IS NULL
GROUP BY sport_name
ORDER BY sport_name;
```

**Query 2 — which (sport, discipline) pairs are missing?**

This needs comparison against the source. Easiest path: paste the result of Query 1 back to Claude, and Claude cross-references against `Sports_Framework_v10.xlsx` Sheet 3 to identify the missing pairs. The xlsx isn't reliably introspected from the chat side but is uploaded to the project, so Andy could also run a manual check from his end.

**Query 3 — applicability filter check:**
```sql
SELECT applicability, COUNT(*) AS n
FROM layer0.sport_discipline_map
WHERE superseded_at IS NULL
GROUP BY applicability
ORDER BY n DESC;
```
If `applicability='EXCLUDED'` has 0 rows, ETL is silently dropping them — spec says load all rows and let query layer filter. If it has 1 row, the 3-row gap is unexplained and we need Query 2's comparison.

---

## §9. D-14 — `cross_sport_properties.source_text` dedup decision

**Problem:** Deployed has both `source_evidence TEXT` and `source_text TEXT` columns. Drift Report §2.7: "duplicates source_evidence semantically; likely leftover from an earlier ETL run." Only 1 row in the table.

### Investigation query
```sql
SELECT property_id, property_name,
       source_evidence,
       source_text
FROM layer0.cross_sport_properties
WHERE superseded_at IS NULL;
```

### Proposal pending the data check
- If both columns hold the same content: **drop `source_text`** (it's the redundant one per drift report inference). Migration: `ALTER TABLE layer0.cross_sport_properties DROP COLUMN source_text;`
- If they hold different content: keep both, document semantic difference in v4 spec §4.8, and back-fill the missing one consistently. The drift report calls source_text "suspicious" — most likely outcome is they're identical or `source_text IS NULL`.

Decision pending — surfaced in §X below.

---

## §10. D-15 — `discipline_substitutes` UNIQUE constraint review

**Problem:** Spec v3 §4.9 says `UNIQUE (target_id, substitute_id, etl_version)`. Deployed has `UNIQUE (target_id, substitute_id, substitute_name, etl_version)` — looser. The looser constraint allows two rows for the same (target, substitute) pair if `substitute_name` differs across them.

### Investigation query
```sql
-- Are there any (target_id, substitute_id, etl_version) groups that have
-- more than one row under the looser deployed UNIQUE? If yes, tightening
-- would violate.
SELECT target_id, substitute_id, etl_version, COUNT(*) AS n,
       ARRAY_AGG(substitute_name ORDER BY substitute_name) AS names
FROM layer0.discipline_substitutes
WHERE superseded_at IS NULL
GROUP BY target_id, substitute_id, etl_version
HAVING COUNT(*) > 1
ORDER BY n DESC, target_id;
```

### Proposal pending the data check
- If query returns 0 rows: **tighten deployed to match spec.** Migration drops the loose constraint, adds the tight one. Spec stays as-is.
- If query returns >0 rows: **investigate before tightening.** The conflict rows are denormalization errors that need normalizing (probably substitute_name needs to be looked up consistently from `disciplines.discipline_name` rather than carried per-row).

### Tightening migration (apply only after the query returns 0 conflicts)
```sql
BEGIN;

ALTER TABLE layer0.discipline_substitutes
  DROP CONSTRAINT IF EXISTS discipline_substitutes_target_id_substitute_id_substitute_name_etl_version_key;
-- ☝ confirm constraint name from \d layer0.discipline_substitutes in Neon first

ALTER TABLE layer0.discipline_substitutes
  ADD CONSTRAINT discipline_substitutes_target_sub_etl_unique
  UNIQUE (target_id, substitute_id, etl_version);

DO $$
BEGIN
  -- Verify the new constraint is in place
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='layer0.discipline_substitutes'::regclass
      AND conname='discipline_substitutes_target_sub_etl_unique'
  ) THEN
    RAISE EXCEPTION 'D-15 verify failed — new UNIQUE constraint not added';
  END IF;
  RAISE NOTICE 'D-15 verify OK';
END $$;

COMMIT;
```

Don't run the migration above until Andy decides — surfaced in §X.

---

## §11. D-03 — Build-or-drop on `is_conditional` / `vertical_gain_notes`

**Context:** Spec v3 §4.5 declares both. ETL never built them. Both are derivable from existing source data:
- `is_conditional`: TRUE if `Role` contains `(*Conditional)` OR `Notes / Conditions` starts with `*CONDITIONAL`.
- `vertical_gain_notes`: parsed from Notes when sport ∈ {Skimo, Mountain Running, XC Skiing, Fell Running}.

### Options

**Option A — Build (retain in v4 spec).**
Pros: structured queryable fields. Plan-gen and Layer 2C can filter on `is_conditional` directly rather than re-deriving from raw notes per query. `vertical_gain_notes` lifted into a discrete field is easier for Layer 4 to inject as plan context.
Cons: requires ETL code change (parser additions in the phase_load_allocation extractor) before v20 re-run. Today's queries still need to fall back to raw notes parsing until v20 ships.

**Option B — Drop from v4 spec.**
Pros: no code change. Spec stops claiming fields that don't exist.
Cons: query layer / plan-gen carries the parsing logic indefinitely. The `*CONDITIONAL` filter rule becomes a code-side convention rather than a structured column.

### Recommendation: Option A — Build.
The derivation logic is simple and the structured form is cheaper to consume than re-parsing notes everywhere. The risk (spec drifts ahead of code again) is real but mitigable with an explicit spec footnote: *"Scheduled for v20 ETL re-run; not yet deployed — do not query as available until v20 ships."*

Actual code change is a CC task, not FC-1a. FC-1a deliverable for D-03 is the **decision**, not the implementation.

Decision surfaced in §X.

---

## §X. Decisions to surface for Andy

Four decision blocks, in order of how blocking they are.

### X.1 — Versioning rule sub-decisions (most blocking; everything below this depends on it)

**Q1. When superseded, does the new version take the tag or does the old version get renamed?**
- **Option A (Andy's literal request):** New version takes the tag. `Control_Spec.md` → on next save becomes `Control_Spec_v1.md`. Subsequent: `_v2`, `_v3`. Cross-references must cite the current versioned filename.
- **Option B (lower-friction alternative):** New version keeps the unversioned name; old version is renamed to add `_v<N>` at the moment of supersession. `Control_Spec.md` always = latest. Old versions accumulate as `Control_Spec_v1.md`, `Control_Spec_v2.md`, etc. Cross-references stay stable.

→ **Claude's recommendation: Option B.** Stable cross-references, no per-edit reference churn. The IJKL-drift event was about duplicate filenames colliding at upload time — Option B keeps the canonical name pinned and only versions the archive.

**Q2. What counts as a "new version" trigger?**
- **Option X:** Every save / every material edit (high friction; full history).
- **Option Y:** Only material restructures or content rewrites (lower friction; partial history).

→ **Claude's recommendation: Option Y.** Per-keystroke versioning floods project knowledge.

**Q3. Are old versions retained or archived?**
- **Option P:** Kept alongside current in project knowledge.
- **Option Q:** Archived (moved by Andy out of project knowledge after some retention period).

→ **Claude's recommendation: Option P for now.** Andy controls project knowledge upload; can clean periodically. Q can come later if clutter becomes a problem.

**Q4. Scope of rule.**
- Spec docs: clearly yes (this is the source of the conflict).
- SQL files: already follow `migrate_X_v1.sql` convention; rule already complied.
- Handoff docs: sequential per session, less collision-prone; existing `_v1`-`_v8` convention complies.
- **Recommendation: rule applies universally.** Existing conventions for SQL/handoffs already comply; no behavior change.

### X.2 — D-03 build-or-drop

→ **Recommendation:** Build (Option A). Retain `is_conditional` and `vertical_gain_notes` in v4 §4.5 with a "not-yet-deployed; ships v20" footnote.

Alternative: drop both from v4 spec. Acceptable if Andy thinks the parsing logic belongs in query-layer code rather than the data model.

### X.3 — D-14 `cross_sport_properties.source_text` dedup

Run the query in §9 first. Then choose:
- If `source_text` content == `source_evidence` content (or is NULL): **drop `source_text` column.**
- If they hold different content: investigate provenance before deciding.

→ **Claude's recommendation pending data:** drop, because drift report flags source_text as a likely leftover and the 1-row population makes the risk near-zero.

### X.4 — D-15 `discipline_substitutes` UNIQUE tightening

Run the query in §10 first. Then choose:
- If 0 conflict rows: **tighten the constraint.** Migration in §10.
- If >0 conflict rows: investigate before tightening.

→ **Claude's recommendation pending data:** tighten. Spec's constraint matches the intended semantics (substitute_name is denormalized and shouldn't disambiguate the pair).

---

## §13. File edits to existing files (mechanically-applicable, rule #11)

Per the new versioning rule (once Andy confirms Option B), the editing pattern is: apply str_replace edits to the in-place `Control_Spec.md` / `Project_Backlog.md`, then upload as the new authoritative version under the same name. If Andy chooses Option A instead, the same edits apply but the upload name becomes `Control_Spec_v1.md` / `Project_Backlog_v1.md` (or whatever the next version number is — the existing files have no `_v` suffix yet).

### Edit 1 — `Control_Spec.md` §10 (add file-versioning rule bullet)

```
old_string:
- **Handoffs that defer file edits include the edits as mechanically-applicable instructions** — str_replace-style `old_string` / `new_string` blocks, or "replace section X with verbatim content [...]". Narrative summaries like "update §3 of Control_Spec" without the new text are not acceptable. Failure mode is loud (str_replace mismatch) rather than silent drift. See memory rule #11; companion to rules #9 (session-start verification) and #10 (session-end verification).
- **Project_Backlog.md is the only deferred-work tracker.** Per-spec open items reference back to it.

new_string:
- **Handoffs that defer file edits include the edits as mechanically-applicable instructions** — str_replace-style `old_string` / `new_string` blocks, or "replace section X with verbatim content [...]". Narrative summaries like "update §3 of Control_Spec" without the new text are not acceptable. Failure mode is loud (str_replace mismatch) rather than silent drift. See memory rule #11; companion to rules #9 (session-start verification) and #10 (session-end verification).
- **File versioning convention.** Every materially revised file is saved with a numeric version suffix: `<base_name>_v<N>.md` / `<base_name>_v<N>.sql`. Current authoritative = highest N. Old versions stay in project knowledge until intentionally archived. Spec docs cross-reference the unversioned base name as a logical pointer; handoff docs may cite specific versions when historical state matters. Rule #12; companion to #9 / #10 / #11.
- **Project_Backlog.md is the only deferred-work tracker.** Per-spec open items reference back to it.
```

### Edit 2 — `Control_Spec.md` §9 Layer 1 bullet (D-26 stale status)

```
old_string:
- ✅ `Supplement_Vocabulary_Spec.md` — Layer 0 supplement_vocabulary table schema + 25 seed entries (drafted; D-26 FC-1 implementation pending)

new_string:
- ✅ `Supplement_Vocabulary_Spec.md` — Layer 0 `supplement_vocabulary` table schema + 25 seed entries (drafted; D-26 deployed 2026-05-11 — table live in Neon dev with 25 active rows at `supp_vocab.v1.FC1`)
```

### Edit 3 — `Control_Spec.md` §8.2 (retire D-05 standing rule — apply AFTER D-05 ETL code patch deploys)

```
old_string:
- **D-05 aggregator filter** until ETL fix lands (will retire in FC-1 per file edits above).

new_string:
- **D-05 aggregator filter — REMOVED (FC-1a, 2026-05-11).** ETL now drops `WEEKLY TOTAL TARGET` rows at load time. Existing query-layer filters are now redundant but harmless; leave in place until FC-2 spec rewrite to keep diffs scoped.
```

Apply only after CC commits the ETL code patch AND Andy verifies the next ETL run doesn't re-introduce aggregator rows. Until both, keep the standing rule as-is.

### Edit 4 — `Project_Backlog.md` D-04 resolution

```
old_string:
- D-04 — drop `phase_` prefix from `phase_load_allocation` band columns (spec rename: `phase_base_pct_low → base_pct_low`, etc.; ETL already produces unprefixed names per Drift Report §2.3)

new_string:
- ~~D-04~~ — ✅ Resolved 2026-05-11 (FC-1a). Idempotent rename migration `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` confirms deployed state matches spec target (8 unprefixed band columns). Spec patch in Batch D landed (Layer0_ETL_Spec_v3_Patch_Batch_D_v1.md).
```

Locate this in the §"FC-1 work plan" section of the backlog. The exact line text may differ slightly — apply by content match.

### Edit 5 — `Project_Backlog.md` D-06 resolution

```
old_string:
- D-06 — rename `phase_load_weekly_totals.hours_low/high` from deployed `weekly_low_hours/weekly_high_hours` (spec already correct; deployed catches up)

new_string:
- ~~D-06~~ — ✅ Resolved 2026-05-11 (FC-1a). Rename migration `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql` applied; deployed columns now `hours_low`, `hours_high` matching spec §4.5.1.
```

### Edit 6 — `Project_Backlog.md` D-12, D-13, D-16 resolution

After each of these spec patches uploads as `Layer0_ETL_Spec_v3_Patch_Batch_D_v1.md` and `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md`:

```
old_string:
- D-12 — Add `sport_name_aliases` schema to v4 §4

new_string:
- ~~D-12~~ — ✅ Resolved 2026-05-11 (FC-1a). Schema block drafted in `Layer0_ETL_Spec_v3_Patch_Batch_D_v1.md` §4.x. UNIQUE constraint assumption flagged for verification before v4 lock.
```

```
old_string:
- D-13 — correct Batch B patch (`source_exercise_ids[]`, add `audit_log`)

new_string:
- ~~D-13~~ — ✅ Resolved 2026-05-11 (FC-1a). Correction drafted in `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md` — `source_exercise_ids TEXT[]` (was singular) + `audit_log TEXT` (was missing). Documentation patch only; deployed shape already matches corrected spec.
```

```
old_string:
- D-16 — add `primary_muscles` / `secondary_muscles` to v4 §4.12 schema block

new_string:
- ~~D-16~~ — ✅ Resolved 2026-05-11 (FC-1a). Type confirmed as `TEXT[]` per Drift Report §1; ETL transform documented (`string_to_array(value, ', ')`). Folds into Batch B patch §4.12 "Columns added" table — replacement rows in `FC1a_Pass1_Bundle_v1.md` §4.
```

### Edit 7 — `Project_Backlog.md` D-05 resolution (apply AFTER both halves deploy)

```
old_string:
- D-05 — add aggregator filter to phase_load_allocation ETL (33 rows to filter; affects all sports including AR)

new_string:
- ~~D-05~~ — ✅ Resolved 2026-05-11 (FC-1a). Cleanup SQL `cleanup_phase_load_allocation_aggregators_v1.sql` soft-superseded 33 misrouted aggregator rows. ETL extractor patch applied (see CC commit). Control_Spec §8.2 standing rule retired.
```

---

## §14. End-of-session checklist (rule #10)

Before composing the FC-1a closing handoff, verify on disk:

- [ ] `Control_Spec.md` (or `Control_Spec_v<N>.md` per chosen versioning option) reflects §10 file-versioning bullet, §9 D-26 status flip, §8.2 D-05 retirement (if/when applied).
- [ ] `Project_Backlog.md` (or versioned) reflects D-04, D-06, D-12, D-13, D-16 ✅, and D-05 ✅ (if/when both halves landed).
- [ ] `Layer0_ETL_Spec_v3_Patch_Batch_D_v1.md` uploaded (contains §2 + §4 content from this bundle).
- [ ] `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md` uploaded (contains §3 content from this bundle).
- [ ] Three SQL migration files committed to `etl/sources/` and run results confirmed in Neon.
- [ ] Memory rule #12 added via `memory_user_edits` tool.

Do not write the closing handoff until each item above is verified. The pattern of "claim landed in handoff before disk reflects it" is the original drift mode.

---

## Gut check

**What this pass got right:**
- All 6 deliverable items (D-04, D-06, D-12, D-13, D-16, D-05 cleanup half) produced with verify-block patterns matching house style.
- All 4 investigation items (D-07, D-08, D-14, D-15) have queries ready to run; no guesswork about what's needed.
- Versioning rule explicitly surfaces interpretation options rather than picking silently.
- Decisions block scoped tightly — 4 questions, recommendations on each, no decision-paralysis fan-out.

**Risks:**
- The "Option B" recommendation for versioning collides with Andy's literal request ("new version with version tag"). I think Option B is the practical choice but Andy may have a reason he wants Option A.
- The §2 D-12 schema block assumes the UNIQUE constraint structure based on the drift report's verbal description. If deployed UNIQUE differs (e.g., includes etl_version in a different position), the spec block needs a fix. The verification query in §2 flags this.
- D-07 investigation depends on Andy running D-05 cleanup first, then re-running the diff query. If queries get run out of order, the result will be misleading (the 33 aggregator rows would inflate the "expected sports" set).
- D-05 has three components (cleanup SQL, ETL code patch, standing rule retirement). The order matters: cleanup first → code patch second → standing rule retirement only after the next clean ETL run. If any one of them is skipped, the next ETL run will regress the cleanup.

**What might be missing:**
- D-12's deployed UNIQUE constraint isn't verified yet. Should run the verification query and patch the spec block if needed before treating D-12 as fully closed.
- D-08's "compare to source xlsx" step requires reading Sheet 3 of `Sports_Framework_v10.xlsx` — that's an additional follow-on action that needs scheduling.
- No coverage of `terrain_types` provenance (Drift Report §2.10, 7 enrichment columns) or `terrain_gap_rules` (§2.12, undocumented 12-column table). Both are FC-2 work per the original handoff scope; flagging here to confirm they stayed out of FC-1a.

**Best argument against the pass:**
The versioning rule is being designed under pressure right after an event it would have prevented. Decisions made in that state tend to over-fit to the most recent failure. The rule as written is reasonable, but if Andy's actual lived problem isn't filename collisions but is rather "I lose track of which version is canonical," then a different mechanism (e.g., a `VERSION.md` file in the project listing current authoritative filenames) might serve better than ubiquitous version-suffixing. Worth a 30-second sanity check before locking the rule in.

---

*End of FC-1a Pass 1 bundle.*
