# V5 Implementation — #884 Unified Gear/Craft Model — Slice 4.3 (retire `craft_discipline_aliases` + swim-equipment strip) — Closing Handoff

**Session:** Slice 4.3 of #884 — the **Layer-0 cleanup** slice. Two migrations: **(0030)** DROP the now-readerless `craft_discipline_aliases` table + remove it from `_LAYER0_TABLE_FAMILY` (bridged in the drift-guard exceptions until the redump folds it out of the baseline); **(0029)** strip `Pull buoy`/`Kickboard`/`Swim fins` from `equipment_items` (0C cache-neutral) and from EX126/EX128 `equipment_required` (0B serving-relevant). Both **Trigger #3** (cross-layer cache invalidation) — Andy-ratified scope (design v3 §15.4; the swim strip was Andy-deferred from slice 3b).
**Date:** 2026-06-29
**Predecessor handoff:** `V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice4b_PR3_2CGearToggleFeed_2026_06_29_Closing_Handoff_v1.md` (PR-3, merged as `e29e8d5` / PR #993)
**Branch:** `claude/884-unified-gear-craft-35gio1` (at `origin/main` HEAD `e29e8d5`; effectively a fresh branch off main, as slice 4.3 wanted)
**Status:** code done, **suite 3802/30 green**, ruff clean on changed files, `validate_layer0` **PASS** on baseline + all migrations (PG16 local gate). **2 migrations + 1 code + 1 test = under the 5-file ceiling.** **PR not yet opened — awaiting Andy's go** (operating model). **Two Andy-gated ops OWED on merge** (§1/§6.1): `layer0-apply` (runs `0029`+`0030`), then `layer0-redump` + fold. **#884 CONTINUES — next is slice 5** (away overlay).

> **Andy decisions this session (AskUserQuestion, 2026-06-29):** (1) **scope = both pieces in one PR** (one combined Layer-0 apply); (2) **retire method = DROP TABLE + redump-fold** (clean end state; not supersede-keep-DDL).

---

## 0. Thread continuity — NEXT SESSION CONTINUES #884

**The next forward move is slice 5** (away/locale availability overlay — generalize `_build_event_window_overlay` + away re-resolve, design v3 §7), then **slice 6** (capture-UX "Your gear" surface + onboarding parity + picker/validator registry, §10). Design v3 §15: 1→2→3→3a→3b→4(a/4.2/4b)→**4.3 (this)**→5→6. **But first the slice-4.3 Layer-0 ops must finish** (§6.1) — they trail the PR merge across an apply + a redump.

---

## 1. The change

### Decision context (no NEW architecture — ratified scope executed)
Slice 4.3 was ratified in design v3 §15.4 ("retire `craft_discipline_aliases`") and the swim-equipment strip was explicitly **Andy-deferred from slice 3b** to "a later swim slice" (0023's own header names it: *"Swim kit (Kickboard / Pull buoy / Swim fins) — deferred to a later swim slice … untouched"*). This session executes that. The two AskUserQuestion calls above resolved the only open shape decisions (combine vs split; DROP vs supersede) plus surfaced a **sequencing hazard not in the prior plan** (§2).

### Part A — retire `craft_discipline_aliases` (migration `0030`, DROP)
- No live reader remains: slice 4a repointed `_q_craft_discipline_aliases` + `_q_craft_group_kind` (`layer4/orchestrator.py`) onto `gear_discipline_aliases` (migration 0024); a repo-wide grep finds only docstrings/comments naming the old table. Data migrated 1:1 (verified byte-identical) and survives in git baselines + the active `gear_discipline_aliases` rows.
- `0030`: `DROP TABLE IF EXISTS layer0.craft_discipline_aliases CASCADE` (drops its OWNED-BY sequence; no inbound FK — audited vs the v1.9.0 baseline). Idempotent (`IF EXISTS`), atomic verify (`information_schema` confirms gone).
- Code: removed `"craft_discipline_aliases": "0A"` from `_LAYER0_TABLE_FAMILY`.

### Part B — swim-equipment strip (migration `0029`)
- **PART A (0B serving-relevant supersede+reinsert, the 0020 pattern):** EX126 `{Pull buoy}`→`{}`, EX128 `{Kickboard}`→`{}`, both moved to **`0B-v1.6.20`** (current max active exercises version was `0B-v1.6.19`). Every other column copied verbatim (incl. `equipment_substitutes_structured` — only the top-level `equipment_required` array changes, per the plan). The 0B `exercises` per-table digest advances → plan-gen caches invalidate.
- **PART B (0C cache-neutral supersede-only, the 0023 pattern):** `Pull buoy`/`Kickboard`/`Swim fins` superseded from `equipment_items` (the per-locale picker). NO version bump. The exercise strip runs FIRST so the cache-neutral precondition (0 active exercises name a retired item) holds when the picker rows are superseded.

---

## 2. The sequencing hazard (NEW finding — drove the DROP mechanics)

`_q_current_etl_version_set` (`layer4/orchestrator.py:2108`) runs `SELECT … FROM layer0.<table>` for **every** table in `_LAYER0_TABLE_FAMILY`. So:
1. **DROP-before-deploy breaks prod.** If `0030` drops the table on live while the *deployed* code still maps it, that query throws (relation does not exist) → all plan-gen breaks. **Safe order: merge (Vercel deploys the map-removal) → THEN `layer0-apply` runs `0030`.** Vercel deploys on merge; `layer0-apply` is a separate manual Andy tap, so the order falls out naturally — but it must be respected (do NOT apply `0030` before the PR merges + deploys).
2. **Drift-guard vs the committed baseline.** `TestLayer0TableFamilyMap.test_map_covers_every_baseline_versioned_table` reads the newest baseline (`etl/output/layer0_etl_v1.9.0.sql`, which still contains the table's DDL). Removing it from the map would normally fail the guard. **Bridge:** `craft_discipline_aliases` is listed in the guard's `_FAMILY_MAP_EXCEPTIONS` (`tests/test_layer4_orchestrator.py`) **as a TEMPORARY entry**, removed once the redump folds `0030` out of the baseline. `test_intentional_exceptions_stay_unmapped` then enforces it stays out of the map.

---

## 3. File-by-file edits

### 3.1 `etl/migrations/layer0/0029_strip_swim_gear_equipment.sql` (new)
Two-part migration (see §1B). Verify asserts: EX126/EX128 active with empty `equipment_required`; 0 active exercises name any of the 3 items; 0 of the 3 still active in `equipment_items`; no double-active `exercise_id`.

### 3.2 `etl/migrations/layer0/0030_drop_craft_discipline_aliases.sql` (new)
`DROP TABLE IF EXISTS … CASCADE` + verify. Header documents the deploy-order hazard + the redump-fold follow-up.

### 3.3 `layer4/orchestrator.py` (modified)
Removed the `craft_discipline_aliases` entry from `_LAYER0_TABLE_FAMILY`; updated the adjacent comment to record the DROP (0030) + the drift-guard bridge + the deploy-order constraint.

### 3.4 `tests/test_layer4_orchestrator.py` (modified)
Added `craft_discipline_aliases` to `_FAMILY_MAP_EXCEPTIONS` with a TEMPORARY-until-redump note.

---

## 4. Behavior change (intended) + cache

- **Swim strip:** served output is **presently identical** — slice 3b's owned-gear cardio-drill gate already drops EX126/EX128 from every pool while owned swim gear is empty (no swim-gear capture until slice 6). So the 0B digest shift is a **correct-but-harmless re-synth** (same property the #884 cascade slices carried). Once swim-gear capture lands (slice 6), an owner of a pull buoy/kickboard gets the drill via the owned-gear gate alone — no longer also needing the equipment in the locale pool.
- **Alias retirement:** zero served-output change (no reader). Removing the table from `_LAYER0_TABLE_FAMILY` drops its segment from the 0A digest → a **one-time 0A invalidation** (harmless re-synth; the cascade reads `gear_discipline_aliases`, unchanged).
- Net: two correct, intended cache invalidations (0A digest loses `craft_discipline_aliases`; 0B `exercises` digest advances to `0B-v1.6.20`). Andy acknowledged the Trigger-#3 invalidation by ratifying the slice.

---

## 5. Code / tests validation

- **Local gate (PG16, replicating `.github/workflows/ci.yml` `layer0-gate`):** loaded `layer0_etl_v1.9.0.sql`, applied `0023`–`0030` in order (all verify NOTICEs OK), `validate_layer0` → **PASS — all checks clean (or waived)** (the 5 `sum_to_100` waivers are pre-existing). Re-applied `0029`+`0030` → clean idempotent no-op.
- **Suite `tests/ etl/tests/`: 3802 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings).
- **Ruff:** clean on the 2 changed Python files' edited regions (the 3 pre-existing F841/E-class findings at `orchestrator.py:2440/2473` + `test_layer4_orchestrator.py:3023` are HEAD-pre-existing, untouched by this slice).
- **File count:** 2 migrations + `orchestrator.py` + the test = **4 substantive, under the ceiling.**

---

## 6. Next session pointers

### 6.1 OWED this PR — the Layer-0 ops sequence (do in this order)
1. **Andy's go → open the PR** (ready, not draft), `enable_pr_auto_merge` method=`merge`. **CI-trigger gotcha:** if opened via the GitHub MCP token, fire `ci.yml` via `workflow_dispatch` on the branch (CARRY_FORWARD ops note) so the 3 required checks attach.
2. **On merge → Vercel deploys the `_LAYER0_TABLE_FAMILY` map-removal FIRST** (this is the safety precondition — see §2.1).
3. **`layer0-apply`** (Andy one-taps `production`) — runs `0029` (strip) + `0030` (DROP). Idempotent; safe to re-run. **Only after the merge-deploy has landed** (so prod code no longer queries the dropped table).
4. **`layer0-redump`** (input `version` = next; `v1.9.0` → suggest **`v1.10.0`**) → `pg_dump` live `layer0` → `etl/output/layer0_etl_v1.10.0.sql` on a branch → open PR → `layer0-gate` validates the raw new baseline. The new baseline will **lack** `craft_discipline_aliases` (dropped) and carry the stripped EX126/EX128 + superseded swim items.
5. **Fold + cleanup in the redump PR** (README §"A re-dump … MUST be paired with folding the now-baked migrations"):
   - Archive `0023`–`0030` out of `etl/migrations/layer0/` (into a new `etl/_archive/pre_v1.10.0_baseline/`) — the gate re-applies a verify-bearing migration on a converged baseline and fails (e.g. `0030`'s DROP on a baseline that already lacks the table is an `IF EXISTS` no-op, but `0029`'s verify expecting `{Pull buoy}` present-then-stripped would mis-fire on already-stripped rows).
   - **Remove `craft_discipline_aliases` from `_FAMILY_MAP_EXCEPTIONS`** (`tests/test_layer4_orchestrator.py`) — once it's gone from the baseline DDL the drift guard no longer sees it, so the bridge is retired.
   - **Add `cardio_drill_gear_requirements` to `_LAYER0_TABLE_FAMILY`** (`0B`) — it was created by migration `0025` (not in the v1.9.0 baseline, so the drift guard doesn't yet require it), but the redump folds it INTO the new baseline → the guard will then require it mapped. It is a `0B`-versioned serving table read by `compute_cardio_drill_pool_ids` (the owned-gear drill gate), so it belongs in the 0B family. **Do this in the SAME redump PR** or the guard fails. *(Confirm its `etl_version` carries a `0B-` prefix — `0025` seeded it `0B-v1.9.1`.)*

### 6.2 Next session — CONTINUE #884 → slice 5 (away overlay)
Generalize `_build_event_window_overlay` + away re-resolve so brought gear/craft is feasible in the away segment only (design v3 §7; test scenario: "brings climbing gear to an away window → D-012 feasible in that segment only"). Then slice 6 (capture UX + unified registry). **Stay on the #884 thread until 5–6 done or Andy redirects.**

### 6.3 Open follow-ons (not owed by this slice)
- **Onboarding parity for gear toggles** (carried PR-1→PR-3): toggles captured on the profile gear-tab only; folds into slice 6 (capture UX).
- **`Provider_Inbound_Matrix_v2` §12 rollerski footnote** (CARRY_FORWARD doc-nit, #884 design v3 Decision 10).

### 6.4 Operating notes (Rule #13)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — last-shipped (this) + #884 predecessors. 3. `CARRY_FORWARD.md` — the #884 rolling item + the ops gotcha. 4. This handoff + `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md` (§4.3). 5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Both pieces (alias retire + equipment strip) in ONE PR | Andy 2026-06-29 | One combined Layer-0 apply / one merged invalidation window |
| 2 | Retire `craft_discipline_aliases` via DROP TABLE + redump-fold (not supersede-keep-DDL) | Andy 2026-06-29 | Cleanest end state; the table must leave the schema to leave the family map; data lives on in git + `gear_discipline_aliases` |
| 3 | Bridge the drift guard via a TEMPORARY `_FAMILY_MAP_EXCEPTIONS` entry until the redump | Claude | The committed baseline still carries the DDL; map-removal would otherwise fail the guard. Deploy-order hazard (§2) forced map-removal to ship with the DROP |
| 4 | EX126/EX128 bumped to `0B-v1.6.20` | Claude | Differ from + advance past the current max active exercises version `0B-v1.6.19` (README per-table digest rule) |

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Swim strip migration | `etl/migrations/layer0/0029_strip_swim_gear_equipment.sql` | grep `0B-v1.6.20`; PART A reinsert + PART B equipment_items supersede + verify DO block |
| DROP migration | `etl/migrations/layer0/0030_drop_craft_discipline_aliases.sql` | grep `DROP TABLE IF EXISTS layer0.craft_discipline_aliases CASCADE` |
| Map entry removed | `layer4/orchestrator.py` | grep `craft_discipline_aliases` → only the explanatory comment, NOT a dict key |
| Drift-guard bridge | `tests/test_layer4_orchestrator.py` | grep `"craft_discipline_aliases",` inside `_FAMILY_MAP_EXCEPTIONS` |
| Gate green | (local PG16) | `validate_layer0` PASS on baseline + `0023`–`0030`; idempotent re-apply |
| Suite green | (local) | `tests/ etl/tests/` 3802 passed / 30 skipped |
| Layer-0 ops OWED | — | `layer0-apply` (`0029`+`0030`) then `layer0-redump` v1.10.0 + fold — NOT yet run (§6.1) |

---

## 9. Files shipped this session

**Substantive (2 migrations + 1 code + 1 test):**
1. `etl/migrations/layer0/0029_strip_swim_gear_equipment.sql` — swim-equipment strip
2. `etl/migrations/layer0/0030_drop_craft_discipline_aliases.sql` — retire the legacy alias table
3. `layer4/orchestrator.py` — remove `craft_discipline_aliases` from `_LAYER0_TABLE_FAMILY`
4. `tests/test_layer4_orchestrator.py` — drift-guard exception bridge

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue updates.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` #884: slice-4 PROGRESS — 4a/4.2 + 4b PR1/PR2/PR3 done+merged (#298 fully closed); **4.3 (DROP `craft_discipline_aliases` + swim-equipment strip) done+pushed, PR awaiting Andy's go; Layer-0 apply + redump-fold OWED on merge (§6.1).** **Next: slice 5 (away overlay), then 6 (capture UX).**

---

**End of handoff.**
