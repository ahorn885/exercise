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
| 1 | Dip | {Push-V} | Push | Dip bars / BW | mint | |
| 2 | Walking Lunge | {Single-Leg, Locomotion} | Lunge | DB / BW |mint | |
| 3 | Push Press | {Push-V} | Push | Barbell / DB / KB|mint | |
| 4 | Single-Leg Glute Bridge | {Hip-Ext, Single-Leg} | Hinge | BW / kb / db/ barbell / weight plate| mint| |
| 5 | KB Snatch | {Hinge, Pull-V} | Hinge | Kettlebell | mint|mint but this should be generic snatch, allowing kb or barbell |
| 6 | KB Clean & Press | {Hinge, Push-V} | Hinge | Kettlebell |mint | mint but this should be generic clean and press, allowing kb or barbell |
| 7 | Single-Arm KB Swing | {Hinge} | Hinge | Kettlebell | mint| |
| 8 | Rack Carry | {Carry, Isometric} | Carry | KB / DB |mint | |
| 9 | Renegade Row | {Pull-H, Anti-Rotation} | Pull | DB /kb| mint| |
| 10 | Straight-Arm Lat Pulldown | {Pull-V} | Pull | Cable / band|mint | |
| 11 | Sandbag Get-Up | {Anti-Lateral-Flexion, Isometric} | Core | Sandbag | mint| |
| 12 | Front Lever Progression | {Anti-Extension, Pull-V} | Pull | Pull-up bar | mint| |
| 13 | L-Sit Pull-Up | {Pull-V, Anti-Extension} | Pull | Pull-up bar |mint | |
| 14 | KB Sumo Deadlift | {Hinge} | Hinge | Kettlebell |mint |mint but this should be generic sumo dl, allowing kb, db or barbell |
| 15 | Banded Pull-Through | {Hip-Ext} | Hinge | Band |mint | |
| 16 | Lunge to Rotation | {Single-Leg, Rotation} | Lunge | Slam ball / DB | mint|should allow kb and weight plates too |
| 17 | Stability Ball Hamstring Curl | {Hip-Ext} | Hinge | Stability ball |mint | |

### 1b. From Batch A — your earlier requests (my rec: **mint**)

| # | Exercise | Proposed MP | rx | Equip | DECISION | NOTES |
|---|---|---|---|---|---|---|
| 18 | Overhead Bulgarian Split Squat | {Single-Leg} | Lunge | DB / KB |mint | |
| 19 | Wide-Grip Seated Cable Row | {Pull-H} | Pull | Cable |mint | |
| 20 | Close-Grip Lat Pulldown | {Pull-V} | Pull | Cable | mint| |
| 21 | Chest Flye | {Push-H} | Push | DB / Cable | mint| |
| 22 | Hack Squat | {Squat} | Squat | Machine / Barbell |mint | |
| 23 | Box Squat | {Squat} | Squat | Barbell |mint | |
| 24 | Standing Calf Raise | {Isometric} | Various | BW / Machine / kb / kb |mint | |
| 25 | Spiderman Plank | {Anti-Extension, Anti-Rotation} | Core | BW | mint| |
| 26 | Side Kick Plank | {Anti-Lateral-Flexion} | Core | BW |mint | |
| 27 | Side Plank Lift | {Anti-Lateral-Flexion} | Core | BW | mint| |

### 1c. Borderline — your call (my rec in NOTES)

| # | Exercise | Proposed MP | rx | DECISION | NOTES (my rec) |
|---|---|---|---|---|---|
| 28 | Battle Ropes | {Locomotion} | Various | mint| rec **leave** — conditioning, not a progressing load  - andy's response - I think the progressive load is higher weight ropes, longer ropes, or just longer time period for the set|
| 29 | Treadwall Intervals | — | — |mint | rec **leave** — cardio-climb |
| 30 | Seated Glute Squeeze (Iso) | {Hip-Ext, Isometric} | Core |mint | rec **leave** — minor iso |
| 31 | Sumo Deadlift High Pull | {Hinge, Pull-V} | Hinge |mint | your call — real but niche - should have kb or barbell as required equipment|
| 32 | KB Windmill | {Rotation, Anti-Lateral-Flexion} | Rotation | mint| your call |
| 33 | Pedal Stance Deadlift | {Hinge, Single-Leg} | Hinge |mint | rec **map:EX004** (kickstand RDL) — not mint  - probably needs to map to kb or db?  not sure if feasible with bb?|
| 34 | Forearm Wrist Curls | {—} | — |mint | wrist-flexion — mint w/ hard contraindication flag, or **leave**? (your left wrist) - this app isnt just for me, do not add hard coded warnings like this|

---

## Part 2 — Renames: drop the equipment qualifier? (confirm)

| EX | Current name | → Proposed | DECISION | NOTES |
|---|---|---|---|---|
| EX002 | Goblet Squat (DB/KB) | Goblet Squat |confirm  - but add kb, db as required equipment| |
| EX231 | Front Squat (Barbell / KB) | Front Squat | confirm but add kb, db, bb as required equipment| |
| EX016 | Thoracic Rotation Drill | Thoracic Rotation |confirm | |
| EX081 | Band Face Pull | Face Pull |confirm, but add band or cable as required equipment | |
| EX061 | Good Morning (Barbell) | Good Morning | confirm but add bb or bodyweight as required equipment| |
| EX111 | Reverse Wrist Curl (DB) | Reverse Wrist Curl |confirm but add db, kb, cable, band, as required equipment  | |
| EX021 | Bulgarian Split Squat (DB) | Bulgarian Split Squat |confirm but add db or kb as required equipment | |

---

## Part 3 — Already-shipped `M`-confidence aliases (flag any to re-route)

These are live (PR #701). I routed each to the nearest canonical; mark `re-route:EXxxx` or `→ new` on any you'd rather handle differently.

| Logged name | Mapped to | OK? / re-route | NOTES |
|---|---|---|---|
| 1,000 Step-Up Challenge | EX024 Step-Up High Box |delete | |
| 4-Side Box Step-Up/Off | EX024 Step-Up High Box |confirm | |
| 7/3 Repeaters (Hangboard) | EX100 Hangboard Half-Crimp Hold |confirm | |
| Asymmetric Stab. Ball Push-Up | EX228 Push-Up | new ex| |
| Cable Woodchop (Low-to-High) | EX087 Cable High-to-Low Chop |new ex | |
| Elevated Reverse Lunge | EX022 Reverse Lunge |confirm |maybe add elevation as coach notes for progression? |
| Glute Bridge / Hip Thrust | EX039 Glute Bridge (Double-Leg) |confirm | |
| Half-Kneeling 1-Arm Cable Row | EX078 Single-Arm DB Row | confirm| |
| Hangboard Max Hangs | EX100 Hangboard Half-Crimp Hold | confirm| |
| Hanging Leg Raise in Boots | EX223 Hanging Knee Raise |confirm | |
| Hillbounding | EX036 Running Bounds | confirm|is this a cardio exercise? |
| KB Swing on Inverted BOSU | EX031 Kettlebell Swing |confirm |maybe add this as coach notes for progression |
| Med Ball Torso Rotation (Seated) | EX088 Russian Twist |confirm |maybe add as coach notes for progression |
| Nasal-Breathing-Only Climbing | EX139 On-Wall Breathing Control | confirm| |
| Oblique Press (Contralateral) | EX011 Pallof Press |confirm | |
| Plank with Rotation | EX216 Plank (Front) | new ex| |
| Rapid Calf Raises | EX025 Single-Leg Calf Raise | confirm| |
| Sandbag / Pack Carry (Bear Hug) | EX095 Portage Carry Simulation |change entirely - we should have a loaded carry option that both of these map to with options for kb, sandbag, db as required equipment | |
| Side Plank + Banded Leg Raise | EX219 Side Plank | new ex| |
| Side Split Lunges (Deep) | EX023 Lateral Lunge | confirm| |
| Single-Leg Stance Eyes Closed | EX043 Single-Leg Balance Hold | delete both of these| |
| Sled Pull (Hand-Over-Hand) | EX030 Reverse Sled Drag |confirm | |
| Stability Ball Seated Shoulder Press | EX098 DB Shoulder Press |confirm |maybe add this as coach notes for progression |
| Stability Ball Single-Arm DB Press | EX242 Single-Arm DB Bench Press | confirm|maybe add this as coach notes for progression |
| Standing Figure-4 Stretch | EX015 Pigeon Pose |confirm | |
| Standing Hip Flexor Stretch | EX046 Hip Flexor Lunge Stretch |confirm | |
| TRX Mtn Climber / Unstable Bar | EX221 Mountain Climber | confirm| |
| Towel Pull-Up | EX006 Pull-Up (BW) |new ex | |
