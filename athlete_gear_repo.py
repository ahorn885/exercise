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

from athlete import BIKE_TYPES, CRAFT_LABELS, PADDLE_CRAFT_TYPES
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
#   - DISCIPLINE-UNLOCKING gear (bike/paddle/ski/snow/climb/alpine) — aliases
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
    # #884 slice 4b — the climbing gear kind is `climb`, aligned with the modality
    # vocab (`modality_groups.group_kind`), not the divergent `climbing` (Andy
    # 2026-06-29). ski/snow/alpine keep their finer gear-family names (no modality
    # equivalent — collapsing them would let snowshoes proxy for skis).
    "climbing_gear": "climb",
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

# Discipline-unlocking GEAR-TOGGLE kinds — the slice-4b capture surface owns this
# slice of the store. Crafts (bike/paddle) have their own owned-craft picker; swim
# gear is drill-gating (slice 6) — neither is captured here. These four kinds are
# the owned-gear toggles that alias to a discipline in `gear_discipline_aliases`
# (ski/snow/climb/alpine), so capturing them un-starves the cascade's gear gate
# (#298). The capture writes `athlete_gear`; nothing READS the toggle kinds until
# the slice-4b cascade extension lands (staged, like the slice-3 store itself).
_GEAR_TOGGLE_KINDS: frozenset[str] = frozenset({"ski", "snow", "climb", "alpine"})

# Craft kinds — bike/paddle, the slice the owned-craft picker (and the craft
# baselines) own. Together with `_GEAR_TOGGLE_KINDS` these are the six kinds the
# unified "Your gear" registry (slice 6a) covers; swim is excluded (drill-gating,
# no label/capture surface yet — see `load_gear_registry`).
_CRAFT_KINDS: frozenset[str] = frozenset({"bike", "paddle"})

# Presentation labels for the gear-toggle picker — the analogue of `athlete.
# CRAFT_LABELS` for the bike/paddle picker. Slugs are the stored + aliased
# `gear_id` keys (GEAR_REGISTRY); labels are presentation-only. Covers exactly the
# `_GEAR_TOGGLE_KINDS` slugs (guarded in lockstep by the repo test).
GEAR_TOGGLE_LABELS: dict[str, str] = {
    "classic_xc_ski": "Classic XC skis",
    "skate_xc_ski": "Skate XC skis",
    "rollerskis": "Rollerskis",
    "snowshoes": "Snowshoes",
    "climbing_gear": "Climbing gear (rope, harness, protection)",
    "mountaineering": "Mountaineering kit (ice axe, crampons)",
    "skimo_at": "Skimo / AT setup",
}


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


def replace_owned_gear_for_kinds(
    db, user_id: int, owned: dict[str, str], group_kinds: set[str]
) -> None:
    """Replace the athlete's owned gear WITHIN `group_kinds` only — gear of other
    kinds is preserved (#884 slice 4).

    Each capture surface owns a slice of the unified store: crafts → {'bike',
    'paddle'}, gear toggles → {'ski','snow','climb','alpine'} (slice 4b), swim
    → {'swim'} (slice 6). This lets the per-surface forms write their own kinds
    without clobbering the others, while keeping one store the feasibility cascade
    reads (slice 4a). `owned` maps `gear_id → access`; every gear_id must be in
    `GEAR_REGISTRY`, carry a `group_kind` in `group_kinds`, and every access in
    `_ACCESS_VALUES`, else `GearSelectionError` is raised and nothing is written.
    Caller commits.
    """
    validated = _validate_owned(owned)
    off_surface = sorted(g for g in validated if GEAR_REGISTRY[g] not in group_kinds)
    if off_surface:
        raise GearSelectionError(
            f"gear_id(s) outside this surface's kinds {sorted(group_kinds)}: "
            f"{', '.join(off_surface)}"
        )
    kinds = sorted(group_kinds)
    placeholders = ",".join("?" for _ in kinds)
    db.execute(
        f"DELETE FROM athlete_gear WHERE user_id = ? AND group_kind IN ({placeholders})",
        (user_id, *kinds),
    )
    for gid in _GEAR_IDS:
        if gid not in validated:
            continue
        db.execute(
            "INSERT INTO athlete_gear (user_id, gear_id, group_kind, access) "
            "VALUES (?, ?, ?, ?)",
            (user_id, gid, GEAR_REGISTRY[gid], validated[gid]),
        )


# ─── gear-toggle capture surface (slice 4b) ──────────────────────────────────
# The profile gear-tab picker for the discipline-unlocking owned-gear toggles
# (ski/snow/climb/alpine). Mirrors the owned-craft picker
# (`athlete_crafts_repo.load_craft_catalog` + `parse`-style helpers): catalog →
# checkboxes, parse → `{gear_id: 'own'}`, write via `replace_owned_gear_for_kinds`
# scoped to `_GEAR_TOGGLE_KINDS`. Replace-all within those kinds — an unchecked
# box means "not owned", same as the craft picker (no explicit-False rows).

def load_gear_toggle_catalog() -> list[dict]:
    """The gear-toggle picker catalog — `[{'slug', 'label'}, …]` in `_GEAR_IDS`
    order, filtered to the discipline-unlocking `_GEAR_TOGGLE_KINDS`. Static (the
    closed §5.5 keyspace + `GEAR_TOGGLE_LABELS`), mirroring `load_craft_catalog`."""
    return [
        {"slug": gid, "label": GEAR_TOGGLE_LABELS[gid]}
        for gid in _GEAR_IDS
        if GEAR_REGISTRY[gid] in _GEAR_TOGGLE_KINDS
    ]


def get_owned_gear_toggles(db, user_id: int) -> list[str]:
    """The athlete's currently-owned gear-toggle slugs (the `_GEAR_TOGGLE_KINDS`
    slice of `athlete_gear`), in `_GEAR_IDS` order — the checked-state source for
    the picker. Empty list when none."""
    return [
        g["gear_id"]
        for g in get_athlete_gear(db, user_id)
        if g["group_kind"] in _GEAR_TOGGLE_KINDS
    ]


# #884 slice 4b PR-3 — the `gear_id → sport_specific_gear_toggles.toggle_name`
# bridge (design v3 §5.5 is the source). The two keyspaces differ — the unified
# store keys on stable snake_case `gear_id` (GEAR_REGISTRY) while Layer 2C's
# `cluster_gear_toggle_states` / `toggle_defs` key on the catalog's free-text
# `toggle_name` — so the 2C gear-toggle gate can't read `athlete_gear` without
# this map. Covers exactly the discipline-unlocking toggles that have a live
# `sport_specific_gear_toggles` row; `rollerskis` is intentionally absent (new
# gear, Decision 10 — no toggle row; its D-028 feasibility is the cascade's job
# via `gear_discipline_aliases`, and it gates nothing in 2C). Pinned by the repo
# test against the live catalog's toggle_name strings.
GEAR_TOGGLE_NAMES: dict[str, str] = {
    "classic_xc_ski": "Classic XC ski setup",
    "skate_xc_ski": "Skate XC ski setup",
    "snowshoes": "Snowshoeing setup",
    "climbing_gear": "Climbing gear",
    "mountaineering": "Mountaineering",
    "skimo_at": "Skimo / AT setup",
}


def owned_gear_toggle_states(owned_gear_ids) -> dict[str, bool]:
    """Map the athlete's owned gear_ids → `{toggle_name: True}` for Layer 2C's
    `cluster_gear_toggle_states` (#884 slice 4b PR-3 — closes the last #298
    consumer).

    Pure derivation off `Layer1Payload.owned_gear` (no new query — rides the
    layer1_hash, like the cascade's gear read). Only owned gear-toggle gear_ids
    bridged by `GEAR_TOGGLE_NAMES` contribute a key; the 2C consumer treats every
    absent toggle as OFF, so unowned/unbridged gear (incl. rollerskis, bike/paddle
    crafts) is correctly omitted. Owned gear is always ON (the store has no
    explicit-False rows — an unchecked box is simply not stored)."""
    return {
        GEAR_TOGGLE_NAMES[gid]: True
        for gid in owned_gear_ids
        if gid in GEAR_TOGGLE_NAMES
    }


def parse_gear_toggle_form(form) -> dict[str, str]:
    """Coerce a POST form into `{gear_id: 'own'}` for the checked gear toggles.

    Checkboxes use `gear__<gear_id>`; presence means owned, absence means not
    owned (replace-all within `_GEAR_TOGGLE_KINDS`, so unchecked rows are simply
    omitted — no explicit-False persistence, unlike the skill toggles). Only
    catalog slugs are considered, so a malformed POST can't inject an unknown or
    off-surface gear_id."""
    return {
        item["slug"]: "own"
        for item in load_gear_toggle_catalog()
        if form.get(f"gear__{item['slug']}")
    }


# ─── unified gear registry + "Your gear" surface (slice 6a) ──────────────────
# One ordered catalog keyed by the §5.5 `gear_id`, folding the owned-craft
# catalog (bike/paddle, labels from `athlete.CRAFT_LABELS`) and the gear-toggle
# catalog (ski/snow/climb/alpine, labels from `GEAR_TOGGLE_LABELS`) into a single
# source the consolidated "Your gear" picker + validator both read (design v3
# §10). Each row captures `access` ('own' | 'access') — the unified store is the
# access authority for ALL kinds (crafts are kept in lockstep in `athlete_gear`
# by `athlete_crafts_repo.replace_athlete_crafts`; their baseline CSVs still carry
# the full available set, own ∪ access, which feeds Layer 1 substitution — that
# read doesn't distinguish access). NOT a new Layer-0 surface (D2 — the two
# catalogs already exist; no digest bump). Swim gear is excluded: it has no
# presentation label and no capture surface yet (drill-gating, separate from the
# discipline-unlocking registry).

# group_kind → display heading for the grouped picker. Presentation-only (not
# gear vocabulary); the ordering here is the render order of the sections.
_GROUP_KIND_LABELS: dict[str, str] = {
    "bike": "Bikes",
    "paddle": "Paddle craft",
    "ski": "Skis & rollerskis",
    "snow": "Snow",
    "climb": "Climbing",
    "alpine": "Mountaineering / ski-mo",
}


def load_gear_registry() -> list[dict]:
    """The unified picker/validator catalog — `[{'gear_id', 'group_kind', 'label',
    'source'}, …]` in `_GEAR_IDS` order, folding the craft + gear-toggle catalogs.
    `source` is 'craft' (bike/paddle) or 'toggle' (ski/snow/climb/alpine); swim
    gear is omitted (no label / no capture surface). Static (the closed §5.5
    keyspace + the two label maps)."""
    out: list[dict] = []
    for gid in _GEAR_IDS:
        kind = GEAR_REGISTRY[gid]
        if kind in _CRAFT_KINDS:
            out.append({"gear_id": gid, "group_kind": kind,
                        "label": CRAFT_LABELS[gid], "source": "craft"})
        elif kind in _GEAR_TOGGLE_KINDS:
            out.append({"gear_id": gid, "group_kind": kind,
                        "label": GEAR_TOGGLE_LABELS[gid], "source": "toggle"})
    return out


def load_gear_registry_grouped() -> list[dict]:
    """The registry grouped by `group_kind` for the "Your gear" picker —
    `[{'group_kind', 'label', 'rows': [{'gear_id', 'label'}, …]}, …]` in
    `_GROUP_KIND_LABELS` (render) order, rows in `_GEAR_IDS` order. Empty groups
    are omitted. (`rows`, not `items` — Jinja resolves `.items` to the dict
    method, not the key.)"""
    by_kind: dict[str, list[dict]] = {}
    for entry in load_gear_registry():
        by_kind.setdefault(entry["group_kind"], []).append(
            {"gear_id": entry["gear_id"], "label": entry["label"]}
        )
    return [
        {"group_kind": kind, "label": _GROUP_KIND_LABELS[kind], "rows": by_kind[kind]}
        for kind in _GROUP_KIND_LABELS
        if kind in by_kind
    ]


def get_gear_access_map(db, user_id: int) -> dict[str, str]:
    """`{gear_id: access}` across all registry kinds — the checked-state source
    for the "Your gear" picker. Reads `athlete_gear` (crafts are synced there by
    `replace_athlete_crafts`, so this covers crafts + gear toggles uniformly)."""
    return {g["gear_id"]: g["access"] for g in get_athlete_gear(db, user_id)}


def parse_gear_registry_form(form) -> dict[str, str]:
    """Coerce a "Your gear" POST into `{gear_id: access}` for the chosen rows.

    Each registry row posts `gear__<gear_id>` ∈ {'', 'own', 'access'}; '' (or an
    absent field) means "not owned" and is omitted (replace-all). Only registry
    gear_ids with an in-set access value are kept, so a malformed POST can't inject
    an unknown gear_id, an off-registry kind (e.g. swim), or a junk access token."""
    out: dict[str, str] = {}
    for entry in load_gear_registry():
        val = (form.get(f"gear__{entry['gear_id']}") or "").strip()
        if val in _ACCESS_VALUES:
            out[entry["gear_id"]] = val
    return out


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
