"""#698 Track 1 — recovery_exercises threading + deterministic crash-guard.

Two coupled defects sank prod plan #74 (Build:w1, 2026-06-19), the first
plan-create run after deterministic Slice-3b recovery placement started *forcing*
a `kind=='recovery'` session onto every plan:

1. `_build_plan_session` never threaded `recovery_exercises` from the raw tool
   dict into `PlanSession`, so the field was always `None` → the invariant
   `kind=='recovery' requires recovery_exercises non-None and non-empty` failed
   100% of the time, discarding the whole week's block as unparseable.
2. Nothing structurally guarantees the synthesizer fills the (advisory) schema
   block, so even with #1 fixed a model omission would still fail the forced
   recovery day — which the placement-match validator rule won't let us drop.

`_repair_recovery_exercises` (mirrors `_repair_strength_collisions`) fills an
empty recovery block from the SAME resolved pool BEFORE validation, so the forced
day self-heals instead of failing.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace as NS

import pytest

from layer4.payload import (
    PhaseSpec,
    PlanSession,
    RecoveryExercise,
    SynthesisMetadata,
)
from layer4.per_phase import (
    _RECOVERY_FILL_COUNT,
    _build_plan_session,
    _recovery_pool_entries,
    _repair_recovery_exercises,
    compute_recovery_pool_ids,
)
from pydantic import ValidationError


# ─── fixtures (duck-typed, like test_layer4_strength_pool) ───────────────────


def _rx(exercise_id, name, exercise_type):
    return NS(exercise_id=exercise_id, exercise_name=name, exercise_type=exercise_type)


def _l2c(locale_id, resolved):
    return NS(locale_id=locale_id, exercises_resolved=resolved)


def _l2d(excluded_ids):
    return NS(excluded_exercises=[NS(exercise_id=i) for i in excluded_ids])


def _pool():
    """A recovery pool with one of each recovery type + a non-recovery row that
    must be filtered out. Sorted ids: EX001 (Mobility), EX002 (Flex), EX003 (Soft
    Tissue), EX004 (Breathwork)."""
    return {
        "home": _l2c("home", [
            _rx("EX001", "Cat-Cow", "Mobility"),
            _rx("EX002", "Hamstring Stretch", "Flexibility / Stretching"),
            _rx("EX003", "Foam Roll Quads", "Recovery / Soft Tissue"),
            _rx("EX004", "Box Breathing", "Breathwork"),
            _rx("EX900", "Back Squat", "Strength"),  # non-recovery → excluded
        ])
    }


def _recovery_dict(recovery_exercises=None, **overrides):
    """A raw synthesizer session dict for a forced recovery day."""
    d = {
        "date": "2026-06-22",
        "day_of_week": "Mon",
        "session_index_in_day": 2,
        "time_of_day": "evening",
        "kind": "recovery",
        "duration_min": 18,
        "intensity_summary": "easy",
        "recovery_exercises": recovery_exercises,
        "session_notes": "Assigned recovery day.",
        "coaching_intent": "Sub-threshold mobility.",
        "coaching_flags": [],
    }
    d.update(overrides)
    return d


def _cardio_dict():
    return {
        "date": "2026-06-23",
        "day_of_week": "Tue",
        "session_index_in_day": 0,
        "time_of_day": "morning",
        "kind": "cardio",
        "duration_min": 60,
        "intensity_summary": "moderate",
        "cardio_blocks": [{
            "block_kind": "main_set", "duration_min": 40, "intensity_zone": "Z2",
            "intensity_target": {"hr_bpm_low": 130, "hr_bpm_high": 150},
            "instructions": "Steady Z2.",
        }],
        "session_notes": "n", "coaching_intent": "c", "coaching_flags": [],
    }


def _phase_spec():
    return PhaseSpec(
        phase_name="Build",
        start_date=date(2026, 6, 22),
        end_date=date(2026, 7, 19),
        weeks=4,
        intended_volume_band=(8.0, 12.0),
        intended_intensity_distribution={"z12": 0.8, "z345": 0.2},
        synthesis_metadata=SynthesisMetadata(
            model="claude-sonnet-4-6", temperature=1.0, input_tokens=0,
            output_tokens=0, latency_ms=0, retries_used=0, cap_hit=False,
        ),
    )


def _build(raw):
    return _build_plan_session(
        raw, session_id="S-test-bui-000", plan_version_id=1, phase_spec=_phase_spec()
    )


# ─── _recovery_pool_entries ──────────────────────────────────────────────────


def test_pool_entries_match_compute_pool_and_carry_name_type():
    entries = _recovery_pool_entries(_pool(), None)
    # Same id set the enum/prompt use (non-recovery type filtered out).
    assert sorted(entries) == compute_recovery_pool_ids(_pool(), None)
    assert "EX900" not in entries  # Strength row dropped
    assert entries["EX001"] == ("Cat-Cow", "Mobility")


def test_pool_entries_honor_2d_exclusions():
    entries = _recovery_pool_entries(_pool(), _l2d({"EX002"}))
    assert "EX002" not in entries and "EX001" in entries


# ─── _repair_recovery_exercises ──────────────────────────────────────────────


def test_fills_empty_recovery_block_from_sorted_pool():
    entries = _recovery_pool_entries(_pool(), None)
    sessions, notes = _repair_recovery_exercises([_recovery_dict()], entries)
    rx = sessions[0]["recovery_exercises"]
    assert len(rx) == _RECOVERY_FILL_COUNT  # lean
    # First two sorted ids, each in-pool, with a type-correct prescription.
    assert [e["exercise_id"] for e in rx] == ["EX001", "EX002"]
    assert rx[0]["prescription"] == "2×8 controlled reps/side"  # Mobility
    assert rx[1]["prescription"] == "2×30s/side"  # Flexibility / Stretching
    assert notes and "filled 2 recovery_exercises" in notes[0]


def test_filled_ids_are_in_pool():
    entries = _recovery_pool_entries(_pool(), None)
    pool = set(compute_recovery_pool_ids(_pool(), None))
    sessions, _ = _repair_recovery_exercises([_recovery_dict()], entries)
    assert all(e["exercise_id"] in pool for e in sessions[0]["recovery_exercises"])


def test_leaves_populated_block_untouched():
    entries = _recovery_pool_entries(_pool(), None)
    preset = [{"exercise_id": "EX004", "exercise_name": "Box Breathing",
               "prescription": "5 min", "instructions": "slow"}]
    sessions, notes = _repair_recovery_exercises(
        [_recovery_dict(recovery_exercises=preset)], entries
    )
    assert sessions[0]["recovery_exercises"] == preset and notes == []


def test_ignores_non_recovery_sessions():
    entries = _recovery_pool_entries(_pool(), None)
    sessions, notes = _repair_recovery_exercises([_cardio_dict()], entries)
    assert "recovery_exercises" not in sessions[0] and notes == []


def test_noop_when_pool_empty():
    raw = [_recovery_dict()]
    sessions, notes = _repair_recovery_exercises(raw, {})
    assert sessions is raw and notes == []
    assert sessions[0]["recovery_exercises"] is None


def test_idempotent():
    entries = _recovery_pool_entries(_pool(), None)
    once, _ = _repair_recovery_exercises([_recovery_dict()], entries)
    twice, notes2 = _repair_recovery_exercises(once, entries)
    assert notes2 == []  # already populated on the second pass


# ─── _build_plan_session threading (primary fix) + plan #74 regression ───────


def test_build_plan_session_threads_recovery_exercises():
    """The primary defect: the field was dropped on the way into PlanSession."""
    preset = [{"exercise_id": "EX001", "exercise_name": "Cat-Cow",
               "prescription": "2×8/side", "instructions": "slow"}]
    s = _build(_recovery_dict(recovery_exercises=preset))
    assert s.kind == "recovery"
    assert s.recovery_exercises is not None and len(s.recovery_exercises) == 1
    assert s.recovery_exercises[0].exercise_id == "EX001"


def test_plan74_regression_empty_block_fails_then_repair_heals():
    # Reproduce plan #74: a forced recovery session with no recovery_exercises
    # fails the PlanSession invariant when built directly...
    with pytest.raises(ValidationError, match="recovery_exercises non-None and non-empty"):
        _build(_recovery_dict(recovery_exercises=None))
    # ...and self-heals after the deterministic crash-guard fills it.
    entries = _recovery_pool_entries(_pool(), None)
    repaired, _ = _repair_recovery_exercises([_recovery_dict()], entries)
    s = _build(repaired[0])
    assert s.kind == "recovery" and len(s.recovery_exercises) == _RECOVERY_FILL_COUNT
    assert all(isinstance(e, RecoveryExercise) for e in s.recovery_exercises)
