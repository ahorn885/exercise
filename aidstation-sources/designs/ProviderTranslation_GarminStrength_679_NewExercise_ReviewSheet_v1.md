# #679 — New-Exercise & Catalog Review Sheet (for Andy)

**Edit this doc directly — fill the `DECISION` and `NOTES` columns, change any `rx`/pattern call.**
I author migration `0012` from your marks. Reads with the worklist:
`ProviderTranslation_GarminStrength_679_CandidateBatch_v1.md` (Round 2).

Legend — **DECISION**: `mint` (new EX-id) · `leave` (stay bucket-3, recorded but not prescribable) · `map:EXxxx` (alias to an existing one instead) · `skip`.
`rx` = the progression class it loads as. `MP` = layer0 `movement_patterns` I'd tag it. Strike/replace anything.

---

## Part 1 — New exercises: mint / leave / map?  (Trigger #2 — no-padding)

### 1a. Clear-mint candidates (my rec: **mint**)

| # | Exercise | Proposed MP | rx | Equip | DECISION | NOTES |
|---|---|---|---|---|---|---|
| 1 | Dip | {Push-V} | Push | Dip bars / BW | | |
| 2 | Walking Lunge | {Single-Leg, Locomotion} | Lunge | DB / BW | | |
| 3 | Push Press | {Push-V} | Push | Barbell / DB | | |
| 4 | Single-Leg Glute Bridge | {Hip-Ext, Single-Leg} | Hinge | BW | | |
| 5 | KB Snatch | {Hinge, Pull-V} | Hinge | Kettlebell | | |
| 6 | KB Clean & Press | {Hinge, Push-V} | Hinge | Kettlebell | | |
| 7 | Single-Arm KB Swing | {Hinge} | Hinge | Kettlebell | | |
| 8 | Rack Carry | {Carry, Isometric} | Carry | KB / DB | | |
| 9 | Renegade Row | {Pull-H, Anti-Rotation} | Pull | DB | | |
| 10 | Straight-Arm Lat Pulldown | {Pull-V} | Pull | Cable | | |
| 11 | Sandbag Get-Up | {Anti-Lateral-Flexion, Isometric} | Core | Sandbag | | |
| 12 | Front Lever Progression | {Anti-Extension, Pull-V} | Pull | Pull-up bar | | |
| 13 | L-Sit Pull-Up | {Pull-V, Anti-Extension} | Pull | Pull-up bar | | |
| 14 | KB Sumo Deadlift | {Hinge} | Hinge | Kettlebell | | |
| 15 | Banded Pull-Through | {Hip-Ext} | Hinge | Band | | |
| 16 | Lunge to Rotation | {Single-Leg, Rotation} | Lunge | Slam ball / DB | | |
| 17 | Stability Ball Hamstring Curl | {Hip-Ext} | Hinge | Stability ball | | |

### 1b. From Batch A — your earlier requests (my rec: **mint**)

| # | Exercise | Proposed MP | rx | Equip | DECISION | NOTES |
|---|---|---|---|---|---|---|
| 18 | Overhead Bulgarian Split Squat | {Single-Leg} | Lunge | DB / KB | | |
| 19 | Wide-Grip Seated Cable Row | {Pull-H} | Pull | Cable | | |
| 20 | Close-Grip Lat Pulldown | {Pull-V} | Pull | Cable | | |
| 21 | Chest Flye | {Push-H} | Push | DB / Cable | | |
| 22 | Hack Squat | {Squat} | Squat | Machine / Barbell | | |
| 23 | Box Squat | {Squat} | Squat | Barbell | | |
| 24 | Standing Calf Raise | {Isometric} | Various | BW / Machine | | |
| 25 | Spiderman Plank | {Anti-Extension, Anti-Rotation} | Core | BW | | |
| 26 | Side Kick Plank | {Anti-Lateral-Flexion} | Core | BW | | |
| 27 | Side Plank Lift | {Anti-Lateral-Flexion} | Core | BW | | |

### 1c. Borderline — your call (my rec in NOTES)

| # | Exercise | Proposed MP | rx | DECISION | NOTES (my rec) |
|---|---|---|---|---|---|
| 28 | Battle Ropes | {Locomotion} | Various | | rec **leave** — conditioning, not a progressing load |
| 29 | Treadwall Intervals | — | — | | rec **leave** — cardio-climb |
| 30 | Seated Glute Squeeze (Iso) | {Hip-Ext, Isometric} | Core | | rec **leave** — minor iso |
| 31 | Sumo Deadlift High Pull | {Hinge, Pull-V} | Hinge | | your call — real but niche |
| 32 | KB Windmill | {Rotation, Anti-Lateral-Flexion} | Rotation | | your call |
| 33 | Pedal Stance Deadlift | {Hinge, Single-Leg} | Hinge | | rec **map:EX004** (kickstand RDL) — not mint |
| 34 | Forearm Wrist Curls | {—} | — | | wrist-flexion — mint w/ hard contraindication flag, or **leave**? (your left wrist) |

---

## Part 2 — Renames: drop the equipment qualifier? (confirm)

| EX | Current name | → Proposed | DECISION | NOTES |
|---|---|---|---|---|
| EX002 | Goblet Squat (DB/KB) | Goblet Squat | | |
| EX231 | Front Squat (Barbell / KB) | Front Squat | | |
| EX016 | Thoracic Rotation Drill | Thoracic Rotation | | |
| EX081 | Band Face Pull | Face Pull | | |
| EX061 | Good Morning (Barbell) | Good Morning | | |
| EX111 | Reverse Wrist Curl (DB) | Reverse Wrist Curl | | |
| EX021 | Bulgarian Split Squat (DB) | Bulgarian Split Squat | | |

---

## Part 3 — Already-shipped `M`-confidence aliases (flag any to re-route)

These are live (PR #701). I routed each to the nearest canonical; mark `re-route:EXxxx` or `→ new` on any you'd rather handle differently.

| Logged name | Mapped to | OK? / re-route | NOTES |
|---|---|---|---|
| 1,000 Step-Up Challenge | EX024 Step-Up High Box | | |
| 4-Side Box Step-Up/Off | EX024 Step-Up High Box | | |
| 7/3 Repeaters (Hangboard) | EX100 Hangboard Half-Crimp Hold | | |
| Asymmetric Stab. Ball Push-Up | EX228 Push-Up | | |
| Cable Woodchop (Low-to-High) | EX087 Cable High-to-Low Chop | | |
| Elevated Reverse Lunge | EX022 Reverse Lunge | | |
| Glute Bridge / Hip Thrust | EX039 Glute Bridge (Double-Leg) | | |
| Half-Kneeling 1-Arm Cable Row | EX078 Single-Arm DB Row | | |
| Hangboard Max Hangs | EX100 Hangboard Half-Crimp Hold | | |
| Hanging Leg Raise in Boots | EX223 Hanging Knee Raise | | |
| Hillbounding | EX036 Running Bounds | | |
| KB Swing on Inverted BOSU | EX031 Kettlebell Swing | | |
| Med Ball Torso Rotation (Seated) | EX088 Russian Twist | | |
| Nasal-Breathing-Only Climbing | EX139 On-Wall Breathing Control | | |
| Oblique Press (Contralateral) | EX011 Pallof Press | | |
| Plank with Rotation | EX216 Plank (Front) | | |
| Rapid Calf Raises | EX025 Single-Leg Calf Raise | | |
| Sandbag / Pack Carry (Bear Hug) | EX095 Portage Carry Simulation | | |
| Side Plank + Banded Leg Raise | EX219 Side Plank | | |
| Side Split Lunges (Deep) | EX023 Lateral Lunge | | |
| Single-Leg Stance Eyes Closed | EX043 Single-Leg Balance Hold | | |
| Sled Pull (Hand-Over-Hand) | EX030 Reverse Sled Drag | | |
| Stability Ball Seated Shoulder Press | EX098 DB Shoulder Press | | |
| Stability Ball Single-Arm DB Press | EX242 Single-Arm DB Bench Press | | |
| Standing Figure-4 Stretch | EX015 Pigeon Pose | | |
| Standing Hip Flexor Stretch | EX046 Hip Flexor Lunge Stretch | | |
| TRX Mtn Climber / Unstable Bar | EX221 Mountain Climber | | |
| Towel Pull-Up | EX006 Pull-Up (BW) | | |
