-- 0013_add_strength_exercises_lowerpull.sql
--
-- #679 family slice 2 of 4 (after 0012). New layer0 exercises ratified on the
-- #679 review sheet (Andy 2026-06-17: mint, Tier 3). Lower-body leftovers + the
-- pull family. EX255-EX267. Same shape/standard as 0012 (the calibration slice
-- Andy approved 2026-06-17). MP -> rx via the layer0_progression crosswalk;
-- equipment uses only existing valid equipment_required tokens; injury_flags are
-- general biomechanics (not athlete-specific).
--
--   EX255 Single-Leg Glute Bridge   {Hip-Ext,Single-Leg} -> Hinge
--   EX256 Banded Pull-Through        {Hip-Ext} -> Hinge
--   EX257 Stability Ball Hamstring Curl {Hip-Ext} -> Hinge
--   EX258 Standing Calf Raise        {Hip-Ext} -> Hinge (mirrors EX026 calf convention)
--   EX259 Pedal Stance Deadlift      {Hinge,Single-Leg} -> Hinge
--   EX260 Lunge to Rotation          {Single-Leg,Rotation} -> Lunge
--   EX261 Renegade Row               {Pull-H,Anti-Rotation} -> Pull
--   EX262 Straight-Arm Lat Pulldown  {Pull-V} -> Pull
--   EX263 L-Sit Pull-Up              {Pull-V,Anti-Extension} -> Pull
--   EX264 Front Lever Progression    {Anti-Extension,Pull-V} -> Pull
--   EX265 Wide-Grip Seated Cable Row {Pull-H} -> Pull
--   EX266 Close-Grip Lat Pulldown    {Pull-V} -> Pull
--   EX267 Towel Pull-Up              {Pull-V} -> Pull
--
-- SERVING-RELEVANT: rows carry 0B-v1.6.13 (same version as 0012 — the whole #679
-- new-exercise set lands at one version; the digest bumps once for the batch).
-- Pure additions, idempotent, atomic verify. Proxies point at active exercises.

\set ON_ERROR_STOP on

BEGIN;

INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured, movement_components
)
SELECT * FROM ( VALUES
  ('EX255','Single-Leg Glute Bridge','Strength','{Hip-Ext,Single-Leg}'::text[],
   '{Glutes,Hamstrings}'::text[],'{Core,"Hip Stabilisers"}'::text[],'{Dumbbell,Kettlebell,Barbell}'::text[],
   'Lumbar — hyperextension at the top if you arch; Hamstring — cramping under load; Neck — pressure if you push through the head',
   '{"Lower back",Hamstring,Neck}'::text[],'{}'::text[],
   '{"standard": ["Glute Bridge (two-leg)", "Hip Thrust"], "improvised": ["Bodyweight", "backpack on the hips"]}'::jsonb,
   '[{"exercise_id": "EX039", "exercise_name": "Glute Bridge (Double-Leg)"}, {"exercise_id": "EX019", "exercise_name": "Barbell Hip Thrust"}]'::jsonb,
   NULL,NULL,'EX039','Glute Bridge (Double-Leg)',NULL::integer,
   'Drive through the heel of the working leg, keep the hips square, squeeze the glute at the top without arching the low back; single-leg exposes side-to-side imbalance',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL::text[]),

  ('EX256','Banded Pull-Through','Strength','{Hip-Ext}'::text[],
   '{Glutes,Hamstrings}'::text[],'{"Erector Spinae",Core}'::text[],'{"Resistance band"}'::text[],
   'Lumbar — rounding under the band tension; Hamstring — overstretch if flexibility is limited',
   '{"Lower back",Hamstring}'::text[],'{}'::text[],
   '{"standard": ["Romanian Deadlift", "Cable Pull-Through", "KB Swing"], "improvised": ["Band anchored to a post"]}'::jsonb,
   '[{"exercise_id": "EX003", "exercise_name": "Romanian Deadlift (Barbell)"}, {"exercise_id": "EX031", "exercise_name": "Kettlebell Swing (Two-Hand)"}]'::jsonb,
   NULL,NULL,'EX003','Romanian Deadlift (Barbell)',NULL,
   'Hinge at the hips and let the band pull you back, then snap the hips through to lockout; teaches the hinge pattern with constant tension and low spinal load',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX257','Stability Ball Hamstring Curl','Strength','{Hip-Ext}'::text[],
   '{Hamstrings,Glutes}'::text[],'{Gastrocnemius,Core}'::text[],'{"Stability ball"}'::text[],
   'Hamstring — cramping under load; Lumbar — sagging hips if the bridge is not held',
   '{Hamstring,"Lower back"}'::text[],'{}'::text[],
   '{"standard": ["Nordic Hamstring Curl", "Machine Leg Curl", "Slider hamstring curl"], "improvised": ["Towel on a smooth floor"]}'::jsonb,
   '[{"exercise_id": "EX020", "exercise_name": "Nordic Hamstring Curl"}, {"exercise_id": "EX236", "exercise_name": "Leg Curl (Machine / Band)"}]'::jsonb,
   NULL,NULL,'EX236','Leg Curl (Machine / Band)',NULL,
   'Bridge the hips up and hold them high, curl the ball in with the heels under control; eccentric hamstring strength with a knee-flexion bias that complements the hip-hinge work',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX258','Standing Calf Raise','Strength','{Hip-Ext}'::text[],
   '{Gastrocnemius}'::text[],'{Soleus,"Tibialis Posterior"}'::text[],'{Dumbbell,Kettlebell}'::text[],
   'Achilles — tendon stress if loaded heavy too fast; Ankle — rolling if single-leg balance is poor',
   '{Achilles,Ankle}'::text[],'{}'::text[],
   '{"standard": ["Seated Calf Raise", "Single-Leg Calf Raise", "Smith Machine Calf Raise"], "improvised": ["Stair edge with a backpack"]}'::jsonb,
   '[{"exercise_id": "EX025", "exercise_name": "Single-Leg Calf Raise (Loaded)"}, {"exercise_id": "EX026", "exercise_name": "Seated Calf Raise"}]'::jsonb,
   NULL,NULL,'EX025','Single-Leg Calf Raise (Loaded)',NULL,
   'Straight knee biases the gastrocnemius; full range — a deep stretch at the bottom and full plantarflexion at the top; the propulsive calf strength behind running and hiking push-off',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX259','Pedal Stance Deadlift','Strength','{Hinge,Single-Leg}'::text[],
   '{Hamstrings,Glutes}'::text[],'{"Erector Spinae","Hip Stabilisers"}'::text[],'{Dumbbell,Kettlebell}'::text[],
   'Lumbar — rounding under load; Hamstring — overstretch; Hip — instability in the kickstand stance',
   '{"Lower back",Hamstring,Hip}'::text[],'{}'::text[],
   '{"standard": ["Single-Leg RDL", "Romanian Deadlift", "B-stance RDL"], "improvised": ["Two water jugs in a kickstand stance"]}'::jsonb,
   '[{"exercise_id": "EX004", "exercise_name": "Single-Leg RDL (DB)"}, {"exercise_id": "EX003", "exercise_name": "Romanian Deadlift (Barbell)"}]'::jsonb,
   NULL,NULL,'EX004','Single-Leg RDL (DB)',NULL,
   'Kickstand stance — most of the weight on the front leg, the back toe for balance only; hinge with a neutral spine; a single-leg-biased deadlift that loads more easily than a true single-leg RDL',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX260','Lunge to Rotation','Strength','{Single-Leg,Rotation}'::text[],
   '{Quadriceps,Glutes,Obliques}'::text[],'{Core,"Hip Stabilisers"}'::text[],'{Dumbbell,Kettlebell,"Medicine ball","Weight plates"}'::text[],
   'Knee — front-knee tracking on the lunge; Lumbar — rotating from the spine instead of the hips; Shoulder — if reaching too far with the load',
   '{Knee,"Lower back",Shoulder}'::text[],'{}'::text[],
   '{"standard": ["Reverse Lunge", "Landmine Rotation", "Med-ball lunge and twist"], "improvised": ["Backpack held at the chest"]}'::jsonb,
   '[{"exercise_id": "EX022", "exercise_name": "Reverse Lunge (DB or BW)"}, {"exercise_id": "EX086", "exercise_name": "Landmine Rotation"}]'::jsonb,
   NULL,NULL,'EX022','Reverse Lunge (DB or BW)',NULL,
   'Lunge down, then rotate the torso over the front leg from the trunk — not the arms; combines single-leg strength with rotational control for paddling and twisting-under-load demands',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX261','Renegade Row','Strength','{Pull-H,Anti-Rotation}'::text[],
   '{"Latissimus Dorsi",Core}'::text[],'{Rhomboids,Biceps,Obliques}'::text[],'{Dumbbell,Kettlebell}'::text[],
   'Lumbar — hips rotating or sagging in the plank; Shoulder — instability on the supporting arm; Wrist — load on the planted hand',
   '{"Lower back",Shoulder,Wrist}'::text[],'{}'::text[],
   '{"standard": ["Single-Arm DB Row", "Plank with shoulder tap"], "improvised": ["Backpack rows from a plank"]}'::jsonb,
   '[{"exercise_id": "EX078", "exercise_name": "Single-Arm DB Row"}, {"exercise_id": "EX216", "exercise_name": "Plank (Front)"}]'::jsonb,
   NULL,NULL,'EX078','Single-Arm DB Row',NULL,
   'Row from a plank without letting the hips twist — anti-rotation core plus a unilateral back pull; widen the feet to reduce the rotational demand',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX262','Straight-Arm Lat Pulldown','Strength','{Pull-V}'::text[],
   '{"Latissimus Dorsi"}'::text[],'{Triceps,"Rear Delts",Core}'::text[],'{"Cable machine","Resistance band"}'::text[],
   'Shoulder — impingement if you shrug; Elbow — keep a soft fixed angle rather than locking hard',
   '{Shoulder,Elbow}'::text[],'{}'::text[],
   '{"standard": ["Lat Pulldown", "Band straight-arm pulldown", "Cable pullover"], "improvised": ["Band anchored overhead"]}'::jsonb,
   '[{"exercise_id": "EX080", "exercise_name": "Lat Pulldown (Wide Grip)"}, {"exercise_id": "EX006", "exercise_name": "Pull-Up (BW)"}]'::jsonb,
   NULL,NULL,'EX080','Lat Pulldown (Wide Grip)',NULL,
   'Arms nearly straight, drive the bar down to the thighs with the lats rather than the triceps; a straight-arm pullover pattern that isolates the lat without elbow flexion',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX263','L-Sit Pull-Up','Strength','{Pull-V,Anti-Extension}'::text[],
   '{"Latissimus Dorsi","Rectus Abdominis"}'::text[],'{Biceps,"Hip Flexors",Forearms}'::text[],'{"Pull-up bar"}'::text[],
   'Shoulder — high demand at the bottom; Elbow — biceps and tendon load; Hip Flexor — cramping holding the L position',
   '{Shoulder,Elbow,"Hip Flexor"}'::text[],'{}'::text[],
   '{"standard": ["Pull-Up", "L-Sit hold", "Tuck pull-up"], "improvised": ["Knees-tucked regression"]}'::jsonb,
   '[{"exercise_id": "EX006", "exercise_name": "Pull-Up (BW)"}, {"exercise_id": "EX226", "exercise_name": "L-Sit (Between Chairs / Parallettes)"}]'::jsonb,
   NULL,NULL,'EX006','Pull-Up (BW)',NULL,
   'Hold a strict L-sit — legs parallel to the floor — through the whole pull-up; extreme combined pulling strength and anti-extension core; regress by tucking the knees',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX264','Front Lever Progression','Strength','{Anti-Extension,Pull-V}'::text[],
   '{"Latissimus Dorsi","Rectus Abdominis"}'::text[],'{"Erector Spinae","Rear Delts",Core}'::text[],'{"Pull-up bar"}'::text[],
   'Shoulder — very high straight-arm load; Elbow — straight-arm tendon stress; Lumbar — if the hips sag out of the hollow position',
   '{Shoulder,Elbow,"Lower back"}'::text[],'{}'::text[],
   '{"standard": ["Tuck front lever", "Advanced-tuck front lever", "Scapular pull-up"], "improvised": ["Gymnastic rings"]}'::jsonb,
   '[{"exercise_id": "EX089", "exercise_name": "Hollow Body Hold"}, {"exercise_id": "EX109", "exercise_name": "Scapular Pull-Up"}]'::jsonb,
   NULL,NULL,'EX089','Hollow Body Hold',NULL,
   'Straight-arm horizontal hold under the bar; progress tuck to advanced-tuck to one-leg to full; brutal lat and anterior-core strength for climbing — build slowly to protect the elbows',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX265','Wide-Grip Seated Cable Row','Strength','{Pull-H}'::text[],
   '{"Latissimus Dorsi",Rhomboids,"Mid Traps"}'::text[],'{"Rear Delts",Biceps,Core}'::text[],'{"Cable machine"}'::text[],
   'Lumbar — rounding or heaving with the low back; Shoulder — if you shrug at the finish',
   '{"Lower back",Shoulder}'::text[],'{}'::text[],
   '{"standard": ["Seated Cable Row (narrow)", "Bent-Over Row", "Wide-grip band row"], "improvised": ["Band anchored at chest height, wide grip"]}'::jsonb,
   '[{"exercise_id": "EX079", "exercise_name": "Seated Cable Row (Narrow Grip)"}, {"exercise_id": "EX246", "exercise_name": "Barbell Row (Bent-Over)"}]'::jsonb,
   NULL,NULL,'EX079','Seated Cable Row (Narrow Grip)',NULL,
   'A wide grip biases the upper back and rear delts; pull to the upper abdomen, squeeze the shoulder blades, no torso heave',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX266','Close-Grip Lat Pulldown','Strength','{Pull-V}'::text[],
   '{"Latissimus Dorsi",Biceps}'::text[],'{Rhomboids,"Mid Traps",Forearms}'::text[],'{"Cable machine"}'::text[],
   'Shoulder — impingement if you lean far back; Elbow — biceps load with the narrow grip',
   '{Shoulder,Elbow}'::text[],'{}'::text[],
   '{"standard": ["Wide-Grip Lat Pulldown", "Close-grip pull-up", "Band close-grip pulldown"], "improvised": ["Band anchored overhead, neutral handle"]}'::jsonb,
   '[{"exercise_id": "EX080", "exercise_name": "Lat Pulldown (Wide Grip)"}, {"exercise_id": "EX006", "exercise_name": "Pull-Up (BW)"}]'::jsonb,
   NULL,NULL,'EX080','Lat Pulldown (Wide Grip)',NULL,
   'Neutral or narrow grip, drive the elbows down and back to the ribs; more lat stretch and biceps involvement than the wide grip',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX267','Towel Pull-Up','Strength','{Pull-V}'::text[],
   '{"Latissimus Dorsi",Forearms}'::text[],'{Biceps,"Forearm Flexors",Rhomboids}'::text[],'{"Pull-up bar"}'::text[],
   'Elbow — high grip and tendon load; Shoulder — bottom-position demand; Forearm — grip fatigue under bodyweight',
   '{Elbow,Shoulder,Forearm}'::text[],'{}'::text[],
   '{"standard": ["Pull-Up", "Dead Hang", "Towel dead hang"], "improvised": ["Two towels draped over a sturdy bar"]}'::jsonb,
   '[{"exercise_id": "EX006", "exercise_name": "Pull-Up (BW)"}, {"exercise_id": "EX005", "exercise_name": "Dead Hang"}]'::jsonb,
   NULL,NULL,'EX006','Pull-Up (BW)',NULL,
   'Pull up gripping towels draped over the bar — a savage grip and forearm demand on top of the pull; central for climbing-specific grip strength',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises e WHERE e.exercise_id = v.column1 AND e.superseded_at IS NULL);

INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note, priority, etl_version, etl_run_at
)
SELECT v.exercise_id, v.exercise_name, v.exercise_type, v.sport_name, v.note, v.priority, '0B-v1.6.13', now()
FROM ( VALUES
  ('EX255','Single-Leg Glute Bridge','Strength','General Conditioning','Single-leg posterior-chain strength that exposes and corrects side-to-side imbalance','High'),
  ('EX255','Single-Leg Glute Bridge','Strength','Trail Running','Unilateral glute strength for stride stability on uneven terrain','Medium'),
  ('EX255','Single-Leg Glute Bridge','Strength','Hiking','Single-leg hip strength supporting loaded stepping','Medium'),
  ('EX255','Single-Leg Glute Bridge','Strength','Rock Climbing','Hip drive and pelvic control for high steps','Medium'),
  ('EX256','Banded Pull-Through','Strength','General Conditioning','Low-load hinge pattern teaching hip drive with minimal spinal load','High'),
  ('EX256','Banded Pull-Through','Strength','Trail Running','Posterior-chain hinge strength for climbing power','Medium'),
  ('EX256','Banded Pull-Through','Strength','Hiking','Glute and hamstring drive for sustained climbing under load','Medium'),
  ('EX256','Banded Pull-Through','Strength','Rowing','Hip-hinge drive pattern supporting the rowing stroke','Medium'),
  ('EX257','Stability Ball Hamstring Curl','Strength','General Conditioning','Knee-flexion hamstring strength balancing the hip-dominant work','High'),
  ('EX257','Stability Ball Hamstring Curl','Strength','Trail Running','Hamstring strength for descents and injury resilience','High'),
  ('EX257','Stability Ball Hamstring Curl','Strength','Hiking','Hamstring durability for sustained descending','Medium'),
  ('EX258','Standing Calf Raise','Strength','General Conditioning','Gastrocnemius strength for propulsion and ankle resilience','High'),
  ('EX258','Standing Calf Raise','Strength','Trail Running','Propulsive calf strength for push-off and rocky terrain','High'),
  ('EX258','Standing Calf Raise','Strength','Hiking','Calf endurance and strength for climbing and load carriage','High'),
  ('EX258','Standing Calf Raise','Strength','Rock Climbing','Calf strength for edging and toe-standing on small holds','Medium'),
  ('EX259','Pedal Stance Deadlift','Strength','General Conditioning','Single-leg-biased hinge strength that loads heavier than a true single-leg RDL','High'),
  ('EX259','Pedal Stance Deadlift','Strength','Trail Running','Unilateral posterior-chain strength for stride power','Medium'),
  ('EX259','Pedal Stance Deadlift','Strength','Hiking','Single-leg hinge strength for loaded stepping and lifting','Medium'),
  ('EX259','Pedal Stance Deadlift','Strength','Obstacle Course Racing','Single-leg pulling and lifting strength for varied obstacles','Medium'),
  ('EX260','Lunge to Rotation','Strength','General Conditioning','Single-leg strength combined with rotational core control','High'),
  ('EX260','Lunge to Rotation','Strength','Kayaking','Rotational power linked to a stable single-leg base for the paddle stroke','High'),
  ('EX260','Lunge to Rotation','Strength','Packrafting','Trunk rotation with leg drive for paddling propulsion','Medium'),
  ('EX260','Lunge to Rotation','Strength','Trail Running','Single-leg strength and trunk control for technical terrain','Medium'),
  ('EX261','Renegade Row','Strength','General Conditioning','Anti-rotation core plus a unilateral horizontal pull in one movement','High'),
  ('EX261','Renegade Row','Strength','Rock Climbing','Core stability and pulling strength for body tension on the wall','Medium'),
  ('EX261','Renegade Row','Strength','Kayaking','Anti-rotation trunk control with a pulling demand for the stroke','Medium'),
  ('EX261','Renegade Row','Strength','Obstacle Course Racing','Combined core and pulling strength for crawls and drags','Medium'),
  ('EX262','Straight-Arm Lat Pulldown','Strength','General Conditioning','Lat isolation that builds the pull-down strength behind a strong pull','High'),
  ('EX262','Straight-Arm Lat Pulldown','Strength','Rock Climbing','Straight-arm lat strength for steep pulling and lock-off positions','High'),
  ('EX262','Straight-Arm Lat Pulldown','Strength','Kayaking','Lat-driven pulling strength for the catch phase of the stroke','Medium'),
  ('EX263','L-Sit Pull-Up','Strength','General Conditioning','High-end combined pulling strength and anti-extension core','Medium'),
  ('EX263','L-Sit Pull-Up','Strength','Rock Climbing','Pulling strength with extreme core tension for steep terrain','High'),
  ('EX263','L-Sit Pull-Up','Strength','Obstacle Course Racing','Strong pulling and core control for bars, walls, and rigs','Medium'),
  ('EX264','Front Lever Progression','Strength','Rock Climbing','Straight-arm lat and core strength for the hardest steep climbing','High'),
  ('EX264','Front Lever Progression','Strength','General Conditioning','Advanced anterior-core and pulling strength benchmark','Medium'),
  ('EX265','Wide-Grip Seated Cable Row','Strength','General Conditioning','Upper-back and rear-delt rowing strength for balanced posture','High'),
  ('EX265','Wide-Grip Seated Cable Row','Strength','Rowing','Horizontal pulling strength biased to the upper back for the drive','High'),
  ('EX265','Wide-Grip Seated Cable Row','Strength','Kayaking','Mid-back pulling strength supporting the forward stroke','High'),
  ('EX265','Wide-Grip Seated Cable Row','Strength','Canoeing','Sustained single-blade pulling base from the mid-back','Medium'),
  ('EX266','Close-Grip Lat Pulldown','Strength','General Conditioning','Lat and biceps pulling strength with a vertical-pull bias','High'),
  ('EX266','Close-Grip Lat Pulldown','Strength','Rock Climbing','Lat and arm pulling strength for vertical and overhanging moves','High'),
  ('EX266','Close-Grip Lat Pulldown','Strength','Kayaking','Vertical-pull strength supporting the catch and exit of the stroke','Medium'),
  ('EX267','Towel Pull-Up','Strength','Rock Climbing','Grip-intensive pulling — the most climbing-specific of the pull-ups','Critical'),
  ('EX267','Towel Pull-Up','Strength','General Conditioning','Combined pulling and grip strength under bodyweight','Medium'),
  ('EX267','Towel Pull-Up','Strength','Obstacle Course Racing','Grip and pulling strength for rigs, ropes, and monkey bars','Medium')
) AS v(exercise_id, exercise_name, exercise_type, sport_name, note, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_exercise_map m
   WHERE m.exercise_id = v.exercise_id AND m.sport_name = v.sport_name AND m.superseded_at IS NULL
);

DO $$
DECLARE v_ex INT; v_map INT; v_prog INT; v_regr INT; v_proxy INT; v_mapfk INT;
BEGIN
  SELECT count(*) INTO v_ex FROM layer0.exercises
   WHERE superseded_at IS NULL AND etl_version='0B-v1.6.13'
     AND exercise_id IN ('EX255','EX256','EX257','EX258','EX259','EX260','EX261','EX262','EX263','EX264','EX265','EX266','EX267');
  IF v_ex <> 13 THEN RAISE EXCEPTION '0013: expected 13 new exercises at 0B-v1.6.13, found %', v_ex; END IF;

  SELECT count(*) INTO v_map FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX255','EX256','EX257','EX258','EX259','EX260','EX261','EX262','EX263','EX264','EX265','EX266','EX267');
  IF v_map <> 45 THEN RAISE EXCEPTION '0013: expected 45 sport_exercise_map rows, found %', v_map; END IF;

  SELECT count(*) INTO v_prog FROM layer0.exercises e WHERE e.superseded_at IS NULL AND e.progression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=e.progression_exercise_id);
  SELECT count(*) INTO v_regr FROM layer0.exercises e WHERE e.superseded_at IS NULL AND e.regression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=e.regression_exercise_id);
  SELECT count(*) INTO v_proxy FROM layer0.exercises e, jsonb_array_elements(
           CASE WHEN jsonb_typeof(e.physical_proxies)='array' THEN e.physical_proxies ELSE '[]'::jsonb END) p
   WHERE e.superseded_at IS NULL AND p->>'exercise_id' IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=p->>'exercise_id');
  SELECT count(*) INTO v_mapfk FROM layer0.sport_exercise_map m WHERE m.superseded_at IS NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=m.exercise_id);
  IF v_prog + v_regr + v_proxy + v_mapfk > 0 THEN
    RAISE EXCEPTION '0013: dangling ref(s) (prog=%, regr=%, proxy=%, map=%)', v_prog, v_regr, v_proxy, v_mapfk;
  END IF;

  RAISE NOTICE '0013: OK — 13 lower-body/pull strength exercises (EX255-EX267) + 45 sport_exercise_map rows at 0B-v1.6.13';
END $$;

COMMIT;

-- End of 0013_add_strength_exercises_lowerpull.sql
