"""Layer 5B — per-day conditions / clothing advisory payload schemas.

Layer 5 is the supplemental, advisory, **deterministic (zero-LLM)** tier that
runs *after* a Layer 4 plan reaches ``ready`` and consumes its per-day sessions
(see `Control_Spec_v8.md` — "Layer 5 — Supplemental parallel outputs" and the
LLM-call budget row "Layer 5 | None — supplemental, advisory only"). 5A is the
nutrition synthesis (`layer5.payload` — `PlanNutrition`); 5B (this module) is
the conditions/clothing advisor.

5B derives, for each training day that has an outdoor session at a locale with
coordinates, the *typical* conditions to prepare for — multi-year climate
normals around that calendar date at the locale (via `weather_client`, the same
source the race-week brief uses) — and maps them deterministically to a thermal
band, a clothing summary, a kit list and per-day advisory flags. It is **not** a
forecast: normals work for any plan date (the forecast horizon is only ~7–14
days), so the advisory is "dress for this, but check the live forecast nearer
the day". Days with no locale, or a locale with no coordinates, carry no
conditions row (best-effort, mirroring `weather_client`'s degrade-to-``None``).

Like 5A this is a parallel post-plan output keyed by date/locale — *not* a field
on `PlanSession` — so the training→supplemental dependency stays one-way.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThermalBand = Literal["freezing", "cold", "cool", "mild", "warm", "hot"]
ConditionsSource = Literal["climate_normals"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConditionsModelMeta(_Base):
    """Transparency record for how the advisory was derived + its thresholds."""

    model: str = "climate_normals_advisory_v1"
    normals_years: int = Field(ge=1)
    window_days: int = Field(ge=0)
    # Daily-high (°C) upper cutoff per band; the top band ("hot") has no cutoff.
    band_cutoffs_tmax_c: dict[str, float]
    heat_tmax_c: float
    cold_tmin_c: float
    wet_pct_threshold: int = Field(ge=0, le=100)


class DayConditions(_Base):
    """Per-day expected conditions + clothing/kit advisory for one locale."""

    date: date
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    locale_id: str
    locale_name: str | None = None
    session_ids: list[str]
    source: ConditionsSource = "climate_normals"
    temp_max_c: float
    temp_min_c: float
    wet_day_probability_pct: int = Field(ge=0, le=100)
    sample_years: int = Field(ge=1)
    thermal_band: ThermalBand
    clothing_summary: str
    kit_items: list[str] = Field(default_factory=list)
    advisory_flags: list[str] = Field(default_factory=list)


class PlanConditions(_Base):
    """The Layer 5B artifact for one plan version: per-day conditions + meta."""

    plan_version_id: int
    generated_at: datetime
    model_meta: ConditionsModelMeta
    days: list[DayConditions] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
