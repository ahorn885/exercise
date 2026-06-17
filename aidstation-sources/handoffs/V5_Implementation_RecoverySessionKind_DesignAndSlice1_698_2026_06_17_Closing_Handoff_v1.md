# #698 Cardio/Recovery Catalog Arc — strength-pool filter + recovery-session design + Slice 1 — Closing Handoff

**Session:** Long multi-step arc continuing the #692/#698 cardio-catalog thread ("check it out and keep working"). Shipped the strength-pool type leak fix, expanded the allowlist, ran cited sport-science research, ratified a design for a new `recovery` session kind, and built Slice 1 (schema).
**Date:** 2026-06-17
**Predecessor handoff:** `V5_Implementation_IndoorBikeFold_692_2026_06_17_Closing_Handoff_v1.md`
**Branch:** `claude/admiring-cori-hjdqaq`
**PRs (all auto-merge SQUASH):** [#704](https://github.com/ahorn885/exercise/pull/704) MERGED · [#705](https://github.com/ahorn885/exercise/pull/705) MERGED · [#706](https://github.com/ahorn885/exercise/pull/706) MERGED · [#708](https://github.com/ahorn885/exercise/pull/708) MERGED · [#711](https://github.com/ahorn885/exercise/pull/711) (Slice 1) auto-merge.

---

## 1. What shipped
1. **#704 — #698 Finding 2 fix.** Type-filtered both strength surfaces (`compute_feasible_pool_ids` enum + `_format_strength_exercise_pool`) via `_STRENGTH_POOL_EXERCISE_TYPES` + `_is_strength_pool_type` (case-insensitive; Rule #15 log) so cardio/skill `0B` rows can't be mis-prescribed as strength lifts.
2. **#706 — allowlist expansion + research doc.** Added `Agility`, `Activation / Primer`, `Balance / Proprioception` to the strength allowlist (Andy-ratified: resistance + athletic-development). Added `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md` (5-agent cited synthesis).
3. **#708 — RATIFIED design** `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md` (the spec the remaining build follows; §13a has the slice plan).
4. **#711 — Slice 1 (schema).** `layer4/payload.py`: `kind += "recovery"`; `RecoveryExercise` model (structured, D1) + `recovery_exercises` field; `session_index_in_day` max 1→2; recovery invariants; `_check_two_per_day` now caps **training** sessions only (≤2) + ≤1 recovery (exempt/additive). +9 tests; full suite **2598 passed / 30 skipped**.

## 2. Ratified decisions (Andy 2026-06-17) — locked in the design doc
- New `recovery` session **kind** (not a discipline), with **independent allocation that does not interfere with cardio/strength** (allocated *after/outside* the §5.1.1 session ceiling + saturation cap).
- **Exempt from the ≤2/day training cap:** ≤2 training (cardio/strength) **+ ≤1 recovery** ("2 cardio + 1 recovery OK; 1 cardio + 1 strength + 1 recovery OK").
- **D1 = structured `recovery_exercises[]` block** (EX-id-bound to a recovery pool, parallel to strength — NOT free-text).
- **D2 = dose `{Base:2, Build:2, Peak:2, Taper:1}` × ~15 min** — the evidence-supported frequency (ACSM ≥2–3 days/wk) at the small per-session volume the ROM-plateau data demands; no endurance-specific count exists in the literature → calibrated/tunable.
- **D3 = ≤2 training + ≤1 recovery/day**, `session_index_in_day` max→2.
- **D4 = bias rest days to full rest when `phase=="Peak"` OR deload/taper week** (active recovery allowed otherwise; adaptation-neutral per the evidence).
- **D5 = `per_phase` (plan-create) + `race_week_brief` now; `plan_refresh`/`single_session` later.**

## 3. Evidence highlights (from the research doc — drives the design)
- Recovery/mobility benefit **plateaus at small doses** (~10 min/wk per muscle group; breathwork ~5 min) and is **not an injury lever** (strength is) → keep recovery small/capped.
- **Active vs passive rest is adaptation-neutral** → load-adaptive rest days (full-rest floor, active-recovery variant).
- Cardio drills **transfer strongly in swimming** (drag-limited) but are **weak/equivocal for running/cycling economy** → Track 2's drills pool should be discipline-weighted (swimming-heavy), Base-emphasized.

## 4. NEXT — finish Track 1 (mechanically spec'd in design §13a)
**Slice 2 — pool + dose + prompt (the LLM-facing slice; cache bump):**
- `layer4/per_phase.py`: `_RECOVERY_POOL_EXERCISE_TYPES = {mobility, flexibility / stretching, recovery / soft tissue, breathwork}` (lowercased, case-insensitive — mirror `_STRENGTH_POOL_EXERCISE_TYPES`); `compute_recovery_pool_ids(...)` (the EX-id enum) + `_format_recovery_exercise_pool(...)` (rendered pool) — both filter the SAME `l2c.exercises_resolved`, 2D-excluded dropped; a `# Recovery programming` SYSTEM_PROMPT section (recovery is off the daily cap; placed on/after hard or rest-adjacent days; full-rest bias under high load); a rendered recovery dose block; the session schema `kind` enum += `"recovery"` and `session_index_in_day` schema `maximum` 1→2; the `recovery_exercises` property bound to the pool enum.
- `layer4/session_grid.py`: `_RECOVERY_SESSIONS_PER_WEEK = {"Base":2,"Build":2,"Peak":2,"Taper":1}` + `_RECOVERY_SESSION_MINUTES = 15` + `compute_recovery_dose(phase_name, high_load: bool)` — allocated **off** the ceiling (NOT in `discipline_allocations`, NOT in `apply_session_ceiling`/`cardio_total`/intensity).
- `layer4/hashing.py`: `LAYER4_PROMPT_REVISION "7"→"8"`.
- Tests: pool filter (recovery types in, others out), dose per phase, ceiling-unaffected-by-recovery assertion.

**Slice 3 — validator + render:**
- `layer4/validator.py`: recovery handling (exclude from volume-band/ACWR/rest-spacing/strength-count/discipline-gate rules — treat like rest but with duration); **amend `_rule_two_per_day`** to the training-only cap + recovery exemption (mirror `payload._check_two_per_day`); **new recovery-pool-membership rule** (Rule-6a analog — every `recovery_exercises[*].exercise_id` ∈ `compute_recovery_pool_ids`).
- `layer4/race_week_brief.py:235`: enum += `"recovery"`.
- `templates/plan_create/view.html` (~110): `{% elif sess.kind == 'recovery' %}` branch.
- Tests + full suite.

**Then Track 2** (#698 cardio drills "consider these" pool + Technical/Skill cull — its own design; evidence: swimming-heavy, Base-emphasized).

## 5. Watch-outs for next session
- **Branch churn:** every squash-merge deletes `claude/admiring-cori-hjdqaq`; the next push recreates it. **Main advanced underneath this branch mid-session** (a concurrent `0012_add_strength_exercises_lowerbody.sql` + the #679 review sheet landed). Before pushing a new slice, `git fetch origin main` and `git reset --soft origin/main` (or rebase) and confirm `git status` shows ONLY your slice's files — twice this session a stale base would have reverted others' work (once caught via `git checkout origin/main -- <files>`).
- **Note:** there appear to be two `0012_*` migrations on main now (`0012_retire_spin_stationary_bike.sql` from #692 + `0012_add_strength_exercises_lowerbody.sql` from concurrent work) — verify the layer0 apply-ledger/gate handles the numbering; not this arc's scope but flag it.
- `single_session.py`/`plan_refresh.py` stay `["cardio","strength"]` (recovery not emitted there in v1).

## 6. Verification
- Full Python suite **2598 passed / 30 skipped** (`/tmp/venv`). No DDL/migration in this arc (recovery reads existing 0B rows). Slice 1 has no prompt change → no cache bump yet (that's Slice 2).

## 7. Files
**Substantive (shipped):** `layer4/per_phase.py` (#704/#706), `tests/test_layer4_strength_pool.py`, `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md`, `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md`, `layer4/payload.py` + `tests/test_layer4_payload.py` + `tests/test_layer4_plan_create.py` (Slice 1). **Bookkeeping:** `CURRENT_STATE.md`, this handoff, #698 comments.

## 8. Read order for next session (Rule #13): `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then the ratified design `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md` §13a and build Slice 2.
**STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify (Andy-action).

---

**End of handoff.**
