"""Tests for `layer4.session_grid` — Track 2 slice 2b §5.1 / §5.2 / §5.3 +
slice 2b.2 §5.1.1 (session-count ceiling)."""

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
    apply_session_ceiling,
    build_session_grid,
    phase_session_ceiling,
    placeable_days_in_week,
    resolve_available_days,
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


# ─── §5.1 Slice 2 session typing (#624) ──────────────────────────────────────


class TestSessionTypes:
    def test_quality_counts_sum_to_week_hard_count(self):
        """The per-discipline quality counts sum exactly to the week-level
        hard_count — the typing and the polarized mix are consistent."""
        l2a = _layer2a([
            _discipline("trail_running", "Running", load_weight=3.0,
                        build_pct=(40.0, 50.0)),
            _discipline("mtb_outdoor", "MTB", load_weight=2.0,
                        build_pct=(25.0, 35.0)),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=14.0)
        typed = [a for a in grid.discipline_allocations if a.session_types is not None]
        assert typed, "expected cardio disciplines to be typed"
        assert sum(a.session_types.quality for a in typed) == grid.intensity_mix.hard_count
        # Each discipline's slots account for exactly its session count.
        for a in typed:
            assert a.session_types.total == a.sessions_this_week

    def test_primary_discipline_gets_one_long_anchor(self):
        """The highest-load-weight cardio discipline carves exactly one long
        LSD cornerstone; secondaries carry none."""
        l2a = _layer2a([
            _discipline("trail_running", "Running", load_weight=3.0,
                        build_pct=(40.0, 50.0)),
            _discipline("mtb_outdoor", "MTB", load_weight=2.0,
                        build_pct=(25.0, 35.0)),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=14.0)
        primary = next(a for a in grid.discipline_allocations if a.discipline_id == "trail_running")
        secondary = next(a for a in grid.discipline_allocations if a.discipline_id == "mtb_outdoor")
        assert primary.session_types.long == 1
        assert secondary.session_types.long == 0

    def test_taper_drops_the_long_anchor(self):
        """No phase but Taper carries the long cornerstone; Taper drops LSD."""
        l2a = _layer2a([
            _discipline("trail_running", "Running", load_weight=3.0,
                        taper_pct=(40.0, 50.0)),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Taper", 1, capacity_hours=7.0)
        primary = next(a for a in grid.discipline_allocations if a.discipline_id == "trail_running")
        if primary.sessions_this_week > 0:
            assert primary.session_types.long == 0

    def test_strength_is_not_typed(self):
        """Strength is not surface-routed → session_types stays None."""
        l2a = _layer2a([
            _discipline("trail_running", "Running", load_weight=3.0,
                        build_pct=(50.0, 60.0)),
            _discipline("strength", "Strength", load_weight=1.0,
                        build_pct=(20.0, 30.0)),
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Build", 1, capacity_hours=14.0)
        strength = next(a for a in grid.discipline_allocations if a.discipline_id == "strength")
        assert strength.session_types is None

    def test_no_negative_easy_when_all_sessions_are_quality(self):
        """quality never exceeds the discipline's session count, so easy ≥ 0."""
        l2a = _layer2a([_discipline("trail_running", "Running", load_weight=3.0)])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        for phase in ("Base", "Build", "Peak", "Taper"):
            grid = build_session_grid(l2a, ps, phase, 1, capacity_hours=14.0)
            for a in grid.discipline_allocations:
                if a.session_types is not None:
                    assert a.session_types.easy >= 0
                    assert a.session_types.quality <= a.sessions_this_week


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


# ─── Track 2 slice 2b.2 §5.1.1 — session-count ceiling ──────────────────────


def _alloc(did: str, sessions: int, hours: float = 2.0) -> DisciplineAllocation:
    return DisciplineAllocation(
        discipline_id=did,
        discipline_name=did.title(),
        sessions_this_week=sessions,
        typical_session_minutes=60,
        target_hours_this_week=hours,
    )


class TestPhaseSessionCeiling:
    def test_peak_anchor_and_phase_scales(self):
        # peak_sessions_max=10, D=6 → Build/Peak 10, Base round(9.0)=9, Taper round(8.5)=8
        assert phase_session_ceiling("Peak", 6, peak_sessions_max=10) == 10
        assert phase_session_ceiling("Build", 6, peak_sessions_max=10) == 10
        assert phase_session_ceiling("Base", 6, peak_sessions_max=10) == 9
        assert phase_session_ceiling("Taper", 6, peak_sessions_max=10) == 8

    def test_hard_clamp_two_per_day(self):
        # D=4 → hard max 2×4=8, even though peak_sessions_max asks for 10.
        assert phase_session_ceiling("Peak", 4, peak_sessions_max=10) == 8

    def test_preference_density_fallback(self):
        # No explicit number → derive from the two_a_day_preference density.
        assert phase_session_ceiling("Peak", 6, two_a_day_preference="never") == 6
        assert phase_session_ceiling("Peak", 6, two_a_day_preference="occasionally") == 9
        assert phase_session_ceiling("Peak", 6, two_a_day_preference="regularly") == 11

    def test_default_when_unset(self):
        # Both unset → default peak ceiling of 10.
        assert phase_session_ceiling("Peak", 6) == 10


class TestApplySessionCeiling:
    def test_under_ceiling_is_identity(self):
        allocs = [_alloc("a", 2), _alloc("b", 2)]  # total 4 ≤ 10
        out = apply_session_ceiling(allocs, "Build", 6, peak_sessions_max=10)
        assert out is allocs  # identity-preserving short-circuit

    def test_trims_multi_before_dropping(self):
        # 3 disciplines × 2 = 6; Peak/D=2 → ceiling min(10, 4) = 4.
        # Trim lowest-priority multis (tail first); nothing drops to 0 (2+1+1=4).
        allocs = [_alloc("a", 2), _alloc("b", 2), _alloc("c", 2)]
        out = apply_session_ceiling(allocs, "Peak", 2, peak_sessions_max=10)
        counts = {a.discipline_id: a.sessions_this_week for a in out}
        assert sum(counts.values()) == 4
        assert counts["a"] == 2  # highest priority keeps its sessions
        assert all(v >= 1 for v in counts.values())  # breadth preserved

    def test_drops_lowest_priority_when_all_singles(self):
        # 5 singles; ceiling 4 (D=2) → drop the lowest-priority discipline to 0.
        allocs = [_alloc(x, 1) for x in ("a", "b", "c", "d", "e")]
        out = apply_session_ceiling(allocs, "Peak", 2, peak_sessions_max=10)
        counts = {a.discipline_id: a.sessions_this_week for a in out}
        assert sum(counts.values()) == 4
        assert counts["a"] == 1  # highest priority kept
        assert counts["e"] == 0  # lowest priority rotated out
        dropped = next(a for a in out if a.discipline_id == "e")
        assert dropped.cadence_note is not None

    def test_volume_preserved_on_trim(self):
        # b (lowest priority) trimmed 3→2 but its target hours are unchanged
        # ("fewer, longer sessions").
        allocs = [_alloc("a", 2, hours=5.0), _alloc("b", 3, hours=6.0)]  # total 5
        out = apply_session_ceiling(allocs, "Peak", 2, peak_sessions_max=10)  # ceiling 4
        b = next(a for a in out if a.discipline_id == "b")
        assert b.sessions_this_week == 2
        assert b.target_hours_this_week == 6.0


class TestResolveAvailableDays:
    def test_available_days_per_week_wins(self):
        assert resolve_available_days({"available_days_per_week": 5}) == 5

    def test_falls_back_to_enabled_window_count(self):
        windows = [{"enabled": True}, {"enabled": False}, {"enabled": True}]
        assert resolve_available_days(
            {"daily_availability_windows": windows}
        ) == 2

    def test_defaults_to_all_seven_when_unset(self):
        assert resolve_available_days({}) == 7
        assert resolve_available_days(None) == 7


class TestPlaceableDaysInWeek:
    # A 7-day window, Mon 2026-07-13 .. Sun 2026-07-19. The race is Fri 2026-07-17;
    # with the pre-race day reserved as rest, the last trainable day is Wed 07-15,
    # so cutoff = event_date − 2 = 2026-07-15.
    WK_START = date(2026, 7, 13)
    WK_END = date(2026, 7, 19)
    CUTOFF = date(2026, 7, 15)

    def _windows(self, enabled_days):
        # layer1_payload with one window per weekday; `enabled_days` = the Mon..Sun
        # short names that train.
        all_dows = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return {
            "daily_availability_windows": [
                {"day_of_week": d, "enabled": d in enabled_days} for d in all_dows
            ]
        }

    def test_no_cutoff_returns_available_days_unchanged(self):
        # Open-ended plan (no race): never truncate.
        assert placeable_days_in_week(5, {}, self.WK_START, self.WK_END, None) == 5

    def test_week_fully_before_cutoff_unchanged(self):
        # A normal mid-plan week ends well before the race → identical to today.
        far = date(2026, 9, 1)
        assert placeable_days_in_week(
            5, self._windows(["Mon", "Tue", "Wed", "Thu", "Fri"]),
            self.WK_START, self.WK_END, far,
        ) == 5

    def test_race_week_truncates_to_enabled_days_before_cutoff(self):
        # Trains Mon–Fri; only Mon/Tue/Wed survive the Wed cutoff → 3.
        wins = self._windows(["Mon", "Tue", "Wed", "Thu", "Fri"])
        assert placeable_days_in_week(5, wins, self.WK_START, self.WK_END, self.CUTOFF) == 3

    def test_pre_race_rest_day_is_excluded(self):
        # Athlete trains Wed/Thu/Fri/Sat/Sun. Thu (07-16) is the pre-race rest day
        # and Fri (07-17) is race day — both past the Wed cutoff. Only Wed remains.
        wins = self._windows(["Wed", "Thu", "Fri", "Sat", "Sun"])
        assert placeable_days_in_week(5, wins, self.WK_START, self.WK_END, self.CUTOFF) == 1

    def test_capped_by_available_days_without_windows(self):
        # No per-day windows: cap nominal availability by surviving calendar days
        # (Mon/Tue/Wed ≤ cutoff = 3). available_days_per_week=5 → min(5, 3) = 3.
        assert placeable_days_in_week(5, {}, self.WK_START, self.WK_END, self.CUTOFF) == 3

    def test_result_never_exceeds_available_days(self):
        # Every weekday enabled but the athlete only trains 2 days/week → the
        # nominal availability still caps the placeable count.
        wins = self._windows(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        assert placeable_days_in_week(2, wins, self.WK_START, self.WK_END, self.CUTOFF) == 2


class TestBuildGridCeilingIntegration:
    def test_caps_to_available_days(self):
        # 7 disciplines naturally allocate ≥7 sessions; with D=2 the grid must
        # cap the week to the 2×2 = 4 hard max (proves the ceiling plumbs through).
        l2a = _layer2a([
            _discipline(f"d{i}", f"D{i}", load_weight=1.0 - i * 0.1)
            for i in range(7)
        ])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(
            l2a, ps, "Peak", 1, capacity_hours=14.0, available_days=2,
        )
        total = sum(a.sessions_this_week for a in grid.discipline_allocations)
        assert total <= 4

    def test_no_cap_without_available_days(self):
        # Bare caller (no available_days) keeps the uncapped per-discipline sum.
        l2a = _layer2a([_discipline(f"d{i}", f"D{i}") for i in range(7)])
        ps = _phase_structure({"Base": 4, "Build": 4, "Peak": 4, "Taper": 2})
        grid = build_session_grid(l2a, ps, "Peak", 1, capacity_hours=14.0)
        total = sum(a.sessions_this_week for a in grid.discipline_allocations)
        assert total >= 7  # ≥1-per-discipline floor, no ceiling applied
