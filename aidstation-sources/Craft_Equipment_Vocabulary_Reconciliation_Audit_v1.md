# Craft / Equipment Vocabulary Reconciliation Audit — v1

**Date:** 2026-06-08
**Branch:** `claude/v5-layer2c-handoff-988dgv`
**Trigger:** X1b.3b (craft→discipline alias substrate) surfaced that the craft vocabulary is
fragmented across three independent lists that do not agree. Andy directed: *fix the foundation
first; audit all three lists side by side, then decide the single source of truth and the prune
list.* This doc is Step 1 of that arc. **No code changed.** Decisions are Andy's and are listed
in §6.

---

## 1. The three lists (why this is "messed up")

There are three places that name craft/equipment, none authoritative over the others:

| # | List | File | Form | Scope |
|---|---|---|---|---|
| **A** | `EQUIPMENT_CATEGORIES` | `init_db.py:2132` | snake_case slug + display label | v1 app profile/onboarding picker |
| **B** | athlete craft enums (`PADDLE_CRAFT_TYPES`, `bike_types_available`) | `athlete.py:286,300` | snake_case enum | v1 athlete-profile write-path |
| **C** | `layer0.equipment_items` | `etl/output/layer0_etl_v1.5.0.sql:585-705` (121 rows) | Title-case canonical_name | the LLM-pipeline gear catalog ("our gear table") |

List **B** sources its bike values *from* List A's `Cycling Equipment` block, so A and B are coupled
on the bike side but **diverge on paddle** (B adds `surfski`, which is in neither A nor C).

Track 1 (Locations Consolidation, 2026-06-05/06) already moved **locale** equipment off the v1
slug model onto List C canonical-direct. The athlete **craft** inventory was never migrated — it
still reads A/B. That is the root of the fragmentation.

---

## 2. Side-by-side — the craft slice (bike + paddle vessels)

Only the sport-specific *vessels* matter for craft substitution (X1b.3b). Indoor ergs
(trainer / stationary / spin / assault / kayak-erg / paddle-erg) are training surfaces, not
crafts, and are excluded from the substitution map.

### 2.1 Bike vessels

| A — `EQUIPMENT_CATEGORIES['Cycling Equipment']` | B — `bike_types_available` | C — `layer0.equipment_items` (cat: Sport-Specific — Cycling) |
|---|---|---|
| `road_bike` "Road Bike" | (subset of A) | **Road bike** |
| `mountain_bike` "Mountain Bike (MTB)" | | **Mountain bike** |
| `gravel_bike` "Gravel Bike" | | **Gravel bike** |
| `cycling_trainer` "Cycling Trainer / Smart Trainer" *(indoor)* | | **TT / triathlon bike** ← *only in C* |
| | | **Bike (generic)** ← *only in C* |
| | | Power meter, Helmet *(accessories, not vessels)* |

**Divergence:** `TT / triathlon bike` and `Bike (generic)` exist only in C. `cycling_trainer`
(indoor) exists only in A. So the v1 picker cannot select a TT bike even though the canonical
catalog has it.

### 2.2 Paddle vessels

| A — `EQUIPMENT_CATEGORIES['Paddling Equipment']` | B — `PADDLE_CRAFT_TYPES` | C — `layer0.equipment_items` (cat: Sport-Specific — Paddle) |
|---|---|---|
| `kayak` "Kayak" | `kayak` | **Kayak** |
| `canoe` "Canoe" | `canoe` | **Canoe** |
| `packraft` "Packraft" | `packraft` | **Packraft** |
| | `surfski` ← *only in B* | **Sea kayak** ← *only in C* |
| | | **SUP** ← *only in C* |
| | | **Inflatable raft** ← *only in C* |
| | | **Rowing shell** ← *only in C* |
| | | Paddle (double/single-blade), Rowing oar, Kayak/canoe seat *(accessories, not vessels)* |

**Divergence:** `surfski` is in B only (never in the canonical catalog). `Sea kayak`, `SUP`,
`Inflatable raft`, `Rowing shell` are in C only. Andy's read: *surfski, Sea kayak, Inflatable raft
were never things we actually tracked.*

---

## 3. The discipline targets (what crafts can map to)

The craft→discipline map can only point at disciplines that exist. The bike/paddle disciplines in
the live canon (`discipline_canon.py` == `layer0.disciplines`, no divergence — see §4):

| Discipline | Name | Modality group(s) |
|---|---|---|
| D-006 | Road Cycling | bike_pavement |
| D-007 | Time-Trial Cycling | bike_pavement |
| D-008 | Mountain Biking | bike_offroad |
| D-009 | Packrafting | paddle_flatwater + paddle_whitewater |
| D-010 | Kayaking | paddle_flatwater + paddle_whitewater |
| D-011 | Canoeing | paddle_flatwater |
| D-019 | Paddle Rafting | paddle_flatwater |

**No XC / Enduro cycling discipline exists.** Andy's desired mapping (`gravel → Road + XC`,
`mtb → MTB + XC`) treats XC as a distinct target, but the canon has only the single `D-008 Mountain
Biking`. "XC" appears in the bridge layer as a *sport sub-format* ("XC Mountain Biking", "XC / AR
Cycling") that resolves to D-008 — not as a `discipline_id`. The XC/Enduro split is **deferred
issue #477** (D-008 → D-008a XC / D-008b Enduro; plus D-006 road format variants). **Until #477
ships, gravel and mtb can only both point at the single D-008.**

**Orphan vessels (no discipline target exists):** `SUP`, `Rowing shell`. No standalone SUP or
rowing discipline in the canon. They cannot be aliased to anything today.

---

## 4. Disciplines — NOT fragmented (clearing the "two lists?" worry)

Unlike equipment, there is **one** discipline list. `etl/layer0/discipline_canon.py` and the live
`layer0.disciplines` agree exactly: **21 active disciplines + 3 aliases** (D-005→D-004 Swimming,
D-015→D-003 Trekking, D-016→D-004). **All 21 active disciplines carry a modality group** — the
X1b.1 `run_modality_group_orphan` ERROR-severity validator guarantees none is left off. Verified
membership coverage: D-001/002/003 → foot; D-004 → swim_openwater; D-006/007 → bike_pavement;
D-008 → bike_offroad; D-009/010/011/019 → paddle_*; D-012/013/014 → climb; D-017/018 → snow_travel;
D-021/022/028 → snow_glide; D-024/027 → foot.

So the "multiple disciplines left off" impression comes from the **craft map** only touching the 7
bike/paddle disciplines — which is correct: foot, climb, swim, and snow disciplines have no
"craft" to alias. The substrate is sound; the gap is purely in the equipment/craft vocabulary.

---

## 5. Cruft inventory (Andy's "never tracked" flags)

| Item | Where it lives | Origin | Disposition Andy flagged |
|---|---|---|---|
| `surfski` | B (`PADDLE_CRAFT_TYPES`) | D-73 Phase 1.2C enum (athlete.py:300) | Never tracked → **prune candidate** |
| `Sea kayak` | C (`equipment_items`) | Vocabulary_Audit "subtype of Kayak via sub-question"; also in `sum_to_100` paddle list | Never separately tracked → **prune / fold into Kayak** |
| `Inflatable raft` | C (`equipment_items`) | K2 additions migration ("normalized from Inflatable Raft, Loaded Packraft") | Never tracked → **prune / fold into Packraft or D-019** |
| `SUP` | C (`equipment_items`) | canonical catalog | Orphan (no discipline) — keep or prune? |
| `Rowing shell` | C (`equipment_items`) | canonical catalog | Orphan (no discipline) — keep or prune? |
| `Bike (generic)` | C (`equipment_items`) | canonical catalog | Ambiguous vessel — map to D-006 or prune? |

**Note:** `Sea kayak` is referenced by the ETL `sum_to_100` validator and `report.py` paddle-set
logic (`etl/layer0/validation/sum_to_100.py:40`, `report.py:46`). Pruning it touches those — not a
pure delete. Same caution applies before removing any C row that other ETL passes read.

---

## 6. `EQUIPMENT_CATEGORIES` removal — blast radius (Andy: "remove it entirely")

`EQUIPMENT_CATEGORIES` (List A) is referenced in **4 files**:

- `init_db.py` (definition + seed)
- `athlete.py` (the `bike_types_available` subset-of comment + craft enum context)
- `etl/layer0/extractors/vocabulary.py` (`_EQUIPMENT_CATEGORIES` — a *separate* copy in the ETL)
- `tests/test_bucket_c_terrain_vocab_audit.py`

The downstream craft fields it feeds (`bike_types_available`, `paddle_craft_types`) flow through
**6 files**: `init_db.py`, `athlete.py`, `layer1/builder.py`, `layer4/orchestrator.py`
(`_collect_athlete_crafts`), `layer4/context.py`, plus `tests/test_layer1_builder.py`.

Removing A entirely means the athlete craft picker must be re-sourced from C (canonical-direct),
mirroring the Track 1 locale-equipment migration. That is its own slice with profile/onboarding UI
work — **not** a side effect of the vocabulary decision. Recommend treating it as a distinct slice
*after* the vocabulary is pinned.

---

## 7. Recommendation + decisions owed (Andy)

**Recommended source of truth:** List **C** (`layer0.equipment_items`), consistent with the Track 1
canonical-direct model already shipped for locale equipment. A and B become projections of C (or
are retired). This is a recommendation only — Andy decides.

**Decisions owed before X1b.3b can resume:**

1. **D1 — Source of truth.** Confirm C (`layer0.equipment_items`) as authoritative; A/B retired or
   driven from C. *(Recommended: yes.)*
2. **D2 — Prune list.** For each cruft row in §5 (`surfski`, `Sea kayak`, `Inflatable raft`, `SUP`,
   `Rowing shell`, `Bike (generic)`): keep, prune, or fold-into-parent. Pruning C rows requires
   updating the ETL passes that read them (§5 note). *(Trigger #2 — data removal.)*
3. **D3 — XC ordering.** Either (a) ship #477 (D-008 → D-008a XC / D-008b Enduro) **before** the
   craft map so `gravel → Road + XC` / `mtb → MTB + XC` can be expressed exactly, or (b) accept
   `gravel`+`mtb` both → single D-008 now and tighten when #477 lands. *(Trigger #3 — cross-layer.)*
4. **D4 — `EQUIPMENT_CATEGORIES` retirement.** Confirm full removal of List A and re-sourcing the
   athlete craft picker from C as a **separate** slice (§6 blast radius). *(Trigger #3.)*

**Proposed sequence once D1–D4 are answered:** (1) prune/normalize C per D2 → emit
`layer0_etl_v1.6.0.sql`; (2) #477 discipline split if D3=(a); (3) `EQUIPMENT_CATEGORIES` retirement +
craft picker re-source (D4); (4) **then** X1b.3b craft→discipline alias substrate + the
`resolve_training_substitution` filter, now keyed on clean canonical vessels against a stable
discipline set.

---

## 8. Gut check

- **Biggest risk:** scope sprawl. D2+D3+D4 are each a slice; doing them as one PR blows the 5-file
  ceiling and mixes data-removal, vocabulary, and discipline-taxonomy concerns. They should be
  sequenced, not bundled.
- **What might be missing:** the `exercises.equipment_required` column references List C names
  (e.g. exercise EX073-075 list "Road bike, Mountain bike, Bike trainer, TT Bike, Gravel bike").
  Any C rename/prune in D2 must be checked against `equipment_required` and the
  `clean_equipment_column.py` / `pass2_cleanup.py` ETL maps, or exercise availability resolution
  breaks. This widens D2 beyond a simple row delete.
- **Best argument against the recommendation:** if the only near-term consumer is X1b.3b's craft
  substitution, a *minimal* fix (key the alias map on C for just the 7 real bike/paddle vessels,
  ignore the cruft, defer #477) unblocks X1b.3b without the full A-retirement project — option
  "Build X1b.3b against current canon" from the resequencing question. The full reconciliation is
  the right long-term call but is not strictly required to ship X1b.3b imperfectly.

*End of audit v1.*
