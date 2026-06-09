"""Tests for `layer4.rx_wire` — Track 2 slice 2d §7."""

from __future__ import annotations

from datetime import date

import pytest

from layer4.context import (
    DisciplineCoverage,
    Layer2CPayload,
    ResolvedExercise,
)
from layer4.payload import (
    CardioBlock,
    HRTarget,
    Layer4Payload,
    PlanSession,
    StrengthExercise,
    ValidatorResult,
)
from layer4.rx_wire import (
    ExerciseRxOutcome,
    RxWireDiagnostic,
    _FIRST_EXPOSURE_TEMPLATES,
    _classify_category,
    apply_current_rx,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeDb:
    """Minimal db stub: maps (exercise_name, user_id) → dict-like row.
    Returns None for unknown keys (simulates first-exposure)."""

    def __init__(self, rows: dict[tuple[str, int], dict | None] | None = None):
        self._rows = rows or {}
        self.queries: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params=()):
        self.queries.append((sql, tuple(params)))
        if "FROM current_rx" in sql:
            ex_name, uid = params[0], params[1]
            row = self._rows.get((ex_name, uid))
            return _Cursor(row)
        return _Cursor(None)


class _ErroringDb:
    """db stub that raises on every execute — used to verify the inner
    try/except in `apply_current_rx` records `path=skipped` and passes
    the original prescription through unmodified."""

    def execute(self, sql: str, params=()):
        raise RuntimeError("simulated db failure")


def _row(sets=3, reps=8, weight=None, duration=None, movement_pattern="Squat"):
    return {
        'current_sets': sets,
        'current_reps': reps,
        'current_weight': weight,
        'current_duration': duration,
        'movement_pattern': movement_pattern,
    }


def _resolved(
    ex_id: str,
    name: str = "",
    *,
    patterns: list[str] | None = None,
    tier: int = 1,
) -> ResolvedExercise:
    return ResolvedExercise(
        exercise_id=ex_id,
        exercise_name=name or ex_id,
        exercise_type="strength",
        discipline_ids=["D-strength"],
        sport_relevance_notes={},
        priority_per_discipline={"D-strength": "High"},
        movement_patterns=patterns or [],
        tier=tier,
        resolution_detail=None,
        terrain_required=[],
        contraindicated_parts=[],
        contraindicated_conditions=[],
        accommodations=[],
    )


def _layer2c(locale_id: str, exercises: list[ResolvedExercise]) -> Layer2CPayload:
    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"0A": "0A-v11.0", "0B": "0B-v11.0", "0C": "0C-v2.0-r2"},
        effective_pool=[],
        discipline_coverage=[],
        exercises_resolved=exercises,
        coaching_flags=[],
    )


def _strength_ex(
    ex_id: str,
    *,
    name: str | None = None,
    coaching_flags: list[str] | None = None,
) -> StrengthExercise:
    return StrengthExercise(
        exercise_id=ex_id,
        exercise_name=name or ex_id,
        resolution_tier=1,
        sets=3,
        reps_per_set=8,
        load_prescription="LLM advisory: RPE 7-8",
        rest_between_sets_sec=90,
        instructions="Standard execution.",
        coaching_flags=coaching_flags or [],
    )


def _strength_session(sid: str, exercises: list[StrengthExercise]) -> PlanSession:
    return PlanSession(
        session_id=sid,
        plan_version_id=1,
        date=date(2026, 6, 1),
        day_of_week="Mon",
        session_index_in_day=0,
        time_of_day="morning",
        kind="strength",
        discipline_id="D-strength",
        discipline_name="Strength",
        duration_min=45,
        intensity_summary="moderate",
        strength_exercises=exercises,
        session_notes="test session",
        coaching_intent="test intent",
        coaching_flags=[],
    )


def _cardio_session(sid: str) -> PlanSession:
    return PlanSession(
        session_id=sid,
        plan_version_id=1,
        date=date(2026, 6, 1),
        day_of_week="Mon",
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="D-001",
        discipline_name="Trail Running",
        duration_min=60,
        intensity_summary="easy",
        cardio_blocks=[CardioBlock(
            block_kind="main_set",
            duration_min=60,
            intensity_zone="Z1",
            intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=140),
            instructions="Easy run.",
        )],
        session_notes="test cardio",
        coaching_intent="test intent",
        coaching_flags=[],
    )


def _rest_session(sid: str) -> PlanSession:
    return PlanSession(
        session_id=sid,
        plan_version_id=1,
        date=date(2026, 6, 1),
        day_of_week="Mon",
        session_index_in_day=0,
        time_of_day="unspecified",
        kind="rest",
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        session_notes="rest",
        coaching_intent="recover",
        coaching_flags=[],
    )


def _payload(sessions: list[PlanSession]) -> Layer4Payload:
    """Minimal `plan_refresh` + pattern B payload — the lightest mode that
    skips the `phase_structure` / `seam_reviews` invariants so the rx_wire
    transform can be exercised without dragging the full Pattern-A scaffold."""
    return Layer4Payload(
        user_id=1,
        mode="plan_refresh",
        plan_version_id=1,
        scope_start_date=min(s.date for s in sessions) if sessions else date(2026, 6, 1),
        scope_end_date=max(s.date for s in sessions) if sessions else date(2026, 6, 1),
        model_synthesizer="m",
        temperature=0.0,
        pattern="B",
        latency_ms_total=0,
        input_tokens_total=0,
        output_tokens_total=0,
        llm_call_count=0,
        etl_version_set={"layer0": "v7"},
        sessions=sessions,
        validator_results=[
            ValidatorResult(pass_index=0, accepted=True, rule_failures=[], retried_phase_names=[])
        ],
        notable_observations=[],
    )


# ─── Tests ─────────────────────────────────────────────────────────────────


class TestCurrentRxHit:
    """When `current_rx(...)` returns a row, the precise baseline is written
    to `load_prescription` and `first_exposure` is NOT added."""

    def test_renders_weight_reps_sets(self):
        # #469 — storage is canonical kg; imperial-default display renders lb.
        # 83.9 kg ≈ 185 lb after conversion.
        ex = _strength_ex("EX-001", name="Back Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=5, weight=83.9146)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == "3 × 5 @ 185 lb"
        assert "first_exposure" not in result_ex.coaching_flags
        assert diag.current_rx_hits == 1
        assert diag.first_exposure_count == 0
        assert diag.outcomes[0].path == "current_rx"

    def test_rounds_weight_to_whole_lbs(self):
        # #469 — 84.6 kg → 186.5 lb → rounds to 187 lb. Whole-number
        # rendering reads cleaner than "186.5 lb".
        ex = _strength_ex("EX-001", name="Back Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=5, weight=84.6)})

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "3 × 5 @ 187 lb"

    def test_duration_only_renders_seconds(self):
        ex = _strength_ex("EX-PLANK", name="Plank")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-PLANK", "Plank", patterns=["Anti-Extension"])])
        db = _FakeDb({("Plank", 1): _row(sets=3, reps=None, weight=None, duration=45)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "3 × 45s"
        assert diag.current_rx_hits == 1

    def test_sparse_row_with_no_weight_or_duration_falls_through(self):
        """A `current_rx` row with both weight=None and duration=None should
        fall through to first-exposure rather than render an empty prescription."""
        ex = _strength_ex("EX-001", name="Back Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=5, weight=None, duration=None)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert diag.current_rx_hits == 0
        assert diag.first_exposure_count == 1


class TestFirstExposure:
    """When `current_rx` returns None, the category-keyed template is written
    and `first_exposure` is appended to the exercise's coaching_flags."""

    def test_compound_barbell_template(self):
        ex = _strength_ex("EX-001", name="Back Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb()  # no rows → first exposure

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["compound_barbell"]
        assert "first_exposure" in result_ex.coaching_flags
        assert diag.outcomes[0].category == "compound_barbell"

    def test_compound_dumbbell_template(self):
        ex = _strength_ex("EX-002", name="Dumbbell Goblet Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-002", "Dumbbell Goblet Squat", patterns=["Squat"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["compound_dumbbell"]

    def test_accessory_dumbbell_template(self):
        # No compound pattern in the resolved entry → accessory.
        ex = _strength_ex("EX-003", name="Dumbbell Curl")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-003", "Dumbbell Curl", patterns=["Curl"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["accessory_dumbbell"]

    def test_accessory_cable_template(self):
        ex = _strength_ex("EX-004", name="Cable Row")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-004", "Cable Row", patterns=["Pull"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["accessory_cable"]

    def test_bodyweight_template_via_tier(self):
        """Layer2C tier 0/3 → bodyweight category regardless of name."""
        ex = _strength_ex("EX-005", name="Air Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-005", "Air Squat", patterns=["Squat"], tier=3)])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["bodyweight"]

    def test_first_exposure_flag_idempotent(self):
        """An exercise that already carries `first_exposure` doesn't get
        a second copy when rx_wire runs again."""
        ex = _strength_ex("EX-001", name="Back Squat", coaching_flags=["first_exposure"])
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        flags = new_payload.sessions[0].strength_exercises[0].coaching_flags
        assert flags.count("first_exposure") == 1

    def test_unknown_exercise_id_no_resolved_entry(self):
        """An exercise emitted with no corresponding cluster-resolved entry
        (e.g., a layer0-only exercise not yet propagated through 2C)
        defaults to bodyweight — the conservative pick that never invites
        the athlete to guess a load."""
        ex = _strength_ex("EX-UNKNOWN", name="Mystery Movement")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [])  # empty resolved index
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["bodyweight"]


class TestClassifyCategory:
    """Direct unit coverage of the classifier."""

    def test_tier3_overrides_name(self):
        ex = _strength_ex("E1", name="Barbell Back Squat")
        resolved = _resolved("E1", "Barbell Back Squat", patterns=["Squat"], tier=3)
        assert _classify_category(ex, resolved) == "bodyweight"

    def test_tier0_classified_as_bodyweight(self):
        ex = _strength_ex("E1", name="Air Squat")
        resolved = _resolved("E1", "Air Squat", patterns=["Squat"], tier=0)
        assert _classify_category(ex, resolved) == "bodyweight"

    def test_machine_in_name_is_accessory_cable(self):
        ex = _strength_ex("E1", name="Leg Press Machine")
        resolved = _resolved("E1", "Leg Press Machine", patterns=["Squat"])
        assert _classify_category(ex, resolved) == "accessory_cable"

    def test_no_resolved_no_equipment_cue_defaults_bodyweight(self):
        ex = _strength_ex("E1", name="Pushup")
        assert _classify_category(ex, None) == "bodyweight"


class TestNonStrengthUntouched:
    def test_cardio_session_pass_through(self):
        cardio = _cardio_session("S-cardio")
        db = _FakeDb()
        new_payload, diag = apply_current_rx(_payload([cardio]), db, 1, {})
        # Cardio session round-tripped intact; no diag outcomes emitted.
        assert new_payload.sessions[0].kind == "cardio"
        assert diag.outcomes == []
        assert diag.current_rx_hits == 0
        assert diag.first_exposure_count == 0

    def test_rest_session_pass_through(self):
        rest = _rest_session("S-rest")
        db = _FakeDb()
        new_payload, diag = apply_current_rx(_payload([rest]), db, 1, {})
        assert new_payload.sessions[0].kind == "rest"
        assert diag.outcomes == []


class TestDegradedDb:
    def test_db_exception_skips_exercise_keeps_original(self):
        """A db error on `current_rx` lookup is caught per-exercise: the
        original `load_prescription` survives + the outcome records
        `path=skipped`. Plan generation is never wedged by an rx-wire defect."""
        ex = _strength_ex("EX-001", name="Back Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])

        new_payload, diag = apply_current_rx(
            _payload([session]), _ErroringDb(), 1, {"home": l2c},
        )

        # Original prescription preserved.
        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == "LLM advisory: RPE 7-8"
        assert "first_exposure" not in result_ex.coaching_flags
        assert diag.skipped_count == 1
        assert diag.outcomes[0].path == "skipped"


class TestDiagnosticMetadata:
    def test_to_metadata_shape(self):
        ex_hit = _strength_ex("EX-001", name="Back Squat")
        ex_first = _strength_ex("EX-002", name="Cable Row")
        session = _strength_session("S-1", [ex_hit, ex_first])
        l2c = _layer2c("home", [
            _resolved("EX-001", "Back Squat", patterns=["Squat"]),
            _resolved("EX-002", "Cable Row", patterns=["Pull"]),
        ])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=5, weight=185)})

        _, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        meta = diag.to_metadata()["track2_slice2d_rx_wire"]
        assert meta["exercise_count"] == 2
        assert meta["current_rx_hits"] == 1
        assert meta["first_exposure_count"] == 1
        assert meta["skipped_count"] == 0
        assert len(meta["outcomes"]) == 2
        paths = {o["path"] for o in meta["outcomes"]}
        assert paths == {"current_rx", "first_exposure"}
