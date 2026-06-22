# V5 Implementation — #203 D-77 Slice 3 week-seam stitcher — Closing Handoff (2026-06-21)

**Branch:** `claude/issue-203-status-lmfixa` · **Commit:** `59366b6` · **PR:** opened + auto-merge [PR-gated] · **Issue:** #203 (week-seam stitcher), fast-follow #847.

## 1. What shipped

The **intra-phase week-seam reviewer** (D-77 Slice 3) — the corrective complement to the phase-seam reviewer (`seam_review.py`). Per-week decomposition (Slices 1+2) generates each week of a phase as an independent block, so weeks within a phase can show abrupt week-to-week cliffs; this reviewer blends them.

`#202` (the gate — convergence/cache-key determinism) closed 2026-06-11, so #203 was unblocked (the user's "may already be closed" was a mix-up with #202 — #203 itself was open).

**Trigger #1 prompt + calibration ratified at an AskUserQuestion ×3 gate (2026-06-21):**
1. **Anchor = the deterministic per-week periodization grid**, NOT raw week-over-week deltas.
2. New separate module (reuse the phase-seam machinery).
3. Build now.

The anchor **inverts** the phase-seam logic: each week's actual volume/intensity is judged against the planned multiplier the grid already fixed (`periodization.week_volume_multiplier` + `is_deload_week_for`), so a planned recovery/deload week's ~45% dip reads as CORRECT and only *unjustified* divergence from the planned progression flags.

## 2. Scope decision — review-and-escalate, NOT auto-resynth (stated, ratified path)

This slice ships the **detector**: a non-clean verdict surfaces a `notable_observation` (`warning` for `flagged_minor`; HITL-escalated `seam_unresolved` for `flagged_major`/`patched`) and **records the propose-patch direction**. The **β auto-resynth** of a week-block (re_prompt at week grain) is **gated on the real-LLM walk** per design §7 (cascade-invalidation watch item) + §14, filed as fast-follow **#847**.

Rationale: design §14 says coherence — and whether the reviewer fires usefully and whether re-prompt resolves seams — is judged on a real-LLM run, not unit tests; and §7 flags that a fine-grained re_prompt mutating a block re-rolls the downstream per-block chain hash (cascade invalidation). Wiring that into the 1700-line orchestrator before the walk is the high-risk part. The prompt already emits the direction, so #847 is a pure orchestrator change with no prompt revision.

Findings ride `notable_observations` — **no new `Layer4Payload` field**, so no cross-layer (Trigger #3) schema change.

## 3. Files (6 substantive — one cohesive ratified slice)

| File | Change |
|---|---|
| `aidstation-sources/prompts/Layer4_WeekSeamReviewer_v1.md` | NEW — Trigger #1 prompt body + calibration anchors (design record; runtime body lives in the module) |
| `layer4/week_seam_review.py` | NEW — `SYSTEM_PROMPT`, `compute_week_rollup`, grid-anchored `render_week_seam_prompt`, `review_week_seam`. Imports the phase-seam machinery (`build_record_seam_review_tool`, `_coerce_verdict_combination`, `_default_seam_reviewer_caller`, `SeamReviewerCaller`, `SeamReviewCallResult`, `_format_active_injury_summary`) |
| `layer4/hashing.py` | `compute_week_seam_review_cache_key` (iter-1 cache key; mirrors `compute_seam_review_cache_key`) |
| `layer4/plan_create.py` | week-seam review pass after the phase-seam loop: build intra-phase adjacent-week seams of synthesized phases → cached + parallel iter-1 → observations. `_WEEK_SEAM_CACHE_PHASE_IDX_BASE=2000` namespace; `defaultdict` import; Rule #15 per-seam verdict log |
| `aidstation-sources/specs/Layer4_Spec.md` | §6.6 (the week-seam reviewer + the v1 review-and-escalate ship + the #847 gate) |
| `tests/test_layer4_week_seam_review.py` | NEW — 10 cases (rollup, grid-anchor rendering, verdict/coercion, schema-violation, cache-key determinism) |

## 4. Tests

`tests/test_layer4_week_seam_review.py` +10 (all pass). Full layer4 sweep **1429 passed / 5 pre-existing skips** — plan_create / plan_refresh / hashing / periodization / routes all green (the new pass runs on every Pattern-A `plan_create`, sharing the `seam_caller` stub which returns `approved` → no behavior change to existing tests).

No migration; no `LAYER4_PROMPT_REVISION` bump (that constant governs the *synthesizer* cache, not the seam reviewers — this is a new reviewer prompt with its own cache key).

## 5. Live-verify owed (the real proof — design §14; container can't run plan-gen)

**The real-LLM walk** is what judges whether decomposition actually produces week-to-week cliffs and whether the reviewer fires usefully. If weeks still don't blend even with the reviewer, the seam to cut may be wrong (2-week blocks / day-range splits = a design redo, not a tuning knob). The green suite covers the verdict/cache mechanics, NOT coherence.

On a real plan-gen: `/admin/logs` `week_seam_review: <Phase> wk<n>→wk<n+1> verdict=… direction=… issues=…` per intra-phase seam; a planned deload week should read `approved`, an injected unjustified mid-phase cliff `flagged_major`.

## 6. Owed / carried

- **#847 (fast-follow):** wire the β auto-resynth of a week-block — gated on the walk (§7 cascade-containment, §14). Orchestrator-only.
- **#203:** left OPEN pending #847 (the corrective "blend" half). Close in favor of #847 if you'd rather call the detector done.
- All prior carried items unchanged (see CARRY_FORWARD).

### 6.3 Read order for next session (Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — last shipped (#203) + layer status
3. `CARRY_FORWARD.md` — the #203 walk-owed + #847 entry (top)
4. This handoff
5. `./scripts/verify-handoff.sh` — anchor sweep

## 7. Session-end verification (Rule #10) — anchor table

| File | Anchor string | Check |
|---|---|---|
| `layer4/week_seam_review.py` | `def review_week_seam(` | grep |
| `layer4/week_seam_review.py` | `You are AIDSTATION's Layer 4 week-seam reviewer.` | grep |
| `layer4/hashing.py` | `def compute_week_seam_review_cache_key(` | grep |
| `layer4/plan_create.py` | `_WEEK_SEAM_CACHE_PHASE_IDX_BASE = 2000` | grep |
| `layer4/plan_create.py` | `from layer4.week_seam_review import review_week_seam` | grep |
| `aidstation-sources/specs/Layer4_Spec.md` | `### 6.6 Intra-phase week-seam reviewer (D-77 Slice 3)` | grep |
| `aidstation-sources/prompts/Layer4_WeekSeamReviewer_v1.md` | `# Layer 4 — Week-Seam Reviewer (D-77 Slice 3) — Prompt v1` | grep |
| `tests/test_layer4_week_seam_review.py` | `class TestReviewVerdict` | pytest |
