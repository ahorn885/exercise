"""Render smoke tests for the redesign onboarding wizard — Slice A.

The onboarding steps were the last app surface still on `base_legacy`. Slice A
migrates Connect / Profile-prefill / Skills / Schedule onto the new `.app`
shell behind a shared progress stepper (`_onb_steps.html`). These boot the
real app with a permissive fake DB and drive each GET route, asserting the
new shell + the stepper + CSP-cleanliness. (Locations + Target race are
Slice B.)
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
    def __init__(self, one):
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return []


_TARGET = _FakeRow(id=9, name='Pocket Gopher Extreme', race_format='continuous_multi_day',
                   event_date=None, race_terrain=None, previous_attempts=None,
                   included_discipline_ids=None, event_locale_lat=None, event_locale_lng=None)


class _Conn:
    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM users' in s:
            return _Cursor(_FakeRow(id=1, username='owner', email='o@x.test',
                                    display_name='Owner'))
        if 'is_target_event = TRUE' in s:
            return _Cursor(_TARGET)   # a target race exists → route_locales won't redirect
        return _Cursor(None)

    def commit(self):
        pass


def _client(monkeypatch):
    conn = _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _assert_onboarding_shell(html, current_label):
    assert 'app-shell' in html              # new shell, not base_legacy
    assert 'onb-steps' in html              # shared progress stepper
    assert 'Set up' in html
    assert 'style="' not in html            # CSP-clean
    assert 'onclick=' not in html


def test_connect_render(monkeypatch):
    resp = _client(monkeypatch).get('/onboarding/connect')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'connect')
    assert 'Connect your providers.' in html
    # The continue/skip forms survive.
    assert "url_for" not in html  # sanity: rendered, not raw
    assert '/onboarding/continue' in html or 'onboarding.continue' in html


def test_prefill_render(monkeypatch):
    resp = _client(monkeypatch).get('/onboarding/prefill')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'prefill')
    assert 'Review your profile data.' in html


def test_skills_render(monkeypatch):
    resp = _client(monkeypatch).get('/onboarding/skills')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'skills')
    assert 'technical skills' in html


def test_schedule_render(monkeypatch):
    resp = _client(monkeypatch).get('/onboarding/schedule')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'schedule')
    assert 'When can you train?' in html


def test_locales_render(monkeypatch):
    resp = _client(monkeypatch).get('/onboarding/locales')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'locales')
    assert 'Where do you train?' in html
    # F5 (#608 item 3): the optional event-windows card links into the live
    # editor with a return_to back to this step — surfaced, not gated.
    assert 'event windows' in html
    assert 'Set up event windows' in html
    assert '/profile/event-windows?return_to=' in html


def test_target_race_render(monkeypatch):
    resp = _client(monkeypatch).get('/onboarding/target-race')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'target_race')
    assert 'What race are you training for?' in html
    # Bootstrap-grid form body kept under the gutter-restoring wrapper.
    assert 'onb-form' in html
    # Issue #885 — structured "Race event type" <select>, moved up by the
    # race format; the free-text "sport override" is gone.
    assert 'Race event type' in html
    assert '<select class="form-select" id="framework_sport" name="framework_sport">' in html
    assert 'Sport (override' not in html


def test_route_locales_render(monkeypatch):
    # A target race exists (faked), so the route renders rather than redirecting.
    resp = _client(monkeypatch).get('/onboarding/route-locales')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_onboarding_shell(html, 'route_locales')
    assert 'Map the race route.' in html
