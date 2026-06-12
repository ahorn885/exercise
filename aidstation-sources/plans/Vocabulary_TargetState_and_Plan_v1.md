# Vocabulary Target State + Implementation Plan — v1

**Date:** 2026-06-08 · **Branch:** `claude/v5-layer2c-handoff-988dgv`
**Consumes / supersedes:** the audit chain `Craft_Equipment_Vocabulary_Reconciliation_Audit_v1..v3.md`
+ the `Vocabulary_Reconciliation_v4.xlsx` workbook (Andy's first-column feedback, 2026-06-09).
This doc is the **decided end-state** and the ordered build plan. Decisions below are final
(Andy, via the v4 workbook + the follow-up Q&A); opens are explicitly marked.

---

## 1. Decisions ledger (resolved)

| Ref | Decision |
|---|---|
| Source of truth | `layer0.equipment_items` / `layer0.disciplines` (canonical) is authoritative; v1 `EQUIPMENT_CATEGORIES` + athlete craft enums are retired or projected from it. |
| #477 / #476 | **SUPERSEDED.** No full a/b/c split, **D-007 is NOT removed.** Keep generic D-006 / D-007 / D-008; ADD only **D-006b Gravel Cycling** + **D-008a Cross Country Cycling**. Both issues to be rewritten to this plan. |
| Orienteering | **Keep merged** into D-003 Trekking (no standalone re-add). Foot group covers it via D-003. |
| Vessel naming | Normalize every source-list to the **"Vessel" column** value (single canonical craft name). |
| Equipment categories | Recategorize **gym equipment only**; Sport-Specific vessels, Recovery & Therapy, Assumed Universal keep their categories. |
| D4 kayak split | D-010a/b was unverified; **dropped** — single D-010 Kayaking stays (no split surfaced in any decision). |
| D7 Mountaineering routing | **OPEN** — TRN-005 vs TRN-012 for D-018 (not blocking this arc). |

---

## 2. Target state — Disciplines

**Keep (no change):** D-001 Trail Running, D-002 Road Running, D-003 Trekking, D-004 Swimming,
D-006 Road Cycling, D-007 Time-Trial Cycling, D-008 Mountain Biking, D-009 Packrafting,
D-010 Kayaking, D-011 Canoeing, D-012 Rock Climbing, D-013 Abseiling, D-014 Via Ferrata,
D-017 Snowshoeing, D-018 Mountaineering, D-021 Uphill Skinning, D-022 Alpine Descent,
D-024 Mountain Running, D-027 Obstacle Course Racing, D-028 Cross-Country Skiing.

**ADD (new, to layer0 + canon + bridge):**

| ID | Name | Modality group(s) | Notes |
|---|---|---|---|
| D-006b | Gravel Cycling | **bike_pavement + bike_offroad** | replaces Endurance-Cycling bridge r59 |
| D-008a | Cross Country Cycling | bike_offroad | replaces r61 |
| d-SUP | Stand-up Paddleboard | paddle_flatwater | new craft discipline (final id TBD — see §6) |

**CHANGE:** D-019 Paddle Rafting → add **paddle_whitewater** (now paddle_flatwater + paddle_whitewater).

**Do NOT create:** D-006a, D-006c, D-008b (the #477 dupes). **Stay merged/removed:** D-005, D-015, D-016.

**Endurance-Cycling bridge** duplicate-discipline_id fix (the #477 bug) resolves to 5 distinct IDs:
r58→D-006, r59→**D-006b**, r60→D-007, r61→**D-008a**, r62→D-008.

---

## 3. Target state — Modality groups

| group_id | Description (NEW) | Members (target) |
|---|---|---|
| paddle_flatwater | Flatwater paddle | D-009, D-010, D-011, D-019, **d-SUP** |
| paddle_whitewater | Whitewater paddle | D-009, D-010, **D-019** |
| foot | **Foot** *(was "Foot (run / hike / nav)")* | D-001, D-002, D-003, D-024, D-027 |
| bike_pavement | Bike on pavement | D-006, D-007, **D-006b** |
| bike_offroad | Bike off-road | D-008, **D-006b**, **D-008a** |
| snow_travel | **Snow Travel (on foot)** *(was "Snow travel (foot)")* | D-017, D-018 |
| snow_glide | **Skiing** *(was "Snow travel (gliding)")* | D-021, D-022, D-028 |
| climb | **Roped climbing** *(was "Climbing (rope-protected)")* | D-012, D-013, D-014 |
| swim_openwater | Open-water swim | D-004 |

---

## 4. Target state — Craft vessels

Canonical name = the **Vessel** value; normalize `layer0.equipment_items`, the v1 picker, and the
athlete enum to it. "Maps to discipline(s)" feeds the X1b.3b craft→discipline alias substrate.

| Vessel (canonical) | Type | Maps to discipline(s) | Action |
|---|---|---|---|
| Road bike | cycling | D-006 | keep |
| Mountain bike | cycling | D-008, D-008a | keep |
| Gravel bike | cycling | D-006, D-006b, D-008a | keep |
| TT / triathlon bike | cycling | D-007 | add to v1 picker (catalog-only today) |
| Cycling trainer | cycling | all cycling disciplines (indoor) | rename from "Bike trainer"; normalize |
| Kayak | paddle | D-010 | keep |
| Canoe | paddle | D-011 | keep |
| Packraft | paddle | D-009 | keep |
| Stand-up Paddleboard | paddle | d-SUP | rename from "SUP"; add to v1 picker + ensure layer0 |
| Raft | paddle | D-019 | rename from "Inflatable raft"; add to v1 picker |

**Eliminate (prune):** Bike (generic), Surfski (enum-only), Sea kayak, Rowing shell.
*(Sea kayak prune touches ETL readers `sum_to_100.py` + `report.py` — handle in the equipment slice.)*

---

## 5. Target state — Terrain

| ID | Name (target) | Change |
|---|---|---|
| TRN-007 | **Technical Rock / Scree** | rename (UI tooltip already added per #444) |
| TRN-014 | Climbing Gym | `race_eligible = FALSE` (training-only) |
| TRN-015 | Pump Track / Skills Course | `race_eligible = FALSE` |
| TRN-016 | Indoor / Gym | `race_eligible = FALSE` |
| **TRN-018** | **Off Trail / Bushwhack** | NEW (next free id; TRN-017 is Moving Water). `race_eligible = TRUE` |

(`race_eligible` is a NEW terrain attribute — #445. D-018 routing semantics, D7, remains open.)

---

## 6. Target state — Equipment categories (gym only)

Recategorize `layer0.equipment_items` gym rows into this 6-category scheme (Sport-Specific vessels,
Recovery & Therapy, Assumed Universal **unchanged**):

| New category | Items |
|---|---|
| **Freeweights** | Barbell, EZ curl bar, Trap bar, Dumbbell, Kettlebell, Squat rack, Bench, + fold-in Tricep bar (W-bar), Preacher curl bench |
| **Machines - Strength** | Smith machine, GHD, Leg press, Hack squat, Leg extension, Leg curl, Standing/Seated calf raise, Hip abductor/adductor, Hip thrust machine, Cable, Lat pulldown, Seated row, Chest press (pec deck), Shoulder press, Rear delt fly, Assisted pull-up/dip, Bicep/Tricep station |
| **Machines - Cardio** | Treadmill, Elliptical, Stationary bike, Spin bike, Stair climber, Rowing ergometer, Ski erg, Paddle ergometer, Assault bike, Arm bike/UBE |
| **Plyo, Power & Stability** | Sandbag, Medicine ball, Weighted sled, Battle ropes, Plyo box, Stability ball, BOSU ball, Balance disc, Slider discs, Foam pad, Incline board, + fold-in Slam ball→(see note) |
| **Grip & Climbing** | Grip trainer, Rice bucket, Hangboard, Campus board, Wrist roller, Fat grips, Pinch block, Finger extension band, + fold-in Treadwall, Climbing wall |
| **Bodyweight & Portable Equipment** | Pull-up bar, Dip bars, Parallettes, Gymnastic rings, TRX, Resistance band, Ab wheel, Foam roller, Lacrosse ball, Massage gun, Jump rope, Agility ladder, Cones, Yoga mat, Nordic curl strap, Knee pad, Weighted vest |

*(Slam ball: Andy tagged "bodyweight & portable equipment"; physically a Plyo/Power item — confirm at
build. The 5 A-only items Treadwall/Climbing wall/Tricep bar/Preacher bench/Slam ball fold INTO C so
`EQUIPMENT_CATEGORIES` can be deleted.)*

---

## 7. Implementation plan (ordered slices — each ≤5 substantive files; ETL = Andy's-hands Neon apply)

1. **Slice V1 — Disciplines + bridge + modality membership.** `discipline_canon.py` (add D-006b,
   D-008a, d-SUP); `Sports_Framework_v14.xlsx` Sheet 2 (disciplines) + Sheet 3 (Endurance-Cycling
   bridge r58-r62 → 5 distinct IDs); modality membership (new disciplines + D-019 whitewater +
   gravel in both bike groups); `etl/layer0/run.py` version bump; emit `layer0_etl_v1.6.0.sql`.
   Rewrite issues **#477** + **#476** to this plan. *(Trigger #3 — cross-layer.)*
2. **Slice V2 — Modality group descriptions** (foot/climb/snow_glide/snow_travel renames). Folds into
   V1's ETL emit if same version; otherwise a 1-file vocab edit.
3. **Slice V3 — Terrain.** Rename TRN-007; add TRN-018 Off Trail / Bushwhack; add `race_eligible`
   attribute + set FALSE on TRN-014/015/016 (closes #445, #444, #340). `vocabulary.py` + emit.
4. **Slice V4 — Equipment normalization.** Gym recategorization (§6); vessel renames (SUP→Stand-up
   Paddleboard, Inflatable raft→Raft, Bike trainer→Cycling trainer); prune Surfski/Sea kayak/Rowing
   shell/Bike (generic) — update `sum_to_100.py`/`report.py`/`exercises.equipment_required` refs; fold
   5 A-only items into C.
5. **Slice V5 — Retire `EQUIPMENT_CATEGORIES` (A)** + re-source the athlete craft picker
   (`bike_types_available` / `paddle_craft_types`) from `layer0.equipment_items`. Adds TT bike, SUP,
   Raft as selectable. (D5; own slice — UI + `athlete.py` + onboarding.)
6. **Slice V6 — `layer0.craft_discipline_aliases` substrate (the original X1b.3b foundation).** Keyed
   on the normalized Vessel names → target disciplines (§4). Now unblocked.
7. **Slice V7 — `resolve_training_substitution` group-aware filter + orchestrator wire (X1b.3b).**

**Gating:** V6/V7 (X1b.3b) depend on V1 (disciplines exist) + V4 (clean vessel keys). V1→V4 each
need an Andy's-hands Neon ETL apply before the next consumes them.

---

## 8. Gut check

- This grew from "ship X1b.3b" into a 7-slice layer-0 vocabulary overhaul. That's the right call —
  X1b.3b on the old rotten vocabulary would have hard-coded the rot — but it's a multi-session arc,
  not one PR. Each slice is independently shippable + Neon-appliable.
- Biggest risk: the discipline-ID adds (D-006b/D-008a/d-SUP) ripple through bridge, membership,
  `sport_exercise_map`, and any hardcoded `D-006`/`D-008` references. V1 needs the `grep -rn` cross-layer
  audit #477's comment already scoped.
- d-SUP id: suggest a real sequential id (next free is **D-029**) rather than the placeholder `d-sup`,
  to match the D-NNN convention. Confirm at V1.
- Best argument against doing all 7 now: if you want X1b.3b's flag working fastest, V1 + V6 + V7 are
  the critical path; V2/V3/V4/V5 are quality/cleanup that can trail. But you chose foundation-first.

*End of v1.*
