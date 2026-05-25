"""Layer 0 ETL — discipline canon (single source of truth for discipline ids + names).

Background
----------
Discipline names were drifting: the ETL extracted `discipline_name` *literally*
from `Sports_Framework_v11.xlsx`, so the same `discipline_id` carried up to ten
different labels across the denorm tables (per-sport context smeared into the
name field — "Trail Running (Base) (on fell terrain where possible)", etc.). A
parallel app-layer overlay (`discipline_display_names.py`) tried to clean this
up for display only, and itself drifted into mislabels (e.g. "Alpine Skiing" for
the skimo descent leg).

This module is the one authoritative map: id -> canonical name, plus the
structural rules (merges, removals, composite splits, non-discipline rows) that
collapse the messy source keyspace onto the curated canon. It is applied at ETL
time (source xlsx is never modified — same convention as `sport_name_aliases`
and `vocabulary_transforms`). `discipline_display_names.py` re-exports from here
so there is a single source of truth.

Canon decisions captured: Andy, May 2026. See the conversation/audit for the
full rationale (which direction each disagreement was resolved, and why).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# The canon — 25 surviving disciplines, one clean craft name each.
# ---------------------------------------------------------------------------

CANONICAL_NAMES: dict[str, str] = {
    "D-001": "Trail Running",
    "D-002": "Road Running",
    "D-003": "Hiking",
    "D-004": "Swimming",            # absorbs former D-005 (pool sprint) + D-016 (generic)
    "D-006": "Road Cycling",
    "D-007": "Time-Trial Cycling",
    "D-008": "Mountain Biking",
    "D-009": "Packrafting",
    "D-010": "Kayaking",
    "D-011": "Canoeing",
    "D-012": "Rock Climbing",
    "D-013": "Abseiling",
    "D-014": "Via Ferrata",
    "D-015": "Orienteering",
    "D-017": "Snowshoeing",
    "D-018": "Mountaineering",
    "D-019": "Paddle Rafting",
    "D-021": "Uphill Skinning",     # was mislabelled "Ski Touring" in the overlay
    "D-022": "Alpine Descent",      # was mislabelled "Alpine Skiing" in the overlay
    "D-024": "Mountain Running",
    "D-025": "Fencing",
    "D-026": "Laser Run",
    "D-027": "Obstacle Course Racing",
    "D-028": "Cross-Country Skiing",
    "D-029": "Rifle Shooting",
}

# Merged-away ids -> survivor. Both former swim variants collapse onto D-004.
ID_REMAP: dict[str, str] = {
    "D-005": "D-004",   # Pool Sprint Swimming -> Swimming
    "D-016": "D-004",   # generic Swimming      -> Swimming
}

# Disciplines removed from the canon entirely.
#   D-020 Swimrun  -> reclassified as a *sport* (swim + run), not a discipline.
#   D-023 Ski Transitions / Boot-packing -> not tracked as a discipline.
REMOVED_IDS: frozenset[str] = frozenset({"D-020", "D-023"})

# Non-discipline rows that legitimately appear in phase_load_allocation under a
# placeholder id ("-" / "—"). They are kept, but keyed with discipline_id = NULL
# and tagged with a category, rather than masquerading as disciplines.
CATEGORY_STRENGTH = "strength"
CATEGORY_MOBILITY = "mobility"
CATEGORY_WEEKLY_TOTAL = "weekly_total"

# Orphan activities with no real discipline id, removed per canon decision:
#   "Portage Running ..."           (parked under a dash id)
#   "Technical Scrambling ..."      (parked under the pseudo-id "D-014 (Ref)")
# These return [] from resolve_ids and None from classify_non_discipline, i.e.
# they are dropped.

_CLEAN_ID_RE = re.compile(r"^D-\d{3}$")
_COMPOSITE_RE = re.compile(r"^D-\d{3}(?:\s*\+\s*D-\d{3})+$")
_ANY_ID_RE = re.compile(r"D-\d{3}")


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def resolve_ids(raw_id: str | None) -> list[str]:
    """Resolve a raw discipline id to zero or more canonical discipline ids.

    - Clean id (``D-001``)         -> ``[canonical]`` (after merge), or ``[]`` if removed.
    - Composite (``D-006 + D-007``) -> the split, canonicalized component ids.
    - Placeholder / pseudo / blank  -> ``[]`` (not a discipline — caller decides
      whether it is a kept non-discipline row or a dropped orphan via
      ``classify_non_discipline``).

    A *clean* id matches ``^D-\\d{3}$`` exactly; ``"D-014 (Ref)"`` does NOT, so it
    is never mistaken for D-014.
    """
    rid = (raw_id or "").strip()
    if not rid:
        return []

    if _COMPOSITE_RE.match(rid):
        out: list[str] = []
        for part in _ANY_ID_RE.findall(rid):
            out.extend(resolve_ids(part))
        return _dedupe(out)

    if _CLEAN_ID_RE.match(rid):
        if rid in REMOVED_IDS:
            return []
        return [ID_REMAP.get(rid, rid)]

    return []


def canonical_id(raw_id: str | None) -> str | None:
    """The single canonical id for a *non-composite* raw id, or None.

    Convenience for callers (substitutes, pairing) that never carry composite
    keys. Returns None for removed / placeholder / pseudo ids.
    """
    ids = resolve_ids(raw_id)
    return ids[0] if len(ids) == 1 else None


def canonical_name(disc_id: str | None) -> str | None:
    """Canonical name for a (already-canonical) discipline id, or None."""
    if not disc_id:
        return None
    return CANONICAL_NAMES.get(disc_id)


def is_canonical_discipline(disc_id: str | None) -> bool:
    return bool(disc_id) and disc_id in CANONICAL_NAMES


def classify_non_discipline(raw_name: str | None) -> str | None:
    """Categorize a non-discipline phase-load row by its name, or None.

    Returns one of the ``CATEGORY_*`` values for the support/aggregate rows that
    are kept (strength, mobility, weekly total). Returns None for anything else
    — including orphan activities (Portage Running, Technical Scrambling) which
    the caller drops.
    """
    n = (raw_name or "").strip().lower()
    if not n:
        return None
    if n.startswith("strength training"):
        return CATEGORY_STRENGTH
    if n.startswith("mobility"):          # "Mobility / Recovery", "Mobility/Recovery"
        return CATEGORY_MOBILITY
    if "weekly total" in n:
        return CATEGORY_WEEKLY_TOTAL
    return None


# Canonical display label per non-discipline category — collapses source
# spelling variants ("Mobility / Recovery" vs "Mobility/Recovery").
CATEGORY_DISPLAY: dict[str, str] = {
    CATEGORY_STRENGTH: "Strength Training",
    CATEGORY_MOBILITY: "Mobility / Recovery",
    CATEGORY_WEEKLY_TOTAL: "WEEKLY TOTAL TARGET",
}


# ---------------------------------------------------------------------------
# Row-level application — apply the canon to extracted ETL row dicts.
#
# Each helper returns a NEW list of row dicts with canonical ids + names,
# composites split into atomic rows, merges/removals/orphans dropped, and the
# table's natural unique key de-duplicated (first-seen wins, mirroring the
# existing extractor dedup). Dropped rows are appended to `dropped` if given,
# for surfacing in the ETL report.
# ---------------------------------------------------------------------------

def normalize_dimension_rows(
    rows: list[dict],
    *,
    id_field: str = "discipline_id",
    name_field: str = "discipline_name",
) -> list[dict]:
    """For `layer0.disciplines`: keep one row per surviving canonical id,
    renamed to canon. Merged-away ids (D-005/D-016) and removed ids
    (D-020/D-023) are dropped — the native survivor row (D-004) carries the
    merged disciplines' dimension attributes.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        rid = (row.get(id_field) or "").strip()
        if rid not in CANONICAL_NAMES or rid in seen:
            continue
        seen.add(rid)
        nr = dict(row)
        nr[name_field] = CANONICAL_NAMES[rid]
        out.append(nr)
    return out


def normalize_named_rows(
    rows: list[dict],
    *,
    unique_fields: tuple[str, ...],
    id_field: str = "discipline_id",
    name_field: str = "discipline_name",
    keep_non_discipline: bool = False,
    category_field: str = "row_category",
    dropped: list[dict] | None = None,
) -> list[dict]:
    """Canonicalize a list of (id, name)-bearing rows.

    - composite id -> one output row per component id;
    - merged/clean id -> single canonical row;
    - removed/orphan/placeholder id -> dropped, UNLESS `keep_non_discipline`
      and the name classifies as a kept non-discipline (strength / mobility /
      weekly total), in which case the row is kept with id=NULL + category.

    De-duplicated by `unique_fields` (first-seen wins).
    """
    out: list[dict] = []
    seen: set[tuple] = set()
    for row in rows:
        produced: list[dict] = []
        for cid in resolve_ids(row.get(id_field)):
            nr = dict(row)
            nr[id_field] = cid
            nr[name_field] = CANONICAL_NAMES[cid]
            if keep_non_discipline:
                nr[category_field] = None
            produced.append(nr)

        if not produced and keep_non_discipline:
            cat = classify_non_discipline(row.get(name_field))
            if cat is not None:
                nr = dict(row)
                nr[id_field] = None
                nr[name_field] = CATEGORY_DISPLAY[cat]
                nr[category_field] = cat
                produced.append(nr)

        if not produced:
            if dropped is not None:
                dropped.append(row)
            continue

        for nr in produced:
            key = tuple(nr.get(f) for f in unique_fields)
            if key in seen:
                if dropped is not None:
                    dropped.append(nr)
                continue
            seen.add(key)
            out.append(nr)
    return out


def normalize_substitute_rows(
    rows: list[dict],
    *,
    dropped: list[dict] | None = None,
) -> list[dict]:
    """Canonicalize `discipline_substitutes` (two id/name pairs).

    A row is dropped if either side is a removed/orphan discipline, or if the
    target and substitute collapse onto the same id after merge (a discipline
    can't substitute for itself). De-duplicated by
    (target_id, substitute_id, substitute_name).
    """
    out: list[dict] = []
    seen: set[tuple] = set()
    for row in rows:
        targets = resolve_ids(row.get("target_id"))
        subs = resolve_ids(row.get("substitute_id"))
        if not targets or not subs:
            if dropped is not None:
                dropped.append(row)
            continue
        for t in targets:
            for s in subs:
                if t == s:
                    if dropped is not None:
                        dropped.append(row)
                    continue
                nr = dict(row)
                nr["target_id"] = t
                nr["target_name"] = CANONICAL_NAMES[t]
                nr["substitute_id"] = s
                nr["substitute_name"] = CANONICAL_NAMES[s]
                key = (t, s, nr["substitute_name"])
                if key in seen:
                    if dropped is not None:
                        dropped.append(nr)
                    continue
                seen.add(key)
                out.append(nr)
    return out


def normalize_pairing_rows(
    rows: list[dict],
    *,
    dropped: list[dict] | None = None,
) -> list[dict]:
    """Canonicalize `discipline_pairing` (id-only pairs). Drops pairs touching a
    removed discipline and self-pairs created by the merge; dedup by (a, b)."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for row in rows:
        a_ids = resolve_ids(row.get("discipline_id_a"))
        b_ids = resolve_ids(row.get("discipline_id_b"))
        if not a_ids or not b_ids:
            if dropped is not None:
                dropped.append(row)
            continue
        for a in a_ids:
            for b in b_ids:
                if a == b or (a, b) in seen:
                    continue
                seen.add((a, b))
                nr = dict(row)
                nr["discipline_id_a"] = a
                nr["discipline_id_b"] = b
                out.append(nr)
    return out
