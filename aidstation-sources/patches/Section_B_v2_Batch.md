# Section B — Health Status (v2 batch)

**Built:** May 2026
**Slots into:** `Athlete_Onboarding_Data_Spec_v2.md` (when v2 is written)
**Replaces:** Section B of `Athlete_Onboarding_Data_Spec_v1.md` in its entirety
**Source decisions:**
- Health Conditions merge confirmed (Vocabulary Audit v2 §2)
- Canonical body parts confirmed (Vocabulary Audit v2 §1)
- Injury Type field added (Onboarding handoff Section B decision)
- Movement Constraints unchanged from v1

---

## What changed vs v1

| Field | v1 → v2 |
|---|---|
| Chronic Medical Conditions (multi-select) | **Replaced** by Health Conditions (record-type field, B.4) |
| Systemic Constraints (proposed B.1 subfield) | **Dropped** — absorbed into Health Conditions |
| Injury Record (B.1) | **Adds** Injury Type field; Body Part vocab replaced |
| Body Part enumeration (B.2) | **Replaced** with canonical list (41 entries) |
| Movement Constraint enumeration (B.3) | **Unchanged** |
| Current Medications | **Unchanged** |
| Food Allergies & Intolerances | **Unchanged** |
| Resting Heart Rate | **Unchanged** |

---

# Section B — Health Status

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Current Injuries | Injury Record (1+, see B.1) | 1 | Exercise filtering via col 9 + col 13 | Self-report |
| Injury History (last 3 years, resolved) | Injury Record (0+, status=resolved) | 2 | Preventive exercise prioritisation | Self-report |
| Health Conditions | Health Condition Record (0+, see B.4) | 1 | Volume ceiling, HR ceiling, altitude flags, carb-timing for diabetic ultra athletes, system-specific filtering | Self-report |
| Current Medications (training-relevant types only) | Multi-select | 2 | Beta blockers → RPE not HR; diuretics → hydration; NSAIDs → injury masking flag; HRT → programming-independent of biological sex | Self-report |
| Food Allergies & Intolerances | Multi-select + free text | 2 | Race nutrition planning, aid station strategy, anaphylaxis kit flag | Self-report |
| Resting Heart Rate | Number (bpm) | 2 | HR zone calibration; >10 bpm above baseline = overtraining flag | FIT-fill (wellness, 5+ day average) |

**Disclosure language at account creation** (Section A.1) replaces the previously-removed Physician Clearance field. Specific copy is a product/legal decision — flagged in Open Items.

---

## B.1 Injury Record substructure

Each injury record contains:

| Field | Type | Notes |
|---|---|---|
| Body Part | Enum (see B.2) | Maps directly to exercise DB col 13 — vocabulary aligned per Vocabulary Audit v2 §1 |
| Side | Enum (Left / Right / Both / N/A) | |
| Injury Type | Enum (see B.1.1) | **NEW in v2.** Drives prescription specificity (e.g., tendinopathy needs different loading than acute strain) |
| Severity | Enum (Acute / Recovering / Chronic-Managed / Post-surgical / Structural-Permanent / Resolved) | Determines filtering aggressiveness |
| Movement Constraints | Multi-select (see B.3) | Maps to exercise DB col 9 keyword patterns |
| Date of Onset | Date | |
| Status History | Timeline of severity changes with dates | Tracks acute → recovering → chronic → resolved |
| Notes | Free text | Provider instructions, surgical details, etc. |

### B.1.1 Injury Type enumeration

Tier 1, single-select per injury record.

| Type | Examples | Programming implication |
|---|---|---|
| Acute soft tissue (strain / sprain / tear) | Hamstring strain, ankle sprain, calf tear | Acute phase: no loading; recovery phase: gradual eccentric reload |
| Tendinopathy / overuse | Achilles tendinopathy, patellar tendinopathy, plantar fasciitis | Heavy slow resistance protocol; avoid plyometric loading until pain-free |
| Joint (mechanical) | Meniscus tear, labral tear, impingement | ROM-restricted prescription; avoid end-range loading |
| Bone (fracture / stress fracture / contusion) | Tibial stress fracture, rib fracture | No-load / cross-train; bone healing timeline (6–8 wk minimum) |
| Skin / surface (burn / abrasion / laceration) | Road rash, blister, friction burn | Short-term gear-contact avoidance; localised filtering only |
| Nerve | Sciatica, radiculopathy, peroneal neuropathy | Avoid neural tension positions; specific to constraint |
| Inflammatory (bursitis / fasciitis) | Trochanteric bursitis, plantar fasciitis | Anti-inflammatory loading patterns; avoid impact spikes |
| Post-surgical | ACL reconstruction, meniscectomy, rotator cuff repair | Phase-based protocol per surgeon; gates by clearance date |
| Other / uncertain | Athlete unsure of type | Conservative filter (treat as acute soft tissue + flag for self-recheck) |

---

## B.2 Body Part enumeration

Vocabulary aligned with exercise DB col 13 per Vocabulary Audit v2 §1. **41 canonical body parts.** Side (L/R/Both/N/A) is a separate field on the injury record.

### Head / Neck
Neck · Jaw · Trapezius

### Shoulder
Shoulder · Rotator cuff · AC joint · Shoulder blade

### Arm
Elbow · Forearm · Wrist · Hand · Bicep · Tricep · Fingers · Thumb · Finger pulley · DIP joint · CMC joint

### Back
Upper back · Lower back · Spine (general) · SI joint · Sciatica

### Hip
Hip · Groin · Hip flexor · Glute · Hip crest · TFL

### Upper leg
Quad · Hamstring · IT band

### Knee
Knee · Kneecap · Meniscus · ACL · PCL · MCL · LCL

### Lower leg
Calf · Soleus · Shin · Achilles · Peroneal

### Foot / Ankle
Ankle · Plantar fascia · Foot · Toes

### Trunk
Rib · Chest

**Notes:**
- "Hand" and "Fingers" are generic; "Finger pulley", "DIP joint", "CMC joint" are climbing-specific and kept separate.
- "Spine (general)" exists for non-region-specific flags; prefer Upper back / Lower back / SI joint when locatable.
- "Sciatica" is functionally distinct from generic Lower back (nerve symptom vs. mechanical) for filtering purposes.

---

## B.3 Movement Constraint enumeration

**Unchanged from v1.** Maps to keyword patterns in exercise DB col 9. Multi-select per injury.

| Constraint | Maps to col 9 keywords |
|---|---|
| Pain with loading | "under load", "heavy load", "weighted" |
| Pain with impact | "landing", "impact", "reactive load" |
| Pain above specific joint angle | "above 90°", "at full extension", "at depth" |
| Pain on descent / eccentric | "eccentric", "descent", "downhill", "braking" |
| Pain on rotation | "rotation", "torque", "twisting" |
| Pain with grip / sustained hold | "grip", "sustained hold", "forearm fatigue" |
| Pain with wrist extension | "wrist extension", "palm-down" |
| Pain with overhead movement | "overhead", "above shoulder", "impingement" |
| Instability | "instability", "subluxation", "gives way" |
| Reduced ROM | "ROM restriction", "dorsiflexion limited" |
| Pain at high volume only | "sustained", "repetitive", "overuse" |

**Cross-layer note:** Keyword matching against free-text col 9 is fuzzy. Layer 0 enhancement (Open Item #9) — add structured Movement Components field to col 9 — would replace keyword matching with direct field-to-field alignment. Out of scope for v2 onboarding spec; flagged for Layer 0 work.

---

## B.4 Health Condition Record substructure

**NEW in v2.** Replaces v1's "Chronic Medical Conditions" multi-select field. Parallel record-type structure to Injury Record.

| Field | Type | Notes |
|---|---|---|
| Name | Free text | The condition itself ("Asthma", "Type 1 diabetes", "Crohn's", "Concussion history", "Heat-induced syncope") |
| System category | Single-select enum (see B.4.1) | Drives plan-side filtering and prescription rules |
| Status | Enum (Current / History) | Current = actively affects programming; History = informs prevention/return-to-load logic |
| Notes | Free text | Provider instructions, trigger patterns, severity context, medication cross-ref |

**Multiplicity:** 0+ records per athlete. Tier 1.

### B.4.1 System category enum

| System category | Drives | Examples |
|---|---|---|
| Cardiac | HR ceiling enforcement; avoid max-effort and high-HR-spike work | Hypertension, arrhythmia, post-MI, HCM |
| Respiratory | Altitude-sim caution; interval intensity management; cold-air protocols | Asthma, EIB, COPD, post-COVID lung |
| Endocrine / Metabolic | Carb-timing for diabetic ultra; thyroid-aware volume ramps; cortisol-aware load | T1D, T2D, hypo/hyperthyroid, adrenal insufficiency, PCOS |
| GI | Race-fueling planning; aid-station strategy; avoid high-jostle post-fueling | IBS, IBD, Crohn's, celiac, chronic reflux |
| Neurological | Coordination/disorientation drill caution; concussion return-to-load; seizure-risk gating | Concussion history, migraine, epilepsy, MS, neuropathy |
| Cognitive / Mental health | Plan complexity calibration; recovery prioritisation; stimulant ↔ HR interaction | ADHD, anxiety, depression, OCD — when affects training adherence/intensity |
| Musculoskeletal (chronic non-injury) | Permanent regression chain; load management; flare-up flags | Arthritis, fibromyalgia, hypermobility, congenital structural |
| Skin | Sun-exposure exercise filtering; abrasion-risk surfaces; sweat-irritation gear | Photosensitivity, eczema, severe sweat allergy |
| Thermoregulation | Heat/cold tolerance flags; pairs with system-tracked heat-acclim history | Heat intolerance, Raynaud's, MS-related thermal dysreg |
| Immune / Autoimmune | Recovery time inflation; flare-aware load management | RA, lupus, MCAS, post-infection syndromes |
| Other | Free text in Name describes | — |

### B.4.2 Auto-population (deferred to v2 spec design)

Some Health Condition records can be auto-suggested from other onboarding fields:
- **Food Allergies & Intolerances** with anaphylaxis flag → suggest GI or Immune/Autoimmune record
- **Current Medications** containing condition-specific drugs (insulin, beta blocker, levothyroxine) → suggest corresponding system category record
- **Resting Heart Rate** outliers → suggest Cardiac record (with caveat: athlete bradycardia is normal)

Auto-suggest, not auto-create. Athlete confirms before record is added.

**Status:** Auto-population logic is a v2 spec design decision — flagged in Open Items, not specced here.

---

# Open Items (Section B specific)

| # | Item | Status |
|---|---|---|
| 1 | Auto-population logic for Health Conditions from other fields (medications, allergies, RHR) | Deferred to v2 spec design |
| 2 | HRT presence affecting programming independently of biological sex | Captured under Medications; document in v2 Section A.1 disclosure note |
| 3 | Movement Components structured upgrade on col 9 | Cross-layer Open Item #9 — Layer 0 enhancement |
| 4 | "Pre-injury risk model" — should resolved injuries (status=Resolved) get a preventive priority boost in exercise selection? | Onboarding handoff Open Item #6, deferred to v2 |
| 5 | Concussion history as Health Condition (Neurological, History) vs. Injury History (Brain, Resolved) — pick one path | Recommend Health Condition only — concussions have systemic/cognitive aftermath beyond a body-part injury record |

---

# Implementation checklist (for v2 spec writer)

- [ ] Replace v1 §B field table with B field table above
- [ ] Replace v1 §B.1 substructure table with B.1 above (note Injury Type addition)
- [ ] Add v1 §B.1.1 Injury Type enumeration (new)
- [ ] Replace v1 §B.2 with B.2 above (canonical body part list)
- [ ] Confirm v1 §B.3 carries forward unchanged
- [ ] Add §B.4 Health Condition Record substructure (new)
- [ ] Add §B.4.1 System category enum (new)
- [ ] Note §B.4.2 auto-population deferred
- [ ] Update v2 Open Items list with the 5 items above
- [ ] Cross-reference Vocabulary Audit v2 §1 (body parts) and §2 (Health Conditions) as the canonical sources
