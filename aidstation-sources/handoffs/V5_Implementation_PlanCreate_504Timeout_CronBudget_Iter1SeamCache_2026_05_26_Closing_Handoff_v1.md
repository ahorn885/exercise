# plan-create 504-timeout hardening — cron wall-clock budget + iter-1 seam-review cache — Closing Handoff

**Session:** Andy: "check out the Layer4 missing-sessions handoff and let's work — I want to investigate the 504 timeouts first." Investigated the recurring plan-gen 504s, found they are **not a standing incident** (production is healthy — the every-minute `generate-pending` cron returns `200` as a fast no-op when nothing is `generating`); they surface only during *active, non-converging* generation, and the schema_violation chain (#179/#181/#182) was driving the non-convergence (a row that never cached a phase kept the cron re-burning the whole cone every minute). Confirmed **Function Max Duration = 300s (Pro)** via the live deployment — that closes the "single uncached unit > function budget" trap for normal plans. Andy chose **"fix both"** remaining structural traps: **(trap #2)** the cron advanced up to `_CRON_ADVANCE_BATCH=5` full resumable passes back-to-back in one request with no wall-clock guard → added a `_CRON_WALL_CLOCK_BUDGET_S=240` budget; **(trap #3)** the seam-review tier ran whole + uncached on every resumable pass → the **iter-1 seam reviews are now cached individually**, migration-free, so a resumed pass replays them from cache.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_Layer4_SchemaViolation_MissingSessions_2026_05_26_Closing_Handoff_v1.md` (PR #182 `244ec67`)
**Branch:** `claude/504-timeout-investigation-PB5oM`
**Status:** 3 substantive code files (`routes/plan_create.py`, `layer4/hashing.py`, `layer4/plan_create.py`) + `Layer4_Spec.md §9.2` note + 3 test files + bookkeeping. Full suite **1733 passed / 16 skipped** (+4 over the 1729 baseline). **No migration; no owed deploy beyond a normal redeploy.**

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` clean; working tree clean on the branch. Spot-checked the predecessor (#182) §8 claims:

| Claim (predecessor) | Anchor | Result |
|---|---|---|
| #182 merged (`244ec67`) on `main`; is current prod | `git log` + Vercel `list_deployments` (`dpl_4oN6EXiyx3mJsxwm6dyRwuBi191W`, target=production) | ✅ |
| missing-`sessions` retry shipped at `per_phase.py` | grep `_clamp_sessions_over_emit` / retry block | ✅ |
| cron exists at `routes/plan_create.py` | grep `def cron_generate_pending` / `_CRON_ADVANCE_BATCH` | ✅ |

No drift.

## 2. Session narrative + diagnosis

**A 504 here = the Vercel function exceeded its max duration.** Generation is stepped + resumable: each `POST /<id>/generate` (poller) or each cron row runs one `orchestrate_plan_create` pass that replays cached units fast and computes the next uncached one. A 504 mid-pass is tolerated *iff each pass makes forward progress* (commits a cache row). It turns pathological only when a pass can't make progress within one function window.

**Evidence (Vercel runtime-log MCP, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`, team `team_rkZGxltBw2ykWtrIPCYy16JZ`):** on the current prod deployment the cron fires every minute and returns `200` sub-second (no `generating` rows → no LLM work). So the "recurring 504s" the #182 handoff §2 flagged were a *symptom of non-converging generation*, not a standing incident. They were coupled to the schema_violation: a phase that hard-raised never cached, the row stayed `generating`, and the every-minute cron re-burned the cone each fire (long enough to 504, never converging). #182's missing-sessions retry makes phases cache → the loop converges.

**Three latent traps identified; #1 already closed by Pro:**
1. *Single uncached unit > budget.* A phase synthesis is up to 3 sequential extended-thinking calls (1 + `capped_retries=2`) in one pass. On Hobby (60s) that alone can't fit → infinite loop. **Pro/300s (confirmed active) closes this** for normal 3–4 phase plans.
2. *Cron batch-of-5 with no wall-clock guard* — `cron_generate_pending` advanced up to `_CRON_ADVANCE_BATCH=5` full passes back-to-back in ONE request; two+ cold rows blow 300s and 504 mid-batch (the comment even falsely claimed the batch bounded wall-clock).
3. *Seam tier uncached* — per-phase syntheses cache, but the seam-review + final-validator tail (`layer4/plan_create.py`) re-ran whole on every resume. The final validator is deterministic/cheap; the **iter-1 seam reviews are the real uncached LLM bulk** (the §9.2 Step-6 carry-forward gap).

**Reassessment surfaced to Andy on trap #3 (AskUserQuestion):** "cache the seam tier as a unit" does NOT fix the hard-wall case (an uncompletable unit never gets stored). The correct granular fix is to cache the *individual* iter-1 reviews. On Pro the wall is unlikely for normal plans (iter-1 parallelized ≈ one reviewer call; iter-2 capped at one re-synth per seam), and there's zero current evidence the tier nears 300s — so I recommended instrument-first. **Andy chose "build the iter-1 seam cache now."**

## 3. File-by-file edits

### 3.1 `routes/plan_create.py` (trap #2)
- `import time`.
- New `_CRON_WALL_CLOCK_BUDGET_S = 240` (below the 300s cap; leaves headroom for a final pass started just under budget to finish + commit). Rewrote the misleading `_CRON_ADVANCE_BATCH` comment (it bounds the SELECT, not wall-clock).
- `cron_generate_pending`: compute `deadline = time.monotonic() + _CRON_WALL_CLOCK_BUDGET_S`; `break` out of the row loop once `time.monotonic() >= deadline` BEFORE starting the next pass. The in-flight pass still commits its per-phase progress; unstarted rows resume next fire. (The poller path `generate_plan` runs one pass per request — unaffected.)

### 3.2 `layer4/hashing.py` (trap #3 — key)
- New `compute_seam_review_cache_key(*, call_cache_key, seam_index, prior_phase_sessions, next_phase_sessions, model, max_tokens, extended_thinking_budget)` — `sha256(call_cache_key || 'seam' || str(seam_index) || sha256(canonical_json(prior_sessions)) || sha256(canonical_json(next_sessions)) || model || max_tokens || thinking_budget)`. The session lists are the per-call-variable part; everything else rides on `call_cache_key`.

### 3.3 `layer4/plan_create.py` (trap #3 — engine)
- `import json`; import `compute_seam_review_cache_key`.
- New `_SEAM_CACHE_PHASE_IDX_BASE = 1000` (disjoint from per-phase `phase_idx` 0..N-1 and the −1 per-entry sentinel).
- New `_serialize_seam_call_result` / `_hydrate_seam_call_result` (verdict + seam_issues + direction only; hydrate zeros token/latency per §9.6 — a hit fired no LLM call).
- In `_run_pattern_a_engine`: extracted `_seam_prior_sessions`/`_seam_next_sessions` (so the cache key hashes EXACTLY the sessions passed to `review_seam`); slimmed `_iter1_task` to use them. Replaced the iter-1 execution block with a **cache-aware partition**: sequential cache GET per seam (`cache.backend.get(_seam_cache_key(i), base+i)`) → cached results hydrated, uncached collected → only the uncached fire the parallel LLM calls (preserves §5.2 cross-seam parallelism on a cold run) → fresh results stored via `cache.backend.put(... entry_point=cache_entry_point, phase_name=f"__seam_{i}__" ...)` → merge + sort by seam_idx. All get/put happen BEFORE the processing loop runs any iter-2 re-synth, so the key always hashes the original (per-phase-cached) sessions on both cold + resume. Metrics recorded as `is_phase=True` (sub-call tier). The processing-loop `llm_call_count += 1` is now gated on `seam_idx not in cached_seam_indices` (a hit counts zero per §9.6).
- **Iteration-2 (re-synth-driven) reviews stay uncached** — they mutate `results_by_index` and are the rare flagged path. Unchanged.

### 3.4 `Layer4_Spec.md §9.2` (in place)
Replaced the "**Seam reviews are NOT cached**" paragraph with "**Iteration-1 seam reviews ARE cached (Step-6 follow-on)**" documenting the key formula, the same-entry_point + disjoint-phase_idx storage (no migration), the cold-run parallelism preservation, the iter-2-uncached carve-out, and the §9.6 zero-on-hit semantics. Edited in place (no `_vN` Layer4_Spec variants exist; matches the Layer3-spec in-place precedent).

### 3.5 Tests
- `tests/test_routes_plan_create.py`: new `TestCronGeneratePending::test_stops_starting_passes_once_wall_clock_budget_spent` (monkeypatches `plan_create.time.monotonic` to trip the deadline before row 3 → asserts only rows 1+2 advanced). 37 passed.
- `tests/test_layer4_plan_create.py`: new `_CountingSeamStub` + `TestIter1SeamReviewCache` (3: cold-run stores one row per seam under `plan_create` in the seam phase_idx namespace; resume replays all seams from cache with 0 new seam LLM calls; no-cache path still runs seams uncached). Updated `TestPerPhaseCacheWiring` + the cached-wrapper test assertions to account for the `n_seams = n_phases − 1` extra rows/misses/hits.
- `tests/test_layer4_plan_refresh.py`: updated `test_t3_cross_phase_threads_cache_through_to_per_phase` to add `first_seam_calls` to the miss/hit expectations + assert the resume doesn't re-fire seams (the engine is shared by T3 cross-phase).

## 4. Code / tests

Full suite **1733 passed / 16 skipped** in a fresh `/tmp/venv` (+4 over 1729: +1 cron test, +3 seam-cache tests; the existing per-phase/refresh cache-count assertions were adjusted, not removed). `py_compile` clean on all three code files. (Container: Neon egress blocked, PyPI works, `pytest` not in `requirements.txt` — see `CLAUDE.md` Environment quick-reference.)

## 5. Owed action (Andy's hands)

**None beyond a normal redeploy.** No migration — the seam-cache rows satisfy the existing `layer4_cache` constraints verbatim: `entry_point` stays `plan_create`/`plan_refresh` (in the CHECK set), `phase_idx = 1000+seam_idx` (`INTEGER`, no upper bound, `>= 0`), `phase_name = "__seam_N__"` (NOT NULL) — so they pass the `(phase_idx=-1 AND name NULL) OR (phase_idx>=0 AND name NOT NULL)` CHECK. Redeploy picks up the code; the iter-1 cache + cron budget engage immediately. Live walk in `CARRY_FORWARD.md`.

## 6. Next session pointers

### 6.1 Remaining seam-cache gap (low value)
Iteration-2 (re-synth-driven) seam reviews are still uncached — they mutate phase state (re-synthesize a phase) and only fire on `flagged_major`/`patched`. Caching them correctly couples to wiring the seam-driven re-synth into the per-phase cache (the other half of the §9.2 Step-6 gap). Low value on Pro; only worth it if a flagged-seam-heavy plan is observed nearing the budget.

### 6.2 The big deferred slices (unchanged from #182 §6)
#1 `Layer4ShapeInfeasibleError` (4 detection algos + OPEN routing decision §10.2/C3), #4 Layer 3C/3D/3.5 HITL gate (stop-and-ask #4, spec-first), #5 L3B §H.2 deployed-shape gap. Each its own scope. **Confirm Andy's profile has `body_weight_kg` + `height_cm`** before a live plan-gen walk — else 2E still blocks with the named `Layer2EInputError`.

### 6.3 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules (now includes the **Environment quick-reference**: Vercel team/project IDs, 300s cap, runtime-log gotcha, container test setup).
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items.
4. This handoff.
5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Add a wall-clock budget to the cron rather than dropping the batch to 1 | Claude→Andy ("fix both") | The budget is the correct guard regardless of batch size; keeps the batch as a hard SELECT cap; a single-user app rarely has >1 pending plan anyway. |
| 2 | Cache iter-1 seam reviews individually (not "the seam tier as a unit") | Claude→Andy ("build now") | A unit that can't complete never gets stored, so unit-caching doesn't fix the wall; per-seam caching makes the bulk resumable. |
| 3 | Store seam rows under the existing `plan_create`/`plan_refresh` entry_point + a disjoint `phase_idx` namespace | Claude | Avoids a new `entry_point` CHECK label → **no migration** (the exact failure mode that bit #177). Keeps the `entry_points == {...}` cache invariant intact. |
| 4 | Leave iter-2 (re-synth) reviews uncached | Claude | They mutate phase state + are the rare flagged path; correct caching couples to the unwired re-synth cache. Low value on Pro. |
| 5 | Record seam cache hits/misses on the `phase_*` metric counters (`is_phase=True`) | Claude | Seam rows are sub-call cache rows in the same tier as per-phase; the metric's purpose is sub-call cache effectiveness. Existing per-phase cache-count assertions updated to `n_phases + n_seams`. |

## 8. Session-end verification (Rule #10)

| Check | File:anchor | Method | Result |
|---|---|---|---|
| `_CRON_WALL_CLOCK_BUDGET_S = 240` defined + `time.monotonic()` deadline `break` in the cron | `routes/plan_create.py` | grep + read | ✅ |
| `import time` added | `routes/plan_create.py` | grep | ✅ |
| `compute_seam_review_cache_key` defined | `layer4/hashing.py` | grep | ✅ |
| `_SEAM_CACHE_PHASE_IDX_BASE = 1000` + `_serialize/_hydrate_seam_call_result` + cache partition in `_run_pattern_a_engine` | `layer4/plan_create.py` | grep + read | ✅ |
| `llm_call_count += 1` gated on `seam_idx not in cached_seam_indices` | `layer4/plan_create.py` | read | ✅ |
| `Layer4_Spec §9.2` now says iter-1 seam reviews ARE cached | `Layer4_Spec.md` | read | ✅ |
| New cron-budget test green | `tests/test_routes_plan_create.py` | pytest (37 passed) | ✅ |
| `TestIter1SeamReviewCache` (3) + updated per-phase/refresh assertions green | `tests/test_layer4_plan_create.py`, `tests/test_layer4_plan_refresh.py` | pytest | ✅ |
| Full suite → 1733 passed / 16 skipped | — | fresh `/tmp/venv` | ✅ |
| No new `layer4_cache` CHECK label needed (seam rows satisfy existing DDL) | `init_db.py` | read | ✅ |
| `CURRENT_STATE.md` last-shipped = this handoff; #182 demoted | `CURRENT_STATE.md` | read | ✅ |
| `CARRY_FORWARD.md` walk count +1 + new entry; `CLAUDE.md` Environment quick-reference added | `CARRY_FORWARD.md`, `CLAUDE.md` | read | ✅ |

## 9. Files shipped this session

**Substantive (code, 3 files):**
1. `routes/plan_create.py` (cron wall-clock budget)
2. `layer4/hashing.py` (`compute_seam_review_cache_key`)
3. `layer4/plan_create.py` (iter-1 seam-review cache)

**Spec:** `Layer4_Spec.md` (§9.2 in-place note).

**Tests:** `tests/test_routes_plan_create.py`, `tests/test_layer4_plan_create.py`, `tests/test_layer4_plan_refresh.py`.

**Bookkeeping (outside the ceiling):** `CLAUDE.md` (Environment quick-reference), `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
