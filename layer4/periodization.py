"""Per-week volume periodization grid — the per-`(phase, week_in_phase)` volume
shape shared by the validator (`volume_band`), the synthesizer prompt
(concrete per-week targets), and `recovery_week` stamping.

Background. The `volume_band` validator graded every training week against ONE
flat per-phase band (`validator.phase_volume_bands_hours`), while the prompt
told the model to "ramp + deload + taper volume within the phase." A correct
week-2 ramp could therefore land outside the flat band and hard-block, looping
re-synthesis into the function-timeout stall (prod plan 58, `Build:w2`). This
module replaces the flat band with a per-week multiplier so the band bends with
the intended periodization — band, prompt target, and `recovery_week` flag all
derive from ONE definition and can never disagree.

Curve (design note `Layer4_VolumePeriodizationGrid_Design_v1.md` §4; parameters
signed off 2026-06-05):

  * Deload cadence: mode-dependent (standard 4 / compressed 3 / extended 5; the
    canonical 3:1 mesocycle for standard), matching `per_phase._DELOAD_CADENCE`.
  * Deload depth: ~45% volume cut (`_M_DELOAD = 0.55`), within the 30–60% band
    of the deloading literature (DCU practical-deloading review).
  * Loading ramp: ~8%/week ascending within a loading block (`_RAMP_STEP`), the
    "10% guide" + ACWR 0.8–1.3 sweet-spot direction. The ramp counter RESETS at
    each deload, so a phase reads as a 3:1 sawtooth (ramp → deload → ramp) and a
    week coming OUT of a deload returns to baseline, not straight to the peak.
  * Base/Build/Peak are volume-NEUTRAL: the per-week multipliers are
    renormalized so the phase mean is 1.0, preserving the 2A phase allocation —
    the grid redistributes load WITHIN a phase, it does not inflate the total.
  * Taper is deliberately net-NEGATIVE (a Bosquet-2007 descent: ~41–60% volume
    reduction across its final weeks, intensity held), so it is NOT renormalized.

v2 (#424) — 3A coupling. `ramp_modulation_for(layer3a_payload)` derives a
`RampModulation(ramp_step_factor, deload_multiplier)` from three Layer-3A
signals and threads it into `phase_week_multipliers`:

  * `recent_trajectory.medium_term.direction` drives ramp slope (the 3A spec's
    "drives volume ramp shape"): building → steeper, fatigued/overreached/
    detrained → gentler.
  * `data_density.recent_workouts_count` → sparse-data athletes get a more
    conservative (flatter) ramp (`Layer4_Spec.md` §8.2 intent).
  * ACWR (`recent_trajectory.acwr_status.combined.zone`) caps the ramp slope
    when the athlete is already loaded, keeping the acute:chronic ratio in the
    safe band for THAT athlete's chronic load.

The factor scales the ramp STEP (week-to-week slope), not the absolute levels,
so the Base/Build/Peak phase-mean renormalization keeps the volume-neutral
invariant for free: a capped ramp just makes the phase flatter, it never
changes the phase total (that stays the 2A allocation's job). Fatigue signals
ALSO deepen the deload (lower `deload_multiplier`); renormalization keeps the
phase volume-neutral, so a deeper deload sharpens the recovery dip without
inflating the total. Absent payload → `NEUTRAL_MODULATION` → the v1
athlete-agnostic curve, so every entry point without 3A degrades gracefully.

Modulation magnitudes are v1 defaults (`_K_*`, `_DELOAD_DEEPEN_STEP`); tune
post-launch per the `Layer4_Spec.md` §8.3 calibration pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    from layer4.context import Layer3APayload
    from layer4.payload import PhaseStructure, PlanSession

PeriodizationMode = Literal["standard", "compressed", "extended", "custom"]

# Per-mode deload cadence (weeks between planned deloads). Mirrors
# `per_phase._DELOAD_CADENCE` (the value already surfaced to the synthesizer
# prompt) so the band and the prompt anchor agree. `None` (custom) → no
# auto-deloads (the athlete/coach drives the structure).
_DELOAD_CADENCE_WEEKS: dict[PeriodizationMode, int | None] = {
    "standard": 4,
    "compressed": 3,
    "extended": 5,
    "custom": None,
}

# `PhaseStructure.derived_from` → periodization mode. `layer4_override` has no
# 3B mode; default it to standard cadence (the common case).
_DERIVED_FROM_TO_MODE: dict[str, PeriodizationMode] = {
    "3b_standard": "standard",
    "3b_compressed": "compressed",
    "3b_extended": "extended",
    "3b_custom": "custom",
    "layer4_override": "standard",
}

_M_DELOAD = 0.55
"""Deload-week multiplier (~45% volume cut). A target ratio: the Base/Build/Peak
renormalization (volume-neutrality) nudges the realized absolute value slightly,
but the deload-to-loading RATIO is preserved."""

_RAMP_STEP = 0.08
"""Per-week loading ramp (~8%/wk), applied to the loading-week index since the
last deload (0-indexed). Renormalized away from absolute terms by the phase-mean
division below; what survives is the WEEK-TO-WEEK ramp slope."""

# Taper (Bosquet 2007): progressive volume reduction over the final weeks,
# intensity maintained. Keyed by weeks-from-phase-end (0 = the last/race week).
_TAPER_FACTOR_BY_WEEKS_FROM_END: dict[int, float] = {0: 0.40, 1: 0.60}
_TAPER_FACTOR_EARLY = 0.75
"""Taper weeks earlier than the final two sit at a milder reduction."""

_LOADING_PHASES = frozenset({"Base", "Build", "Peak"})


# ── v2 (#424) 3A modulation — v1 defaults, tune post-launch (Spec §8.3) ──────
#
# `ramp_step_factor` multiplies `_RAMP_STEP` (the week-to-week slope); the three
# sub-factors below multiply together then clamp to `_K_CLAMP`. 1.0 = neutral.

_K_TRAJECTORY: dict[str, float] = {
    "building": 1.15,  # rising → steeper ramp
    "peaking": 1.0,
    "recovered": 1.0,
    "steady": 1.0,
    "insufficient_data": 1.0,
    "fatigued": 0.85,  # flat/detrained/fatigued → gentler ramp
    "overreached": 0.85,
    "detrained": 0.85,
}

# Sparse-data athletes ramp conservatively (Spec §8.2). Keyed off
# `recent_workouts_count`; <5 mirrors the 3A builder's "very sparse" floor.
_K_DENSITY_VERY_SPARSE_MAX = 5
_K_DENSITY_SPARSE_MAX = 12
_K_DENSITY_VERY_SPARSE = 0.80
_K_DENSITY_SPARSE = 0.90

# ACWR cap — already-loaded athletes get a flatter ramp so acute:chronic stays
# in the safe band. Keyed on the 3A zone (which already classifies the
# no-chronic-base sentinel into `non_functional_overreach`). Sweet-spot /
# undertraining / detraining → 1.0 (never ACCELERATE on an ACWR signal alone).
_K_ACWR: dict[str, float] = {
    "non_functional_overreach": 0.70,
    "functional_overreach": 0.85,
}

_K_CLAMP = (0.5, 1.5)

# Deeper deload for fatigued / non-functional-overreached athletes. Each signal
# subtracts a step from `_M_DELOAD`, floored at `_DELOAD_DEEPEST` (~60% cut, the
# bottom of the cited 30–60% deloading band). Volume-neutrality keeps the phase
# total fixed → a deeper deload just sharpens the recovery dip.
_DELOAD_DEEPEN_STEP = 0.075
_DELOAD_DEEPEST = 0.40
_FATIGUE_DIRECTIONS = frozenset({"fatigued", "overreached", "detrained"})


class RampModulation(NamedTuple):
    """Per-athlete shaping of the loading curve, derived from Layer 3A.

    `ramp_step_factor` scales `_RAMP_STEP` (slope); `deload_multiplier` is the
    deload-week value (≤ `_M_DELOAD`). `NEUTRAL_MODULATION` = the v1
    athlete-agnostic curve."""

    ramp_step_factor: float
    deload_multiplier: float


NEUTRAL_MODULATION = RampModulation(1.0, _M_DELOAD)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def ramp_modulation_for(
    layer3a_payload: "Layer3APayload | None",
) -> RampModulation:
    """Map the three Layer-3A signals to a `RampModulation`. Reads only
    `recent_trajectory.medium_term.direction`,
    `recent_trajectory.acwr_status.combined.zone`, and
    `data_density.recent_workouts_count` — defensively, so a missing field or a
    `None` payload degrades to `NEUTRAL_MODULATION` (the v1 curve)."""
    if layer3a_payload is None:
        return NEUTRAL_MODULATION

    rt = getattr(layer3a_payload, "recent_trajectory", None)
    direction = getattr(getattr(rt, "medium_term", None), "direction", None)
    combined = getattr(getattr(rt, "acwr_status", None), "combined", None)
    zone = getattr(combined, "zone", None)
    workouts = getattr(
        getattr(layer3a_payload, "data_density", None), "recent_workouts_count", None
    )

    k_traj = _K_TRAJECTORY.get(direction or "", 1.0)
    if workouts is None:
        k_density = 1.0
    elif workouts < _K_DENSITY_VERY_SPARSE_MAX:
        k_density = _K_DENSITY_VERY_SPARSE
    elif workouts < _K_DENSITY_SPARSE_MAX:
        k_density = _K_DENSITY_SPARSE
    else:
        k_density = 1.0
    k_acwr = _K_ACWR.get(zone or "", 1.0)
    ramp_step_factor = _clamp(k_traj * k_density * k_acwr, *_K_CLAMP)

    deepen = 0.0
    if direction in _FATIGUE_DIRECTIONS:
        deepen += _DELOAD_DEEPEN_STEP
    if zone == "non_functional_overreach":
        deepen += _DELOAD_DEEPEN_STEP
    deload_multiplier = max(_M_DELOAD - deepen, _DELOAD_DEEPEST)

    return RampModulation(ramp_step_factor, deload_multiplier)


def log_ramp_modulation(layer3a_payload: "Layer3APayload | None") -> None:
    """Rule #15 — emit the per-athlete modulation decision (inputs + chosen
    factor) ONCE at the prompt-build path. `ramp_modulation_for` is pure and
    runs per memoized phase-week in the validator, so logging lives here rather
    than in the hot function to keep one attributable line per phase render."""
    if layer3a_payload is None:
        return
    rt = getattr(layer3a_payload, "recent_trajectory", None)
    direction = getattr(getattr(rt, "medium_term", None), "direction", None)
    zone = getattr(getattr(getattr(rt, "acwr_status", None), "combined", None), "zone", None)
    workouts = getattr(
        getattr(layer3a_payload, "data_density", None), "recent_workouts_count", None
    )
    mod = ramp_modulation_for(layer3a_payload)
    print(
        f"ramp_modulation: medium_term={direction} acwr_zone={zone} "
        f"workouts={workouts} → ramp_step_factor={mod.ramp_step_factor:.3f} "
        f"deload_multiplier={mod.deload_multiplier:.3f}"
    )


def mode_from_derived_from(derived_from: str | None) -> PeriodizationMode:
    """Map `PhaseStructure.derived_from` to a periodization mode (default
    standard for unknown / `layer4_override`)."""
    return _DERIVED_FROM_TO_MODE.get(derived_from or "", "standard")


def deload_cadence_weeks(mode: PeriodizationMode) -> int | None:
    return _DELOAD_CADENCE_WEEKS.get(mode)


def is_deload_week(global_week_index: int, mode: PeriodizationMode) -> bool:
    """`global_week_index` is 1-indexed from plan start. A deload falls on every
    `cadence`-th plan-global week (so cadence is continuous across phase
    boundaries, not reset per phase). `custom` mode → never auto-deload."""
    cadence = deload_cadence_weeks(mode)
    if cadence is None or cadence <= 0 or global_week_index < 1:
        return False
    return global_week_index % cadence == 0


def phase_global_start_week(
    phase_structure: "PhaseStructure | None", phase_name: str
) -> int | None:
    """1-indexed plan-global week of `week_in_phase == 1` for `phase_name`
    (= 1 + Σ weeks of all phases ordered before it). `None` when the structure
    is absent or the phase isn't present."""
    if phase_structure is None:
        return None
    acc = 0
    for p in phase_structure.phases:
        if p.phase_name == phase_name:
            return acc + 1
        acc += p.weeks
    return None


def _phase_weeks_of(
    phase_structure: "PhaseStructure | None", phase_name: str
) -> int | None:
    if phase_structure is None:
        return None
    for p in phase_structure.phases:
        if p.phase_name == phase_name:
            return p.weeks
    return None


def _taper_multipliers(phase_weeks: int) -> list[float]:
    out: list[float] = []
    for w in range(1, phase_weeks + 1):
        from_end = phase_weeks - w
        out.append(
            _TAPER_FACTOR_BY_WEEKS_FROM_END.get(from_end, _TAPER_FACTOR_EARLY)
        )
    return out


def phase_week_multipliers(
    phase_name: str,
    phase_weeks: int,
    phase_global_start: int,
    mode: PeriodizationMode,
    modulation: RampModulation = NEUTRAL_MODULATION,
) -> list[float]:
    """Volume multipliers for `week_in_phase` 1..`phase_weeks` (index `w-1` →
    week `w`).

    Loading phases (Base/Build/Peak): a ramp + planned deload, renormalized so
    the phase mean is 1.0 (volume-neutral). Taper: a Bosquet descent (NOT
    renormalized). Returns `[]` for a non-positive week count.

    `modulation` (#424) personalizes the loading curve from Layer 3A: it scales
    the ramp slope (`ramp_step_factor`) and sets the deload depth
    (`deload_multiplier`). The phase-mean renormalization below keeps Base/Build/
    Peak volume-neutral regardless of the modulation; default
    `NEUTRAL_MODULATION` reproduces the v1 athlete-agnostic curve."""
    if phase_weeks <= 0:
        return []
    if phase_name not in _LOADING_PHASES:  # Taper (and any non-loading phase)
        return _taper_multipliers(phase_weeks)

    step = _RAMP_STEP * modulation.ramp_step_factor
    raw: list[float] = []
    loading_idx = 0  # loading weeks since the last deload (ramp position)
    for w in range(1, phase_weeks + 1):
        gw = phase_global_start + (w - 1)
        if is_deload_week(gw, mode):
            raw.append(modulation.deload_multiplier)
            loading_idx = 0
        else:
            raw.append(1.0 + step * loading_idx)
            loading_idx += 1

    mean = sum(raw) / len(raw)
    if mean <= 0:
        return [1.0] * phase_weeks
    return [r / mean for r in raw]


def phase_week_multipliers_for_phase(
    phase_structure: "PhaseStructure | None",
    phase_name: str,
    layer3a_payload: "Layer3APayload | None" = None,
) -> list[float]:
    """The full per-week multiplier vector for `phase_name`, deriving cadence,
    global-week offset, and week count from `phase_structure`. `[]` when the
    structure can't resolve the phase. Both the validator band and the prompt
    target route through this, so they compute identically (no cadence drift).

    `layer3a_payload` (#424) personalizes the loading curve per athlete; `None`
    → the v1 athlete-agnostic curve (graceful degradation)."""
    weeks = _phase_weeks_of(phase_structure, phase_name)
    gstart = phase_global_start_week(phase_structure, phase_name)
    if weeks is None or gstart is None:
        return []
    mode = mode_from_derived_from(getattr(phase_structure, "derived_from", None))
    modulation = ramp_modulation_for(layer3a_payload)
    return phase_week_multipliers(phase_name, weeks, gstart, mode, modulation)


def week_volume_multiplier(
    phase_structure: "PhaseStructure | None",
    phase_name: str,
    week_in_phase: int,
    layer3a_payload: "Layer3APayload | None" = None,
) -> float:
    """The single per-week multiplier for one `(phase, week_in_phase)`. Returns
    1.0 (flat / no reshaping) when the structure can't resolve the week — so
    callers degrade gracefully to the flat per-phase band."""
    mults = phase_week_multipliers_for_phase(
        phase_structure, phase_name, layer3a_payload
    )
    if not (1 <= week_in_phase <= len(mults)):
        return 1.0
    return mults[week_in_phase - 1]


def is_deload_week_for(
    phase_structure: "PhaseStructure | None",
    phase_name: str,
    week_in_phase: int,
) -> bool:
    """Whether one `(phase, week_in_phase)` is a planned deload — same cadence
    the grid uses. Convenience for the prompt's deload annotation."""
    gstart = phase_global_start_week(phase_structure, phase_name)
    if gstart is None:
        return False
    mode = mode_from_derived_from(getattr(phase_structure, "derived_from", None))
    return is_deload_week(gstart + week_in_phase - 1, mode)


def stamp_recovery_week(
    sessions: "list[PlanSession]",
    phase_structure: "PhaseStructure | None",
) -> None:
    """Stamp `recovery_week` on every session whose plan-global training week is
    a planned deload (per the SAME cadence the grid uses, so the flag and the
    bent band can never disagree). Mutates `coaching_flags` in place; idempotent.
    No-op when the structure is absent.

    This is the §8.1 orchestrator-stamped step the spec documents but had no
    implementation — previously `recovery_week` was never written, so the
    deload-aware paths downstream never lit up."""
    if phase_structure is None:
        return
    mode = mode_from_derived_from(getattr(phase_structure, "derived_from", None))
    start_by_phase: dict[str, int | None] = {}
    for s in sessions:
        pm = getattr(s, "phase_metadata", None)
        if pm is None:
            continue
        phase_name = pm.phase_name
        if phase_name not in start_by_phase:
            start_by_phase[phase_name] = phase_global_start_week(
                phase_structure, phase_name
            )
        gstart = start_by_phase[phase_name]
        if gstart is None:
            continue
        gw = gstart + pm.week_in_phase - 1
        if is_deload_week(gw, mode) and "recovery_week" not in s.coaching_flags:
            s.coaching_flags.append("recovery_week")
