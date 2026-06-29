"""Tests for the Phase 5.1 form-refresh C additions to `routes/locales.py`.

Coverage:
- `_TRN_PATTERN` — accepts canonical TRN-xxx; rejects anything else.
- `_parse_locale_terrain(form)` — multi-checkbox parser. Happy path,
  empty input, malformed entries dropped, duplicates deduped, output
  sorted for deterministic storage.
- `_terrain_choices(db)` — SELECT shape against `layer0.terrain_types` +
  dict mapping + empty-rows degenerate.
- `_hydrate_locale_terrain_ids(row)` — list / JSON-string / NULL / column-
  missing tolerance mirroring `race_events_repo.get_race_event` adapter
  shape across psycopg2 native TEXT[] vs sqlite shim JSON-string.
- `_evict_layer2b_on_terrain_change(db, uid)` — fires the layer2b policy
  on the injected `Layer4Cache`.

Edit-flow exercise (POST against `/locales/<loc>/edit` with the new
terrain field) is captured in the §5.0 manual walkthrough rather than
pytest — mirrors `tests/test_race_events_repo.py` + `tests/test_onboarding_race_events.py`
precedent (route-level smoke deferred to manual against Andy's PGE 2026 row).
"""

from __future__ import annotations

import pytest

from layer4.cache import (
    PER_ENTRY_PHASE_IDX_SENTINEL,
    InMemoryCacheBackend,
    Layer4Cache,
)
from routes.locales import (
    _TRN_PATTERN,
    _address_fingerprint,
    _category_default_private,
    _create_gym_profile,
    _edit_locale,
    _evict_layer2b_on_terrain_change,
    _evict_layer2c_on_equipment_change,
    _find_gym_profile,
    _find_gym_profile_by_fingerprint,
    _hydrate_locale_terrain_ids,
    _list_pending_profile_edits,
    _parse_locale_terrain,
    _record_profile_edit,
    _resolve_private,
    _resolve_shared_profile,
    _review_profile_edit,
    _terrain_choices,
    delete_locale,
)


# ─── Shared fakes ───────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def keys(self):  # locales.py uses _row_has() which calls .keys()
        return super().keys()


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
        pass

    def rollback(self):
        pass


class _FakeForm:
    """`request.form`-shaped fake — supports `getlist(key)`."""

    def __init__(self, mapping: dict[str, list[str]] | None = None):
        self._mapping = mapping or {}

    def getlist(self, key: str) -> list[str]:
        return list(self._mapping.get(key, []))


# ─── _TRN_PATTERN ────────────────────────────────────────────────────────────


class TestTrnPattern:
    def test_matches_canonical(self):
        assert _TRN_PATTERN.match("TRN-001")
        assert _TRN_PATTERN.match("TRN-016")
        assert _TRN_PATTERN.match("TRN-999")

    def test_rejects_non_canonical(self):
        assert _TRN_PATTERN.match("trail") is None
        assert _TRN_PATTERN.match("TRN-1") is None
        assert _TRN_PATTERN.match("TRN-1000") is None
        assert _TRN_PATTERN.match("trn-001") is None  # case-sensitive
        assert _TRN_PATTERN.match("") is None


# ─── _parse_locale_terrain ──────────────────────────────────────────────────


class TestParseLocaleTerrain:
    def test_happy_multi_select(self):
        form = _FakeForm({
            'locale_terrain_ids': ['TRN-002', 'TRN-003', 'TRN-009'],
        })
        result = _parse_locale_terrain(form)
        # Sorted output for deterministic storage.
        assert result == ['TRN-002', 'TRN-003', 'TRN-009']

    def test_empty_form_returns_empty_list(self):
        form = _FakeForm()
        assert _parse_locale_terrain(form) == []

    def test_empty_locale_terrain_field_returns_empty_list(self):
        form = _FakeForm({'locale_terrain_ids': []})
        assert _parse_locale_terrain(form) == []

    def test_drops_blank_entries(self):
        form = _FakeForm({
            'locale_terrain_ids': ['TRN-002', '', '   ', 'TRN-004'],
        })
        assert _parse_locale_terrain(form) == ['TRN-002', 'TRN-004']

    def test_drops_invalid_trn_patterns(self):
        form = _FakeForm({
            'locale_terrain_ids': [
                'TRN-002',  # valid
                'trail',  # bad
                'trn-005',  # case
                'TRN-12',  # too few digits
                'TRN-12345',  # too many digits
                'TRN-004',  # valid
            ],
        })
        assert _parse_locale_terrain(form) == ['TRN-002', 'TRN-004']

    def test_dedupes_duplicates(self):
        form = _FakeForm({
            'locale_terrain_ids': ['TRN-002', 'TRN-002', 'TRN-004', 'TRN-002'],
        })
        assert _parse_locale_terrain(form) == ['TRN-002', 'TRN-004']

    def test_output_always_sorted(self):
        form = _FakeForm({
            'locale_terrain_ids': ['TRN-009', 'TRN-002', 'TRN-016', 'TRN-003'],
        })
        assert _parse_locale_terrain(form) == [
            'TRN-002', 'TRN-003', 'TRN-009', 'TRN-016',
        ]

    def test_strips_whitespace(self):
        form = _FakeForm({
            'locale_terrain_ids': ['  TRN-002  ', '\tTRN-004\n'],
        })
        assert _parse_locale_terrain(form) == ['TRN-002', 'TRN-004']


# ─── _terrain_choices ───────────────────────────────────────────────────────


class TestTerrainChoices:
    def test_returns_id_label_description_dicts_in_select_order(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'terrain_id': 'TRN-001', 'canonical_name': 'Road / Paved',
             'notes': 'Sealed road surface.'},
            {'terrain_id': 'TRN-002', 'canonical_name': 'Groomed Trail',
             'notes': 'Compacted dirt trail.'},
            {'terrain_id': 'TRN-016', 'canonical_name': 'Indoor / Gym',
             'notes': 'The indoor training environment itself.'},
        ])

        result = _terrain_choices(conn)

        # The locale picker is for training venues, so it is NOT race-
        # eligibility filtered (issue #445) — TRN-016 (Indoor / Gym) stays.
        # `description` carries the row notes for the #444 hover tooltip.
        assert result == [
            {'id': 'TRN-001', 'label': 'Road / Paved',
             'description': 'Sealed road surface.'},
            {'id': 'TRN-002', 'label': 'Groomed Trail',
             'description': 'Compacted dirt trail.'},
            {'id': 'TRN-016', 'label': 'Indoor / Gym',
             'description': 'The indoor training environment itself.'},
        ]
        sql, _params = conn.calls[0]
        assert 'layer0.terrain_types' in sql
        assert 'superseded_at IS NULL' in sql
        assert 'ORDER BY terrain_id' in sql
        assert 'notes' in sql

    def test_empty_rows_returns_empty_list(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert _terrain_choices(conn) == []


# ─── _hydrate_locale_terrain_ids ────────────────────────────────────────────


class TestHydrateLocaleTerrainIds:
    def test_none_row_returns_empty(self):
        assert _hydrate_locale_terrain_ids(None) == []

    def test_column_missing_returns_empty(self):
        # Pre-migration row shape (no `locale_terrain_ids` key).
        row = _FakeRow({'locale': 'home', 'notes': 'x'})
        assert _hydrate_locale_terrain_ids(row) == []

    def test_null_column_returns_empty(self):
        row = _FakeRow({'locale_terrain_ids': None})
        assert _hydrate_locale_terrain_ids(row) == []

    def test_native_list_passes_through(self):
        # psycopg2 native TEXT[] path.
        row = _FakeRow({
            'locale_terrain_ids': ['TRN-002', 'TRN-004', 'TRN-016'],
        })
        assert _hydrate_locale_terrain_ids(row) == [
            'TRN-002', 'TRN-004', 'TRN-016',
        ]

    def test_native_list_drops_invalid_trn(self):
        row = _FakeRow({
            'locale_terrain_ids': ['TRN-002', 'trail', '', 'TRN-004'],
        })
        assert _hydrate_locale_terrain_ids(row) == ['TRN-002', 'TRN-004']

    def test_json_string_path(self):
        # SQLite shim path — JSON-text representation.
        row = _FakeRow({
            'locale_terrain_ids': '["TRN-002", "TRN-009"]',
        })
        assert _hydrate_locale_terrain_ids(row) == ['TRN-002', 'TRN-009']

    def test_empty_array_literal_string_returns_empty(self):
        row = _FakeRow({'locale_terrain_ids': '{}'})
        assert _hydrate_locale_terrain_ids(row) == []
        row = _FakeRow({'locale_terrain_ids': '[]'})
        assert _hydrate_locale_terrain_ids(row) == []

    def test_malformed_json_string_returns_empty(self):
        row = _FakeRow({'locale_terrain_ids': '{not json}'})
        assert _hydrate_locale_terrain_ids(row) == []


# ─── _evict_layer2b_on_terrain_change ───────────────────────────────────────


class TestEvictLayer2bOnTerrainChange:
    """Phase 5.1 form-refresh C D10 — locale-terrain edit fires the
    `evict_on_layer_change(cache, uid, 'layer2b')` primitive so the next
    plan_create / plan_refresh / race_week_brief invocation re-derives
    Layer 2B. Production path builds a transient `Layer4Cache(PostgresCacheBackend)`;
    tests inject a working in-memory cache via monkeypatch.
    """

    _USER_ID = 42

    def test_evicts_layer2b_consumers(self, monkeypatch):
        backend = InMemoryCacheBackend()
        # Seed each layer2b consumer + single_session (which DOESN'T consume 2B).
        for ep in (
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        ):
            backend.put(
                cache_key=f"k-{self._USER_ID}-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=self._USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json='{"seed": true}',
            )

        # Replace Layer4Cache construction with our seeded backend.
        injected_cache = Layer4Cache(backend)
        import routes.locales as locales_mod
        monkeypatch.setattr(
            locales_mod, "Layer4Cache",
            lambda *_args, **_kwargs: injected_cache,
        )
        monkeypatch.setattr(
            locales_mod, "PostgresCacheBackend",
            lambda *_args, **_kwargs: backend,
        )

        _evict_layer2b_on_terrain_change(db=object(), user_id=self._USER_ID)

        remaining = {
            entry.entry_point
            for (_k, _i), entry in backend._rows.items()  # noqa: SLF001
            if entry.user_id == self._USER_ID
        }
        # layer2b policy = _NON_SINGLE_SESSION → single_session preserved.
        assert remaining == {"single_session_synthesize"}


# ─── _evict_layer2c_on_equipment_change ─────────────────────────────────────


class TestEvictLayer2cOnEquipmentChange:
    """Phase 5.2 doc-sweep — locale-equipment edit fires the
    `evict_on_layer_change(cache, uid, 'layer2c')` primitive so the next
    plan_create / plan_refresh / single_session_synthesize / race_week_brief
    invocation re-derives Layer 2C. Mirrors the 2B test substrate but
    expects ALL four entry points to be evicted (layer2c policy is
    `_ALL_ENTRY_POINTS`, broader than 2B's `_NON_SINGLE_SESSION`).
    """

    _USER_ID = 42

    def test_evicts_all_layer2c_consumers(self, monkeypatch):
        backend = InMemoryCacheBackend()
        # Seed every Layer 4 entry point — all four consume Layer 2C.
        for ep in (
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        ):
            backend.put(
                cache_key=f"k-{self._USER_ID}-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=self._USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json='{"seed": true}',
            )

        injected_cache = Layer4Cache(backend)
        import routes.locales as locales_mod
        monkeypatch.setattr(
            locales_mod, "Layer4Cache",
            lambda *_args, **_kwargs: injected_cache,
        )
        monkeypatch.setattr(
            locales_mod, "PostgresCacheBackend",
            lambda *_args, **_kwargs: backend,
        )

        _evict_layer2c_on_equipment_change(db=object(), user_id=self._USER_ID)

        remaining = {
            entry.entry_point
            for (_k, _i), entry in backend._rows.items()  # noqa: SLF001
            if entry.user_id == self._USER_ID
        }
        # layer2c policy = _ALL_ENTRY_POINTS → no entry point survives.
        assert remaining == set()

    def test_does_not_evict_other_users(self, monkeypatch):
        backend = InMemoryCacheBackend()
        other_user = 99
        backend.put(
            cache_key=f"k-{other_user}-plan_create",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=other_user,
            entry_point="plan_create",
            phase_name=None,
            payload_json='{"seed": true}',
        )
        backend.put(
            cache_key=f"k-{self._USER_ID}-plan_create",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=self._USER_ID,
            entry_point="plan_create",
            phase_name=None,
            payload_json='{"seed": true}',
        )

        injected_cache = Layer4Cache(backend)
        import routes.locales as locales_mod
        monkeypatch.setattr(
            locales_mod, "Layer4Cache",
            lambda *_args, **_kwargs: injected_cache,
        )
        monkeypatch.setattr(
            locales_mod, "PostgresCacheBackend",
            lambda *_args, **_kwargs: backend,
        )

        _evict_layer2c_on_equipment_change(db=object(), user_id=self._USER_ID)

        survivors = {
            entry.user_id
            for (_k, _i), entry in backend._rows.items()  # noqa: SLF001
        }
        # Only the other user's row should remain.
        assert survivors == {other_user}


# ─── delete_locale FK ordering (Bucket B #2 2026-05-21) ─────────────────────


def _make_app():
    from flask import Flask
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    from routes.locales import bp
    app.register_blueprint(bp)
    return app


def _sql_indices(calls, fragment: str) -> list[int]:
    """Return positions in `calls` whose SQL contains `fragment`."""
    return [i for i, (sql, _params) in enumerate(calls) if fragment in sql]


class TestDeleteLocale:
    """Track 1 — `locale_equipment` is dropped; delete_locale no longer
    touches it (overrides cascade on the locale_profiles delete). A private,
    athlete-owned gym_profiles row is dropped too — keyed on the explicit
    `private` flag (#446), not re-derived from the locale category."""

    def test_drops_owned_private_gym_profile_by_flag(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        # Opted-private shareable locale with a linked, owned gym_profile.
        conn.queue_response(row={
            'category': 'independent_gym',
            'gym_profile_id': 42,
            'locale_name': "Joe's Place",
        })
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)

        with app.test_request_context('/locales/joe_s_place/delete', method='POST'):
            delete_locale('joe_s_place')

        gym_del = [
            (sql, params) for sql, params in conn.calls
            if 'DELETE FROM gym_profiles' in sql
        ]
        assert gym_del, 'expected the linked gym_profiles row to be deleted'
        sql, params = gym_del[0]
        # The privacy gate is the row's own `private` flag, not the category.
        assert 'private' in sql.lower()
        assert 'created_by_user_id' in sql
        assert params == (42, 1)

    def test_deletes_locale_profiles_not_legacy_table(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        # delete_locale flow: (1) SELECT profile, (2) DELETE locale_profiles,
        # (3) optional DELETE gym_profiles (residential + owned).
        conn.queue_response(row={
            'category': 'other_residence',
            'gym_profile_id': None,
            'locale_name': 'Horn\'s House',
        })
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)

        with app.test_request_context('/locales/horn_s_house/delete', method='POST'):
            delete_locale('horn_s_house')

        # The legacy table is gone — no DELETE against it.
        assert not _sql_indices(conn.calls, 'DELETE FROM locale_equipment ')
        lp_idx = _sql_indices(conn.calls, 'DELETE FROM locale_profiles')
        assert lp_idx, 'expected a DELETE FROM locale_profiles call'

    def test_former_legacy_slug_is_now_deletable(self, monkeypatch):
        # WS-B — the legacy enum is retired, so a locale that happens to use a
        # former-legacy slug ('home') is just an athlete-created row: it is
        # deleted like any other, no short-circuit-to-edit.
        app = _make_app()
        conn = _FakeConn()
        conn.queue_response(row={
            'category': 'home_gym',
            'gym_profile_id': None,
            'locale_name': 'Home',
        })
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)

        with app.test_request_context('/locales/home/delete', method='POST'):
            delete_locale('home')

        assert _sql_indices(conn.calls, 'DELETE FROM locale_profiles'), \
            'former-legacy slug should now delete like any athlete-created locale'


# ─── unified edit path — locale_terrain_ids round-trip ─────────────────────


def _seed_edit_layer0_equipment(conn, names=('Barbell',)):
    """Queue the `_layer0_equipment` SELECT (first query in `_edit_locale`)."""
    conn.queue_response(rows=[
        {'canonical_name': n, 'equipment_category': 'Free Weights'} for n in names
    ])


def _patch_craft_save(monkeypatch, locales_mod, *, prior=None, calls=None):
    """Neutralise the #953 inline craft save in equipment-path tests that don't
    seed its repo queries: `load_craft_locales` returns `prior` (default: none
    kept here), `replace_craft_locale` records `(uid, locale, crafts)` into
    `calls`, and the craft cache eviction is a no-op."""
    monkeypatch.setattr(locales_mod, 'load_craft_locales',
                        lambda *_a, **_k: dict(prior or {}))

    def _replace(_db, uid, locale, crafts):
        if calls is not None:
            calls.append((uid, locale, list(crafts)))
    monkeypatch.setattr(locales_mod, 'replace_craft_locale', _replace)
    monkeypatch.setattr(locales_mod, 'evict_plan_caches_on_craft_locale_change',
                        lambda *_a, **_k: None)


class TestEditLocaleTerrainPersists:
    """Track 1 — the unified `_edit_locale` POST persists `locale_terrain_ids`
    via the INSERT ... ON CONFLICT upsert (param index 4) on the build path
    (no backing gym profile yet)."""

    def test_build_path_upsert_includes_terrain(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        _seed_edit_layer0_equipment(conn)
        # locale_effective_tags: gym_profile_id lookup (None → empty) + overrides.
        conn.queue_response(row={'gym_profile_id': None})
        conn.queue_response(rows=[])
        # _ensure_home: a home already exists → no extra UPDATE.
        conn.queue_response(row={'preferred': 1})
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)
        _patch_craft_save(monkeypatch, locales_mod)

        profile = _FakeRow({'locale_terrain_ids': []})
        with app.test_request_context(
            '/locales/horn_s_house/edit',
            method='POST',
            data={
                'equipment': [],
                'notes': '',
                'locale_terrain_ids': ['TRN-002', 'TRN-003', 'TRN-016'],
            },
        ):
            _edit_locale(conn, 1, 'horn_s_house', profile)

        upsert = [
            (sql, params) for sql, params in conn.calls
            if 'INSERT INTO locale_profiles' in sql
            and 'locale_terrain_ids' in sql
        ]
        assert upsert, 'expected an INSERT ... ON CONFLICT for locale_profiles'
        sql, params = upsert[0]
        # Params: (uid, locale, notes, sharing_opt_out, new_terrain_ids).
        # #941 dropped the free-text `city` column from the upsert.
        assert params[0] == 1
        assert params[1] == 'horn_s_house'
        assert params[4] == ['TRN-002', 'TRN-003', 'TRN-016']
        assert 'city' not in sql
        # Defensive `::text[]` cast on the array placeholder forces explicit
        # typing — production rows landed empty without it.
        assert '::text[]' in sql

    def test_build_path_categoryless_defaults_private_residential(self, monkeypatch):
        """gym_profiles.category is NOT NULL — a categoryless locale (legacy
        enum slug, or a Mapbox/manual locale with no detected category) must
        build a profile with a non-null category, defaulting to private
        residential. Regression: NULL category 500'd /locales/<l>/edit."""
        app = _make_app()
        conn = _FakeConn()
        _seed_edit_layer0_equipment(conn, names=('Barbell',))
        conn.queue_response(row={'gym_profile_id': None})  # locale_effective_tags
        conn.queue_response(rows=[])                        # overrides
        conn.queue_response(row={'preferred': 1})           # _ensure_home
        conn.queue_response(row={'id': 5})                  # _create_gym_profile RETURNING
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)
        _patch_craft_save(monkeypatch, locales_mod)

        # No 'category' key → categoryless (legacy 'home' slug shape).
        profile = _FakeRow({'locale_terrain_ids': []})
        with app.test_request_context(
            '/locales/home/edit', method='POST',
            data={'equipment': ['Barbell'], 'notes': '',
                  'locale_terrain_ids': []},
        ):
            _edit_locale(conn, 1, 'home', profile)

        gym_insert = [
            params for sql, params in conn.calls
            if 'INSERT INTO gym_profiles' in sql
        ]
        assert gym_insert, 'expected a gym_profiles INSERT on the build path'
        # params = (mapbox_id, display, category, equipment_json, uid, uid, private)
        category, private = gym_insert[0][2], gym_insert[0][6]
        assert category == 'home_gym', f'category must be non-null; got {category!r}'
        assert private is True, 'categoryless residential build must be private'

    def test_inherit_path_writes_overrides_and_terrain(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        _seed_edit_layer0_equipment(conn, names=('Barbell', 'Squat rack'))
        # _resolve_shared_profile: gym_profiles lookup → a PEER profile
        # (created_by != uid) → inherit path.
        peer = {'id': 42, 'equipment': '["Barbell"]', 'created_by_user_id': 99,
                'last_confirmed_at': None, 'contribution_count': 1}
        conn.queue_response(row=peer)
        # locale_effective_tags: gym_profile_id (42) + gym_profiles.equipment + overrides.
        conn.queue_response(row={'gym_profile_id': 42})
        conn.queue_response(row={'equipment': '["Barbell"]'})
        conn.queue_response(rows=[])
        # _ensure_home: home exists.
        conn.queue_response(row={'preferred': 1})
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)
        _patch_craft_save(monkeypatch, locales_mod)

        profile = _FakeRow({
            'mapbox_id': 'mb_chisenhall',
            'gym_profile_id': 42,
            'category': 'outdoor_park',
            'manual_entry': False,
            'locale_name': 'Chisenhall MTB Trailhead',
            'locale_terrain_ids': [],
            'notes': '',
        })
        with app.test_request_context(
            '/locales/chisenhall_mtb_trailhead/edit',
            method='POST',
            data={
                'equipment': ['Squat rack'],
                'notes': '',
                'locale_terrain_ids': ['TRN-002', 'TRN-003'],
            },
        ):
            _edit_locale(conn, 1, 'chisenhall_mtb_trailhead', profile)

        # Terrain lands in the upsert.
        upsert = [
            (sql, params) for sql, params in conn.calls
            if 'INSERT INTO locale_profiles' in sql
            and 'locale_terrain_ids' in sql
        ]
        assert upsert, 'expected INSERT ... ON CONFLICT for locale_profiles'
        # Params: (uid, locale, notes, sharing_opt_out, new_terrain_ids).
        # #941 dropped the free-text `city` column from the upsert.
        assert upsert[0][1][4] == ['TRN-002', 'TRN-003']
        # Inherit path writes per-athlete override deltas (canonical names),
        # not a direct gym_profiles equipment edit.
        assert _sql_indices(conn.calls, 'DELETE FROM locale_equipment_overrides')
        ovr_inserts = [
            params for sql, params in conn.calls
            if 'INSERT INTO locale_equipment_overrides' in sql
        ]
        # Submitted {'Squat rack'} on a shared base of {'Barbell'} → add 'Squat rack'.
        assert any('Squat rack' in p and 'add' in p for p in ovr_inserts)


# ─── #953 — craft kept here folded into the single location save ────────────


class TestEditLocaleSavesCraftInline:
    """#953 — the unified editor save persists "craft kept here" in the same
    POST as equipment/terrain (folded off its standalone form/button so editing
    both no longer bounces back to the list), and evicts the craft plan caches
    only when the kept set actually changes."""

    def _post(self, monkeypatch, *, craft_slugs, prior_crafts):
        app = _make_app()
        conn = _FakeConn()
        _seed_edit_layer0_equipment(conn)
        conn.queue_response(row={'gym_profile_id': None})  # locale_effective_tags
        conn.queue_response(rows=[])                        # overrides
        conn.queue_response(row={'preferred': 1})           # _ensure_home
        conn.queue_response(row={'id': 7})                  # _create_gym_profile RETURNING
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)
        craft_calls: list = []
        _patch_craft_save(monkeypatch, locales_mod,
                          prior={'cabin': prior_crafts}, calls=craft_calls)
        evicted: list = []
        monkeypatch.setattr(locales_mod, 'evict_plan_caches_on_craft_locale_change',
                            lambda *_a, **_k: evicted.append(True))

        profile = _FakeRow({'locale_terrain_ids': []})
        with app.test_request_context(
            '/locales/cabin/edit', method='POST',
            data={'equipment': ['Barbell'], 'notes': '', 'city': '',
                  'locale_terrain_ids': [], 'craft_slug': craft_slugs},
        ):
            _edit_locale(conn, 1, 'cabin', profile)
        return craft_calls, evicted

    def test_post_replaces_craft_and_evicts_on_change(self, monkeypatch):
        craft_calls, evicted = self._post(
            monkeypatch, craft_slugs=['kayak', 'mountain_bike'], prior_crafts=[])
        # The submitted craft set is replace-all'd in the same POST...
        assert craft_calls == [(1, 'cabin', ['kayak', 'mountain_bike'])]
        # ...and the craft plan caches evict because the kept set changed.
        assert evicted, 'craft cache must evict when the kept set changes'

    def test_post_skips_craft_eviction_when_unchanged(self, monkeypatch):
        craft_calls, evicted = self._post(
            monkeypatch, craft_slugs=['kayak'], prior_crafts=['kayak'])
        # Still replace-all'd (idempotent), but no cache churn on a no-op change.
        assert craft_calls == [(1, 'cabin', ['kayak'])]
        assert not evicted, 'unchanged craft set must not evict the plan caches'


# ─── #446 — explicit privacy override (private/shared) ──────────────────────


class TestResolvePrivate:
    """`_resolve_private` / `_category_default_private` — privacy is
    category-derived by default but an explicit `sharing_opt_out` can only
    *tighten* a shareable-category locale to private; residences stay private
    regardless of the flag (residences are never crowd-shareable)."""

    def test_residential_categories_default_private(self):
        assert _category_default_private('home_gym') is True
        assert _category_default_private('other_residence') is True

    def test_categoryless_defaults_private(self):
        # gym_profiles defaults a category-less locale to home_gym, so the
        # privacy default must match (private).
        assert _category_default_private(None) is True
        assert _category_default_private('') is True

    def test_shareable_categories_default_shared(self):
        assert _category_default_private('commercial_chain_gym') is False
        assert _category_default_private('independent_gym') is False
        assert _category_default_private('outdoor_park') is False

    def test_opt_out_forces_shareable_private(self):
        assert _resolve_private('independent_gym', False) is False
        assert _resolve_private('independent_gym', True) is True

    def test_opt_out_cannot_loosen_a_residence(self):
        # The opt-out only tightens; a residence can never be made shareable.
        assert _resolve_private('home_gym', False) is True
        assert _resolve_private('home_gym', True) is True


class TestFindGymProfileExcludesPrivate:
    """Crowd-source discovery reads the explicit `private` flag (#446): a
    private peer profile is never surfaced for inheritance."""

    def test_query_filters_private(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        _find_gym_profile(conn, 'mbx.123')
        assert conn.calls, 'expected a SELECT on gym_profiles'
        sql, params = conn.calls[0]
        assert 'FROM gym_profiles' in sql
        assert 'private' in sql.lower()
        assert params == ('mbx.123',)

    def test_no_mapbox_id_short_circuits(self):
        conn = _FakeConn()
        assert _find_gym_profile(conn, None) is None
        assert conn.calls == []


class TestEditPrivacyOverride:
    """`_edit_locale` POST persists the explicit opt-out: it lands in the
    locale_profiles upsert (`sharing_opt_out`) and drives `gym_profiles.private`
    on the build path."""

    def _common_monkeypatch(self, monkeypatch, conn):
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)
        _patch_craft_save(monkeypatch, locales_mod)

    def test_opt_out_forces_shareable_build_private(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        _seed_edit_layer0_equipment(conn, names=('Barbell',))
        conn.queue_response(row={'gym_profile_id': None})  # locale_effective_tags
        conn.queue_response(rows=[])                        # overrides
        conn.queue_response(row={'preferred': 1})           # _ensure_home
        conn.queue_response(row={'id': 7})                  # _create_gym_profile RETURNING
        self._common_monkeypatch(monkeypatch, conn)

        # Shareable category (independent_gym) + explicit opt-out.
        profile = _FakeRow({'category': 'independent_gym', 'locale_terrain_ids': []})
        with app.test_request_context(
            '/locales/joe_s_garage/edit', method='POST',
            data={'equipment': ['Barbell'], 'notes': '',
                  'private': '1', 'locale_terrain_ids': []},
        ):
            _edit_locale(conn, 1, 'joe_s_garage', profile)

        # sharing_opt_out lands TRUE in the locale_profiles upsert (index 3 after
        # #941 dropped the free-text `city` column).
        upsert = [
            params for sql, params in conn.calls
            if 'INSERT INTO locale_profiles' in sql and 'sharing_opt_out' in sql
        ]
        assert upsert, 'expected locale_profiles upsert with sharing_opt_out'
        assert upsert[0][3] is True

        # The built gym_profiles row is private despite the shareable category.
        gym_insert = [
            params for sql, params in conn.calls
            if 'INSERT INTO gym_profiles' in sql
        ]
        assert gym_insert, 'expected a gym_profiles INSERT on the build path'
        # params = (mapbox_id, display, category, equipment_json, uid, uid, private)
        assert gym_insert[0][2] == 'independent_gym'
        assert gym_insert[0][6] is True

    def test_no_opt_out_keeps_shareable_build_shared(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        _seed_edit_layer0_equipment(conn, names=('Barbell',))
        conn.queue_response(row={'gym_profile_id': None})
        conn.queue_response(rows=[])
        conn.queue_response(row={'preferred': 1})
        conn.queue_response(row={'id': 8})
        self._common_monkeypatch(monkeypatch, conn)

        profile = _FakeRow({'category': 'independent_gym', 'locale_terrain_ids': []})
        with app.test_request_context(
            '/locales/joe_s_gym/edit', method='POST',
            data={'equipment': ['Barbell'], 'notes': '',
                  'locale_terrain_ids': []},
        ):
            _edit_locale(conn, 1, 'joe_s_gym', profile)

        upsert = [
            params for sql, params in conn.calls
            if 'INSERT INTO locale_profiles' in sql and 'sharing_opt_out' in sql
        ]
        assert upsert[0][3] is False
        gym_insert = [
            params for sql, params in conn.calls
            if 'INSERT INTO gym_profiles' in sql
        ]
        assert gym_insert[0][6] is False


# ─── #971 — name+geo crowd-source dedup ─────────────────────────────────────


class TestAddressFingerprint:
    """`_address_fingerprint(name, lat, lng)` — the name+geo dedup key. Same
    hotel under minor coordinate drift → one bucket; same-name venues far apart
    → distinct buckets; missing name/coords → None (mapbox_id-only matchable)."""

    def test_normalizes_name_and_buckets_geo(self):
        assert _address_fingerprint('Hilton Downtown', 30.2711, -97.7437) == (
            'hilton downtown|30.271|-97.744'
        )

    def test_punctuation_and_case_collapse_to_same_key(self):
        a = _address_fingerprint('Courtyard by Marriott®', 40.0001, -70.0001)
        b = _address_fingerprint('  courtyard  by   marriott ', 40.0001, -70.0001)
        assert a == b == 'courtyard by marriott|40.000|-70.000'

    def test_same_hotel_minor_coord_drift_same_bucket(self):
        # Two Mapbox lookups for the same hotel whose coords drift within the
        # ~111 m grid resolve to one bucket — the dedup the issue is about.
        a = _address_fingerprint('Marriott', 30.2711, -97.7437)
        b = _address_fingerprint('Marriott', 30.2714, -97.7442)
        assert a == b

    def test_same_chain_far_apart_differs(self):
        austin = _address_fingerprint('Marriott', 30.27, -97.74)
        dallas = _address_fingerprint('Marriott', 32.78, -96.80)
        assert austin != dallas

    def test_missing_name_or_coords_returns_none(self):
        assert _address_fingerprint('', 30.0, -97.0) is None
        assert _address_fingerprint('Hilton', None, -97.0) is None
        assert _address_fingerprint('Hilton', 30.0, None) is None
        # A name that normalizes to empty (pure punctuation) is unmatchable.
        assert _address_fingerprint('!!!', 30.0, -97.0) is None

    def test_non_numeric_coords_returns_none(self):
        assert _address_fingerprint('Hilton', 'x', 'y') is None


class TestFindGymProfileByFingerprint:
    """`_find_gym_profile_by_fingerprint` — the mapbox-miss fallback. Excludes
    private profiles (mirrors `_find_gym_profile`) and short-circuits on None."""

    def test_query_excludes_private_and_passes_fingerprint(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        _find_gym_profile_by_fingerprint(conn, 'hilton|30.271|-97.744')
        assert conn.calls, 'expected a SELECT on gym_profiles'
        sql, params = conn.calls[0]
        assert 'FROM gym_profiles' in sql
        assert 'address_fingerprint' in sql
        assert 'private' in sql.lower()
        assert params == ('hilton|30.271|-97.744',)

    def test_none_fingerprint_short_circuits(self):
        conn = _FakeConn()
        assert _find_gym_profile_by_fingerprint(conn, None) is None
        assert conn.calls == []


class TestCreateGymProfileStampsFingerprint:
    """`_create_gym_profile` writes the name+geo dedup key, appended LAST so the
    positional params the privacy tests assert (private at index 6) don't
    shift."""

    def test_insert_includes_fingerprint_as_last_param(self):
        conn = _FakeConn()
        conn.queue_response(row={'id': 5})  # RETURNING id
        profile = _FakeRow({
            'locale_name': 'Hilton Downtown', 'category': 'hotel_gym',
            'mapbox_id': 'mb.1', 'lat': 30.2711, 'lng': -97.7437,
        })
        new_id = _create_gym_profile(conn, 1, profile, {'Barbell'}, {'Barbell'})
        assert new_id == 5
        inserts = [
            (sql, params) for sql, params in conn.calls
            if 'INSERT INTO gym_profiles' in sql
        ]
        assert inserts, 'expected a gym_profiles INSERT'
        sql, params = inserts[0]
        assert 'address_fingerprint' in sql
        # Pre-existing positional contract is intact...
        assert params[1] == 'Hilton Downtown'   # display_name
        assert params[2] == 'hotel_gym'         # category
        assert params[6] is False               # private (shareable category)
        # ...and the fingerprint rides at the end.
        assert params[-1] == 'hilton downtown|30.271|-97.744'

    def test_missing_coords_stamps_null_fingerprint(self):
        conn = _FakeConn()
        conn.queue_response(row={'id': 6})
        # Categoryless, coordinate-less locale (legacy shape) → NULL fingerprint.
        profile = _FakeRow({'locale_name': 'Home'})
        _create_gym_profile(conn, 1, profile, set(), set())
        params = next(
            params for sql, params in conn.calls
            if 'INSERT INTO gym_profiles' in sql
        )
        assert params[-1] is None


class TestResolveSharedProfileFingerprintFallback:
    """`_resolve_shared_profile` falls back to the name+geo key only when the
    mapbox_id lookup misses, and leaves it untouched when mapbox_id hits."""

    def test_falls_back_to_fingerprint_when_mapbox_misses(self):
        conn = _FakeConn()
        conn.queue_response(row=None)  # _find_gym_profile(mapbox) → miss
        peer = {'id': 77, 'created_by_user_id': 99, 'equipment': '["Barbell"]'}
        conn.queue_response(row=peer)  # _find_gym_profile_by_fingerprint → hit
        profile = _FakeRow({
            'mapbox_id': 'mb.new', 'gym_profile_id': None,
            'locale_name': 'Hilton Downtown', 'lat': 30.2711, 'lng': -97.7437,
        })
        shared, gid = _resolve_shared_profile(conn, 1, profile)
        assert gid is None
        assert shared is not None and shared['id'] == 77
        # The second query is the fingerprint lookup carrying the computed key.
        fp_calls = [
            (sql, params) for sql, params in conn.calls
            if 'address_fingerprint' in sql
        ]
        assert fp_calls
        assert fp_calls[0][1] == ('hilton downtown|30.271|-97.744',)

    def test_no_fallback_when_mapbox_hits(self):
        conn = _FakeConn()
        conn.queue_response(row={'id': 5, 'created_by_user_id': 99})  # mapbox hit
        profile = _FakeRow({
            'mapbox_id': 'mb.x', 'gym_profile_id': None,
            'locale_name': 'Hilton', 'lat': 30.0, 'lng': -97.0,
        })
        shared, gid = _resolve_shared_profile(conn, 1, profile)
        assert shared['id'] == 5
        # No fingerprint query — the exact mapbox_id match wins.
        assert not any('address_fingerprint' in sql for sql, _ in conn.calls)


# ─── #971 Slice 3 — peer-proposed corrections + admin review ─────────────────


import json as _json  # noqa: E402 — local alias for asserting JSON payloads


def _last_disputed_write(conn):
    """The JSON written to disputed_items by the most recent UPDATE, parsed."""
    writes = [
        params for sql, params in conn.calls
        if 'UPDATE gym_profiles' in sql and 'disputed_items' in sql
    ]
    assert writes, 'expected a disputed_items UPDATE'
    payload = writes[-1][0]  # disputed_items is the first param in these writes
    return None if payload is None else _json.loads(payload)


class TestRecordProfileEdit:
    """`_record_profile_edit` stashes a peer's shared-vs-submitted delta as a
    correction proposal on `gym_profiles.disputed_items`."""

    def test_records_delta_as_proposal(self):
        conn = _FakeConn()
        conn.queue_response(row={'disputed_items': None})  # _load_profile_edits
        _record_profile_edit(
            conn, 77, 42, {'Barbell', 'Squat rack'}, {'Barbell', 'Treadmill'},
            {'Barbell', 'Squat rack', 'Treadmill'}, now='2026-06-29T12:00:00+00:00')
        proposals = _last_disputed_write(conn)
        assert proposals == [{
            'by': 42, 'adds': ['Treadmill'], 'removes': ['Squat rack'],
            'at': '2026-06-29T12:00:00+00:00',
        }]

    def test_empty_delta_withdraws_proposal(self):
        conn = _FakeConn()
        # An existing proposal by this peer is on file...
        conn.queue_response(row={'disputed_items': _json.dumps(
            [{'by': 42, 'adds': ['Treadmill'], 'removes': [], 'at': 't'}])})
        # ...but the peer's view now matches the shared base → withdraw it.
        _record_profile_edit(conn, 77, 42, {'Barbell'}, {'Barbell'}, {'Barbell'})
        assert _last_disputed_write(conn) is None  # nothing pending → NULL

    def test_upsert_replaces_same_peer_keeps_others(self):
        conn = _FakeConn()
        conn.queue_response(row={'disputed_items': _json.dumps([
            {'by': 42, 'adds': ['Old'], 'removes': [], 'at': 't0'},
            {'by': 99, 'adds': ['Kept'], 'removes': [], 'at': 't1'},
        ])})
        _record_profile_edit(
            conn, 77, 42, {'Barbell'}, {'Barbell', 'Dumbbells'},
            {'Barbell', 'Dumbbells'}, now='t2')
        proposals = _last_disputed_write(conn)
        assert {p['by'] for p in proposals} == {42, 99}
        p42 = next(p for p in proposals if p['by'] == 42)
        assert p42['adds'] == ['Dumbbells']  # replaced, not appended
        assert next(p for p in proposals if p['by'] == 99)['adds'] == ['Kept']

    def test_invalid_names_dropped_from_proposal(self):
        conn = _FakeConn()
        conn.queue_response(row={'disputed_items': None})
        _record_profile_edit(
            conn, 77, 42, set(), {'Barbell', 'Bogus'}, {'Barbell'}, now='t')
        proposals = _last_disputed_write(conn)
        assert proposals[0]['adds'] == ['Barbell']  # 'Bogus' rejected


class TestListPendingProfileEdits:
    """`_list_pending_profile_edits` surfaces shared profiles carrying proposals,
    excluding private rows, with shared equipment + proposals parsed."""

    def test_lists_and_parses(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 77, 'display_name': 'Hilton', 'category': 'hotel_gym',
            'equipment': '["Barbell", "Squat rack"]',
            'disputed_items': _json.dumps(
                [{'by': 42, 'adds': ['Treadmill'], 'removes': [], 'at': 't'}]),
        }])
        out = _list_pending_profile_edits(conn)
        sql = conn.calls[0][0]
        assert 'COALESCE(private, FALSE) = FALSE' in sql
        assert out[0]['shared_tags'] == ['Barbell', 'Squat rack']
        assert out[0]['proposals'][0]['by'] == 42

    def test_skips_rows_without_parseable_proposals(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'id': 1, 'display_name': 'A', 'category': 'gym',
             'equipment': '[]', 'disputed_items': '[]'},      # empty list
            {'id': 2, 'display_name': 'B', 'category': 'gym',
             'equipment': '[]', 'disputed_items': 'not json'},  # malformed
        ])
        assert _list_pending_profile_edits(conn) == []


class TestReviewProfileEdit:
    """`_review_profile_edit` approves (folds into shared equipment) or rejects
    (leaves it) one peer's proposal and clears it from the queue."""

    def test_approve_folds_into_shared_equipment(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'equipment': '["Barbell", "Squat rack"]',
            'disputed_items': _json.dumps(
                [{'by': 42, 'adds': ['Treadmill'], 'removes': ['Squat rack'],
                  'at': 't'}]),
        })
        applied = _review_profile_edit(conn, 77, 42, approve=True)
        assert applied['by'] == 42
        update = next(
            params for sql, params in conn.calls
            if 'UPDATE gym_profiles' in sql and 'equipment' in sql)
        # New shared set = (Barbell, Squat rack ∪ Treadmill) − Squat rack.
        assert _json.loads(update[0]) == ['Barbell', 'Treadmill']
        assert update[1] is None          # disputed_items cleared (none remain)
        assert update[2] == 42            # last_confirmed_by = proposer

    def test_reject_leaves_equipment_untouched(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'equipment': '["Barbell"]',
            'disputed_items': _json.dumps(
                [{'by': 42, 'adds': ['Treadmill'], 'removes': [], 'at': 't'}]),
        })
        applied = _review_profile_edit(conn, 77, 42, approve=False)
        assert applied['by'] == 42
        assert not any(
            'equipment' in sql for sql, _ in conn.calls
            if 'UPDATE gym_profiles' in sql)  # no equipment write on reject

    def test_unknown_proposal_returns_none(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'equipment': '["Barbell"]',
            'disputed_items': _json.dumps(
                [{'by': 99, 'adds': ['X'], 'removes': [], 'at': 't'}]),
        })
        assert _review_profile_edit(conn, 77, 42, approve=True) is None

    def test_missing_profile_returns_none(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        assert _review_profile_edit(conn, 77, 42, approve=True) is None
