"""Render smoke test for the redesign race-event add/edit form (finish-the-open).

`profile/race_event_edit.html` shares the 3 race partials with the migrated
onboarding/target_race. This drives the add-flow (`race_events.new_race` GET,
is_new) on the new `.app` shell — which compiles the whole template (incl. the
edit-only route section) — asserting the shell + the `.onb-form` grid wrapper +
CSP-cleanliness.
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
    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner')

    def fetchall(self):
        return []


class _Conn:
    def execute(self, sql, *a, **k):
        return _Cursor()

    def commit(self):
        pass


def _client(monkeypatch):
    conn = _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_race_event_add_render(monkeypatch):
    resp = _client(monkeypatch).get('/profile/race-events/new')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html               # new shell, not base_legacy
    assert 'Add race.' in html
    assert 'onb-form' in html                # Bootstrap grids keep gutters
    # The shared race partials are present (locale picker hidden inputs).
    assert 'name="race_format"' in html
    # Issue #885 — "Race event type" is a structured <select>, not free text,
    # and the old "sport override" framing is gone.
    assert 'Race event type' in html
    assert '<select class="form-select" id="framework_sport" name="framework_sport">' in html
    assert 'Sport (override' not in html
    assert 'type="text" class="form-control" id="framework_sport"' not in html
    assert 'style="' not in html             # CSP-clean
    assert 'onclick=' not in html
