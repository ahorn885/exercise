"""Deterministic day-composition normalizer (`_normalize_day_composition`).

Unifies the former `_repair_strength_collisions` (#579/WS-E) +
`_repair_day_composition` (#778/#779) into one shape-agnostic pass that
guarantees every day satisfies the hard `Layer4Payload._check_two_per_day`
invariant BEFORE the validator runs (strength+strength, two-hard,
neither-cardio, >2 training, >1 recovery, contiguous indices), with the #778
same-discipline relocation kept as a best-effort soft preference.

plan-78 regression: a day carrying two DIFFERENT-discipline strength sessions
PLUS an additive #698 recovery slot (3 sessions) was repaired by NEITHER former
function — the strength repairer required exactly 2 sessions on the day, the
day-composition repairer only fired on same-discipline/two-hard — so it
hard-failed every Build:w1 attempt (`synthesis_budget_exhausted`, 2026-06-21).
"""
from __future__ import annotations

from datetime import date

from layer4.payload import (
    CardioBlock,
    HRTarget,
    PlanSession,
    RecoveryExercise,
    StrengthExercise,
)
from layer4.per_phase import _normalize_day_composition


def _cardio(
    session_id: str,
    d: date,
    dow: str,
    idx: int = 0,
    intensity: str = "moderate",
    discipline_id: str = "D-001",
) -> PlanSession:
    return PlanSession(
        session_id=session_id, plan_version_id=1, date=d, day_of_week=dow,
        session_index_in_day=idx, time_of_day="morning", kind="cardio",
        discipline_id=discipline_id, discipline_name="Disc", locale_id="home",
        locale_name="Home", duration_min=45, intensity_summary=intensity,
        cardio_blocks=[CardioBlock(
            block_kind="main_set", duration_min=30, intensity_zone="Z2",
            intensity_target=HRTarget(hr_bpm_low=140, hr_bpm_high=155),
            instructions="Steady Z2.")],
        session_notes="n", coaching_intent="c", coaching_flags=[],
    )


def _strength(
    session_id: str,
    d: date,
    dow: str,
    idx: int = 0,
    intensity: str = "moderate",
    discipline_id: str = "D-008",
) -> PlanSession:
    return PlanSession(
        session_id=session_id, plan_version_id=1, date=d, day_of_week=dow,
        session_index_in_day=idx, time_of_day="evening", kind="strength",
        discipline_id=discipline_id, discipline_name="Strength", locale_id="home",
        locale_name="Home", duration_min=45, intensity_summary=intensity,
        strength_exercises=[StrengthExercise(
            exercise_id="ex-1", exercise_name="Squat", resolution_tier=1, sets=3,
            reps_per_set=10, load_prescription="20kg", rest_between_sets_sec=90,
            instructions="x", coaching_flags=[])],
        session_notes="n", coaching_intent="c", coaching_flags=[],
    )


def _recovery(session_id: str, d: date, dow: str, idx: int = 2) -> PlanSession:
    return PlanSession(
        session_id=session_id, plan_version_id=1, date=d, day_of_week=dow,
        session_index_in_day=idx, time_of_day="evening", kind="recovery",
        duration_min=20, intensity_summary="easy",
        recovery_exercises=[RecoveryExercise(
            exercise_id="rx-1", exercise_name="Stretch",
            prescription="2x30s/side", instructions="Gentle.")],
        session_notes="n", coaching_intent="c", coaching_flags=[],
    )


def _by_day(sessions):
    out: dict = {}
    for s in sessions:
        out.setdefault(s.date, []).append(s)
    return out


def _training(ss):
    return [s for s in ss if s.kind in ("cardio", "strength")]


def _no_double_strength(sessions) -> bool:
    return not any(
        len(_training(ss)) == 2 and all(s.kind == "strength" for s in _training(ss))
        for ss in _by_day(sessions).values()
    )


def _no_two_hard(sessions) -> bool:
    return not any(
        len(_training(ss)) == 2
        and all(s.intensity_summary == "hard" for s in _training(ss))
        for ss in _by_day(sessions).values()
    )


def _no_same_discipline(sessions) -> bool:
    for ss in _by_day(sessions).values():
        disc = [s.discipline_id for s in _training(ss) if s.discipline_id]
        if len(disc) != len(set(disc)):
            return False
    return True


def _max_two_training(sessions) -> bool:
    return all(len(_training(ss)) <= 2 for ss in _by_day(sessions).values())


def _indices_contiguous(sessions) -> bool:
    for ss in _by_day(sessions).values():
        idxs = sorted(s.session_index_in_day for s in ss)
        if idxs != list(range(len(ss))):
            return False
    return True


# ─── plan-78 regression: two different-discipline strength + a recovery ──────

def test_plan78_strength_plus_strength_plus_recovery_relocates():
    # The exact failing shape (2026-06-25): two DIFFERENT-discipline strength +
    # an additive recovery (3 sessions). Both former repairers skipped it.
    d1, d2 = date(2026, 6, 25), date(2026, 6, 27)
    sessions = [
        _strength("s_d003", d1, "Thu", idx=0, discipline_id="D-003"),
        _strength("s_d012", d1, "Thu", idx=1, discipline_id="D-012"),
        _recovery("rec", d1, "Thu", idx=2),
        _cardio("c", d2, "Sat", idx=0, intensity="easy", discipline_id="D-008"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "relocated" in notes[0] and "strength+strength" in notes[0]
    assert _no_double_strength(out) and _indices_contiguous(out)
    by_day = _by_day(out)
    # source day keeps the 1st strength + the recovery, renumbered contiguous.
    assert sorted(s.kind for s in by_day[d1]) == ["recovery", "strength"]
    assert sorted(s.session_index_in_day for s in by_day[d1]) == [0, 1]
    # target day gained the relocated strength alongside its cardio.
    assert sorted(s.kind for s in by_day[d2]) == ["cardio", "strength"]


def test_plan78_strength_collision_with_recovery_drops_when_no_target():
    # Same 3-session collision but no cardio relocation day → drop the 2nd
    # strength; the recovery survives and the day stays legal + contiguous.
    d1 = date(2026, 6, 25)
    sessions = [
        _strength("s_d003", d1, "Thu", idx=0, discipline_id="D-003"),
        _strength("s_d012", d1, "Thu", idx=1, discipline_id="D-012"),
        _recovery("rec", d1, "Thu", idx=2),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "dropped 2nd strength" in notes[0]
    assert {s.session_id for s in out} == {"s_d003", "rec"}
    assert _no_double_strength(out) and _indices_contiguous(out)
    assert sorted(s.session_index_in_day for s in out) == [0, 1]


# ─── strength+strength (migrated from the WS-E suite) ─────────────────────────

def test_relocates_second_strength_to_cardio_day():
    d1, d2 = date(2026, 6, 16), date(2026, 6, 17)
    sessions = [
        _strength("s1", d1, "Tue", idx=0),
        _strength("s2", d1, "Tue", idx=1),
        _cardio("c1", d2, "Wed", idx=0, discipline_id="D-001"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "relocated" in notes[0]
    assert _no_double_strength(out)
    by_day = _by_day(out)
    assert len(by_day[d1]) == 1 and by_day[d1][0].kind == "strength"
    assert sorted(s.kind for s in by_day[d2]) == ["cardio", "strength"]
    assert sorted(s.session_index_in_day for s in by_day[d2]) == [0, 1]


def test_drops_when_no_cardio_target():
    d1 = date(2026, 6, 16)
    sessions = [_strength("s1", d1, "Tue", idx=0), _strength("s2", d1, "Tue", idx=1)]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "dropped" in notes[0]
    assert len(out) == 1 and out[0].kind == "strength" and out[0].session_index_in_day == 0


def test_hard_cardio_is_not_a_relocation_target():
    d1, d2 = date(2026, 6, 16), date(2026, 6, 17)
    sessions = [
        _strength("s1", d1, "Tue", idx=0),
        _strength("s2", d1, "Tue", idx=1),
        _cardio("c1", d2, "Wed", idx=0, intensity="hard"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert "dropped" in notes[0]
    assert _no_double_strength(out)


# ─── two-hard + same-discipline (migrated from the #778/#779 suite) ───────────

def test_two_hard_relocated_to_non_hard_different_discipline_day():
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "relocated" in notes[0]
    assert _no_two_hard(out) and _no_same_discipline(out) and _indices_contiguous(out)
    by_day = _by_day(out)
    assert len(by_day[d1]) == 1
    assert sorted(s.session_index_in_day for s in by_day[d2]) == [0, 1]


def test_two_hard_demoted_when_no_relocation_day():
    d1 = date(2026, 7, 9)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-001"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "demoted" in notes[0]
    assert _no_two_hard(out)
    mover = next(s for s in out if s.session_id == "c2")
    assert mover.intensity_summary == "moderate"


def test_same_discipline_relocated_even_when_not_hard():
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="moderate", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="easy", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "relocated" in notes[0] and "two_same_discipline" in notes[0]
    assert _no_same_discipline(out)


def test_same_discipline_only_left_unrepaired_when_no_target():
    d1 = date(2026, 7, 9)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="moderate", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="easy", discipline_id="D-008"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes and "unrepaired" in notes[0]
    assert not _no_same_discipline(out)  # unchanged: still same-discipline (legal)


def test_same_discipline_cardio_is_not_a_relocation_target():
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-008"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert "demoted" in notes[0]
    assert _no_two_hard(out)


def test_reindex_keeps_recovery_day_contiguous():
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _recovery("r1", d1, "Thu", idx=2),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert "relocated" in notes[0]
    assert _no_two_hard(out) and _indices_contiguous(out)
    by_day = _by_day(out)
    assert sorted(s.session_index_in_day for s in by_day[d1]) == [0, 1]
    # recovery keeps the last slot on its (now 2-session) day.
    assert by_day[d1][-1].kind == "recovery" or max(
        by_day[d1], key=lambda s: s.session_index_in_day
    ).kind == "recovery"


# ─── defensive count caps ────────────────────────────────────────────────────

def test_excess_training_capped_to_two():
    # Three training on one day (>2): the LLM can emit it though the grid won't.
    # The excess is evicted so the hard "max 2 training" clause can't fire.
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="easy", discipline_id="D-001"),
        _cardio("c2", d1, "Thu", idx=1, intensity="easy", discipline_id="D-008"),
        _strength("s1", d1, "Thu", idx=2, discipline_id="D-003"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-009"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes
    assert _max_two_training(out) and _indices_contiguous(out)


# ─── identity + idempotence ──────────────────────────────────────────────────

def test_no_offending_day_is_identity_passthrough():
    sessions = [
        _strength("s1", date(2026, 6, 16), "Tue", idx=0),
        _cardio("c1", date(2026, 6, 17), "Wed", idx=0),
        _cardio("c2", date(2026, 6, 18), "Thu", idx=0, intensity="hard", discipline_id="D-001"),
    ]
    out, notes = _normalize_day_composition(sessions)
    assert notes == [] and out is sessions


def test_idempotent():
    d1, d2 = date(2026, 6, 16), date(2026, 6, 17)
    sessions = [
        _strength("s1", d1, "Tue", idx=0),
        _strength("s2", d1, "Tue", idx=1),
        _cardio("c1", d2, "Wed", idx=0, discipline_id="D-001"),
    ]
    out1, _ = _normalize_day_composition(sessions)
    out2, notes2 = _normalize_day_composition(out1)
    assert notes2 == [] and _no_double_strength(out2) and _no_two_hard(out2)
