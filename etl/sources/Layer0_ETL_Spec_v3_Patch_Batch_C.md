# Layer 0 ETL Spec v3 Patch — Batch C

**Date:** 2026-05-10
**Predecessor patch:** `Layer0_ETL_Spec_v3_Patch_Batch_B.md`
**Successor:** v4 consolidated rewrite (post-2C/2D/2E lock)
**Scope:** Equipment curation on 10 exercises; resolution of Open Item R; downstream notes for v20 ETL re-run.

---

## What this patch records

### 1. Batch C exercise-data curation

10 exercises whose `equipment_required[]` carried implicit-OR alternatives were curated into primary + structured-substitute form. Migrated to `etl_version = '0B-v19.C'` via supersede + reinsert in `migrate_batch_c_bike_load_curation.sql`.

| Exercise | Old `equipment_required[]` | New primary | New substitutes added (prepended) |
|---|---|---|---|
| EX073 Threshold Intervals (Bike) | Road bike, Mountain bike, Bike trainer, TT Bike, Gravel bike | `[Road bike]` | Mountain bike; Gravel bike; TT Bike; Bike trainer |
| EX074 VO2 Max Intervals (Bike) | same | `[Road bike]` | same 4 |
| EX075 Sweet Spot Training (Bike) | same | `[Road bike]` | same 4 |
| EX117 Loaded Step-Down (Eccentric Box) | Plyo box, Dumbbell, Kettlebell, Weighted vest | `[Plyo box, Dumbbell]` | KB Loaded Step-Down `[[Plyo box, Kettlebell]]`; Vested Loaded Step-Down `[[Plyo box, Weighted vest]]` |
| EX119 Weighted Step-Up (High Box, Heavy Load) | Dumbbell, Barbell, Kettlebell, Weighted vest | `[Plyo box, Dumbbell]` | KB Weighted Step-Up; Vested Weighted Step-Up. **Plyo box added as primary (authoring fix); Barbell dropped (separate exercise).** |
| EX174 Aero / TT Position Hold | TT Bike, Road bike, Bike trainer | `[TT Bike]` | On bike trainer in aero `[[TT Bike, Bike trainer]]`. Existing "Road bike with clip-on aero bars" entry preserved as-is. |
| EX185 Climb Pacing & Cadence Management | Road bike, Mountain bike, Bike trainer, Treadmill | `[Road bike]` | 4 bike variants. **Treadmill dropped entirely.** |
| EX186 High Cadence Spin Drill | Road bike, Mountain bike, Bike trainer | `[Road bike]` | 4 bike variants |
| EX197 Double Brick / Run-Bike-Run Pacing Drill | Road or Trail (→ terrain), Road bike, Mountain bike | `[Road bike]` | 4 bike variants. `terrain_required` already populated by ETL split; not touched. |
| EX229 Bench Press (Barbell / DB) | Barbell, Dumbbell, Bench, Squat rack | `[Barbell, Bench, Squat rack]` | On bench press station `[[Barbell, Bench press rack]]`; DB Bench Press `[[Dumbbell, Bench]]` |

**Substitute merge order (locked design — Andy's choice (b) this session):**

1. New Batch C entries (equipment variants of same exercise)
2. Existing entries where `is_improvised = false` (cross-modal subs from K-parser)
3. Existing entries where `is_improvised = true` (improvised / 🏠)

Within each bucket, original ordinality is preserved. This gives Layer 2C Tier 2 a coherent priority gradient.

### 2. Open Item R — RESOLVED

`primary_muscles` and `secondary_muscles` deployed as `TEXT[]` (`_text`). ETL transform: `string_to_array(value, ', ')` on the comma-separated source cells.

**v4 §4.12 schema block must add:**
```sql
primary_muscles    TEXT[],    -- ETL: string_to_array(col 5, ', ')
secondary_muscles  TEXT[],    -- ETL: string_to_array(col 6, ', ')
```

### 3. CNF semantics for substitute equipment_required confirmed in production

`equipment_substitutes_structured` JSONB entries use `equipment_required: list[list[str]]` where the outer list is OR (any group satisfies) and the inner list is AND (all items in group required). Batch C entries follow this:

- `[["Mountain bike"]]` — needs just Mountain bike (single OR group, single AND member)
- `[["TT Bike", "Bench trainer"]]` — wait, "Bike trainer" — needs both TT Bike AND Bike trainer
- `[["Backpack"], ["Weighted vest"]]` (from K-parser data) — needs Backpack OR Weighted vest

No spec change needed — already documented in `ETL_Spec_v3_Corrections_2ABC_v2.md` §4.12.

---

## §4.12 update — Batch C state

After Batch C, `layer0.exercises` carries 159 active rows distributed across three etl_versions:

| etl_version | Active rows |
|---|---|
| `0B-v1.3.1` | 136 |
| `0B-v19.B`  | 13  (Batch B retypes) |
| `0B-v19.C`  | 10  (Batch C curation) |
| **Total**   | **159** |

Total table size after Batch C: 234 rows (224 pre-Batch-C + 10 reinserts).

---

## §8 consumer table — no change

Batch C doesn't change the consumer surface. The columns it writes to (`equipment_required`, `equipment_substitutes_structured`) are already consumed by 2C per `ETL_Spec_v3_Corrections_2ABC_v2.md`.

---

## §7 open items — status

| ID | Item | Status after Batch C |
|---|---|---|
| R | Confirm `primary_muscles` / `secondary_muscles` deployed types | ✅ RESOLVED — both `TEXT[]` |
| S | Sweep other Layer 0 tables for spec drift before further migrations | ✅ DONE — see `Layer0_Deployed_Schema_and_Drift_Report.md` |
| O | Rowing discipline missing from Sports Framework | Carried; v11 framework fix |
| P | Layer 4 selection logic for foci | Carried; plan-gen design |
| Q | Foci edit workflow | Deferred |
| T | Exercise-name refresh pass (13 retyped exercises with "Technique Drill" naming) | Carried; not blocking |
| — | v20 xlsx rebuild | New | Andy's choice: structured subs format; K-parser sanity check required |
| — | v4 ETL spec consolidation | New scope inflated by drift report; spec rewrite is its own multi-section batch |

---

## §6.x notes for v20 ETL re-run

The drift report (`Layer0_Deployed_Schema_and_Drift_Report.md` §4) flagged several pre-rerun verification items. The two most relevant to Batch C consequences:

1. **`exercises` table re-run must not overwrite Batch B/C work.** Batches B and C are not derived from xlsx — they're hand-curated SQL on top of `0B-v1.3.1` rows. If v20 ETL truncates and re-loads `layer0.exercises`, all Batch B/C state is lost. Options:
   - (a) v20 xlsx fully encodes Batch B drops + retypes + Batch C primary/substitute splits, so the new ETL run produces the same end state at `0B-v20`.
   - (b) v20 ETL preserves active rows whose `etl_version` is `0B-v19.B` or `0B-v19.C` and only re-runs against `0B-v1.3.1` predecessors.

   Recommendation: (a). It restores xlsx as source-of-truth and removes the drift surface.

2. **K-parser sanity check (Andy's decision this session).** v20 xlsx will store substitutes in structured form. Either:
   - The xlsx authors the structured JSONB directly per row (no parser dependency), or
   - The xlsx authors free-text and the K-parser runs at ETL time.

   Choice not yet made. Pre-decision check: enumerate every substitute_text format in current `equipment_substitutes_structured` rows and confirm the K-parser would reproduce them. If yes, free-text is safe. If no, structured authoring is required.

Both items belong in the v20 xlsx batch, not this patch.

---

## Run sequence

```bash
psql $DATABASE_URL -f migrate_batch_c_bike_load_curation.sql
```

Single script. All pre-flight checks abort the transaction on failure. Post-flight verification embedded. Safe to re-run (idempotent via etl_version check).

---

## Gut check

**What this patch gets right:** Equipment-variant substitutes now structured for Layer 2C Tier 2 — Layer 4 can prescribe named bike or load variants rather than generic "any bike works". The authoring fix on EX119 (missing Plyo box) is captured; the Treadmill purge on EX185 is captured.

**Risks / what we might be missing:**
- Substitute-text wording chosen "bare" per Andy's pick. Layer 4 has to render those in context ("Threshold Intervals on Mountain bike") — if the prompt assembler doesn't natively prefix the parent exercise name, the output will read awkwardly. Worth verifying when Layer 4 design lands.
- The 3-bucket merge order is locked, but for the 7 exercises with existing K-parser data, the resulting Tier 2 priority is "new bike variants → rowing erg / running cross-modal → improvised hotel stairs". That's the right order for bike-cardio exercises but may not generalize when this same pattern is applied to other exercise families later. Not a Batch C problem.
- **Best argument against this batch:** if v20 xlsx rebuild lands before plan-gen exists, Batch C's specific primary/substitute choices become reversible by xlsx authoring decisions. We're not protected against re-litigation. Mitigation: this patch and the v3 corrections doc both record the curation rules so v20 can encode them cleanly.
