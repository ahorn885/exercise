# D-73 Layer 4 Step 7 — Env-gated `ANTHROPIC_API_KEY` SDK Smoke Scaffolding — Closing Handoff

**Session:** Layer 4 Step 7 — SDK smoke scaffolding (3A + 3B subset). Andy opened with the Phase 4 closing-handoff URL + "lets work!" → state report per Rule #13 → picked **Layer 4 Step 7 SDK scaffolding** at the scope gate → after the file plan + D1-D9 + gut check were laid out, picked **Approve as recommended** at the second scope gate. Lands the first REAL Anthropic SDK call harness against both 3A + 3B drivers shipped earlier the same day. Closes L3A-P-1 + L3B-P-1 deferred real-LLM regression scaffolding (the smoke harness itself; remaining §13 scenarios on each driver deferred per ceiling discipline).
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_4_Layer3B_Driver_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/phase-4-layer-3b-driver-aPvU0` (harness-pinned; predecessor's branch name carried forward — same-day-after Phase 4 session continuity).
**Status:** 🟢 3 substantive files shipped (well under ceiling). 1072 tests passing + 4 skipped (default `pytest tests/` runs unchanged; smoke tests skip cleanly when `ANTHROPIC_API_KEY` unset). Layer 4 Step 7 SDK smoke scaffolding **complete for 3A + 3B**; remaining 6 entry-points (Layer 4 single_session + plan_create + 3 plan_refresh tiers + race_week_brief) deferred per same-day-shipped driver focus.

---

## 1. Session-start verification (Rule #9)

Anchor sweep of predecessor §8 via `./aidstation-sources/scripts/verify-handoff.sh` + 1072-test baseline rerun.

| Claim | Anchor | Result |
|---|---|---|
| All predecessor §8 anchor paths exist on disk | `verify-handoff.sh` [1] | ✅ 2 ❌ paths flagged are expected forward-references per predecessor §8 closing note: `layer3b/errors.py` (errors inlined in `builder.py` per architect-pick) + `layer4/orchestrator.py` (Phase 5.1 forward-pointer). All other paths ✅. |
| Predecessor §8 table reads green | `verify-handoff.sh` [3] | ✅ extracted clean |
| `python -m pytest tests/` → 1072 passed | bootstrap + rerun | ✅ `1072 passed in 2.49s` after the documented `pip install --break-system-packages` bootstrap |
| Working tree clean at session start | `git status` | ✅ |

**No drift between predecessor narrative and on-disk state.** The 2 ❌ paths are the predecessor handoff's §8 documented forward-references; not actual drift.

---

## 2. Session narrative

Andy opened with the Phase 4 closing-handoff URL + "lets work!". Session-start verification per Rule #13 ran clean (state report per CLAUDE.md first-session-checklist step 7; 2 expected forward-ref drift entries flagged but not blocking). Andy picked **Layer 4 Step 7 SDK scaffolding** at the scope question (architect-recommended next move per Phase 4 closing handoff §6.1 + CURRENT_STATE focus).

Trigger #5 (architectural alternatives with real tradeoffs) fired for the env-gating shape. I read the precedent surfaces (`layer3a/builder.py:126-182` `_default_llm_caller` — env-gating already inline; `layer3b/builder.py:155-211` same shape; `layer4/single_session.py:661-717` original precedent; `tests/test_layer3a_builder.py:820-` `TestS13Scenarios` for the 3A §13 fixture shapes; `tests/test_layer3b_builder.py:1314-` same for 3B TS-1..TS-8; `Layer4_Spec.md` §14.3.4 step 7 for the broader Step 7 scope; `CARRY_FORWARD.md` L3A-P-1 + L3B-P-1 carry-forwards) and confirmed the gap: env-gating is **already done inline** in all 3 `_default_llm_caller` functions (each raises `*OutputError("anthropic_api_key_missing")` if env var unset). What's missing is the **smoke test harness** that exercises those code paths against real Sonnet 4.6.

I presented the plan-mode gate in chat with:

1. The architectural-shape decision (`tests/conftest.py` skipif marker vs `layer4/llm_smoke.py` production helper vs inline-in-each-test) — picked **conftest.py** for test-scope minimalism.
2. The 3 substantive file scope (conftest + 3A smoke + 3B smoke).
3. The 9 D-decisions table with recommendations + rationale. D1-D2 architectural shape; D3-D4 scenario picks (§13.1 + §13.4 for 3A; TS-1 + TS-4 for 3B per handoff §6.3); D5 module-level skipif; D6 mixed structural + loose-enum assertion stringency; D7 4-test budget (~$0.12/run); D8 skip cache-wrapper smoke (covered by unit tests); D9 default collection (skipif handles zero-cost-when-absent).
4. The pattern shape (4-step per-test: fixture → driver call with `llm_caller=None` → structural assertions → loose-enum assertions).
5. A gut check covering 5 named risks (test flakiness, API key in CI shells, latency, cost runaway, schema drift) + 3 "what might be missing" (Layer 4 single_session parity, telemetry assertions, prompt_hash determinism) + 3 best-arguments-against.

Andy picked **Approve as recommended**, ratifying all 9 D-decisions + the 3-file scope.

Execution:

1. **`tests/conftest.py`** (~25 LOC) shipped first as the shared marker. Exposes `ANTHROPIC_API_KEY_ENV` constant + `requires_anthropic_api_key = pytest.mark.skipif(not os.environ.get(ANTHROPIC_API_KEY_ENV))`. Module-level skipif applied via `pytestmark = requires_anthropic_api_key` in each smoke file.
2. **`tests/test_layer3a_smoke.py`** (~300 LOC) — 2 real-LLM round-trip tests against the production Sonnet 4.6 adapter via `llm_layer3a_athlete_state(...)` with `llm_caller=None`. Includes inline fixture factories (`_make_layer1` / `_make_layer2a` / `_make_bundle_dense` / `_make_bundle_sparse`) — fixtures self-contained per the no-cross-test-import convention in the codebase. Two scenarios:
   - `test_dense_data_fit_athlete`: §13.1 shape — 5y AR athlete + 20 workouts + 14 sleep + 14 HRV + sweet_spot ACWR (1.14) + 2 providers active. Loose-enum allowlist asserts `aerobic_capacity.level ∈ {good, strong}` + `aerobic_capacity.confidence ∈ {high, medium}` + ACWR zone preserved.
   - `test_sparse_data_returning_athlete`: §13.4 shape — experienced athlete (5y training, 50-mile ultra history) + empty bundle (0 workouts/sleep/HRV) + 0 providers. Loose-enum asserts `recent_trajectory.confidence == low` (§6.2 floor rule 1 fires) + short_term direction ∈ {detrained, insufficient_data} + ACWR combined None + `confidence_clamped_by_data_density` data_gap observation present.
3. **`tests/test_layer3b_smoke.py`** (~315 LOC) — same shape for 3B via `llm_layer3b_goal_timeline_viability(...)`. Inline fixture factories (`_make_layer1` / `_make_layer3a` / `_make_layer2a` / `_make_race_event`). Two scenarios:
   - `test_ts1_ar_finisher_compressed_event_mode`: TS-1 — Andy's PGE 2026 baseline (race_event_id=1, event_date=2026-07-22, race_format=expedition_ar, event_locale_id=nerstrand-mn), 9 weeks out, `goal_outcome=Finish`, `first_time_at_distance=False`, prior AR Finished attempt. Asserts mode=event + D14 event-metadata populated from RaceEventPayload (`event_date == date(2026,7,22)` + `event_locale_id == "nerstrand-mn"` + `race_format == "expedition_ar"` + `time_to_event_weeks ∈ [8, 10]`) + viability ∈ {achievable, achievable-with-adjustment} + periodization mode ∈ {compressed, custom} + no blocker HITL.
   - `test_ts4_no_event_endurance_standard`: TS-4 — no-event mode, 24w endurance block, primary_sport=Trail Running, moderate aerobic. Asserts mode=no-event + all 4 D14 event-metadata fields None + viability ∈ {achievable, achievable-with-adjustment} + periodization mode ∈ {standard, extended} + no blocker HITL.

Test collection verification:
- Default run (`python -m pytest tests/`): `1072 passed, 4 skipped in 2.80s` ✅
- Key-set collection (`ANTHROPIC_API_KEY=fake-test python -m pytest tests/test_layer3a_smoke.py tests/test_layer3b_smoke.py --collect-only`): 4 tests collected ✅
- Wiring verification (fake key, single test): smoke test reaches `anthropic.Anthropic.messages.create()` → 401 AuthenticationError as expected (proves the production SDK adapter is invoked end-to-end, not short-circuited).

Bookkeeping: CURRENT_STATE pointer flipped; CARRY_FORWARD L3A-P-1 + L3B-P-1 partial-close annotations applied (smoke harness shipped; remaining §13 scenarios deferred); new "Layer 4 Step 7 follow-ons" section added with 6 items (single_session smoke parity + remaining 5 entry-point smoke parity + Step 8 telemetry tuning + cost-budget governance + assertion calibration loop + CI gating policy); Upstream Plan §4 Layer 4 reference updated to note Step 7 partial-shipped; this handoff.

No fixture bugs surfaced this session (inline fixtures copied the relevant subsets from `test_layer3a_builder.py:_make_layer1` / `_make_layer2a` / `_make_bundle` and `test_layer3b_builder.py:_make_layer1` / `_make_layer3a` / `_make_layer2a` / `_make_race_event` patterns verbatim).

---

## 3. File-by-file edits

### 3.1 `tests/conftest.py` (NEW, ~25 LOC)

The shared pytest fixtures module. Exposes:

- `ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"` — environment variable name constant; re-export for clarity if any future test needs the literal key name.
- `requires_anthropic_api_key = pytest.mark.skipif(not os.environ.get(ANTHROPIC_API_KEY_ENV), reason="...")` — module-level skipif marker. Applied via `pytestmark = requires_anthropic_api_key` in each smoke file → all tests in the file collect-and-skip when env var unset; collect-and-run when set. Reason string explains the gate: "set the env var to exercise the production Anthropic SDK adapter."

Module docstring explains the contract: default `pytest tests/` runs are $0 and side-effect-free; tests execute only when the key is intentionally set (local dev / CI smoke job).

### 3.2 `tests/test_layer3a_smoke.py` (NEW, ~300 LOC)

Real-LLM smoke harness for `layer3a.builder.llm_layer3a_athlete_state`. Structure:

- **Module docstring** — references `Upstream_Implementation_Plan_v1.md` §4 Layer-4-Step-7 + `Layer3A_v1.md` §12 L3A-P-1 + the two §13 scenarios picked (dense + sparse) + the assertion philosophy (mixed structural + loose-enum).
- **`pytestmark = requires_anthropic_api_key`** — module-level skipif from `conftest.py`.
- **Constants block** — `_ETL = {"0A":"v1","0B":"v1","0C":"v1"}`, `_AS_OF = datetime(2026, 5, 20, 0, 0)`.
- **Inline fixture factories**:
  - `_make_layer1(...)` — `Layer1Payload` with configurable years_structured_training / peak_weekly_volume_hrs / pushup_max_reps / cycling_ftp_w / primary_sport. Mirrors `tests/test_layer3a_builder.py:_make_layer1` subset.
  - `_make_layer2a()` — `Layer2APayload` with 4 included AR disciplines (Trail Running primary + Mountain Biking + Packrafting + Rock Climbing) — closer to Andy's PGE 2026 context than the synthetic 3-disc fixture in `test_layer3a_builder.py`.
  - `_make_bundle_dense()` — `Layer3AIntegrationBundle` with 20 workouts + 14 sleep + 14 HRV + sweet_spot ACWR (acute 8.0 / chronic 7.0 / ratio 1.14) + 2 active providers (garmin for workouts; polar for sleep + HRV).
  - `_make_bundle_sparse()` — empty bundle: 0 workouts/sleep/HRV + 0 providers + ACWR combined None.
- **`TestLayer3ASmoke`** class with 2 tests:
  - `test_dense_data_fit_athlete` — calls driver with dense bundle + 5y AR athlete; asserts structural (user_id, model="claude-sonnet-4-6", temperature=0.0, tokens > 0, latency_ms > 0, prompt_hash length 64, etl_version_set preserved) + loose-enum (aerobic_capacity.level ∈ {good, strong} + confidence ∈ {high, medium} + strength.level ∈ {moderate, good, strong} + evidence_basis non-empty + reasoning_text non-empty + ACWR sweet_spot-or-functional_overreach preserved).
  - `test_sparse_data_returning_athlete` — calls driver with empty bundle + 5y athlete; asserts tokens > 0 + `recent_trajectory.confidence == "low"` (§6.2 floor rule 1 enforced) + short_term direction ∈ {detrained, insufficient_data} + ACWR combined None + at least one data_gap/clamp observation appended by §6.3 post-LLM transform.

### 3.3 `tests/test_layer3b_smoke.py` (NEW, ~315 LOC)

Real-LLM smoke harness for `layer3b.builder.llm_layer3b_goal_timeline_viability`. Structure:

- **Module docstring** — references `Upstream_Implementation_Plan_v1.md` §4 Layer-4-Step-7 + `Layer3B_v1.md` §12 L3B-P-1 + the two TS scenarios picked (TS-1 event-mode + TS-4 no-event-mode) per handoff §6.3.
- **`pytestmark = requires_anthropic_api_key`** — module-level skipif.
- **Constants** — `_ETL`, `_AS_OF`, `_TODAY = date(2026, 5, 20)`.
- **Inline fixture factories**:
  - `_make_layer1(primary_sport=...)` — `Layer1Payload` per `test_layer3b_builder.py:_make_layer1` shape.
  - `_make_layer3a(...)` — `Layer3APayload` with configurable aerobic_level / aerobic_confidence / strength_level / strength_confidence / trajectory_confidence / short_term / medium_term. Mirrors `test_layer3b_builder.py:_make_layer3a`.
  - `_make_layer2a(framework_sport=...)` — 4 included disciplines (matches the 3A smoke fixture's discipline set).
  - `_make_race_event()` — Andy's PGE 2026 race event: `race_event_id=1`, `name="Pocket Gopher Extreme 2026"`, `event_date=date(2026, 7, 22)` (9 weeks out from 2026-05-20), `race_format="expedition_ar"`, `distance_km=Decimal("250")`, `event_locale_id="nerstrand-mn"`, `route_locales=[]`.
- **`TestLayer3BSmoke`** class with 2 tests:
  - `test_ts1_ar_finisher_compressed_event_mode` — calls driver with race_event + Finish goal + prior AR Finished attempt; asserts structural (model="claude-sonnet-4-6", tokens > 0, latency_ms > 0, prompt_hash length 64, etl_version_set preserved) + D14 event-metadata population (mode="event" + event_date == 2026-07-22 + event_locale_id == "nerstrand-mn" + race_format == "expedition_ar" + time_to_event_weeks ∈ [8, 10]) + loose-enum (viability ∈ {achievable, achievable-with-adjustment} + confidence ∈ {high, medium, low} + evidence_basis non-empty + reasoning_text non-empty + periodization mode ∈ {compressed, custom} + start_phase ∈ Base/Build/Peak/Taper) + no blocker HITL.
  - `test_ts4_no_event_endurance_standard` — calls driver with race_event_payload=None + plan_duration_weeks=24 + non_event_goal_type="endurance" + moderate aerobic; asserts tokens > 0 + mode="no-event" + all 4 D14 event-metadata fields None + viability ∈ {achievable, achievable-with-adjustment} + periodization mode ∈ {standard, extended} + no blocker HITL.

### 3.4 Bookkeeping (outside ceiling per CLAUDE.md B3)

- `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer status row 4 updated to include "Step 7 SDK smoke scaffolding (3A + 3B subset)"; Tests note 1072 → 1072 + 4 skipped; Current focus reframed to Phase 5.1 orchestrator vertical slice (architect-recommended next move now that real-LLM harness exists).
- `aidstation-sources/CARRY_FORWARD.md` — L3A-P-1 + L3B-P-1 partial-close annotations applied; new "Layer 4 Step 7 follow-ons" section with 6 items (Layer 4 single_session smoke parity / remaining 5 entry-point smoke parity / Step 8 telemetry tuning / cost-budget governance / assertion calibration loop / CI gating policy); Orthogonal track Layer 4 Step 7 line updated to 🟡 Partial (3A + 3B subset shipped).
- This handoff.

---

## 4. Code / tests

- New code: ~640 LOC across `tests/conftest.py` (~25) + `tests/test_layer3a_smoke.py` (~300) + `tests/test_layer3b_smoke.py` (~315). All test code; zero production-code changes (env-gating in `_default_llm_caller` already done by predecessor sessions).
- New tests: 4 smoke tests (2 in 3A + 2 in 3B).
- `tests/` count: 1072 → 1076 (+4); 1072 passed + 4 skipped when default (`ANTHROPIC_API_KEY` unset).
- `python -m pytest tests/ -q` → `1072 passed, 4 skipped in 2.80s` post-final-edit.
- `ANTHROPIC_API_KEY=fake-test python -m pytest tests/test_layer3*_smoke.py --collect-only -q` → `4 tests collected in 0.22s` (wiring confirmed).
- Wiring sanity: `ANTHROPIC_API_KEY=fake-test python -m pytest tests/test_layer3a_smoke.py::TestLayer3ASmoke::test_dense_data_fit_athlete -x` → `anthropic.AuthenticationError: 401 invalid x-api-key` (proves the production SDK adapter is reached end-to-end).

---

## 5. Operational sequence for Andy

N/A for code-level migrations. The new sequence for **running smoke tests locally**:

```bash
# default run — smoke tests skip cleanly (no cost)
python -m pytest tests/ -q
# → 1072 passed, 4 skipped

# real-LLM smoke run — exercises actual Sonnet 4.6 (~$0.12/run total)
export ANTHROPIC_API_KEY=sk-ant-...
python -m pytest tests/test_layer3a_smoke.py tests/test_layer3b_smoke.py -v
# → 4 passed (or 4 failed with classification details if Sonnet drifts)

# full suite with smoke
export ANTHROPIC_API_KEY=sk-ant-...
python -m pytest tests/ -q
# → 1076 passed
```

CI policy: not yet wired. Per CARRY_FORWARD §"Layer 4 Step 7 follow-ons" CI gating policy item — decide between cron job / pre-deploy gate / on-demand when production deploys begin.

The Phase 2.4-Prep operational sequence (3 SQL migrations + ETL re-run) is still the live prerequisite for the Phase 2.4 + 2.5 §5.0 walkthrough scenarios, unchanged.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Phase 5.1 orchestrator vertical slice** — `layer4/orchestrator.py` with `orchestrate_race_week_brief(db, user_id)` that (a) loads `RaceEventPayload` via `load_target_race_event_payload`; (b) calls Layer 1 builder → Layer 2A-E builders → Layer 3A → Layer 3B → `llm_layer4_race_week_brief_cached`. NOW STRUCTURALLY UNBLOCKED (all upstream LLM drivers operational + real-LLM smoke harness exists). ~5-7 files including paired `Layer4_Spec.md` §4.5 source-pointer wording fix (CARRY_FORWARD doc-nit). Opens with a `/plan-mode` gate walking orchestrator D-decisions (load order + invalidation cascade routing + error propagation shape).

### 6.2 Alternative pivots

- **Layer 4 Step 7 — remaining smoke parity** — extend the smoke harness to Layer 4's `single_session.py` + `plan_create.py` + 3 `plan_refresh` tiers + `race_week_brief.py`. Per `Layer4_Spec.md` §14.3.4 Step 7. Likely splits into 2-3 sessions of ~2-3 files each. Cumulative cost when all entry points covered: ~$0.50/full-smoke-run.
- **§H.2 / §J / §I.1 form-refresh PR** — closes L3B-P-2 (3B's deployed-shape gap) + Layer 2B + Layer 2E input-source surfaces. ~6-8 files, over ceiling — needs split.
- **Plan Management spec authorship** — de-stubs Layer 2E §5.5 heat acclim + 2E-2/3/4 open items.
- **D-73 Phase 1.4** — D-52 catalog migration sequencing.
- **Manual §5.0 walkthrough** of the accumulated 71 scenarios — the 3B AR baseline call against Andy's PGE 2026 context can now use the smoke harness as the live-data sanity check (set `ANTHROPIC_API_KEY` + run `test_ts1_ar_finisher_compressed_event_mode` against Andy's actual production data via a thin substitution of the `_make_layer1` / `_make_layer3a` / `_make_layer2a` factories with `build_layer1_payload(db, andy)` / `q_layer3a_integration_bundle(...)` / `q_layer2a_discipline_classifier_payload(...)` and the cached 3A payload).
- **Real-LLM assertion calibration loop** — first 5-10 actual Sonnet 4.6 runs surface whether loose-enum allowlists are tight enough. Quick session: tighten or loosen the allowlists per observed distribution; document the calibration history in CARRY_FORWARD. Pairs with Andy's first manual `ANTHROPIC_API_KEY=... pytest tests/test_layer3*_smoke.py` invocation.

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff; layer status row 4 includes Step 7 SDK smoke scaffolding (3A + 3B subset)
3. `aidstation-sources/CARRY_FORWARD.md` — Layer 4 Step 7 follow-ons section is new; L3A-P-1 + L3B-P-1 partial-closed
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report 1 expected ❌ forward-ref (`layer4/orchestrator.py` — Phase 5.1 forward-pointer; same drift pattern as predecessor sessions) + working-tree clean

**Runtime-env note (carries forward):** the cloud container's default `pytest` is `uv tool install` isolated Python; working path is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**Smoke test cost / running:** smoke tests only run when `ANTHROPIC_API_KEY` is set. Default `pytest tests/` skips them (1072 passed, 4 skipped). To exercise them locally: `export ANTHROPIC_API_KEY=sk-ant-... && python -m pytest tests/test_layer3*_smoke.py -v` (~$0.12/run for the 4 tests).

**If picking Phase 5.1 orchestrator vertical slice:** larger scope (~5-7 files). Opens with a `/plan-mode` gate walking orchestrator-specific D-decisions. Pair with `Layer4_Spec.md` §4.5 source-pointer wording fix (CARRY_FORWARD doc-nit). The smoke harness shipped this session can be used during orchestrator development as a live sanity check that the 3A + 3B calls still produce sensible output through the orchestrator's input-construction shape.

**If picking Layer 4 Step 7 — remaining smoke parity:** ~2-3 files per entry-point batch. Same `requires_anthropic_api_key` skipif marker; copy the inline-fixtures pattern from `test_layer3a_smoke.py` / `test_layer3b_smoke.py`. Cumulative budget when all 6 entry points covered: ~$0.50/full-smoke-run.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Layer 4 Step 7 scope = 3A + 3B subset only (architect-recommended); Layer 4 single_session + remaining 5 entry-points deferred | Andy 2026-05-20 (approved as recommended) | Same-day-after-3A+3B-drivers session focus — exercises the two production SDK call sites JUST shipped. Broader Step 7 expansion better as a focused follow-up batch. |
| 2 | D1 env-gating helper location = `tests/conftest.py` skipif marker (not a `layer4/llm_smoke.py` production helper) | Architect-pick | Test-scope only; conftest is canonical pytest location. Env-gating already inline in drivers' `_default_llm_caller` — no production helper needed. Avoids over-anticipating orchestrator needs. |
| 3 | D2 smoke entry shape = public driver entry with `llm_caller=None` (defaults to `_default_llm_caller`) | Architect-pick | Exercises full driver pipeline including post-LLM transforms (HITL auto-emit, floor clamp, periodization sanity, metadata stamping, D14 population). Bypassing driver would only test the SDK adapter shape. |
| 4 | D3 3A scenarios = dense-data fit athlete (§13.1 shape) + sparse-data returning athlete (§13.4 shape) | Architect-pick | Covers high-confidence-signal vs low-confidence-signal paths; both reasoning-quality scenarios per L3A-P-1 (§13.1 + §13.4 were specifically called out in `Layer3A_v1.md` §12). |
| 5 | D4 3B scenarios = TS-1 AR finisher compressed (event-mode, Andy's PGE 2026) + TS-4 no-event endurance (no-event-mode) | Andy 2026-05-20 (approved as recommended; matches predecessor handoff §6.3 hint) | Both modes covered (event + no-event); TS-1 mirrors Andy's actual production race; TS-4 is the clean no-event reference. |
| 6 | D5 key-absent behavior = module-level `pytest.mark.skipif` | Architect-pick | Standard pytest pattern; tests collect-and-skip when key absent; collect-and-run when set. CI clean. |
| 7 | D6 assertion stringency = mixed structural (payload validates, metadata stamped, evidence_basis non-empty, D14 fields populated/null per mode) + loose enum (allowlist sets) | Architect-pick | Pure structural misses regression signal; strict enum brittle across Sonnet 4.6 minor versions. Loose enum catches obviously-wrong classifications without breaking on minor variations. |
| 8 | D7 real-LLM budget = 4 smoke tests × ~$0.03/call ≈ $0.12/run | Architect-pick | Per handoff §6.3: "1-2 §13 fixture smoke tests on each driver". Affordable for local + ad-hoc CI runs. |
| 9 | D8 cache-wrapper smoke = SKIP (direct driver only) | Architect-pick | Cache unit-tested in `TestCacheWrapper`; smoke budget focused on real-LLM round-trips not infrastructure. |
| 10 | D9 pytest collection = default-collected `test_*_smoke.py` filenames | Architect-pick | Skipif gating means zero-cost when key absent — no special CI gating needed. Files visible in `pytest --collect-only` for discoverability. |
| 11 | Fixture sharing approach = inline fixture factories in each smoke file (not cross-test-module imports) | Architect-pick | Consistent with the codebase's no-cross-test-import convention. ~30-40 LOC duplication per smoke file is acceptable; future shared-fixture extraction is a separate refactor if/when the pattern proliferates. |
| 12 | Wiring verification = fake-key dry-run reaches `anthropic.Anthropic.messages.create()` → 401 AuthenticationError | Architect-pick (post-implementation sanity check) | Confirms the smoke test actually invokes the production SDK adapter end-to-end (not short-circuited by env-gating or some other gate). The 401 is expected with a fake key; what matters is the call site reaches the real HTTP request. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `tests/conftest.py` exists + contains `requires_anthropic_api_key = pytest.mark.skipif(...)` | ✅ inspection |
| `tests/conftest.py` references `ANTHROPIC_API_KEY` env var name | ✅ grep |
| `tests/test_layer3a_smoke.py` exists + contains `pytestmark = requires_anthropic_api_key` | ✅ grep |
| `tests/test_layer3a_smoke.py` contains `class TestLayer3ASmoke:` with `test_dense_data_fit_athlete` + `test_sparse_data_returning_athlete` | ✅ grep |
| `tests/test_layer3a_smoke.py` calls `llm_layer3a_athlete_state(...)` with no `llm_caller` kwarg (defaults to production `_default_llm_caller`) | ✅ inspection |
| `tests/test_layer3b_smoke.py` exists + contains `pytestmark = requires_anthropic_api_key` | ✅ grep |
| `tests/test_layer3b_smoke.py` contains `class TestLayer3BSmoke:` with `test_ts1_ar_finisher_compressed_event_mode` + `test_ts4_no_event_endurance_standard` | ✅ grep |
| `tests/test_layer3b_smoke.py` TS-1 fixture has `event_date=date(2026, 7, 22)` + `race_format="expedition_ar"` + `event_locale_id="nerstrand-mn"` (Andy's PGE 2026 context) | ✅ inspection |
| `tests/test_layer3b_smoke.py` TS-4 fixture has `race_event_payload=None` + `plan_duration_weeks=24` + `non_event_goal_type="endurance"` | ✅ inspection |
| `python -m pytest tests/ -q` → 1072 passed + 4 skipped (default; no ANTHROPIC_API_KEY) | ✅ `1072 passed, 4 skipped in 2.80s` |
| `ANTHROPIC_API_KEY=fake-test python -m pytest tests/test_layer3*_smoke.py --collect-only -q` → 4 tests collected | ✅ `4 tests collected in 0.22s` |
| Smoke test wiring reaches `anthropic.Anthropic.messages.create()` (verified via fake-key dry-run → 401) | ✅ `anthropic.AuthenticationError: Error code: 401` |
| `aidstation-sources/CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Layer status row 4 includes "Step 7 SDK smoke scaffolding (3A + 3B subset)" | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Tests note reads "1072 green + 4 skipped" | ✅ inspection |
| `aidstation-sources/CARRY_FORWARD.md` L3A-P-1 + L3B-P-1 partial-close annotations applied (✅ Resolved / ✅ Partial-close) | ✅ inspection |
| `aidstation-sources/CARRY_FORWARD.md` "Layer 4 Step 7 follow-ons" section landed with 6 items | ✅ inspection |
| Working tree clean after commit + push (pending) | ⏳ pending commit |

**Expected ❌ in next session's `verify-handoff.sh` [1] sweep:** 1 path flagged by the script's regex is an expected forward-reference (NOT actual drift): `layer4/orchestrator.py` — mentioned in §6.1 as the Phase 5.1 vertical-slice forward-pointer. Same drift pattern as the predecessor sessions. Treat as expected, not blocking.

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (3 files; well under the 5-file ceiling):**

1. NEW `tests/conftest.py` — shared `requires_anthropic_api_key` skipif marker + `ANTHROPIC_API_KEY_ENV` constant. ~25 LOC.
2. NEW `tests/test_layer3a_smoke.py` — 2 real-LLM smoke tests (dense + sparse) against `llm_layer3a_athlete_state` with inline fixtures. ~300 LOC.
3. NEW `tests/test_layer3b_smoke.py` — 2 real-LLM smoke tests (TS-1 event-mode + TS-4 no-event-mode) against `llm_layer3b_goal_timeline_viability` with inline fixtures. ~315 LOC.

**Bookkeeping (3 files; outside ceiling per B3):**

4. MODIFIED `aidstation-sources/CURRENT_STATE.md` — pointer flipped; Layer status row 4 updated with Step 7 SDK smoke scaffolding annotation; Tests note 1072 → 1072 + 4 skipped; Current focus reframed to Phase 5.1 orchestrator vertical slice.
5. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — L3A-P-1 + L3B-P-1 partial-close annotations applied; new "Layer 4 Step 7 follow-ons" section with 6 items; Orthogonal Layer 4 Step 7 line updated to 🟡 Partial.
6. New `aidstation-sources/handoffs/V5_Implementation_D73_Layer4_Step7_SDK_Smoke_2026_05_20_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Phase 3.1-Driver follow-ons section: `Real-LLM smoke test scaffolding (Layer 4 Step 7 territory)` struck out (✅ Resolved); `§13 real-LLM regression on the 10 spec scenarios` annotated as 2-of-10 shipped this session, remaining 8 deferred per ceiling discipline.

`CARRY_FORWARD.md` Phase 4 follow-ons section: `L3B-P-1: Real-LLM regression on §13 TS-1..TS-8 scenarios` struck out as ✅ Partial-close (2 of 8 shipped this session — TS-1 + TS-4; remaining 6 deferred).

New `CARRY_FORWARD.md` "Layer 4 Step 7 follow-ons" section with 6 items: (1) Layer 4 single_session smoke parity; (2) remaining 5 entry-point smoke parity (plan_create + 3 plan_refresh tiers + race_week_brief); (3) Step 8 telemetry tuning; (4) cost-budget governance (`-m smoke_lite` vs `-m smoke_full` split when test count crosses ~10); (5) real-LLM assertion calibration loop (tighten/loosen allowlists per observed Sonnet 4.6 distribution); (6) CI gating policy (cron / pre-deploy gate / on-demand).

Manual §5.0 walkthrough count is 71 = 69 accumulated + 1 Phase 3.1-Driver + 1 Phase 4 scenario; the 3B AR baseline call against Andy's PGE 2026 context can now use the smoke harness as the live-data sanity check vehicle once Andy sets `ANTHROPIC_API_KEY` and runs the suite locally.

Doc-sweep nits ledger unchanged. 5th deferred nit (`Layer2E_Spec.md` §6.1 + §14 D-26 wording) remains active.

---

**End of handoff.**
