# `etl/migrations/layer0/` — DB-native Layer 0 edits

Reviewed SQL migrations are the authoring source of truth for Layer 0 reference
data, replacing the xlsx → `etl.layer0.run` re-import loop. See
`aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` (epic
[#488](https://github.com/ahorn885/exercise/issues/488)) for the why; this README
is the how.

The genesis snapshot (`etl/output/layer0_etl_v1.6.7.sql`) is the frozen baseline.
Migrations stack on top of it in order. **Do not emit new full snapshots while
migrations are in flight** — the snapshot stays the genesis baseline and the
`*.sql` files here are the forward history.

## Edit flow (§5.1 of the design spec)

```
1. write etl/migrations/layer0/NNNN_<slug>.sql
2. CI "Layer 0 integrity gate" loads schema + genesis snapshot, applies every
   migration in order, then runs validate_layer0 — a bad migration fails here
   BEFORE it ever reaches the database
3. review the .sql diff in the PR
4. on merge, Andy applies the migration in the Neon SQL editor
   (the container has no Neon egress, so the apply stays a hands-on step)
5. the app picks up the change automatically (every serving query filters
   `WHERE superseded_at IS NULL`) — no restart, no redeploy
```

## Naming

`NNNN_<slug>.sql` — zero-padded 4-digit sequence + a short snake_case slug, e.g.
`0001_remove_triathlon_d007_noop_rows.sql`. The gate applies them in `sort -V`
order, so the number is the apply order. Each file wraps its statements in a
single `BEGIN; … COMMIT;` and should be safe to re-run (idempotent).

## Versioning model (read before writing a migration)

Layer 0 rows are versioned by **invalidation, not overwrite**: a row is retired
by setting `superseded_at` (it stays as history; it leaves the active set), and a
new value arrives as a fresh `INSERT … superseded_at = NULL`. The
`etl_version` column is family-prefixed — `0A-v…` (sports + disciplines + bridge
+ maps + phase-load + modality + aliases), `0B-v…` (exercises + sport_exercise_map),
`0C-v…` (vocabulary / terrain / body-parts / equipment / conditions / toggles).

**Serving reads the active set directly** (`WHERE superseded_at IS NULL`) — it does
*not* match on `etl_version` (slice 3b). A migration is therefore picked up the
moment it commits, with no version coordination. The `etl_version` string survives
only as the **cache-invalidation signal**: `_q_current_etl_version_set`
(`layer4/orchestrator.py`) digests each family's active version **per table**, and
that digest is part of every plan-gen cache key. Because it is per-table, bumping
one table's version perturbs the digest — and invalidates the caches — without
touching any other table. Two shapes follow:

### Two edit shapes

**1. Cache-neutral structural edit** — when the change does not alter any served
output (e.g. removing zero-weight rows, fixing a field no serving path reads).
Just supersede / insert the affected rows; **no version bump**. Serving picks up
the new active set immediately, but the version digest is unchanged so caches stay
warm (stale = correct, because the output is unchanged). `0001` is this shape.

```sql
-- remove a row from the active set (history preserved)
UPDATE layer0.<table> SET superseded_at = now()
 WHERE superseded_at IS NULL AND <key predicate>;
```

**2. Serving-relevant edit** — when the change *does* alter served output and the
plan-gen caches must invalidate. Supersede the affected rows and re-insert them
with the edit applied at a **bumped version on that table only**. The table's
entry in the family digest advances, so the caches invalidate; every other table
(and every unchanged row) stays put. No whole-family re-stamp:

```sql
-- serving-relevant edit to one table (e.g. terrain_types). Only the changed
-- rows move to the new version; unchanged rows stay active at the old one.
INSERT INTO layer0.terrain_types (<cols>, etl_version, etl_run_at)
SELECT <cols, with the edit applied>, '0C-v<new>', now()
  FROM layer0.terrain_types
 WHERE superseded_at IS NULL AND <rows to change>;
UPDATE layer0.terrain_types SET superseded_at = now()
 WHERE superseded_at IS NULL AND etl_version = '0C-v<old>' AND <rows to change>;
```

> The new version need only **differ** from the table's current active version
> (convention: bump up) — it need not advance a family-wide max, because the
> digest is per-table. Serving reads `superseded_at IS NULL`, so the mixed
> active-version state (changed rows new, unchanged rows old) serves correctly;
> the digest takes the per-table max. The per-table model landed in slice 3b
> (`_q_current_etl_version_set` + the Layer 2 builders reading the active set);
> it replaced the earlier per-family re-stamp.

## Tables that are not in the genesis snapshot (spec-sourced, not ETL-emitted)

Most `layer0.*` tables are emitted by the ETL into the genesis snapshot
(`etl/output/layer0_etl_v1.6.x.sql`). A few are **spec-sourced** — hand-authored
from a spec rather than parsed from a workbook — so they never appeared in the
snapshot and historically lived as one-shot `etl/sources/migrate_*.sql` files the
gate never saw. Folding them into this loop has two halves:

1. **DDL → `etl/layer0/schema.sql`** so the gate (and any `apply_schema` setup)
   creates the table. Mirror the table's *existing* live shape exactly — do not
   "normalize" column types/columns in the same step, or you risk drift with a
   copy already on Neon.
2. **Seed → a migration here**, self-contained (`CREATE TABLE IF NOT EXISTS` +
   `INSERT … ON CONFLICT DO NOTHING`) so a standalone Neon SQL-editor apply
   provisions the table without a separate schema step.

`0002_seed_supplement_vocabulary.sql` is the worked example (epic #488): it
de-orphans `layer0.supplement_vocabulary`, subsuming the legacy
`migrate_supplement_vocabulary.sql` (base seed) + the D-21
`migrate_supplement_vocab_contraindication_retag_v1.sql` (the seed already
carries the canonical §B tokens the retag produced). `layer0.terrain_gap_rules`
is the remaining orphan and the natural next migration in this shape.

## The gate

The `layer0-gate` job in `.github/workflows/ci.yml` is the integrity backstop:
it stands up a throwaway Postgres, loads `etl/layer0/schema.sql` + the genesis
snapshot, applies every migration here in order, and runs
`python -m etl.layer0.validate_layer0`. A migration that introduces a dangling
FK, a canon violation, a sub-100 phase load, etc. fails CI before it can be
applied to Neon. Run order and disposition are owned by
`etl/layer0/validate_layer0.py` (decision C: every check FAIL, `sum_to_100` the
only waiver bucket).
