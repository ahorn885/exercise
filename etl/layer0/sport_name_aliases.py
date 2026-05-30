"""Layer 0 ETL — Sport name alias map (Open Item #5 resolution).

Maps exercise DB `sport_name` values → one or more framework sport names
(as they appear in `layer0.sports.sport_name`, after newline-stripping).

Used by the bridge builder and vocab alignment validator to resolve the
vocabulary mismatch between the exercise DB's discipline-level sport tags
and the framework's sport-level names.

Decisions captured: Andy, May 2026.

Rules:
  - Keys are exercise DB sport_name strings (exact, case-sensitive as stored).
  - Values are lists of framework sport_name strings (newline-stripped).
  - WILDCARD sentinel "*" means the exercise maps to ALL framework sports.
  - Framework sport names here must match layer0.sports.sport_name exactly
    (post newline-strip normalization — see extract_sports() fix below).
"""

# Sentinel used for General Conditioning → all sports
_ALL = "*"

SPORT_NAME_ALIASES: dict[str, list[str] | str] = {

    # ── Already matched (kept here for completeness / single source of truth) ──
    "Triathlon":           ["Triathlon", "Triathlon (Full / Ironman 140.6)",
                            "Triathlon (Half / 70.3)", "Triathlon (Sprint)",
                            "Triathlon (Standard / Olympic)"],
    "SkiMo":               ["Skimo", "Skimo (Individual / Team)",
                            "Skimo (Long Distance / Grand Traverse)",
                            "Skimo (Sprint)", "Skimo (Vertical / VK)"],
    "Fell Running":        ["Fell Running"],
    # "Modern Pentathlon" removed as a sport (sport_canon.REMOVED_SPORTS) — alias dropped.
    "SwimRun":             ["Swimrun"],

    # ── AR core disciplines ──
    "Trail Running":       ["Adventure Racing", "Fell Running",
                            "Ultramarathon (Trail)", "Marathon (Trail)"],
    "Hiking":              ["Adventure Racing"],
    "Mountain Biking":     ["Adventure Racing",
                            "Long Distance / Endurance Cycling (XC Mountain Biking)"],
    "Packrafting":         ["Adventure Racing"],
    "Kayaking":            ["Adventure Racing", "Canoe / Kayak Marathon",
                            "Canoe / Kayak Marathon (ICF Competition)",
                            "Canoe / Kayak Marathon (Ultra-Distance)"],
    "Orienteering":        ["Adventure Racing"],

    # ── Other clear sport mappings ──
    "Ultramarathon":       ["Ultramarathon (Road)", "Ultramarathon (Trail)"],
    "Marathon":            ["Marathon (Road)", "Marathon (Trail)", "Marathon (Mountain)"],
    "Mountain Running / Sky Running": ["Mountain Running / Skyrunning"],
    "Run-Bike-Run Duathlon": ["Duathlon"],
    "Canoeing":            ["Canoe / Kayak Marathon",
                            "Canoe / Kayak Marathon (ICF Competition)",
                            "Canoe / Kayak Marathon (Ultra-Distance)"],
    "Bikepacking":         ["Long Distance / Endurance Cycling"],
    "XC Skiing":           ["Cross-Country / Nordic Skiing",  # "Biathlon" removed (sport_canon)
                            "Skimo", "Skimo (Individual / Team)"],
    "Road Cycling":        ["Long Distance / Endurance Cycling (Road / Gran Fondo)",
                            "Long Distance / Endurance Cycling (Time Trial)"],
    "Long Distance Paddle Racing": ["Canoe / Kayak Marathon",
                                   "Canoe / Kayak Marathon (ICF Competition)",
                                   "Canoe / Kayak Marathon (Ultra-Distance)"],
    "Long Distance Orienteering": ["Adventure Racing"],
    "XC / AR Cycling":     ["Adventure Racing",
                            "Long Distance / Endurance Cycling (XC Mountain Biking)"],
    "Swimming":            ["Triathlon", "Triathlon (Full / Ironman 140.6)",
                            "Triathlon (Half / 70.3)", "Triathlon (Sprint)",
                            "Triathlon (Standard / Olympic)",
                            "Swimrun", "Aquabike", "Aquathlon",
                            "Open Water Marathon Swimming",
                            "Open Water Marathon Swimming (10km / Olympic Distance)",
                            "Open Water Marathon Swimming (25km / Ultra Distance)"],
    "Gravel Cycling":      ["Long Distance / Endurance Cycling (Gravel)"],
    "Paddle Rafting":      ["Adventure Racing"],

    # ── Decided items ──

    # Rock Climbing: AR (climbing/abseiling are AR disciplines),
    # Off-Road Multisport, Skimo (technical mountain terrain overlap)
    "Rock Climbing":       ["Adventure Racing",
                            "Off-Road / Adventure Multisport (Non-Nav)",
                            "Skimo"],

    # General Conditioning: cross-sport — applies to all framework sports
    "General Conditioning": _ALL,

    # Multi-Sport Race: direct match to Off-Road / Adventure Multisport (Non-Nav)
    # NOTE: fuzzy matcher missed this because xlsx cell has embedded newline
    # in the framework sport name. Fix: strip newlines in extract_sports().
    "Multi-Sport Race":    ["Off-Road / Adventure Multisport (Non-Nav)"],

    # Mountaineering: AR (expedition AR), Multisport, Skimo (altitude/technical)
    "Mountaineering":      ["Adventure Racing",
                            "Off-Road / Adventure Multisport (Non-Nav)",
                            "Skimo"],

    # Rappelling / Abseiling: AR discipline, Multisport
    "Rappelling / Abseiling": ["Adventure Racing",
                               "Off-Road / Adventure Multisport (Non-Nav)"],

    # Fixed Rope / Via Ferrata: AR, Multisport, Skimo
    "Fixed Rope / Via Ferrata": ["Adventure Racing",
                                 "Off-Road / Adventure Multisport (Non-Nav)",
                                 "Skimo"],

    # Fencing: was Modern Pentathlon only — sport + D-025 discipline removed; alias dropped.

    # Rowing: AR + Multisport + all endurance paddle sports
    "Rowing":              ["Adventure Racing",
                            "Off-Road / Adventure Multisport (Non-Nav)",
                            "Canoe / Kayak Marathon",
                            "Canoe / Kayak Marathon (ICF Competition)",
                            "Canoe / Kayak Marathon (Ultra-Distance)"],

    # Obstacle Course Racing: re-homed to Off-Road / Adventure Multisport after
    # Modern Pentathlon was removed as a sport (Andy, 2026-05-30). OCR (D-027)
    # is kept; this keeps OCR-tagged exercises mapped to a surviving sport.
    "Obstacle Course Racing": ["Off-Road / Adventure Multisport (Non-Nav)"],

    # SUP: AR + Multisport
    "SUP":                 ["Adventure Racing",
                            "Off-Road / Adventure Multisport (Non-Nav)"],

    # Snowshoeing: AR + Multisport
    "Snowshoeing":         ["Adventure Racing",
                            "Off-Road / Adventure Multisport (Non-Nav)"],
}


def resolve_framework_sports(
    exercise_db_sport: str,
    all_framework_sports: list[str],
) -> list[str]:
    """Resolve an exercise DB sport name to framework sport name(s).

    Returns a list of framework sport names. Returns all_framework_sports
    when the alias is the wildcard sentinel. Returns an empty list when the
    sport name is not in the alias map (caller should surface as WARN).
    """
    result = SPORT_NAME_ALIASES.get(exercise_db_sport)
    if result is None:
        return []
    if result == _ALL:
        return list(all_framework_sports)
    return list(result)
