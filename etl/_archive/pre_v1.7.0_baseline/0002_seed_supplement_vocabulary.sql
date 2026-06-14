-- 0002_seed_supplement_vocabulary.sql
-- Epic #488 — bring layer0.supplement_vocabulary into the DB-native authoring
-- model (the migrations/gate loop), de-orphaning it from the ad-hoc
-- etl/sources/ one-shot SQL.
--
-- Why this exists: supplement_vocabulary is a *spec-sourced* Layer 0 table
-- (Supplement_Vocabulary_Spec.md), NOT emitted by the ETL, so it never appeared
-- in the genesis snapshot (etl/output/layer0_etl_v1.6.x.sql) and the layer0-gate
-- never saw it. Its DDL is now folded into etl/layer0/schema.sql (canonical
-- substrate); this migration carries the 25-row seed as a reviewed, gate-checked
-- DB-native edit.
--
-- Subsumes two legacy one-shots (both now historical):
--   * etl/sources/migrate_supplement_vocabulary.sql          (base CREATE + seed)
--   * etl/sources/migrate_supplement_vocab_contraindication_retag_v1.sql (D-21)
-- The contraindications[] below already carry the canonical §B tokens the retag
-- produced (bare system_category for conditions; rx:<medication_class> for meds;
-- allergen tokens dropped; pregnancy kept), so applying this migration reaches
-- the retag's end-state directly — on a fresh DB or on a prod DB that still
-- holds the pre-retag tokens.
--
-- Self-contained CREATE IF NOT EXISTS (mirrors schema.sql) so a standalone Neon
-- SQL-editor apply provisions the table without a separate schema step. Layer 2E
-- §5.5 matches these tokens DIRECTLY against §B health conditions / medications.
--
-- Idempotent: CREATE ... IF NOT EXISTS + ON CONFLICT (supplement_id) DO NOTHING.
-- Safe to re-run; no-op once applied.

BEGIN;

-- ── Schema (mirrors etl/layer0/schema.sql; no-op when already present) ───────

CREATE TABLE IF NOT EXISTS layer0.supplement_vocabulary (
  supplement_id            TEXT PRIMARY KEY,
  canonical_name           TEXT NOT NULL,
  alternative_names        TEXT[] DEFAULT '{}',
  category                 TEXT NOT NULL,
  primary_effect           TEXT NOT NULL,
  typical_dose             TEXT NOT NULL,
  timing_recommendations   TEXT[] NOT NULL,
  contraindications        TEXT[] DEFAULT '{}',
  evidence_quality         TEXT NOT NULL,
  notes                    TEXT,
  etl_version              TEXT NOT NULL,
  superseded_at            TIMESTAMP,
  CONSTRAINT supp_vocab_category_enum CHECK (
    category IN ('Performance', 'Recovery', 'Health', 'Race-day', 'GI', 'Sleep', 'Hormonal-Stress', 'Other')
  ),
  CONSTRAINT supp_vocab_evidence_enum CHECK (
    evidence_quality IN ('Strong', 'Moderate', 'Weak', 'Theoretical')
  )
);

CREATE INDEX IF NOT EXISTS idx_supplement_vocab_active
  ON layer0.supplement_vocabulary (supplement_id)
  WHERE superseded_at IS NULL;

-- ── Seed data (25 entries; canonical §B contraindication tokens) ─────────────

INSERT INTO layer0.supplement_vocabulary
  (supplement_id, canonical_name, category, primary_effect, typical_dose,
   timing_recommendations, contraindications, evidence_quality, notes, etl_version)
VALUES

  -- Performance ─────────────────────────────────────────────────────────────
  ('creatine_monohydrate', 'Creatine monohydrate', 'Performance',
   'Muscle creatine saturation; improves short-duration high-intensity output and total work capacity over volume sessions',
   '3–5 g/day (no loading needed for adherent athletes)',
   ARRAY['Variable','Morning','Post-workout'], ARRAY[]::TEXT[], 'Strong',
   'No on/off cycling needed once saturated. May cause initial water-weight gain (~1-2 kg).',
   'supp_vocab.v1.FC1'),

  ('beta_alanine', 'Beta-alanine', 'Performance',
   'Muscle carnosine precursor; buffers H+ in 30–120s high-intensity efforts',
   '3.2–6.4 g/day, divided',
   ARRAY['Variable'], ARRAY[]::TEXT[], 'Strong',
   'Causes paresthesia (tingling) at higher single doses. Split dosing recommended. Loading phase: 4–8 weeks for full effect.',
   'supp_vocab.v1.FC1'),

  ('beetroot_nitrate', 'Beetroot or nitrate supplement', 'Performance',
   'Nitric oxide production via dietary nitrate; vasodilation, improved O2 economy',
   '6–8 mmol nitrate (~500 mg)',
   ARRAY['Pre-workout'], ARRAY['rx:pde5_inhibitor'], 'Moderate',
   'Effect more pronounced in lower-trained athletes; elite endurance athletes see smaller gains. Pre-workout dose 2–3 hr before event.',
   'supp_vocab.v1.FC1'),

  ('caffeine', 'Caffeine (anhydrous, pill, gum, gel)', 'Performance',
   'Adenosine antagonist; ergogenic for endurance and high-intensity',
   '3–6 mg/kg body weight',
   ARRAY['Pre-workout','During workout'], ARRAY['cardiac','pregnancy'], 'Strong',
   'Cross-ref §I.1 Caffeine Tolerance & Strategy and §I.1.1 Race-day Caffeine Strategy — daily intake and race-day strategy are captured there. This vocabulary entry handles non-daily supplemental use (race-day pills/gels).',
   'supp_vocab.v1.FC1'),

  ('citrulline_malate', 'Citrulline malate', 'Performance',
   'NO precursor; muscle endurance support',
   '6–8 g',
   ARRAY['Pre-workout'], ARRAY[]::TEXT[], 'Moderate',
   'Better-absorbed than L-arginine for raising plasma arginine levels. Take 60 min before workout.',
   'supp_vocab.v1.FC1'),

  -- Recovery ────────────────────────────────────────────────────────────────
  ('whey_protein', 'Whey protein isolate or concentrate', 'Recovery',
   'Fast-absorbing protein for post-training MPS stimulation',
   '20–40 g',
   ARRAY['Post-workout','Morning'], ARRAY[]::TEXT[], 'Strong',
   'Concentrate has lactose; isolate is near-lactose-free.',
   'supp_vocab.v1.FC1'),

  ('casein_protein', 'Casein protein', 'Recovery',
   'Slow-release protein; supports overnight MPS',
   '20–40 g',
   ARRAY['Evening'], ARRAY[]::TEXT[], 'Moderate',
   'Often combined with magnesium for sleep support.',
   'supp_vocab.v1.FC1'),

  ('plant_protein', 'Plant protein blend (pea, rice, hemp)', 'Recovery',
   'Plant-based alternative to whey/casein',
   '25–45 g (higher dose due to lower DIAAS)',
   ARRAY['Post-workout','Morning','Evening'], ARRAY[]::TEXT[], 'Moderate',
   'DIAAS lower than animal sources; multi-source blends close the gap.',
   'supp_vocab.v1.FC1'),

  ('eaas', 'Essential amino acids (EAAs)', 'Recovery',
   'Full essential amino spectrum for MPS',
   '6–15 g',
   ARRAY['Pre-workout','During workout','Post-workout'], ARRAY[]::TEXT[], 'Moderate',
   'Generally preferred over BCAAs for MPS effect.',
   'supp_vocab.v1.FC1'),

  ('bcaas', 'Branched-chain amino acids (BCAAs)', 'Recovery',
   'Leucine/isoleucine/valine for MPS support',
   '5–10 g',
   ARRAY['Pre-workout','During workout'], ARRAY[]::TEXT[], 'Weak',
   'Limited additional benefit if total protein intake is adequate. EAAs preferred when supplementation is desired.',
   'supp_vocab.v1.FC1'),

  ('omega_3', 'Omega-3 (EPA/DHA)', 'Recovery',
   'Anti-inflammatory; joint, cognitive, cardiovascular support',
   '1–3 g EPA+DHA/day',
   ARRAY['Morning','Evening'], ARRAY['rx:anticoagulant'], 'Strong',
   'Fish-oil form more bioavailable than ALA (flax). Quality varies wildly by brand.',
   'supp_vocab.v1.FC1'),

  ('collagen', 'Hydrolyzed collagen + Vit C', 'Recovery',
   'Connective tissue (tendon, ligament) synthesis support',
   '10–15 g + 50 mg Vit C',
   ARRAY['Pre-workout'], ARRAY[]::TEXT[], 'Moderate',
   'Timing matters more than total daily intake. Pre-workout window (30 min before, especially before tendon-loading work) leverages bloodstream amino availability.',
   'supp_vocab.v1.FC1'),

  ('tart_cherry', 'Tart cherry juice or extract', 'Recovery',
   'Anti-inflammatory; possible sleep aid via melatonin content',
   '480 mg extract or 240 mL juice',
   ARRAY['Pre-workout','Evening'], ARRAY[]::TEXT[], 'Moderate',
   'May blunt training adaptations if used chronically — best for race week and recovery from key sessions.',
   'supp_vocab.v1.FC1'),

  ('curcumin', 'Curcumin (with piperine or liposomal)', 'Recovery',
   'Anti-inflammatory; possible DOMS reduction',
   '500–1500 mg curcuminoids',
   ARRAY['Evening','As-needed'], ARRAY['rx:anticoagulant'], 'Moderate',
   'Bioavailability is the major limitation — non-bioavailable forms have minimal effect. As-needed post heavy session.',
   'supp_vocab.v1.FC1'),

  -- Health ──────────────────────────────────────────────────────────────────
  ('magnesium', 'Magnesium (glycinate, citrate, malate)', 'Health',
   'Muscle/nerve function, sleep support; common deficiency in athletes',
   '200–400 mg',
   ARRAY['Evening'], ARRAY['gi_immune'], 'Moderate',
   'Glycinate is best-tolerated for sleep; citrate has laxative effect at high doses.',
   'supp_vocab.v1.FC1'),

  ('iron', 'Iron (ferrous sulfate, bisglycinate, etc.)', 'Health',
   'Red blood cell production; addresses common athlete iron deficiency',
   '18–65 mg elemental iron',
   ARRAY['Morning'], ARRAY['gi_immune','rx:thyroid_medication'], 'Strong',
   'Requires medical guidance — supplementation without serum ferritin testing risks overload. Morning dose away from coffee/tea. Often combined with Vit C for absorption. Separate from thyroid meds by 4hr.',
   'supp_vocab.v1.FC1'),

  ('vitamin_d', 'Vitamin D3', 'Health',
   'Bone density, immune function, athletic performance support',
   '1000–4000 IU/day',
   ARRAY['Morning'], ARRAY[]::TEXT[], 'Strong',
   'Serum 25(OH)D level should guide dosing. Target 30–50 ng/mL for athletes.',
   'supp_vocab.v1.FC1'),

  ('vitamin_b12', 'Vitamin B12', 'Health',
   'Energy metabolism, RBC formation; deficiency risk in plant-based diets',
   '250–1000 mcg/day or 1000–2500 mcg/week',
   ARRAY['Morning'], ARRAY[]::TEXT[], 'Strong',
   'Sublingual or injection forms have higher bioavailability than oral tablets.',
   'supp_vocab.v1.FC1'),

  ('multivitamin', 'Multivitamin (broad-spectrum)', 'Health',
   'Micronutrient insurance for inconsistent diet',
   '1 serving/day',
   ARRAY['Morning'], ARRAY[]::TEXT[], 'Weak',
   'Most athletes with varied diet don''t need this; useful for athletes with restrictive diets or high training loads.',
   'supp_vocab.v1.FC1'),

  -- Race-day ────────────────────────────────────────────────────────────────
  ('electrolyte_mix', 'Sodium/potassium/magnesium electrolyte mix', 'Race-day',
   'Hot-weather sodium replacement and cramp prevention',
   'Scaled to sweat loss; typical 300–1000 mg Na/hr',
   ARRAY['During workout','As-needed'], ARRAY['cardiac','endocrine','metabolic'], 'Strong',
   'Cross-ref §I.2 Salt/Electrolyte Tolerance. Cardiac contraindication applies to high-Na formulas; Endocrine/Metabolic applies to aldosterone disorders.',
   'supp_vocab.v1.FC1'),

  ('carb_powder', 'Carbohydrate powder (maltodextrin/fructose blend)', 'Race-day',
   'Race-day exogenous CHO; sustains blood glucose at intensity',
   '60–120 g/hr during effort',
   ARRAY['During workout'], ARRAY['gi_immune'], 'Strong',
   'Multi-transporter blends (maltodextrin + fructose at 2:1) tolerated up to ~120 g/hr. Single-source caps near 60 g/hr. High-concentration formulas can cause GI distress.',
   'supp_vocab.v1.FC1'),

  ('sodium_bicarbonate', 'Sodium bicarbonate', 'Race-day',
   'Extracellular H+ buffering; ergogenic for 1–7 min high-intensity efforts',
   '0.2–0.3 g/kg body weight',
   ARRAY['Pre-workout'], ARRAY['gi_immune','cardiac','endocrine','metabolic'], 'Strong',
   'GI distress is the limiting factor; new enteric-coated forms reduce risk. Test in training before race use. Take 60–90 min pre-workout. Effect is meaningful only in repeated high-intensity efforts, not long endurance.',
   'supp_vocab.v1.FC1'),

  -- GI ──────────────────────────────────────────────────────────────────────
  ('probiotics', 'Probiotics (multi-strain)', 'GI',
   'Gut microbiome support; useful for athletes with frequent GI issues',
   '10–100 billion CFU/day',
   ARRAY['Morning'], ARRAY[]::TEXT[], 'Moderate',
   'Strain-specific effects. Look for strains studied in athletes (Lactobacillus, Bifidobacterium).',
   'supp_vocab.v1.FC1'),

  -- Sleep ───────────────────────────────────────────────────────────────────
  ('melatonin', 'Melatonin', 'Sleep',
   'Circadian regulation, sleep-onset support',
   '0.3–3 mg',
   ARRAY['Evening'], ARRAY['rx:ssri','rx:beta_blocker','rx:diuretic'], 'Strong',
   'Take 30–60 min before sleep. Lower doses (0.3–1 mg) often as effective as higher; high doses can cause grogginess. Avoid chronic daily use without medical guidance.',
   'supp_vocab.v1.FC1'),

  -- Hormonal-Stress ─────────────────────────────────────────────────────────
  ('ashwagandha', 'Ashwagandha (KSM-66 or sensoril)', 'Hormonal-Stress',
   'Cortisol modulation, stress adaptation, possible sleep and recovery benefit',
   '300–600 mg/day',
   ARRAY['Morning','Evening'], ARRAY['rx:thyroid_medication','pregnancy'], 'Moderate',
   'Standardized extracts (KSM-66) have more research support than general extract. Effects most pronounced in stressed populations.',
   'supp_vocab.v1.FC1')

ON CONFLICT (supplement_id) DO NOTHING;

-- ── Verify ──────────────────────────────────────────────────────────────────

DO $$
DECLARE
  seed_ids TEXT[] := ARRAY[
    'creatine_monohydrate','beta_alanine','beetroot_nitrate','caffeine','citrulline_malate',
    'whey_protein','casein_protein','plant_protein','eaas','bcaas',
    'omega_3','collagen','tart_cherry','curcumin',
    'magnesium','iron','vitamin_d','vitamin_b12','multivitamin',
    'electrolyte_mix','carb_powder','sodium_bicarbonate',
    'probiotics','melatonin','ashwagandha'
  ];
  missing_ids TEXT[];
  active_count INT;
BEGIN
  -- Confirm all 25 seed IDs present and active.
  SELECT ARRAY_AGG(s)
    INTO missing_ids
    FROM UNNEST(seed_ids) AS s
    WHERE s NOT IN (
      SELECT supplement_id
        FROM layer0.supplement_vocabulary
        WHERE superseded_at IS NULL
    );

  IF missing_ids IS NOT NULL AND ARRAY_LENGTH(missing_ids, 1) > 0 THEN
    RAISE EXCEPTION '0002 verify failed — missing seed IDs: %', missing_ids;
  END IF;

  SELECT COUNT(*)
    INTO active_count
    FROM layer0.supplement_vocabulary
    WHERE superseded_at IS NULL;

  IF active_count < 25 THEN
    RAISE EXCEPTION '0002 verify failed — expected >= 25 active rows, got %', active_count;
  END IF;

  RAISE NOTICE '0002 verify OK — % active rows in layer0.supplement_vocabulary', active_count;
END $$;

COMMIT;
