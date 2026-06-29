"""Regression for #951 — post-delete redirect returns to the originating list.

The Workouts feed (`/training`) federates strength sessions + cardio entries,
each with its own delete control. Before the fix a cardio delete redirected to
`/cardio` (a different page), so the feed the athlete was on — and its delete
controls — vanished until they navigated back. The delete routes now honor a
local `next` form value so the delete re-renders the same feed in place
(filters preserved), while rejecting off-site `next` values (open-redirect
defense) and falling back to the blueprint's own list otherwise.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-delete-redirect')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _Cursor:
    def fetchone(self):
        # Truthy row so session_delete proceeds past its ownership check.
        return _FakeRow(id=1, user_id=1)

    def fetchall(self):
        return []


class _Conn:
    def execute(self, sql, *a, **k):
        return _Cursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def _client(monkeypatch):
    conn = _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _location(resp):
    return resp.headers.get('Location', '')


# ── cardio delete ───────────────────────────────────────────────────────────

def test_cardio_delete_honors_local_next(monkeypatch):
    c = _client(monkeypatch)
    resp = c.post('/cardio/5/delete', data={'next': '/training?modality=cardio'})
    assert resp.status_code == 302
    assert _location(resp).endswith('/training?modality=cardio')


def test_cardio_delete_defaults_to_cardio_list(monkeypatch):
    c = _client(monkeypatch)
    resp = c.post('/cardio/5/delete', data={})
    assert resp.status_code == 302
    assert _location(resp).endswith('/cardio')


def test_cardio_delete_rejects_offsite_next(monkeypatch):
    c = _client(monkeypatch)
    resp = c.post('/cardio/5/delete', data={'next': '//evil.example/x'})
    assert resp.status_code == 302
    # Off-site value ignored → falls back to the cardio list.
    assert _location(resp).endswith('/cardio')
    assert 'evil.example' not in _location(resp)


# ── strength session delete ─────────────────────────────────────────────────

def test_session_delete_honors_local_next(monkeypatch):
    c = _client(monkeypatch)
    resp = c.post('/training/session/9/delete', data={'next': '/training?date=2026-06-28'})
    assert resp.status_code == 302
    assert _location(resp).endswith('/training?date=2026-06-28')


def test_session_delete_defaults_to_feed(monkeypatch):
    c = _client(monkeypatch)
    resp = c.post('/training/session/9/delete', data={})
    assert resp.status_code == 302
    assert _location(resp).endswith('/training')


def test_session_delete_rejects_offsite_next(monkeypatch):
    c = _client(monkeypatch)
    resp = c.post('/training/session/9/delete', data={'next': 'https://evil.example/x'})
    assert resp.status_code == 302
    assert _location(resp).endswith('/training')
    assert 'evil.example' not in _location(resp)
