# Athlete Onboarding Data Spec — v2

**Version:** 2.5
**Status:** Batches 1–5 complete. Spec body complete pending Open Items.
**Last updated:** 2026-05-06 (v2.3: batch 4+5 integration + §B.1.2/§B.4.2 patches + Rule 3 sex-adjustment; v2.4: §B.1.1 Joint mechanical split into surgical / non-surgical; v2.5: §B.1.1 Bone split into non-stress / stress fracture)
**Supersedes:** `Athlete_Onboarding_Data_Spec_v1.md`
**Built:** May 2026
**Sources reconciled:**
- v1 spec
- `V2_spec_decisions_handoff.md` (authoritative for the three locked decisions: Athlete Network, §D drop, §E.7 strength field migration)
- `V2_Reconciliation_Findings.md` (pre-drafting reconciliation pass)
- v2 batch docs: `Section_B_v2_Batch.md`, `Sections_C_J_v2_Batch.md`, `Sections_GHMN_v2_Batch.md`, `Adherence_Drop_Spec_v2.md`
- `Vocabulary_Audit_v2.md` (controlled vocab — body parts, equipment, health conditions)
- `Onboarding_Session_Handoff.md` (foundational decisions for §A, §I, §J, §K)

---

## Purpose

Defines the complete athlete-side data the training plan app collects from a user, organised into three top-level groups:

1. **Athlete Data** — what drives plan generation (§A–§L)
2. **Account Configuration** — how the user's account integrates with services and tracks consent (Connected Services, Gym Memberships, Disclosure Acknowledgments)
3. **Plan Management** — how plans are generated, updated, and reconciled across linked athletes (Profile Update Triggers, Adherence Drop, Plan Duration logic, joint-training generation)

This split clarifies what's onboarding-blocking versus account-level versus deferred to runtime. The v1 flat 14-section structure (A–N) collapsed all three concerns into one outline; v2 separates them.

This spec is **agnostic to UX flow.** What screens exist, what's collected upfront vs. deferred, what defaults are pre-filled — those are separate design passes.

---

## What changed structurally vs v1

| v1 | v2 |
|---|---|
| 14 flat sections (A–N) | Three groups: Athlete Data (A–L), Account Configuration, Plan Management |
| §A had Sex (TIER 1) and Gender Identity (TIER 3) | Gender Identity dropped; Sex stays TIER 1; A.1 Disclosures added |
| §B Chronic Medical Conditions (multi-select) | §B Health Conditions (record-type field, parallel to Injury Record) |
| §B.1 Injury Record had no Injury Type | §B.1 adds Injury Type (TIER 1, 9-value enum) |
| §B.2 body parts: ~50 mixed-vocabulary entries | §B.2: 41 canonical, hybrid common-name/anatomical |
| §C had no Discipline Weighting | §C adds Discipline Weighting (defaults from Phase Load Allocation midpoints) |
| §C had no Pack Load Training History | §C adds Pack Training Record substructure |
| §D Sport & Discipline Selection | **Eliminated.** Training Target → §H prefix gate; Constituent Disciplines stays §H per-event; Discipline Weighting → §C |
| §E (v1 letter) Discipline-Specific Baselines | Renumbered §D. §D.7 (was §E.7) renamed "Technical Disciplines"; Pull-Up / Dead Hang / Grip moved to §E |
| §F (v1) Strength, Core & Balance Benchmarks | Renumbered §E. Adds Pull-Up Maximum, Dead Hang Duration, Grip Strength (moved from old §E.7); drops the v1 "don't double-collect" footnote |
| §G (v1) Performance Testing | Renumbered §F. Adds Running Threshold Pace |
| §H (v1) Schedule | Renumbered §G. Drops Time-of-Day Preferences; promotes Doubles Feasible to TIER 1 |
| §I (v1) Target Events | Renumbered §H. Adds Specific Event Y/N prefix gate; adds Plan Duration enum (8/12/16/20/24 weeks, only when Y/N=No); Estimated Duration > 20 hr now drives **collection** of Sleep Dep field on §I, not just an internal flag |
| §J (v1) Lifestyle & Recovery | Renumbered §I. Drops Heat Acclimatization (system-tracked instead); adds race-day fueling preferences (Caffeine race-day strategy, Fueling Format, GI Triggers, Salt/Electrolyte Tolerance); adds Sleep Deprivation Experience (conditional on §H.Estimated Duration > 20 hr) |
| §K (v1) Locales | Renumbered §J. Geographic locale model (city-tagged, no parent-child). Gym Chain field added. Seasonality is hybrid (climate-derived defaults + user override) |
| §L (v1) Locale Schedule | Renumbered §K. Adds joint-training overlay fields (FK to Athlete Link, Status, Proposed By, Source, Parent Recurrence); recurring overlay sub-entity added |
| §M (v1) Profile Update Triggers | **Moved out of Athlete Data.** Lives in Plan Management group |
| §N (v1) Sport-Specific Additional Data | **Eliminated.** AR Team Composition → §L (Athlete Network); Carb Tolerance was a duplicate of §D.1 Gut Training History (deleted); Sleep Dep → §I (above); Saddle Endurance unchanged in §D.2 |
| (no v1 equivalent) | New §L: **Athlete Network.** Slim Athlete Link entity covering both Solo Training Partners and Race Teammates. Joint-training scheduling lives in §K Locale Schedule overlays |

---

## Tier definitions (unchanged from v1)

- **TIER 1** — Required. Plan generation cannot produce a meaningful output without it.
- **TIER 2** — Important. Significantly improves plan specificity. App should prompt for it but accept deferred entry.
- **TIER 3** — Optional. Refinement only.

---

## Connected Services data convention

v1 marked fields with `FIT-fill` where Garmin/wearable FIT files could populate them. v2 generalises this:

> **Source convention:** Where a field has a viable third-party data source, the spec lists the source as **"Manual entry from FIT export at launch; Connected Service post-launch."** At launch, all values are manually entered or imported from FIT files the user uploads themselves. Post-launch, Connected Services (Garmin Connect, Strava, Apple Health, etc.) supply these automatically. The Account Configuration group owns the Connected Services entity — see Group 2.

Freshness rules carry forward from v1: ≤90 days for activity-derived fields, ≤30 days for wellness-derived fields. Post-launch, freshness is enforced against Connected Service sync timestamps; pre-launch, against last manual entry date.

---

# Group 1 — Athlete Data

The data that drives plan generation. Sections §A through §L. All sections are athlete-scoped (one record set per user) except §J Locales (1+ per athlete), §K Locale Schedule (0+ overlays), §L Athlete Network (0+ links).

---

## Section A — Athlete Identity

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Name | Text | 1 | Labeling only | Self-report |
| Date of Birth | Date (Month/Year) | 1 | Volume ceiling, ramp rate, masters injury stratification (40+), age-group categorization | Self-report |
| Sex | Enum (M/F) | 1 | Event categorization for mixed relays; physiological adaptation rates; HR zone calibration; iron metabolism flags | Self-report |
| Height | Number (cm or ft/in) | 2 | Body composition context, swim drag, bike fit, OCR obstacle scaling | Measured |
| Body Weight | Number (kg or lb) | 1 | W/kg cycling, calorie targets, OW buoyancy, pack-weight % of bodyweight | Manual entry from FIT export at launch; Connected Service post-launch; measured monthly fallback |
| Primary Training Location | Text (Country/State/City) | 1 | Seeds required home locale; climate, altitude, terrain defaults | Self-report at locale setup |

**Notes on what's not collected:**

Gender identity is not collected. Sex (M/F) is collected because plan logic genuinely depends on it (HR zones, iron metabolism, event categorization for mixed-team races where rules apply). Gender identity drives no plan logic; collecting it without using it adds friction without value. Athletes whose physiology differs from their assigned sex due to HRT or other medical context capture that through §B Medications, which is read independently of §A Sex.

**HRT and programming:**

Where an athlete is on hormone replacement therapy, programming should respond to the medication record in §B, not to a presumed mapping from §A Sex. The §B.4 Health Condition record can also capture endocrine context. v2 treats biological sex (§A) and hormonal milieu (§B) as separate inputs to plan generation.

### A.1 Disclosures

A.1 documents what the athlete is shown and asked to acknowledge during onboarding and at certain plan-generation moments. The athlete's acknowledgment **state** (timestamp, content version, what was shown) is stored in Account Configuration. A.1 specifies what those disclosures contain.

| Disclosure | When shown | What it covers |
|---|---|---|
| Account-creation acknowledgment | One-time, at account creation | Replaces v1's removed Physician Clearance field. User acknowledges training carries inherent risk; app provides plan recommendations, not medical advice; user is responsible for medical clearance with their own provider; app may surface risk-relevant prompts based on data they enter (e.g., chest pain Health Condition → recommend medical clearance before high-intensity work) |
| Sex-collection inline disclosure | At the §A Sex field | Brief explainer: "We ask biological sex because plan logic uses it for HR zone calibration, iron-metabolism flags, and event-categorization for races with mixed-team rules. We don't ask gender identity because no plan logic depends on it." Link to longer privacy/data-use page |
| Health-data inline disclosure | At §B section entry | Brief explainer on data sensitivity: what's stored, what's used in plan generation, what's not shared with linked partners (§L) without explicit per-link consent. Link to privacy policy |
| HRT inline disclosure | At §B Medications when an HRT-class drug is entered | Brief explainer that HRT presence overrides §A Sex assumptions for relevant programming decisions; user can add a §B.4 Health Condition record if endocrine context affects training response |
| Connected Service consent | At Connected Service connect flow (Account Config) | Per-service scope acknowledgment — what data is read, frequency, revocation path. Owned by Account Config; A.1 cross-references for completeness |
| Linked-partner data-sharing disclosure | At §L Athlete Link creation when Linked Account FK is set | What the other party sees; what they don't; revocation flow |

**Copy is product/legal-owned.** Specific wording for each disclosure is a separate design pass. A.1 specifies the **slots**; the actual text is filled in pre-launch.

**Storage of acknowledgment state:** Each disclosure shown to a user creates an acknowledgment record in Account Configuration with `disclosure_id`, `version_id`, `shown_at`, `acknowledged_at`, `content_hash` (so the system can detect if a user needs to re-acknowledge after a copy update).

---

## Section B — Health Status

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Current Injuries | Injury Record (1+, see B.1) | 1 | Exercise filtering via col 9 + col 13 | Self-report |
| Injury History (last 3 years, resolved) | Injury Record (0+, status=Resolved) | 2 | Preventive exercise prioritisation | Self-report |
| Health Conditions | Health Condition Record (0+, see B.4) | 1 | Volume ceiling, HR ceiling, altitude flags, carb-timing for diabetic ultra athletes, system-specific filtering | Self-report |
| Current Medications (training-relevant types only) | Multi-select | 2 | Beta blockers → RPE not HR; diuretics → hydration; NSAIDs → injury masking flag; HRT → programming-independent of biological sex | Self-report |
| Food Allergies & Intolerances | Multi-select + free text | 2 | Race nutrition planning, aid station strategy, anaphylaxis kit flag | Self-report |
| Resting Heart Rate | Number (bpm) | 2 | HR zone calibration; >10 bpm above baseline = overtraining flag | Manual entry from FIT export at launch; Connected Service post-launch (5+ day average) |

The Disclosure Acknowledgment for §B (see A.1) is shown at section entry.

### B.1 Injury Record substructure

Each injury record contains:

| Field | Type | Notes |
|---|---|---|
| Body Part | Enum (see B.2) | Maps directly to exercise DB col 13 — vocabulary aligned per `Vocabulary_Audit_v2.md` §1 |
| Side | Enum (Left / Right / Both / N/A) | |
| Injury Type | Enum (see B.1.1) | TIER 1 sub-field. Drives prescription specificity (e.g., tendinopathy needs different loading than acute strain) |
| Severity | Enum (Acute / Recovering / Chronic-Managed / Post-surgical / Structural-Permanent / Resolved) | Determines filtering aggressiveness |
| Movement Constraints | Multi-select (see B.3) | Maps to exercise DB col 9 keyword patterns |
| Date of Onset | Date | |
| Status History | Timeline of severity changes with dates | Tracks acute → recovering → chronic → resolved. Drives the re-injury preventive priority rule (see §B.1.2) — the lifecycle history determines whether preventive priority persists after resolution |
| Notes | Free text | Provider instructions, surgical details, etc. |

#### B.1.1 Injury Type enumeration

TIER 1, single-select per injury record.

| Type | Examples | Programming implication |
|---|---|---|
| Acute soft tissue (strain / sprain / tear) | Hamstring strain, ankle sprain, calf tear | Acute phase: no loading; recovery phase: gradual eccentric reload |
| Tendinopathy / overuse | Achilles tendinopathy, patellar tendinopathy, plantar fasciitis | Heavy slow resistance protocol; avoid plyometric loading until pain-free |
| Joint (mechanical) — non-surgical | Meniscus tear (managed conservatively), labral tear (managed conservatively), impingement, joint instability without surgery | ROM-restricted prescription; avoid end-range loading |
| Joint (mechanical) — surgical | ACL / PCL / MCL / LCL reconstruction, meniscectomy, meniscus repair, labral repair, joint replacement, surgical impingement decompression | Phase-based protocol per surgeon; gates by clearance date; permanent preventive priority post-clearance per §B.1.2 |
| Bone (fracture / contusion) — non-stress | Traumatic fracture (rib, wrist, clavicle, tib/fib from impact), bone contusion, avulsion fracture | No-load / cross-train through healing window (typically 6–8 wk minimum); gradual return-to-load post-clearance |
| Bone — stress fracture | Tibial stress fracture, metatarsal stress fracture, navicular stress fracture, sacral stress fracture, femoral neck stress fracture | No-load through healing window + extended residual caution per §B.1.2 (18-mo decay); flag overload pattern, bone-density risk factors, and nutrition gaps; permanent attention to load progression on affected bone |
| Skin / surface (burn / abrasion / laceration) | Road rash, blister, friction burn | Short-term gear-contact avoidance; localised filtering only |
| Nerve | Sciatica, radiculopathy, peroneal neuropathy | Avoid neural tension positions; specific to constraint |
| Inflammatory (bursitis / fasciitis) | Trochanteric bursitis, plantar fasciitis | Anti-inflammatory loading patterns; avoid impact spikes |
| Post-surgical | Rotator cuff repair, hardware removal, post-fracture-fixation recovery, non-orthopedic surgical recovery affecting training | Phase-based protocol per surgeon; gates by clearance date; underlying injury type drives residual decay per §B.1.2. Use the most-specific Injury Type when one applies (e.g., joint-mechanical surgery → use Joint (mechanical) — surgical, not Post-surgical) |
| Other / uncertain | Athlete unsure of type | Conservative filter (treat as acute soft tissue + flag for self-recheck) |

#### B.1.2 Re-injury preventive priority rule

When an injury record is set to Severity = Resolved, plan generation continues to apply preventive priority for that body part / injury type. The duration and shape of the priority decay depend on (a) the injury's lifecycle history and (b) its Injury Type.

**Override rule (applies first, regardless of Injury Type):**

If the Status History ever included **Chronic-Managed or Structural-Permanent** at any point in the injury's lifecycle → **permanent preventive priority**. Plan-gen continues to apply protective adjustments (extra warm-up, capped impact volume on the affected body part, preferred substitutions) indefinitely. Rationale: tissue that earned a Chronic-Managed or Structural-Permanent label has structural changes that don't reverse with symptom resolution.

**Default decay model by Injury Type (applies when override does not):**

| Injury Type (per §B.1.1) | Decay model | Evidence basis |
|---|---|---|
| Acute soft tissue (strain / sprain / tear) | Stepped exponential decay over 12 months: full priority (1.0) months 0–3; half (0.5) months 3–6; quarter (0.25) months 6–12; neutral after 12 months | Hamstring strain literature: ~59% of recurrences occur in the first month after return to play; ~25% in the first week; 12-month reinjury rate plateaus around 17% (Jiménez-Rubio et al.; multicentre Qatar/NL prospective cohort, n=330) |
| Tendinopathy / overuse | **Permanent** elevated priority, even after symptom resolution | Achilles tendinopathy 10-yr follow-up: 19% report persisting symptoms; 41% develop bilateral overuse symptoms in the initially uninvolved tendon; recurrence rate up to 44% even after surgery (Lagas et al. 2023; Paavola et al.) |
| Joint (mechanical) — non-surgical | Stepped exponential decay over 18 months: full (1.0) months 0–6; half (0.5) months 6–12; quarter (0.25) months 12–18; neutral after 18 months | Ankle sprain proxy: 2-fold increased risk in year 1; recurrence may happen up to 8 years after initial; chronic symptoms ≥12 months in ~40% (Doherty et al.; Pourkazemi et al.) |
| Joint (mechanical) — surgical | **Permanent** elevated priority | ACL graft rupture: 18% by 5 yr; 47% of those in year 1, 74% by year 2; 23–36% second-ACL injury rate in young athletes (Webster & Feller; NACOX cohort). Surgical joint repair never returns to native tissue mechanics |
| Bone (fracture / contusion) — non-stress | Through documented healing window (typically 6–8 wk minimum) + 6-month residual decay (full first 3 mo, half last 3 mo); neutral after | Standard bone healing timeline; minimal residual structural risk after remodeling complete |
| Bone — stress fracture | Through healing window + 18-month residual decay (full 0–6 mo, half 6–12 mo, quarter 12–18 mo); neutral after | Stress fracture literature shows elevated refracture risk extending well beyond initial healing; bone remodeling and restoration of mechanical properties takes 12–18 months |
| Skin / surface | None — neutral immediately on Resolved | Skin/surface injuries heal without lasting structural change to load-bearing tissue |
| Nerve | Stepped exponential decay over 12 months as for Acute soft tissue, **unless** ever Chronic-Managed (then permanent per override rule) | Acute neural compression typically resolves; chronic radiculopathy / neuropathy is captured by the override rule |
| Inflammatory (bursitis / fasciitis) | Stepped exponential decay over 6 months: full (1.0) months 0–2; half (0.5) months 2–4; quarter (0.25) months 4–6; neutral after | Inflammatory injuries typically resolve quickly; recurrent inflammatory injuries get the Chronic-Managed label and trigger the override rule |
| Post-surgical | Layered: (a) hard gate through surgeon's clearance date; (b) underlying injury type's decay model after clearance; (c) override rule applies if Chronic-Managed or Structural-Permanent at any point | Post-surgical alone does not imply permanent priority — many surgical cases (clean meniscectomy, isolated fracture fixation) recover fully. The underlying injury type drives residual decay |
| Other / uncertain | Conservative default = Acute soft tissue model (stepped decay over 12 months) | Default to the most-studied curve when the type is unclear |

**Status History walk:** the override determination is made by reading the full Status History timeline — not the current Severity value. A record currently at Resolved that *previously* held Chronic-Managed status is treated under the permanent rule, even though the current value is Resolved.

**What "preventive priority weight" means operationally:**

Plan generation reads the priority weight (between 0.0 and 1.0) for each resolved injury at each plan generation event. The weight modulates the strength of preventive adjustments — at weight 1.0, full preventive treatment applies (extra warm-up sets, capped impact volume, preferred low-stress exercise substitutions for the affected body part). At weight 0.5, the same adjustments apply at reduced intensity (e.g., warm-up additions but no impact volume cap). At weight 0.25, only the lowest-cost preventive measures persist (e.g., preferred substitution available but not enforced). At 0 (neutral), no preventive treatment is applied.

The exact mapping from weight to specific plan-gen behaviour is owned by the Plan Management spec; this section defines the weight signal and the decay curve.

**Edge cases:**
- Re-injuries to the same body part / type create a new injury record with its own Status History and decay timer; the existing record's decay continues independently.
- Athlete-edited Status History (correcting a mis-entry) recomputes the override rule and decay weight from the corrected timeline at the next plan generation.
- Multiple resolved injuries on the same body part: weights stack additively, capped at 1.0 (athlete with two separate hamstring strains in the past 6 months still gets full preventive treatment, not 1.5x).
- The decay model treats months as discrete steps for implementation simplicity. A continuous exponential function is no more defensible given the precision of the underlying epidemiological data.

**Confidence note:**

Decay shapes for tendinopathy (permanent), ACL/surgical joint (permanent), and acute soft tissue (12-mo stepped) are well-supported by long-term cohort data. Decay shapes for non-surgical joint mechanical (18-mo) and stress fracture (18-mo) are extrapolated from related literature with less direct evidence and should be revisited if better data emerges. Inflammatory and Nerve decay shapes are clinical heuristics, not literature-derived.

### B.2 Body Part enumeration

41 canonical body parts. Vocabulary aligned with exercise DB col 13 per `Vocabulary_Audit_v2.md` §1. Hybrid naming convention: common-name where it adds no precision over anatomical (Lumbar → Lower back; Cervical → Neck; Thoracic → Upper back); anatomical retained where athletes already know the term from their PT (Achilles, Plantar fascia, IT band, Soleus, Peroneal, Meniscus, ACL/PCL/MCL/LCL, TFL).

Side (L/R/Both/N/A) is a separate field on the injury record.

| Region | Parts |
|---|---|
| Head / Neck | Neck · Jaw · Trapezius |
| Shoulder | Shoulder · Rotator cuff · AC joint · Shoulder blade |
| Arm | Elbow · Forearm · Wrist · Hand · Bicep · Tricep · Fingers · Thumb · Finger pulley · DIP joint · CMC joint |
| Back | Upper back · Lower back · Spine (general) · SI joint · Sciatica |
| Hip | Hip · Groin · Hip flexor · Glute · Hip crest · TFL |
| Upper leg | Quad · Hamstring · IT band |
| Knee | Knee · Kneecap · Meniscus · ACL · PCL · MCL · LCL |
| Lower leg | Calf · Soleus · Shin · Achilles · Peroneal |
| Foot / Ankle | Ankle · Plantar fascia · Foot · Toes |
| Trunk | Rib · Chest |

**Notes:**
- "Hand" and "Fingers" are generic; "Finger pulley", "DIP joint", "CMC joint" are climbing-specific and kept separate.
- "Spine (general)" exists for non-region-specific flags; prefer Upper back / Lower back / SI joint when locatable.
- "Sciatica" is functionally distinct from generic Lower back (nerve symptom vs. mechanical) for filtering purposes.

### B.3 Movement Constraint enumeration

Unchanged from v1. Maps to keyword patterns in exercise DB col 9. Multi-select per injury.

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

**Cross-layer note:** Keyword matching against free-text col 9 is fuzzy. Layer 0 enhancement — adding a structured Movement Components field to col 9 — would replace keyword matching with direct field-to-field alignment. Out of scope for v2 onboarding spec; tracked as Open Item.

### B.4 Health Condition Record substructure

New in v2. Replaces v1's "Chronic Medical Conditions" multi-select field. Parallel record-type structure to Injury Record. Absorbs both the v1 Chronic Medical Conditions multi-select AND the v1-proposed "Systemic Constraints" Injury Record subfield (~70% overlap).

| Field | Type | Notes |
|---|---|---|
| Name | Free text | The condition itself ("Asthma", "Type 1 diabetes", "Crohn's", "Concussion history", "Heat-induced syncope") |
| System category | Single-select enum (see B.4.1) | Drives plan-side filtering and prescription rules |
| Status | Enum (Current / History) | Current = actively affects programming; History = informs prevention/return-to-load logic |
| Notes | Free text | Provider instructions, trigger patterns, severity context, medication cross-ref |

**Multiplicity:** 0+ records per athlete. TIER 1.

#### B.4.1 System category enum

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

**Concussion handling:** Concussion history is a Health Condition (Neurological, Status = History) rather than an Injury History record. Concussions have systemic/cognitive aftermath that exceeds what a body-part injury record captures.

#### B.4.2 Auto-population (launch behaviour)

Three Health Condition auto-suggest rules ship at launch. All are auto-suggest, not auto-create — the athlete confirms before any record is added. Suggestions are non-blocking; an athlete can dismiss any suggestion and proceed with onboarding or training.

##### Rule 1 — Anaphylaxis flag → suggest GI or Immune / Autoimmune record

| Trigger | Suggested record | Notes |
|---|---|---|
| A Food Allergy & Intolerances entry has the anaphylaxis flag set | New Health Condition record, System category = Immune / Autoimmune (default) or GI (if the trigger is ingestion-only with no systemic component) | Suggested at the moment the anaphylaxis flag is set. Pre-fills Name from the allergy entry; athlete edits System category and Notes as desired. Suggestion is suppressed if a record matching the same allergen already exists |

##### Rule 2 — Condition-specific medication → suggest matching system category record

| Trigger | Suggested record | Notes |
|---|---|---|
| A Current Medications entry contains a drug from the launch reference list (insulin, beta blocker, levothyroxine, methotrexate, biologics, antiepileptics, others on the launch list) | New Health Condition record, System category matching the drug's primary indication (e.g., insulin → Endocrine / Metabolic; beta blocker → Cardiac; levothyroxine → Endocrine / Metabolic; antiepileptic → Neurological / Cognitive) | Suggested at the moment the medication is added. Drug-to-category mapping is a launch reference table maintained as part of the medication enum; expand post-launch as new drug classes are added. Suggestion is suppressed if a record in the matching system category already exists |

##### Rule 3 — RHR outlier → suggest Cardiac record

This is the most nuanced rule. Operational thresholds depend on whether the athlete has an established RHR baseline and on whether symptoms are present.

**Sex-based threshold adjustment:**

Women have an average resting heart rate approximately 5 bpm higher than men in large population cohorts (Health eHeart Study, n=66,800: ~4 bpm difference; Fasa PERSIAN cohort: ~5 bpm difference). Bradycardia thresholds are adjusted upward by 5 bpm for athletes with §A Sex = Female to maintain symmetric outlier sensitivity. Tachycardia thresholds (clinical definition 100 bpm per AHA) are sex-agnostic. Baseline shift triggers are inherently self-correcting for sex (the athlete's own baseline is the reference).

Athletes whose §A Sex is unspecified or marked Other use the male thresholds as a conservative default (lower bradycardia trigger threshold = fewer false positives for athletes with naturally lower baselines).

**Trigger conditions** (any one fires the suggestion):

| Condition | Threshold (Male / Other / Unspecified) | Threshold (Female) | Notes |
|---|---|---|---|
| **Sustained tachycardia at rest** | 7-day rolling average RHR > 100 bpm | Same — 100 bpm | Sex-agnostic per AHA clinical tachycardia definition. Suppressed if any of the following is logged within the same 7-day window: illness, fever, recent caffeine spike, ACWR > 1.5 (training overload), severe sleep deprivation |
| **Symptomatic bradycardia** | RHR < 40 bpm AND athlete has logged within the past 14 days any of: dizziness, syncope, unexplained fatigue, exercise intolerance, chest discomfort, palpitations | RHR < **45 bpm** AND same symptom set | RHR below the threshold alone is normal in trained endurance athletes (up to 80% of endurance athletes develop sinus bradycardia). The trigger is the symptom pairing, not the rate. The 5-bpm sex offset reflects the higher female baseline |
| **Sustained baseline shift upward** | 30-day rolling average RHR > 10 bpm above the prior 90-day baseline | Same — 10 bpm above own baseline | Inherently self-correcting for sex (uses the athlete's own baseline). Only fires after a 90-day baseline is established (≥60 days of data in the last 90). Suppressed if illness, ACWR > 1.5, or recent significant detraining is logged |
| **First-entry extreme outlier** | Initial RHR > 100 bpm OR < 35 bpm AND no training history sufficient to explain the value (Years of Structured Training < 1 in primary endurance discipline, OR primary discipline is non-endurance) | Initial RHR > 100 bpm OR < **40 bpm** AND same training-history condition | One-time check at first RHR entry. Upper threshold sex-agnostic (clinical tachycardia). Lower threshold sex-adjusted to maintain equivalent outlier sensitivity |

**Per-trigger context shown to the athlete:**

Each trigger surfaces its own specific copy explaining what was detected and why a Cardiac Health Condition record might be appropriate. The copy explicitly invites athlete dismissal if the elevation/depression has a known cause not captured in the system.

For Rule 3, the suggestion always includes the standard caveat: "Athlete bradycardia from endurance training is normal and not a cardiac condition. Only add a record here if you have symptoms or a clinical concern."

**Suggestion suppression and dismissal memory:**

Dismissed suggestions are remembered for that specific trigger event — the system does not re-suggest the same record on subsequent edits to the same triggering field unless the trigger condition materially changes (e.g., new medication added; allergy upgraded to anaphylaxis; new symptom logged with existing bradycardia). Re-prompts on the same trigger require either a new triggering event or 90+ days elapsed since dismissal.

**Out of scope for launch:**

- Auto-suggestion from Connected Service signals (e.g., wearable-derived AFib detection, HRV crash patterns). Deferred — depends on signal-quality validation per service.
- Auto-suggestion from injury patterns (e.g., recurring tendinopathy → suggest Musculoskeletal chronic record). Deferred — needs separate review of false-positive risk.
- Auto-suggestion from §H Target Event characteristics (e.g., first cold-water swim event → suggest Thermoregulation record). Deferred — collects signal that the athlete may not yet have evidence for.
- **Age-specific** RHR band refinements (e.g., adjusting upper threshold downward for athletes >50). Defer until enough launch data confirms whether age adjustment is warranted on top of sex adjustment. Resting heart rate rises only ~1–2 bpm per decade in adults (Health eHeart Study), so the absolute thresholds may remain valid across age bands without explicit adjustment, but launch data should confirm.
- Pregnancy-state RHR adjustments. Pregnancy elevates resting heart rate by 10–20 bpm during the second and third trimesters; the system does not currently track pregnancy state on the athlete profile, so the trigger may produce false positives for pregnant athletes. Athletes can dismiss the suggestion with no system-side memory penalty in this case, but a future profile field for pregnancy state could suppress the trigger automatically. Tracked as a post-launch design item.

**Confidence note:**

The 60-100 bpm general adult range is AHA standard (well-established). The athlete-specific lower bound (40 bpm normal for endurance athletes; <30 bpm reported in elite) is well-supported by sports cardiology literature. The +10 bpm baseline shift threshold for tachycardia trigger is consistent with the existing §B Resting Heart Rate field's overtraining-flag heuristic. The 14-day symptom-pairing window for bradycardia is a clinical default — could tighten with usage data. The +5 bpm female adjustment is well-supported by large-cohort data (Health eHeart Study n=66,800; Fasa PERSIAN cohort) clustering around 4–6 bpm; smaller cohorts report wider ranges (8–11 bpm) but the conservative middle-of-range value is the right launch heuristic.

---

## Section C — Training History & Fitness Baseline

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Years of Structured Training | Integer | 1 | Year 1: 6%/wk ramp + mandatory 3-on-1-off; veteran 5+ yr: 10% ramp | Self-report |
| Primary Sport | Single-select (from 18 framework sports in `Sports_Framework_v3.xlsx` Sheet 1) | 1 | Aerobic base transferability; seeds Discipline Weighting defaults | Self-report |
| Secondary Sports / Disciplines | Multi-select + experience tier per (Under 1yr / 1–3yr / 3+ yr) | 1 | Per-discipline base-build vs. accelerated vs. maintenance decision | Self-report |
| Discipline Weighting | Per-discipline % (slider/numeric, sum=100) | 2 | Volume allocation across disciplines (hours, not priority levels). Defaults from `Sports_Framework_v3.xlsx` Phase Load Allocation midpoints for Primary Sport. Editable; sum-to-100 validation; zeroed disciplines allowed | Default + self-edit |
| Current Weekly Training Volume | Number (hrs/wk) + per-discipline breakdown | 1 | Week 1 starting point; ACWR 0.8–1.3 from day 1 | Manual entry from FIT export at launch; Connected Service post-launch |
| Peak Historical Weekly Volume | Number (hrs/wk) + year | 2 | Proven physiological ceiling; never target >20% above prior peak without extended base | Self-report |
| Longest Event Completed | Text (event, distance, time, year) — within 2 yrs preferred | 1 | Race endurance proof; gates ultra distance jumps | Self-report |
| Most Recent Race Results | Structured list (last 3–5 races) | 2 | Fitness calibration; pace/FTP/CSS estimation | Manual entry from FIT export at launch; Connected Service post-launch |
| Training Consistency (last 12 mo) | Number (disrupted weeks) + cause | 2 | High disruption → conservative ramp + flexibility; chronic travel → auto-activate hotel substitution | Self-report |
| Pack Load Training History | Pack Training Record (see C.1) | 2 | Pack-load ramp rate; race-pack tolerance gate; chafing/blister/hot-spot risk flagging at high prescribed pack weights | Self-report |
| Previous Coaching/Plans | Single-select (Self / Online plan / Coach / None) | 3 | Calibrates plan complexity (technical vs. simplified) | Self-report |

**On Discipline Weighting:** Single athlete-level set of weights that resolves what proportion of weekly training hours each discipline gets when plan generation runs. Sums to 100 across the user's selected disciplines (Primary Sport's constituent disciplines for combined sports, or Primary + Secondary Sports for mixed solo-discipline athletes). Defaults pulled from `Sports_Framework_v3.xlsx` → Phase Load Allocation sheet, midpoint of % range per discipline. User can edit; zeroed disciplines allowed (athlete fully excludes a discipline they could otherwise train).

**Sports Framework gap dependency:** Defaults assume Phase Load Allocation covers all 18 sports + sub-formats. AR is well-populated; the other 17 are unverified pre-launch. Fallback when a sport has no Phase Load Allocation entries: equal weights across the user's selected disciplines. Tracked as Open Item.

**Pack Load Training History tier rationale:** Tier 2 by default. Effectively Tier 1 for athletes with AR / expedition / mountain-marathon target events (pack >20 lb is mandatory). Conditional elevation handled at plan-gen time, not at onboarding.

### C.1 Pack Training Record substructure

| Field | Type | Notes |
|---|---|---|
| Most recent pack-loaded long session | Weight (lb/kg) + duration (hrs) + date | Anchors current pack-tolerance baseline |
| Typical pack training cadence | Enum (Never / Occasional / 1×/wk / 2+×/wk) | Drives ramp aggressiveness — Never = start at 10 lb / 30 min; 2+×/wk = start at current weight |
| Heaviest pack sustained for >2 hours (lifetime peak) | Weight (lb/kg) + approximate date | Proven physiological ceiling; never target >20% above prior peak without extended ramp |
| Notes | Free text | Discomfort patterns, chafing locations, gear adjustments that helped |

Re-test trigger (Plan Management profile-update spec): profile prompt every 8 weeks if athlete has any pack-required target event in the next 16 weeks; otherwise on athlete demand.

---

## Section D — Discipline-Specific Baselines

Sport-relevant fields collected only when the athlete's Primary Sport, Secondary Sports, or §H Constituent Disciplines include the relevant discipline. UX implication: dynamic — only relevant sub-sections are shown. For database design: every field is nullable; null means "not asked."

Two structural changes from v1 §E worth flagging up front:

1. **Threshold/Tempo Pace removed from §D.1.** This data point is now Running Threshold Pace in §F (Performance Testing), parallel to FTP and CSS — single canonical home for threshold-test outputs. Easy Run Pace stays in §D.1 (different concept: zone 2 anchor for easy-run prescription, not test-derived).
2. **FTP removed from §D.2.** Cycling FTP value moves to §F. §D.2 keeps Bike Types, MTB Technical Skill, Longest Ride, Saddle Endurance, Aero Position Endurance.

The v1 §E.1 "Pack Load Training History" row is removed (moved to §C). §D.7 is renamed **Technical Disciplines** (was "Strength & Technical Disciplines"); strength benchmarks Pull-Up Maximum, Dead Hang Duration, Grip Strength move to §E. §D.7 retains Rock Climbing, Abseiling, Fencing, Shooting.

### D.1 Running

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Easy Run Pace | Time (min:sec/km or /mile) | 1 | Zone 2 anchor; 80/20 polarised distribution | Self-report or HR-calibrated test |
| Recent Race Paces (5K/10K/HM/Mar) | Per distance — derived from §C if available | 2 | McMillan/Riegel pace prediction | Manual entry from FIT export at launch; Connected Service post-launch; or derived from §C |
| Trail Running Experience | Y/N + terrain category (mod/tech/mtn/moor) + Night Y/N | 1 | Road→trail: 8–12 wk terrain adaptation; moorland is non-transferable from road | Self-report |
| Downhill Running Adaptation | Y/N + sessions/3mo at >-10% grade | 1 | **CRITICAL** — only proven EIMD prevention is prior exposure; no adaptation = -5% start max | Self-report |
| Vertical Gain Tolerance | Number (m/wk current) + peak single-session (m) | 1 | Primary load metric for mountain sports; max 10%/wk increase | GPS watch / self-report |
| Night Running Experience | Y/N | 2 | 100M ultra + multi-day AR: 2–3 night sessions mandatory in peak phase | Self-report |
| Gut Training History | Number (g/hr CHO sustained without GI distress) + issues | 1 | Ultra finisher avg 70 g/hr, non-finisher <45 g/hr; 8–12 wk gut training to bridge gap | Training log |

(Threshold/Tempo Pace was a v1 field here. Now in §F.)

### D.2 Cycling

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Bike Types Available | Multi-select (Road/Gravel/MTB-HT/MTB-FS/TT-Tri/CX/Trainer-only) | 1 | XTERRA/AR require MTB; TT events require TT/tri bike | Multi-select |
| MTB Technical Skill | Enum (Beginner/Intermediate/Advanced) | 1 | Cannot start at race-difficulty terrain without skill base; 2 hard tech sessions/wk CNS cap | Self-report |
| Longest Ride (12 mo) | Distance + time, self-supported flag | 2 | Endurance baseline; peak training ride targets 70–80% of event distance | Manual entry from FIT export at launch; Connected Service post-launch |
| Saddle Endurance | Longest comfortable consecutive hours + issues | 2 | Events >4 hr saddle-limited not aerobic-limited; <2 hr → can't jump to 6 hr training. Soft warning at plan gen for any cycling event >4 hr (Plan Management classification table) | Self-report |
| Aero Position Endurance (TT only) | Time (min) sustainable + issues | 2 | TT FTP 3–8% lower than road; start 20 min/session if new | Self-assessment during ride |

(FTP was a v1 field here. Now in §F.)

### D.3 Swimming

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Pool 100m Pace | Time (best in 6 mo) + flip turn Y/N | 1 | Calibration anchor; OW 5–10% slower than pool. (CSS — derived from a separate 400/200 TT protocol — lives in §F) | Self-test |
| Open Water Experience | Y/N + sessions/yr + distance + conditions + mass start Y/N + sighting confidence | 1 | No OW base = 4–8 wk specific OW adaptation before OW race | Self-report |
| Wetsuit Experience | Y/N trained or raced + transition comfort Y/N | 2 | New-to-wetsuit: 3–5 sessions before racing; T1 drill 2–4 sessions | Self-report |
| Cold Water Experience | Lowest temp (°C) + adverse reactions | 2 | <18°C race: 8–10 wk cold acclimatization; cold shock = drowning risk | Self-report |
| OW Marathon Feeding Experience | Y/N + sessions practiced (pontoon feeding rolling-on-back) | 2 | OW marathon: feed every 2.5 km; 15–20 sessions to automate technique | Self-report |
| Weekly Swim Volume | km/wk + sessions/wk | 1 | Starting prescription anchor; OW marathon target 40–60 km/wk | Self-report / log |

### D.4 Paddling (Kayak / Canoe / Packraft)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Kayak Experience | Enum (None/Rec/Intermediate/Competitive) + boat type | 1 | Tendon lag 4–8 wk; must start paddle training 8+ wk before race | Self-report |
| Canoe Experience | Enum (None/Rec/Competitive) + blade type (single/double) | 2 | C1/C2 single-blade is separate from kayak — limited transfer | Self-report |
| Packraft Experience | Enum (None/Rec/Race) + inflation comfort + river reading | 2 | None: 4–6 sessions minimum before racing | Self-report |
| Longest Paddle (12 mo) | Distance + time + water type | 2 | Endurance baseline; taper target 70–80% of event distance | Manual entry from FIT export at launch; Connected Service post-launch |
| Portage Fitness (canoe marathon) | Text + time estimate carrying boat | 2 | Portage running mechanically distinct; race-decisive at competitive level | Self-report |
| Continuous Forward Stroke | Time sustainable (min) | 1 | <30 min: technique before intervals | Self-report |

### D.5 Skiing (XC / Nordic / Skimo)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| XC Skiing Experience | Enum (None/Rec/Competitive) + technique (Classic/Skate/Both) + race Y/N | 1 | No XC base: 6–8 wk technique intro; biathlon = SKATE ONLY (no classic substitute) | Self-report |
| Snow Access Window | Months/year (specific months, multi-select Jan–Dec) | 1 | ≤3 mo snow: off-snow base must build full aerobic; max on-snow within window | Self-report — see §J Snow Access for detail |
| Skimo Experience | Enum (None/Rec/Competitive) + technique comfort + skin removal time if known | 1 | Requires both XC aerobic base AND alpine descent competency; transition speed measurable | Self-report + timed assessment |
| Alpine Descent Competency | Enum (Beg/Intermediate/Adv) + prior falls/injuries on descent | 1 | 65.6% skimo injuries on descent; beginner needs 10–15 days on skimo gear before race-format | Self-assessment + observed run |

### D.6 Navigation

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Map & Compass Proficiency | Enum (None / Basic / Intermediate / Advanced) | 1 | AR + Fell Running mandatory (GPS prohibited in fell); sleep dep ES -2.12 (strongest discipline effect); novice = highest priority deficit regardless of fitness | Self-report + orienteering attendance |

### D.7 Technical Disciplines

(Renamed from v1 §E.7 "Strength & Technical Disciplines." Strength benchmarks — Pull-Up Maximum, Dead Hang Duration, Grip Strength — moved to §E.)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Rock Climbing Experience | Enum + grade + years | 1 | AR outdoor climbing requires indoor base; A2 pulley risk rises rapidly without base | Self-report |
| Abseiling Experience | Enum (None / 1–3 guided / 4+ incl. self-directed) + fear of heights Y/N | 1 | Distinct from climbing; AR mandatory; fear of heights = progressive exposure required | Self-report |
| Fencing Experience (épée) | Enum (None/Rec/Competitive) + years | 1 | Modern Pent: cannot self-teach; ≥6 mo coached before competition | Self-report |
| Shooting Experience | Per-sport enum (rifle for biathlon, laser pistol for pent) | 1 | Biathlon: cannot self-teach for competitive use; range frequency drives shooting plan design | Self-report |

---

## Section E — Strength, Core & Balance Benchmarks

These benchmarks gate progression chains in the exercise database (cols 14/15) and prevent prescribing advanced exercises to athletes who can't perform foundations. **Manual entry only** — these don't FIT-fill or Connected-Service-fill. Field is always asked at onboarding.

| Field | Type | Tier | Gates |
|---|---|---|---|
| Front plank hold time | Enum (0 / <30s / 30–60s / 60–90s / 90s+) | 1 | <60s: Plank is training exercise; don't prescribe Hollow Body, Ab Wheel, L-Sit |
| Dead bug — 10 controlled reps with flat back | Y/N | 1 | No: Dead Bug as primary core. Yes: clear for dynamic core |
| Side plank hold time (per side) | Enum (0 / <20s / 20–45s / 45s+) | 2 | <30s: Side Plank is training; flag lateral stability deficit |
| Push-ups (max single set) | Enum (0 / 1–10 / 11–25 / 26–50 / 50+) | 1 | 0–10: Push-up is training; no bench. 11–25: bench at light-mod. 26+: warm-up only |
| Bodyweight squat to parallel (heels down) | Y/N | 1 | No: ankle/hip mobility limiter — mobility + goblet squat before back squat |
| Single-leg squat to chair height | Y/N each side or "One side only" | 1 | No: start reverse lunge. One-side: flag asymmetry |
| **Pull-Up Maximum (strict)** | Integer reps + shoulder pain Y/N | 1 | Climbing prereq: ≥5 strict; OCR prereq: ≥8; tendon lag 4–8 wk |
| **Dead Hang Duration** | Seconds + grip-fail vs shoulder-fail | 1 | Climbing baseline: ≥40 s for confidence; differentiates intervention |
| **Grip Strength** | Number (kg, dynamometer) or category (weak/avg/strong) | 2 | Max 3 hard grip sessions/wk (tendon lag); fit but grip-untrained = 6+ wk before heavy work |

Bolded fields moved from v1 §E.7 ("Strength & Technical Disciplines") per `V2_spec_decisions_handoff.md` Decision 3. The v1 footnote that previously read "Pull-up max and dead hang are captured in E.7 — don't double-collect" is removed; these fields live in §E only.

§D.7 Technical Disciplines (Rock Climbing, Abseiling, Fencing, Shooting) reads Pull-Up Maximum and Dead Hang Duration from §E for climbing-prerequisite gating logic.

---

## Section F — Performance Testing Baselines (Aerobic & Lab)

Test-derived performance values that drive interval and zone prescription. UX guidance: prompt for FIT upload first, auto-populate from connected services where available, ask manual entry only as fallback.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Maximum Heart Rate (HRmax) | Number (bpm) + source (measured/estimated) | 1 | All HR zone calculations; beta blockers invalidate — RPE only | Manual entry from FIT export at launch; Connected Service post-launch; Tanaka (208 - 0.7×age) fallback |
| Lactate Threshold HR | Number (bpm) + method | 2 | Primary intensity anchor for threshold zones | Manual entry from FIT export (30-min hard effort avg HR) or lab test |
| VO2max Estimate | Number (ml/kg/min) + source | 3 | Aerobic capacity ceiling; -1 to -2% per 300m above 1500m altitude | Manual entry from wearable export or Cooper test |
| Cycling FTP | Number (W) + test date | 2 | All cycling zones; W/kg climbing performance. FTP decays 5–7% over 6–8 wk without maintenance — re-test cadence. Soft warning at plan gen if cycling intervals scheduled (see Plan Management classification table) | 20-min TT or ramp test |
| Running Threshold Pace | Pace (min:sec/km or /mile) + test date | 2 | Run interval prescription; parallels FTP for cycling. Soft warning at plan gen if running threshold intervals scheduled (see Plan Management). New in v2 | Standard test: 30-min time trial, average pace over the final 20 min = threshold pace. 5K race pace is an acceptable proxy when no recent TT exists |
| Critical Swim Speed (CSS) | Time (min:sec/100m) + test date | 2 | Pool interval prescription; re-test every 8–10 wk. Soft warning at plan gen if pool intervals scheduled (see Plan Management) | 400m TT + 200m TT |

**Section banner (UX guidance):**

> "Upload your most recent activity FIT file or your wellness FIT and we'll auto-populate what we can. Otherwise enter manually below. We'll prompt you to update these as you re-test."

**Soft-warning linkage:** Each Tier 2/3 field's plan-generation behaviour when missing is captured in the Plan Management profile-update spec's classification table. The linkage is explicit in v2 (was implicit in v1).

**Migrations from v1:** Cycling FTP value moves here from v1 §E.2 (v1 split it inconsistently — value in §E.2, test date in §G). Running Threshold Pace is new in v2; the v1 §E.1 "Threshold/Tempo Pace" baseline is replaced by this single canonical home.

---

## Section G — Schedule & Availability

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Available Training Hours per Week | Number (hrs) + variability note | 1 | Hard ceiling on phase load allocation | Self-report + lifestyle audit |
| Training Days Available | Day-of-week multi-select | 1 | Long workout placement; recovery day; doubles feasibility. Days not selected are unavailable for any session | Self-report |
| Preferred Rest Day(s) | Day-of-week single or multi-select | 1 | Hard constraint on rest day | Self-report |
| Typical Session Duration | Enum (30/45/60/90 min / 2 hr / 3+ hr) | 1 | Determines exercise count and warm-up allocation | Self-report |
| Long Session Available | Y/N + day + max duration (2/3/4/5/6/8+ hr) | 1 | Long run/ride/hike ceiling per week | Self-report |
| Doubles Feasible | Enum (Regularly / Occasionally / No) | 1 | Two-discipline days; brick scheduling. Promoted from Tier 2 to Tier 1 in v2 — multi-discipline sports (AR, triathlon, multi-sport) cannot generate a viable plan without this | Self-report |

**Removed from v1:**
- ~~Time-of-Day Preferences~~ (Tier 3, low signal-to-effort)
- ~~Recurring Conflicts~~ (was a free-text sub-field on Training Days Available; redundant at day-level with Training Days Available — if a day is conflicted, deselect it. v2 does not track hour-granularity recurring blocks)

**Cross-reference to §K:**

§G captures the athlete's *typical weekly* availability. §K (Locale Schedule) overlays specific date ranges for travel, blackout periods, alternate locales, and date-bound joint training. Plan generation reads §G first (default schedule), then applies §K overlays for any covered dates.

---

## Section H — Target Events

§H is conditional. The H.1 prefix gate determines whether the athlete is training for a specific event (H.2 fills) or following a time-based plan (H.3 fills). Multiple events supported in H.2 — periodisation runs around primary (nearest or highest priority).

### H.1 Event mode gate

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Specific event Y/N | Y/N | 1 | Routes to H.2 (Yes) or H.3 (No). Yes → backward periodisation from event date. No → forward from start date with selected Plan Duration | Self-report |

### H.2 Event details (when H.1 = Yes)

Multiple event records supported. Each event contains:

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Event Name | Free text | 1 | Identification | Self-report |
| Event Date | Date | 1 | Backward periodisation; phase durations | Self-report |
| Event URL | URL (optional) | 3 | System can fetch course updates, mandatory gear changes, complications | Self-report |
| Target Sport / Format | Enum (from 18 sports + sub-format in `Sports_Framework_v3.xlsx`) | 1 | Disciplines, phase load, sport-specific protocols | Single-select |
| Constituent Disciplines | Multi-select (pre-populated from event type) | 1 | Exercise pool union; not all ARs include packrafting; not all triathlons same distances | Multi-select |
| Race Distance + Estimated Duration | km + hours (athlete's expected, not elite) | 1 | Nutrition planning; **>20 hr triggers collection of §I Sleep Deprivation Experience field** (v2 change — was an internal flag only in v1) | Self-report + race info |
| Race Elevation Gain / Loss | m gain + m loss | 1 | Vertical training targets; downhill EIMD exposure | Race website |
| Race Terrain Type | Multi-select with % breakdown | 1 | Peak-phase terrain must match race; flat→technical = 8–12 wk specific exposure | Race website |
| Race Pack Weight + Mandatory Kit | kg + kit list | 1 | Load calc for hiking/running EE; weighted vest training simulation | Race rules doc |
| Navigation Requirement | Enum (Fully marked / Checkpoints marked / Plot own / Self-directed) | 1 | Activates D-013 training; novice + plot-own = highest priority deficit | Race rules |
| Team Format | Enum (Individual / Unified Team / Relay / Doubles) + role | 1 | Unified: train all disciplines. Relay: assigned leg only. Team ceiling = weakest member. **Non-Individual values activate §L Athlete Link collection (Race Teammate relationship type) for this event** — replaces v1 §N "Competing with team" Y/N gate | Athlete + linking flow |
| Goal Outcome | Enum (Finish / Compete mid-pack / Podium attempt) + time goal + first-time-at-distance Y/N | 1 | Finish: injury-prevention focus. Competitive: intensity periodization. Podium: precision + testing cadence | Self-report |
| Previous Attempts | Y/N + outcome (Finish/DNF/DNS) + DNF cause text | 2 | Documented DNF point = highest training priority (e.g., "quad failure mile 68" → D-023 top priority) | Self-report |
| Known Event Complications | Free text + system-suggested via URL fetch | 2 | Surfaces specific terrain/conditions to train for: Heartbreak Hill, river crossings, altitude, exposed ridgelines | Self-report; pre-fetched from Event URL where possible |
| Number of Transition Areas | Integer (multi-sport races only) | 2 | Brick training cadence; transition drill volume. Conditional on Constituent Disciplines containing 2+ disciplines requiring TAs | Self-report or Event URL |
| Number of Aid Stations | Integer + spacing if known | 2 | Self-sustainment pack weight calculation; fueling spacing strategy. Athlete-unknown fallback: Plan Management defaults conservatively (assume sparse aid) | Self-report or Event URL |
| Race-Specific Nutrition Restrictions | Free text | 2 | Distinct from §I dietary pattern. Example: vegan athlete (§I) at race with non-vegan aid → must self-pack everything | Self-report |

**Help text on Estimated Duration:** "If your race has a cutoff time and you don't know your expected finish, enter the cutoff." Resolves V2 spec decisions handoff Deferred #4 — UX clarification, not a data-model change.

**Sleep deprivation field collection:** When Estimated Duration > 20 hr, the system prompts the athlete to fill the §I Sleep Deprivation Experience field as a conditional collection step. This replaces v1's internal-flag-only behaviour where >20 hr just triggered the night-across session protocol invisibly.

**Race-day fueling fields are NOT in §H.** They're in §I (Lifestyle & Recovery) as athlete-level characteristics — caffeine response, fueling format preference, GI triggers, salt tolerance don't change race-to-race. What does change race-to-race (aid station stocking, mandatory kit fueling rules, cup vs. soft-flask handling) is event metadata captured implicitly in the Event URL fetch and Race Rules.

### H.3 No-event mode (when H.1 = No)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Plan Duration | Enum (8 / 12 / 16 / 20 / 24 weeks) | 1 | Phase durations and forward periodisation. Maximum 24 weeks | Self-report |

**On no-event disciplines:** When H.1 = No, Constituent Disciplines is derived from §C Primary Sport defaults + §C Secondary Sports rather than asked again. §C Discipline Weighting drives proportional volume allocation.

**On Plan Duration max = 24 weeks:** The user-facing maximum is 24 weeks. Generation strategy for weeks 13+ is unresolved — options under consideration are (a) simpler/cheaper LLM for later weeks, (b) generate weeks 1–12 only and produce a re-gen handoff for weeks 13+ as the plan progresses. Decided pre-launch. Tracked as Open Item #9.

---

## Section I — Lifestyle & Recovery

*Was v1 §J.*

> **Section scope:** These fields describe stable athlete characteristics — how your body responds to fueling, stress, and sleep deprivation. They apply across all events and plan cycles. What changes race-to-race (aid station spacing, mandatory kit) is a plan output, not a profile input.

### I.1 Core lifestyle fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Average Nightly Sleep | Number (hours, 0.5 increments) + subjective quality (Poor / Fair / Good / Excellent) | 1 | Sleep deficit modelling; recovery day placement; consecutive hard-day limits | Self-report |
| Work / Life Stress Level | Enum (Low / Moderate / High / Variable) | 1 | Weekly volume ceiling; rest day frequency; hard session placement | Self-report |
| Dietary Pattern | Multi-select (Omnivore / Vegetarian / Vegan / Dairy-free / Gluten-free / Halal / Other) + free text | 2 | Nutrition recommendations; supplement suggestions that are pattern-compatible | Self-report |
| Current Supplement Protocol | Free text | 2 | Cross-reference at plan generation; avoids double-recommending what athlete already takes | Self-report |
| Caffeine Tolerance & Strategy | Enum (None / Low — 1 cup/day or less / Moderate — 2–3 cups/day / High — 4+ cups/day) + daily mg estimate (optional) | 2 | Training-day caffeine windows; pre-workout recommendations; gates race-day sub-question | Self-report |
| Altitude Acclimatization History | Y/N + altitude range (m) + approximate exposure count | 3 | Pacing adjustments for altitude events; VO2max correction (-1 to -2% per 300m above 1500m) if athlete has known acclimatization capacity | Self-report |

**Dropped from v1:** Heat Acclimatization History — replaced by system tracking via workout date + location + weather API in Plan Management (see Group 3).

#### I.1.1 Race-day Caffeine Strategy

Sub-question on Caffeine Tolerance & Strategy. Collected when Caffeine Tolerance ≠ None.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Race-day Caffeine Strategy | Enum (Same as daily / Loaded — abstain 7–14d pre-race then peak on race day / Avoid race-day entirely / Variable by event length) | 2 | Race-week protocol: Loaded users need 10–14d abstinence window in taper; Avoid users skip caffeine planning entirely | Self-report |
| Intended race-day dose | Number (mg, optional) | 3 | Refines timing and carrier-format recommendations (pill vs. gel vs. drink) | Self-report |

**Implementation note:** The Caffeine Tolerance & Strategy field may be restructured into a record substructure (parallel to Pack Training Record) if v2 engineering decides the sub-question warrants it. Either is compatible with this spec; the field inventory is the same.

### I.2 Race-day fueling preferences

These fields describe physiological characteristics that are stable across events. They drive plan-gen outputs — what to carry, what to train the gut toward, what to avoid at aid stations.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Fueling Format Preference | Multi-select with priority ranking (Real food / Gels / Chews / Liquid carbs / Mix — no strong preference) + free text comments | 2 | Race nutrition planning: what the plan recommends carrying; which aid station formats to prioritize or avoid; gut-training session design (progressive real-food tolerance for AR) | Self-report |
| Known Race-day GI Triggers | Free text (foods, formats, timings that caused GI distress in past races or long training sessions) | 2 | Avoid in race nutrition recommendations; flag aid stations serving trigger foods; inform mid-race contingency plan | Self-report |
| Salt / Electrolyte Tolerance | Enum (Low — cramps even with replacement / Standard / High — heavy sweater, high salt loss) + preferred form (Capsule / Drink mix / Chew / Food-based / No preference) | 2 | Hot-weather plan adjustments; race fueling sodium target (typical range 300–1000 mg/hr scaled to tolerance band); cramping risk flag for plans with high-heat event dates | Self-report |

### I.3 Sleep deprivation experience

**Conditional:** collected only when §H Target Event record has Estimated Duration > 20 hr.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Sleep Deprivation Experience | Hours awake in longest prior sustained effort + notable incidents (hallucinations Y/N, decision failures Y/N, nausea Y/N, involuntary sleep Y/N) + free text context | 2 | Capacity model for overnight event planning; mandatory night-across session timing in peak phase; sleep-dep mitigation strategy (strategic napping windows, caffeine timing) | Self-report |

**Trigger logic:** When Estimated Duration is updated on any §H Target Event and crosses 20 hr, §I prompts for this field if not already collected. Remains in profile until athlete removes all >20hr events.

---

## Section J — Locales

*Was v1 §K. Largest single section in the spec.*

A Locale is a geographic base from which the athlete trains. Most athletes have one primary locale (home) and may add travel locales. Equipment, terrain access, and gear readiness are stored per locale.

**Proximity model (replaces v1 parent-child FK):**

Each Locale has coordinates derived from a place lookup at creation. The system computes a proximity cluster using a default radius of **26.2 mi / 42.2 km** — locales within this radius of the active locale are treated as co-accessible (their equipment and terrain pools union into the active set). The athlete can manually override: explicitly link two locales the system didn't catch, or unlink two it linked incorrectly. Manual overrides persist across proximity recalculations.

Gear readiness toggles are **not** inferred from proximity. A climbing gym two miles away does not imply the athlete has climbing hardware at that locale. Toggles are explicit per-locale.

### J.1 Locale-level fields

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Locale Name | Text (e.g., "Home — Austin", "Nashville hotel", "In-laws — Portland") | 1 | Display label only | Self-report |
| Location | Place lookup → lat/long (auto-filled; athlete can correct) | 1 | Proximity cluster computation; terrain defaults; weather-API heat tracking; event travel distance estimates | Place lookup |
| Gym Chain Memberships | Multi-select from chain list (e.g., Planet Fitness, LA Fitness, Anytime Fitness, YMCA) + "Independent gym" option | 2 | When athlete sets a new travel locale in the same chain, system surfaces stored gym-equipment profile as a starting point; reduces re-entry burden for frequent travelers | Self-report |
| Is Primary Locale | Boolean | 1 | Designates the home base; first locale created defaults to primary | System-set (athlete can override) |

**Dropped from v1:** Linked Primary Locale FK — replaced by proximity model above.

### J.2 Equipment Inventory

Equipment availability at this locale. Structured as a checklist against the canonical equipment list from `Vocabulary_Audit_v2.md` §3 (121 items across 17 categories + 9 Assumed Universal items).

**Assumed Universal items** (always present, not on the checklist): Bodyweight, Wall, Doorway, Chair, Floor, Stairs, Backpack, Timer, Tape measure.

**v2 changes vs v1 equipment list:**

| Change | Items |
|---|---|
| Added | Bench (flat), Foam pad, Incline board |
| Dropped | Jacob's Ladder, Compression boots (Normatec), Sauna access, Stretch strap |
| Renamed / consolidated | Per `Vocabulary_Audit_v2.md` §5 rename table — e.g., "Band" → "Resistance Band", "MTB" → "Mountain Bike", "Cable" → "Cable Machine" |

The full canonical equipment list is the authoritative reference. The UI checklist presents items grouped by category (Barbells & Bars / Dumbbells / Kettlebells / Machines / Bodyweight & Portable / etc.).

### J.3 Sport-Specific Gear Readiness Toggles

12 rolled-up sport-specific gear readiness toggles replace v1's sub-component checklists. Canonical toggle names are defined in `Vocabulary_Audit_v2.md` §4.1. Each toggle is a binary ready/not-ready state at the locale level.

| Toggle (canonical name per Vocabulary_Audit_v2 §4.1) | Tier | What it gates |
|---|---|---|
| Climbing — roped | 2 | Lead climbing, top-rope, multi-pitch exercise selection; also satisfies Rappelling / abseiling check |
| Bouldering | 2 | Bouldering-specific exercise selection |
| Rappelling / abseiling | 2 | Rappel / abseil sessions; also satisfied by Climbing — roped (roped passes rappelling) |
| Via ferrata | 2 | Via ferrata sessions |
| Mountaineering | 2 | Alpine / glacier sessions; hard gate without avalanche safety endorsement on col-type terrain |
| Whitewater paddling setup | 2 | Whitewater kayak / packraft sessions above Class II |
| Touring / AT ski setup | 2 | Ski mountaineering, randonnée sessions |
| Classic XC ski setup | 2 | Classic cross-country ski sessions |
| Skate XC ski setup | 2 | Skate cross-country ski sessions |
| Fencing setup | 2 | Fencing technical drills; modern pentathlon fencing leg |
| Shooting setup | 2 | Biathlon / modern pentathlon shooting sessions (range access implicit) |
| Snowshoeing setup | 2 | Snowshoe-specific conditioning sessions. Note: snowshoes are a single-item kit — this toggle is effectively "snowshoes present Y/N" with no sub-component rollup |

**Roped climbing passes rappelling check:** an athlete with Climbing — roped enabled is assumed to have gear sufficient for rappelling. The reverse is not true.

### J.4 Terrain Access

Terrain types available within practical reach of this locale. Drives session location planning and exercise selection for terrain-specific skills.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Terrain types | Multi-select from `Vocabulary_Audit_v2.md` §3 terrain canonical list (15 types — e.g., Trail access, Hill / mountain access, Flat road, Whitewater access, Snow terrain, Open water access, Indoor climbing wall) | 1 | Session planning; terrain-specific exercise eligibility; identifies gaps (e.g., no hills → hill-substitute programming) | Self-report |
| Seasonality | Per terrain type: climate-derived defaults (system infers from locale lat/long + month) + per-month athlete override | 2 | Disables terrain types in months when unavailable; adjusts to athlete's local reality (e.g., snow earlier/later than climate average) | System + self-report |

### J.5 Locale Capacity Metrics

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Typical session time available | Enum (< 45 min / 45–60 min / 60–90 min / 90–120 min / > 120 min) | 2 | Session length defaults when this locale is active; shorter windows prioritize compound movements and drop accessory work | Self-report |
| Max session duration (hard constraint) | Number (minutes, optional) | 3 | Hard cap applied at plan generation; no session exceeds this limit at this locale | Self-report |

---

## Section K — Locale Schedule

*Was v1 §L. Expanded to host joint-training overlays and recurrence templates.*

A Locale Schedule overlay is a date-range record that overrides or supplements the athlete's default weekly schedule. Three sub-types:

- **K.1 Self-overlays** — travel, blackout, locale switch, constraints
- **K.2 Joint-training overlays** — same structure as K.1 plus joint-training-specific fields when linked to an Athlete Link
- **K.3 Recurrence templates** — generates K.1 or K.2 instances on a rolling forward window

All overlay types share the base fields in K.1. Joint-training overlays add the K.2 fields on top.

### K.1 Self-overlays (base overlay fields — applies to all types)

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Start Date | Date | 1 | Overlay window start | Self-report |
| End Date | Date | 1 | Overlay window end | Self-report |
| Active Locale | FK to Locale (J.1) | 1 | Equipment pool and terrain available during this window; if null, inherits current primary locale | Self-report |
| Date-Specific Constraints | Multi-select (At home only / Indoor only / Short sessions only / Other) + free text when Other | 2 | Session type restrictions during overlay window; plan-gen applies these on top of the active locale's normal profile | Self-report |
| Notes | Free text | 3 | Context for planner; not machine-read | Self-report |

### K.2 Joint-training overlay fields

Additional fields present when the overlay is linked to an Athlete Link. Can be added to any K.1 overlay at creation or retroactively.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Joint Training Link | FK to Athlete Link (§L) | 1 | Identifies which training partner this overlay concerns; gates K.2 fields | Self-report |
| Joint Training Status | Enum (Proposed / Accepted / Declined / Expired) | 1 | Plan-gen only reads Accepted overlays for joint sessions; Declined records preserved for proposer audit trail | Self-report; updated by linked athlete |
| Proposed By | FK to user account | 1 | Identifies who initiated; system-set | System-set |
| Notes from Proposer | Free text | 3 | Context passed to linked athlete with invitation | Self-report |
| Source | Enum (Single / Generated-from-Recurring) | 1 | Identifies whether this instance was created manually or auto-generated from a K.3 template | System-set |
| Parent Recurrence | FK to K.3 Recurring template (nullable) | 1 | Set when Source = Generated-from-Recurring; null for Single instances | System-set |

**Storage model:** when User A proposes and User B accepts, two overlay records are created — one in each athlete's §K — linked by a shared joint-training-instance ID. Declined records are not deleted; they remain visible to the proposer as an audit trail.

**Plan-gen reads Accepted joint overlays as follows:** for the dates covered, each athlete's existing prescription is read; plan-gen seeks the session design most beneficial to both given their respective phases, the resolved locale's terrain and equipment, and the Proposer's Notes as tiebreaker context (not as override instruction).

### K.3 Recurrence templates

A Recurrence template defines a repeating joint-training pattern and generates individual K.1/K.2 instances on a rolling forward window (default 8 weeks; finalize with engineering per Open Item #10).

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Pattern | Enum (Weekly / Biweekly) + Day-of-week multi-select (Sun–Sat, 1+) | 1 | Forward-generation schedule | Self-report |
| Start Date | Date | 1 | First possible generated instance | Self-report |
| End Date | Date (nullable — open-ended if null) | 2 | Last possible generated instance; null = ongoing until cancelled | Self-report |
| Template Status | Enum (Active / Cancelled) | 1 | Cancelling halts forward generation; already-generated future instances are not auto-deleted — each requires individual handling | System-set (athlete action) |
| Inherited overlay fields | Active Locale, Date-Specific Constraints, Joint Training Link (if joint template), Notes from Proposer | — | Copied to each generated instance at generation time; instance-level overrides do not affect the template | Self-report (at template creation) |

**Instance audit trail:** generated instances carry Parent Recurrence FK and Source = Generated-from-Recurring. If the template is later cancelled, already-generated instances retain the FK to the cancelled template — the Status = Cancelled on the template is the signal, not a null FK.

**Single-instance override:** either party in a joint recurring template can modify an individual generated instance (change locale, decline that date, adjust constraints) without touching the template.

---

## Section L — Athlete Network

*New in v2. Takes the §N letter slot. Replaces v1's inline Training Partner record on §L and the v1 Team Composition Record on §N.*

**Sole authoritative source for this section:** `V2_spec_decisions_handoff.md` Decision 1. Do not re-incorporate fields from the deleted `Athlete_Link_Entity_v2.md` — that version is superseded.

### L.1 Athlete Link

One record per training partner or race teammate. A single Athlete Link can carry both relationship types simultaneously.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Partner Name | Text (display name) | 1 | Displayed in joint overlay UI, team composition view, and plan notes | Self-report |
| Linked Account | FK to user account (optional) | 2 | When set: changes to the linked athlete's profile propagate to shared plan adjustments per Plan Management spec; consent flow in Account Configuration | Consent flow (Account Config) |
| Relationship Types | Multi-select: Solo Training Partner / Race Teammate (at least one required) | 1 | Gates conditional fields below; drives §K joint-training overlay collection; for Race Teammate: drives team ceiling logic, role assignment, cross-plan alignment | Self-report |
| Partner-specific Rules | Free text | 3 | E.g., "limit hikes to 2 hours", "prefers morning sessions". Read by plan-gen as soft constraints on joint sessions | Self-report |

### L.2 Race Teammate conditional fields

Collected when Relationship Types includes Race Teammate.

| Field | Type | Tier | Drives | Source |
|---|---|---|---|---|
| Race Event Association | FK to §H Target Event (1 or more; same Athlete Link can cover multiple events) | 1 | Links this teammate relationship to specific events; gates discipline focus collection; drives team ceiling = slowest-member logic per associated event | Self-report |
| Discipline Focus on Team | Multi-select from the associated event's Constituent Disciplines | 2 | For relay-style events and AR with delegated legs: informs cross-training framing on joint dates; affects which teammate's baseline is the constraint for each discipline | Self-report |

**What was removed vs. earlier drafts:** Role on Team enum (Captain / Navigator / Pacer / Specialist) and Discipline-specific role notes. These were in the deleted `Athlete_Link_Entity_v2.md`. Discipline Focus on Team captures the functionally important information without the role taxonomy.

**Not modelled:** Coach, Training Group, Race Crew — out of scope. Team-training spec to revisit if evidence of need emerges post-launch.

---

# Group 2 — Account Configuration

Account-level entities. Not plan-gen inputs directly — they determine *what data the system can pull* and *what the athlete has consented to*.

## Account Config 1 — Connected Services

One record per integrated third-party service. Source of athlete activity data (FIT files, wellness sync).

| Field | Type | Notes |
|---|---|---|
| Service Name | Enum (Garmin / Strava / Apple Health / Polar / Wahoo / Suunto / COROS — extendable) | Launch tier: Garmin, Strava, Apple Health |
| Connection Status | Enum (Connected / Disconnected / Auth Error / Sync Paused) | System-set |
| Last Sync | Timestamp | System-set |
| Scopes Granted | Multi-select (Activity data / Wellness / Sleep / HR / Power / GPS track) | System-set from OAuth flow; athlete cannot grant scopes the service doesn't offer |
| Sync Direction | Enum (Pull only / Push only / Bidirectional) | System-set per service integration; Garmin = Pull at launch |

**At launch:** Connected Services are manual-upload equivalents (FIT file upload). OAuth integration is the post-launch upgrade path. Section wording at launch should reflect manual-upload-at-launch posture per v2 spec note.

**Effect side lives in Plan Management.** When a Connected Service connects, disconnects, or errors, the athlete-data effects (field auto-fill, staleness flags, re-test prompts) are handled in Group 3 (M.2 Account Config events).

## Account Config 2 — Gym Memberships

| Field | Type | Notes |
|---|---|---|
| Gym Chain | Text or FK to chain list | Athlete adds the chains they have active memberships at |
| Membership Active | Boolean | Inactive memberships are retained for history but not surfaced in locale setup |

**Drives:** when athlete creates a new locale in a city where a member-chain has locations, system surfaces the stored gym-equipment profile from another locale at that chain as a starting point for J.2. Does not auto-set equipment — surfaces as suggestion for athlete to confirm.

## Account Config 3 — Disclosure Acknowledgment Records

Storage backing for §A.1 disclosures. One record per disclosure type per acknowledgment event.

| Field | Type | Notes |
|---|---|---|
| Disclosure Type | FK to disclosure category (from §A.1) | E.g., Medical disclaimer, Data use, Injury liability |
| Acknowledged At | Timestamp | System-set on athlete confirmation |
| Version Seen | Text (disclosure version string) | Enables re-prompt when disclosure copy changes materially |
| Delivery Method | Enum (In-app / Email) | Audit trail |

**Pre-launch blocker:** disclosure copy is PLACEHOLDER — refine with product/legal before ship (Open Item #1).

## Account Config 4 — Privacy and Linked-Partner Sharing

One record per Athlete Link (§L) where Linked Account is set.

| Field | Type | Notes |
|---|---|---|
| Athlete Link | FK to Athlete Link (§L) | The relationship this consent applies to |
| Consent Scope | Enum (None — name only / Activity summaries — session completion, duration, discipline / Full plan access — all prescriptions visible to linked partner) | Athlete controls; defaults to None until explicitly upgraded |
| Consent Granted At | Timestamp | System-set on consent action |
| Consent Revoked At | Timestamp (nullable) | System-set on revocation; revocation strips linked-data scope immediately and flags the Athlete Link as name-only |

**Multi-partner consent (N>2):** partial-link behaviour decided (link forms, non-consenters see nothing); detailed UX deferred to team-training spec (Open Item #12).

---

# Group 3 — Plan Management

Lifecycle events and runtime logic. Not athlete-facing data points — these are how the system responds to data changes, plan signals, and account events.

## Plan Management 1 — Plan Duration and Event Prefix Logic

When §H.1 (Specific Event?) = Yes:
- Plan duration is derived from today → event date, subject to the minimum base phase for each constituent discipline (from `Sports_Framework_v6.xlsx` Discipline Library).
- If timeline is too short for a legitimate plan, system surfaces an honest assessment and does not generate a plan that sets the athlete up to fail.

When §H.1 (Specific Event?) = No:
- Athlete selects Plan Duration from enum: 8 / 12 / 16 / 20 / 24 weeks.
- Maximum 24 weeks user-facing. Generation strategy for weeks 13+ is Open Item #9 — options are (a) simpler/cheaper LLM for later weeks, (b) generate weeks 1–12 only and produce a re-gen handoff for weeks 13+. Decide pre-launch.

## Plan Management 2 — Profile Update Triggers (§M)

*Slotted from `Sections_GHMN_v2_Batch.md` §M.1–M.4.*

### M.1 Athlete data lifecycle triggers

| Trigger | What updates |
|---|---|
| Athlete adds new locale | Prompt for J.2–J.5 fields at new locale |
| Athlete flags existing locale as changed | Re-prompt equipment at that locale only |
| Athlete switches to previously-configured locale | No prompt — use stored profile |
| Athlete switches to unconfigured travel locale | Default to bodyweight-only; prompt to configure when ready |
| **Athlete updates equipment availability at a locale** | Re-evaluate exercise pool for that locale |
| **Athlete toggles a sport-specific gear readiness state** (acquires or loses kit) | Re-evaluate exercise pool for that locale; flag any in-flight plan sessions affected |
| Athlete reports new injury | Create injury record; immediately apply filtering |
| Athlete updates injury status | Update record; relax/tighten filtering |
| Athlete reports injury resolved | Move to history; retain for preventive priority |
| **Athlete reports new health condition** | Create Health Condition record; apply system-category filtering |
| **Athlete updates health condition status** | Update record; apply Current vs History filtering rules |
| **Athlete reports health condition resolved / inactive** | Set Status = History; retain for context |
| Athlete completes benchmark reassessment | Update benchmarks; unlock progressions |
| New event added to §H | Recalculate periodisation; confirm event disciplines + terrain; trigger Sleep Dep prompt if Estimated Duration > 20 hr |
| Event details change (URL fetch) | Flag changes; adjust terrain-specific exercise selection |
| Season changes (inferred from weather + month) | Adjust terrain and session planning per locale seasonality |
| Athlete completes a training block | Prompt for benchmark re-test |
| **Athlete reports plan adherence dropping** *(self-reported)* | Branch to root cause: bored / busy / injured / ill / life stress. Each branch routes to its own response. Full branching logic in `Adherence_Drop_Spec_v2.md` |
| **System detects plan adherence dropping** *(4 consecutive flagged sessions)* | Fire adherence-drop prompt; route through opt-in confirmation per branch. Full detection logic, periodisation overrides, and stacking rules in `Adherence_Drop_Spec_v2.md` |

**Bolded rows are new in v2.**

### M.2 Account Config events that affect athlete data

| Account Config event | Athlete data effect |
|---|---|
| Connected Service connects | Begin pulling activity / wellness data; offer to backfill §F fields if values aren't present |
| Connected Service disconnects | Stop auto-fill; flag fields as stale at next plan generation; revert to manual-entry expectations |
| Connected Service scope reduced | Re-check which fields can still auto-fill; prompt athlete for any newly-uncovered fields |
| Connected Service auth fails / sync stops | Stale-data warning at plan generation; prompt athlete to reconnect |
| Gym membership added | Surface gym-equipment profile suggestions at any locale in that chain |
| Gym membership removed | Re-evaluate whether gym-dependent exercises remain valid at affected locales |

### M.3 Adherence-drop detection threshold

**4 consecutive flagged sessions** triggers the adherence-drop prompt. A session is flagged when: skipped, volume short (<70% of prescribed), volume over (>130%), or intensity off by >2 RPE in either direction. Full detection logic, branching, athlete-facing prompts, periodisation overrides, and stacking rules: see `Adherence_Drop_Spec_v2.md`.

### M.4 Soft Warning / Hard Gate / Profile Prompt classification

| Classification | Behaviour | Examples |
|---|---|---|
| **Hard gate** | Plan generation is blocked. Clear reason given. Athlete must resolve to proceed. | Missing HRmax when HR-zone training is planned; no pack-carry locale when pack-required event is in plan |
| **Soft warning** | Plan generates. Flag surfaces to athlete. No action required to proceed. | FTP not re-tested in >8 weeks and cycling intervals are scheduled; cycling event >4 hr without saddle endurance baseline |
| **Profile prompt** | Background nudge; no blocking. Athlete can dismiss. | "It's been 9 weeks since your last FTP test — would you like to schedule one?"; Sleep Dep field not collected for >20hr event |

Hard gates phrase as safety stops. Soft warnings phrase as flags for attention. Profile prompts phrase as nudges.

## Plan Management 3 — Joint Training Generation

When a §K Recurring template has Template Status = Active:

- System generates individual K.1/K.2 instances on a **rolling 8-week forward window** (finalize with engineering per Open Item #10).
- Generated instances default to Status = Proposed (joint templates) or accepted (self-templates), Source = Generated-from-Recurring, Parent Recurrence = FK.
- Either party can override a single generated instance (decline a specific date, change locale for one occurrence) without affecting the template.
- Cancelling the template halts forward generation. Already-generated future instances remain; each requires individual handling (athlete can decline, re-accept, or leave as-is).
- When both athletes in a joint template are at different locales for a generated date, system flags a locale mismatch and prompts reconciliation.

## Plan Management 4 — System-Tracked Heat Acclimatization

Replaces the dropped §I Heat Acclimatization History field.

- System infers heat exposure from workout date + active locale coordinates + weather API (temperature, humidity, heat index).
- Exposure accumulates toward acclimatization threshold (typically 10–14 days of training in ≥32°C / ≥90°F heat index conditions).
- Acclimatization state is not athlete-reported — it is derived and stored as a Plan Management record.
- When acclimatization is insufficient for an upcoming hot-weather event, system surfaces a soft warning and inserts heat-training sessions into the plan.

## Plan Management 5 — Multi-Athlete Plan Sync

**Out of scope for first v2 publish.**

How accepted joint-training overlays are read by plan generation to align prescriptions across athletes — the specifics of cross-plan coordination for linked athletes — are deferred to the team-training spec session. The data model (Athlete Link, §K joint overlays, consent scope in Account Config 4) is in place; the generation logic is not.

---

# Open Items

Genuinely deferred or in-progress. Items resolved during the May 2026 decisions session moved to the **Resolved decisions log** below. Renumbered post-batch-4+5 integration.

| # | Item | Source | Status |
|---|---|---|---|
| 1 | Disclosure copy refinement (§A.1) — placeholder copy drafted; legal review pending | Onboarding handoff #5; placeholder added May 2026 | Pre-launch blocker; product/legal owns |
| 2 | Movement Components structured field on exercise DB | Cross-layer (Layer 0 enhancement) | Deferred — Layer 0 enhancement, post-v2 |
| 3 | Re-injury risk model — Walk Status History; if ever Chronic-Managed or Structural-Permanent → permanent preventive priority post-resolution; otherwise per-Injury-Type decay (12-mo, 18-mo, or permanent depending on type) | Resolved May 2026 | **Integrated** — §B.1.2 |
| 4 | Sheet 7 deprecation execution — mark superseded once v2 spec is signed off | v1 Open Item; Onboarding handoff #8 | Mechanical action; trigger on v2 signoff |
| 5 | Migration path from current app database — needs current schema dump | Onboarding handoff #10 | Architecture hold; needs schema dump |
| 6 | Layer 1 ↔ Layer 0 query layer concrete spec | v1 To-Do #6 | **Next active workstream** |
| 7 | Health Condition auto-population (§B.4.2) — anaphylaxis, condition-specific meds, RHR outliers — three rules ship at launch | Resolved May 2026 | **Integrated** — §B.4.2 |
| 8 | Sports Framework Phase Load Allocation gap audit — full pre-launch audit, all 17 unverified sports (AR verified) | `V2_spec_decisions_handoff.md` Deferred #7 | Pre-launch audit; multi-session effort, track separately |
| 9 | Plan gen strategy for weeks 13+ — split-model: stronger LLM weeks 1–12, cheaper LLM weeks 13+ | Resolved May 2026; engineering implementation pending | Pre-launch decision; product/engineering |
| 10 | Recurring §K rolling-window length — direction set (8 weeks); confirm with engineering | Batch 4+5 | Direction set; close once engineering confirms |
| 11 | TA / aid station fallback — conservative default (assume sparse aid; full self-sustainment for max segment) | Resolved May 2026 | Plan-gen behaviour; integrate during plan-gen spec |
| 12 | Multi-partner consent rules (N>2) — partial-link behaviour decided (link forms, non-consenters see nothing); detailed UX deferred | `V2_spec_decisions_handoff.md` Deferred #17 | Direction set; detailed UX in team-training spec |
| 13 | Stale-link cleanup — never auto-archive; manual user action only | V2_Spec_Prep #25 | Direction set; team-training spec to formalize |
| 14 | Coach mode — out of scope (the app is the coach) | Resolved May 2026 | **Closed** — no further work |
| 15 | Linked-account consent flow — each athlete owns own plan; joint sessions appear on both with shared metadata; either can decline | Resolved May 2026; integrated in Account Config 4 | Direction set; full flow in Plan Management spec |

---

# Resolved decisions log (May 2026 session)

Decisions made in the May 2026 open-items review. Items marked **(integrate)** still need to land in spec body during the relevant batch; items marked **(closed)** require no further drafting. Status updated post batch-4+5 integration.

| # | Item | Decision | Integration target |
|---|---|---|---|
| 1 | Disclosure copy | Placeholder drafted; refine with legal pre-launch | **Integrated** — §A.1.1 |
| 2 | Movement Components on exercise DB col 9 | Keep free text; no structural change | **Closed** |
| 3 | Re-injury risk model | Walk Status History; if ever Chronic-Managed or Structural-Permanent → permanent preventive priority post-resolution. Otherwise per-Injury-Type decay (literature-grounded: 12-mo for acute soft tissue / nerve; 18-mo for non-surgical mechanical joint and stress fracture; permanent for tendinopathy and surgical mechanical joint; 6-mo for inflammatory; healing-window-only for non-stress bone and skin/surface) | **Integrated** — §B.1.2 (rule definition; Plan Management filter logic lives in Plan Management spec) |
| 4 | Sheet 7 deprecation timing | Mark superseded post-v2 signoff | Tracked as Open Item #4 (mechanical action) |
| 5 | Migration path | Defer until v2 rewrite complete | Tracked as Open Item #5 |
| 6 | Query layer concrete spec | Defer until schema built | Tracked as Open Item #6 |
| 7 | Health Condition auto-population (§B.4.2) | Ship all three named rules at launch (anaphylaxis, condition-specific meds, RHR outliers) with sex-adjusted RHR thresholds | **Integrated** — §B.4.2 |
| 8 | Sports Framework gap audit | Full pre-launch audit, all 17 unverified sports | Tracked as Open Item #8 (active) |
| 9 | Plan Duration weeks 13+ generation | Split-model: stronger LLM weeks 1–12, cheaper LLM weeks 13+ | **Integrated** — §H Plan Duration note + Plan Management 1 |
| 10 | §J Locale proximity radius default | 26.2 mi (km users: 42.2 km) | **Integrated** — §J |
| 11 | §J Locale manual link/unlink UX | Two buttons per locale: "Link to existing locale" picker + "Unlink from group" | **Integrated** — §J proximity model |
| 12 | §K Recurring overlay rolling-window length | Match Plan Duration (8 / 12 / 16 / 20 / 24 weeks) | **Integrated** — §K.3 + Plan Management 3 |
| 13 | TA / aid station fallback | Conservative default (assume sparse aid; full self-sustainment for max segment) | **(integrate)** Plan Management spec; cross-ref §H Number of Aid Stations — pending |
| 14 | Multi-partner consent (N>2) | Partial-link: link forms; non-consenters see nothing. Full UX deferred | **Integrated** — §L + Account Config 4; tracked as Open Item #12 |
| 15 | Stale-link cleanup | Never auto-archive; manual user action only | **Integrated** — §L direction; tracked as Open Item #13 |
| 16 | Coach mode | Out of scope; the app is the coach | **Closed** |
| 17 | Linked-account consent flow | Each athlete owns own plan; joint sessions appear on both with shared metadata; either can decline a proposed joint session | **Integrated** — Account Config 4 + Plan Management 3 |
| 18 | Sports_Framework_Handoff_v2 deprecation banner | Banner added May 2026 | **Closed** |

---

# What this spec is not

- **Not the UX flow.** What screens exist, what's collected upfront vs. deferred, what's a wizard vs. a settings page — separate design pass.
- **Not the database schema.** This is the data-point inventory schema is built from.
- **Not the prompt design.** Prompts reference schema fields. Schema comes first.

---

# Drafting status

| Section / Group | Status | Source |
|---|---|---|
| Front matter, structural reorg, Connected Services convention | ✅ Drafted (batch 1) | v2 drafting |
| §A Athlete Identity + A.1 Disclosures | ✅ Drafted (batch 1) | v2 drafting |
| §B Health Status (B, B.1, B.1.1, B.1.2, B.2, B.3, B.4, B.4.1, B.4.2) | ✅ Drafted (batch 1; §B.1.2 + §B.4.2 patched 2026-05-06) | v2 drafting |
| §C Training History & Fitness Baseline | ✅ Drafted (batch 2) | v2 drafting |
| §D Discipline-Specific Baselines | ✅ Drafted (batch 2) | v2 drafting |
| §E Strength, Core & Balance Benchmarks | ✅ Drafted (batch 2) | v2 drafting |
| §F Performance Testing | ✅ Drafted (batch 3) | v2 drafting |
| §G Schedule & Availability | ✅ Drafted (batch 3) | v2 drafting |
| §H Target Events | ✅ Drafted (batch 3) | v2 drafting |
| §I Lifestyle & Recovery | ✅ Drafted (batch 4) | v2 drafting |
| §J Locales | ✅ Drafted (batch 4) | v2 drafting |
| §K Locale Schedule | ✅ Drafted (batch 4) | v2 drafting |
| §L Athlete Network | ✅ Drafted (batch 5) | v2 drafting |
| Group 2 — Account Configuration | ✅ Drafted (batch 5) | v2 drafting |
| Group 3 — Plan Management | ✅ Drafted (batch 5) | v2 drafting |
