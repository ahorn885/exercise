# D-73 Phase 5.2 Walkthrough — Best-Fit Re-Model Slice 2 (Vocab / Pure-Craft Display Names) + CURRENT_STATE Drift Fix — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Continued the best-fit re-model from the Spec-v3 + Slice-1 predecessor. Shipped **Slice 2 (vocab)** as a runtime pure-craft display-name overlay, plus a `CURRENT_STATE.md` drift fix.

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitRemodel_SpecV3_Slice1_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/brave-meitner-S3Uot` (PR #149, draft)
**Status:** Slice 2 shipped (2 substantive code files + 2 test files) + bookkeeping. Suite **1616 passed / 16 skipped** (was 1604; +12 new tests). Scope evolved at 6 AskUserQuestion gates — see §7.

---

## 1. Session-start verification (Rule #9)

Ran `scripts/verify-handoff.sh` + targeted grep spot-checks against the Spec-v3/Slice-1 predecessor's §8 table. **All content claims verified on-disk:** resolver `race_craft` count 0, D-008b vocab present (1), `init_db.py` DROP-COLUMN migration present + ADD gone, residual `race_modality_hints|race_craft` non-docs grep = 0, K3 ETL present, `_race_modality_hints_editor.html` gone. The sweep's one ❌ (the `_race_modality_hints_editor` partial MISSING) is the *intended* Slice-1 deletion (false positive — the script lists all referenced paths including deleted ones). **One real (minor) drift found + fixed:** `CURRENT_STATE.md`'s `## Current focus` block was never refreshed across the LogThis → FreqCaps → TriggeredByAdHoc → Layer2C-Telemetry → Layer3-caching → re-model sessions; it still narrated the freq-caps work. Repointed it at re-model Slice 1 (shipped) + Slice 2 (forward move), keeping the prior chain as labeled history (commit `884f161`).

## 2. Session narrative

Andy opened with "lets work" on the Slice-1 closing handoff. After the Rule #9 sweep + state report, he picked (a) the `CURRENT_STATE` drift fix and (b) Slice 2 (vocab). Slice 2 is a Trigger #2 gate, so it ran as investigation → ratification → implement.

**Investigation (ground truth, not handoff narrative):** read the actual `Sports_Framework_v10.xlsx`. The UI picker label = `sport_discipline_bridge.discipline_name`, sourced by the ETL (`etl/layer0/extractors/sports_framework.py:extract_sport_discipline_map`) from **Sheet 3 col 3** (sport-variant labels), e.g. Adventure Racing surfaces D-005 as **"XC Cycling (Road/Gravel)"** — a mislabel. Key finding: the spec's premise ("use canonical Sheet-2 names") is only half-right — Sheet-2 names *also* bundle qualifiers ("Road Cycling (Road / Gravel / Tri / TT)"), so a curated set is genuinely needed (justifies Trigger #2).

**Scope evolution across the gates (§7):** Andy reframed from "label cleanup" toward a full pure-craft re-derivation ("each discipline separately, all sports"; cycling = Road / Gravel / MTB; "XC" isn't a craft). Blast-radius check showed discipline IDs are cross-layer keys in ~40 code/SQL/test files + 6 xlsx sheets + specs → a Trigger #3 migration. Net landing: **labels-only this slice, IDs stable, collapses + clean renumber deferred.** Mechanism pivoted from "edit the xlsx" to a **runtime overlay** after code review found a *silent* name-coupling in the xlsx pairing machinery (see §3 / §7 M).

**Implementation:** curated `discipline_id → display_name` overlay + helper, applied at the single shared label choke point.

## 3. File-by-file edits

### Slice 2 — pure-craft display-name overlay (substantive)
- **NEW `discipline_display_names.py`** — `DISCIPLINE_DISPLAY_NAMES` dict (30 disciplines, pure-craft labels; terrain/equipment qualifiers stripped) + `discipline_display_name(discipline_id, fallback=None)` helper (curated label wins; falls back to the bridge name, then the id). Module docstring records the overlay rationale + the deferred kayak/mountain-running collapses.
- **`routes/race_events.py`** — import `discipline_display_name`; in `_disciplines_for_framework_sport` the label is now `discipline_display_name(r['discipline_id'], r['discipline_name'])` (was the raw bridge `discipline_name`). This is the shared choke point — `routes/onboarding.py:973` imports + calls the same helper, so both the race-event edit picker and onboarding step-3 inherit the clean labels. Docstring note added.

### Tests
- **NEW `tests/test_discipline_display_names.py`** — 11 tests (2 classes): id-format/non-empty/no-paren-qualifier invariants on the map; D-005 mislabel fixed; kayak + mountain-running pairs still distinct this slice; helper curated-wins / fallback-to-bridge / fallback-to-id paths.
- **`tests/test_routes_race_events.py`** — `test_returns_id_label_dicts_from_bridge` updated (labels now come from the overlay, not raw bridge names) + NEW `test_uncurated_id_falls_back_to_bridge_name` (combined "D-005 + D-005a" row falls back).

### Bookkeeping
- `CURRENT_STATE.md` (drift fix §1 + this-session pointer), `CARRY_FORWARD.md` (Slice-2 shipped + deferred collapses/renumber), this handoff.

## 4. Code / tests results

- Full suite (`pytest tests/ --ignore=tests/test_layer1_builder.py`): **1616 passed, 16 skipped** (pre-session 1604; +12 net new). Zero failures. (Sandbox deps `pytest`/`flask`/`pydantic`/`bcrypt`/`zxcvbn`/`flask_wtf` pip-installed to run the suite; `--ignore-installed blinker` to dodge a debian RECORD conflict.)
- Overlay covers all 30 single-id disciplines; combined-id bridge rows ("D-005 + D-005a") + any future id fall back to the bridge `discipline_name` (graceful).

## 5. Manual §5.0 verification steps

No new §5.0 scenario added. The change is a UI-label transform with full unit coverage. **Andy should eyeball** on the next Vercel preview: the race-event edit discipline picker (`/profile/race-events/...`) + onboarding step-3 should show pure-craft labels — for Adventure Racing: "Road Cycling" (not "XC Cycling (Road/Gravel)"), "Hiking" (not "Hiking (Weighted)"), "Orienteering", "Mountaineering", "Rock Climbing", with "Flat-water Kayaking"/"Whitewater Kayaking" still distinct. **No Neon re-extract owed** — the overlay is runtime, takes effect on deploy of this branch.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Re-model Slice 3 — data model** (Spec v3 §12): `race_terrain` → discipline-keyed dict `{discipline_id: [{terrain_id, pct}]}`; discipline-centric form; migrate rows (Trigger #3). **Land the two deferred ID collapses here** (kayak D-008a/b → "Kayaking"; mountain-running D-022/D-023 → "Mountain Running") because the per-discipline terrain/gradient axis is what absorbs the flat-vs-whitewater / uphill-vs-downhill distinction the collapse would otherwise flatten. When those ids collapse, **prune the now-dead entries from `DISCIPLINE_DISPLAY_NAMES`** and add the survivor label ("Kayaking", "Mountain Running").

### 6.2 Remaining re-model slices (Spec v3 §12)
- Slice 4 — Layer 2B per-discipline terrain gaps (`RaceTerrainEntry.discipline_id` exists, unused).
- Slice 5 — resolver re-model + Layer 4 craft reasoning; replace the v2 `race_modality_hints_hash` cache slot (Trigger #1).
- Slice 6 — renderers consume `TrainingSubstitution`.

### 6.3 Other carried items
- **Deferred — clean discipline-ID renumber:** own dedicated migration session (~40 files + 6 xlsx sheets + Neon rows + specs in lockstep; silent-mismap risk). Schedule after Slices 3–6.
- **DEPLOY (owed):** K3 equipment ETL on Neon — `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql`; confirm `populate_skill_capability_toggles.sql` applied.
- Deferred form feedback (Slice-1 §6.3): format vs `framework_sport` reconciliation, Aid-stations count → fueling cadence (2E), mandatory-gear → pack-weight, injury Side-field drop + vocab generalization (2D), schedule simplification.
- M-7 multi-locale cluster ingestion; #8 locales→locations rename; BM-5 equipment-canon tail still stand.

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `BestFitModality_Spec_v3.md` (load-bearing for Slices 3–6) 6. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **QW** | Do drift fix + Slice 2 | Andy | "4 and 1" at the scope gate. |
| **M-mech** | Display name = **runtime overlay**, not xlsx edit | Andy at gate | Code review found *silent* name-coupling (Sheet-2 names ↔ Sheet-3 B2B free-text ↔ `extract_pairing_b2b_fallback` name→id; a rename silently drops pairings). Overlay is immediate, unit-testable in-sandbox, clean diff, doesn't perturb the pairing machinery. |
| **M-scope** | Pure-craft **labels**, all sports, **IDs stable** | Andy at gate | Reframed from "AR-only" to "each discipline separately, all sports"; blast-radius check kept the *set/IDs* change out of this slice (Trigger #3). |
| **M-kayak** | Defer D-008a/b collapse to **Slice 3** | Andy at gate | Flat-vs-whitewater is a terrain distinction; the terrain axis that carries it (Slice 3/4) doesn't exist yet — collapsing now would flatten differentiated fidelity/skill data. |
| **M-mtnrun** | Defer D-022/D-023 collapse to **Slice 3** | Andy | "there aren't events that only do one or the other" — same lossy-merge logic as kayak (uphill/downhill = gradient axis). |
| **M-renum** | Clean ID renumber = **later, own session** | Andy at gate | IDs are invisible keys; the labels carry the visible win. A renumber riding a label change = max churn / min benefit + silent-mismap risk. |
| **D-005** | AR road-cycling label = **"Road Cycling"** | Andy | Fixes the "XC Cycling (Road/Gravel)" mislabel; "XC" isn't a cycling craft (it's MTB on XC terrain). |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `discipline_display_names.py` exists | ✅ `ls discipline_display_names.py` |
| Map has 30 entries | ✅ `python3 -c "from discipline_display_names import DISCIPLINE_DISPLAY_NAMES as m; print(len(m))"` → 30 |
| D-005 mislabel fixed | ✅ `DISCIPLINE_DISPLAY_NAMES['D-005']` == "Road Cycling" |
| kayak pair still distinct (collapse deferred) | ✅ `DISCIPLINE_DISPLAY_NAMES['D-008a'] != ['D-008b']` |
| mountain-running pair still distinct (collapse deferred) | ✅ `['D-022'] != ['D-023']` |
| overlay wired at the label choke point | ✅ `grep -n discipline_display_name routes/race_events.py` → import + use in `_disciplines_for_framework_sport` |
| no parenthetical qualifiers in labels | ✅ test `test_no_terrain_qualifier_parens_in_labels` green |
| uncurated id falls back to bridge name | ✅ test `test_uncurated_id_falls_back_to_bridge_name` green |
| full suite green | ✅ 1616 passed, 16 skipped |
| `CURRENT_STATE.md` pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Slice-2 shipped + deferrals recorded | ✅ |

## 9. Files shipped this session

**Substantive:** NEW `discipline_display_names.py`; `routes/race_events.py` (overlay wire); NEW `tests/test_discipline_display_names.py`; `tests/test_routes_race_events.py` (2 tests). **Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff. Commits: `884f161` (drift fix), plus the Slice-2 commit.

## 10. Carry-forward updates

- **Re-model Slice 2 shipped** as a runtime display-name overlay (mechanism flip from xlsx → overlay; IDs stable). The `CARRY_FORWARD` re-model section now records the two Slice-3 collapse candidates (kayak, mountain-running) + the deferred clean ID renumber as its own session.
- UI labels are now pure-craft at runtime — no Neon re-extract owed for this slice.

**End of handoff.**
