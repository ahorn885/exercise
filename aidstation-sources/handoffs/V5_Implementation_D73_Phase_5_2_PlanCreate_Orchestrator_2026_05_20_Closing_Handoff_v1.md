# D-73 Phase 5.2 Slice 3 — `orchestrate_plan_create` Pattern A Orchestrator — Closing Handoff

**Session:** D-73 Phase 5.2 slice 3 — fourth and final Layer 4 entry-point orchestrator (`orchestrate_plan_create`) atop the same-day Phase 5.2 slice 1 (`orchestrate_single_session_synthesize`) + slice 2 (`orchestrate_plan_refresh` + `_upstream_full_cone` helper extract). Architect-recommended next move per predecessor handoff §6.1(a); Trigger #5 plan-mode gate before implementation. Reuses the slice 2 `_upstream_full_cone` helper as-is — slice 2's "slice 3 reuses the helper as-is" forecast confirmed.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_PlanRefresh_Orchestrator_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/phase-5-2-orchestrator-QNUwA` (harness-assigned; matches session scope this time — predecessor handoff noted name mismatch on slice 2's `claude/single-session-orchestrator-ak1PN`)
**Status:** 2 substantive files (well under 5-file ceiling); container-runnable subset 491 → 501 (+10 net new `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreate*`); production count 1158 → 1168 (+10); 4 SDK smoke tests still skip cleanly. All 40 existing race_week_brief + single_session + plan_refresh tests pass unchanged (no refactor on slice 3 — only additive). **Phase 5.2 slice 3 complete; orchestrator now exposes all 4 of 4 Layer 4 entry points** (race_week_brief 5.1 + single_session_synthesize 5.2.S1 + plan_refresh 5.2.S2 + plan_create 5.2.S3). **Phase 5.2 complete, closing Phase 5.**

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `layer4/orchestrator.py` has `orchestrate_plan_refresh` function | `grep -n "^def orchestrate_plan_refresh" layer4/orchestrator.py` | ✅ line 501 |
| `layer4/orchestrator.py` has `_UpstreamFullCone` dataclass | `grep -n "^class _UpstreamFullCone" layer4/orchestrator.py` | ✅ line 135 |
| `layer4/orchestrator.py` has `_upstream_full_cone` helper | `grep -n "^def _upstream_full_cone" layer4/orchestrator.py` | ✅ line 162 |
| `layer4/orchestrator.py` imports `Layer2Bundle` + `ParsedIntent` + `llm_layer4_plan_refresh_cached` | grep on imports | ✅ |
| `layer4/orchestrator.py` `orchestrate_race_week_brief` calls `_upstream_full_cone` | `grep -n "cone = _upstream_full_cone" layer4/orchestrator.py` | ✅ |
| `layer4/__init__.py` re-exports `orchestrate_plan_refresh` | `grep -n "orchestrate_plan_refresh" layer4/__init__.py` | ✅ (2 hits — import + `__all__`) |
| `tests/test_layer4_orchestrator.py` has 6 `TestOrchestratePlanRefresh*` classes | `grep -c "^class TestOrchestratePlanRefresh" tests/test_layer4_orchestrator.py` | ✅ 6 |
| Container-runnable subset 491 baseline at session start | `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` | ✅ (491 green; baseline verified) |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.2.S2 → ✅ Shipped 2026-05-20 | `grep -n "5.2.S2.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` | ✅ |
| `CURRENT_STATE.md` last-shipped pointer points to Phase 5.2 PlanRefresh handoff | `grep -n "Phase_5_2_PlanRefresh_Orchestrator" aidstation-sources/CURRENT_STATE.md` | ✅ |
| `CARRY_FORWARD.md` has "Phase 5.2 orchestrator follow-ons (slices 1 + 2 shipped..." section | `grep -n "Phase 5.2 orchestrator follow-ons (slices 1 + 2 shipped" aidstation-sources/CARRY_FORWARD.md` | ✅ |

`./scripts/verify-handoff.sh` flagged 7 ❌ — all pre-explained in the predecessor §1 reconciliation note as forward-pointer placeholders (not actual drift): 3 from form-refresh predecessor placeholders + 4 net-new forward-pointers from slices 1 + 2 for queued D-63/D-64 caller-side surfaces.

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state. The 7 ❌s remain after this session unchanged — slice 3 closes no caller-side placeholders (those are the queued D-63/D-64 + plan-create caller-side routes, which become the next architect-recommended arc).

---

## 2. Session narrative

Andy opened the session with the predecessor (slice 2) handoff loaded. First-session checklist ran per CLAUDE.md; reported current state + Phase 5.2 slices 1 + 2 completion + the 7 known `verify-handoff.sh` ❌s pre-explained by the predecessor.

Andy picked **Phase 5.2 slice 3 — `plan_create` Pattern A orchestrator** at the AskUserQuestion gate (over Form-refresh D, D-64 caller-side, or D-63 caller-side). Per CLAUDE.md Trigger #5 (architectural alternatives with real tradeoffs), the session entered the plan-mode gate before implementation.

The pre-implementation surface survey checked:

- `layer4/plan_create.py:llm_layer4_plan_create(...)` already exists at line 1108 (~1320 LOC); driver runs Pattern A per-phase synthesis loop + seam reviews + final cross-phase validator pass internally per `Layer4_Spec.md` §5.2; orchestrator does not see per-phase internals.
- `layer4/cached_wrappers.py:llm_layer4_plan_create_cached(...)` at line 294 — signature: first 12 positional args (user_id + 8 upstream payloads + plan_start_date + plan_version_id + etl_version_set), then `cache` + the rest kwarg-only; matches the slice 1 + slice 2 + race_week_brief precedent of "orchestrator calls cached wrapper, not raw driver."
- `_validate_plan_create_inputs(...)` at `layer4/plan_create.py:76` covers 4 driver-level preconditions: `plan_start_date_in_past`, `plan_version_id_unset` (`plan_version_id <= 0`), `time_to_event_weeks_mismatch` (3B vs `(event_date - plan_start_date) // 7`), `discipline_weights_invalid` (2A weights sum ≈ 1.0). All raise `Layer4InputError` — orchestrator does not duplicate.
- `Layer4Payload._check_mode_invariants` at `layer4/payload.py:548-552` enforces: `mode='plan_create'` requires `phase_structure` non-None + `seam_reviews` non-None. Empty `phases: list[PhaseSpec]` + empty `seam_reviews: list[SeamReview]` lists satisfy "non-None" without forcing the orchestrator test surface to construct full PhaseSpec/SeamReview rows.
- `_upstream_full_cone` at `layer4/orchestrator.py:162` already supports `target_race_event=None` (no-event-mode path for plan_refresh's slice 2 D5); plan_create reuses this verbatim — Pattern A supports open-ended plans (`race_event_payload: RaceEventPayload | None = None` per spec §3.1).
- Pre-existing `layer1/layer4` circular-import remains (per CURRENT_STATE.md historical note + all 6+ predecessor handoffs §4); verified by `git stash` round-trip that this slice does NOT introduce or worsen it.

10 D-decisions surfaced + ratified at the plan-mode gate before implementation:

- **D1: Reuse `_upstream_full_cone` as-is — no helper changes.** Slice 2's forecast confirmed: race_week_brief + plan_refresh + plan_create all consume the full cone identically (Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B → 2E). No new helpers needed; no refactor needed; single_session continues to opt out per cone-shape divergence (narrower cone with no 2B/2E/3B + `request.sport` + `request.locale_slug` + optional 2C).
- **D2: `plan_start_date: date` required kwarg (orchestrator does NOT default to today).** Driver expects non-Optional date; route handler is the right place to resolve "athlete picks future start" vs "today" per D-64 caller-side surface. Matches the driver's `_validate_plan_create_inputs` precondition that `plan_start_date >= today`.
- **D3: `plan_version_id: int` caller-supplied kwarg.** Matches slice 1 D4 + slice 2 D3 precedent for D-63/D-64 caller-side deferral. `plan_versions` table allocation belongs at route layer pending D-64 caller-side. Driver's `_validate_inputs` rejects `<= 0` so a sentinel like `1` per race_week_brief's `_RACE_WEEK_BRIEF_PLAN_VERSION_ID_PLACEHOLDER` isn't viable here — caller must allocate a real positive int (1+ acceptable; in practice the route handler will allocate row N+1 against the parent plan).
- **D4: 3 pre-flight gates only — `etl_version_set_undiscoverable` + `primary_locale_missing` + `framework_sport_missing` (all shared via `_upstream_full_cone`).** NO `no_target_event` (Pattern A supports open-ended plans — `race_event_payload=None` flows cleanly through the cone; Layer 3B's `mode='no-event'` branch handles downstream). NO `race_week_brief_too_early` (plan_create fires on demand). NO orchestrator-side `plan_start_date_in_past` / `plan_version_id_unset` / `time_to_event_weeks_mismatch` / `discipline_weights_invalid` — driver's `_validate_plan_create_inputs` covers all four per `Layer4_Spec.md` §4.2; `Layer4InputError` propagates verbatim (matches slice 1/2 + race_week_brief precedent of not wrapping driver-level errors).
- **D5: Target-race lookup conditional, not gated.** Same as slice 2 D5. Orchestrator queries `load_target_race_event_payload`; passes `race_event_payload` or `None` to the cone helper. Open-ended plans pass cleanly.
- **D6: NO `parsed_intent` kwarg.** Only plan_refresh consumes ParsedIntent (refresh-trigger context for the NL parser); plan_create has no refresh-trigger semantics.
- **D7: `today: date | None = None` kwarg mirroring race_week_brief + single_session + plan_refresh signatures.** Consistent kwarg shape across all 4 entry points; deterministic test injection.
- **D8: Orchestrator calls `llm_layer4_plan_create_cached` (not the raw driver).** Matches race_week_brief D9 + slice 1 D9 + slice 2 D8 — per-entry-point cache sits in front of the synthesizer.
- **D9: layer2c packed as `{primary_locale: payload}` dict (race_week_brief shape, NOT plan_refresh's Layer2Bundle).** Driver signature requires `dict[str, Layer2CPayload]`. v1 home-locale only (matches existing `_q_primary_locale` precedent for race_week_brief + plan_refresh); multi-locale cluster union remains spec §3 future work.
- **D10: 10 tests across 5 classes at parity with single_session test density.** Lower than plan_refresh (13) since plan_create has no `tier` dispatch dimension. HappyPath 2 (event + no-event) / PreflightGates 3 / Defaults 2 / PassThrough 2 / ReturnValue 1.

Implementation flow:

1. **Orchestrator** — Module docstring rewritten from "three-entry-point" → "four-entry-point" shape; documents the Pattern A heaviness note (per-phase synthesis loop + seam reviews + final cross-phase validator internal to driver) + the no-event-mode first-class call-out. Added `llm_layer4_plan_create_cached` to the `layer4.cached_wrappers` import block. Added new public `orchestrate_plan_create(db, user_id, *, plan_start_date: date, plan_version_id: int, cache: Layer4Cache, today: date | None = None) -> Layer4Payload`: looks up target_race conditionally → calls `_upstream_full_cone(target_race_event=race_event)` → calls `llm_layer4_plan_create_cached` with composed kwargs (individual payloads + `layer2c_payloads={primary_locale: layer2c_payload}` per D9). Existing functions untouched (no refactor). Extended `__all__` with `orchestrate_plan_create`.

2. **Re-export** — `layer4/__init__.py` re-exports `orchestrate_plan_create` alongside `orchestrate_race_week_brief` + `orchestrate_single_session_synthesize` + `orchestrate_plan_refresh` + `OrchestrationError`; `__all__` block updated.

3. **Tests** — Added 10 tests across 5 `TestOrchestratePlanCreate*` classes (`TestOrchestratePlanCreateHappyPath` 2 (event-mode pipeline-in-order + no-event-mode pipeline-in-order); `TestOrchestratePlanCreatePreflightGates` 3 (3 shared gates); `TestOrchestratePlanCreateDefaults` 2 (today defaults to `date.today()` + layer2c packed as primary-locale dict); `TestOrchestratePlanCreatePassThrough` 2 (plan_start_date + plan_version_id thread verbatim); `TestOrchestratePlanCreateReturnValue` 1 (cached-wrapper output passed through verbatim). New `_plan_create_patches(*, layer4_return)` patches the same 10 import sites as race_week_brief + plan_refresh except the cached wrapper is `llm_layer4_plan_create_cached`. New `_fake_plan_create_layer4_payload(plan_version_id)` factory constructs a valid Pattern A plan_create `Layer4Payload` satisfying mode invariants (`mode='plan_create'` requires `phase_structure` non-None + `seam_reviews` non-None; empty `phases` list + empty `seam_reviews` list both satisfy "non-None" without forcing full PhaseSpec/SeamReview rows). Imports extended (`PhaseStructure`, `orchestrate_plan_create`).

4. **Test suite** — Container-runnable subset 491 → 501 passing in ~1.3s (`pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py`). All 40 pre-existing race_week_brief + single_session + plan_refresh tests pass unchanged (no refactor on slice 3 — only additive). Verified via wider `pytest tests/ --ignore=<circular-import-blocked>` = 844 passed (no regressions in the wider tractable surface; 834 prior + 10 new).

5. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count (1158 → 1168) + current-focus arc summary + Layer 4 status row bump (4 of 4 entry points wired); `CARRY_FORWARD.md` Phase 5.2 follow-ons section: slice 3 entry struck (✅) + section header updated to "(slices 1 + 2 + 3 shipped... Phase 5.2 complete)" + new plan_create caller-side queue entry + 3A/3B caching policy entry tightened to reflect 4 consumers; `Upstream_Implementation_Plan_v1.md` §4 new row 5.2.S3; this closing handoff.

No additional `/plan-mode` triggers fired during implementation past the initial gate (no prompt body, no schema, no HITL gate, no padding refusal — D1-D10 were ratified before edits started).

---

## 3. File-by-file edits

### 3.1 `layer4/orchestrator.py` (MODIFIED, +~70 LOC net, 0 LOC removed — additive only)

- Module docstring rewritten from "Phase 5.1 race_week_brief + Phase 5.2 single_session + plan_refresh" → "Phase 5.1 race_week_brief + Phase 5.2 single_session + plan_refresh + plan_create"; documents the four-entry-point shape + Pattern A heaviness call-out (per-phase synthesis loop + seam reviews + final cross-phase validator internal to driver) + the no-event-mode first-class call-out for plan_create + plan_refresh.
- Imports: added `llm_layer4_plan_create_cached` to the `layer4.cached_wrappers` import block.
- New public `orchestrate_plan_create(db, user_id, *, plan_start_date: date, plan_version_id: int, cache: Layer4Cache, today: date | None = None) -> Layer4Payload`: see §2 narrative step 1 for the algorithm. Conditionally loads target race; calls `_upstream_full_cone(target_race_event=race_event)`; composes the cached-wrapper kwargs from the cone's fields (`layer2c_payloads={primary_locale: layer2c_payload}` per D9).
- Existing functions (`orchestrate_race_week_brief` + `orchestrate_single_session_synthesize` + `orchestrate_plan_refresh` + `_upstream_full_cone` + all private `_q_*` helpers) untouched — no refactor on slice 3.
- `__all__` updated to add `"orchestrate_plan_create"`.

### 3.2 `tests/test_layer4_orchestrator.py` (MODIFIED, +~370 LOC)

- Imports: added `orchestrate_plan_create` to the `from layer4 import (...)` block; added `PhaseStructure` to the `from layer4.payload import (...)` block.
- New helpers (after the plan_refresh test classes):
  - `_plan_create_patches(*, layer4_return)` — 10-patch stack (same shape as race_week_brief / plan_refresh `_patches()` except the final cached wrapper is `llm_layer4_plan_create_cached`). Stubs `build_layer1_payload` + `q_layer2a` + `q_layer2b` + `q_layer2c` + `q_layer2d` + `q_layer2e` + `assemble_layer3a_bundle` + `llm_layer3a` + `llm_layer3b` + `llm_layer4_plan_create_cached`.
  - `_fake_plan_create_layer4_payload(plan_version_id=3)` — returns a valid Pattern A plan_create Layer4Payload satisfying mode invariants (`mode='plan_create'` requires `phase_structure` non-None + `seam_reviews` non-None per `payload.py:548-552`). Empty `phases` list + empty `seam_reviews` list both satisfy "non-None" without forcing the orchestrator test surface to construct full PhaseSpec/SeamReview rows — those belong to `tests/test_layer4_plan_create.py`.
- 10 new tests across 5 classes:
  - `TestOrchestratePlanCreateHappyPath` (2): `test_pipeline_in_order_event_mode` (asserts D9 + cached-wrapper kwargs reflect orchestrator composition — plan_start_date + plan_version_id + cache + layer1_payload as dict + layer2c_payloads as `{home: payload}` dict + race_event_payload threads through with `race_event_id=1`); `test_pipeline_in_order_no_event_mode` (asserts D5 + open-ended plans: `load_target_race_event_payload` returns None → 2B `race_terrain=[]` + 2E `target_events=[]` + 3B `race_event_payload=None` + wrapper `race_event_payload=None`).
  - `TestOrchestratePlanCreatePreflightGates` (3): `test_etl_version_set_undiscoverable` (asserts D4: NULL `MAX(etl_version)` → `OrchestrationError('etl_version_set_undiscoverable')`); `test_primary_locale_missing` (asserts D4: missing `'home'` row → `OrchestrationError('primary_locale_missing')`); `test_framework_sport_missing` (asserts D4: empty `layer1.identity.primary_sport` → `OrchestrationError('framework_sport_missing')`).
  - `TestOrchestratePlanCreateDefaults` (2): `test_today_kwarg_defaults_to_date_today` (asserts D7: `today=None` → orchestrator uses `date.today()`; Layer 3B `current_date` kwarg threads to the resolved value); `test_layer2c_packed_as_primary_locale_dict` (asserts D9: layer2c packed as `{primary_locale: payload}` dict per race_week_brief shape, not plan_refresh's Layer2Bundle).
  - `TestOrchestratePlanCreatePassThrough` (2): `test_plan_start_date_threads_verbatim` (asserts D2: caller-supplied `plan_start_date=date(2026,7,15)` threads verbatim to the cached wrapper); `test_plan_version_id_threads_verbatim` (asserts D3: caller-supplied `plan_version_id=99` threads verbatim — no allocation at orchestrator level).
  - `TestOrchestratePlanCreateReturnValue` (1): `test_returns_cached_wrapper_output_verbatim` (asserts D8: orchestrator returns wrapper output `is` sentinel; all 10 upstream + wrapper sites fire exactly once).

### 3.3 `layer4/__init__.py` (MODIFIED, +2 LOC)

- `from layer4.orchestrator import` block extended with `orchestrate_plan_create`.
- `__all__` entry added.

(Re-export only; bookkeeping per CLAUDE.md "5-file ceiling = substantive files only" — does NOT count against the ceiling.)

---

## 4. Code / tests

**Test count delta:** 1158 → 1168 in production count (+10 net new tests, all in `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreate*` across 5 classes); 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Container-runnable subset:** 491 → 501 passing (layer4 + race_events + onboarding + locales) in ~1.3s.

Run reproducer (container-runnable subset):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py
# 501 passed in ~1.3s
```

The +10 new tests:

- `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreateHappyPath::*` (2 — event-mode + no-event-mode)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreatePreflightGates::*` (3)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreateDefaults::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreatePassThrough::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanCreateReturnValue::*` (1)

**No-refactor confirmation:** all 40 pre-existing orchestrator tests (`TestHappyPath` + `TestPreflightGates` + `TestDiscoveryFailures` + `TestDefaults` + `TestOrchestrationError` + `TestRaceTerrainAndAidStationsWireUp` + `TestLocaleTerrainIdsWireUp` + 6 × `TestOrchestrateSingleSessionSynthesize*` + 6 × `TestOrchestratePlanRefresh*`) pass unchanged. Slice 3 is purely additive — no shared helpers modified, no signatures changed.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + Phase 5.1.B/C/5.2.S1/5.2.S2 handoffs §4); verified by `git stash` round-trip that this slice did NOT introduce or worsen it — wider `pytest tests/ --ignore=<blocked>` runs at 844 passed (834 prior + 10 new).

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.2 slice 3 — plan_create orchestrator** — 3-step verification (executable once plan-create caller-side route + `plan_versions` table land):

**Step 1: Event-mode happy-path E2E (Andy's PGE 2026).** From a Python REPL or test harness (no Flask UI yet — plan-create caller-side queued):

```python
from datetime import date
from layer4 import orchestrate_plan_create, Layer4Cache, InMemoryCacheBackend
result = orchestrate_plan_create(
    db, andy_user_id,
    plan_start_date=date(2026, 4, 1),  # Andy's actual plan start
    plan_version_id=allocate_plan_versions_row(db, andy_user_id),  # caller-side
    cache=Layer4Cache(InMemoryCacheBackend()),
    today=date(2026, 5, 20),
)
```

Confirm: (a) no `OrchestrationError` raised; (b) `result.mode == 'plan_create'`; (c) `result.pattern == 'A'`; (d) `result.phase_structure` non-None with `phases` list populated (typically 3-4 phases for Andy's 15-week PGE plan: Base/Build/Peak/Taper); (e) `result.seam_reviews` non-None list (typically 2-3 seam reviews — one per phase boundary); (f) `len(result.sessions) >= 30` covering the full 15-week scope; (g) sessions all have `phase_metadata` non-None (Pattern A invariant); (h) `result.validator_results[-1].accepted == True`; (i) Layer 4 cache row created with `entry_point='plan_create'` + the slice-3 hash key.

**Step 2: Open-ended (no-event) plan E2E.** Athlete with no `is_target_event=true` race row + `plan_start_date=date(2026,6,1)` + 24-week scope (default Layer 3B no-event ceiling). Confirm: (a) no `OrchestrationError('no_target_event')` raised (this is the slice 3 D4 distinction vs race_week_brief — open-ended plans are first-class); (b) `result.mode == 'plan_create'` + `result.pattern == 'A'`; (c) Layer 3B `mode='no-event'` reflected in `notable_observations`; (d) Layer 2B emits `race_terrain_unset` coaching flag per Phase 5.1 form-refresh C loosen; (e) Layer 2E `target_events=[]` + `race_day_fueling=[]`; (f) phase_structure has `derived_from='3b_standard'` (default no-event periodization); (g) plan proceeds without crash.

**Step 3: T3 cross-phase plan_refresh E2E reuses slice 3's path.** Once D-64 caller-side lands, fire a T3 plan_refresh that spans a phase boundary against the plan created in Step 1. Confirm the driver routes to Pattern A via `_route_t3_cross_phase_to_pattern_a` (shipped at Step 4f 2026-05-18) + the same `_run_pattern_a_engine` invoked by slice 3 executes — slice 3's exercises the Pattern A engine via the cleanest entry point; T3 cross-phase exercises it via the cross-phase routing path. Both should produce structurally identical `Layer4Payload(mode=..., pattern='A', phase_structure=..., seam_reviews=...)`.

**Real-LLM cost:** ~$0.30-$0.50 per cold plan_create synthesis (3-4 per-phase synthesizer calls + 2-3 seam reviewer calls; Sonnet 4.6 + extended thinking) when `ANTHROPIC_API_KEY` set; ~$0 with mocked LLM caller. Per-entry §9.1 cache + per-phase §9.2 cache inside the engine short-circuit most repeat invocations.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**(a) D-64 caller-side route + `plan_versions` table + NL parser glue.** Makes slice 2's plan_refresh orchestrator E2E-reachable from the v1 UI. The orchestrator is structurally complete + tested in isolation but the route handler that allocates a `plan_versions` row + queries the prior session window + runs the NL parser to produce `ParsedIntent` + dispatches `tier` from athlete-supplied free text is queued. Files (est. 4-6): init_db.py `plan_versions` migration + new `routes/plan_refresh.py` + NL parser glue + templates + tests. **`/plan` gate per Triggers #1 + #3 + #5** on form copy + schema + NL parser design.

Closely related and arguably batchable: **plan-create caller-side route** can share the `plan_versions` table — combining D-64 caller-side + plan-create caller-side into one arc keeps the schema work in one slice + lets both orchestrator entry points become E2E-reachable simultaneously. Likely shape: same `plan_versions` migration + 2 route handlers (`routes/plan_refresh.py` + `routes/plan_create.py`) + 2 templates. Estimated 6-8 files; surface ratification at plan-mode gate.

### 6.2 Alternative pivots

- **D-63 caller-side route + `ad_hoc_workout_suggestions` table** — slice 1's E2E-reachability surface; ~3-4 files (init_db.py migration + new `routes/ad_hoc_workouts.py` + template + tests). `/plan` gate per Trigger #1 (form copy).
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1 + #3 + #5 — table vs JSONB schema choice).
- **Layer 3A + 3B caching policy modules at orchestrator level** — with 4 entry points now sharing user-scoped 3A/3B outputs (3 full-cone + 1 narrower), the orchestrator-level cache is near-load-bearing — a single athlete who fires plan_create + plan_refresh + race_week_brief on the same day hits the 3A driver 3 times with the same input hash. Add 3A + 3B cache wrappers + invalidation policies per `Layer3_3A_Spec.md` §9.2 + the 3B equivalent. Pair with the cache-invalidation policy modules (analogue to Layer 4's §9.3 matrix). ~4-6 files.
- **Layer 3B None-tolerant kwargs L3B-P-2** — with Form-refresh A/B/C closure, all 8 None-tolerant kwargs can flip to populated-from-payload. ~3-4 files.
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — surfaced as a doc-sweep nit during Phase 5.1 form-refresh C. ~1-2 files.
- **Manual §5.0 walkthrough** of the accumulated scenarios + all 4 orchestrator entry points end-to-end (once D-63/D-64/plan-create caller-side ship). Real-LLM ~$1-$2/pass.
- **Real-LLM Layer 4 regression** parity to race_week_brief / single_session / plan_refresh / plan_create entry points. plan_create is the heaviest at ~$0.30-$0.50/cold synthesis.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Phase 5.2 follow-ons section now reflects slices 1 + 2 + 3 all shipped, Phase 5.2 complete; D-63/D-64/plan-create caller-side wiring remain).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_PlanCreate_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Reuse `_upstream_full_cone` as-is — no helper changes | Andy ratified at plan-mode gate | Slice 2's "slice 3 reuses the helper as-is" forecast confirmed. race_week_brief + plan_refresh + plan_create all consume the full cone identically (Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B → 2E). No new helpers needed; no refactor needed; single_session continues to opt out per cone-shape divergence. |
| **D2** | `plan_start_date: date` required kwarg (orchestrator does NOT default to today) | Andy | Driver expects non-Optional date; route handler is the right place to resolve "athlete picks future start" vs "today" per D-64 caller-side surface. Matches driver's `_validate_plan_create_inputs` precondition that `plan_start_date >= today`. Orchestrator default-to-today would silently mask caller bugs. |
| **D3** | `plan_version_id: int` caller-supplied kwarg | Andy | Matches slice 1 D4 + slice 2 D3 precedent for D-63/D-64 caller-side deferral. `plan_versions` table allocation belongs at route layer pending D-64 caller-side. Driver's `_validate_inputs` rejects `<= 0` so race_week_brief's placeholder sentinel of `1` isn't viable here without committing a real row 1. |
| **D4** | 3 pre-flight gates only — `etl_version_set_undiscoverable` + `primary_locale_missing` + `framework_sport_missing` (all shared via `_upstream_full_cone`) | Andy | Minimal set. NO `no_target_event` (Pattern A supports open-ended plans — `race_event_payload=None` flows cleanly; Layer 3B's `mode='no-event'` branch handles downstream). NO `race_week_brief_too_early` (plan_create fires on demand). NO orchestrator-side `plan_start_date_in_past` / `plan_version_id_unset` / `time_to_event_weeks_mismatch` / `discipline_weights_invalid` — driver's `_validate_plan_create_inputs` covers all four per §4.2; `Layer4InputError` propagates verbatim (matches slice 1/2 + race_week_brief precedent of not wrapping driver-level errors). |
| **D5** | Target-race lookup conditional, not gated | Andy | Same as slice 2 D5. Orchestrator queries `load_target_race_event_payload`; passes `race_event_payload` or `None` to the cone helper. Open-ended plans pass cleanly. |
| **D6** | NO `parsed_intent` kwarg | Andy | Only plan_refresh consumes ParsedIntent (refresh-trigger context for the NL parser per D-64 §5.4); plan_create has no refresh-trigger semantics. Adding the kwarg would invite caller confusion + force an unused-default path. |
| **D7** | `today: date | None = None` kwarg mirroring race_week_brief + single_session + plan_refresh signatures | Andy | Consistent kwarg shape across all 4 entry points; deterministic test injection via `today=date(2026, 6, 1)`. |
| **D8** | Orchestrator calls `llm_layer4_plan_create_cached` (not raw driver) | Andy | Matches race_week_brief D9 + slice 1 D9 + slice 2 D8 — per-entry-point cache sits in front of the synthesizer; orchestrator gets per-entry §9.1 cache key for free. Pattern A's per-phase §9.2 cache also sits inside the driver, threaded via the cached wrapper. |
| **D9** | layer2c packed as `{primary_locale: payload}` dict (race_week_brief shape, NOT plan_refresh's Layer2Bundle) | Andy | Driver signature requires `dict[str, Layer2CPayload]`. v1 home-locale only matches the existing `_q_primary_locale` precedent. plan_refresh wraps differently because the driver uses a `Layer2Bundle` input shape per D-64 §5; plan_create's driver takes individual payloads + the locale-keyed 2C dict. |
| **D10** | 10 tests across 5 classes at parity with single_session test density | Andy | Lower than plan_refresh's 13 since plan_create has no `tier` dispatch dimension. 5-class organization keeps test failures isolated to a specific D-decision (e.g., a D9 regression surfaces in `TestDefaults::test_layer2c_packed_as_primary_locale_dict` only; a D5 regression in `TestHappyPath::test_pipeline_in_order_no_event_mode`). HappyPath uses 2 tests for event + no-event coverage — keeps the test count balanced (2 happy-path + 3 gates + 2 defaults + 2 pass-through + 1 return-value = 10). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/orchestrator.py` has new `orchestrate_plan_create` function | ✅ `grep -n "^def orchestrate_plan_create" layer4/orchestrator.py` returns line 589 |
| `layer4/orchestrator.py` imports `llm_layer4_plan_create_cached` | ✅ `grep -n "llm_layer4_plan_create_cached" layer4/orchestrator.py` shows import + docstring refs + call site |
| `layer4/orchestrator.py` `__all__` includes `orchestrate_plan_create` | ✅ `grep -n "\"orchestrate_plan_create\"" layer4/orchestrator.py` |
| `layer4/orchestrator.py` module docstring reflects "Four entry points" | ✅ `grep -n "Four entry points" layer4/orchestrator.py` |
| `layer4/__init__.py` re-exports `orchestrate_plan_create` (2 hits — import + `__all__`) | ✅ `grep -n "orchestrate_plan_create" layer4/__init__.py` |
| `tests/test_layer4_orchestrator.py` has 5 new `TestOrchestratePlanCreate*` classes | ✅ `grep -c "^class TestOrchestratePlanCreate" tests/test_layer4_orchestrator.py` returns 5 |
| `tests/test_layer4_orchestrator.py` has 10 net new tests in plan_create test classes | ✅ (verified via pytest collected count: 50 total — 40 pre + 10 new) |
| `tests/test_layer4_orchestrator.py` imports `orchestrate_plan_create` + `PhaseStructure` | ✅ `grep -n "orchestrate_plan_create\|    PhaseStructure," tests/test_layer4_orchestrator.py` |
| Existing race_week_brief + single_session + plan_refresh tests pass unchanged | ✅ All 40 pre-existing orchestrator tests pass in the same `pytest tests/test_layer4_orchestrator.py` run |
| Container-runnable subset green at 501 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` reports 501 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has new row 5.2.S3 → ✅ Shipped 2026-05-20 | ✅ `grep -n "5.2.S3.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 PlanCreate handoff | ✅ `grep -n "Phase_5_2_PlanCreate_Orchestrator" aidstation-sources/CURRENT_STATE.md` |
| `CURRENT_STATE.md` tests count flipped 1158 → 1168 | ✅ `grep -n "1168 green" aidstation-sources/CURRENT_STATE.md` |
| `CARRY_FORWARD.md` Phase 5.2 follow-ons section reflects slices 1 + 2 + 3 shipped | ✅ `grep -n "Phase 5.2 orchestrator follow-ons (slices 1 + 2 + 3 shipped" aidstation-sources/CARRY_FORWARD.md` |

---

## 9. Files shipped this session

**Substantive (2 files; well under 5-file ceiling):**

1. MODIFIED `layer4/orchestrator.py` (+~70 LOC net) — new public `orchestrate_plan_create(db, user_id, *, plan_start_date, plan_version_id, cache, today=None)` entry point; added `llm_layer4_plan_create_cached` to the `layer4.cached_wrappers` import block; module docstring rewritten from "three-entry-point" → "four-entry-point" shape + Pattern A heaviness note + no-event-mode first-class call-out; `__all__` extended.
2. MODIFIED `tests/test_layer4_orchestrator.py` (+~370 LOC) — 10 tests across 5 `TestOrchestratePlanCreate*` classes; new `_plan_create_patches()` + `_fake_plan_create_layer4_payload()` helpers; imports extended (`orchestrate_plan_create`, `PhaseStructure`).

**Bookkeeping (4 files):**

3. MODIFIED `layer4/__init__.py` — re-export `orchestrate_plan_create` + `__all__` entry.
4. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flip + tests count + current-focus arc summary + Layer 4 status row bump (4 of 4 entry points wired) + D-73 arc summary update (Phase 5.2 complete).
5. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Phase 5.2 follow-ons section: slice 3 ✅ + section heading updated to "slices 1 + 2 + 3 shipped... Phase 5.2 complete"; new plan_create caller-side queue entry; 3A/3B caching policy entry tightened to reflect 4 consumers.
6. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row 5.2.S3.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_PlanCreate_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes in this session:

- "Phase 5.2 orchestrator follow-ons" section header updated to reflect slices 1 + 2 + 3 shipped + Phase 5.2 complete (was "slices 1 + 2 shipped").
- Slice 3 follow-on entry struck (✅ Shipped 2026-05-20).
- New plan_create caller-side queue entry added (parallel to the existing D-63 + D-64 caller-side entries; notes that the `plan_versions` table can be shared with D-64 caller-side).
- 3A + 3B caching policy entry tightened: "with 4 entry points now sharing user-scoped 3A outputs (3 full-cone + 1 narrower), the orchestrator-level cache is near-load-bearing" (was "becomes load-bearing soonest at slice 3").

Phase 5.2 slice 3 closes the 10 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions.

**Phase 5.2 slice 3 complete; orchestrator now exposes all 4 of 4 Layer 4 entry points (race_week_brief 5.1 + single_session_synthesize 5.2.S1 + plan_refresh 5.2.S2 + plan_create 5.2.S3). Phase 5.2 complete, closing Phase 5.** Remaining: caller-side route surfaces (D-63 + D-64 + plan-create) for E2E reachability.

---

**End of handoff.**
