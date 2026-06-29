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


class _GymEditConn(_Conn):
    """Routes the #971 gym_profiles proposal query to a controlled row; all
    other SQL (login hydration, etc.) falls back to the base conn."""

    def execute(self, sql, *a, **k):
        if 'FROM gym_profiles' in ' '.join(sql.split()):
            return _Cursor(rows=[{
                'id': 77, 'display_name': 'Hilton Downtown',
                'category': 'hotel_gym', 'equipment': '["Barbell"]',
                'disputed_items': (
                    '[{"by": 2, "adds": ["Treadmill"], '
                    '"removes": ["Barbell"], "at": "2026-06-29T12:00:00"}]'),
            }])
        return super().execute(sql, *a, **k)


def test_gym_profile_edits_renders(monkeypatch):
    """#971 Slice 3 — the crowd-sourced correction review queue renders the
    pending proposal with approve/reject actions wired to the review route."""
    client = _client(monkeypatch, _GymEditConn())
    resp = client.get('/admin/gym-profile-edits')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Crowd-sourced equipment corrections.' in html
    assert 'Hilton Downtown' in html
    assert 'Treadmill' in html  # proposed add
    assert '/admin/gym-profile-edits/77/review' in html
    assert 'User #2' in html


def test_dashboard_links_to_gym_profile_edits(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.get('/admin/')
    assert resp.status_code == 200
    assert '/admin/gym-profile-edits' in resp.get_data(as_text=True)


def test_dashboard_links_to_fit_inspect(monkeypatch):
    """The relocated FIT inspector (issue #473) is reachable from the admin
    dashboard, not the user-facing Connections/Data hub."""
    client = _client(monkeypatch, _Conn())
    resp = client.get('/admin/')
    assert resp.status_code == 200
    assert '/admin/fit-inspect' in resp.get_data(as_text=True)


def test_fit_inspect_get_renders_form(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.get('/admin/fit-inspect')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'FIT inspector.' in html
    # The upload form posts back to the admin route.
    assert '/admin/fit-inspect' in html
    assert 'name="fit_file"' in html
    assert 'style="' not in html and 'onclick=' not in html


def test_fit_inspect_post_renders_dumps_with_copy_all(monkeypatch):
    """After an upload, the admin inspector renders the dump inline with the
    'Copy all' button + per-dump data-copy-name hooks (CSP-clean)."""
    import io

    import garmin_fit_parser as gfp
    monkeypatch.setattr(gfp, '_dump_fit',
                        lambda raw: {'message_counts': {'FileIdMessage': 1}})

    client = _client(monkeypatch, _Conn())
    # CSRFProtect is global — bypass via WTF_CSRF_ENABLED for this POST.
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    try:
        data = {'fit_file': (io.BytesIO(b'\x0e\x10\x00\x00.FIT'), 'sample.fit')}
        resp = client.post('/admin/fit-inspect', data=data,
                           content_type='multipart/form-data')
    finally:
        _appmod.app.config['WTF_CSRF_ENABLED'] = True
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'data-copy-all' in html
    assert 'data-copy-label-default="Copy all"' in html
    assert 'data-copy-label-done="Copied!"' in html
    assert 'data-copy-name="sample.fit"' in html
    assert 'navigator.clipboard' in html
    assert '<script nonce=' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_fit_inspect_requires_admin(monkeypatch):
    """Non-admin users get a 403 — the dump is operator-only."""
    client = _client(monkeypatch, _Conn())
    with client.session_transaction() as sess:
        sess['user_id'] = 2  # not the admin (id 1)
    resp = client.get('/admin/fit-inspect')
    assert resp.status_code == 403


# ─── /admin/plan/<id>/inspect — #333 plan_sessions fallback ──────────────────


class _PlanInspectConn:
    """#333 — routes the three SELECTs the inspect view fires (plan_versions /
    plan_progress_blocks / plan_sessions). Decoupled from `_Conn` so the
    fallback path can be exercised without bleeding into the dashboard fakes."""

    def __init__(self, *, pv_row, progress_rows, session_payload_rows):
        self.pv_row = pv_row
        self.progress_rows = progress_rows
        self.session_payload_rows = session_payload_rows
        self.calls: list[str] = []

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        self.calls.append(s)
        # User-hydration query fires on every request via the login wall
        # (app._require_login → routes.auth.current_user). Route it to ADMIN
        # so the gate admits the session and the inspect route is reached.
        if 'FROM users WHERE id' in s:
            return _Cursor(one=ADMIN)
        if 'FROM plan_versions' in s:
            return _Cursor(one=self.pv_row)
        if 'FROM plan_progress_blocks' in s:
            return _Cursor(rows=self.progress_rows)
        if 'FROM plan_sessions' in s:
            return _Cursor(rows=self.session_payload_rows)
        return _Cursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def _pv_ready_row():
    return {
        'id': 46, 'user_id': 1, 'created_at': '2026-05-30',
        'created_via': 'plan_create',
        'scope_start_date': '2026-06-01', 'scope_end_date': '2026-08-24',
        'pattern': 'A', 'generation_status': 'ready',
        'generation_error': None, 'generation_units_cached': 12,
    }


def _session_payload_row(*, session_id, d, phase_name, week_in_phase):
    import json as _json
    return {'payload_json': _json.dumps({
        'session_id': session_id, 'plan_version_id': 46,
        'date': d, 'day_of_week': 'Mon', 'session_index_in_day': 0,
        'time_of_day': 'morning', 'kind': 'cardio',
        'discipline_id': 'D-run', 'discipline_name': 'Running',
        'locale_id': 'home', 'locale_name': 'Home',
        'duration_min': 45, 'intensity_summary': 'easy',
        'cardio_blocks': [{
            'block_kind': 'main_set', 'duration_min': 45,
            'intensity_zone': 'Z2',
            'intensity_target': {'hr_bpm_low': 125, 'hr_bpm_high': 140},
            'instructions': 'Steady easy.',
        }],
        'strength_exercises': None, 'rest_reason': None,
        'phase_metadata': {
            'phase_name': phase_name, 'week_in_phase': week_in_phase,
            'total_weeks_in_phase': 4,
            'intended_volume_band': [5.0, 7.0],
            'intended_intensity_distribution': {'Z2': 1.0},
        },
        'session_notes': 'n', 'coaching_intent': 'Easy aerobic.',
        'coaching_flags': [], 'is_ad_hoc': False,
        'ad_hoc_request_payload': None,
    })}


def test_plan_inspect_falls_back_to_plan_sessions_for_ready_plan(monkeypatch):
    """#333 — a `ready` plan with no per-block snapshot reconstructs blocks
    from `plan_sessions` so the inspect view stays useful post-completion.
    Before the fix this page rendered `blocks: 0 / sessions: 0` for the first
    finished PGE 2026 plan (pv=46) — the snapshot is in-flight only."""
    conn = _PlanInspectConn(
        pv_row=_pv_ready_row(),
        progress_rows=[],  # the in-flight snapshot is empty for a finished plan
        session_payload_rows=[
            _session_payload_row(session_id='s1', d='2026-06-01',
                                 phase_name='Base', week_in_phase=1),
            _session_payload_row(session_id='s2', d='2026-06-08',
                                 phase_name='Base', week_in_phase=2),
            _session_payload_row(session_id='s3', d='2026-06-15',
                                 phase_name='Build', week_in_phase=1),
        ],
    )
    client = _client(monkeypatch, conn)
    resp = client.get('/admin/plan/46/inspect')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Fallback notice surfaces so the operator knows where the data came from.
    assert 'Reconstructed from' in html
    assert 'plan_sessions' in html
    # The reconstructed blocks render with phase × week labels.
    assert 'Base · week 1' in html
    assert 'Base · week 2' in html
    assert 'Build · week 1' in html
    # The per-row session shape lands in the table.
    assert '2026-06-01' in html
    assert 'Running' in html


def test_plan_inspect_skips_fallback_when_progress_blocks_present(monkeypatch):
    """In-flight plan with a real snapshot: the fallback path is skipped
    entirely (no plan_sessions SELECT, no info alert) — the snapshot is the
    canonical source while the pass is still running."""
    conn = _PlanInspectConn(
        pv_row=_pv_ready_row(),
        progress_rows=[{
            'phase_idx': 0, 'phase_name': 'Base',
            'sessions_json': [{
                'date': '2026-06-01', 'discipline_name': 'Running',
                'duration_min': 45, 'intensity_summary': 'easy',
                'coaching_intent': 'Easy aerobic.',
            }],
            'synthesis_metadata_json': {'accepted': True, 'latency_ms': 1200},
            'snapshot_at': '2026-05-30 12:00:00',
        }],
        session_payload_rows=[],  # would assert below if the fallback queried this
    )
    client = _client(monkeypatch, conn)
    resp = client.get('/admin/plan/46/inspect')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Reconstructed from' not in html
    # Snapshot's own metadata still surfaces (accepted badge + snapshot_at).
    assert 'accepted' in html
    assert any('FROM plan_sessions' in c for c in conn.calls) is False


def test_plan_inspect_no_fallback_for_generating_plan(monkeypatch):
    """A `generating` plan with no snapshot yet shows the "nothing yet" copy
    instead of guessing from plan_sessions — sessions don't persist until the
    generation completes, so the fallback would always be empty for an
    in-flight plan and the snapshot is the only signal of pass progress."""
    pv = {**_pv_ready_row(), 'generation_status': 'generating'}
    conn = _PlanInspectConn(
        pv_row=pv, progress_rows=[], session_payload_rows=[],
    )
    client = _client(monkeypatch, conn)
    resp = client.get('/admin/plan/46/inspect')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Reconstructed from' not in html
    # The plan_sessions table is never queried for an in-flight plan.
    assert any('FROM plan_sessions' in c for c in conn.calls) is False
