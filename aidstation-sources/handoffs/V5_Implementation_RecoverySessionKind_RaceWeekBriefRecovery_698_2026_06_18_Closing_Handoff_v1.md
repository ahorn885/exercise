# #698 Track 1 — recovery session kind: race-week-brief recovery (selection-only) — Closing Handoff

**Session:** Implementation. Built the deferred #698 sub-item (Slice 3b handoff §4 NEXT): wire the `recovery` session kind into the **race-week-brief** synthesizer. Andy ratified the scope at session start (Trigger #1 prompt change). Selection-only — no D6 placement on this path. Code + tests; no validator changes needed.
**Date:** 2026-06-18
**Predecessor handoff:** `V5_Implementation_RecoverySessionKind_Slice3b_DeterministicPlacement_698_2026_06_18_Closing_Handoff_v1.md`
**Branch/PR:** branch `claude/recovery-session-deterministic-placement-8m9mzn`; **PR [#730](https://github.com/ahorn885/exercise/pull/730) MERGED** (auto-merge SQUASH).

---

## 1. What shipped (2 substantive files + tests)

**`layer4/race_week_brief.py` — recovery wired into the brief override path:**
- **`_taper_override_session_schema(feasible_pool_ids=None, recovery_pool_ids=None)`** — `kind` enum gains `"recovery"`; new **`recovery_exercises`** block (exact mirror of `per_phase._session_schema`'s — `exercise_id`/`exercise_name`/`prescription`/`instructions`, `exercise_id` enum-bound to `recovery_pool_ids` when non-empty, free string otherwise); **`session_index_in_day` max `1→2`** so a prior recovery session occupying the 3rd daily slot (≤2 training + ≤1 recovery) can be echoed (mirrors `payload.PlanSession.session_index_in_day` `le=2`).
- **`build_record_race_week_brief_tool(feasible_pool_ids=None, recovery_pool_ids=None)`** — threads `recovery_pool_ids` into the override-item schema.
- **`_build_session_override`** — parses `recovery_exercises` → `[RecoveryExercise(**r)]`, passed to the constructed `PlanSession` (alongside the existing `cardio_blocks`/`strength_exercises` parsing).
- **`_render_user_prompt`** — the prior-session loop now renders a session's `recovery_exercises` (a `    recovery_exercises:` sub-block listing `exercise_id (name): prescription`) so the synthesizer can echo/trim them and only ever picks ids it has already seen.
- **`_SYSTEM_PROMPT`** — new recovery paragraph under `# Taper session modulation`: race-week bias toward **rest**, never introduce novel recovery stimulus; keep a recovery session only when it aids freshness (emit `kind=recovery`, echo/trim prior `recovery_exercises`, pick ids only from those already prescribed), else drop to full rest (`kind=rest`, `intensity_summary=rest`, `rest_reason=planned_recovery`, null `recovery_exercises`).
- **Synthesize call site** — computes `recovery_pool_ids = compute_recovery_pool_ids(layer2c_payloads, layer2d_payload)` and passes it (with `feasible_pool_ids`) to `build_record_race_week_brief_tool`. Import added: `compute_recovery_pool_ids` (per_phase) + `RecoveryExercise` (payload).

**`layer4/hashing.py`:** `LAYER4_PROMPT_REVISION "9"→"10"` (recovery instruction + prior-recovery render + schema `recovery` kind change synthesis output).

Full suite **2647 passed / 30 skipped** (+8: `TestRecoverySlice` in `tests/test_layer4_race_week_brief.py` — kind enum, enum-binding present/absent, pool threading, override parse, prior-session render, system-prompt instruction).

## 2. Key design decision — selection-only, no D6 placement (and why no validator change)
The brief is **Pattern B** (modify prior Taper sessions); it has **no session grid** to place against, so **D6 deterministic placement does not apply here**. The validator's `_rule_recovery_placement_match` is guarded on `phase_structure` + `2A` + `daily_availability_windows` — none of which the brief's `ValidatorContext` carries — so it **stays dormant** on this path (correct; verified by Slice 3b handoff §3 watch-out #4).
- **No validator changes were needed.** The existing **`_rule_recovery_pool_membership`** keys on `ctx.layer2c_payloads`/`layer2d_payload` (both present in the brief ctx) → it **already backstops** the new enum binding (out-of-pool recovery ids blocked; skips on empty pool, no re-freeze). The **Slice-3a `_rule_two_per_day`** fix (training-only cap + recovery exemption) already governs the daily-slot invariant. So the recovery override is enforced end-to-end with zero net validator surface this session.

## 3. Watch-outs
- **Carried, pre-existing (NOT this slice):** `_build_layer4_payload_for_validation` runs `_check_two_per_day` **outside** the per-override try/except (`race_week_brief.py:~1790`) → a non-contiguous single override 500s instead of a `schema_violation` retry. Untouched here; separate hardening pass (also flagged in Slice 3a/3b handoffs).
- **Selection bias is intentional.** The system-prompt instruction biases toward dropping recovery to full rest in race-week (evidence: recovery dose is small, race-week wants freshness). The brief can still keep a light recovery session when the prior plan had one. This is a *softer* contract than plan-create's deterministic placement — by design (the brief has no grid + race-week is the one phase where "just rest" is usually right).
- **Pool render deliberately omitted.** Mirroring the strength path (which enum-binds `feasible_pool_ids` but does **not** render a strength pool), the brief does not render the full recovery pool — it renders the **prior session's** `recovery_exercises` and bounds picks via the enum. The conservative "echo or drop" contract means the LLM carries forward known-valid ids rather than composing new ones, so a rendered pool is unnecessary.

## 4. NEXT
- **Track 2** (#698 cardio drills pool + Technical/Skill cull — **separate design**, likely Trigger #1/#2). The recovery-session arc (Track 1) is now complete: Slice 1 (schema) → Slice 2 (pool+dose+prompt) → Slice 3a (freeze fix + render) → Slice 3b (deterministic placement) → race-week-brief recovery (this session).
- **Other open:** #690/#624/#689 (Trigger #1 prompt); #283 (FIT-decode prod log).
- **STILL OWED (carried, Andy-action — container can't reach Neon / trigger gen):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; **LIVE-VERIFY Slice 3b** (recovery lands on assigned dates + no false `daily_window_fit`/`recovery_placement_mismatch` blocks); **LIVE-VERIFY race-week-brief recovery** (a real race-week brief either keeps a prior recovery session with valid `recovery_exercises` or drops it to full rest — no false `recovery_pool_membership` blocks).

## 5. Verification
- Full suite **2647 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`).
- **Anchor checks for the next Rule #9 sweep:**
  - `grep -n '"cardio", "strength", "rest", "recovery"' layer4/race_week_brief.py` → the override `kind` enum.
  - `grep -n "recovery_pool_ids" layer4/race_week_brief.py` → schema param + tool thread + synthesize-site compute (5 hits).
  - `grep -n "recovery_exercises=recovery_exercises" layer4/race_week_brief.py` → `_build_session_override` passes the parsed block.
  - `grep -n "kind=recovery" layer4/race_week_brief.py` → the `_SYSTEM_PROMPT` recovery instruction.
  - `grep -n "recovery_exercises:" layer4/race_week_brief.py` → the prior-session render sub-block.
  - `grep -n "LAYER4_PROMPT_REVISION = " layer4/hashing.py` → `"10"`.
  - design v2 §13a → the Slice-3a deferred bullet now carries a "**Race-week-brief recovery — ✅ SHIPPED (PR #730)**" sub-bullet.

## 6. Files
**Substantive (this session):** `layer4/race_week_brief.py`, `layer4/hashing.py` (+ tests `tests/test_layer4_race_week_brief.py`). **Bookkeeping:** `CURRENT_STATE.md` (new Last-shipped + Slice 3b demoted to predecessor), design v2 §13a (race-week-brief recovery SHIPPED sub-bullet), this handoff, #698 comment.

## 7. Read order for next session (Rule #13)
`CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then design **Track 2** (#698 cardio drills pool + Technical/Skill cull — separate design; Trigger gate) or pick up an open #690/#624/#689/#283 item.
**STILL OWED (carried):** see §4.

---

**End of handoff.**
