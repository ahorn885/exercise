# Craft / Equipment / Discipline Vocabulary Reconciliation — v2 (matrix)

**Date:** 2026-06-08
**Branch:** `claude/v5-layer2c-handoff-988dgv`
**Supersedes:** `Craft_Equipment_Vocabulary_Reconciliation_Audit_v1.md` (v1 read only the live tables and
wrongly concluded "XC cycling does not exist" — it is a **committed** decision in #477, see §0).

**Purpose:** one place to see every craft / equipment / discipline / modality value, **which source
each lives in**, and where they duplicate or diverge — so Andy can pick the **authoritative source
per row** and we collapse to a single source of truth. Format: columns = sources, rows = values.
Mark the **✓Auth** column. No code changed.

---

## 0. Correction to v1 — the committed (issue-decided) vocabulary

Mined from GitHub issues (all open + closed). These are **decided but not yet in the live canon**:

- **#477 (FIRM, Andy 2026-06-07 — "Option 2: split discipline IDs into format-specific IDs"):**
  D-006 → **D-006a** Road LD / **D-006b** Gravel / **D-006c** TT; D-008 → **D-008a** MTB-XC /
  **D-008b** Enduro. Names "pending canon review"; the split itself is committed. Deferred to after
  the X1 series + modality system land.
- **#476 (FIRM, subsumed by #477):** **D-007 removed** as a discipline ID; folds into **D-006c**.
- **D-010a / D-010b kayak flatwater/whitewater split** — cited in #477's comment as established
  precedent "from earlier Layer 0 vocab notes," but **no tracking issue exists**; provenance is
  design docs/PRs only. Marked ⚠️unverified below — Andy to confirm whether this is decided.

Source legend (columns used in the matrices):

| Col | Source | Form | Role |
|---|---|---|---|
| **A** | `EQUIPMENT_CATEGORIES` (`init_db.py:2132`) | snake_case slug | v1 app picker |
| **B** | athlete enums `PADDLE_CRAFT_TYPES` / `bike_types_available` (`athlete.py`) | snake_case | v1 profile write-path |
| **C** | `layer0.equipment_items` (live, 121 rows) | Title-case canonical | LLM-pipeline gear catalog |
| **D** | `discipline_canon.py` == `layer0.disciplines` (live) | D-NNN id + name | live discipline canon |
| **E** | Committed-in-issues (not yet ETL'd) | D-NNNx id | #477 / #476 |
| **G** | `layer0.modality_groups` membership (live) | group_id | modality grouping |

---

## 1. Disciplines — full canon (live D vs committed E)

| ID | D — live canon name | E — committed change (#) | G — modality group (live) | ✓Auth |
|---|---|---|---|---|
| D-001 | Trail Running | — | foot | |
| D-002 | Road Running | — | foot | |
| D-003 | Trekking *(absorbed D-015 Orienteering)* | — | foot | |
| D-004 | Swimming *(absorbed D-005, D-016)* | — | swim_openwater | |
| **D-006** | Road Cycling | **split → D-006a/b/c (#477)** | bike_pavement | |
| **D-007** | Time-Trial Cycling | **REMOVE → D-006c (#476/#477)** | bike_pavement | |
| **D-008** | Mountain Biking | **split → D-008a/b (#477)** | bike_offroad | |
| D-009 | Packrafting | — | paddle_flatwater + paddle_whitewater | |
| D-010 | Kayaking | ⚠️D-010a/b split (unverified) | paddle_flatwater + paddle_whitewater | |
| D-011 | Canoeing | — | paddle_flatwater | |
| D-012 | Rock Climbing | — | climb | |
| D-013 | Abseiling | — | climb | |
| D-014 | Via Ferrata | — | climb | |
| D-017 | Snowshoeing | — | snow_travel | |
| D-018 | Mountaineering | — | snow_travel | |
| D-019 | Paddle Rafting | — | paddle_flatwater | |
| D-021 | Uphill Skinning | — | snow_glide | |
| D-022 | Alpine Descent | — | snow_glide | |
| D-024 | Mountain Running | — | foot | |
| D-027 | Obstacle Course Racing | — | foot | |
| D-028 | Cross-Country Skiing | — | snow_glide | |

**Committed new IDs (E only — do not exist live yet):**

| New ID | E — name (#477) | G — committed group (#477) | Replaces | ✓Auth |
|---|---|---|---|---|
| D-006a | Road Cycling (Long Distance) | bike_pavement | D-006 (Endurance Cycling bridge r58) | |
| D-006b | Road Cycling (Gravel) | bike_offroad | r59 | |
| D-006c | Time Trial Cycling | bike_pavement | r60 + old D-007 | |
| D-008a | Mountain Biking (XC) | bike_offroad | r61 | |
| D-008b | Mountain Biking (Enduro) | bike_offroad | r62 | |

*Note: the #477 split applies only to the `Long Distance / Endurance Cycling` framework_sport bridge
rows; other sports keep generic D-006/D-008. Andy decides whether the split IDs become global.*

---

## 2. Cycling craft / equipment vessels

| Value | A — EQUIPMENT_CATEGORIES | B — bike_types_available | C — layer0.equipment_items | maps to discipline(s) | ✓Auth |
|---|---|---|---|---|---|
| Road bike | `road_bike` "Road Bike" | ✓ | **Road bike** | D-006 → D-006a | |
| Mountain bike | `mountain_bike` "Mountain Bike (MTB)" | ✓ | **Mountain bike** | D-008 → D-008a/b | |
| Gravel bike | `gravel_bike` "Gravel Bike" | ✓ | **Gravel bike** | D-006b (+ Andy: road+XC) | |
| TT / tri bike | — | — | **TT / triathlon bike** | D-006c | |
| Bike (generic) | — | — | **Bike (generic)** | D-006? (ambiguous) | |
| Cycling trainer *(indoor)* | `cycling_trainer` "Cycling Trainer / Smart Trainer" | ✓ | **Bike trainer** *(cat: Machines—Cardio)* | n/a (not a craft) | |
| Power meter *(accessory)* | — | — | **Power meter** | n/a | |
| Helmet *(accessory)* | — | — | **Helmet** | n/a | |

**Divergence:** TT bike + Bike (generic) live only in C (the v1 picker can't select them).
`cycling_trainer` (A/B) ↔ `Bike trainer` (C) is the same thing under two names in two categories.

---

## 3. Paddle craft / equipment vessels

| Value | A — EQUIPMENT_CATEGORIES | B — PADDLE_CRAFT_TYPES | C — layer0.equipment_items | maps to discipline(s) | ✓Auth |
|---|---|---|---|---|---|
| Kayak | `kayak` "Kayak" | `kayak` | **Kayak** | D-010 | |
| Canoe | `canoe` "Canoe" | `canoe` | **Canoe** | D-011 | |
| Packraft | `packraft` "Packraft" | `packraft` | **Packraft** | D-009 | |
| Surfski | — | `surfski` | — | (no discipline; Andy: never tracked) | |
| Sea kayak | — | — | **Sea kayak** | D-010 (Andy: never tracked) | |
| SUP | — | — | **SUP** | (no discipline) | |
| Inflatable raft | — | — | **Inflatable raft** | D-019 (Andy: never tracked) | |
| Rowing shell | — | — | **Rowing shell** | (no discipline) | |

**Divergence:** `surfski` lives only in B (never canonical). `Sea kayak`/`SUP`/`Inflatable raft`/
`Rowing shell` live only in C. None of the three v1 paddle lists agree with C.
**Landmine:** `Sea kayak` is read by the ETL `sum_to_100` validator + `report.py` paddle-set logic;
pruning it touches those, not just the catalog row.

---

## 4. Modality groups (live, reference — 9 groups)

| group_id | description | group_kind |
|---|---|---|
| paddle_flatwater | Flatwater paddle | paddle |
| paddle_whitewater | Whitewater paddle | paddle |
| foot | Foot (run / hike / nav) | foot |
| bike_pavement | Bike on pavement | bike |
| bike_offroad | Bike off-road | bike |
| snow_travel | Snow travel (foot) | snow |
| snow_glide | Snow travel (gliding) | snow |
| climb | Climbing (rope-protected) | climb |
| swim_openwater | Open-water swim | swim |

(No tracking issue for the modality system; it lives in `Modality_Group_Spec_v1.md`. Live + stable.)

---

## 5. Other vocabulary decisions in flight (from issue mine — context, not craft/disc)

- **#317** (OPEN) — `discipline_category` live values non-canonical: D-008 "Cycling" should be
  `Cycle / Trail`; D-015 "Navigation"/"Orienteering / Navigation" should be `Foot / Running`.
  Canonical prefix set `{foot, snow, cycle, water, vertical, mixed}`.
- **#340** (decided-to-add, deferred) — new "off-trail / trackless" terrain; `race_eligible=TRUE` +
  training-eligible.
- **#445** (open) — add `race_eligible: bool` terrain attribute (False for climbing gym / pump track
  / indoor gym).
- **#444** (open) — rename TRN-007 "Technical Rock" (candidate "Scree / boulder field").
- **#320** — disciplines/sports removed-via-code-canon (Fencing, Modern Pentathlon, Biathlon,
  Hiking, Orienteering, …) still physically in the xlsx; canon code is authoritative.
- **#428 (Track 1, shipped)** — equipment canonicalized to layer0 Title-case; picker reads
  `layer0.equipment_items`. **#430/#235** — full catalog → `layer0.*` (deferred).
- **#301 / #308** — dead `craft_substitution` flag enum value (emit-or-drop).

---

## 6. Duplication map (what "one source of truth" must collapse)

| Concept | Lives in | Forms | Collapse to? |
|---|---|---|---|
| Bike vessels | A, B, C | slug ↔ slug ↔ Title-case; C is superset (adds TT, generic) | **C** (rec) |
| Paddle vessels | A, B, C | three disagreeing lists; surfski only in B; sea kayak/SUP/raft/shell only in C | **C** (rec) |
| Indoor trainer | A/B (`cycling_trainer`) + C (`Bike trainer`) | two names | **C** |
| Disciplines | D (live) + E (committed #477/#476) | live single IDs vs committed split IDs | **E once ETL'd** |
| `discipline_category` | live (non-canonical) vs #317 canonical | "Cycling" vs "Cycle / Trail" | #317 canonical |

---

## 7. Decisions owed (Andy) — updated from v1

1. **D1 — Source of truth = `layer0.equipment_items` (C)?** v1 lists A + B retired or projected from
   C. *(Rec: yes — matches Track 1 #428 canonical-direct.)*
2. **D2 — Prune list.** Per row in §2–§3: keep / prune / fold. Specifically: surfski (B-only),
   Sea kayak, SUP, Inflatable raft, Rowing shell, Bike (generic). Mind the §3 landmine (ETL readers)
   and `exercises.equipment_required` references.
3. **D3 — #477 ETL.** The XC/Enduro/Road/Gravel/TT split is **committed**; the open question is
   *when* it lands in the canon and *whether* the split IDs are global or Endurance-Cycling-only.
   X1b.3b's craft→discipline map should target the post-#477 IDs (D-006a/b/c, D-008a/b), so #477
   ETL is now a **prerequisite**, not a parallel nicety.
4. **D4 — D-010a/b kayak split.** Confirm decided (then add to canon) or drop (keep single D-010).
5. **D5 — `EQUIPMENT_CATEGORIES` removal** — confirm full retirement of A + re-source the athlete
   craft picker from C (separate slice; 4-file + 6-file blast radius from v1 §6).

**Andy's stated craft→discipline intent (for X1b.3b, post-#477 — captured, not yet built):**
road bike → D-006a; TT bike → D-006c; gravel bike → Road + XC (D-006a/D-006b + D-008a); mtb → MTB +
XC (D-008b + D-008a); kayak + packraft carry whitewater; canoe flatwater-only.

---

## 8. Gut check

- The discipline side is **not** rotten — it's a clean live canon plus a clean committed split that
  simply hasn't been ETL'd. The rot is concentrated in the **equipment/craft** tri-furcation (§2–§3).
- Biggest sequencing truth: X1b.3b's craft map depends on **both** D2 (clean craft keys) **and** D3
  (#477 split IDs as targets). Neither is shippable in the same 5-file slice as the filter. Order:
  #477 ETL → craft-catalog prune/normalize → EQUIPMENT_CATEGORIES retirement → X1b.3b filter.
- Best argument against full reconciliation first: if you only want X1b.3b working soon, key the map
  on C's 7 real vessels against current single D-006/D-008 and refine when #477 lands. Coarser, but
  unblocks. (You chose "fix foundation first," so this is the fallback, not the plan.)

*End of audit v2.*
