"""Render smoke test for the redesign wellness-log viewer (finish-the-open).

Boots the real Flask app with a fake DB and drives `garmin.wellness_log`
(`/garmin/wellness`) through `render_template` on the new `.app` shell. The
route does a `latest`-date fetchone + a rows fetchall + a distinct-dates
fetchall, so the fake connection routes by SQL. Assertions stay structural +
CSP-clean, and pin the Chart.js token remap + the "Recovery" relabel.
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
    def __init__(self, one=None, all_=None):
        self._one = one
        self._all = all_ or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


_USER = _FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner')


class _Conn:
    def __init__(self, rows, dates):
        self._rows = rows
        self._dates = dates

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM wellness_log' in s:
            if 'SELECT DISTINCT date' in s:
                return _Cursor(all_=self._dates)
            if s.startswith('SELECT date FROM wellness_log'):
                # latest-date probe (fetchone)
                return _Cursor(one=(self._dates[0] if self._dates else None))
            return _Cursor(all_=self._rows)  # SELECT * ... rows
        # Shell user-hydration + anything else.
        return _Cursor(one=_USER, all_=[])

    def commit(self):
        pass


def _client(monkeypatch, rows, dates):
    conn = _Conn(rows, dates)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _csp_clean(html):
    assert 'style="' not in html
    assert 'onclick=' not in html


def _row(**kw):
    base = {'date': '2026-06-01', 'timestamp_ms': 1_717_200_000_000,
            'heart_rate': 58, 'stress_level': 22, 'body_battery': 76,
            'respiration_rate': 13, 'steps': 0, 'active_calories': 1,
            'active_time_s': 60, 'distance_m': 0}
    base.update(kw)
    return _FakeRow(base)


def test_wellness_log_populated(monkeypatch):
    rows = [_row(timestamp_ms=1_717_200_000_000),
            _row(timestamp_ms=1_717_200_060_000, heart_rate=60, body_battery=74)]
    dates = [_FakeRow(date='2026-06-01'), _FakeRow(date='2026-05-31')]
    client = _client(monkeypatch, rows, dates)
    resp = client.get('/garmin/wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Wellness log.' in html
    # Date filter + all four chart canvases + the records table.
    assert 'data-autosubmit' in html
    assert 'id="chart-hr"' in html
    assert 'id="chart-bb"' in html
    assert 'class="data"' in html
    # CONVENTIONS §E.4 — "body battery" → "Recovery"; no Garmin-ism survives.
    assert 'Recovery' in html
    assert 'Body battery' not in html
    assert 'Body bat' not in html
    # Chart.js loads (CSP-allowed CDN) and reads the NEW design tokens.
    assert 'chart.umd.min.js' in html
    assert "cssVar('--fg')" in html
    assert "cssVar('--accent')" in html
    assert '--ink' not in html  # legacy palette fully remapped
    assert '--orange' not in html
    _csp_clean(html)


def test_wellness_log_empty(monkeypatch):
    client = _client(monkeypatch, [], [])
    resp = client.get('/garmin/wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # No data → the import-prompt line, no filter form, no charts.
    assert 'No wellness data yet.' in html
    assert 'well-charts' not in html
    assert 'data-autosubmit' not in html
    _csp_clean(html)
