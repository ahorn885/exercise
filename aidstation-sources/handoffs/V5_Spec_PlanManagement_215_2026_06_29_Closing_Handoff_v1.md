# V5 — Plan Management Spec + `PlanManagementState` contract (#215, keystone of epic #210)

Session date: 2026-06-29. Branch: `claude/work-on-210-mp77up`. Spec-only session
(no code, no schema). PR not yet opened — push + bookkeep + wait for Andy's go.

## 1. What this session did

Authored **`specs/Plan_Management_Spec_v1.md`** — the previously-unwritten Plan
Management spec that Layer 2E names but never defined. Closes epic #210's
keystone sub-issue **#215** and unblocks the heat work (#220 de-stub, #221
derivation).

The spec defines:
- The **`PlanManagementState`** + **`HeatAcclimState`** contracts, matching the
  forward-declarations in `Layer2E_Spec.md` §3 / §5.8 **byte-for-byte** — so no
  cross-layer contract churn (Trigger #3 satisfied by *honoring* the locked 2E
  signature, not changing it).
- Read-time derivation for all five Plan Management surfaces: `current_phase`
  (§5.1), `heat_acclim_state` (§5.2), `expected_race_temp_c` (§5.3),
  weight-staleness (§5.4), adherence-drop (§5.5, references onboarding §M.3 —
  does not redefine the threshold).
- Invalidation consistency with `Control_Spec` §4 (§6), edge cases (§9),
  performance budget (§10), open items PM-1..5 (§11), implementation handoff
  for #220/#221 (§12), test scenarios (§13), gut check (§14).

Adapted the 14-section depth standard (`Layer2C_Spec.md`) for a
**contract+derivation** subsystem rather than a single query node (documented in
the spec preamble).

## 2. Andy's decisions (AskUserQuestion, 2026-06-29)

1. **Start with #215** (the keystone spec) of epic #210.
2. **Spec scope = write the computation rules now** (not a thin contract-only
   doc) — so #221 has written rules to build against.
3. **`expected_race_temp_c` = climate-normal blended toward live forecast**
   inside a 14-day horizon (§5.3), not climate-normal-only.
4. **`current_phase` derived from Layer 3B `periodization_shape` + plan start +
   week index** (§5.1), NOT a Layer 4 persisted calendar. Accepted tradeoff:
   divergence if Layer 4's correction loop reshapes blocks — tracked PM-1.

## 3. Key spec choices (grounded, tunable)

- **Heat-acclim banding (§5.2.3):** `days_at_temp_last_30` from
  `COUNT(DISTINCT date)` on `conditions_log` where `temp_f > 77.0` (= 25 °C);
  low <5 / moderate 5–13 / high ≥14, grounded in 2E's "10–14 day full
  acclimatization floor." Sparse data (<5 logged days) → `low` +
  `heat_acclim_data_sparse` advisory (conservative direction for a hot race,
  but flagged as a data gap). Marked as tuning, not contract.
- **Weight-staleness window = 60 days** (§5.4) — tuning, not contract.
- **`expected_race_temp_c` = daytime high** (`ExpectedConditions.temp_max_c`),
  matching 2E's §5.8 daytime-racing bands.
- **Reuses existing surfaces:** `weather_client.get_expected_conditions()`
  (Open-Meteo climate normals), `race_events.event_locale_lat/lng`,
  `conditions_log`. The only new code surface is
  `weather_client.get_forecast_high()` (§5.3.2), which lands with the #220
  de-stub PR.

## 4. Cross-references reconciled (this session's other edits)

- `Layer2E_Spec.md` §3 note (PlanManagementState/HeatAcclimState "now defined"),
  §5.8 ("now written"), §12 open items **2E-2/3/4 → ✅ Resolved** (point at the
  new spec). Contracts unchanged — doc-consistency only.
- `Athlete_Data_Integration_Spec_v6.md` §2.6 — derivation owner now points at
  `Plan_Management_Spec_v1.md` §5.2; backlog **D-53 → ✅ Resolved**.

## 5. Next session

### 5.1 Start here
- **#220** — wire 2E §5.8 `heat_acclim_overlay` to this contract; replace
  `_stub_heat_acclim_adjustments()` in `layer2e/builder.py`; add
  `weather_client.get_forecast_high()` (spec §5.3.2 / PM-5).
- **#221** — implement §5.1 (`derive_current_phase`) + §5.2 (heat-acclim from
  `conditions_log`) + the `heat_acclim_data_sparse` advisory. No new schema.
- Rule #15 logging requirements for both are itemized in spec §12.

### 5.2 Operating notes — session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. Open items / decisions owed
- Spec open items **PM-1..PM-5** (`Plan_Management_Spec_v1.md` §11): phase
  divergence under L4 reshaping (PM-1); heat-acclim future signals (PM-2);
  branch-specific adherence mute (PM-3); race-temp refresh cadence (PM-4);
  `get_forecast_high` client method (PM-5, pending #220).
- Epic **#210 stays open**: #218/#220/#221/#222/#223/#224/#226/#227 remain.

## 7. Rule #9 verification table (input to next session's anchor sweep)

| File | Anchor string | Check |
|---|---|---|
| `specs/Plan_Management_Spec_v1.md` | `# Plan Management Spec — v1` | file exists; §1–§14 present |
| `specs/Plan_Management_Spec_v1.md` | `class PlanManagementState:` / `class HeatAcclimState:` | §3 contracts present, match 2E §3 |
| `specs/Layer2E_Spec.md` | `2E-2 \| ... \| ✅ Resolved — \`Plan_Management_Spec_v1.md\`` | §12 open items flipped |
| `specs/Layer2E_Spec.md` | `now defined — \`Plan_Management_Spec_v1.md\` §3 / §5.2` | §5.8 cross-ref updated |
| `specs/Athlete_Data_Integration_Spec_v6.md` | `Now specified in \`specs/Plan_Management_Spec_v1.md\` §5.2` | §2.6 / D-53 updated |
| `CURRENT_STATE.md` | `#215 LAYER 2E — PLAN MANAGEMENT SPEC` | pointer updated |

## 8. Issue reconcile
- **#215** — spec authored; comment posted with branch/commit ref; **close on
  merge** (`completed`).
- **#210** (epic) — comment progress (keystone #215 done); **stays open**.
- No new issues filed (open items captured as spec PM-1..5).
