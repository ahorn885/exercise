# D-73 Phase 5.2 Log-this + T1 Hook — Closing Handoff

**Session:** D-73 Phase 5.2 log-this slice + D-63 T1 plan-check hook. Wires [Log this workout] on the on-demand workout result view to persist into `cardio_log` / `training_log` tagged with `is_ad_hoc=TRUE`, then auto-fires a Bootstrap modal offering a T1 plan refresh with NL context pre-filled per D-63 §3.5. Closes the §6.1 architect-recommended forward move from the D-73 Phase 5.2 Dashboard CTAs handoff. **7 substantive files** (above 5-file ceiling, ratified at AskUserQuestion gate; precedented by 5.1.A=8 / 5.1.C=8 / 5.2.Caller-D63+PlanCreate=9 / 5.2.Caller-D64=8).
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Dashboard_CTAs_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/log-this-t1-hook-pcIhF` (renamed at session start from harness-pinned `claude/dashboard-ctas-implementation-pcIhF` per CLAUDE.md branch-naming rule — the pinned name matched the prior session's scope, not this one).
**Status:** 7 substantive files. Tests 1334 → 1363 (+29 net new across 2 extended test files). Container-runnable subset 667 → 696 in ~1.7s. 16 skipped tests (12 NL parser smoke + 4 prior Layer 3 SDK smoke) unchanged.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (D-73 Phase 5.2 Dashboard CTAs) handoff's §8 table against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `templates/dashboard.html` has new "Quick actions" row | `grep "Quick actions (Layer 4 v2 entry points)"` | ✅ |
| `templates/dashboard.html` references `url_for('ad_hoc_workouts.build_workout')` | grep | ✅ |
| `templates/dashboard.html` references `url_for('plan_create.new_plan')` | grep | ✅ |
| `templates/dashboard.html` references `url_for('plan_refresh.refresh')` | grep | ✅ |
| `templates/dashboard.html` Refresh card has `{% if has_plan_version %}` + `opacity-50` + `btn-secondary disabled` | grep | ✅ |
| `routes/dashboard.py` defines `_has_plan_version` | grep | ✅ |
| `routes/dashboard.py` threads `has_plan_version` into `render_template` | grep | ✅ |
| `tests/test_routes_dashboard.py` exists with `TestHasPlanVersion` class | grep | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 row `5.2.Dashboard-CTAs` | grep | ✅ |
| Container-runnable subset green at 667 | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 Dashboard CTAs | grep | ✅ |

`./scripts/verify-handoff.sh` ran clean — all referenced files present. Branch pinned name (`claude/dashboard-ctas-implementation-pcIhF`) mismatched scope; renamed to `claude/log-this-t1-hook-pcIhF` at session start per CLAUDE.md branch-naming rule. No drift.

**Reconciliation note:** Clean. Dashboard CTAs (predecessor) merged to main via PR #120 (`820f1e0`); this branch started equal to `origin/main`. No in-progress work to inherit.

---

## 2. Session narrative

Andy ratified scope at the AskUserQuestion gate: **log-this slice + D-63 T1 plan-check hook** (the architect-recommended §6.1 forward move from the dashboard CTAs handoff), over the §6.2 alternatives (NL parser freq caps, equipment-edit cache gap, orchestrator 3A/3B caching).

Pre-design surface survey:

- `aidstation-sources/OnDemand_Workout_D63_Design_v1.md:99-105` — §3.5 spec: button [Log this workout] → write to `cardio_log`/`training_log` with `is_ad_hoc=TRUE` → banner "Logged. Want to refresh the next 2 days based on this session? [Yes — refresh] [No, thanks]" → [Yes] fires T1 with NL pre-filled / [No, thanks] logs `t1_hook_dismissed=TRUE`.
- `OnDemand_Workout_D63_Design_v1.md:153-162` + `:164-173` — §5.1 / §5.2 prescribe `cardio_log` + `training_log` column extensions: `is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE` + `ad_hoc_request_payload JSONB` + `ad_hoc_suggestion_id BIGINT` + partial index `(user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE`.
- `OnDemand_Workout_D63_Design_v1.md` §5.4 — names `triggered_by_ad_hoc_id BIGINT` column on `plan_refresh_log`. Not yet present; this session adds it.
- `init_db.py:123-137` + `:86-101` — current `cardio_log` + `training_log` PG_SCHEMA. No `is_ad_hoc` columns yet.
- `init_db.py:1587-1602` — `ad_hoc_workout_suggestions` already has `logged_into_table` + `logged_into_id` (reserved by predecessor handoff for this slice).
- `routes/ad_hoc_workouts.py` — existing routes: GET/POST `/workouts/build`, GET `/workouts/suggestions/<id>`, POST `/.../discard`, POST `/.../regenerate`. Natural insertion point for log + dismiss_t1_hook after `regenerate_suggestion`.
- `routes/plan_refresh.py:313-328` — GET handler renders refresh.html; no query-param prefill mechanism yet.
- `templates/workouts/suggestion_view.html:88-90` — explicit placeholder `[Log this workout] coming in a follow-on (paired with the D-64 T1 plan-check hook)`. Struck this session.

The 4 design questions surfaced at the AskUserQuestion gate per `/plan` Trigger #5 (architectural alternatives) + Trigger #1 (form copy) + Trigger #3 (cross-layer schema):

- **D1: T1 hook UX shape = auto-fired Bootstrap modal.** Picked over (a) inline post-redirect banner (my recommendation; simplest, no JS), (c) direct 302 to refresh form (loses [No, thanks] flow), (d) flash banner on dashboard (low discoverability). Modal implementation kept JS-light: pre-render the modal markup conditionally in the template; auto-open via a 3-line inline `<script>` that checks `window.bootstrap.Modal.getOrCreateInstance(...).show()` on `?just_logged=1` query param. No AJAX adapter — log POST is a plain form submit + 302 redirect.
- **D2: `t1_hook_dismissed` telemetry placement = NEW `t1_hook_telemetry` table.** Picked over (a) two columns on `ad_hoc_workout_suggestions` (my recommendation; sparser, no new table), (c) skip telemetry. Andy's pick is extensible — future hook event types (partial-dismiss, deferred-refresh) can land as additional column on the same table without churning the suggestions schema. Cost: 1 new table + 1 index.
- **D4: NL context auto-fill template = verbatim intensity word.** Picked: `f"Did an unscheduled {duration_min}min {sport} ({intensity}) at {locale}"`. Intensity renders verbatim from the request payload — `easy` / `moderate` / `hard` / `race pace` (underscore → space). Picked over (b) HR-zone translation (would require a static intensity→zone map that doesn't reflect athlete-specific zones), (c) skip intensity (loses parser signal). Locale fallback chain matches the existing template precedence on `suggestion_view.html:24`: `sess.locale_name or sess.locale_id or req.locale_slug`. Trigger #1 ratified — copy ships verbatim.
- **D5: Refresh form prefill mechanism = query-param.** Picked: `/plans/v2/refresh?nl_context=<encoded>&tier=T1`. Picked over (b) flask flash (mixed semantics with warnings/errors), (c) session storage (state coupling between routes), (d) auto-submit T1 refresh (loses editability — D-63 §3.5 explicitly says "athlete sees the D-64 modal with NL pre-filled (editable)"). Implementation: GET handler reads `request.args.get('nl_context')` + `.get('tier')`, passes to template; refresh.html populates textarea + highlights matching tier button (filled vs outline-primary).

Implementation flow:

1. **`init_db.py`** — 4 new migration blocks appended after the existing `plan_refresh_log` index in `_PG_MIGRATIONS`:
   - 3× `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS …` for `is_ad_hoc` / `ad_hoc_request_payload` / `ad_hoc_suggestion_id` + 1× partial `CREATE INDEX … WHERE is_ad_hoc = TRUE` per D-63 §5.1
   - 3× `ALTER TABLE training_log ADD COLUMN IF NOT EXISTS …` (mirror) + 1× partial index per D-63 §5.2
   - 1× `ALTER TABLE plan_refresh_log ADD COLUMN IF NOT EXISTS triggered_by_ad_hoc_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)` per D-63 §5.4
   - NEW `t1_hook_telemetry` table per D-63 §3.5 + dismissed_at index

2. **`routes/ad_hoc_workouts.py`** — 6 new helpers + 2 new routes:
   - `_render_nl_context(request_payload, generated_session) -> str` — D-63 §3.5 auto-fill string. Verbatim intensity (underscore → space); locale fallback chain matches template precedence.
   - `_log_cardio_session(db, ..., today)` — INSERT one `cardio_log` row tagged `is_ad_hoc=TRUE`; notes column concatenates `coaching_intent` + `session_notes`.
   - `_log_strength_session(db, ..., today)` — INSERT one `training_log` row per `StrengthExercise`; returns first row id (canonical `logged_into_id`); int `reps_per_set` persists to `target_reps`, str ranges (`"6-8"`) fall to notes column with `Load:` / `Tempo:` / `Reps:` prefixes.
   - `_mark_logged(db, suggestion_id, user_id, *, logged_into_table, logged_into_id)` — flips suggestion status to `'logged'` + populates pointers per §5.5.
   - `_record_t1_dismiss(db, user_id, suggestion_id)` — INSERTs one `t1_hook_telemetry` row per §3.5.
   - `view_suggestion()` extended: reads `?just_logged=1` query param, computes server-side `t1_hook_nl_context` deterministically from request_payload + session, builds `t1_hook_refresh_query` via `urlencode({nl_context, tier:'T1'})`, threads all 3 into template.
   - POST `/workouts/suggestions/<id>/log` → `log_suggestion()`: defensive checks status='suggested' + generated_session non-None; dispatches on session.kind ('cardio'/'strength'); atomic per D-64 §6.2 — `db.commit()` fires only after both INSERT into log table + UPDATE on suggestions both succeed; on error rolls back. Redirects to `/workouts/suggestions/<id>?just_logged=1`.
   - POST `/workouts/suggestions/<id>/dismiss_t1_hook` → `dismiss_t1_hook()`: INSERTs telemetry row + commits + 302s to suggestion view (no `?just_logged=1` so modal doesn't re-open). Idempotent at the row level — each POST is a new telemetry event.
   - `_get_suggestion()` extended: SELECT now includes `logged_into_table` + `logged_into_id`; result dict carries them. Uses `row.get()` for tolerance to test fixtures that don't queue all columns.

3. **`templates/workouts/suggestion_view.html`** — 3 changes:
   - Strike the placeholder `[Log this workout] coming in a follow-on` note (line 89 in predecessor).
   - Add `<form>` POSTing to `ad_hoc_workouts.log_suggestion` with `[Log this workout]` `btn-primary` button (leftmost in the d-flex gap-2 row), only on `status='suggested'`.
   - Add `status='logged'` branch rendering `Logged ✓ — Saved to your cardio/training log.` text.
   - Add modal markup at end of `content` block: `#t1HookModal` with title `Logged ✓`, body containing the auto-fill preview + the two action buttons (form-wrapped [No, thanks] POSTing to `dismiss_t1_hook` + anchor [Yes — refresh] linking to `/plans/v2/refresh?{t1_hook_refresh_query}`).
   - Inline `<script>` block that runs only when `{% if just_logged %}` — uses `URLSearchParams`-equivalent (just checks for the modal element + Bootstrap availability) + `bootstrap.Modal.getOrCreateInstance(modalEl).show()`.

4. **`routes/plan_refresh.py`** — 2 changes:
   - NEW `_resolve_prefill(args) -> tuple[str, str | None]` helper at module scope — reads `args.get('nl_context')` + `.get('tier')`, caps nl_context at `_NL_TEXT_SOFT_CAP_CHARS`, validates tier against `VALID_TIERS` (unknown/blank → None).
   - `refresh()` GET branch threads `prefill_nl_context` + `prefill_tier` into the template context.

5. **`templates/plans/v2/refresh.html`** — 2 changes:
   - Textarea body switches from `></textarea>` to `>{{ prefill_nl_context or '' }}</textarea>` (Jinja outputs nothing when None/empty).
   - 3 tier buttons gain conditional class: `btn-primary` when `prefill_tier is none` (default — preserves existing all-equal visual) OR matches this tier; `btn-outline-primary` otherwise.

6. **`tests/test_routes_ad_hoc_workouts.py`** — extended with 7 new test classes (+22 net new tests):
   - `TestRenderNlContext` 5 — happy path, race_pace renders with space, locale fallback chain (3 cases), blank intensity drops clause.
   - `TestLogCardioSession` 5 — INSERT shape + returns id, notes concatenation, notes None when both blank, raises on missing RETURNING, does not commit.
   - `TestLogStrengthSession` 5 — one row per exercise + returns first id, int-vs-str reps handling + notes formatting, raises on empty `strength_exercises`, raises mid-insert on missing RETURNING, does not commit.
   - `TestMarkLogged` 2 — SQL shape + params + no-commit, training_log table value accepted.
   - `TestRecordT1Dismiss` 2 — INSERT shape, per-event semantics (two calls = two rows).
   - `TestGetSuggestionLoggedFields` 3 — logged status returns table + id, suggested status returns None pointers, SELECT query includes new columns.
   - Imports extended for the 6 new helpers.

7. **`tests/test_routes_plan_refresh.py`** — 1 new test class (+7 net new tests):
   - `TestResolvePrefill` 7 — empty args, nl_context passthrough, tier uppercase, unknown tier → None, blank tier → None, soft-cap truncation, full T1-hook pattern.
   - Import extended for `_resolve_prefill`.

`/plan` Triggers fired: #5 (UX shape + telemetry placement + prefill mechanism) cleared via AskUserQuestion before drafting. #1 (auto-fill NL template + log button copy + modal copy) iterative — drafts approved at the same gate. #3 (3 new columns on `cardio_log`/`training_log` shared tables + 1 new column on `plan_refresh_log` + NEW `t1_hook_telemetry` table — cross-layer schema surface) ratified at the same gate. Triggers #2 / #4 / #6 did not fire.

---

## 3. File-by-file edits

### 3.1 `init_db.py` — 4 migration blocks appended to `_PG_MIGRATIONS`

- Insertion point: between `plan_refresh_log_user_triggered_idx` index (line 1632 in predecessor) and the closing `]`.
- 3× `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS …` for `is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE` / `ad_hoc_request_payload JSONB` / `ad_hoc_suggestion_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)` per D-63 §5.1.
- Partial index `CREATE INDEX IF NOT EXISTS cardio_log_ad_hoc_idx ON cardio_log (user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE` per spec.
- Mirror 3× for `training_log` + 1 partial index per D-63 §5.2.
- 1× `ALTER TABLE plan_refresh_log ADD COLUMN IF NOT EXISTS triggered_by_ad_hoc_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)` per D-63 §5.4.
- NEW table `t1_hook_telemetry`: BIGSERIAL PK + user_id FK + suggestion_id FK + `dismissed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` + `created_at` + 1 index `(user_id, dismissed_at DESC)`. Decoupled from `ad_hoc_workout_suggestions` per D2 so future hook event types extend without schema churn on the suggestions table.

### 3.2 `routes/ad_hoc_workouts.py` — 6 new helpers + 2 new routes + `_get_suggestion` extension

- Module docstring updated: predecessor's `[Log this workout] is not wired here` block struck; new paragraph documents the §5.1/§5.2/§3.5 wiring + the modal flow.
- New imports: `datetime.date`, `urllib.parse.urlencode`.
- `_render_nl_context(request_payload: dict, generated_session: dict | None) -> str` — template `f"Did an unscheduled {duration_min}min {sport} ({intensity}) at {locale}"`. Intensity word renders verbatim (underscore → space). Locale fallback chain matches `suggestion_view.html:24`. Drops `({intensity})` clause when intensity is blank.
- `_log_cardio_session(...)` — INSERT one `cardio_log` row with `is_ad_hoc TRUE` literal in SQL (not parameterized; safer in case psycopg2's DEFAULT-application differs from explicit bound). Notes column concatenates `coaching_intent` + `session_notes` with `\n\n` separator; both blank → notes=None. Caller owns the transaction.
- `_log_strength_session(...)` — one row per `StrengthExercise`; returns the first row's id as the canonical `logged_into_id` pointer (downstream queries find all rows in the set via `ad_hoc_suggestion_id`). `reps_per_set: int` → `target_reps`; `reps_per_set: str` → `target_reps=None` + `"Reps: 6-8"` in notes column. Load + tempo + instructions composed into notes with `Load:` / `Tempo:` prefixes; `instructions` appended raw at the end. Caller owns transaction.
- `_mark_logged(db, suggestion_id, user_id, *, logged_into_table, logged_into_id)` — `UPDATE ad_hoc_workout_suggestions SET status = 'logged', logged_into_table = ?, logged_into_id = ? WHERE id = ? AND user_id = ?`. Scoped to user_id defensively. Status literal `'logged'` in SQL (not parameterized) — single allowed value at this entry point.
- `_record_t1_dismiss(db, user_id, suggestion_id)` — `INSERT INTO t1_hook_telemetry (user_id, suggestion_id) VALUES (?, ?)`. `dismissed_at` + `created_at` default to NOW() via the table DDL. Caller commits.
- `view_suggestion(suggestion_id)` extended: reads `request.args.get('just_logged') == '1'`; computes `t1_hook_nl_context = _render_nl_context(...)` server-side every render (deterministic — same input always renders the same string); computes `t1_hook_refresh_query = urlencode({nl_context: ..., tier: 'T1'})` so the modal's [Yes — refresh] anchor can interpolate it directly into the href. Adds 3 new template kwargs.
- POST `/workouts/suggestions/<id>/log` → `log_suggestion(suggestion_id)`: 4 defensive gates (404 on miss, `flash` + redirect on status≠suggested, `flash` + redirect on generated_session=None, `flash` + redirect on unknown session.kind). Calls `_log_cardio_session` for kind='cardio', `_log_strength_session` for kind='strength'. On (ValueError, RuntimeError) calls `db.rollback()` + flashes the error. On success calls `_mark_logged` + `db.commit()` + 302s to `view_suggestion + '?just_logged=1'`.
- POST `/workouts/suggestions/<id>/dismiss_t1_hook` → `dismiss_t1_hook(suggestion_id)`: 404 on miss; INSERT `t1_hook_telemetry` row + commit + 302 to suggestion view.
- `_get_suggestion(db, user_id, suggestion_id)` extended: SELECT now includes `logged_into_table` + `logged_into_id`; result dict carries them. Uses `row.get()` (via `hasattr(row, 'get')` guard) so existing `_FakeConn` fixtures that don't queue the new keys still hydrate without `KeyError`.

### 3.3 `templates/workouts/suggestion_view.html` — log button + modal + auto-open script

- Strike: `<p class="text-muted small mt-2">[Log this workout] coming in a follow-on (paired with the D-64 T1 plan-check hook).</p>` (predecessor placeholder).
- Add `[Log this workout]` form (`btn-primary`) leftmost in the `d-flex gap-2 mt-3` row on `status='suggested'`. Adjacent to existing [Regenerate] + [Discard] forms.
- Add `{% elif suggestion.status == 'logged' %}` branch rendering `<p class="text-success">Logged ✓ — Saved to your {cardio,training} log.</p>` (table-aware copy).
- Add `{% if suggestion.status == 'logged' %} … {% endif %}` block at end of `content` block containing:
  - `#t1HookModal` Bootstrap modal (centered, fade) with title `Logged ✓`, body `Want to refresh the next 2 days based on this session?` + auto-fill preview, footer with `<form>` POSTing to `dismiss_t1_hook` + anchor `<a>` linking to `/plans/v2/refresh?{t1_hook_refresh_query}` styled as `btn-primary`.
  - `{% if just_logged %}<script>(function() { var modalEl = document.getElementById('t1HookModal'); if (modalEl && window.bootstrap && window.bootstrap.Modal) { window.bootstrap.Modal.getOrCreateInstance(modalEl).show(); } })();</script>{% endif %}` — 3-line inline JS that auto-opens the modal exactly once (refresh drops `?just_logged=1`).

### 3.4 `routes/plan_refresh.py` — `_resolve_prefill` helper + GET threads kwargs

- New `_resolve_prefill(args) -> tuple[str, str | None]` between `_athlete_active_injury_summary` and `_parse_tier`. Reads `args.get('nl_context')` (defaulted ''), truncates at `_NL_TEXT_SOFT_CAP_CHARS=500`. Reads `args.get('tier')`, strips + uppercases, validates against `VALID_TIERS=('T1','T2','T3')`. Unknown/blank → None.
- `refresh()` GET branch: comment block explains D-63 §3.5 auto-fill; calls `_resolve_prefill(request.args)` + threads `prefill_nl_context` + `prefill_tier` kwargs to `render_template`.

### 3.5 `templates/plans/v2/refresh.html` — prefill rendering

- Textarea body: `<textarea ...>{{ prefill_nl_context or '' }}</textarea>`. Jinja outputs '' when None/empty.
- 3 tier buttons: conditional class `{% if prefill_tier is none or prefill_tier == 'TX' %}btn-primary{% else %}btn-outline-primary{% endif %}`. Default behavior (no prefill_tier) preserved — all 3 buttons render as `btn-primary` (filled). With prefill_tier='T1' only T1 renders filled; T2 + T3 outline.

### 3.6 `tests/test_routes_ad_hoc_workouts.py` — +22 tests in 6 new classes + 1 imports extension

- Imports: 6 new helpers + 1 stdlib `from datetime import date`.
- `TestRenderNlContext` (5): test_happy_path_with_locale_name / test_race_pace_intensity_renders_with_space / test_falls_back_to_locale_id_then_locale_slug / test_falls_back_to_request_locale_slug_when_session_none / test_drops_intensity_clause_when_blank.
- `TestLogCardioSession` (5): test_inserts_row_with_is_ad_hoc_true_and_returns_id (full param shape check) / test_notes_concatenates_intent_and_session_notes / test_notes_none_when_both_blank / test_raises_when_no_returning_row / test_does_not_commit.
- `TestLogStrengthSession` (5): test_inserts_one_row_per_exercise_and_returns_first_id / test_int_reps_persisted_str_reps_in_notes / test_raises_when_no_strength_exercises / test_raises_when_returning_row_missing_mid_insert / test_does_not_commit.
- `TestMarkLogged` (2): test_updates_status_and_pointers / test_training_log_table_value_accepted.
- `TestRecordT1Dismiss` (2): test_inserts_row_with_user_and_suggestion / test_each_call_inserts_a_new_row.
- `TestGetSuggestionLoggedFields` (3): test_returns_logged_into_table_and_id_when_present / test_logged_into_fields_none_when_status_suggested / test_select_query_includes_logged_columns.

### 3.7 `tests/test_routes_plan_refresh.py` — +7 tests in 1 new class + 1 imports extension

- Imports: 1 new helper `_resolve_prefill`.
- `TestResolvePrefill` (7): test_returns_empty_when_no_args / test_nl_context_passes_through / test_valid_tier_uppercased / test_unknown_tier_collapses_to_none / test_blank_tier_collapses_to_none / test_nl_context_truncated_at_soft_cap (uses `_NL_TEXT_SOFT_CAP_CHARS` import) / test_t1_hook_full_pattern (e2e: nl_context + tier=T1).

---

## 4. Code / tests

**Tests 1334 → 1363 (+29 net new across 2 extended test files):**

- `tests/test_routes_ad_hoc_workouts.py` +22 (51 total): 6 new test classes (TestRenderNlContext 5 + TestLogCardioSession 5 + TestLogStrengthSession 5 + TestMarkLogged 2 + TestRecordT1Dismiss 2 + TestGetSuggestionLoggedFields 3)
- `tests/test_routes_plan_refresh.py` +7 (43 total): TestResolvePrefill (7 tests)

**Container-runnable subset 667 → 696 in ~1.7s.**

Run reproducer for the container-runnable subset (matches the predecessor handoff §4 invocation):

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
# 696 passed, 12 skipped in 1.72s
```

**No-regression confirmation:** All 667 pre-existing container-subset tests pass unchanged. Touched modules: `init_db.py` (migration block append), `routes/ad_hoc_workouts.py` (3 new helpers + 2 new routes + `_get_suggestion` extension + `view_suggestion` extension), `routes/plan_refresh.py` (1 new helper + GET prefill threading), 2 templates, 2 test files. No edits to `layer4/`, repos, schema beyond the migration block, or specs.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 9+ predecessor handoffs §4). Full `pytest tests/` invocation fails collection on `tests/test_layer1_builder.py`; container-runnable subset above is the canonical green count.

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass.

**Step 1: `init_db.py` migration spot-check on Neon.** `\d cardio_log` shows new columns `is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE` + `ad_hoc_request_payload JSONB` + `ad_hoc_suggestion_id BIGINT` (FK to `ad_hoc_workout_suggestions(id)`) + partial index `cardio_log_ad_hoc_idx ON (user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE`. Mirror on `\d training_log`. `\d plan_refresh_log` shows new `triggered_by_ad_hoc_id BIGINT` column (FK to `ad_hoc_workout_suggestions(id)`). `\d t1_hook_telemetry` exists with BIGSERIAL PK + user_id FK + suggestion_id FK + `dismissed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` + `created_at` + index on `(user_id, dismissed_at DESC)`.

**Step 2: Log-this cardio happy path.** Andy (already has Andy's PGE 2026 target race row + at least one prior plan_versions row from the plan-create walkthrough) navigates to `/workouts/build`, picks sport=Running + duration=60 + intensity=hard + locale=home, clicks Generate workout; lands on `/workouts/suggestions/<id>` rendering the cardio session with [Log this workout] (primary) + [Regenerate] + [Discard] buttons. Click [Log this workout]. Confirm: (a) `cardio_log` gets one new row with `is_ad_hoc=TRUE` + `ad_hoc_suggestion_id=<id>` + `ad_hoc_request_payload` matches the SingleSessionRequest JSON + `date=today` + `activity='Running'` + `duration_min=60.0` + `notes` = coaching_intent + session_notes concatenated; (b) `ad_hoc_workout_suggestions.status` flips to `'logged'` + `logged_into_table='cardio_log'` + `logged_into_id=<cardio_log_id>`; (c) URL is `/workouts/suggestions/<id>?just_logged=1`; (d) the page renders the `Logged ✓` text below the workout card AND a Bootstrap modal auto-opens with title `Logged ✓` + body `Want to refresh the next 2 days based on this session?` + preview text `We'll pre-fill: "Did an unscheduled 60min Running (hard) at home" (editable on the next screen).` + buttons `[No, thanks]` (outline-secondary) + `[Yes — refresh]` (primary, anchor to `/plans/v2/refresh?nl_context=...&tier=T1`); (e) refresh the page (drop `?just_logged=1`) — modal does NOT re-open.

**Step 3: T1 hook [Yes — refresh] click-through.** From the modal in Step 2, click [Yes — refresh]. Confirm: (a) URL is `/plans/v2/refresh?nl_context=Did+an+unscheduled+60min+Running+%28hard%29+at+home&tier=T1`; (b) refresh.html renders with textarea body populated with `Did an unscheduled 60min Running (hard) at home`; (c) the `Refresh next 2 days` button renders `btn-primary` (filled); (d) the other two tier buttons render `btn-outline-primary` (outlined); (e) Andy can edit the textarea and pick a different tier if desired; (f) clicking [Refresh next 2 days] submits the form normally — POST goes through the existing refresh handler with `submit_t1=1` + `nl_context=<edited or unchanged>`; (g) the resulting T1 refresh fires the NL parser against the auto-filled / edited text + lands a new `plan_versions` row + `plan_refresh_log` row.

**Step 4: T1 hook [No, thanks] dismissal.** Repeat Step 2 with a fresh generate. When the modal auto-opens, click [No, thanks]. Confirm: (a) URL redirects to `/workouts/suggestions/<id>` (no query param); (b) modal does NOT re-open; (c) `t1_hook_telemetry` row lands with `user_id=<andy>` + `suggestion_id=<id>` + `dismissed_at=NOW()`; (d) clicking [No, thanks] a second time inserts a second telemetry row (per-event semantics).

**Step 5: Log-this strength path.** Build a strength session (sport=Strength or any framework_sport that routes to kind=strength), click [Log this workout]. Confirm: (a) `training_log` gets one row per strength exercise (e.g., 5 exercises → 5 rows) all tagged with `is_ad_hoc=TRUE` + `ad_hoc_suggestion_id=<id>`; (b) `logged_into_table='training_log'` + `logged_into_id=<first row id>`; (c) per-row `notes` contains `Load:` / `Tempo:` / `Reps:` lines + `instructions`; (d) the `Logged ✓` text below the card reads `Saved to your training log.`; (e) modal flow + T1 hook redirect identical to cardio path.

**Step 6: Defensive cases.** (a) Re-click [Log this workout] on an already-logged suggestion — flash warning "This workout has already been logged, discarded, or regenerated." + no double-insert. (b) Cross-user URL probe `GET /workouts/suggestions/<other_users_id>?just_logged=1` returns 404 + no modal renders. (c) POST `/workouts/suggestions/<other_users_id>/log` returns 404 + no row inserted.

Captured in `CARRY_FORWARD.md` manual walkthrough section (6 new scenarios under D-73 Phase 5.2 log-this + T1 hook).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**NL parser frequency caps per D-64 §8 (deferred via D4 in the D-64 runtime session).** With the T1 hook now driving real T1 refresh traffic from the post-log modal, frequency caps move from anti-cohort discipline into near-load-bearing. T1 ≤3/24h, T2 ≤1/48h, T3 ≤1/7d server-side count against `plan_refresh_log`; modal-confirm UI when exceeded; new `cap_overridden BOOLEAN` column on `plan_refresh_log`. ~3-4 files. `/plan` gate per Triggers #3 (column add on existing telemetry table) + #5 (cap-exceeded UX — modal vs blocking gate vs soft warning).

### 6.2 Alternative pivots

- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** (~1-2 files; doc-sweep nit from form-refresh C investigation. Add `_evict_layer2c_on_equipment_change(db, uid)` mirror of the terrain helper + wire to both legacy + shared edit branches on actual equipment-set change. No `/plan` triggers.)
- **Plan refresh: triggered_by_ad_hoc_id wiring** (~1-2 files; D-63 §5.4 ships the column this session but `routes/plan_refresh.py:_write_refresh_log` doesn't yet populate it. When the T1 hook redirects from a log-this dismissal-to-Yes flow, the refresh log row should carry `triggered_by_ad_hoc_id=<suggestion_id>` for downstream attribution. Threading point: pass `triggered_by_ad_hoc_id` through the query-param prefill OR detect via `nl_context` heuristic. Trigger #5: per-flow plumbing approach.)
- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** (~5-6 files; need ~20-30 hand-labeled fixtures + a Haiku-vs-Sonnet agreement comparison harness.)
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1+#3+#5).
- **Layer 3A + 3B caching policy at orchestrator level** — all 4 entry points call `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` uncached. ~4-6 files.
- **Manual §5.0 walkthrough** of D-64 + D-63 + plan_create + dashboard CTAs + log-this/T1 hook E2E on Neon (real-LLM ~$1.50 per pass across the 3 routes + T1 hook follow-on; T1 hook surface itself is no-cost beyond what the refresh re-run costs).
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_LogThis_T1Hook_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | T1 hook UX shape = auto-fired Bootstrap modal | Andy at AskUserQuestion gate | Picked over inline-banner / direct-redirect / dashboard-flash alternatives. Modal kept JS-light: pre-rendered conditional markup + 3-line `bootstrap.Modal.getOrCreateInstance().show()` on `?just_logged=1`. No AJAX adapter; log POST is a plain form submit + 302. |
| **D2** | `t1_hook_dismissed` telemetry = NEW `t1_hook_telemetry` table | Andy | Picked over columns-on-suggestions / skip-telemetry. Extensible — future hook event types (partial-dismiss, deferred-refresh) extend without schema churn on `ad_hoc_workout_suggestions`. Cost: 1 new table + 1 index. |
| **D4** | NL context auto-fill template = verbatim intensity word | Andy | Template `f"Did an unscheduled {duration_min}min {sport} ({intensity}) at {locale}"`. Intensity renders verbatim from request (`easy`/`moderate`/`hard`/`race pace`; underscore→space). Picked over HR-zone translation (would need static intensity→zone map that doesn't reflect athlete-specific zones) + skip-intensity (loses parser signal). Locale fallback chain matches `suggestion_view.html:24`. |
| **D5** | Refresh form prefill = query-param | Andy | `/plans/v2/refresh?nl_context=<encoded>&tier=T1`. Stateless; no session/flash coupling; preserves editability per D-63 §3.5 "athlete sees the D-64 modal with NL pre-filled (editable)". |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` migration adds 3 columns + 1 partial index to `cardio_log` | ✅ `grep "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS is_ad_hoc" init_db.py` + `grep "cardio_log_ad_hoc_idx" init_db.py` |
| `init_db.py` migration adds 3 columns + 1 partial index to `training_log` | ✅ `grep "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS is_ad_hoc" init_db.py` + `grep "training_log_ad_hoc_idx" init_db.py` |
| `init_db.py` adds `triggered_by_ad_hoc_id` to `plan_refresh_log` | ✅ `grep "triggered_by_ad_hoc_id" init_db.py` |
| `init_db.py` creates `t1_hook_telemetry` table + index | ✅ `grep "CREATE TABLE IF NOT EXISTS t1_hook_telemetry" init_db.py` + `grep "t1_hook_telemetry_user_dismissed_idx" init_db.py` |
| `routes/ad_hoc_workouts.py` defines `_render_nl_context` | ✅ `grep "def _render_nl_context" routes/ad_hoc_workouts.py` |
| `routes/ad_hoc_workouts.py` defines `_log_cardio_session` + `_log_strength_session` + `_mark_logged` + `_record_t1_dismiss` | ✅ grep |
| `routes/ad_hoc_workouts.py` defines POST `/workouts/suggestions/<id>/log` route | ✅ `grep "@bp.route('/suggestions/<int:suggestion_id>/log'" routes/ad_hoc_workouts.py` |
| `routes/ad_hoc_workouts.py` defines POST `/workouts/suggestions/<id>/dismiss_t1_hook` route | ✅ `grep "/dismiss_t1_hook" routes/ad_hoc_workouts.py` |
| `routes/ad_hoc_workouts.py` `_get_suggestion` SELECT includes `logged_into_table`/`id` | ✅ grep |
| `routes/ad_hoc_workouts.py` `view_suggestion` threads `just_logged` + `t1_hook_nl_context` + `t1_hook_refresh_query` | ✅ grep |
| `templates/workouts/suggestion_view.html` has `[Log this workout]` button on status='suggested' | ✅ `grep "ad_hoc_workouts.log_suggestion" templates/workouts/suggestion_view.html` |
| `templates/workouts/suggestion_view.html` has the `#t1HookModal` modal block | ✅ `grep "t1HookModal" templates/workouts/suggestion_view.html` |
| `templates/workouts/suggestion_view.html` `{% if just_logged %}` auto-open script | ✅ `grep "just_logged" templates/workouts/suggestion_view.html` |
| `routes/plan_refresh.py` defines `_resolve_prefill` | ✅ `grep "def _resolve_prefill" routes/plan_refresh.py` |
| `templates/plans/v2/refresh.html` textarea renders `prefill_nl_context` | ✅ `grep "prefill_nl_context" templates/plans/v2/refresh.html` |
| `templates/plans/v2/refresh.html` tier buttons render `prefill_tier`-aware class | ✅ `grep "prefill_tier" templates/plans/v2/refresh.html` |
| `tests/test_routes_ad_hoc_workouts.py` has `TestRenderNlContext` + `TestLogCardioSession` + `TestLogStrengthSession` + `TestMarkLogged` + `TestRecordT1Dismiss` + `TestGetSuggestionLoggedFields` classes | ✅ grep all 6 |
| `tests/test_routes_plan_refresh.py` has `TestResolvePrefill` class | ✅ grep |
| Container-runnable subset 667 → 696 (+29 net new) | ✅ pytest run returns "696 passed, 12 skipped in ~1.7s" |
| Tests 1334 → 1363 (+29 net new across 2 extended test files) | ✅ Counted via diff: +22 (ad_hoc_workouts) + 7 (plan_refresh) = +29 |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 LogThis+T1Hook handoff | ✅ |
| `CURRENT_STATE.md` tests count flipped to 1363 + 16 skipped | ✅ |
| `CURRENT_STATE.md` Layer 4 status row updated to reflect log-this+T1 hook landing | ✅ |
| `CARRY_FORWARD.md` log-this + T1 hook entry struck (✅ Shipped) + 6 new manual §5.0 walkthrough scenarios added | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.LogThis-T1Hook` → ✅ Shipped 2026-05-21 | ✅ grep |
| Branch renamed to `claude/log-this-t1-hook-pcIhF` at session start | ✅ `git branch --show-current` |

---

## 9. Files shipped this session

**Substantive (7 files; ceiling break ratified at AskUserQuestion gate; precedented by 5.1.A=8 / 5.1.C=8 / 5.2.Caller-D63+PlanCreate=9 / 5.2.Caller-D64=8):**

1. `init_db.py` — 4 new migration blocks appended to `_PG_MIGRATIONS` (cardio_log + training_log column extensions + plan_refresh_log column + NEW t1_hook_telemetry table).
2. `routes/ad_hoc_workouts.py` — 6 new helpers + 2 new routes + `_get_suggestion` / `view_suggestion` extensions; module docstring rewritten.
3. `templates/workouts/suggestion_view.html` — [Log this workout] button + `status='logged'` text block + `#t1HookModal` modal + 3-line auto-open script.
4. `routes/plan_refresh.py` — `_resolve_prefill` helper + GET threads prefill kwargs.
5. `templates/plans/v2/refresh.html` — textarea prefill rendering + tier-button prefill highlighting.
6. `tests/test_routes_ad_hoc_workouts.py` — +22 tests in 6 new classes (TestRenderNlContext / TestLogCardioSession / TestLogStrengthSession / TestMarkLogged / TestRecordT1Dismiss / TestGetSuggestionLoggedFields).
7. `tests/test_routes_plan_refresh.py` — +7 tests in 1 new class (TestResolvePrefill).

**Bookkeeping (4 files):**

8. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + Layer 4 status row + tests count.
9. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — log-this + T1 hook entry struck + 6 new manual §5.0 walkthrough scenarios.
10. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.LogThis-T1Hook`.
11. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_LogThis_T1Hook_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- "Log-this slice + D-63 T1 plan-check hook (~5-7 files; `/plan` gate per Triggers #1+#3+#5)" entry → ✅ Shipped 2026-05-21 (`claude/log-this-t1-hook-pcIhF`).
- 6 new manual §5.0 walkthrough scenarios added under D-73 Phase 5.2 log-this + T1 hook (init_db migration spot-check + cardio happy path + T1 hook [Yes — refresh] click-through + T1 hook [No, thanks] dismissal + strength path + defensive cases).
- New doc-sweep nit: `routes/plan_refresh.py:_write_refresh_log` does NOT yet populate `triggered_by_ad_hoc_id`; the column ships but its caller doesn't thread the FK. Forward-pointer to next session that touches plan_refresh.

**Phase 5.2 caller-side v2 surfacing arc + log-this slice complete; the post-log T1 plan-check hook now closes the D-63 → D-64 cross-route flow with auto-filled NL context. The next caller-side surface work is the NL parser frequency caps per D-64 §8 (now near-load-bearing with real T1 traffic from the modal) OR the `triggered_by_ad_hoc_id` plumbing wiring at the `_write_refresh_log` seam.**

---

**End of handoff.**
