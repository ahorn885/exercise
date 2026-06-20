"""Layer 5 — supplemental, deterministic advisory outputs (zero-LLM).

5A nutrition synthesis: per-day + plan-level nutrition modulated off the Layer 2E
phase baseline using the Layer 4 plan's scheduled training load.

5B conditions synthesis: per-day expected conditions + a clothing/kit advisory,
derived from climate normals at each session's locale.
"""

from __future__ import annotations

from layer5.builder import (
    ENERGY_MODEL_NAME,
    build_plan_nutrition,
    build_race_day_fueling_plan,
)
from layer5.conditions_builder import (
    CONDITIONS_MODEL_NAME,
    build_plan_conditions,
)
from layer5.conditions_orchestrator import generate_and_persist_plan_conditions
from layer5.conditions_payload import (
    ConditionsModelMeta,
    DayConditions,
    PlanConditions,
)
from layer5.orchestrator import generate_and_persist_plan_nutrition
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
    "generate_and_persist_plan_nutrition",
    "DayNutrition",
    "EnergyModelMeta",
    "PlanNutrition",
    "RaceFuelingPlan",
    "WeekReconciliation",
    "CONDITIONS_MODEL_NAME",
    "build_plan_conditions",
    "generate_and_persist_plan_conditions",
    "ConditionsModelMeta",
    "DayConditions",
    "PlanConditions",
]
