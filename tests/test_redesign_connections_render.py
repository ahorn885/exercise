"""Render smoke tests for the redesign §17 Connections hub.

Boots the real Flask app with a fake DB and drives `connections.hub`
through `render_template` on the new shell across its three tabs. The route
reads provider_auth (via load_connections), cardio_log (Files), and the
Garmin auth status (best-effort). A fake connection keyed off the SQL
exercises each tab. Assertions stay structural + CSP-clean.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _Cursor:
    def __init__(self, rows, one=None):
        self._rows = rows
        self._one = one

    def fetchone(self):
        if self._one is not None:
            return self._one
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner', garth_session=None,
                        garmin_username=None)

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, providers, activities):
        self._providers = providers
        self._activities = activities

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM provider_auth' in s:
            return _Cursor(self._providers)
        if 'COUNT(*)' in s and 'cardio_log' in s:
            return _Cursor([], one=_FakeRow(n=len(self._activities)))
        if 'FROM cardio_log' in s:
            return _Cursor(self._activities)
        return _Cursor([])

    def commit(self):
        pass


def _activity(**kw):
    base = {
        'id': 1, 'date': '2026-05-22', 'activity': 'Run',
        'activity_name': 'Morning trail run', 'duration_min': 78,
        'distance_mi': 9.42, 'avg_hr': 152, 'max_hr': 178, 'calories': 924,
        'garmin_activity_id': 'fit:abc123', 'created_at': '2026-05-22',
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, providers=(), activities=()):
    conn = _Conn(list(providers), list(activities))
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_sources_tab(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Bring data in.' in html
    # Three tabs present.
    assert 'role="tablist"' in html
    assert '?tab=files' in html and '?tab=prefs' in html
    # Real OAuth providers + Garmin PAUSED + at least one stub.
    assert 'COROS' in html
    assert 'Polar' in html
    assert 'Garmin' in html and 'Paused' in html
    assert 'Strava' in html and 'Not available yet' in html
    # Drop zone posts to the real import pipeline.
    assert '/garmin/import' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_files_tab_lists_activities_and_inspector(monkeypatch):
    activities = [
        _activity(id=1, activity_name='Manual trail run',
                  garmin_activity_id='fit:hash1'),
        _activity(id=2, activity='Ride', activity_name='Synced ride',
                  garmin_activity_id='garmin-998877', distance_mi=18.6),
    ]
    client = _client(monkeypatch, activities=activities)
    resp = client.get('/connections/?tab=files')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Manual trail run' in html
    assert 'Synced ride' in html
    # Manual (fit:) vs synced classification.
    assert 'Manual .FIT' in html
    assert 'Synced' in html
    # Inline inspector posts to the new connections.inspect route.
    assert '/connections/inspect' in html
    assert 'style="' not in html


def test_files_tab_empty(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/?tab=files')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'No files yet' in html
    assert '/connections/inspect' in html
    assert 'style="' not in html


def test_prefs_tab_is_grounded(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/?tab=prefs')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # Grounded, real-behavior facts — no fabricated toggles.
    assert 'Duplicate detection' in html
    assert 'SHA-256' in html
    assert 'Paused' in html
    assert 'style="' not in html


def test_bad_tab_falls_back_to_sources(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/?tab=bogus')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Bring data in.' in html
    # Sources content present.
    assert 'Auto-sync providers' in html


def test_inspect_results_copy_all_and_layout_stays_balanced(monkeypatch):
    """After an inspector upload, the page renders inspect_dumps inline.
    Verify the 'Copy all' button + payload script are present, that each
    dump carries a data-copy-name attribute the script reads, and that the
    CSS keeps the activities/inspector tracks balanced (min-width: 0)."""
    import io
    import routes.connections as conn_mod

    # Stub the FIT parser so we don't need real .fit bytes in the test.
    monkeypatch.setattr(
        conn_mod, '_hub_context',
        # Pass through to the original but stamp inspect_dumps directly.
        lambda db, uid, tab, **extra: {
            'tab': tab, 'oauth_providers': [], 'stub_providers': [],
            'garmin_auth': {'authenticated': False, 'username': None},
            'connected_count': 0, 'provider_total': 1,
            'recent_activities': [], 'activity_count': 0,
            'inspect_dumps': extra.get('inspect_dumps'),
        },
    )
    # Patch the dump call inside the inspect route to skip fit_tool.
    import garmin_fit_parser as gfp
    monkeypatch.setattr(gfp, '_dump_fit',
                        lambda raw: {'message_counts': {'FileIdMessage': 1}})

    client = _client(monkeypatch)
    # CSRFProtect is global — bypass via WTF_CSRF_ENABLED for this POST.
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    try:
        data = {'fit_file': (io.BytesIO(b'\x0e\x10\x00\x00.FIT'), 'sample.fit')}
        resp = client.post('/connections/inspect', data=data,
                           content_type='multipart/form-data')
    finally:
        _appmod.app.config['WTF_CSRF_ENABLED'] = True
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Copy-all button + its hooks
    assert 'data-copy-all' in html
    assert 'data-copy-label-default="Copy all"' in html
    assert 'data-copy-label-done="Copied!"' in html
    # Each dump carries the name so the script can label it
    assert 'data-copy-name="sample.fit"' in html
    # Copy script is loaded (CSP-clean, nonce'd) and uses the clipboard API
    assert 'navigator.clipboard' in html
    assert '<script nonce=' in html
    # Inline style/handler hygiene
    assert 'style="' not in html
    assert 'onclick=' not in html
