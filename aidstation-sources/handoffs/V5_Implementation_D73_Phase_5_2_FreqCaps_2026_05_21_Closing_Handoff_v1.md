# D-73 Phase 5.2 Refresh Frequency Caps — Closing Handoff

**Session:** D-73 Phase 5.2 NL parser refresh frequency caps per D-64 §8. Closes the §6.1 architect-recommended forward move from the LogThis+T1Hook closing handoff. Implements T1 ≤3/24h, T2 ≤1/48h, T3 ≤1/7d soft caps server-side against `plan_refresh_log`, with an auto-opening Bootstrap `#capExceededModal` modal-confirm on overflow (mirroring the predecessor session's `#t1HookModal` pattern). **4 substantive files** (well under the 5-file ceiling).
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_LogThis_T1Hook_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/logthis-t1-hook-phase5-UxDnv` (harness-pinned at session start; kept as-is — the next slice from the §6.1 forward-move is on the same load-bearing surface as the log-this/T1 hook session, and renaming would mid-arc what's effectively the second slice of the same line of work).
**Status:** 4 substantive files. Tests 1363 → 1376 (+13 net new in 1 extended test file). Container-runnable subset 696 → 709 in ~1.7s. 16 skipped tests (12 NL parser smoke + 4 prior Layer 3 SDK smoke) unchanged.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (D-73 Phase 5.2 LogThis+T1Hook) handoff's §8 table against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` migration adds 3 columns + 1 partial index to `cardio_log` | `grep "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS is_ad_hoc" init_db.py` + `grep "cardio_log_ad_hoc_idx" init_db.py` | ✅ |
| `init_db.py` migration adds 3 columns + 1 partial index to `training_log` | grep | ✅ |
| `init_db.py` adds `triggered_by_ad_hoc_id` to `plan_refresh_log` | grep | ✅ |
| `init_db.py` creates `t1_hook_telemetry` table + index | grep | ✅ |
| `routes/ad_hoc_workouts.py` defines the 5 log-this helpers + 2 routes | grep | ✅ |
| `templates/workouts/suggestion_view.html` has `#t1HookModal` + auto-open script | grep | ✅ |
| `routes/plan_refresh.py` defines `_resolve_prefill` | grep | ✅ |
| `templates/plans/v2/refresh.html` renders `prefill_nl_context` + `prefill_tier` | grep | ✅ |
| Container-runnable subset 696 passing | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 LogThis+T1Hook | grep | ✅ |

`./scripts/verify-handoff.sh` ran clean. No drift. Predecessor merged to main via PR #121 (`44d707c`); the branch I'm on (`claude/logthis-t1-hook-phase5-UxDnv`) started equal to `origin/main` after the merge.

**Reconciliation note:** Clean. No in-progress work to inherit.

---

## 2. Session narrative

Andy ratified scope at the AskUserQuestion gate: **NL parser frequency caps per D-64 §8** (the architect-recommended §6.1 forward move from the LogThis+T1Hook handoff), over the §6.2 alternatives (`triggered_by_ad_hoc_id` plumbing, Layer 2C equipment-edit invalidation gap, Layer 3A/3B caching at orchestrator).

Pre-design surface survey:

- `Plan_Refresh_D64_Design_v1.md:289-299` — §8 spec table: T1 = 3 per 24h / T2 = 1 per 48h / T3 = 1 per 7d. Override allowed with confirmation; logged with `cap_overridden=TRUE`. No hard cap.
- `Plan_Refresh_D64_Design_v1.md:158-162` — §4.5: "Modal-confirm: 'You've refreshed 3 times today. Each refresh costs ~$X in compute. Continue?' + [Refresh anyway] + [Cancel]. Override logged to `plan_refresh_log.cap_overridden=TRUE`."
- `Plan_Refresh_D64_Design_v1.md:271` — §7.1 schema: `cap_overridden BOOLEAN NOT NULL DEFAULT FALSE` on `plan_refresh_log`.
- `init_db.py:1603-1632` — the existing `plan_refresh_log` migration block; comment block notes "Frequency-cap fields per D-64 §8 deferred." Append a new `ALTER TABLE … ADD COLUMN IF NOT EXISTS cap_overridden` migration after the existing column-extension migrations.
- `routes/plan_refresh.py:228-268` — `_write_refresh_log` signature; needs a `cap_overridden: bool = False` kwarg and the SQL extended with the new column.
- `routes/plan_refresh.py:325-482` — `refresh()` POST flow; cap check needs to land after `_parse_tier` but before allocating the `plan_versions` row (so over-cap submissions don't create orphan rows).
- `templates/plans/v2/refresh.html:1-76` — the existing tier-picker form; the `#capExceededModal` block lands at the end of the plan-exists branch with a 3-line auto-open `<script>` mirroring the predecessor's `#t1HookModal` pattern.

The 4 design questions surfaced at the AskUserQuestion gate per `/plan` Triggers #3 (column add on existing telemetry table) + #5 (architectural alternatives for cap-exceeded UX):

- **D1: Cap-exceeded UX shape = auto-open modal on re-render** (recommended). Picked over (b) 302 redirect with `cap_exceeded=T1&count=3` query params (wider state-coupling), (c) inline alert banner + checkbox (loses cost-confirmation friction). Modal pattern matches the `#t1HookModal` precedent shipped in the predecessor session — minimal new JS surface, predictable behaviour. POST checks cap, when exceeded + no override re-renders the form template with a `cap_exceeded={tier, count, window_hours}` kwarg and the auto-open script fires.
- **D2: Cap counting = `success=TRUE` rows only.** Andy flipped from the architect's "count-all-rows" recommendation. Trade-off: conservative cost-protection (count every attempt) vs. fault-tolerance (let athletes retry through a broken orchestrator without burning the cap). Andy picked fault-tolerance — failed cascades shouldn't penalize the athlete. Failed runs already get a `plan_refresh_log` row with `success=FALSE` for telemetry; they just don't count toward the soft cap. SQL filter: `WHERE … AND success = TRUE`.
- **D3: Override scope = single-use per refresh.** Each subsequent submit re-checks the cap independently. Picked over window-clearing (first override clears the cap for the rest of the window). Matches the D-64 §8 framing of "athlete owns the decision" on a per-refresh basis — the cost signal surfaces on every over-cap attempt, not once per window.
- **D4: `cap_overridden=TRUE` lands only on real-exceeded.** The route's own cap-check returns `(exceeded, count)`; `cap_overridden = exceeded AND cap_override` (where `cap_override = request.form.get("cap_override") == "1"`). Stale forms / direct-curls with `cap_override=1` against an under-cap window land `cap_overridden=FALSE`. Column reflects "athlete confirmed the cost gate," not "request contained an override field."

Implementation flow:

1. **`init_db.py`** — append 1 new migration after the existing `t1_hook_telemetry` index: `ALTER TABLE plan_refresh_log ADD COLUMN IF NOT EXISTS cap_overridden BOOLEAN NOT NULL DEFAULT FALSE` per D-64 §7.1. Existing rows backfill to FALSE on the DEFAULT.

2. **`routes/plan_refresh.py`** — 2 new helpers + cap-check threading + `_write_refresh_log` extension:
   - Module docstring updated: predecessor's "Frequency caps per D-64 §8 deferred" paragraph replaced with the enforcement summary (server-side check, modal-confirm UX, single-use override semantics).
   - New imports: `datetime`, `timezone` (alongside the existing `date` + `timedelta`).
   - New module-level constant `_TIER_CAP_LIMITS: dict[str, tuple[int, int]] = {"T1": (3, 24), "T2": (1, 48), "T3": (1, 24 * 7)}` — (count_limit, window_hours) tuple per tier.
   - New `_count_recent_refreshes(db, user_id, tier, *, window_hours, now=None) -> int` — `SELECT COUNT(*) AS n FROM plan_refresh_log WHERE user_id = ? AND tier = ? AND success = TRUE AND triggered_at >= ?`; threshold computed as `now - timedelta(hours=window_hours)`; `now` defaults to `datetime.now(timezone.utc)`; row-None defensive returns 0.
   - New `_check_frequency_cap(db, user_id, tier, *, now=None) -> tuple[bool, int]` — looks up `(limit, window_hours)` in `_TIER_CAP_LIMITS`, calls `_count_recent_refreshes`, returns `(count >= limit, count)`. Cap is hit when count is already at-or-above the limit (the next attempt would be the (count+1)th in-window row).
   - `refresh()` POST flow extended: after `_parse_tier`, reads `cap_override = request.form.get("cap_override") == "1"`, calls `_check_frequency_cap`. If `cap_exceeded_now and not cap_override`, re-renders `plans/v2/refresh.html` with `cap_exceeded={tier, count, window_hours}` kwarg (plus `prefill_nl_context=nl_text` + `prefill_tier=tier` so the submitted state pre-populates the form). Otherwise resolves `cap_overridden = cap_exceeded_now and cap_override` per D4 and continues into the existing allocate → parse → orchestrate → persist → log → commit flow.
   - `_write_refresh_log` signature gains `cap_overridden: bool = False` kwarg; INSERT SQL extended with the new column and the new positional parameter (index 13). Success-path log INSERT threads the resolved `cap_overridden` value; failure-path log INSERTs keep the default `False` (failures never count as a successful override of the gate — they didn't actually run the cascade against the override).

3. **`templates/plans/v2/refresh.html`** — 2 changes:
   - NEW conditional `{% if cap_exceeded %}` block at the end of the plan-exists branch (sibling to the form, after the closing `</form>` tag) rendering the `#capExceededModal` markup: centered fade modal with title `Refresh again?`, body `You've already refreshed <strong>{{ cap_exceeded.count }}</strong> {{ cap_exceeded.tier }} {{ 'time' if cap_exceeded.count == 1 else 'times' }} in the last {{ cap_exceeded.window_hours }} hours.` + a text-muted small paragraph `Each refresh re-runs the cascade and costs compute. Continue if this signal is worth the cost.`, footer with [Cancel] (`btn-outline-secondary` + `data-bs-dismiss="modal"`) and a separate mini-form `<form method="post" action="{{ url_for('plan_refresh.refresh') }}" class="d-inline">` containing hidden `csrf_token` + hidden `nl_context` (server-pre-filled from `prefill_nl_context`) + hidden `cap_override=1` + a submit `<button name="submit_{{ cap_exceeded.tier|lower }}" value="1" class="btn btn-primary">Refresh anyway</button>` so the override re-POST preserves the original tier + nl_context.
   - 3-line inline `<script>` block immediately after the modal that auto-opens it via `window.bootstrap.Modal.getOrCreateInstance(modalEl).show()` (mirrors the `{% if just_logged %}` precedent from `templates/workouts/suggestion_view.html` shipped by the predecessor session).

4. **`tests/test_routes_plan_refresh.py`** — 3 new test classes + 2 added tests on existing class:
   - Imports extended: `datetime` + `timezone` added to the existing `date, timedelta` block; `_TIER_CAP_LIMITS` + `_count_recent_refreshes` + `_check_frequency_cap` added to the route-helper imports.
   - `TestWriteRefreshLog` extended with `test_cap_overridden_defaults_to_false` + `test_cap_overridden_true_passed_through` — pinning the `cap_overridden` column position (params[13]) and the default value semantics.
   - New `TestTierCapLimits` (3 tests) — sanity-pins `_TIER_CAP_LIMITS["T1"] == (3, 24)` + T2 == (1, 48) + T3 == (1, 168).
   - New `TestCountRecentRefreshes` (4 tests) — `test_returns_count_from_row` (happy path with queued `{"n": 2}` row); `test_zero_when_no_row` (zero count case); `test_filters_user_tier_and_success` (asserts SQL contains `FROM plan_refresh_log` + `user_id = ?` + `tier = ?` + `success = TRUE` + `triggered_at >= ?` + params order: user_id / tier / threshold-datetime); `test_default_now_uses_utc` (monkeypatches `datetime` in the route module + asserts the default-now call passes `tz=timezone.utc`).
   - New `TestCheckFrequencyCap` (4 tests) — `test_under_cap` (T1 count=2 → exceeded=False); `test_at_cap_is_exceeded` (T1 count=3 → exceeded=True; pins the "the next attempt would be over-cap" semantics); `test_t2_at_cap` (T2 count=1 → exceeded=True with limit=1); `test_t3_window_hours_threaded` (T3 call passes threshold-datetime = now - timedelta(hours=168)).

`/plan` Triggers fired: #3 (column add on existing `plan_refresh_log` telemetry table — counts as cross-layer schema surface since the column is consumed downstream by future telemetry analytics) + #5 (cap-exceeded UX shape — modal-confirm vs blocking gate vs soft warning). Both cleared via AskUserQuestion before drafting. Triggers #1 / #2 / #4 / #6 did not fire (no LLM prompt design, no vocab additions, no HITL gate, no architecture promotion).

---

## 3. File-by-file edits

### 3.1 `init_db.py` — 1 new migration appended to `_PG_MIGRATIONS`

- Insertion point: after the existing `t1_hook_telemetry_user_dismissed_idx` index (the last line of the predecessor's migration block before the closing `]`).
- 1× `ALTER TABLE plan_refresh_log ADD COLUMN IF NOT EXISTS cap_overridden BOOLEAN NOT NULL DEFAULT FALSE` per D-64 §7.1. The NOT NULL DEFAULT FALSE keeps existing rows + new failure-path INSERTs valid without needing a backfill step.

### 3.2 `routes/plan_refresh.py` — 2 new helpers + cap check in POST + `_write_refresh_log` extension

- Module docstring rewritten: replaces the "Frequency caps per D-64 §8 deferred — caps are anti-cohort guard and N=1 athlete doesn't warrant the modal-confirm UX yet" paragraph with the enforcement summary documenting the server-side check, the modal-confirm flow, and the single-use override semantics per D3.
- New imports: `datetime` + `timezone` added to the existing `from datetime import date, timedelta` block.
- New constant `_TIER_CAP_LIMITS: dict[str, tuple[int, int]] = {"T1": (3, 24), "T2": (1, 48), "T3": (1, 24 * 7)}` — single source of truth for tier → (count_limit, window_hours) lookup. `24 * 7` keeps the T3 168 hours explicitly readable as "7 days × 24 hours."
- `_count_recent_refreshes(db, user_id, tier, *, window_hours, now=None) -> int` — issues `SELECT COUNT(*) AS n FROM plan_refresh_log WHERE user_id = ? AND tier = ? AND success = TRUE AND triggered_at >= ?` with the threshold computed as `now - timedelta(hours=window_hours)`. `now` defaults to `datetime.now(timezone.utc)` for test-isolation (monkeypatch-friendly via the route module's `datetime` symbol). Row-None defensive returns 0.
- `_check_frequency_cap(db, user_id, tier, *, now=None) -> tuple[bool, int]` — looks up `(limit, window_hours)` in `_TIER_CAP_LIMITS`, calls `_count_recent_refreshes`, returns `(count >= limit, count)`. The "next attempt would be the (count+1)th" semantics means a count exactly at the limit is already exceeded — the cap blocks the would-be (limit+1)th refresh.
- `refresh()` POST flow extended: after `_parse_tier` resolution, reads `nl_text` + `cap_override = request.form.get("cap_override") == "1"`. Calls `_check_frequency_cap(db, uid, tier)`. If `cap_exceeded_now and not cap_override`, looks up the tier's `window_hours` from `_TIER_CAP_LIMITS` and re-renders `plans/v2/refresh.html` with `parent_plan` (unchanged from GET) + `nl_text_cap` (unchanged) + `prefill_nl_context=nl_text` (preserves the submitted text in the textarea) + `prefill_tier=tier` (highlights the matching tier button) + `cap_exceeded={"tier": tier, "count": current_count, "window_hours": window_hours}` (drives the modal markup). Otherwise resolves `cap_overridden = cap_exceeded_now and cap_override` per D4 and continues into the existing allocate → parse → orchestrate → persist → log → commit flow with the new value threaded into the final `_write_refresh_log` call.
- `_write_refresh_log` signature extended with `cap_overridden: bool = False` kwarg at the end of the param list. INSERT SQL extended: column list gains `cap_overridden` (positions 14 of 14); VALUES gains a 14th `?`; positional-params tuple appends `cap_overridden` at the end. Failure-path callers (the existing `OrchestrationError` + `Layer4InputError` + `Layer4OutputError` branches) keep the default `False` — failures don't override the gate.

### 3.3 `templates/plans/v2/refresh.html` — `#capExceededModal` + auto-open script

- Add `{% if cap_exceeded %}` block at the end of the `{% else %}` (plan-exists) branch, immediately after the closing `</form>` tag and before the `{% endif %}` that closes the `parent_plan is none` conditional.
- Modal: `id="capExceededModal" tabindex="-1" aria-labelledby="capExceededLabel" aria-hidden="true"` with `modal-dialog modal-dialog-centered` shell. Title `Refresh again?`. Body interpolates `{{ cap_exceeded.count }}` + tier + window_hours with grammar-correct "time" vs "times" via Jinja inline conditional. Footer two-element row: [Cancel] (outline-secondary, `data-bs-dismiss="modal"`) + a separate mini-form `<form method="post" action="{{ url_for('plan_refresh.refresh') }}" class="d-inline">` containing hidden `csrf_token` + hidden `nl_context` (`value="{{ prefill_nl_context or '' }}"`) + hidden `cap_override=1` + the [Refresh anyway] submit button named `submit_{{ cap_exceeded.tier|lower }}` so the override re-POST carries the original tier through `_parse_tier`'s named-submit-button branch.
- Inline `<script>` block immediately after the modal: 3 lines wrapped in an IIFE that runs at parse time — looks up `#capExceededModal` by ID, checks `window.bootstrap` + `window.bootstrap.Modal` availability (defensive against page loads where Bootstrap JS hasn't initialized yet), calls `window.bootstrap.Modal.getOrCreateInstance(modalEl).show()`. Mirrors the predecessor session's `{% if just_logged %}` script in `templates/workouts/suggestion_view.html` line-for-line — same defensive guards, same IIFE shape.

### 3.4 `tests/test_routes_plan_refresh.py` — +13 tests across 3 new classes + 2 added to TestWriteRefreshLog

- Imports: `datetime` + `timezone` added to the existing `date, timedelta` line; route-helper import block gains `_TIER_CAP_LIMITS` + `_check_frequency_cap` + `_count_recent_refreshes` (sorted alphabetically with the existing imports).
- `TestWriteRefreshLog` (existing class) extended with 2 tests:
  - `test_cap_overridden_defaults_to_false` — asserts the INSERT SQL contains `cap_overridden` + `params[13] is False` when the kwarg is omitted.
  - `test_cap_overridden_true_passed_through` — asserts `params[13] is True` when `cap_overridden=True` is passed.
- `TestTierCapLimits` (3 tests) — `test_t1_three_per_twenty_four_hours` + `test_t2_one_per_forty_eight_hours` + `test_t3_one_per_seven_days` — direct constant-pin assertions. Catches accidental edits to the limits or the underlying `_TIER_HORIZON_DAYS` confusion.
- `TestCountRecentRefreshes` (4 tests) —
  - `test_returns_count_from_row` (happy path: queued `{"n": 2}` row → returns 2);
  - `test_zero_when_no_row` (queued `{"n": 0}` row → returns 0);
  - `test_filters_user_tier_and_success` (asserts SQL contains `FROM plan_refresh_log` + `WHERE user_id = ?` + `tier = ?` + `success = TRUE` + `triggered_at >= ?`; asserts params order user_id=42 / tier='T3' / threshold = now - timedelta(hours=168) — verifying the window calculation lands in the placeholder);
  - `test_default_now_uses_utc` (monkeypatches `routes.plan_refresh.datetime` with a `_FrozenDatetime` class whose `now(tz)` captures the tz arg; calls `_count_recent_refreshes` without `now=` kwarg; asserts the captured tz is `timezone.utc`).
- `TestCheckFrequencyCap` (4 tests) —
  - `test_under_cap` (T1 count=2 → `(False, 2)`);
  - `test_at_cap_is_exceeded` (T1 count=3 → `(True, 3)`; pins the threshold semantics — count exactly equal to the limit is already over because the next attempt would be the (count+1)th);
  - `test_t2_at_cap` (T2 count=1 with limit=1 → `(True, 1)`);
  - `test_t3_window_hours_threaded` (T3 call → threshold = now - timedelta(hours=168) in the third positional param).

---

## 4. Code / tests

**Tests 1363 → 1376 (+13 net new in 1 extended test file):**

- `tests/test_routes_plan_refresh.py` +13 (56 total): 2 added to `TestWriteRefreshLog` + 3 new test classes (`TestTierCapLimits` 3 + `TestCountRecentRefreshes` 4 + `TestCheckFrequencyCap` 4).

**Container-runnable subset 696 → 709 in ~1.7s.**

Run reproducer for the container-runnable subset:

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
                    tests/test_routes_dashboard.py
# 709 passed, 12 skipped in 1.73s
```

**No-regression confirmation:** All 696 pre-existing container-subset tests pass unchanged. Touched modules: `init_db.py` (migration block append), `routes/plan_refresh.py` (2 new helpers + cap check threading + `_write_refresh_log` extension + module docstring rewrite), 1 template, 1 test file. No edits to `layer4/`, repos, schema beyond the column add, or specs.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 10+ predecessor handoffs §4). Full `pytest tests/` invocation fails collection on `tests/test_layer1_builder.py`; container-runnable subset above is the canonical green count.

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass.

**Step 1: `init_db.py` migration spot-check on Neon.** `\d plan_refresh_log` shows the new column `cap_overridden BOOLEAN NOT NULL DEFAULT FALSE` appended after the existing columns. Existing rows backfill to FALSE on the DEFAULT clause; verify via `SELECT COUNT(*) FILTER (WHERE cap_overridden) FROM plan_refresh_log` = 0 immediately post-migration.

**Step 2: T1 cap-hit happy path.** Andy (already has a `plan_versions` row from the plan-create walkthrough) navigates to `/plans/v2/refresh`. POST 3 successful T1 refreshes within 24h (any nl_text or empty; the 3rd should commit normally with `cap_overridden=FALSE` since `count=2` at the cap check before the 3rd lands). On the 4th refresh attempt confirm: (a) the form re-renders with the submitted `nl_context` still in the textarea + tier=T1 button highlighted via `prefill_tier='T1'`; (b) `#capExceededModal` Bootstrap modal auto-opens with title `Refresh again?`, body reading `You've already refreshed 3 T1 times in the last 24 hours.` + the cost-disclosure text-muted paragraph; (c) footer shows [Cancel] (outline-secondary) + [Refresh anyway] (primary); (d) click [Cancel] — modal closes, page stays on `/plans/v2/refresh` form, no new `plan_refresh_log` row inserted; (e) click [Refresh anyway] — the 4th refresh proceeds; the new `plan_refresh_log` row lands with `cap_overridden=TRUE` + `success=TRUE`; (f) immediately POST a 5th T1 refresh (without override) — the cap check still fires (single-use override per D3); the modal re-opens.

**Step 3: T2 + T3 cap sanity.** From a clean window (truncate `plan_refresh_log` or wait): POST 1 T2 refresh; immediately attempt a 2nd T2 refresh — modal fires with `tier='T2'` + `window_hours=48`. Same for T3 with `window_hours=168`.

**Step 4: Failure rows don't count.** Trigger an orchestrator failure mid-flight (e.g., unset `framework_sport` for Andy temporarily; expect `OrchestrationError('framework_sport_missing')`). A `plan_refresh_log` row lands with `success=FALSE` + `failure_reason='orchestration:framework_sport_missing'` + `cap_overridden=FALSE`. Restore `framework_sport`; immediately POST a T1 refresh — the cap check sees `count=0` (only `success=TRUE` rows count per D2) and the refresh proceeds normally without firing the modal.

**Step 5: Defensive cases.** (a) Direct-curl POST with `cap_override=1` + `submit_t1=1` against an under-cap window — proceeds normally with `cap_overridden=FALSE` per D4 (the route's own cap-check returned `exceeded=False`, so the override doesn't apply). (b) Cross-user URL probe via `_FakeConn`-style fixture is N/A here since the cap check uses the authenticated `current_user_id()` directly; the SQL is `user_id=?`-scoped.

Captured in `CARRY_FORWARD.md` manual walkthrough section (3 new scenarios under D-73 Phase 5.2 refresh frequency caps).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**`triggered_by_ad_hoc_id` plumbing wiring at `_write_refresh_log`** — the doc-sweep nit carried since the LogThis+T1Hook session. D-63 §5.4 column ships but its caller doesn't thread the FK; the T1 hook's [Yes — refresh] anchor URL encodes `nl_context` + `tier` only. To populate `triggered_by_ad_hoc_id`, add a third query param `triggered_by_ad_hoc_id=<id>` on the T1 hook anchor in `templates/workouts/suggestion_view.html`; thread it through `_resolve_prefill` (return type extends to 3-tuple `(nl_context, tier, triggered_by_ad_hoc_id)`) + render kwargs + a hidden form input on the refresh form; `_write_refresh_log` signature gains `triggered_by_ad_hoc_id: int | None = None` kwarg. ~1-2 files (`routes/plan_refresh.py` + `templates/workouts/suggestion_view.html` + `templates/plans/v2/refresh.html` + tests). `/plan` Trigger #5 (per-flow plumbing approach).

### 6.2 Alternative pivots

- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** (~5-6 files; need ~20-30 hand-labeled fixtures from Andy's PGE 2026 + AR vocab + a Haiku-vs-Sonnet agreement comparison harness; `/plan` Trigger #2 LLM-prompt-design gate would fire if prompt body changes for Haiku.)
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** (~1-2 files; doc-sweep nit from form-refresh C investigation; add `_evict_layer2c_on_equipment_change(db, uid)` mirror of the terrain helper + wire to both legacy + shared edit branches on actual equipment-set change. No `/plan` triggers.)
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1+#3+#5).
- **Layer 3A + 3B caching policy at orchestrator level** — all 4 entry points call `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` uncached. ~4-6 files.
- **Manual §5.0 walkthrough** of D-64 + D-63 + plan_create + dashboard CTAs + log-this/T1 hook + freq caps E2E on Neon (real-LLM ~$1.50 per pass across the 3 routes + T1 hook follow-on; freq-cap surface itself is no-cost beyond the modal interaction).
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).
- **Telemetry analytics surface for `plan_refresh_log`** per NL-8 (now that `cap_overridden` is populated, the override rate becomes a useful telemetry signal alongside parser-degraded rate and per-tier latency).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_FreqCaps_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Cap-exceeded UX = auto-open modal on re-render | Andy at AskUserQuestion gate | Picked over 302-redirect-with-query-params + inline-alert-banner. Mirrors the predecessor `#t1HookModal` pattern; minimal new JS surface; preserves submitted `nl_context` + tier highlighting via the existing `prefill_*` kwargs. |
| **D2** | Cap counting = `success=TRUE` rows only | Andy | Andy flipped from architect's "count-all-rows" recommendation. Fault-tolerance over conservative cost-protection — failed cascades shouldn't penalize the athlete retrying through a broken orchestrator. SQL filter: `AND success = TRUE`. |
| **D3** | Override scope = single-use per refresh | Andy | Picked over window-clearing override. Each subsequent submit re-checks the cap independently; matches D-64 §8 "athlete owns the decision" framing on a per-refresh cost-signal basis. |
| **D4** | `cap_overridden=TRUE` lands only on real-exceeded | Andy | Picked over trust-the-form-field. `cap_overridden = (route's own cap-check returned exceeded) AND (form arrived with cap_override=1)`. Stale forms / direct-curls land FALSE. Column reflects "athlete confirmed the cost gate," not "request contained an override field." |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` migration adds `cap_overridden` column to `plan_refresh_log` | ✅ `grep "cap_overridden BOOLEAN NOT NULL DEFAULT FALSE" init_db.py` |
| `routes/plan_refresh.py` defines `_TIER_CAP_LIMITS` constant | ✅ `grep "_TIER_CAP_LIMITS" routes/plan_refresh.py` |
| `routes/plan_refresh.py` defines `_count_recent_refreshes` | ✅ `grep "def _count_recent_refreshes" routes/plan_refresh.py` |
| `routes/plan_refresh.py` defines `_check_frequency_cap` | ✅ `grep "def _check_frequency_cap" routes/plan_refresh.py` |
| `routes/plan_refresh.py` `refresh()` POST checks the cap before allocating | ✅ `grep "cap_exceeded_now" routes/plan_refresh.py` |
| `routes/plan_refresh.py` `_write_refresh_log` accepts `cap_overridden` kwarg | ✅ `grep "cap_overridden: bool" routes/plan_refresh.py` |
| `templates/plans/v2/refresh.html` has the `#capExceededModal` modal block | ✅ `grep "capExceededModal" templates/plans/v2/refresh.html` |
| `templates/plans/v2/refresh.html` auto-open script fires on `{% if cap_exceeded %}` | ✅ `grep "cap_exceeded" templates/plans/v2/refresh.html` |
| `tests/test_routes_plan_refresh.py` has `TestTierCapLimits` + `TestCountRecentRefreshes` + `TestCheckFrequencyCap` classes | ✅ grep all 3 |
| `tests/test_routes_plan_refresh.py` `TestWriteRefreshLog` has cap_overridden default + true tests | ✅ grep |
| Container-runnable subset 696 → 709 (+13 net new) | ✅ pytest run returns "709 passed, 12 skipped in ~1.7s" |
| Tests 1363 → 1376 (+13 net new in 1 extended test file) | ✅ Counted via diff: 2 (TestWriteRefreshLog) + 3 (TestTierCapLimits) + 4 (TestCountRecentRefreshes) + 4 (TestCheckFrequencyCap) = +13 |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 FreqCaps handoff | ✅ |
| `CURRENT_STATE.md` Layer 4 status row updated to reflect freq caps landing | ✅ |
| `CARRY_FORWARD.md` NL-6 entry flipped to ✅ Shipped + 3 new manual §5.0 walkthrough scenarios added | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.FreqCaps` → ✅ Shipped 2026-05-21 | ✅ grep |

---

## 9. Files shipped this session

**Substantive (4 files; under the 5-file ceiling):**

1. `init_db.py` — 1 new migration appended to `_PG_MIGRATIONS` (cap_overridden column on plan_refresh_log).
2. `routes/plan_refresh.py` — 2 new helpers (`_count_recent_refreshes` + `_check_frequency_cap`) + new constant `_TIER_CAP_LIMITS` + POST flow cap check + `_write_refresh_log` cap_overridden kwarg + module docstring rewrite.
3. `templates/plans/v2/refresh.html` — conditional `#capExceededModal` markup + 3-line auto-open script.
4. `tests/test_routes_plan_refresh.py` — +13 tests across 3 new classes (TestTierCapLimits 3 + TestCountRecentRefreshes 4 + TestCheckFrequencyCap 4) + 2 added to existing TestWriteRefreshLog.

**Bookkeeping (4 files):**

5. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + Layer 4 status row.
6. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — NL-6 entry flipped to ✅ Shipped + 3 new manual §5.0 walkthrough scenarios.
7. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.FreqCaps`.
8. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_FreqCaps_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **NL-6 — Frequency caps per D-64 §8** entry → ✅ Shipped 2026-05-21 (`claude/logthis-t1-hook-phase5-UxDnv`). No intermediate `/plans/v2/refresh/confirm` page — modal-confirm flow uses the existing form re-render path instead.
- 3 new manual §5.0 walkthrough scenarios added under D-73 Phase 5.2 refresh frequency caps (migration spot-check + T1 cap-hit happy path with modal + cross-tier sanity + failure-rows-don't-count).
- `triggered_by_ad_hoc_id` plumbing nit still open — carried forward unchanged from the predecessor handoff (architect-recommended §6.1 forward move for the next session).

**Phase 5.2 caller-side v2 surfacing arc + log-this slice + post-log T1 plan-check hook + refresh frequency caps all complete; the D-64 §8 cost-gate now caps refresh traffic from the T1 hook end-to-end. The remaining caller-side nit is the `triggered_by_ad_hoc_id` plumbing wiring at `_write_refresh_log` for downstream telemetry attribution.**

---

**End of handoff.**
