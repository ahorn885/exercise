# D-73 Phase 5.2 Caller-Side Routes — D-63 + plan-create Flask Routes — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side routes — first end-to-end Flask wiring of the Layer 4 orchestrator surface. Picks the architect-recommended batched (a)+(b) arc per the substrate handoff §6.1: D-63 on-demand workout route + plan-create caller-side route together, both consuming the same-day-prior `plan_sessions_repo.py` substrate. **9 substantive files** (ceiling break ratified at AskUserQuestion gate per Trigger #1 form copy + Trigger #3 new `ad_hoc_workout_suggestions` table + Trigger #5 route shape; precedented by Phase 5.1.A=8 + 5.1.C=8).
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_CallerSide_PlanSessions_Substrate_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/implement-plan-sessions-orchestrator-JN0sH` (harness-assigned; matches session scope — the substrate landed yesterday on a different branch, today's arc composes routes atop it).
**Status:** 9 substantive files (ceiling break ratified); container-runnable subset 523 → 568 (+45 net new route tests); production count 1190 → 1235 (+45); 4 SDK smoke tests still skip cleanly. All prior orchestrator + substrate + race_events + locales + onboarding tests pass unchanged (purely additive).

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor (caller-side substrate) handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` has `plan_sessions` table migration | `grep -n "CREATE TABLE IF NOT EXISTS plan_sessions" init_db.py` | ✅ line 1566 |
| `init_db.py` has 2 plan_sessions indexes | grep | ✅ both |
| `plan_sessions_repo.py` exists with 4 helpers | grep | ✅ 4 lines |
| `plan_sessions_repo.py` exports `_PRIOR_WINDOW_DAYS_BY_TIER` | grep | ✅ |
| `tests/test_plan_sessions_repo.py` has 5 classes + 22 tests | grep | ✅ |
| Container-runnable subset green at 523 | `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py tests/test_plan_sessions_repo.py` | ✅ 523 passed in 1.23s |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 caller-side substrate | grep | ✅ |
| `CARRY_FORWARD.md` "Caller-side persistence substrate" entry struck | grep | ✅ |

`./scripts/verify-handoff.sh` flagged 7 ❌ at session start — `routes/ad_hoc_workouts.py` + `routes/plan_create.py` + `routes/plan_refresh.py` + 3 templates + `aidstation-sources/prompts/NLParser_v1.md`. All 7 are pre-explained forward-pointers from the substrate handoff §1 reconciliation note (queued caller-side routes + NL parser body deferred per D-64 Decision #12).

**Reconciliation note:** Clean. No drift. This session closes 5 of the 7 forward-pointers (D-63 route + D-63 templates + plan-create route + plan-create templates land here). 2 remain — `routes/plan_refresh.py` + `prompts/NLParser_v1.md` — both queued for the D-64 caller-side arc, gated on a separate /plan Trigger #2 prompt-body design session.

---

## 2. Session narrative

Andy picked (a)+(b) batched at the AskUserQuestion gate over (a)-only D-63, (b)-only plan-create, or (c) D-64. Per CLAUDE.md Triggers #1 (user-facing form copy on 2 new routes) + #3 (new `ad_hoc_workout_suggestions` table) + #5 (route shape + atomic-transaction boundary + error-handling routing), the session entered the design gate before implementation.

Pre-implementation surface survey checked:

- `orchestrate_single_session_synthesize(db, user_id, request, suggestion_id, *, cache, today=None)` at `layer4/orchestrator.py:382` — caller supplies `suggestion_id: int`; v1 needs the `ad_hoc_workout_suggestions` table to allocate the id pre-orchestrate.
- `orchestrate_plan_create(db, user_id, *, plan_start_date, plan_version_id, cache, today=None)` at `layer4/orchestrator.py:589` — caller supplies `plan_start_date: date` + `plan_version_id: int`; `plan_versions` table already on disk per Layer 4 §7.11 migration; substrate `allocate_plan_version_row(...)` validates `created_via` + `pattern` + scope dates.
- `SingleSessionRequest` at `layer4/single_session.py:66` — `sport: str`, `duration_min: int Field(ge=30, le=360)`, `intensity: Literal["easy","moderate","hard","race_pace"]`, `locale_slug: str | None` XOR `quick_equipment: list[str]`, `notes_for_synthesizer: str | None`.
- D-63 §5.3 `ad_hoc_workout_suggestions` schema — 11 columns + 1 index; `generated_session` JSONB intentionally NULLable so the row can be allocated pre-orchestrate (allocate-then-fill pattern; the suggestion_id flows into the orchestrator's `suggestion_id` kwarg + appears in `payload.suggestion_id` per `Layer4Payload._check_mode_invariants` line 580).
- `Layer4ShapeInfeasibleError` spec'd at Layer 4 §3.5 + §10.2 but **NOT yet implemented in code** — route catches `OrchestrationError` + `Layer4InputError` + `Layer4OutputError` only.
- `routes/race_events.py` precedent: Blueprint with `url_prefix`, `current_user_id()` from `routes.auth`, `get_db()` per-request connection, `flash() + redirect()` for error UX, helper-level pytest via `_FakeConn` (NOT Flask `test_client()` — end-to-end route walkthrough deferred to §5.0 per the existing module precedent).
- `Layer4Cache(PostgresCacheBackend(db_conn_factory))` — production cache wiring; `db_conn_factory` is a `Callable[[], db]` returning the per-request connection. Production routes pass `lambda: get_db()`.

14 D-decisions surfaced + ratified at the AskUserQuestion gate before implementation:

- **D1: D-63 schema scope = `ad_hoc_workout_suggestions` table only.** `cardio_log`/`training_log` `is_ad_hoc` extensions (D-63 §5.1/§5.2) defer to the log-this slice (paired with D-64 caller-side T1 hook). v1 ships generate + view + discard + regenerate; logging-it lands later.
- **D2: URL prefixes `/workouts/*` (D-63) + `/plans/v2/*` (plan-create).** Avoid v1 `routes/plans.py` legacy collision; `v2` prefix flags the new pipeline cleanly.
- **D3: Sport vocabulary = broad list** `SELECT DISTINCT framework_sport FROM layer0.sports WHERE superseded_at IS NULL ORDER BY framework_sport`. Athlete-filtered vocabulary (primary_sport + cross-training options) is a v2 follow-on.
- **D4: Quick-equipment "Somewhere else" path defer** for v1. Force locale-only requests. Per D-63 §3.4 the path requires a sport-conditional checkbox grid + free-text "other" line; out of scope this slice. Form-refresh follow-on.
- **D5: Caller owns transaction per substrate D-64 §6.2.** Route handler manages atomic write: allocate → orchestrate → persist → `db.commit()`. On any raised exception in the chain no commit fires; the connection's auto-rollback keeps half-allocated rows off the table.
- **D6: `PostgresCacheBackend(lambda: get_db())` cache factory in production.** Routes wire real cache from day 1; repeat workouts/plans cache-hit free.
- **D7: No target-race picker on plan-create form.** Orchestrator already calls `load_target_race_event_payload(db, user_id)` which reads the athlete's `is_target_event=TRUE` row from `race_events`. Form only asks for `plan_start_date`. Race association lives on `/profile/race-events`.
- **D8: `notes=None` on `allocate_plan_version_row` for v1.** Population from `payload.phase_structure.phases[*].phase_synthesis_notes` requires a new `update_plan_version_notes` repo helper that doesn't exist; defer to a follow-on.
- **D9: Inline 4-helper layout in `routes/ad_hoc_workouts.py`** (no new `ad_hoc_workouts_repo.py`). The table has a narrow surface + single caller; substrate handoff's repo-extract precedent applies when ≥2 callers exist. Extract when a 2nd caller appears.
- **D10: Result-view actions on D-63 = `[Regenerate]` + `[Discard]` only.** `[Log this workout]` deferred — pairs with cardio_log/training_log `is_ad_hoc` extensions + D-64 T1 hook.
- **D11: 9-file ceiling break ratified** (precedented by 5.1.A=8 + 5.1.C=8). Substrate handoff §6.1 explicitly recommended batching (a)+(b) ("~6-8 files batched"). Actual file count: 1 init_db migration + 2 route modules + 4 templates + 2 test files = 9 substantive (5 D-63 + 4 plan-create).
- **D12: Test density = helper-level pytest via `_FakeConn`.** End-to-end Flask `test_client()` walkthrough deferred to §5.0 manual verification per `routes/race_events.py` + `routes/onboarding.py` + `routes/locales.py` precedent. Each route's helpers fully covered; the route flow itself is verified at §5.0.
- **D13: Batch (a)+(b)** per substrate §6.1 recommendation over split. Single-session ceiling break ratified.
- **D14: Broad sport vocabulary** per D3 — Andy picked over per-athlete filtering.

Implementation flow:

1. **Schema migration** — Added to `init_db.py` `_PG_MIGRATIONS` (anchored after the plan_sessions migrations). Single `CREATE TABLE IF NOT EXISTS ad_hoc_workout_suggestions (...)` + 1 index on `(user_id, status, requested_at DESC)`. `generated_session JSONB` is nullable so the row can be allocated pre-orchestrate (substrate D5 caller-owns-transaction pattern needs the id BEFORE the orchestrator fires; the suggestion_id flows into the orchestrator kwarg + `Layer4Payload.suggestion_id` per `payload.py:580`).

2. **D-63 route module** — NEW `routes/ad_hoc_workouts.py` (~330 LOC) with Blueprint `/workouts/*` + 9 inline helpers (`_athlete_sport_choices` broad framework_sport list from `layer0.sports`, `_allocate_suggestion` RETURNING id, `_persist_generated_session` UPDATE generated_session JSONB, `_get_suggestion` SELECT-with-user_id-scoping + JSONB hydration, `_mark_status` discarded/regenerated state-machine flips, `_decode_jsonb` dual-path psycopg2/SQLite-shim, `_build_layer4_cache` PostgresCacheBackend factory, `_parse_request_form` SingleSessionRequest factory + ValidationError → flash translation, `_orchestration_error_message` 4-code translation table). 4 routes: `GET /workouts/build` renders the form; `POST /workouts/build` allocates → orchestrates → persists → commits; `GET /workouts/suggestions/<id>` renders the result card; `POST /workouts/suggestions/<id>/discard` flips status; `POST /workouts/suggestions/<id>/regenerate` re-orchestrates + links via `regenerated_into_id`.

3. **D-63 templates** — NEW `templates/workouts/build_form.html` (Bootstrap form: sport dropdown + duration 30-360/15 + intensity 4-value dropdown + locale dropdown + optional notes textarea + submit) + NEW `templates/workouts/suggestion_view.html` (renders the generated `PlanSession` from `Layer4Payload.sessions[0]`: header with sport+duration+intensity badge + status badge for non-suggested + coaching_intent alert + cardio_blocks loop OR strength_exercises list + session_notes card + [Regenerate]/[Discard] action buttons on suggested rows + supersession link when regenerated).

4. **Plan-create route module** — NEW `routes/plan_create.py` (~190 LOC) with Blueprint `/plans/v2/*` + 5 inline helpers (`_parse_plan_start_date` ISO-format guard with strip-whitespace, `_load_plan_version` SELECT-with-user_id-scoping, `_build_layer4_cache` PostgresCacheBackend factory, `_resolve_plan_scope_end_date` race-date-when-future-target-else-24-week-fallback per Layer 3B §6.6 no-event default, `_orchestration_error_message`). 2 routes: `GET/POST /plans/v2/new` (form + atomic allocate+orchestrate+persist+commit); `GET /plans/v2/<plan_version_id>` (plan view with sessions grouped by date).

5. **Plan-create templates** — NEW `templates/plan_create/new_form.html` (date input + read-only target-race summary block OR "No target race set" alert + "Create plan" button) + NEW `templates/plan_create/view.html` (header with Pattern badge + created_via badge + scope dates + session count + per-date list with discipline + duration + intensity badge + coaching_intent + session_notes).

6. **Tests** — NEW `tests/test_routes_ad_hoc_workouts.py` (~330 LOC; 29 tests across 8 classes): `TestAthleteSportChoices` 3 / `TestAllocateSuggestion` 3 / `TestPersistGeneratedSession` 1 / `TestGetSuggestion` 4 / `TestMarkStatus` 3 / `TestDecodeJsonb` 5 / `TestParseRequestForm` 8 / `TestOrchestrationErrorMessage` 2. NEW `tests/test_routes_plan_create.py` (~190 LOC; 16 tests across 4 classes): `TestParsePlanStartDate` 6 / `TestLoadPlanVersion` 3 / `TestResolvePlanScopeEndDate` 5 / `TestOrchestrationErrorMessage` 2. `_FakeConn` / `_FakeCursor` / `_FakeRow` fixtures copied from the substrate test precedent.

7. **Blueprint registration** — `app.py` adds 2 import lines + 2 `register_blueprint` calls (bookkeeping; doesn't count against the ceiling).

8. **Test suite** — Container-runnable subset 523 → 568 passing in ~1.0s. No regressions on Layer 4 orchestrator / repo / race_events / locales / onboarding / cache surfaces.

9. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count (1190 → 1235) + current-focus arc (refocused on D-64 caller-side as the remaining unblocked surface); `CARRY_FORWARD.md` Phase 5.2 follow-ons section: D-63 + plan-create entries struck (✅) + new "Log-this slice + D-63 T1 plan-check hook" entry + new "Dashboard CTAs" follow-on + 3 new §5.0 walkthrough scenarios; `Upstream_Implementation_Plan_v1.md` §4 new row `5.2.Caller-D63+PlanCreate`; this closing handoff.

No additional `/plan-mode` triggers fired during implementation past the initial gate.

---

## 3. File-by-file edits

### 3.1 `init_db.py` (MODIFIED, +~30 LOC net)

- Added to `_PG_MIGRATIONS` list (anchored after the `plan_sessions_user_version_idx` migration, before `_CLOTHING_SEEDS`):
  - `CREATE TABLE IF NOT EXISTS ad_hoc_workout_suggestions (...)` — BIGSERIAL PK + user_id INTEGER FK + requested_at TIMESTAMPTZ DEFAULT NOW() + request_payload JSONB NOT NULL + generated_session JSONB (nullable until orchestrate succeeds; allocate-then-fill substrate D5 pattern) + status TEXT NOT NULL DEFAULT 'suggested' CHECK in (suggested, logged, discarded, regenerated) + logged_into_table TEXT + logged_into_id BIGINT + discarded_at TIMESTAMPTZ + regenerated_into_id BIGINT self-FK + token_cost_estimate INTEGER + created_at TIMESTAMPTZ DEFAULT NOW().
  - `CREATE INDEX IF NOT EXISTS ad_hoc_workout_suggestions_user_status_idx ON ad_hoc_workout_suggestions (user_id, status, requested_at DESC)`.
- Inline comment block documents the schema rationale: D-63 §5.3 reference + allocate-then-fill nullable `generated_session` rationale + status lifecycle + logged_into_* columns reserved for log-this slice + regenerated_into_id self-FK telemetry chain.

### 3.2 NEW `routes/ad_hoc_workouts.py` (~330 LOC)

- Module docstring documents the atomic-transaction contract (caller owns commit per D-64 §6.2) + D-63 §3.4 quick-equipment deferral + D-63 T1 hook deferral.
- Module-level constants: `VALID_INTENSITIES = ('easy', 'moderate', 'hard', 'race_pace')`.
- 7 inline helpers (see §2 narrative step 2).
- 4 routes: `build_workout` (GET form, POST orchestrate), `view_suggestion`, `discard_suggestion`, `regenerate_suggestion`.
- Cross-user-defense: `_get_suggestion(db, user_id, suggestion_id)` scopes the SELECT WHERE clause to `user_id = ?` so a crafted GET against another user's suggestion_id returns None (route 404s).
- `_orchestration_error_message` translation table covers 4 codes (`request_sport_unavailable`, `locale_unknown`, `etl_version_set_undiscoverable`, `framework_sport_missing`) + generic fallback for unknown codes.

### 3.3 NEW `templates/workouts/build_form.html`

- Bootstrap form with sport dropdown (broad framework_sport list per D3) + duration number input (min=30 max=360 step=15 default=60) + intensity dropdown (4-value VALID_INTENSITIES) + locale dropdown (from `athlete_locale_choices`) + optional notes textarea + submit.
- "Build a workout right now — sport, duration, intensity, location" descriptive paragraph; coaching voice per CLAUDE.md "Coaching voice" — direct, no platitudes.
- "Somewhere else" path defer documented inline: "Equipment derives from the location. 'Somewhere else' (quick-equipment) coming in a follow-on."

### 3.4 NEW `templates/workouts/suggestion_view.html`

- Renders the generated `PlanSession` from `suggestion.generated_session`. Header with sport + duration + intensity badge + (non-suggested) status badge.
- `coaching_intent` rendered in an `.alert.alert-light` block.
- Conditional rendering: `kind == 'cardio'` loops `cardio_blocks` (block_type + duration_min + description + HR target); `kind == 'strength'` lists `strength_exercises` (name × sets × reps + load_kg + notes).
- `session_notes` rendered in a card body.
- Footer: when `status == 'suggested'`, surfaces `[Regenerate]` + `[Discard]` buttons in separate POST forms (CSRF tokens included); `[Log this workout]` defer-note rendered as `.text-muted small`; when `status == 'regenerated'` + `regenerated_into_id` set, link to the new suggestion view.

### 3.5 NEW `routes/plan_create.py` (~190 LOC)

- Module docstring documents the atomic-transaction contract + `notes=None` v1 deferral + no-target-race-picker rationale + `Layer4ShapeInfeasibleError` not-yet-implemented note.
- 4 inline helpers (see §2 narrative step 4).
- 2 routes: `new_plan` (GET form, POST orchestrate-and-persist), `view_plan` (GET plan view).
- `_resolve_plan_scope_end_date` picks `race_event.event_date` when future-target set, else `start_date + timedelta(days=168)` per Layer 3B §6.6 no-event default.
- Catches `OrchestrationError` + `Layer4InputError` + `Layer4OutputError`; renders via `flash()` + redirect-to-form.

### 3.6 NEW `templates/plan_create/new_form.html`

- Date input with `min=today_iso` + `value=today_iso` default + required.
- Read-only target-race summary card OR "No target race set" alert with link to `/profile/race-events`.
- "Pattern A synthesis — typically 3-4 phases ... takes ~30-60 seconds" expectation-setting copy.
- "Create plan" submit button.

### 3.7 NEW `templates/plan_create/view.html`

- Header: "Training plan" + Pattern badge + created_via badge.
- Scope dates + session count line.
- Per-date list (sorted): date header + day_of_week + each session rendered as a card with discipline + duration + intensity badge + time_of_day (if not 'unspecified') + coaching_intent + session_notes.
- Empty-sessions edge case handled with "No sessions persisted for this plan version." message.

### 3.8 NEW `tests/test_routes_ad_hoc_workouts.py` (~330 LOC)

- 29 tests across 8 classes (see §2 narrative step 6).
- `_FakeConn` / `_FakeCursor` / `_FakeRow` fixtures duplicated from substrate test precedent.

### 3.9 NEW `tests/test_routes_plan_create.py` (~190 LOC)

- 16 tests across 4 classes (see §2 narrative step 6).
- `_FakeRaceEvent` test double for `_resolve_plan_scope_end_date` exercises.

### 3.10 `app.py` (MODIFIED, +4 LOC bookkeeping)

- 2 import lines added after the existing `from routes.nudges import ...` block.
- 2 `register_blueprint` calls added after `app.register_blueprint(nudges_bp)`.
- Does NOT count against the 5-file ceiling — pure plumbing.

---

## 4. Code / tests

**Test count delta:** 1190 → 1235 in production count (+45 net new tests: 29 in NEW `tests/test_routes_ad_hoc_workouts.py` + 16 in NEW `tests/test_routes_plan_create.py`); 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Container-runnable subset:** 523 → 568 passing in ~1.0s.

Run reproducer:

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py \
                                tests/test_plan_sessions_repo.py \
                                tests/test_routes_ad_hoc_workouts.py \
                                tests/test_routes_plan_create.py
# 568 passed in ~1.0s
```

The +45 new tests:

- `tests/test_routes_ad_hoc_workouts.py::TestAthleteSportChoices::*` (3)
- `tests/test_routes_ad_hoc_workouts.py::TestAllocateSuggestion::*` (3)
- `tests/test_routes_ad_hoc_workouts.py::TestPersistGeneratedSession::*` (1)
- `tests/test_routes_ad_hoc_workouts.py::TestGetSuggestion::*` (4)
- `tests/test_routes_ad_hoc_workouts.py::TestMarkStatus::*` (3)
- `tests/test_routes_ad_hoc_workouts.py::TestDecodeJsonb::*` (5)
- `tests/test_routes_ad_hoc_workouts.py::TestParseRequestForm::*` (8)
- `tests/test_routes_ad_hoc_workouts.py::TestOrchestrationErrorMessage::*` (2)
- `tests/test_routes_plan_create.py::TestParsePlanStartDate::*` (6)
- `tests/test_routes_plan_create.py::TestLoadPlanVersion::*` (3)
- `tests/test_routes_plan_create.py::TestResolvePlanScopeEndDate::*` (5)
- `tests/test_routes_plan_create.py::TestOrchestrationErrorMessage::*` (2)

**No-regression confirmation:** all 50 pre-existing orchestrator tests + 21 locales + 27 race_events + 19 onboarding race_events + 22 plan_sessions_repo + 30+ each across layer4 context/payload/hashing/cache + 12 race_week_brief tests pass unchanged. Slice landing is purely additive.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 7+ predecessor handoffs §4); verified by `git stash` round-trip that this slice did NOT introduce or worsen it.

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog as 3 new scenarios under "3 D-73 Phase 5.2 caller-side routes" entry:

**Phase 5.2 caller-side routes (D-63 + plan-create)** — 3-step verification:

**Step 1: Migration applied on Neon.** Run `init_db.py` against Neon DB. Confirm:
- `\d ad_hoc_workout_suggestions` shows BIGSERIAL PK + user_id INTEGER FK + requested_at + request_payload JSONB NOT NULL + generated_session JSONB (nullable) + status TEXT NOT NULL with CHECK constraint in (suggested, logged, discarded, regenerated) + logged_into_table TEXT + logged_into_id BIGINT + discarded_at + regenerated_into_id BIGINT self-FK + token_cost_estimate + created_at.
- `\di ad_hoc_workout_suggestions*` shows `ad_hoc_workout_suggestions_user_status_idx`.

**Step 2: D-63 happy-path against Andy's PGE 2026 context.**
- Log in as Andy.
- Navigate to `/workouts/build` (direct URL — dashboard CTA is a follow-on; see CARRY_FORWARD.md "Dashboard CTAs" entry).
- Pick sport=Running + duration=60 + intensity=hard + locale=home + optional notes "focus on hill climbs"; click "Generate workout".
- Confirm a row lands in `ad_hoc_workout_suggestions` with `status='suggested'` + `request_payload` matches the SingleSessionRequest JSON + `generated_session` populated with a PlanSession JSON (cardio kind + 60min total across warmup/main/cooldown blocks).
- Page redirects to `/workouts/suggestions/<id>` rendering the cardio_blocks loop + coaching_intent + session_notes + [Regenerate] / [Discard] buttons.
- Click [Regenerate]; confirm a NEW row lands (id+1) with the prior row flipped to `regenerated` + `regenerated_into_id` linking to the new row; new row displays a different session (LLM stochasticity).
- Click [Discard] on the new row; confirm `status='discarded'` + `discarded_at` populated.
- Real-LLM cost: ~$0.05 per generate (single-session is the cheapest Layer 4 entry point — no full upstream cone, no 3B/2B/2E).

**Step 3: plan-create happy-path against Andy's PGE 2026 context.**
- Log in as Andy.
- Navigate to `/plans/v2/new`. Confirm the form shows Andy's PGE 2026 target race in the read-only summary block (since `is_target_event=TRUE`).
- Pick `plan_start_date=2026-04-01` (or today + a small offset for testing — orchestrator validates `>= today`).
- Click "Create plan". Watch the request take ~30-60s (Pattern A: 3-4 per-phase synthesizer calls + 2-3 seam reviewer calls).
- Confirm a `plan_versions` row lands with `created_via='plan_create'` + `pattern='A'` + `scope_start_date=2026-04-01` + `scope_end_date=2026-07-17` (PGE date).
- Confirm `plan_sessions` rows land for all dates in scope with the natural-key `(plan_version_id, date, session_index_in_day)` populated.
- Page redirects to `/plans/v2/<plan_version_id>` rendering the plan grouped by date with discipline + duration + intensity badge + coaching_intent per session.
- Reload `/plans/v2/<plan_version_id>` — confirm sessions render identically (cache hit; ~$0).
- Real-LLM cost: ~$0.30-$0.50 first-fire.

**Pre-walkthrough nit:** Dashboard CTAs to `/workouts/build` + `/plans/v2/new` are NOT yet wired (forward-pointer follow-on in CARRY_FORWARD). Athletes find the surfaces via direct URL until dashboard cards are added.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**(a) D-64 caller-side route + NL parser glue.** The last unfired caller-side arc. Makes slice 2's `orchestrate_plan_refresh` E2E-reachable from v1 UI. Largest of the 3 caller-side arcs because it requires a separate /plan Trigger #2 LLM prompt-design session for the NEW `aidstation-sources/prompts/NLParser_v1.md` (D-64 Decision #12 deferred) BEFORE route work; then `nl_parser.py` LLM-backed implementation + `routes/plan_refresh.py` + tier-picker template + tests. Files (est. 5-7 across 2 sessions): NL parser prompt-design session = 1 substantive (the prompt body); route session = 4-6 substantive (`nl_parser.py` + `routes/plan_refresh.py` + `templates/plans/v2/refresh.html` + tests + init_db migration if any new schema). **`/plan` gate per Trigger #2 (NL parser LLM prompt design)** + Trigger #1 (form copy on the refresh-trigger card + tier picker) + Trigger #5 (route shape — dashboard CTA vs plan-view button entry + redirect-after-refresh UX).

### 6.2 Alternative pivots

- **Log-this slice + D-63 T1 plan-check hook** — pairs naturally with D-64 caller-side. Adds `is_ad_hoc` + `ad_hoc_request_payload` + `ad_hoc_suggestion_id` extensions to `cardio_log` + `training_log` per D-63 §5.1/§5.2; wires `[Log this workout]` button on `templates/workouts/suggestion_view.html`; surfaces T1 refresh CTA. Gated on D-64 caller-side landing first (T1 hook needs the refresh route). ~5-7 files.
- **Dashboard CTAs** — `/workouts/build` + `/plans/v2/new` cards on `templates/dashboard.html` (D-63 §3.1). ~1-2 files. Pair with manual §5.0 walkthrough.
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1 + #3 + #5).
- **Layer 3A + 3B caching policy modules at orchestrator level** — with 4 entry points + 2 of 3 caller-side routes shipped, the orchestrator-level cache is increasingly load-bearing. ~4-6 files.
- **Layer 3B None-tolerant kwargs L3B-P-2** consumer migration. ~3-4 files.
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — ~1-2 files; doc-sweep nit from form-refresh C.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Manual §5.0 walkthrough** of D-63 + plan-create routes E2E on Neon (once dashboard CTAs land for findability). Real-LLM ~$0.50-$1.00 per pass.
- **Real-LLM Layer 4 regression** parity to plan_create (~$0.30-$0.50 per cold synthesis on Pattern A's per-phase loop).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_D63_PlanCreate_Routes_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | D-63 schema scope = `ad_hoc_workout_suggestions` only; `cardio_log`/`training_log` `is_ad_hoc` extensions defer | Andy | Scope discipline. Generate-the-suggestion surface lands first; the log-this transition (status `suggested` → `logged`) needs the cardio_log/training_log schema work + the T1 hook UX, which pairs with D-64 caller-side. Splitting cleanly keeps both slices under ceiling. |
| **D2** | URL prefixes `/workouts/*` + `/plans/v2/*` | Andy | Avoid v1 `routes/plans.py` legacy collision (legacy plan-import surface). `v2` prefix flags the new pipeline cleanly + leaves room for future v2 routes. |
| **D3** | Broad framework_sport list `SELECT DISTINCT framework_sport FROM layer0.sports WHERE superseded_at IS NULL` | Andy ratified at AskUserQuestion gate | Simpler form, smaller scope. Filtering to athlete's primary_sport set + Layer 2A cross-training options is a v2 follow-on requiring a new helper + a test. Broad list is the simplest workable v1. |
| **D4** | Quick-equipment "Somewhere else" path defer | Andy | Per D-63 §3.4 the path requires a sport-conditional checkbox grid + free-text "other" line. Form-shape variant + per-sport conditional logic is a meaningful surface; out of scope this slice. Form-refresh follow-on. |
| **D5** | Caller owns transaction per substrate D-64 §6.2 | Andy | Route handler manages atomic write: allocate → orchestrate → persist → `db.commit()`. On any raised exception in the chain no commit fires; the connection's auto-rollback keeps half-allocated rows off the table. Exactly what the substrate intended. |
| **D6** | `PostgresCacheBackend(lambda: get_db())` cache factory in production | Andy | Real cache from day 1; repeat workouts/plans cache-hit free. `InMemoryCacheBackend()` is for tests only (always-empty in prod = $0.30-$0.50 cost per repeat plan). |
| **D7** | No target-race picker on plan-create form | Andy | Orchestrator already calls `load_target_race_event_payload(db, user_id)` which reads the `is_target_event=TRUE` row from `race_events`. Form only asks for `plan_start_date`. Race association lives on `/profile/race-events`; the plan-create form would duplicate that surface. |
| **D8** | `notes=None` on `allocate_plan_version_row` for v1 | Andy | Population from `payload.phase_structure.phases[*].phase_synthesis_notes` requires a new `update_plan_version_notes` repo helper that doesn't exist; substrate intentionally shipped 4 helpers no update. Future-clean over half-wired notes. |
| **D9** | Inline 4-helper layout in `routes/ad_hoc_workouts.py` (no `ad_hoc_workouts_repo.py`) | Andy | The table has a narrow surface + single caller. Substrate's repo-extract precedent (`race_events_repo.py` / `plan_sessions_repo.py`) applies when ≥2 callers exist. Extract when a 2nd caller appears (e.g., the log-this slice's `[Log this workout]` POST handler will be the 2nd caller). |
| **D10** | Result-view actions = `[Regenerate]` + `[Discard]` only on D-63 | Andy | `[Log this workout]` needs the cardio_log/training_log `is_ad_hoc` extensions + the T1 hook UX, both pair with D-64 caller-side. Half-wired log-this would be worse than none. |
| **D11** | 9-file ceiling break ratified | Andy ratified at AskUserQuestion gate | Substrate handoff §6.1 explicitly recommended batching (a)+(b) ("~6-8 files batched"). Actual count = 9. Precedented by Phase 5.1.A=8 + 5.1.C=8. Splitting would lose the batching benefit + spread across 2 sessions for marginal ceiling cleanliness. |
| **D12** | Helper-level pytest density; end-to-end Flask test_client deferred to manual §5.0 walkthrough | Andy | Existing route modules (`routes/race_events.py` + `routes/onboarding.py` + `routes/locales.py`) all follow this precedent. End-to-end via Flask test_client doubles the test infrastructure (test app fixture + CSRF tokens + session cookies) for marginal value; manual §5.0 walkthrough catches the same regressions on Neon. Helper-level pytest is sufficient. |
| **D13** | Batch (a) + (b) | Andy ratified at AskUserQuestion gate | Per substrate handoff §6.1 explicit recommendation. Both arcs small; share `persist_layer4_sessions` substrate; ship E2E-reachability for 2 of 3 entry points in one session. |
| **D14** | Broad sport vocabulary on D-63 form | Andy ratified at AskUserQuestion gate | Simplest workable v1; per-athlete filtering is a v2 enhancement. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` has new `ad_hoc_workout_suggestions` table migration | ✅ `grep -n "CREATE TABLE IF NOT EXISTS ad_hoc_workout_suggestions" init_db.py` |
| `init_db.py` has new `ad_hoc_workout_suggestions_user_status_idx` migration | ✅ `grep -n "ad_hoc_workout_suggestions_user_status_idx" init_db.py` |
| NEW `routes/ad_hoc_workouts.py` exists with Blueprint `/workouts/*` | ✅ `grep -n "Blueprint.*ad_hoc_workouts.*url_prefix='/workouts'" routes/ad_hoc_workouts.py` |
| `routes/ad_hoc_workouts.py` has 4 routes | ✅ `grep -c "^@bp.route" routes/ad_hoc_workouts.py` returns 4 |
| `routes/ad_hoc_workouts.py` has 9 inline helpers (incl `_build_layer4_cache` + `_orchestration_error_message`) | ✅ `grep -c "^def _" routes/ad_hoc_workouts.py` returns 9 |
| NEW `templates/workouts/build_form.html` exists | ✅ |
| NEW `templates/workouts/suggestion_view.html` exists | ✅ |
| NEW `routes/plan_create.py` exists with Blueprint `/plans/v2/*` | ✅ `grep -n "Blueprint.*plan_create.*url_prefix='/plans/v2'" routes/plan_create.py` |
| `routes/plan_create.py` has 2 routes | ✅ `grep -c "^@bp.route" routes/plan_create.py` returns 2 |
| `routes/plan_create.py` has 5 inline helpers (incl `_build_layer4_cache`) | ✅ `grep -c "^def _" routes/plan_create.py` returns 5 |
| NEW `templates/plan_create/new_form.html` exists | ✅ |
| NEW `templates/plan_create/view.html` exists | ✅ |
| NEW `tests/test_routes_ad_hoc_workouts.py` has 8 test classes | ✅ `grep -c "^class Test" tests/test_routes_ad_hoc_workouts.py` returns 8 |
| NEW `tests/test_routes_ad_hoc_workouts.py` has 29 tests | ✅ `grep -c "    def test_" tests/test_routes_ad_hoc_workouts.py` returns 29 |
| NEW `tests/test_routes_plan_create.py` has 4 test classes | ✅ `grep -c "^class Test" tests/test_routes_plan_create.py` returns 4 |
| NEW `tests/test_routes_plan_create.py` has 16 tests | ✅ `grep -c "    def test_" tests/test_routes_plan_create.py` returns 16 |
| All 45 new tests pass | ✅ `pytest tests/test_routes_ad_hoc_workouts.py tests/test_routes_plan_create.py -q` reports 45 passed |
| `app.py` registers 2 new blueprints | ✅ `grep "register_blueprint(ad_hoc_workouts_bp)\|register_blueprint(plan_create_bp)" app.py` returns 2 lines |
| Container-runnable subset green at 568 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py tests/test_plan_sessions_repo.py tests/test_routes_ad_hoc_workouts.py tests/test_routes_plan_create.py` reports 568 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has new row 5.2.Caller-D63+PlanCreate → ✅ Shipped 2026-05-21 | ✅ |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 caller-side D-63 + plan-create routes handoff | ✅ |
| `CURRENT_STATE.md` tests count flipped 1190 → 1235 | ✅ |
| `CARRY_FORWARD.md` D-63 caller-side + plan-create caller-side entries struck (✅ Shipped) | ✅ |

---

## 9. Files shipped this session

**Substantive (9 files; ceiling break ratified at AskUserQuestion gate):**

1. MODIFIED `init_db.py` (+~30 LOC net) — new `CREATE TABLE IF NOT EXISTS ad_hoc_workout_suggestions (...)` migration + 1 index in `_PG_MIGRATIONS`; inline comment block documents schema rationale.
2. NEW `routes/ad_hoc_workouts.py` (~330 LOC) — Blueprint `/workouts/*` + 9 inline helpers + 4 routes.
3. NEW `templates/workouts/build_form.html` (~70 LOC) — Bootstrap form: sport / duration / intensity / locale / notes.
4. NEW `templates/workouts/suggestion_view.html` (~80 LOC) — generated PlanSession render + Regenerate/Discard actions.
5. NEW `tests/test_routes_ad_hoc_workouts.py` (~330 LOC) — 29 tests across 8 classes.
6. NEW `routes/plan_create.py` (~190 LOC) — Blueprint `/plans/v2/*` + 5 inline helpers + 2 routes.
7. NEW `templates/plan_create/new_form.html` (~50 LOC) — date input + target-race summary + create button.
8. NEW `templates/plan_create/view.html` (~50 LOC) — plan view sessions grouped by date.
9. NEW `tests/test_routes_plan_create.py` (~190 LOC) — 16 tests across 4 classes.

**Bookkeeping (5 files):**

10. MODIFIED `app.py` — 2 import lines + 2 `register_blueprint` calls.
11. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flip + tests count + current-focus arc refocused on D-64 caller-side.
12. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — D-63 caller-side + plan-create caller-side entries struck (✅); new log-this + dashboard-CTAs follow-on entries; 3 new §5.0 walkthrough scenarios.
13. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row 5.2.Caller-D63+PlanCreate.
14. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_D63_PlanCreate_Routes_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- "`ad_hoc_workout_suggestions` table + D-63 caller-side route" — struck (✅ Shipped 2026-05-21).
- "plan-create caller-side route" — struck (✅ Shipped 2026-05-21).
- New entry: "Log-this slice + D-63 T1 plan-check hook" — pairs with D-64 caller-side; adds cardio_log/training_log `is_ad_hoc` extensions + wires the [Log this workout] action + T1 refresh CTA.
- New entry: "Dashboard CTAs for `/workouts/build` + `/plans/v2/new`" — D-63 §3.1 dashboard surfacing + plan-create analogue; ~1-2 files; pair with manual §5.0 walkthrough.
- New §5.0 walkthrough scenarios: 3 D-73 Phase 5.2 caller-side routes (init_db migration spot-check + D-63 happy-path on Andy's PGE 2026 + plan-create happy-path).
- §5.0 scenario count: 70 → 73.

**Phase 5.2 caller-side routes for 2 of 3 entry points complete; D-64 caller-side route + NL parser glue remain (gated on /plan Trigger #2 NL parser prompt-body design session before route work).** 4 of 4 Layer 4 entry points wired at the orchestrator level; 2 of 3 caller-side routes E2E-reachable from v1 UI (single_session + plan_create).

---

**End of handoff.**
