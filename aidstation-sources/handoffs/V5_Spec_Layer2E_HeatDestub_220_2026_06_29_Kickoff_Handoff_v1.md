# V5 — Kickoff: Layer 2E §5.8 heat-acclim de-stub (#220), epic #210

Kickoff (planning) handoff. Created 2026-06-29 alongside the #215 Plan
Management spec ship. The next session implements #220. **This is a planning
doc — no code was written for #220 in this session.**

## 1. What #220 is

`_stub_heat_acclim_adjustments()` (`layer2e/builder.py:1124`) returns a zero
modifier + a `race_temp_unknown` flag for every event. Replace it with a real
`heat_acclim_overlay` that applies the §5.8 fluid/Na band modifiers, fed by the
now-defined Plan Management contract (`specs/Plan_Management_Spec_v1.md`, shipped
#215).

The algorithm already exists in spec form — `Layer2E_Spec.md` §5.8
(`heat_acclim_overlay` + `_hot_event_adjustment`) and the derivation in
`Plan_Management_Spec_v1.md` §5.3 (`expected_race_temp_c`) + §5.2
(`heat_acclim_state`). #220 is a **wiring job**, not green-field design.

## 2. Scope split vs #221 (read first — there's an ordering dependency)

Per `Plan_Management_Spec_v1.md` §12:
- **#221** implements §5.1 `derive_current_phase` + §5.2 `heat_acclim_state`
  (from `conditions_log`). It is the **producer** of `HeatAcclimState`.
- **#220** implements §5.3 `derive_expected_race_temp_c` (+ the new
  `weather_client.get_forecast_high`) and wires §5.8 `heat_acclim_overlay` to
  the contract. The overlay is the **consumer** of `HeatAcclimState`.

**Dependency:** #220's overlay consumes a real `HeatAcclimState`, which #221
produces. The overlay is not end-to-end testable without it.
**Recommendation: do #221 first (or fold both into one PR).** A heat slice that
ships the consumer against a hand-built `HeatAcclimState` while the producer
lands separately is testable in isolation but not in the pipeline. Flag for
Andy at session start.

## 3. Decisions owed (stop-and-ask — Trigger #3, cross-layer signature)

1. **Builder signature fork.** `q_layer2e_nutrition_baseline_payload`
   (`layer2e/builder.py:1254`) currently takes a **bare** `current_phase:
   _PHASE_LITERAL` (line 1263) — the vertical slice unpacked `PlanManagementState`
   to just the one field it used. The overlay now needs `heat_acclim_state` +
   `expected_race_temp_c` too. Options:
   - **(a)** Add a `plan_management_state: PlanManagementState` param (spec §3
     shape), and migrate `current_phase` to read off it. Cleanest vs spec;
     touches the orchestrator call site + every test that calls the builder.
   - **(b)** Add `heat_acclim_state` + `expected_race_temp_c` as bare params
     alongside the existing `current_phase` (matches the current bare-param
     convention). Smaller diff; diverges from the spec §3 single-object shape.
   - Recommendation: **(a)** — the spec already names `PlanManagementState` as
     the 2E input, and three loose params is the thing the contract exists to
     avoid. Andy's call (cross-layer signature = Trigger #3).
2. **Where the derivations live.** New `plan_management.py` (or
   `layer2e/plan_management.py`) implementing spec §5.1/§5.2/§5.3, called by the
   orchestrator to assemble `PlanManagementState` before the 2E call. #221 owns
   §5.1/§5.2 there; #220 adds §5.3. Confirm module placement with Andy.
3. **`current_phase` wiring refinement (in-scope flag).** The orchestrator
   passes `current_phase=layer3b_payload.periodization_shape.start_phase`
   (`layer4/orchestrator.py:1292`) — always the **first** block, not today's
   active phase. Spec §5.1 wants the week-indexed current phase. This is #221's
   §5.1 deliverable; #220 only needs to know the call site moves.

## 4. File map (current `main`/branch line refs — re-verify before editing)

| File | Where | Change |
|---|---|---|
| `weather_client.py` | after `get_expected_conditions` (ends ~line 153) | **NEW** `get_forecast_high(lat, lng, target_date, *, fetcher=None)` → Open-Meteo forecast endpoint, daily high °C or `None`. Same `Fetcher` injection pattern. Spec §5.3.2. |
| `layer4/context.py` | near `HeatAcclimEventAdjustment` (line 797) | **NEW** `HeatAcclimState` + `PlanManagementState` model classes (spec §3 shapes). |
| new `plan_management.py` | — | `derive_expected_race_temp_c` (§5.3) + `_blend` (§5.3.3). (#221 adds `derive_current_phase` §5.1 + heat-acclim §5.2 here.) |
| `layer2e/builder.py` | `_stub_heat_acclim_adjustments` (1124–1155) | **REPLACE** with `heat_acclim_overlay` + `_hot_event_adjustment` per `Layer2E_Spec.md` §5.8. Rule #15 log per event: chosen temp + source (normal/forecast-blend/unresolved) + band + days_out. |
| `layer2e/builder.py` | signature 1254–1268; call site of stub at ~1348 | Thread the new input(s) per decision 1. |
| `layer4/orchestrator.py` | 1283–1296 | Assemble `PlanManagementState` (or the two heat fields) and pass per decision 1. |
| `tests/test_layer2e.py` | `TestHeatAcclimStub` (line ~875), assertions at 453–455, 643, 894–900 | **REWRITE** stub tests → real band tests (cool/temperate/warm/hot/unknown; low-acclim < 14 days → `heat_acclim_gap`); `temp_signal='unknown'` only when `expected_race_temp_c is None`. |

## 5. Mechanically-applicable anchors (Rule #11)

The replacement body for `_stub_heat_acclim_adjustments` is the spec algorithm
verbatim — `Layer2E_Spec.md` §5.8 `heat_acclim_overlay` (bands: `<18 cool`
0.85/0.85, `<26 temperate` 1.0/1.0, `<32 warm` 1.15/1.15, `≥32 hot` 1.30/1.35)
and `_hot_event_adjustment` (low acclim + <14 days → `heat_acclim_gap`; low
acclim otherwise → `heat_acclim_in_progress`). `expected_race_temp_c[event_id]
is None` → keep the existing `temp_signal='unknown'` + `race_temp_unknown`
branch (it stays correct for coordinate-less events).

`derive_expected_race_temp_c` + `_blend`: copy from
`Plan_Management_Spec_v1.md` §5.3 (FORECAST_HORIZON_DAYS=14, daytime-high
`temp_max_c`, linear horizon blend, None on dual-fetch-failure).

## 6. Test surface

- `tests/test_layer2e.py` — convert `TestHeatAcclimStub` to real-band coverage
  (§4 table above). Existing canonical scenario `Layer2E_Spec.md` §13.1 expects
  PGE temperate (25 °C, no flag).
- New `plan_management.py` tests — `derive_expected_race_temp_c` with a stub
  `Fetcher` (deterministic), covering: far-out → normal only; ≤14d → blend;
  forecast-fail → normal fallback; no-coords → None. Mirror
  `Plan_Management_Spec_v1.md` §13.2/§13.3.
- `weather_client` test for `get_forecast_high` with stub fetcher.
- Run full `tests/` (circular-import quirk on isolated single-file collection —
  see CLAUDE.md env note).

## 7. Start here / read order (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md` — #215 is the last shipped session
3. `CARRY_FORWARD.md`
4. **`specs/Plan_Management_Spec_v1.md`** (the contract being wired) + this handoff
5. `specs/Layer2E_Spec.md` §5.8 (the overlay algorithm)
6. `./scripts/verify-handoff.sh`

First action: get Andy's call on decisions §3.1 (signature) + §3.2 (module
placement) + the #221-first ordering (§2), then implement.

## 8. Out of scope

- Supplement de-stub (#218) — separate gate (structured supplements + pregnancy
  field). The heat work does not touch it.
- `expected_race_temp_c` refresh cadence as events cross the horizon (spec
  PM-4) — scheduling concern, not this slice.
