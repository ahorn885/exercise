# D-73 Phase 5.2 Walkthrough — Best-Fit Re-Model Slice 4 (Layer 2B per-discipline terrain gaps) — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Best-fit re-model **Slice 4** — make Layer 2B the first node to *consume* the captured `RaceTerrainEntry.discipline_id`. Layer 2B now emits an additive per-discipline view (`terrain_by_discipline`) keyed off the discipline tag; the flat top-level aggregate is unchanged. Ratified at a **Trigger #3 gate** (3 AskUserQuestion decisions, all the recommended option).

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitRemodel_Slice3_Reconcile_SpecV4_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/kind-thompson-3Vac1` (harness-pinned; PR draft)
**Status:** Slice 4 shipped. 4 substantive files (`context.py`, `layer2b/builder.py`, `tests/test_layer2b.py`, `Layer2B_Spec.md`) + 1 trivial export (`layer4/__init__.py`) + bookkeeping. Runtime contract change (additive payload field). Scope ratified at a Trigger #3 gate — see §7.

---

## 1. Session-start verification (Rule #9)

Ran `scripts/verify-handoff.sh` — **all ✅, no ❌**, working tree clean on `claude/kind-thompson-3Vac1`, Slice 3 reconciliation (PR #150, `dd09701`) merged in. Spot-checked the predecessor §8 claims on-disk: `BestFitModality_Spec_v4.md` exists (§0 R5+R6, §12 Slice 3 satisfied-on-disk + Slice 4 next); `tests/test_discipline_display_names.py` count-pin asserts `len == 31`; `CURRENT_STATE` focus → Slice 4, Tests → 1616; `CARRY_FORWARD` re-model section reconciled. **No drift found** — narrative matched disk.

## 2. Session narrative

Andy opened with "lets work" on the Slice-3 closing handoff. After the Rule #9 sweep + state report he picked **Slice 4** as the scope. Per CLAUDE.md Trigger #3 (Layer 2B inter-layer contract change) I planned the change and put 3 decisions to an AskUserQuestion gate before any code; all 3 came back the recommended option (§7).

**Ground-truth read before planning:** `RaceTerrainEntry.discipline_id` is captured (Bucket E) but ignored by Layer 2B — `context.py:264` + the comment at 256-261 say "passes the field through without behavior change." The builder collapses everything by `terrain_id` (`builder.py` `race_id_set` / `pct_by_target` / `gaps_by_target`), so a terrain appearing in two disciplines at different percentages **loses one pct** (last-write-wins in `pct_by_target`). That collapse is the concrete bug per-discipline keying fixes. The proxy lookup (`_load_best_proxy`) is per `terrain_id` + locale set and **discipline-independent**, so grouping by discipline needs **zero extra SQL** — the per-block gaps are sliced from the already-computed gap records. Consumers take `Layer2BPayload` as a typed param and don't field-access the terrain internals (the brief/per-phase renderers don't even render terrain yet — that's Slice 6), so an additive field is safe.

## 3. File-by-file edits

### Runtime (contract change — additive)
- **`layer4/context.py`** — NEW `Layer2BDisciplineBlock` (`discipline_id`, `race_terrain: list[RaceTerrainOutput]`, `terrain_gaps: list[TerrainGap]`, `summary: Layer2BSummaryBlock`); added `discipline_id: str | None = None` to `RaceTerrainOutput` (pass-through); added `terrain_by_discipline: list[Layer2BDisciplineBlock] = []` to `Layer2BPayload`. Default `[]` keeps old cached payloads + existing consumers valid.
- **`layer4/__init__.py`** — export `Layer2BDisciplineBlock` (import + `__all__`).
- **`layer2b/builder.py`** — NEW `_build_discipline_blocks(race_terrain, included_discipline_ids, name_map, locale_id_set, gaps_by_target)`: one block per `included_discipline_id`, subset = entries tagged with that id **∪** race-wide (`None`) entries folded in, with tagged-wins dedup by `terrain_id`; per-block coverage / gaps / summary recomputed over the subset via the existing `_build_summary` + the already-computed `gaps_by_target` (no extra SQL). Block rows stamp the block's `discipline_id`; the flat top-level loop now also stamps the captured `entry.discipline_id` verbatim. Wired into the `Layer2BPayload(...)` return. Disciplines with no terrain (nothing tagged + no race-wide) emit no block; entries tagged to a discipline outside `included_discipline_ids` are excluded from blocks but remain in the flat aggregate.

### Tests
- **`tests/test_layer2b.py`** — NEW `TestPerDisciplineBlocks` (10): race-wide-folds-into-every-discipline, tagged-entries-route, **same-terrain-two-disciplines-keeps-distinct-pct** (the collapse fix), tagged-wins-over-race-wide, single-discipline-untagged-matches-aggregate, orphan-tagged-discipline-excluded, discipline-with-no-terrain-emits-no-block, empty-race_terrain-no-blocks, block-carries-race-wide-gap-for-every-discipline, tags-do-not-change-flat-aggregate (additive contract).

### Spec (in-place amend — form-refresh-C marker precedent, no version bump)
- **`Layer2B_Spec.md`** — §3 (`RaceTerrainEntry.discipline_id` + optional-tag paragraph); NEW §5.6 (per-discipline grouping algorithm + no-extra-SQL note + Slice-5 pointer); §7 (`Layer2BDisciplineBlock`, `terrain_by_discipline`, `RaceTerrainOutput.discipline_id`); §9 (additive-shape + one-time-invalidation note, no new eviction helper); §10 (4 new edge-case rows).

### Bookkeeping
- `BestFitModality_Spec_v4.md` — §12 Slice 4 ✅ shipped + Slice 5 flagged next; header status line.
- `CURRENT_STATE.md` — Last-shipped pointer → this handoff; narrative prepended; Current focus repointed Slice 4→done / Slice 5 next; Layer-2 status row; Tests headline 1616→**1649** with the partial-vs-full-collection note; neutralized the stale "next move: Slice 4" inside the preserved Slice-3 prose.
- `CARRY_FORWARD.md` — re-model section: Slice 4 ✅ shipped, Slice 5 next; section header.
- This handoff.

## 4. Code / tests results

- **Full suite `pytest tests/`: 1649 passed / 16 skipped** (this session `pip install`-ed `pytest` + `pydantic` + `requirements.txt` in-sandbox so all route-test modules collect — they were import-blocked in prior sessions without flask/pydantic, which is why the recorded headline read `1616`). Clean full-suite baseline **1639 → 1649** (+10 from `TestPerDisciplineBlocks`); zero regressions. `tests/test_layer2b.py` 21→**31**; `tests/test_layer4_orchestrator.py` + `test_layer4_cache.py` + `test_layer3_cached_wrappers.py` all green (143).
- Additive payload field → old cached cone entries deserialize (default `[]`); a one-time downstream Layer 3B/4 invalidation lands on first deploy (Spec v4 §9). No new eviction helper — the per-discipline grouping derives from inputs already covered by `evict_layer2b_on_terrain_change` + `evict_on_target_event_included_discipline_ids_change`.

## 5. Manual §5.0 verification steps

No new §5.0 scenario. No user-facing behavior changed (Layer 2B is a pure query node; nothing renders `terrain_by_discipline` until Slice 5/6). The form-side per-row discipline picker (Bucket E) was already walkable.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Re-model Slice 5 — resolver re-model + Layer 4 craft reasoning** (Spec v4 §5 / §12). The per-discipline resolver consumes the Slice-4 `terrain_by_discipline` blocks: rank each leg's terrain emphasis by `pct × fidelity` (§5.1), assemble the craft candidate set (§5.2; family grouping is the implicit open question flagged in Spec v4 §14), thread the candidate set + terrain emphasis into the Layer 4 plan-gen prompt, and replace v2's `race_modality_hints_hash` cache slot (§9). **Trigger #1** (LLM prompt-body change) → ratify at a gate before code.

### 6.2 Remaining re-model slices (Spec v4 §12)
- Slice 5 — resolver + Layer 4 craft reasoning (next; Trigger #1).
- Slice 6 — renderers consume `TrainingSubstitution` (migrate the 3 plan-gen renderers off the v2 modality payload AND off the flat `Layer2BPayload` fields onto `terrain_by_discipline`).

### 6.3 Other carried items
- **Deferred — clean discipline-ID renumber + the two collapses (R6, own session):** kayak D-008a/b → "Kayaking"; mtn-running D-022/D-023 → "Mountain Running". R6's gating rationale was "terrain axis consumed" — Slice 4 captured the Layer 2B consume, but the full consume is Slice 5; safest after Slice 5. When they collapse, prune the dead entries from `DISCIPLINE_DISPLAY_NAMES` + add survivor labels. ~40 files + 6 xlsx sheets + Neon rows + specs in lockstep.
- **DEPLOY (owed):** K3 equipment ETL on Neon — `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql`; confirm `populate_skill_capability_toggles.sql` applied.
- Deferred form feedback (Slice-1 §6.3): format vs `framework_sport`, aid-stations cadence (2E), mandatory-gear → pack-weight, injury Side-field drop + vocab generalization (2D), schedule simplification.
- M-7 multi-locale cluster ingestion; #8 locales→locations rename; BM-5 equipment-canon tail.
- 2B-1 (`relevant_discipline_ids TEXT[]` on `terrain_gap_rules` for structured relevance) still open — Slice 4 keys by the *athlete-captured* discipline tag, not gap-rule-side relevance; 2B-1 is the orthogonal gap-rule-side scoping.

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `BestFitModality_Spec_v4.md` (load-bearing for Slices 5-6) + `Layer2B_Spec.md` §5.6/§7 (the Slice-4 contract) 6. `./scripts/verify-handoff.sh`.

**Sandbox note:** `pytest`, `pydantic`, and `requirements.txt` are not preinstalled — `pip install -r requirements.txt --ignore-installed blinker` (the debian-managed blinker 1.7.0 lacks a RECORD file) then `pytest tests/` collects the full 1649-test suite.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **QW** | Session scope = re-model Slice 4 | Andy | Picked at the scope gate over K3 deploy / Slice 5+ / state-report-only. |
| **S4-1** | Layer 2B emits **per-discipline blocks** (vs thread `discipline_id` only) | Andy at gate | The real "consume the field" work; fixes the same-terrain-two-disciplines pct collapse; no extra SQL. |
| **S4-2** | Discipline tag stays **OPTIONAL** (`None`=race-wide, folds into every included discipline) — NOT required per row | Andy at gate | A single-discipline race's race-wide == its one discipline, so a global requirement would be wrong; existing rows are all `None`; no form/migration change. Resolves the optional-vs-required question Spec v4 §12 deferred to this slice. |
| **S4-3** | Output is **ADDITIVE** — keep flat `race_terrain`/`terrain_gaps`/`summary`; add `terrain_by_discipline` alongside | Andy at gate | No consumer break; Slice 6 migrates renderers. Replace-now would force a same-session renderer migration (Slice 6's job). |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `Layer2BPayload.terrain_by_discipline` field added (default `[]`) | ✅ `layer4/context.py` |
| `Layer2BDisciplineBlock` defined + exported | ✅ `context.py` + `layer4/__init__.py` |
| `RaceTerrainOutput.discipline_id` added | ✅ `context.py` |
| `_build_discipline_blocks` builds blocks; folds race-wide; tagged-wins; no extra SQL | ✅ `layer2b/builder.py` |
| flat aggregate fields unchanged | ✅ `test_tags_do_not_change_flat_aggregate` passes |
| same-terrain-two-disciplines pct preserved per block | ✅ `test_same_terrain_two_disciplines_keeps_distinct_pct` |
| `TestPerDisciplineBlocks` 10 tests pass; full suite 1649/16 | ✅ |
| `Layer2B_Spec.md` §3/§5.6/§7/§9/§10 amended | ✅ |
| `BestFitModality_Spec_v4.md` §12 Slice 4 ✅ / Slice 5 next | ✅ |
| `CURRENT_STATE` Last-shipped → this handoff; focus → Slice 5; Tests → 1649 | ✅ |
| `CARRY_FORWARD` re-model section: Slice 4 ✅, Slice 5 next | ✅ |

## 9. Files shipped this session

**Substantive:** `layer4/context.py`, `layer2b/builder.py`, `tests/test_layer2b.py`, `aidstation-sources/Layer2B_Spec.md` (+ trivial `layer4/__init__.py` export). **Bookkeeping:** `BestFitModality_Spec_v4.md`, `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

## 10. Carry-forward updates

- **Re-model Slice 4 shipped** — Layer 2B consumes `discipline_id` via additive `terrain_by_discipline`. Optional tag (None=race-wide) + additive output ratified at a Trigger #3 gate.
- **Slice 5** (resolver + Layer 4 craft reasoning, Trigger #1) is the next forward move; Slice 6 (renderers) after.

**End of handoff.**
