"""Render smoke tests for the redesign §15 Exercises library.

Boots the real Flask app with a fake DB and drives `rx.list_entries`
through `render_template` on the new shell. The route makes three reads
(current_rx join, inventory-only, locale list) plus the user-hydration
fetchone; a fake connection that hands each .execute() a cursor whose
fetchall() is keyed off the SQL is enough to exercise the
current-Rx-table / catalog / plateau-alert / no-Rx-hero branches.
Assertions stay structural + CSP-clean (no inline style/handlers).
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
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return self._rows


class _Conn:
    """Routes each SELECT to a controlled row list. The three list reads are
    distinguished by a fragment of their SQL; everything else (user hydration)
    uses fetchone(), which ignores the rows."""

    def __init__(self, entries, inventory, locales):
        self._entries = entries
        self._inventory = inventory
        self._locales = locales

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        # Order matters: the inventory query carries a `FROM current_rx cr`
        # NOT EXISTS subquery, so match it before the plain current_rx read.
        if 'FROM exercise_inventory ei' in s and 'NOT EXISTS' in s:
            return _Cursor(self._inventory)
        if 'FROM current_rx cr' in s:
            return _Cursor(self._entries)
        if 'FROM locale_profiles' in s:
            return _Cursor(self._locales)
        return _Cursor([])

    def commit(self):
        pass


def _entry(**kw):
    base = {
        'id': 1, 'exercise': 'Back squat', 'discipline': 'Foot',
        'type': 'Compound', 'movement_pattern': 'Squat',
        'current_sets': 3, 'current_reps': 5, 'current_weight': 225,
        'last_performed': '2026-05-25', 'last_outcome': '↑ progress',
        'consecutive_failures': 0, 'sessions_since_progress': 0,
        'video_reference': None, 'where_available': None,
        'ei_suggested_volume': None,
    }
    base.update(kw)
    return _FakeRow(base)


def _inv(**kw):
    base = {
        'exercise': 'Kettlebell swing', 'discipline': 'Cross',
        'type': 'Assist.', 'movement_pattern': 'Hinge',
        'suggested_volume': '3 × 15', 'where_available': 'Home gym',
        'video_reference': None,
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, entries, inventory, locales):
    conn = _Conn(entries, inventory, locales)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_rx_list_renders_current_rx_and_catalog(monkeypatch):
    entries = [
        _entry(id=1, exercise='Back squat', last_outcome='↑ progress'),
        # Stalled exercise → plateau alert + per-row deload button.
        _entry(id=2, exercise='Overhead press', last_outcome='↓ reduce',
               sessions_since_progress=6, consecutive_failures=3),
    ]
    client = _client(monkeypatch, entries, [_inv()], [])
    resp = client.get('/rx')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Exercises.' in html
    # With current Rx present, the no-Rx hero must NOT show.
    assert 'No Rx yet.' not in html
    assert 'Back squat' in html
    assert 'Overhead press' in html
    # Plateau alert + deload action both rendered for the stalled row.
    assert 'Plateau check' in html
    assert '/rx/2/deload' in html
    assert '−10%' in html
    # Catalog (inventory-only) section.
    assert 'Kettlebell swing' in html
    assert 'id="catalog"' in html
    # Progress/outcome use chips; CSP-clean (no inline style/handlers).
    assert 'data-confirm=' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_rx_list_no_rx_hero(monkeypatch):
    client = _client(monkeypatch, [], [_inv()], [])
    resp = client.get('/rx')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'No Rx yet.' in html
    assert 'Generate plan' in html
    # No current-Rx table; catalog still browsable inline.
    assert 'Current Rx ·' not in html
    assert 'id="catalog"' in html
    assert 'style="' not in html


def test_rx_list_prescribed_but_unlogged_reads_no_log_yet(monkeypatch):
    # #693: a prescribed exercise (has current_sets) that hasn't been logged yet
    # is "set up" — its Outcome cell must read "no log yet", not the misleading
    # "needs setup" (which wrongly implied the exercise wasn't configured).
    entries = [
        _entry(id=5, exercise='Front squat', current_sets=3, current_reps=5,
               last_outcome=None, last_performed=None),
    ]
    client = _client(monkeypatch, entries, [], [])
    resp = client.get('/rx')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Front squat' in html
    assert 'no log yet' in html
    assert 'needs setup' not in html


def test_rx_list_filtered_empty_shows_clear(monkeypatch):
    client = _client(monkeypatch, [], [], [])
    resp = client.get('/rx?discipline=Bike')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # A filter is active but nothing matched → no-match note, not the hero.
    assert 'No Rx yet.' not in html
    assert 'No prescribed exercises match' in html
    assert 'Clear filters' in html
    assert 'style="' not in html
