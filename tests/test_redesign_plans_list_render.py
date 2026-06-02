"""Render smoke tests for the redesign §11 Plans · history.

Boots the real Flask app with a fake DB and drives `plans.list_plans`
through `render_template` on the new shell. The route's SELECT is the only
DB read, so a fake cursor returning a controlled plan list is enough to
exercise the active-cards / archived-rows / empty-state branches.
Assertions stay structural + CSP-clean (no inline style/handlers).
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import pytest

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _ListCursor:
    """Cursor whose fetchall() returns a caller-supplied plan list; fetchone()
    serves the current_user() hydration row."""

    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return self._rows


class _ListConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, *a, **k):
        # The plans list query is the only fetchall() the route makes; the
        # auth/user lookups use fetchone(). Hand the plan rows to every
        # cursor — fetchone() ignores them.
        return _ListCursor(self._rows)

    def commit(self):
        pass


def _plan(**kw):
    base = {
        'id': 1, 'name': 'Plan', 'status': 'active', 'sport_focus': 'run',
        'start_date': '2026-06-01', 'end_date': '2026-11-01',
        'item_count': 10, 'completed_count': 4,
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, rows):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda rows=rows: _ListConn(rows),
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_plans_list_renders_active_and_archived(monkeypatch):
    rows = [
        _plan(id=1, name='Boston Marathon 2026', status='active'),
        _plan(id=2, name='Fall Base Block', status='archived',
              completed_count=20, item_count=20),
    ]
    client = _client(monkeypatch, rows)
    resp = client.get('/plans/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Your plans.' in html
    assert 'Boston Marathon 2026' in html
    assert 'Fall Base Block' in html
    # Active card spotlight + archived section both rendered.
    assert 'plan-card spot' in html
    assert 'plan-archived' in html
    # Progress bar uses data-progress (CSP-clean), not inline width.
    assert 'data-progress="40"' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_plans_list_empty_state(monkeypatch):
    client = _client(monkeypatch, [])
    resp = client.get('/plans/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert "You're at the start line." in html
    # Both ways in are offered.
    assert 'Set race &amp; generate' in html or 'Set race & generate' in html
    assert 'Import a plan' in html
    assert 'plan-cards' not in html
    assert 'style="' not in html
