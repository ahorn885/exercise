"""Render-smoke tests for templates/workouts/suggestion_view.html (D-63 ad-hoc
workout card). The view renders `suggestion.generated_session`, which is a
serialized `PlanSession` (`PlanSession.model_dump_json()`), so the template must
read the real model field names. #764: the cardio_blocks / strength_exercises
branches previously used stale names (`block_type`/`hr_target`/`reps`/`load_kg`)
that don't exist on the models, silently dropping the block/exercise content —
and there was no render test to catch it. These render the template through the
booted app's Jinja env and assert the corrected fields surface.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flask  # noqa: E402
import app as _appmod  # noqa: E402


def _render(template, **ctx):
    with _appmod.app.test_request_context('/'):
        flask.g.current_user_row = {'id': 1, 'username': 'owner',
                                    'display_name': 'Owner'}
        return flask.render_template(template, **ctx)


def _suggestion(generated_session, status='suggested'):
    return {
        'id': 5,
        'user_id': 1,
        'requested_at': '2026-06-19',
        'request_payload': {'sport': 'Cycling', 'duration_min': 60,
                            'intensity': 'hard', 'locale_slug': 'home'},
        'generated_session': generated_session,
        'status': status,
        'regenerated_into_id': None,
        'logged_into_table': None,
        'logged_into_id': None,
    }


def _render_view(generated_session, status='suggested'):
    return _render(
        'workouts/suggestion_view.html',
        suggestion=_suggestion(generated_session, status=status),
        just_logged=False,
        t1_hook_nl_context='Did an unscheduled 60min Cycling (hard) at Home',
        t1_hook_refresh_query='nl_context=x&tier=T1',
    )


def test_cardio_blocks_render_with_real_field_names():
    sess = {
        'kind': 'cardio',
        'intensity_summary': 'hard',
        'locale_name': 'Home', 'locale_id': 'home',
        'coaching_intent': 'VO2 work.',
        'session_notes': 'Hard intervals.',
        'cardio_blocks': [
            {'block_kind': 'main_set', 'duration_min': 40, 'intensity_zone': 'Z4',
             'intensity_target': {'hr_bpm_low': 160, 'hr_bpm_high': 175},
             'instructions': 'Hold threshold.'},
            {'block_kind': 'interval_set', 'duration_min': 20, 'intensity_zone': 'Z5',
             'intensity_target': {'rpe_low': 8, 'rpe_high': 9},
             'instructions': 'All out.', 'repetitions': 5,
             'rest_between_min': 3, 'rest_intensity_zone': 'Z1'},
        ],
    }
    html = _render_view(sess)
    # block_kind (was block_type → undefined → empty), intensity_zone, the
    # polymorphic intensity_target, and instructions (was description) all surface.
    assert 'Main Set' in html
    assert 'Z4' in html
    assert 'HR 160–175 bpm' in html
    assert 'Hold threshold.' in html
    # interval_set rep/rest line + a non-HR target shape.
    assert '5×' in html
    assert 'RPE 8–9' in html


def test_strength_exercises_render_with_real_field_names():
    sess = {
        'kind': 'strength',
        'intensity_summary': 'moderate',
        'coaching_intent': 'Maintain strength.',
        'session_notes': 'Lower body.',
        'strength_exercises': [
            {'exercise_name': 'Back Squat', 'resolution_tier': 1, 'sets': 3,
             'reps_per_set': 8, 'load_prescription': '70% 1RM',
             'rest_between_sets_sec': 120, 'instructions': 'Full depth.'},
        ],
    }
    html = _render_view(sess)
    assert 'Back Squat' in html
    # reps_per_set (was reps) + load_prescription (was load_kg) + rest + instructions (was notes).
    assert '3 × 8 @ 70% 1RM' in html
    assert 'rest 120s' in html
    assert 'Full depth.' in html


def test_cardio_drill_renders_on_cardio_card():
    sess = {
        'kind': 'cardio',
        'intensity_summary': 'hard',
        'coaching_intent': 'x', 'session_notes': 'x',
        'cardio_blocks': [
            {'block_kind': 'main_set', 'duration_min': 40, 'intensity_zone': 'Z3',
             'intensity_target': {'power_w_low': 200, 'power_w_high': 240},
             'instructions': 'Steady.'},
        ],
        'cardio_drills': [
            {'exercise_id': 'EX292', 'exercise_name': 'Bike Over-Under Intervals',
             'prescription': '6×3min', 'instructions': 'Hold the over.'},
        ],
    }
    html = _render_view(sess)
    assert 'Bike Over-Under Intervals' in html
    assert 'drill' in html
    assert '200–240 W' in html  # power target shape
