"""Unit tests for garmin_fit_parser._parse_strength sentinel filtering (#456).

Andy's 2026-05-25 FIT import surfaced an "Unknown Exercise" row whose per-set
chips read `65535r 9030.0lb` — the FIT uint16 "no value" sentinel was being
stored as a literal rep count, and a scale-mismatched weight (4096 kg →
9030 lb after the kg→lb conversion) was poisoning the volume + est_1RM
aggregates (the session row showed a 21-billion-pound-rep volume).

These tests stub the fit_tool message objects with plain Python objects so
we don't need a real .FIT fixture.
"""

from __future__ import annotations

from types import SimpleNamespace

from garmin_fit_parser import _parse_strength


def _session(date_iso='2026-05-25'):
    """Minimal session stub — _parse_strength only needs a start_time / timestamp."""
    return SimpleNamespace(start_time=None, timestamp=None)


def _set(*, reps=None, weight_kg=None, duration=None, exercise_name='Bench Press',
         category=None):
    return SimpleNamespace(
        repetitions=reps,
        weight=weight_kg,
        duration=duration,
        exercise_name=exercise_name,
        category=category,
    )


def test_uint16_sentinel_reps_become_none():
    """65535 is the uint16 'no value' sentinel — must not flow through as reps."""
    out = _parse_strength(_session(), [_set(reps=65535, weight_kg=100.0, duration=46)])
    assert len(out['data']) == 1
    sets = out['data'][0]['sets']
    assert sets[0]['reps'] is None
    # Real weight + duration still pass through.
    assert sets[0]['weight_kg'] is not None
    assert sets[0]['duration_sec'] == 46


def test_uint32_sentinel_duration_becomes_none():
    out = _parse_strength(_session(), [_set(reps=5, weight_kg=100.0, duration=4294967295)])
    sets = out['data'][0]['sets']
    assert sets[0]['duration_sec'] is None
    assert sets[0]['reps'] == 5


def test_implausible_weight_becomes_none():
    """4096 kg isn't a standard sentinel but is physically impossible
    (~9030 lb). Sanity ceiling kicks it out."""
    out = _parse_strength(_session(), [_set(reps=5, weight_kg=4096.0, duration=46)])
    sets = out['data'][0]['sets']
    assert sets[0]['weight_kg'] is None
    assert sets[0]['reps'] == 5


def test_implausible_reps_become_none():
    """A 1000-rep "set" is also nonsense — anything over the sanity cap is dropped."""
    out = _parse_strength(_session(), [_set(reps=1000, weight_kg=100.0, duration=46)])
    sets = out['data'][0]['sets']
    assert sets[0]['reps'] is None


def test_zero_weight_remains_none():
    """A 0 kg / 0 rep field is a sentinel-equivalent — drop it."""
    out = _parse_strength(_session(), [_set(reps=5, weight_kg=0.0, duration=46)])
    sets = out['data'][0]['sets']
    assert sets[0]['weight_kg'] is None
    assert sets[0]['reps'] == 5


def test_andys_2026_05_25_fixture():
    """Replays the shape of Andy's bad row: reps=65535, weight=4096 kg,
    duration in normal range. Per-set chips should render as bodyweight
    timed-set (no reps, no weight, real duration) instead of the original
    `65535r 9030.0lb 35s` garbage."""
    bad_sets = [_set(reps=65535, weight_kg=4096.0, duration=d)
                for d in (35, 71, 167, 7, 76, 9, 10, 69, 9, 74)]
    out = _parse_strength(_session(), bad_sets)
    assert len(out['data']) == 1
    sets = out['data'][0]['sets']
    assert len(sets) == 10
    for s in sets:
        assert s['reps'] is None
        assert s['weight_kg'] is None
        assert s['duration_sec'] is not None  # durations pass through


def test_legitimate_set_passes_through_unchanged():
    """Sanity check: a normal set survives the filter intact."""
    out = _parse_strength(_session(), [
        _set(reps=5, weight_kg=102.0, duration=None, exercise_name='Back Squat'),
        _set(reps=5, weight_kg=102.0, duration=None, exercise_name='Back Squat'),
        _set(reps=5, weight_kg=102.0, duration=None, exercise_name='Back Squat'),
    ])
    assert len(out['data']) == 1
    assert out['data'][0]['exercise'] == 'Back Squat'
    sets = out['data'][0]['sets']
    assert len(sets) == 3
    for s in sets:
        assert s['reps'] == 5
        # Storage is canonical kg now (#469).
        assert s['weight_kg'] == 102.0


# ── Richer (category, category_subtype) labeling — pulls from fit_tool's
# per-category ExerciseName enums (the Garmin SDK is the source of truth).

def _ex(*, category, category_subtype, reps=5, weight_kg=100.0, duration=None):
    """Set stub that exercises the (category, category_subtype) lookup path.
    `exercise_name` deliberately absent so the legacy attr path is skipped."""
    return SimpleNamespace(
        repetitions=reps, weight=weight_kg, duration=duration,
        exercise_name=None,
        category=[category], category_subtype=[category_subtype],
    )


def test_subtype_lookup_resolves_barbell_bench_press():
    """(category=0 BENCH_PRESS, subtype=1 BARBELL_BENCH_PRESS) →
    'Barbell Bench Press' — not the coarse 'Bench Press'."""
    out = _parse_strength(_session(), [_ex(category=0, category_subtype=1)])
    assert out['data'][0]['exercise'] == 'Barbell Bench Press'


def test_subtype_lookup_resolves_incline_dumbbell_bench_press():
    """The example in Andy's request — subtype=9 in BenchPressExerciseName."""
    out = _parse_strength(_session(), [_ex(category=0, category_subtype=9)])
    assert out['data'][0]['exercise'] == 'Incline Dumbbell Bench Press'


def test_subtype_lookup_strips_n_prefix_for_digit_tokens():
    """N3_WAY_CALF_RAISE (CalfRaise.N3_WAY_CALF_RAISE = 0) → "3 Way Calf Raise"."""
    out = _parse_strength(_session(), [_ex(category=1, category_subtype=0)])
    assert out['data'][0]['exercise'] == '3 Way Calf Raise'


def test_unknown_subtype_falls_back_to_category():
    """Subtype 9999 isn't in BenchPressExerciseName → 'Bench Press'."""
    out = _parse_strength(_session(), [_ex(category=0, category_subtype=9999)])
    assert out['data'][0]['exercise'] == 'Bench Press'


def test_subtype_sentinel_falls_back_to_category():
    """Subtype 65535 (UNKNOWN) → fall back to the category-only label."""
    out = _parse_strength(_session(), [_ex(category=8, category_subtype=65535)])
    assert out['data'][0]['exercise'] == 'Deadlift'


def test_no_category_or_subtype_yields_unknown():
    """Confirms the Andy-Fenix-uncategorized path still lands 'Unknown Exercise'."""
    s = SimpleNamespace(repetitions=5, weight=100.0, duration=None,
                        exercise_name=None, category=None, category_subtype=None)
    out = _parse_strength(_session(), [s])
    assert out['data'][0]['exercise'] == 'Unknown Exercise'
