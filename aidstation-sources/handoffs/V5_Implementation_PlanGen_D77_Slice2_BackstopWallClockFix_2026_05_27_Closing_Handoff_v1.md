# Plan-Gen D-77 — Slice 2 Backstop Wall-Clock Fix — Closing Handoff

**Session:** Mid-stream live-incident session. Got up to speed on the just-shipped D-77 Slices 1+2 while Andy ran the first real-LLM coherence walk; it failed ~46s in ("Plan generation stalled"). Diagnosed the failure to the **Slice 2 progress backstop false-tripping** (NOT the decomposition), and replaced the per-call stall counter with a wall-clock gate. Code + spec + tests + bookkeeping.
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_PerWeekDecomposition_D77_Slices1_2_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/gallant-gates-DWmb6` (harness-pinned).
**PR:** opened this session.
**Status:** 2 code files + 1 spec + 1 test file (+ `init_db.py` comment) + bookkeeping. Suite **1780 passed / 16 skipped** (+3 vs. the 1777 baseline). **Decomposition convergence remains UNVERIFIED** — the backstop killed plan 24 before the first week-block could cache; the coherence walk is now runnable.

---

## 1. Session-start verification (Rule #9)

Ran `./aidstation-sources/scripts/verify-handoff.sh` — all ✅. Spot-checked the Slices 1+2 code anchors against on-disk (content, not narrative): `compute_block_cache_key` (`layer4/hashing.py:302`), block-mode `synthesize_phase(week_range=...)` + `_MAX_SESSIONS_PER_WEEK=14` (`layer4/per_phase.py`), the per-`(phase, week-block)` loop + `_BLOCK_WEEKS=1` + `_aggregate_block_results` (`layer4/plan_create.py:85,310,633`), the backstop `_STALL_PASS_LIMIT=2`/`_count_cached_blocks` (`routes/plan_create.py`), and the 2 columns (`init_db.py:1972-1973`). All present; `git log` confirms PR #188 (`086f8d6`) + #187 (`ea3b436`) merged to `main`. No drift. The current prod deploy is `dpl_BMDhBJUcJ8FRieP43LYptqxNEYx5` (= #188).

## 2. Session narrative

Andy pointed me at the Slices 1+2 closing handoff to get up to speed while a fresh plan-gen ran in prod as the coherence walk. It came back **"Plan generation stalled and was stopped"** — the D-77 backstop's terminal message.

**Diagnosis (Vercel runtime logs, deploy-scoped so negatives are reliable):**
- The whole failing window for `plan_version_id=24`: created 03:26:32 → one `POST /plans/v2/24/generate` (504, an `api.anthropic.com` request in flight) at 03:26:35 → cron at 03:27:18 logged the stall-backstop trip → `failed`. **~46 seconds, one LLM call, no `schema_violation`** (clean deploy-scoped negative).
- Code confirmed block mode IS wired on the prod path (`_run_pattern_a_engine` passes `week_range=(week,week_end)` per 1-week block — `plan_create.py:634/669`) and each block **self-commits** the instant it caches (`cache_postgres.py:143`, `db.commit()` per `put`). So zero blocks cached across the window ⇒ the first block never finished.
- **Root cause = the Slice 2 backstop, not the decomposition.** The stall trip was a per-CALL counter (`_STALL_PASS_LIMIT=2` consecutive no-progress passes), and BOTH the every-minute cron and the progress-screen poller call `_advance_plan_generation` on the same `generating` row. The backstop ran BEFORE the cone and incremented on a call-to-call basis: poller-start ticked `generation_stall_passes` 0→1 (then began the first ~300s block), the cron 43s later (block still in flight) ticked 1→2 → trip → `failed`. The stall counter advances on wall-clock cadence (~every cron fire) while progress advances on synthesis cadence (≤300s/block), so the counter always wins — **any plan whose first block takes longer than ~one cron interval is killed before it can cache, regardless of whether it would converge.** `_count_cached_blocks` itself is correct (returns 0 because nothing cached yet, not a query bug).

**The fix (Andy's gate: "Fix backstop, then re-run").** Replaced the per-call counter with a **wall-clock-since-last-progress gate** (`_generation_stalled`): trip only when no `plan_create` block has cached for `_STALL_WALLCLOCK_S` (900s, ~3 function budgets), measured on the DB clock (`NOW()` vs. `MAX(layer4_cache.created_at)` for the user's block rows, falling back to `plan_versions.created_at` when none has cached). This can't false-trip a block legitimately in flight, and concurrent cron/poller calls can't race it. Migration-free (uses existing `created_at` timestamps). The loud-fail safety net for a genuinely over-budget unit is preserved (just time-gated, not count-gated).

## 3. File-by-file

- **`routes/plan_create.py`** — replaced `_STALL_PASS_LIMIT=2` with `_STALL_WALLCLOCK_S=900` (+ rationale comment naming the cron/poller race). New `_generation_stalled(db, user_id, plan_version_id)` helper (single SQL: `NOW() - COALESCE(MAX(block.created_at), pv.created_at) > _STALL_WALLCLOCK_S × INTERVAL '1 second'`). `_advance_plan_generation`: the backstop now short-circuits on `_generation_stalled` (before the cone); on the not-stalled path it persists `generation_units_cached = now_cached` (telemetry only) then runs the pass. `generation_stall_passes` is no longer written.
- **`init_db.py`** — schema comment for the 2 D-77 columns updated to describe the wall-clock gate; notes `generation_stall_passes` is retained-but-unused (no drop migration). No DDL change.
- **`aidstation-sources/Layer4_Spec.md`** — §11.5 D-77 backstop note amended in place: the trip is wall-clock (`_generation_stalled` / `_STALL_WALLCLOCK_S`), with a dated correction recording the per-call-counter false-trip (plan_version_id=24).
- **`tests/test_routes_plan_create.py`** — rewrote `TestStallBackstop` (3 tests) for the wall-clock behavior incl. `test_in_flight_first_block_does_not_false_trip` (the plan-24 regression); new `TestGenerationStalled` (3 tests: over-window True / within-window False / missing-row False + SQL-shape assertions). Added `_generation_stalled` to the import.

## 4. Code / tests

Full suite **1780 passed / 16 skipped** (`/tmp/venv`; baseline 1777 → +3 new `TestGenerationStalled`; the 3 `TestStallBackstop` tests were rewritten in place). `pyflakes` clean on `routes/plan_create.py` + `init_db.py` (the 2 flags it reports — `pytest`, `Layer3BOutputError` in the test file — predate this session; left for the `simplify` sweep).

## 5. Owed actions + manual verification

- **⚠ Owed (Andy's hands), in order:**
  1. **Redeploy** (merge this PR). No Neon migration owed — the 2 D-77 columns are already applied (plan 24 ran the backstop with no column error) and this fix is migration-free.
  2. **Re-run the real-LLM coherence walk** — NOW it actually exercises decomposition. Generate a complex plan (PGE 2026) and watch: (a) does it reach `generation_status='ready'` without 504-looping? (b) Vercel log shows `synthesize_phase: <Phase>:w1`, `:w2`, … per week-block (not per phase), and the cached-block count climbs pass over pass; (c) **coherence — the real proof (design §14):** do the independently-generated weeks blend within a phase (continuous ramp, planned recovery), no abrupt week-over-week cliffs? Steps at phase boundaries are intended. If weeks don't blend even with threading, that's a **design redo** (2-week blocks / day-range splits), NOT a knob — report back before Slice 3. Full walk in `CARRY_FORWARD.md` (the D-77 entry).
- **No owed action ships in code this session beyond the above.**

## 6. Next session pointers

### 6.1 Next moves — priority order
1. **The coherence walk (above).** This is the still-open question Slices 1+2 set out to answer — the backstop fix just unblocks it. If it converges + blends, the incident is closed and **Slice 3 (intra-phase week-seam stitcher)** is next (its own **Trigger #1** prompt-design pass before code; new `prompts/Layer4_WeekSeamReviewer_v1.md` + `compute_week_seam_review_cache_key` + `_WEEK_SEAM_CACHE_PHASE_IDX_BASE=2000`; design §11/§12).
2. **Plan-refresh surface redesign** (parked) — per-concept decisions in the Slices-1+2 predecessor handoff §7.2; gates on D-77 convergence (shared T3 engine).
3. **Plan-comparison feature** (completes D-64 #9) — per-session old-vs-new field comparison.

### 6.2 Operating notes for next session (read order, Rule #13)
1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what shipped (this backstop fix) + the 3 prioritized moves.
3. `aidstation-sources/CARRY_FORWARD.md` — the D-77 entry (the UPDATE note + the now-runnable walk) + parked tracks.
4. `aidstation-sources/Layer4_PerWeekDecomposition_D77_Design_v1.md` — the design (Slice 3 detail + the §14 "is the seam right" gut check).
5. This handoff + the Slices 1+2 predecessor.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Fix the backstop, then re-run (over neutering to test first / a design discussion) | Andy (gate) | The backstop is the thing killing good runs; fixing it properly both unblocks the walk and removes the false-trip permanently. |
| **D2** | Stall trip = wall-clock-since-last-progress (over the per-call counter) | Claude (root-cause-driven) | The cron + poller both advance the row and a single pass legitimately needs a full ~300s budget for its first block; a call-count trip is structurally guaranteed to race the synthesis cadence. Wall-clock measures the thing we actually mean ("no progress for too long"). |
| **D3** | `_STALL_WALLCLOCK_S = 900` (~3 function budgets) | Claude (implementer latitude) | Comfortably above the worst-case legitimate time-to-first-block (cold cone + a ~300s block over a couple passes), so a progressing plan never false-trips; still a bounded loud fail (vs. the original ~30-min manual kill). Tunable. |
| **D4** | Migration-free (gate on existing `created_at`) over a new `last_progress_at` column | Claude (constraint-driven) | `plan_versions.created_at` + `MAX(layer4_cache.created_at)` already give "time since last progress"; avoids another owed Neon migration so Andy can redeploy + re-run immediately. `generation_stall_passes` left in place (unused) — no drop migration. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| Wall-clock constant replaces the counter | ✅ `routes/plan_create.py` `_STALL_WALLCLOCK_S = 900`; `_STALL_PASS_LIMIT` gone except in an explanatory comment |
| Wall-clock gate helper | ✅ `routes/plan_create.py` `def _generation_stalled` (SQL: `NOW() - COALESCE(MAX(created_at), pv.created_at) > ? * INTERVAL '1 second'`) |
| Backstop short-circuits on it | ✅ `_advance_plan_generation` calls `_generation_stalled(...)` before the cone; `generation_stall_passes` no longer written |
| Spec amended in place | ✅ `Layer4_Spec.md` §11.5 "wall-clock on the DB clock" + the dated plan-24 correction |
| Schema comment updated | ✅ `init_db.py` D-77 column comment describes the wall-clock gate + retained-but-unused `generation_stall_passes` |
| Tests rewritten + added | ✅ `tests/test_routes_plan_create.py::TestStallBackstop` (incl. `test_in_flight_first_block_does_not_false_trip`) + new `TestGenerationStalled` |
| Backlog + changelog | ✅ `Project_Backlog_v62.md` D-77 row Slice-2 note updated + 2026-05-27 changelog entry |
| Full suite | ✅ 1780 passed / 16 skipped |
| `CURRENT_STATE.md` pointer flipped | ✅ "Last shipped session" → this file; Slices 1+2 demoted to Predecessor |
| No owed migration | ✅ migration-free; the 2 D-77 columns are already on Neon (plan 24 ran the backstop) |

## 9. Files shipped this session

**Substantive (4):** `routes/plan_create.py`, `aidstation-sources/Layer4_Spec.md`, `tests/test_routes_plan_create.py`, and `init_db.py` (comment-only — bookkeeping-grade).

**Bookkeeping:** `Project_Backlog_v62.md` (D-77 row + changelog), `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

## 10. Carry-forward updates

See `CARRY_FORWARD.md` (the D-77 entry). Net: an UPDATE note records the backstop false-trip + the wall-clock fix; the owed action drops to "redeploy + re-run the walk" (migration already applied); the walk's backstop/regression steps are corrected from the retired per-pass counter to the wall-clock gate. **Decomposition convergence is still the open question** — the walk now actually tests it.

**End of handoff.**
