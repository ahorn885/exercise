"""Layer 5 — supplemental, deterministic advisory outputs (zero-LLM).

5A nutrition synthesis: per-day + plan-level nutrition modulated off the Layer 2E
phase baseline using the Layer 4 plan's scheduled training load.
"""

from __future__ import annotations

from layer5.builder import (
    ENERGY_MODEL_NAME,
    build_plan_nutrition,
    build_race_day_fueling_plan,
)
from layer5.payload import (
    DayNutrition,
    EnergyModelMeta,
    PlanNutrition,
    RaceFuelingPlan,
    WeekReconciliation,
)

__all__ = [
    "ENERGY_MODEL_NAME",
    "build_plan_nutrition",
    "build_race_day_fueling_plan",
    "DayNutrition",
    "EnergyModelMeta",
    "PlanNutrition",
    "RaceFuelingPlan",
    "WeekReconciliation",
]
