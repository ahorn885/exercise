# Layer 2E — Nutrition Baseline (Query Node)

**Status:** Consolidated spec, first draft 2026-05-11. Designed from scratch per `2D_Done_2E_Kickoff_Handoff.md` agenda. **Amended in place 2026-05-25** (upstream-sourced discipline classification, PR #156): §3 `IncludedDiscipline` + §5.3.3 endurance/protein band + §5.4.3 sport profile now describe deriving the classification from upstream `discipline_category` / `primary_movement` (no hand-maintained per-discipline dicts); §6.1 / §12 (2E-6) / §14 corrected to reflect that D-26 `supplement_vocabulary` shipped FC-1 (the §5.5 stub is an input-shape gap, not a vocab blocker).
**Type:** Query node. Pure read, deterministic given inputs, no LLM involvement.
**Supersedes:** the v3 stub `q_layer2e_nutrition_baseline_payload(...)` placeholder. Like 2D, the original signature was incomplete — 2E requires direct access to the athlete's §A demographics, §B health records, §H target events, and §I lifestyle/recovery data. v4 spec rewrite (FC-2) folds in the full signature.

---

## 1. Purpose

Given an athlete's demographics (§A), health records (§B), target events (§H), lifestyle/recovery profile (§I), and the disciplines they're training (2A output), plus Plan Management's heat acclim state, compute:

- A **per-phase daily nutrition baseline** (calorie target + macro split scaled to Base / Build / Peak / Taper)
- A **per-event race-day fueling plan** (CHO g/hr, Na mg/hr, fluid mL/hr, plus protein g/hr for >8 hr events) with sport- and tolerance-adjusted bands
- A **supplement integration view** that filters the athlete's existing protocol against `supplement_vocabulary` metadata, surfaces contraindications, and suggests race-day-specific additions
- **Dietary-pattern adjustments** (vegan B12/iron flags, low-FODMAP race fueling notes, allergen blocks)
- A **sleep-deprivation fueling overlay** for any target event with estimated duration >20 hr
- **Coaching flags** for non-gating concerns (heat-acclim gap before hot races, low calorie target relative to RMR, dietary-pattern micronutrient risk)
- **HITL items** that block plan-gen until the athlete confirms (supplement × current Cardiac, pregnancy × stimulants, anaphylaxis × unavoidable race aid)

2E's output, combined with 2A discipline weights and 2D filter, gives Layer 4 plan-gen the targets and constraints it needs to schedule meals, drive macro periodization, and prescribe race fueling. It does not generate the meals or recipes themselves.

## 2. What 2E does NOT do

Clarifying boundaries to prevent scope creep:

- **Does not generate meals or recipes.** Layer 4 or out of scope. 2E produces targets and constraints.
- **Does not adjust fueling mid-race.** That's Plan Management / Layer 4 in-race telemetry, not a 2E concern.
- **Does not track daily hydration.** Daily fluid is not specced as a 2E output. Race-day fluid is. Daily hydration is out of v1 scope (V3-I-9 candidate).
- **Does not recommend body composition changes.** Weight-loss or weight-gain targeting raises clinical-judgment liability that the app isn't credentialed for. 2E reports the calorie target from energy balance math; it does not prescribe a deficit or surplus.
- **Does not derive heat acclim state.** Plan Management system-tracks this from workout date + location + weather API. 2E consumes the state as input.
- **Does not run any LLM call.** All recommendations come from formula application, lookup tables, and set intersect.
- **Does not modify athlete records.** Pure read.
- **Does not pull aid-station stocking lists from event URLs.** Race aid-station detail is captured implicitly in §H Event URL + Race Rules and consumed by Layer 4 at race-week planning. 2E operates on athlete-level fueling characteristics.
- **Does not enforce LEA / RED-S surveillance.** Bone health and energy availability monitoring are out of v1 scope (deferred per Andy's 2026-05-11 scoping decision). Future work; see open items.
- **Does not consume 2C, 2D, or 2B output.** Parallel-classifier architecture (Control_Spec §2). Layer 3 cross-references outputs.

## 3. Function signature

```python
def q_layer2e_nutrition_baseline_payload(
    athlete_demographics: AthleteDemographics,        # §A
    health_records: HealthRecords,                    # §B (conditions, allergies, medications)
    target_events: list[TargetEvent],                 # §H.2 (when H.1 = Yes); empty list otherwise
    lifestyle_recovery: LifestyleRecovery,            # §I
    included_disciplines: list[IncludedDiscipline],   # 2A output (subset of payload)
    framework_sport: str,                             # 2A input, in sub-format-resolved form
    plan_management_state: PlanManagementState,       # Heat acclim, current phase
    etl_version_set: dict[str, str]
) -> Layer2EPayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `athlete_demographics` | AthleteDemographics | Layer 1 §A | sex, date_of_birth, height_cm, body_weight_kg, ffm_kg (optional) |
| `health_records` | HealthRecords | Layer 1 §B | conditions[], allergies[], medications[]. Status (Current / History) is on each record. |
| `target_events` | list[TargetEvent] | Layer 1 §H.2 | Empty list when §H.1 = No (athlete in time-based mode). Race-day fueling sub-payload only populates for events. |
| `lifestyle_recovery` | LifestyleRecovery | Layer 1 §I (structured form per handoff) | dietary_pattern[], supplements[] (record set), caffeine_*, fueling_format_pref[], fueling_shift_triggers[], gi_triggers[], salt_tolerance, sleep_dep, altitude_acclim |
| `included_disciplines` | list[IncludedDiscipline] | 2A `Layer2APayload.disciplines` | Subset: discipline_id, weight, role, plus the upstream `discipline_category` + `primary_movement` classification (plumbed by 2A from `layer0.disciplines`; see §5.3.3 / §5.4.3 — added 2026-05-25, upstream-sourced classification). Drives activity multiplier, the §5.3.3 endurance/protein band positions, and the race-day sport modifier. |
| `framework_sport` | str | 2A input, post-strip | Sub-format-named where applicable ("Triathlon (Standard / Olympic)", "Adventure Racing"). Used for phase_load_allocation lookup. |
| `plan_management_state` | PlanManagementState | Plan Management subsystem | current_phase (Base/Build/Peak/Taper), heat_acclim_state, expected_race_temp_c per event |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Per ETL spec v3 §5.1 Decision 2. Locks Layer 0 version for the plan. |

### Input record shapes

Defined in `Athlete_Onboarding_Data_Spec_v2.md` §A, §B, §H, §I (structured form). 2E imports them; the relevant fields:

```python
@dataclass
class AthleteDemographics:
    sex: str                                  # 'M' | 'F' (per §A)
    date_of_birth: date
    height_cm: float
    body_weight_kg: float                     # Most recent value
    ffm_kg: float | None                      # OPTIONAL — not currently in §A or §F; v3 onboarding candidate. None → fall back to Mifflin.

@dataclass
class HealthRecords:
    conditions: list[HealthConditionRecord]   # §B.4
    allergies: list[FoodAllergyRecord]        # §B Food Allergies & Intolerances
    medications: list[str]                    # §B Current Medications (multi-select enum)

@dataclass
class FoodAllergyRecord:
    name: str                                 # Free text + multi-select
    severity: str                             # 'Anaphylaxis' | 'Severe' | 'Moderate' | 'Mild GI' | 'Intolerance'
    notes: str | None

@dataclass
class TargetEvent:
    event_name: str
    event_date: date
    framework_sport: str                      # Sub-format-resolved
    estimated_duration_hr: float              # §H.2 race distance + estimated duration
    race_terrain_pct: dict[str, float]        # §H.2 terrain breakdown
    race_pack_weight_kg: float                # §H.2
    team_format: str                          # Individual / Unified / Relay / Doubles
    race_specific_nutrition_restrictions: str | None
    event_id: str                             # Internal ID for downstream cross-ref

@dataclass
class LifestyleRecovery:
    avg_nightly_sleep_hr: float
    sleep_quality: str                        # Poor / Fair / Good / Excellent
    work_life_stress: str                     # Low / Moderate / High / Variable
    dietary_pattern: list[str]                # Multi-select + free text 'other'
    supplements: list[AthleteSupplementRecord]  # §I.1 structured supplement protocol; FK to supplement_vocabulary
    caffeine_tolerance: str                   # None / Low / Moderate / High
    caffeine_daily_mg: float | None
    caffeine_race_day_strategy: str | None    # Same as daily / Loaded / Avoid / Variable
    caffeine_race_day_dose_mg: float | None
    fueling_format_pref: list[FuelingFormatPref]  # Multi-select with priority ranking
    fueling_shift_triggers: list[FuelingShiftTrigger]  # Structured multi-select (handoff: Hour / Intensity / GI-state / Temperature / None)
    gi_triggers: list[GITriggerCategory]      # Multi-select common categories + per-category specifics free-text
    salt_tolerance: str                       # Low / Standard / High
    salt_preferred_form: str                  # Capsule / Drink mix / Chew / Food-based / No preference
    sleep_dep: SleepDepProfile | None         # Populated only when any §H event has Estimated Duration > 20 hr
    altitude_acclim: AltitudeAcclimRecord | None

@dataclass
class AthleteSupplementRecord:
    supplement_id: str                        # FK to supplement_vocabulary.supplement_id; 'other' sentinel
    other_name: str | None
    dosage_amount: float
    dosage_unit: str
    timing: list[str]
    purpose: str | None

@dataclass
class IncludedDiscipline:
    discipline_id: str
    discipline_name: str
    weight: float                             # 2A's load weight, 0-1
    role: str                                 # Primary / Secondary / Conditional
    phase_load: PhaseLoadBands | None         # 2A pass-through from phase_load_allocation
    discipline_category: str | None           # Upstream terrain axis (layer0.disciplines), plumbed via 2A. Drives §5.3.3 endurance band. None → 'Mixed'.
    primary_movement: str | None              # Upstream movement axis (layer0.disciplines), plumbed via 2A. Drives §5.4.3 sport profile + §5.3.3 protein band. None → 'multi_sport'.

@dataclass
class PlanManagementState:
    current_phase: str                        # 'Base' | 'Build' | 'Peak' | 'Taper'
    heat_acclim_state: HeatAcclimState        # See §5.8
    expected_race_temp_c: dict[str, float | None]  # event_id → temp; None means unknown
```

The exact §I sub-field shapes for `FuelingFormatPref`, `FuelingShiftTrigger`, `GITriggerCategory`, `SleepDepProfile`, `AltitudeAcclimRecord`, and `PlanManagementState.HeatAcclimState` are not yet committed to a Layer 1 spec file as of this draft. The handoff describes the intent. 2E treats them as the structured-data contract it expects; if Layer 1 spec lands different sub-field names, 2E's signature updates accordingly. Tracked in §12 open items.

### Return type

See §7 below.

## 4. Input validation (preconditions)

Fail-loud on bad inputs. Validation runs before any DB query.

1. `athlete_demographics.sex` ∈ `{'M', 'F'}`.
2. `athlete_demographics.body_weight_kg` > 20 (sanity floor; ~44 lb; below this is suspect input).
3. `athlete_demographics.height_cm` > 100 (sanity floor; ~3'3").
4. `athlete_demographics.ffm_kg`, if present, < `body_weight_kg` and > 0.3 × `body_weight_kg` (sanity range; rejects obvious unit confusion).
5. `target_events` is a list (may be empty).
6. For each `TargetEvent`: `estimated_duration_hr` > 0, `event_date` ≥ today (if past, log WARN and skip race-day fueling for that event; profile still computes daily baseline).
7. Each `HealthConditionRecord.system_category` ∈ the 11-value enum per `Athlete_Onboarding_Data_Spec_v2.md` §B.4.1.
8. Each `AthleteSupplementRecord.supplement_id` either matches a row in `layer0.supplement_vocabulary` for the active 0C version OR equals `'other'` (with `other_name` populated). Unknown supplement_id → log WARN, skip from contraindication matching, surface in `unknown_supplements[]` coaching flag.
9. `included_disciplines` non-empty.
10. `framework_sport` non-empty string.
11. `plan_management_state.current_phase` ∈ `{'Base', 'Build', 'Peak', 'Taper'}`.
12. `etl_version_set` contains keys for `0A`, `0B`, `0C` at minimum.

Validation failure → raise `Layer2EInputError`. Plan-gen catches and surfaces a user-facing error. This is NOT a HITL gate — HITL is for ambiguous *content* (e.g., race-day supplement that contraindicates with current condition), not malformed inputs.

**Note on body weight currency:** 2E reads whatever `body_weight_kg` is currently on the athlete's profile. Plan Management is responsible for prompting re-entry on a cadence that matters for nutrition accuracy. If the athlete hasn't updated weight in >6 months, that's a Plan Management coaching surface, not a 2E hard gate.


## 5. Algorithm

### 5.1 Partition athlete data

```python
current_conditions = [c for c in health_records.conditions if c.status == 'Current']
history_conditions = [c for c in health_records.conditions if c.status == 'History']

active_supplements = [s for s in lifestyle_recovery.supplements]
# All §I.1 records are "currently taken" by definition — no Current/History split on supplements.

# Split allergies by severity for downstream HITL vs flag dispatch
anaphylaxis_allergies = [a for a in health_records.allergies if a.severity == 'Anaphylaxis']
other_allergies       = [a for a in health_records.allergies if a.severity != 'Anaphylaxis']

# Sub-partition target events by duration tier for race-day fueling sub-algorithm
events_by_tier: dict[str, list[TargetEvent]] = {}
for ev in target_events:
    tier = _classify_duration_tier(ev.estimated_duration_hr)   # see §5.4.1
    events_by_tier.setdefault(tier, []).append(ev)
```

`current_conditions` and `current_supplements` drive **HITL gates** and **contraindication flagging**. `history_conditions` drive **informational coaching flags** but never gate. `target_events` drive race-day fueling sub-payloads — daily baseline computes even when target_events is empty.

### 5.2 Daily calorie target

Two-step computation: BMR from one of two formulas, then activity-adjusted total.

#### 5.2.1 Basal Metabolic Rate

```python
def compute_bmr(demo: AthleteDemographics, today: date) -> tuple[float, str]:
    """Returns (bmr_kcal, method_used)."""
    age_years = _years_between(demo.date_of_birth, today)

    if demo.ffm_kg is not None:
        # Cunningham (1991): athletic-population validated
        bmr = 370 + 21.6 * demo.ffm_kg
        return bmr, 'cunningham_1991'

    # Mifflin-St Jeor (1990): general-population validated, ±10% accuracy for athletes
    base = (10 * demo.body_weight_kg) + (6.25 * demo.height_cm) - (5 * age_years)
    if demo.sex == 'M':
        bmr = base + 5
    else:
        bmr = base - 161
    return bmr, 'mifflin_st_jeor'
```

Cunningham (1991) is preferred when FFM is available because it indexes on lean mass rather than total body weight, which is the relevant metabolic compartment. Mifflin is the fallback when FFM is not collected.

**FFM provenance:** `ffm_kg` is currently NOT collected in §A or §F. Future onboarding addition tracked in §12 open items. For all current athletes, Mifflin runs. When FFM becomes available (DEXA, BodPod, BIA, or skinfold-derived), the spec automatically switches without code change.

**Sex enum and HRT note:** Per §A, sex is biological and HRT is captured separately via §B Medications. v1 nutrition baseline uses §A sex for the formula coefficient. A coaching flag fires if the athlete is on HRT (see §8.6) to surface the limitation rather than silently producing potentially wrong numbers. v2 spec for HRT × BMR adjustment is research-pending.

#### 5.2.2 Activity multiplier from phase load

```python
def compute_activity_multiplier(
    framework_sport: str,
    current_phase: str,
    etl_version_set: dict
) -> tuple[float, dict]:
    """Returns (multiplier, debug_info)."""
    # Pull weekly hours band for this sport × phase
    sql = """
        SELECT weekly_low_hours, weekly_high_hours
        FROM layer0.phase_load_weekly_totals
        WHERE sport_name = %s
          AND phase = %s
          AND etl_version = %s
          AND superseded_at IS NULL
    """
    row = q(sql, [framework_sport, current_phase, etl_version_set['0A']])

    if row is None:
        # Sport × phase missing (D-07: 4 sports affected as of 2026-05-10). Use phase default.
        return _phase_default_multiplier(current_phase), {'fallback': 'phase_default_no_pla_row'}

    weekly_hours_mid = (row.weekly_low_hours + row.weekly_high_hours) / 2
    multiplier = _lookup_multiplier_band(current_phase, weekly_hours_mid)
    return multiplier, {'weekly_hours_mid': weekly_hours_mid, 'phase': current_phase}
```

**Multiplier band table** (BMR multiplier scaling phase × volume):

| Phase | Low volume (<6 hr/wk) | Mid (6–10) | High (10–15) | Very high (15+) |
|---|---|---|---|---|
| Base | 1.40 | 1.55 | 1.70 | 1.85 |
| Build | 1.60 | 1.75 | 1.90 | 2.05 |
| Peak | 1.75 | 1.90 | 2.10 | 2.30 |
| Taper | 1.55 | 1.70 | 1.85 | 2.00 |

**Phase default fallback** (when no PLA row): Base 1.55, Build 1.75, Peak 1.90, Taper 1.70. Lands the athlete in mid-volume territory of their phase. Coaching flag fires (`pla_missing_for_sport_phase`).

**Source anchor:** Athletic-population activity multipliers per Burke (2018) and the ACSM Joint Position Stand (2016). Elite endurance athletes in peak training can exceed 2.5, but the table caps at 2.3 for v1 conservatism. v3 candidate: support athlete-reported per-day NEAT modifier for shift workers / standing-job athletes.

#### 5.2.3 Daily calorie target

```python
def compute_daily_calorie_target(
    bmr: float,
    multiplier: float
) -> int:
    """Round to nearest 50 kcal for athlete-facing display."""
    raw = bmr * multiplier
    return int(round(raw / 50) * 50)
```

**No deficit or surplus prescription.** 2E reports the energy-balance target for the athlete's current phase + load. If the athlete wants to lose or gain weight, that's a Layer 4 coaching surface or out of v1 scope. 2E never prescribes a body composition change.

**Cross-phase visibility:** 2E computes targets for **all four phases** (Base / Build / Peak / Taper), not only `current_phase`. Layer 4 needs the projected target for each phase the athlete will pass through. Daily baseline output is a 4-row sub-payload (`DailyNutritionBaseline.per_phase`).

### 5.3 Macro split by phase

Macro targets are computed per phase using `body_weight_kg` as the denominator. Phase scaling reflects carbohydrate periodisation: higher CHO during high-volume phases supports glycogen replenishment; lower CHO during low-volume phases supports metabolic flexibility without compromising recovery.

#### 5.3.1 Reference table (g/kg/day)

| Phase | CHO low | CHO high | Protein low | Protein high | Fat min |
|---|---|---|---|---|---|
| Base | 5.0 | 7.0 | 1.4 | 1.7 | 1.0 |
| Build | 6.0 | 9.0 | 1.6 | 1.9 | 1.0 |
| Peak | 7.0 | 12.0 | 1.7 | 2.0 | 1.0 |
| Taper | 5.0 | 7.0 | 1.6 | 1.9 | 1.0 |

**Source anchor:**
- CHO bands: Burke et al. (2018) "Re-Examining High-Fat Diets for Sports Performance"; Jeukendrup (2014) "A step towards personalized sports nutrition: carbohydrate intake during exercise"; ISSN position stand (2018, updated 2023)
- Protein: Phillips & Van Loon (2011) plus 2022 ISSN update; bands account for endurance-athlete elevations beyond general 0.8 g/kg RDA
- Fat floor: 1.0 g/kg minimum is a hormonal-function and fat-soluble-vitamin safety floor (Loucks, IOC RED-S guidance 2018)

#### 5.3.2 Computation

```python
def compute_macros_for_phase(
    phase: str,
    body_weight_kg: float,
    daily_calorie_target: int,
    discipline_mix: list[IncludedDiscipline]
) -> MacroTargets:
    band = MACRO_BANDS[phase]
    # Position within band scales with sport endurance profile + discipline weighting
    cho_position = _cho_band_position(discipline_mix)   # 0.0 = low, 1.0 = high
    cho_g_per_kg = band.cho_low + cho_position * (band.cho_high - band.cho_low)

    protein_position = _protein_band_position(discipline_mix)
    protein_g_per_kg = band.protein_low + protein_position * (band.protein_high - band.protein_low)

    cho_g = round(cho_g_per_kg * body_weight_kg)
    protein_g = round(protein_g_per_kg * body_weight_kg)

    cho_kcal = cho_g * 4
    protein_kcal = protein_g * 4
    fat_kcal = daily_calorie_target - cho_kcal - protein_kcal
    fat_g = round(fat_kcal / 9)

    # Verify fat floor
    fat_floor_g = round(band.fat_min * body_weight_kg)
    if fat_g < fat_floor_g:
        # Recompute: keep fat at floor, shrink CHO band position
        fat_g = fat_floor_g
        fat_kcal = fat_g * 9
        cho_kcal = daily_calorie_target - protein_kcal - fat_kcal
        cho_g = round(cho_kcal / 4)
        cho_g_per_kg = cho_g / body_weight_kg
        # Coaching flag: fat-floor-constrained target

    return MacroTargets(
        cho_g=cho_g, cho_g_per_kg=cho_g_per_kg, cho_kcal=cho_kcal,
        protein_g=protein_g, protein_g_per_kg=protein_g_per_kg, protein_kcal=protein_kcal,
        fat_g=fat_g, fat_kcal=fat_kcal
    )
```

#### 5.3.3 Discipline-mix-driven band position

**Endurance profile is sourced from upstream (2026-05-25, upstream-sourced classification).** Each discipline's endurance band comes from its `discipline_category` (the terrain axis on `layer0.disciplines`, plumbed via 2A onto `IncludedDiscipline.discipline_category`) — mapped by category-prefix to an endurance label `{Pure endurance | Mixed | Technical-dominant}` (aligned with Layer 0 `ENUM_ENDURANCE`), which the share-weighting below consumes. There is **no** hand-maintained `discipline_id → endurance_profile` dict (the prior v1 design did; it duplicated authoritative Layer 0 data it never read and drifted off the post-R6 taxonomy — the finding that drove this change). Missing/unknown category defaults to `Mixed`; a present-but-unrecognised value is logged.

```python
def _cho_band_position(disciplines: list[IncludedDiscipline]) -> float:
    """Higher CHO for endurance-heavy mixes; mid for mixed; lower for technical-dominant."""
    # Endurance profile derived per-discipline from upstream `discipline_category`
    # (category-prefix → {Pure endurance | Mixed | Technical-dominant}).
    profiles = [_endurance_profile(d) for d in disciplines]   # reads d.discipline_category
    weights = [d.weight for d in disciplines]
    pure_endurance_share = _weighted_share(profiles, weights, 'Pure endurance')
    mixed_share          = _weighted_share(profiles, weights, 'Mixed')
    # Position: 0.5 + 0.4 × pure_endurance_share − 0.2 × technical_share
    return min(1.0, max(0.0, 0.5 + 0.4 * pure_endurance_share - 0.2 * (1 - pure_endurance_share - mixed_share)))
```

Endurance-heavy mix (e.g., pure ultrarunning) lands near CHO high; technical-dominant mix (e.g., skimo with substantial mountaineering load) lands closer to CHO low. AR's multi-discipline mix is "Mixed" overall and lands near the band midpoint.

Protein band position is simpler — strength-biased movements push protein higher, detected from the upstream **movement** axis (`primary_movement`; `climbing` is the strength-biased movement in the Layer 0 vocabulary), not a hand-maintained strength-discipline id set:

```python
def _protein_band_position(disciplines: list[IncludedDiscipline]) -> float:
    """Strength-weighted disciplines push protein higher."""
    strength_share = sum(
        d.weight for d in disciplines
        if (d.primary_movement or '').lower() in _STRENGTH_MOVEMENTS   # {'climbing'}
    )
    return min(1.0, 0.4 + 0.6 * strength_share)
```

### 5.4 Race-day fueling per target event

If `target_events` is empty, this sub-payload is `[]`. Otherwise compute one `RaceDayFueling` record per event.

#### 5.4.1 Duration tier classification

```python
def _classify_duration_tier(hours: float) -> str:
    if hours <= 4:   return 'tier_short'           # ≤4 hr — sprint-to-mid AR, marathon, sprint tri
    if hours <= 12:  return 'tier_mid'             # 4–12 hr — half/full IM, 12-hr AR, 50-mile ultra
    if hours <= 24:  return 'tier_long'            # 12–24 hr — long AR, 100-mile ultra
    if hours <= 48:  return 'tier_expedition'      # 24–48 hr — expedition AR, 200-mile ultra
    return 'tier_extended_expedition'              # >48 hr — multi-day AR, 100+ hr efforts
```

#### 5.4.2 Base bands by tier

| Tier | CHO g/hr low | CHO high | Na mg/hr low | Na high | Fluid mL/hr low | Fluid high | Protein g/hr |
|---|---|---|---|---|---|---|---|
| Short (≤4 hr) | 60 | 90 | 500 | 800 | 500 | 750 | 0 |
| Mid (4–12) | 60 | 90 | 600 | 1000 | 400 | 700 | 0 |
| Long (12–24) | 50 | 80 | 500 | 800 | 400 | 700 | 0 (5 g/hr after hr 8) |
| Expedition (24–48) | 40 | 70 | 400 | 700 | scaled by exertion | scaled | 5–10 g/hr after hr 8 |
| Extended (>48) | 40 | 70 | 400 | 700 | scaled | scaled | 5–10 g/hr; mandatory food rotation |

**Source anchor:** Bands derived from WLDNCO fueling guides (6hr / 24hr / expedition), Jeukendrup (2023) "Carbohydrate periodization", BendRacing race nutrition guidance, ARWS feedback corpora from expedition AR field data. CHO ceilings at 90 g/hr assume multi-transporter blends (maltodextrin + fructose at 2:1); single-source caps near 60 g/hr.

**Format note:** Race-day fueling bands are spec-internal constants for v1. Promotion to a Layer 0 `race_fueling_bands` table is a future addition (tracked in §12). Pattern mirrors 2D's body-part keyword map: ship as code, promote to data when curation matters.

#### 5.4.3 Sport modifier

| Sport profile | CHO modifier | GI-risk note |
|---|---|---|
| Running-dominant | ×0.85 on upper band | Higher GI risk; cap real recommendations near 70 g/hr |
| Cycling-dominant | ×1.0 (use upper band freely) | Lower GI risk; trained guts handle 90+ g/hr |
| Swimming-dominant | ×0.6 (lower upper band) | Limited fueling windows; lower CHO ceiling |
| Paddling-dominant | ×0.9 | Position-restricted; mid CHO range |
| Multi-sport (AR / triathlon) | ×0.95 | Real-food bias; transitions enable variety |
| Skimo-dominant | ×0.9 | Cold-thermoregulation increases need; pocket access limits |

**Sport profile derivation (2026-05-25, upstream-sourced classification).** The sport-profile vote is sourced from each discipline's upstream `primary_movement` (the movement axis on `layer0.disciplines`, plumbed via 2A onto `IncludedDiscipline.primary_movement`) — **not** a hand-maintained `discipline_id → profile` dict. Each movement maps to a profile (`running`/`hiking` → Running-dominant; `cycling` → Cycling-dominant; `swimming` → Swimming-dominant; `paddling` → Paddling-dominant; `skiing` → Skimo-dominant; `climbing`/`navigation`/`other_skill` → Multi-sport). The weighted vote picks the profile with the largest load share; any mix where no single profile claims >50% (AR / triathlon) resolves to Multi-sport. The **movement** axis is required because the terrain `discipline_category` cannot distinguish swimming from paddling (both share a 'Water / *' category) — the original motivation for adding `primary_movement` to Layer 0. Missing/unrecognised `primary_movement` defaults to Multi-sport (a present-but-unknown value is logged).

#### 5.4.4 Athlete tolerance modifiers

```python
def apply_tolerance_modifiers(
    base_band: FuelingBand,
    lifestyle: LifestyleRecovery
) -> FuelingBand:
    band = base_band.copy()

    # Salt tolerance shifts Na band
    if lifestyle.salt_tolerance == 'Low':
        band.na_low *= 0.8
        band.na_high *= 0.8
        # Coaching flag: cramping risk in heat (see §8)
    elif lifestyle.salt_tolerance == 'High':
        band.na_low *= 1.2
        band.na_high *= 1.2

    # GI trigger categories filter format suggestions (handled downstream in §5.4.5)
    # No band number change — format filtering only.

    # Fueling format pref shifts recommended format mix (handled downstream)
    # No band number change.

    # Fueling shift triggers don't change race-day band — they drive race-week protocol
    # (gut-training session design, format rotation cadence). Surface in metadata.

    return band
```

#### 5.4.5 Format recommendations

For each event, output a `recommended_formats[]` list ranked by athlete preference and filtered by trigger categories:

```python
def recommend_formats(
    base_options: list[str],
    fueling_format_pref: list[FuelingFormatPref],
    gi_triggers: list[GITriggerCategory]
) -> list[str]:
    # Filter out trigger categories
    filtered = [opt for opt in base_options if opt not in _trigger_blocked_categories(gi_triggers)]
    # Rank by athlete preference order
    ranked = _rank_by_athlete_pref(filtered, fueling_format_pref)
    return ranked
```

Base options per tier:
- Short: gels, chews, drink mix, sports drink
- Mid: gels, chews, drink mix, real food (bars, fruit, sandwiches)
- Long+: real food bias, gels for spikes, drink mix for hydration
- Expedition: real food primary, gels/chews tactical only, hot food at extended stops

#### 5.4.6 Caffeine race-day integration

```python
def compute_caffeine_plan(
    lifestyle: LifestyleRecovery,
    event: TargetEvent
) -> CaffeineRacedayPlan | None:
    strategy = lifestyle.caffeine_race_day_strategy
    if strategy is None or lifestyle.caffeine_tolerance == 'None' or strategy == 'Avoid':
        return None

    body_weight = ... # from demographics; passed in or closed over
    if strategy == 'Same as daily':
        return CaffeineRacedayPlan(
            pre_race_mg=None,
            during_race_mg_per_hr=lifestyle.caffeine_daily_mg / 16 if lifestyle.caffeine_daily_mg else None,
            timing='maintain_daily_pattern',
            notes='Maintain habitual pattern; no special protocol'
        )
    elif strategy == 'Loaded':
        # Abstain 10–14 days, dose 3–6 mg/kg pre-race
        dose_mg = (lifestyle.caffeine_race_day_dose_mg
                   or _default_loaded_dose(body_weight))
        return CaffeineRacedayPlan(
            pre_race_mg=dose_mg,
            during_race_mg_per_hr=_loaded_during_race(event.estimated_duration_hr, dose_mg),
            timing='abstain_10_14d_then_load',
            notes='Insert 10–14 day abstinence in taper; first dose 30–60 min pre-start'
        )
    elif strategy == 'Variable by event length':
        return _variable_caffeine_plan(event.estimated_duration_hr, body_weight)
```

### 5.5 Supplement integration

For each athlete supplement record, look up `supplement_vocabulary`, surface contraindications.

```python
def integrate_supplements(
    supplements: list[AthleteSupplementRecord],
    current_conditions: list[HealthConditionRecord],
    allergies: list[FoodAllergyRecord],
    medications: list[str],
    is_pregnant: bool,
    target_events: list[TargetEvent],
    etl_version_set: dict
) -> SupplementIntegrationPayload:
    vocab = _load_supplement_vocab(etl_version_set['0C'])

    integrated = []
    flags = []
    hitl_items = []

    condition_categories = {c.system_category for c in current_conditions}
    allergen_keys = {f'allergen:{a.name.lower()}' for a in allergies}
    rx_keys = {f'rx:{m}' for m in medications}

    for record in supplements:
        if record.supplement_id == 'other':
            integrated.append(IntegratedSupplement(
                supplement_id='other',
                canonical_name=record.other_name,
                contraindication_hits=[],
                is_known=False
            ))
            continue

        vocab_row = vocab.get(record.supplement_id)
        if vocab_row is None:
            flags.append(CoachingFlag(
                flag_type='unknown_supplement',
                message=f'Supplement {record.supplement_id} not in vocabulary; cannot check contraindications.',
                ...
            ))
            continue

        contraindication_hits = []
        for contra in vocab_row.contraindications:
            if contra in condition_categories:
                contraindication_hits.append({'type': 'condition', 'value': contra})
            if contra in allergen_keys:
                contraindication_hits.append({'type': 'allergen', 'value': contra})
            if contra in rx_keys:
                contraindication_hits.append({'type': 'medication', 'value': contra})
            if contra == 'pregnancy' and is_pregnant:
                contraindication_hits.append({'type': 'pregnancy', 'value': contra})

        integrated.append(IntegratedSupplement(
            supplement_id=record.supplement_id,
            canonical_name=vocab_row.canonical_name,
            contraindication_hits=contraindication_hits,
            is_known=True
        ))

        # HITL dispatch for hard contraindications (see §5.9)
        for hit in contraindication_hits:
            if _is_hitl_contraindication(record.supplement_id, hit, current_conditions):
                hitl_items.append(_build_supplement_hitl(record, hit))
            else:
                flags.append(_build_supplement_flag(record, hit))

    # Race-day suggestions: for each event tier, recommend standard race-day supplements
    # if not already in athlete's protocol
    race_day_suggestions = _race_day_supplement_suggestions(
        target_events, supplements, lifestyle_recovery=None, vocab=vocab
    )

    return SupplementIntegrationPayload(
        integrated=integrated,
        race_day_suggestions=race_day_suggestions,
        contraindication_flags=flags,
        contraindication_hitl_items=hitl_items
    )
```

**Race-day suggestions:**

- Short tier: electrolyte_mix (if not already in protocol), optional sodium_bicarbonate (only for high-intensity sub-disciplines and only if athlete has tested it)
- Mid tier: electrolyte_mix, carb_powder (if not already in protocol), caffeine per §I.1.1 strategy
- Long tier: electrolyte_mix, carb_powder, caffeine per strategy, magnesium (post-race recovery cue)
- Expedition+: above plus omega_3 (anti-inflammatory, recovery support during the event), branched protein options for muscle preservation

Suggestions are *additive* to athlete protocol — never recommend deletion or replacement. If athlete already takes a recommended supplement, suppress the suggestion and tag in metadata.

### 5.6 Dietary pattern adjustments

```python
def dietary_pattern_adjustments(
    dietary_pattern: list[str],
    supplements: list[AthleteSupplementRecord]
) -> list[DietaryPatternFlag]:
    flags = []

    if 'Vegan' in dietary_pattern:
        athlete_supps = {s.supplement_id for s in supplements}
        if 'vitamin_b12' not in athlete_supps:
            flags.append(DietaryPatternFlag(
                pattern='Vegan', concern='b12_deficiency_risk',
                severity='moderate',
                rationale='Vegan diet without B12 supplementation creates measurable deficiency risk in 6–18 months.',
                suggested_supplement_id='vitamin_b12'
            ))
        if 'iron' not in athlete_supps:
            flags.append(DietaryPatternFlag(
                pattern='Vegan', concern='iron_status_risk',
                severity='low',
                rationale='Non-heme iron absorption is lower than heme; surveillance recommended via ferritin testing.',
                suggested_supplement_id='iron',
                requires_medical_guidance=True
            ))
        if 'omega_3' not in athlete_supps:
            flags.append(DietaryPatternFlag(
                pattern='Vegan', concern='epa_dha_conversion',
                severity='low',
                rationale='ALA→EPA/DHA conversion is inefficient; algae-derived EPA/DHA supplementation closes the gap.',
                suggested_supplement_id='omega_3'
            ))

    if 'Vegetarian' in dietary_pattern:
        # Milder than Vegan: B12 still a concern if no dairy/eggs
        # Iron less so
        ...

    if 'Pescatarian' in dietary_pattern:
        # Omega-3 covered; B12 likely OK from fish
        ...

    if 'Low-FODMAP' in dietary_pattern:
        flags.append(DietaryPatternFlag(
            pattern='Low-FODMAP', concern='race_fueling_format_constraint',
            severity='moderate',
            rationale='High-FODMAP gels (fructose-rich, polyol-containing) may trigger GI distress. Maltodextrin-dominant formats preferred.',
            race_day_format_adjustment='prefer_maltodextrin_dominant'
        ))

    return flags
```

Allergens are handled separately — they're hard constraints, not pattern flags. See §5.9 HITL triggers for anaphylaxis-class.

### 5.7 Sleep-deprivation fueling overlay

Triggered when **any** target event has `estimated_duration_hr > 20`. Reads `lifestyle_recovery.sleep_dep` (the structured §I.3 substructure).

```python
def sleep_dep_overlay(
    sleep_dep: SleepDepProfile | None,
    long_events: list[TargetEvent],
    caffeine_plan: CaffeineRacedayPlan | None
) -> SleepDepFuelingOverlay | None:
    if not long_events:
        return None

    return SleepDepFuelingOverlay(
        applicable_events=[ev.event_id for ev in long_events],
        cognitive_maintenance_protocol={
            'caffeine_strategic_windows': _caffeine_strategic_windows(caffeine_plan, long_events),
            'glucose_floor': 'maintain blood glucose >70 g/hr CHO during overnight phases',
            'protein_dose_overnight': '5–10 g/hr after hr 8 to slow glycogen depletion and support cognition'
        },
        warm_food_strategy={
            'recommendation': 'Hot food at extended stops increases palatability when GI fatigue compounds with cognitive fatigue',
            'frequency': 'every 8–12 hr depending on aid station spacing'
        },
        format_rotation={
            'rationale': 'Palate fatigue compounds in expedition events; rotate formats every 2–3 hr',
            'rotation_categories': ['sweet_gels', 'savory_real', 'liquid', 'chew_or_solid_sweet']
        },
        sleep_dep_specific_flags=_derive_flags_from_sleep_dep_profile(sleep_dep)
    )
```

**If `sleep_dep` is None but events have >20 hr duration:** the spec contract per §H.2 says collection is conditional and prompted when duration crosses 20 hr. If the athlete has not yet provided the data, surface coaching flag `sleep_dep_data_missing` and use defaults. Plan-gen still runs.

### 5.8 Heat acclimation overlay

Reads `plan_management_state.heat_acclim_state` and `plan_management_state.expected_race_temp_c` per event. Plan Management owns derivation.

```python
def heat_acclim_overlay(
    target_events: list[TargetEvent],
    plan_state: PlanManagementState,
    salt_tolerance: str
) -> list[HeatAcclimEventAdjustment]:
    adjustments = []

    for ev in target_events:
        expected_temp = plan_state.expected_race_temp_c.get(ev.event_id)
        if expected_temp is None:
            adjustments.append(HeatAcclimEventAdjustment(
                event_id=ev.event_id,
                temp_signal='unknown',
                na_modifier=1.0,
                fluid_modifier=1.0,
                flag=CoachingFlag(
                    flag_type='race_temp_unknown',
                    message=f'Expected race temp not yet computed for {ev.event_name}. Plan Management hasn\'t resolved a forecast yet.',
                ...)
            ))
            continue

        if expected_temp < 18:
            adjustments.append(HeatAcclimEventAdjustment(
                event_id=ev.event_id, temp_signal='cool',
                na_modifier=0.85, fluid_modifier=0.85, flag=None
            ))
        elif expected_temp < 26:
            adjustments.append(HeatAcclimEventAdjustment(
                event_id=ev.event_id, temp_signal='temperate',
                na_modifier=1.0, fluid_modifier=1.0, flag=None
            ))
        elif expected_temp < 32:
            # Warm-to-hot
            na_mod, fluid_mod, flag = _hot_event_adjustment(
                plan_state.heat_acclim_state, ev, salt_tolerance, severity='warm'
            )
            adjustments.append(HeatAcclimEventAdjustment(
                event_id=ev.event_id, temp_signal='warm', na_modifier=na_mod,
                fluid_modifier=fluid_mod, flag=flag
            ))
        else:
            # Hot (≥32 C)
            na_mod, fluid_mod, flag = _hot_event_adjustment(
                plan_state.heat_acclim_state, ev, salt_tolerance, severity='hot'
            )
            adjustments.append(HeatAcclimEventAdjustment(
                event_id=ev.event_id, temp_signal='hot', na_modifier=na_mod,
                fluid_modifier=fluid_mod, flag=flag
            ))

    return adjustments


def _hot_event_adjustment(
    heat_acclim_state: HeatAcclimState,
    event: TargetEvent,
    salt_tolerance: str,
    severity: str
) -> tuple[float, float, CoachingFlag | None]:
    # heat_acclim_state.level ∈ {'low', 'moderate', 'high'}
    # heat_acclim_state.days_at_temp_last_30 (numeric)
    # If low acclim and <14 days to event_date, flag heat-acclim-gap
    days_to_race = (event.event_date - date.today()).days
    if heat_acclim_state.level == 'low' and days_to_race < 14:
        flag = CoachingFlag(
            flag_type='heat_acclim_gap',
            event_id=event.event_id,
            message=f'{event.event_name} expected hot ({severity}); athlete heat acclim is low with {days_to_race} days to event. Insufficient time for full acclimatization (typically 10–14 days minimum).',
            severity='moderate',
            metadata={'heat_acclim_level': heat_acclim_state.level, 'days_to_race': days_to_race}
        )
    elif heat_acclim_state.level == 'low':
        flag = CoachingFlag(
            flag_type='heat_acclim_in_progress',
            event_id=event.event_id,
            message=f'{event.event_name} expected hot; heat acclim protocol should be active. Plan Management will sequence heat-stress sessions.',
            severity='info',
            metadata={'heat_acclim_level': heat_acclim_state.level}
        )
    else:
        flag = None

    # Na modifier: 1.15 for warm, 1.30 for hot. Adjust further by salt_tolerance later in §5.4.4.
    na_mod = 1.15 if severity == 'warm' else 1.30
    fluid_mod = 1.15 if severity == 'warm' else 1.35
    return na_mod, fluid_mod, flag
```

**HeatAcclimState contract** (Plan Management spec, not yet written):

```python
@dataclass
class HeatAcclimState:
    level: str                          # 'low' | 'moderate' | 'high'
    days_at_temp_last_30: int           # Count of training days at >25 C in last 30 days
    last_assessment: date
```

2E names this contract. Plan Management spec must honor it when it lands. Tracked in §12.

### 5.9 HITL triggers

Conservative gates per Andy's 2026-05-11 scoping decision. Each gate listed produces a HITL item that blocks Layer 3.5 / plan-gen until the athlete resolves.

| # | Gate | Trigger condition | Severity |
|---|---|---|---|
| 1 | Supplement × current Cardiac | Athlete's supplements contain any with `'Cardiac'` in `contraindications[]` AND athlete has a `HealthConditionRecord.system_category == 'Cardiac'` with `status == 'Current'`. Specific named: sodium_bicarbonate, caffeine (high-dose race-day) | block |
| 2 | Race-day caffeine × current Cardiac | Caffeine race-day strategy ∈ {Loaded, Variable} AND current Cardiac condition AND condition name suggests arrhythmia subtype (free-text match on athlete's condition name field for 'arrhythmia', 'tachycardia', 'fibrillation', 'WPW', 'palpitation'). Conservative: any Current Cardiac × Loaded strategy gates regardless of subtype | block |
| 3 | Pregnancy × race-day stimulant | `is_pregnant` (resolved from §B medications HRT class + free text) AND any supplement with `'pregnancy'` in contraindications. Examples: caffeine high-dose, ashwagandha, beetroot nitrate | block |
| 4 | Pregnancy × race-day supplement contraindicated | Pregnancy AND any non-stimulant supplement flagged `'pregnancy'` (e.g., high-dose iron without OB clearance, vitamin A excess) | block |

**Removed gate (FormRefresh A2, 2026-05-25):** the former gate 5 (Anaphylaxis × race aid) was dropped together with the `aid_stations` column. The project does not capture or plan for the anaphylaxis-aid-exposure scenario; race-day aid logistics are carried structurally by the `race_route_locales` graph, not a count.

**T1 Diabetes × long events:** explicitly NOT a HITL gate (Andy decision 2026-05-11). Treated as a coaching flag: surface that T1D athletes self-managing long events benefit from endocrinologist coordination, but do not block plan-gen.

```python
@dataclass
class Layer2EHitlItem:
    item_id: str
    gate_number: int                    # 1–4 per table above
    block_level: str                    # 'block' (others may be added in v2)
    affected_supplement_id: str | None
    affected_event_id: str | None
    affected_condition_category: str | None
    rationale_for_athlete: str          # User-facing copy
    rationale_for_layer3: str           # Structured machine-readable summary
    resolution_options: list[str]       # e.g., ['remove_supplement', 'medical_clearance_uploaded', 'acknowledge_risk']
```

Layer 3.5 renders these to the athlete with the resolution options as picker buttons.


## 6. Drift items affecting 2E + promotion candidates

### 6.1 Drift items currently affecting 2E queries

| Drift ID | Issue | Mitigation in 2E |
|---|---|---|
| D-05 | `phase_load_allocation` has 33 aggregator (WEEKLY TOTAL TARGET) rows not filtered by ETL | **Mandatory defensive filter** in any 2E query touching `phase_load_allocation` or `phase_load_weekly_totals`: `AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`. Standing rule per Control_Spec §8.2. Applied in §5.2.2. |
| D-06 | `phase_load_weekly_totals` columns `hours_low/high` deployed as `weekly_low_hours/high_hours` | 2E query uses deployed names (`weekly_low_hours`, `weekly_high_hours`). Spec rename in FC-2. |
| D-07 | 4 sports missing rows in `phase_load_weekly_totals` (Off-Road / Adventure Multisport (Non-Nav), 2× Open Water Marathon Swimming sub-formats, Swimrun) | Activity multiplier falls back to phase default with `pla_missing_for_sport_phase` coaching flag. AR is safe ✓. FC-1 fix. |
| D-17 | Non-AR sport naming mismatch between `sport_discipline_map` and `phase_load_allocation` (top-level vs sub-format) | 2E's `framework_sport` parameter is in the sub-format-resolved form (same as 2A consumes). Layer 1 §H must capture sub-format at race-goal setup. Design owner: Layer 1 race-goal capture spec. Tracked in §12. |
| D-21 | `health_condition_categories` column name reconciliation (deferred) | 2E's `current_conditions` matching against supplement contraindications is symbol-based (string match on system_category values, not column names). Reconciliation is FC-1 / FC-2 housekeeping; doesn't affect 2E correctness. |
| D-26 | `supplement_vocabulary` Layer 0 table | ✅ **Resolved (FC-1, 2026-05-11)** — table + 25 seed entries shipped via `etl/sources/migrate_supplement_vocabulary.sql`. No longer a blocker. The §5.5 supplement-integration stub roots in an **input-shape gap** (Layer 1 `Layer1Lifestyle.supplement_protocol_notes` is free text vs the spec's structured `list[AthleteSupplementRecord]`), not vocab availability — closed by the §I.1 structured-supplement form refresh (§12 2E-6, CARRY_FORWARD). |

### 6.2 Future Layer 0 promotion candidates (post-v1)

| Candidate | What lives in spec/code today | Why promote |
|---|---|---|
| `race_fueling_bands` table | §5.4.2 base bands (5×7 matrix) | Curated bands deserve auditable Layer 0 history. Splits curation from algorithm code. Pattern mirrors D-22 (`movement_components`) and D-23 (`body_parts_at_risk`) promotions. |
| `sport_endurance_modifier` table | §5.4.3 sport modifier (6×3 matrix) | Same rationale. Keyed on a derived "sport profile" classification now sourced from upstream `primary_movement` (2026-05-25); promoting the modifier matrix itself formalizes the band curation. |
| `dietary_pattern_adjustments` table | §5.6 logic (vegan B12/iron/EPA, low-FODMAP race adj, etc.) | Hand-curated rules with research citations; auditable in Layer 0 form. |
| `sport_mets_table` (Compendium-based) | None today (multiplier-based fallback used instead in §5.2.2) | Enables v3 MET-based activity multiplier path that's more precise than phase × volume lookup. |
| Per-discipline GI-risk classification | §5.4.3 sport modifier captures this indirectly | Tighter discipline-level (not sport-level) signal for race fueling format choice. |

Promotion is forward work, NOT a v1 blocker. Spec ships with code-level data per the 2D precedent.

## 7. Payload schema

```python
@dataclass
class Layer2EPayload:
    athlete_id: str
    etl_version_set: dict[str, str]
    computed_at: datetime
    bmr_method: str                                    # 'cunningham_1991' | 'mifflin_st_jeor'
    bmr_kcal: float
    daily_nutrition_baseline: DailyNutritionBaseline
    race_day_fueling: list[RaceDayFueling]             # One per target event; [] if none
    supplement_integration: SupplementIntegrationPayload
    dietary_pattern_adjustments: list[DietaryPatternFlag]
    sleep_dep_overlay: SleepDepFuelingOverlay | None
    heat_acclim_adjustments: list[HeatAcclimEventAdjustment]
    coaching_flags: list[CoachingFlag]
    hitl_items: list[Layer2EHitlItem]
    hitl_required: bool                                # True iff any hitl_items have block_level='block'


@dataclass
class DailyNutritionBaseline:
    per_phase: dict[str, DailyPhaseTargets]            # 'Base' | 'Build' | 'Peak' | 'Taper' → targets


@dataclass
class DailyPhaseTargets:
    activity_multiplier: float
    activity_multiplier_source: dict                   # debug from §5.2.2
    daily_calorie_target_kcal: int
    macros: MacroTargets


@dataclass
class MacroTargets:
    cho_g: int
    cho_g_per_kg: float
    cho_kcal: int
    protein_g: int
    protein_g_per_kg: float
    protein_kcal: int
    fat_g: int
    fat_kcal: int
    fat_floor_constrained: bool                        # True if computed CHO had to be reduced for fat floor


@dataclass
class RaceDayFueling:
    event_id: str
    event_name: str
    duration_tier: str                                 # tier_short | tier_mid | tier_long | tier_expedition | tier_extended_expedition
    cho_g_per_hr_low: float
    cho_g_per_hr_high: float
    na_mg_per_hr_low: float
    na_mg_per_hr_high: float
    fluid_ml_per_hr_low: float | None                  # None for expedition tiers (scaled by exertion)
    fluid_ml_per_hr_high: float | None
    protein_g_per_hr_after_hr_n: tuple[int, float, float] | None   # (hr_threshold, low, high)
    sport_modifier_applied: float
    salt_tolerance_modifier_applied: float
    heat_acclim_modifier_applied: float
    recommended_formats: list[str]                     # Ranked by athlete pref, filtered by GI triggers
    blocked_formats: list[str]                         # Filtered out due to GI triggers
    caffeine_plan: CaffeineRacedayPlan | None
    sleep_dep_overlay_applies: bool                    # True iff duration > 20 hr (cross-ref §5.7)
    notes: list[str]                                   # Human-readable caveats for Layer 4 surfacing


@dataclass
class CaffeineRacedayPlan:
    pre_race_mg: float | None
    during_race_mg_per_hr: float | None
    timing: str
    notes: str


@dataclass
class SupplementIntegrationPayload:
    integrated: list[IntegratedSupplement]
    race_day_suggestions: list[RaceDaySupplementSuggestion]
    contraindication_flags: list[CoachingFlag]
    contraindication_hitl_items: list[Layer2EHitlItem]


@dataclass
class IntegratedSupplement:
    supplement_id: str
    canonical_name: str
    is_known: bool                                     # False if 'other' or vocab miss
    contraindication_hits: list[dict]                  # Each: {type: 'condition'|'allergen'|'medication'|'pregnancy', value: str}


@dataclass
class RaceDaySupplementSuggestion:
    event_id: str
    supplement_id: str
    canonical_name: str
    reason: str                                        # Human-readable
    already_in_athlete_protocol: bool                  # If True, suggestion is suppressed in athlete-facing render


@dataclass
class DietaryPatternFlag:
    pattern: str
    concern: str                                       # e.g., 'b12_deficiency_risk', 'race_fueling_format_constraint'
    severity: str                                      # 'info' | 'low' | 'moderate'
    rationale: str
    suggested_supplement_id: str | None = None
    requires_medical_guidance: bool = False
    race_day_format_adjustment: str | None = None


@dataclass
class SleepDepFuelingOverlay:
    applicable_events: list[str]                       # event_ids
    cognitive_maintenance_protocol: dict
    warm_food_strategy: dict
    format_rotation: dict
    sleep_dep_specific_flags: list[CoachingFlag]


@dataclass
class HeatAcclimEventAdjustment:
    event_id: str
    temp_signal: str                                   # 'unknown' | 'cool' | 'temperate' | 'warm' | 'hot'
    na_modifier: float
    fluid_modifier: float
    flag: CoachingFlag | None


@dataclass
class CoachingFlag:
    flag_type: str
    event_id: str | None
    supplement_id: str | None
    message: str
    severity: str                                      # 'info' | 'low' | 'moderate' | 'high'
    metadata: dict
```

## 8. Coaching flag rules

Five active flag types fire from 2E. All surface in `coaching_flags[]` for Layer 3 to render.

### 8.1 `pla_missing_for_sport_phase`

Trigger: §5.2.2 fallback path (no `phase_load_weekly_totals` row for sport × phase).
Severity: `low`.
Affected: 4 sports (D-07): Off-Road / Adventure Multisport (Non-Nav), Open Water Marathon Swimming (10km), Open Water Marathon Swimming (25km), Swimrun. AR-safe.

### 8.2 `unknown_supplement`

Trigger: athlete's supplement record has `supplement_id` not in `supplement_vocabulary`.
Severity: `info`.
Metadata: surface `record.other_name` or `record.supplement_id` so the curator can promote to vocab if frequency rises.

### 8.3 `supplement_contraindication` (soft)

Trigger: athlete supplement has contraindication overlap that's NOT in the HITL list (§5.9 gates 1–5).
Examples: `omega_3` × `rx:anticoagulant` is a flag (medical coordination recommended), not a hard block.
Severity: `moderate`.

### 8.4 `dietary_pattern_deficiency_risk`

Trigger: §5.6 logic — vegan without B12, low-FODMAP athlete at a high-FODMAP-aid race, etc.
Severity: `low` to `moderate` per pattern × supplement absence.

### 8.5 `heat_acclim_gap` / `heat_acclim_in_progress` / `race_temp_unknown`

Trigger: §5.8 logic — hot race × low acclim × insufficient time; hot race × low acclim with time; race temp not yet forecasted by Plan Management.
Severity: `moderate`, `info`, `info` respectively.

### 8.6 `hrt_bmr_limitation`

Trigger: athlete on HRT (per §B Medications) AND BMR computed via Mifflin-St Jeor (since v1 doesn't have an HRT-aware formula).
Severity: `info`.
Surfaces the limitation rather than silently producing potentially miscalibrated calories.

### 8.7 `sleep_dep_data_missing`

Trigger: §H event with `estimated_duration_hr > 20` AND `lifestyle_recovery.sleep_dep is None`.
Severity: `low`.
Layer 4 / UI should prompt athlete to fill the §I.3 sub-structure.

### 8.8 `weight_data_stale` (advisory only)

Trigger: Plan Management reports the body weight on profile is >180 days old.
Severity: `info`.
2E doesn't compute the staleness itself — receives an advisory from `plan_management_state` if Plan Management chooses to surface it. v1: not implemented; placeholder for v2.

### 8.9 `low_calorie_target_relative_to_rmr` (replaces hard HITL gate per Andy decision)

Trigger: `daily_calorie_target_kcal` for any phase < `bmr * 1.2`. Catches plausible miscalibrations (very small athlete, very low volume reported) without making clinical judgments about disordered eating.
Severity: `low`.
Message points athlete to a sports dietitian if they want a precision check.

### 8.10 `t1d_long_event_coordination`

Trigger: athlete has Endocrine/Metabolic Current condition with name matching diabetes patterns AND any target event > 4 hr.
Severity: `moderate`.
Surface endocrinologist-coordination recommendation. Replaces what was originally a HITL gate; demoted per 2026-05-11 scoping.

## 9. Caching & determinism

Per ETL spec v3 §5.1 Decision 3: 2E is deterministic and cache-friendly.

**Cache key:**

```
(athlete_id,
 sha256(etl_version_set),
 sha256(canonicalize(athlete_demographics)),
 sha256(canonicalize(health_records)),
 sha256(canonicalize(target_events)),
 sha256(canonicalize(lifestyle_recovery)),
 sha256(canonicalize(included_disciplines)),
 framework_sport,
 sha256(canonicalize(plan_management_state)))
```

`athlete_id` is the primary key. The hashes of each input substructure mean any change to any field invalidates the entry — appropriate because 2E is fast (<500 ms; see §11).

**Invalidation triggers:**

| Layer 1 / 2A / Plan Management change | Invalidates |
|---|---|
| §A demographics (body weight, height, FFM, sex change) | all `(athlete_id, *)` entries |
| §B health conditions / allergies / medications | all `(athlete_id, *)` entries |
| §H target event added/changed/removed | all `(athlete_id, *)` entries |
| §I lifestyle/recovery (any sub-field) | all `(athlete_id, *)` entries |
| 2A discipline mix or weight | all `(athlete_id, *)` entries |
| Plan Management current_phase change | all `(athlete_id, *)` entries — but per-phase output means downstream Layer 4 can pick the right slice without re-running |
| Plan Management heat_acclim_state | invalidate entries containing target events with hot expected temps |
| New ETL run (etl_version_set change) | all entries with old hash |

No time-based expiration. Sticky until invalidated.

**Latency target:** <500 ms for a single 2E call. With small SQL footprint (3–5 queries on indexed tables, ~30 rows total) and pure Python math for the rest, well within budget.

## 10. Edge cases

| Case | Behavior |
|---|---|
| `target_events = []` (athlete in time-based mode per §H.1 = No) | Daily nutrition baseline still computes for all four phases. `race_day_fueling = []`, `sleep_dep_overlay = None`, `heat_acclim_adjustments = []`. No race-day supplement suggestions. |
| Multiple target events with overlapping date windows | Each event gets its own `RaceDayFueling` record. No cross-event reconciliation in 2E — Layer 4 handles taper-stacking conflicts. |
| Event in the past (event_date < today) | Log WARN, skip race-day fueling for that event. Profile still computes daily baseline. |
| Athlete on multiple Cardiac medications without a Cardiac condition record (medications imply condition) | §5.9 gate 1 fires only on the condition record, not on medications. Beta blocker presence triggers an `hrt_bmr_limitation`-style coaching flag (`beta_blocker_present`, not yet in §8 — v2 addition). Conservative: don't auto-infer a Cardiac condition from meds. |
| `caffeine_tolerance = 'None'` but `caffeine_race_day_strategy = 'Loaded'` | Input validation: inconsistent. Loaded strategy implies tolerance. Log WARN, set strategy to 'Same as daily' (defaults to maintenance, which for None = no caffeine). Coaching flag `caffeine_strategy_inconsistency`. |
| Athlete weight in lbs vs kg (unit confusion) | §A onboarding stores canonical kg. 2E receives kg. No conversion needed. UI-side validation against unit fields. |
| Anaphylaxis allergy with no aid-station-bound event | No HITL. Allergy still flagged in `dietary_pattern_adjustments` for daily training fueling. |
| Plan_management_state has `expected_race_temp_c = None` for an event | §5.8 produces `temp_signal='unknown'` adjustment with `race_temp_unknown` flag. No band modifier applied. |
| Athlete has FFM_kg listed at 0 or negative | Validation failure (precondition #4). Don't silently fall back to Mifflin — that hides a data-entry bug. |
| Athlete is on HRT and biological sex from §A is M but estrogen-class HRT (gender-affirming care) is present | v1: spec doesn't auto-adjust. Coaching flag `hrt_bmr_limitation` fires. Athlete and coach review the calorie target with explicit awareness of limitation. v2 work: research on HRT-aware BMR formulas. |
| Athlete in §H = No mode but with §I sleep_dep populated (residual from prior event) | OK. Daily baseline computes; sleep_dep_overlay = None because no >20hr event in current target list. Sleep_dep data harmless until next event. |
| Multiple `Vegan` + `Low-FODMAP` patterns simultaneously | Multiple `DietaryPatternFlag` records. Plan-gen renders both sets. Pattern-stacking is supported. |
| Phase load query returns 0 hours/wk for the current phase (data anomaly) | Activity multiplier falls to phase default. Coaching flag. Don't divide by zero anywhere. |
| Athlete has 30+ supplement records | Performance still under budget (set ops). Surface a coaching flag at >15 supplements: `extensive_supplement_protocol` — informational, recommend periodic review with a sports dietitian. |

## 11. Performance budget

Per Control_Spec §6 / 2D precedent: <500 ms for a single 2E call.

Breakdown:
- **§5.2.2 phase load query:** 1 indexed lookup on `phase_load_weekly_totals` × 4 phases. ~5 ms total.
- **§5.5 supplement vocab load:** 1 query on `supplement_vocabulary` (25 active rows). ~10 ms.
- **§5.6 dietary pattern logic:** pure Python on small lists. <5 ms.
- **§5.7 sleep_dep overlay:** pure Python. <5 ms.
- **§5.8 heat acclim per event:** ~5 ms × N events. <50 ms typical (1–3 events).
- **§5.9 HITL dispatch:** set intersect on small lists. <10 ms.
- **Aggregation + serialization:** <50 ms.

**Total per-athlete budget:** ~150 ms typical, ~300 ms worst case (many supplements, many events). Comfortable headroom under 500 ms.

If athlete has 5+ target events, scaling is linear in event count. Per-event budget ~50 ms. 10 events would land ~700 ms — outside budget for high-multi-event athletes; flag for monitoring if real-world data shows >5 events common.

## 12. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| 2E-1 | **FFM field promotion to §A or §F** (current §A captures body weight, §F captures performance test values, but neither captures FFM_kg) | Layer 1 onboarding v3 | Awaiting onboarding session |
| 2E-2 | **Plan Management `HeatAcclimState` contract** (§5.8 names the contract; Plan Management spec must honor) | Plan Management spec | Spec not yet written; will land post-Layer-3 |
| 2E-3 | **Plan Management `expected_race_temp_c` derivation** (location + date + weather API) | Plan Management spec | Same |
| 2E-4 | **Plan Management `current_phase` source-of-truth** (athlete is in a plan; phase is derived) | Plan Management spec | Same |
| 2E-5 | **D-17 sub-format selection in §H** — for non-AR sports, athlete's race goal must drive sub-format ("Triathlon (Standard / Olympic)" vs "Triathlon (Half Ironman)" etc.). 2E inherits the contract from 2A. | Layer 1 race-goal capture | Tracked in `Project_Backlog.md`; not 2E-blocking but a Layer 1 design gap |
| 2E-6 | **D-26 supplement_vocabulary table** — 25 seed entries. ~~Hard blocker.~~ ✅ Table shipped (FC-1, 2026-05-11). Remaining 2E-6 work is the §I.1 structured-supplement form refresh that de-stubs §5.5 (input-shape gap: free-text `supplement_protocol_notes` → structured `AthleteSupplementRecord` records), NOT the vocab table. | Onboarding §I.1 form refresh | Table ✅ Resolved; §5.5 de-stub awaiting structured-supplement capture |
| 2E-7 | **Race-day fueling band promotion to Layer 0** — §5.4.2 bands ship in code v1; promote to `race_fueling_bands` table when curation pressure rises | Future FC | Tracked in §6.2 |
| 2E-8 | **Sport endurance modifier table promotion** — §5.4.3 same pattern | Future FC | §6.2 |
| 2E-9 | **HRT × BMR research** — current spec produces miscalibrated BMR for HRT athletes (coaching flag surfaces the limitation; doesn't fix it) | Research | v2 candidate |
| 2E-10 | **Beta blocker × Cardiac inference** — should beta blocker presence imply a Cardiac condition for HITL purposes, or stay conservative (require explicit condition record)? Per §10 edge case, v1 stays conservative. | Future scoping | Defer until first-cohort data |
| 2E-11 | **Sport METs table** — enable v3 MET-based activity multiplier path more precise than v1 phase × volume lookup | Future FC | §6.2 |
| 2E-12 | **Pregnancy status capture** — currently 2E reads `is_pregnant` from §B (HRT class or free text). §B doesn't have an explicit pregnancy status field. Either add to §B or treat as a Health Condition record (Endocrine/Metabolic). | Onboarding v3 | Tracked |
| 2E-13 | **LEA / RED-S surveillance** — out of v1 scope per 2026-05-11 decision. Bone health, energy availability tracking deferred. | Future | v3+ |
| 2E-14 | **Per-discipline GI-risk classification** — currently sport-level; per-discipline would tighten race fueling format choice | Future FC | §6.2 |
| 2E-15 | **2E type confirmation** — query node (no LLM). Confirmed per 2026-05-11 scoping. No reason to revisit unless first-cohort feedback surfaces a reasoning gap. | — | Resolved |
| 2E-16 | **D-21 health_condition_categories rename** — column name reconciliation. 2E reads system_category values (strings), so column rename doesn't affect 2E correctness. FC-1 / FC-2 housekeeping. | FC-1/FC-2 | Tracked |

## 13. Test scenarios

These aren't unit tests yet — integration scenarios 2E must handle correctly. Spec'd so test coverage is clear when implementation begins.

### 13.1 Andy at PGE 2026 — expedition AR, multi-event mix

Inputs:
- `athlete_demographics`: sex=M, weight 80 kg (placeholder), height 178 cm (placeholder), DOB ~1985, FFM=None
- `health_records.conditions`: empty current; possibly some history records
- `health_records.allergies`: empty
- `health_records.medications`: empty
- `target_events`: [PGE 2026 — event_date 2026-07-17, duration 56 hr, terrain mix of trail/hike/MTB/packraft/climb/rappel, expected ~25 C in MN July]
- `lifestyle_recovery`: dietary_pattern=[Omnivore], supplements=[creatine, electrolyte_mix, magnesium (placeholder)], caffeine Moderate/Same-as-daily, salt Standard
- `included_disciplines`: 14 AR disciplines from 2A; mix weighted by phase
- `framework_sport`: "Adventure Racing"
- `plan_management_state`: current_phase=Build, heat_acclim_state=moderate (assumed), expected_race_temp_c={PGE: 25.0}

Expected output:
- BMR via Mifflin (no FFM): ~1850 kcal
- Activity multiplier for Build × ~10 hr/wk: ~1.75
- Daily calorie target ~3250 kcal
- Macros for Build: CHO ~520 g (6.5 g/kg), Protein ~140 g (1.75 g/kg), Fat ~95 g (rest)
- Race-day fueling for PGE: tier_expedition, CHO 40–70 g/hr (real-food bias), Na 400–700 mg/hr × 1.0 sport mod × 1.0 salt × 1.0 heat (temperate), fluid scaled by exertion, protein 5–10 g/hr after hr 8
- Sleep_dep overlay applies (56 hr > 20 hr): cognitive maintenance protocol; format rotation; warm food strategy
- Heat_acclim: temperate signal, no flag (25 C falls in temperate band 18–26)
- Supplement integration: creatine OK, electrolyte_mix OK, magnesium OK; no contraindications. Race-day suggestion: carb_powder (not in protocol).
- Coaching flags: none expected
- HITL: none expected
- `hitl_required = False`

This is the canonical test for 2E correctness on a real athlete in the system.

### 13.2 Hot-weather marathon × low heat acclim

Inputs:
- `athlete_demographics`: weight 65 kg, height 165 cm, sex F, age 38
- `target_events`: [Phoenix Marathon, event_date 2026-12-15, duration 4.2 hr, terrain road, expected 32 C (anomalous warm December)]
- `lifestyle_recovery`: salt_tolerance=Standard, dietary_pattern=Omnivore
- `framework_sport`: "Marathon"
- `plan_management_state`: heat_acclim_state.level='low', days_at_temp_last_30=2

Expected:
- Race-day fueling tier_short (4.2 hr): CHO 60–90 g/hr, Na 500–800 mg/hr ×1.30 heat modifier = 650–1040 mg/hr, fluid 500–750 mL/hr × 1.35 = 675–1015 mL/hr
- Heat acclim adjustment: temp_signal='hot', `heat_acclim_gap` flag fires (days_to_race depends on `today`; if < 14 days, gap; if more, in_progress flag)
- No HITL items.

### 13.3 Vegan ultrarunner × 100-mile event

Inputs:
- `athlete_demographics`: weight 58 kg, height 168 cm, sex F, age 32
- `target_events`: [Western States 100, duration 27 hr]
- `lifestyle_recovery`: dietary_pattern=[Vegan], supplements=[whey_protein...] — wait, vegan with whey is a conflict. Adjust: supplements=[plant_protein, beta_alanine, electrolyte_mix], no B12, no iron, no omega_3 yet
- `framework_sport`: "Long Distance Trail Running (Ultra)"
- 14-discipline mix dominated by trail running

Expected:
- Race-day fueling tier_long (27 hr → tier_expedition since >24 hr): real-food bias, CHO 40–70 g/hr
- Dietary pattern flags fire 3x: B12 deficiency risk (vitamin_b12 not in protocol), iron status risk (iron not in protocol; medical guidance recommended), EPA/DHA gap (omega_3 not in protocol)
- Sleep_dep overlay applies (27 hr)
- Sleep_dep_data_missing flag if athlete hasn't filled §I.3
- No HITL items.

### 13.4 Cardiac × race-day caffeine — HITL block

Inputs:
- `current_conditions`: [HealthConditionRecord(name='Atrial fibrillation', system_category='Cardiac', status='Current')]
- `lifestyle_recovery`: caffeine_tolerance=Moderate, caffeine_race_day_strategy='Loaded', caffeine_race_day_dose_mg=400
- `target_events`: [some marathon]

Expected:
- HITL gate 2 fires (`race_day_caffeine_x_cardiac`). `block_level='block'`. `hitl_required=True`. Resolution options: ['change_strategy_to_avoid', 'medical_clearance_uploaded', 'acknowledge_risk_with_athlete_signature'].
- Daily nutrition baseline still computes.
- Race-day fueling computes but flags `caffeine_plan_blocked_pending_resolution`.

### 13.5 Pregnant athlete × race-day stimulant — HITL block

Inputs:
- `health_records.medications`: includes HRT-class drug (or §B has explicit pregnancy flag if added)
- `is_pregnant`: True (resolved upstream)
- `lifestyle_recovery.supplements`: includes `caffeine` and `ashwagandha`
- `target_events`: [10K race]

Expected:
- HITL gates 3 + 4 fire (one per offending supplement). Two HITL items.
- `hitl_required=True`.
- Daily baseline computes.
- Coaching flag `hrt_bmr_limitation` fires.

### 13.6 Anaphylaxis × race aid HITL block — REMOVED (FormRefresh A2, 2026-05-25)

Gate 5 and the `aid_stations` column were removed; this scenario no
longer applies (see §5.9). Retained as a numbered placeholder so the
following scenario numbers stay stable.

### 13.7 Time-based mode — no events

Inputs:
- `target_events = []` (athlete in §H.1=No mode)
- All other inputs realistic

Expected:
- Daily nutrition baseline computes per phase.
- `race_day_fueling=[]`, `sleep_dep_overlay=None`, `heat_acclim_adjustments=[]`.
- Supplement integration: athlete's daily protocol integrated; no race-day suggestions.
- No HITL items from event-driven gates.

### 13.8 Missing PLA row — fallback path

Inputs:
- `framework_sport`: "Swimrun" (D-07 affected sport)
- `current_phase`: 'Build'

Expected:
- §5.2.2 falls to phase default multiplier (1.75).
- Coaching flag `pla_missing_for_sport_phase` fires.
- Other computation continues normally.

### 13.9 Athlete with FFM available — Cunningham path

Inputs:
- `athlete_demographics.ffm_kg = 62`

Expected:
- BMR = 370 + 21.6 × 62 = 1709 kcal
- `bmr_method = 'cunningham_1991'`
- All downstream math unchanged from Mifflin baseline structurally; only the kcal numbers shift.

### 13.10 Multiple-event athlete (rare but supported)

Inputs:
- `target_events`: [Boston Marathon April 2026, World's Toughest Mudder Nov 2026, expedition AR July 2026]
- Three distinct duration tiers (short, long, expedition)

Expected:
- 3× `RaceDayFueling` records, one per event, each with tier-specific bands.
- Daily baseline computes for current phase only.
- Per-event sleep_dep overlay only for expedition AR (>20 hr).
- Per-event heat acclim adjustments per Plan Management's `expected_race_temp_c` for each.

## 14. Gut check

**What this spec gets right:**
- Algorithm fully specified — BMR formulas explicit, multiplier band table explicit, macro band table explicit, race-day fueling bands explicit. No "TBD" math.
- Two-path BMR (Cunningham when FFM available, Mifflin otherwise) accommodates future onboarding evolution without requiring code change.
- Cross-phase visibility (compute all four phases at once) anticipates Layer 4's needs rather than forcing re-runs at phase transitions.
- Sport-modifier + tolerance-modifier composition is clear and auditable — a coach reviewing an athlete's bands can trace each adjustment.
- Heat acclim handoff to Plan Management names the contract explicitly. Plan Management spec must honor it; no implicit handshake.
- HITL gates are named, conservative, and athlete-resolvable (resolution options listed).
- T1D handling demoted from HITL to coaching flag per Andy's 2026-05-11 decision — preserves athlete autonomy without abandoning the surface.
- Test scenario 13.1 anchored on Andy's actual PGE 2026 race; integration tests can build on this.

**Risks:**
- **Macro band tables are opinionated.** Reasonable sports dietitians would set the bands ±15%. v1 cites the source anchors inline; future curation passes can adjust. Risk: bands shipped at the wrong end of the band-spread reduce plan quality for outliers.
- **Activity multiplier band table is opinionated.** Same issue. Multipliers for elite endurance athletes can exceed 2.5 in peak; current cap at 2.3 underfuels the elite cohort by ~5–10%. Acceptable for v1; revisit when elite-cohort data lands.
- **The fat floor at 1.0 g/kg can produce a fat-floor-constrained CHO target** in low-calorie scenarios (small athlete, low volume). 5.3.2 handles this by shrinking CHO band position; coaching flag fires. Edge case but real.
- **Plan Management contract dependencies (2E-2, 2E-3, 2E-4)** mean 2E can't ship in isolation — Plan Management must land first or 2E ships with stubbed state. This is a real coupling between layers that the parallel-classifier architecture otherwise avoids.
- **D-26 (supplement_vocabulary)** ~~is a hard implementation blocker~~ shipped (FC-1, 2026-05-11) — contraindication flags + HITL items can compute against the table. The residual §5.5 supplement-integration stub is an input-shape gap (free-text `supplement_protocol_notes` vs structured `AthleteSupplementRecord`), closed by the §I.1 form refresh — not a vocab blocker.
- **2E doesn't audit caloric intent.** If an athlete is under-eating relative to phase requirements (energy availability concern), 2E flags only the soft `low_calorie_target_relative_to_rmr` — and only when the *target* is low, not when the actual intake is. Actual intake tracking is Layer 4 / Plan Management. The gap is intentional but worth acknowledging.

**What might be missing:**
- **Sex-specific CHO oxidation curves.** Recent research (Devries 2022, Sims 2016+) suggests women have slightly different CHO oxidation patterns during exercise. v1 spec doesn't differentiate macro band position by sex. Probably <5% effect on targets; v3 candidate.
- **Vegetarian and pescatarian sub-pattern handling.** §5.6 sketches the logic but only Vegan and Low-FODMAP are fully spec'd. Vegetarian, Pescatarian, Halal, Kosher need fleshed-out flag logic. v2 cleanup.
- **Beta blocker handling.** Current spec marks it as a Cardiac-condition-only flag, not a medication-presence-only flag. Reasonable for v1 (avoid false inferences) but means an athlete on a beta blocker without a Cardiac condition record gets a coaching flag opportunity missed. 2E-10 tracks.
- **Per-event aid station fueling availability lookup.** Spec assumes Layer 4 reads race rules / event URL fetch and reconciles aid-station stocking. 2E doesn't currently model "this race has 2 aid stations, athlete needs to self-pack 80% of fuel." A Layer 4 surface; 2E provides the per-hour band only.
- **Carb loading protocol for events.** 2E mentions taper-phase carb loading (5.3 reference table comment) but doesn't spec the protocol. That's a Layer 4 plan-gen rendering concern more than a 2E target-setting concern, but the boundary is fuzzy.

**Best argument against this spec as drafted:**
2E is the most opinionated of the five Layer 2 nodes. Calorie targets, macro splits, and fueling bands are all band-based recommendations with material practitioner variance. Hard-coding even well-cited bands creates a single-source-of-truth that's harder to dispute than per-athlete reasoning would be. The alternative — letting the athlete or coach override every band — defeats the value proposition of the app (give me a recommendation, don't make me pick a band). The spec lands on the side of explicit recommendations + override flags, which is the right tradeoff for the product but creates curation pressure on §5.4.2, §5.3.1, and §5.2.2 tables.

Counter: every band is anchored on cited research. Disagreement is auditable. Future iterations can tighten or loosen bands without spec rewrites — just data updates once the tables promote to Layer 0 (§6.2). And the alternative LLM-reasoning path would produce more drift, less reproducibility, and worse latency. Ship the bands; curate them.

---

*End of spec. Open items 2E-1 through 2E-16 need Andy's decisions before implementation. Drift items D-05, D-07, D-17, D-21 confirmed as 2E-relevant; D-26 (supplement_vocabulary) resolved FC-1 2026-05-11 (its residual §5.5 stub is an input-shape gap, not a vocab blocker). §5.3.3 / §5.4.3 amended 2026-05-25 to the upstream-sourced discipline classification (see PR #156 closing handoff).*
