# V5 — Closing: Layer 2E heat-acclim derivation (#221), epic #210

Implementation handoff. Created 2026-06-29 on branch
`claude/layer2e-heat-destub-221-c5l13a`. Implements the **producer** half of the
`PlanManagementState` contract authored in #215 (`specs/Plan_Management_Spec_v1.md`).
PR not yet opened — push + bookkeep + wait for Andy's go.

## 1. What this session did

Implemented `Plan_Management_Spec_v1.md` §5.1 + §5.2 — the two #221 surfaces —
as a new root-level `plan_management.py`, plus the `HeatAcclimState` model.

- **`plan_management.derive_current_phase(layer3b_payload, plan_start, today,
  total_weeks=None)`** (§5.1) — the active periodization phase today, from the
  Layer 3B shape + plan start. Before plan start → first block; past plan end →
  last block (Taper). See §3 for the reuse decision.
- **`plan_management.derive_heat_acclim_state(db, user_id, today)`** (§5.2) —
  returns `(HeatAcclimState, data_sparse: bool)`. Bands `level` from
  `COUNT(DISTINCT date)` of hot training days (`temp_f > 77.0` = 25 °C) in
  `conditions_log` over the last 30 days: 0–4 `low` / 5–13 `moderate` / ≥14
  `high`. `data_sparse` (<5 logged condition-days total in the window) forces
  `level='low'`; the consumer (#220) renders it as `heat_acclim_data_sparse`.
  Derived at read time — **no new schema** (Athlete_Data_Integration_Spec §2.6).
- **`layer4/context.py`** — new `HeatAcclimState` pydantic model (spec §3 shape:
  `level` / `days_at_temp_last_30` / `last_assessment`), placed next to
  `HeatAcclimEventAdjustment`. Locked to 2E's signature — extend, don't rename.
- **Rule #15 logging** on both derivations (inputs + chosen band/phase + the
  sparse branch).
- **`tests/test_plan_management.py`** — 19 tests: §5.1 windows / before-start /
  past-end clamps / non-Base start / custom mode / degenerate-raise; §5.2 bands
  + boundaries (4/5/13/14) / sparse / empty-log / NULL-aggregate / query-shape.

## 2. Verification

- `tests/test_plan_management.py` — 19 passed.
- Full `tests/` — **3797 passed, 30 skipped** (single-file collection still hits
  the documented circular-import quirk — run the full suite; CLAUDE.md env note).
- 3 substantive files (`plan_management.py`, `layer4/context.py`,
  `tests/test_plan_management.py`) — within the 5-file ceiling.

## 3. Key implementation choice — §5.1 reuses Layer 4's decomposition (flag for Andy)

The spec §5.1 pseudocode walks an abstract "ordered list of phase blocks". The
real 3B contract (`PeriodizationShape`, `layer4/context.py:1070`) carries
per-phase week counts **only for `mode=='custom'`**; for standard / compressed /
extended the spans come from `Layer4_Spec.md` §6.1 proportions, which Layer 4
already decomposes in **`layer4/phase_structure.py::phase_structure_from_3b`** +
`phase_for_date`. `derive_current_phase` reuses those rather than duplicating the
§6.1 allocation math.

Why this is the right call (and consistent with the spec's intent — "derive from
3B shape + plan start, NOT a Layer 4 *persisted* calendar"): `phase_structure_from_3b`
is a **pure decomposition of the 3B shape**, not a read of Layer 4's realized
plan-gen output. Reusing it guarantees PM's phase boundaries equal the ones
Layer 4 renders into, which *minimizes* the PM-1 divergence the spec flags as
§5.1's soft spot. The cost: `derive_current_phase` takes the full
`Layer3BPayload` (not a bare `periodization_shape`) and an optional
`total_weeks` — the plan horizon Layer 4 used (`plan_create._compute_total_weeks`;
`None` → the helper's 12-week open-ended default). **The orchestrator wiring in
#220 must pass the same `total_weeks` the plan was built with** so the phase
read matches the rendered calendar.

## 4. Next session — #220 (the consumer)

#221 produced the state; **#220 consumes it.** Per
`handoffs/V5_Spec_Layer2E_HeatDestub_220_2026_06_29_Kickoff_Handoff_v1.md`:

1. Add **`weather_client.get_forecast_high(lat, lng, target_date, *, fetcher=None)`**
   (§5.3.2) — Open-Meteo forecast endpoint, same `Fetcher` pattern.
2. Implement **`derive_expected_race_temp_c` + `_blend`** (§5.3) in
   `plan_management.py` — alongside the two functions this session added.
3. Replace **`_stub_heat_acclim_adjustments`** (`layer2e/builder.py:1124`) with
   the real `heat_acclim_overlay` + `_hot_event_adjustment` (`Layer2E_Spec.md`
   §5.8), fed by `HeatAcclimState` + `expected_race_temp_c`. Render the
   `heat_acclim_data_sparse` advisory from the `data_sparse` bool this session
   returns.
4. **Resolve the builder signature fork (Trigger #3 — stop-and-ask)** and the
   orchestrator wiring of `PlanManagementState` (kickoff §3.1/§3.2). #221 left
   the builder signature untouched.
5. Rewrite `TestHeatAcclimStub` → real band tests (kickoff §4).

`PlanManagementState` (the umbrella struct) is **not** defined yet — it needs
`expected_race_temp_c` (§5.3, #220). Define it in `layer4/context.py` when #220
assembles it.

## 5. Operating notes — session-start read order (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md` — #221 is the last shipped session
3. `CARRY_FORWARD.md`
4. This handoff + `handoffs/V5_Spec_Layer2E_HeatDestub_220_2026_06_29_Kickoff_Handoff_v1.md`
5. `specs/Plan_Management_Spec_v1.md` §5.3 (the unbuilt leg) + `specs/Layer2E_Spec.md` §5.8
6. `./scripts/verify-handoff.sh`

## 6. Open items / decisions owed

- **#220 builder signature fork** (Trigger #3) — kickoff §3.1, Andy's call.
- **Module placement confirmed by default:** `plan_management.py` at root
  (mirrors `weather_client.py`). If Andy prefers it inside the `layer2e`
  package, it's a single `git mv` + import update before #220 builds on it.
- **PM-1** (phase divergence under Layer 4 reshaping) — this session's reuse of
  `phase_structure_from_3b` reduces but does not eliminate it; still tracked.

## 7. Rule #9 verification table (input to next session's anchor sweep)

| File | Anchor | Check |
|---|---|---|
| `plan_management.py` | `def derive_current_phase(` + `def derive_heat_acclim_state(` | both present; module at repo root |
| `plan_management.py` | `_HOT_DAY_THRESHOLD_F = 77.0`, `_SPARSE_MIN_DAYS = 5`, `_HIGH_FLOOR_DAYS = 14` | band/threshold constants |
| `layer4/context.py` | `class HeatAcclimState(_Base):` | model present, 3 fields, above `HeatAcclimEventAdjustment` |
| `tests/test_plan_management.py` | `class TestDeriveCurrentPhase` + `class TestDeriveHeatAcclimState` | 19 tests; full-suite run green |
| `layer2e/builder.py` | `def _stub_heat_acclim_adjustments(` (1124) | **still the stub** — #221 did not touch it (that's #220) |

## 8. Issue reconcile

- **#221** — already `closed`/`completed` (Andy closed it when the #215 spec
  shipped, which closed the *design*). This session shipped the
  *implementation*; commented on the closed issue with the commit ref. Not
  reopened.
- **Epic #210** — stays open; remaining sub-issues #218/#220/#222/#223/#224/
  #226/#227. #220 is the immediate next.
