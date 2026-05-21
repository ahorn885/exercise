"""Tests for `layer4/orchestrator.py` — Phase 5.1 race_week_brief vertical
slice.

Coverage:
- Happy-path composition: all upstream builders + LLM drivers invoked in
  dependency order; arguments threaded correctly; `Layer4Payload` returned.
- Pre-flight gates: no target event, race-week-brief-too-early (cheap
  optimization that skips the 3A + 3B LLM cost when out-of-window).
- Discovery failures: etl_version_set undiscoverable, primary locale
  missing, framework_sport empty.
- `today` kwarg defaulting to `date.today()` for production callers.
- `Layer2ETargetEvent` derivation from `RaceEventPayload`.

Each upstream builder + LLM driver is stubbed at the module-level import
on `layer4.orchestrator` via `unittest.mock.patch`. The fake `db` only
needs to answer the orchestrator's direct queries
(`_q_current_etl_version_set`, `_q_primary_locale`, `_q_locale_equipment_pool`,
`load_target_race_event_payload`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import patch

import pytest

from layer4 import (
    InMemoryCacheBackend,
    Layer4Cache,
    OrchestrationError,
    ParsedIntent,
    SingleSessionRequest,
    orchestrate_plan_create,
    orchestrate_plan_refresh,
    orchestrate_race_week_brief,
    orchestrate_single_session_synthesize,
)
from layer2a.builder import Layer2AInputError
from layer4.context import (
    ACWRStatus,
    Assessment,
    CurrentState,
    DataDensity,
    GoalViability,
    Layer1Disclosures,
    Layer1DisciplineBaselines,
    Layer1EventGoal,
    Layer1Availability,
    Layer1Identity,
    Layer1HealthStatus,
    Layer1Lifestyle,
    Layer1Network,
    Layer1Payload,
    Layer1Performance,
    Layer1TrainingHistory,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2BPayload,
    Layer2BSummaryBlock,
    Layer2Bundle,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3APayload,
    Layer3BPayload,
    MacroTargets,
    DailyNutritionBaseline,
    DailyPhaseTargets,
    PeriodizationShape,
    PhaseLoadBands,
    RaceDayFueling,
    RaceEventPayload,
    RationaleMetadata,
    RecentTrajectory,
    SupplementIntegrationPayload,
    TrainingGapsSummary,
    TrajectoryWindow,
    WeightResult,
)
from layer4.payload import (
    CardioBlock,
    HRTarget,
    Layer4Payload,
    PhaseStructure,
    PlanSession,
    RaceWeekBrief,
    ValidatorResult,
)


_TODAY = date(2026, 6, 1)
_EVENT_DATE = date(2026, 6, 8)  # 7 days out — within auto-fire window
_USER_ID = 42


# ─── _FakeConn — covers the orchestrator's direct queries + race_events_repo ─


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []

    def queue(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)


def _queue_target_race_event(
    conn: _FakeConn,
    *,
    race_event_id: int = 1,
    event_date: date = _EVENT_DATE,
    race_format: str = "single_day",
    race_terrain: list | None = None,
    aid_stations: int | None = None,
) -> None:
    """Queue responses for `load_target_race_event_payload` (3 SELECTs when
    route_locales empty: target_id lookup + main row + route_locales).
    Equipment SELECT is skipped because route_locales is empty."""
    conn.queue(row={"id": race_event_id})  # target lookup
    conn.queue(  # main race_events row
        row={
            "id": race_event_id,
            "user_id": _USER_ID,
            "name": "Test Race 2026",
            "event_date": event_date,
            "race_format": race_format,
            "distance_km": None,
            "total_elevation_gain_m": None,
            "race_rules_summary": None,
            "mandatory_gear_text": None,
            "event_locale_slug": "home",
            "is_target_event": True,
            "notes": None,
            "race_terrain": race_terrain if race_terrain is not None else [],
            "aid_stations": aid_stations,
            # D-73 Phase 5.2 walkthrough #1 + #2a (2026-05-21) — race-events
            # rows now carry Mapbox-anchored race location + race_url. None
            # values exercise the pre-walkthrough row shape (athlete hasn't
            # yet picked a Mapbox anchor).
            "event_locale_name": None,
            "event_locale_mapbox_id": None,
            "event_locale_place_name": None,
            "event_locale_lat": None,
            "event_locale_lng": None,
            "race_url": None,
        }
    )
    conn.queue(rows=[])  # route_locales (empty for single_day)


def _queue_etl_version_set(conn: _FakeConn, *, v: str = "v7") -> None:
    conn.queue(row={"v": v})


def _queue_primary_locale(conn: _FakeConn, *, locale: str = "home") -> None:
    conn.queue(row={"locale": locale})


def _queue_locale_equipment_pool(conn: _FakeConn) -> None:
    conn.queue(rows=[])  # empty pool — Layer 2C handles


# ─── Stub upstream-payload factories ────────────────────────────────────────


def _fake_layer1_payload() -> Layer1Payload:
    return Layer1Payload(
        user_id=_USER_ID,
        as_of=datetime.combine(_TODAY, datetime.min.time()),
        identity=Layer1Identity(primary_sport="AR"),
        health_status=Layer1HealthStatus(),
        training_history=Layer1TrainingHistory(),
        discipline_baselines=Layer1DisciplineBaselines(),
        performance=Layer1Performance(),
        availability=Layer1Availability(),
        event_goal=Layer1EventGoal(),
        lifestyle=Layer1Lifestyle(),
        network=Layer1Network(),
        disclosures=Layer1Disclosures(),
    )


def _fake_layer2a_payload() -> Layer2APayload:
    return Layer2APayload(
        framework_sport="AR",
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        disciplines=[
            Layer2ADiscipline(
                discipline_id="D-trail",
                discipline_name="trail_running",
                inclusion="included",
                role="Primary",
                is_conditional=False,
                load_weight=WeightResult(
                    value=0.5, source="system_default", system_default=0.5
                ),
                sleep_deprivation_relevant=False,
                rationale="r",
                phase_load=PhaseLoadBands(
                    base_low=5.0,
                    base_high=8.0,
                    build_low=6.0,
                    build_high=9.0,
                    peak_low=6.5,
                    peak_high=9.5,
                    taper_low=3.0,
                    taper_high=6.0,
                    default_inclusion="included",
                ),
            )
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
            template_version="v1", generated_at="2026-06-01T10:00:00Z"
        ),
    )


def _fake_layer2b_payload() -> Layer2BPayload:
    return Layer2BPayload(
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        race_terrain=[],
        terrain_gaps=[],
        coaching_flags=[],
        summary=Layer2BSummaryBlock(
            total_race_terrain_count=0,
            covered_count=0,
            gap_count=0,
            bridgeable_count=0,
            unbridgeable_count=0,
            min_adaptation_weeks_needed=0,
            worst_fidelity=1.0,
            pct_of_race_uncovered=0.0,
            any_unbridgeable=False,
            any_undefined=False,
        ),
    )


def _fake_layer2c_payload() -> Layer2CPayload:
    return Layer2CPayload(
        locale_id="home",
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        effective_pool=[],
        discipline_coverage=[],
        exercises_resolved=[],
        coaching_flags=[],
    )


def _fake_layer2d_payload() -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        excluded_exercises=[],
        accommodated_exercises=[],
        clean_exercise_ids=[],
        discipline_risk_profiles=[],
        coaching_flags=[],
        hitl_required=False,
        hitl_items=[],
        body_part_vocab_misses=[],
        condition_vocab_misses=[],
    )


def _fake_layer2e_payload() -> Layer2EPayload:
    macros = MacroTargets(
        cho_g=400,
        cho_g_per_kg=5.7,
        cho_kcal=1600,
        protein_g=140,
        protein_g_per_kg=2.0,
        protein_kcal=560,
        fat_g=70,
        fat_kcal=630,
        fat_floor_constrained=False,
    )
    targets = DailyPhaseTargets(
        activity_multiplier=1.6,
        activity_multiplier_source={"row": "base"},
        daily_calorie_target_kcal=2800,
        macros=macros,
    )
    return Layer2EPayload(
        athlete_id=str(_USER_ID),
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        computed_at=datetime(2026, 6, 1, 10, 0, 0),
        bmr_method="mifflin_st_jeor",
        bmr_kcal=1750.0,
        daily_nutrition_baseline=DailyNutritionBaseline(
            per_phase={
                "Base": targets,
                "Build": targets,
                "Peak": targets,
                "Taper": targets,
            }
        ),
        race_day_fueling=[
            RaceDayFueling(
                event_id="1",
                event_name="Test Race 2026",
                duration_tier="tier_long",
                cho_g_per_hr_low=60.0,
                cho_g_per_hr_high=90.0,
                na_mg_per_hr_low=500.0,
                na_mg_per_hr_high=700.0,
                fluid_ml_per_hr_low=500.0,
                fluid_ml_per_hr_high=700.0,
                sport_modifier_applied=1.0,
                salt_tolerance_modifier_applied=1.0,
                heat_acclim_modifier_applied=1.0,
                recommended_formats=[],
                blocked_formats=[],
                sleep_dep_overlay_applies=False,
                notes=[],
            )
        ],
        supplement_integration=SupplementIntegrationPayload(
            integrated=[],
            race_day_suggestions=[],
            contraindication_flags=[],
            contraindication_hitl_items=[],
        ),
        dietary_pattern_adjustments=[],
        sleep_dep_overlay=None,
        heat_acclim_adjustments=[],
        coaching_flags=[],
        hitl_items=[],
        hitl_required=False,
    )


def _fake_layer3a_payload() -> Layer3APayload:
    return Layer3APayload(
        user_id=_USER_ID,
        as_of=datetime.combine(_TODAY, datetime.min.time()),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1000,
        input_tokens=2000,
        output_tokens=500,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        current_state=CurrentState(
            aerobic_capacity=Assessment(
                level="good", confidence="high", reasoning_text="r", evidence_basis=["e"]
            ),
            strength=Assessment(
                level="moderate",
                confidence="medium",
                reasoning_text="r",
                evidence_basis=["e"],
            ),
            weak_links=[],
            skill_assessments={},
        ),
        recent_trajectory=RecentTrajectory(
            short_term=TrajectoryWindow(
                direction="steady", reasoning_text="r", evidence_basis=["e"]
            ),
            medium_term=TrajectoryWindow(
                direction="building", reasoning_text="r", evidence_basis=["e"]
            ),
            acwr_status=ACWRStatus(per_discipline={}, combined=None),
            confidence="medium",
        ),
        data_density=DataDensity(
            connected_providers=["coros"],
            integration_data_days=28,
            recent_workouts_count=20,
            recent_sleep_count=14,
            recent_hrv_count=14,
            self_report_freshness_days=2,
            section_completeness={"C": 1.0},
        ),
        notable_observations=[],
    )


def _fake_layer3b_payload(
    *,
    event_date: date = _EVENT_DATE,
    start_phase: str = "Taper",
) -> Layer3BPayload:
    return Layer3BPayload(
        user_id=_USER_ID,
        as_of=datetime.combine(_TODAY, datetime.min.time()),
        mode="event",
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1000,
        input_tokens=2000,
        output_tokens=500,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="r",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode="standard",
            start_phase=start_phase,  # type: ignore[arg-type]
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        hitl_surface=[],
        notable_observations=[],
        event_date=event_date,
        event_locale_id="home",
        race_format="single_day",
        time_to_event_weeks=1,
    )


def _fake_layer4_payload(
    *,
    race_event_payload: RaceEventPayload,
) -> Layer4Payload:
    return Layer4Payload(
        user_id=_USER_ID,
        mode="race_week_brief",
        plan_version_id=1,
        scope_start_date=_TODAY,
        scope_end_date=race_event_payload.event_date,
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.2,
        pattern="B",
        latency_ms_total=8000,
        input_tokens_total=4500,
        output_tokens_total=2500,
        llm_call_count=1,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        sessions=[],
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
        # race_week_brief always uses single_day in the test fake to avoid
        # needing a separate race_plan stub — the orchestrator doesn't
        # validate the wrapper's return value, so the format inside the
        # cached-wrapper return value is independent of the test's
        # `race_format` axis.
        race_week_brief=RaceWeekBrief(
            days_to_event=(race_event_payload.event_date - _TODAY).days,
            event_name=race_event_payload.name,
            event_date=race_event_payload.event_date,
            event_locale="home",
            race_format="single_day",
            goal_outcome="Finish",
            pre_race_logistics="x",
            kit_manifest=[],
            kit_check_dates=[],
            race_day_fueling_plan="x",
            pre_race_meal_strategy="x",
            pacing_strategy_summary="x",
            contingencies=[],
            mental_prep_cues=[],
        ),
    )


# ─── happy path ─────────────────────────────────────────────────────────────


def _patches(*, layer4_return: Layer4Payload):
    """Stack of patches that swap upstream builders / LLM drivers for the
    happy-path composition. Returns a list of `patch` context managers — the
    caller enters all of them."""
    return [
        patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2b_terrain_classifier_payload",
            return_value=_fake_layer2b_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2c_equipment_mapper_payload",
            return_value=_fake_layer2c_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2d_injury_risk_profile_payload",
            return_value=_fake_layer2d_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2e_nutrition_baseline_payload",
            return_value=_fake_layer2e_payload(),
        ),
        patch(
            "layer4.orchestrator.assemble_layer3a_integration_bundle",
            return_value=object(),  # opaque — only re-threaded into 3A
        ),
        patch(
            "layer4.orchestrator.llm_layer3a_athlete_state_cached",
            return_value=_fake_layer3a_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer3b_goal_timeline_viability_cached",
            return_value=_fake_layer3b_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer4_race_week_brief_cached",
            return_value=layer4_return,
        ),
    ]


def _enter_all(stack: list) -> list[Any]:
    """Enter a list of context managers; return the entered mocks in order.
    The caller is responsible for `__exit__`-ing via a try/finally."""
    return [cm.__enter__() for cm in stack]


def _exit_all(stack: list) -> None:
    for cm in stack:
        cm.__exit__(None, None, None)


class TestHappyPath:
    def test_returns_layer4_payload_and_invokes_pipeline_in_order(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        layer4_out = _fake_layer4_payload(race_event_payload=race_event_for_l4)
        stack = _patches(layer4_return=layer4_out)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_race_week_brief(
                conn, _USER_ID, cache=cache, today=_TODAY
            )
        finally:
            _exit_all(stack)

        assert isinstance(result, Layer4Payload)
        assert result.mode == "race_week_brief"
        assert result.user_id == _USER_ID

        # Pipeline ordering — Layer 1 first, Layer 4 last.
        (
            m_l1,
            m_l2a,
            m_l2b,
            m_l2c,
            m_l2d,
            m_l2e,
            m_bundle,
            m_l3a,
            m_l3b,
            m_l4,
        ) = mocks
        for m in mocks:
            assert m.call_count == 1

        # Layer 2E receives `current_phase` from 3B's `start_phase` — verifies
        # the 2A/2B/2D/2C → 3A → 3B → 2E ordering decision.
        l2e_kwargs = m_l2e.call_args.kwargs
        assert l2e_kwargs["current_phase"] == "Taper"
        assert l2e_kwargs["framework_sport"] == "AR"
        # target_events derives from RaceEventPayload (single Layer2ETargetEvent)
        assert len(l2e_kwargs["target_events"]) == 1
        te = l2e_kwargs["target_events"][0]
        assert te.event_id == "1"
        assert te.event_name == "Test Race 2026"
        assert te.framework_sport == "AR"
        # single_day → 8.0 hour estimate
        assert te.estimated_duration_hr == 8.0

        # Layer 4 cached wrapper receives composed payloads
        l4_kwargs = m_l4.call_args.kwargs
        assert l4_kwargs["user_id"] == _USER_ID
        assert l4_kwargs["plan_version_id"] == 1
        assert l4_kwargs["prior_plan_session_window"] == []
        assert l4_kwargs["cache"] is cache
        assert l4_kwargs["today"] == _TODAY
        assert l4_kwargs["etl_version_set"] == {"0A": "v7", "0B": "v7", "0C": "v7"}
        # layer1_payload threaded as dict (not pydantic model)
        assert isinstance(l4_kwargs["layer1_payload"], dict)
        # Per-locale dict keyed by primary locale slug
        assert set(l4_kwargs["layer2c_payloads"].keys()) == {"home"}


# ─── pre-flight gates ───────────────────────────────────────────────────────


class TestPreflightGates:
    def test_no_target_event_raises(self):
        conn = _FakeConn()
        # load_target_race_event_payload's first SELECT returns None
        conn.queue(row=None)
        cache = Layer4Cache(InMemoryCacheBackend())

        with pytest.raises(OrchestrationError) as exc:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        assert exc.value.code == "no_target_event"

    def test_race_week_brief_too_early_raises_before_upstream_calls(self):
        """Pre-flight check fires BEFORE Layer 1 / 2A / 3A LLM cost."""
        conn = _FakeConn()
        # Event 30 days out — outside auto-fire window
        _queue_target_race_event(conn, event_date=_TODAY.replace(month=7, day=1))
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _patches(
            layer4_return=_fake_layer4_payload(
                race_event_payload=RaceEventPayload(
                    race_event_id=1,
                    user_id=_USER_ID,
                    name="x",
                    event_date=_EVENT_DATE,
                    race_format="single_day",
                    is_target_event=True,
                )
            )
        )
        mocks = _enter_all(stack)
        try:
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_race_week_brief(
                    conn, _USER_ID, cache=cache, today=_TODAY
                )
        finally:
            _exit_all(stack)

        assert exc.value.code == "race_week_brief_too_early"
        assert "days_to_event=30" in exc.value.detail
        # None of the upstream stages were entered.
        for m in mocks:
            assert m.call_count == 0


# ─── discovery failures ─────────────────────────────────────────────────────


class TestDiscoveryFailures:
    def test_etl_version_set_undiscoverable(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        conn.queue(row={"v": None})  # etl_version_set lookup returns NULL
        cache = Layer4Cache(InMemoryCacheBackend())

        with pytest.raises(OrchestrationError) as exc:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        assert exc.value.code == "etl_version_set_undiscoverable"

    def test_primary_locale_missing(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        # build_layer1_payload is stubbed; orchestrator proceeds to
        # _q_primary_locale next. Then _q_locale_equipment_pool.
        conn.queue(row=None)  # locale_profiles lookup returns no row
        cache = Layer4Cache(InMemoryCacheBackend())

        with patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ), patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ), patch(
            "layer4.orchestrator.q_layer2b_terrain_classifier_payload",
            return_value=_fake_layer2b_payload(),
        ), patch(
            "layer4.orchestrator.q_layer2d_injury_risk_profile_payload",
            return_value=_fake_layer2d_payload(),
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_race_week_brief(
                    conn, _USER_ID, cache=cache, today=_TODAY
                )
        assert exc.value.code == "primary_locale_missing"

    def test_framework_sport_missing(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        # Layer1Payload with no primary_sport
        l1_no_sport = Layer1Payload(
            user_id=_USER_ID,
            as_of=datetime.combine(_TODAY, datetime.min.time()),
            identity=Layer1Identity(),  # primary_sport=None
            health_status=Layer1HealthStatus(),
            training_history=Layer1TrainingHistory(),
            discipline_baselines=Layer1DisciplineBaselines(),
            performance=Layer1Performance(),
            availability=Layer1Availability(),
            event_goal=Layer1EventGoal(),
            lifestyle=Layer1Lifestyle(),
            network=Layer1Network(),
            disclosures=Layer1Disclosures(),
        )
        with patch(
            "layer4.orchestrator.build_layer1_payload", return_value=l1_no_sport
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_race_week_brief(
                    conn, _USER_ID, cache=cache, today=_TODAY
                )
        assert exc.value.code == "framework_sport_missing"


# ─── defaults + multi-day duration ──────────────────────────────────────────


class TestDefaults:
    def test_today_kwarg_defaults_to_date_today(self):
        """Production callers pass `today=None`; orchestrator anchors to
        `date.today()`. We patch `date.today()` via the orchestrator module
        and verify the resolved value propagates to the Layer 4 call."""
        conn = _FakeConn()
        # Race event one day from now — must satisfy `days_to_event <= 14`.
        _queue_target_race_event(
            conn, event_date=date.today().replace()  # placeholder; overwritten below
        )
        # Rebuild with a realistic date close to today.
        conn.responses = []
        _today_real = date.today()
        _queue_target_race_event(conn, event_date=_today_real)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_today_real,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        # Layer3B fake must also report the same event_date so D-66 row 8
        # would pass (defensive — the 3B driver in real code populates this).
        stack[8] = patch(
            "layer4.orchestrator.llm_layer3b_goal_timeline_viability_cached",
            return_value=_fake_layer3b_payload(event_date=_today_real),
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache)
        finally:
            _exit_all(stack)

        # `today` was None at call site → resolved via date.today() →
        # threaded to the cached wrapper.
        l4_kwargs = mocks[-1].call_args.kwargs
        assert l4_kwargs["today"] == _today_real

    def test_expedition_ar_format_uses_56h_duration_estimate(self):
        conn = _FakeConn()
        _queue_target_race_event(conn, race_format="expedition_ar")
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="expedition_ar",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(
                conn, _USER_ID, cache=cache, today=_TODAY
            )
        finally:
            _exit_all(stack)

        m_l2e = mocks[5]
        te = m_l2e.call_args.kwargs["target_events"][0]
        assert te.estimated_duration_hr == 56.0


# ─── OrchestrationError surface ─────────────────────────────────────────────


class TestOrchestrationError:
    def test_code_and_detail_round_trip(self):
        err = OrchestrationError("x_y_z", detail="some detail")
        assert err.code == "x_y_z"
        assert err.detail == "some detail"
        assert "x_y_z" in str(err)
        assert "some detail" in str(err)

    def test_no_detail(self):
        err = OrchestrationError("bare")
        assert str(err) == "bare"


# ─── Phase 5.1 form-refresh A — race_terrain + aid_stations wire-up ─────────


class TestRaceTerrainAndAidStationsWireUp:
    """The Phase 5.1 form-refresh A slice (2026-05-20) flips the orchestrator's
    `race_terrain=[]` + `Layer2ETargetEvent.aid_stations=None` forward-pointers
    so they thread the actual RaceEventPayload fields. These tests assert the
    threading; downstream behavior is owned by the Layer 2B + Layer 2E specs.
    """

    def test_race_terrain_threads_into_layer2b_call(self):
        conn = _FakeConn()
        _queue_target_race_event(
            conn,
            race_terrain=[
                {"terrain_id": "TRN-002", "pct_of_race": 35.0},
                {"terrain_id": "TRN-009", "pct_of_race": 15.0},
            ],
            aid_stations=4,
        )
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2b = mocks[2]
        l2b_kwargs = m_l2b.call_args.kwargs
        assert len(l2b_kwargs["race_terrain"]) == 2
        # Hydrated to typed RaceTerrainEntry by load_race_event_payload.
        assert l2b_kwargs["race_terrain"][0].terrain_id == "TRN-002"
        assert l2b_kwargs["race_terrain"][0].pct_of_race == 35.0
        assert l2b_kwargs["race_terrain"][1].terrain_id == "TRN-009"

    def test_aid_stations_threads_into_layer2e_target_event(self):
        conn = _FakeConn()
        _queue_target_race_event(conn, aid_stations=12)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2e = mocks[5]
        te = m_l2e.call_args.kwargs["target_events"][0]
        assert te.aid_stations == 12

    def test_empty_race_terrain_still_passed_through_unchanged(self):
        """Athletes who haven't captured terrain yet get the empty list
        threaded through verbatim. Form-refresh C (2026-05-20) paired the
        loosen on Layer 2B `_validate_inputs` so the empty case now emits
        a `race_terrain_unset` coaching flag instead of raising — that
        downstream behavior is covered by `tests/test_layer2b.py`; this
        test still asserts the orchestrator-side threading."""
        conn = _FakeConn()
        _queue_target_race_event(conn, race_terrain=[], aid_stations=None)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2b = mocks[2]
        assert m_l2b.call_args.kwargs["race_terrain"] == []
        m_l2e = mocks[5]
        assert m_l2e.call_args.kwargs["target_events"][0].aid_stations is None


class TestLocaleTerrainIdsWireUp:
    """Phase 5.1 form-refresh C (2026-05-20) flips the orchestrator's last
    `locale_terrain_ids=[]` forward-pointer so it reads from the home
    `locale_profiles.locale_terrain_ids` TEXT[] column instead. These tests
    assert the threading: home-locale terrain IDs make it into Layer 2B's
    kwargs (and the empty / NULL paths surface as empty without raising).
    """

    def test_locale_terrain_ids_thread_into_layer2b_call(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        # New: `_q_locale_terrain_ids` SELECT — psycopg2 returns TEXT[]
        # as a native Python list.
        conn.queue(
            row={"locale_terrain_ids": ["TRN-002", "TRN-003", "TRN-016"]}
        )
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2b = mocks[2]
        l2b_kwargs = m_l2b.call_args.kwargs
        assert l2b_kwargs["locale_terrain_ids"] == [
            "TRN-002", "TRN-003", "TRN-016",
        ]

    def test_locale_terrain_ids_empty_when_column_null(self):
        """Athletes who haven't captured locale terrain (default `'{}'`
        post-migration → SQL NULL pre-migration) get an empty list. Layer
        2B accepts the empty case per spec §4 condition 5 + §13.3."""
        conn = _FakeConn()
        _queue_target_race_event(
            conn,
            race_terrain=[{"terrain_id": "TRN-002", "pct_of_race": 100.0}],
        )
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        # NULL column — pre-migration row shape OR athlete hasn't yet
        # checked any boxes.
        conn.queue(row={"locale_terrain_ids": None})
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2b = mocks[2]
        assert m_l2b.call_args.kwargs["locale_terrain_ids"] == []

    def test_locale_terrain_ids_empty_when_row_missing(self):
        """Defensive — if the home locale_profiles row somehow lacks the
        column (pre-migration / racing init flow), `_q_locale_terrain_ids`
        returns `[]` rather than crashing."""
        conn = _FakeConn()
        _queue_target_race_event(
            conn,
            race_terrain=[{"terrain_id": "TRN-002", "pct_of_race": 100.0}],
        )
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        # No row from the `_q_locale_terrain_ids` query at all.
        conn.queue(row=None)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2b = mocks[2]
        assert m_l2b.call_args.kwargs["locale_terrain_ids"] == []

    def test_locale_terrain_ids_tolerates_json_string_path(self):
        """SQLite shim path — TEXT[] arrives as a JSON-text representation
        instead of a native list."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        conn.queue(
            row={"locale_terrain_ids": '["TRN-002", "TRN-004"]'}
        )
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        race_event_for_l4 = RaceEventPayload(
            race_event_id=1,
            user_id=_USER_ID,
            name="Test Race 2026",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_id="home",
            is_target_event=True,
        )
        stack = _patches(
            layer4_return=_fake_layer4_payload(race_event_payload=race_event_for_l4)
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_race_week_brief(conn, _USER_ID, cache=cache, today=_TODAY)
        finally:
            _exit_all(stack)

        m_l2b = mocks[2]
        assert m_l2b.call_args.kwargs["locale_terrain_ids"] == [
            "TRN-002", "TRN-004",
        ]


# ─── Phase 5.2 slice 1 — orchestrate_single_session_synthesize ───────────────


def _single_session_patches(*, layer4_return: Layer4Payload):
    """Patch stack for `orchestrate_single_session_synthesize`. Narrower cone
    than race_week_brief: Layer 1 → 2A → 2D → 2C (locale-only) → 3A; no 2B
    / 2E / 3B / race_week_brief driver."""
    return [
        patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2c_equipment_mapper_payload",
            return_value=_fake_layer2c_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2d_injury_risk_profile_payload",
            return_value=_fake_layer2d_payload(),
        ),
        patch(
            "layer4.orchestrator.assemble_layer3a_integration_bundle",
            return_value=object(),
        ),
        patch(
            "layer4.orchestrator.llm_layer3a_athlete_state_cached",
            return_value=_fake_layer3a_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer4_single_session_synthesize_cached",
            return_value=layer4_return,
        ),
    ]


def _fake_single_session_layer4_payload(suggestion_id: int = 99) -> Layer4Payload:
    """Minimal single-session-mode Layer4Payload return for the cached-wrapper
    stub. `mode=single_session_synthesize` requires len(sessions)==1 + the
    session marked `is_ad_hoc=True` + `suggestion_id` non-None per the §7.1
    invariants."""
    session = PlanSession(
        session_id="S-orch",
        plan_version_id=0,
        date=_TODAY,
        day_of_week="Mon",
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="D-run",
        discipline_name="Running",
        locale_id="home",
        locale_name="Home",
        duration_min=60,
        intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=130, hr_bpm_high=145),
                instructions="Steady aerobic.",
            )
        ],
        session_notes="Aerobic.",
        coaching_intent="Aerobic stimulus.",
        coaching_flags=[],
        is_ad_hoc=True,
        ad_hoc_request_payload={"source": "orchestrator_test"},
    )
    return Layer4Payload(
        user_id=_USER_ID,
        mode="single_session_synthesize",
        plan_version_id=0,
        suggestion_id=suggestion_id,
        scope_start_date=_TODAY,
        scope_end_date=_TODAY,
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.3,
        pattern="B",
        latency_ms_total=3000,
        input_tokens_total=3500,
        output_tokens_total=800,
        llm_call_count=1,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        sessions=[session],
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
    )


def _request_with_locale() -> SingleSessionRequest:
    return SingleSessionRequest(
        sport="AR",
        duration_min=60,
        intensity="moderate",
        locale_slug="home",
    )


def _request_with_quick_equipment() -> SingleSessionRequest:
    return SingleSessionRequest(
        sport="AR",
        duration_min=45,
        intensity="hard",
        locale_slug=None,
        quick_equipment=["Dumbbells", "Bench"],
    )


def _queue_locale_by_slug_hit(conn: _FakeConn) -> None:
    """Queue `_q_locale_by_slug` SELECT — row present."""
    conn.queue(row={"hit": 1})


def _queue_locale_by_slug_miss(conn: _FakeConn) -> None:
    """Queue `_q_locale_by_slug` SELECT — row missing."""
    conn.queue(row=None)


class TestOrchestrateSingleSessionSynthesizeHappyPath:
    def test_locale_path_threads_payloads_in_dependency_order(self):
        """Locale-slug path: orchestrator validates the slug, calls 2C with
        the locale's equipment pool, threads everything to the cached
        wrapper."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        _queue_locale_by_slug_hit(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            result = orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                _request_with_locale(),
                suggestion_id=99,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert isinstance(result, Layer4Payload)
        assert result.mode == "single_session_synthesize"
        assert result.suggestion_id == 99

        (m_l1, m_l2a, m_l2c, m_l2d, m_bundle, m_l3a, m_l4) = mocks
        for m in mocks:
            assert m.call_count == 1

        # Layer 2A gets request.sport, NOT layer1.identity.primary_sport (D2)
        assert m_l2a.call_args.kwargs["framework_sport"] == "AR"
        # Layer 2C gets the resolved locale + included disciplines
        l2c_kwargs = m_l2c.call_args.kwargs
        assert l2c_kwargs["locale_id"] == "home"
        assert l2c_kwargs["cluster_locale_ids"] == ["home"]
        assert l2c_kwargs["included_discipline_ids"] == ["D-trail"]
        # Layer 4 cached wrapper receives everything threaded
        l4_kwargs = m_l4.call_args.kwargs
        assert l4_kwargs["user_id"] == _USER_ID
        assert l4_kwargs["suggestion_id"] == 99
        assert l4_kwargs["cache"] is cache
        assert l4_kwargs["session_date"] == _TODAY
        assert l4_kwargs["etl_version_set"] == {"0A": "v7", "0B": "v7", "0C": "v7"}
        # layer1_payload threaded as dict (matches race_week_brief precedent)
        assert isinstance(l4_kwargs["layer1_payload"], dict)
        # 2C payload non-None on the locale path
        assert l4_kwargs["layer2c_payload_for_locale"] is not None

    def test_quick_equipment_path_skips_layer2c(self):
        """Somewhere-else path: layer2c_payload_for_locale=None; no 2C call
        fires; no locale-by-slug SELECT fires."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                _request_with_quick_equipment(),
                suggestion_id=42,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        (m_l1, m_l2a, m_l2c, m_l2d, m_bundle, m_l3a, m_l4) = mocks
        # Layer 2C is NOT called on the quick_equipment path
        assert m_l2c.call_count == 0
        # The other upstream stages still run
        for m in (m_l1, m_l2a, m_l2d, m_bundle, m_l3a, m_l4):
            assert m.call_count == 1
        # Driver receives None for layer2c_payload_for_locale
        l4_kwargs = m_l4.call_args.kwargs
        assert l4_kwargs["layer2c_payload_for_locale"] is None
        assert l4_kwargs["suggestion_id"] == 42


class TestOrchestrateSingleSessionSynthesizePreflightGates:
    def test_request_sport_unavailable_when_layer2a_raises(self):
        """Layer 2A's `Layer2AInputError` on unknown framework_sport →
        `OrchestrationError('request_sport_unavailable')`."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        # Patch 2A to raise; the orchestrator should catch + re-raise as
        # OrchestrationError with code='request_sport_unavailable'.
        with patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ), patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            side_effect=Layer2AInputError("framework_sport=PingPong not found"),
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_single_session_synthesize(
                    conn,
                    _USER_ID,
                    SingleSessionRequest(
                        sport="PingPong",
                        duration_min=30,
                        intensity="easy",
                        locale_slug="home",
                    ),
                    suggestion_id=1,
                    cache=cache,
                    today=_TODAY,
                )
        assert exc.value.code == "request_sport_unavailable"
        assert "PingPong" in exc.value.detail

    def test_locale_unknown_when_slug_not_in_locale_profiles(self):
        """Athlete picked a locale_slug that doesn't exist as a
        `locale_profiles` row → `OrchestrationError('locale_unknown')`
        before 2C is called."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        # _q_locale_by_slug fires AFTER 2D in the orchestrator flow, but
        # the SELECT order is: etl_version + locale_by_slug. 2D doesn't
        # touch the db. So the locale_by_slug miss is the second SELECT.
        _queue_locale_by_slug_miss(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_single_session_synthesize(
                    conn,
                    _USER_ID,
                    SingleSessionRequest(
                        sport="AR",
                        duration_min=60,
                        intensity="easy",
                        locale_slug="hotel-london",
                    ),
                    suggestion_id=1,
                    cache=cache,
                    today=_TODAY,
                )
        finally:
            _exit_all(stack)
        assert exc.value.code == "locale_unknown"
        assert "hotel-london" in exc.value.detail
        # 2C + 3A + Layer 4 must not have been called
        (m_l1, m_l2a, m_l2c, m_l2d, m_bundle, m_l3a, m_l4) = mocks
        assert m_l2c.call_count == 0
        assert m_l3a.call_count == 0
        assert m_l4.call_count == 0


class TestOrchestrateSingleSessionSynthesizeDiscoveryFailures:
    def test_etl_version_set_undiscoverable(self):
        """No non-superseded `layer0.sports` row → orchestrator raises before
        any upstream call."""
        conn = _FakeConn()
        conn.queue(row={"v": None})  # etl_version_set lookup returns NULL
        cache = Layer4Cache(InMemoryCacheBackend())

        with pytest.raises(OrchestrationError) as exc:
            orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                _request_with_locale(),
                suggestion_id=1,
                cache=cache,
                today=_TODAY,
            )
        assert exc.value.code == "etl_version_set_undiscoverable"


class TestOrchestrateSingleSessionSynthesizeDefaults:
    def test_today_defaults_to_date_today(self):
        """When `today=None`, orchestrator defaults to `date.today()` and
        passes it through as `session_date` to the cached wrapper."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        _queue_locale_by_slug_hit(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            with patch("layer4.orchestrator.date") as m_date:
                fixed_today = date(2026, 6, 10)
                m_date.today.return_value = fixed_today
                # `datetime.combine` reads `date.today()` indirectly via the
                # `today` arg, but the orchestrator calls `date.today()` only
                # at the kwarg default; once a value is bound, it threads
                # through. Pass `today=None` to exercise the default path.
                orchestrate_single_session_synthesize(
                    conn,
                    _USER_ID,
                    _request_with_locale(),
                    suggestion_id=7,
                    cache=cache,
                    today=None,
                )
        finally:
            _exit_all(stack)
        (m_l1, m_l2a, m_l2c, m_l2d, m_bundle, m_l3a, m_l4) = mocks
        assert m_l4.call_args.kwargs["session_date"] == fixed_today

    def test_layer2c_kwargs_include_layer2d_payload(self):
        """2C must consume 2D's payload for accommodation modality
        pass-through per Layer2C_Spec.md §5.6 — verifies the threading."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        _queue_locale_by_slug_hit(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                _request_with_locale(),
                suggestion_id=1,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)
        (m_l1, m_l2a, m_l2c, m_l2d, m_bundle, m_l3a, m_l4) = mocks
        l2c_kwargs = m_l2c.call_args.kwargs
        # 2D payload threads into 2C (accommodation modality pass-through)
        assert l2c_kwargs["layer2d_payload"] is m_l2d.return_value


class TestOrchestrateSingleSessionSynthesizeSportSemantics:
    def test_request_sport_overrides_layer1_primary_sport(self):
        """D2 ratified — Layer 2A is called with `request.sport`, not
        `layer1.identity.primary_sport`. Athlete picks Rowing for
        cross-training even though their primary is AR."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        _queue_locale_by_slug_hit(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        cross_train_request = SingleSessionRequest(
            sport="Rowing",
            duration_min=60,
            intensity="moderate",
            locale_slug="home",
        )

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                cross_train_request,
                suggestion_id=1,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)
        (m_l1, m_l2a, m_l2c, m_l2d, m_bundle, m_l3a, m_l4) = mocks
        # 2A receives request.sport ("Rowing"), NOT layer1.identity.primary_sport ("AR")
        assert m_l2a.call_args.kwargs["framework_sport"] == "Rowing"

    def test_quick_equipment_path_no_locale_by_slug_select(self):
        """When locale_slug is None, _q_locale_by_slug must NOT fire — saves
        an unnecessary SELECT. Queue only the etl_version_set row; if any
        further SELECT was attempted, the FakeConn returns empty and the
        flow would raise downstream. The assertion is that we successfully
        complete with just the etl_version_set queued."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        # Intentionally NO locale_by_slug + NO locale_equipment_pool queued.
        cache = Layer4Cache(InMemoryCacheBackend())

        stack = _single_session_patches(
            layer4_return=_fake_single_session_layer4_payload()
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                _request_with_quick_equipment(),
                suggestion_id=1,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)
        # Only 1 SELECT (etl_version_set) — the orchestrator didn't query
        # locale_profiles or locale_equipment on the quick_equipment path.
        assert len(conn.calls) == 1


class TestOrchestrateSingleSessionSynthesizeReturnValue:
    def test_returns_cached_wrapper_output_verbatim(self):
        """The orchestrator returns whatever
        `llm_layer4_single_session_synthesize_cached` returns. It does NOT
        wrap, modify, or validate the Layer4Payload — the cached wrapper
        + driver already handle rebinding (suggestion_id, plan_version_id)
        and validation."""
        conn = _FakeConn()
        _queue_etl_version_set(conn)
        _queue_locale_by_slug_hit(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_single_session_layer4_payload()
        stack = _single_session_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_single_session_synthesize(
                conn,
                _USER_ID,
                _request_with_locale(),
                suggestion_id=99,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)
        assert result is sentinel


# ─── Phase 5.2 slice 2 — orchestrate_plan_refresh tests ─────────────────────


def _plan_refresh_patches(*, layer4_return: Layer4Payload):
    """Patch-stack for `orchestrate_plan_refresh`. Same 10 sites as
    race_week_brief except the final cached wrapper is
    `llm_layer4_plan_refresh_cached` (not `_race_week_brief_cached`). The
    shared `_upstream_full_cone` helper calls these by their module-level
    names so the patches apply transparently to both entry points."""
    return [
        patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2b_terrain_classifier_payload",
            return_value=_fake_layer2b_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2c_equipment_mapper_payload",
            return_value=_fake_layer2c_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2d_injury_risk_profile_payload",
            return_value=_fake_layer2d_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2e_nutrition_baseline_payload",
            return_value=_fake_layer2e_payload(),
        ),
        patch(
            "layer4.orchestrator.assemble_layer3a_integration_bundle",
            return_value=object(),
        ),
        patch(
            "layer4.orchestrator.llm_layer3a_athlete_state_cached",
            return_value=_fake_layer3a_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer3b_goal_timeline_viability_cached",
            return_value=_fake_layer3b_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer4_plan_refresh_cached",
            return_value=layer4_return,
        ),
    ]


def _fake_plan_refresh_layer4_payload(
    *, plan_version_id: int = 2
) -> Layer4Payload:
    """Construct a valid Pattern B plan_refresh Layer4Payload. Mode invariants
    (`payload.py:_check_mode_invariants` lines 553-565): mode='plan_refresh'
    + pattern='B' requires phase_structure=None + seam_reviews=None."""
    return Layer4Payload(
        user_id=_USER_ID,
        mode="plan_refresh",
        plan_version_id=plan_version_id,
        scope_start_date=_TODAY,
        scope_end_date=date(2026, 6, 8),
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.4,
        pattern="B",
        latency_ms_total=6000,
        input_tokens_total=3500,
        output_tokens_total=1800,
        llm_call_count=1,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        sessions=[],
        phase_structure=None,
        seam_reviews=None,
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
    )


def _default_prior_plan_session_window() -> list[PlanSession]:
    """Single non-ad-hoc PlanSession for the prior-window kwarg. The driver
    enforces non-empty; the orchestrator passes the list through verbatim
    without inspecting its contents, so a single placeholder session is
    enough for orchestrator-level tests."""
    return [
        PlanSession(
            session_id="ps-prior-1",
            plan_version_id=1,
            date=date(2026, 5, 25),
            day_of_week="Mon",
            session_index_in_day=0,
            time_of_day="morning",
            kind="cardio",
            discipline_id="D-run",
            discipline_name="Running",
            locale_id="home",
            locale_name="Home",
            duration_min=45,
            intensity_summary="easy",
            cardio_blocks=[
                CardioBlock(
                    block_kind="main_set",
                    duration_min=45,
                    intensity_zone="Z2",
                    intensity_target=HRTarget(hr_bpm_low=125, hr_bpm_high=140),
                    instructions="Steady easy.",
                )
            ],
            session_notes="Easy aerobic.",
            coaching_intent="Aerobic base.",
            coaching_flags=[],
            is_ad_hoc=False,
        )
    ]


class TestOrchestratePlanRefreshHappyPath:
    @pytest.mark.parametrize(
        ("tier", "scope_days"),
        [("T1", 2), ("T2", 7), ("T3", 28)],
    )
    def test_tier_dispatch_pipeline_in_order(self, tier, scope_days):
        """T1/T2/T3 happy path: full upstream cone fires; tier kwarg threads
        verbatim to the cached wrapper; refresh_scope dates thread."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        scope_start = _TODAY
        scope_end = date(2026, 6, 1 + scope_days - 1)
        sentinel = _fake_plan_refresh_layer4_payload(plan_version_id=2)
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier=tier,
                refresh_scope_start=scope_start,
                refresh_scope_end=scope_end,
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                plan_start_date=date(2026, 4, 1) if tier == "T3" else None,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert result is sentinel
        # All 10 upstream + wrapper sites fire exactly once.
        for m in mocks:
            assert m.call_count == 1

        # Cached wrapper kwargs reflect the orchestrator's composition.
        (*_others, m_wrapper) = mocks
        kw = m_wrapper.call_args.kwargs
        assert kw["user_id"] == _USER_ID
        assert kw["tier"] == tier
        assert kw["refresh_scope_start"] == scope_start
        assert kw["refresh_scope_end"] == scope_end
        assert kw["plan_version_id"] == 2
        assert kw["plan_version_id_parent"] == 1
        assert kw["cache"] is cache
        assert kw["parsed_intent"] is None  # default
        if tier == "T3":
            assert kw["plan_start_date"] == date(2026, 4, 1)
        else:
            assert kw["plan_start_date"] is None
        # layer1_payload threaded as dict (matches single_session + race_week_brief)
        assert isinstance(kw["layer1_payload"], dict)
        # Layer2Bundle packs all 5 layer-2 payloads; c is dict keyed by locale.
        bundle = kw["layer2_bundle"]
        assert isinstance(bundle, Layer2Bundle)
        assert bundle.a is not None
        assert bundle.b is not None
        assert set(bundle.c.keys()) == {"home"}
        assert bundle.d is not None
        assert bundle.e is not None

    def test_parsed_intent_threads_to_wrapper(self):
        """`parsed_intent` kwarg threads verbatim — orchestrator does not
        construct a default ParsedIntent; None passes through per D-64 §5.4
        graceful-degradation contract."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        pi = ParsedIntent(
            triggers_2a_discipline=True,
            fatigue_signal="tired",
            raw_text="cut volume this week",
        )
        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T2",
                refresh_scope_start=_TODAY,
                refresh_scope_end=date(2026, 6, 7),
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                parsed_intent=pi,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        kw = mocks[-1].call_args.kwargs
        assert kw["parsed_intent"] is pi


class TestOrchestratePlanRefreshPreflightGates:
    """3 gates shared with race_week_brief (raised by `_upstream_full_cone`).
    No `no_target_event` gate (no-event mode is supported)."""

    def test_etl_version_set_undiscoverable(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        conn.queue(row={"v": None})  # etl_version lookup returns NULL
        cache = Layer4Cache(InMemoryCacheBackend())

        with pytest.raises(OrchestrationError) as exc:
            orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T1",
                refresh_scope_start=_TODAY,
                refresh_scope_end=_TODAY,
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                today=_TODAY,
            )
        assert exc.value.code == "etl_version_set_undiscoverable"

    def test_primary_locale_missing(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        conn.queue(row=None)  # locale_profiles 'home' lookup returns no row
        cache = Layer4Cache(InMemoryCacheBackend())

        with patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ), patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_plan_refresh(
                    conn,
                    _USER_ID,
                    tier="T2",
                    refresh_scope_start=_TODAY,
                    refresh_scope_end=date(2026, 6, 7),
                    plan_version_id=2,
                    plan_version_id_parent=1,
                    prior_plan_session_window=_default_prior_plan_session_window(),
                    cache=cache,
                    today=_TODAY,
                )
        assert exc.value.code == "primary_locale_missing"

    def test_framework_sport_missing(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        l1_no_sport = Layer1Payload(
            user_id=_USER_ID,
            as_of=datetime.combine(_TODAY, datetime.min.time()),
            identity=Layer1Identity(),  # primary_sport=None
            health_status=Layer1HealthStatus(),
            training_history=Layer1TrainingHistory(),
            discipline_baselines=Layer1DisciplineBaselines(),
            performance=Layer1Performance(),
            availability=Layer1Availability(),
            event_goal=Layer1EventGoal(),
            lifestyle=Layer1Lifestyle(),
            network=Layer1Network(),
            disclosures=Layer1Disclosures(),
        )
        with patch(
            "layer4.orchestrator.build_layer1_payload", return_value=l1_no_sport
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_plan_refresh(
                    conn,
                    _USER_ID,
                    tier="T1",
                    refresh_scope_start=_TODAY,
                    refresh_scope_end=_TODAY,
                    plan_version_id=2,
                    plan_version_id_parent=1,
                    prior_plan_session_window=_default_prior_plan_session_window(),
                    cache=cache,
                    today=_TODAY,
                )
        assert exc.value.code == "framework_sport_missing"


class TestOrchestratePlanRefreshNoEventMode:
    def test_no_target_race_threads_race_event_payload_none(self):
        """When the athlete has no `is_target_event=true` race row,
        plan_refresh proceeds (unlike race_week_brief, which raises
        `no_target_event`). Layer 2B's `race_terrain` is `[]`, Layer 2E's
        `target_events` is `[]`, Layer 3B's `race_event_payload` is `None`."""
        conn = _FakeConn()
        # load_target_race_event_payload's first SELECT returns None
        conn.queue(row=None)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T2",
                refresh_scope_start=_TODAY,
                refresh_scope_end=date(2026, 6, 7),
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert result is sentinel
        # 2B receives race_terrain=[] (empty), 2E receives target_events=[],
        # 3B receives race_event_payload=None.
        (
            _m_l1,
            _m_l2a,
            m_l2b,
            _m_l2c,
            _m_l2d,
            m_l2e,
            _m_bundle,
            _m_l3a,
            m_l3b,
            _m_wrapper,
        ) = mocks
        assert m_l2b.call_args.kwargs["race_terrain"] == []
        assert m_l2e.call_args.kwargs["target_events"] == []
        assert m_l3b.call_args.kwargs["race_event_payload"] is None


class TestOrchestratePlanRefreshDefaults:
    def test_today_kwarg_defaults_to_date_today(self):
        """Production callers pass `today=None`; orchestrator anchors to
        `date.today()` and threads the resolved value into the upstream
        pipeline (Layer 2E `today` kwarg + Layer 3B `current_date`)."""
        conn = _FakeConn()
        _queue_target_race_event(conn, event_date=date.today())
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        # Layer3B fake reports event_date matching the queued race row so the
        # D-66 model-validator row 8 (event_date consistency) passes.
        stack[8] = patch(
            "layer4.orchestrator.llm_layer3b_goal_timeline_viability_cached",
            return_value=_fake_layer3b_payload(event_date=date.today()),
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T1",
                refresh_scope_start=date.today(),
                refresh_scope_end=date.today(),
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                # today omitted → defaults to date.today()
            )
        finally:
            _exit_all(stack)

        # Layer 3B current_date = today (resolved).
        m_l3b = mocks[8]
        assert m_l3b.call_args.kwargs["current_date"] == date.today()

    def test_parsed_intent_defaults_to_none(self):
        """`parsed_intent` kwarg defaults to None when caller omits — matches
        the D-64 §5.4 graceful-degradation contract."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T2",
                refresh_scope_start=_TODAY,
                refresh_scope_end=date(2026, 6, 7),
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                today=_TODAY,
                # parsed_intent omitted
            )
        finally:
            _exit_all(stack)

        assert mocks[-1].call_args.kwargs["parsed_intent"] is None


class TestOrchestratePlanRefreshTierPassThrough:
    def test_t3_plan_start_date_threads_to_wrapper(self):
        """T3 requires plan_start_date for the driver's
        `phase_structure_from_3b()` boundary detection. Orchestrator threads
        the caller-supplied value verbatim — does not derive."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        plan_start = date(2026, 4, 1)
        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T3",
                refresh_scope_start=_TODAY,
                refresh_scope_end=date(2026, 6, 28),
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                plan_start_date=plan_start,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert mocks[-1].call_args.kwargs["plan_start_date"] == plan_start

    def test_prior_plan_session_window_threads_verbatim(self):
        """Orchestrator passes `prior_plan_session_window` through without
        inspection or modification — driver enforces non-empty."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        prior_window = _default_prior_plan_session_window()
        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T1",
                refresh_scope_start=_TODAY,
                refresh_scope_end=_TODAY,
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=prior_window,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        # Same list object passes through (orchestrator does not copy).
        assert mocks[-1].call_args.kwargs["prior_plan_session_window"] is prior_window


class TestOrchestratePlanRefreshReturnValue:
    def test_returns_cached_wrapper_output_verbatim(self):
        """Orchestrator returns whatever `llm_layer4_plan_refresh_cached`
        returns. Matches the single_session + race_week_brief precedents —
        no wrap/modify/validate at orchestrator level."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_refresh_layer4_payload()
        stack = _plan_refresh_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_plan_refresh(
                conn,
                _USER_ID,
                tier="T1",
                refresh_scope_start=_TODAY,
                refresh_scope_end=_TODAY,
                plan_version_id=2,
                plan_version_id_parent=1,
                prior_plan_session_window=_default_prior_plan_session_window(),
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)
        assert result is sentinel


# ─── Phase 5.2 slice 3 — orchestrate_plan_create tests ──────────────────────


def _plan_create_patches(*, layer4_return: Layer4Payload):
    """Patch-stack for `orchestrate_plan_create`. Same 10 sites as
    race_week_brief + plan_refresh except the final cached wrapper is
    `llm_layer4_plan_create_cached`. The shared `_upstream_full_cone`
    helper calls the upstream sites by their module-level names so the
    patches apply transparently across all three full-cone entry points."""
    return [
        patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2b_terrain_classifier_payload",
            return_value=_fake_layer2b_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2c_equipment_mapper_payload",
            return_value=_fake_layer2c_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2d_injury_risk_profile_payload",
            return_value=_fake_layer2d_payload(),
        ),
        patch(
            "layer4.orchestrator.q_layer2e_nutrition_baseline_payload",
            return_value=_fake_layer2e_payload(),
        ),
        patch(
            "layer4.orchestrator.assemble_layer3a_integration_bundle",
            return_value=object(),
        ),
        patch(
            "layer4.orchestrator.llm_layer3a_athlete_state_cached",
            return_value=_fake_layer3a_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer3b_goal_timeline_viability_cached",
            return_value=_fake_layer3b_payload(),
        ),
        patch(
            "layer4.orchestrator.llm_layer4_plan_create_cached",
            return_value=layer4_return,
        ),
    ]


def _fake_plan_create_layer4_payload(
    *, plan_version_id: int = 3
) -> Layer4Payload:
    """Construct a valid Pattern A plan_create Layer4Payload. Mode invariants
    (`payload.py:_check_mode_invariants` lines 548-552): mode='plan_create'
    requires phase_structure non-None + seam_reviews non-None. Empty
    `phases` list + empty `seam_reviews` list satisfy "non-None" without
    forcing the orchestrator test surface to construct full PhaseSpec /
    SeamReview rows — those belong to `tests/test_layer4_plan_create.py`."""
    return Layer4Payload(
        user_id=_USER_ID,
        mode="plan_create",
        plan_version_id=plan_version_id,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 8, 24),
        model_synthesizer="claude-sonnet-4-6",
        model_seam_reviewer="claude-sonnet-4-6",
        temperature=0.2,
        pattern="A",
        latency_ms_total=45000,
        input_tokens_total=22000,
        output_tokens_total=9000,
        llm_call_count=5,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        sessions=[],
        phase_structure=PhaseStructure(
            phases=[], total_weeks=12, derived_from="3b_standard"
        ),
        seam_reviews=[],
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
    )


class TestOrchestratePlanCreateHappyPath:
    def test_pipeline_in_order_event_mode(self):
        """Event-mode happy path: full upstream cone fires; cached wrapper
        receives composed payloads + race_event_payload non-None."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_create_layer4_payload(plan_version_id=3)
        stack = _plan_create_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date(2026, 6, 1),
                plan_version_id=3,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert result is sentinel
        # All 10 upstream + wrapper sites fire exactly once.
        for m in mocks:
            assert m.call_count == 1

        (*_others, m_wrapper) = mocks
        kw = m_wrapper.call_args.kwargs
        assert kw["user_id"] == _USER_ID
        assert kw["plan_start_date"] == date(2026, 6, 1)
        assert kw["plan_version_id"] == 3
        assert kw["cache"] is cache
        assert kw["etl_version_set"] == {"0A": "v7", "0B": "v7", "0C": "v7"}
        # layer1_payload threaded as dict (matches race_week_brief +
        # plan_refresh — driver expects dict[str, Any]).
        assert isinstance(kw["layer1_payload"], dict)
        # layer2c_payloads keyed by primary locale (race_week_brief shape;
        # plan_refresh uses Layer2Bundle but plan_create takes the dict).
        assert set(kw["layer2c_payloads"].keys()) == {"home"}
        # race_event_payload threads through (event-mode).
        assert kw["race_event_payload"] is not None
        assert kw["race_event_payload"].race_event_id == 1

    def test_pipeline_in_order_no_event_mode(self):
        """No-event-mode happy path: open-ended plan_create proceeds without
        a target race row. Layer 2B's race_terrain=[], Layer 2E's
        target_events=[], Layer 3B's race_event_payload=None, cached
        wrapper's race_event_payload=None."""
        conn = _FakeConn()
        # load_target_race_event_payload's first SELECT returns None
        conn.queue(row=None)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_create_layer4_payload()
        stack = _plan_create_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date(2026, 6, 1),
                plan_version_id=3,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert result is sentinel
        (
            _m_l1,
            _m_l2a,
            m_l2b,
            _m_l2c,
            _m_l2d,
            m_l2e,
            _m_bundle,
            _m_l3a,
            m_l3b,
            m_wrapper,
        ) = mocks
        # No-event-mode threading.
        assert m_l2b.call_args.kwargs["race_terrain"] == []
        assert m_l2e.call_args.kwargs["target_events"] == []
        assert m_l3b.call_args.kwargs["race_event_payload"] is None
        assert m_wrapper.call_args.kwargs["race_event_payload"] is None


class TestOrchestratePlanCreatePreflightGates:
    """3 gates shared with race_week_brief + plan_refresh (raised by
    `_upstream_full_cone`). No `no_target_event` gate — open-ended plans
    are first-class."""

    def test_etl_version_set_undiscoverable(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        conn.queue(row={"v": None})  # etl_version lookup returns NULL
        cache = Layer4Cache(InMemoryCacheBackend())

        with pytest.raises(OrchestrationError) as exc:
            orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date(2026, 6, 1),
                plan_version_id=3,
                cache=cache,
                today=_TODAY,
            )
        assert exc.value.code == "etl_version_set_undiscoverable"

    def test_primary_locale_missing(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        conn.queue(row=None)  # locale_profiles 'home' lookup returns no row
        cache = Layer4Cache(InMemoryCacheBackend())

        with patch(
            "layer4.orchestrator.build_layer1_payload",
            return_value=_fake_layer1_payload(),
        ), patch(
            "layer4.orchestrator.q_layer2a_discipline_classifier_payload",
            return_value=_fake_layer2a_payload(),
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_plan_create(
                    conn,
                    _USER_ID,
                    plan_start_date=date(2026, 6, 1),
                    plan_version_id=3,
                    cache=cache,
                    today=_TODAY,
                )
        assert exc.value.code == "primary_locale_missing"

    def test_framework_sport_missing(self):
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        l1_no_sport = Layer1Payload(
            user_id=_USER_ID,
            as_of=datetime.combine(_TODAY, datetime.min.time()),
            identity=Layer1Identity(),  # primary_sport=None
            health_status=Layer1HealthStatus(),
            training_history=Layer1TrainingHistory(),
            discipline_baselines=Layer1DisciplineBaselines(),
            performance=Layer1Performance(),
            availability=Layer1Availability(),
            event_goal=Layer1EventGoal(),
            lifestyle=Layer1Lifestyle(),
            network=Layer1Network(),
            disclosures=Layer1Disclosures(),
        )
        with patch(
            "layer4.orchestrator.build_layer1_payload", return_value=l1_no_sport
        ):
            with pytest.raises(OrchestrationError) as exc:
                orchestrate_plan_create(
                    conn,
                    _USER_ID,
                    plan_start_date=date(2026, 6, 1),
                    plan_version_id=3,
                    cache=cache,
                    today=_TODAY,
                )
        assert exc.value.code == "framework_sport_missing"


class TestOrchestratePlanCreateDefaults:
    def test_today_kwarg_defaults_to_date_today(self):
        """Production callers pass `today=None`; orchestrator anchors to
        `date.today()` and threads the resolved value into the upstream
        pipeline (Layer 3B `current_date` kwarg)."""
        conn = _FakeConn()
        _queue_target_race_event(conn, event_date=date.today())
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_create_layer4_payload()
        stack = _plan_create_patches(layer4_return=sentinel)
        # 3B fake must report event_date matching the queued race row so
        # the D-66 model-validator row 8 (event_date consistency) passes.
        stack[8] = patch(
            "layer4.orchestrator.llm_layer3b_goal_timeline_viability_cached",
            return_value=_fake_layer3b_payload(event_date=date.today()),
        )
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date.today(),
                plan_version_id=3,
                cache=cache,
                # today omitted → defaults to date.today()
            )
        finally:
            _exit_all(stack)

        m_l3b = mocks[8]
        assert m_l3b.call_args.kwargs["current_date"] == date.today()

    def test_layer2c_packed_as_primary_locale_dict(self):
        """plan_create's layer2c_payloads shape matches race_week_brief
        (single-locale dict keyed by primary locale), not plan_refresh's
        Layer2Bundle. Driver signature requires dict[str, Layer2CPayload]."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_create_layer4_payload()
        stack = _plan_create_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date(2026, 6, 1),
                plan_version_id=3,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        kw = mocks[-1].call_args.kwargs
        assert isinstance(kw["layer2c_payloads"], dict)
        assert set(kw["layer2c_payloads"].keys()) == {"home"}


class TestOrchestratePlanCreatePassThrough:
    def test_plan_start_date_threads_verbatim(self):
        """`plan_start_date` is required caller-supplied; orchestrator
        passes it verbatim to the cached wrapper. The driver consumes it
        for `phase_structure_from_3b()` boundary detection + the §3.1
        plan-creation calendar anchor."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        plan_start = date(2026, 7, 15)
        sentinel = _fake_plan_create_layer4_payload()
        stack = _plan_create_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=plan_start,
                plan_version_id=3,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert mocks[-1].call_args.kwargs["plan_start_date"] == plan_start

    def test_plan_version_id_threads_verbatim(self):
        """`plan_version_id` is caller-supplied per D-64 caller-side
        deferral; orchestrator passes through without allocation."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_create_layer4_payload(plan_version_id=99)
        stack = _plan_create_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date(2026, 6, 1),
                plan_version_id=99,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)

        assert mocks[-1].call_args.kwargs["plan_version_id"] == 99


class TestOrchestratePlanCreateReturnValue:
    def test_returns_cached_wrapper_output_verbatim(self):
        """Orchestrator returns whatever `llm_layer4_plan_create_cached`
        returns. Matches race_week_brief + single_session + plan_refresh
        precedent — no wrap/modify/validate at orchestrator level."""
        conn = _FakeConn()
        _queue_target_race_event(conn)
        _queue_etl_version_set(conn)
        _queue_primary_locale(conn)
        _queue_locale_equipment_pool(conn)
        cache = Layer4Cache(InMemoryCacheBackend())

        sentinel = _fake_plan_create_layer4_payload()
        stack = _plan_create_patches(layer4_return=sentinel)
        mocks = _enter_all(stack)
        try:
            result = orchestrate_plan_create(
                conn,
                _USER_ID,
                plan_start_date=date(2026, 6, 1),
                plan_version_id=3,
                cache=cache,
                today=_TODAY,
            )
        finally:
            _exit_all(stack)
        assert result is sentinel
        # And the upstream pipeline fired completely once.
        for m in mocks:
            assert m.call_count == 1
