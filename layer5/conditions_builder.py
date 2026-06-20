"""Layer 5B conditions synthesis — deterministic per-day clothing/kit advisor.

Pure functions (no DB, no network, no LLM). Given a plan version's persisted
sessions plus a ``conditions_for(locale_id, date)`` resolver (the orchestrator
wires this to `weather_client.get_expected_conditions`; tests pass a stub),
produce a `PlanConditions` artifact: for each day with an outdoor session at a
locale that resolves to expected conditions, a thermal band, a clothing summary,
a kit list and advisory flags.

The mapping is the whole point of "deterministic advisory": identical expected
conditions always yield an identical recommendation, so the output is auditable
and reproducible (modulo the supplied ``generated_at``).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Callable

from layer4.payload import PlanSession
from layer5.conditions_payload import (
    ConditionsModelMeta,
    DayConditions,
    PlanConditions,
    ThermalBand,
)

if TYPE_CHECKING:  # avoid importing `requests` (weather_client) just to type-hint
    from weather_client import ExpectedConditions

CONDITIONS_MODEL_NAME = "climate_normals_advisory_v1"

# Resolver: locale slug + date -> the locale's expected conditions, or None when
# coordinates are missing / the climate-normals sample is empty.
ConditionsResolver = Callable[[str, date], "ExpectedConditions | None"]

# ─── §5B thresholds ──────────────────────────────────────────────────────────

# Thermal band by the day's *high* (°C). Ordered low→high; first band whose
# upper cutoff the high falls under wins. The top band ("hot") has no cutoff.
_BAND_CUTOFFS_C: tuple[tuple[ThermalBand, float], ...] = (
    ("freezing", 0.0),
    ("cold", 8.0),
    ("cool", 15.0),
    ("mild", 22.0),
    ("warm", 28.0),
)
_TOP_BAND: ThermalBand = "hot"

# Flag thresholds.
_HEAT_TMAX_C = 28.0  # daytime high at/above which heat management matters
_COLD_TMIN_C = 2.0  # overnight/early low at/below which a cold start matters
_WET_PCT_THRESHOLD = 40  # wet-day probability at/above which rain is "likely"

_BAND_CLOTHING: dict[ThermalBand, str] = {
    "freezing": "Thermal base layer, tights, gloves, hat and a windproof shell.",
    "cold": "Long sleeves and tights; light gloves and a wind layer to start.",
    "cool": "A long-sleeve or light layer over short sleeves; arm warmers.",
    "mild": "Shorts and short sleeves; a light layer for the warm-up.",
    "warm": "Lightweight, breathable kit; sun protection.",
    "hot": "Minimal breathable kit; hat and sunglasses; pre-hydrate.",
}

# Base kit per band; rain adds a waterproof layer (see `kit_for`).
_BAND_KIT: dict[ThermalBand, tuple[str, ...]] = {
    "freezing": ("thermal base layer", "gloves", "hat", "windproof shell"),
    "cold": ("long sleeves", "tights", "light gloves"),
    "cool": ("light long-sleeve", "arm warmers"),
    "mild": ("light warm-up layer",),
    "warm": ("sunscreen", "cap"),
    "hot": ("sunscreen", "cap", "sunglasses", "extra fluids"),
}

# Standing framing note — normals are not a forecast.
STANDING_NOTE = (
    "Typical conditions from multi-year climate normals at each session's "
    "locale — dress for these, but check the live forecast nearer the day."
)


def classify_band(temp_max_c: float) -> ThermalBand:
    """Map a day's high (°C) to a thermal band."""
    for band, cutoff in _BAND_CUTOFFS_C:
        if temp_max_c < cutoff:
            return band
    return _TOP_BAND


def clothing_for(band: ThermalBand) -> str:
    return _BAND_CLOTHING[band]


def kit_for(band: ThermalBand, wet: bool) -> list[str]:
    items = list(_BAND_KIT[band])
    if wet:
        items.append("waterproof layer")
    return items


def advisory_flags(temp_max_c: float, temp_min_c: float, wet_pct: int) -> list[str]:
    """Per-day advisory chips, in a stable order."""
    flags: list[str] = []
    if temp_max_c >= _HEAT_TMAX_C:
        flags.append("heat — front-load hydration and electrolytes; favour cooler hours")
    if temp_min_c <= _COLD_TMIN_C:
        flags.append("cold start — cover hands and ears; wear a layer you can shed")
    if wet_pct >= _WET_PCT_THRESHOLD:
        flags.append("rain likely — pack a waterproof layer and mind your footing")
    return flags


def _model_meta() -> ConditionsModelMeta:
    return ConditionsModelMeta(
        model=CONDITIONS_MODEL_NAME,
        normals_years=5,  # weather_client._NORMALS_YEARS
        window_days=3,  # weather_client._WINDOW_DAYS
        band_cutoffs_tmax_c={band: cutoff for band, cutoff in _BAND_CUTOFFS_C},
        heat_tmax_c=_HEAT_TMAX_C,
        cold_tmin_c=_COLD_TMIN_C,
        wet_pct_threshold=_WET_PCT_THRESHOLD,
    )


def _representative_session(day_sessions: list[PlanSession]) -> PlanSession | None:
    """The first session of the day that has a locale (outdoor work)."""
    for s in day_sessions:
        if s.locale_id:
            return s
    return None


def build_plan_conditions(
    *,
    plan_version_id: int,
    sessions: list[PlanSession],
    conditions_for: ConditionsResolver,
    generated_at: datetime | None = None,
) -> PlanConditions:
    """Build the Layer 5B conditions artifact for one plan version.

    `sessions` is the plan version's persisted `PlanSession` list. `conditions_for`
    resolves a locale slug + date to its expected conditions (or None). A day is
    represented by its first session carrying a locale; days with no such session,
    or whose locale resolves to None, produce no row. Pure + deterministic.
    """
    generated_at = generated_at or datetime.now(timezone.utc)

    by_date: dict[date, list[PlanSession]] = defaultdict(list)
    for sess in sessions:
        by_date[sess.date].append(sess)

    days: list[DayConditions] = []
    for d in sorted(by_date):
        day_sessions = by_date[d]
        rep = _representative_session(day_sessions)
        if rep is None:
            continue
        ec = conditions_for(rep.locale_id, d)
        if ec is None:
            continue

        band = classify_band(ec.temp_max_c)
        wet_pct = int(ec.wet_day_probability_pct)
        is_wet = wet_pct >= _WET_PCT_THRESHOLD
        days.append(
            DayConditions(
                date=d,
                day_of_week=day_sessions[0].day_of_week,
                locale_id=rep.locale_id,
                locale_name=rep.locale_name,
                # Only the sessions actually at the represented locale.
                session_ids=[
                    s.session_id for s in day_sessions if s.locale_id == rep.locale_id
                ],
                source="climate_normals",
                temp_max_c=ec.temp_max_c,
                temp_min_c=ec.temp_min_c,
                wet_day_probability_pct=wet_pct,
                sample_years=ec.sample_years,
                thermal_band=band,
                clothing_summary=clothing_for(band),
                kit_items=kit_for(band, is_wet),
                advisory_flags=advisory_flags(ec.temp_max_c, ec.temp_min_c, wet_pct),
            )
        )

    return PlanConditions(
        plan_version_id=plan_version_id,
        generated_at=generated_at,
        model_meta=_model_meta(),
        days=days,
        notes=[STANDING_NOTE] if days else [],
    )
