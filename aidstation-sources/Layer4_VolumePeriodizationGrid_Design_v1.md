# Layer 4 — Per-week volume periodization grid (Design v1, for sign-off)

**Status:** SIGNED OFF + IMPLEMENTED (2026-06-05). Curve parameters confirmed by
Andy (§4 resolutions below). Shipped in `layer4/periodization.py` +
`validator.py` (`phase_week_volume_bands_hours`, `_rule_volume_band`) +
`per_phase.py` (`_format_phase_load_bands`, `recovery_week` stamp). v2 3A coupling
(Q4) is a **committed** follow-up, tracked separately.

**Resolved decisions (2026-06-05):**
- **Q1** Volume-neutral on Base/Build/Peak (phase mean = 1.0); **Taper is the
  exception** — a deliberate net-negative Bosquet descent (NOT renormalized).
- **Q2** Deload cadence = mode-dependent (`standard 4` / `compressed 3` /
  `extended 5`, reusing `per_phase._DELOAD_CADENCE`; `custom` → none); depth
  `_M_DELOAD = 0.55` (~45% cut). Evidence: 30–60% volume reduction, every 4–8 wk.
- **Q3** Loading ramp `_RAMP_STEP = 0.08` (~8%/wk, resets each deload → 3:1
  sawtooth); Taper factors 0.40 (race wk) / 0.60 / 0.75 (Bosquet 41–60%).
- **Q4** 3A coupling (`recent_trajectory` / `data_density` / ACWR) **deferred to
  v2** — committed, separate change.

**Date:** 2026-06-05
**Motivates:** the plan-58 `Build:w2` stall (per-discipline `volume_band` blockers → retry loop → 800s timeout).
**Related:** `Layer4_Spec.md` §5.4 (validator rule 1), §6.1 (phase allocation), §8.2–§8.5 (spec-auto flags), `Layer3_3A_Spec.md` (`recent_trajectory` "drives volume ramp shape").

---

## 1. Problem

`Build:w2` failed synthesis with three **blocker** validator failures:

```
volume_band_above_week_2_D-001_build   (blocker)  ← too many hours in one sport
volume_band_below_week_2_D-003_build   (blocker)  ← too few in another
volume_band_below_week_2_D-009_build   (blocker)  ← too few in a third
```

Two independent causes produced and then perpetuated the loop:

- **Cause A — model misallocation (real content error).** The weekly hour budget is a fixed pie (capacity-bounded). The synthesizer over-fed `D-001` and starved `D-003`/`D-009`. Today the prompt feeds per-discipline **flat low–high ranges** (`per_phase._format_phase_load_bands`); a range plus a shared ceiling leaves too much freedom to split badly.
- **Cause B — validator rigidity (false blocks).** `volume_band` grades every training week against **one flat per-phase band** (`validator.phase_volume_bands_hours`), but the prompt instructs the model to "ramp + deload + taper volume within the phase" (`per_phase.py:197`). A *correct* week-2 ramp can therefore land outside the flat band and hard-block. The only existing softening — demote `below`→warning — covers Peak/Taper/`recovery_week` **only**, never Build, and `above` is never demoted.

Each blocker forces a full re-synthesis retry, and each retry re-incurs the expensive synthesis attempt — so a content/validator mismatch on one week escalates to the function-timeout stall.

> **Out of scope for this note (tracked separately):** the per-attempt cost itself — the extended-thinking-first synthesizer runaway (~418s) plus the ungated first attempt. That is "WS-1 / forced-tool synthesis," an independent change that shortens each attempt from ~530s to ~110s. This note addresses *why attempts keep failing*; WS-1 addresses *why each failure is so expensive*. They are complementary and should ship together.

---

## 2. Design goal

Replace the flat per-phase band with a **per-`(phase, week_in_phase)` band grid** that bends with the intended periodization (ramp / deload / taper). The grid becomes the **single source of truth** consumed by three call sites:

1. **Validator** (`_rule_volume_band`) — grades each training week against *its own* week band.
2. **Synthesizer prompt** (`_format_phase_load_bands`) — feeds a **concrete per-week target** per discipline (band midpoint) plus the tolerance edges, instead of a flat range.
3. **Orchestrator** — stamps `recovery_week` on the deload weeks the grid identifies (closing the documented-but-unimplemented gap), so the flag is consistent with the band.

This single change addresses all six of the requested fixes:

| Requested fix | How the grid delivers it |
|---|---|
| Feed concrete hours (Cause A) | Per-week midpoint target rendered into the prompt — model stops guessing the split |
| "model allocation error" | Same as above — the concrete per-week, per-discipline anchor is the fix |
| Per-week periodization grid | This *is* the grid |
| Cover Build phases | Build weeks get correctly-shaped bands; no Build-specific demotion hack needed |
| Allow `above` demotion | Largely **obviated** — a legitimate high week is now *inside* its (higher) week band; a residual threshold (§5) handles the rest symmetrically |
| Validator rigidity | Removed at the source: the band bends, so legitimate progression isn't flagged |

---

## 3. The grid — structure & invariants

### 3.1 Core function (new)

```
phase_week_volume_bands_hours(
    layer2a, phase_name, week_in_phase, total_weeks_in_phase,
    plan_global_week_index,            # for deload cadence (§4.2)
    capacity_hours,
) -> dict[discipline_id, (low_hr, high_hr)]
```

It takes the existing flat band `(low, high)` from `phase_volume_bands_hours` and scales **both edges by a per-week multiplier `m(w)`**:

```
week_band(disc, w) = (low(disc) · m(w),  high(disc) · m(w))
week_target(disc, w) = midpoint = (low+high)/2 · m(w)     # the prompt anchor
```

The multiplier `m(w)` is **discipline-independent** (the whole week scales together) so the *cross-discipline proportions* from 2A are preserved — we are reshaping volume *over time*, not re-allocating *across sports*. (Cross-sport allocation correctness is handled by feeding the concrete target, §2 row 1.)

### 3.2 Invariant: volume-neutrality (proposed — see §4.1)

The multipliers **average to ~1.0 across the phase**:

```
mean over w in 1..W of m(w)  ≈  1.0
```

so total phase volume still equals the 2A phase allocation — the grid *redistributes* load within the phase (some weeks higher, deloads lower) without inflating or deflating the phase total. This keeps the grid consistent with the upstream 2A/3B volume budget and avoids silently changing training load. **This is a design choice; the alternative ("peak-anchored," where the flat band's high edge = the peak week and earlier weeks sit below it) raises total phase volume and is called out as Open Question Q1.**

### 3.3 Fallback

When the flat band can't be computed (no 2A payload / no capacity / no weekly-total row), the grid returns `{}` exactly as `phase_volume_bands_hours` does today → callers fall back to open-ended bands (no behavior change in that path).

---

## 4. The curve — **DECISIONS NEEDED** (this is the coaching-domain part)

Everything below is a *proposal*. These are the parameters I need you to confirm or correct.

### 4.1 Volume-neutral vs peak-anchored — **Q1**
Proposed: **volume-neutral** (§3.2). Confirm, or choose peak-anchored.

### 4.2 Deload cadence & depth — **Q2**
- **Cadence:** `Layer4_Spec.md` §8 / TS-60 says `recovery_week` is "typically every 4th week in standard mode (cycle lengths per mode TBD)." Proposed v1: a deload every 4th **plan-global** week (using `plan_global_week_index`), so cadence is continuous across phase boundaries rather than resetting each phase.
  - *Open:* per-mode cycle length (the spec's "TBD"). Proposed default 4 for all modes until tuned.
- **Depth:** proposed deload multiplier **`m_deload = 0.65`** (deload week ≈ 65% of the typical week). Confirm the depth.

### 4.3 Per-phase ramp shape — **Q3**
Proposed v1 shapes (loading weeks = non-deload weeks in the phase):

| Phase | Shape of `m(w)` over loading weeks |
|---|---|
| **Base** | Gentle linear ramp, ~0.9 → ~1.1 |
| **Build** | Steeper linear ramp, ~0.85 → ~1.2 |
| **Peak** | Hold high (~1.1) then step down on the final loading week |
| **Taper** | Monotonic descent, ~0.8 → ~0.4 into race week |

After the raw shape is applied, multipliers are **renormalized so the phase mean = 1.0** (per §4.1), with deload weeks pinned at `m_deload` first. Confirm the per-phase start/end fractions, or hand me your preferred numbers.

### 4.4 3A-driven modulation — **Q4 (scope)**
`recent_trajectory` is specified to "drive volume ramp shape," and §8.2 prescribes conservative ramps for sparse data. Proposed: **v1 ships the deterministic structural curve above; 3A-driven steepening/flattening (and ACWR/`data_density` coupling) is a v2 layer.** Confirm you're OK deferring 3A coupling, or say you want it in v1.

---

## 5. Validator changes (`layer4/validator.py`, `_rule_volume_band`)

- Swap the flat `phase_volume_bands_hours(...)` lookup for `phase_week_volume_bands_hours(..., week_in_phase, total_weeks_in_phase, plan_global_week_index, ...)`.
- Keep the existing severity structure around the *week* band: blocker at `< 0.8·low_w` or `> 1.2·high_w`, warning at the `0.9 / 1.1` edges.
- **Remove** the Peak/Taper/`recovery_week` `below`→warning demotion (lines 395–422): it was an interim patch for the flat band's wrongness; with a correctly-bending band, a deload/taper week is *inside* its (lower) band and no longer false-flags.
- **`above` becomes symmetric** with `below` — same blocker/warning thresholds around the week band. A genuinely over-prescribed week (e.g. ignoring a deload → way over the deload band) still blocks; a mild over warns. This is what "allow `above` to be demoted" resolves to once the band is correct.

*Net:* fewer special cases, not more. The grid replaces the demotion zoo.

## 6. Prompt changes (`layer4/per_phase.py`, `_format_phase_load_bands`)

- Render per **week-in-range**: for each week the block covers and each included discipline, emit a concrete target + tolerance, e.g.
  `- Cycling (D-001) — wk2: target 5.4 hr (ok 4.3–6.5)`.
- Add one explicit line that this is a deload week when applicable, tying to the `recovery_week` intent.
- This is the direct remedy for Cause A: the model receives the intended split, per week, instead of a flat range it has to divide blindly.

## 7. Orchestrator change — stamp `recovery_week`

- A small post-synthesis stamping step (the §8.1 "orchestrator-stamped" step that is currently absent) sets `recovery_week` on every session whose `(phase, week_in_phase, plan_global_week_index)` the grid marks as a deload — using the **same** deload determination as §4.2 so the flag and the band can never disagree.
- This closes the documented gap (`validator.py:408-413`) and lets `recovery_week` light up the existing downstream consumers (rest-spacing exemptions, UI, other rules) for free.

---

## 8. Shared deload determination (single source)

`§4.2` is implemented **once** (a small pure helper, e.g. `is_deload_week(plan_global_week_index, mode)`) and consumed by the grid (§3), the validator (§5, via the grid), and the stamper (§7). One definition → the band, the target, and the flag are always consistent.

---

## 9. Testing

- **Unit (grid):** multipliers average to 1.0 per phase (§3.2); deload weeks pinned at `m_deload`; per-phase shapes match §4.3; `{}` fallback preserved.
- **Unit (validator):** a correctly-ramped Build:w2 that *fails today* passes against its week band; a deload week prescribed at full volume blocks; an over-prescribed loading week blocks; demotion special-cases gone.
- **Unit (prompt):** concrete per-week targets render; deload weeks annotated.
- **Unit (stamper):** `recovery_week` lands on exactly the grid's deload weeks.
- **Regression:** existing `tests/test_layer4_validator.py` volume-band cases re-baselined to the grid; `tests/test_layer4_plan_create.py` end-to-end remains green.
- **Live proof:** a cold plan re-run (à la plan 58) — `Build:w2` accepts without volume-band blockers, no retry loop.

## 10. Back-compat / risk

- **No DB migration.** All inputs (2A bands, capacity, `week_in_phase`, phase weeks, plan-global week index) already exist or are derivable from phase structure.
- **Cached 2C/cone payloads unaffected** — this is Layer 4 band math + prompt text + a post-synthesis stamp.
- **Risk:** the curve is a coaching judgment; wrong parameters could push *legitimate* weeks out of band the other way. Mitigated by the volume-neutral invariant (totals preserved), the warning tier (soft signal before blocker), and shipping with WS-1 so any residual retry is cheap.

## 11. Rollout / sequencing

1. **WS-1 (parallel, no design needed):** forced-tool synthesis — biggest single lever on cycle *length*. Can land immediately.
2. **This grid (WS-3), after §4 sign-off:** shared deload helper → grid function → validator → prompt → stamper → tests.
3. WS-2's demotion band-aids are **absorbed** into WS-3 (§5) rather than shipped separately.

---

## 12. Open questions (consolidated — your call)

- **Q1** Volume-neutral (proposed) vs peak-anchored band? (§4.1)
- **Q2** Deload cadence (every 4th plan-global week?) and depth (`m_deload = 0.65`?). (§4.2)
- **Q3** Per-phase ramp start/end fractions — confirm the §4.3 table or supply your own.
- **Q4** Defer 3A `recent_trajectory` / ACWR / `data_density` coupling to v2 (proposed), or include in v1? (§4.4)
- **Q5** Land WS-1 (forced-tool) now as a separate quick win, or bundle it with the grid PR?
