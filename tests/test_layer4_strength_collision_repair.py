"""WS-E — deterministic strength+strength repair.

A day with two `strength` sessions trips the hard `Layer4Payload._check_two_per_day`
invariant (the pv=69 / plan-70 stall class). `_repair_strength_collisions`
relocates the 2nd strength onto a single non-hard CARDIO day (else drops it)
BEFORE validation, so the collision self-heals instead of forcing a re-synthesis.
"""
from __future__ import annotations

from datetime import date

from layer4.payload import CardioBlock, HRTarget, PlanSession, StrengthExercise
from layer4.per_phase import _repair_strength_collisions


def _cardio(session_id: str, d: date, dow: str, idx: int = 0, intensity: str = "moderate") -> PlanSession:
    return PlanSession(
        session_id=session_id, plan_version_id=1, date=d, day_of_week=dow,
        session_index_in_day=idx, time_of_day="morning", kind="cardio",
        discipline_id="D-001", discipline_name="Run", locale_id="home",
        locale_name="Home", duration_min=45, intensity_summary=intensity,
        cardio_blocks=[CardioBlock(
            block_kind="main_set", duration_min=30, intensity_zone="Z2",
            intensity_target=HRTarget(hr_bpm_low=140, hr_bpm_high=155),
            instructions="Steady Z2.")],
        session_notes="n", coaching_intent="c", coaching_flags=[],
    )


def _strength(session_id: str, d: date, dow: str, idx: int = 0, intensity: str = "moderate") -> PlanSession:
    return PlanSession(
        session_id=session_id, plan_version_id=1, date=d, day_of_week=dow,
        session_index_in_day=idx, time_of_day="evening", kind="strength",
        discipline_id="D-008", discipline_name="MTB", locale_id="home",
        locale_name="Home", duration_min=45, intensity_summary=intensity,
        strength_exercises=[StrengthExercise(
            exercise_id="ex-1", exercise_name="Squat", resolution_tier=1, sets=3,
            reps_per_set=10, load_prescription="20kg", rest_between_sets_sec=90,
            instructions="x", coaching_flags=[])],
        session_notes="n", coaching_intent="c", coaching_flags=[],
    )


def _by_day(sessions):
    out: dict = {}
    for s in sessions:
        out.setdefault(s.date, []).append(s)
    return out


def _no_double_strength(sessions) -> bool:
    return not any(
        len(ss) == 2 and all(s.kind == "strength" for s in ss)
        for ss in _by_day(sessions).values()
    )


def test_relocates_second_strength_to_cardio_day():
    d1, d2 = date(2026, 6, 16), date(2026, 6, 17)
    sessions = [
        _strength("s1", d1, "Tue", idx=0),
        _strength("s2", d1, "Tue", idx=1),
        _cardio("c1", d2, "Wed", idx=0),
    ]
    out, notes = _repair_strength_collisions(sessions)
    assert notes and "relocated" in notes[0]
    assert _no_double_strength(out)
    by_day = _by_day(out)
    assert len(by_day[d1]) == 1 and by_day[d1][0].kind == "strength"
    assert sorted(s.kind for s in by_day[d2]) == ["cardio", "strength"]
    assert sorted(s.session_index_in_day for s in by_day[d2]) == [0, 1]


def test_drops_when_no_cardio_target():
    d1 = date(2026, 6, 16)
    sessions = [_strength("s1", d1, "Tue", idx=0), _strength("s2", d1, "Tue", idx=1)]
    out, notes = _repair_strength_collisions(sessions)
    assert notes and "dropped" in notes[0]
    assert len(out) == 1 and out[0].kind == "strength" and out[0].session_index_in_day == 0


def test_hard_cardio_is_not_a_relocation_target():
    # Only candidate day's cardio is 'hard' — adding strength would not be
    # two-hard, but the guard is conservative (avoid stacking onto a key day) →
    # falls back to drop. Asserts the collision is still resolved.
    d1, d2 = date(2026, 6, 16), date(2026, 6, 17)
    sessions = [
        _strength("s1", d1, "Tue", idx=0),
        _strength("s2", d1, "Tue", idx=1),
        _cardio("c1", d2, "Wed", idx=0, intensity="hard"),
    ]
    out, notes = _repair_strength_collisions(sessions)
    assert "dropped" in notes[0]
    assert _no_double_strength(out)


def test_no_collision_is_identity_passthrough():
    sessions = [
        _strength("s1", date(2026, 6, 16), "Tue", idx=0),
        _cardio("c1", date(2026, 6, 17), "Wed", idx=0),
    ]
    out, notes = _repair_strength_collisions(sessions)
    assert notes == [] and out is sessions


def test_idempotent():
    d1, d2 = date(2026, 6, 16), date(2026, 6, 17)
    sessions = [
        _strength("s1", d1, "Tue", idx=0),
        _strength("s2", d1, "Tue", idx=1),
        _cardio("c1", d2, "Wed", idx=0),
    ]
    out1, _ = _repair_strength_collisions(sessions)
    out2, notes2 = _repair_strength_collisions(out1)
    assert notes2 == [] and _no_double_strength(out2)
