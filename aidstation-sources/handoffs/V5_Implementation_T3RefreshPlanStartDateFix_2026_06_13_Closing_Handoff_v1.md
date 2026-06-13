# V5 Implementation — T3 plan-refresh fix: wire `plan_start_date` through the async path (#570)

**Date:** 2026-06-13
**Branch:** `claude/plan-65-refresh-r8tclv`
**PR:** [#569](https://github.com/ahorn885/exercise/pull/569) — squash-merged to `main`
**Issue:** [#570](https://github.com/ahorn885/exercise/issues/570) (T3 refresh `plan_start_date_missing`) — closed by this PR.

> **Read order (Rule #13):** this handoff → `CURRENT_STATE.md` top entry → `CARRY_FORWARD.md`. This session ran the live T3-refresh verify owed by the #566/#208 handoff, found that **T3 refresh had never actually worked**, fixed it, and shipped. The #208 async/resumable plumbing itself is now confirmed sound on real prod traffic.

---

## 1. What this session was

The #566 handoff (#208 async/resumable refresh) left one owed item: a live verify of a refresh on prod — "shows the progress screen, finishes via the cron/poller, lands on the diff view, and (for a T3 cross-phase) survives without a 504." Andy ran a **T3** refresh of pv=65; I watched it via the Vercel runtime-log MCP and the token-gated diag endpoint. The verify did its job: it surfaced a real, shipping bug.

## 2. What the watch found (the split result)

- **#208 async plumbing — PASS (confirmed on real traffic).** `POST /plans/v2/refresh → 302` (allocates the `generating` row pv=66, freezes inputs, no inline synthesis), `GET /plans/v2/66/progress → 200` (shared progress screen), then background passes via **both** the progress poller (`POST /66/generate`) and the every-minute cron (`/plans/v2/cron/generate-pending`). After the tab was closed the **cron solo-drove** the generation; the D-77 advance-lock guard correctly bounced overlapping cron fires (`advance lock held elsewhere`). No 504. It failed **gracefully** via the single terminal `_mark_plan_failed` choke point with a clean user-facing error — exactly the resilience the slice added.

- **T3 refresh synthesis — BROKEN.** pv=66 reached `generation_status=failed`, `generation_error=plan_start_date_missing`:
  ```
  layer4.errors.Layer4InputError: plan_start_date_missing: tier='T3' requires
  plan_start_date non-None per Layer4_Spec.md §3.2 (Step 4d amendment) —
  phase_structure_from_3b() needs the parent plan's start date to compute phase boundaries
    orchestrator.py:1071 orchestrate_plan_refresh
    → cached_wrappers.py:273 llm_layer4_plan_refresh
    → plan_refresh.py:480 _validate_inputs → raise Layer4InputError
  ```

**Method note (Rule #14, again):** the failure was emitted via `print()`, which Vercel classifies as `info` — so the runtime-log MCP `level=error` sweep showed it clean and a naive read of "cron went idle" looked like `ready`. The **token-gated `/admin/plan/<id>/diag`** endpoint gave the real fault (`created_via`, `generation_status`, `generation_error`, `generation_traceback`). Diag token is the live `DIAG_TOKEN` in §6.1.1 of the 2026-05-31 DiagAuthGate handoff. **Direct container curl to prod is egress-blocked** ("Host not in allowlist") — fetch via the Vercel MCP `web_fetch_vercel_url` tool (this still works).

## 3. Root cause

`routes/plan_refresh.py` **never supplied `plan_start_date`** to `orchestrate_plan_refresh`. `run_refresh_orchestration` didn't pass it, and the frozen-input `build_refresh_advance_ctx` it reads from didn't carry it. T1/T2 ignore `plan_start_date`; only T3 requires it (Step 4d §3.2 — `phase_structure_from_3b()` anchors phase boundaries on the plan's real start). `git log -S plan_start_date -- routes/plan_refresh.py` returns nothing → the string was never in that file, so **this is not a #208 regression** — T3 refresh had never worked end-to-end; the live verify was the first real T3 attempt.

## 4. The fix (PR #569 — 2 files)

`routes/plan_refresh.py`:
- New **`_resolve_plan_start_date(db, user_id, parent_id)`** — walks `refresh_parent_version_id` back to the **root `plan_create` row** and returns its `scope_start_date`. The plan's TRUE start, **not** the refresh row's own `scope_start_date` (that's the refresh *window*; using it would let synthesis run but silently mis-place every phase boundary). A `seen`-set guards cyclic parent pointers; an unresolvable chain returns `None` so the T3 validator still raises the explicit error rather than anchoring on a wrong date.
- `build_refresh_advance_ctx` → adds `'plan_start_date'` (resolved from the parent chain) to the frozen-input ctx.
- `run_refresh_orchestration` → forwards `plan_start_date=ctx['plan_start_date']` into `orchestrate_plan_refresh`.

**Orthogonality (answers Andy's "are we only refreshing future data?"):** `plan_start_date` (past — the plan's real start) and `refresh_scope_start/end` (future window, derived from `today` via `_resolve_scope_dates`) are independent. Only phases overlapping the future scope are re-synthesized (`plan_refresh.py` `_route_t3_cross_phase…`: "phases outside the scope keep [their sessions]"). The past start date only anchors the periodization calendar; it never widens the write window. Refresh never rewrites past dates.

## 5. Verification

- Full suite **2362 passed / 30 skipped** locally; CI green on PR #569 (Python unit, JS harness, Layer 0 gate, Vercel preview ✅; Real-LLM smoke skipped).
- New tests (`tests/test_routes_plan_refresh.py`): `TestResolvePlanStartDate` (immediate root / chain-walk to root / `None` parent / missing row / cycle guard), `TestBuildRefreshAdvanceCtx.test_threads_resolved_plan_start_date`, `TestRunRefreshOrchestration.test_forwards_plan_start_date` (the exact regression guard).
- **Owed — live re-verify (Andy's hands):** re-run a **T3** refresh on prod post-merge → confirm the new pv reaches `generation_status=ready` with a phase-correct `total_sessions` (read via the diag token). The other tiers (T1/T2) were never affected.

## 6. Owed / next move

- **No Neon migration owed** — code-only fix; the `refresh_*` columns are already applied (#566/#567, verified 2026-06-13). Owed-deploy list stays drained.
- **Live T3 re-verify** (above) is the only follow-up for this fix.
- **Next live candidates** (unchanged): the **#541/#542/#543** plan-quality batch (shallow strength / low-protein macros / structured health conditions), then the **compliance build-out** (epics #353/#355/#356/#359) — the long pole for general availability. #540's only residual is the Track-3-gated layer0 column lift (parked).

## 6.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry is this PR (#569); current focus = #541/#542/#543 + compliance.
3. `CARRY_FORWARD.md` — rolling carry-state (owed-deploys drained; the one open item from this session is the live T3 re-verify).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

**Diag-token recipe (used this session, worth keeping):** read any plan's generation state past the app login wall via the Vercel MCP — `web_fetch_vercel_url("https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=<DIAG_TOKEN>")` → JSON with `created_via` / `generation_status` / `generation_error` / `generation_traceback` / `total_sessions`. Direct container curl is egress-blocked; the MCP fetch is the path. The runtime-log MCP `level` filter misses `print()`-based failures (they're `info`) — the diag endpoint is authoritative.

## 7. Stop-and-asks this session

- **Fix approach (which date sources `plan_start_date`)** was surfaced to Andy before implementing — chose **root create row** (robust to refresh-of-a-refresh chains) over the immediate parent. No prompt/schema/HITL change, so no other trigger fired.

## 8. §8 anchor table (Rule #10)

| Area | Path | Anchor / check |
| --- | --- | --- |
| Resolver (new) | `routes/plan_refresh.py` | `def _resolve_plan_start_date(` — walks `refresh_parent_version_id` to root create row |
| Ctx threading | `routes/plan_refresh.py` | `build_refresh_advance_ctx` returns `'plan_start_date'` |
| Orchestration passthrough | `routes/plan_refresh.py` | `run_refresh_orchestration` → `orchestrate_plan_refresh(..., plan_start_date=ctx['plan_start_date'])` |
| T3 input gate (unchanged) | `layer4/plan_refresh.py:479` | `if tier == "T3" and plan_start_date is None: raise … plan_start_date_missing` |
| Tests | `tests/test_routes_plan_refresh.py` | `TestResolvePlanStartDate`, `test_threads_resolved_plan_start_date`, `TestRunRefreshOrchestration` |
