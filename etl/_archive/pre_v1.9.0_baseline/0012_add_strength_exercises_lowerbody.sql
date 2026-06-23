-- 0012_add_strength_exercises_lowerbody.sql
--
-- #679 (provider data translation — Garmin strength resolution). New layer0
-- exercises so Andy's logged lower-body lifts resolve to a real EX-id and become
-- capacity-derived loads. Trigger #2 ratified per-entry on the #679 review sheet
-- (designs/ProviderTranslation_GarminStrength_679_NewExercise_ReviewSheet_v1.md;
-- Andy 2026-06-17: mint, Tier 3 = full prescribable). FIRST FAMILY SLICE
-- (lower-body, EX250-EX254) — the remaining families land in 0013-0015.
--
-- Per-entry calls (MP -> rx class via layer0_progression crosswalk; equipment
-- per the review sheet; injury_flags general biomechanics, NOT athlete-specific
-- per Andy's "this app isn't just for me" rule):
--   EX250 Walking Lunge          {Single-Leg,Locomotion} -> Lunge. DB/KB load.
--   EX251 Overhead Bulgarian Split Squat {Single-Leg} -> Lunge. DB/KB.
--   EX252 Hack Squat             {Squat} -> Squat. Machine/Barbell.
--   EX253 Box Squat              {Squat} -> Squat. Barbell.
--   EX254 Sumo Deadlift          {Hinge} -> Hinge. Barbell/KB/DB (generic — was
--         "KB Sumo Deadlift"; Andy: allow kb, db or barbell).
--
-- Edit shape (README "Two edit shapes"): SERVING-RELEVANT — new programmable
-- exercises that change plan-gen output, so rows carry a bumped exercises
-- version 0B-v1.6.12 -> 0B-v1.6.13 (advances the 0B per-table digest, invalidates
-- plan-gen caches). The sport_exercise_map rows carry the same 0B-v1.6.13. Pure
-- ADDITIONS (new EX-ids never existed — nothing superseded). No public-schema
-- DDL. No LAYER4_PROMPT_REVISION bump (data-only; cache rides the 0B digest).
--
-- FK integrity (#648 exercises_fk_check): every physical_proxies id and every
-- sport_exercise_map.exercise_id resolves to an ACTIVE exercise (proxies point at
-- live EX001/EX002/EX003/EX021/EX022/EX037/EX038/EX230; map rows point at the 5
-- ids this migration activates). No dangling refs introduced.
--
-- Idempotent: each INSERT guarded by NOT EXISTS on an active row for the same key.
-- Atomic: the verify DO block RAISEs (rolling back) unless exactly these 5
-- exercises are active at 0B-v1.6.13 and their map rows are active with no new
-- dangling ref.

\set ON_ERROR_STOP on

BEGIN;

-- ── EX250 Walking Lunge ───────────────────────────────────────────────────────
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
  'EX250', 'Walking Lunge', 'Strength',
  '{Single-Leg,Locomotion}'::text[],
  '{Quadriceps,Glutes}'::text[],
  '{Hamstrings,"Hip Stabilisers",Core}'::text[],
  '{Dumbbell,Kettlebell}'::text[],
  'Knee — anterior pain if the front knee drives past the toes or caves inward; Hip Flexor — tightness limiting stride length; Ankle — instability on uneven ground',
  '{Knee,"Hip Flexor",Ankle}'::text[],
  '{}'::text[],
  '{"standard": ["Reverse Lunge (stationary)", "DB / KB load", "backpack load"], "improvised": ["Bodyweight only", "water jugs for load"]}'::jsonb,
  '[{"exercise_id": "EX022", "exercise_name": "Reverse Lunge (DB or BW)"}, {"exercise_id": "EX021", "exercise_name": "Bulgarian Split Squat (DB)"}]'::jsonb,
  NULL, NULL, 'EX022', 'Reverse Lunge (DB or BW)', NULL,
  'Long, controlled stride; torso upright; push through the front heel to travel; the locomotor pattern carries directly to loaded hiking and pack-carry under fatigue',
  '0B-v1.6.13', now(), '{}'::text[], '[]'::jsonb, NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX250' AND superseded_at IS NULL);

-- ── EX251 Overhead Bulgarian Split Squat ──────────────────────────────────────
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
  'EX251', 'Overhead Bulgarian Split Squat', 'Strength',
  '{Single-Leg}'::text[],
  '{Quadriceps,Glutes}'::text[],
  '{Hamstrings,Core,"Anterior Deltoid"}'::text[],
  '{Dumbbell,Kettlebell}'::text[],
  'Knee — anterior pain if the front shin is too vertical; Shoulder — instability holding load overhead; Lumbar — extension if the core is not braced',
  '{Knee,Shoulder,"Lower back"}'::text[],
  '{}'::text[],
  '{"standard": ["Bulgarian Split Squat (load at sides)", "Goblet Bulgarian Split Squat"], "improvised": ["Single overhead KB", "backpack overhead"]}'::jsonb,
  '[{"exercise_id": "EX021", "exercise_name": "Bulgarian Split Squat (DB)"}, {"exercise_id": "EX038", "exercise_name": "Split Squat ISO Hold"}]'::jsonb,
  NULL, NULL, 'EX021', 'Bulgarian Split Squat (DB)', NULL,
  'Load locked out overhead, ribs down, core braced hard; the overhead position adds an anti-extension trunk demand on top of the single-leg strength — keep the front shin angled, not vertical',
  '0B-v1.6.13', now(), '{}'::text[], '[]'::jsonb, NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX251' AND superseded_at IS NULL);

-- ── EX252 Hack Squat ──────────────────────────────────────────────────────────
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
  'EX252', 'Hack Squat', 'Strength',
  '{Squat}'::text[],
  '{Quadriceps,Glutes}'::text[],
  '{Hamstrings,Core}'::text[],
  '{"Hack squat machine",Barbell}'::text[],
  'Knee — anterior shear at deep flexion under the fixed path; Lumbar — if the hips shoot off the pad and the back rounds',
  '{Knee,"Lower back"}'::text[],
  '{}'::text[],
  '{"standard": ["Back Squat", "Leg Press", "Goblet Squat"], "improvised": ["Heavy backpack goblet squat"]}'::jsonb,
  '[{"exercise_id": "EX001", "exercise_name": "Back Squat (Barbell)"}, {"exercise_id": "EX002", "exercise_name": "Goblet Squat (DB/KB)"}]'::jsonb,
  NULL, NULL, 'EX001', 'Back Squat (Barbell)', NULL,
  'Machine-guided squat with a quad bias; control the depth and the eccentric — the fixed path lets you load the quads hard without balancing the bar',
  '0B-v1.6.13', now(), '{}'::text[], '[]'::jsonb, NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX252' AND superseded_at IS NULL);

-- ── EX253 Box Squat ───────────────────────────────────────────────────────────
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
  'EX253', 'Box Squat', 'Strength',
  '{Squat}'::text[],
  '{Quadriceps,Glutes}'::text[],
  '{Hamstrings,"Erector Spinae",Core}'::text[],
  '{Barbell}'::text[],
  'Lumbar — flexion if the trunk relaxes on the box; Knee — impact if you drop or bounce off the box',
  '{"Lower back",Knee}'::text[],
  '{}'::text[],
  '{"standard": ["Back Squat to depth", "Goblet Box Squat"], "improvised": ["Bench or sturdy chair as the box"]}'::jsonb,
  '[{"exercise_id": "EX001", "exercise_name": "Back Squat (Barbell)"}, {"exercise_id": "EX037", "exercise_name": "Wall Sit"}]'::jsonb,
  NULL, NULL, 'EX001', 'Back Squat (Barbell)', NULL,
  'Sit back to the box under control, stay tight through the pause, then drive up — teaches consistent depth and hip drive without bouncing out of the bottom',
  '0B-v1.6.13', now(), '{}'::text[], '[]'::jsonb, NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX253' AND superseded_at IS NULL);

-- ── EX254 Sumo Deadlift (generic — KB/DB/Barbell) ─────────────────────────────
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
  'EX254', 'Sumo Deadlift', 'Strength',
  '{Hinge}'::text[],
  '{Glutes,Quadriceps,Hamstrings}'::text[],
  '{"Erector Spinae","Hip Adductors",Forearms}'::text[],
  '{Barbell,Kettlebell,Dumbbell}'::text[],
  'Lumbar — rounding under load; Hip — impingement in the wide stance at the bottom; Knee — valgus collapse on the drive',
  '{"Lower back",Hip,Knee}'::text[],
  '{}'::text[],
  '{"standard": ["Conventional Deadlift", "KB Sumo Deadlift", "Trap Bar Deadlift"], "improvised": ["Backpack or two jugs between the legs"]}'::jsonb,
  '[{"exercise_id": "EX230", "exercise_name": "Conventional Deadlift (Barbell)"}, {"exercise_id": "EX003", "exercise_name": "Romanian Deadlift (Barbell)"}]'::jsonb,
  NULL, NULL, 'EX230', 'Conventional Deadlift (Barbell)', NULL,
  'Wide stance, toes out, hips lower than conventional with a vertical torso — shorter range of motion that shifts load onto the quads and adductors; brace and push the floor away',
  '0B-v1.6.13', now(), '{}'::text[], '[]'::jsonb, NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX254' AND superseded_at IS NULL);

-- ── sport_exercise_map rows (make the 5 programmable — Tier 3) ─────────────────
-- sport_name strings are all drawn from existing active map rows (0011 set), so
-- they resolve against sport_discipline_bridge.exercise_db_sport.
INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note,
  priority, etl_version, etl_run_at
)
SELECT v.exercise_id, v.exercise_name, v.exercise_type, v.sport_name, v.note,
       v.priority, '0B-v1.6.13', now()
FROM ( VALUES
  -- EX250 Walking Lunge
  ('EX250','Walking Lunge','Strength','General Conditioning','Traveling single-leg strength with a locomotor pattern; balanced lower-body base','High'),
  ('EX250','Walking Lunge','Strength','Trail Running','Single-leg strength and stride mechanics under load for undulating terrain','High'),
  ('EX250','Walking Lunge','Strength','Hiking','Loaded single-leg strength that mirrors stepping under a pack','High'),
  ('EX250','Walking Lunge','Strength','Obstacle Course Racing','Traveling lunge strength for carries, climbs, and varied terrain','Medium'),
  ('EX250','Walking Lunge','Strength','Rock Climbing','Single-leg drive and stability for high steps and mantles','Medium'),
  -- EX251 Overhead Bulgarian Split Squat
  ('EX251','Overhead Bulgarian Split Squat','Strength','General Conditioning','Single-leg strength with an overhead anti-extension core demand','High'),
  ('EX251','Overhead Bulgarian Split Squat','Strength','Rock Climbing','Single-leg drive plus overhead shoulder stability for steep and overhanging terrain','High'),
  ('EX251','Overhead Bulgarian Split Squat','Strength','Trail Running','Single-leg durability and trunk control for technical descents','Medium'),
  ('EX251','Overhead Bulgarian Split Squat','Strength','Hiking','Single-leg strength and overhead-loaded posture for pack carriage','Medium'),
  -- EX252 Hack Squat
  ('EX252','Hack Squat','Strength','General Conditioning','Quad-biased squat strength on a fixed path; safe heavy quad loading','High'),
  ('EX252','Hack Squat','Strength','Trail Running','Quad strength for eccentric control on descents','Medium'),
  ('EX252','Hack Squat','Strength','Hiking','Quad strength base for sustained climbing and descending under load','Medium'),
  ('EX252','Hack Squat','Strength','Obstacle Course Racing','Quad strength for repeated squatting, climbing, and carries','Medium'),
  -- EX253 Box Squat
  ('EX253','Box Squat','Strength','General Conditioning','Squat strength with a controlled depth target and strong hip drive','High'),
  ('EX253','Box Squat','Strength','Trail Running','Posterior-chain and hip-drive strength for power on climbs','Medium'),
  ('EX253','Box Squat','Strength','Hiking','Hip-drive squat strength for steep step-ups under a pack','Medium'),
  ('EX253','Box Squat','Strength','Obstacle Course Racing','Hip-dominant squat strength for explosive obstacles','Medium'),
  -- EX254 Sumo Deadlift
  ('EX254','Sumo Deadlift','Strength','General Conditioning','Hip-hinge pulling strength with a quad/adductor bias','High'),
  ('EX254','Sumo Deadlift','Strength','Obstacle Course Racing','Strong floor-to-standing pull for heavy carries and drags','High'),
  ('EX254','Sumo Deadlift','Strength','Trail Running','Posterior-chain and hip strength supporting climbing power and posture','Medium'),
  ('EX254','Sumo Deadlift','Strength','Hiking','Hinge strength for lifting and load handling on the trail','Medium'),
  ('EX254','Sumo Deadlift','Strength','Rock Climbing','Hip and posterior-chain strength for heel hooks and high steps','Medium')
) AS v(exercise_id, exercise_name, exercise_type, sport_name, note, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_exercise_map m
   WHERE m.exercise_id = v.exercise_id AND m.sport_name = v.sport_name
     AND m.superseded_at IS NULL
);

-- ── Verify (atomic — any failure rolls back the whole migration) ──────────────
DO $$
DECLARE
  v_ex INT; v_map INT; v_prog INT; v_regr INT; v_proxy INT; v_mapfk INT;
BEGIN
  SELECT count(*) INTO v_ex FROM layer0.exercises
   WHERE superseded_at IS NULL AND etl_version='0B-v1.6.13'
     AND exercise_id IN ('EX250','EX251','EX252','EX253','EX254');
  IF v_ex <> 5 THEN
    RAISE EXCEPTION '0012: expected 5 new exercises active at 0B-v1.6.13, found %', v_ex;
  END IF;

  SELECT count(*) INTO v_map FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX250','EX251','EX252','EX253','EX254');
  IF v_map <> 22 THEN
    RAISE EXCEPTION '0012: expected 22 sport_exercise_map rows for the 5 new exercises, found %', v_map;
  END IF;

  SELECT count(*) INTO v_prog FROM layer0.exercises e
   WHERE e.superseded_at IS NULL AND e.progression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=e.progression_exercise_id);
  SELECT count(*) INTO v_regr FROM layer0.exercises e
   WHERE e.superseded_at IS NULL AND e.regression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=e.regression_exercise_id);
  SELECT count(*) INTO v_proxy FROM layer0.exercises e, jsonb_array_elements(
           CASE WHEN jsonb_typeof(e.physical_proxies)='array' THEN e.physical_proxies ELSE '[]'::jsonb END) p
   WHERE e.superseded_at IS NULL AND p->>'exercise_id' IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=p->>'exercise_id');
  SELECT count(*) INTO v_mapfk FROM layer0.sport_exercise_map m
   WHERE m.superseded_at IS NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=m.exercise_id);
  IF v_prog + v_regr + v_proxy + v_mapfk > 0 THEN
    RAISE EXCEPTION '0012: dangling ref(s) (prog=%, regr=%, proxy=%, map=%)', v_prog, v_regr, v_proxy, v_mapfk;
  END IF;

  RAISE NOTICE '0012: OK — 5 lower-body strength exercises (EX250-EX254) + 22 sport_exercise_map rows at 0B-v1.6.13';
END $$;

COMMIT;

-- End of 0012_add_strength_exercises_lowerbody.sql
