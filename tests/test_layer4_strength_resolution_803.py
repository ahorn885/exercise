"""#803 — deterministic strength resolution-tier assignment.

The `StrengthExercise` tier↔field contract (`payload._check_resolution_tier`:
tier 1 ⇒ substitute_text/proxy_origin_id both None; tier 2 ⇒ substitute_text
set; tier 3 ⇒ proxy_origin_id set) is a cross-field rule the synthesizer's JSON
tool schema can't express and the prompt only half-stated. So the LLM routinely
emitted a tier-1 (exact) pick WITH a stray `substitute_text` note →
`ValidationError` → Build block-fumble → the whole plan failed (pv76/pv77).

`_apply_strength_resolution` fixes this by overwriting the three fields from the
chosen `exercise_id`'s deterministic 2C resolution BEFORE `StrengthExercise(**e)`
construction. The helper lives in `per_phase` and is wired into all four
synthesis construction sites (per_phase / single_session / plan_refresh /
race_week_brief). These cover the helper directly (duck-typed 2C fakes — it only
does attribute access) plus the regression that the failing pv77 shape now
constructs.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from layer4.payload import StrengthExercise
from layer4.per_phase import _apply_strength_resolution, _strength_resolution_fields


def _detail(substitute_text=None, proxy_exercise_id=None):
    return NS(substitute_text=substitute_text, proxy_exercise_id=proxy_exercise_id)


def _rx(exercise_id, tier, *, substitute_text=None, proxy_exercise_id=None):
    detail = None
    if substitute_text is not None or proxy_exercise_id is not None:
        detail = _detail(substitute_text, proxy_exercise_id)
    return NS(exercise_id=exercise_id, tier=tier, resolution_detail=detail)


def _l2c(locale_id, resolved):
    return NS(locale_id=locale_id, exercises_resolved=list(resolved))


def _raw_strength(exercise_id, **overrides):
    """A strength-exercise dict shaped like the synthesizer's tool output."""
    base = {
        "exercise_id": exercise_id,
        "exercise_name": "Back Squat",
        # Intentionally the BUG shape by default: tier-1 with a stray
        # substitute_text — exactly what failed in pv77 (EX231/EX241).
        "resolution_tier": 1,
        "substitute_text": "single-arm grip front squat",
        "proxy_origin_id": None,
        "sets": 3,
        "reps_per_set": 5,
        "load_prescription": "RPE 7",
        "rest_between_sets_sec": 120,
        "instructions": "Brace and descend under control.",
        "coaching_flags": [],
    }
    base.update(overrides)
    return base


def _session(locale_id, strength_exercises, kind="strength"):
    return {"locale_id": locale_id, "kind": kind, "strength_exercises": strength_exercises}


# ─── _strength_resolution_fields ────────────────────────────────────────────


def test_fields_tier1_clears_substitute_and_proxy():
    assert _strength_resolution_fields(_rx("EX1", 1)) == (1, None, None)


def test_fields_tier2_sets_substitute_text():
    rx = _rx("EX1", 2, substitute_text="band good-morning")
    assert _strength_resolution_fields(rx) == (2, "band good-morning", None)


def test_fields_tier2_empty_string_substitute_is_kept_non_none():
    # 2C `_tier_2` can emit substitute_text="" (bodyweight-variant subs); "" is
    # non-None so it satisfies the tier-2 validator.
    rx = _rx("EX1", 2, substitute_text="")
    assert _strength_resolution_fields(rx) == (2, "", None)


def test_fields_tier3_sets_proxy_origin_id():
    rx = _rx("EX1", 3, proxy_exercise_id="EX-PROXY")
    assert _strength_resolution_fields(rx) == (3, None, "EX-PROXY")


def test_fields_tier0_degrades_to_exact():
    assert _strength_resolution_fields(_rx("EX1", 0)) == (1, None, None)


def test_fields_unknown_pick_degrades_to_exact():
    assert _strength_resolution_fields(None) == (1, None, None)


def test_fields_tier2_without_detail_degrades_to_exact():
    # Defensive: tier 2 but no substitute text available → exact, never an
    # invalid (tier 2, None) pair.
    assert _strength_resolution_fields(_rx("EX1", 2)) == (1, None, None)


# ─── _apply_strength_resolution (the pv77 regression) ───────────────────────


def test_tier1_pick_with_stray_substitute_is_normalized_and_constructs():
    """The exact pv77 failure: a tier-1 exact pick the LLM tagged with a
    substitute_text. After normalization it constructs without raising."""
    l2c = {"home": _l2c("home", [_rx("EX1", 1)])}
    sessions = [_session("home", [_raw_strength("EX1")])]

    notes = _apply_strength_resolution(sessions, l2c)

    e = sessions[0]["strength_exercises"][0]
    assert (e["resolution_tier"], e["substitute_text"], e["proxy_origin_id"]) == (1, None, None)
    assert notes == []
    # The whole point: this used to raise ValidationError here.
    StrengthExercise(**e)


def test_tier2_pick_gets_substitute_text_from_2c():
    l2c = {"home": _l2c("home", [_rx("EX2", 2, substitute_text="ring row")])}
    # LLM emitted it as tier-1/exact (wrong); 2C says it's a tier-2 substitute.
    sessions = [_session("home", [_raw_strength("EX2", substitute_text=None)])]

    _apply_strength_resolution(sessions, l2c)

    e = sessions[0]["strength_exercises"][0]
    assert (e["resolution_tier"], e["substitute_text"], e["proxy_origin_id"]) == (2, "ring row", None)
    StrengthExercise(**e)


def test_tier3_pick_gets_proxy_origin_id_from_2c():
    l2c = {"home": _l2c("home", [_rx("EX3", 3, proxy_exercise_id="EX-BW")])}
    sessions = [_session("home", [_raw_strength("EX3")])]

    _apply_strength_resolution(sessions, l2c)

    e = sessions[0]["strength_exercises"][0]
    assert (e["resolution_tier"], e["substitute_text"], e["proxy_origin_id"]) == (3, None, "EX-BW")
    StrengthExercise(**e)


def test_resolution_is_per_session_locale():
    """Same exercise_id resolves tier-1 at home, tier-2 at hotel — the session's
    locale decides."""
    l2c = {
        "home": _l2c("home", [_rx("EX1", 1)]),
        "hotel": _l2c("hotel", [_rx("EX1", 2, substitute_text="db floor press")]),
    }
    sessions = [
        _session("home", [_raw_strength("EX1")]),
        _session("hotel", [_raw_strength("EX1")]),
    ]

    _apply_strength_resolution(sessions, l2c)

    home_e = sessions[0]["strength_exercises"][0]
    hotel_e = sessions[1]["strength_exercises"][0]
    assert home_e["resolution_tier"] == 1 and home_e["substitute_text"] is None
    assert hotel_e["resolution_tier"] == 2 and hotel_e["substitute_text"] == "db floor press"
    StrengthExercise(**home_e)
    StrengthExercise(**hotel_e)


def test_out_of_locale_pick_falls_back_to_any_locale_resolution():
    """A pick feasible at another cluster locale (enum is the cluster-union) is
    resolved via the cross-locale fallback rather than defaulted blindly."""
    l2c = {
        "home": _l2c("home", [_rx("EX1", 1)]),
        "hotel": _l2c("hotel", [_rx("EX9", 3, proxy_exercise_id="EX-BW")]),
    }
    # Session at home picked EX9, which only resolves at hotel.
    sessions = [_session("home", [_raw_strength("EX9")])]

    notes = _apply_strength_resolution(sessions, l2c)

    e = sessions[0]["strength_exercises"][0]
    assert (e["resolution_tier"], e["proxy_origin_id"]) == (3, "EX-BW")
    assert notes == []  # resolved via fallback, not a true miss
    StrengthExercise(**e)


def test_truly_unknown_pick_defaults_exact_and_is_noted():
    l2c = {"home": _l2c("home", [_rx("EX1", 1)])}
    sessions = [_session("home", [_raw_strength("EX-INVENTED")])]

    notes = _apply_strength_resolution(sessions, l2c)

    e = sessions[0]["strength_exercises"][0]
    assert (e["resolution_tier"], e["substitute_text"], e["proxy_origin_id"]) == (1, None, None)
    assert notes == ["EX-INVENTED@home"]
    StrengthExercise(**e)


def test_non_strength_sessions_and_empty_lists_are_skipped():
    l2c = {"home": _l2c("home", [_rx("EX1", 1)])}
    sessions = [
        {"locale_id": "home", "kind": "cardio", "strength_exercises": None},
        {"locale_id": "home", "kind": "rest"},
        _session("home", []),
    ]
    # Must not raise and must report no notes.
    assert _apply_strength_resolution(sessions, l2c) == []
