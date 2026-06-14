"""athlete_event_windows repository — Event Windows (#581 WS-H).

Read + write side for an athlete's declared **event windows**: date-bounded
periods where the training environment differs from the default home cluster.

  - `indoor_only`        — home cluster minus all outdoor terrain (weather /
                           childcare); the cascade reroutes outdoor cardio to
                           the indoor machine / strength.                (Slice 1)
  - `locale_unavailable` — home cluster minus one locale (a closed gym, a
                           flooded park); the discipline reroutes to another
                           cluster locale or substitutes.                (Slice 1)
  - `away`               — home cluster REPLACED by a destination locale (a
                           `locale_profiles` row, picked or built inline); the
                           cascade resolves against that location's terrain /
                           equipment, with no brought craft unless declared
                           (Slice 4).                                    (Slice 2)

Windows are athlete-scoped (F1). The plan-gen orchestrator loads them via
`load_event_windows`, segments the plan span by date, and resolves the existing
feasibility cascade once per distinct environment (reduced or replaced).

Constraints live in app code (the project's no-DB-CHECK convention, mirroring
`athlete_crafts_repo`): `end_date >= start_date`; for `locale_unavailable` the
`unavailable_locale` is required + must resolve to one of the athlete's
`locale_profiles` rows; for `away` the `away_locale` is required + must likewise
resolve; each is cleared when the override_type doesn't use it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# The closed override-type set. Kept here (not a DB CHECK) so the capture form +
# this repo are the single source the validator asserts against.
OVERRIDE_TYPES: tuple[str, ...] = ("indoor_only", "locale_unavailable", "away")


class EventWindowError(ValueError):
    """A submitted event window failed an app-layer constraint."""


@dataclass(frozen=True)
class EventWindow:
    """One athlete-declared event window row."""

    id: int
    user_id: int
    start_date: date
    end_date: date
    override_type: str
    unavailable_locale: str | None
    away_locale: str | None
    notes: str


def load_event_windows(db, user_id: int) -> list[EventWindow]:
    """The athlete's event windows, ordered by `(start_date, id)` for a
    deterministic plan-span hash + render order."""
    rows = db.execute(
        "SELECT id, user_id, start_date, end_date, override_type, "
        "unavailable_locale, away_locale, notes FROM athlete_event_windows "
        "WHERE user_id = ? ORDER BY start_date, id",
        (user_id,),
    ).fetchall()
    return [
        EventWindow(
            id=row["id"],
            user_id=row["user_id"],
            start_date=_as_date(row["start_date"]),
            end_date=_as_date(row["end_date"]),
            override_type=row["override_type"],
            unavailable_locale=row["unavailable_locale"] or None,
            away_locale=row["away_locale"] or None,
            notes=row["notes"] or "",
        )
        for row in rows
    ]


def add_event_window(
    db,
    user_id: int,
    *,
    start_date: date,
    end_date: date,
    override_type: str,
    unavailable_locale: str | None = None,
    away_locale: str | None = None,
    notes: str = "",
) -> None:
    """Validate + insert one event window. Raises `EventWindowError` (writing
    nothing) on any constraint failure. Caller commits."""
    if override_type not in OVERRIDE_TYPES:
        raise EventWindowError(
            f"unknown override_type {override_type!r}; expected one of "
            f"{', '.join(OVERRIDE_TYPES)}"
        )
    if end_date < start_date:
        raise EventWindowError(
            f"end_date ({end_date.isoformat()}) is before start_date "
            f"({start_date.isoformat()})"
        )
    unavailable = (unavailable_locale or "").strip() or None
    away = (away_locale or "").strip() or None
    if override_type == "locale_unavailable":
        if unavailable is None:
            raise EventWindowError(
                "locale_unavailable requires an unavailable_locale"
            )
        if not _locale_exists(db, user_id, unavailable):
            raise EventWindowError(
                f"unavailable_locale {unavailable!r} is not one of your saved locales"
            )
        away = None
    elif override_type == "away":
        if away is None:
            raise EventWindowError("away requires an away_locale (destination)")
        if not _locale_exists(db, user_id, away):
            raise EventWindowError(
                f"away_locale {away!r} is not one of your saved locales"
            )
        unavailable = None
    else:
        # indoor_only carries no locale — clear any stray value so the stored row
        # can't imply a subtraction/replacement it doesn't make.
        unavailable = None
        away = None
    db.execute(
        "INSERT INTO athlete_event_windows "
        "  (user_id, start_date, end_date, override_type, unavailable_locale, "
        "   away_locale, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, start_date, end_date, override_type, unavailable, away, notes),
    )


def delete_event_window(db, user_id: int, window_id: int) -> None:
    """Delete one of the athlete's windows (user-scoped — a foreign window id
    matches nothing). Caller commits."""
    db.execute(
        "DELETE FROM athlete_event_windows WHERE id = ? AND user_id = ?",
        (window_id, user_id),
    )


def evict_plan_caches_on_event_windows_change(db, user_id: int) -> None:
    """A window add/delete changes the date-segmented plan-gen feasibility, so
    invalidate the two synthesis entry points that consume it. Unlike the craft
    store, event windows are NOT a Layer-1 field — they fold directly into the
    `plan_create` / `plan_refresh` cache keys (`compute_event_windows_hash`) — so
    eviction is scoped to those two, not `single_session` / `race_week_brief`."""
    # Imported lazily: this repo is imported at `layer4` package-init time by the
    # orchestrator, so a module-level `layer4.cache` import would cycle.
    from layer4.cache import Layer4Cache
    from layer4.cache_postgres import PostgresCacheBackend

    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    cache.invalidate_user(
        user_id,
        layer="event_windows",
        entry_points=("plan_create", "plan_refresh"),
    )


def _locale_exists(db, user_id: int, locale: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    ).fetchone()
    return row is not None


def _as_date(value) -> date:
    """Coerce a DATE cell to `date` — Postgres returns `date`; the SQLite test
    shim and form round-trips can hand back an ISO string."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
