# Plan-Gen D-77 — Per-Block Synthesis Budget Finding + Diagnostic Instrumentation — Closing Handoff

**Session:** Live-incident follow-up. Andy re-ran the coherence walk on the deployed wall-clock-backstop fix (#189) and it **still** failed with "Plan generation stalled." Pulled the prod runtime logs, found the real root cause (a single week-block's synthesis can't fit the 300s function cap because its capped-retry stack is non-resumable), put the fix decision to Andy at an `AskUserQuestion` gate, and — per his pick — shipped **diagnostic instrumentation only** (no behavior change) so the next re-run reveals *why* blocks retry before we commit to a fix.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_Slice2_BackstopWallClockFix_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/plan-generation-timeout-8s1Hn` (harness-pinned; name fits scope).
**PR:** opened this session.
**Status:** 1 code file (`layer4/per_phase.py`, logging-only) + 1 spec note (`Layer4_Spec.md §11.5`) + bookkeeping. Suite **1780 passed / 16 skipped** (unchanged — pure instrumentation). **No migration, no generation-behavior change.** The fix itself is DEFERRED to the next session pending the re-run's captured logs + Andy's approach pick.

---

## 1. The finding (root cause of the still-failing walk)

The predecessor fixed the Slice 2 backstop (per-call counter → wall-clock gate, `_STALL_WALLCLOCK_S=900`). That fix is **deployed and working** (current prod #190 stacks on #189). Andy re-ran the walk anyway and got the same "Plan generation stalled" message. The prod runtime log (deployment-scoped, clean negatives) for `plan_version_id=25` shows:

- **04:17:54** first `POST /plans/v2/25/generate`.
- **04:18:43 onward** — `synthesize_phase` (week-1 block) is reached almost immediately. 3A/3B were warm cache hits (from the earlier plans 22–24), so the **upstream cone was NOT the bottleneck** — the cone is not what eats the budget here.
- **04:17 → 04:31** — *every* generate pass (poller + cron) returns **504 with an `api.anthropic.com` call in flight**: the function hit its 300s cap mid-LLM-call, every time.
- **04:33:43** — the wall-clock backstop trips at ~960s (≈ the 900s window) with **zero week-blocks cached**.

**Root cause:** a single week-block's `synthesize_phase` (`layer4/per_phase.py:1457` retry loop) can fire **up to `capped_retries+1 = 3` sequential extended-thinking LLM calls** (and each `caller()` can itself add a forced-tool fallback call per #174 — so up to ~6 Anthropic calls), in an **in-memory loop that does NOT resume across function invocations**. The block caches only *after* the loop returns. So a block that needs retries (a schema-miss or a per-block validator rejection) runs ~300–450s+, gets 504-killed mid-loop, caches nothing, and the next pass **restarts that block from call 1** — an infinite 504 loop. The backstop now correctly converts that loop into a loud failure.

This is the **same failure mode as the original incident (`plan_version_id=23`)** that D-77 set out to kill. D-77 Slice 1 shrank the **cache unit** (phase → week) but did **not** bound a single block's **synthesis cost**, so "every unit fits the budget" is not actually true when a block retries. **The backstop is healthy; the unit still doesn't fit.**

## 2. Decision gate (Andy)

Put four approaches to Andy at an `AskUserQuestion` (plain-language second pass). Options offered: (A) wall-clock-bound the per-block retry loop → accept best-effort if time runs out (recommended); (B) lower `capped_retries`/thinking budget for blocks; (C) decompose finer than 1 week; (D) **add logging first** — instrument *why* block 0 retries before choosing a fix.

**Andy picked (D): add logging first.** So this session changes **no generation behavior** — it only adds the instrumentation needed to read the next run.

## 3. What shipped — `layer4/per_phase.py` (logging only)

All additions are `print()` lines (matching the existing runtime-log style; the same diagnostic precedent as #180/#182). They do **not** touch `render_user_prompt`, the tool schema, or any payload — so **no content-addressed cache key shifts** and no behavior changes. A greppable per-block `unit_tag` (`<phase>:w<week>` in block mode, else `<phase>:full-phase`) anchors every line.

- **`unit_tag`** computed alongside the unit-scope block.
- **Per-attempt LLM latency** — after each `caller()` returns: `synthesize_phase: <tag> attempt N/M llm call <ms>ms (in=… out=…)`. Reveals whether a SINGLE call is near the 300s cap or whether the retry STACK is the budget killer.
- **Parse-failure log** (was silent before the terminal raise): `… attempt N sessions did not parse (<ErrType>): <detail>`.
- **No-`sessions` log** — updated to the `unit_tag` + attempt numbering (was `phase_name`/`pass`).
- **Validator-rejection log (the key blind spot — was entirely silent):** `… attempt N validator rejected (K failure(s)): rule_a(blocker); rule_b(warning); …`. This is what tells us whether the retries are a fixable rule bug (à la #179/#181/#182/#186) or a genuinely-unsatisfiable plan.
- **Per-block summary** (fires only when the block RETURNS — a 504-killed block is traced via the per-attempt lines instead): `… done — K llm call(s), <ms>ms total, accepted=…, cap_hit=…, retries_used=…, sessions=…`.

## 4. Code / tests

Full suite **1780 passed / 16 skipped** (`/tmp/venv`; unchanged vs. the 1780 baseline — pure logging, no new tests warranted for `print` lines, and no existing `synthesize_phase` stdout assertions to break; only `tests/test_routes_plan_create.py` uses `capsys`, and it asserts the route's own log). `pyflakes layer4/per_phase.py` reports only a **pre-existing** `Observation imported but unused` (NOT introduced this session — no imports were touched; left for a `simplify` sweep).

## 5. Owed actions + manual verification

- **⚠ Owed (Andy's hands), in order:**
  1. **Redeploy** (merge this PR). No migration.
  2. **Re-run the PGE 2026 plan** (the same complex case). It will very likely **stall again** (we changed no behavior — this is expected; the goal is the logs, not a pass).
  3. **Send back the runtime log**, filtered to `synthesize_phase:` for the failing `plan_version_id` (Vercel runtime logs, deployment-scoped). What we're reading:
     - **Per-attempt latency** — is one call ~250–290s (a single call near the cap) or ~100–150s (the retry stack is the killer)?
     - **`validator rejected (… )` lines** — *which rules* fail, and do they repeat the same rule every attempt (→ likely a fixable validator/synthesis bug we can close like the #179–#186 chain) or vary?
     - **`returned no 'sessions'` / `did not parse`** — is the model declining/mis-emitting the tool under extended thinking (#174/#182 territory)?
- That read picks between the deferred fixes below.

## 6. Next session — the fix decision (deferred, Andy-gated)

Once the logs are in hand, pick the fix. Options as framed at the gate (all are Trigger #5 / some Trigger #1):
1. **Wall-clock-bound the per-block retry loop** (my recommendation): in `synthesize_phase`, track elapsed wall-clock; before firing another retry, if a per-block budget (~200s, headroom under the 300s cap) is spent, stop and accept the **best parseable attempt so far** as best-effort (`cap_hit` → `best_effort_plan` observation, `elevates_to_hitl=True` — the existing §5.5 demotion semantics). Guarantees a block returns within budget → always caches → monotonic convergence; preserves retries when they fit. Trade-off: a block that can't validate in time is accepted best-effort (HITL-flagged), not retried forever. Guard: only accept a parseable attempt; if even attempt 1 is a schema-miss and time's up, that's still a terminal `schema_violation`.
2. **Lower `capped_retries_per_phase` (2→1) and/or `extended_thinking_budget` for block mode** — blunt knob; lowers quality for every plan; one forced-tool retry can still push a single retry over.
3. **Decompose finer (sub-week / day-range)** — more, cheaper units, but the retry multiplier still applies per unit, so it mitigates rather than eliminates; bigger change, more seams.
4. **If the logs show a specific repeating validator rule**, the cleanest first move may be to **fix that rule/synthesis bug** (block passes in 1 call → caches) — but the structural budget-bound (option 1) is still the robust backstop against the *next* such bug, so do both.

Then: the still-open **decomposition coherence** question (design §14 — do independently-generated weeks blend?) and **Slice 3** (intra-phase week-seam stitcher, own Trigger #1) remain after convergence is actually reached.

## 7. Operating notes for next session (read order, Rule #13)

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what shipped (this instrumentation) + the deferred fix.
3. `aidstation-sources/CARRY_FORWARD.md` — the D-77 entry (the per-block-budget UPDATE + the re-run-for-logs step).
4. `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` — the design (the §14 coherence gut check; Slice 3).
5. This handoff + the wall-clock-fix predecessor.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 8. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Diagnose before fixing — add logging, re-run, read, then pick | Andy (gate) | The per-block retry could be a fixable validator bug (1-call cache) or a genuine cost problem; the right fix differs. The redeploy/re-run loop is expensive, so spend one cycle to know rather than guess. |
| **D2** | Root cause = per-block synthesis cost (non-resumable capped-retry stack > 300s), NOT the backstop and NOT the upstream cone | Claude (log-driven) | Prod log for plan 25: 3A/3B warm (cone fast), block synthesis reached immediately, every pass 504s mid-Anthropic-call, zero blocks cached in ~900s. Only the block loop fits that shape. |
| **D3** | Instrumentation is `print`-only, no prompt/schema/payload touch | Claude (constraint) | Keeps content-addressed cache keys stable + zero behavior change, so the re-run reproduces the exact same path with visibility added. |

## 9. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `unit_tag` added | ✅ `layer4/per_phase.py` (`<phase>:w<week>` / `:full-phase`) |
| Per-attempt latency log | ✅ after `caller()` — `attempt N/M llm call <ms>ms` |
| Validator-rejection log (was silent) | ✅ on `not validator_result.accepted` — lists `rule_name(severity)` |
| Parse-failure + no-`sessions` logs | ✅ parse-failure now logged; no-`sessions` uses `unit_tag` |
| Per-block summary | ✅ before `return PhaseSynthesisResult(...)` |
| No behavior change / no cache-key shift | ✅ `print`-only; `render_user_prompt`/tool schema/payload untouched |
| Spec note | ✅ `Layer4_Spec.md §11.5` — per-block synthesis-cost limitation + the diagnostic logging |
| Full suite | ✅ 1780 passed / 16 skipped (unchanged) |
| Backlog + changelog | ✅ `Project_Backlog_v62.md` D-77 row + 2026-05-27 changelog entry |
| `CURRENT_STATE.md` pointer flipped | ✅ → this file; wall-clock fix demoted to predecessor |

## 10. Files shipped this session

**Substantive (2):** `layer4/per_phase.py` (logging-only), `aidstation-sources/Layer4_Spec.md` (§11.5 note).
**Bookkeeping:** `Project_Backlog_v62.md`, `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

**End of handoff.**
