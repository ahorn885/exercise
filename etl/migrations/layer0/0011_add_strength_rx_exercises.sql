-- 0011_add_strength_rx_exercises.sql
--
-- #335 Phase 2b (A) — add the 4 NEW layer0 exercises that Andy's logged
-- current_rx names map to but no existing 0B entry covers (the 16-name backfill
-- in #667 mapped the rest; these 4 had "no existing value" — Andy, 2026-06-16).
-- The single-source-of-truth fix keys the strength-rx path off the layer0 EX-id,
-- so these names need real EX-ids to backfill onto (the follow-up _PG_MIGRATIONS
-- step keys Andy's 'Row' / 'Curl' / 'Sit Up' / 'KB Halo' rows to EX246-EX249).
--
-- Decision (Andy via AskUserQuestion, 2026-06-16): ALL 4 are full prescribable
-- 0B entries (added to layer0.exercises AND layer0.sport_exercise_map so the
-- synthesizer can program them — not identity-only). Per-entry 0B fields +
-- movement-pattern/rx-class calls signed off the same session:
--   EX246 Barbell Row (Bent-Over) — Strength; {Pull-H} -> rx Pull. Bilateral
--         horizontal pull, distinct from EX078 Single-Arm DB Row (unilateral)
--         and EX079 Seated Cable Row (machine).
--   EX247 Biceps Curl (DB)        — Strength; {Pull-H} -> rx Pull. Supinated
--         elbow-flexion isolation, distinct from EX234 Hammer Curl (neutral).
--         Pull-H matches the existing EX234 curl convention (Andy chose Pull-H
--         over the handoff's "Various" guess).
--   EX248 Sit-Up                  — Strength; {Anti-Extension} -> rx Core. Full
--         dynamic trunk flexion; layer0 has no plain "flexion" pattern, so it
--         takes the catalog's existing ab convention (Anti-* family, as EX224
--         Bicycle Crunch / EX225 V-Sit) to land in the Core progression class
--         without adding new vocab (Andy chose this over a new "Flexion" value).
--   EX249 Kettlebell Halo         — Strength; {Rotation,Anti-Extension} -> rx
--         Rotation. Andy: "strength and stability exercise" (NOT a warm-up /
--         mobility primer): the rotational load is weight-progressed (Rotation),
--         the anti-extension component documents the core-stability demand.
--
-- Edit shape (README "Two edit shapes"): SERVING-RELEVANT — these are new
-- programmable exercises that change plan-gen output, so the rows carry a bumped
-- exercises version 0B-v1.6.11 -> 0B-v1.6.12; the new version advances the 0B
-- per-table digest and invalidates plan-gen caches. The sport_exercise_map rows
-- carry the same 0B-v1.6.12 (its active max was 0B-v1.6.7). Pure ADDITIONS — new
-- EX-ids that never existed, so nothing is superseded. No public-schema DDL. No
-- LAYER4_PROMPT_REVISION bump (data-only; cache rides the 0B digest).
--
-- FK integrity (the #648 exercises_fk_check gate): every progression /
-- regression / physical_proxies id and every sport_exercise_map.exercise_id on
-- these rows resolves to an ACTIVE exercise — proxies/regression point at the
-- live EX078/EX079/EX234/EX005/EX224/EX225/EX016/EX082, and the map rows point
-- at the 4 ids this migration makes active. No dangling refs introduced.
--
-- Idempotent: each INSERT is guarded by NOT EXISTS on an active row for the same
-- key (exercise_id for exercises; (exercise_id, sport_name) for the map), so a
-- re-run inserts nothing. Atomic: the verify DO block RAISEs (rolling back the
-- whole txn) unless exactly the 4 exercises are active at 0B-v1.6.12, all 26 map
-- rows are active, and no new ref dangles.

\set ON_ERROR_STOP on

BEGIN;

-- ── EX246 Barbell Row (Bent-Over) ─────────────────────────────────────────────
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
  'EX246', 'Barbell Row (Bent-Over)', 'Strength',
  '{Pull-H}'::text[],
  '{"Latissimus Dorsi",Rhomboids,"Mid Traps"}'::text[],
  '{"Rear Delts",Biceps,"Erector Spinae",Core}'::text[],
  '{Barbell}'::text[],
  'Lumbar — rounding under load in the hinged hold; Shoulder — anterior stress if elbows flare wide',
  '{"Lower back",Shoulder}'::text[],
  '{}'::text[],
  '{"standard": ["DB Bent-Over Row (bilateral)", "TRX / Inverted Row", "Band bent-over row"], "improvised": ["Backpack bent-over row", "Two-jug bent-over row"]}'::jsonb,
  '[{"exercise_id": "EX078", "exercise_name": "Single-Arm DB Row"}, {"exercise_id": "EX079", "exercise_name": "Seated Cable Row (Narrow Grip)"}]'::jsonb,
  NULL, NULL, 'EX078', 'Single-Arm DB Row', NULL,
  'Hinge to about 45 degrees with a flat, braced back; pull the bar to the lower ribs with elbows tracking back, not flaring; bilateral horizontal pull that builds the mid-back pulling strength behind the paddle catch and pack-carry posture; control the eccentric — do not heave with the lower back',
  '0B-v1.6.12', now(), '{}'::text[],
  '[{"is_improvised": false, "substitute_text": "DB Bent-Over Row (bilateral)", "equipment_required": [["Dumbbell"]]}, {"is_improvised": false, "substitute_text": "TRX / Inverted Row", "equipment_required": [["TRX / suspension trainer"]]}, {"is_improvised": false, "substitute_text": "Band bent-over row", "equipment_required": [["Resistance band"]]}, {"is_improvised": true, "substitute_text": "Backpack bent-over row", "equipment_required": []}, {"is_improvised": true, "substitute_text": "Two-jug bent-over row", "equipment_required": []}]'::jsonb,
  NULL
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.exercises WHERE exercise_id = 'EX246' AND superseded_at IS NULL
);

-- ── EX247 Biceps Curl (DB) ────────────────────────────────────────────────────
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
  'EX247', 'Biceps Curl (DB)', 'Strength',
  '{Pull-H}'::text[],
  '{"Biceps Brachii"}'::text[],
  '{Brachialis,Brachioradialis,"Forearm Flexors"}'::text[],
  '{Dumbbell}'::text[],
  'Elbow — biceps-tendon stress with heavy load or swinging; Shoulder — anterior stress if the shoulders roll forward; Wrist — strain if the wrist is allowed to bend back',
  '{Elbow,Shoulder,Wrist}'::text[],
  '{}'::text[],
  '{"standard": ["Cable biceps curl", "Band curl", "Barbell / EZ-bar curl"], "improvised": ["Water-jug curl", "Backpack curl"]}'::jsonb,
  '[{"exercise_id": "EX234", "exercise_name": "Hammer Curl (DB)"}, {"exercise_id": "EX005", "exercise_name": "Dead Hang"}]'::jsonb,
  NULL, NULL, NULL, NULL, NULL,
  'Supinated grip, palms up; keep the elbows pinned to your sides and flex at the elbow only — no shoulder swing or torso heave; control the lowering over two to three seconds; supinated elbow-flexion isolation that complements the neutral-grip Hammer Curl (EX234) and supports pulling and grip endurance for paddling and climbing',
  '0B-v1.6.12', now(), '{}'::text[],
  '[{"is_improvised": false, "substitute_text": "Cable biceps curl", "equipment_required": [["Cable machine"]]}, {"is_improvised": false, "substitute_text": "Band curl", "equipment_required": [["Resistance band"]]}, {"is_improvised": false, "substitute_text": "Barbell / EZ-bar curl", "equipment_required": [["Barbell"]]}, {"is_improvised": true, "substitute_text": "Water-jug curl", "equipment_required": []}, {"is_improvised": true, "substitute_text": "Backpack curl", "equipment_required": []}]'::jsonb,
  NULL
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.exercises WHERE exercise_id = 'EX247' AND superseded_at IS NULL
);

-- ── EX248 Sit-Up ──────────────────────────────────────────────────────────────
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
  'EX248', 'Sit-Up', 'Strength',
  '{Anti-Extension}'::text[],
  '{"Rectus Abdominis"}'::text[],
  '{"Hip Flexors",Obliques,"Transverse Abdominis"}'::text[],
  '{}'::text[],
  'Lumbar — repeated spinal flexion loads the discs (limit volume if disc-sensitive); Cervical — neck strain if pulling on the head; Hip Flexor — dominates the movement if the core is weak',
  '{"Lower back",Neck,"Hip Flexor"}'::text[],
  '{}'::text[],
  '{"standard": [], "improvised": ["No equipment needed"]}'::jsonb,
  '[{"exercise_id": "EX224", "exercise_name": "Bicycle Crunch"}, {"exercise_id": "EX225", "exercise_name": "V-Sit Hold"}]'::jsonb,
  NULL, NULL, NULL, NULL, NULL,
  'Full trunk flexion — curl the spine up one vertebra at a time, do not yank from the neck; hands across the chest or fingertips light at the temples (never pulling the head); control the descent; trains dynamic rectus-abdominis flexion strength, complementing the anti-extension V-Sit (EX225) and the rotational Bicycle Crunch (EX224); keep volume moderate if the lower back is disc-sensitive',
  '0B-v1.6.12', now(), '{}'::text[],
  '[{"is_improvised": true, "substitute_text": "No equipment needed", "equipment_required": []}]'::jsonb,
  NULL
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.exercises WHERE exercise_id = 'EX248' AND superseded_at IS NULL
);

-- ── EX249 Kettlebell Halo ─────────────────────────────────────────────────────
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
  'EX249', 'Kettlebell Halo', 'Strength',
  '{Rotation,Anti-Extension}'::text[],
  '{Deltoids,"Rotator Cuff",Core}'::text[],
  '{Obliques,Trapezius,"Serratus Anterior","Thoracic Erectors"}'::text[],
  '{Kettlebell}'::text[],
  'Shoulder — impingement if the bell drifts too far from the head or the shoulders shrug; Cervical — strain if the head juts forward to clear the bell; Wrist — extension load if the wrist is not kept stacked',
  '{Shoulder,Neck,Wrist}'::text[],
  '{}'::text[],
  '{"standard": ["DB or plate halo", "Bottoms-up KB halo"], "improvised": ["Backpack or water-jug halo"]}'::jsonb,
  '[{"exercise_id": "EX016", "exercise_name": "Thoracic Rotation Drill"}, {"exercise_id": "EX082", "exercise_name": "External Rotation (Band / Cable)"}]'::jsonb,
  NULL, NULL, NULL, NULL, NULL,
  'Circle the bell slowly around the head, close to the skull with the elbows leading; keep the ribs down and the core braced hard so the motion comes from the shoulders and upper back, not the lower back — the anti-rotation/anti-extension demand is the point; controlled tempo, reverse direction each rep; builds shoulder and rotator-cuff strength with rotational core stability for overhead and pulling work; progress by load',
  '0B-v1.6.12', now(), '{}'::text[],
  '[{"is_improvised": false, "substitute_text": "DB or plate halo", "equipment_required": [["Dumbbell"]]}, {"is_improvised": false, "substitute_text": "Bottoms-up KB halo", "equipment_required": [["Kettlebell"]]}, {"is_improvised": true, "substitute_text": "Backpack or water-jug halo", "equipment_required": []}]'::jsonb,
  NULL
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.exercises WHERE exercise_id = 'EX249' AND superseded_at IS NULL
);

-- ── sport_exercise_map rows (make the 4 programmable) ─────────────────────────
-- sport_name must match an active sport_discipline_bridge.exercise_db_sport (all
-- strings below are drawn from existing active map rows, so they resolve).
INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note,
  priority, etl_version, etl_run_at
)
SELECT v.exercise_id, v.exercise_name, v.exercise_type, v.sport_name, v.note,
       v.priority, '0B-v1.6.12', now()
FROM ( VALUES
  -- EX246 Barbell Row (Bent-Over)
  ('EX246','Barbell Row (Bent-Over)','Strength','Rowing','Bilateral horizontal pull that directly mirrors the rowing drive; primary mid-back and lat strength builder','Critical'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Kayaking','Builds the bilateral pulling strength behind the forward-stroke catch','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Canoeing','Posterior-chain and mid-back strength for sustained single-blade pulling','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Packrafting','Mid-back pulling strength for paddle propulsion and self-rescue','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Paddle Rafting','Bilateral pulling base for sustained raft paddling','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','SUP','Mid-back and lat strength supporting the paddle catch and upright posture','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Long Distance Paddle Racing','Endurance-pull strength base for the catch phase over long durations','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Obstacle Course Racing','Pulling strength for carries, climbs, and drags','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','General Conditioning','Foundational bilateral horizontal pull for balanced upper-body strength','High'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Trail Running','Mid-back and postural strength for upright posture under pack','Medium'),
  ('EX246','Barbell Row (Bent-Over)','Strength','Hiking','Postural pulling strength supporting pack carriage','Medium'),
  -- EX247 Biceps Curl (DB)
  ('EX247','Biceps Curl (DB)','Strength','General Conditioning','Elbow-flexor isolation for balanced arm strength','High'),
  ('EX247','Biceps Curl (DB)','Strength','Rock Climbing','Supplemental elbow-flexor strength supporting pulling and lock-off','Medium'),
  ('EX247','Biceps Curl (DB)','Strength','Kayaking','Accessory pulling and grip strength for the paddle stroke','Medium'),
  ('EX247','Biceps Curl (DB)','Strength','Canoeing','Accessory elbow-flexor strength for single-blade pulling','Medium'),
  ('EX247','Biceps Curl (DB)','Strength','Packrafting','Accessory arm strength for paddle propulsion','Medium'),
  -- EX248 Sit-Up
  ('EX248','Sit-Up','Strength','General Conditioning','Dynamic trunk-flexion strength for balanced core development','High'),
  ('EX248','Sit-Up','Strength','Kayaking','Trunk-flexion strength for the seated paddling posture and rotation base','High'),
  ('EX248','Sit-Up','Strength','Packrafting','Core flexion strength for boat seating and bracing','High'),
  ('EX248','Sit-Up','Strength','Canoeing','Trunk strength supporting the kneeling and seated paddling position','Medium'),
  ('EX248','Sit-Up','Strength','Rowing','Trunk-flexion strength supporting the drive-to-finish body swing','Medium'),
  -- EX249 Kettlebell Halo
  ('EX249','Kettlebell Halo','Strength','General Conditioning','Loaded shoulder strength with rotational core stability','High'),
  ('EX249','Kettlebell Halo','Strength','Rock Climbing','Shoulder and rotator-cuff strength and stability for overhead and steep terrain','Medium'),
  ('EX249','Kettlebell Halo','Strength','Kayaking','Shoulder stability and anti-rotation core control for the paddle stroke','Medium'),
  ('EX249','Kettlebell Halo','Strength','Packrafting','Shoulder and thoracic strength with core stability for paddling','Medium'),
  ('EX249','Kettlebell Halo','Strength','SUP','Shoulder stability and standing anti-rotation control','Medium')
) AS v(exercise_id, exercise_name, exercise_type, sport_name, note, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_exercise_map m
   WHERE m.exercise_id = v.exercise_id
     AND m.sport_name = v.sport_name
     AND m.superseded_at IS NULL
);

-- ── Verify (atomic — any failure rolls back the whole migration) ──────────────
DO $$
DECLARE
  v_ex    INT;
  v_map   INT;
  v_prog  INT;
  v_regr  INT;
  v_proxy INT;
  v_mapfk INT;
BEGIN
  -- Exactly the 4 new exercises active at the bumped version (digest carrier).
  SELECT count(*) INTO v_ex
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND etl_version = '0B-v1.6.12'
     AND exercise_id IN ('EX246','EX247','EX248','EX249');
  IF v_ex <> 4 THEN
    RAISE EXCEPTION '0011: expected 4 new exercises active at 0B-v1.6.12, found %', v_ex;
  END IF;

  -- All 26 map rows for the 4 new exercises are active.
  SELECT count(*) INTO v_map
    FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX246','EX247','EX248','EX249');
  IF v_map <> 26 THEN
    RAISE EXCEPTION '0011: expected 26 sport_exercise_map rows for the 4 new exercises, found %', v_map;
  END IF;

  -- No new dangling reference: every progression / regression / proxy id on the
  -- new rows, and every map row, resolves to an active exercise.
  SELECT count(*) INTO v_prog
    FROM layer0.exercises e
   WHERE e.superseded_at IS NULL
     AND e.progression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a
                      WHERE a.superseded_at IS NULL AND a.exercise_id = e.progression_exercise_id);
  SELECT count(*) INTO v_regr
    FROM layer0.exercises e
   WHERE e.superseded_at IS NULL
     AND e.regression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a
                      WHERE a.superseded_at IS NULL AND a.exercise_id = e.regression_exercise_id);
  SELECT count(*) INTO v_proxy
    FROM layer0.exercises e, jsonb_array_elements(
           CASE WHEN jsonb_typeof(e.physical_proxies) = 'array'
                THEN e.physical_proxies ELSE '[]'::jsonb END) p
   WHERE e.superseded_at IS NULL
     AND p->>'exercise_id' IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a
                      WHERE a.superseded_at IS NULL AND a.exercise_id = p->>'exercise_id');
  SELECT count(*) INTO v_mapfk
    FROM layer0.sport_exercise_map m
   WHERE m.superseded_at IS NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a
                      WHERE a.superseded_at IS NULL AND a.exercise_id = m.exercise_id);
  IF v_prog + v_regr + v_proxy + v_mapfk > 0 THEN
    RAISE EXCEPTION '0011: dangling ref(s) remain (prog=%, regr=%, proxy=%, map=%)',
      v_prog, v_regr, v_proxy, v_mapfk;
  END IF;

  RAISE NOTICE '0011: OK — 4 new strength-rx exercises (EX246-EX249) + 26 sport_exercise_map rows added at 0B-v1.6.12';
END $$;

COMMIT;

-- End of 0011_add_strength_rx_exercises.sql
