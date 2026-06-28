"""athlete_gear repository — #884 unified gear/craft model, slice 3.

The public-schema store for the athlete's owned **gear/craft** — the one
concept that merges the two craft families (bikes / boats, previously the
`discipline_baseline_{cycling,paddling}` CSV columns) with the owned gear
toggles (ski / climbing / mountaineering / snowshoe / skimo setups + rollerskis,
which had *no* store before #884). Collapses `athlete_crafts_repo` (owned set) +
`athlete_craft_locale_repo` (per-locale availability) onto the dedicated
`athlete_gear` / `athlete_gear_locale` tables (design v3 §5.1/§5.2).

STAGING (design v3 §15): the old craft path stays live. Nothing reads this store
yet — the orchestrator feasibility cascade cuts over onto `athlete_gear` +
`layer0.gear_discipline_aliases` in slice 4, and first capture (the "Your gear"
surface) is slice 6. Slice 3 builds the table, backfills it from the live craft
data (init_db), and lands this read/write surface so 4 and 6 have it.

Convention (mirrors the two craft repos): values are the snake_case `gear_id`
keys of the closed §5.5 keyspace (`GEAR_REGISTRY` below) — the same keys
`layer0.gear_discipline_aliases` (migration 0024) and the picker share. `locale`
is one of the athlete's `locale_profiles.locale` slugs. Both are app-validated
(the project's no-DB-CHECK convention) — an unknown `gear_id`, an out-of-set
`access`, or a foreign locale is rejected and nothing is written.
"""
from __future__ import annotations

from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES
from layer4.cache import Layer4Cache
from layer4.cache_invalidation import evict_on_layer_change
from layer4.cache_postgres import PostgresCacheBackend

# §5.5 `gear_id` keyspace — the closed, stable, snake_case key set shared by
# `athlete_gear`, `layer0.gear_discipline_aliases`, `athlete_gear_locale`,
# `brought_gear`, and the picker. `gear_id → group_kind`, the substitute-grouping
# discriminator stored denormalized on `athlete_gear` so read paths route without
# a catalog join (§5.1). Craft slugs (bike/paddle) reuse the existing closed
# craft enums (single source — no drift with the craft pickers); the owned-gear
# toggles get their stable slugs here. `rollerskis` is the one new entry
# (Decision 10).
#
# Two kinds of gear share this keyspace:
#   - DISCIPLINE-UNLOCKING gear (bike/paddle/ski/snow/climbing/alpine) — aliases
#     to disciplines in layer0.gear_discipline_aliases (migration 0024). Guarded
#     in lockstep by test_athlete_gear_repo.test_registry_matches_layer0_keyspace.
#   - DRILL-GATING swim gear (group_kind 'swim') — #884 slice 3b / Decision 11.
#     Owned portable gear that gates cardio_drills[] pool membership (pull buoy →
#     pull set, kickboard → kick set), NEVER discipline feasibility (D-004 stays
#     feasible on water) — so it has NO gear_discipline_aliases row. The gate
#     reads layer0.cardio_drill_gear_requirements (migration 0025). `paddles` +
#     `fins` are capturable owned gear with no gated drill in the active catalog
#     yet (Andy 2026-06-23 — seed the vocab; the drills can map to them later).
GEAR_REGISTRY: dict[str, str] = {
    **{slug: "bike" for slug in BIKE_TYPES},
    **{slug: "paddle" for slug in PADDLE_CRAFT_TYPES},
    "classic_xc_ski": "ski",
    "skate_xc_ski": "ski",
    "rollerskis": "ski",
    "snowshoes": "snow",
    "climbing_gear": "climbing",
    "mountaineering": "alpine",
    "skimo_at": "alpine",
    # Swim gear — drill-gating, non-discipline-unlocking (slice 3b).
    "pull_buoy": "swim",
    "kickboard": "swim",
    "paddles": "swim",
    "fins": "swim",
}

# Stable ordering for deterministic reads + a stable INSERT sequence on write
# (owned gear feeds Layer 1 once the cascade cuts over — slice 4 — so the read
# order must be deterministic for the Layer 1 hash, the same reason the craft
# repos emit in enum order).
_GEAR_IDS: tuple[str, ...] = tuple(GEAR_REGISTRY)

# §5.1 / §8 — `access` closed set.
_ACCESS_VALUES: tuple[str, ...] = ("own", "access")


class GearSelectionError(ValueError):
    """A submitted gear_id / access / gear↔locale value failed an app-layer
    constraint (unknown gear_id, out-of-set access, or a foreign locale)."""


# ─── owned gear (athlete_gear) ───────────────────────────────────────────────

def get_athlete_gear(db, user_id: int) -> list[dict]:
    """The athlete's owned gear/craft as `[{'gear_id', 'group_kind', 'access'},
    …]`, emitted in `_GEAR_IDS` order for a stable read. Empty list when none."""
    rows = db.execute(
        "SELECT gear_id, group_kind, access FROM athlete_gear WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    by_id = {row["gear_id"]: row for row in rows}
    return [
        {
            "gear_id": gid,
            "group_kind": by_id[gid]["group_kind"],
            "access": by_id[gid]["access"],
        }
        for gid in _GEAR_IDS
        if gid in by_id
    ]


def replace_athlete_gear(db, user_id: int, owned: dict[str, str]) -> None:
    """Replace the athlete's owned gear/craft set (replace-all).

    `owned` maps `gear_id → access` ('own' | 'access'); an empty dict clears the
    athlete's gear. Every `gear_id` must be in `GEAR_REGISTRY` and every `access`
    in `_ACCESS_VALUES`, else `GearSelectionError` is raised and nothing is
    written. `group_kind` is derived from `GEAR_REGISTRY` (stored denormalized).
    Caller commits.
    """
    validated = _validate_owned(owned)
    db.execute("DELETE FROM athlete_gear WHERE user_id = ?", (user_id,))
    for gid in _GEAR_IDS:
        if gid not in validated:
            continue
        db.execute(
            "INSERT INTO athlete_gear (user_id, gear_id, group_kind, access) "
            "VALUES (?, ?, ?, ?)",
            (user_id, gid, GEAR_REGISTRY[gid], validated[gid]),
        )


def evict_layer1_on_gear_change(db, user_id: int) -> None:
    """Owned gear feeds the feasibility cascade (Layer 1 baselines, once slice 4
    re-homes `_collect_athlete_crafts` onto `athlete_gear`), so a save invalidates
    every Layer 4 entry point + both Layer 3 wrappers per the Layer 1 eviction
    policy — craft + gear sharing one eviction story (design v3 §9). Mirrors
    `athlete_crafts_repo.evict_layer1_on_crafts_change`."""
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    evict_on_layer_change(cache, user_id, "layer1")


# ─── per-locale availability (athlete_gear_locale) ───────────────────────────

def load_gear_locales(db, user_id: int) -> dict[str, list[str]]:
    """`{locale: [gear_id, …]}` for the athlete — gear emitted in `_GEAR_IDS`
    order per locale for a stable read. Empty dict when none. Mirrors
    `athlete_craft_locale_repo.load_craft_locales`."""
    rows = db.execute(
        "SELECT locale, gear_id FROM athlete_gear_locale "
        "WHERE user_id = ? ORDER BY locale, gear_id",
        (user_id,),
    ).fetchall()
    by_locale: dict[str, set[str]] = {}
    for row in rows:
        by_locale.setdefault(row["locale"], set()).add(row["gear_id"])
    return {
        loc: [g for g in _GEAR_IDS if g in gear]
        for loc, gear in by_locale.items()
    }


def replace_gear_locale(db, user_id: int, locale: str, gear_ids: list[str]) -> None:
    """Replace the gear kept at `locale` with `gear_ids` (replace-all per locale;
    an empty list clears the locale). Raises `GearSelectionError` (writing nothing)
    on an unknown gear_id or a locale the athlete doesn't own. Caller commits.
    Mirrors `athlete_craft_locale_repo.replace_craft_locale`."""
    loc = (locale or "").strip()
    if not loc:
        raise GearSelectionError("a locale is required")
    if not _locale_exists(db, user_id, loc):
        raise GearSelectionError(f"{loc!r} is not one of your saved locales")
    chosen = _validate_gear_ids(gear_ids)
    db.execute(
        "DELETE FROM athlete_gear_locale WHERE user_id = ? AND locale = ?",
        (user_id, loc),
    )
    for gid in chosen:
        db.execute(
            "INSERT INTO athlete_gear_locale (user_id, gear_id, locale) "
            "VALUES (?, ?, ?)",
            (user_id, gid, loc),
        )


def delete_gear_locale(db, user_id: int, locale: str) -> None:
    """Clear all gear kept at `locale` (user-scoped). Caller commits."""
    db.execute(
        "DELETE FROM athlete_gear_locale WHERE user_id = ? AND locale = ?",
        (user_id, (locale or "").strip()),
    )


def evict_plan_caches_on_gear_locale_change(db, user_id: int) -> None:
    """A gear↔locale change alters which gear an away segment resolves with, so
    invalidate the two synthesis entry points that consume the away env. Standing
    athlete data (not a window field) → eviction-on-write is the cache story (not
    folded into `compute_event_windows_hash`). Mirrors
    `athlete_craft_locale_repo.evict_plan_caches_on_craft_locale_change`."""
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    cache.invalidate_user(
        user_id,
        layer="gear_locale",
        entry_points=("plan_create", "plan_refresh"),
    )


# ─── validation ──────────────────────────────────────────────────────────────

def _validate_owned(owned: dict[str, str]) -> dict[str, str]:
    """Reject unknown gear_ids or out-of-set access; return the validated map.
    Nothing is written if this raises."""
    unknown = set(owned or {}) - set(GEAR_REGISTRY)
    if unknown:
        raise GearSelectionError(f"unknown gear_id(s): {', '.join(sorted(unknown))}")
    bad_access = {a for a in (owned or {}).values() if a not in _ACCESS_VALUES}
    if bad_access:
        raise GearSelectionError(f"unknown access value(s): {', '.join(sorted(bad_access))}")
    return dict(owned or {})


def _validate_gear_ids(values: list[str]) -> list[str]:
    """De-dupe + reject unknown gear_ids; emit in `_GEAR_IDS` order. Mirrors
    `athlete_craft_locale_repo._validate`."""
    chosen = {v for v in (values or []) if v}
    unknown = chosen - set(GEAR_REGISTRY)
    if unknown:
        raise GearSelectionError(f"unknown gear_id(s): {', '.join(sorted(unknown))}")
    return [g for g in _GEAR_IDS if g in chosen]


def _locale_exists(db, user_id: int, locale: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    ).fetchone()
    return row is not None
