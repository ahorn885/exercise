-- 0022_unify_gear_toggle_catalog.sql
--
-- #884 (unified gear/craft model) — slice 1, "catalog shape only". Reshape the
-- `layer0.sport_specific_gear_toggles` vocabulary into the canonical gear set
-- the unified model is built around, and de-drift the two active exercises that
-- gate on a renamed toggle so no reference dangles. This migration deliberately
-- does NOT touch the alias table, the fidelity_rank column, gear alias rows, or
-- any NEW gated_discipline_ids wiring — those cluster with the gear consumer +
-- the athlete-gear store in a later slice (and per-discipline gating only
-- becomes real once a store exists to turn the toggles ON; wiring it now would
-- emit spurious "toggle off" coaching flags for every gear discipline, since
-- both 2C call sites still pass `cluster_gear_toggle_states={}`). Scope ratified
-- by Andy via AskUserQuestion (2026-06-23): "Catalog shape only (safe)".
--
-- ── (0C) Toggle catalog — three shape edits (active set 12 -> 6 rows) ─────────
--   1. DELETE four orphan toggles that gate nothing and belong to no modelled
--      sport in scope — Bouldering, Whitewater paddling setup, Fencing setup,
--      Shooting setup. (Supersede-only; each carries gated_discipline_ids = {},
--      also_satisfies = {}, paired_equipment_categories = {}, so removing them
--      changes no served 2C output — `_load_toggle_defs` just returns fewer
--      keys and the gating/pool loops never reference them. No active exercise
--      gates on any of the four.)
--   2. ROLL UP the three roped-climbing toggles into one "Climbing gear":
--      Climbing — roped (gated D-012 Rock Climbing, also_satisfies the now-gone
--      'Rappelling / abseiling'), Rappelling / abseiling (gated D-013 Abseiling)
--      and Via ferrata (gated nothing) collapse into a single toggle gating
--      {D-012, D-013, D-014 (Via Ferrata)} directly. also_satisfies drops to {}
--      — the multi-row gate subsumes the one-hop alias and it no longer dangles
--      to a deleted toggle name.
--   3. RENAME "Touring/AT ski setup" -> "Skimo / AT setup" (the label the
--      unified model standardises on; the existing row already covers SkiMo
--      gear in its description). Gating stays {} (no new wiring this slice).
-- Survivors, untouched: Classic XC ski setup, Skate XC ski setup, Mountaineering,
-- Snowshoeing setup (keeps its D-017 gate).
--
-- ── (0B) De-drift the two exercises that gate on a renamed toggle ─────────────
-- A toggle name in an exercise's equipment_required (or a structured
-- substitute's equipment_required) is the tier-1 gear gate — the same shape
-- 0007/0008 de-drifted for vessels/assumed gear. Two ACTIVE exercises reference
-- a toggle this migration renames (0017/0021 already culled the rest):
--   * EX170 "SkiMo Race Transition Drill" — equipment_required {Touring/AT ski
--     setup} -> {Skimo / AT setup}.
--   * EX101 "Hangboard Open-Hand Hold" — a structured substitute ("Climbing
--     holds mounted on wall") requires [["Climbing — roped"]] -> [["Climbing
--     gear"]].
-- Behaviour-neutral today (both gate on a toggle that is never enabled — 2C
-- passes states={} — so feasibility is unchanged either way), but it keeps the
-- gear->exercise linkage intact for the future enable path. Leaving it would
-- silently sever EX170/EX101 from their gear when the store lands.
--
-- ── Edit shape (README §"Two edit shapes") ───────────────────────────────────
-- SERVING-RELEVANT on both families, so the changed rows carry a bumped
-- per-table version and the family digests advance (caches invalidate):
--   * 0C: the two re-inserted toggles ("Climbing gear", "Skimo / AT setup") land
--     at 0C-v1.6.8 (current active toggles are all 0C-v1.6.7). The four orphan
--     deletions are cache-neutral alone but ride the same digest bump.
--   * 0B: the two de-drifted exercises land at 0B-v1.6.19 (current 0B numeric
--     max active is 0B-v1.6.18; `_max_etl_version` compares integer tuples).
-- `sport_specific_gear_toggles` and `exercises` are both already in
-- `_LAYER0_TABLE_FAMILY` — no family-map change, no public-schema DDL.
--
-- Idempotent: every supersede is guarded to still-active rows; each re-insert is
-- guarded so a re-run (where the target name/version is already present)
-- selects nothing — clean no-op, no UNIQUE(exercise_id, etl_version) collision.
--
-- Atomic: the verify DO block RAISEs (rolling back the whole txn) if any removed
-- name is left active, the rolled-up/renamed toggles are missing or mis-gated,
-- the active toggle set is not the expected 6, or either de-drifted exercise
-- still references an old toggle name.

\set ON_ERROR_STOP on

BEGIN;

-- ── Removed toggle names (orphans + roll-up sources + rename source) ─────────
CREATE TEMP TABLE _retired_toggles (toggle_name text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _retired_toggles (toggle_name) VALUES
  -- orphans (gate nothing; out of modelled scope)
  ('Bouldering'),
  ('Whitewater paddling setup'),
  ('Fencing setup'),
  ('Shooting setup'),
  -- climbing roll-up sources (folded into 'Climbing gear')
  ('Climbing — roped'),
  ('Rappelling / abseiling'),
  ('Via ferrata'),
  -- rename source (-> 'Skimo / AT setup')
  ('Touring/AT ski setup');

-- ── (0C) Supersede every removed/superseded source row (history preserved) ───
UPDATE layer0.sport_specific_gear_toggles t
   SET superseded_at = now()
  FROM _retired_toggles r
 WHERE t.superseded_at IS NULL
   AND t.toggle_name = r.toggle_name;

-- ── (0C) Roll up: one "Climbing gear" toggle gating {D-012, D-013, D-014} ────
INSERT INTO layer0.sport_specific_gear_toggles
  (toggle_name, display_label, description,
   paired_equipment_categories, also_satisfies, gated_discipline_ids,
   etl_version, etl_run_at)
SELECT
  'Climbing gear', 'Climbing gear',
  'Climbing rope, Harness, Belay/rappel device, Carabiners, Slings, '
    || 'Anchor hardware, Quickdraws, Via ferrata Y-lanyard, Helmet (climbing)',
  '{}'::text[], '{}'::text[], ARRAY['D-012', 'D-013', 'D-014'],
  '0C-v1.6.8', now()
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_specific_gear_toggles a
   WHERE a.superseded_at IS NULL AND a.toggle_name = 'Climbing gear'
);

-- ── (0C) Rename: "Touring/AT ski setup" -> "Skimo / AT setup" ────────────────
INSERT INTO layer0.sport_specific_gear_toggles
  (toggle_name, display_label, description,
   paired_equipment_categories, also_satisfies, gated_discipline_ids,
   etl_version, etl_run_at)
SELECT
  'Skimo / AT setup', 'Skimo / AT setup',
  'Touring skis, Alpine skis, Ski boots (touring), Ski poles, Climbing skins, '
    || 'Ski crampons, Boot buckles, Touring binding, '
    || 'Mountaineering harness (when used in SkiMo), Ice axe (when used in SkiMo)',
  '{}'::text[], '{}'::text[], '{}'::text[],
  '0C-v1.6.8', now()
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_specific_gear_toggles a
   WHERE a.superseded_at IS NULL AND a.toggle_name = 'Skimo / AT setup'
);

-- ── (0B) De-drift EX170 + EX101 onto the renamed toggles ─────────────────────
-- Re-insert each at the bumped version with the toggle reference rewritten; the
-- array_replace / structured-text replace only affects the row that holds the
-- token (a no-op on the other), so applying both edits to both rows is safe.
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
  array_replace(e.equipment_required, 'Touring/AT ski setup', 'Skimo / AT setup'),
  e.injury_flags_text, e.contraindicated_parts,
  e.contraindicated_conditions, e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name, e.regression_exercise_id,
  e.regression_exercise_name, e.sport_count, e.coaching_cues,
  '0B-v1.6.19', now(), e.terrain_required,
  replace(e.equipment_substitutes_structured::text, 'Climbing — roped', 'Climbing gear')::jsonb,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.exercise_id IN ('EX170', 'EX101')
  AND e.etl_version <> '0B-v1.6.19';

-- Supersede the pre-de-drift rows now replaced (the new rows are at 0B-v1.6.19).
UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.exercise_id IN ('EX170', 'EX101')
   AND e.etl_version <> '0B-v1.6.19';

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_left_active INT;
  v_climb_gate  TEXT[];
  v_skimo       INT;
  v_active      INT;
  v_survivors   INT;
  v_ex_dirty    INT;
  v_ex170       INT;
  v_ex101       INT;
BEGIN
  -- 0C: no removed/source toggle name is still active.
  SELECT count(*) INTO v_left_active
    FROM layer0.sport_specific_gear_toggles
   WHERE superseded_at IS NULL
     AND toggle_name IN (SELECT toggle_name FROM _retired_toggles);
  IF v_left_active > 0 THEN
    RAISE EXCEPTION '0022: % retired/source toggle(s) still active', v_left_active;
  END IF;

  -- 0C: "Climbing gear" active and gating exactly {D-012, D-013, D-014}.
  SELECT gated_discipline_ids INTO v_climb_gate
    FROM layer0.sport_specific_gear_toggles
   WHERE superseded_at IS NULL AND toggle_name = 'Climbing gear';
  IF v_climb_gate IS NULL THEN
    RAISE EXCEPTION '0022: rolled-up "Climbing gear" toggle missing';
  END IF;
  IF NOT (v_climb_gate @> ARRAY['D-012','D-013','D-014']
          AND array_length(v_climb_gate, 1) = 3) THEN
    RAISE EXCEPTION '0022: "Climbing gear" gates % (expected D-012,D-013,D-014)', v_climb_gate;
  END IF;

  -- 0C: "Skimo / AT setup" active (rename source already asserted gone above).
  SELECT count(*) INTO v_skimo
    FROM layer0.sport_specific_gear_toggles
   WHERE superseded_at IS NULL AND toggle_name = 'Skimo / AT setup';
  IF v_skimo <> 1 THEN
    RAISE EXCEPTION '0022: expected 1 active "Skimo / AT setup", found %', v_skimo;
  END IF;

  -- 0C: exactly 6 active toggles remain.
  SELECT count(*) INTO v_active
    FROM layer0.sport_specific_gear_toggles WHERE superseded_at IS NULL;
  IF v_active <> 6 THEN
    RAISE EXCEPTION '0022: expected 6 active toggles, found %', v_active;
  END IF;

  -- 0C: survivors untouched (Snowshoeing keeps its D-017 gate).
  SELECT count(*) INTO v_survivors
    FROM (VALUES
      ('Classic XC ski setup'),
      ('Skate XC ski setup'),
      ('Mountaineering'),
      ('Snowshoeing setup')
    ) s(toggle_name)
   WHERE EXISTS (
     SELECT 1 FROM layer0.sport_specific_gear_toggles t
      WHERE t.superseded_at IS NULL AND t.toggle_name = s.toggle_name
   );
  IF v_survivors <> 4 THEN
    RAISE EXCEPTION '0022: expected 4 untouched survivor toggles, found %', v_survivors;
  END IF;

  -- 0B: no active exercise still references a renamed toggle name anywhere a
  -- gate is read (equipment_required or a structured substitute).
  SELECT count(*) INTO v_ex_dirty
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND ('Touring/AT ski setup' = ANY(equipment_required)
          OR 'Climbing — roped' = ANY(equipment_required)
          OR equipment_substitutes_structured::text LIKE '%Touring/AT ski setup%'
          OR equipment_substitutes_structured::text LIKE '%Climbing — roped%');
  IF v_ex_dirty > 0 THEN
    RAISE EXCEPTION '0022: % active exercise(s) still reference a renamed toggle name', v_ex_dirty;
  END IF;

  -- 0B: EX170 de-drifted onto the new ski toggle.
  SELECT count(*) INTO v_ex170
    FROM layer0.exercises
   WHERE superseded_at IS NULL AND exercise_id = 'EX170'
     AND 'Skimo / AT setup' = ANY(equipment_required);
  IF v_ex170 <> 1 THEN
    RAISE EXCEPTION '0022: EX170 not gated on "Skimo / AT setup" (found %)', v_ex170;
  END IF;

  -- 0B: EX101's structured substitute de-drifted onto "Climbing gear".
  SELECT count(*) INTO v_ex101
    FROM layer0.exercises
   WHERE superseded_at IS NULL AND exercise_id = 'EX101'
     AND equipment_substitutes_structured::text LIKE '%Climbing gear%';
  IF v_ex101 <> 1 THEN
    RAISE EXCEPTION '0022: EX101 structured substitute not de-drifted to "Climbing gear" (found %)', v_ex101;
  END IF;

  RAISE NOTICE '0022: OK — gear toggle catalog reshaped to 6 (4 orphans dropped, climbing rolled up, Touring/AT -> Skimo / AT setup); EX170/EX101 de-drifted';
END $$;

COMMIT;

-- End of 0022_unify_gear_toggle_catalog.sql
