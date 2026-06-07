"""Deterministic per-week training grid — Track 2 slices 2b + 2c (§5.1–§5.4
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

Slice 2b.2 (§5.1.1 / D11) adds the session-count ceiling:
  - `apply_session_ceiling(...)` caps the week's total session count at a
    deterministic, athlete-controlled ceiling derived from available days
    (`peak_sessions_max` default 10 / `two_a_day_preference`), scaled per phase
    and hard-clamped to 2 × available_days. Over-ceiling weeks shed the
    lowest-priority disciplines first (rotating them onto lighter weeks). Fixes
    the cold-PGE plan #60 failure (14 sessions for a 6-day athlete → unschedulable
    under the two_per_day invariant). The athlete owns their rest days
    (`daily_availability_windows`); there is no separate rest-count expectation.

Cache surface: pure function of (layer2a, phase_structure, phase, week_in_phase,
capacity_hours, race_format, race_duration_h). No new key surface beyond what
`periodization` + `validator.phase_week_volume_bands_hours` already contribute.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
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


# ─── Session-count ceiling (§5.1.1, D11) ────────────────────────────────────

# Athlete two-a-day preference → sessions per available training day at Peak.
# Module constants per spec §5.1.1 (D-8, tunable). `never` = strictly one-a-day;
# `regularly` ≈ near the 2/day ceiling.
_TWO_A_DAY_DENSITY: dict[str, float] = {
    "never": 1.0,
    "occasionally": 1.5,
    "regularly": 1.85,
}
_DEFAULT_TWO_A_DAY_PREFERENCE = "occasionally"

# Default Peak weekly-session ceiling when the athlete hasn't set one. The
# two_a_day_preference UI writes this value; the number is the source of truth.
_DEFAULT_PEAK_SESSIONS_MAX = 10

# Per-phase scale on the Peak ceiling. Near-flat: endurance frequency is roughly
# stable across phases (the volume_band + §5.3 polarized split carry the
# periodization); the taper cuts volume, not session count (Mujika & Padilla 2003).
_PHASE_SESSION_SCALE: dict[str, float] = {
    "Base": 0.90,
    "Build": 1.00,
    "Peak": 1.00,
    "Taper": 0.85,
}

# Availability fallback when neither available_days_per_week nor any enabled
# daily_availability_windows is set: assume the whole week is open (Andy, D-7).
_DEFAULT_AVAILABLE_DAYS = 7


def resolve_available_days(layer1_payload: dict | None) -> int:
    """Resolve the athlete's available training days/week for the ceiling:
    `available_days_per_week` if set; else the count of enabled
    `daily_availability_windows`; else all 7 (spec §5.1.1, D-7)."""
    if not layer1_payload:
        return _DEFAULT_AVAILABLE_DAYS
    avail = layer1_payload.get("available_days_per_week")
    if isinstance(avail, int) and avail > 0:
        return avail
    windows = layer1_payload.get("daily_availability_windows") or []
    enabled = sum(
        1 for w in windows
        if (w.get("enabled") if isinstance(w, dict) else getattr(w, "enabled", False))
    )
    return enabled if enabled > 0 else _DEFAULT_AVAILABLE_DAYS


def _peak_ceiling(
    available_days: int,
    two_a_day_preference: str | None,
    peak_sessions_max: int | None,
) -> int:
    """The Peak weekly-session ceiling, hard-clamped to 2 × available_days.
    `peak_sessions_max` is authoritative (default 10); when absent it derives
    from `two_a_day_preference` via the density map; when both are absent it
    falls back to the default."""
    d = max(1, available_days)
    if peak_sessions_max is not None:
        ceiling = peak_sessions_max
    elif two_a_day_preference is not None:
        density = _TWO_A_DAY_DENSITY.get(
            two_a_day_preference, _TWO_A_DAY_DENSITY[_DEFAULT_TWO_A_DAY_PREFERENCE]
        )
        ceiling = round(density * d)
    else:
        ceiling = _DEFAULT_PEAK_SESSIONS_MAX
    return max(1, min(int(ceiling), 2 * d))


def phase_session_ceiling(
    phase_name: str,
    available_days: int,
    two_a_day_preference: str | None = None,
    peak_sessions_max: int | None = None,
) -> int:
    """Deterministic weekly session ceiling for `(phase, available_days)`: the
    Peak ceiling scaled by the phase factor, hard-clamped to 2 × available_days."""
    d = max(1, available_days)
    peak = _peak_ceiling(d, two_a_day_preference, peak_sessions_max)
    scale = _PHASE_SESSION_SCALE.get(phase_name, 1.0)
    return max(1, min(round(peak * scale), 2 * d))


def apply_session_ceiling(
    allocations: list[DisciplineAllocation],
    phase_name: str,
    available_days: int,
    two_a_day_preference: str | None = None,
    peak_sessions_max: int | None = None,
) -> list[DisciplineAllocation]:
    """Cap the week's total session count at the deterministic phase ceiling
    (§5.1.1). `allocations` MUST be in priority order (highest `load_weight`
    first — `build_session_grid` sorts them so). Sheds lowest-priority sessions
    first: trims multi-session disciplines down toward 1 before dropping any
    discipline to 0 (rotated out, with a cadence note). Returns the input list
    unchanged (identity-preserving) when nothing needs shedding."""
    ceiling = phase_session_ceiling(
        phase_name, available_days, two_a_day_preference, peak_sessions_max
    )
    counts = [a.sessions_this_week for a in allocations]
    total = sum(counts)
    if total <= ceiling:
        return allocations

    # Phase 1: trim multi-session disciplines (>1), lowest-priority (tail) first.
    while total > ceiling and any(c > 1 for c in counts):
        for i in range(len(counts) - 1, -1, -1):
            if counts[i] > 1:
                counts[i] -= 1
                total -= 1
                break
    # Phase 2: still over → drop lowest-priority single-session disciplines to 0
    # (they rotate back in on a lighter week via the maintenance-cadence note).
    while total > ceiling and any(c == 1 for c in counts):
        for i in range(len(counts) - 1, -1, -1):
            if counts[i] == 1:
                counts[i] = 0
                total -= 1
                break

    out: list[DisciplineAllocation] = []
    for a, c in zip(allocations, counts):
        if c == a.sessions_this_week:
            out.append(a)
        elif c == 0:
            out.append(replace(
                a,
                sessions_this_week=0,
                cadence_note="deferred — weekly capacity ceiling; rotates in on a lighter week",
            ))
        else:
            out.append(replace(a, sessions_this_week=c))
    return out


def build_session_grid(
    layer2a: Layer2APayload | None,
    phase_structure: PhaseStructure | None,
    phase_name: str,
    week_in_phase: int,
    capacity_hours: float | None,
    *,
    race_format: str | None = None,
    race_duration_h: float | None = None,
    available_days: int | None = None,
    two_a_day_preference: str | None = None,
    peak_sessions_max: int | None = None,
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

    # §5.1.1 ceiling — cap the weekly session total to a schedulable, athlete-
    # controlled number before counting cardio for the intensity mix. Applied
    # only when available_days is known (callers in the synthesis path resolve
    # it via resolve_available_days; bare unit callers pass None → no cap).
    if allocations and available_days is not None:
        allocations = apply_session_ceiling(
            allocations,
            phase_name,
            available_days,
            two_a_day_preference,
            peak_sessions_max,
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
    "apply_session_ceiling",
    "build_session_grid",
    "phase_session_ceiling",
    "resolve_available_days",
]
