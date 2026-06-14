# Pre-v1.7.0 Layer 0 artifacts (folded into the baseline)

As of the **v1.7.0 genesis baseline** (`etl/output/layer0_etl_v1.7.0.sql`, issue
#604), the Layer 0 gate loads a single self-contained snapshot — a full
`pg_dump` of live `layer0` (schema + data). The artifacts below are the
**pre-collapse** authoring layers; their effects are already reflected in live
Neon and therefore in the v1.7.0 baseline, so they are no longer loaded by CI or
applied to a fresh DB. They are kept here for history (git also retains them).

**Do not re-apply these to a DB seeded from the v1.7.0 baseline** — they would
double-create / double-seed. New Layer 0 DDL starts at migration `0006` in
`etl/migrations/layer0/`.

| File | What it was |
| --- | --- |
| `schema.sql` | The base Layer 0 schema (CREATE TABLEs) the gate loaded before the snapshot. Now superseded by the DDL embedded in the v1.7.0 baseline dump. |
| `0001_remove_triathlon_d007_noop_rows.sql` | Migration — removed D-007 no-op rows. Effect baked into the baseline. |
| `0002_seed_supplement_vocabulary.sql` | Migration — created + seeded `supplement_vocabulary`. |
| `0003_seed_terrain_gap_rules.sql` | Migration — created + seeded `terrain_gap_rules`. |
| `0004_craft_terrain_compat_and_drop_cycling_trainer.sql` | Migration — created `craft_terrain_compatibility`, dropped the cycling-trainer row. |
| `0005_seed_location_category_baseline.sql` | Migration — created + seeded `location_category_equipment_baseline` (WS-H Slice 3 / F8). |
| `populate_equipment_items_batch_a.sql`, `…_K_additions.sql`, `…_K2_additions.sql`, `…_K3_additions.sql` | Retired xlsx-era equipment-vocabulary scaffolding (pre-reconciliation tokens such as `Bench press rack` / `Climbing Wall` / `Crash pad`). Sourcing from these caused the Slice-3 token mix-up (#603); the live vocabulary is unified and captured in the baseline. |
| `Equipment_Column_Canonical_Addendum.md` | Stale v19 equipment-column addendum (caps-cased tokens that don't match live). |
