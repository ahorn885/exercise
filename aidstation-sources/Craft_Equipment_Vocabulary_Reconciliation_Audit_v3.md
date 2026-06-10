# Vocabulary Reconciliation — v3 (single normalized matrix)

**Date:** 2026-06-08 · **Branch:** `claude/v5-layer2c-handoff-988dgv`
**Supersedes:** Audit v1 + v2. One normalized table, one column schema for every row.

## How to read this (column rules)

Every row uses the **same** columns. Cells contain the **actual full value**, or:
- **`N/A`** = this column does not apply to this row's domain (e.g. a discipline has no
  "v1 picker slug"; a gym machine has no "modality group").
- **`missing`** = this column *applies* to this row but the value is **absent there** — a real gap
  or divergence to reconcile.

| Column | Meaning |
|---|---|
| **Domain** | discipline / craft-vessel / equipment / modality-group / terrain |
| **Value** | the full human name (authoritative/canonical form) |
| **ID** | `D-NNN` / `TRN-NNN` / `group_id`; `N/A` for equipment (catalog is name-keyed) |
| **layer0 live** | how it appears in the live `layer0.*` table, or `missing` |
| **v1 EQUIPMENT_CATEGORIES** | `slug "Label"` from `init_db.py`, or `N/A`, or `missing` |
| **v1 athlete enum** | value + which enum (`PADDLE_CRAFT_TYPES` / `bike_types_available`), or `N/A`, or `missing` |
| **Committed elsewhere** | firm/proposed change from an issue or spec (with ref), or `none` |
| **Mapping** | discipline→modality group; craft→discipline(s); else `N/A` |
| **Status** | `live` / `committed-pending-ETL` / `prune-candidate` / `open-question` / `removed-via-canon` |

**Sources mined for this table:** live `layer0.*` (v1.5.0 ETL), all 100 open + closed GitHub issues,
and all `aidstation-sources/` specs + handoffs. If a decision exists only in conversation (not written
in an issue or doc), it is **not** here — point me at it and I'll fold it in.

---

## A. Disciplines

| Domain | Value | ID | layer0 live | v1 EQUIPMENT_CATEGORIES | v1 athlete enum | Committed elsewhere | Mapping (group) | Status |
|---|---|---|---|---|---|---|---|---|
| discipline | Trail Running | D-001 | Trail Running | N/A | N/A | none | foot | live |
| discipline | Road Running | D-002 | Road Running | N/A | N/A | none | foot | live |
| discipline | Trekking | D-003 | Trekking | N/A | N/A | absorbed D-015 Orienteering (canon) | foot | live |
| discipline | Swimming | D-004 | Swimming | N/A | N/A | absorbed D-005, D-016 (canon) | swim_openwater | live |
| discipline | Road Cycling | D-006 | Road Cycling | N/A | N/A | split → D-006a/b/c (#477, firm) | bike_pavement | committed-pending-ETL |
| discipline | Time-Trial Cycling | D-007 | Time-Trial Cycling | N/A | N/A | REMOVE → folds into D-006c (#476/#477, firm) | bike_pavement | committed-pending-ETL |
| discipline | Mountain Biking | D-008 | Mountain Biking | N/A | N/A | split → D-008a/b (#477, firm) | bike_offroad | committed-pending-ETL |
| discipline | Packrafting | D-009 | Packrafting | N/A | N/A | none | paddle_flatwater + paddle_whitewater | live |
| discipline | Kayaking | D-010 | Kayaking | N/A | N/A | D-010a/b flatwater/whitewater split (⚠️unverified — no issue/doc) | paddle_flatwater + paddle_whitewater | open-question |
| discipline | Canoeing | D-011 | Canoeing | N/A | N/A | none | paddle_flatwater | live |
| discipline | Rock Climbing | D-012 | Rock Climbing | N/A | N/A | none | climb | live |
| discipline | Abseiling | D-013 | Abseiling | N/A | N/A | none | climb | live |
| discipline | Via Ferrata | D-014 | Via Ferrata | N/A | N/A | none | climb | live |
| discipline | Snowshoeing | D-017 | Snowshoeing | N/A | N/A | none | snow_travel | live |
| discipline | Mountaineering | D-018 | Mountaineering | N/A | N/A | TRN-005-vs-TRN-012 routing (open, Synthesis_Design_v2 §5.1) | snow_travel | open-question |
| discipline | Paddle Rafting | D-019 | Paddle Rafting | N/A | N/A | none | paddle_flatwater | live |
| discipline | Uphill Skinning | D-021 | Uphill Skinning | N/A | N/A | none | snow_glide | live |
| discipline | Alpine Descent | D-022 | Alpine Descent | N/A | N/A | none | snow_glide | live |
| discipline | Mountain Running | D-024 | Mountain Running | N/A | N/A | none | foot | live |
| discipline | Obstacle Course Racing | D-027 | Obstacle Course Racing | N/A | N/A | none | foot | live |
| discipline | Cross-Country Skiing | D-028 | Cross-Country Skiing | N/A | N/A | none | snow_glide | live |
| discipline | Road Cycling (Long Distance) | D-006a | missing | N/A | N/A | NEW (#477, firm) | bike_pavement | committed-pending-ETL |
| discipline | Road Cycling (Gravel) | D-006b | missing | N/A | N/A | NEW (#477, firm) | bike_offroad | committed-pending-ETL |
| discipline | Time Trial Cycling | D-006c | missing | N/A | N/A | NEW (#477, firm; absorbs D-007) | bike_pavement | committed-pending-ETL |
| discipline | Mountain Biking (XC) | D-008a | missing | N/A | N/A | NEW (#477, firm) | bike_offroad | committed-pending-ETL |
| discipline | Mountain Biking (Enduro) | D-008b | missing | N/A | N/A | NEW (#477, firm) | bike_offroad | committed-pending-ETL |
| discipline | Orienteering | D-015 | missing (merged → D-003) | N/A | N/A | removed/merged (canon) | foot (via D-003) | removed-via-canon |
| discipline | Pool Sprint Swimming | D-005 | missing (merged → D-004) | N/A | N/A | removed/merged (canon) | swim (via D-004) | removed-via-canon |
| discipline | Generic Swimming | D-016 | missing (merged → D-004) | N/A | N/A | removed/merged (canon) | swim (via D-004) | removed-via-canon |

*(Per-sport removed via `discipline_canon`/`sport_canon` and still physically in the xlsx (#320): Fencing,
Modern Pentathlon, Biathlon, Hiking — status `removed-via-canon`; not enumerated as rows here.)*

---

## B. Modality groups (live, firm — reference)

| Domain | Value | ID | layer0 live | v1 EQUIPMENT_CATEGORIES | v1 athlete enum | Committed elsewhere | Mapping | Status |
|---|---|---|---|---|---|---|---|---|
| modality-group | Flatwater paddle | paddle_flatwater | Flatwater paddle | N/A | N/A | none | D-009/010/011/019 | live |
| modality-group | Whitewater paddle | paddle_whitewater | Whitewater paddle | N/A | N/A | none | D-009/010 | live |
| modality-group | Foot (run / hike / nav) | foot | Foot (run / hike / nav) | N/A | N/A | none | D-001/002/003/024/027 | live |
| modality-group | Bike on pavement | bike_pavement | Bike on pavement | N/A | N/A | none | D-006/007 (→D-006a/c) | live |
| modality-group | Bike off-road | bike_offroad | Bike off-road | N/A | N/A | none | D-008 (→D-006b/008a/008b) | live |
| modality-group | Snow travel (foot) | snow_travel | Snow travel (foot) | N/A | N/A | none | D-017/018 | live |
| modality-group | Snow travel (gliding) | snow_glide | Snow travel (gliding) | N/A | N/A | none | D-021/022/028 | live |
| modality-group | Climbing (rope-protected) | climb | Climbing (rope-protected) | N/A | N/A | none | D-012/013/014 | live |
| modality-group | Open-water swim | swim_openwater | Open-water swim | N/A | N/A | none | D-004 | live |

---

## C. Craft vessels — cycling

| Domain | Value | ID | layer0 live | v1 EQUIPMENT_CATEGORIES | v1 athlete enum | Committed elsewhere | Mapping (craft→discipline) | Status |
|---|---|---|---|---|---|---|---|---|
| craft-vessel | Road bike | N/A | Road bike | road_bike "Road Bike" | road_bike (bike_types_available) | none | D-006 → D-006a | live |
| craft-vessel | Mountain bike | N/A | Mountain bike | mountain_bike "Mountain Bike (MTB)" | mountain_bike (bike_types_available) | none | D-008 → D-008a + D-008b | live |
| craft-vessel | Gravel bike | N/A | Gravel bike | gravel_bike "Gravel Bike" | gravel_bike (bike_types_available) | none | Road + XC (Andy: D-006a + D-008a) | live |
| craft-vessel | TT / triathlon bike | N/A | TT / triathlon bike | missing | missing | maps to D-006c after #477 | D-006c | live (catalog only) |
| craft-vessel | Bike (generic) | N/A | Bike (generic) | missing | missing | none | D-006 (ambiguous) | prune-candidate |
| craft-vessel | Cycling trainer (indoor) | N/A | Bike trainer | cycling_trainer "Cycling Trainer / Smart Trainer" | cycling_trainer (bike_types_available) | none | N/A (indoor, not a craft) | live (name mismatch: "Bike trainer" vs "Cycling Trainer") |

---

## D. Craft vessels — paddle

| Domain | Value | ID | layer0 live | v1 EQUIPMENT_CATEGORIES | v1 athlete enum | Committed elsewhere | Mapping (craft→discipline) | Status |
|---|---|---|---|---|---|---|---|---|
| craft-vessel | Kayak | N/A | Kayak | kayak "Kayak" | kayak (PADDLE_CRAFT_TYPES) | none | D-010 | live |
| craft-vessel | Canoe | N/A | Canoe | canoe "Canoe" | canoe (PADDLE_CRAFT_TYPES) | none | D-011 | live |
| craft-vessel | Packraft | N/A | Packraft | packraft "Packraft" | packraft (PADDLE_CRAFT_TYPES) | none | D-009 | live |
| craft-vessel | Surfski | N/A | missing | missing | surfski (PADDLE_CRAFT_TYPES) | none | no discipline | prune-candidate (Andy: never tracked) |
| craft-vessel | Sea kayak | N/A | Sea kayak | missing | missing | none | D-010 | prune-candidate (Andy: never tracked; ETL readers: sum_to_100, report.py) |
| craft-vessel | SUP | N/A | SUP | missing | missing | none | no discipline | prune-candidate (orphan) |
| craft-vessel | Inflatable raft | N/A | Inflatable raft | missing | missing | none | D-019 | prune-candidate (Andy: never tracked) |
| craft-vessel | Rowing shell | N/A | Rowing shell | missing | missing | none | no discipline | prune-candidate (orphan) |

---

## E. Terrain types

| Domain | Value | ID | layer0 live | v1 EQUIPMENT_CATEGORIES | v1 athlete enum | Committed elsewhere | Mapping | Status |
|---|---|---|---|---|---|---|---|---|
| terrain | Road / Paved | TRN-001 | Road / Paved | N/A | N/A | none | N/A | live |
| terrain | Groomed Trail | TRN-002 | Groomed Trail | N/A | N/A | none | N/A | live |
| terrain | Technical Trail | TRN-003 | Technical Trail | N/A | N/A | none | N/A | live |
| terrain | Hill / Rolling | TRN-004 | Hill / Rolling | N/A | N/A | none | N/A | live |
| terrain | Mountain / Alpine | TRN-005 | Mountain / Alpine | N/A | N/A | none | N/A | live |
| terrain | Fell / Moorland | TRN-006 | Fell / Moorland | N/A | N/A | none | N/A | live |
| terrain | Technical Rock | TRN-007 | Technical Rock | N/A | N/A | RENAME → "Technical Rock/Scree" (Synthesis_Design_v2 §5.1, firm); relabel UI (#444, open) | N/A | committed-pending-ETL |
| terrain | Pool | TRN-008 | Pool | N/A | N/A | none | N/A | live |
| terrain | Flat Water | TRN-009 | Flat Water | N/A | N/A | none | N/A | live |
| terrain | Ocean / Tidal | TRN-010 | Ocean / Tidal | N/A | N/A | none | N/A | live |
| terrain | Whitewater | TRN-011 | Whitewater | N/A | N/A | none | N/A | live |
| terrain | Snow / Winter Alpine | TRN-012 | Snow / Winter Alpine | N/A | N/A | none | N/A | live |
| terrain | Rock Wall (Outdoor) | TRN-013 | Rock Wall (Outdoor) | N/A | N/A | none | N/A | live |
| terrain | Climbing Gym | TRN-014 | Climbing Gym | N/A | N/A | race_eligible=FALSE proposal (#445, open) | N/A | open-question |
| terrain | Pump Track / Skills Course | TRN-015 | Pump Track / Skills Course | N/A | N/A | race_eligible=FALSE proposal (#445, open) | N/A | open-question |
| terrain | Indoor / Gym | TRN-016 | Indoor / Gym | N/A | N/A | race_eligible=FALSE proposal (#445, open) | N/A | open-question |
| terrain | Moving Water | TRN-017 | Moving Water | N/A | N/A | none | N/A | live |
| terrain | Gravel | TRN-020 | Gravel | N/A | N/A | none | N/A | live |
| terrain | Off-Trail / Bush (trackless) | TBD (NOT TRN-017 — taken) | missing | N/A | N/A | NEW, firm (Synthesis_Design_v2 §5.1; race_eligible=TRUE per #340) | N/A | committed-pending-ETL |

**⚠️ ID conflict to resolve:** CARRY_FORWARD + the 2c handoff call the off-trail terrain "TRN-017",
but TRN-017 is already **Moving Water** live. The new off-trail row needs a free id (TRN-018/019/021).

---

## F. General equipment (strength / cardio) — `EQUIPMENT_CATEGORIES` (A) vs `layer0.equipment_items` (C)

This section exists for the **D5 decision** (retire `EQUIPMENT_CATEGORIES` entirely). It shows whether
every A item is covered by C. v1 athlete-enum column is `N/A` for all (these aren't craft enums).
*(Confidence: name-level semantic match; a few are best-effort — flagged.)*

| Domain | Value (C canonical) | layer0 live (C) | v1 EQUIPMENT_CATEGORIES (A) | Status |
|---|---|---|---|---|
| equipment | Barbell | Barbell | barbell "Barbell (Olympic)" | live (both) |
| equipment | EZ curl bar | EZ curl bar | ez_bar "EZ Curl Bar" | live (both) |
| equipment | Trap bar | Trap bar | hex_bar "Hex / Trap Bar" | live (both) |
| equipment | Dumbbell | Dumbbell | dumbbells "Dumbbells" | live (both) |
| equipment | Kettlebell | Kettlebell | kettlebell "Kettlebell" | live (both) |
| equipment | Sandbag | Sandbag | sandbag "Sandbag" | live (both) |
| equipment | Medicine ball | Medicine ball | med_ball "Med Ball" | live (both) |
| equipment | Squat rack | Squat rack | squat_rack "Squat Rack / Power Cage" | live (both) |
| equipment | Smith machine | Smith machine | smith_machine "Smith Machine" | live (both) |
| equipment | Bench | Bench | bench_flat "Flat Bench" + bench_adjustable "Adjustable / Incline Bench" | live (C merges two A rows) |
| equipment | Glute ham developer (GHD) | Glute ham developer (GHD) | ghd "GHD / Hyperextension Bench" | live (both) |
| equipment | Pull-up bar | Pull-up bar | pull_up_bar "Pull-Up Bar" | live (both) |
| equipment | Dip bars | Dip bars | dip_bars "Dip Bars / Parallel Bars" | live (both) |
| equipment | Gymnastic rings | Gymnastic rings | rings "Gymnastic Rings" | live (both) |
| equipment | Leg press machine | Leg press machine | leg_press "Leg Press" | live (both) |
| equipment | Hack squat machine | Hack squat machine | hack_squat "Hack Squat Machine" | live (both) |
| equipment | Leg extension machine | Leg extension machine | leg_extension "Leg Extension Machine" | live (both) |
| equipment | Leg curl machine | Leg curl machine | leg_curl "Leg Curl Machine" | live (both) |
| equipment | Standing calf raise machine | Standing calf raise machine | calf_raise_machine "Calf Raise Machine" | live (both) |
| equipment | Cable machine | Cable machine | cable_machine "Cable Machine / Crossover" | live (both) |
| equipment | Lat pulldown machine | Lat pulldown machine | lat_pulldown "Lat Pulldown Machine" | live (both) |
| equipment | Seated row machine | Seated row machine | seated_row_machine "Seated Row Machine" | live (both) |
| equipment | Chest press machine | Chest press machine | pec_deck "Pec Deck / Chest Fly Machine" | live (approx — pec deck≈chest fly) |
| equipment | Shoulder press machine | Shoulder press machine | shoulder_press_machine "Shoulder Press Machine" | live (both) |
| equipment | Assisted pull-up / dip machine | Assisted pull-up / dip machine | assisted_pullup "Assisted Pull-Up / Dip Machine" | live (both) |
| equipment | Treadmill | Treadmill | treadmill "Treadmill" | live (both) |
| equipment | Elliptical | Elliptical | elliptical "Elliptical / Cross Trainer" | live (both) |
| equipment | Stationary bike | Stationary bike | stationary_bike "Stationary Bike (Upright)" + recumbent_bike "Recumbent Bike" | live (C merges) |
| equipment | Spin bike | Spin bike | spin_bike "Spin Bike / Peloton" | live (both) |
| equipment | Stair climber | Stair climber | stair_climber "Stair Climber / StepMill" | live (both) |
| equipment | Rowing ergometer | Rowing ergometer | rowing_erg "Rowing Erg (Concept2)" | live (both) |
| equipment | Paddle ergometer | Paddle ergometer | kayak_erg "Kayak Ergometer" | live (name diff) |
| equipment | Assault bike | Assault bike | air_bike "Air Bike / Assault Bike" | live (both) |
| equipment | Ski erg | Ski erg | ski_erg "SkiErg" | live (both) |
| equipment | Weighted sled | Weighted sled | sled "Sled" | live (both) |
| equipment | Battle ropes | Battle ropes | battle_ropes "Battle Ropes" | live (both) |
| equipment | Plyo box | Plyo box | plyo_box "Plyo Box" | live (both) |
| equipment | Resistance band | Resistance band | resistance_bands "Resistance Bands" | live (both) |
| equipment | TRX / suspension trainer | TRX / suspension trainer | trx "TRX / Suspension Trainer" | live (both) |
| equipment | Weighted vest | Weighted vest | weighted_vest "Weighted Vest" | live (both) |
| equipment | Jump rope | Jump rope | jump_rope "Jump Rope" | live (both) |
| equipment | Stability ball | Stability ball | stability_ball "Stability Ball" | live (both) |
| equipment | BOSU ball | BOSU ball | bosu "BOSU Ball" | live (both) |
| equipment | Ab wheel | Ab wheel | ab_wheel "Ab Wheel" | live (both) |
| equipment | Foam roller | Foam roller | foam_roller "Foam Roller" | live (both) |
| equipment | Grip trainer | Grip trainer | grip_trainer "Grip Trainer (squeeze)" | live (both) |
| equipment | Rice bucket | Rice bucket | rice_bucket "Rice Bucket" | live (both) |
| equipment | Lacrosse ball | Lacrosse ball | lacrosse_ball "Lacrosse Ball / Massage Ball" | live (both) |
| equipment | Hangboard | Hangboard | hangboard "Hangboard" | live (both) |
| equipment | (none) | missing | treadwall "Treadwall" | A-only — C has no Treadwall |
| equipment | (none) | missing | climbing_wall "Climbing Wall / Bouldering" | A-only — C has TRN-014 Climbing Gym terrain instead |
| equipment | (none) | missing | tricep_bar "Tricep Bar (W-bar)" | A-only — not in C |
| equipment | (none) | missing | preacher_bench "Preacher Curl Bench" | A-only — not in C |
| equipment | (none) | missing | slam_ball "Slam Ball" | A-only — not in C |

**A-only items (block a clean `EQUIPMENT_CATEGORIES` deletion until folded into C):** Treadwall,
Climbing Wall, Tricep Bar (W-bar), Preacher Curl Bench, Slam Ball. *(C additionally has ~60 items A
lacks — grip/forearm, stability, recovery, sport-specific running/winter/swimming, navigation,
assumed-universal — i.e. C is the far richer catalog.)*

---

## G. Decisions owed (Andy)

1. **D1** — Source of truth = `layer0.equipment_items` (C)? (rec: yes)
2. **D2** — Prune list per row in §C/§D (surfski, Sea kayak, SUP, Inflatable raft, Rowing shell,
   Bike (generic)): keep / prune / fold. (Trigger #2; mind ETL readers + `exercises.equipment_required`.)
3. **D3** — #477 cycling split (D-006a/b/c, D-008a/b, remove D-007) ETL ordering — prerequisite for
   X1b.3b's craft map. Global IDs or Endurance-Cycling-bridge-only?
4. **D4** — D-010a/b kayak split: confirm decided (then ETL) or drop (keep single D-010)?
5. **D5** — Retire `EQUIPMENT_CATEGORIES` (A): fold the 5 A-only items (§F) into C first, then delete A
   + re-source the athlete picker from C (own slice).
6. **D6** — Off-trail terrain new id (TRN-017 is taken by Moving Water) + TRN-007 rename — bundle as a
   terrain ETL micro-slice?
7. **D7** — D-018 Mountaineering routing (TRN-005 vs TRN-012) — open semantics call.

*End of v3.*
