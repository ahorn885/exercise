-- migrate_exercises_add_movement_components_v1.sql
--
-- Promote `layer0.exercises.injury_flags_text` (free text) to a structured
-- `movement_components TEXT[]` column. Enables mathematically exact set-
-- intersect against the Athlete_Onboarding_Data_Spec §B.3 11-token enum,
-- replacing the heuristic keyword-match path in Layer 2D.
--
-- Population: 159 active exercise rows (superseded_at IS NULL).
-- Baseline: 57 Pass 1 + 102 Pass 2 = 159 rows.
-- Source of truth: D22_Curation_Reference_v2.md row tables.
-- Generator: etl/sources/generate_movement_components_migration.py
--
-- Idempotent: ALTER TABLE / CREATE INDEX use IF NOT EXISTS; UPDATEs are
-- naturally idempotent (hardcoded values keyed on exercise_id with
-- superseded_at IS NULL filter).
--
-- Atomic: the DO $$ verification block at the end RAISEs EXCEPTION on
-- any violation, which rolls back the entire transaction (ALTER, UPDATEs,
-- INDEX). Safe to re-run.
--
-- Resolves: Project_Backlog D-22 (FC-1b).

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.exercises
  ADD COLUMN IF NOT EXISTS movement_components TEXT[];

COMMENT ON COLUMN layer0.exercises.movement_components IS
  'Canonical movement-constraint tokens (subset of Onboarding §B.3 11-token enum). Populated by migrate_exercises_add_movement_components_v1.sql from D22_Curation_Reference_v2.md. Curated 2026-05-11 (Pass 1) / 2026-05-12 (Pass 2).';

-- ── 2. Populate — 159 UPDATE statements grouped by curation section ───────

-- Pass 1 — Activation / Primer
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with impact', 'Pain with wrist extension', 'Pain with loading', 'Reduced ROM']::TEXT[]
 WHERE exercise_id = 'EX159' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading', 'Pain on rotation', 'Pain above specific joint angle', 'Pain with impact']::TEXT[]
 WHERE exercise_id = 'EX240' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Reduced ROM', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX218' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain at high volume only']::TEXT[] WHERE exercise_id = 'EX217' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX110' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX066' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX083' AND superseded_at IS NULL;

-- Pass 1 — Aerobic / Endurance
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX185' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Reduced ROM', 'Pain at high volume only', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX168' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX150' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX120' AND superseded_at IS NULL;

-- Pass 1 — Agility
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Instability', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX054' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain on descent / eccentric', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX055' AND superseded_at IS NULL;

-- Pass 1 — Balance / Proprioception
UPDATE layer0.exercises SET movement_components = ARRAY['Reduced ROM', 'Pain with loading', 'Instability']::TEXT[] WHERE exercise_id = 'EX115' AND superseded_at IS NULL;

-- Pass 1 — Breathwork
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with grip / sustained hold']::TEXT[] WHERE exercise_id = 'EX139' AND superseded_at IS NULL;

-- Pass 1 — Flexibility / Stretching
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX096' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX046' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX047' AND superseded_at IS NULL;

-- Pass 1 — Interval / Tempo
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading', 'Pain on descent / eccentric']::TEXT[]
 WHERE exercise_id = 'EX180' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain at high volume only', 'Pain with loading', 'Reduced ROM', 'Pain on descent / eccentric']::TEXT[]
 WHERE exercise_id = 'EX215' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain on descent / eccentric']::TEXT[] WHERE exercise_id = 'EX197' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX178' AND superseded_at IS NULL;

-- Pass 1 — Isometric
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain at high volume only', 'Pain with loading', 'Reduced ROM']::TEXT[]
 WHERE exercise_id = 'EX174' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain with wrist extension', 'Pain above specific joint angle', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX226' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX201' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with wrist extension', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX216' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain at high volume only', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX160' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX219' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX225' AND superseded_at IS NULL;

-- Pass 1 — Loaded Carry
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle', 'Pain with loading', 'Pain with wrist extension']::TEXT[]
 WHERE exercise_id = 'EX244' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain with grip / sustained hold', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX243' AND superseded_at IS NULL;

-- Pass 1 — Mobility
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX065' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX045' AND superseded_at IS NULL;

-- Pass 1 — Plyometric
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain at high volume only', 'Pain above specific joint angle', 'Instability', 'Pain with wrist extension', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX221' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with impact', 'Instability', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX034' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with impact', 'Pain at high volume only', 'Instability']::TEXT[] WHERE exercise_id = 'EX035' AND superseded_at IS NULL;

-- Pass 1 — Power
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading', 'Pain above specific joint angle', 'Instability', 'Pain with impact']::TEXT[]
 WHERE exercise_id = 'EX232' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading', 'Pain with impact', 'Pain above specific joint angle', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX238' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with impact', 'Pain above specific joint angle', 'Pain on rotation', 'Pain at high volume only', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX245' AND superseded_at IS NULL;

-- Pass 1 — Recovery / Soft Tissue
UPDATE layer0.exercises SET movement_components = ARRAY[]::TEXT[] WHERE exercise_id = 'EX018' AND superseded_at IS NULL;

-- Pass 1 — Strength
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle', 'Pain with loading', 'Pain with grip / sustained hold', 'Pain at high volume only', 'Pain on rotation', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX195' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading', 'Pain above specific joint angle', 'Reduced ROM']::TEXT[]
 WHERE exercise_id = 'EX231' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Instability', 'Pain with grip / sustained hold', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX223' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with wrist extension', 'Pain with loading', 'Pain with impact']::TEXT[]
 WHERE exercise_id = 'EX229' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle', 'Instability', 'Pain with grip / sustained hold', 'Pain with impact']::TEXT[]
 WHERE exercise_id = 'EX230' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain with loading', 'Instability', 'Pain with wrist extension', 'Pain on rotation', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX239' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Instability', 'Pain with loading', 'Pain with wrist extension', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX241' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Instability', 'Pain with wrist extension']::TEXT[]
 WHERE exercise_id = 'EX222' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading', 'Pain above specific joint angle', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX228' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX233' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX237' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX236' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX220' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain on rotation', 'Instability', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX242' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Instability']::TEXT[] WHERE exercise_id = 'EX224' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX234' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle', 'Pain with loading', 'Pain with wrist extension']::TEXT[]
 WHERE exercise_id = 'EX098' AND superseded_at IS NULL;

-- Pass 2 — Activation / Primer
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX013' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX017' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX039' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX040' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX041' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Instability', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX042' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX062' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX063' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX081' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading']::TEXT[] WHERE exercise_id = 'EX082' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading']::TEXT[] WHERE exercise_id = 'EX105' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with overhead movement']::TEXT[] WHERE exercise_id = 'EX109' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle', 'Pain with loading', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX127' AND superseded_at IS NULL;

-- Pass 2 — Aerobic / Endurance
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX051' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on descent / eccentric', 'Pain with loading', 'Instability']::TEXT[] WHERE exercise_id = 'EX052' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain at high volume only', 'Pain on rotation']::TEXT[] WHERE exercise_id = 'EX090' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX124' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Instability', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX126' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Reduced ROM', 'Pain at high volume only']::TEXT[]
 WHERE exercise_id = 'EX128' AND superseded_at IS NULL;

-- Pass 2 — Agility
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX053' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain on rotation', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX056' AND superseded_at IS NULL;

-- Pass 2 — Balance / Proprioception
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX043' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX044' AND superseded_at IS NULL;

-- Pass 2 — Flexibility / Stretching
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Instability']::TEXT[] WHERE exercise_id = 'EX015' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX076' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain above specific joint angle', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX077' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX097' AND superseded_at IS NULL;

-- Pass 2 — Interval / Tempo
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain with impact', 'Pain at high volume only', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX048' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain with loading', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX049' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading', 'Pain at high volume only']::TEXT[] WHERE exercise_id = 'EX073' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading']::TEXT[] WHERE exercise_id = 'EX074' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX075' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with impact', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX179' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only']::TEXT[] WHERE exercise_id = 'EX186' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain at high volume only', 'Instability', 'Pain with loading', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX203' AND superseded_at IS NULL;

-- Pass 2 — Isometric
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain with wrist extension', 'Pain with loading', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX005' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain on rotation']::TEXT[] WHERE exercise_id = 'EX011' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX012' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX037' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX038' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain at high volume only', 'Pain above specific joint angle', 'Pain with wrist extension', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX067' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX084' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Instability', 'Pain at high volume only', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX089' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with grip / sustained hold', 'Pain with wrist extension', 'Pain with loading', 'Pain with overhead movement']::TEXT[]
 WHERE exercise_id = 'EX100' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with grip / sustained hold', 'Pain above specific joint angle', 'Pain with overhead movement']::TEXT[]
 WHERE exercise_id = 'EX101' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain with wrist extension', 'Pain at high volume only', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX102' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading', 'Pain above specific joint angle', 'Pain with overhead movement', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX106' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain with loading', 'Pain with grip / sustained hold', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX107' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain at high volume only', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX173' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain at high volume only', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX227' AND superseded_at IS NULL;

-- Pass 2 — Loaded Carry
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain with loading', 'Pain with grip / sustained hold']::TEXT[] WHERE exercise_id = 'EX009' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading', 'Pain on descent / eccentric']::TEXT[]
 WHERE exercise_id = 'EX010' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain at high volume only', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX050' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Instability', 'Pain with loading', 'Pain at high volume only']::TEXT[]
 WHERE exercise_id = 'EX095' AND superseded_at IS NULL;

-- Pass 2 — Mobility
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with wrist extension', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX014' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX016' AND superseded_at IS NULL;

-- Pass 2 — Plyometric
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with impact', 'Instability', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX007' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with impact', 'Pain above specific joint angle', 'Instability']::TEXT[] WHERE exercise_id = 'EX008' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading', 'Pain on descent / eccentric', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX033' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Reduced ROM', 'Pain with impact', 'Pain at high volume only']::TEXT[]
 WHERE exercise_id = 'EX036' AND superseded_at IS NULL;

-- Pass 2 — Power
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX029' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with wrist extension', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX031' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with impact', 'Instability', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX032' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain on rotation', 'Pain with loading', 'Pain on descent / eccentric', 'Pain with impact']::TEXT[]
 WHERE exercise_id = 'EX085' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Pain with loading', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX086' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain with impact', 'Pain on descent / eccentric', 'Pain above specific joint angle', 'Pain with overhead movement', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX108' AND superseded_at IS NULL;

-- Pass 2 — Strength
UPDATE layer0.exercises
   SET movement_components = ARRAY['Instability', 'Pain above specific joint angle', 'Pain with loading', 'Reduced ROM']::TEXT[]
 WHERE exercise_id = 'EX001' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Instability', 'Pain above specific joint angle', 'Pain with loading', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX002' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Reduced ROM', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX003' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Instability', 'Pain on rotation', 'Pain with loading', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX004' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with overhead movement', 'Pain with grip / sustained hold', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX006' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX019' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain above specific joint angle', 'Pain on descent / eccentric', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX020' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX021' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX022' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Instability', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX023' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX024' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading']::TEXT[] WHERE exercise_id = 'EX025' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading']::TEXT[] WHERE exercise_id = 'EX026' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Reduced ROM']::TEXT[] WHERE exercise_id = 'EX027' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle', 'Reduced ROM', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX028' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading']::TEXT[] WHERE exercise_id = 'EX030' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability', 'Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX060' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX061' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle', 'Pain on descent / eccentric']::TEXT[]
 WHERE exercise_id = 'EX064' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with wrist extension', 'Pain above specific joint angle', 'Pain with loading', 'Pain on rotation']::TEXT[]
 WHERE exercise_id = 'EX068' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with loading', 'Pain above specific joint angle', 'Reduced ROM']::TEXT[] WHERE exercise_id = 'EX069' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Instability']::TEXT[] WHERE exercise_id = 'EX070' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain on rotation', 'Instability', 'Pain above specific joint angle', 'Pain with loading']::TEXT[]
 WHERE exercise_id = 'EX078' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX079' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with overhead movement', 'Pain with wrist extension', 'Pain with loading', 'Pain above specific joint angle']::TEXT[]
 WHERE exercise_id = 'EX080' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain on rotation', 'Pain with loading', 'Pain above specific joint angle', 'Pain with overhead movement']::TEXT[]
 WHERE exercise_id = 'EX087' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Pain with loading', 'Pain above specific joint angle']::TEXT[] WHERE exercise_id = 'EX088' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain with wrist extension', 'Pain with overhead movement']::TEXT[]
 WHERE exercise_id = 'EX099' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain with wrist extension', 'Pain with grip / sustained hold']::TEXT[]
 WHERE exercise_id = 'EX103' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with grip / sustained hold']::TEXT[] WHERE exercise_id = 'EX104' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain with wrist extension', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX111' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain with loading', 'Pain on descent / eccentric', 'Instability', 'Pain with impact']::TEXT[]
 WHERE exercise_id = 'EX117' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading', 'Pain with impact']::TEXT[] WHERE exercise_id = 'EX119' AND superseded_at IS NULL;
UPDATE layer0.exercises
   SET movement_components = ARRAY['Pain on descent / eccentric', 'Pain at high volume only', 'Pain with loading', 'Instability']::TEXT[]
 WHERE exercise_id = 'EX125' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain on rotation', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX129' AND superseded_at IS NULL;
UPDATE layer0.exercises SET movement_components = ARRAY['Pain above specific joint angle', 'Pain with loading']::TEXT[] WHERE exercise_id = 'EX235' AND superseded_at IS NULL;

-- ── 3. Index — GIN on movement_components for set-intersect performance ───

CREATE INDEX IF NOT EXISTS idx_exercises_movement_components
  ON layer0.exercises USING GIN (movement_components);

-- ── 4. Verify — RAISE EXCEPTION aborts the transaction on any violation ───

DO $$
DECLARE
  v_active_rows   INTEGER;
  v_null_rows     INTEGER;
  v_dup_rows      INTEGER;
  v_bad_tokens    TEXT;
  v_missing_base  INTEGER;
  v_off_baseline  INTEGER;
  v_canonical     TEXT[] := ARRAY[
    'Pain with loading',
    'Pain with impact',
    'Pain above specific joint angle',
    'Pain on descent / eccentric',
    'Pain on rotation',
    'Pain with grip / sustained hold',
    'Pain with wrist extension',
    'Pain with overhead movement',
    'Instability',
    'Reduced ROM',
    'Pain at high volume only'
  ]::TEXT[];
  v_baseline      TEXT[] := ARRAY[
    'EX159',
    'EX240',
    'EX218',
    'EX217',
    'EX110',
    'EX066',
    'EX083',
    'EX185',
    'EX168',
    'EX150',
    'EX120',
    'EX054',
    'EX055',
    'EX115',
    'EX139',
    'EX096',
    'EX046',
    'EX047',
    'EX180',
    'EX215',
    'EX197',
    'EX178',
    'EX174',
    'EX226',
    'EX201',
    'EX216',
    'EX160',
    'EX219',
    'EX225',
    'EX244',
    'EX243',
    'EX065',
    'EX045',
    'EX221',
    'EX034',
    'EX035',
    'EX232',
    'EX238',
    'EX245',
    'EX018',
    'EX195',
    'EX231',
    'EX223',
    'EX229',
    'EX230',
    'EX239',
    'EX241',
    'EX222',
    'EX228',
    'EX233',
    'EX237',
    'EX236',
    'EX220',
    'EX242',
    'EX224',
    'EX234',
    'EX098',
    'EX013',
    'EX017',
    'EX039',
    'EX040',
    'EX041',
    'EX042',
    'EX062',
    'EX063',
    'EX081',
    'EX082',
    'EX105',
    'EX109',
    'EX127',
    'EX051',
    'EX052',
    'EX090',
    'EX124',
    'EX126',
    'EX128',
    'EX053',
    'EX056',
    'EX043',
    'EX044',
    'EX015',
    'EX076',
    'EX077',
    'EX097',
    'EX048',
    'EX049',
    'EX073',
    'EX074',
    'EX075',
    'EX179',
    'EX186',
    'EX203',
    'EX005',
    'EX011',
    'EX012',
    'EX037',
    'EX038',
    'EX067',
    'EX084',
    'EX089',
    'EX100',
    'EX101',
    'EX102',
    'EX106',
    'EX107',
    'EX173',
    'EX227',
    'EX009',
    'EX010',
    'EX050',
    'EX095',
    'EX014',
    'EX016',
    'EX007',
    'EX008',
    'EX033',
    'EX036',
    'EX029',
    'EX031',
    'EX032',
    'EX085',
    'EX086',
    'EX108',
    'EX001',
    'EX002',
    'EX003',
    'EX004',
    'EX006',
    'EX019',
    'EX020',
    'EX021',
    'EX022',
    'EX023',
    'EX024',
    'EX025',
    'EX026',
    'EX027',
    'EX028',
    'EX030',
    'EX060',
    'EX061',
    'EX064',
    'EX068',
    'EX069',
    'EX070',
    'EX078',
    'EX079',
    'EX080',
    'EX087',
    'EX088',
    'EX099',
    'EX103',
    'EX104',
    'EX111',
    'EX117',
    'EX119',
    'EX125',
    'EX129',
    'EX235'
  ]::TEXT[];
BEGIN
  -- 4a: active row count should be exactly 159
  SELECT COUNT(*) INTO v_active_rows
    FROM layer0.exercises WHERE superseded_at IS NULL;
  IF v_active_rows <> 159 THEN
    RAISE EXCEPTION 'migrate_exercises_add_movement_components: expected % active rows, found %',
      159, v_active_rows;
  END IF;

  -- 4b: every baseline exercise_id must exist as an active row
  SELECT COUNT(*) INTO v_missing_base
    FROM unnest(v_baseline) AS b(exercise_id)
    WHERE NOT EXISTS (
      SELECT 1 FROM layer0.exercises e
      WHERE e.exercise_id = b.exercise_id AND e.superseded_at IS NULL
    );
  IF v_missing_base > 0 THEN
    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % baseline exercise_id(s) not present as active rows',
      v_missing_base;
  END IF;

  -- 4c: no active row may have NULL movement_components
  SELECT COUNT(*) INTO v_null_rows
    FROM layer0.exercises
    WHERE superseded_at IS NULL AND movement_components IS NULL;
  IF v_null_rows > 0 THEN
    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % active row(s) with NULL movement_components',
      v_null_rows;
  END IF;

  -- 4d: every token must be in the canonical 11-token set
  SELECT string_agg(DISTINCT t.token, ', ') INTO v_bad_tokens
    FROM layer0.exercises e,
         unnest(e.movement_components) AS t(token)
    WHERE e.superseded_at IS NULL
      AND NOT (t.token = ANY (v_canonical));
  IF v_bad_tokens IS NOT NULL THEN
    RAISE EXCEPTION 'migrate_exercises_add_movement_components: non-canonical token(s) found: %',
      v_bad_tokens;
  END IF;

  -- 4e: no duplicate tokens within a single row's array
  -- (COALESCE on array_length: empty array → 0, not NULL, so check passes for EX018)
  SELECT COUNT(*) INTO v_dup_rows
    FROM layer0.exercises
    WHERE superseded_at IS NULL
      AND movement_components IS NOT NULL
      AND COALESCE(array_length(movement_components, 1), 0) IS DISTINCT FROM
          (SELECT COUNT(DISTINCT t)::INT FROM unnest(movement_components) AS t);
  IF v_dup_rows > 0 THEN
    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % row(s) with duplicate tokens',
      v_dup_rows;
  END IF;

  -- 4f: no active row outside the curated baseline
  -- (catches: active row added since curation that we missed)
  SELECT COUNT(*) INTO v_off_baseline
    FROM layer0.exercises e
    WHERE e.superseded_at IS NULL
      AND NOT (e.exercise_id = ANY (v_baseline));
  IF v_off_baseline > 0 THEN
    RAISE EXCEPTION 'migrate_exercises_add_movement_components: % active exercise(s) outside the 159-row baseline',
      v_off_baseline;
  END IF;

  RAISE NOTICE 'migrate_exercises_add_movement_components: OK — 159 rows populated, % canonical tokens, GIN index in place',
    array_length(v_canonical, 1);
END $$;

COMMIT;

-- End of migrate_exercises_add_movement_components_v1.sql