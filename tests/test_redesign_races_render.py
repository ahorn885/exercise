"""Render smoke tests for the redesign §10 Races · event manager.

Boots the real Flask app (gate + blueprints + token-CSS shell) with a fake
DB connection, then drives `race_events.index` through `render_template`.
`list_athlete_race_events` is monkeypatched so the route sees a controlled
target / upcoming / past mix without a real Postgres. Assertions stay
structural: the redesign shell wraps the page, the target spotlight + lists
render, and the page is CSP-clean (no inline style/handlers).
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import pytest

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _FakeCursor:
    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return []


class _FakeConn:
    def execute(self, *a, **k):
        return _FakeCursor()

    def commit(self):
        pass


def _fake_get_db():
    return _FakeConn()


@pytest.fixture()
def client(monkeypatch):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', _fake_get_db, raising=False)

    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _race(**kw):
    base = {
        'id': 1, 'name': 'Race', 'event_date': '2026-01-01',
        'race_format': 'single_day', 'is_target_event': False,
        'distance_km': None, 'total_elevation_gain_m': None,
        'event_locale_name': None, 'event_locale_place_name': None,
        'notes': None,
    }
    base.update(kw)
    return base


def test_races_manager_renders_spotlight_and_lists(client, monkeypatch):
    import routes.race_events as re_mod
    today = date.today()
    target = _race(id=1, name='Boston Marathon', is_target_event=True,
                   event_date=(today + timedelta(weeks=22)).isoformat(),
                   race_format='single_day', distance_km=42.2,
                   event_locale_place_name='Boston, MA')
    upcoming = _race(id=2, name='Cherry Blossom Ten Miler',
                     event_date=(today + timedelta(weeks=14)).isoformat())
    past = _race(id=3, name='NYC Marathon',
                 event_date=(today - timedelta(weeks=30)).isoformat())
    monkeypatch.setattr(re_mod, 'list_athlete_race_events',
                        lambda db, uid: [target, upcoming, past])

    resp = client.get('/profile/race-events/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Redesign shell + active nav.
    assert 'app-shell' in html
    assert 'aria-current="page"' in html
    # Target spotlight.
    assert 'race-spotlight' in html
    assert 'Boston Marathon' in html
    assert 'Target race' in html
    assert 'phase-band' in html
    assert '22' in html  # weeks-out
    # Upcoming + past lists.
    assert 'Cherry Blossom Ten Miler' in html
    assert 'NYC Marathon' in html
    # CSP hygiene.
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_races_manager_empty_state(client, monkeypatch):
    import routes.race_events as re_mod
    monkeypatch.setattr(re_mod, 'list_athlete_race_events', lambda db, uid: [])

    resp = client.get('/profile/race-events/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'race-empty' in html
    assert "Add the race you're training for." in html
    assert 'race-spotlight' not in html
    assert 'style="' not in html


def test_races_manager_no_target_still_lists_upcoming(client, monkeypatch):
    import routes.race_events as re_mod
    today = date.today()
    upcoming = _race(id=5, name='Local 10K',
                     event_date=(today + timedelta(weeks=4)).isoformat())
    monkeypatch.setattr(re_mod, 'list_athlete_race_events',
                        lambda db, uid: [upcoming])

    resp = client.get('/profile/race-events/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Local 10K' in html
    assert 'race-spotlight' not in html
    # "Set as target" affordance present on the non-target upcoming row.
    assert 'Set as target' in html
    assert 'style="' not in html
