"""Real-LLM smoke tests for `layer3a.builder.llm_layer3a_athlete_state`.

Per `Upstream_Implementation_Plan_v1.md` §4 row Layer-4-Step-7 +
`Layer3A_v1.md` §12 L3A-P-1 — exercises the production Anthropic SDK
adapter (`_default_llm_caller`) against real Sonnet 4.6. Gated on
`ANTHROPIC_API_KEY` via the `requires_anthropic_api_key` skipif marker
from `tests/conftest.py`; default `pytest tests/` runs ignore this file.

Two scenarios mirror §13 spec fixtures:

- **Dense data, fit athlete** (~§13.1 shape) — rich integration bundle +
  experienced AR athlete; expect `aerobic_capacity.level ∈ {good, strong}`
  + high/medium trajectory confidence.
- **Sparse data, returning athlete** (~§13.4 shape) — empty integration
  bundle + structured training history; expect `recent_trajectory.confidence
  == low` + detrained-or-insufficient_data short_term direction +
  data-density observation appended by the confidence-floor clamp.

Assertions are mixed structural (payload validates, metadata stamped,
evidence_basis non-empty) + loose enum (allowlist sets) to absorb minor
classification variance across Sonnet 4.6 minor versions without false
positives.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from conftest import requires_anthropic_api_key

from layer3a.builder import llm_layer3a_athlete_state
from layer4.context import (
    ACWREntry,
    CombinedLoadReport,
    DailyWellnessRecord,
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
    Layer3AIntegrationBundle,
    ProviderStatus,
    RationaleMetadata,
    SleepRecord,
    TrainingGapsSummary,
    WeightResult,
    WorkoutRecord,
)

pytestmark = requires_anthropic_api_key

_ETL = {"0A": "v1", "0B": "v1", "0C": "v1"}
_AS_OF = datetime(2026, 5, 20, 0, 0)


def _make_layer1(
    *,
    years_structured_training: int = 5,
    peak_weekly_volume_hrs: float = 12.0,
    pushup_max_reps: int | None = 40,
    cycling_ftp_w: int | None = 240,
    primary_sport: str = "Adventure Racing",
) -> Layer1Payload:
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
            years_structured_training=years_structured_training,
            peak_weekly_volume_hrs=peak_weekly_volume_hrs,
            peak_weekly_volume_year=2024,
            longest_event_completed="50-mile ultra",
            discipline_weighting=[
                DisciplineWeightRecord(discipline_slug="run", weight_pct=40),
                DisciplineWeightRecord(discipline_slug="bike", weight_pct=40),
                DisciplineWeightRecord(discipline_slug="paddle", weight_pct=20),
            ],
        ),
        discipline_baselines=Layer1DisciplineBaselines(),
        strength_benchmarks=Layer1StrengthBenchmarks(
            front_plank_sec=180,
            pushup_max_reps=pushup_max_reps,
            dead_hang_sec=60,
        ),
        performance=Layer1Performance(
            body_weight_kg=75.0,
            hrmax_bpm=185,
            cycling_ftp_w=cycling_ftp_w,
            cycling_ftp_test_date=date(2026, 1, 15),
        ),
        availability=Layer1Availability(),
        event_goal=Layer1EventGoal(),
        lifestyle=Layer1Lifestyle(
            sleep_baseline_hours=7.5,
            work_stress_level="moderate",
        ),
        network=Layer1Network(),
        disclosures=Layer1Disclosures(),
    )


def _make_layer2a() -> Layer2APayload:
    return Layer2APayload(
        framework_sport="Adventure Racing",
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
                rationale="AR baseline.",
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


def _make_bundle_dense() -> Layer3AIntegrationBundle:
    workouts = [
        WorkoutRecord(
            date=_AS_OF.date() - timedelta(days=i),
            activity="Run" if i % 2 == 0 else "Bike",
            duration_min=60.0 + (i % 4) * 15.0,
            distance_mi=6.0 + (i % 4) * 2.0,
            avg_hr=145 + (i % 3) * 5,
            source="garmin",
        )
        for i in range(20)
    ]
    wellness = [
        DailyWellnessRecord(
            date=_AS_OF.date() - timedelta(days=i),
            total_sleep_hours=7.5,
            total_sleep_hours_source="polar",
            hrv_rmssd_ms=45.0 - (i * 0.2),
            hrv_rmssd_ms_source="polar",
            resting_hr=48,
            resting_hr_source="garmin",
        )
        for i in range(14)
    ]
    self_report_sleep = [
        SleepRecord(
            date=_AS_OF.date() - timedelta(days=i),
            total_sleep_hours=7.5,
            sleep_quality=8 if i % 2 == 0 else 7,
        )
        for i in range(14)
    ]
    combined = ACWREntry(
        acute_load=8.0,
        chronic_load=7.0,
        ratio=1.14,
        zone="sweet_spot",
        units="hours",
    )
    return Layer3AIntegrationBundle(
        as_of=_AS_OF,
        recent_workouts=workouts,
        recent_wellness=wellness,
        recent_self_report_sleep=self_report_sleep,
        combined_load=CombinedLoadReport(
            per_discipline={},
            combined=combined,
            units="hours",
            polar_cross_ref=None,
        ),
        connected_providers=[
            ProviderStatus(
                provider="garmin",
                status="active",
                last_sync=_AS_OF - timedelta(hours=2),
                has_recent_workouts=True,
                has_recent_sleep=False,
                has_recent_hrv=False,
            ),
            ProviderStatus(
                provider="polar",
                status="active",
                last_sync=_AS_OF - timedelta(hours=4),
                has_recent_workouts=False,
                has_recent_sleep=True,
                has_recent_hrv=True,
            ),
        ],
    )


def _make_bundle_sparse() -> Layer3AIntegrationBundle:
    return Layer3AIntegrationBundle(
        as_of=_AS_OF,
        recent_workouts=[],
        recent_wellness=[],
        recent_self_report_sleep=[],
        combined_load=CombinedLoadReport(
            per_discipline={},
            combined=None,
            units="hours",
            polar_cross_ref=None,
        ),
        connected_providers=[],
    )


# ─── Smoke tests ─────────────────────────────────────────────────────────────


class TestLayer3ASmoke:
    """Real-LLM round-trip against Sonnet 4.6. Gated on ANTHROPIC_API_KEY."""

    def test_dense_data_fit_athlete(self):
        """§13.1 dense-data fit-athlete: experienced AR athlete with rich
        integration bundle. Expect good/strong aerobic + high/medium
        trajectory confidence + sweet_spot ACWR zone preserved."""
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle_dense(),
            as_of=_AS_OF,
            etl_version_set=_ETL,
        )

        # Structural — driver-stamped metadata
        assert payload.user_id == 1
        assert payload.model == "claude-sonnet-4-6"
        assert payload.temperature == 0.0
        assert payload.input_tokens > 0
        assert payload.output_tokens > 0
        assert payload.latency_ms > 0
        assert len(payload.prompt_hash) == 64
        assert payload.etl_version_set == _ETL

        # Loose enum — fit athlete should land in good-or-strong band
        assert payload.current_state.aerobic_capacity.level in {
            "good",
            "strong",
        }, f"unexpected aerobic level for fit athlete: {payload.current_state.aerobic_capacity.level}"
        assert payload.current_state.aerobic_capacity.confidence in {
            "high",
            "medium",
        }
        assert payload.current_state.strength.level in {
            "moderate",
            "good",
            "strong",
        }
        # Evidence basis non-empty
        assert payload.current_state.aerobic_capacity.evidence_basis
        assert payload.current_state.strength.evidence_basis
        # Reasoning text non-empty
        assert payload.current_state.aerobic_capacity.reasoning_text.strip()
        # ACWR sweet_spot preserved from integration data
        assert payload.recent_trajectory.acwr_status.combined is not None
        assert payload.recent_trajectory.acwr_status.combined.zone in {
            "sweet_spot",
            "functional_overreach",
        }

    def test_sparse_data_returning_athlete(self):
        """§13.4 sparse-data: experienced athlete (5y training base) with
        no recent activity. Expect low trajectory confidence + detrained or
        insufficient_data short_term + the §6.3
        confidence_clamped_by_data_density observation appended by the
        floor-clamp post-LLM transform."""
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(years_structured_training=5),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle_sparse(),
            as_of=_AS_OF,
            etl_version_set=_ETL,
        )

        # Structural
        assert payload.input_tokens > 0
        assert payload.output_tokens > 0
        assert payload.latency_ms > 0

        # Sparse data → recent_trajectory.confidence should clamp to low
        # (§6.2 floor rule 1: no providers + no integration data).
        assert payload.recent_trajectory.confidence == "low"

        # Short-term direction should reflect the absence of activity
        assert payload.recent_trajectory.short_term.direction in {
            "detrained",
            "insufficient_data",
        }

        # ACWR combined should be None given empty bundle
        assert payload.recent_trajectory.acwr_status.combined is None

        # Floor-clamp post-LLM transform should append the
        # confidence_clamped_by_data_density observation per §6.3.
        clamp_obs = [
            o
            for o in payload.notable_observations
            if "clamped" in o.text.lower() or o.category == "data_gap"
        ]
        assert clamp_obs, (
            "expected at least one data_gap/clamp observation given sparse "
            f"data; got {[o.category for o in payload.notable_observations]}"
        )


# ─── §13 regression scenarios 13.2 / 13.3 / 13.6 / 13.10 ────────────────────
#
# 13.1 (dense-fit) + 13.4 (sparse-returning) are the two scenarios above.
# 13.7 (missing primary_sport → Layer3AInputError, no LLM call) is an
# input-error case covered in tests/test_layer3a_builder.py, so it isn't
# duplicated in this key-gated module. 13.5 (pregnancy) / 13.8 (model-swap) /
# 13.9 (volume conflict-flag) are tracked separately (#225) — 13.8 needs a
# second model and 13.5/13.9 need extra fixture plumbing.


def _make_bundle(
    *,
    n_workouts: int = 20,
    providers: bool = True,
    workout_source: str = "garmin",
    ratio: float | None = 1.14,
    zone: str = "sweet_spot",
    with_sleep: bool = True,
    sleep_hours: float = 7.5,
) -> Layer3AIntegrationBundle:
    """Flexible integration bundle for the §13 scenarios. `providers=False`
    drops connected providers (manual-log shape); `ratio=None` leaves the
    combined ACWR unpopulated (sparse shape)."""
    workouts = [
        WorkoutRecord(
            date=_AS_OF.date() - timedelta(days=i),
            activity="Run" if i % 2 == 0 else "Bike",
            duration_min=60.0 + (i % 4) * 15.0,
            distance_mi=6.0 + (i % 4) * 2.0,
            avg_hr=145 + (i % 3) * 5,
            source=workout_source,
        )
        for i in range(n_workouts)
    ]
    # Device sleep (no HRV in these scenarios → preserves the old recent_hrv=[]
    # shape so the §6.2 "no recent HRV" floor still fires).
    wellness = (
        [
            DailyWellnessRecord(
                date=_AS_OF.date() - timedelta(days=i),
                total_sleep_hours=sleep_hours,
                total_sleep_hours_source="polar",
            )
            for i in range(14)
        ]
        if (with_sleep and providers)
        else []
    )
    self_report_sleep = (
        [
            SleepRecord(
                date=_AS_OF.date() - timedelta(days=i),
                total_sleep_hours=sleep_hours,
                sleep_quality=8 if i % 2 == 0 else 7,
            )
            for i in range(14)
        ]
        if (with_sleep and providers)
        else []
    )
    combined = (
        None
        if ratio is None
        else ACWREntry(
            acute_load=round(7.0 * ratio, 2),
            chronic_load=7.0,
            ratio=ratio,
            zone=zone,
            units="hours",
        )
    )
    provs = (
        [
            ProviderStatus(
                provider="garmin",
                status="active",
                last_sync=_AS_OF - timedelta(hours=2),
                has_recent_workouts=True,
                has_recent_sleep=False,
                has_recent_hrv=False,
            )
        ]
        if providers
        else []
    )
    return Layer3AIntegrationBundle(
        as_of=_AS_OF,
        recent_workouts=workouts,
        recent_wellness=wellness,
        recent_self_report_sleep=self_report_sleep,
        combined_load=CombinedLoadReport(
            per_discipline={},
            combined=combined,
            units="hours",
            polar_cross_ref=None,
        ),
        connected_providers=provs,
    )


class TestLayer3ASmokeScenarios:
    """§13 regression scenarios beyond 13.1/13.4. Real-LLM, gated on the key."""

    def test_13_2_sparse_new_athlete(self):
        """§13.2 — new athlete, ~6 weeks history, 8 manual entries, no
        providers. Expect low trajectory confidence + a data_gap, and an
        aerobic read no higher than 'good' with non-high confidence."""
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(
                years_structured_training=1,
                peak_weekly_volume_hrs=3.0,
                pushup_max_reps=None,
                cycling_ftp_w=None,
            ),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(
                n_workouts=8, providers=False, workout_source="manual", ratio=None
            ),
            as_of=_AS_OF,
            etl_version_set=_ETL,
        )
        assert payload.input_tokens > 0 and payload.output_tokens > 0
        assert payload.recent_trajectory.confidence == "low"
        assert payload.current_state.aerobic_capacity.confidence in {"low", "medium"}
        assert payload.current_state.aerobic_capacity.level in {
            "low",
            "moderate",
            "good",
            "insufficient_data",
        }
        gaps = [o for o in payload.notable_observations if o.category == "data_gap"]
        assert gaps, "expected a data_gap observation for a sparse new athlete"

    def test_13_3_conflicting_signals(self):
        """§13.3 — high logged volume + functional-overreach ACWR + short
        sleep. Expect a solid aerobic read but a fatigue-leaning trajectory
        and at least one warning/data_hygiene observation."""
        l1 = _make_layer1()
        l1.lifestyle.sleep_baseline_hours = 5.5
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=l1,
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(
                n_workouts=24, ratio=1.45, zone="non_functional_overreach"
            ),
            as_of=_AS_OF,
            etl_version_set=_ETL,
        )
        assert payload.current_state.aerobic_capacity.level in {"good", "strong"}
        assert payload.recent_trajectory.short_term.direction in {
            "fatigued",
            "overreached",
            "steady",
        }
        flagged = [
            o
            for o in payload.notable_observations
            if o.category in {"warning", "data_hygiene"}
        ]
        assert flagged, "expected a warning/data_hygiene observation on conflict"

    def test_13_6_no_providers_rich_self_report(self):
        """§13.6 — rich manual cardio_log (35 entries), no providers. Expect
        a plausible aerobic read at non-high confidence + a provider-gap
        data_gap observation, with combined ACWR populated from the log."""
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(years_structured_training=4),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(
                n_workouts=35, providers=False, workout_source="manual", ratio=1.05
            ),
            as_of=_AS_OF,
            etl_version_set=_ETL,
        )
        assert payload.input_tokens > 0
        assert payload.current_state.aerobic_capacity.confidence in {"low", "medium"}
        assert payload.recent_trajectory.acwr_status.combined is not None
        gaps = [o for o in payload.notable_observations if o.category == "data_gap"]
        assert gaps, "expected a provider-connection data_gap observation"

    def test_13_10_acwr_red_zone(self):
        """§13.10 — combined ACWR 1.62 (non-functional overreach). Expect a
        warning observation and a fatigue-leaning short-term trajectory."""
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(
                n_workouts=24, ratio=1.62, zone="non_functional_overreach"
            ),
            as_of=_AS_OF,
            etl_version_set=_ETL,
        )
        warnings = [o for o in payload.notable_observations if o.category == "warning"]
        assert warnings, "expected a warning observation for a red-zone ACWR"
        assert payload.recent_trajectory.short_term.direction in {
            "overreached",
            "fatigued",
            "steady",
        }
