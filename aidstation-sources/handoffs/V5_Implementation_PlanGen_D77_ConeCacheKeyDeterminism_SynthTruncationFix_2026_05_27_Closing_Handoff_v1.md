# Plan-Gen D-77 — Non-Convergence Root Cause Fixed (Cone Cache-Key Determinism + Synthesizer Truncation + Per-Block Budget) — Closing Handoff

**Session:** Live-incident close. Andy re-ran the plan on the deployed instrumentation build (#192) and got the same "Plan generation stalled" — but now the `synthesize_phase` logs were captured. Read the prod logs for `plan_version_id=27`, pinned the stall to TWO independent bugs, put the fix to Andy at an `AskUserQuestion` gate (he chose "investigate the cone first", then "fix both together"), and shipped both fixes + the structural backstop.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_PerBlockBudget_Instrumentation_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/plan-gen-timeout-logs-caH8Q`
**PR:** opened this session.
**Status:** 4 substantive code files + 4 test files + `Layer4_Spec §11.5` (in place) + bookkeeping. Suite **1793 passed / 16 skipped** (+13). **No migration. No generation-behavior change to cache-key inputs other than day-anchoring two provenance timestamps.** The fix is DEPLOY-then-RE-RUN gated (owed Andy's hands).

---

## 1. The finding (root cause of the still-failing plan)

The instrumented re-run produced exactly one full `synthesize_phase` block trace before the 504 (prod, deployment `dpl_9kFGGhBa1MYhMAEeyvStAiKXrr8m`, `plan_version_id=27`):

```
06:25:11.802  synthesize_phase: Build:w1 attempt 1/3 llm call 142528ms (in=6896 out=9000)
06:25:11.802  synthesize_phase: Build:w1 attempt 1 returned no 'sessions' array (tool_args keys=[])
06:25:19.667  Vercel Runtime Timeout Error: Task timed out after 300 seconds
```

Two independent bugs, both of which independently break convergence:

### Bug 1 — cache keys are non-deterministic across function invocations (the primary bug)

`Layer1Payload.as_of` (`layer1/builder.py`) and `Layer2APayload.rationale_metadata.generated_at` (`layer2a/builder.py`) were stamped with a **full-precision `datetime.utcnow()`** and hashed into `layer1_hash` / `layer2a_hash`. Those two hashes fold into **every** Layer 4 cache key: `layer3a_athlete_state_key`, `layer3b_goal_timeline_viability_key`, `compute_block_cache_key`, `plan_create_key`, `plan_refresh_key`, `single_session_synthesize_key`, `race_week_brief_key` (all via `layer4/hashing.py`). So every resumable pass computed a **different key for the same work**:

- **3A + 3B re-ran cold on every pass** — proven empirically: the live-run-only `Layer3AEvidenceBasisWarning` and `Layer3BEvidenceBasisWarning` (emitted by the builder on a real run, never on a cache hit) appeared in **17/17** generate + cron passes from 06:11→06:26, each burning ~150s of the 300s budget before the synthesizer even started.
- Any block the synthesizer did produce would get a **new key next pass** → orphaned → re-synthesized → never reused.

So D-77's "each pass caches ≥1 unit → monotonic convergence" premise was **structurally impossible**. This is why per-week decomposition never helped — a smaller unit still got a fresh key every pass. **It also overturns the predecessor's plan-25 read ("3A/3B were warm cache hits, cone NOT the bottleneck")** — that was an assumption made without per-layer cache instrumentation; the cone has never cached across passes.

Neither `as_of` nor `generated_at` is consumed anywhere (grep for reads of `.as_of` / `.generated_at` → none) — pure build provenance.

### Bug 2 — the synthesizer starves its own output on the thinking budget

`out=9000` is exactly `max_tokens(4000) + extended_thinking_budget(5000)`. Under extended thinking the request ceiling is their sum; the model spent the entire budget thinking and emitted a **contentless tool call** (`tool_args keys=[]`, `stop_reason=max_tokens`). The block never produced sessions → never cached → 504-loop. The single attempt took **142s** (thinking), so the retry stack also can't fit 3× in 300s.

`invoke_tool_call`'s forced-tool fallback (the #174 thinking-miss path) did NOT catch this — it only fired on a *fully missing* tool_use block, and here a block was present but empty.

## 2. The decision gate (Andy)

`AskUserQuestion` ×3: (a) which synthesizer fix → Andy: "tell me how to find the log"; provided the Vercel dashboard steps; (b) after the log → Andy: "**investigate the cone first**" (which surfaced Bug 1); (c) after the full investigation → Andy: "**fix both together**". So this session fixes both bugs + the structural backstop in one PR.

## 3. What shipped

**Bug 1 fix — `layer1/builder.py` + `layer2a/builder.py` (cone cache-key determinism).** Both timestamps are day-anchored (`.replace(hour=0, minute=0, second=0, microsecond=0)`), matching the Layer 3A `as_of` day-granular cache semantics. Same-day re-builds now hash identically → 3A/3B cache after pass 1, blocks cache, convergence becomes possible. Pure-provenance fields, so only the hash is affected (no consumer change).

**Bug 2 fix — `llm_invocation.py` (forced-tool escalation on empty tool call).** A `tool_use` block with empty `input` (`tool_args == {}`) is now treated like a missing block, so the existing forced-tool retry fires (thinking off → the full `max_tokens` is available for output, and a forced `tool_choice` the model cannot decline). The fallback log line is updated to "absent or empty". This is a no-op for the in-budget=0 callers and for non-empty tool calls.

**Structural backstop — `layer4/per_phase.py` (`_PER_BLOCK_BUDGET_MS = 120_000`).** A per-block budget guard at the top of the retry loop: once a block's accumulated LLM latency (`total_latency_ms`) meets the budget, it will not START another extended-thinking attempt — it accepts the best parseable attempt as best-effort (`cap_hit=True`, so the block caches and the plan progresses) or, with no parseable attempt, raises `Layer4OutputError("synthesis_budget_exhausted")` (fast terminal). The first attempt is never gated. Guarantees a block RETURNS within the 300s cap instead of 504-looping. Also corrected the now-disproven "max_tokens is ample headroom" comment in `synthesize_phase`.

## 4. Code / tests

Full suite **1793 passed / 16 skipped** (`/tmp/venv`; +13 vs. the 1780 baseline):
- `tests/test_layer4_thinking_request.py` — `test_empty_tool_call_falls_back_to_forced` + `test_empty_tool_call_both_attempts_raises`, each parametrized over the 5 Layer 4 callers (×10).
- `tests/test_layer1_builder.py::TestCacheKeyDeterminism::test_as_of_day_anchored_so_layer1_hash_is_stable` — two same-day builds at different sub-day clocks hash identically.
- `tests/test_layer2a.py::TestCacheKeyDeterminism::test_generated_at_day_anchored_so_layer2a_hash_is_stable` — same for 2A.
- `tests/test_layer4_plan_create.py::TestPerBlockBudgetGuard::test_budget_guard_terminal_when_no_parseable_attempt` — the guard blocks the 2nd attempt and raises `synthesis_budget_exhausted` (only 1 caller invocation).

`pyflakes` on the 4 changed code files reports only **pre-existing** findings (`layer2a/builder.py:457 rows_by_id` unused; `layer4/per_phase.py:50 Observation` imported-unused — the latter was already flagged in the predecessor handoff). Neither introduced this session.

## 5. Owed actions + manual verification

- **⚠ Owed (Andy's hands), in order:**
  1. **Redeploy** (merge this PR). No migration — the day-anchoring only changes how the payloads are hashed; existing cone cache rows simply re-run once under the new (now stable) key, then stick.
  2. **Re-run the PGE 2026 plan** (the same complex case). **Expect it to CONVERGE now** — this is the first run where progress is reusable across passes.
  3. **Confirm + (if it stalls) send back the `synthesize_phase:` log** for the failing `plan_version_id`. What to look for:
     - `synthesize_phase: <phase>:w<n> done — K llm call(s), …ms total, accepted=…` — this **per-block summary has NEVER fired** (no block ever returned); it firing is the proof a block cached.
     - 3A/3B should NOT re-run every pass — the `Layer3A/3BEvidenceBasisWarning` lines should appear at most once (pass 1), then the cone replays from cache.
     - If a forced-tool retry truncates a dense ~14-session week against `max_tokens=4000` alone (watch `out=` near 4000 on a `tool_choice:{type:tool}` request), the follow-on is bumping block-mode `max_tokens` (see §6).

## 6. Next session — the deferred follow-on(s)

1. **Residual: block-mode `max_tokens` headroom (watch-item, only if the re-run shows it).** The escalation gives the forced retry the full 4000 output tokens (no thinking reservation), which should hold a typical week. If a dense 14-session week truncates against 4000 anyway, raise block-mode `max_tokens` (and/or trim the block thinking budget). The per-block budget guard keeps such a block failing fast, not 504-looping, in the meantime. Data-gated — don't pre-tune.
2. **Coherence (design §14, still UNVERIFIED).** Once a plan reaches `ready`, open it and read across week boundaries WITHIN a phase — do the independently-generated weeks blend (gentle ramp, planned recovery), or show cliffs/duplication? If they don't blend, the seam to cut may be wrong (a design redo, not a tuning knob) — report before Slice 3.
3. **Slice 3** (intra-phase week-seam stitcher; own Trigger #1 prompt pass) remains after convergence + coherence are confirmed.

## 7. Operating notes for next session (read order, Rule #13)

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what shipped (this fix) + the owed redeploy/re-run.
3. `aidstation-sources/CARRY_FORWARD.md` — the D-77 entry (now ✅ root-cause-fixed; prior chain marked superseded).
4. `aidstation-sources/Layer4_Spec.md §11.5` — the root-cause + fix record.
5. This handoff + the instrumentation predecessor.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 8. Session-end verification (Rule #10)

| Check | Result | Anchor / method |
|---|---|---|
| Layer 1 `as_of` day-anchored | ✅ | `layer1/builder.py` — `as_of=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)` |
| Layer 2A `generated_at` day-anchored | ✅ | `layer2a/builder.py` — `generated_at=datetime.utcnow().replace(...).isoformat()` |
| Empty tool call → forced retry | ✅ | `llm_invocation.py` — `if not tool_args: return None, stop_reason` |
| Per-block budget constant | ✅ | `layer4/per_phase.py` — `_PER_BLOCK_BUDGET_MS = 120_000` |
| Per-block budget guard | ✅ | `layer4/per_phase.py` — `if pass_offset > 0 and total_latency_ms >= _PER_BLOCK_BUDGET_MS:` → best-effort `cap_hit` or `raise Layer4OutputError("synthesis_budget_exhausted")` |
| Hash-determinism tests | ✅ | `tests/test_layer1_builder.py::TestCacheKeyDeterminism`, `tests/test_layer2a.py::TestCacheKeyDeterminism` |
| Escalation tests | ✅ | `tests/test_layer4_thinking_request.py::test_empty_tool_call_falls_back_to_forced` + `..._both_attempts_raises` |
| Budget-guard test | ✅ | `tests/test_layer4_plan_create.py::TestPerBlockBudgetGuard` |
| Spec note | ✅ | `Layer4_Spec.md §11.5` — "Non-convergence root cause + fix (2026-05-27, RESOLVED)" |
| Full suite | ✅ | 1793 passed / 16 skipped (`/tmp/venv`) |
| CURRENT_STATE pointer flipped | ✅ | → this file; instrumentation demoted to predecessor |

## 9. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Investigate the cone before touching the synthesizer | Andy (gate) | The instinct caught the deeper bug: the synthesizer truncation alone would still never converge because the cache keys were non-deterministic. |
| **D2** | Fix both bugs in one PR | Andy (gate) | Both are required for convergence — fixing only one leaves the plan stalling (key-determinism without the truncation fix → empty blocks; truncation fix without key-determinism → orphaned blocks). |
| **D3** | Day-anchor the provenance timestamps (vs. exclude-from-hash or drop) | Claude (recommendation) | Single-point fix at the builder propagates to every hash site; matches the existing 3A `as_of` day-granular cache TTL; no payload-shape change, no consumer risk. |
| **D4** | Stay within approved scope — escalation + budget bound, NOT a speculative `max_tokens` bump | Claude (constraint) | The escalation directly addresses the OBSERVED cause (thinking eating the budget); a `max_tokens` bump targets an unobserved failure mode — defer until data shows it. |

## 10. Files shipped this session

**Substantive (4 code + 4 test):** `layer1/builder.py`, `layer2a/builder.py`, `llm_invocation.py`, `layer4/per_phase.py`; `tests/test_layer1_builder.py`, `tests/test_layer2a.py`, `tests/test_layer4_thinking_request.py`, `tests/test_layer4_plan_create.py`. Plus `aidstation-sources/Layer4_Spec.md` (§11.5 in place).
**Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

**End of handoff.**
