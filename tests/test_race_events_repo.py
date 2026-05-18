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

from layer4.context import RaceEventPayload, RouteLocale
from race_events_repo import (
    VALID_RACE_FORMATS,
    VALID_ROUTE_LOCALE_ROLES,
    add_route_locale,
    add_route_locale_equipment,
    create_race_event,
    delete_race_event,
    list_athlete_race_events,
    load_race_event_payload,
    load_target_race_event_payload,
    set_target_event,
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
        "event_locale_id": 5,
        "is_target_event": True,
        "notes": "Crew at TA2.",
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
        assert payload.event_locale_id == 5
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
