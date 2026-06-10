"""Layer 5A — per-day + plan-level nutrition synthesis payload schemas.

Layer 5 is the supplemental, advisory, **deterministic (zero-LLM)** tier that
runs *after* a Layer 4 plan reaches ``ready`` and consumes its per-day sessions
(see `Control_Spec_v8.md` — "Layer 5 — Supplemental parallel outputs",
"Layer 4 → Layer 5", and the LLM-call budget table row "Layer 5 | None —
supplemental, advisory only"). `Layer5_Spec.md` is not yet drafted; this module
is the first concrete Layer 5 output.

5A (this module) modulates the Layer 2E *phase* nutrition baseline
(`DailyNutritionBaseline.per_phase`, computed by
`layer2e.q_layer2e_nutrition_baseline_payload`) down to the *day* level using
the actual training load scheduled on each date, and surfaces race-day fueling
per event. The energy model **redistributes rather than inflates** the 2E
weekly energy: over a normal training week, Σ(per-day kcal) reconciles to the
2E phase daily target × days-in-week. See `layer5.builder` for the model.

The race-day fueling synthesis (`RaceFuelingPlan` + `build_race_day_fueling_plan`)
is intentionally a standalone, reusable structure so the future race-day plan
generator can consume it directly rather than reimplementing it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from layer4.context import (
    CaffeineRacedayPlan,
    DailyPhaseTargets,
    DietaryPatternFlag,
    MacroTargets,
)

PhaseName = Literal["Base", "Build", "Peak", "Taper"]
LoadTier = Literal["rest", "light", "moderate", "hard", "peak"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnergyModelMeta(_Base):
    """Transparency record for how per-day energy was derived."""

    model: str = "load_redistribution_v1"
    bmr_kcal: float = Field(ge=0.0)
    rmr_floor_mult: float = Field(gt=0.0)
    strength_met: float = Field(gt=0.0)
    zone_met: dict[str, float]


class DayNutrition(_Base):
    """Per-day nutrition target, load-modulated off the 2E phase baseline."""

    date: date
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    phase_name: PhaseName | None = None
    is_rest_day: bool
    is_race_day: bool
    session_ids: list[str]
    training_duration_min: int = Field(ge=0)
    # Net training energy expenditure for the day (above resting metabolism).
    exercise_kcal: int = Field(ge=0)
    total_kcal: int = Field(ge=0)
    macros: MacroTargets
    load_tier: LoadTier
    cho_floor_constrained: bool = False
    non_training_floor_applied: bool = False
    race_fueling_event_ids: list[str] = Field(default_factory=list)
    fueling_note: str


class WeekReconciliation(_Base):
    """Per-week proof that per-day kcal redistribute the 2E phase baseline."""

    week_key: str
    week_start: date
    phase_name: PhaseName | None = None
    days: int = Field(ge=1)
    baseline_daily_kcal: int = Field(ge=0)
    weekly_baseline_kcal: int = Field(ge=0)
    weekly_assigned_kcal: int = Field(ge=0)
    non_training_floor_applied: bool = False


class RaceFuelingPlan(_Base):
    """Standalone, reusable per-event race-day fueling plan.

    Wraps a Layer 2E `RaceDayFueling` into a consume-ready structure shared by
    the training-plan view *and* the (future) race-day plan generator.
    `estimated_totals` is left ``None`` until an event duration is known — the
    race-day generator fills it once it resolves the event's expected time.
    """

    event_id: str
    event_name: str
    event_date: date | None = None
    duration_tier: Literal[
        "tier_short", "tier_mid", "tier_long", "tier_expedition", "tier_extended_expedition"
    ]
    cho_g_per_hr: tuple[float, float]
    na_mg_per_hr: tuple[float, float]
    fluid_ml_per_hr: tuple[float, float] | None = None
    protein_after: tuple[int, float, float] | None = None
    caffeine: CaffeineRacedayPlan | None = None
    recommended_formats: list[str] = Field(default_factory=list)
    blocked_formats: list[str] = Field(default_factory=list)
    sleep_dep_overlay_applies: bool = False
    estimated_totals: dict[str, float] | None = None
    notes: list[str] = Field(default_factory=list)


class PlanNutrition(_Base):
    """The Layer 5A artifact for one plan version: top-level baseline + per-day."""

    plan_version_id: int
    generated_at: datetime
    body_weight_kg: float = Field(gt=0.0)
    energy_model: EnergyModelMeta
    # Top-level "every-day" baseline (passthrough of the 2E phase targets).
    per_phase_baseline: dict[str, DailyPhaseTargets]
    days: list[DayNutrition]
    week_reconciliation: list[WeekReconciliation]
    race_fueling: list[RaceFuelingPlan] = Field(default_factory=list)
    standing_supplement_notes: str | None = None
    dietary_flags: list[DietaryPatternFlag] = Field(default_factory=list)
