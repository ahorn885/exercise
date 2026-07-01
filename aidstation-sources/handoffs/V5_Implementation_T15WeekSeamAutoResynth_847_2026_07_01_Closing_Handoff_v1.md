# V5 Implementation — T-1.5 (#847 week-seam auto-resynth) — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4
Global order, picking up T-1.5 — the plan's own "most complex task" — right after it was flagged
next/unblocked by the predecessor session.
**Date:** 2026-07-01
**Predecessor handoff:** [`V5_Implementation_T14Taper_WS2RenderTrim_T32T33_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_T14Taper_WS2RenderTrim_T32T33_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/aidstation-implementation-handoff-mcncf7`
**Status:** T-1.5 CODE fully built + tested per the plan's 7 steps. 2 substantive files touched
(`layer4/plan_create.py`, `layer4/hashing.py`) — well under the 5-file ceiling. Suite: **4181 passed /
49 skipped, 0 failed** (+5 over the T-3.3/WS-2 baseline of 4176/49).

---

## 1. Session-start verification (Rule #9)

Ran `bash aidstation-sources/scripts/verify-handoff.sh` — every automated anchor from the predecessor
handoff's §8 table (taper anchor, Layer2B/3B trims, terrain-gap + goal-viability + race_url renders,
prompt revision "21", #831 normalizer, solo-athlete flag + migration, Layer 2A gate) resolved ✅. No
drift between the predecessor's narrative and on-disk `main`; no reconciliation needed. Working branch
was already even with `origin/main` (the predecessor's PR #1126 was merged before this session started).

---

## 2. Session narrative

Per the plan's §4 Global order, T-1.5 was the next unblocked item (T-1.4/R3 precondition met, `GATE:
none`). This session ran outside `/plan` mode (no live Andy chat available this session — an async
continuation) and executed the plan's 7 steps directly, since the task carries no `GATE:` requiring a
prior ratification (unlike WS-2's render/trim table or T-3.3's solo/team design call).

Read the phase-seam re-synth template (`plan_create.py` — the whole-phase re-synth loop, the
`[500,1000)` cache band, `compute_seam_resynth_block_cache_key`, the iter-2 cached review) and the
existing week-seam review-and-escalate pass line-by-line before writing anything, per the task's own
step 1 instruction.

Two design points needed resolving beyond what the plan's prose states literally, both recorded in the
plan doc's as-built note:

1. **R4's cache band** literally asked for "a NEW sub-band inside `[0,1000)`" that doesn't collide with
   the two bands already occupying the ENTIRE `[0,1000)` range. Resolved by widening the counted range
   itself (`_SEAM_CACHE_PHASE_IDX_BASE` 1000→1500) rather than trying to fit a third band into an
   already-full two-band space — confirmed via repo-wide grep that nothing hardcodes the old literal
   `1000`, only the symbolic constant.
2. **CW-b's "unchanged" comparison** needed a session-content hash that excludes `session_id` — a
   naive full-session hash would have made "unchanged" vacuously always-false, because `session_id` is
   stamped from the caller's own `session_id_prefix`, which differs between a primary block and its
   resynth block by construction. Caught by the very first test written against it (a scripted
   "identical" resynth output still hashed as "changed" until the field was excluded).

Full narrative + every other judgment call is in the plan doc's T-1.5 as-built note (kept there per
Rule #11 rather than duplicated here).

---

## 3. File-by-file edits

### 3.1 `layer4/hashing.py` (modified)

- `compute_week_seam_resynth_block_cache_key()` — new chained cache-key helper for a week-seam-driven
  single-week re-synth block, mirroring `compute_seam_resynth_block_cache_key` (the phase-seam
  analogue) but hashing the live `prior_week_sessions` directly instead of chaining a whole-phase
  `prev_accepted_output_hash`.
- `compute_sessions_content_hash()` — new CW-b comparison hash, deliberately excluding
  `synthesis_metadata` (token counts always differ across two real LLM calls) AND `session_id` +
  `plan_version_id` (both per-call synthetic, not content).

### 3.2 `layer4/plan_create.py` (modified)

- Cache-band comment block + constants rewritten: `_SEAM_CACHE_PHASE_IDX_BASE` 1000→1500,
  `_SEAM_ITER2_CACHE_PHASE_IDX_BASE` 2000→2500 (kept in lockstep), new
  `_WEEK_SEAM_RESYNTH_BLOCK_IDX_BASE = 1000` sub-band (stride 2: primary-target slot + CW-b-downstream
  slot) + `_week_seam_resynth_block_phase_idx()` helper. `_seam_resynth_block_phase_idx`'s own assert
  tightened to the new adjacent boundary (`_WEEK_SEAM_RESYNTH_BLOCK_IDX_BASE`) so it can't silently
  drift into the new band.
- `_merge_week_resynth_meta()`, `_sessions_before_week()`, `_splice_week_into_phase_result()` — new
  helpers for CW-c splice-back (replace only the targeted week's sessions inside an already-aggregated
  `PhaseSynthesisResult`, combine the aggregate fields mirroring `_aggregate_block_results`'s own
  2-item combine rule).
- The intra-phase week-seam processing loop (previously review-and-escalate only) now: checks a
  per-(phase, week) retry budget, auto-resynthesizes the ONE targeted week-block on
  `flagged_major`/`patched` + `re_prompt_prior`/`re_prompt_next`, splices it back (CW-c), fires a
  bounded ≤1-hop CW-b downstream rebuild when content genuinely changed and the direction is
  `re_prompt_next`, then re-reviews the seam once at `seam_iteration=2` (per-seam cap 2, mirroring the
  phase-seam path).

---

## 4. Code / tests

New `tests/test_layer4_plan_create.py::TestWeekSeamAutoResynth` (5 tests), +5 over baseline (4176→4181):

- `test_flagged_cliff_re_prompt_next_corrects_the_block` — verify (a): a scripted mid-phase cliff at
  week 2 is flagged + re-synthesized; the corrected content lands in the result. Also exercises CW-b's
  changed→1-downstream-rebuild branch (week 2's content genuinely changes, so week 3 gets one bounded
  rebuild) — caught a test-authoring bug on the first pass (an under-scripted stub fed the rebuild call
  wrong dates, dropping week 3 to zero sessions), which is itself a positive signal that CW-b's
  "content changed" detection is working correctly.
- `test_planned_recovery_week_no_resynth` — verify (b): both seams approve on iter-1 → zero resynth
  calls, original content untouched.
- `test_resynth_cache_row_counted_by_stall_backstop_band` — verify (c): a real resynth run's cache row
  lands inside `[0, _SEAM_CACHE_PHASE_IDX_BASE)`, the exact range `_count_cached_blocks` counts.
- `test_week_seam_resynth_phase_idx_stays_in_disjoint_band` — direct unit check mirroring the existing
  phase-seam analogue (`test_seam_resynth_phase_idx_stays_in_disjoint_band`).
- `test_unchanged_resynth_output_does_not_invalidate_downstream_week` — verify (d): CW-b's
  unchanged-content branch — exactly 4 synthesizer calls (3 primary + 1 resynth), no 5th downstream
  call.

A single-phase 3-week fixture (`periodization_shape.mode="custom"`, one Base phase) keeps phase-seam
review out of the picture entirely (0 phase-seams exist with only 1 phase), and a `_SequentialExecutor`
test double forces the normally-concurrent iter-1 week-seam-review dispatch into deterministic,
scriptable call order.

Full suite: **4181 passed / 49 skipped, 0 failed**. `ruff check` on both touched files — 0 new findings
(2 pre-existing findings, `plan_create.py`'s unused `Layer4OutputError` import and
`test_layer4_plan_create.py`'s unused `RaceDayFueling` import, confirmed unchanged via `git stash`
diff).

---

## 5. Manual §5.0 verification steps

None new. T-1.5's real-LLM verification rides the SAME walk already pending for T-2.9 (see §6 below) —
no separate manual walkthrough scenario added to `CARRY_FORWARD.md` this session; the existing T-2.9
walk checklist in the plan doc should get a T-1.5 addendum when Andy is ready to run it (see §6.1).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

T-1.5's CODE is done, but issue #847's own text explicitly gates its cascade-containment logic and its
overall "does this actually help" judgment on a real-LLM walk (container can't run one). Recommend
folding a T-1.5 checklist into the SAME real-LLM walk already pending for T-2.9 (both are Layer-4
synthesis-loop behavior best judged together on one real plan generation) rather than running two
separate walks. A T-1.5 walk item to add: generate/refresh a plan, watch for a `week_seam_review:
... verdict=flagged_major/patched` log line, confirm the auto-resynth actually improves the flagged
week's coherence (not just replaces it with an equally-off block), and confirm the CW-b downstream
rebuild (when it fires) doesn't visibly thrash cost/latency.

### 6.2 Alternative pivots

- **T-3.1 (#1060)** — small, `GATE: none`, its prompt-content effect also rides the T-2.9 walk. Cheap
  next pick if Andy wants a quick win before the walk.
- **T-3.3's discipline-flagging follow-up** and **#1125** (CI-wiring fast-follow) remain open,
  ungated, from before this session.

### 6.3 Operating notes for next session

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
6. `bash aidstation-sources/scripts/verify-handoff.sh`

**PR note (per the repo's settled convention, CLAUDE.md → Ops automation):** work is committed +
pushed to the session branch; no PR opened this session (Andy's explicit, previously-settled rule —
push, bookkeep, wait for his go, without re-flagging it each session).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Widen `_SEAM_CACHE_PHASE_IDX_BASE` 1000→1500 rather than shrink the phase-seam-resynth band to make room | This session (no Andy chat available) | `[0,1000)` was already fully claimed by the 2 existing bands; nothing in the repo hardcodes the old literal (grep-confirmed), so widening the counted range is a safe, symbolic-only change. Reversible if Andy wants a different split. |
| 2 | CW-b downstream rebuild fires only for `direction=="re_prompt_next"`, not `re_prompt_prior` | This session | For `re_prompt_prior`, `target_week+1` IS the other side of the SAME seam (`ws.next_week`) — already re-judged by the mandatory iter-2 re-review (step 6). A mechanical rebuild there would duplicate/conflict with that judgment call rather than genuinely extend CW-b's "downstream, outside this seam" intent. |
| 3 | Per-(phase, week) resynth retry budget as a NEW separate dict, not reusing `retries_used_per_phase` | This session | Task text explicitly frames the budget as "(phase, week)", not "(phase)"; two different week seams can target the same (phase, week), mirroring how two adjacent phase-seams already share a phase's budget. |
| 4 | T-1.5's real-LLM walk folded into T-2.9's pending walk rather than a separate one | This session | Issue #847's own text gates it on a real-LLM walk the container can't run; T-2.9 already has one pending for the same reason, and both are Layer-4 synthesis-loop behavior best judged on one real generation rather than two separate walks. |

---

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Week-seam-resynth cache key | `layer4/hashing.py` | `def compute_week_seam_resynth_block_cache_key(` |
| CW-b content hash | `layer4/hashing.py` | `def compute_sessions_content_hash(` |
| Cache band bump | `layer4/plan_create.py` | `_SEAM_CACHE_PHASE_IDX_BASE = 1500` |
| New resynth band | `layer4/plan_create.py` | `_WEEK_SEAM_RESYNTH_BLOCK_IDX_BASE = 1000` |
| Band helper | `layer4/plan_create.py` | `def _week_seam_resynth_block_phase_idx(` |
| Splice-back helper | `layer4/plan_create.py` | `def _splice_week_into_phase_result(` |
| Auto-resynth wiring | `layer4/plan_create.py` | `# --- Auto-resynthesize the ONE targeted week-block` |
| CW-b containment | `layer4/plan_create.py` | `CW-b — cascade containment` |
| Tests | `tests/test_layer4_plan_create.py` | `class TestWeekSeamAutoResynth:` (5 tests) |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4181 passed / 49 skipped |
| Ruff | — | 0 new findings on `layer4/plan_create.py` + `layer4/hashing.py` (git-stash-diff confirmed) |
| Plan doc | `plans/PlanGenReliability_..._v1.md` | T-1.5 as-built note + §4 Global order updated in place |
| Branch | — | `claude/aidstation-implementation-handoff-mcncf7`, pushed, no PR opened |

---

## 9. Files shipped this session

**Substantive (2 files):**
1. `layer4/plan_create.py`
2. `layer4/hashing.py`

**Bookkeeping (4 files):**
3. `tests/test_layer4_plan_create.py` (tests, exempt from the ceiling)
4. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
5. `aidstation-sources/CURRENT_STATE.md`
6. This handoff

---

## 10. Carry-forward updates

None this session — no new manual walkthrough scenarios, doc-sweep nits, or orthogonal tracks
surfaced. `CARRY_FORWARD.md` unchanged.

---

**End of handoff.**
