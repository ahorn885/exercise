"""Tests for `layer4/phase_structure.py` — `phase_structure_from_3b()` per
`Layer4_Spec.md` §6.1 + the `scope_spans_phase_boundary()` helper used by
T3 dispatch in `plan_refresh.py`."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from layer4.context import GoalViability, Layer3BPayload, PeriodizationShape
from layer4.errors import Layer4InputError
from layer4.phase_structure import (
    phase_for_date,
    phase_structure_from_3b,
    scope_spans_phase_boundary,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


_PLAN_START = date(2026, 1, 1)


def _layer3b(
    *,
    mode: str = "standard",
    start_phase: str = "Base",
    phase_weeks: dict[str, int] | None = None,
    time_to_event_weeks: int | None = None,
) -> Layer3BPayload:
    # #334: an event-mode payload carries time_to_event_weeks (top-level
    # mode='event'); that field is what phase_structure_from_3b keys off to
    # apply the >=2-week terminal-phase (Taper) floor. Open-ended payloads
    # leave it None (mode='no-event') and get no floor.
    top_mode = "event" if time_to_event_weeks is not None else "no-event"
    return Layer3BPayload(
        user_id=42,
        as_of=datetime(2026, 1, 1, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1500,
        input_tokens=3000,
        output_tokens=800,
        etl_version_set={"layer0": "v7"},
        mode=top_mode,  # type: ignore[arg-type]
        time_to_event_weeks=time_to_event_weeks,
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="solid base",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode=mode,  # type: ignore[arg-type]
            start_phase=start_phase,  # type: ignore[arg-type]
            phase_weeks=phase_weeks,  # type: ignore[arg-type]
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        hitl_surface=[],
        notable_observations=[],
    )


# ─── phase_structure_from_3b ─────────────────────────────────────────────────


class TestPhaseStructureStandardMode:
    def test_standard_12_weeks_from_base(self):
        """12-week standard: 0.05*12 = 0.6 → int=0 for Taper; phase is
        dropped. 0.15*12 = 1.8 → 1 Peak. 0.30*12 = 3.6 → 3 Build. Base = 6
        + remainder 2 = 8. Total 12 across surviving Base/Build/Peak."""
        ps = phase_structure_from_3b(_layer3b(mode="standard"), _PLAN_START)
        names = [p.phase_name for p in ps.phases]
        # Taper is dropped because the proportion math gives it 0 weeks at
        # 12-week horizon. Documented behavior.
        assert names == ["Base", "Build", "Peak"]
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert sum(weeks_by_phase.values()) == 12
        assert weeks_by_phase["Base"] >= 6

    def test_standard_20_weeks_from_base(self):
        """Cleaner 20-week test: 50/30/15/5 = 10/6/3/1."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase == {"Base": 10, "Build": 6, "Peak": 3, "Taper": 1}
        assert ps.total_weeks == 20
        assert ps.derived_from == "3b_standard"

    def test_standard_start_phase_build(self):
        """start_phase=Build: Base dropped; remaining {Build,Peak,Taper}
        re-normalize from {0.30, 0.15, 0.05} = 0.50 sum → 60/30/10 of total."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard", start_phase="Build"),
            _PLAN_START,
            total_weeks=10,
        )
        names = [p.phase_name for p in ps.phases]
        assert "Base" not in names
        assert names[0] == "Build"

    def test_standard_phases_chain_dates(self):
        """phases[i].end_date + 1d == phases[i+1].start_date."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        for prev, nxt in zip(ps.phases, ps.phases[1:]):
            assert prev.end_date + timedelta(days=1) == nxt.start_date


class TestPhaseStructureCompressedMode:
    def test_compressed_15_weeks(self):
        """Compressed: 30/35/25/10 of 15 = 4.5/5.25/3.75/1.5 →
        4/5/3/1 = 13; remainder 2 → Base = 6."""
        ps = phase_structure_from_3b(
            _layer3b(mode="compressed"), _PLAN_START, total_weeks=15
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert sum(weeks_by_phase.values()) == 15
        assert ps.derived_from == "3b_compressed"

    def test_compressed_no_zero_phases(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="compressed"), _PLAN_START, total_weeks=20
        )
        for p in ps.phases:
            assert p.weeks > 0


class TestPhaseStructureExtendedMode:
    def test_extended_proportions(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="extended"), _PLAN_START, total_weeks=20
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        # extended: 60/25/10/5 of 20 = 12/5/2/1 = 20 (exact, no remainder).
        assert weeks_by_phase == {"Base": 12, "Build": 5, "Peak": 2, "Taper": 1}
        assert ps.derived_from == "3b_extended"


class TestPhaseStructureCustomMode:
    def test_custom_verbatim(self):
        l3b = _layer3b(
            mode="custom",
            start_phase="Base",
            phase_weeks={"Base": 8, "Build": 4, "Peak": 2, "Taper": 2},
        )
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase == {"Base": 8, "Build": 4, "Peak": 2, "Taper": 2}
        assert ps.total_weeks == 16
        assert ps.derived_from == "3b_custom"

    def test_custom_with_start_phase_peak(self):
        """Earlier phases dropped per §6.1 start_phase handling."""
        l3b = _layer3b(
            mode="custom",
            start_phase="Peak",
            phase_weeks={"Base": 8, "Build": 4, "Peak": 2, "Taper": 2},
        )
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        names = [p.phase_name for p in ps.phases]
        assert names == ["Peak", "Taper"]
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase == {"Peak": 2, "Taper": 2}

    def test_custom_skips_zero_entries(self):
        l3b = _layer3b(
            mode="custom",
            start_phase="Base",
            phase_weeks={"Base": 8, "Build": 4, "Peak": 0, "Taper": 0},
        )
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        names = [p.phase_name for p in ps.phases]
        assert names == ["Base", "Build"]

    def test_custom_all_zero_raises(self):
        l3b = _layer3b(
            mode="custom",
            start_phase="Base",
            phase_weeks={"Base": 0, "Build": 0, "Peak": 0, "Taper": 0},
        )
        # Typed backstop (was a bare ValueError → raw 500). 3B's sanity loop
        # now catches this upstream and falls back to standard; this is the
        # defense-in-depth path for any other caller.
        with pytest.raises(Layer4InputError) as exc:
            phase_structure_from_3b(l3b, _PLAN_START)
        assert exc.value.code == "periodization_shape_unusable"


class TestPhaseStructureDefaults:
    def test_open_ended_defaults_to_12_weeks(self):
        ps = phase_structure_from_3b(_layer3b(mode="standard"), _PLAN_START)
        # standard / 12 weeks; remainder allocation puts Taper=0 (dropped)
        # so total is 12 across surviving phases.
        assert ps.total_weeks == 12

    def test_negative_total_weeks_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            phase_structure_from_3b(
                _layer3b(mode="standard"), _PLAN_START, total_weeks=0
            )
        assert exc.value.code == "periodization_shape_unusable"


class TestPhaseStructureEventModeTerminalFloor:
    """#334: in event mode the terminal phase (Taper) is floored at 2 weeks
    (a taper week + the race week) so the race-week brief + Taper coaching_flags
    have a phase to attach to. Shortfall reclaimed from non-terminal phases
    (Base first, else largest) without driving any below 1 week."""

    def test_pge_7_weeks_taper_survives(self):
        """The canonical #334 case: 7-week standard plan from Base. Pre-fix the
        0.05*7=0.35 Taper floored to 0 and the plan ended on Peak, a week short
        of the event. Now Taper >= 2; sum preserved at 7."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard", time_to_event_weeks=7),
            _PLAN_START,
            total_weeks=7,
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase.get("Taper", 0) >= 2
        assert sum(weeks_by_phase.values()) == 7
        # terminal phase ends on the plan's last day
        assert ps.phases[-1].phase_name == "Taper"

    def test_open_ended_7_weeks_taper_still_dropped(self):
        """Same horizon, but open-ended (no time_to_event_weeks) → no floor;
        Taper stays dropped per the unchanged proportional rounding."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=7
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase.get("Taper", 0) == 0
        assert sum(weeks_by_phase.values()) == 7

    def test_build_start_6_weeks_reclaims_without_starving(self):
        """Documented bug case: 6-week standard from Build gave Build5/Peak1/
        Taper0. Now Taper>=2, reclaimed from Build (largest), Peak stays >=1."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard", start_phase="Build", time_to_event_weeks=6),
            _PLAN_START,
            total_weeks=6,
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert "Base" not in weeks_by_phase
        assert weeks_by_phase["Taper"] >= 2
        assert weeks_by_phase["Peak"] >= 1
        assert sum(weeks_by_phase.values()) == 6

    def test_no_non_terminal_phase_driven_below_one_week(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard", time_to_event_weeks=7),
            _PLAN_START,
            total_weeks=7,
        )
        for p in ps.phases:
            if p.phase_name != "Taper":
                assert p.weeks >= 1

    def test_degenerate_horizon_target_not_invariant(self):
        """A 2-week plan from Peak can't give Taper 2 without starving Peak
        below 1 week — Taper keeps what remains (Peak1/Taper1), floor is a
        target not an invariant."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard", start_phase="Peak", time_to_event_weeks=2),
            _PLAN_START,
            total_weeks=2,
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase == {"Peak": 1, "Taper": 1}

    def test_taper_already_above_floor_unchanged(self):
        """20-week event plan: Taper already 1 from proportions... actually
        floored to 2; but a longer horizon where Taper >= 2 naturally is a
        no-op. Use 40 weeks: 0.05*40 = 2 exactly."""
        ps = phase_structure_from_3b(
            _layer3b(mode="standard", time_to_event_weeks=40),
            _PLAN_START,
            total_weeks=40,
        )
        weeks_by_phase = {p.phase_name: p.weeks for p in ps.phases}
        assert weeks_by_phase["Taper"] == 2
        assert sum(weeks_by_phase.values()) == 40


# ─── phase_for_date ──────────────────────────────────────────────────────────


class TestPhaseForDate:
    def test_date_inside_base(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        # Base = weeks 1-10 = days 0-69
        result = phase_for_date(ps, _PLAN_START + timedelta(days=5))
        assert result is not None
        assert result.phase_name == "Base"

    def test_date_at_phase_start(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        for p in ps.phases:
            assert phase_for_date(ps, p.start_date) is p

    def test_date_at_phase_end(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        for p in ps.phases:
            assert phase_for_date(ps, p.end_date) is p

    def test_date_before_plan_start_returns_none(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        assert phase_for_date(ps, _PLAN_START - timedelta(days=1)) is None

    def test_date_after_plan_end_returns_none(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        end = ps.phases[-1].end_date
        assert phase_for_date(ps, end + timedelta(days=1)) is None


# ─── scope_spans_phase_boundary ──────────────────────────────────────────────


class TestScopeSpansPhaseBoundary:
    def test_intra_phase_returns_false(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        # Both inside Base
        assert not scope_spans_phase_boundary(
            ps, _PLAN_START + timedelta(days=5), _PLAN_START + timedelta(days=30)
        )

    def test_cross_phase_returns_true(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        # Base ends day 69; Build starts day 70
        assert scope_spans_phase_boundary(
            ps, _PLAN_START + timedelta(days=65), _PLAN_START + timedelta(days=80)
        )

    def test_scope_starts_before_plan_returns_true(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        assert scope_spans_phase_boundary(
            ps, _PLAN_START - timedelta(days=5), _PLAN_START + timedelta(days=5)
        )

    def test_scope_ends_after_plan_returns_true(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        end = ps.phases[-1].end_date
        assert scope_spans_phase_boundary(
            ps, end - timedelta(days=5), end + timedelta(days=5)
        )

    def test_inverted_scope_raises(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        with pytest.raises(ValueError):
            scope_spans_phase_boundary(
                ps, _PLAN_START + timedelta(days=10), _PLAN_START + timedelta(days=5)
            )

    def test_single_day_intra_phase(self):
        ps = phase_structure_from_3b(
            _layer3b(mode="standard"), _PLAN_START, total_weeks=20
        )
        d = _PLAN_START + timedelta(days=15)
        assert not scope_spans_phase_boundary(ps, d, d)


__all__ = ["TestPhaseStructureStandardMode"]  # silence ruff
