"""Tests for `layer4.session_grid` — Track 2 slice 2b §5.1 / §5.2 / §5.3."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from layer4.context import (
    Layer2ADiscipline,
    Layer2APayload,
    PhaseLoadBands,
    RationaleMetadata,
    TrainingGapsSummary,
    WeightResult,
)
from layer4.payload import PhaseSpec, PhaseStructure, SynthesisMetadata
from layer4.session_grid import (
    DisciplineAllocation,
    IntensityMix,
    RaceSimLongDay,
    SessionGrid,
    build_session_grid,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _weight(value: float = 1.0) -> WeightResult:
    return WeightResult(value=value, source="system_default", system_default=value)


def _discipline(
    did: str,
    name: str,
    *,
    base_pct: tuple[float, float] = (10.0, 20.0),
    build_pct: tuple[float, float] = (15.0, 25.0),
    peak_pct: tuple[float, float] = (20.0, 30.0),
    taper_pct: tuple[float, float] = (8.0, 12.0),
    load_weight: float = 1.0,
    inclusion: str = "included",
) -> Layer2ADiscipline:
    return Layer2ADiscipline(
        discipline_id=did,
        discipline_name=name,
        inclusion=inclusion,  # type: ignore[arg-type]
        role="Primary",
        is_conditional=False,
        load_weight=_weight(load_weight),
        sleep_deprivation_relevant=False,
        rationale="test",
        phase_load=PhaseLoadBands(
            base_low=base_pct[0],
            base_high=base_pct[1],
            build_low=build_pct[0],
            build_high=build_pct[1],
            peak_low=peak_pct[0],
            peak_high=peak_pct[1],
            taper_low=taper_pct[0],
            taper_high=taper_pct[1],
            default_inclusion="included",
        ),
    )


def _layer2a(disciplines: list[Layer2ADiscipline]) -> Layer2APayload:
    return Layer2APayload(
        framework_sport="adventure_racing",
        etl_version_set={"layer0": "v7"},
        disciplines=disciplines,
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
            any_no_substitute=False,
            any_multi_substitute_candidate=False,
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            template_version="v1", generated_at="2026-06-06T00:00:00Z"
        ),
        # Per-phase weekly hour totals (low, high) — what's left of `capacity_hours`
        # after the phase_load percentages are renormalized.
        weekly_total_hours_by_phase={
            "Base": (8.0, 10.0),
            "Build": (10.0, 14.0),
            "Peak": (12.0, 16.0),
            "Taper": (5.0, 7.0),
        },
    )


def _phase_structure(phase_weeks: dict[str, int]) -> PhaseStructure:
    start = date.today()
    phases: list[PhaseSpec] = []
    cursor = start
    for phase_name, weeks in phase_weeks.items():
        end = cursor + timedelta(days=weeks * 7 - 1)
        phases.append(
            PhaseSpec(
                phase_name=phase_name,  # type: ignore[arg-type]
                start_date=cursor,
                end_date=end,
                weeks=weeks,
                intended_volume_band=(8.0, 14.0),
                intended_intensity_distribution={"easy": 0.8, "hard": 0.2},
                synthesis_metadata=SynthesisMetadata(
                    model="claude-sonnet-4-6",
                    temperature=0.2,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0,
                    retries_used=0,
                    cap_hit=False,
                ),
            )
        )
        cursor = end + timedelta(days=1)
    return PhaseStructure(
        phases=phases,
        total_weeks=sum(phase_weeks.values()),
        derived_from="3b_standard",
    )


# ─── §5.1 session counts ─────────────────────────────────────────────────────


class TestSessionCounts:
    def test_empty_inputs_returns_empty_grid(self):
        grid = build_session_grid(None, None, "Build", 1, None)
        assert isinstance(grid, SessionGrid)
        assert grid.discipline_allocations == []
        assert grid.intensity_mix == IntensityMix(easy_count=0, hard_count=0)

    def test_typical_count_for_dominant_discipline(self):
        """Trail run + MTB at 60/40 in a 12h Build week → trail run gets ~7h/wk
        at 1.25h typical = ~5-6 sessions."""
        l2a = _layer2a([
            _discipline(
                "trail_running",
                "Trail Running",
                base_pct=(50.0, 60.0),
                build_pct=(50.0, 60.0),
                peak_pct=(50.0, 60.0),
                taper_pct=(50.0, 60.0),
            ),
            _discipline(
                "mtb_outdoor",
                "MTB",
                base_pct=(30.0, 40.0),
                build_pct=(30.0, 40.0),
                peak_pct=(30.0, 40.0),
                taper_pct=(30.0, 40.0),
            ),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=12.0)

        assert len(grid.discipline_allocations) == 2
        running = next(a for a in grid.discipline_allocations if a.discipline_id == "trail_running")
        assert running.typical_session_minutes == 75  # 1.25h
        # ~7h / 1.25h ≈ 5-6 sessions (with periodization week-1 multiplier)
        assert 4 <= running.sessions_this_week <= 7
        assert running.cadence_note is None

    def test_disciplines_sorted_by_load_weight_desc(self):
        l2a = _layer2a([
            _discipline("hiking", "Hiking", load_weight=0.5),
            _discipline("trail_running", "Running", load_weight=1.0),
            _discipline("mtb_outdoor", "MTB", load_weight=0.7),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=12.0)
        ids = [a.discipline_id for a in grid.discipline_allocations]
        assert ids == ["trail_running", "mtb_outdoor", "hiking"]


# ─── §5.1.6 maintenance cadence ─────────────────────────────────────────────


class TestMaintenanceCadence:
    def test_small_share_discipline_gets_maintenance_cadence(self):
        """Climbing at 3% of 12h Build = 0.36h/wk; typical 1.5h → 0.24 sess/wk
        → maintenance cadence ~4-5 weeks between sessions."""
        l2a = _layer2a([
            _discipline(
                "trail_running",
                "Running",
                base_pct=(50.0, 60.0),
                build_pct=(50.0, 60.0),
                peak_pct=(50.0, 60.0),
                taper_pct=(50.0, 60.0),
                load_weight=1.0,
            ),
            _discipline(
                "rock_climbing_outdoor",
                "Climbing",
                base_pct=(2.0, 4.0),  # ~3%
                build_pct=(2.0, 4.0),
                peak_pct=(2.0, 4.0),
                taper_pct=(2.0, 4.0),
                load_weight=0.2,
            ),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        # Week 1 of Build → climbing emits
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=12.0)
        climb = next(a for a in grid.discipline_allocations if a.discipline_id == "rock_climbing_outdoor")
        assert climb.sessions_this_week == 1
        assert climb.cadence_note is not None
        assert "maintenance" in climb.cadence_note

    def test_maintenance_cadence_skips_in_off_weeks(self):
        l2a = _layer2a([
            _discipline(
                "trail_running",
                "Running",
                base_pct=(60.0, 70.0),
                build_pct=(60.0, 70.0),
                peak_pct=(60.0, 70.0),
                taper_pct=(60.0, 70.0),
                load_weight=1.0,
            ),
            _discipline(
                "rock_climbing_outdoor",
                "Climbing",
                base_pct=(2.0, 4.0),
                build_pct=(2.0, 4.0),
                peak_pct=(2.0, 4.0),
                taper_pct=(2.0, 4.0),
                load_weight=0.2,
            ),
        ])
        ps = _phase_structure({"Base": 4, "Build": 8, "Peak": 4, "Taper": 2})
        weeks_with_climb = [
            w
            for w in range(1, 9)
            if any(
                a.sessions_this_week > 0
                and a.discipline_id == "rock_climbing_outdoor"
                for a in build_session_grid(
                    l2a, ps, "Build", w, capacity_hours=12.0
                ).discipline_allocations
            )
        ]
        # Maintenance cadence ~4 weeks → climbing emits weeks 1 and 5 (not every week).
        assert weeks_with_climb != list(range(1, 9))  # NOT every week
        assert 1 in weeks_with_climb
        assert len(weeks_with_climb) <= 4  # Sparse, not weekly


# ─── §5.3 intensity split ────────────────────────────────────────────────────


class TestIntensityMix:
    @pytest.mark.parametrize(
        "phase,expected_hard_pct",
        [("Base", 0.10), ("Build", 0.20), ("Peak", 0.30), ("Taper", 0.10)],
    )
    def test_polarized_ratios_per_phase(self, phase, expected_hard_pct):
        l2a = _layer2a([_discipline("trail_running", "Running")])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, phase, 1, capacity_hours=12.0)
        total = grid.intensity_mix.total
        if total == 0:
            pytest.skip("no cardio sessions to check ratio")
        # Allow ±1 session of rounding tolerance.
        expected_hard = round(total * expected_hard_pct)
        assert abs(grid.intensity_mix.hard_count - expected_hard) <= 1

    def test_no_moderate_in_polarized(self):
        """Polarized = easy + hard only; no moderate field exists on IntensityMix."""
        assert not hasattr(IntensityMix(easy_count=4, hard_count=1), "moderate_count")

    def test_strength_sessions_excluded_from_intensity_mix(self):
        l2a = _layer2a([
            _discipline(
                "trail_running",
                "Running",
                base_pct=(50.0, 60.0),
                build_pct=(50.0, 60.0),
                peak_pct=(50.0, 60.0),
                taper_pct=(50.0, 60.0),
            ),
            _discipline(
                "strength",
                "Strength",
                base_pct=(20.0, 30.0),
                build_pct=(20.0, 30.0),
                peak_pct=(20.0, 30.0),
                taper_pct=(20.0, 30.0),
            ),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=12.0)
        running = next(a for a in grid.discipline_allocations if a.discipline_id == "trail_running")
        # Intensity mix total = cardio (running) only, NOT strength.
        assert grid.intensity_mix.total == running.sessions_this_week


# ─── §5.2 race-sim long day ─────────────────────────────────────────────────


class TestRaceSimLongDay:
    def test_no_race_sim_when_race_format_single_day(self):
        l2a = _layer2a([_discipline("trail_running", "Running")])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(
            l2a, ps, "Peak", 1, capacity_hours=12.0,
            race_format="single_day", race_duration_h=4.0,
        )
        assert grid.race_sim_long_day is None

    def test_race_sim_in_peak_for_continuous_multi_day(self):
        l2a = _layer2a([_discipline("trail_running", "Running")])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        # PGE = 56h race; race-sim = min(8, 56/8) = 7h.
        grid = build_session_grid(
            l2a, ps, "Peak", 2, capacity_hours=12.0,
            race_format="continuous_multi_day", race_duration_h=56.0,
        )
        assert grid.race_sim_long_day is not None
        assert grid.race_sim_long_day.phase_position == "peak"
        assert grid.race_sim_long_day.duration_min == 7 * 60
        assert grid.race_sim_long_day.weekend_anchored is True
        assert grid.race_sim_long_day.multi_discipline is True

    def test_race_sim_capped_at_8h(self):
        """For an 80h race, race_duration/8 = 10h; cap at 8h."""
        l2a = _layer2a([_discipline("trail_running", "Running")])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(
            l2a, ps, "Peak", 1, capacity_hours=12.0,
            race_format="continuous_multi_day", race_duration_h=80.0,
        )
        assert grid.race_sim_long_day is not None
        assert grid.race_sim_long_day.duration_min == 8 * 60

    def test_race_sim_in_taper_week_1_only(self):
        """Taper week 1 = scaled race-sim; later Taper weeks = none."""
        l2a = _layer2a([_discipline("trail_running", "Running")])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        # Taper-1: race_duration=56 → peak_duration=7h × 0.6 = 4.2h ≈ 252 min.
        grid_t1 = build_session_grid(
            l2a, ps, "Taper", 1, capacity_hours=12.0,
            race_format="continuous_multi_day", race_duration_h=56.0,
        )
        assert grid_t1.race_sim_long_day is not None
        assert grid_t1.race_sim_long_day.phase_position == "taper_1"
        assert grid_t1.race_sim_long_day.duration_min == int(round(7 * 0.6 * 60))

        # Taper-2 (final): no race-sim.
        grid_t2 = build_session_grid(
            l2a, ps, "Taper", 2, capacity_hours=12.0,
            race_format="continuous_multi_day", race_duration_h=56.0,
        )
        assert grid_t2.race_sim_long_day is None


# ─── Track 2 slice 2c §5.4 — rest detection ────────────────────────────────


class _StubSession:
    """Minimal duck-type for `detect_insufficient_rest` (only `.date` + `.kind`
    are read). Keeps the rest-detection tests independent of the full
    PlanSession schema (which requires pydantic + many unrelated fields)."""

    def __init__(self, date_: date, kind: str = "cardio") -> None:
        self.date = date_
        self.kind = kind


class TestExpectedRestCount:
    def test_phase_defaults(self):
        from layer4.session_grid import expected_rest_count

        assert expected_rest_count("Base") == 2
        assert expected_rest_count("Build") == 2
        assert expected_rest_count("Peak") == 1
        assert expected_rest_count("Taper") == 2

    def test_unknown_phase_returns_zero(self):
        from layer4.session_grid import expected_rest_count

        assert expected_rest_count("Bogus") == 0

    def test_disabled_days_cover_rest_target(self):
        """Athlete with 5 enabled days has 2 disabled days already → Base's
        2-rest target is already met by disabled days → return 0 (no
        additional LLM rest required)."""
        from layer4.session_grid import expected_rest_count

        assert expected_rest_count("Base", weekly_capacity_days=5) == 0

    def test_partial_disabled_subtracts_from_target(self):
        """6 enabled days = 1 disabled = 1 auto-rest. Base needs 2 total →
        LLM must pick 1 more rest day."""
        from layer4.session_grid import expected_rest_count

        assert expected_rest_count("Base", weekly_capacity_days=6) == 1

    def test_full_capacity_no_subtraction(self):
        """All 7 days enabled = 0 auto-rest. Phase target stands."""
        from layer4.session_grid import expected_rest_count

        assert expected_rest_count("Base", weekly_capacity_days=7) == 2

    def test_peak_one_day_target(self):
        from layer4.session_grid import expected_rest_count

        assert expected_rest_count("Peak", weekly_capacity_days=7) == 1
        # Peak only wants 1 rest; even 6 enabled (1 disabled) meets it.
        assert expected_rest_count("Peak", weekly_capacity_days=6) == 0


class TestDetectInsufficientRest:
    def test_meets_expected_returns_none(self):
        """3 days with sessions, 7-3=4 rest days, expected 2 → no warning."""
        from layer4.session_grid import detect_insufficient_rest

        monday = date(2026, 6, 1)
        sessions = [_StubSession(monday + timedelta(days=i)) for i in range(3)]
        assert detect_insufficient_rest(sessions, expected=2) is None

    def test_below_expected_emits_warning(self):
        """7 days with non-rest sessions → 0 rest days, expected 2 → warning."""
        from layer4.session_grid import detect_insufficient_rest

        monday = date(2026, 6, 1)
        sessions = [_StubSession(monday + timedelta(days=i)) for i in range(7)]
        warning = detect_insufficient_rest(sessions, expected=2)
        assert warning is not None
        assert warning.expected == 2
        assert warning.actual == 0

    def test_rest_session_doesnt_count_as_workload(self):
        """A `kind='rest'` session on a date doesn't count as a workload day —
        it's still a rest day. So Mon/Tue cardio + Wed rest = 2 workload
        days → 7-2=5 rest days, expected 2 → no warning."""
        from layer4.session_grid import detect_insufficient_rest

        monday = date(2026, 6, 1)
        sessions = [
            _StubSession(monday, "cardio"),
            _StubSession(monday + timedelta(days=1), "cardio"),
            _StubSession(monday + timedelta(days=2), "rest"),
        ]
        assert detect_insufficient_rest(sessions, expected=2) is None

    def test_six_workload_days_one_rest_warns(self):
        """6 workload days → 1 rest day. Expected 2 → warning (actual 1 < 2)."""
        from layer4.session_grid import detect_insufficient_rest

        monday = date(2026, 6, 1)
        sessions = [_StubSession(monday + timedelta(days=i)) for i in range(6)]
        warning = detect_insufficient_rest(sessions, expected=2)
        assert warning is not None
        assert warning.actual == 1

    def test_zero_expected_returns_none(self):
        from layer4.session_grid import detect_insufficient_rest

        sessions = [_StubSession(date(2026, 6, 1))]
        assert detect_insufficient_rest(sessions, expected=0) is None

    def test_empty_sessions_returns_none(self):
        from layer4.session_grid import detect_insufficient_rest

        assert detect_insufficient_rest([], expected=2) is None
