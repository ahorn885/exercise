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


def locale_effective_tags(db: Any, user_id: int, locale: str) -> set[str]:
    """The authoritative effective-equipment set at one locale, as layer0
    canonical names. `(shared ∪ adds) ∖ removes` (§4):

      - shared  = the linked `gym_profiles.equipment` JSON (canonical names),
      - adds    = this athlete's `locale_equipment_overrides` action='add',
      - removes = ditto action='remove'.

    Empty set when the locale links no gym profile and carries no overrides.
    """
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
    for r in others:
        if (
            _haversine_km(home_lat, home_lng, float(r["lat"]), float(r["lng"]))
            <= _CLUSTER_RADIUS_KM
        ):
            ids.append(r["locale"])
    return ids


def cluster_effective_tags(db: Any, user_id: int, cluster: list[str]) -> list[str]:
    """Union of `locale_effective_tags` across every locale in `cluster`, as a
    sorted list — the equipment pool Layer 2C resolves against. Sorted for a
    deterministic 2C cache key (the pool feeds the cache-key hash)."""
    pool: set[str] = set()
    for locale in cluster:
        pool |= locale_effective_tags(db, user_id, locale)
    return sorted(pool)


def cluster_equipment_by_locale(
    db: Any, user_id: int, cluster: list[str]
) -> dict[str, set[str]]:
    """Per-locale effective-equipment sets across the cluster — the equipment
    analogue kept un-unioned (keyed by locale) for session-feasibility routing,
    where *which* locale carries a cardio machine matters (#540 slice 2c.2)."""
    out = {locale: locale_effective_tags(db, user_id, locale) for locale in cluster}
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
        print(
            f"cluster_equipment_by_locale: user_id={user_id} locale={locale!r} "
            f"gym_profile_id={gid} n_tags={len(out[locale])}"
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
    for locale in cluster:
        row = db.execute(
            "SELECT locale_terrain_ids FROM locale_profiles "
            "WHERE user_id = ? AND locale = ? LIMIT 1",
            (user_id, locale),
        ).fetchone()
        raw = row["locale_terrain_ids"] if row else None
        coerced = _coerce_terrain_ids(raw)
        # Rule #15 observability: log the raw cell alongside the coerced set so a
        # terrain that IS saved but fails to surface (missing row, NULL, or an
        # unexpected TEXT[]/JSON shape `_coerce_terrain_ids` drops to empty) is
        # visible rather than silently absent from the feasibility cascade.
        print(
            f"cluster_terrain_by_locale: user_id={user_id} locale={locale!r} "
            f"row_found={row is not None} raw={raw!r} coerced={sorted(coerced)}"
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
