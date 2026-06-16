-- 0007_retire_vessel_equipment_add_crafts.sql
--
-- #622 — movable crafts (bikes / boats) must live in the athlete-level craft
-- store, NOT the per-location equipment vocabulary. #586 added the craft store
-- (athlete.BIKE_TYPES / PADDLE_CRAFT_TYPES -> discipline_baseline_* + the
-- craft_discipline_aliases / craft_terrain_compatibility feasibility wiring) but
-- never removed the vessels from layer0.equipment_items, so the per-locale gear
-- editor (routes/locales._layer0_equipment, which renders every active
-- equipment_items row) still lists them under "Sport-Specific — Cycling/Paddle
-- (top-level vessels — kept individual)".
--
-- This migration does three coupled things (Andy-ratified via AskUserQuestion,
-- 2026-06-16; Trigger #2 vocab + Trigger #3 cross-layer):
--
--   (0C) Retire the 9 vessel rows from layer0.equipment_items so the gear picker
--        stops offering them. KEEP the genuine accessories that share those
--        categories (Power meter, Helmet, Cycling trainer) — they are locale-able
--        equipment, not portable owned vessels.
--
--   (0A) Add the 3 vessels missing from the craft store so every bike/boat has a
--        home there: tt_bike (TT / triathlon bike), sup (Stand-up Paddleboard),
--        raft (Raft). Each gets a craft_discipline_aliases row (the discipline it
--        unlocks in the feasibility cascade) + craft_terrain_compatibility rows
--        (the terrain it can travel), mirroring the closest existing craft.
--        Live discipline/terrain keyspace verified via neon-query (0A-v1.6.8):
--          tt_bike -> D-007 Time-Trial Cycling ; terrain TRN-001 Road, TRN-004 Hill/Rolling
--          raft    -> D-019 Paddle Rafting     ; terrain TRN-009 Flat Water, TRN-011 Whitewater, TRN-017 Moving Water
--          sup     -> D-032 Stand-up Paddleboard; terrain TRN-009 Flat Water, TRN-010 Ocean/Tidal
--
--   (0B) De-drift the exercises that name a vessel in equipment_required. Post-#586
--        the DISCIPLINE-level cascade (session_feasibility, craft-aware) is the
--        authority on whether a cycling/paddling session is scheduled; Layer 2C
--        exercise resolution gating a bike *exercise* on vessel-equipment is now
--        redundant double-gating (and references vessels we are retiring). Drop the
--        vessel tokens from equipment_required (the active rows already use the
--        canonical "Cycling trainer" name — the old "Bike trainer"/"TT Bike" drift
--        lived only in superseded rows), keeping any genuine accessory (Cycling
--        trainer, Backpack, Foam pad, Treadmill). One exercise (EX174) also names a
--        vessel inside equipment_substitutes_structured — cleaned in the same pass.
--
-- Edit shape — SERVING-RELEVANT (README §"Two edit shapes" #2) for all three:
--   * equipment_items: a removal that changes the gear picker + 2C effective pool
--     (supersede only; the 0A/0B bumps below carry cache invalidation, since every
--     plan reads exercises (0B) and craft plans read the craft tables (0A)).
--   * exercises: supersede + re-insert the affected rows at 0B-v1.6.7 -> 0B-v1.6.8.
--   * craft_discipline_aliases / craft_terrain_compatibility: insert the new rows
--     at 0A-v1.6.7 -> 0A-v1.6.8 (additive; existing rows untouched). MAX per-table
--     version advances, so the 0A digest invalidates craft plan-gen caches.
-- All four tables are already in _LAYER0_TABLE_FAMILY — no family-map change.
--
-- Idempotent: equipment_items supersede matches only still-active vessels;
-- the exercise reinsert/supersede is guarded to the pre-bump version
-- (etl_version <> '0B-v1.6.8'); the craft inserts are guarded by NOT EXISTS on
-- the active craft_name. A re-run after apply is a clean no-op (no UNIQUE
-- collision on (exercise_id, etl_version) / (craft_name, *, etl_version)).
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- vessel is left active in equipment, any active exercise still names a vessel,
-- or any new craft alias/terrain row is missing.

\set ON_ERROR_STOP on

BEGIN;

-- The 9 vessel canonical names retired from equipment_items + stripped from
-- exercise equipment_required. Dropped at COMMIT.
CREATE TEMP TABLE _vessels (name text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _vessels (name) VALUES
  ('Road bike'), ('Mountain bike'), ('Gravel bike'), ('TT / triathlon bike'),
  ('Kayak'), ('Canoe'), ('Packraft'), ('Stand-up Paddleboard'), ('Raft');

-- ── (0C) Retire the vessels from the equipment vocabulary ────────────────────
-- Supersede-only (history preserved); accessories in the same categories stay.
UPDATE layer0.equipment_items e
   SET superseded_at = now()
  FROM _vessels v
 WHERE e.superseded_at IS NULL
   AND e.canonical_name = v.name;

-- ── (0A) Add the 3 missing vessels to the craft store ────────────────────────
-- craft_discipline_aliases: craft_name -> the discipline it unlocks (+ group_kind).
INSERT INTO layer0.craft_discipline_aliases
  (craft_name, discipline_id, group_kind, etl_version, etl_run_at)
SELECT c.craft_name, c.discipline_id, c.group_kind, '0A-v1.6.8', now()
FROM (VALUES
  ('tt_bike', 'D-007', 'bike'),
  ('raft',    'D-019', 'paddle'),
  ('sup',     'D-032', 'paddle')
) AS c(craft_name, discipline_id, group_kind)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.craft_discipline_aliases a
   WHERE a.superseded_at IS NULL AND a.craft_name = c.craft_name
);

-- craft_terrain_compatibility: craft_name -> terrain it can travel (mirrors the
-- closest existing craft — tt_bike≈road_bike, raft≈packraft, sup≈flatwater/ocean).
INSERT INTO layer0.craft_terrain_compatibility
  (craft_name, terrain_id, etl_version, etl_run_at)
SELECT c.craft_name, c.terrain_id, '0A-v1.6.8', now()
FROM (VALUES
  ('tt_bike', 'TRN-001'), ('tt_bike', 'TRN-004'),
  ('raft',    'TRN-009'), ('raft',    'TRN-011'), ('raft', 'TRN-017'),
  ('sup',     'TRN-009'), ('sup',     'TRN-010')
) AS c(craft_name, terrain_id)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.craft_terrain_compatibility t
   WHERE t.superseded_at IS NULL
     AND t.craft_name = c.craft_name AND t.terrain_id = c.terrain_id
);

-- ── (0B) De-drift the affected exercises ─────────────────────────────────────
-- Re-insert each active exercise that names a vessel, with the vessel tokens
-- removed from equipment_required (order preserved) and EX174's vessel substitute
-- cleaned. Every other column copied verbatim; id (serial) + superseded_at (NULL)
-- omitted.
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
  e.secondary_muscles,
  (
    SELECT COALESCE(array_agg(tok ORDER BY ord), '{}')
      FROM unnest(e.equipment_required) WITH ORDINALITY AS u(tok, ord)
     WHERE tok NOT IN (SELECT name FROM _vessels)
  ),
  e.injury_flags_text, e.contraindicated_parts,
  e.contraindicated_conditions, e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name, e.regression_exercise_id,
  e.regression_exercise_name, e.sport_count, e.coaching_cues,
  '0B-v1.6.8', now(), e.terrain_required,
  CASE WHEN e.exercise_id = 'EX174'
    THEN '[{"is_improvised": false, "substitute_text": "Road bike with clip-on aero bars", "equipment_required": []}, {"is_improvised": true, "substitute_text": "Handlebar spacer reduction (position change)", "equipment_required": []}]'::jsonb
    ELSE e.equipment_substitutes_structured
  END,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.8'
  AND e.equipment_required && ARRAY(SELECT name FROM _vessels);

-- Supersede the old (vessel-bearing) rows now replaced by the cleaned copies.
UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.etl_version <> '0B-v1.6.8'
   AND e.equipment_required && ARRAY(SELECT name FROM _vessels);

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_left_active   INT;
  v_acc_missing   INT;
  v_ex_dirty      INT;
  v_alias_missing INT;
  v_terr_missing  INT;
BEGIN
  -- 0C: no vessel is still active in the equipment vocabulary.
  SELECT count(*) INTO v_left_active
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN (SELECT name FROM _vessels);
  IF v_left_active > 0 THEN
    RAISE EXCEPTION '0007: % vessel(s) still active in equipment_items', v_left_active;
  END IF;

  -- 0C: the kept accessories survived (guards against an over-broad retire).
  SELECT count(*) INTO v_acc_missing
    FROM (VALUES ('Power meter'), ('Helmet'), ('Cycling trainer')) a(name)
   WHERE NOT EXISTS (
     SELECT 1 FROM layer0.equipment_items e
      WHERE e.superseded_at IS NULL AND e.canonical_name = a.name
   );
  IF v_acc_missing > 0 THEN
    RAISE EXCEPTION '0007: % expected accessory row(s) missing from equipment_items', v_acc_missing;
  END IF;

  -- 0B: no active exercise still names a retired vessel in equipment_required.
  SELECT count(*) INTO v_ex_dirty
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND equipment_required && ARRAY(SELECT name FROM _vessels);
  IF v_ex_dirty > 0 THEN
    RAISE EXCEPTION '0007: % active exercise(s) still name a retired vessel', v_ex_dirty;
  END IF;

  -- 0A: the 3 new craft aliases are active and point at real active disciplines.
  SELECT count(*) INTO v_alias_missing
    FROM (VALUES ('tt_bike', 'D-007'), ('raft', 'D-019'), ('sup', 'D-032')) c(craft_name, discipline_id)
   WHERE NOT EXISTS (
     SELECT 1 FROM layer0.craft_discipline_aliases a
      JOIN layer0.disciplines d
        ON d.discipline_id = a.discipline_id AND d.superseded_at IS NULL
     WHERE a.superseded_at IS NULL
       AND a.craft_name = c.craft_name AND a.discipline_id = c.discipline_id
   );
  IF v_alias_missing > 0 THEN
    RAISE EXCEPTION '0007: % new craft alias(es) missing or pointing at a dead discipline', v_alias_missing;
  END IF;

  -- 0A: every new craft has at least one active terrain-compatibility row.
  SELECT count(*) INTO v_terr_missing
    FROM (VALUES ('tt_bike'), ('raft'), ('sup')) c(craft_name)
   WHERE NOT EXISTS (
     SELECT 1 FROM layer0.craft_terrain_compatibility t
      WHERE t.superseded_at IS NULL AND t.craft_name = c.craft_name
   );
  IF v_terr_missing > 0 THEN
    RAISE EXCEPTION '0007: % new craft(s) missing terrain compatibility', v_terr_missing;
  END IF;

  RAISE NOTICE '0007: OK — vessels retired from equipment; tt_bike/raft/sup added to the craft store; exercises de-drifted';
END $$;

COMMIT;

-- End of 0007_retire_vessel_equipment_add_crafts.sql
