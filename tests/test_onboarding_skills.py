"""Tests for the Bucket C (l) capture-surface follow-on onboarding
steps (`/onboarding/locales` Step 4 + `/onboarding/skills` Step 5) +
the `athlete_skill_toggles_repo` helpers they delegate to.

Mirrors the `_FakeConn` substrate from
`tests/test_onboarding_race_events.py` — no real DB connection.
"""

from __future__ import annotations

import pytest


# ─── Shared fake conn (same shape as test_onboarding_race_events) ───────


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


def _make_onboarding_app():
    import os
    from flask import Flask
    from routes.onboarding import bp
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__,
                template_folder=os.path.join(root, 'templates'),
                static_folder=os.path.join(root, 'static'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # Initialize CSRFProtect so {{ csrf_token() }} in base.html resolves
    # (WTF_CSRF_ENABLED=False still leaves the jinja global registered).
    from flask_wtf.csrf import CSRFProtect
    CSRFProtect(app)
    app.register_blueprint(bp)
    return app


# ─── Repo helpers ───────────────────────────────────────────────────────


class TestLoadActiveSkillCapabilityToggleVocab:
    def test_returns_active_rows_as_dicts(self):
        from athlete_skill_toggles_repo import (
            load_active_skill_capability_toggle_vocab,
        )
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'toggle_name': 'climbing_roped',
             'display_label': 'Roped climbing',
             'description': 'Lead/top-rope.'},
            {'toggle_name': 'whitewater_handling',
             'display_label': 'Whitewater',
             'description': 'Moving-water skill.'},
        ])
        result = load_active_skill_capability_toggle_vocab(conn)
        assert result == [
            {'toggle_name': 'climbing_roped',
             'display_label': 'Roped climbing',
             'description': 'Lead/top-rope.'},
            {'toggle_name': 'whitewater_handling',
             'display_label': 'Whitewater',
             'description': 'Moving-water skill.'},
        ]
        sql, _ = conn.calls[0]
        assert 'layer0.skill_capability_toggles' in sql
        assert 'superseded_at IS NULL' in sql

    def test_empty_when_populate_not_applied(self):
        from athlete_skill_toggles_repo import (
            load_active_skill_capability_toggle_vocab,
        )
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert load_active_skill_capability_toggle_vocab(conn) == []


class TestGetAthleteSkillToggles:
    def test_returns_dict_keyed_by_toggle_name(self):
        from athlete_skill_toggles_repo import get_athlete_skill_toggles
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'toggle_name': 'climbing_roped', 'enabled': True},
            {'toggle_name': 'swim_open_water', 'enabled': False},
        ])
        result = get_athlete_skill_toggles(conn, user_id=42)
        assert result == {'climbing_roped': True, 'swim_open_water': False}
        sql, params = conn.calls[0]
        assert 'athlete_skill_toggles' in sql
        assert params == (42,)

    def test_empty_athlete_yields_empty_dict(self):
        from athlete_skill_toggles_repo import get_athlete_skill_toggles
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert get_athlete_skill_toggles(conn, user_id=42) == {}


class TestUpsertAthleteSkillToggles:
    def test_upserts_one_row_per_toggle(self):
        from athlete_skill_toggles_repo import upsert_athlete_skill_toggles
        conn = _FakeConn()
        upsert_athlete_skill_toggles(conn, 42, {
            'climbing_roped': True,
            'swim_open_water': False,
        })
        assert len(conn.calls) == 2
        for sql, params in conn.calls:
            assert 'INSERT INTO athlete_skill_toggles' in sql
            assert 'ON CONFLICT (user_id, toggle_name) DO UPDATE' in sql
            assert params[0] == 42
            assert params[1] in ('climbing_roped', 'swim_open_water')
            assert isinstance(params[2], bool)

    def test_empty_dict_no_ops(self):
        from athlete_skill_toggles_repo import upsert_athlete_skill_toggles
        conn = _FakeConn()
        upsert_athlete_skill_toggles(conn, 42, {})
        assert conn.calls == []


class TestParseSkillForm:
    def test_checked_rows_become_true(self):
        from athlete_skill_toggles_repo import parse_skill_form
        vocab = [
            {'toggle_name': 'climbing_roped',
             'display_label': 'X', 'description': 'X'},
            {'toggle_name': 'swim_open_water',
             'display_label': 'X', 'description': 'X'},
        ]
        form = {'skill__climbing_roped': '1'}
        result = parse_skill_form(form, vocab)
        # Climbing checked → True; swim absent → explicit False (default-OFF).
        assert result == {'climbing_roped': True, 'swim_open_water': False}

    def test_unknown_form_keys_ignored(self):
        from athlete_skill_toggles_repo import parse_skill_form
        vocab = [
            {'toggle_name': 'climbing_roped',
             'display_label': 'X', 'description': 'X'},
        ]
        form = {'skill__unknown_toggle': '1', 'random_field': 'whatever'}
        result = parse_skill_form(form, vocab)
        assert result == {'climbing_roped': False}

    def test_empty_vocab_returns_empty_dict(self):
        from athlete_skill_toggles_repo import parse_skill_form
        assert parse_skill_form({}, []) == {}


class TestEvictLayer1OnSkillToggleChange:
    def test_fires_layer1_eviction(self, monkeypatch):
        import athlete_skill_toggles_repo as repo
        calls = []
        monkeypatch.setattr(
            repo, 'evict_on_layer_change',
            lambda cache, uid, layer: calls.append((uid, layer)) or 7,
        )
        # Layer4Cache + PostgresCacheBackend instantiations are inert in
        # this test — they don't touch the DB until cache.invalidate_user
        # which the monkeypatched evict_on_layer_change replaces.
        conn = _FakeConn()
        repo.evict_layer1_on_skill_toggle_change(conn, user_id=42)
        assert calls == [(42, 'layer1')]


# ─── Onboarding routes ──────────────────────────────────────────────────


class TestAthleteLocalesForReview:
    def test_empty_athlete_yields_four_unconfigured_legacy_slots(self):
        from routes.onboarding import _athlete_locales_for_review
        conn = _FakeConn()
        conn.queue_response(rows=[])
        result = _athlete_locales_for_review(conn, 42)
        assert len(result) == 4
        for entry in result:
            assert entry['is_custom'] is False
            assert entry['configured'] is False
        assert {e['slug'] for e in result} == {
            'home', 'hotel', 'partner', 'airport',
        }

    def test_configured_legacy_slot_uses_locale_name(self):
        from routes.onboarding import _athlete_locales_for_review
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'locale': 'home', 'locale_name': 'My Apartment',
             'category': 'home_gym'},
        ])
        result = _athlete_locales_for_review(conn, 42)
        home = next(e for e in result if e['slug'] == 'home')
        assert home['label'] == 'My Apartment'
        assert home['configured'] is True
        assert home['is_custom'] is False

    def test_custom_locale_appended_with_is_custom_true(self):
        from routes.onboarding import _athlete_locales_for_review
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'locale': 'trailhead_alpha', 'locale_name': 'Alpha Trail',
             'category': 'outdoor_park'},
        ])
        result = _athlete_locales_for_review(conn, 42)
        assert len(result) == 5  # 4 legacy + 1 custom
        custom = result[-1]
        assert custom['slug'] == 'trailhead_alpha'
        assert custom['label'] == 'Alpha Trail'
        assert custom['is_custom'] is True
        assert custom['category'] == 'outdoor_park'


class TestLocalesRoute:
    def test_get_passes_athlete_locales_to_template(self, monkeypatch):
        # We monkeypatch render_template to capture kwargs instead of
        # actually rendering — the full base.html template needs every
        # blueprint registered (dashboard.index, etc.) which is more
        # plumbing than this slice cares about.
        app = _make_onboarding_app()
        conn = _FakeConn()
        conn.queue_response(rows=[])  # empty locale_profiles
        import routes.onboarding as ob_mod
        captured = {}
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            ob_mod, 'render_template',
            lambda tpl, **kw: captured.update({'tpl': tpl, **kw}) or 'OK',
        )

        with app.test_request_context('/onboarding/locales', method='GET'):
            ob_mod.locales()

        assert captured['tpl'] == 'onboarding/locales.html'
        assert len(captured['athlete_locales']) == 4  # 4 legacy slots
        assert captured['post_step_locales_target'] == '/onboarding/skills'

    def test_continue_redirects_to_skills(self, monkeypatch):
        app = _make_onboarding_app()
        import routes.onboarding as ob_mod
        monkeypatch.setattr(ob_mod, 'get_db', lambda: _FakeConn())
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 1)
        with app.test_request_context(
            '/onboarding/locales/continue', method='POST'
        ):
            response = ob_mod.locales_continue()
        assert response.status_code == 302
        assert '/onboarding/skills' in response.location


class TestSkillsRoute:
    def test_get_loads_vocab_and_current_state(self, monkeypatch):
        app = _make_onboarding_app()
        conn = _FakeConn()
        # vocab SELECT
        conn.queue_response(rows=[
            {'toggle_name': 'climbing_roped',
             'display_label': 'Roped climbing',
             'description': 'Lead/top-rope.'},
        ])
        # athlete state SELECT
        conn.queue_response(rows=[
            {'toggle_name': 'climbing_roped', 'enabled': True},
        ])
        import routes.onboarding as ob_mod
        captured = {}
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            ob_mod, 'render_template',
            lambda tpl, **kw: captured.update({'tpl': tpl, **kw}) or 'OK',
        )

        with app.test_request_context('/onboarding/skills', method='GET'):
            ob_mod.skills()

        assert captured['tpl'] == 'onboarding/skills.html'
        assert captured['toggle_defs'] == [{
            'toggle_name': 'climbing_roped',
            'display_label': 'Roped climbing',
            'description': 'Lead/top-rope.',
        }]
        assert captured['current_states'] == {'climbing_roped': True}
        assert captured['post_step_skills_target'] == '/onboarding/schedule'
        # 2c.2b — the craft picker shares this step.
        assert [c['slug'] for c in captured['craft_catalog']['cycling']] == [
            'road_bike', 'mountain_bike', 'gravel_bike']  # cycling_trainer dropped (WS-I, #586)
        assert [c['slug'] for c in captured['craft_catalog']['paddling']] == [
            'kayak', 'canoe', 'packraft']
        assert captured['athlete_crafts'] == {'bike_types': [], 'paddle_crafts': []}

    def test_post_upserts_state_and_evicts_layer1(self, monkeypatch):
        app = _make_onboarding_app()
        conn = _FakeConn()
        # vocab SELECT inside skills_save
        conn.queue_response(rows=[
            {'toggle_name': 'climbing_roped',
             'display_label': 'X', 'description': 'X'},
            {'toggle_name': 'swim_open_water',
             'display_label': 'X', 'description': 'X'},
        ])
        import routes.onboarding as ob_mod
        evictions = []
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 42)
        monkeypatch.setattr(
            ob_mod, 'evict_layer1_on_skill_toggle_change',
            lambda db, uid: evictions.append(uid),
        )

        with app.test_request_context(
            '/onboarding/skills',
            method='POST',
            data={'skill__climbing_roped': '1'},
        ):
            response = ob_mod.skills_save()

        # Vocab SELECT + 2 craft upserts (2c.2b) + 2 skill upserts.
        assert len(conn.calls) == 5
        skill_upserts = [(sql, params) for sql, params in conn.calls
                         if 'INSERT INTO athlete_skill_toggles' in sql]
        assert len(skill_upserts) == 2
        # Climbing was checked → True; swim absent → explicit False.
        states_by_toggle = {p[1]: p[2] for _, p in skill_upserts}
        assert states_by_toggle == {
            'climbing_roped': True,
            'swim_open_water': False,
        }
        # No craft checkboxes submitted → both families cleared (empty strings).
        craft_upserts = [(sql, params) for sql, params in conn.calls
                         if 'discipline_baseline_' in sql]
        assert len(craft_upserts) == 2
        assert all(p[1] == '' for _, p in craft_upserts)
        # Commit + Layer 1 eviction fired once.
        assert conn.commits == 1
        assert evictions == [42]
        # Redirect lands on schedule (Step 6).
        assert response.status_code == 302
        assert '/onboarding/schedule' in response.location

    def test_post_empty_vocab_still_persists_crafts_and_redirects(self, monkeypatch):
        # Defensive path: skill vocab not applied → no skill rows. Crafts are a
        # separate closed enum and still persist; the athlete advances.
        app = _make_onboarding_app()
        conn = _FakeConn()
        conn.queue_response(rows=[])  # empty vocab
        import routes.onboarding as ob_mod
        evictions = []
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 42)
        monkeypatch.setattr(
            ob_mod, 'evict_layer1_on_skill_toggle_change',
            lambda db, uid: evictions.append(uid),
        )

        with app.test_request_context('/onboarding/skills', method='POST',
                                      data={'bike_types': 'mountain_bike'}):
            response = ob_mod.skills_save()

        # Vocab SELECT + 2 craft upserts (no skill upsert — empty vocab).
        assert len(conn.calls) == 3
        craft_upserts = [(sql, params) for sql, params in conn.calls
                         if 'discipline_baseline_' in sql]
        assert len(craft_upserts) == 2
        cyc = [p for sql, p in craft_upserts if 'cycling' in sql][0]
        assert cyc == (42, 'mountain_bike')
        assert conn.commits == 1
        assert evictions == [42]
        assert response.status_code == 302
        assert '/onboarding/schedule' in response.location

    def test_post_persists_selected_crafts_in_enum_order(self, monkeypatch):
        app = _make_onboarding_app()
        conn = _FakeConn()
        conn.queue_response(rows=[])  # empty vocab — isolate the craft writes
        import routes.onboarding as ob_mod
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 42)
        monkeypatch.setattr(
            ob_mod, 'evict_layer1_on_skill_toggle_change', lambda db, uid: None)

        with app.test_request_context(
            '/onboarding/skills', method='POST',
            # submitted out of enum order → stored in enum order.
            data={'bike_types': ['gravel_bike', 'road_bike'],
                  'paddle_crafts': ['packraft']},
        ):
            ob_mod.skills_save()

        craft = {('cycling' if 'cycling' in sql else 'paddling'): p
                 for sql, p in conn.calls if 'discipline_baseline_' in sql}
        assert craft['cycling'] == (42, 'road_bike,gravel_bike')
        assert craft['paddling'] == (42, 'packraft')

    def test_post_invalid_craft_bounces_to_skills(self, monkeypatch):
        app = _make_onboarding_app()
        conn = _FakeConn()
        conn.queue_response(rows=[])  # vocab
        import routes.onboarding as ob_mod
        evictions = []
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 42)
        monkeypatch.setattr(
            ob_mod, 'evict_layer1_on_skill_toggle_change',
            lambda db, uid: evictions.append(uid))

        with app.test_request_context('/onboarding/skills', method='POST',
                                      data={'bike_types': 'tandem'}):
            response = ob_mod.skills_save()

        # Validation rejects before any write/commit/eviction.
        assert conn.commits == 0
        assert evictions == []
        assert all('INSERT' not in sql for sql, _ in conn.calls)
        # Bounced back to the skills step, not advanced.
        assert response.status_code == 302
        assert '/onboarding/skills' in response.location
