# plan-create Layer 3A schema_violation (notable_observations text) + spec/prompt reconciliation — Closing Handoff

**Session:** Diagnosed a **recurrence** of the live "Plan generation didn't finish — Athlete evaluation failed (schema_violation)" report. Pinned it via the new #180 Layer3-detail log + the Vercel runtime log to a **`Layer3AOutputError(schema_violation)` on `notable_observations[].text`** (a `string_too_long` over-running `Layer3Observation.text`'s `max_length=240`), fixed it with the same pre-validation-clamp pattern as #179, then (Andy-directed) added an LLM-facing prompt rule and **folded in the owed doc-only spec/prompt reconciliation** (§8.2 cap 6→10, §7 weak_links "most-limiting first"). Root cause: the per-string bound the #179 handoff §6.4 explicitly flagged to watch — the tool-schema `maxLength: 240` is only an Anthropic API hint, so for a detailed observation the model over-runs 240 and the cone walls on both capped attempts.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_Layer3A_SchemaViolation_WeakLinks_2026_05_26_Closing_Handoff_v1.md` (§6.4 bounded-collection watch; PR #179 `243b35d`; #180 `03a3e46` added the Layer4/Layer3 detail logging that made this diagnosable)
**Branch:** `claude/plan-gen-schema-violation-B2ttn`
**PR:** #181 (3 commits: `1a57475` clamp + tests; `e8f289d` prompt rule; + the 6→10 prompt fold-in / spec / doc reconciliation)
**Status:** 2 substantive code files (`layer3a/builder.py`, `layer3b/builder.py`) + 2 test files + 4 doc/spec/prompt files + bookkeeping. Full suite **1724 passed / 16 skipped** (+4 over the 1720 baseline).

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor) | Anchor | Result |
|---|---|---|
| PR #179 merged (`243b35d`) + #180 Layer3/4 detail log (`03a3e46`) on `main` | `git log` | ✅ present; branch base |
| `_clamp_weak_links` / `_clamp_notable_observations` present + called pre-validation | grep `layer3a/builder.py`, `layer3b/builder.py` | ✅ |
| §6.4 watch: "3A observation `text` 240-char … not yet clamped — watch if a new `schema_violation` appears" | predecessor handoff | ✅ it appeared — this session |

Andy reported the live symptom directly ("Athlete evaluation failed (schema_violation)" on a fresh plan-gen), so the session was bug-driven.

## 2. Session narrative

The athlete-facing string `Athlete evaluation failed ({exc.code})` is built at `routes/plan_create.py:280` — the typed Layer 3 catch (covers `Layer3A/3B Input/OutputError`). #180 added `print(... type/code/plan_version_id/detail ...)` to that catch, so the failing field was now in the runtime log.

Diagnosed via the **Vercel runtime-log MCP** by the predecessor's full-text-elimination method (the MCP collapses each request to one line; whole-token substring search is reliable). On the failing requests (`POST /plans/v2/20/generate` + the `generate-pending` cron): `Layer3AOutputError` **matches**, `Layer3BOutputError` **does not** → Layer **3A**. `notable_observations`, `string_too_long`, `at most 240 characters` **all match**; `weak_links` **does not** → the failing locus is `notable_observations[].text` exceeding `Layer3Observation.text`'s `max_length=240`. (`weak_links` no longer matching confirms #179's clamp holds; the field moved.)

Why now: nothing changed structurally — a multi-discipline expedition-AR athlete legitimately draws a detailed observation (e.g. the self-report-vs-integration divergence data-hygiene note), and the model writes >240 chars. The tool-schema `maxLength` is a hint, so it failed `Layer3APayload` validation on both capped attempts.

Andy then directed: add the LLM-facing length instruction, fold the 6→10 prompt correction in, and update all docs.

## 3. File-by-file edits

### 3.1 `layer3a/builder.py` (modified)
- New `_OBSERVATION_TEXT_MAX_CHARS = 240` (mirrors `Layer3Observation.text` `max_length` + the tool-schema `maxLength`, lock-step comment).
- New `_truncate_to_word_boundary(text, max_chars)` — cuts to ≤`max_chars`, snapping to the last word boundary within the last 40 chars and appending a single-char ellipsis (`…`) so the result is ≤ cap and reads cleanly.
- New `_clamp_observation_text(candidate)` — truncates each `notable_observations[i].text` over the cap **before** `Layer3APayload.model_validate`. Only `text` is trimmed; `category`/`evidence_basis`/`elevates_to_hitl` untouched → HITL gating unaffected. Logs `truncating a notable_observations text from N to M chars` when it fires.
- Called in the validation loop right after `_clamp_weak_links(candidate)`.
- **Prompt body** rule 6: appended "Keep each observation's `text` under 240 characters — one concise flag, not a paragraph (it is hard-capped at 240 and truncated past that)."

### 3.2 `layer3b/builder.py` (modified)
- Same `_OBSERVATION_TEXT_MAX_CHARS` / `_truncate_to_word_boundary` / `_clamp_observation_text` (3B shares `Layer3Observation`), called after `_clamp_notable_observations` in **both** the main loop and the sanity-retry loop (`retry_candidate`).
- **Prompt body** rule 9: cap text **6 → 10** items (matching the deployed `_NOTABLE_OBSERVATIONS_MAX`) + appended the same <240-char observation-text instruction.

### 3.3 Tests (modified)
- `tests/test_layer3a_builder.py` — +2 (`TestObservationTextClamp`): over-length text truncated to ≤240 + ellipsis, no schema_violation, structured fields/HITL preserved; at-cap (exactly 240) unchanged.
- `tests/test_layer3b_builder.py` — +2 (`TestNotableObservationsBudget`): over-length text truncated, no schema_violation, category/HITL preserved; (the at-cap path is covered by 3A's symmetric test).

### 3.4 Spec + prompt reconciliation (doc — the owed #179 §6.1 follow-on, folded in)
- `Layer3_3B_Spec.md` §8.2 — `max_items` **6 → 10**; now documents the pre-validation `_clamp_notable_observations` (budget) + `_clamp_observation_text` (per-string) clamps.
- `Layer3_3A_Spec.md` §7 — `weak_links` now "**ordered most-limiting first**" (driver truncates first-5); new schema-rule bullet documenting `_clamp_observation_text` on `notable_observations[].text`.
- `prompts/Layer3B_v1.md` — summary line + rule 9 `6 → 10`; +<240-char rule.
- `prompts/Layer3A_v1.md` — rule 9 weak_links "most-limiting first"; rule 6 +<240-char rule.
- **Edited in place, NOT version-bumped.** Rationale: the on-disk precedent for both Layer3 specs is edit-in-place (last touched in place by `828fa99`, no `_vN` variants exist), and the prompt artifacts are `_v1`-named with no `_v2` (the #179 handoff itself named `prompts/Layer3A_v1.md` as the edit target). This contradicts the literal Rule #12 version-suffix rule — **flagged for Andy in §7 decision 4**; reverse if you want versioned copies.

## 4. Code / tests

Full suite **1724 passed / 16 skipped** in a fresh `/tmp/venv` (+4 over the 1720 baseline). `py_compile` clean on both code files. (DB egress to Neon blocked from the container; PyPI egress works — tests run, no live DB. Note the isolated-collection circular-import quirk: `pytest tests/test_layer3a_builder.py` alone fails to import — run the full `tests/` or front-load a `tests/test_layer4_*.py` so `layer4` imports first.)

## 5. Owed action (Andy's hands)

**None for code** — no migration (code-only). The prompt-body change shifts the 3A/3B content-addressed cache key, so the next plan re-runs both layers fresh (good — it exercises the fix). The live test: a fresh `/plans/v2/new` for PGE 2026 (event mode) — 3A no longer `schema_violation`s on observation text; the cone reaches Layer 4. **Confirm Andy's profile has `body_weight_kg` + `height_cm` first** — else 2E raises a *named* `Layer2EInputError` (still blocks). Stale failed rows (e.g. plan 20) stay terminal — start a fresh plan.

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — email + in-app notifications
Unchanged from the chain: on terminal status in `_advance_plan_generation` (the single terminal hook for poller + cron), send a "plan ready"/"plan failed" email (`email_helper.py`) + a dashboard status badge; guard double-send (transition-into-terminal only, or a `notified_at` column).

### 6.2 Watch — bounded-collection class (now broadly guarded)
The over-emit-vs-cap class is now guarded for `weak_links` (3A list), `notable_observations` count (3B list) **and** `notable_observations[].text` (3A+3B per-string). Remaining un-clamped bounded fields are low-risk per-string bounds the model respects (e.g. HITL-label lists, `reasoning_text` has no cap). Watch the runtime log for a new `schema_violation` token if one surfaces; the #180 detail log + the elimination method pin it fast.

### 6.3 Carried — `load_weight` scale spec reconciliation (doc-only, PR #178)
Still owed: `Layer2A_Spec §5.4` text describes the old 0–100 midpoint; code normalizes to 0–1. See `CARRY_FORWARD.md`.

### 6.4 Operating notes (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items.
4. This handoff.
5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Clamp `notable_observations[].text` to 240 in the driver (not raise the cap) | Claude→Andy | Consistent with #179 decision #1 (clamp, don't raise); raising `Layer3Observation.text` `max_length` is a cross-layer contract change (stop-and-ask). |
| 2 | Truncate at a word boundary + ellipsis (not a hard mid-word cut) | Claude | Coaching copy reads cleanly; the structured decision fields are untouched so the degrade is cosmetic. |
| 3 | Add an LLM-facing <240-char prompt rule (3A rule 6 / 3B rule 9) | Andy ("do that now") | Stops the over-run at the source so the clamp rarely fires (preserving the model's full wording); clamp stays as the backstop. |
| 4 | Reconcile specs/prompts **in place** (not version-bumped) | Claude→Andy ("update all docs appropriately") | On-disk precedent for these files is edit-in-place; literal Rule #12 says version-bump — flagged here so Andy can reverse to versioned copies if he prefers. |
| 5 | Fold the §8.2 `max_items` 6→10 prompt/spec correction in | Andy ("fold that correction in") | The 3B prompt said 6 while the deployed clamp is 10 — the prompt was needlessly under-using the budget. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_clamp_observation_text` + `_truncate_to_word_boundary` defined in `layer3a/builder.py`; called after `_clamp_weak_links` pre-validation | ✅ |
| `_clamp_observation_text` defined in `layer3b/builder.py`; called after `_clamp_notable_observations` in main loop **and** retry loop | ✅ |
| 3A prompt rule 6 + 3B prompt rule 9 carry the "<240 characters" instruction; 3B rule 9 says "capped at 10 items" | ✅ |
| `Layer3_3B_Spec.md` §8.2 says `max_items=10` + documents the clamps | ✅ |
| `Layer3_3A_Spec.md` §7 says weak_links "ordered most-limiting first" + observation-text clamp bullet | ✅ |
| `prompts/Layer3A_v1.md` rule 9 ordering + rule 6 length; `prompts/Layer3B_v1.md` 6→10 (line ~47 + rule 9) + length | ✅ |
| 4 test files green; full suite `pytest tests/` → 1724 passed / 16 skipped | ✅ (fresh `/tmp/venv`) |
| `CARRY_FORWARD.md` doc-only follow-on marked ✅ RECONCILED; PR #181 entry added; walkthrough count +1 | ✅ |
| `CURRENT_STATE.md` last-shipped = PR #181; #179 demoted to predecessor | ✅ |
| Working tree clean after commit | ✅ (verified at push) |

## 9. Files shipped this session

**Substantive (code, 2 files):**
1. `layer3a/builder.py`
2. `layer3b/builder.py`

**Tests:**
3. `tests/test_layer3a_builder.py`
4. `tests/test_layer3b_builder.py`

**Spec / prompt (doc reconciliation, 4 files):**
5. `Layer3_3A_Spec.md`
6. `Layer3_3B_Spec.md`
7. `prompts/Layer3A_v1.md`
8. `prompts/Layer3B_v1.md`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
