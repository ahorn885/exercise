"""Pure-craft display names for race disciplines.

Thin app-layer re-export of the discipline canon defined in
`etl/layer0/discipline_canon.py` — the single source of truth for discipline
ids and names. This module used to maintain its own hand-curated dict, which
drifted out of sync with the ETL (e.g. "Alpine Skiing" for the skimo descent
leg). It now derives from the canon so there is exactly one place names live.

Callers pass a `discipline_id` and an optional `fallback` (typically a raw
`discipline_name` from a denorm row). Merged ids (former D-005 / D-016 → D-004
"Swimming") resolve to the survivor's name; composite, removed, or unknown ids
fall back to `fallback` (then to the id itself).
"""
from __future__ import annotations

from etl.layer0.discipline_canon import (
    CANONICAL_NAMES as DISCIPLINE_DISPLAY_NAMES,
    canonical_id,
    canonical_name,
)

__all__ = ["DISCIPLINE_DISPLAY_NAMES", "discipline_display_name"]


def discipline_display_name(discipline_id: str, fallback: str | None = None) -> str:
    """Pure-craft label for a discipline id.

    Resolves merges (D-005 / D-016 → D-004) to the canonical survivor name.
    Falls back to `fallback` (typically the denorm `discipline_name`) when the
    id is composite / removed / unknown, and to the id itself when no fallback
    is given.
    """
    cid = canonical_id(discipline_id)
    if cid:
        name = canonical_name(cid)
        if name:
            return name
    return fallback or discipline_id
