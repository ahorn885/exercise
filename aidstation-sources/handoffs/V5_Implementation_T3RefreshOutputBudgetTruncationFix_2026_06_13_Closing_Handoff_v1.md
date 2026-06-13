# V5 Implementation — T3 plan-refresh truncation fix: size synthesis output budget to the session ceiling (PR #572)

**Date:** 2026-06-13
**Branch:** `claude/adoring-mccarthy-su0igw`
**PR:** [#572](https://github.com/ahorn885/exercise/pull/572) — squash-merged to `main`
**Issue:** none closed — this is the live-verify follow-up owed by the #569 handoff. Two optional follow-ups filed: [#574](https://github.com/ahorn885/exercise/issues/574), [#575](https://github.com/ahorn885/exercise/issues/575).

> **Read order (Rule #13):** this handoff → `CURRENT_STATE.md` top entry → `CARRY_FORWARD.md`. This session ran the owed live T3-refresh re-verify from #569, found the #569 fix works **and** that it exposed a *second* shipping bug (output-token truncation), fixed it, and shipped. Same shape as #569: the live verify did its job and caught a real, deterministic bug.

---

## 1. What this session was

The #569 handoff left one owed item: a live re-verify of a **T3** refresh on prod to confirm the new pv reaches `generation_status=ready` with a phase-correct `total_sessions`. Andy ran a T3 refresh of pv=65; the new row is **pv=67**. I watched it via the Vercel runtime-log MCP-adjacent **token-gated `/admin/plan/<id>/diag`** endpoint (the authoritative read; `print()` failures log as `info`, invisible to the runtime-log `level=error` sweep — Rule #14).

## 2. What the watch found (the split result)

- **#569 fix — CONFIRMED LIVE.** pv=67 is `created_via=plan_refresh_t3` and **cleared `_validate_inputs`** — no `plan_start_date_missing`. T3 refresh now reaches real synthesis. The bug we shipped #569 to fix is gone.
- **NEW bug — T3 synthesis truncates at its output ceiling.** Stable across four diag reads (04:06→04:13):
  ```
  schema_violation: model did not emit a record_refresh_sessions tool_use block
  (stop_reason=max_tokens); last_attempt_output_tokens=10000/ceiling=10000
  thinking=0 kind=empty_tool_args
  ```
  pv=67 never reached `ready` — it stayed `generation_status=generating`; the every-minute cron re-acquired the advance lock (`advance_lock_until` rolled 04:12:23 → 04:24:54) and re-attempted, deterministically truncating each pass (frozen inputs + fixed ceiling = no convergence). `blocks_snapshotted=0`, `total_sessions=0` throughout.

## 3. Root cause

The refresh tiers carried **flat per-tier output budgets** that never absorbed the two lessons the create path (`per_phase.py`, D-77) learned the hard way:

| Path | max_tokens | thinking | sessions | tokens/session |
| --- | --- | --- | --- | --- |
| Refresh T1 | 2000 | 3000 | ≤4 | ~500 |
| Refresh T2 | 4000 | 4500 | ≤14 | ~285 |
| **Refresh T3 (before)** | **10000** | 6500 | **≤56** | **~178** |
| Create (`per_phase`) | **~1400 × N** (scales) | **0** | decomposed | **1400** |

`per_phase.py` settled on `_BLOCK_OUTPUT_TOKENS_PER_SESSION = 1400` (raised 600→900→1400 across pv=38/40) and **zeroed thinking** (the pv=58/59 lesson: the thinking attempt starves the forced-tool output budget). The T3 refresh asked the model to emit **up to 56 sessions in one `record_refresh_sessions` call** on a flat 10k budget — ~178 tok/session, ~8× under the tuned rate — so it truncated before closing the tool-call JSON. Not a #569 regression: this path had its own flat constant from the start; #569 was the first time T3 got *past* validation to hit it.

## 4. The fix (PR #572 — 4 files) — reuse the create-path balancing (Andy's call)

Andy's direction: *"reuse the same balancing that a new plan gen does."* Not decomposition (that's the parked follow-up #574) — the per-session output sizing + thinking-off.

- **`layer4/per_phase.py`** — new **`block_output_budget(max_sessions, floor=0)`**: `max_sessions × _BLOCK_OUTPUT_TOKENS_PER_SESSION + _BLOCK_OUTPUT_TOKENS_OVERHEAD`, never below `floor`, **clamped to `_MODEL_MAX_OUTPUT_TOKENS = 64000`** (the `claude-sonnet-4-6` per-request output ceiling — confirmed via the claude-api skill). The create block-mode `effective_max_tokens` now calls it — **behavior-preserving** (create's per-week blocks are ≤21,600, so the clamp is a no-op there). Exported in `__all__`.
- **`layer4/plan_refresh.py`** — lifted `_TIER_MAX_SESSIONS = {"T1": 4, "T2": 14, "T3": 56}` to a module constant (also feeds the tool schema's `maxItems`); the driver `llm_layer4_plan_refresh` now sizes `effective_max_tokens = block_output_budget(_TIER_MAX_SESSIONS[tier], floor=<caller-or-tier-default>)`. **T1 = 7,600 / T2 = 21,600 / T3 = 80,400 → clamped to 64,000.**
- **`layer4/plan_refresh_t3.py`** — `DEFAULT_EXTENDED_THINKING_BUDGET` **6500 → 0**. Required: under extended thinking the API request ceiling is `max_tokens + thinking_budget`, so a 64K output budget + a 6500 thinking budget would exceed the model limit (a 400). Thinking off = the forced tool gets the whole 64K (mirrors `per_phase`). T1/T2 keep their thinking (their budgets + thinking stay well under 64K; they don't hit the ceiling).
- **`tests/test_layer4_plan_refresh.py`** — updated the T3 budget-capture test (now 64000/thinking 0) + new `TestOutputBudgetSizing` (helper scale/clamp/floor + T1 driver sizing).

**Orthogonality kept:** this only raises the *output ceiling* (a cap; billed/latency cost tracks tokens actually emitted). T1/T2 behavior is unchanged apart from the larger headroom.

## 5. Verification

- Full suite **2366 passed / 30 skipped** locally (+4 net new tests over the 2362 baseline).
- CI green on PR #572: Python unit suite ✅, Layer 0 integrity gate ✅, JS harness ✅, Vercel preview ✅; Real-LLM smoke skipped (expected).
- **Owed — live T3 re-verify (Andy's hands, post-merge):** re-run a T3 refresh on prod → confirm the new pv reaches `generation_status=ready` with a phase-correct `total_sessions` (diag token). This fix resolves realistic ~20–35-session 4-week windows (≈28–49k output, under 64K).

## 6. Owed / next move

- **No Neon migration owed** — code-only fix.
- **Live T3 re-verify** (above) is the only follow-up for *this* fix.
- **Two optional/contingent follow-ups filed** (build only if the trigger fires — `status:deferred`/`priority:low`):
  - **[#574](https://github.com/ahorn885/exercise/issues/574)** — decompose T3 refresh into per-week blocks (the create-path D-77 machinery we did *not* port; the refresh is single-call Pattern B). Trigger: a dense ≥~46-session 4-week window truncates at the 64K clamp post-#572.
  - **[#575](https://github.com/ahorn885/exercise/issues/575)** — per-pass give-up backstop so a deterministic *retryable* refresh failure stops the cron re-driving it (the reason pv=67 cron-looped instead of cleanly failing; create has `_PER_BLOCK_BUDGET_MS`, refresh doesn't). Adjacent to #539. Trigger: any retryable refresh failure recurs cron-looping post-#572.
- **Next live candidates** (unchanged): the **#541/#542/#543** plan-quality batch (shallow strength / low-protein macros / structured health conditions), then the **compliance build-out** (epics #353/#355/#356/#359). #573 (refresh strength-failover lighting) + #557 tail are adjacent refresh-path work.

## 6.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry is this PR (#572); current focus = #541/#542/#543 + compliance.
3. `CARRY_FORWARD.md` — rolling carry-state (the T3-refresh saga section: owed = post-#572 live re-verify; optional #574/#575).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

**Diag-token recipe (used this session):** read any plan's generation state past the app login wall via the Vercel MCP — `web_fetch_vercel_url("https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=<DIAG_TOKEN>")` → JSON with `created_via` / `generation_status` / `generation_error` / `generation_traceback` / `total_sessions` / `advance_lock_until`. `DIAG_TOKEN` is in §6.1.1 of the 2026-05-31 DiagAuthGate handoff. Direct container curl is egress-blocked; the MCP fetch is the path. The runtime-log MCP `level` filter misses `print()`-based failures (they're `info`) — the diag endpoint is authoritative (Rule #14).

## 7. Stop-and-asks this session

- **Fix approach (which create-path machinery to reuse)** was surfaced to Andy before implementing — three options (raise+rebalance budget / decompose per-week / just log it). Andy chose **reuse the create balancing** (option 1); decomposition (option 2) was filed as optional #574. No prompt-body change (the budget is sampling config, not Trigger #1); the budget/thinking tradeoff was the Trigger-#5 surface.
- **Model output ceiling** (64K) was looked up via the claude-api skill, not guessed (the LLM-limits trigger).

## 8. §8 anchor table (Rule #10)

| Area | Path | Anchor / check |
| --- | --- | --- |
| Budget helper (new) | `layer4/per_phase.py` | `def block_output_budget(` + `_MODEL_MAX_OUTPUT_TOKENS = 64000` |
| Create reuse | `layer4/per_phase.py` | block-mode `effective_max_tokens = block_output_budget(max_sessions_this_unit, floor=max_tokens)` |
| Tier ceiling map | `layer4/plan_refresh.py` | `_TIER_MAX_SESSIONS = {"T1": 4, "T2": 14, "T3": 56}` |
| Driver sizing | `layer4/plan_refresh.py` | `effective_max_tokens = block_output_budget(_TIER_MAX_SESSIONS[tier], floor=floor)` |
| T3 thinking off | `layer4/plan_refresh_t3.py` | `DEFAULT_EXTENDED_THINKING_BUDGET = 0` |
| Tests | `tests/test_layer4_plan_refresh.py` | `class TestOutputBudgetSizing`, `test_intra_phase_t3_sizes_output_budget_to_session_ceiling` |
