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
import threading
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
from layer4.plan_create import (
    _SEAM_CACHE_PHASE_IDX_BASE,
    _SEAM_ITER2_CACHE_PHASE_IDX_BASE,
)
from layer4.per_phase import _SynthesizerOutput as _PhaseOut
from layer4.seam_review import _SeamReviewerOutput as _SeamOut


# ─── Fixtures ────────────────────────────────────────────────────────────────


# Plan start must be today-or-future (the §4.2 `plan_start_date_in_past` guard).
# Anchored to today so the suite never goes stale by the calendar — a hardcoded
# date silently failed every test in this file once it slipped into the past.
# Day-of-week is irrelevant: weeks bucket by `week_in_phase` offset from the
# phase start, not by ISO/calendar week. event_date / race fixtures derive from
# this relatively, so weeks-to-event (and the phase structure) is unchanged.
_PLAN_START = date.today()


def _layer1() -> dict[str, Any]:
    return {
        "experience_level": "advanced",
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


class TestPerBlockBudgetGuard:
    """D-77 §6: a block must RETURN within the function cap (caching a
    best-effort attempt or failing fast) rather than stacking extended-thinking
    retries until the 300s cap 504-kills the loop and nothing caches."""

    def test_budget_guard_terminal_when_no_parseable_attempt(self):
        from layer4 import per_phase
        from layer4.errors import Layer4OutputError
        from layer4.phase_structure import phase_structure_from_3b

        ps = phase_structure_from_3b(_layer3b(), _PLAN_START)
        calls = {"n": 0}

        # The model keeps returning a sessions-less tool call, and a single
        # call already spends the whole per-block budget. The first attempt
        # runs; the guard must then refuse to start a second and raise.
        def _caller(*_a, **_kw):
            calls["n"] += 1
            return _PhaseOut(
                tool_args={"phase_synthesis_notes": "x"},
                input_tokens=6000,
                output_tokens=9000,
                latency_ms=per_phase._PER_BLOCK_BUDGET_MS,
            )

        with pytest.raises(Layer4OutputError) as exc:
            per_phase.synthesize_phase(
                user_id=1,
                phase_spec=ps.phases[0],
                phase_structure=ps,
                phase_index_in_plan=0,
                layer1_payload=_layer1(),
                layer2a_payload=_layer2a(),
                layer2b_payload=_layer2b(),
                layer2c_payloads=_layer2c(),
                layer2d_payload=_layer2d(),
                layer2e_payload=_layer2e(),
                layer3a_payload=_layer3a(),
                layer3b_payload=_layer3b(),
                race_event_payload=_race_event(),
                prior_block_sessions=[],
                plan_version_id=1,
                etl_version_set={"layer0": "v7"},
                mode="plan_create",
                week_range=(1, 1),
                llm_caller=_caller,
            )

        assert exc.value.code == "synthesis_budget_exhausted"
        # Only ONE attempt fired — the guard blocked the 2nd/3rd retries.
        assert calls["n"] == 1


class TestTopLevelPayloadValidationRetryable:
    """#47 (2026-05-31): a top-level `Layer4Payload` @model_validator failure
    raises at `_build_payload_for_validation` construction, OUTSIDE the per-row
    parse try/except. It used to escape as a raw pydantic ValidationError → the
    route catch-all marked the WHOLE plan 'failed unexpectedly' and discarded it
    (prod plan #47: "max 2 sessions per day (got 3)"). It must instead surface as
    a RETRYABLE `Layer4OutputError(schema_violation)` so the block re-synthesizes.

    The original #47 trigger (>2 training sessions on one day) now self-heals
    deterministically via the #351 per-day clamp BEFORE construction — proven by
    `test_three_training_one_day_self_heals_via_clamp` — so the retryable wrap is
    no longer exercised by that input. `test_payload_validation_error_is_retryable_not_fatal`
    keeps the #47/#349 wrap under test for the cross-session invariants that are
    NOT clamped (e.g. >1 recovery/day)."""

    def _run(self, caller):
        from layer4 import per_phase
        from layer4.phase_structure import phase_structure_from_3b

        ps = phase_structure_from_3b(_layer3b(), _PLAN_START)
        return per_phase.synthesize_phase(
            user_id=1,
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            race_event_payload=_race_event(),
            prior_block_sessions=[],
            plan_version_id=1,
            etl_version_set={"layer0": "v7"},
            mode="plan_create",
            week_range=(1, 1),
            llm_caller=caller,
        )

    def test_three_training_one_day_self_heals_via_clamp(self):
        # #351: three cardio sessions all dated to week-1 day 2 — 3 TRAINING
        # sessions on one day, which `_check_two_per_day` rejects (`max 2 training
        # sessions per day`; the exact boundary #47 fell through). The per-day
        # clamp now trims that day to 2 BEFORE payload construction, so the block
        # NO LONGER fumbles on the payload invariant — it proceeds past
        # construction with the day clamped to 2 (zero retries spent on the
        # over-emit). (The thin 2-session block may still draw periodization-
        # validator retries on volume grounds — orthogonal to the clamp — so this
        # asserts the clamp outcome, not the call count.)
        d2 = _PLAN_START + timedelta(days=1)
        out = {
            "sessions": [
                _cardio_session(d=d2, idx=0),
                _cardio_session(d=d2, idx=1),
                _cardio_session(d=d2, idx=1),
            ],
            "phase_synthesis_notes": "over-emitted a 3rd session on day 2",
        }

        def _caller(*_a, **_kw):
            return _PhaseOut(
                tool_args=out, input_tokens=6000, output_tokens=2000, latency_ms=8000
            )

        # Does NOT raise the schema_violation payload fumble — returns a result.
        result = self._run(_caller)

        day2 = [s for s in result.sessions if s.date == d2]
        assert len(day2) == 2  # clamped from 3 to 2
        assert sum(1 for s in day2 if s.kind == "cardio") >= 1  # a cardio kept
        assert sorted(s.session_index_in_day for s in day2) == [0, 1]

    def test_payload_validation_error_is_retryable_not_fatal(self):
        # #47/#349 contract: ANY top-level Layer4Payload ValidationError at
        # construction must surface as a RETRYABLE `schema_violation` (not a raw
        # pydantic error the route discards the whole plan over). Monkeypatch
        # construction to raise — standing in for the cross-session invariants
        # that AREN'T deterministically clamped (e.g. >1 recovery/day) — and
        # confirm it retries across the full cap, then raises the typed code.
        import pydantic

        from layer4 import per_phase
        from layer4.errors import Layer4OutputError

        calls = {"n": 0}

        def _caller(*_a, **_kw):
            calls["n"] += 1
            return _PhaseOut(
                tool_args={
                    "sessions": [_cardio_session(d=_PLAN_START + timedelta(days=1), idx=0)],
                    "phase_synthesis_notes": "ok",
                },
                input_tokens=6000,
                output_tokens=2000,
                latency_ms=8000,
            )

        def _raise_validation(*_a, **_kw):
            raise pydantic.ValidationError.from_exception_data("Layer4Payload", [])

        orig = per_phase._build_payload_for_validation
        per_phase._build_payload_for_validation = _raise_validation
        try:
            with pytest.raises(Layer4OutputError) as exc:
                self._run(_caller)
        finally:
            per_phase._build_payload_for_validation = orig

        # Surfaced as the RETRYABLE typed code, retried across the full cap
        # (capped_retries=2 → 3 attempts) rather than failing fatally on attempt 1.
        assert exc.value.code == "schema_violation"
        assert calls["n"] == 3

    def test_budget_break_with_no_validator_is_retryable(self):
        # prod plan #52 (2026-05-31), sibling of #47. When EVERY completed pass
        # raises a top-level Layer4Payload ValidationError, its handler assigns
        # `latest_sessions` at parse time but `continue`s WITHOUT running the
        # validator, so `latest_validator` stays None. The per-block budget guard
        # then trips on the next pass and takes the best-effort-accept `break`
        # (latest_sessions is set). The post-loop check USED to be a bare
        # `assert latest_validator is not None`, raising a raw AssertionError that
        # escaped the typed-error contract → the route discarded the whole plan.
        # It must now raise a RETRYABLE coded error instead.
        import pydantic

        from layer4 import per_phase
        from layer4.errors import Layer4OutputError

        # Each call returns parseable sessions (sets latest_sessions) and spends
        # the entire per-block budget, so pass 2's guard trips immediately.
        def _caller(*_a, **_kw):
            return _PhaseOut(
                tool_args={
                    "sessions": [_cardio_session(d=_PLAN_START + timedelta(days=1), idx=0)],
                    "phase_synthesis_notes": "n",
                },
                input_tokens=6000,
                output_tokens=2000,
                latency_ms=per_phase._PER_BLOCK_BUDGET_MS,
            )

        def _raise_validation(*_a, **_kw):
            raise pydantic.ValidationError.from_exception_data("Layer4Payload", [])

        orig = per_phase._build_payload_for_validation
        per_phase._build_payload_for_validation = _raise_validation
        try:
            with pytest.raises(Layer4OutputError) as exc:
                self._run(_caller)
            # synthesis_budget_exhausted ∈ the route's _RETRYABLE_BLOCK_CODES, so
            # the block re-synthesizes next pass instead of killing the plan.
            assert exc.value.code == "synthesis_budget_exhausted"
        finally:
            per_phase._build_payload_for_validation = orig


class TestBlockOutputBudget:
    """D-77 §6 follow-on: block-mode `max_tokens` scales to the unit's session
    ceiling. The per-phase 4000 default truncated a dense week's `sessions`
    array on the forced-tool retry (thinking off → `max_tokens` IS the whole
    output budget) → empty/partial tool args → schema_violation."""

    def _capture_max_tokens(self, week_range):
        from layer4 import per_phase
        from layer4.phase_structure import phase_structure_from_3b

        ps = phase_structure_from_3b(_layer3b(), _PLAN_START)
        captured: dict[str, int] = {}

        def _caller(_sys, _user, _tool, _model, _temp, max_tokens, _thinking):
            captured["max_tokens"] = max_tokens
            # Empty sessions → accepted immediately so the loop runs exactly
            # once and we capture the budget passed to the LLM caller.
            return _PhaseOut(
                tool_args={"sessions": [], "phase_synthesis_notes": "x"},
                input_tokens=1000,
                output_tokens=50,
                latency_ms=1000,
            )

        per_phase.synthesize_phase(
            user_id=1,
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(),
            race_event_payload=_race_event(),
            prior_block_sessions=[],
            plan_version_id=1,
            etl_version_set={"layer0": "v7"},
            mode="plan_create",
            week_range=week_range,
            llm_caller=_caller,
        )
        return captured["max_tokens"]

    def test_block_mode_scales_max_tokens_to_session_ceiling(self):
        from layer4 import per_phase

        mt = self._capture_max_tokens((1, 1))
        expected = (
            per_phase._MAX_SESSIONS_PER_WEEK
            * per_phase._BLOCK_OUTPUT_TOKENS_PER_SESSION
            + per_phase._BLOCK_OUTPUT_TOKENS_OVERHEAD
        )
        assert mt == expected
        # The whole point: the dense-week budget exceeds the per-phase default
        # that truncated the forced-tool retry.
        assert mt > per_phase.DEFAULT_MAX_TOKENS

    def test_full_phase_mode_keeps_caller_max_tokens(self):
        from layer4 import per_phase

        # Whole-phase (seam-driven re-synth) is intentionally NOT scaled — a
        # 56-session single call is the unit decomposition replaced.
        mt = self._capture_max_tokens(None)
        assert mt == per_phase.DEFAULT_MAX_TOKENS


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
        # #698 Track 1 (Slice 2) — `recovery` is the 4th session kind.
        assert set(sess_items["properties"]["kind"]["enum"]) == {
            "cardio",
            "strength",
            "rest",
            "recovery",
        }

    def test_intensity_target_oneof_nine_shapes(self):
        t = build_record_phase_sessions_tool()
        cb_items = (
            t["input_schema"]["properties"]["sessions"]["items"][
                "properties"
            ]["cardio_blocks"]["items"]
        )
        assert len(cb_items["properties"]["intensity_target"]["oneOf"]) == 9

    def test_feasible_pool_enum_bounds_exercise_id(self):
        """Track 2 D1: passing feasible_pool_ids constrains exercise_id to enum."""
        pool = ["E-back-squat", "E-deadlift", "E-bench-press"]
        t = build_record_phase_sessions_tool(feasible_pool_ids=pool)
        ex_prop = (
            t["input_schema"]["properties"]["sessions"]["items"][
                "properties"
            ]["strength_exercises"]["items"]["properties"]["exercise_id"]
        )
        assert ex_prop == {"type": "string", "enum": pool}

    def test_feasible_pool_none_keeps_free_string(self):
        """Backward compat: no feasible_pool_ids → free-string exercise_id."""
        t = build_record_phase_sessions_tool()
        ex_prop = (
            t["input_schema"]["properties"]["sessions"]["items"][
                "properties"
            ]["strength_exercises"]["items"]["properties"]["exercise_id"]
        )
        assert ex_prop == {"type": "string"}
        assert "enum" not in ex_prop

    def test_feasible_pool_empty_list_keeps_free_string(self):
        """Empty list → no enum (avoids invalid empty-enum schema)."""
        t = build_record_phase_sessions_tool(feasible_pool_ids=[])
        ex_prop = (
            t["input_schema"]["properties"]["sessions"]["items"][
                "properties"
            ]["strength_exercises"]["items"]["properties"]["exercise_id"]
        )
        assert "enum" not in ex_prop


class TestComputeFeasiblePoolIds:
    """Track 2 D1: cluster-union of resolved exercise ids minus 2D-excluded."""

    def _l2c(self, locale_id: str, exercise_ids: list[str]) -> Layer2CPayload:
        return Layer2CPayload(
            locale_id=locale_id,
            etl_version_set={"layer0": "v7"},
            effective_pool=list(exercise_ids),
            discipline_coverage=[
                DisciplineCoverage(
                    discipline_id="D-run",
                    discipline_name="Running",
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
                    discipline_ids=["D-run"],
                    sport_relevance_notes={"D-run": "x"},
                    priority_per_discipline={"D-run": "Medium"},
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

    def test_empty_payloads_returns_empty(self):
        from layer4 import compute_feasible_pool_ids

        assert compute_feasible_pool_ids({}, None) == []

    def test_single_locale_returns_sorted_ids(self):
        from layer4 import compute_feasible_pool_ids

        l2c = self._l2c("L-home", ["E-deadlift", "E-back-squat", "E-bench"])
        assert compute_feasible_pool_ids({"L-home": l2c}, None) == [
            "E-back-squat",
            "E-bench",
            "E-deadlift",
        ]

    def test_cluster_union_dedupes(self):
        from layer4 import compute_feasible_pool_ids

        home = self._l2c("L-home", ["E-deadlift", "E-bench"])
        hotel = self._l2c("L-hotel", ["E-bench", "E-pushup"])
        out = compute_feasible_pool_ids({"L-home": home, "L-hotel": hotel}, None)
        assert out == ["E-bench", "E-deadlift", "E-pushup"]

    def test_2d_exclusion_drops_excluded_ids(self):
        from layer4 import compute_feasible_pool_ids
        from layer4.context import Evidence, ExerciseRisk

        l2c = self._l2c("L-home", ["E-deadlift", "E-back-squat", "E-overhead-press"])
        l2d = Layer2DPayload(
            etl_version_set={"layer0": "v7"},
            excluded_exercises=[
                ExerciseRisk(
                    exercise_id="E-overhead-press",
                    exercise_name="Overhead Press",
                    discipline_ids=["D-run"],
                    verdict="exclude",
                    accommodations=[],
                    evidence=[
                        Evidence(
                            source="contraindicated_part",
                            exercise_field="contraindicated_parts",
                            matched_value="wrist",
                            injury_body_part="wrist",
                            injury_severity="severe",
                        )
                    ],
                )
            ],
            accommodated_exercises=[],
            clean_exercise_ids=["E-deadlift", "E-back-squat"],
            discipline_risk_profiles=[],
            coaching_flags=[],
            hitl_required=False,
            hitl_items=[],
        )
        assert compute_feasible_pool_ids({"L-home": l2c}, l2d) == [
            "E-back-squat",
            "E-deadlift",
        ]


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

    def test_seam_resynthesis_runs_week_by_week_not_whole_phase(self):
        """D-77 Slice 3: a seam-driven re-synthesis is decomposed into week-blocks
        (each sized to the block-mode session ceiling, ~21.6k) instead of one
        whole-phase call at the raw 4000 default that truncated → schema_violation.
        Assert EVERY synthesizer call in the run — primary AND seam re-synth —
        used the block-mode ceiling, i.e. none fell back to the 4000 whole-phase
        budget the seam path used to take."""
        from layer4 import per_phase

        block_ceiling = (
            per_phase._MAX_SESSIONS_PER_WEEK
            * per_phase._BLOCK_OUTPUT_TOKENS_PER_SESSION
            + per_phase._BLOCK_OUTPUT_TOKENS_OVERHEAD
        )
        seen_max_tokens: list[int] = []

        def _recording_phase_caller(
            _sys, _user, _tool, _model, _temp, max_tokens, _thinking
        ) -> _PhaseOut:
            seen_max_tokens.append(max_tokens)
            return _PhaseOut(
                tool_args=_empty_phase_output(),
                input_tokens=6000,
                output_tokens=2000,
                latency_ms=8000,
            )

        result = llm_layer4_plan_create(
            **_call_kwargs(),
            phase_caller=_recording_phase_caller,
            seam_caller=_seam_stub_flagged_major_then_approved(),
        )

        # The re-synth fired...
        assert (result.seam_reviews or [])[0].triggered_resynthesis is True
        # ...and no call used the whole-phase 4000 default — every synthesizer
        # call (primary blocks + the seam re-synth's blocks) was block-mode sized.
        assert seen_max_tokens, "expected synthesizer calls"
        assert all(mt == block_ceiling for mt in seen_max_tokens), seen_max_tokens
        assert per_phase.DEFAULT_MAX_TOKENS not in seen_max_tokens

    def test_seam_resynth_phase_idx_stays_in_disjoint_band(self):
        """Seam-resynth cache rows must land in [500, 1000): above the primary
        block index (< 500, far above any real plan's week count) and below the
        seam-review base (1000), so they never alias either row class."""
        from layer4.plan_create import (
            _SEAM_CACHE_PHASE_IDX_BASE,
            _SEAM_RESYNTH_BLOCK_IDX_BASE,
            _seam_resynth_block_phase_idx,
        )

        # Realistic worst case: several seams, many weeks per phase.
        for seam_idx in range(5):
            for week in range(1, 21):
                idx = _seam_resynth_block_phase_idx(seam_idx, week)
                assert _SEAM_RESYNTH_BLOCK_IDX_BASE <= idx < _SEAM_CACHE_PHASE_IDX_BASE
        # Distinct (seam, week) pairs never collide.
        seen = {
            _seam_resynth_block_phase_idx(s, w)
            for s in range(5)
            for w in range(1, 21)
        }
        assert len(seen) == 5 * 20


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


class TestSessionGridPromptRewrite:
    """Track 2 slice 2b: the per_phase prompt now consumes the deterministic
    session_grid; the prior allocation-by-LLM framing is removed."""

    def _layer2a_with_totals(self) -> Layer2APayload:
        """The default _layer2a omits weekly_total_hours_by_phase, which the
        grid needs to convert phase_load percentages into hours. Add it."""
        base = _layer2a()
        return base.model_copy(
            update={
                "weekly_total_hours_by_phase": {
                    "Base": (8.0, 12.0),
                    "Build": (10.0, 14.0),
                    "Peak": (12.0, 16.0),
                    "Taper": (5.0, 8.0),
                },
            }
        )

    def _render(self, race_event_payload=None):
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        # Extend _layer1 with a weekly_hours_target so the grid has capacity to
        # convert into session counts (default _layer1 has neither windows nor
        # goal, so weekly_capacity_hours returns None → empty grid).
        l1 = {**_layer1(), "identity": {"weekly_hours_target": 12.0}}
        return render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=l1,
            layer2a_payload=self._layer2a_with_totals(),
            layer2b_payload=_layer2b(),
            layer2c_payloads=_layer2c(),
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=l3b,
            race_event_payload=race_event_payload,
            prior_block_sessions=[],
            retries_used=0,
            rule_failures=[],
            seam_issues=[],
            seam_direction=None,
            week_range=(1, 1),
        )

    def test_session_grid_block_appears(self):
        text = self._render()
        assert "=== Session grid" in text

    def test_session_grid_renders_per_discipline_counts(self):
        text = self._render()
        assert "session(s) ×" in text
        # The _layer2a fixture includes D-run; it should appear under the grid.
        assert "D-run" in text

    def test_session_grid_renders_polarized_intensity_mix(self):
        text = self._render()
        # Cardio-having weeks emit a polarized intensity line.
        assert "polarized" in text
        assert "easy" in text and "hard" in text

    def test_old_allocation_framing_removed_from_user_prompt(self):
        """The pre-2b 'Per-week volume targets' + 'Intended intensity
        distribution' lines are gone; the grid block replaces them."""
        text = self._render()
        assert "Per-week volume targets per discipline" not in text
        assert "Intended intensity distribution" not in text

    def test_race_sim_block_absent_for_single_day_race(self):
        # Default no race_event_payload → no race-sim block.
        text = self._render()
        assert "Race-sim long day" not in text

    def test_system_prompt_dropped_hardcoded_dose_language(self):
        from layer4.per_phase import SYSTEM_PROMPT

        # The pre-2b dose-by-phase guidance is gone; the grid is the source.
        assert "2 sessions/week" not in SYSTEM_PROMPT
        assert "Base/Build 2 sessions" not in SYSTEM_PROMPT
        assert "deterministic" in SYSTEM_PROMPT.lower()
        assert "session grid" in SYSTEM_PROMPT.lower()


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

    def test_coaching_memory_renders_when_present(self):
        # #690 — durable coaching_preferences surface in the Athlete context so
        # the synthesizer can honor an explicit high-variety request + notes.
        from layer4.per_phase import render_user_prompt
        from layer4.phase_structure import phase_structure_from_3b

        l3b = _layer3b()
        ps = phase_structure_from_3b(l3b, _PLAN_START)
        l1 = dict(_layer1())
        l1["coaching_preferences"] = [
            {"category": "training",
             "content": "Wants high exercise variety.", "permanent": True},
            {"category": "avoid_exercise",
             "content": "No overhead pressing.", "permanent": False},
        ]
        text = render_user_prompt(
            phase_spec=ps.phases[0],
            phase_structure=ps,
            phase_index_in_plan=0,
            is_first_phase_in_plan=True,
            layer1_payload=l1,
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
        assert "Coaching memory" in text
        assert "[permanent] training: Wants high exercise variety." in text
        assert "[advisory] avoid_exercise: No overhead pressing." in text

    def test_coaching_memory_suppressed_when_absent(self):
        # Suppress-on-empty: the default _layer1() carries no coaching_preferences.
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
        assert "Coaching memory" not in text

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
    def test_patched_with_accept_with_observation_coerces(self):
        # A seam review is advisory; an invalid LLM verdict combination must be
        # coerced to the nearest valid one, NOT raise and kill the plan (pv=55
        # regression, 2026-06-03). `patched` + `accept_with_observation` →
        # `flagged_major` + `accept_with_observation` (verdict name is
        # informational per §6.2; the accept-with-observation intent is kept).
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
        result = review_seam(
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
        assert result.verdict == "flagged_major"
        assert result.proposed_patch_direction == "accept_with_observation"
        assert result.seam_issues == ["x"]

    def test_coerce_verdict_combination_table(self):
        # Every invalid combination maps to a valid one; valid combinations pass
        # through untouched.
        from layer4.seam_review import _coerce_verdict_combination

        # Invalid → coerced
        assert _coerce_verdict_combination("patched", "accept_with_observation", ["x"]) == (
            "flagged_major", "accept_with_observation")
        assert _coerce_verdict_combination("flagged_major", None, ["x"]) == (
            "flagged_major", "accept_with_observation")
        assert _coerce_verdict_combination("patched", None, ["x"]) == (
            "flagged_major", "accept_with_observation")
        assert _coerce_verdict_combination("approved", None, ["x"]) == (
            "flagged_minor", None)
        assert _coerce_verdict_combination("approved", "re_prompt_prior", []) == (
            "approved", None)
        assert _coerce_verdict_combination("flagged_minor", "re_prompt_next", ["x"]) == (
            "flagged_minor", None)

        # Valid → unchanged
        assert _coerce_verdict_combination("approved", None, []) == ("approved", None)
        assert _coerce_verdict_combination("flagged_minor", None, ["x"]) == (
            "flagged_minor", None)
        assert _coerce_verdict_combination("flagged_major", "re_prompt_prior", ["x"]) == (
            "flagged_major", "re_prompt_prior")
        assert _coerce_verdict_combination("patched", "re_prompt_next", ["x"]) == (
            "patched", "re_prompt_next")
        assert _coerce_verdict_combination(
            "flagged_major", "accept_with_observation", ["x"]) == (
            "flagged_major", "accept_with_observation")


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

    def test_cache_hit_rebinds_plan_version_id_on_sessions(self):
        """Regression (prod pv=45 UniqueViolation): the per-block cache key folds
        in only the athlete inputs (call_cache_key), so the SAME cached block is
        shared across plan versions — but the cached payload stamps each session
        with the SYNTHESIZING run's plan_version_id. A later plan replaying an
        older plan's cached block must REBIND every session to its own id, else
        the stale id reaches persist and collides on the plan_sessions
        natural-key UNIQUE. Synthesize under pv=1, hit the cache under pv=2, and
        assert every session carries 2 — not the cached 1."""
        cache = Layer4Cache(InMemoryCacheBackend())
        sessions_stub = _phase_stub(
            _phase_output_with_sessions(phase_start=_PLAN_START, phase_weeks=1)
        )

        first = llm_layer4_plan_create(
            **{**_call_kwargs(), "plan_version_id": 1},
            cache=cache,
            call_cache_key="call-shared",
            phase_caller=sessions_stub,
            seam_caller=_seam_stub_approved(),
        )
        assert first.sessions
        assert all(s.plan_version_id == 1 for s in first.sessions)

        # Same call_cache_key (same athlete inputs) → every block is a cache HIT,
        # but the plan being built is pv=2.
        second = llm_layer4_plan_create(
            **{**_call_kwargs(), "plan_version_id": 2},
            cache=cache,
            call_cache_key="call-shared",
            phase_caller=sessions_stub,
            seam_caller=_seam_stub_approved(),
        )
        assert second.sessions
        # Every hydrated-from-cache session is rebound to the NEW plan version.
        assert all(s.plan_version_id == 2 for s in second.sessions), [
            s.plan_version_id for s in second.sessions
        ]

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


class _CountingFlaggedThenApprovedSeamStub:
    """flagged_major+re_prompt_next on the FIRST invocation (drives one seam
    re-synthesis + an iter-2 review), approved thereafter, counting every call.
    Mirrors `_seam_stub_flagged_major_then_approved` but exposes `.calls` so a
    resumed pass can assert ZERO new seam LLM calls — iter-1 AND iter-2 served
    from cache. Locked so the first-call-flagged contract holds even though
    iter-1 reviews fire in parallel."""

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, *_a, **_kw) -> _SeamOut:
        with self._lock:
            i = self.calls
            self.calls += 1
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


class TestIter2SeamReviewCache:
    """#209 §9.2 iter-2 seam-review cache — the re-synthesis-driven iter-2 review
    caches under a disjoint phase_idx band (>= _SEAM_ITER2_CACHE_PHASE_IDX_BASE),
    so a resumed pass replays it from cache instead of re-firing the LLM call.
    Closes the gap where the iter-2 seam tail re-ran whole on every resume."""

    def test_cold_run_stores_iter2_row_in_disjoint_band(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        seam_stub = _CountingFlaggedThenApprovedSeamStub()
        result = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-iter2",
            phase_caller=_CountingPhaseStub(_empty_phase_output()),
            seam_caller=seam_stub,
        )
        # The flagged seam triggered a re-synthesis + an iter-2 review.
        assert any(sr.triggered_resynthesis for sr in (result.seam_reviews or []))
        backend: Any = cache.backend
        iter2_rows = [
            e for (_k, idx), e in backend._rows.items()
            if idx >= _SEAM_ITER2_CACHE_PHASE_IDX_BASE
        ]
        # Exactly one iter-2 review fired (one seam flagged) → one iter-2 row,
        # routed to the same entry_point as the per-phase + iter-1 rows.
        assert len(iter2_rows) == 1
        assert {e.entry_point for e in iter2_rows} == {"plan_create"}

    def test_resume_replays_iter2_from_cache(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        first_seam = _CountingFlaggedThenApprovedSeamStub()
        first_phase = _CountingPhaseStub(_empty_phase_output())
        first = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-iter2",
            phase_caller=first_phase,
            seam_caller=first_seam,
        )
        assert any(sr.triggered_resynthesis for sr in (first.seam_reviews or []))
        misses_after_cold = cache.metrics.phase_misses_total
        assert misses_after_cold > 0
        assert cache.metrics.phase_hits_total == 0

        second_seam = _CountingFlaggedThenApprovedSeamStub()
        second_phase = _CountingPhaseStub(_empty_phase_output())
        second = llm_layer4_plan_create(
            **_call_kwargs(),
            cache=cache,
            call_cache_key="call-iter2",
            phase_caller=second_phase,
            seam_caller=second_seam,
        )
        # The resumed pass fired NO seam LLM calls (iter-1 + iter-2 from cache)
        # and NO synthesizer calls (primary + re-synth blocks from cache).
        assert second_seam.calls == 0
        assert second_phase.calls == 0
        # Every row written on the cold pass is a hit; no new misses.
        assert cache.metrics.phase_misses_total == misses_after_cold
        assert cache.metrics.phase_hits_total == misses_after_cold
        assert isinstance(second, Layer4Payload)

    def test_iter2_phase_idx_band_disjoint_from_iter1(self):
        """iter-2 rows sit at >= 2000, above the iter-1 base (1000), so under any
        realistic seam count the two seam-review row classes never alias."""
        assert _SEAM_ITER2_CACHE_PHASE_IDX_BASE > _SEAM_CACHE_PHASE_IDX_BASE
        for seam_idx in range(50):
            assert (
                _SEAM_CACHE_PHASE_IDX_BASE + seam_idx
                < _SEAM_ITER2_CACHE_PHASE_IDX_BASE
            )


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


def _plan_session(
    kind: str,
    d: date,
    idx: int,
    *,
    intensity: str = "easy",
    sid: str | None = None,
):
    """Build a minimal valid `PlanSession` of the given kind for the per-day
    clamp unit tests (the clamp operates on built `PlanSession` objects)."""
    from layer4.payload import (
        CardioBlock,
        PlanSession,
        RecoveryExercise,
        StrengthExercise,
    )

    kw: dict[str, Any] = dict(
        session_id=sid or f"S-{kind}-{d.isoformat()}-{idx}-{intensity}",
        plan_version_id=1,
        date=d,
        day_of_week=d.strftime("%a"),
        session_index_in_day=idx,
        time_of_day="morning",
        kind=kind,
        duration_min=60,
        intensity_summary=intensity,
        session_notes="n.",
        coaching_intent="c.",
        coaching_flags=[],
    )
    if kind == "cardio":
        kw["discipline_id"] = "D-run"
        kw["locale_id"] = "home_gym"
        kw["cardio_blocks"] = [
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target={"hr_bpm_low": 130, "hr_bpm_high": 145},
                instructions="steady.",
            )
        ]
    elif kind == "strength":
        kw["discipline_id"] = "D-strength"
        kw["locale_id"] = "home_gym"
        kw["strength_exercises"] = [
            StrengthExercise(
                exercise_id="E-1",
                exercise_name="Squat",
                resolution_tier=1,
                sets=3,
                reps_per_set=5,
                load_prescription="bodyweight",
                rest_between_sets_sec=90,
                instructions="x.",
                coaching_flags=[],
            )
        ]
    elif kind == "recovery":
        kw["duration_min"] = 20
        kw["recovery_exercises"] = [
            RecoveryExercise(
                exercise_id="R-1",
                exercise_name="Foam roll",
                prescription="2x30s/side",
                instructions="x.",
            )
        ]
    return PlanSession(**kw)


class TestPerDayTrainingClamp:
    """#351 — `_clamp_sessions_per_day` caps TRAINING sessions at 2 per calendar
    day pre-validation (drop policy: keep a cardio + one other), so the common
    >2/day over-emit self-heals with zero retries. Recovery is exempt and
    additive — never counted or trimmed."""

    def test_keeps_the_lone_cardio(self):
        # 1 cardio + 2 strength on one day. The drop policy keeps a cardio + one
        # other, so the lone cardio must SURVIVE (never dropped to leave a
        # strength+strength pair), satisfying the "≥1 cardio" composition rule.
        from layer4.per_phase import _clamp_sessions_per_day

        d = date(2026, 4, 6)
        sessions = [
            _plan_session("strength", d, 0, sid="s0"),
            _plan_session("cardio", d, 1, sid="c1"),
            _plan_session("strength", d, 2, sid="s2"),
        ]
        out, notes = _clamp_sessions_per_day(sessions)
        assert notes  # the clamp fired
        kept = [s for s in out if s.date == d]
        assert len(kept) == 2
        assert sum(1 for s in kept if s.kind == "cardio") == 1
        assert "c1" in {s.session_id for s in kept}
        # surviving sessions renumbered to a contiguous 0..n-1
        assert sorted(s.session_index_in_day for s in kept) == [0, 1]

    def test_prefers_non_hard(self):
        # 3 cardio, one hard + two easy. The hard one sorts last and is dropped.
        from layer4.per_phase import _clamp_sessions_per_day

        d = date(2026, 4, 6)
        sessions = [
            _plan_session("cardio", d, 0, intensity="hard", sid="hard"),
            _plan_session("cardio", d, 1, intensity="easy", sid="easy1"),
            _plan_session("cardio", d, 2, intensity="easy", sid="easy2"),
        ]
        out, _ = _clamp_sessions_per_day(sessions)
        kept_ids = {s.session_id for s in out}
        assert "hard" not in kept_ids
        assert kept_ids == {"easy1", "easy2"}

    def test_recovery_preserved_when_training_clamped(self):
        # 3 training + 1 additive recovery on one day. The clamp trims TRAINING to
        # 2 but the recovery is never counted or dropped (≤2 training + ≤1
        # recovery, #698 Track 1). Survivors renumber to a contiguous 0..2.
        from layer4.per_phase import _clamp_sessions_per_day

        d = date(2026, 4, 6)
        sessions = [
            _plan_session("cardio", d, 0, sid="c0"),
            _plan_session("cardio", d, 1, sid="c1a"),
            _plan_session("cardio", d, 1, sid="c1b"),
            _plan_session("recovery", d, 2, sid="rec"),
        ]
        out, notes = _clamp_sessions_per_day(sessions)
        assert notes
        ids = {s.session_id for s in out}
        assert "rec" in ids
        day_out = [s for s in out if s.date == d]
        training = [s for s in day_out if s.kind in ("cardio", "strength")]
        assert len(training) == 2
        assert sorted(s.session_index_in_day for s in day_out) == [0, 1, 2]

    def test_passthrough_two_training_plus_recovery(self):
        # The normal additive-recovery day (2 training + 1 recovery) is at the cap,
        # not over it — the clamp must leave it completely untouched.
        from layer4.per_phase import _clamp_sessions_per_day

        d = date(2026, 4, 6)
        sessions = [
            _plan_session("cardio", d, 0),
            _plan_session("strength", d, 1),
            _plan_session("recovery", d, 2),
        ]
        out, notes = _clamp_sessions_per_day(sessions)
        assert notes == []
        assert out == sessions

