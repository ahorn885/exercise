# V5 Implementation — Layer 3D HITL Gate: Slice 2 + Slice 3 Kickoff (#213)

**Date:** 2026-06-21
**Status of #213:** Slice 1 **MERGED** (PR #850 → `main`). This handoff is the next-thread starting point for **Slice 2** (feasibility detectors) and **Slice 3** (revise cascade + staleness re-fire).
**Predecessor handoff:** `handoffs/V5_Implementation_Layer3D_Slice1_Foundation_213_2026_06_21_Closing_Handoff_v1.md`
**Spec:** `specs/Layer3D_Spec.md` (the gate, 14 sections) + `specs/Layer4_Spec.md` §10.2 (the re-scoped infeasibility detectors).

---

## 1. Where Slice 1 left it (merged, live)

The deterministic gate (`layer3d/gate.py`) aggregates the upstream HITL items (2A/2D/2E/3B), the orchestrator parks non-green plans at `needs_review`, and the review screen (read + acknowledge) is wired. What's **not** built yet: the two pre-synthesis feasibility detectors, and the revise cascade. Both were deferred by design with no contract change required.

## 2. Session-start read order (Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — lead entry (Slice 1 merged) + Layer-3 rows
3. `CARRY_FORWARD.md`
4. This handoff
5. `./scripts/verify-handoff.sh`
6. Then read `specs/Layer3D_Spec.md` §5.2 / §5.3 (Slice 2) + §11.2 (Slice 3 staleness) and `layer3d/gate.py` end-to-end before writing code.

**Env notes (verified this session):** the container reaches only a **cold Neon** — `import app` (pulled in transitively by `routes/plan_create`) blocks on `init_db.init_postgres()` until Neon wakes, so an *isolated* `pytest tests/test_layer3d_*.py` can appear to hang; **run the full `tests/` suite** (it warms the DB once) or expect a slow first import. `pip install -r requirements.txt pytest` first (the suite now needs `pyotp`, added by main's MFA work). Full suite at Slice 1 merge: **green**.

## 3. Slice 2 — the two feasibility detectors (the real work) + Layer 4 §10.2

### 3.1 Where they drop in (no contract change)

`layer3d/gate.py`, in `evaluate_layer3d_gate()`, at the **marked call site** (search the comment `# 4. Feasibility detectors (§5.2/§5.3) — deferred to the next slice`). They append `GateItem`s to `items` **before** the de-dup pass. The §3 signature already carries everything they need: `layer1_payload`, `layer2c_payloads`, `plan_start_date`, `total_weeks`, `race_event_payload`.

Implement two functions in `layer3d/gate.py` and call them at that site:

```
phase_structure = phase_structure_from_3b(layer3b_payload, plan_start_date, total_weeks=total_weeks)
items += detect_injury_pool_empty(phase_structure, layer2a_payload, layer2c_payloads, layer2d_payload)   # blocker(s)
item  = detect_schedule_volume_under_target(phase_structure, layer2a_payload, layer1_payload)             # warning | None
if item: items.append(item)
```

Helpers that already exist (no need to rebuild):
- `phase_structure_from_3b` — `layer4/phase_structure.py:178`
- `weekly_capacity_hours(layer1_payload)` — `layer4/validator.py:361` (Σ enabled §K daily windows, capped by `weekly_hours_target`)
- `phase_volume_bands_hours(...)` — `layer4/validator.py:285` (phase target band low/high for the dominant discipline)

### 3.2 `detect_injury_pool_empty` (blocker) — §5.2

Per phase, after applying 2D exclusions to the 2C pool:
- **Strength pool empty:** if a phase needs strength (a 2A strength-weighted discipline with a non-zero phase band) and the post-exclusion **distinct usable strength exercises `< 3`** (Andy's v1 floor — `Layer3D_Spec` §5.2), raise a blocker `GateItem` for that phase. `evidence` carries `{phase, usable_count, excluding_2d_ids}`; `revise_target` → the Layer 1 §B injury record (`"profile.injuries"`) or the 2A discipline-inclusion toggle (`"profile.disciplines"`).
- **Cardio modality banned:** if 2D excludes the only available cardio modality for an included discipline, raise a blocker for that discipline.
- `severity="blocker"`, `can_acknowledge=False`, `source="3D_feasibility"`. The pool source is 2C `effective_pool` minus 2D `excluded_exercises` (the `ExerciseRisk.exercise_id`s with `verdict=='exclude'`).

### 3.3 `detect_schedule_volume_under_target` (warning) — §5.3

Compute bounded available weekly hours (`weekly_capacity_hours(layer1_payload)`) vs the phase target low band (`phase_volume_bands_hours(...)` low edge for the dominant discipline). If available `< target_low`, emit **one** warning `GateItem` (the worst/most-constrained phase headlines it; others listed in `evidence`). `severity="warning"`, `can_acknowledge=True`. Coaching-voice message per §5.3 ("Your schedule gives about {avail} h/week; this block targets {low}–{high} h. The plan will be built to the time you have, but expect it to under-prepare you…"). **Does NOT block** — Layer 4 already clamps volume to capacity; 3D just surfaces the trim.

### 3.4 Layer 4 §10.2 — IMPORTANT correction to the predecessor handoff

The predecessor said Slice 2 should "delete the two retired Layer-4 detectors (`discipline_frequency_infeasible`, `skill_acquisition_infeasible`)." **Verified this session: those detectors + `Layer4ShapeInfeasibleError` were never implemented in code — they are spec-only** (`grep -rn "ShapeInfeasible\|skill_acquisition\|discipline_frequency" --include=*.py` returns nothing). So there is **nothing to delete in code.** The §10.2 re-scope (`specs/Layer4_Spec.md:1389`) is already written. The only Layer-4 code action, if any, is an optional **defensive raise** on the injury-pool-empty shape if synthesis is somehow reached on it (§10.2 / §13) — but since 3D now gates pre-synthesis, this is defense-in-depth, not required for Slice 2 to function. Decide with Andy whether to add it or leave the gate as the sole guard.

### 3.5 Tests
`tests/test_layer3d_gate.py` already covers the aggregation TS rows; add the §5.2/§5.3 scenarios: **TS-3D-5** (injury empties a phase strength pool → 1 `3D_feasibility` blocker, evidence carries phase + post-exclusion count + 2D ids), **TS-3D-6** (all-running-banned removes a discipline's only cardio modality → blocker), **TS-3D-7** (available 4 h/wk vs Build 10–12 h → 1 warning → acknowledge → green; plan still generates). Build the upstream fixtures with the same minimal-payload pattern already in that file.

## 4. Slice 3 — revise cascade + staleness re-fire (highest-risk; the spec's gut-check flags it)

### 4.1 Revise cascade (§11 / §6.3)
Today the review screen (`templates/plan_create/review.html`) shows a blocker's `revise_target` as **text** ("Fix via: …") — no in-place edit. Slice 3 wires `[Fix this]` → the Layer 1 edit surface the `revise_target` names → on save, the **existing partial-update invalidation cascade** (`Control_Spec` §4) re-runs the affected layers → the gate re-aggregates against fresh payloads. A `GateResolution(kind='revised')` is recorded; per `resolved_status` (already implemented) a revised item that **re-surfaces with the same `item_key` reverts to `pending`** (the edit didn't fix it), and one that disappears clears. The riskiest piece: the invalidation cascade "has never been driven from an athlete-facing mid-plan-creation edit" (spec §14) — give it the most testing; if flaky, a blocker could be un-fixable from the screen.

### 4.2 Staleness re-fire (§11.2)
The guard is `Layer3DGate.evaluated_against` (the `etl_version_set`). Current state:
- The orchestrator **already re-evaluates the gate at the real [Generate plan]** (the advance loop re-runs `orchestrate_plan_create` → `evaluate_layer3d_gate` with the stored resolutions), so a stale-green plan that recomputes non-green re-parks. That backstop exists.
- **What's missing for Slice 3:** re-evaluate on **review-screen re-entry** and on **any upstream re-run** (provider sync → 3A → 3B), comparing `evaluated_against` to the current upstream version set and recomputing the item list (resolutions surviving by `item_key`). `routes/plan_create.py:generate_from_review` currently re-checks only the *stored* gate's status, not a fresh aggregation — strengthen that (or the `plan_review` GET) to recompute when `evaluated_against` is stale. The thin spot (named, non-blocking): what *wakes* the re-eval when the athlete isn't on the screen — v1 leans on "re-check on next view / next click," with the generate-click guard as the backstop.

## 5. 3C (separate, later) — #844
Cross-node conflict detection drops in as one more `map_3c_items()` source at the same §5 step-3 aggregation point — no `Layer3DGate`/`GateItem` change. Not part of Slices 2/3.

## 6. Rule #9 verification table (for the next session's sweep)

| Claim | File | Anchor | Check |
|---|---|---|---|
| Slice 1 gate merged to main | `layer3d/gate.py` | `def evaluate_layer3d_gate(` | exists on `main` |
| Detector hook site present | `layer3d/gate.py` | `# 4. Feasibility detectors (§5.2/§5.3) — deferred` | grep |
| §5.3 helpers exist | `layer4/validator.py` | `def weekly_capacity_hours` / `def phase_volume_bands_hours` | grep |
| phase structure helper | `layer4/phase_structure.py` | `def phase_structure_from_3b` | grep |
| Layer-4 detectors are spec-only | (repo) | `grep -rn "ShapeInfeasible" --include=*.py` → 0 hits | grep |
| §10.2 re-scope in spec | `specs/Layer4_Spec.md` | `### 10.2 Shape-infeasibility detection — moved to the 3D gate` | grep |
| Review screen (Slice 1) | `routes/plan_create.py` | `def plan_review(` | grep |

## 7. Operating notes
- Slices 2 and 3 are **separate PRs** (5-file ceiling; Slice 3 especially wants its own room for the cascade testing).
- Bookkeeping rides the work PR; reconcile #213 (keep open until Slice 3 lands) + #844 (3C).
- Live-verify still owed on Slice 1 (Andy-action): plan with a known upstream HITL item → review → acknowledge → green-gated generate → "Needs review" badge.
