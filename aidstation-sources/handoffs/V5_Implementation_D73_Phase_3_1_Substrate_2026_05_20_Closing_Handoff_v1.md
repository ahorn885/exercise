# D-73 Phase 3.1-Substrate — Layer 3A Integration Substrate — Closing Handoff

**Session:** Phase 3.1 split-scope first half. Andy opened with the Doc-Sweep closing handoff URL + "lets work!" → state report per Rule #13 → picked **Phase 3.1 — Layer 3A driver** at the first scope gate → after the substrate-then-driver tradeoff was laid out, picked **Option A: Substrate then driver** at the second scope gate. This session lands the substrate — five `q_layer3A_*` query-node accessors + the `Layer3AIntegrationBundle` aggregator per `Athlete_Data_Integration_Spec_v6.md` §10. Pure SQL, no LLM, no `/plan-mode` triggers, under ceiling. The driver session (LLM call + prompt body + Anthropic SDK adapter + confidence-floor validator) opens next session with the `/plan-mode` gate on green substrate.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Doc_Sweep_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/v5-doc-sweep-handoff-QKl0s` (harness-pinned; scope mismatch with this session's substrate work flagged but not renamed — branch already carries the predecessor session's commits, renaming mid-stream would require coordinating with the harness).
**Status:** 🟢 5 substantive files shipped under ceiling. 941 tests green (901 baseline + 40 new). One commit pending push.

---

## 1. Session-start verification (Rule #9)

Anchor-check of predecessor §8 via `./aidstation-sources/scripts/verify-handoff.sh` + 901-test baseline rerun.

| Claim | Anchor | Result |
|---|---|---|
| All §8 anchor paths from predecessor exist on disk | `verify-handoff.sh` [1] | ✅ all 13 paths ✅ |
| Predecessor §8 table reads green | `verify-handoff.sh` [3] | ✅ extracted clean |
| `python -m pytest tests/` → 901 passed | bootstrap + rerun | ✅ `901 passed in 3.00s` after the documented `pip install --break-system-packages` bootstrap |
| Working tree clean at session start | `git status` | ✅ |
| Branch is harness-pinned | `git branch --show-current` | claude/v5-doc-sweep-handoff-QKl0s — scope mismatch noted but not renamed; commit retains continuity with predecessor PR #104 |

**No drift between predecessor narrative and on-disk state.** Runtime-env quirk repeated (cloud container's default `pytest` is `uv tool install` isolated Python; documented working path used).

---

## 2. Session narrative

Andy opened with the Doc-Sweep handoff URL + "lets work!" — standard session-start. Read order per Rule #13 executed cleanly: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md → predecessor handoff → verify-handoff.sh (all green) → PR_Verification_Status.md (no new flips since predecessor). Status report given with the architect-recommended Phase 3.1 forward move highlighted alongside the alternative pivots (Step 7 SDK scaffolding, form-refresh PR, Plan Management spec, Phase 1.4 catalog migration, Step 4f, §5.0 walkthrough).

Andy picked **Phase 3.1 — Layer 3A driver**. Triggers #2 (prompt body design) + #5 (architectural alternatives) fired; I stopped and presented the plan-mode gate in chat with three sub-options — (A) substrate-then-driver split, (B) all-in-one over-ceiling, (C) driver with stub accessors — alongside file-by-file scope, the D1-D10 source decisions, and a gut check. Recommendation was Option A on the grounds that (a) the integration substrate isn't shipped (Layer3AIntegrationBundle + 5 q_layer3A_* accessors needed per Integration Spec v6 §10), (b) substrate is a pure query-node session with no `/plan-mode` triggers, (c) splitting matches the Phase 2.4-Prep / Phase 2.4 precedent.

Andy picked Option A.

Execution: bootstrapped pytest per the documented runtime quirk → confirmed 901 baseline → read deployed schemas (cardio_log + wellness_self_report + polar_sleep + polar_nightly_recharge + polar_cardio_load + coros_daily_summary + coros_hrv_samples + provider_auth + webhook_events) → read the Layer 2C builder pattern + `_FakeConn` test precedent → wrote `layer4/context.py` additions (7 new dataclasses + 3 source Literals) → wrote `layer3a/__init__.py` + `layer3a/integration.py` (~480 LOC) → wrote `tests/test_layer3a_integration.py` (40 tests). First test pass hit one off-by-one bug in `_window_cutoff` — "last N days" should yield N calendar dates inclusive of `as_of`, not N+1. Fixed the helper to subtract `(days - 1)` and updated four affected param-assertion tests. Second test pass: 40/40 green; full suite 941/941. Bookkeeping: `layer4/__init__.py` re-exports updated; Upstream Plan §4 row 3.1 rewritten to reflect the 2-session split; CURRENT_STATE.md pointer flipped; CARRY_FORWARD.md carry-forwards for the driver session documented with the D1-D10 decisions pre-staged.

---

## 3. File-by-file edits

### 3.1 `layer4/context.py` — 7 new dataclasses + 3 source Literals

Appended after `Layer3APayload` (line 738), before the Layer 3B block. New types:

- `WorkoutSource` Literal — `manual` / `garmin` / `polar` / `wahoo` / `coros`.
- `WorkoutRecord` — date, activity, duration_min, moving_time_min, distance_mi, avg_hr, max_hr, avg_power, elev_gain_ft, source. Numeric fields are optional (provider rows may be sparse).
- `SleepSource` Literal — `wellness_self_report` / `polar` / `coros`.
- `SleepRecord` — date, total_sleep_hours, sleep_quality (1-10, self-report only), source.
- `HRVSource` Literal — `polar` / `coros`.
- `HRVRecord` — date, hrv_rmssd_ms, source.
- `PolarCardioLoadCrossRef` — date, daily_load, acute_load, chronic_load, cardio_load_status, strain. Per Integration Spec §10 this is a cross-reference only; the primary ACWR number is computed from `cardio_log`.
- `CombinedLoadReport` — per_discipline dict (discipline → `ACWREntry`), combined `ACWREntry | None`, units pinned to `"hours"` Literal, polar_cross_ref optional.
- `ProviderStatus` — provider, status (`active` / `error` / `pending_backfill` / NULL per `provider_auth.status`), last_sync (from MAX webhook_events.received_at), has_recent_workouts / has_recent_sleep / has_recent_hrv coverage bools.
- `Layer3AIntegrationBundle` — as_of + the 5 accessor outputs composed together. This is the input to the driver session's `llm_layer3a_athlete_state(integration_bundle=...)`.

All models inherit `_Base` (extra="forbid"). `ACWREntry` reused from existing Layer3APayload sub-models.

### 3.2 `layer3a/__init__.py` (NEW)

Re-exports the 5 `q_layer3A_*` accessors + `assemble_layer3a_integration_bundle`. Module-level docstring distinguishes substrate (this session) from driver (next).

### 3.3 `layer3a/integration.py` (NEW, ~480 LOC)

Five accessor implementations matching Integration Spec v6 §10 signatures (with parameter naming aligned to the deployed schema):

1. **`q_layer3A_recent_workouts(db, user_id, as_of, *, since_days=28)`** — single SELECT against `cardio_log` filtered on `user_id` + `date >= cutoff`. Source detection in Python via foreign-id column presence (Garmin > Polar > Wahoo > COROS > manual priority). Returns chronological-descending list of `WorkoutRecord`.

2. **`q_layer3A_recent_sleep(db, user_id, as_of, *, since_days=14)`** — three SELECTs (self-report, polar_sleep total_sleep_min ÷ 60, coros_daily_summary sleep_start_ms/end_ms delta ÷ 3.6M) merged in Python, sorted by (date, source) descending. Sleep quality emitted only on self-report rows; provider rows leave it None (LLM resolves per §6.1 rules at the driver seam).

3. **`q_layer3A_recent_hrv(db, user_id, as_of, *, since_days=14)`** — two SELECTs (polar_nightly_recharge.hrv_rmssd_ms, coros_daily_summary.ppg_hrv) with NULL filtering. ppg_hrv cast int → float for type consistency. coros_hrv_samples downsampling deferred (the nightly summary covers v1 needs).

4. **`q_layer3A_combined_load(db, user_id, as_of, *, window_days=28, acute_window_days=7)`** — one SELECT for cardio_log over the chronic window, one for the latest polar_cardio_load row (cross-ref only). Python ACWR computation: per-activity + combined; prefers `moving_time_min` over `duration_min` when both populated; converts minutes → hours; classifies zones via `_classify_zone` against the Gabbett-2016 sweet-spot band 0.8-1.3 + the spec §8.1 warning thresholds at >1.5 + <0.5. Sentinel `999.0` ratio when acute_hours > 0 but chronic_hours == 0 (new-athlete-no-base case). `_compute_acwr` returns None when both acute and chronic are zero (no signal → sparse dict entry).

5. **`q_layer3A_connected_providers(db, user_id, *, as_of=None, ...)`** — 7 SELECTs total: provider_auth roster + webhook_events MAX(received_at) per provider + cardio_log COUNT FILTER per foreign-id + 4 single-table counts for sleep + HRV per polar/coros. Returns one `ProviderStatus` per row in provider_auth with per-data-type coverage flags computed from the recency windows.

6. **`assemble_layer3a_integration_bundle(db, user_id, as_of)`** — convenience composer running all 5 accessors against the same `as_of` anchor.

Constants block documents the ACWR zone thresholds, window defaults, and the no-base sentinel. Helpers: `_as_date` handles the deployed schema's TEXT date columns + datetime/date inputs from tests; `_window_cutoff(as_of, days)` returns the inclusive cutoff so `[cutoff, as_of_date]` contains exactly `days` calendar dates; `_detect_workout_source` does the foreign-id priority check; `_classify_zone` + `_compute_acwr` are pure functions for testability.

### 3.4 `tests/test_layer3a_integration.py` (NEW, 40 tests)

`_FakeConn` / `_FakeCursor` / `_FakeRow` pattern matching `tests/test_layer2c.py`. Coverage:

- **TestRecentWorkouts** (7 tests): empty, since_days param, default 28d window, 5-source detection, garmin-wins priority, full-field round-trip, date|datetime accepted.
- **TestRecentSleep** (5 tests): empty all sources, self-report only, polar source, coros ms-conversion, multi-source merge sort desc.
- **TestRecentHRV** (3 tests): empty, polar+coros merge, default 14d window.
- **Zone classifier parametrize** (11 tests): all 5 zone boundaries swept.
- **ACWR helpers** (3 tests): no-data None, no-base sentinel, steady-state sweet_spot.
- **TestCombinedLoad** (6 tests): empty, single-discipline 28-day sweet-spot, multi-discipline independent ACWR, moving_time preference, polar cross-ref population, null-duration filtering.
- **TestConnectedProviders** (3 tests): no providers, polar full coverage, coros workouts only.
- **TestAssembleBundle** (2 tests): full compose with all sources populated, empty compose with no data anywhere (15 empty batches).

40/40 green.

### 3.5 `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 3.1 split annotation

Phase 3 section rewritten to document the 2-session split (Substrate ✅ + Driver). Same precedent annotation pattern as the Phase 2.4 / 2.4-Prep split. Substrate row marked ✅ Shipped with file count + test delta; Driver row carries the remaining `/plan-mode` gate + D1-D10 source-decision pointer.

### 3.6 Bookkeeping (outside ceiling per CLAUDE.md B3)

- `layer4/__init__.py` — added 7 new dataclasses to the `from layer4.context import (...)` block + `__all__` list (alphabetized into the Layer 3A section).
- `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer status row 3 updated to 🟡 substrate; Tests note flipped 901 → 941; Current focus reframed to Phase 3.1-Driver as the architect-recommended next move.
- `aidstation-sources/CARRY_FORWARD.md` — new "Phase 3.1-Driver carry-forwards" section pre-stages the D1-D10 source decisions for the driver session's `/plan-mode` gate; notes the spec §3.3 `claude-sonnet-4-5` literal drift vs current canonical Sonnet 4.6.
- This handoff.

---

## 4. Code / tests

- New code: ~510 LOC across `layer3a/__init__.py` (25) + `layer3a/integration.py` (~480) + new dataclasses in `layer4/context.py` (~90 LOC added).
- New tests: 40 (across 7 test groups, including 11-point parametrized zone-classifier sweep).
- `tests/` count: 901 → 941 (+40).
- `python -m pytest tests/ -q` → `941 passed in 1.67s` post-final-edit.

---

## 5. Operational sequence for Andy on Neon

N/A — substrate session ships code only, no schema migrations. The Phase 2.4-Prep operational sequence (3 SQL migrations + ETL re-run) is still the live prerequisite for the Phase 2.4 §5.0 manual walkthrough scenarios, unchanged.

When Phase 3.1-Driver ships, the §5.0 walkthrough scenario will be: run `assemble_layer3a_integration_bundle(db, andy_user_id, as_of=datetime.now())` against Andy's live production state — confirm `recent_workouts` populates from his manual cardio_log entries (no providers fully connected yet in production), `recent_sleep` populates from any `wellness_self_report` rows he's logged, `recent_hrv` is empty (no Polar/COROS sync yet), `combined_load.combined` returns a per-discipline ACWR derived from his actual logged training, `polar_cross_ref` is None, `connected_providers` lists whatever rows are in his `provider_auth` table.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Phase 3.1-Driver — Layer 3A LLM driver** (architect-recommended per Upstream Plan §4 row 3.1-Driver). Same scope, same triggers, opens with `/plan-mode`:

- `llm_layer3a_athlete_state(...)` entry point in `layer3a/builder.py`.
- `Layer3AInputError` / `Layer3AOutputError` in `layer3a/errors.py` (or inlined per Layer 4 Step 4a + Layer 2C precedents — both are valid).
- Anthropic SDK adapter — `_default_llm_caller` matching `layer4/single_session.py:_default_llm_caller` (extended thinking + forced tool-use).
- Tool schema mirroring full `Layer3APayload` contract.
- Capped retry on schema violation (§5.3 step 1; lighter than Layer 4 Step 4a's validator-driven retry).
- Confidence-floor enforcement (§5.3 step 3 + §6.2 floor rules + §6.3 `confidence_clamped_by_data_density` observation auto-append).
- Prompt body in `aidstation-sources/prompts/Layer3A_v1.md`.
- Tests in `tests/test_layer3a_builder.py` covering §13's 10 scenarios + the §6.2 floor enforcement + the §4 precondition raises.

`Layer3APayload` pydantic schema is already shipped (`layer4/context.py` line 725) — no schema work.

### 6.2 Alternative pivots

Unchanged from predecessor §6.2:

- **Layer 4 Step 7** — env-gated `ANTHROPIC_API_KEY` scaffolding (~3-4 files). Unblocks Phase 5 vertical slice in parallel.
- **§H.2 / §J / §I.1 form-refresh PR** — paired alignment to wire Layer 2B + Layer 2E input-source surfaces (~6-8 files, over ceiling).
- **Plan Management spec authorship** — de-stubs Layer 2E §5.8 heat acclim.
- **D-73 Phase 1.4** — D-52 catalog migration sequencing.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration.
- **Manual §5.0 walkthrough** of the accumulated 69 scenarios.

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff; layer status row 3 is 🟡 substrate
3. `aidstation-sources/CARRY_FORWARD.md` — Phase 3.1-Driver carry-forwards pre-stage the D1-D10 decisions
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward):** the cloud container's default `pytest` is `uv tool install` isolated Python; working path is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**If picking Phase 3.1-Driver:** open with the `/plan-mode` gate walking the 10 D-decisions itemized in `CARRY_FORWARD.md` → Phase 3.1-Driver section. Pair with a 1-line spec correction in `Layer3_3A_Spec.md` §3.3 flipping the default-model literal `claude-sonnet-4-5` → `claude-sonnet-4-6` (current canonical). Reuse `layer4/single_session.py` as the precedent.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Phase 3.1 scope = substrate-then-driver split | Andy 2026-05-20 (after Option A/B/C tradeoff laid out) | Integration substrate isn't shipped (Layer3AIntegrationBundle + 5 q_layer3A_* accessors needed per Integration Spec v6 §10). Substrate is pure query-node work with no `/plan-mode` triggers, fits cleanly under ceiling. Driver session opens on green substrate with a clean `/plan-mode` gate. Mirrors Phase 2.4-Prep / 2.4 precedent. |
| 2 | ACWR `combined.units` pinned to `"hours"` Literal | Architect-pick + spec consistency | Integration Spec §10 says Polar's `cardio_load` is cross-reference only; primary number is `cardio_log` durations. Hours is the only canonical unit until a TRIMP normalization factor lands (spec §13 gut-check flagged this as fragile). Literal pins the v1 contract so the LLM doesn't see ambiguous units. |
| 3 | `_window_cutoff(as_of, days)` returns inclusive cutoff (subtract `days - 1`) | Architect-pick (after off-by-one surfaced in first test pass) | "Last 7 days" semantically means 7 calendar dates inclusive of `as_of`. The original `as_of - 7 days` gave 8 dates in the window. The fix subtracts `(days - 1)` so `[cutoff, as_of_date]` contains exactly `days` dates. ACWR computation now matches the standard convention. |
| 4 | `coros_hrv_samples` high-resolution downsampling deferred | Architect-pick + Integration Spec §10 note | Spec calls for downsampling to nightly but `coros_daily_summary.ppg_hrv` already provides the nightly value. v1 substrate uses the summary; sample-level downsampling lands later if signal quality demands. |
| 5 | Garmin wellness_log sleep skipped in v1 | Architect-pick + D-55 status | Spec names Garmin wellness_log sleep as a source but no Garmin sleep table is deployed (Garmin paused per D-55). Add when Garmin reopens API access. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer4/context.py` contains `class Layer3AIntegrationBundle(_Base):` | ✅ grep |
| `layer4/context.py` contains `class WorkoutRecord(_Base):` + `WorkoutSource = Literal[...]` | ✅ grep |
| `layer4/context.py` contains `class SleepRecord` + `class HRVRecord` + `class CombinedLoadReport` + `class ProviderStatus` + `class PolarCardioLoadCrossRef` | ✅ grep |
| `layer3a/__init__.py` exists and re-exports the 5 `q_layer3A_*` functions + `assemble_layer3a_integration_bundle` | ✅ inspection |
| `layer3a/integration.py` contains all 5 `def q_layer3A_*` functions + `def assemble_layer3a_integration_bundle` | ✅ grep |
| `layer3a/integration.py` `_window_cutoff` subtracts `days - 1` for inclusive cutoff | ✅ inspection |
| `tests/test_layer3a_integration.py` contains 40 test cases across 7 groups (TestRecentWorkouts / TestRecentSleep / TestRecentHRV / TestCombinedLoad / TestConnectedProviders / TestAssembleBundle + parametrized zone classifier + 3 ACWR helper tests) | ✅ grep + pytest count |
| `python -m pytest tests/test_layer3a_integration.py -q` → 40 passed | ✅ `40 passed in 0.69s` |
| `python -m pytest tests/ -q` → 941 passed | ✅ `941 passed in 1.67s` |
| `layer4/__init__.py` re-exports the 7 new dataclasses + Literals | ✅ `python -c "from layer4 import Layer3AIntegrationBundle, WorkoutRecord, ..."` returns clean |
| `aidstation-sources/Upstream_Implementation_Plan_v1.md` §4 Phase 3 section names 2-session split (Substrate ✅ + Driver) | ✅ grep |
| `aidstation-sources/CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Layer status row 3 reads "🟡 3A integration substrate shipped" | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Tests note reads "941 green" | ✅ inspection |
| `aidstation-sources/CARRY_FORWARD.md` Phase 3.1-Driver section pre-stages D1-D10 decisions | ✅ inspection |
| Working tree clean after commit + push (pending) | ⏳ pending commit |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (5 files; AT the 5-file ceiling):**

1. Modified `layer4/context.py` — 7 new dataclasses (`WorkoutRecord` + `SleepRecord` + `HRVRecord` + `PolarCardioLoadCrossRef` + `CombinedLoadReport` + `ProviderStatus` + `Layer3AIntegrationBundle`) + 3 source Literals (`WorkoutSource` / `SleepSource` / `HRVSource`).
2. NEW `layer3a/__init__.py` — re-exports the 5 `q_layer3A_*` accessors + `assemble_layer3a_integration_bundle`.
3. NEW `layer3a/integration.py` — 5 accessors + aggregator + ACWR helpers; ~480 LOC.
4. NEW `tests/test_layer3a_integration.py` — 40 tests using `_FakeConn` pattern.
5. Modified `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 Phase 3 section rewritten to reflect the 2-session split.

**Bookkeeping (4 files; outside ceiling per B3):**

6. Modified `layer4/__init__.py` — re-export the 7 new dataclasses (one-line additions).
7. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped; layer status row 3 updated; Tests note 901 → 941; Current focus reframed.
8. Modified `aidstation-sources/CARRY_FORWARD.md` — new Phase 3.1-Driver carry-forwards section.
9. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_3_1_Substrate_2026_05_20_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Phase 3.1-Driver section (new) pre-stages the D1-D10 decisions for the driver session's `/plan-mode` gate. See that section for the canonical list.

`CARRY_FORWARD.md` Doc-sweep nits ledger unchanged (predecessor closed the §5.1 cleanup + 4 nits batch; the 5th deferred nit — `Layer2E_Spec.md` §6.1 + §14 D-26 wording — remains in the active list; one new spec drift item flagged here: `Layer3_3A_Spec.md` §3.3 names `claude-sonnet-4-5` as the default model, which is stale vs the project's current Opus 4.7 / Sonnet 4.6 / Haiku 4.5 canonical IDs — fold into the Phase 3.1-Driver session as a 1-line spec correction).

Manual §5.0 walkthrough count unchanged at 69. Phase 2.4 scenarios still need Andy's Neon migrations + ETL re-run before they're runnable. Phase 3.1-Driver §5.0 scenarios will land with the driver session (likely 1-2 scenarios: AR baseline 3A call against Andy's PGE 2026 context with empty integration bundle + one with simulated provider data).

---

**End of handoff.**
