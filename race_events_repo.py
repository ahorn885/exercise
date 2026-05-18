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
    of route_locale ids we found). Returns None when the race_event_id
    doesn't exist.

    Caller is responsible for authorizing the read (user_id is on the row;
    no access control here).
    """
    cur = db.execute(
        """
        SELECT id, user_id, name, event_date, race_format,
               distance_km, total_elevation_gain_m,
               race_rules_summary, mandatory_gear_text,
               event_locale_id, is_target_event, notes
          FROM race_events
         WHERE id = ?
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
        event_locale_id=race_row["event_locale_id"],
        is_target_event=bool(race_row["is_target_event"]),
        notes=race_row["notes"],
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
    is_target_event: bool = False,
    notes: str | None = None,
    etl_version_set: dict[str, Any] | None = None,
) -> int:
    """INSERT a new race_event row. Returns the new id.

    Caller responsible for unsetting an existing target row before inserting
    a second target (use `set_target_event` for an atomic flip). Direct
    insertion of a second target_event=TRUE row will violate the partial
    UNIQUE index and raise.
    """
    if race_format not in VALID_RACE_FORMATS:
        raise ValueError(f"race_format must be one of {VALID_RACE_FORMATS}; got {race_format!r}")

    cur = db.execute(
        """
        INSERT INTO race_events
            (user_id, name, event_date, race_format,
             distance_km, total_elevation_gain_m,
             race_rules_summary, mandatory_gear_text,
             event_locale_id, is_target_event, notes, etl_version_set)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
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
