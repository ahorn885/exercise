"""Unit tests for fit_workout_generator (#945).

Andy's checklist flagged that planned-workout FIT/ZWO downloads weren't
consistently populating. Root cause: `generate_workout_fit` raised on any
malformed numeric field (e.g. a stray non-numeric `target_duration_min`
from a manual edit or import), and the bulk `workouts.zip` download
silently swallowed those exceptions — so some workouts just vanished from
the export with no indication anything went wrong.

These tests cover the generator's tolerance of malformed numeric inputs
across the discipline types exercised by `_build_steps`.
"""

from __future__ import annotations

from fit_workout_generator import generate_workout_fit


def _item(**overrides):
    base = dict(
        workout_name='Workout',
        sport_type='running',
        target_duration_min=30,
        target_distance_mi=0,
        intensity='easy',
        description='',
    )
    base.update(overrides)
    return base


def test_generates_for_running_cycling_swimming_strength():
    for sport_type in ('running', 'cycling', 'swimming', 'strength_training', 'rowing'):
        fit_bytes = generate_workout_fit(_item(sport_type=sport_type))
        assert isinstance(fit_bytes, bytes)
        assert len(fit_bytes) > 0


def test_non_numeric_duration_does_not_raise():
    """A stray non-numeric duration must fall back, not abort generation."""
    fit_bytes = generate_workout_fit(_item(target_duration_min='thirty'))
    assert len(fit_bytes) > 0


def test_whitespace_duration_does_not_raise():
    fit_bytes = generate_workout_fit(_item(target_duration_min='   '))
    assert len(fit_bytes) > 0


def test_non_numeric_distance_does_not_raise():
    fit_bytes = generate_workout_fit(
        _item(sport_type='swimming', target_duration_min=0, target_distance_mi='n/a')
    )
    assert len(fit_bytes) > 0


def test_missing_fields_fall_back_to_open_step():
    fit_bytes = generate_workout_fit(_item(target_duration_min=None, target_distance_mi=None))
    assert len(fit_bytes) > 0
