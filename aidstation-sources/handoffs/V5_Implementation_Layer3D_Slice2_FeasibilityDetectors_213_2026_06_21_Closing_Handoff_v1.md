# V5 Implementation — Layer 3D HITL Gate, Slice 2: feasibility detectors (#213)

**Date:** 2026-06-21
**Branch:** `claude/magical-carson-snzvvh`
**Predecessor handoff:** `handoffs/V5_Implementation_Layer3D_Slice2_Slice3_Kickoff_213_2026_06_21.md` (kickoff) → built off `handoffs/V5_Implementation_Layer3D_Slice1_Foundation_213_2026_06_21_Closing_Handoff_v1.md`
**Spec:** `specs/Layer3D_Spec.md` §5.2/§5.3 (synced this session) + `specs/Layer4_Spec.md` §10.2 (defensive-raise decision still open)
**PR:** pending Andy's go (PR-gated operating model).

---

## 1. What this session did

Built the two pre-synthesis **feasibility detectors** that Slice 1 left as marked drop-in call sites, turning the aggregation-only gate into the full §5 gate. Both detector semantics were ratified at AskUserQuestion gates this session (§3). Pure additive change to `layer3d/gate.py`: **no `Layer3DGate`/`GateItem` contract change, no migration** (reuses Slice 1's `hitl_gate` JSONB + `needs_review` status), **no LLM/cache-revision bump** (deterministic).

Rule #9 sweep at session start: the kickoff's §6 table was clean — Slice 1 merged (PR #850), the detector hook site present, the §5.3 helpers (`weekly_capacity_hours`, `phase_volume_bands_hours`), `phase_structure_from_3b`, and the Layer-4-detectors-are-spec-only claim all verified.

## 2. The code — `layer3d/gate.py`

New section `# ─── Feasibility detectors (§5.2 / §5.3) ───`, wired at step 4 of `evaluate_layer3d_gate` (before the §9 de-dup pass):

- **`detect_injury_pool_empty(phase_structure, layer2a, layer2c_payloads, layer2d) -> list[GateItem]`** — two blocker classes:
  1. **strength-pool-empty.** Reuses `per_phase.compute_feasible_pool_ids(layer2c, layer2d)` (the exact strength surface synthesis prescribes from — strength-type, `tier>0`, ∪ across locales, minus 2D `excluded_exercises`; lazy-imported to keep the gate node light). Fires **one plan-wide** blocker when the pool drops below `_STRENGTH_POOL_MIN = 3` **and** was ≥3 *before* the exclusions (injury emptied it, not a structurally strength-light plan). Helper `_phase_needs_strength` scopes which phases ride in `evidence` (≥1 included discipline with a non-zero phase band). A plan that never had ≥3 strength exercises is never flagged.
  2. **cardio-modality-banned.** Reads 2D `discipline_risk_profiles`; one blocker per *included* discipline with `risk_level=='high'` and **no usable substitute** (every `suggested_substitutes` `still_at_risk`, or none). **Suppressed** when 2D already emitted a `no_substitute_for_high_risk`/`gap_x_high_risk_concurrent` hitl_item for that `discipline_id` (the §9 item_key de-dup can't merge across sources → explicit suppression so the athlete sees the finding once).
  - Both revise-only: `revise_target='profile.injuries'`, `can_acknowledge=False`.
- **`detect_schedule_volume_under_target(phase_structure, layer2a, layer1_payload) -> GateItem | None`** — `validator.weekly_capacity_hours` vs each phase's **whole-sport target low band** (2A `weekly_total_hours_by_phase[phase][0]`). One warning, worst (highest-target) phase headlines, rest in `evidence`. `severity='warning'`, `can_acknowledge=True`, `revise_target='profile.availability'`. Returns None when capacity is unknown or no phase is under target. **Never blocks** (Layer 4 clamps volume to capacity; this just surfaces the trim).
- **Call-site guard:** detectors run only when `plan_start_date is not None` (the orchestrator always supplies it; Slice-1 aggregation-only callers leave it None → skipped, so all existing Slice-1 tests are untouched). `phase_structure_from_3b` raising `Layer4InputError` (unusable periodization shape) is caught → logged (Rule #15) → detectors skipped, **gate never fails** (aggregation items still gate). In the wired path the orchestrator computes the same `phase_structure` before the gate, so the shape is already known-usable.
- **Rule #15 logging:** each detector logs its inputs + decision (pool before/after + floor + phases + excluding ids; banned discipline + substitutes; avail vs under-target phases).

## 3. Decisions ratified this session (AskUserQuestion)

1. **§5.3 target band → phase-total, NOT dominant-discipline.** Compare available hours to the phase's whole-sport weekly total (`weekly_total_hours_by_phase`), not the per-discipline `phase_volume_bands_hours` low edge. The per-discipline band rarely trips for a multi-sport athlete even when total weekly time is well under demand (each slice looks individually fitable while the sum doesn't) → the per-discipline reading would under-warn exactly our multi-sport target athletes. Spec §5.3 updated with the decision note.
2. **§5.2 cardio-ban → compute it in 3D**, not "rely on 2D, skip in 3D." 3D owns the feasibility check, reading `discipline_risk_profiles`. To avoid double-surfacing (the design flagged that 2D's own hitl_item fires on the same condition and de-dup can't merge across sources), 3D **suppresses** its item when 2D already covered that discipline. Spec §5.2 updated with the mechanism.

## 4. Tests / suite

`tests/test_layer3d_gate.py` +13 (extended the existing minimal-payload fixtures with `exercises_resolved` / `excluded_exercises` / `discipline_risk_profiles` / `weekly_total_hours_by_phase`):

- **TS-3D-5** strength pool emptied → 1 blocker (evidence: usable_count / pool_before_count / excluding_2d_ids / phases / headline_phase).
- **TS-3D-6** cardio modality banned → 1 blocker; + usable-substitute → no block; + non-included/non-high → no block; + 2D-already-covered → suppressed (only the 2D item shows).
- **TS-3D-7** available 4 h/wk vs Build 10–12 h → 1 warning (headline=Build, under={Base,Build,Peak}); + acknowledge → green; + capacity-meets-target → no warning.
- Edge: structurally-strength-light plan (pool_before<3) not flagged; non-strength exercise types don't count toward the floor; detectors-off-without-plan_start_date.

**Full suite: 3400 passed / 30 skipped** (`env -u DATABASE_URL python -m pytest tests/ etl/tests/ -q`). **Run note:** the container's `DATABASE_URL` points at a cold Neon; the app-importing tests (`test_layer3d_wiring.py`, `test_layer4_plan_create.py`) hang at `init_db.init_postgres()` on it. CI sets no `DATABASE_URL`, so **replicate CI by unsetting it** — `env -u DATABASE_URL`. (The pure `test_layer3d_gate.py` runs fine either way; it imports no app.)

## 5. Commits (branch `claude/magical-carson-snzvvh`)

- detectors + tests + spec sync + bookkeeping (this session). See `git log` on the branch.

## 6. Next session

### 6.1 Layer 4 §10.2 defensive raise — RESOLVED (Andy 2026-06-22: skip)
**RESOLVED (Andy 2026-06-22, AskUserQuestion): skip the raise — the 3D gate is the sole guard.** `Layer4_Spec.md` §10.2 updated to match in a follow-up commit on this branch (a fresh PR after #868 merged). Original analysis kept below for the record.

`specs/Layer4_Spec.md` §10.2 (Andy's ratified amendment) said Layer 4 "retains a defensive `Layer4ShapeInfeasibleError` raise" for the injury-pool-empty shape. The kickoff §3.4 softened this to "decide with Andy." **Recommendation (now ratified): skip it / gate is the sole guard** — the orchestrator already evaluates the gate and raises `Layer3DGateBlocked` *before* Layer 4 is invoked (Slice 1 wiring), so a Layer-4-internal raise is redundant for a case the architecture already prevents; simplicity-first. **If Andy wants it (belt-and-suspenders):** it's a small, well-specified follow-up — mechanically (Rule #11):
- `layer4/errors.py`: add `class Layer4ShapeInfeasibleError(Layer4Error)` carrying `class_: str` + `evidence: dict`.
- At the synthesis entry (`layer4/orchestrator.orchestrate_plan_create`, right before the per-phase synthesis loop, after the cone is built): call `detect_injury_pool_empty(phase_structure, ...)`; if it returns any blocker, `raise Layer4ShapeInfeasibleError('cumulative_load_injury_infeasible', evidence=...)`; orchestrator rolls back the `plan_versions` row per D-64 §6.2.
- Test: synthesis on an injury-pool-empty shape raises (defensive; normally unreachable behind the gate).
- **If we skip it instead:** update `Layer4_Spec.md` §10.2 to say 3D is the sole guard (strike "Layer 4 retains a defensive raise") so spec ↔ code stay honest.

### 6.2 Slice 3 — revise cascade + staleness re-fire (highest-risk; spec gut-check §15)
Per kickoff §4: wire `[Fix this]` on the review screen → the Layer 1 edit surface named by `revise_target` → on save, the existing partial-update invalidation cascade re-runs the affected layers → the gate re-aggregates against fresh payloads (`GateResolution(kind='revised')`; `resolved_status` already reverts a re-surfacing same-key item to pending). Plus staleness re-fire on review-screen re-entry / any upstream re-run, guarded by `evaluated_against`. The riskiest piece: the invalidation cascade has never been driven from an athlete-facing mid-plan-creation edit (spec §14) — give it the most testing.

### 6.3 3C cross-node conflict — #844 (separate, later)
Drops in as one more `map_3c_items()` source at the §5 step-3 aggregation point — no contract change.

### 6.4 Operating notes — session-start read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `./scripts/verify-handoff.sh`.

## 7. Open items / decisions owed

- **Layer 4 §10.2 defensive raise** — decide (§6.1); my rec is skip.
- **LIVE-VERIFY** (Andy-action — container can't run plan-gen): (a) athlete whose injuries empty the strength pool or ban an only-modality discipline → review screen shows the blocker, `[Generate plan]` stays disabled; (b) athlete whose schedule is below a phase target → the warning, acknowledge → green, plan generates clamped (lighter than the band). `/admin/logs` shows the detector Rule #15 lines.

## 8. Rule #9 verification table (input to next session's anchor sweep)

| Claim | File | Anchor string | Check |
|---|---|---|---|
| Strength + cardio-ban detector | `layer3d/gate.py` | `def detect_injury_pool_empty(` | grep |
| Schedule-volume detector | `layer3d/gate.py` | `def detect_schedule_volume_under_target(` | grep |
| Strength floor constant | `layer3d/gate.py` | `_STRENGTH_POOL_MIN = 3` | grep |
| Reuses the synth pool fn | `layer3d/gate.py` | `from layer4.per_phase import compute_feasible_pool_ids` | grep |
| Cardio-ban reads 2D risk profiles | `layer3d/gate.py` | `for risk in layer2d_payload.discipline_risk_profiles:` | grep |
| 2D-already-covered suppression | `layer3d/gate.py` | `covered_by_2d` | grep |
| Phase-total band (not dominant) | `layer3d/gate.py` | `layer2a_payload.weekly_total_hours_by_phase` | grep |
| Detectors guarded on start_date | `layer3d/gate.py` | `if plan_start_date is not None:` | grep |
| Shape error skips, never fails | `layer3d/gate.py` | `except Layer4InputError as exc:` | grep |
| Spec §5.2 mechanism synced | `specs/Layer3D_Spec.md` | `Cardio sessions are free-composed in Layer 4` | grep |
| Spec §5.3 phase-total decision | `specs/Layer3D_Spec.md` | `phase-total band, not dominant-discipline` | grep |
| Spec status = Slices 1+2 | `specs/Layer3D_Spec.md` | `**Slices 1 + 2 implemented**` | grep |
| Tests green | `tests/test_layer3d_gate.py` | `def test_ts3d5_injury_empties_strength_pool_blocks` | `env -u DATABASE_URL pytest tests/test_layer3d_gate.py` → 34 passed |
| CURRENT_STATE lead entry | `CURRENT_STATE.md` | `3D HITL GATE — SLICE 2 BUILT` | grep |

## 9. Issue reconcile

- **#213** (3D HITL gate) — commented Slice 2 (detectors) built on `claude/magical-carson-snzvvh`; remains OPEN (Slice 3 revise-cascade + the §10.2 defensive-raise decision still pending). Slice 1 already noted on it.
- **#214** (feasibility detectors) — the two surviving detectors are now implemented in 3D; commented with the ref. Closeable once Andy signs off (and the §10.2 defensive-raise decision lands).
- **#844** (3C cross-node conflict) — untouched; still deferred.
