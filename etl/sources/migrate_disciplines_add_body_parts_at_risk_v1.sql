-- migrate_disciplines_add_body_parts_at_risk_v1.sql
--
-- Promote `layer0.disciplines.common_injury_patterns` (free text) to a
-- structured `body_parts_at_risk TEXT[]` column. Enables direct set-
-- intersect against athlete `Injury Record.body_part` (canonical 51-token
-- vocabulary from Vocabulary_Audit_v2 + Collarbone amendment), replacing
-- the heuristic BODY_PART_KEYWORDS map currently in Layer 2D §5.5.
--
-- Population: 29 active discipline rows (post-R6 collapse).
-- Source of truth: D23_Curation_Reference_v1.md row tables.
-- Generator: etl/sources/generate_body_parts_at_risk_migration.py
--
-- Vocabulary: 51 canonical body parts (Vocabulary_Audit_v2 Section 1's 50
-- + Collarbone added 2026-05-12 per D-23 curation review).
--
-- Idempotent: ALTER TABLE / CREATE INDEX use IF NOT EXISTS; UPDATEs are
-- naturally idempotent (hardcoded values keyed on discipline_id).
--
-- Atomic: the DO $$ verification block at the end RAISEs EXCEPTION on
-- any violation, which rolls back the entire transaction.
--
-- Resolves: Project_Backlog D-23 (FC-1b).

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.disciplines
  ADD COLUMN IF NOT EXISTS body_parts_at_risk TEXT[];

COMMENT ON COLUMN layer0.disciplines.body_parts_at_risk IS
  'Canonical body parts at risk per discipline (subset of Vocabulary_Audit Section 1 + Collarbone). Populated by migrate_disciplines_add_body_parts_at_risk_v1.sql from D23_Curation_Reference_v1.md. Curated 2026-05-12.';

-- ── 2. Populate — 29 UPDATE statements grouped by sport family ──────────

-- Running family
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['IT band', 'Plantar fascia', 'Shin', 'Foot', 'Knee', 'Kneecap', 'Achilles', 'Ankle']::TEXT[]
 WHERE discipline_id = 'D-001' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Plantar fascia', 'IT band', 'Knee', 'Kneecap', 'Achilles', 'Shin', 'Hamstring', 'Foot']::TEXT[]
 WHERE discipline_id = 'D-002' AND superseded_at IS NULL;
UPDATE layer0.disciplines SET body_parts_at_risk = ARRAY['Ankle']::TEXT[] WHERE discipline_id = 'D-015' AND superseded_at IS NULL;
-- D-024 Mountain Running: R6 collapse union of uphill + downhill injury profiles.
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Hip flexor', 'Calf', 'Achilles', 'Knee', 'Kneecap', 'Shin', 'Foot', 'Ankle', 'Quad', 'IT band']::TEXT[]
 WHERE discipline_id = 'D-024' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Knee', 'Kneecap', 'Achilles', 'Plantar fascia', 'IT band', 'Wrist', 'Forearm']::TEXT[]
 WHERE discipline_id = 'D-026' AND superseded_at IS NULL;

-- Swimming family
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Rotator cuff', 'Shoulder', 'Neck', 'Elbow', 'Tricep']::TEXT[]
 WHERE discipline_id = 'D-004' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Rotator cuff', 'Shoulder', 'Knee', 'Ankle', 'Foot']::TEXT[]
 WHERE discipline_id = 'D-005' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Rotator cuff', 'Shoulder']::TEXT[]
 WHERE discipline_id = 'D-016' AND superseded_at IS NULL;

-- Cycling family
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Knee', 'Kneecap', 'IT band', 'Lower back', 'Neck', 'Shoulder', 'Achilles', 'Hand', 'Foot', 'Hip flexor']::TEXT[]
 WHERE discipline_id = 'D-006' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Knee', 'Kneecap', 'IT band', 'Lower back', 'Neck', 'Shoulder', 'Achilles', 'Hand', 'Foot', 'Hip flexor']::TEXT[]
 WHERE discipline_id = 'D-007' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Lower back', 'Knee', 'Hand', 'Wrist', 'Shoulder', 'Rotator cuff', 'Collarbone']::TEXT[]
 WHERE discipline_id = 'D-008' AND superseded_at IS NULL;

-- Paddle family
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Rotator cuff', 'Elbow', 'Lower back', 'Wrist', 'Bicep']::TEXT[]
 WHERE discipline_id = 'D-009' AND superseded_at IS NULL;
-- D-010 Kayaking: R6 collapse union of flat-water + whitewater injury profiles.
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Shoulder', 'Rotator cuff', 'Wrist', 'Lower back', 'Hand', 'Forearm']::TEXT[]
 WHERE discipline_id = 'D-010' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Shoulder', 'Rotator cuff', 'Wrist', 'Elbow', 'Lower back']::TEXT[]
 WHERE discipline_id = 'D-011' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Shoulder', 'Lower back']::TEXT[]
 WHERE discipline_id = 'D-019' AND superseded_at IS NULL;

-- Climbing / vertical / obstacles
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Finger pulley', 'Rotator cuff', 'Elbow', 'Wrist']::TEXT[]
 WHERE discipline_id = 'D-012' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Hand', 'Shoulder', 'Ankle', 'Shin', 'Lower back']::TEXT[]
 WHERE discipline_id = 'D-013' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Finger pulley', 'Shoulder']::TEXT[]
 WHERE discipline_id = 'D-014' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Fingers', 'Forearm', 'Shoulder', 'Rotator cuff', 'Ankle', 'Knee', 'Elbow']::TEXT[]
 WHERE discipline_id = 'D-027' AND superseded_at IS NULL;

-- Skimo / skiing family
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Hip flexor', 'Knee', 'Kneecap', 'IT band', 'Achilles', 'Lower back', 'Plantar fascia']::TEXT[]
 WHERE discipline_id = 'D-021' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['ACL', 'Knee', 'Shoulder', 'Wrist', 'Hip']::TEXT[]
 WHERE discipline_id = 'D-022' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Shoulder', 'Wrist', 'Calf', 'Shin', 'Foot']::TEXT[]
 WHERE discipline_id = 'D-023' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Shoulder', 'Rotator cuff', 'Knee', 'Lower back', 'Shin']::TEXT[]
 WHERE discipline_id = 'D-028' AND superseded_at IS NULL;

-- Hiking / snow travel
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Hip flexor', 'Lower back', 'Knee', 'Shoulder', 'Trapezius']::TEXT[]
 WHERE discipline_id = 'D-003' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Hip flexor', 'Hip', 'IT band', 'Ankle']::TEXT[]
 WHERE discipline_id = 'D-017' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Ankle', 'Hip flexor', 'Lower back', 'Knee', 'Shoulder', 'Trapezius', 'Finger pulley', 'Rotator cuff', 'Elbow', 'Wrist']::TEXT[]
 WHERE discipline_id = 'D-018' AND superseded_at IS NULL;

-- Combined / specialty
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Achilles', 'Foot', 'Shoulder', 'Hip flexor']::TEXT[]
 WHERE discipline_id = 'D-020' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Knee', 'Ankle', 'Hip flexor', 'Shoulder', 'Rotator cuff', 'Elbow', 'Lower back']::TEXT[]
 WHERE discipline_id = 'D-025' AND superseded_at IS NULL;
UPDATE layer0.disciplines
   SET body_parts_at_risk = ARRAY['Shoulder', 'Neck']::TEXT[]
 WHERE discipline_id = 'D-029' AND superseded_at IS NULL;

-- ── 3. Index — GIN on body_parts_at_risk for set-intersect performance ────

CREATE INDEX IF NOT EXISTS idx_disciplines_body_parts_at_risk
  ON layer0.disciplines USING GIN (body_parts_at_risk);

-- ── 4. Verify — RAISE EXCEPTION aborts the transaction on any violation ───

DO $$
DECLARE
  v_total_rows    INTEGER;
  v_null_rows     INTEGER;
  v_dup_rows      INTEGER;
  v_bad_parts     TEXT;
  v_missing_base  INTEGER;
  v_off_baseline  INTEGER;
  v_canonical     TEXT[] := ARRAY[
    'Neck',
    'Jaw',
    'Trapezius',
    'Shoulder',
    'Rotator cuff',
    'AC joint',
    'Shoulder blade',
    'Collarbone',
    'Elbow',
    'Forearm',
    'Wrist',
    'Hand',
    'Bicep',
    'Tricep',
    'Fingers',
    'Thumb',
    'Finger pulley',
    'DIP joint',
    'CMC joint',
    'Upper back',
    'Lower back',
    'Spine (general)',
    'SI joint',
    'Sciatica',
    'Hip',
    'Groin',
    'Hip flexor',
    'Glute',
    'Hip crest (iliac crest)',
    'TFL',
    'Quad',
    'Hamstring',
    'IT band',
    'Knee',
    'Kneecap',
    'Meniscus',
    'ACL',
    'PCL',
    'MCL',
    'LCL',
    'Calf',
    'Soleus',
    'Shin',
    'Achilles',
    'Peroneal',
    'Ankle',
    'Plantar fascia',
    'Foot',
    'Toes',
    'Rib',
    'Chest'
  ]::TEXT[];
  v_baseline      TEXT[] := ARRAY[
    'D-001',
    'D-002',
    'D-015',
    'D-024',
    'D-026',
    'D-004',
    'D-005',
    'D-016',
    'D-006',
    'D-007',
    'D-008',
    'D-009',
    'D-010',
    'D-011',
    'D-019',
    'D-012',
    'D-013',
    'D-014',
    'D-027',
    'D-021',
    'D-022',
    'D-023',
    'D-028',
    'D-003',
    'D-017',
    'D-018',
    'D-020',
    'D-025',
    'D-029'
  ]::TEXT[];
BEGIN
  -- 4a: active discipline row count should equal baseline size.
  -- Scope to superseded_at IS NULL — under the row-invalidation model each
  -- prior ETL version leaves its rows behind (superseded), so an unscoped
  -- COUNT(*) sees every historical version, not the active discipline set.
  SELECT COUNT(*) INTO v_total_rows FROM layer0.disciplines
    WHERE superseded_at IS NULL;
  IF v_total_rows <> 29 THEN
    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: expected % rows, found %',
      29, v_total_rows;
  END IF;

  -- 4b: every baseline discipline_id must exist as a row
  SELECT COUNT(*) INTO v_missing_base
    FROM unnest(v_baseline) AS b(discipline_id)
    WHERE NOT EXISTS (
      SELECT 1 FROM layer0.disciplines d
      WHERE d.discipline_id = b.discipline_id
        AND d.superseded_at IS NULL
    );
  IF v_missing_base > 0 THEN
    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % baseline discipline_id(s) not present',
      v_missing_base;
  END IF;

  -- 4c: no active row may have NULL body_parts_at_risk
  -- (superseded rows predate the column and legitimately stay NULL)
  SELECT COUNT(*) INTO v_null_rows
    FROM layer0.disciplines
    WHERE body_parts_at_risk IS NULL
      AND superseded_at IS NULL;
  IF v_null_rows > 0 THEN
    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % row(s) with NULL body_parts_at_risk',
      v_null_rows;
  END IF;

  -- 4d: every token must be in the canonical 51-token set
  SELECT string_agg(DISTINCT t.part, ', ') INTO v_bad_parts
    FROM layer0.disciplines d,
         unnest(d.body_parts_at_risk) AS t(part)
    WHERE NOT (t.part = ANY (v_canonical))
      AND d.superseded_at IS NULL;
  IF v_bad_parts IS NOT NULL THEN
    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: non-canonical token(s): %',
      v_bad_parts;
  END IF;

  -- 4e: no duplicate tokens within a single row's array
  -- (COALESCE on array_length: empty array → 0, not NULL)
  SELECT COUNT(*) INTO v_dup_rows
    FROM layer0.disciplines
    WHERE body_parts_at_risk IS NOT NULL
      AND superseded_at IS NULL
      AND COALESCE(array_length(body_parts_at_risk, 1), 0) IS DISTINCT FROM
          (SELECT COUNT(DISTINCT t)::INT FROM unnest(body_parts_at_risk) AS t);
  IF v_dup_rows > 0 THEN
    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % row(s) with duplicate tokens',
      v_dup_rows;
  END IF;

  -- 4f: no active row outside the curated baseline
  -- (superseded rows carry prior-scheme ids — D-008a/b, D-022/3, etc.)
  SELECT COUNT(*) INTO v_off_baseline
    FROM layer0.disciplines d
    WHERE NOT (d.discipline_id = ANY (v_baseline))
      AND d.superseded_at IS NULL;
  IF v_off_baseline > 0 THEN
    RAISE EXCEPTION 'migrate_disciplines_add_body_parts_at_risk: % discipline(s) outside the baseline',
      v_off_baseline;
  END IF;

  RAISE NOTICE 'migrate_disciplines_add_body_parts_at_risk: OK — 29 rows populated, % canonical body parts, GIN index in place',
    array_length(v_canonical, 1);
END $$;

COMMIT;

-- End of migrate_disciplines_add_body_parts_at_risk_v1.sql