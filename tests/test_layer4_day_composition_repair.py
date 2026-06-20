"""#778/#779 — deterministic day-composition repair.

Two day-compositions the deterministic grid can't constrain up front (day
placement + which session is hard are the LLM's free choice):

- two training sessions sharing a `discipline_id` on one day (#778) — NO guard
  blocks it (it slips through whenever the pair isn't both-hard), so a
  doubled-MTB day passed every guard on plan-75 (2026-07-09).
- two hard training sessions on one day (#779) — a hard `_check_two_per_day`
  payload invariant that, pre-repair, fumbled the block + burned a retry.

`_repair_day_composition` (mirrors `_repair_strength_collisions`) RELOCATES the
later session onto a single non-hard cardio day of a DIFFERENT discipline (fixes
both flags, content intact); else DEMOTES a two-hard day's 2nd session
hard→moderate; else leaves a same-discipline-only day (it passes validation).
"""
from __future__ import annotations

from datetime import date

from layer4.payload import (
    CardioBlock,
    HRTarget,
    PlanSession,
    RecoveryExercise,
)
from layer4.per_phase import _repair_day_composition


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


def _indices_contiguous(sessions) -> bool:
    for ss in _by_day(sessions).values():
        idxs = sorted(s.session_index_in_day for s in ss)
        if idxs != list(range(len(ss))):
            return False
    return True


def test_two_hard_relocated_to_non_hard_different_discipline_day():
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out, notes = _repair_day_composition(sessions)
    assert notes and "relocated" in notes[0]
    assert _no_two_hard(out) and _no_same_discipline(out)
    assert _indices_contiguous(out)
    by_day = _by_day(out)
    assert len(by_day[d1]) == 1
    assert sorted(s.session_index_in_day for s in by_day[d2]) == [0, 1]


def test_two_hard_demoted_when_no_relocation_day():
    d1 = date(2026, 7, 9)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-001"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
    ]
    out, notes = _repair_day_composition(sessions)
    assert notes and "demoted" in notes[0]
    assert _no_two_hard(out)
    # the later (idx==1) session is the mover and is demoted off 'hard'.
    mover = next(s for s in out if s.session_id == "c2")
    assert mover.intensity_summary == "moderate"


def test_same_discipline_relocated_even_when_not_hard():
    # Two D-008 cardio, one easy one moderate → no guard blocks it; #778 repairs.
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="moderate", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="easy", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out, notes = _repair_day_composition(sessions)
    assert notes and "relocated" in notes[0] and "two_same_discipline" in notes[0]
    assert _no_same_discipline(out)


def test_same_discipline_only_left_unrepaired_when_no_target():
    d1 = date(2026, 7, 9)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="moderate", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="easy", discipline_id="D-008"),
    ]
    out, notes = _repair_day_composition(sessions)
    # Not a hard blocker → left as-is, but the decision is logged (Rule #15).
    assert notes and "unrepaired" in notes[0]
    assert out == sessions or len(out) == len(sessions)
    assert not _no_same_discipline(out)  # unchanged: still same-discipline


def test_same_discipline_cardio_is_not_a_relocation_target():
    # Only candidate day shares the mover's discipline → relocating there would
    # create a NEW same-discipline day, so it's rejected. Two-hard still demotes.
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-008"),
    ]
    out, notes = _repair_day_composition(sessions)
    assert "demoted" in notes[0]
    assert _no_two_hard(out)


def test_reindex_keeps_recovery_day_contiguous():
    # 3-session source day (2 hard training + 1 recovery): relocating the mover
    # must renumber the remaining keeper+recovery to contiguous 0..1.
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _recovery("r1", d1, "Thu", idx=2),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out, notes = _repair_day_composition(sessions)
    assert "relocated" in notes[0]
    assert _no_two_hard(out) and _indices_contiguous(out)
    by_day = _by_day(out)
    assert sorted(s.session_index_in_day for s in by_day[d1]) == [0, 1]


def test_no_offending_day_is_identity_passthrough():
    sessions = [
        _cardio("c1", date(2026, 7, 9), "Thu", idx=0, intensity="moderate", discipline_id="D-001"),
        _cardio("c2", date(2026, 7, 9), "Thu", idx=1, intensity="easy", discipline_id="D-008"),
        _cardio("c3", date(2026, 7, 10), "Fri", idx=0, intensity="hard", discipline_id="D-001"),
    ]
    out, notes = _repair_day_composition(sessions)
    assert notes == [] and out is sessions


def test_idempotent():
    d1, d2 = date(2026, 7, 9), date(2026, 7, 10)
    sessions = [
        _cardio("c1", d1, "Thu", idx=0, intensity="hard", discipline_id="D-008"),
        _cardio("c2", d1, "Thu", idx=1, intensity="hard", discipline_id="D-008"),
        _cardio("t", d2, "Fri", idx=0, intensity="easy", discipline_id="D-001"),
    ]
    out1, _ = _repair_day_composition(sessions)
    out2, notes2 = _repair_day_composition(out1)
    assert notes2 == [] and _no_two_hard(out2) and _no_same_discipline(out2)
