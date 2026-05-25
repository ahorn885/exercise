# D-73 Phase 5.2 Walkthrough — Best-Fit Re-Model Slice 6 (renderer migration onto TrainingSubstitution + full v2 retirement) — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Best-fit re-model **Slice 6** — the final slice. Migrates the plan-gen per-phase renderer onto `TrainingSubstitution`, threads the substitution payload into **plan_create** + **plan_refresh** (all 3 tiers) alongside the already-wired **race_week_brief**, and **retires the entire v2 `Layer2ModalityPayload` path** (`resolve_best_fit_modality` + `_MODALITY_OPTIONS_PER_DISCIPLINE` + the 3 `_render_modality_section_*` renderers + the 4 v2 types). `resolve_training_substitution` is now the sole best-fit node. **The best-fit re-model is complete.** Ratified at a **Trigger #1 gate** (2 AskUserQuestion decisions).

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitRemodel_Slice5_TrainingSubstitution_RaceWeekBrief_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/youthful-shannon-dJa6I` (harness-pinned; PR draft)
**Status:** Slice 6 shipped. ~12 substantive code files + 1 deleted + 2 test files migrated + 1 test file deleted + spec amend + bookkeeping. Runtime contract change (3 cache-key shape changes → one-time invalidation per entry point on first deploy; prompt-body change on plan_create / plan_refresh; v2 surface removed). Ceiling break ratified at the gate (§7).

---

## 1. Session-start verification (Rule #9)

Ran `scripts/verify-handoff.sh` — **all ✅, no ❌**, working tree clean on `claude/youthful-shannon-dJa6I`; Slice 5 (PR #152, `b2ebe7a`) merged into main and the branch sat exactly on `origin/main` (0 ahead / 0 behind). Spot-checked the predecessor §8 claims on-disk: the 5 new types in `layer4/context.py`, `resolve_training_substitution` in `layer2_modality/substitution.py`, the `training_substitution_hash` slot in `hashing.py`, and Spec v4 §12 Slice-5-SHIPPED / Slice-6-next markers all matched disk. **No drift found.**

## 2. Session narrative

Andy opened with "lets work" on the Slice-5 closing handoff, then picked **full Slice 6 including v2 retirement** at the scope gate. Before any code I ran a thorough Explore pass + direct reads to map the full v2 surface. The trace surfaced the slice-shaping fact: **single_session has no Layer 2B** in its cone (it runs the v2 *locale-menu* resolver keyed on locale terrain + equipment pool, not race-terrain breakdown — `orchestrator.py` single_session path), so it structurally **cannot** produce a `TrainingSubstitution` (which is derived entirely from `terrain_by_discipline`). "Full v2 retirement" therefore forces a decision about single_session's modality section.

Per Trigger #1 I put 2 decisions to an AskUserQuestion gate (options + tradeoffs + recommendation + gut check) and presented the proposed per-phase render design. Andy's picks (§7): **(1)** single_session **drops its modality section entirely** (true full retirement — its `effective_pool` + discipline coverage already carry the raw availability signal; keeping v2 for one entry point would preserve the hardcoded `_MODALITY_OPTIONS_PER_DISCIPLINE` dict the re-model set out to kill); **(2)** **full retirement in one session** (ratified ceiling break).

A second wiring fact shaped the plan_refresh work: **plan_refresh uses tier-specific render functions** (`plan_refresh_t1/t2/t3.py`), NOT per_phase's `render_user_prompt` (the Slice-5 handoff's "per_phase renderer" note was imprecise). I threaded `training_substitution_payload` through `llm_layer4_plan_refresh` → all 3 tier `render_user_prompt`s, each rendering via the shared `_format_training_substitution_per_phase` helper imported from `per_phase.py`.

## 3. File-by-file edits

### Runtime (contract change)
- **`layer4/context.py`** — DELETED the v2 types `ModalityOption`, `ModalityRecommendation`, `ModalityCoachingFlag`, `Layer2ModalityPayload` (+ the stale Slice-5 "additive alongside v2" comment in the `TrainingSubstitutionFlag` docstring).
- **`layer2_modality/resolver.py`** — DELETED entirely (`resolve_best_fit_modality` + `_MODALITY_OPTIONS_PER_DISCIPLINE` + `ClusterLocaleInput` + `ModalityOptionDef` + the menu/flag helpers). The surviving `Layer2ModalityInputError` (reused by `resolve_training_substitution`) MOVED into `substitution.py`.
- **`layer2_modality/substitution.py`** — added `class Layer2ModalityInputError(ValueError)`; dropped the `from .resolver import` line; dropped the stale "additive alongside the v2 `Layer2ModalityPayload`" docstring line.
- **`layer2_modality/__init__.py`** — rewritten: exports `Layer2ModalityInputError` + `resolve_training_substitution` from `.substitution` only.
- **`layer4/per_phase.py`** — `_format_modality_recommendations_per_phase(Layer2ModalityPayload)` → `_format_training_substitution_per_phase(TrainingSubstitutionPayload)` (compact `=== Best-fit training substitution (per discipline) ===` idiom: race craft + candidate crafts + `pct × fidelity` terrain emphasis + untrainable terrain + flags + the natural-language cite line). `render_user_prompt` + `synthesize_phase` params `layer2_modality_payload` → `training_substitution_payload`; call sites updated; import swapped (`Layer2ModalityPayload` → `TrainingSubstitutionPayload`).
- **`layer4/plan_create.py`** — param `layer2_modality_payload` → `training_substitution_payload` through `_run_pattern_a_engine` signature + the 2 `synthesize_phase` call sites + the `llm_layer4_plan_create` entry + the engine call; import swapped.
- **`layer4/plan_refresh.py`** — `llm_layer4_plan_refresh` gains `training_substitution_payload`; threaded into the `tier_module.render_user_prompt(...)` dispatch; import +`TrainingSubstitutionPayload`.
- **`layer4/plan_refresh_t1.py` / `_t2.py` / `_t3.py`** — each `render_user_prompt` gains `training_substitution_payload` kwarg + renders the section (via the shared per_phase helper) before `=== Retry context ===`; import +`TrainingSubstitutionPayload` + `from layer4.per_phase import _format_training_substitution_per_phase`.
- **`layer4/race_week_brief.py`** — DELETED `_render_modality_section_race_week_brief` + its call; dropped `layer2_modality_payload` from `_render_user_prompt` + `llm_layer4_race_week_brief` + the threading; dropped the import. (Slice-5 substitution renderer + threading retained.)
- **`layer4/single_session.py`** — DELETED `_render_modality_section_single_session` + its call; dropped `layer2_modality_payload_for_locale` from `_render_user_prompt` + the entry; dropped the import. **single_session now renders NO best-fit section.**
- **`layer4/orchestrator.py`** — dropped both `resolve_best_fit_modality` calls (full-cone + single_session blocks) + the `layer2_modality_payload` field on `_UpstreamFullCone` + the single_session `layer2_modality_payload_for_locale` var/thread; threaded `cone.training_substitution_payload` into plan_create (swap) + plan_refresh (add); dropped `layer2_modality_payload=` from race_week_brief; dropped imports (`ClusterLocaleInput`, `resolve_best_fit_modality`, `Layer2ModalityPayload`).
- **`layer4/hashing.py`** — `plan_create_key`: `layer2_modality_hash` → `training_substitution_hash` (swap). `plan_refresh_key`: +`training_substitution_hash` (net-new). `single_session_synthesize_key`: −`layer2_modality_locale_hash`. `race_week_brief_key`: −`layer2_modality_hash` (kept `training_substitution_hash`).
- **`layer4/cached_wrappers.py`** — plan_create swap (param/hash/key/thread), plan_refresh add (param/hash/key/thread), single_session remove, race_week_brief remove v2; import −`Layer2ModalityPayload`.

### Tests
- **`tests/test_layer2_modality.py`** — DELETED (the v2 resolver suite).
- **`tests/test_layer4_hashing.py`** — plan_create v2 hash-slot tests → `training_substitution_hash`; ADDED plan_refresh `training_substitution_hash` none==empty + set-distinguishes + parametrize entry; DELETED single_session + race_week v2 modality-hash tests + their parametrize entries + the race_week independence test.
- **`tests/test_layer2_substitution.py`** — import `Layer2ModalityInputError` now from `layer2_modality` (was `layer2_modality.resolver`).

### Spec (in-place amend — form-refresh-C marker precedent, no version bump)
- **`BestFitModality_Spec_v4.md`** — Status line (Slice 6 ✅ / re-model complete); §9 Slice-6 as-built note (3 key-shape changes + one-time invalidation); §12 Slice 6 → SHIPPED with full as-built + gate decisions + file list + test delta.

### Bookkeeping
- `CURRENT_STATE.md` (last-shipped prepended; focus → re-model complete + next-move menu; Layer 2 + Layer 4 rows; Tests 1680 → **1631**); `CARRY_FORWARD.md` (re-model section header → COMPLETE + Slice 6 ✅ entry; the stale BM-3 §5.0 walkthrough scenario marked SUPERSEDED with replacement-walk pointer); this handoff.

## 4. Code / tests results

- **Full suite `python -m pytest tests/`: 1631 passed / 16 skipped** (−49 vs Slice 5's 1680). The delta is fully accounted for: deleting `tests/test_layer2_modality.py` (the v2 resolver suite) + the hashing-test migration (v2 slots removed, plan_refresh slot added). **Zero regressions.**
- **v2-surface grep is clean repo-wide** (`Layer2ModalityPayload`, `resolve_best_fit_modality`, `_MODALITY_OPTIONS_PER_DISCIPLINE`, `_render_modality_section*`, `_format_modality_recommendations_per_phase`, `layer2_modality_hash`, `layer2_modality_payload`, `layer2_modality_locale_hash`, `ClusterLocaleInput`, `ModalityOptionDef`, `Modality{Option,Recommendation,CoachingFlag}` — no matches outside the unrelated `AccommodationModality` union).
- Import sanity: all of `layer4.*` + `layer2_modality.*` import cleanly.
- Three cache-key shape changes → one-time invalidation per entry point on first deploy (Spec v4 §9 Slice-6 as-built). No new eviction helper — the substitution payload derives from the Layer 1 + 2B cone already covered.
- **Sandbox interpreter note:** run `python -m pytest tests/`, NOT bare `pytest` (the `~/.local/bin/pytest` shim uses a python without the deps/path). Deps install: `python -m pip install -r requirements.txt --ignore-installed blinker` then `python -m pip install pytest`.

## 5. Manual §5.0 verification steps

No new §5.0 scenario *required* (prompt cite-material change only; no schema, no route, no user-facing form). The prior BM-3 §5.0 walkthrough scenario is now **superseded** (CARRY_FORWARD.md — its v2 sections no longer render). Replacement walk worth doing once in the auto-fire window: run a plan_create (`/plans/v2/new`, PGE 2026, `plan_start_date=2026-04-01`) and confirm the **`=== Best-fit training substitution (per discipline) ===`** section renders in the per-phase prompt after `=== Race + locale + equipment ===` / before `=== Schedule ===`; run `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026,7,3), cache=Layer4Cache(InMemoryCacheBackend()))` and confirm the **`# Best-fit training substitution (Layer 2 substitution resolver)`** section renders before `# Race-day fueling tier (2E)`; drive a single_session (`/workouts/build`) and confirm **no** best-fit section appears (no Layer 2B in its cone). ~$0.50–$1.00 real-LLM across the routes.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
The best-fit re-model has **no remaining build slices**. Strongest next move: the deferred **R6 clean discipline-ID renumber + the two collapses** (kayak D-008a/b → "Kayaking"; mtn-running D-022/D-023 → "Mountain Running"). R6's gating rationale was "terrain axis consumed" — Slice 4 captured the 2B consume, Slice 5 the resolver consume, and **Slice 6 the full renderer consume**, so the gate is now fully satisfied. ~40 code/SQL/test files + 6 xlsx sheets + Neon rows + specs in lockstep; prune dead `DISCIPLINE_DISPLAY_NAMES` entries + add survivor labels. Own session (renumber-class blast radius + silent-mismap risk). Trigger #3 (cross-layer) + #2 (vocab).

### 6.2 Re-model follow-ons / known limitations (open, low-priority)
- **`craft_substitution` flag is LLM-side, not deterministic** (no `discipline_id → craft-token` map). If a deterministic flag is wanted, add a small race-craft-derivation map (NOT the §14 family table).
- **§6 skill-gating is not applied** in the substitution node (no skill→terrain or skill→craft map on disk). The untrainable-terrain narrative carries the "can't train X" signal.
- **Craft family grouping (§14) deferred** (all owned crafts handed to the LLM). Watch real plan/brief output for over-substitution (e.g. recommending a bike for a paddle leg); if it happens, add a coarse deterministic craft-family proximity table (§14 escape hatch — Trigger #2/#5).
- **Fidelity thresholds** (`_UNTRAINABLE_FIDELITY_FLOOR = 0.25`, `_LOW_FIDELITY_THRESHOLD = 0.60`) are `substitution.py` module constants; tune if output misclassifies.
- **single_session has no best-fit section by design.** If on-demand workouts later want locale-aware modality guidance, that's a net-new locale-scoped variant (NOT the retired v2 menu) — its own design + gate.

### 6.3 Other carried items
- **DEPLOY (owed):** K3 equipment ETL on Neon — `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql`; confirm `populate_skill_capability_toggles.sql` applied.
- Deferred form feedback (Slice-1 §6.3): format vs `framework_sport`, aid-stations cadence, mandatory-gear → pack-weight, injury Side-field drop, schedule simplification.
- M-7 multi-locale cluster ingestion; #8 locales→locations rename; BM-5 equipment-canon tail; 2B-1 (`relevant_discipline_ids TEXT[]` gap-rule-side relevance).

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `BestFitModality_Spec_v4.md` (§12 — re-model now complete; §9 as-built) 6. `./scripts/verify-handoff.sh`.

**Sandbox note:** `python -m pip install -r requirements.txt --ignore-installed blinker` then `python -m pip install pytest`, then run **`python -m pytest tests/`** (NOT bare `pytest`). Full suite = 1631.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **QW** | Session scope = full Slice 6 incl. v2 retirement | Andy | Picked at the scope gate (over a 6a/6b split). |
| **S6-1** | single_session **drops its modality section** (full v2 retirement) | Andy at gate | single_session has no Layer 2B → can't produce a `TrainingSubstitution`; its `effective_pool` + discipline coverage already carry the raw availability signal; keeping v2 for one entry point would preserve the hardcoded `_MODALITY_OPTIONS_PER_DISCIPLINE` dict the re-model set out to kill. |
| **S6-2** | **Full retirement in one session** (ratified ceiling break) | Andy at gate | Wanted v2 gone in one shot; ~12 code files precedented by the prior caller-side ceiling-break sessions. |
| **S6-3** | per-phase render design (compact `=== … ===` idiom, race-craft + candidates + `pct × fidelity` emphasis + untrainable + flags) | Andy at gate (Trigger #1 prompt body) | Mirrors the Slice-5 brief section in per_phase's existing idiom; reused by all 3 plan_refresh tiers via the shared helper. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| v2 types deleted from `layer4/context.py` | ✅ grep clean (`Layer2ModalityPayload`/`ModalityOption`/`ModalityRecommendation`/`ModalityCoachingFlag` absent) |
| `layer2_modality/resolver.py` deleted; `Layer2ModalityInputError` in `substitution.py` | ✅ `git rm` + `class Layer2ModalityInputError` at `substitution.py:37`, raised at `:79` |
| `_format_training_substitution_per_phase` replaces v2 renderer | ✅ `layer4/per_phase.py` (def + `render_user_prompt`/`synthesize_phase` threading) |
| plan_create threads `training_substitution_payload` | ✅ `plan_create.py` (`_run_pattern_a_engine` + entry) + `cached_wrappers.py` + `orchestrator.py` |
| plan_refresh threads it through all 3 tiers | ✅ `plan_refresh.py` dispatch + `_t1`/`_t2`/`_t3` `render_user_prompt` + `cached_wrappers.py` |
| race_week_brief + single_session v2 renderers/params removed | ✅ `race_week_brief.py` + `single_session.py` (grep clean) |
| cache keys: plan_create swap / plan_refresh add / single_session + race_week remove v2 | ✅ `hashing.py` (4 key fns) + `cached_wrappers.py` |
| orchestrator: both `resolve_best_fit_modality` calls + cone field removed; substitution threaded to plan_create/plan_refresh | ✅ `orchestrator.py` |
| `tests/test_layer2_modality.py` deleted; `test_layer4_hashing.py` migrated | ✅ |
| full suite 1631 / 16 skipped, zero regressions; v2 grep clean repo-wide | ✅ |
| Spec v4 §9/§12 + status amended (Slice 6 ✅, re-model complete) | ✅ `BestFitModality_Spec_v4.md` |
| `CURRENT_STATE` last-shipped + focus + Layer 2/4 rows + Tests → 1631 | ✅ |
| `CARRY_FORWARD` re-model section → COMPLETE + BM-3 §5.0 scenario superseded | ✅ |

## 9. Files shipped this session

**Substantive (code):** `layer4/context.py`, `layer4/per_phase.py`, `layer4/plan_create.py`, `layer4/plan_refresh.py`, `layer4/plan_refresh_t1.py`, `layer4/plan_refresh_t2.py`, `layer4/plan_refresh_t3.py`, `layer4/race_week_brief.py`, `layer4/single_session.py`, `layer4/orchestrator.py`, `layer4/hashing.py`, `layer4/cached_wrappers.py`, `layer2_modality/substitution.py`, `layer2_modality/__init__.py`; **deleted** `layer2_modality/resolver.py`. **Substantive (tests):** `tests/test_layer4_hashing.py`, `tests/test_layer2_substitution.py`; **deleted** `tests/test_layer2_modality.py`. **Spec:** `aidstation-sources/BestFitModality_Spec_v4.md`. **Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

## 10. Carry-forward updates

- **Re-model Slice 6 shipped — the best-fit re-model is COMPLETE.** `resolve_training_substitution` is the sole best-fit node; the v2 `Layer2ModalityPayload` path is fully retired. Substitution payload threaded into race_week_brief + plan_create + plan_refresh (all 3 tiers); single_session intentionally carries no best-fit section.
- **No remaining best-fit build slices.** Next forward move is the deferred R6 discipline-ID renumber + the two collapses (now unblocked — terrain axis fully consumed).

**End of handoff.**
