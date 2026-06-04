"""#335 Phase 2 Slice 1 — the strength exercise-surface rendering that stops the
synthesizer flying blind.

Before this, `render_user_prompt` told the model only `effective_pool size=N`
(a count), so it invented `exercise_id`s and validator Rule 6a rejected every
one as `equipment_unavailable` — even for gear the athlete owns. These cover the
pure `_format_strength_exercise_pool` helper (duck-typed fakes — it only does
attribute access) + the `# Strength programming` system-prompt section.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from layer4.per_phase import (
    SYSTEM_PROMPT,
    _STRENGTH_POOL_CAP_PER_DISCIPLINE,
    _format_strength_exercise_pool,
)


def _rx(exercise_id, name, disciplines, priorities, tier=1, detail=None):
    return NS(
        exercise_id=exercise_id,
        exercise_name=name,
        discipline_ids=list(disciplines),
        priority_per_discipline=dict(priorities),
        tier=tier,
        resolution_detail=detail,
    )


def _l2c(locale_id, resolved):
    return NS(locale_id=locale_id, exercises_resolved=resolved)


def _l2a(weights):
    # weights: {discipline_id: load_weight} -> included disciplines
    return NS(disciplines=[
        NS(discipline_id=d, inclusion="included", load_weight=NS(value=w))
        for d, w in weights.items()
    ])


def _l2d(excluded_ids):
    return NS(excluded_exercises=[NS(exercise_id=i) for i in excluded_ids])


def test_renders_resolved_ids_grouped_by_discipline():
    pool = {"home": _l2c("home", [
        _rx("EX-001", "Goblet Squat", ["D-003"], {"D-003": "Critical"}),
        _rx("EX-002", "RDL", ["D-003"], {"D-003": "High"}),
    ])}
    lines = _format_strength_exercise_pool(pool, _l2a({"D-003": 0.5}), None)
    text = "\n".join(lines)
    assert "- Locale home:" in text
    assert "D-003:" in text
    # Real resolved ids are present so the model can pick them verbatim.
    assert "EX-001 (Goblet Squat) [Tier 1; Critical]" in text
    assert "EX-002 (RDL) [Tier 1; High]" in text


def test_ranks_critical_before_high_before_medium():
    pool = {"home": _l2c("home", [
        _rx("EX-MED", "Med", ["D-003"], {"D-003": "Medium"}),
        _rx("EX-CRIT", "Crit", ["D-003"], {"D-003": "Critical"}),
        _rx("EX-HIGH", "High", ["D-003"], {"D-003": "High"}),
    ])}
    lines = _format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None)
    order = [ln for ln in lines if ln.strip().startswith("- EX")]
    assert order[0].startswith("  - EX-CRIT")
    assert order[1].startswith("  - EX-HIGH")
    assert order[2].startswith("  - EX-MED")


def test_2d_excluded_dropped():
    pool = {"home": _l2c("home", [
        _rx("EX-OK", "Ok", ["D-003"], {"D-003": "High"}),
        _rx("EX-BAD", "Wrist Loader", ["D-003"], {"D-003": "Critical"}),
    ])}
    lines = _format_strength_exercise_pool(
        pool, _l2a({"D-003": 1.0}), _l2d(["EX-BAD"])
    )
    text = "\n".join(lines)
    assert "EX-OK" in text
    assert "EX-BAD" not in text  # injury-excluded never offered to the model


def test_capped_per_discipline():
    many = [
        _rx(f"EX-{i:03d}", f"Ex{i}", ["D-003"], {"D-003": "High"})
        for i in range(_STRENGTH_POOL_CAP_PER_DISCIPLINE + 5)
    ]
    pool = {"home": _l2c("home", many)}
    lines = _format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None)
    rendered = [ln for ln in lines if ln.strip().startswith("- EX")]
    assert len(rendered) == _STRENGTH_POOL_CAP_PER_DISCIPLINE


def test_deduped_across_disciplines_under_highest_weight():
    # EX-SHARED serves both; D-003 has the higher 2A load weight, so it lists
    # there and is NOT repeated under D-009.
    pool = {"home": _l2c("home", [
        _rx("EX-SHARED", "Shared", ["D-003", "D-009"],
            {"D-003": "High", "D-009": "Critical"}),
        _rx("EX-ONLY9", "Only9", ["D-009"], {"D-009": "High"}),
    ])}
    lines = _format_strength_exercise_pool(
        pool, _l2a({"D-003": 0.7, "D-009": 0.3}), None
    )
    text = "\n".join(lines)
    assert text.count("EX-SHARED") == 1
    # D-003 renders first (higher weight) and owns the shared exercise.
    assert text.index("D-003:") < text.index("EX-SHARED")


def test_empty_discipline_renders_nothing():
    # A discipline with zero resolved exercises (e.g. MTB/Climbing) produces no
    # section and no blocker.
    assert _format_strength_exercise_pool({"home": _l2c("home", [])}, None, None) == []


def test_tier2_substitute_and_tier3_proxy_notes():
    pool = {"home": _l2c("home", [
        _rx("EX-SUB", "Sub", ["D-003"], {"D-003": "High"}, tier=2,
            detail=NS(substitute_text="band good-morning", proxy_exercise_id=None)),
        _rx("EX-PROX", "Prox", ["D-003"], {"D-003": "Medium"}, tier=3,
            detail=NS(substitute_text=None, proxy_exercise_id="EX-CANON")),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    assert "[Tier 2; High; substitute: band good-morning]" in text
    assert "[Tier 3; Medium; proxy: EX-CANON]" in text


def test_no_layer2c_returns_empty():
    assert _format_strength_exercise_pool({}, _l2a({"D-003": 1.0}), None) == []


def test_system_prompt_has_strength_section_and_no_invent_rule():
    assert "# Strength programming" in SYSTEM_PROMPT
    # The load-bearing instruction: pick from the rendered pool, never invent.
    assert "never invent `exercise_id`s" in SYSTEM_PROMPT
    assert "=== Strength exercise pool ===" in SYSTEM_PROMPT
    # Dose + RM/RPE guidance present (no absolute weights).
    assert "RM/RPE" in SYSTEM_PROMPT
    assert "2 sessions/week" in SYSTEM_PROMPT
