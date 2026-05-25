"""Curated pure-craft display names for race disciplines.

Overlay on `layer0.sport_discipline_bridge.discipline_name`, whose labels
are the sport-specific Sheet-3 variants from `Sports_Framework_v10.xlsx`
(e.g. "XC Cycling (Road/Gravel)", "Hiking (Weighted)"). This map gives one
pure-craft label per craft, sport-independent — and callers fall back to
the bridge name for ids absent here (future disciplines, or the combined
"D-005 + D-005a" bridge rows that never match a single id).

Terrain/condition qualifiers are intentionally dropped: terrain becomes a
separate per-discipline axis in the best-fit re-model (BestFitModality_Spec_v3).
IDs are left untouched this slice (kayak D-008a/b and mountain-running
D-022/D-023 keep distinct labels; their collapse lands with the Slice-3
terrain axis that absorbs the flat-vs-whitewater / uphill-vs-downhill split).
"""

from __future__ import annotations

DISCIPLINE_DISPLAY_NAMES: dict[str, str] = {
    "D-001": "Trail Running",
    "D-002": "Road Running",
    "D-003": "Hiking",
    "D-004": "Open Water Swimming",
    "D-004b": "Pool Swimming",
    "D-005": "Road Cycling",
    "D-005a": "Time-Trial Cycling",
    "D-006": "Mountain Biking",
    "D-007": "Packrafting",
    "D-008a": "Flat-water Kayaking",
    "D-008b": "Whitewater Kayaking",
    "D-009": "Canoeing",
    "D-010": "Rock Climbing",
    "D-011": "Abseiling",
    "D-012": "Via Ferrata",
    "D-013": "Orienteering",
    "D-014": "Swimming",
    "D-015": "Snowshoeing",
    "D-016": "Mountaineering",
    "D-017": "Paddle Rafting",
    "D-018": "Swimrun",
    "D-019": "Ski Touring",
    "D-020": "Alpine Skiing",
    "D-021": "Ski Transitions",
    "D-022": "Uphill Running",
    "D-023": "Downhill Running",
    "D-024": "Fencing",
    "D-025": "Laser Run",
    "D-026": "Obstacle Racing",
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
