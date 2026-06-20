"""Layer 5A — deterministic supplement recommendation engine (zero-LLM).

Surfaces the two supplement views the athlete asked for (#621):

  * **Standard** — the "what you always take" daily baseline: a curated set of
    general endurance-athlete supplements, plus any Layer 2E dietary-pattern
    additions (e.g. Vegan → B12), minus anything the Layer 2E contraindication
    screen auto-removed. Each line is tagged `already_in_protocol` when the
    athlete already logs it.
  * **Daily / effort-based** — per training day, keyed off the day's load tier
    (and the Layer 2E race-day suggestions on a race day).

Advisory only — never medical instruction. These mirror the supplement content
previously hard-coded in `routes/plans.py` (`DAILY_SUPPLEMENTS` + the per-tier
fueling strings), now made data-driven so it renders off the real plan and the
real Layer 2E contraindication screen rather than a constant.
"""

from __future__ import annotations

from layer4.context import (
    DietaryPatternFlag,
    RaceDaySupplementSuggestion,
    SupplementIntegrationPayload,
)
from layer5.payload import SupplementRec

# Curated baseline — the system "standard daily" recommendation for an endurance
# athlete. Ported from the legacy hard-coded `DAILY_SUPPLEMENTS` (routes/plans.py)
# so behaviour is preserved while becoming data-driven + contraindication-aware.
# `supplement_id` aligns with the Layer 0 supplement vocab where one exists
# (omega_3, magnesium) so the `already_in_protocol` match lands; the rest are
# display-only ids (best-effort match).
# (supplement_id, name, dose, timing)
_BASELINE: list[tuple[str, str, str | None, str | None]] = [
    ("creatine", "Creatine", "5 g", "morning"),
    ("omega_3", "Omega-3", "2–3 g", "with a meal"),
    ("vitamin_d3", "Vitamin D3", "2000 IU", "morning"),
    ("magnesium", "Magnesium glycinate", "400 mg", "pre-bed"),
    ("multivitamin", "Multivitamin", None, "with breakfast"),
]

# Dietary-pattern supplement display names keyed by the Layer 2E
# `suggested_supplement_id`; falls back to a title-cased id when unmapped.
_DIETARY_NAMES: dict[str, str] = {
    "vitamin_b12": "Vitamin B12",
    "iron": "Iron",
    "omega_3": "Omega-3 (algae EPA/DHA)",
}

# Effort / load-tier daily recommendations. Ported from the supplement-like
# content in the legacy per-intensity fueling strings (electrolytes, BCAAs, tart
# cherry). Richer tiers carry more; rest/light days carry none.
# tier -> [(name, dose, timing, reason)]
_EFFORT_TIER: dict[str, list[tuple[str, str | None, str | None, str]]] = {
    "rest": [],
    "light": [],
    "moderate": [
        ("Electrolyte mix", None, "during", "sodium + fluid for the session"),
    ],
    "hard": [
        ("Electrolyte mix", "~500 mg Na/hr", "during", "high-sweat session"),
        ("Tart cherry", "30 ml", "post-session", "recovery after a hard day"),
    ],
    "peak": [
        ("Electrolyte mix", "~500 mg Na/hr", "during", "peak training load"),
        ("Carbohydrate drink", "50–60 g/hr", "during", "fuel the session"),
        ("Tart cherry", "30 ml", "post-session", "recovery after a peak day"),
    ],
}


def build_standing_supplements(
    supplement_integration: SupplementIntegrationPayload | None,
    dietary_flags: list[DietaryPatternFlag] | None,
) -> list[SupplementRec]:
    """The Standard "always take" block: baseline + dietary additions, screened.

    Drops any baseline / dietary supplement the Layer 2E screen auto-removed for
    a contraindication, and tags each line `already_in_protocol` when the athlete
    already logs it. Deterministic — ordered baseline first, then dietary in flag
    order, de-duplicated by supplement id.
    """
    si = supplement_integration
    in_protocol_ids: set[str] = set()
    contraindicated_ids: set[str] = set()
    if si is not None:
        in_protocol_ids = {s.supplement_id for s in si.integrated}
        contraindicated_ids = {
            f.supplement_id for f in si.contraindication_flags if f.supplement_id
        }

    recs: list[SupplementRec] = []
    seen: set[str] = set()
    for supp_id, name, dose, timing in _BASELINE:
        if supp_id in contraindicated_ids:
            continue  # auto-removed by the 2E screen — never recommend
        seen.add(supp_id)
        recs.append(SupplementRec(
            name=name,
            dose=dose,
            timing=timing,
            reason="daily baseline for endurance training",
            source="baseline",
            already_in_protocol=supp_id in in_protocol_ids,
        ))

    for flag in dietary_flags or []:
        sid = flag.suggested_supplement_id
        if not sid or sid in seen or sid in contraindicated_ids:
            continue
        seen.add(sid)
        recs.append(SupplementRec(
            name=_DIETARY_NAMES.get(sid, sid.replace("_", " ").title()),
            dose=None,
            timing=None,
            reason=f"{flag.pattern}: {flag.rationale}",
            source="dietary",
            already_in_protocol=sid in in_protocol_ids,
        ))
    return recs


def effort_supplements_for_day(
    load_tier: str,
    *,
    is_race_day: bool,
    race_suggestions: list[RaceDaySupplementSuggestion] | None = None,
) -> list[SupplementRec]:
    """The Daily / effort-based block for one day.

    On a race day, passes through the Layer 2E race-day suggestions for the
    event(s) on that date (the race fueling plan carries the per-hour detail).
    Otherwise maps the day's `load_tier` to its effort-based recommendations.
    """
    if is_race_day:
        return [
            SupplementRec(
                name=sug.canonical_name,
                dose=None,
                timing="race day",
                reason=sug.reason,
                source="race",
                already_in_protocol=sug.already_in_athlete_protocol,
            )
            for sug in (race_suggestions or [])
        ]
    return [
        SupplementRec(
            name=name, dose=dose, timing=timing, reason=reason, source="effort",
        )
        for name, dose, timing, reason in _EFFORT_TIER.get(load_tier, [])
    ]
