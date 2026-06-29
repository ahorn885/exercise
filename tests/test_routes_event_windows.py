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
