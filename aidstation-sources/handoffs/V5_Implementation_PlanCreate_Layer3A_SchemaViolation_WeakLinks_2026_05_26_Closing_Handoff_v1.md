# plan-create Layer 3A schema_violation (weak_links) + bounded-collection hardening — Closing Handoff

**Session:** Diagnosed a live "Plan generation didn't finish — Athlete evaluation failed (schema_violation)" report, pinned it via the Vercel runtime log to a **`Layer3AOutputError(schema_violation)` on `current_state.weak_links`**, fixed it, then (Andy-directed) hardened the same bounded-collection failure class across 3A/3B + closed the route's error-taxonomy gap + did the full `phase_weeks` fix. Root cause: PR #178 changed the 2A payload, which changed 3A's content-addressed cache key, so **3A re-ran fresh in prod for the first time** — and for a multi-discipline athlete the model emits >5 `weak_links`, which the Anthropic API does not hard-cap (tool-schema `maxItems` is only a hint), so it failed `Layer3APayload`'s `max_length=5` on both capped-retry attempts and walled the cone.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_EventModeBlockers_2026_05_26_Closing_Handoff_v1.md` (§the event-mode blocker chain, PR #178 `15ff2a7`)
**Branch:** `claude/awesome-cray-wiXk4`
**PR:** #179 (2 commits: `b8f473f` schema_violation + taxonomy; `3fcf8ff` priority/twin/phase_weeks)
**Status:** 5 substantive files (`layer3a/builder.py`, `routes/plan_create.py`, `layer3b/builder.py`, `layer4/context.py`, `layer4/phase_structure.py`) + 4 test files + bookkeeping. Full suite **1720 passed / 16 skipped** (+6 over the 1714 baseline).

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor) | Anchor | Result |
|---|---|---|
| PR #178 merged to `main` (`15ff2a7`) | `git log` | ✅ present; branch base |
| `_clamp` / normalize / `viability_current_date` edits present | `verify-handoff.sh` | ✅ all anchors green |

Andy reported the live symptom directly ("Athlete evaluation failed (schema_violation)" after the #178 deploy), so the session was bug-driven.

## 2. Session narrative

The error string is built at `routes/plan_create.py:264` (`Athlete evaluation failed ({exc.code})`) — the typed Layer 3 catch, so it's a `Layer3AOutputError`/`Layer3BOutputError` with code `schema_violation`. Static analysis cleared the deterministic suspects (tool-schema↔pydantic field-presence drift; driver-stamped event fields; the retry feedback), so the cause was an LLM-output conformance failure — and which field needed the prod log.

Diagnosed via the **Vercel runtime-log MCP** by the predecessor's full-text-elimination method (the MCP collapses each request to one line, but whole-token substring search is reliable). On today's cron `generate-pending` requests: `Layer3AOutputError`, `schema_violation`, `current_state`, `weak_links` **all match**; `Layer3BOutputError`, `recent_trajectory`, `skill_assessments`, `data_density`, `notable_observations` **do not**. → the failing locus is `current_state.weak_links`, whose only constraint is `max_length=5`. Why 3A and why now: 3A's cache key is content-addressed on the 2A payload hash; #178 normalized `load_weight` → the key changed → 3A re-ran fresh (no longer a hit), and a 6-discipline athlete legitimately draws >5 weak links.

Andy then directed the forward set: add `weak_links` priority ordering; fix the latent twin (`notable_observations`) and raise its cap to 10; do the full `phase_weeks` fix. A prior background audit confirmed the deep Layer-4 stretch (per-phase synth → seam review → final validator) has **no** deterministic schema↔model walls (the final validator self-heals).

## 3. File-by-file edits

### 3.1 `layer3a/builder.py` (modified)
- `_clamp_weak_links(candidate)` — trims `current_state.weak_links` to the cap (`_WEAK_LINKS_MAX_ITEMS = 5`, shared with the tool-schema `maxItems`) **before** `Layer3APayload.model_validate`, so an over-emit degrades gracefully instead of `schema_violation`. Called in the validation loop after candidate assembly.
- 3A system-prompt rule 9 now orders `weak_links` **most-limiting first** → the first-5 clamp is a principled top-5, not an arbitrary cut.

### 3.2 `routes/plan_create.py` (modified)
- Typed-catch `Layer2A/B/C/D/E` + `Layer2ModalityInputError` in `_advance_plan_generation` → a named, diagnosable failure (`Plan setup failed ({type})`) instead of the opaque catch-all. Closes the gap where Layer 1/2 input failures (notably 2E's `body_weight_kg`/`height_cm` gate) surfaced as "failed unexpectedly".

### 3.3 `layer3b/builder.py` (modified)
- `_clamp_notable_observations(candidate)` — pre-validation **priority** clamp (warning > opportunity > data_gap > data_hygiene; ties by emission order) mirroring the weak_links fix; called in both the main loop and the sanity-loop retry. Closes the twin wall (the existing `_trim_observations_to_budget` runs post-validation, so it never protected the raw over-emit path).
- Budget cap raised **6 → 10** via new `_NOTABLE_OBSERVATIONS_MAX`, shared by the tool-schema `maxItems`, the clamp, and `_trim_observations_to_budget`'s default. Hoisted `_OBSERVATION_CATEGORY_PRIORITY`.
- `_check_periodization_sanity` tightened: a `custom` shape with no positive `phase_weeks` **at/after `start_phase`** now fails (the total-sum check could pass while the post-start allocation was empty), routing through the existing retry→fallback-to-standard. New `_PERIODIZATION_PHASE_ORDER` constant.

### 3.4 `layer4/context.py` (modified)
- `Layer3BPayload.notable_observations` `max_length` **6 → 10** (lock-step with `_NOTABLE_OBSERVATIONS_MAX`; comment cross-references it).

### 3.5 `layer4/phase_structure.py` (modified)
- The three bare `ValueError`s in the decomposition path (`_allocate_weeks_standard`, `_allocate_weeks_custom`, the `total_weeks<=0` guard) → typed `Layer4InputError("periodization_shape_unusable", detail=...)`, so a degenerate shape surfaces as a coded message (caught by the route) instead of a raw 500. Defense-in-depth behind §3.3's upstream catch.

### 3.6 Tests (modified)
- `tests/test_layer3a_builder.py` — +2: over-cap weak_links clamped (no schema_violation); at-cap unchanged.
- `tests/test_routes_plan_create.py` — +1: a `Layer2EInputError` marks the row `failed` with a named message (not "unexpectedly").
- `tests/test_layer3b_builder.py` — +3: periodization sanity rejects weeks-before-start (unit + e2e fallback); notable_observations over-budget clamp keeps warnings. Updated `test_observation_max_items` 6→10.
- `tests/test_layer4_phase_structure.py` — updated 2 assertions: `ValueError` → `Layer4InputError("periodization_shape_unusable")`.

## 4. Code / tests

Full suite **1720 passed / 16 skipped** in a fresh `/tmp/venv` (+6 over the 1710/1714 chain baseline). `py_compile` clean on all 5 substantive files. (DB egress to Neon blocked from the container; PyPI egress works — tests run, no live DB.)

## 5. Owed action (Andy's hands)

**None for code** — no migration (code-only). The live test is a fresh `/plans/v2/new` for Andy's PGE 2026 (event mode): 3A no longer `schema_violation`s on weak_links, the cone reaches 2E → Layer 4. **Confirm Andy's profile has `body_weight_kg` + `height_cm` first** — else 2E raises `Layer2EInputError`, which now shows a *named* failure (§3.2) but still blocks. Stale failed rows stay terminal — start a fresh plan.

## 6. Next session pointers

### 6.1 Spec reconciliation (doc-only — owed, deferred this session)
Two contracts now lag the code (held out to keep PR #179 code-scoped):
- **`Layer3_3B_Spec §8.2`** + `prompts/Layer3B_*` say `max_items=6`; code is now 10. Reconcile to 10 (the §8.2 priority-drop order is unchanged; note the cap is enforced pre-validation by `_clamp_notable_observations` AND post-validation by `_trim_observations_to_budget`).
- **`Layer3_3A_Spec §7`** + `prompts/Layer3A_v1.md` rule 9: add the new "ordered most-limiting first" semantic for `weak_links` (the basis for keeping the first 5). Per Rule #12 these carry version-suffix bumps; they're Andy's design artifacts.

### 6.2 Carried — the 2E athlete-data gate (data, not wiring)
2E `_validate_inputs` (`layer2e/builder.py:302-311`) requires `performance.body_weight_kg` + `identity.height_cm`. Now caught as a named `Layer2EInputError` (§3.2); still needs the profile populated. Confirm before the live test.

### 6.3 Architect-recommended next forward move — §6.3 email + in-app notifications
Unchanged from the predecessor chain: on terminal status in `_advance_plan_generation` (the single terminal hook for poller + cron), send a "plan ready"/"plan failed" email (`email_helper.py`) + a dashboard status badge; guard double-send (transition-into-terminal only, or a `notified_at` column).

### 6.4 Watch — bounded-collection class + uncached seam tail (carried)
The over-emit-vs-cap class is now guarded for `weak_links` (3A) and `notable_observations` (3B); other bounded collections (e.g. 3A observation `text` 240-char, HITL lists) are not yet clamped — low risk (per-string bounds the model respects), watch if a new `schema_violation` appears. The Layer-4 seam-review + final-validator tail is still uncached (re-runs whole on resume); Pro 300s makes a kill-and-resume tractable.

### 6.5 Operating notes (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items.
4. This handoff.
5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Clamp `weak_links` to 5 in the driver (not raise the cap) | Andy | Enforces the existing `Layer3_3A_Spec §7` contract deterministically; paired with the prompt priority-ordering it's a principled top-5. |
| 2 | Order `weak_links` most-limiting first in the 3A prompt | Andy | Makes the first-5 clamp meaningful (lead with the weaknesses that most constrain training). |
| 3 | Pre-validation priority clamp for `notable_observations` + raise cap 6→10 | Andy | Fixes the twin of the weak_links wall (post-validation trim never runs on the raw over-emit path); 10 gives multi-category + required-trigger room. |
| 4 | Full `phase_weeks` fix: tighten 3B sanity (at/after start_phase) + typed Layer4 backstop | Andy | (1) routes a degenerate custom shape through the existing fallback-to-standard so it produces a working plan; (2) any residual degenerate allocation surfaces as a coded message, not a 500. |
| 5 | Widen route error taxonomy to Layer 1/2 input errors | Claude→Andy ("fix safe items") | Turns the next opaque wall (2E data gate) into a named, diagnosable failure. |
| 6 | Defer spec-text reconciliation (§8.2 cap, §7 weak_links ordering) to a doc-only follow-on | Claude | Keeps PR #179 code-scoped; spec edits carry the Rule #12 version-suffix + are Andy's design artifacts. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_clamp_weak_links` defined + called pre-validation in `layer3a/builder.py`; prompt rule 9 "most-limiting first" | ✅ |
| `(Layer2A/B/C/D/E + Layer2Modality)InputError` catch in `routes/plan_create.py` | ✅ |
| `_clamp_notable_observations` defined + called (main loop + sanity retry); `_NOTABLE_OBSERVATIONS_MAX = 10` | ✅ |
| `Layer3BPayload.notable_observations` `Field(max_length=10)` in `layer4/context.py` | ✅ |
| `_check_periodization_sanity` rejects no-weeks-at/after-start_phase; `_PERIODIZATION_PHASE_ORDER` | ✅ |
| 3 bare `ValueError`s → `Layer4InputError("periodization_shape_unusable")` in `layer4/phase_structure.py` | ✅ |
| 4 test files updated/added; full suite `pytest tests/` → 1720 passed / 16 skipped | ✅ (fresh `/tmp/venv`) |
| Working tree clean after commit | ✅ |

## 9. Files shipped this session

**Substantive (5 files):**
1. `layer3a/builder.py`
2. `routes/plan_create.py`
3. `layer3b/builder.py`
4. `layer4/context.py`
5. `layer4/phase_structure.py`

**Tests:**
6. `tests/test_layer3a_builder.py`
7. `tests/test_routes_plan_create.py`
8. `tests/test_layer3b_builder.py`
9. `tests/test_layer4_phase_structure.py`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
