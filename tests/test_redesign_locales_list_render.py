"""Render smoke tests for the redesign §16 Locations.

Boots the real Flask app with a fake DB and drives `locales.list_profiles`
through `render_template` on the new shell. The route makes two reads
(locale_profiles, locale_equipment join) plus the user-hydration fetchone;
a fake connection keyed off the SQL exercises the populated-grid vs
empty-hero branches. Assertions stay structural + CSP-clean.
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
    def __init__(self, profiles, equipment):
        self._profiles = profiles
        self._equipment = equipment

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM locale_profiles' in s:
            return _Cursor(self._profiles)
        if 'FROM locale_equipment' in s:
            return _Cursor(self._equipment)
        return _Cursor([])

    def commit(self):
        pass


def _profile(**kw):
    base = {
        'locale': 'home', 'locale_name': None, 'chain_name': None,
        'category': None, 'manual_entry': 0, 'mapbox_id': None,
        'city': 'Washington', 'notes': None, 'updated_at': '2026-05-14',
        'address': None, 'street': None, 'state': None, 'postal_code': None,
    }
    base.update(kw)
    return _FakeRow(base)


def _equip(locale, tag, label):
    return _FakeRow(locale=locale, tag=tag, label=label)


def _client(monkeypatch, profiles, equipment):
    conn = _Conn(profiles, equipment)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_locations_grid_with_profiles(monkeypatch):
    profiles = [
        _profile(locale='home', city='Washington', notes='Garage at 65°F.'),
        _profile(locale='Equinox Cap Hill', locale_name='Equinox Capitol Hill',
                 chain_name='Equinox', category='gym', manual_entry=0,
                 mapbox_id='mb-123', city='Washington'),
    ]
    equipment = [
        _equip('home', 'barbell', 'Barbell'),
        _equip('home', 'rack', 'Squat rack'),
        _equip('Equinox Cap Hill', 'platform', 'Olympic platform'),
    ]
    client = _client(monkeypatch, profiles, equipment)
    resp = client.get('/locales')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Where you train.' in html
    # Legacy enum (home) + custom (Equinox) both render as cards.
    assert 'loc-grid' in html
    assert 'Equinox Capitol Hill' in html
    assert 'Barbell' in html
    # Custom location gets the refresh (mapbox) + delete actions.
    assert '/locales/Equinox%20Cap%20Hill/refresh' in html
    assert '/locales/Equinox%20Cap%20Hill/delete' in html
    # Add-another tile points at the real new-locale route.
    assert '/locales/new' in html
    # Not the empty hero.
    assert 'Where do you train?' not in html
    assert 'data-confirm=' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_locations_empty_hero(monkeypatch):
    client = _client(monkeypatch, [], [])
    resp = client.get('/locales')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # Nothing configured → the "Where do you train?" hero, not blank cards.
    assert 'Where do you train?' in html
    assert 'loc-grid' not in html
    # Each legacy enum offers a set-up shortcut to its edit route.
    assert '/locales/home/edit' in html
    assert '/locales/hotel/edit' in html
    assert 'Search by address'.lower() in html.lower()
    assert 'style="' not in html
