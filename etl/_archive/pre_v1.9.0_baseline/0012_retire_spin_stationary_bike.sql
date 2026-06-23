-- 0012_retire_spin_stationary_bike.sql
--
-- #692 — fold the duplicative indoor-cycling machines into one picker entry.
-- The per-locale gear editor (routes/locales._layer0_equipment) renders every
-- active layer0.equipment_items row. Investigation (read-only neon-query +
-- etl/output/layer0_etl_v1.8.0.sql, 2026-06-17) showed four near-identical
-- indoor bikes — `Cycling trainer`, `Stationary bike`, `Spin bike`,
-- `Assault bike` — that the feasibility cascade's INDOOR tier
-- (layer4/session_feasibility._DISCIPLINE_INDOOR_MACHINES, D-006/007/008/030/031)
-- treats interchangeably: any one present routes a cycling session indoors.
-- `Cycling trainer` additionally maps to 8 cycling 0B exercises; `Assault bike`
-- carries a distinct upper-body component; `Spin bike` and `Stationary bike`
-- (upright) are leg-only and map to ZERO exercises.
--
-- Andy-ratified (2026-06-17; Trigger #2 vocab): fold `Spin bike` + `Stationary
-- bike` into `Cycling trainer`, keep `Assault bike` separate. This retires the
-- two from the picker so new athletes can't add them; `Cycling trainer` is the
-- canonical indoor-cycling entry going forward.
--
-- Scope = pure 0C equipment-vocab retirement. Unlike 0008 there is NO 0B
-- de-drift: a live read confirmed ZERO active exercises name `Spin bike` or
-- `Stationary bike` in equipment_required (the cascade's only consumer is the
-- INDOOR tuple, which reads the athlete's *saved* gear, not the vocab). So no
-- exercise rows change and no plan-gen cache needs bumping. Supersede-only;
-- history preserved (row-invalidation model).
--
-- Back-compat (deliberate, see #692): the `_DISCIPLINE_INDOOR_MACHINES` tuples
-- still list `Spin bike`/`Stationary bike`, so an athlete who *already* saved
-- one keeps indoor routing. Rewriting saved gym_profiles.equipment JSON
-- (`Spin/Stationary bike` -> `Cycling trainer`) is a separate, deploy-applied
-- public migration left as an optional follow-up; not needed for correctness.
--
-- Edit shape (README §"Two edit shapes"): equipment_items SERVING-RELEVANT
-- removal (changes the picker + the 2C effective-pool vocabulary). Supersede-
-- only; no 0B bump because nothing in 0B references these. In _LAYER0_TABLE_FAMILY
-- already — no family-map change. No public-schema DDL.
--
-- Idempotent: the supersede matches only still-active rows named below; a re-run
-- selects nothing (clean no-op).
--
-- Atomic: the verify DO block RAISEs (rolling back the txn) if either retired
-- item is left active, if `Cycling trainer`/`Assault bike` got caught by mistake,
-- or if any active exercise names a retired item in equipment_required.

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE _folded_bikes (name text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _folded_bikes (name) VALUES ('Spin bike'), ('Stationary bike');

-- ── (0C) Retire the two folded bikes from the equipment vocabulary ───────────
-- Supersede-only (history preserved). The picker filters superseded_at IS NULL,
-- so they vanish from it the moment this commits.
UPDATE layer0.equipment_items e
   SET superseded_at = now()
  FROM _folded_bikes b
 WHERE e.superseded_at IS NULL
   AND e.canonical_name = b.name;

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_left_active INT;
  v_kept        INT;
  v_ex_dirty    INT;
BEGIN
  -- Neither folded bike is still active in the vocabulary.
  SELECT count(*) INTO v_left_active
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN ('Spin bike', 'Stationary bike');
  IF v_left_active > 0 THEN
    RAISE EXCEPTION '0012: % folded bike(s) still active in equipment_items', v_left_active;
  END IF;

  -- The kept indoor bikes survive (guard against an over-broad match).
  SELECT count(*) INTO v_kept
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN ('Cycling trainer', 'Assault bike');
  IF v_kept <> 2 THEN
    RAISE EXCEPTION '0012: expected Cycling trainer + Assault bike to remain active, found %', v_kept;
  END IF;

  -- No active exercise hard-requires a folded bike (confirmed pre-migration;
  -- this guards against drift since the audit).
  SELECT count(*) INTO v_ex_dirty
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND equipment_required && ARRAY['Spin bike', 'Stationary bike'];
  IF v_ex_dirty > 0 THEN
    RAISE EXCEPTION '0012: % active exercise(s) name a folded bike in equipment_required — needs 0B de-drift', v_ex_dirty;
  END IF;

  RAISE NOTICE '0012: OK — Spin bike + Stationary bike retired from the picker; Cycling trainer + Assault bike kept';
END $$;

COMMIT;

-- End of 0012_retire_spin_stationary_bike.sql
