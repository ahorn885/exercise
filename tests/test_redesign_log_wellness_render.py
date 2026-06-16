"""Render smoke tests for the redesign §08 (Strength pane) and §09 (Wellness).

There's no local Postgres in CI and `database.get_db()` has no SQLite
fallback, so we boot the *real* Flask app (gate + blueprints + the
token-CSS shell templates all wired together) and swap `get_db` for a
fake connection that returns empty result sets. That's enough to drive
both routes through `render_template`, which is the integration these
tests guard: the new `training/session_form.html` extends the unified Log
shell (so the type picker renders around it), and `wellness/index.html`
extends the redesign `base.html` and carries the `#self-report` deep-link
target the Log picker's Wellness tile now points at.

The assertions stay structural (status 200, shell present, the specific
hooks each screen must expose) rather than pixel-level — parity with the
artboard is a manual/visual check per the build conventions.
"""

from __future__ import annotations

import os
import sys

# Must precede the `app` import — read at module-import time (mirrors
# tests/test_app_auth_gate.py). Empty DATABASE_URL makes the module-level
# init_postgres() fail fast (caught) instead of hanging on a real host.
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import pytest

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    """dict that also supports the sqlite3.Row-ish access the routes use."""


class _FakeCursor:
    def fetchone(self):
        # A truthy, attribute/`.get`-friendly row. Enough for current_user()
        # hydration and wellness' `today_row`.
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return []


class _FakeConn:
    def execute(self, *a, **k):
        return _FakeCursor()

    def commit(self):
        pass


def _fake_get_db():
    return _FakeConn()


@pytest.fixture()
def client(monkeypatch):
    # Every module that did `from database import get_db` holds its own
    # binding, so patch the name wherever it resolved.
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', _fake_get_db, raising=False)

    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_strength_pane_renders_in_log_shell(client):
    resp = client.get('/training/new')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Redesign shell + unified Log picker wrap the strength form.
    assert 'app-shell' in html
    assert 'log-picker' in html
    assert 'class="log-type active"' in html  # strength tile is the active one
    # The set-log + save machinery survived the migration.
    assert 'id="set-log-body"' in html
    assert 'id="save-btn"' in html
    # CSP hygiene: no inline style/handlers leaked into the rendered page.
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_wellness_renders_on_redesign_shell(client):
    resp = client.get('/wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # The Log picker's Wellness tile deep-links to this anchor.
    assert 'id="self-report"' in html
    # Self-report form still posts every rating field.
    for name in ('sleep_hours', 'sleep_quality', 'energy', 'soreness', 'mood'):
        assert f'name="{name}"' in html
    assert 'style="' not in html


def test_log_picker_wellness_tile_targets_self_report_anchor(client):
    # The picker renders inside any log pane; the cardio default carries it.
    resp = client.get('/cardio/new')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '/wellness#self-report' in html


# ── §04 Plan generation (start form · cup-pour progress · plan view) ──────────

def test_plan_gen_start_form_renders(client, monkeypatch):
    import routes.plan_create as pc
    # No-target-race branch — keeps the form off the race_events DB shape.
    monkeypatch.setattr(pc, 'load_target_race_event_payload', lambda *a, **k: None)
    resp = client.get('/plans/v2/new')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Build me a plan.' in html
    assert 'phase-band' in html          # illustrative typical-shape band
    assert 'i-bolt' in html              # Generate plan button icon
    assert 'style="' not in html


def test_plan_gen_progress_is_cup_pour(client, monkeypatch):
    import routes.plan_create as pc
    monkeypatch.setattr(pc, '_load_plan_version',
                        lambda db, uid, pid: {'generation_status': 'generating'})
    resp = client.get('/plans/v2/1/progress')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Pouring you a plan.' in html
    assert 'id="genCup"' in html
    assert 'letterTumble' in html            # cup-pour animation wired
    assert 'data-generate-url' in html       # poller target preserved
    assert 'The build stalled.' in html      # §27 failed-state copy present
    # Cup-pour is time-bucket, not server sub-steps: no per-step message cycle.
    assert 'progressMessage' not in html
    assert 'style="' not in html


def test_plan_gen_view_renders_sessions(client, monkeypatch):
    import types
    import routes.plan_create as pc
    monkeypatch.setattr(pc, '_load_plan_version', lambda db, uid, pid: {
        'generation_status': 'ready', 'pattern': 'A', 'created_via': 'plan_create',
        'scope_start_date': '2026-06-01', 'scope_end_date': '2026-11-01',
    })
    # No-target-race branch (#620) — keeps the header off the race_events DB
    # shape; the plain "Training plan" fallback label is asserted below.
    monkeypatch.setattr(pc, 'target_race_name', lambda *a, **k: None)
    pm = types.SimpleNamespace(phase_name='Base', week_in_phase=1,
                               total_weeks_in_phase=4, intended_volume_band=(6, 8))
    sess = types.SimpleNamespace(date='2026-06-01', day_of_week='Mon', kind='run',
                                 discipline_name='Easy run', discipline_id='run',
                                 duration_min=45, intensity_summary='easy',
                                 time_of_day='am', coaching_intent='Aerobic base.',
                                 session_notes='Keep it conversational.',
                                 phase_metadata=pm)
    monkeypatch.setattr(pc, 'load_plan_sessions_by_version', lambda db, pid: [sess])
    resp = client.get('/plans/v2/1')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Training plan' in html
    # #618 — internal "Pattern A" jargon + raw created_via are gone; a
    # state-appropriate lifecycle label shows instead (dates bracket today).
    assert 'Pattern A' not in html
    assert 'plan create' not in html
    assert 'Active' in html
    assert 'Base phase' in html
    assert 'Easy run' in html
    assert 'style="' not in html
