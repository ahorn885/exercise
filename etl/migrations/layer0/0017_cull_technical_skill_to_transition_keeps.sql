-- 0017_cull_technical_skill_to_transition_keeps.sql
--
-- #698 Track 2 — curate the 'Technical / Skill' library down to the drills that
-- are physically trainable / transition- and carry-focused. After 0009 retired
-- the 10 clear non-trainables, 55 'Technical / Skill' rows remained. Andy ratified
-- (AskUserQuestion, 2026-06-19) keeping only EIGHT and retiring the other 47:
--   KEEP (8): EX070 Single-Leg Cycling Drill · EX144 Hike-a-Bike Carry ·
--             EX163 Canoe Portage Yoke Carry · EX170 SkiMo Race Transition ·
--             EX175 Brick Run (Bike-to-Run) · EX176 Triathlon Transition (T1&T2) ·
--             EX183 Running with Poles · EX196 Obstacle Vault & Wall Traversal
-- The 47 retired are pure in-sport technique-acquisition drills (strokes, rolls,
-- line reading, ski edging, navigation, climbing footwork, descent technique,
-- entry/exit familiarization) that a coach does not program as a standalone
-- prescribable session. Active 'Technical / Skill' drops 55 -> 8.
--
-- Coverage note (Andy-ratified, eyes-open): the cull zeroes 'Technical / Skill'
-- sport_exercise_map coverage for 17 sports (all paddle/climb/snow/pure-run
-- disciplines); those sports retain their Interval/Tempo + Aerobic/Endurance
-- cardio drills, and the EX290/EX291 additions (migration 0018) refill the
-- running/swimming side. 104 active sport_exercise_map rows are superseded.
--
-- FK integrity (validate_layer0 has NO exercises-FK validator — see 0009 — so the
-- atomic DO block below verifies it itself). Seven SURVIVING rows reference a
-- culled id and are repointed (dangling progression/regression nulled; culled
-- physical_proxies elements stripped), then re-inserted at the bumped version:
--   * EX170 (KEEP)  regression EX168 -> null
--   * EX176 (KEEP)  physical_proxies: drop EX180
--   * EX183 (KEEP)  progression EX051 -> null; regression EX118 -> null; proxy: drop EX118
--   * EX173 (Isometric)        progression EX171 -> null
--   * EX201 (Isometric)        progression EX200 -> null
--   * EX203 (Interval/Tempo)   regression EX200 -> null
--   * EX288 (Interval/Tempo)   regression EX113 -> null; proxy: drop EX113
-- (All other inbound references into the cull set are internal to the cull set and
-- retire together.)
--
-- Edit shapes (README §"Two edit shapes"):
--   * 47 culled exercises + their sport_exercise_map rows: supersede-only (history
--     preserved; both auto-excluded by the superseded_at IS NULL readers in
--     layer2c/2d builders).
--   * 7 surviving repointed rows: SERVING-RELEVANT edit (progression/regression/
--     physical_proxies feed plan-gen + Tier-3 resolution) -> supersede + re-insert
--     at 0B-v1.6.14 -> 0B-v1.6.15, so the exercises-table digest advances and
--     plan-gen caches invalidate. No public-schema DDL. No LAYER4_PROMPT_REVISION
--     bump (data-only; cache rides the 0B digest, same as 0007/0008/0009).
--
-- Idempotent: the survivor re-insert is guarded to rows not yet at 0B-v1.6.15 that
-- still reference a culled id (the cleaned re-inserts reference none and carry the
-- new version, so a re-run selects nothing); the supersede UPDATEs match only
-- still-active rows. A re-run is a clean no-op.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- culled exercise is still active, any active exercise still references a culled
-- id (progression/regression/physical_proxies), any active sport_exercise_map row
-- still maps one, fewer/more than 7 survivors were repointed, or the active
-- 'Technical / Skill' count is not 8 (= 55 - 47).

\set ON_ERROR_STOP on

BEGIN;

-- The 47 exercise_ids retired from the 'Technical / Skill' library.
CREATE TEMP TABLE _cull_exercises (exercise_id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _cull_exercises (exercise_id) VALUES
  ('EX051'),('EX052'),('EX057'),('EX058'),('EX071'),('EX072'),('EX091'),('EX092'),
  ('EX093'),('EX112'),('EX113'),('EX114'),('EX116'),('EX118'),('EX124'),('EX125'),
  ('EX130'),('EX131'),('EX138'),('EX140'),('EX142'),('EX149'),('EX156'),('EX157'),
  ('EX158'),('EX159'),('EX162'),('EX164'),('EX165'),('EX166'),('EX167'),('EX168'),
  ('EX169'),('EX171'),('EX172'),('EX180'),('EX184'),('EX185'),('EX186'),('EX194'),
  ('EX197'),('EX199'),('EX200'),('EX212'),('EX213'),('EX214'),('EX215');

-- ── (0B-i) Repoint the 7 surviving rows that reference a culled id ─────────────
-- Re-insert each still-active, non-culled row that names a culled id in
-- progression/regression/physical_proxies, with the dangling links nulled and the
-- culled proxy elements stripped (order preserved), at the bumped version. Every
-- other column copied verbatim; id (serial) + superseded_at (NULL) omitted.
INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured,
  movement_components
)
SELECT
  e.exercise_id, e.exercise_name, e.exercise_type, e.movement_patterns, e.primary_muscles,
  e.secondary_muscles, e.equipment_required, e.injury_flags_text, e.contraindicated_parts,
  e.contraindicated_conditions, e.equipment_substitutes,
  COALESCE(
    (SELECT jsonb_agg(elem ORDER BY ord)
       FROM jsonb_array_elements(e.physical_proxies) WITH ORDINALITY AS u(elem, ord)
      WHERE elem->>'exercise_id' NOT IN (SELECT exercise_id FROM _cull_exercises)),
    '[]'::jsonb),
  CASE WHEN e.progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
       THEN NULL ELSE e.progression_exercise_id END,
  CASE WHEN e.progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
       THEN NULL ELSE e.progression_exercise_name END,
  CASE WHEN e.regression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
       THEN NULL ELSE e.regression_exercise_id END,
  CASE WHEN e.regression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
       THEN NULL ELSE e.regression_exercise_name END,
  e.sport_count, e.coaching_cues,
  '0B-v1.6.15', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.15'
  AND e.exercise_id NOT IN (SELECT exercise_id FROM _cull_exercises)
  AND (
        e.progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
     OR e.regression_exercise_id  IN (SELECT exercise_id FROM _cull_exercises)
     OR EXISTS (SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
                 WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises))
  );

-- Supersede the old (dangling-ref-bearing) rows now replaced by the cleaned copies.
UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.etl_version <> '0B-v1.6.15'
   AND e.exercise_id NOT IN (SELECT exercise_id FROM _cull_exercises)
   AND (
         e.progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
      OR e.regression_exercise_id  IN (SELECT exercise_id FROM _cull_exercises)
      OR EXISTS (SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
                  WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises))
   );

-- ── (0B-ii) Retire the 47 culled exercises ────────────────────────────────────
UPDATE layer0.exercises e
   SET superseded_at = now()
  FROM _cull_exercises c
 WHERE e.exercise_id = c.exercise_id
   AND e.superseded_at IS NULL;

-- ── (0B-iii) Retire the culled exercises' sport_exercise_map rows ──────────────
UPDATE layer0.sport_exercise_map m
   SET superseded_at = now()
  FROM _cull_exercises c
 WHERE m.exercise_id = c.exercise_id
   AND m.superseded_at IS NULL;

-- ── Verify (atomic — any failure rolls back the whole migration) ──────────────
DO $$
DECLARE
  v_left   INT;
  v_prog   INT;
  v_regr   INT;
  v_proxy  INT;
  v_map    INT;
  v_repnt  INT;
  v_count  INT;
  v_keeps  INT;
BEGIN
  -- No culled exercise is still active.
  SELECT count(*) INTO v_left
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  IF v_left > 0 THEN
    RAISE EXCEPTION '0017: % culled exercise(s) still active', v_left;
  END IF;

  -- No active exercise still references a culled id (the exercises-FK check the
  -- standing validator lacks).
  SELECT count(*) INTO v_prog FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  SELECT count(*) INTO v_regr FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND regression_exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  SELECT count(*) INTO v_proxy
    FROM layer0.exercises e, jsonb_array_elements(e.physical_proxies) p
   WHERE e.superseded_at IS NULL
     AND p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises);
  IF v_prog + v_regr + v_proxy > 0 THEN
    RAISE EXCEPTION '0017: dangling FK ref(s) after cull (progression=%, regression=%, proxy=%)',
      v_prog, v_regr, v_proxy;
  END IF;

  -- No active sport_exercise_map row still maps a culled exercise.
  SELECT count(*) INTO v_map FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  IF v_map > 0 THEN
    RAISE EXCEPTION '0017: % active sport_exercise_map row(s) still map a culled exercise', v_map;
  END IF;

  -- Exactly 7 surviving rows were repointed (re-inserted active at 0B-v1.6.15).
  SELECT count(*) INTO v_repnt FROM layer0.exercises
   WHERE superseded_at IS NULL AND etl_version = '0B-v1.6.15';
  IF v_repnt <> 7 THEN
    RAISE EXCEPTION '0017: expected 7 repointed survivors at 0B-v1.6.15, found %', v_repnt;
  END IF;

  -- The 8 keeps are all still active.
  SELECT count(*) INTO v_keeps FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX070','EX144','EX163','EX170','EX175','EX176','EX183','EX196');
  IF v_keeps <> 8 THEN
    RAISE EXCEPTION '0017: expected 8 KEEP exercises active, found %', v_keeps;
  END IF;

  -- Active 'Technical / Skill' count drops 55 -> 8.
  SELECT count(*) INTO v_count FROM layer0.exercises
   WHERE superseded_at IS NULL AND exercise_type = 'Technical / Skill';
  IF v_count <> 8 THEN
    RAISE EXCEPTION '0017: expected 8 active Technical/Skill exercises, found %', v_count;
  END IF;

  RAISE NOTICE '0017: OK — 47 Technical/Skill exercises retired (55->8); 7 survivors repointed; sport_exercise_map cleaned';
END $$;

COMMIT;

-- End of 0017_cull_technical_skill_to_transition_keeps.sql
