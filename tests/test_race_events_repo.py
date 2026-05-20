"""Tests for `race_events_repo.py` data-access helpers (D-66 §3 + §10).

Coverage:
- `list_athlete_race_events` — SELECT shape + ORDER BY + dict return shape
- `load_race_event_payload` — three-table assembly + ORDER BY sequence_idx +
  equipment bucketing by parent route_locale + None on missing race_event_id
  + empty route_locales case (single-day events with no athlete-saved route)
- `load_target_race_event_payload` — convenience target-row read; None when
  no target set; delegates to `load_race_event_payload` on hit
- `create_race_event` — INSERT params + RETURNING id; race_format validation
- `set_target_event` — atomic flip (UNSET old + SET new in two statements)
- `delete_race_event` — DELETE issued
- `add_route_locale` + `add_route_locale_equipment` — INSERT shape + validation

All tests use the `_FakeConn` / `_FakeCursor` pattern from
`tests/test_layer4_cache.py` — no real DB connection.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from layer4.context import RaceEventPayload, RaceTerrainEntry, RouteLocale
from race_events_repo import (
    VALID_RACE_FORMATS,
    VALID_ROUTE_LOCALE_ROLES,
    add_route_locale,
    add_route_locale_equipment,
    create_race_event,
    delete_race_event,
    delete_route_locale,
    delete_route_locale_equipment,
    get_race_event,
    list_athlete_race_events,
    list_route_locale_equipment,
    list_route_locales,
    load_race_event_payload,
    load_target_race_event_payload,
    set_target_event,
    update_race_event,
    update_route_locale,
)


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
    """Stand-in for `database._PgConn`. Each call to `execute()` returns a
    `_FakeCursor` seeded from `.responses` (a queue of (row, rows) tuples in
    the order the helper invokes execute). Commits are counted.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.responses: list[tuple] = []  # each entry: (row, rows)

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


# ─── list_athlete_race_events ────────────────────────────────────────────────


class TestListAthleteRaceEvents:
    def test_empty_list_when_no_rows(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        result = list_athlete_race_events(conn, user_id=1)
        assert result == []
        assert len(conn.calls) == 1
        assert "FROM race_events" in conn.calls[0][0]
        assert conn.calls[0][1] == (1,)

    def test_returns_dicts_for_multiple_rows(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {
                "id": 1,
                "name": "Pocket Gopher Extreme 2026",
                "event_date": date(2026, 7, 17),
                "race_format": "expedition_ar",
                "is_target_event": True,
                "distance_km": Decimal("160"),
                "total_elevation_gain_m": Decimal("3000"),
                "event_locale_id": 5,
                "created_at": None,
                "updated_at": None,
            },
            {
                "id": 2,
                "name": "Local 5K",
                "event_date": date(2026, 9, 1),
                "race_format": "single_day",
                "is_target_event": False,
                "distance_km": Decimal("5"),
                "total_elevation_gain_m": None,
                "event_locale_id": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        result = list_athlete_race_events(conn, user_id=1)
        assert len(result) == 2
        assert result[0]["name"] == "Pocket Gopher Extreme 2026"
        assert result[0]["is_target_event"] is True
        assert result[1]["race_format"] == "single_day"

    def test_order_by_event_date_ascending(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        list_athlete_race_events(conn, user_id=1)
        assert "ORDER BY event_date ASC" in conn.calls[0][0]


# ─── load_race_event_payload ─────────────────────────────────────────────────


def _race_row(**overrides):
    # D-72 resolved 2026-05-19 — `load_race_event_payload` JOINs locale_profiles
    # and surfaces the slug under `event_locale_slug`. The DB column itself is
    # still BIGINT FK; tests for write-path helpers (create + update + listing)
    # still seed `event_locale_id: int`.
    base = {
        "id": 10,
        "user_id": 1,
        "name": "Pocket Gopher Extreme 2026",
        "event_date": date(2026, 7, 17),
        "race_format": "expedition_ar",
        "distance_km": Decimal("160"),
        "total_elevation_gain_m": Decimal("3000"),
        "race_rules_summary": "Mandatory checkpoints; 56h cutoff.",
        "mandatory_gear_text": "Headlamp; bivvy; 6L water cap.",
        "event_locale_slug": "nerstrand_finish",
        "is_target_event": True,
        "notes": "Crew at TA2.",
        # Phase 5.1 form-refresh A — JSONB list surfaces as list or str
        # depending on adapter; tests seed list (the psycopg2 default).
        "race_terrain": [],
        "aid_stations": None,
    }
    base.update(overrides)
    return base


class TestLoadRaceEventPayload:
    def test_returns_none_when_race_event_not_found(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        result = load_race_event_payload(conn, race_event_id=999)
        assert result is None
        assert len(conn.calls) == 1  # only the initial SELECT race_events

    def test_loads_payload_with_empty_route_locales(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        conn.queue_response(rows=[])  # empty route_locales
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert isinstance(payload, RaceEventPayload)
        assert payload.race_event_id == 10
        assert payload.user_id == 1
        assert payload.name == "Pocket Gopher Extreme 2026"
        assert payload.race_format == "expedition_ar"
        assert payload.event_locale_id == "nerstrand_finish"
        assert payload.is_target_event is True
        assert payload.route_locales == []
        # 2 SELECTs (race_events + race_route_locales); no equipment SELECT
        # since route_locales was empty.
        assert len(conn.calls) == 2

    def test_loads_payload_with_route_locales_and_equipment(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        conn.queue_response(rows=[
            {
                "id": 100,
                "role": "start",
                "sequence_idx": 1,
                "name": "Trailhead",
                "mile_marker": Decimal("0"),
                "lat": Decimal("44.345"),
                "lng": Decimal("-93.106"),
                "mapbox_id": None,
                "notes": "Pre-race brief at 5am.",
            },
            {
                "id": 101,
                "role": "aid_station",
                "sequence_idx": 2,
                "name": "AS1 — Lake Mary",
                "mile_marker": Decimal("12.5"),
                "lat": None,
                "lng": None,
                "mapbox_id": None,
                "notes": None,
            },
            {
                "id": 102,
                "role": "finish",
                "sequence_idx": 3,
                "name": "Finish Line",
                "mile_marker": Decimal("100"),
                "lat": None,
                "lng": None,
                "mapbox_id": None,
                "notes": None,
            },
        ])
        # Equipment SELECT (one batch covering all 3 route_locales).
        conn.queue_response(rows=[
            {
                "race_route_locale_id": 101,
                "equipment_name": "6L water cache",
                "quantity_text": "6 liters",
                "notes": "Shared with team",
            },
            {
                "race_route_locale_id": 101,
                "equipment_name": "Dry socks",
                "quantity_text": "2 pair",
                "notes": None,
            },
        ])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert len(payload.route_locales) == 3
        assert payload.route_locales[0].role == "start"
        assert payload.route_locales[-1].role == "finish"
        # Equipment correctly bucketed under the right route_locale.
        as1 = payload.route_locales[1]
        assert as1.name == "AS1 — Lake Mary"
        assert len(as1.equipment) == 2
        assert as1.equipment[0].equipment_name == "6L water cache"
        # Start + finish have no equipment.
        assert payload.route_locales[0].equipment == []
        assert payload.route_locales[2].equipment == []
        assert len(conn.calls) == 3  # race_events + route_locales + equipment

    def test_route_locales_query_orders_by_sequence_idx(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        conn.queue_response(rows=[])
        load_race_event_payload(conn, race_event_id=10)
        assert "ORDER BY sequence_idx ASC" in conn.calls[1][0]

    def test_race_events_select_joins_locale_profiles_for_slug(self):
        # D-72 resolved 2026-05-19 — the typed-payload load helper LEFT JOINs
        # locale_profiles on the surrogate id to surface the locale slug so
        # RaceEventPayload.event_locale_id stays str-shaped (slug) across the
        # Layer 4 pipeline. The DB column event_locale_id remains BIGINT FK.
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        conn.queue_response(rows=[])
        load_race_event_payload(conn, race_event_id=10)
        sql = conn.calls[0][0]
        assert "LEFT JOIN locale_profiles" in sql
        assert "lp.locale AS event_locale_slug" in sql

    def test_payload_event_locale_id_is_none_when_fk_unresolved(self):
        # ON DELETE SET NULL behavior on locale_profiles row deletion +
        # races with no event_locale_id set both surface as None after
        # the LEFT JOIN.
        conn = _FakeConn()
        conn.queue_response(row=_race_row(event_locale_slug=None))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.event_locale_id is None


# ─── load_target_race_event_payload ──────────────────────────────────────────


class TestLoadTargetRaceEventPayload:
    def test_none_when_no_target_set(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        result = load_target_race_event_payload(conn, user_id=1)
        assert result is None
        assert len(conn.calls) == 1

    def test_delegates_to_load_race_event_payload_on_hit(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 10})  # target lookup
        conn.queue_response(row=_race_row())  # race_events SELECT
        conn.queue_response(rows=[])  # route_locales SELECT (empty)
        result = load_target_race_event_payload(conn, user_id=1)
        assert result is not None
        assert result.race_event_id == 10
        # SQL: target lookup + race_events + route_locales = 3 calls.
        assert len(conn.calls) == 3
        assert "is_target_event = TRUE" in conn.calls[0][0]


# ─── create_race_event ───────────────────────────────────────────────────────


class TestCreateRaceEvent:
    def test_inserts_returning_id(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 42})
        new_id = create_race_event(
            conn,
            user_id=1,
            name="Local 5K",
            event_date=date(2026, 9, 1),
            race_format="single_day",
        )
        assert new_id == 42
        assert conn.commits == 1
        # INSERT issued with correct values.
        assert "INSERT INTO race_events" in conn.calls[0][0]
        assert "RETURNING id" in conn.calls[0][0]
        params = conn.calls[0][1]
        assert params[0] == 1  # user_id
        assert params[1] == "Local 5K"
        assert params[3] == "single_day"

    def test_rejects_invalid_race_format(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="race_format must be one of"):
            create_race_event(
                conn,
                user_id=1,
                name="Bogus",
                event_date=date(2026, 1, 1),
                race_format="marathon",  # not in the closed enum
            )
        # No SQL issued on validation failure.
        assert len(conn.calls) == 0

    def test_passes_optional_fields_through(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 7})
        create_race_event(
            conn,
            user_id=1,
            name="Pocket Gopher Extreme 2026",
            event_date=date(2026, 7, 17),
            race_format="expedition_ar",
            distance_km=Decimal("160"),
            total_elevation_gain_m=Decimal("3000"),
            race_rules_summary="rules text",
            mandatory_gear_text="gear text",
            event_locale_id=5,
            is_target_event=True,
            notes="crew notes",
        )
        params = conn.calls[0][1]
        assert params[4] == Decimal("160")  # distance_km
        assert params[5] == Decimal("3000")  # total_elevation_gain_m
        assert params[6] == "rules text"
        assert params[7] == "gear text"
        assert params[8] == 5  # event_locale_id
        assert params[9] is True  # is_target_event
        assert params[10] == "crew notes"

    def test_serializes_etl_version_set_as_json(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 1})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 1, 1),
            race_format="single_day",
            etl_version_set={"race_events_v1": "manual_create_2026-05-18"},
        )
        # etl_version_set is the last positional param; serialized to JSON
        # for the ?::jsonb cast in the SQL.
        last_param = conn.calls[0][1][-1]
        assert isinstance(last_param, str)
        assert "race_events_v1" in last_param


# ─── set_target_event ────────────────────────────────────────────────────────


class TestSetTargetEvent:
    def test_unsets_old_then_sets_new(self):
        conn = _FakeConn()
        set_target_event(conn, user_id=1, race_event_id=10)
        assert len(conn.calls) == 2
        # First call: UNSET old target rows (skipping our own row).
        unset_sql, unset_params = conn.calls[0]
        assert "is_target_event = FALSE" in unset_sql
        assert "is_target_event = TRUE" in unset_sql
        assert "id <> ?" in unset_sql
        assert unset_params == (1, 10)
        # Second call: SET our row to TRUE.
        set_sql, set_params = conn.calls[1]
        assert "is_target_event = TRUE" in set_sql
        assert set_params == (10, 1)
        assert conn.commits == 1


# ─── delete_race_event ───────────────────────────────────────────────────────


class TestDeleteRaceEvent:
    def test_deletes_with_user_id_scope(self):
        conn = _FakeConn()
        delete_race_event(conn, user_id=1, race_event_id=10)
        assert len(conn.calls) == 1
        sql, params = conn.calls[0]
        assert "DELETE FROM race_events" in sql
        assert "user_id = ?" in sql
        assert params == (10, 1)
        assert conn.commits == 1


# ─── add_route_locale ────────────────────────────────────────────────────────


class TestAddRouteLocale:
    def test_inserts_returning_id(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 100})
        new_id = add_route_locale(
            conn,
            race_event_id=10,
            role="start",
            sequence_idx=1,
            name="Trailhead",
        )
        assert new_id == 100
        assert conn.commits == 1
        assert "INSERT INTO race_route_locales" in conn.calls[0][0]
        params = conn.calls[0][1]
        assert params[0] == 10  # race_event_id
        assert params[1] == "start"
        assert params[2] == 1
        assert params[3] == "Trailhead"

    def test_rejects_invalid_role(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="role must be one of"):
            add_route_locale(
                conn,
                race_event_id=10,
                role="midpoint",  # not in the closed 7-element enum
                sequence_idx=1,
                name="X",
            )
        assert len(conn.calls) == 0

    def test_rejects_sequence_idx_below_one(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="sequence_idx must be >= 1"):
            add_route_locale(
                conn,
                race_event_id=10,
                role="start",
                sequence_idx=0,
                name="X",
            )
        assert len(conn.calls) == 0


# ─── add_route_locale_equipment ──────────────────────────────────────────────


class TestAddRouteLocaleEquipment:
    def test_inserts_returning_id(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 500})
        new_id = add_route_locale_equipment(
            conn,
            race_route_locale_id=100,
            equipment_name="6L water cache",
            quantity_text="6 liters",
            notes="Shared with team",
        )
        assert new_id == 500
        assert conn.commits == 1
        assert "INSERT INTO race_route_locale_equipment" in conn.calls[0][0]
        params = conn.calls[0][1]
        assert params[0] == 100
        assert params[1] == "6L water cache"
        assert params[2] == "6 liters"
        assert params[3] == "Shared with team"

    def test_optional_fields_default_to_none(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 501})
        add_route_locale_equipment(
            conn,
            race_route_locale_id=100,
            equipment_name="Spare batteries",
        )
        params = conn.calls[0][1]
        assert params[2] is None  # quantity_text
        assert params[3] is None  # notes


# ─── Module constants ────────────────────────────────────────────────────────


class TestModuleConstants:
    def test_valid_race_formats_closed_4_set(self):
        assert set(VALID_RACE_FORMATS) == {
            "single_day",
            "expedition_ar",
            "stage_race",
            "multi_day_ultra",
        }

    def test_valid_route_locale_roles_closed_7_set(self):
        assert set(VALID_ROUTE_LOCALE_ROLES) == {
            "start",
            "transition_area",
            "aid_station",
            "drop_bag_point",
            "bivvy",
            "finish",
            "other",
        }


# ─── get_race_event ──────────────────────────────────────────────────────────


class TestGetRaceEvent:
    def test_returns_none_when_row_missing_or_wrong_user(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        assert get_race_event(conn, user_id=1, race_event_id=999) is None
        sql, params = conn.calls[0]
        assert "FROM race_events" in sql
        assert "user_id = ?" in sql
        assert params == (999, 1)

    def test_returns_dict_with_full_columns(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        result = get_race_event(conn, user_id=1, race_event_id=10)
        assert result is not None
        assert result["id"] == 10
        assert result["user_id"] == 1
        assert result["name"] == "Pocket Gopher Extreme 2026"
        assert result["race_rules_summary"] == "Mandatory checkpoints; 56h cutoff."


# ─── update_race_event ───────────────────────────────────────────────────────


class TestUpdateRaceEvent:
    def test_updates_with_user_scope(self):
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Renamed Race",
            event_date=date(2026, 8, 1),
            race_format="multi_day_ultra",
            distance_km=Decimal("200"),
            notes="New notes",
        )
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "UPDATE race_events" in sql
        assert "WHERE id = ? AND user_id = ?" in sql
        # name + event_date + race_format + distance_km + total_elevation_gain_m
        # + race_rules_summary + mandatory_gear_text + event_locale_id + notes
        # + race_event_id + user_id
        assert params[0] == "Renamed Race"
        assert params[1] == date(2026, 8, 1)
        assert params[2] == "multi_day_ultra"
        assert params[3] == Decimal("200")
        assert params[-2] == 10  # race_event_id
        assert params[-1] == 1   # user_id

    def test_rejects_invalid_race_format(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="race_format must be one of"):
            update_race_event(
                conn,
                user_id=1,
                race_event_id=10,
                name="X",
                event_date=date(2026, 8, 1),
                race_format="ultra_megalong",  # not in closed enum
            )
        assert len(conn.calls) == 0


# ─── list_route_locales ──────────────────────────────────────────────────────


class TestListRouteLocales:
    def test_returns_dicts_ordered_by_sequence_idx(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {
                "id": 100,
                "race_event_id": 10,
                "role": "start",
                "sequence_idx": 1,
                "name": "Trailhead",
                "mile_marker": Decimal("0"),
                "lat": None,
                "lng": None,
                "mapbox_id": None,
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
            {
                "id": 101,
                "race_event_id": 10,
                "role": "finish",
                "sequence_idx": 5,
                "name": "Finish line",
                "mile_marker": Decimal("100"),
                "lat": None,
                "lng": None,
                "mapbox_id": None,
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        result = list_route_locales(conn, race_event_id=10)
        assert len(result) == 2
        assert result[0]["role"] == "start"
        assert result[1]["sequence_idx"] == 5
        sql, params = conn.calls[0]
        assert "ORDER BY sequence_idx ASC" in sql
        assert params == (10,)


# ─── update_route_locale ─────────────────────────────────────────────────────


class TestUpdateRouteLocale:
    def test_updates_with_race_event_scope(self):
        conn = _FakeConn()
        update_route_locale(
            conn,
            race_event_id=10,
            route_locale_id=100,
            role="aid_station",
            sequence_idx=3,
            name="Aid Station 1",
            mile_marker=Decimal("12.5"),
            notes="Water + Coke",
        )
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "UPDATE race_route_locales" in sql
        assert "WHERE id = ? AND race_event_id = ?" in sql
        assert params[0] == "aid_station"
        assert params[1] == 3
        assert params[2] == "Aid Station 1"
        assert params[-2] == 100  # route_locale_id
        assert params[-1] == 10   # race_event_id

    def test_rejects_invalid_role(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="role must be one of"):
            update_route_locale(
                conn,
                race_event_id=10,
                route_locale_id=100,
                role="midpoint",
                sequence_idx=1,
                name="X",
            )
        assert len(conn.calls) == 0

    def test_rejects_sequence_idx_below_one(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="sequence_idx must be >= 1"):
            update_route_locale(
                conn,
                race_event_id=10,
                route_locale_id=100,
                role="start",
                sequence_idx=0,
                name="X",
            )
        assert len(conn.calls) == 0


# ─── delete_route_locale ─────────────────────────────────────────────────────


class TestDeleteRouteLocale:
    def test_delete_scoped_to_race_event(self):
        conn = _FakeConn()
        delete_route_locale(conn, race_event_id=10, route_locale_id=100)
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "DELETE FROM race_route_locales" in sql
        assert "race_event_id = ?" in sql
        assert params == (100, 10)


# ─── list_route_locale_equipment ─────────────────────────────────────────────


class TestListRouteLocaleEquipment:
    def test_returns_rows_ordered_by_id(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {
                "id": 500,
                "race_route_locale_id": 100,
                "equipment_name": "6L water cache",
                "quantity_text": "6 liters",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        result = list_route_locale_equipment(conn, race_route_locale_id=100)
        assert len(result) == 1
        assert result[0]["equipment_name"] == "6L water cache"
        sql, params = conn.calls[0]
        assert "ORDER BY id ASC" in sql
        assert params == (100,)


# ─── delete_route_locale_equipment ───────────────────────────────────────────


class TestDeleteRouteLocaleEquipment:
    def test_delete_scoped_to_route_locale(self):
        conn = _FakeConn()
        delete_route_locale_equipment(
            conn, race_route_locale_id=100, equipment_id=500
        )
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "DELETE FROM race_route_locale_equipment" in sql
        assert "race_route_locale_id = ?" in sql
        assert params == (500, 100)


# ─── race_terrain + aid_stations (Phase 5.1 form-refresh A) ──────────────────


class TestRaceTerrainAndAidStations:
    """Phase 5.1 form-refresh A — closes the race_event_payload.race_terrain
    + aid_stations forward-pointers carried by the orchestrator's vertical
    slice. Validates CRUD round-trip + JSONB adapter tolerance + payload
    construction including the TRN-xxx pattern validator."""

    def test_load_payload_hydrates_race_terrain_from_list(self):
        # psycopg2 default surfaces JSONB as a Python list/dict directly.
        conn = _FakeConn()
        conn.queue_response(row=_race_row(
            race_terrain=[
                {"terrain_id": "TRN-002", "pct_of_race": 35.0},
                {"terrain_id": "TRN-009", "pct_of_race": 15.0},
            ],
            aid_stations=4,
        ))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert len(payload.race_terrain) == 2
        assert payload.race_terrain[0].terrain_id == "TRN-002"
        assert payload.race_terrain[0].pct_of_race == 35.0
        assert payload.race_terrain[1].terrain_id == "TRN-009"
        assert payload.aid_stations == 4

    def test_load_payload_hydrates_race_terrain_from_jsonb_string(self):
        # Sqlite shim path surfaces JSONB as a JSON string; tolerant hydrate.
        conn = _FakeConn()
        conn.queue_response(row=_race_row(
            race_terrain='[{"terrain_id":"TRN-003","pct_of_race":40.0}]',
            aid_stations=0,
        ))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert len(payload.race_terrain) == 1
        assert payload.race_terrain[0].terrain_id == "TRN-003"
        assert payload.aid_stations == 0

    def test_load_payload_defaults_empty_when_jsonb_missing(self):
        conn = _FakeConn()
        # `race_terrain` absent (None) — older row pre-migration; should
        # surface as empty list, not raise.
        conn.queue_response(row=_race_row(race_terrain=None, aid_stations=None))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.race_terrain == []
        assert payload.aid_stations is None

    def test_load_payload_rejects_malformed_terrain_id(self):
        # The payload-level model_validator catches non-TRN-xxx ids loudly
        # at load time rather than letting them leak into Layer 2B.
        conn = _FakeConn()
        conn.queue_response(row=_race_row(
            race_terrain=[{"terrain_id": "MUD", "pct_of_race": 50.0}],
        ))
        conn.queue_response(rows=[])
        with pytest.raises(Exception) as exc:
            load_race_event_payload(conn, race_event_id=10)
        assert "TRN-\\d{3}" in str(exc.value) or "TRN-" in str(exc.value)

    def test_create_serializes_race_terrain_as_json_and_passes_aid_stations(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 99})
        new_id = create_race_event(
            conn,
            user_id=1,
            name="Pocket Gopher Extreme 2026",
            event_date=date(2026, 7, 17),
            race_format="expedition_ar",
            race_terrain=[
                {"terrain_id": "TRN-002", "pct_of_race": 35.0},
                {"terrain_id": "TRN-009", "pct_of_race": 15.0},
            ],
            aid_stations=0,
        )
        assert new_id == 99
        sql, params = conn.calls[0]
        # race_terrain JSON serialization + aid_stations integer position.
        # Param layout: (..., notes, race_terrain_json, aid_stations,
        # etl_version_set_json) → race_terrain at index -3, aid_stations -2.
        terrain_json = params[-3]
        assert isinstance(terrain_json, str)
        assert "TRN-002" in terrain_json
        assert "TRN-009" in terrain_json
        assert params[-2] == 0  # aid_stations

    def test_create_empty_race_terrain_serializes_as_empty_array(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 1})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 1, 1),
            race_format="single_day",
        )
        params = conn.calls[0][1]
        # Defaults: race_terrain=None → serialized as `[]`; aid_stations=None.
        assert params[-3] == "[]"
        assert params[-2] is None

    def test_update_serializes_race_terrain_and_aid_stations(self):
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="expedition_ar",
            race_terrain=[{"terrain_id": "TRN-016", "pct_of_race": 100.0}],
            aid_stations=12,
        )
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "race_terrain = ?::jsonb" in sql
        assert "aid_stations = ?" in sql
        # Layout of params in UPDATE: name, event_date, race_format,
        # distance_km, total_elevation_gain_m, race_rules_summary,
        # mandatory_gear_text, event_locale_id, notes, race_terrain_json,
        # aid_stations, race_event_id, user_id  (13 total)
        assert params[-1] == 1   # user_id
        assert params[-2] == 10  # race_event_id
        assert params[-3] == 12  # aid_stations
        terrain_json = params[-4]
        assert isinstance(terrain_json, str)
        assert "TRN-016" in terrain_json

    def test_get_race_event_hydrates_jsonb_terrain_from_string(self):
        # Sqlite shim path — same tolerance as load_race_event_payload.
        conn = _FakeConn()
        conn.queue_response(row={
            "id": 10,
            "user_id": 1,
            "name": "Race",
            "event_date": date(2026, 7, 17),
            "race_format": "expedition_ar",
            "distance_km": None,
            "total_elevation_gain_m": None,
            "race_rules_summary": None,
            "mandatory_gear_text": None,
            "event_locale_id": None,
            "is_target_event": True,
            "notes": None,
            "race_terrain": '[{"terrain_id":"TRN-002","pct_of_race":50.0}]',
            "aid_stations": 4,
            "created_at": None,
            "updated_at": None,
        })
        result = get_race_event(conn, user_id=1, race_event_id=10)
        assert result is not None
        assert result["race_terrain"] == [
            {"terrain_id": "TRN-002", "pct_of_race": 50.0}
        ]
        assert result["aid_stations"] == 4

    def test_list_athlete_includes_aid_stations(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{
            "id": 1,
            "name": "PGE 2026",
            "event_date": date(2026, 7, 17),
            "race_format": "expedition_ar",
            "is_target_event": True,
            "distance_km": Decimal("160"),
            "total_elevation_gain_m": Decimal("3000"),
            "event_locale_id": None,
            "aid_stations": 0,
            "created_at": None,
            "updated_at": None,
        }])
        result = list_athlete_race_events(conn, user_id=1)
        assert len(result) == 1
        assert result[0]["aid_stations"] == 0
        # SELECT names the column.
        assert "aid_stations" in conn.calls[0][0]
