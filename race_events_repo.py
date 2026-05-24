"""Data-access helpers for the D-66 race-event tables.

Pure read/write functions against `race_events` + `race_route_locales` +
`race_route_locale_equipment`. No HTTP / no Flask blueprint — the profile UI
PR (deferred to a follow-on) will register a blueprint that consumes these
helpers, and the Layer 4 orchestrator consumes `load_target_race_event_payload`
to build the typed `RaceEventPayload` from DB rows before calling
`llm_layer4_race_week_brief`.

The composite key invariants for race-route-locale ordering + role anchors
live on `layer4.context.RaceEventPayload`'s model_validator — this module
issues `ORDER BY sequence_idx` on the SELECT so the payload constructor
doesn't have to re-sort.

Schema reference: `Race_Events_D66_Design_v1.md` §3.
Typed contract: `layer4/context.py` — RaceEventPayload + RouteLocale +
RouteLocaleEquipment.
"""

from __future__ import annotations

import json
from typing import Any

from layer4.context import (
    RaceEventPayload,
    RaceTerrainEntry,
    RouteLocale,
    RouteLocaleEquipment,
)


VALID_RACE_FORMATS = ("single_day", "expedition_ar", "stage_race", "multi_day_ultra")
VALID_ROUTE_LOCALE_ROLES = (
    "start",
    "transition_area",
    "aid_station",
    "drop_bag_point",
    "bivvy",
    "finish",
    "other",
)


def list_athlete_race_events(db, user_id: int) -> list[dict[str, Any]]:
    """List all race_events for an athlete ordered by event_date ascending.

    Returns lightweight dicts suitable for the profile-tab listing — does not
    join in route_locales or equipment (use `load_race_event_payload` for the
    full typed payload).
    """
    cur = db.execute(
        """
        SELECT id, name, event_date, race_format, is_target_event,
               distance_km, total_elevation_gain_m, event_locale_id,
               event_locale_name, event_locale_place_name,
               aid_stations,
               created_at, updated_at
          FROM race_events
         WHERE user_id = ?
         ORDER BY event_date ASC, id ASC
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def load_race_event_payload(db, race_event_id: int) -> RaceEventPayload | None:
    """Build a typed `RaceEventPayload` from DB rows for a specific race_event_id.

    Reads race_events + race_route_locales + race_route_locale_equipment in
    three SELECTs (one per table; the equipment SELECT is keyed on the set
    of route_locale ids we found). The race_events SELECT LEFT JOINs
    `locale_profiles` so the payload surfaces the locale slug (`str`) per
    the D-72 type-alignment resolution (2026-05-19) — Layer 2C + Layer 3B
    + dict-keys + cache keys all use slug; race_events keeps the BIGINT FK
    in the DB column for ON DELETE SET NULL behavior, transparent to
    consumers. Returns None when the race_event_id doesn't exist.

    Caller is responsible for authorizing the read (user_id is on the row;
    no access control here).
    """
    cur = db.execute(
        """
        SELECT re.id, re.user_id, re.name, re.event_date, re.race_format,
               re.distance_km, re.total_elevation_gain_m,
               re.race_rules_summary, re.mandatory_gear_text,
               lp.locale AS event_locale_slug,
               re.is_target_event, re.notes,
               re.race_terrain, re.aid_stations,
               re.event_locale_name, re.event_locale_mapbox_id,
               re.event_locale_place_name, re.event_locale_lat, re.event_locale_lng,
               re.race_url, re.framework_sport, re.included_discipline_ids,
               re.race_modality_hints
          FROM race_events re
          LEFT JOIN locale_profiles lp ON lp.id = re.event_locale_id
         WHERE re.id = ?
        """,
        (race_event_id,),
    )
    race_row = cur.fetchone()
    if race_row is None:
        return None

    cur = db.execute(
        """
        SELECT id, role, sequence_idx, name, mile_marker,
               lat, lng, mapbox_id, notes
          FROM race_route_locales
         WHERE race_event_id = ?
         ORDER BY sequence_idx ASC
        """,
        (race_event_id,),
    )
    locale_rows = list(cur.fetchall())

    # Equipment SELECT joins back to its parent route_locale row so we can
    # bucket per locale in one pass. Empty IN clause is safe because we
    # short-circuit when there are no route_locales.
    equipment_by_locale: dict[int, list[RouteLocaleEquipment]] = {}
    if locale_rows:
        locale_ids = [int(r["id"]) for r in locale_rows]
        placeholders = ",".join(["?"] * len(locale_ids))
        cur = db.execute(
            f"""
            SELECT race_route_locale_id, equipment_name, quantity_text, notes
              FROM race_route_locale_equipment
             WHERE race_route_locale_id IN ({placeholders})
             ORDER BY id ASC
            """,
            tuple(locale_ids),
        )
        for eq_row in cur.fetchall():
            parent_id = int(eq_row["race_route_locale_id"])
            equipment_by_locale.setdefault(parent_id, []).append(
                RouteLocaleEquipment(
                    equipment_name=eq_row["equipment_name"],
                    quantity_text=eq_row["quantity_text"],
                    notes=eq_row["notes"],
                )
            )

    route_locales = [
        RouteLocale(
            route_locale_id=int(r["id"]),
            role=r["role"],
            sequence_idx=int(r["sequence_idx"]),
            name=r["name"],
            mile_marker=r["mile_marker"],
            lat=r["lat"],
            lng=r["lng"],
            mapbox_id=r["mapbox_id"],
            notes=r["notes"],
            equipment=equipment_by_locale.get(int(r["id"]), []),
        )
        for r in locale_rows
    ]

    # JSONB column surfaces as list/dict via psycopg2's default adapter, or
    # as a str when the adapter routing isn't enabled (sqlite shim path).
    # Tolerate both so the payload construction matches the deployed shape.
    raw_terrain = race_row["race_terrain"]
    if isinstance(raw_terrain, str):
        raw_terrain = json.loads(raw_terrain) if raw_terrain else []
    elif raw_terrain is None:
        raw_terrain = []
    race_terrain = [
        RaceTerrainEntry(
            terrain_id=entry["terrain_id"],
            pct_of_race=float(entry["pct_of_race"]),
            discipline_id=entry.get("discipline_id"),
        )
        for entry in raw_terrain
    ]

    # included_discipline_ids: psycopg2's TEXT[] adapter returns list[str],
    # or None for NULL. The sqlite shim path stringifies as PG array literal
    # ('{D-001,D-008b}') which we don't tolerate here — sqlite path is only
    # used by the _FakeConn substrate in tests, which sets the field directly
    # as list[str] | None.
    raw_disc_filter = race_row["included_discipline_ids"]
    if raw_disc_filter is not None and not isinstance(raw_disc_filter, list):
        raw_disc_filter = list(raw_disc_filter)

    # BestFitModality_Spec_v2.md §C — race_modality_hints JSONB column;
    # same dual-shape tolerance as race_terrain (dict for psycopg2 adapter,
    # str for the sqlite shim path). Column default is '{}'::jsonb so pre-v2
    # rows surface as an empty dict (v1-identical resolver behavior).
    raw_hints = race_row["race_modality_hints"]
    if isinstance(raw_hints, str):
        raw_hints = json.loads(raw_hints) if raw_hints else {}
    elif raw_hints is None:
        raw_hints = {}
    race_modality_hints: dict[str, list[str]] = {}
    if isinstance(raw_hints, dict):
        for d_id, equip_list in raw_hints.items():
            if not isinstance(d_id, str) or not isinstance(equip_list, list):
                continue
            race_modality_hints[d_id] = [
                e for e in equip_list if isinstance(e, str) and e
            ]

    # D-73 Phase 5.2 walkthrough #1 (2026-05-21) — race_events now carries
    # Mapbox-anchored race-location columns alongside the legacy
    # event_locale_id BIGINT FK. New rows populate the Mapbox columns; the
    # legacy FK stays nullable for pre-walkthrough rows where the athlete
    # picked a saved locale from the (now-removed) dropdown. Layer 4 +
    # Layer 3B treat the row as "locale resolved" when EITHER the legacy
    # FK slug OR the new event_locale_name is set.
    event_locale_lat = race_row["event_locale_lat"]
    event_locale_lng = race_row["event_locale_lng"]
    return RaceEventPayload(
        race_event_id=int(race_row["id"]),
        user_id=int(race_row["user_id"]),
        name=race_row["name"],
        event_date=race_row["event_date"],
        race_format=race_row["race_format"],
        distance_km=race_row["distance_km"],
        total_elevation_gain_m=race_row["total_elevation_gain_m"],
        race_rules_summary=race_row["race_rules_summary"],
        mandatory_gear_text=race_row["mandatory_gear_text"],
        event_locale_id=race_row["event_locale_slug"],
        event_locale_name=race_row["event_locale_name"],
        event_locale_mapbox_id=race_row["event_locale_mapbox_id"],
        event_locale_place_name=race_row["event_locale_place_name"],
        event_locale_lat=(
            float(event_locale_lat) if event_locale_lat is not None else None
        ),
        event_locale_lng=(
            float(event_locale_lng) if event_locale_lng is not None else None
        ),
        is_target_event=bool(race_row["is_target_event"]),
        notes=race_row["notes"],
        race_terrain=race_terrain,
        aid_stations=(
            int(race_row["aid_stations"])
            if race_row["aid_stations"] is not None
            else None
        ),
        race_url=race_row["race_url"],
        framework_sport=race_row["framework_sport"],
        included_discipline_ids=raw_disc_filter,
        race_modality_hints=race_modality_hints,
        route_locales=route_locales,
    )


def load_target_race_event_payload(db, user_id: int) -> RaceEventPayload | None:
    """Convenience for the Layer 4 orchestrator — returns the athlete's
    current target race event payload, or None when no race row has
    is_target_event=true (open-ended mode per Layer 3B §8.3).
    """
    cur = db.execute(
        "SELECT id FROM race_events WHERE user_id = ? AND is_target_event = TRUE LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return load_race_event_payload(db, int(row["id"]))


def create_race_event(
    db,
    user_id: int,
    name: str,
    event_date,
    race_format: str,
    *,
    distance_km=None,
    total_elevation_gain_m=None,
    race_rules_summary: str | None = None,
    mandatory_gear_text: str | None = None,
    event_locale_id: int | None = None,
    event_locale_name: str | None = None,
    event_locale_mapbox_id: str | None = None,
    event_locale_place_name: str | None = None,
    event_locale_lat: float | None = None,
    event_locale_lng: float | None = None,
    race_url: str | None = None,
    framework_sport: str | None = None,
    included_discipline_ids: list[str] | None = None,
    is_target_event: bool = False,
    notes: str | None = None,
    race_terrain: list[dict[str, Any]] | None = None,
    aid_stations: int | None = None,
    etl_version_set: dict[str, Any] | None = None,
) -> int:
    """INSERT a new race_event row. Returns the new id.

    Caller responsible for unsetting an existing target row before inserting
    a second target (use `set_target_event` for an atomic flip). Direct
    insertion of a second target_event=TRUE row will violate the partial
    UNIQUE index and raise.

    `race_terrain` accepts a list of dicts shaped `{"terrain_id": str,
    "pct_of_race": float}` (route-layer parser already normalizes from
    form fields). Serialized to JSONB. Callers can also pass an empty list
    or None for "not captured yet"; both round-trip as `[]` on load.

    `event_locale_name` / `event_locale_mapbox_id` / `event_locale_place_name`
    / `event_locale_lat` / `event_locale_lng` carry the Mapbox-anchored
    race location per D-73 Phase 5.2 walkthrough #1. New rows populate
    these; the legacy `event_locale_id` BIGINT FK to locale_profiles stays
    nullable for backward compat with pre-walkthrough rows that used the
    saved-locale dropdown.
    """
    if race_format not in VALID_RACE_FORMATS:
        raise ValueError(f"race_format must be one of {VALID_RACE_FORMATS}; got {race_format!r}")

    cur = db.execute(
        """
        INSERT INTO race_events
            (user_id, name, event_date, race_format,
             distance_km, total_elevation_gain_m,
             race_rules_summary, mandatory_gear_text,
             event_locale_id, is_target_event, notes,
             race_terrain, aid_stations,
             event_locale_name, event_locale_mapbox_id, event_locale_place_name,
             event_locale_lat, event_locale_lng,
             race_url, framework_sport, included_discipline_ids,
             etl_version_set)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?, ?, ?, ?, ?, ?, ?, ?::text[], ?::jsonb)
        RETURNING id
        """,
        (
            user_id,
            name,
            event_date,
            race_format,
            distance_km,
            total_elevation_gain_m,
            race_rules_summary,
            mandatory_gear_text,
            event_locale_id,
            is_target_event,
            notes,
            json.dumps(race_terrain or []),
            aid_stations,
            event_locale_name,
            event_locale_mapbox_id,
            event_locale_place_name,
            event_locale_lat,
            event_locale_lng,
            race_url,
            framework_sport,
            included_discipline_ids,
            json.dumps(etl_version_set or {}),
        ),
    )
    row = cur.fetchone()
    db.commit()
    return int(row["id"])


def set_target_event(db, user_id: int, race_event_id: int) -> None:
    """Atomically flip the athlete's target race event to `race_event_id`.

    The partial UNIQUE index `race_events_user_target_uidx` enforces at most
    one target per athlete. We unset any existing TRUE rows before setting
    the new one so the index never sees two TRUE rows mid-transaction.
    """
    db.execute(
        "UPDATE race_events SET is_target_event = FALSE, updated_at = NOW() "
        "WHERE user_id = ? AND is_target_event = TRUE AND id <> ?",
        (user_id, race_event_id),
    )
    db.execute(
        "UPDATE race_events SET is_target_event = TRUE, updated_at = NOW() "
        "WHERE id = ? AND user_id = ?",
        (race_event_id, user_id),
    )
    db.commit()


def delete_race_event(db, user_id: int, race_event_id: int) -> None:
    """Delete a race event row. CASCADE clears its route_locales + equipment."""
    db.execute(
        "DELETE FROM race_events WHERE id = ? AND user_id = ?",
        (race_event_id, user_id),
    )
    db.commit()


def add_route_locale(
    db,
    race_event_id: int,
    role: str,
    sequence_idx: int,
    name: str,
    *,
    mile_marker=None,
    lat=None,
    lng=None,
    mapbox_id: str | None = None,
    notes: str | None = None,
) -> int:
    """INSERT a new race_route_locales row. Returns the new id.

    The UNIQUE (race_event_id, sequence_idx) constraint enforces caller-side
    sequence integrity; callers reordering existing rows are responsible for
    issuing the UPDATEs in an order that avoids transient collisions (e.g.,
    shift to negative + back, or DELETE + INSERT).
    """
    if role not in VALID_ROUTE_LOCALE_ROLES:
        raise ValueError(f"role must be one of {VALID_ROUTE_LOCALE_ROLES}; got {role!r}")
    if sequence_idx < 1:
        raise ValueError(f"sequence_idx must be >= 1; got {sequence_idx}")

    cur = db.execute(
        """
        INSERT INTO race_route_locales
            (race_event_id, role, sequence_idx, name, mile_marker, lat, lng, mapbox_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (race_event_id, role, sequence_idx, name, mile_marker, lat, lng, mapbox_id, notes),
    )
    row = cur.fetchone()
    db.commit()
    return int(row["id"])


def add_route_locale_equipment(
    db,
    race_route_locale_id: int,
    equipment_name: str,
    *,
    quantity_text: str | None = None,
    notes: str | None = None,
) -> int:
    """INSERT a new race_route_locale_equipment row. Returns the new id."""
    cur = db.execute(
        """
        INSERT INTO race_route_locale_equipment
            (race_route_locale_id, equipment_name, quantity_text, notes)
        VALUES (?, ?, ?, ?)
        RETURNING id
        """,
        (race_route_locale_id, equipment_name, quantity_text, notes),
    )
    row = cur.fetchone()
    db.commit()
    return int(row["id"])


# ─── Single-row reads + UPDATE/DELETE helpers (profile UI surface) ──────────


def get_race_event(db, user_id: int, race_event_id: int) -> dict[str, Any] | None:
    """Return one race_events row scoped to user_id, or None when the row
    doesn't exist or belongs to another user. Used by the profile-tab edit
    form to pre-populate fields before UPDATE.
    """
    cur = db.execute(
        """
        SELECT id, user_id, name, event_date, race_format,
               distance_km, total_elevation_gain_m,
               race_rules_summary, mandatory_gear_text,
               event_locale_id, is_target_event, notes,
               race_terrain, aid_stations,
               event_locale_name, event_locale_mapbox_id, event_locale_place_name,
               event_locale_lat, event_locale_lng,
               race_url, framework_sport, included_discipline_ids,
               created_at, updated_at
          FROM race_events
         WHERE id = ? AND user_id = ?
        """,
        (race_event_id, user_id),
    )
    row = cur.fetchone()
    if row is None:
        return None
    # JSONB column surfaces as list/dict via psycopg2's default adapter;
    # tolerate the sqlite shim path where it arrives as str (matching the
    # load_race_event_payload hydration).
    result = dict(row)
    raw_terrain = result.get("race_terrain")
    if isinstance(raw_terrain, str):
        result["race_terrain"] = json.loads(raw_terrain) if raw_terrain else []
    elif raw_terrain is None:
        result["race_terrain"] = []
    # NUMERIC(9,6) round-trips as Decimal under psycopg2; coerce to float so
    # template arithmetic + form-field rendering stay simple. None passes
    # through.
    for k in ("event_locale_lat", "event_locale_lng"):
        v = result.get(k)
        if v is not None and not isinstance(v, float):
            result[k] = float(v)
    # TEXT[] column surfaces as list[str] via psycopg2's array adapter, or
    # None for NULL. Coerce any non-list iterable (test substrates) to list
    # so callers can compare against list literals cleanly.
    raw_disc_filter = result.get("included_discipline_ids")
    if raw_disc_filter is not None and not isinstance(raw_disc_filter, list):
        result["included_discipline_ids"] = list(raw_disc_filter)
    return result


def update_race_event(
    db,
    user_id: int,
    race_event_id: int,
    *,
    name: str,
    event_date,
    race_format: str,
    distance_km=None,
    total_elevation_gain_m=None,
    race_rules_summary: str | None = None,
    mandatory_gear_text: str | None = None,
    event_locale_id: int | None = None,
    event_locale_name: str | None = None,
    event_locale_mapbox_id: str | None = None,
    event_locale_place_name: str | None = None,
    event_locale_lat: float | None = None,
    event_locale_lng: float | None = None,
    race_url: str | None = None,
    framework_sport: str | None = None,
    included_discipline_ids: list[str] | None = None,
    notes: str | None = None,
    race_terrain: list[dict[str, Any]] | None = None,
    aid_stations: int | None = None,
    race_modality_hints: dict[str, list[str]] | None = None,
) -> None:
    """UPDATE a race_events row's editable fields. `is_target_event` flips
    are handled separately via `set_target_event`. Caller is expected to
    have verified ownership via `get_race_event` before issuing the
    update.

    `race_terrain` accepts a list of dicts; serialized to JSONB. Pass an
    empty list to clear; passing None coerces to empty list (the column
    is NOT NULL DEFAULT '[]'::jsonb).

    `race_modality_hints` per BestFitModality_Spec_v2.md §C accepts a dict
    shaped `{discipline_id: [equipment_canonical_name, ...], ...}`;
    serialized to JSONB. None coerces to empty dict ('{}'::jsonb default).
    """
    if race_format not in VALID_RACE_FORMATS:
        raise ValueError(f"race_format must be one of {VALID_RACE_FORMATS}; got {race_format!r}")

    db.execute(
        """
        UPDATE race_events
           SET name = ?,
               event_date = ?,
               race_format = ?,
               distance_km = ?,
               total_elevation_gain_m = ?,
               race_rules_summary = ?,
               mandatory_gear_text = ?,
               event_locale_id = ?,
               event_locale_name = ?,
               event_locale_mapbox_id = ?,
               event_locale_place_name = ?,
               event_locale_lat = ?,
               event_locale_lng = ?,
               race_url = ?,
               framework_sport = ?,
               included_discipline_ids = ?::text[],
               notes = ?,
               race_terrain = ?::jsonb,
               aid_stations = ?,
               race_modality_hints = ?::jsonb,
               updated_at = NOW()
         WHERE id = ? AND user_id = ?
        """,
        (
            name,
            event_date,
            race_format,
            distance_km,
            total_elevation_gain_m,
            race_rules_summary,
            mandatory_gear_text,
            event_locale_id,
            event_locale_name,
            event_locale_mapbox_id,
            event_locale_place_name,
            event_locale_lat,
            event_locale_lng,
            race_url,
            framework_sport,
            included_discipline_ids,
            notes,
            json.dumps(race_terrain or []),
            aid_stations,
            json.dumps(race_modality_hints or {}),
            race_event_id,
            user_id,
        ),
    )
    db.commit()


def update_race_event_locale(
    db,
    user_id: int,
    race_event_id: int,
    *,
    event_locale_name: str | None,
    event_locale_mapbox_id: str | None,
    event_locale_place_name: str | None,
    event_locale_lat: float | None,
    event_locale_lng: float | None,
) -> None:
    """UPDATE just the 5 Mapbox-anchored race-location columns on a single
    race_events row. Used by the race-edit page's "Set race location" inline
    flow so the athlete can pick a Mapbox feature without re-submitting the
    full race-details form. Also clears the legacy `event_locale_id` BIGINT
    FK so a row that previously pointed at a saved athlete locale stops
    surfacing the old slug downstream.
    """
    db.execute(
        """
        UPDATE race_events
           SET event_locale_name = ?,
               event_locale_mapbox_id = ?,
               event_locale_place_name = ?,
               event_locale_lat = ?,
               event_locale_lng = ?,
               event_locale_id = NULL,
               updated_at = NOW()
         WHERE id = ? AND user_id = ?
        """,
        (
            event_locale_name,
            event_locale_mapbox_id,
            event_locale_place_name,
            event_locale_lat,
            event_locale_lng,
            race_event_id,
            user_id,
        ),
    )
    db.commit()


def list_route_locales(db, race_event_id: int) -> list[dict[str, Any]]:
    """Return the race_route_locales rows for an event ordered by
    sequence_idx ascending. Used by the edit page to render per-locale
    inline forms.
    """
    cur = db.execute(
        """
        SELECT id, race_event_id, role, sequence_idx, name,
               mile_marker, lat, lng, mapbox_id, notes,
               created_at, updated_at
          FROM race_route_locales
         WHERE race_event_id = ?
         ORDER BY sequence_idx ASC, id ASC
        """,
        (race_event_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def update_route_locale(
    db,
    race_event_id: int,
    route_locale_id: int,
    *,
    role: str,
    sequence_idx: int,
    name: str,
    mile_marker=None,
    lat=None,
    lng=None,
    mapbox_id: str | None = None,
    notes: str | None = None,
) -> None:
    """UPDATE a race_route_locales row's editable fields. Scoped to
    race_event_id to defend against crafted POSTs targeting another
    race's locales.
    """
    if role not in VALID_ROUTE_LOCALE_ROLES:
        raise ValueError(f"role must be one of {VALID_ROUTE_LOCALE_ROLES}; got {role!r}")
    if sequence_idx < 1:
        raise ValueError(f"sequence_idx must be >= 1; got {sequence_idx}")

    db.execute(
        """
        UPDATE race_route_locales
           SET role = ?,
               sequence_idx = ?,
               name = ?,
               mile_marker = ?,
               lat = ?,
               lng = ?,
               mapbox_id = ?,
               notes = ?,
               updated_at = NOW()
         WHERE id = ? AND race_event_id = ?
        """,
        (
            role,
            sequence_idx,
            name,
            mile_marker,
            lat,
            lng,
            mapbox_id,
            notes,
            route_locale_id,
            race_event_id,
        ),
    )
    db.commit()


def delete_route_locale(db, race_event_id: int, route_locale_id: int) -> None:
    """DELETE a race_route_locales row scoped to race_event_id. CASCADE
    clears the row's equipment items.
    """
    db.execute(
        "DELETE FROM race_route_locales WHERE id = ? AND race_event_id = ?",
        (route_locale_id, race_event_id),
    )
    db.commit()


def list_route_locale_equipment(
    db, race_route_locale_id: int
) -> list[dict[str, Any]]:
    """Return the equipment rows for a route locale ordered by id ascending."""
    cur = db.execute(
        """
        SELECT id, race_route_locale_id, equipment_name, quantity_text, notes,
               created_at, updated_at
          FROM race_route_locale_equipment
         WHERE race_route_locale_id = ?
         ORDER BY id ASC
        """,
        (race_route_locale_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def delete_route_locale_equipment(
    db, race_route_locale_id: int, equipment_id: int
) -> None:
    """DELETE a single equipment row scoped to its parent route_locale_id."""
    db.execute(
        "DELETE FROM race_route_locale_equipment "
        "WHERE id = ? AND race_route_locale_id = ?",
        (equipment_id, race_route_locale_id),
    )
    db.commit()
