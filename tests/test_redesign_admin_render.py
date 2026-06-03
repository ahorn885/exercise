"""Render smoke tests for the redesign §25 Admin surfaces.

Boots the real Flask app with a fake DB and drives the migrated admin
views (dashboard, user drill-in, audit log, telemetry) through
render_template on the new shell. A single fake connection routes every
SELECT by SQL fragment and returns controlled fetchone/fetchall results:

- `FROM users WHERE id=?`  → the admin user (login hydration; _require_admin
  keys off the session id == 1, so this only needs to succeed).
- `FROM users u WHERE u.id` → the drill-in target (parametrized so we can
  render both a deletable user and the un-deletable admin).
- `FROM users u` (ORDER BY) → the dashboard user list.
- `admin_audit` / `t1_hook_telemetry` / `ad_hoc_workout_suggestions` /
  `plan_refresh_log` → their respective shapes.

Assertions stay structural + CSP-clean.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _Row(dict):
    pass


ADMIN = {
    'id': 1, 'username': 'owner', 'email': 'o@x.test', 'display_name': 'Owner',
    'created_at': '2026-01-01', 'last_login': '2026-05-01',
    'strength_logs': 3, 'cardio_logs': 2, 'plans': 1, 'chat_msgs': 5,
    'locations': 2, 'rx_entries': 4, 'feedback_rows': 0, 'wellness_rows': 7,
}
ALICE = {**ADMIN, 'id': 2, 'username': 'alice', 'email': 'a@x.test',
         'display_name': 'Alice'}


class _Cursor:
    def __init__(self, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def fetchone(self):
        return _Row(self._one) if self._one is not None else None

    def fetchall(self):
        return [_Row(r) for r in self._rows]


class _Conn:
    def __init__(self, users=None, detail_user=None, audit=None, actions=None):
        self.users = users if users is not None else [ADMIN, ALICE]
        self.detail_user = detail_user if detail_user is not None else ALICE
        self.audit = audit or []
        self.actions = actions or []

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 't1_hook_telemetry' in s:
            return _Cursor(one={'n': 0})
        if 'DISTINCT action' in s:
            return _Cursor(rows=[{'action': x} for x in self.actions])
        if 'admin_audit' in s:
            return _Cursor(rows=self.audit)
        if 'ad_hoc_workout_suggestions' in s or 'plan_refresh_log' in s:
            return _Cursor(rows=[])
        if 'account_nudges' in s:
            return _Cursor(rows=[])
        if 'FROM users u WHERE u.id' in s:
            return _Cursor(one=self.detail_user)
        if 'FROM users u' in s:
            return _Cursor(rows=self.users)
        if 'FROM users' in s:
            return _Cursor(one=ADMIN)
        return _Cursor()

    def commit(self):
        pass


def _client(monkeypatch, conn):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1  # admin
    return c


def test_dashboard_renders_users(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.get('/admin/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Users.' in html
    assert 'owner' in html and 'alice' in html
    # Admin row chipped; both rows drill into the detail route.
    assert '/admin/users/2' in html
    assert 'admin' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_user_detail_has_typeconfirm_delete(monkeypatch):
    client = _client(monkeypatch, _Conn(detail_user=ALICE))
    resp = client.get('/admin/users/2')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Data footprint' in html
    # Focus-trapped type-to-confirm delete dialog, keyed to the username.
    assert 'data-dialog-open="del-user-dlg"' in html
    assert 'data-typeconfirm' in html
    assert 'data-typeconfirm-match="alice"' in html
    assert 'Delete permanently' in html
    assert '/admin/users/2/delete' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_user_detail_admin_not_deletable(monkeypatch):
    client = _client(monkeypatch, _Conn(detail_user=ADMIN))
    resp = client.get('/admin/users/1')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # The admin user shows the guard copy and no delete dialog.
    assert 'cannot be deleted' in html
    assert 'data-dialog-open' not in html


def test_audit_renders(monkeypatch):
    row = _Row({
        'id': 9, 'actor_user_id': 1, 'actor_username': 'owner',
        'action': 'delete_user', 'target_user_id': 2,
        'target_username': 'alice', 'details': '', 'created_at': '2026-05-20 10:00:00',
    })
    client = _client(monkeypatch, _Conn(audit=[row], actions=['delete_user']))
    resp = client.get('/admin/audit')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Who did what.' in html
    assert 'delete_user' in html
    assert 'alice' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_telemetry_renders(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.get('/admin/telemetry/refresh')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'System telemetry.' in html
    assert 'Ad-hoc workout generation' in html
    assert 'Plan refresh by tier' in html
    assert 'style="' not in html and 'onclick=' not in html
