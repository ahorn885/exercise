# Layer 0 — `supplement_vocabulary` Table Spec

**Status:** Draft 2026-05-10, slated for FC-1 implementation (tracked as D-26 in `Project_Backlog.md`).
**Type:** Layer 0 vocabulary / reference table.
**Purpose:** Structured canonical list of supplements commonly used by endurance athletes, with effect, timing, dosing, and contraindication metadata. Replaces the free-text "Current Supplement Protocol" field in onboarding §I.1, enabling 2E and Layer 4 to perform set-intersect lookups instead of LLM interpretation of athlete-entered text.

---

## 1. Schema

```sql
CREATE TABLE layer0.supplement_vocabulary (
  supplement_id            TEXT PRIMARY KEY,            -- slug, e.g., 'creatine_monohydrate'
  canonical_name           TEXT NOT NULL,
  alternative_names        TEXT[] DEFAULT '{}',         -- common alternate spellings / brand-class names for fuzzy match
  category                 TEXT NOT NULL,               -- enum below
  primary_effect           TEXT NOT NULL,               -- short summary, ≤200 chars
  typical_dose             TEXT NOT NULL,               -- includes range and unit, e.g., "3-5 g/day"
  timing_recommendations   TEXT[] NOT NULL,             -- multi-select from timing enum
  contraindications        TEXT[] DEFAULT '{}',         -- cross-ref to health_condition_categories or named allergens
  evidence_quality         TEXT NOT NULL,               -- enum: Strong / Moderate / Weak / Theoretical
  notes                    TEXT,                        -- caveats, interactions, GI risk, etc.
  etl_version              TEXT NOT NULL,
  superseded_at            TIMESTAMP,
  CONSTRAINT category_enum CHECK (
    category IN ('Performance', 'Recovery', 'Health', 'Race-day', 'GI', 'Sleep', 'Hormonal-Stress', 'Other')
  ),
  CONSTRAINT evidence_enum CHECK (
    evidence_quality IN ('Strong', 'Moderate', 'Weak', 'Theoretical')
  )
);

CREATE INDEX idx_supplement_vocab_active ON layer0.supplement_vocabulary (supplement_id)
  WHERE superseded_at IS NULL;
```

### Enum: `category`

| Value | Meaning | Examples |
|---|---|---|
| Performance | Direct performance-effect supplements | Creatine, Beta-alanine, Beetroot/Nitrate, Caffeine |
| Recovery | Post-training adaptation/recovery support | Whey, Casein, Tart cherry, Omega-3 |
| Health | General/medical maintenance | Iron, Vit D, Multivitamin, Vit B12 |
| Race-day | Race-day-only protocols | Sodium bicarbonate, Carbohydrate powder |
| GI | Gut/digestive support | Probiotics |
| Sleep | Sleep-related | Melatonin, Magnesium (for sleep) |
| Hormonal-Stress | Stress/HPA modulation | Adaptogens (ashwagandha, rhodiola) |
| Other | Catch-all for vocab evolution | Athlete-flagged free-text entries |

### Enum: `timing_recommendations[]` values

Same enum as §I.1 Current Supplement Protocol's timing field, for matching:
- Morning
- Pre-workout
- During workout
- Post-workout
- Evening
- As-needed
- Variable

Multi-select — most supplements have ≥1 valid timing window.

### Contraindications format

`contraindications[]` entries are one of:
- A `health_condition_categories.system_category` value (e.g., `'GI'`, `'Cardiac'`, `'Endocrine/Metabolic'`)
- A named allergen string with prefix `'allergen:'` (e.g., `'allergen:dairy'`, `'allergen:soy'`)
- A drug interaction string with prefix `'rx:'` (e.g., `'rx:anticoagulant'`, `'rx:SSRIs'`)
- An age constraint with prefix `'age:'` (e.g., `'age:<18'`)
- A pregnancy/lactation flag: `'pregnancy'`, `'lactation'`

2E and Layer 4 consume this field for coaching-flag generation when athlete's §B records (conditions, allergies, medications) overlap with a supplement they're taking.

---

## 2. Seed data — 25 common supplements

Each row spec'd at curation depth. FC-1 implements as INSERT statements.

| supplement_id | canonical_name | category | primary_effect | typical_dose | timing | contraindications | evidence_quality | notes |
|---|---|---|---|---|---|---|---|---|
| creatine_monohydrate | Creatine monohydrate | Performance | Muscle creatine saturation; improves short-duration high-intensity output and total work capacity over volume sessions | 3–5 g/day (no loading needed for adherent athletes) | Variable, Morning, Post-workout | — | Strong | No on/off cycling needed once saturated. May cause initial water-weight gain (~1-2 kg). |
| whey_protein | Whey protein isolate or concentrate | Recovery | Fast-absorbing protein for post-training MPS stimulation | 20–40 g | Post-workout, Morning | allergen:dairy | Strong | Concentrate has lactose; isolate is near-lactose-free. |
| casein_protein | Casein protein | Recovery | Slow-release protein; supports overnight MPS | 20–40 g | Evening | allergen:dairy | Moderate | Often combined with magnesium for sleep support. |
| plant_protein | Plant protein blend (pea, rice, hemp) | Recovery | Plant-based alternative to whey/casein | 25–45 g (higher dose due to lower DIAAS) | Post-workout, Morning, Evening | — | Moderate | DIAAS lower than animal sources; multi-source blends close the gap. |
| eaas | Essential amino acids (EAAs) | Recovery | Full essential amino spectrum for MPS | 6–15 g | Pre-workout, During workout, Post-workout | — | Moderate | Generally preferred over BCAAs for MPS effect. |
| bcaas | Branched-chain amino acids (BCAAs) | Recovery | Leucine/isoleucine/valine for MPS support | 5–10 g | Pre-workout, During workout | — | Weak | Limited additional benefit if total protein intake is adequate. EAAs preferred when supplementation is desired. |
| beta_alanine | Beta-alanine | Performance | Muscle carnosine precursor; buffers H+ in 30–120s high-intensity efforts | 3.2–6.4 g/day, divided | Variable | — | Strong | Causes paresthesia (tingling) at higher single doses. Split dosing recommended. Loading phase: 4–8 weeks for full effect. |
| electrolyte_mix | Sodium/potassium/magnesium electrolyte mix | Race-day | Hot-weather sodium replacement and cramp prevention | Scaled to sweat loss; typical 300–1000 mg Na/hr | During workout, As-needed | Cardiac (high-Na formulas), Endocrine/Metabolic (e.g., aldosterone disorders) | Strong | Cross-ref §I.2 Salt/Electrolyte Tolerance. |
| magnesium | Magnesium (glycinate, citrate, malate) | Health | Muscle/nerve function, sleep support; common deficiency in athletes | 200–400 mg | Evening | GI (citrate form can cause GI distress at high doses) | Moderate | Glycinate is best-tolerated for sleep; citrate has laxative effect at high doses. |
| iron | Iron (ferrous sulfate, bisglycinate, etc.) | Health | Red blood cell production; addresses common athlete iron deficiency | 18–65 mg elemental iron | Morning (away from coffee/tea) | GI (causes constipation/GI distress); rx:thyroid medications (4hr separation) | Strong | Requires medical guidance — supplementation without serum ferritin testing risks overload. Often combined with Vit C for absorption. |
| vitamin_d | Vitamin D3 | Health | Bone density, immune function, athletic performance support | 1000–4000 IU/day | Morning | — | Strong | Serum 25(OH)D level should guide dosing. Target 30–50 ng/mL for athletes. |
| vitamin_b12 | Vitamin B12 | Health | Energy metabolism, RBC formation; deficiency risk in plant-based diets | 250–1000 mcg/day or 1000–2500 mcg/week | Morning | — | Strong | Sublingual or injection forms have higher bioavailability than oral tablets. |
| omega_3 | Omega-3 (EPA/DHA) | Recovery | Anti-inflammatory; joint, cognitive, cardiovascular support | 1–3 g EPA+DHA/day | Morning, Evening | rx:anticoagulant | Strong | Fish-oil form more bioavailable than ALA (flax). Quality varies wildly by brand. |
| probiotics | Probiotics (multi-strain) | GI | Gut microbiome support; useful for athletes with frequent GI issues | 10–100 billion CFU/day | Morning | — | Moderate | Strain-specific effects. Look for strains studied in athletes (Lactobacillus, Bifidobacterium). |
| collagen | Hydrolyzed collagen + Vit C | Recovery | Connective tissue (tendon, ligament) synthesis support | 10–15 g + 50 mg Vit C | Pre-workout (30 min before, especially before tendon-loading work) | — | Moderate | Timing matters more than total daily intake. Pre-workout window leverages bloodstream amino availability. |
| tart_cherry | Tart cherry juice or extract | Recovery | Anti-inflammatory; possible sleep aid via melatonin content | 480 mg extract or 240 mL juice | Pre-workout (intense days), Evening | — | Moderate | May blunt training adaptations if used chronically — best for race week and recovery from key sessions. |
| beetroot_nitrate | Beetroot or nitrate supplement | Performance | Nitric oxide production via dietary nitrate; vasodilation, improved O2 economy | 6–8 mmol nitrate (~500 mg) | Pre-workout (2–3 hr before event) | rx:PDE5-inhibitors | Moderate | Effect more pronounced in lower-trained athletes; elite endurance athletes see smaller gains. |
| caffeine | Caffeine (anhydrous, pill, gum, gel) | Performance | Adenosine antagonist; ergogenic for endurance and high-intensity | 3–6 mg/kg body weight | Pre-workout, During workout (race-day) | Cardiac (arrhythmia risk), pregnancy | Strong | **Cross-ref §I.1 Caffeine Tolerance & Strategy and §I.1.1 Race-day Caffeine Strategy** — daily intake and race-day strategy are captured there. This vocabulary entry handles non-daily supplemental use (race-day pills/gels). |
| carb_powder | Carbohydrate powder (maltodextrin/fructose blend) | Race-day | Race-day exogenous CHO; sustains blood glucose at intensity | 60–120 g/hr during effort | During workout | GI (high-concentration formulas can cause distress) | Strong | Multi-transporter blends (maltodextrin + fructose at 2:1) tolerated up to ~120 g/hr. Single-source caps near 60 g/hr. |
| sodium_bicarbonate | Sodium bicarbonate | Race-day | Extracellular H+ buffering; ergogenic for 1–7 min high-intensity efforts | 0.2–0.3 g/kg body weight | Pre-workout (60–90 min before) | GI (causes distress; new enteric-coated forms reduce risk), Cardiac, Endocrine/Metabolic | Strong | GI distress is the limiting factor. Test in training before race use. Effect is meaningful only in repeated high-intensity efforts, not long endurance. |
| citrulline_malate | Citrulline malate | Performance | NO precursor; muscle endurance support | 6–8 g | Pre-workout (60 min before) | — | Moderate | Better-absorbed than L-arginine for raising plasma arginine levels. |
| multivitamin | Multivitamin (broad-spectrum) | Health | Micronutrient insurance for inconsistent diet | 1 serving/day | Morning | — | Weak | Most athletes with varied diet don't need this; useful for athletes with restrictive diets or high training loads. |
| melatonin | Melatonin | Sleep | Circadian regulation, sleep-onset support | 0.3–3 mg | Evening (30–60 min before sleep) | rx:SSRIs, rx:blood-pressure medications | Strong | Lower doses (0.3–1 mg) often as effective as higher; high doses can cause grogginess. Avoid chronic daily use without medical guidance. |
| ashwagandha | Ashwagandha (KSM-66 or sensoril) | Hormonal-Stress | Cortisol modulation, stress adaptation, possible sleep and recovery benefit | 300–600 mg/day | Morning, Evening | rx:thyroid medications, pregnancy | Moderate | Standardized extracts (KSM-66) have more research support than general extract. Effects most pronounced in stressed populations. |
| curcumin | Curcumin (with piperine or liposomal) | Recovery | Anti-inflammatory; possible DOMS reduction | 500–1500 mg curcuminoids | Evening, As-needed (post heavy session) | rx:anticoagulant | Moderate | Bioavailability is the major limitation — non-bioavailable forms have minimal effect. |

---

## 3. Validation rules

1. `supplement_id` is unique, lowercase, underscore-separated, ≤50 chars.
2. `canonical_name` is unique per active row (not superseded).
3. `category` ∈ enum.
4. `evidence_quality` ∈ enum.
5. `timing_recommendations[]` entries each valid per the §I.1 timing enum.
6. `contraindications[]` entries: if not prefixed with `allergen:`, `rx:`, `age:`, or one of `{'pregnancy', 'lactation'}`, MUST be a valid `health_condition_categories` value. ETL validation enforces.

---

## 4. How §I.1 Current Supplement Protocol consumes this

Athlete's §I.1 Current Supplement Protocol is a record set. Each record:

```python
@dataclass
class AthleteSupplementRecord:
    supplement_id: str           # FK to supplement_vocabulary.supplement_id; or 'other' sentinel
    other_name: str | None       # populated only when supplement_id == 'other'
    dosage_amount: float
    dosage_unit: str             # 'g' | 'mg' | 'mcg' | 'IU' | 'mL' | 'capsule' | 'serving'
    timing: list[str]            # Multi-select from timing enum
    purpose: str | None          # Optional athlete free-text annotation
```

`supplement_id = 'other'` is the escape hatch for supplements not yet in vocab. ETL flags 'other' rows with frequency >5 for vocab promotion review.

---

## 5. How 2E and Layer 4 consume this

### 2E consumes for:
- **Daily supplement integration into nutrition baseline:** if athlete records Iron, 2E doesn't recommend additional iron in daily macro plan
- **Race-day supplement integration:** if athlete records Sodium bicarbonate or Carb powder, 2E factors these into race-day macro plan
- **Cross-reference contraindication flagging:** athlete on Iron + §B GI condition (Status=Current) → coaching flag; athlete on Sodium bicarbonate + §B Cardiac condition → coaching flag

### Layer 4 consumes for:
- **Plan rendering:** when prescribing intervals, plan-gen reads collagen records and times collagen+VitC 30 min before tendon-loading sessions
- **Athlete-facing rationale:** "Pre-workout: 5g creatine (you take this daily; no change to your protocol)"
- **Caffeine cross-reference:** Layer 4 reconciles §I.1 Caffeine Tolerance × race-day caffeine entry in supplement protocol × §I.1.1 race-day strategy

---

## 6. Curation workflow for FC-1

1. FC-1 curator validates the 25 seed entries above against current evidence base
2. Inserts seed via INSERT statements (one transaction)
3. ETL validates per §3
4. Coverage review: do AR-relevant supplements have entries? (Caffeine, electrolyte_mix, carb_powder, sodium_bicarbonate are AR-relevant; all in seed.)
5. Flags any entry where evidence_quality is Weak or Theoretical for Andy review — these may be candidates for removal vs inclusion

Estimated FC-1 effort: 30–45 min. Trivial compared to D-22 (~600 cells) and D-23 (~150 cells).

---

## 7. Forward references / open items

- **Supplement interactions (supplement × supplement):** not currently captured. Iron + Vit C, Calcium + Iron timing conflict, etc. Future enhancement; tracked here pending real-world signal.
- **Brand-specific entries:** supplement_vocabulary is generic (ingredient-level). Specific products (e.g., "Gatorade Endurance Formula") are NOT in scope — those go in `athlete_supplement_record.other_name` or `purpose` for now.
- **Athlete-curated additions:** if 'other' frequency rises to ≥5 across athlete records, the entry surfaces for FC-2 vocab promotion review.
- **Sport-specificity:** some supplements are sport-specific (e.g., sodium bicarbonate for sprint efforts is irrelevant to ultra-endurance athletes). Currently no sport-targeting metadata. Layer 4 plan-gen can ignore inappropriate suggestions; not a vocab table concern.

---

## 8. Gut check

**What this gets right:**
- Pulls free-text supplement entry off 2E's input surface; 2E becomes clean set-intersect like other Layer 2 nodes.
- 25 entries cover the high-frequency cases; "other" sentinel preserves flexibility.
- Contraindication metadata enables coaching flags that the free-text version literally couldn't generate (you can't check "Iron + GI condition" against a free-text field).
- Cross-ref to §I.1 Caffeine fields makes the redundancy explicit rather than hidden.

**Risks:**
- 25 entries is opinionated. Some entries (BCAAs, multivitamin) are listed despite Weak evidence — including them risks signaling endorsement. Counter: athletes use them whether or not we list them; structured capture is better than free text we can't analyze.
- `evidence_quality` field is curator judgment — different sources rate the same supplement differently (Creatine is Strong across most reviews; BCAAs ratings range from Weak to Moderate by source). FC-1 curation should anchor on a single source for consistency (e.g., the Antinutrients Examine.com synthesis or Australian Institute of Sport AIS rankings, both widely cited).
- Brand-specificity gap (sodium drink mix X vs Y) means free-text capture continues at the dosage/purpose level. 2E loses brand-level granularity but gains category-level structure. Net win.

**What might be missing:**
- **Carbohydrate gel** as its own entry — currently captured as `carb_powder` which is the powder form. Gels and chews have different absorption profiles. Could split or merge. Recommendation: keep `carb_powder` covering all CHO supplement forms (gels, chews, drink mix, powder) with notes about format differences. Simpler.
- **Glutamine, taurine, l-carnitine** — three more performance/recovery supplements with moderate-to-weak evidence. Could expand to 30 entries. Recommendation: ship 25, expand when athlete 'other' frequency surfaces them.

**Best argument against:**
Curating supplement vocabulary opens a evidence-claim liability surface — if we list Beta-alanine as Strong evidence and athletes consume more of it, we're implicitly endorsing it. Counter: we're not making claims; we're structuring what athletes already take. The `evidence_quality` field documents our confidence rather than recommending. Plan-gen never *adds* supplements the athlete didn't enter; it only *integrates* their existing protocol.

---

*End of spec. FC-1 implements: schema migration + 25 seed inserts. Tracked as D-26 in `Project_Backlog.md`.*
