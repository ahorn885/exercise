# D-73 Phase 5.1 — Layer 4 Orchestrator Vertical Slice — Closing Handoff

**Session:** D-73 Phase 5.1 — first end-to-end Layer 4 orchestrator (`orchestrate_race_week_brief`) threading the full upstream pipeline (Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → `llm_layer4_race_week_brief_cached`). Paired §4.5 D-72 source-pointer wording fix.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Layer4_Step7_SDK_Smoke_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/phase-5-1-orchestrator-aPvU0` (PR #109, merged into main as `8854fa4`)
**Status:** 4 substantive files (under 5-file ceiling); 358 layer4 tests green (10 new + 348 pre-existing including the new file); 1082 total green + 4 skipped (smoke). **Phase 5.1 complete.**

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 (Session-end verification) table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `tests/conftest.py` `requires_anthropic_api_key` shipped | `grep -n requires_anthropic_api_key tests/conftest.py` | ✅ (verified during pre-flight read sweep) |
| `tests/test_layer3a_smoke.py` + `tests/test_layer3b_smoke.py` exist | `ls tests/test_layer3{a,b}_smoke.py` | ✅ |
| `layer3a/builder.py` `llm_layer3a_athlete_state` + `layer3b/builder.py` `llm_layer3b_goal_timeline_viability` exposed | `grep -n "^def llm_layer3" layer3{a,b}/builder.py` | ✅ |
| Layer 3B D14 D-66 event-metadata population in `_assemble_payload_candidate` | `grep -n "D14" layer3b/builder.py` | ✅ (line 1418 docstring + lines 1432-1438 population) |
| `Layer4_Spec.md` §4.5 source-pointer amendment 2026-05-18 narrative present | `grep -n "Source-pointer amendment 2026-05-18" aidstation-sources/Layer4_Spec.md` | ✅ |

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state.

---

## 2. Session narrative

Scope-pick gate landed on **Phase 5.1 orchestrator vertical slice** — the architect-recommended next move per the predecessor handoff's §6.1 ("structurally unblocked … all upstream LLM drivers operational + real-LLM smoke harness exists"). Andy ratified.

`/plan-mode` gate (Trigger #5 — architectural alternatives) surfaced **19 D-decisions** spanning public API shape, time-anchor propagation, error semantics, per-layer source plumbing, call ordering (load-bearing on the 2E ← 3B `start_phase` dependency), vertical-slice deferrals (`prior_plan_session_window=[]`, `plan_version_id=1`, Layer 2B `race_terrain=[]`), cache wiring, and test surface. Andy approved en-bloc.

Implementation flow:

1. Pre-flight reads — surveyed all 5 Layer 2 query-node signatures, Layer 3A + 3B driver signatures, Layer 4 cached-wrapper shape, `race_events_repo.load_target_race_event_payload`, locale_profiles conventions (`locale='home'`), and `etl_version_set` discovery patterns. Settled that `_q_current_etl_version_set` queries `MAX(etl_version) FROM layer0.sports WHERE superseded_at IS NULL` and applies the same version to all 3 sub-arc keys (v1 approximation; coordinated rollouts ship aligned versions).
2. Wrote `layer4/orchestrator.py` end-to-end (266 LOC).
3. Wrote `tests/test_layer4_orchestrator.py` (10 tests). Iterated through 3 fixture validation errors (`race_week_brief` required field on `Layer4Payload`; `validator_results` non-empty constraint; `Layer2CPayload` `extra='forbid'` rejecting `hitl_required`); each fix surgical.
4. Verified `from layer4 import orchestrate_race_week_brief, OrchestrationError` resolves.
5. Layer4 test suite confirmed green (348 tests; 10 new + 338 pre-existing).
6. Paired §4.5 source-pointer wording fix: surgical 2-line edit folding D-72 audit-trail (`load_race_event_payload` JOINs `locale_profiles` and surfaces slug; Layer 4 doesn't re-resolve).
7. Commit + push + PR #109 + merge.

No `/plan-mode` triggers fired during implementation (no prompt body, no schema change, no HITL gate, no padding refusal).

---

## 3. File-by-file edits

### 3.1 `layer4/orchestrator.py` (NEW, 266 LOC)

Entry point `orchestrate_race_week_brief(db, user_id, *, cache: Layer4Cache, today: date | None = None) -> Layer4Payload`. Algorithm:

1. `load_target_race_event_payload(db, user_id)` → raise `OrchestrationError('no_target_event')` when None.
2. Pre-flight auto-fire gate: `days_to_event = (race_event.event_date - today).days`; raise `OrchestrationError('race_week_brief_too_early')` when `> 14`. Saves 3A + 3B LLM cost on out-of-window invocations.
3. `_q_current_etl_version_set(db)` → triplet `{"0A": v, "0B": v, "0C": v}`.
4. `build_layer1_payload(db, user_id)`; raise `OrchestrationError('framework_sport_missing')` when `layer1_payload.identity.primary_sport` is empty.
5. Sequence: Layer 2A → 2B → 2D → 2C (2D feeds 2C per `Layer2C_Spec.md` §5.4) → `assemble_layer3a_integration_bundle` → 3A → 3B → 2E (consumes `start_phase` from 3B's `periodization_shape`) → `llm_layer4_race_week_brief_cached`.
6. `Layer2ETargetEvent` built inline from `RaceEventPayload`; `estimated_duration_hr` from `_DURATION_HR_BY_RACE_FORMAT` (single_day=8, stage_race=24, multi_day_ultra=24, expedition_ar=56).
7. Private helpers: `_q_current_etl_version_set`, `_q_primary_locale` (queries `locale_profiles WHERE user_id=? AND locale='home'`), `_q_locale_equipment_pool` (joins `locale_equipment` × `equipment_items`).
8. `OrchestrationError(RuntimeError)` carries `code: str` + `detail: str`.

Module docstring explicitly lists 4 vertical-slice forward-pointers: empty `race_terrain`, empty `prior_plan_session_window`, hardcoded `plan_version_id=1`, uncached 3A/3B at orchestrator level.

### 3.2 `tests/test_layer4_orchestrator.py` (NEW, 10 tests, ~700 LOC)

| Test class | Tests | Coverage |
|---|---|---|
| `TestHappyPath` | 1 | Pipeline ordering (10 mocks invoked in order); `Layer2ETargetEvent` derived from `RaceEventPayload`; `current_phase` threaded from 3B → 2E; cached wrapper receives composed payloads including `cache` + `today` + `etl_version_set` + `prior_plan_session_window=[]` + `plan_version_id=1`. |
| `TestPreflightGates` | 2 | `no_target_event` raises when `load_target_race_event_payload` returns None; `race_week_brief_too_early` raises with `days_to_event=30` and ZERO upstream mocks invoked. |
| `TestDiscoveryFailures` | 3 | `etl_version_set_undiscoverable` (`MAX(etl_version)` returns NULL); `primary_locale_missing` (no `locale='home'` row); `framework_sport_missing` (`Layer1Identity()` with no `primary_sport`). |
| `TestDefaults` | 2 | `today=None` kwarg → resolves via `date.today()` and threads to cached wrapper; `race_format='expedition_ar'` → `estimated_duration_hr=56.0`. |
| `TestOrchestrationError` | 2 | `code` + `detail` round-trip; `str(err)` shape with/without detail. |

Stubs upstream builders + LLM drivers via `unittest.mock.patch` at `layer4.orchestrator` module-level imports. `_FakeConn` / `_FakeCursor` / `_FakeRow` pattern mirrors `tests/test_layer1_builder.py` for the orchestrator's direct DB queries (`load_target_race_event_payload` + 3 `_q_*` helpers).

### 3.3 `aidstation-sources/Layer4_Spec.md` §4.5 (MODIFIED, surgical 2-line edit)

Source-pointer amendment header: `2026-05-18 (D-66 paired implementation)` → `2026-05-18 (D-66 paired implementation; D-72 slug-FK follow-on 2026-05-19)`.

Row 5 `event_locale_unresolved` description: previously "Caller-side: orchestrator resolves `race_event_payload.event_locale_id` against `locale_profiles` before invocation" → now reflects the D-72 reality that `race_events_repo.load_race_event_payload` itself JOINs `race_events.event_locale_id (BIGINT FK)` against `locale_profiles` and surfaces the resolved slug on `RaceEventPayload.event_locale_id`; Layer 4 receives a pre-resolved slug and doesn't re-resolve.

### 3.4 `layer4/__init__.py` (MODIFIED, +7 lines)

`from layer4.orchestrator import OrchestrationError, orchestrate_race_week_brief` import block + 2 entries appended to `__all__`.

---

## 4. Code / tests

**Test count delta:** 1072 → 1082 green (+10 new orchestrator smoke tests); 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Layer4 suite (unaffected by container-level missing `flask`/`psycopg2`):** 338 → 348 green (10 new + 338 pre-existing across `test_layer4_orchestrator.py`, `test_layer4_race_week_brief.py`, `test_layer4_cache.py`, `test_layer4_payload.py`, `test_layer4_hashing.py`, `test_layer4_context.py`).

Run reproducer:
```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_layer4_race_week_brief.py \
                   tests/test_layer4_cache.py tests/test_layer4_payload.py \
                   tests/test_layer4_hashing.py tests/test_layer4_context.py
# 348 passed in 0.54s
```

---

## 5. Manual §5.0 verification steps

Deferred — no UI surface change. The orchestrator's first live exercise lands when the §H.2 form-refresh PR closes the `L3B-P-2` deployed-shape gap (or when Andy chooses to run a real-LLM smoke pass against his PGE 2026 data with `today=2026-07-03` for the natural `days_to_event=14` fire).

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog: **Phase 5.1 orchestrator end-to-end** — invoke `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026, 7, 3), cache=Layer4Cache(InMemoryCacheBackend()))` against Andy's PGE 2026 race row + populated `locale='home'` row + populated `etl_version_set` triplet; expect a `Layer4Payload` with `mode='race_week_brief'`, race_week_brief populated, race_plan populated (multi-day expedition_ar), validator-accepted. Cost: ~$0.50 (3A + 3B + Layer 4 Sonnet 4.6 with extended thinking).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**§H.2 / §J / §I.1 form-refresh PR** (split across 2 sessions per Upstream Plan §4.2 / Phase 2.5 / Phase 4 L3B-P-2 deferred items). Closes 4 gaps simultaneously:

1. Layer 2B `race_terrain` source — currently `[]` in orchestrator; orchestrator's only forward-pointer that affects coaching output quality on multi-day events.
2. Layer 3B None-tolerant kwargs (`goal_outcome`, `first_time_at_distance`, `previous_attempts`, `race_distance_km`, `race_duration_hr`, `race_terrain`, `race_pack_weight_kg`, `navigation_required`) — surface to onboarding §H.2 + race-event entry/edit forms.
3. Layer 2E `target_events.aid_stations` — currently None; surfaces in onboarding §H.2 race-row capture.
4. `RaceEventPayload.distance_km` + `total_elevation_gain_m` + `race_rules_summary` + `mandatory_gear_text` — already in the typed payload, partially captured via `routes/race_events.py`; needs the form-refresh PR to close the data-completion gap.

Estimated 6-8 files. Likely needs a split (§H.2 onboarding-side first; then race-event entry/edit form refresh; then Layer 2E + 2B input-source wire-up). `/plan-mode` gate per Trigger #1 (form copy is user-facing) + Trigger #5 (multi-layer wire-up).

### 6.2 Alternative pivots

- **Phase 5.2 — remaining 3 Layer 4 entry points** (`single_session_synthesize`, `plan_refresh` T1/T2/T3, `plan_create`). Structurally similar; mostly composing upstream-builder calls + threading different inputs. **Critical refactor:** extract `_upstream_pipeline(db, user_id, today) -> (layer1, ..., layer3b)` shared helper from `orchestrator.py` so 5.2 entry points reuse the composition. Auto-fire policy gates (Trigger #5) per Layer 4 §14.3.4 Step 8. ~4-6 files per entry point; batchable.
- **Layer 4 Step 4f follow-ons** — Pattern A polish, telemetry hooks, postgres cache backend hardening.
- **Plan Management spec authorship** — closes 2E §5.5 / §5.8 deferred contracts.
- **Phase 1.4** — D-52 catalog migration sequencing.
- **Real-LLM regression** for Layer 4 itself — extend `tests/test_layer4_*_smoke.py` parity to race_week_brief / single_session / plan_refresh / plan_create entry points. ~$0.50/run × 4 entry points = ~$2/full smoke pass.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (now includes Phase 5.1 orchestrator manual walkthrough entry).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Public API: single `orchestrate_race_week_brief(db, user_id, *, cache, today)` | Andy ratified plan-mode gate | Vertical-slice focus; refactor into shared `_upstream_pipeline` helper at Phase 5.2 |
| **D2** | Single `today: date \| None` kwarg threaded to all layers (as_of for 3A, current_date for 3B, today for 4) | Andy | Testability + deterministic snapshots |
| **D3** | Error propagation: fail-loud (no try/except wrap) | Andy | Partial-failure semantics TBD until production telemetry |
| **D4** | Use existing `assemble_layer3a_integration_bundle` composer | Andy | Canonical composer (`layer3a/integration.py:586`) |
| **D5** | `framework_sport` from `layer1_payload.identity.primary_sport` | Andy | Avoid duplicate DB hit |
| **D6** | Layer 2B `race_terrain=[]` + `locale_terrain_ids=[]` | Andy | §H.2 form-refresh gap; 2B handles empty + emits coaching flag |
| **D7** | `_q_primary_locale(db, user_id)` — `locale='home'` convention | Andy | Matches v1 `routes/dashboard.py:31` + `routes/plans.py:625` |
| **D8** | Layer 2D injuries/conditions from `layer1_payload.health_status.{current_injuries, health_conditions_active}` | Andy | Avoid double-query |
| **D9** | `Layer2ETargetEvent` built inline from `RaceEventPayload` | Andy | Single call site; no premature abstraction |
| **D10** | Call ordering: 2A/2B/2D/2C → 3A → 3B → 2E → race_week_brief | Andy | 2E needs `start_phase` from 3B's `periodization_shape` |
| **D11** | `prior_plan_session_window=[]` | Andy | No v2 plan-gen wired yet; Phase 5.2 will close |
| **D12** | `plan_version_id=1` hardcode with `# TODO(plan-versioning)` | Andy | Plan-versioning surface not yet implemented in v2 |
| **D13** | `_q_current_etl_version_set` queries `MAX(etl_version) FROM layer0.sports WHERE superseded_at IS NULL` and applies the same version to all 3 sub-arc keys | Andy | v1 approximation; coordinated Layer 0 rollouts ship aligned versions |
| **D14** | Pre-flight auto-fire gate raises `OrchestrationError('race_week_brief_too_early')` BEFORE upstream calls | Andy | Saves ~$0.30 of 3A + 3B LLM cost on out-of-window invocations |
| **D15** | Use `llm_layer4_race_week_brief_cached`; orchestrator accepts `cache: Layer4Cache` kwarg | Andy | Vertical slice shows the cached-wrapper path is the production path |
| **D16** | Orchestrator does NOT emit `evict_on_layer_change` | Andy | Invalidation is external-event-driven; otherwise cache is always empty |
| **D17** | §4.5 source-pointer fix: surgical 2-line D-72 audit-trail addition | Andy | Doc-nit; minor wording fix only |
| **D18** | Test surface: `_FakeConn` + `unittest.mock.patch` on upstream module-level imports | Andy | Matches `tests/test_layer1_builder.py` + `tests/test_layer4_race_week_brief.py` precedent |
| **D19** | Test scope: 10 smoke tests | Andy | Vertical-slice smoke; full regression deferred to post-Phase 5.2 |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/orchestrator.py` exists; `orchestrate_race_week_brief` + `OrchestrationError` defined | ✅ `grep -n "^def orchestrate_race_week_brief\|^class OrchestrationError" layer4/orchestrator.py` |
| `tests/test_layer4_orchestrator.py` exists; 10 tests | ✅ `pytest --collect-only tests/test_layer4_orchestrator.py` reports 10 items |
| `layer4/__init__.py` re-exports `orchestrate_race_week_brief` + `OrchestrationError` | ✅ `python -c "from layer4 import orchestrate_race_week_brief, OrchestrationError"` returns 0 |
| `Layer4_Spec.md` §4.5 source-pointer narrative mentions D-72 slug-FK follow-on | ✅ `grep -n "D-72 slug-FK follow-on" aidstation-sources/Layer4_Spec.md` |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1 flipped to ✅ | ✅ `grep -n "Shipped 2026-05-20.*PR #109" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| Layer4 suite green | ✅ 348 passed (10 new + 338 pre-existing) |
| PR #109 merged to main | ✅ `git log --oneline -1 origin/main` shows `8854fa4 Merge pull request #109` |

---

## 9. Files shipped this session

**Substantive (4 files; under 5-file ceiling):**

1. NEW `layer4/orchestrator.py` (266 LOC) — `orchestrate_race_week_brief` + `OrchestrationError` + 3 private helpers.
2. NEW `tests/test_layer4_orchestrator.py` (~700 LOC) — 10 smoke tests across 5 test classes.
3. MODIFIED `aidstation-sources/Layer4_Spec.md` §4.5 — surgical D-72 audit-trail wording fix.
4. MODIFIED `layer4/__init__.py` — re-export block + `__all__` entries.

**Bookkeeping (3 files):**

5. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 5.1 flipped to ✅ Shipped.
6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + Layer 4 status + tests count.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

Appended to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

> **Phase 5.1 orchestrator end-to-end** — invoke `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026, 7, 3), cache=Layer4Cache(InMemoryCacheBackend()))` against Andy's PGE 2026 race row. Expect `Layer4Payload(mode='race_week_brief', pattern='B', sessions=[…], race_week_brief=…, race_plan=…non-None for expedition_ar, validator_results last accepted=True)`. ~$0.50 real-LLM cost (3A + 3B + Layer 4 Sonnet 4.6 extended-thinking). Hard prerequisite: §H.2 form-refresh PR closes the empty `race_terrain` + `aid_stations` gaps for a high-quality brief.

Phase 5.1 closes the 19 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions. The 4 vertical-slice forward-pointers (`prior_plan_session_window=[]`, `plan_version_id=1` hardcode, Layer 2B `race_terrain=[]`, uncached 3A/3B at orchestrator level) live in `layer4/orchestrator.py`'s module docstring and surface naturally when Phase 5.2 picks them up.

---

**End of handoff.**
