-- migrate_exercises_substitutes_structured.sql
-- Adds equipment_substitutes_structured JSONB to layer0.exercises.
--
-- Why this field exists:
--   The original equipment_substitutes_standard[] and
--   equipment_substitutes_improvised[] columns store free-text substitute
--   descriptions (e.g., "DB Romanian Deadlift", "Trap Bar Deadlift",
--   "🏠 Backpack loaded with books or water"). Free text cannot support
--   structured Tier 2 resolution at Layer 1 Node 2C — there's no way to
--   programmatically check whether a substitute's equipment is in the
--   athlete's pool.
--
--   This new field stores parsed substitutes as structured JSONB:
--     [
--       {
--         "substitute_text":     "DB Romanian Deadlift",
--         "equipment_required":  ["Dumbbell"],
--         "is_improvised":       false
--       },
--       {
--         "substitute_text":     "Backpack loaded with books or water...",
--         "equipment_required":  [],
--         "is_improvised":       true
--       }
--     ]
--
-- 2C contract (using this field):
--   For each exercise where Tier 1 fails, iterate equipment_substitutes_structured.
--   For each substitute:
--     - If is_improvised=true → assumed available (athletes have household items).
--     - Else if equipment_required ⊆ athlete's available pool → available.
--   Pick first matching substitute. Tier 2 result references the specific
--   substitute_text so Layer 4 can prescribe the named variant.
--
-- Data population:
--   Column added NULL-able. Existing rows have NULL until populate script runs.
--   Companion script: populate_substitutes_structured.py — reads
--   parsed_substitutes.json (parser output, 154 exercises × 510 entries)
--   and updates active rows in place.
--
-- Old fields retained:
--   equipment_substitutes_standard[] and equipment_substitutes_improvised[]
--   stay as reference data. They are no longer the source of truth for 2C —
--   equipment_substitutes_structured is. Migration is additive, not destructive.
--
-- Safe to re-run: ADD COLUMN IF NOT EXISTS.

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.exercises
  ADD COLUMN IF NOT EXISTS equipment_substitutes_structured JSONB;

-- ── 2. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  col_exists BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'layer0'
      AND table_name   = 'exercises'
      AND column_name  = 'equipment_substitutes_structured'
  ) INTO col_exists;

  IF NOT col_exists THEN
    RAISE EXCEPTION 'migrate_exercises_substitutes_structured: column not found';
  END IF;

  RAISE NOTICE 'migrate_exercises_substitutes_structured: OK — column added';
END $$;

COMMIT;
