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
    _edit_legacy_locale,
    _edit_shared_locale,
    _evict_layer2b_on_terrain_change,
    _evict_layer2c_on_equipment_change,
    _hydrate_locale_terrain_ids,
    _parse_locale_terrain,
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
    def test_returns_id_label_dicts_in_select_order(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'terrain_id': 'TRN-001', 'canonical_name': 'Road / Paved'},
            {'terrain_id': 'TRN-002', 'canonical_name': 'Groomed Trail'},
            {'terrain_id': 'TRN-016', 'canonical_name': 'Indoor / Gym'},
        ])

        result = _terrain_choices(conn)

        assert result == [
            {'id': 'TRN-001', 'label': 'Road / Paved'},
            {'id': 'TRN-002', 'label': 'Groomed Trail'},
            {'id': 'TRN-016', 'label': 'Indoor / Gym'},
        ]
        sql, _params = conn.calls[0]
        assert 'layer0.terrain_types' in sql
        assert 'superseded_at IS NULL' in sql
        assert 'ORDER BY terrain_id' in sql

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


class TestDeleteLocaleClearsEquipmentFirst:
    """Bucket B #2 (2026-05-21 walkthrough) — `/locales/<slug>/delete`
    raised `ForeignKeyViolation` because `locale_equipment` has a FK on
    `(user_id, locale)` with no `ON DELETE CASCADE`. Fix clears
    `locale_equipment` before `locale_profiles`.
    """

    def test_locale_equipment_cleared_before_locale_profiles(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        # delete_locale flow: (1) SELECT profile, (2) DELETE locale_equipment,
        # (3) DELETE locale_profiles, (4) optional DELETE gym_profiles.
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

        eq_idx = _sql_indices(conn.calls, 'DELETE FROM locale_equipment')
        lp_idx = _sql_indices(conn.calls, 'DELETE FROM locale_profiles')
        assert eq_idx, 'expected a DELETE FROM locale_equipment call'
        assert lp_idx, 'expected a DELETE FROM locale_profiles call'
        assert eq_idx[0] < lp_idx[0], (
            f'locale_equipment must be cleared before locale_profiles to '
            f'satisfy the FK (got positions {eq_idx[0]} vs {lp_idx[0]})'
        )

    def test_legacy_locale_short_circuits_without_delete(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)

        with app.test_request_context('/locales/home/delete', method='POST'):
            delete_locale('home')

        # Legacy enum slot → redirected to edit, no DELETEs issued.
        assert not _sql_indices(conn.calls, 'DELETE FROM locale_equipment')
        assert not _sql_indices(conn.calls, 'DELETE FROM locale_profiles')


# ─── locale_terrain_ids round-trip (Bucket B #3 2026-05-21) ────────────────


class TestEditLegacyLocaleTerrainPersists:
    """Bucket B #3 — terrain checkboxes did not persist on save. This
    test exercises the legacy-locale POST path with terrain checkboxes
    and asserts the upsert SQL receives the parsed list at param index 4.
    """

    def test_upsert_includes_locale_terrain_ids(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        # First call inside _edit_legacy_locale is the prior-equipment snapshot.
        conn.queue_response(rows=[])
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)

        profile = _FakeRow({'locale_terrain_ids': []})
        with app.test_request_context(
            '/locales/horn_s_house/edit',
            method='POST',
            data={
                'equipment': [],
                'notes': '',
                'city': '',
                'locale_terrain_ids': ['TRN-002', 'TRN-003', 'TRN-016'],
            },
        ):
            _edit_legacy_locale(conn, 1, 'horn_s_house', profile)

        upsert = [
            (sql, params) for sql, params in conn.calls
            if 'INSERT INTO locale_profiles' in sql
            and 'locale_terrain_ids' in sql
        ]
        assert upsert, 'expected an INSERT ... ON CONFLICT for locale_profiles'
        sql, params = upsert[0]
        # Params: (uid, locale, notes, city, new_terrain_ids).
        assert params[0] == 1
        assert params[1] == 'horn_s_house'
        assert params[4] == ['TRN-002', 'TRN-003', 'TRN-016']
        # Defensive `::text[]` cast on the array placeholder forces explicit
        # typing — production rows landed empty without it.
        assert '::text[]' in sql


class TestEditSharedLocaleTerrainPersists:
    """Bucket B #3 — shared-profile path (outdoor_park, gym, etc.) must
    also persist `locale_terrain_ids`. Andy's repro locale
    `chisenhall_mtb_trailhead` is category `outdoor_park` (in
    `SHARED_PROFILE_CATEGORIES`), so it routes through
    `_edit_shared_locale`.
    """

    def test_inherit_path_updates_terrain_ids(self, monkeypatch):
        app = _make_app()
        conn = _FakeConn()
        # _edit_shared_locale call order on inherit path:
        # 1. SELECT gym_profiles WHERE id=? (shared lookup)
        # 2. _load_overrides SELECT (prior overrides snapshot)
        # 3. _save_overrides DELETE (then 0+ INSERTs)
        # 4. UPDATE locale_profiles SET notes, locale_terrain_ids, ...
        conn.queue_response(row={
            'id': 42,
            'equipment': '[]',
            'last_confirmed_at': None,
            'contribution_count': 1,
        })
        conn.queue_response(rows=[])  # _load_overrides
        import routes.locales as locales_mod
        monkeypatch.setattr(locales_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(locales_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(locales_mod, '_evict_layer2b_on_terrain_change',
                            lambda *_a, **_k: None)
        monkeypatch.setattr(locales_mod, '_evict_layer2c_on_equipment_change',
                            lambda *_a, **_k: None)

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
                'equipment': [],
                'notes': '',
                'locale_terrain_ids': ['TRN-002', 'TRN-003'],
            },
        ):
            _edit_shared_locale(conn, 1, 'chisenhall_mtb_trailhead', profile)

        # Find the UPDATE locale_profiles statement carrying terrain ids.
        update = [
            (sql, params) for sql, params in conn.calls
            if 'UPDATE locale_profiles' in sql
            and 'locale_terrain_ids' in sql
        ]
        assert update, 'expected UPDATE locale_profiles SET ... locale_terrain_ids'
        sql, params = update[0]
        # Inherit-path params: (notes, new_terrain_ids, uid, locale).
        assert params[0] == ''
        assert params[1] == ['TRN-002', 'TRN-003']
        assert params[2] == 1
        assert params[3] == 'chisenhall_mtb_trailhead'
        # Defensive `::text[]` cast — see legacy-path test.
        assert '::text[]' in sql
