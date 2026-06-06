"""Tests for `layer4.locale_assign` — Track 2 slice 2c §5.5."""

from __future__ import annotations

from datetime import date

import pytest

from layer4.context import (
    AccommodationModality,
    DisciplineCoverage,
    Layer2CPayload,
    ResolvedExercise,
)
from layer4.locale_assign import (
    ExerciseSubstitution,
    LocaleAssignDiagnostic,
    SessionAssignment,
    assign_locales,
)
from layer4.payload import PlanSession, StrengthExercise


# ─── Fixtures ──────────────────────────────────────────────────────────────


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
        tier=tier,  # 1=ideal, 0/3=bodyweight proxy band
        resolution_detail=None,
        terrain_required=[],
        contraindicated_parts=[],
        contraindicated_conditions=[],
        accommodations=[],
    )


def _layer2c(
    locale_id: str,
    exercises: list[ResolvedExercise],
) -> Layer2CPayload:
    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"0A": "0A-v11.0", "0B": "0B-v11.0", "0C": "0C-v2.0-r2"},
        effective_pool=["Barbell", "Squat rack"],
        discipline_coverage=[],
        exercises_resolved=exercises,
        coaching_flags=[],
    )


def _strength_exercise(
    ex_id: str,
    *,
    patterns: list[str] | None = None,
) -> StrengthExercise:
    return StrengthExercise(
        exercise_id=ex_id,
        exercise_name=ex_id,
        resolution_tier=1,
        sets=3,
        reps_per_set=8,
        load_prescription="RPE 7",
        rest_between_sets_sec=90,
        instructions="Standard execution.",
        coaching_flags=[],
    )


def _strength_session(
    sid: str,
    exercises: list[StrengthExercise],
    *,
    date_: date | None = None,
) -> PlanSession:
    return PlanSession(
        session_id=sid,
        plan_version_id=1,
        date=date_ or date(2026, 6, 1),
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


def _cardio_session(sid: str, *, locale_id: str | None = None) -> PlanSession:
    from layer4.payload import CardioBlock, HRTarget

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
        locale_id=locale_id,
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


# ─── Tests ─────────────────────────────────────────────────────────────────


class TestPickLocaleByMajorityFit:
    """§5.5 step 2-3."""

    def test_single_locale_assigns_home(self):
        ex = _strength_exercise("EX-001", patterns=["Squat"])
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", patterns=["Squat"])])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": l2c},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
        )

        assert len(new_sessions) == 1
        assert new_sessions[0].locale_id == "home"
        assert diag.assignments[0].chosen_locale == "home"
        assert diag.assignments[0].fit_count == 1

    def test_picks_higher_fit_locale_over_home(self):
        """Home covers 1 of 3 exercises; alt locale covers 3 of 3 → alt wins."""
        exs = [
            _strength_exercise("EX-001", patterns=["Squat"]),
            _strength_exercise("EX-002", patterns=["Hinge"]),
            _strength_exercise("EX-003", patterns=["Lunge"]),
        ]
        session = _strength_session("S-1", exs)
        home = _layer2c("home", [_resolved("EX-001", patterns=["Squat"])])
        alt = _layer2c("alt", [
            _resolved("EX-001", patterns=["Squat"]),
            _resolved("EX-002", patterns=["Hinge"]),
            _resolved("EX-003", patterns=["Lunge"]),
        ])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "alt": alt},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home", "alt"],
        )

        assert new_sessions[0].locale_id == "alt"
        assert diag.assignments[0].fit_count == 3

    def test_tie_breaks_to_home(self):
        """Both locales cover 1 of 1 → home wins on tie."""
        ex = _strength_exercise("EX-001", patterns=["Squat"])
        session = _strength_session("S-1", [ex])
        home = _layer2c("home", [_resolved("EX-001", patterns=["Squat"])])
        alt = _layer2c("alt", [_resolved("EX-001", patterns=["Squat"])])

        new_sessions, _ = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "alt": alt},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home", "alt"],
        )

        assert new_sessions[0].locale_id == "home"

    def test_tie_among_non_home_uses_alphabetical(self):
        """Three locales all cover 0; tie → home wins. Test the alphabetical
        secondary tiebreak when home isn't in the cluster (degenerate case
        used for explicit determinism guarantee)."""
        ex = _strength_exercise("EX-NONE", patterns=["Other"])
        session = _strength_session("S-1", [ex])
        # All three locales have empty resolved sets → all tie at fit=0
        b = _layer2c("b_locale", [])
        a = _layer2c("a_locale", [])
        z = _layer2c("z_locale", [])

        new_sessions, _ = assign_locales(
            sessions=[session],
            layer2c_payloads={"b_locale": b, "a_locale": a, "z_locale": z},
            db=None,
            user_id=1,
            home_locale_id="missing_home",  # not in cluster → alphabetical applies
            cluster_locale_ids=["b_locale", "a_locale", "z_locale"],
        )

        assert new_sessions[0].locale_id == "a_locale"


class TestSubstitutionLadder:
    """§5.5 step 4-6."""

    def test_pattern_match_substitute(self):
        """Original doesn't fit chosen locale but a pattern-sharing exercise
        is in the chosen pool. The original's movement_patterns live on the
        ResolvedExercise side (cluster-union), not on the StrengthExercise
        payload — so the original must be findable somewhere in
        layer2c_payloads for the pattern lookup to succeed."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        # Home pool has EX-ALT (pattern=Squat). The original EX-MISSING is in
        # the cluster-union via a separate locale's pool (mimics multi-locale
        # cluster; chosen will still be home since it has more fit).
        home = _layer2c("home", [
            _resolved("EX-ALT", patterns=["Squat"], tier=1),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["Squat"], tier=1),
        ])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],  # elsewhere is in payloads but not cluster
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-ALT"
        assert new_ex.resolution_tier == 2
        assert new_ex.substitute_text is not None
        sub = diag.assignments[0].substitutions[0]
        assert sub.path == "pattern_match"
        assert sub.substitute_exercise_id == "EX-ALT"

    def test_tier3_proxy_when_no_pattern_match(self):
        """No tier-1 pattern match; falls through to a tier-3 bodyweight proxy."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        home = _layer2c("home", [
            _resolved("EX-BW-SQUAT", patterns=["Squat"], tier=3),
        ])
        # Cluster-union must include EX-MISSING for pattern lookup.
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["Squat"], tier=1),
        ])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-BW-SQUAT"
        assert new_ex.resolution_tier == 3
        assert new_ex.proxy_origin_id == "EX-MISSING"
        sub = diag.assignments[0].substitutions[0]
        assert sub.path == "tier3_proxy"

    def test_pattern_match_preferred_over_proxy(self):
        """When BOTH a tier-1 match and a tier-3 proxy exist, the pattern-match
        path wins (it's the first rung of the ladder)."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        home = _layer2c("home", [
            _resolved("EX-T1", patterns=["Squat"], tier=1),
            _resolved("EX-BW", patterns=["Squat"], tier=3),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["Squat"], tier=1),
        ])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-T1"
        assert new_ex.resolution_tier == 2  # pattern-match substitute

    def test_coaching_flag_tail_when_no_candidate(self):
        """No pattern match and no tier-3 proxy → original kept, flag added."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        # Home has no pattern match for "VeryNiche" (only Squat).
        home = _layer2c("home", [
            _resolved("EX-UNRELATED", patterns=["Squat"], tier=1),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["VeryNiche"], tier=1),
        ])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-MISSING"  # original kept
        assert new_ex.resolution_tier == 1
        assert "substitution_no_candidate" in new_ex.coaching_flags
        sub = diag.assignments[0].substitutions[0]
        assert sub.path == "no_candidate"


class TestLLMSubstituteFallback:
    """§5.5 step 6 — small-call LLM, budget-gated."""

    def test_llm_called_when_pattern_and_tier3_miss(self):
        """No pattern match, no tier-3 proxy, LLM caller wired → LLM picks."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        home = _layer2c("home", [
            _resolved("EX-ALT", patterns=["Squat"], tier=1),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["VeryNiche"], tier=1),
        ])

        # Mock LLM caller — returns EX-ALT.
        def fake_caller(*, model, system_prompt, tool, max_tokens):
            return {"substitute_exercise_id": "EX-ALT", "preserves_intent": False}

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
            llm_substitute_caller=fake_caller,
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-ALT"
        assert new_ex.resolution_tier == 2
        assert diag.llm_calls == 1
        sub = diag.assignments[0].substitutions[0]
        assert sub.path == "llm_substitute"

    def test_llm_call_budget_respected(self):
        """≤1 LLM call per assign_locales invocation (per spec §5.5 step 6)."""
        ex1 = _strength_exercise("EX-MISS-1")
        ex2 = _strength_exercise("EX-MISS-2")
        session = _strength_session("S-1", [ex1, ex2])
        home = _layer2c("home", [
            _resolved("EX-ALT", patterns=["Squat"], tier=1),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISS-1", patterns=["Niche1"], tier=1),
            _resolved("EX-MISS-2", patterns=["Niche2"], tier=1),
        ])

        call_count = 0

        def fake_caller(*, model, system_prompt, tool, max_tokens):
            nonlocal call_count
            call_count += 1
            return {"substitute_exercise_id": "EX-ALT", "preserves_intent": False}

        _, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
            llm_substitute_caller=fake_caller,
        )

        assert call_count == 1
        assert diag.llm_calls == 1
        # Second stuck exercise hits coaching-flag tail (budget exhausted).
        assert any(s.path == "no_candidate" for s in diag.assignments[0].substitutions)

    def test_llm_returns_out_of_pool_id_falls_through_to_flag(self):
        """LLM hallucinates an exercise_id outside the bounded pool → ignored,
        coaching-flag tail fires. Defensive — the enum schema should prevent
        this at the SDK boundary, but we trust nothing from a tool result."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        home = _layer2c("home", [
            _resolved("EX-ALT", patterns=["Squat"], tier=1),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["VeryNiche"], tier=1),
        ])

        def fake_caller(*, model, system_prompt, tool, max_tokens):
            return {"substitute_exercise_id": "EX-HALLUCINATED", "preserves_intent": True}

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
            llm_substitute_caller=fake_caller,
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-MISSING"  # original kept
        assert "substitution_no_candidate" in new_ex.coaching_flags

    def test_llm_caller_none_skips_to_flag(self):
        """When the small-call LLM caller is unwired (None), the impossible
        tail goes straight to the coaching_flag, never raises."""
        ex = _strength_exercise("EX-MISSING")
        session = _strength_session("S-1", [ex])
        home = _layer2c("home", [
            _resolved("EX-ALT", patterns=["Squat"], tier=1),
        ])
        elsewhere = _layer2c("elsewhere", [
            _resolved("EX-MISSING", patterns=["VeryNiche"], tier=1),
        ])

        new_sessions, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": home, "elsewhere": elsewhere},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
            llm_substitute_caller=None,
        )

        new_ex = new_sessions[0].strength_exercises[0]
        assert new_ex.exercise_id == "EX-MISSING"
        assert "substitution_no_candidate" in new_ex.coaching_flags
        assert diag.llm_calls == 0


class TestNonStrengthUntouched:
    """Cardio + rest sessions should pass through unchanged."""

    def test_cardio_session_untouched(self):
        cardio = _cardio_session("C-1", locale_id="some_locale")
        l2c = _layer2c("home", [])

        new_sessions, diag = assign_locales(
            sessions=[cardio],
            layer2c_payloads={"home": l2c},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
        )

        assert len(new_sessions) == 1
        assert new_sessions[0].locale_id == "some_locale"  # unchanged
        # No assignment entry for non-strength sessions
        assert len(diag.assignments) == 0


class TestDiagnosticMetadata:
    """The LocaleAssignDiagnostic must serialize cleanly to JSON-safe dict
    for `synthesis_metadata` inclusion (Rule #14 observability)."""

    def test_to_metadata_shape(self):
        ex = _strength_exercise("EX-001", patterns=["Squat"])
        session = _strength_session("S-1", [ex])
        l2c = _layer2c("home", [_resolved("EX-001", patterns=["Squat"])])

        _, diag = assign_locales(
            sessions=[session],
            layer2c_payloads={"home": l2c},
            db=None,
            user_id=1,
            home_locale_id="home",
            cluster_locale_ids=["home"],
        )
        meta = diag.to_metadata()
        assert "track2_slice2c_locale_assign" in meta
        block = meta["track2_slice2c_locale_assign"]
        assert block["session_count"] == 1
        assert block["llm_substitute_calls"] == 0
        assert block["home_locale_id"] == "home"
        assert block["cluster_locale_ids"] == ["home"]
        assert len(block["assignments"]) == 1
        assignment = block["assignments"][0]
        assert assignment["session_id"] == "S-1"
        assert assignment["chosen_locale"] == "home"
        assert len(assignment["substitutions"]) == 1
        assert assignment["substitutions"][0]["path"] == "kept"
