-- 0009_cull_nontrainable_technical_skill.sql
--
-- #644 — curate the "Technical / Skill" exercise library. 65 of 211 active
-- exercises are typed 'Technical / Skill'; most are legitimate skill *sessions*
-- a coach programs (roll practice, transitions, line reading, navigation, stroke
-- and cadence drills, pacing methods, self-arrest), but a handful are
-- non-trainable familiarization, gear setup, or a coaching cue mislabelled as a
-- prescribable exercise. Because these live in sport_exercise_map, Layer 4 can
-- prescribe them into a plan ("do Snowshoe Gait Technique this week").
--
-- Andy-ratified via AskUserQuestion (2026-06-16; Trigger #2 — exercise-DB
-- curation; the strict no-padding rule applied in reverse: retire ONLY true
-- non-exercises). Decision: keep 'Technical / Skill' a prescribable
-- exercise_type and cull only (no separate skill-lane). Retire the 10 below
-- (the 6 clear-cut non-sessions + 4 borderline Andy ruled to cull):
--   EX094  Packraft Inflation / Deflation Drill   — gear handling
--   EX121  Trekking Pole Technique (Descent Braking) — a descent cue
--   EX122  Hip Hinge Under Pack (Practice Drill)   — pack pickup/setdown drill
--   EX123  Pack Fit Optimization Drill            — gear setup
--   EX148  Crampon Walking Technique              — gear familiarization
--   EX150  Rest Step Technique                    — a pacing/breathing cue
--   EX152  Post-Hole Recovery Gait                — pace-management cue
--   EX153  Snowshoe Gait Technique                — "adapts in 30–60 min"
--   EX154  Plunge Step Descent (Snowshoe)         — snowshoe familiarization
--   EX155  Snowshoe Sidehill Traverse & Kickturn  — snowshoe familiarization
-- EX118 (Trekking Pole Push) was reviewed and KEPT — a real propulsion-economy
-- technique that is also EX183's regression link.
--
-- FK integrity (the issue's caution; verified live via read-only neon-query):
--   * The snowshoe trio (EX153/EX154/EX155) progression/regression links are all
--     INTERNAL to the trio — culling them together is self-contained.
--   * The 6 confident culls + EX121/EX122 have ZERO inbound references.
--   * The ONLY external reference into the cull set is EX176 (Triathlon
--     Transition Practice, KEPT), which lists EX094 in physical_proxies. This
--     migration repoints it: EX176 is superseded + re-inserted at the bumped
--     version with the EX094 proxy stripped (its other proxy, EX180, preserved).
--   NOTE: validate_layer0 has no exercises-FK validator (it only FK-checks the
--   disciplines family), so the gate would NOT catch a dangling
--   progression/regression/physical_proxies ref — the atomic DO block below does
--   that verification itself (no active row may reference a culled exercise).
--
-- sport_exercise_map: Layer 2C/2D read it only through a JOIN to exercises with
-- e.superseded_at IS NULL (layer2c/builder.py, layer2d/builder.py), so
-- superseding the exercise already makes the mapping inert. We additionally
-- supersede the culled exercises' sport_exercise_map rows so the table stays
-- consistent with the retired exercises (data hygiene).
--
-- Edit shape (README §"Two edit shapes"):
--   * culled exercises + their sport_exercise_map rows: supersede-only (history
--     preserved; both are auto-excluded by the superseded_at IS NULL readers).
--   * EX176: SERVING-RELEVANT edit (physical_proxies feeds Tier-3 resolution) —
--     supersede + re-insert at 0B-v1.6.9 -> 0B-v1.6.10, so the exercises-table
--     digest advances and plan-gen caches invalidate. This reinsert is also the
--     migration's version-bump carrier. No public-schema DDL. No
--     LAYER4_PROMPT_REVISION bump (data-only; cache rides the 0B digest, same as
--     0007/0008).
--
-- Idempotent: the EX176 reinsert is guarded to the pre-bump row (etl_version <>
-- '0B-v1.6.10' AND a culled proxy present); the reinserted row carries no culled
-- proxy and the new version, so a re-run selects nothing. The supersede UPDATEs
-- match only still-active rows. A re-run is a clean no-op.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- culled exercise is still active, any active exercise still references a culled
-- id (progression/regression/physical_proxies), any active sport_exercise_map
-- row still maps one, EX176 was not repointed, or the active 'Technical / Skill'
-- count is not the expected 55 (= 65 - 10; guards against a typo'd cull id).

\set ON_ERROR_STOP on

BEGIN;

-- The 10 exercise_ids retired from the library. Dropped at COMMIT.
CREATE TEMP TABLE _cull_exercises (exercise_id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _cull_exercises (exercise_id) VALUES
  ('EX094'), ('EX121'), ('EX122'), ('EX123'), ('EX148'),
  ('EX150'), ('EX152'), ('EX153'), ('EX154'), ('EX155');

-- ── (0B-i) Repoint the one external FK: EX176 lists EX094 in physical_proxies ──
-- Re-insert each still-active KEPT exercise whose physical_proxies names a culled
-- id, with those proxy elements removed (order preserved), at the bumped
-- version. Every other column copied verbatim; id (serial) + superseded_at (NULL)
-- omitted. In practice this is EX176 only.
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
  e.progression_exercise_id, e.progression_exercise_name, e.regression_exercise_id,
  e.regression_exercise_name, e.sport_count, e.coaching_cues,
  '0B-v1.6.10', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.10'
  AND e.exercise_id NOT IN (SELECT exercise_id FROM _cull_exercises)
  AND EXISTS (
        SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
         WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises));

-- Supersede the old (culled-proxy-bearing) rows now replaced by the cleaned copies.
UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.etl_version <> '0B-v1.6.10'
   AND e.exercise_id NOT IN (SELECT exercise_id FROM _cull_exercises)
   AND EXISTS (
         SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
          WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises));

-- ── (0B-ii) Retire the 10 culled exercises ───────────────────────────────────
-- Supersede-only (history preserved). The 2C/2D readers filter
-- superseded_at IS NULL, so they leave the library immediately.
UPDATE layer0.exercises e
   SET superseded_at = now()
  FROM _cull_exercises c
 WHERE e.exercise_id = c.exercise_id
   AND e.superseded_at IS NULL;

-- ── (0B-iii) Retire the culled exercises' sport_exercise_map rows ─────────────
-- Already inert via the exercises JOIN filter; superseded here for consistency.
UPDATE layer0.sport_exercise_map m
   SET superseded_at = now()
  FROM _cull_exercises c
 WHERE m.exercise_id = c.exercise_id
   AND m.superseded_at IS NULL;

-- ── Verify (atomic — any failure rolls back the whole migration) ──────────────
DO $$
DECLARE
  v_left  INT;
  v_prog  INT;
  v_regr  INT;
  v_proxy INT;
  v_map   INT;
  v_ex176 INT;
  v_count INT;
BEGIN
  -- No culled exercise is still active.
  SELECT count(*) INTO v_left
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  IF v_left > 0 THEN
    RAISE EXCEPTION '0009: % culled exercise(s) still active', v_left;
  END IF;

  -- No active exercise still references a culled id (the exercises-FK check the
  -- standing validator lacks).
  SELECT count(*) INTO v_prog
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND progression_exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  SELECT count(*) INTO v_regr
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND regression_exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  SELECT count(*) INTO v_proxy
    FROM layer0.exercises e, jsonb_array_elements(e.physical_proxies) p
   WHERE e.superseded_at IS NULL
     AND p->>'exercise_id' IN (SELECT exercise_id FROM _cull_exercises);
  IF v_prog + v_regr + v_proxy > 0 THEN
    RAISE EXCEPTION '0009: dangling FK ref(s) after cull (progression=%, regression=%, proxy=%)',
      v_prog, v_regr, v_proxy;
  END IF;

  -- No active sport_exercise_map row still maps a culled exercise.
  SELECT count(*) INTO v_map
    FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN (SELECT exercise_id FROM _cull_exercises);
  IF v_map > 0 THEN
    RAISE EXCEPTION '0009: % active sport_exercise_map row(s) still map a culled exercise', v_map;
  END IF;

  -- EX176 survived the repoint: active at the bumped version, EX094 stripped, and
  -- its surviving proxy (EX180) intact (guards against an over-broad strip).
  SELECT count(*) INTO v_ex176
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id = 'EX176'
     AND etl_version = '0B-v1.6.10'
     AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(physical_proxies) p WHERE p->>'exercise_id' = 'EX094')
     AND EXISTS     (SELECT 1 FROM jsonb_array_elements(physical_proxies) p WHERE p->>'exercise_id' = 'EX180');
  IF v_ex176 <> 1 THEN
    RAISE EXCEPTION '0009: EX176 repoint check failed (expected 1, got %)', v_ex176;
  END IF;

  -- Exactly 10 retired: the active 'Technical / Skill' count drops 65 -> 55.
  -- (Guards against a typo'd cull id that would supersede fewer rows.)
  SELECT count(*) INTO v_count
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_type = 'Technical / Skill';
  IF v_count <> 55 THEN
    RAISE EXCEPTION '0009: expected 55 active Technical/Skill exercises, found %', v_count;
  END IF;

  RAISE NOTICE '0009: OK — 10 non-trainable Technical/Skill exercises retired; EX176 proxy repointed; sport_exercise_map cleaned';
END $$;

COMMIT;

-- End of 0009_cull_nontrainable_technical_skill.sql
