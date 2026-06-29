"""Tests for `routes/conditions.py` — the conditions logging surface.

Focus: the dashboard "Log conditions" nudge deep-links here with a
`cardio_log_id`. The conditions row must save with that FK so the nudge
clears (#955). The session dropdown is capped at 60 recent rows, so a
prefilled session outside that window would otherwise not be selectable
and the link would be dropped — `new_entry` injects the prefilled session
into the dropdown so the FK is always set.

Mirrors the SQL-aware fake-connection pattern in
`tests/test_routes_dashboard.py`.
"""

from __future__ import annotations


class _Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Conn:
    """SQL-aware fake: the prefill lookup returns a session that is NOT in the
    capped dropdown list, so the route must inject it for the option to render
    as selected."""

    def __init__(self, *, prefill_row, dropdown_rows):
        self._prefill_row = prefill_row
        self._dropdown_rows = dropdown_rows

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if 'FROM cardio_log WHERE id=' in s:        # prefill lookup
            return _Cursor(one=self._prefill_row)
        if 'FROM cardio_log' in s:                  # _load_cardio_sessions
            return _Cursor(many=self._dropdown_rows)
        if 'FROM clothing_options' in s:            # _load_clothing_options
            return _Cursor(many=[])
        if 'FROM users' in s:                       # before-request auth hydration
            return _Cursor(one=_Row(
                id=1, username='owner', email='o@x.test', display_name='Owner'))
        return _Cursor(one=None, many=[])

    def commit(self):
        pass


def _client(monkeypatch, conn):
    import os
    import sys

    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-conditions-tests')
    os.environ['DATABASE_URL'] = ''

    import app as _appmod

    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda: conn, raising=False)

    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


class TestPrefillAlwaysSelectable:
    """The prefilled session must render as a *selected* option even when it
    falls outside the 60-row dropdown window (#955) — otherwise conditions save
    with no FK link and the dashboard nudge never clears."""

    def test_out_of_window_prefill_is_injected_and_selected(self, monkeypatch):
        prefill = _Row(id=999, date='2026-06-25', activity='Road Cycling',
                       activity_name='Morning ride')
        # Dropdown window does NOT include id 999.
        dropdown = [_Row(id=1, date='2026-06-29', activity='Running',
                         activity_name='Easy')]
        conn = _Conn(prefill_row=prefill, dropdown_rows=dropdown)
        client = _client(monkeypatch, conn)

        resp = client.get('/conditions/new?cardio_log_id=999')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # The linked session is present as an option and is preselected.
        assert 'value="999"' in html
        assert 'selected' in html
        # The dropdown's other recent session is still listed.
        assert 'value="1"' in html

    def test_no_prefill_renders_unlinked(self, monkeypatch):
        dropdown = [_Row(id=1, date='2026-06-29', activity='Running',
                         activity_name='Easy')]
        conn = _Conn(prefill_row=None, dropdown_rows=dropdown)
        client = _client(monkeypatch, conn)

        resp = client.get('/conditions/new')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'value="999"' not in html
