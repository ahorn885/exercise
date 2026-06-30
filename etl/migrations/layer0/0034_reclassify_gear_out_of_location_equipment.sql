-- 0034_reclassify_gear_out_of_location_equipment.sql
--
-- #1063 — finish the job 0007 started (vessels) for the remaining mis-bucketed
-- items: portable, athlete-OWNED gear must live in the athlete gear store
-- (athlete_gear / GEAR_REGISTRY), NOT the per-location equipment vocabulary.
-- Four canonical names are still active in layer0.equipment_items, so the
-- per-locale gear editor (routes/locales._layer0_equipment, which renders every
-- active equipment_items row) still offers them as "location equipment":
--
--   * 'Swim paddles'      (Sport-Specific — Swimming)  -> athlete gear only
--   * 'SwimRun paddles'   (Sport-Specific — Swimming)  -> athlete gear only
--   * 'Snowshoes'         (Sport-Specific — Winter)    -> gear only (showed in BOTH
--                                                         equipment + the gear toggle)
--   * 'Rollerskis'        (Sport-Specific — Winter)    -> gear only (showed in BOTH)
--
-- Snowshoes + Rollerskis are already owned-gear toggles (athlete_gear_repo.
-- GEAR_REGISTRY: 'snowshoes' -> snow, 'rollerskis' -> ski; GEAR_TOGGLE_LABELS),
-- so they were double-listed. Swim/SwimRun paddles are swim-kind owned gear
-- ('paddles' in GEAR_REGISTRY); they belong with the athlete, not the venue.
-- This retires all four from the equipment vocabulary so they stop being offered
-- as location equipment.
--
-- KEEP the genuine cardio machine 'Paddle ergometer' (category Machines - Cardio)
-- — it IS locale-able equipment, not portable owned gear. The verify block below
-- guards against an over-broad match accidentally retiring it.
--
-- Edit shape — CACHE-NEUTRAL structural edit (README §"Two edit shapes" #1; no
-- version bump). The serving path `locations.locale_effective_tags` reads the
-- stored `gym_profiles.equipment` JSON directly and does NOT re-validate it
-- against the active vocabulary, so retiring these rows changes only what the
-- equipment PICKER offers (and what a future re-save keeps, since `_edit_locale`
-- filters submissions to `valid_names`) — it does not alter any already-served
-- plan output at apply time. equipment_items stays in _LAYER0_TABLE_FAMILY; no
-- family-map change.
--
-- Idempotent: the supersede matches only still-active rows by exact canonical
-- name; a re-run after apply is a clean no-op.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- of the four is left active, or if 'Paddle ergometer' was caught by mistake.

\set ON_ERROR_STOP on

BEGIN;

-- The 4 owned-gear canonical names retired from the location-equipment vocab.
CREATE TEMP TABLE _gear_names (name text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _gear_names (name) VALUES
  ('Swim paddles'), ('SwimRun paddles'), ('Snowshoes'), ('Rollerskis');

-- Supersede-only (history preserved; the active set loses them).
UPDATE layer0.equipment_items e
   SET superseded_at = now()
  FROM _gear_names g
 WHERE e.superseded_at IS NULL
   AND e.canonical_name = g.name;

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_left_active INT;
  v_ergo_gone   INT;
BEGIN
  -- None of the four is still active in the equipment vocabulary.
  SELECT count(*) INTO v_left_active
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN (SELECT name FROM _gear_names);
  IF v_left_active > 0 THEN
    RAISE EXCEPTION '0034: % owned-gear name(s) still active in equipment_items', v_left_active;
  END IF;

  -- The genuine cardio machine survived (guards against an over-broad retire).
  SELECT count(*) INTO v_ergo_gone
    FROM (VALUES ('Paddle ergometer')) a(name)
   WHERE NOT EXISTS (
     SELECT 1 FROM layer0.equipment_items e
      WHERE e.superseded_at IS NULL AND e.canonical_name = a.name
   );
  IF v_ergo_gone > 0 THEN
    RAISE EXCEPTION '0034: Paddle ergometer was retired by mistake (over-broad match)';
  END IF;

  RAISE NOTICE '0034: OK — swim/swimrun paddles + snowshoes + rollerskis retired from location equipment (now athlete gear only)';
END $$;

COMMIT;

-- End of 0034_reclassify_gear_out_of_location_equipment.sql
