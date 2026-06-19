"""Tests for `layer2d.builder.q_layer2d_injury_risk_profile_payload`.

Coverage maps to `Layer2D_Spec.md` §13 test scenarios + §10 edge cases:

- §4 input validation (empty disciplines, missing ETL keys, non-list args)
- §13.1 Andy baseline — Chronic-Managed Tendinopathy/overuse on Left Wrist
- §13.2 Post-surgical scenario — ACL reconstruction, no clearance notes → HITL block
- §13.3 Concussion history — `condition_history_informational` flag, no HITL
- §13.4 Current asthma (Respiratory, Active) — accommodation via condition match
- §13.5 Clean baseline — no injuries, no conditions, fast path
- §13.6 Multi-injury cumulative load — `multi_body_part_load_concern` fires
- §13.7 D-020 Swimrun gap × HIGH risk — `gap_x_high_risk_concurrent` HITL
- §5.3.4 severity → verdict mapping (Acute → exclude; Recovering → accommodate)
- §5.3.6 modality dispatch (Tendinopathy / Chronic-Managed → HSR tempo)
- §5.3.6.4 phase contraindication (acute tendinopathy forces isometric)
- §5.6.1 substitute back-check (still_at_risk flag)
- §5.7 cardiac × high-load → HITL block
- §10 body-part vocab miss → coaching flag, not failure

Fixtures use the `_FakeConn` / `_FakeCursor` pattern matching
`tests/test_layer2a.py`. Each test queues one row-set per SQL call the
builder makes (candidates query, disciplines query, training-gaps query,
optionally per-discipline substitutes queries).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from layer2d import Layer2DInputError, q_layer2d_injury_risk_profile_payload
from layer4.context import (
    HealthConditionRecord,
    InjuryRecord,
    Layer2DPayload,
    TempoModificationModality,
    VolumeReductionModality,
)


# ─── Fakes ───────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[list] = []

    def queue_response(self, rows=None):
        self.responses.append(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows=rows)


# ─── Row helpers ─────────────────────────────────────────────────────────────


def _exercise(
    eid: str,
    name: str,
    discipline_id: str,
    *,
    contraindicated_parts: list[str] | None = None,
    contraindicated_conditions: list[str] | None = None,
    injury_flags_text: str | None = None,
    priority: str = "core",
) -> dict:
    """Builds one row of the §5.2 candidates query (pre-dedupe)."""
    return {
        "exercise_id": eid,
        "exercise_name": name,
        "exercise_type": "compound",
        "priority": priority,
        "contraindicated_parts": contraindicated_parts or [],
        "contraindicated_conditions": contraindicated_conditions or [],
        "injury_flags_text": injury_flags_text,
        "movement_patterns": [],
        "discipline_id": discipline_id,
    }


def _discipline(
    discipline_id: str,
    name: str,
    *,
    common_injury_patterns: list[str] | None = None,
) -> dict:
    return {
        "discipline_id": discipline_id,
        "discipline_name": name,
        "common_injury_patterns": common_injury_patterns or [],
    }


def _substitute(
    target_id: str,
    substitute_id: str,
    name: str,
    *,
    fidelity: float = 0.7,
    category: str | None = "cross-modality",
    constraints: str | None = None,
    substitute_patterns: list[str] | None = None,
) -> dict:
    return {
        "substitute_id": substitute_id,
        "substitute_name": name,
        "fidelity": fidelity,
        "constraints": constraints,
        "category": category,
        "substitute_covers": [],
        "substitute_patterns": substitute_patterns,
    }


def _injury(
    body_part: str,
    *,
    status: str = "Active",
    severity: str | None = "Chronic-Managed",
    injury_type: str | None = "Tendinopathy / overuse",
    movement_constraints: list[str] | None = None,
    side: str = "Left",
    start_date: date | None = None,
    description: str | None = None,
    modifications_needed: str | None = None,
    injury_id: int = 1,
) -> InjuryRecord:
    return InjuryRecord(
        injury_id=injury_id,
        body_part=body_part,
        description=description,
        severity=severity,  # type: ignore[arg-type]
        injury_type=injury_type,  # type: ignore[arg-type]
        side=side,  # type: ignore[arg-type]
        movement_constraints=movement_constraints or [],
        status=status,  # type: ignore[arg-type]
        start_date=start_date or date(2026, 1, 1),
        resolved_date=None,
        modifications_needed=modifications_needed,
    )


def _condition(
    category: str,
    name: str,
    *,
    status: str = "Active",
    severity: int | None = None,
    notes: str | None = None,
    condition_id: int = 1,
) -> HealthConditionRecord:
    return HealthConditionRecord(
        condition_id=condition_id,
        system_category=category,  # type: ignore[arg-type]
        condition_name=name,
        severity=severity,
        notes=notes,
        status=status,  # type: ignore[arg-type]
        start_date=date(2025, 1, 1),
        resolved_date=None,
    )


_PIN = {"0A": "0A-v10", "0B": "0B-v19.C", "0C": "0C-v3"}


# ─── §4 input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def test_non_list_injuries_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2DInputError):
            q_layer2d_injury_risk_profile_payload(
                conn, "not a list", [], ["D-001"], etl_version_set=_PIN,  # type: ignore[arg-type]
            )

    def test_non_list_conditions_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2DInputError):
            q_layer2d_injury_risk_profile_payload(
                conn, [], "not a list", ["D-001"], etl_version_set=_PIN,  # type: ignore[arg-type]
            )

    def test_empty_disciplines_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2DInputError):
            q_layer2d_injury_risk_profile_payload(
                conn, [], [], [], etl_version_set=_PIN,
            )

    def test_missing_etl_keys_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2DInputError):
            q_layer2d_injury_risk_profile_payload(
                conn, [], [], ["D-001"], etl_version_set={"0A": "v1"},
            )

    def test_non_dict_etl_set_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2DInputError):
            q_layer2d_injury_risk_profile_payload(
                conn, [], [], ["D-001"], etl_version_set="bad",  # type: ignore[arg-type]
            )


# ─── §13.5 clean baseline ────────────────────────────────────────────────────


class TestCleanBaseline:
    def test_no_injuries_no_conditions_all_clean(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise("E-001", "Squat", "D-001"),
            _exercise("E-002", "Pushup", "D-001"),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])  # training_gaps empty
        payload = q_layer2d_injury_risk_profile_payload(
            conn, [], [], ["D-001"], etl_version_set=_PIN,
        )
        assert payload.excluded_exercises == []
        assert payload.accommodated_exercises == []
        assert sorted(payload.clean_exercise_ids) == ["E-001", "E-002"]
        assert payload.discipline_risk_profiles[0].risk_level == "low"
        assert payload.coaching_flags == []
        assert payload.hitl_required is False
        assert payload.hitl_items == []


# ─── §13.1 Andy baseline — Chronic-Managed wrist tendinopathy ────────────────


class TestAndyBaseline:
    def test_chronic_wrist_accommodates_with_hsr_tempo(self):
        conn = _FakeConn()
        # Pushup contraindicates Wrist; bench press too
        conn.queue_response(rows=[
            _exercise(
                "E-PUSHUP", "Standard Pushup", "D-012",
                contraindicated_parts=["Wrist"],
                injury_flags_text="palm-down loading at end-range wrist extension",
            ),
            _exercise(
                "E-PULLUP", "Pullup", "D-012",
                contraindicated_parts=[],
                injury_flags_text=None,
            ),
        ])
        conn.queue_response(rows=[
            _discipline(
                "D-012", "Rock Climbing",
                common_injury_patterns=[
                    "Wrist flexor / extensor strain",
                    "Finger pulley tear",
                ],
            ),
        ])
        conn.queue_response(rows=[])  # training_gaps
        conn.queue_response(rows=[
            _substitute(
                "D-012", "D-009", "Packrafting", fidelity=0.6,
                substitute_patterns=["Wrist tendinitis (paddle bracing)"],
            ),
        ])
        injuries = [_injury(
            "Left Wrist",
            severity="Chronic-Managed",
            injury_type="Tendinopathy / overuse",
            movement_constraints=["Pain above specific joint angle", "Pain with loading"],
            modifications_needed="fist pushups only",
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-012"], etl_version_set=_PIN,
        )
        # Pushup is accommodated (Chronic-Managed → ACCOMMODATE per §5.3.4)
        assert len(payload.accommodated_exercises) == 1
        assert payload.accommodated_exercises[0].exercise_id == "E-PUSHUP"
        accs = payload.accommodated_exercises[0].accommodations
        # §5.3.6 Tendinopathy / overuse + Chronic-Managed → tempo_hsr
        assert any(
            isinstance(a, TempoModificationModality)
            and a.tempo_pattern == "heavy_slow_resistance"
            for a in accs
        )
        # Pullup with no contraindication = CLEAN
        assert payload.clean_exercise_ids == ["E-PULLUP"]
        # Discipline-level: D-012 elevated; substitute back-check flags
        # Packrafting as still_at_risk for Wrist
        dr = payload.discipline_risk_profiles[0]
        assert dr.risk_level == "elevated"
        assert dr.suggested_substitutes[0].still_at_risk is True
        assert "Wrist" in dr.suggested_substitutes[0].still_at_risk_body_parts
        # Coaching flags: elevated + substitution_suggested
        flag_types = {f.flag_type for f in payload.coaching_flags}
        assert "elevated_discipline_risk" in flag_types
        assert "discipline_substitution_suggested" in flag_types
        # HITL false (Chronic-Managed isn't a HITL trigger)
        assert payload.hitl_required is False


# ─── §5.3.4 severity → verdict ───────────────────────────────────────────────


class TestSeverityToVerdict:
    def test_acute_severity_excludes(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise(
                "E-001", "Bench", "D-001",
                contraindicated_parts=["Shoulder"],
            ),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Cycling")])
        conn.queue_response(rows=[])
        injuries = [_injury(
            "Left Shoulder",
            severity="Acute",
            injury_type="Acute soft tissue (strain / sprain / tear)",
            movement_constraints=["Pain with overhead movement"],
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        assert len(payload.excluded_exercises) == 1
        assert payload.excluded_exercises[0].verdict == "exclude"
        assert payload.accommodated_exercises == []

    def test_recovering_severity_accommodates(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise(
                "E-001", "Bench", "D-001",
                contraindicated_parts=["Shoulder"],
            ),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Cycling")])
        conn.queue_response(rows=[])
        injuries = [_injury(
            "Left Shoulder",
            severity="Recovering",
            injury_type="Acute soft tissue (strain / sprain / tear)",
            movement_constraints=[],
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        assert payload.excluded_exercises == []
        assert len(payload.accommodated_exercises) == 1
        # Recovering soft tissue → volume + intensity per V1_DEFAULT
        modality_types = {
            type(a).__name__
            for a in payload.accommodated_exercises[0].accommodations
        }
        assert "VolumeReductionModality" in modality_types


# ─── §5.3.6.4 phase contraindication — acute tendinopathy forces isometric ───


class TestAcuteTendinopathyOverride:
    def test_acute_tendinopathy_emits_isometric_only(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise(
                "E-001", "Calf Raise", "D-001",
                contraindicated_parts=["Achilles"],
            ),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Running")])
        conn.queue_response(rows=[])
        injuries = [_injury(
            "Achilles",
            side="N/A",
            severity="Acute",
            injury_type="Tendinopathy / overuse",
            movement_constraints=[],
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        # Acute → EXCLUDE per §5.3.4, no accommodations
        assert len(payload.excluded_exercises) == 1
        assert payload.excluded_exercises[0].accommodations == []


# ─── §13.2 Post-surgical without clearance → HITL block ──────────────────────


class TestPostSurgicalHitl:
    def test_post_surgical_no_clearance_blocks(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise(
                "E-001", "Squat", "D-001",
                contraindicated_parts=["Knee"],
            ),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        injuries = [_injury(
            "Right Knee",
            severity="Post-surgical",
            injury_type="Joint (mechanical) — surgical",
            side="Right",
            description="ACL reconstruction",
            modifications_needed=None,  # no clearance
            start_date=date.today() - timedelta(days=60),
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        assert payload.hitl_required is True
        block_items = [i for i in payload.hitl_items if i.severity == "block"]
        assert any(i.hitl_type == "post_surgical_clearance" for i in block_items)

    def test_post_surgical_with_clearance_warns_not_blocks(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise(
                "E-001", "Squat", "D-001",
                contraindicated_parts=["Knee"],
            ),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        injuries = [_injury(
            "Right Knee",
            severity="Post-surgical",
            injury_type="Joint (mechanical) — surgical",
            description="ACL reconstruction; surgeon cleared 2026-05-01",
            modifications_needed="Released to train per ortho clearance",
            start_date=date.today() - timedelta(days=60),
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        post_surgical_items = [
            i for i in payload.hitl_items if i.hitl_type == "post_surgical_clearance"
        ]
        assert len(post_surgical_items) == 1
        assert post_surgical_items[0].severity == "warn"


# ─── #202 — post-surgical recency anchored to `today` (cache-key determinism) ─


class TestPostSurgicalRecencyDeterminism:
    """#202: `_is_recent_post_surgical` must key off the cone's day-anchored
    `today`, not wall-clock `utcnow()`. The recency bool drives the
    cross-education loading swap, whose modality rides in the Layer2D payload →
    `layer2d_hash` → `plan_create_key`; a wall-clock anchor would drift that
    cache key across a calendar boundary between resumable passes, the exact
    non-convergence class #202 hunts."""

    def test_recency_window_keys_off_passed_today_not_wall_clock(self):
        from layer2d.builder import _is_recent_post_surgical

        start = date(2026, 3, 1)
        injury = _injury(
            "Right Knee",
            severity="Post-surgical",
            injury_type="Joint (mechanical) — surgical",
            start_date=start,
        )
        # Anchored entirely on the passed `today`: inside vs outside the 42-day
        # window flips on the boundary, independent of when the test runs.
        assert _is_recent_post_surgical(injury, start + timedelta(days=20)) is True
        assert _is_recent_post_surgical(injury, start + timedelta(days=41)) is True
        assert _is_recent_post_surgical(injury, start + timedelta(days=42)) is False
        assert _is_recent_post_surgical(injury, start + timedelta(days=60)) is False
        # Deterministic: same `today` → same verdict, every call.
        anchor = start + timedelta(days=20)
        assert _is_recent_post_surgical(injury, anchor) == _is_recent_post_surgical(
            injury, anchor
        )

    def test_payload_hash_stable_across_passes_for_same_today(self):
        """The public entry accepts the day-anchored `today` and two builds with
        the same `today` produce an identical payload hash — the #202
        convergence guarantee carried through `layer2d_hash`."""
        from layer4.hashing import compute_payload_hash

        def _build(today: date):
            conn = _FakeConn()
            conn.queue_response(rows=[
                _exercise("E-001", "Squat", "D-001", contraindicated_parts=["Knee"]),
            ])
            conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
            conn.queue_response(rows=[])
            injuries = [_injury(
                "Right Knee",
                severity="Post-surgical",
                injury_type="Joint (mechanical) — surgical",
                start_date=date(2026, 3, 1),
            )]
            return q_layer2d_injury_risk_profile_payload(
                conn, injuries, [], ["D-001"], etl_version_set=_PIN, today=today,
            )

        today = date(2026, 3, 21)
        assert compute_payload_hash(_build(today)) == compute_payload_hash(_build(today))


# ─── §13.3 Concussion history (informational, no HITL) ───────────────────────


class TestConcussionHistory:
    def test_concussion_history_informational_only(self):
        conn = _FakeConn()
        conn.queue_response(rows=[_exercise("E-001", "Squat", "D-001")])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        conditions = [_condition(
            "neurological", "Concussion (2024)", status="Resolved",
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, [], conditions, ["D-001"], etl_version_set=_PIN,
        )
        assert payload.hitl_required is False
        flag_types = {f.flag_type for f in payload.coaching_flags}
        assert "condition_history_informational" in flag_types

    def test_concussion_current_blocks(self):
        conn = _FakeConn()
        conn.queue_response(rows=[_exercise("E-001", "Squat", "D-001")])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        conditions = [_condition(
            "neurological", "Concussion (current)", status="Active",
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, [], conditions, ["D-001"], etl_version_set=_PIN,
        )
        assert payload.hitl_required is True
        assert any(i.hitl_type == "concussion_current" for i in payload.hitl_items)


# ─── §5.7 rule 2 cardiac × high-load → HITL ──────────────────────────────────


class TestCardiacHighLoadHitl:
    def test_active_cardiac_with_trail_running_blocks(self):
        conn = _FakeConn()
        conn.queue_response(rows=[_exercise("E-001", "Run", "D-001")])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        conditions = [_condition(
            "cardiac", "Hypertension", status="Active",
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, [], conditions, ["D-001"], etl_version_set=_PIN,
        )
        assert payload.hitl_required is True
        assert any(
            i.hitl_type == "cardiac_high_load_review" for i in payload.hitl_items
        )


# ─── §13.4 Current respiratory — accommodation via condition ─────────────────


class TestRespiratoryAccommodation:
    def test_respiratory_current_accommodates_only_if_contraindicated(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            _exercise(
                "E-001", "VO2 Intervals", "D-001",
                contraindicated_conditions=["respiratory"],
            ),
            _exercise("E-002", "Easy Run", "D-001"),
        ])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        conditions = [_condition("respiratory", "EIB", status="Active")]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, [], conditions, ["D-001"], etl_version_set=_PIN,
        )
        # E-001 contraindicates respiratory → accommodate; E-002 clean
        assert len(payload.accommodated_exercises) == 1
        assert payload.accommodated_exercises[0].exercise_id == "E-001"
        # Accommodation routes through V1_FALLBACK (condition-driven, no injury)
        modality_types = [
            type(a).__name__
            for a in payload.accommodated_exercises[0].accommodations
        ]
        assert "VolumeReductionModality" in modality_types
        assert "IntensityReductionModality" in modality_types
        # No HITL — respiratory current isn't in §5.7 list
        assert payload.hitl_required is False


# ─── §13.6 Multi-injury cumulative load ──────────────────────────────────────


class TestMultiInjuryCumulativeLoad:
    def test_three_active_injuries_fires_load_concern(self):
        conn = _FakeConn()
        conn.queue_response(rows=[_exercise("E-001", "Squat", "D-001")])
        conn.queue_response(rows=[_discipline("D-001", "Trail Running")])
        conn.queue_response(rows=[])
        injuries = [
            _injury(
                "Left Wrist", severity="Recovering",
                injury_type="Tendinopathy / overuse",
                movement_constraints=[], injury_id=1,
            ),
            _injury(
                "Lower back", side="N/A", severity="Chronic-Managed",
                injury_type="Tendinopathy / overuse",
                movement_constraints=[], injury_id=2,
            ),
            _injury(
                "Achilles", side="N/A", severity="Recovering",
                injury_type="Tendinopathy / overuse",
                movement_constraints=[], injury_id=3,
            ),
        ]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        flag_types = {f.flag_type for f in payload.coaching_flags}
        assert "multi_body_part_load_concern" in flag_types


# ─── §13.7 D-020 gap × HIGH risk → HITL ──────────────────────────────────────


class TestGapTimesHighRisk:
    def test_gap_discipline_with_high_risk_blocks(self):
        conn = _FakeConn()
        conn.queue_response(rows=[_exercise("E-001", "Stroke", "D-020")])
        conn.queue_response(rows=[
            _discipline(
                "D-020", "Swimrun",
                common_injury_patterns=[
                    "Shoulder overuse",
                    "Rotator cuff impingement",
                ],
            ),
        ])
        conn.queue_response(rows=[{"discipline_id": "D-020"}])  # gap row
        conn.queue_response(rows=[])  # no substitutes
        injuries = [_injury(
            "Left Shoulder",
            severity="Acute",
            injury_type="Acute soft tissue (strain / sprain / tear)",
            movement_constraints=["Pain with overhead movement"],
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-020"], etl_version_set=_PIN,
        )
        # D-020 risk = HIGH (Acute shoulder + patterns match)
        assert payload.discipline_risk_profiles[0].risk_level == "high"
        # HITL: rule 4 (HIGH + no substitutes) + rule 5 (gap × HIGH)
        hitl_types = {i.hitl_type for i in payload.hitl_items}
        assert "gap_x_high_risk_concurrent" in hitl_types
        assert payload.hitl_required is True


# ─── §10 body-part vocab miss — RETIRED ──────────────────────────────────────
# The `body_part_vocab_miss` coaching flag + `Layer2DPayload.body_part_vocab_misses`
# field were retired (2026-06). The injury form's `body_part` is a closed
# structured dropdown over the canonical parts (Abdomen mapped, 'Other' catch-all
# removed), so an out-of-vocab selection can't occur; and matching falls back to
# the lowercased body part regardless (`BODY_PART_KEYWORDS.get(canonical,
# [canonical.lower()])`), so the strict key-membership audit added no value.


class TestBodyPartVocabMissRetired:
    def test_no_vocab_miss_flag_or_field(self):
        conn = _FakeConn()
        conn.queue_response(rows=[_exercise("E-001", "Squat", "D-001")])
        conn.queue_response(rows=[_discipline("D-001", "Running")])
        conn.queue_response(rows=[])
        injuries = [_injury(
            "Brain",  # historically out-of-vocab — once tripped the audit
            severity="Chronic-Managed",
            injury_type="Other / uncertain",
            movement_constraints=[],
        )]
        payload = q_layer2d_injury_risk_profile_payload(
            conn, injuries, [], ["D-001"], etl_version_set=_PIN,
        )
        flag_types = {f.flag_type for f in payload.coaching_flags}
        assert "body_part_vocab_miss" not in flag_types
        assert not hasattr(payload, "body_part_vocab_misses")


# ─── Smoke — payload constructs against empty connection ─────────────────────


class TestSmokeEmptyDB:
    def test_empty_db_returns_valid_payload(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])  # candidates
        conn.queue_response(rows=[])  # disciplines
        conn.queue_response(rows=[])  # training_gaps
        payload = q_layer2d_injury_risk_profile_payload(
            conn, [], [], ["D-999"], etl_version_set=_PIN,
        )
        assert isinstance(payload, Layer2DPayload)
        assert payload.discipline_risk_profiles[0].risk_level == "low"
        assert payload.discipline_risk_profiles[0].discipline_name == "D-999"
