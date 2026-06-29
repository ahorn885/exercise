"""Tests for the Connections source-precedence picker (#196 P5 B4).

Covers the `_precedence_options` dropdown builder (pure) + the
`POST /connections/source-precedence` route: set a pin, clear to automatic, and
the no-change no-op. The apply helpers (`apply_wellness_pin_change` /
`apply_cardio_pin_change`) and the Layer-4 cache are exercised by their own
tests — here they're monkeypatched so the route is tested in isolation with a
fake connection (no live Postgres / cache backend; egress is blocked).
"""
from __future__ import annotations


class _Cursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return None


class _FakeConn:
    """Serves the `get_source_preferences` read from `pins`; records every
    (sql, params) so a test can assert the set/clear writes + commit count."""

    def __init__(self, pins=None):
        self.calls: list[tuple] = []
        self.commits = 0
        self._pins = pins or {}

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM user_source_preferences" in " ".join(sql.split()):
            return _Cursor(rows=[{"domain": d, "preferred_provider": p}
                                 for d, p in self._pins.items()])
        return _Cursor()

    def commit(self):
        self.commits += 1


def _make_connections_app():
    import os
    from flask import Flask
    from flask_wtf.csrf import CSRFProtect
    from routes.connections import bp
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__,
                template_folder=os.path.join(root, 'templates'),
                static_folder=os.path.join(root, 'static'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    CSRFProtect(app)
    app.register_blueprint(bp)
    return app


def _patch(monkeypatch, conn, applied):
    import routes.connections as cm
    monkeypatch.setattr(cm, 'get_db', lambda: conn)
    monkeypatch.setattr(cm, 'current_user_id', lambda: 7)
    monkeypatch.setattr(cm, 'apply_wellness_pin_change',
                        lambda db, cache, uid: applied.append(('wellness', uid)))
    monkeypatch.setattr(cm, 'apply_cardio_pin_change',
                        lambda db, cache, uid: applied.append(('cardio', uid)))
    return cm


class TestPrecedenceOptions:
    def test_lists_all_valid_providers_with_automatic_first(self):
        import routes.connections as cm
        from source_preferences_repo import VALID_PROVIDERS, WELLNESS
        opts = cm._precedence_options(WELLNESS, 'whoop')
        assert opts[0]['value'] == ''            # Automatic leads
        assert opts[0]['selected'] is False      # a pin is set → not automatic
        assert {o['value'] for o in opts[1:]} == set(VALID_PROVIDERS[WELLNESS])
        whoop = next(o for o in opts if o['value'] == 'whoop')
        assert whoop['selected'] is True
        assert all(not o['selected'] for o in opts if o['value'] not in ('', 'whoop'))

    def test_automatic_selected_when_no_pin(self):
        import routes.connections as cm
        from source_preferences_repo import CARDIO
        opts = cm._precedence_options(CARDIO, None)
        assert opts[0]['value'] == '' and opts[0]['selected'] is True
        assert all(not o['selected'] for o in opts[1:])


class TestSourcePrecedenceRoute:
    def test_set_wellness_pin_applies_and_redirects(self, monkeypatch):
        app = _make_connections_app()
        conn = _FakeConn(pins={})            # no current pins
        applied = []
        cm = _patch(monkeypatch, conn, applied)
        with app.test_request_context(
            '/connections/source-precedence', method='POST',
            data={'pin_wellness': 'whoop', 'pin_cardio': ''},
        ):
            resp = cm.source_precedence()
        inserts = [(s, p) for s, p in conn.calls
                   if 'INSERT INTO user_source_preferences' in s]
        assert len(inserts) == 1
        assert inserts[0][1] == (7, 'wellness', 'whoop')
        # Cardio stayed '' → Automatic == no current pin → no-op (no cardio apply).
        assert applied == [('wellness', 7)]
        assert conn.commits == 1
        assert resp.status_code == 302 and 'tab=sources' in resp.location

    def test_clear_cardio_pin_to_automatic(self, monkeypatch):
        app = _make_connections_app()
        conn = _FakeConn(pins={'cardio': 'strava'})
        applied = []
        cm = _patch(monkeypatch, conn, applied)
        with app.test_request_context(
            '/connections/source-precedence', method='POST',
            data={'pin_wellness': '', 'pin_cardio': ''},
        ):
            resp = cm.source_precedence()
        deletes = [(s, p) for s, p in conn.calls
                   if 'DELETE FROM user_source_preferences' in s]
        assert len(deletes) == 1
        assert deletes[0][1] == (7, 'cardio')
        assert applied == [('cardio', 7)]      # only cardio changed
        assert conn.commits == 1
        assert resp.status_code == 302 and 'tab=sources' in resp.location

    def test_no_change_does_not_apply_or_commit(self, monkeypatch):
        app = _make_connections_app()
        conn = _FakeConn(pins={'wellness': 'garmin'})
        applied = []
        cm = _patch(monkeypatch, conn, applied)
        with app.test_request_context(
            '/connections/source-precedence', method='POST',
            data={'pin_wellness': 'garmin', 'pin_cardio': ''},
        ):
            resp = cm.source_precedence()
        assert not [s for s, _ in conn.calls
                    if 'INSERT INTO user_source_preferences' in s
                    or 'DELETE FROM user_source_preferences' in s]
        assert applied == []
        assert conn.commits == 0
        assert resp.status_code == 302 and 'tab=sources' in resp.location
