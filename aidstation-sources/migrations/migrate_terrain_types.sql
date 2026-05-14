-- migrate_terrain_types.sql
-- Extends layer0.terrain_types with structured attributes and replaces
-- the original 15 minimal-name rows with 16 properly structured rows.
--
-- Why supersede-and-reinsert rather than UPDATE:
--   The original rows had no terrain_id and some categories need splitting
--   (e.g., "Trail" → Groomed Trail + Technical Trail). Versioning the change
--   cleanly via superseded_at is the right pattern for Layer 0.
--
-- etl_version: '0C-v2.0-r2'  (0C = Vocabulary Audit source; r2 = second
--   revision of the v2 terrain vocab, adding IDs + structured attributes)
--
-- Safe to re-run: ADD COLUMN IF NOT EXISTS guards schema changes.
--   Supersede block targets terrain_id IS NULL (original rows only).
--   INSERT is blocked by UNIQUE (canonical_name, etl_version) on conflict.

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.terrain_types
  ADD COLUMN IF NOT EXISTS terrain_id          TEXT,
  ADD COLUMN IF NOT EXISTS category            TEXT,
  ADD COLUMN IF NOT EXISTS requires_elevation  BOOLEAN,
  ADD COLUMN IF NOT EXISTS technical_surface   BOOLEAN,
  ADD COLUMN IF NOT EXISTS environment         TEXT,
  ADD COLUMN IF NOT EXISTS simulatable         TEXT,
  ADD COLUMN IF NOT EXISTS simulation_note     TEXT;

-- Add unique constraint on terrain_id (post-migration, all rows will have one)
-- Wrapped in DO block so it's idempotent
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'terrain_types_terrain_id_etl_version_key'
  ) THEN
    ALTER TABLE layer0.terrain_types
      ADD CONSTRAINT terrain_types_terrain_id_etl_version_key
      UNIQUE (terrain_id, etl_version);
  END IF;
END $$;

-- ── 2. Supersede original rows (terrain_id IS NULL = pre-r2 rows) ──────────

UPDATE layer0.terrain_types
SET superseded_at = NOW()
WHERE terrain_id IS NULL
  AND superseded_at IS NULL;

-- ── 3. Insert 16 structured rows ───────────────────────────────────────────

INSERT INTO layer0.terrain_types (
  terrain_id, canonical_name, category,
  requires_elevation, technical_surface, environment,
  simulatable, simulation_note, notes,
  etl_version, etl_run_at
) VALUES

-- Foot terrains
('TRN-001', 'Road / Paved',         'Foot',     FALSE, FALSE, 'Outdoor',
  'full',
  'Treadmill is full-fidelity substitute for road running.',
  'Standard road and paved path running surface.',
  '0C-v2.0-r2', NOW()),

('TRN-002', 'Groomed Trail',        'Foot',     FALSE, FALSE, 'Outdoor',
  'partial',
  'Treadmill covers aerobic load; loses surface variation and proprioceptive demand.',
  'Compacted, maintained singletrack or dirt trail. Low surface variability.',
  '0C-v2.0-r2', NOW()),

('TRN-003', 'Technical Trail',      'Foot',     FALSE, TRUE,  'Outdoor',
  'partial',
  'Agility and balance drills are partial proxy; proprioceptive adaptation to variable surface requires real terrain.',
  'Rocky, root-crossed, or otherwise unpredictable trail surface. High ankle demand.',
  '0C-v2.0-r2', NOW()),

('TRN-004', 'Hill / Rolling',       'Foot',     TRUE,  FALSE, 'Outdoor',
  'partial',
  'Max-incline treadmill simulates uphill aerobic load; descent EIMD adaptation requires actual downhill terrain.',
  'Moderate sustained elevation. Rolling hills with recoverable grades.',
  '0C-v2.0-r2', NOW()),

('TRN-005', 'Mountain / Alpine',    'Foot',     TRUE,  TRUE,  'Outdoor',
  'partial',
  'Stair climber and weighted vest simulate vertical load; descent skill and alpine balance cannot be replicated indoors.',
  'High sustained elevation with exposed, technical, or multi-hour vertical gain. Includes above-treeline terrain.',
  '0C-v2.0-r2', NOW()),

('TRN-006', 'Fell / Moorland',      'Foot',     TRUE,  TRUE,  'Outdoor',
  'none',
  'No meaningful indoor substitute. Navigation on unmarked terrain and variable footing on heather/bog cannot be simulated.',
  'Open, pathless, navigationally demanding terrain. Steep grass, heather, bog, moorland. Fell running specific.',
  '0C-v2.0-r2', NOW()),

('TRN-007', 'Technical Rock',       'Foot',     FALSE, TRUE,  'Outdoor',
  'none',
  'Balance drills develop general stability but rock-specific proprioceptive adaptation requires actual boulder/scree terrain.',
  'Loose boulder fields, scree slopes, rock gardens. Distinct from rock climbing — locomotive movement over unstable rock.',
  '0C-v2.0-r2', NOW()),

-- Water terrains
('TRN-008', 'Pool',                 'Water',    FALSE, FALSE, 'Indoor',
  'full',
  'Full fidelity for stroke mechanics and aerobic base. Standard pool environment.',
  'Controlled lane swimming. Flip turns, lane lines, consistent conditions.',
  '0C-v2.0-r2', NOW()),

('TRN-009', 'Flat Water',           'Water',    FALSE, FALSE, 'Outdoor',
  'partial',
  'Pool covers aerobic base and stroke mechanics; loses mild current navigation, open-water pacing, and environmental variables.',
  'Calm lake, reservoir, or slow river. Low technical demand. Standard kayak/packraft training environment.',
  '0C-v2.0-r2', NOW()),

('TRN-010', 'Open Water / Ocean',   'Water',    FALSE, FALSE, 'Outdoor',
  'partial',
  'Pool maintains aerobic base; loses sighting, wave/current navigation, cold exposure, and mass-start dynamics.',
  'Ocean, large lake, or tidal water with meaningful chop, current, or swell. OW swimming and ocean paddling territory.',
  '0C-v2.0-r2', NOW()),

('TRN-011', 'Whitewater',           'Water',    FALSE, TRUE,  'Outdoor',
  'none',
  'Flat water maintains paddling fitness only. Whitewater skill (eddy catches, reading water, bracing, rolling) requires moving water.',
  'Class II+ moving water with rapids, eddies, hydraulics. Technical paddling terrain.',
  '0C-v2.0-r2', NOW()),

-- Snow terrain
('TRN-012', 'Snow / Winter Alpine', 'Snow',     TRUE,  TRUE,  'Outdoor',
  'partial',
  'Stair climber with poles approximates uphill skinning aerobic load. Descent skill on snow cannot be simulated off-snow.',
  'Snow-covered mountain terrain requiring skis, snowshoes, or crampons. Includes groomed tracks, off-piste, and alpine descent.',
  '0C-v2.0-r2', NOW()),

-- Climbing terrains
('TRN-013', 'Rock Wall (Outdoor)',  'Climbing', FALSE, TRUE,  'Outdoor',
  'partial',
  'Climbing gym transfers movement patterns and strength well; loses natural rock reading, exposure confidence, and protection placement.',
  'Natural rock climbing terrain. Sport routes, trad, or scrambling on real rock.',
  '0C-v2.0-r2', NOW()),

('TRN-014', 'Climbing Gym',         'Climbing', FALSE, TRUE,  'Indoor',
  'full',
  'Full fidelity for movement pattern development, finger strength, and route reading on plastic holds.',
  'Indoor climbing wall. Bouldering or roped. Standard AR climbing prep environment.',
  '0C-v2.0-r2', NOW()),

-- MTB terrain
('TRN-015', 'Pump Track / Skills Course', 'MTB', FALSE, TRUE, 'Outdoor',
  'none',
  'No indoor substitute for pump track or MTB skills course. Balance and cornering drills are poor proxies.',
  'MTB-specific terrain. Berms, jumps, pump sections, technical flow. Skills training focused.',
  '0C-v2.0-r2', NOW()),

-- Gym / indoor
('TRN-016', 'Indoor / Gym',         'Gym',      FALSE, FALSE, 'Indoor',
  'full',
  'By definition this is the simulation environment. Full fidelity for any exercise it hosts.',
  'Treadmill, stair climber, erg, gym equipment. The indoor training environment itself.',
  '0C-v2.0-r2', NOW())

ON CONFLICT (canonical_name, etl_version) DO NOTHING;

-- ── 4. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  new_count   INT;
  null_id     INT;
BEGIN
  SELECT COUNT(*) INTO new_count
  FROM layer0.terrain_types
  WHERE etl_version = '0C-v2.0-r2' AND superseded_at IS NULL;

  SELECT COUNT(*) INTO null_id
  FROM layer0.terrain_types
  WHERE superseded_at IS NULL AND terrain_id IS NULL;

  IF new_count <> 16 THEN
    RAISE EXCEPTION 'migrate_terrain_types: expected 16 active rows at v2.0-r2, found %', new_count;
  END IF;

  IF null_id > 0 THEN
    RAISE EXCEPTION 'migrate_terrain_types: % active rows still have NULL terrain_id', null_id;
  END IF;

  RAISE NOTICE 'migrate_terrain_types: OK — 16 structured rows active, 0 NULL terrain_id';
END $$;

COMMIT;
