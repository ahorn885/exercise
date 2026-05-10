-- migrate_gear_toggles_also_satisfies.sql
-- Adds also_satisfies TEXT[] to layer0.sport_specific_gear_toggles.
--
-- Why this field exists:
--   Some gear toggles imply other toggles via shared equipment. Example:
--   an athlete with full Climbing — roped setup (rope, harness, belay device,
--   carabiners, slings) also has everything required for Rappelling /
--   abseiling. Without an implication mechanism, athletes with roped climbing
--   kit would still see rappelling-gated exercises drop unless they
--   explicitly toggle Rappelling on — friction with no signal value.
--
--   Implication is one-way: roped → rappelling holds, but not the reverse
--   (an abseiling-only athlete may lack a belay device and lead-climb
--   experience). Layer 1 Node 2C's matcher checks each token classified as
--   a toggle token using:
--
--     classified_pass = G[T]
--                       OR EXISTS(t in toggles WHERE G[t] = TRUE
--                                                AND T = ANY(t.also_satisfies))
--
--   where G is the cluster gear-toggle state and T is the toggle token
--   appearing in exercises.equipment[].
--
-- Initial population scope (Batch A):
--   Climbing — roped → ['Rappelling / abseiling']
--   All other toggles remain NULL.
--
-- Out of scope for this migration:
--   Removal of the Bouldering toggle. Handled in populate_gear_toggles_batch_a.sql.
--
-- Data population:
--   Column added NULL-able. Existing rows have NULL until the populate
--   script runs. Companion script: populate_gear_toggles_batch_a.sql.
--
-- Pairs with: Vocab_Audit_v2_Batch_A_Patch.md §4.1.
--
-- Safe to re-run: ADD COLUMN IF NOT EXISTS.

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.sport_specific_gear_toggles
  ADD COLUMN IF NOT EXISTS also_satisfies TEXT[];

-- ── 2. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  col_exists BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'layer0'
      AND table_name   = 'sport_specific_gear_toggles'
      AND column_name  = 'also_satisfies'
  ) INTO col_exists;

  IF NOT col_exists THEN
    RAISE EXCEPTION 'migrate_gear_toggles_also_satisfies: column also_satisfies not added';
  END IF;

  RAISE NOTICE 'migrate_gear_toggles_also_satisfies: OK — also_satisfies column present on sport_specific_gear_toggles';
END $$;

COMMIT;
