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
# the single closed set the validator asserts. Slice 2 adds 'away'; Slice 6
# (#593) adds the two VOLUME types — 'reduced_volume' (the day carries a reduced
# share of capacity, the athlete-set `volume_pct`) and 'no_training' (the day is
# zeroed + dropped from the placement pool). Unlike the first three (feasibility
# overrides — they change WHAT is trainable), the volume types change HOW MUCH;
# they carry no locale and compose by union with a feasibility override on the
# same dates.
OVERRIDE_TYPES: tuple[str, ...] = (
    "indoor_only", "locale_unavailable", "away", "reduced_volume", "no_training",
)

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
    # Slice 6 (#593) — the retained capacity fraction for a 'reduced_volume'
    # window (0 < pct < 1), athlete-set per window. None on every other type
    # ('no_training' is the discrete 0% type, not pct=0).
    volume_pct: float | None = None


def load_event_windows(db, user_id: int) -> list[EventWindow]:
    """The athlete's event windows, ordered by `(start_date, id)` for a
    deterministic plan-span hash + render order."""
    rows = db.execute(
        "SELECT id, user_id, start_date, end_date, override_type, "
        "unavailable_locale, away_locale, brought_craft, volume_pct, notes "
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
            volume_pct=(
                float(row["volume_pct"]) if row["volume_pct"] is not None else None
            ),
        )
        for row in rows
    ]


def resolve_weather_city(db, user_id: int, on_date: date) -> str:
    """City to drive weather / clothing lookups for ``on_date``.

    An ``away`` event window covering the date wins — its destination
    (``away_locale``) resolves to that ``locale_profiles`` row's ``city``;
    otherwise the athlete's preferred-home city; otherwise ``''`` (the caller
    supplies its own fallback, e.g. the ``WEATHER_LOCATION`` env default).

    Replaces the retired ``plan_travel`` city read. Event windows are
    athlete-scoped, so the answer no longer varies by plan. Mirrors the old
    empty-city fall-through: an ``away`` window whose destination has no
    recorded city defers to the home city rather than blanking the lookup.
    """
    away = db.execute(
        "SELECT lp.city AS city FROM athlete_event_windows w "
        "JOIN locale_profiles lp "
        "  ON lp.user_id = w.user_id AND lp.locale = w.away_locale "
        "WHERE w.user_id = ? AND w.override_type = 'away' "
        "  AND w.start_date <= ? AND w.end_date >= ? AND lp.city != '' "
        "ORDER BY w.start_date, w.id LIMIT 1",
        (user_id, on_date, on_date),
    ).fetchone()
    if away:
        city, source = away["city"], "away"
    else:
        home = db.execute(
            "SELECT city FROM locale_profiles "
            "WHERE preferred AND user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        if home and home["city"]:
            city, source = home["city"], "home"
        else:
            city, source = "", "none"
    print(  # Rule #15 — which surface decided the weather/clothing city.
        f"[trip-city] user={user_id} date={on_date.isoformat()} "
        f"source={source} city={city!r}"
    )
    return city


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
    volume_pct: float | None = None,
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
    # Slice 6 (#593) — volume_pct is meaningful only on reduced_volume (required,
    # strictly between 0 and 1); cleared on every other type.
    vol_pct: float | None = None
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
    elif override_type == "reduced_volume":
        # Volume window — carries no locale; requires a retained fraction in (0,1).
        unavail = None
        away = None
        if volume_pct is None:
            raise EventWindowError("reduced_volume requires a volume_pct in (0, 1)")
        try:
            vol_pct = float(volume_pct)
        except (TypeError, ValueError):
            raise EventWindowError(f"volume_pct {volume_pct!r} is not a number")
        if not 0.0 < vol_pct < 1.0:
            raise EventWindowError(
                f"volume_pct must be strictly between 0 and 1 (got {vol_pct})"
            )
    else:
        # indoor_only / no_training carry no locale and no volume_pct — clear any
        # stray value so the stored row can't imply something it doesn't mean.
        unavail = None
        away = None
    db.execute(
        "INSERT INTO athlete_event_windows "
        "  (user_id, start_date, end_date, override_type, unavailable_locale, "
        "   away_locale, brought_craft, volume_pct, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, start_date, end_date, override_type, unavail, away,
            (",".join(crafts) or None), vol_pct, notes,
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
