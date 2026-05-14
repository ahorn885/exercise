# Layer0 ETL Spec — Batch B Correction Patch

**Date:** 2026-05-11
**Predecessor patch:** `Layer0_ETL_Spec_v3_Patch_Batch_B.md`
**Status:** Correction — supplements the original Batch B patch with two errata. Apply alongside Batch B when FC-2 folds both into `Layer0_ETL_Spec_v4.md`.

This patch corrects two documentation gaps in the original Batch B patch. Both are documentation-only — the deployed shape already matches what's documented here; the original Batch B patch described it incorrectly.

Tracked as **D-13** (`discipline_technique_foci` patch correction) and **D-16** (`exercises` primary/secondary muscles type confirmation) in `Project_Backlog.md`.

---

## Correction 1 — `discipline_technique_foci` schema (D-13)

**Patch target in Batch B:** §4.15 (the `discipline_technique_foci` schema block).

Two errors in the original Batch B schema block:

1. `source_exercise_id TEXT` declared as **singular scalar**. Deployed is **plural array** `source_exercise_ids TEXT[]`.
2. `audit_log TEXT` column is **missing from Batch B**. Deployed table has it.

### Replacement schema block (use this for v4 §4.15)

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
  source_exercise_ids         TEXT[],                  -- ★ ARRAY (was singular `source_exercise_id TEXT` in Batch B patch)
  audit_log                   TEXT,                    -- ★ ADDED (omitted in Batch B patch)

  etl_version                 TEXT        NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (focus_id, etl_version)
);

CREATE INDEX idx_dtf_disciplines ON layer0.discipline_technique_foci USING GIN (discipline_ids);
CREATE INDEX idx_dtf_active      ON layer0.discipline_technique_foci (etl_version) WHERE superseded_at IS NULL;
```

### Why this is documentation-only

The 35 rows currently in the table at `etl_version = '0B-v19.B'` already conform to the corrected shape. The Batch B *populate* script (`populate_discipline_technique_foci.sql`) is what actually deployed the table — and it used the correct types. The error is purely in the spec patch describing what got deployed. No DB migration needed.

---

## Correction 2 — `exercises` primary/secondary muscles types (D-16)

**Patch target in Batch B:** §4.12 "Columns added" table.

The original Batch B patch lists:

| Deployed | Type | Notes |
|---|---|---|
| `primary_muscles` | TEXT (or TEXT[]) | source col 5 |
| `secondary_muscles` | TEXT (or TEXT[]) | source col 6 |

The "or TEXT[]" hedge is resolved by `Layer0_Deployed_Schema_and_Drift_Report.md` §1 (Open Item R resolved): **both columns are `TEXT[]`**.

### Replacement rows for the §4.12 "Columns added" table

| Deployed | Type | Notes |
|---|---|---|
| `primary_muscles` | `TEXT[]` | Source col 5. ETL transform: `string_to_array(value, ', ')`. xlsx stores comma-separated string per cell (e.g., `"Quadriceps, Glutes, Adductors"`). Empty cells produce empty arrays (`'{}'`), not NULL. |
| `secondary_muscles` | `TEXT[]` | Source col 6. ETL transform: `string_to_array(value, ', ')`. Same shape and rules as `primary_muscles`. |

### Canonical column set — no change

The "Canonical column set (deployed)" listing in Batch B already names `primary_muscles, secondary_muscles` in correct position. The 24-column total is correct.

### ETL field transforms — new note for v4 §4.12

When the v4 §4.12 schema block is rewritten, add this transform note alongside the schema:

> **ETL field transforms (cols 5, 6):** the source xlsx cells for `Primary Muscles` and `Secondary Muscles` are comma-separated strings. ETL applies `string_to_array(value, ', ')` to produce the deployed `TEXT[]` column shape. Empty cells produce empty arrays (`'{}'`), not NULL.

---

## §8 update — consumer reference table

No change. Both corrections are local to §4.12 and §4.15.

---

## §7 — open items (no addition)

No new open items. Both corrections close their respective backlog rows (D-13, D-16).

---

## Files shipped for Batch B Correction

| File | Purpose |
|---|---|
| `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction.md` | This patch document |

No SQL files — both corrections are documentation-only. Deployed shape already matches.

---

*End of Batch B Correction patch.*
