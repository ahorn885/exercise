# Plan-Gen D-77 — Poller 'generating' Mapping + Client Give-Up Fix — Closing Handoff

**Session:** Live-incident session. Andy reported plan-gen "still failed" with the screen message *"Plan generation didn't finish — This is taking longer than expected. Please try again."* on the just-shipped D-77 accepted-week-gate / concurrency-guard / per-invocation-budget work (PR #311, merged `7f203f2`). Root-caused it to a **route-mapping regression introduced by PR #311** (the poller never learned to handle the two new `'generating'` outcomes) plus the client's total-poll give-up cap that compounded it. Fixed both + tests + bookkeeping.
**Date:** 2026-05-29
**Predecessor handoff:** PR #311's closing handoff (`…AcceptedWeekGate_ConcurrencyGuard_InvocationBudget…`, referenced by Andy; never committed to the repo — the code it documents IS on `main`).
**Branch:** `claude/ecstatic-hamilton-NoWBX` (harness-pinned). **PR #312.**
**Status:** 2 substantive files (`routes/plan_create.py`, `templates/plan_create/progress.html`) + 1 test file. `tests/test_routes_plan_create.py` **50 passed** (45 baseline → +5 new `TestGeneratePlanRoute`); related suite (`test_plan_create_concurrency.py` + `test_layer4_validator.py` + this file) **160 passed** combined. No migration.

---

## 1. Session-start verification (Rule #9)

Anchored PR #311 against on-disk `main` (the predecessor handoff isn't committed, so the §8 sweep ran against the code it shipped):

| Claim | Anchor | Result |
|---|---|---|
| PR #311 merged to main | `git log` → `7f203f2` merge, `1258702` | ✅ |
| Concurrency guard returns a new `'generating'` outcome | `routes/plan_create.py` `_try_acquire_advance_lock` + `{"status": "generating", "note": "advance_in_progress_elsewhere"}` | ✅ |
| Per-invocation budget returns a new `'generating'` outcome | `except Layer4GenerationIncomplete` → `{"status": "generating", "note": "budget_partial_progress"}` | ✅ |
| `Layer4GenerationIncomplete` is a `BaseException` | `layer4/generation_budget.py:35` | ✅ |
| Poller route `generate_plan` handles those outcomes | `routes/plan_create.py` `generate_plan` — **NO**, fell through to `outcome['error']` | ❌ → the bug |

**Reconciliation note:** the ❌ above is the defect this session fixes — not pre-existing drift in a handoff claim.

## 2. Session narrative

Andy: "plan gen still failed" + the screen copy *"Plan generation didn't finish — This is taking longer than expected. Please try again."* That exact string is the client's `showFailure(...)` in `templates/plan_create/progress.html`, fired when the poll loop hits its give-up cap — so the trail starts at the poller, not the cone.

**Root cause — a regression PR #311 introduced.** PR #311 added two new `{"status": "generating", ...}` return paths to `_advance_plan_generation` (the per-plan concurrency guard → `advance_in_progress_elsewhere`; the per-invocation wall-clock budget → `budget_partial_progress`) but never updated the poller route `generate_plan` to handle them. The route was:

```python
if outcome['status'] == 'not_found': abort(404)
if outcome['status'] == 'ready':     return jsonify({...ready...})
return jsonify({"status": "failed", "error": outcome['error']})   # ← fallthrough
```

A `'generating'` outcome has no `'error'` key, so `outcome['error']` raised **`KeyError` → HTTP 500** on every intermediate poll. Because the per-invocation budget makes `budget_partial_progress` the **normal** path for any plan needing more than one synthesis pass (each pass now caches ~1 week-block, by design), essentially every real multi-block plan 500'd its way to the give-up message — while the cone itself was healthy and caching blocks. This sat directly on top of the D-77 convergence work: even a fully-converging cone could never be *observed* converging, because the poller 500'd before `ready`.

**Compounding cause — the client total-poll cap.** The poller capped *total* polls at `MAX_ATTEMPTS = 20`, incremented on every poll (progress or not). Each 500 above counted as a failed attempt; and even with the route fixed, 20 total polls is far too few now that the budget caps each pass to ~1 block — a real 12–24-week plan needs many more passes. The client must not impose a total-poll ceiling; the **server-side wall-clock stall backstop** (`_STALL_WALLCLOCK_S = 900`s of no new block) is the real terminal guard.

## 3. File-by-file edits

### 3.1 `routes/plan_create.py` (modified)
`generate_plan` (the `POST /<id>/generate` poller endpoint) now branches on `status` explicitly: `not_found` → 404, `ready` → redirect JSON, `failed` → `{"status":"failed","error":...}`, and the new fallthrough `'generating'` → `{"status":"generating"}` (the poller's keep-polling signal). Comment names both `generating` notes and the prior KeyError/500 symptom so it can't silently regress.

### 3.2 `templates/plan_create/progress.html` (modified)
Replaced the total-poll cap `MAX_ATTEMPTS=20`/`attempts` + `retryOrGiveUp(delayMs)` with `MAX_CONSECUTIVE_FAILURES=20`/`consecutiveFailures` + `giveUpAfterFailures(delayMs)`. A clean JSON response (any status) resets `consecutiveFailures = 0`; only the `.catch` (5xx / network) path increments it. A `generating` response keeps polling (1s) indefinitely — bounded server-side by the stall backstop reaching terminal `failed`/`ready`. Give-up copy unchanged. Inline JS passes `node --check`.

### 3.3 `tests/test_routes_plan_create.py` (modified)
New `TestGeneratePlanRoute` (5 tests) drives the poller route via a Flask test client: both `generating` notes → `200 + {"status":"generating"}` (the regression guard — would 500 before), `ready` → redirect JSON, `failed` → stored error, `not_found` → 404.

## 4. Code / tests

`tests/test_routes_plan_create.py`: **50 passed** (was 45; +5 `TestGeneratePlanRoute`). `test_plan_create_concurrency.py` + `test_layer4_validator.py` + this file: **160 passed** combined (`/tmp/venv`; `pip install pytest flask pydantic bcrypt zxcvbn requests`). No migration (HTTP-mapping + client-JS only; no schema, no cache key).

## 5. Manual §5.0 verification steps

Appended to `CARRY_FORWARD.md`. The load-bearing one: this fix is a **prerequisite for the still-owed D-77 convergence re-run** (CARRY_FORWARD owed-deploy #1) — that proof could never have gone green at the client before, because the poller 500'd on every `budget_partial_progress` pass. So the convergence walk and this fix verify together:

1. Redeploy `main`, create one fresh PGE 2026 plan. The progress screen should now run for many minutes (well past the old ~20-poll wall), elapsed counter climbing, and open the plan automatically on `ready` — no premature "taking longer than expected".
2. Mid-flight, confirm `POST /plans/v2/<id>/generate` returns `200 {"status":"generating"}` in devtools → Network, **not** `500`.
3. Negative path preserved: a genuinely stuck unit still fails loudly via the server stall backstop (900s) → poller surfaces the stored failure message, not the generic give-up copy.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
The D-77 convergence re-run (CARRY_FORWARD owed #1, epic #201) is now actually observable end-to-end — run it. Watch `ibundle` identical across passes, per-block `HIT`, plan reaches `ready`, then the §14 coherence read.

### 6.2 Alternative pivots
The still-open non-blocking D-77 quality flags (`volume_band_below` (B), ~150s/block latency (C), discipline data hygiene (D)) and the SAFETY item #303 (`food_allergies` → Layer 2E) per `CURRENT_STATE.md` "Next moves".

### 6.3 Operating notes for next session
Read order (Rule #13): (1) `CLAUDE.md`; (2) `CURRENT_STATE.md`; (3) `CARRY_FORWARD.md`; (4) this handoff; (5) `./scripts/verify-handoff.sh`. The poller's give-up cap now counts **consecutive transport failures**, not total polls — healthy multi-pass generation is unbounded client-side. If a misconfigured `PLAN_GEN_FUNCTION_CAP_S` lets a pass 504 mid-synthesis, those 504s count as consecutive failures; keep that env in sync with the Vercel dashboard Max Duration (300s).

## 7. Decisions pinned

- `_advance_plan_generation`'s `'generating'` outcomes are a first-class poller signal (`{"status":"generating"}`), **not** an error. Any future outcome status added to the engine must be mapped in `generate_plan` (the route no longer has a catch-all `failed` fallthrough that hides a missing key).
- The poller's give-up cap counts **consecutive transport failures**, not total polls. The server-side wall-clock stall backstop is the terminal guard for a stuck generation; the client polls until the server reaches a terminal state.

## 8. Session-end verification (Rule #10)

| Claim | Anchor | Method | Result |
|---|---|---|---|
| `generate_plan` maps `'generating'` → keep-polling JSON | `routes/plan_create.py` `generate_plan` → `return jsonify({"status": "generating"})` | grep | ✅ |
| No `outcome['error']` fallthrough remains | `routes/plan_create.py` — `outcome['error']` only under `status == 'failed'` | inspection | ✅ |
| Client counts consecutive failures, not total polls | `templates/plan_create/progress.html` → `MAX_CONSECUTIVE_FAILURES` + `consecutiveFailures = 0` reset on clean response | grep | ✅ |
| No stale `MAX_ATTEMPTS`/`attempts`/`retryOrGiveUp` | `grep -n` in `progress.html` → none | grep | ✅ |
| Regression test present | `tests/test_routes_plan_create.py` → `class TestGeneratePlanRoute` (5 tests) | grep + run | ✅ |
| Suite green | `tests/test_routes_plan_create.py` 50 passed; combined 160 passed | `pytest` | ✅ |
