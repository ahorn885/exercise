# V5 Implementation — plan-78 Build:w1 failure → unified day-composition normalizer (Closing Handoff)

**Date:** 2026-06-21
**Branch:** `claude/plan-78-generation-vzl2b6`
**PR:** open + auto-merge armed (`Fixes #831`)
**Issue:** [#831](https://github.com/ahorn885/exercise/issues/831)

## 1. Task

Andy: "plan 78 failed. investigate why" → fix.

## 2. Investigation (Rule #14 — read the real logs)

Container can't reach Neon, so pulled prod via the read-only **`neon-query`** GitHub Action:

- `plan_versions` id=78: user 1, `plan_create`, scope 2026-06-21→2026-07-17, `generation_status='failed'`, `generation_units_cached=0`, no traceback. `generation_error`: `synthesis_budget_exhausted: Build:w1: per-block budget spent before any validation pass completed (every attempt raised a payload invariant violation)`.
- `vercel_logs` for the generation window: every Build:w1 attempt → `payload validation failed (ValidationError): ... 2026-06-25: no strength+strength on same day`; the multi-session dump showed `2026-06-25: strength/D-003/idx0, strength/D-012/idx1, recovery/-/idx2`. 2nd pass: `REPEATED identically with 0 cached blocks — deterministic; failing fast`.

## 3. Root cause

The 6/25 day carried **two different-discipline strength sessions + an additive #698 recovery slot** (3 sessions). It was repaired by **neither** pre-validation guard:

- `_repair_strength_collisions` guard `if len(ss) != 2 or len(strengths) != 2: continue` → skipped the 3-session day.
- `_repair_day_composition` only fired on same-discipline or two-hard → different-discipline strength+strength matched neither.

`Layer4Payload._check_two_per_day` (`layer4/payload.py:684`) then hard-rejected strength+strength every attempt. Structural pattern: each guard hard-codes a day **shape**, so #698's recovery slot silently re-opened a hole — same `first-Build-block-fails` symptom as pv=69/plan-75/pv76-77, distinct cause each time.

## 4. Fix (Andy chose: unified normalizer over surgical guard)

Replaced both guards with one shape-agnostic **`_normalize_day_composition`** (`layer4/per_phase.py`). It derives offenders from `_check_two_per_day`'s own clauses across **all** days and guarantees the invariant pre-validation:

- relocate the later (mover) session onto the nearest single non-hard **cardio of a different discipline** (consumed once); else
- demote a two-hard day's mover `intensity_summary` hard→moderate; else
- **drop** the mover (strength+strength / excess). #778 same-discipline relocation kept best-effort (legal → never dropped). Defensive caps for >2 training / >1 recovery. Final pass renumbers each day's indices contiguous 0..n-1 (recovery keeps the last slot).

Drop-as-last-resort ⇒ the **day-composition** failure class is structurally unreachable. Does NOT cover unrelated hard invariants (#803 resolution-tier, schema parse, validator rules).

**No prompt/cache/migration change** — deterministic post-LLM repair; prompt wording unchanged → no `LAYER4_PROMPT_REVISION` bump. Failed plan cached 0 blocks → regen re-synthesizes Build:w1 fresh.

## 5. Files

- `layer4/per_phase.py` — `_normalize_day_composition` (replaces `_repair_strength_collisions` + `_repair_day_composition`); call site in `synthesize_phase`; 2 comment refs updated.
- `layer4/session_grid.py` — comment ref updated.
- `tests/test_layer4_day_composition_normalizer.py` (new) — consolidates both retired suites + plan-78 regression + >2-training cap.
- removed `tests/test_layer4_strength_collision_repair.py`, `tests/test_layer4_day_composition_repair.py`.
- `tests/test_layer4_plan_create.py` — `test_three_sessions_one_day_is_normalized_not_fatal` (was `_is_retryable_not_fatal`).

**Full suite: 3095 passed / 30 skipped.**

## 6. Next session

### 6.1 Live-verify owed (Andy-action — container can't run plan-gen)
On deploy, regenerate plan #78 → `/admin/logs` shows `synthesize_phase: Build:w1 day-composition normalize — 2026-06-25: …`, and the plan reaches `ready` with no `no strength+strength` reject. If Build:w1 then trips a *different* hard invariant, that's a separate class — re-pull the logs.

### 6.2 Open question parked
Andy floated discouraging two same-discipline **cardio** (e.g. two trail runs) as a quality rule. It's legal (doesn't fail plans), so it was deliberately left as best-effort relocation. Scope as its own change if wanted.

### 6.3 Operating notes / read order
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. this handoff
5. `./scripts/verify-handoff.sh` — anchor sweep

## 7. Bookkeeping

- `CURRENT_STATE.md` — new "Last shipped" entry prepended; prior #424 entry demoted to predecessor.
- Issue #831 filed; closes on merge via `Fixes #831`.

## 8. Anchor table (Rule #10 — next session's Rule #9 sweep)

| Claim | File | Anchor | Check |
|---|---|---|---|
| Unified normalizer exists | `layer4/per_phase.py` | `def _normalize_day_composition(` | grep |
| Old guards removed | `layer4/per_phase.py` | `_repair_strength_collisions` / `_repair_day_composition` | grep → only doc-mirror refs in `_repair_recovery_exercises`, none as defs |
| Call site rewired | `layer4/per_phase.py` | `day-composition normalize —` | grep |
| Hard invariant | `layer4/payload.py` | `no strength+strength on same day` | grep |
| New test suite | `tests/test_layer4_day_composition_normalizer.py` | `test_plan78_strength_plus_strength_plus_recovery_relocates` | grep |
| Old suites retired | `tests/` | `test_layer4_strength_collision_repair.py` absent | ls |
