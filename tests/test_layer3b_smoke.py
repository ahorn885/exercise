"""Real-LLM smoke tests for
`layer3b.builder.llm_layer3b_goal_timeline_viability`.

Per `Upstream_Implementation_Plan_v1.md` §4 row Layer-4-Step-7 +
`Layer3B_v1.md` §12 L3B-P-1 — exercises the production Anthropic SDK
adapter (`_default_llm_caller`) against real Sonnet 4.6. Gated on
`ANTHROPIC_API_KEY` via the `requires_anthropic_api_key` skipif marker
from `tests/conftest.py`; default `pytest tests/` runs ignore this file.

Two §13 scenarios per handoff §6.3 — both modes covered:

- **TS-1 AR finisher compressed** (event-mode): Andy's PGE 2026 baseline.
  9 weeks out, Finish goal, prior AR finish on record. Expect
  `mode == 'event'` + viability in {achievable, achievable-with-adjustment}
  + `periodization_shape.mode == 'compressed'` + D14 event-metadata fields
  populated from the `RaceEventPayload`.
- **TS-4 no-event endurance standard** (no-event-mode): 24-week endurance
  block. Expect `mode == 'no-event'` + viability achievable +
  `periodization_shape.mode == 'standard'` + all 4 D14 event-metadata
  fields None.

Assertions are mixed structural (payload validates, metadata stamped,
D14 fields populated/null per mode) + loose enum (allowlist sets) to
absorb minor classification variance across Sonnet 4.6 minor versions
without false positives.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from conftest import requires_anthropic_api_key

from layer3b.builder import llm_layer3b_goal_timeline_viability
from layer4.context import (
    ACWRStatus,
    Assessment,
    CurrentState,
    DataDensity,
    DisciplineWeightRecord,
    Layer1Availability,
    Layer1Disclosures,
    Layer1DisciplineBaselines,
    Layer1EventGoal,
    Layer1HealthStatus,
    Layer1Identity,
    Layer1Lifestyle,
    Layer1Network,
    Layer1Payload,
    Layer1Performance,
    Layer1StrengthBenchmarks,
    Layer1TrainingHistory,
    Layer2ADiscipline,
    Layer2APayload,
    Layer3APayload,
    RaceEventPayload,
    RationaleMetadata,
    RecentTrajectory,
    TrainingGapsSummary,
    TrajectoryWindow,
    WeightResult,
)

pytestmark = requires_anthropic_api_key

_ETL = {"0A": "v1", "0B": "v1", "0C": "v1"}
_AS_OF = datetime(2026, 5, 20, 0, 0)
_TODAY = date(2026, 5, 20)


def _make_layer1(primary_sport: str = "Adventure Racing") -> Layer1Payload:
    return Layer1Payload(
        user_id=1,
        as_of=_AS_OF,
        identity=Layer1Identity(
            date_of_birth=date(1980, 6, 1),
            sex="male",
            height_cm=180.0,
            primary_sport=primary_sport,
        ),
        health_status=Layer1HealthStatus(current_injuries=[], resting_hr_bpm=52),
        training_history=Layer1TrainingHistory(
            years_structured_training=5,
            peak_weekly_volume_hrs=12.0,
            peak_weekly_volume_year=2024,
            longest_event_completed="50-mile ultra",
            discipline_weighting=[
                DisciplineWeightRecord(discipline_slug="run", weight_pct=40),
                DisciplineWeightRecord(discipline_slug="bike", weight_pct=40),
                DisciplineWeightRecord(discipline_slug="paddle", weight_pct=20),
            ],
        ),
        discipline_baselines=Layer1DisciplineBaselines(),
        strength_benchmarks=Layer1StrengthBenchmarks(),
        performance=Layer1Performance(body_weight_kg=75.0, hrmax_bpm=185),
        availability=Layer1Availability(),
        event_goal=Layer1EventGoal(),
        lifestyle=Layer1Lifestyle(sleep_baseline_hours=7.5),
        network=Layer1Network(),
        disclosures=Layer1Disclosures(),
    )


def _make_layer3a(
    *,
    aerobic_level: str = "good",
    aerobic_confidence: str = "medium",
    strength_level: str = "moderate",
    strength_confidence: str = "medium",
    trajectory_confidence: str = "medium",
    short_term: str = "building",
    medium_term: str = "building",
) -> Layer3APayload:
    return Layer3APayload(
        user_id=1,
        as_of=_AS_OF,
        model="claude-sonnet-4-6",
        temperature=0.0,
        prompt_hash="a" * 64,
        latency_ms=4500,
        input_tokens=3200,
        output_tokens=900,
        etl_version_set=_ETL,
        current_state=CurrentState(
            aerobic_capacity=Assessment(
                level=aerobic_level,
                confidence=aerobic_confidence,
                reasoning_text="Established AR endurance base per multi-year history.",
                evidence_basis=[
                    "section_c.peak_weekly_volume_hrs",
                    "integration.recent_workouts",
                ],
            ),
            strength=Assessment(
                level=strength_level,
                confidence=strength_confidence,
                reasoning_text="Moderate strength baseline.",
                evidence_basis=["section_e.pushup_max_reps"],
            ),
            weak_links=[],
            skill_assessments={},
            body_composition_notes=None,
        ),
        recent_trajectory=RecentTrajectory(
            short_term=TrajectoryWindow(
                direction=short_term,
                reasoning_text="Volume building.",
                evidence_basis=["integration.recent_workouts"],
            ),
            medium_term=TrajectoryWindow(
                direction=medium_term,
                reasoning_text="Sustained 28-day volume trend.",
                evidence_basis=["integration.recent_workouts"],
            ),
            acwr_status=ACWRStatus(per_discipline={}, combined=None),
            confidence=trajectory_confidence,
        ),
        data_density=DataDensity(
            connected_providers=["polar"],
            integration_data_days=28,
            recent_workouts_count=20,
            recent_sleep_count=14,
            recent_hrv_count=14,
            self_report_freshness_days=0,
            section_completeness={"C": 0.8, "E": 0.4, "F": 0.6},
        ),
        notable_observations=[],
    )


def _make_layer2a(framework_sport: str = "Adventure Racing") -> Layer2APayload:
    return Layer2APayload(
        framework_sport=framework_sport,
        etl_version_set=_ETL,
        disciplines=[
            Layer2ADiscipline(
                discipline_id=f"D-{i:03d}",
                discipline_name=name,
                inclusion="included",
                role="Primary" if i == 1 else "Secondary",
                is_conditional=False,
                load_weight=WeightResult(
                    value=w, source="system_default", system_default=w
                ),
                sleep_deprivation_relevant=False,
                rationale="Baseline.",
            )
            for i, name, w in [
                (1, "Trail Running", 0.4),
                (5, "Mountain Biking", 0.3),
                (6, "Packrafting", 0.2),
                (10, "Rock Climbing", 0.1),
            ]
        ],
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
            any_no_substitute=False,
            any_multi_substitute_candidate=False,
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            template_version="v1",
            generated_at="2026-05-20T12:00:00",
        ),
    )


def _make_race_event() -> RaceEventPayload:
    return RaceEventPayload(
        race_event_id=1,
        user_id=1,
        name="Pocket Gopher Extreme 2026",
        event_date=date(2026, 7, 22),
        race_format="continuous_multi_day",
        distance_km=Decimal("250"),
        is_target_event=True,
        event_locale_id="nerstrand-mn",
        route_locales=[],
    )


# ─── Smoke tests ─────────────────────────────────────────────────────────────


class TestLayer3BSmoke:
    """Real-LLM round-trip against Sonnet 4.6. Gated on ANTHROPIC_API_KEY."""

    def test_ts1_ar_finisher_compressed_event_mode(self):
        """§13 TS-1 — AR Finish goal, ~9 weeks out, prior AR finish.
        Expect event-mode + viability achievable-or-with-adjustment +
        compressed periodization + D14 event-metadata populated."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=_TODAY,
            etl_version_set=_ETL,
            goal_outcome="Finish",
            first_time_at_distance=False,
            previous_attempts=[{"outcome": "Finished", "dnf_cause": ""}],
        )

        # Structural — driver-stamped metadata
        assert payload.user_id == 1
        assert payload.model == "claude-sonnet-4-6"
        assert payload.input_tokens > 0
        assert payload.output_tokens > 0
        assert payload.latency_ms > 0
        assert len(payload.prompt_hash) == 64
        assert payload.etl_version_set == _ETL

        # Mode + D14 event-metadata fields
        assert payload.mode == "event"
        assert payload.event_date == date(2026, 7, 22)
        assert payload.event_locale_id == "nerstrand-mn"
        assert payload.race_format == "continuous_multi_day"
        assert payload.time_to_event_weeks is not None
        assert 8 <= payload.time_to_event_weeks <= 10

        # Loose enum — Finish goal with prior AR finish should be viable
        assert payload.goal_viability.viability in {
            "achievable",
            "achievable-with-adjustment",
        }
        assert payload.goal_viability.confidence in {"high", "medium", "low"}
        assert payload.goal_viability.evidence_basis
        assert payload.goal_viability.reasoning_text.strip()

        # Compressed periodization expected per spec §5.3 phase band
        # (9 weeks out → "compressed" band). Allow custom as a fallback if
        # the LLM emits a custom shape with valid phase_weeks sum.
        assert payload.periodization_shape.mode in {"compressed", "custom"}
        assert payload.periodization_shape.start_phase in {
            "Base",
            "Build",
            "Peak",
            "Taper",
        }

        # Finish goal + prior finish → no blocker HITL expected
        blockers = [h for h in payload.hitl_surface if h.severity == "blocker"]
        assert not blockers, f"unexpected blocker HITL: {[h.item_label for h in blockers]}"

    def test_ts4_no_event_endurance_standard(self):
        """§13 TS-4 — 24-week no-event endurance block. Expect no-event
        mode + standard periodization + all D14 event-metadata fields
        None."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Trail Running"),
            layer3a_payload=_make_layer3a(aerobic_level="moderate"),
            layer2a_payload=_make_layer2a(framework_sport="Trail Running"),
            race_event_payload=None,
            current_date=_TODAY,
            etl_version_set=_ETL,
            plan_duration_weeks=24,
            non_event_goal_type="endurance",
        )

        # Structural
        assert payload.input_tokens > 0
        assert payload.output_tokens > 0
        assert payload.latency_ms > 0

        # Mode + D14 fields all None per no-event-mode
        assert payload.mode == "no-event"
        assert payload.event_date is None
        assert payload.event_locale_id is None
        assert payload.race_format is None
        assert payload.time_to_event_weeks is None

        # Loose enum — 24w endurance block with moderate aerobic should
        # be achievable; allow with-adjustment to absorb borderline reads
        assert payload.goal_viability.viability in {
            "achievable",
            "achievable-with-adjustment",
        }
        assert payload.goal_viability.evidence_basis

        # Standard periodization expected for 24w endurance (no compression)
        # Allow extended as alternative read.
        assert payload.periodization_shape.mode in {"standard", "extended"}
        assert payload.periodization_shape.start_phase in {
            "Base",
            "Build",
            "Peak",
            "Taper",
        }

        # No-event endurance block → no blocker HITL expected
        blockers = [h for h in payload.hitl_surface if h.severity == "blocker"]
        assert not blockers, f"unexpected blocker HITL: {[h.item_label for h in blockers]}"


# ─── §13 regression scenarios TS-2/3/5/6/7 ──────────────────────────────────
#
# TS-1 (AR finisher compressed) + TS-4 (no-event endurance standard) are the
# two scenarios above. TS-8 (event_date in the past → Layer3BInputError, no
# LLM call) is an input-error case covered in tests/test_layer3b_builder.py,
# so it is not duplicated here in the key-gated module.


def _race_event_weeks_out(
    weeks: int,
    *,
    name: str = "Test Race",
    race_format: str = "continuous_multi_day",
    distance_km: str = "250",
) -> RaceEventPayload:
    return RaceEventPayload(
        race_event_id=1,
        user_id=1,
        name=name,
        event_date=_TODAY + timedelta(weeks=weeks),
        race_format=race_format,
        distance_km=Decimal(distance_km),
        is_target_event=True,
        event_locale_id="nerstrand-mn",
        route_locales=[],
    )


class TestLayer3BSmokeScenarios:
    """§13 regression scenarios beyond TS-1/TS-4. Real-LLM, gated on the key.
    Assertions are structural + loose-enum to absorb minor model variance."""

    def test_ts2_ar_podium_4_weeks_unrealistic(self):
        """§13 TS-2 — Podium attempt only 4 weeks out (unrealistic). Expect
        unrealistic-as-stated viability + a blocker HITL + compressed shape."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(
                aerobic_level="moderate", strength_level="moderate"
            ),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_race_event_weeks_out(4, name="Short AR"),
            current_date=_TODAY,
            etl_version_set=_ETL,
            goal_outcome="Podium attempt",
            first_time_at_distance=False,
            previous_attempts=[],
        )
        assert payload.input_tokens > 0 and payload.output_tokens > 0
        assert payload.mode == "event"
        assert payload.time_to_event_weeks is not None
        assert 3 <= payload.time_to_event_weeks <= 5
        assert payload.goal_viability.viability == "unrealistic-as-stated"
        blockers = [h for h in payload.hitl_surface if h.severity == "blocker"]
        assert blockers, "expected a blocker HITL for a 4-week podium goal"
        assert payload.periodization_shape.mode in {"compressed", "custom"}

    def test_ts3_trail_half_first_time_12_weeks(self):
        """§13 TS-3 — first-time competitive trail half, 12 weeks out. Expect
        achievable-with-adjustment + a first-time warning HITL + standard."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Trail Running"),
            layer3a_payload=_make_layer3a(
                aerobic_level="moderate",
                strength_level="good",
                short_term="steady",
                trajectory_confidence="high",
            ),
            layer2a_payload=_make_layer2a(framework_sport="Trail Running"),
            race_event_payload=_race_event_weeks_out(
                12, name="Trail Half", distance_km="21"
            ),
            current_date=_TODAY,
            etl_version_set=_ETL,
            goal_outcome="Compete mid-pack",
            first_time_at_distance=True,
            previous_attempts=[],
        )
        assert payload.mode == "event"
        assert payload.goal_viability.viability in {
            "achievable",
            "achievable-with-adjustment",
        }
        warnings = [h for h in payload.hitl_surface if h.severity == "warning"]
        assert warnings, "expected a first-time competitive-goal warning HITL"
        assert payload.periodization_shape.mode in {"standard", "compressed"}

    def test_ts5_no_event_strength_8_weeks_low_base(self):
        """§13 TS-5 — 8-week no-event strength block from a low strength base
        (primary sport cycling). Expect achievable-with-adjustment + an
        extended/longer-base shape; no blocker HITL."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Road Cycling"),
            layer3a_payload=_make_layer3a(
                strength_level="low", aerobic_level="good"
            ),
            layer2a_payload=_make_layer2a(framework_sport="Road Cycling"),
            race_event_payload=None,
            current_date=_TODAY,
            etl_version_set=_ETL,
            plan_duration_weeks=8,
            non_event_goal_type="strength",
        )
        assert payload.mode == "no-event"
        assert payload.goal_viability.viability in {
            "achievable",
            "achievable-with-adjustment",
        }
        assert payload.periodization_shape.mode in {
            "standard",
            "extended",
            "custom",
        }
        blockers = [h for h in payload.hitl_surface if h.severity == "blocker"]
        assert not blockers

    def test_ts6_ultra_prior_dnf_12_weeks(self):
        """§13 TS-6 — 100-mile ultra Finish with a prior DNF (quad_failure),
        12 weeks out. Expect achievable-with-adjustment + no blocker (the DNF
        window is borderline → warning, not blocker)."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Trail Running"),
            layer3a_payload=_make_layer3a(
                aerobic_level="good", strength_level="moderate"
            ),
            layer2a_payload=_make_layer2a(framework_sport="Trail Running"),
            race_event_payload=_race_event_weeks_out(
                12, name="100-mile Ultra", distance_km="161"
            ),
            current_date=_TODAY,
            etl_version_set=_ETL,
            goal_outcome="Finish",
            first_time_at_distance=False,
            previous_attempts=[{"outcome": "DNF", "dnf_cause": "quad_failure"}],
        )
        assert payload.mode == "event"
        assert payload.goal_viability.viability in {
            "achievable",
            "achievable-with-adjustment",
        }
        blockers = [h for h in payload.hitl_surface if h.severity == "blocker"]
        assert not blockers, "DNF 12-weeks-out should warn, not block"
        assert payload.periodization_shape.mode in {
            "standard",
            "compressed",
            "extended",
        }

    def test_ts7_event_one_week_away(self):
        """§13 TS-7 — event ~1 week out. Expect a compressed taper-anchored
        shape regardless of goal."""
        payload = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_race_event_weeks_out(1, name="Imminent AR"),
            current_date=_TODAY,
            etl_version_set=_ETL,
            goal_outcome="Finish",
            first_time_at_distance=False,
            previous_attempts=[{"outcome": "Finished", "dnf_cause": ""}],
        )
        assert payload.mode == "event"
        assert payload.time_to_event_weeks is not None
        assert payload.time_to_event_weeks <= 2
        assert payload.periodization_shape.mode in {"compressed", "custom"}
        assert payload.periodization_shape.start_phase in {"Taper", "Peak"}
