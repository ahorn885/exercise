"""Tests for the profile Skills capture surface — the Gear & skills tab
(`/profile?tab=gear`, #894) GET render + `/profile/skills` POST handler.
Mirrors the `tests/test_onboarding_skills.py` `_FakeConn` substrate.
"""

from __future__ import annotations


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

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


class TestSaveSkillsRoute:
    def test_post_upserts_state_evicts_and_redirects_to_skills_tab(
        self, monkeypatch
    ):
        app = _make_profile_app()
        conn = _FakeConn()
        # vocab SELECT inside save_skills
        conn.queue_response(rows=[
            {'toggle_name': 'climbing_roped',
             'display_label': 'X', 'description': 'X'},
            {'toggle_name': 'whitewater_handling',
             'display_label': 'X', 'description': 'X'},
        ])
        import routes.profile as pf_mod
        evictions = []
        monkeypatch.setattr(pf_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
        monkeypatch.setattr(
            pf_mod, 'evict_layer1_on_skill_toggle_change',
            lambda db, uid: evictions.append(uid),
        )

        with app.test_request_context(
            '/profile/skills',
            method='POST',
            data={'skill__whitewater_handling': '1'},
        ):
            response = pf_mod.save_skills()

        # 1 vocab SELECT + 2 UPSERTs.
        assert len(conn.calls) == 3
        upserts = [(sql, params) for sql, params in conn.calls
                   if 'INSERT INTO athlete_skill_toggles' in sql]
        assert len(upserts) == 2
        states_by_toggle = {p[1]: p[2] for _, p in upserts}
        assert states_by_toggle == {
            'climbing_roped': False,
            'whitewater_handling': True,
        }
        assert conn.commits == 1
        assert evictions == [7]
        # Redirects back to the Gear & skills tab on /profile (#894).
        assert response.status_code == 302
        assert 'tab=gear' in response.location

    def test_empty_vocab_no_ops_but_still_redirects(self, monkeypatch):
        app = _make_profile_app()
        conn = _FakeConn()
        conn.queue_response(rows=[])  # empty vocab
        import routes.profile as pf_mod
        evictions = []
        monkeypatch.setattr(pf_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(pf_mod, 'current_user_id', lambda: 7)
        monkeypatch.setattr(
            pf_mod, 'evict_layer1_on_skill_toggle_change',
            lambda db, uid: evictions.append(uid),
        )

        with app.test_request_context(
            '/profile/skills', method='POST', data={}
        ):
            response = pf_mod.save_skills()

        assert len(conn.calls) == 1  # vocab SELECT only
        assert conn.commits == 0
        assert evictions == []
        assert response.status_code == 302
        assert 'tab=gear' in response.location
