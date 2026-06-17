# Layer 4 — Recovery/Mobility session kind + load-adaptive rest days — Design

**Status:** RATIFIED (Andy 2026-06-17) — ready to build (Trigger #1 prompt + Trigger #3 schema/cross-layer). Build in slices (>5 files; see §13a). **D2 dose LOCKED 2026-06-17** to `{Base:3, Build:3, Peak:2, Taper:1}` × ~15–20 min after a second, dose-specific research pass (see §5 / §13 / the research doc's *Recovery-session dose* addendum). **D6 placement RATIFIED 2026-06-17 (v2):** recovery **placement is deterministic** (the grid computes the target recovery day(s) and renders them as a hard constraint); the LLM keeps **exercise selection** from the rendered pool. See §6a (new), the reshaped §6/§7, and the Slice 3 entry in §13a.
**Date:** 2026-06-17 (v2 — D6 deterministic-placement ratification; v1 archived under `archive/superseded-specs/`)
**Issue:** #698 follow-up (Track 1). **Evidence base:** `research/RecoveryMobility_RestDay_CardioDrills_EnduranceEvidence_v1.md`.
**Ratified decisions (Andy 2026-06-17):** new `recovery` session **kind** (not a discipline); **recovery is exempt from the ≤2/day training cap** — "2 cardio + 1 recovery OK; 1 cardio + 1 strength + 1 recovery OK"; recovery allocation must **not interfere with strength/cardio assignment**; **load-adaptive** rest days (full-rest floor + active-recovery variant, biased to full rest under high load); build this track **first**.
**Open decisions — RATIFIED:** **D1 = structured `recovery_exercises[]` block now** (parallel to `strength_exercises`, EX-id-bound to a recovery pool — NOT free-text); **D2 = `{Base:3, Build:3, Peak:2, Taper:1}` × ~15–20 min** (LOCKED 2026-06-17 — anchored to the one endurance-specific dedicated-session prescription found, 80/20 Endurance's 3×/wk × 15–20 min, trimmed at Peak/Taper for freshness; the periodization authorities periodize recovery as deload *weeks/days*, not weekly mobility sessions — so the exact count is a defensible, tunable default, weak-RCT-evidence by its own admission); **D3 = ≤2 training + ≤1 recovery/day** (`session_index_in_day` max→2); **D4 = bias to full rest when phase==Peak OR deload/taper week**; **D5 = `per_phase` (plan-create) + `race_week_brief` now; `plan_refresh`/`single_session` later**; **D6 = deterministic placement, LLM selection** (RATIFIED v2 2026-06-17 — the grid computes which day(s) carry recovery, anchored on the deterministically-known signals: the **long-session day**, **available days**, and the **week's load level** (capacity-hours band) + Peak/deload flags; the LLM still picks the `recovery_exercises` from the rendered pool. X/Y load thresholds **derived from the existing per-phase volume bands**, not fixed hours. See §6a).

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
1. **`# Recovery programming` system-prompt section:** explains the recovery kind — small mobility/soft-tissue/breathwork sessions, sub-threshold, that **do not count toward the daily session cap**. **Placement is deterministic (D6, §6a):** the section tells the synthesizer recovery days are *assigned*, not chosen — "emit a recovery session on exactly the dates the `=== Recovery programming ===` block lists; do not add, drop, or move them." The LLM's only job on recovery is filling `recovery_exercises` from the pool.
2. **Rendered recovery block** (deterministic, from `compute_recovery_dose` **+ `compute_recovery_placement`**, §6a): per week, the **explicit target dates** the recovery sessions must land on, plus the per-session minutes — e.g. "Week 2: place a recovery session on 2026-04-11 and 2026-04-14 (~18 min each) — mobility/soft-tissue/breathwork; these days are assigned, off the training cap." A zeroed week (deload bias or empty pool, §6a) renders the explicit full-rest line instead.
3. **Recovery exercise pool — structurally consumed (D1).** Build the strength-pool analog scoped to recovery types: `_RECOVERY_POOL_EXERCISE_TYPES = {mobility, flexibility / stretching, recovery / soft tissue, breathwork}` (case-insensitive, mirrors `_STRENGTH_POOL_EXERCISE_TYPES`), plus `compute_recovery_pool_ids(...)` (the EX-id enum bounding `recovery_exercises[*].exercise_id`) and `_format_recovery_exercise_pool(...)` (the rendered pool). Both filter the SAME `l2c.exercises_resolved` already used by the strength pool — reuses the #704 infrastructure; just a different type allowlist. 2D-excluded ids dropped (wrist/injury contraindications honored). The synthesizer picks `recovery_exercises` EX-ids from this enum (never invents), exactly like strength. **This is what gives the orphaned Mobility/Flexibility/Recovery/Breathwork catalog a real, structured home.** **Suppress-on-empty (D6):** when `compute_recovery_pool_ids(...)` returns **empty** (no resolvable recovery exercise for this athlete/locale), placement returns **zero** for the week and **no recovery instruction is rendered** — the LLM is never asked to fill an unfillable `recovery_exercises[]`, which would be a guaranteed-invalid payload and waste a correction-loop retry. Logged (Rule #15).

## 6a. Deterministic recovery placement (D6 — RATIFIED v2 2026-06-17)
**Decision (Andy, 2026-06-17):** *placement* of recovery sessions is **deterministic** (the grid decides which day(s) carry recovery, rendered to the prompt as a hard constraint and enforced by the validator); *exercise selection* stays with the **LLM** (it picks `recovery_exercises` from the rendered pool so it can target what was worked and honor 2D/injury context). This replaces the v1 prose judgment ("place on/after hard days or rest-adjacent") with a computed date list.

**The determinism limit (load-bearing — read first).** Per-DAY realized training volume is **not known deterministically before synthesis**, because which day carries which session is the LLM's layout job. At prompt-render time the only deterministic load signals are: the computed **long-session day** (the longest enabled availability window — already derived in `_format_schedule`), the set of **enabled/available days**, the week's **capacity-hours** level relative to the phase's load band, and the **Peak/deload** flags. So Andy's original per-day rule ("day volume in [X,Y] → recovery today/after; > Y extreme → not today") is **recast onto the week level + the long-day anchor** — the faithful deterministic projection of that intent, not a literal per-day volume test. (A literal per-day test is only possible by injecting recovery *after* the LLM lays out the week, which trades away LLM exercise selection — rejected by D6.)

**Load signal & thresholds — derived from the existing per-phase volume band (Andy ratified: not fixed hours).** The week's `weekly_capacity_hours` is classified against the phase's own `phase_load_bands` `[low, high]` (2A):
- **`light`** — capacity ≤ band-low (or no band): recovery placement is unconstrained among enabled days (low load; active recovery is harmless/adaptation-neutral).
- **`moderate`** (= Andy's `[X, Y]`) — capacity within the band: place the dose **anchored to the day *after* the long-session day** ("today or after" → post-key active recovery), then spread the remainder across other enabled days, **excluding the long-session day**.
- **`extreme`** (= Andy's `> Y`) — capacity ≥ band-high, **OR** `phase == "Peak"`, **OR** a deload week: **bias to genuine rest** — exclude the long-session day **and the day before it** (keep the pre-key day clean) from recovery candidates; do **not** further reduce the count (the count trim is the dose's job — §5 — not placement's, avoiding a double-trim).

`X = band-low`, `Y = band-high` for that phase; no new constant. (`band-low`/`band-high` come from the same 2A `phase_load_bands` the grid already reads for `weekly_capacity_hours`.)

**Function (new, `session_grid.py` — mirrors `compute_recovery_dose`):**
```
compute_recovery_placement(
    week_dates: list[date],          # the week's calendar dates (phase render range)
    enabled_days: set[str],          # day_of_week names with an enabled window (Layer 1 §K)
    long_session_dow: str | None,    # the longest-enabled-window day (shared w/ _format_schedule)
    dose_count: int,                 # compute_recovery_dose(...).sessions_this_week
    load_band: Literal["light","moderate","extreme"],
    pool_is_empty: bool,
) -> list[date]                      # the EXACT dates recovery must land on (sorted)
```
Algorithm: if `pool_is_empty` or `dose_count == 0` → return `[]`. Else build the candidate enabled dates for the week, drop the excluded days per the band rule above, order them by the anchor preference (day-after-long first under `moderate`; otherwise even spread), and take the first `dose_count`. **Clamp to the number of feasible candidate days** (can't place 2 recovery sessions on one day, §4) — if fewer candidates than `dose_count`, place what fits and **log the clamp (Rule #15)**. The returned date list is the **single source of truth** for both the rendered block (§6.2) and the validator (§8) — the dose's `sessions_this_week` is the *request*; this is what's actually placed.

**Wiring (`per_phase.py`):** the long-session-day derivation in `_format_schedule` (the longest enabled window, ties→earliest) is factored into a shared helper (or the value is threaded) so placement and the `=== Schedule ===` block name the **same** long day. `_format_recovery_programming` calls `compute_recovery_placement` per week and renders the explicit dates (§6.2).

**Why this kills retries:** placement is fixed, so the LLM has zero placement latitude to get wrong — it can only fill exercises (enum-bound) on assigned dates. The two failure paths Slice 2 left open — (a) the LLM mis-placing recovery and tripping the validator, (b) being asked to fill an empty pool — are both closed deterministically (placement + suppress-on-empty), not by retrying the model.

## 7. Load-adaptive rest-day policy (Trigger #1) — now realized by §6a placement
Rest stays athlete-owned (no forced rest count). The policy governs **whether a non-training day is full rest or light active recovery** — and under D6 it is **enacted deterministically by `compute_recovery_placement` (§6a)** rather than left to synthesizer judgment:
- **Default:** full rest is the floor; recovery sessions are the active-recovery mechanism, placed by §6a on enabled days anchored off the long-session day.
- **High-load weeks → bias to full rest:** the **count** trim is the dose (§5: Peak/Taper in the table + the deload-week `high_load` trim); the **placement** bias is §6a's `extreme` band (recovery kept off the long day and the pre-key day). **High-load = `phase == "Peak"` OR a deload week** (D4; `periodization.is_deload_week_for`). The capacity-band `extreme` classification (≥ band-high) is the additional within-phase trigger §6a adds.
- The synthesizer is still *told* (prose, §6.1) that under high load full rest is preferred — but the actual placement no longer depends on it following that prose; the date list already encodes it.

## 8. Validator (`validator.py`) — recovery handling
Add recovery to the kind-keyed rules, treating it like rest (zero-load, low-friction) **except** it carries a duration:
- **Exclude** from: volume-band grading (`_rule_volume_band`), ACWR load (`_rule_acwr` — recovery ≈ 0 training load), intensity/rest-spacing (`_rule_rest_spacing` — recovery isn't hard), strength-count (`_rule_strength_sessions_per_phase` / `_rule_strength_frequency_band`), discipline-excluded / skill-gate / sport-locale / indoor-only / schedule-violation / daily-window-fit *(recovery DOES still need its `duration_min` to fit the day's window — keep it in `_rule_daily_window_fit`, exclude only the discipline-keyed rules)*.
- **Apply — AMENDED two-per-day (`_rule_two_per_day`) — THE FREEZE FIX (live blocker on shipped Slice 2):** today `_rule_two_per_day` (validator.py:609) counts **all** sessions, so a valid 2-training + 1-recovery day trips `two_per_day_max_exceeded`, and `two_per_day_no_cardio`/`double_strength` misfire when recovery is in the mix (e.g. strength + recovery → "no cardio" blocker). This **freezes plan generation** for any plan the Slice-2 prompt induced to place recovery (the correction loop can't clear a structurally-valid payload). Mirror the already-shipped pydantic `_check_two_per_day` (payload.py): split `training = kind ∈ {cardio,strength}` vs `recovery = kind=='recovery'`; cap **`len(training) > 2`** and **`len(recovery) > 1`**; run the `double_strength` / `double_hard` / `no_cardio` blockers over **`training` only** (≥1 cardio required only when there are 2 *training* sessions). This is the §4 cap, re-expressed as the independent §5.4 check. **Sequence first (Slice 3a) — it un-freezes shipped behavior.**
- **New (D1 structured):** a recovery-pool-membership rule — the Rule-6a analog: every `recovery_exercises[*].exercise_id` must be in `compute_recovery_pool_ids(...)` (blocker if not, mirroring the strength out-of-pool reject). The enum bound makes this structurally near-impossible, but the validator backstops the `model_construct` / injected-session path.
- **New (D6 placement-match):** the week's set of `kind=='recovery'` session **dates must equal** `compute_recovery_placement(...)` for that week (blocker on mismatch — extra, missing, or moved recovery day). This is what makes deterministic placement *enforced*, not merely *requested*. Skipped when placement is unavailable to the validator context (e.g. a refresh path that doesn't carry the grid) — guard on context presence, like the other grid-derived rules.
- **New (optional, low priority):** a soft check that the placed recovery count matches the dose request when not clamped — Rule #15 log, not a blocker.

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
- `validator.py` (Slice 3a): recovery excluded from volume/ACWR/strength-count; **amended two-per-day — the freeze regression: 2 cardio + 1 recovery ✓, 1 cardio + 1 strength + 1 recovery ✓, strength + recovery (no cardio) ✓ (recovery doesn't trip `no_cardio`), 3 training ✗, 2 strength ✗**; pool-membership blocker on an out-of-pool `recovery_exercises` id.
- `session_grid.py` (Slice 3b): `compute_recovery_placement` — `moderate` band anchors day-after-long; `extreme` band excludes long-day + pre-key day; empty pool / zero dose → `[]`; clamp when candidate days < dose (+ Rule #15 log); placement and `_format_schedule` agree on the long day.
- `validator.py` (Slice 3b): D6 placement-match blocker on an extra/missing/moved recovery date; skipped when the grid isn't in context.
- `per_phase.py` (Slice 3b): recovery block renders explicit dates; suppressed entirely when the pool is empty.
- render: recovery branch (Slice 3a).
- Full suite green; `LAYER4_PROMPT_REVISION` `8→9` reflected in hashing tests (Slice 3b).

## 13. Decisions — ALL RATIFIED (Andy 2026-06-17)
- **D1 — recovery content:** ✅ **structured `recovery_exercises[]` block now** (EX-id-bound to the recovery pool; §3/§6).
- **D2 — dose numbers:** ✅ **LOCKED 2026-06-17** `{Base:3, Build:3, Peak:2, Taper:1}` × ~15–20 min (`_RECOVERY_SESSION_MINUTES = 18`). Grounded in a second, dose-specific research pass: 80/20 Endurance prescribes **3 mobility sessions/wk × 15–20 min** (the only endurance-specific dedicated-session dose found); practitioner sources for runners/cyclists cluster at 2–3×/wk × 15–20 min; the periodization authorities (Friel/Bompa/NSCA) periodize recovery as deload *weeks/days*, not weekly mobility sessions. Trimmed to 2 (Peak) / 1 (Taper) for freshness. Evidence strength weak on the exact count → tuning knob, not settled science. See the research doc's *Recovery-session dose* addendum.
- **D3 — daily cap:** ✅ ≤2 training + ≤1 recovery, `session_index_in_day` max→2 (matches Andy's examples).
- **D4 — high-load:** ✅ bias to full rest when `phase=="Peak"` OR deload/taper week (no new signal; ACWR/strain flag is a later add).
- **D5 — scope:** ✅ `per_phase` + `race_week_brief` now; `plan_refresh`/`single_session` later.
- **D6 — placement vs selection:** ✅ **RATIFIED v2 2026-06-17.** Recovery **placement is deterministic** (`compute_recovery_placement`, §6a — the grid computes the exact recovery dates from the long-session day + enabled days + capacity-band, rendered as a hard constraint, validator-enforced); the LLM keeps **exercise selection** from the rendered pool. **X/Y load thresholds = the existing per-phase `phase_load_bands` `[low, high]`** (Andy: derive from bands, not fixed hours). Determinism limit accepted: per-day realized volume isn't known pre-synthesis, so the placement is the week-level + long-day projection of Andy's per-day X/Y rule (§6a). Also covers **suppress-on-empty-pool** (no recovery instruction when the pool resolves empty — kills the unfillable-payload retry).

## 13a. Build slices (>5 files → split per the 5-file ceiling)
- **Slice 1 — schema + invariants: ✅ SHIPPED (#711, 2026-06-17).** `payload.py` (`kind` += recovery; new `RecoveryExercise` model + `recovery_exercises` field; `_check_kind_invariants` recovery branch; `_check_two_per_day` training-only cap + recovery exemption; `session_index_in_day` max→2) + tests. No prompt/grid yet — payload contract first.
- **Slice 2 — pool + dose + prompt: ✅ SHIPPED (#718, 2026-06-17).** `per_phase.py` (recovery schema enum + `session_index_in_day` schema max; `_RECOVERY_POOL_EXERCISE_TYPES` + `compute_recovery_pool_ids` + `_format_recovery_exercise_pool`; `# Recovery programming` prompt section + rendered recovery block; load-adaptive rest-day directive), `session_grid.py` (`_RECOVERY_SESSIONS_PER_WEEK` + `compute_recovery_dose`, allocated off the ceiling), `hashing.py` (`LAYER4_PROMPT_REVISION "7"→"8"`) + tests. **`high_load` = the per-week deload bias only (`is_deload_week_for`), trimming one session toward full rest (floor 0); the phase-level Peak/Taper freshness is already in `_RECOVERY_SESSIONS_PER_WEEK`, so high_load does NOT re-trim Peak/Taper (avoids double-trim). The broader D4 prompt directive still fires on Peak-phase OR any deload week.**
- **Slice 3a — validator alignment + render (THE FREEZE FIX): NEXT.** `validator.py` (amended `_rule_two_per_day` — training-only cap + recovery exemption, §8; recovery excluded from the discipline-keyed rules, §8; recovery-pool-membership rule, §8) + `race_week_brief.py` (taper-override `kind` enum += recovery) + `templates/plan_create/view.html` (recovery render branch, §9) + tests. **Sequenced first because it un-freezes shipped Slice-2 behavior** (the validator currently blocks any plan that placed recovery — tier-2 go-live blocker per the 4-tier order). 3 substantive files. Deterministic placement is NOT required to clear the freeze — the amended two-per-day alone does, so 3a ships independently.
- **Slice 3b — deterministic placement (D6) + suppress-on-empty: AFTER 3a.** `session_grid.py` (`compute_recovery_placement`, §6a — mirrors `compute_recovery_dose`) + `per_phase.py` (factor/thread the long-session-day derivation so placement and `=== Schedule ===` agree; `_format_recovery_programming` renders the placed **dates**, §6.2; suppress the recovery instruction when the pool is empty, §6.3) + `validator.py` (the D6 placement-match rule, §8) + tests. 3 substantive files. Bumps `LAYER4_PROMPT_REVISION "8"→"9"` (the recovery block text changes from a count to a date list) — `hashing.py`. **Note:** 3b reshapes the Slice-2 recovery block from "N sessions this week" to explicit dates; the load-adaptive prose (§6.1/§7) stays but is now belt-and-suspenders to the date list.

## 14. Gut check
- **Biggest risk:** over-engineering recovery into something heavy — the evidence is explicit that the dose is small and the performance/injury payoff is modest. The design keeps it capped, free-text, and off the training budget; resist scope creep into structured blocks/big volumes.
- **Second risk:** the daily-cap exemption + `session_index_in_day` max→2 touches a load-bearing invariant (`_check_two_per_day`) — must be surgical so a recovery slot can't be abused to smuggle a 3rd *training* session. The invariant is explicitly "≤2 *training* + ≤1 *recovery*," enforced by kind, not raw count.
- **Thin evidence:** the exact dose integers and the deload/rest-day frequencies are practitioner heuristics (the RCT base there is weak — flagged in the research doc), so they're tuning knobs, not settled science. Everything load-bearing (small dose, adaptation-neutral rest) is on firmer ground.
- **Best argument against:** "recovery doesn't need to be a first-class kind — fold it into warmup/cooldown." You considered and rejected this (you chose the new kind for trackability/separate-session intent); the cost is the schema+invariant surface above, which is real but contained.
- **D6 placement risk:** deterministic placement can collide with the LLM's training layout — the assigned recovery date might be the day the LLM wanted for a 2-training stack (fine — recovery is the legal 3rd slot) or, worse, a day the athlete's window is too short for even ~18 min (caught by `_rule_daily_window_fit`, which recovery still passes through). The mitigation is that placement only picks **enabled** days and the duration is small; the residual risk is a tightly-constrained week where the only enabled days are all key days — there the clamp + the validator's window-fit rule degrade gracefully (fewer recovery sessions) rather than freeze. **Watch in the first live plan:** whether the placement-match rule ever fights the window-fit rule (recovery assigned to a day it can't fit). If it does, placement needs a window-minutes filter on candidates — a one-line add deferred until a real case shows up (Rule #15 log will surface it).
- **Best argument against D6 itself:** "you're hard-coding a coach judgment the LLM was handling fine." True if the LLM placed recovery well — but Slice 2's prose placement is exactly what the validator can't verify and what burns correction-loop retries when it's wrong; making it deterministic trades a little nuance (the LLM can't notice "this particular week is unusually heavy") for verifiability and zero placement-retries. The nuance loss is bounded because the band-classification already captures the heavy-week case.
