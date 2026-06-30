-- 0034 — retire the "WEEKLY TOTAL TARGET" aggregator rows from the active
-- phase_load_allocation set (#269).
--
-- These are zero-weight per-sport summary rows, not real disciplines: the
-- per-sport weekly total was extracted long ago into
-- layer0.phase_load_weekly_totals, and the Layer 2A discipline loader has
-- carried a defensive "discipline_name NOT LIKE '%WEEKLY TOTAL%'" filter (the
-- D-05 standing filter, layer2a/builder.py) to keep them out of plan-gen.
-- Superseding them at the source removes them from the active set so that
-- filter (and the matching default_inclusion exemption) can finally retire,
-- and the new validate_layer0 check `phase_load_allocation_aggregators` keeps
-- them from ever coming back.
--
-- Cache-neutral structural edit (README §"Two edit shapes", shape 1): the rows
-- are never served — the loader filters them out — so removing them alters no
-- plan-gen output. No etl_version bump; the cache digest is unchanged and
-- caches stay warm.
--
-- As of the v1.10.1 genesis baseline this supersedes 31 rows (one per
-- sub-format sport). Idempotent: re-running matches nothing once applied
-- (every WEEKLY TOTAL row already has superseded_at set).
BEGIN;

UPDATE layer0.phase_load_allocation
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND discipline_name LIKE '%WEEKLY TOTAL%';

COMMIT;
