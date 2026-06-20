"""Tests for `layer4/single_session.py` — Step 4a integration: D-63
`llm_layer4_single_session_synthesize` per `Layer4_Spec.md` §3.3.

Coverage:
- `SingleSessionRequest` validation (locale XOR quick_equipment, enums, bounds)
- Tool schema shape
- §4.4 input validation preconditions
- Prompt rendering (locale branch / quick_equipment branch / retry context)
- Entry-point happy path × locale × quick_equipment × cardio + strength
- Capped retry semantics (validator fail then pass; cap-hit best-effort)
- `intensity_modulated` Observation emission
- Layer4Payload composition invariants (mode, pattern, ad_hoc, suggestion_id)

LLM calls are mocked via a stub `llm_caller` dependency. No real Anthropic
SDK invocations.
"""

from __future__ import annotations

from datetime import date, datetime
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
    Layer2CPayload,
    Layer2DPayload,
    Layer3APayload,
    Layer4InputError,
    Layer4OutputError,
    Layer4Payload,
    Observation,
    RecentTrajectory,
    ResolvedExercise,
    SingleSessionRequest,
    TrajectoryWindow,
    build_record_single_session_tool,
    llm_layer4_single_session_synthesize,
)
from layer4.single_session import _SynthesizerOutput


_DATE = date(2026, 6, 1)  # a Monday


# ─── Fixtures ────────────────────────────────────────────────────────────────


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
                level="moderate", confidence="medium", reasoning_text="r", evidence_basis=["e"]
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


def _layer2c(
    locale_id: str = "home_gym",
    exercise_ids: tuple[str, ...] = ("E-squat", "E-pushup"),
    discipline_id: str = "D-run",
    tier0_ids: tuple[str, ...] = (),
) -> Layer2CPayload:
    def _resolved(ex: str, tier: int) -> ResolvedExercise:
        return ResolvedExercise(
            exercise_id=ex,
            exercise_name=ex,
            exercise_type="strength",
            discipline_ids=[discipline_id],
            sport_relevance_notes={discipline_id: "x"},
            priority_per_discipline={discipline_id: "Medium"},
            tier=tier,
            terrain_required=[],
            contraindicated_parts=[],
            contraindicated_conditions=[],
            accommodations=[],
        )

    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"layer0": "v7"},
        effective_pool=list(exercise_ids),
        discipline_coverage=[
            DisciplineCoverage(
                discipline_id=discipline_id,
                discipline_name=discipline_id,
                exercise_db_sport="x",
                total_exercises=len(exercise_ids) + len(tier0_ids),
                tier_1_count=len(exercise_ids),
                tier_2_count=0,
                tier_3_count=0,
                unavailable_count=len(tier0_ids),
                coverage_pct=1.0,
            )
        ],
        exercises_resolved=(
            [_resolved(ex, 1) for ex in exercise_ids]
            + [_resolved(ex, 0) for ex in tier0_ids]
        ),
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


def _layer1() -> dict[str, Any]:
    return {"experience_level": "advanced", "coaching_voice_preferences": None}


# ─── Tool output builders for the LLM stub ────────────────────────────────────


def _cardio_tool_output(
    *,
    duration_min: int = 60,
    intensity_summary: str = "easy",
    coaching_flags: list[str] | None = None,
    locale_id: str | None = "home_gym",
    discipline_id: str | None = "D-run",
    session_date: date = _DATE,
) -> dict[str, Any]:
    """Build a `record_single_session` tool args dict for a cardio session
    that satisfies all payload contracts. The IntensityTarget shape used is
    HRTarget (universal for endurance)."""
    return {
        "session": {
            "date": session_date.isoformat(),
            "day_of_week": session_date.strftime("%a"),
            "session_index_in_day": 0,
            "time_of_day": "morning",
            "kind": "cardio",
            "discipline_id": discipline_id,
            "discipline_name": discipline_id,
            "locale_id": locale_id,
            "locale_name": locale_id,
            "duration_min": duration_min,
            "intensity_summary": intensity_summary,
            "session_notes": "Easy aerobic block; keep effort conversational.",
            "coaching_intent": "Maintain Z2 aerobic stimulus without accumulating fatigue.",
            "coaching_flags": coaching_flags or [],
            "cardio_blocks": [
                {
                    "block_kind": "warmup",
                    "duration_min": 10,
                    "intensity_zone": "Z1",
                    "intensity_target": {"hr_bpm_low": 110, "hr_bpm_high": 125},
                    "instructions": "Easy spin/jog to warmup.",
                },
                {
                    "block_kind": "main_set",
                    "duration_min": duration_min - 20,
                    "intensity_zone": "Z2",
                    "intensity_target": {"hr_bpm_low": 130, "hr_bpm_high": 145},
                    "instructions": "Steady aerobic effort, conversational pace.",
                },
                {
                    "block_kind": "cooldown",
                    "duration_min": 10,
                    "intensity_zone": "Z1",
                    "intensity_target": {"hr_bpm_low": 110, "hr_bpm_high": 125},
                    "instructions": "Easy cooldown.",
                },
            ],
        }
    }


def _strength_tool_output(
    *,
    duration_min: int = 45,
    locale_id: str | None = "home_gym",
    discipline_id: str | None = "D-run",
    exercise_ids: tuple[str, ...] = ("E-squat", "E-pushup"),
    session_date: date = _DATE,
) -> dict[str, Any]:
    return {
        "session": {
            "date": session_date.isoformat(),
            "day_of_week": session_date.strftime("%a"),
            "session_index_in_day": 0,
            "time_of_day": "afternoon",
            "kind": "strength",
            "discipline_id": discipline_id,
            "discipline_name": discipline_id,
            "locale_id": locale_id,
            "locale_name": locale_id,
            "duration_min": duration_min,
            "intensity_summary": "moderate",
            "session_notes": "Lower-body + push focus.",
            "coaching_intent": "Maintain strength baseline.",
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
                    "instructions": "Maintain neutral spine; full ROM.",
                    "coaching_flags": [],
                }
                for ex in exercise_ids
            ],
        }
    }


def _stub_caller(tool_args: dict[str, Any]):
    """Return a callable matching the LLMCaller protocol that always returns
    `tool_args`."""

    def _call(*_args, **_kwargs) -> _SynthesizerOutput:
        return _SynthesizerOutput(
            tool_args=tool_args, input_tokens=3000, output_tokens=800, latency_ms=4200
        )

    return _call


def _sequence_caller(outputs: list[dict[str, Any]]):
    """Return a callable that yields `outputs[i]` on the i'th call (for
    testing retry semantics)."""
    state = {"i": 0}

    def _call(*_args, **_kwargs) -> _SynthesizerOutput:
        i = state["i"]
        state["i"] = i + 1
        return _SynthesizerOutput(
            tool_args=outputs[i], input_tokens=3000, output_tokens=800, latency_ms=4200
        )

    return _call


# ─── SingleSessionRequest validation ─────────────────────────────────────────


class TestSingleSessionRequest:
    def test_happy_locale(self):
        r = SingleSessionRequest(
            sport="running",
            duration_min=60,
            intensity="easy",
            locale_slug="home_gym",
        )
        assert r.locale_slug == "home_gym"
        assert r.quick_equipment == []

    def test_happy_quick_equipment(self):
        r = SingleSessionRequest(
            sport="strength",
            duration_min=45,
            intensity="moderate",
            quick_equipment=["dumbbells", "bench"],
        )
        assert r.locale_slug is None
        assert r.quick_equipment == ["dumbbells", "bench"]

    def test_both_locale_and_quick_rejected(self):
        with pytest.raises(ValueError, match="both provided"):
            SingleSessionRequest(
                sport="running",
                duration_min=60,
                intensity="easy",
                locale_slug="home_gym",
                quick_equipment=["dumbbells"],
            )

    def test_neither_locale_nor_quick_rejected(self):
        with pytest.raises(ValueError, match="neither provided"):
            SingleSessionRequest(sport="running", duration_min=60, intensity="easy")

    def test_duration_below_minimum_rejected(self):
        with pytest.raises(ValueError):
            SingleSessionRequest(
                sport="running", duration_min=20, intensity="easy", locale_slug="x"
            )

    def test_duration_above_maximum_rejected(self):
        with pytest.raises(ValueError):
            SingleSessionRequest(
                sport="running", duration_min=400, intensity="easy", locale_slug="x"
            )

    def test_invalid_intensity_rejected(self):
        with pytest.raises(ValueError):
            SingleSessionRequest(
                sport="running",
                duration_min=60,
                intensity="brutal",  # type: ignore[arg-type]
                locale_slug="x",
            )

    def test_race_pace_intensity_accepted(self):
        r = SingleSessionRequest(
            sport="running",
            duration_min=60,
            intensity="race_pace",
            locale_slug="x",
        )
        assert r.intensity == "race_pace"

    def test_extra_field_rejected(self):
        with pytest.raises(ValueError):
            SingleSessionRequest(
                sport="running",
                duration_min=60,
                intensity="easy",
                locale_slug="x",
                bogus_field=True,  # type: ignore[call-arg]
            )


# ─── Tool schema basics ──────────────────────────────────────────────────────


class TestToolSchema:
    def test_tool_name_and_top_level_shape(self):
        tool = build_record_single_session_tool()
        assert tool["name"] == "record_single_session"
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"]["additionalProperties"] is False
        assert tool["input_schema"]["required"] == ["session"]

    def test_session_required_fields_cover_payload_invariants(self):
        tool = build_record_single_session_tool()
        required = tool["input_schema"]["properties"]["session"]["required"]
        for field in (
            "date",
            "day_of_week",
            "session_index_in_day",
            "kind",
            "duration_min",
            "intensity_summary",
            "session_notes",
            "coaching_intent",
            "coaching_flags",
        ):
            assert field in required, f"{field} missing from required"

    def test_coaching_flags_closed_set(self):
        tool = build_record_single_session_tool()
        cf = tool["input_schema"]["properties"]["session"]["properties"]["coaching_flags"]
        assert cf["items"]["enum"] == [
            "intensity_modulated",
            "technique_emphasis",
            "discipline_specific_intensity",
        ]

    def test_intensity_target_oneof_nine_shapes(self):
        tool = build_record_single_session_tool()
        block_schema = tool["input_schema"]["properties"]["session"]["properties"][
            "cardio_blocks"
        ]["items"]
        oneof = block_schema["properties"]["intensity_target"]["oneOf"]
        assert len(oneof) == 9

    def test_intensity_zone_enum(self):
        tool = build_record_single_session_tool()
        block_schema = tool["input_schema"]["properties"]["session"]["properties"][
            "cardio_blocks"
        ]["items"]
        assert block_schema["properties"]["intensity_zone"]["enum"] == [
            "Z1",
            "Z2",
            "Z3",
            "Z4",
            "Z5",
            "mixed",
        ]


# ─── Input validation (§4.4) ─────────────────────────────────────────────────


class TestInputValidation:
    def _common_kwargs(self) -> dict[str, Any]:
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "suggestion_id": 999,
            "etl_version_set": {"layer0": "v7"},
            "session_date": _DATE,
        }

    def test_missing_layer2d_raises(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        with pytest.raises(Layer4InputError) as exc_info:
            llm_layer4_single_session_synthesize(
                request=req,
                layer2c_payload_for_locale=_layer2c(),
                layer2d_payload=None,  # type: ignore[arg-type]
                layer3a_payload=_layer3a(),
                llm_caller=_stub_caller(_cardio_tool_output()),
                **self._common_kwargs(),
            )
        assert exc_info.value.code == "missing_upstream_payload"
        assert "layer2d_payload" in (exc_info.value.detail or "")

    def test_missing_layer3a_raises(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        with pytest.raises(Layer4InputError) as exc_info:
            llm_layer4_single_session_synthesize(
                request=req,
                layer2c_payload_for_locale=_layer2c(),
                layer2d_payload=_layer2d(),
                layer3a_payload=None,  # type: ignore[arg-type]
                llm_caller=_stub_caller(_cardio_tool_output()),
                **self._common_kwargs(),
            )
        assert exc_info.value.code == "missing_upstream_payload"

    def test_locale_without_2c_raises(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        with pytest.raises(Layer4InputError) as exc_info:
            llm_layer4_single_session_synthesize(
                request=req,
                layer2c_payload_for_locale=None,
                layer2d_payload=_layer2d(),
                layer3a_payload=_layer3a(),
                llm_caller=_stub_caller(_cardio_tool_output()),
                **self._common_kwargs(),
            )
        assert exc_info.value.code == "layer2c_payload_for_locale_missing"

    def test_locale_mismatch_with_2c_raises(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="hotel_gym"
        )
        with pytest.raises(Layer4InputError) as exc_info:
            llm_layer4_single_session_synthesize(
                request=req,
                layer2c_payload_for_locale=_layer2c(locale_id="home_gym"),
                layer2d_payload=_layer2d(),
                layer3a_payload=_layer3a(),
                llm_caller=_stub_caller(_cardio_tool_output()),
                **self._common_kwargs(),
            )
        assert exc_info.value.code == "layer2c_payload_for_locale_missing"
        assert "does not match" in (exc_info.value.detail or "")


# ─── Happy-path entry point ──────────────────────────────────────────────────


class TestEntryPointHappyPath:
    def _common(self) -> dict[str, Any]:
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2d_payload": _layer2d(),
            "layer3a_payload": _layer3a(),
            "suggestion_id": 999,
            "etl_version_set": {"layer0": "v7"},
            "session_date": _DATE,
        }

    def test_cardio_via_locale(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert isinstance(payload, Layer4Payload)
        assert payload.mode == "single_session_synthesize"
        assert payload.pattern == "B"
        assert len(payload.sessions) == 1
        assert payload.sessions[0].is_ad_hoc is True
        assert payload.sessions[0].kind == "cardio"
        assert payload.phase_structure is None
        assert payload.seam_reviews is None
        assert payload.suggestion_id == 999

    def test_strength_via_locale(self):
        req = SingleSessionRequest(
            sport="strength",
            duration_min=45,
            intensity="moderate",
            locale_slug="home_gym",
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_strength_tool_output()),
            **self._common(),
        )
        assert payload.sessions[0].kind == "strength"
        assert payload.sessions[0].strength_exercises is not None
        assert len(payload.sessions[0].strength_exercises) == 2

    def test_cardio_via_quick_equipment(self):
        req = SingleSessionRequest(
            sport="running",
            duration_min=60,
            intensity="easy",
            quick_equipment=["running_shoes"],
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=None,
            llm_caller=_stub_caller(
                _cardio_tool_output(locale_id=None, discipline_id=None)
            ),
            **self._common(),
        )
        assert payload.sessions[0].locale_id is None

    def test_ad_hoc_request_payload_stored(self):
        req = SingleSessionRequest(
            sport="running",
            duration_min=60,
            intensity="easy",
            locale_slug="home_gym",
            notes_for_synthesizer="form drills today",
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        stored = payload.sessions[0].ad_hoc_request_payload
        assert stored is not None
        assert stored["sport"] == "running"
        assert stored["notes_for_synthesizer"] == "form drills today"

    def test_validator_results_populated_and_accepted(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert len(payload.validator_results) >= 1
        assert payload.validator_results[-1].accepted is True

    def test_telemetry_fields_aggregated(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.llm_call_count == 1
        assert payload.input_tokens_total == 3000
        assert payload.output_tokens_total == 800
        assert payload.latency_ms_total == 4200

    def test_scope_dates_equal_session_date(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.scope_start_date == _DATE
        assert payload.scope_end_date == _DATE


# ─── Observation emission (§8.7) ─────────────────────────────────────────────


class TestObservationEmission:
    def _common(self) -> dict[str, Any]:
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2d_payload": _layer2d(),
            "layer3a_payload": _layer3a(),
            "suggestion_id": 999,
            "etl_version_set": {"layer0": "v7"},
            "session_date": _DATE,
        }

    def test_intensity_modulated_flag_emits_observation(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="hard", locale_slug="home_gym"
        )
        out = _cardio_tool_output(
            intensity_summary="moderate", coaching_flags=["intensity_modulated"]
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(out),
            **self._common(),
        )
        cats = [o.category for o in payload.notable_observations]
        assert "intensity_modulated" in cats

    def test_no_flag_no_observation(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        cats = [o.category for o in payload.notable_observations]
        assert "intensity_modulated" not in cats


# ─── Retry semantics (§5.5) ──────────────────────────────────────────────────


class TestCappedRetry:
    def _common(self, layer2d: Layer2DPayload | None = None) -> dict[str, Any]:
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2d_payload": layer2d or _layer2d(),
            "layer3a_payload": _layer3a(),
            "suggestion_id": 999,
            "etl_version_set": {"layer0": "v7"},
            "session_date": _DATE,
        }

    def test_validator_fail_then_pass_retries_once(self):
        # First pass: emits a session with a locale_id NOT in the validator
        # context's cluster → `session_locale_not_in_cluster_*` blocker
        # (Rule 6c, structural per spec §8). Retry: emits the right locale →
        # accepted. Switched from injury_violation in Track 2 slice 2d: Rule 7
        # is now warning-only.
        bad_strength = _strength_tool_output(
            exercise_ids=("E-squat",), locale_id="not_in_cluster",
        )
        good_strength = _strength_tool_output(exercise_ids=("E-squat",))

        req = SingleSessionRequest(
            sport="strength",
            duration_min=45,
            intensity="moderate",
            locale_slug="home_gym",
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(exercise_ids=("E-squat",)),
            llm_caller=_sequence_caller([bad_strength, good_strength]),
            **self._common(),
        )
        assert payload.llm_call_count == 2
        # validator_results: pass 0 (fail), pass 1 (accepted)
        assert len(payload.validator_results) == 2
        assert payload.validator_results[0].accepted is False
        assert payload.validator_results[-1].accepted is True

    def test_cap_hit_emits_best_effort_observation(self):
        # Same blocker swap as above — Rule 6c session_locale_not_in_cluster.
        bad_strength = _strength_tool_output(
            exercise_ids=("E-squat",), locale_id="not_in_cluster",
        )

        req = SingleSessionRequest(
            sport="strength",
            duration_min=45,
            intensity="moderate",
            locale_slug="home_gym",
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(exercise_ids=("E-squat",)),
            llm_caller=_sequence_caller([bad_strength, bad_strength, bad_strength]),
            capped_retries=2,
            **self._common(),
        )
        # 1 initial + 2 retries = 3 LLM calls
        assert payload.llm_call_count == 3
        cats = [o.category for o in payload.notable_observations]
        assert "best_effort_plan" in cats
        # Demoted: last validator_result has only `warning`-severity failures
        last = payload.validator_results[-1]
        assert last.accepted is True
        assert all(f.severity == "warning" for f in last.rule_failures)

    def test_first_pass_accept_skips_retries(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.llm_call_count == 1
        assert len(payload.validator_results) == 1

    def test_capped_retries_zero_no_retry_path(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            capped_retries=0,
            **self._common(),
        )
        assert payload.llm_call_count == 1


# ─── Schema-violation handling ───────────────────────────────────────────────


class TestSchemaViolation:
    def _common(self) -> dict[str, Any]:
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2d_payload": _layer2d(),
            "layer3a_payload": _layer3a(),
            "suggestion_id": 999,
            "etl_version_set": {"layer0": "v7"},
            "session_date": _DATE,
        }

    def test_missing_session_key_raises(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        with pytest.raises(Layer4OutputError) as exc_info:
            llm_layer4_single_session_synthesize(
                request=req,
                layer2c_payload_for_locale=_layer2c(),
                llm_caller=_stub_caller({"not_session": {}}),
                **self._common(),
            )
        assert exc_info.value.code == "schema_violation"

    def test_malformed_session_retries_then_raises(self):
        # First two passes return a session that can't construct a PlanSession;
        # on the cap+1 attempt the schema-violation raises.
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        bad = {"session": {"date": "not-a-date", "kind": "cardio"}}
        with pytest.raises(Layer4OutputError) as exc_info:
            llm_layer4_single_session_synthesize(
                request=req,
                layer2c_payload_for_locale=_layer2c(),
                llm_caller=_sequence_caller([bad, bad, bad]),
                capped_retries=2,
                **self._common(),
            )
        assert exc_info.value.code == "schema_violation"

    def test_malformed_then_valid_recovers(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        bad = {"session": {"date": "not-a-date", "kind": "cardio"}}
        good = _cardio_tool_output()
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_sequence_caller([bad, good]),
            capped_retries=2,
            **self._common(),
        )
        assert payload.sessions[0].kind == "cardio"


# ─── Layer4Payload composition invariants ────────────────────────────────────


class TestLayer4PayloadComposition:
    def _common(self) -> dict[str, Any]:
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2d_payload": _layer2d(),
            "layer3a_payload": _layer3a(),
            "suggestion_id": 999,
            "etl_version_set": {"layer0": "v7"},
            "session_date": _DATE,
        }

    def test_mode_is_single_session_synthesize(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.mode == "single_session_synthesize"

    def test_pattern_is_b(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.pattern == "B"

    def test_phase_structure_and_seam_reviews_none(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.phase_structure is None
        assert payload.seam_reviews is None

    def test_sessions_length_one(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert len(payload.sessions) == 1

    def test_session_is_ad_hoc(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.sessions[0].is_ad_hoc is True

    def test_session_phase_metadata_none(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **self._common(),
        )
        assert payload.sessions[0].phase_metadata is None

    def test_suggestion_id_propagates(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            suggestion_id=12345,
            user_id=42,
            layer1_payload=_layer1(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            etl_version_set={"layer0": "v7"},
            session_date=_DATE,
        )
        assert payload.suggestion_id == 12345

    def test_model_temperature_recorded(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            model="claude-sonnet-4-6",
            temperature=0.3,
            **self._common(),
        )
        assert payload.model_synthesizer == "claude-sonnet-4-6"
        assert payload.temperature == 0.3
        assert payload.model_seam_reviewer is None

    def test_etl_version_set_propagated(self):
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        common = self._common()
        common["etl_version_set"] = {"layer0": "v7", "layer2c": "v3"}
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c(),
            llm_caller=_stub_caller(_cardio_tool_output()),
            **common,
        )
        assert payload.etl_version_set == {"layer0": "v7", "layer2c": "v3"}


# ─── Prompt rendering surface ────────────────────────────────────────────────


class TestPromptRendering:
    def test_retry_context_appears_only_on_retry(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        prompt_first = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        prompt_retry = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=1,
            rule_failures=[],
        )
        assert "Retry context" not in prompt_first
        assert "Retry context" in prompt_retry

    def test_locale_branch_renders_effective_pool(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(exercise_ids=("E-foo", "E-bar")),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "Effective pool" in prompt
        assert "E-foo" in prompt
        assert "E-bar" in prompt

    def test_coaching_memory_renders_when_present_339(self):
        # #339 — the durable Coaching-memory block now renders on the
        # single-session path too (#690 rendered it on plan-create only), so
        # non-variety prefs (e.g. avoid-exercise notes) reach the ad-hoc session.
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        l1 = dict(_layer1())
        l1["coaching_preferences"] = [
            {"category": "avoid_exercise", "content": "No overhead pressing.",
             "permanent": False},
        ]
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=l1,
            layer2c_payload_for_locale=_layer2c(exercise_ids=("E-foo",)),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "Coaching memory" in prompt
        assert "No overhead pressing." in prompt

    def test_resolved_exercises_render_excludes_tier0(self):
        # #691 — a tier-0 (equipment-infeasible, no substitute/proxy) exercise
        # must NOT appear in the "Resolved exercises" prompt menu, where it would
        # otherwise render as a plain bullet (no tier note) the model could pick.
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(
                exercise_ids=("E-feasible",), tier0_ids=("E-nosled",)
            ),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "E-feasible" in prompt
        assert "E-nosled" not in prompt

    def test_quick_equipment_branch_renders_list(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="strength",
            duration_min=45,
            intensity="moderate",
            quick_equipment=["dumbbells", "bench", "kettlebell"],
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=None,
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "Somewhere else" in prompt
        assert "dumbbells" in prompt
        assert "bench" in prompt
        assert "kettlebell" in prompt

    def test_excluded_exercise_appears_in_injury_section(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(excluded=("E-bench",)),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "EXCLUDE E-bench" in prompt

    def test_no_injuries_renders_clean_marker(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "None on file" in prompt

    def test_athlete_note_renders_when_present(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running",
            duration_min=60,
            intensity="easy",
            locale_slug="home_gym",
            notes_for_synthesizer="focus on form",
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "focus on form" in prompt


# ─── #698 Track 2 (Slice C1) — on-demand cardio drills ───────────────────────


def _layer2c_with_drill(
    locale_id: str = "home_gym",
    drill_id: str = "EX292",
    drill_type: str = "Interval / Tempo",
    discipline_id: str = "D-bike",
    coaching_cue: str | None = "6×3min Z4 / 3min Z2",
) -> Layer2CPayload:
    """A locale 2C carrying one cardio-drill-type resolved exercise so the
    Slice-C1 pool resolves non-empty."""
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
                exercise_name="Bike Over-Under Intervals",
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


class TestCardioDrillsSliceC1:
    def test_schema_has_capped_cardio_drills_block(self):
        tool = build_record_single_session_tool()
        drills = tool["input_schema"]["properties"]["session"]["properties"][
            "cardio_drills"
        ]
        assert drills["type"] == ["array", "null"]
        assert drills["maxItems"] == 1
        assert drills["items"]["required"] == [
            "exercise_id",
            "exercise_name",
            "prescription",
        ]

    def test_exercise_id_enum_bound_when_pool_nonempty(self):
        tool = build_record_single_session_tool(cardio_drill_pool_ids=["EX292", "EX073"])
        prop = tool["input_schema"]["properties"]["session"]["properties"][
            "cardio_drills"
        ]["items"]["properties"]["exercise_id"]
        assert prop == {"type": "string", "enum": ["EX292", "EX073"]}

    def test_exercise_id_free_string_when_pool_empty(self):
        tool = build_record_single_session_tool(cardio_drill_pool_ids=None)
        prop = tool["input_schema"]["properties"]["session"]["properties"][
            "cardio_drills"
        ]["items"]["properties"]["exercise_id"]
        assert prop == {"type": "string"}

    def test_system_prompt_has_cardio_drills_section(self):
        from layer4.single_session import _SYSTEM_PROMPT

        assert "# Cardio drills" in _SYSTEM_PROMPT
        assert "At most one drill" in _SYSTEM_PROMPT

    def test_user_prompt_renders_pool_when_lines_present(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="cycling", duration_min=60, intensity="hard", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c_with_drill(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
            cardio_drill_pool_lines=["- D-bike:", "  - EX292 (Bike Over-Under Intervals)"],
        )
        assert "=== Cardio drill pool (consider these) ===" in prompt
        assert "EX292" in prompt

    def test_user_prompt_suppresses_pool_when_no_lines(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="cycling", duration_min=60, intensity="hard", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c_with_drill(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
            cardio_drill_pool_lines=[],
        )
        assert "Cardio drill pool" not in prompt

    def test_build_plan_session_parses_cardio_drills(self):
        from layer4.single_session import _build_plan_session

        out = _cardio_tool_output(discipline_id="D-bike")
        out["session"]["cardio_drills"] = [
            {
                "exercise_id": "EX292",
                "exercise_name": "Bike Over-Under Intervals",
                "prescription": "6×3min Z4 / 3min Z2",
                "instructions": "Hold the over just above threshold.",
            }
        ]
        sess = _build_plan_session(
            out["session"],
            session_id="S-test",
            plan_version_id=1,
            request=SingleSessionRequest(
                sport="cycling",
                duration_min=60,
                intensity="hard",
                locale_slug="home_gym",
            ),
        )
        assert sess.cardio_drills is not None
        assert len(sess.cardio_drills) == 1
        assert sess.cardio_drills[0].exercise_id == "EX292"

    def test_end_to_end_drill_lands_and_pool_enum_binds(self):
        from layer4.single_session import build_record_single_session_tool as _t

        req = SingleSessionRequest(
            sport="cycling", duration_min=60, intensity="hard", locale_slug="home_gym"
        )
        out = _cardio_tool_output(discipline_id="D-bike")
        out["session"]["cardio_drills"] = [
            {
                "exercise_id": "EX292",
                "exercise_name": "Bike Over-Under Intervals",
                "prescription": "6×3min Z4 / 3min Z2",
                "instructions": None,
            }
        ]
        payload = llm_layer4_single_session_synthesize(
            request=req,
            layer2c_payload_for_locale=_layer2c_with_drill(),
            llm_caller=_stub_caller(out),
            user_id=42,
            layer1_payload=_layer1(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            suggestion_id=999,
            etl_version_set={"layer0": "v7"},
            session_date=_DATE,
        )
        sess = payload.sessions[0]
        assert sess.cardio_drills is not None
        assert sess.cardio_drills[0].exercise_id == "EX292"
        # the drill-bearing locale resolves a non-empty pool → enum-bound schema
        assert "EX292" in _t(cardio_drill_pool_ids=["EX292"])["input_schema"][
            "properties"
        ]["session"]["properties"]["cardio_drills"]["items"]["properties"][
            "exercise_id"
        ]["enum"]


class TestStructuredCardio337:
    """#337 — structured cardio prescription on the single-session path: the
    shared `# Cardio programming` section is in the system prompt, and the
    measured-physiology block renders into `# Athlete context` only when Layer 1
    carries a physiological anchor (suppress-on-empty)."""

    def test_cardio_programming_section_in_system_prompt(self):
        from layer4.single_session import _SYSTEM_PROMPT

        assert "# Cardio programming" in _SYSTEM_PROMPT

    def test_measured_physiology_surfaced_when_anchors_present(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="hard", locale_slug="home_gym"
        )
        layer1 = {
            "experience_level": "advanced",
            "coaching_voice_preferences": None,
            "performance": {
                "hrmax_bpm": 188,
                "running_threshold_pace_sec_per_km": 245,
            },
        }
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=layer1,
            layer2c_payload_for_locale=_layer2c_with_drill(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "Measured physiology" in prompt
        assert "HR max 188 bpm" in prompt
        assert "run threshold pace 4:05 /km" in prompt

    def test_measured_physiology_suppressed_when_no_anchors(self):
        from layer4.single_session import _render_user_prompt

        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="hard", locale_slug="home_gym"
        )
        prompt = _render_user_prompt(
            request=req,
            layer1_payload=_layer1(),  # no `performance` key
            layer2c_payload_for_locale=_layer2c_with_drill(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            session_date=_DATE,
            retries_used=0,
            rule_failures=[],
        )
        assert "Measured physiology" not in prompt
