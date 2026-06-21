-- 0021_cull_rope_climb_foot_smear.sql
--
-- #698 equipment-gating soundness (the audit's first finding, 2026-06-17). That
-- sweep flagged 13 active exercises whose equipment_required carried a non-
-- equipment skill/discipline token ("Climbing — roped", "Touring/AT ski setup",
-- "Mountaineering") that can never be a member of the 2C effective_pool, so the
-- _tier_1 gate (equipment_required ⊆ effective_pool) can never match — the row is
-- permanently Tier-1-infeasible. The 0017 Technical/Skill cull already retired 10
-- of the 13; THREE remained active (read-only neon-query, 2026-06-20):
--   EX115 Foot Smear Strength (Incline Board)  {"Incline board","Climbing — roped"}
--   EX170 SkiMo Race Transition Drill          {"Touring/AT ski setup"}
--   EX195 Rope Climb                           {"Climbing — roped"}
--
-- Andy's disposition (2026-06-21):
--   * EX195 Rope Climb  — RETIRE (the roped-climbing capability isn't a strength
--     prescription; cull outright, #694/#0017 pattern).
--   * EX115 Foot Smear  — RETIRE (a climbing-footwork balance drill gated on a
--     wall; cull outright).
--   * EX170 SkiMo Transition — KEEP, no change. Its token "Touring/AT ski setup"
--     is the EXACT name of the active layer0.sport_specific_gear_toggles row (the
--     "AT gear toggle"), so EX170 is already gated on that toggle — not a vocab
--     error. (Whether enabling that toggle injects its token into the effective
--     pool — all 12 toggles carry an empty paired_equipment_categories — is a
--     separate, broader gear-toggle wiring question, out of scope here.)
--
-- So this migration retires EX115 + EX195 only. EX170 is untouched.
--
-- FK integrity (validate_layer0 has NO exercises-FK validator — see 0009/0017 — so
-- the atomic DO block verifies it itself). ONE surviving row references a culled
-- id and is repointed at the bumped version (read-only neon-query, 2026-06-20):
--   * EX196 Obstacle Vault & Wall Traversal — progression_exercise_id EX195 -> null
--     (regression EX007 + physical_proxies EX006/EX007 are clean, copied verbatim).
--
-- Alias map: provider_value_map_seed.GARMIN_STRENGTH_ALIASES carried
-- 'Rope Climb' -> 'EX195'; that entry is removed in the same PR (a culled id must
-- not stay an alias target — the #694 "respect the cull" precedent). EX115 was not
-- an alias target. Neither is a v1 exercise_inventory seed name, so no public-schema
-- catalog edit.
--
-- Edit shapes (README §"Two edit shapes"):
--   * EX115 + EX195 + their sport_exercise_map rows: supersede-only (history
--     preserved; both auto-excluded by the superseded_at IS NULL readers).
--   * EX196 (1 surviving repointed row): SERVING-RELEVANT edit (progression feeds
--     plan-gen + Tier-3 resolution) -> supersede + re-insert at 0B-v1.6.17 ->
--     0B-v1.6.18, so the exercises-table digest advances and plan-gen caches
--     invalidate. No public-schema DDL. No LAYER4_PROMPT_REVISION bump (data-only;
--     cache rides the 0B digest, same as 0009/0017).
--
-- Idempotent: the survivor re-insert is guarded to rows not yet at 0B-v1.6.18 that
-- still reference a culled id (the cleaned re-insert references none and carries the
-- new version, so a re-run selects nothing); the supersede UPDATEs match only
-- still-active rows. A re-run is a clean no-op.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if either
-- culled exercise is still active, any active exercise still references a culled id
-- (progression/regression/physical_proxies), any active sport_exercise_map row still
-- maps one, the EX196 survivor was not repointed, or an exercise_id is double-active.

\set ON_ERROR_STOP on

BEGIN;

-- The exercise_ids retired here.
CREATE TEMP TABLE _cull_exercises (exercise_id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _cull_exercises (exercise_id) VALUES ('EX115'), ('EX195');

-- ── (i) Repoint the surviving row(s) that reference a culled id ───────────────
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
  '0B-v1.6.18', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.18'
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
   AND e.etl_version <> '0B-v1.6.18'
   AND e.exercise_id NOT IN (SELECT exercise_id FROM _cull_exercises)
   AND (
         e.progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises)
      OR e.regression_exercise_id  IN (SELECT exercise_id FROM _cull_exercises)
      OR EXISTS (SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
                  WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises))
   );

-- ── (ii) Retire the culled exercises ──────────────────────────────────────────
UPDATE layer0.exercises e
   SET superseded_at = now()
  FROM _cull_exercises c
 WHERE e.exercise_id = c.exercise_id
   AND e.superseded_at IS NULL;

-- ── (iii) Retire the culled exercises' sport_exercise_map rows ────────────────
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
  v_dup    INT;
BEGIN
  -- No culled exercise is still active.
  SELECT count(*) INTO v_left FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX115', 'EX195');
  IF v_left > 0 THEN
    RAISE EXCEPTION '0021: % culled exercise(s) still active', v_left;
  END IF;

  -- No active exercise still references a culled id (the exercises-FK check the
  -- standing validator lacks).
  SELECT count(*) INTO v_prog FROM layer0.exercises
   WHERE superseded_at IS NULL AND progression_exercise_id IN ('EX115', 'EX195');
  SELECT count(*) INTO v_regr FROM layer0.exercises
   WHERE superseded_at IS NULL AND regression_exercise_id IN ('EX115', 'EX195');
  SELECT count(*) INTO v_proxy FROM layer0.exercises e
   WHERE e.superseded_at IS NULL
     AND EXISTS (SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
                  WHERE p->>'exercise_id' IN ('EX115', 'EX195'));
  IF v_prog + v_regr + v_proxy > 0 THEN
    RAISE EXCEPTION '0021: dangling refs to culled ids — prog=% regr=% proxy=%',
      v_prog, v_regr, v_proxy;
  END IF;

  -- No active sport_exercise_map row maps a culled exercise.
  SELECT count(*) INTO v_map FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL AND exercise_id IN ('EX115', 'EX195');
  IF v_map > 0 THEN
    RAISE EXCEPTION '0021: % active sport_exercise_map row(s) still map a culled id', v_map;
  END IF;

  -- The EX196 survivor was repointed (active, at the bumped version, no dangling progression).
  SELECT count(*) INTO v_repnt FROM layer0.exercises
   WHERE superseded_at IS NULL AND exercise_id = 'EX196'
     AND etl_version = '0B-v1.6.18' AND progression_exercise_id IS NULL;
  IF v_repnt <> 1 THEN
    RAISE EXCEPTION '0021: expected EX196 repointed (active, 0B-v1.6.18, null progression), found %', v_repnt;
  END IF;

  -- No exercise_id is double-active (supersede landed).
  SELECT count(*) INTO v_dup FROM (
    SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL
     GROUP BY exercise_id HAVING count(*) > 1) d;
  IF v_dup > 0 THEN RAISE EXCEPTION '0021: % exercise_id(s) double-active after supersede', v_dup; END IF;

  RAISE NOTICE '0021: OK — EX115 + EX195 retired (Climbing — roped vocab); EX196 progression repointed; EX170 left gated on the Touring/AT ski setup toggle';
END $$;

COMMIT;

-- End of 0021_cull_rope_climb_foot_smear.sql
