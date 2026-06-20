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

from datetime import date, timedelta
from types import SimpleNamespace as NS

from layer4.per_phase import (
    SYSTEM_PROMPT,
    _RECOVERY_POOL_CAP,
    _STRENGTH_CORE_CAP,
    _STRENGTH_POOL_CAP_PER_DISCIPLINE,
    compute_feasible_pool_ids,
    compute_recovery_pool_ids,
    _format_recovery_exercise_pool,
    _format_recovery_programming,
    _format_skill_capability_gates,
    _format_strength_exercise_pool,
)


def _rx(exercise_id, name, disciplines, priorities, tier=1, patterns=(), detail=None,
        exercise_type="Strength"):
    return NS(
        exercise_id=exercise_id,
        exercise_name=name,
        exercise_type=exercise_type,
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


# ─── #698 Finding 2 — strength-type filter (cardio/skill rows can't leak) ────


def test_rendered_pool_drops_non_strength_types():
    pool = {"home": _l2c("home", [
        _rx("EX-LIFT", "Goblet Squat", ["D-006"], {"D-006": "High"},
            patterns=["Squat"], exercise_type="Strength"),
        # A cycling cardio drill mapped to the same discipline — must NOT render.
        _rx("EX-CARDIO", "Threshold Intervals (Bike)", ["D-006"],
            {"D-006": "Critical"}, exercise_type="Interval / Tempo"),
        _rx("EX-SKILL", "High Cadence Spin Drill", ["D-006"],
            {"D-006": "Critical"}, exercise_type="Technical / Skill"),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-006": 1.0}), None))
    assert "EX-LIFT" in text
    assert "EX-CARDIO" not in text
    assert "EX-SKILL" not in text


def test_rendered_pool_keeps_resistance_modalities():
    # Loaded Carry / Plyometric / Isometric are real strength work and stay in.
    pool = {"home": _l2c("home", [
        _rx("EX-CARRY", "Farmer Carry", ["D-003"], {"D-003": "High"},
            exercise_type="Loaded Carry"),
        _rx("EX-JUMP", "Box Jump", ["D-003"], {"D-003": "High"},
            exercise_type="Plyometric"),
        _rx("EX-ISO", "Wall Sit", ["D-003"], {"D-003": "High"},
            exercise_type="Isometric"),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    assert "EX-CARRY" in text
    assert "EX-JUMP" in text
    assert "EX-ISO" in text


def test_rendered_pool_keeps_athletic_development_types():
    # Andy 2026-06-17: agility / activation / balance count as strength-session
    # work and belong in the strength pool.
    pool = {"home": _l2c("home", [
        _rx("EX-AGI", "Agility Ladder Drill", ["D-003"], {"D-003": "High"},
            exercise_type="Agility"),
        _rx("EX-ACT", "Band Pull-Apart", ["D-003"], {"D-003": "High"},
            exercise_type="Activation / Primer"),
        _rx("EX-BAL", "Single-Leg Balance Hold", ["D-003"], {"D-003": "High"},
            exercise_type="Balance / Proprioception"),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    assert "EX-AGI" in text
    assert "EX-ACT" in text
    assert "EX-BAL" in text


def test_type_match_is_case_insensitive():
    # Real prod values are title-case ("Strength"); a lowercase fixture must
    # still resolve (mirrors the movement-pattern case-insensitive match).
    pool = {"home": _l2c("home", [
        _rx("EX-LC", "Squat", ["D-003"], {"D-003": "High"}, exercise_type="strength"),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    assert "EX-LC" in text


def test_compute_feasible_pool_ids_excludes_non_strength_types():
    pool = {"home": _l2c("home", [
        _rx("EX-LIFT", "Squat", ["D-006"], {"D-006": "High"},
            exercise_type="Strength"),
        _rx("EX-CARDIO", "VO2 Max Intervals (Bike)", ["D-006"], {"D-006": "High"},
            exercise_type="Interval / Tempo"),
    ])}
    ids = compute_feasible_pool_ids(pool, None)
    assert ids == ["EX-LIFT"]


# ─── #691 — tier-0 (equipment-infeasible) exclusion from the feasible pool ───
#
# Tier 0 = the athlete lacks the required equipment AND there's no resolvable
# substitute (tier 2) or proxy (tier 3) — not prescribable. Such a row must
# appear in NEITHER the SDK enum (`compute_feasible_pool_ids`, the sole strength-
# membership guard since validator Rule 6a retired) NOR the rendered menu. This
# is the gate leak #691 reported: a sled drag offered to an athlete with no sled.


def test_compute_feasible_pool_ids_excludes_tier0():
    pool = {"home": _l2c("home", [
        _rx("EX-OK", "Goblet Squat", ["D-003"], {"D-003": "High"}, tier=1),
        _rx("EX-SUB", "Reverse Sled Drag", ["D-003"], {"D-003": "High"}, tier=2),
        # No sled, no substitute, no proxy → tier 0 → never prescribable.
        _rx("EX-GONE", "Barbell Hip Thrust", ["D-003"], {"D-003": "Critical"},
            tier=0),
    ])}
    ids = compute_feasible_pool_ids(pool, None)
    assert ids == ["EX-OK", "EX-SUB"]
    assert "EX-GONE" not in ids


def test_rendered_strength_pool_excludes_tier0():
    pool = {"home": _l2c("home", [
        _rx("EX-OK", "Goblet Squat", ["D-003"], {"D-003": "High"}, tier=1,
            patterns=["Squat"]),
        _rx("EX-GONE", "Sled Drag", ["D-003"], {"D-003": "Critical"}, tier=0,
            patterns=["Hinge"]),
    ])}
    text = "\n".join(_format_strength_exercise_pool(pool, _l2a({"D-003": 1.0}), None))
    assert "EX-OK" in text
    # The infeasible tier-0 row is never rendered (it would otherwise show as
    # "Tier 0" with no "Do instead" substitute — the exact #691 symptom).
    assert "EX-GONE" not in text
    assert "Tier 0" not in text


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


# ─── #698 Track 1 (Slice 2) — recovery pool + dose + prompt ──────────────────


def _l2c_recovery(locale_id, resolved):
    return NS(locale_id=locale_id, exercises_resolved=resolved)


def test_compute_recovery_pool_ids_keeps_only_recovery_types():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-MOB", "Hip 90/90", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility"),
        _rx("EX-FLEX", "Hamstring Stretch", ["D-003"], {"D-003": "High"},
            exercise_type="Flexibility / Stretching"),
        _rx("EX-SOFT", "Foam Roll Quads", ["D-003"], {"D-003": "High"},
            exercise_type="Recovery / Soft Tissue"),
        _rx("EX-BREATH", "Box Breathing", ["D-003"], {"D-003": "High"},
            exercise_type="Breathwork"),
        # Strength + cardio rows must NOT leak into the recovery pool.
        _rx("EX-LIFT", "Squat", ["D-003"], {"D-003": "High"},
            exercise_type="Strength"),
        _rx("EX-CARDIO", "Threshold Intervals", ["D-003"], {"D-003": "High"},
            exercise_type="Interval / Tempo"),
    ])}
    ids = compute_recovery_pool_ids(pool, None)
    assert ids == ["EX-BREATH", "EX-FLEX", "EX-MOB", "EX-SOFT"]


def test_compute_recovery_pool_ids_drops_2d_excluded():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-MOB", "Wrist Circles", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility"),
        _rx("EX-OK", "Ankle Mobility", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility"),
    ])}
    ids = compute_recovery_pool_ids(pool, _l2d(["EX-MOB"]))
    assert ids == ["EX-OK"]  # wrist-contraindicated mobility never offered


def test_compute_recovery_pool_ids_case_insensitive_and_empty():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-LC", "Mobility Flow", ["D-003"], {"D-003": "High"},
            exercise_type="mobility"),
    ])}
    assert compute_recovery_pool_ids(pool, None) == ["EX-LC"]
    assert compute_recovery_pool_ids({}, None) == []


def test_recovery_pool_render_lists_ids_and_drops_non_recovery():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-MOB", "Hip 90/90", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility"),
        _rx("EX-LIFT", "Squat", ["D-003"], {"D-003": "High"},
            exercise_type="Strength"),
    ])}
    text = "\n".join(_format_recovery_exercise_pool(pool, None))
    assert "Recovery / mobility menu" in text
    assert "EX-MOB (Hip 90/90) [Mobility]" in text
    assert "EX-LIFT" not in text


def test_recovery_pool_render_dedups_and_caps():
    many = [
        _rx(f"EX-{i:03d}", f"Mob{i}", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility")
        for i in range(_RECOVERY_POOL_CAP + 5)
    ]
    # add a duplicate id across a second locale — must render once.
    pool = {
        "home": _l2c_recovery("home", many),
        "gym": _l2c_recovery("gym", [many[0]]),
    }
    lines = _format_recovery_exercise_pool(pool, None)
    rendered = [ln for ln in lines if ln.strip().startswith("- EX")]
    assert len(rendered) == _RECOVERY_POOL_CAP
    assert "\n".join(lines).count("EX-000") == 1


def test_recovery_pool_render_empty_when_no_recovery_types():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-LIFT", "Squat", ["D-003"], {"D-003": "High"},
            exercise_type="Strength"),
    ])}
    assert _format_recovery_exercise_pool(pool, None) == []


# #691 — the recovery pool has the same tier-0 leak class as strength. A
# recovery/mobility row needing equipment the athlete lacks (e.g. a foam roller),
# with no substitute, resolves tier 0 and must not be prescribable.
def test_compute_recovery_pool_ids_excludes_tier0():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-MOB", "Hip 90/90", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility", tier=1),
        _rx("EX-ROLL", "Foam Roll Quads", ["D-003"], {"D-003": "High"},
            exercise_type="Recovery / Soft Tissue", tier=0),
    ])}
    assert compute_recovery_pool_ids(pool, None) == ["EX-MOB"]


def test_recovery_pool_render_excludes_tier0():
    pool = {"home": _l2c_recovery("home", [
        _rx("EX-MOB", "Hip 90/90", ["D-003"], {"D-003": "High"},
            exercise_type="Mobility", tier=1),
        _rx("EX-ROLL", "Foam Roll Quads", ["D-003"], {"D-003": "High"},
            exercise_type="Recovery / Soft Tissue", tier=0),
    ])}
    text = "\n".join(_format_recovery_exercise_pool(pool, None))
    assert "EX-MOB" in text
    assert "EX-ROLL" not in text


# #698 Track 1 (Slice 3b, D6) — `_format_recovery_programming` now renders the
# EXACT assigned placement dates (not a per-week count) + suppresses on empty.
# Windows: Sat is the longest enabled window (→ long-session day); goal 7h with
# >7h available → capacity 7h, inside the Base band (5,10) → `moderate`.
def _l1_windows():
    durs = {"Mon": 60, "Tue": 60, "Wed": 60, "Thu": 60, "Fri": 60, "Sat": 180, "Sun": 60}
    return {
        "daily_availability_windows": [
            {"day_of_week": d, "enabled": True, "window_duration": durs[d]} for d in durs
        ],
        "identity": {"weekly_hours_target": 7.0},
    }


_L2A_BANDS = NS(weekly_total_hours_by_phase={"Base": (5.0, 10.0), "Peak": (6.0, 9.0)})


def _spec(phase_name="Base", start=date(2026, 4, 6), weeks=2):  # 2026-04-06 = Mon
    return NS(
        phase_name=phase_name,
        start_date=start,
        end_date=start + timedelta(days=weeks * 7 - 1),
        weeks=weeks,
    )


def test_recovery_programming_renders_assigned_dates():
    # phase_structure=None → is_deload_week_for False, so the base dose (3) holds.
    lines = _format_recovery_programming(
        None, _spec("Base", weeks=1), (1, 1), _l1_windows(), _L2A_BANDS, False
    )
    text = "\n".join(lines)
    assert "Recovery programming (deterministic — off the training cap)" in text
    assert "do NOT" in text  # the off-the-cap directive
    assert "place a recovery session on" in text
    assert "ASSIGNED" in text
    # moderate band excludes the long-session day (Sat 2026-04-11)…
    assert "2026-04-11" not in text
    # …and anchors the day AFTER the long day (Sun 2026-04-12).
    assert "2026-04-12" in text


def test_recovery_programming_peak_emits_full_rest_directive():
    lines = _format_recovery_programming(
        None, _spec("Peak", weeks=1), (1, 1), _l1_windows(), _L2A_BANDS, False
    )
    text = "\n".join(lines)
    assert "place a recovery session on" in text
    # D4 — Peak phase always carries the load-adaptive full-rest directive.
    assert "full rest is the protective default" in text
    # extreme band (Peak) keeps recovery off the long day (Sat 04-11) AND the
    # pre-key day before it (Fri 04-10).
    assert "2026-04-11" not in text
    assert "2026-04-10" not in text


def test_recovery_programming_suppressed_when_pool_empty():
    # Suppress-on-empty (§6.3) — no block when the recovery pool resolves empty.
    assert (
        _format_recovery_programming(
            None, _spec("Base"), (1, 2), _l1_windows(), _L2A_BANDS, True
        )
        == []
    )


def test_recovery_programming_unknown_phase_renders_nothing():
    # A phase with no defined recovery dose renders nothing (matches today).
    assert (
        _format_recovery_programming(
            None, _spec("Transition", weeks=3), (1, 3), _l1_windows(), _L2A_BANDS, False
        )
        == []
    )


def test_system_prompt_has_recovery_section():
    assert "# Recovery programming" in SYSTEM_PROMPT
    assert "=== Recovery exercise pool ===" in SYSTEM_PROMPT
    assert "do **not** count toward the ≤2/day training cap" in SYSTEM_PROMPT
    assert "recovery_exercises[]" in SYSTEM_PROMPT
