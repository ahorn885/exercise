# #679 — Garmin strength → EX-id: consolidated candidate batch for ratification (D-10)

**Status:** AWAITING ANDY (one consolidated batch, per D-10 / design §5). Produced at the end of the #679 build (PR for `claude/upbeat-euler-q4ucqa`).
**Date:** 2026-06-17
**Reads with:** `designs/ProviderTranslation_GarminStrength_679_Design_v1.md` (the ratified design), `provider_strength_resolve.py` (the shipped resolver).

---

## What already shipped (no ratification needed — safe core)

The resolver (`provider_strength_resolve.resolve_strength_ex_id`) ships with two
HITL-free layers, because neither adds vocabulary:

1. **12 token-set-exact Garmin aliases** (`GARMIN_STRENGTH_ALIASES`) — deterministic
   equivalences (identical normalized token sets), e.g. `Dumbbell Hammer Curl` → EX234.
2. **Category-collapse backstop** over the **11 Garmin categories that already have a
   coarse home in the ratified `NAME_TO_EX_ID`** — this alone routes **582** specific
   subtypes (Bench Press 27, Curl 44, Deadlift 19, Lateral Raise 34, Plank 135,
   Pull Up 39, Push Up 79, Row 34, Sit Up 38, Squat 92, Triceps Extension 41) to their
   coarse EX-id with zero new decisions.

Everything below is what the safe core leaves on the table — your call, in one pass.

**Provenance / re-run:** the candidate lists were generated offline by enumerating the
Garmin name space from `fit_tool` (`garmin_fit_parser._build_exercise_subtype_map`,
1,239 subtypes) × the live layer0 strength catalog (`etl/output/layer0_etl_v1.8.0.sql`
`superseded_at IS NULL` + migration 0011's EX246–249), token-set-exact for the seed and
`difflib` ratio for the fuzzy candidates. (No `rapidfuzz` runtime dep was added — see the
deviation note in the handoff.)

---

## Batch A — fuzzy alias candidates (accept → add to `GARMIN_STRENGTH_ALIASES`)

Each row is a specific Garmin name with **no** token-exact match but a plausible specific
EX-id. **REC = my recommendation.** "Covered by collapse" rows already resolve correctly
to a coarse EX-id today — listed only so you know they're handled (no alias needed).

| Garmin name | Proposed EX-id | REC | Note |
|---|---|---|---|
| Goblet Squat | EX002 Goblet Squat (DB/KB) | ✅ accept | exact concept, equipment-qualified name |
| Barbell Front Squat | EX231 Front Squat (Barbell/KB) | ✅ accept | |
| Thoracic Rotation | EX016 Thoracic Rotation Drill | ✅ accept | |
| Cable External Rotation | EX082 External Rotation (Band/Cable) | ✅ accept | |
| Band External Rotation | EX082 External Rotation (Band/Cable) | ✅ accept | |
| Face Pull | EX081 Band Face Pull | ✅ accept | |
| Fire Hydrant Kicks | EX042 Donkey Kick / Fire Hydrant | ✅ accept | |
| Seated Barbell Good Morning | EX061 Good Morning (Barbell) | ✅ accept | |
| Split Barbell Good Morning | EX061 Good Morning (Barbell) | ✅ accept | |
| Single Leg Barbell Good Morning | EX061 Good Morning (Barbell) | ✅ accept | |
| High Box Jump | EX007 Box Jump | ✅ accept | |
| Barbell Reverse Wrist Curl | EX111 Reverse Wrist Curl (DB) | ✅ accept | |
| Reverse Grip Wrist Curl | EX111 Reverse Wrist Curl (DB) | ✅ accept | |
| Weighted Bicycle Crunch | EX224 Bicycle Crunch | ✅ accept | |
| Weighted Mountain Climber | EX221 Mountain Climber | ✅ accept | |
| Barbell Bulgarian Split Squat | EX021 Bulgarian Split Squat (DB) | ✅ accept | |
| Overhead Bulgarian Split Squat | EX021 Bulgarian Split Squat (DB) | ⚠️ your call | overhead-loaded variant |
| Wide Grip Seated Cable Row | EX079 Seated Cable Row (Narrow Grip) | ⚠️ your call | grip differs; else Row→EX246 |
| Close Grip Lat Pulldown | EX080 Lat Pulldown (Wide Grip) | ⚠️ your call | grip differs; else Pull Up→EX006 |
| Wall Slide | EX065 Scapular Wall Slide | ⚠️ your call | (NOT EX037 Wall Sit — fuzzy mismap) |
| Kettlebell Flye | — (keep bucket-3) | ❌ reject | fuzzy mismap to EX249 Halo; no pec-flye home |
| Barbell Hack Squat | — (collapse Squat→EX001) | ❌ reject | covered by collapse |
| Barbell Box Squat | — (collapse Squat→EX001) | ❌ reject | covered by collapse |
| Seated Lateral Raise | — (collapse Lateral Raise→EX233) | ✅ covered | resolves correctly today |
| Standing/Weighted Calf Raise | — (see Batch B: Calf Raise home) | → B | depends on Calf Raise category home |
| Spiderman / Side Kick Plank, Side Plank Lift | — (collapse Plank→EX216) | ✅ covered | generic-plank coarse is acceptable |

## Batch B — coarse category-home extensions (the high-leverage decisions)

These **19 strength-relevant Garmin categories have no coarse home** today, so all their
subtypes fall to bucket-3. Pointing each at one existing coarse EX-id (one decision)
rescues the whole category at once (subtype counts in parens). **REC** = best existing
candidate; ❓ = no clean existing home → keep bucket-3 **or** mint a new EX-id (Batch C).

| Garmin category | REC coarse home | subtypes rescued | Note |
|---|---|---|---|
| **Shoulder Press** | EX098 DB Shoulder Press | 24 | clean (0.90 match) |
| **Hang** | EX005 Dead Hang | 33 | clean |
| **Carry** | EX009 Farmer Carry | 5 | clean (already the carry staple) |
| **Leg Curl** | EX236 Leg Curl (Machine/Band) | 12 | clean |
| **Hyperextension** | EX220 Superman / Back Extension (BW) | 40 | clean |
| **Calf Raise** | EX026 Seated Calf Raise | 21 | seated≠standing — OK as coarse? your call |
| **Hip Raise** | EX019 Barbell Hip Thrust | 50 | thrust/bridge/glute-raise family |
| **Lunge** | EX022 Reverse Lunge (or EX023 Lateral) | 81 | which lunge is the coarse default? |
| **Crunch** | EX248 Sit-Up (or EX224 Bicycle Crunch) | 85 | trunk-flexion coarse |
| **Olympic Lift** | EX232 Hang Clean (Barbell/KB) | 21 | clean/snatch family; partial fit |
| **Core** | ❓ keep bucket-3 | 73 | too broad to collapse meaningfully |
| **Leg Raise** | ❓ keep bucket-3 / new EX-id | 22 | no hanging/lying leg-raise EX |
| **Flye** | ❓ keep bucket-3 / new EX-id | 10 | no pec-flye EX |
| **Shrug** | ❓ keep bucket-3 / new EX-id | 17 | no trap-shrug EX |
| **Chop** | ❓ EX087 Cable High-to-Low Chop? | 23 | EX087 is specific; coarse fit weak |
| **Hip Stability** | ❓ keep bucket-3 | 34 | activation family; many homes |
| **Shoulder Stability** | ❓ keep bucket-3 | 33 | activation family; many homes |
| **Hip Swing** | ❓ EX013 Hip Circle (Band)? | 3 | weak; tiny category |
| **Total Body** | ❓ keep bucket-3 | 13 | inherently mixed; don't collapse |

**How a Batch-B "yes" is applied:** add the category name → coarse EX-id to the resolver's
coarse map (a sibling of `NAME_TO_EX_ID`, or extend `NAME_TO_EX_ID` itself). One line per
category. No layer0 DDL.

## Batch C — new-EX-id candidates (Trigger #2 — strict no-padding)

The categories marked ❓ "new EX-id" in Batch B are the genuine gaps — common Garmin
families with **no** layer0 exercise covering the same stimulus. Candidates to mint
(precedent: EX246–249). Only if you want them prescribable; otherwise they stay bucket-3
(record-don't-drop — no data loss, surfaces inline in a later wave):

- **Pec Flye** (Flye, 10 subtypes) — horizontal-adduction isolation; no current home.
- **Trap Shrug** (Shrug, 17 subtypes) — scapular elevation; no current home.
- **Hanging/Lying Leg Raise** (Leg Raise, 22 subtypes) — hip-flexion core; EX248 Sit-Up is the nearest but distinct.

(Bar: *no existing EX-id covers the same physical stimulus / technique / injury profile.*)

---

## What I need from you

1. **Batch A:** strike any ✅ you disagree with; decide the four ⚠️ rows.
2. **Batch B:** confirm the clean ones (Shoulder Press, Hang, Carry, Leg Curl,
   Hyperextension), and rule on Calf Raise / Hip Raise / Lunge / Crunch / Olympic Lift
   (coarse home vs bucket-3), and the lunge-default question.
3. **Batch C:** mint / defer each of the three.

I'll apply your marks in a follow-up PR (alias rows + coarse-map lines; new EX-ids as a
gated `layer0` migration like 0011 if you greenlight Batch C). The shipped core stands on
its own regardless.

---

# Round 2 — `current_rx` vocabulary mapping (Andy: "map them all", 2026-06-17)

The read-only prod query showed the real precision target is **Andy's own logged
vocabulary** (117 `current_rx` rows), not the Garmin enum — his Garmin imports come in
*coarse* (`Squat`, `Deadlift`) and already resolve. Of the **97 unmapped** rows: everything
he's actually weighted/logged already had an EX-id; the rest are unperformed prescription
scaffolding. Classified all 97 against the live catalog: **70 → existing-EX alias (shipped),
24 → new exercise (0B batch), 1 → leave bucket-3, 1 (`Face Pull`) already aliased in Batch A,
+ his Garmin-name reqs from Batch A.**

## R2-A — Shipped aliases (audit + flag any wrong; `H`=same lift, `M`=close-variant lean)

`H` (same movement, naming/equipment only): Ab Wheel Rollout→EX222, Back Extension/Rev.Hyper→EX220,
Band Pull-Apart→EX066, Bent-Over Barbell Row→EX246, Bird Dog→EX218, Box Jump→EX007,
Cable Woodchop (High-to-Low)→EX087, Clamshell (Banded)→EX040, Copenhagen Plank→EX012,
Deadlift (Standard)→EX230, Dumbbell Chest Press→EX229, Fire Hydrant (Banded)→EX042,
Front Squat→EX231, Glute Kickback (Banded)→EX042, Good Morning→EX061, Hanging Knee Raise→EX223,
Isometric Lunge Hold→EX038, Kettlebell Swing (Two-Hand)→EX031, Lat Pulldown→EX080,
Med Ball Wall Throws (Rotational)→EX085, Mountain Climbers→EX221, Nordic Hamstring Curl→EX020,
Overhead Carry→EX244, Pallof Press→EX011, Pistol Squat→EX028, Pull-Up→EX006, Push-Up→EX228,
Rice Bucket→EX104, Romanian Deadlift→EX003, Russian Twist (Feet Elevated)→EX088,
Seated Cable Row→EX079, Single-Leg Calf Raise→EX025, Single-Leg Deadlift→EX004, Sled Push→EX029,
Step-Down (Eccentric)→EX117, Suitcase Carry→EX243, Turkish Get-Up→EX239, Wall Calf Stretch→EX047,
Wall Chest/Doorway Stretch→EX077, Wall Sit→EX037, Weighted Box Step-Up→EX119,
Weighted Treadmill Incline Walk→EX050.

`M` (close-variant lean — most likely to want a tweak): 1,000 Step-Up Challenge→EX024,
4-Side Box Step-Up/Off→EX024, 7/3 Repeaters (Hangboard)→EX100, Asymmetric Stab.Ball Push-Up→EX228,
Cable Woodchop (Low-to-High)→EX087, Elevated Reverse Lunge→EX022, Glute Bridge/Hip Thrust→EX039,
Half-Kneeling 1-Arm Cable Row→EX078, Hangboard Max Hangs→EX100, Hanging Leg Raise in Boots→EX223,
Hillbounding→EX036, KB Swing on Inverted BOSU→EX031, Med Ball Torso Rotation (Seated)→EX088,
Nasal-Breathing-Only Climbing→EX139, Oblique Press (Contralateral)→EX011, Plank with Rotation→EX216,
Rapid Calf Raises→EX025, Sandbag/Pack Carry (Bear Hug)→EX095, Side Plank + Banded Leg Raise→EX219,
Side Split Lunges (Deep)→EX023, Single-Leg Stance Eyes Closed→EX043, Sled Pull (Hand-Over-Hand)→EX030,
Stability Ball Seated Shoulder Press→EX098, Stability Ball Single-Arm DB Press→EX242,
Standing Figure-4 Stretch→EX015, Standing Hip Flexor Stretch→EX046, TRX Mtn Climber→EX221,
Towel Pull-Up→EX006.

## R2-B — New-exercise 0B batch (Trigger #2 — author specs, your per-entry sign-off)

From `current_rx` (24): Banded Pull-Through, Battle Ropes, Dip, Forearm Wrist Curls (flexion —
note your wrist injury), Front Lever Progression, KB Clean & Press, KB Snatch, KB Sumo Deadlift,
KB Windmill, L-Sit Pull-Up, Lunge to Rotation, Pedal Stance Deadlift, Push Press, Rack Carry,
Renegade Row, Sandbag Get-Up, Seated Glute Squeeze (Iso), Single-Arm KB Swing,
Single-Leg Glute Bridge, Stability Ball Hamstring Curl, Straight-Arm Lat Pulldown,
Sumo Deadlift High Pull, Treadwall Intervals, Walking Lunge.

From Batch A (10): Overhead Bulgarian Split Squat, Wide-Grip Seated Cable Row,
Close-Grip Lat Pulldown, Chest Flye, Hack Squat, Box Squat, Standing Calf Raise, Spiderman Plank,
Side Kick Plank, Side Plank Lift.

**= ~34 new exercises.** Each needs full 0B fields (movement_patterns→rx class, muscles,
equipment, injury flags, coaching cues, sport_exercise_map rows) + the alias. Authored as
migration `0012`, applied via gated `layer0-apply`. I'll bring the specs as a batch (likely
sliced by movement family) for sign-off — too big to ship blind.

## R2-C — Renames (drop equipment qualifiers; bundled into 0012)

EX002 `Goblet Squat (DB/KB)`→`Goblet Squat`, EX231 `Front Squat (Barbell/KB)`→`Front Squat`,
EX016 `Thoracic Rotation Drill`→`Thoracic Rotation`, EX081 `Band Face Pull`→`Face Pull`,
EX061 `Good Morning (Barbell)`→`Good Morning`, EX111 `Reverse Wrist Curl (DB)`→`Reverse Wrist Curl`,
EX021 `Bulgarian Split Squat (DB)`→`Bulgarian Split Squat`. Versioned 0B change (cache-invalidating)
+ denormalized-name updates across `sport_exercise_map`/proxies/progression/regression.

## R2-D — Leave bucket-3

`High-Rep Strength Endurance Sets` (a protocol, not a discrete exercise).
