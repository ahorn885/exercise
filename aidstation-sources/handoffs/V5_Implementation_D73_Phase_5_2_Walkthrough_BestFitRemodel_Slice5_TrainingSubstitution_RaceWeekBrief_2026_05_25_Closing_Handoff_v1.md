# D-73 Phase 5.2 Walkthrough — Best-Fit Re-Model Slice 5 (training-substitution resolver + Layer 4 craft reasoning, race_week_brief) — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Best-fit re-model **Slice 5** — the resolver *re-model*. NEW `resolve_training_substitution` consumes the Slice-4 `Layer2BPayload.terrain_by_discipline` blocks and emits a per-discipline `TrainingSubstitutionPayload` (terrain emphasis ranked `pct × fidelity` + untrainable-terrain gaps + craft candidate set), threaded additively into the **race_week_brief** prompt body + cache key. Ratified at a **Trigger #1 gate** (3 AskUserQuestion decisions).

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitRemodel_Slice4_Layer2B_PerDiscipline_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/cool-shannon-LdkOj` (harness-pinned; PR draft)
**Status:** Slice 5 shipped. 7 substantive code files + 4 test files + spec amend + bookkeeping. Runtime contract change (additive payload field + additive prompt section + additive cache slot, race_week_brief only). Ceiling break ratified at the gate (§7).

---

## 1. Session-start verification (Rule #9)

Ran `scripts/verify-handoff.sh` — **all ✅, no ❌**, working tree clean on `claude/cool-shannon-LdkOj`; Slice 4 (PR #151, `af68228`) merged into main and the branch sits exactly on `origin/main` (0 ahead / 0 behind). Spot-checked the predecessor §8 claims on-disk: `Layer2BDisciplineBlock` + `terrain_by_discipline` in `layer4/context.py`, `_build_discipline_blocks` in `layer2b/builder.py`, Spec v4 §12 Slice 4 ✅ / Slice 5 next, `CURRENT_STATE` focus → Slice 5, Tests → 1649. **No drift found** — narrative matched disk.

## 2. Session narrative

Andy opened with "lets work" on the Slice-4 closing handoff, then picked **Slice 5**. Before any code I traced the full surface (a thorough Explore pass + direct reads). The discovery reframed the slice: the existing `resolve_best_fit_modality` → `Layer2ModalityPayload` is a *vocab-driven menu* node; Spec v4 §5 wants a *different* node (`resolve_training_substitution` → `TrainingSubstitutionPayload`) — net-new. Two facts shaped scope: (a) full §5 is ~8-10 substantive files (over the 5-ceiling), and (b) the craft axis has a real data gap — only `paddle_craft_types` + `bike_types_available` exist; no general `athlete_crafts` dict, no `discipline_id → race_craft` map, no craft-family grouping (the §14 open question). The terrain half is fully supported by the Slice-4 blocks.

Per Trigger #1 I put 3 decisions to an AskUserQuestion gate (options + tradeoffs + recommendation + gut check). Andy's picks (§7): **full Slice 5 with a ceiling break**, **all owned crafts handed to the LLM** (no family table), **additive** alongside the v2 payload. One wiring fact then narrowed scope honestly: **single_session does not compute Layer 2B** (off-race, 2A/2D/2C only), so it has no terrain breakdown and substitution doesn't apply there — Slice 5 targets **race_week_brief** (the full-cone entry point that already threads the v2 modality payload and is the PGE forcing function). plan_create / plan_refresh threading folds into Slice 6 (matches their pre-existing v2-modality threading deferral).

## 3. File-by-file edits

### Runtime (contract change — additive)
- **`layer4/context.py`** — NEW `TerrainEmphasis` (`race_terrain_id`, `terrain_name`, `pct`, `proxy_terrain_id/name`, `fidelity`, `gap_severity`, `proxy_methods`, `uncoverable_stimulus`, `emphasis_score` = pct×fidelity), `TerrainGapRef` (`race_terrain_id`, `terrain_name`, `pct`, `gap_severity`, `reason`), `TrainingSubstitution` (`discipline_id`, `discipline_name`, `race_craft`, `candidate_training_crafts`, `terrain_emphasis`, `untrainable_terrain`), `TrainingSubstitutionFlag` (Literal `craft_unavailable`/`craft_substitution`/`terrain_untrainable`/`terrain_low_fidelity`; optional discipline/terrain scope; message; metadata), `TrainingSubstitutionPayload` (`etl_version_set`, `recommendations`, `coaching_flags`).
- **`layer2_modality/substitution.py`** (NEW) — `resolve_training_substitution(*, terrain_by_discipline, athlete_crafts, etl_version_set, discipline_names=None, fidelity_floor=0.25, low_fidelity_threshold=0.60)`. **db-less, no extra SQL** (consumes the 2B blocks directly per §3's delegation). Per block: `available_locally` → emphasis at fidelity 1.0; gap with usable proxy → emphasis at `gap.proxy_fidelity` (+`terrain_low_fidelity` flag if < 0.60); unbridgeable / no-proxy / fidelity < floor → `untrainable_terrain` + `terrain_untrainable` flag. Emphasis sorted desc by `pct × fidelity`. `race_craft` = pure-craft display label. `candidate_training_crafts` = owned crafts verbatim (LLM picks). `craft_unavailable` once when zero crafts logged. `_untrainable_reason` helper.
- **`layer2_modality/__init__.py`** — export `resolve_training_substitution`.
- **`layer4/orchestrator.py`** — `_collect_athlete_crafts(layer1_payload)` flattens paddle+bike owned crafts (deduped/sorted); resolver runs at the end of `_upstream_full_cone`; NEW `training_substitution_payload` field on `_UpstreamFullCone`; threaded into the `llm_layer4_race_week_brief_cached` call. Import extended.
- **`layer4/hashing.py`** — `race_week_brief_key` gains `training_substitution_hash: str | None = None` (own slot, alongside `layer2_modality_hash`; `None → ''`; one-time key shift on first deploy).
- **`layer4/cached_wrappers.py`** — `llm_layer4_race_week_brief_cached` accepts `training_substitution_payload`, hashes it (`compute_payload_hash`), threads into `race_week_brief_key` + the `_synthesize` driver call. Import extended.
- **`layer4/race_week_brief.py`** — NEW `_render_training_substitution_section`; `_render_user_prompt` + `llm_layer4_race_week_brief` accept the payload + render the section additively (after the BM-3 modality section, before the 2E fueling section). Import extended.

### Tests
- **`tests/test_layer2_substitution.py`** (NEW, 20) — §13.1 packraft scenario (race_craft label, candidate set, river-top emphasis, whitewater untrainable, low-fid + untrainable flags); craft candidates (owns race craft, zero-crafts → `craft_unavailable`, dedup); terrain emphasis (available-locally fidelity 1.0, floor boundary trainable-vs-not, low-fid adaptation_weeks, good-proxy no-flag, missing-gap → untrainable); edge cases (empty-terrain craft-only, all-untrainable, empty-blocks, multi-discipline, determinism, name fallback, empty-etl raises).
- **`tests/test_layer4_hashing.py`** — +4: `training_substitution_hash` none==empty, set-distinguishes, independent-of-modality-slot, + parametrized component case.
- **`tests/test_layer4_orchestrator.py`** — NEW `TestTrainingSubstitutionWireUp` (2): payload threads to the brief wrapper; resolver consumes a `terrain_by_discipline` block (race_craft "Packrafting", river emphasis fidelity 1.0).
- **`tests/test_layer4_race_week_brief.py`** — NEW `TestTrainingSubstitutionSection` (5): section threads into the user prompt; absent when payload None; emphasis/untrainable/flags rendered; empty payload explanatory line; "(none logged)" candidates.

### Spec (in-place amend — form-refresh-C marker precedent, no version bump)
- **`BestFitModality_Spec_v4.md`** — Status line (Slice 5 ✅ / Slice 6 next); §7 + §9 Slice-5 as-built notes; §12 Slice 5 → SHIPPED with full as-built + deviations + scope; §12 Slice 6 expanded.

### Bookkeeping
- `CURRENT_STATE.md` (last-shipped prepended; focus → Slice 6; Layer 2 + Layer 4 status rows; Tests 1649 → **1680** + the `python -m pytest` interpreter note); `CARRY_FORWARD.md` (re-model section header + Slice 5 ✅ / Slice 6 next); this handoff.

## 4. Code / tests results

- **Full suite `python -m pytest tests/`: 1680 passed / 16 skipped** (+31 over Slice 4's 1649; zero regressions). New: `test_layer2_substitution.py` 20 + hashing +4 + orchestrator +2 + brief renderer +5.
- Additive `training_substitution_hash` slot → one-time race_week_brief cache invalidation on first deploy (Spec v4 §9). No new eviction helper — the substitution payload derives entirely from the Layer 1 + 2B inputs already covered by `evict_layer2b_on_terrain_change` + `evict_layer1_on_skill_toggle_change` + the included-discipline policy.
- **Sandbox interpreter note:** the `pytest` shim at `~/.local/bin/pytest` runs the *system* python (no pydantic/path). Deps + pytest are installed under `/usr/local/bin/python` — run `python -m pytest tests/`, not bare `pytest`.

## 5. Manual §5.0 verification steps

No new §5.0 scenario *required* (the substitution payload only affects the race_week_brief prompt cite material; no schema, no route, no user-facing form). A real-LLM brief walk is worth doing once the brief is in the auto-fire window: run `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026,7,3), cache=Layer4Cache(InMemoryCacheBackend()))` and confirm the `# Best-fit training substitution (Layer 2 substitution resolver)` section renders between the modality section and the `# Race-day fueling tier (2E)` section, with a per-discipline line for each `terrain_by_discipline` block (race craft + candidate crafts + terrain emphasis + untrainable terrain) and the substitution coaching flags. For Andy's PGE 2026 home context this exercises the paddle disciplines (kayak/canoe owned) against the Nerstrand terrain set. ~$0.50 real-LLM.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Re-model Slice 6 — renderers + remaining entry points** (Spec v4 §12). Migrate the plan-gen prompt renderers to consume `TrainingSubstitution` instead of the v2 `Layer2ModalityPayload`; thread the substitution payload (already on `_UpstreamFullCone`) into **plan_create** + **plan_refresh** — add cache slots to `plan_create_key` / `plan_refresh_key`, accept+hash in `llm_layer4_plan_create_cached` / `llm_layer4_plan_refresh_cached`, render in `layer4/per_phase.py` (`_format_modality_recommendations_per_phase` sibling) and `plan_refresh.py` if it has its own renderer. Then **retire the v2 path** (`resolve_best_fit_modality` + `_MODALITY_OPTIONS_PER_DISCIPLINE` + the three `_render_modality_section_*` renderers) once parity is proven. **Trigger #1** (prompt-body change) → ratify at a gate before code. Likely needs its own ceiling-aware scope cut (renderer migration + 2 entry-point wirings + v2 retirement is itself large).

### 6.2 Slice-5 follow-ons / known limitations (fold into Slice 6 or a later slice)
- **`craft_substitution` flag is LLM-side, not deterministic.** No `discipline_id → craft-token` map exists, so the resolver surfaces the candidate set + race-craft label and lets Layer 4 name the substitute. If a deterministic flag is wanted, add a small craft-token map (NOT the §14 family table — just the race-craft derivation per §3 R3).
- **§6 skill-gating is not applied** in the substitution node (no skill→terrain or skill→craft map on disk). The untrainable-terrain narrative carries the "can't train X" signal; explicit skill gating would need a mapping source.
- **Craft family grouping (§14) deferred** per gate decision 2 (all owned crafts handed to the LLM). Watch real briefs for over-substitution (e.g. recommending a bike for a paddle leg); if it happens, add a coarse deterministic craft-family proximity table (§14 escape hatch) — that's a vocab-ish change (Trigger #2/#5).
- **Fidelity thresholds** (`_UNTRAINABLE_FIDELITY_FLOOR = 0.25`, `_LOW_FIDELITY_THRESHOLD = 0.60`) are module constants aligned with the 2B severity banding; tune if briefs misclassify.

### 6.3 Other carried items
- **Deferred — clean discipline-ID renumber + the two collapses (R6, own session):** kayak D-008a/b → "Kayaking"; mtn-running D-022/D-023 → "Mountain Running". R6's gating rationale was "terrain axis consumed" — Slice 4 captured the 2B consume; Slice 5 is the resolver consume. Safest after Slice 6 (full renderer consume). When they collapse, prune dead `DISCIPLINE_DISPLAY_NAMES` entries + add survivor labels. ~40 files + 6 xlsx sheets + Neon rows + specs in lockstep.
- **DEPLOY (owed):** K3 equipment ETL on Neon — `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql`; confirm `populate_skill_capability_toggles.sql` applied.
- Deferred form feedback (Slice-1 §6.3): format vs `framework_sport`, aid-stations cadence, mandatory-gear → pack-weight, injury Side-field drop, schedule simplification.
- M-7 multi-locale cluster ingestion; #8 locales→locations rename; BM-5 equipment-canon tail; 2B-1 (`relevant_discipline_ids TEXT[]` gap-rule-side relevance).

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `BestFitModality_Spec_v4.md` (§5 + §12 Slice 6; §7/§9 as-built) + `Layer2B_Spec.md` §5.6/§7 (the Slice-4 contract the resolver reads) 6. `./scripts/verify-handoff.sh`.

**Sandbox note:** `pip install -r requirements.txt --ignore-installed blinker` then `python -m pip install pytest`, then run **`python -m pytest tests/`** (NOT bare `pytest` — the `~/.local/bin/pytest` shim uses a python without the deps/path). Full suite = 1680.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **QW** | Session scope = re-model Slice 5 | Andy | Picked at the scope gate. |
| **S5-1** | **Full Slice 5 with a ratified ceiling break** (vs a 5a/5b split or prompt-deferral) | Andy at gate | Wanted the complete vertical end-to-end; ceiling break precedented by the 8-9 file caller-side sessions. (Scope then narrowed to race_week_brief by the hard constraint that single_session has no Layer 2B.) |
| **S5-2** | Craft candidates = **all the athlete's owned crafts handed to the LLM**; no family-grouping vocab table | Andy at gate | Honors R1 (craft similarity is LLM-side) + §14's escape hatch. Only paddle has multiple owned crafts today; a deterministic family table is premature. Add one later only if the LLM over-substitutes. |
| **S5-3** | Output **ADDITIVE** — new `TrainingSubstitutionPayload` alongside the v2 `Layer2ModalityPayload` | Andy at gate | No consumer break; Slice 6 migrates renderers + retires v2. Mirrors the Slice-4 additive pattern. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `TrainingSubstitutionPayload` + 4 sub-types defined | ✅ `layer4/context.py` |
| `resolve_training_substitution` consumes 2B blocks, db-less, no extra SQL | ✅ `layer2_modality/substitution.py` + `__init__.py` export |
| emphasis ranked `pct × fidelity`; untrainable at floor; low-fid < 0.60; craft_unavailable on zero crafts | ✅ `test_layer2_substitution.py` (20 pass) |
| cone computes `training_substitution_payload` + threads to brief wrapper | ✅ `orchestrator.py` + `TestTrainingSubstitutionWireUp` |
| `training_substitution_hash` slot on `race_week_brief_key` (own slot, None→'') | ✅ `hashing.py` + 4 hashing tests |
| brief wrapper accepts+hashes+threads | ✅ `cached_wrappers.py` |
| additive `_render_training_substitution_section` in the brief prompt | ✅ `race_week_brief.py` + `TestTrainingSubstitutionSection` (5 pass) |
| Spec v4 §7/§9/§12 amended (Slice 5 ✅, as-built deviations, Slice 6 next) | ✅ `BestFitModality_Spec_v4.md` |
| `CURRENT_STATE` last-shipped + focus → Slice 6 + Layer 2/4 rows + Tests → 1680 | ✅ |
| `CARRY_FORWARD` re-model section: Slices 1+2+4+5 shipped, Slice 6 next | ✅ |
| full suite 1680 / 16 skipped, zero regressions | ✅ |

## 9. Files shipped this session

**Substantive (code):** `layer4/context.py`, `layer2_modality/substitution.py` (new), `layer2_modality/__init__.py`, `layer4/orchestrator.py`, `layer4/hashing.py`, `layer4/cached_wrappers.py`, `layer4/race_week_brief.py`. **Substantive (tests):** `tests/test_layer2_substitution.py` (new), `tests/test_layer4_hashing.py`, `tests/test_layer4_orchestrator.py`, `tests/test_layer4_race_week_brief.py`. **Spec:** `aidstation-sources/BestFitModality_Spec_v4.md`. **Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

## 10. Carry-forward updates

- **Re-model Slice 5 shipped** — `resolve_training_substitution` consumes `terrain_by_discipline` → `TrainingSubstitutionPayload`, threaded additively into race_week_brief (prompt + cache slot). All-owned-crafts-to-LLM + additive output ratified at a Trigger #1 gate.
- **Slice 6** (renderer migration onto `TrainingSubstitution` + plan_create/plan_refresh threading + v2 retirement, Trigger #1) is the next forward move.

**End of handoff.**
