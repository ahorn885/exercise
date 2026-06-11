# Vocabulary Audit v2 — Batch A Patches

**Date:** 2026-05-09
**Driver:** Layer 1 Node 2C (Equipment Mapper) design session.
**Pairs with:**
- `migrate_gear_toggles_also_satisfies.sql`
- `populate_gear_toggles_batch_a.sql`
- `populate_equipment_items_batch_a.sql`
- `cleanup_sport_exercise_map_header_residue.sql`

**etl_version:** Layer 0C tables stamp `'0C-v2.0-r3'` for new/changed rows.

---

## Section 3 — Equipment Canonical List — ADDITION

### Machines — Upper Body

Add a new row to the Machines — Upper Body table:

| Canonical | Col 7 variant(s) | Notes |
|---|---|---|
| Bench press rack | — | Fixed flat-bench station with integrated bench. Distinct from Squat rack (vertical rack/cage that requires a separate Bench item placed inside it for bench press). Common in hotel and apartment gyms. For EX229 Bench Press, interchangeable with Squat rack + Bench combo via `equipment_substitutes_structured`. |

(Insert immediately after the Cable machine row.)

---

## Section 4 — Sport-Specific Gear Readiness Toggles

### §4.1 — REMOVE Bouldering toggle (was row 5) and RENUMBER

Bouldering is not a sport in Layer 0B v19:
- Zero exercises mapped to Bouldering in `sport_exercise_map`
- Zero exercises in Exercise Master require Bouldering kit in `equipment[]`
- The toggle exists in `sport_specific_gear_toggles` but gates nothing

Toggle has no functional role in the current DB. Remove from §4.1 list and renumber the remaining entries sequentially. Final §4.1 table after this patch:

| # | Toggle (canonical token) | Replaces these former col 7 sub-tokens | Y/N gates these exercise families |
|---|---|---|---|
| 1 | Touring/AT ski setup | Touring skis, Alpine skis, Ski boots (touring), Ski poles, Climbing skins, Ski crampons, Boot buckles, Touring binding, Mountaineering harness (when used in SkiMo), Ice axe (when used in SkiMo) | SkiMo, ski-touring, alpine descent training |
| 2 | Classic XC ski setup | Classic Cross-Country Skis, Classic XC boots, Classic XC poles | Classic XC technique, XC endurance (classic) |
| 3 | Skate XC ski setup | Skate Cross-Country Skis, Skate XC boots, Skate XC poles | Skate XC technique, XC endurance (skate) |
| 4 | Climbing — roped | Climbing rope, Harness, Belay device, Carabiners, Slings, Anchor hardware, Quickdraws, Helmet (climbing) | Lead climbing, top-rope, rope-team movement |
| 5 | Rappelling / abseiling | Rappel device, Harness, Slings, Backup prusik, Helmet (climbing) | Fixed-rope descent, AR-specific abseil sections |
| 6 | Via ferrata | Via ferrata Y-lanyard, Harness, Helmet (climbing) | Via ferrata routes, fixed-cable terrain |
| 7 | Mountaineering | Crampons, Mountaineering boots, Ice axe, Mountaineering harness, Mechanical ascender, Helmet (climbing) | Mountaineering, glacier travel, technical alpine |
| 8 | Whitewater paddling setup | Spray skirt, Whitewater helmet, Whitewater PFD, Throw bag | Whitewater kayak/canoe/packraft, swiftwater drills |
| 9 | Fencing setup | Mask, Jacket, Foil/épée/sabre, Glove, Lamé (electric) | Fencing technical work, modern pent fencing leg |
| 10 | Shooting setup | Laser pistol, Air pistol, Rifle (subtype sub-question if needed), Targets | Modern pent shooting leg, biathlon shooting |
| 11 | Snowshoeing setup *(retained as note only)* | (Snowshoes already top-level singleton — no rollup needed) | — |

10 active toggles + 1 note (toggle 11 Snowshoeing remains a documentation note; Snowshoes singleton handling unchanged).

Old → new number mapping (for any cross-references in other docs):

| Old # | Toggle | New # |
|---|---|---|
| 1 | Touring/AT ski setup | 1 |
| 2 | Classic XC ski setup | 2 |
| 3 | Skate XC ski setup | 3 |
| 4 | Climbing — roped | 4 |
| 5 | Bouldering | **removed** |
| 6 | Rappelling / abseiling | 5 |
| 7 | Via ferrata | 6 |
| 8 | Mountaineering | 7 |
| 9 | Whitewater paddling setup | 8 |
| 10 | Fencing setup | 9 |
| 11 | Shooting setup | 10 |
| 12 | Snowshoeing setup (note) | 11 |

**No DB schema impact.** `sport_specific_gear_toggles` is keyed by `toggle_name`, not numeric position. Renumbering is documentation-only.

### §4.1 — NEW field on every toggle row: `also_satisfies`

Schema migration adds `also_satisfies TEXT[]` column to `layer0.sport_specific_gear_toggles`. Encodes one-way kit-implication rules: an athlete with toggle A on automatically passes exercises gated on each toggle in A's `also_satisfies` list.

Population in Batch A:

| Toggle | also_satisfies |
|---|---|
| Climbing — roped | `[Rappelling / abseiling]` |
| (all others) | NULL |

### §4.2 — Rewrite the Climbing/Rappelling overlap paragraph

**Old text (replace):**

> "Climbing — roped and Rappelling share most kit. They're separate toggles because some athletes (especially AR-only) only abseil and never lead. An athlete with full roped setup automatically passes rappelling-gated exercises; the matching engine treats Climbing — roped = true as also satisfying Rappelling = true."

**New text:**

> "Climbing — roped and Rappelling — abseiling share most kit. They remain separate toggles because some athletes only abseil and never lead. The implication is encoded in `sport_specific_gear_toggles.also_satisfies` — Climbing — roped's `also_satisfies` includes `Rappelling / abseiling`, so 2C's matcher passes any Rappelling-gated exercise for athletes with Climbing — roped = TRUE. The implication is one-way: a rappelling-only athlete may lack a belay device and lead-climb experience, so Rappelling does NOT imply Climbing — roped. Mountaineering, Touring/AT ski setup, and other toggles do NOT auto-satisfy each other; their `also_satisfies` is NULL."

---

## Companion deliverable (in this batch)

- **`ETL_Parser_Fix_Header_Offset.md`** — over-there ETL repo instruction. Permanent fix for the AR_Exercise_Database extractor row-offset bug that produced the "Sport" placeholder. Pairs with `cleanup_sport_exercise_map_header_residue.sql` (one-shot DB cleanup) — once the parser fix lands and the next ETL re-run completes, the cleanup script becomes a permanent no-op.

## Out of scope for this patch (handled in later batches)

- **Exercise DB curation (10 rows: bike/load primary-substitute splits).** Batch C, after Batch B technique-focus migration settles.

- **Technique-focus migration (drop 41 rows + create `discipline_technique_foci`).** Batch B.
