"""Render smoke tests for the redesign §16 Locations.

Boots the real Flask app with a fake DB and drives `locales.list_profiles`
through `render_template` on the new shell. Track 1: equipment per locale is
resolved via `locations.locale_effective_tags` (gym_profiles.equipment +
overrides, layer0 canonical names) rather than the dropped locale_equipment
join; the fake connection answers the locale_profiles list, per-locale
gym_profile_id lookups, gym_profiles.equipment, and overrides, plus the
user-hydration fetchone. Assertions stay structural + CSP-clean.
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402

_USER_ROW = None  # set lazily below


class _FakeRow(dict):
    pass


_USER_ROW = _FakeRow(id=1, username='owner', email='o@x.test',
                     display_name='Owner')


class _Cursor:
    def __init__(self, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, profiles, gym_profiles=None, overrides=None):
        self._profiles = profiles
        self._gym = gym_profiles or {}      # gym_profile_id -> equipment JSON
        self._overrides = overrides or {}   # locale -> list of override rows

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        params = a[0] if a else ()
        if 'gym_profile_id FROM locale_profiles' in s:
            locale = params[1] if len(params) > 1 else None
            prof = next((p for p in self._profiles if p.get('locale') == locale), None)
            if prof is None:
                return _Cursor(one=None)
            return _Cursor(one=_FakeRow(gym_profile_id=prof.get('gym_profile_id')))
        if 'FROM gym_profiles WHERE id' in s:
            gid = params[0] if params else None
            return _Cursor(one=_FakeRow(equipment=self._gym.get(gid)))
        if 'FROM locale_equipment_overrides' in s:
            locale = params[1] if len(params) > 1 else None
            return _Cursor(rows=self._overrides.get(locale, []))
        if 'FROM locale_profiles' in s:
            return _Cursor(rows=self._profiles)
        # Default (incl. user hydration before_request) → the owner row.
        return _Cursor(one=_USER_ROW)

    def commit(self):
        pass


def _profile(**kw):
    base = {
        'locale': 'home', 'locale_name': None, 'chain_name': None,
        'category': None, 'manual_entry': 0, 'mapbox_id': None,
        'gym_profile_id': None, 'preferred': False,
        'notes': None, 'updated_at': '2026-05-14',
        'address': None, 'street': None, 'state': None, 'postal_code': None,
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, conn):
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
        _profile(locale='home', notes='Garage at 65°F.',
                 gym_profile_id=1, preferred=True),
        _profile(locale='Equinox Cap Hill', locale_name='Equinox Capitol Hill',
                 chain_name='Equinox', category='gym', manual_entry=0,
                 mapbox_id='mb-123', gym_profile_id=2),
    ]
    gym = {
        1: json.dumps(['Barbell', 'Squat rack']),
        2: json.dumps(['Olympic platform']),
    }
    client = _client(monkeypatch, _Conn(profiles, gym_profiles=gym))
    resp = client.get('/locales')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Where you train.' in html
    # Both athlete-created locales (home + Equinox) render as cards.
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
    client = _client(monkeypatch, _Conn([]))
    resp = client.get('/locales')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # Nothing configured → the "Where do you train?" hero, not blank cards.
    assert 'Where do you train?' in html
    assert 'loc-grid' not in html
    # Legacy enum set-up shortcuts are retired (WS-B) — the empty hero leads
    # with the search/add path to the real new-locale route.
    assert '/locales/home/edit' not in html
    assert '/locales/new' in html
    assert 'Search by address'.lower() in html.lower()
    assert 'style="' not in html
