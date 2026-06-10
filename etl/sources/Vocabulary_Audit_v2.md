# Vocabulary Self-Pass — v2

**Built:** May 2026
**Supersedes:** `Vocabulary_Audit_v1.md`
**Resolves:** Onboarding handoff Open Items #1 (equipment vocab) and #2 (body part vocab)
**Sources reconciled:** `AR_Athlete_Onboarding_Schema.md` Section 2.2 · `AR_Exercise_Database_v17.xlsx` cols 7, 11, 13
**Status:** Canonical lists locked. Layer 0 cleanup actions and v2 spec changes flagged.

---

## What changed in v2 vs v1

1. **Systemic Constraints field eliminated.** Merged with Chronic Medical Conditions into a unified **Health Conditions** record-type field on Section B. Single record-type field, parallel structure to Injury Record.
2. **Sport-specific kit consolidated to one-token-per-kit-category.** Sub-component tokens (rope, harness, belay device, crampons, climbing skins, etc.) are removed from col 7 entirely. Each rolled-up category is one-to-one with its readiness toggle.
3. **XC skiing split into two kit-category tokens** (Classic XC ski setup, Skate XC ski setup). Touring/AT setup is one token. SkiMo and alpine descent ride on top of touring/AT setup.
4. **12 sport-specific gear-readiness toggles** locked as the canonical list (was open in v1).

---

## Naming convention decisions

1. **Body parts — hybrid naming.** Common-name where it adds no precision over anatomical (Lumbar → Lower back; Cervical → Neck; Thoracic → Upper back). Anatomical retained where athletes already know the term from their PT (Achilles, Plantar fascia, IT band, Soleus, Peroneal, Meniscus, ACL/PCL/MCL/LCL, TFL).
2. **Health Conditions absorbs Systemic Constraints + Chronic Medical Conditions.** ~70% overlap eliminated. System category enum below.
3. **Sub-region precision unified.** Where the proposed handoff list and col 13 each had entries the other lacked, both kept.
4. **Equipment slash-strings decomposed.** "Kayak / Packraft" type col 7 entries split into atomic items + OR-logic in the matching engine.
5. **Assumed-universal items.** Wall, Doorway, Floor, Anchor Point, Compass, Topographic Map, GPS — assumed available to every athlete in every locale. Not a checklist item, not a filter trigger.
6. **Over-collected AR Schema items removed.** Equipment listed in AR Schema 2.2 but never used in col 7 → dropped from the schema.
7. **Sport-specific kit rolled up to single token per category.** No sub-component tracking in col 7 or in onboarding. Single token in col 7 for the whole kit, matching one-to-one with the readiness toggle.

---

# Section 1 — Body Part Canonical List

For Injury Record `Body Part` field (Section B.1). Side picker (L/R/Both/N/A) is a separate field.

## Head / Neck

| Canonical | Source | Notes |
|---|---|---|
| Neck | proposed + col 13 (Neck, Cervical, Cervical Spine — all merged) | |
| Jaw | proposed | |
| Trapezius | col 13 | Spans neck/upper back/shoulder; kept distinct because col 13 uses it |
| Trachea | Exercise DB col-13 | Added v2.1 — airway contraindication flag |

## Shoulder

| Canonical | Source | Notes |
|---|---|---|
| Shoulder | both | Generic shoulder — the most-used label |
| Rotator cuff | proposed | |
| AC joint | proposed | |
| Shoulder blade | proposed | |

## Arm

| Canonical | Source | Notes |
|---|---|---|
| Elbow | both | |
| Forearm | both | |
| Wrist | both | |
| Hand | proposed | Generic hand; finer detail below |
| Bicep | col 13 | |
| Tricep | col 13 | |
| Fingers | proposed | Generic; finer detail below for climbing-specific |
| Thumb | proposed + col 13 | |
| Finger pulley | col 13 | Climbing-specific (pulley A1–A4 strain) |
| DIP joint | col 13 | Climbing-specific (distal finger joint) |
| CMC joint | col 13 | Climbing-specific (thumb base) |
| Biceps | Exercise DB col-13 | Added v2.1 — rename from "Bicep" |
| Triceps | Exercise DB col-13 | Added v2.1 — rename from "Tricep" |
| Thumb | Exercise DB col-13 | Added v2.1 |

## Back

| Canonical | Source | Notes |
|---|---|---|
| Upper back | proposed (col 13 "Thoracic" → translated per Option B) | |
| Lower back | proposed (col 13 "Lumbar" → translated per Option B) | |
| Spine (general) | col 13 | For non-region-specific spinal flags |
| SI joint | proposed (col 13 "Sacrum" folds in here) | |
| Sciatica | col 13 | Nerve symptom; functionally distinct from generic Lower back for filtering |
| Trapezius | Exercise DB col-13 | Added v2.1 |

## Hip

| Canonical | Source | Notes |
|---|---|---|
| Hip | both | Generic hip (joint) |
| Groin | both | |
| Hip flexor | both | |
| Glute | proposed (absorbs col 13 "Hip Abductor") | Glute med = hip abductor; one label is enough |
| Hip crest (iliac crest) | col 13 | Pack-belt rub site; bony landmark — kept |
| TFL | col 13 | Tensor Fasciae Latae — athletes who get this know the term |
| TFL | Exercise DB col-13 | Added v2.1 — Tensor Fasciae Latae |

## Upper leg

| Canonical | Source | Notes |
|---|---|---|
| Quad | both | |
| Hamstring | both | |
| IT band | both | |

## Knee

| Canonical | Source | Notes |
|---|---|---|
| Knee | both | Generic knee — most common |
| Kneecap | proposed | |
| Meniscus | proposed | |
| ACL | both (col 13 "Anterior Cruciate Ligament" → ACL) | |
| PCL | proposed | Not in col 13 yet — would be added when relevant exercise enters DB |
| MCL | proposed | Same — added when relevant |
| LCL | proposed | Same — added when relevant |

## Lower leg

| Canonical | Source | Notes |
|---|---|---|
| Calf | both | |
| Soleus | proposed | Distinct from gastroc; runners with soleus issues know this term |
| Shin | both | |
| Achilles | both | Anatomical retained — universally known |
| Peroneal | proposed | |

## Foot / Ankle

| Canonical | Source | Notes |
|---|---|---|
| Ankle | both | |
| Plantar fascia | both | Anatomical retained — universally known |
| Foot | proposed | Generic foot |
| Toes | proposed | |

## Trunk

| Canonical | Source | Notes |
|---|---|---|
| Rib | col 13 | (col 13 "Ribs" and "Chest/Rib" — Chest/Rib should be split into Rib + Chest at col 13 cleanup time) |
| Chest | derived | Add as canonical for split of "Chest/Rib" |
| Diaphragm | Exercise DB col-13 | Added v2.1 — breathing muscle, relevant for breath-hold / contact exercises |

**Total:** 41 canonical body parts.

---

# Section 2 — Health Conditions Canonical List

Replaces both **Chronic Medical Conditions** (multi-select field, v1) and **Systemic Constraints** (proposed Injury Record subfield, v1) with a single record-type field on Section B (parallel structure to Injury Record).

## 2.1 Health Condition Record substructure

| Field | Type | Notes |
|---|---|---|
| Name | Free text | The condition itself ("Asthma", "Type 1 diabetes", "Crohn's", "Concussion history", "Heat-induced syncope") |
| System category | Single-select enum (see 2.2) | Drives plan-side filtering and prescription rules |
| Status | Enum (Current / History) | Current = actively affects programming; History = informs prevention/return-to-load logic |
| Notes | Free text | Provider instructions, trigger patterns, severity context, medications cross-ref |

**Multiplicity:** 0+ records per athlete. Tier 1.

## 2.2 System category enum

| System category | Drives | Examples that map here |
|---|---|---|
| Cardiac | HR ceiling enforcement; avoid max-effort and high-HR-spike work | Hypertension, arrhythmia, post-MI, HCM, mitral valve issues |
| Respiratory | Altitude-sim caution; interval intensity management; cold-air protocols | Asthma, EIB, COPD, post-COVID lung |
| Endocrine / Metabolic | Carb-timing for diabetic ultra; thyroid-aware volume ramps; cortisol-aware load mgmt | T1D, T2D, hypo/hyperthyroid, adrenal insufficiency, PCOS |
| GI | Race-fueling planning; aid-station strategy; avoid high-jostle post-fueling | IBS, IBD, Crohn's, celiac, chronic reflux |
| Neurological | Coordination/disorientation drill caution; concussion return-to-load; seizure-risk gating | Concussion history, migraine, epilepsy, MS, neuropathy |
| Cognitive / Mental health | Plan complexity calibration; recovery prioritisation; stimulant interaction with HR | ADHD, anxiety, depression, OCD — when affects training adherence/intensity |
| Cognitive | Skill-heavy drill gating; sequencing-load caution; processing-speed-aware progression | TBI, post-concussion processing-speed deficits, cognitive impairment affecting drill execution |
| Musculoskeletal (chronic, non-injury) | Permanent regression chain; load management; flare-up flags | Arthritis, fibromyalgia, hypermobility, congenital structural |
| Skin | Sun-exposure exercise filtering; abrasion-risk surfaces; sweat-irritation gear | Photosensitivity, eczema, severe sweat allergy |
| Thermoregulation | Heat/cold tolerance flags; pairs with system-tracked heat-acclim history | Heat intolerance, Raynaud's, MS-related thermal dysreg |
| Immune / Autoimmune | Recovery time inflation; flare-aware load management | RA, lupus, MCAS, post-infection syndromes |
| Other | Captures anything not above | Free text in Name field describes |

**Mapping from old col 13 systemic tokens:**

| Old col 13 token | New System category |
|---|---|
| Cardiac | Cardiac |
| Cognitive | Cognitive |
| Lungs | Respiratory |
| GI | GI |
| Skin | Skin |
| Sciatica | Neurological |
| Core Temperature | Thermoregulation |

**Excluded — col 13 keeps as filter flags but no athlete-side field:**

| col 13 token | Reason |
|---|---|
| Saddle | Captured by Section D cycling baselines (Saddle Endurance — soft warning) |
| Goggle | Gear adaptation, not athlete data — built up through training |
| Blister | Footwear/sock adaptation, not athlete data — built up through training |

These remain valid col 13 flags for exercise filtering at runtime but are not asked at onboarding.

## 2.3 Why merge

- ~70% overlap between v1's "Chronic Medical Conditions" multi-select and v1's "Systemic Constraints" subfield.
- Same underlying data — a system-level health condition that affects plan generation. The split was an artifact of two source docs proposing it differently.
- Record-type structure beats multi-select because real conditions have specifics worth capturing (status changes, provider context, trigger patterns) that multi-select can't hold.
- Parallel structure to Injury Record means the same UI pattern handles both — add/edit/resolve a record over time.

---

# Section 3 — Equipment Canonical List

Organised to mirror AR Schema 2.2 categories. Each row shows the canonical name and (where applicable) col 7 variants that should be renamed to it. New "Assumed Universal" category and rolled-up "Sport-Specific Gear Readiness" categories at the end.

## Freeweights

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Barbell | Barbell ✓ | Bar weight (15/35/45 lb) sub-question retained |
| Squat rack | Rack | "Rack" alone in col 7 is ambiguous; clarify in cleanup |
| EZ curl bar | — | |
| Trap bar | — | |
| Safety squat bar | — | |
| Tricep bar (W-bar) | — | Folded in from EQUIPMENT_CATEGORIES (Vocabulary V4) so the A-only list can retire |
| Landmine attachment | Landmine Attachment ✓ | |
| Weight plates | Weight Plate, Light Plate, Barbell with Plates | Consolidate; "Barbell with Plates" redundant with Barbell |
| Dumbbell | Dumbbell, Light Dumbbell, Heavy Dumbbell, Light DB | Quantity/weight via sub-question |
| Kettlebell | Kettlebell ✓ | |
| Bench | Bench, Floor or Bench, Bench or Box, Incline Bench | Generic flat bench; sub-questions for incline. Moved from Bodyweight & Portable (V4 §6) |
| Preacher curl bench | — | Folded in from EQUIPMENT_CATEGORIES (Vocabulary V4) |

## Machines - Strength

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Smith machine | — | |
| Leg press machine | Leg Press Machine ✓ | |
| Hack squat machine | — | |
| Leg extension machine | Leg Extension Machine ✓ | |
| Leg curl machine | Leg Curl Machine ✓ | |
| Standing calf raise machine | — | |
| Seated calf raise machine | — | |
| Hip abductor machine | — | |
| Hip adductor machine | — | |
| Glute ham developer (GHD) | — | |
| Hip thrust machine | — | |
| Cable machine | Cable, Cable Machine | RENAME col 7 "Cable" → "Cable Machine" |
| Lat pulldown machine | — | |
| Seated row machine | — | |
| Chest press machine | — | |
| Shoulder press machine | — | |
| Rear delt fly machine | — | |
| Assisted pull-up / dip machine | — | |
| Bicep station | — | |
| Tricep station | — | |

## Machines - Cardio

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Treadmill | Treadmill, Inclined Treadmill at Maximum Grade | Incline % is a sub-question, not a separate equipment item |
| Stationary bike | — | |
| Spin bike | — | |
| Stair climber | — | |
| Elliptical | — | |
| Assault bike | — | |
| Rowing ergometer | Rowing Ergometer ✓ | |
| Ski erg | — | |
| Paddle ergometer | Paddle Ergometer ✓ | |
| Arm bike / UBE | — | |

## Plyo, Power & Stability

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Plyo box | Plyo Box, Box, Vault Box | RENAME col 7 "Box", "Vault Box" → "Plyo Box" |
| Medicine ball | Medicine Ball ✓ | |
| Slam ball | — | Folded in from EQUIPMENT_CATEGORIES (V4). Power implement — grouped with the other power items (you tagged Bodyweight; placed here per build decision) |
| Weighted sled | Weighted Sled ✓ | |
| Battle ropes | — | |
| Sandbag | — | |
| BOSU ball | BOSU ✓ | |
| Balance disc | Balance Disc ✓ | |
| Stability ball | Stability Ball ✓ | |
| Slider discs | — | |
| Foam pad | Foam Pad ✓ | Used in paddle balance drills |
| Incline board | Incline Board ✓ | Used for balance/calf |

## Grip & Climbing

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Hangboard | Hangboard ✓ | |
| Campus board | Campus Board ✓ | |
| Grip trainer | — | |
| Wrist roller | Wrist Roller ✓ | |
| Rice bucket | Rice Bucket ✓ | |
| Fat grips | — | |
| Pinch block | Pinch Block ✓ | |
| Finger extension band | — | |
| Treadwall | — | Folded in from EQUIPMENT_CATEGORIES (Vocabulary V4) |

<!-- "Climbing wall" is intentionally NOT folded in here: it already exists in
layer0 as the active 0B legacy row "Climbing Wall" (0B-v19.K2). Adding a 0C
copy violates equipment_items_active_ci_name_idx (case-insensitive unique on
active names). The A-list item maps to the existing row; casing reconciliation
(Climbing Wall vs Climbing wall) is left to V5's EQUIPMENT_CATEGORIES retirement. -->

## Bodyweight & Portable Equipment

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Pull-up bar | Pull-Up Bar ✓ | |
| Dip bars | Dip Bars ✓ | |
| Parallettes | Parallettes ✓ | |
| Gymnastic rings | Rings | RENAME col 7 "Rings" → "Gymnastic Rings" for clarity |
| TRX / suspension trainer | TRX | Acceptable as-is |
| Resistance band | Resistance Band, Band, Rubber Band | RENAME col 7 "Band", "Rubber Band" → "Resistance Band" |
| Ab wheel | Ab Wheel ✓ | |
| Foam roller | Foam Roller ✓ | |
| Lacrosse ball | — | |
| Massage gun | — | |
| Jump rope | — | |
| Agility ladder | Agility Ladder ✓ | |
| Cones | Cones ✓ | |
| Yoga mat | — | |
| Nordic curl strap | — | |
| Knee pad | Knee Pad ✓ | |
| Weighted vest | Vest, Weight Vest | RENAME col 7 → "Weighted Vest". Moved from Sport-Specific Running & Hiking (Vocabulary V4 §6) |

## Sport-Specific — Cycling (top-level vessels — kept individual)

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Road bike | Road Bike ✓ | |
| Mountain bike | Mountain Bike, MTB | RENAME col 7 "MTB" → "Mountain Bike" |
| Gravel bike | Gravel Bike ✓ | |
| TT / triathlon bike | TT Bike or Road Bike on Trainer, Aero Bars | "TT Bike or Road Bike on Trainer" is exercise-side OR-logic; col 7 cleanup needed |
| Power meter | — | |
| Cycling trainer | Trainer, Bike Trainer, Indoor Trainer | RENAME col 7 → "Cycling trainer". Indoor cycling trainer; maps to all cycling disciplines. Renamed from "Bike trainer" + relocated here from Machines — Cardio (V4 §4). |
| Helmet | Helmet ✓ | Add to AR Schema 2.2 — currently assumed but listed in col 7 |

## Sport-Specific — Paddle (top-level vessels — kept individual)

| Canonical | Col 7 variant(s) → rename / split | Notes |
|---|---|---|
| Kayak | Kayak, Kayak / Packraft, Kayak / Canoe, Kayak / Sea Kayak, Kayak / Canoe / Packraft, Kayak / Canoe / Raft | **DECOMPOSE.** Each slash-string in col 7 splits to atomic items + OR-match logic. "Sea Kayak" token folds to Kayak (subtype via sub-question) — Sea kayak pruned as a standalone vessel (V4 §4). |
| Canoe | Canoe ✓ | |
| Packraft | Packraft, Loaded Packraft | "Loaded" is prescription detail, not equipment |
| Stand-up Paddleboard | SUP, Stand-Up Paddleboard, SUP Paddle | Renamed from "SUP" → canonical "Stand-up Paddleboard" (V4 §4). "SUP Paddle" is sub-component, assumed with the board. |
| Raft | Raft, Inflatable Raft | Renamed from "Inflatable raft" → "Raft" (V4 §4). |
| Paddle (double-blade) | Paddle, Two Paddles | Generic — implicit with Kayak/Packraft |
| Single-blade paddle | Single-Blade Paddle ✓ | Implicit with Canoe |
| Rowing oar | Rowing Oar, Sculling Blade, Erg Handle, Oars | Sub-components of Rowing Erg (Rowing shell vessel pruned, V4 §4) |
| Kayak / canoe seat | Kayak / Canoe Seat ✓ | Implicit with vessel |

**Whitewater-specific accessories** (spray skirt, WW helmet, WW PFD) → rolled into **Whitewater paddling setup** toggle (Section 4 below).

## Sport-Specific — Running & Hiking (top-level — kept individual)

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Running shoes | Running Shoes, Shoes | RENAME col 7 "Shoes" → "Running Shoes" |
| Hiking boots | — | |
| Trekking poles | Trekking Poles, Poles | "Poles" is ambiguous (trekking / ski / paddle). Disambiguate at col 7 cleanup |
| Backpack | Backpack, Loaded Backpack | "Loaded" is prescription detail |
| Headlamp | Headlamp ✓ | |

**Race nutrition items — not tracked.** Col 7 entries "Gels", "Chews", "Cups", "Soft Flask" dropped from athlete onboarding. Fueling advice is provided in plan generation (Section I race fueling preferences); item availability is not logged. **Layer 0 cleanup:** move these col 7 entries to col 10 (Notes / Cues), or drop entirely.

## Sport-Specific — Winter (top-level singletons — kept individual)

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Snowshoes | Snowshoes ✓ | Single-item kit — no rollup needed; the item IS the kit |
| Avalanche safety gear | — | Beacon + probe + shovel + training. Safety gate retained — gates backcountry programming on **Avalanche safety training completed Y/N** |

**All other ski equipment** (touring skis, alpine skis, XC skis, ski boots, ski poles, climbing skins, ski crampons, boot buckles, ice axe, mountaineering harness used in SkiMo) → rolled into the three ski-setup toggles in Section 4 below.

## Sport-Specific — Swimming (top-level — kept individual)

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Wetsuit | Wetsuit, Wetsuit (optional), Wetsuit (SwimRun cut or full) | Sub-type as sub-question (full / sleeveless / SwimRun cut) |
| Pull buoy | Pull Buoy ✓ | |
| Kickboard | Kickboard ✓ | |
| Swim paddles | — | |
| Swim fins | — | |
| Swim cap and goggles | Swim Cap and Goggles ✓ | Treated as assumed-universal for swimmers |
| SwimRun paddles | SwimRun Paddles (optional) ✓ | |

## Recovery & Therapy

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Foam roller | Foam Roller ✓ | (Already in Bodyweight & Portable) |
| Lacrosse ball | — | |
| Massage gun | — | |
| Compression boots (Normatec) | — | **DROP from AR Schema 2.2** — never used in col 7 |
| Ice bath / cold plunge | — | |
| Sauna access | — | **DROP from AR Schema 2.2** — never used in col 7 |
| TENS / EMS unit | — | |
| Yoga blocks | — | |
| Stretch strap | — | **DROP from AR Schema 2.2** — never used in col 7 |

## Assumed Universal — system-level category

Items every athlete is assumed to have in every locale. **Not asked at onboarding. Not a filter trigger.** Exercises that require only items from this list are universally available regardless of locale equipment.

| Canonical | Col 7 token(s) | Use case |
|---|---|---|
| Bodyweight | Bodyweight (44) | Base case for any bodyweight exercise |
| Floor space | Floor (1) | Floor-based exercises |
| Wall | Wall (8) | Wall sits, handstand wall walks, wall plank |
| Doorway | Doorway (2) | Pull-up bar mount, band anchor |
| Anchor point | Anchor Point (2) | Generic sturdy attachment for bands/straps |
| Compass | Compass (2) | Orienteering navigation drill |
| Topographic map | Topographic Map (3) | Orienteering navigation drill |
| GPS | GPS (1) | Orienteering / nav verification |
| Outdoor space | Outdoor (1), Track (1), Running Space (1), Open Space (in compounds) | Generic outdoor area for running / drills |

**System logic:** When an exercise's col 7 lists only items from this Assumed Universal set (plus Bodyweight), it passes equipment matching unconditionally for every athlete.

## Terrain (separate from equipment — not athlete-side)

These are not equipment but terrain features. They should NOT live in AR Schema 2.2 equipment checklist; they belong in Section K (Locale) terrain access. Listed here only because they appeared in col 7 alongside true equipment.

| Terrain in col 7 | Belongs in Section K (Locale Terrain) |
|---|---|
| Outdoor Hill, Steep Hill, Steep Mountain, Steep Track | Hill / mountain access |
| Trail, Flat Trail, Gravel or Dirt Trail | Trail access |
| Road, Descent Road, Gravel Road | Road access |
| Pump Track | Pump track access |
| Pool, Open Water, Open Water Body, Pool or Flat Water, Open Water or Ocean, Ocean or Surf, Flat or Choppy Water | Water access types |
| Whitewater, Moving Water, River | Whitewater access |
| Snow Slope, Groomed Slope, Groomed Track, Deep Snow or Sand | Snow terrain |
| Rocky Terrain, Boulders, Scree Field, Loose Rocky Slope | Technical terrain |
| Fell Terrain (Steep Grass, Moorland, Heather, Bog) | Fell-running terrain |
| Darkness | Time-of-day condition (not terrain) |
| Climb, Steep Mountain | Mountain access |
| Varied Terrain | Generic — implies multiple types |
| Group Riding Environment | Social condition (not terrain) |
| Partner or Visual Cue, Tandem Partner, Team | Partner/team-presence (not terrain) |
| Rock Wall, Climbing Gym | Climbing terrain (gym vs. outdoor — see Section K) |

**Layer 0 cleanup task:** Move all of the above from col 7 (Equipment) to a new col 7b (Terrain Required) or to col 10 (Notes) where contextual. Equipment column should only list portable/owned items.

---

# Section 4 — Sport-Specific Gear Readiness Toggles

The canonical kit-category list. Each toggle is a single token in col 7 and a single onboarding question. **Sub-components are not asked, not stored, and not present in col 7.**

## 4.1 The 12 toggles

| # | Toggle (canonical token) | Replaces these former col 7 sub-tokens | Y/N gates these exercise families |
|---|---|---|---|
| 1 | Touring/AT ski setup | Touring skis, Alpine skis, Ski boots (touring), Ski poles, Climbing skins, Ski crampons, Boot buckles, Touring binding, Mountaineering harness (when used in SkiMo), Ice axe (when used in SkiMo) | SkiMo, ski-touring, alpine descent training |
| 2 | Classic XC ski setup | Classic Cross-Country Skis, Classic XC boots, Classic XC poles | Classic XC technique, XC endurance (classic) |
| 3 | Skate XC ski setup | Skate Cross-Country Skis, Skate XC boots, Skate XC poles | Skate XC technique, XC endurance (skate) |
| 4 | Climbing — roped | Climbing rope, Harness, Belay device, Carabiners, Slings, Anchor hardware, Quickdraws, Helmet (climbing) | Lead climbing, top-rope, rope-team movement |
| 5 | Bouldering | Bouldering shoes, Chalk, Crash pad | Bouldering, V-grade training |
| 6 | Rappelling / abseiling | Rappel device, Harness, Slings, Backup prusik, Helmet (climbing) | Fixed-rope descent, AR-specific abseil sections |
| 7 | Via ferrata | Via ferrata Y-lanyard, Harness, Helmet (climbing) | Via ferrata routes, fixed-cable terrain |
| 8 | Mountaineering | Crampons, Mountaineering boots, Ice axe, Mountaineering harness, Mechanical ascender, Helmet (climbing) | Mountaineering, glacier travel, technical alpine |
| 9 | Whitewater paddling setup | Spray skirt, Whitewater helmet, Whitewater PFD, Throw bag | Whitewater kayak/canoe/packraft, swiftwater drills |
| 10 | Fencing setup | Mask, Jacket, Foil/épée/sabre, Glove, Lamé (electric) | Fencing technical work, modern pent fencing leg |
| 11 | Shooting setup | Laser pistol, Air pistol, Rifle (subtype sub-question if needed), Targets | Modern pent shooting leg, biathlon shooting |
| 12 | Snowshoeing setup *(retained as note only)* | (Snowshoes already top-level singleton — no rollup needed) | — |

Toggle 12 is documented for completeness — snowshoeing has only one piece of kit (snowshoes), so the snowshoe item itself functions as both the top-level and the readiness toggle. There is no separate "snowshoeing setup" token.

## 4.2 Notes on overlap and edge cases

- **Climbing — roped** and **Rappelling** share most kit. They're separate toggles because some athletes (especially AR-only) only abseil and never lead. An athlete with full roped setup automatically passes rappelling-gated exercises; the matching engine treats Climbing — roped = true as also satisfying Rappelling = true.
- **Via ferrata** uses a subset of climbing kit but with a sport-specific Y-lanyard. Treated as distinct because the harness + Y-lanyard combo without belay device is a complete via ferrata kit on its own.
- **Mountaineering** overlaps with **Touring/AT ski setup** for ice axe and crampons. Treated as distinct because the use cases are different (technical alpine vs. ski-mountaineering ascent) and the boots are not interchangeable.
- **Helmet (climbing)** appears across multiple toggles. It's not its own token in col 7 — it's a sub-component of whichever readiness toggle is gating the exercise.
- **Bouldering** typically requires terrain (rock wall / climbing gym / outdoor boulders), which lives in Section K Terrain. Toggle = Y but no terrain access = exercise still gated.

## 4.3 Why this consolidation

Per Andy: "Don't track sub-items at all — not in col 7, not in onboarding. Single token in col 7 for whole-kit categories, matching one-to-one with readiness toggle."

Trade-off accepted: an athlete who owns a partial kit (e.g., harness but no rope) has to set the toggle to N. The granularity loss is intentional — partial-kit cases are rare, and the alternative (asking 8+ questions per sport) is high-friction with low payoff.

---

# Section 5 — Required Changes Summary

## AR Schema 2.2 — additions

- **Bench** — new entry in Bodyweight & Portable Equipment.
- **Foam pad** — new entry in Stability & Balance.
- **Incline board** — new entry in Stability & Balance.
- **Helmet (cycling)** — confirm in checklist; col 7 references it.

## AR Schema 2.2 — removals (over-collected)

- Jacob's Ladder
- Compression boots (Normatec)
- Sauna access
- Stretch strap

## AR Schema 2.2 — Sport-Specific section restructure

Replace the v1 "Sport-Specific Gear Readiness" sub-component checklists with the **12 rolled-up toggles** in Section 4 above. Each toggle is one onboarding question (Y/N) plus, where applicable, a single sub-question (e.g., avalanche training completed for ski/snowshoe; rifle subtype for shooting).

## Col 7 (Layer 0) cleanup tasks — vocab-driven renames

| Issue | Action |
|---|---|
| "Band", "Rubber Band" | Rename → "Resistance Band" |
| "MTB" | Rename → "Mountain Bike" |
| "Cable" | Rename → "Cable Machine" |
| "Box", "Vault Box" | Rename → "Plyo Box" (Vault Box only if distinct from generic plyo box) |
| "Vest", "Weight Vest" | Rename → "Weighted Vest" |
| "Shoes" | Rename → "Running Shoes" |
| "Rings" | Rename → "Gymnastic Rings" |
| "Trainer", "or Trainer" | Rename → "Bike Trainer"; investigate comma-split artifact |
| "Cervical", "Cervical Spine" (col 13) | Rename → "Neck" |
| "Lumbar" (col 13) | Rename → "Lower back" |
| "Thoracic" (col 13) | Rename → "Upper back" |
| "Anterior Cruciate Ligament" (col 13) | Rename → "ACL" |
| "Hip Abductor" (col 13) | Merge into "Glute" |
| "Sacrum" (col 13) | Merge into "SI joint" |
| "Ribs" (col 13) | Rename → "Rib" |
| "Chest/Rib" (col 13) | Split into "Rib" + "Chest" entries |
| "Shoulder/Wrist", "Shoulder/Neck" (col 13) | Split into separate entries per affected part |
| Slash-strings ("Kayak / Packraft", etc.) | Decompose to atomic items + OR-logic at matching engine |
| "Race Belt)" | Fix typo (closing paren) |
| "Gels", "Chews", "Cups", "Soft Flask" | Move from col 7 to col 10 (Notes / Cues), or drop |

## Col 7 (Layer 0) cleanup tasks — sport-specific gear rollup (NEW in v2)

Collapse the following individual col 7 tokens into the rolled-up toggle token. Each row is a former sub-component → its new rolled-up token.

| Former col 7 token | New rolled-up col 7 token |
|---|---|
| Climbing rope | Climbing — roped |
| Harness (when context = roped climbing) | Climbing — roped |
| Belay device | Climbing — roped |
| Carabiners | Climbing — roped |
| Slings | Climbing — roped (or Rappelling, by exercise context) |
| Anchor hardware | Climbing — roped |
| Quickdraws | Climbing — roped |
| Bouldering shoes | Bouldering |
| Crash pad | Bouldering |
| Chalk (when bouldering) | Bouldering |
| Rappel device | Rappelling |
| Backup prusik | Rappelling |
| Via ferrata Y-lanyard | Via ferrata |
| Crampons | Mountaineering |
| Mountaineering boots | Mountaineering |
| Ice axe | Mountaineering (or Touring/AT ski setup if SkiMo context) |
| Mountaineering harness | Mountaineering |
| Mechanical ascender | Mountaineering |
| Touring skis | Touring/AT ski setup |
| Alpine skis | Touring/AT ski setup |
| Ski boots (touring) | Touring/AT ski setup |
| Ski poles (touring/alpine) | Touring/AT ski setup |
| Climbing skins | Touring/AT ski setup |
| Ski crampons | Touring/AT ski setup |
| Boot buckles | Touring/AT ski setup |
| Classic Cross-Country Skis | Classic XC ski setup |
| Classic XC boots | Classic XC ski setup |
| Classic XC poles | Classic XC ski setup |
| Skate Cross-Country Skis | Skate XC ski setup |
| Skate XC boots | Skate XC ski setup |
| Skate XC poles | Skate XC ski setup |
| Spray skirt | Whitewater paddling setup |
| Whitewater helmet | Whitewater paddling setup |
| Whitewater PFD | Whitewater paddling setup |
| Throw bag | Whitewater paddling setup |
| Mask, Jacket, Foil/épée/sabre, Glove (fencing) | Fencing setup |
| Laser Pistol, Air Pistol | Shooting setup (sub-type sub-question) |
| Pull-up bar towel wrap | Drop from col 7; move to col 11 (substitute) for hangboard exercises |

**Implementation note:** This is an exercise-by-exercise pass through every climbing, mountaineering, ski, whitewater, fencing, and shooting exercise in the DB to update col 7. Estimated touch count: 60–100 exercises.

## Col 7 (Layer 0) structural cleanup — terrain extraction

Move all terrain entries (Trail, Road, Hill, Mountain, Pool, Open Water, Snow, Whitewater, Fell terrain, Rock Wall, Climbing Gym, etc.) out of col 7 and into either:
- A new col 7b (Terrain Required), or
- Col 10 (Notes / Cues) where contextual.

Recommend col 7b — keeps terrain queryable rather than buried in free text. The matching engine then checks athlete's locale terrain access (Section K) against col 7b at exercise selection time, the same way it checks equipment.

---

# Section 6 — UX flow note (for next session)

When an athlete adds a Locale (Section K), the UI flow should collect **equipment + terrain access in the same step**. They share the same scope (per-locale), and asking them together avoids a second prompt. Data structure stays separated (equipment under Account Config, terrain under Section K), but the input flow is unified.

The 12 sport-specific gear readiness toggles are also locale-scoped (an athlete may have full climbing gear at home but not while traveling). Default = home locale; athlete can override per locale.

---

# Section 7 — v2 spec changes summary

- **Section A.1 "Disclosures" subsection:** Add (per Onboarding handoff). Account-creation legal/medical acknowledgment + contextual inline disclosures.
- **Section B — Health Status:**
  - Replace "Chronic Medical Conditions" multi-select field with **Health Conditions** record-type field (see Section 2 above).
  - Drop the proposed "Systemic Constraints" subfield on Injury Record (B.1) — superseded by Health Conditions.
  - Apply canonical body part list (Section 1 above) to B.2.
  - Add **Injury Type** field to B.1 substructure (Tier 1, single-select enum — see Section_B_v2_Batch.md).
- **Section 2.2 (becomes v2's equipment section under Account Configuration):**
  - Apply additions and removals from Section 5 above.
  - Add new "Assumed Universal" category as system-only (not exposed in onboarding UI).
  - Replace sport-specific sub-component checklists with 12 readiness toggles (Section 4).
  - Document the rolled-up token principle explicitly: one token per kit category, no sub-components.
- **Section K — Locale:**
  - Confirm terrain items live here, not in equipment.
  - UX recommendation: locale equipment + terrain + readiness toggles collected together at locale-add time.
- **Cross-layer flag:** col 7 cleanup task is a Layer 0 dependency. v2 spec should reference the rollup pass as a prerequisite for clean field-matching at runtime.

---

# Section 8 — No-equipment fallback logic

How the database handles an athlete with no equipment available — clarification of what's already in the data model. Unchanged from v1.

## The four-tier fallback (already in place per AR Exercise DB Documentation §5)

| Tier | Trigger | Action | Source col |
|---|---|---|---|
| 1 | Athlete's locale has equipment matching col 7 | Programme exercise as written | Col 7 |
| 2 | Col 7 doesn't match, but col 11 lists an equipment-substitute that does match | Swap to substitute variant (same exercise, different kit) | Col 11 (non-🏠) |
| 3 | Tiers 1+2 fail; col 11 has 🏠-prefixed improvised entries | Auto-suggest improvised option alongside Tier 4 fallback | Col 11 (🏠 entries) |
| 4 | Nothing matches | Fall back to Physical Proxy — different exercise, same physical qualities | Col 12 |

## "Last resort" exercise set — how to derive it

For an athlete in a hotel with literally nothing (no improvised options viable, no fitness equipment, only their bodyweight in a small space): the system can produce a viable session by querying:

- Exercises where col 7 = "Bodyweight" only (44 exercises in the DB) — these run unconditionally
- Exercises where col 7 contains only Assumed Universal items (Bodyweight, Wall, Floor, Doorway, Anchor point) — these also run unconditionally
- For everything else, use col 12 Physical Proxy — Physical Proxies tend to themselves bias toward bodyweight or simple-equipment alternatives

**No new data structure needed.** The "last resort" set is a derived view of the existing data, not a separately-tagged subset. The matching engine produces it dynamically based on locale equipment = empty + Assumed Universal items.

## Implication for Onboarding spec (v2)

No spec change needed. Document the derivation logic as a query pattern in the Layer 1 ↔ Layer 0 query layer (when that gets specced — currently deferred).

---

# Open items deferred (out of scope for this audit)

| Item | Why deferred |
|---|---|
| Movement Components on col 9 | Pre-existing handoff Open Item #9; out of vocab scope |
| Layer 1 ↔ Layer 0 query layer spec (including no-equipment derivation logic) | Deferred until schema is built |
| Whether assumed-universal items should appear in any audit/log for transparency | UX/spec decision |
| Helmet (climbing) — own token vs. always-implicit-with-toggle | Deferred to v2 spec design — current default: implicit with toggle |
| Bouldering chalk vs. lifting chalk — same item, different context | Trivial — drop the distinction; chalk = chalk |
