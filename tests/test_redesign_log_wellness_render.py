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


def test_wellness_charts_grouped_into_collapsible_sections(client, monkeypatch):
    # #526 — with data present, the charts render inside 4 collapsible
    # <details> sections instead of one flat scroll. Populate one chart per
    # section so has_any_data is True and each section carries content.
    import routes.wellness as wl
    # Build the full-shaped (all-empty) chart_data the strict-Undefined template
    # expects, then seed one existing leaf series per section.
    base = wl._build_chart_data([], [], [], [], [], [])
    pt = [{'x': '2026-06-01', 'y': 1}]
    base['sleep_hours'] = pt        # Sleep
    base['stress']['avg'] = pt      # Stress & Recovery
    base['soreness'] = pt           # Body
    base['activities'] = pt         # Activity
    monkeypatch.setattr(wl, '_build_chart_data', lambda *a, **k: base)
    resp = client.get('/wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert html.count('<details class="wl-section"') == 4
    for heading in ('Sleep', 'Stress &amp; Recovery', 'Body', 'Activity'):
        assert '<summary>' + heading + '</summary>' in html
    # Grouping is pure DOM rearrangement — cards still bind by their canvas id.
    assert 'id="chart-sleep-hours"' in html
    assert 'id="chart-soreness"' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_wellness_headline_strip_renders(client, monkeypatch):
    # #527 — the "what changed" strip renders above the charts when there's a
    # baseline. Patch the strip builder (its selection logic is unit-tested in
    # test_wellness_headline.py) and assert the markup + CSP hygiene.
    import routes.wellness as wl
    base = wl._build_chart_data([], [], [], [], [], [])
    base['sleep_hours'] = [{'x': '2026-06-01', 'y': 1}]   # has_any_data → True
    monkeypatch.setattr(wl, '_build_chart_data', lambda *a, **k: base)
    monkeypatch.setattr(wl, '_build_headline_strip', lambda cd: [
        {'name': 'Resting HR', 'unit': ' bpm', 'direction': 'up', 'tone': 'bad',
         'delta_abs': '+2', 'delta_pct': 4, 'abs_pct': 4},
    ])
    resp = client.get('/wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'wl-headline' in html
    assert 'What changed' in html
    assert 'wl-stat-bad' in html
    assert 'Resting HR' in html
    assert '+2 bpm' in html
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


# ── #893 wellness self-report history (read view + scoped delete) ─────────────

class _HistCursor:
    def __init__(self, rows, one='__none__'):
        self._rows = rows
        self._one = one

    def fetchone(self):
        return None if self._one == '__none__' else self._one

    def fetchall(self):
        return self._rows


class _HistConn:
    """Serves the self-report *history* SELECT (the DESC-ordered list view) and
    a truthy users row for auth hydration; everything else is empty so the
    chart builder takes its all-empty path."""
    def __init__(self, history):
        self._history = history

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'wellness_self_report' in s and 'ORDER BY date DESC' in s:
            return _HistCursor(self._history)
        if 'FROM users' in s:
            return _HistCursor([], one=_FakeRow(
                id=1, username='owner', email='o@x.test', display_name='Owner'))
        return _HistCursor([])

    def commit(self):
        pass


def _boot_client(monkeypatch, conn):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_wellness_self_report_history_renders(monkeypatch):
    rows = [
        _FakeRow(id=11, date='2026-06-20', sleep_hours=7.5, sleep_quality=4,
                 energy=3, soreness=2, mood=4, notes='solid'),
        _FakeRow(id=12, date='2026-06-19', sleep_hours=None, sleep_quality=None,
                 energy=None, soreness=None, mood=None, notes=None),
    ]
    client = _boot_client(monkeypatch, _HistConn(rows))
    html = client.get('/wellness').get_data(as_text=True)
    assert 'id="self-report-history"' in html
    assert 'Recent self-reports' in html
    assert '2026-06-20' in html and 'solid' in html
    # Edit deep-links back to the form for that day; delete is wired per entry.
    assert 'date=2026-06-20' in html
    assert '/wellness/self-report/11/delete' in html
    # Body-metrics history is reachable from the header.
    assert 'Body metrics history' in html and '/body' in html
    assert 'style="' not in html


def test_wellness_self_report_delete_is_user_scoped(monkeypatch):
    captured = {}

    class _DelConn:
        def execute(self, sql, *a, **k):
            s = ' '.join(sql.split())
            if 'DELETE FROM wellness_self_report' in s:
                captured['params'] = a[0]
            return _FakeCursor()

        def commit(self):
            captured['committed'] = True

    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _boot_client(monkeypatch, _DelConn())
    resp = client.post('/wellness/self-report/11/delete', data={'range': '30'})
    assert resp.status_code in (302, 303)
    assert captured['params'] == (11, 1)        # (report_id, user_id) — scoped
    assert captured.get('committed')
    assert 'range=30' in resp.headers['Location']


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
