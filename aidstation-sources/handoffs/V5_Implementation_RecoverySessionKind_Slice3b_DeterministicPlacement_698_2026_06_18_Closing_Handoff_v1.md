# #698 Track 1 — recovery session kind: Slice 3b (deterministic placement D6 + suppress-on-empty) — Closing Handoff

**Session:** Implementation. Built the ratified design v2 §6a/§8/§13a **Slice 3b — deterministic recovery PLACEMENT (D6)**: the grid now computes the exact recovery dates per week and renders them as a hard prompt constraint, validator-enforced; the LLM keeps only exercise selection. Code + tests; one mid-build architectural decision ratified by Andy in chat (windows → validator ctx, below).
**Date:** 2026-06-18
**Predecessor handoff:** `V5_Implementation_RecoverySessionKind_Slice3a_ValidatorFreezeFix_Render_698_2026_06_18_Closing_Handoff_v1.md`
**Branch/PR:** branch `claude/recovery-validator-freeze-fix-dr0spu` (harness-pinned; kept per the session's explicit branch instruction — overrides the rename-to-scope convention). PR pending at handoff write.

---

## 1. What shipped (Slice 3b — 5 substantive files)

**`layer4/session_grid.py` — the deterministic placement core (§6a):**
- **`compute_recovery_placement(week_dates, enabled_days, long_session_dow, dose_count, load_band, pool_is_empty) -> list[date]`** — the EXACT recovery dates for one week. `pool_is_empty` or `dose_count==0` → `[]`. Else: enabled dates in the week, drop excluded days per band (`moderate` excludes the long day; `extreme` also excludes the day before it; `light` excludes nothing), order (moderate anchors the day-AFTER-long first, then even spread; else even spread), take `dose_count` clamped to feasible days. **Single source of truth for both the render block and the validator** — both call this same pure fn with the same upstream-derived inputs, so they can't disagree.
- **`classify_recovery_load_band(capacity_hours, phase_band, phase_name, is_deload)`** — `Peak`/deload → `extreme` (D4); else capacity vs the phase total band `[low,high]` (2A `weekly_total_hours_by_phase`): `≤low`→light, in-band→moderate, `≥high`→extreme; no band/capacity→light.
- **`derive_enabled_days` / `derive_long_session_dow`** — shared helpers (handle both dict windows from Layer1 `model_dump()` and `DailyAvailabilityWindow` objects). `_even_spread` uses integer-floor indices (no banker's-rounding collisions).

**`layer4/per_phase.py` — render placed dates + single-source the long day:**
- **`_format_recovery_programming`** rewritten — new signature `(phase_structure, phase_spec, week_range, layer1_payload, layer2a_payload, pool_is_empty)`. Renders **explicit assigned dates** ("Week N: place a recovery session on YYYY-MM-DD, … — these dates are ASSIGNED; do not add, drop, or move them") instead of a count. **Suppress-on-empty** (§6.3): returns `[]` (no block) when `pool_is_empty` — the LLM is never asked to fill an unfillable `recovery_exercises[]`. Clamp + zero-dose weeks render the explicit full-rest line. Rule #15 logs (suppress + clamp).
- Call site in `render_user_prompt` computes `recovery_pool_is_empty = not compute_recovery_pool_ids(...)` and threads it.
- **`_format_daily_windows_schedule`** now derives the long day via `derive_long_session_dow(windows)` (single-sourced with placement, per §6a "so placement and `=== Schedule ===` agree") — behavior-identical (same strict-`>`/earliest-tie logic), just no longer a parallel copy.

**`layer4/validator.py` — D6 placement-match (§8):**
- **`_rule_recovery_placement_match`** (new, registered in `_ALL_RULES` 23→24) — the week's `kind=='recovery'` dates **must equal** `compute_recovery_placement(...)` for that week (blocker on extra/missing/moved). Groups every `(phase, week_in_phase)` present in the payload (a missing recovery day is a failure, so all weeks are checked), recomputes week dates from `payload.phase_structure` (mirrors `_block_date_window`), dose/band/placement from the same fns the render uses. **Lazy-imports** `session_grid` + `per_phase` (both import this module at top → top-level imports cycle; precedent: `_rule_recovery_pool_membership`). Guarded on `phase_structure` + `2A` + `daily_availability_windows` present (no-ops on refresh/single-session paths that don't carry the grid).
- **`daily_windows_from_layer1(layer1_payload)`** (new helper) — rebuilds the typed `DailyAvailabilityWindow` tuple from Layer1 `model_dump()` dicts.

**`layer4/plan_create.py` + `layer4/per_phase.py` (ctx) — WINDOWS THREADED (Andy-ratified, §2):** both `ValidatorContext` constructions now set `daily_availability_windows=daily_windows_from_layer1(layer1_payload)`.

**`layer4/hashing.py`:** `LAYER4_PROMPT_REVISION "8"→"9"` (recovery block: count→dates + suppress-on-empty change synthesis output).

Full suite **2639 passed / 30 skipped** (+13: 8 placement/band/derive unit tests in `test_layer4_session_grid.py`, 4 validator placement-match tests, +2 net render tests in `test_layer4_strength_pool.py`).

## 2. DECISION ratified mid-build (Andy, chat 2026-06-18) — thread windows into the validator ctx
**Discovery:** `daily_availability_windows` was **never populated in the production `ValidatorContext`** — only in tests. So the existing window-keyed rules (`daily_window_fit` [**blocker**], `schedule_violation` [warning]) AND the new D6 rule were all **dormant in prod** (enforced render-side via the prompt only). My D6 rule, written to guard on that field (like the other grid rules), would have been dead in prod too.
- I surfaced the tradeoff: **(A)** keep render-side enforcement + validator backstop (surgical, no behavior change), vs **(B)** thread windows in (D6 prod-enforced, but **activates `daily_window_fit` as a prod blocker for the first time** — a cross-cutting change, Rule #16 churn risk).
- **Andy chose (B).** Threaded `daily_windows_from_layer1(...)` into both ctx constructions. This is the **5th substantive file** (`plan_create.py`) beyond the design's 4 — flagged.

## 3. Watch-outs
- **🔴 #1 — `daily_window_fit` is now a LIVE PROD BLOCKER for the first time.** Any plan where the LLM stacks a day's total session minutes over its window now **blocks** (was previously silent in prod). Expected/intended per Andy's choice — but watch the first live plan-create for unexpected `daily_window_fit_*` rejections / correction-loop churn. The prompt already renders `=== Schedule ===` windows, so the LLM has the info to comply.
- **🔴 #2 — placement-match vs window-fit deadlock (carried + now more reachable).** With both live blockers, an over-full assigned recovery day (2 training + ~18 min recovery > the window) is a genuine infeasibility that blocks + churns. The design's deferred mitigation (window-minutes filter on placement candidates) is a **no-op** against this — enabled windows are `ge=30` min ≥ 18 min standalone, so the conflict is *dynamic* (training-stacked), not pre-resolvable deterministically (the §6a determinism limit: per-day realized volume isn't known pre-synthesis). **Diagnosable:** both `daily_window_fit_*` and `recovery_placement_mismatch_*` co-occur in the per-block failed-rules log (`per_phase.py:~2959`). Low risk for Andy's own (generous) expedition windows. If it bites live, the fix is a policy call (which rule yields) — surface to Andy, don't auto-resolve.
- **Render/validator agreement is load-bearing.** Both compute placement from `weekly_capacity_hours(layer1)` + `derive_*` over the same Layer1 windows + the same `PhaseSpec` dates + the same pure fns. If the orchestrator ever sets `ctx.capacity_hours` or the windows from a different source than render, placement-match will false-block every plan. Keep them sourced identically (same assumption `_rule_volume_band` already relies on).
- **`single_session.py` / `plan_refresh.py` stay `["cardio","strength"]`** (recovery not emitted there — D5). Their ctx constructions were NOT given windows this session (only plan_create + per_phase synthesis) — D6 stays dormant on those paths, which is correct (no recovery to place).
- **Pre-existing (NOT 3b's job, carried from 3a):** `race_week_brief._build_layer4_payload_for_validation` runs `_check_two_per_day` outside the per-override try/except → a non-contiguous single override 500s instead of a `schema_violation` retry. Separate hardening pass.

## 4. NEXT
- **Then the deferred race-week-brief recovery slice** (§13a / Slice 3a handoff §2) — a **Trigger #1 prompt change** (surface a recovery instruction in `race_week_brief`'s `_SYSTEM_PROMPT`/`_render_user_prompt` + render prior `recovery_exercises` into the prior-session lines) + enum-bind the field (thread `recovery_pool_ids` through `build_record_race_week_brief_tool`, mirroring `feasible_pool_ids`). Andy's call on scope/timing — filed as a #698 sub-item.
- **Then Track 2** (#698 cardio drills pool + Technical/Skill cull — separate design).
- **Other open:** #690/#624/#689 (Trigger #1 prompt); #283 (FIT-decode prod log).
- **STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify (Andy-action); **LIVE-VERIFY this slice** — a real plan-create with a recovery pool, confirm recovery lands on the assigned dates + no false `daily_window_fit`/`recovery_placement_mismatch` blocks (Andy-action; container can't reach Neon / trigger gen).

## 5. Verification
- Full suite **2639 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`).
- **Anchor checks for the next Rule #9 sweep:**
  - `grep -n "def compute_recovery_placement" layer4/session_grid.py` → def (the §6a core).
  - `grep -n "_rule_recovery_placement_match" layer4/validator.py` → def + `_ALL_RULES` registration.
  - `grep -n "daily_availability_windows=daily_windows_from_layer1" layer4/plan_create.py layer4/per_phase.py` → 2 hits (the §2 windows threading).
  - `grep -n "place a recovery session on" layer4/per_phase.py` → render branch (dates, not count).
  - `grep -n "LAYER4_PROMPT_REVISION = " layer4/hashing.py` → `"9"`.
  - `grep -n "len(sessions) > 2" layer4/validator.py` → **no hit** (3a freeze still fixed).
  - design v2 §13a → "**Slice 3b … ✅ SHIPPED (2026-06-18)**" + the windows-threading deviation bullet.

## 6. Files
**Substantive (this session):** `layer4/session_grid.py`, `layer4/per_phase.py`, `layer4/validator.py`, `layer4/hashing.py`, `layer4/plan_create.py` (+ tests `tests/test_layer4_session_grid.py`, `tests/test_layer4_validator.py`, `tests/test_layer4_strength_pool.py`). **Bookkeeping:** `CURRENT_STATE.md` (new Last-shipped), design v2 §13a (Slice 3b SHIPPED + windows-threading deviation), this handoff, #698 comment.

## 7. Read order for next session (Rule #13)
`CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh` → then the ratified design `designs/Layer4_RecoveryMobilitySession_RestDayPolicy_Design_v2.md` §13a and build the **deferred race-week-brief recovery slice** (Trigger #1 — needs Andy's scope call) or **Track 2**.
**STILL OWED (carried):** see §4.

---

**End of handoff.**
