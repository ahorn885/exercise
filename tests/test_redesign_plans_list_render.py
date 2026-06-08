"""Render smoke tests for the Plans · history screen.

Boots the real Flask app with a fake DB and drives `plans.list_plans`
through `render_template` on the new shell. The route makes two fetchall()
reads — the legacy `training_plans` list and the `plan_versions` (generated)
list — which the fake conn routes by SQL. Assertions stay structural +
CSP-clean (no inline style/handlers).
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

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
    `training_plans` list vs. the `plan_versions` (generated) list. The
    auth/user lookups use fetchone(), which ignores both."""

    def __init__(self, rows, generated=()):
        self._rows = rows
        self._generated = list(generated)

    def execute(self, sql, *a, **k):
        if 'plan_versions' in sql:
            return _ListCursor(self._generated)
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


def _gen(**kw):
    # Defaults to a ready, currently-active plan (scope spans today). Callers
    # override scope dates / status / completed_at to land it in a bucket.
    today = date.today()
    base = {
        'id': 7, 'created_at': '2026-06-01', 'created_via': 'plan_create',
        'scope_start_date': today - timedelta(days=7),
        'scope_end_date': today + timedelta(days=30),
        'pattern': 'A', 'generation_status': 'ready', 'completed_at': None,
        'session_count': 42,
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, rows, generated=()):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(
                mod, 'get_db',
                lambda rows=rows, generated=generated: _ListConn(rows, generated),
                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_plans_list_renders_imported_and_archived(monkeypatch):
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
    # Legacy active card spotlight + archived section both rendered.
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


def test_generated_plans_bucketed_by_scope_dates(monkeypatch):
    today = date.today()
    client = _client(monkeypatch, [], generated=[
        _gen(id=10, scope_start_date=today + timedelta(days=14),
             scope_end_date=today + timedelta(days=60)),            # upcoming
        _gen(id=11, scope_start_date=today - timedelta(days=3),
             scope_end_date=today + timedelta(days=30)),            # active
        _gen(id=12, scope_start_date=today - timedelta(days=90),
             scope_end_date=today - timedelta(days=2)),             # completed (past)
    ])
    resp = client.get('/plans/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "You're at the start line." not in html
    # Each bucket has its own section header.
    assert 'Upcoming · 1' in html
    assert 'Active · 1' in html
    assert 'Completed · 1' in html
    # Each links to its /plans/v2/<id> view.
    assert '/plans/v2/10' in html
    assert '/plans/v2/11' in html
    assert '/plans/v2/12' in html
    assert '42 sessions' in html
    # Non-completed plans expose a Mark-complete action.
    assert '/plans/v2/11/complete' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_generating_plan_shown_with_progress_link(monkeypatch):
    client = _client(monkeypatch, [], generated=[
        _gen(id=20, generation_status='generating', session_count=0),
    ])
    resp = client.get('/plans/')
    html = resp.get_data(as_text=True)
    assert 'Generating · 1' in html
    # Generating plans link to the progress screen, not the (empty) view.
    assert '/plans/v2/20/progress' in html
    # Pluralization branch is skipped for generating plans (no session line).
    assert '0 sessions' not in html


def test_marked_complete_forces_completed_bucket(monkeypatch):
    today = date.today()
    # Active scope dates, but a manual completed_at stamp pins it to Completed.
    client = _client(monkeypatch, [], generated=[
        _gen(id=30, scope_start_date=today - timedelta(days=3),
             scope_end_date=today + timedelta(days=30),
             completed_at='2026-06-08T00:00:00Z'),
    ])
    resp = client.get('/plans/')
    html = resp.get_data(as_text=True)
    assert 'Completed · 1' in html
    assert 'Active ·' not in html
    assert 'Marked complete' in html
    # A completed plan offers Reopen, not Mark-complete.
    assert '/plans/v2/30/reopen' in html
    assert '/plans/v2/30/complete' not in html
