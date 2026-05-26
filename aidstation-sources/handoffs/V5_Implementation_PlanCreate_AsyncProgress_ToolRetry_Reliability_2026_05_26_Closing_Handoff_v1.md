# Plan-Create Reliability — Async Progress Screen + 3A/3B Tool-Call Retry — Comprehensive Closing Handoff

**Session:** Andy drove the plan-create path end-to-end against the real Anthropic API for the first time and hit two distinct failures in sequence; both are fixed here, and the remaining work is scoped + decided. (1) The *still-live* "internal server error after a long wait" was a **Vercel function timeout** — the POST ran the whole multi-minute LLM cone synchronously. Fixed by **async, resumable, stepped generation behind a progress/thinking screen** (PR #173, merged). (2) With that live, the next live run failed `Athlete evaluation failed (schema_violation)` — under extended thinking the tool is offered via `auto` (a forced tool is incompatible with thinking), so the model can decline it and emit no `tool_use` block. Fixed by a **forced-tool retry fallback** in the shared invocation (PR #174). Andy then chose the forward plan for the remaining gaps: **cron-driven background generation** + **email & in-app notifications**, and **keep extended thinking** (retry, don't drop it).
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_AsyncPlanCreate_ProgressScreen_TimeoutFix_2026_05_26_Closing_Handoff_v1.md` (PR #173 — the async progress-screen half of this arc; full detail there)
**Branch:** `claude/compassionate-meitner-CovIC`
**PRs this session:** #173 (async progress screen — merged `c91efe0`), #174 (3A/3B forced-tool retry — merged).

---

## 1. Session-start verification (Rule #9)

This session continued directly from PR #173 (same session). Anchors for #173 verified at merge (`grep -c "plan_versions_generation_status_chk" init_db.py` → 2; `generate_plan`/`plan_progress` present; suite 1690/16). PR #174 built on `origin/main` after #173's squash-merge (branch reset to `main` + force-push, Andy-approved — the old commit's content is already in `main`).

---

## 2. Session narrative — the live-test loop

Andy applied the two owed actions from PR #173 (Neon `init_db.py` migration + Vercel **Function Max Duration = 300s**; he's on Pro) and ran a real plan-create:

1. **Progress screen worked.** The page flipped to the thinking screen, the rotating status copy + elapsed timer ran, and generation proceeded across multiple function invocations (resuming from `layer4_cache`). The timeout-500 is gone. ✅
2. **Then it failed** with `Athlete evaluation failed (schema_violation)`. Diagnosis: Layer 3A or 3B's LLM call returned **no `tool_use` block**. Root cause = the structural tail of the extended-thinking saga: PR #172 had to relax `tool_choice` to `auto` (a *forced* tool is rejected by the API alongside `thinking`), but `auto` makes the tool call *optional*, so the model can "think out loud" and never call the tool. This is the 4th distinct failure (after forced-`tool_choice`, `temperature != 1`, `max_tokens ≤ budget_tokens`).

**Decisions (Andy, via the scope questions):**
- **Fix:** keep extended thinking; add a **retry + diagnostics** (not "drop thinking"). → PR #174.
- **Navigate-away:** generation **should keep running** with the tab closed → **cron-driven background worker** (forward work).
- **Notifications:** **both** email + in-app → (forward work).

Also surfaced: pressing "Back to dashboard" on the progress screen currently *pauses* generation (polling stops; the in-flight pass finishes server-side + caches, but nothing re-fires; the row stays `generating`). Resumable by returning to the plan URL, but there's no dashboard affordance to do so — the cron worker (forward work) makes this moot.

---

## 3. What shipped

### 3.1 PR #173 — async progress-screen plan-create (merged `c91efe0`)
Full detail in the predecessor handoff. In brief: POST `/plans/v2/new` allocates + marks `generation_status='generating'` + redirects to a progress screen; the screen polls POST `/<id>/generate`, a resumable worker that runs one `orchestrate_plan_create` pass resuming from `layer4_cache` (each layer/phase cache row self-commits); on completion → persist + flip `ready` + redirect; typed errors → `failed` + graceful panel. New `plan_versions.generation_status` / `generation_error` columns (+ CHECK). Files: `init_db.py`, `routes/plan_create.py`, `templates/plan_create/progress.html` (new), `templates/plan_create/new_form.html`, `tests/test_routes_plan_create.py`.

### 3.2 PR #174 — 3A/3B forced-tool retry (this PR)
`llm_invocation.invoke_tool_call` refactored so its `messages.create` lives in an inner `_attempt(thinking_budget)` returning `(ToolCallResult | None, stop_reason)`. Main flow: run the configured attempt (thinking → `auto` tool); **if it returns no tool block AND thinking was on, retry once with `_attempt(0)`** (thinking off → FORCED tool, which the model cannot decline); still nothing → raise `schema_violation` with `stop_reason` in the detail. A `print(...)` logs the miss + the retry to Vercel runtime logs. Extended thinking stays the primary path; the forced fallback only fires after thinking already failed to produce the tool call. Covers **Layer 3A/3B** (they delegate to the shared helper). Files: `llm_invocation.py`, `tests/test_layer3_thinking_request.py` (+2 tests → 13), `aidstation-sources/CARRY_FORWARD.md`.

Anchor: `grep -c "retrying with\nthinking off" llm_invocation.py` → the retry block + `print`; `grep -c "def _attempt" llm_invocation.py` → 1.

---

## 4. Tests

Full suite **1692 passed / 16 skipped** in a fresh `/tmp/venv` (1685 pre-session → 1690 after #173 → 1692 after #174). New #174 tests: `test_helper_thinking_miss_falls_back_to_forced` (asserts the forced retry fires + its result is returned + the final request is forced/no-thinking) and `test_helper_thinking_off_does_not_retry_on_miss` (a forced call that still misses raises immediately, no retry). All prior thinking-shape + APIError-mapping tests still pass.

---

## 5. Owed actions (Andy's hands) — STATUS

| Action | Status |
|---|---|
| Neon migration `python init_db.py` (PR #173 columns) | ✅ Done (live run confirmed the progress flow) |
| Vercel **Function Max Duration** raised | ✅ Done — set to **300s** (Pro) |
| Live plan-create end-to-end | ⏳ In progress — progress screen works; blocked at Layer 4 `schema_violation` until §6.1 ships (3A/3B now retry-safe) |

---

## 6. Next session pointers — the agreed roadmap

Three forward PRs, in priority order. Each is its own PR (5-file ceiling); each needs the merge → `reset --hard origin/main` → `git push --force-with-lease` branch cycle (this branch is reused post-merge; Andy approved the force-push).

### 6.1 Layer 4 caller dedupe — REQUIRED for an end-to-end plan (do first)
Migrate the 5 Layer 4 `_default_*_caller`s (`per_phase` / `seam_review` / `single_session` / `plan_refresh` / `race_week_brief`) onto `llm_invocation.invoke_tool_call`, deleting their inline `client.messages.create` request construction. This **distributes the #174 forced-tool retry to them** — without it, a plan still `schema_violation`s at the phase synthesizer (3A/3B clear, then Layer 4 fails the same way). Also point `tests/test_layer4_thinking_request.py` at the shared helper, and extend the graceful typed-error catch to the sibling routes (`routes/plan_refresh.py` ~`except OrchestrationError`/`Layer4*` block, `routes/ad_hoc_workouts.py` ~lines 426 + 604) which call 3A/3B through the same cone and still 500 on a `Layer3*OutputError`. ~6–7 files → its own PR. **This is the architect-recommended next forward move.**

### 6.2 Cron-driven background generation
Add a Vercel cron (you already have `crons` in `vercel.json` for nudges) that runs frequently (Pro allows ≥1/min) and hits a new endpoint that finds `plan_versions` rows with `generation_status='generating'` (bounded — e.g. created within the last N hours, not failed) and advances each by one `generate_plan`-style resumable pass. Decouples generation from the page; the progress page still polls for faster feedback when open. Mechanically: factor the body of `routes/plan_create.generate_plan` into a reusable `_advance_plan_generation(db, uid, plan_version_id)` the cron + the route both call. Watch: the cron endpoint must be auth-exempt (it's not a logged-in user) but guarded (e.g. a `CRON_SECRET` header check) — see `routes/nudges.py` for the existing cron-auth precedent.

### 6.3 Notifications — email + in-app (both)
On terminal status in `generate_plan`/`_advance_plan_generation`: send a "plan ready" / "plan failed" email via `email_helper.py`, and surface a dashboard status badge + link (the `plan_versions.generation_status` column already carries the state — the dashboard query just needs to read it). Guard against double-send (e.g. a `notified_at` column or only send on the transition into `ready`/`failed`).

### 6.4 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items (incl. the 3A/3B retry §5.0 entry + the async progress-screen entry).
4. This handoff.
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Resumable stepped generation behind a progress screen (PR #173) | Andy | Hobby/Pro per-function cap can't hold the multi-minute cone; the per-layer/per-phase cache makes re-invocation cheap. |
| 2 | Keep extended thinking + add a forced-tool retry (vs. drop thinking) | Andy | Preserves 3A/3B reasoning depth; the forced fallback only fires when thinking already failed to produce the tool call. |
| 3 | Cron-driven background generation (vs. page-driven + resume link) | Andy | Generation should finish with the tab closed. |
| 4 | Notifications: both email + in-app | Andy | Email reaches the user when away; in-app badge for on-site. |
| 5 | Reuse the merged branch via `reset --hard origin/main` + `--force-with-lease` | Andy | Clean per-PR diffs; the old commit's content is already in `main`. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -c "def _attempt" llm_invocation.py` → 1 | ✅ |
| `invoke_tool_call` retries `_attempt(0)` on a thinking-miss + logs `stop_reason` | ✅ |
| `tests/test_layer3_thinking_request.py` → 13 passed | ✅ |
| Full suite `pytest tests/` → 1692 passed / 16 skipped | ✅ |
| PR #173 merged (`c91efe0`); PR #174 merged | ✅ |

---

## 9. Files shipped this session

**PR #173 (merged):** `init_db.py`, `routes/plan_create.py`, `templates/plan_create/progress.html` (new), `templates/plan_create/new_form.html`, `tests/test_routes_plan_create.py`.
**PR #174 (this):** `llm_invocation.py`, `tests/test_layer3_thinking_request.py`.
**Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md` (async + 3A/3B §5.0 entries), the PR #173 predecessor handoff, this handoff.

---

## 10. Carry-forward

`CARRY_FORWARD.md` §5.0 carries the async progress-screen walk + the 3A/3B retry walk (incl. the Layer 4 still-exposed warning). §6.1 (Layer 4 dedupe) is the required next move for an end-to-end plan; §6.2 (cron) + §6.3 (notifications) follow.

---

**End of handoff.**
