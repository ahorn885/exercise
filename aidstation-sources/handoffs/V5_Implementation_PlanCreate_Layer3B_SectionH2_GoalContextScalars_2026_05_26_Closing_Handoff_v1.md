# Layer 3B §H.2 deployed-shape gap — scalar goal-context capture (Slice 1 of 2) — Closing Handoff

**Session:** Andy: "let's work. we should continue to focus on the designed-but-not-implemented blockers." Walked the three deferred blocker slices from the 504-timeout handoff §6.2 against code+spec: **#1 `Layer4ShapeInfeasibleError`** (fully designed in `Layer4_Spec §10.2`, zero code), **#4 the 3C/3D/3.5 HITL gate** (spec-first — no per-node specs exist; stop-and-ask #4), **#5 the L3B §H.2 deployed-shape gap** (partially patched). Andy picked **#5**, then asked for a plain-language explanation, then chose **"Full §H.2 (all goal fields)"**, then **"Slice 1 now (4 scalars)"** + **"add the numeric `race_pack_weight_kg` column."** This session shipped Slice 1: the scalar §H.2 goal fields end-to-end.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_504Timeout_CronBudget_Iter1SeamCache_2026_05_26_Closing_Handoff_v1.md`
**Branch:** `claude/v5-implementation-blockers-PV5LH`
**Status:** ~8 substantive code files + 1 spec amend + 3 test files + bookkeeping. Full suite **1746 passed / 16 skipped** (+13 over the 1733 baseline). **No code blocker; one owed Neon migration (`python init_db.py`) + redeploy.**

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` clean; working tree clean on the branch. Spot-checked the predecessor (504-timeout) §8 claims — all present (`_CRON_WALL_CLOCK_BUDGET_S = 240` in `routes/plan_create.py`; `compute_seam_review_cache_key` in `layer4/hashing.py`; `_SEAM_CACHE_PHASE_IDX_BASE = 1000` in `layer4/plan_create.py`). That work shipped on branch `claude/504-timeout-investigation-PB5oM`; this branch was clean. No drift.

## 2. The problem (plain language) + diagnosis

Layer 3B judges *"is this goal realistic in this timeline, and what should we flag?"* It was **designed to read the athlete's §H.2 goal fields** — its code hard-requires `goal_outcome` and uses `first_time_at_distance` / `previous_attempts` / `time_goal` / `race_pack_weight_kg` in the goal-context prompt block (`layer3b/builder.py:548-593`) + two HITL triggers (`Layer3_3B_Spec §6.1`). But the **deployed `race_events` row stored none of `goal_outcome` / `first_time_at_distance` / `previous_attempts` / `time_goal` / `race_pack_weight_kg`** (no columns; `RaceEventPayload` didn't carry them; the orchestrator passed none). To keep generation from crashing on the required `goal_outcome`, PR #178's band-aid hardcoded `goal_outcome="Finish"` in `layer3b/cached_wrapper.py`.

**Impact:** (1) every athlete was treated as a finisher → viability skewed optimistic (a "podium in 4 weeks" goal that should flag `unrealistic-as-stated` looked achievable once silently downgraded to "Finish"); (2) two of 3B's four HITL flags could **never fire** — `3B.first_time_competitive_goal` (needs `first_time_at_distance` + a competitive goal) and `3B.dnf_recurrence_risk` (needs `previous_attempts`); (3) periodization could be miscalibrated (competitive goals warrant more Build/Peak). **UX:** the race-event form never asked the athlete their goal — it guessed "Finish."

Also surfaced: `estimated_duration_hr` + `race_terrain` are already on `RaceEventPayload` but **never reached 3B's prompt** (the builder reads them from kwargs, and the orchestrator passed none); only `distance_km` had a builder fallback.

## 3. File-by-file edits (Slice 1 = the 4 scalar goal fields)

### 3.1 `init_db.py` — schema (migration)
4 idempotent `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS` after the FormRefresh A1 `estimated_duration_hr`/`primary_metric` block: `goal_outcome TEXT NULL CHECK (... IN 'Finish','Compete mid-pack','Podium')` (mirrors `layer3b.builder._VALID_GOAL_OUTCOMES`), `first_time_at_distance BOOLEAN NULL`, `time_goal TEXT NULL`, `race_pack_weight_kg NUMERIC NULL CHECK (>= 0)`. All nullable → no backfill; fresh DB converges via the same ALTERs (matches the `estimated_duration_hr` precedent, not the CREATE TABLE).

### 3.2 `layer4/context.py` — `RaceEventPayload`
4 fields after `included_discipline_ids`: `goal_outcome: Literal["Finish","Compete mid-pack","Podium"] | None`, `first_time_at_distance: bool | None`, `time_goal: str | None (max_length=200)`, `race_pack_weight_kg: Decimal | None (ge=0)`. `previous_attempts` intentionally NOT added (Slice 2).

### 3.3 `race_events_repo.py`
- New `VALID_GOAL_OUTCOMES = ("Finish","Compete mid-pack","Podium")` (lock-step with builder + DB CHECK).
- `load_race_event_payload`: 4 columns added to the SELECT + mapped onto the payload (`first_time_at_distance` bool-coerced).
- `get_race_event` (form pre-fill): 4 columns added to the SELECT; `race_pack_weight_kg` added to the Decimal→float coercion loop.
- `create_race_event` + `update_race_event`: 4 keyword-only kwargs (defaulting None) + INSERT/UPDATE column+value additions + a `goal_outcome not in VALID_GOAL_OUTCOMES` raise (mirrors the `primary_metric` guard). `etl_version_set` stays the last INSERT value, so the existing "last param" test holds.

### 3.4 `layer4/orchestrator.py` — thread into 3B
Before the `llm_layer3b_goal_timeline_viability_cached` call, build `section_h2_kwargs` from `target_race_event` (event-mode only): `goal_outcome`, `first_time_at_distance`, `time_goal`, `race_pack_weight_kg` (float), plus `race_duration_hr` (from `estimated_duration_hr`) + `race_terrain` (`[e.terrain_id for e in ...] or None`). Splatted with `**section_h2_kwargs`. `race_distance_km` deliberately omitted (builder already falls back to `payload.distance_km`). No-event mode → empty dict → wrapper's no-event resolution unchanged.

### 3.5 `layer3b/cached_wrapper.py`
Comment-only: the `_DEFAULT_EVENT_GOAL_OUTCOME = "Finish"` band-aid header now says the capture form shipped 2026-05-26 + the fallback fires only for legacy/uncaptured (NULL) rows (was: "the capture form does not exist yet"). The fallback logic is unchanged — correct now that the orchestrator threads the real value.

### 3.6 Templates — capture UI
A "Goal" section (full-width heading + 4 fields) added after the elevation field in BOTH `templates/profile/race_event_edit.html` (var `race`) and `templates/onboarding/target_race.html` (var `target`): `goal_outcome` `<select>` (—/Finish/Compete mid-pack/Podium, hardcoded — stable closed set), `first_time_at_distance` tri-state `<select>` (—/Yes/No), `race_pack_weight_kg` number input, `time_goal` text input.

### 3.7 Routes — parse + evict
- `routes/race_events.py`: imported `VALID_GOAL_OUTCOMES`; 3 new parse helpers (`_parse_goal_outcome`, `_parse_first_time_at_distance` tri-state, `_parse_pack_weight_kg` ≥0); wired into `new_race` (create) + `update_race` (update); folded the 4 goal-field diffs into `periodization_changed` (a goal change re-runs 3B → shape can shift → periodization-grade eviction). `time_goal` uses the existing `_parse_str`.
- `routes/onboarding.py` `target_race_save`: imported the 3 helpers; parsed the 4 fields; passed them to BOTH the update + create branches; mirrored the periodization-eviction fold.

### 3.8 `Athlete_Onboarding_Data_Spec_v6.md §H.2` (in place)
Added a dated "Goal-context amendment 2026-05-26" note + a 4-row field table (Goal Outcome / First Time At Distance / Time Goal / Race Pack Weight) after the D-66 amendment table; flagged `Previous Attempts` as the follow-on slice; reconciled the storage note (pack-weight magnitude is now the numeric column, not folded into `mandatory_gear_text`). In-place amend (matches the D-66 in-place amendment + recent Layer-spec in-place precedent — no `_v7` created).

### 3.9 Tests (+13)
- `tests/test_layer4_orchestrator.py`: `_queue_target_race_event` helper extended with the 4 goal kwargs + the fake race row gains the 4 keys; new `test_section_h2_goal_fields_thread_to_3b` (asserts goal_outcome/first_time/time_goal/pack_weight + race_duration_hr/race_terrain reach the 3B mock) + `test_section_h2_goal_fields_absent_in_no_event_mode`.
- `tests/test_race_events_repo.py`: `_race_row` helper gains the 4 keys (default None); new `TestSectionH2GoalContext` (7: create/update pass-through + invalid-goal_outcome raise ×2 + load populate/default + get pack-weight float coercion).
- `tests/test_routes_race_events.py`: new `TestParseGoalContextHelpers` (4: goal_outcome valid/blank-invalid, first_time tri-state, pack_weight parsing).

## 4. Code / tests

Full suite **1746 passed / 16 skipped** in `/tmp/venv` (+13 over 1733: +2 orchestrator, +7 repo, +4 route helpers; nothing removed). `py_compile` clean on all 7 changed Python files. (Container: Neon egress blocked, PyPI works, `pytest` not in `requirements.txt` — `CLAUDE.md` Environment quick-reference.)

## 5. Owed action (Andy's hands)

**`python init_db.py` against Neon, then redeploy.** The 4 `ADD COLUMN IF NOT EXISTS` are idempotent (safe to re-run; stacks onto any prior owed init_db runs). Until applied, the live `race_events` lacks the columns → the form submit + payload load would error / the new behavior is inert (legacy NULL → "Finish" fallback). No data backfill needed. **No new env var.** After deploy: the form captures goal_outcome etc.; 3B reads them; `3B.first_time_competitive_goal` is reachable.

## 6. Next session pointers

### 6.1 Slice 2 — `previous_attempts` (the remaining §H.2 half)
Structured: a list of `{outcome, dnf_cause}` records (`dnf_cause` vocab pinned in `Layer3_3B_Spec §6.1`: quad_failure→12, nutrition_blowup→4, injury_during_event→16, weather/timeout→4, other→8 recovery weeks). Needs: a `race_events.previous_attempts JSONB` column (shape like `race_terrain`), `RaceEventPayload.previous_attempts`, repo serialize/hydrate, a **repeating sub-form** (heaviest piece — model on `_race_terrain_editor.html`), route parse (`race_terrain[N][...]`-style indexed fields), orchestrator threading (`previous_attempts` is already a builder kwarg). **Unblocks `3B.dnf_recurrence_risk`** — the last starved HITL flag. After it lands, L3B-P-3 (tighten the evidence_basis mode-discriminator from warn → `Layer3BOutputError`) becomes safe.

### 6.2 The other two designed-but-unbuilt blockers (untouched this session)
- **#1 `Layer4ShapeInfeasibleError`** — fully designed (`Layer4_Spec §10.2`: 4 pure-function detection classes `schedule_volume_infeasible` / `discipline_frequency_infeasible` / `skill_acquisition_infeasible` / `cumulative_load_injury_infeasible`, tolerance defaults, test scenarios TS-10..TS-13), **zero code**. Evaluates after `phase_structure_from_3b()` and before per-phase synthesis. One OPEN routing decision (§10.2/C3/§12.3): inline athlete error now vs the 3D gate — the §14-retro recommends inline now (3D as a future backup), and since 3D isn't built, inline is the only implementable path. Self-contained, one PR.
- **#4 3C/3D/3.5 HITL gate** — spec-first (no `Layer3_3C/3D/3.5` spec files exist); stop-and-ask trigger #4.

### 6.3 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items (L3B-P-2 now reflects the scalar-half close).
4. This handoff.
5. `./scripts/verify-handoff.sh`.
**Before a live plan-gen walk:** confirm Andy's profile has `body_weight_kg` + `height_cm` (the 2E gate) and run the owed `init_db.py`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Close §H.2 gap (#5) this session over `Layer4ShapeInfeasibleError` (#1) / HITL gate (#4) | Andy | (after a plain-language explanation of the gap's problem/impact/UX) |
| 2 | Full §H.2 scope, sliced: scalars now / `previous_attempts` next | Andy ("Full §H.2" + "Slice 1 now") | The capture path is ~8 files for ANY field set; the efficient fault line is scalars vs the structurally-complex `previous_attempts` (own JSONB shape + repeating UI + a different HITL flag). |
| 3 | Add a numeric `race_pack_weight_kg` column (diverges from the spec's "pack weight folds into mandatory_gear_text") | Andy ("Add numeric column") | 3B reads it as a float; spec §H.2 reconciled in the amend. |
| 4 | Accept the >5-file count for Slice 1 | Andy ("~8 files") | One coupled capture surface (schema→payload→repo→2 forms→2 routes→consume); splitting horizontally would ship a session with zero athlete-visible change, fighting the "ship working code" rule. |
| 5 | Goal-field edits → periodization-grade eviction | Claude | A goal change flips the 3B cache key → 3B re-runs and the periodization shape can move; periodization-grade is the correct breadth (mirrors `estimated_duration_hr`). |
| 6 | `goal_outcome` as a `Literal` on the payload + a CHECK + a repo guard | Claude | DB CHECK is the source of truth; Literal gives a typed contract; repo guard fails loud on a bad caller. |

## 8. Session-end verification (Rule #10)

| Check | File:anchor | Method | Result |
|---|---|---|---|
| 4 `ADD COLUMN IF NOT EXISTS` (goal_outcome/first_time/time_goal/race_pack_weight_kg) | `init_db.py` (after `estimated_duration_hr` ALTER) | read | ✅ |
| 4 fields on `RaceEventPayload` | `layer4/context.py` (after `included_discipline_ids`) | read | ✅ |
| `VALID_GOAL_OUTCOMES` + 4 cols in create/update/load/get | `race_events_repo.py` | read | ✅ |
| `section_h2_kwargs` built + `**`-splatted into the 3B call | `layer4/orchestrator.py` | read | ✅ |
| "Finish" band-aid comment updated (form shipped) | `layer3b/cached_wrapper.py` | read | ✅ |
| "Goal" section in both forms | `templates/profile/race_event_edit.html`, `templates/onboarding/target_race.html` | read | ✅ |
| 3 parse helpers + wired into create/update/onboarding + periodization-evict fold | `routes/race_events.py`, `routes/onboarding.py` | read | ✅ |
| §H.2 goal-field table amended in place | `Athlete_Onboarding_Data_Spec_v6.md` | read | ✅ |
| +13 tests green; full suite 1746/16 | `tests/test_layer4_orchestrator.py`, `tests/test_race_events_repo.py`, `tests/test_routes_race_events.py` | pytest (`/tmp/venv`) | ✅ |
| `CURRENT_STATE.md` last-shipped = this handoff; 504-timeout demoted; D-73 follow-on note updated | `CURRENT_STATE.md` | read | ✅ |
| `CARRY_FORWARD.md` L3B-P-2 reflects scalar-half close + owed migration + Slice 2 | `CARRY_FORWARD.md` | read | ✅ |

## 9. Files shipped this session

**Substantive (code, 7):** `init_db.py`, `layer4/context.py`, `race_events_repo.py`, `layer4/orchestrator.py`, `layer3b/cached_wrapper.py`, `templates/profile/race_event_edit.html`, `templates/onboarding/target_race.html`, `routes/race_events.py`, `routes/onboarding.py` (9 incl. the 2 route files — over the 5-file ceiling; Andy approved the coupled capture-path width).
**Spec:** `Athlete_Onboarding_Data_Spec_v6.md` (§H.2 in-place amend).
**Tests:** `tests/test_layer4_orchestrator.py`, `tests/test_race_events_repo.py`, `tests/test_routes_race_events.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
