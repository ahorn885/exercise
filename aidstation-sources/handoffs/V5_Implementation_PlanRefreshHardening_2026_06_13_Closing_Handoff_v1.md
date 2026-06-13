# V5 Implementation — Plan-refresh hardening: dashboard sessions, shared injury renderer (#555), refresh terrain feasibility (#557), async/resumable refresh (#208)

**Date:** 2026-06-13
**Branch:** `claude/sleepy-rubin-5nilih`
**PR:** [#566](https://github.com/ahorn885/exercise/pull/566) — squash-merged to `main`
**Issues:** [#555](https://github.com/ahorn885/exercise/issues/555) (injury-accommodation render), [#557](https://github.com/ahorn885/exercise/issues/557) (refresh terrain feasibility), [#208](https://github.com/ahorn885/exercise/issues/208) (async/resumable refresh) — all closed by this PR. [#540](https://github.com/ahorn885/exercise/issues/540) refresh tail (#557) now also done.

> **Read order (Rule #13):** this handoff → `CURRENT_STATE.md` top entry → `CARRY_FORWARD.md`. The plan-refresh feature is now production-shaped: it reuses the create path's resumable generation infra rather than its own synchronous one, and the two synthesis prompts share their renderers so they can't drift.

---

## 1. What this session was

Started as a single bug ("today's sessions don't show on the dashboard"), expanded — at Andy's direction ("do all of them in the listed order") — into a four-part hardening of the plan-**refresh** path, ranked A→D by effort. The throughline: make refresh *capitalise on the hardened plan-gen process and not reintroduce failure points*.

## 2. What shipped (PR #566, four commits + a `main` merge)

- **A — dashboard v2 sessions + plan-page Refresh button.** The dashboard Today/Tomorrow cards only queried the legacy `plan_items`/`training_plans` model, so an active v2 plan (`plan_versions`/`plan_sessions`, e.g. pv=65) showed *"No session scheduled."* New `plan_sessions_repo.load_scheduled_sessions_for_window` resolves "what's scheduled" over a date window via the **D-64 §6.3 per-day version pointer** (`DISTINCT ON (date, slot) ORDER BY plan_version_id DESC`), restricted to **active** versions (`generation_status='ready'`, not archived/completed; deliberately NOT filtering `superseded_at` so a partial refresh's parent keeps its non-refreshed tail). `routes/dashboard._v2_session_card` normalises each `PlanSession` into the legacy card shape (`is_v2` flips links to the v2 view); `templates/dashboard.html` `wk_url()` macro + read-only "View" for v2 (no fabricated complete/skip/.FIT). Added the missing **Refresh plan** button to `templates/plan_create/view.html`.

- **B — shared injury-accommodation renderer; fix #555.** Both the create (`per_phase._format_active_injuries`) and refresh (`plan_refresh_t1._format_active_injuries`) prompts had their own copy that rendered only the modality *type name* — dropping params + rationale (#555). New **`layer4/injury_render.py`** is the single source of truth (`format_modality` surfaces each of the 6 `AccommodationModality` variants' params + rationale; `format_active_injuries` owns the EXCLUDE/ACCOMMODATE line shape, caller passes empty-state copy). Both paths delegate → cannot drift again.

- **C — terrain feasibility into refresh (#557, mirrors create #540).** `orchestrate_plan_refresh` now computes terrain feasibility with the same `_build_terrain_feasibility(db, user_id, cone)` the create path uses, folds its hash into the `plan_refresh` cache key (`hashing.plan_refresh_key` + `cached_wrappers.llm_layer4_plan_refresh_cached`), and all three tier prompts (T1/T2/T3 `render_user_prompt`) render the **shared** `per_phase._format_session_feasibility` block. T3 cross-phase threads `terrain_feasibility` through `_route_t3_cross_phase_to_pattern_a` → `synthesize_pattern_a_for_refresh` → `_run_pattern_a_engine` (which already consumed it).

- **D — async/resumable refresh (#208).** Refresh ran the whole Layer-4 synthesis inline in the POST (no progress screen, no resumable passes), so a heavy T3 cross-phase (Pattern A) refresh could blow the serverless timeout. The POST now allocates a `generating` `plan_versions` row, **freezes** the refresh inputs on it, and redirects to the **shared** progress screen; the existing cron + poller drive it. `plan_create._advance_plan_generation_locked` dispatches on `created_via` (`plan_refresh_t*` → `plan_refresh.run_refresh_orchestration`, else create) inside the *same* budget/stall/retry envelope — create rows take the byte-for-byte identical path. Post-`ready`, refresh writes its success refresh-log (diff vs parent + attribution); the single terminal `_mark_plan_failed` choke point writes a best-effort failure refresh-log for refresh rows. Ready/failed redirects are `created_via`-aware (refresh → its diff view).

  **Determinism guard (the #202 lesson, applied):** the NL note is parsed **once** at request time and stored as `refresh_parsed_intent_json`; every background pass reads it back verbatim — a re-parse would drift `parsed_intent` → drift the `plan_refresh` cache key → non-convergence.

## 3. Schema (part D) — APPLIED on Neon by Andy (2026-06-13)

Six idempotent `plan_versions` ALTERs in `init_db._PG_MIGRATIONS` (auto-applied at boot; Andy also applied by hand and verified all six present): `refresh_nl_text`, `refresh_parent_version_id`, `refresh_triggered_by_ad_hoc_id`, `refresh_cap_overridden`, `refresh_parsed_intent_json`, `refresh_used_degraded`. **No backfill** — existing rows are all `plan_create` (the columns stay NULL/false, which the code reads as "not a refresh row").

## 4. Verification

- Full suite **2355 passed / 30 skipped** locally; CI green on `main` merge base (Python unit, JS harness, Layer 0 integrity gate, Vercel preview all ✅; Real-LLM smoke skipped).
- New tests: `_v2_session_card` + the window read (`test_routes_dashboard.py`); the shared injury renderer incl. the #555 ACCOMMODATE contract (`test_layer4_injury_render.py`); refresh terrain-block render + `plan_refresh_key` terrain fold (`test_layer4_terrain_feasibility_wiring.py`, `test_layer4_plan_refresh.py`); `build_refresh_advance_ctx` frozen-intent/no-reparse + `write_refresh_failure_log` (`test_routes_plan_refresh.py`); create-advance doubles updated for the new SELECT columns (`test_routes_plan_create.py`).
- **Owed — live verify (Andy's hands):** run a refresh from the dashboard/plan page on prod → confirm it shows the progress screen, finishes via the cron/poller, lands on the diff view, and (for a T3 cross-phase) survives without a 504.

## 5. Owed / next move

- **No Neon migration owed** — part D's columns are applied. The wider owed-deploy list was reconciled in #567 (#531/#504/#336/0002 all confirmed applied); `craft_discipline_aliases` verified healthy (14 active / single version).
- **#540 tail:** with #557 done, the only residual under #540 is the **Track-3-gated layer0 column lift** of the discipline→terrain map (currently a Python constant in `session_feasibility.py`). Not a live surface — fine to close #540 or keep it parked on that residual.
- **Next live candidates** (unchanged from the predecessor): the **#541/#542/#543** plan-quality batch (shallow strength / low-protein macros / structured health conditions), then the **compliance build-out** (epics #353/#355/#356/#359) which is the long pole for general availability.

## 6.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry is this PR (#566); current focus = #541/#542/#543 + compliance.
3. `CARRY_FORWARD.md` — rolling carry-state (owed-deploys list now fully reconciled; no Neon migration owed).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

## 6. Stop-and-asks this session

- **#555 prompt-body change** was Trigger #1 (prompt edit) — folded into the shared renderer rather than a one-path patch, so it's resolved for both create + refresh at once.
- **Part D scope** (async refresh) was confirmed with Andy as architecturally significant before building: chose **full mirror on PR #566** over targeted-T3 / defer.

## 7. §8 anchor table (Rule #10)

| Area | Path |
| --- | --- |
| A — window read | `plan_sessions_repo.py` (`load_scheduled_sessions_for_window`) |
| A — dashboard | `routes/dashboard.py` (`_v2_session_card`), `templates/dashboard.html`, `templates/plan_create/view.html` |
| B — shared renderer (new) | `layer4/injury_render.py` |
| B — delegations | `layer4/per_phase.py`, `layer4/plan_refresh_t1.py` |
| C/D — refresh wiring | `layer4/orchestrator.py`, `layer4/cached_wrappers.py`, `layer4/hashing.py`, `layer4/plan_refresh.py`, `layer4/plan_refresh_t2.py`, `layer4/plan_refresh_t3.py`, `layer4/plan_create.py` |
| D — schema | `init_db.py` |
| Tests | `tests/test_routes_dashboard.py`, `tests/test_layer4_injury_render.py`, `tests/test_layer4_terrain_feasibility_wiring.py`, `tests/test_layer4_plan_refresh.py`, `tests/test_routes_plan_create.py` |
