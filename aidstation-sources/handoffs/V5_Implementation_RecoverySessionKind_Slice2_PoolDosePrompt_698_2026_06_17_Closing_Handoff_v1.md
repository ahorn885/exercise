# #698 Track 1 — recovery session kind Slice 2 (pool + dose + prompt) — Closing Handoff

**Session:** Continued the #698 cardio/recovery-catalog arc ("check it out and let's work"). Picked up the predecessor handoff's designated Slice-2 programming-entry and shipped Slice 2 — the LLM-facing slice that wires the ratified `recovery` session kind into the per-phase synthesis prompt + tool schema.
**Date:** 2026-06-17
**Predecessor handoff:** `V5_Implementation_RecoverySessionKind_DesignAndSlice1_698_2026_06_17_Closing_Handoff_v1.md`
**Branch:** `claude/recovery-session-kind-design-qaikq0` (harness-pinned; deleted on squash-merge, recreated on next push)
**PR:** [#718](https://github.com/ahorn885/exercise/pull/718) **MERGED** (auto-merge SQUASH; required checks green).

---

## 1. What shipped (#718 — Slice 2)
Built per the ratified design `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md` §13a. **No DDL** (recovery reads existing 0B rows). 3 substantive code files + 3 test files.

- **`layer4/session_grid.py`** — `_RECOVERY_SESSIONS_PER_WEEK = {Base:3,Build:3,Peak:2,Taper:1}` + `_RECOVERY_SESSION_MINUTES = 18` (D2 LOCKED) + `RecoveryAllocation` dataclass + `compute_recovery_dose(phase, high_load)`. Allocated **off** the training ceiling — a standalone function, NOT in `discipline_allocations`, never through `apply_session_ceiling`/`cardio_total`/intensity (design §2 "doesn't interfere" guarantee, mechanically).
- **`layer4/per_phase.py`** —
  - `_RECOVERY_POOL_EXERCISE_TYPES = {mobility, flexibility / stretching, recovery / soft tissue, breathwork}` + `_is_recovery_pool_type` (case-insensitive, mirrors `_is_strength_pool_type`).
  - `compute_recovery_pool_ids(...)` (the EX-id enum bounding `recovery_exercises[*].exercise_id`) + `_format_recovery_exercise_pool(...)` (rendered flat menu — recovery is not discipline/locale-routed, so no per-discipline ranking or core/accessory split; cap `_RECOVERY_POOL_CAP=12`; 2D-excluded dropped). Both filter the SAME `l2c.exercises_resolved` as the strength pool (#704 infra reuse).
  - `_format_recovery_programming(phase_structure, phase_name, week_range)` — per-week dose block + load-adaptive full-rest directive (D4). Returns `[]` for any phase NOT in `_RECOVERY_SESSIONS_PER_WEEK` (unknown phase → no block, matches today). A deload-zeroed week of a KNOWN recovery phase still renders an explicit full-rest line (Rule #15 `print`).
  - `# Recovery programming` SYSTEM_PROMPT section (off the daily cap; `recovery_exercises` from the pool only; full-rest bias under high load).
  - Session schema: `kind` enum += `recovery`; `session_index_in_day` schema `maximum` 1→2; new enum-bound `recovery_exercises` block; `_session_schema` + `build_record_phase_sessions_tool` gain a `recovery_pool_ids` param; `synthesize_phase` computes `compute_recovery_pool_ids(...)` and passes it; `render_user_prompt` renders the dose block (after the grid) + the recovery pool (after the strength pool, only when a dose is in play).
- **`layer4/hashing.py`** — `LAYER4_PROMPT_REVISION "7"→"8"` (prompt + schema change → cache invalidation).
- **Tests** — `tests/test_layer4_session_grid.py` (dose per phase, deload trim, unknown-phase zero, off-the-grid "doesn't interfere" assertion), `tests/test_layer4_strength_pool.py` (recovery pool filter/render/dedup/cap/2D-exclusion + programming block + Peak directive + unknown-phase suppression + prompt section), `tests/test_layer4_plan_create.py` (1-line: kind enum now includes `recovery`). **Full suite 2614 passed / 30 skipped.**

## 2. Interpretation call — `high_load` semantics (flagged to Andy on the PR + chat)
The design left the exact `high_load` arithmetic loose (the dose integers are explicit "tuning knobs"). The LOCKED base table **already bakes in** the phase-level Peak/Taper freshness trim (`{Peak:2, Taper:1}`). Applying a Peak-phase trim on top would double-trim Peak→1 every week and contradict the locked `{Peak:2}`. **Decision: `high_load` = the per-week *deload* bias only (`periodization.is_deload_week_for`), trimming one session toward full rest (floor 0).** Result: Base/Build 3→2 on deload, Peak 2→1, Taper 1→0. Matches §5 + §11. The broader D4 *prompt directive* ("prefer full rest under high load") still fires on `phase=="Peak"` OR any deload week. **If Andy wants different high-load semantics it's a one-line table/condition tweak — surfaced, not silently chosen.** (Design §13a updated with this note.)

## 3. NEXT — Slice 3 (validator + render); mechanically spec'd in design §8/§9 + §13a
- **`layer4/validator.py`:** recovery handling — **exclude** recovery from `_rule_volume_band`, `_rule_acwr`, `_rule_rest_spacing`, `_rule_strength_sessions_per_phase`, discipline-excluded / skill-gate / sport-locale / indoor-only (recovery has no discipline; treat like rest but with a duration). **Amend `_rule_two_per_day`** to the training-only cap + recovery exemption (mirror `payload._check_two_per_day` from Slice 1). **New recovery-pool-membership rule** (Rule-6a analog): every `recovery_exercises[*].exercise_id` ∈ `compute_recovery_pool_ids(...)` (blocker; the enum bound makes it near-impossible but the validator backstops it).
- **`layer4/race_week_brief.py:235`** (verify line) — taper-override `kind` enum += `"recovery"`.
- **`templates/plan_create/view.html`** (~line 110) — `{% elif sess.kind == 'recovery' %}` branch: "Recovery — {{ duration_min }} min" + session_notes, light/subordinate card, easy/rest chip, no cardio/strength rendering.
- Tests + full suite. (No cache bump — Slice 3 is validator/render only, post-synthesis.)

**Then Track 2** (#698 cardio drills "consider these" pool + Technical/Skill cull — its own design; evidence: swimming-heavy, Base-emphasized).

## 4. Watch-outs
- **Branch churn:** the squash-merge deleted `claude/recovery-session-kind-design-qaikq0`; this session already `git reset --hard origin/main` after the merge to write bookkeeping. Next slice: `git fetch origin main` + reset/rebase, confirm `git status` shows ONLY the slice's files before pushing.
- **`single_session.py` / `plan_refresh.py` stay `["cardio","strength"]`** (recovery not emitted there in v1 — D5). A refresh that drops a recovery session can't re-emit it until v2 — acceptable (non-load-bearing); design §3 flag.
- **Two `0012_*` migrations on main** (`0012_retire_spin_stationary_bike.sql` #692 + `0012_add_strength_exercises_lowerbody.sql` concurrent) — flagged in the predecessor handoff; verify the layer0 apply-ledger handles the numbering (not this arc's scope).

## 5. Verification
- Full Python suite **2614 passed / 30 skipped** (`/tmp/venv`). No DDL/migration. Cache bumped (revision 8) — cached plans regenerate with recovery on next plan-gen. No live plan-gen run this session (Neon egress blocked from the container; Slice 2 is deterministic-render + schema, verified by unit tests).

## 6. Files
**Substantive (shipped #718):** `layer4/session_grid.py`, `layer4/per_phase.py`, `layer4/hashing.py`, `tests/test_layer4_session_grid.py`, `tests/test_layer4_strength_pool.py`, `tests/test_layer4_plan_create.py`. **Bookkeeping:** `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md` (§13a status flip + high_load note), `CURRENT_STATE.md`, this handoff, #698 comment.

## 7. Read order for next session (Rule #13)
`CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then the ratified design `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md` §8/§9/§13a and build **Slice 3**.
**STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify (Andy-action).

---

**End of handoff.**
