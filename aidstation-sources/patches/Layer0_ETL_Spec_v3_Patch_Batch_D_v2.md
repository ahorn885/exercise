# Layer0 ETL Spec — Batch D Patch

**Date:** 2026-05-11
**File revision:** v2 — adds D-14 + D-15 corrections alongside D-12.
**Predecessor spec:** `Layer0_ETL_Spec_v3.md`
**Companion docs:** `Layer0_ETL_Spec_v3_Patch_Batch_A.md`, `_Batch_B.md`, `_Batch_C.md`, `_Batch_B_Correction.md`
**Status:** Patch — apply alongside other pending §8 corrections at the next consolidated spec revision (FC-2 — `Layer0_ETL_Spec_v4.md`).

This patch covers three drift items closed in FC-1a (2026-05-11):

| Section | Drift ID | Type |
|---|---|---|
| §2 | D-12 | New schema block for `sport_name_aliases` (was undocumented) |
| §3 | D-14 | Column drop — `cross_sport_properties.source_text` removed (post-migration) |
| §4 | D-15 | UNIQUE clarification — `discipline_substitutes` deployed UNIQUE is correct; spec catches up |

---

## §2 — `sport_name_aliases` schema block (D-12)

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

## §3 — `cross_sport_properties.source_text` removed (D-14)

**Patch target in v4:** §4.8 schema block for `cross_sport_properties`.

**Background:** Spec v3 §4.8 lists 4 extra deployed columns vs spec: `source_evidence`, `notes`, `source_text`, `confidence`. Drift Report §2.7 flagged `source_text` as suspicious — "duplicates `source_evidence` semantically; likely leftover from earlier ETL run." Investigation 2026-05-11 confirmed: on the single deployed row, `source_text` content was byte-identical to `source_evidence`. Column dropped via `migrate_cross_sport_properties_drop_source_text_v1.sql`.

### Replacement column list for v4 §4.8 (deployed shape, post-FC-1a)

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | — |
| `property_id` | TEXT NOT NULL | e.g. `LIT_RATIO_001` |
| `property_name` | TEXT NOT NULL | e.g. "LIT (Low-Intensity Training) Ratio — mid-prep" |
| `property_type` | TEXT NOT NULL | (per spec v3) |
| `value` | TEXT NOT NULL | (per spec v3) |
| `unit` | TEXT | (per spec v3) |
| `applies_to_sports` | TEXT[] | (per spec v3) |
| `applies_to_disciplines` | TEXT[] | (per spec v3) |
| **`source_evidence`** | TEXT | Free-text citation list (semicolon-separated). The authoritative source field. |
| **`notes`** | TEXT | Additional context beyond source_evidence. |
| **`confidence`** | TEXT | Confidence rating (HIGH / MEDIUM / LOW or similar). |
| `etl_version`, `etl_run_at`, `superseded_at` | versioning | — |

UNIQUE `(property_id, etl_version)` per spec v3 (no change).

**v3 → v4 delta:** drop `source_text TEXT` from the post-FC-1a deployed shape comparison; spec v3 had not yet documented it.

---

## §4 — `discipline_substitutes` UNIQUE clarification (D-15)

**Patch target in v4:** §4.9 schema block for `discipline_substitutes`.

**Background:** Spec v3 §4.9 declared UNIQUE as `(target_id, substitute_id, etl_version)`. Deployed has the looser `(target_id, substitute_id, substitute_name, etl_version)`. Drift Report §2.8 originally proposed tightening deployed to match spec.

Investigation 2026-05-11 surfaced 2 conflict rows under the tighter constraint:

| target_id | target_name | substitute_id | substitute_name | fidelity | constraint |
|---|---|---|---|---|---|
| D-008b | Whitewater Kayaking | D-007 | Packrafting (whitewater) | 0.6 | "similar bracing and decision-making demands..." |
| D-008b | Whitewater Kayaking | D-007 | Packrafting (flat-water) | 0.4 | "paddle aerobic base only; loses whitewater skills entirely" |
| D-023 | Downhill Mountain Running | D-001 | Trail Running (sustained downhill) | 0.85 | "eccentric loading transfers fully" |
| D-023 | Downhill Mountain Running | D-001 | Trail Running (rolling) | 0.3 | "rolling terrain doesn't capture sustained eccentric load..." |

These are **deliberately-authored sub-format variants** with distinct Fidelity ratings carrying real coaching signal. Tightening the constraint would destroy this information. The deployed loose UNIQUE is correct.

### Resolution: spec catches up to code

**v4 §4.9 UNIQUE clause:**

```sql
UNIQUE (target_id, substitute_id, substitute_name, etl_version)
```

`substitute_name` acts as a **variant key** when multiple rows exist for the same `(target_id, substitute_id)` pair. The variant captures sub-format context (e.g., whitewater vs flat-water Packrafting) and is paired with a distinct `fidelity` rating per variant.

### Consumer guidance for Layer 2D / Layer 4

Substitution queries should NOT assume one row per `(target_id, substitute_id)`. The correct pattern:

```sql
-- Get all variants for a target+substitute pair, sorted by fidelity
SELECT substitute_name, fidelity, constraints
FROM layer0.discipline_substitutes
WHERE target_id = $1
  AND substitute_id = $2
  AND superseded_at IS NULL
ORDER BY fidelity DESC;
```

Consumer (2D substitution logic or Layer 4 plan-gen) picks the variant by fidelity given athlete context — typically locale terrain availability, equipment, sub-format preferences. A low-fidelity variant (e.g., 0.3) surfaces as a coaching flag rather than an active substitution.

---

## §5 — §6 (ETL run order) — no change

The new table (`sport_name_aliases`, D-12) is already in §6.2 phase 1, position 6. The two existing tables (`cross_sport_properties` D-14, `discipline_substitutes` D-15) keep their existing run order positions.

---

## §6 — §8 (consumer reference table) — no change

No new consumer rows from this patch. Existing consumer references stand. The §8 row for `sport_discipline_bridge` may want a clarifying parenthetical adding `sport_name_aliases` to its "Tables queried" cell — confirm against current §8 before patching.

---

## §7 — open items

| Item | Notes |
|---|---|
| D-12 deployed UNIQUE verification | Run the query in §2 "Open assumption flagged" before v4 lock. |
| D-14 spec fold-in | v4 §4.8 column list reflects post-FC-1a shape (3 extras, not 4). |
| D-15 spec fold-in | v4 §4.9 UNIQUE clause matches deployed (includes `substitute_name`). |

---

## §8 — Files shipped for Batch D

| File | Purpose |
|---|---|
| `Layer0_ETL_Spec_v3_Patch_Batch_D_v2.md` | This patch document (supersedes _v1 which only covered D-12) |
| `migrate_cross_sport_properties_drop_source_text_v1.sql` | D-14 deploy (already run 2026-05-11) |

No new SQL for D-12 (table was already deployed) or D-15 (no migration; spec patch only).

---

*End of Batch D patch v2.*
