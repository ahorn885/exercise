# Plan-Gen Per-Week Decomposition + Week-Seam Stitcher — D-77 Design

**Version:** 1.0
**Date:** 2026-05-27
**Status:** DESIGN — core decisions ratified by Andy at an AskUserQuestion gate (stitch strategy = "threading + week-seam reviewer now"; block size = "1 week, tunable"). Architecture (Trigger #5) + cache contract (Trigger #3) + a new intra-phase reviewer prompt (Trigger #1) — implementation slices are **gated on Andy's ratification of this doc**. No code written yet.
**Backlog row:** D-77 (PROPOSED — needs ratification; new cross-layer D-row per Trigger #3).
**Track:** Plan-gen reliability. Closes the production non-convergence incident on `plan_version_id=23` (2026-05-27): a single per-phase synthesizer call exceeded the Vercel 300s function cap, never cached, and 504-looped every cron pass for ~30 min until manually killed (`UPDATE plan_versions SET generation_status='failed'`).
**Affects:** Layer 4 Pattern A engine (`layer4/plan_create.py:_run_pattern_a_engine`), the per-phase synthesizer (`layer4/per_phase.py`), cache-key helpers (`layer4/hashing.py`), the cache namespace (`layer4/cache.py`), the resumable-pass driver (`routes/plan_create.py`), `plan_versions` schema (`init_db.py`), a NEW reviewer prompt (`prompts/Layer4_WeekSeamReviewer_v1.md`), and `Layer4_Spec.md` §5.2 / §6 / §9.2 / §11. Pattern B (T1/T2 refresh) is **out of scope** (single-call, intra-phase, already small).

**Cross-references:**
- `Layer4_Spec.md` §5.2 (Pattern A per-phase synthesis + seam review), §6 (periodization decomposition + seam-reviewer authority), §9.2 (per-phase cache chain), §11 (performance budget).
- `layer4/seam_review.py` — the existing PHASE-level seam reviewer; the week-seam stitcher generalizes its machinery (verdict enum, propose-patch authority, per-seam iter cap 2, cached iter-1) with a new intra-phase calibration.
- `layer4/hashing.py` `compute_phase_cache_key` / `compute_accepted_output_hash` / `compute_seam_review_cache_key` — the chained-cache primitives this design extends.
- `routes/plan_create.py` `_advance_plan_generation` / `cron_generate_pending` (`_CRON_WALL_CLOCK_BUDGET_S=240`) — the resumable-pass driver the progress backstop lives in.
- Incident evidence: Vercel runtime logs, prod deploy `dpl_Lepws…` (#186), 00:53→01:31 UTC 2026-05-27.

---

## 1. Purpose

Plan generation must **converge for the complex multi-discipline, multi-phase, long-horizon plan as the NORM**, not the edge case. Complex plans for complex sports is the product (Andy, 2026-05-27): "we should be planning to accommodate this as the NORM not the edge."

The current Pattern A engine synthesizes **one phase per LLM call** (`synthesize_phase`, up to `_MAX_SESSIONS_PER_PHASE=56` sessions, extended thinking, + capped validator/seam retries). For a 6-discipline expedition plan, a single phase call exceeds the **300s Vercel Pro function ceiling** (which is immovable — `vercel.json` can't raise it and 300s is the plan max). When one unit can't fit the budget, it never caches; the resumable cron redoes it every pass → an infinite 504 loop that never reaches a terminal state.

**The only lever is unit size.** This design shrinks the synthesis unit to one that always fits the budget, guarantees monotonic progress, and preserves coaching coherence across the now-independently-generated units via proactive context-threading + a corrective week-seam stitcher.

## 2. Decisions

| # | Decision | Source |
|---|---|---|
| D1 | Shrink the synthesis unit to **one week** (`_BLOCK_WEEKS=1`), tunable via config (batchable to 2+ if call-count overhead proves high). | Andy (gate) |
| D2 | Coherence = **proactive threading** (always-on) **+ a corrective week-seam reviewer built in this arc** (not deferred). | Andy (gate) |
| D3 | The week-seam reviewer is a **new prompt** with intra-phase calibration; it reuses `seam_review.py` machinery but is NOT the phase-seam prompt (different semantics — see §5.2). | Trigger #1 |
| D4 | The runaway guard is **progress-based, not time-based**: a pass that caches ≥1 new unit is "progressing" regardless of total elapsed; only a pass that caches **zero** units is a stall → fail loudly. Complex plans may take many passes. | Derived from "complex is the norm" |
| D5 | Scope = **Pattern A only** (`_run_pattern_a_engine`): `plan_create` (full cone) + `plan_refresh` T3 cross-phase. Pattern B (T1/T2) untouched. | Derived |
| D6 | No change to the upstream cone (Layers 1–3B) or the phase **skeleton** — 3B + `phase_structure` still fix phase count, weeks-per-phase, intended volume/intensity bands. We only change how a phase's sessions are *filled in*. | Derived |

## 3. Scope & boundaries

- **In scope:** the per-phase synthesis loop + phase-seam review tail inside `_run_pattern_a_engine`; the cache-key chain; the resumable-pass progress guard; `plan_versions` columns; the new week-seam reviewer prompt + call path.
- **Out of scope:** Pattern B (T1/T2 single-call refresh — already small, no seam reviewer per `plan_refresh_key`'s `model_seam_reviewer=None`); the upstream cone (3A/3B/2x) and its caches; the phase skeleton (3B periodization); session schema (`PlanSession` shape unchanged).
- **Invariant preserved:** the final composed `Layer4Payload` shape and the per-entry-point cache (`get_or_synthesize` + §9.4 rebinding) are unchanged. Decomposition lives entirely below the per-entry cache, in the per-unit chain.

## 4. Pillar 1 — per-week synthesis unit

### 4.1 Loop change
`_run_pattern_a_engine`'s sequential `for i, phase in enumerate(phases)` synthesis loop becomes a nested per-`(phase, week)` loop. For each phase to synthesize, iterate `week_in_phase` in `1..phase.weeks` stepped by `_BLOCK_WEEKS` (default 1). Each iteration synthesizes the sessions for that week-block only.

A global monotonic **block index** `u` (0-based, across all synthesized phases) identifies each unit. `u` is the cache-row `phase_idx` (stays `0..W-1`, `W` = total synthesized weeks ≈ ≤30, well below the seam namespace base of 1000).

### 4.2 Synthesizer
`synthesize_phase` is narrowed/duplicated into a **block synthesizer** scoped to a week range:
- New required arg `week_range: tuple[int,int]` (inclusive `week_in_phase` bounds; `(k,k)` for `_BLOCK_WEEKS=1`).
- The `record_phase_sessions` tool's `maxItems` ceiling drops from 56 (whole phase) to a per-block ceiling (`_MAX_SESSIONS_PER_BLOCK`, sized to `_BLOCK_WEEKS × max_sessions_per_week`; ≈ 12–14 for a 6-discipline week with doubles).
- `max_tokens` scales down to the block (a fraction of `max_tokens_per_phase`). The existing per-phase validator (`§5.4`) runs scoped to the block.
- `prev_accepted_output_hash` rolls forward **per block** (finer chain than per-phase): block `u`'s key folds in block `u-1`'s accepted-output hash, so a change at week `k` invalidates `k+1..end` only.

### 4.3 Cache key (extends `hashing.py`)
New `compute_block_cache_key(*, call_cache_key, phase_name, phase_index, week_in_phase, prev_accepted_output_hash)` — same shape as `compute_phase_cache_key` plus `week_in_phase`. The cache row stores `phase_idx=u`, `phase_name=f"{phase_name}:w{week_in_phase}"` (satisfies the `phase_idx>=0 ⇒ phase_name not None` invariant in `cache.py`). `compute_accepted_output_hash` is reused unchanged (hashes the block's `list[PlanSession]` + metadata).

### 4.4 Convergence guarantee
With each block sized to fit the 300s budget (worst case = `capped_retries+1` LLM calls + cold start + composition, target ≪ 300s), **every resumable pass caches ≥1 new block**. A `W`-week plan therefore converges in ≤`W` cron passes regardless of total wall-clock — which is the explicit "complex is the norm" requirement. The §6 backstop catches the residual case where even a single block can't fit (a bug / mis-sized `_BLOCK_WEEKS`) by failing loudly instead of looping.

## 5. Pillar 2 — coherence

Decomposition's cost is intra-phase coherence: a model that saw a whole phase at once balanced volume, sequenced hard/easy days, and distributed disciplines as a unit. Two mechanisms restore it.

### 5.1 Proactive threading (always on; part of the decomposition slice)
`render_user_prompt`'s existing `prior_phase_sessions` continuity arg generalizes to **`prior_block_sessions`** = the immediately-preceding week's accepted sessions (same phase, or the prior phase's last week at a phase boundary). Each block is generated *knowing what preceded it*. The phase **skeleton** (intended volume bands from 2A `phase_load`, `phase_spec.intended_intensity_distribution`, weekly discipline mix) is already in the prompt and constrains every block toward the same phase intent — this is what makes independently-generated weeks land coherently without the model seeing forward.

### 5.2 Corrective week-seam stitcher (NEW — Trigger #1)
A reviewer runs at intra-phase **week seams** (between block `u` and `u+1`), reusing `seam_review.py`'s machinery — the 4-verdict enum (`approved`/`flagged_minor`/`flagged_major`/`patched`), propose-patch authority (`re_prompt_prior`/`re_prompt_next`/`accept_with_observation`), per-seam iteration cap 2, cached iter-1 / uncached iter-2 — but with a **new prompt** (`prompts/Layer4_WeekSeamReviewer_v1.md`) carrying **intra-phase calibration**:

- Within a phase, week-over-week should be **progressive and continuous** (gentle ramp, planned recovery/down weeks) — NOT the deliberate step a phase transition has. The phase-seam anchors (e.g., "a >25% volume drop with no taper rationale = flagged_major") are WRONG here: a planned recovery week's drop is correct. The week-seam prompt's anchors instead key on *unjustified* week-over-week discontinuity relative to the phase's intended weekly progression.
- `re_prompt_prior` / `re_prompt_next` re-synthesize **one week-block** (not a phase).
- Authority bounds mirror the phase reviewer: constraint-level issues, not session rewrites; cannot cross more than one week-hop; cannot change phase boundaries.

Phase-seam reviews (existing, `seam_review.py`) stay exactly as-is at phase boundaries. The week-seam reviewer is additive.

## 6. Pillar 3 — progress-based backstop (`routes/plan_create.py`)

A stall guard that respects "complex is the norm": never abandon a plan for being long; only fail one that makes **zero progress in a full pass**.

- New `plan_versions` columns: `generation_units_cached INT NOT NULL DEFAULT 0`, `generation_stall_passes INT NOT NULL DEFAULT 0`. (`generation_status` / `generation_error` already exist.)
- At the **start** of each `_advance_plan_generation` pass (before doing work — so it's robust to the prior pass being 504-killed mid-flight): count cached block rows for this plan's `call_cache_key`. If `now_count > generation_units_cached` → progress: update `generation_units_cached`, reset `generation_stall_passes=0`. If `now_count == generation_units_cached` → the prior pass cached nothing: `generation_stall_passes += 1`.
- If `generation_stall_passes >= _STALL_PASS_LIMIT` (default **2**): `_mark_plan_failed(..., generation_error="stall: a single synthesis unit exceeds the function budget — see block index N")`. This converts the silent infinite 504 loop into a loud, diagnosable terminal failure.
- The counter resets on any real progress, so a 25-pass complex plan that advances each pass never trips it.

## 7. Caching & determinism (amends §9.2)

- Block rows: `(compute_block_cache_key(...), phase_idx=u)`, `entry_point` unchanged (`plan_create`/`plan_refresh`).
- Week-seam iter-1 rows: a new disjoint namespace `phase_idx = _WEEK_SEAM_CACHE_PHASE_IDX_BASE (=2000) + week_seam_idx`, disjoint from per-block (`0..W-1`) and phase-seam (`1000+seam_idx`). New `compute_week_seam_review_cache_key` mirrors `compute_seam_review_cache_key`.
- Resumed-pass determinism: a hit replays a block (or week-seam review) at zero tokens, exactly as the per-phase chain does today (§9.6).
- **Cascade-invalidation note (watch item):** a late week-seam `re_prompt` mutates a block's output → the chain hash for downstream blocks changes → downstream cache invalidates → redo. Finer grain amplifies this vs. the phase-level model. Containment: the re_prompt is targeted to one side + iter cap 2 already bound it; the design accepts at most one downstream-chain rebuild per flagged week-seam. If churn is observed in the §5.0 walk, a follow-on can pin re-synthesis to not re-roll the chain when the re-prompted block's output hash is unchanged.

## 8. Schema changes

`init_db.py` (idempotent, additive, nullable-with-default — same migration pattern as the `generation_status`/`generation_error` add):
```
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_units_cached INTEGER NOT NULL DEFAULT 0;
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_stall_passes INTEGER NOT NULL DEFAULT 0;
```
No backfill needed (defaults are correct for in-flight rows). **Owed-Andy's-hands:** `python init_db.py` on Neon + redeploy (container egress to Neon is blocked).

## 9. Performance budget (amends §11)

- **Call count ↑:** a 15-week plan ≈ 15 block synths + ~14 week-seam iter-1 reviews vs. today's ~4 phase synths + ~3 phase-seam reviews. ~4× more calls.
- **Mitigations:** (a) each block call is small (smaller `max_tokens`, faster); (b) prompt caching — the system prompt + upstream payload blocks are `cache_control`'d, so the shared context is not re-billed per block; (c) per-unit caching — a resumed hit is 0 tokens / 0 latency; (d) iter-1 week-seam reviews parallelize across non-overlapping seams (same pattern as phase-seam iter-1).
- **The trade is correct:** more total tokens/latency in exchange for *plans that finish*. The status quo is plans that never finish.

## 10. Edge cases

1. **A single week still too big** (e.g., 6 disciplines × doubles in a peak week): caught by §6 (zero-progress → fail loudly) and remediable by lowering `_BLOCK_WEEKS` is moot at 1 — the real lever becomes splitting a week by day-range; flagged as a follow-on if it occurs.
2. **Phase shorter than `_BLOCK_WEEKS`** (e.g., a 1-week taper with `_BLOCK_WEEKS=2`): block clamps to the phase's actual weeks.
3. **T3 cross-phase carryover:** carryover (non-synthesized) phases contribute their existing sessions as `prior_block_sessions` at the first synthesized block; week-seams are only reviewed where ≥1 side was synthesized this call (mirrors the existing phase-seam `pairs_to_review` rule).
4. **First block of the plan** (`u=0`, `start_phase`): `prev_accepted_output_hash=None` (collapses to '' in the key); `prior_block_sessions=[]` — `render_user_prompt` already handles the empty-prior case.
5. **Re-synthesis exhausts the per-seam cap:** emit `seam_unresolved` observation (existing phase-seam behavior, reused).

## 11. Implementation slicing (exceeds the 5-file ceiling → 3 slices)

- **Slice 1 — decomposition + threading (fixes convergence).** `per_phase.py` (block synthesizer + `week_range` + per-block ceiling/tokens), `plan_create.py` (per-`(phase,week)` loop + per-block chain), `hashing.py` (`compute_block_cache_key`), `Layer4_Spec.md` §5.2/§9.2 amendments, tests. Threading is the generalized `prior_block_sessions` arg in `render_user_prompt`.
- **Slice 2 — progress backstop.** `routes/plan_create.py` (`_advance_plan_generation` start-of-pass progress check + `_STALL_PASS_LIMIT`), `init_db.py` (2 columns), `Layer4_Spec.md` §11 note, tests. *(Slices 1+2 together close the incident.)*
- **Slice 3 — week-seam stitcher (Trigger #1 prompt).** NEW `prompts/Layer4_WeekSeamReviewer_v1.md`, `seam_review.py` generalization (or a thin week-seam module), `plan_create.py` week-seam loop, `hashing.py` (`compute_week_seam_review_cache_key`), `cache.py` (`_WEEK_SEAM_CACHE_PHASE_IDX_BASE`), `Layer4_Spec.md` §6 amendment, tests.

Slice 3's prompt body is itself a Trigger #1 stop-and-ask: it gets its own design/ratification pass (calibration anchors) before writing.

## 12. Open items

- **D-77 ratification** — new cross-layer D-row (Trigger #3); needs Andy's sign-off + a backlog entry.
- **`_BLOCK_WEEKS` default** — locked at 1 per the gate; revisit after the §5.0 real-LLM walk measures per-block latency (if blocks are far under budget, batching to 2 halves the call count).
- **Week-seam reviewer calibration** — the new prompt's anchors (§5.2) are the load-bearing Trigger #1 decision; drafted + ratified in Slice 3.
- **Cascade-invalidation containment** (§7 watch item) — only act on it if the §5.0 walk shows re-prompt churn.
- **Cross-cutting:** the same engine powers `plan_refresh` T3 cross-phase, so this also hardens T3; confirm in the refresh-surface design (the parked detour) that the Tier-3 "regenerate-or-generate-without-passing-plan-end" semantics compose with per-week blocks.

## 13. Test scenarios (forward-pointers)

1. A synthetic N-week, M-discipline plan generates the correct block count + each block ≤ `_MAX_SESSIONS_PER_BLOCK`.
2. Per-block cache chain: changing week `k`'s inputs invalidates `k+1..end` only; weeks `<k` hit.
3. Resumed pass: a pass cut after caching blocks `0..j` replays them at zero tokens and advances from `j+1`.
4. Progress backstop: a stubbed always-timeout block trips `_STALL_PASS_LIMIT` and marks `failed` with the diagnostic (not an infinite loop); a plan that advances ≥1 block/pass never trips it.
5. Week-seam reviewer: an injected week-over-week discontinuity (unjustified volume cliff mid-Base) → `flagged_major` + `re_prompt`; a planned recovery week → `approved`/`flagged_minor` (NOT flagged as a phase-style cliff).
6. T3 cross-phase: carryover-only week-seams are not re-reviewed; threading pulls carryover sessions as `prior_block_sessions`.

## 14. Gut check

**Risks / what might be missing / best argument against:**
- **Call-count blow-up is the real cost.** 4× calls is acceptable given caching + the alternative (never finishing), but if per-block latency is low we're over-decomposing; the `_BLOCK_WEEKS` knob + the §5.0 measurement are the release valve.
- **Coherence is the thing to actually verify, not assume.** Threading + skeleton *should* hold a phase together, and the week-seam stitcher is the safety net — but the proof is the real-LLM walk, not the unit tests. If the walk shows weeks that don't blend even with the stitcher, the seam to cut may be wrong (e.g., 2-week blocks with overlap, or day-range splits) — that's a design redo, not a tuning knob.
- **Cascade-invalidation at fine grain** could, worst case, make a late flagged week-seam rebuild a lot of downstream blocks — re-introducing a (smaller) convergence cost. Bounded by iter cap 2 + targeted re-prompt; watched in §5.0.
- **Best argument against the whole approach:** if the per-phase call were merely *occasionally* over budget, a cheaper fix (drop extended thinking on the synthesizer, or raise the per-phase retry efficiency) might suffice without decomposition. Rejected because the 300s ceiling is immovable AND complex plans are the stated norm — any single-call-per-phase design is structurally guaranteed to wall for some athlete, so the unit must shrink. Decomposition is the only fix that scales with complexity instead of fighting it.
