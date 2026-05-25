# Layer 4 Synthesizer 500 Fix (extended thinking × max_tokens ≤ budget_tokens) — Closing Handoff

**Session:** Diagnosed + fixed the *remaining* production 500 on plan-create. Extended thinking makes `max_tokens` the combined thinking + visible-output budget, so the API requires `max_tokens > budget_tokens`; three of the five Layer 4 callers violated it. This is the third thinking-incompatibility in the chain — it only began firing once the predecessor cleared the `tool_choice` + `temperature` 400s. Shipped on PR #171, merged to `main`.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_Layer4_SynthesizerThinkingToolChoice_500Fix_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/fervent-planck-frRbB`
**Status:** 6 substantive files (one logical change — an identical 1-line edit across 5 callers — plus its guard-test extension); over the ~5 ceiling but a single mechanical fix, not 6 independent changes. Bookkeeping: this handoff + `CURRENT_STATE.md`. Shipped on PR #171 (merged).

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (`…SynthesizerThinkingToolChoice_500Fix…`) §8 claims against on-disk state before opening work:

| Claim | Anchor | Result |
|---|---|---|
| `tool_choice` → `auto` when thinking on, in all 5 callers | `grep -c 'request_kwargs\["tool_choice"\] = {"type": "auto"}'` → 1 each | ✅ |
| `anthropic.APIError` → `Layer4OutputError` wrap, 5 callers | `grep -c 'anthropic_api_error' layer4/*.py` → 1 per caller | ✅ |
| `tests/test_layer4_thinking_request.py` exists | file present, 15 parametrized cases | ✅ |
| Route degrades `Layer4OutputError` gracefully (no 500) | `routes/plan_create.py:166` catches `(Layer4InputError, Layer4OutputError)` → flash + redirect | ✅ |

**Reconciliation note:** clean — the predecessor's edits all landed. The predecessor was nonetheless *incomplete*: it fixed two of three thinking incompatibilities. The Anthropic API 400s on the **first** violation it encounters; clearing `tool_choice`/`temperature` unmasked the next one (`max_tokens ≤ budget_tokens`), which is why Andy still got a 500 on plan-create.

---

## 2. Session narrative

Andy reported: "still getting a 500 when I try to generate a new plan." Single half — a focused follow-on to the predecessor 500 fix.

**Root cause.** With extended thinking enabled, `max_tokens` is the **total** budget covering both the thinking tokens and the visible output, so the API requires `max_tokens > thinking.budget_tokens`. The five callers set `max_tokens` and `extended_thinking_budget` independently, and three had `max_tokens ≤ budget`:

| Caller | `max_tokens` | `budget_tokens` | Pre-fix |
|---|---|---|---|
| `per_phase` (core plan_create synthesizer) | 4000 | 5000 | ❌ 400 |
| `seam_review` | 1500 | 2000 | ❌ 400 |
| `single_session` | 1500 | 3500 | ❌ 400 |
| `plan_refresh` (tier defaults) | per-tier | per-tier | varies |
| `race_week_brief` | 6000 | 5500 | ✅ valid but only 500 tok output headroom |

`plan_create` runs `per_phase` (4000 < 5000) on every phase, so it 400'd unconditionally — the live 500 Andy hit.

**Fix (chosen approach).** In each caller's `if extended_thinking_budget > 0:` branch, set `request_kwargs["max_tokens"] = max_tokens + extended_thinking_budget`. This stacks the thinking budget on top of each caller's intended *visible-output* allowance, so `max_tokens > budget_tokens` always holds and the output budget is preserved (not cannibalized by thinking). Applied uniformly to all five callers — `race_week_brief`, though already valid, gains real output headroom (it previously left only 500 tokens for visible output above a 5500 thinking budget, a latent truncation bug).

No `/plan`-gate trigger applies: this is request-config correctness to make a malformed API call valid, not prompt-body design (Trigger #1) or a cross-layer contract change (Trigger #3).

---

## 3. File-by-file edits

### 3.1 `layer4/per_phase.py`, `layer4/seam_review.py`, `layer4/single_session.py`, `layer4/plan_refresh.py`, `layer4/race_week_brief.py` (modified)

Identical edit in each `_default_*_caller`. In the `if extended_thinking_budget > 0:` block, after the `tool_choice` + `temperature` relaxations, add:

```python
request_kwargs["max_tokens"] = max_tokens + extended_thinking_budget
```

and rewrote the leading comment to name all three thinking constraints (tool_choice must be `auto`; temperature must be 1; max_tokens must exceed budget_tokens). When `extended_thinking_budget == 0` the path is unchanged (forced tool + passed temperature + passed max_tokens). Anchor: `grep -c 'request_kwargs\["max_tokens"\] = max_tokens + extended_thinking_budget' layer4/per_phase.py layer4/seam_review.py layer4/single_session.py layer4/plan_refresh.py layer4/race_week_brief.py` → 1 each.

---

## 4. Code / tests

Extended `tests/test_layer4_thinking_request.py` (already 15 cases) with two assertions, no new cases:

- thinking-on (`test_thinking_on_relaxes_tool_choice_and_temperature`, called with `max_tokens=4000, budget=5000`) → asserts `max_tokens == 9000` **and** `max_tokens > thinking.budget_tokens`;
- thinking-off (`test_thinking_off_keeps_forced_tool`) → asserts `max_tokens == 4000` (unchanged).

Module docstring updated to name the `max_tokens ≤ budget_tokens` incompatibility alongside the existing two. Full suite **1674 passed / 16 skipped** in a fresh `/tmp/venv` (`pip install -r requirements.txt pytest`; system python lacks pytest/pydantic). 16 skipped = NL-parser + Layer 3 SDK smoke (no `ANTHROPIC_API_KEY`).

---

## 5. Manual §5.0 verification steps

The predecessor's live-plan-create §5.0 scenario in `CARRY_FORWARD.md` still stands and is now even more decisive: it is the only proof that plan-gen runs end-to-end against the real Anthropic API. With this fix all three thinking 400s are cleared; the per-phase synthesizer should return a `record_phase_sessions` tool_use block under `tool_choice: auto`. The PR #171 Vercel preview is live for this:

- `https://exercise-git-claude-fervent-planck-frrbb-andy-horns-projects.vercel.app/plans/v2/new` (`ANTHROPIC_API_KEY` set; ~$0.30–0.50). Confirm no 500; a plan renders. If it fails it is now a graceful `Layer4OutputError` flash whose detail names the SDK error type — capture that string.

No new scenario appended (the existing one covers it).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

Run the **live plan-create** end-to-end (now unblocked by both 500 fixes). It has still never run against the real API, so it may surface downstream issues (tool-arg → `PlanSession` parsing, validator behavior under real output, persistence). Any failure is now graceful, not a 500.

### 6.2 Alternative pivots

- **Dedupe the 5 callers (now strongly indicated).** The request construction + the *three* thinking relaxations + the error-wrap are byte-identical across `per_phase`/`seam_review`/`single_session`/`plan_refresh`/`race_week_brief`. This is now the **second** session in a row to apply an identical N-line edit across all five — exactly the failure mode that let two of the three incompatibilities ship undetected. Extract a shared `_build_messages_request(...)` + `_invoke_with_thinking(...)` helper so the request shape lives at one site with one unit test. Good `simplify`-skill candidate; deferred again only to keep this urgent fix minimal. **If a third request-shape bug appears, do the dedupe first.**
- **Retry on transient overload.** API 429/529 still become a `Layer4OutputError` (manual retry). Bounded backoff on transient errors only — nice-to-have, not in scope.

### 6.3 Operating notes for next session

1. `CLAUDE.md` — stable rules (Rule #13).
2. `CURRENT_STATE.md` — what just shipped + focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | When thinking is on, set `max_tokens = max_tokens + extended_thinking_budget` (vs. bumping the module-level `DEFAULT_MAX_TOKENS` constants) | Claude (config correctness; no Trigger gate) | Localizes the change to the thinking branch where the constraint applies; preserves each caller's intended visible-output allowance and the unchanged thinking-off path. |
| 2 | Apply uniformly to all 5 callers incl. the already-valid `race_week_brief` | Claude | Uniform request shape + fixes `race_week_brief`'s latent 500-token output truncation (6000 − 5500). |
| 3 | Fold into PR #171 on the harness-pinned branch + merge to `main` | Andy ("merge it all") | — |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -c 'request_kwargs\["max_tokens"\] = max_tokens + extended_thinking_budget' layer4/per_phase.py layer4/seam_review.py layer4/single_session.py layer4/plan_refresh.py layer4/race_week_brief.py` → 1 each | ✅ |
| `python -m py_compile` on all 5 callers | ✅ |
| `tests/test_layer4_thinking_request.py` asserts `max_tokens == 9000` + `> budget_tokens` (thinking-on) and `== 4000` (thinking-off) | ✅ |
| Full suite `pytest tests/` → 1674 passed / 16 skipped | ✅ |
| PR #171 CI (Vercel) | ✅ success |
| PR #171 merged to `main` | ✅ |

---

## 9. Files shipped this session

**Substantive (6 files — one logical change + its test):**
1. `layer4/per_phase.py`
2. `layer4/seam_review.py`
3. `layer4/single_session.py`
4. `layer4/plan_refresh.py`
5. `layer4/race_week_brief.py`
6. `tests/test_layer4_thinking_request.py` (extended)

Files 1–5 are an identical 1-line edit (+ a comment rewrite); file 6 guards it. Over the ~5 ceiling, but a single mechanical fix replicated across near-identical callers — the §6.2 dedupe would prevent the replication next time.

**Bookkeeping:**
7. `CURRENT_STATE.md` — last-shipped pointer bumped to this handoff; ToolChoice fix demoted to predecessor; Tests section updated.
8. This handoff.

---

## 10. Carry-forward updates

None. The predecessor's live-plan-create §5.0 scenario already covers the decisive end-to-end walk; this fix makes it executable but adds no new scenario.

---

**End of handoff.**
