# D-73 Phase 5.2 Layer 2C Invalidation + Refresh Telemetry — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — Layer 2C cache-invalidation gap fix (closes the doc-sweep nit carried since form-refresh C investigation 2026-05-20) + refresh-flow telemetry surface per §6.2 #7 (NL-8). Combined two-slice session at the 5-file ceiling.
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_TriggeredByAdHoc_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/layer2c-invalidation-telemetry` (renamed at session start from harness-pinned `claude/v5-phase-5-2-handoff-sK0sI` per CLAUDE.md branch-naming rule — the harness name didn't reflect scope; the prior session arc already shipped via PR #123).
**Status:** 5 substantive files (at ceiling). Tests 1384 → 1405 (+21 net new across 2 extended/new test files). Container-runnable subset 717 → 738 in ~2.0s. 16 skipped tests (12 NL parser smoke + 4 prior Layer 3 SDK smoke) unchanged.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (TriggeredByAdHoc) handoff's §8 table against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `routes/ad_hoc_workouts.py` T1 hook anchor adds `triggered_by_ad_hoc_id` query param | grep | ✅ |
| `routes/plan_refresh.py` `_resolve_prefill` returns 3-tuple | grep | ✅ |
| `routes/plan_refresh.py` defines `_validate_ad_hoc_id_for_user` | grep | ✅ |
| `routes/plan_refresh.py` POST flow reads + validates form field | grep | ✅ |
| `routes/plan_refresh.py` `_write_refresh_log` accepts `triggered_by_ad_hoc_id` kwarg | grep | ✅ |
| `templates/plans/v2/refresh.html` main + cap-exceeded mini-form both have hidden input | grep returns 2 | ✅ |
| `tests/test_routes_plan_refresh.py` has `TestValidateAdHocIdForUser` class | grep | ✅ |
| Container-runnable subset 717 passing | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → TriggeredByAdHoc | grep | ✅ |

`./scripts/verify-handoff.sh` ran clean. No drift. Predecessor merged to main via PR #123 (`a21cb70`); the branch I'm on started equal to `origin/main` after the merge.

**Reconciliation note:** Clean. No in-progress work to inherit. Branch was harness-pinned for a slice that had already shipped — renamed to match this session's actual scope.

---

## 2. Session narrative

Andy picked **Option 1 + Option 2 combined** at the AskUserQuestion scope gate (Option 1 = Layer 2C invalidation gap in `routes/locales.py`; Option 2 = telemetry analytics surface for `plan_refresh_log` per NL-8). Combined slice sized to 5 substantive files (at ceiling, not over). Other §6.2 alternatives passed over for this session: NL parser smoke-eval + Haiku 4.5 migration (Trigger #2 fires; needs hand-labeled fixtures); Form-refresh D §I.1 structured supplements (~6-8 files, over ceiling — would need split proposal).

Option 1 had no real design decisions — mirrors the precedented `_evict_layer2b_on_terrain_change` helper from form-refresh C. Option 2 surfaced 4 design questions per Trigger #5; all 4 ratified at the AskUserQuestion gate before any code:

- **D1: Admin-only at `/admin/telemetry/refresh` behind `_require_admin()`** (Andy's pick). Picked over (b) per-user `/profile/telemetry` and (c) both routes. No multi-user audience exists; per-user adds template polish for a non-existent audience.
- **D2: Full D-63 → D-64 funnel scope across 3 tables** (Andy flipped from architect's "plan_refresh_log only" recommendation). Adds `t1_hook_telemetry` + `ad_hoc_workout_suggestions` aggregates. Broader picture useful even at low traffic; the modest extra query cost is fine for an admin-gated view.
- **D3: Aggregates only — no row-level drill-down** (Andy flipped from architect's "aggregate block + recent 50 rows" recommendation). `psql` is the drill-down path; the surface stays template-light.
- **D4: Fixed last 30 days, no URL param** (Andy's pick). Picked over (b) configurable 7/30/90/all. Premature given current traffic (~1 week of caller-side data); add control later if it becomes useful.

Pre-design surface survey:

- `routes/locales.py:102` — `_evict_layer2b_on_terrain_change(db, user_id)` precedent (Phase 5.1 form-refresh C). Mirror this for 2C.
- `routes/locales.py:520` `_edit_legacy_locale` POST branch — DELETE-then-INSERT pattern; need to snapshot `prior_equipment_tags` before the DELETE so the no-op gate has a baseline.
- `routes/locales.py:600` `_edit_shared_locale` POST branch — two sub-paths: build-new (no `shared` row yet) + inherit (`_save_overrides` writes deltas). Need `_load_overrides` + `_effective_equipment` BEFORE `_save_overrides` so the comparison sees the pre-mutation effective view.
- `layer4/cache_invalidation.py:79` — `_EVICTION_POLICY['layer2c'] = _ALL_ENTRY_POINTS` (4 entries: `plan_create`, `plan_refresh`, `single_session_synthesize`, `race_week_brief`) vs `layer2b = _NON_SINGLE_SESSION` (3 entries, no single_session). Equipment changes affect on-demand workouts too — that's why 2C is broader.
- `routes/admin.py` — existing `_require_admin()` gate (user_id=1 = Andy) + Blueprint `bp` already exists. Add to this file rather than introducing a new admin/telemetry submodule.
- `init_db.py:1587/1614/1657` — `ad_hoc_workout_suggestions` + `plan_refresh_log` + `t1_hook_telemetry` schemas all populated; all 3 carry timestamp columns (`requested_at` / `triggered_at` / `dismissed_at`) suitable for window filtering.

Implementation flow:

1. **`routes/locales.py` Layer 2C invalidation:**
   - Add `_evict_layer2c_on_equipment_change(db, user_id)` helper right after `_evict_layer2b_on_terrain_change`.
   - In `_edit_legacy_locale`: snapshot `prior_equipment_tags = SELECT ei.tag FROM locale_equipment JOIN equipment_items` before the DELETE (mirrors the snapshot pattern for `prior_terrain_ids`). After `db.commit()`, fire helper when `set(selected_tags) != prior_equipment_tags`.
   - In `_edit_shared_locale`: compute `prior_effective_equipment = _effective_equipment(shared_tags, prior_adds, prior_removes)` when `shared` is non-None (else empty set for build-new). In both build-new and inherit POST paths, fire helper when `submitted != prior_effective_equipment`.

2. **`tests/test_locales.py`:**
   - Extend import to include `_evict_layer2c_on_equipment_change`.
   - NEW `TestEvictLayer2cOnEquipmentChange` class with 2 tests: `test_evicts_all_layer2c_consumers` (seeds 4 entry points; asserts all evicted per `_ALL_ENTRY_POINTS` policy) + `test_does_not_evict_other_users` (seeds rows for both target user and another user; asserts only target user's rows evicted).

3. **`routes/admin.py` telemetry route:**
   - Add `TELEMETRY_WINDOW_DAYS = 30` constant.
   - Add 4 private aggregate helpers:
     - `_telemetry_window_threshold(now=None)` returns `now - 30d`; default `datetime.now(timezone.utc)` for test isolation.
     - `_percentile(sorted_values, pct)` returns `None` on empty, clamps pct to [0, 100], nearest-rank index `int(pct/100 * N)` with bounds-clamp.
     - `_aggregate_ad_hoc_suggestions(db, threshold)` — `SELECT status, COUNT(*) GROUP BY status WHERE requested_at >= ?`; returns `{total, suggested, logged, discarded, regenerated, logged_rate}`.
     - `_aggregate_t1_hook_dismissals(db, threshold)` — `SELECT COUNT(*) WHERE dismissed_at >= ?`; returns `{total}`.
     - `_aggregate_plan_refresh_log(db, threshold)` — single SELECT then per-tier aggregation over T1/T2/T3; per-tier emits total + success_count/rate + cap_override_count/rate + parser_degraded_count/rate + t1_hook_attributed_count/rate + p50/p95 success-only duration_ms.
   - NEW `@bp.route('/telemetry/refresh') telemetry_refresh()` calls `_require_admin()`, computes threshold, calls 3 aggregate helpers, renders template.

4. **`templates/admin/telemetry_refresh.html`:**
   - Extends `base.html`. 3 sections: D-63 ad-hoc workout generation (6 small counter cards), post-log T1 hook (4 small counter cards + dismissal-to-log ratio computation in Jinja), D-64 plan refresh per-tier (8-column table × 3 rows T1/T2/T3 with count + percent rendering).

5. **`tests/test_routes_admin.py` (NEW):**
   - 19 tests across 5 classes: `TestTelemetryWindowThreshold` (2 — subtracts window + default UTC); `TestPercentile` (6 — empty + single + p50 + p95 + clamp_min + clamp_max); `TestAggregateAdHocSuggestions` (4 — empty-zero + SQL shape pin + happy-path aggregates + missing status keys default to 0); `TestAggregateT1HookDismissals` (3 — count + no-row zero + SQL shape pin); `TestAggregatePlanRefreshLog` (4 — empty per-tier zero-fill + SQL shape pin + happy-path per-tier aggregates + failure-row duration exclusion).
   - Shared `_FakeRow` / `_FakeCursor` / `_FakeConn` substrate matching the `tests/test_locales.py` + `tests/test_routes_plan_refresh.py` precedent.

`/plan` Triggers fired: **#5** (telemetry surface shape — D1/D2/D3/D4 cleared via AskUserQuestion). Triggers #1 / #2 / #3 / #4 / #6 did not fire (no new prompt body, no vocab additions, no cross-layer schema change — all 3 tables already exist on disk, no HITL gate, no architecture promotion).

---

## 3. File-by-file edits

### 3.1 `routes/locales.py` — Layer 2C invalidation helper + 3 wire sites

- **NEW `_evict_layer2c_on_equipment_change(db, user_id: int) -> None`:** 12-line helper directly after `_evict_layer2b_on_terrain_change`. Builds transient `Layer4Cache(PostgresCacheBackend(lambda: db))` and calls `evict_on_layer_change(cache, user_id, 'layer2c')`. Docstring explains that 2C policy is `_ALL_ENTRY_POINTS` (broader than 2B's `_NON_SINGLE_SESSION`) because equipment changes invalidate on-demand single-session synthesis too.
- **`_edit_legacy_locale` POST branch:** Inserts `prior_equipment_rows = db.execute('SELECT ei.tag FROM locale_equipment le JOIN equipment_items ei ON ei.id = le.equipment_id WHERE le.user_id = ? AND le.locale = ?', (uid, locale)).fetchall()` + `prior_equipment_tags = {row['tag'] for row in prior_equipment_rows}` after the existing `prior_terrain_ids` snapshot. After `db.commit()` and the existing terrain-eviction gate, fires `_evict_layer2c_on_equipment_change(db, uid)` only when `set(selected_tags) != prior_equipment_tags`. GET-branch SELECT for `active_rows` left in place (mirror of the snapshot SELECT; kept separate so the snapshot stays close to the mutation it gates).
- **`_edit_shared_locale` POST branch:** Inserts `if shared: prior_adds_tags, prior_removes_tags = _load_overrides(db, uid, locale); prior_effective_equipment = _effective_equipment(shared_tags, prior_adds_tags, prior_removes_tags) else: prior_effective_equipment = set()` after the existing `prior_terrain_ids` snapshot. After `db.commit()` and the existing terrain-eviction gate, fires `_evict_layer2c_on_equipment_change(db, uid)` only when `submitted != prior_effective_equipment` in BOTH build-new and inherit POST paths.

### 3.2 `tests/test_locales.py` — `_evict_layer2c_on_equipment_change` coverage

- Extends `from routes.locales import (...)` with `_evict_layer2c_on_equipment_change` (alphabetically sorted).
- NEW `TestEvictLayer2cOnEquipmentChange` class with 2 tests:
  - `test_evicts_all_layer2c_consumers` (mirrors `TestEvictLayer2bOnTerrainChange.test_evicts_layer2b_consumers` substrate; seeds 4 entry points including `single_session_synthesize`; monkeypatches `Layer4Cache` + `PostgresCacheBackend`; asserts `remaining == set()` since `_ALL_ENTRY_POINTS` evicts everything).
  - `test_does_not_evict_other_users` (seeds rows for `_USER_ID=42` + a second user `other_user=99` at the same entry point; asserts only the target user's row evicts via `survivors == {other_user}`).

### 3.3 `routes/admin.py` — refresh-flow telemetry surface

- **Imports:** adds `from datetime import datetime, timedelta, timezone`.
- **`TELEMETRY_WINDOW_DAYS = 30`** constant + 5-line doc-comment annotating it.
- **`_telemetry_window_threshold(now: datetime | None = None) -> datetime`:** Defaults to `datetime.now(timezone.utc)` when `now` is None; returns `now - timedelta(days=TELEMETRY_WINDOW_DAYS)`. Monkeypatch-friendly via the `now` kwarg.
- **`_percentile(sorted_values: list[int], pct: float) -> int | None`:** Nearest-rank percentile. Returns None on empty input. Clamps `pct <= 0` → first value and `pct >= 100` → last value. Otherwise `idx = max(0, min(N-1, int(pct/100 * N)))`.
- **`_aggregate_ad_hoc_suggestions(db, threshold) -> dict`:** Single `SELECT status, COUNT(*) AS n FROM ad_hoc_workout_suggestions WHERE requested_at >= ? GROUP BY status`. Returns `{total, suggested, logged, discarded, regenerated, logged_rate}`. Missing status keys default to 0.
- **`_aggregate_t1_hook_dismissals(db, threshold) -> dict`:** Single `SELECT COUNT(*) AS n FROM t1_hook_telemetry WHERE dismissed_at >= ?`. Returns `{total}`.
- **`_aggregate_plan_refresh_log(db, threshold) -> dict`:** Single SELECT pulling tier/success/cap_overridden/triggered_by_ad_hoc_id/failure_reason/duration_ms; per-tier (T1/T2/T3) Python-side aggregation. Each tier emits `{total, success_count, success_rate, cap_override_count, cap_override_rate, parser_degraded_count, parser_degraded_rate, t1_hook_attributed_count, t1_hook_attribution_rate, p50_duration_ms, p95_duration_ms}`. p50/p95 computed via `_percentile` on success-only durations (failure-row durations excluded since rollback short-circuits the timer).
- **NEW `@bp.route('/telemetry/refresh') telemetry_refresh()`:** Calls `_require_admin()` (existing gate). Renders `admin/telemetry_refresh.html` with kwargs `{window_days, threshold, ad_hoc, t1_hook, refresh_by_tier}`.

### 3.4 `templates/admin/telemetry_refresh.html` (NEW)

- Extends `base.html` like the other admin templates. Title `Admin · Refresh telemetry`.
- Heading row: `Admin · Refresh telemetry` + small "Last 30 days" text. Subhead paragraph references psql for row-level drill-down.
- **Section 1 — Ad-hoc workout generation (D-63):** 6 small counter cards (`col-md-2` × 6 in a row): Generated / Logged / Discarded / Regenerated / Suggested (open) / Logged rate.
- **Section 2 — Post-log T1 plan-check hook:** 4 counter cards (`col-md-3` × 4): [No, thanks] dismissals / Logged workouts (cross-ref above) / T1 attributed (cross-ref below) / Dismissal-to-log ratio (Jinja inline arithmetic with `if ad_hoc.logged` zero-guard rendering `—`). Funnel-explanation paragraph below.
- **Section 3 — Plan refresh by tier (D-64):** 8-column `table-sm` × 3 rows (T1/T2/T3). Columns: Tier / Total / Success (count + rate%) / Cap override (count + rate%) / Parser degraded (count + rate%) / T1-hook attributed (count + rate%) / p50 (ms) / p95 (ms). Percentile cells render `—` when None (no success rows in the window).

### 3.5 `tests/test_routes_admin.py` (NEW)

- ~290 LOC. Module docstring names the helpers tested + the manual-§5.0 deferral for route-level Flask test client coverage (mirrors `tests/test_locales.py` precedent).
- `_FakeRow` / `_FakeCursor` / `_FakeConn` substrate matches `tests/test_locales.py` (FIFO `queue_response` semantics).
- **`TestTelemetryWindowThreshold` (2):** `test_subtracts_window_days` (pins explicit `now` + asserts `now - 30d`); `test_default_now_is_utc` (asserts result lands within `[before-30d, after-30d]` window).
- **`TestPercentile` (6):** `test_empty_returns_none`; `test_single_value`; `test_p50_median` (idx=5 on 10 values returns 60); `test_p95_near_top` (idx=9 returns 100); `test_clamp_min` (pct=0 + pct=-10 → first); `test_clamp_max` (pct=100 + pct=200 → last).
- **`TestAggregateAdHocSuggestions` (4):** `test_empty_window_zero_counts`; `test_sql_filters_on_requested_at_threshold` (pins `ad_hoc_workout_suggestions` + `requested_at >= ?` + `GROUP BY status` + threshold param); `test_aggregates_all_statuses` (4 statuses → total + logged_rate); `test_missing_status_keys_default_to_zero`.
- **`TestAggregateT1HookDismissals` (3):** `test_returns_count`; `test_no_row_returns_zero`; `test_sql_filters_on_dismissed_at_threshold`.
- **`TestAggregatePlanRefreshLog` (4):** `test_empty_returns_zero_filled_per_tier` (T1/T2/T3 all keyed with zeros + None percentiles); `test_sql_pins` (pins all 6 column names + `triggered_at >= ?`); `test_per_tier_aggregates` (3 T1 rows + 1 T2 row + no T3 → per-tier metrics including 2/3 success rate, 1/3 cap rate, 2/3 attribution rate, p50/p95 derived from durations [100, 300] → 300/300); `test_failure_rows_excluded_from_duration_percentiles` (1 success duration=200 + 1 failure duration=9999 → p50 = p95 = 200).

---

## 4. Code / tests

**Tests 1384 → 1405 (+21 net new across 2 extended/new test files):**

- `tests/test_locales.py` +2 (21 → 23): `TestEvictLayer2cOnEquipmentChange` class with `test_evicts_all_layer2c_consumers` + `test_does_not_evict_other_users`.
- NEW `tests/test_routes_admin.py` (~290 LOC; 19 tests).

**Container-runnable subset 717 → 738 in ~2.0s.**

Run reproducer for the container-runnable subset (adds `tests/test_routes_admin.py` to the predecessor's set):

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
                    tests/test_routes_admin.py
# 738 passed, 12 skipped in ~2.0s
```

**No-regression confirmation:** All 717 pre-existing container-subset tests pass unchanged. Touched modules: `routes/locales.py` (1 new helper + 3 wire sites), `routes/admin.py` (1 new route + 5 helpers + 1 constant), 1 new template, 2 test files (1 extended + 1 new). No edits to `init_db.py`, `layer4/`, repos, schema, or specs — the telemetry surface reads existing columns + the invalidation helper reuses the existing eviction primitive.

Pre-existing `layer1/layer4` circular import remains. Full `pytest tests/` invocation fails collection on `tests/test_layer1_builder.py`; container-runnable subset above is the canonical green count.

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass.

**Step 1: Layer 2C equipment-edit invalidation.** Andy navigates to `/locales/home/edit`. Toggles 1-2 equipment tags (e.g., adds a treadmill, removes a dumbbell set). Saves. Confirms `SELECT entry_point FROM layer4_cache WHERE user_id=<andy> AND entry_point IN ('plan_create','plan_refresh','single_session_synthesize','race_week_brief') AND superseded_at IS NULL` returns no rows after the equipment edit (all 4 entry points should evict per `_ALL_ENTRY_POINTS` policy — broader than 2B which keeps single_session). Repeats Save with NO equipment change and confirms cache NOT evicted (`prior != new` field-change gate fires only on actual diff).

**Step 2: Shared-locale variant.** Andy navigates to `/locales/<chain_gym_slug>/edit` (a shared-profile locale). Toggles 1-2 equipment override tags (add/remove against the shared base). Saves. Confirms same `layer4_cache` row-count behavior; the shared path computes prior effective via `_load_overrides + _effective_equipment` before `_save_overrides` overwrites the override row.

**Step 3: `/admin/telemetry/refresh` view renders.** Andy logs in as user_id=1 (admin). Navigates to `/admin/telemetry/refresh`. Confirms: (a) page title reads `Admin · Refresh telemetry`; (b) "Last 30 days" small text in header; (c) section 1 (D-63 generation) shows 6 counter cards with current values from `ad_hoc_workout_suggestions` (logged_rate rendered as `%.0f%%`); (d) section 2 (T1 hook) shows 4 counter cards; dismissal-to-log ratio renders `—` when `ad_hoc.logged == 0` else as `%.0f%%`; (e) section 3 (per-tier table) shows 3 rows T1/T2/T3 × 8 columns; cells with `count + rate` show `N (M%)`; p50/p95 cells render `—` when no success rows exist in the window.

**Step 4: Cross-user lockout.** Andy logs out and creates / logs in as a second test user (or visits the route while authenticated as a non-admin). Navigates to `/admin/telemetry/refresh`. Confirms 403 abort.

**Step 5: Aggregate correctness.** Andy executes a known-shape sequence on Neon to seed predictable data: 2 successful T1 refreshes from the T1 hook + 1 failed T1 refresh (e.g., transient orchestration error) + 1 successful T2 refresh with no T1-hook attribution. Refreshes `/admin/telemetry/refresh`; confirms T1 row shows total=3, success=2 (67%), parser_degraded=count-of-degraded-rows, t1_hook_attributed=2 (67%); T2 row shows total=1, success=1 (100%), t1_hook_attributed=0; T3 row all zeros + percentiles `—`.

Captured in `CARRY_FORWARD.md` manual walkthrough section (1 new scenario `2 D-73 Phase 5.2 Layer 2C invalidation + refresh telemetry`).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Manual §5.0 walkthrough on Neon** — same recommendation as the predecessor handoff. The caller-side v2 surfacing arc is end-to-end complete on the code surface; the freshly-shipped telemetry surface gives Andy a live view of what's actually happening during the walkthrough. Costs ~$1.50/pass across the 3 routes + T1 hook follow-on; new telemetry surface is no-cost beyond the route load. This is the canonical "did this actually work" check that no test harness replaces — and now the harness has a built-in dashboard for spotting regression patterns.

### 6.2 Alternative pivots

- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** (~5-6 files; need ~20-30 hand-labeled fixtures from Andy's PGE 2026 + AR vocab + Haiku-vs-Sonnet agreement comparison harness; `/plan` Trigger #2 LLM-prompt-design gate would fire if prompt body changes for Haiku).
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1+#3+#5; would need a split proposal since over the 5-file ceiling).
- **Layer 3A + 3B caching policy at orchestrator level** — all 4 entry points call `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` uncached. ~4-6 files.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).
- **Telemetry surface extensions** — once Andy's Neon walkthrough generates traffic into the new dashboard, follow-on candidates: row-level drill-down view (the D3 alternative we passed on), configurable time window (D4 alternative), per-user filter for future multi-user, charts (sparklines for tier-latency trend over the window).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Layer2C_Telemetry_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Telemetry surface scope = admin-only at `/admin/telemetry/refresh` | Andy at AskUserQuestion gate | Picked over per-user `/profile/telemetry` + both-routes alternatives. No multi-user audience to speculate against; per-user adds template polish for a non-existent audience. Lives in the existing admin Blueprint behind `_require_admin()`. |
| **D2** | Data scope = full D-63 → D-64 funnel (3 tables) | Andy | Flipped from architect's "plan_refresh_log only" recommendation. Broader picture useful even at low traffic; modest extra query cost (3 simple SELECTs) is fine for an admin-gated view that loads infrequently. |
| **D3** | View shape = aggregates only, no row-level drill-down | Andy | Flipped from architect's "aggregate block + recent 50 rows" recommendation. `psql` is the drill-down path; the surface stays template-light + drift-resistant. |
| **D4** | Time window = fixed last 30 days, no URL param | Andy | Picked over configurable 7/30/90/all. Premature at current traffic (~1 week of caller-side data); configurable adds branching SQL + a select dropdown for negligible early-stage value. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `routes/locales.py` defines `_evict_layer2c_on_equipment_change` | ✅ `grep "def _evict_layer2c_on_equipment_change" routes/locales.py` |
| `routes/locales.py` `_edit_legacy_locale` snapshots `prior_equipment_tags` before mutation | ✅ `grep "prior_equipment_tags" routes/locales.py` returns 3 occurrences (snapshot + comparison + doc-comment cross-ref) |
| `routes/locales.py` `_edit_shared_locale` snapshots `prior_effective_equipment` before mutation | ✅ `grep "prior_effective_equipment" routes/locales.py` returns 4 occurrences (build-new assign + empty-set assign + 2 comparison sites in build-new + inherit POST paths) |
| `routes/locales.py` fires Layer 2C eviction in 3 sites (legacy + shared-build + shared-inherit) | ✅ `grep "_evict_layer2c_on_equipment_change(db, uid)" routes/locales.py` returns 3 |
| `routes/admin.py` defines `TELEMETRY_WINDOW_DAYS = 30` | ✅ grep |
| `routes/admin.py` defines `_telemetry_window_threshold` + `_percentile` + 3 aggregate helpers | ✅ grep all 5 |
| `routes/admin.py` defines `@bp.route('/telemetry/refresh') telemetry_refresh()` | ✅ grep |
| `templates/admin/telemetry_refresh.html` exists with 3 sections | ✅ grep `"Ad-hoc workout generation"` + `"Post-log T1"` + `"Plan refresh by tier"` |
| `tests/test_locales.py` has `TestEvictLayer2cOnEquipmentChange` class | ✅ grep |
| `tests/test_routes_admin.py` exists with 5 test classes | ✅ grep `"class TestTelemetryWindowThreshold"` + 4 others |
| Container-runnable subset 717 → 738 (+21 net new) | ✅ pytest run returns "738 passed, 12 skipped" |
| Tests 1384 → 1405 (+21 net new) | ✅ Counted via diff: 2 (TestEvictLayer2cOnEquipmentChange) + 19 (test_routes_admin.py 5 classes) = +21 |
| `CURRENT_STATE.md` last-shipped pointer flipped to Layer2C_Telemetry handoff | ✅ |
| `CARRY_FORWARD.md` Layer 2C invalidation nit flipped to ✅ Shipped + 1 new manual §5.0 walkthrough scenario added | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.Layer2C-Telemetry` → ✅ Shipped 2026-05-21 | ✅ grep |
| Branch renamed `claude/v5-phase-5-2-handoff-sK0sI` → `claude/layer2c-invalidation-telemetry` | ✅ `git branch` |

---

## 9. Files shipped this session

**Substantive (5 files; at the 5-file ceiling):**

1. `routes/locales.py` — NEW `_evict_layer2c_on_equipment_change` helper; `_edit_legacy_locale` snapshots `prior_equipment_tags` before DELETE + fires helper after commit on actual change; `_edit_shared_locale` computes `prior_effective_equipment` before mutation + fires helper after commit in build-new + inherit paths.
2. `tests/test_locales.py` — extended import + NEW `TestEvictLayer2cOnEquipmentChange` class (+2 tests).
3. `routes/admin.py` — NEW `TELEMETRY_WINDOW_DAYS` constant + 4 private aggregate helpers + NEW `telemetry_refresh()` route.
4. NEW `templates/admin/telemetry_refresh.html` — 3-section aggregate-only view.
5. NEW `tests/test_routes_admin.py` (~290 LOC; 19 tests).

**Bookkeeping (4 files):**

6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + this session's narrative.
7. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — `routes/locales.py` Layer 2C invalidation open nit flipped to ✅ Shipped + 1 new manual §5.0 walkthrough scenario; walkthrough counter 79 → 81.
8. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.Layer2C-Telemetry`.
9. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Layer2C_Telemetry_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **`routes/locales.py` Layer 2C invalidation gap** open nit → ✅ Shipped 2026-05-21 (`claude/layer2c-invalidation-telemetry`). The doc-sweep nit carried since Phase 5.1 form-refresh C investigation 2026-05-20 is closed end-to-end.
- 1 new manual §5.0 walkthrough scenario added under D-73 Phase 5.2 Layer 2C invalidation + refresh telemetry (legacy + shared equipment-edit eviction + `/admin/telemetry/refresh` render check + cross-user 403 + aggregate correctness).
- Architect-recommended §6.1 forward move remains **Manual §5.0 walkthrough on Neon** — unchanged from the predecessor; the caller-side v2 surfacing arc is end-to-end complete on the code surface and the new telemetry surface gives Andy a live view during the walkthrough.

**Phase 5.2 caller-side v2 surfacing arc + log-this slice + post-log T1 plan-check hook + refresh frequency caps + `triggered_by_ad_hoc_id` attribution + Layer 2C invalidation gap + refresh-flow telemetry surface all complete. D-63 + D-64 caller-side surfaces are end-to-end coherent + observably instrumented. The manual §5.0 Neon walkthrough is the next genuine forward move; the only remaining caller-side code surface is the orthogonal NL parser smoke-eval + Haiku migration arc.**

---

**End of handoff.**
