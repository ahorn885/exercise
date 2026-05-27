# Plan-Gen Per-Week Decomposition — D-77 Slices 1+2 — Closing Handoff

**Session:** Ratified the D-77 design at the gate, then implemented **Slice 1 (per-week decomposition + proactive threading)** and **Slice 2 (progress-based backstop)** — the two slices that close the production non-convergence incident. Code + spec + tests + bookkeeping.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_PerWeekDecomposition_D77_Design_2026_05_27_Closing_Handoff_v1.md` (the design this session implements).
**Branch:** `claude/magical-pasteur-nihYk` (harness-pinned).
**PR:** opened this session (Slices 1+2 as two sequential commits on the one pinned branch — the harness pins a single branch and forbids pushing to another without explicit permission, so "two PRs" collapsed to one PR with two clean commits).
**Status:** 8 substantive files (3 code + 1 spec + ... see §9) + bookkeeping. Suite **1777 passed / 16 skipped** (+15 new tests vs. the 1762 baseline). No application behavior outside Pattern A plan-gen changed.

---

## 1. Session-start verification (Rule #9)

Ran `./aidstation-sources/scripts/verify-handoff.sh` — all ✅ (file existence, backlog pointer, predecessor §8 table). Then spot-checked the design's code anchors against on-disk (content, not narrative): `_run_pattern_a_engine` (`layer4/plan_create.py:442`, 2 callers), `synthesize_phase` + `_MAX_SESSIONS_PER_PHASE=56` (`layer4/per_phase.py`), `_advance_plan_generation` / `cron_generate_pending` / `_CRON_WALL_CLOCK_BUDGET_S=240` (`routes/plan_create.py`), `generation_status`/`generation_error` in `init_db.py`, the three `hashing.py` helpers, `_SEAM_CACHE_PHASE_IDX_BASE=1000` (`plan_create.py:304`). All present; the symbols the design proposes (`compute_block_cache_key`, the 2 columns, `_STALL_PASS_LIMIT`) were absent — consistent with the predecessor's "no code shipped." No drift.

## 2. Session narrative

Andy ratified the D-77 design at an AskUserQuestion gate: **"Ratify + Slices 1 & 2"** with **`_BLOCK_WEEKS=1`**. (I flagged that 1+2 combined exceeds the 5-file ceiling; Andy accepted, so I shipped them as two clean commits.) The two core design decisions were already ratified at the predecessor's gate (stitch = threading + week-seam reviewer now; block = 1 week, tunable). This session implemented Slices 1+2; **Slice 3 (the week-seam stitcher) stays deferred** — it has its own Trigger #1 prompt-design pass before any code (design §11).

**The fix.** The incident: a single per-phase `synthesize_phase` call for a complex multi-discipline plan exceeds the immovable 300s Vercel function cap, so it never caches and the resumable cron 504-loops it forever. The only honest lever (complex is the NORM) is unit size. Slice 1 shrinks the synthesis unit to **one week-block**, which always fits the budget, so each resumable pass caches ≥1 new block → monotonic convergence. Slice 2 adds a **progress-based backstop** that converts any residual zero-progress loop into a loud terminal failure.

## 3. File-by-file

### Slice 1 — decomposition + threading (commit 1)
- **`layer4/hashing.py`** — NEW `compute_block_cache_key(*, call_cache_key, phase_name, phase_index, week_in_phase, prev_accepted_output_hash)`: `compute_phase_cache_key`'s shape + `week_in_phase`.
- **`layer4/per_phase.py`** — `synthesize_phase` gains `week_range: tuple[int,int] | None`; in block mode it scopes the §5.4 validator to the block's date window, filters parsed sessions to that window FIRST (`_filter_raw_sessions_to_window`) then applies the per-block ceiling clamp (`_MAX_SESSIONS_PER_WEEK × block_weeks`, capped at 56). `render_user_prompt` gains `week_range` + block-aware phase-context / prior-week-continuity / output sections; `prior_phase_sessions` → `prior_block_sessions`. New helpers `_block_date_window`, `_filter_raw_sessions_to_window`; new constant `_MAX_SESSIONS_PER_WEEK=14`; `_clamp_sessions_over_emit` parameterized with `max_sessions`. `max_tokens` is deliberately left at the per-phase value per block (a block needs fewer output tokens; scaling down risks truncation + dipping below `extended_thinking_budget`) — a reasoned deviation from the design §4.2 "scale down" note.
- **`layer4/plan_create.py`** — `_run_pattern_a_engine`'s per-phase loop becomes a nested per-`(phase, week-block)` loop: global monotonic block index `u` = cache `phase_idx`; per-BLOCK §9.2 chain (`compute_block_cache_key`, `phase_name="{Phase}:w{week}"`); `prior_block_sessions` threads the preceding block forward (seeded from carryover at a T3 boundary); `_aggregate_block_results` concatenates a phase's blocks back into one `PhaseSynthesisResult` + `SynthesisMetadata` for the unchanged phase-seam tail + final pass. New `_BLOCK_WEEKS=1` knob. The phase-seam re-synth path stays whole-phase (`week_range=None`) — Slice 3 generalizes it. Dropped the now-unused `compute_phase_cache_key` import.
- **`layer4/__init__.py`** — re-export `compute_block_cache_key` (bookkeeping-grade).
- **`aidstation-sources/Layer4_Spec.md`** — §5.2 + §9.2 amended in place (the established precedent for this file).
- **`tests/test_layer4_plan_create.py`** — count-coupled assertions re-expressed from `n_phases` to total week-blocks via a new `_total_blocks()` helper; renamed `prior_phase_sessions=` → `prior_block_sessions=` in the 6 render tests; NEW `TestPerWeekDecomposition` (block-row namespace, window-filter no-duplication, block-mode prompt rendering ×3).
- **`tests/test_layer4_cache.py`** — NEW `compute_block_cache_key` tests in `TestPerPhaseHelpers` (determinism / chains / differs-by-week / first-block None / distinct-from-phase-key).

### Slice 2 — progress-based backstop (commit 2)
- **`init_db.py`** — `_PG_MIGRATIONS` gains two idempotent additive nullable-default columns: `generation_units_cached`, `generation_stall_passes` (same pattern as `generation_status`/`error`).
- **`routes/plan_create.py`** — `_advance_plan_generation` runs the backstop BEFORE the cone: `_count_cached_blocks(db, uid)` (COUNT of `entry_point='plan_create'` rows with `phase_idx` in `[0, _SEAM_CACHE_PHASE_IDX_BASE)`) vs. the count recorded last pass → progress (reset) / no-progress (increment) / shrink (re-baseline); persists the counter (durable against a 504-killed pass), and after `_STALL_PASS_LIMIT=2` consecutive no-progress passes marks the row `failed`. `_load_plan_version` reads the 2 new columns; imports `_SEAM_CACHE_PHASE_IDX_BASE`.
- **`aidstation-sources/Layer4_Spec.md`** — §11.5 backstop note (in place).
- **`tests/test_routes_plan_create.py`** — fixture rows carry the 2 columns; success-path commit count 1→2; NEW `TestCountCachedBlocks` + `TestStallBackstop` (trips after limit without running the cone; progress resets; no first-pass false-trip).

## 4. Code / tests

Full suite **1777 passed / 16 skipped** (`/tmp/venv`; baseline 1762 → +15 new: 5 block-key + 5 decomposition + 5 backstop/count). `pyflakes` clean on the changed modules (two pre-existing unused imports — `Observation` in `per_phase.py`, `Layer4OutputError` in `plan_create.py` — predate this session; left for the periodic `simplify` sweep).

## 5. Owed actions + manual verification

- **⚠ Owed (Andy's hands), in order:**
  1. `python init_db.py` on Neon — adds `generation_units_cached` + `generation_stall_passes` (idempotent, no backfill; container egress to Neon is blocked, so this is hands-on).
  2. Redeploy (the merge).
  3. **The real-LLM coherence walk** — the load-bearing verification (design §14: the proof is the live run, not unit tests). Generate a complex plan (PGE 2026) and confirm it reaches `ready` without 504-looping AND that the independently-generated weeks blend within a phase. Full walk script in `CARRY_FORWARD.md` (the D-77 entry).
- **No owed action ships in code this session beyond the above.**

## 6. Next session pointers

### 6.1 Next moves — priority order
1. **D-77 owed-deploy + the coherence walk (above), then Slice 3 — the intra-phase week-seam stitcher.** Generalizes `layer4/seam_review.py` to week boundaries with a NEW `prompts/Layer4_WeekSeamReviewer_v1.md` (intra-phase calibration: unjustified week-over-week discontinuity, NOT the phase-step anchors). **Trigger #1** — its prompt body gets its own design/ratification pass before code (design §11 + §12). New `compute_week_seam_review_cache_key` + `_WEEK_SEAM_CACHE_PHASE_IDX_BASE=2000` namespace. Spec: `Layer4_PerWeekDecomposition_D77_Design_v1.md`.
2. **Plan-refresh surface redesign** (parked) — per-concept decisions in the predecessor handoff §7.2; D-77 convergence is foundational to its T3 path, so it sequences after the walk.
3. **Plan-comparison feature** (completes D-64 #9) — per-session old-vs-new field comparison.

### 6.2 Operating notes for next session (read order, Rule #13)
1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what shipped (Slices 1+2) + the 3 prioritized moves.
3. `aidstation-sources/CARRY_FORWARD.md` — the D-77 entry (Slice 3 + owed walk) + the parked tracks.
4. `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` — the design (Slice 3 detail + open items).
5. This handoff.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Implement Slices 1 AND 2 this session (over Slice 1 only / design-only / hold) | Andy (gate) | Together they close the incident. Accepted the >5-file ceiling for the combined scope. |
| **D2** | `_BLOCK_WEEKS=1` (confirmed) | Andy (gate) | Smallest safe unit / max convergence margin; tunable to 2 after the §5.0 latency walk. |
| **D3** | One PR, two commits (over two branches/PRs) | Claude (constraint-driven) | The harness pins one branch + forbids pushing to another without explicit permission; two clean commits preserve the slice separation. |
| **D4** | `max_tokens` stays at the per-phase value per block (over the design's "scale down") | Claude (implementer latitude) | A block emits fewer tokens, so the per-phase cap is ample headroom; scaling down risks truncation + dropping below `extended_thinking_budget`. Cost-neutral (max_tokens is a cap, not a charge). |
| **D5** | Backstop counts all the user's `plan_create` block rows (over isolating to this plan's `call_cache_key`) | Claude (implementer latitude) | The route doesn't hold the call_cache_key (the orchestrator derives it internally) and a 504-killed pass never returns it. Stale rows from a prior plan can only DELAY detection by a pass (the count plateaus → stall still trips), never mask a real stall. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `compute_block_cache_key` exists | ✅ `layer4/hashing.py` `def compute_block_cache_key` |
| `synthesize_phase` block mode | ✅ `layer4/per_phase.py` `week_range:` param + `_filter_raw_sessions_to_window` + `_MAX_SESSIONS_PER_WEEK = 14` |
| Engine per-`(phase, week-block)` loop | ✅ `layer4/plan_create.py` `_BLOCK_WEEKS = 1` + `_aggregate_block_results` + `compute_block_cache_key(` call + `while week <= phase.weeks` |
| Stall backstop | ✅ `routes/plan_create.py` `_STALL_PASS_LIMIT = 2` + `def _count_cached_blocks` + `generation_stall_passes` UPDATE in `_advance_plan_generation` |
| Schema columns | ✅ `init_db.py` `generation_units_cached` + `generation_stall_passes` ALTER lines |
| Spec amended in place | ✅ `Layer4_Spec.md` "D-77 per-week decomposition" (§5.2), "D-77 per-week-block chain" (§9.2), "D-77 progress-based generation backstop" (§11.5) |
| Backlog row + changelog | ✅ `Project_Backlog_v62.md` `D-77` row + 2026-05-27 Changelog entry |
| New tests pass | ✅ `tests/test_layer4_plan_create.py::TestPerWeekDecomposition`, `tests/test_layer4_cache.py::TestPerPhaseHelpers::test_compute_block_cache_key_*`, `tests/test_routes_plan_create.py::{TestCountCachedBlocks,TestStallBackstop}` |
| Full suite | ✅ 1777 passed / 16 skipped |
| `CURRENT_STATE.md` pointer flipped | ✅ "Last shipped session" → this file; design demoted to "Predecessor" |
| No owed deploy shipped in code | ✅ the Neon migration + redeploy + coherence walk are owed-Andy's-hands (§5) |

## 9. Files shipped this session

**Substantive (8):** `layer4/hashing.py`, `layer4/per_phase.py`, `layer4/plan_create.py`, `routes/plan_create.py`, `init_db.py`, `aidstation-sources/Layer4_Spec.md`, `tests/test_layer4_plan_create.py`, `tests/test_layer4_cache.py`, `tests/test_routes_plan_create.py` (the test files counted with their code; `layer4/__init__.py` is a 2-line re-export — bookkeeping-grade).

**Bookkeeping:** `Project_Backlog_v62.md` (D-77 row + changelog), `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

## 10. Carry-forward updates

See `CARRY_FORWARD.md`. Net: the D-77 entry flips from "design — pending ratification" to "**Slices 1+2 shipped; Slice 3 + owed Neon migration + real-LLM coherence walk pending**," with the full §5.0 walk script (generate PGE 2026 → reaches `ready` without 504-looping; read across week seams for coherence; backstop fail-loud check; no-false-trip regression).

**End of handoff.**
