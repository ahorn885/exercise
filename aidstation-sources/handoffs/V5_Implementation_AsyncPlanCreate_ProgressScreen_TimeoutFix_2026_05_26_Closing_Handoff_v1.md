# Async Plan-Create + Progress Screen — Plan-Create Timeout 500 Fix — Closing Handoff

**Session:** Andy: "tried to generate a plan … sat on the create-plan screen a long time ('sending request to [vercel]') … then an internal server error again. Also — when generating a plan we should flip to a progress / thinking screen rather than sitting on the create-plan button." Diagnosed the *still-live* 500 as a **serverless function timeout** (NOT the prior extended-thinking 400, which is fixed): `routes/plan_create.py` ran the entire Layer 3A → 3B → per-phase Layer 4 cone **synchronously** inside one Vercel request — many sequential extended-thinking LLM calls, minutes of wall-clock, well past the function ceiling. Andy chose **resumable stepped generation** on **Hobby (60s cap)**, scoped to **progress screen + 500 fix only** (the Layer 4 dedupe follow-on stays a separate PR). Shipped: async generation driven by a progress/thinking screen that polls a resumable `/generate` worker, with completed layers/phases resuming from `layer4_cache`.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_Layer3_ThinkingIncompatibility_500Fix_Dedupe_2026_05_26_Closing_Handoff_v1.md`
**Branch:** `claude/compassionate-meitner-CovIC`
**Status:** 5 substantive files (migration + route refactor + new progress template + form-copy fix + extended test). Bookkeeping: this handoff + `CURRENT_STATE.md` + `CARRY_FORWARD.md`. **Two owed Andy-hands actions** before it works in prod (Neon migration + Vercel Function Max Duration = 60s) — see §5.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (`…ThinkingIncompatibility_500Fix_Dedupe…`) §8 claims against on-disk state:

| Claim | Anchor | Result |
|---|---|---|
| Shared request site exists | `grep -c 'max_tokens + extended_thinking_budget' llm_invocation.py` → 1 | ✅ |
| 3A/3B delegate + map | `grep -c 'except ThinkingToolCallError as exc' layer3a/builder.py layer3b/builder.py` → 1 each | ✅ |
| Route catches Layer3 errors | `routes/plan_create.py` had `except (Layer3AOutputError, Layer3BOutputError)` | ✅ |
| PR #172 merged | `git log` shows `d2940ce …(#172)` | ✅ |

No drift. The thinking-400 work all landed and is correct. The remaining 500 is a **different failure mode** (timeout), exactly the "may surface downstream issues" the predecessor §5 flagged for the never-run end-to-end path.

---

## 2. Session narrative

**Root cause.** `new_plan` POST called `orchestrate_plan_create(...)` inline, then `persist_layer4_sessions` + `commit`. `orchestrate_plan_create` → `_upstream_full_cone` fires **Layer 3A then 3B** (2 extended-thinking LLM calls; 2A/2B/2C/2D/2E are `q_` DB queries, not LLM), then `llm_layer4_plan_create_cached` runs the **per-phase synthesis loop** (one extended-thinking call per phase, typically 3–4, each with up to 2 capped retries) + **parallel seam reviews** + a final cross-phase validator. That's many sequential LLM calls — minutes — inside one HTTP request. Vercel kills the function at its max duration → the browser gets an error after a long "sending request" wait. Andy read it as "internal server error again."

**Fix (Andy's pick: resumable stepped generation; Hobby 60s; scope = progress screen + 500 only).** The key enabler already exists: every cached layer/phase **commits its cache row immediately** (`cache_postgres.py:143`), and `orchestrate_plan_create` has a per-entry cache that short-circuits the whole call on a hit. So re-invoking `orchestrate_plan_create` **resumes cheaply from cache** — completed layers/phases replay as fast cache reads; the next uncached unit computes; a pass cut at the 60s timeout keeps everything that committed.

New flow:
- **POST `/plans/v2/new`** validates + allocates the `plan_versions` row, sets `generation_status='generating'`, commits, redirects to the progress screen. **No LLM work** → can't time out.
- **GET `/plans/v2/<id>/progress`** renders a thinking screen (spinner + rotating status copy + elapsed timer) whose JS repeatedly `POST`s `/generate`.
- **POST `/plans/v2/<id>/generate`** runs one `orchestrate_plan_create` pass (resumes from cache). On completion: `DELETE`-guarded `persist_layer4_sessions` + flip to `ready` + commit, return `{status:'ready', redirect}`. On a typed upstream error (`OrchestrationError` / `Layer4InputError` / `Layer4OutputError` / `Layer3AOutputError` / `Layer3BOutputError`): flip to `failed` + store the user-facing message, return `{status:'failed', error}`. If the pass is cut by the timeout, the request drops and the poller re-fires.
- **GET `/plans/v2/<id>`** redirects `generating` → progress, flashes on `failed`, renders sessions when `ready`.

No `/plan`-gate trigger applies: this is caller-side route plumbing + a v1-app lifecycle column, not a prompt body (Trigger #1) or an inter-layer contract (Trigger #3). Andy approved the approach + scope + Vercel-plan facts via the scope questions.

---

## 3. File-by-file edits

### 3.1 `init_db.py` (migration)
Appended to `_PG_MIGRATIONS` (before the closing `]`): `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_status TEXT NOT NULL DEFAULT 'ready'` + `… generation_error TEXT` + a named-CHECK `DO $$` block adding `plan_versions_generation_status_chk CHECK (generation_status IN ('generating','ready','failed'))` idempotently. Default `'ready'` so existing rows + the synchronous `plan_refresh`/`single_session` paths (which also `allocate_plan_version_row`) stay valid; only plan_create's async path sets `'generating'`. Anchor: `grep -c "plan_versions_generation_status_chk" init_db.py` → 2.

### 3.2 `routes/plan_create.py` (async refactor)
- Import `jsonify`.
- `_load_plan_version` now SELECTs + returns `generation_status` + `generation_error`.
- New helpers: `_view_plan_url`; `_terminal_status_response(plan_version, view_url)` (ready→redirect / failed→error / generating→None — pure, unit-tested); `_mark_plan_failed(db, id, uid, message)` (rollback → UPDATE failed → commit → return JSON).
- `new_plan` POST: allocate → `UPDATE … generation_status='generating'` → commit → redirect to `plan_progress`. No orchestrate call.
- New `plan_progress` GET (renders `progress.html`; `ready` skips to the view).
- New `generate_plan` POST (the resumable worker; returns JSON; `DELETE`-before-persist keeps re-persist idempotent against the natural-key UNIQUE on a cache-hit replay).
- `view_plan` GET: `generating`→redirect to progress; `failed`→flash + redirect to new; `ready`→render as before.
- Module + `new_plan` docstrings rewritten to describe the async flow.

Anchors: `grep -c "def generate_plan\|def plan_progress" routes/plan_create.py` → 1 each; `grep -c "generation_status = 'generating'" routes/plan_create.py` → 1.

### 3.3 `templates/plan_create/progress.html` (NEW)
Thinking screen: Bootstrap spinner + rotating status copy + elapsed-seconds counter + a hidden failure panel. Inline `<script nonce="{{ csp_nonce() }}">` IIFE polls `data-generate-url` via `fetch`. **CSRF:** reads the token directly from `<meta name="csrf-token">` and sets `X-CSRFToken` itself — does **not** rely on the `static/app.js` fetch wrapper, because this inline script runs during body parse *before* app.js (loaded at body end) wraps `window.fetch`. On `{ready}` → `window.location` to the view; on `{failed}` → show the error panel; on a non-OK response / network error (timeout) → re-fire, bounded by `MAX_ATTEMPTS=20` so a step that can't fit the timeout can't loop forever. No inline `style=` attrs (CSP `style-src` is nonce-only).

### 3.4 `templates/plan_create/new_form.html` (copy)
Replaced the misleading "Takes ~30-60 seconds." with "This runs the full coaching cascade and can take a few minutes; you'll see a progress screen while it works."

### 3.5 `tests/test_routes_plan_create.py` (extended)
`_FakeConn` gains a `rollback` counter; `_load_plan_version` test row + assertions gain the two new columns; new `TestTerminalStatusResponse` (4) + `TestMarkPlanFailed` (1). Net **+5** tests.

---

## 4. Code / tests

Full suite **1690 passed / 16 skipped** in a fresh `/tmp/venv` (was 1685/16; **+5** — the new helper tests). `python -m py_compile` clean on `routes/plan_create.py` + `init_db.py` + the test. App imports + all four `/plans/v2` routes register (`/new`, `/<id>`, `/<id>/progress`, `/<id>/generate`). Both templates Jinja-compile. The cone itself is unexercised by the suite (no `ANTHROPIC_API_KEY`); the async plumbing is what's new and what the tests cover.

---

## 5. Manual §5.0 verification + OWED ACTIONS (Andy's hands)

New `CARRY_FORWARD.md` §5.0 scenario added (count 114→115). **Two owed actions before this works in prod:**

1. **Neon migration** — `python init_db.py` against Neon; confirm `\d plan_versions` lists `generation_status` (NOT NULL DEFAULT 'ready', CHECK) + `generation_error`. Idempotent; stacks onto any prior owed run.
2. **Vercel Function Max Duration** — Hobby defaults to ~10s/function, far too short for a single extended-thinking call. Set Settings → Functions → **Function Max Duration = 60s** (Hobby ceiling); consider enabling **Fluid Compute**. `vercel.json` can't set this (legacy `builds` array can't coexist with the `functions` key) — it's a dashboard action, left untouched in this PR.

Then walk: create a plan → confirm it flips to the progress screen (no 500) and auto-opens the plan when done (spanning several `/generate` invocations); confirm a failure shows the graceful panel.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**The Layer 4 caller dedupe follow-on (still owed; Andy queued it this session).** Migrate the 5 Layer 4 `_default_*_caller`s (`per_phase`/`seam_review`/`single_session`/`plan_refresh`/`race_week_brief`) onto `invoke_tool_call` + point `tests/test_layer4_thinking_request.py` at the shared helper, and extend the graceful typed-error catch to the sibling routes (`routes/plan_refresh.py:~537`, `routes/ad_hoc_workouts.py:~426,604`) which call 3A/3B through the same cone and still 500 on a `Layer3*OutputError`. ~6–7 files → its own PR (split to respect the 5-file ceiling). **Note:** those sibling routes are *also* still synchronous — if their cones likewise time out, they'll want the same async treatment as a later slice; out of scope here.

### 6.2 Operating notes / known gotcha
- **Seam-review tier is not resumable.** Layer 4's per-phase syntheses are cached per phase, but the seam-review + final-validator tail runs whole at the end of `_run_pattern_a_engine` and isn't cached (a pre-existing §9.2 Step-6 gap). It re-runs on each resume. If a single per-phase synthesis (with retries) or the seam block can't finish within the 60s Hobby ceiling, the poller hits `MAX_ATTEMPTS` and shows "taking longer than expected." Fixes if it bites: Pro (300s functions) or caching the seam tier. Candidate backlog row.
- **Idempotent persist.** `persist_layer4_sessions` plain-INSERTs (UNIQUE natural key); `generate_plan` `DELETE`s sessions for the version before re-persist so a cache-hit replay after a partial pass can't collide.

### 6.3 Operating notes for next session (read order)
1. `CLAUDE.md` — stable rules (Rule #13).
2. `CURRENT_STATE.md` — what just shipped + focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items (incl. the two owed actions above).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Resumable stepped generation (vs. background-generate + bump maxDuration) | Andy | Robust to any total cone length / timeout; the Hobby 60s cap can't hold the whole cone, and the per-layer/per-phase cache already makes re-invocation cheap. |
| 2 | Hobby plan facts → each step must fit 60s | Andy | Confirms stepped is necessary; documents the single-unit>60s residual. |
| 3 | Scope this PR to progress screen + 500 fix; defer the Layer 4 dedupe | Andy | Keeps the PR at the 5-file ceiling; the dedupe is its own ~6–7-file PR. |
| 4 | Leave `vercel.json` untouched; max-duration is a dashboard action | Claude | The Python runtime honors the dashboard Function Max Duration; `functions` can't coexist with the working legacy `builds` entry, so editing vercel.json risks breaking the deploy for no gain. |
| 5 | Read CSRF token directly in the progress JS (not via app.js wrapper) | Claude | The inline script runs before app.js wraps `fetch`; reading the meta tag removes the ordering dependency. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -c "plan_versions_generation_status_chk" init_db.py` → 2 (the DO block's check + the ADD CONSTRAINT) | ✅ |
| `grep -c "def generate_plan\|def plan_progress" routes/plan_create.py` → 1 each | ✅ |
| `grep -c "generation_status = 'generating'" routes/plan_create.py` → 1 | ✅ |
| `routes/plan_create.py` no longer calls `orchestrate_plan_create` in `new_plan` (only in `generate_plan`) | ✅ |
| `templates/plan_create/progress.html` exists + Jinja-compiles | ✅ |
| `python -m py_compile` on the 3 Python files | ✅ |
| App imports; 4 `/plans/v2` routes register | ✅ |
| Full suite `pytest tests/` → 1690 passed / 16 skipped | ✅ |

---

## 9. Files shipped this session

**Substantive (5 files):**
1. `init_db.py` (migration — `plan_versions.generation_status` + `generation_error` + CHECK)
2. `routes/plan_create.py` (async refactor + `plan_progress` + `generate_plan`)
3. `templates/plan_create/progress.html` (new — thinking screen + polling JS)
4. `templates/plan_create/new_form.html` (copy — removed the misleading "~30-60s")
5. `tests/test_routes_plan_create.py` (extended — +5 tests)

**Bookkeeping:**
6. `CURRENT_STATE.md` — last-shipped pointer bumped to this handoff.
7. `CARRY_FORWARD.md` — new §5.0 scenario + the two owed actions.
8. This handoff.

---

## 10. Carry-forward updates

New §5.0 scenario + the two owed Andy-hands actions (Neon migration + Vercel Function Max Duration) recorded in `CARRY_FORWARD.md`. §6.1 (Layer 4 dedupe follow-on) is the recommended next forward move; §6.2 (seam-review-tier non-resumability) is a latent follow-on candidate.

---

**End of handoff.**
