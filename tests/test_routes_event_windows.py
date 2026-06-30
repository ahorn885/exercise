"""Tests for the event-window add route's single-day ergonomics (#889).

A `reduced_volume` / `no_training` window applies its effect to EVERY covered
day, so the per-day fix is to make a one-day window cheap to declare: a blank
end date means `end == start`. These exercise the route's date defaulting via
`app.test_request_context` (mirrors `tests/test_routes_profile_skills.py`'s
fake-DB substrate), capturing the dates handed to `add_event_window`.
"""

from __future__ import annotations

from datetime import date


class _FakeConn:
    def __init__(self):
        self.commits = 0

    def execute(self, sql, params=()):  # not reached — add_event_window stubbed
        raise AssertionError(f"unexpected SQL: {sql}")

    def commit(self):
        self.commits += 1


def _make_profile_app():
    import os
    from flask import Flask
    from routes.profile import bp
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__,
                template_folder=os.path.join(root, 'templates'),
                static_folder=os.path.join(root, 'static'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    from flask_wtf.csrf import CSRFProtect
    CSRFProtect(app)
    app.register_blueprint(bp)
    return app


def _post(monkeypatch, data):
    """Drive add_event_window_route with `data`, returning the kwargs the route
    handed to `add_event_window` (or None if it bailed before calling it)."""
    app = _make_profile_app()
    conn = _FakeConn()
    import routes.profile as pf_mod
    captured: dict = {}

    def _fake_add(db, uid, **kwargs):
        captured.update(kwargs)
        return 99  # the new window id (add_event_window now RETURNs it)

    monkeypatch.setattr(pf_mod, 'get_db', lambda: conn)
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'add_event_window', _fake_add)
    monkeypatch.setattr(
        pf_mod, 'evict_plan_caches_on_event_windows_change',
        lambda db, uid: None,
    )
    with app.test_request_context('/event-windows/add', method='POST', data=data):
        response = pf_mod.add_event_window_route()
    return captured or None, response


def test_blank_end_date_defaults_to_single_day(monkeypatch):
    """#889 — a blank end date yields a one-day window (end == start) so a single
    reduced/travel day doesn't have to be typed twice."""
    captured, response = _post(monkeypatch, {
        'start_date': '2026-07-03',
        'end_date': '',
        'override_type': 'reduced_volume',
        'volume_pct': '50',
    })
    assert captured is not None
    assert captured['start_date'] == date(2026, 7, 3)
    assert captured['end_date'] == date(2026, 7, 3)
    assert captured['volume_pct'] == 0.5
    assert response.status_code == 302


def test_explicit_end_date_is_preserved(monkeypatch):
    """A supplied end date still spans the full range (regression — the default
    only fills a blank)."""
    captured, _ = _post(monkeypatch, {
        'start_date': '2026-07-03',
        'end_date': '2026-07-07',
        'override_type': 'no_training',
    })
    assert captured is not None
    assert captured['start_date'] == date(2026, 7, 3)
    assert captured['end_date'] == date(2026, 7, 7)


def test_blank_start_date_still_rejected(monkeypatch):
    """A blank START date is a real error — only the END defaults (#889)."""
    captured, response = _post(monkeypatch, {
        'start_date': '',
        'end_date': '',
        'override_type': 'no_training',
    })
    assert captured is None  # bailed before add_event_window
    assert response.status_code == 302


# ─── consolidated per-day editor (#237 + #889) ───────────────────────────────


def _reduced_window(start='2026-07-03', end='2026-07-05', **kw):
    import types
    from datetime import date as _date
    base = dict(
        id=5, user_id=7,
        start_date=_date.fromisoformat(start), end_date=_date.fromisoformat(end),
        override_type='reduced_volume', unavailable_locale=None, away_locale=None,
        brought_gear=(), volume_pct=0.5, volume_by_date={}, restrictions_by_date={},
        notes='',
    )
    base.update(kw)
    return types.SimpleNamespace(**base)


class _FakeLocaleConnForPerDay:
    """A conn whose `execute` answers the per-day editor's locale SELECT."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        return _FakeLocaleCur(self._rows)

    def commit(self):
        pass


def test_per_day_editor_renders_pct_lock_indoor_per_date(monkeypatch):
    """GET builds a row per covered date with the % / lock / indoor controls,
    pre-filled from the saved volume + restriction schedule (no minutes, no
    disciplines). Rendered through the real app so base.html resolves."""
    import os
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
    os.environ.setdefault('DATABASE_URL', '')
    from datetime import date
    import flask
    import app as _appmod
    import routes.profile as pf_mod
    win = _reduced_window(
        volume_by_date={date(2026, 7, 4): 0.25},
        restrictions_by_date={date(2026, 7, 4): {'locale_lock': 'home',
                                                 'indoor_only': True}},
    )
    rows = [{'locale': 'home', 'locale_name': 'Home'}]
    monkeypatch.setattr(pf_mod, 'get_db',
                        lambda: _FakeLocaleConnForPerDay(rows))
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'load_event_window', lambda db, uid, wid: win)
    with _appmod.app.test_request_context('/profile/event-windows/5/restrictions'):
        flask.g.current_user_row = {'id': 7, 'username': 'o', 'display_name': 'O'}
        html = pf_mod.event_window_per_day(5)
    assert 'name="pct_2026-07-03"' in html   # one control set per covered day
    assert 'name="pct_2026-07-04"' in html
    assert 'name="lock_2026-07-04"' in html
    assert 'name="indoor_2026-07-04"' in html
    assert '<option value="25" selected>25% — very light</option>' not in html  # no minutes copy
    assert 'name="mins_' not in html          # minutes cap dropped
    assert 'name="excl_' not in html          # excluded disciplines dropped
    # the dialed day is pre-selected at 25%, lock=home, indoor checked
    assert '<option value="25" selected>25%</option>' in html
    assert '<option value="home" selected>Home</option>' in html


def test_per_day_post_writes_both_volume_and_restrictions(monkeypatch):
    """POST collects pct_/lock_/indoor_ per covered date and writes BOTH
    volume_by_date and restrictions_by_date, then evicts the synthesis."""
    from datetime import date
    app = _make_profile_app()
    conn = _FakeConn()
    import routes.profile as pf_mod
    win = _reduced_window(start='2026-07-03', end='2026-07-04')
    vol, restr, evicted = {}, {}, []
    monkeypatch.setattr(pf_mod, 'get_db', lambda: conn)
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'load_event_window', lambda db, uid, wid: win)
    monkeypatch.setattr(
        pf_mod, 'update_event_window_volume_by_date',
        lambda db, uid, wid, by_date: vol.update(by_date))
    monkeypatch.setattr(
        pf_mod, 'update_event_window_restrictions_by_date',
        lambda db, uid, wid, by_date: restr.update(by_date))
    monkeypatch.setattr(
        pf_mod, 'evict_plan_caches_on_event_windows_change',
        lambda db, uid: evicted.append(uid))
    with app.test_request_context(
        '/event-windows/5/restrictions', method='POST',
        data={'pct_2026-07-03': '25', 'lock_2026-07-03': 'home',
              'pct_2026-07-04': '100', 'indoor_2026-07-04': '1'},
    ):
        response = pf_mod.save_event_window_per_day(5)
    assert vol == {date(2026, 7, 3): 0.25, date(2026, 7, 4): 1.0}
    assert restr[date(2026, 7, 3)] == {'locale_lock': 'home', 'indoor_only': False}
    assert restr[date(2026, 7, 4)] == {'locale_lock': None, 'indoor_only': True}
    assert conn.commits == 1 and evicted == [7]
    assert response.status_code == 302


def test_per_day_editor_accepts_any_window_type(monkeypatch):
    """The consolidated editor applies to ANY window type — a no_training window
    renders (no longer bounced as reduced_volume-only)."""
    import os
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
    os.environ.setdefault('DATABASE_URL', '')
    import flask
    import app as _appmod
    import routes.profile as pf_mod
    win = _reduced_window(override_type='no_training', volume_pct=None)
    rows = [{'locale': 'home', 'locale_name': 'Home'}]
    monkeypatch.setattr(pf_mod, 'get_db',
                        lambda: _FakeLocaleConnForPerDay(rows))
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'load_event_window', lambda db, uid, wid: win)
    with _appmod.app.test_request_context('/profile/event-windows/5/restrictions'):
        flask.g.current_user_row = {'id': 7, 'username': 'o', 'display_name': 'O'}
        html = pf_mod.event_window_per_day(5)
    assert 'name="pct_2026-07-03"' in html  # rendered, not redirected


# ─── location picker display names (#1049) + pre-select new locale (#1058) ────


class _FakeLocaleCur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeLocaleConn:
    """Minimal conn whose only `execute` answers the event_windows() locale
    SELECT with the supplied rows."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        return _FakeLocaleCur(self._rows)


def _render_event_windows(monkeypatch, *, rows, url, draft=None, current_row=None,
                          windows=None):
    import os
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
    os.environ.setdefault('DATABASE_URL', '')
    import flask
    import app as _appmod
    import routes.profile as pf_mod
    monkeypatch.setattr(pf_mod, 'get_db', lambda: _FakeLocaleConn(rows))
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'load_event_windows', lambda db, uid: windows or [])
    monkeypatch.setattr(pf_mod, 'load_gear_registry_grouped', lambda: [])
    with _appmod.app.test_request_context(url):
        flask.g.current_user_row = current_row or {
            'id': 7, 'username': 'o', 'display_name': 'O'}
        if draft is not None:
            flask.session['event_window_draft'] = draft
        return pf_mod.event_windows()


def test_event_windows_picker_shows_display_names(monkeypatch):
    """#1049 — the location pickers render the refined display name
    (`locale_name`), keeping the slug only as the option value."""
    rows = [{'locale': 'horn_s_house', 'locale_name': "Horn's House"}]
    html = _render_event_windows(
        monkeypatch, rows=rows, url='/profile/event-windows')
    assert 'value="horn_s_house"' in html              # slug stays the value
    assert 'Horn&#39;s House' in html                  # display name is shown
    assert '>horn_s_house<' not in html                # slug is never the label


def test_event_windows_preselects_new_locale(monkeypatch):
    """#1058 — returning from an inline /locales/new with ?new_locale=<slug>
    pre-selects that location in the away field of the repopulated draft."""
    rows = [{'locale': 'lake_house', 'locale_name': 'Lake House'}]
    draft = {
        'start_date': '', 'end_date': '', 'override_type': '',
        'unavailable_locale': '', 'away_locale': '', 'brought_gear': [],
        'volume_pct': '', 'notes': '',
    }
    html = _render_event_windows(
        monkeypatch, rows=rows, draft=draft,
        url='/profile/event-windows?new_locale=lake_house')
    assert '<option value="lake_house" selected>Lake House</option>' in html


def test_event_windows_ignores_unknown_new_locale(monkeypatch):
    """#1058 — a `new_locale` the athlete doesn't own is not pre-selected."""
    rows = [{'locale': 'lake_house', 'locale_name': 'Lake House'}]
    draft = {
        'start_date': '', 'end_date': '', 'override_type': '',
        'unavailable_locale': '', 'away_locale': '', 'brought_gear': [],
        'volume_pct': '', 'notes': '',
    }
    html = _render_event_windows(
        monkeypatch, rows=rows, draft=draft,
        url='/profile/event-windows?new_locale=someone_elses_place')
    assert 'selected' not in html.split('name="away_locale"')[1].split('</select>')[0]


# ─── collapse past windows (#1057) + surface per-day editor (#889) ────────────


def test_event_windows_collapses_past_windows(monkeypatch):
    """#1057 — fully-elapsed windows render in a collapsed "Past windows"
    section, while upcoming ones stay in the main list."""
    past = _reduced_window(start='2020-01-01', end='2020-01-03')
    future = _reduced_window(start='2030-01-01', end='2030-01-03')
    rows = [{'locale': 'home', 'locale_name': 'Home'}]
    html = _render_event_windows(
        monkeypatch, rows=rows, url='/profile/event-windows',
        windows=[past, future])
    main, sep, past_section = html.partition('<details')
    assert sep, 'expected a <details> collapsed past-windows section'
    assert 'Past windows (1)' in past_section
    assert '2030-01-01' in main          # upcoming window in the main list
    assert '2020-01-01' in past_section  # elapsed window collapsed away


def test_add_form_hint_promotes_per_day_settings(monkeypatch):
    """#237/#889 — the reduced-volume hint points at the consolidated per-day
    editor instead of the old "add a separate one-day window" misdirection."""
    rows = [{'locale': 'home', 'locale_name': 'Home'}]
    html = _render_event_windows(monkeypatch, rows=rows, url='/profile/event-windows')
    assert 'per-day settings' in html
    assert 'add it as its own one-day window' not in html


def test_multiday_window_shows_inline_per_day_expander(monkeypatch):
    """#237/#889 — a multi-day window expands IN PLACE to the consolidated per-day
    editor (a visibly-styled <details> toggle), not a buried invisible link."""
    multiday = _reduced_window(start='2030-01-01', end='2030-01-05')
    rows = [{'locale': 'home', 'locale_name': 'Home'}]
    html = _render_event_windows(
        monkeypatch, rows=rows, url='/profile/event-windows', windows=[multiday])
    assert 'pf-perday-toggle' in html               # the high-contrast toggle
    assert 'Per-day settings' in html
    assert 'name="pct_2030-01-01"' in html          # inline per-day controls
    assert 'name="lock_2030-01-01"' in html
    assert 'name="indoor_2030-01-01"' in html
    assert '/restrictions' in html                  # posts to the per-day save
    assert 'Per-day rules' not in html              # old invisible link gone
    assert 'volume-days' not in html                # old volume editor gone


def test_singleday_window_has_no_per_day_expander(monkeypatch):
    """A single-day window has nothing per-day to set — no inline expander."""
    single = _reduced_window(start='2030-01-01', end='2030-01-01')
    rows = [{'locale': 'home', 'locale_name': 'Home'}]
    html = _render_event_windows(
        monkeypatch, rows=rows, url='/profile/event-windows', windows=[single])
    assert 'pf-perday-toggle' not in html


# ─── add-route guided create-flow redirect (#237/#889) ───────────────────────


def test_add_multiday_window_redirects_to_per_day_editor(monkeypatch):
    """A successful MULTI-day add lands the athlete in the per-day editor for the
    new window id (the guided create-flow)."""
    app = _make_profile_app()
    conn = _FakeConn()
    import routes.profile as pf_mod
    monkeypatch.setattr(pf_mod, 'get_db', lambda: conn)
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'add_event_window', lambda db, uid, **kw: 42)
    monkeypatch.setattr(
        pf_mod, 'evict_plan_caches_on_event_windows_change', lambda db, uid: None)
    with app.test_request_context(
        '/event-windows/add', method='POST',
        data={'start_date': '2026-07-03', 'end_date': '2026-07-07',
              'override_type': 'no_training'},
    ):
        resp = pf_mod.add_event_window_route()
    assert resp.status_code == 302
    assert '/event-windows/42/restrictions' in resp.headers['Location']


def test_add_singleday_window_does_not_redirect_to_per_day_editor(monkeypatch):
    """A single-day add keeps the plain windows-list redirect (nothing per-day)."""
    app = _make_profile_app()
    conn = _FakeConn()
    import routes.profile as pf_mod
    monkeypatch.setattr(pf_mod, 'get_db', lambda: conn)
    monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
    monkeypatch.setattr(pf_mod, 'add_event_window', lambda db, uid, **kw: 43)
    monkeypatch.setattr(
        pf_mod, 'evict_plan_caches_on_event_windows_change', lambda db, uid: None)
    with app.test_request_context(
        '/event-windows/add', method='POST',
        data={'start_date': '2026-07-03', 'end_date': '',
              'override_type': 'no_training'},
    ):
        resp = pf_mod.add_event_window_route()
    assert resp.status_code == 302
    assert '/restrictions' not in resp.headers['Location']
