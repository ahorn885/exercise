# D-73 Phase 5.2 Slice 2 — `orchestrate_plan_refresh` + `_upstream_full_cone` Helper Extract — Closing Handoff

**Session:** D-73 Phase 5.2 slice 2 — third Layer 4 entry-point orchestrator (`orchestrate_plan_refresh`) atop the same-day Phase 5.2 slice 1 (`orchestrate_single_session_synthesize`). Architect-recommended next move per predecessor handoff §6.1(a); Trigger #5 plan-mode gate before implementation. Andy flipped D1 from architect-recommended defer-to-slice-3 to extract-now — `_upstream_full_cone` helper extracted in this session, race_week_brief refactored to consume (behavior-preserving).
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_SingleSession_Orchestrator_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/single-session-orchestrator-ak1PN` (harness-pinned; branch name reflects the slice 1 arc but the session scope is slice 2; not renamed per task instructions "NEVER push to a different branch without explicit permission")
**Status:** 2 substantive files (well under 5-file ceiling); container-runnable subset 478 → 491 (+13 net new `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefresh*`); production count 1145 → 1158 (+13); 4 SDK smoke tests still skip cleanly. All 17 existing race_week_brief tests pass unchanged after the helper-extract refactor (behavior-preserving). **Phase 5.2 slice 2 complete; orchestrator now exposes 3 of 4 Layer 4 entry points** (race_week_brief 5.1 + single_session_synthesize 5.2.S1 + plan_refresh 5.2.S2).

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `layer4/orchestrator.py` has `orchestrate_single_session_synthesize` | `grep -n "^def orchestrate_single_session_synthesize" layer4/orchestrator.py` | ✅ line 269 |
| `layer4/orchestrator.py` has `_q_locale_by_slug` helper | `grep -n "^def _q_locale_by_slug" layer4/orchestrator.py` | ✅ line 451 |
| `layer4/orchestrator.py` imports `Layer2AInputError` + `SingleSessionRequest` + `llm_layer4_single_session_synthesize_cached` | `grep -n "Layer2AInputError\|SingleSessionRequest\|llm_layer4_single_session_synthesize_cached" layer4/orchestrator.py` | ✅ |
| `layer4/orchestrator.py` catches `Layer2AInputError` + re-raises as `OrchestrationError('request_sport_unavailable')` | `grep -n "except Layer2AInputError\|request_sport_unavailable" layer4/orchestrator.py` | ✅ |
| `layer4/orchestrator.py` raises `OrchestrationError('locale_unknown')` when `_q_locale_by_slug` returns False | `grep -n "locale_unknown" layer4/orchestrator.py` | ✅ |
| `layer4/orchestrator.py` `__all__` includes `orchestrate_single_session_synthesize` | `grep -n "\"orchestrate_single_session_synthesize\"" layer4/orchestrator.py` | ✅ |
| `layer4/__init__.py` re-exports `orchestrate_single_session_synthesize` (2 hits — import + `__all__`) | `grep -n "orchestrate_single_session_synthesize" layer4/__init__.py` | ✅ |
| `tests/test_layer4_orchestrator.py` has 6 `TestOrchestrateSingleSessionSynthesize*` classes | `grep -c "^class TestOrchestrateSingleSessionSynthesize" tests/test_layer4_orchestrator.py` | ✅ 6 |
| Container-runnable subset 478 baseline at session start | `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` | ✅ (478 green; baseline verified) |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.2.S1 → ✅ Shipped 2026-05-20 | `grep -n "5.2.S1.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` | ✅ |
| `CURRENT_STATE.md` last-shipped pointer points to Phase 5.2 SingleSession handoff | `grep -n "Phase_5_2_SingleSession_Orchestrator" aidstation-sources/CURRENT_STATE.md` | ✅ |
| `CARRY_FORWARD.md` has "Phase 5.2 orchestrator follow-ons" section | `grep -n "Phase 5.2 orchestrator follow-ons" aidstation-sources/CARRY_FORWARD.md` | ✅ |

`./scripts/verify-handoff.sh` flagged 7 ❌ — all pre-explained in the predecessor §1 reconciliation note as forward-pointer placeholders (not actual drift): 3 from form-refresh predecessor placeholders (`migrations/migrate_locale_terrain_ids.sql`, `templates/onboarding/_race_terrain_editor.html`, `templates/profile/...locale_edit...html`) + 4 net-new forward-pointers from slice 1 for queued follow-ons (`layer4/_upstream_pipeline.py`, `routes/ad_hoc_workouts.py`, `templates/workouts/single_session_request.html`, `templates/workouts/single_session_view.html`).

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state. The 7 ❌s remain after this session — slice 2 closes the `_upstream_pipeline.py` forward-pointer NOT by creating that file (the helper landed inline in `orchestrator.py` per the D1 inline-default rationale from the predecessor §6.1(a)) but by extracting it into the same module. The 7th `_upstream_pipeline.py` placeholder will sit until the verify-handoff script's anchor list is refreshed — folding the dead pointer is bookkeeping for the next session.

---

## 2. Session narrative

Andy opened the session with the predecessor (slice 1) handoff loaded. First-session checklist ran per CLAUDE.md; reported current state + Phase 5.2 slice 1 completion + the 7 known `verify-handoff.sh` ❌s pre-explained by the predecessor.

Andy picked **Phase 5.2 slice 2 — `plan_refresh` T1/T2/T3 orchestrator** at the AskUserQuestion gate (over slice 3, Form-refresh D, or the routes/locales.py 2C invalidation nit). Per CLAUDE.md Trigger #5 (architectural alternatives with real tradeoffs), the session entered the plan-mode gate before implementation.

The pre-implementation surface survey checked:

- `layer4/plan_refresh.py:llm_layer4_plan_refresh(...)` already exists at line 782 (~1222 LOC); driver internally dispatches T1/T2/T3 via the `tier` kwarg + routes T3 cross-phase to Pattern A via `_route_t3_cross_phase_to_pattern_a` (shipped at Step 4f 2026-05-18 per the closing handoff that named row 4f).
- `layer4/plan_refresh_t1.py` / `_t2.py` / `_t3.py` are tier-specific prompt+schema modules; the dispatch happens in `plan_refresh.py`.
- `layer4/cached_wrappers.py:llm_layer4_plan_refresh_cached(...)` at line 180 — 1:1 with driver signature; matches the slice 1 + race_week_brief precedent of "orchestrator calls cached wrapper, not raw driver."
- `Layer4_Spec.md` §3.2 documents the entry-point contract (signature + parameters); `Plan_Refresh_D64_Design_v1.md` §3 documents tier semantics + dispatch rules; no separate orchestrator-side composer spec.
- `ParsedIntent` already in `layer4/context.py` at line 1176 (D-64 §5.2 NL parser output); accepts `None` per D-64 §5.4 graceful-degradation contract.
- `Layer2Bundle` at `layer4/context.py:1159` — D-64 driver expects packed bundle shape (5 fields: a/b/c/d/e where c is dict keyed by locale).
- Pre-existing `layer1/layer4` circular-import remains (per CURRENT_STATE.md historical note + all 5+ predecessor handoffs §4); verified by `git stash` round-trip that this slice does NOT introduce or worsen it.

10 D-decisions surfaced + ratified at the plan-mode gate before implementation:

- **D1: extract `_upstream_full_cone` helper now + refactor race_week_brief to consume.** Andy flipped from architect's defer-to-slice-3 recommendation (predecessor §6.1(a) said Rule of Three lands at slice 3 because slice 2 only adds the 2nd full-cone consumer). Andy's pick: extract now even though only 2/3 full-cone consumers exist — single_session opts out per cone-shape divergence (narrower cone; uses `request.sport` not `primary_sport`; uses `request.locale_slug` not `'home'`; optional 2C; no 2B/2E/3B). Helper covers shared pre-flight gates + Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B → 2E composition.
- **D2: tier as required kwarg from caller (D-64 dispatch happens at route layer, not orchestrator).** Avoids embedding D-64 dispatch logic in Layer 4; keeps orchestrator a thin composer; matches the D-64 design where tier classification happens before orchestration via the NL parser route handler.
- **D3: `plan_version_id` + `plan_version_id_parent` + `prior_plan_session_window` + `parsed_intent` + `plan_start_date` all caller-supplied kwargs.** Matches slice 1 D4 precedent for D-63's `suggestion_id` (caller-supplied because the persistence table isn't shipped); same pattern applies for the v2 `plan_versions` table.
- **D4: 3 pre-flight gates only** — `etl_version_set_undiscoverable`, `primary_locale_missing`, `framework_sport_missing` (all shared with race_week_brief, all raised inside `_upstream_full_cone`). NO `no_target_event` (no-event refresh supported — race_event_payload=None flows to L3B; Layer 2B accepts race_terrain=[] per Phase 5.1 form-refresh C loosen; Layer 2E gets empty target_events). NO `race_week_brief_too_early` (refresh fires on demand, not on a calendar window). Driver's own `_validate_inputs` covers tier/refresh_scope/plan_version_id_parent/plan_start_date validity — `Layer4InputError` propagates verbatim (matches slice 1's pattern of not wrapping driver errors).
- **D5: target-race lookup is conditional, not gated.** Orchestrator queries the target race row via `load_target_race_event_payload`; passes `race_event_payload` or `None` to the upstream cone helper. No-event-mode plans refresh fine without a race.
- **D6: `parsed_intent: ParsedIntent | None` pass-through.** Orchestrator does not construct a default ParsedIntent when caller omits — None passes through per D-64 §5.4 graceful-degradation contract.
- **D7: `today: date | None = None` kwarg mirroring race_week_brief + single_session signatures.** Same shape across all 3 entry points; deterministic test injection.
- **D8: orchestrator calls `llm_layer4_plan_refresh_cached` (not the raw driver).** Matches slice 1 D9 + race_week_brief D9 — per-entry-point cache sits in front of the synthesizer.
- **D9: single function `orchestrate_plan_refresh(tier=...)` not 3 per-tier functions (`_t1`/`_t2`/`_t3`).** Mirrors driver's internal dispatch on the `tier` kwarg; avoids 3x duplication in the orchestrator. The route handler picks tier upstream.
- **D10: 13 tests across 6 classes at parity with single_session test density** (HappyPath parametrized T1/T2/T3 + parsed_intent threading = 4 / PreflightGates 3 / NoEventMode 1 / Defaults 2 / TierPassThrough 2 / ReturnValue 1).

Implementation flow:

1. **Orchestrator** — Rewrote module docstring from "two-entry-point" → "three-entry-point" shape; documented the helper-extract decision + the cone-shape variance reasoning for single_session opting out. Added imports: `dataclass` from dataclasses; `Literal` from typing; payload types (`Layer1Payload`, `Layer2APayload`, `Layer2BPayload`, `Layer2Bundle`, `Layer2CPayload`, `Layer2DPayload`, `Layer2EPayload`, `Layer3APayload`, `Layer3BPayload`, `ParsedIntent`, `RaceEventPayload`) from `layer4.context`; `PlanSession` from `layer4.payload`; `llm_layer4_plan_refresh_cached` from `layer4.cached_wrappers`. Added new private `@dataclass(frozen=True) _UpstreamFullCone` (11 fields: etl_version_set + framework_sport + primary_locale + all 8 upstream payloads). Added new private `_upstream_full_cone(db, user_id, today, *, target_race_event: RaceEventPayload | None) -> _UpstreamFullCone` helper that composes the full upstream cone (Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B → 2E) and raises the 3 shared pre-flight gates (`etl_version_set_undiscoverable` / `framework_sport_missing` / `primary_locale_missing`). When `target_race_event is None`: race_terrain=[] / target_events=[] / race_event_payload=None — no-event-mode path. Refactored `orchestrate_race_week_brief` to consume the helper (preserves all brief-specific behavior: `no_target_event` + `race_week_brief_too_early` gates still inline before the helper call; cached-wrapper kwargs unchanged). Added `orchestrate_plan_refresh(db, user_id, *, tier, refresh_scope_start, refresh_scope_end, plan_version_id, plan_version_id_parent, prior_plan_session_window, cache, parsed_intent=None, plan_start_date=None, today=None) -> Layer4Payload`: looks up target_race conditionally → calls helper → packs `Layer2Bundle` from helper output → calls `llm_layer4_plan_refresh_cached`. Single_session NOT touched (cone-shape divergence per D1 rationale). Extended `__all__` with `orchestrate_plan_refresh`.

2. **Re-export** — `layer4/__init__.py` re-exports `orchestrate_plan_refresh` alongside `orchestrate_race_week_brief` + `orchestrate_single_session_synthesize` + `OrchestrationError`; `__all__` block updated.

3. **Tests** — Added 13 tests across 6 `TestOrchestratePlanRefresh*` classes (`TestOrchestratePlanRefreshHappyPath` 4 (parametrized [T1,T2,T3] tier dispatch + parsed_intent threading); `TestOrchestratePlanRefreshPreflightGates` 3 (3 shared gates); `TestOrchestratePlanRefreshNoEventMode` 1 (race_event_payload=None when no target race + 2B/2E/3B receive empty/None inputs); `TestOrchestratePlanRefreshDefaults` 2 (today defaults + parsed_intent defaults); `TestOrchestratePlanRefreshTierPassThrough` 2 (T3 plan_start_date threads + prior_plan_session_window threads verbatim); `TestOrchestratePlanRefreshReturnValue` 1). New `_plan_refresh_patches(*, layer4_return)` patch-stack patches the same 10 import sites as race_week_brief except the cached wrapper is `llm_layer4_plan_refresh_cached`. New `_fake_plan_refresh_layer4_payload(plan_version_id)` factory constructs a valid Pattern B plan_refresh `Layer4Payload` (mode invariants per `payload.py:553-565` = `mode='plan_refresh'` + `pattern='B'` requires `phase_structure=None` + `seam_reviews=None`). New `_default_prior_plan_session_window()` helper constructs a single non-ad-hoc `PlanSession` for the prior-window kwarg (orchestrator doesn't inspect contents; driver enforces non-empty). Imports extended (`ParsedIntent`, `orchestrate_plan_refresh`, `Layer2Bundle`).

4. **Test suite** — Container-runnable subset 478 → 491 passing in ~1.0s (`pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py`). All 17 pre-existing race_week_brief tests pass unchanged after the helper-extract refactor — the patches still hook at `layer4.orchestrator.q_layer2a_*` etc. (module-level imports unchanged) and the SELECT order is preserved. Verified via `pytest tests/ --ignore=<circular-import-blocked>` = 834 passed (no regressions in the wider tractable surface).

5. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count (1145 → 1158) + current-focus arc summary; `CARRY_FORWARD.md` Phase 5.2 follow-ons section: slice 2 entry struck (✅) + helper extract entry struck (✅) + slice 3 entry refined + new D-64 caller-side queue entry; `Upstream_Implementation_Plan_v1.md` §4 new row 5.2.S2; this closing handoff.

No additional `/plan-mode` triggers fired during implementation past the initial gate (no prompt body, no schema, no HITL gate, no padding refusal — D1-D10 were ratified before edits started).

---

## 3. File-by-file edits

### 3.1 `layer4/orchestrator.py` (MODIFIED, +~300 LOC net, ~50 LOC removed via refactor)

- Module docstring rewritten from "Phase 5.1 race_week_brief + Phase 5.2 single_session" → "Phase 5.1 race_week_brief + Phase 5.2 single_session + plan_refresh"; documents the helper-extract decision + cone-shape variance reasoning for single_session opting out; documents the slice 2 forward-pointers (caller-supplied kwargs pending D-64 caller-side).
- Imports: added `dataclass` from `dataclasses`; `Literal` from `typing`; payload types + `Layer2Bundle` + `ParsedIntent` + `RaceEventPayload` (block) from `layer4.context`; `PlanSession` from `layer4.payload`; `llm_layer4_plan_refresh_cached` to the `layer4.cached_wrappers` import block; `Layer1Payload` from `layer4.context`.
- New `@dataclass(frozen=True) _UpstreamFullCone`: 11 fields (etl_version_set + framework_sport + primary_locale + layer1_payload + layer2a/2b/2c/2d/2e_payload + layer3a/3b_payload). Docstring documents the consumer contract (race_week_brief wraps layer2c into `{primary_locale: payload}` dict; plan_refresh packs all 5 layer-2 payloads into a `Layer2Bundle`).
- New private `_upstream_full_cone(db, user_id, today, *, target_race_event: RaceEventPayload | None) -> _UpstreamFullCone`: composes the full upstream cone per the dependency-order ordering (Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B → 2E); raises the 3 shared pre-flight gates inline; handles the `target_race_event is None` no-event-mode path (race_terrain=[] / target_events=[] / race_event_payload=None).
- Refactored `orchestrate_race_week_brief`: keeps brief-specific gates (`no_target_event` + `race_week_brief_too_early`) inline before the helper call; calls `_upstream_full_cone(target_race_event=race_event)`; composes the cached-wrapper kwargs from the cone's fields. Behavior-preserving (all 17 existing race_week_brief tests pass unchanged).
- New public `orchestrate_plan_refresh(db, user_id, *, tier, refresh_scope_start, refresh_scope_end, plan_version_id, plan_version_id_parent, prior_plan_session_window, cache, parsed_intent=None, plan_start_date=None, today=None) -> Layer4Payload`: see §2 narrative step 1 for the algorithm. Pack the cone's 5 Layer 2 payloads into a `Layer2Bundle(a=, b=, c={primary_locale: layer2c_payload}, d=, e=)` and call `llm_layer4_plan_refresh_cached`.
- `__all__` updated to add `"orchestrate_plan_refresh"`.

### 3.2 `tests/test_layer4_orchestrator.py` (MODIFIED, +~500 LOC)

- Imports: added `ParsedIntent` + `orchestrate_plan_refresh` to the `from layer4 import (...)` block; added `Layer2Bundle` to the `from layer4.context import (...)` block.
- New helpers (after the single_session test classes):
  - `_plan_refresh_patches(*, layer4_return)` — 10-patch stack (same shape as race_week_brief's `_patches()` except the final cached wrapper is `llm_layer4_plan_refresh_cached`). Stubs `build_layer1_payload` + `q_layer2a` + `q_layer2b` + `q_layer2c` + `q_layer2d` + `q_layer2e` + `assemble_layer3a_bundle` + `llm_layer3a` + `llm_layer3b` + `llm_layer4_plan_refresh_cached`.
  - `_fake_plan_refresh_layer4_payload(plan_version_id=2)` — returns a valid Pattern B plan_refresh Layer4Payload satisfying mode invariants (`mode='plan_refresh'` + `pattern='B'` requires `phase_structure=None` + `seam_reviews=None` per `payload.py:553-565`).
  - `_default_prior_plan_session_window()` — single non-ad-hoc `PlanSession` for the prior-window kwarg. Orchestrator passes the list through verbatim without inspection.
- 13 new tests across 6 classes:
  - `TestOrchestratePlanRefreshHappyPath` (4): `test_tier_dispatch_pipeline_in_order` parametrized over `[("T1", 2), ("T2", 7), ("T3", 28)]` (asserts all 10 upstream + wrapper sites fire once; cached wrapper kwargs reflect orchestrator composition — tier + refresh_scope dates + plan_version_id + plan_version_id_parent + cache + parsed_intent=None default + plan_start_date conditional on T3 + layer1_payload as dict + Layer2Bundle packing all 5 payloads); `test_parsed_intent_threads_to_wrapper` (asserts D6: caller-supplied `ParsedIntent(triggers_2a_discipline=True, fatigue_signal='tired', ...)` passes through verbatim — orchestrator does not construct a default).
  - `TestOrchestratePlanRefreshPreflightGates` (3): `test_etl_version_set_undiscoverable` (asserts D4: NULL `MAX(etl_version)` → `OrchestrationError('etl_version_set_undiscoverable')` before any upstream call); `test_primary_locale_missing` (asserts D4: missing `'home'` row → `OrchestrationError('primary_locale_missing')` after Layer 1 + 2A but before 2B); `test_framework_sport_missing` (asserts D4: empty `layer1.identity.primary_sport` → `OrchestrationError('framework_sport_missing')` after Layer 1 but before 2A).
  - `TestOrchestratePlanRefreshNoEventMode` (1): `test_no_target_race_threads_race_event_payload_none` (asserts D5: `load_target_race_event_payload` returns None → orchestrator does NOT raise `no_target_event` → 2B receives `race_terrain=[]` + 2E receives `target_events=[]` + 3B receives `race_event_payload=None`).
  - `TestOrchestratePlanRefreshDefaults` (2): `test_today_kwarg_defaults_to_date_today` (asserts D7: `today=None` → orchestrator uses `date.today()`; Layer 3B `current_date` kwarg threads to the resolved value); `test_parsed_intent_defaults_to_none` (asserts D6 default: caller omits → wrapper receives `parsed_intent=None`).
  - `TestOrchestratePlanRefreshTierPassThrough` (2): `test_t3_plan_start_date_threads_to_wrapper` (asserts D3 + D9: T3 caller-supplied `plan_start_date=date(2026,4,1)` threads verbatim to the cached wrapper for the driver's `phase_structure_from_3b()` boundary detection); `test_prior_plan_session_window_threads_verbatim` (asserts D3: same list object passes through — orchestrator does not copy/inspect).
  - `TestOrchestratePlanRefreshReturnValue` (1): `test_returns_cached_wrapper_output_verbatim` (asserts D8: orchestrator returns wrapper output `is` sentinel — no wrap/modify/validate at orchestrator level).

### 3.3 `layer4/__init__.py` (MODIFIED, +2 LOC)

- `from layer4.orchestrator import` block extended with `orchestrate_plan_refresh`.
- `__all__` entry added.

(Re-export only; bookkeeping per CLAUDE.md "5-file ceiling = substantive files only" — does NOT count against the ceiling.)

---

## 4. Code / tests

**Test count delta:** 1145 → 1158 in production count (+13 net new tests, all in `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefresh*` across 6 classes); 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Container-runnable subset:** 478 → 491 passing (layer4 + race_events + onboarding + locales) in ~1.0s.

Run reproducer (container-runnable subset):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py
# 491 passed in ~1.0s
```

The +13 new tests:

- `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefreshHappyPath::*` (4 — parametrized [T1,T2,T3] + parsed_intent threading)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefreshPreflightGates::*` (3)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefreshNoEventMode::*` (1)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefreshDefaults::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefreshTierPassThrough::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestratePlanRefreshReturnValue::*` (1)

**Behavior-preservation verification for the race_week_brief refactor:** all 17 pre-existing race_week_brief tests (`TestHappyPath` + `TestPreflightGates` + `TestDiscoveryFailures` + `TestDefaults` + `TestOrchestrationError` + `TestRaceTerrainAndAidStationsWireUp` + `TestLocaleTerrainIdsWireUp`) pass unchanged after the `_upstream_full_cone` helper extraction. The refactor preserves both the SELECT query order and the module-level import names that the existing `_patches()` stack hooks into.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + Phase 5.1.B/C/5.2.S1 handoffs §4); verified by `git stash` round-trip that this slice did NOT introduce or worsen it — wider `pytest tests/ --ignore=<blocked>` runs at 834 passed.

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.2 slice 2 — plan_refresh orchestrator** — 3-step verification (executable once D-64 caller-side route + `plan_versions` table land):

**Step 1: T1 happy-path E2E (intra-day refresh).** From a Python REPL or test harness (no Flask UI yet — D-64 caller-side queued):

```python
from datetime import date
from layer4 import (
    orchestrate_plan_refresh,
    Layer4Cache, InMemoryCacheBackend, ParsedIntent,
)
result = orchestrate_plan_refresh(
    db, andy_user_id,
    tier="T1",
    refresh_scope_start=date(2026, 6, 1),
    refresh_scope_end=date(2026, 6, 2),
    plan_version_id=2,
    plan_version_id_parent=1,
    prior_plan_session_window=load_prior_window(db, andy_user_id, weeks=2),
    cache=Layer4Cache(InMemoryCacheBackend()),
    parsed_intent=ParsedIntent(fatigue_signal="tired", raw_text="rough sleep last night"),
    today=date(2026, 6, 1),
)
```

Confirm: (a) no `OrchestrationError` raised; (b) `result.mode == 'plan_refresh'`; (c) `result.pattern == 'B'`; (d) `result.phase_structure is None` + `result.seam_reviews is None` (Pattern B invariants); (e) `len(result.sessions) >= 1` covering the 2-day scope; (f) sessions reflect the tired-signal modulation (intensity ↓, recovery emphasis ↑); (g) Layer 4 cache row created with `entry_point='plan_refresh'` + the slice-2 hash key.

**Step 2: T3 cross-phase routing E2E.** Same harness; `tier='T3'` + `refresh_scope_start=date(2026,6,15)` + `refresh_scope_end=date(2026,7,15)` (spans Build → Peak phase boundary per Andy's plan; +30 day scope). Confirm: (a) driver routes to Pattern A via `_route_t3_cross_phase_to_pattern_a` automatically; (b) `result.pattern == 'A'`; (c) `result.phase_structure` + `result.seam_reviews` both non-None (Pattern A invariants); (d) sessions cover the full 30-day scope; (e) phase boundary seam_reviews documents the Build→Peak transition.

**Step 3: No-event-mode E2E.** Athlete with no `is_target_event=true` race row + `tier='T2'` + 7-day scope. Confirm: (a) no `OrchestrationError('no_target_event')` raised (this is the slice 2 D5 distinction vs race_week_brief); (b) `result.mode == 'plan_refresh'` + Layer 3B `mode='no-event'` reflected in observations; (c) Layer 2B emits `race_terrain_unset` coaching flag per Phase 5.1 form-refresh C loosen; (d) Layer 2E `target_events=[]` reflected in race_day_fueling absence; (e) plan proceeds without crash.

**Real-LLM cost:** ~$0.05/run for T1/T2 + ~$0.30/run for T3 (3-5 phase synthesizer calls in Pattern A) when `ANTHROPIC_API_KEY` set; ~$0 with mocked LLM caller.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**(a) Phase 5.2 slice 3 — `plan_create` Pattern A orchestrator.** Final orchestrator entry point closing Phase 5.2. Pattern A heaviest: per-phase synthesis loop + seam reviews + cross-phase reconciliation. Layer 3A + 3B inputs already wired in race_week_brief + plan_refresh precedents. The shared `_upstream_full_cone` helper (extracted in this session) already covers the full upstream cone; slice 3 reuses it as-is. `plan_version_id` allocation can stay caller-supplied per slice 2 D3 precedent (matches D-63 / D-64 caller-side deferral pattern) OR flip to real D-64 versioning surface if the `plan_versions` table lands first. Likely shape: new `orchestrate_plan_create(db, user_id, *, plan_version_id, plan_start_date, cache, today=None) -> Layer4Payload` calling `_upstream_full_cone` + `llm_layer4_plan_create_cached`. ~3-5 files (orchestrator additions + tests + bookkeeping). **`/plan` gate per Trigger #5** on per-phase loop + cross-phase reconciliation design + plan_version_id allocation strategy decision.

Files (est. 3-5):

1. `layer4/orchestrator.py` — new `orchestrate_plan_create` entry-point + module docstring update for 4-of-4 entry-point shape; reuses `_upstream_full_cone` helper.
2. `tests/test_layer4_orchestrator.py` — new `TestOrchestratePlanCreate*` classes (~10-12 tests covering happy path + preflight gates + defaults + return value pass-through).
3. `layer4/__init__.py` — re-export `orchestrate_plan_create`.
4. (Possibly) `aidstation-sources/Layer4_Spec.md` — paired doc-touchpoint if any §3.4 wording drifts.
5. Bookkeeping (CURRENT_STATE.md, CARRY_FORWARD.md, Upstream_Implementation_Plan_v1.md row 5.2.S3, new closing handoff).

Closes Phase 5.2 row 5.2 in `Upstream_Implementation_Plan_v1.md` fully (all 3 sub-slices shipped).

### 6.2 Alternative pivots

- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1 + #3 + #5 — table vs JSONB schema choice).
- **D-64 caller-side route + `plan_versions` table + NL parser glue** — slice 2's orchestrator is structurally complete + tested in isolation but not E2E-reachable from the v1 UI. ~4-6 files: `init_db.py` migration (plan_versions table per D-64 §3) + NEW `routes/plan_refresh.py` + NL parser glue + templates + tests.
- **D-63 caller-side route + `ad_hoc_workout_suggestions` table** — slice 1's caller-side wiring; ~3-4 files.
- **Layer 3B None-tolerant kwargs L3B-P-2** — with Form-refresh A/B/C closure, all 8 None-tolerant kwargs can flip to populated-from-payload. ~3-4 files.
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — surfaced as a doc-sweep nit during Phase 5.1 form-refresh C. Locale-equipment edits don't fire `evict_on_layer_change(cache, uid, 'layer2c')`. ~1-2 files.
- **Manual §5.0 walkthrough** of the accumulated scenarios + Phase 5.1 orchestrator + Phase 5.2 slices 1 + 2 end-to-end (once D-63/D-64 caller-side ship). Real-LLM ~$0.50/pass.
- **Real-LLM Layer 4 regression** parity to race_week_brief / single_session / plan_refresh / plan_create entry points (~$2/full smoke pass).
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **3A/3B caching policy modules at orchestrator level** — slice 2 added a 3rd consumer of uncached 3A/3B; load-bearing soonest at slice 3 (or when athletes fire multiple plan refreshes per day with the same Layer 1 hash).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Phase 5.2 follow-ons section now reflects slices 1 + 2 both shipped; slice 3 + D-63/D-64 caller-side wiring remain).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_PlanRefresh_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Extract `_upstream_full_cone` helper now + refactor race_week_brief to consume (single_session opts out) | Andy ratified plan-mode gate; flipped from architect-recommended defer-to-slice-3 | Architect's reasoning was that Rule of Three for the full-cone helper lands at slice 3 (slice 2 only adds the 2nd full-cone consumer; single_session has a narrower cone and would force the helper into a flag-driven shape). Andy's pick: extract now even at 2/3 — single_session opts out per cone-shape divergence (no 2B/2E/3B + uses request.sport not primary_sport + uses request.locale_slug not 'home' + optional 2C). Helper covers race_week_brief + plan_refresh cleanly; future slice 3 (plan_create) reuses as-is. Race_week_brief refactor is behavior-preserving (all 17 existing tests pass unchanged); risk of regression on the tested surface is mitigated by the helper preserving SELECT order + module-level import names. |
| **D2** | Tier as required kwarg from caller (D-64 dispatch happens at route layer, not orchestrator) | Andy | Per D-64 design, tier classification happens before orchestration via NL parser route handler. Avoids embedding D-64 dispatch logic in Layer 4; keeps orchestrator a thin composer. Driver internally dispatches T1/T2/T3 + routes T3 cross-phase to Pattern A — orchestrator passes tier through unchanged. |
| **D3** | `plan_version_id` + `plan_version_id_parent` + `prior_plan_session_window` + `parsed_intent` + `plan_start_date` all caller-supplied kwargs | Andy | Matches slice 1 D4 precedent for D-63's `suggestion_id` (caller-supplied because the persistence table isn't shipped). v2 `plan_versions` table queued per D-64 §3; orchestrator can't query it yet. Caller-side route handler (also queued) will allocate the rows + query prior window + run NL parser + dispatch tier. |
| **D4** | 3 pre-flight gates only — `etl_version_set_undiscoverable` + `primary_locale_missing` + `framework_sport_missing` (all shared with race_week_brief, all raised inside `_upstream_full_cone`) | Andy | Minimal set. NO `no_target_event` (no-event refresh supported — race_event_payload=None flows to L3B; 2B accepts race_terrain=[]; 2E gets empty target_events). NO `race_week_brief_too_early` (refresh fires on demand). Driver's own `_validate_inputs` covers tier/refresh_scope/plan_version_id_parent/plan_start_date validity — `Layer4InputError` propagates verbatim (orchestrator does not wrap; same pattern as slice 1 not wrapping driver's `Layer4InputError("locale_xor_quick_required")`). |
| **D5** | Target-race lookup is conditional, not gated | Andy | Orchestrator queries the target race row via `load_target_race_event_payload`; passes `race_event_payload` or `None` to the upstream cone helper. No-event-mode plans refresh fine without a race; Layer 3B's `mode='no-event'` branch handles this downstream. |
| **D6** | `parsed_intent: ParsedIntent | None` pass-through | Andy | Orchestrator does not construct a default ParsedIntent when caller omits — None passes through per D-64 §5.4 graceful-degradation contract. Driver internally handles None via `_default_parsed_intent()`. |
| **D7** | `today: date | None = None` kwarg mirroring race_week_brief + single_session signatures | Andy | Consistent kwarg shape across all 3 entry points; deterministic test injection via `today=date(2026, 6, 1)`. |
| **D8** | Orchestrator calls `llm_layer4_plan_refresh_cached` (not raw driver) | Andy | Matches slice 1 D9 + race_week_brief D9 — per-entry-point cache sits in front of the synthesizer; orchestrator gets cache rebinding (plan_version_id) for free per §9.4. |
| **D9** | Single function `orchestrate_plan_refresh(tier=...)` not 3 per-tier functions (`_t1`/`_t2`/`_t3`) | Andy | Mirrors driver's internal dispatch on the `tier` kwarg. Avoids 3x duplication in the orchestrator. The route handler picks tier upstream per D2. |
| **D10** | 13 tests across 6 classes at parity with single_session test density | Andy | Matches single_session + race_week_brief test density precedent. 6-class organization keeps test failures isolated to a specific D-decision (e.g., a D2 regression surfaces in `TestTierPassThrough` only; a D5 regression in `TestNoEventMode`). HappyPath uses pytest.parametrize for the 3 tiers — keeps the test count balanced (4 happy-path + 3 gates + 1 no-event + 2 defaults + 2 pass-through + 1 return-value = 13). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/orchestrator.py` has new `orchestrate_plan_refresh` function | ✅ `grep -n "^def orchestrate_plan_refresh" layer4/orchestrator.py` |
| `layer4/orchestrator.py` has new `_UpstreamFullCone` dataclass | ✅ `grep -n "^class _UpstreamFullCone" layer4/orchestrator.py` |
| `layer4/orchestrator.py` has new `_upstream_full_cone` helper | ✅ `grep -n "^def _upstream_full_cone" layer4/orchestrator.py` |
| `layer4/orchestrator.py` imports `Literal` + `dataclass` + `Layer2Bundle` + `ParsedIntent` + `PlanSession` + `llm_layer4_plan_refresh_cached` | ✅ `grep -n "Literal\|dataclass\|Layer2Bundle\|ParsedIntent\|PlanSession\|llm_layer4_plan_refresh_cached" layer4/orchestrator.py` |
| `layer4/orchestrator.py` `__all__` includes `orchestrate_plan_refresh` | ✅ `grep -n "\"orchestrate_plan_refresh\"" layer4/orchestrator.py` |
| `layer4/orchestrator.py` `orchestrate_race_week_brief` now calls `_upstream_full_cone` | ✅ `grep -n "cone = _upstream_full_cone" layer4/orchestrator.py` |
| `layer4/__init__.py` re-exports `orchestrate_plan_refresh` (2 hits — import + `__all__`) | ✅ `grep -n "orchestrate_plan_refresh" layer4/__init__.py` |
| `tests/test_layer4_orchestrator.py` has 6 new `TestOrchestratePlanRefresh*` classes | ✅ `grep -c "^class TestOrchestratePlanRefresh" tests/test_layer4_orchestrator.py` returns 6 |
| `tests/test_layer4_orchestrator.py` has 13 net new tests in plan_refresh test classes | ✅ (verified via pytest collected count delta: 27 pre → 40 post for the orchestrator file) |
| `tests/test_layer4_orchestrator.py` imports `ParsedIntent` + `orchestrate_plan_refresh` + `Layer2Bundle` | ✅ `grep -n "ParsedIntent\|orchestrate_plan_refresh\|Layer2Bundle," tests/test_layer4_orchestrator.py` |
| Existing race_week_brief tests pass unchanged after helper-extract refactor | ✅ `pytest tests/test_layer4_orchestrator.py::TestHappyPath tests/test_layer4_orchestrator.py::TestPreflightGates ...` all pass |
| Container-runnable subset green at 491 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` reports 491 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has new row 5.2.S2 → ✅ Shipped 2026-05-20 | ✅ `grep -n "5.2.S2.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 PlanRefresh handoff | ✅ `grep -n "Phase_5_2_PlanRefresh_Orchestrator" aidstation-sources/CURRENT_STATE.md` |
| `CURRENT_STATE.md` tests count flipped 1145 → 1158 | ✅ `grep -n "1158 green" aidstation-sources/CURRENT_STATE.md` |
| `CARRY_FORWARD.md` Phase 5.2 follow-ons section reflects slices 1 + 2 shipped | ✅ `grep -n "Phase 5.2 orchestrator follow-ons (slices 1 + 2 shipped" aidstation-sources/CARRY_FORWARD.md` |

---

## 9. Files shipped this session

**Substantive (2 files; well under 5-file ceiling):**

1. MODIFIED `layer4/orchestrator.py` (+~300 LOC net) — new `@dataclass(frozen=True) _UpstreamFullCone` (11 fields) + new private `_upstream_full_cone(db, user_id, today, *, target_race_event)` helper + new public `orchestrate_plan_refresh(...)` entry point + refactor of `orchestrate_race_week_brief` to consume the helper (behavior-preserving); new imports (`dataclass`, `Literal`, payload types + `Layer2Bundle` + `ParsedIntent` + `RaceEventPayload` from `layer4.context`, `PlanSession` from `layer4.payload`, `llm_layer4_plan_refresh_cached` from `layer4.cached_wrappers`); module docstring rewritten to reflect three-entry-point shape + helper-extract decision; `__all__` extended.
2. MODIFIED `tests/test_layer4_orchestrator.py` (+~500 LOC) — 13 tests across 6 `TestOrchestratePlanRefresh*` classes; new `_plan_refresh_patches()` + `_fake_plan_refresh_layer4_payload()` + `_default_prior_plan_session_window()` helpers; imports extended (`ParsedIntent`, `orchestrate_plan_refresh`, `Layer2Bundle`).

**Bookkeeping (4 files):**

3. MODIFIED `layer4/__init__.py` — re-export `orchestrate_plan_refresh` + `__all__` entry.
4. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flip + tests count + current-focus arc summary + Layer 4 status row bump.
5. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Phase 5.2 follow-ons section: slice 2 ✅ + helper extract ✅; refined slice 3 entry; new D-64 caller-side queue entry.
6. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row 5.2.S2.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_PlanRefresh_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes in this session:

- "Phase 5.2 orchestrator follow-ons" section header updated to reflect slices 1 + 2 shipped (was "slice 1 — single_session shipped").
- Slice 2 follow-on entry struck (✅ Shipped 2026-05-20).
- Shared `_upstream_pipeline` helper extract entry struck (✅ Shipped 2026-05-20 as `_UpstreamFullCone` + `_upstream_full_cone`).
- Slice 3 entry refined: notes that the helper is already extracted; ~3-5 files (down from previous estimate of ~6-8); `plan_version_id` allocation decision called out.
- New D-64 caller-side queue entry added (parallel to the existing D-63 caller-side entry from slice 1).
- Layer 3A + 3B caching policy entry refined to note that load-bearing case is now closer (3 consumers).

Phase 5.2 slice 2 closes the 10 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions.

**Phase 5.2 slice 2 complete; orchestrator now exposes 3 of 4 Layer 4 entry points (race_week_brief 5.1 + single_session_synthesize 5.2.S1 + plan_refresh 5.2.S2). Remaining: `plan_create` Pattern A (slice 3) — final orchestrator entry point closing Phase 5.2.**

---

**End of handoff.**
