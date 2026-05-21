# D-73 Phase 5.2 Dashboard CTAs — Closing Handoff

**Session:** D-73 Phase 5.2 dashboard CTAs. Wires the 3 Layer 4 v2 caller-side routes shipped earlier this same-day arc (single_session, plan_create, plan_refresh) onto the dashboard so athletes find them without knowing direct URLs. Closes the §6.1 architect-recommended forward move from the D-64 runtime closing handoff. **3 substantive files** (well under 5-file ceiling).
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_CallerSide_D64_Runtime_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/dashboard-ctas-UOFaP` (renamed at session start from harness-pinned `claude/caller-side-runtime-phase5-UOFaP` per CLAUDE.md branch-naming rule — the pinned name matched the previous session's scope, not this one).
**Status:** 3 substantive files. Tests 1331 → 1334 (+3 net new in 1 NEW test file). Container-runnable subset 664 → 667 in ~1.8s. 16 skipped tests (12 NL parser smoke + 4 prior Layer 3 SDK smoke) unchanged.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (D-64 NL parser runtime + plan_refresh route) handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `nl_parser.py` exists | `ls nl_parser.py` | ✅ |
| `routes/plan_refresh.py` exists | `ls routes/plan_refresh.py` | ✅ |
| `templates/plans/v2/refresh.html` exists | `ls templates/plans/v2/refresh.html` | ✅ |
| `templates/plans/v2/refresh_view.html` exists | `ls templates/plans/v2/refresh_view.html` | ✅ |
| `tests/test_nl_parser.py` exists | `ls tests/test_nl_parser.py` | ✅ |
| `tests/test_nl_parser_smoke.py` exists | `ls tests/test_nl_parser_smoke.py` | ✅ |
| `tests/test_routes_plan_refresh.py` exists | `ls tests/test_routes_plan_refresh.py` | ✅ |
| `init_db.py` `_PG_MIGRATIONS` includes `plan_refresh_log` | grep | ✅ |
| `app.py` registers `plan_refresh_bp` | grep | ✅ |
| `layer4/cache.py` `VALID_ENTRY_POINTS` includes `nl_parser_parse_intent` | grep | ✅ |
| Container-runnable subset green at 664 | pytest | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → D-64 runtime | grep | ✅ |

`./scripts/verify-handoff.sh` ran clean — all referenced files present, branch clean, working tree clean. No drift.

**Reconciliation note:** Clean. The prior D-64 runtime work was already merged to main via PR #119 (`ec60901`); this branch (`claude/caller-side-runtime-phase5-UOFaP`) started equal to `origin/main`. No in-progress work to inherit. Branch renamed locally before any edits (per CLAUDE.md branch-naming rule).

---

## 2. Session narrative

Andy ratified scope at the AskUserQuestion gate: **Dashboard CTAs** for the 3 v2 caller-side routes (the architect-recommended §6.1 forward move from the D-64 runtime closing handoff), over the §6.2 alternatives (log-this slice + T1 hook, NL parser caps, Haiku migration, form-refresh D, orchestrator 3A/3B caching, manual §5.0 walkthrough, locales 2C invalidation gap, Plan Management spec, real-LLM Layer 4 regression).

Pre-design surface survey:

- `templates/dashboard.html` (358 LOC) — vertical stack of sections: brand header → Today's/Tomorrow's Workouts + Weather → conditional alerts (clothing recs, unconditioned cardio, missed workouts) → Stats row (4 cards) → Recent Activity (Strength + Cardio tables). Bootstrap grid; Today/Tomorrow blocks still read legacy v1 `plan_items` + `training_plans` tables. No v2 route surfacing existed.
- `routes/dashboard.py:index` (lines 52-168) — Flask blueprint at `bp = Blueprint('dashboard', __name__)`; route `/` renders `dashboard.html` with stats, today/tomorrow/missed workouts, recent training/cardio, weather, clothing recs, unconditioned cardio. Easy seam to thread a new `has_plan_version` kwarg.
- `routes/plan_refresh.py:89` — `_latest_plan_version(db, user_id) -> dict | None` precedent; for dashboard we only need a boolean, so a cheaper `SELECT 1 FROM plan_versions WHERE user_id = ? LIMIT 1` works.
- `init_db.py:1083-1101` — `plan_versions` table schema (BIGSERIAL PK + user_id FK + created_via + scope dates + pattern + supersession + 2 indexes). Already deployed; no schema work needed this session.
- `routes/ad_hoc_workouts.py:54` — `Blueprint('ad_hoc_workouts', __name__, url_prefix='/workouts')` + `def build_workout()` at line 227 → `url_for('ad_hoc_workouts.build_workout')`.
- `routes/plan_create.py:54` — `Blueprint('plan_create', __name__, url_prefix='/plans/v2')` + `def new_plan()` at line 128 → `url_for('plan_create.new_plan')`.
- `routes/plan_refresh.py:62` — `Blueprint("plan_refresh", __name__, url_prefix="/plans/v2/refresh")` + `def refresh()` at line 314 → `url_for('plan_refresh.refresh')`.

The 4 design questions surfaced at the AskUserQuestion gate:

- **D1: Branch rename = `claude/dashboard-ctas-UOFaP`.** Picked over keeping the harness-pinned `claude/caller-side-runtime-phase5-UOFaP`. CLAUDE.md branch-naming rule: rename when harness-pinned name mismatches scope. The pinned name matched the prior session's D-64 runtime scope verbatim — not this one. Suffix `UOFaP` preserved as the harness marker.
- **D2: CTA placement = top of dashboard, directly under brand header, above Today's Workouts.** Picked over (b) after Stats row (lower discoverability), (c) split (Refresh up top, Build+Create lower; higher visual cost). Andy's pick makes v2 routes the first interactive surface athletes see. The legacy v1 Today's Workouts section (still reading `plan_items` + `training_plans`) gets pushed down ~120px, which is the right relative priority anyway — v2 is the path forward.
- **D3: Conditional rendering = always show all 3 cards + gray out Refresh + swap copy when athlete has no `plan_versions` row.** Picked over (a) always show all 3 with no conditional copy (Refresh route's own empty-state would catch it, but bouncing through a route is worse UX than signaling state in the card), (b) hide Refresh when no plan (changes layout depending on athlete state — feels jumpy). Andy's pick preserves stable layout while signaling state up-front. Requires 1 helper (`_has_plan_version`) + 1 new template var.
- **D4: Card copy approved as drafted.** Build: "Need a one-off session? Generate a single workout tailored to your sport, duration, and locale." Create: "Generate a full training plan from your current state through your target race." Refresh: "Update the next 2 days, week, or 4 weeks based on how training is actually going." Disabled-state Refresh body: "Available once you have an active plan." Matches CLAUDE.md coaching voice (direct, no platitudes, no hype). Iterative per Trigger #1 — not a gate, but ratified explicitly to avoid back-and-forth.

Implementation flow:

1. **`templates/dashboard.html`** — NEW "Quick actions" row inserted between the brand header (line 25) and the "Today + Weather" row (line 26 onwards). 3 cards in a `row g-3 mb-3` with `col-md-4` each. Card body uses `d-flex flex-column` + `flex-grow-1` on the body paragraph + `align-self-start` on the button so 3 different-length bodies render with the button vertically aligned at the same bottom-left position. Refresh card wraps title-body-button in a `{% if has_plan_version %}` Jinja branch — primary state uses `btn-primary` + working `url_for('plan_refresh.refresh')` link; disabled state uses `opacity-50` on the card + `btn-secondary disabled` with `aria-disabled="true"` + `tabindex="-1"` + `href="#"` on the anchor. Build + Create cards render unconditionally (both target routes accept any athlete state — single_session is athlete-driven off-plan-off-race; plan_create works regardless of prior plans).

2. **`routes/dashboard.py`** — NEW `_has_plan_version(db, user_id) -> bool` helper at module scope. Cheap `SELECT 1 FROM plan_versions WHERE user_id = ? LIMIT 1` — only fetches existence, doesn't carry latest-row fields like `_latest_plan_version` does. Threaded into `index()` as `has_plan_version = _has_plan_version(db, uid)`; added as a `render_template` kwarg.

3. **NEW `tests/test_routes_dashboard.py`** (~60 LOC; 3 tests in `TestHasPlanVersion` class) — first test file for `routes/dashboard.py`. Mirrors `tests/test_routes_plan_refresh.py` test-double pattern: `_FakeRow` dict + `_FakeCursor.fetchone()` + `_FakeConn.execute()` recording calls. Tests cover: True-when-row-present, False-when-row-absent, SQL-is-user-id-scoped (asserts `FROM plan_versions`, `WHERE user_id = ?`, `LIMIT 1`, params `(42,)`).

`/plan` Triggers fired: #5 (architectural alternatives — placement + conditional render) cleared via AskUserQuestion before drafting; #1 (form copy on the 3 CTA cards) iterative — Andy approved drafts in the same gate. Triggers #2 / #3 / #4 / #6 did not fire (no LLM prompt design, no schema, no HITL gate, no status/architecture promotion).

---

## 3. File-by-file edits

### 3.1 `templates/dashboard.html` — Quick actions row

- Inserted between `{# ── Brand header ── #}` block (lines 5-24) and `{# ── Today + Weather ── #}` block (line 26 onwards). Exact insertion point: right before `{# ── Today + Weather ── #}` comment + the following `<div class="row g-3 mb-3">`.
- New block:
  - `{# ── Quick actions (Layer 4 v2 entry points) ── #}`
  - `<div class="row g-3 mb-3">` with 3 `<div class="col-md-4">` columns.
  - Each card has `<div class="card h-100">` (Refresh card adds `{% if not has_plan_version %}opacity-50{% endif %}`) wrapping `<div class="card-body d-flex flex-column">` (fw-semibold title + `<p class="text-muted small flex-grow-1 mb-3">` body + `<a class="btn btn-primary btn-sm align-self-start">` button).
  - Refresh card uses `{% if has_plan_version %} ... {% else %} ... {% endif %}` Jinja branch around the body + button — when False the body reads "Available once you have an active plan." and the button is `btn-secondary disabled` + `aria-disabled="true"` + `tabindex="-1"` + `href="#"`.
- `url_for` endpoints (verified at session-start grep against routes/):
  - Build card → `url_for('ad_hoc_workouts.build_workout')` → `/workouts/build`
  - Create card → `url_for('plan_create.new_plan')` → `/plans/v2/new`
  - Refresh card → `url_for('plan_refresh.refresh')` → `/plans/v2/refresh`
- Jinja syntax validated by parsing the template through a `jinja2.Environment` at session-end (5 AST nodes, no syntax errors).

### 3.2 `routes/dashboard.py` — `_has_plan_version` helper

- Added `_has_plan_version(db, user_id: int) -> bool` between `_weather_cache = {}` (line 12) and `_get_weather` (line 15).
- Body: `SELECT 1 FROM plan_versions WHERE user_id = ? LIMIT 1`; returns `row is not None`. Cheap existence-check (LIMIT 1 + no field selection).
- Docstring documents the dashboard CTA gating role + the fact that `/plans/v2/refresh` itself has an empty-state CTA back to `/plans/v2/new`, so the dashboard signal short-circuits a bounce rather than enforces hard navigation.
- Threaded into `index()`: `has_plan_version = _has_plan_version(db, uid)` after `clothing_recs` resolution, before `_get_weather(db)` call.
- Added to the `render_template` kwarg list: `has_plan_version=has_plan_version`.

### 3.3 NEW `tests/test_routes_dashboard.py` (~60 LOC; 3 tests in 1 class)

- Test class `TestHasPlanVersion`:
  - `test_returns_true_when_row_present` — queues `{"?column?": 1}` row; expects `True`.
  - `test_returns_false_when_no_row` — queues `None`; expects `False`.
  - `test_query_is_user_scoped` — asserts 1 SQL call; SQL contains `FROM plan_versions`, `WHERE user_id = ?`, `LIMIT 1`; params == `(42,)`.
- `_FakeRow` / `_FakeCursor` / `_FakeConn` test doubles mirror `tests/test_routes_plan_refresh.py`. The `_FakeConn` substrate here is lighter (no `commit` / `rollback` counters since `_has_plan_version` is read-only).

---

## 4. Code / tests

**Tests 1331 → 1334 (+3 net new in 1 NEW test file):**

- `tests/test_routes_dashboard.py` 3 tests in `TestHasPlanVersion` (returns_true_when_row_present + returns_false_when_no_row + query_is_user_scoped)

**Container-runnable subset 664 → 667 in ~1.8s.**

Run reproducer for the container-runnable subset (matches the predecessor handoff §4 invocation + the new file):

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
                                tests/test_routes_plan_create.py \
                                tests/test_nl_parser.py \
                                tests/test_routes_plan_refresh.py \
                                tests/test_nl_parser_smoke.py \
                                tests/test_routes_dashboard.py
# 667 passed, 12 skipped in 1.78s
```

**No-regression confirmation:** All 664 pre-existing container-subset tests pass unchanged. Only `routes/dashboard.py` + `templates/dashboard.html` touched on the runtime surface; no edits to `layer4/`, `routes/plan_refresh.py`, `routes/plan_create.py`, `routes/ad_hoc_workouts.py`, repos, schema, or specs.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 8+ predecessor handoffs §4).

---

## 5. Manual §5.0 verification steps

Forward-pointer for the next manual walkthrough pass:

**Step 1: Empty-state dashboard.** Fresh athlete with no `plan_versions` row — log in, navigate to `/`, confirm the dashboard renders a NEW "Quick actions" row directly below the brand header + above Today's Workouts containing 3 equal-width Bootstrap cards. "Build a workout" card body reads "Need a one-off session? Generate a single workout tailored to your sport, duration, and locale." with a primary "Build a workout" button linking to `/workouts/build`. "Create a training plan" card body reads "Generate a full training plan from your current state through your target race." with a primary "Create a plan" button linking to `/plans/v2/new`. "Refresh your plan" card renders with `opacity-50` styling + body reads "Available once you have an active plan." + button styled `btn-secondary disabled` with `aria-disabled="true"` and `tabindex="-1"` (button visible but does not navigate when clicked).

**Step 2: Populated-state dashboard.** Athlete with at least one `plan_versions` row (Andy after plan-create walkthrough) — log in, navigate to `/`, confirm the same "Quick actions" row renders but the "Refresh your plan" card has NO opacity-50 styling + body reads "Update the next 2 days, week, or 4 weeks based on how training is actually going." + button styled `btn-primary` linking to `/plans/v2/refresh`. End-to-end click-through: from each card button, land on the target route's GET surface (workouts/build form, plan_create form with PGE 2026 target-race summary, refresh tier-picker with parent-plan summary card).

Captured in `CARRY_FORWARD.md` manual walkthrough section (2 new scenarios).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Log-this slice + D-63 T1 plan-check hook.** With all 3 caller-side routes dashboard-reachable, the next caller-side surface work is the log-this slice that pairs with D-64. Adds `is_ad_hoc` + `ad_hoc_request_payload` + `ad_hoc_suggestion_id` extensions to `cardio_log` + `training_log` per D-63 §5.1/§5.2; wires `[Log this workout]` button on `templates/workouts/suggestion_view.html` → POST `/workouts/suggestions/<id>/log` allocates a cardio_log/training_log row + flips suggestion status to `logged` + surfaces the T1 refresh CTA (which fires D-64 with NL context auto-filled per §5.4); `[No, thanks]` logs `t1_hook_dismissed=TRUE` per §3.5. ~5-7 files.

**`/plan` gate sequence:** Trigger #1 (form copy on the log-this button + T1 hook prompt copy) + Trigger #3 (new columns on `cardio_log` + `training_log`, both shared tables — cross-layer surface change) + Trigger #5 (T1 hook UX shape — auto-fired modal vs inline prompt vs post-redirect banner).

### 6.2 Alternative pivots

- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — ~1-2 files; doc-sweep nit from form-refresh C investigation. Add `_evict_layer2c_on_equipment_change(db, uid)` mirror of the terrain helper + wire to both legacy + shared edit branches on actual equipment-set change. No `/plan` triggers.
- **NL parser frequency caps per D-64 §8** — deferred via D4 in the D-64 runtime session. T1 ≤3/24h, T2 ≤1/48h, T3 ≤1/7d server-side count against `plan_refresh_log`; modal-confirm UI when exceeded; new `cap_overridden` column on `plan_refresh_log`. ~3-4 files. `/plan` gate: Trigger #3 (column add on existing telemetry table) + Trigger #5 (cap-exceeded UX — modal vs blocking gate vs soft warning).
- **NL parser smoke-eval harness expansion + Haiku 4.5 migration eval per NL-1** — ~5-6 files; need ~20-30 hand-labeled fixtures + a Haiku-vs-Sonnet agreement comparison harness. Cost gain ~10× ($0.0003-$0.0005/call vs $0.003-$0.005/call) if Haiku holds ≥95% agreement.
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1+#3+#5).
- **Layer 3A + 3B caching policy at orchestrator level** — all 4 entry points call `llm_layer3a_athlete_state` + `llm_layer3b_goal_timeline_viability` uncached. With dashboard now driving real athlete traffic to all 3 entry points, orchestrator-level 3A/3B caching becomes near-load-bearing. ~4-6 files.
- **Manual §5.0 walkthrough** of D-64 + D-63 + plan_create + dashboard CTAs E2E on Neon (real-LLM ~$1.00 per pass across the 3 routes; dashboard surface is no-cost).
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Real-LLM Layer 4 regression** parity to plan_refresh (~$0.30-$0.50 per cold synthesis on Pattern B + ~$0.50-$1.00 on Pattern A).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Dashboard_CTAs_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Branch rename to `claude/dashboard-ctas-UOFaP` | Andy ratified at AskUserQuestion gate | CLAUDE.md branch-naming rule: rename when harness-pinned name (`caller-side-runtime-phase5-UOFaP`) mismatches scope. The pinned name matched the previous session's D-64 runtime scope verbatim, not this one. `UOFaP` suffix preserved as the harness marker. |
| **D2** | CTA placement = top of dashboard, directly under brand header, above Today's Workouts | Andy | Picked over after-Stats-row + split-Refresh-up-top alternatives. Makes v2 routes the first interactive surface athletes see; the legacy v1 Today's Workouts (still reading `plan_items` + `training_plans`) gets pushed down ~120px, which matches the relative priority since v2 is the path forward. |
| **D3** | Conditional render = always show all 3 cards + gray out Refresh + swap copy when athlete has no `plan_versions` row | Andy | Picked over always-show-no-conditional (Refresh route's own empty-state would catch it, but bouncing through a route is worse UX than signaling state in the card) + hide-Refresh-when-no-plan (changes layout depending on athlete state — feels jumpy). Stable layout + up-front state signal. Requires 1 helper `_has_plan_version(db, user_id)` + 1 new template var. |
| **D4** | Card copy approved as drafted in the AskUserQuestion preview block | Andy | Build / Create / Refresh titles match button text; bodies are single-sentence per spec D-63 §3.1 + D-64 §4.1. Disabled-state Refresh body reads "Available once you have an active plan." Matches CLAUDE.md coaching voice (direct, no platitudes, no hype). |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `templates/dashboard.html` has new "Quick actions" row block | ✅ `grep "Quick actions (Layer 4 v2 entry points)" templates/dashboard.html` |
| `templates/dashboard.html` references `url_for('ad_hoc_workouts.build_workout')` | ✅ `grep "ad_hoc_workouts.build_workout" templates/dashboard.html` |
| `templates/dashboard.html` references `url_for('plan_create.new_plan')` | ✅ `grep "plan_create.new_plan" templates/dashboard.html` |
| `templates/dashboard.html` references `url_for('plan_refresh.refresh')` | ✅ `grep "plan_refresh.refresh" templates/dashboard.html` |
| `templates/dashboard.html` Refresh card has `{% if has_plan_version %}` branch + `opacity-50` + `btn-secondary disabled` | ✅ `grep "has_plan_version" templates/dashboard.html` + grep `opacity-50` + grep `btn-secondary disabled` |
| `routes/dashboard.py` defines `_has_plan_version` | ✅ `grep "def _has_plan_version" routes/dashboard.py` |
| `routes/dashboard.py` `_has_plan_version` uses `SELECT 1 FROM plan_versions WHERE user_id = ? LIMIT 1` | ✅ grep |
| `routes/dashboard.py` threads `has_plan_version` into `render_template` | ✅ `grep "has_plan_version=has_plan_version" routes/dashboard.py` |
| NEW `tests/test_routes_dashboard.py` exists with 3 tests in `TestHasPlanVersion` class | ✅ `ls tests/test_routes_dashboard.py` + `grep "class TestHasPlanVersion" tests/test_routes_dashboard.py` |
| Container-runnable subset 664 → 667 (+3 net new) | ✅ pytest run returns "667 passed, 12 skipped in ~1.8s" |
| Tests 1331 → 1334 (+3 net new in 1 NEW test file) | ✅ Counted via new test file: 3 |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 Dashboard CTAs handoff | ✅ |
| `CURRENT_STATE.md` tests count flipped to 1334 + 16 skipped | ✅ |
| `CURRENT_STATE.md` Layer 4 status row updated to reflect dashboard CTAs landing | ✅ |
| `CARRY_FORWARD.md` Dashboard CTAs entry struck (✅ Shipped) + new manual §5.0 walkthrough scenarios (2) added | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 has new row `5.2.Dashboard-CTAs` → ✅ Shipped 2026-05-21 | ✅ `grep "5.2.Dashboard-CTAs" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| Branch renamed to `claude/dashboard-ctas-UOFaP` at session start | ✅ `git branch --show-current` |

---

## 9. Files shipped this session

**Substantive (3 files; well under 5-file ceiling):**

1. `templates/dashboard.html` — NEW "Quick actions" row with 3 Bootstrap cards.
2. `routes/dashboard.py` — NEW `_has_plan_version` helper + `has_plan_version` threaded to template context.
3. NEW `tests/test_routes_dashboard.py` (~60 LOC) — 3 helper tests in `TestHasPlanVersion`.

**Bookkeeping (4 files):**

4. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + Layer 4 status row + tests count.
5. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Dashboard CTAs entry struck + 2 new manual §5.0 walkthrough scenarios.
6. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row `5.2.Dashboard-CTAs`.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Dashboard_CTAs_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- "Dashboard CTAs for `/workouts/build` + `/plans/v2/new` + `/plans/v2/refresh`" entry → ✅ Shipped 2026-05-21 (`claude/dashboard-ctas-UOFaP`).
- 2 new manual §5.0 walkthrough scenarios added under D-73 Phase 5.2 dashboard CTAs (empty-state dashboard + populated-state dashboard click-through).

**Phase 5.2 caller-side v2 surfacing arc complete; all 3 of 3 Layer 4 caller-side routes E2E-reachable + dashboard-surfaced. The next caller-side surface work is the log-this slice + D-63 T1 plan-check hook (~5-7 files; `/plan` gate per Triggers #1+#3+#5).**

---

**End of handoff.**
