# Handoff — Equipment Column Cleanup Pass 1 complete; resuming ETL run

## Architectural principle (locked, load-bearing)

**equipment[] tokens in source data are canonical gear toggles meaningful for plan generation only.** Not sub-components, not venues that are universally available, not athlete-choice clothing/configuration, not technical-skill prerequisites for sports we don't model. This needs to be documented in the data spec to prevent drift.

Implications applied:
- Universal venues (Floor, Wall, Track, Open Space, Outdoor) → drop
- Sport-skill venues for sports we don't model — fencing, shooting (Marked Floor, Fencing Strip, Shooting Range) → drop
- Sub-components of canonical kits (Belay Device, Erg Handle, Canoe Seat, Sculling Blade, Spray Skirt, Boot Buckles) → drop or aggregate
- Athlete-choice clothing/gear (Wetsuit, Running Shoes, Headlamp, Soft Flask, Knee Pad, swim cap/goggles) → drop
- Configuration tokens (Loaded Touring Bike, Bikepacking Setup, Inclined Treadmill, Loaded Backpack qualifier) → drop or normalize
- Universal AR nav gear (Compass, GPS, Topographic Map) → drop
- Consumables (Chews, Cups, Gels) → drop

## What Pass 1 produced

**File: `AR_Exercise_Database_v18.xlsx`** — cleaned source xlsx, identical to v17 except the Equipment column has been transformed.

Stats:
- 167/245 exercise rows had their Equipment column changed
- Net token reduction: 456 → 330 raw token instances (126 dropped/aggregated)
- Unique vocabulary: ~245 distinct tokens before → 105 unique tokens after
- 42 exercises now have empty Equipment columns (mostly was-Bodyweight rows; correct semantics — empty means "no equipment required")

Aggregations introduced (NEW canonical entries needing vocab DB):
- **Climbing gear** — aggregates Belay Device, Rope, Sling, Slings, Fixed Rope, Harness, Mountaineering Harness, Carabiners, Anchor Hardware, Anchor Point, Mechanical Ascender, Via Ferrata Y-Lanyard
- **XC ski kit** — aggregates Cross-Country Skis, Classic Cross-Country Skis, Skate Cross-Country Skis, Ski Poles on Flat Ground
- **Touring ski kit** — aggregates Ski Boots, Touring Skis, Touring Skis with Climbing Skins, Climbing Skins, Ski Crampons, Alpine Skis
- **SUP** — normalizes Stand-Up Paddleboard
- **TT Bike** — already a recognizable canonical, kept as-is

Other normalizations: Cable Machine variants → "Cable machine"; Bike trainer / Trainer / Mountain Bike / Road Bike / Climbing Rope case fixes; Resistance band variants (Band, Rubber Band, Resistance Band) → "Resistance band"; Weighted vest variants (Vest, Weight Vest) → "Weighted vest"; Plyo box variants (Box, Plyo Box) → "Plyo box".

## Flagged drops — review needed (the script flagged 2 rows)

- **EX026 (Seated Calf Raise)** — was "Machine, Barbell on Thighs", now "Barbell". Acceptable but `Calf raise machine` would be a better canonical to add if seated calf raises are common enough to warrant.
- **EX027 (Tibialis Raise)** — was "Wall, Machine, Band", now "Resistance band". Acceptable.

## Pass 2 vocab decisions still pending — the 7 unclassified tokens

These tokens currently pass through to v18 unchanged. They're not garbage but need conscious vocab decisions before being added to `layer0.equipment_items`:

| Count | Token | Question |
|---|---|---|
| 9 | Poles | Trekking? Ski? Aggregate to one of the ski kits, or keep as separate canonical "Trekking Poles"? Note: "Trekking Poles" already canonical with 4 separate occurrences |
| 2 | Crampons | Separate canonical for ice climbing? Or aggregate to a "Mountaineering kit"? |
| 2 | Ice Axe | Same question — separate or part of "Mountaineering kit"? |
| 2 | Mountaineering Boots | Same — separate or kit aggregate? |
| 2 | Inflatable Raft | Aggregate to Packraft (functionally similar for AR)? Or keep as separate canonical? |
| 1 | Pinch Block | Grip training equipment — real canonical, or rare enough to drop? |
| 1 | Wrist Roller | Grip training — real canonical, or rare enough to drop? |

Open architectural question Andy flagged earlier but hasn't resolved: is **"Climbing Wall"** a venue toggle (athlete has access to a climbing gym) or part of "Climbing gear"? Currently passes through as-is (1 occurrence in v18).

## Architectural finding from this session

**Source xlsx encodes equipment disjunction via " or " between tokens** ("Road Bike or Trainer", "TT Bike or Road Bike on Trainer", "Classic or Skate Cross-Country Skis"). This is informal; the schema for `equipment_required[]` is currently a flat array (AND semantics). Decisions made:

- For Pass 1 cleanup, each compound was encoded as an explicit `SPLITS` rule (decompose to all named options as separate tokens — over-restrictive, but preserves data)
- True AND-OR encoding for primary `equipment[]` (mirroring `equipment_substitutes_structured`) is a Pass 2 / future architectural question

The full list of 17 compound " or " tokens encountered is in `clean_equipment_column.py` SPLITS dict.

## Where the prior ETL run left off

Steps 1-2 ran, step 3 patched (`vocabulary_transforms.py` J patch applied — 127→133 tests passing), step 4 (full ETL re-run on terrain-aware vocab) was paused for this cleanup. Now that v18 exists:

1. **Replace v17 with v18 in `etl/sources/`**, update parser entry point if it pins a filename
2. **Resume step 4** — run ETL against v18
3. **Add new canonical entries to `layer0.equipment_items` via SQL patch K2**: Climbing gear, XC ski kit, Touring ski kit, SUP, TT Bike, Cable machine, Plyo box, Weighted vest, Resistance band (if not present), Bike trainer (if not present). Equipment items uses `(canonical_name, etl_version)` composite key — patch K1 already corrected this.
4. **Step 5** lands afterwards (`populate_substitutes_structured.py` with runtime canonical vocab check).

## Files in /mnt/user-data/outputs/

| File | Purpose |
|---|---|
| `AR_Exercise_Database_v18.xlsx` | **The new source xlsx** — replaces v17 |
| `clean_equipment_column.py` | The cleanup script (idempotent — safe to re-run on v18) |
| `cleanup_diff_log.txt` | Per-exercise diff showing every change made; Andy reviews before commit |
| `parse_substitutes.py`, `parsed_substitutes.json` | Layer 1 Node 2C parser + 511 parsed entries (locked from prior session) |
| `populate_substitutes_structured.py` | DB populator with vocab validation (locked) |
| `populate_equipment_items_K_additions.sql` | K1 patch — adds initial new vocab entries (locked) |
| `migrate_exercises_*.sql` | Schema migrations for terrain[] and substitutes_structured (locked) |
| `vocab_patch_K_new_entries.md` | K vocab decision doc (locked) |
| `vocabulary_transforms_J_patch.md` | J patch doc (locked, applied) |
| `ETL_Spec_v3_Corrections_2ABC_v2.md` | Layer 1 Nodes 2A/2B/2C contracts with AND-OR semantics (locked) |
| `HANDOFF_equipment_cleanup_pass1.md` | This doc |

## Outstanding TODOs from prior session memory

- **Layer 0A and 0B schema specs** — design before parallel content-generation chat continues. Immediate next architectural task after ETL completes.
- **Layer 1 sequential prompt design** — begins after Layer 0 spec is locked.
- **`AR_Merged_Database.xlsx` updates** — Week 1-2 actuals still pending batch update; file accessible via direct upload only.
- **EX193 (Shooting) deletion** — track for v18 DB iteration. With Air Pistol/Laser Pistol now in DROP_TOKENS, the equipment column for EX193/EX194 is empty in v18, but the rows themselves are still present and probably should be removed from source xlsx entirely (we don't model shooting as a sport).
- **Document the canonical gear toggle principle** in the data spec — this session's main architectural output.

## Gut check on Pass 1

**Risks:** New canonical entries (Climbing gear, XC ski kit, Touring ski kit, SUP, TT Bike, Plyo box, Weighted vest, Cable machine) are not yet in `layer0.equipment_items`. ETL run against v18 will produce parsed exercise rows that reference these names; if the FK or vocab check trips, the run halts. Pre-add via patch K2 SQL before running ETL.

**What might be missing:** Pass 1 didn't make Mountaineering/Crampons/Ice Axe decisions — there are 6 exercises (~2.5%) that will pass-through to v18 with non-canonical equipment tokens and fail Tier 1 matching in 2C until Pass 2 lands. Acceptable as a known transient state if Pass 2 is on the roadmap.

**Best argument against this approach:** Cleaning the source xlsx (rather than handling all transformations in ETL transforms) means the source is now the audited spec and any future re-export from upstream content generation must follow the same canonical conventions. If the parallel content-generation chat doesn't know about the cleanup rules, it can re-introduce garbage. Mitigation: the canonical gear toggle principle and rule lists in `clean_equipment_column.py` need to be communicated to whatever process generates exercise database content.

**Assumption flag:** I assumed `Packraft` is already a canonical equipment entry (used for "Loaded Packraft" → "Packraft" normalization). If it's not, the ETL run will trip on it. Verify in equipment_items before running.
