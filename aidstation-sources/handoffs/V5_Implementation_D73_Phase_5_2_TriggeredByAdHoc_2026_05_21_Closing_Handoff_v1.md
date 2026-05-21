# D-73 Phase 5.2 `triggered_by_ad_hoc_id` Plumbing — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — `triggered_by_ad_hoc_id` plumbing per D-63 §5.4. Closes the §6.1 architect-recommended forward move from the FreqCaps handoff and the longstanding carry-forward doc-sweep nit (caller doesn't thread the FK) carried since LogThis+T1Hook 2026-05-21. **4 substantive files** (well under 5-file ceiling).
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_FreqCaps_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/triggered-by-ad-hoc-id` (renamed at session start from harness-pinned `claude/implement-freq-caps-phase-5-ma6n9` per CLAUDE.md branch-naming rule — freq caps already shipped to main via PR #122; mid-arc-same-surface justification doesn't apply since this work doesn't touch the cap surface).
**Status:** 4 substantive files. Tests 1376 → 1384 (+8 net new in 1 extended test file). Container-runnable subset 709 → 717 in ~1.6s. 16 skipped tests (12 NL parser smoke + 4 prior Layer 3 SDK smoke) unchanged.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (D-73 Phase 5.2 FreqCaps) handoff's §8 table against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` adds `cap_overridden BOOLEAN NOT NULL DEFAULT FALSE` on `plan_refresh_log` | `grep "cap_overridden BOOLEAN NOT NULL DEFAULT FALSE" init_db.py` | ✅ |
| `routes/plan_refresh.py` defines `_TIER_CAP_LIMITS` constant | grep | ✅ |
| `routes/plan_refresh.py` defines `_count_recent_refreshes` | grep | ✅ |
| `routes/plan_refresh.py` defines `_check_frequency_cap` | grep | ✅ |
| `routes/plan_refresh.py` `refresh()` POST checks cap before allocating | `grep "cap_exceeded_now"` | ✅ |
| `routes/plan_refresh.py` `_write_refresh_log` accepts `cap_overridden` kwarg | `grep "cap_overridden: bool"` | ✅ |
| `templates/plans/v2/refresh.html` has `#capExceededModal` block | grep | ✅ |
| `tests/test_routes_plan_refresh.py` has `TestTierCapLimits` + `TestCountRecentRefreshes` + `TestCheckFrequencyCap` | grep all 3 | ✅ |
| Container-runnable subset 709 passing | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 FreqCaps | grep | ✅ |

`./scripts/verify-handoff.sh` ran clean. No drift. Predecessor merged to main via PR #122 (`afbfe21`); the branch I'm on started equal to `origin/main` after the merge.

**Reconciliation note:** Clean. No in-progress work to inherit. Branch was harness-pinned for a slice that had already shipped — renamed to match this session's actual scope.

---

## 2. Session narrative

Andy ratified scope at the AskUserQuestion gate: **`triggered_by_ad_hoc_id` plumbing per D-63 §5.4** (the architect-recommended §6.1 forward move from the FreqCaps handoff, also the longstanding carry-forward doc-sweep nit) over the §6.2 alternatives (NL parser smoke-eval + Haiku 4.5 migration; Layer 2C equipment-edit invalidation gap; Form-refresh D structured supplements; Layer 3A/3B caching at orchestrator; manual §5.0 walkthrough on Neon; Plan Management spec authorship; real-LLM Layer 4 regression; telemetry analytics for `plan_refresh_log.cap_overridden`).

Pre-design surface survey:

- `init_db.py:1651` — `plan_refresh_log.triggered_by_ad_hoc_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)` shipped via D-63 §5.4 migration on 2026-05-21 (LogThis+T1Hook session) but no caller threads the FK.
- `routes/plan_refresh.py:175` — `_resolve_prefill(args) -> tuple[str, str | None]` parses `nl_context` + `tier` from query/form args; needs extension to 3-tuple to surface the new FK.
- `routes/plan_refresh.py:279` — `_write_refresh_log` signature already carries 14 columns (including `cap_overridden` from FreqCaps); needs `triggered_by_ad_hoc_id: int | None = None` kwarg appended.
- `routes/plan_refresh.py:392 / 419 / 477 / 499 / 530` — GET prefill resolution + POST cap check re-render + 3 `_write_refresh_log` call sites (success path + 2 failure paths); all need the FK threaded.
- `routes/ad_hoc_workouts.py:473-475` — `view_suggestion` builds `t1_hook_refresh_query = urlencode({'nl_context': ..., 'tier': 'T1'})`; needs `'triggered_by_ad_hoc_id': suggestion['id']` added.
- `templates/plans/v2/refresh.html:41-72` — main form needs a hidden input round-tripping the FK on POST; the existing cap-exceeded mini-form (`templates/plans/v2/refresh.html:101-109`) needs the same so the override path preserves attribution.

The 4 design questions surfaced at the AskUserQuestion gate per `/plan` Trigger #5 (architectural alternatives with real tradeoffs):

- **D1: Validate ownership at both GET (prefill) and POST (pre-log)** (Andy's pick). Picked over (a) POST-time only (slightly cheaper — no DB hit on GET; but form's hidden field would carry a bad value into the cap-exceeded mini-form re-render if the URL was stale/malicious) and (c) skip validation (cheapest; allows cross-user attribution telemetry pollution, low blast radius since the column can't be read back, but the column means less if it can lie). Defense-in-depth pick — the hidden field never carries a bad value into either the cap-exceeded mini-form re-render or the underlying `_write_refresh_log` INSERT.
- **D2: Silent drop to None on validation failure** (Andy's pick). Picked over reject-POST-with-flash. Telemetry is best-effort and the refresh itself is legitimate — punishing the athlete with a flash for a stale URL is the wrong UX trade.
- **D3: Cap-exceeded override mini-form carries the FK through** (Andy's pick). Picked over drop-on-override (argument: the override was a separate decision, not "caused by" the ad-hoc workout — weak; the underlying trigger was still the ad-hoc workout). Attribution survives the override path since the cost-confirmation is athlete-driven on the same underlying trigger.
- **D4: Both failure-path `_write_refresh_log` calls thread the FK** (Andy's pick). Picked over success-only (narrower meaning: "the workout that caused a successful refresh"; less useful telemetry — failed cascades are interesting data points that should preserve attribution). The orchestrator-error + Layer4-error paths both write a `plan_refresh_log` row; attribution is independent of success.

Implementation flow:

1. **`routes/ad_hoc_workouts.py`** — extend `view_suggestion` line 473's `urlencode({...})` dict with a third key `'triggered_by_ad_hoc_id': suggestion['id']` (the suggestion row is already in scope; `suggestion['id']` is the BIGINT PK that becomes the FK target). 1-line change + 2-line code comment per D-63 §5.4.

2. **`routes/plan_refresh.py`** — 5 sub-edits:
   - Module docstring extended with a 6-line paragraph documenting the D-63 §5.4 attribution flow (GET+POST validation per D1, silent collapse per D2, override + failure-path FK threading per D3+D4).
   - `_resolve_prefill(args)` extended from 2-tuple to 3-tuple return `(nl_context, tier, triggered_by_ad_hoc_id)`. Adds 5 lines for int-coercion via `int(raw_id) if raw_id else None` wrapped in `try/except (TypeError, ValueError) → None`. Function stays pure (no DB dependency) — ownership validation lives in a separate helper per D1 separation of parsing from validation, easing test isolation.
   - NEW `_validate_ad_hoc_id_for_user(db, user_id, ad_hoc_id) -> int | None` helper — 12 lines. Short-circuits to None on None input (no DB roundtrip). Otherwise issues `SELECT 1 AS ok FROM ad_hoc_workout_suggestions WHERE id = ? AND user_id = ?` and returns the ID on hit, None on miss (per D1+D2).
   - GET branch at line 388 — wraps `_resolve_prefill(request.args)` to unpack 3-tuple; calls `_validate_ad_hoc_id_for_user(db, uid, raw_prefill_ad_hoc_id)`; threads `prefill_triggered_by_ad_hoc_id` template kwarg.
   - POST branch at line 413 — reads `raw_form_ad_hoc_id = request.form.get("triggered_by_ad_hoc_id")`, int-coerces defensively (form values are strings), re-validates against current user (D1 second-pass: a tampered form arrives in POST even if GET was clean), binds `triggered_by_ad_hoc_id` for downstream use; threads through the cap-exceeded re-render's `prefill_triggered_by_ad_hoc_id` kwarg (D3) AND all 3 `_write_refresh_log` call sites (success path + both failure paths per D4).
   - `_write_refresh_log` signature extended with `triggered_by_ad_hoc_id: int | None = None` kwarg appended after `cap_overridden`. INSERT SQL extended: column list adds `triggered_by_ad_hoc_id` (position 15 of 15); VALUES gains a 15th `?`; positional-params tuple appends the new value at the end. Column placed at INSERT position 14 (after `cap_overridden` at 13) so the existing positional test indexes for `cap_overridden` at 13 + `success` at 11 + etc. remain stable — only the new tests touch position 14.

3. **`templates/plans/v2/refresh.html`** — 2 conditional `{% if prefill_triggered_by_ad_hoc_id %}<input type="hidden" name="triggered_by_ad_hoc_id" value="{{ prefill_triggered_by_ad_hoc_id }}">{% endif %}` blocks: (a) main form, immediately after the csrf_token hidden input; (b) cap-exceeded mini-form (the existing `<form>` containing hidden `csrf_token` + `nl_context` + `cap_override=1`), immediately after the `cap_override=1` hidden input. Per D3 the mini-form preserves attribution when the athlete confirms the cost gate.

4. **`tests/test_routes_plan_refresh.py`** — 8 new tests across 2 extended classes + 1 new class:
   - Imports: `_validate_ad_hoc_id_for_user` added to the route-helper imports (sorted alphabetically).
   - `TestResolvePrefill` (existing 7 tests): all 7 tests updated to unpack 3-tuple (most use `_` for the new field); `test_t1_hook_full_pattern` extended with `triggered_by_ad_hoc_id: "42"` query param input + int-coerced assertion. NEW: `test_triggered_by_ad_hoc_id_int_coerced` (`"123"` → `123`); `test_triggered_by_ad_hoc_id_blank_collapses_to_none` (`""` → `None`); `test_triggered_by_ad_hoc_id_non_numeric_collapses_to_none` (`"abc"` → `None`).
   - NEW `TestValidateAdHocIdForUser` (3 tests): `test_returns_none_for_none_input` (None input short-circuits — asserts `db.calls == []`); `test_returns_id_when_owned_by_user` (queued `{"ok": 1}` row → returns the ID; pins SQL contains `ad_hoc_workout_suggestions` + `id = ?` + `user_id = ?` + params order `(7, 42)`); `test_returns_none_when_not_owned` (no queued response → fetchone() returns None → returns None).
   - `TestWriteRefreshLog` extended with `test_triggered_by_ad_hoc_id_defaults_to_none` (asserts `"triggered_by_ad_hoc_id" in sql` + `params[14] is None`) + `test_triggered_by_ad_hoc_id_passed_through` (asserts `params[14] == 987`).

`/plan` Triggers fired: **#5** (per-flow plumbing approach with real tradeoffs — D1/D2/D3/D4 cleared via AskUserQuestion). Triggers #1 / #2 / #3 / #4 / #6 did not fire (no new prompt body, no vocab additions, no cross-layer schema change — column already exists from D-63 §5.4, no HITL gate, no architecture promotion). Note: Trigger #3 evaluated but cleared — no new column or contract change; the FK column was already on disk since the LogThis+T1Hook session 2026-05-21, this session only adds caller wiring.

---

## 3. File-by-file edits

### 3.1 `routes/ad_hoc_workouts.py` — 1 line change + 2-line comment in `view_suggestion`

- Insertion point: line 473 (the `urlencode({...})` dict).
- Adds `'triggered_by_ad_hoc_id': suggestion['id']` as a third key alongside `nl_context` + `tier`. The suggestion row is already in scope (loaded via `_get_suggestion(db, uid, suggestion_id)` at line 465); `suggestion['id']` is the BIGINT PK referenced by `plan_refresh_log.triggered_by_ad_hoc_id`. 2-line code comment annotated with D-63 §5.4 above the dict.

### 3.2 `routes/plan_refresh.py` — 5 sub-edits in 1 file

- **Module docstring extension:** appended 6-line "D-63 §5.4 attribution" paragraph after the existing "Frequency caps per D-64 §8" paragraph, documenting GET+POST validation per D1, silent best-effort collapse per D2, override + failure-path FK threading per D3+D4.
- **`_resolve_prefill(args) -> tuple[str, str | None, int | None]`:** signature extended from 2-tuple to 3-tuple. Adds int-coercion block via `int(raw_id) if raw_id else None` wrapped in `try/except (TypeError, ValueError)` collapsing to None. Function kept pure (no DB dependency) — ownership validation lives in a separate helper per D1 separation of concerns + test isolation. Docstring updated.
- **NEW `_validate_ad_hoc_id_for_user(db, user_id: int, ad_hoc_id: int | None) -> int | None`:** 12-line helper. None input short-circuits to None (no DB roundtrip). Otherwise issues `SELECT 1 AS ok FROM ad_hoc_workout_suggestions WHERE id = ? AND user_id = ?` via the standard `db.execute(...).fetchone()` pattern; returns the ID on hit, None on miss. Docstring references D-63 §5.4 + the best-effort-telemetry framing per D2.
- **GET branch (line 388-410):** unpacks 3-tuple from `_resolve_prefill(request.args)`; calls `_validate_ad_hoc_id_for_user(db, uid, raw_prefill_ad_hoc_id)`; threads `prefill_triggered_by_ad_hoc_id=prefill_triggered_by_ad_hoc_id` template kwarg. Inline comment explains the D1 GET-side validation.
- **POST branch (line 413-434):** new block immediately after `cap_override = request.form.get("cap_override") == "1"`. Reads `raw_form_ad_hoc_id = request.form.get("triggered_by_ad_hoc_id")`, int-coerces defensively (form values are always strings), re-validates against current user via `_validate_ad_hoc_id_for_user` (D1 second-pass: a tampered form arrives in POST even if GET was clean). The resolved `triggered_by_ad_hoc_id` is then threaded into: (a) the cap-exceeded re-render's `prefill_triggered_by_ad_hoc_id` kwarg (D3); (b) the orchestrator-failure-path `_write_refresh_log` call (D4); (c) the Layer4-error-path `_write_refresh_log` call (D4); (d) the success-path `_write_refresh_log` call. Inline comment explains the D-63 §5.4 attribution flow.
- **`_write_refresh_log`:** signature extended with `triggered_by_ad_hoc_id: int | None = None` kwarg appended after `cap_overridden`. INSERT SQL extended: column list adds `triggered_by_ad_hoc_id` (position 15 of 15 in the column list); VALUES adds a 15th `?`; positional-params tuple appends `triggered_by_ad_hoc_id` at the end (positional index 14 in the params tuple, 0-indexed). Column placed at INSERT position 14 (after `cap_overridden` at 13) so the existing positional test indexes for `cap_overridden`, `success`, etc. remain stable — only the new tests touch position 14.

### 3.3 `templates/plans/v2/refresh.html` — 2 conditional hidden input blocks

- **Main form (after csrf_token, line 42-48 area):** NEW `{% if prefill_triggered_by_ad_hoc_id %}<input type="hidden" name="triggered_by_ad_hoc_id" value="{{ prefill_triggered_by_ad_hoc_id }}">{% endif %}` block. 2-line Jinja comment annotated with D-63 §5.4.
- **Cap-exceeded mini-form (after `cap_override=1` hidden input, line 106-109 area):** NEW conditional hidden input identical to (a). 2-line Jinja comment notes per D3 preservation of attribution through the override path.

### 3.4 `tests/test_routes_plan_refresh.py` — +8 tests across 2 extended classes + 1 new class

- **Imports:** `_validate_ad_hoc_id_for_user` added to the route-helper imports (alphabetically sorted between `_resolve_scope_dates` and `_run_parser` block — see actual line ordering).
- **`TestResolvePrefill` (existing 7 tests + 3 NEW):**
  - All 7 existing tests updated to unpack 3-tuple from `_resolve_prefill(...)` (most use `_` for the new field).
  - `test_t1_hook_full_pattern` extended to pass `triggered_by_ad_hoc_id: "42"` query param input + asserts int coercion to `42`.
  - NEW `test_triggered_by_ad_hoc_id_int_coerced` (`"123"` → `123`).
  - NEW `test_triggered_by_ad_hoc_id_blank_collapses_to_none` (`""` → `None`).
  - NEW `test_triggered_by_ad_hoc_id_non_numeric_collapses_to_none` (`"abc"` → `None`).
- **NEW `TestValidateAdHocIdForUser` (3 tests):**
  - `test_returns_none_for_none_input` — None input short-circuits without a DB roundtrip; asserts `db.calls == []`.
  - `test_returns_id_when_owned_by_user` — queued `{"ok": 1}` row → returns the ID; asserts SQL contains `ad_hoc_workout_suggestions` + `id = ?` + `user_id = ?` + params order `(7, 42)`.
  - `test_returns_none_when_not_owned` — no queued response → `fetchone()` returns None → helper returns None.
- **`TestWriteRefreshLog` extended +2 tests:**
  - `test_triggered_by_ad_hoc_id_defaults_to_none` — asserts column name in SQL + `params[14] is None`.
  - `test_triggered_by_ad_hoc_id_passed_through` — asserts `params[14] == 987` when kwarg passed.

---

## 4. Code / tests

**Tests 1376 → 1384 (+8 net new in 1 extended test file):**

- `tests/test_routes_plan_refresh.py` +8 (was 56 with FreqCaps + LogThis adds, now 64): 3 added to `TestResolvePrefill` + 3 new `TestValidateAdHocIdForUser` + 2 added to `TestWriteRefreshLog`. (Pre-this-session count was 56; after FreqCaps shipped on 2026-05-21 the file had 56. Note: existing 7 `TestResolvePrefill` tests were modified for 3-tuple unpack but kept; only 3 NEW tests added there.)

**Container-runnable subset 709 → 717 in ~1.6s.**

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
# 717 passed, 12 skipped in 1.62s
```

**No-regression confirmation:** All 709 pre-existing container-subset tests pass unchanged. Touched modules: `routes/ad_hoc_workouts.py` (1-line urlencode dict extension), `routes/plan_refresh.py` (3-tuple `_resolve_prefill` + new validator helper + GET/POST threading + `_write_refresh_log` kwarg + module docstring), 1 template, 1 test file. No edits to `init_db.py` (column already on disk since D-63 §5.4 LogThis+T1Hook session), `layer4/`, repos, schema, or specs.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 10+ predecessor handoffs §4). Full `pytest tests/` invocation fails collection on `tests/test_layer1_builder.py`; container-runnable subset above is the canonical green count.

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass.

**Step 1: T1 hook attribution happy path.** Andy logs a cardio workout via `/workouts/build` → `[Log this workout]`; on the auto-opened T1 hook modal, clicks `[Yes — refresh]`; confirm the URL is `/plans/v2/refresh?nl_context=...&tier=T1&triggered_by_ad_hoc_id=<suggestion_id>` (the new third query param). On `/plans/v2/refresh` GET, view the rendered form HTML and confirm `<input type="hidden" name="triggered_by_ad_hoc_id" value="<id>">` is present inside the main form. Submit the T1 refresh (any nl_text or as-is from the pre-fill). Confirm `SELECT triggered_by_ad_hoc_id FROM plan_refresh_log WHERE id = <new_row_id>` returns the originating `ad_hoc_workout_suggestions.id` (not NULL).

**Step 2: Defensive cases — non-existent ID.** Hand-craft a URL `/plans/v2/refresh?nl_context=hi&tier=T1&triggered_by_ad_hoc_id=99999999` (id that doesn't exist anywhere). Navigate to it. Confirm the form renders with NO hidden `triggered_by_ad_hoc_id` field (validated-and-collapsed-to-None at GET-side per D1). Submit the form. Confirm the resulting `plan_refresh_log` row lands with `triggered_by_ad_hoc_id IS NULL` (silent collapse per D2).

**Step 3: Defensive cases — cross-user ID.** Hand-craft a URL with another user's actual suggestion id (find one via `SELECT id, user_id FROM ad_hoc_workout_suggestions WHERE user_id != <andy_id> LIMIT 1`). Confirm same silent-collapse behavior — the GET-side validation rejects the cross-user ID; the hidden form field is absent; the resulting `plan_refresh_log` row has `triggered_by_ad_hoc_id IS NULL`.

**Step 4: Defensive cases — non-numeric.** Hand-craft `/plans/v2/refresh?nl_context=hi&tier=T1&triggered_by_ad_hoc_id=abc`. Confirm GET renders with no hidden field; POST lands with NULL.

**Step 5: Cap-exceeded override preserves attribution (D3).** Trigger an over-cap T1 refresh from the T1 hook anchor (POST 3 successful T1 refreshes within 24h first to fill the cap; the 4th from the T1 hook click-through triggers the modal). View the cap-exceeded modal's `[Refresh anyway]` mini-form HTML and confirm `<input type="hidden" name="triggered_by_ad_hoc_id" value="<id>">` is present inside the mini-form (alongside the existing `cap_override=1` + `nl_context` + `csrf_token` hidden inputs). Click `[Refresh anyway]`. Confirm the resulting `plan_refresh_log` row has BOTH `cap_overridden=TRUE` AND `triggered_by_ad_hoc_id=<suggestion_id>` (attribution preserved through the override per D3).

**Step 6: Failure-path attribution (D4).** Temporarily unset Andy's `framework_sport` to force an `OrchestrationError("framework_sport_missing")` mid-flight. Initiate a T1 refresh from the T1 hook anchor. Confirm the resulting `plan_refresh_log` row has `success=FALSE` + `failure_reason='orchestration:framework_sport_missing'` + `triggered_by_ad_hoc_id=<suggestion_id>` (attribution preserved through the failure path per D4). Restore `framework_sport`.

Captured in `CARRY_FORWARD.md` manual walkthrough section (1 new scenario `2 D-73 Phase 5.2 triggered_by_ad_hoc_id plumbing` covering all 6 steps).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Manual §5.0 walkthrough on Neon** — the §6.2 #5 alternative from the FreqCaps handoff. End-to-end test pass across D-64 + D-63 + plan_create + dashboard CTAs + log-this/T1 hook + freq caps + the new `triggered_by_ad_hoc_id` attribution, using real LLMs. Costs ~$1.50/pass across the 3 routes + T1 hook follow-on; freq-cap surface itself is no-cost beyond the modal click; new `triggered_by_ad_hoc_id` surface is no-cost beyond the URL inspection. This is the canonical "did this actually work" check that no test harness replaces — the caller-side v2 surfacing arc is now end-to-end complete on the code surface; the manual walkthrough validates against Andy's live Neon production data + real-LLM cost realism. No `/plan` triggers.

### 6.2 Alternative pivots

- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** (~5-6 files; need ~20-30 hand-labeled fixtures from Andy's PGE 2026 + AR vocab + a Haiku-vs-Sonnet agreement comparison harness; `/plan` Trigger #2 LLM-prompt-design gate would fire if prompt body changes for Haiku).
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** (~1-2 files; doc-sweep nit from form-refresh C investigation; add `_evict_layer2c_on_equipment_change(db, uid)` mirror of the terrain helper + wire to both legacy + shared edit branches on actual equipment-set change. No `/plan` triggers).
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1+#3+#5).
- **Layer 3A + 3B caching policy at orchestrator level** — all 4 entry points call `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` uncached. ~4-6 files.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).
- **Telemetry analytics surface for `plan_refresh_log`** per NL-8 — now that both `cap_overridden` AND `triggered_by_ad_hoc_id` are populated end-to-end, the override rate + T1-hook attribution rate become useful telemetry signals alongside parser-degraded rate and per-tier latency. ~3-4 files (admin/telemetry view + repo query + template).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_TriggeredByAdHoc_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | User-scope validation at both GET (prefill) and POST (pre-log) | Andy at AskUserQuestion gate | Picked over POST-only + skip-validation. Defense-in-depth — the form's hidden field never carries a bad value into the cap-exceeded mini-form re-render or the underlying `_write_refresh_log` INSERT. Adds 1 DB hit per GET render (cheap `SELECT 1`). |
| **D2** | Silent drop to None on validation failure | Andy | Picked over reject-POST-with-flash. Telemetry is best-effort and the refresh itself is legitimate — punishing the athlete with a flash for a stale URL is the wrong UX trade. |
| **D3** | Cap-exceeded override mini-form carries the FK through | Andy | Picked over drop-on-override. Attribution survives the override since the cost-confirmation is athlete-driven on the same underlying ad-hoc trigger. |
| **D4** | Both failure-path `_write_refresh_log` calls thread the FK | Andy | Picked over success-only. Attribution is independent of success — failed cascades are interesting telemetry that should preserve attribution. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `routes/ad_hoc_workouts.py` T1 hook anchor adds `triggered_by_ad_hoc_id` query param | ✅ `grep "'triggered_by_ad_hoc_id': suggestion\['id'\]" routes/ad_hoc_workouts.py` |
| `routes/plan_refresh.py` `_resolve_prefill` returns 3-tuple including `triggered_by_ad_hoc_id` | ✅ `grep "tuple\[str, str | None, int | None\]" routes/plan_refresh.py` |
| `routes/plan_refresh.py` defines `_validate_ad_hoc_id_for_user` | ✅ `grep "def _validate_ad_hoc_id_for_user" routes/plan_refresh.py` |
| `routes/plan_refresh.py` POST flow reads + validates form field | ✅ `grep "raw_form_ad_hoc_id" routes/plan_refresh.py` |
| `routes/plan_refresh.py` `_write_refresh_log` accepts `triggered_by_ad_hoc_id` kwarg | ✅ `grep "triggered_by_ad_hoc_id: int | None" routes/plan_refresh.py` |
| `routes/plan_refresh.py` GET threads `prefill_triggered_by_ad_hoc_id` to template | ✅ `grep "prefill_triggered_by_ad_hoc_id" routes/plan_refresh.py` |
| `templates/plans/v2/refresh.html` main form has hidden input | ✅ `grep "name=\"triggered_by_ad_hoc_id\"" templates/plans/v2/refresh.html` (returns 2 — main form + mini-form) |
| `templates/plans/v2/refresh.html` cap-exceeded mini-form preserves FK | ✅ same grep above returns 2 occurrences |
| `tests/test_routes_plan_refresh.py` has `TestValidateAdHocIdForUser` class | ✅ grep |
| `tests/test_routes_plan_refresh.py` `TestResolvePrefill` has int_coerced + collapse tests | ✅ grep |
| `tests/test_routes_plan_refresh.py` `TestWriteRefreshLog` has triggered_by_ad_hoc_id default + true tests | ✅ grep |
| Container-runnable subset 709 → 717 (+8 net new) | ✅ pytest run returns "717 passed, 12 skipped in ~1.6s" |
| Tests 1376 → 1384 (+8 net new in 1 extended test file) | ✅ Counted via diff: 3 (TestResolvePrefill NEW) + 3 (TestValidateAdHocIdForUser NEW) + 2 (TestWriteRefreshLog NEW) = +8 |
| `CURRENT_STATE.md` last-shipped pointer flipped to TriggeredByAdHoc handoff | ✅ |
| `CARRY_FORWARD.md` `_write_refresh_log` open nit flipped to ✅ Shipped + 1 new manual §5.0 walkthrough scenario added | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.TriggeredByAdHoc` → ✅ Shipped 2026-05-21 | ✅ grep |
| Branch renamed `claude/implement-freq-caps-phase-5-ma6n9` → `claude/triggered-by-ad-hoc-id` | ✅ `git branch` |

---

## 9. Files shipped this session

**Substantive (4 files; under the 5-file ceiling):**

1. `routes/ad_hoc_workouts.py` — 1-line addition to `view_suggestion`'s T1 hook `urlencode({...})` dict + 2-line code comment.
2. `routes/plan_refresh.py` — module docstring extension; `_resolve_prefill` extended to 3-tuple; NEW `_validate_ad_hoc_id_for_user` helper; GET branch validates + threads template kwarg; POST branch reads + re-validates form field + threads through cap-exceeded re-render + all 3 `_write_refresh_log` call sites; `_write_refresh_log` signature + INSERT extended.
3. `templates/plans/v2/refresh.html` — 2 conditional hidden inputs (main form + cap-exceeded mini-form).
4. `tests/test_routes_plan_refresh.py` — +8 tests across 2 extended classes + 1 new class (3 added to `TestResolvePrefill` + NEW `TestValidateAdHocIdForUser` 3 + 2 added to `TestWriteRefreshLog`).

**Bookkeeping (4 files):**

5. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + this session's narrative.
6. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — `_write_refresh_log` open nit flipped to ✅ Shipped + 1 new manual §5.0 walkthrough scenario.
7. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.TriggeredByAdHoc`.
8. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_TriggeredByAdHoc_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **`routes/plan_refresh.py:_write_refresh_log` does NOT populate `triggered_by_ad_hoc_id`** open nit → ✅ Shipped 2026-05-21 (`claude/triggered-by-ad-hoc-id`). The longstanding doc-sweep nit carried since LogThis+T1Hook 2026-05-21 is closed end-to-end.
- 1 new manual §5.0 walkthrough scenario added under D-73 Phase 5.2 `triggered_by_ad_hoc_id` plumbing (T1 hook attribution happy path + 4 defensive cases + cap-exceeded override preserves attribution + failure-path attribution).
- Architect-recommended §6.1 forward move flips to **Manual §5.0 walkthrough on Neon** — the caller-side v2 surfacing arc is now complete on the code surface; the manual walkthrough is the canonical "did this actually work end-to-end against real LLMs + Neon" check.

**Phase 5.2 caller-side v2 surfacing arc + log-this slice + post-log T1 plan-check hook + refresh frequency caps + `triggered_by_ad_hoc_id` attribution all complete; D-63 + D-64 caller-side surfaces are now end-to-end coherent from `/workouts/build` → `[Log this workout]` → T1 hook modal → `/plans/v2/refresh` → cap check → orchestrate → log row with full FK attribution back to the originating ad-hoc workout. The manual §5.0 Neon walkthrough is the next genuine forward move; the only remaining caller-side code surface is the orthogonal NL parser smoke-eval + Haiku migration arc.**

---

**End of handoff.**
