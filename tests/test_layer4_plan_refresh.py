"""Tests for `layer4/plan_refresh.py` + `plan_refresh_t1.py` + `plan_refresh_t2.py`
— Step 4b/c integration: D-64 `llm_layer4_plan_refresh` per `Layer4_Spec.md` §3.2.

Coverage:
- `Layer2Bundle` + `ParsedIntent` construction (context.py additions)
- Tool schema shape (T1 vs T2 `maxItems`, closed coaching-flag enum, 9-shape
  IntensityTarget oneOf, intensity_zone enum)
- §4.3 input validation preconditions (8 rows)
- Entry-point happy path × T1 + T2 × cardio + strength + empty + mixed
- Capped retry semantics (validator fail then pass; cap-hit best-effort)
- `intensity_modulated` Observation emission (per-session + multi-session)
- Layer4Payload composition invariants (mode=plan_refresh, pattern=B,
  phase_structure=None, seam_reviews=None, suggestion_id=None, each
  session.phase_metadata=None, sessions list)
- Prompt rendering (parsed_intent + prior window + retry context)
- T3 intra-phase routes to Pattern B; cross-phase raises pattern_a
- phase_structure_from_3b dispatch + plan_start_date validation

LLM calls are mocked via a stub `llm_caller` dependency. No real Anthropic
SDK invocations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from layer4 import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    CurrentState,
    DataDensity,
    DisciplineCoverage,
    ExerciseRisk,
    GoalViability,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2Bundle,
    Layer2CPayload,
    Layer2DPayload,
    Layer3APayload,
    Layer3BPayload,
    Layer4InputError,
    Layer4OutputError,
    Layer4Payload,
    ParsedIntent,
    PeriodizationShape,
    PhaseLoadBands,
    PlanSession,
    RationaleMetadata,
    RecentTrajectory,
    ResolvedExercise,
    TrainingGapsSummary,
    TrajectoryWindow,
    WeightResult,
    build_record_refresh_sessions_tool,
    llm_layer4_plan_refresh,
)
from layer4.plan_refresh import _SynthesizerOutput


# ─── Fixtures ────────────────────────────────────────────────────────────────


_T1_START = date(2026, 6, 1)  # Mon
_T1_END = date(2026, 6, 2)  # Tue
_T2_START = date(2026, 6, 1)
_T2_END = date(2026, 6, 7)  # Sun


def _layer1() -> dict[str, Any]:
    return {"experience_level": "advanced", "coach_notes": None}


def _layer2a() -> Layer2APayload:
    return Layer2APayload(
        framework_sport="multisport",
        etl_version_set={"layer0": "v7"},
        disciplines=[
            Layer2ADiscipline(
                discipline_id="D-run",
                discipline_name="Running",
                inclusion="included",
                role="Primary",
                is_conditional=False,
                load_weight=WeightResult(
                    value=1.0, source="system_default", system_default=1.0
                ),
                sleep_deprivation_relevant=False,
                rationale="primary endurance discipline",
                phase_load=PhaseLoadBands(
                    base_low=5.0,
                    base_high=8.0,
                    build_low=6.0,
                    build_high=10.0,
                    peak_low=7.0,
                    peak_high=11.0,
                    taper_low=3.0,
                    taper_high=5.0,
                    default_inclusion="included",
                ),
            ),
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
            generated_at="2026-05-31T10:00:00",
        ),
    )


def _layer2c(
    locale_id: str = "home_gym",
    exercise_ids: tuple[str, ...] = ("E-squat", "E-pushup"),
    discipline_id: str = "D-run",
) -> Layer2CPayload:
    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"layer0": "v7"},
        effective_pool=list(exercise_ids),
        discipline_coverage=[
            DisciplineCoverage(
                discipline_id=discipline_id,
                discipline_name=discipline_id,
                exercise_db_sport="x",
                total_exercises=len(exercise_ids),
                tier_1_count=len(exercise_ids),
                tier_2_count=0,
                tier_3_count=0,
                unavailable_count=0,
                coverage_pct=1.0,
            )
        ],
        exercises_resolved=[
            ResolvedExercise(
                exercise_id=ex,
                exercise_name=ex,
                exercise_type="strength",
                discipline_ids=[discipline_id],
                sport_relevance_notes={discipline_id: "x"},
                priority_per_discipline={discipline_id: "Medium"},
                tier=1,
                terrain_required=[],
                contraindicated_parts=[],
                contraindicated_conditions=[],
                accommodations=[],
            )
            for ex in exercise_ids
        ],
        coaching_flags=[],
    )


def _layer2d(excluded: tuple[str, ...] = ()) -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"layer0": "v7"},
        excluded_exercises=[
            ExerciseRisk(
                exercise_id=ex,
                exercise_name=ex,
                discipline_ids=["D-run"],
                verdict="exclude",
                accommodations=[],
                evidence=[],
            )
            for ex in excluded
        ],
        accommodated_exercises=[],
        clean_exercise_ids=[],
        discipline_risk_profiles=[],
        coaching_flags=[],
        hitl_required=False,
        hitl_items=[],
    )


def _layer3a(zone: str = "sweet_spot", ratio: float = 0.95) -> Layer3APayload:
    return Layer3APayload(
        user_id=42,
        as_of=datetime(2026, 5, 31, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1000,
        input_tokens=2000,
        output_tokens=500,
        etl_version_set={"layer0": "v7"},
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
            acwr_status=ACWRStatus(
                per_discipline={
                    "D-run": ACWREntry(
                        acute_load=7.0,
                        chronic_load=8.0,
                        ratio=ratio,
                        zone=zone,  # type: ignore[arg-type]
                        units="hours",
                    )
                },
                combined=None,
            ),
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


def _layer3b(mode: str = "no-event", start_phase: str = "Build") -> Layer3BPayload:
    return Layer3BPayload(
        user_id=42,
        as_of=datetime(2026, 5, 31, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1500,
        input_tokens=3000,
        output_tokens=800,
        etl_version_set={"layer0": "v7"},
        mode=mode,  # type: ignore[arg-type]
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="solid base",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode="standard",
            start_phase=start_phase,  # type: ignore[arg-type]
            phase_weeks=None,
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        hitl_surface=[],
        notable_observations=[],
    )


def _layer2_bundle(
    *,
    with_2a: bool = True,
    with_2c: bool = True,
    with_2d: bool = True,
) -> Layer2Bundle:
    return Layer2Bundle(
        a=_layer2a() if with_2a else None,
        b=None,
        c={"home_gym": _layer2c()} if with_2c else {},
        d=_layer2d() if with_2d else None,
        e=None,
    )


def _prior_session(d: date, *, idx: int = 0) -> PlanSession:
    """Build a prior plan session for the window context. Uses rest kind to
    avoid the cardio_blocks-non-empty / strength_exercises-non-empty
    invariants — the prior window is context-only, not validated for shape."""
    return PlanSession(
        session_id=f"prior-{d.isoformat()}-{idx}",
        plan_version_id=1,
        date=d,
        day_of_week=d.strftime("%a"),
        session_index_in_day=idx,
        time_of_day="morning",
        kind="rest",
        discipline_id=None,
        discipline_name=None,
        locale_id=None,
        locale_name=None,
        duration_min=0,
        intensity_summary="rest",
        cardio_blocks=None,
        strength_exercises=None,
        rest_reason="planned_recovery",
        phase_metadata=None,
        session_notes="prior rest",
        coaching_intent="recovery placeholder for context",
        coaching_flags=[],
        is_ad_hoc=False,
        ad_hoc_request_payload=None,
    )


def _prior_window(start: date, end: date, *, pre_days: int = 7, post_days: int = 7) -> list[PlanSession]:
    """Build a list of prior sessions covering [start - pre_days, end + post_days].
    Includes the to-be-replaced sessions in [start, end] so the validator's
    'prior_plan_window_empty' check passes."""
    sessions = []
    for offset in range(-pre_days, (end - start).days + post_days + 1):
        sessions.append(_prior_session(start + timedelta(days=offset)))
    return sessions


# ─── Tool output builders ────────────────────────────────────────────────────


def _cardio_session(
    *,
    d: date,
    idx: int = 0,
    duration_min: int = 60,
    intensity_summary: str = "easy",
    coaching_flags: list[str] | None = None,
    locale_id: str | None = "home_gym",
) -> dict[str, Any]:
    return {
        "date": d.isoformat(),
        "day_of_week": d.strftime("%a"),
        "session_index_in_day": idx,
        "time_of_day": "morning",
        "kind": "cardio",
        "discipline_id": "D-run",
        "discipline_name": "Running",
        "locale_id": locale_id,
        "locale_name": locale_id,
        "duration_min": duration_min,
        "intensity_summary": intensity_summary,
        "session_notes": "easy aerobic.",
        "coaching_intent": "Z2 aerobic stimulus.",
        "coaching_flags": coaching_flags or [],
        "cardio_blocks": [
            {
                "block_kind": "warmup",
                "duration_min": 10,
                "intensity_zone": "Z1",
                "intensity_target": {"hr_bpm_low": 110, "hr_bpm_high": 125},
                "instructions": "easy warmup.",
            },
            {
                "block_kind": "main_set",
                "duration_min": duration_min - 20,
                "intensity_zone": "Z2",
                "intensity_target": {"hr_bpm_low": 130, "hr_bpm_high": 145},
                "instructions": "steady aerobic.",
            },
            {
                "block_kind": "cooldown",
                "duration_min": 10,
                "intensity_zone": "Z1",
                "intensity_target": {"hr_bpm_low": 110, "hr_bpm_high": 125},
                "instructions": "easy cooldown.",
            },
        ],
    }


def _strength_session(
    *,
    d: date,
    idx: int = 0,
    duration_min: int = 45,
    exercise_ids: tuple[str, ...] = ("E-squat", "E-pushup"),
    locale_id: str | None = "home_gym",
    discipline_id: str = "D-run",
) -> dict[str, Any]:
    return {
        "date": d.isoformat(),
        "day_of_week": d.strftime("%a"),
        "session_index_in_day": idx,
        "time_of_day": "afternoon",
        "kind": "strength",
        "discipline_id": discipline_id,
        "discipline_name": discipline_id,
        "locale_id": locale_id,
        "locale_name": locale_id,
        "duration_min": duration_min,
        "intensity_summary": "moderate",
        "session_notes": "lower body + push.",
        "coaching_intent": "strength baseline.",
        "coaching_flags": [],
        "strength_exercises": [
            {
                "exercise_id": ex,
                "exercise_name": ex,
                "resolution_tier": 1,
                "sets": 3,
                "reps_per_set": 8,
                "load_prescription": "70% 1RM",
                "rest_between_sets_sec": 90,
                "instructions": "neutral spine.",
                "coaching_flags": [],
            }
            for ex in exercise_ids
        ],
    }


def _stub_caller(tool_args: dict[str, Any]):
    def _call(*_args, **_kwargs) -> _SynthesizerOutput:
        return _SynthesizerOutput(
            tool_args=tool_args, input_tokens=4500, output_tokens=1500, latency_ms=6800
        )

    return _call


def _sequence_caller(outputs: list[dict[str, Any]]):
    state = {"i": 0}

    def _call(*_args, **_kwargs) -> _SynthesizerOutput:
        i = state["i"]
        state["i"] = i + 1
        return _SynthesizerOutput(
            tool_args=outputs[i], input_tokens=4500, output_tokens=1500, latency_ms=6800
        )

    return _call


# ─── Layer2Bundle + ParsedIntent ─────────────────────────────────────────────


class TestLayer2Bundle:
    def test_empty_bundle_construction(self):
        b = Layer2Bundle()
        assert b.a is None and b.b is None and b.c == {} and b.d is None and b.e is None

    def test_partial_bundle_construction(self):
        b = Layer2Bundle(a=_layer2a(), d=_layer2d())
        assert b.a is not None and b.d is not None and b.b is None

    def test_full_bundle_construction(self):
        b = _layer2_bundle()
        assert b.a is not None and b.c and b.d is not None

    def test_extra_field_forbidden(self):
        with pytest.raises(Exception):
            Layer2Bundle(unexpected_field="x")  # type: ignore[call-arg]


class TestParsedIntent:
    def test_default_construction(self):
        pi = ParsedIntent()
        assert pi.fatigue_signal == "normal"
        assert pi.sickness_signal == "none"
        assert pi.motivation_signal == "normal"
        assert pi.raw_text == ""
        assert pi.parser_confidence == "high"
        assert pi.triggers_2c_equipment == []

    def test_with_text_and_flags(self):
        pi = ParsedIntent(
            raw_text="I'm tired",
            fatigue_signal="tired",
            triggers_2d_injury=True,
            parser_confidence="medium",
        )
        assert pi.raw_text == "I'm tired"
        assert pi.fatigue_signal == "tired"
        assert pi.triggers_2d_injury is True

    def test_invalid_signal_rejected(self):
        with pytest.raises(Exception):
            ParsedIntent(fatigue_signal="exhausted")  # type: ignore[arg-type]


# ─── Tool schema ─────────────────────────────────────────────────────────────


class TestToolSchema:
    def test_t1_maxitems_4(self):
        t1 = build_record_refresh_sessions_tool("T1")
        assert t1["input_schema"]["properties"]["sessions"]["maxItems"] == 4

    def test_t2_maxitems_14(self):
        t2 = build_record_refresh_sessions_tool("T2")
        assert t2["input_schema"]["properties"]["sessions"]["maxItems"] == 14

    def test_tool_name(self):
        for tier in ("T1", "T2"):
            assert build_record_refresh_sessions_tool(tier)["name"] == "record_refresh_sessions"  # type: ignore[arg-type]

    def test_required_fields_cover_payload_invariants(self):
        sess_schema = build_record_refresh_sessions_tool("T1")["input_schema"]["properties"]["sessions"]["items"]
        required = set(sess_schema["required"])
        # Mirror PlanSession contract — same required fields as single_session tool
        for field in (
            "date",
            "day_of_week",
            "session_index_in_day",
            "time_of_day",
            "kind",
            "duration_min",
            "intensity_summary",
            "session_notes",
            "coaching_intent",
            "coaching_flags",
        ):
            assert field in required

    def test_coaching_flags_closed_7_set(self):
        sess_schema = build_record_refresh_sessions_tool("T1")["input_schema"]["properties"]["sessions"]["items"]
        flags_enum = sess_schema["properties"]["coaching_flags"]["items"]["enum"]
        assert set(flags_enum) == {
            "technique_emphasis",
            "long_slow_distance",
            "weak_link_targeted",
            "overreach_test",
            "discipline_specific_intensity",
            "race_pace_specific",
            "intensity_modulated",
        }

    def test_intensity_target_oneof_nine_shapes(self):
        sess_schema = build_record_refresh_sessions_tool("T1")["input_schema"]["properties"]["sessions"]["items"]
        cardio_items = sess_schema["properties"]["cardio_blocks"]["items"]
        one_of = cardio_items["properties"]["intensity_target"]["oneOf"]
        assert len(one_of) == 9

    def test_intensity_zone_closed_set(self):
        sess_schema = build_record_refresh_sessions_tool("T2")["input_schema"]["properties"]["sessions"]["items"]
        cardio_items = sess_schema["properties"]["cardio_blocks"]["items"]
        zone_enum = cardio_items["properties"]["intensity_zone"]["enum"]
        assert set(zone_enum) == {"Z1", "Z2", "Z3", "Z4", "Z5", "mixed"}

    def test_t3_maxitems_56(self):
        schema = build_record_refresh_sessions_tool("T3")
        assert schema["input_schema"]["properties"]["sessions"]["maxItems"] == 56


# ─── Input validation (§4.3) ─────────────────────────────────────────────────


def _call_t1(
    *,
    layer1=None,
    bundle=None,
    layer3a=None,
    layer3b=None,
    prior_window=None,
    plan_version_id_parent: int = 1,
    parsed_intent: ParsedIntent | None = None,
    llm_caller=None,
):
    return llm_layer4_plan_refresh(
        user_id=42,
        tier="T1",
        refresh_scope_start=_T1_START,
        refresh_scope_end=_T1_END,
        layer1_payload=layer1 if layer1 is not None else _layer1(),
        layer2_bundle=bundle if bundle is not None else _layer2_bundle(),
        layer3a_payload=layer3a if layer3a is not None else _layer3a(),
        layer3b_payload=layer3b if layer3b is not None else _layer3b(),
        prior_plan_session_window=prior_window
        if prior_window is not None
        else _prior_window(_T1_START, _T1_END),
        parsed_intent=parsed_intent,
        plan_version_id=2,
        plan_version_id_parent=plan_version_id_parent,
        etl_version_set={"layer0": "v7"},
        llm_caller=llm_caller
        or _stub_caller({"sessions": [_cardio_session(d=_T1_START)]}),
    )


class TestInputValidation:
    def test_missing_layer1_payload_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T1",
                refresh_scope_start=_T1_START,
                refresh_scope_end=_T1_END,
                layer1_payload=None,  # type: ignore[arg-type]
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "missing_upstream_payload"
        assert "layer1_payload" in (exc.value.detail or "")

    def test_missing_layer2_bundle_raises(self):
        # Layer2Bundle is required (non-None)
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T1",
                refresh_scope_start=_T1_START,
                refresh_scope_end=_T1_END,
                layer1_payload=_layer1(),
                layer2_bundle=None,  # type: ignore[arg-type]
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "missing_upstream_payload"
        assert "layer2_bundle" in (exc.value.detail or "")

    def test_missing_layer3a_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T1",
                refresh_scope_start=_T1_START,
                refresh_scope_end=_T1_END,
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=None,  # type: ignore[arg-type]
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "missing_upstream_payload"

    def test_missing_layer3b_raises(self):
        """§4.3 row 1 (Andy 2026-05-17 §4.3-wins pick): 3B required for
        T1/T2."""
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T1",
                refresh_scope_start=_T1_START,
                refresh_scope_end=_T1_END,
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=None,  # type: ignore[arg-type]
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "missing_upstream_payload"
        assert "layer3b_payload" in (exc.value.detail or "")

    def test_invalid_tier_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T9",  # type: ignore[arg-type]
                refresh_scope_start=_T1_START,
                refresh_scope_end=_T1_END,
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "tier_invalid"

    def test_scope_inverted_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T1",
                refresh_scope_start=_T1_END,  # reversed
                refresh_scope_end=_T1_START,
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "refresh_scope_inverted"

    def test_t1_scope_too_long_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T1",
                refresh_scope_start=_T1_START,
                refresh_scope_end=_T1_START + timedelta(days=4),  # 5 days > 3
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T1_START, _T1_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "tier_scope_mismatch"

    def test_t2_scope_too_long_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T2",
                refresh_scope_start=_T2_START,
                refresh_scope_end=_T2_START + timedelta(days=10),  # 11 days > 9
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(_T2_START, _T2_END),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "tier_scope_mismatch"

    def test_empty_prior_window_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            _call_t1(prior_window=[])
        assert exc.value.code == "prior_plan_window_empty"

    def test_plan_version_id_parent_zero_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            _call_t1(plan_version_id_parent=0)
        assert exc.value.code == "plan_version_id_parent_missing"

    def test_t3_plan_start_date_missing_raises(self):
        """Step 4d amendment: tier=T3 requires plan_start_date non-None."""
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T3",
                refresh_scope_start=_T2_START,
                refresh_scope_end=_T2_START + timedelta(days=27),
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(
                    _T2_START, _T2_START + timedelta(days=27), pre_days=7, post_days=7
                ),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                # plan_start_date intentionally omitted
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "plan_start_date_missing"

    def test_t3_scope_too_long_raises(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_refresh(
                user_id=42,
                tier="T3",
                refresh_scope_start=_T2_START,
                refresh_scope_end=_T2_START + timedelta(days=33),  # 34 days > 32
                layer1_payload=_layer1(),
                layer2_bundle=_layer2_bundle(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                prior_plan_session_window=_prior_window(
                    _T2_START, _T2_START + timedelta(days=33), pre_days=14, post_days=7
                ),
                parsed_intent=None,
                plan_version_id=2,
                plan_version_id_parent=1,
                etl_version_set={"layer0": "v7"},
                plan_start_date=_T2_START - timedelta(days=14),
                llm_caller=_stub_caller({"sessions": []}),
            )
        assert exc.value.code == "tier_scope_mismatch"

    def test_t3_cross_phase_routes_to_pattern_a(self):
        """Per Layer4_Spec.md §5.1 + §6.3: T3 with scope spanning a phase
        boundary routes to Pattern A (Step 4f closes the raise path).

        Verifies the delegate path runs to completion when stubbed callers
        return parseable per-phase and seam outputs.
        """
        from layer4.per_phase import _SynthesizerOutput as _PhaseOut
        from layer4.seam_review import _SeamReviewerOutput as _SeamOut

        plan_start = _T2_START - timedelta(days=35)  # athlete is at day 35

        def phase_stub(*_a, **_kw) -> _PhaseOut:
            return _PhaseOut(
                tool_args={
                    "sessions": [],
                    "phase_synthesis_notes": "rest week pull-back.",
                    "opportunities": [],
                },
                input_tokens=4000,
                output_tokens=200,
                latency_ms=5000,
            )

        def seam_stub(*_a, **_kw) -> _SeamOut:
            return _SeamOut(
                tool_args={
                    "reviewer_verdict": "approved",
                    "seam_issues": [],
                    "proposed_patch_direction": None,
                },
                input_tokens=2000,
                output_tokens=100,
                latency_ms=2500,
            )

        result = llm_layer4_plan_refresh(
            user_id=42,
            tier="T3",
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_START + timedelta(days=27),
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(start_phase="Base"),
            prior_plan_session_window=_prior_window(
                _T2_START, _T2_START + timedelta(days=27), pre_days=14, post_days=7
            ),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            plan_start_date=plan_start,
            phase_caller=phase_stub,
            seam_caller=seam_stub,
        )
        assert isinstance(result, Layer4Payload)
        assert result.mode == "plan_refresh"
        assert result.pattern == "A"
        assert result.phase_structure is not None
        assert result.seam_reviews is not None

    def test_t3_cross_phase_threads_cache_through_to_per_phase(self):
        """Step 6a: cache + call_cache_key thread from plan_refresh entry
        point through `_route_t3_cross_phase_to_pattern_a` →
        `synthesize_pattern_a_for_refresh` → `_run_pattern_a_engine`. The
        per-phase cache populates with `entry_point='plan_refresh'`."""
        from layer4 import InMemoryCacheBackend, Layer4Cache
        from layer4.per_phase import _SynthesizerOutput as _PhaseOut
        from layer4.seam_review import _SeamReviewerOutput as _SeamOut

        plan_start = _T2_START - timedelta(days=35)
        call_count = {"phase": 0, "seam": 0}

        def phase_stub(*_a, **_kw) -> _PhaseOut:
            call_count["phase"] += 1
            return _PhaseOut(
                tool_args={
                    "sessions": [],
                    "phase_synthesis_notes": "rest week pull-back.",
                    "opportunities": [],
                },
                input_tokens=4000,
                output_tokens=200,
                latency_ms=5000,
            )

        def seam_stub(*_a, **_kw) -> _SeamOut:
            call_count["seam"] += 1
            return _SeamOut(
                tool_args={
                    "reviewer_verdict": "approved",
                    "seam_issues": [],
                    "proposed_patch_direction": None,
                },
                input_tokens=2000,
                output_tokens=100,
                latency_ms=2500,
            )

        cache = Layer4Cache(InMemoryCacheBackend())
        # First call populates the per-phase cache.
        first = llm_layer4_plan_refresh(
            user_id=42,
            tier="T3",
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_START + timedelta(days=27),
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(start_phase="Base"),
            prior_plan_session_window=_prior_window(
                _T2_START, _T2_START + timedelta(days=27), pre_days=14, post_days=7
            ),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            plan_start_date=plan_start,
            phase_caller=phase_stub,
            seam_caller=seam_stub,
            cache=cache,
            call_cache_key="t3-cross-phase-abc",
        )
        assert isinstance(first, Layer4Payload)
        first_phase_calls = call_count["phase"]
        first_seam_calls = call_count["seam"]
        assert first_phase_calls >= 1  # cross-phase synthesizes at least 1 phase
        # phase_* counter covers per-phase + iter-1 seam sub-call rows; each
        # approved seam review is one fresh miss.
        assert cache.metrics.phase_misses_total == first_phase_calls + first_seam_calls

        # Verify per-phase rows are tagged 'plan_refresh' entry_point.
        backend = cache.backend
        entry_points = {e.entry_point for e in backend._rows.values()}  # type: ignore[attr-defined]
        assert entry_points == {"plan_refresh"}

        # Second call hits the per-phase cache.
        llm_layer4_plan_refresh(
            user_id=42,
            tier="T3",
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_START + timedelta(days=27),
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(start_phase="Base"),
            prior_plan_session_window=_prior_window(
                _T2_START, _T2_START + timedelta(days=27), pre_days=14, post_days=7
            ),
            parsed_intent=None,
            plan_version_id=3,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            plan_start_date=plan_start,
            phase_caller=phase_stub,
            seam_caller=seam_stub,
            cache=cache,
            call_cache_key="t3-cross-phase-abc",
        )
        # No new phase synthesizer calls (all hit); the iter-1 seam reviews
        # also replay from cache, so the seam reviewer doesn't re-fire.
        assert call_count["phase"] == first_phase_calls
        assert call_count["seam"] == first_seam_calls
        assert cache.metrics.phase_hits_total == first_phase_calls + first_seam_calls


# ─── T3 intra-phase Pattern B (Step 4d) ──────────────────────────────────────


def _call_t3_intra_phase(
    *,
    layer3b=None,
    plan_start_offset_days: int = -14,
    llm_caller=None,
    sessions_output: list[dict[str, Any]] | None = None,
):
    """Helper: T3 invocation with a plan_start_date positioned so the
    refresh scope falls entirely inside one phase.

    Defaults: plan_start_date = T2_START - 14 days (athlete is 2 weeks into
    the plan). With standard mode + Base start + 12-week total, Base runs
    weeks 1-6 (days 1-42); refresh days 15-42 → entirely inside Base.
    """
    plan_start = _T2_START + timedelta(days=plan_start_offset_days)
    scope_end = _T2_START + timedelta(days=27)
    if sessions_output is None:
        sessions_output = [
            _cardio_session(d=_T2_START + timedelta(days=offset))
            for offset in (0, 2, 4, 7, 9, 11, 14, 16, 18, 21, 23, 25)
        ]
    return llm_layer4_plan_refresh(
        user_id=42,
        tier="T3",
        refresh_scope_start=_T2_START,
        refresh_scope_end=scope_end,
        layer1_payload=_layer1(),
        layer2_bundle=_layer2_bundle(),
        layer3a_payload=_layer3a(),
        layer3b_payload=layer3b if layer3b is not None else _layer3b(start_phase="Base"),
        prior_plan_session_window=_prior_window(
            _T2_START, scope_end, pre_days=14, post_days=7
        ),
        parsed_intent=None,
        plan_version_id=2,
        plan_version_id_parent=1,
        etl_version_set={"layer0": "v7"},
        plan_start_date=plan_start,
        llm_caller=llm_caller or _stub_caller({"sessions": sessions_output}),
    )


class TestT3IntraPhase:
    def test_intra_phase_routes_to_pattern_b(self):
        """T3 inside Base phase: returns Pattern B payload with sessions."""
        result = _call_t3_intra_phase()
        assert isinstance(result, Layer4Payload)
        assert result.mode == "plan_refresh"
        assert result.pattern == "B"
        assert result.phase_structure is None
        assert result.seam_reviews is None
        assert len(result.sessions) == 12

    def test_intra_phase_sessions_inside_scope(self):
        result = _call_t3_intra_phase()
        for s in result.sessions:
            assert _T2_START <= s.date <= _T2_START + timedelta(days=27)
            assert s.phase_metadata is None
            assert s.is_ad_hoc is False

    def test_intra_phase_validator_results_accepted(self):
        result = _call_t3_intra_phase()
        assert result.validator_results
        assert result.validator_results[-1].accepted is True

    def test_intra_phase_empty_sessions_allowed(self):
        result = _call_t3_intra_phase(sessions_output=[])
        assert len(result.sessions) == 0
        assert result.validator_results[-1].accepted is True

    def test_intra_phase_t3_sizes_output_budget_to_session_ceiling(self):
        """T3 output budget is sized to its 56-session ceiling and clamped to the
        model's 64K limit, with thinking OFF — not the flat 10000 that truncated
        `record_refresh_sessions` (the #569 live verify caught the
        `schema_violation`). Verify via stub caller capture."""
        captured: dict[str, Any] = {}

        def _capturing_caller(
            _sys, _user, _tool, _model, _temp, max_tokens, thinking
        ) -> _SynthesizerOutput:
            captured["max_tokens"] = max_tokens
            captured["thinking"] = thinking
            return _SynthesizerOutput(
                tool_args={"sessions": []},
                input_tokens=9000,
                output_tokens=4000,
                latency_ms=11000,
            )

        _call_t3_intra_phase(llm_caller=_capturing_caller)
        # 56 * 1400 + 2000 = 80400, clamped to the 64K model ceiling.
        assert captured["max_tokens"] == 64000
        assert captured["thinking"] == 0

    def test_intra_phase_extended_mode_routes_correctly(self):
        """Extended mode: Base = 60% of 12wks = 7-8 weeks. Days 15-42 stay
        intra-Base."""
        # Use extended mode 3B
        l3b = _layer3b(start_phase="Base")
        l3b = Layer3BPayload(
            **{
                **l3b.model_dump(),
                "periodization_shape": PeriodizationShape(
                    mode="extended",
                    start_phase="Base",
                    phase_weeks=None,
                    reasoning_text="r",
                    evidence_basis=["e"],
                ).model_dump(),
            }
        )
        result = _call_t3_intra_phase(layer3b=l3b)
        assert result.mode == "plan_refresh"
        assert result.pattern == "B"


# ─── Output-budget sizing (create-path reuse) ────────────────────────────────


class TestOutputBudgetSizing:
    """The refresh driver sizes the synthesizer output budget to the tier's
    session ceiling via `per_phase.block_output_budget` — the same balancing the
    create per-phase path uses — instead of a flat per-tier constant that
    truncated dense blocks (the #569 live verify caught a T3 `schema_violation`)."""

    def test_block_output_budget_scales_per_session(self):
        from layer4.per_phase import block_output_budget

        assert block_output_budget(14) == 21600  # create per-week block
        assert block_output_budget(4) == 7600

    def test_block_output_budget_clamps_to_model_ceiling(self):
        from layer4.per_phase import block_output_budget

        # 56 × 1400 + 2000 = 80400 > 64K model ceiling → clamped.
        assert block_output_budget(56) == 64000

    def test_block_output_budget_respects_floor(self):
        from layer4.per_phase import block_output_budget

        # Caller floor wins when it exceeds the per-session estimate.
        assert block_output_budget(1, floor=9000) == 9000

    def test_t1_driver_sizes_budget_to_session_ceiling(self):
        captured: dict[str, Any] = {}

        def _capturing_caller(
            _sys, _user, _tool, _model, _temp, max_tokens, thinking
        ) -> _SynthesizerOutput:
            captured["max_tokens"] = max_tokens
            return _SynthesizerOutput(
                tool_args={"sessions": []},
                input_tokens=100,
                output_tokens=100,
                latency_ms=100,
            )

        _call_t1(llm_caller=_capturing_caller)
        assert captured["max_tokens"] == 7600  # 4 × 1400 + 2000


# ─── Entry-point happy path ──────────────────────────────────────────────────


class TestEntryPointHappyPath:
    def test_t1_cardio_single_session(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert isinstance(result, Layer4Payload)
        assert result.mode == "plan_refresh"
        assert result.pattern == "B"
        assert len(result.sessions) == 1
        assert result.sessions[0].kind == "cardio"

    def test_t1_two_sessions_across_two_days(self):
        result = _call_t1(
            llm_caller=_stub_caller(
                {
                    "sessions": [
                        _cardio_session(d=_T1_START),
                        _cardio_session(d=_T1_END),
                    ]
                }
            )
        )
        assert len(result.sessions) == 2
        assert {s.date for s in result.sessions} == {_T1_START, _T1_END}

    def test_t1_empty_sessions_allowed(self):
        """0 sessions is valid output (entire window is rest)."""
        result = _call_t1(llm_caller=_stub_caller({"sessions": []}))
        assert result.sessions == []
        assert result.mode == "plan_refresh"

    def test_t2_cardio_full_week(self):
        sessions = [
            _cardio_session(d=_T2_START + timedelta(days=i))
            for i in range(7)
        ]
        result = llm_layer4_plan_refresh(
            user_id=42,
            tier="T2",
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T2_START, _T2_END),
            parsed_intent=ParsedIntent(raw_text="standard week"),
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            llm_caller=_stub_caller({"sessions": sessions}),
        )
        assert len(result.sessions) == 7
        assert result.mode == "plan_refresh"
        assert result.pattern == "B"

    def test_t2_mixed_cardio_and_strength(self):
        sessions = [
            _cardio_session(d=_T2_START),
            _strength_session(d=_T2_START + timedelta(days=1)),
            _cardio_session(d=_T2_START + timedelta(days=2)),
        ]
        result = llm_layer4_plan_refresh(
            user_id=42,
            tier="T2",
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T2_START, _T2_END),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            llm_caller=_stub_caller({"sessions": sessions}),
        )
        assert len(result.sessions) == 3
        assert result.sessions[1].kind == "strength"

    def test_telemetry_fields_aggregated(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.llm_call_count == 1
        assert result.input_tokens_total == 4500
        assert result.output_tokens_total == 1500
        assert result.latency_ms_total == 6800

    def test_scope_dates_propagate(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.scope_start_date == _T1_START
        assert result.scope_end_date == _T1_END


# ─── Observation emission (§8.6/§8.7) ────────────────────────────────────────


class TestObservationEmission:
    def test_intensity_modulated_flag_emits_observation(self):
        result = _call_t1(
            llm_caller=_stub_caller(
                {
                    "sessions": [
                        _cardio_session(
                            d=_T1_START, coaching_flags=["intensity_modulated"]
                        )
                    ]
                }
            )
        )
        categories = [o.category for o in result.notable_observations]
        assert "intensity_modulated" in categories

    def test_no_flag_no_observation(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        categories = [o.category for o in result.notable_observations]
        assert "intensity_modulated" not in categories

    def test_multi_session_intensity_modulated_single_observation(self):
        """Per §8.6 broadening: whole-week modulation emits the flag on every
        affected session; orchestrator emits ONE paired Observation."""
        result = _call_t1(
            llm_caller=_stub_caller(
                {
                    "sessions": [
                        _cardio_session(
                            d=_T1_START, coaching_flags=["intensity_modulated"]
                        ),
                        _cardio_session(
                            d=_T1_END,
                            idx=0,
                            coaching_flags=["intensity_modulated"],
                        ),
                    ]
                }
            )
        )
        intensity_obs = [
            o for o in result.notable_observations if o.category == "intensity_modulated"
        ]
        assert len(intensity_obs) == 1
        # Text references 2 sessions affected
        assert "2" in intensity_obs[0].text


# ─── Capped retry (§5.5) ─────────────────────────────────────────────────────


def _injury_violating_session(d: date) -> dict[str, Any]:
    """Strength session on a discipline NOT in `_layer2a()`'s included set —
    fires `discipline_excluded_*` blocker (Rule 12, structural per spec §8).

    Was injury_violation (Rule 7) until Track 2 slice 2d demoted Rule 7 to
    warning; switched to Rule 12 as the still-blocker driver for the
    capped-retry tests below. Helper name preserved so the call sites read
    the same (the only thing the tests care about is "produces a blocker
    that drives a retry").
    """
    return _strength_session(
        d=d,
        exercise_ids=("E-banned",),
        discipline_id="D-not-included",
    )


class TestCappedRetry:
    def test_validator_fail_then_pass_retries_once(self):
        bundle_with_banned = Layer2Bundle(
            a=_layer2a(),
            c={"home_gym": _layer2c(exercise_ids=("E-banned",))},
            d=_layer2d(excluded=("E-banned",)),
        )
        good = {"sessions": [_strength_session(d=_T1_START, exercise_ids=("E-squat",))]}
        bad = {"sessions": [_injury_violating_session(_T1_START)]}
        # First pass: bad (violator); second pass: good — accepted
        bundle_with_both = Layer2Bundle(
            a=_layer2a(),
            c={"home_gym": _layer2c(exercise_ids=("E-squat", "E-banned"))},
            d=_layer2d(excluded=("E-banned",)),
        )
        result = llm_layer4_plan_refresh(
            user_id=42,
            tier="T1",
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=bundle_with_both,
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            llm_caller=_sequence_caller([bad, good]),
        )
        assert result.llm_call_count == 2
        # Validator results: first pass failed, second accepted
        assert result.validator_results[-1].accepted is True

    def test_cap_hit_emits_best_effort_observation(self):
        """Repeated validator failures → cap-hit + best_effort_plan
        observation."""
        bundle = Layer2Bundle(
            a=_layer2a(),
            c={"home_gym": _layer2c(exercise_ids=("E-banned",))},
            d=_layer2d(excluded=("E-banned",)),
        )
        bad = {"sessions": [_injury_violating_session(_T1_START)]}
        result = llm_layer4_plan_refresh(
            user_id=42,
            tier="T1",
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=bundle,
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            llm_caller=_sequence_caller([bad, bad, bad]),
        )
        assert result.llm_call_count == 3  # initial + 2 retries
        categories = [o.category for o in result.notable_observations]
        assert "best_effort_plan" in categories
        # validator_results[-1].accepted is True (best-effort demotion)
        assert result.validator_results[-1].accepted is True
        # Demoted: no blockers in the final validator pass
        final_blockers = [
            f for f in result.validator_results[-1].rule_failures if f.severity == "blocker"
        ]
        assert final_blockers == []

    def test_first_pass_accept_skips_retries(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.llm_call_count == 1
        assert len(result.validator_results) == 1

    def test_capped_retries_zero_no_retry_path(self):
        bundle = Layer2Bundle(
            a=_layer2a(),
            c={"home_gym": _layer2c(exercise_ids=("E-banned",))},
            d=_layer2d(excluded=("E-banned",)),
        )
        bad = {"sessions": [_injury_violating_session(_T1_START)]}
        result = llm_layer4_plan_refresh(
            user_id=42,
            tier="T1",
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=bundle,
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
            capped_retries=0,
            llm_caller=_stub_caller(bad),
        )
        assert result.llm_call_count == 1
        # cap=0 means single pass; if it fails, immediate best-effort
        categories = [o.category for o in result.notable_observations]
        assert "best_effort_plan" in categories


# ─── Schema violation (§5.5 special case) ────────────────────────────────────


class TestSchemaViolation:
    def test_missing_sessions_key_raises(self):
        with pytest.raises(Layer4OutputError) as exc:
            _call_t1(llm_caller=_stub_caller({"not_sessions": []}))
        assert exc.value.code == "schema_violation"

    def test_malformed_session_retries_then_raises(self):
        """All passes return malformed sessions → raises after schema-only
        retries exhaust."""
        bad = {"sessions": [{"date": "not-iso", "kind": "cardio"}]}
        with pytest.raises(Layer4OutputError) as exc:
            _call_t1(llm_caller=_sequence_caller([bad, bad, bad]))
        assert exc.value.code == "schema_violation"

    def test_malformed_then_valid_recovers(self):
        bad = {"sessions": [{"date": "not-iso", "kind": "cardio"}]}
        good = {"sessions": [_cardio_session(d=_T1_START)]}
        result = _call_t1(llm_caller=_sequence_caller([bad, good]))
        assert len(result.sessions) == 1


# ─── Layer4Payload composition ───────────────────────────────────────────────


class TestLayer4PayloadComposition:
    def test_mode_plan_refresh(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.mode == "plan_refresh"

    def test_pattern_b(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.pattern == "B"

    def test_phase_structure_none(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.phase_structure is None

    def test_seam_reviews_none(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.seam_reviews is None

    def test_suggestion_id_none(self):
        """Plan refresh doesn't carry a D-63 suggestion_id."""
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.suggestion_id is None

    def test_session_phase_metadata_none(self):
        """§7.12: mode=plan_refresh + pattern=B requires phase_metadata None."""
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        for s in result.sessions:
            assert s.phase_metadata is None

    def test_session_is_ad_hoc_false(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        for s in result.sessions:
            assert s.is_ad_hoc is False

    def test_model_synthesizer_recorded(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.model_synthesizer == "claude-sonnet-4-6"
        assert result.model_seam_reviewer is None

    def test_etl_version_set_propagated(self):
        result = _call_t1(
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]})
        )
        assert result.etl_version_set == {"layer0": "v7"}


# ─── Prompt rendering ────────────────────────────────────────────────────────


class TestPromptRendering:
    def test_t1_prompt_includes_athletes_words(self):
        from layer4.plan_refresh_t1 import render_user_prompt

        prompt = render_user_prompt(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(raw_text="I'm tired", fatigue_signal="tired"),
            retries_used=0,
            rule_failures=[],
        )
        assert "I'm tired" in prompt
        assert "tired" in prompt  # fatigue signal rendered

    def test_t1_prompt_no_text_renders_placeholder(self):
        from layer4.plan_refresh_t1 import render_user_prompt

        prompt = render_user_prompt(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        assert "refreshed without typing a note" in prompt

    def test_t1_prompt_retry_context_conditional(self):
        from layer4.payload import RuleFailure
        from layer4.plan_refresh_t1 import render_user_prompt

        rf = RuleFailure(
            rule_name="injury_violation_strength",
            phase_name=None,
            severity="blocker",
            detail="exercise E-banned violates injury exclusion",
            affected_session_ids=["S-001"],
        )
        prompt_with = render_user_prompt(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=1,
            rule_failures=[rf],
        )
        assert "Retry context" in prompt_with
        assert "injury_violation_strength" in prompt_with

        prompt_without = render_user_prompt(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        assert "Retry context" not in prompt_without

    def test_t2_prompt_includes_weekly_aggregate(self):
        from layer4.plan_refresh_t2 import render_user_prompt

        prompt = render_user_prompt(
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_END,
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T2_START, _T2_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        assert "Weekly aggregate" in prompt
        assert "T2 (7-day rolling window)" in prompt

    def test_t1_vs_t2_prompts_differ(self):
        from layer4.plan_refresh_t1 import render_user_prompt as render_t1
        from layer4.plan_refresh_t2 import render_user_prompt as render_t2

        kwargs = dict(
            layer1_payload=_layer1(),
            layer2_bundle=_layer2_bundle(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        p1 = render_t1(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            **kwargs,
        )
        p2 = render_t2(
            refresh_scope_start=_T2_START,
            refresh_scope_end=_T2_END,
            prior_plan_session_window=_prior_window(_T2_START, _T2_END),
            **kwargs,
        )
        assert "T1 (2-day rolling window)" in p1
        assert "T2 (7-day rolling window)" in p2
        assert "Weekly aggregate" in p2 and "Weekly aggregate" not in p1

    def test_active_injuries_rendered_when_present(self):
        from layer4.plan_refresh_t1 import render_user_prompt

        bundle = Layer2Bundle(a=_layer2a(), c={}, d=_layer2d(excluded=("E-wrist",)))
        prompt = render_user_prompt(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=bundle,
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        assert "EXCLUDE E-wrist" in prompt

    def test_terrain_feasibility_block_rendered_when_present(self):
        # #557 — the refresh prompt must carry the deterministic terrain-
        # feasibility block (mirrors create #540) so a refreshed plan never
        # prescribes a session the athlete can't physically do.
        from layer4.plan_refresh_t1 import render_user_prompt
        from layer4.session_feasibility import TerrainResolution

        feas = {
            "D-012": TerrainResolution(
                "D-012", "strength", "Home Gym",
                substitute_exercise_ids=["E-pull"],
            )
        }
        kwargs = dict(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=Layer2Bundle(a=_layer2a(), c={}, d=_layer2d()),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        with_feas = render_user_prompt(**kwargs, terrain_feasibility=feas)
        without = render_user_prompt(**kwargs)
        assert "=== Session feasibility" in with_feas
        assert "substitute a STRENGTH session" in with_feas
        # Omitted entirely when nothing was resolved (legacy/empty callers).
        assert "=== Session feasibility" not in without

    def test_event_window_overlay_rendered_when_segment_overlaps(self):
        # #581 WS-H — the refresh prompt must carry the date-scoped event-window
        # overlay (mirrors the create-side per_phase render) when a declared
        # window overlaps the refresh scope, and omit it otherwise.
        from layer4.plan_refresh_t1 import render_user_prompt
        from layer4.session_feasibility import (
            EventWindowOverride,
            EventWindowSegment,
            TerrainResolution,
        )

        seg = EventWindowSegment(
            _T1_START,
            _T1_END,
            (EventWindowOverride("indoor_only"),),
            {
                "D-001": TerrainResolution(
                    "D-001", "indoor", "Home Gym", machine="Treadmill",
                    note="indoor Treadmill at Home Gym",
                )
            },
        )
        kwargs = dict(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=Layer2Bundle(a=_layer2a(), c={}, d=_layer2d()),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
        )
        with_overlay = render_user_prompt(**kwargs, event_window_segments=[seg])
        without = render_user_prompt(**kwargs)
        assert "=== Event-window overlay" in with_overlay
        assert "indoor-only (no outdoor terrain available)" in with_overlay
        assert "Placement preference (soft)" in with_overlay
        # Omitted when no segment supplied (legacy/no-window refreshes).
        assert "=== Event-window overlay" not in without

    def test_event_window_overlay_absent_when_segment_outside_scope(self):
        # A window that doesn't overlap the refresh scope renders nothing.
        from datetime import timedelta

        from layer4.plan_refresh_t1 import render_user_prompt
        from layer4.session_feasibility import (
            EventWindowOverride,
            EventWindowSegment,
            TerrainResolution,
        )

        far = _T1_END + timedelta(days=30)
        seg = EventWindowSegment(
            far,
            far + timedelta(days=2),
            (EventWindowOverride("indoor_only"),),
            {
                "D-001": TerrainResolution(
                    "D-001", "indoor", "Home Gym", machine="Treadmill",
                    note="indoor Treadmill at Home Gym",
                )
            },
        )
        prompt = render_user_prompt(
            refresh_scope_start=_T1_START,
            refresh_scope_end=_T1_END,
            layer1_payload=_layer1(),
            layer2_bundle=Layer2Bundle(a=_layer2a(), c={}, d=_layer2d()),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            prior_plan_session_window=_prior_window(_T1_START, _T1_END),
            parsed_intent=ParsedIntent(),
            retries_used=0,
            rule_failures=[],
            event_window_segments=[seg],
        )
        assert "=== Event-window overlay" not in prompt

    def test_default_parsed_intent_when_none_passed(self):
        """When parsed_intent=None, the driver substitutes a degraded
        ParsedIntent with parser_confidence='low'."""
        result = _call_t1(
            parsed_intent=None,
            llm_caller=_stub_caller({"sessions": [_cardio_session(d=_T1_START)]}),
        )
        # The driver doesn't raise — the degraded ParsedIntent is rendered
        # internally and the synthesis proceeds.
        assert result.mode == "plan_refresh"


# ─── #698 Track 2 (Slice C2) — cardio drills on the plan-refresh path ────────


def _layer2c_with_drill(
    locale_id: str = "home_gym",
    drill_id: str = "EX290",
    drill_type: str = "Interval / Tempo",
    discipline_id: str = "D-run",
    coaching_cue: str | None = "6×3min @ VO2 / 3min jog",
) -> Layer2CPayload:
    """A locale 2C carrying one cardio-drill-type resolved exercise so the
    Slice-C2 refresh pool resolves non-empty for the `D-run` athlete."""
    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"layer0": "v7"},
        effective_pool=[drill_id],
        discipline_coverage=[
            DisciplineCoverage(
                discipline_id=discipline_id,
                discipline_name=discipline_id,
                exercise_db_sport="x",
                total_exercises=1,
                tier_1_count=1,
                tier_2_count=0,
                tier_3_count=0,
                unavailable_count=0,
                coverage_pct=1.0,
            )
        ],
        exercises_resolved=[
            ResolvedExercise(
                exercise_id=drill_id,
                exercise_name="Flat VO2max Run Intervals",
                exercise_type=drill_type,
                discipline_ids=[discipline_id],
                sport_relevance_notes={discipline_id: "x"},
                priority_per_discipline={discipline_id: "High"},
                tier=1,
                terrain_required=[],
                contraindicated_parts=[],
                contraindicated_conditions=[],
                accommodations=[],
                coaching_cue=coaching_cue,
            )
        ],
        coaching_flags=[],
    )


def _bundle_with_drill() -> Layer2Bundle:
    return Layer2Bundle(
        a=_layer2a(),
        b=None,
        c={"home_gym": _layer2c_with_drill()},
        d=_layer2d(),
        e=None,
    )


def _capturing_caller(tool_args: dict[str, Any]):
    """An LLMCaller that records the (system_prompt, user_prompt, tool_schema)
    it was handed and returns `tool_args`."""
    captured: dict[str, Any] = {}

    def _call(*args, **_kwargs) -> _SynthesizerOutput:
        captured["system_prompt"] = args[0]
        captured["user_prompt"] = args[1]
        captured["tool_schema"] = args[2]
        return _SynthesizerOutput(
            tool_args=tool_args,
            input_tokens=10,
            output_tokens=10,
            latency_ms=5,
        )

    return _call, captured


class TestCardioDrillsSliceC2:
    def test_schema_has_capped_cardio_drills_block(self):
        for tier in ("T1", "T2", "T3"):
            sess = build_record_refresh_sessions_tool(tier)["input_schema"][  # type: ignore[arg-type]
                "properties"
            ]["sessions"]["items"]
            drills = sess["properties"]["cardio_drills"]
            assert drills["type"] == ["array", "null"]
            assert drills["maxItems"] == 1
            assert drills["items"]["required"] == [
                "exercise_id",
                "exercise_name",
                "prescription",
            ]

    def test_exercise_id_enum_bound_when_pool_nonempty(self):
        sess = build_record_refresh_sessions_tool(
            "T1", cardio_drill_pool_ids=["EX290", "EX073"]
        )["input_schema"]["properties"]["sessions"]["items"]
        prop = sess["properties"]["cardio_drills"]["items"]["properties"]["exercise_id"]
        assert prop == {"type": "string", "enum": ["EX290", "EX073"]}

    def test_exercise_id_free_string_when_pool_empty(self):
        sess = build_record_refresh_sessions_tool("T1", cardio_drill_pool_ids=None)[
            "input_schema"
        ]["properties"]["sessions"]["items"]
        prop = sess["properties"]["cardio_drills"]["items"]["properties"]["exercise_id"]
        assert prop == {"type": "string"}

    def test_build_session_output_parses_cardio_drills(self):
        from layer4.plan_refresh import _build_plan_session as _build_session_output

        data = _cardio_session(d=_T1_START)
        data["cardio_drills"] = [
            {
                "exercise_id": "EX290",
                "exercise_name": "Flat VO2max Run Intervals",
                "prescription": "6×3min @ VO2 / 3min jog",
                "instructions": "Hold even splits across reps.",
            }
        ]
        sess = _build_session_output(data, session_id="S-x", plan_version_id=2)
        assert sess.cardio_drills is not None
        assert sess.cardio_drills[0].exercise_id == "EX290"

    def test_prompt_section_and_menu_appear_when_pool_nonempty(self):
        out = _cardio_session(d=_T1_START)
        out["cardio_drills"] = [
            {
                "exercise_id": "EX290",
                "exercise_name": "Flat VO2max Run Intervals",
                "prescription": "6×3min @ VO2 / 3min jog",
                "instructions": None,
            }
        ]
        caller, captured = _capturing_caller({"sessions": [out]})
        result = _call_t1(bundle=_bundle_with_drill(), llm_caller=caller)
        assert result.sessions[0].cardio_drills is not None
        assert result.sessions[0].cardio_drills[0].exercise_id == "EX290"
        # the ratified prompt section + the rendered menu both reach the model
        assert "# Cardio drills" in captured["system_prompt"]
        assert "=== Cardio drill pool (consider these) ===" in captured["user_prompt"]
        assert "EX290" in captured["user_prompt"]
        # enum-bound at the SDK boundary
        prop = captured["tool_schema"]["input_schema"]["properties"]["sessions"][
            "items"
        ]["properties"]["cardio_drills"]["items"]["properties"]["exercise_id"]
        assert prop == {"type": "string", "enum": ["EX290"]}

    def test_prompt_section_and_menu_suppressed_when_pool_empty(self):
        # default bundle's 2C carries only strength-type exercises → empty pool
        caller, captured = _capturing_caller(
            {"sessions": [_cardio_session(d=_T1_START)]}
        )
        _call_t1(llm_caller=caller)
        assert "# Cardio drills" not in captured["system_prompt"]
        assert "Cardio drill pool" not in captured["user_prompt"]
        prop = captured["tool_schema"]["input_schema"]["properties"]["sessions"][
            "items"
        ]["properties"]["cardio_drills"]["items"]["properties"]["exercise_id"]
        assert prop == {"type": "string"}


class TestStructuredCardio337:
    """#337 — structured cardio prescription on the refresh path: the shared
    `# Cardio programming` section is always in the system prompt, and the
    measured-physiology block reaches the user prompt only when Layer 1 carries
    a physiological anchor (suppress-on-empty)."""

    def test_cardio_programming_section_always_in_system_prompt(self):
        caller, captured = _capturing_caller(
            {"sessions": [_cardio_session(d=_T1_START)]}
        )
        _call_t1(llm_caller=caller)
        assert "# Cardio programming" in captured["system_prompt"]
        assert "ground intensity targets" in captured["system_prompt"].lower() or (
            "measured physiology" in captured["system_prompt"].lower()
        )

    def test_measured_physiology_surfaced_when_anchors_present(self):
        caller, captured = _capturing_caller(
            {"sessions": [_cardio_session(d=_T1_START)]}
        )
        layer1 = {
            "experience_level": "advanced",
            "coach_notes": None,
            "performance": {
                "hrmax_bpm": 188,
                "lactate_threshold_hr_bpm": 168,
                "cycling_ftp_w": 245,
            },
        }
        _call_t1(layer1=layer1, llm_caller=caller)
        assert "Measured physiology" in captured["user_prompt"]
        assert "HR max 188 bpm" in captured["user_prompt"]
        assert "LT-HR 168 bpm" in captured["user_prompt"]
        assert "cycling FTP 245 W" in captured["user_prompt"]

    def test_measured_physiology_suppressed_when_no_anchors(self):
        caller, captured = _capturing_caller(
            {"sessions": [_cardio_session(d=_T1_START)]}
        )
        _call_t1(llm_caller=caller)  # default _layer1() has no `performance`
        assert "Measured physiology" not in captured["user_prompt"]
