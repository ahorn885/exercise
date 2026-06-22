# V5 Implementation — Layer 3D HITL Gate, Slice 3: revise cascade + staleness re-fire (#213)

**Date:** 2026-06-22
**Branch:** `claude/magical-carson-snzvvh`
**Predecessor:** `handoffs/V5_Implementation_Layer3D_Slice2_FeasibilityDetectors_213_2026_06_21_Closing_Handoff_v1.md`
**Spec:** `specs/Layer3D_Spec.md` §11 (revise flow) + §11.2 (staleness re-fire) + §6.3 (resolution rule) — all synced this session.

---

## 1. What this session did

Built Slice 3 — the §11 revise cascade + §11.2 staleness re-fire — turning the parked-plan review screen from acknowledge-only (Slice 1) into an athlete-facing **fix loop**. This is the slice the spec's gut-check (§15) flagged as highest-risk: it touches the plan-generation orchestrator + advance loop.

**Andy decisions (AskUserQuestion):** re-fire via the **resumable advance loop** (not synchronous-on-GET); do it **all in one slice** (accepting the >5-file scope).

**The key de-risking finding:** 2D injury risk is a **deterministic query** (`q_layer2d_injury_risk_profile_payload(db, injuries=...)` reads the athlete's injuries fresh on every cone build), and its content hash folds into the Layer-4 synthesis cache key (`hashing.py` `layer2d_hash`). So re-running the cone after an injury edit reflects the fix **automatically** — both in the gate re-aggregation and in the generated plan. **No eviction wiring and no migration were needed** (my initial plan feared both).

## 2. The flow (as-built)

1. `[Fix this]` on a blocker/warning → POST `/review/resolve` with `kind=revise` → `resolve_review_item` records a `revised` `GateResolution`, sets `Layer3DGate.stale=True`, persists, and redirects to the Layer-1 edit surface via `_REVISE_TARGET_ENDPOINTS` (`profile.injuries`→`/injuries`; `profile.availability`→`/profile?tab=schedule`; `profile.disciplines`→`/profile?tab=athlete`; `profile.nutrition`→`/profile`; unknown/3B targets → `/profile` fallback).
2. The athlete edits + saves on that surface (existing handlers, unchanged), then returns to the plan (plans-list "Needs review" badge → `/review`).
3. `plan_review` GET sees `gate.stale` → re-gates **inline** by calling `_advance_plan_generation` → which, for a `needs_review`+stale row, calls `_regate_parked_plan` → `orchestrate_plan_create(gate_only=True)`: re-runs the cone (fresh deterministic 2D reflects the edit; LLM 3A/3B hit cache → fast) + re-aggregates the gate + persists (`stale=False`) + **always raises `Layer3DGateBlocked` even when green** (so the row re-parks, never auto-synthesizes — §11 step 3 "on green, offer [Generate plan]"). Resolutions survive by `item_key` (`load_prior_resolutions`).
4. The athlete sees the post-edit gate. If green → `[Generate plan]` → the existing `generate_from_review` → full `orchestrate_plan_create` (gate_only=False) → synthesizes the fresh plan.

**Universal staleness backstop:** the `[Generate plan]` click already ran the full orchestrate (Slice 1), which re-evaluates the gate before building — so any staleness (incl. provider-sync) is caught there regardless of the screen state (§11.2 point 4).

## 3. The code

- `layer3d/gate.py` — `Layer3DGate.stale: bool = False` (persisted in the `hitl_gate` JSONB; backward-compatible default).
- `layer4/orchestrator.py` — `orchestrate_plan_create(..., gate_only: bool = False)`; after `save_hitl_gate`, `if gate_only or gate.gate_status != "green": raise Layer3DGateBlocked(gate)`. Surgical; the default path is unchanged.
- `routes/plan_create.py`:
  - `_regate_parked_plan(db, uid, pv, plan_version)` — lock + `orchestrate(gate_only=True)` + catch `Layer3DGateBlocked` (commit fresh gate, re-park) + broad-except (leave parked + log, never fail the plan) + release lock.
  - `_advance_plan_generation` needs_review branch: load gate; `stale` → `_regate_parked_plan`; else the existing no-op short-circuit.
  - `resolve_review_item`: `kind` field (`acknowledge` default | `revise`); the revise branch records `revised` + `stale=True` + redirects to the fix surface (valid for blockers — revise is their only path).
  - `plan_review` GET: `stale` → inline `_advance_plan_generation` → reload the fresh gate → render.
  - `_REVISE_TARGET_ENDPOINTS` + `_revise_target_url`.
- `templates/plan_create/review.html` — `[Fix this]` is now a POST form (`kind=revise`) instead of "Fix via: …" text.
- Rule #15 logging on the re-gate (`_regate_parked_plan` + the `gate_only` branch in orchestrate).

## 4. Tests / suite

`tests/test_layer3d_wiring.py` +4: `test_needs_review_stale_triggers_regate` (stale → cone re-runs gate_only), `test_regate_parked_plan_runs_gate_only_and_parks` (gate_only=True, parks, never synthesizes), `test_revise_records_revised_marks_stale_and_redirects`, `test_revise_target_endpoint_map`. Updated `test_review_get_renders_items` for the new `[Fix this]` form. **Full suite: 3433 passed / 30 skipped** (`env -u DATABASE_URL python -m pytest tests/ etl/tests/ -q` — CI-style; the container's cold-Neon `DATABASE_URL` otherwise hangs the app-importing tests at `init_postgres`).

## 5. Open items / owed

- **LIVE-VERIFY (Andy-action — container can't run plan-gen; the real proof for this orchestrator-touching slice):** park a plan on an injury blocker (e.g. injuries that empty the strength pool) → `[Fix this]` → resolve the injury on `/injuries` → return to `/review` → the blocker clears via the re-gate → `[Generate plan]` → a fresh plan reflecting the fix. `/admin/logs` shows `orchestrate_plan_create: gate_only re-gate …` and `_regate_parked_plan: re-evaluated …`.
- **v1 scope gap (named, §13):** the stale flag is set on an athlete `[Fix this]` edit; a provider-sync-while-parked that shifts 3A→3B does NOT auto-re-fire the idle review screen — the generate-click backstop catches it (correctness preserved; only on-screen freshness is deferred). A push-based re-fire (provider sync marks the parked gate stale) is the future refinement.
- **3C cross-node conflict (#844)** — the one remaining 3D slice; drops in as a `map_3c_items()` source with no contract change.

## 6. Next session

### 6.1 Read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `./scripts/verify-handoff.sh`.

### 6.2 Next focus
3C cross-node conflict detection (#844) — the last 3D node. Otherwise the 4-tier order picks the next thread.

## 7. Rule #9 verification table (input to next session's anchor sweep)

| Claim | File | Anchor string | Check |
|---|---|---|---|
| `stale` flag on the gate | `layer3d/gate.py` | `stale: bool = False` | grep |
| `gate_only` re-gate mode | `layer4/orchestrator.py` | `gate_only: bool = False` | grep |
| Park even when green (gate_only) | `layer4/orchestrator.py` | `if gate_only or gate.gate_status != "green":` | grep |
| Re-gate function | `routes/plan_create.py` | `def _regate_parked_plan(` | grep |
| needs_review+stale → re-gate | `routes/plan_create.py` | `if gate is not None and getattr(gate, 'stale', False):` | grep |
| Resolve revise branch | `routes/plan_create.py` | `if kind == 'revise':` | grep |
| Review GET re-gates on stale | `routes/plan_create.py` | `if getattr(gate, 'stale', False):` | grep |
| Revise-target URL map | `routes/plan_create.py` | `_REVISE_TARGET_ENDPOINTS` | grep |
| [Fix this] POST form | `templates/plan_create/review.html` | `name="kind" value="revise"` | grep |
| Tests green | `tests/test_layer3d_wiring.py` | `def test_regate_parked_plan_runs_gate_only_and_parks` | `env -u DATABASE_URL pytest tests/test_layer3d_wiring.py` → all pass |
| Spec status = Slices 1+2+3 | `specs/Layer3D_Spec.md` | `Slices 1 + 2 + 3 implemented` | grep |
| §11.2 as-built note | `specs/Layer3D_Spec.md` | `As-built (2026-06-22, Slice 3)` | grep |
| CURRENT_STATE lead | `CURRENT_STATE.md` | `3D HITL GATE — SLICE 3 BUILT` | grep |

## 8. Issue reconcile

- **#213** (3D HITL gate) — Slice 3 (revise cascade + staleness re-fire) built; comment with the ref. Only **3C (#844)** remains for the node.
- **#214** (feasibility detectors) — unchanged this session (done in Slice 2).
- **#844** (3C) — untouched; the remaining 3D slice.
