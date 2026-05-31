"""Layer 4 — `phase_structure_from_3b()` helper per `Layer4_Spec.md` §6.1.

Pure-function helper that decomposes a Layer 3B periodization shape into an
ordered list of `PhaseSpec` rows with concrete date ranges.

Used by:

- **Pattern A** (`plan_create` + `plan_refresh` T3 cross-phase) — drives the
  per-phase synthesis loop (Step 4f, future).
- **Step 4d T3 dispatch** — drives intra-phase-vs-cross-phase detection in
  `llm_layer4_plan_refresh`. When the refresh scope falls entirely inside one
  phase, Pattern B is used; otherwise Pattern A activates.

Open-ended-mode horizon defaults to 12 weeks (`Layer4_Spec.md` §6.1 v1
default — "one mesocycle rolling forward"). Event-mode callers can pass
`total_weeks` explicitly when the on-disk `Layer3BPayload` doesn't carry
`time_to_event_weeks` (forward-pointer; the typed payload landed without
this field — see context.py).

The §5.4 default intensity distributions used here are the v1 calibration
per Andy 2026-05-16 session-3: Base 80/15/5, Build 70/20/10, Peak 70/20/10
(shares Build's shape; race-pace differentiation surfaces via
`race_pace_specific` per-session flag rather than zone-distribution shift),
Taper 75/15/10.

The intended_volume_band is a forward-pointer to 2A `phase_load_bands`
which is per-discipline. The §7.6 `PhaseSpec.intended_volume_band` is a
single `(low, high)` tuple typed on `payload.py`. v1 surfaces a sentinel
(0.0, 0.0) when the 2A payload isn't available at helper-call time; the
synthesizer reads the band from the 2A payload directly during prompt
rendering. The helper's job is the phase decomposition; band-population is
the caller's concern.
"""

from __future__ import annotations

from datetime import date as _date_type, timedelta
from typing import Literal

from layer4.context import Layer3BPayload
from layer4.errors import Layer4InputError
from layer4.payload import PhaseSpec, PhaseStructure, SynthesisMetadata


PhaseName = Literal["Base", "Build", "Peak", "Taper"]
_PHASE_ORDER: tuple[PhaseName, ...] = ("Base", "Build", "Peak", "Taper")


# Per `Layer4_Spec.md` §6.1 per-mode proportions:
_MODE_PROPORTIONS: dict[
    Literal["standard", "compressed", "extended"],
    dict[PhaseName, float],
] = {
    "standard": {"Base": 0.50, "Build": 0.30, "Peak": 0.15, "Taper": 0.05},
    "compressed": {"Base": 0.30, "Build": 0.35, "Peak": 0.25, "Taper": 0.10},
    "extended": {"Base": 0.60, "Build": 0.25, "Peak": 0.10, "Taper": 0.05},
}


# Per `Layer4_Spec.md` §5.4 v1 intensity-distribution calibration:
_INTENDED_INTENSITY_DISTRIBUTION: dict[PhaseName, dict[str, float]] = {
    "Base": {"Z1-Z2": 0.80, "Z3": 0.15, "Z4-Z5": 0.05},
    "Build": {"Z1-Z2": 0.70, "Z3": 0.20, "Z4-Z5": 0.10},
    "Peak": {"Z1-Z2": 0.70, "Z3": 0.20, "Z4-Z5": 0.10},
    "Taper": {"Z1-Z2": 0.75, "Z3": 0.15, "Z4-Z5": 0.10},
}


_OPEN_ENDED_DEFAULT_TOTAL_WEEKS = 12


def _zero_synthesis_metadata() -> SynthesisMetadata:
    """Placeholder synthesis metadata for phase rows that haven't yet been
    synthesized. `phase_structure_from_3b()` returns the decomposition
    BEFORE any per-phase synthesis call has run; the orchestrator overwrites
    each `PhaseSpec.synthesis_metadata` after the corresponding synthesizer
    call completes. v1 helper emits a zero-valued placeholder so the
    `PhaseSpec` model construction succeeds (the field is required at the
    pydantic level)."""
    return SynthesisMetadata(
        model="(unsynthesized)",
        temperature=0.0,
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
        retries_used=0,
        cap_hit=False,
    )


def _allocate_weeks_standard(
    mode: Literal["standard", "compressed", "extended"],
    total_weeks: int,
    start_phase: PhaseName,
    terminal_phase_min_weeks: int = 0,
) -> dict[PhaseName, int]:
    """Per `Layer4_Spec.md` §6.1: when `start_phase != 'Base'`, the skipped
    earlier phases' percentages are dropped; remaining phases keep their
    relative proportions and re-normalize to fit `total_weeks`. Proportions
    round to whole weeks; remainder allocated to Base if Base is in the set,
    otherwise to the earliest remaining phase.

    `terminal_phase_min_weeks` (#334 amendment 2026-05-31, event mode = 2):
    the terminal phase (the one ending on `scope_end_date` — last in the
    remaining set, Taper for a Base-start plan) is rounded *up* to this
    minimum so the §6.1-budgeted Taper survives proportional rounding to drive
    the Decision-4 race-week machinery (it's a taper week + the race week). The
    shortfall is reclaimed one week at a time from a non-terminal phase (Base
    first when present, else the largest remaining), never driving a preceding
    phase below 1 week — so `sum == total_weeks` holds. On a horizon too small
    to reach the minimum without starving a preceding phase, the terminal phase
    keeps whatever remains (the floor is a target, not an invariant)."""
    proportions = _MODE_PROPORTIONS[mode]
    start_idx = _PHASE_ORDER.index(start_phase)
    remaining = _PHASE_ORDER[start_idx:]
    remaining_sum = sum(proportions[p] for p in remaining)
    if remaining_sum <= 0:
        raise Layer4InputError(
            "periodization_shape_unusable",
            detail=f"degenerate remaining proportions for start_phase={start_phase}",
        )

    raw = {p: total_weeks * proportions[p] / remaining_sum for p in remaining}
    rounded = {p: int(raw[p]) for p in remaining}
    allocated = sum(rounded.values())
    remainder = total_weeks - allocated

    if remainder > 0:
        # Per spec: remainder to Base (most flexible) when Base is in the
        # remaining set; otherwise to the earliest remaining phase.
        target = "Base" if "Base" in remaining else remaining[0]
        rounded[target] += remainder

    # #334: float the terminal phase up to its minimum, reclaiming from
    # non-terminal phases one week at a time (Base first, else largest) without
    # driving any preceding phase below 1 week.
    terminal = remaining[-1]
    while rounded[terminal] < terminal_phase_min_weeks:
        donors = [p for p in remaining if p != terminal and rounded[p] > 1]
        if not donors:
            break  # horizon too small — terminal keeps what it has
        if "Base" in donors:
            donor = "Base"
        else:
            # largest remaining; tie-break to the earlier (more flexible) phase
            donor = max(donors, key=lambda p: (rounded[p], -remaining.index(p)))
        rounded[donor] -= 1
        rounded[terminal] += 1

    return rounded


def _allocate_weeks_custom(
    phase_weeks: dict[PhaseName, int],
    start_phase: PhaseName,
) -> dict[PhaseName, int]:
    """Per `Layer4_Spec.md` §6.1: custom mode uses `phase_weeks` verbatim.
    Filters to phases at or after `start_phase` (earlier phases dropped per
    the standard start_phase handling)."""
    start_idx = _PHASE_ORDER.index(start_phase)
    remaining = _PHASE_ORDER[start_idx:]
    out: dict[PhaseName, int] = {}
    for p in remaining:
        weeks = phase_weeks.get(p, 0)
        if weeks > 0:
            out[p] = weeks
    if not out:
        raise Layer4InputError(
            "periodization_shape_unusable",
            detail=(
                f"custom phase_weeks has no positive entries at or after "
                f"start_phase={start_phase}: {phase_weeks!r}"
            ),
        )
    return out


def phase_structure_from_3b(
    layer3b_payload: Layer3BPayload,
    plan_start_date: _date_type,
    total_weeks: int | None = None,
) -> PhaseStructure:
    """Decompose `Layer3BPayload.periodization_shape` into a `PhaseStructure`
    with concrete `[start_date, end_date]` ranges per phase, starting from
    `plan_start_date` + `start_phase`.

    Per `Layer4_Spec.md` §6.1:

    - Per-mode proportions (standard / compressed / extended) applied to
      `total_weeks` for the phases the athlete still needs to traverse.
    - Custom mode uses `phase_weeks` verbatim.
    - `start_phase != 'Base'`: earlier phases dropped; remaining phases
      re-normalize.
    - Proportions round to whole weeks; remainder allocated to Base (or
      earliest remaining phase if Base skipped).

    Arguments:

    - `layer3b_payload`: the 3B output. Drives mode + start_phase + (when
      custom) phase_weeks. Open-ended-mode horizon defaults to 12 weeks
      unless `total_weeks` is supplied.
    - `plan_start_date`: when phase 0 starts. Per §6.1 "orchestrator-supplied".
      For T3 refresh, this is the date the parent plan was first synthesized.
    - `total_weeks`: optional override for the horizon. Defaults to 12 in
      open-ended mode (v1 — `Layer4_Spec.md` §6.1 default). In event mode the
      caller should pass `(event_date - plan_start_date).days // 7` until the
      `Layer3BPayload.time_to_event_weeks` field lands.

    Returns a `PhaseStructure` with `phases` ordered Base→Build→Peak→Taper
    (subset starting from `start_phase`), `total_weeks` set, and
    `derived_from` reflecting the mode origin.

    Per `Layer4_Spec.md` §7.6, each `PhaseSpec.synthesis_metadata` is
    required; this helper emits a zero-valued placeholder per
    `_zero_synthesis_metadata()`. The orchestrator overwrites each entry
    after the corresponding synthesizer call completes.
    """
    shape = layer3b_payload.periodization_shape
    start_phase = shape.start_phase
    mode = shape.mode

    if mode == "custom":
        assert shape.phase_weeks is not None  # pydantic invariant
        allocation = _allocate_weeks_custom(shape.phase_weeks, start_phase)
    else:
        if total_weeks is None:
            total_weeks = _OPEN_ENDED_DEFAULT_TOTAL_WEEKS
        if total_weeks <= 0:
            raise Layer4InputError(
                "periodization_shape_unusable",
                detail=f"total_weeks must be positive (got {total_weeks})",
            )
        # #334: event mode (time_to_event_weeks present) floors the terminal
        # phase at 2 weeks (taper week + race week) so the race-week brief +
        # Taper coaching_flags have a phase to attach to. Open-ended mode has
        # no race-day boundary, so no floor.
        terminal_phase_min_weeks = (
            2 if layer3b_payload.time_to_event_weeks is not None else 0
        )
        allocation = _allocate_weeks_standard(
            mode, total_weeks, start_phase, terminal_phase_min_weeks
        )

    actual_total_weeks = sum(allocation.values())

    phases: list[PhaseSpec] = []
    cursor = plan_start_date
    for phase_name in _PHASE_ORDER:
        weeks = allocation.get(phase_name, 0)
        if weeks <= 0:
            continue
        end_date = cursor + timedelta(days=weeks * 7 - 1)
        phases.append(
            PhaseSpec(
                phase_name=phase_name,
                start_date=cursor,
                end_date=end_date,
                weeks=weeks,
                intended_volume_band=(0.0, 0.0),
                intended_intensity_distribution=_INTENDED_INTENSITY_DISTRIBUTION[
                    phase_name
                ],
                synthesis_metadata=_zero_synthesis_metadata(),
            )
        )
        cursor = end_date + timedelta(days=1)

    derived_from: Literal[
        "3b_standard", "3b_compressed", "3b_extended", "3b_custom", "layer4_override"
    ] = (
        "3b_custom"
        if mode == "custom"
        else (
            "3b_standard"
            if mode == "standard"
            else ("3b_compressed" if mode == "compressed" else "3b_extended")
        )
    )

    return PhaseStructure(
        phases=phases,
        total_weeks=actual_total_weeks,
        derived_from=derived_from,
    )


def phase_for_date(
    phase_structure: PhaseStructure, target_date: _date_type
) -> PhaseSpec | None:
    """Return the `PhaseSpec` whose `[start_date, end_date]` contains
    `target_date`, or None when the date falls outside every phase's window.

    Used by the T3 dispatcher in `plan_refresh.py` to determine whether
    `refresh_scope_start` and `refresh_scope_end` fall inside the same phase
    (intra-phase → Pattern B) or different phases / outside the plan
    horizon (cross-phase → Pattern A, currently raises pending Step 4f)."""
    for phase in phase_structure.phases:
        if phase.start_date <= target_date <= phase.end_date:
            return phase
    return None


def scope_spans_phase_boundary(
    phase_structure: PhaseStructure,
    scope_start: _date_type,
    scope_end: _date_type,
) -> bool:
    """True iff `[scope_start, scope_end]` straddles at least one
    `PhaseStructure.phases[].end_date` boundary OR either endpoint falls
    outside the plan horizon (which is treated as cross-phase since the
    plan-create scope was longer and the unseen-future-phase is a different
    phase than wherever scope_start lies)."""
    if scope_start > scope_end:
        raise ValueError(
            f"scope_start={scope_start.isoformat()} > "
            f"scope_end={scope_end.isoformat()}"
        )
    phase_at_start = phase_for_date(phase_structure, scope_start)
    phase_at_end = phase_for_date(phase_structure, scope_end)
    if phase_at_start is None or phase_at_end is None:
        return True
    return phase_at_start.phase_name != phase_at_end.phase_name


__all__ = [
    "phase_structure_from_3b",
    "phase_for_date",
    "scope_spans_phase_boundary",
]
