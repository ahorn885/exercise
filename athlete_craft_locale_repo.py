"""athlete_craft_locale repository — Event Windows Slice 4 (#581 WS-H), the (b)
surface.

A standing "this craft is kept at this locale" association — a bike at the
parents' place, a kayak at the lake cabin. Athlete-scoped. Distinct from the (c)
brought-craft set on an away window (`athlete_event_windows_repo`): (b) needs no
per-trip re-declaration, it applies whenever that locale falls in the active
away cluster.

Plan-gen reads the whole map via `load_craft_locales` and, for an `away`
segment, unions the crafts kept at any locale in the destination's radius
cluster into that segment's `owned_crafts` (alongside the window's brought set) —
`layer4.orchestrator._build_event_window_overlay`.

Convention (mirrors `athlete_crafts_repo`): values are the snake_case craft
slugs (`mountain_bike`, `kayak`) of the closed `BIKE_TYPES ∪ PADDLE_CRAFT_TYPES`
enum; `locale` is one of the athlete's `locale_profiles.locale` slugs. Both are
app-validated (the project's no-DB-CHECK convention) — an unknown slug or a
foreign locale is rejected, nothing written. Replace-all per locale on write.
"""
from __future__ import annotations

from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES

_CRAFT_SLUGS: tuple[str, ...] = (*BIKE_TYPES, *PADDLE_CRAFT_TYPES)


class CraftLocaleError(ValueError):
    """A submitted craft↔locale association failed an app-layer constraint."""


def load_craft_locales(db, user_id: int) -> dict[str, list[str]]:
    """`{locale: [craft_slug, ...]}` for the athlete — crafts emitted in
    `_CRAFT_SLUGS` order per locale for a stable read. Empty dict when none."""
    rows = db.execute(
        "SELECT locale, craft_slug FROM athlete_craft_locale "
        "WHERE user_id = ? ORDER BY locale, craft_slug",
        (user_id,),
    ).fetchall()
    by_locale: dict[str, set[str]] = {}
    for row in rows:
        by_locale.setdefault(row["locale"], set()).add(row["craft_slug"])
    return {
        loc: [s for s in _CRAFT_SLUGS if s in crafts]
        for loc, crafts in by_locale.items()
    }


def replace_craft_locale(db, user_id: int, locale: str, crafts: list[str]) -> None:
    """Replace the crafts kept at `locale` with `crafts` (replace-all per locale;
    an empty list clears the locale). Raises `CraftLocaleError` (writing nothing)
    on an unknown craft slug or a locale the athlete doesn't own. Caller commits."""
    loc = (locale or "").strip()
    if not loc:
        raise CraftLocaleError("a locale is required")
    if not _locale_exists(db, user_id, loc):
        raise CraftLocaleError(f"{loc!r} is not one of your saved locales")
    chosen = _validate(crafts)
    db.execute(
        "DELETE FROM athlete_craft_locale WHERE user_id = ? AND locale = ?",
        (user_id, loc),
    )
    for slug in chosen:
        db.execute(
            "INSERT INTO athlete_craft_locale (user_id, craft_slug, locale) "
            "VALUES (?, ?, ?)",
            (user_id, slug, loc),
        )


def delete_craft_locale(db, user_id: int, locale: str) -> None:
    """Clear all crafts kept at `locale` (user-scoped). Caller commits."""
    db.execute(
        "DELETE FROM athlete_craft_locale WHERE user_id = ? AND locale = ?",
        (user_id, (locale or "").strip()),
    )


def evict_plan_caches_on_craft_locale_change(db, user_id: int) -> None:
    """A craft↔locale change alters which crafts an away segment resolves with,
    so invalidate the two synthesis entry points that consume the away env.
    Standing athlete data (not a window field) → eviction-on-write is the cache
    story (it is NOT folded into `compute_event_windows_hash`), mirroring how the
    owned-craft store relies on `evict_layer1_on_crafts_change`. Scoped to
    plan_create/plan_refresh like the event-windows eviction."""
    from layer4.cache import Layer4Cache
    from layer4.cache_postgres import PostgresCacheBackend

    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    cache.invalidate_user(
        user_id,
        layer="craft_locale",
        entry_points=("plan_create", "plan_refresh"),
    )


def _validate(values: list[str]) -> list[str]:
    """De-dupe + reject unknown slugs; emit in `_CRAFT_SLUGS` order. Mirrors
    `athlete_crafts_repo._validate`."""
    chosen = {v for v in (values or []) if v}
    unknown = chosen - set(_CRAFT_SLUGS)
    if unknown:
        raise CraftLocaleError(f"unknown craft(s): {', '.join(sorted(unknown))}")
    return [s for s in _CRAFT_SLUGS if s in chosen]


def _locale_exists(db, user_id: int, locale: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    ).fetchone()
    return row is not None
