"""Tests for the shared Layer-4 injury-accommodation renderer.

Locks in #555 (modality params + rationale reach the synthesizer, not just
the type name) and the create/refresh no-drift contract (both paths call this
one module).
"""

from __future__ import annotations

from types import SimpleNamespace

from layer4.context import (
    ExerciseSubstitutionModality,
    FrequencyReductionModality,
    IntensityReductionModality,
    LoadingTypeChangeModality,
    TempoModificationModality,
    VolumeReductionModality,
)
from layer4.injury_render import format_active_injuries, format_modality


class TestFormatModality:
    def test_volume_reduction_carries_factor_and_rationale(self):
        s = format_modality(
            VolumeReductionModality(
                factor=0.7, applies_to="sets",
                rationale="reduce patellar load", evidence_basis=[],
            )
        )
        assert "volume_reduction" in s
        assert "0.7" in s and "sets" in s
        assert "reduce patellar load" in s  # #555: rationale must survive

    def test_intensity_reduction_carries_metric(self):
        s = format_modality(
            IntensityReductionModality(
                factor=0.8, target_metric="percent_1rm",
                rationale="deload", evidence_basis=[],
            )
        )
        assert "0.8" in s and "percent_1rm" in s and "deload" in s

    def test_tempo_modification_lists_populated_params_only(self):
        s = format_modality(
            TempoModificationModality(
                tempo_pattern="isometric_only", hold_s=45, sets=3,
                intensity_pct_mvc=70, rationale="tendon stage 1",
                evidence_basis=[],
            )
        )
        assert "isometric_only" in s
        assert "hold_s=45" in s and "sets=3" in s and "intensity_pct_mvc=70" in s
        assert "eccentric_s" not in s  # unpopulated params are omitted
        assert "tendon stage 1" in s

    def test_loading_type_change_shows_transition(self):
        s = format_modality(
            LoadingTypeChangeModality(
                from_type="barbell", to_type="dumbbell",
                rationale="shoulder impingement", evidence_basis=[],
            )
        )
        assert "barbell" in s and "dumbbell" in s and "shoulder impingement" in s

    def test_frequency_reduction_cap(self):
        s = format_modality(
            FrequencyReductionModality(
                sessions_per_week_cap=2, rationale="manage flare",
                evidence_basis=[],
            )
        )
        assert "2" in s and "manage flare" in s

    def test_exercise_substitution_has_rationale_only(self):
        s = format_modality(
            ExerciseSubstitutionModality(
                rationale="swap to leg press", evidence_basis=[],
            )
        )
        assert s.startswith("exercise_substitution")
        assert "swap to leg press" in s


def _exercise(ex_id, name, accommodations=()):
    return SimpleNamespace(
        exercise_id=ex_id, exercise_name=name, accommodations=list(accommodations)
    )


def _layer2d(excluded=(), accommodated=()):
    return SimpleNamespace(
        excluded_exercises=list(excluded),
        accommodated_exercises=list(accommodated),
    )


class TestFormatActiveInjuries:
    def test_none_payload_uses_caller_line(self):
        out = format_active_injuries(
            None, none_payload_line="NP", none_on_file_line="NONE"
        )
        assert out == ["NP"]

    def test_empty_uses_none_on_file_line(self):
        out = format_active_injuries(
            _layer2d(), none_payload_line="NP", none_on_file_line="NONE"
        )
        assert out == ["NONE"]

    def test_exclude_line_format(self):
        out = format_active_injuries(
            _layer2d(excluded=[_exercise("E-bench", "Bench Press")]),
            none_payload_line="NP", none_on_file_line="NONE",
        )
        assert out == ["- EXCLUDE E-bench (Bench Press)"]

    def test_accommodate_line_includes_modality_detail(self):
        # #555: the ACCOMMODATE line must carry the params + rationale, not
        # just the modality type name.
        out = format_active_injuries(
            _layer2d(accommodated=[
                _exercise("E-squat", "Back Squat", accommodations=[
                    VolumeReductionModality(
                        factor=0.6, applies_to="reps",
                        rationale="knee OA", evidence_basis=[],
                    ),
                ]),
            ]),
            none_payload_line="NP", none_on_file_line="NONE",
        )
        assert len(out) == 1
        line = out[0]
        assert line.startswith("- ACCOMMODATE E-squat (Back Squat):")
        assert "volume_reduction" in line
        assert "0.6" in line and "reps" in line
        assert "knee OA" in line
