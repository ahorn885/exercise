"""Regression test for #1053 — the "Add route locale" form on the race-edit
page was missing a `notes` field entirely, so notes typed for a new aid
station / transition area could never reach the server and were silently
dropped. The per-row "update locale" form already had the field; only the
add form lacked it.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402
import routes.race_events as race_events_mod  # noqa: E402


class _FakeRow(dict):
    pass


class _Cursor:
    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner')

    def fetchall(self):
        return []


class _Conn:
    def execute(self, sql, *a, **k):
        return _Cursor()

    def commit(self):
        pass


def _client(monkeypatch, race_row):
    conn = _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)

    monkeypatch.setattr(race_events_mod, 'get_race_event', lambda db, uid, rid: race_row, raising=False)
    monkeypatch.setattr(race_events_mod, 'list_route_locales', lambda db, rid: [], raising=False)
    monkeypatch.setattr(race_events_mod, 'list_route_locale_equipment', lambda db, rlid: [], raising=False)
    monkeypatch.setattr(race_events_mod, '_resolve_effective_framework_sport', lambda db, uid, race: None, raising=False)
    monkeypatch.setattr(race_events_mod, '_terrain_choices', lambda db: [], raising=False)
    monkeypatch.setattr(race_events_mod, '_discipline_choices_for_race', lambda db, fs, race: [], raising=False)
    monkeypatch.setattr(race_events_mod, '_framework_sport_choices', lambda db: [], raising=False)
    monkeypatch.setattr(
        race_events_mod, '_sub_format_context',
        lambda db, race: {'sub_format_options': [], 'sub_format_options_map': {}},
        raising=False,
    )
    monkeypatch.setattr(race_events_mod, '_disclosure_acked', lambda db, uid: True, raising=False)

    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_add_route_locale_form_has_notes_field(monkeypatch):
    race_row = _FakeRow(
        id=42,
        name='Test 100',
        event_date='2026-09-01',
        race_format='ultra',
        framework_sport='trail_running',
        is_target_event=False,
        event_locale_mapbox_id='abc',
        updated_at=None,
    )
    resp = _client(monkeypatch, race_row).get('/profile/race-events/42/edit')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert 'Add route locale' in html
    add_form_start = html.index('Add route locale')
    add_form_html = html[add_form_start:]

    # The fix: the add-locale form must include a notes textarea, mirroring
    # the existing per-row update-locale form's field.
    assert 'id="new_notes"' in add_form_html
    assert 'name="notes"' in add_form_html
