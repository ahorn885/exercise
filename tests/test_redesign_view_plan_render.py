"""Render smoke tests for the generated-plan view (`/plans/v2/<id>`).

Boots the real Flask app, monkeypatches the two helpers `view_plan` reads
(`_load_plan_version`, `load_plan_sessions_by_version`) so the template
hydrates without a real Postgres, then asserts the structural HTML +
CSP-cleanliness.

Covers the #333 "Sparse daily view" remaining checklist item — verifies
that the rich PlanSession fields already in plan_sessions (cardio_blocks
w/ zones + targets, strength_exercises, rest_reason, locale_name,
coaching_flags) actually surface on the page.
"""

from __future__ import annotations

import os
import sys
from datetime import date

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import pytest

import app as _appmod  # noqa: E402

from layer4.payload import (  # noqa: E402
    CardioBlock,
    HRTarget,
    PaceTarget,
    PlanSession,
    PowerTarget,
    SessionPhaseMetadata,
    StrengthExercise,
)


class _FakeRow(dict):
    pass


class _FakeCursor:
    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return []


class _FakeConn:
    def execute(self, *a, **k):
        return _FakeCursor()

    def commit(self):
        pass


PV = {
    'id': 46, 'user_id': 1, 'created_at': '2026-05-30',
    'created_via': 'plan_create',
    'scope_start_date': '2026-06-01',
    'scope_end_date': '2026-08-31',
    'pattern': 'A',
    'generation_status': 'ready',
    'generation_error': None,
    'generation_units_cached': 12,
    'generation_stall_passes': 0,
}


def _phase(week=1, total=4, name='Base'):
    return SessionPhaseMetadata(
        phase_name=name, week_in_phase=week, total_weeks_in_phase=total,
        intended_volume_band=(6.0, 8.0),
        intended_intensity_distribution={'easy': 0.8, 'moderate': 0.15, 'hard': 0.05},
    )


def _cardio_session(**kw):
    base = dict(
        session_id='s-c-1', plan_version_id=46,
        date=date(2026, 6, 1), day_of_week='Mon', session_index_in_day=0,
        time_of_day='morning', kind='cardio',
        discipline_id='D-001', discipline_name='Run',
        locale_id='L-1', locale_name='Lake loop',
        duration_min=60, intensity_summary='moderate',
        cardio_blocks=[
            CardioBlock(
                block_kind='warmup', duration_min=10,
                intensity_zone='Z1',
                intensity_target=HRTarget(hr_bpm_low=110, hr_bpm_high=130),
                instructions='Easy build to working HR.',
            ),
            CardioBlock(
                block_kind='interval_set', duration_min=30,
                intensity_zone='Z4',
                intensity_target=PaceTarget(
                    pace_per_km_low='4:20', pace_per_km_high='4:30'),
                instructions='5×4 min @ threshold, jog rest.',
                repetitions=5, rest_between_min=2, rest_intensity_zone='Z1',
            ),
            CardioBlock(
                block_kind='cooldown', duration_min=10,
                intensity_zone='Z1',
                intensity_target=HRTarget(hr_bpm_low=100, hr_bpm_high=120),
                instructions='Float home.',
            ),
        ],
        phase_metadata=_phase(),
        session_notes='Hydrate.',
        coaching_intent='Threshold stimulus inside Base 4.',
        coaching_flags=['low_calorie_target_relative_to_rmr'],
    )
    base.update(kw)
    return PlanSession(**base)


def _strength_session(**kw):
    base = dict(
        session_id='s-s-1', plan_version_id=46,
        date=date(2026, 6, 2), day_of_week='Tue', session_index_in_day=0,
        time_of_day='evening', kind='strength',
        locale_id='L-2', locale_name='Home gym',
        duration_min=45, intensity_summary='moderate',
        strength_exercises=[
            StrengthExercise(
                exercise_id='E-001', exercise_name='Back squat',
                resolution_tier=1, sets=4, reps_per_set=5,
                load_prescription='75% 1RM',
                rest_between_sets_sec=180, tempo='2-1-X-1',
                instructions='Brace before each rep.',
                coaching_flags=[],
            ),
            StrengthExercise(
                exercise_id='E-002', exercise_name='Bulgarian split squat',
                resolution_tier=2, substitute_text='Subbed for step-ups (knee).',
                sets=3, reps_per_set='8-10',
                load_prescription='2× 20 lb DBs',
                rest_between_sets_sec=90,
                instructions='Front-foot elevated.',
                coaching_flags=[],
            ),
        ],
        phase_metadata=_phase(),
        session_notes='Sleep ≥7 h tonight.',
        coaching_intent='Posterior chain volume.',
        coaching_flags=[],
    )
    base.update(kw)
    return PlanSession(**base)


def _rest_session(**kw):
    base = dict(
        session_id='s-r-1', plan_version_id=46,
        date=date(2026, 6, 3), day_of_week='Wed', session_index_in_day=0,
        time_of_day='unspecified', kind='rest',
        duration_min=0, intensity_summary='rest',
        rest_reason='taper_drop',
        phase_metadata=_phase(),
        session_notes='', coaching_intent='Recovery for Thursday quality.',
        coaching_flags=[],
    )
    base.update(kw)
    return PlanSession(**base)


@pytest.fixture()
def client(monkeypatch):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda: _FakeConn(), raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _patch_view(monkeypatch, sessions):
    import routes.plan_create as pc
    monkeypatch.setattr(pc, '_load_plan_version', lambda db, uid, pvid: dict(PV))
    monkeypatch.setattr(
        pc, 'load_plan_sessions_by_version',
        lambda db, pvid: list(sessions),
    )


def test_cardio_blocks_render_with_zones_and_targets(client, monkeypatch):
    _patch_view(monkeypatch, [_cardio_session()])
    resp = client.get('/plans/v2/46')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Phase header still rendered (#403).
    assert 'Base phase' in html
    # Discipline + duration on the head.
    assert 'Run — 60 min' in html
    # Locale chip ("@ Lake loop").
    assert '@ Lake loop' in html
    # Each block kind appears, humanized.
    assert 'Warmup' in html
    assert 'Interval set' in html
    assert 'Cooldown' in html
    # Zones surface verbatim.
    assert 'Z1' in html and 'Z4' in html
    # Both target shapes rendered (HR + pace).
    assert 'HR 110–130 bpm' in html
    assert 'pace 4:20–4:30 /km' in html
    # Interval reps + rest detail surfaces.
    assert '5×' in html
    assert 'rest 2 min Z1' in html
    # Per-block instructions surface.
    assert '5×4 min @ threshold' in html
    # Session coaching_flags chip surfaces (#295 dead-channel begin to fix).
    assert 'low calorie target relative to rmr' in html
    # CSP-clean.
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_strength_exercises_render_with_prescription(client, monkeypatch):
    _patch_view(monkeypatch, [_strength_session()])
    resp = client.get('/plans/v2/46')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Exercise names surface.
    assert 'Back squat' in html
    assert 'Bulgarian split squat' in html
    # Prescription line (sets × reps @ load · rest · tempo).
    assert '4 × 5 @ 75% 1RM' in html
    assert 'rest 180s' in html
    assert 'tempo 2-1-X-1' in html
    # Resolution-tier 2 carries a "substitute" chip + substitute_text.
    assert 'substitute' in html
    assert 'Subbed for step-ups' in html
    # #691 — the Tier-2 substitute is surfaced as the directive ("Do instead:"
    # in the elevated sess-exercise-sub line), not buried as a footnote, so the
    # athlete isn't read the un-available base exercise as the headline.
    assert 'sess-exercise-sub' in html
    assert 'Do instead: Subbed for step-ups (knee).' in html
    # Locale chip rendered for strength session.
    assert '@ Home gym' in html
    assert 'style="' not in html


def test_strength_session_labeled_strength_not_its_discipline(client, monkeypatch):
    # The synthesizer tags strength sessions with their associated sport
    # (discipline_name). The card must label them "Strength" — keeping the
    # sport as a secondary association — not as the sport alone (#4).
    _patch_view(monkeypatch, [_strength_session(
        discipline_id='D-008', discipline_name='Mountain Biking')])
    html = client.get('/plans/v2/46').get_data(as_text=True)
    # Labeled "Strength" with the sport kept as a secondary association — the
    # sport is never the standalone label for a strength session.
    assert 'Strength · Mountain Biking — 45 min' in html


def test_rest_session_surfaces_reason(client, monkeypatch):
    _patch_view(monkeypatch, [_rest_session()])
    resp = client.get('/plans/v2/46')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Rest reason humanized into the session name.
    assert 'Rest — Taper drop' in html
    # The redundant intensity_summary='rest' chip is suppressed for rest.
    # (The replace is structural: no chip with the word "Rest" outside the name.)
    # Coaching intent still surfaces on rest cards.
    assert 'Recovery for Thursday quality.' in html
    assert 'style="' not in html


def test_mixed_day_renders_all_three_kinds(client, monkeypatch):
    _patch_view(monkeypatch, [
        _cardio_session(),
        _strength_session(),
        _rest_session(),
    ])
    resp = client.get('/plans/v2/46')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # All three discipline sections present.
    assert 'Run — 60 min' in html
    assert 'Back squat' in html
    assert 'Rest — Taper drop' in html
    # No leftover Jinja artifacts.
    assert '{{' not in html and '{%' not in html


def test_internal_jargon_hidden_from_plan_view(client, monkeypatch):
    # #618 — neither the internal "Pattern A" synthesis term nor the raw
    # `created_via` slug ("plan create") may surface to the athlete.
    _patch_view(monkeypatch, [_cardio_session()])
    html = client.get('/plans/v2/46').get_data(as_text=True)
    assert 'Pattern A' not in html
    assert 'plan create' not in html


def test_lifecycle_label_shown_not_created_via(client, monkeypatch):
    # #618 — a state-appropriate lifecycle label replaces "plan create": a
    # completed plan reads "Completed" regardless of its scope dates.
    import routes.plan_create as pc
    pv = dict(PV)
    pv['completed_at'] = '2026-06-10'
    monkeypatch.setattr(pc, '_load_plan_version', lambda db, uid, pvid: pv)
    monkeypatch.setattr(
        pc, 'load_plan_sessions_by_version',
        lambda db, pvid: [_cardio_session()],
    )
    html = client.get('/plans/v2/46').get_data(as_text=True)
    assert 'Completed' in html
    assert 'plan create' not in html


def test_coaching_flags_render_above_workout_detail(client, monkeypatch):
    # #618 — workout-type / coaching flags (e.g. "long slow distance") sit with
    # the coach notes ABOVE the per-block detail, not buried below it.
    _patch_view(monkeypatch, [_cardio_session(coaching_flags=['long_slow_distance'])])
    html = client.get('/plans/v2/46').get_data(as_text=True)
    assert 'long slow distance' in html
    # The flag appears before the first block's humanized kind ("Warmup").
    assert html.index('long slow distance') < html.index('Warmup')


def test_off_days_render_as_explicit_rest(client, monkeypatch):
    # #618 — a gap between session dates surfaces as explicit rest days so the
    # week reads continuously (Mon + Thu sessions → Tue & Wed shown as rest).
    mon = _cardio_session(session_id='s-mon', date=date(2026, 6, 1), day_of_week='Mon')
    thu = _cardio_session(session_id='s-thu', date=date(2026, 6, 4), day_of_week='Thu')
    _patch_view(monkeypatch, [mon, thu])
    html = client.get('/plans/v2/46').get_data(as_text=True)
    assert 'Off day — recovery.' in html
    # Two interior gap days (Tue + Wed) → two rest cards; the dated sessions stay.
    assert html.count('sess-rest') == 2
    assert 'Run — 60 min' in html
