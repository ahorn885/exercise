"""Curated pure-craft display names for race disciplines.

Overlay on `layer0.sport_discipline_bridge.discipline_name`, whose labels
are the sport-specific variants from `Sports_Framework_v11.xlsx`
(e.g. "XC Cycling (Road/Gravel)", "Hiking (Weighted)"). This map gives one
pure-craft label per craft, sport-independent — and callers fall back to
the bridge name for ids absent here.

Terrain/condition qualifiers are intentionally dropped: terrain is a
separate per-discipline axis (BestFitModality_Spec_v4). The R6 renumber
(2026-05-25) re-sequenced ids to D-001..D-029 (no suffixes, no gaps) and
collapsed two pairs: kayak flat/whitewater -> D-010 "Kayaking"; mountain-
running uphill/downhill -> D-024 "Mountain Running". The terrain axis now
carries the flat-vs-whitewater / uphill-vs-downhill split.
See `Discipline_ID_Renumber_R6_Design_v1.md` for the old->new map.
"""

from __future__ import annotations

DISCIPLINE_DISPLAY_NAMES: dict[str, str] = {
    "D-001": "Trail Running",
    "D-002": "Road Running",
    "D-003": "Hiking",
    "D-004": "Open Water Swimming",
    "D-005": "Pool Swimming",
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
    "D-016": "Swimming",
    "D-017": "Snowshoeing",
    "D-018": "Mountaineering",
    "D-019": "Paddle Rafting",
    "D-020": "Swimrun",
    "D-021": "Ski Touring",
    "D-022": "Alpine Skiing",
    "D-023": "Ski Transitions",
    "D-024": "Mountain Running",
    "D-025": "Fencing",
    "D-026": "Laser Run",
    "D-027": "Obstacle Racing",
    "D-028": "Cross-Country Skiing",
    "D-029": "Rifle Shooting",
}


def discipline_display_name(discipline_id: str, fallback: str | None = None) -> str:
    """Pure-craft label for a discipline id.

    Falls back to `fallback` (typically the bridge `discipline_name`) when
    the id isn't curated, and to the id itself when no fallback is given.
    """
    label = DISCIPLINE_DISPLAY_NAMES.get(discipline_id)
    if label:
        return label
    return fallback or discipline_id
