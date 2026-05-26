# §6.2 Cron-Driven Background Plan Generation — Closing Handoff

**Session:** Executed the §6.2 forward move (architect-recommended next per the predecessor roadmap, Andy decision #3): factored the progress-screen poller's generation body into a shared `routes/plan_create._advance_plan_generation(db, uid, plan_version_id)` and added a token-gated Vercel cron (`GET /plans/v2/cron/generate-pending`) that advances bounded `generation_status='generating'` rows by one resumable pass each — so a plan finishes even with the create tab closed. Promoted the `CRON_SECRET` Bearer check to a shared `routes.auth.cron_authorized()`.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_Layer4_CallerDedupe_SiblingRouteCatches_2026_05_26_Closing_Handoff_v1.md` (§6.1 — 5 Layer 4 callers onto `invoke_tool_call` + sibling-route Layer3 catches, PR #175 `cff6437`)
**Branch:** `claude/compassionate-davinci-DgsIp`
**Status:** 5 substantive files (`routes/plan_create.py`, `routes/auth.py`, `routes/nudges.py`, `app.py`, `vercel.json`) + 1 test file + bookkeeping. Andy approved the full §6.2 scope (single PR, tests included). Full suite **1709 passed / 16 skipped**.

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor §8) | Anchor | Result |
|---|---|---|
| `grep -rn "messages.create" layer4/*.py` → none | grep | ✅ none |
| 5 Layer 4 callers delegate to `invoke_tool_call` | grep | ✅ 1 each |
| `Layer3AOutputError` caught in `routes/plan_refresh.py` + `routes/ad_hoc_workouts.py` | grep | ✅ present |
| Full suite → 1697 / 16 skipped | pytest (fresh `/tmp/venv`) | ✅ baseline reproduced before edits |
| Branch even with `origin/main` at PR #175 `cff6437` | `git log` | ✅ clean, working tree clean |
| `./scripts/verify-handoff.sh` file-existence sweep | script | ✅ all green |

**Reconciliation note:** clean — no drift. Branch `claude/compassionate-davinci-DgsIp` was harness-pinned and already even with `origin/main` at `cff6437`, the correct base (no `reset --hard` needed).

---

## 2. Session narrative

Andy linked the predecessor handoff and said "lets work." Ran the first-session checklist (CLAUDE.md): read CLAUDE.md / CURRENT_STATE / CARRY_FORWARD §5.0 / PR_Verification_Status / the predecessor handoff, ran `verify-handoff.sh`, spot-checked the §8 anchors. State was clean; both CURRENT_STATE and the handoff named **§6.2 cron-driven background generation** as the next forward move (Andy decision #3).

Scope gate (AskUserQuestion): Andy chose **build §6.2 in full** (the `_advance_plan_generation` refactor + the guarded cron endpoint + the `vercel.json` cron registration, single PR, tests). No stop-and-ask trigger fired — this is request-shape/route plumbing on existing columns (no schema change → not Trigger #3), the architecture was decided by Andy (roadmap §6.2), and there's no prompt-body or HITL work.

Implementation was a straight extraction of the proven poller body into a shared engine, plus a cron route mirroring the `routes/nudges.py` `CRON_SECRET` precedent. The one small judgment call: promote `_cron_authorized` to a shared `routes.auth.cron_authorized()` rather than import a leading-underscore private across modules or duplicate the constant-time compare.

---

## 3. File-by-file edits

### 3.1 `routes/plan_create.py` (modified)
- **New `_advance_plan_generation(db, uid, plan_version_id) -> dict`** — the shared generation engine, factored out of the old `generate_plan` body verbatim. Loads the row (scoped to `uid`); short-circuits an already-terminal row (`ready`/`failed`) without re-running the cone; else runs one `orchestrate_plan_create` pass; on a typed upstream error (`OrchestrationError` / `Layer4InputError|Layer4OutputError` / `Layer3AOutputError|Layer3BOutputError`) flips `failed` via `_mark_plan_failed`; on success does the DELETE-guarded persist + flips `ready`. Returns a **view-agnostic** outcome dict: `{"status": "not_found"}` / `{"status": "ready"}` / `{"status": "failed", "error": <msg>}` (no URLs — callers own view concerns).
- **`generate_plan` route is now a thin wrapper** — calls the engine, maps `not_found`→`abort(404)`, `ready`→`{"status":"ready","redirect": _view_plan_url(...)}`, `failed`→the stored error JSON. Behavior + poller JSON unchanged.
- **Removed `_terminal_status_response`** — its terminal-status mapping is subsumed by the engine's short-circuit (the route now adds the redirect URL).
- **New `cron_generate_pending` route** (`GET /plans/v2/cron/generate-pending`) — `cron_authorized()` gate → 401; selects up to `_CRON_ADVANCE_BATCH` (=5) `generation_status='generating'` rows `ORDER BY created_at ASC`; advances each via `_advance_plan_generation(db, row.user_id, row.id)` (each row under its own owner's uid, committed independently inside the engine); returns `{advanced, ready, failed}`.
- New module constant `_CRON_ADVANCE_BATCH = 5`; import widened to `from routes.auth import cron_authorized, current_user_id`.

### 3.2 `routes/auth.py` (modified)
New shared **`cron_authorized() -> bool`** (+ `import hmac`) — the `Authorization: Bearer $CRON_SECRET` constant-time check, lifted verbatim from `routes/nudges.py._cron_authorized`. Fails closed when `CRON_SECRET` is unset. The natural home (auth helpers live here alongside `current_user_id`).

### 3.3 `routes/nudges.py` (modified)
Dropped the local `_cron_authorized` + its now-unused `import hmac` / `import os`; imports `cron_authorized` from `routes.auth` and calls it in `scan_connect_provider_14d`. No behavior change (same check, one home).

### 3.4 `app.py` (modified)
Added `'plan_create.cron_generate_pending'` to `_AUTH_EXEMPT_ENDPOINTS` (Vercel Cron carries no session cookie; auth is the Bearer header verified in-route). Reworded the adjacent comment to name `routes.auth.cron_authorized`.

### 3.5 `vercel.json` (modified)
Second cron entry: `{ "path": "/plans/v2/cron/generate-pending", "schedule": "* * * * *" }` (every minute — a backstop; tunable). The existing daily nudge cron is unchanged.

### 3.6 `tests/test_routes_plan_create.py` (modified)
- Removed `TestTerminalStatusResponse` (4 cases — the function is gone).
- Added **`TestAdvancePlanGeneration`** (8): not_found; ready/failed short-circuit (no cone run, stored-error + fallback); generating→ready (asserts orchestrate args, persist, DELETE-guard, status flip, one commit); orchestration/Layer4/Layer3 typed errors → failed with the mapped message.
- Added **`TestCronAuthorized`** (5): no-secret fails closed; correct token authorized; wrong token / missing header / wrong scheme rejected (via a throwaway `Flask(__name__).test_request_context`).
- Added **`TestCronGeneratePending`** (3): unauthorized→401; advances two generating rows under their own user ids + tallies `{advanced:2, ready:1, failed:1}` + asserts the `generating` filter + batch LIMIT; empty set is a `{0,0,0}` no-op (via a minimal Flask app + the `bp` blueprint + monkeypatched module globals).

---

## 4. Code / tests

Full suite **1709 passed / 16 skipped** in a fresh `/tmp/venv` (1697 pre-session → **+12**: +16 new cases across the three new classes, −4 the removed `TestTerminalStatusResponse`; nothing else removed). `tests/test_nudges.py` still green after the `cron_authorized` move (it never referenced `_cron_authorized`).

---

## 5. Manual §5.0 verification steps

Appended to `CARRY_FORWARD.md` (Manual §5.0 walkthrough, "Cron-driven background plan generation — §6.2"). The migration + 300s function duration are already applied (PR #173 owed actions, done by Andy). **The one owed action is a redeploy** so Vercel registers the new cron from `vercel.json` (`CRON_SECRET` already set, PR9). The walk:
1. **Auth.** `curl .../plans/v2/cron/generate-pending` with no header → **401**; with `-H "Authorization: Bearer $CRON_SECRET"` → **200** + `{advanced, ready, failed}`. Wrong token / `Basic` scheme → 401.
2. **Tab-closed completion.** Submit `/plans/v2/new`, then close the tab at the progress screen; within ~1–2 min the cron advances the row to `ready` (resuming from `layer4_cache` each pass); reopen `/plans/v2/<id>` and confirm the rendered plan.
3. **Tab-open still works.** Repeat leaving the progress screen open; it still redirects to the plan (poller + cron race harmlessly — whichever finishes marks `ready`, the other sees the terminal row and no-ops).
4. **Failure path.** A typed upstream error increments the cron's `failed` tally + leaves `generation_status='failed'`; the progress screen (if open) shows the graceful failure panel — no 500 either way.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — §6.3 email + in-app notifications
Per the predecessor roadmap (Andy decision #4). On terminal status in **`_advance_plan_generation`** — now the single terminal-status hook for both the poller and the cron — send a "plan ready" / "plan failed" email via `email_helper.py` (`send_email`, gated by `email_configured()`) + surface a dashboard status badge reading `plan_versions.generation_status`. **Guard double-send:** the poller and the cron can both reach a row near-simultaneously, and the engine short-circuits already-terminal rows — so fire the notification only on the *transition into* `ready`/`failed` (e.g. make the status-flip `UPDATE ... WHERE generation_status = 'generating'` and notify only when it actually updated a row, or add a `notified_at` column). Best done as the one terminal-status hook inside `_advance_plan_generation` so both paths notify once through the same code.

### 6.2 Alternative pivots / residuals
- **Cron schedule tuning.** `* * * * *` (every minute) is a responsive backstop on Pro. If cost matters with more athletes, widen it; on Hobby it would cap at daily. Not load-bearing — the progress page still polls for fast feedback when open.
- **Sibling routes still synchronous** (carried from §6.1): `routes/plan_refresh.py` + `routes/ad_hoc_workouts.py` run their cones inline; if those time out they'll want the same async progress-screen + resumable treatment plan_create got in PR #173. Not triggered yet.
- **Seam-review / final-validator caching** (residual from PR #173): the Layer 4 tail isn't individually cached, so it re-runs whole on each resume. Moot on Pro (300s) unless a single unit can't fit the window.

### 6.3 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items (incl. this session's §5.0 walk entry).
4. This handoff.
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Build §6.2 in full as one PR (engine refactor + guarded cron + `vercel.json` cron) | Andy | The pieces are small + tightly coupled; splitting the cron registration off would just cost a second cycle. |
| 2 | Promote `_cron_authorized` → shared `routes.auth.cron_authorized()` | Claude | Reuse the vetted constant-time Bearer check from one home rather than import a `_private` across modules or duplicate a security-sensitive compare. `routes/nudges.py` now imports it; no behavior change. |
| 3 | `_advance_plan_generation` returns a view-agnostic outcome dict; the route adds the redirect URL | Claude | The cron has no view/URL; keeping URLs out of the engine lets both callers share it cleanly. The route stays thin; the old `_terminal_status_response` (route-shaped) is subsumed. |
| 4 | Cron advances a bounded batch (`_CRON_ADVANCE_BATCH=5`) per fire, each row committed independently | Claude | Bounds one invocation's wall-clock under the function-duration cap; a pass cut at the timeout keeps the rows it already finished; remaining rows roll to the next fire. |
| 5 | Schedule `* * * * *` (every minute) | Claude | A responsive backstop for tab-closed completion; idempotent + token-gated so frequent firing is safe. Tunable; flagged in §6.2. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -rn "_terminal_status_response\|_cron_authorized"` → none | ✅ |
| `def cron_authorized` in `routes/auth.py`; called in `routes/nudges.py` + `routes/plan_create.py` | ✅ |
| `_advance_plan_generation` + `cron_generate_pending` + `_CRON_ADVANCE_BATCH` in `routes/plan_create.py` | ✅ |
| `'plan_create.cron_generate_pending'` in `app.py` `_AUTH_EXEMPT_ENDPOINTS` | ✅ |
| `/plans/v2/cron/generate-pending` cron in `vercel.json` (valid JSON) | ✅ |
| `py_compile` the 5 substantive files + the test file | ✅ |
| Full suite `pytest tests/` → 1709 passed / 16 skipped | ✅ (fresh `/tmp/venv`) |
| Working tree clean after commit | ✅ git status |

---

## 9. Files shipped this session

**Substantive (5 files):**
1. `routes/plan_create.py`
2. `routes/auth.py`
3. `routes/nudges.py`
4. `app.py`
5. `vercel.json`

**Tests:**
6. `tests/test_routes_plan_create.py`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Manual §5.0 walkthrough: added the 4-step §6.2 walk (auth; tab-closed completion; tab-open still works; failure tally) + the **owed redeploy** note; count delta `+1`.

---

**End of handoff.**
