"""Plan Management read-time derivations (`Plan_Management_Spec_v1.md`).

Plan Management is a deterministic derivation subsystem (no LLM) that assembles
the `PlanManagementState` contract Layer 2E imports. This module implements the
two #221 surfaces:

- **§5.1 `derive_current_phase`** — which periodization phase is active today,
  from the Layer 3B shape + plan start (the *producer* side; 2E §5.2/§5.3
  consume `current_phase`).
- **§5.2 `derive_heat_acclim_state`** — the athlete's heat-acclimation `level`
  from logged training conditions, with a `heat_acclim_data_sparse` advisory
  when the signal is thin. Produces the `HeatAcclimState` 2E §5.8 consumes.

The remaining contract field — `expected_race_temp_c` (§5.3) — plus the
`weather_client.get_forecast_high` leg and the 2E §5.8 overlay wiring land with
the #220 de-stub PR (`Plan_Management_Spec_v1.md` §12).

Heat-acclim state is **derived, never stored** (Athlete_Data_Integration_Spec
§2.6): no new schema, recomputed on read from `public.conditions_log`.
"""

from __future__ import annotations

from datetime import date, timedelta

from layer4.context import HeatAcclimState, Layer3BPayload
from layer4.phase_structure import phase_for_date, phase_structure_from_3b


# ─── §5.2 heat-acclim constants ──────────────────────────────────────────────

# §5.2.1: `conditions_log.temp_f` is °F; the 25 °C acclim threshold is exactly
# 77 °F. Compare in the stored unit to avoid round-trip drift — a row counts
# when `temp_f > 77.0`.
_HOT_DAY_THRESHOLD_F = 77.0
_WINDOW_DAYS = 30
# §5.2.4: <5 logged condition-days total in the window → sparse-data advisory.
_SPARSE_MIN_DAYS = 5
# §5.2.3 banding on distinct hot days in the last 30, grounded in the 10–14-day
# acclimatization timeline 2E §5.8 already encodes.
_MODERATE_FLOOR_DAYS = 5
_HIGH_FLOOR_DAYS = 14


def derive_current_phase(
    layer3b_payload: Layer3BPayload,
    plan_start: date,
    today: date,
    total_weeks: int | None = None,
) -> str:
    """`Plan_Management_Spec_v1.md` §5.1 — the periodization phase active on
    ``today``, derived from the Layer 3B shape + plan start (NOT a Layer 4
    persisted calendar; Andy 2026-06-29).

    The spec pseudocode walks an abstract "ordered list of phase blocks". The
    concrete 3B contract (`PeriodizationShape`) carries per-phase week counts
    only for ``mode == 'custom'``; for standard/compressed/extended the week
    spans come from `Layer4_Spec.md` §6.1 proportions. Rather than duplicate
    that allocation math, this reuses Layer 4's canonical decomposition
    (`phase_structure_from_3b` → `phase_for_date`) so Plan Management's phase
    boundaries match the ones Layer 4 actually renders into — minimizing the
    PM-1 divergence the spec flags as the §5.1 soft spot.

    ``total_weeks`` is the plan horizon Layer 4 used (event mode:
    ``plan_create._compute_total_weeks``); ``None`` falls back to
    `phase_structure_from_3b`'s 12-week open-ended default.

    Edge behavior (spec §5.1 / §9): before plan start → first block; after the
    last block → last block (a completed/over-running plan reads as Taper, the
    conservative low-volume default). Raises (via `phase_structure_from_3b`)
    when the shape is degenerate — a phase with no plan is a contract
    violation, not a default.
    """
    structure = phase_structure_from_3b(layer3b_payload, plan_start, total_weeks)
    week_index = max(0, (today - plan_start).days // 7)

    if today < plan_start:
        phase = structure.phases[0].phase_name
    else:
        spec = phase_for_date(structure, today)
        phase = spec.phase_name if spec is not None else structure.phases[-1].phase_name

    # Rule #15 — log the inputs the phase decision rested on.
    print(
        f"plan_management.derive_current_phase: phase={phase} "
        f"plan_start={plan_start.isoformat()} today={today.isoformat()} "
        f"week_index={week_index} mode={layer3b_payload.periodization_shape.mode} "
        f"total_weeks={structure.total_weeks}"
    )
    return phase


def _band_level(days_at_temp: int) -> str:
    """§5.2.3 banding: 0–4 → low, 5–13 → moderate, ≥14 → high."""
    if days_at_temp >= _HIGH_FLOOR_DAYS:
        return "high"
    if days_at_temp >= _MODERATE_FLOOR_DAYS:
        return "moderate"
    return "low"


def derive_heat_acclim_state(
    db,
    user_id: int,
    today: date,
) -> tuple[HeatAcclimState, bool]:
    """`Plan_Management_Spec_v1.md` §5.2 — derive `HeatAcclimState` at read time
    from `public.conditions_log` (closes #221).

    Returns ``(state, data_sparse)``. ``data_sparse`` is True when the athlete
    logged fewer than 5 condition-days total in the 30-day window (§5.2.4) — the
    consumer (2E §5.8) surfaces a `heat_acclim_data_sparse` advisory so a `low`
    reading from absent data isn't misread as a confirmed-unacclimatized one.
    Sparse data forces ``level='low'`` (the conservative default that biases
    toward firing 2E's heat-acclim-gap flag — the safe direction for a hot race).

    `temp_f` NULL is excluded from the hot-day count (`temp_f > 77.0` is
    NULL-safe-false). Counts distinct *days*, not rows — heat exposure is a
    per-day stimulus (§5.2.2).
    """
    cutoff = (today - timedelta(days=_WINDOW_DAYS)).isoformat()
    cur = db.execute(
        """
        SELECT
            COUNT(DISTINCT date) AS total_days,
            COUNT(DISTINCT CASE WHEN temp_f > ? THEN date END) AS hot_days
          FROM conditions_log
         WHERE user_id = ?
           AND date >= ?
        """,
        (_HOT_DAY_THRESHOLD_F, user_id, cutoff),
    )
    row = cur.fetchone()
    total_days = int(row["total_days"] or 0) if row else 0
    hot_days = int(row["hot_days"] or 0) if row else 0

    data_sparse = total_days < _SPARSE_MIN_DAYS
    level = "low" if data_sparse else _band_level(hot_days)

    # Rule #15 — log the counts + chosen level + the sparse branch.
    print(
        f"plan_management.derive_heat_acclim_state: user_id={user_id} "
        f"days_at_temp_last_30={hot_days} total_logged_days={total_days} "
        f"level={level} data_sparse={data_sparse} "
        f"window_from={cutoff} today={today.isoformat()}"
    )

    state = HeatAcclimState(
        level=level,
        days_at_temp_last_30=hot_days,
        last_assessment=today,
    )
    return state, data_sparse


__all__ = ["derive_current_phase", "derive_heat_acclim_state"]
