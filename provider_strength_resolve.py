"""Resolve a logged strength exercise NAME to its canonical layer0 EX-id (#679).

First concrete **inbound** slice of the provider data translation layer
(`aidstation-sources/specs/Provider_Data_Translation_Layer_Spec` §6.1; design
`aidstation-sources/designs/ProviderTranslation_GarminStrength_679_Design_v1.md`).

After #430 Slice C the rx write path keys off the layer0 EX-id, but a Garmin FIT
upload's *specific* exercise name (e.g. "Barbell Back Squat" — 1 of 92 squat
subtypes the parser can emit) rarely matched the 20-entry curated
`NAME_TO_EX_ID`, so most Garmin-logged lifts landed as NULL-EX-id rows and never
surfaced as capacity-derived loads in plan-gen — defeating the #335 goal for the
athlete who dogfoods via Garmin.

This module resolves a name through three additive steps (design §3.1), called
from the single write chokepoint `rx_engine.apply_session_outcome`:

    1. ALIAS    — exact-authored name → EX-id. Merges the curated `NAME_TO_EX_ID`
                  (also read by the init_db `current_rx` backfill) with the
                  token-set-exact Garmin specifics authored for #679. Preserves
                  specificity: "Dumbbell Hammer Curl" → EX234 (neutral-grip
                  hammer curl), NOT the coarse "Curl" → EX247.
    2. CATEGORY — backstop only. Collapse a specific Garmin subtype to its coarse
                  FIT category name, then through the SAME ratified coarse
                  `NAME_TO_EX_ID` ("Barbell Bench Press" → "Bench Press" → EX229).
                  No new vocabulary: only categories already mapped to a coarse
                  EX-id resolve here; the rest fall through to bucket-3.
    3. BUCKET-3 — no match → `(None, 'bucket3')`. The caller records the lift
                  (record-don't-drop) with no canonical EX-id instead of silently
                  treating it as a brand-new exercise on every ingest (design §4).
                  A later wave surfaces it inline in completed history.

Fuzzy (non-token-exact) candidate matches and Garmin categories with no coarse
layer0 home are deliberately NOT auto-added here — they are HITL decisions Andy
ratifies in one consolidated batch (design §5, D-10), then authored into
`GARMIN_STRENGTH_ALIASES` / extended onto the coarse map.
"""

from __future__ import annotations

from layer0_progression import NAME_TO_EX_ID


# Garmin FIT subtype name → specific layer0 EX-id. Authored for #679 as the
# token-set-exact matches between the Garmin name space (garmin_fit_parser's
# `_EXERCISE_SUBTYPE_MAP`, 1,239 subtypes) and the strength-relevant layer0
# qualified names — identical normalized token sets (equipment synonyms folded:
# bb↔barbell, db↔dumbbell, …). These are deterministic equivalences, not fuzzy
# judgement calls, so they seed without per-row HITL. Each adds SPECIFICITY the
# coarse category backstop can't: "Dumbbell Hammer Curl" → EX234 (hammer),
# distinct from the coarse "Curl" → EX247; "Seated Calf Raise" → EX026 (the Calf
# Raise category has no coarse home, so without this it would bucket-3).
# Entries already present verbatim in NAME_TO_EX_ID (Dead Bug, Side Plank,
# Sit Up) are intentionally omitted — the merge in `_alias_map()` covers them.
GARMIN_STRENGTH_ALIASES: dict[str, str] = {
    "Barbell Back Squat": "EX001",            # Back Squat (Barbell)
    "Bear Crawl": "EX240",                    # Bear Crawl
    "Bicycle Crunch": "EX224",                # Bicycle Crunch
    "Burpee": "EX238",                        # Burpee
    "Dumbbell Bulgarian Split Squat": "EX021",  # Bulgarian Split Squat (DB)
    "Dumbbell Hammer Curl": "EX234",          # Hammer Curl (DB)
    "Dumbbell Reverse Wrist Curl": "EX111",   # Reverse Wrist Curl (DB)
    "Mountain Climber": "EX221",              # Mountain Climber
    "Rope Climb": "EX195",                    # Rope Climb
    "Seated Calf Raise": "EX026",             # Seated Calf Raise
    "Single Arm Dumbbell Bench Press": "EX242",  # Single-Arm DB Bench Press
    "Wide Grip Lat Pulldown": "EX080",        # Lat Pulldown (Wide Grip)
}


# Inverted Garmin subtype-name → coarse FIT category name, derived from
# garmin_fit_parser's maps (the SAME source the parser emits names from, so the
# reverse map cannot drift from the names actually seen). Built lazily and
# cached: importing the parser pulls `fit_tool`, and this module must stay
# importable on the manual-log path even where the category backstop is never
# exercised. Degrades to {} if the parser/fit_tool is unavailable → the category
# step no-ops and the name falls through to bucket-3 (safe).
_SUBTYPE_TO_CATEGORY: dict[str, str] | None = None


def _subtype_to_category() -> dict[str, str]:
    global _SUBTYPE_TO_CATEGORY
    if _SUBTYPE_TO_CATEGORY is not None:
        return _SUBTYPE_TO_CATEGORY
    try:
        from garmin_fit_parser import (
            _EXERCISE_SUBTYPE_MAP,
            _EXERCISE_CATEGORY_MAP,
        )
    except Exception:
        _SUBTYPE_TO_CATEGORY = {}
        return _SUBTYPE_TO_CATEGORY
    inv: dict[str, str] = {}
    for cat_int, subs in _EXERCISE_SUBTYPE_MAP.items():
        cat_name = _EXERCISE_CATEGORY_MAP.get(cat_int)
        if not cat_name:
            continue
        for human in subs.values():
            inv.setdefault(human, cat_name)  # first category wins on dup names
    _SUBTYPE_TO_CATEGORY = inv
    return _SUBTYPE_TO_CATEGORY


def _alias_map() -> dict[str, str]:
    """Curated `NAME_TO_EX_ID` (coarse + manual-log names) extended/superseded by
    the #679 Garmin specifics. The Garmin entries win on any key collision."""
    return {**NAME_TO_EX_ID, **GARMIN_STRENGTH_ALIASES}


def resolve_strength_ex_id(exercise, *, subtype_to_category=None):
    """Resolve a logged strength exercise NAME to `(layer0_ex_id, match_kind)`.

    `match_kind`:
      - ``'alias'``    — exact-authored name → specific EX-id.
      - ``'category'`` — coarse category-collapse backstop → coarse EX-id.
      - ``'bucket3'``  — no match; `layer0_ex_id` is None (record-don't-drop).

    `subtype_to_category` is injectable for tests; production passes None and the
    lazily-built reverse map (from `garmin_fit_parser`) is used.
    """
    if not exercise:
        return None, 'bucket3'
    ex_id = _alias_map().get(exercise)
    if ex_id:
        return ex_id, 'alias'
    s2c = _subtype_to_category() if subtype_to_category is None else subtype_to_category
    cat_name = s2c.get(exercise)
    if cat_name:
        ex_id = NAME_TO_EX_ID.get(cat_name)
        if ex_id:
            return ex_id, 'category'
    return None, 'bucket3'
