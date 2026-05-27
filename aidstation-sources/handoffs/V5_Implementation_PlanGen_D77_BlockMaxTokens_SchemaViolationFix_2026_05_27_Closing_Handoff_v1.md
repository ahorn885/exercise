# Plan-Gen D-77 — Block-Mode `max_tokens` Truncation Fix (the watch-item fired) — Closing Handoff

**Session:** Live-incident close. Andy redeployed the cone/truncation fix (PR #195, merged as `bbb0492`) and re-ran the PGE plan — it no longer 504-looped, but failed with the athlete-facing **"Plan synthesis failed (schema_violation). Adjust your inputs and try again."** This is exactly the residual watch-item the predecessor handoff flagged: the forced-tool retry truncating a dense week against `max_tokens=4000`. Shipped the pre-specified follow-on (block-mode output-budget scaling).
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_ConeCacheKeyDeterminism_SynthTruncationFix_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/plan-gen-schema-violation-tpu23`
**PR:** opened this session.
**Status:** 1 substantive code file + 1 test file + `Layer4_Spec §11.5` (in place) + bookkeeping. Suite **1795 passed / 16 skipped** (+2). **No migration. No prompt/schema/contract change** — only the per-block output-token ceiling.

---

## 1. The finding (why the re-run failed, now with schema_violation not a stall)

The predecessor fix worked as designed: the cone now caches across passes (day-anchored timestamps) and the per-block budget guard + empty-tool escalation stopped the 504-loop. So the re-run RETURNED a terminal result instead of spinning — but the terminal result was a `schema_violation`, not `ready`.

Root cause (the predecessor's §6 #1 / §11.5 watch-item, now fired): the **forced-tool retry** in `invoke_tool_call` runs with **thinking OFF**, so `max_tokens` is the *entire* output budget (no `+ thinking_budget` headroom). The per-phase default `max_tokens=4000` predates the dense `PlanSession` schema — each session serializes to ~400–600 output tokens (per-session `cardio_blocks` with intensity targets + `strength_exercises` arrays + 240-char `session_notes`/`instructions`/`coaching_intent`). A full high-frequency week-block (up to `_MAX_SESSIONS_PER_WEEK=14` sessions, the PGE 6-discipline norm) serializes well past 4000, so the forced retry **truncated mid-`sessions`** → the SDK returns an incomplete tool call (`block.input == {}` or partial) → `invoke_tool_call` treats it as a non-answer → `ThinkingToolCallError("schema_violation", detail="… stop_reason=max_tokens")` → `Layer4OutputError("schema_violation")` → the route message.

**Diagnosis basis (read this):** the prod log was NOT in hand this session — Andy pasted only the athlete-facing message. The diagnosis is **code-evidence-based**: (a) the dense session schema vs the 4000 ceiling; (b) the failure mode shifting from 504-loop to a *bounded* `schema_violation` is precisely what the predecessor's guard+escalation predicted; (c) `schema_violation` (not `cap_hit`) means the missing/parse/no-block path fired, and under the new forced-retry regime truncation is its most likely cause. Validator rejection produces `cap_hit` (best-effort accept), NOT `schema_violation`, so it's excluded.

## 2. What shipped

**`layer4/per_phase.py` — block-mode output-budget scaling.** In `synthesize_phase`, when `week_range` is set (block mode), the output budget now scales to the unit's session ceiling:

```
effective_max_tokens = max(
    max_tokens,
    max_sessions_this_unit * _BLOCK_OUTPUT_TOKENS_PER_SESSION + _BLOCK_OUTPUT_TOKENS_OVERHEAD,
)
```

New constants: `_BLOCK_OUTPUT_TOKENS_PER_SESSION = 600` (worst-case dense session), `_BLOCK_OUTPUT_TOKENS_OVERHEAD = 800` (`phase_synthesis_notes` ≤600 chars + `opportunities` 3×≤240 + JSON envelope). For a 1-week block (`_BLOCK_WEEKS=1` → 14 sessions): **9200**. Passed to the LLM caller in place of the raw `max_tokens`; the per-attempt diagnostic now logs `max_tokens=<effective>` so a re-run shows the budget. **Never below the caller's value.**

Why this is the right shape:
- It fixes the forced retry directly (thinking off → 9200 output tokens hold a dense week).
- It also helps the *first* (thinking) attempt: the request ceiling becomes `9200 + 5000 = 14200`, leaving ~9200 post-thinking output room, so the thinking attempt less often exhausts on reasoning and emits an empty tool call — i.e., the forced retry fires less, and when it does it has room.
- A higher `max_tokens` is **only a ceiling**: billed/latency cost tracks tokens *actually emitted*, and the `_PER_BLOCK_BUDGET_MS=120_000` guard still bounds total synthesis time. So no cost/timeout regression.
- Model is `claude-sonnet-4-6` (64K output ceiling) — 14200 is well within limits.

**Scope decision — block mode only.** Whole-phase mode (the seam-driven re-synth at `plan_create.py:1017`, `week_range=None`, up to 56 sessions) keeps the caller's `max_tokens` unchanged. A 56-session single call is the exact unit D-77 decomposition replaced; scaling it to ~34k would invite a >300s single generation → 504. Its scaling path is the **week-seam stitcher (Slice 3)**, not a token bump. That path is also iteration-2 (rare) and unreached when the initial blocks fail, so it's not the observed failure.

## 3. Code / tests

Full suite **1795 passed / 16 skipped** (`/tmp/venv`; +2 vs. the 1793 baseline):
- `tests/test_layer4_plan_create.py::TestBlockOutputBudget::test_block_mode_scales_max_tokens_to_session_ceiling` — captures the `max_tokens` passed to the LLM caller in block mode; asserts it equals `14×600 + 800 = 9200` and exceeds `DEFAULT_MAX_TOKENS`.
- `…::TestBlockOutputBudget::test_full_phase_mode_keeps_caller_max_tokens` — whole-phase mode passes through the caller's `DEFAULT_MAX_TOKENS` (no scaling).

`pyflakes layer4/per_phase.py` reports only the **pre-existing** `layer4/payload.Observation imported-unused` finding (flagged in the predecessor handoff; not introduced here).

## 4. Owed actions + manual verification

- **⚠ Owed (Andy's hands), in order:**
  1. **Redeploy** (merge this PR). No migration — `max_tokens` is a request sampling param, not part of any cache key or schema; existing cache rows are unaffected and a fresh plan synthesizes under the new ceiling.
  2. **Re-run the PGE 2026 plan** (the same complex case).
  3. **Confirm.** What to look for in the Vercel `synthesize_phase:` log:
     - The per-attempt line now reads `… out=N max_tokens=9200`. **`out` should land BELOW 9200** (a complete dense week is ~5000–9000 output tokens) instead of pinning a ceiling.
     - `synthesize_phase: <phase>:w<n> done — … accepted=True …` should fire per block (the convergence proof).
     - If a `schema_violation` STILL surfaces: send back (a) that per-attempt line AND (b) the route log `_advance_plan_generation: Layer4 … (schema_violation) … : <detail>` — the `detail` carries `stop_reason` + the missing/parse cause. `stop_reason=max_tokens` with `out` near 9200 ⇒ a still-larger budget or a trimmed block thinking budget (§5). Anything else (genuinely malformed sessions, a parse error) ⇒ a different fix, not a budget bump.

## 5. Next session — deferred follow-on(s)

1. **Further budget tuning (only if the re-run still truncates).** If `out` pins 9200, either raise `_BLOCK_OUTPUT_TOKENS_PER_SESSION` or trim the block `extended_thinking_budget` (5000) to shift more of the ceiling to output. Data-gated — don't pre-tune.
2. **Coherence (design §14, still UNVERIFIED).** Once a plan reaches `ready`, read across week boundaries WITHIN a phase — do the independently-generated weeks blend (gentle ramp, planned recovery) or show cliffs/duplication? If they don't blend, the seam may be wrong (a design redo, not a tuning knob) — report before Slice 3.
3. **Slice 3** (intra-phase week-seam stitcher; own Trigger #1 prompt pass) remains after convergence + coherence are confirmed.

## 6. Operating notes for next session (read order, Rule #13)

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what shipped (this fix) + the owed redeploy/re-run.
3. `aidstation-sources/CARRY_FORWARD.md` — the D-77 entry (watch-item now ✅ fired+fixed).
4. `aidstation-sources/Layer4_Spec.md §11.5` — the block-mode `max_tokens` fix record.
5. This handoff + the cone/truncation predecessor.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 7. Session-end verification (Rule #10)

| Check | Result | Anchor / method |
|---|---|---|
| Block-mode budget constants | ✅ | `layer4/per_phase.py` — `_BLOCK_OUTPUT_TOKENS_PER_SESSION = 600`, `_BLOCK_OUTPUT_TOKENS_OVERHEAD = 800` |
| Block-mode `effective_max_tokens` scaling | ✅ | `layer4/per_phase.py` — `effective_max_tokens = max(max_tokens, max_sessions_this_unit * _BLOCK_OUTPUT_TOKENS_PER_SESSION + _BLOCK_OUTPUT_TOKENS_OVERHEAD)` (block mode) / `= max_tokens` (whole-phase) |
| Caller uses effective budget | ✅ | `layer4/per_phase.py` — `caller(..., effective_max_tokens, extended_thinking_budget)` |
| Per-attempt diagnostic shows budget | ✅ | `layer4/per_phase.py` — `… out={...} max_tokens={effective_max_tokens})` |
| Block-budget tests | ✅ | `tests/test_layer4_plan_create.py::TestBlockOutputBudget` (×2) |
| Spec note | ✅ | `Layer4_Spec.md §11.5` — "Block-mode output-token budget (2026-05-27, RESOLVED — the watch-item above fired)" |
| Full suite | ✅ | 1795 passed / 16 skipped (`/tmp/venv`) |
| CURRENT_STATE pointer flipped | ✅ | → this file; cone/truncation fix demoted to predecessor |

## 8. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Implement the pre-specified block-mode `max_tokens` raise now (vs. ask first / instrument again) | Claude | The predecessor handoff pre-approved this exact follow-on, gated on "data shows it"; the re-run failing with a *bounded* `schema_violation` (not a 504-loop) IS the data. The fix is low-risk (a higher ceiling has no cost unless tokens are emitted; no schema/contract/cache change) and reversible via PR review. |
| **D2** | Scale the budget to the session ceiling (vs. a flat higher number) | Claude | Robust to `_BLOCK_WEEKS` tuning — a 2-week block automatically gets 2× the output room; self-documents the sizing logic. |
| **D3** | Block mode only; leave whole-phase seam-resynth unscaled | Claude | A 56-session single call is the unit decomposition replaced; scaling it invites a >300s generation → 504. Its scaling path is the Slice-3 stitcher, not a token bump. Minimal blast radius, aligned with the observed failure. |

## 9. Files shipped this session

**Substantive (1 code + 1 test):** `layer4/per_phase.py`; `tests/test_layer4_plan_create.py`. Plus `aidstation-sources/Layer4_Spec.md` (§11.5 in place).
**Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

**End of handoff.**
