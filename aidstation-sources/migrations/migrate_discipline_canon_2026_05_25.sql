-- migrate_discipline_canon_2026_05_25.sql
-- Discipline canon — single source of truth for discipline ids + names.
-- Pairs with etl/layer0/discipline_canon.py (the ETL-time normalizer).
--
-- WHAT THE CANON DOES (decisions: Andy, May 2026):
--   * 25 surviving disciplines, one clean craft name each.
--   * Merge D-005 (Pool Sprint Swimming) + D-016 (Swimming) -> D-004 "Swimming".
--   * Remove D-020 (Swimrun -> reclassified as a *sport* = swim + run) and
--     D-023 (Ski Transitions / Boot-packing -> not tracked).
--   * Split composite keys "D-006 + D-007" and "D-010 + D-011" into atomic rows.
--   * Drop orphans: "D-014 (Ref)" Technical Scrambling, "Portage Running".
--   * Non-discipline phase-load rows (Strength / Mobility / Weekly Total) get
--     discipline_id = NULL + a row_category, instead of a placeholder "-"/"—".
--   * Name corrections vs the old display overlay: D-021 "Uphill Skinning"
--     (was "Ski Touring"), D-022 "Alpine Descent" (was "Alpine Skiing").
--
-- ─────────────────────────────────────────────────────────────────────────
-- RUNBOOK
-- ─────────────────────────────────────────────────────────────────────────
-- This layer0 store is ETL-versioned: re-running the loader inserts a new
-- etl_version and supersedes the prior one. The canon is applied *by the ETL*
-- (etl/layer0/discipline_canon.py). So the data fix is:
--
--   1. Run THIS migration (adds the row_category column required by the new
--      phase_load_allocation insert).
--   2. Re-run the loader:  python -m etl.layer0.run
--      -> regenerates every discipline-bearing table under the canon
--         (renames, the D-004 merge, composite splits, non-discipline
--          categories, pairing/substitute cleanup) and supersedes the old rows.
--
-- In-place renames are deliberately NOT done here: phase_load_allocation is
-- UNIQUE(sport_name, discipline_name, etl_version), so collapsing variant names
-- to canon in place can collide. The ETL re-run de-dupes correctly. PART 2
-- below is an OPTIONAL, abort-proof retire of the rows the canon drops, for
-- environments that want the stale rows gone before the re-run. It only ever
-- sets superseded_at (never touches a unique key), so it cannot abort.

BEGIN;

-- ─── PART 1 — schema (required before the next ETL run) ──────────────────────
ALTER TABLE layer0.phase_load_allocation
    ADD COLUMN IF NOT EXISTS row_category TEXT;

-- ─── PART 2 — OPTIONAL safe retire of canon-dropped rows ─────────────────────
-- Comment PART 2 out if you will re-run the ETL immediately (the re-run
-- supersedes the whole prior etl_version anyway). Pair with the re-run: it does
-- not repopulate (e.g. merged swim legs), so don't leave the DB in this state.

-- Removed disciplines (D-020 Swimrun, D-023 Ski Transitions) + merged-away swim
-- ids (D-005, D-016) — retired across the dimension and the denorm tables.
UPDATE layer0.disciplines              SET superseded_at = now()
 WHERE discipline_id IN ('D-005','D-016','D-020','D-023') AND superseded_at IS NULL;

UPDATE layer0.sport_discipline_map     SET superseded_at = now()
 WHERE discipline_id IN ('D-005','D-016','D-020','D-023') AND superseded_at IS NULL;

UPDATE layer0.sport_discipline_bridge  SET superseded_at = now()
 WHERE discipline_id IN ('D-005','D-016','D-020','D-023') AND superseded_at IS NULL;

UPDATE layer0.phase_load_allocation    SET superseded_at = now()
 WHERE discipline_id IN ('D-005','D-016','D-020','D-023') AND superseded_at IS NULL;

UPDATE layer0.discipline_training_gaps SET superseded_at = now()
 WHERE discipline_id IN ('D-005','D-016','D-020','D-023') AND superseded_at IS NULL;

UPDATE layer0.discipline_substitutes   SET superseded_at = now()
 WHERE (target_id     IN ('D-005','D-016','D-020','D-023')
     OR substitute_id IN ('D-005','D-016','D-020','D-023'))
   AND superseded_at IS NULL;

-- Composite keys (split into atomic rows by the ETL re-run).
UPDATE layer0.sport_discipline_map     SET superseded_at = now()
 WHERE discipline_id IN ('D-006 + D-007','D-010 + D-011') AND superseded_at IS NULL;
UPDATE layer0.phase_load_allocation    SET superseded_at = now()
 WHERE discipline_id IN ('D-006 + D-007','D-010 + D-011') AND superseded_at IS NULL;

-- Orphans: pseudo-id "D-014 (Ref)" (Technical Scrambling) and "Portage Running"
-- (parked under a dash id). Matched defensively by id and by name.
UPDATE layer0.sport_discipline_map     SET superseded_at = now()
 WHERE (discipline_id = 'D-014 (Ref)' OR discipline_name ILIKE 'Technical Scrambling%'
        OR discipline_name ILIKE 'Portage Running%')
   AND superseded_at IS NULL;
UPDATE layer0.phase_load_allocation    SET superseded_at = now()
 WHERE discipline_name ILIKE 'Portage Running%'
   AND superseded_at IS NULL;

-- discipline_pairing: retire any pair touching a removed/merged id; the ETL
-- re-run rebuilds the matrix canonically (remaps survive, self-pairs dropped).
UPDATE layer0.discipline_pairing       SET superseded_at = now()
 WHERE (discipline_id_a IN ('D-005','D-016','D-020','D-023')
     OR discipline_id_b IN ('D-005','D-016','D-020','D-023'))
   AND superseded_at IS NULL;

COMMIT;
