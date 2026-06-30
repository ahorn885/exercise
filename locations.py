"""Authoritative locations / equipment-pool domain logic (Track 1).

ONE definition of "what equipment is effective at a locale" and "which
locales form the athlete's training cluster", shared by the plan-gen
orchestrator, the locale UI, and the references view. Replaces the divergent
legacy copies — `orchestrator._q_locale_equipment_pool` (snake_case
`public.equipment_items.tag` over the legacy `locale_equipment` table) vs
`routes/locales._effective_equipment` (the new gym_profiles model) — that
disagreed by construction. That disagreement was the pv=59
`equipment_unavailable` root cause.

Equipment is stored and returned as layer0 canonical names (e.g. "Barbell",
"Squat rack") — the same vocabulary Layer 2C resolves
`exercises.equipment_required` against. No snake_case→canonical conversion:
the canonical vocabulary is authoritative end to end
(Locations_Consolidation_Design_v1 §2.8).
"""

from __future__ import annotations

import json
import math
from typing import Any

# §5.2 — cluster = home + every saved locale within this great-circle radius
# of home. Reuses the D-59 nearby radius (mapbox_client.DEFAULT_RADIUS_KM =
# 26.2 mi / 42.2 km).
_CLUSTER_RADIUS_KM = 42.2


class PrimaryLocaleMissing(Exception):
    """Raised when an athlete has no `preferred` (home) locale. Home is a
    required invariant (§10) — onboarding sets one and the first locale an
    athlete creates auto-flags home — so this is a guarded can't-happen
    surfaced rather than silently tolerated."""


def primary_locale(db: Any, user_id: int) -> str:
    """Return the athlete's home locale slug — the `locale_profiles` row with
    `preferred = TRUE` (§5.1). Replaces the hardcoded `locale = 'home'`
    convention. Raises PrimaryLocaleMissing when none is set."""
    row = db.execute(
        "SELECT locale FROM locale_profiles WHERE user_id = ? AND preferred LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        raise PrimaryLocaleMissing(
            f"user_id={user_id} has no locale_profiles row with preferred=TRUE"
        )
    return row["locale"]


def disputed_equipment_tags(db: Any, gym_profile_id: int) -> set[str]:
    """The set of equipment tags currently DISPUTED on a shared profile — the
    union of every open correction proposal's `removes` on
    `gym_profiles.disputed_items` (#971 Slice 3 records these as a JSON list of
    `{by, adds, removes, at}` objects).

    A disputed tag is one a peer has flagged as wrong on the shared profile; per
    D-60 §5 it is treated as not-available for plan generation until an admin
    reviews the proposal. Only `removes` matter — a proposal's `adds` aren't in
    the shared set until approved, so they never drive plan-gen.

    Tolerant of NULL / empty / malformed `disputed_items` (returns set()). Mirrors
    the inline `gym_profiles.equipment` parse above — same tolerance, same module
    (no `routes/locales` import, so no circular dependency)."""
    row = db.execute(
        "SELECT disputed_items FROM gym_profiles WHERE id = ?",
        (gym_profile_id,),
    ).fetchone()
    if row is None or not row["disputed_items"]:
        return set()
    try:
        proposals = json.loads(row["disputed_items"])
    except (ValueError, TypeError):
        return set()
    disputed: set[str] = set()
    for p in proposals:
        if isinstance(p, dict):
            disputed.update(t for t in (p.get("removes") or []) if isinstance(t, str))
    return disputed


def locale_effective_tags(
    db: Any, user_id: int, locale: str, *, exclude_disputed: bool = False
) -> set[str]:
    """The authoritative effective-equipment set at one locale, as layer0
    canonical names. `(shared ∪ adds) ∖ removes` (§4):

      - shared  = the linked `gym_profiles.equipment` JSON (canonical names),
      - adds    = this athlete's `locale_equipment_overrides` action='add',
      - removes = ditto action='remove'.

    Empty set when the locale links no gym profile and carries no overrides.

    `exclude_disputed=True` (the plan-gen path only — #971 D-60 §5): subtract the
    shared profile's DISPUTED tags before the override math, so a tag a peer
    flagged as wrong stops driving plan prescriptions while it's under admin
    review. Resolves `((shared − disputed) ∪ adds) − removes`, so an athlete who
    personally re-added the tag keeps it (a personal override is authoritative
    for that athlete; it beats a peer's provisional dispute). The UI / references
    / override-save / legacy-coaching callers take the default (False) and are
    byte-identical to before — only the locale's own equipment view stays the
    real shared set."""
    shared: set[str] = set()
    prof = db.execute(
        "SELECT gym_profile_id FROM locale_profiles "
        "WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    ).fetchone()
    if prof is not None and prof["gym_profile_id"]:
        gym = db.execute(
            "SELECT equipment FROM gym_profiles WHERE id = ?",
            (prof["gym_profile_id"],),
        ).fetchone()
        if gym is not None and gym["equipment"]:
            try:
                shared = {
                    t for t in json.loads(gym["equipment"]) if isinstance(t, str)
                }
            except (ValueError, TypeError):
                shared = set()
        if exclude_disputed:
            disputed = disputed_equipment_tags(db, prof["gym_profile_id"])
            if disputed & shared:
                # Rule #15: a "why did the plan stop prescribing X" question must
                # be answerable from /admin/logs alone — log the inputs + the
                # tags the dispute actually removed from this locale's pool.
                print(
                    f"locale_effective_tags: user_id={user_id} locale={locale!r} "
                    f"gym_profile_id={prof['gym_profile_id']} disputed-excluded "
                    f"{sorted(disputed & shared)} (plan-gen path)"
                )
            shared = shared - disputed
    rows = db.execute(
        "SELECT equipment_tag, action FROM locale_equipment_overrides "
        "WHERE user_id = ? AND locale = ?",
        (user_id, locale),
    ).fetchall()
    adds = {r["equipment_tag"] for r in rows if r["action"] == "add"}
    removes = {r["equipment_tag"] for r in rows if r["action"] == "remove"}
    return (shared | adds) - removes


def cluster_locale_ids(
    db: Any, user_id: int, anchor_locale: str | None = None
) -> list[str]:
    """The athlete's training cluster: the anchor locale + every saved locale
    within `_CLUSTER_RADIUS_KM` of the anchor by lat/lng (§5.2). The anchor is
    always first. Manual-entry locales without coordinates are excluded from the
    radius sweep (the anchor itself is included even when it lacks coords).

    `anchor_locale=None` → the anchor is the athlete's `preferred` home locale
    (the default plan cluster; byte-identical to the pre-Slice-2 signature). A
    supplied `anchor_locale` → the radius sweep re-anchors at that locale (Event
    Windows Slice 2 `away` — the destination's own cluster, same logic as home).
    Returns [] only when the anchor row can't be resolved (callers guard)."""
    if anchor_locale is None:
        home = db.execute(
            "SELECT locale, lat, lng FROM locale_profiles "
            "WHERE user_id = ? AND preferred LIMIT 1",
            (user_id,),
        ).fetchone()
    else:
        home = db.execute(
            "SELECT locale, lat, lng FROM locale_profiles "
            "WHERE user_id = ? AND locale = ? LIMIT 1",
            (user_id, anchor_locale),
        ).fetchone()
    if home is None:
        print(
            f"cluster_locale_ids: user_id={user_id} anchor={anchor_locale or 'home'} "
            f"unresolvable → cluster=[] (feasibility resolution will be skipped)"
        )
        return []
    ids = [home["locale"]]
    if home["lat"] is None or home["lng"] is None:
        # Rule #15 observability: an anchor without coords yields a single-locale
        # cluster (radius sweep skipped) that looks normal downstream but can
        # starve the feasibility cascade of terrain/equipment at other locales.
        print(
            f"cluster_locale_ids: user_id={user_id} anchor={home['locale']!r} has "
            f"no coords → cluster=[anchor] only (radius sweep skipped)"
        )
        return ids
    home_lat, home_lng = float(home["lat"]), float(home["lng"])
    others = db.execute(
        "SELECT locale, lat, lng FROM locale_profiles "
        "WHERE user_id = ? AND locale != ? AND lat IS NOT NULL AND lng IS NOT NULL",
        (user_id, home["locale"]),
    ).fetchall()
    # Distance-sorted, NEAREST first (#624): the feasibility cascade resolves the
    # FIRST cluster locale carrying a required terrain at each tier, so ordering
    # the cluster by distance makes "first satisfying locale" mean "nearest
    # satisfying locale" — the deterministic venue pick. (Wires the haversine sort
    # `resolve_terrain_feasibility` long flagged as a stand-in.) Slug breaks
    # distance ties for a stable order (the cache key reads this order).
    within: list[tuple[float, str]] = []
    for r in others:
        d = _haversine_km(home_lat, home_lng, float(r["lat"]), float(r["lng"]))
        if d <= _CLUSTER_RADIUS_KM:
            within.append((d, r["locale"]))
    within.sort(key=lambda t: (t[0], t[1]))
    ids.extend(locale for _d, locale in within)
    return ids


def _humanize_locale_slug(slug: str) -> str:
    """Fallback display label for a locale that carries no `locale_name`
    (`'509_williams_avenue'` → `'509 Williams Avenue'`)."""
    return slug.replace("_", " ").title()


def cluster_locale_meta(
    db: Any, user_id: int, cluster: list[str], anchor_locale: str | None = None
) -> dict[str, dict[str, Any]]:
    """Display metadata per cluster locale: its human `name`
    (`locale_profiles.locale_name`, falling back to a humanized slug) and its
    great-circle `distance_km` from the cluster anchor (the first cluster locale
    by default — home).

    Feeds the deterministic venue naming in the synthesis feasibility block
    (#624 / #618-7) so the synthesizer cites the athlete's real saved locales by
    NAME + distance instead of inventing a venue or mangling a slug
    ('509 Williams Avenue' vs 'Williams'). `distance_km` is None when either the
    anchor or the locale carries no coordinates (manual-entry locales)."""
    anchor = anchor_locale or (cluster[0] if cluster else None)
    alat = alng = None
    if anchor is not None:
        arow = db.execute(
            "SELECT lat, lng FROM locale_profiles "
            "WHERE user_id = ? AND locale = ? LIMIT 1",
            (user_id, anchor),
        ).fetchone()
        if arow is not None and arow["lat"] is not None and arow["lng"] is not None:
            alat, alng = float(arow["lat"]), float(arow["lng"])
    out: dict[str, dict[str, Any]] = {}
    for locale in cluster:
        row = db.execute(
            "SELECT locale_name, lat, lng FROM locale_profiles "
            "WHERE user_id = ? AND locale = ? LIMIT 1",
            (user_id, locale),
        ).fetchone()
        name = (row["locale_name"] if row and row["locale_name"] else "") or (
            _humanize_locale_slug(locale)
        )
        dist: float | None = None
        if (
            alat is not None
            and row is not None
            and row["lat"] is not None
            and row["lng"] is not None
        ):
            dist = _haversine_km(alat, alng, float(row["lat"]), float(row["lng"]))
        out[locale] = {"name": name, "distance_km": dist}
    return out


def cluster_effective_tags(db: Any, user_id: int, cluster: list[str]) -> list[str]:
    """Union of `locale_effective_tags` across every locale in `cluster`, as a
    sorted list — the equipment pool Layer 2C resolves against. Sorted for a
    deterministic 2C cache key (the pool feeds the cache-key hash)."""
    pool: set[str] = set()
    for locale in cluster:
        pool |= locale_effective_tags(db, user_id, locale, exclude_disputed=True)
    return sorted(pool)


# ── Event Windows Slice 3 (#581 WS-H, F8) — category equipment baselines ──────
# A not-yet-logged locale (an away destination the athlete just created inline,
# or a cold home gym) links no gym_profile and carries no logged terrain, so the
# feasibility cascade degrades every discipline to near-strength. F8: until the
# athlete logs actuals on arrival, a locale whose CATEGORY has an authored
# baseline ASSUMES that baseline's equipment + terrain (the plan is built around
# it; logging actuals then refreshes the window — the arrival-regen loop). The 5
# gym + 2 pool MANUAL_CATEGORIES slugs (routes/locales.py) collapse to 4 authored
# baselines (layer0.location_category_equipment_baseline, migration 0005).
_CATEGORY_BASELINE_KEY: dict[str, str] = {
    "commercial_chain_gym": "commercial",
    "independent_gym": "commercial",
    "hotel_gym": "hotel",
    "climbing_gym_chain": "climbing",
    "climbing_gym_indie": "climbing",
    "pool_indoor": "pool",
    "pool_outdoor": "pool",
}

# Display label for the assumed-baseline overlay note (Trigger-#1 wording, Andy
# 2026-06-14). Keyed by the logical baseline category.
_BASELINE_DISPLAY: dict[str, str] = {
    "commercial": "commercial gym",
    "hotel": "hotel gym",
    "climbing": "climbing gym",
    "pool": "pool",
}


def load_category_baselines(db: Any) -> dict[str, dict[str, set[str]]]:
    """`{baseline_key: {"equipment": {...}, "terrain": {...}}}` from
    `layer0.location_category_equipment_baseline` (active rows). Empty dict when
    the table is absent (pre-migration 0005) or unreadable — the substitution
    then no-ops and a cold locale degrades exactly as before Slice 3, rather than
    crashing the resolution."""
    try:
        rows = db.execute(
            "SELECT category, equipment_tags, terrain_ids "
            "FROM layer0.location_category_equipment_baseline "
            "WHERE superseded_at IS NULL"
        ).fetchall()
    except Exception:  # table not yet migrated / unreachable
        return {}
    return {
        r["category"]: {
            "equipment": _coerce_terrain_ids(r["equipment_tags"]),
            "terrain": _coerce_terrain_ids(r["terrain_ids"]),
        }
        for r in rows
    }


def _category_baseline(
    baselines: dict[str, dict[str, set[str]]], category: str | None
) -> dict[str, set[str]] | None:
    """The assumed baseline for a locale's MANUAL_CATEGORIES slug, or None when
    the slug maps to no baseline (park/residences) or the table is empty."""
    return baselines.get(_CATEGORY_BASELINE_KEY.get(category or ""))


def _locale_category(db: Any, user_id: int, locale: str) -> str | None:
    """The locale's MANUAL_CATEGORIES slug. Issued as its own query (kept out of
    the existing `gym_profile_id` / `locale_terrain_ids` SELECTs so their SQL
    shape is unchanged) and only ever called when a baseline table exists."""
    row = db.execute(
        "SELECT category FROM locale_profiles "
        "WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    ).fetchone()
    return row["category"] if row else None


def locale_assumed_baseline_display(
    db: Any, user_id: int, locale: str
) -> str | None:
    """The display label of the baseline a locale ASSUMES — set only when the
    locale is genuinely cold (no logged equipment AND no logged terrain) and its
    category has an authored baseline. Used to mark an away window's overlay as
    running on assumed equipment/terrain (Slice 3). None otherwise."""
    baselines = load_category_baselines(db)
    if not baselines:
        return None
    row = db.execute(
        "SELECT category, locale_terrain_ids FROM locale_profiles "
        "WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    ).fetchone()
    if row is None:
        return None
    key = _CATEGORY_BASELINE_KEY.get(row["category"] or "")
    if key is None or key not in baselines:
        return None
    if locale_effective_tags(db, user_id, locale):
        return None  # has logged equipment → not assumed
    if _coerce_terrain_ids(row["locale_terrain_ids"]):
        return None  # has logged terrain → not assumed
    return _BASELINE_DISPLAY.get(key, key)


def cluster_equipment_by_locale(
    db: Any, user_id: int, cluster: list[str]
) -> dict[str, set[str]]:
    """Per-locale effective-equipment sets across the cluster — the equipment
    analogue kept un-unioned (keyed by locale) for session-feasibility routing,
    where *which* locale carries a cardio machine matters (#540 slice 2c.2).

    Slice 3 (F8): a locale with NO logged equipment whose category has an
    authored baseline assumes that baseline (replace semantics — any logged
    equipment wins, so a logged locale is untouched)."""
    out = {
        locale: locale_effective_tags(db, user_id, locale, exclude_disputed=True)
        for locale in cluster
    }
    baselines = load_category_baselines(db)
    # Rule #15 observability: equipment feeds the feasibility INDOOR tier + craft
    # routing. The usual reason a locale's pool is empty is that it links no
    # gym_profile — log the link + tag count per locale so a thin pool is
    # attributable to "no profile linked" rather than guessed. Scoped to this
    # feasibility/2C helper, not the per-page-load `locale_effective_tags`.
    for locale in cluster:
        prof = db.execute(
            "SELECT gym_profile_id FROM locale_profiles "
            "WHERE user_id = ? AND locale = ? LIMIT 1",
            (user_id, locale),
        ).fetchone()
        gid = prof["gym_profile_id"] if prof else None
        assumed = ""
        if baselines and not out[locale]:
            category = _locale_category(db, user_id, locale)
            base = _category_baseline(baselines, category)
            if base and base["equipment"]:
                out[locale] = set(base["equipment"])
                assumed = (
                    f" assumed_baseline={_CATEGORY_BASELINE_KEY.get(category)}"
                    f" (category={category} no logged equipment)"
                )
        print(
            f"cluster_equipment_by_locale: user_id={user_id} locale={locale!r} "
            f"gym_profile_id={gid} n_tags={len(out[locale])}{assumed}"
        )
    return out


def cluster_terrain_by_locale(
    db: Any, user_id: int, cluster: list[str]
) -> dict[str, set[str]]:
    """Per-locale `locale_terrain_ids` (canonical TRN-xxx) across the cluster —
    the terrain analogue of `cluster_equipment_by_locale`. Reads the
    `locale_profiles.locale_terrain_ids` TEXT[] for each locale; the Postgres
    list shape and the SQLite JSON-string shim are both tolerated (mirrors
    `_hydrate_locale_terrain_ids` route-side). Locales with NULL/empty terrain
    map to an empty set. Keyed by locale (not unioned) because session routing
    needs to know *which* cluster locale carries the required terrain (#540)."""
    out: dict[str, set[str]] = {}
    baselines = load_category_baselines(db)
    for locale in cluster:
        row = db.execute(
            "SELECT locale_terrain_ids FROM locale_profiles "
            "WHERE user_id = ? AND locale = ? LIMIT 1",
            (user_id, locale),
        ).fetchone()
        raw = row["locale_terrain_ids"] if row else None
        coerced = _coerce_terrain_ids(raw)
        # Slice 3 (F8): a locale with NO logged terrain whose category has an
        # authored baseline assumes that baseline's terrain (replace semantics —
        # any logged terrain wins). Mirrors the equipment fallback above.
        assumed = ""
        if baselines and not coerced:
            category = _locale_category(db, user_id, locale)
            base = _category_baseline(baselines, category)
            if base and base["terrain"]:
                coerced = set(base["terrain"])
                assumed = (
                    f" assumed_baseline={_CATEGORY_BASELINE_KEY.get(category)}"
                    f" (category={category} no logged terrain)"
                )
        # Rule #15 observability: log the raw cell alongside the coerced set so a
        # terrain that IS saved but fails to surface (missing row, NULL, or an
        # unexpected TEXT[]/JSON shape `_coerce_terrain_ids` drops to empty) is
        # visible rather than silently absent from the feasibility cascade.
        print(
            f"cluster_terrain_by_locale: user_id={user_id} locale={locale!r} "
            f"row_found={row is not None} raw={raw!r} coerced={sorted(coerced)}{assumed}"
        )
        out[locale] = coerced
    return out


def _coerce_terrain_ids(raw: Any) -> set[str]:
    """Normalize a `locale_terrain_ids` cell (PG list / SQLite JSON-string /
    NULL) into a set of TRN-xxx ids."""
    if raw is None:
        return set()
    if isinstance(raw, (list, tuple)):
        return {str(t) for t in raw if t}
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s in ("{}", "[]"):
            return set()
        try:
            parsed = json.loads(s)
        except (ValueError, TypeError):
            return set()
        if isinstance(parsed, list):
            return {str(t) for t in parsed if t}
    return set()


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two lat/lng points."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))
