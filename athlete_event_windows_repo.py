"""athlete_event_windows repository — Event Windows Slice 1 (#581 WS-H).

Read + write side for an athlete's declared **event windows**: date-bounded
periods where the training environment differs from the default home cluster.
Slice 1 covers the two SUBTRACTIVE home override types —

  - `indoor_only`        — home cluster minus all outdoor terrain (weather /
                           childcare); the cascade reroutes outdoor cardio to
                           the indoor machine / strength.
  - `locale_unavailable` — home cluster minus one locale (a closed gym, a
                           flooded park); the discipline reroutes to another
                           cluster locale or substitutes.
  - `away`               — training from a DIFFERENT location whose own radius
                           cluster (anchored at `away_locale`, same logic as
                           home) REPLACES the home cluster for the window's
                           dates. Away craft defaults to none (Slice 4 adds
                           declared brought-craft).

Windows are athlete-scoped (F1). The plan-gen orchestrator loads them via
`load_event_windows`, segments the plan span by date, and resolves the existing
feasibility cascade once per environment (reduced for the subtractive types, the
destination's cluster for `away`).

Constraints live in app code (the project's no-DB-CHECK convention, mirroring
`athlete_crafts_repo`): `end_date >= start_date`; `unavailable_locale` is
required + must resolve to one of the athlete's `locale_profiles` rows iff
`override_type = 'locale_unavailable'`; `away_locale` likewise iff
`override_type = 'away'`. The non-applicable locale field is cleared.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES

# Override types. Kept here (not a DB CHECK) so the capture form + this repo are
# the single closed set the validator asserts. Slice 2 adds 'away'.
OVERRIDE_TYPES: tuple[str, ...] = ("indoor_only", "locale_unavailable", "away")

# Slice 4 (#581 WS-H) — the closed craft enum brought-craft is validated against
# (the same set athlete_crafts_repo offers). Emitted in this order for a stable
# stored CSV → deterministic compute_event_windows_hash.
_CRAFT_SLUGS: tuple[str, ...] = (*BIKE_TYPES, *PADDLE_CRAFT_TYPES)


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
    # Slice 4 (#581 WS-H) — craft brought to an 'away' window (the (c) surface);
    # empty tuple on non-away windows / when nothing is brought. Fed (unioned with
    # the standing craft<->locale set) as the away cluster's owned_crafts.
    brought_craft: tuple[str, ...] = ()


def load_event_windows(db, user_id: int) -> list[EventWindow]:
    """The athlete's event windows, ordered by `(start_date, id)` for a
    deterministic plan-span hash + render order."""
    rows = db.execute(
        "SELECT id, user_id, start_date, end_date, override_type, "
        "unavailable_locale, away_locale, brought_craft, notes "
        "FROM athlete_event_windows "
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
            brought_craft=tuple(_split_craft(row["brought_craft"])),
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
    brought_craft: list[str] | None = None,
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
    unavail = (unavailable_locale or "").strip() or None
    away = (away_locale or "").strip() or None
    crafts: list[str] = []
    if override_type == "locale_unavailable":
        if unavail is None:
            raise EventWindowError(
                "locale_unavailable requires an unavailable_locale"
            )
        if not _locale_exists(db, user_id, unavail):
            raise EventWindowError(
                f"unavailable_locale {unavail!r} is not one of your saved locales"
            )
        away = None
    elif override_type == "away":
        if away is None:
            raise EventWindowError("away requires an away_locale (the destination)")
        if not _locale_exists(db, user_id, away):
            raise EventWindowError(
                f"away_locale {away!r} is not one of your saved locales"
            )
        unavail = None
        # Brought-craft is only meaningful on an away window (the destination's
        # env replaces home); validate against the closed enum, emit in enum
        # order for a stable stored CSV.
        crafts = _validate_crafts(brought_craft or [])
    else:
        # indoor_only carries no locale — clear any stray value so the stored row
        # can't imply a subtraction it doesn't make.
        unavail = None
        away = None
    db.execute(
        "INSERT INTO athlete_event_windows "
        "  (user_id, start_date, end_date, override_type, unavailable_locale, "
        "   away_locale, brought_craft, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, start_date, end_date, override_type, unavail, away,
            (",".join(crafts) or None), notes,
        ),
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


def _split_craft(value) -> list[str]:
    """Split the stored comma-separated brought-craft CSV (mirror of
    `athlete_crafts_repo._split`)."""
    if not value:
        return []
    return [tok.strip() for tok in str(value).split(",") if tok.strip()]


def _validate_crafts(values: list[str]) -> list[str]:
    """De-dupe + reject unknown slugs; emit in `_CRAFT_SLUGS` order for a stable
    stored CSV. Mirrors `athlete_crafts_repo._validate`."""
    chosen = {v for v in values if v}
    unknown = chosen - set(_CRAFT_SLUGS)
    if unknown:
        raise EventWindowError(
            f"unknown brought craft(s): {', '.join(sorted(unknown))}"
        )
    return [s for s in _CRAFT_SLUGS if s in chosen]


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
