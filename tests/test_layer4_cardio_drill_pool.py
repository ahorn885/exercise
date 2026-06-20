"""#698 Track 2 (A2) — the cardio drill pool: deterministic compute, grouped
render, and the enum-bound tool schema.

Covers `compute_cardio_drill_pool_ids` (type allowlist, 2D exclusion, discipline
match, the constituent-sport gate on EX175/EX176, character-keyed phase
periodization, deterministic order, empty pool), `_format_cardio_drill_pool`
(discipline grouping, coaching_cue dose, character tag, cap, dedup), the
`# Cardio drills` system-prompt section, and the `cardio_drills` tool-schema
enum-bind + maxItems:1 cap.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from layer4.per_phase import (
    SYSTEM_PROMPT,
    _CARDIO_DRILL_POOL_CAP,
    build_record_phase_sessions_tool,
    compute_cardio_drill_pool_ids,
    _format_cardio_drill_pool,
)


def _rx(exercise_id, name, disciplines, *, exercise_type="Interval / Tempo",
        priorities=None, coaching_cue=None, tier=1):
    return NS(
        exercise_id=exercise_id,
        exercise_name=name,
        exercise_type=exercise_type,
        discipline_ids=list(disciplines),
        priority_per_discipline=dict(priorities or {}),
        coaching_cue=coaching_cue,
        # tier defaults to 1 (feasible); the pool fns now drop tier-0 (#691).
        tier=tier,
    )


def _l2c(locale_id, resolved):
    return NS(locale_id=locale_id, exercises_resolved=resolved)


def _l2a(weights, names=None):
    names = names or {}
    return NS(disciplines=[
        NS(discipline_id=d, discipline_name=names.get(d, d),
           inclusion="included", load_weight=NS(value=w))
        for d, w in weights.items()
    ])


def _l2d(excluded_ids):
    return NS(excluded_exercises=[NS(exercise_id=i) for i in excluded_ids])


# ─── compute_cardio_drill_pool_ids ───────────────────────────────────────────


def test_compute_keeps_only_drill_types():
    pool = {"loc": _l2c("loc", [
        _rx("EX073", "Threshold Bike", ["D-006"], exercise_type="Interval / Tempo"),
        _rx("EX120", "Sustained LISS", ["D-006"], exercise_type="Aerobic / Endurance"),
        _rx("EX070", "Single-Leg Cycling", ["D-006"], exercise_type="Technical / Skill"),
        _rx("EX001", "Back Squat", ["D-006"], exercise_type="Strength"),
        _rx("EX-MOB", "Foam Roll", ["D-006"], exercise_type="Mobility"),
    ])}
    ids = compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Base"
    )
    assert ids == ["EX070", "EX073", "EX120"]  # sorted; strength + mobility dropped


# #691 — tier 0 = equipment-infeasible with no substitute/proxy; a drill that
# needs gear the athlete lacks must not enter the pool or the rendered menu.
def test_compute_excludes_tier0():
    pool = {"loc": _l2c("loc", [
        _rx("EX073", "Threshold Bike", ["D-006"], tier=1),
        _rx("EX-GONE", "Erg Intervals", ["D-006"], tier=0),  # no erg, no sub
    ])}
    ids = compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Base"
    )
    assert ids == ["EX073"]


def test_render_excludes_tier0():
    pool = {"loc": _l2c("loc", [
        _rx("EX073", "Threshold Bike", ["D-006"], tier=1, coaching_cue="Z4 4x4"),
        _rx("EX-GONE", "Erg Intervals", ["D-006"], tier=0),
    ])}
    text = "\n".join(_format_cardio_drill_pool(
        pool, _l2a({"D-006": 1.0}), None, disciplines={"D-006"}, phase="Base"
    ))
    assert "EX073" in text
    assert "EX-GONE" not in text


def test_compute_discipline_match_required():
    pool = {"loc": _l2c("loc", [
        _rx("EX073", "Threshold Bike", ["D-006"]),
        _rx("EX291", "Swim CSS", ["D-004"]),
    ])}
    ids = compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Base"
    )
    assert ids == ["EX073"]  # swim drill not matched by a cycling-only athlete


def test_compute_drops_2d_excluded():
    pool = {"loc": _l2c("loc", [
        _rx("EX288", "Treadwall", ["D-012"]),
        _rx("EX073", "Threshold Bike", ["D-012"]),
    ])}
    ids = compute_cardio_drill_pool_ids(
        pool, _l2d(["EX288"]), disciplines={"D-012"}, phase="Base"
    )
    assert ids == ["EX073"]  # wrist-excluded Treadwall dropped (Andy's 2D case)


def test_constituent_sport_gate_requires_cycling_and_running():
    pool = {"loc": _l2c("loc", [
        _rx("EX175", "Brick Run", ["D-001", "D-006"], exercise_type="Technical / Skill"),
        _rx("EX176", "Tri Transition", ["D-006"], exercise_type="Technical / Skill"),
    ])}
    # Has running (D-001) + cycling (D-006) → both included.
    both = compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-001", "D-006"}, phase="Base"
    )
    assert both == ["EX175", "EX176"]
    # Cycling only (no running) → both gated out.
    cyc_only = compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Base"
    )
    assert cyc_only == []


def test_constituent_gate_filters_paddle_climb_ar_athlete():
    """An AR athlete matching EX175 only via a broad composite, with no
    cycling+running pair, does not get the brick drill."""
    pool = {"loc": _l2c("loc", [
        _rx("EX175", "Brick Run", ["D-009", "D-012"], exercise_type="Technical / Skill"),
        _rx("EX090", "Paddling Erg", ["D-009"], exercise_type="Aerobic / Endurance"),
    ])}
    ids = compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-009", "D-012"}, phase="Base"
    )
    assert ids == ["EX090"]  # paddle erg keeps; brick gated out


def test_phase_periodization_by_character():
    pool = {"loc": _l2c("loc", [
        _rx("EX070", "Single-Leg Cycling", ["D-006"], exercise_type="Technical / Skill"),
        _rx("EX073", "Threshold Bike", ["D-006"], exercise_type="Interval / Tempo"),
    ])}
    # Base/Build keep the skill drill; Peak/Taper drop it. Interval always kept.
    assert compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Base") == ["EX070", "EX073"]
    assert compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Build") == ["EX070", "EX073"]
    assert compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Peak") == ["EX073"]
    assert compute_cardio_drill_pool_ids(
        pool, None, disciplines={"D-006"}, phase="Taper") == ["EX073"]


def test_compute_empty_inputs():
    assert compute_cardio_drill_pool_ids(
        {}, None, disciplines={"D-006"}, phase="Base") == []
    pool = {"loc": _l2c("loc", [_rx("EX073", "Threshold Bike", ["D-006"])])}
    assert compute_cardio_drill_pool_ids(
        pool, None, disciplines=set(), phase="Base") == []


# ─── _format_cardio_drill_pool ───────────────────────────────────────────────


def test_render_groups_by_discipline_with_cue_and_character_tag():
    pool = {"loc": _l2c("loc", [
        _rx("EX290", "Flat VO2max Run", ["D-001"], priorities={"D-001": "Critical"},
            coaching_cue="3-5 min reps at ~95-100% vVO2max"),
        _rx("EX070", "Single-Leg Cycling", ["D-006"], priorities={"D-006": "High"},
            exercise_type="Technical / Skill"),
    ])}
    l2a = _l2a({"D-001": 0.6, "D-006": 0.4},
               names={"D-001": "Trail Running", "D-006": "Road Cycling"})
    lines = _format_cardio_drill_pool(
        pool, l2a, None, disciplines={"D-001", "D-006"}, phase="Base"
    )
    text = "\n".join(lines)
    assert "- Trail Running:" in text
    assert "- Road Cycling:" in text
    # interval row carries its dose + the follow-phase tag
    assert ("EX290 (Flat VO2max Run) — 3-5 min reps at ~95-100% vVO2max "
            "[interval — follow phase intent]") in text
    # skill row gets the Base-tool tag (no cue → no dash segment)
    assert "EX070 (Single-Leg Cycling) [transition/skill — Base tool, fades to race]" in text
    # discipline order follows load weight (running 0.6 before cycling 0.4)
    assert text.index("Trail Running") < text.index("Road Cycling")


def test_render_dedupes_across_disciplines_and_caps():
    resolved = [
        _rx(f"EX{n:03d}", f"Drill {n}", ["D-006"], priorities={"D-006": "High"})
        for n in range(20)
    ]
    pool = {"loc": _l2c("loc", resolved)}
    lines = _format_cardio_drill_pool(
        pool, _l2a({"D-006": 1.0}), None, disciplines={"D-006"}, phase="Base"
    )
    rows = [ln for ln in lines if ln.strip().startswith("- EX")]
    assert len(rows) == _CARDIO_DRILL_POOL_CAP  # capped at 12


def test_render_empty_when_nothing_resolves():
    assert _format_cardio_drill_pool(
        {}, None, None, disciplines={"D-006"}, phase="Base") == []


# ─── tool schema enum-bind + cap ─────────────────────────────────────────────


def _cardio_drills_schema(tool):
    return (tool["input_schema"]["properties"]["sessions"]["items"]
            ["properties"]["cardio_drills"])


def test_schema_binds_enum_and_caps_at_one():
    tool = build_record_phase_sessions_tool(cardio_drill_pool_ids=["EX073", "EX290"])
    cd = _cardio_drills_schema(tool)
    assert cd["maxItems"] == 1
    assert cd["items"]["properties"]["exercise_id"]["enum"] == ["EX073", "EX290"]


def test_schema_free_string_when_pool_empty():
    tool = build_record_phase_sessions_tool(cardio_drill_pool_ids=None)
    cd = _cardio_drills_schema(tool)
    assert cd["maxItems"] == 1
    assert cd["items"]["properties"]["exercise_id"] == {"type": "string"}
    assert "enum" not in cd["items"]["properties"]["exercise_id"]


# ─── system prompt ───────────────────────────────────────────────────────────


def test_system_prompt_has_cardio_drills_section():
    assert "# Cardio drills" in SYSTEM_PROMPT
    assert "=== Cardio drill pool (consider these) ===" in SYSTEM_PROMPT
    assert "At most one drill per session" in SYSTEM_PROMPT
