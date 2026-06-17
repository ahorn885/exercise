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
