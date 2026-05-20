# D-73 Phase 5.2 Caller-Side Substrate — `plan_sessions` Table + Repo — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side substrate — lifts the Layer 4 §7.11 + §7.12 spec contract (PlanSession natural key + per-day version pointer per D-64 §6.3) into deployed schema + repo helpers. Substrate for the D-63 + D-64 + plan-create caller-side route arcs queued post Phase 5.2 closure. **No `/plan` Triggers #1/#3 fired** — schema is mechanical implementation of an existing spec contract; only D4 (lookback policy) was a real design call, ratified via AskUserQuestion gate.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_PlanCreate_Orchestrator_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/phase-5-2-orchestrator-QNUwA` (continues the slice 3 branch — substrate landed in the same harness session post Phase 5.2 closure)
**Status:** 3 substantive files (under 5-file ceiling); container-runnable subset 501 → 523 (+22); production count 1168 → 1190 (+22); 4 SDK smoke tests still skip cleanly. All prior orchestrator + race_events + locales + onboarding tests pass unchanged (purely additive).

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor (slice 3) handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `layer4/orchestrator.py` has `orchestrate_plan_create` function | `grep -n "^def orchestrate_plan_create"` | ✅ line 589 |
| `layer4/orchestrator.py` imports `llm_layer4_plan_create_cached` | grep | ✅ |
| `layer4/orchestrator.py` `__all__` includes `orchestrate_plan_create` | grep | ✅ |
| Module docstring reflects "Four entry points" | grep | ✅ |
| `layer4/__init__.py` re-exports `orchestrate_plan_create` (2 hits) | grep | ✅ |
| `tests/test_layer4_orchestrator.py` has 5 `TestOrchestratePlanCreate*` classes | `grep -c` | ✅ 5 |
| Container subset green at 501 | `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` | ✅ 501 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has row 5.2.S3 → ✅ Shipped 2026-05-20 | grep | ✅ |
| `CURRENT_STATE.md` last-shipped pointer → Phase 5.2 PlanCreate handoff | grep | ✅ |

`./scripts/verify-handoff.sh` flagged 3 ❌ at slice 3 close — `routes/ad_hoc_workouts.py` + `routes/plan_create.py` + `routes/plan_refresh.py`, all queued caller-side route forward-pointers.

**Reconciliation note:** Clean. No drift. The 3 ❌s are forward-pointers (queued caller-side routes) that this substrate-only session does NOT close (caller-side route work itself is a separate next-arc). Substrate landing is a prerequisite for those routes; this session ships the prerequisite.

---

## 2. Session narrative

Andy continued the thread after Phase 5.2 slice 3 shipped. Picked option (1) "D-64 + plan-create caller-side" at the next-move gate. Pre-implementation surface survey surfaced the scope mismatch: the D-64 spec defers `plan_versions` DDL (now on disk per Layer 4 §7.11), `plan_sessions` table (NOT on disk), and NL parser prompt body (deferred to its own Trigger #2 session). Full D-64 + plan-create caller-side arc realistically spans 12-15 files across 3-4 sessions — too large for this session's remaining context.

Andy picked **`plan_sessions` schema + repo** at the AskUserQuestion sub-piece gate — the substrate that unblocks all 3 caller-side route arcs without committing to the bigger NL-parser-design + route-handler arc. No `/plan` Triggers #1 / #3 fired — schema is mechanical implementation of Layer 4 §7.11 + §7.12 spec contract; only D4 (`prior_plan_session_window` lookback policy) was a real design call.

8 D-decisions surfaced + ratified before implementation:

- **D1: `plan_sessions` schema with JSONB payload column** (not 17-column denormalize). Simpler for v1; denormalize when plan-view queries become load-bearing. Natural key UNIQUE `(plan_version_id, date, session_index_in_day)` enforces Layer 4 §7.12 invariant at DB layer. user_id denormalized for fast (user_id, date) lookups bypassing the plan_versions join.
- **D2: Repo at repo root: `plan_sessions_repo.py`** (mirrors `race_events_repo.py` precedent; NOT inside `layer4/` — repos are caller-side per the 5.2 deferral pattern).
- **D3: 4 helpers** — `allocate_plan_version_row` + `persist_layer4_sessions` + `load_plan_sessions_by_version` + `load_prior_plan_session_window` + private `_decode_payload` for JSONB dual-path hydration.
- **D4: Tier-tied default lookback** — `_PRIOR_WINDOW_DAYS_BY_TIER = {T1: 2, T2: 7, T3: 28}` days (matches refresh forward-scope shape), with `days` kwarg override and ValueError when neither supplied. Ratified at AskUserQuestion gate over Fixed-2-week / Required-no-default alternatives.
- **D5: Caller owns transaction per D-64 §6.2** — `persist_layer4_sessions` does NOT call `db.commit()`. Route handler manages atomic boundary spanning `allocate_plan_version_row` + `orchestrate_*` + `persist_layer4_sessions`.
- **D6: 22 tests across 5 classes** at full helper coverage.
- **D7: user_id denormalized** into `plan_sessions` for fast (user_id, date) lookups bypassing the plan_versions join. plan_versions already carries user_id but the join cost on every dashboard query is unnecessary when the dashboard is the high-traffic surface.
- **D8: Natural-key UNIQUE constraint at DB layer** — `UNIQUE (plan_version_id, date, session_index_in_day)`. v1 invariant per Layer 4 §7.12 (max two sessions per day per version); the DB enforces, not just the pydantic validator.

Implementation flow:

1. **Schema migration** — Added to `init_db.py` `_PG_MIGRATIONS` (anchored after the layer0.terrain_gap_rules reclassification). Single `CREATE TABLE IF NOT EXISTS plan_sessions (...)` + 2 indexes (`(user_id, date)` + `(user_id, plan_version_id)`). FK ON DELETE CASCADE so dropping a plan_versions row cleans up sessions atomically (matches the orchestrator's atomic-write-or-rollback per D-64 §6.2).

2. **Repo module** — NEW `plan_sessions_repo.py` (~210 LOC) with the 4 helpers + `_PRIOR_WINDOW_DAYS_BY_TIER` mapping + `VALID_CREATED_VIA` / `VALID_PATTERN` enum tuples + private `_decode_payload` for JSONB dual-path hydration tolerating psycopg2 dict + SQLite-shim JSON string (mirrors `race_events_repo` pattern).

3. **Tests** — NEW `tests/test_plan_sessions_repo.py` (~430 LOC) with 22 tests across 5 classes:
   - `TestAllocatePlanVersionRow` (6): happy-path RETURNING id round-trip + notes JSONB serialization + created_via input validation + pattern input validation + inverted scope-date rejection + RuntimeError on no-RETURNING-row.
   - `TestPersistLayer4Sessions` (3): inserts each session with natural-key columns + payload_json model dump + empty-sessions no-op + user_id from payload threads to every row.
   - `TestLoadPlanSessionsByVersion` (3): JSONB → PlanSession round-trip + JSONB string-path hydration (SQLite-shim) + empty rows returns [].
   - `TestLoadPriorPlanSessionWindow` (9): tier-tied defaults T1=2/T2=7/T3=28 days + days kwarg override + ValueError when both None + ValueError when days<=0 + DISTINCT ON resolver SQL + ORDER BY plan_version_id DESC clause + empty result for first-plan athletes + PlanSession hydration round-trip.
   - `TestTierDefaultMapping` (1): sanity-pin on `_PRIOR_WINDOW_DAYS_BY_TIER` constants.

4. **Test suite** — Container-runnable subset 501 → 523 passing in ~1.6s. No regressions on slice 1/2/3 orchestrator surface or any other layer.

5. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count (1168 → 1190) + current-focus arc summary (refocused on caller-side route arcs); `CARRY_FORWARD.md` Phase 5.2 follow-ons section: substrate entry struck (✅) + D-64 caller-side entry refined to reference the now-available `load_prior_plan_session_window(tier=tier)` helper + plan-create caller-side entry refined similarly; `Upstream_Implementation_Plan_v1.md` §4 new row 5.2.Caller-Prep; this closing handoff.

---

## 3. File-by-file edits

### 3.1 `init_db.py` (MODIFIED, +25 LOC net)

- Added to `_PG_MIGRATIONS` list (anchored after the terrain_gap_rules reclassification migration, before the `_CLOTHING_SEEDS` block):
  - `CREATE TABLE IF NOT EXISTS plan_sessions (...)` — BIGSERIAL PK + plan_version_id BIGINT FK with ON DELETE CASCADE + user_id INTEGER FK + session_id TEXT + date DATE + session_index_in_day SMALLINT CHECK 0/1 + payload_json JSONB + created_at TIMESTAMPTZ DEFAULT NOW() + UNIQUE (plan_version_id, date, session_index_in_day).
  - `CREATE INDEX IF NOT EXISTS plan_sessions_user_date_idx ON plan_sessions (user_id, date)`.
  - `CREATE INDEX IF NOT EXISTS plan_sessions_user_version_idx ON plan_sessions (user_id, plan_version_id)`.
- Inline comment block documents the schema rationale: natural key per Layer 4 §7.11/§7.12, per-day version pointer per D-64 §6.3, user_id denormalization, JSONB payload trade-off, indexing for dashboard + plan-view queries.

### 3.2 NEW `plan_sessions_repo.py` (~210 LOC)

- Module docstring documents the substrate scope (no Flask blueprint, repo only), references Layer 4 §7.11/§7.12 + D-64 §6.2/§6.3, documents the tier-tied lookback default policy + caller-owns-transaction contract.
- Module-level constants: `VALID_CREATED_VIA` (5-value tuple matching plan_versions CHECK constraint) + `VALID_PATTERN` ('A'/'B') + `_PRIOR_WINDOW_DAYS_BY_TIER = {"T1": 2, "T2": 7, "T3": 28}`.
- `allocate_plan_version_row(db, user_id, *, created_via, scope_start_date, scope_end_date, pattern, notes=None) -> int` — Input validation (created_via + pattern + scope dates); INSERT ... RETURNING id; notes JSONB-serialized to a JSON string for the JSONB column.
- `persist_layer4_sessions(db, payload: Layer4Payload) -> None` — Iterates `payload.sessions`; INSERT each row with denormalized natural-key columns + `session.model_dump_json()` as payload_json + user_id from `payload.user_id`. Empty-list no-op.
- `load_plan_sessions_by_version(db, plan_version_id) -> list[PlanSession]` — SELECT payload_json FROM plan_sessions WHERE plan_version_id = ? ORDER BY date, session_index_in_day; dual-path JSONB hydration via `_decode_payload`; reconstruct via `PlanSession.model_validate(...)`.
- `load_prior_plan_session_window(db, user_id, *, today, tier=None, days=None) -> list[PlanSession]` — Lookback resolution (`days` overrides `tier`; both None → ValueError); cutoff window `[today - days, today - 1]` inclusive; SELECT DISTINCT ON (date, session_index_in_day) ... ORDER BY date, session_index_in_day, plan_version_id DESC per D-64 §6.3.
- Private `_decode_payload(raw)` helper — JSONB dual-path normalization (dict pass-through; JSON-string parse; TypeError on neither).

### 3.3 NEW `tests/test_plan_sessions_repo.py` (~430 LOC)

- 22 tests across 5 classes (see §2 narrative step 3 + §4 below for detail).
- `_FakeConn` / `_FakeCursor` / `_FakeRow` fixtures duplicated from `tests/test_layer4_orchestrator.py` pattern with a `committed` flag added so tests can assert "repo does NOT call commit".
- `_make_plan_session(...)` + `_make_layer4_payload(...)` factory helpers for valid PlanSession + Layer4Payload construction across tests (cardio kind with valid CardioBlock + HRTarget; Pattern B plan_refresh shape).

---

## 4. Code / tests

**Test count delta:** 1168 → 1190 in production count (+22 net new tests, all in NEW `tests/test_plan_sessions_repo.py` across 5 classes); 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Container-runnable subset:** 501 → 523 passing in ~1.6s.

Run reproducer:

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py \
                                tests/test_plan_sessions_repo.py
# 523 passed in ~1.6s
```

The +22 new tests:

- `tests/test_plan_sessions_repo.py::TestAllocatePlanVersionRow::*` (6)
- `tests/test_plan_sessions_repo.py::TestPersistLayer4Sessions::*` (3)
- `tests/test_plan_sessions_repo.py::TestLoadPlanSessionsByVersion::*` (3)
- `tests/test_plan_sessions_repo.py::TestLoadPriorPlanSessionWindow::*` (9)
- `tests/test_plan_sessions_repo.py::TestTierDefaultMapping::*` (1)

**No-regression confirmation:** all 50 pre-existing orchestrator tests + 21 locales + 27 race_events + 19 onboarding race_events + 30+ each across layer4 context/payload/hashing/cache + 12 race_week_brief tests pass unchanged. Slice landing is purely additive.

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + all 6+ predecessor handoffs §4); verified by `git stash` round-trip that this slice did NOT introduce or worsen it.

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.2 caller-side substrate** — 3-step verification (executable once D-64 / plan-create / D-63 caller-side routes land + a real orchestrator invocation persists sessions):

**Step 1: Migration applied on Neon.** Run `init_db.py` against the Neon DB. Confirm:
- `\d plan_sessions` shows the table with BIGSERIAL id + plan_version_id BIGINT NOT NULL + user_id INTEGER NOT NULL + session_id TEXT NOT NULL + date DATE NOT NULL + session_index_in_day SMALLINT NOT NULL + payload_json JSONB NOT NULL + created_at TIMESTAMPTZ NOT NULL.
- `\d plan_sessions` shows the UNIQUE constraint on (plan_version_id, date, session_index_in_day).
- `\di plan_sessions*` shows the 2 indexes (user_date_idx + user_version_idx).
- FK ON DELETE CASCADE: `DELETE FROM plan_versions WHERE id=<test_id>` removes all plan_sessions rows pointing to that version.

**Step 2: Repo round-trip against Andy's PGE 2026 context.** From Python REPL (no Flask UI yet):
```python
from datetime import date
from plan_sessions_repo import (
    allocate_plan_version_row,
    persist_layer4_sessions,
    load_plan_sessions_by_version,
    load_prior_plan_session_window,
)
# Allocate a plan_versions row for Andy's PGE 2026 plan
pv_id = allocate_plan_version_row(
    db, andy_user_id,
    created_via="plan_create",
    scope_start_date=date(2026, 4, 1),
    scope_end_date=date(2026, 7, 17),
    pattern="A",
    notes={"manual_verification": True},
)
db.commit()
# Invoke orchestrator (mocked for §5.0; real-LLM in step 3)
result = orchestrate_plan_create(
    db, andy_user_id,
    plan_start_date=date(2026, 4, 1),
    plan_version_id=pv_id,
    cache=Layer4Cache(InMemoryCacheBackend()),
)
persist_layer4_sessions(db, result)
db.commit()
# Load back
loaded = load_plan_sessions_by_version(db, pv_id)
assert len(loaded) == len(result.sessions)
```

Confirm: (a) allocate returns a positive int; (b) persist inserts N rows where N = len(result.sessions); (c) load_plan_sessions_by_version returns all N PlanSession objects ordered by (date, slot); (d) Each loaded PlanSession is equal to its original (via `model_dump()`); (e) Natural-key UNIQUE constraint rejects a second persist call with the same plan_version_id.

**Step 3: Prior-window resolver E2E.** After step 2, fire a T2 refresh against Andy + assert `load_prior_plan_session_window(db, andy_user_id, today=date(2026, 5, 1), tier="T2")` returns sessions from `[2026-04-24, 2026-04-30]` (the 7-day window pre-today). Verify per-day version pointer: insert a NEW plan_versions row with `created_via='plan_refresh_t1'` covering 2026-04-28 + persist 1 session there; re-run `load_prior_plan_session_window` and confirm the new version's row wins for 2026-04-28 (per D-64 §6.3 resolver picks `MAX(plan_version_id)` per slot).

**Real-LLM cost:** ~$0 (repo work; no LLM). Step 2's `orchestrate_plan_create(...)` real-LLM cost only when ANTHROPIC_API_KEY set (~$0.30-$0.50 per cold synthesis on Pattern A's per-phase loop).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward moves

The 3 caller-side route arcs are now unblocked. Recommended order (smallest to largest):

**(a) D-63 caller-side route + `ad_hoc_workout_suggestions` table** — slice 1 (`orchestrate_single_session_synthesize`) E2E-reachability. ~3-4 files: init_db.py migration (`ad_hoc_workout_suggestions` table per D-63 §5.3) + NEW `routes/ad_hoc_workouts.py` (form GET — athlete picks sport + locale or quick_equipment + free-text constraints; POST — allocate suggestion_id + invoke `orchestrate_single_session_synthesize` + persist via `persist_layer4_sessions` + redirect to session view) + new `templates/workouts/single_session_request.html` + new `templates/workouts/single_session_view.html` + tests. **`/plan` gate per Trigger #1** (form copy on the ad-hoc workout request UX). Smallest of the 3 caller-side arcs.

**(b) plan-create caller-side route** — slice 3 E2E-reachability. ~3-4 files: NEW `routes/plan_create.py` (form GET — athlete picks plan_start_date + optional target-race association; POST — allocate plan_versions row via `allocate_plan_version_row(created_via='plan_create', pattern='A')` + invoke `orchestrate_plan_create` + persist via `persist_layer4_sessions` + atomic commit per D-64 §6.2 + redirect to plan view) + new `templates/plans/plan_create.html` + plan-view template (or extend existing v1 plan view) + tests. **`/plan` gate per Trigger #1** (form copy) + **Trigger #5** (error handling for `Layer4ShapeInfeasibleError` HITL routing per spec §3.5). Pairs cleanly with (a) — both can land in one batched session.

**(c) D-64 caller-side route + NL parser glue** — slice 2 E2E-reachability. ~5-7 files: NEW `routes/plan_refresh.py` (refresh-trigger form GET — tier picker T1/T2/T3 + scope dates + nl_text free-text; POST — allocate plan_versions row via `allocate_plan_version_row(created_via='plan_refresh_t<N>', pattern='B' or 'A')` + run NL parser → ParsedIntent + query prior window via `load_prior_plan_session_window(tier=tier)` + invoke `orchestrate_plan_refresh` + persist + atomic commit + redirect) + NEW `nl_parser.py` (D-64 §5 implementation — LLM-backed Sonnet with deterministic cache per `(athlete_id, sha256(nl_text_normalized), parser_prompt_version)` + graceful degradation on API failure per §5.4) + NEW `aidstation-sources/prompts/NLParser_v1.md` (parser prompt body — DEFERRED to its own session per D-64 Decision #12) + tier-picker template + dashboard refresh-trigger card update + tests. **`/plan` gate per Trigger #2 (LLM prompt design — NL parser body)** + **Trigger #1** (form copy on the refresh-trigger card) + **Trigger #5** (route shape — dashboard vs plan-view entry points + redirect-after-refresh UX). Largest of the 3 caller-side arcs; the NL parser prompt-body design is its own substantive session even before route work.

**Recommended batching for the next session:** ship (a) + (b) together — both are smallest and share the `persist_layer4_sessions` substrate. ~6-8 files batched. The D-64 caller-side arc (c) opens a separate prompt-design session per Trigger #2.

### 6.2 Alternative pivots

- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1 + #3 + #5).
- **Layer 3A + 3B caching policy modules at orchestrator level** — with 4 entry points sharing 3A/3B outputs, near-load-bearing. ~4-6 files.
- **Layer 3B None-tolerant kwargs L3B-P-2** consumer migration. ~3-4 files.
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — ~1-2 files; doc-sweep nit from form-refresh C.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.
- **Manual §5.0 walkthrough** of substrate + all 4 orchestrator entry points (once caller-side routes land).
- **Real-LLM Layer 4 regression** parity to plan_create (~$0.30-$0.50 per cold synthesis on Pattern A).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items.
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_PlanSessions_Substrate_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | `plan_sessions` schema with JSONB payload column (not 17-column denormalize) | Andy | Simpler for v1. UNIQUE natural key + 2 indexes give dashboard + plan-view queries the access patterns they need without column proliferation. Denormalize specific fields (e.g., `kind`, `duration_min`) when plan-view queries become load-bearing. |
| **D2** | Repo at repo root: `plan_sessions_repo.py` | Andy | Mirrors `race_events_repo.py` precedent. NOT inside `layer4/` — repos are caller-side per the 5.2 deferral pattern. Layer 4 stays a pure synthesizer; persistence lives outside. |
| **D3** | 4 helpers — `allocate_plan_version_row` + `persist_layer4_sessions` + `load_plan_sessions_by_version` + `load_prior_plan_session_window` | Andy | Minimal set covering the 3 caller-side route arcs' needs. No `update_plan_session` (sessions are immutable per plan_version_id — overrides land via per-day version pointer per D-64 §6.3). No `delete_plan_version` (CASCADE handles cleanup; manual delete is a v2 admin tool). |
| **D4** | Tier-tied default lookback `_PRIOR_WINDOW_DAYS_BY_TIER = {T1: 2, T2: 7, T3: 28}` days + `days` kwarg override | Andy ratified at AskUserQuestion gate | Matches refresh forward-scope shape so the prior window roughly mirrors what's about to change. T1 (2-day refresh scope) → 2-day lookback; T2 (week scope) → 7-day lookback; T3 (28-day cross-phase scope) → 28-day lookback. `days` kwarg lets callers override for cases like race_week_brief wanting a 6-week window irrespective of tier. ValueError when both None forces caller to be explicit. Picked over Fixed-2-week (insufficient for T3) and Required-no-default (more boilerplate at callsites). |
| **D5** | Caller owns transaction per D-64 §6.2 — `persist_layer4_sessions` does NOT call `db.commit()` | Andy | D-64 §6.2 mandates atomic write boundaries; route handler manages the transaction spanning `allocate_plan_version_row` + `orchestrate_*` + `persist_layer4_sessions`. Repo helpers compose; they don't decide commit boundary. |
| **D6** | 22 tests across 5 classes | Andy | Full coverage of all 4 helpers + the tier-default mapping pin. AllocatePlanVersionRow has the most tests (6) because input validation is load-bearing; LoadPriorPlanSessionWindow has 9 because the tier-tied default mapping + days override + window math + DISTINCT ON resolver each need anchors. |
| **D7** | user_id denormalized into `plan_sessions` for fast (user_id, date) lookups | Andy | plan_versions already carries user_id but the join cost on every dashboard query is unnecessary. The dashboard "show me today's sessions" query is `SELECT ... FROM plan_sessions WHERE user_id=? AND date=?`; denormalizing eliminates a join. Cost = 4 bytes per row + cascade-cleanup discipline via FK. |
| **D8** | Natural-key UNIQUE constraint at DB layer — `UNIQUE (plan_version_id, date, session_index_in_day)` | Andy | Layer 4 §7.12 invariant ("max two sessions per day" + natural key) enforced at DB layer, not just at pydantic. INSERT conflict → caller's transaction rolls back atomically per D-64 §6.2. Defense-in-depth against orchestrator bugs that emit duplicate slots. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` has new `plan_sessions` table migration | ✅ `grep -n "CREATE TABLE IF NOT EXISTS plan_sessions" init_db.py` returns line 1566 |
| `init_db.py` has new `plan_sessions_user_date_idx` index migration | ✅ `grep -n "plan_sessions_user_date_idx" init_db.py` |
| `init_db.py` has new `plan_sessions_user_version_idx` index migration | ✅ `grep -n "plan_sessions_user_version_idx" init_db.py` |
| NEW `plan_sessions_repo.py` exists with 4 helpers | ✅ `grep -n "^def allocate_plan_version_row\|^def persist_layer4_sessions\|^def load_plan_sessions_by_version\|^def load_prior_plan_session_window" plan_sessions_repo.py` returns 4 lines |
| `plan_sessions_repo.py` exports `_PRIOR_WINDOW_DAYS_BY_TIER = {T1: 2, T2: 7, T3: 28}` | ✅ `grep -n "_PRIOR_WINDOW_DAYS_BY_TIER" plan_sessions_repo.py` |
| NEW `tests/test_plan_sessions_repo.py` has 5 test classes | ✅ `grep -c "^class Test" tests/test_plan_sessions_repo.py` returns 5 |
| NEW `tests/test_plan_sessions_repo.py` has 22 tests | ✅ `grep -c "def test_" tests/test_plan_sessions_repo.py` returns 22 |
| All 22 new tests pass | ✅ `pytest tests/test_plan_sessions_repo.py -q` reports 22 passed |
| Container-runnable subset green at 523 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py tests/test_plan_sessions_repo.py` reports 523 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has new row 5.2.Caller-Prep → ✅ Shipped 2026-05-20 | ✅ `grep -n "5.2.Caller-Prep.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 caller-side substrate handoff | ✅ `grep -n "Phase_5_2_CallerSide_PlanSessions_Substrate" aidstation-sources/CURRENT_STATE.md` |
| `CURRENT_STATE.md` tests count flipped 1168 → 1190 | ✅ `grep -n "1190 green" aidstation-sources/CURRENT_STATE.md` |
| `CARRY_FORWARD.md` Caller-side substrate entry struck (✅ Shipped) | ✅ `grep -n "Caller-side persistence substrate.*Shipped 2026-05-20" aidstation-sources/CARRY_FORWARD.md` |

---

## 9. Files shipped this session

**Substantive (3 files; well under 5-file ceiling):**

1. MODIFIED `init_db.py` (+25 LOC net) — new `CREATE TABLE IF NOT EXISTS plan_sessions (...)` migration + 2 indexes in `_PG_MIGRATIONS`; inline comment block documents schema rationale.
2. NEW `plan_sessions_repo.py` (~210 LOC) — 4 helpers (`allocate_plan_version_row` + `persist_layer4_sessions` + `load_plan_sessions_by_version` + `load_prior_plan_session_window`) + `_PRIOR_WINDOW_DAYS_BY_TIER` tier-tied default mapping + private `_decode_payload` JSONB hydration helper + `VALID_CREATED_VIA` / `VALID_PATTERN` enum tuples.
3. NEW `tests/test_plan_sessions_repo.py` (+~430 LOC) — 22 tests across 5 classes; `_FakeConn` / `_FakeCursor` / `_FakeRow` fixtures with `committed` flag; `_make_plan_session` + `_make_layer4_payload` factories.

**Bookkeeping (4 files):**

4. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flip + tests count + current-focus arc refocused on caller-side route arcs.
5. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Phase 5.2 follow-ons section: substrate entry struck (✅) + D-64/plan-create caller-side entries refined to reference the now-available repo helpers.
6. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row 5.2.Caller-Prep.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_CallerSide_PlanSessions_Substrate_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- "Caller-side persistence substrate (`plan_sessions` table + repo)" — NEW entry, struck (✅ Shipped 2026-05-20).
- "D-64 caller-side route" entry refined to note substrate now landed + cite `load_prior_plan_session_window(tier=tier)` as the prior-window query path. NL parser prompt body still deferred per Trigger #2.
- "plan-create caller-side route" entry refined to note substrate now landed + cite `allocate_plan_version_row` + `persist_layer4_sessions` as the composition path.

Phase 5.2 caller-side substrate complete; D-63 + D-64 + plan-create caller-side route arcs all unblocked. **Next session: smallest is D-63 caller-side; largest is D-64 (gated on NL parser prompt-body design session). plan-create caller-side fits between.** Recommended batching: (D-63 + plan-create) together — both small, share substrate.

---

**End of handoff.**
