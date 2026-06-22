"""Tests for `layer3d.gate` — the HITL aggregation + gate node per
`aidstation-sources/specs/Layer3D_Spec.md` (Slice 1: aggregation of the
already-emitted upstream items + resolution/status rules + gate-status).

The 3C source is deferred to a later slice and is not exercised here. The
§5.2/§5.3 feasibility detectors (Slice 2) are covered by TS-3D-5/6/7. Upstream
payloads are built with minimal valid fixtures (same construction pattern as
`tests/test_layer4_orchestrator.py`); HITL items are injected per scenario.
No LLM, no DB — the node is a pure function (§3).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from layer3d.gate import (
    GateResolution,
    Layer3DGateError,
    compute_gate_status,
    evaluate_layer3d_gate,
    make_item_key,
    map_2a_items,
    map_2d_items,
    map_2e_items,
    map_3b_items,
)
from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DisciplineRisk,
    ExerciseRisk,
    GoalViability,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2CPayload,
    Layer2DHitlItem,
    Layer2DPayload,
    Layer2EHitlItem,
    Layer2EPayload,
    Layer3BHITLItem,
    Layer3BPayload,
    MacroTargets,
    PeriodizationShape,
    PhaseLoadBands,
    RationaleMetadata,
    ResolvedExercise,
    SubstituteRecommendation,
    SupplementIntegrationPayload,
    TrainingGapsSummary,
    UnresolvedFlag,
    WeightResult,
)

_EVS = {"0A": "v7", "0B": "v7", "0C": "v7"}
_USER_ID = 42
_PVID = 100
_PLAN_START = date(2026, 7, 1)


# ─── Minimal valid upstream payload builders ────────────────────────────────


def _layer2a(
    *,
    disciplines: list[Layer2ADiscipline] | None = None,
    unresolved_flags: list[UnresolvedFlag] | None = None,
    hitl_required: bool = False,
    weekly_total_hours_by_phase: dict[str, tuple[float, float]] | None = None,
    etl_version_set: dict[str, str] | None = None,
) -> Layer2APayload:
    return Layer2APayload(
        framework_sport="AR",
        etl_version_set=etl_version_set or dict(_EVS),
        disciplines=disciplines or [],
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
            any_no_substitute=False,
            any_multi_substitute_candidate=False,
        ),
        hitl_required=hitl_required,
        unresolved_flags=unresolved_flags or [],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            template_version="v1", generated_at="2026-06-01T10:00:00Z"
        ),
        weekly_total_hours_by_phase=weekly_total_hours_by_phase or {},
    )


def _discipline(
    *,
    discipline_id: str = "D-trail",
    name: str = "trail_running",
    inclusion: str = "included",
) -> Layer2ADiscipline:
    return Layer2ADiscipline(
        discipline_id=discipline_id,
        discipline_name=name,
        inclusion=inclusion,  # type: ignore[arg-type]
        role="Primary",
        is_conditional=False,
        load_weight=WeightResult(value=0.5, source="system_default", system_default=0.5),
        sleep_deprivation_relevant=False,
        rationale="Listed in onboarding but ambiguous.",
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


def _layer2c(
    *,
    exercises_resolved: list[ResolvedExercise] | None = None,
    etl_version_set: dict[str, str] | None = None,
) -> Layer2CPayload:
    return Layer2CPayload(
        locale_id="home",
        etl_version_set=etl_version_set or dict(_EVS),
        effective_pool=[rx.exercise_id for rx in (exercises_resolved or [])],
        discipline_coverage=[],
        exercises_resolved=exercises_resolved or [],
        coaching_flags=[],
    )


def _resolved_ex(
    *,
    exercise_id: str,
    exercise_type: str = "Strength",
    discipline_id: str = "D-trail",
    tier: int = 1,
) -> ResolvedExercise:
    return ResolvedExercise(
        exercise_id=exercise_id,
        exercise_name=exercise_id.replace("EX", "Exercise "),
        exercise_type=exercise_type,
        discipline_ids=[discipline_id],
        sport_relevance_notes={},
        priority_per_discipline={discipline_id: "High"},
        tier=tier,  # type: ignore[arg-type]
        terrain_required=[],
        contraindicated_parts=[],
        contraindicated_conditions=[],
        accommodations=[],
    )


def _excluded_ex(*, exercise_id: str, discipline_id: str = "D-trail") -> ExerciseRisk:
    return ExerciseRisk(
        exercise_id=exercise_id,
        exercise_name=exercise_id.replace("EX", "Exercise "),
        discipline_ids=[discipline_id],
        verdict="exclude",
        accommodations=[],
        evidence=[],
    )


def _disc_risk(
    *,
    discipline_id: str = "D-trail",
    name: str = "trail_running",
    risk_level: str = "high",
    substitutes: list[SubstituteRecommendation] | None = None,
) -> DisciplineRisk:
    return DisciplineRisk(
        discipline_id=discipline_id,
        discipline_name=name,
        risk_level=risk_level,  # type: ignore[arg-type]
        matched_current_parts=[],
        matched_history_parts=[],
        suggested_substitutes=substitutes or [],
        reasoning="Injury rules out the discipline.",
    )


def _layer2d(
    *,
    hitl_items: list[Layer2DHitlItem] | None = None,
    excluded_exercises: list[ExerciseRisk] | None = None,
    discipline_risk_profiles: list[DisciplineRisk] | None = None,
    hitl_required: bool = False,
    etl_version_set: dict[str, str] | None = None,
) -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set=etl_version_set or dict(_EVS),
        excluded_exercises=excluded_exercises or [],
        accommodated_exercises=[],
        clean_exercise_ids=[],
        discipline_risk_profiles=discipline_risk_profiles or [],
        coaching_flags=[],
        hitl_required=hitl_required,
        hitl_items=hitl_items or [],
    )


def _layer2e(
    *,
    hitl_items: list[Layer2EHitlItem] | None = None,
    contraindication_hitl_items: list[Layer2EHitlItem] | None = None,
    hitl_required: bool = False,
    etl_version_set: dict[str, str] | None = None,
) -> Layer2EPayload:
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
        athlete_id=str(_USER_ID),
        etl_version_set=etl_version_set or dict(_EVS),
        computed_at=datetime(2026, 6, 1, 10, 0, 0),
        bmr_method="mifflin_st_jeor",
        bmr_kcal=1750.0,
        daily_nutrition_baseline=DailyNutritionBaseline(
            per_phase={"Base": targets, "Build": targets, "Peak": targets, "Taper": targets}
        ),
        race_day_fueling=[],
        supplement_integration=SupplementIntegrationPayload(
            integrated=[],
            race_day_suggestions=[],
            contraindication_flags=[],
            contraindication_hitl_items=contraindication_hitl_items or [],
        ),
        dietary_pattern_adjustments=[],
        sleep_dep_overlay=None,
        heat_acclim_adjustments=[],
        coaching_flags=[],
        hitl_items=hitl_items or [],
        hitl_required=hitl_required,
    )


def _layer3b(
    *,
    hitl_surface: list[Layer3BHITLItem] | None = None,
    etl_version_set: dict[str, str] | None = None,
) -> Layer3BPayload:
    return Layer3BPayload(
        user_id=_USER_ID,
        as_of=datetime(2026, 6, 1, 10, 0, 0),
        mode="no-event",
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1500,
        input_tokens=3000,
        output_tokens=800,
        etl_version_set=etl_version_set or dict(_EVS),
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="solid base",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode="standard",
            start_phase="Base",
            phase_weeks=None,
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        hitl_surface=hitl_surface or [],
        notable_observations=[],
    )


def _2d_item(
    *,
    hitl_type: str = "post_surgical_clearance",
    severity: str = "block",
    discipline_id: str | None = None,
) -> Layer2DHitlItem:
    return Layer2DHitlItem(
        hitl_type=hitl_type,  # type: ignore[arg-type]
        discipline_id=discipline_id,
        severity=severity,  # type: ignore[arg-type]
        message="Post-surgical clearance required before high-load training.",
        suggested_resolutions=["Confirm clearance with your surgeon"],
    )


def _2e_item(*, item_id: str = "supp_cardiac_1", block_level: str = "block") -> Layer2EHitlItem:
    return Layer2EHitlItem(
        item_id=item_id,
        gate_number=1,
        block_level=block_level,
        affected_supplement_id="caffeine",
        rationale_for_athlete="A stimulant supplement with your cardiac history needs review.",
        rationale_for_layer3="cardiac x stimulant contraindication",
        resolution_options=["Drop the supplement", "Get medical clearance"],
    )


def _3b_item(*, item_label: str = "unrealistic_goal", severity: str = "warning") -> Layer3BHITLItem:
    return Layer3BHITLItem(
        source="3B",
        item_label=item_label,
        severity=severity,  # type: ignore[arg-type]
        description="Your goal is aggressive for the time you have.",
        recommended_action="Consider extending the runway.",
        acknowledge_option=None if severity == "blocker" else "I understand",
        revise_option="Extend timeline",
        revise_target="h2.goal_outcome",
    )


def _evaluate(**overrides):
    kwargs = dict(
        user_id=_USER_ID,
        plan_version_id=_PVID,
        layer1_payload={},
        layer2a_payload=_layer2a(),
        layer2c_payloads={"home": _layer2c()},
        layer2d_payload=_layer2d(),
        layer2e_payload=_layer2e(),
        layer3b_payload=_layer3b(),
    )
    kwargs.update(overrides)
    return evaluate_layer3d_gate(**kwargs)


# ─── TS-3D-1: clean athlete ──────────────────────────────────────────────────


def test_clean_athlete_is_green():
    gate = _evaluate()
    assert gate.gate_status == "green"
    assert gate.items == []
    assert gate.evaluated_against == _EVS
    assert gate.evaluated_at is None  # caller stamps on persist


# ─── TS-3D-2: 3B blocker ─────────────────────────────────────────────────────


def test_3b_blocker_blocks_and_is_revise_only():
    gate = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[_3b_item(severity="blocker")])
    )
    assert gate.gate_status == "blocked"
    assert len(gate.items) == 1
    item = gate.items[0]
    assert item.source == "3B"
    assert item.severity == "blocker"
    assert item.can_acknowledge is False
    assert item.revise_target == "h2.goal_outcome"
    assert item.status == "pending"


# ─── TS-3D-3: 2D block → revise_target injury record ─────────────────────────


def test_2d_block_is_blocker_pointing_at_injuries():
    gate = _evaluate(layer2d_payload=_layer2d(hitl_items=[_2d_item()]))
    assert gate.gate_status == "blocked"
    item = gate.items[0]
    assert item.source == "2D"
    assert item.severity == "blocker"
    assert item.can_acknowledge is False
    assert item.revise_target == "profile.injuries"
    assert item.resolution_options == ["Confirm clearance with your surgeon"]


# ─── TS-3D-4: 2E supplement×cardiac contraindication ─────────────────────────


def test_2e_block_is_blocker():
    gate = _evaluate(
        layer2e_payload=_layer2e(contraindication_hitl_items=[_2e_item()])
    )
    assert gate.gate_status == "blocked"
    item = gate.items[0]
    assert item.source == "2E"
    assert item.severity == "blocker"
    assert item.can_acknowledge is False


# ─── TS-3D-8: 3B warning acknowledged with reasoning → green ─────────────────


def test_warning_acknowledged_with_reasoning_goes_green():
    item = _3b_item(severity="warning")
    key = make_item_key("3B", item.item_label, "")
    res = GateResolution(
        kind="acknowledged",
        reasoning="I know it's a stretch; I want to try anyway.",
        resolved_at=datetime(2026, 6, 1, 12, 0, 0),
    )
    gate = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[item]),
        prior_resolutions={key: res},
    )
    assert gate.gate_status == "green"
    assert gate.items[0].status == "acknowledged"
    assert gate.items[0].resolution is not None
    assert gate.items[0].resolution.reasoning.startswith("I know")


def test_warning_unresolved_is_needs_review():
    gate = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[_3b_item(severity="warning")])
    )
    assert gate.gate_status == "needs_review"
    assert gate.items[0].can_acknowledge is True
    assert gate.items[0].status == "pending"


# ─── TS-3D-9: blocker + warning together ─────────────────────────────────────


def test_blocker_and_warning_blocks_even_if_warning_ack():
    blocker = _3b_item(item_label="dnf_recurrence_risk", severity="blocker")
    warning = _3b_item(item_label="first_time_competitive_goal", severity="warning")
    warn_key = make_item_key("3B", warning.item_label, "")
    res = GateResolution(kind="acknowledged", resolved_at=datetime(2026, 6, 1, 12, 0, 0))
    gate = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[blocker, warning]),
        prior_resolutions={warn_key: res},
    )
    assert gate.gate_status == "blocked"
    by_label = {it.source_item_id: it for it in gate.items}
    assert by_label["first_time_competitive_goal"].status == "acknowledged"
    assert by_label["dnf_recurrence_risk"].status == "pending"


# ─── TS-3D-10: ack round 1, revise (clears) round 2 → green ──────────────────


def test_round1_ack_persists_after_round2_revise_clears_blocker():
    blocker = _3b_item(item_label="dnf_recurrence_risk", severity="blocker")
    warning = _3b_item(item_label="first_time_competitive_goal", severity="warning")
    warn_key = make_item_key("3B", warning.item_label, "")

    # Round 1: athlete acknowledges the warning (blocker still pending).
    res_ack = GateResolution(kind="acknowledged", resolved_at=datetime(2026, 6, 1, 12, 0, 0))
    round1 = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[blocker, warning]),
        prior_resolutions={warn_key: res_ack},
    )
    assert round1.gate_status == "blocked"

    # Round 2: the blocker was revised away (re-aggregation no longer surfaces
    # it); the round-1 acknowledgment still applies by stable item_key.
    round2 = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[warning]),
        prior_resolutions={warn_key: res_ack},
    )
    assert round2.gate_status == "green"
    assert round2.items[0].status == "acknowledged"


# ─── TS-3D-11: revise that doesn't fix the blocker ───────────────────────────


def test_revise_that_does_not_fix_reverts_to_pending():
    blocker = _3b_item(item_label="dnf_recurrence_risk", severity="blocker")
    key = make_item_key("3B", blocker.item_label, "")
    res_revised = GateResolution(kind="revised", resolved_at=datetime(2026, 6, 1, 12, 0, 0))
    gate = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[blocker]),
        prior_resolutions={key: res_revised},
    )
    # Same item_key re-surfaced → the edit didn't clear it → pending; blocked.
    assert gate.items[0].status == "pending"
    assert gate.gate_status == "blocked"


# ─── TS-3D-12: etl_version_set mismatch ──────────────────────────────────────


def test_etl_version_set_mismatch_raises():
    with pytest.raises(Layer3DGateError) as exc:
        _evaluate(layer3b_payload=_layer3b(etl_version_set={"0A": "v8"}))
    assert exc.value.code == "etl_version_set_mismatch"


# ─── Preconditions (§4) ──────────────────────────────────────────────────────


def test_missing_upstream_payload_raises():
    with pytest.raises(Layer3DGateError) as exc:
        _evaluate(layer2d_payload=None)
    assert exc.value.code == "missing_upstream_payload"
    assert "2D" in exc.value.detail


def test_plan_version_id_unset_raises():
    with pytest.raises(Layer3DGateError) as exc:
        _evaluate(plan_version_id=0)
    assert exc.value.code == "plan_version_id_unset"


# ─── 2A mapping ──────────────────────────────────────────────────────────────


def test_2a_prompt_required_is_warning():
    p = _layer2a(disciplines=[_discipline(inclusion="prompt_required", name="skiing")])
    items = map_2a_items(p)
    assert len(items) == 1
    assert items[0].source == "2A"
    assert items[0].severity == "warning"
    assert items[0].can_acknowledge is True
    assert "skiing" in items[0].title


def test_2a_included_discipline_emits_nothing():
    assert map_2a_items(_layer2a(disciplines=[_discipline(inclusion="included")])) == []


def test_2a_unresolved_flag_error_is_blocker_warning_is_warning():
    p = _layer2a(
        unresolved_flags=[
            UnresolvedFlag(raw_input="xyz", suggested_match="skiing", severity="error"),
            UnresolvedFlag(raw_input="abc", suggested_match=None, severity="warning"),
        ]
    )
    items = map_2a_items(p)
    by_sev = {it.severity for it in items}
    assert by_sev == {"blocker", "warning"}
    blocker = next(it for it in items if it.severity == "blocker")
    assert blocker.can_acknowledge is False
    warn = next(it for it in items if it.severity == "warning")
    assert "skiing" not in warn.message  # the no-suggestion flag


# ─── 2D / 2E / 3B mapping severities ─────────────────────────────────────────


def test_2d_warn_is_warning():
    items = map_2d_items(_layer2d(hitl_items=[_2d_item(hitl_type="cardiac_high_load_review", severity="warn")]))
    assert items[0].severity == "warning"
    assert items[0].can_acknowledge is True


def test_2e_non_block_level_is_warning():
    items = map_2e_items(_layer2e(hitl_items=[_2e_item(block_level="warn")]))
    assert items[0].severity == "warning"
    assert items[0].can_acknowledge is True


def test_3b_informational_kept():
    items = map_3b_items(_layer3b(hitl_surface=[_3b_item(item_label="note", severity="informational")]))
    assert items[0].severity == "informational"
    assert items[0].can_acknowledge is True


# ─── §9 de-dup: 2E contraindication duplicates a hitl_items entry ────────────


def test_2e_duplicate_contraindication_dedups_by_item_key():
    dup = _2e_item(item_id="same_id")
    gate = _evaluate(
        layer2e_payload=_layer2e(hitl_items=[dup], contraindication_hitl_items=[_2e_item(item_id="same_id")])
    )
    keys = [it.item_key for it in gate.items]
    assert len(keys) == len(set(keys))
    assert len([it for it in gate.items if it.source == "2E"]) == 1


# ─── item_key stability (§6.4) ───────────────────────────────────────────────


def test_item_key_is_stable_and_scoped():
    a = make_item_key("2D", "post_surgical_clearance", "D-trail")
    b = make_item_key("2D", "post_surgical_clearance", "D-trail")
    c = make_item_key("2D", "post_surgical_clearance", "D-ski")
    assert a == b
    assert a != c
    assert len(a) == 16


# ─── unit: resolved_status / compute_gate_status ─────────────────────────────


def test_acknowledge_on_blocker_defensively_dropped_to_pending():
    blocker = _3b_item(severity="blocker")
    key = make_item_key("3B", blocker.item_label, "")
    res = GateResolution(kind="acknowledged", resolved_at=datetime(2026, 6, 1, 12, 0, 0))
    gate = _evaluate(
        layer3b_payload=_layer3b(hitl_surface=[blocker]),
        prior_resolutions={key: res},
    )
    # acknowledge is invalid on a blocker → status falls back to pending.
    assert gate.items[0].status == "pending"
    assert gate.gate_status == "blocked"


def test_compute_gate_status_empty_is_green():
    assert compute_gate_status([]) == "green"


# ─── Rule #15: hitl_required=True but no items → warn + trust the list ───────


def test_hitl_required_with_no_items_does_not_fabricate(caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        gate = _evaluate(layer2d_payload=_layer2d(hitl_required=True, hitl_items=[]))
    assert gate.gate_status == "green"
    assert gate.items == []
    assert any("2D hitl_required=True" in r.message for r in caplog.records)


# ─── §5.2/§5.3 feasibility detectors ─────────────────────────────────────────
#
# These pass `plan_start_date` + `total_weeks`, which is what switches the
# detectors on (the aggregation-only tests above leave `plan_start_date` None
# and so never build a phase structure). total_weeks=20 (standard, no event) →
# all four phases Base(10)/Build(6)/Peak(3)/Taper(1).


def test_feasibility_detectors_off_without_plan_start_date():
    # Same emptied strength pool, but no plan_start_date → no phase structure →
    # detectors skipped → clean aggregation stays green.
    pool = [_resolved_ex(exercise_id=f"EX00{i}") for i in (1, 2, 3)]
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2c_payloads={"home": _layer2c(exercises_resolved=pool)},
        layer2d_payload=_layer2d(
            excluded_exercises=[_excluded_ex(exercise_id="EX001"), _excluded_ex(exercise_id="EX002")]
        ),
    )
    assert gate.gate_status == "green"
    assert gate.items == []


# TS-3D-5 — injury empties a phase's strength pool → blocker.
def test_ts3d5_injury_empties_strength_pool_blocks():
    pool = [_resolved_ex(exercise_id=f"EX00{i}") for i in (1, 2, 3)]
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2c_payloads={"home": _layer2c(exercises_resolved=pool)},
        layer2d_payload=_layer2d(
            excluded_exercises=[_excluded_ex(exercise_id="EX001"), _excluded_ex(exercise_id="EX002")]
        ),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert gate.gate_status == "blocked"
    assert len(gate.items) == 1
    it = gate.items[0]
    assert it.source == "3D_feasibility"
    assert it.source_item_id == "injury_pool_empty"
    assert it.severity == "blocker"
    assert it.can_acknowledge is False
    assert it.revise_target == "profile.injuries"
    assert it.evidence["usable_count"] == 1
    assert it.evidence["pool_before_count"] == 3
    assert set(it.evidence["excluding_2d_ids"]) == {"EX001", "EX002"}
    assert it.evidence["phases"]  # the phases that program strength
    assert it.evidence["headline_phase"] == it.evidence["phases"][0]


def test_structurally_strength_light_plan_is_not_flagged():
    # Only 2 strength exercises ever resolved (pool_before < floor): a pure
    # MTB/climbing-style plan that never had a strength surface — sport sessions
    # cover it, so excluding one is NOT a blocker.
    pool = [_resolved_ex(exercise_id="EX001"), _resolved_ex(exercise_id="EX002")]
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2c_payloads={"home": _layer2c(exercises_resolved=pool)},
        layer2d_payload=_layer2d(excluded_exercises=[_excluded_ex(exercise_id="EX001")]),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert gate.gate_status == "green"
    assert [it for it in gate.items if it.source == "3D_feasibility"] == []


def test_non_strength_types_do_not_count_toward_the_floor():
    # Cardio/skill rows are not strength-session exercises, so a pool of them is
    # not a strength surface (pool_before < floor) — no blocker even if excluded.
    pool = [
        _resolved_ex(exercise_id="EX001", exercise_type="Aerobic / Endurance"),
        _resolved_ex(exercise_id="EX002", exercise_type="Interval / Tempo"),
        _resolved_ex(exercise_id="EX003", exercise_type="Technical / Skill"),
    ]
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2c_payloads={"home": _layer2c(exercises_resolved=pool)},
        layer2d_payload=_layer2d(),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert [it for it in gate.items if it.source_item_id == "injury_pool_empty"] == []


# TS-3D-6 — all-running-banned removes a discipline's only cardio modality.
def test_ts3d6_cardio_modality_banned_blocks():
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2d_payload=_layer2d(
            discipline_risk_profiles=[_disc_risk(discipline_id="D-trail", name="trail_running")]
        ),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert gate.gate_status == "blocked"
    items = [it for it in gate.items if it.source_item_id == "cardio_modality_banned"]
    assert len(items) == 1
    it = items[0]
    assert it.source == "3D_feasibility"
    assert it.severity == "blocker"
    assert it.can_acknowledge is False
    assert it.revise_target == "profile.injuries"
    assert it.evidence["discipline_id"] == "D-trail"
    assert "trail_running" in it.title


def test_cardio_ban_with_usable_substitute_does_not_block():
    sub = SubstituteRecommendation(
        substitute_discipline_id="D-bike",
        substitute_name="cycling",
        fidelity=0.7,
        still_at_risk=False,
        still_at_risk_body_parts=[],
    )
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2d_payload=_layer2d(discipline_risk_profiles=[_disc_risk(substitutes=[sub])]),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert gate.gate_status == "green"
    assert [it for it in gate.items if it.source == "3D_feasibility"] == []


def test_cardio_ban_not_for_non_included_or_non_high_discipline():
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2d_payload=_layer2d(
            discipline_risk_profiles=[
                _disc_risk(discipline_id="D-other", risk_level="high"),  # not included in 2A
                _disc_risk(discipline_id="D-trail", risk_level="elevated"),  # included but not high
            ]
        ),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert [it for it in gate.items if it.source == "3D_feasibility"] == []


def test_cardio_ban_suppressed_when_2d_hitl_already_covers_it():
    gate = _evaluate(
        layer2a_payload=_layer2a(disciplines=[_discipline()]),
        layer2d_payload=_layer2d(
            discipline_risk_profiles=[_disc_risk(discipline_id="D-trail")],
            hitl_items=[
                _2d_item(hitl_type="no_substitute_for_high_risk", severity="block", discipline_id="D-trail")
            ],
        ),
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    # 2D already surfaced the finding (source 2D); 3D does not double-show it.
    assert [it for it in gate.items if it.source_item_id == "cardio_modality_banned"] == []
    twod = [it for it in gate.items if it.source == "2D"]
    assert len(twod) == 1
    assert gate.gate_status == "blocked"  # the 2D blocker still blocks


# TS-3D-7 — available 4 h/wk vs Build 10–12 h → warning → acknowledge → green.
def _schedule_inputs():
    l2a = _layer2a(
        disciplines=[_discipline()],
        weekly_total_hours_by_phase={
            "Base": (5.0, 8.0),
            "Build": (10.0, 12.0),
            "Peak": (8.0, 10.0),
            "Taper": (4.0, 6.0),
        },
    )
    l1 = {
        "daily_availability_windows": [
            {"enabled": True, "window_duration": 240, "second_window_duration": 0}
        ],
        "identity": {"weekly_hours_target": 10},
    }
    return l2a, l1


def test_ts3d7_schedule_under_target_warns():
    l2a, l1 = _schedule_inputs()
    gate = _evaluate(
        layer2a_payload=l2a,
        layer1_payload=l1,
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert gate.gate_status == "needs_review"
    assert len(gate.items) == 1
    it = gate.items[0]
    assert it.source == "3D_feasibility"
    assert it.source_item_id == "schedule_volume_under_target"
    assert it.severity == "warning"
    assert it.can_acknowledge is True
    assert it.revise_target == "profile.availability"
    assert it.evidence["headline_phase"] == "Build"  # highest target low edge
    assert "10" in it.message and "12" in it.message
    assert {p["phase"] for p in it.evidence["phases"]} == {"Base", "Build", "Peak"}


def test_ts3d7_acknowledge_goes_green():
    l2a, l1 = _schedule_inputs()
    key = make_item_key("3D_feasibility", "schedule_volume_under_target", "schedule")
    res = GateResolution(kind="acknowledged", resolved_at=datetime(2026, 6, 1, 12, 0, 0))
    gate = _evaluate(
        layer2a_payload=l2a,
        layer1_payload=l1,
        plan_start_date=_PLAN_START,
        total_weeks=20,
        prior_resolutions={key: res},
    )
    assert gate.gate_status == "green"
    assert gate.items[0].status == "acknowledged"


def test_schedule_no_warning_when_capacity_meets_target():
    l2a, _ = _schedule_inputs()
    l1 = {
        "daily_availability_windows": [
            {"enabled": True, "window_duration": 600, "second_window_duration": 300}
        ],
        "identity": {"weekly_hours_target": 15},
    }  # 15 h/wk available ≥ every phase low edge
    gate = _evaluate(
        layer2a_payload=l2a,
        layer1_payload=l1,
        plan_start_date=_PLAN_START,
        total_weeks=20,
    )
    assert gate.gate_status == "green"
    assert [it for it in gate.items if it.source == "3D_feasibility"] == []
