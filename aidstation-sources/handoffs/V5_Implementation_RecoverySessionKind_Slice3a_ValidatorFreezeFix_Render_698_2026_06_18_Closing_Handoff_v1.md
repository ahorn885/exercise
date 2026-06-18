# #698 Track 1 — recovery session kind: Slice 3a (validator freeze fix + plan-view render) — Closing Handoff

**Session:** Implementation. Built the ratified design §8/§9 **Slice 3a — THE FREEZE FIX** (the tier-2 go-live blocker that un-freezes shipped Slice-2 behavior). Code + tests; no design decisions owed except the one I flagged + corrected (race_week_brief deferral, below).
**Date:** 2026-06-18
**Predecessor handoff:** `V5_Implementation_RecoverySessionKind_DesignV2DeterministicPlacement_698_2026_06_18_Closing_Handoff_v1.md`
**Branch/PR:** branch `claude/nifty-bardeen-czyqlj` (harness-pinned; kept per the session's explicit branch instruction). Code commit + bookkeeping commit; PR pending.

---

## 1. What shipped (Slice 3a — validator + render, 3 substantive files)

**`layer4/validator.py` — THE FREEZE FIX + recovery handling (design §8):**
- **`_rule_two_per_day` rewritten** — counted **all** sessions, so a structurally-valid `2-training + 1-recovery` day tripped `two_per_day_max_exceeded`, and a `strength + recovery` day misfired `two_per_day_no_cardio`. Now splits `training = kind∈{cardio,strength}` vs `recovery`: caps `len(training) > 2` + `len(recovery) > 1` (new `two_per_day_recovery_exceeded` blocker), and runs `double_strength` / `double_hard` / `no_cardio` over the **training pair only**. Mirrors the shipped pydantic `_check_two_per_day` (payload.py).
- **ACWR exclusion** — `_session_volume_hours` now returns `0.0` for `kind=="recovery"` (was only `rest`); recovery ≈ zero training load. Both call sites (volume_band, acwr) are correct: volume_band already drops recovery via `discipline_id is None`, acwr keys off the helper.
- **schedule-violation** — `_rule_schedule_violation` now skips `kind in ("rest","recovery")`.
- **Already-excluded (verified, no code change):** `_rule_volume_band` / `_rule_rest_spacing` (both filter `discipline_id is None`), `_rule_discipline_excluded` / `_rule_indoor_only_violation` (`discipline_id is None`), `_rule_skill_capability_gate` (`kind != cardio`), `_rule_sport_locale_incompatible` + `_rule_strength_frequency_band` (`kind !=/== strength`). Recovery always has `discipline_id is None` (payload invariant), so these drop it for free.
- **KEPT recovery in `_rule_daily_window_fit`** (no kind filter — recovery's `duration_min` must still fit the day's window). Per §8 / Watch-out §4.
- **New `_rule_recovery_pool_membership`** (Rule 6a-recovery analog) — every `recovery_exercises[*].exercise_id` must be in `compute_recovery_pool_ids(ctx.layer2c_payloads, ctx.layer2d_payload)`; **blocker**. Registered in `_ALL_RULES` (22→23 rules). **Lazy-imports** `compute_recovery_pool_ids` inside the fn (per_phase imports validator at module top → a top-level import would cycle; precedent: `plan_refresh`→`plan_create`). **Skips when `ctx.layer2c_payloads` is empty OR the pool resolves empty** — the empty-pool case is owned by suppress-on-empty (Slice 3b); blocking there would re-freeze the path 3a frees.

**`templates/plan_create/view.html` + `static/style.css` — render (design §9):**
- Name-line `{% elif sess.kind == 'recovery' %}Recovery — {{ duration_min }} min` branch (before the generic else).
- Subordinate card: `<div class="card card-pad sess-card{% if recovery %} sess-recovery{% endif %}">` + a `.sess-recovery` CSS rule (left-border + muted, class-based — no inline style).
- Structured `recovery_exercises` block (exercise_name / prescription / instructions) reusing `sess-exercises`/`sess-exercise`.

**No cache bump** — `LAYER4_PROMPT_REVISION` stays `"8"` (validator/render only; `hashing.py` untouched). Full suite **2626 passed / 30 skipped** (+12: 9 validator, 3 render).

## 2. DEVIATION from design §13a — race_week_brief recovery DEFERRED (flagged + corrected the design)

The design §13a Slice 3a listed `race_week_brief.py` "taper-override `kind` enum += recovery". **It's unsafe as written and I deferred it** (design §13a now records this):
- **Enum-only is unsafe:** a `kind=="recovery"` override fails `PlanSession` construction — the recovery invariant needs a `recovery_exercises` field, which the override schema + `_build_session_override` don't thread.
- **The minimal-safe completion (field + builder) ships DEAD surface:** the race-week-brief prompt body never mentions recovery, and the prior-session rendering (`race_week_brief.py:~1157`) never surfaces a prior recovery session's `recovery_exercises` ids — so the LLM can neither be instructed to emit recovery nor echo prior ids. The field is unreachable on the normal path. (It also marginally widens a **pre-existing** merged-payload contiguity-500: `_build_layer4_payload_for_validation` (~`:1780`) runs `_check_two_per_day` **outside** the per-override try/except (ends `~:1763`) — reachable today via a single index-1 override; the index `1→2` bump would add one more triggering value.)
- **Deferring is safe:** prior Taper recovery sessions **pass through unchanged** (pass-throughs aren't rebuilt via the override schema). Nothing breaks.
- I built the safe version, ran the review, then **reverted it** (`git checkout HEAD -- layer4/race_week_brief.py`). Per CLAUDE.md "simplicity first / nothing speculative" + "first principle wins over a detailed rule — flag the conflict".

**Functional race-week recovery is its own slice** = a **Trigger #1 prompt change** (surface a recovery instruction in `_SYSTEM_PROMPT`/`_render_user_prompt` + render prior `recovery_exercises` into the prior-session lines) + enum-bind the field (thread `recovery_pool_ids` through `build_record_race_week_brief_tool`, mirroring `feasible_pool_ids`). **Andy's call on scope/timing — flagged in chat + filed as a #698 sub-item.**

## 3. NEXT — Slice 3b (deterministic placement D6), spec'd in design §6a/§8/§13a
- **`session_grid.py`** — `compute_recovery_placement(...)` (§6a; mirror `compute_recovery_dose`): from the **long-session day** + **enabled days** + capacity-hours classified against the phase `phase_load_bands [low,high]` (+ Peak/deload). `light`=≤low (unconstrained), `moderate`=in-band (anchor day-after-long, off the long day), `extreme`=≥high OR Peak/deload (off long-day + pre-key day). Empty pool / zero dose → `[]`; clamp when candidate days < dose (+ Rule #15 log).
- **`per_phase.py`** — factor/thread the long-session-day derivation so placement and `=== Schedule ===` agree; `_format_recovery_programming` renders placed **dates** (not a count); **suppress-on-empty** (no recovery instruction when the pool is empty → kills the unfillable-payload retry).
- **`validator.py`** — D6 placement-match rule (week's `kind=='recovery'` dates **must equal** `compute_recovery_placement(...)`; blocker; guard on grid-in-context, like the other grid rules).
- **`hashing.py`** — `LAYER4_PROMPT_REVISION "8"→"9"` (recovery block text changes count→dates). 3 substantive files.
- **Then** the deferred race-week-brief recovery slice (§2 above, Trigger #1), **then Track 2** (#698 cardio drills pool + Technical/Skill cull — separate design).

## 4. Watch-outs
- **D6 placement vs window-fit (carried):** an assigned recovery date could land on a too-short day — caught by `_rule_daily_window_fit` (recovery stays in it). If placement-match ever fights window-fit live, add a window-minutes filter to `compute_recovery_placement` candidates (one-line, deferred; Rule #15 log surfaces it). Design §14.
- **`_rule_recovery_pool_membership` empty-pool skip is deliberate** — don't "tighten" it to always-block; that re-freezes the very edge 3b's suppress-on-empty fixes properly.
- **Pre-existing (NOT 3a's job):** `race_week_brief._build_layer4_payload_for_validation` constructs the merged payload outside the per-override try/except, so a `_check_two_per_day` ValueError 500s instead of becoming a `schema_violation` retry. Reachable today via a non-contiguous single override. Worth a separate hardening pass; do NOT fold into 3b.
- **Branch:** harness-pinned `claude/nifty-bardeen-czyqlj`; kept per the session's explicit "develop on this branch" instruction (overrides the usual rename-to-scope convention). Next slice: `git fetch origin main` + fresh branch.
- **`single_session.py` / `plan_refresh.py` stay `["cardio","strength"]`** (recovery not emitted there — D5). Unchanged.

## 5. Verification
- Full suite **2626 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`). +12 new tests: freeze regressions (2c+1rec ✓, c+s+rec ✓, strength+rec no false no_cardio ✓, 3-training ✗, 2-strength ✗, 2-recovery ✗), ACWR-exclusion (`_session_volume_hours` recovery→0), pool-membership (in-pool ✓ / out-of-pool ✗ / no-2C skip / empty-pool skip), render (subordinate card + movements).
- The **freeze anchor is gone:** `grep -n "len(sessions) > 2" layer4/validator.py` → **no hit** (replaced by the training-split). The previous handoff named this as the un-fix marker.
- Review pass (3 finder agents): validator mirror confirmed faithful (exhaustive enumeration, 0 accept/reject divergences vs pydantic), lazy import sound, template Jinja balanced + CSS vars present in `tokens.css`. The race_week_brief agent's findings drove the §2 deferral.

## 6. Files
**Substantive (this session):** `layer4/validator.py`, `templates/plan_create/view.html`, `static/style.css` (+ tests `tests/test_layer4_validator.py`, `tests/test_redesign_view_plan_render.py`). **Reverted (built then pulled):** `layer4/race_week_brief.py` (back to HEAD — the §2 deferral). **Bookkeeping:** `CURRENT_STATE.md` (new Last-shipped), design v2 §13a (3a SHIPPED + race_week_brief deferral correction), this handoff, #698 comment + the race-week-brief sub-item.
- **Anchor checks for the next Rule #9 sweep:**
  - `grep -n "two_per_day_recovery_exceeded" layer4/validator.py` → hits (the freeze-fix marker).
  - `grep -n "_rule_recovery_pool_membership" layer4/validator.py` → def + `_ALL_RULES` registration.
  - `grep -n "kind in (\"rest\", \"recovery\")" layer4/validator.py` → 2 hits (`_session_volume_hours` + `_rule_schedule_violation`).
  - `grep -n "sess-recovery" templates/plan_create/view.html static/style.css` → render branch + CSS.
  - `grep -n "len(sessions) > 2" layer4/validator.py` → **no hit** (freeze fixed).
  - `grep -n "LAYER4_PROMPT_REVISION = " layer4/hashing.py` → still `"8"` (no 3a cache bump; 3b bumps to "9").
  - design v2 §13a → "**Slice 3a — validator alignment + render (THE FREEZE FIX): ✅ SHIPPED**" + the `race_week_brief.py` recovery DEFERRED bullet.

## 7. Read order for next session (Rule #13)
`CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then the ratified design `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v2.md` §6a/§8/§13a and build **Slice 3b (deterministic placement)**.
**STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify (Andy-action).

---

**End of handoff.**
