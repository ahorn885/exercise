# V5 Implementation — Plan-Gen Six-Link Failure Chain: Diagnose→Decompose→Timeout→Rebind (2026-05-30) — Closing Handoff

**Session:** A single live-debugging arc that took plan generation from "fails with a generic stall" to **synthesizing a complete, coherent PGE plan** — by excavating and fixing **four distinct blockers in sequence**, each of which masked the next. Watched live prod runs pv=41→45 via the Vercel runtime logs + the `/admin/plan/<id>/inspect` view, root-causing each failure from its actual traceback/`generation_error` rather than guessing.

**Five PRs merged + one open:** #329 (diagnostic instrumentation + deterministic-retry fast-fail), #330 (seam re-synth → resumable week-blocks, D-77 Slice 3), #331 (pin SDK request timeout), **#332 (rebind `plan_version_id` on per-block cache hits + persist guard — OPEN, CI-green, awaiting merge)**. All app code is deployed-on-cold-start. **No migration.**

**Headline:** pv=45 ran the seam re-synthesis through all four Build weeks at the correct 21,600 ceiling, produced genuinely good programming (deload week lighter, Z4 ramp-in, wrist-aware climbing), and died only at the **final DB persist** on a `UniqueViolation` — the sixth and (believed) last link, fixed by #332. The *mechanism* is proven end-to-end; #332 removes the last plumbing gap.

---

## 1. The chain — what failed, in order, and why each masked the next

Each fix exposed the next failure because the prior one was the first thing to break. The throughline: **block output budgets grew across the session (#327's 21,600 ceiling), and that growth crossed thresholds that had never been crossed before.**

1. **pv=41 — opaque 15-min stall (fixed: #329).** A deterministic `schema_violation` on block 0 was retried into the 900s wall by #325, surfacing only "contact support." Root issue: the failing attempt's usage was discarded, so the cause was unfalsifiable from logs.
   - **#329:** (a) `llm_invocation.py` now folds the failing attempt's `output_tokens / ceiling / thinking / kind` into the terminal `schema_violation` detail (env-gated `PLAN_GEN_LOG_FAILED_ATTEMPT=1` also captures a text prefix); (b) `routes/plan_create.py` persists the real `code: detail` to `generation_error` each pass AND **fails fast** when the identical detail repeats with 0 cached blocks (kills the 15-min silent stall — the #325 design flaw).

2. **pv=42 — `ceiling=4000`, the truth (diagnosed via #329).** The instrumentation immediately showed the failing call ran at **ceiling=4000, NOT 21,600**. 4000 = the raw whole-phase `DEFAULT_MAX_TOKENS`, reached only via the `week_range=None` branch = the **seam-driven re-synthesis path**. When a seam review flagged a phase boundary, the engine re-synthesized the WHOLE phase in one 4000-token call → truncation → `schema_violation`. **This is why #327's 21,600 bump "did nothing"** — #327 sized block mode only; the seam path never used it. And why runs differed: whether a seam fires is **stochastic** (depends on the reviewer flagging a boundary that pass), not on block sizing. Andy's original instinct ("a token bump can't be the cure") was correct.

3. **pv=43/44 — `ValueError: Streaming is required` (fixed: #331).** With the seam path decomposed into 21,600-ceiling week-blocks (#330), the thinking attempt sent `max_tokens + thinking_budget = 21,600 + 5,000 = 26,600`. The Anthropic SDK auto-derives a non-streaming timeout and **refuses** any call where `(3600 × max_tokens) / 128000 > 600`, i.e. `max_tokens > 21,333` — an **untyped `ValueError`** thrown before the HTTP call, escaping the typed-error contract → generic "failed unexpectedly." A **latent landmine**: pv=39 (18,800) and the old seam path (9,000) sat under it by luck; #330 was the first change to cross it. The forced-retry path (21,600) clears it too, so primary blocks were equally exposed.
   - **#331:** construct the Anthropic client with an explicit `timeout` AND pass it per-request (`llm_invocation.py`). The guard only fires when `timeout` is unset and the client timeout is the SDK default; a concrete value disables it across SDK versions for every caller. 600s default, env override `LLM_REQUEST_TIMEOUT_S`. Verified empirically against the installed SDK.

4. **pv=45 — `UniqueViolation` at persist (fixed: #332, OPEN).** 5 blocks synthesized, seam re-synth ran clean through Build w1–w4, then crashed at the final persist: `duplicate key (plan_version_id, date, session_index_in_day)=(39, 2026-06-27, 0)`. A session being saved under **pv=45** carried id **39**. Root cause: the §9.2 per-block cache key folds in only the athlete **inputs** (via `call_cache_key`), NOT the `plan_version_id` — so the same cached block is shared across plan versions, but the cached payload stamps each session with the **synthesizing** run's id. The whole-payload cache path rebinds on a hit (`_rebind_payload_dict`, §9.4); the **per-block** hydrate path (`_hydrate_phase_result_with_meta`) did **not**. So pv=45 replayed pv=39's cached blocks and persisted sessions still stamped 39 → collided with pv=39's own rows. **Shared by both the primary block loop AND the #330 seam loop;** pv=45 was simply the first plan to reach persist while an older version's blocks sat in the cache (every earlier run crashed upstream first).
   - **#332:** (a) **root cause** — `_hydrate_phase_result_with_meta` now rebinds `plan_version_id` on every hydrated session to the current run's id (mirrors §9.4); covers both call sites. Rebinds at **read** time, so the already-poisoned cache **self-heals on the next hit** — no purge needed. (b) **safety net** — `persist_layer4_sessions` writes every row under `payload.plan_version_id` (not the per-session id) and re-stamps the stored `payload_json`, so a stale id can't reach the table from any future path; a mismatch is logged.

---

## 2. The structural win — #330 (D-77 Slice 3, seam re-synth decomposition)

The spec's intended scaling path for seam re-synthesis (deferred since the D-77 design as "the week-seam stitcher"). Replaces the single whole-phase seam re-synth call (4000-token ceiling, no resume) with a **week-by-week loop** mirroring the primary block loop:

- Each seam-fix block gets `week_range` (→ the 21,600 block-mode budget) + the `seam_issues`/`seam_direction` constraints.
- **Cache-wired** under a seam-aware key (`compute_seam_resynth_block_cache_key`, folds in `seam_index` + issues + direction) in a **disjoint `phase_idx` band `[500, 1000)`** (`_seam_resynth_block_phase_idx`) — kept BELOW `_SEAM_CACHE_PHASE_IDX_BASE=1000` ON PURPOSE so the stall-backstop progress counter (`_count_cached_blocks` / `_generation_stalled`, which count `[0, 1000)`) sees seam-fix blocks as progress → **no route SQL change**.
- **Budget-gated + resumable** via the same `Layer4GenerationIncomplete` control-flow signal as the primary loop; aggregated back via `_aggregate_block_results`.

pv=45 proved this works in prod: seam blocks 500–503 cached real, coherent weeks.

---

## 3. Issues / state

- **#324** (open) — plan-gen completion blocker. Its **truncation half** (#327) + **seam-path half** (#330) + **diagnosability** (#329) + **SDK guard** (#331) + **rebind** (#332) are now all addressed. Once #332 merges and a run reaches `ready`, #324 is effectively closed pending that proof.
- **#316** (open, `status:designed`) — the per-week pre-compute periodization grid (latency cure). Unchanged; still Andy's call (pre-compute, not shrink blocks). pv=45 showed blocks taking the full 120s per-block budget (`synthesis_budget_exhausted` non-fatal, resumes) — so latency is still real, but it's #316 territory, not a crash.
- **Per-block budget tightness (watch-item, not filed):** every pv=45 seam block was `cap_hit` (validator never fully passed; best-effort accepted) and one block hit the 120s budget. Non-fatal (resumes), but worth watching whether a heavy plan ping-pongs on the budget vs converges. Tied to the 300s function cap → the 120s per-block budget is about as much as a block gets.
- **#325 deterministic-retry flaw** — addressed by #329's fast-fail (identical detail + 0 cached blocks → fail fast with the real code).
- **Cap-config drift** (`reserve 330 > live cap 300` → `_INVOCATION_BUDGET_S` floors to 30s) — still latent, still deferred (never fired in any run this session).

---

## 4. Open / owed / next

**Owed (Andy's hands): merge #332, redeploy, run ONE more PGE plan.** This is the proof run for the whole chain. Expect: primary blocks cache (idx 0..N), a seam fires → seam blocks cache in `[500, 1000)`, no `ValueError`, no `UniqueViolation`, plan → **`ready`**. Watch via `/admin/plan/<id>/inspect`.
- **If it reaches `ready`** → the six-link chain is closed; plan-gen is **functional end-to-end**; the go-live blocker (#324) clears; #316 becomes a schedulable speed optimization.
- **If it stalls on the 120s per-block budget** (blocks cache but it never finishes) → that's the **latency** wall (#316), not a crash — the next fix is the pre-compute grid or a budget/cap reconciliation, NOT another bug hunt.
- **If a NEW failure surfaces** → it'll now be **diagnosable** (#329 persists the real `generation_error`; the catch-all logs a full traceback). Send back the inspect `generation_error` + the traceback.

**Honest note for next session:** this was six consecutive "fix → new failure" cycles. Two of the six (#330's missing rebind = #332; the seam-path 4000 ceiling pre-existed but #330's decomposition is what surfaced the SDK guard) trace to gaps in this session's own work — the rebind was a genuine miss (a new cached-block path wired without the §9.4 rebind the codebase already had). The remaining surface after persist (status flip → done) is small and not LLM-dependent, so a `ready` is plausible — but do not *assume* it; the pattern all session was that each blocker hid the next.

**Do NOT pre-build #316 or any further hardening** — the proof run decides what (if anything) is next.

---

## 6.3 Operating notes — session-start reads (Rule #13)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling carry-state (owed = merge #332 + the proof run).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

**First move next session:** confirm #332 merged, then the proof run (above). If it's `ready`, the focus shifts off the convergence/completion blocker for the first time in ~15 sessions — to coherence verification (design §14: do the weeks blend?) and then #316 latency, or new functionality per the 4-tier order.

---

## 8. Verification table (Rule #10 — file:line anchors for the next Rule #9 sweep)

| Claim | File | Anchor / check |
|------|------|------|
| Failing-attempt diagnostics in terminal error | `llm_invocation.py` | `last_attempt_output_tokens=` in the `schema_violation` detail; `last_miss` dict |
| Env-gated failed-attempt text prefix | `llm_invocation.py` | `PLAN_GEN_LOG_FAILED_ATTEMPT` |
| Deterministic block-fumble fails fast | `routes/plan_create.py` | `prior_err == fumble_detail and now_cached == 0` → `_mark_plan_failed` |
| Fumble detail persisted live to generation_error | `routes/plan_create.py` | `UPDATE plan_versions SET generation_error = ?` in the `block_retry_resume` branch |
| Seam re-synth decomposed into week-blocks | `layer4/plan_create.py` | `while rs_week <= target_phase.weeks:` + `_synth_seam_block` with `week_range=_wr` |
| Seam-resynth cache key folds in the seam | `layer4/hashing.py` | `compute_seam_resynth_block_cache_key` (folds `seam_index`, `seam_issues`, `seam_direction`) |
| Seam-resynth phase_idx band [500,1000) | `layer4/plan_create.py` | `_SEAM_RESYNTH_BLOCK_IDX_BASE = 500`; `_seam_resynth_block_phase_idx` asserts `< _SEAM_CACHE_PHASE_IDX_BASE` |
| Explicit SDK request timeout (client) | `llm_invocation.py` | `anthropic.Anthropic(api_key=api_key, timeout=request_timeout_s)` |
| Explicit SDK request timeout (per-request) | `llm_invocation.py` | `"timeout": request_timeout_s` in `request_kwargs`; env `LLM_REQUEST_TIMEOUT_S` |
| Cache-hit rebinds plan_version_id (root cause) | `layer4/plan_create.py` | `_hydrate_phase_result_with_meta(..., plan_version_id=plan_version_id)` → `.model_copy(update={"plan_version_id": ...})` |
| Persist writes under payload id (safety net) | `plan_sessions_repo.py` | `payload.plan_version_id` in the INSERT params (not `session.plan_version_id`); mismatch `print` |

PRs merged this session: **#329, #330, #331** (to `main`). **#332 OPEN, CI-green.** Suite at session end: **1845 passed / 16 skipped** (on the #332 branch). No migration.
