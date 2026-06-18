# Layer 4 — Recovery/Mobility session kind + load-adaptive rest days — Design

**Status:** RATIFIED (Andy 2026-06-17) — ready to build (Trigger #1 prompt + Trigger #3 schema/cross-layer). Build in slices (>5 files; see §13a). **D2 dose LOCKED 2026-06-17** to `{Base:3, Build:3, Peak:2, Taper:1}` × ~15–20 min after a second, dose-specific research pass (see §5 / §13 / the research doc's *Recovery-session dose* addendum).
**Date:** 2026-06-17
**Issue:** #698 follow-up (Track 1). **Evidence base:** `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md`.
**Ratified decisions (Andy 2026-06-17):** new `recovery` session **kind** (not a discipline); **recovery is exempt from the ≤2/day training cap** — "2 cardio + 1 recovery OK; 1 cardio + 1 strength + 1 recovery OK"; recovery allocation must **not interfere with strength/cardio assignment**; **load-adaptive** rest days (full-rest floor + active-recovery variant, biased to full rest under high load); build this track **first**.
**Open decisions — RATIFIED:** **D1 = structured `recovery_exercises[]` block now** (parallel to `strength_exercises`, EX-id-bound to a recovery pool — NOT free-text); **D2 = `{Base:3, Build:3, Peak:2, Taper:1}` × ~15–20 min** (LOCKED 2026-06-17 — anchored to the one endurance-specific dedicated-session prescription found, 80/20 Endurance's 3×/wk × 15–20 min, trimmed at Peak/Taper for freshness; the periodization authorities periodize recovery as deload *weeks/days*, not weekly mobility sessions — so the exact count is a defensible, tunable default, weak-RCT-evidence by its own admission); **D3 = ≤2 training + ≤1 recovery/day** (`session_index_in_day` max→2); **D4 = bias to full rest when phase==Peak OR deload/taper week**; **D5 = `per_phase` (plan-create) + `race_week_brief` now; `plan_refresh`/`single_session` later.**

---

## 1. Purpose & boundaries
Give the **orphaned recovery/mobility 0B catalog** (`Mobility`, `Flexibility / Stretching`, `Recovery / Soft Tissue`, `Breathwork` — ~12 active rows) a prescription home, and make rest days a deliberate, load-aware choice rather than the implicit absence of training. Today these types have **no session kind** to live in (`kind ∈ {cardio, strength, rest}`) and could only ever have leaked into the strength pool (now closed, #704/#706).

**In scope:** a 4th session `kind="recovery"`; a deterministic per-week recovery **dose** computed *outside* the training-session ceiling; the daily-cap exemption (≤2 training + ≤1 recovery); load-adaptive rest-day policy; a recovery/mobility "consider these" pool rendered into the per-phase synthesis prompt; validator + render + cache updates.
**Out of scope (explicitly):** Track 2 (cardio drills pool / Technical-Skill cull) — separate design. Retrofitting existing `yoga`/`mobility` *disciplines* (they stay disciplines, rendered as cardio). A structured `recovery_exercises` payload block (v2 — see §6/D1). `plan_refresh` / `single_session` emitting recovery (v2 — see §5).

**Evidence guardrails (from the research doc):** recovery/mobility benefit **plateaus at small doses** (≈10 min/wk per muscle group; breathwork ≈5 min) and is **not an injury lever** (strength is) — so the dose is deliberately **small and capped**. Active-vs-passive rest is **adaptation-neutral** — so full rest is the protective default, active recovery an allowed variant, and the choice tilts on accumulated load.

## 2. The "doesn't interfere" guarantee (core constraint)
Recovery is allocated **separately from and after** the existing cardio/strength pipeline in `build_session_grid`:
1. discipline allocations → 2. `apply_session_ceiling` (training-load cap) → 3. `apply_strength_saturation_cap` → 4. intensity mix + typing → **5. NEW: `compute_recovery_dose` (additive, independent).**

The recovery dose is **never** passed through `apply_session_ceiling` and **never** counted in `cardio_total`/`IntensityMix`/`_STRENGTH` logic. It is a parallel, low-cost track. This is the mechanical meaning of Andy's "new logic, doesn't interfere with strength/cardio assignment."

## 3. Schema changes (Trigger #3)
| File:line | Change |
|---|---|
| `layer4/payload.py:233` | `PlanSession.kind`: add `"recovery"` → `Literal["cardio","strength","rest","recovery"]` |
| `layer4/payload.py` `PlanSession` | NEW field `recovery_exercises: list[RecoveryExercise] | None` (D1 structured block — mirror `strength_exercises`; `RecoveryExercise` carries `exercise_id` + free `prescription` text e.g. "2×30s/side"). EX-id-bound to the recovery pool enum in the schema. |
| `layer4/payload.py` `_check_kind_invariants` (~265–295) | add a `recovery` branch (§4) |
| `layer4/payload.py` `_check_two_per_day` (~602–624) | recovery exempt from the count + the cardio/strength pairing rules (§4) |
| `layer4/per_phase.py:519` | session-schema `kind` enum: add `"recovery"` |
| `layer4/per_phase.py:474` | `session_index_in_day` `"maximum": 1` → `2` (allow the recovery 3rd slot; see §4) |
| `layer4/race_week_brief.py:235` | taper-override `kind` enum: add `"recovery"` |
| `layer4/hashing.py:56` | `LAYER4_PROMPT_REVISION "7" → "8"` (prompt changes → cache invalidation) |

`plan_refresh.py:250` / `single_session.py:255` stay `["cardio","strength"]` for v1 (they emit working sessions only). **Flag:** a refresh that drops a recovery session can't re-emit it until v2 — acceptable (recovery is non-load-bearing); noted as a follow-up.

## 4. `kind="recovery"` invariants & the daily-cap exemption
**Recovery session invariants** (`_check_kind_invariants`):
- `recovery_exercises` is **non-empty** (D1 structured — the analog of strength's "strength_exercises required"); `cardio_blocks` is None/empty; `strength_exercises` is None/empty; `rest_reason` is None.
- `duration_min` ∈ [5, 45] (small-dose evidence; typical 10–20).
- `intensity_summary` ∈ {`rest`, `easy`} (recovery is sub-threshold).
- `discipline_id` / `locale_id` = None (recovery is not a discipline; like rest it isn't locale-routed). `coaching_intent`/`session_notes` carry the framing; the prescribed work is the structured `recovery_exercises` (EX-ids from the recovery pool, §6).

**Daily-cap exemption** (`_check_two_per_day` + validator `_rule_two_per_day`): redefine the cap over **training sessions only** (`kind ∈ {cardio, strength}`):
- ≤ 2 training sessions/day **plus** ≤ 1 recovery session/day (so 2 cardio + 1 recovery ✓; 1 cardio + 1 strength + 1 recovery ✓; 2 strength still ✗; a day with only training sessions still needs ≥1 cardio if it has 2 training).
- `session_index_in_day` max → 2 (three slots possible only when one is recovery). Recovery takes the highest index (placed last in a day).
- Recovery does **not** trip "all strength" / "no cardio" pairing blockers — those apply to the training pair only.

## 5. Recovery dose (deterministic, phase-aware) — `session_grid.py`
Mirror the strength-dose constant pattern (`_STRENGTH_SESSIONS_PER_WEEK = {Base:2,Build:2,Peak:1,Taper:1}`):

```
_RECOVERY_SESSIONS_PER_WEEK = {"Base": 3, "Build": 3, "Peak": 2, "Taper": 1}   # LOCKED 2026-06-17 — D2
_RECOVERY_SESSION_MINUTES = 18                                                  # LOCKED 2026-06-17 — D2 (~15–20 min band; 18 = midpoint)
```
Rationale (dose-specific research pass, 2026-06-17): **3×/wk × 15–20 min** matches the single endurance-specific dedicated-session prescription in the literature — 80/20 Endurance (Fitzgerald/Warden) — and the practitioner consensus cluster for runners/cyclists (2–3×/wk × 15–20 min). Held at 3 through Base/Build, trimmed to 2 at Peak and 1 in Taper for freshness (the periodized deload *week* — Friel: every 3rd–4th week — carries phase-level recovery, per D4, not a higher session count). `compute_recovery_dose(phase_name, week_flags) -> RecoveryAllocation` returns the count + per-session minutes; rendered as its own prompt block (§6). **Not** in `discipline_allocations`, **not** ceilinged. The integers stay tuning knobs — the RCT base for an exact session count is weak (one coaching program + practitioner blogs); what's firm is the *small per-session* volume and the deload-week construct.

## 6. Prompt changes (Trigger #1) — `per_phase.py`
1. **`# Recovery programming` system-prompt section:** explains the recovery kind — small mobility/soft-tissue/breathwork sessions, sub-threshold, that **do not count toward the daily session cap**, placed on/after hard days or rest-adjacent; full rest is preferred under high load (§7).
2. **Rendered recovery block** (deterministic, from `compute_recovery_dose`): "Recovery: N sessions this week, ~M min each — mobility/soft-tissue/breathwork; place off the training cap."
3. **Recovery exercise pool — structurally consumed (D1).** Build the strength-pool analog scoped to recovery types: `_RECOVERY_POOL_EXERCISE_TYPES = {mobility, flexibility / stretching, recovery / soft tissue, breathwork}` (case-insensitive, mirrors `_STRENGTH_POOL_EXERCISE_TYPES`), plus `compute_recovery_pool_ids(...)` (the EX-id enum bounding `recovery_exercises[*].exercise_id`) and `_format_recovery_exercise_pool(...)` (the rendered pool). Both filter the SAME `l2c.exercises_resolved` already used by the strength pool — reuses the #704 infrastructure; just a different type allowlist. 2D-excluded ids dropped (wrist/injury contraindications honored). The synthesizer picks `recovery_exercises` EX-ids from this enum (never invents), exactly like strength. **This is what gives the orphaned Mobility/Flexibility/Recovery/Breathwork catalog a real, structured home.**

## 7. Load-adaptive rest-day policy (Trigger #1, deterministic input)
Rest stays athlete-owned (no forced rest count). The policy governs **whether a non-training day is full rest or light active recovery**:
- **Default:** full rest is the floor; recovery sessions are the active-recovery mechanism, preferentially placed on lighter days.
- **High-load weeks → bias to full rest** (fewer/zero recovery-on-rest-day substitutions; keep recovery minimal/short). **High-load = `phase == "Peak"` OR a deload/taper week OR a week the periodizer flags high-strain.** (D4 — exact flag source below.)
- The synthesizer is told: under high load, prefer genuine full rest over active recovery; otherwise light active recovery is fine (adaptation-neutral per the evidence).

## 8. Validator (`validator.py`) — recovery handling
Add recovery to the kind-keyed rules, treating it like rest (zero-load, low-friction) **except** it carries a duration:
- **Exclude** from: volume-band grading (`_rule_volume_band`), ACWR load (`_rule_acwr` — recovery ≈ 0 training load), intensity/rest-spacing (`_rule_rest_spacing` — recovery isn't hard), strength-count (`_rule_strength_sessions_per_phase`), discipline-excluded / skill-gate / sport-locale / indoor-only (recovery has no discipline).
- **Apply (amended):** the two-per-day rule per §4.
- **New (D1 structured):** a recovery-pool-membership rule — the Rule-6a analog: every `recovery_exercises[*].exercise_id` must be in `compute_recovery_pool_ids(...)` (blocker if not, mirroring the strength `equipment_unavailable`/out-of-pool reject). The enum bound makes this structurally near-impossible, but the validator backstops it.
- **New (optional, low priority):** a soft check that the week's recovery count ≈ the deterministic dose (advisory, not a blocker) — Rule #15 log rather than a hard rule for v1.

## 9. Render (`templates/plan_create/view.html:110–112`)
Add `{% elif sess.kind == 'recovery' %}` → "Recovery — {{ duration_min }} min" with the session_notes body; intensity chip shows easy/rest. No cardio_blocks / strength_exercises rendering (both absent). A recovery session renders as a distinct light card, visually subordinate to training sessions.

## 10. Caching
`LAYER4_PROMPT_REVISION "7"→"8"` — the recovery prompt section + pool change synthesis output, so cached plans must regenerate. No layer0/DDL change (recovery reads existing 0B rows; no migration).

## 11. Edge cases
- Zero recovery dose (e.g., a phase set to 0) → no recovery block rendered; behaves like today. 
- Recovery on a 2-training-session day = the 3rd slot (index 2); a day can't have 2 recovery sessions.
- Taper/race week: recovery trimmed to 1 (or 0 in the final taper week via the high-load bias) — freshness first.
- Existing cached plans (revision 7) keep rendering (backward-compatible kinds); only regenerated plans get recovery.
- Wrist-injury / 2D exclusions: recovery content is free-text; the 2D contraindication surface still applies to the rendered pool (exclude contraindicated mobility moves) — reuse the existing exclusion plumbing on the recovery pool.

## 12. Test plan
- `payload.py`: recovery invariants (valid recovery row; rejects cardio_blocks/strength_exercises/rest_reason on recovery); two-per-day exemption (2 cardio+1 recovery ✓; 1+1+1 ✓; 2 strength ✗; 3 training ✗).
- `session_grid.py`: `compute_recovery_dose` per phase; recovery NOT in discipline_allocations; ceiling unaffected by recovery (the "doesn't interfere" assertion — same cardio/strength counts with/without recovery).
- `per_phase.py`: recovery block + pool render; high-load bias text present in Peak/deload.
- `validator.py`: recovery excluded from volume/ACWR/strength-count; amended two-per-day.
- render: recovery branch.
- Full suite green; `LAYER4_PROMPT_REVISION` bump reflected in hashing tests.

## 13. Decisions — ALL RATIFIED (Andy 2026-06-17)
- **D1 — recovery content:** ✅ **structured `recovery_exercises[]` block now** (EX-id-bound to the recovery pool; §3/§6).
- **D2 — dose numbers:** ✅ **LOCKED 2026-06-17** `{Base:3, Build:3, Peak:2, Taper:1}` × ~15–20 min (`_RECOVERY_SESSION_MINUTES = 18`). Grounded in a second, dose-specific research pass: 80/20 Endurance prescribes **3 mobility sessions/wk × 15–20 min** (the only endurance-specific dedicated-session dose found); practitioner sources for runners/cyclists cluster at 2–3×/wk × 15–20 min; the periodization authorities (Friel/Bompa/NSCA) periodize recovery as deload *weeks/days*, not weekly mobility sessions. Trimmed to 2 (Peak) / 1 (Taper) for freshness. Evidence strength weak on the exact count → tuning knob, not settled science. See the research doc's *Recovery-session dose* addendum.
- **D3 — daily cap:** ✅ ≤2 training + ≤1 recovery, `session_index_in_day` max→2 (matches Andy's examples).
- **D4 — high-load:** ✅ bias to full rest when `phase=="Peak"` OR deload/taper week (no new signal; ACWR/strain flag is a later add).
- **D5 — scope:** ✅ `per_phase` + `race_week_brief` now; `plan_refresh`/`single_session` later.

## 13a. Build slices (>5 files → split per the 5-file ceiling)
- **Slice 1 — schema + invariants: ✅ SHIPPED (#711, 2026-06-17).** `payload.py` (`kind` += recovery; new `RecoveryExercise` model + `recovery_exercises` field; `_check_kind_invariants` recovery branch; `_check_two_per_day` training-only cap + recovery exemption; `session_index_in_day` max→2) + tests. No prompt/grid yet — payload contract first.
- **Slice 2 — pool + dose + prompt: ✅ SHIPPED (#718, 2026-06-17).** `per_phase.py` (recovery schema enum + `session_index_in_day` schema max; `_RECOVERY_POOL_EXERCISE_TYPES` + `compute_recovery_pool_ids` + `_format_recovery_exercise_pool`; `# Recovery programming` prompt section + rendered recovery block; load-adaptive rest-day directive), `session_grid.py` (`_RECOVERY_SESSIONS_PER_WEEK` + `compute_recovery_dose`, allocated off the ceiling), `hashing.py` (`LAYER4_PROMPT_REVISION "7"→"8"`) + tests. **`high_load` = the per-week deload bias only (`is_deload_week_for`), trimming one session toward full rest (floor 0); the phase-level Peak/Taper freshness is already in `_RECOVERY_SESSIONS_PER_WEEK`, so high_load does NOT re-trim Peak/Taper (avoids double-trim). The broader D4 prompt directive still fires on Peak-phase OR any deload week.**
- **Slice 3 — validator + render: NEXT.** `validator.py` (recovery handling + pool-membership rule + amended two-per-day) + `race_week_brief.py` (enum) + `templates/plan_create/view.html` (recovery branch) + tests.

## 14. Gut check
- **Biggest risk:** over-engineering recovery into something heavy — the evidence is explicit that the dose is small and the performance/injury payoff is modest. The design keeps it capped, free-text, and off the training budget; resist scope creep into structured blocks/big volumes.
- **Second risk:** the daily-cap exemption + `session_index_in_day` max→2 touches a load-bearing invariant (`_check_two_per_day`) — must be surgical so a recovery slot can't be abused to smuggle a 3rd *training* session. The invariant is explicitly "≤2 *training* + ≤1 *recovery*," enforced by kind, not raw count.
- **Thin evidence:** the exact dose integers and the deload/rest-day frequencies are practitioner heuristics (the RCT base there is weak — flagged in the research doc), so they're tuning knobs, not settled science. Everything load-bearing (small dose, adaptation-neutral rest) is on firmer ground.
- **Best argument against:** "recovery doesn't need to be a first-class kind — fold it into warmup/cooldown." You considered and rejected this (you chose the new kind for trackability/separate-session intent); the cost is the schema+invariant surface above, which is real but contained.
