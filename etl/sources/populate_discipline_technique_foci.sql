-- populate_discipline_technique_foci.sql
-- Inserts 35 technique-focus rows derived from the 52 exercises being dropped
-- in Batch B (technique-focus migration).
--
-- NOTE on count: Prior planning estimate was 33 foci. Final count is 35 because
-- two canoe-specific exercises (EX162 Tandem Canoe Coordination, EX163 Canoe
-- Portage Yoke Carry) were missed in the original collapse table — they don't
-- fit cleanly into any other paddle group. Each becomes its own focus.
--
-- Collapse rules applied:
--   - Snowshoe gait (4 exercises → 1 focus, multi-cue)
--   - Climbing movement (4 exercises → 1 focus)
--   - Climbing rope/device handling (3 exercises → 1 focus)
--   - Flatwater paddle stroke (3 exercises → 1 focus)
--   - Moving-water paddle (2 exercises → 1 focus)
--   - Multi-person raft coordination (2 exercises → 1 focus)
--   - Open-water swim technique (2 exercises → 1 focus)
--   - Ski uphill & transition (2 exercises → 1 focus)
--   - Ski descent & edge control (2 exercises → 1 focus)
--   - Technical descent on loose/uneven terrain (scree + fell) (2 exercises → 1 focus)
--   - All other exercises map 1:1 to foci.
--
-- Description text condenses cues from source exercises. Layer 4 surfaces the
-- description as the in-session coaching cue.
--
-- Open gap noted in audit_log:
--   TF-033 Rowing drive sequence — discipline_ids is empty because the
--   discipline framework (Sports_Framework_v10) has no Rowing discipline.
--   The exercise mapped to sport "Rowing" only. Selection logic will not fire
--   on any session until a Rowing discipline is added or this focus is
--   re-tagged. Flagged for framework v11.
--
-- etl_version: '0B-v19.B'
-- Safe to re-run: a DELETE-by-version prefix rebuilds this version's rows from
-- this file on every run, so a row removed from the file can't linger as an
-- active orphan (D-74) — matching etl/layer0/db.py:insert_versioned. The
-- ON CONFLICT (focus_id, etl_version) DO NOTHING guard is retained as
-- belt-and-suspenders.

BEGIN;

-- D-74: clear this version's rows first so re-running rebuilds them from this
-- file (a row removed from the file can't survive as an active orphan).
DELETE FROM layer0.discipline_technique_foci WHERE etl_version = '0B-v19.B';

INSERT INTO layer0.discipline_technique_foci (
  focus_id, focus_name, description,
  discipline_ids, applicable_session_types, applicable_terrain_ids,
  required_equipment, required_gear_toggle,
  athlete_level, priority, when_to_emphasize, source_exercise_ids,
  audit_log,
  etl_version, etl_run_at
) VALUES

-- ── Navigation (1 focus) ───────────────────────────────────────────────────

( 'TF-001', 'Navigation under movement',
  'Run-navigate or walk-navigate simultaneously: fold map to the current section, thumb on position; when on bearing, pick an attack point ~200m ahead and travel to it without looking down repeatedly. Start slow to build the dual-task habit; speed comes after error rate drops.',
  ARRAY['D-015','D-001'], NULL, NULL,
  NULL, NULL,
  'any', 'Critical',
  'Early in plan and reinforced before navigation-critical sessions and races.',
  ARRAY['EX057','EX058'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── MTB skill (2 foci) ─────────────────────────────────────────────────────

( 'TF-002', 'MTB cornering technique',
  'Outside pedal down and weighted; lean the bike, not the body; look through the corner to the exit. Start slow on known corners until the line is automatic before adding speed.',
  ARRAY['D-008'], NULL,
  ARRAY['TRN-002','TRN-003','TRN-015'],
  ARRAY['Mountain bike'], NULL,
  'any', 'Standard',
  'Early Base and during MTB skill blocks; refresh in race week if the course has technical corners.',
  ARRAY['EX071'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-003', 'MTB pump track / trail-feature technique',
  'Generate speed from terrain without pedaling, using body-weight shift to pump rolls and absorb features. Builds rhythm for efficient riding on natural trail.',
  ARRAY['D-008'], NULL,
  ARRAY['TRN-015','TRN-003'],
  ARRAY['Mountain bike'], NULL,
  'any', 'Standard',
  'Skills blocks; useful any time pump track or feature-rich trail is accessible.',
  ARRAY['EX072'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Climbing (2 foci) ──────────────────────────────────────────────────────

( 'TF-004', 'Climbing movement (footwork, body position, flagging, mantling, rest)',
  'Footwork and body position are the highest-return skills — climbing is mostly legs, not arms. Look before placing each foot. Flag inside or outside leg to counter barn-door swing. Mantle by pushing down on the ledge and locking off to stand. Find the most straight-arm rest position possible, shift weight onto feet, and shake from the shoulder for 30–60s before crux moves. (Mantling cue: monitor wrist extension flag — relevant to Andy''s active wrist injury.)',
  ARRAY['D-012'], NULL,
  ARRAY['TRN-013','TRN-014'],
  NULL, NULL,
  'any', 'Critical',
  'Throughout climbing prep blocks; foundational skill cluster.',
  ARRAY['EX113','EX114','EX116','EX138'],
  'Wrist-extension flag inherited from EX116 (mantling). Layer 4 should suppress mantling cue when athlete has active wrist-extension contraindication.',
  '0B-v19.B', NOW() ),

( 'TF-005', 'Climbing rope-and-device handling (belay, rappel, descent)',
  'Practice PBUS belay (pull, brake, under, slide) to automaticity — belaying under fatigue is a safety issue. Rappel: practice slow controlled lowering in brake mode before committing; GriGri rappel mode differs from belay mode — practice explicitly; brake hand stays below the device at all times. Wall-walk descent: feet flat on wall (not tiptoes), hips square, slight lean back against harness tension; the instinct to lean in must be overridden.',
  ARRAY['D-012','D-013','D-014'], NULL,
  ARRAY['TRN-013','TRN-014'],
  ARRAY['Climbing gear'], 'Climbing — roped',
  'any', 'Critical',
  'Before any roped climbing or rappel session; refresh whenever there''s a layoff > 4 weeks.',
  ARRAY['EX112','EX130','EX131'],
  'Safety-critical. Gated by Climbing — roped toggle (which also satisfies Rappelling / abseiling per Batch A).',
  '0B-v19.B', NOW() ),

-- ── Trekking poles (2 foci) ────────────────────────────────────────────────

( 'TF-006', 'Trekking pole uphill push',
  'Drive poles behind the hip for propulsion; don''t reach forward. Doubles per-pole output. Trains the active plant that most hikers skip.',
  ARRAY['D-001','D-003','D-024'], NULL,
  ARRAY['TRN-004','TRN-005'],
  ARRAY['Trekking Poles'], NULL,
  'any', 'Standard',
  'Base and Build phases on hilly terrain; reinforces during sustained uphill blocks.',
  ARRAY['EX118'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-007', 'Trekking pole descent braking',
  'On descents, plant poles ahead to transfer load from knees to arms; shorten poles for descent. Measurably reduces knee fatigue under pack on long descents.',
  ARRAY['D-001','D-003','D-024'], NULL,
  ARRAY['TRN-004','TRN-005'],
  ARRAY['Trekking Poles'], NULL,
  'any', 'Standard',
  'Build and Peak phases on courses with significant descent volume.',
  ARRAY['EX121'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Pack drills (3 foci) ───────────────────────────────────────────────────

( 'TF-008', 'Hip hinge under pack',
  'Pick up and set down the pack with a proper hip hinge — bend at the hips, not the spine. Lumbar injury risk under fatigue is often at pack pickup, not during the carry.',
  ARRAY['D-003'], NULL, NULL,
  ARRAY['Backpack'], NULL,
  'any', 'Standard',
  'Reinforce in Base when pack carry first introduces; refresh under fatigue states.',
  ARRAY['EX122'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-009', 'Pack fit optimization',
  '80% of load on the hip belt; 20% on the shoulders; sternum strap for stability, not load. Adjust every 30–60 min in race conditions as the body and pack settle.',
  ARRAY['D-001','D-003','D-015','D-017','D-018','D-021'], NULL, NULL,
  ARRAY['Backpack'], NULL,
  'any', 'Critical',
  'Race week and any session > 3h with pack; revisit when pack contents change.',
  ARRAY['EX123'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-010', 'Hike-a-bike carry',
  'Carry the bike on the shoulder (top tube) or push-drag depending on terrain angle. Practice the clip-out and dismount sequence to automatic — in AR, hike-a-bike sections often decide races; the athlete who transitions cleanly gains minutes.',
  ARRAY['D-008'], NULL, NULL,
  ARRAY['Mountain bike','Backpack'], NULL,
  'any', 'Standard',
  'Build and Peak phases when course profile includes hike-a-bike sections.',
  ARRAY['EX144'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Mountaineering (2 foci) ────────────────────────────────────────────────

( 'TF-011', 'Crampon walking technique',
  'French technique (flat-foot) on moderate angles — all points contact simultaneously. Front-pointing on steep ice — front two points only; calf demand increases sharply. Kick each step deliberately on hard surfaces.',
  ARRAY['D-018','D-021'], NULL,
  ARRAY['TRN-005','TRN-012'],
  ARRAY['Mountaineering kit'], NULL,
  'intermediate', 'Critical',
  'Before any glacier or crampon-travel session; refresh whenever there''s a layoff > season.',
  ARRAY['EX148'],
  'Skill prerequisite for D-018 sessions.',
  '0B-v19.B', NOW() ),

( 'TF-012', 'Ice axe self-arrest',
  'Safety-critical. Practice from multiple starting positions (head-up face-down, head-down face-up, face-up). Arrest position: pick into the slope, adze near the cheek, weight on toes and pick. Build to automaticity.',
  ARRAY['D-018'], NULL,
  ARRAY['TRN-012'],
  ARRAY['Mountaineering kit'], NULL,
  'intermediate', 'Critical',
  'Before any glacier or steep-snow session; mandatory refresh annually.',
  ARRAY['EX149'],
  'Safety-critical skill.',
  '0B-v19.B', NOW() ),

-- ── Snowshoe (1 focus, multi-cue) ──────────────────────────────────────────

( 'TF-013', 'Snowshoe gait technique (multi-cue)',
  'Slightly wider stance than normal walking; lift each snowshoe clear of the other rather than dragging; poles provide rhythm and reduce leg load 20–30% on ascent. Plunge step on descent: heel-first strike, drive heel into slope, poles planted slightly ahead. Sidehill: edge the uphill frame into the slope; kickturn (180° reversal) requires removing the uphill snowshoe — practice before steep terrain. Post-hole recovery: high knee lift to clear hole, minimize knee twisting on extract; pace down immediately — post-holing is 4–6× the energy cost of hard-pack walking.',
  ARRAY['D-017'], NULL,
  ARRAY['TRN-012'],
  ARRAY['Snowshoes'], NULL,
  'any', 'Standard',
  'Early in any snowshoe block; gait adapts within 30–60 min of first session in a season.',
  ARRAY['EX152','EX153','EX154','EX155'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Paddle stroke / handling (4 foci) ──────────────────────────────────────

( 'TF-014', 'Flatwater paddle stroke technique (forward, sweep, draw/pry)',
  'Forward stroke: rotate torso to plant the paddle near the feet; unwind torso to drive — not arms; exit at the hip. Highest-return technical improvement in paddling. Sweep stroke: full arc bow-to-stern (kayak) or bow-to-mid-ship (canoe); torso rotation drives arc, not arm reach. Draw: plant blade parallel to boat, pull water under hull toward the paddle. Pry: lever blade off gunwale to push boat away. Both draw and pry are lateral boat control — essential for docking, eddying, and avoiding obstacles.',
  ARRAY['D-009','D-010','D-011'], NULL,
  ARRAY['TRN-008','TRN-009'],
  NULL, NULL,
  'any', 'Critical',
  'Reinforce throughout Base in any flatwater session; foundational for all paddle disciplines.',
  ARRAY['EX091','EX156','EX157'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-015', 'Moving-water paddle technique (brace, ferry, eddy turn)',
  'Brace: keep elbow below wrist in high brace; low brace preferred when possible — most paddling shoulder injuries come from poor brace mechanics. Ferry: cross current at upstream angle to move laterally without losing ground. Eddy turn: hit eddy line at speed, lean and look into eddy, let current pivot the bow — upriver lean on the eddy line is a flip risk; downriver lean is correct.',
  ARRAY['D-009','D-010','D-011','D-019'], NULL,
  ARRAY['TRN-011','TRN-017'],
  NULL, NULL,
  'intermediate', 'Critical',
  'Before any whitewater session; gates progression to moving-water work.',
  ARRAY['EX092','EX166'],
  'Safety-critical for moving water.',
  '0B-v19.B', NOW() ),

( 'TF-016', 'Eskimo roll',
  'Hip snap drives the roll, not the arms; C-to-C or sweep roll. Not required for packraft but valuable for rescue confidence in any decked craft.',
  ARRAY['D-010'], NULL,
  ARRAY['TRN-008','TRN-009'],
  ARRAY['Kayak'], NULL,
  'intermediate', 'Standard',
  'Pool sessions; refresh annually; required prerequisite before progressing to whitewater kayaking.',
  ARRAY['EX093'],
  'Self-rescue skill.',
  '0B-v19.B', NOW() ),

( 'TF-017', 'Packraft inflation / deflation drill',
  'Timed practice for transition efficiency: oral inflation vs pump bag; deflation, fold, and pack. Time is lost at packraft transitions — train this until it''s automatic.',
  ARRAY['D-009'], NULL, NULL,
  ARRAY['Packraft'], NULL,
  'any', 'Standard',
  'Early in plan and again in race week; reinforces transition efficiency.',
  ARRAY['EX094'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Whitewater specific (3 foci) ───────────────────────────────────────────

( 'TF-018', 'Whitewater line reading',
  'Scout from high ground if possible. Identify entry point, line through rapid, and exit eddy. Read water-surface features: V-shapes point downstream-safe lines; pillows indicate submerged rocks; pour-overs show as horizon lines.',
  ARRAY['D-009','D-010','D-019'], NULL,
  ARRAY['TRN-011'],
  NULL, NULL,
  'intermediate', 'Critical',
  'Before any whitewater session; reinforce when scouting at race recon.',
  ARRAY['EX158'],
  'Safety-critical cognitive skill.',
  '0B-v19.B', NOW() ),

( 'TF-019', 'Multi-person raft coordination (high-side + paddle sync)',
  'Safety-critical. High-side: move body weight immediately to the downstream tube when the raft is wrapping — a delayed response lets the current pin the raft. Paddle sync: guide calls stroke rate; all blades enter simultaneously; power phase is short and vertical, not a long sweep. Synchronisation at 70% effort outperforms individual 100% effort at different timing.',
  ARRAY['D-019'], NULL,
  ARRAY['TRN-011'],
  NULL, NULL,
  'intermediate', 'Critical',
  'Pre-trip practice on flat water before any whitewater raft session.',
  ARRAY['EX164','EX165'],
  'Safety-critical for team-raft contexts.',
  '0B-v19.B', NOW() ),

( 'TF-020', 'Surf zone entry / exit (sea kayak)',
  'Time entry to paddle out between sets; punch through waves bow-first with forward momentum. On exit: surf the wave straight, exit on the beach before the wave recedes. In AR ocean legs, surf-zone entry and exit are decisive — most capsizes happen here.',
  ARRAY['D-010'], NULL,
  ARRAY['TRN-010'],
  ARRAY['Kayak'], NULL,
  'intermediate', 'Standard',
  'Race week if the course has ocean legs; reinforce in any sea-kayak block.',
  ARRAY['EX167'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Canoe-specific (2 foci) ────────────────────────────────────────────────

( 'TF-021', 'Canoe tandem coordination',
  'Bow sets the pace; stern matches and steers. Call stroke changes before executing; practice side switches on command (hut-hut call). Synchronised power is 15–20% more efficient than asynchronous paddling.',
  ARRAY['D-011'], NULL, NULL,
  ARRAY['Canoe'], NULL,
  'any', 'Standard',
  'In any tandem-canoe block; race week for events with mandatory tandem segments.',
  ARRAY['EX162'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-022', 'Canoe portage yoke carry',
  'Centre the yoke precisely on the cervical vertebrae — off-centre causes neck muscle strain. Solo tipping technique requires a gunwale flick from a low position. Vision is obstructed under the canoe — short steps, scan ground before moving.',
  ARRAY['D-011'], NULL, NULL,
  ARRAY['Canoe'], NULL,
  'any', 'Standard',
  'Pre-race for events with mandatory portage; reinforce in canoeing Base if portages are part of the discipline profile.',
  ARRAY['EX163'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Swim (2 foci) ──────────────────────────────────────────────────────────

( 'TF-023', 'Open-water swim technique (sighting + bilateral breathing)',
  'Sighting: lift eyes just above the water surface (crocodile eyes, not chin) every 6–10 strokes; sight on inhale side; pick a large target, not a buoy. Bilateral breathing: every 3 strokes alternating sides; builds symmetrical stroke and allows sighting from either side. Mandatory if current or wind pushes from one direction.',
  ARRAY['D-004','D-016','D-020'], NULL,
  ARRAY['TRN-008','TRN-009','TRN-010'],
  NULL, NULL,
  'any', 'Critical',
  'Throughout swim training blocks; reinforce before open-water sessions and races.',
  ARRAY['EX140','EX142'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-024', 'SwimRun water entry / exit technique',
  'Entry: run to water''s edge at pace, assess depth quickly, transition to dolphin dive or high-step wade depending on depth — never dive without knowing the bottom; SwimRun venues often have rocky shallow entries. Exit: time exit to incoming wave, plant feet, drive forward into the run, transition gear (if any) on the move.',
  ARRAY['D-020'], NULL,
  ARRAY['TRN-010','TRN-009'],
  NULL, NULL,
  'any', 'Critical',
  'Race week; reinforce in any SwimRun-specific block.',
  ARRAY['EX199'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Ski (2 foci) ───────────────────────────────────────────────────────────

( 'TF-025', 'Ski uphill technique & race transition (kick-turn + skin-mode change)',
  'Kick-turn: plant uphill pole; lift and swing uphill ski 180° first — place it pointed opposite direction; transfer weight; swing downhill ski to match. Common error is rushing and catching a ski tip — causes falls. Race transition sequence: skin removal (fold glue-to-glue to preserve adhesive), ski crampon attach or remove, boot buckle mode change (walk to ski or reverse), pole basket swap if required. Time the full sequence repeatedly.',
  ARRAY['D-021','D-023'], NULL,
  ARRAY['TRN-012'],
  ARRAY['Touring ski kit'], NULL,
  'intermediate', 'Critical',
  'Pre-season and through Base for SkiMo; race-week refresh.',
  ARRAY['EX169','EX170'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-026', 'Ski descent technique & lateral edge control',
  'Touring skis are lighter and less damp than resort skis — they react faster to terrain changes. Lean forward into the boot cuff; weight on downhill ski; short-radius turns on steep terrain. Edge control: traverse on uphill edges; practice lateral weight shift edge-to-edge without skidding. SkiMo edging demand is more about secure footing on traverses than about carved turns.',
  ARRAY['D-022','D-023'], NULL,
  ARRAY['TRN-012'],
  ARRAY['Touring ski kit'], NULL,
  'intermediate', 'Critical',
  'Throughout descent-focused training; race-week refresh on representative terrain.',
  ARRAY['EX171','EX172'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Transition / multi-modal (3 foci) ──────────────────────────────────────

( 'TF-027', 'Brick-run pacing adaptation (bike-to-run)',
  'Ride 20–60 min then immediately run 10–20 min without rest. The first 3–8 min of the run feel like running with concrete legs — this is normal and trainable. Shorten stride initially, increase cadence; let HR and biomechanics catch up before pushing pace.',
  ARRAY['D-001','D-002','D-006'], NULL, NULL,
  NULL, NULL,
  'any', 'Standard',
  'Build and Peak phases for any bike-to-run race format; race-week dress rehearsal.',
  ARRAY['EX175'],
  'Pacing adaptation, not just transition gear-change. Distinct from TF-028 (T1/T2).',
  '0B-v19.B', NOW() ),

( 'TF-028', 'Triathlon transition practice (T1 & T2)',
  'T1 sequence: exit water, wetsuit strip (pull cord at neck, peel to waist, step out), run to bike, helmet on and buckled before touching bike, shoes on (or run in socks to mount), mount line. T2 sequence: dismount line, rack bike, helmet off, run shoes on, exit. Time the full sequence repeatedly until the order is automatic.',
  ARRAY['D-002','D-006','D-016'], NULL, NULL,
  NULL, NULL,
  'any', 'Standard',
  'Race week; reinforce when transition layout changes.',
  ARRAY['EX176'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-029', 'Laser-Run transition (run-to-shoot)',
  'Run 800m–1km at race effort (RPE 8–9), then immediately attempt 5 shots on target. The format requires managing HR recovery at the firing line — not resting until precise, but shooting while elevated. Practice the breath-and-trigger rhythm under load.',
  ARRAY['D-001','D-026'], NULL, NULL,
  NULL, NULL,
  'intermediate', 'Critical',
  'Throughout Modern Pentathlon prep; race-week refresh.',
  ARRAY['EX194'],
  NULL,
  '0B-v19.B', NOW() ),

-- ── Other (6 foci) ─────────────────────────────────────────────────────────

( 'TF-030', 'Running with poles (trail / ultra)',
  'Distinct from hiking pole technique (TF-006/007) which is at walking pace — running with poles requires faster plant rhythm, shorter swing arc, and higher cadence coordination with stride. Plant beside foot, not ahead.',
  ARRAY['D-001','D-024'], NULL,
  ARRAY['TRN-002','TRN-003','TRN-004','TRN-005'],
  ARRAY['Trekking Poles'], NULL,
  'intermediate', 'Standard',
  'Build and Peak phases for ultra and mountain-running events that allow poles.',
  ARRAY['EX183'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-031', 'Road cycling descending technique',
  'Distinct from MTB descending — road descending is higher speed, no suspension, smooth surface. Tuck low with elbows bent, weight back behind saddle, look well ahead. Brake before corners, not in them.',
  ARRAY['D-006','D-007'], NULL,
  ARRAY['TRN-001','TRN-004','TRN-005'],
  ARRAY['Road bike'], NULL,
  'any', 'Standard',
  'Throughout cycling Base and Build; race-week refresh on representative descents.',
  ARRAY['EX184'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-032', 'Obstacle vault & wall traversal',
  'Speed vault (lazy vault): lead hand on obstacle, swing both legs to the same side. Safety vault: both hands, both legs together over. Wall: jump to grab the top, press body up using triceps and hip-flexor pull-up, swing legs over.',
  ARRAY['D-027'], NULL, NULL,
  ARRAY['Plyo box'], NULL,
  'intermediate', 'Standard',
  'OCR / Modern Pentathlon prep blocks.',
  ARRAY['EX196'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-033', 'Rowing drive sequence',
  'The defining rowing technical skill: legs drive first (≈80% extended) before back swings, arms pull last. This sequence is unintuitive — reverting to arms-first under fatigue is the most common rowing breakdown. Reinforce the order on every stroke.',
  ARRAY[]::TEXT[], NULL, NULL,
  NULL, NULL,
  'any', 'Standard',
  'Throughout rowing training when scheduled.',
  ARRAY['EX200'],
  'GAP: Sports_Framework_v10 has no Rowing discipline. Source EX200 mapped only to sport "Rowing". Layer 4 selection will not fire on any session until a Rowing discipline is added or this focus is re-tagged. Flagged for framework v11.',
  '0B-v19.B', NOW() ),

( 'TF-034', 'Scrambling technique (moving over rocky terrain)',
  'Scrambling bridges trail running and rock climbing: moving through steep terrain using hands for balance and upward progress, not ascending a single route. Distinct from hiking by the hand contact; distinct from climbing by the locomotive intent. Three points of contact at all times in committing terrain. Plan two moves ahead — find the next hand and foot before moving the current one.',
  ARRAY['D-001','D-003','D-018','D-024'], NULL,
  ARRAY['TRN-005','TRN-007'],
  NULL, NULL,
  'intermediate', 'Standard',
  'Build and Peak phases for any course with scramble sections; race-week refresh.',
  ARRAY['EX212'],
  NULL,
  '0B-v19.B', NOW() ),

( 'TF-035', 'Technical descent on loose / uneven terrain (scree + fell)',
  'Scree running requires committing to movement the brain resists — the surface moves under you, and that''s the technique, not the enemy; lean slightly back, weight on heels, let feet sink and slide with each stride. Fell descent (steep grass, bog, heather) is categorically different — heel-planting rather than forefoot striking; the heel digs in for grip; lean forward slightly more than instinct says. Both share: short controlled strides, wide arms for balance, scan terrain 3–5 strides ahead.',
  ARRAY['D-001','D-024'], NULL,
  ARRAY['TRN-005','TRN-006','TRN-007'],
  NULL, NULL,
  'intermediate', 'Standard',
  'Build and Peak phases for mountain / fell racing; race-week refresh on representative terrain.',
  ARRAY['EX213','EX214'],
  'Collapsed from EX213 (scree) and EX214 (fell). Multi-cue handles the surface-specific differences.',
  '0B-v19.B', NOW() )

ON CONFLICT (focus_id, etl_version) DO NOTHING;

-- ── Verify ─────────────────────────────────────────────────────────────────

DO $$
DECLARE
  total_count INT;
  null_disc   INT;
BEGIN
  SELECT COUNT(*) INTO total_count
  FROM layer0.discipline_technique_foci
  WHERE etl_version = '0B-v19.B' AND superseded_at IS NULL;

  SELECT COUNT(*) INTO null_disc
  FROM layer0.discipline_technique_foci
  WHERE etl_version = '0B-v19.B' AND superseded_at IS NULL
    AND (cardinality(discipline_ids) = 0)
    AND focus_id <> 'TF-033';  -- TF-033 (Rowing) is the documented gap

  IF total_count <> 35 THEN
    RAISE EXCEPTION 'populate_discipline_technique_foci: expected 35 active rows, found %', total_count;
  END IF;

  IF null_disc > 0 THEN
    RAISE EXCEPTION 'populate_discipline_technique_foci: % rows have empty discipline_ids (only TF-033 should)', null_disc;
  END IF;

  RAISE NOTICE 'populate_discipline_technique_foci: OK — 35 active rows, 1 documented gap (TF-033 Rowing)';
END $$;

COMMIT;
