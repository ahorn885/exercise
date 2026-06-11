# Layer0 ETL Spec — Batch D Patch

**Date:** 2026-05-11
**Predecessor spec:** `Layer0_ETL_Spec_v3.md`
**Companion docs:** `Layer0_ETL_Spec_v3_Patch_Batch_A.md`, `_Batch_B.md`, `_Batch_C.md`, `_Batch_B_Correction.md`
**Status:** Patch — apply alongside other pending §8 corrections at the next consolidated spec revision (FC-2 — `Layer0_ETL_Spec_v4.md`).

This patch documents the `layer0.sport_name_aliases` schema. The table is referenced by spec v3 §6.2 run order and by §4.11 `sport_discipline_bridge` derivation but has no §4 schema block. This patch fills the gap. It is a documentation-only patch — the table is already deployed and populated.

Tracked as **D-12** in `Project_Backlog.md`.

---

## §4 addition — new table

Insert as **§4.x** at the appropriate point in v4 (after `4.10 discipline_training_gaps`, before the bridge sections, to match phase 1 run order where vocabularies load before 0A core).

### 4.x `layer0.sport_name_aliases` (NEW in v4 — undocumented in v3)

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
- Source: `etl/layer0/sport_name_aliases.py` (Python dict literal, not xlsx).
- One row per (exercise_db_sport, framework_sport) pair.
- Many-to-one allowed: one `framework_sport` may receive multiple `exercise_db_sport` aliases. (e.g., multiple exercise-DB phrasings for adventure racing all collapse to the canonical "Off-Road / Adventure Multisport (Nav)".)
- One-to-one enforced in the inverse direction by the UNIQUE constraint — an `exercise_db_sport` at a given `etl_version` maps to exactly one `framework_sport` (no ambiguity at lookup time).
- Validate `framework_sport` exists in `layer0.sports.sport_name`. Fail row + warn on broken FK.

**Consumers:**
- §4.11 `sport_discipline_bridge` ETL — joins exercise-DB sport rows to framework sport rows via this table.
- Query layer — occasional alias resolution when an athlete's onboarding answer uses an exercise-DB phrasing rather than a Sports Framework canonical name.

**Open assumption — pre-v4 verification required:**

The UNIQUE constraint shape above is inferred from the Drift Report v2 §2.13 description ("2 functional columns + versioning"). Before v4 lock, run this query in Neon to confirm:

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'layer0.sport_name_aliases'::regclass
  AND contype IN ('u','p');
```

Expected output: one PK constraint on `id`, one UNIQUE constraint on `(exercise_db_sport, etl_version)`.

If the deployed UNIQUE differs (e.g., includes `framework_sport` in the column set, or uses a different ordering), update the schema block in this patch to match deployed. Per the "spec catches up to code" pattern in `Layer0_ETL_Spec_v3_Patch_Batch_B.md`, deployed wins when spec and code disagree on a live table.

---

## §6 (ETL run order) — no change

The table is already in §6.2 phase 1, position 6. No re-ordering required.

---

## §8 update — consumer reference table

No new consumer rows. Existing `sport_discipline_bridge` derivation already implicitly consumes this table; no consumer-table change needed. The §8 row for `sport_discipline_bridge` may want a clarifying parenthetical:

| Layer | Receives from Layer 0 | Tables queried |
|-------|----------------------|----------------|
| 2A (Race Discipline Mix) | sport-discipline mapping (canonical names resolved via `sport_name_aliases` when athlete inputs use exercise-DB phrasing) | `sport_discipline_map`, `sport_discipline_bridge`, `sport_name_aliases` |

Only add if §8 currently fails to list `sport_name_aliases` for 2A. Confirm against current §8 before patching.

---

## §7 — open items (no addition)

No open items. The verification query under "Open assumption flagged" above is a one-shot check, not a tracked open item.

---

## Files shipped for Batch D

| File | Purpose |
|---|---|
| `Layer0_ETL_Spec_v3_Patch_Batch_D.md` | This patch document |

No SQL files — schema is already deployed. Patch is documentation-only.

---

*End of Batch D patch.*
