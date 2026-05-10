-- migrate_drop_technique_exercises.sql
-- Supersedes the 52 technique-only exercises that have been migrated to
-- layer0.discipline_technique_foci as of Batch B.
--
-- Pattern: row invalidation, not DELETE. Preserves audit trail —
-- prior etl_version rows can still be queried for historical reasoning.
--
-- Affected tables:
--   - layer0.exercises          (52 rows superseded)
--   - layer0.sport_exercise_map (all rows superseded for these 52 exercise_ids)
--
-- The 52 IDs are the drop list classified in Batch B planning. See
-- Batch_A_Done_Batches_BC_Kickoff_Handoff.md and the Batch B drop list doc.
--
-- Idempotent: WHERE clauses guard with `superseded_at IS NULL` so re-running
-- is a no-op. Verify block confirms expected row counts.
--
-- etl_version stamp: rows are not re-inserted at a new etl_version (they're
-- gone, not changed). The supersede timestamp marks Batch B's drop event.

BEGIN;

-- ── 1. Define the drop list as a CTE for re-use ────────────────────────────

-- Use a temp table so the same list is referenced by both UPDATE statements
-- and the verify block without copy-pasting 52 IDs four times.

CREATE TEMP TABLE _batch_b_drops (exercise_id TEXT PRIMARY KEY) ON COMMIT DROP;

INSERT INTO _batch_b_drops (exercise_id) VALUES
  -- Navigation
  ('EX057'), ('EX058'),
  -- MTB skill
  ('EX071'), ('EX072'),
  -- Climbing technique
  ('EX112'), ('EX113'), ('EX114'), ('EX116'), ('EX130'), ('EX131'), ('EX138'),
  -- Trekking poles + pack drills
  ('EX118'), ('EX121'), ('EX122'), ('EX123'), ('EX144'),
  -- Mountaineering technique
  ('EX148'), ('EX149'),
  -- Snowshoe technique
  ('EX152'), ('EX153'), ('EX154'), ('EX155'),
  -- Paddle technique (kayak / canoe / packraft / raft / sea kayak)
  ('EX091'), ('EX092'), ('EX093'), ('EX094'),
  ('EX156'), ('EX157'), ('EX158'),
  ('EX162'), ('EX163'), ('EX164'), ('EX165'), ('EX166'), ('EX167'),
  -- Swim technique
  ('EX140'), ('EX142'), ('EX199'),
  -- Ski technique
  ('EX169'), ('EX170'), ('EX171'), ('EX172'),
  -- Transition drills
  ('EX175'), ('EX176'), ('EX194'),
  -- Other technique
  ('EX183'), ('EX184'), ('EX196'), ('EX200'),
  ('EX212'), ('EX213'), ('EX214');

-- Sanity check on the temp table itself before touching real tables.
DO $$
DECLARE
  drop_count INT;
BEGIN
  SELECT COUNT(*) INTO drop_count FROM _batch_b_drops;
  IF drop_count <> 52 THEN
    RAISE EXCEPTION 'migrate_drop_technique_exercises: drop list has % entries, expected 52', drop_count;
  END IF;
END $$;

-- ── 2. Snapshot pre-state (for verify) ─────────────────────────────────────

CREATE TEMP TABLE _pre_counts (
  what  TEXT,
  count INT
) ON COMMIT DROP;

INSERT INTO _pre_counts
SELECT 'exercises_active_in_drop_list',
       COUNT(*)
FROM layer0.exercises e
JOIN _batch_b_drops d USING (exercise_id)
WHERE e.superseded_at IS NULL;

INSERT INTO _pre_counts
SELECT 'sport_exercise_map_active_in_drop_list',
       COUNT(*)
FROM layer0.sport_exercise_map m
JOIN _batch_b_drops d USING (exercise_id)
WHERE m.superseded_at IS NULL;

-- ── 3. Supersede in layer0.exercises ───────────────────────────────────────

UPDATE layer0.exercises e
SET superseded_at = NOW()
FROM _batch_b_drops d
WHERE e.exercise_id = d.exercise_id
  AND e.superseded_at IS NULL;

-- ── 4. Supersede in layer0.sport_exercise_map ──────────────────────────────

UPDATE layer0.sport_exercise_map m
SET superseded_at = NOW()
FROM _batch_b_drops d
WHERE m.exercise_id = d.exercise_id
  AND m.superseded_at IS NULL;

-- ── 5. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  ex_pre        INT;
  ex_remaining  INT;
  map_pre       INT;
  map_remaining INT;
BEGIN
  SELECT count INTO ex_pre  FROM _pre_counts WHERE what = 'exercises_active_in_drop_list';
  SELECT count INTO map_pre FROM _pre_counts WHERE what = 'sport_exercise_map_active_in_drop_list';

  SELECT COUNT(*) INTO ex_remaining
  FROM layer0.exercises e
  JOIN _batch_b_drops d USING (exercise_id)
  WHERE e.superseded_at IS NULL;

  SELECT COUNT(*) INTO map_remaining
  FROM layer0.sport_exercise_map m
  JOIN _batch_b_drops d USING (exercise_id)
  WHERE m.superseded_at IS NULL;

  -- Pre-state should have been 52 active exercise rows (one per drop ID).
  -- If pre-count was already 0, the script is idempotently re-running — fine.
  -- If pre-count was non-zero, post-count must be 0.
  IF ex_pre > 0 AND ex_pre <> 52 THEN
    RAISE WARNING 'migrate_drop_technique_exercises: expected 52 active exercises in drop list pre-supersede, found %', ex_pre;
  END IF;

  IF ex_remaining <> 0 THEN
    RAISE EXCEPTION 'migrate_drop_technique_exercises: % exercise rows still active after supersede', ex_remaining;
  END IF;

  IF map_remaining <> 0 THEN
    RAISE EXCEPTION 'migrate_drop_technique_exercises: % sport_exercise_map rows still active after supersede', map_remaining;
  END IF;

  RAISE NOTICE 'migrate_drop_technique_exercises: OK — superseded % exercise rows, % map rows (pre-counts: % / %)',
    ex_pre, map_pre, ex_pre, map_pre;
END $$;

COMMIT;
