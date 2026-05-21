# D-73 Phase 5.2 Layer 3A + 3B Caching at Orchestrator — Closing Handoff

**Session:** D-73 Phase 5.2 — Layer 3A + 3B caching deployed at the orchestrator level + Layer 3 invalidation policy extended. Closes the §6.2 #3 architect-recommended pivot from the Layer2C_Telemetry handoff.
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Layer2C_Telemetry_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/layer2c-telemetry-implementation-UVgyV` (harness-assigned at session start; not renamed — the implementation branch name and the scope diverged because the predecessor handoff is the entry point Andy linked. Kept the harness pin since this is a single-slice slice with no naming-mismatch confusion downstream.)
**Status:** 5 substantive files (at ceiling). Tests 1405 → 1419 (+14 net new across 1 NEW + 1 extended test file). Container-runnable subset 738 → 752 in ~1.2s. 16 skipped tests (12 NL parser smoke + 4 prior Layer 3 SDK smoke) unchanged.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (Layer2C_Telemetry) handoff's §8 table against on-disk state via `./scripts/verify-handoff.sh`.

| Claim | Anchor | Result |
|---|---|---|
| `routes/locales.py` defines `_evict_layer2c_on_equipment_change` | grep | ✅ |
| `routes/locales.py` fires Layer 2C eviction in 3 sites | grep returns 3 | ✅ |
| `routes/admin.py` defines `TELEMETRY_WINDOW_DAYS = 30` + 5 helpers + `telemetry_refresh()` route | grep | ✅ |
| `templates/admin/telemetry_refresh.html` exists with 3 sections | grep | ✅ |
| `tests/test_routes_admin.py` exists with 5 test classes | grep | ✅ |
| `tests/test_locales.py` `TestEvictLayer2cOnEquipmentChange` class present | grep | ✅ |
| Container-runnable subset 738 passing | pytest | ✅ |

`./scripts/verify-handoff.sh` ran clean. No drift. Predecessor merged to main via PR #124 (`05e947f`); the branch this session opens on was equal to `origin/main`.

**Reconciliation note:** Clean. The predecessor's §6.2 pivot list named "Layer 3A + 3B caching policy at orchestrator level" as one of 4 alternatives; Andy picked it at the AskUserQuestion gate.

---

## 2. Session narrative

The cached wrappers for Layer 3A + 3B shipped at Phase 3.1-Driver (2026-05-20) + Phase 4 (2026-05-20) per `Layer3_3A_Spec.md` §9 + `Layer3_3B_Spec.md` §9 — they live at `layer3a/cached_wrapper.py:109` (`llm_layer3a_athlete_state_cached`) + `layer3b/cached_wrapper.py:134` (`llm_layer3b_goal_timeline_viability_cached`) and accept a `cache_backend: CacheBackend` kwarg. But they were never wired in: `layer4/orchestrator.py` imported the raw drivers and called them uncached at 3 sites (2 in `_upstream_full_cone`; 1 in `orchestrate_single_session_synthesize`). The orchestrator's own docstring (lines 61-65 in the pre-session form) flagged the gap as a vertical-slice carry: "Layer 3A + Layer 3B run uncached at the orchestrator level. ... Upstream caching becomes load-bearing only when multiple Layer 4 entry points share user-scoped 3A/3B outputs; slice 3 adds the 3rd full-cone consumer so this is closer to load-bearing."

This slice deploys the wrappers + extends `_EVICTION_POLICY` in `cache_invalidation.py` so 3A/3B caches participate in upstream-driven eviction explicitly.

Pre-design surface survey (via Explore agent):

- `layer3a/cached_wrapper.py` + `layer3b/cached_wrapper.py` — fully shipped per spec §9 contracts; serialize via `pydantic .model_dump_json()`; cache key includes day-anchored `as_of`/`current_date`; entry_point labels `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` already in `VALID_ENTRY_POINTS` superset frozenset.
- `layer4/orchestrator.py:252` + `:261` + `:486` — 3 uncached call sites. All take consistent argument shapes (a single cached wrapper can replace each).
- `layer4/cache.py:399` — `Layer4Cache` exposes `.backend` as a public property → clean threading from existing `cache: Layer4Cache` kwargs in the orchestrator entry points down to the 3A/3B wrappers' `cache_backend=` parameter.
- `layer4/cache_invalidation.py:75` — `_EVICTION_POLICY` matrix currently covers only Layer 4 entry points; 3A/3B caches were over-evicted by the None-optimization at `layer4/cache_invalidation.py:105-111` (when `set(entry_points) == set(_ALL_ENTRY_POINTS)` the filter collapses to `None` → backend wipes ALL user rows including 3A/3B/NL_parser).
- `tests/test_layer3a_builder.py::TestCacheWrapper` (7 tests) + `tests/test_layer3b_builder.py::TestCacheWrapper` (7 tests) — existed but uncollectible due to the pre-existing layer1/layer4 circular import (predecessor handoff §4 documents this).
- Per-payload dependency analysis from `cached_wrapper.py:65-96` (3A) + `cached_wrapper.py:69-121` (3B): 3A depends on layer1_hash + layer2a_hash + integration_bundle_hash + as_of + etl_version_set; 3B adds layer3a_hash + race_event_id + current_date + non_event_goal_type + section_h2_kwargs. Neither depends on layer2b / 2c / 2d / 2e output — those upstream changes leave 3A/3B caches alone (no orphans).

2 D-decisions ratified at the AskUserQuestion gate per Trigger #5 (architectural alternatives — don't pick silently):

- **D1: Scope = all 4 entry points** (Andy's pick over "Shared cone only, defer single_session"). 3A wired at race_week_brief / plan_refresh / plan_create via `_upstream_full_cone` + at single_session inline (3B not consumed by single_session per D-63). Closes the wiring gap end-to-end; matches the handoff §6.2 "all 4 entry points" framing.
- **D2: Extend invalidation policy now** (Andy's pick over "Defer invalidation policy"). The runtime-shipped wrappers had no explicit eviction policy entry — closes the policy-vs-runtime gap in the same slice. Bumps file count from 4 → 5 (at ceiling); both tests/test_layer4_cache.py policy assertions + behavior tests need updates.

Implementation flow:

1. **`layer4/cache_invalidation.py`:**
   - Add `_LAYER3_BOTH` constant = (`llm_layer3a_athlete_state`, `llm_layer3b_goal_timeline_viability`) tuple.
   - Add `_LAYER3_B_ONLY` constant = (`llm_layer3b_goal_timeline_viability`,) tuple.
   - Extend `_EVICTION_POLICY`:
     - `layer1 / layer2a / etl_version_set` → `_ALL_ENTRY_POINTS + _LAYER3_BOTH` (6-tuple).
     - `layer3a` → `_ALL_ENTRY_POINTS + _LAYER3_B_ONLY` (5-tuple; 3B depends on 3A; 3A's own row stays per orphan-cleanup-deferred scope).
     - `layer2b / 2c / 2d / 2e / 3b` → unchanged (3A/3B don't depend on those upstreams).
   - Rewrite module docstring with the extended matrix + `no*` callout for the layer2c/layer2d over-eviction edge.

2. **`layer4/orchestrator.py`:**
   - Swap imports: `from layer3a.builder import llm_layer3a_athlete_state` → `from layer3a.cached_wrapper import llm_layer3a_athlete_state_cached`; same for 3B.
   - `_upstream_full_cone` signature: add `cache: Layer4Cache` kwarg.
   - Replace 3A + 3B uncached calls inside `_upstream_full_cone` with cached wrappers (pass `cache_backend=cache.backend`).
   - Update 3 callers (race_week_brief / plan_refresh / plan_create) of `_upstream_full_cone` to pass `cache=cache` (already in scope).
   - `orchestrate_single_session_synthesize`: swap inline 3A call to cached wrapper (3B not consumed).
   - Update module docstring lines 61-65 + `orchestrate_single_session_synthesize` step-6 docstring (the "uncached at orchestrator level" claim is now stale).

3. **NEW `tests/test_layer3_cached_wrappers.py`:**
   - Combined sister-module test file (both wrappers have parallel shape; combining saves a file under the 5-file ceiling). ~340 LOC.
   - File header documents the import-order workaround for the pre-existing layer1/layer4 circular import (`from layer4 import InMemoryCacheBackend` first to force `layer4/__init__.py` to fully load).
   - Reuse `_fake_layer*_payload()` builders from `tests.test_layer4_orchestrator` rather than duplicating ~200 LOC of pydantic constructors.
   - 13 tests across 2 classes:
     - `TestLayer3ACachedWrapper` 6 — miss-then-hit / day-granular as_of intra-day collapse / different user_id distinct keys / different layer1_hash distinct keys / serialization round-trip / entry_point label stored as `llm_layer3a_athlete_state`.
     - `TestLayer3BCachedWrapper` 7 — miss-then-hit / event-vs-no-event distinct keys / different race_event_id distinct keys / `section_h2_kwargs` slot distinct keys / `current_date` distinct keys / serialization round-trip / entry_point label stored as `llm_layer3b_goal_timeline_viability`.

4. **`tests/test_layer4_orchestrator.py`:**
   - Mock target swap at all 10 patch sites: `layer4.orchestrator.llm_layer3a_athlete_state` → `_cached` (4 sites); `layer4.orchestrator.llm_layer3b_goal_timeline_viability` → `_cached` (6 sites). Mechanical `replace_all`.
   - Existing kwarg assertions like `m_l3b.call_args.kwargs["race_event_payload"]` + `m_l3b.call_args.kwargs["current_date"]` still hold — cached wrapper takes the same kwargs plus an additional `cache_backend=`. No assertion updates needed.

5. **`tests/test_layer4_cache.py`:**
   - 4 policy tests updated to assert `_includes_layer3` shape: `test_policy_layer1/layer2a/layer3a/etl_version_set_all_entry_points` → `_covers_layer4_and_layer3` / `_includes_layer3b`.
   - `test_policy_layer2b_excludes_single_session` + `test_policy_layer3b_excludes_single_session` extended with disjointness assertions against the layer3 set.
   - `test_layer1_evicts_all_user_rows` rewritten as `test_layer1_evicts_layer4_and_layer3_preserves_nl_parser` (count was `len(VALID_ENTRY_POINTS)` = 7; now 6 with NL parser preserved).
   - NEW `test_layer3a_change_evicts_layer3b_preserves_layer3a` — 3B evicted on 3A change; 3A's own row stays (orphan-cleanup deferred).

`/plan` Triggers fired: **#5** (architectural alternatives — scope + invalidation timing cleared via AskUserQuestion). Triggers #1 / #2 / #3 / #4 / #6 did not fire (no new prompt body, no vocab additions, no schema change, no HITL gate, no architecture promotion).

---

## 3. File-by-file edits

### 3.1 `layer4/cache_invalidation.py` — `_EVICTION_POLICY` extended

- **Module docstring rewritten** with the extended matrix table (Layer 4 entry points × Layer 3A column × Layer 3B column for each upstream layer trigger) + `no*` callout for the layer2c/layer2d over-eviction edge.
- **NEW `_LAYER3_BOTH: tuple[EntryPoint, ...]`** = both Layer 3 entry_point labels.
- **NEW `_LAYER3_B_ONLY: tuple[EntryPoint, ...]`** = (3B only) for the layer3a eviction list.
- **`_EVICTION_POLICY` extended** at 4 layer keys:
  - `layer1`: was `_ALL_ENTRY_POINTS` (4-tuple), now `_ALL_ENTRY_POINTS + _LAYER3_BOTH` (6-tuple).
  - `layer2a`: same.
  - `layer3a`: was `_ALL_ENTRY_POINTS`, now `_ALL_ENTRY_POINTS + _LAYER3_B_ONLY` (5-tuple; 3B depends on 3A re-running).
  - `etl_version_set`: same as layer1.
- Unchanged: `layer2b` + `layer2c` + `layer2d` + `layer2e` + `layer3b` (3A/3B don't depend on those upstreams per their cache-key formulas).
- The None-optimization at `evict_on_layer_change` lines 105-111 is unchanged: now triggers only for layer2c / layer2d (whose policies still equal `_ALL_ENTRY_POINTS` 4-tuple). For layer1 / layer2a / layer3a / etl_version_set the set comparison fails (6-tuple ≠ 4-tuple) → explicit IN-clause filter → precise eviction → NL parser cache preserved.

### 3.2 `layer4/orchestrator.py` — cached wrappers wired at 3 call sites

- **Imports swapped:** `from layer3a.builder import llm_layer3a_athlete_state` → `from layer3a.cached_wrapper import llm_layer3a_athlete_state_cached`; same for 3B.
- **Module docstring lines 61-65 updated** — replaced the "uncached at orchestrator level" carry note with a 7-line description of the cached-wrapper deployment + invalidation policy reference.
- **`_upstream_full_cone`:** signature gains `cache: Layer4Cache` kwarg; docstring extended with a "cache threads through" paragraph. Both 3A + 3B calls inside the helper now pass `cache_backend=cache.backend`.
- **3 callers updated:**
  - `orchestrate_race_week_brief` (line 374): `cone = _upstream_full_cone(db, user_id, today, cache=cache, target_race_event=race_event)`.
  - `orchestrate_plan_refresh` (line 575): same.
  - `orchestrate_plan_create` (line 654): same.
- **`orchestrate_single_session_synthesize` (line 501):** 3A call swapped to `llm_layer3a_athlete_state_cached(..., cache_backend=cache.backend)`. Step-6 docstring updated to reflect cached-wrapper deployment.

### 3.3 NEW `tests/test_layer3_cached_wrappers.py` (~340 LOC; 13 tests)

- Module docstring covers the circular-import workaround + the `tests.test_layer4_orchestrator` builder reuse rationale.
- `_make_integration_bundle()` returns minimal-shape `Layer3AIntegrationBundle` (empty workouts/sleep/hrv + empty `CombinedLoadReport`).
- `_make_race_event()` returns event-mode `RaceEventPayload` with `race_format='expedition_ar'` (per Andy's PGE 2026 context).
- `TestLayer3ACachedWrapper`:
  - `test_miss_invokes_driver_then_hit_serves_cached` — patches `layer3a.cached_wrapper.llm_layer3a_athlete_state`; 2 invocations of the cached wrapper → 1 driver call.
  - `test_day_granular_as_of_collapses_intraday_calls` — calls with `as_of=datetime(2026,6,1,0,5)` + `datetime(2026,6,1,14,30)` collide on the same cache key.
  - `test_different_user_id_distinct_keys` — direct `layer3a_athlete_state_key()` call asserting key changes on `user_id` swap.
  - `test_different_layer1_hash_distinct_keys` — same shape on `layer1_hash` swap.
  - `test_serialization_round_trip_preserves_payload` — `model_dump_json()` round-trip on hit returns byte-identical payload.
  - `test_entry_point_label_stored_with_row` — asserts backend stores row with `entry_point='llm_layer3a_athlete_state'` so the extended `_EVICTION_POLICY` routes correctly.
- `TestLayer3BCachedWrapper`:
  - `test_miss_invokes_driver_then_hit_serves_cached`.
  - `test_event_vs_no_event_distinct_keys` — `race_event_id=7` vs `race_event_id=None` (no-event mode → `"no-event"` string literal in the key).
  - `test_different_race_event_id_distinct_keys` — race switch flips the key.
  - `test_section_h2_kwargs_distinct_keys` — empty kwargs dict vs `{"goal_outcome": "podium"}` distinct keys per the D11 forward-compat slot.
  - `test_current_date_distinct_keys` — `2026-06-01` vs `2026-06-02` distinct keys (day-granular).
  - `test_serialization_round_trip_preserves_payload`.
  - `test_entry_point_label_stored_with_row` — asserts `entry_point='llm_layer3b_goal_timeline_viability'`.

### 3.4 `tests/test_layer4_orchestrator.py` — mock target swap

- 10 patch sites updated via `replace_all` Edit: 4 sites swap `layer4.orchestrator.llm_layer3a_athlete_state` → `_cached`; 6 sites swap `layer4.orchestrator.llm_layer3b_goal_timeline_viability` → `_cached`.
- No assertion updates needed — existing `m_l3b.call_args.kwargs["race_event_payload"]` + `m_l3b.call_args.kwargs["current_date"]` assertions still hold (cached wrapper takes the same kwargs plus an additional `cache_backend=` that isn't asserted on).

### 3.5 `tests/test_layer4_cache.py` — policy + eviction tests updated

- Added module-level `_LAYER3_BOTH_LABELS` constant (frozenset of both Layer 3 entry_point labels) for sharing across the policy tests.
- 4 policy tests renamed + updated to assert the new shape:
  - `test_policy_layer1_all_entry_points` → `test_policy_layer1_covers_layer4_and_layer3` (assert union of `LAYER4_ENTRY_POINTS` + `_LAYER3_BOTH_LABELS`).
  - `test_policy_layer2a_all_entry_points` → same shape for layer2a.
  - `test_policy_layer3a_all_entry_points` → `test_policy_layer3a_includes_layer3b` (assert `LAYER4_ENTRY_POINTS` + 3B; explicitly assert 3A NOT in result since orphan-cleanup deferred).
  - `test_policy_etl_version_set_all_entry_points` → same shape for etl_version_set.
- `test_policy_layer2b_excludes_single_session` + `test_policy_layer3b_excludes_single_session` extended with `assert result.isdisjoint(_LAYER3_BOTH_LABELS)` (those upstream layers don't evict Layer 3 caches).
- `test_layer1_evicts_all_user_rows` rewritten as `test_layer1_evicts_layer4_and_layer3_preserves_nl_parser` — count was `len(VALID_ENTRY_POINTS)` = 7; now 6 with NL parser preserved + explicit `assert backend.get("k-nl_parser_parse_intent") is not None` + `assert backend.get("k-llm_layer3a_athlete_state") is None` for the precise-eviction behavior.
- NEW `test_layer3a_change_evicts_layer3b_preserves_layer3a` — seeds all `VALID_ENTRY_POINTS`; calls `evict_on_layer_change(cache, _USER_ID, "layer3a")`; asserts count=5 + 3B + 4 Layer 4 evicted + 3A's own row + NL parser preserved.

---

## 4. Code / tests

**Tests 1405 → 1419 (+14 net new across 1 NEW + 1 extended test file):**

- NEW `tests/test_layer3_cached_wrappers.py` (~340 LOC; 13 tests).
- `tests/test_layer4_cache.py` net +1 (rewritten 1 test + new 1 test + 4 renames net 0 + 1 layer3b extension net 0).

**Container-runnable subset 738 → 752 in ~1.2s.**

Run reproducer for the container-runnable subset (adds `tests/test_layer3_cached_wrappers.py` to the predecessor's set):

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py \
                    tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py \
                    tests/test_layer4_context.py tests/test_layer4_payload.py \
                    tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                    tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py \
                    tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py \
                    tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py \
                    tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py \
                    tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py
# 752 passed, 12 skipped in ~1.2s
```

**No-regression confirmation:** All 738 pre-existing container-subset tests pass (with the 4 cache policy tests + 1 cache eviction test refactored to reflect the extended policy; net behavior on policy intent is the same — Layer 3 caches now participate explicitly). Touched modules: `layer4/orchestrator.py` (import swap + helper signature + 4 wire-site replacements + docstring updates), `layer4/cache_invalidation.py` (2 new constants + 4 policy entries extended + matrix docstring rewrite), 2 test files (1 extended + 1 new), `tests/test_layer4_orchestrator.py` (mechanical mock target swap × 10).

Pre-existing `tests/test_layer3a_builder.py::TestCacheWrapper` (7 tests) + `tests/test_layer3b_builder.py::TestCacheWrapper` (7 tests) remain pre-existing-circular-import-blocked from collection (same as before; the new `tests/test_layer3_cached_wrappers.py` is the canonical living coverage path). The pre-existing `layer1/layer4` circular import remains as a documented carry — same as predecessor handoff §4.

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass. None of these are exercise-required for the in-container test pass; they validate the cache wiring against real Postgres traffic.

**Step 1: 3A/3B cache hits across multiple entry points within a calendar day.** Andy logs in. Fires `/plans/v2/refresh` → T1. Observes the `plan_refresh_log` row lands with `duration_ms ~1500-3000ms` (cold-cache cascade). Within the same calendar day, fires `/plans/v2/refresh` → T1 again. Confirms: (a) `plan_refresh_log.duration_ms` drops noticeably (3A + 3B served from cache); (b) `layer4_cache` rows present for `entry_point IN ('llm_layer3a_athlete_state', 'llm_layer3b_goal_timeline_viability')` for `user_id=<andy>`; (c) `hit_count >= 1` for those rows. Repeat with `/workouts/build` (3A only, no 3B for single_session per D-63) — confirm 3A cache hits.

**Step 2: Layer 1 / 2A change evicts 3A + 3B + Layer 4 caches; NL parser preserved.** Andy edits his Layer 1 profile (e.g., flips an injury status). Confirms: (a) `evict_on_layer_change(cache, uid, 'layer1')` fires (visible in route logs); (b) `SELECT entry_point FROM layer4_cache WHERE user_id=<andy>` shows NL parser rows still present + 3A/3B + Layer 4 rows wiped; (c) the next `/plans/v2/refresh` re-warms 3A + 3B (cold-cache `duration_ms`).

**Step 3: Equipment edit (layer2c) over-eviction edge.** Andy edits a locale equipment toggle. Confirms: (a) `layer2c` eviction fires; (b) ALL `layer4_cache` rows for the user are wiped (including 3A/3B/NL_parser via the None-optimization). This is the documented over-eviction acceptable noise — verify the next 3A call cold-warms cleanly.

**Step 4: 3A re-run evicts 3B but preserves 3A's own row.** Manually fire `evict_on_layer_change(cache, uid, 'layer3a')` (e.g., via a Python REPL hitting Neon). Confirms: (a) 3A's previous row remains in `layer4_cache` (orphan-cleanup deferred); (b) 3B rows wiped (3B depends on 3A); (c) Layer 4 rows wiped.

Captured in `CARRY_FORWARD.md` manual walkthrough section under a new scenario for Phase 5.2 Layer 3 caching.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Manual §5.0 walkthrough on Neon** — same recommendation as the past several handoffs. The caller-side v2 surfacing arc + the freshly-shipped Layer 3 caching deployment are end-to-end complete on the code surface; the manual walkthrough validates real-LLM behavior + the new cache participation against actual athlete traffic. Costs remain ~$1.50/pass across the 3 routes + T1 hook + 1 plan refresh re-fire to demonstrate cache hits; the freshly-shipped 3A/3B caching surface should DROP the marginal cost of the second refresh (3A + 3B served from cache).

### 6.2 Alternative pivots

- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** (~5-6 files; need ~20-30 hand-labeled fixtures from Andy's PGE 2026 + AR vocab + Haiku-vs-Sonnet agreement comparison harness; `/plan` Trigger #2 LLM-prompt-design gate would fire if prompt body changes for Haiku).
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` Triggers #1 + #3 + #5; would need a split proposal since over the 5-file ceiling).
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).
- **Telemetry surface extensions** — once Andy's Neon walkthrough generates traffic into the dashboard (admin/telemetry/refresh shipped 2026-05-21), follow-on candidates: row-level drill-down view (the Layer2C-Telemetry D3 alternative we passed on), configurable time window (D4 alternative), per-user filter for future multi-user, charts (sparklines for tier-latency trend over the window), cache hit-rate panels surfacing `layer4_cache.hit_count` aggregates (newly load-bearing post this slice).
- **Over-eviction cleanup for layer2c/layer2d** — remove the None-optimization at `cache_invalidation.py:105-111` so layer2c/layer2d evictions stop incidentally wiping 3A/3B/NL_parser. Small follow-on (~2 files: `cache_invalidation.py` + `tests/test_layer4_cache.py` update). Pair with the daily cleanup nit for 3A/3B (cache rows from prior calendar days orphan naturally via the key change but never get evicted).
- **Layer 3A + 3B explicit eviction primitives for 3D revise action** — the spec §9.2 calls out "explicit 3D revise invalidation" as an eviction trigger; 3D doesn't exist yet so this is deferred. When 3D ships, add `evict_on_layer3_revise(cache, user_id)` per the §9.2 contract.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Layer3_Caching_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Scope = all 4 entry points (3A everywhere; 3B in the 3 full-cone consumers) | Andy at AskUserQuestion gate | Picked over "shared cone only, defer single_session." Closes the wiring gap end-to-end + matches the predecessor §6.2 "all 4 entry points" framing. single_session also benefits from 3A caching since same-day repeated /workouts/build calls hit the cache. |
| **D2** | Extend `_EVICTION_POLICY` now for 3A/3B (Andy picked over "defer invalidation policy") | Andy | Closes the policy-vs-runtime gap in the same slice — the runtime-shipped wrappers had no explicit eviction policy entry. Bumps file count from 4 → 5 (at ceiling). Side benefit: NL parser cache rows now explicitly preserved on Layer 1 / 2A / 3A / ETL eviction (previously over-evicted by the None-optimization). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/orchestrator.py` imports `llm_layer3a_athlete_state_cached` (not the raw driver) | ✅ `grep "from layer3a" layer4/orchestrator.py` returns the cached_wrapper import |
| `layer4/orchestrator.py` imports `llm_layer3b_goal_timeline_viability_cached` (not the raw driver) | ✅ same grep |
| `layer4/orchestrator.py` `_upstream_full_cone` signature has `cache: Layer4Cache` kwarg | ✅ grep |
| `layer4/orchestrator.py` 3 `_upstream_full_cone` callers thread `cache=cache` | ✅ `grep "cache=cache, target_race_event=" layer4/orchestrator.py` returns 3 |
| `layer4/orchestrator.py` `orchestrate_single_session_synthesize` calls 3A cached | ✅ `grep "llm_layer3a_athlete_state_cached" layer4/orchestrator.py` returns 3 occurrences (2 import refs + 1 imports doc + 1 call sites × 2 from cone + 1 from single_session = total 5 with the docstring; actual call sites = 2 in cone helper + 1 in single_session = 3 calls) |
| `layer4/cache_invalidation.py` defines `_LAYER3_BOTH` + `_LAYER3_B_ONLY` constants | ✅ grep |
| `layer4/cache_invalidation.py` `_EVICTION_POLICY["layer1"]` includes 3A + 3B | ✅ `policy_for_layer("layer1")` test asserts |
| `layer4/cache_invalidation.py` `_EVICTION_POLICY["layer3a"]` includes 3B (NOT 3A) | ✅ `test_policy_layer3a_includes_layer3b` asserts |
| `tests/test_layer3_cached_wrappers.py` exists with 2 test classes + 13 tests | ✅ pytest collects 13 |
| `tests/test_layer4_orchestrator.py` 10 patch sites swapped to `_cached` | ✅ `grep "llm_layer3a_athlete_state_cached\\|llm_layer3b_goal_timeline_viability_cached" tests/test_layer4_orchestrator.py` returns 10 |
| `tests/test_layer4_cache.py` `test_layer1_evicts_layer4_and_layer3_preserves_nl_parser` present + `test_layer3a_change_evicts_layer3b_preserves_layer3a` present | ✅ pytest collects both |
| Container-runnable subset 738 → 752 (+14 net new) | ✅ pytest run returns "752 passed, 12 skipped" |
| Tests 1405 → 1419 (+14 net new) | ✅ +13 in NEW test file + 1 net in cache test file = +14 |
| `CURRENT_STATE.md` last-shipped pointer flipped to Layer3_Caching handoff | ✅ |
| `CARRY_FORWARD.md` 3 entries flipped to ✅ Shipped (3A cache invalidation wiring + Layer 3 orchestrator partial-close + 3B cache invalidation wiring + Layer 3A + 3B caching policy at orchestrator level) | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.Layer3-Caching` → ✅ Shipped 2026-05-21 | ✅ grep |

---

## 9. Files shipped this session

**Substantive (5 files; at the 5-file ceiling):**

1. `layer4/orchestrator.py` — import swap (`llm_layer3a_athlete_state` → `_cached`; same for 3B); `_upstream_full_cone` signature gains `cache: Layer4Cache` kwarg + 2 inline call sites swapped to cached wrappers; 3 callers updated to pass `cache=cache`; `orchestrate_single_session_synthesize` 3A call swapped; docstring updates at module header + `orchestrate_single_session_synthesize` step 6.
2. `layer4/cache_invalidation.py` — 2 new constants (`_LAYER3_BOTH` + `_LAYER3_B_ONLY`); `_EVICTION_POLICY` extended at 4 layer keys (layer1 + layer2a + layer3a + etl_version_set); module docstring rewritten with extended matrix + `no*` over-eviction callout.
3. NEW `tests/test_layer3_cached_wrappers.py` (~340 LOC; 13 tests across `TestLayer3ACachedWrapper` 6 + `TestLayer3BCachedWrapper` 7).
4. `tests/test_layer4_orchestrator.py` — 10 patch-site mock targets swapped to `_cached` (4 sites for 3A + 6 sites for 3B).
5. `tests/test_layer4_cache.py` — 4 policy tests renamed + updated; 2 layer2b/layer3b tests extended with disjointness; `test_layer1_evicts_all_user_rows` rewritten as `_preserves_nl_parser`; NEW `test_layer3a_change_evicts_layer3b_preserves_layer3a`.

**Bookkeeping (4 files):**

6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + this session's narrative.
7. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — 3 entries flipped to ✅ Shipped (3A cache invalidation wiring + Layer 3 orchestrator partial-close + 3B cache invalidation wiring + Layer 3A + 3B caching policy at orchestrator level).
8. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.Layer3-Caching`.
9. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Layer3_Caching_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Cache invalidation wiring for 3A** ✅ Shipped 2026-05-21 (this slice).
- **3B cache invalidation wiring** ✅ Shipped 2026-05-21 (this slice; paired with 3A).
- **Layer 3 orchestrator** ✅ Partially closed 2026-05-21 (3A/3B caching wired; 3C + 3D + 3.5 still future work; no orthogonal module added).
- **Layer 3A + 3B caching policy at orchestrator level** ✅ Shipped 2026-05-21 (this slice).
- 1 new manual §5.0 walkthrough scenario added (Layer 3 cache hit verification + Layer 1/2A eviction precision + 3A re-run eviction shape).
- Architect-recommended §6.1 forward move remains **Manual §5.0 walkthrough on Neon** — unchanged from prior handoffs; the caller-side v2 surfacing arc + the freshly-shipped Layer 3 caching deployment are end-to-end complete on the code surface, and the new admin telemetry dashboard now has 3A/3B cache hit_count aggregates available for follow-on extension.

**Phase 5.2 caller-side v2 surfacing arc + log-this slice + post-log T1 plan-check hook + refresh frequency caps + `triggered_by_ad_hoc_id` attribution + Layer 2C invalidation gap + refresh-flow telemetry surface + Layer 3A + 3B caching at orchestrator level all complete. D-63 + D-64 caller-side surfaces are end-to-end coherent + observably instrumented + the Layer 3 cache participates in upstream eviction explicitly. The manual §5.0 Neon walkthrough is the next genuine forward move; the only remaining caller-side code surface is the orthogonal NL parser smoke-eval + Haiku migration arc.**

---

**End of handoff.**
