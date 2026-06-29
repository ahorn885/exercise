"""Layer 2E builder — nutrition baseline query node.

Per `Layer2E_Spec.md` §3 (function signature) + §5 (algorithm). Pure query
node: deterministic given inputs, no LLM involvement. One indexed SELECT
per phase on `layer0.phase_load_weekly_totals` (4 SELECTs total) — every
other path is pure-Python math against spec-internal constant tables.

This is the **vertical-slice** ship per Andy 2026-05-19 scope pick:

  §5.2 BMR + activity multiplier   — full
  §5.3 macro split by phase         — full
  §5.4 race-day fueling per event   — full (base bands + sport mod +
                                      tolerance mod + format ranking +
                                      caffeine plan)
  §5.5 supplement integration       — **STUB** (Layer 1 §I deploys
                                      `supplement_protocol_notes: str`,
                                      not the spec's structured
                                      `list[AthleteSupplementRecord]`;
                                      §I.1 form refresh closes this)
  §5.6 dietary pattern adjustments  — full
  §5.7 sleep-dep overlay            — simplified (consumes the flat
                                      `Layer1Lifestyle.sleep_deprivation_*`
                                      fields rather than the spec's
                                      `SleepDepProfile` substructure)
  §5.8 heat acclim overlay          — **STUB** (PlanManagementState +
                                      HeatAcclimState contracts not yet
                                      written per `Layer2E_Spec.md` §5.8
                                      + open items 2E-2/3/4 — every event
                                      surfaces `temp_signal='unknown'`
                                      with a `race_temp_unknown` flag)
  §5.9 HITL triggers                — none active (the food-allergy gate 5
                                      was retired with the food_allergies
                                      capture; gates 1-4 require structured
                                      supplements + a pregnancy field
                                      that aren't deployed yet)

Drift translations between spec §3 and deployed `Layer1*` types
(documented inline at use site):

  spec sex 'M'/'F'                → Layer1Identity.sex 'male'/'female'
  spec status 'Current'/'History' → status 'Active'/'Resolved'/'Inactive'
                                    (Active → Current; Resolved+Inactive
                                    → History)
  spec dietary_pattern Title Case → list[str], free-form; matched
                                    case-insensitively
  spec salt_tolerance Low/Standard/High
                                  → low/moderate/high
  spec caffeine strategy 4-enum   → caffeine_loading/taper/maintain/avoid

`current_phase` arrives inside the §3 `plan_management_state` contract
(`Plan_Management_Spec_v1.md` §3); it is retained for spec-shape compliance,
but the algorithm computes daily baselines for all four phases per §5.2.3
'cross-phase visibility' — Layer 4 needs the projection across the
periodization, not only the active phase. The same `plan_management_state`
carries the `heat_acclim_state` + `expected_race_temp_c` the §5.8 overlay
consumes (#220 de-stub).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from layer4.context import (
    AthleteSupplementRecord,
    CaffeineRacedayPlan,
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DietaryPatternFlag,
    HeatAcclimEventAdjustment,
    HeatAcclimState,
    HealthConditionRecord,
    IntegratedSupplement,
    Layer1HealthStatus,
    Layer1Identity,
    Layer1Lifestyle,
    Layer1Performance,
    Layer2ADiscipline,
    Layer2ECoachingFlag,
    Layer2EHitlItem,
    Layer2EPayload,
    Layer2ETargetEvent,
    MacroTargets,
    PlanManagementState,
    RaceDayFueling,
    RaceDaySupplementSuggestion,
    SleepDepFuelingOverlay,
    SupplementIntegrationPayload,
)

logger = logging.getLogger(__name__)


# ─── Constants ───────────────────────────────────────────────────────────────


_REQUIRED_ETL_KEYS: frozenset[str] = frozenset({"0A"})
_PHASES: tuple[str, ...] = ("Base", "Build", "Peak", "Taper")

# §4 sanity floors (preconditions #2 + #3)
_BODY_WEIGHT_MIN_KG: float = 20.0
_HEIGHT_MIN_CM: float = 100.0

# §5.2.2 multiplier band table (Phase × volume tier). Indexed by phase
# then by `_volume_tier_index` based on weekly hours midpoint.
_MULTIPLIER_BANDS: dict[str, tuple[float, float, float, float]] = {
    # (low <6 hr, mid 6-10, high 10-15, very high 15+)
    "Base": (1.40, 1.55, 1.70, 1.85),
    "Build": (1.60, 1.75, 1.90, 2.05),
    "Peak": (1.75, 1.90, 2.10, 2.30),
    "Taper": (1.55, 1.70, 1.85, 2.00),
}
_PHASE_DEFAULT_MULTIPLIER: dict[str, float] = {
    "Base": 1.55, "Build": 1.75, "Peak": 1.90, "Taper": 1.70,
}

# §5.3.1 macro band table (g/kg/day). `cho_low/high`, `protein_low/high`,
# `fat_min` per phase.
#
# Protein bands raised 2026-06-20 (issue #542 — daily protein was under-
# recommended). The prior floors (Base 1.4, Build/Taper 1.6, Peak 1.7) sat at
# the bottom of, or below, the modern evidence band: contemporary work on
# trained athletes converges on ~1.6 g/kg as the floor for endurance athletes,
# not the old ~1.2-1.4 g/kg endurance figure —
#   • Kato et al. (2016), IAAO method: endurance protein requirement ~1.65 g/kg
#     and a safe intake ~1.83 g/kg on training days (well above the RDA / older
#     ACSM endurance band).
#   • Morton et al. (2018) meta-analysis: ~1.6 g/kg is the breakpoint that
#     maximises training-induced lean-mass gains.
#   • ISSN protein position stand (Jäger 2017): 1.4-2.0 g/kg for building/
#     maintaining muscle in exercising individuals, trending higher (toward
#     2.3-3.1 g/kg) during hypocaloric periods to preserve lean mass.
# Bands now run 1.6 (Base) → 2.2 (Peak), with Taper held high (1.8-2.0) because
# the race-week energy pull-back is a mild deficit where higher protein protects
# lean mass (Helms et al. 2014). CHO + fat_min unchanged (still spec-anchored).
_MACRO_BANDS: dict[str, dict[str, float]] = {
    "Base":  {"cho_low": 5.0, "cho_high": 7.0,  "protein_low": 1.6, "protein_high": 1.8, "fat_min": 1.0},
    "Build": {"cho_low": 6.0, "cho_high": 9.0,  "protein_low": 1.7, "protein_high": 2.0, "fat_min": 1.0},
    "Peak":  {"cho_low": 7.0, "cho_high": 12.0, "protein_low": 1.8, "protein_high": 2.2, "fat_min": 1.0},
    "Taper": {"cho_low": 5.0, "cho_high": 7.0,  "protein_low": 1.8, "protein_high": 2.0, "fat_min": 1.0},
}

# §5.4.2 race-day base bands by duration tier.
_FUELING_BANDS: dict[str, dict[str, Any]] = {
    "tier_short": {
        "cho_low": 60.0, "cho_high": 90.0,
        "na_low": 500.0, "na_high": 800.0,
        "fluid_low": 500.0, "fluid_high": 750.0,
        "protein_after_hr": None,
    },
    "tier_mid": {
        "cho_low": 60.0, "cho_high": 90.0,
        "na_low": 600.0, "na_high": 1000.0,
        "fluid_low": 400.0, "fluid_high": 700.0,
        "protein_after_hr": None,
    },
    "tier_long": {
        "cho_low": 50.0, "cho_high": 80.0,
        "na_low": 500.0, "na_high": 800.0,
        "fluid_low": 400.0, "fluid_high": 700.0,
        "protein_after_hr": (8, 5.0, 5.0),
    },
    "tier_expedition": {
        "cho_low": 40.0, "cho_high": 70.0,
        "na_low": 400.0, "na_high": 700.0,
        "fluid_low": None, "fluid_high": None,
        "protein_after_hr": (8, 5.0, 10.0),
    },
    "tier_extended_expedition": {
        "cho_low": 40.0, "cho_high": 70.0,
        "na_low": 400.0, "na_high": 700.0,
        "fluid_low": None, "fluid_high": None,
        "protein_after_hr": (8, 5.0, 10.0),
    },
}

# §5.4.3 sport-profile CHO modifier. Resolved from the discipline mix
# via `_resolve_sport_profile`.
_SPORT_PROFILE_CHO_MOD: dict[str, float] = {
    "running": 0.85,
    "cycling": 1.0,
    "swimming": 0.6,
    "paddling": 0.9,
    "multi_sport": 0.95,
    "skimo": 0.9,
    "default": 1.0,
}

# §5.3.3 endurance profile — read directly from the curated upstream
# `layer0.disciplines.endurance_profile` (plumbed via Layer 2A onto
# `Layer2ADiscipline.endurance_profile`; values curated in
# `etl/layer0/discipline_canon.DISCIPLINE_ENDURANCE_PROFILE`). This replaced the
# old terrain-prefix parse of the free-text `discipline_category` (removed May
# 2026 — it mis-classified ~6 disciplines). Values ∈ Layer 0 `ENUM_ENDURANCE`.
# Missing/unknown defaults to 'Mixed' (an unrecognised-but-present value logs).
_ENUM_ENDURANCE: frozenset[str] = frozenset(
    {"Pure endurance", "Mixed", "Technical-dominant"}
)

# §5.4.3 sport-profile vote, derived from the upstream movement axis
# `layer0.disciplines.primary_movement` (∈ Layer 0 `ENUM_MOVEMENTS`),
# plumbed onto `Layer2ADiscipline.primary_movement`. This is the
# movement-faithful source the terrain category cannot provide
# (e.g. swimming vs paddling both share a 'Water / *' category).
# Missing/unknown movement defaults to 'multi_sport'.
_MOVEMENT_SPORT_PROFILE: dict[str, str] = {
    "running": "running",
    "hiking": "running",
    "cycling": "cycling",
    "swimming": "swimming",
    "paddling": "paddling",
    "skiing": "skimo",
    "climbing": "multi_sport",
    "navigation": "multi_sport",
    "other_skill": "multi_sport",
}

# §5.3.3 protein band — movements whose force demand pushes dietary
# protein higher. 'climbing' is the strength-biased movement in the
# Layer 0 vocabulary.
_STRENGTH_MOVEMENTS: frozenset[str] = frozenset({"climbing"})


def _endurance_profile(discipline: Layer2ADiscipline) -> str:
    profile = (discipline.endurance_profile or "").strip()
    if not profile:
        return "Mixed"
    if profile not in _ENUM_ENDURANCE:
        logger.warning(
            "unknown endurance_profile %r for %s; defaulting endurance to 'Mixed'",
            profile, discipline.discipline_id,
        )
        return "Mixed"
    return profile


def _movement_sport_profile(discipline: Layer2ADiscipline) -> str:
    movement = discipline.primary_movement
    if not movement:
        return "multi_sport"
    profile = _MOVEMENT_SPORT_PROFILE.get(movement.strip().lower())
    if profile is None:
        logger.warning(
            "unknown primary_movement %r for %s; defaulting profile to 'multi_sport'",
            movement, discipline.discipline_id,
        )
        return "multi_sport"
    return profile


# §5.4.4 deployed → spec salt_tolerance translation.
_SALT_TOLERANCE_NORM: dict[str | None, str | None] = {
    "low": "Low",
    "moderate": "Standard",
    "high": "High",
    None: None,
}

# §5.4.6 deployed → spec caffeine strategy translation. `taper` in the
# deployed enum reduces intake leading up to race day — no direct spec
# equivalent; map to 'Same as daily' (maintain pattern) for v1 plan
# computation. `caffeine_loading` → spec 'Loaded'.
_CAFFEINE_STRATEGY_NORM: dict[str | None, str | None] = {
    "caffeine_loading": "Loaded",
    "taper": "Same as daily",
    "maintain": "Same as daily",
    "avoid": "Avoid",
    None: None,
}

# Format options per tier (§5.4.5 base options).
_FORMAT_OPTIONS: dict[str, list[str]] = {
    "tier_short": ["gels", "chews", "drink_mix", "sports_drink"],
    "tier_mid": ["gels", "chews", "drink_mix", "real_food"],
    "tier_long": ["real_food", "gels", "drink_mix", "chews"],
    "tier_expedition": ["real_food", "gels", "drink_mix", "warm_food"],
    "tier_extended_expedition": ["real_food", "warm_food", "drink_mix", "gels"],
}

# §5.7 trigger threshold — sleep-dep overlay activates when any event
# duration exceeds this.
_SLEEP_DEP_DURATION_THRESHOLD_HR: float = 20.0


# ─── Errors ──────────────────────────────────────────────────────────────────


class Layer2EInputError(ValueError):
    """Raised by `q_layer2e_nutrition_baseline_payload` on §4 validation
    failure. Plan-gen catches and surfaces a user-facing error."""


# ─── Validation (§4) ─────────────────────────────────────────────────────────


def _validate_inputs(
    identity: Layer1Identity,
    health_status: Layer1HealthStatus,
    performance: Layer1Performance,
    target_events: list[Layer2ETargetEvent],
    lifestyle: Layer1Lifestyle,
    included_disciplines: list[Layer2ADiscipline],
    framework_sport: str,
    current_phase: str,
    etl_version_set: dict[str, str],
) -> None:
    # Spec §4 precondition 1 — sex enum. Deployed Literal['male','female']
    # already constrains; explicit check stays loud if a builder caller
    # somehow constructs an instance with None sex.
    if identity.sex not in ("male", "female"):
        raise Layer2EInputError(
            f"identity.sex must be 'male' or 'female'; got {identity.sex!r}"
        )

    # Spec §4 #2 / #3 — sanity floors. Deployed types are Optional so
    # missing values fail here.
    if performance.body_weight_kg is None or performance.body_weight_kg <= _BODY_WEIGHT_MIN_KG:
        raise Layer2EInputError(
            f"performance.body_weight_kg must be > {_BODY_WEIGHT_MIN_KG} "
            f"kg; got {performance.body_weight_kg}"
        )
    if identity.height_cm is None or identity.height_cm <= _HEIGHT_MIN_CM:
        raise Layer2EInputError(
            f"identity.height_cm must be > {_HEIGHT_MIN_CM} cm; "
            f"got {identity.height_cm}"
        )

    # Spec §4 #5 — target_events is a list (may be empty).
    if not isinstance(target_events, list):
        raise Layer2EInputError(
            "target_events must be a list (may be empty)"
        )
    for idx, ev in enumerate(target_events):
        if not isinstance(ev, Layer2ETargetEvent):
            raise Layer2EInputError(
                f"target_events[{idx}] must be a Layer2ETargetEvent"
            )

    # Spec §4 #9 — non-empty disciplines.
    if not isinstance(included_disciplines, list) or not included_disciplines:
        raise Layer2EInputError(
            "included_disciplines must be a non-empty list"
        )

    # Spec §4 #10 — framework_sport non-empty.
    if not isinstance(framework_sport, str) or not framework_sport:
        raise Layer2EInputError("framework_sport must be a non-empty string")

    # Spec §4 #11 — current_phase enum.
    if current_phase not in _PHASES:
        raise Layer2EInputError(
            f"current_phase must be one of {_PHASES}; got {current_phase!r}"
        )

    # Spec §4 #12 — etl_version_set keys (vertical slice only consumes 0A
    # for the phase_load_weekly_totals lookup; 0B/0C requirements relax
    # until §5.5 supplement integration de-stubs).
    if not isinstance(etl_version_set, dict) or not _REQUIRED_ETL_KEYS.issubset(
        etl_version_set.keys()
    ):
        raise Layer2EInputError(
            f"etl_version_set must contain keys {sorted(_REQUIRED_ETL_KEYS)}; "
            f"got {sorted(etl_version_set.keys()) if isinstance(etl_version_set, dict) else etl_version_set!r}"
        )


# ─── §5.2 Daily calorie target ──────────────────────────────────────────────


def _years_between(dob: date | None, today: date) -> float:
    if dob is None:
        return 35.0  # spec doesn't require dob; Mifflin needs age, default
    return (today - dob).days / 365.25


def _compute_bmr(
    identity: Layer1Identity,
    performance: Layer1Performance,
    today: date,
) -> tuple[float, str]:
    # ffm_kg is not deployed on Layer1Performance (open item 2E-1);
    # algorithm auto-switches to Cunningham when the field lands.
    ffm_kg = getattr(performance, "ffm_kg", None)
    if ffm_kg is not None and ffm_kg > 0:
        bmr = 370.0 + 21.6 * ffm_kg
        return bmr, "cunningham_1991"

    age_years = _years_between(identity.date_of_birth, today)
    base = (
        10.0 * float(performance.body_weight_kg)
        + 6.25 * float(identity.height_cm)
        - 5.0 * age_years
    )
    bmr = base + 5.0 if identity.sex == "male" else base - 161.0
    return bmr, "mifflin_st_jeor"


def _volume_tier_index(weekly_hours_mid: float) -> int:
    # §5.2.2 multiplier band — <6 / 6-10 / 10-15 / 15+.
    if weekly_hours_mid < 6.0:
        return 0
    if weekly_hours_mid < 10.0:
        return 1
    if weekly_hours_mid < 15.0:
        return 2
    return 3


def _load_phase_weekly_hours(
    db,
    framework_sport: str,
    phase: str,
) -> tuple[float | None, float | None]:
    cur = db.execute(
        """
        SELECT weekly_low_hours, weekly_high_hours
          FROM layer0.phase_load_weekly_totals
         WHERE sport_name = ?
           AND phase = ?
           AND superseded_at IS NULL
         LIMIT 1
        """,
        (framework_sport, phase),
    )
    row = cur.fetchone()
    if row is None:
        return None, None
    low = row["weekly_low_hours"] if row["weekly_low_hours"] is not None else None
    high = row["weekly_high_hours"] if row["weekly_high_hours"] is not None else None
    return (
        float(low) if low is not None else None,
        float(high) if high is not None else None,
    )


def _compute_activity_multiplier(
    db,
    framework_sport: str,
    phase: str,
) -> tuple[float, dict[str, Any], bool]:
    low, high = _load_phase_weekly_hours(db, framework_sport, phase)
    if low is None or high is None:
        return (
            _PHASE_DEFAULT_MULTIPLIER[phase],
            {"fallback": "phase_default_no_pla_row", "phase": phase},
            True,
        )
    mid = (low + high) / 2.0
    idx = _volume_tier_index(mid)
    multiplier = _MULTIPLIER_BANDS[phase][idx]
    return (
        multiplier,
        {"weekly_hours_mid": mid, "phase": phase, "volume_tier_index": idx},
        False,
    )


def _compute_daily_calorie_target(bmr: float, multiplier: float) -> int:
    raw = bmr * multiplier
    return int(round(raw / 50.0) * 50)


# ─── §5.3 Macro split ───────────────────────────────────────────────────────


def _discipline_weight(d: Layer2ADiscipline) -> float:
    # `WeightResult.value` is Optional — fall back to system_default,
    # else 0 (discipline contributes nothing to weighted sums).
    if d.load_weight.value is not None:
        return float(d.load_weight.value)
    if d.load_weight.system_default is not None:
        return float(d.load_weight.system_default)
    return 0.0


def _cho_band_position(disciplines: list[Layer2ADiscipline]) -> float:
    # §5.3.3 — position scales with endurance-vs-technical share of the
    # weighted discipline mix.
    weight_sum = sum(_discipline_weight(d) for d in disciplines) or 1.0
    pure = 0.0
    mixed = 0.0
    for d in disciplines:
        profile = _endurance_profile(d)
        share = _discipline_weight(d) / weight_sum
        if profile == "Pure endurance":
            pure += share
        elif profile == "Mixed":
            mixed += share
    technical_share = max(0.0, 1.0 - pure - mixed)
    return min(1.0, max(0.0, 0.5 + 0.4 * pure - 0.2 * technical_share))


def _protein_band_position(disciplines: list[Layer2ADiscipline]) -> float:
    # §5.3.3 — strength-weighted disciplines push protein higher.
    weight_sum = sum(_discipline_weight(d) for d in disciplines) or 1.0
    strength = sum(
        _discipline_weight(d) for d in disciplines
        if (d.primary_movement or "").strip().lower() in _STRENGTH_MOVEMENTS
    ) / weight_sum
    return min(1.0, 0.4 + 0.6 * strength)


def _compute_macros_for_phase(
    phase: str,
    body_weight_kg: float,
    daily_calorie_target: int,
    disciplines: list[Layer2ADiscipline],
) -> MacroTargets:
    band = _MACRO_BANDS[phase]
    cho_pos = _cho_band_position(disciplines)
    cho_g_per_kg = band["cho_low"] + cho_pos * (band["cho_high"] - band["cho_low"])

    protein_pos = _protein_band_position(disciplines)
    protein_g_per_kg = band["protein_low"] + protein_pos * (band["protein_high"] - band["protein_low"])

    cho_g = round(cho_g_per_kg * body_weight_kg)
    protein_g = round(protein_g_per_kg * body_weight_kg)

    cho_kcal = cho_g * 4
    protein_kcal = protein_g * 4
    fat_kcal = max(0, daily_calorie_target - cho_kcal - protein_kcal)
    fat_g = round(fat_kcal / 9.0) if fat_kcal > 0 else 0

    fat_floor_g = round(band["fat_min"] * body_weight_kg)
    fat_floor_constrained = False
    if fat_g < fat_floor_g:
        # §5.3.2 fat floor: keep fat at floor, shrink CHO band position.
        fat_g = fat_floor_g
        fat_kcal = fat_g * 9
        cho_kcal = max(0, daily_calorie_target - protein_kcal - fat_kcal)
        cho_g = round(cho_kcal / 4.0) if cho_kcal > 0 else 0
        cho_g_per_kg = cho_g / body_weight_kg if body_weight_kg > 0 else 0.0
        fat_floor_constrained = True

    return MacroTargets(
        cho_g=int(cho_g),
        cho_g_per_kg=round(float(cho_g_per_kg), 3),
        cho_kcal=int(cho_kcal),
        protein_g=int(protein_g),
        protein_g_per_kg=round(float(protein_g_per_kg), 3),
        protein_kcal=int(protein_kcal),
        fat_g=int(fat_g),
        fat_kcal=int(fat_kcal),
        fat_floor_constrained=fat_floor_constrained,
    )


# ─── §5.4 Race-day fueling ──────────────────────────────────────────────────


def _classify_duration_tier(hours: float) -> str:
    if hours <= 4:
        return "tier_short"
    if hours <= 12:
        return "tier_mid"
    if hours <= 24:
        return "tier_long"
    if hours <= 48:
        return "tier_expedition"
    return "tier_extended_expedition"


def _resolve_sport_profile(disciplines: list[Layer2ADiscipline]) -> str:
    # §5.4.3 weighted vote. Multi-discipline races (AR / triathlon) where
    # no single profile claims >50% land on 'multi_sport'.
    weight_sum = sum(_discipline_weight(d) for d in disciplines) or 1.0
    tallies: dict[str, float] = {}
    for d in disciplines:
        profile = _movement_sport_profile(d)
        tallies[profile] = tallies.get(profile, 0.0) + _discipline_weight(d) / weight_sum
    top_profile, top_share = max(tallies.items(), key=lambda kv: kv[1])
    if top_share < 0.5:
        return "multi_sport"
    return top_profile


def _sport_modifier(sport_profile: str) -> float:
    return _SPORT_PROFILE_CHO_MOD.get(sport_profile, _SPORT_PROFILE_CHO_MOD["default"])


def _salt_tolerance_modifier(deployed_value: str | None) -> tuple[float, str]:
    # §5.4.4 — Low → 0.8 / Standard → 1.0 / High → 1.2.
    spec = _SALT_TOLERANCE_NORM.get(deployed_value)
    if spec == "Low":
        return 0.8, "Low"
    if spec == "High":
        return 1.2, "High"
    return 1.0, spec or "Standard"


def _build_caffeine_plan(
    lifestyle: Layer1Lifestyle,
    body_weight_kg: float,
    event: Layer2ETargetEvent,
) -> CaffeineRacedayPlan | None:
    # §5.4.6 — strategy translation runs first; Avoid + None tolerance
    # both short-circuit to None.
    deployed_strategy = lifestyle.caffeine_race_day_strategy
    if deployed_strategy is None:
        return None
    if lifestyle.caffeine_tolerance == "none":
        return None
    spec_strategy = _CAFFEINE_STRATEGY_NORM.get(deployed_strategy)
    if spec_strategy is None or spec_strategy == "Avoid":
        return None

    if spec_strategy == "Same as daily":
        daily = lifestyle.caffeine_daily_mg_estimate
        # Spread daily dose across a 16-hr wake window if known.
        per_hr = float(daily) / 16.0 if daily else None
        return CaffeineRacedayPlan(
            pre_race_mg=None,
            during_race_mg_per_hr=per_hr,
            timing="maintain_daily_pattern",
            notes="Maintain habitual pattern; no special protocol.",
        )

    # 'Loaded' branch — 3-6 mg/kg pre-race dose with 10-14 day abstain.
    # Default to 4.5 mg/kg midpoint when athlete didn't specify a dose
    # (Layer1Lifestyle doesn't carry race-day dose on the v1 form).
    dose_mg = round(4.5 * body_weight_kg, 0)
    return CaffeineRacedayPlan(
        pre_race_mg=dose_mg,
        during_race_mg_per_hr=None,
        timing="abstain_10_14d_then_load",
        notes=(
            "Insert 10–14 day abstinence in taper; deliver pre-race dose "
            "30–60 min before start. Dose centered on 4.5 mg/kg until the "
            "§I.1 form refresh captures a per-athlete race-day dose."
        ),
    )


def _recommend_formats(
    duration_tier: str,
    fueling_format_pref: list[str],
    gi_triggers_known: str | None,
) -> tuple[list[str], list[str]]:
    # §5.4.5 — filter trigger categories then rank by athlete pref.
    # Deployed `gi_triggers_known` is free text rather than the spec's
    # structured `list[GITriggerCategory]`. Substring scan keeps the
    # primitive boundary working without invented vocabulary.
    base = list(_FORMAT_OPTIONS[duration_tier])
    blocked: list[str] = []

    if gi_triggers_known:
        lower = gi_triggers_known.lower()
        if any(kw in lower for kw in ("gel", "maltodext", "fructose")):
            if "gels" in base:
                base.remove("gels")
                blocked.append("gels")
        if any(kw in lower for kw in ("sugar alcohol", "polyol", "sorbitol")):
            if "chews" in base:
                base.remove("chews")
                blocked.append("chews")

    # Rank by athlete pref order. Items not in the athlete's pref list
    # tail behind, preserving spec order.
    pref_lower = [p.lower() for p in fueling_format_pref or []]
    ranked = sorted(
        base,
        key=lambda opt: (
            pref_lower.index(opt) if opt in pref_lower else len(pref_lower),
            base.index(opt),
        ),
    )
    return ranked, blocked


def _build_race_day_fueling(
    event: Layer2ETargetEvent,
    lifestyle: Layer1Lifestyle,
    body_weight_kg: float,
    sport_profile: str,
) -> tuple[RaceDayFueling, list[str]]:
    tier = _classify_duration_tier(event.estimated_duration_hr)
    band = _FUELING_BANDS[tier]

    sport_mod = _sport_modifier(sport_profile)
    salt_mod, _salt_label = _salt_tolerance_modifier(lifestyle.salt_electrolyte_tolerance)

    # §5.4.3 sport modifier shrinks the upper CHO band but not the lower.
    cho_low = band["cho_low"]
    cho_high = band["cho_high"] * sport_mod

    na_low = band["na_low"] * salt_mod
    na_high = band["na_high"] * salt_mod

    fluid_low = band["fluid_low"] * salt_mod if band["fluid_low"] is not None else None
    fluid_high = band["fluid_high"] * salt_mod if band["fluid_high"] is not None else None

    protein_after = band["protein_after_hr"]

    formats, blocked = _recommend_formats(
        tier, lifestyle.fueling_format_preference or [], lifestyle.gi_triggers_known
    )

    caffeine = _build_caffeine_plan(lifestyle, body_weight_kg, event)

    sleep_dep_applies = event.estimated_duration_hr > _SLEEP_DEP_DURATION_THRESHOLD_HR

    notes: list[str] = []
    if tier in ("tier_expedition", "tier_extended_expedition"):
        notes.append(
            "Fluid scales with exertion + heat per §5.4.2; mid-tier band "
            "not directly applicable."
        )
    if sport_mod < 1.0:
        notes.append(
            f"Sport-profile CHO modifier {sport_mod} applied "
            f"({sport_profile}); upper CHO band reduced."
        )

    rdf = RaceDayFueling(
        event_id=event.event_id,
        event_name=event.event_name,
        duration_tier=tier,
        cho_g_per_hr_low=round(cho_low, 1),
        cho_g_per_hr_high=round(cho_high, 1),
        na_mg_per_hr_low=round(na_low, 1),
        na_mg_per_hr_high=round(na_high, 1),
        fluid_ml_per_hr_low=round(fluid_low, 1) if fluid_low is not None else None,
        fluid_ml_per_hr_high=round(fluid_high, 1) if fluid_high is not None else None,
        protein_g_per_hr_after_hr_n=protein_after,
        sport_modifier_applied=sport_mod,
        salt_tolerance_modifier_applied=salt_mod,
        heat_acclim_modifier_applied=1.0,  # §5.8 stub — no modifier applied
        recommended_formats=formats,
        blocked_formats=blocked,
        caffeine_plan=caffeine,
        sleep_dep_overlay_applies=sleep_dep_applies,
        notes=notes,
    )
    return rdf, blocked


# ─── §5.5 Supplement integration ────────────────────────────────────────────

# Race-day supplement suggestions by duration tier (§5.5). Additive — richer
# tiers inherit the lighter tiers' set. caffeine is gated on the athlete's
# race-day strategy below. sodium_bicarbonate is intentionally omitted: the
# spec gates it on a high-intensity sub-discipline AND "athlete has tested it",
# neither of which is captured today (no-padding — don't suggest on data we
# don't have).
_S_ELECTROLYTE = ("electrolyte_mix",
                  "Replace sodium and fluid lost across the effort.")
_S_CARB = ("carb_powder",
           "Hit race-day CHO g/hr targets without leaning on solids alone.")
_S_CAFFEINE = ("caffeine",
               "Ergogenic for sustained efforts; dose per your race-day "
               "caffeine strategy.")
_S_MAGNESIUM = ("magnesium",
                "Post-race neuromuscular recovery after prolonged load.")
_S_OMEGA3 = ("omega_3",
             "Anti-inflammatory and recovery support across a multi-day event.")
_S_BCAAS = ("bcaas",
            "Branched-chain support for muscle preservation on "
            "expedition-length events.")

_RACE_DAY_TIER_SUPPLEMENTS: dict[str, list[tuple[str, str]]] = {
    "tier_short": [_S_ELECTROLYTE],
    "tier_mid": [_S_ELECTROLYTE, _S_CARB, _S_CAFFEINE],
    "tier_long": [_S_ELECTROLYTE, _S_CARB, _S_CAFFEINE, _S_MAGNESIUM],
    "tier_expedition": [_S_ELECTROLYTE, _S_CARB, _S_CAFFEINE, _S_MAGNESIUM,
                        _S_OMEGA3, _S_BCAAS],
    "tier_extended_expedition": [_S_ELECTROLYTE, _S_CARB, _S_CAFFEINE,
                                 _S_MAGNESIUM, _S_OMEGA3, _S_BCAAS],
}


def _load_supplement_vocab(db) -> dict[str, dict]:
    """`supplement_id -> {canonical_name, contraindications}` for active
    `layer0.supplement_vocabulary` rows. Best-effort: the table is ETL-owned and
    may be absent on a freshly migrated DB, so any read fault yields {} (→ no
    suggestions, no screening) rather than breaking the nutrition baseline."""
    try:
        cur = db.execute(
            "SELECT supplement_id, canonical_name, contraindications "
            "FROM layer0.supplement_vocabulary WHERE superseded_at IS NULL"
        )
        return {
            r["supplement_id"]: {
                "canonical_name": r["canonical_name"],
                "contraindications": list(r["contraindications"] or []),
            }
            for r in cur.fetchall()
        }
    except Exception as exc:  # noqa: BLE001 — advisory; never break the baseline
        print(f"_load_supplement_vocab failed (non-fatal): {exc}")
        return {}


def _contraindication_hits(
    contraindications: list[str],
    active_categories: set[str],
    active_med_classes: set[str],
) -> tuple[set[str], set[str]]:
    """Split a supplement's canonical vocab contraindications (D-21 retag)
    against the athlete's active §B inputs → (matched system_category values,
    matched medication_class values).

    Tokens are canonical now (no in-app mapping): a bare token is a
    `system_category`; an `rx:<class>` token is a `medication_class`. `pregnancy`
    is deferred (#518) and ignored; any other unrecognized token can't match."""
    condition_hits: set[str] = set()
    med_hits: set[str] = set()
    for token in contraindications:
        if token == "pregnancy":
            continue  # deferred to #518
        if token.startswith("rx:"):
            cls = token[3:]
            if cls in active_med_classes:
                med_hits.add(cls)
        elif token in active_categories:
            condition_hits.add(token)
    return condition_hits, med_hits


def _contraindication_flag(
    canonical_name: str,
    supplement_id: str,
    cond_hits: set[str],
    med_hits: set[str],
    active_conditions: list[HealthConditionRecord],
) -> Layer2ECoachingFlag:
    """Non-blocking warning naming the active condition(s) / medication class(es)
    a just-removed supplement conflicts with."""
    named = [c.condition_name for c in active_conditions
             if c.system_category in cond_hits]
    reasons: list[str] = []
    if named:
        reasons.append("an active health condition (" + ", ".join(named) + ")")
    if med_hits:
        reasons.append("a medication you take ("
                       + ", ".join(sorted(m.replace("_", " ") for m in med_hits))
                       + ")")
    return Layer2ECoachingFlag(
        flag_type="supplement_contraindicated",
        event_id=None,
        supplement_id=supplement_id,
        message=(
            f"{canonical_name} contraindicates with {' and '.join(reasons)}. "
            f"It's been removed from your active supplement protocol — clear any "
            f"use with your physician first."
        ),
        severity="high",
        metadata={
            "auto_removed": True,
            "condition_categories": sorted(cond_hits),
            "condition_names": named,
            "medication_classes": sorted(med_hits),
        },
    )


def _race_day_supplement_suggestions(
    target_events: list[Layer2ETargetEvent],
    supplements: list[AthleteSupplementRecord],
    lifestyle: Layer1Lifestyle,
    vocab: dict[str, dict],
    suppressed_ids: set[str],
) -> list[RaceDaySupplementSuggestion]:
    # §5.5 — per event, suggest the duration tier's standard race-day
    # supplements. Additive (never deletion/replacement); ones already in the
    # athlete's protocol are emitted tagged `already_in_athlete_protocol=True`
    # rather than dropped. `suppressed_ids` carries contraindication auto-removals
    # (B2) — those are never suggested.
    if not target_events or not vocab:
        return []
    in_protocol = {s.supplement_id for s in supplements}
    avoid_caffeine = lifestyle.caffeine_race_day_strategy == "avoid"
    suggestions: list[RaceDaySupplementSuggestion] = []
    for ev in target_events:
        tier = _classify_duration_tier(ev.estimated_duration_hr)
        for supp_id, reason in _RACE_DAY_TIER_SUPPLEMENTS[tier]:
            if supp_id in suppressed_ids:
                continue
            if supp_id == "caffeine" and avoid_caffeine:
                continue
            vocab_row = vocab.get(supp_id)
            if vocab_row is None:
                continue  # vocab id absent (shouldn't happen for the seed ids)
            suggestions.append(RaceDaySupplementSuggestion(
                event_id=ev.event_id,
                supplement_id=supp_id,
                canonical_name=vocab_row["canonical_name"],
                reason=reason,
                already_in_athlete_protocol=supp_id in in_protocol,
            ))
    return suggestions


def _build_supplement_integration(
    db,
    lifestyle: Layer1Lifestyle,
    target_events: list[Layer2ETargetEvent],
    health_status: Layer1HealthStatus,
) -> tuple[SupplementIntegrationPayload, list[Layer2ECoachingFlag]]:
    # §5.5 — non-blocking contraindication screening (Andy 2026-06-10). A logged
    # supplement that contraindicates with an active health condition (§B
    # system_category) OR medication (§B medication_class) is (a) auto-removed
    # from the integrated protocol + race-day suggestions and (b) flagged with a
    # non-blocking warning. NO Layer 3.5 block, NO HITL item, no medical-clearance.
    # Tokens match the canonical vocab directly (D-21 retag); pregnancy → #518.
    vocab = _load_supplement_vocab(db)
    active_conditions = health_status.health_conditions_active
    active_categories = {c.system_category for c in active_conditions}
    active_med_classes = {m.medication_class for m in health_status.medications_active}

    integrated: list[IntegratedSupplement] = []
    flags: list[Layer2ECoachingFlag] = []
    removed_ids: set[str] = set()

    for rec in lifestyle.supplements:
        vocab_row = vocab.get(rec.supplement_id)
        if vocab_row is None:
            # Unknown id — can't screen it; keep, marked not-known.
            integrated.append(IntegratedSupplement(
                supplement_id=rec.supplement_id,
                canonical_name=rec.canonical_name,
                is_known=False,
                contraindication_hits=[],
            ))
            continue
        cond_hits, med_hits = _contraindication_hits(
            vocab_row["contraindications"], active_categories, active_med_classes
        )
        if cond_hits or med_hits:
            removed_ids.add(rec.supplement_id)
            flags.append(_contraindication_flag(
                vocab_row["canonical_name"], rec.supplement_id,
                cond_hits, med_hits, active_conditions,
            ))
            continue  # auto-removed → not carried in `integrated`
        integrated.append(IntegratedSupplement(
            supplement_id=rec.supplement_id,
            canonical_name=vocab_row["canonical_name"],
            is_known=True,
            contraindication_hits=[],
        ))

    # Gate 2 — race-day caffeine loading × active cardiac → warn + suppress
    # caffeine from race-day suggestions (no supplement record to remove).
    suppressed_suggestion_ids = set(removed_ids)
    cardiac = next(
        (c for c in active_conditions if c.system_category == "cardiac"), None)
    if cardiac and lifestyle.caffeine_race_day_strategy == "caffeine_loading":
        suppressed_suggestion_ids.add("caffeine")
        flags.append(Layer2ECoachingFlag(
            flag_type="race_day_caffeine_contraindicated_cardiac",
            event_id=None,
            supplement_id="caffeine",
            message=(
                f"Your race-day caffeine-loading strategy conflicts with an "
                f"active cardiac condition ({cardiac.condition_name}). Caffeine has "
                f"been left out of your race-day suggestions — clear any race-day "
                f"stimulant plan with your physician first."
            ),
            severity="high",
            metadata={
                "auto_removed": True,
                "condition_category": "cardiac",
                "caffeine_race_day_strategy": "caffeine_loading",
            },
        ))

    race_day_suggestions = _race_day_supplement_suggestions(
        target_events, lifestyle.supplements, lifestyle,
        vocab=vocab, suppressed_ids=suppressed_suggestion_ids,
    )

    return (
        SupplementIntegrationPayload(
            integrated=integrated,
            race_day_suggestions=race_day_suggestions,
            contraindication_flags=flags,
            # Non-blocking by design (Andy 2026-06-10) — no HITL, plan never
            # blocked on a contraindication; resolution stays informational.
            contraindication_hitl_items=[],
        ),
        [],
    )


# ─── §5.6 Dietary pattern adjustments ───────────────────────────────────────


def _has_pattern(dietary_pattern: list[str], target: str) -> bool:
    return target.lower() in {d.lower() for d in dietary_pattern}


def _dietary_pattern_adjustments(
    lifestyle: Layer1Lifestyle,
) -> list[DietaryPatternFlag]:
    # §5.6 — case-insensitive pattern matching against the deployed
    # free-form list. Supplement-presence checks intentionally not run
    # (see §5.5 stub) — flags surface unconditionally when a pattern is
    # present so plan-gen can render the deficiency-risk warning.
    flags: list[DietaryPatternFlag] = []
    if _has_pattern(lifestyle.dietary_pattern, "Vegan"):
        flags.append(DietaryPatternFlag(
            pattern="Vegan",
            concern="b12_deficiency_risk",
            severity="moderate",
            rationale=(
                "Vegan diet without B12 supplementation creates measurable "
                "deficiency risk within 6–18 months. Verify B12 in athlete's "
                "supplement protocol."
            ),
            suggested_supplement_id="vitamin_b12",
        ))
        flags.append(DietaryPatternFlag(
            pattern="Vegan",
            concern="iron_status_risk",
            severity="low",
            rationale=(
                "Non-heme iron absorption is lower than heme; surveillance "
                "via periodic ferritin testing recommended for endurance "
                "athletes on plant-only diets."
            ),
            suggested_supplement_id="iron",
            requires_medical_guidance=True,
        ))
        flags.append(DietaryPatternFlag(
            pattern="Vegan",
            concern="epa_dha_conversion",
            severity="low",
            rationale=(
                "ALA→EPA/DHA conversion is inefficient; algae-derived "
                "EPA/DHA supplementation closes the gap."
            ),
            suggested_supplement_id="omega_3",
        ))
    if _has_pattern(lifestyle.dietary_pattern, "Low-FODMAP"):
        flags.append(DietaryPatternFlag(
            pattern="Low-FODMAP",
            concern="race_fueling_format_constraint",
            severity="moderate",
            rationale=(
                "High-FODMAP gels (fructose-rich, polyol-containing) may "
                "trigger GI distress. Maltodextrin-dominant formats "
                "preferred for race-day fueling."
            ),
            race_day_format_adjustment="prefer_maltodextrin_dominant",
        ))
    return flags


# ─── §5.7 Sleep-dep overlay ─────────────────────────────────────────────────


def _build_sleep_dep_overlay(
    target_events: list[Layer2ETargetEvent],
    lifestyle: Layer1Lifestyle,
) -> tuple[SleepDepFuelingOverlay | None, list[Layer2ECoachingFlag]]:
    long_events = [
        ev for ev in target_events
        if ev.estimated_duration_hr > _SLEEP_DEP_DURATION_THRESHOLD_HR
    ]
    if not long_events:
        return None, []

    # Deployed §I has flat sleep_dep_* fields rather than the spec's
    # `SleepDepProfile` substructure. If the flat fields are unset for
    # an athlete with a >20hr event, surface §8.7 sleep_dep_data_missing.
    flags: list[Layer2ECoachingFlag] = []
    if (
        lifestyle.sleep_deprivation_max_hrs_continuous_awake is None
        and not (lifestyle.sleep_deprivation_strategy_notes or "").strip()
    ):
        flags.append(Layer2ECoachingFlag(
            flag_type="sleep_dep_data_missing",
            event_id=long_events[0].event_id,
            supplement_id=None,
            message=(
                "At least one target event exceeds 20 hr but §I sleep "
                "deprivation fields are empty. Capture max-awake hours + "
                "strategy notes to refine the cognitive-maintenance protocol."
            ),
            severity="low",
            metadata={"long_event_count": len(long_events)},
        ))

    overlay = SleepDepFuelingOverlay(
        applicable_events=[ev.event_id for ev in long_events],
        cognitive_maintenance_protocol={
            "caffeine_strategic_windows": (
                "Schedule caffeine boluses against the circadian dip "
                "(02:00–06:00 local) rather than constant trickle."
            ),
            "glucose_floor": (
                "Maintain blood glucose with ≥40–50 g/hr CHO through "
                "overnight phases; sub-band CHO targets are the floor."
            ),
            "protein_dose_overnight": (
                "5–10 g/hr after hr 8 slows glycogen depletion and "
                "supports cognitive maintenance."
            ),
        },
        warm_food_strategy={
            "recommendation": (
                "Hot food at extended stops improves palatability when "
                "GI fatigue compounds with cognitive fatigue."
            ),
            "frequency": "every 8–12 hr depending on aid-station spacing",
        },
        format_rotation={
            "rationale": (
                "Palate fatigue compounds in expedition events; rotate "
                "formats every 2–3 hr."
            ),
            "rotation_categories": [
                "sweet_gels",
                "savory_real",
                "liquid",
                "chew_or_solid_sweet",
            ],
        },
        sleep_dep_specific_flags=[],
    )
    return overlay, flags


# ─── §5.8 Heat acclim overlay ───────────────────────────────────────────────

# §5.8: full heat acclimatization takes 10–14 days minimum; under that with a
# `low` acclim state we flag a heat-acclim gap.
_HEAT_FULL_ACCLIM_DAYS = 14


def _hot_event_adjustment(
    heat_acclim_state: HeatAcclimState,
    event: Layer2ETargetEvent,
    severity: str,
    today: date,
) -> tuple[float, float, Layer2ECoachingFlag | None]:
    """`Layer2E_Spec.md` §5.8 `_hot_event_adjustment` — fluid/Na modifiers for a
    warm/hot event plus a heat-acclim flag when the athlete is under-acclimatized.

    `na_mod`/`fluid_mod`: 1.15/1.15 (warm), 1.30/1.35 (hot). `salt_tolerance`
    is intentionally not consumed here — the spec applies it later in the §5.4
    race-day path (`_salt_tolerance_modifier`), not in the heat band.
    """
    days_to_race = (event.event_date - today).days
    if heat_acclim_state.level == "low" and days_to_race < _HEAT_FULL_ACCLIM_DAYS:
        flag: Layer2ECoachingFlag | None = Layer2ECoachingFlag(
            flag_type="heat_acclim_gap",
            event_id=event.event_id,
            message=(
                f"{event.event_name} is expected to run {severity}; your heat "
                f"acclimation is low with {days_to_race} days to the event — "
                "not enough runway for full acclimatization (10–14 days minimum)."
            ),
            severity="moderate",
            metadata={
                "heat_acclim_level": heat_acclim_state.level,
                "days_to_race": days_to_race,
            },
        )
    elif heat_acclim_state.level == "low":
        flag = Layer2ECoachingFlag(
            flag_type="heat_acclim_in_progress",
            event_id=event.event_id,
            message=(
                f"{event.event_name} is expected to run {severity}; run your "
                "heat-acclimation protocol — there's still time to adapt before "
                "the event."
            ),
            severity="info",
            metadata={"heat_acclim_level": heat_acclim_state.level},
        )
    else:
        flag = None

    na_mod = 1.15 if severity == "warm" else 1.30
    fluid_mod = 1.15 if severity == "warm" else 1.35
    return na_mod, fluid_mod, flag


def _heat_acclim_overlay(
    target_events: list[Layer2ETargetEvent],
    plan_state: PlanManagementState,
    heat_acclim_data_sparse: bool,
    today: date,
) -> tuple[list[HeatAcclimEventAdjustment], list[Layer2ECoachingFlag]]:
    """`Layer2E_Spec.md` §5.8 — per-event fluid/Na band modifiers from the Plan
    Management contract (#220 de-stub).

    Bands on `expected_race_temp_c[event_id]`: `<18` cool 0.85/0.85, `<26`
    temperate 1.0/1.0, `<32` warm, `≥32` hot (warm/hot route through
    `_hot_event_adjustment`). `None` (coordinate-less event or both weather
    fetches failed, PM §5.3.4) keeps the `temp_signal='unknown'` +
    `race_temp_unknown` branch with no modifier. When the heat-acclim signal is
    thin (`heat_acclim_data_sparse`, PM §5.2.4) one `heat_acclim_data_sparse`
    advisory is surfaced so a `low` reading from absent data isn't misread as a
    confirmed-unacclimatized one.
    """
    adjustments: list[HeatAcclimEventAdjustment] = []
    flags: list[Layer2ECoachingFlag] = []
    heat_state = plan_state.heat_acclim_state

    for ev in target_events:
        expected_temp = plan_state.expected_race_temp_c.get(ev.event_id)
        if expected_temp is None:
            signal = "unknown"
            na_mod = fluid_mod = 1.0
            flag: Layer2ECoachingFlag | None = Layer2ECoachingFlag(
                flag_type="race_temp_unknown",
                event_id=ev.event_id,
                message=(
                    f"Expected race temperature for {ev.event_name} isn't "
                    "resolved yet (no locale coordinates, or weather lookup "
                    "failed) — no heat band modifiers applied."
                ),
                severity="info",
                metadata={"reason": "expected_race_temp_unresolved"},
            )
        elif expected_temp < 18:
            signal, na_mod, fluid_mod, flag = "cool", 0.85, 0.85, None
        elif expected_temp < 26:
            signal, na_mod, fluid_mod, flag = "temperate", 1.0, 1.0, None
        elif expected_temp < 32:
            signal = "warm"
            na_mod, fluid_mod, flag = _hot_event_adjustment(
                heat_state, ev, "warm", today
            )
        else:
            signal = "hot"
            na_mod, fluid_mod, flag = _hot_event_adjustment(
                heat_state, ev, "hot", today
            )

        adjustments.append(HeatAcclimEventAdjustment(
            event_id=ev.event_id,
            temp_signal=signal,
            na_modifier=na_mod,
            fluid_modifier=fluid_mod,
            flag=flag,
        ))
        if flag is not None:
            flags.append(flag)

        # Rule #15 — per-event chosen temp + band + the acclim inputs behind it.
        print(
            f"layer2e._heat_acclim_overlay: event={ev.event_id} "
            f"expected_temp_c={expected_temp} signal={signal} na_mod={na_mod} "
            f"fluid_mod={fluid_mod} acclim_level={heat_state.level} "
            f"days_at_temp_last_30={heat_state.days_at_temp_last_30} "
            f"flag={flag.flag_type if flag else None}"
        )

    # PM §5.2.4 — one sparse-data advisory per build (athlete-level, not per event).
    if heat_acclim_data_sparse and target_events:
        flags.append(Layer2ECoachingFlag(
            flag_type="heat_acclim_data_sparse",
            event_id=None,
            message=(
                "Heat-acclimation was read from very few logged training "
                "conditions (<5 days in the last 30) — treated as low to stay "
                "safe for a hot race, but log your conditions to sharpen it."
            ),
            severity="info",
            metadata={
                "days_at_temp_last_30": heat_state.days_at_temp_last_30,
                "level": heat_state.level,
            },
        ))

    return adjustments, flags


# ─── §5.9 HITL (no active gates) ────────────────────────────────────────────


def _emit_hitl_items(
    health_status: Layer1HealthStatus,
    target_events: list[Layer2ETargetEvent],
) -> list[Layer2EHitlItem]:
    # Gates 1-4 require structured supplements + a pregnancy field; deferred
    # to post-§I.1-refresh. The food-allergy gate 5 was retired along with the
    # food_allergies capture (dead code — never populated or consumed).
    # No active gates remain; this stays as the emission point for the
    # deferred gates.
    return []


# ─── §8 coaching flags assembly ─────────────────────────────────────────────


def _emit_general_coaching_flags(
    identity: Layer1Identity,
    health_status: Layer1HealthStatus,
    bmr_method: str,
    daily_baseline: DailyNutritionBaseline,
    bmr_kcal: float,
    pla_fallback_phases: list[str],
) -> list[Layer2ECoachingFlag]:
    flags: list[Layer2ECoachingFlag] = []

    # §8.1 — pla_missing_for_sport_phase, surfaced once per phase that
    # fell back to the default multiplier.
    for phase in pla_fallback_phases:
        flags.append(Layer2ECoachingFlag(
            flag_type="pla_missing_for_sport_phase",
            event_id=None,
            supplement_id=None,
            message=(
                f"`phase_load_weekly_totals` has no row for the current "
                f"framework_sport × {phase}; activity multiplier fell back "
                "to phase default. Affected sports per D-07: Swimrun, "
                "Off-Road / Adventure Multisport (Non-Nav), Open Water "
                "Marathon Swimming sub-formats."
            ),
            severity="low",
            metadata={"phase": phase},
        ))

    # §8.6 — hrt_bmr_limitation: HRT medication active + Mifflin path.
    on_hrt = any(
        m.medication_class == "hrt" for m in health_status.medications_active
    )
    if on_hrt and bmr_method == "mifflin_st_jeor":
        flags.append(Layer2ECoachingFlag(
            flag_type="hrt_bmr_limitation",
            event_id=None,
            supplement_id=None,
            message=(
                "Athlete is on HRT-class medication; v1 BMR uses §A sex "
                "for the Mifflin coefficient and may misestimate by "
                "5–10%. Coaching surface for the limitation; revisit "
                "with the athlete when v2 HRT-aware formulas land."
            ),
            severity="info",
            metadata={"bmr_method": bmr_method},
        ))

    # §8.9 — low_calorie_target_relative_to_rmr: surfaced per phase that
    # falls below bmr × 1.2.
    floor = bmr_kcal * 1.2
    for phase, targets in daily_baseline.per_phase.items():
        if targets.daily_calorie_target_kcal < floor:
            flags.append(Layer2ECoachingFlag(
                flag_type="low_calorie_target_relative_to_rmr",
                event_id=None,
                supplement_id=None,
                message=(
                    f"Daily calorie target for {phase} "
                    f"({targets.daily_calorie_target_kcal} kcal) is below "
                    f"BMR × 1.2 ({int(floor)} kcal). Verify body weight + "
                    "weekly volume; consider sports-dietitian review for "
                    "precision."
                ),
                severity="low",
                metadata={
                    "phase": phase,
                    "daily_calorie_target_kcal": targets.daily_calorie_target_kcal,
                    "bmr_kcal": bmr_kcal,
                    "floor": int(floor),
                },
            ))

    return flags


# ─── Public entry point ─────────────────────────────────────────────────────


def q_layer2e_nutrition_baseline_payload(
    db,
    identity: Layer1Identity,
    health_status: Layer1HealthStatus,
    performance: Layer1Performance,
    target_events: list[Layer2ETargetEvent],
    lifestyle: Layer1Lifestyle,
    included_disciplines: list[Layer2ADiscipline],
    framework_sport: str,
    plan_management_state: PlanManagementState,
    *,
    etl_version_set: dict[str, str],
    heat_acclim_data_sparse: bool = False,
    athlete_id: str | None = None,
    today: date | None = None,
) -> Layer2EPayload:
    """Build the per-athlete nutrition baseline payload.

    Pure query node per `Layer2E_Spec.md` §3 — single SQL footprint is
    one indexed SELECT per phase on `layer0.phase_load_weekly_totals`
    (4 SELECTs total). All other paths are pure-Python math against
    spec-internal constant tables.

    Vertical-slice ship: §5.5 supplement integration ships race-day
    suggestions (B1) + non-blocking contraindication screening across all
    §B conditions + medications (B2 + D-21 — auto-remove + warning flag,
    no HITL block; matches the canonical vocab directly after the D-21
    retag). Pregnancy contraindications go to #518. §5.8 heat acclim
    stays stubbed pending Plan Management contract authorship. §5.9 emits
    no blocking HITL gates. See module docstring for the full drift map.

    Validation per §4 raises `Layer2EInputError`.
    """
    _validate_inputs(
        identity,
        health_status,
        performance,
        target_events,
        lifestyle,
        included_disciplines,
        framework_sport,
        plan_management_state.current_phase,
        etl_version_set,
    )

    today = today or date.today()
    body_weight_kg = float(performance.body_weight_kg)

    # §5.2 BMR + per-phase activity multiplier.
    bmr_kcal, bmr_method = _compute_bmr(identity, performance, today)

    per_phase: dict[str, DailyPhaseTargets] = {}
    pla_fallback_phases: list[str] = []
    for phase in _PHASES:
        multiplier, source, fallback = _compute_activity_multiplier(
            db, framework_sport, phase
        )
        if fallback:
            pla_fallback_phases.append(phase)
        daily_target = _compute_daily_calorie_target(bmr_kcal, multiplier)
        macros = _compute_macros_for_phase(
            phase, body_weight_kg, daily_target, included_disciplines
        )
        per_phase[phase] = DailyPhaseTargets(
            activity_multiplier=multiplier,
            activity_multiplier_source=source,
            daily_calorie_target_kcal=daily_target,
            macros=macros,
        )
    daily_baseline = DailyNutritionBaseline(per_phase=per_phase)

    # §5.4 race-day fueling per event.
    sport_profile = _resolve_sport_profile(included_disciplines)
    race_day: list[RaceDayFueling] = []
    for ev in target_events:
        rdf, _blocked = _build_race_day_fueling(
            ev, lifestyle, body_weight_kg, sport_profile
        )
        race_day.append(rdf)

    # §5.5 supplement integration — race-day suggestions (B1) + non-blocking
    # contraindication screening across §B conditions + medications (B2 + D-21).
    supplement_payload, supplement_flags = _build_supplement_integration(
        db, lifestyle, target_events, health_status
    )

    # §5.6 dietary pattern adjustments.
    dietary_flags_dpf = _dietary_pattern_adjustments(lifestyle)

    # §5.7 sleep-dep overlay.
    sleep_dep_overlay, sleep_dep_flags = _build_sleep_dep_overlay(
        target_events, lifestyle
    )

    # §5.8 heat acclim overlay — per-event band modifiers from the Plan
    # Management contract (heat_acclim_state + expected_race_temp_c).
    heat_adjustments, heat_flags = _heat_acclim_overlay(
        target_events, plan_management_state, heat_acclim_data_sparse, today
    )

    # §5.9 HITL — gate 5 only this slice.
    hitl_items = _emit_hitl_items(health_status, target_events)

    # §8 general coaching flags.
    general_flags = _emit_general_coaching_flags(
        identity,
        health_status,
        bmr_method,
        daily_baseline,
        bmr_kcal,
        pla_fallback_phases,
    )

    coaching_flags = (
        general_flags
        + supplement_flags
        + sleep_dep_flags
        + heat_flags
    )

    return Layer2EPayload(
        athlete_id=athlete_id or "",
        etl_version_set=dict(etl_version_set),
        # D-77: day-anchor to the cone's logical `today`, NOT wall-clock now().
        # `computed_at` folds into `layer2e_hash` → `plan_create_key` → every
        # Layer 4 per-block cache key. A sub-day timestamp differs on each
        # resumable cron/poller pass, orphaning every cached block → plan-gen
        # never converges (the same bug class day-anchored for layer1.as_of /
        # layer2a.generated_at).
        computed_at=datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
        bmr_method=bmr_method,  # type: ignore[arg-type]
        bmr_kcal=round(bmr_kcal, 1),
        daily_nutrition_baseline=daily_baseline,
        race_day_fueling=race_day,
        supplement_integration=supplement_payload,
        dietary_pattern_adjustments=dietary_flags_dpf,
        sleep_dep_overlay=sleep_dep_overlay,
        heat_acclim_adjustments=heat_adjustments,
        coaching_flags=coaching_flags,
        hitl_items=hitl_items,
        hitl_required=any(it.block_level == "block" for it in hitl_items),
    )
