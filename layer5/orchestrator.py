"""Layer 5A nutrition stage — assemble persisted inputs, build, persist.

Deterministic glue (zero-LLM) between the durable substrate and the pure
`layer5.builder`. Runs AFTER a plan reaches `ready`: it reads the Layer 2E
inputs snapshot stashed at generation time (`plan_nutrition_inputs`) plus the
plan's persisted sessions, runs `build_plan_nutrition`, and persists the
`PlanNutrition` artifact. Also the entry point for the manual regenerate action.

Best-effort by contract: callers wrap this so a fault can never affect the
already-`ready` plan. Returns None (rather than raising) for the expected
"can't run" cases — no inputs snapshot, no sessions, or a non-positive body
weight — so a caller's `if result is None` branch can message the user without
treating it as an error.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from layer4.context import Layer2EPayload
from layer5.builder import build_plan_nutrition
from layer5.payload import PlanNutrition
from plan_nutrition_repo import (
    load_plan_nutrition_inputs,
    persist_plan_nutrition,
)
from plan_sessions_repo import load_plan_sessions_by_version


def generate_and_persist_plan_nutrition(
    db: Any, user_id: int, plan_version_id: int
) -> PlanNutrition | None:
    """Build + persist the Layer 5A nutrition artifact for `plan_version_id`.

    Returns the `PlanNutrition` on success, or None when nutrition cannot be
    produced (no stashed inputs, no sessions, or non-positive body weight).
    Caller owns the transaction boundary — this helper does NOT commit.
    """
    inputs = load_plan_nutrition_inputs(db, plan_version_id)
    if inputs is None:
        return None

    body_weight_kg = float(inputs.get("body_weight_kg") or 0.0)
    if body_weight_kg <= 0:
        return None

    sessions = load_plan_sessions_by_version(db, plan_version_id)
    if not sessions:
        return None

    l2e = Layer2EPayload.model_validate(inputs["layer2e_payload"])
    event_dates = {
        eid: date.fromisoformat(d)
        for eid, d in (inputs.get("event_dates") or {}).items()
    }

    nutrition = build_plan_nutrition(
        plan_version_id=plan_version_id,
        sessions=sessions,
        baseline=l2e.daily_nutrition_baseline,
        bmr_kcal=l2e.bmr_kcal,
        body_weight_kg=body_weight_kg,
        race_day_fueling=l2e.race_day_fueling,
        event_dates=event_dates,
        supplement_integration=l2e.supplement_integration,
        dietary_flags=l2e.dietary_pattern_adjustments,
    )
    persist_plan_nutrition(db, user_id, nutrition)
    return nutrition
