"""Tests for `layer4/plan_create.py` + `layer4/per_phase.py` + `layer4/seam_review.py`
— Step 4f integration: `llm_layer4_plan_create` Pattern A per `Layer4_Spec.md` §3.1.

Coverage:
- Tool schemas (record_phase_sessions + record_seam_review) — shapes, enums, oneOf
- §4.2 input validation preconditions (missing payloads + plan_start_date_in_past
  + plan_version_id_unset + time_to_event_weeks_mismatch + discipline_weights_invalid)
- Entry-point happy path × open-ended + event-mode + start_phase != Base
- Per-phase synthesis loop (sessions filled with phase_metadata; phase_structure
  with synthesis_metadata overwritten)
- Seam review loop × approved + flagged_minor + flagged_major+re_prompt
- Propose-patch authority — re-synthesizes target phase + re-runs seam (iter 2)
- Per-seam cap — iter 2 still flagged emits seam_unresolved observation
- Per-phase retry budget shared between validator-driven + seam-driven retries
- Capped retry budget exhaustion → seam_unresolved when target budget hit
- Layer4Payload composition invariants (mode='plan_create', pattern='A',
  phase_structure non-None, seam_reviews non-None, suggestion_id None,
  each session.phase_metadata non-None)
- T3 cross-phase Pattern A delegation (via plan_refresh entry point) — already
  covered in test_layer4_plan_refresh.py::test_t3_cross_phase_routes_to_pattern_a;
  additional T3-specific Pattern A tests live there
- Prompt rendering snippets — phase block, prior phase context, race_event_payload

LLM calls are mocked via stub callers. No real Anthropic SDK invocations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from layer4 import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    CurrentState,
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DataDensity,
    DisciplineCoverage,
    GoalViability,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2BPayload,
    Layer2BSummaryBlock,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3APayload,
    Layer3BPayload,
    Layer4InputError,
    Layer4OutputError,
    Layer4Payload,
    MacroTargets,
    PeriodizationShape,
    PhaseLoadBands,
    PhaseStructure,
    RaceDayFueling,
    RaceEventPayload,
    RationaleMetadata,
    RecentTrajectory,
    ResolvedExercise,
    RouteLocale,
    SupplementIntegrationPayload,
    TrainingGapsSummary,
    TrajectoryWindow,
    WeightResult,
    build_record_phase_sessions_tool,
    build_record_seam_review_tool,
    llm_layer4_plan_create,
)
from layer4 import InMemoryCacheBackend, Layer4Cache
from layer4.plan_create import _SEAM_CACHE_PHASE_IDX_BASE
from layer4.per_phase import _SynthesizerOutput as _PhaseOut
from layer4.seam_review import _SeamReviewerOutput as _SeamOut


# ─── Fixtures ────────────────────────────────────────────────────────────────


_PLAN_START = date(2026, 6, 1)  # Mon


def _layer1() -> dict[str, Any]:
    return {
        "experience_level": "advanced",
        "coaching_voice_preferences": None,
        "available_days_per_week": 5,
    }


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


def _layer2b() -> Layer2BPayload:
    return Layer2BPayload(
        etl_version_set={"layer0": "v7"},
        race_terrain=[],
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
        terrain_gaps=[],
        coaching_flags=[],
    )


def _layer2c() -> dict[str, Layer2CPayload]:
    return {
        "home_gym": Layer2CPayload(
            locale_id="home_gym",
            etl_version_set={"layer0": "v7"},
            effective_pool=["E-squat", "E-pushup"],
            discipline_coverage=[
                DisciplineCoverage(
                    discipline_id="D-run",
                    discipline_name="Running",
                    exercise_db_sport="x",
                    total_exercises=2,
                    tier_1_count=2,
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
                    discipline_ids=["D-run"],
                    sport_relevance_notes={"D-run": "x"},
                    priority_per_discipline={"D-run": "Medium"},
                    tier=1,
                    terrain_required=[],
                    contraindicated_parts=[],
                    contraindicated_conditions=[],
                    accommodations=[],
                )
                for ex in ("E-squat", "E-pushup")
            ],
            coaching_flags=[],
        )
    }


def _layer2d() -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"layer0": "v7"},
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


def _layer2e() -> Layer2EPayload:
    targets = DailyPhaseTargets(
        activity_multiplier=1.6,
        activity_multiplier_source={"row": "base"},
        daily_calorie_target_kcal=2800,
        macros=MacroTargets(
            cho_g=400,
            cho_g_per_kg=5.7,
            cho_kcal=1600,
            protein_g=140,
            protein_g_per_kg=2.0,
            protein_kcal=560,
            fat_g=70,
            fat_kcal=630,
            fat_floor_constrained=False,
        ),
    )
    return Layer2EPayload(
        athlete_id="A-1",
        etl_version_set={"layer0": "v7"},
        computed_at=datetime(2026, 5, 31, 10, 0, 0),
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
        race_day_fueling=[],
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
                level="good",
                confidence="high",
                reasoning_text="r",
                evidence_basis=["e"],
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


def _layer3b(
    mode: str = "standard",
    start_phase: str = "Base",
    time_to_event_weeks: int | None = None,
) -> Layer3BPayload:
    base_mode = "event" if time_to_event_weeks else "no-event"
    fields: dict[str, Any] = {
        "user_id": 42,
        "as_of": datetime(2026, 5, 31, 10, 0, 0),
        "model": "claude-opus-4-7",
        "temperature": 0.0,
        "prompt_hash": "abc",
        "latency_ms": 1500,
        "input_tokens": 3000,
        "output_tokens": 800,
        "etl_version_set": {"layer0": "v7"},
        "mode": base_mode,
        "goal_viability": GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="solid base",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        "periodization_shape": PeriodizationShape(
            mode=mode,  # type: ignore[arg-type]
            start_phase=start_phase,  # type: ignore[arg-type]
            phase_weeks=None,
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        "hitl_surface": [],
        "notable_observations": [],
    }
    if time_to_event_weeks is not None:
        fields["time_to_event_weeks"] = time_to_event_weeks
        fields["event_date"] = _PLAN_START + timedelta(days=time_to_event_weeks * 7)
        fields["race_format"] = "single_day"
        fields["event_locale_id"] = "home_gym"
    return Layer3BPayload(**fields)


def _race_event(weeks_out: int = 8) -> RaceEventPayload:
    return RaceEventPayload(
        race_event_id=1,
        user_id=42,
        name="Test Race",
        event_date=_PLAN_START + timedelta(days=weeks_out * 7),
        race_format="single_day",
        distance_km=Decimal("42.2"),
        total_elevation_gain_m=None,
        race_rules_summary=None,
        mandatory_gear_text=None,
        event_locale_id=None,
        event_locale_mapbox_id="poi.test_anchor",
        is_target_event=True,
        notes=None,
        route_locales=[],
    )


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
                "duration_min": max(1, duration_min - 20),
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


def _empty_phase_output() -> dict[str, Any]:
    return {
        "sessions": [],
        "phase_synthesis_notes": "deload taper.",
        "opportunities": [],
    }


def _phase_output_with_sessions(
    *,
    phase_start: date,
    phase_weeks: int,
    flags: list[str] | None = None,
) -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    for w in range(phase_weeks):
        wk_start = phase_start + timedelta(days=w * 7)
        for day_offset in (0, 2, 4):
            d = wk_start + timedelta(days=day_offset)
            sessions.append(_cardio_session(d=d, coaching_flags=flags or []))
    return {
        "sessions": sessions,
        "phase_synthesis_notes": f"{phase_weeks}wk phase.",
        "opportunities": [],
    }


def _phase_stub(output: dict[str, Any]):
    def _call(*_a, **_kw) -> _PhaseOut:
        return _PhaseOut(
            tool_args=output, input_tokens=6000, output_tokens=2000, latency_ms=8000
        )

    return _call


def _phase_seq_stub(outputs: list[dict[str, Any]]):
    state = {"i": 0}

    def _call(*_a, **_kw) -> _PhaseOut:
        i = state["i"]
        state["i"] = i + 1
        return _PhaseOut(
            tool_args=outputs[min(i, len(outputs) - 1)],
            input_tokens=6000,
            output_tokens=2000,
            latency_ms=8000,
        )

    return _call


def _total_blocks(phase_structure) -> int:
    """D-77: the engine synthesizes one unit per week-block, so the synthesizer
    call count + the per-block cache-row count equal the number of blocks (not
    phases). A phase contributes ceil(weeks / _BLOCK_WEEKS) blocks."""
    from layer4.plan_create import _BLOCK_WEEKS

    return sum(-(-p.weeks // _BLOCK_WEEKS) for p in phase_structure.phases)


def _plan_session_on(d: date):
    """Build one valid PlanSession dated `d` (for prompt-continuity tests)."""
    from layer4.per_phase import _build_plan_session
    from layer4.phase_structure import phase_structure_from_3b

    ps = phase_structure_from_3b(_layer3b(), _PLAN_START)
    return _build_plan_session(
        _cardio_session(d=d),
        session_id=f"S-prior-{d.isoformat()}",
        plan_version_id=1,
        phase_spec=ps.phases[0],
    )


def _seam_stub_approved():
    def _call(*_a, **_kw) -> _SeamOut:
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

    return _call


def _seam_stub_flagged_minor(issue: str = "minor edge"):
    def _call(*_a, **_kw) -> _SeamOut:
        return _SeamOut(
            tool_args={
                "reviewer_verdict": "flagged_minor",
                "seam_issues": [issue],
                "proposed_patch_direction": None,
            },
            input_tokens=2000,
            output_tokens=100,
            latency_ms=2500,
        )

    return _call


def _seam_stub_flagged_major_then_approved():
    """First call: flagged_major + re_prompt_next; second call: approved."""
    state = {"i": 0}

    def _call(*_a, **_kw) -> _SeamOut:
        i = state["i"]
        state["i"] = i + 1
        if i == 0:
            return _SeamOut(
                tool_args={
                    "reviewer_verdict": "flagged_major",
                    "seam_issues": ["Peak entry too aggressive"],
                    "proposed_patch_direction": "re_prompt_next",
                },
                input_tokens=2000,
                output_tokens=100,
                latency_ms=2500,
            )
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

    return _call


class _CountingSeamStub:
    """Approved-verdict seam reviewer that counts invocations — proves the
    iter-1 seam cache skips the LLM call on a resume."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_a, **_kw) -> _SeamOut:
        self.calls += 1
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


# ─── Tool schema tests ───────────────────────────────────────────────────────


class TestRecordPhaseSessionsTool:
    def test_tool_name(self):
        t = build_record_phase_sessions_tool()
        assert t["name"] == "record_phase_sessions"

    def test_required_top_level_fields(self):
        t = build_record_phase_sessions_tool()
        req = set(t["input_schema"]["required"])
        assert "sessions" in req
        assert "phase_synthesis_notes" in req

    def test_max_sessions_configurable(self):
        t = build_record_phase_sessions_tool(max_sessions=28)
        assert t["input_schema"]["properties"]["sessions"]["maxItems"] == 28

    def test_phase_synthesis_notes_maxlength(self):
        t = build_record_phase_sessions_tool()
        assert t["input_schema"]["properties"]["phase_synthesis_notes"]["maxLength"] == 600

    def test_opportunities_optional_max_3(self):
        t = build_record_phase_sessions_tool()
        opp_schema = t["input_schema"]["properties"]["opportunities"]
        assert opp_schema["maxItems"] == 3

    def test_coaching_flags_6_LLM_emittable(self):
        t = build_record_phase_sessions_tool()
        sess_items = t["input_schema"]["properties"]["sessions"]["items"]
        flags = sess_items["properties"]["coaching_flags"]["items"]["enum"]
        assert set(flags) == {
            "technique_emphasis",
            "long_slow_distance",
            "weak_link_targeted",
            "overreach_test",
            "discipline_specific_intensity",
            "race_pace_specific",
        }
        # Pattern A per-phase does NOT emit intensity_modulated.
        assert "intensity_modulated" not in flags

    def test_session_kind_includes_rest(self):
        t = build_record_phase_sessions_tool()
        sess_items = t["input_schema"]["properties"]["sessions"]["items"]
        assert set(sess_items["properties"]["kind"]["enum"]) == {
            "cardio",
            "strength",
            "rest",
        }

    def test_intensity_target_oneof_nine_shapes(self):
        t = build_record_phase_sessions_tool()
        cb_items = (
            t["input_schema"]["properties"]["sessions"]["items"][
                "properties"
            ]["cardio_blocks"]["items"]
        )
        assert len(cb_items["properties"]["intensity_target"]["oneOf"]) == 9


class TestRecordSeamReviewTool:
    def test_tool_name(self):
        t = build_record_seam_review_tool()
        assert t["name"] == "record_seam_review"

    def test_verdict_enum(self):
        t = build_record_seam_review_tool()
        assert set(t["input_schema"]["properties"]["reviewer_verdict"]["enum"]) == {
            "approved",
            "flagged_minor",
            "flagged_major",
            "patched",
        }

    def test_seam_issues_maxitems_4(self):
        t = build_record_seam_review_tool()
        assert t["input_schema"]["properties"]["seam_issues"]["maxItems"] == 4

    def test_direction_enum_with_null(self):
        t = build_record_seam_review_tool()
        enum = t["input_schema"]["properties"]["proposed_patch_direction"]["enum"]
        assert None in enum
        assert "re_prompt_prior" in enum
        assert "re_prompt_next" in enum
        assert "accept_with_observation" in enum


# ─── §4.2 input validation ───────────────────────────────────────────────────


def _call_kwargs() -> dict[str, Any]:
    """Minimum kwargs to invoke llm_layer4_plan_create."""
    return {
        "user_id": 42,
        "layer1_payload": _layer1(),
        "layer2a_payload": _layer2a(),
        "layer2b_payload": _layer2b(),
        "layer2c_payloads": _layer2c(),
        "layer2d_payload": _layer2d(),
        "layer2e_payload": _layer2e(),
        "layer3a_payload": _layer3a(),
        "layer3b_payload": _layer3b(),
        "plan_start_date": _PLAN_START,
        "plan_version_id": 1,
        "etl_version_set": {"layer0": "v7"},
    }


class TestInputValidation:
    def test_missing_layer1(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "layer1_payload": None},
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "missing_upstream_payload"

    def test_missing_layer2a(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "layer2a_payload": None},
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "missing_upstream_payload"

    def test_missing_layer2c_empty(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "layer2c_payloads": {}},
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "missing_upstream_payload"

    def test_missing_layer3b(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "layer3b_payload": None},
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "missing_upstream_payload"

    def test_plan_start_date_in_past(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "plan_start_date": date(2020, 1, 1)},
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "plan_start_date_in_past"

    def test_plan_version_id_unset(self):
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "plan_version_id": 0},
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "plan_version_id_unset"

    def test_time_to_event_weeks_mismatch(self):
        """3B time_to_event_weeks=20 but race_event_payload at 8 weeks → mismatch."""
        l3b = _layer3b(time_to_event_weeks=20)
        re = _race_event(weeks_out=8)
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_plan_create(
                **{**_call_kwargs(), "layer3b_payload": l3b},
                race_event_payload=re,
                phase_caller=_phase_stub(_empty_phase_output()),
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "time_to_event_weeks_mismatch"


# ─── Entry-point happy path ──────────────────────────────────────────────────


class TestEntryPointHappyPath:
    def test_open_ended_plan_returns_layer4_payload(self):
        """Open-ended plan (no race_event), Base start, standard mode →
        12-week horizon; all 4 phases synthesized."""
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        assert result.mode == "plan_create"
        assert result.pattern == "A"
        assert result.phase_structure is not None
        assert result.seam_reviews is not None

    def test_phase_structure_populated(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result.phase_structure, PhaseStructure)
        assert len(result.phase_structure.phases) > 0

    def test_synthesis_metadata_overwritten_per_phase(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.phase_structure is not None
        for phase in result.phase_structure.phases:
            sm = phase.synthesis_metadata
            # Default placeholder is model='(unsynthesized)'; after synth
            # the orchestrator overwrites with the real model name.
            assert sm.model != "(unsynthesized)"
            assert sm.model == "claude-sonnet-4-6"

    def test_seam_reviews_one_per_adjacent_pair(self):
        """4 phases → 3 seams."""
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.phase_structure is not None
        assert result.seam_reviews is not None
        n_phases = len(result.phase_structure.phases)
        assert len(result.seam_reviews) == n_phases - 1

    def test_sessions_filled_with_phase_metadata(self):
        """When per-phase synthesizer emits sessions, each PlanSession gets
        `phase_metadata` populated from the PhaseSpec (per §7.12 + §7.5).
        Tested directly against `_build_plan_session` to avoid validator-
        driven retries on undersized test outputs."""
        from layer4.per_phase import _build_plan_session
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        phase0 = ps.phases[0]
        session_dict = _cardio_session(d=phase0.start_date)
        s = _build_plan_session(
            session_dict,
            session_id="S-x",
            plan_version_id=1,
            phase_spec=phase0,
        )
        assert s.phase_metadata is not None
        assert s.phase_metadata.phase_name == phase0.phase_name
        assert s.phase_metadata.week_in_phase >= 1
        assert s.phase_metadata.total_weeks_in_phase == phase0.weeks
        assert (
            s.phase_metadata.intended_intensity_distribution
            == phase0.intended_intensity_distribution
        )

    def test_telemetry_aggregated(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.input_tokens_total > 0
        assert result.output_tokens_total > 0
        assert result.latency_ms_total > 0
        # D-77: one synthesis call per week-block + (n_phases - 1) seam reviews.
        assert result.phase_structure is not None
        n_phases = len(result.phase_structure.phases)
        total_blocks = _total_blocks(result.phase_structure)
        assert result.llm_call_count == total_blocks + max(0, n_phases - 1)

    def test_validator_results_last_accepted(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.validator_results
        assert result.validator_results[-1].accepted is True

    def test_start_phase_taper_only(self):
        """start_phase='Taper' + standard mode = only Taper phase synthesized;
        no seam reviews."""
        l3b = _layer3b(mode="standard", start_phase="Taper")
        result = llm_layer4_plan_create(
            **{**_call_kwargs(), "layer3b_payload": l3b},
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.phase_structure is not None
        assert len(result.phase_structure.phases) == 1
        assert result.phase_structure.phases[0].phase_name == "Taper"
        assert result.seam_reviews == []

    def test_event_mode_with_race_event_payload(self):
        l3b = _layer3b(time_to_event_weeks=8)
        re = _race_event(weeks_out=8)
        result = llm_layer4_plan_create(
            **{**_call_kwargs(), "layer3b_payload": l3b},
            race_event_payload=re,
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.mode == "plan_create"
        assert result.phase_structure is not None
        assert result.phase_structure.total_weeks == 8


# ─── Seam review orchestration ───────────────────────────────────────────────


class TestSeamReview:
    def test_approved_seam_no_observation(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        # No seam-related observations on approved seams.
        for obs in result.notable_observations:
            assert obs.category not in ("warning", "seam_unresolved")
        for sr in result.seam_reviews or []:
            assert sr.reviewer_verdict == "approved"
            assert sr.triggered_resynthesis is False

    def test_flagged_minor_emits_warning_observation(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_flagged_minor("seams a bit rough"),
        )
        warning_obs = [
            o for o in result.notable_observations if o.category == "warning"
        ]
        assert len(warning_obs) >= 1
        assert any("seams a bit rough" in o.text for o in warning_obs)
        for sr in result.seam_reviews or []:
            assert sr.reviewer_verdict == "flagged_minor"
            assert sr.triggered_resynthesis is False

    def test_flagged_major_re_prompt_next_triggers_resynthesis(self):
        """First seam flagged_major+re_prompt_next → next phase re-synthesized →
        iter-2 seam approves."""
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_flagged_major_then_approved(),
        )
        # First seam should record triggered_resynthesis=True with re_prompted
        # phase set to the next phase (Build, when we have Base→Build).
        srs = result.seam_reviews or []
        assert srs
        first_seam = srs[0]
        # After iter-2 approval, the recorded verdict is approved.
        assert first_seam.reviewer_verdict == "approved"
        assert first_seam.triggered_resynthesis is True


# ─── Layer4Payload composition invariants ────────────────────────────────────


class TestPayloadComposition:
    def test_mode_plan_create(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.mode == "plan_create"

    def test_pattern_A(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.pattern == "A"

    def test_phase_structure_non_none(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.phase_structure is not None

    def test_seam_reviews_non_none(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.seam_reviews is not None

    def test_suggestion_id_none(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.suggestion_id is None

    def test_race_week_brief_none(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.race_week_brief is None
        assert result.race_plan is None

    def test_model_seam_reviewer_recorded(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.model_seam_reviewer == "claude-sonnet-4-6"

    def test_etl_version_set_propagated(self):
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.etl_version_set == {"layer0": "v7"}


# ─── per_phase rendering snippets ────────────────────────────────────────────


class TestPerPhasePromptRendering:
    def test_phase_block_includes_phase_name_and_weeks(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
        )
        assert ps.phases[0].phase_name in text
        assert f"{ps.phases[0].weeks} weeks" in text

    def test_first_phase_no_prior_context(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
        )
        assert "First phase of plan; no prior context." in text

    def test_open_ended_mode_no_race_pace_specific(self):
        """Open-ended mode prompt instructs no race_pace_specific."""
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
        )
        assert "Do NOT emit `race_pace_specific`" in text

    def test_race_event_route_locales_rendered(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b(time_to_event_weeks=8)
        ps = phase_structure_from_3b(l3b, _PLAN_START, total_weeks=8)
        re = RaceEventPayload(
            race_event_id=1,
            user_id=42,
            name="3-Day Stage",
            event_date=_PLAN_START + timedelta(weeks=8),
            race_format="stage_race",
            distance_km=Decimal("100.0"),
            total_elevation_gain_m=Decimal("2500"),
            race_rules_summary=None,
            mandatory_gear_text=None,
            event_locale_id=None,
            event_locale_mapbox_id="poi.test_anchor",
            is_target_event=True,
            notes=None,
            route_locales=[
                RouteLocale(
                    route_locale_id=1,
                    role="start",
                    sequence_idx=1,
                    name="Start Line",
                ),
                RouteLocale(
                    route_locale_id=2,
                    role="aid_station",
                    sequence_idx=2,
                    name="AS1",
                ),
                RouteLocale(
                    route_locale_id=3,
                    role="finish",
                    sequence_idx=3,
                    name="Finish",
                ),
            ],
        )
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=re,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
        )
        assert "stage_race" in text
        assert "Start Line" in text
        assert "Finish" in text
        assert "aid_station" in text

    def test_retry_context_conditional(self):
        from layer4.per_phase import render_user_prompt
        from layer4.payload import RuleFailure
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=1,
            rule_failures=[
                RuleFailure(
                    rule_name="volume_band_high",
                    phase_name="Base",
                    severity="blocker",
                    detail="weekly volume exceeded band",
                    affected_session_ids=["S-x"],
                )
            ],
            seam_issues=[],
            seam_direction=None,
        )
        assert "Retry context" in text
        assert "volume_band_high" in text

    def test_seam_driven_retry_context(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=1,
            rule_failures=[],
            seam_issues=["Peak entry must hold ≥60% Z2."],
            seam_direction="re_prompt_next",
        )
        assert "Seam-driven re-prompt" in text
        assert "Peak entry must hold ≥60% Z2." in text


# ─── FormRefresh Slice C: long-session day = longest enabled window ──────────


class TestDailyWindowsSchedule:
    """`per_phase._format_daily_windows_schedule` derives the athlete's
    long-session day as the longest enabled window (FormRefresh Slice C);
    shared into plan_refresh T2/T3."""

    @staticmethod
    def _w(dow, enabled, dur=None, second=None, doubles=None):
        return {
            "day_of_week": dow,
            "enabled": enabled,
            "window_start": "06:00" if enabled else None,
            "window_duration": dur,
            "second_window_start": "17:00" if second else None,
            "second_window_duration": second,
            "doubles_feasible": doubles,
        }

    def test_longest_enabled_window_named_long_session_day(self):
        from layer4.per_phase import _format_daily_windows_schedule

        windows = [
            self._w("Mon", True, 90),
            self._w("Wed", True, 120),
            self._w("Sat", True, 480),
            self._w("Sun", False),
        ]
        text = "\n".join(
            _format_daily_windows_schedule(
                {"available_days_per_week": 3, "daily_availability_windows": windows}
            )
        )
        assert "Long-session day = Sat (480 min" in text
        assert "- Sat: available, 480 min  ← longest enabled window" in text
        assert "- Mon: available, 90 min" in text
        assert "- Mon: available, 90 min  ← longest enabled window" not in text
        assert "- Sun: rest (unavailable)" in text

    def test_tie_resolves_to_earliest_listed_day(self):
        from layer4.per_phase import _format_daily_windows_schedule

        windows = [self._w("Tue", True, 240), self._w("Thu", True, 240)]
        text = "\n".join(
            _format_daily_windows_schedule({"daily_availability_windows": windows})
        )
        assert "Long-session day = Tue" in text
        assert "- Tue: available, 240 min  ← longest enabled window" in text
        assert "- Thu: available, 240 min  ← longest enabled window" not in text

    def test_all_disabled_no_long_session_day(self):
        from layer4.per_phase import _format_daily_windows_schedule

        windows = [self._w("Mon", False), self._w("Tue", False)]
        text = "\n".join(
            _format_daily_windows_schedule({"daily_availability_windows": windows})
        )
        assert "Long-session day" not in text
        assert "No enabled windows" in text

    def test_missing_windows_renders_gracefully(self):
        from layer4.per_phase import _format_daily_windows_schedule

        text = "\n".join(
            _format_daily_windows_schedule({"available_days_per_week": 0})
        )
        assert "=== Schedule ===" in text
        assert "No per-day availability windows on file." in text

    def test_second_window_and_doubles_surface(self):
        from layer4.per_phase import _format_daily_windows_schedule

        windows = [self._w("Mon", True, 120, second=60, doubles="occasionally")]
        text = "\n".join(
            _format_daily_windows_schedule({"daily_availability_windows": windows})
        )
        assert "- Mon: available, 120 min (+ 60 min second window)" in text
        assert "Doubles feasible: occasionally" in text


# ─── seam_review module direct tests ─────────────────────────────────────────


class TestSeamReviewInvalidCombinations:
    def test_patched_with_accept_with_observation_raises(self):
        from layer4.payload import PhaseSpec, SynthesisMetadata
        from layer4.seam_review import review_seam

        def bad_caller(*_a, **_kw):
            return _SeamOut(
                tool_args={
                    "reviewer_verdict": "patched",
                    "seam_issues": ["x"],
                    "proposed_patch_direction": "accept_with_observation",
                },
                input_tokens=2000,
                output_tokens=100,
                latency_ms=2500,
            )

        prior = PhaseSpec(
            phase_name="Base",
            start_date=_PLAN_START,
            end_date=_PLAN_START + timedelta(days=27),
            weeks=4,
            intended_volume_band=(5.0, 8.0),
            intended_intensity_distribution={"Z1-Z2": 0.8, "Z3": 0.15, "Z4-Z5": 0.05},
            synthesis_metadata=SynthesisMetadata(
                model="x",
                temperature=0.2,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                retries_used=0,
                cap_hit=False,
            ),
        )
        nxt = PhaseSpec(
            phase_name="Build",
            start_date=_PLAN_START + timedelta(days=28),
            end_date=_PLAN_START + timedelta(days=55),
            weeks=4,
            intended_volume_band=(6.0, 10.0),
            intended_intensity_distribution={"Z1-Z2": 0.7, "Z3": 0.2, "Z4-Z5": 0.1},
            synthesis_metadata=SynthesisMetadata(
                model="x",
                temperature=0.2,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                retries_used=0,
                cap_hit=False,
            ),
        )
        with pytest.raises(Exception) as exc:
            review_seam(
                seam_index=0,
                prior_phase_spec=prior,
                next_phase_spec=nxt,
                prior_phase_sessions=[],
                next_phase_sessions=[],
                layer2a_payload=_layer2a(),
                layer2d_payload=_layer2d(),
                discipline_mix=["D-run"],
                mode="standard",
                start_phase="Base",
                race_format="open_ended",
                event_date=None,
                seam_iteration=1,
                prior_seam_issues=[],
                caller=bad_caller,
            )
        assert "seam_reviewer_invalid_verdict_combination" in str(exc.value)


# ─── Step 6a: per-phase cache wiring (§9.2 chain) ────────────────────────────


class _CountingPhaseStub:
    """Stub that counts how many times it was invoked. Returns the same
    output each time (one cardio session in the first week of the phase)."""

    def __init__(self, output: dict[str, Any]):
        self.output = output
        self.calls = 0

    def __call__(self, *_a, **_kw) -> _PhaseOut:
        self.calls += 1
        return _PhaseOut(
            tool_args=self.output, input_tokens=6000, output_tokens=2000, latency_ms=8000
        )


class TestPerPhaseCacheWiring:
    """Step 6a — `_run_pattern_a_engine` consumes `cache` + `call_cache_key`
    kwargs and chains per-phase keys via `prev_accepted_output_hash`."""

    def test_cache_none_retains_today_behavior(self):
        """No `cache` arg → synthesizer called once per week-block (D-77).
        Default 12-week open-ended standard mode yields 3 phases
        (Base/Build/Peak; Taper rounds to 0 weeks under proportions
        50/30/15/5 at this size), decomposed into one block per week."""
        stub = _CountingPhaseStub(_empty_phase_output())
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        assert result.phase_structure is not None
        assert stub.calls == _total_blocks(result.phase_structure)

    def test_cache_miss_then_store_per_phase(self):
        """First call with cache: B synthesizer calls + B per-block cache rows
        (B = total week-blocks, D-77) + (n_phases - 1) iter-1 seam rows."""
        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-abc",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        assert result.phase_structure is not None
        n_phases = len(result.phase_structure.phases)
        n_seams = n_phases - 1  # all phases synthesized → every seam reviewed
        total_blocks = _total_blocks(result.phase_structure)
        assert stub.calls == total_blocks
        # phase_* counters cover both per-block + iter-1 seam sub-call rows.
        assert cache.metrics.phase_misses_total == total_blocks + n_seams
        assert cache.metrics.phase_hits_total == 0
        assert len(cache.backend) == total_blocks + n_seams

    def test_cache_hit_skips_synthesizer(self):
        """Second call with same call_cache_key: 0 new synthesizer calls;
        all phases hit."""
        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())

        first = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-abc",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        assert first.phase_structure is not None
        n_phases = len(first.phase_structure.phases)
        total_blocks = _total_blocks(first.phase_structure)
        first_call_count = stub.calls

        second = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-abc",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        n_seams = n_phases - 1
        assert stub.calls == first_call_count
        assert cache.metrics.phase_hits_total == total_blocks + n_seams
        assert cache.metrics.phase_misses_total == total_blocks + n_seams
        assert isinstance(second, Layer4Payload)
        assert second.pattern == "A"

    def test_cache_hit_preserves_synthesis_metadata(self):
        """On per-phase cache hit, the SynthesisMetadata in PhaseStructure
        keeps the original token counts from the cached pass (not zeros from
        the hydrated PhaseSynthesisResult)."""
        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())

        first = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-abc",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        # Capture token counts from first call.
        assert first.phase_structure is not None
        first_phase_tokens = first.phase_structure.phases[0].synthesis_metadata.input_tokens
        assert first_phase_tokens > 0  # synthesizer reported 6000

        # Second call: cache hit; synthesis_metadata should match.
        second = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-abc",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        assert second.phase_structure is not None
        second_phase_tokens = second.phase_structure.phases[
            0
        ].synthesis_metadata.input_tokens
        assert second_phase_tokens == first_phase_tokens

    def test_different_call_cache_key_misses(self):
        """Different `call_cache_key` → fresh chain → all misses."""
        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())
        first = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-A",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        n_phases = len(first.phase_structure.phases)  # type: ignore[union-attr]
        total_blocks = _total_blocks(first.phase_structure)  # type: ignore[arg-type]
        llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-B",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        n_seams = n_phases - 1
        assert stub.calls == 2 * total_blocks
        assert cache.metrics.phase_hits_total == 0
        # Two distinct call_cache_keys → both block + seam chains miss twice.
        assert cache.metrics.phase_misses_total == 2 * (total_blocks + n_seams)

    def test_cache_returns_byte_stable_output_across_callers(self):
        """§9.2 cache key for phase 0 is `sha256(call_cache_key||'Base'||'0'||'')`
        — deterministic against the call key. A second invocation with the
        same call_cache_key but a DIFFERENT stub hits cache for phase 0 and
        returns the original synthesized output, regardless of what the new
        stub would have produced. Downstream phases also hit because the
        chain hash is recomputed from the CACHED phase output."""
        cache = Layer4Cache(InMemoryCacheBackend())
        stub_a = _CountingPhaseStub(_empty_phase_output())
        first = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-xyz",
            phase_caller=stub_a,
            seam_caller=_seam_stub_approved(),
        )
        n_phases = len(first.phase_structure.phases)  # type: ignore[union-attr]
        total_blocks = _total_blocks(first.phase_structure)  # type: ignore[arg-type]
        assert stub_a.calls == total_blocks

        stub_b = _CountingPhaseStub(
            _phase_output_with_sessions(phase_start=_PLAN_START, phase_weeks=1)
        )
        llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-xyz",
            phase_caller=stub_b,
            seam_caller=_seam_stub_approved(),
        )
        assert stub_b.calls == 0  # all blocks hit cache; stub_b never invoked
        assert cache.metrics.phase_hits_total == total_blocks + (n_phases - 1)

    def test_per_entry_point_label_routed_to_cache(self):
        """plan_create routes phase rows to 'plan_create' entry_point label;
        plan_refresh T3 cross-phase routes to 'plan_refresh'."""
        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())
        llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-abc",
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        # Inspect the backend's internal dict — all 4 entries should have
        # entry_point='plan_create'.
        backend: Any = cache.backend
        entry_points = {e.entry_point for e in backend._rows.values()}
        assert entry_points == {"plan_create"}


class TestPerWeekDecomposition:
    """D-77 §4 — the Pattern A engine synthesizes one unit per week-block; the
    block boundary is enforced by the window filter so blocks stay disjoint."""

    def test_one_block_row_per_week_with_global_index(self):
        """Each week-block caches under a contiguous global phase_idx (0..B-1,
        below the seam namespace base) with phase_name 'PhaseName:wN'."""
        cache = Layer4Cache(InMemoryCacheBackend())
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-blocks",
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert result.phase_structure is not None
        total_blocks = _total_blocks(result.phase_structure)
        backend: Any = cache.backend
        block_rows = [
            (idx, e)
            for (_k, idx), e in backend._rows.items()
            if idx < _SEAM_CACHE_PHASE_IDX_BASE
        ]
        # Contiguous global block index 0..B-1, one row per week-block.
        assert sorted(idx for idx, _ in block_rows) == list(range(total_blocks))
        # Each block row's phase_name carries the week tag.
        assert all(":w" in e.phase_name for _, e in block_rows)

    def test_blocks_filtered_to_window_no_cross_block_duplication(self):
        """A synthesizer that emits the whole plan's sessions on every block
        call has each block trimmed to its own week, so the composed plan has
        no duplicate (date, session_index_in_day) and exactly one week's worth
        of sessions per synthesized week (proving the block-window filter)."""
        wide = {
            "sessions": [
                _cardio_session(d=_PLAN_START + timedelta(days=w * 7 + off))
                for w in range(20)
                for off in (0, 2, 4)
            ],
            "phase_synthesis_notes": "wide",
            "opportunities": [],
        }
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(wide),
            seam_caller=_seam_stub_approved(),
        )
        assert result.phase_structure is not None
        total_weeks = sum(p.weeks for p in result.phase_structure.phases)
        keys = [(s.date, s.session_index_in_day) for s in result.sessions]
        assert len(keys) == len(set(keys))  # no cross-block duplication
        # 3 sessions/week × synthesized weeks (each block kept only its week).
        assert len(result.sessions) == 3 * total_weeks

    def test_render_block_mode_first_week_no_prior(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
            week_range=(1, 1),
        )
        assert "THIS CALL synthesizes ONLY week 1" in text
        assert "First week of plan; no prior context." in text

    def test_render_block_mode_mid_phase_continuity(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[_plan_session_on(_PLAN_START)],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
            week_range=(2, 2),
        )
        assert "Prior-week continuity" in text
        assert "Progress GENTLY" in text
        assert "THIS CALL synthesizes ONLY week 2" in text

    def test_render_block_mode_phase_transition(self):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        # First block (week 1) of a NON-first phase = a deliberate phase step.
        text = render_user_prompt(
            phase_spec=ps.phases[1],
            phase_structure=ps,
            phase_index_in_plan=1,
            is_first_phase_in_plan=False,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=None,
            prior_block_sessions=[_plan_session_on(_PLAN_START)],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
            week_range=(1, 1),
        )
        assert "DELIBERATE phase transition" in text


class TestIter1SeamReviewCache:
    """§9.2 iter-1 seam-review cache — each iteration-1 review caches under the
    same entry_point as the per-phase rows (disjoint phase_idx namespace), so a
    resumed pass replays the seam LLM calls from cache instead of re-running the
    whole uncached seam tail (the §9.2 Step-6 gap)."""

    def test_cold_run_stores_one_row_per_seam(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        phase_stub = _CountingPhaseStub(_empty_phase_output())
        seam_stub = _CountingSeamStub()
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-seam",
            phase_caller=phase_stub,
            seam_caller=seam_stub,
        )
        assert result.phase_structure is not None
        n_phases = len(result.phase_structure.phases)
        n_seams = n_phases - 1
        total_blocks = _total_blocks(result.phase_structure)
        assert n_seams >= 1
        # Seam reviewer fired once per seam; backend holds block + seam rows.
        assert seam_stub.calls == n_seams
        assert len(cache.backend) == total_blocks + n_seams
        # Seam rows route to the same entry_point (no new CHECK label → no
        # migration); they sit in a disjoint phase_idx namespace.
        backend: Any = cache.backend
        seam_rows = [
            e for (_k, idx), e in backend._rows.items()
            if idx >= _SEAM_CACHE_PHASE_IDX_BASE
        ]
        assert len(seam_rows) == n_seams
        assert {e.entry_point for e in seam_rows} == {"plan_create"}

    def test_resume_replays_seams_from_cache(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        first_seam = _CountingSeamStub()
        first = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-seam",
            phase_caller=_CountingPhaseStub(_empty_phase_output()),
            seam_caller=first_seam,
        )
        assert first.phase_structure is not None
        n_phases = len(first.phase_structure.phases)
        n_seams = n_phases - 1
        total_blocks = _total_blocks(first.phase_structure)
        assert first_seam.calls == n_seams

        second_seam = _CountingSeamStub()
        second = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-seam",
            phase_caller=_CountingPhaseStub(_empty_phase_output()),
            seam_caller=second_seam,
        )
        # The resumed pass made NO new seam LLM calls — all replayed from cache.
        assert second_seam.calls == 0
        assert cache.metrics.phase_hits_total == total_blocks + n_seams
        assert isinstance(second, Layer4Payload)

    def test_no_cache_args_still_runs_seam_reviews_uncached(self):
        seam_stub = _CountingSeamStub()
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_CountingPhaseStub(_empty_phase_output()),
            seam_caller=seam_stub,
        )
        assert result.phase_structure is not None
        assert seam_stub.calls == len(result.phase_structure.phases) - 1


# ─── Step 6b: ThreadPoolExecutor concurrency for iter-1 seam reviews ─────────


class _RecordingExecutor:
    """Drop-in for ThreadPoolExecutor.map that runs sequentially in-caller
    thread but counts tasks submitted and tracks order. Tests use this to
    verify the executor path is exercised."""

    def __init__(self):
        self.submitted_keys: list[Any] = []

    def map(self, fn, iterable):
        items = list(iterable)
        self.submitted_keys.extend(items)
        return [fn(item) for item in items]


class TestSeamReviewConcurrency:
    """Step 6b — iter-1 seam reviews fire in parallel via ThreadPoolExecutor
    (or a caller-injected Executor). Iter-2 stays sequential per §6.2."""

    def test_caller_injected_executor_used_for_multi_seam(self):
        """Default 12-week open-ended plan has 3 phases (Base/Build/Peak),
        2 seams → the caller-provided executor receives both iter-1 tasks
        in seam_idx order."""
        exe = _RecordingExecutor()
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            executor=exe,
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        # 2 seams (3 phases - 1).
        assert exe.submitted_keys == [0, 1]

    def test_single_seam_skips_executor_path(self):
        """Single-seam plan (start_phase='Peak', 6wk horizon → 2 phases)
        runs the one iter-1 task directly without the executor."""
        exe = _RecordingExecutor()
        result = llm_layer4_plan_create(
            **{
                **_call_kwargs(),
                "layer3b_payload": _layer3b(
                    start_phase="Peak", time_to_event_weeks=6
                ),
            },
            race_event_payload=_race_event(weeks_out=6),
            executor=exe,
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        # Single seam: caller-injected executor NOT used (executor only
        # kicks in for >=2 seams).
        assert exe.submitted_keys == []

    def test_seam_reviews_returned_in_seam_idx_order(self):
        """Even with parallel iter-1, SeamReview rows are sorted by
        seam_index in the final Layer4Payload."""

        def _seam_caller(*_a, **_kw) -> _SeamOut:
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

        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_caller,
        )
        assert result.seam_reviews is not None
        # Default 3-phase plan → 2 seams in index order.
        assert [sr.seam_index for sr in result.seam_reviews] == [0, 1]

    def test_default_executor_used_when_none_supplied(self):
        """`executor=None` → internal ThreadPoolExecutor handles iter-1.
        Verify the call completes (no missing-arg / thread-leak errors)."""
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        assert result.seam_reviews is not None
        # 3 phases → 2 seams.
        assert len(result.seam_reviews) == 2

    def test_iter1_parallel_iter2_sequential_with_resynth(self):
        """Iter-1 fires in parallel; iter-2 (post-resynth) is sequential.
        Inject a sequential RecordingExecutor so stub call-order is
        deterministic: call 1 = seam 0 iter-1 (flagged_major), call 2 =
        seam 1 iter-1 (approved), call 3 = seam 0 iter-2 (approved after
        re-synth)."""
        state = {"count": 0}

        def _seam_caller(*_a, **_kw) -> _SeamOut:
            state["count"] += 1
            if state["count"] == 1:
                return _SeamOut(
                    tool_args={
                        "reviewer_verdict": "flagged_major",
                        "seam_issues": ["Build entry mismatched"],
                        "proposed_patch_direction": "re_prompt_next",
                    },
                    input_tokens=2000,
                    output_tokens=100,
                    latency_ms=2500,
                )
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

        result = llm_layer4_plan_create(
            **_call_kwargs(),
            executor=_RecordingExecutor(),  # sequential => deterministic order
            phase_caller=_phase_stub(_empty_phase_output()),
            seam_caller=_seam_caller,
        )
        assert isinstance(result, Layer4Payload)
        # 2 iter-1 calls (parallel) + 1 iter-2 (only seam 0 flagged) = 3.
        assert state["count"] == 3
        assert result.seam_reviews is not None
        assert result.seam_reviews[0].triggered_resynthesis is True
        # Seam 1 iter-1 was approved → no re-synth on it.
        assert result.seam_reviews[1].triggered_resynthesis is False


# ─── Step 6a + 6b combined: cached_wrapper threads cache + executor ──────────


class TestCachedWrapperThreadsCacheAndExecutor:
    """The cached entry-point wrapper (plan_create) should thread `cache` +
    `executor` down to `_run_pattern_a_engine`."""

    def test_wrapper_engages_per_phase_cache(self):
        from layer4 import llm_layer4_plan_create_cached

        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())
        kwargs = _call_kwargs()
        result = llm_layer4_plan_create_cached(
            user_id=kwargs["user_id"],
            layer1_payload=kwargs["layer1_payload"],
            layer2a_payload=kwargs["layer2a_payload"],
            layer2b_payload=kwargs["layer2b_payload"],
            layer2c_payloads=kwargs["layer2c_payloads"],
            layer2d_payload=kwargs["layer2d_payload"],
            layer2e_payload=kwargs["layer2e_payload"],
            layer3a_payload=kwargs["layer3a_payload"],
            layer3b_payload=kwargs["layer3b_payload"],
            plan_start_date=kwargs["plan_start_date"],
            plan_version_id=kwargs["plan_version_id"],
            etl_version_set=kwargs["etl_version_set"],
            cache=cache,
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        assert result.phase_structure is not None
        n_phases = len(result.phase_structure.phases)
        n_seams = n_phases - 1
        total_blocks = _total_blocks(result.phase_structure)
        # 1 per-entry miss; the phase_* counter covers per-block + iter-1 seam.
        assert cache.metrics.misses_total == 1
        assert cache.metrics.phase_misses_total == total_blocks + n_seams
        backend: Any = cache.backend
        # per-entry row + B per-block rows + (N-1) iter-1 seam rows
        assert len(backend) == total_blocks + n_seams + 1

    def test_wrapper_full_hit_skips_all_llm_calls(self):
        from layer4 import llm_layer4_plan_create_cached

        cache = Layer4Cache(InMemoryCacheBackend())
        stub = _CountingPhaseStub(_empty_phase_output())
        kwargs = _call_kwargs()
        kwargs_call = dict(
            user_id=kwargs["user_id"],
            layer1_payload=kwargs["layer1_payload"],
            layer2a_payload=kwargs["layer2a_payload"],
            layer2b_payload=kwargs["layer2b_payload"],
            layer2c_payloads=kwargs["layer2c_payloads"],
            layer2d_payload=kwargs["layer2d_payload"],
            layer2e_payload=kwargs["layer2e_payload"],
            layer3a_payload=kwargs["layer3a_payload"],
            layer3b_payload=kwargs["layer3b_payload"],
            plan_start_date=kwargs["plan_start_date"],
            plan_version_id=kwargs["plan_version_id"],
            etl_version_set=kwargs["etl_version_set"],
            cache=cache,
            phase_caller=stub,
            seam_caller=_seam_stub_approved(),
        )
        first = llm_layer4_plan_create_cached(**kwargs_call)
        assert first.phase_structure is not None
        total_blocks = _total_blocks(first.phase_structure)
        first_calls = stub.calls
        assert first_calls == total_blocks

        # Second call: per-entry cache hits → synthesizer never invoked
        # (per-phase caches not even consulted; the top-level get_or_synthesize
        # short-circuits before _run_pattern_a_engine fires).
        llm_layer4_plan_create_cached(**kwargs_call)
        assert stub.calls == first_calls
        assert cache.metrics.hits_total == 1


class TestMissingSessionsRetry:
    """A per-phase tool_use block with no 'sessions' array (observed in
    production under extended-thinking `tool_choice: auto`, where the model can
    emit a thin/partial tool call) is retried within the cap rather than
    hard-failing the whole plan on the first miss."""

    def test_missing_sessions_then_valid_retries_and_succeeds(self):
        # Pass 0: tool args with no 'sessions' key. Pass 1 (retry): valid.
        seq = _phase_seq_stub(
            [
                {"phase_synthesis_notes": "thinking out loud", "opportunities": []},
                _empty_phase_output(),
            ]
        )
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=seq,
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)
        assert result.phase_structure is not None

    def test_null_sessions_treated_as_missing_and_retried(self):
        seq = _phase_seq_stub(
            [
                {"sessions": None, "phase_synthesis_notes": "x", "opportunities": []},
                _empty_phase_output(),
            ]
        )
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=seq,
            seam_caller=_seam_stub_approved(),
        )
        assert isinstance(result, Layer4Payload)

    def test_missing_sessions_all_passes_raises_schema_violation(self):
        # Every pass omits 'sessions' → terminal Layer4OutputError after the
        # cap, NOT a first-miss hard fail.
        always_missing = _phase_stub(
            {"phase_synthesis_notes": "never emits sessions", "opportunities": []}
        )
        with pytest.raises(Layer4OutputError) as exc:
            llm_layer4_plan_create(
                **_call_kwargs(),
                phase_caller=always_missing,
                seam_caller=_seam_stub_approved(),
            )
        assert exc.value.code == "schema_violation"
        assert "sessions" in (exc.value.detail or "")


class TestSessionsOverEmitClamp:
    """The bounded `sessions` array is clamped to the schema ceiling
    pre-validation — the `maxItems` hint is not API-enforced."""

    def test_clamp_trims_over_emit(self):
        from layer4.per_phase import (
            _MAX_SESSIONS_PER_PHASE,
            _clamp_sessions_over_emit,
        )

        over = [{"i": i} for i in range(_MAX_SESSIONS_PER_PHASE + 17)]
        out = _clamp_sessions_over_emit(over, "Build")
        assert len(out) == _MAX_SESSIONS_PER_PHASE

    def test_clamp_passthrough_at_or_under_ceiling(self):
        from layer4.per_phase import (
            _MAX_SESSIONS_PER_PHASE,
            _clamp_sessions_over_emit,
        )

        under = [{"i": i} for i in range(5)]
        assert _clamp_sessions_over_emit(under, "Build") == under
        at_cap = [{"i": i} for i in range(_MAX_SESSIONS_PER_PHASE)]
        out = _clamp_sessions_over_emit(at_cap, "Build")
        assert len(out) == _MAX_SESSIONS_PER_PHASE

