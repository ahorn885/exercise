"""#335 Phase 2 — the strength exercise-surface rendering that stops the
synthesizer flying blind.

Before this, `render_user_prompt` told the model only `effective_pool size=N`
(a count), so it invented `exercise_id`s and validator Rule 6a rejected every
one as `equipment_unavailable` — even for gear the athlete owns. These cover the
pure `_format_strength_exercise_pool` helper (duck-typed fakes — it only does
attribute access): id rendering, priority + movement-pattern ranking, the
priority-driven core/accessory split, 2D exclusion, cap, dedup, tier notes —
plus the `# Strength programming` system-prompt section.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from layer4.per_phase import (
    SYSTEM_PROMPT,
    _STRENGTH_CORE_CAP,
    _STRENGTH_POOL_CAP_PER_DISCIPLINE,
    _format_skill_capability_gates,
    _format_strength_exercise_pool,
)


def _rx(exercise_id, name, disciplines, priorities, tier=1, patterns=(), detail=None):
    return NS(
        exercise_id=exercise_id,
        exercise_name=name,
        discipline_ids=list(disciplines),
        priority_per_discipline=dict(priorities),
        movement_patterns=list(patterns),
        tier=tier,
        resolution_detail=detail,
    )


def _l2c(locale_id, resolved):
    return NS(locale_id=locale_id, exercises_resolved=resolved)


def _l2a(weights):
    return NS(disciplines=[
        NS(discipline_id=d, inclusion="included", load_weight=NS(value=w))
        for d, w in weights.items()
    ])


def _l2d(excluded_ids):
    return NS(excluded_exercises=[NS(exercise_id=i) for i in excluded_ids])


def test_renders_resolved_ids_with_role_pattern_priority():
    pool = {"home": _l2c("home", [
        _rx("EX-001", "Goblet Squat", ["D-003"], {"D-003": "Critical"},
            patterns=["Squat"]),
        _rx("EX-002", "RDL", ["D-003"], {"D-003": "High"}, patterns=["Hinge"]),
    ])}
    lines = _format_strength_exercise_pool(pool, _l2a({"D-003": 0.5}), None)
    text = "\n".join(lines)
    assert "- Locale home:" in text
    assert "D-003:" in text
    # Real resolved ids present (the model picks them verbatim), with the
    # data-driven core tag (Critical/High + compound pattern), pattern, priority.
    assert "EX-001 (Goblet Squat) [core; Tier 1; Critical; Squat]" in text
    assert "EX-002 (RDL) [core; Tier 1; High; Hinge]" in text


def test_preferred_pattern_breaks_ties_at_equal_priority():
    pool = {"home": _l2c("home", [
        _rx("EX-PLAIN", "Plain", ["D-003"], {"D-003": "High"}, patterns=["Push"]),
        _rx("EX-UNI", "Single-leg", ["D-003"], {"D-003": "High"},
            patterns=["Single-Leg"]),
    ])}
    lines = _format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None)
    order = [ln for ln in lines if ln.strip().startswith("- EX")]
    # Same priority → the preferred (Single-Leg) pattern ranks first.
    assert order[0].startswith("  - EX-UNI")
    assert order[1].startswith("  - EX-PLAIN")


def test_core_requires_compound_pattern_and_high_priority():
    pool = {"home": _l2c("home", [
        # High priority but NOT a compound pattern → accessory, not core.
        _rx("EX-CARRY", "Carry", ["D-003"], {"D-003": "High"}, patterns=["Carry"]),
        # Medium priority compound → not core (priority too low).
        _rx("EX-MEDSQ", "Med Squat", ["D-003"], {"D-003": "Medium"},
            patterns=["Squat"]),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    assert "EX-CARRY (Carry) [accessory" in text
    assert "EX-MEDSQ (Med Squat) [accessory" in text


def test_core_capped():
    many = [
        _rx(f"EX-{i:03d}", f"Sq{i}", ["D-003"], {"D-003": "Critical"},
            patterns=["Squat"])
        for i in range(_STRENGTH_CORE_CAP + 3)
    ]
    pool = {"home": _l2c("home", many)}
    lines = _format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None)
    core_lines = [ln for ln in lines if "[core;" in ln]
    assert len(core_lines) == _STRENGTH_CORE_CAP


def test_2d_excluded_dropped():
    pool = {"home": _l2c("home", [
        _rx("EX-OK", "Ok", ["D-003"], {"D-003": "High"}, patterns=["Hinge"]),
        _rx("EX-BAD", "Wrist Loader", ["D-003"], {"D-003": "Critical"},
            patterns=["Push"]),
    ])}
    text = "\n".join(_format_strength_exercise_pool(
        pool, _l2a({"D-003": 1.0}), _l2d(["EX-BAD"])
    ))
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
    pool = {"home": _l2c("home", [
        _rx("EX-SHARED", "Shared", ["D-003", "D-009"],
            {"D-003": "High", "D-009": "Critical"}, patterns=["Hinge"]),
        _rx("EX-ONLY9", "Only9", ["D-009"], {"D-009": "High"}, patterns=["Squat"]),
    ])}
    text = "\n".join(_format_strength_exercise_pool(
        pool, _l2a({"D-003": 0.7, "D-009": 0.3}), None
    ))
    assert text.count("EX-SHARED") == 1
    assert text.index("D-003:") < text.index("EX-SHARED")


def test_empty_discipline_renders_nothing():
    assert _format_strength_exercise_pool({"home": _l2c("home", [])}, None, None) == []


def test_tier2_substitute_and_tier3_proxy_notes():
    pool = {"home": _l2c("home", [
        _rx("EX-SUB", "Sub", ["D-003"], {"D-003": "High"}, tier=2,
            patterns=["Hinge"],
            detail=NS(substitute_text="band good-morning", proxy_exercise_id=None)),
        _rx("EX-PROX", "Prox", ["D-003"], {"D-003": "Medium"}, tier=3,
            patterns=["Carry"],
            detail=NS(substitute_text=None, proxy_exercise_id="EX-CANON")),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    # Tier 2/3 are not core (tier-1-only via the compound+priority gate here
    # they're High/Medium, but the substitute/proxy note is what we assert).
    assert "substitute: band good-morning" in text
    assert "proxy: EX-CANON" in text


def test_no_layer2c_returns_empty():
    assert _format_strength_exercise_pool({}, _l2a({"D-003": 1.0}), None) == []


# ─── #336 skill-capability gate substitution directive ──────────────────────


def _l2c_with_skill_flag(locale_id, discipline_id, toggle_name):
    flag = NS(
        flag_type="requires_skill_capability",
        discipline_id=discipline_id,
        metadata={"toggle_name": toggle_name},
    )
    return NS(locale_id=locale_id, exercises_resolved=[], coaching_flags=[flag])


def _l2a_named(names):
    return NS(disciplines=[
        NS(discipline_id=d, discipline_name=n, inclusion="included",
           load_weight=NS(value=0.5))
        for d, n in names.items()
    ])


def test_skill_gates_render_substitution_directive():
    pool = {"home": _l2c_with_skill_flag("home", "D-012", "climbing_roped")}
    text = "\n".join(
        _format_skill_capability_gates(pool, _l2a_named({"D-012": "Rock Climbing"}))
    )
    assert "Skill-capability gates" in text
    assert "kind='strength'" in text
    assert "Rock Climbing (D-012)" in text
    assert "climbing_roped" in text


def test_skill_gates_empty_when_nothing_gated():
    pool = {"home": NS(locale_id="home", exercises_resolved=[], coaching_flags=[])}
    assert _format_skill_capability_gates(pool, _l2a_named({"D-012": "Rock Climbing"})) == []


def test_skill_gates_falls_back_to_id_without_2a():
    pool = {"home": _l2c_with_skill_flag("home", "D-012", "climbing_roped")}
    text = "\n".join(_format_skill_capability_gates(pool, None))
    assert "D-012" in text


def test_system_prompt_has_strength_section_and_no_invent_rule():
    assert "# Strength programming" in SYSTEM_PROMPT
    assert "never invent `exercise_id`s" in SYSTEM_PROMPT
    assert "=== Strength exercise pool ===" in SYSTEM_PROMPT
    assert "RM/RPE" in SYSTEM_PROMPT
    # Track 2 slice 2b: session counts moved to the deterministic grid;
    # the prompt now references the grid rather than hardcoded "2 sessions/week".
    assert "session grid" in SYSTEM_PROMPT.lower()
