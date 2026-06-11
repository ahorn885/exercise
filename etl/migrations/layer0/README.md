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

Serving resolves **one active version per family** and exact-matches it
(`layer4/orchestrator.py:_q_current_etl_version_set` → the Layer 2 builders), and
that version string is part of every plan-gen cache key. Two consequences shape
how you write a migration:

### Two edit shapes

**1. Cache-neutral structural edit** — when the change does not alter any served
output (e.g. removing zero-weight rows, fixing a field no serving path reads).
Just supersede / insert the affected rows; **no version bump**. The active set
stays uniform at the current family version, and caches need not invalidate
(stale = correct, because the output is unchanged). `0001` is this shape.

```sql
-- remove a row from the active set (history preserved)
UPDATE layer0.<table> SET superseded_at = now()
 WHERE superseded_at IS NULL AND <key predicate>;
```

**2. Serving-relevant edit** — when the change *does* alter served output and the
plan-gen caches must invalidate. Today this requires **bumping the family
version**, which (because serving exact-matches one version per family) means
re-stamping every table in that family to the new version via copy-forward +
supersede:

```sql
-- bump family 0A: copy every active row forward to the new version, applying
-- the surgical change inline, then supersede the old version.
INSERT INTO layer0.<each 0A table> (<cols>, etl_version, etl_run_at)
SELECT <cols, with the edit applied via CASE/WHERE>, '0A-v<new>', now()
  FROM layer0.<each 0A table>
 WHERE superseded_at IS NULL AND etl_version = '0A-v<old>';
UPDATE layer0.<each 0A table> SET superseded_at = now()
 WHERE superseded_at IS NULL AND etl_version = '0A-v<old>';
-- ...repeat for all ~14 0A tables...
```

> The ~14-table re-stamp for a single-row 0A edit is the cost of the
> per-family version model. A follow-up slice (per-table version resolution)
> will shrink a serving-relevant edit to just the changed table — until that
> lands, a serving-relevant edit re-stamps the whole family. No migration of
> this shape has shipped yet; `0001` is deliberately the cache-neutral kind.

## The gate

The `layer0-gate` job in `.github/workflows/ci.yml` is the integrity backstop:
it stands up a throwaway Postgres, loads `etl/layer0/schema.sql` + the genesis
snapshot, applies every migration here in order, and runs
`python -m etl.layer0.validate_layer0`. A migration that introduces a dangling
FK, a canon violation, a sub-100 phase load, etc. fails CI before it can be
applied to Neon. Run order and disposition are owned by
`etl/layer0/validate_layer0.py` (decision C: every check FAIL, `sum_to_100` the
only waiver bucket).
