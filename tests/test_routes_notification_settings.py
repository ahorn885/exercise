"""Route tests for the §22 notification-settings POST and the §21 read/unread
actions (#963).

Boots the real Flask app with a fake DB. The settings POST persists the matrix
via `save_from_form`; the read routes stamp `account_nudges.read_at`. A fake
connection records every (sql, params) so the assertions stay structural. CSRF
is disabled for the test client (mirrors the other route POST tests).
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-notif-settings')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _Cursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        # Feeds _require_login's user-hydration only.
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return self._rows


class _Conn:
    """Records writes; returns empty cursors for reads (the POST paths don't
    need read data, and the settings GET degrades to defaults on empty)."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.committed = 0

    def execute(self, sql, params=()):
        self.calls.append((' '.join(sql.split()), params))
        return _Cursor([])

    def commit(self):
        self.committed += 1


def _client(monkeypatch, conn):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_settings_post_persists_matrix_and_redirects(monkeypatch):
    conn = _Conn()
    client = _client(monkeypatch, conn)
    # Check two cells; everything else posts as off.
    resp = client.post('/notifications/settings', data={
        'pref:plan_ready:email': 'on',
        'pref:science_update:in_app': 'on',
    })
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/notifications/settings')
    # Every write is an upsert into notification_preferences.
    upserts = [(p[1], p[2], p[3]) for (s, p) in conn.calls
               if 'INSERT INTO notification_preferences' in s]
    assert ('plan_ready', 'email', True) in upserts
    assert ('science_update', 'in_app', True) in upserts
    # An unchecked applicable cell is written False (captures the off state).
    assert ('plan_ready', 'in_app', False) in upserts
    assert conn.committed >= 1


def test_mark_read_stamps_single_row_scoped(monkeypatch):
    conn = _Conn()
    client = _client(monkeypatch, conn)
    resp = client.post('/nudges/7/read')
    assert resp.status_code == 302
    sql, params = conn.calls[-1]
    assert 'UPDATE account_nudges SET read_at = NOW()' in sql
    assert 'WHERE id = ? AND user_id = ? AND read_at IS NULL' in sql
    assert params == (7, 1)
    assert conn.committed == 1


def test_mark_all_read_scoped_to_undismissed_unread(monkeypatch):
    conn = _Conn()
    client = _client(monkeypatch, conn)
    resp = client.post('/nudges/read-all')
    assert resp.status_code == 302
    sql, params = conn.calls[-1]
    assert 'UPDATE account_nudges SET read_at = NOW()' in sql
    assert 'WHERE user_id = ? AND dismissed_at IS NULL AND read_at IS NULL' in sql
    assert params == (1,)
    assert conn.committed == 1
