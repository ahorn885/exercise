# Discipline-ID Renumber + Two Collapses (R6) — Migration Design v1

**Date:** 2026-05-25
**Trigger gate:** #3 (cross-layer) + #2 (vocab) + #5 (architectural). Scope + numbering scheme ratified by Andy at two AskUserQuestion gates this session.
**Status:** authoritative migration spec. The §2 map is the single source of truth; the migration script and all hand edits derive from it.

---

## 1. Decision record

- **Scope:** Full R6 as written — the two collapses **and** a clean sequential ID renumber (Andy at gate, over "mtn-run only / hold kayak", "collapse both no renumber", "hold both / re-scope").
- **Numbering scheme:** **Clean sequential** D-001..D-029, logical order, no suffixes, no gaps (Andy at gate, over "minimal-safe in-place" and "collapses only"). ~24 of 29 IDs change meaning — accepted with full knowledge of the silent-mismap risk.
- **Kayak regression accepted:** collapsing D-008a/b removes the whitewater-specific conditional inclusion (Layer 2A duration≥20h/nav gate) + the `whitewater_handling` skill gate's discipline target. Andy accepted this when choosing to collapse both pairs (the injury/stimulus/skill axes do not consume the Layer 2B terrain breakdown, so the distinction is not recoverable post-collapse).

## 2. Authoritative old → new ID map

Both members of a collapse pair map to the **same** new id (the survivor). All other ids re-sequence to close gaps + drop suffixes.

| Old | New | Discipline (survivor label) | Note |
|-----|-----|-----------------------------|------|
| D-001 | D-001 | Trail Running | stable |
| D-002 | D-002 | Road Running | stable |
| D-003 | D-003 | Hiking | stable |
| D-004 | D-004 | Open Water Swimming | stable |
| D-004b | D-005 | Pool Sprint Swimming | suffix absorbed |
| D-005 | D-006 | Road Cycling | shift |
| D-005a | D-007 | Road Cycling — TT/Tri | suffix absorbed |
| D-006 | D-008 | Mountain Biking | shift |
| D-007 | D-009 | Packrafting | shift |
| D-008a | **D-010** | **Kayaking** | **COLLAPSE** |
| D-008b | **D-010** | **Kayaking** | **COLLAPSE** |
| D-009 | D-011 | Canoeing | shift |
| D-010 | D-012 | Rock Climbing | shift |
| D-011 | D-013 | Abseiling / Rappelling | shift |
| D-012 | D-014 | Via Ferrata | shift |
| D-013 | D-015 | Orienteering / Navigation | shift |
| D-014 | D-016 | Swimming | shift |
| D-015 | D-017 | Snowshoeing | shift |
| D-016 | D-018 | Mountaineering | shift |
| D-017 | D-019 | Paddle Rafting | shift |
| D-018 | D-020 | Swimrun | shift |
| D-019 | D-021 | Uphill Skinning | shift |
| D-020 | D-022 | Alpine Descent | shift |
| D-021 | D-023 | Boot-packing & Transitions | shift |
| D-022 | **D-024** | **Mountain Running** | **COLLAPSE** |
| D-023 | **D-024** | **Mountain Running** | **COLLAPSE** |
| D-024 | D-025 | Epee Fencing | shift |
| D-025 | D-026 | Laser Run | shift |
| D-026 | D-027 | Obstacle Course Racing | shift (fills gap) |
| D-028 | D-028 | Cross-Country / Nordic Skiing | stable |
| D-029 | D-029 | Biathlon Shooting | stable |

**Sentinels left untouched** (not real disciplines; test-only "unknown id" fixtures): `D-030`, `D-031`, `D-099`, `D-997`, `D-999`. The map does not contain them, so the map-driven script leaves them alone.

### 2.1 Collision-safety

A naive sequential find/replace double-applies (e.g. D-005→D-006, then D-006→D-008 rewrites the just-made D-006). The migration script therefore runs **two phases**: phase 1 rewrites every old id to a unique sentinel token `@@RENUM:<new>@@`; phase 2 rewrites the token to the final id. No old id can be hit twice.

## 3. Collapse data-union spec

After the script renumbers, D-010 and D-024 each have **two** source rows/statements (the two collapsed members). Merge each into one survivor:

### D-010 Kayaking (was D-008a flat + D-008b whitewater)
- **stimulus_components** = union(D-008a, D-008b), deduped, order-stable.
- **body_parts_at_risk** = union (adds `Forearm` from whitewater).
- **technique_foci** = union of the foci arrays that referenced D-008a and/or D-008b.
- **skill toggle:** `whitewater_handling` `gated_discipline_ids` retargets to D-010 (Kayaking now carries the whitewater competence flag for races that need it; this is the accepted over-application).
- **Layer 2A conditional inclusion:** REMOVE the `_WHITEWATER_DISCIPLINE_ID` special-casing — Kayaking is an ordinary discipline now (no duration/nav auto-in gate, no sleep-dep whitewater special case). This is the accepted regression.

### D-024 Mountain Running (was D-022 uphill + D-023 downhill)
- **stimulus_components** = union(D-022, D-023), deduped.
- **body_parts_at_risk** = union (uphill hip-flexor/calf/achilles ∪ downhill quad/IT-band).
- **technique_foci** = union of foci arrays referencing D-022 and/or D-023.

## 4. File scope

**Renumbered (load-bearing, mechanical + hand):**
- All `.py` — runtime (`layer1..4/`, `layer2*/`, `routes/`, repo-root) + `etl/` + all of `tests/`.
- All live `.sql` — `etl/sources/*.sql` + `aidstation-sources/migrations/*.sql`.
- `discipline_display_names.py` — collapse: prune dead suffix/member entries, set survivor labels, renumber the rest.
- Workbook → saved as **`Sports_Framework_v11.xlsx`** (both `etl/sources/` and `aidstation-sources/data/`); ETL retargeted to v11; 0A etl_version bumps `0A-v10.0` → `0A-v11.0`.
- Current spec versions whose normative discipline references must stay correct.

**Left as history (NOT rewritten):** old handoffs, superseded `_vN` doc versions, and past-session narrative in `CURRENT_STATE.md` / `CARRY_FORWARD.md`. A single migration note + pointer to this map is added to the live state docs. Forward-looking §5.0 walkthrough scenarios that will be re-run get their IDs updated.

## 5. Execution order

1. Migration script renumbers all in-scope text files (two-phase token swap).
2. openpyxl renumbers the workbook (all sheets: cell values + embedded substrings) → save v11; collapse merges the two row pairs.
3. Hand-merge the duplicate D-010 / D-024 SQL statements + dict entries per §3.
4. Hand-rework the Layer 2A whitewater conditional + the `whitewater_handling` toggle target.
5. Retarget ETL to v11 + bump 0A etl_version pin.
6. Install test deps; run `python -m pytest tests/`; green any fallout.
7. Grep sweep: zero live references to `D-004b|D-005a|D-008a|D-008b|D-022|D-023` outside this doc + history; old base-id meanings reconciled.

## 6. Verification

- **Test suite:** full `python -m pytest tests/` green (baseline 1631 passed / 16 skipped; collapse removes some whitewater-conditional tests → expect a small net delta, fully accounted for).
- **Grep-clean:** no live (non-historical) file references a retired id form.
- **ETL pairing-count guard (silent name-coupling):** `extract_pairing_b2b_fallback` does name→id lookup on workbook Sheet "Sport × Discipline Map" col 7; renaming D-008a/b/D-022/3 risks silently dropping pairings. Mitigation: after the workbook edit, the next ETL run on Neon must assert `discipline_pairing` row-count is non-decreasing vs the v10 baseline. (Owed to Andy — see §7.)

## 7. Owed to Andy (cannot run in the ephemeral container — no DATABASE_URL)

- **Neon re-extract:** `python -m etl.layer0.run` against the v11 workbook → lands `0A-v11.0` rows in `layer0.disciplines` / `sport_discipline_bridge` / `discipline_pairing` / etc.; confirm `discipline_pairing` count non-decreasing (name-coupling guard).
- **Apply the renumbered populate scripts** (`populate_stimulus_components.sql`, `migrate_disciplines_add_body_parts_at_risk_v1.sql`, `populate_discipline_technique_foci.sql`, `populate_skill_capability_toggles.sql`, terrain-gap rules) against the new etl_version rows.
- **Re-pin** any deployed `etl_version_set` to `0A-v11.0`.
- This must ship together with the code change — runtime reads `layer0.*` by pinned etl_version; mismatched code (new ids) against un-re-extracted Neon (old ids) breaks every discipline lookup.
