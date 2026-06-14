-- 0001_remove_triathlon_d007_noop_rows.sql
--
-- Issue #476 — retire the zero-weight Triathlon × D-007 (Time-Trial Cycling)
-- placeholder rows. These are documentation-only pointers: D-007 in a Triathlon
-- context carries a 0.0/0.0 race-time band ("included in D-006 road-cycling %,
-- not additional time"), so it contributes nothing to Layer 2A allocation.
--
-- D-007 itself is a REAL discipline and is left fully intact — it keeps its
-- `disciplines` definition, its real 95-100% band under "Long Distance /
-- Endurance Cycling", both `discipline_substitutes` (D-006<->D-007), the
-- D-007->D-002 pairing, its `discipline_modality_membership`, and the
-- `cycling_trainer` craft alias. Only the Triathlon-context rows go.
--
-- Edit shape: CACHE-NEUTRAL structural removal (see README §"Two edit shapes").
-- The rows are zero-weight, so dropping them from the active set does not change
-- any served allocation, and no etl_version bump / cache invalidation is needed.
-- Removal = supersede (soft), per the row-invalidation model: the rows stay in
-- the table as history and drop out of the active set (`superseded_at IS NULL`).
-- Idempotent: re-running matches no active rows on the second pass.

BEGIN;

-- sport_discipline_bridge: Triathlon × D-007 (1 row, 0.0/0.0).
UPDATE layer0.sport_discipline_bridge
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND framework_sport = 'Triathlon'
   AND discipline_id = 'D-007';

-- sport_discipline_map: Triathlon × D-007 (1 row, 0.0/0.0). The
-- "Long Distance / Endurance Cycling" map row is a different sport_name and is
-- left untouched.
UPDATE layer0.sport_discipline_map
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND sport_name = 'Triathlon'
   AND discipline_id = 'D-007';

-- phase_load_allocation: the 4 Triathlon-format × D-007 rows (Sprint / Standard
-- / Half / Full), all zero across every phase. `LIKE 'Triathlon%'` excludes
-- the "Long Distance / Endurance Cycling (Time Trial)" row.
UPDATE layer0.phase_load_allocation
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND sport_name LIKE 'Triathlon%'
   AND discipline_id = 'D-007';

COMMIT;
