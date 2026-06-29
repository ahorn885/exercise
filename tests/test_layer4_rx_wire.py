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
    _parse_target_reps,
    _round_to_gym_increment,
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
    reps_per_set: int | str = 8,
    coaching_flags: list[str] | None = None,
) -> StrengthExercise:
    return StrengthExercise(
        exercise_id=ex_id,
        exercise_name=name or ex_id,
        resolution_tier=1,
        sets=3,
        reps_per_set=reps_per_set,
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
        # 83.9 kg ≈ 185 lb. Baseline reps (8) == the block's prescribed reps (8),
        # so the phase-aware step is a no-op and the logged weight renders as-is.
        ex = _strength_ex("EX-001", name="Back Squat", reps_per_set=8)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=8, weight=83.9146)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        # Load-only: view.html prepends `sets × reps @`, so the prescription
        # field carries the weight alone (no double-rendered `3 × 5 @ ...`).
        assert result_ex.load_prescription == "185 lb"
        assert "first_exposure" not in result_ex.coaching_flags
        assert diag.current_rx_hits == 1
        assert diag.first_exposure_count == 0
        assert diag.outcomes[0].path == "current_rx"

    def test_nonnumeric_reps_falls_back_to_logged_weight(self):
        # A non-numeric scheme ("AMRAP") yields no target reps → the %1RM step
        # is skipped and the logged weight renders unadjusted, rounded to the
        # whole lb (84.6 kg → 186.5 lb → "187 lb"). Covers the fallback path's
        # whole-number display (#469).
        ex = _strength_ex("EX-001", name="Back Squat", reps_per_set="AMRAP")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=5, weight=84.6)})

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "187 lb"

    def test_duration_only_renders_seconds(self):
        ex = _strength_ex("EX-PLANK", name="Plank")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-PLANK", "Plank", patterns=["Anti-Extension"])])
        db = _FakeDb({("Plank", 1): _row(sets=3, reps=None, weight=None, duration=45)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "45s"
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


class TestEXIdLookup:
    """#335 Phase 2b — the lookup keys off the layer0 EX-id first, falling back
    to the legacy name path only for rows not yet backfilled."""

    def test_resolves_via_ex_id_when_name_would_miss(self):
        # Seed ONLY by EX-id (NOT by name). A hit proves the EX-id path
        # resolved — the name path ("Back Squat (Barbell)") would have missed
        # against the bare logged name, which is the whole #335 bug.
        ex = _strength_ex("EX001", name="Back Squat (Barbell)", reps_per_set=5)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat (Barbell)", patterns=["Squat"])])
        db = _FakeDb({("EX001", 1): _row(sets=3, reps=5, weight=83.9146)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == "185 lb"  # reps match → no-op
        assert diag.current_rx_hits == 1
        assert diag.first_exposure_count == 0

    def test_falls_back_to_name_when_no_ex_id_row(self):
        # No EX-id row seeded → the name path resolves the not-yet-backfilled
        # baseline (the transitional state until the backfill runs in prod).
        ex = _strength_ex("EX001", name="Back Squat", reps_per_set=5)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("Back Squat", 1): _row(sets=3, reps=5, weight=83.9146)})

        new_payload, diag = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "185 lb"
        assert diag.current_rx_hits == 1

    def test_ex_id_row_wins_over_name_row(self):
        # Both seeded with different weights → the EX-id row must win.
        ex = _strength_ex("EX001", name="Back Squat", reps_per_set=8)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({
            ("EX001", 1): _row(sets=3, reps=8, weight=90.7),       # ≈ 200 lb
            ("Back Squat", 1): _row(sets=3, reps=8, weight=45.36),  # ≈ 100 lb
        })

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "200 lb"


class TestPhaseAwareLoad:
    """#335 Phase 2b D5b — the logged baseline is re-expressed at the block's
    prescribed reps via Epley + its inverse, rounded to a gym increment."""

    def test_heavier_when_phase_prescribes_fewer_reps(self):
        # Logged 100 kg × 10; phase calls for 5 reps → heavier working load.
        # est_1RM = 100·(1+10/30) = 133.3; load = 133.3/(1+5/30) = 114.3 kg
        # ≈ 251.9 lb → rounds to 250 lb.
        ex = _strength_ex("EX001", name="Back Squat", reps_per_set=5)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("EX001", 1): _row(sets=3, reps=10, weight=100.0)})

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "250 lb"

    def test_lighter_when_phase_prescribes_more_reps(self):
        # Logged 100 kg × 5; phase calls for 12 reps → lighter working load.
        # est_1RM = 100·(1+5/30) = 116.7; load = 116.7/(1+12/30) = 83.4 kg
        # ≈ 183.8 lb → rounds to 185 lb.
        ex = _strength_ex("EX001", name="Back Squat", reps_per_set=12)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("EX001", 1): _row(sets=3, reps=5, weight=100.0)})

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "185 lb"

    def test_rep_range_uses_midpoint(self):
        # "8-12" → midpoint 10. Logged 100 kg × 10 → load at 10 reps == baseline
        # (est_1RM/(1+10/30) == logged weight) → 100 kg ≈ 220 lb.
        ex = _strength_ex("EX001", name="Back Squat", reps_per_set="8-12")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("EX001", 1): _row(sets=3, reps=10, weight=100.0)})

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "220 lb"

    def test_no_baseline_reps_renders_logged_weight(self):
        # A bootstrapped row with weight but no reps can't seed an est-1RM →
        # the logged weight renders unadjusted (90.7 kg → 200 lb).
        ex = _strength_ex("EX001", name="Back Squat", reps_per_set=5)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb({("EX001", 1): _row(sets=3, reps=None, weight=90.7)})

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        assert new_payload.sessions[0].strength_exercises[0].load_prescription == "200 lb"


class TestRepsAndRounding:
    """Direct unit coverage of the load helpers."""

    def test_parse_int_reps(self):
        assert _parse_target_reps(8) == 8

    def test_parse_zero_and_negative(self):
        assert _parse_target_reps(0) is None

    def test_parse_bool_guarded(self):
        # bool is an int subclass — must not be read as reps.
        assert _parse_target_reps(True) is None

    def test_parse_single_string(self):
        assert _parse_target_reps("10") == 10

    def test_parse_range_midpoint(self):
        assert _parse_target_reps("8-12") == 10

    def test_parse_nonnumeric(self):
        assert _parse_target_reps("AMRAP") is None
        assert _parse_target_reps(None) is None

    def test_round_imperial_nearest_5lb(self):
        # 114.3 kg ≈ 251.9 lb → 250 lb → back to ≈ 113.4 kg.
        rounded = _round_to_gym_increment(114.3, "imperial")
        from units import kg_to_lb
        assert round(kg_to_lb(rounded)) == 250

    def test_round_metric_nearest_2_5kg(self):
        assert _round_to_gym_increment(83.4, "metric") == 82.5


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
        load_q, note = _FIRST_EXPOSURE_TEMPLATES["compound_barbell"]
        # #962 — the load slot carries the load-only qualifier; the longer
        # calibration framing lands in instructions, not the `@`-load field.
        assert result_ex.load_prescription == load_q
        assert note in result_ex.instructions
        assert "first_exposure" in result_ex.coaching_flags
        assert diag.outcomes[0].category == "compound_barbell"

    def test_compound_dumbbell_template(self):
        ex = _strength_ex("EX-002", name="Dumbbell Goblet Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-002", "Dumbbell Goblet Squat", patterns=["Squat"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["compound_dumbbell"][0]

    def test_accessory_dumbbell_template(self):
        # No compound pattern in the resolved entry → accessory.
        ex = _strength_ex("EX-003", name="Dumbbell Curl")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-003", "Dumbbell Curl", patterns=["Curl"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["accessory_dumbbell"][0]

    def test_accessory_cable_template(self):
        ex = _strength_ex("EX-004", name="Cable Row")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-004", "Cable Row", patterns=["Pull"])])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["accessory_cable"][0]

    def test_bodyweight_template_via_tier(self):
        """Layer2C tier 0/3 → bodyweight category regardless of name."""
        ex = _strength_ex("EX-005", name="Air Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-005", "Air Squat", patterns=["Squat"], tier=3)])
        db = _FakeDb()

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["bodyweight"][0]

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
        assert result_ex.load_prescription == _FIRST_EXPOSURE_TEMPLATES["bodyweight"][0]


class TestFirstExposureRender:
    """#962 — the first-exposure write must not garble the rendered
    `{sets} × {reps} @ {load_prescription}` string: the load slot carries a
    load-only qualifier with NO rep count, and the calibration framing lands in
    instructions on its own line."""

    def test_load_qualifier_has_no_rep_count(self):
        # The load slot must not name a rep count (it would collide with the
        # structured `reps_per_set` — "3 × 6 @ ... RPE 6 for 8 reps").
        for category, (load_q, _note) in _FIRST_EXPOSURE_TEMPLATES.items():
            assert "rep" not in load_q.lower() or "reserve" in load_q.lower(), (
                f"{category} load qualifier names reps: {load_q!r}"
            )

    def test_calibration_note_goes_to_instructions_not_load(self):
        ex = _strength_ex("EX-001", name="Back Squat", reps_per_set=6)
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb()  # first exposure

        new_payload, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})

        result_ex = new_payload.sessions[0].strength_exercises[0]
        load_q, note = _FIRST_EXPOSURE_TEMPLATES["compound_barbell"]
        assert result_ex.load_prescription == load_q
        # The note is in instructions, NOT bleeding into the load field.
        assert note in result_ex.instructions
        assert note not in result_ex.load_prescription
        # The original LLM execution cue is preserved alongside the note.
        assert "Standard execution." in result_ex.instructions
        # The full rendered prescription reads cleanly — the load slot adds no
        # second rep count after the structured "3 × 6".
        rendered = f"{result_ex.sets} × {result_ex.reps_per_set} @ {result_ex.load_prescription}"
        assert rendered == "3 × 6 @ RPE 6 — first session, set your baseline"

    def test_note_merge_idempotent_on_rerun(self):
        # rx_wire re-runs on refresh; the calibration note must not stack twice.
        ex = _strength_ex("EX-001", name="Back Squat")
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", "Back Squat", patterns=["Squat"])])
        db = _FakeDb()

        once, _ = apply_current_rx(_payload([session]), db, 1, {"home": l2c})
        twice, _ = apply_current_rx(once, db, 1, {"home": l2c})

        _load_q, note = _FIRST_EXPOSURE_TEMPLATES["compound_barbell"]
        instr = twice.sessions[0].strength_exercises[0].instructions
        assert instr.count(note) == 1


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
