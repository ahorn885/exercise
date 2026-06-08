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
    """Cursor whose fetchall() returns a caller-supplied row list; fetchone()
    serves the current_user() hydration row."""

    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return self._rows


class _ListConn:
    """Routes the route's two fetchall() reads by SQL: the legacy
    `training_plans` list vs. the `plan_versions` (completed AI-generated)
    list. The auth/user lookups use fetchone(), which ignores both."""

    def __init__(self, rows, completed=()):
        self._rows = rows
        self._completed = list(completed)

    def execute(self, sql, *a, **k):
        if 'plan_versions' in sql:
            return _ListCursor(self._completed)
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


def _completed(**kw):
    base = {
        'id': 7, 'created_at': '2026-06-01', 'created_via': 'plan_create',
        'scope_start_date': '2026-06-10', 'scope_end_date': '2026-11-01',
        'pattern': 'A', 'session_count': 42,
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, rows, completed=()):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(
                mod, 'get_db',
                lambda rows=rows, completed=completed: _ListConn(rows, completed),
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


def test_plans_list_renders_completed_generated_plans(monkeypatch):
    # AI-generated plans live in plan_versions, so they surface even when there
    # are zero legacy training_plans — the original bug was an empty screen.
    client = _client(monkeypatch, [], completed=[
        _completed(id=7, pattern='A', session_count=42),
        _completed(id=8, pattern='B', session_count=1),
    ])
    resp = client.get('/plans/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Not the empty state — the Completed section renders the generated plans.
    assert "You're at the start line." not in html
    assert 'Completed · 2' in html
    assert 'Pattern A' in html
    assert 'Pattern B' in html
    # Each links to its /plans/v2/<id> view.
    assert '/plans/v2/7' in html
    assert '/plans/v2/8' in html
    # Session-count pluralization.
    assert '42 sessions' in html
    assert '1 session' in html
    assert 'style="' not in html
    assert 'onclick=' not in html
