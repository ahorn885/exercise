-- 0031_retag_supplement_contraindications_canonical.sql
--
-- #255 — system_category canonical retag (8 → 11). Layer 2E supplement
-- screening matches an athlete's active health-condition `system_category`
-- directly against a supplement's `contraindications` tokens
-- (`layer2e/builder.py` `_contraindication_hits`: `elif token in
-- active_categories`). The athlete-side enum moves to the canonical 11-value
-- set (`athlete.KNOWN_SYSTEM_CATEGORIES`), so the supplement-vocab tokens must
-- move with it or those supplements silently stop screening.
--
-- Token remap (the same fold applied to the app enum):
--   gi_immune  → gi                  (these are GI-DISTRESS contraindications —
--                                      magnesium/carb_powder/iron/sodium_bicarb
--                                      are gut-tolerance risks, not autoimmune;
--                                      mapping to immune_autoimmune too would
--                                      falsely auto-remove them for RA/lupus/MCAS
--                                      athletes)
--   endocrine  → endocrine_metabolic
--   metabolic  → endocrine_metabolic
--   cardiac / pregnancy / rx:<class> → unchanged
--
-- Affected active rows (v1.9.0 baseline): magnesium {gi_immune}→{gi},
-- carb_powder {gi_immune}→{gi}, iron {gi_immune,rx:thyroid_medication}→
-- {gi,rx:thyroid_medication}, electrolyte_mix {cardiac,endocrine,metabolic}→
-- {cardiac,endocrine_metabolic}, sodium_bicarbonate
-- {gi_immune,cardiac,endocrine,metabolic}→{gi,cardiac,endocrine_metabolic}.
-- caffeine {cardiac,pregnancy} and ashwagandha {rx:thyroid_medication,pregnancy}
-- are untouched (no legacy tokens).
--
-- Edit shape: in-place UPDATE, not supersede+reinsert. The PK is
-- `supplement_id` alone, so a same-id history row is impossible; and
-- supplement_vocabulary is a *standing exception* to the per-table
-- cache-invalidation digest (`TestLayer0TableFamilyMap` _FAMILY_MAP_EXCEPTIONS:
-- "Layer 2E reads active rows live, so its edits serve without a cache-key
-- dependency"). So no version bump and no superseding is owed — the active row
-- is corrected in place and serves immediately.
--
-- Idempotent: the `&&` guard excludes rows already free of legacy tokens, so a
-- re-apply (incl. on a future re-dumped baseline) selects nothing.

BEGIN;

UPDATE layer0.supplement_vocabulary AS s
   SET contraindications = ARRAY(
         SELECT DISTINCT
                CASE elem
                    WHEN 'gi_immune' THEN 'gi'
                    WHEN 'endocrine' THEN 'endocrine_metabolic'
                    WHEN 'metabolic' THEN 'endocrine_metabolic'
                    ELSE elem
                END
           FROM unnest(s.contraindications) AS elem
          ORDER BY 1
       )
 WHERE s.superseded_at IS NULL
   AND s.contraindications && ARRAY['gi_immune', 'endocrine', 'metabolic'];

DO $$
DECLARE
    leftover int;
BEGIN
    SELECT count(*) INTO leftover
      FROM layer0.supplement_vocabulary
     WHERE superseded_at IS NULL
       AND contraindications && ARRAY['gi_immune', 'endocrine', 'metabolic'];
    IF leftover <> 0 THEN
        RAISE EXCEPTION '0031: % active supplement row(s) still carry a legacy contraindication token', leftover;
    END IF;
    RAISE NOTICE '0031: supplement contraindications retagged to canonical system_category vocab (#255)';
END $$;

COMMIT;
