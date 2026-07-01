"""Tests for the §7 WS-E2 strength-saturation cap in `layer4.session_grid`.

The cap runs after the §5.1.1 ceiling: weekly FAILOVER strength (terrain/craft-
infeasible cardio composed as a strength substitution) is capped at `dose + 2`
total strength, and the over-cap excess is reallocated to feasible disciplines
proportional to load_weight — volume-conserving, with a per-discipline
absorption cap (a discipline can at most double) and excess-stays-strength when
no feasible absorber has capacity.
"""

from __future__ import annotations

from datetime import date, timedelta

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
    apply_strength_saturation_cap,
    build_session_grid,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _alloc(did: str, n: int, *, name: str | None = None) -> DisciplineAllocation:
    return DisciplineAllocation(
        discipline_id=did,
        discipline_name=name or did,
        sessions_this_week=n,
        typical_session_minutes=90,
        target_hours_this_week=float(n) * 1.5,
    )


def _total(allocs: list[DisciplineAllocation]) -> int:
    return sum(a.sessions_this_week for a in allocs)


def _by_id(allocs: list[DisciplineAllocation]) -> dict[str, int]:
    return {a.discipline_id: a.sessions_this_week for a in allocs}


# ─── No-op cases ─────────────────────────────────────────────────────────────


def test_no_op_when_failover_within_headroom():
    # Peak: failover headroom is +2. Two failover-strength disciplines == 2 → no cap.
    allocs = [_alloc("D-001", 3), _alloc("D-008", 1), _alloc("D-009", 1)]
    out, detail = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-001": "exact", "D-008": "strength", "D-009": "strength"},
        {"D-001": 3.0, "D-008": 2.0, "D-009": 1.0},
    )
    assert out is allocs  # identity-preserving
    assert detail == ""


def test_unknown_phase_is_no_op():
    allocs = [_alloc("D-008", 5)]
    out, detail = apply_strength_saturation_cap(
        allocs, "Recovery", {"D-008": "strength"}, {"D-008": 1.0}
    )
    assert out is allocs
    assert detail == ""


# ─── Trim + reallocate ───────────────────────────────────────────────────────


def test_over_cap_trims_to_headroom_and_reallocates():
    # Peak. One craft-failed discipline allocated 5x → 5 failover strength.
    # headroom 2 → over = 3. Feasible absorber D-001 (running) at 3 sessions can
    # absorb up to 3 (double rule). All 3 move; volume conserved.
    allocs = [_alloc("D-001", 3), _alloc("D-008", 5)]
    out, detail = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-001": "exact", "D-008": "strength"},
        {"D-001": 3.0, "D-008": 2.0},
    )
    counts = _by_id(out)
    assert counts["D-008"] == 2  # failover capped at headroom
    assert counts["D-001"] == 6  # absorbed the 3 freed sessions
    assert _total(out) == _total(allocs)  # volume conserved
    assert "moved=3" in detail and "residual=0" in detail


def test_reallocation_is_proportional_to_load_weight():
    # over = 4 freed; two absorbers weighted 3:1 → d'Hondt gives 3 and 1.
    allocs = [
        _alloc("D-001", 4),  # weight 3.0
        _alloc("D-006", 4),  # weight 1.0
        _alloc("D-008", 6),  # failover, weight 2.0
    ]
    out, _ = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-001": "exact", "D-006": "exact", "D-008": "strength"},
        {"D-001": 3.0, "D-006": 1.0, "D-008": 2.0},
    )
    counts = _by_id(out)
    assert counts["D-008"] == 2  # 6 → 2 (headroom)
    # 4 freed split 3:1 by weight
    assert counts["D-001"] == 4 + 3
    assert counts["D-006"] == 4 + 1
    assert _total(out) == _total(allocs)


def test_absorption_capped_residual_stays_strength():
    # Only one feasible absorber, at 1 session → can take at most 1 (double rule).
    # over = 3, capacity = 1 → 1 moved, 2 residual stay strength.
    allocs = [_alloc("D-002", 1), _alloc("D-008", 5)]
    out, detail = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-002": "exact", "D-008": "strength"},
        {"D-002": 1.0, "D-008": 2.0},
    )
    counts = _by_id(out)
    assert counts["D-002"] == 2  # absorbed its capacity (1)
    assert counts["D-008"] == 4  # 5 → 4 (only 1 could move; 4 stay strength)
    assert _total(out) == _total(allocs)
    assert "moved=1" in detail and "residual=2" in detail


def test_no_feasible_absorber_leaves_strength_unchanged():
    # Everything is infeasible → nowhere to reallocate → strength stays (degrade
    # gracefully rather than drop training).
    allocs = [_alloc("D-008", 5), _alloc("D-009", 2)]
    out, detail = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-008": "strength", "D-009": "strength"},
        {"D-008": 2.0, "D-009": 1.0},
    )
    assert out is allocs
    assert "moved=0" in detail and "no absorber capacity" in detail


def test_trims_lowest_priority_failover_first():
    # Two failover disciplines; D-009 (lower priority, listed last) is trimmed
    # before the higher-priority D-008. headroom 2, total failover 6, over 4.
    # Absorber D-001 at 5 can take up to 5.
    allocs = [_alloc("D-001", 5), _alloc("D-008", 4), _alloc("D-009", 2)]
    out, _ = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-001": "exact", "D-008": "strength", "D-009": "strength"},
        {"D-001": 3.0, "D-008": 2.0, "D-009": 1.0},
    )
    counts = _by_id(out)
    # D-009 (2) fully trimmed first, then D-008 4→2. Combined failover == 2.
    assert counts["D-009"] == 0
    assert counts["D-008"] == 2
    assert counts["D-001"] == 5 + 4
    assert _total(out) == _total(allocs)


def test_skill_gated_excluded_from_trim_and_absorb():
    # D-012 is skill-gated (also rendered as strength) but must NOT be trimmed
    # (it's a deliberate #336 safety substitution) nor used as an absorber.
    allocs = [_alloc("D-001", 2), _alloc("D-012", 3), _alloc("D-008", 5)]
    out, detail = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-001": "exact", "D-008": "strength"},  # D-012 absent (skill-gated)
        {"D-001": 3.0, "D-012": 2.0, "D-008": 2.0},
        skill_gated_ids=frozenset({"D-012"}),
    )
    counts = _by_id(out)
    assert counts["D-012"] == 3  # untouched — neither trimmed nor absorbing
    # over = 3, but the only absorber D-001 (2 sessions) caps at 2 (double rule),
    # so 2 move (D-008 5→3) and 1 residual stays strength.
    assert counts["D-008"] == 3
    assert counts["D-001"] == 2 + 2
    assert "residual=1" in detail


def test_unconstrained_discipline_is_a_valid_absorber():
    # A discipline with no terrain requirement is absent from the tier map and
    # must still be eligible to absorb reallocated volume.
    allocs = [_alloc("D-002", 3), _alloc("D-008", 5)]  # D-002 unconstrained
    out, _ = apply_strength_saturation_cap(
        allocs,
        "Peak",
        {"D-008": "strength"},  # D-002 absent → unconstrained, feasible
        {"D-002": 1.0, "D-008": 2.0},
    )
    counts = _by_id(out)
    assert counts["D-008"] == 2
    assert counts["D-002"] == 3 + 3
    assert _total(out) == _total(allocs)


# ─── Integration through build_session_grid ──────────────────────────────────


def _weight(value: float) -> WeightResult:
    return WeightResult(value=value, source="system_default", system_default=value)


def _discipline(did: str, name: str, lw: float) -> Layer2ADiscipline:
    return Layer2ADiscipline(
        discipline_id=did,
        discipline_name=name,
        inclusion="included",  # type: ignore[arg-type]
        role="Primary",
        load_weight=_weight(lw),
        rationale="test",
        phase_load=PhaseLoadBands(
            base_low=20.0, base_high=30.0,
            build_low=20.0, build_high=30.0,
            peak_low=40.0, peak_high=50.0,
            taper_low=20.0, taper_high=30.0,
            default_inclusion="included",
        ),
    )


def _phase_structure() -> PhaseStructure:
    start = date.today()
    return PhaseStructure(
        phases=[
            PhaseSpec(
                phase_name="Peak",  # type: ignore[arg-type]
                start_date=start,
                end_date=start + timedelta(days=6),
                weeks=1,
                intended_volume_band=(12.0, 16.0),
                intended_intensity_distribution={"easy": 0.7, "hard": 0.3},
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
        ],
        total_weeks=1,
        derived_from="3b_standard",
    )


def _l2a(disciplines: list[Layer2ADiscipline]) -> Layer2APayload:
    return Layer2APayload(
        framework_sport="adventure_racing",
        etl_version_set={"layer0": "v7"},
        disciplines=disciplines,
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            generated_at="2026-06-06T00:00:00Z"
        ),
        weekly_total_hours_by_phase={
            "Base": (8.0, 10.0),
            "Build": (10.0, 14.0),
            "Peak": (12.0, 16.0),
            "Taper": (5.0, 7.0),
        },
    )


def test_build_session_grid_applies_saturation_cap_when_tiers_supplied():
    l2a = _l2a([
        _discipline("D-001", "Trail Running", 3.0),
        _discipline("D-008", "Mountain Biking", 2.0),
    ])
    ps = _phase_structure()
    # Generous capacity so both disciplines get multiple sessions; high
    # available_days so the ceiling doesn't pre-trim.
    common = dict(
        capacity_hours=20.0,
        available_days=7,
    )
    base = build_session_grid(l2a, ps, "Peak", 1, **common)
    capped = build_session_grid(
        l2a, ps, "Peak", 1,
        strength_feasibility_tiers={"D-001": "exact", "D-008": "strength"},
        **common,
    )
    base_counts = {a.discipline_id: a.sessions_this_week for a in base.discipline_allocations}
    capped_counts = {a.discipline_id: a.sessions_this_week for a in capped.discipline_allocations}
    # The cap only fires if D-008 had > 2 sessions; assert the wiring either
    # capped it or left it untouched, but never exceeds the headroom when it fires.
    if base_counts["D-008"] > 2:
        assert capped_counts["D-008"] == 2
        assert capped.saturation_note is not None
        # volume conserved across the rebalance
        assert sum(capped_counts.values()) == sum(base_counts.values())
    else:
        assert capped.saturation_note is None


def test_build_session_grid_no_cap_without_tiers():
    l2a = _l2a([_discipline("D-008", "Mountain Biking", 2.0)])
    grid = build_session_grid(
        l2a, _phase_structure(), "Peak", 1,
        capacity_hours=20.0, available_days=7,
    )
    assert grid.saturation_note is None
