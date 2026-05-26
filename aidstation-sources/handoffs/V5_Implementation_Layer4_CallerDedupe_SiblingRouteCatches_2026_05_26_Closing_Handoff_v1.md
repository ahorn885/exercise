# Layer 4 Caller Dedupe + Sibling-Route Layer3 Catches — Closing Handoff

**Session:** Executed the §6.1 follow-on (the REQUIRED next move for an end-to-end plan): migrated all 5 Layer 4 `_default_*_caller`s off their inline `messages.create` onto the shared `llm_invocation.invoke_tool_call`, which distributes the PR #174 forced-tool retry to them; and extended the graceful typed-error catch to the two sibling routes (`plan_refresh`, `ad_hoc_workouts`) that fire 3A/3B through the same cone and still 500'd on a `Layer3*OutputError`.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_AsyncProgress_ToolRetry_Reliability_2026_05_26_Closing_Handoff_v1.md` (PR #173 async progress screen + PR #174 3A/3B forced-tool retry)
**Branch:** `claude/lucid-heisenberg-8uoUh`
**Status:** 7 substantive files (5 caller migrations + 2 route catches), 1 test file, bookkeeping. Andy approved the single-PR scope (the 5 caller edits are byte-identical). Full suite **1697 passed / 16 skipped**.

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor §8) | Anchor | Result |
|---|---|---|
| `grep -c "def _attempt" llm_invocation.py` → 1 | grep | ✅ 1 |
| `invoke_tool_call` retries `_attempt(0)` on a thinking-miss + logs `stop_reason` | inspection | ✅ (llm_invocation.py:144-167) |
| `tests/test_layer3_thinking_request.py` → 13 passed | pytest | ✅ 13 |
| Full suite → 1692 / 16 skipped | pytest (fresh `/tmp/venv`) | ✅ baseline reproduced before edits |
| PR #173 (`c91efe0`) + #174 merged | `git log` | ✅ #174 = `51f4c3b`, branch even with `origin/main` |
| `./scripts/verify-handoff.sh` file-existence sweep | script | ✅ all green, working tree clean |

**Reconciliation note:** clean — no drift between handoff narrative and on-disk state. Branch `claude/lucid-heisenberg-8uoUh` was harness-pinned and already even with `origin/main` at `51f4c3b`, so it was the correct base (no `reset --hard` needed this time).

---

## 2. Session narrative

Andy linked the predecessor handoff and said "lets work." Ran the full first-session checklist (CLAUDE.md): read CLAUDE.md / CURRENT_STATE / CARRY_FORWARD / PR_Verification_Status / the predecessor handoff, ran `verify-handoff.sh`, spot-checked the §8 anchors. State was clean; both CURRENT_STATE and the handoff named **§6.1 Layer 4 caller dedupe** as the required next move.

Scope-pick gate (AskUserQuestion): Andy chose **all in one PR** over splitting, accepting the ~7-file count because the 5 caller edits are mechanically identical. No stop-and-ask trigger fired — this is request-shape plumbing, not prompt-body design (Trigger #1), not a cross-layer contract change (Trigger #3), and the architecture was already decided by Andy (decision §6.1).

Implementation was a straight replication of the proven `layer3a/builder.py:139` delegation pattern across the 5 callers, plus broadening two route catch tuples.

---

## 3. File-by-file edits

### 3.1 `layer4/per_phase.py` (modified)
`_default_llm_caller` now delegates to `invoke_tool_call`, mapping `ThinkingToolCallError → Layer4OutputError` and converting `ToolCallResult → _SynthesizerOutput`. Dropped the now-unused `import os` / `import time` (and the function-local `import anthropic` went with the body). Added `from llm_invocation import ThinkingToolCallError, invoke_tool_call`.

### 3.2 `layer4/seam_review.py` (modified)
Same migration for `_default_seam_reviewer_caller` → `_SeamReviewerOutput`. Same import cleanup.

### 3.3 `layer4/single_session.py` (modified)
Same migration for `_default_llm_caller` → `_SynthesizerOutput`. Same import cleanup.

### 3.4 `layer4/plan_refresh.py` (modified)
Same migration for `_default_llm_caller` → `_SynthesizerOutput`. Same import cleanup.

### 3.5 `layer4/race_week_brief.py` (modified)
Same migration for `_default_llm_caller` → `_SynthesizerOutput`. Same import cleanup.

> Net effect of 3.1–3.5: the request shape + the forced-tool retry now live ONLY in `llm_invocation.invoke_tool_call`. `grep -rn "messages.create" layer4/*.py` → none. A plan that clears 3A/3B no longer `schema_violation`s at the phase synthesizer when the model declines the tool under thinking — the synthesizer retries thinking-off + forced tool, same as 3A/3B.

### 3.6 `routes/plan_refresh.py` (modified)
Imported `Layer3AOutputError` / `Layer3BOutputError`. Broadened the `except (Layer4InputError, Layer4OutputError)` block (~line 560) to also catch the two Layer 3 errors, with a `layer_tag = "layer3" if isinstance(...) else "layer4"` so the refresh-log `failure_reason` stays accurate (`exc.code` alone is ambiguous — both layers emit `schema_violation`). Flash + rollback + redirect unchanged.

### 3.7 `routes/ad_hoc_workouts.py` (modified)
Imported the two Layer 3 errors. Broadened BOTH single-session catch blocks (build path ~line 429, regenerate path ~line 613) to include them. These had no failure-log write, so just the tuple widened; flash text unchanged.

### 3.8 `tests/test_layer4_thinking_request.py` (modified)
Reframed the module docstring (the shape now lives in the shared helper; the callers delegate). Added `_NoToolMsg` + `_fake_anthropic_sequence` (mirrors the layer3 test). New parametrized `test_thinking_miss_falls_back_to_forced` (×5 callers) asserts a thinking-miss drives one forced retry through each caller (`rec["n"] == 2`, final request forced + no `thinking`, result returned). The 3 pre-existing parametrized tests (shape-on, shape-off, APIError→Layer4OutputError) still pass unchanged — they pass *through* the delegation because the `anthropic.Anthropic` monkeypatch is module-global.

---

## 4. Code / tests

Full suite **1697 passed / 16 skipped** in a fresh `/tmp/venv` (1692 pre-session → +5 = the new `test_thinking_miss_falls_back_to_forced` × 5 callers; nothing removed). `tests/test_layer3_thinking_request.py` still 13; `tests/test_layer4_thinking_request.py` now 20 (4 parametrized × 5 callers).

---

## 5. Manual §5.0 verification steps

Appended to `CARRY_FORWARD.md` (Manual §5.0 walkthrough). With `ANTHROPIC_API_KEY` set on the deployed app:
1. **End-to-end plan-create now completes the synthesizer.** Run `/plans/v2/new` for Andy's PGE 2026 context. Confirm the progress screen runs the per-phase Layer 4 synthesis to completion — no `schema_violation` at the synthesizer. If the model declines the tool under thinking, the Vercel runtime log shows `invoke_tool_call: <tool> returned no tool_use block on the thinking attempt … retrying with thinking off + forced tool_choice`, then the run proceeds.
2. **plan_refresh no longer 500s on a Layer3 error.** Drive a T1/T2/T3 refresh via `/plans/.../refresh`; if 3A/3B raise a `Layer3*OutputError`, confirm a graceful red flash "Plan refresh failed (<code>). Adjust your inputs and try again." + redirect (not an unhandled 500), and a refresh-log row with `failure_reason=layer3:<code>`.
3. **ad_hoc_workouts (single_session) no longer 500s on a Layer3 error.** Drive `/workouts/build` (and the regenerate path); confirm a `Layer3*OutputError` yields the "Workout synthesis failed (<code>)." flash + redirect, not a 500.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — §6.2 Cron-driven background generation
Per the predecessor roadmap (Andy decision #3). Add a Vercel cron hitting a new auth-exempt-but-guarded endpoint (`CRON_SECRET` header, precedent in `routes/nudges.py`) that finds bounded `plan_versions` rows with `generation_status='generating'` and advances each by one resumable pass. Mechanically: factor the body of `routes/plan_create.generate_plan` into a reusable `_advance_plan_generation(db, uid, plan_version_id)` the cron + the route both call. Decouples generation from the page (keeps running with the tab closed); the progress page still polls for faster feedback when open.

### 6.2 Alternative pivots
- **§6.3 Notifications (email + in-app, both — Andy decision #4):** on terminal status in `generate_plan`/`_advance_plan_generation`, send a "plan ready"/"plan failed" email via `email_helper.py` + a dashboard status badge reading `plan_versions.generation_status`. Guard double-send (transition-into-`ready`/`failed` only, or a `notified_at` column). Best done *after* §6.2 so both the cron path and the route path notify through one terminal-status hook.
- **Seam-review / final-validator caching** (residual from PR #173): the Layer 4 tail isn't individually cached, so it re-runs whole on each resume. Now moot on Pro (300s) but worth caching if a single unit ever can't fit the window.

### 6.3 Operating notes for next session (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items (incl. this session's §5.0 walk entries).
4. This handoff.
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Ship §6.1 as a single PR (all 5 caller migrations + both route catches) | Andy | The 5 caller edits are byte-identical; splitting would cost two merge cycles for no review clarity. |
| 2 | Keep the existing `test_layer4_thinking_request.py` parametrized tests rather than delete them as "redundant with the helper test" | Claude | They verify each of the 5 callers actually delegates (the shape *and* the retry reach them) — the helper test alone wouldn't catch a caller that stopped delegating. |
| 3 | Derive `failure_reason` layer tag by `isinstance` in `plan_refresh` rather than a second catch block | Claude | `exc.code` is ambiguous across layers (both emit `schema_violation`); one block + a tag keeps telemetry accurate without duplicating the ~20-line log-write. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -rn "messages.create" layer4/*.py` → none | ✅ |
| `grep -c "invoke_tool_call" layer4/per_phase.py layer4/seam_review.py layer4/single_session.py layer4/plan_refresh.py layer4/race_week_brief.py` → 1 each | ✅ |
| `grep -rn "Layer3AOutputError" routes/plan_refresh.py routes/ad_hoc_workouts.py` present | ✅ |
| `py_compile` all 7 substantive files + the test file | ✅ |
| Full suite `pytest tests/` → 1697 passed / 16 skipped | ✅ (fresh `/tmp/venv`) |
| Working tree clean after commit | ✅ git status |

---

## 9. Files shipped this session

**Substantive (7 files):**
1. `layer4/per_phase.py`
2. `layer4/seam_review.py`
3. `layer4/single_session.py`
4. `layer4/plan_refresh.py`
5. `layer4/race_week_brief.py`
6. `routes/plan_refresh.py`
7. `routes/ad_hoc_workouts.py`

**Tests:**
8. `tests/test_layer4_thinking_request.py`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Manual §5.0 walkthrough: added the 3-step §6.1 walk (end-to-end synthesizer completes; plan_refresh + ad_hoc no longer 500 on a Layer3 error). The predecessor's "⚠ Layer 4 still exposed" warning in the 3A/3B retry §5.0 entry is now **resolved** — flagged there.

---

**End of handoff.**
