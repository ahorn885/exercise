"""Deterministic per-week training grid — Track 2 slice 2b (§5.1, §5.2, §5.3
of `Layer4_DeterminismFirst_Synthesis_Design_v1.md`).

Replaces the LLM's "decide how many sessions per discipline this week" job with
a deterministic computation off `phase_load × phase_week_multipliers ÷
typical_session_hours`. The LLM keeps placement (which day, which time-of-day)
+ content (exercise selection, coaching intent); the grid hands it a pre-filled
allocation.

Slice 2b covers:
  - session counts per discipline (`build_session_grid`), with §2.2's
    maintenance-cadence rule for sub-0.5-sessions/week disciplines.
  - intensity split (polarized per-phase ratios, Seiler 2010).
  - race-sim long day slot for `race_format == 'continuous_multi_day'`.

Slice 2c will extend with rest-detection (`expected_rest_count` +
`detect_insufficient_rest`); not in 2b.

Cache surface: pure function of (layer2a, phase_structure, phase, week_in_phase,
capacity_hours, race_format, race_duration_h). No new key surface beyond what
`periodization` + `validator.phase_week_volume_bands_hours` already contribute.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from layer4.context import Layer2APayload
from layer4.payload import PhaseStructure
from layer4.validator import phase_week_volume_bands_hours

# ─── Constants ──────────────────────────────────────────────────────────────

# Per-discipline AVERAGE session duration (hours). Coach-set defaults reflecting
# the typical mix within a discipline's weekly volume (e.g. for running this
# blends easy 1h sessions + 1 long 2h, average ~1.25h). The LLM places long-day
# variation within the discipline. PGE coverage explicit; fallback at 1.0h.
#
# v1.1 may lift these to a layer0 coach-config table; for v1 they're module-
# level constants per the spec §5.1.4.
_DISCIPLINE_TYPICAL_SESSION_HOURS: dict[str, float] = {
    "trail_running": 1.25,
    "road_running": 1.0,
    "mountain_running": 1.5,
    "hiking": 2.0,
    "mtb_outdoor": 1.5,
    "mtb_indoor": 1.0,
    "outdoor_road_cycling": 1.5,
    "outdoor_gravel_cycling": 1.5,
    "indoor_cycling": 1.0,
    "packrafting": 1.5,
    "kayaking": 1.5,
    "stand_up_paddleboarding": 1.5,
    "swimming": 1.0,
    "open_water_swimming": 1.25,
    "rock_climbing_outdoor": 1.5,
    "rock_climbing_indoor": 1.5,
    "abseiling": 0.75,
    "skimo": 1.5,
    "cross_country_skiing": 1.5,
    "strength": 1.0,
    "yoga": 0.75,
    "mobility": 0.5,
}
_DEFAULT_TYPICAL_SESSION_HOURS = 1.0

# Polarized intensity split per phase (Seiler 2010 80/20 + race-prep concentration
# in Peak). Values are (easy_fraction, hard_fraction); moderate is intentionally
# omitted (polarized training avoids zone 3). Sums to 1.0.
_PHASE_INTENSITY_SPLIT: dict[str, tuple[float, float]] = {
    "Base": (0.90, 0.10),
    "Build": (0.80, 0.20),
    "Peak": (0.70, 0.30),
    "Taper": (0.90, 0.10),
}

# Maintenance-cadence threshold: below this many sessions/week, the discipline
# rotates onto a multi-week cadence instead of being rounded up to 1/wk. Andy
# 2026-06-06: prevents over-allocation of small-share disciplines (climbing at
# 3% of PGE phase_load → ~1 session every 3-4 weeks, not weekly).
_MAINTENANCE_CADENCE_THRESHOLD = 0.5

# Race-sim long day caps for continuous_multi_day races.
_RACE_SIM_MAX_DURATION_HR = 8.0
_RACE_SIM_FRACTION_OF_RACE = 1.0 / 8.0  # Peak race-sim ≈ race_duration / 8
_RACE_SIM_TAPER_SCALE = 0.6  # Taper-1 race-sim ≈ 60% of Peak race-sim


# ─── Typed result models ────────────────────────────────────────────────────


@dataclass(frozen=True)
class DisciplineAllocation:
    """One discipline's per-week session count + cadence reasoning."""

    discipline_id: str
    discipline_name: str
    sessions_this_week: int
    typical_session_minutes: int
    target_hours_this_week: float  # mid of `phase_week_volume_bands_hours` band
    cadence_note: str | None = None  # "maintenance: 1× every 3 weeks" when sub-threshold


@dataclass(frozen=True)
class IntensityMix:
    """Phase-level polarized split — applies across ALL cardio sessions in the
    week (the LLM places easy/hard by day; the grid only enforces counts).
    Moderate intentionally absent per polarized training (Seiler 2010)."""

    easy_count: int
    hard_count: int

    @property
    def total(self) -> int:
        return self.easy_count + self.hard_count


@dataclass(frozen=True)
class RaceSimLongDay:
    """Continuous-multi-day race-format Peak/Taper-1 anchor session. Multi-
    discipline, weekend-anchored; the LLM fills the discipline mix from the
    week's available disciplines."""

    phase_position: Literal["peak", "taper_1"]
    duration_min: int
    multi_discipline: bool = True
    weekend_anchored: bool = True


@dataclass(frozen=True)
class SessionGrid:
    """Deterministic per-week training grid — the pre-filled allocation the
    per_phase synthesizer prompt presents to the LLM (slice 2b prompt rewrite)."""

    phase_name: str
    week_in_phase: int
    weekly_capacity_hours: float
    discipline_allocations: list[DisciplineAllocation] = field(default_factory=list)
    intensity_mix: IntensityMix = field(
        default_factory=lambda: IntensityMix(easy_count=0, hard_count=0)
    )
    race_sim_long_day: RaceSimLongDay | None = None


# ─── Algorithm ──────────────────────────────────────────────────────────────


def _typical_session_hours(discipline_id: str) -> float:
    return _DISCIPLINE_TYPICAL_SESSION_HOURS.get(
        discipline_id, _DEFAULT_TYPICAL_SESSION_HOURS
    )


def _maintenance_cadence_weeks(raw_count_per_week: float) -> int:
    """How many weeks between sessions when raw_count_per_week < threshold.
    E.g. 0.3 sess/wk → ceil(1/0.3) = 4 weeks between sessions. Floors at 2."""
    if raw_count_per_week <= 0:
        return 0
    return max(2, math.ceil(1.0 / raw_count_per_week))


def _allocate_discipline(
    discipline_id: str,
    discipline_name: str,
    target_hours: float,
    week_in_phase: int,
) -> DisciplineAllocation:
    """Convert per-discipline weekly hours into a session count, honoring the
    maintenance-cadence rule for sub-0.5-sessions/week disciplines."""
    typical_h = _typical_session_hours(discipline_id)
    typical_min = int(round(typical_h * 60))
    raw_count = target_hours / typical_h if typical_h > 0 else 0.0

    if raw_count <= 0:
        return DisciplineAllocation(
            discipline_id=discipline_id,
            discipline_name=discipline_name,
            sessions_this_week=0,
            typical_session_minutes=typical_min,
            target_hours_this_week=target_hours,
        )

    if raw_count < _MAINTENANCE_CADENCE_THRESHOLD:
        cadence = _maintenance_cadence_weeks(raw_count)
        # week_in_phase is 1-indexed; emit a session when (week-1) % cadence == 0
        # so the first week of any phase always gets the maintenance session
        # and subsequent appearances repeat on the cadence.
        emit_this_week = ((week_in_phase - 1) % cadence) == 0
        return DisciplineAllocation(
            discipline_id=discipline_id,
            discipline_name=discipline_name,
            sessions_this_week=1 if emit_this_week else 0,
            typical_session_minutes=typical_min,
            target_hours_this_week=target_hours,
            cadence_note=f"maintenance: 1× every {cadence} weeks",
        )

    # Round to nearest int, floor at 1 (any non-trivial allocation gets ≥1 session).
    rounded = max(1, int(round(raw_count)))
    return DisciplineAllocation(
        discipline_id=discipline_id,
        discipline_name=discipline_name,
        sessions_this_week=rounded,
        typical_session_minutes=typical_min,
        target_hours_this_week=target_hours,
    )


def _intensity_mix(phase_name: str, total_cardio_sessions: int) -> IntensityMix:
    """Polarized split applied to the week's cardio session total. Floors hard
    at 1 when there's any cardio in a non-Base phase (otherwise Base/Taper at
    low counts emit zero hard — fine; the LLM keeps the placement freedom)."""
    if total_cardio_sessions <= 0 or phase_name not in _PHASE_INTENSITY_SPLIT:
        return IntensityMix(easy_count=total_cardio_sessions, hard_count=0)
    easy_pct, hard_pct = _PHASE_INTENSITY_SPLIT[phase_name]
    raw_hard = total_cardio_sessions * hard_pct
    hard_count = int(round(raw_hard))
    # In Build/Peak, ensure at least one hard session when there are 3+ cardio
    # sessions — polarized concentration matters at those phases.
    if phase_name in ("Build", "Peak") and hard_count == 0 and total_cardio_sessions >= 3:
        hard_count = 1
    hard_count = min(hard_count, total_cardio_sessions)
    return IntensityMix(
        easy_count=total_cardio_sessions - hard_count,
        hard_count=hard_count,
    )


def _race_sim_slot(
    phase_name: str,
    week_in_phase: int,
    phase_weeks: int | None,
    race_format: str | None,
    race_duration_h: float | None,
) -> RaceSimLongDay | None:
    """Per spec §5.2: continuous_multi_day race format gets a race-sim long day
    in each Peak week + Taper week 1. Duration is `min(8h, race_duration / 8)`;
    Taper-1 scales to 60% of that."""
    if race_format != "continuous_multi_day" or race_duration_h is None:
        return None
    if race_duration_h <= 0:
        return None
    peak_duration_h = min(_RACE_SIM_MAX_DURATION_HR, race_duration_h * _RACE_SIM_FRACTION_OF_RACE)
    if phase_name == "Peak":
        return RaceSimLongDay(
            phase_position="peak",
            duration_min=int(round(peak_duration_h * 60)),
        )
    if phase_name == "Taper" and week_in_phase == 1:
        return RaceSimLongDay(
            phase_position="taper_1",
            duration_min=int(round(peak_duration_h * _RACE_SIM_TAPER_SCALE * 60)),
        )
    return None


def build_session_grid(
    layer2a: Layer2APayload | None,
    phase_structure: PhaseStructure | None,
    phase_name: str,
    week_in_phase: int,
    capacity_hours: float | None,
    *,
    race_format: str | None = None,
    race_duration_h: float | None = None,
) -> SessionGrid:
    """The §5.1 deterministic grid for one `(phase, week_in_phase)`. Returns an
    empty-but-typed `SessionGrid` when inputs are insufficient (graceful
    degradation — caller renders nothing rather than fabricating a target)."""
    bands = phase_week_volume_bands_hours(
        layer2a, phase_name, week_in_phase, phase_structure, capacity_hours
    )

    allocations: list[DisciplineAllocation] = []
    if layer2a is not None and bands:
        # Sort by load_weight desc (highest-priority discipline first) so the
        # rendered grid mirrors the existing prompt's discipline order.
        included = [
            d for d in layer2a.disciplines
            if d.inclusion == "included" and d.discipline_id in bands
        ]
        included.sort(key=lambda d: d.load_weight.value, reverse=True)
        for d in included:
            lo, hi = bands[d.discipline_id]
            target = (lo + hi) / 2.0
            allocations.append(
                _allocate_discipline(
                    discipline_id=d.discipline_id,
                    discipline_name=d.discipline_name,
                    target_hours=target,
                    week_in_phase=week_in_phase,
                )
            )

    # Count cardio sessions for intensity mix. Strength is excluded —
    # the polarized split is a cardio-aerobic-system concept.
    cardio_total = sum(
        a.sessions_this_week for a in allocations if a.discipline_id != "strength"
    )
    intensity = _intensity_mix(phase_name, cardio_total)

    # Race-sim slot requires phase_weeks for the Taper-week-1 check.
    phase_weeks: int | None = None
    if phase_structure is not None:
        for ph in phase_structure.phases:
            if ph.phase_name == phase_name:
                phase_weeks = ph.weeks
                break
    race_sim = _race_sim_slot(
        phase_name=phase_name,
        week_in_phase=week_in_phase,
        phase_weeks=phase_weeks,
        race_format=race_format,
        race_duration_h=race_duration_h,
    )

    return SessionGrid(
        phase_name=phase_name,
        week_in_phase=week_in_phase,
        weekly_capacity_hours=float(capacity_hours or 0),
        discipline_allocations=allocations,
        intensity_mix=intensity,
        race_sim_long_day=race_sim,
    )


__all__ = [
    "DisciplineAllocation",
    "IntensityMix",
    "RaceSimLongDay",
    "SessionGrid",
    "build_session_grid",
]
