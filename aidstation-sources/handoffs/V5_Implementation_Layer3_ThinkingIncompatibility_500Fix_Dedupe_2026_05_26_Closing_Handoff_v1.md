# Layer 3A/3B Thinking-Incompatibility 500 Fix + Shared-Invocation Dedupe — Closing Handoff

**Session:** Diagnosed the *still-live* plan-create 500 (Andy: "still getting an internal server error … maybe some plumbing isn't fully done"). PR #170/#171 fixed the extended-thinking incompatibility in the five Layer 4 callers — but the orchestrator fires **Layer 3A then Layer 3B** LLM calls *before* any Layer 4 call, and both carried the identical bug (forced `tool_choice` + `temperature != 1` + `max_tokens ≤ budget_tokens`), unwrapped. The chain 500'd at Layer 3A and never reached the fixed Layer 4 code. Andy chose the handoff §6.2 dedupe (this is the predicted "third request-shape bug") + typed-error wrapping. Shipped the shared `invoke_tool_call` site and migrated 3A + 3B onto it.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_Layer4_ThinkingMaxTokensBudget_500Fix_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/inspiring-franklin-abgx7`
**Status:** 5 substantive files (new shared helper + 3A + 3B + plan_create route + new guard test). Bookkeeping: this handoff + `CURRENT_STATE.md`. **Partial dedupe** — the 5 Layer 4 callers still hold inline copies of the (already-correct) request shape; migrating them onto the shared helper is the §6.1 follow-on (a no-behavior-change refactor, split out to respect the 5-file ceiling).

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (`…ThinkingMaxTokensBudget…`) §8 claims against on-disk state:

| Claim | Anchor | Result |
|---|---|---|
| 5 Layer 4 callers set `max_tokens = max_tokens + extended_thinking_budget` | `grep -c 'request_kwargs\["max_tokens"\] = max_tokens + extended_thinking_budget' layer4/*.py` → 1 each | ✅ |
| `tests/test_layer4_thinking_request.py` asserts `max_tokens == 9000` (thinking-on) | file present | ✅ |
| Route degrades `Layer4*Error` (no 500) | `routes/plan_create.py` catches `(Layer4InputError, Layer4OutputError)` | ✅ |

**Reconciliation note:** the predecessor's edits all landed and are correct — but were **scoped to Layer 4 only**. The predecessor §6.1 explicitly warned plan-create had never run end-to-end and "may surface downstream issues." The actual issue was *upstream*: Layer 3A/3B (which run first) had the same never-fixed incompatibility. No on-disk drift; the gap was unshipped scope, exactly the replication failure mode §6.2 flagged.

---

## 2. Session narrative

**Root cause.** `orchestrate_plan_create` → `_upstream_full_cone` calls `llm_layer3a_athlete_state_cached` (`orchestrator.py:320`) then `llm_layer3b_…_cached` (`:330`) **before** `llm_layer4_plan_create_cached` (`:743`). Both Layer 3 `_default_llm_caller`s built the pre-fix request shape:

| Caller | forced `tool_choice` | `temperature` default | `max_tokens` vs budget | APIError wrap |
|---|---|---|---|---|
| `layer3a/builder.py` | ✗ `{"type":"tool"}` | 0.2 (≠1) | 4000 **==** 4000 | none (bare `create`) |
| `layer3b/builder.py` | ✗ `{"type":"tool"}` | 0.0 (≠1) | 2000 **<** 3000 | none (bare `create`) |

All three thinking constraints violated in both; the API 400s on the first. And neither wrapped `client.messages.create`, so the raw `anthropic.BadRequestError` propagated past the route's `except (OrchestrationError, Layer4InputError, Layer4OutputError)` → **500**. Plan-create died at the Layer 3A call.

**Fix (Andy's picks: dedupe §6.2 + wrap-to-typed-error).** New top-level `llm_invocation.py` holds the one authoritative request construction (`invoke_tool_call`) with the thinking relaxation (tool_choice `auto` + temperature 1 + `max_tokens = max_tokens + budget`) and an `anthropic.APIError` → `ThinkingToolCallError` wrap. Layer 3A and 3B `_default_llm_caller`s are now thin wrappers that delegate and map `ThinkingToolCallError` → their own `Layer3AOutputError` / `Layer3BOutputError` (preserving the §5.3 / §5.5 contracts). `routes/plan_create.py` catches those two typed errors → flash + redirect instead of 500.

No `/plan`-gate trigger applies: request-config correctness, not prompt-body design (Trigger #1) or a cross-layer contract change (Trigger #3). Andy approved the approach via the scope question.

---

## 3. File-by-file edits

### 3.1 `llm_invocation.py` (NEW)
`ToolCallResult` dataclass + `ThinkingToolCallError(code, detail=None)` + `invoke_tool_call(*, system_prompt, user_prompt, tool_schema, model, temperature, max_tokens, extended_thinking_budget) -> ToolCallResult`. Thinking-off keeps the forced tool + passed temperature + passed max_tokens; thinking-on relaxes all three. Codes: `anthropic_api_key_missing` / `anthropic_api_error` / `schema_violation`. Anchor: `grep -c 'request_kwargs\["max_tokens"\] = max_tokens + extended_thinking_budget' llm_invocation.py` → 1.

### 3.2 `layer3a/builder.py`, `layer3b/builder.py` (modified)
`_default_llm_caller` replaced with a delegate to `invoke_tool_call`, mapping `ThinkingToolCallError` → `Layer3AOutputError` / `Layer3BOutputError` via `raise …(exc.code, detail=exc.detail) from exc`. Added `from llm_invocation import ThinkingToolCallError, invoke_tool_call`. Removed now-dead `import os` + `import time`. Anchor: `grep -c 'except ThinkingToolCallError as exc' layer3a/builder.py layer3b/builder.py` → 1 each.

### 3.3 `routes/plan_create.py` (modified)
Added imports `from layer3a.builder import Layer3AOutputError` + `from layer3b.builder import Layer3BOutputError`; new `except (Layer3AOutputError, Layer3BOutputError)` clause → flash `"Athlete evaluation failed ({code})."` + redirect.

---

## 4. Code / tests

New `tests/test_layer3_thinking_request.py` (11 tests): mocks the SDK and asserts (a) the shared helper relaxes all three on thinking-on + keeps the forced tool on thinking-off + maps APIError / missing-tool-block / missing-key to `ThinkingToolCallError`; (b) the 3A + 3B wrappers build the relaxed request through the helper and map APIError → their typed `Layer3*OutputError`. The file imports `layer4` first to dodge a **pre-existing** import cycle (`layer3a.builder → layer4.context → layer4 → orchestrator → layer3a.cached_wrapper → layer3a.builder`) that is masked in the full suite — see §6.2. Full suite **1685 passed / 16 skipped** in `/tmp/venv` (was 1674/16; +11).

---

## 5. Manual §5.0 verification steps

The predecessor's live-plan-create §5.0 scenario in `CARRY_FORWARD.md` now becomes the *decisive* end-to-end walk: it was previously doomed to 500 at the Layer 3A call regardless of the Layer 4 fixes. With 3A/3B unblocked the cone should compose 3A → 3B → 2E → Layer 4 and a plan should render. **Still owed (Andy's hands, ~$0.30–0.50; PR Vercel preview):** confirm no 500 and a plan renders. Any failure is now a graceful flash whose detail names the SDK error type — capture that string. No new scenario appended (the existing one covers it, now executable upstream).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Finish the dedupe (the §6.2 follow-on).** Migrate the 5 Layer 4 `_default_*_caller`s (`per_phase` / `seam_review` / `single_session` / `plan_refresh` / `race_week_brief`) onto `invoke_tool_call`, deleting their inline request construction, and point `tests/test_layer4_thinking_request.py` at the shared helper. This is a **no-behavior-change refactor** (they're already correct) — it just collapses the request shape to one site so a 4th request-shape bug can't recur. Also extend the graceful catch to the sibling routes (`routes/plan_refresh.py:524`, `routes/ad_hoc_workouts.py:422,604`) which call 3A/3B via the same cone and still 500 on a typed `Layer3*OutputError`. Together ~6–7 files → its own PR.

### 6.2 Operating notes / known gotcha
- **Pre-existing import cycle.** Importing `layer3a.builder` (or `layer3b.builder`) *before* `layer4` raises `ImportError: cannot import name '_DEFAULT_MAX_TOKENS' … partially initialized`. It's masked in the full suite (something imports `layer4` first) and in production (the app imports `layer4`/orchestrator first). The new test imports `layer4` up front to stay runnable in isolation. Pre-dates this session; not fixed here (would be its own refactor — likely move the shared `_DEFAULT_*` consts or break the `layer3a.builder → layer4.context` edge). Candidate `Cleanup` backlog row if it bites again.

### 6.3 Operating notes for next session (read order)
1. `CLAUDE.md` — stable rules (Rule #13).
2. `CURRENT_STATE.md` — what just shipped + focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Dedupe to a shared `invoke_tool_call` (vs. copy the 3-line relaxation into 3A/3B inline) | Andy | This is the third appearance of the request-shape bug; §6.2 said "if a third appears, do the dedupe first." Kills the bug class. |
| 2 | Wrap 3A/3B SDK errors → typed `Layer3*OutputError` + route catch → flash | Andy | A failure degrades gracefully instead of 500ing (matches the Layer 4 PR #170 pattern). |
| 3 | Shared helper at repo root (`llm_invocation.py`), not under `layer4/` | Claude | Layer 3 importing from `layer4/` would invert the pipeline dependency; a neutral root module avoids a new cycle. |
| 4 | Ship 3A/3B now; defer the 5 Layer 4 caller migration to a follow-on PR | Claude | The blocker is 3A/3B; the Layer 4 callers are already correct. Splitting keeps each PR at/under the 5-file ceiling. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -c 'request_kwargs\["max_tokens"\] = max_tokens + extended_thinking_budget' llm_invocation.py` → 1 | ✅ |
| `grep -c 'except ThinkingToolCallError as exc' layer3a/builder.py layer3b/builder.py` → 1 each | ✅ |
| `routes/plan_create.py` catches `(Layer3AOutputError, Layer3BOutputError)` → flash | ✅ |
| `import os` / `import time` removed from both builders (now dead) | ✅ |
| `python -m py_compile` on all 5 files | ✅ |
| Full suite `pytest tests/` → 1685 passed / 16 skipped | ✅ |

---

## 9. Files shipped this session

**Substantive (5 files):**
1. `llm_invocation.py` (new — shared request site)
2. `layer3a/builder.py` (caller → delegate)
3. `layer3b/builder.py` (caller → delegate)
4. `routes/plan_create.py` (graceful catch)
5. `tests/test_layer3_thinking_request.py` (new — guards the shared shape + both wrappers)

**Bookkeeping:**
6. `CURRENT_STATE.md` — last-shipped pointer bumped to this handoff.
7. This handoff.

---

## 10. Carry-forward updates

None beyond §5 (the existing live-plan-create scenario now executes upstream). §6.1 (finish the dedupe + sibling-route catches) is the recommended next forward move; §6.2 (pre-existing import cycle) is a latent cleanup candidate.

---

**End of handoff.**
