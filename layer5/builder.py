"""Layer 5A nutrition synthesis — deterministic per-day + race-day builder.

Pure functions (no DB, no LLM). Given a plan version's persisted sessions plus
the Layer 2E nutrition baseline, produce a `PlanNutrition` artifact that varies
day to day with the scheduled training load.

Energy model (``load_redistribution_v1``)
-----------------------------------------
Layer 2E gives a per-*phase* daily calorie target
(``DailyPhaseTargets.daily_calorie_target_kcal`` = BMR × activity_multiplier,
`layer2e/builder.py`). That number is a *weekly average* — it already bakes in
average training load but is flat across all seven days. 5A redistributes it:

1. For a training week, weekly energy ``W = n_days × phase_daily_target``.
2. Per-day **net** training expenditure ``E_day`` is estimated from the day's
   sessions: ``(MET − 1) × body_weight_kg × hours``, summed over cardio blocks
   (MET by HR/power zone) and strength work.
3. The non-training baseline shared by every day is
   ``B = (W − ΣE_day) / n_days`` — clamped to a resting floor (BMR × 1.2,
   matching 2E's ``low_calorie_target_relative_to_rmr`` floor).
4. ``total_kcal[day] = B + E_day``.

So rest days land near the resting floor, long/key days take the surplus, and —
absent the floor clamp — Σ(per-day kcal) over the week equals ``W``. No new
weekly energy is invented; it is only moved around.

Per-day macros: protein held ≈ constant g/kg (recovery-driven), fat held at the
phase value (already ≥ floor), carbohydrate absorbs the day-to-day swing
("fuel for the work required"), with a glycogen-maintenance CHO floor.

Race-week carbohydrate loading
------------------------------
The ``_CARB_LOAD_DAYS`` (2) calendar days before each race event are flagged as
carb-loading days: carbohydrate is pinned at ``_CARB_LOAD_G_PER_KG`` (10 g/kg)
for glycogen supercompensation (ACSM/AND/DC 2016: 10-12 g/kg/day for 36-48 h
before events >90 min). Unlike a normal day, loading drives total energy *up*
(CHO is the fixed target, not the residual), so a loading week's assigned energy
exceeds the redistribution baseline by ``carb_loading_surplus_kcal`` — a
deliberate surplus, not a redistribution. The race day itself fuels per hour
(``race_fueling``), so it is excluded from the loading window. Per Andy
(2026-06-20) every target event is an endurance event >90 min, so all events
qualify — no per-event duration gate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DietaryPatternFlag,
    MacroTargets,
    RaceDayFueling,
)
from layer4.payload import PlanSession
from layer5.payload import (
    DayNutrition,
    EnergyModelMeta,
    PlanNutrition,
    RaceFuelingPlan,
    WeekReconciliation,
)

# ─── §5A.2 energy constants ──────────────────────────────────────────────────

# Endurance HR/power zone → MET (≈ kcal·kg⁻¹·h⁻¹). Deliberately
# discipline-agnostic in v1: the zone already normalises physiological intensity
# across disciplines, and MET tracks intensity more than modality.
_ZONE_MET: dict[str, float] = {
    "Z1": 4.0,
    "Z2": 6.0,
    "Z3": 8.0,
    "Z4": 10.0,
    "Z5": 12.0,
    "mixed": 7.0,
}
# Fallback when a cardio session has no per-block zones.
_SUMMARY_MET: dict[str, float] = {
    "easy": 5.0,
    "moderate": 7.0,
    "hard": 9.0,
    "mixed": 7.0,
    "rest": 0.0,
}
_STRENGTH_MET = 5.0

# Resting floor for the non-training baseline — matches the 2E
# `low_calorie_target_relative_to_rmr` floor (BMR × 1.2, `layer2e/builder.py`).
_RMR_FLOOR_MULT = 1.2
# Glycogen-maintenance carbohydrate floor on low-load days (g/kg/day).
_CHO_FLOOR_G_PER_KG = 3.0

# Race-week carbohydrate loading — glycogen supercompensation in the days before
# a race. 10 g/kg/day across the 2 days pre-race maximises muscle glycogen
# (ACSM/AND/DC 2016: 10-12 g/kg/day for 36-48 h before events >90 min). Andy
# 2026-06-20: we coach endurance athletes, so every target event qualifies — no
# per-event duration gate.
_CARB_LOAD_G_PER_KG = 10.0
_CARB_LOAD_DAYS = 2

_TOTAL_ROUND = 25  # round per-day kcal to the nearest 25

ENERGY_MODEL_NAME = "load_redistribution_v1"


# ─── per-session / per-day energy ────────────────────────────────────────────


def _session_exercise_kcal(session: PlanSession, body_weight_kg: float) -> float:
    """Net training energy (above resting metabolism) for one session, kcal."""
    if session.kind == "rest" or session.duration_min <= 0:
        return 0.0

    if session.kind == "strength":
        hours = session.duration_min / 60.0
        return max(0.0, (_STRENGTH_MET - 1.0) * body_weight_kg * hours)

    # cardio
    if session.cardio_blocks:
        total = 0.0
        for block in session.cardio_blocks:
            met = _ZONE_MET.get(block.intensity_zone, _ZONE_MET["mixed"])
            hours = block.duration_min / 60.0
            total += (met - 1.0) * body_weight_kg * hours
        return max(0.0, total)

    # cardio without block detail — fall back to the session-level summary
    met = _SUMMARY_MET.get(session.intensity_summary, _SUMMARY_MET["moderate"])
    hours = session.duration_min / 60.0
    return max(0.0, (met - 1.0) * body_weight_kg * hours)


def _load_tier(is_rest: bool, exercise_kcal: float, body_weight_kg: float) -> str:
    if is_rest or exercise_kcal <= 1.0:
        return "rest"
    per_kg = exercise_kcal / body_weight_kg  # ≈ MET-hours of net work
    if per_kg < 4.0:
        return "light"
    if per_kg < 8.0:
        return "moderate"
    if per_kg < 14.0:
        return "hard"
    return "peak"


_TIER_NOTE: dict[str, str] = {
    "rest": "Recovery day — lower carbohydrate; prioritise protein distribution and whole foods.",
    "light": "Light day — modest carbohydrate; eat to appetite around the session.",
    "moderate": "Moderate load — fuel before and refuel within 60 min after the session.",
    "hard": "High-carb day — front-load carbohydrate before the key session and replenish after.",
    "peak": "Peak load — maximise carbohydrate availability; fuel during the session.",
}


def _fueling_note(tier: str, is_race_day: bool, cho_floor_constrained: bool) -> str:
    if is_race_day:
        return "Race day — follow the per-event fueling plan; carbohydrate, sodium and fluid are prescribed per hour."
    note = _TIER_NOTE.get(tier, _TIER_NOTE["moderate"])
    if cho_floor_constrained:
        note += " Carbohydrate held at the glycogen-maintenance floor."
    return note


def _carb_load_note(cho_g: int) -> str:
    return (
        f"Carb-load day — raise carbohydrate to ~10 g/kg (~{cho_g} g) to top off "
        "muscle glycogen for the race; keep fat and fibre low and hydrate well."
    )


# ─── macros ──────────────────────────────────────────────────────────────────


def _day_macros(
    phase_targets: DailyPhaseTargets,
    body_weight_kg: float,
    total_kcal: int,
) -> tuple[MacroTargets, bool]:
    """Protein constant, fat held at phase value, CHO absorbs the kcal swing."""
    base = phase_targets.macros

    protein_g = round(base.protein_g_per_kg * body_weight_kg)
    protein_kcal = protein_g * 4

    fat_g = base.fat_g
    fat_kcal = fat_g * 9

    cho_kcal = total_kcal - protein_kcal - fat_kcal
    cho_floor_kcal = round(_CHO_FLOOR_G_PER_KG * body_weight_kg) * 4
    cho_floor_constrained = False
    if cho_kcal < cho_floor_kcal:
        cho_kcal = cho_floor_kcal
        cho_floor_constrained = True

    cho_g = round(cho_kcal / 4.0)
    cho_g_per_kg = cho_g / body_weight_kg if body_weight_kg > 0 else 0.0

    macros = MacroTargets(
        cho_g=int(cho_g),
        cho_g_per_kg=round(float(cho_g_per_kg), 3),
        cho_kcal=int(cho_g * 4),
        protein_g=int(protein_g),
        protein_g_per_kg=round(float(base.protein_g_per_kg), 3),
        protein_kcal=int(protein_kcal),
        fat_g=int(fat_g),
        fat_kcal=int(fat_g * 9),
        fat_floor_constrained=bool(base.fat_floor_constrained),
    )
    return macros, cho_floor_constrained


def _carb_load_macros(
    phase_targets: DailyPhaseTargets, body_weight_kg: float
) -> MacroTargets:
    """Race-week carb-loading macros — CHO pinned at the loading target for
    glycogen supercompensation; protein held at the phase g/kg (recovery /
    lean-mass); fat held at the phase value (already near the 1.0 g/kg floor for
    endurance athletes — loading runs low-fat / low-fibre). Total energy is
    driven *up* by the CHO target rather than CHO absorbing a fixed budget."""
    base = phase_targets.macros
    protein_g = round(base.protein_g_per_kg * body_weight_kg)
    fat_g = base.fat_g
    cho_g = round(_CARB_LOAD_G_PER_KG * body_weight_kg)
    cho_g_per_kg = cho_g / body_weight_kg if body_weight_kg > 0 else 0.0
    return MacroTargets(
        cho_g=int(cho_g),
        cho_g_per_kg=round(float(cho_g_per_kg), 3),
        cho_kcal=int(cho_g * 4),
        protein_g=int(protein_g),
        protein_g_per_kg=round(float(base.protein_g_per_kg), 3),
        protein_kcal=int(protein_g * 4),
        fat_g=int(fat_g),
        fat_kcal=int(fat_g * 9),
        fat_floor_constrained=bool(base.fat_floor_constrained),
    )


# ─── race-day fueling (standalone, reusable) ─────────────────────────────────


def build_race_day_fueling_plan(
    race_day_fueling: list[RaceDayFueling],
    *,
    event_dates: dict[str, date] | None = None,
) -> list[RaceFuelingPlan]:
    """Project Layer 2E `RaceDayFueling` rows into consume-ready per-event plans.

    Standalone so the future race-day plan generator can call it directly.
    """
    dates = event_dates or {}
    plans: list[RaceFuelingPlan] = []
    for rdf in race_day_fueling:
        fluid = None
        if rdf.fluid_ml_per_hr_low is not None and rdf.fluid_ml_per_hr_high is not None:
            fluid = (rdf.fluid_ml_per_hr_low, rdf.fluid_ml_per_hr_high)
        plans.append(
            RaceFuelingPlan(
                event_id=rdf.event_id,
                event_name=rdf.event_name,
                event_date=dates.get(rdf.event_id),
                duration_tier=rdf.duration_tier,
                cho_g_per_hr=(rdf.cho_g_per_hr_low, rdf.cho_g_per_hr_high),
                na_mg_per_hr=(rdf.na_mg_per_hr_low, rdf.na_mg_per_hr_high),
                fluid_ml_per_hr=fluid,
                protein_after=rdf.protein_g_per_hr_after_hr_n,
                caffeine=rdf.caffeine_plan,
                recommended_formats=list(rdf.recommended_formats),
                blocked_formats=list(rdf.blocked_formats),
                sleep_dep_overlay_applies=rdf.sleep_dep_overlay_applies,
                notes=list(rdf.notes),
            )
        )
    return plans


# ─── main entry ──────────────────────────────────────────────────────────────


def _phase_targets(
    baseline: DailyNutritionBaseline, phase: str | None
) -> tuple[str | None, DailyPhaseTargets]:
    per = baseline.per_phase
    if phase is not None and phase in per:
        return phase, per[phase]
    fallback_key = next(iter(per))
    return fallback_key, per[fallback_key]


def _day_phase(sessions_for_day: list[PlanSession]) -> str | None:
    for s in sessions_for_day:
        if s.phase_metadata is not None:
            return s.phase_metadata.phase_name
    return None


def build_plan_nutrition(
    *,
    plan_version_id: int,
    sessions: list[PlanSession],
    baseline: DailyNutritionBaseline,
    bmr_kcal: float,
    body_weight_kg: float,
    race_day_fueling: list[RaceDayFueling] | None = None,
    event_dates: dict[str, date] | None = None,
    standing_supplement_notes: str | None = None,
    dietary_flags: list[DietaryPatternFlag] | None = None,
    generated_at: datetime | None = None,
) -> PlanNutrition:
    """Build the Layer 5A nutrition artifact for one plan version.

    `sessions` is the plan version's persisted `PlanSession` list. `baseline`,
    `bmr_kcal`, `race_day_fueling`, `dietary_flags` and the standing supplement
    notes come from the Layer 2E payload. Pure + deterministic: identical inputs
    yield an identical artifact (modulo the supplied `generated_at`).
    """
    if body_weight_kg <= 0:
        raise ValueError("body_weight_kg must be > 0")
    if not baseline.per_phase:
        raise ValueError("baseline.per_phase must be non-empty")

    generated_at = generated_at or datetime.now(timezone.utc)
    race_day_fueling = race_day_fueling or []
    event_dates = event_dates or {}

    # Dates that host a race event (for per-day flags / notes).
    race_dates_by_id = {eid: d for eid, d in event_dates.items()}
    race_event_ids_by_date: dict[date, list[str]] = defaultdict(list)
    fueling_event_ids = {rdf.event_id for rdf in race_day_fueling}
    for eid, d in race_dates_by_id.items():
        if eid in fueling_event_ids:
            race_event_ids_by_date[d].append(eid)

    # Group sessions by date, preserving input order within a day.
    by_date: dict[date, list[PlanSession]] = defaultdict(list)
    for sess in sessions:
        by_date[sess.date].append(sess)

    # Per-day net training energy + phase.
    day_exercise: dict[date, float] = {}
    day_phase: dict[date, str | None] = {}
    for d, day_sessions in by_date.items():
        day_exercise[d] = sum(
            _session_exercise_kcal(s, body_weight_kg) for s in day_sessions
        )
        day_phase[d] = _day_phase(day_sessions)

    # Carb-loading window — the `_CARB_LOAD_DAYS` calendar days before each race
    # event. The race day itself fuels per hour (race_fueling), so it's excluded;
    # only days present in the plan can carry a target.
    race_dates = set(race_event_ids_by_date)
    carb_load_dates: set[date] = set()
    for rd in race_dates:
        for back in range(1, _CARB_LOAD_DAYS + 1):
            load_day = rd - timedelta(days=back)
            if load_day in by_date and load_day not in race_dates:
                carb_load_dates.add(load_day)

    # Group dates into ISO weeks; resolve each week's dominant phase + baseline.
    weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
    for d in by_date:
        iso = d.isocalendar()
        weeks[(iso[0], iso[1])].append(d)

    # Pass 1 — per-week redistribution baseline (training energy only).
    day_total: dict[date, int] = {}
    day_floor_applied: dict[date, bool] = {}
    week_meta: dict[tuple[int, int], dict[str, Any]] = {}

    for (iso_year, iso_week), week_dates in sorted(weeks.items()):
        week_dates.sort()
        n = len(week_dates)

        phase_votes = Counter(
            day_phase[d] for d in week_dates if day_phase[d] is not None
        )
        dominant_phase = phase_votes.most_common(1)[0][0] if phase_votes else None
        resolved_phase, phase_targets = _phase_targets(baseline, dominant_phase)
        baseline_daily = phase_targets.daily_calorie_target_kcal

        weekly_baseline = n * baseline_daily
        week_training = sum(day_exercise[d] for d in week_dates)
        base = (weekly_baseline - week_training) / n if n else float(baseline_daily)

        floor = bmr_kcal * _RMR_FLOOR_MULT
        floor_applied = base < floor
        if floor_applied:
            base = floor

        for d in week_dates:
            raw = base + day_exercise[d]
            day_total[d] = int(round(raw / _TOTAL_ROUND) * _TOTAL_ROUND)
            day_floor_applied[d] = floor_applied

        week_meta[(iso_year, iso_week)] = {
            "resolved_phase": resolved_phase,
            "days": n,
            "baseline_daily": baseline_daily,
            "weekly_baseline": weekly_baseline,
            "floor_applied": floor_applied,
        }

    # Pass 2 — per-day records. Carb-load days pin CHO at the loading target and
    # recompute total upward (loading adds energy beyond the redistribution).
    days: list[DayNutrition] = []
    week_assigned: dict[tuple[int, int], int] = defaultdict(int)
    week_load_surplus: dict[tuple[int, int], int] = defaultdict(int)

    for d in sorted(by_date):
        day_sessions = by_date[d]
        e_kcal = day_exercise[d]
        is_rest = all(s.kind == "rest" for s in day_sessions)
        race_ids = race_event_ids_by_date.get(d, [])
        is_race = bool(race_ids)
        is_carb_load = d in carb_load_dates

        resolved_phase, phase_targets = _phase_targets(baseline, day_phase[d])
        tier = _load_tier(is_rest, e_kcal, body_weight_kg)

        if is_carb_load:
            macros = _carb_load_macros(phase_targets, body_weight_kg)
            total = macros.cho_kcal + macros.protein_kcal + macros.fat_kcal
            cho_constrained = False
            note = _carb_load_note(macros.cho_g)
        else:
            total = day_total[d]
            macros, cho_constrained = _day_macros(phase_targets, body_weight_kg, total)
            note = _fueling_note(tier, is_race, cho_constrained)

        iso = d.isocalendar()
        wk = (iso[0], iso[1])
        week_assigned[wk] += total
        if is_carb_load:
            week_load_surplus[wk] += total - day_total[d]

        days.append(
            DayNutrition(
                date=d,
                day_of_week=day_sessions[0].day_of_week,
                phase_name=resolved_phase,  # type: ignore[arg-type]
                is_rest_day=is_rest,
                is_race_day=is_race,
                session_ids=[s.session_id for s in day_sessions],
                training_duration_min=sum(s.duration_min for s in day_sessions),
                exercise_kcal=int(round(e_kcal)),
                total_kcal=total,
                macros=macros,
                load_tier=tier,  # type: ignore[arg-type]
                cho_floor_constrained=cho_constrained,
                non_training_floor_applied=day_floor_applied[d],
                carb_loading_applied=is_carb_load,
                race_fueling_event_ids=race_ids,
                fueling_note=note,
            )
        )

    # Pass 3 — week reconciliation from the final per-day totals, so the
    # carb-load surplus shows up and Σ(per-day total) == Σ(weekly_assigned).
    week_recon: list[WeekReconciliation] = []
    for (iso_year, iso_week), meta in sorted(week_meta.items()):
        wk = (iso_year, iso_week)
        week_recon.append(
            WeekReconciliation(
                week_key=f"{iso_year}-W{iso_week:02d}",
                week_start=date.fromisocalendar(iso_year, iso_week, 1),
                phase_name=meta["resolved_phase"],  # type: ignore[arg-type]
                days=meta["days"],
                baseline_daily_kcal=meta["baseline_daily"],
                weekly_baseline_kcal=meta["weekly_baseline"],
                weekly_assigned_kcal=week_assigned[wk],
                non_training_floor_applied=meta["floor_applied"],
                carb_loading_surplus_kcal=week_load_surplus[wk],
            )
        )

    return PlanNutrition(
        plan_version_id=plan_version_id,
        generated_at=generated_at,
        body_weight_kg=body_weight_kg,
        energy_model=EnergyModelMeta(
            model=ENERGY_MODEL_NAME,
            bmr_kcal=round(float(bmr_kcal), 1),
            rmr_floor_mult=_RMR_FLOOR_MULT,
            strength_met=_STRENGTH_MET,
            zone_met=dict(_ZONE_MET),
        ),
        per_phase_baseline=dict(baseline.per_phase),
        days=days,
        week_reconciliation=week_recon,
        race_fueling=build_race_day_fueling_plan(
            race_day_fueling, event_dates=event_dates
        ),
        standing_supplement_notes=standing_supplement_notes,
        dietary_flags=list(dietary_flags or []),
    )
