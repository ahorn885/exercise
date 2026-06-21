"""Render smoke test for the redesign Edit-Rx form (Phase 6 secondary form).

Drives `rx.edit_entry` (GET) through render_template on the new shell. The
route does one `SELECT * FROM current_rx` (fetchone) plus the user-hydration
fetchone; a fake connection routes by SQL fragment. Assertions stay
structural + CSP-clean, and verify the reset-counter checkboxes appear only
when the counters are non-zero.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _Row(dict):
    pass


def _entry(**kw):
    base = {
        'id': 7, 'exercise': 'Back squat', 'movement_pattern': 'Squat',
        'current_sets': 3, 'current_reps': 5, 'current_weight': 225,
        'current_duration': None, 'weight_increment': None,
        'consecutive_failures': 0, 'sessions_since_progress': 0,
    }
    base.update(kw)
    return _Row(base)


class _Cursor:
    def __init__(self, one):
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return []


class _Conn:
    def __init__(self, entry):
        self._entry = entry

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'current_rx' in s:
            return _Cursor(self._entry)
        if 'FROM users' in s:
            return _Cursor(_Row(id=1, username='owner', email='o@x.test',
                                display_name='Owner'))
        return _Cursor(None)

    def commit(self):
        pass


def _client(monkeypatch, entry):
    conn = _Conn(entry)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_rx_form_renders_fields(monkeypatch):
    client = _client(monkeypatch, _entry())
    resp = client.get('/rx/7/edit')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Back squat' in html
    # Field names preserved for the POST handler.
    for name in ('current_sets', 'current_reps', 'current_weight',
                 'current_duration', 'weight_increment'):
        assert 'name="%s"' % name in html
    # Clean counters → no reset checkboxes.
    assert 'name="reset_failures"' not in html
    assert 'name="reset_plateau"' not in html
    assert 'style="' not in html and 'onclick=' not in html


def test_rx_form_shows_reset_checkboxes_when_stalled(monkeypatch):
    client = _client(monkeypatch, _entry(consecutive_failures=3,
                                         sessions_since_progress=6))
    resp = client.get('/rx/7/edit')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="reset_failures"' in html
    assert 'name="reset_plateau"' in html
    assert '3/3' in html and '6/5' in html
    assert 'style="' not in html
