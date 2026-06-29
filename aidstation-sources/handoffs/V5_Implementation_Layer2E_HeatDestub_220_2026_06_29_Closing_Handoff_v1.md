# V5 — Layer 2E §5.8 heat-acclim de-stub (#220): SHIPPED

Closing handoff. #220 replaced the §5.8 heat-acclim stub with the real overlay
fed by the Plan Management contract (#215 spec + #221 producer). Built this
session on `claude/v5-implementation-onboarding-rbotu8`; PR not yet opened
(push + bookkeep + wait for Andy's go).

## 1. What shipped

The §5.8 `_stub_heat_acclim_adjustments` (every event → `temp_signal='unknown'`)
is now `_heat_acclim_overlay` — the **consumer** of the `PlanManagementState`
contract. #220 is the wiring PR for both halves: #221 built
`plan_management.derive_heat_acclim_state` + `derive_current_phase` but left
them **entirely unwired** (dead on main); this session merged `origin/main`,
then wired the producer + built the consumer.

- **`weather_client.get_forecast_high(lat, lng, target_date, *, fetcher=None)`**
  — §5.3.2 forecast leg. Open-Meteo forecast endpoint (`_FORECAST_URL`), single-day
  window, returns daily high °C or `None` (missing coords / fetch fail / empty).
- **`plan_management.derive_expected_race_temp_c(events, coords_by_event_id, today, *, fetcher=None)`
  + `_blend`** — §5.3. Climate normal (`get_expected_conditions`) blended toward
  the forecast inside the 14-day horizon (`_FORECAST_HORIZON_DAYS`); `None` when
  no coords or both legs fail. Coords come via `coords_by_event_id` (keyed by the
  str event_id) because `Layer2ETargetEvent` carries none.
- **`layer4.context.PlanManagementState`** — the §3 contract: `current_phase: str`
  (plain str per the spec dataclass — the 2E builder's `_validate_inputs` stays
  the {Base,Build,Peak,Taper} gate) + `heat_acclim_state` + `expected_race_temp_c`.
- **`layer2e/builder.py`** — `_heat_acclim_overlay` + `_hot_event_adjustment`
  (spec §5.8 verbatim). Signature migrated: bare `current_phase` → `plan_management_state`,
  + keyword-only `heat_acclim_data_sparse: bool = False`. Removed the orphaned
  `_PHASE_LITERAL` + `Literal` import my edit left dead.
- **`layer4/orchestrator.py`** — assembles `PlanManagementState` at read time
  (`derive_heat_acclim_state` + `derive_expected_race_temp_c`), passes it +
  `heat_acclim_data_sparse`. `current_phase` keeps the existing 3B `start_phase`.

### Bands (spec §5.8)
`<18` cool 0.85/0.85 · `<26` temperate 1.0/1.0 · `<32` warm 1.15/1.15 · `≥32`
hot 1.30/1.35 (na/fluid). Low acclim + <14 days to event → `heat_acclim_gap`
(moderate); low acclim otherwise → `heat_acclim_in_progress` (info). Unresolved
temp (`None`) → `temp_signal='unknown'` + `race_temp_unknown`, no modifier. One
`heat_acclim_data_sparse` advisory per build when the producer flags sparse data
(<5 logged condition-days). `salt_tolerance` is NOT consumed in the band (the
spec applies it in the §5.4 race-day path).

## 2. Decisions

- **Signature (Trigger #3):** option (a) — the spec-faithful `PlanManagementState`
  object — chosen (the kickoff recommended it; the AskUserQuestion tool erred, and
  Andy's "let's do it / keep goin" authorized proceeding on the recommendation).
  `current_phase` typed `str` (not Literal) to match the spec §3 dataclass and
  keep `_validate_inputs` the validation gate.
- **`current_phase` derivation unchanged** — kept 3B `start_phase`; did NOT switch
  to the week-indexed `derive_current_phase` (that's a phase-scaling behavior
  change = separate decision). See §4 gap.

## 3. Verification

- Full suite **3919 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B
  `evidence_basis` warnings). Run: `/tmp/venv/bin/python -m pytest tests/ etl/tests/ -q`.
- ruff clean on all changed files. (The 1 E402 in `test_layer2e.py` + 3 `mocks`
  F841 in `test_layer4_orchestrator.py` that ruff reports are **pre-existing** —
  confirmed by stashing the diff and re-linting; not in this session's lines.)
- New/updated tests: `test_layer2e.py` `TestHeatAcclimOverlay` (cool/temperate/
  warm/hot/unknown bands, gap vs in-progress, sparse advisory); `test_plan_management.py`
  `TestDeriveExpectedRaceTempC` (no-coords, far-out-normal, in-horizon-blend §13.2,
  forecast-fail fallback, no-normal-trust-forecast, both-fail); `test_weather_client.py`
  `TestForecastHigh`; `test_layer4_orchestrator.py` kwarg assertion.
- No Neon/layer0 apply owed — all read-time derivation + public-schema reads
  (`conditions_log`, `race_events`); weather recomputed on read, never pinned to
  `etl_version_set` (PM spec §8).

## 4. Discovered gap (filed as a new issue)

`plan_management.derive_current_phase` (§5.1 — week-indexed active phase) is
**built but unwired**: #221 added it to `plan_management.py` but no caller exists,
and the orchestrator still passes `layer3b_payload.periodization_shape.start_phase`
(always the first block, not today's phase). #220 deliberately did not switch it
(changing `current_phase` alters 2E phase-scaling = a separate cross-layer decision,
PM-1). Next session can wire it as a small follow-up. Verify: `git grep -n
"derive_current_phase" -- '*.py'` shows only the def + this handoff, no call site.

## 5. Files (5 code, at ceiling — cohesive de-stub the kickoff anticipated)

`weather_client.py`, `plan_management.py`, `layer4/context.py`, `layer2e/builder.py`,
`layer4/orchestrator.py` + tests `tests/test_layer2e.py`, `tests/test_plan_management.py`,
`tests/test_weather_client.py`, `tests/test_layer4_orchestrator.py`.

## 6.3 Read order for next session (Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — #220 is the last shipped session
3. `CARRY_FORWARD.md`
4. This handoff
5. (no `scripts/verify-handoff.sh` in-repo — Rule #9 spot-check by the §7 anchors)

## 7. Verification anchors (Rule #10)

| Claim | Anchor | Check |
|---|---|---|
| stub gone, overlay live | `_heat_acclim_overlay` + `_hot_event_adjustment` in `layer2e/builder.py`; no `_stub_heat_acclim_adjustments` | grep |
| contract model | `class PlanManagementState` in `layer4/context.py` (current_phase `str`) | grep |
| forecast leg | `def get_forecast_high` in `weather_client.py` | grep |
| temp derivation | `def derive_expected_race_temp_c` + `_blend` in `plan_management.py` | grep |
| orchestrator wiring | `derive_expected_race_temp_c(` + `plan_management_state=` in `layer4/orchestrator.py` | grep |
| current_phase gap | `derive_current_phase` has only a def, no call site | grep |
| suite green | 3919 passed / 30 skipped | pytest |

## 8. Out of scope / deferred

- `derive_current_phase` wiring (§4 gap — filed).
- `expected_race_temp_c` refresh cadence as events cross the horizon (PM-4 —
  scheduling, not this slice).
- HITL gates 1-4 + pregnancy (#223/#518); icebox Layer-0 promotions (#229/#232/#233);
  #222 ffm_kg.
