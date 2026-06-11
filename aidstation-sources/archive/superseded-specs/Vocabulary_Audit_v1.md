# Vocabulary Self-Pass — v1

**Built:** May 2026
**Resolves:** Onboarding handoff Open Items #1 (equipment vocab) and #2 (body part vocab)
**Sources reconciled:** `AR_Athlete_Onboarding_Schema.md` Section 2.2 · `AR_Exercise_Database_v17.xlsx` cols 7, 11, 13
**Status:** Canonical lists locked. Layer 0 cleanup actions and v2 spec changes flagged.

---

## Naming convention decisions

1. **Body parts — hybrid naming.** Common-name where it adds no precision over anatomical (Lumbar → Lower back; Cervical → Neck; Thoracic → Upper back). Anatomical retained where athletes already know the term from their PT (Achilles, Plantar fascia, IT band, Soleus, Peroneal, Meniscus, ACL/PCL/MCL/LCL, TFL).
2. **Non-anatomical flags moved off Body Part.** Cardiac, Cognitive, Lungs, GI, Skin sensitivity, Core Temperature become a new **Systemic Constraints** field on the Injury Record substructure (Section B.1).
3. **Sub-region precision unified.** Where the proposed handoff list and col 13 each had entries the other lacked, both kept.
4. **Equipment slash-strings decomposed.** "Kayak / Packraft" type col 7 entries split into atomic items + OR-logic in the matching engine. (Layer 0 cleanup task.)
5. **Assumed-universal items.** Wall, Doorway, Floor, Anchor Point, Compass, Topographic Map, GPS — assumed available to every athlete in every locale. Not a checklist item, not a filter trigger.
6. **Over-collected AR Schema items removed.** Equipment listed in AR Schema 2.2 but never used in col 7 → dropped from the schema.

---

# Section 1 — Body Part Canonical List

For Injury Record `Body Part` field (Section B.1). Side picker (L/R/Both/N/A) is a separate field.

## Head / Neck

| Canonical | Source | Notes |
|---|---|---|
| Neck | proposed + col 13 (Neck, Cervical, Cervical Spine — all merged) | |
| Jaw | proposed | |
| Trapezius | col 13 | Spans neck/upper back/shoulder; kept distinct because col 13 uses it |

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

## Back

| Canonical | Source | Notes |
|---|---|---|
| Upper back | proposed (col 13 "Thoracic" → translated per Option B) | |
| Lower back | proposed (col 13 "Lumbar" → translated per Option B) | |
| Spine (general) | col 13 | For non-region-specific spinal flags |
| SI joint | proposed (col 13 "Sacrum" folds in here) | |
| Sciatica | col 13 | Nerve symptom; functionally distinct from generic Lower back for filtering |

## Hip

| Canonical | Source | Notes |
|---|---|---|
| Hip | both | Generic hip (joint) |
| Groin | both | |
| Hip flexor | both | |
| Glute | proposed (absorbs col 13 "Hip Abductor") | Glute med = hip abductor; one label is enough |
| Hip crest (iliac crest) | col 13 | Pack-belt rub site; bony landmark — kept |
| TFL | col 13 | Tensor Fasciae Latae — athletes who get this know the term |

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

**Total:** 41 canonical body parts.

---

# Section 2 — Systemic Constraints Canonical List

New field on Injury Record substructure (Section B.1). Multi-select. Replaces non-anatomical entries in col 13. Athletes pick these directly; some can be auto-populated from Chronic Medical Conditions or Food Allergies (deferred design decision for v2).

| Canonical | Source col 13 token | Drives |
|---|---|---|
| Cardiac | Cardiac | Avoid max-effort and high-HR-spike exercises; HR ceiling enforcement |
| Cognitive | Cognitive | Avoid high-coordination / disorientation-risk drills (concussion history) |
| Respiratory | Lungs | Avoid altitude-sim exercises; manage interval intensity for asthma/EIB |
| GI | GI | Race nutrition planning; avoid high-jostle exercises post-fueling |
| Skin sensitivity | Skin | Sun-exposure exercises, abrasion-risk surfaces, sweat-irritation gear |
| Thermoregulation | Core Temperature | Heat/cold tolerance flags; pairs with system-tracked heat-acclim history |

**Excluded — col 13 keeps but no athlete-side field:**

| col 13 token | Reason |
|---|---|
| Saddle | Captured by Section D cycling baselines (Saddle Endurance — soft warning per handoff) |
| Goggle | Gear adaptation, not athlete data — built up through training |
| Blister | Footwear/sock adaptation, not athlete data — built up through training |

These remain valid col 13 flags for exercise filtering but are not asked at onboarding.

---

# Section 3 — Equipment Canonical List

Organised to mirror AR Schema 2.2 categories. Each row shows the canonical name and (where applicable) col 7 variants that should be renamed to it. New "Assumed Universal" category at the end.

## Barbells & Bars

| Canonical | Col 7 variant(s) → rename to canonical | Notes |
|---|---|---|
| Barbell | Barbell ✓ | Bar weight (15/35/45 lb) sub-question retained |
| Squat rack | Rack | "Rack" alone in col 7 (2) is ambiguous; clarify in cleanup |
| Smith machine | — | Kept |
| EZ curl bar | — | |
| Trap bar | — | |
| Safety squat bar | — | |
| Landmine attachment | Landmine Attachment ✓ | |
| Weight plates | Weight Plate, Light Plate, Barbell with Plates | Consolidate; col 7 "Barbell with Plates" redundant with Barbell |

## Dumbbells

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Dumbbell | Dumbbell, Light Dumbbell, Heavy Dumbbell, Light DB | Quantity/weight via sub-question; col 7 should not encode "light/heavy" in the equipment name — that's prescription detail |

## Kettlebells

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Kettlebell | Kettlebell ✓ | |

## Machines — Lower Body

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Leg press machine | Leg Press Machine ✓ | |
| Hack squat machine | — | Not in col 7 |
| Leg extension machine | Leg Extension Machine ✓ | |
| Leg curl machine | Leg Curl Machine ✓ | |
| Standing calf raise machine | — | |
| Seated calf raise machine | — | |
| Hip abductor machine | — | |
| Hip adductor machine | — | |
| Glute ham developer (GHD) | — | |
| Hip thrust machine | — | |

## Machines — Upper Body

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Cable machine | Cable, Cable Machine | RENAME col 7 "Cable" → "Cable Machine" |
| Lat pulldown machine | — | |
| Seated row machine | — | |
| Chest press machine | — | |
| Shoulder press machine | — | |
| Rear delt fly machine | — | |
| Assisted pull-up / dip machine | — | |
| Bicep station | — | |
| Tricep station | — | |
| Rowing ergometer | Rowing Ergometer ✓ | |
| Ski erg | — | |
| Arm bike / UBE | — | |

## Machines — Cardio

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Treadmill | Treadmill, Inclined Treadmill at Maximum Grade, Climb or Inclined Treadmill | Incline % is a sub-question, not a separate equipment item |
| Stationary bike | — | |
| Spin bike | — | |
| Bike trainer | Trainer, Bike Trainer, or Trainer | RENAME col 7 → "Bike Trainer". "or Trainer" is comma-split artifact — fix in col 7 cleanup |
| Stair climber | — | |
| Jacob's Ladder | — | **DROP from AR Schema 2.2** — never used in col 7 |
| Elliptical | — | |
| Paddle ergometer | Paddle Ergometer ✓ | |
| Assault bike | — | |

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
| Bench | Bench, Floor or Bench, Bench or Box, Incline Bench | "Bench" is generic flat bench; sub-questions for incline. "Bench or Box" is exercise-side OR-logic, not new equipment |
| Knee pad | Knee Pad ✓ | |

**ADD to AR Schema 2.2:** Bench (currently absent from the checklist; col 7 uses it 5 times).

## Stability & Balance

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| BOSU ball | BOSU ✓ | |
| Balance disc | Balance Disc ✓ | |
| Stability ball | Stability Ball ✓ | |
| Slider discs | — | |
| Foam pad | Foam Pad ✓ | Used in paddle balance drills; add to AR Schema 2.2 |
| Incline board | Incline Board ✓ | Used for balance/calf — add to AR Schema 2.2 |

## Plyo & Power

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Plyo box | Plyo Box, Box, Vault Box | RENAME col 7 "Box", "Vault Box" → "Plyo Box". "Vault Box" is OCR-specific; merge unless distinct height matters |
| Medicine ball | Medicine Ball ✓ | |
| Weighted sled | Weighted Sled ✓ | |
| Battle ropes | — | |
| Sandbag | — | Not currently in col 7 — DB gap to fill |

## Grip & Forearm Specific

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

## Sport-Specific — Cycling

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Road bike | Road Bike ✓ | |
| Mountain bike | Mountain Bike, MTB | RENAME col 7 "MTB" → "Mountain Bike" |
| Gravel bike | Gravel Bike ✓ | |
| TT / triathlon bike | TT Bike or Road Bike on Trainer, Aero Bars | "TT Bike or Road Bike on Trainer" is exercise-side OR-logic; col 7 cleanup needed |
| Power meter | — | |
| Bike (generic) | Bike, Road or MTB Bike, Road or Trail, Trail or Road, Road or Gravel Bike | Generic-bike entries in col 7 are acceptable (any bike works) but should resolve at matching time, not vocab time |
| Helmet | Helmet ✓ | Add to AR Schema 2.2 — currently assumed but listed in col 7 |
| Pump track | Pump Track ✓ | Terrain, not equipment — see Terrain section |

## Sport-Specific — Paddle

| Canonical | Col 7 variant(s) → rename / split | Notes |
|---|---|---|
| Kayak | Kayak, Kayak / Packraft, Kayak / Canoe, Kayak / Sea Kayak, Kayak / Canoe / Packraft, Kayak / Canoe / Raft | **DECOMPOSE.** Each slash-string in col 7 should split into atomic items + exercise matches if any of them is present |
| Sea kayak | (subtype of Kayak via sub-question) | Type sub-question handles this |
| Canoe | Canoe ✓ | |
| Packraft | Packraft, Loaded Packraft | "Loaded" is prescription detail, not equipment |
| SUP | Stand-Up Paddleboard, SUP Paddle | Rename "Stand-Up Paddleboard" → "SUP" for col 7 brevity. "SUP Paddle" is sub-component, assumed with SUP |
| Inflatable raft | Inflatable Raft ✓ | |
| Rowing shell | Rowing Shell ✓ | |
| Paddle (double-blade) | Paddle, Two Paddles | Generic — implicit with Kayak/Packraft |
| Single-blade paddle | Single-Blade Paddle ✓ | Implicit with Canoe |
| Rowing oar | Rowing Oar, Sculling Blade, Erg Handle, Oars | Consolidate — these are sub-components of Rowing Shell or Rowing Erg |
| Kayak / canoe seat | Kayak / Canoe Seat ✓ | Implicit with vessel |

**Whitewater accessories — abstracted by readiness toggle.** Spray skirt and similar whitewater-specific gear are covered by the "Whitewater paddling setup" readiness toggle, same pattern as climbing.

## Sport-Specific — Running & Hiking

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Running shoes | Running Shoes, Shoes | RENAME col 7 "Shoes" → "Running Shoes" |
| Hiking boots | — | |
| Trekking poles | Trekking Poles, Poles | "Poles" is ambiguous (trekking / ski / paddle). Disambiguate at col 7 cleanup |
| Backpack | Backpack, Loaded Backpack | "Loaded" is prescription detail |
| Weighted vest | Vest, Weight Vest | RENAME col 7 → "Weighted Vest" |
| Headlamp | Headlamp ✓ | |

**Race nutrition items — not tracked.** Col 7 entries "Gels", "Chews", "Cups", "Soft Flask" are dropped from athlete onboarding entirely. Fueling advice is provided in plan generation (Section I race fueling preferences); item availability is not logged. **Layer 0 cleanup:** move these col 7 entries to col 10 (Notes / Cues) where they remain useful as exercise context, or drop entirely.

## Sport-Specific — Winter

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Touring skis | Touring Skis, Touring Skis with Climbing Skins, Touring Skis or Alpine Skis | Decompose; "with Skins" is prescription detail |
| Alpine skis | (in slash-string above) | Add canonical entry |
| XC skis (classic) | Classic Cross-Country Skis | RENAME col 7 → "Classic XC Skis" |
| XC skis (skate) | Skate Cross-Country Skis | RENAME col 7 → "Skate XC Skis" |
| XC skis (generic) | Cross-Country Skis or Ski Poles on Flat Ground, Classic or Skate Cross-Country Skis | Decompose |
| Ski boots | Ski Boots, Ski Boots (ski mode), Bodyweight (ski boots if available) | Mode is a sub-question |
| Ski poles | (in "Poles" col 7 token) | Disambiguate from trekking |
| Snowshoes | Snowshoes ✓ | |
| Avalanche safety gear | — | Safety gate retained |

**Winter accessories — abstracted by readiness toggle or assumed-with-parent.** Climbing skins, Boot buckles, Ski crampons → assumed available with their parent item (Touring skis, Ski boots). Same readiness-toggle abstraction pattern as climbing applies for SkiMo setup and XC skiing setup.

## Sport-Specific — Climbing / Mountaineering — abstracted by readiness toggle

**Decision:** Climbing-specific items in col 7 (Climbing rope, Harness, Belay device, Carabiners, Slings, Anchor hardware, Mechanical ascender, Via ferrata Y-lanyard, Crampons, Mountaineering boots, Ice axe, Pull-up bar towel wrap) are **not asked individually at onboarding.** They are abstracted by the existing gear-readiness toggles in AR Schema 2.2 (Sport-Specific Gear Readiness):

- Full climbing setup (roped) → covers Climbing rope, Harness, Belay device, Carabiners, Slings, Anchor hardware
- Bouldering setup → covers Rock wall access (the readiness toggle implies you have what you need)
- Rappelling / abseiling setup → covers Belay/rappel device, Harness, Slings
- Via ferrata setup → covers Via ferrata Y-lanyard, Harness
- Mountaineering setup → covers Crampons, Mountaineering boots, Ice axe

**System logic:** When an exercise's col 7 includes any of these abstracted items, the matching engine gates on the corresponding readiness toggle, not on individual item presence. If the toggle is off, fall back to Physical Proxy.

**Why this matters:** climbing alone has 13+ specific items. Itemizing them at onboarding creates significant friction with little gain — athletes either have a full setup or they don't. The toggle-based approach matches how athletes actually think about their kit.

**Same pattern applies to other readiness-toggle categories:** Whitewater paddling setup (covers Spray skirt and other whitewater accessories), Snowshoeing setup, SkiMo setup, XC skiing setup, Fencing setup, Shooting setup. Top-level vessel/footwear (Kayak, Skis, Snowshoes, Ski boots) are still asked individually because they're fundamental, but accessories are absorbed by the toggle.

## Sport-Specific — Swimming

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Wetsuit | Wetsuit, Wetsuit (optional), Wetsuit (SwimRun cut or full) | Sub-type as sub-question (full / sleeveless / SwimRun cut) |
| Pull buoy | Pull Buoy ✓ | |
| Kickboard | Kickboard ✓ | |
| Swim paddles | — | |
| Swim fins | — | |
| Swim cap and goggles | Swim Cap and Goggles ✓ | Treated as assumed-universal for swimmers |
| SwimRun paddles | SwimRun Paddles (optional) ✓ | |

## Sport-Specific — Other

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Fencing strip | Fencing Strip or Open Space, Fencing Strip or Marked Floor | Decompose |
| Laser/air pistol | Laser Pistol, Air Pistol, Laser Pistol or Air Pistol | Decompose |
| Shooting range | Shooting Range ✓ | |
| Gymnastics horse | Gymnastics Horse ✓ | OCR-specific |
| Race belt | Race Belt) | col 7 typo (closing paren). Cleanup needed |
| Triathlon kit | Full Triathlon Gear Set (Wetsuit, Bike, Helmet, Shoes, Race Belt) | This col 7 entry is mangled by comma-split; treat as ad-hoc combination, not a vocab item |

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

## Assumed Universal — NEW category

Items every athlete is assumed to have in every locale. **Not asked at onboarding. Not a filter trigger.** Exercises that require only items from this list are universally available regardless of locale equipment.

| Canonical | Col 7 token(s) | Use case |
|---|---|---|
| Bodyweight | Bodyweight (44) | Base case for any bodyweight exercise |
| Floor space | Floor (1) | Floor-based exercises |
| Wall | Wall (8) | Wall sits, handstand wall walks, wall plank, etc. |
| Doorway | Doorway (2) | Pull-up bar mount, band anchor |
| Anchor point | Anchor Point (2) | Generic sturdy attachment for bands/straps |
| Compass | Compass (2) | Orienteering navigation drill |
| Topographic map | Topographic Map (3) | Orienteering navigation drill |
| GPS | GPS (1) | Orienteering / nav verification |
| Outdoor space | Outdoor (1), Track (1), Running Space (1), Open Space (in compounds) | Generic outdoor area for running / drills |

**System logic implication:** When an exercise's col 7 lists only items from this Assumed Universal set (plus Bodyweight), it passes equipment matching unconditionally for every athlete.

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

**Layer 0 cleanup task:** Move all of the above from col 7 (Equipment) to a new col 7b (Terrain Required) or to col 10 (Notes) where contextual. Equipment column should only list portable/owned items.

---

# Section 4 — Required Changes Summary

## AR Schema 2.2 — additions

- **Bench** — new entry in Bodyweight & Portable Equipment.
- **Foam pad** — new entry in Stability & Balance.
- **Incline board** — new entry in Stability & Balance.

## AR Schema 2.2 — removals (over-collected)

- **Jacob's Ladder**
- **Compression boots (Normatec)**
- **Sauna access**
- **Stretch strap**

## AR Schema 2.2 — confirm pattern (no changes, document the principle)

The existing **gear-readiness toggle pattern** (Section 2.2 → "Sport-Specific Gear Readiness") is the right abstraction for sport-specific kit. v2 should explicitly document this principle:

- **Top-level vessel/footwear is asked individually** (Kayak, Mountain bike, Touring skis, Ski boots, Snowshoes).
- **Accessories are abstracted** by either readiness toggle (Climbing rope, Harness, Belay device, Spray skirt, etc.) or assumed-with-parent (Climbing skins with Touring skis, Boot buckles with Ski boots).
- **Race-day consumables are not tracked** (Gels, Chews, Cups, Soft flask). Fueling advice is provided in plan generation; item availability is not logged.

## Col 7 (Layer 0) cleanup tasks — vocab-driven

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
| "Gels", "Chews", "Cups", "Soft Flask" | Move from col 7 to col 10 (Notes / Cues) where contextually useful, or drop |

## Col 7 (Layer 0) structural cleanup — terrain extraction

Move all terrain entries (Trail, Road, Hill, Mountain, Pool, Open Water, Snow, Whitewater, Fell terrain, etc.) out of col 7 and into either:
- A new col 7b (Terrain Required), or
- Col 10 (Notes / Cues) where contextual.

Column 7 should only contain portable/owned items. Recommend col 7b — keeps terrain queryable rather than buried in free text. The matching engine then checks athlete's locale terrain access (Section K) against col 7b at exercise selection time, same way it checks equipment.

## UX flow note (for next session)

When an athlete adds a Locale (Section K), the UI flow should collect **equipment + terrain access in the same step**. They share the same scope (per-locale), and asking them together avoids a second prompt. Data structure stays separated (equipment under Account Config, terrain under Section K), but the input flow is unified.

## v2 spec changes

- **Section B.1 — Injury Record substructure:** add `Systemic Constraints` field (multi-select: Cardiac, Cognitive, Respiratory, GI, Skin sensitivity, Thermoregulation).
- **Section B.2 — Body Part vocab:** replace handoff's proposed list with the canonical list in Section 1 above.
- **Section 2.2 (becomes v2's equipment section under Account Configuration):** apply additions and removals listed above. Add new category "Assumed Universal" as system-only (not exposed in onboarding UI but documented in spec). Document the gear-readiness toggle abstraction principle explicitly.
- **Section K — Locale:** confirm terrain items live here, not in equipment. Note UX flow recommendation that locale equipment + terrain are collected together.
- **Cross-layer flag:** col 7 cleanup task is a Layer 0 dependency. v2 spec should reference the cleanup as a prerequisite for clean field-matching at runtime.

---

# Section 5 — No-equipment fallback logic

How the database handles an athlete with no equipment available — clarification of what's already in the data model.

## The four-tier fallback (already in place per AR Exercise DB Documentation §5)

| Tier | Trigger | Action | Source col |
|---|---|---|---|
| 1 | Athlete's locale has equipment matching col 7 | Programme exercise as written | Col 7 |
| 2 | Col 7 doesn't match, but col 11 lists an equipment-substitute that does match | Swap to substitute variant (same exercise, different kit) | Col 11 (non-🏠) |
| 3 | Tiers 1+2 fail; col 11 has 🏠-prefixed improvised entries | Auto-suggest improvised option alongside Tier 4 fallback | Col 11 (🏠 entries) |
| 4 | Nothing matches | Fall back to Physical Proxy — different exercise, same physical qualities | Col 12 |

## "Last resort" exercise set — how to derive it

For an athlete in a hotel with literally nothing (no improvised options viable, no fitness equipment, only their bodyweight in a small space): the system can produce a viable session by querying:

- **Exercises where col 7 = "Bodyweight" only** (44 exercises in the DB) — these run unconditionally
- **Exercises where col 7 contains only Assumed Universal items** (Bodyweight, Wall, Floor, Doorway, Anchor point) — these also run unconditionally  
- **For everything else, use col 12 Physical Proxy** — Physical Proxies tend to themselves bias toward bodyweight or simple-equipment alternatives

**No new data structure needed.** The "last resort" set is a derived view of the existing data, not a separately-tagged subset. The matching engine produces it dynamically based on locale equipment = empty + Assumed Universal items.

## Implication for Onboarding spec (v2)

No spec change needed. Document the derivation logic as a query pattern in the Layer 1 ↔ Layer 0 query layer (when that gets specced — currently deferred).

The athlete-side onboarding doesn't need a "no-equipment fallback exercise list" field. The system computes it from the athlete's empty equipment inventory + the database's existing structure.

---

# Open items deferred (out of scope for this audit)

| Item | Why deferred |
|---|---|
| Movement Components on col 9 | Pre-existing handoff Open Item #9; out of vocab scope |
| Auto-population of Systemic Constraints from Chronic Medical Conditions | v2 spec design decision, not vocab |
| Layer 1 ↔ Layer 0 query layer spec (including no-equipment derivation logic) | Deferred until schema is built |
| Whether assumed-universal items should appear in any audit/log for transparency | UX/spec decision |
