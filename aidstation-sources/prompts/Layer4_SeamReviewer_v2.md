# Layer 4 Seam-Reviewer Prompt — v2

**Status:** Surgical amendment of `Layer4_SeamReviewer_v1.md` (2026-05-16). Shipped 2026-05-18 paired with Layer 4 implementation Step 4f. v1 retained as in-project history per Rule #12.

**Predecessor:** `Layer4_SeamReviewer_v1.md` (2026-05-16).

**Companion implementation:** `layer4/seam_review.py` (`build_record_seam_review_tool()` + `render_seam_review_prompt()` + `review_seam()` + `_default_seam_reviewer_caller()` + `compose_seam_review_row()`).

**Companion spec sections:** `Layer4_Spec.md` §5.2 step 4 (seam-review call site), §6.2 (β propose-patch authority + verdict→action table + bounds), §7.7 (`SeamReview` schema), §11.1 (latency target ~3-5s per seam), §11.2 (token budget ~6000 input / ~800 output).

---

## v2 changes summary

Single contract-amendment ripple:

1. **PR-C-followon injury source-pointer (2026-05-17):** v1 §3 `active_injury_summary` referenced `Layer3APayload.active_injuries` which never existed in 3A's typed contract. The canonical injury source is `Layer2DPayload.excluded_exercises` + `accommodated_exercises` per `Layer4_Spec.md` §3.2 line 753 (PR-C-followon amendment). v2's §3 input row reads from 2D.

The seam reviewer is structurally light-coupled — it reads weekly rollups + per-session dumps via orchestrator-formatted rendering, so the D1 typed `IntensityTarget` union and D-66 `RaceEventPayload` don't directly surface in the reviewer's input contract (those flow through the synthesizer's input + the pre-rendered session table). The `active_injury_summary` source-pointer is the only v2 amendment.

**System prompt + §6 user-prompt template structure + §7 sampling — unchanged from v1.**

---

## v2 source decisions (delta from v1's D1–D7)

| # | Decision | Choice | Notes |
|---|---|---|---|
| D8 | `active_injury_summary` source | `Layer2DPayload.excluded_exercises` + `accommodated_exercises` (PR-C-followon canonical) | v1 referenced non-existent 3A field; v2 corrects. Renderer surfaces a compact summary line per `seam_review._format_active_injury_summary()` (e.g., "- 2 excluded exercise(s): E-bench-press, E-overhead-press"). Per-modality detail belongs to the per-phase synthesizer, not the reviewer. |

D1–D7 from v1 carry forward unchanged: tool-use (D1), extended thinking ~2000 tokens (D2), hybrid input format (D3), coaching-judgment-with-anchors verdict calibration (D4), constraint-level-only `seam_issues` writing (D5), direct coaching voice + 30-word + 4-entry caps (D6), file location (D7).

---

## §3 input contract — v2 amendment

The full input variable table from v1 §3 carries over. One row is amended:

| Variable | Type | Source | v2 amendment |
|---|---|---|---|
| `active_injury_summary` | list[str] | `Layer2DPayload.excluded_exercises` + `accommodated_exercises` (compact one-line-per-injury rendering) | v1 referenced `3A.active_injuries`; v2 corrects to 2D canonical source. Renderer per `seam_review._format_active_injury_summary()`: "- {N} excluded exercise(s): {ids}" + "- {N} accommodated exercise(s) (per 2D modality framework)". Per-modality detail is the per-phase synthesizer's concern, not the reviewer's. |

The reviewer's job remains phase-transition shape assessment, not session-level validation; the active injury summary is only consumed to NOT flag missing intensity when intensity is medically restricted (per v1 §5 system prompt calibration anchor: "Intensity restricted by an active injury (see active_injury_summary): treat reduced intensity as expected, NOT as a missing element.").

---

## §4 tool schema — unchanged from v1

`record_seam_review` tool definition lives in `layer4/seam_review.py:build_record_seam_review_tool()`. Schema mirrors §7.7 SeamReview minus orchestrator-filled metadata (seam_index, prior/next_phase_name, reviewer_model, *_tokens, *_latency_ms, triggered_resynthesis, re_prompted_phase_name).

Invalid verdict-direction combinations enforced in driver code per `Layer4_Spec.md` §6.2 + v1 §4 — `layer4/seam_review.py:_validate_verdict_combination()` raises `Layer4OutputError('seam_reviewer_invalid_verdict_combination')` on schema violation.

---

## §5 system prompt — unchanged from v1

The full system prompt (verdicts + calibration anchors + patch direction semantics + `seam_issues` writing rules + authority bounds + iteration-2 behavior + voice) is verbatim from v1. Lives in `layer4/seam_review.py:SYSTEM_PROMPT`.

---

## §6 user-prompt template — unchanged from v1; minor variable rename

Template structure (Seam review request → Adjacent phases + race context → Active injury constraints → Intended boundary state → Prior phase weekly rollup + last week → Next phase weekly rollup + first week → Iteration-1 issues conditional → Call to action) is unchanged from v1.

Variable rename: `active_injury_summary` source is now 2D-derived per §3 amendment above. Rendered text format is the same (1 line per item).

Driver code `layer4/seam_review.py:render_seam_review_prompt()` does the inline Python rendering.

---

## §7 sampling — unchanged from v1

`DEFAULT_MAX_TOKENS=1500` + `DEFAULT_EXTENDED_THINKING_BUDGET=2000` + temperature 0.15 (lower than synthesizer's 0.2 per §5.2 step 4.1).

---

## §§8–14 — carry over from v1 unchanged

- §8 authority bounds (recap table) — v1 verbatim.
- §9 verdict calibration anchors — v1 verbatim.
- §10 `seam_issues` writing rules — v1 verbatim.
- §11 edge cases — v1 verbatim.
- §12 test scenarios (SR-1 through SR-15) — v1 verbatim.
- §13 open items / tuning candidates — v1 verbatim.
- §14 gut check — v1 verbatim.

---

## Implementation references (Step 4f)

- `layer4/seam_review.py` — `review_seam()` is the LLM call site (one seam per invocation; called by `plan_create.py` Pattern A engine after per-phase synthesis completes).
- `layer4/plan_create.py:_run_pattern_a_engine()` — applies the §6.2 verdict-to-action table; tracks per-phase retry budget; handles iteration-2 seam re-review after re-synthesis; emits `seam_unresolved` notable_observations on per-seam cap exhaustion.
- `tests/test_layer4_plan_create.py::TestSeamReview` — coverage of approved + flagged_minor + flagged_major+re_prompt_next paths; `TestSeamReviewInvalidCombinations` covers the schema-violation raise on invalid verdict-direction combos.

---

*End of Layer 4 Seam-Reviewer Prompt v2.*
