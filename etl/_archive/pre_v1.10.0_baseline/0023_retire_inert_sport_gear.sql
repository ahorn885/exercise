-- 0023_retire_inert_sport_gear.sql
--
-- Retire three sport-gear rows from layer0.equipment_items that the per-locale
-- gear editor (routes/locales._layer0_equipment, which renders every active
-- equipment_items row) still offers, but which carry NO training-feasibility
-- signal: each is named in ZERO active exercises' equipment_required, so ticking
-- them or not never changes a single prescribed session. Same "clutter with no
-- training signal" test that retired the #623 assumed-gear set in 0008 — but
-- strictly simpler, because here there are no exercises to de-drift.
--
--   * Helmet, Power meter — cycling accessories KEPT by 0007 (#622) on the
--     "locale-able equipment, might gate on it" rationale. Re-evaluated
--     2026-06-23 (Andy-ratified via AskUserQuestion): a read of every active
--     exercise confirms neither is named in any equipment_required (0 rows
--     each), so the "might gate on it" premise does not hold — they gate
--     nothing. Retire them. (0007's apply-time guard asserting they stay active
--     was a one-shot check scoped to that migration; superseding them now is the
--     intended follow-up, not a regression of it.)
--   * Inline skates — a "Sport-Specific — Winter" singleton with no discipline
--     in the sport set (inline skating is not a discipline; the nearest sport,
--     skate-skiing D-028, is gated by the XC-ski toggles, not by this item) and
--     0 exercise references. Pure dead weight in the picker. Retire.
--
-- Explicitly NOT retired — these carry real signal, so they stay in the picker:
--   * Snowshoes       — gates real snowshoe exercises (e.g. EX153), and the
--                       "Snowshoeing setup" toggle separately gates D-017.
--   * Rollerskis      — gates real dryland-XC exercises; Andy chose (2026-06-23)
--                       to keep it rather than un-gate that training.
--   * Cycling trainer — maps to 8 cycling exercises + indoor routing (0012).
--   * Swim kit (Kickboard / Pull buoy / Swim fins) — deferred to a later swim
--                       slice (gear toggles + gear-gated swim drills); untouched.
--
-- Edit shape (README §"Two edit shapes"): CACHE-NEUTRAL structural edit (#1).
-- The retired rows are named in zero exercises, so the Layer 2C effective pool
-- and every plan-gen output are identical before and after — only the live,
-- uncached locale-picker read changes. Supersede-only; NO etl_version bump, so
-- plan-gen caches correctly stay warm (stale == correct, output unchanged).
-- The verify block below asserts that cache-neutral precondition (0 exercises
-- reference the retire set); if it ever trips, the edit is serving-relevant and
-- must instead supersede+re-insert the affected exercises at a bumped 0B version.
--
-- Idempotent: the supersede matches only still-active rows by canonical_name;
-- a re-run after apply selects nothing (clean no-op).
--
-- Atomic: the verify DO block RAISEs (rolling back the whole txn) if any of the
-- three is left active, if a retired item turns out to gate an exercise, or if a
-- kept survivor (Snowshoes / Rollerskis / Cycling trainer) was caught by mistake.

\set ON_ERROR_STOP on

BEGIN;

-- The 3 inert sport-gear rows retired from the equipment vocabulary. Dropped at
-- COMMIT.
CREATE TEMP TABLE _retire_gear (name text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _retire_gear (name) VALUES
  ('Helmet'), ('Power meter'), ('Inline skates');

-- ── Retire them from the equipment vocabulary ────────────────────────────────
-- Supersede-only (history preserved). The picker filters superseded_at IS NULL,
-- so the items vanish from it the moment this commits. No active exercise names
-- any of them (verified below), so no exercise de-drift pass is needed.
UPDATE layer0.equipment_items e
   SET superseded_at = now()
  FROM _retire_gear g
 WHERE e.superseded_at IS NULL
   AND e.canonical_name = g.name;

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_left_active INT;
  v_ex_dirty    INT;
  v_survivors   INT;
BEGIN
  -- none of the 3 is still active in the equipment vocabulary.
  SELECT count(*) INTO v_left_active
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN ('Helmet', 'Power meter', 'Inline skates');
  IF v_left_active > 0 THEN
    RAISE EXCEPTION '0023: % retire-set item(s) still active in equipment_items', v_left_active;
  END IF;

  -- the retired items really were inert: no active exercise names one in
  -- equipment_required. This guards the cache-neutral claim above — if it trips,
  -- the edit is serving-relevant and needs a 0B de-drift + version bump instead
  -- of this supersede-only (cache-neutral) shape.
  SELECT count(*) INTO v_ex_dirty
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND equipment_required && ARRAY['Helmet', 'Power meter', 'Inline skates'];
  IF v_ex_dirty > 0 THEN
    RAISE EXCEPTION '0023: % active exercise(s) name a retired item — edit is not cache-neutral', v_ex_dirty;
  END IF;

  -- guard against an over-broad retire — the signal-bearing winter/cycling
  -- equipment we deliberately keep must stay active.
  SELECT count(*) INTO v_survivors
    FROM (VALUES ('Snowshoes'), ('Rollerskis'), ('Cycling trainer')) s(name)
   WHERE EXISTS (
     SELECT 1 FROM layer0.equipment_items e
      WHERE e.superseded_at IS NULL AND e.canonical_name = s.name
   );
  IF v_survivors <> 3 THEN
    RAISE EXCEPTION '0023: expected Snowshoes + Rollerskis + Cycling trainer to remain active, found %', v_survivors;
  END IF;

  RAISE NOTICE '0023: OK — Helmet, Power meter, Inline skates retired from the picker (inert; no de-drift needed); winter/cycling signal-bearers kept';
END $$;

COMMIT;

-- End of 0023_retire_inert_sport_gear.sql
