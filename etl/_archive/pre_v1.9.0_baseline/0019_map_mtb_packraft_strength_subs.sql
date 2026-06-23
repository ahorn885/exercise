-- 0019_map_mtb_packraft_strength_subs.sql
--
-- Plan-75 finding: Mountain Biking (D-008) and Packrafting (D-009) resolved a
-- strength substitute pool of ZERO (feasibility log `strength_pool_n=0`), so when
-- the schedule forced two same-discipline cardio sessions onto one day there was
-- no strength option to break it up.
--
-- Root cause: the per-discipline exercise pool is a name-equality JOIN
-- `sport_discipline_bridge.exercise_db_sport = sport_exercise_map.sport_name`
-- (layer2c/builder.py), but these disciplines' `exercise_db_sport` held FRAMEWORK
-- sport names (`Adventure Racing`, `Long Distance / Endurance Cycling`, `Off-Road /
-- Adventure Multisport (Non-Nav)`) — none of which exist as a sport_exercise_map
-- tag, so the join matched nothing. The correct exercise-DB tags already exist:
-- `Mountain Biking` (37 exercises, 21 strength-type) and `Packrafting` (35, 20).
-- (D-001/D-003 only work by luck — their exercise_db_sport includes `Fell Running`,
-- spelled identically in both tables.) The alias map already encodes the right
-- mapping (etl/layer0/sport_name_aliases.py) but is read only by the vocab-
-- alignment validator, never by the runtime join.
--
-- Fix: correct `exercise_db_sport` to the existing exercise-DB tag for these two
-- disciplines. NO new exercises (strict no-padding satisfied) and no exercise loss
-- (the old framework-name values matched nothing). This also RESOLVES two existing
-- `vocab_alignment` warnings (`Mountain Biking` / `Packrafting` were sport_exercise_map
-- tags missing from bridge.exercise_db_sport); that check is informational and
-- never fails the gate, so this only improves alignment.
--
-- Edit shape (README §"Two edit shapes"): SERVING-RELEVANT — the strength pool
-- goes 0 -> 37/35, which changes plan-gen output, so the changed bridge rows move
-- to a bumped 0A version (`0A-v1.6.7` -> `0A-v1.6.8`); the per-table digest in
-- `_q_current_etl_version_set` advances and plan-gen caches invalidate. The other
-- 54 active bridge rows stay at 0A-v1.6.7 (per-table max takes 1.6.8). No public-
-- schema DDL. sport_discipline_bridge is already in `_LAYER0_TABLE_FAMILY` (0A).
--
-- Idempotent: the INSERT is guarded by NOT EXISTS on a corrected active row, and
-- the supersede only touches active rows whose tag is still wrong — a re-run
-- selects nothing. The UNIQUE key is (framework_sport, discipline_id, etl_version),
-- so the new 1.6.8 rows never collide with the retired 1.6.7 rows.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole migration)
-- unless every active D-008 row is tagged `Mountain Biking`, every active D-009 row
-- is `Packrafting`, the active row counts are preserved, and the join now resolves
-- a non-empty exercise pool for both.

\set ON_ERROR_STOP on

BEGIN;

-- ── D-008 Mountain Biking → exercise-DB tag `Mountain Biking` ────────────────
INSERT INTO layer0.sport_discipline_bridge
    (framework_sport, discipline_id, discipline_name, exercise_db_sport, role,
     default_race_time_pct_low, default_race_time_pct_high, etl_version, etl_run_at)
SELECT b.framework_sport, b.discipline_id, b.discipline_name, 'Mountain Biking',
       b.role, b.default_race_time_pct_low, b.default_race_time_pct_high,
       '0A-v1.6.8', now()
  FROM layer0.sport_discipline_bridge b
 WHERE b.superseded_at IS NULL
   AND b.discipline_id = 'D-008'
   AND b.exercise_db_sport <> 'Mountain Biking'
   AND NOT EXISTS (
        SELECT 1 FROM layer0.sport_discipline_bridge c
         WHERE c.superseded_at IS NULL
           AND c.discipline_id = 'D-008'
           AND c.framework_sport = b.framework_sport
           AND c.exercise_db_sport = 'Mountain Biking');

UPDATE layer0.sport_discipline_bridge
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND discipline_id = 'D-008'
   AND exercise_db_sport <> 'Mountain Biking';

-- ── D-009 Packrafting → exercise-DB tag `Packrafting` ────────────────────────
INSERT INTO layer0.sport_discipline_bridge
    (framework_sport, discipline_id, discipline_name, exercise_db_sport, role,
     default_race_time_pct_low, default_race_time_pct_high, etl_version, etl_run_at)
SELECT b.framework_sport, b.discipline_id, b.discipline_name, 'Packrafting',
       b.role, b.default_race_time_pct_low, b.default_race_time_pct_high,
       '0A-v1.6.8', now()
  FROM layer0.sport_discipline_bridge b
 WHERE b.superseded_at IS NULL
   AND b.discipline_id = 'D-009'
   AND b.exercise_db_sport <> 'Packrafting'
   AND NOT EXISTS (
        SELECT 1 FROM layer0.sport_discipline_bridge c
         WHERE c.superseded_at IS NULL
           AND c.discipline_id = 'D-009'
           AND c.framework_sport = b.framework_sport
           AND c.exercise_db_sport = 'Packrafting');

UPDATE layer0.sport_discipline_bridge
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND discipline_id = 'D-009'
   AND exercise_db_sport <> 'Packrafting';

-- ── Atomic verification ──────────────────────────────────────────────────────
DO $$
DECLARE
    d008_active int;
    d008_wrong  int;
    d009_active int;
    d009_wrong  int;
    d008_ex     int;
    d009_ex     int;
BEGIN
    SELECT count(*) INTO d008_active FROM layer0.sport_discipline_bridge
     WHERE superseded_at IS NULL AND discipline_id = 'D-008';
    SELECT count(*) INTO d008_wrong FROM layer0.sport_discipline_bridge
     WHERE superseded_at IS NULL AND discipline_id = 'D-008'
       AND exercise_db_sport <> 'Mountain Biking';
    SELECT count(*) INTO d009_active FROM layer0.sport_discipline_bridge
     WHERE superseded_at IS NULL AND discipline_id = 'D-009';
    SELECT count(*) INTO d009_wrong FROM layer0.sport_discipline_bridge
     WHERE superseded_at IS NULL AND discipline_id = 'D-009'
       AND exercise_db_sport <> 'Packrafting';
    -- the exact join the per-discipline strength pool resolves through
    SELECT count(DISTINCT sxm.exercise_id) INTO d008_ex
      FROM layer0.sport_discipline_bridge sdb
      JOIN layer0.sport_exercise_map sxm
        ON sxm.sport_name = sdb.exercise_db_sport AND sxm.superseded_at IS NULL
     WHERE sdb.superseded_at IS NULL AND sdb.discipline_id = 'D-008';
    SELECT count(DISTINCT sxm.exercise_id) INTO d009_ex
      FROM layer0.sport_discipline_bridge sdb
      JOIN layer0.sport_exercise_map sxm
        ON sxm.sport_name = sdb.exercise_db_sport AND sxm.superseded_at IS NULL
     WHERE sdb.superseded_at IS NULL AND sdb.discipline_id = 'D-009';

    IF d008_wrong <> 0 OR d009_wrong <> 0 THEN
        RAISE EXCEPTION '0019: stale-tag bridge rows remain (D-008 wrong=%, D-009 wrong=%)',
            d008_wrong, d009_wrong;
    END IF;
    IF d008_active = 0 OR d009_active = 0 THEN
        RAISE EXCEPTION '0019: active bridge rows lost (D-008=%, D-009=%)',
            d008_active, d009_active;
    END IF;
    IF d008_ex = 0 OR d009_ex = 0 THEN
        RAISE EXCEPTION '0019: strength pool still empty after remap (D-008 ex=%, D-009 ex=%)',
            d008_ex, d009_ex;
    END IF;
END $$;

COMMIT;
