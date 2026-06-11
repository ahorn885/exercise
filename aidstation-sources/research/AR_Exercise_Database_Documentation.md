# AR Exercise Database — Schema Documentation & Implementation Guide
## Version 17 | 245 Exercises · 1,068 Sport Mappings · 36 Sports

> **⚠ Historical reference (epic [#488](https://github.com/ahorn885/exercise/issues/488), 2026-06-11).** The live source of truth for exercise data is now the `layer0.exercises` / `layer0.sport_exercise_map` tables in Postgres, edited via SQL migrations under `etl/migrations/layer0/`. The `.xlsx` workbook this document describes is **frozen** under `etl/_frozen_xlsx_authoring/` and is no longer authored against. This doc remains useful as a description of the data model and column semantics (which the DB mirrors); where it says the spreadsheet/sheet is "source of truth," read that as the *DB table* of the same shape.

---

## 1. Purpose

This document fully describes the AR Exercise Database structure so that any system — human, LLM, or application — can query it, extend it, and build training programs from it. (The data now lives in the `layer0` Postgres tables; this guide documents the model those tables mirror — see the banner above.)

The database is a cross-referencing exercise library built for **multi-sport endurance athletes**. It answers questions like:

- What exercises support trail running at Critical priority?
- I have a knee injury — what should I avoid?
- I'm in a hotel with dumbbells and a pull-up bar — what can I do for climbing prep?
- I can't access scree terrain — what gym exercises train the same physical qualities?
- What's the next harder version of a Goblet Squat?
- Which exercises are useful across the most sports?

The database was designed for an LLM coaching application where the model selects and programs exercises. Three constraints drove every design decision:

1. **The LLM is the primary query engine.** Data structures optimise for machine lookup: EX IDs as foreign keys, controlled vocabulary, flat relational tables.
2. **One athlete, many sports.** Multi-sport athletes train across 5+ disciplines simultaneously. The same exercise has different priority in different sports — a Bulgarian Split Squat is Critical for trail running but Medium for orienteering.
3. **Constraints gate at runtime, not at data entry.** Rather than pre-filtering by injury or location, the database stores all information needed for the system to filter dynamically: what body parts an exercise stresses, what equipment it needs, what to do if the athlete can't perform it as written.

---

## 2. Architecture — Four Sheets

The database is an Excel workbook (.xlsx) with four sheets. Two are data tables the system queries; two are reference materials.

### Sheet 1: Exercise Master (the exercise library)

One row per exercise. 245 rows. 16 columns. This is the **source of truth for what an exercise is** — its mechanics, muscles, equipment, injury risks, and linkages to other exercises.

It does **not** store sport context. An exercise's relationship to a sport (which sport, why it matters, how critical it is) lives in the Sport-Exercise Map.

### Sheet 2: Sport-Exercise Map (the cross-reference)

One row per exercise-sport pairing. 1,068 rows. 6 columns. An exercise appears once per sport it applies to, with a sport-specific relevance note and priority level.

This is the **source of truth for what an exercise means to a specific sport** — not just that it's applicable, but *why* it matters and how critical it is. The relevance note column carries the coaching intelligence.

### Sheet 3: Sport Summary (visual pivot — human use only)

A visual summary of the Map sheet organised by sport, sorted by priority within each. The LLM should query the Map sheet directly; the Summary is for human navigation.

### Sheet 4: Legend (controlled vocabulary definitions)

Defines all enumerated values used across the database: exercise types, movement patterns, priorities, novelty tags, and attribute definitions. Always consult the Legend before adding data.

---

## 3. Exercise Master — Column-by-Column Schema

### Column 1: Exercise ID
- **Type:** String
- **Format:** EX001 through EX245, zero-padded three-digit sequential
- **Purpose:** Primary key. Used as foreign key in the Map sheet and in cross-references within the Master (Progression, Regression, Physical Proxy, Equipment Substitutes)
- **Rules:** Always reference by ID, never by name. IDs are permanent — do not reuse deleted IDs.

### Column 2: Exercise Name
- **Type:** String
- **Format:** Human-readable name with modality qualifier in parentheses where relevant: Single-Leg RDL (DB), Pull-Up (BW), Hang Clean (Barbell / KB)
- **Purpose:** Display name. **Not a key** — do not join on this field.

### Column 3: Exercise Type
- **Type:** Controlled vocabulary (17 values)
- **Purpose:** Classifies the nature of the training stimulus. Determines what kind of adaptation the exercise produces.
- **Valid values:**

| Type | Category | What it trains |
|---|---|---|
| Strength | Primary | Max force production under load |
| Power | Primary | Rate of force development — explosive movements |
| Plyometric | Primary | Bodyweight explosive — stretch-shortening cycle |
| Isometric | Primary | Static hold under load or bodyweight — no joint movement |
| Hypertrophy | Primary | Volume-based muscle building — moderate load, higher rep |
| Activation / Primer | Support | Low-load neuromuscular pre-activation before primary training |
| Balance / Proprioception | Support | Neuromuscular control on stable or unstable surface |
| Agility | Support | Change of direction, footwork, reaction time |
| Loaded Carry | Primary | Sustained postural integrity under load while moving |
| Aerobic / Endurance | Primary | Sustained cardio — the sport modalities themselves |
| Interval / Tempo | Primary | Structured intensity within an aerobic modality |
| Mobility | Support | Dynamic joint range of motion — active movement prep |
| Flexibility / Stretching | Support | Passive range of motion — static holds for tissue length |
| Breathwork | Support | Deliberate breathing practice for performance or recovery |
| Technical / Skill | Primary | Sport-specific movement pattern acquisition — no fitness stimulus |
| Recovery / Soft Tissue | Support | Foam rolling, massage, contrast therapy |
| Yoga / Pilates | Support | Integrated flexibility + isometric + balance + breathwork |

**Distribution:** Technical / Skill is the largest category (92 exercises, 38%) because sport-specific development happens at the technique level. Strength is second (51 exercises, 21%). This reflects a deliberate decision: the database is built for coaching, not gym programming.

### Column 4: Movement Pattern
- **Type:** Controlled vocabulary (20 values), comma-separated where multiple apply
- **Purpose:** Primary substitution logic field. Exercises sharing movement patterns can substitute for each other. Also used for programming balance — a training session should cover multiple patterns, not repeat one.
- **Valid values:**

| Pattern | What it describes |
|---|---|
| Squat | Bilateral knee and hip flexion — vertical load |
| Hinge | Hip-dominant posterior chain — deadlift family |
| Push-H | Horizontal push — bench press, push-up family |
| Push-V | Vertical push — overhead press family |
| Pull-H | Horizontal pull — row family |
| Pull-V | Vertical pull — pull-up, lat pulldown family |
| Carry | Loaded locomotion — farmer carry, ruck family |
| Rotation | Rotational movement — twist, chop, swing family |
| Anti-Rotation | Resisting rotation — Pallof press, plank family |
| Anti-Extension | Resisting spinal extension — plank, dead bug, hollow body family |
| Anti-Flexion | Resisting spinal flexion — suitcase carry, reverse hyper family |
| Anti-Lateral-Flexion | Resisting lateral trunk flexion — side plank, suitcase carry family |
| Single-Leg | Unilateral lower body — split squat, single-leg RDL, lunge family |
| Hip-Ext | Hip extension emphasis — glute bridge, thrust, swing family |
| Abduction | Hip moving away from midline — lateral band walk, clamshell |
| Adduction | Hip moving toward midline — Copenhagen plank, adductor squeeze |
| Anti-Adduction | Resisting adduction — Copenhagen plank variant |
| Locomotion | Traveling movement — run, walk, skip, shuffle, bound, crawl |
| Stretch | Passive or dynamic tissue lengthening |
| Breathwork | Deliberate respiratory pattern — box breathing, diaphragmatic |

**Multiple patterns apply often:** a Bulgarian Split Squat is Single-Leg, Squat. A Single-Arm KB Clean is Hinge, Hip-Ext, Anti-Rotation. Parse the field as a comma-separated list for filtering.

### Column 5: Primary Muscles
- **Type:** Free text, comma-separated
- **Purpose:** Muscles that are the primary training target of the exercise.
- **Usage:** Use for muscle-group search when an athlete needs to target a specific area.

### Column 6: Secondary Muscles
- **Type:** Free text, comma-separated
- **Purpose:** Muscles significantly loaded but not the primary target.
- **Usage:** Use to avoid overloading a muscle group across a session — if a secondary muscle appears in three consecutive exercises, it's being loaded more than intended.

### Column 7: Equipment
- **Type:** Free text, comma-separated
- **Purpose:** Equipment required to perform the exercise as described.
- **Usage:** Match against the user's available equipment inventory. If the user's equipment doesn't include what the exercise requires, check Equipment Substitutes (col 11) and Physical Proxy (col 12) in that order.
- **Examples:** Barbell, Rack / Bodyweight / Kayak / Packraft, Paddle / Touring Skis with Climbing Skins, Ski Boots, Poles

### Column 8: Novelty
- **Type:** Controlled vocabulary (2 values)
- **Purpose:** Distinguishes mainstream exercises from sport-specific ones. Useful for athlete engagement — athletes who bore easily can be served more Specialized exercises; newer athletes can be kept to Common ones.
- **Values:**
  - Common (102 exercises) — Well-known across mainstream training
  - Specialized (143 exercises) — Sport-specific or niche, used in targeted contexts

### Column 9: Injury Flags / Points of Failure
- **Type:** Free text
- **Format:** [Body Part] — [risk description]; [Body Part] — [risk description]
- **Purpose:** Describes what fails or gets injured if the exercise is performed incorrectly or by a contraindicated athlete. Provides clinical detail for coaching explanations.
- **Example:** Knee — valgus collapse; Lumbar — flexion under load; Shoulder/Wrist — bar rack mobility
- **Special markers:** Some entries include warning symbols for high-risk flags specific to known athlete constraints (e.g., wrist extension load for wrist-injured athletes).

### Column 10: Notes / Coaching Cues
- **Type:** Free text
- **Purpose:** Technique cues, context, sport-specific application notes, and training implementation guidance. This is the coaching intelligence per exercise.

### Column 11: Equipment Substitutes
- **Type:** Free text with EX IDs where applicable
- **Purpose:** **Same exercise, different equipment only.** When the athlete has different equipment than what's specified in col 7, this field provides alternatives that maintain the same movement pattern and stimulus.
- **Fill rate:** 154/245 (62%). Many exercises have no meaningful equipment swap (you can't substitute terrain for a scree field or open water for a river). Blank entries are correct.
- **Rule:** This column does NOT contain terrain substitutes or physical proxies. Those belong in col 12.
- **Improvised gear:** Entries prefixed with 🏠 are real-world improvised alternatives (gallon jugs, backpacks, chairs, stairs, towels, etc.) for athletes without gym access. These are programmatically identifiable by the 🏠 prefix.
- **Examples:** DB Romanian Deadlift; KB Deadlift; Trap Bar Deadlift / 🏠 Gallon water jug (~8.5 lb) as light goblet load; filled suitcase held at chest

### Column 12: Physical Proxy Exercises
- **Type:** EX ID references with names, semicolon-separated
- **Format:** EX117 — Loaded Step-Down (Eccentric Box); EX020 — Nordic Hamstring Curl
- **Purpose:** **Can't do the exercise at all — train these instead.** Physical proxies train the same primary physical qualities using available equipment when the technical context (terrain, vessel, weapon, conditions) is unavailable.
- **Fill rate:** 245/245 (100%) — every exercise has at least one entry.
- **Logic by exercise type:**
  - Strength: same movement pattern with available equipment
  - Technical / Skill: exercises training the primary physical components of the skill (e.g., Fell Descent -> Loaded Step-Down + Nordic Hamstring Curl + Ankle Hops = eccentric quad + hamstring protection + reactive ankle stability)
  - Plyometric: same reactive/power quality with available equipment
  - Isometric: similar joint angle loading with available setup
  - Aerobic / Interval: cross-training modality at equivalent intensity
  - Activation: most similar activation exercise with available equipment

### Column 13: Contraindicated Body Parts
- **Type:** Structured comma-separated list
- **Format:** Knee, Shoulder, Wrist
- **Purpose:** Body part labels parsed from Injury Flags (col 9), structured for programmatic filtering.
- **Fill rate:** 245/245 (100%)
- **Usage:** If any body part in the athlete's injury list appears in an exercise's contraindications, exclude or flag the exercise. Use col 9 for the clinical detail explaining why.

### Column 14: Progression Exercise
- **Type:** Single EX ID reference with name
- **Format:** EX089 — Hollow Body Hold
- **Purpose:** The next harder version within the same movement family.
- **Fill rate:** 95/245 (39%) — intentionally sparse. Only populated where a clear, unambiguous in-DB progression exists. Blank means no meaningful harder version exists in the current DB.
- **Rule:** Progression chains are short (usually 1-2 steps). Do not assume chains are exhaustive.

### Column 15: Regression Exercise
- **Type:** Single EX ID reference with name
- **Format:** EX216 — Plank (Front)
- **Purpose:** The easier version within the same movement family.
- **Fill rate:** 107/245 (44%) — same principle as Progression.

### Column 16: Sport Count
- **Type:** Formula
- **Formula:** =COUNTIF('Sport-Exercise Map'!A:A, A{row})
- **Purpose:** Auto-calculates how many sport mappings exist for each exercise.
- **Usage:** High Sport Count (>10) indicates a cross-disciplinary anchor exercise applicable to almost any programme. Low Sport Count (1-2) indicates a sport-specific specialist.

---

## 4. Sport-Exercise Map — Column-by-Column Schema

### Column 1: Exercise ID
- **Type:** String (foreign key to Exercise Master col 1)

### Column 2: Exercise Name
- **Type:** String (denormalised from Master — do not use as key)

### Column 3: Exercise Type
- **Type:** String (denormalised from Master — for in-sheet filtering convenience)

### Column 4: Sport
- **Type:** String (36 distinct values — see Section 6)

### Column 5: Sport Relevance Note
- **Type:** Free text
- **Purpose:** Explains why this exercise matters for this specific sport at this priority level. This is the highest-value field in the Map sheet. It describes the mechanism of transfer, not just the existence of an association.
- **Example for EX021 (Bulgarian Split Squat) in Trail Running:** Best single lower body exercise for trail running; mimics single-leg descent braking mechanics
- **Example for the same exercise in Mountain Biking:** Unilateral leg strength; addresses pedaling asymmetry and supports single-leg climbing power

### Column 6: Priority
- **Type:** Controlled vocabulary (4 values)
- **Values:**
  - **Critical** — Core to performance or safety. Absence would meaningfully impair race outcomes or create injury risk.
  - **High** — Strong carryover. Should be in regular training rotation.
  - **Medium** — Useful but not essential. Rotate in periodically.
  - **Low** — Minor contribution or indirect benefit.
- **Key rule:** Priority is sport-specific, not absolute. The same exercise has different priority in different sports. Always query priority from the Map sheet for the athlete's specific sport. Never assume priority from the Master sheet (which has no priority field).

---

## 5. Substitution and Fallback Logic

The database provides a four-tier fallback system. When an exercise is unavailable, the system checks in this order:

### Tier 1: Equipment Available
**Condition:** Athlete's location inventory matches exercise Equipment (col 7).
**Action:** Programme exercise as written.

### Tier 2: Equipment Substitute Available
**Condition:** Equipment Substitutes (col 11) lists a non-improvised alternative that matches the athlete's inventory.
**Action:** Swap to the substitute. The movement pattern and training stimulus remain the same.
**Example:** Barbell Romanian Deadlift -> DB Romanian Deadlift; KB Deadlift; Trap Bar Deadlift

### Tier 3: Improvised Option Plausible
**Condition:** Equipment Substitutes (col 11) contains a 🏠-prefixed improvised entry.
**Action:** Suggest the improvised option alongside the Physical Proxy as alternatives. Present as: "Try [improvised version] if you have [common object] available, or do [Physical Proxy] instead." The athlete chooses. Improvised items are not asked about during onboarding — they are auto-suggested at exercise-prescription time.
**Example:** No dip station -> "Try dips on a sturdy chair if available, or do Tricep Pushdowns with a band as an alternative."

### Tier 4: No Equipment Match
**Condition:** Nothing in col 7, col 11, or 🏠 entries matches the athlete's inventory.
**Action:** Fall back to Physical Proxy (col 12) — completely different exercises that train the same physical qualities.
**Example:** Scree Running Descent -> EX033 (Depth Drop) + EX035 (Ankle Hops) + EX044 (BOSU Single-Leg Squat)

### Regression (separate from equipment fallback)
**Question:** Is this exercise too hard for the athlete's current level?
**Action:** Drop to the Regression (col 15). When the athlete masters the regression, progress back.
**Example:** Hollow Body Hold -> Plank (Front) -> Bird-Dog

### Asymmetric loading principle
When a bilateral exercise exists (Back Squat EX001, Bench Press EX229, Hang Clean EX232), the database also contains asymmetric variants (Single-Arm KB Front Squat EX241, Single-Arm DB Bench Press EX242, Single-Arm KB Clean EX245). The asymmetric variant creates an anti-lateral-flexion or anti-rotation core demand that the bilateral version does not produce. The system should consider prescribing the asymmetric variant when:
- The athlete's sport involves asymmetric force production (paddling, pack carry, single-arm tasks)
- Core stability is a training focus
- Left-right imbalances need correction

---

## 6. Sports Covered (36)

Grouped by discipline category:

**Adventure Racing disciplines (10):**
Trail Running, Orienteering, XC / AR Cycling, Mountain Biking, Packrafting, Hiking, Rock Climbing, Rappelling / Abseiling, Fixed Rope / Via Ferrata, Long Distance Orienteering

**Running disciplines (4):**
Marathon, Ultramarathon, Mountain Running / Sky Running, Fell Running

**Cycling disciplines (3):**
Road Cycling, Gravel Cycling, Bikepacking

**Multi-discipline / Combined (5):**
Triathlon, Run-Bike-Run Duathlon, SwimRun, Multi-Sport Race, Modern Pentathlon

**Paddle sports (6):**
Kayaking, Canoeing, Paddle Rafting, Long Distance Paddle Racing, Rowing, SUP

**Water sports (1):**
Swimming

**Winter sports (4):**
Mountaineering, Snowshoeing, SkiMo, XC Skiing

**Combat / Precision / Obstacle (2):**
Fencing, Obstacle Course Racing

**Foundation (1):**
General Conditioning

### Duration variants
Several sports exist in both base and long-distance variants: Kayaking vs Long Distance Paddle Racing, Orienteering vs Long Distance Orienteering. The long-distance versions share most exercises but with upgraded priorities. Duration changes what's race-limiting.

### General Conditioning
Added as a catch-all sport for exercises that support whole-body fitness and foundational strength across all sports. This includes core basics, compound lifts, isolation/joint health work, and functional movements. When an athlete's sport isn't in the database, General Conditioning provides the base exercise set.

---

## 7. Key Query Patterns

### 7.1 Get all exercises for a sport, sorted by priority
Query Sport-Exercise Map where Sport = [target]. Sort by Priority (Critical > High > Medium > Low). Join to Exercise Master on Exercise ID for full detail.

### 7.2 Filter by available equipment
Parse Exercise Master Equipment (col 7) as comma-separated list. Match against athlete's equipment inventory. Where equipment unavailable, fall back to Equipment Substitutes (col 11) then Physical Proxy (col 12).

### 7.3 Filter for injury constraints
Parse Contraindicated Body Parts (col 13) as comma-separated list. If any body part in the athlete's injury list appears, exclude or flag the exercise. Use Injury Flags (col 9) for the clinical detail when explaining to the athlete.

### 7.4 Find substitutes when an exercise is unavailable
Four-tier lookup in order:
1. Equipment Substitutes (col 11) — same exercise, different equipment
2. Improvised option (col 11, 🏠 entries) — suggest alongside Physical Proxy as athlete's choice
3. Physical Proxy (col 12) — can't do the exercise at all, train the components
4. Regression (col 15) — exercise is too hard (separate from equipment fallback)

### 7.5 Build a progression chain
Follow Progression (col 14) and Regression (col 15) references. Chains are short (1-2 steps). Do not assume exhaustive chains exist.

### 7.6 Find cross-sport exercises
Use Sport Count (col 16). High count (>10) = general conditioning anchor. Count of 1-2 = sport specialist.

### 7.7 Gate sport-specific exercises by gear readiness
The Athlete Onboarding Schema (Section 2.2) includes gear readiness toggles per discipline per location. When a gear readiness toggle is unchecked (e.g., athlete has no climbing gear at their travel location), substitute all Technical / Skill exercises for that discipline with their Physical Proxies (col 12). This is location-specific — the same athlete may have gear at home but not while traveling.

### 7.8 Programme for asymmetric sports
When the sport involves asymmetric loading (paddling, pack carry, single-blade strokes), include at least one asymmetric loading exercise per session: EX241, EX242, EX243, EX244, or EX245.

### 7.9 Select appropriate core exercises
The database contains a full core progression chain:
- **Foundation:** Plank (EX216), Dead Bug (EX217), Bird-Dog (EX218), Side Plank (EX219)
- **Intermediate:** Mountain Climber (EX221), Bicycle Crunch (EX224), V-Sit Hold (EX225), Compression Tuck Hold (EX227)
- **Advanced:** Hollow Body Hold (EX089), Ab Wheel Rollout (EX222), L-Sit (EX226), Hanging Knee Raise / Toes-to-Bar (EX223)
- **Sport-specific:** Pallof Press (EX011), Cable Chop (EX087), Russian Twist (EX088), Swim Rotational Core (EX129)
- **Lateral plane:** Side Plank (EX219), Copenhagen Plank (EX012), Suitcase Carry (EX243)

An athlete who cannot hold a 60-second plank should not be prescribed Ab Wheel Rollouts. Always verify the athlete can perform the regression before prescribing the exercise.

---

### 7.9 Substitute with improvised equipment
The Equipment Substitutes column (col 11) includes real-world improvised gear entries prefixed with 🏠. These are **not asked about during onboarding** — the system auto-suggests them at exercise-prescription time when the athlete's location lacks the required equipment. See the Athlete Onboarding Schema (Section 2.3) for the full auto-suggestion logic.

**Common improvised substitutions the database uses:**

| Real-World Object | Substitutes For | Approx. Weight |
|---|---|---|
| Gallon water jug | Light dumbbell, light kettlebell | ~8.5 lb / 3.8 kg |
| Backpack loaded with books or water | Weighted vest, light-moderate dumbbell, kettlebell | 10–40 lb / 5–18 kg variable |
| Filled suitcase or duffel bag | Heavy dumbbell, sandbag, kettlebell | 20–50 lb / 9–23 kg variable |
| Sturdy chair | Bench, box, dip station, rear foot elevation, step-up platform |  |
| Hotel/building stairs | Stair climber, hill repeats, step-ups, calf raise platform |  |
| Towel (over door or bar) | TRX/suspension trainer, grip texture, inverted row anchor |  |
| Bed frame / heavy furniture | Anchor point for Nordics, band anchoring, hip thrust bench |  |
| Park bench | Box, bench, step-up platform, incline/decline surface |  |
| Tree branch / playground bar | Pull-up bar, dead hang, monkey bars |  |
| Doorframe | Pull-up bar mount point, band anchor, stretch support |  |
| Countertop / table edge | Dip station, inverted row anchor, incline push-up support |  |
| Broomstick | Barbell for mobility drills, wrist roller dowel, pattern practice |  |
| Bag of rice or dried beans | Rice bucket grip training, light resistance |  |
| Tennis ball / water bottle | Foam roller for targeted tissue work |  |
| Towel or belt loop | Resistance band (light), knee/ankle loop for activation drills |  |
| Rubber bands / hair ties | Finger extension bands for antagonist grip work |  |
| Stair edge or curb | Step for calf raise full ROM, depth drop platform |  |
| Pillow or folded towel | Knee pad, hip pad, elbow comfort on hard floors |  |

**Query logic:** When the athlete declares they have no gym equipment, filter Exercise Master for exercises where Equipment (col 7) includes "Bodyweight" OR where Equipment Substitutes (col 11) contains 🏠 entries. The 🏠 prefix makes these programmatically identifiable.

**Important caveat for the coaching system:** Improvised equipment is a compromise, not an equivalent. A gallon jug (~8.5 lb) is not a 50 lb dumbbell. When substituting, the system should adjust prescribed load, rep range, or exercise selection to match what the improvised equipment can actually provide. A backpack deadlift at 30 lb does not replace a barbell deadlift at 225 lb — but it does maintain the hinge pattern and prevent detraining.


---

## 8. Anti-Patterns — What Not To Do

**Don't use Exercise Name as a key.** Names contain modality qualifiers and can be ambiguous. Always join on Exercise ID.

**Don't read Priority from the Master sheet.** The Master has no priority field. Priority is sport-specific and lives in the Map sheet only.

**Don't conflate Physical Proxy with Progression.** Physical Proxy trains the same physical qualities when the context is unavailable. Progression is the next harder version. Depth Drop (EX033) is a Physical Proxy for Scree Running (EX213), not a progression toward it.

**Don't expect Equipment Substitutes on Technical / Skill exercises.** Many have blank Equipment Substitutes because the equipment is the context — a paddleboard, a rappel device, a ski slope. Blank is correct. Always check Physical Proxy instead.

**Don't conflate Injury Flags with Contraindications.** Injury Flags (col 9) = free text clinical detail. Contraindicated Body Parts (col 13) = structured list for filtering. Use col 13 for programmatic filtering; use col 9 for coaching explanations.

**Don't strip bilateral exercises when asymmetric variants exist.** Both serve a purpose. The bilateral version (Back Squat) builds the strength ceiling. The asymmetric variant (Single-Arm KB Front Squat) builds the lateral stability that transfers to sport. Programme both.

**Don't programme advanced core without verifying the foundation.** The database contains both foundation (Plank, Dead Bug) and advanced (Ab Wheel, L-Sit) core work. The progression chain exists for a reason — skipping it creates injury risk and ineffective training.

---

## 9. Extension Rules

### Adding a new exercise
1. Check whether an existing exercise already captures the same movement pattern, primary muscles, and injury profile. If yes, add a sport mapping to the Map sheet — not a new exercise.
2. Assign the next sequential EX ID. Do not reuse deleted IDs.
3. Populate all 16 columns. Physical Proxy (col 12) and Contraindicated Body Parts (col 13) are mandatory. Equipment Substitutes (col 11), Progression (col 14), and Regression (col 15) are optional but should be populated where obvious relationships exist.
4. All controlled vocabulary values (Type, Pattern, Priority, Novelty) must match the Legend exactly.

### Adding a new sport
1. Audit the existing Map sheet first. Most exercises will already exist — the primary task is mapping them with sport-specific relevance notes and priorities, not creating new exercises.
2. New exercises are only needed when the sport has a genuinely absent stimulus — a movement pattern, injury profile, or technical skill not covered by any existing entry.
3. The guiding rule: **no padding with near-duplicates.** If an existing exercise covers the pattern, map it.

### Adding a sport mapping
1. Always write a Sport Relevance Note (col 5). This explains why the exercise matters for this sport — the mechanism, not just the association.
2. Calibrate Priority against other exercises in the same sport, not in isolation.
3. Check whether the same exercise is already mapped to a related sport — the relevance note should explain what's different about this sport's use.

---

## 10. Build History

The database was built iteratively, adding sports in batches with a strict no-padding rule: new exercises only when no existing exercise captured the stimulus.

**Build order:**
1. AR primary disciplines (Trail Running, Orienteering, Mountain Biking, Packrafting)
2. AR support sports (Hiking, Rock Climbing, Rappelling, Fixed Rope, Swimming)
3. XC/AR Cycling, Mountaineering, Snowshoeing
4. AR paddle sports (Kayaking, Canoeing, Paddle Rafting)
5. SkiMo, Triathlon
6. Marathon, Ultramarathon
7. Long distance cycling (Road, Gravel, Bikepacking)
8. Modern Pentathlon (Fencing, OCR, Shooting)
9. Duathlon (Run-Bike-Run, SwimRun)
10. Rowing, XC Skiing, SUP
11. Duration variants (LD Paddle Racing, LD Orienteering, Multi-Sport Race)
12. Mountain Running / Sky Running, Fell Running
13. General conditioning, compound lifts, core basics, isolation, asymmetric loading

Physical Proxy was added at step 12 and retrofitted to all exercises. Core foundations and asymmetric loading were added at step 13 after auditing the database against real training plans and identifying structural gaps. Improvised real-world equipment substitutes (🏠 entries) were added at step 14, covering 122 exercises with alternatives using common objects: gallon jugs, loaded backpacks, chairs, stairs, towels, park benches, and similar items accessible to athletes without gym access.

The Athlete Onboarding Schema (v3) defines how athlete data maps to database queries: sport selection drives the Sport-Exercise Map lookup, equipment inventory drives the four-tier substitution logic, gear readiness toggles gate Technical / Skill exercises per location, injury records filter against Contraindicated Body Parts (col 13) and Injury Flags (col 9), fitness benchmarks gate progression/regression chains (cols 14/15), and FIT file integration auto-populates aerobic benchmarks where available.

---

## 11. Statistics Summary

| Metric | Value |
|---|---|
| Total exercises | 245 |
| Total sport mappings | 1,068 |
| Sports covered | 36 |
| Exercise types in use | 15 (17 defined) |
| Movement patterns | 20 |
| Common exercises | 102 (42%) |
| Specialized exercises | 143 (58%) |
| Physical Proxy fill rate | 245/245 (100%) |
| Contraindicated Body Parts fill rate | 245/245 (100%) |
| Equipment Substitutes fill rate | 154/245 (62%) |
| Progression fill rate | 95/245 (39%) |
| Regression fill rate | 107/245 (44%) |

---

## 12. Column Reference — Quick Lookup

| # | Column | Type | Required | Fill Rate | Notes |
|---|---|---|---|---|---|
| 1 | Exercise ID | PK | Yes | 100% | EX001-EX245 sequential |
| 2 | Exercise Name | String | Yes | 100% | Include modality qualifier |
| 3 | Exercise Type | CV | Yes | 100% | 17 valid values — see Legend |
| 4 | Movement Pattern | CV | Yes | 100% | Comma-separate multiples |
| 5 | Primary Muscles | Free | Yes | 100% | Comma-separated list |
| 6 | Secondary Muscles | Free | Yes | 100% | Comma-separated list |
| 7 | Equipment | Free | Yes | 100% | Comma-separated; env matching |
| 8 | Novelty | CV | Yes | 100% | Common or Specialized |
| 9 | Injury Flags | Free | Yes | 100% | [Part] — [risk]; [Part] — [risk] |
| 10 | Notes / Cues | Free | Yes | 100% | Technique + sport context |
| 11 | Equipment Subs | Free+ID | Optional | 62% | Same exercise, different kit + improvised gear |
| 12 | Physical Proxy | ID+Name | Yes | 100% | Can't do exercise — train this |
| 13 | Contraindications | Parsed | Yes | 100% | Structured body part list |
| 14 | Progression | ID+Name | Optional | 39% | Next harder in same family |
| 15 | Regression | ID+Name | Optional | 44% | Easier version in same family |
| 16 | Sport Count | Formula | Auto | 100% | =COUNTIF(Map!A:A, A{row}) |

**Key:** PK = Primary Key | CV = Controlled Vocabulary | Free = Free text | ID = EX ID reference
