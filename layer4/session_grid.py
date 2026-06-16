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
from datetime import date as _date, timedelta
from typing import Literal

from layer4.context import Layer2APayload
from layer4.payload import PhaseStructure
from layer4.validator import (
    _STRENGTH_SESSIONS_PER_WEEK as _STRENGTH_DOSE_PER_WEEK,
    phase_week_volume_bands_hours,
)

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
class SessionTypeSplit:
    """Per-discipline typing of the week's sessions into purpose slots (#624
    Slice 2). Binds to the Slice-1 surface routing: `long` is the LSD aerobic
    cornerstone (primary discipline, phase-gated) and `easy` sessions are
    aerobic — both go on the discipline's aerobic surface; `quality` are the
    hard sessions — placed on the vert/technical surface (the LLM matches each
    quality session's intent to vert-vs-technical from `surface_routes`). The
    counts are deterministic; sum(quality) == the week `IntensityMix.hard_count`
    and sum(long+easy) == `easy_count`, so the per-discipline typing and the
    week-level polarized mix are consistent by construction."""

    long: int
    easy: int
    quality: int

    @property
    def total(self) -> int:
        return self.long + self.easy + self.quality


@dataclass(frozen=True)
class DisciplineAllocation:
    """One discipline's per-week session count + cadence reasoning."""

    discipline_id: str
    discipline_name: str
    sessions_this_week: int
    typical_session_minutes: int
    target_hours_this_week: float  # mid of `phase_week_volume_bands_hours` band
    cadence_note: str | None = None  # "maintenance: 1× every 3 weeks" when sub-threshold
    # #624 Slice 2 — per-discipline long/easy/quality typing (cardio only; None
    # for strength + zero-session allocations). Set in `build_session_grid`.
    session_types: SessionTypeSplit | None = None


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
    # Rule #15 — the strength-saturation cap's decision line for this (phase,
    # week), or None when the cap didn't fire. The caller prints it.
    saturation_note: str | None = None


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


def _type_sessions(
    allocations: list[DisciplineAllocation],
    phase_name: str,
    intensity: IntensityMix,
) -> list[DisciplineAllocation]:
    """Type each cardio discipline's sessions into long/easy/quality slots (#624
    Slice 2), binding the surface routing to deterministic per-slot counts.

    The week-level `intensity.hard_count` is the authority on how many quality
    (hard) sessions the week carries; it is distributed across the cardio
    disciplines proportional to their session counts (largest-remainder, capped
    at each discipline's count) so sum(quality) == hard_count exactly. Each
    discipline's remaining (aerobic) sessions are `easy`, except the primary
    (highest-load-weight) discipline carves one `long` LSD cornerstone in every
    phase but Taper. Strength + zero-session allocations are left untyped (None).

    Returns the input list with `session_types` set on each cardio allocation
    (identity-preserving for the strength/zero rows)."""
    cardio = [
        a for a in allocations
        if a.discipline_id != "strength" and a.sessions_this_week > 0
    ]
    if not cardio:
        return allocations

    total_cardio = sum(a.sessions_this_week for a in cardio)
    # Distribute the week hard_count proportional to each discipline's session
    # count via largest-remainder, capped at the discipline's own count.
    hard_total = min(intensity.hard_count, total_cardio)
    quotas = {
        a.discipline_id: hard_total * a.sessions_this_week / total_cardio
        for a in cardio
    }
    quality_by_id = {a.discipline_id: int(quotas[a.discipline_id]) for a in cardio}
    remaining = hard_total - sum(quality_by_id.values())
    # Hand out the remaining hard sessions to the largest fractional remainders,
    # skipping any discipline already at its session cap.
    for a in sorted(
        cardio,
        key=lambda a: quotas[a.discipline_id] - int(quotas[a.discipline_id]),
        reverse=True,
    ):
        if remaining <= 0:
            break
        if quality_by_id[a.discipline_id] < a.sessions_this_week:
            quality_by_id[a.discipline_id] += 1
            remaining -= 1

    primary_id = cardio[0].discipline_id  # allocations are load-weight-sorted desc
    out: list[DisciplineAllocation] = []
    for a in allocations:
        if a.discipline_id == "strength" or a.sessions_this_week <= 0:
            out.append(a)
            continue
        quality = quality_by_id[a.discipline_id]
        aerobic = a.sessions_this_week - quality
        long = 1 if (a.discipline_id == primary_id and phase_name != "Taper" and aerobic >= 1) else 0
        out.append(replace(
            a,
            session_types=SessionTypeSplit(long=long, easy=aerobic - long, quality=quality),
        ))
    return out


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


def placeable_days_in_week(
    available_days: int,
    layer1_payload: dict | None,
    week_start: _date,
    week_end: _date,
    cutoff_date: _date | None,
) -> int:
    """Race-week-aware truncation of the resolved weekly `available_days` to the
    days of THIS calendar week that can still hold a session.

    The session-count ceiling (`apply_session_ceiling`) clamps a week to
    `2 × available_days`, but `available_days` is the athlete's *nominal* weekly
    availability — it doesn't know the final taper week is cut short by the race.
    Without this, the ceiling permits more sessions than there are placeable days,
    the synthesizer can't lay them out at ≤2/day, every payload-validation pass
    fails (`Layer4Payload._check_two_per_day`), and the block exhausts its budget
    and stalls (the plan-72 failure mode). Feeding the *per-week* placeable-day
    count in makes the deterministic `2 × days` clamp a real ≤2/day feasibility
    guarantee instead of resting on the post-hoc validator.

    A day is placeable when it is on/before `cutoff_date` (the caller sets this to
    the last trainable day before the race — race day and the immediate pre-race
    rest day excluded) and, when per-day windows are on file, an enabled weekday.
    Returns `min(available_days, <placeable count>)`, so a normal mid-plan week is
    returned unchanged and only the race-adjacent week shrinks. `cutoff_date is
    None` (open-ended / no race) leaves `available_days` untouched."""
    # Fast path: open-ended plan, or the whole week is before the cutoff → no
    # truncation, identical to pre-existing behaviour for every non-final week.
    if cutoff_date is None or week_end <= cutoff_date:
        return available_days
    enabled_dows = {
        (w.get("day_of_week") if isinstance(w, dict) else getattr(w, "day_of_week", None))
        for w in ((layer1_payload or {}).get("daily_availability_windows") or [])
        if (w.get("enabled") if isinstance(w, dict) else getattr(w, "enabled", False))
    }
    placeable = 0
    d = week_start
    while d <= week_end:
        if d <= cutoff_date and (not enabled_dows or d.strftime("%a") in enabled_dows):
            placeable += 1
        d += timedelta(days=1)
    return min(available_days, placeable)


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


# ─── Strength-saturation cap (§7 WS-E2) ─────────────────────────────────────

# Headroom over the per-phase programmed strength dose for FAILOVER strength
# (terrain/craft-infeasible cardio composed as a strength substitution). Total
# strength/week is capped at `dose + this`; excess failover is reallocated to
# feasible disciplines rather than crowding the week with strength (Andy §7:
# "Cap = dose + 2 total strength/week"). The deterministic crash-guard
# (`per_phase._repair_strength_collisions`, #579) still backstops a same-day
# strength collision; this cap is the upstream periodization-quality guard.
_FAILOVER_STRENGTH_HEADROOM = 2

# A single feasible discipline may absorb at most this multiple of its own
# current weekly count from reallocated over-cap strength — Andy §7: "cap how
# much any one discipline can absorb … not dump it all on the nearest one." A
# multiplier of 1.0 means a discipline can at most DOUBLE in one reallocation
# pass; anything it can't absorb stays as (capped) strength rather than
# concentrating volume on one sport (the "3 running + 3 cycling → 6 running"
# failure mode). The split across absorbers is proportional to load_weight.
_REALLOCATION_ABSORB_MULTIPLE = 1.0

# Default load weight for an absorber whose 2A `load_weight.value` is None, so a
# weightless discipline still participates proportionally rather than being
# dropped from the reallocation.
_DEFAULT_ABSORB_WEIGHT = 1.0

# Feasible tiers an absorber can be in (real trainable sessions). STRENGTH /
# REALLOCATE change or drop the session kind, so they are never absorbers.
_FEASIBLE_TIERS = frozenset({"exact", "proxy", "indoor"})


def apply_strength_saturation_cap(
    allocations: list[DisciplineAllocation],
    phase_name: str,
    feasibility_tiers: dict[str, str],
    discipline_weights: dict[str, float],
    skill_gated_ids: frozenset[str] | set[str] = frozenset(),
) -> tuple[list[DisciplineAllocation], str]:
    """Cap weekly FAILOVER strength at `dose + _FAILOVER_STRENGTH_HEADROOM` and
    reallocate the excess to feasible disciplines, proportional to load_weight
    (§7 WS-E2). `allocations` MUST be priority-ordered (highest `load_weight`
    first — `build_session_grid` sorts them so).

    Volume-conserving: each trimmed over-cap strength session is MOVED to a
    feasible discipline 1:1 (never created or destroyed), so the §5.1.1 session
    ceiling already applied upstream is preserved. Excess that no feasible
    absorber can take (capacity exhausted, or no feasible candidate) STAYS as
    strength — never dropped (training time is preserved; the collision guard
    backstops any same-day clash).

    Scope: caps terrain/craft failover strength (the pv=69 saturation cause).
    Skill-gated disciplines (#336, a deliberate safety substitution) are neither
    trimmed nor used as absorbers — `skill_gated_ids` excludes them.

    Returns `(adjusted_allocations, log_detail)`; the detail is the Rule #15
    decision line the caller prints. Identity-preserving (returns the input list
    + an empty detail) when nothing needs capping.
    """
    dose = _STRENGTH_DOSE_PER_WEEK.get(phase_name)
    if dose is None:
        return allocations, ""

    # The programmed strength dose (`dose`) is added by the synthesis prompt, not
    # the grid, so it is NOT in these allocations. Total strength = dose + grid
    # `strength` allocation (rare — strength is usually prompt-added, not a 2A
    # discipline) + failover. Capping total at `dose + headroom` therefore allows
    # `headroom - grid_strength` failover sessions — the dose cancels, so the
    # failover headroom is a flat +`_FAILOVER_STRENGTH_HEADROOM` in every phase.
    grid_strength = sum(
        a.sessions_this_week for a in allocations if a.discipline_id == "strength"
    )
    allowed_failover = max(0, _FAILOVER_STRENGTH_HEADROOM - grid_strength)

    def _is_failover(a: DisciplineAllocation) -> bool:
        return (
            a.discipline_id != "strength"
            and a.discipline_id not in skill_gated_ids
            and a.sessions_this_week > 0
            and feasibility_tiers.get(a.discipline_id) == "strength"
        )

    def _is_absorber(a: DisciplineAllocation) -> bool:
        # Feasible if explicitly in a real-session tier, OR carrying no terrain
        # constraint at all (absent from the map) and not skill-gated.
        tier = feasibility_tiers.get(a.discipline_id)
        return (
            a.discipline_id != "strength"
            and a.discipline_id not in skill_gated_ids
            and a.sessions_this_week > 0
            and (tier in _FEASIBLE_TIERS or tier is None)
        )

    failover_total = sum(a.sessions_this_week for a in allocations if _is_failover(a))
    over = failover_total - allowed_failover
    if over <= 0:
        return allocations, ""

    # Absorber capacity: each feasible discipline takes at most `multiple × its
    # current count` (the variety cap). total_capacity bounds how much we can move.
    abs_idx = [i for i, a in enumerate(allocations) if _is_absorber(a)]
    capacity = {
        i: int(math.floor(allocations[i].sessions_this_week * _REALLOCATION_ABSORB_MULTIPLE))
        for i in abs_idx
    }
    total_capacity = sum(capacity.values())
    to_move = min(over, total_capacity)
    if to_move <= 0:
        # Over the cap but nowhere feasible to put the volume → leave as strength.
        return allocations, (
            f"saturation: {phase_name} dose={dose} allowed_failover={allowed_failover} "
            f"failover={failover_total} over={over} moved=0 (no absorber capacity); "
            f"residual stays strength"
        )

    counts = [a.sessions_this_week for a in allocations]

    # ── 1. Trim `to_move` failover sessions, LOWEST priority first (tail). ────
    trims: dict[int, int] = {}
    moved = 0
    for i in range(len(allocations) - 1, -1, -1):
        if moved >= to_move:
            break
        if _is_failover(allocations[i]):
            take = min(counts[i], to_move - moved)
            if take:
                counts[i] -= take
                trims[i] = take
                moved += take

    # ── 2. Distribute the moved sessions across absorbers, proportional to ────
    #       load_weight (d'Hondt highest-averages — deterministic, respects the
    #       per-discipline capacity, spreads by priority).
    weights = {
        i: (discipline_weights.get(allocations[i].discipline_id) or _DEFAULT_ABSORB_WEIGHT)
        for i in abs_idx
    }
    adds: dict[int, int] = {i: 0 for i in abs_idx}
    for _ in range(moved):
        eligible = [i for i in abs_idx if adds[i] < capacity[i]]
        if not eligible:
            break
        # Highest weight / (already_assigned + 1); tie → higher weight, then
        # higher priority (lower index).
        best = max(eligible, key=lambda i: (weights[i] / (adds[i] + 1), weights[i], -i))
        adds[best] += 1
        counts[best] += 1

    # ── 3. Rebuild allocations with the adjusted counts + observability notes. ─
    out: list[DisciplineAllocation] = []
    for i, a in enumerate(allocations):
        if i in trims:
            note = f"strength capped at dose+{_FAILOVER_STRENGTH_HEADROOM} — {trims[i]} session(s) reallocated"
            out.append(replace(
                a,
                sessions_this_week=counts[i],
                cadence_note=f"{a.cadence_note}; {note}" if a.cadence_note else note,
            ))
        elif adds.get(i):
            note = f"+{adds[i]} session(s) reallocated from over-cap strength"
            out.append(replace(
                a,
                sessions_this_week=counts[i],
                cadence_note=f"{a.cadence_note}; {note}" if a.cadence_note else note,
            ))
        else:
            out.append(a)

    trim_str = ", ".join(
        f"{allocations[i].discipline_id}-{n}" for i, n in sorted(trims.items())
    )
    add_str = ", ".join(
        f"{allocations[i].discipline_id}+{adds[i]}" for i in abs_idx if adds[i]
    )
    detail = (
        f"saturation: {phase_name} dose={dose} allowed_failover={allowed_failover} "
        f"failover={failover_total} over={over} moved={moved} "
        f"residual={over - moved} trims=[{trim_str}] absorbs=[{add_str}]"
    )
    return out, detail


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
    strength_feasibility_tiers: dict[str, str] | None = None,
    skill_gated_ids: frozenset[str] | set[str] = frozenset(),
) -> SessionGrid:
    """The §5.1 deterministic grid for one `(phase, week_in_phase)`. Returns an
    empty-but-typed `SessionGrid` when inputs are insufficient (graceful
    degradation — caller renders nothing rather than fabricating a target).

    When `strength_feasibility_tiers` (discipline_id → feasibility tier) is
    supplied, the §7 WS-E2 saturation cap runs after the §5.1.1 ceiling: weekly
    failover strength is capped at `dose + 2` and the excess reallocated to
    feasible disciplines proportional to load_weight. Bare callers omit it → no
    cap (mirrors the `available_days`-gated ceiling)."""
    bands = phase_week_volume_bands_hours(
        layer2a, phase_name, week_in_phase, phase_structure, capacity_hours
    )

    allocations: list[DisciplineAllocation] = []
    discipline_weights: dict[str, float] = {}
    if layer2a is not None and bands:
        # Sort by load_weight desc (highest-priority discipline first) so the
        # rendered grid mirrors the existing prompt's discipline order.
        included = [
            d for d in layer2a.disciplines
            if d.inclusion == "included" and d.discipline_id in bands
        ]
        included.sort(key=lambda d: d.load_weight.value, reverse=True)
        discipline_weights = {d.discipline_id: d.load_weight.value for d in included}
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

    # §7 WS-E2 saturation cap — runs on the already-ceilinged allocations so it
    # rebalances strength within a schedulable week. Volume-conserving (moves
    # over-cap strength → feasible disciplines 1:1), so the ceiling holds.
    saturation_note: str | None = None
    if allocations and strength_feasibility_tiers is not None:
        allocations, _sat_detail = apply_strength_saturation_cap(
            allocations,
            phase_name,
            strength_feasibility_tiers,
            discipline_weights,
            skill_gated_ids,
        )
        saturation_note = _sat_detail or None

    # Count cardio sessions for intensity mix. Strength is excluded —
    # the polarized split is a cardio-aerobic-system concept.
    cardio_total = sum(
        a.sessions_this_week for a in allocations if a.discipline_id != "strength"
    )
    intensity = _intensity_mix(phase_name, cardio_total)

    # §5.1 Slice 2 — type each cardio discipline's sessions into long/easy/quality
    # so the surface routing binds to deterministic per-slot counts. Consistent
    # with the week-level mix by construction (sum(quality) == hard_count).
    allocations = _type_sessions(allocations, phase_name, intensity)

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
        saturation_note=saturation_note,
    )


__all__ = [
    "DisciplineAllocation",
    "IntensityMix",
    "RaceSimLongDay",
    "SessionGrid",
    "SessionTypeSplit",
    "apply_session_ceiling",
    "apply_strength_saturation_cap",
    "build_session_grid",
    "phase_session_ceiling",
    "placeable_days_in_week",
    "resolve_available_days",
]
