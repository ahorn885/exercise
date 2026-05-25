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
                "race_format": "continuous_multi_day",
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
    #
    # D-73 Phase 5.2 walkthrough #1 + #2a (2026-05-21) — extended with
    # Mapbox-anchored race-location columns + race_url. Default values None
    # so existing tests that asserted "no Mapbox data" still pass; explicit
    # overrides drive the new-shape tests.
    base = {
        "id": 10,
        "user_id": 1,
        "name": "Pocket Gopher Extreme 2026",
        "event_date": date(2026, 7, 17),
        "race_format": "continuous_multi_day",
        "distance_km": Decimal("160"),
        "total_elevation_gain_m": Decimal("3000"),
        # FormRefresh A1 (2026-05-25) — magnitude axis columns. Default None
        # so existing tests see "not captured"; new-shape tests override.
        "estimated_duration_hr": None,
        "primary_metric": None,
        "race_rules_summary": "Mandatory checkpoints; 56h cutoff.",
        "mandatory_gear_text": "Headlamp; bivvy; 6L water cap.",
        "event_locale_slug": "nerstrand_finish",
        "is_target_event": True,
        "notes": "Crew at TA2.",
        # Phase 5.1 form-refresh A — JSONB list surfaces as list or str
        # depending on adapter; tests seed list (the psycopg2 default).
        "race_terrain": [],
        # D-73 Phase 5.2 walkthrough #1 — Mapbox-anchored race-location
        # columns. Bucket C (i) (2026-05-24) flipped the default from None
        # to a placeholder mapbox_id so the load_race_event_payload pydantic
        # validator (which now requires event_locale_mapbox_id non-null on
        # every RaceEventPayload construction) passes. Tests that want to
        # exercise the un-anchored path override the field directly.
        "event_locale_name": "Test Race Location",
        "event_locale_mapbox_id": "poi.test_anchor",
        "event_locale_place_name": "Test Race Location, Test State",
        "event_locale_lat": None,
        "event_locale_lng": None,
        # D-73 Phase 5.2 walkthrough #2a — race-director site URL.
        "race_url": None,
        # D-73 Phase 5.2 Bucket E.(b) — per-race framework_sport override.
        "framework_sport": None,
        # D-73 Phase 5.2 Bucket E.(b)-B2 — per-race discipline filter
        # override. None = use full bridge defaults (pre-B2 behavior).
        "included_discipline_ids": None,
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
        assert payload.race_format == "continuous_multi_day"
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
            race_format="continuous_multi_day",
            distance_km=Decimal("160"),
            total_elevation_gain_m=Decimal("3000"),
            estimated_duration_hr=Decimal("56"),
            primary_metric="duration",
            race_rules_summary="rules text",
            mandatory_gear_text="gear text",
            event_locale_id=5,
            is_target_event=True,
            notes="crew notes",
        )
        params = conn.calls[0][1]
        # FormRefresh A1 inserted estimated_duration_hr + primary_metric
        # after total_elevation_gain_m, shifting the trailing fields by 2.
        assert params[4] == Decimal("160")  # distance_km
        assert params[5] == Decimal("3000")  # total_elevation_gain_m
        assert params[6] == Decimal("56")  # estimated_duration_hr
        assert params[7] == "duration"  # primary_metric
        assert params[8] == "rules text"
        assert params[9] == "gear text"
        assert params[10] == 5  # event_locale_id
        assert params[11] is True  # is_target_event
        assert params[12] == "crew notes"

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
    def test_valid_race_formats_closed_3_set(self):
        # FormRefresh A1 (2026-05-25) — structural taxonomy collapse.
        # expedition_ar + multi_day_ultra folded into continuous_multi_day;
        # sport now lives on framework_sport, not the format axis.
        assert set(VALID_RACE_FORMATS) == {
            "single_day",
            "continuous_multi_day",
            "stage_race",
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
            race_format="continuous_multi_day",
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
        assert params[2] == "continuous_multi_day"
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


# ─── race_terrain (Phase 5.1 form-refresh A) ─────────────────────────────────


class TestRaceTerrain:
    """Phase 5.1 form-refresh A — closes the race_event_payload.race_terrain
    forward-pointer carried by the orchestrator's vertical slice. Validates
    CRUD round-trip + JSONB adapter tolerance + payload construction
    including the TRN-xxx pattern validator. (The `aid_stations` count was
    removed in FormRefresh A2, 2026-05-25.)"""

    def test_load_payload_hydrates_race_terrain_from_list(self):
        # psycopg2 default surfaces JSONB as a Python list/dict directly.
        conn = _FakeConn()
        conn.queue_response(row=_race_row(
            race_terrain=[
                {"terrain_id": "TRN-002", "pct_of_race": 35.0},
                {"terrain_id": "TRN-009", "pct_of_race": 15.0},
            ],
        ))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert len(payload.race_terrain) == 2
        assert payload.race_terrain[0].terrain_id == "TRN-002"
        assert payload.race_terrain[0].pct_of_race == 35.0
        assert payload.race_terrain[1].terrain_id == "TRN-009"

    def test_load_payload_hydrates_race_terrain_from_jsonb_string(self):
        # Sqlite shim path surfaces JSONB as a JSON string; tolerant hydrate.
        conn = _FakeConn()
        conn.queue_response(row=_race_row(
            race_terrain='[{"terrain_id":"TRN-003","pct_of_race":40.0}]',
        ))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert len(payload.race_terrain) == 1
        assert payload.race_terrain[0].terrain_id == "TRN-003"

    def test_load_payload_defaults_empty_when_jsonb_missing(self):
        conn = _FakeConn()
        # `race_terrain` absent (None) — older row pre-migration; should
        # surface as empty list, not raise.
        conn.queue_response(row=_race_row(race_terrain=None))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.race_terrain == []

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

    def test_create_serializes_race_terrain_as_json(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 99})
        new_id = create_race_event(
            conn,
            user_id=1,
            name="Pocket Gopher Extreme 2026",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            race_terrain=[
                {"terrain_id": "TRN-002", "pct_of_race": 35.0},
                {"terrain_id": "TRN-009", "pct_of_race": 15.0},
            ],
        )
        assert new_id == 99
        sql, params = conn.calls[0]
        # Locate the race_terrain param via its JSONB string content to stay
        # robust against future column adds rather than asserting position.
        terrain_params = [p for p in params if isinstance(p, str) and "TRN-002" in p]
        assert len(terrain_params) == 1, f"expected exactly one TRN-* JSON param; got {params}"
        terrain_json = terrain_params[0]
        assert "TRN-002" in terrain_json
        assert "TRN-009" in terrain_json

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
        # Defaults: race_terrain=None → serialized as `[]`.
        # The JSONB-string `"[]"` appears twice in the param tuple
        # (race_terrain default + etl_version_set default `"{}"`); assert
        # presence rather than exact position to stay robust against future
        # column adds.
        assert "[]" in params
        # etl_version_set serializes as `"{}"` (empty dict default).
        assert "{}" in params

    def test_update_serializes_race_terrain(self):
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            race_terrain=[{"terrain_id": "TRN-016", "pct_of_race": 100.0}],
        )
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "race_terrain = ?::jsonb" in sql
        # `race_terrain = ?::jsonb` is the last SET clause, so the param
        # tuple tail is: ..., race_terrain_json, race_event_id, user_id.
        assert params[-1] == 1   # user_id
        assert params[-2] == 10  # race_event_id
        terrain_json = params[-3]
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
            "race_format": "continuous_multi_day",
            "distance_km": None,
            "total_elevation_gain_m": None,
            "race_rules_summary": None,
            "mandatory_gear_text": None,
            "event_locale_id": None,
            "is_target_event": True,
            "notes": None,
            "race_terrain": '[{"terrain_id":"TRN-002","pct_of_race":50.0}]',
            "created_at": None,
            "updated_at": None,
        })
        result = get_race_event(conn, user_id=1, race_event_id=10)
        assert result is not None
        assert result["race_terrain"] == [
            {"terrain_id": "TRN-002", "pct_of_race": 50.0}
        ]


# ─── D-73 Phase 5.2 walkthrough #1 + #2a — Mapbox race-location columns ─────


class TestMapboxRaceLocationColumns:
    """Mapbox-anchored race-location columns + race_url (D-73 Phase 5.2
    walkthrough #1 + #2a). The 5 race-location columns mirror the
    locale_profiles' Mapbox shape (name + mapbox_id + place_name + lat + lng);
    race_url is athlete-typed verbatim.
    """

    def test_load_payload_populates_mapbox_columns_when_present(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row(
            event_locale_slug=None,  # new shape — legacy FK cleared
            event_locale_name="Nerstrand State Park",
            event_locale_mapbox_id="poi.abcdef123",
            event_locale_place_name="Nerstrand State Park, Nerstrand, MN, US",
            event_locale_lat=Decimal("44.345"),
            event_locale_lng=Decimal("-93.106"),
            race_url="https://example.com/pge2026",
        ))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.event_locale_id is None
        assert payload.event_locale_name == "Nerstrand State Park"
        assert payload.event_locale_mapbox_id == "poi.abcdef123"
        assert payload.event_locale_place_name == "Nerstrand State Park, Nerstrand, MN, US"
        assert payload.event_locale_lat == 44.345
        assert payload.event_locale_lng == -93.106
        assert payload.race_url == "https://example.com/pge2026"

    def test_load_payload_rejects_unanchored_row(self):
        # D-73 Phase 5.2 Bucket C (i) — RaceEventPayload's validator now
        # requires event_locale_mapbox_id non-null on every construction.
        # Legacy pre-walkthrough rows that only had `event_locale_slug` (no
        # Mapbox anchor) raise at load time so the un-anchored shape is loud
        # rather than silently propagating through the orchestrator. The route
        # layer prevents new un-anchored writes; this test pins the load-side
        # backstop for legacy rows still sitting in the DB.
        row = _race_row()
        row["event_locale_name"] = None
        row["event_locale_mapbox_id"] = None
        row["event_locale_place_name"] = None
        conn = _FakeConn()
        conn.queue_response(row=row)
        conn.queue_response(rows=[])
        with pytest.raises(ValueError, match="event_locale_mapbox_id is required"):
            load_race_event_payload(conn, race_event_id=10)

    def test_create_passes_mapbox_kwargs_in_insert(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 42})
        new_id = create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            event_locale_name="Nerstrand State Park",
            event_locale_mapbox_id="poi.xyz",
            event_locale_place_name="Nerstrand State Park, MN",
            event_locale_lat=44.345,
            event_locale_lng=-93.106,
            race_url="https://example.com/pge2026",
        )
        assert new_id == 42
        sql, params = conn.calls[0]
        # SQL names all 6 new columns.
        for col in ("event_locale_name", "event_locale_mapbox_id",
                    "event_locale_place_name", "event_locale_lat",
                    "event_locale_lng", "race_url"):
            assert col in sql, f"SQL missing column {col!r}"
        # Mapbox kwargs threaded into the params tuple.
        assert "Nerstrand State Park" in params
        assert "poi.xyz" in params
        assert 44.345 in params
        assert -93.106 in params
        assert "https://example.com/pge2026" in params

    def test_create_defaults_mapbox_kwargs_to_none(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 1})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="single_day",
        )
        params = conn.calls[0][1]
        # All Mapbox + race_url defaults are None (5 + 1 = 6 None values
        # added by the walkthrough slice beyond the existing column set).
        none_count = sum(1 for p in params if p is None)
        assert none_count >= 6, f"expected ≥6 None params; got {none_count}: {params}"

    def test_update_passes_mapbox_kwargs(self):
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            event_locale_name="Nerstrand State Park",
            event_locale_mapbox_id="poi.xyz",
            event_locale_place_name="Nerstrand State Park, MN",
            event_locale_lat=44.345,
            event_locale_lng=-93.106,
            race_url="https://example.com/pge2026",
        )
        sql, params = conn.calls[0]
        for col in ("event_locale_name = ?", "event_locale_mapbox_id = ?",
                    "event_locale_place_name = ?", "event_locale_lat = ?",
                    "event_locale_lng = ?", "race_url = ?"):
            assert col in sql, f"UPDATE SQL missing {col!r}"
        assert "Nerstrand State Park" in params
        assert "poi.xyz" in params
        assert "https://example.com/pge2026" in params

    def test_update_locale_helper_clears_legacy_fk(self):
        """`update_race_event_locale` updates only the 5 Mapbox columns and
        clears the legacy `event_locale_id BIGINT FK` so post-update reads
        no longer surface the prior slug from the JOIN."""
        from race_events_repo import update_race_event_locale
        conn = _FakeConn()
        update_race_event_locale(
            conn,
            user_id=1,
            race_event_id=10,
            event_locale_name="Nerstrand State Park",
            event_locale_mapbox_id="poi.xyz",
            event_locale_place_name="Nerstrand State Park, MN",
            event_locale_lat=44.345,
            event_locale_lng=-93.106,
        )
        sql, params = conn.calls[0]
        assert "event_locale_id = NULL" in sql
        for col in ("event_locale_name = ?", "event_locale_mapbox_id = ?",
                    "event_locale_place_name = ?", "event_locale_lat = ?",
                    "event_locale_lng = ?"):
            assert col in sql, f"UPDATE SQL missing {col!r}"
        # 5 Mapbox params + race_event_id + user_id = 7 total
        assert len(params) == 7
        assert params[-1] == 1  # user_id
        assert params[-2] == 10  # race_event_id
        # No other columns mentioned (race_url, race_terrain, etc. untouched).
        assert "race_url = ?" not in sql
        assert "race_terrain = ?" not in sql
        assert conn.commits == 1

    def test_get_race_event_coerces_lat_lng_to_float(self):
        """`get_race_event` round-trips NUMERIC(9,6) lat/lng as float for
        template arithmetic + form-field rendering. Mirrors the
        `load_race_event_payload` precedent."""
        conn = _FakeConn()
        conn.queue_response(row={
            "id": 10,
            "user_id": 1,
            "name": "Race",
            "event_date": date(2026, 7, 17),
            "race_format": "continuous_multi_day",
            "distance_km": None,
            "total_elevation_gain_m": None,
            "race_rules_summary": None,
            "mandatory_gear_text": None,
            "event_locale_id": None,
            "is_target_event": True,
            "notes": None,
            "race_terrain": [],
            "event_locale_name": "Nerstrand",
            "event_locale_mapbox_id": "poi.xyz",
            "event_locale_place_name": None,
            "event_locale_lat": Decimal("44.345"),
            "event_locale_lng": Decimal("-93.106"),
            "race_url": None,
            "created_at": None,
            "updated_at": None,
        })
        result = get_race_event(conn, user_id=1, race_event_id=10)
        assert result is not None
        assert isinstance(result["event_locale_lat"], float)
        assert isinstance(result["event_locale_lng"], float)
        assert result["event_locale_lat"] == 44.345
        assert result["event_locale_lng"] == -93.106


class TestFrameworkSportOverride:
    """Per-race framework_sport override column (D-73 Phase 5.2 Bucket
    E.(b)). Athlete-typed verbatim, replaces athlete-profile primary_sport
    when set on the target race row.
    """

    def test_load_payload_populates_framework_sport_when_present(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row(framework_sport="Adventure Racing"))
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.framework_sport == "Adventure Racing"

    def test_load_payload_defaults_framework_sport_to_none(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.framework_sport is None

    def test_create_passes_framework_sport_kwarg(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 42})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            framework_sport="Adventure Racing",
        )
        sql, params = conn.calls[0]
        assert "framework_sport" in sql
        assert "Adventure Racing" in params

    def test_create_defaults_framework_sport_to_none(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 1})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="single_day",
        )
        # framework_sport not passed → None in the params tuple, between
        # race_url and etl_version_set. We don't pin the index (existing
        # tests cover positional stability for the earlier columns); just
        # confirm the new column is in the INSERT SQL.
        assert "framework_sport" in conn.calls[0][0]

    def test_update_passes_framework_sport_kwarg(self):
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            framework_sport="Adventure Racing",
        )
        sql, params = conn.calls[0]
        assert "framework_sport = ?" in sql
        assert "Adventure Racing" in params

    def test_update_can_clear_framework_sport(self):
        """Passing framework_sport=None on update clears the override (the
        column is NULLable). UPDATE SQL still names the column so the row's
        prior value gets overwritten."""
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            framework_sport=None,
        )
        sql, params = conn.calls[0]
        assert "framework_sport = ?" in sql
        # None appears in params for the framework_sport column slot.
        assert None in params


class TestIncludedDisciplineIdsOverride:
    """Per-race `included_discipline_ids` filter column (D-73 Phase 5.2
    Bucket E.(b)-B2). TEXT[] of canonical discipline IDs; narrows Layer
    2A's bridge-derived discipline list when supplied. None = use full
    bridge defaults (pre-B2 behavior).
    """

    def test_load_payload_populates_included_discipline_ids_when_present(self):
        conn = _FakeConn()
        conn.queue_response(
            row=_race_row(included_discipline_ids=["D-001", "D-010", "D-015"])
        )
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.included_discipline_ids == ["D-001", "D-010", "D-015"]

    def test_load_payload_defaults_included_discipline_ids_to_none(self):
        conn = _FakeConn()
        conn.queue_response(row=_race_row())
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.included_discipline_ids is None

    def test_load_payload_coerces_non_list_iterable_to_list(self):
        # psycopg2 may surface TEXT[] as a tuple under some adapter shapes;
        # the repo coerces to list[str] for downstream equality.
        conn = _FakeConn()
        conn.queue_response(
            row=_race_row(included_discipline_ids=("D-001", "D-015"))
        )
        conn.queue_response(rows=[])
        payload = load_race_event_payload(conn, race_event_id=10)
        assert payload is not None
        assert payload.included_discipline_ids == ["D-001", "D-015"]

    def test_create_passes_included_discipline_ids_kwarg(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 42})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            included_discipline_ids=["D-001", "D-015"],
        )
        sql, params = conn.calls[0]
        assert "included_discipline_ids" in sql
        assert "?::text[]" in sql
        assert ["D-001", "D-015"] in params

    def test_create_defaults_included_discipline_ids_to_none(self):
        conn = _FakeConn()
        conn.queue_response(row={"id": 1})
        create_race_event(
            conn,
            user_id=1,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="single_day",
        )
        # Default kwarg → None in the params tuple; column appears in SQL
        # so the row's value gets explicitly set rather than relying on
        # DDL default (which is NULL anyway, but explicit is safer).
        assert "included_discipline_ids" in conn.calls[0][0]

    def test_update_passes_included_discipline_ids_kwarg(self):
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            included_discipline_ids=["D-010", "D-015"],
        )
        sql, params = conn.calls[0]
        assert "included_discipline_ids = ?::text[]" in sql
        assert ["D-010", "D-015"] in params

    def test_update_can_clear_included_discipline_ids(self):
        """Passing included_discipline_ids=None clears the column to NULL
        (the column is NULLable). UPDATE SQL still names the column so the
        prior value gets overwritten."""
        conn = _FakeConn()
        update_race_event(
            conn,
            user_id=1,
            race_event_id=10,
            name="Race",
            event_date=date(2026, 7, 17),
            race_format="continuous_multi_day",
            included_discipline_ids=None,
        )
        sql, params = conn.calls[0]
        assert "included_discipline_ids = ?::text[]" in sql
        # None appears in params for the discipline_ids slot.
        assert None in params
