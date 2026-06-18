# #698 Track 1 — recovery session kind: design v2 (D6 deterministic placement) — Closing Handoff

**Session:** Design-only. Andy ratified **"placement deterministic, exercise selection LLM"** for recovery sessions (chat: "yep" to the proposed model). Revised the recovery-session design to **v2** and reshaped the remaining build (Slice 3 → 3a + 3b). No code — this is a determinism/architecture decision spec'd for the next build session.
**Date:** 2026-06-18 (decision ratified 2026-06-17; bookkeeping/PR landed 2026-06-18)
**Predecessor handoff:** `V5_Implementation_RecoverySessionKind_Slice2_PoolDosePrompt_698_2026_06_17_Closing_Handoff_v1.md`
**Branches/PRs:**
- **#722** [MERGED, squash] — the design v2 doc + v1 archive + CURRENT_STATE NEXT-pointer. Branch `claude/recovery-session-kind-design-qaikq0` (had a merge-conflict against main from a duplicate bookkeeping commit + main advancing #720/#721; resolved by taking main's CURRENT_STATE structure and re-applying only the NEXT-pointer edit — diff landed clean: v2 added, v1 renamed→archive, CURRENT_STATE +1/−1).
- **This bookkeeping PR** — CURRENT_STATE "Last shipped" promotion + this handoff + #698 comment. Branch `claude/recovery-v2-bookkeeping-qaikq0`.

---

## 1. What shipped (#722 — design v2, docs-only)
`designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v2.md` (v1 → `archive/superseded-specs/` per Rule #12). The **D6** decision and its consequences:

- **§6a (NEW) — `compute_recovery_placement` (deterministic placement).** The grid computes the **exact recovery dates** each week and renders them to the prompt as a hard constraint; the validator enforces them. The LLM keeps **exercise selection** (picks `recovery_exercises` from the rendered pool, so it can target what was worked / honor the 2D wrist context).
  - **Determinism limit (load-bearing):** per-day *realized* training volume isn't known before synthesis (day layout is the LLM's job). So placement keys off the signals that *are* deterministic at render time — the **long-session day** (longest enabled window, already derived in `_format_schedule`), the **enabled days**, the week's **capacity-hours** vs the phase band, and **Peak/deload** flags. Andy's per-day "[X,Y]→today/after; >Y→not today" rule is recast onto the **week level + long-day anchor** — the faithful projection, not a literal per-day test (a literal test needs post-synthesis injection, which trades away LLM selection → rejected).
  - **X/Y = the existing per-phase `phase_load_bands` `[low, high]`** (Andy ratified: derive from bands, NOT fixed hours). `light` = ≤ band-low (placement unconstrained); `moderate` = within band (anchor day-after-long, spread off the long day); `extreme` = ≥ band-high OR Peak OR deload (keep recovery off the long day + the pre-key day; the count trim stays the dose's job — no double-trim).
- **§6/§7 reshaped** — prompt renders placed *dates* (not just a count); the load-adaptive rest policy is now *enacted* by placement, with the prose as belt-and-suspenders.
- **§8 validator** — calls out the **live freeze** (see §2) and specs the fixes: amended `_rule_two_per_day`, recovery exclusions from the discipline-keyed rules, recovery-pool-membership rule, and the D6 placement-match rule.
- **§13a — Slice 3 split** into **3a** (validator freeze fix + render + race_week_brief enum — ships first, un-freezes shipped behavior) and **3b** (deterministic placement + suppress-on-empty + `LAYER4_PROMPT_REVISION "8"→"9"`).
- **suppress-on-empty-pool (D6)** — when `compute_recovery_pool_ids(...)` resolves empty, placement returns `[]` and no recovery instruction renders → the LLM is never handed an unfillable `recovery_exercises[]` (kills that wasted correction-loop retry).

## 2. THE FREEZE — live blocker on shipped Slice 2 (drives Slice 3a sequencing)
`layer4/validator.py:609` `_rule_two_per_day` still counts **all** sessions, so a structurally-valid `2-training + 1-recovery` day (which the Slice-2 prompt now induces) trips `two_per_day_max_exceeded`, and `two_per_day_no_cardio`/`double_strength` misfire when recovery is in the mix. The pydantic `_check_two_per_day` (payload.py, Slice 1) is already correct; the validator's independent §5.4 re-check was never amended. **Any plan that places recovery currently can't clear the correction loop.** Slice 3a fixes this first (tier-2 go-live blocker per the 4-tier order). The fix is a mechanical mirror of the shipped pydantic logic — spec'd verbatim in design §8.

## 3. NEXT — Slice 3a (the freeze fix), then 3b; spec'd in design §8/§9/§13a
**Slice 3a (build first):**
- **`layer4/validator.py`** — amend `_rule_two_per_day` to split `training = kind∈{cardio,strength}` vs `recovery`: cap `len(training)>2` and `len(recovery)>1`; run `double_strength`/`double_hard`/`no_cardio` over `training` only. Exclude recovery from `_rule_volume_band`, `_rule_acwr`, `_rule_rest_spacing`, `_rule_strength_sessions_per_phase`/`_rule_strength_frequency_band`, discipline-excluded/skill-gate/sport-locale/indoor-only/schedule-violation (KEEP recovery in `_rule_daily_window_fit` — duration must still fit). New recovery-pool-membership rule (Rule-6a analog): `recovery_exercises[*].exercise_id ∈ compute_recovery_pool_ids(...)`.
- **`layer4/race_week_brief.py:235`** — taper-override `kind` enum += `"recovery"`.
- **`templates/plan_create/view.html`** (~110) — `{% elif sess.kind == 'recovery' %}` branch: "Recovery — {{ duration_min }} min" + session_notes, light/subordinate card, easy/rest chip.
- Tests + full suite. No cache bump (validator/render only). 3 substantive files.

**Slice 3b (after 3a):** `compute_recovery_placement` in `session_grid.py` (§6a — mirror `compute_recovery_dose`); `per_phase.py` wiring (factor/thread the long-session-day derivation so placement and `=== Schedule ===` agree; `_format_recovery_programming` renders placed dates; suppress-on-empty); validator D6 placement-match rule; `hashing.py` `LAYER4_PROMPT_REVISION "8"→"9"`. 3 substantive files.

**Then Track 2** (#698 cardio drills pool + Technical/Skill cull — separate design).

## 4. Watch-outs
- **D6 placement vs window-fit:** an assigned recovery date could land on a day whose window is too short for ~18 min — caught by `_rule_daily_window_fit` (recovery stays in that rule). If placement-match ever fights window-fit in a live plan, add a window-minutes filter to `compute_recovery_placement` candidates (one-line, deferred until a real case; Rule #15 log will surface it). Documented in design §14.
- **Branch:** `claude/recovery-session-kind-design-qaikq0` was squash-merged (#722) and is effectively closed; this bookkeeping rides `claude/recovery-v2-bookkeeping-qaikq0`. Next slice: `git fetch origin main` + fresh branch; confirm `git status` shows only the slice's files before pushing.
- **`single_session.py` / `plan_refresh.py` stay `["cardio","strength"]`** (recovery not emitted there in v1 — D5). Unchanged by v2.

## 5. Verification
- No code/tests this session (design + bookkeeping only). The design's claimed code anchors were grounded against on-disk reality before writing: `validator.py:609` `_rule_two_per_day` counts all sessions (the freeze); `payload.py` `_check_two_per_day` already split training/recovery (Slice 1); `session_grid.py:218` `compute_recovery_dose`; `per_phase.py` `_format_recovery_programming` (~1413) + `_format_schedule` long-day derivation (~1684).
- #722 merged with required checks green (JS harness, Python suite, Layer 0 gate; Real-LLM smoke skipped). v2 present on main, v1 archived (confirmed via `git ls-tree origin/main`).

## 6. Files
**Substantive (shipped #722):** `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v2.md` (new), `archive/superseded-specs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v1.md` (moved). **Bookkeeping:** `CURRENT_STATE.md` (this session = new "Last shipped" entry, anchor `DESIGN V2 — D6 DETERMINISTIC PLACEMENT`), this handoff, #698 comment.
- **Anchor checks for the next Rule #9 sweep:** design v2 §6a header `## 6a. Deterministic recovery placement (D6`; design v2 §13a `Slice 3a — validator alignment + render (THE FREEZE FIX)`; validator freeze still un-fixed on main → `grep -n "len(sessions) > 2" layer4/validator.py` returns a hit until Slice 3a ships.

## 7. Read order for next session (Rule #13)
`CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then the ratified design `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v2.md` §8/§9/§13a and build **Slice 3a (the freeze fix)**.
**STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify (Andy-action).

---

**End of handoff.**
