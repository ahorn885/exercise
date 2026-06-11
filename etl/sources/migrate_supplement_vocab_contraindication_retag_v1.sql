-- migrate_supplement_vocab_contraindication_retag_v1.sql
-- D-21: re-tag layer0.supplement_vocabulary.contraindications to canonical §B
-- enum tokens so Layer 2E §5.5 matches them DIRECTLY (no in-app mapping layer).
--   condition tokens  -> athlete.KNOWN_SYSTEM_CATEGORIES (bare)
--   medication tokens -> rx:<medication_class> (KNOWN_MEDICATION_CLASSES,
--                        incl. the new thyroid_medication / pde5_inhibitor)
--   allergen tokens   -> dropped entirely (no food-allergy capture)
--   pregnancy         -> kept (Layer 2E defers it to #518)
--
-- Idempotent: array_replace / array_remove are no-ops once applied; the two
-- fan-out UPDATEs are guarded on the legacy token's presence so a second run
-- can't double-append. Safe to run multiple times.
--
-- OWED (Andy's hands): apply on Neon — DB egress is blocked from the container.
-- Until applied, the live vocab still carries the legacy tokens and Layer 2E's
-- direct match finds nothing (contraindication screening inert on prod).

BEGIN;

-- ── Condition tokens -> §B system_category ──────────────────────────────────
UPDATE layer0.supplement_vocabulary
   SET contraindications = array_replace(contraindications, 'Cardiac', 'cardiac')
 WHERE 'Cardiac' = ANY(contraindications);

UPDATE layer0.supplement_vocabulary
   SET contraindications = array_replace(contraindications, 'GI', 'gi_immune')
 WHERE 'GI' = ANY(contraindications);

-- Endocrine/Metabolic was one token; §B splits it into two categories.
UPDATE layer0.supplement_vocabulary
   SET contraindications =
       array_remove(contraindications, 'Endocrine/Metabolic')
       || ARRAY['endocrine', 'metabolic']
 WHERE 'Endocrine/Metabolic' = ANY(contraindications);

-- ── Medication tokens -> rx:<medication_class> ──────────────────────────────
-- rx:anticoagulant already matches §B 'anticoagulant' — left as-is.
UPDATE layer0.supplement_vocabulary
   SET contraindications = array_replace(contraindications, 'rx:PDE5-inhibitors', 'rx:pde5_inhibitor')
 WHERE 'rx:PDE5-inhibitors' = ANY(contraindications);

UPDATE layer0.supplement_vocabulary
   SET contraindications = array_replace(contraindications, 'rx:SSRIs', 'rx:ssri')
 WHERE 'rx:SSRIs' = ANY(contraindications);

UPDATE layer0.supplement_vocabulary
   SET contraindications = array_replace(contraindications, 'rx:thyroid medications', 'rx:thyroid_medication')
 WHERE 'rx:thyroid medications' = ANY(contraindications);

-- Blood-pressure meds fan out to the two §B BP-relevant classes.
UPDATE layer0.supplement_vocabulary
   SET contraindications =
       array_remove(contraindications, 'rx:blood-pressure medications')
       || ARRAY['rx:beta_blocker', 'rx:diuretic']
 WHERE 'rx:blood-pressure medications' = ANY(contraindications);

-- ── Drop allergen tokens (no food-allergy capture) ──────────────────────────
UPDATE layer0.supplement_vocabulary
   SET contraindications = array_remove(contraindications, 'allergen:dairy')
 WHERE 'allergen:dairy' = ANY(contraindications);

COMMIT;
