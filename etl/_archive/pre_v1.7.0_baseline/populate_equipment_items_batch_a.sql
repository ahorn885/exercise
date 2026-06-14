-- populate_equipment_items_batch_a.sql
-- Adds canonical entry: Bench press rack
-- Source: Vocab_Audit_v2_Batch_A_Patch.md §3 Machines — Upper Body.
-- Driver: Layer 1 Node 2C (Equipment Mapper) design session — EX229 Bench
--   Press needs to accept either a Squat rack + Bench combo or a
--   Bench press station, depending on what the athlete's locale has.
--
-- Why distinct from Squat rack:
--   Bench press rack is a fixed flat-bench station with integrated bench,
--   typical in hotel and apartment gyms. Squat rack is a vertical rack
--   or cage that supports squats AND can host bench press if a separate
--   Bench item is placed inside it. The two are not interchangeable in
--   general (you can't squat in most flat bench stations), but for the
--   bench press exercise specifically, either works. EX229 will encode
--   this via equipment_substitutes_structured (Tier 2 substitute path).
--
-- etl_version: '0C-v2.0-r3' — Vocab Audit r3 (Batch A)
--   r2 was the terrain_types extension; r3 is this Batch A vocab patch.
--
-- Idempotent: ON CONFLICT (canonical_name, etl_version) DO NOTHING.
--   Targets the documented unique constraint on layer0.equipment_items
--   (per Layer0_ETL_Spec §4.12 / v2 schema). Do NOT change this to
--   ON CONFLICT (canonical_name) — there is no single-column unique
--   constraint on canonical_name; Postgres rejects at parse time.
--   This is the same footgun that hit K1 (commit ac390c4) and K2
--   (commit 0aee877) and was patched in both before they ran.

BEGIN;

INSERT INTO layer0.equipment_items
  (canonical_name, equipment_category, is_universal, notes, etl_version, etl_run_at)
VALUES

  ('Bench press rack',
   'Machines — Upper Body', FALSE,
   'Fixed flat-bench station with integrated bench. Distinct from Squat rack (vertical rack/cage that requires a separate Bench item placed inside it). Common in hotel and apartment gyms. For Bench Press (EX229), interchangeable with Squat rack + Bench combo via equipment_substitutes_structured.',
   '0C-v2.0-r3', NOW())

ON CONFLICT (canonical_name, etl_version) DO NOTHING;

-- ── Verify ──────────────────────────────────────────────────────────────────

DO $$
DECLARE
  bench_rack_active INT;
BEGIN
  SELECT COUNT(*)
    INTO bench_rack_active
    FROM layer0.equipment_items
    WHERE canonical_name = 'Bench press rack'
      AND superseded_at IS NULL;

  IF bench_rack_active = 0 THEN
    RAISE EXCEPTION 'populate_equipment_items_batch_a: Bench press rack not present after insert';
  END IF;

  RAISE NOTICE 'populate_equipment_items_batch_a: OK — Bench press rack canonical item present (active rows: %)', bench_rack_active;
END $$;

COMMIT;
