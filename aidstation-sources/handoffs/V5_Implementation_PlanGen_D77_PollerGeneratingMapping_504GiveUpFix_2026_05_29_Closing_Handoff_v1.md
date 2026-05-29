# Plan-Gen D-77 — Poller 'generating' Mapping + Client Give-Up Fix — Closing Handoff

**Session:** Live-incident session. Andy reported plan-gen "still failed" with the client message *"Plan generation didn't finish — This is taking longer than expected. Please try again."* after the D-77 accepted-week-gate / concurrency-guard / per-invocation-budget work (PR #311) shipped. Root-caused it to a **route-mapping regression introduced by PR #311** and fixed it plus the client-side give-up cap that compounded it.
**Date:** 2026-05-29
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_AcceptedWeekGate_ConcurrencyGuard_InvocationBudget_2026_05_29_Closing_Handoff_v1.md` (referenced by Andy; not committed to the repo)
**Branch:** `claude/ecstatic-hamilton-NoWBX` (harness-pinned)
**Status:** 2 code/template files + 1 test file. `tests/test_routes_plan_create.py` **50 passed** (45 baseline → +5 new `TestGeneratePlanRoute`); related suite (`test_plan_create_concurrency.py`, `test_layer4_validator.py`) green (160 passed combined).

---

## 1. Session-start verification

Confirmed on-disk against `git log`: PR #311 (`7f203f2` merge, `1258702`) added the per-plan concurrency guard + per-invocation budget. Verified `_advance_plan_generation` (`routes/plan_create.py`) returns the two new `{"status": "generating", "note": ...}` outcomes (`advance_in_progress_elsewhere` at the concurrency guard, `budget_partial_progress` in the `except Layer4GenerationIncomplete` handler), and that `generation_budget.py` raises `Layer4GenerationIncomplete` (a `BaseException`). All present.

## 2. Root cause

The symptom string *"This is taking longer than expected. Please try again."* is the client's `showFailure(...)` in `templates/plan_create/progress.html`, fired when the poll loop hits its give-up cap.

**Primary cause — route-mapping regression (PR #311).** PR #311 added two new `{"status": "generating"}` return paths to `_advance_plan_generation` but did **not** update the poller route `generate_plan` to handle them. The route was:

```python
if outcome['status'] == 'not_found': abort(404)
if outcome['status'] == 'ready':     return jsonify({...ready...})
return jsonify({"status": "failed", "error": outcome['error']})   # ← fallthrough
```

A `'generating'` outcome has no `'error'` key, so `outcome['error']` raised **`KeyError` → HTTP 500** on every intermediate poll. Because the per-invocation budget makes `budget_partial_progress` the **normal** path for any plan needing more than one synthesis pass, essentially every real (multi-block) plan 500'd its way to the give-up message. The cone itself was healthy and caching blocks — the failure was purely in the HTTP mapping.

**Compounding cause — client total-poll cap.** The poller capped *total* polls at `MAX_ATTEMPTS = 20`, incrementing on every poll (progress or not). Each 500 above counted as a failed attempt via the `.catch` path, so 20 polls → give up. Even with the route fixed, 20 total polls is too few: the per-invocation budget caps each pass below the function timeout, so a healthy plan advances ~1 week-block per pass and a real 12–24-week plan needs many more than 20 passes. The client must not impose its own total-poll ceiling — the **server-side wall-clock stall backstop** (`_STALL_WALLCLOCK_S = 900`s of no new block) is the real terminal guard.

## 3. File-by-file edits

### 3.1 `routes/plan_create.py` (modified)
`generate_plan` now branches on `status` explicitly: `not_found` → 404, `ready` → redirect JSON, `failed` → `{"status":"failed","error":...}`, and the new fallthrough `'generating'` → `{"status":"generating"}` (the poller's keep-polling signal). Comment names both `generating` notes and the prior KeyError/500 symptom.

### 3.2 `templates/plan_create/progress.html` (modified)
Replaced the total-poll cap `MAX_ATTEMPTS=20`/`attempts` + `retryOrGiveUp(delayMs)` with `MAX_CONSECUTIVE_FAILURES=20`/`consecutiveFailures` + `giveUpAfterFailures(delayMs)`. A clean JSON response (any status) resets `consecutiveFailures = 0`; only the `.catch` (5xx / network) path increments it. A `generating` response keeps polling (1s) indefinitely — bounded server-side by the stall backstop reaching a terminal `failed`/`ready`. Give-up copy unchanged.

### 3.3 `tests/test_routes_plan_create.py` (modified)
New `TestGeneratePlanRoute` (5 tests) over the poller route via a Flask test client: both `generating` notes → 200 + `{"status":"generating"}` (the regression guard — would 500 before), `ready` → redirect JSON, `failed` → stored error, `not_found` → 404.

## 4. Code / tests

`tests/test_routes_plan_create.py`: 50 passed (was 45). `test_plan_create_concurrency.py` + `test_layer4_validator.py` + this file: 160 passed combined. Inline progress.html JS passes `node --check`.

## 5. Manual §5.0 verification steps

1. Create a plan with a target race ~12+ weeks out (multi-block). The progress screen should now run for many minutes (well past the old ~20-poll wall), the elapsed counter climbing, and open the plan automatically on completion — no premature "taking longer than expected".
2. While a plan generates, confirm `POST /plans/v2/<id>/generate` returns `200 {"status":"generating"}` mid-flight (browser devtools → Network), not `500`.
3. Negative path preserved: a genuinely stuck unit still fails loudly via the server stall backstop (900s) → poller surfaces the stored failure message, not the generic give-up copy.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
Decomposition convergence on a real multi-block plan was previously UNVERIFIED (blocked first by the backstop false-trip, then by this poller 500). With the mapping fixed, a real end-to-end coherence walk is now runnable — that is the next gate.

### 6.3 Operating notes
The client now polls until the server reaches a terminal state, so the only client-side give-up is a 20-deep run of consecutive transport failures (~40s of unreachability). If a misconfigured `PLAN_GEN_FUNCTION_CAP_S` lets a pass 504 mid-synthesis, those 504s count as consecutive failures — keep the env cap in sync with the Vercel dashboard Max Duration.

## 7. Decisions pinned

- The poller's give-up cap counts **consecutive transport failures**, not total polls. Healthy multi-pass generation is unbounded client-side; the server stall backstop is the terminal guard.
- `_advance_plan_generation`'s `'generating'` outcomes are a first-class poller signal (`{"status":"generating"}`), not an error.
