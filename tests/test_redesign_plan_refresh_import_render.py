"""Render smoke tests for the redesign §12/§13 (plan refresh + diff view)
and §14 (plan import), all migrated onto the new shell.

Boots the real Flask app with a fake DB; the data-loading helpers in
`routes.plan_refresh` are monkeypatched so the templates render without a
real Postgres. Assertions are structural + CSP-clean.
"""

from __future__ import annotations

import os
import sys
import types

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import pytest

import app as _appmod  # noqa: E402


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


# ── §14 Import ────────────────────────────────────────────────────────────────

def test_import_renders_on_shell(client):
    resp = client.get('/plans/import')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Import a plan.' in html
    assert 'name="plan_json"' in html
    assert 'JSON format reference' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


# ── §13 Refresh form ──────────────────────────────────────────────────────────

def test_refresh_no_plan_empty_state(client, monkeypatch):
    import routes.plan_refresh as pr
    monkeypatch.setattr(pr, '_latest_plan_version', lambda db, uid: None)
    resp = client.get('/plans/v2/refresh')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Create a plan first.' in html
    assert 'refresh-tiers' not in html
    assert 'style="' not in html


def test_refresh_form_renders_tiers(client, monkeypatch):
    import routes.plan_refresh as pr
    monkeypatch.setattr(pr, '_latest_plan_version', lambda db, uid: _FakeRow(
        id=12, created_via='manual_generate', pattern='B',
        scope_start_date='2026-06-01', scope_end_date='2026-11-01'))
    resp = client.get('/plans/v2/refresh')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Refresh your plan.' in html
    assert 'refresh-tiers' in html
    # All three horizons present.
    assert 'Refresh next 2 days' in html
    assert 'Refresh week' in html
    assert 'Refresh next 4 weeks' in html
    assert 'name="nl_context"' in html
    assert 'style="' not in html


# ── §12/§13 Diff view ─────────────────────────────────────────────────────────

def test_refresh_diff_view_renders_session_badge(client, monkeypatch):
    import routes.plan_refresh as pr
    monkeypatch.setattr(pr, '_load_plan_version', lambda db, uid, pid: _FakeRow(
        pattern='B', created_via='refresh_t2',
        scope_start_date='2026-06-01', scope_end_date='2026-06-08'))
    sess = types.SimpleNamespace(
        date='2026-06-01', session_index_in_day=0, day_of_week='Mon',
        kind='run', discipline_name='Easy run', discipline_id='run',
        duration_min=45, intensity_summary='easy', time_of_day='am',
        coaching_intent='Aerobic base.', session_notes='Keep it easy.')
    monkeypatch.setattr(pr, 'load_plan_sessions_by_version', lambda db, pid: [sess])
    monkeypatch.setattr(pr, '_latest_parent_for_refresh', lambda db, uid, pid: None)
    monkeypatch.setattr(pr, '_diff_sessions_against_parent',
                        lambda new, parent: ({('2026-06-01', 0): 'new'}, 1))

    resp = client.get('/plans/v2/refresh/7')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Refreshed plan.' in html
    assert 'Pattern B' in html
    assert 'Easy run' in html
    # 'new' diff badge chip + left-border class.
    assert 'diff-card new' in html
    assert 'session changed' in html
    assert 'style="' not in html
