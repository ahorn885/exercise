"""#698 Track 2 (A2) — cardio_drills threading into PlanSession.

Sibling of the recovery_exercises gap (PR for plan #74): `_build_plan_session`
silently dropped `cardio_drills` on the way into `PlanSession`, so the
synthesizer's pool-bound drills never reached the plan and the
`_rule_cardio_drill_pool_membership` validator was a dead no-op. Drills now
thread through — cardio-only, clamped to the maxItems:1 invariant, blank ids
skipped — so a stray over-emit degrades to dropped data, never a block discard.
"""
from __future__ import annotations

from datetime import date

from layer4.payload import PhaseSpec, SynthesisMetadata
from layer4.per_phase import _build_plan_session


def _phase_spec():
    return PhaseSpec(
        phase_name="Base",
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


def _drill(exercise_id="EX175", name="Brick Run", prescription="15 min off the bike"):
    return {"exercise_id": exercise_id, "exercise_name": name, "prescription": prescription}


def _cardio_dict(cardio_drills=None, kind="cardio"):
    d = {
        "date": "2026-06-22", "day_of_week": "Mon", "session_index_in_day": 0,
        "time_of_day": "morning", "kind": kind, "duration_min": 60,
        "intensity_summary": "moderate",
        "cardio_blocks": [{
            "block_kind": "main_set", "duration_min": 40, "intensity_zone": "Z2",
            "intensity_target": {"hr_bpm_low": 130, "hr_bpm_high": 150},
            "instructions": "Steady Z2.",
        }],
        "session_notes": "n", "coaching_intent": "c", "coaching_flags": [],
    }
    if cardio_drills is not None:
        d["cardio_drills"] = cardio_drills
    return d


def _strength_dict(cardio_drills=None):
    d = {
        "date": "2026-06-23", "day_of_week": "Tue", "session_index_in_day": 0,
        "time_of_day": "evening", "kind": "strength", "duration_min": 45,
        "intensity_summary": "moderate",
        "strength_exercises": [{
            "exercise_id": "EX-1", "exercise_name": "Squat", "resolution_tier": 1,
            "sets": 3, "reps_per_set": 10, "load_prescription": "20kg",
            "rest_between_sets_sec": 90, "instructions": "x", "coaching_flags": [],
        }],
        "session_notes": "n", "coaching_intent": "c", "coaching_flags": [],
    }
    if cardio_drills is not None:
        d["cardio_drills"] = cardio_drills
    return d


def _build(raw):
    return _build_plan_session(
        raw, session_id="S-test-bas-000", plan_version_id=1, phase_spec=_phase_spec()
    )


def test_cardio_drill_threaded_through():
    s = _build(_cardio_dict(cardio_drills=[_drill()]))
    assert s.cardio_drills is not None and len(s.cardio_drills) == 1
    assert s.cardio_drills[0].exercise_id == "EX175"


def test_over_emit_clamped_to_one():
    s = _build(_cardio_dict(cardio_drills=[_drill("EX175"), _drill("EX176", "Tri Transition")]))
    # maxItems:1 invariant — clamp keeps the first rather than failing the block.
    assert len(s.cardio_drills) == 1 and s.cardio_drills[0].exercise_id == "EX175"


def test_blank_exercise_id_skipped():
    s = _build(_cardio_dict(cardio_drills=[_drill(exercise_id="  ")]))
    assert s.cardio_drills is None


def test_no_drills_is_none():
    s = _build(_cardio_dict(cardio_drills=None))
    assert s.cardio_drills is None


def test_drills_on_non_cardio_are_not_threaded():
    # A drill mistakenly attached to a strength session must NOT be threaded
    # (the invariant requires cardio_drills is None on strength) — builds clean.
    s = _build(_strength_dict(cardio_drills=[_drill()]))
    assert s.kind == "strength" and s.cardio_drills is None
