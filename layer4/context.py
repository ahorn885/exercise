"""Layer 4 upstream-context payload schemas — typed pydantic v2 mirrors of the
contracts Layer 4 consumes.

See:
- `aidstation-sources/Layer1_Spec.md` §7 → `Layer1Payload` (D-73 Phase 1.3
  typed-payload promotion 2026-05-19; mirrors D-51 §3 storage shipped in
  Phase 1.2A/B/C). Section-keyed sub-models (`Layer1Identity`,
  `Layer1HealthStatus`, `Layer1TrainingHistory`, `Layer1DisciplineBaselines`,
  `Layer1StrengthBenchmarks`, `Layer1Performance`, `Layer1Availability`,
  `Layer1EventGoal`, `Layer1Lifestyle`, `Layer1Network`, `Layer1Disclosures`)
  carry the full §A-§L view. Layer 4 entry points keep `dict[str, Any]`
  per `Upstream_Implementation_Plan_v1.md` §6 item 3 + §8 mitigation
  ("keep dict[str, Any] for v1; promote in v2"). The orchestrator
  (Phase 5) calls `.model_dump()` before threading to Layer 4.
- `aidstation-sources/Layer2A_Spec.md` §7 → `Layer2APayload`
- `aidstation-sources/Layer2B_Spec.md` §7 → `Layer2BPayload`
- `aidstation-sources/Layer2C_Spec.md` §7 (+ §5.6 amendment) → `Layer2CPayload`
- `aidstation-sources/Layer2D_Spec.md` §7 (+ §5.3.6 amendment) → `Layer2DPayload`
  + `AccommodationModality` discriminated union (6 variants).
- `aidstation-sources/Layer2E_Spec.md` §7 → `Layer2EPayload`
- `aidstation-sources/Layer3_3A_Spec.md` §7 → `Layer3APayload`
- `aidstation-sources/Layer3_3B_Spec.md` §7 → `Layer3BPayload`
- `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` §G.1 → `DailyAvailabilityWindow`
- `aidstation-sources/Race_Events_D66_Design_v1.md` §4 → `RaceEventPayload`
  + `RouteLocale` + `RouteLocaleEquipment` + `RaceFormat` + `RouteLocaleRole`
  (D-66 design wave shipped 2026-05-18; replaces v1 RaceEventStub placeholder).
- `Layer4_Spec.md` §5.4 forward-pointer — `PerDateRestriction` (pending D-67;
  always-empty in v1).

All models reject unknown keys (`extra='forbid'`) so untrusted upstream output
that drifts from the schema raises at construction. Domain-level rules
(volume bands, ACWR, injury exclusions, per-modality compliance, etc.) live
in the Layer 4 §5.4 validator harness, not here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ─── AccommodationModality discriminated union (Layer2D_Spec.md §7 / §5.3.6) ──
#
# Six modality variants. The literal `modality_type` field discriminates the
# union. Layer 4 synthesizer reads to apply modality-specific prescription
# adjustments; Layer 4 §5.4 `injury_accommodation_violation_*` validator
# reads to enforce per-modality compliance.


class VolumeReductionModality(_Base):
    modality_type: Literal["volume_reduction"] = "volume_reduction"
    factor: float = Field(ge=0.3, le=1.0)
    applies_to: Literal["sets", "reps", "duration"]
    rationale: str
    evidence_basis: list[str]


class IntensityReductionModality(_Base):
    modality_type: Literal["intensity_reduction"] = "intensity_reduction"
    factor: float = Field(ge=0.4, le=1.0)
    target_metric: Literal["percent_1rm", "rpe", "pace", "power", "hr_zone"]
    rationale: str
    evidence_basis: list[str]


class TempoModificationModality(_Base):
    modality_type: Literal["tempo_modification"] = "tempo_modification"
    tempo_pattern: Literal["eccentric_focus", "isometric_only", "heavy_slow_resistance"]
    eccentric_s: int | None = None
    isometric_bottom_s: int | None = None
    concentric_s: int | None = None
    isometric_top_s: int | None = None
    hold_s: int | None = Field(default=None, ge=15, le=60)
    sets: int | None = None
    rest_s: int | None = None
    intensity_pct_mvc: int | None = Field(default=None, ge=30, le=100)
    rationale: str
    evidence_basis: list[str]

    @model_validator(mode="after")
    def _check_pattern_fields(self) -> "TempoModificationModality":
        # `isometric_only` requires the isometric-protocol fields populated.
        if self.tempo_pattern == "isometric_only":
            if self.hold_s is None or self.sets is None or self.intensity_pct_mvc is None:
                raise ValueError(
                    "tempo_pattern=='isometric_only' requires hold_s, sets, intensity_pct_mvc non-None"
                )
        # `eccentric_focus` / `heavy_slow_resistance` need at least one tempo-tuple component.
        elif self.tempo_pattern in ("eccentric_focus", "heavy_slow_resistance"):
            if (
                self.eccentric_s is None
                and self.isometric_bottom_s is None
                and self.concentric_s is None
                and self.isometric_top_s is None
            ):
                raise ValueError(
                    f"tempo_pattern=='{self.tempo_pattern}' requires at least one of "
                    "eccentric_s/isometric_bottom_s/concentric_s/isometric_top_s non-None"
                )
        return self


class LoadingTypeChangeModality(_Base):
    modality_type: Literal["loading_type_change"] = "loading_type_change"
    from_type: Literal["bilateral", "barbell", "free_weight", "machine", "cable", "dumbbell"]
    to_type: Literal[
        "bilateral",
        "unilateral_contralateral",
        "unilateral_ipsilateral",
        "dumbbell",
        "machine",
        "cable",
        "assisted",
    ]
    rationale: str
    evidence_basis: list[str]


class FrequencyReductionModality(_Base):
    modality_type: Literal["frequency_reduction"] = "frequency_reduction"
    factor: float | None = Field(default=None, ge=0.0, le=1.0)
    sessions_per_week_cap: int | None = Field(default=None, ge=0)
    discipline_id: str | None = None
    rationale: str
    evidence_basis: list[str]

    @model_validator(mode="after")
    def _check_factor_xor_cap(self) -> "FrequencyReductionModality":
        if self.factor is None and self.sessions_per_week_cap is None:
            raise ValueError(
                "FrequencyReductionModality requires at least one of factor or sessions_per_week_cap non-None"
            )
        return self


class ExerciseSubstitutionModality(_Base):
    modality_type: Literal["exercise_substitution"] = "exercise_substitution"
    rationale: str
    evidence_basis: list[str]


AccommodationModality = Annotated[
    Union[
        VolumeReductionModality,
        IntensityReductionModality,
        TempoModificationModality,
        LoadingTypeChangeModality,
        FrequencyReductionModality,
        ExerciseSubstitutionModality,
    ],
    Field(discriminator="modality_type"),
]


# ─── Layer 2A — discipline mix (Layer2A_Spec.md §7) ──────────────────────────


class WeightResult(_Base):
    value: float | None
    source: Literal["system_default", "athlete_override"]
    system_default: float | None


class PhaseLoadBands(_Base):
    base_low: float | None = None
    base_high: float | None = None
    build_low: float | None = None
    build_high: float | None = None
    peak_low: float | None = None
    peak_high: float | None = None
    taper_low: float | None = None
    taper_high: float | None = None
    notes_conditions: str | None = None
    default_inclusion: Literal["included", "excluded", "prompt_required"]


class TrainingGap(_Base):
    gap_type: str
    notes: str
    multi_substitute_candidate: bool


class TrainingGapsSummary(_Base):
    flagged_count: int = Field(ge=0)
    any_no_substitute: bool
    any_multi_substitute_candidate: bool


class UnresolvedFlag(_Base):
    raw_input: str
    suggested_match: str | None = None
    severity: Literal["error", "warning"]


class Layer2ACoachingFlag(_Base):
    flag_type: str
    discipline_id: str | None = None
    message: str
    metadata: dict[str, Any]


class RationaleMetadata(_Base):
    template_version: str
    generated_at: str  # ISO timestamp string per spec


class Layer2ADiscipline(_Base):
    discipline_id: str
    discipline_name: str
    inclusion: Literal["included", "excluded", "prompt_required"]
    role: str  # 'Primary' | 'Secondary' | 'Minor' | 'Technical' (with *Conditional suffix)
    is_conditional: bool
    conditional_resolution: (
        Literal["race_rule_auto_in", "race_rule_auto_out", "athlete_opt_in"] | None
    ) = None
    load_weight: WeightResult
    race_time_pct_low: float | None = None
    race_time_pct_high: float | None = None
    sport_specific_context: str | None = None
    phase_load: PhaseLoadBands | None = None
    sleep_deprivation_relevant: bool
    training_gap: TrainingGap | None = None
    rationale: str


class Layer2APayload(_Base):
    framework_sport: str
    etl_version_set: dict[str, str]
    disciplines: list[Layer2ADiscipline]
    training_gaps_summary: TrainingGapsSummary
    hitl_required: bool
    unresolved_flags: list[UnresolvedFlag]
    coaching_flags: list[Layer2ACoachingFlag]
    rationale_metadata: RationaleMetadata


# ─── Layer 2B — terrain (Layer2B_Spec.md §7) ─────────────────────────────────


class RaceTerrainEntry(_Base):
    # Layer 2B input row. `terrain_id` must match the canonical TRN-\d{3}
    # vocabulary in `layer0.terrain_types`; `pct_of_race` is in [0.0, 100.0]
    # per `Layer2B_Spec.md` §3 + §4. The runtime validates the pattern + sum
    # bounds; the typed schema constrains the per-row range.
    terrain_id: str
    pct_of_race: float = Field(ge=0.0, le=100.0)


class TerrainGap(_Base):
    target_terrain_id: str
    target_terrain_name: str
    proxy_terrain_id: str | None = None
    proxy_terrain_name: str | None = None
    gap_severity: Literal["critical", "high", "medium", "low", "unbridgeable", "undefined"]
    adaptation_weeks_low: int | None = None
    adaptation_weeks_high: int | None = None
    proxy_fidelity: float | None = Field(default=None, ge=0.0, le=1.0)
    proxy_methods: list[str]
    uncoverable_stimulus: list[str]
    prescription_note: str
    discipline_relevance_assessed: bool


class RaceTerrainOutput(_Base):
    terrain_id: str
    terrain_name: str | None = None
    pct_of_race: float = Field(ge=0.0, le=100.0)
    available_locally: bool
    gap: TerrainGap | None = None


class Layer2BSummaryBlock(_Base):
    total_race_terrain_count: int = Field(ge=0)
    covered_count: int = Field(ge=0)
    gap_count: int = Field(ge=0)
    bridgeable_count: int = Field(ge=0)
    unbridgeable_count: int = Field(ge=0)
    min_adaptation_weeks_needed: int = Field(ge=0)
    worst_fidelity: float = Field(ge=0.0, le=1.0)
    pct_of_race_uncovered: float = Field(ge=0.0, le=100.0)
    any_unbridgeable: bool
    any_undefined: bool


class Layer2BCoachingFlag(_Base):
    flag_type: str
    target_terrain_id: str | None = None
    message: str
    metadata: dict[str, Any]


class Layer2BPayload(_Base):
    race_terrain: list[RaceTerrainOutput]
    terrain_gaps: list[TerrainGap]
    coaching_flags: list[Layer2BCoachingFlag]
    summary: Layer2BSummaryBlock
    etl_version_set: dict[str, str]


# ─── Layer 2C — equipment / modality (Layer2C_Spec.md §7 + §5.6 amendment) ───


class DisciplineCoverage(_Base):
    discipline_id: str
    discipline_name: str
    exercise_db_sport: str
    total_exercises: int = Field(ge=0)
    tier_1_count: int = Field(ge=0)
    tier_2_count: int = Field(ge=0)
    tier_3_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    coverage_pct: float = Field(ge=0.0, le=1.0)


class ResolutionDetail(_Base):
    substitute_text: str | None = None
    substitute_equipment: list[str] | None = None
    is_improvised: bool | None = None
    proxy_exercise_id: str | None = None
    proxy_exercise_name: str | None = None


class ResolvedExercise(_Base):
    exercise_id: str
    exercise_name: str
    exercise_type: str
    discipline_ids: list[str]
    sport_relevance_notes: dict[str, str]
    priority_per_discipline: dict[str, str]
    tier: Literal[0, 1, 2, 3]
    resolution_detail: ResolutionDetail | None = None
    terrain_required: list[str]
    contraindicated_parts: list[str]
    contraindicated_conditions: list[str]
    # ─── Per Layer2C_Spec.md §5.6 amendment (2026-05-17) — pass-through from 2D ──
    accommodations: list[AccommodationModality]


class Layer2CCoachingFlag(_Base):
    flag_type: Literal["low_coverage", "critical_dropped", "toggle_off_for_discipline"]
    discipline_id: str | None = None
    discipline_name: str | None = None
    affected_exercise_ids: list[str]
    message: str
    metadata: dict[str, Any]


class Layer2CPayload(_Base):
    locale_id: str
    etl_version_set: dict[str, str]
    effective_pool: list[str]
    discipline_coverage: list[DisciplineCoverage]
    exercises_resolved: list[ResolvedExercise]
    coaching_flags: list[Layer2CCoachingFlag]


# ─── Layer 2D — injury risk (Layer2D_Spec.md §7 + §5.3.6 amendment) ──────────


class Evidence(_Base):
    source: Literal["contraindicated_part", "contraindicated_condition", "movement_constraint"]
    exercise_field: str
    matched_value: str | None = None
    matched_keywords: list[str] | None = None
    injury_body_part: str | None = None
    injury_severity: str | None = None
    condition_category: str | None = None
    constraint: str | None = None


class ExerciseRisk(_Base):
    exercise_id: str
    exercise_name: str
    discipline_ids: list[str]
    verdict: Literal["exclude", "accommodate", "clean"]
    accommodations: list[AccommodationModality]
    evidence: list[Evidence]

    @model_validator(mode="after")
    def _check_verdict_accommodations(self) -> "ExerciseRisk":
        # §5.3.6: accommodations is non-empty iff verdict == 'accommodate'.
        # `exclude` + `clean` carry empty lists; `accommodate` carries ≥1 modality.
        if self.verdict == "accommodate":
            if not self.accommodations:
                raise ValueError(
                    "verdict=='accommodate' requires accommodations non-empty per §5.3.6"
                )
        elif self.accommodations:
            raise ValueError(
                f"verdict=='{self.verdict}' requires accommodations empty "
                "(only verdict=='accommodate' carries modalities per §5.3.6)"
            )
        return self


class MatchedBodyPart(_Base):
    body_part: str
    side: str
    severity: str
    matched_keywords: list[str]


class SubstituteRecommendation(_Base):
    substitute_discipline_id: str
    substitute_name: str
    fidelity: float = Field(ge=0.0, le=1.0)
    constraints: str | None = None
    category: str | None = None
    still_at_risk: bool
    still_at_risk_body_parts: list[str]


class DisciplineRisk(_Base):
    discipline_id: str
    discipline_name: str
    risk_level: Literal["low", "informational", "elevated", "high"]
    matched_current_parts: list[MatchedBodyPart]
    matched_history_parts: list[MatchedBodyPart]
    suggested_substitutes: list[SubstituteRecommendation]
    reasoning: str


class Layer2DCoachingFlag(_Base):
    flag_type: str
    discipline_id: str | None = None
    discipline_name: str | None = None
    message: str
    metadata: dict[str, Any]


class Layer2DHitlItem(_Base):
    # InjuryRecord + HealthConditionRecord (athlete onboarding contracts) are
    # not consumed by Layer 4 directly — kept opaque (dict[str, Any]) here to
    # avoid pulling Layer 1 onboarding types into Layer 4's context surface.
    hitl_type: Literal[
        "post_surgical_clearance",
        "cardiac_high_load_review",
        "concussion_current",
        "no_substitute_for_high_risk",
        "gap_x_high_risk_concurrent",
    ]
    discipline_id: str | None = None
    injury: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    severity: Literal["block", "warn"]
    message: str
    suggested_resolutions: list[str]


class Layer2DPayload(_Base):
    etl_version_set: dict[str, str]
    excluded_exercises: list[ExerciseRisk]
    accommodated_exercises: list[ExerciseRisk]
    clean_exercise_ids: list[str]
    discipline_risk_profiles: list[DisciplineRisk]
    coaching_flags: list[Layer2DCoachingFlag]
    hitl_required: bool
    hitl_items: list[Layer2DHitlItem]
    body_part_vocab_misses: list[str]
    condition_vocab_misses: list[str]

    @model_validator(mode="after")
    def _check_excluded_verdict(self) -> "Layer2DPayload":
        for er in self.excluded_exercises:
            if er.verdict != "exclude":
                raise ValueError(
                    f"excluded_exercises[{er.exercise_id}].verdict must be 'exclude' "
                    f"(got '{er.verdict}')"
                )
        for er in self.accommodated_exercises:
            if er.verdict != "accommodate":
                raise ValueError(
                    f"accommodated_exercises[{er.exercise_id}].verdict must be 'accommodate' "
                    f"(got '{er.verdict}')"
                )
        return self


# ─── Layer 2E — nutrition baseline (Layer2E_Spec.md §3 + §7) ─────────────────


class Layer2ETargetEvent(_Base):
    # Vertical-slice subset of the Layer2E_Spec.md §3 `TargetEvent` shape.
    # Fields race_terrain_pct / race_pack_weight_kg / team_format /
    # race_specific_nutrition_restrictions are deferred — they don't drive
    # any §5.2-§5.7 path the v1 builder ships. `aid_stations` is retained
    # because §5.9 gate 5 (anaphylaxis × aid-station-bound event) consumes
    # it; left optional so callers without §H.2 wired pass `None`.
    event_id: str
    event_name: str
    event_date: date
    framework_sport: str
    estimated_duration_hr: float = Field(gt=0)
    aid_stations: int | None = None


class MacroTargets(_Base):
    cho_g: int = Field(ge=0)
    cho_g_per_kg: float = Field(ge=0.0)
    cho_kcal: int = Field(ge=0)
    protein_g: int = Field(ge=0)
    protein_g_per_kg: float = Field(ge=0.0)
    protein_kcal: int = Field(ge=0)
    fat_g: int = Field(ge=0)
    fat_kcal: int = Field(ge=0)
    fat_floor_constrained: bool


class DailyPhaseTargets(_Base):
    activity_multiplier: float = Field(gt=0.0)
    activity_multiplier_source: dict[str, Any]
    daily_calorie_target_kcal: int = Field(ge=0)
    macros: MacroTargets


class DailyNutritionBaseline(_Base):
    per_phase: dict[Literal["Base", "Build", "Peak", "Taper"], DailyPhaseTargets]


class CaffeineRacedayPlan(_Base):
    pre_race_mg: float | None = None
    during_race_mg_per_hr: float | None = None
    timing: str
    notes: str


class RaceDayFueling(_Base):
    event_id: str
    event_name: str
    duration_tier: Literal[
        "tier_short", "tier_mid", "tier_long", "tier_expedition", "tier_extended_expedition"
    ]
    cho_g_per_hr_low: float = Field(ge=0.0)
    cho_g_per_hr_high: float = Field(ge=0.0)
    na_mg_per_hr_low: float = Field(ge=0.0)
    na_mg_per_hr_high: float = Field(ge=0.0)
    fluid_ml_per_hr_low: float | None = None
    fluid_ml_per_hr_high: float | None = None
    protein_g_per_hr_after_hr_n: tuple[int, float, float] | None = None
    sport_modifier_applied: float
    salt_tolerance_modifier_applied: float
    heat_acclim_modifier_applied: float
    recommended_formats: list[str]
    blocked_formats: list[str]
    caffeine_plan: CaffeineRacedayPlan | None = None
    sleep_dep_overlay_applies: bool
    notes: list[str]


class IntegratedSupplement(_Base):
    supplement_id: str
    canonical_name: str
    is_known: bool
    contraindication_hits: list[dict[str, Any]]


class RaceDaySupplementSuggestion(_Base):
    event_id: str
    supplement_id: str
    canonical_name: str
    reason: str
    already_in_athlete_protocol: bool


class Layer2ECoachingFlag(_Base):
    flag_type: str
    event_id: str | None = None
    supplement_id: str | None = None
    message: str
    severity: Literal["info", "low", "moderate", "high"]
    metadata: dict[str, Any]


class Layer2EHitlItem(_Base):
    # Per Layer2E_Spec.md §7 line 810. `block_level` typed as `str` (not Literal)
    # because spec line 813 notes 'block' is the current value with v2 additions
    # explicitly anticipated.
    item_id: str
    gate_number: int = Field(ge=1, le=5)
    block_level: str
    affected_supplement_id: str | None = None
    affected_event_id: str | None = None
    affected_condition_category: str | None = None
    rationale_for_athlete: str
    rationale_for_layer3: str
    resolution_options: list[str]


class SupplementIntegrationPayload(_Base):
    integrated: list[IntegratedSupplement]
    race_day_suggestions: list[RaceDaySupplementSuggestion]
    contraindication_flags: list[Layer2ECoachingFlag]
    contraindication_hitl_items: list[Layer2EHitlItem]


class DietaryPatternFlag(_Base):
    pattern: str
    concern: str
    severity: Literal["info", "low", "moderate"]
    rationale: str
    suggested_supplement_id: str | None = None
    requires_medical_guidance: bool = False
    race_day_format_adjustment: str | None = None


class SleepDepFuelingOverlay(_Base):
    applicable_events: list[str]
    cognitive_maintenance_protocol: dict[str, Any]
    warm_food_strategy: dict[str, Any]
    format_rotation: dict[str, Any]
    sleep_dep_specific_flags: list[Layer2ECoachingFlag]


class HeatAcclimEventAdjustment(_Base):
    event_id: str
    temp_signal: Literal["unknown", "cool", "temperate", "warm", "hot"]
    na_modifier: float
    fluid_modifier: float
    flag: Layer2ECoachingFlag | None = None


class Layer2EPayload(_Base):
    athlete_id: str
    etl_version_set: dict[str, str]
    computed_at: datetime
    bmr_method: Literal["cunningham_1991", "mifflin_st_jeor"]
    bmr_kcal: float = Field(ge=0.0)
    daily_nutrition_baseline: DailyNutritionBaseline
    race_day_fueling: list[RaceDayFueling]
    supplement_integration: SupplementIntegrationPayload
    dietary_pattern_adjustments: list[DietaryPatternFlag]
    sleep_dep_overlay: SleepDepFuelingOverlay | None = None
    heat_acclim_adjustments: list[HeatAcclimEventAdjustment]
    coaching_flags: list[Layer2ECoachingFlag]
    hitl_items: list[Layer2EHitlItem]
    hitl_required: bool


# ─── Shared Layer 3 observation (Layer3_3A_Spec.md §7 + Layer3_3B_Spec.md §7) ─


class Layer3Observation(_Base):
    category: Literal["warning", "opportunity", "data_gap", "data_hygiene"]
    text: str = Field(max_length=240)
    evidence_basis: list[str]
    elevates_to_hitl: bool


# ─── Layer 3A — athlete state (Layer3_3A_Spec.md §7) ─────────────────────────


class Assessment(_Base):
    level: Literal["low", "moderate", "good", "strong", "insufficient_data"]
    confidence: Literal["high", "medium", "low"]
    reasoning_text: str
    evidence_basis: list[str]


class CurrentState(_Base):
    aerobic_capacity: Assessment
    strength: Assessment
    weak_links: list[str] = Field(max_length=5)  # §7 schema-level rule: bounded by max_items=5
    skill_assessments: dict[str, Assessment]
    body_composition_notes: str | None = None


class TrajectoryWindow(_Base):
    direction: Literal[
        "overreached",
        "fatigued",
        "recovered",
        "steady",
        "building",
        "detrained",
        "peaking",
        "insufficient_data",
    ]
    reasoning_text: str
    evidence_basis: list[str]


class ACWREntry(_Base):
    acute_load: float = Field(ge=0.0)
    chronic_load: float = Field(ge=0.0)
    ratio: float = Field(ge=0.0)
    zone: Literal[
        "undertraining",
        "sweet_spot",
        "functional_overreach",
        "non_functional_overreach",
        "detraining",
    ]
    units: str


class ACWRStatus(_Base):
    per_discipline: dict[str, ACWREntry]
    combined: ACWREntry | None = None


class RecentTrajectory(_Base):
    short_term: TrajectoryWindow
    medium_term: TrajectoryWindow
    acwr_status: ACWRStatus
    confidence: Literal["high", "medium", "low"]


class DataDensity(_Base):
    connected_providers: list[str]
    integration_data_days: int = Field(ge=0)
    recent_workouts_count: int = Field(ge=0)
    recent_sleep_count: int = Field(ge=0)
    recent_hrv_count: int = Field(ge=0)
    self_report_freshness_days: int = Field(ge=0)
    section_completeness: dict[str, float]


class Layer3APayload(_Base):
    user_id: int
    as_of: datetime
    model: str
    temperature: float
    prompt_hash: str
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    etl_version_set: dict[str, str]
    current_state: CurrentState
    recent_trajectory: RecentTrajectory
    data_density: DataDensity
    notable_observations: list[Layer3Observation]


# ─── Layer 3B — viability + periodization (Layer3_3B_Spec.md §7) ─────────────


class GoalViability(_Base):
    viability: Literal["achievable", "achievable-with-adjustment", "unrealistic-as-stated"]
    confidence: Literal["high", "medium", "low"]
    reasoning_text: str
    evidence_basis: list[str]
    suggested_adjustments: list[str]

    @model_validator(mode="after")
    def _check_adjustments(self) -> "GoalViability":
        # §7 schema rule: `suggested_adjustments` non-empty when viability != 'achievable';
        # empty when viability == 'achievable'.
        if self.viability == "achievable":
            if self.suggested_adjustments:
                raise ValueError(
                    "viability=='achievable' requires suggested_adjustments empty"
                )
        else:
            if not self.suggested_adjustments:
                raise ValueError(
                    f"viability=='{self.viability}' requires suggested_adjustments non-empty"
                )
        return self


class PeriodizationShape(_Base):
    mode: Literal["standard", "compressed", "extended", "custom"]
    start_phase: Literal["Base", "Build", "Peak", "Taper"]
    phase_weeks: dict[Literal["Base", "Build", "Peak", "Taper"], int] | None = None
    reasoning_text: str
    evidence_basis: list[str]

    @model_validator(mode="after")
    def _check_phase_weeks(self) -> "PeriodizationShape":
        # §7 schema rule: phase_weeks non-None iff mode == 'custom'.
        if self.mode == "custom":
            if self.phase_weeks is None:
                raise ValueError("mode=='custom' requires phase_weeks non-None")
        else:
            if self.phase_weeks is not None:
                raise ValueError(f"mode=='{self.mode}' requires phase_weeks is None")
        return self


class Layer3BHITLItem(_Base):
    source: Literal["3B"]
    item_label: str
    severity: Literal["blocker", "warning", "informational"]
    description: str
    recommended_action: str
    acknowledge_option: str | None = None
    revise_option: str
    revise_target: str

    @model_validator(mode="after")
    def _check_blocker_acknowledge(self) -> "Layer3BHITLItem":
        # §7: acknowledge_option is None when severity == 'blocker'.
        if self.severity == "blocker" and self.acknowledge_option is not None:
            raise ValueError("severity=='blocker' requires acknowledge_option is None")
        return self


class Layer3BPayload(_Base):
    user_id: int
    as_of: datetime
    mode: Literal["event", "no-event"]
    model: str
    temperature: float
    prompt_hash: str
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    etl_version_set: dict[str, str]
    goal_viability: GoalViability
    periodization_shape: PeriodizationShape
    hitl_surface: list[Layer3BHITLItem]
    notable_observations: list[Layer3Observation] = Field(max_length=6)

    # ─── Event metadata (D-66 amendment 2026-05-18) ──────────────────────
    # Sourced from `race_events WHERE user_id=? AND is_target_event=true`
    # per `Race_Events_D66_Design_v1.md` §8 (Layer 3B reads the target row).
    # All four fields are None when `mode == 'no-event'`. When `mode ==
    # 'event'`, populated fields drive Layer 4 race-week-brief §4.5
    # preconditions + Layer 3B's mode='event' periodization decisions.
    # Paired `Layer3_3B_Spec.md` §7 amendment lands in the same session.
    event_date: date | None = None
    event_locale_id: str | None = None
    race_format: (
        Literal["single_day", "expedition_ar", "stage_race", "multi_day_ultra"] | None
    ) = None
    time_to_event_weeks: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_hitl_unique_labels(self) -> "Layer3BPayload":
        # §7 schema rule: hitl_surface items have unique item_label.
        labels = [h.item_label for h in self.hitl_surface]
        if len(labels) != len(set(labels)):
            raise ValueError("hitl_surface item_labels must be unique")
        return self

    @model_validator(mode="after")
    def _check_event_mode_consistency(self) -> "Layer3BPayload":
        # D-66 schema rule: when mode == 'no-event', all 4 event-metadata
        # fields are None. When mode == 'event', the orchestrator populates
        # the fields from the target race_events row; None still tolerated
        # for the partial-build case (race row exists but distance/locale
        # not yet set by the athlete). Defensive consistency check only.
        if self.mode == "no-event":
            if (
                self.event_date is not None
                or self.event_locale_id is not None
                or self.race_format is not None
                or self.time_to_event_weeks is not None
            ):
                raise ValueError(
                    "mode=='no-event' requires event_date / event_locale_id / "
                    "race_format / time_to_event_weeks all None"
                )
        return self


# ─── DailyAvailabilityWindow (Athlete_Onboarding_Data_Spec_v5.md §G.1) ───────


class DailyAvailabilityWindow(_Base):
    day_of_week: Literal["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    enabled: bool
    window_start: str | None = None  # time-of-day "HH:MM"; None when enabled=False
    window_duration: int | None = Field(default=None, ge=30, le=360)
    second_window_start: str | None = None
    second_window_duration: int | None = Field(default=None, ge=30, le=360)
    long_session_available: bool | None = None
    long_session_max_duration: Literal[2, 3, 4, 5, 6, 8] | None = None  # hours
    doubles_feasible: Literal["regularly", "occasionally", "no"]
    preferred_rest_day: bool

    @model_validator(mode="after")
    def _check_enabled_invariants(self) -> "DailyAvailabilityWindow":
        # If disabled, window fields must be absent. If enabled, primary window must be set.
        if not self.enabled:
            if (
                self.window_start is not None
                or self.window_duration is not None
                or self.second_window_start is not None
                or self.second_window_duration is not None
            ):
                raise ValueError(
                    "enabled=False requires window_start/duration + second_window_* all None"
                )
        else:
            if self.window_start is None or self.window_duration is None:
                raise ValueError(
                    "enabled=True requires window_start + window_duration non-None"
                )
        return self

    @model_validator(mode="after")
    def _check_second_window_pair(self) -> "DailyAvailabilityWindow":
        # Second window fields must be jointly populated or jointly null.
        s_start_set = self.second_window_start is not None
        s_dur_set = self.second_window_duration is not None
        if s_start_set != s_dur_set:
            raise ValueError(
                "second_window_start and second_window_duration must be both set or both None"
            )
        # Second window is only consultable when doubles_feasible != 'no'.
        if s_start_set and self.doubles_feasible == "no":
            raise ValueError(
                "second_window_* requires doubles_feasible != 'no'"
            )
        return self


# ─── RaceEventPayload (D-66 design wave 2026-05-18) ──────────────────────────
#
# Replaces the v1 RaceEventStub placeholder. Mirrors the new PG tables
# `race_events` + `race_route_locales` + `race_route_locale_equipment` per
# `Race_Events_D66_Design_v1.md` §3; consumed by `llm_layer4_race_week_brief`
# per `Layer4_Spec.md` §3.4 amendment. Orchestrator-side join reads from
# `race_events WHERE user_id=? AND is_target_event=true LIMIT 1` per design
# doc §10.


RaceFormat = Literal["single_day", "expedition_ar", "stage_race", "multi_day_ultra"]
RouteLocaleRole = Literal[
    "start",
    "transition_area",
    "aid_station",
    "drop_bag_point",
    "bivvy",
    "finish",
    "other",
]


class RouteLocaleEquipment(_Base):
    equipment_name: str = Field(..., min_length=1, max_length=160)
    quantity_text: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=400)


class RouteLocale(_Base):
    route_locale_id: int  # FK to race_route_locales(id)
    role: RouteLocaleRole
    sequence_idx: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=160)
    mile_marker: Decimal | None = Field(default=None, ge=0)
    lat: Decimal | None = None
    lng: Decimal | None = None
    mapbox_id: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=800)
    equipment: list[RouteLocaleEquipment] = Field(default_factory=list)


class RaceEventPayload(_Base):
    race_event_id: int
    user_id: int
    name: str = Field(..., min_length=1, max_length=200)
    event_date: date
    race_format: RaceFormat
    distance_km: Decimal | None = Field(default=None, ge=0)
    total_elevation_gain_m: Decimal | None = Field(default=None, ge=0)
    race_rules_summary: str | None = Field(default=None, max_length=8000)
    mandatory_gear_text: str | None = Field(default=None, max_length=8000)
    # D-72 resolved 2026-05-19 — slug everywhere across the typed pipeline.
    # The DB column race_events.event_locale_id is BIGINT FK to
    # locale_profiles(id); race_events_repo.load_race_event_payload JOINs
    # locale_profiles to surface the slug here. Aligns with
    # Layer2CPayload.locale_id + Layer3BPayload.event_locale_id + the dict
    # key in layer2c_payloads + PlanSession.locale_id + the slug-based
    # cache-key formulas in layer4/hashing.py. The DB surrogate id stays
    # the right shape for ON DELETE SET NULL behavior; it just doesn't
    # cross the typed-payload boundary.
    event_locale_id: str | None = None
    is_target_event: bool
    notes: str | None = Field(default=None, max_length=2000)
    route_locales: list[RouteLocale] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_route_locales_invariants(self) -> "RaceEventPayload":
        # §4.2 structural invariants from Race_Events_D66_Design_v1.md:
        # (1) sequence_idx unique within the payload's route_locales list.
        # (2) sorted ascending by sequence_idx (caller-side sort guaranteed
        #     by the orchestrator-side ORDER BY clause; defensive here).
        # (3) when non-empty: first role == 'start' AND last role == 'finish'
        #     (caller-side check; empty route_locales legal and surfaces via
        #     validator rule `kit_manifest_inputs_incomplete_no_route_locales`).
        if not self.route_locales:
            return self
        seq_ids = [rl.sequence_idx for rl in self.route_locales]
        if len(seq_ids) != len(set(seq_ids)):
            raise ValueError(
                "RaceEventPayload.route_locales sequence_idx values must be unique"
            )
        if seq_ids != sorted(seq_ids):
            raise ValueError(
                "RaceEventPayload.route_locales must be sorted ascending by sequence_idx"
            )
        if self.route_locales[0].role != "start":
            raise ValueError(
                "RaceEventPayload.route_locales first entry must have role=='start' "
                "when route_locales non-empty"
            )
        if self.route_locales[-1].role != "finish":
            raise ValueError(
                "RaceEventPayload.route_locales last entry must have role=='finish' "
                "when route_locales non-empty"
            )
        return self


# ─── PerDateRestriction (placeholder pending D-67; always-empty in v1) ───────


class PerDateRestriction(_Base):
    date: datetime
    locale_lock: str | None = None
    discipline_exclusions: list[str] = Field(default_factory=list)
    indoor_only: bool = False
    max_total_minutes: int | None = Field(default=None, ge=0)


# ─── Layer2Bundle (Layer4_Spec.md §3.2 plan_refresh signature) ───────────────
#
# Typed wrapper exposing the five Layer 2 sub-payloads. Each attribute is
# None when that layer was not re-run for the current refresh (per the D-64
# default cascade + parsed_intent triggers). T1 default cascade: all None
# except as added by parsed_intent. T2 default: same (Layer 2 still not
# re-run unless intent-triggered; 3B IS re-run on T2). T3 default: all five
# populated.


class Layer2Bundle(_Base):
    a: Layer2APayload | None = None
    b: Layer2BPayload | None = None
    c: dict[str, Layer2CPayload] = Field(default_factory=dict)
    d: Layer2DPayload | None = None
    e: Layer2EPayload | None = None


# ─── ParsedIntent (Plan_Refresh_D64_Design_v1.md §5.2) ───────────────────────
#
# NL parser output consumed by Layer 4 plan-refresh entry point. Carries the
# 5 upstream-layer re-run flags, 3 soft signals (fatigue/sickness/motivation),
# the raw_text pass-through, parser confidence, and optional ambiguity notes.
# When the NL parser is unavailable, D-64 returns a degraded ParsedIntent with
# all flags False, signals at default, parser_confidence='low'.


class ParsedIntent(_Base):
    # Upstream-layer re-run flags (added to tier's default cascade; never subtracted)
    triggers_2a_discipline: bool = False
    triggers_2b_terrain: bool = False
    triggers_2c_equipment: list[str] = Field(default_factory=list)
    triggers_2d_injury: bool = False
    triggers_2e_nutrition: bool = False

    # Soft signals (passed to Layer 4 as context, not full re-runs)
    fatigue_signal: Literal["fresh", "normal", "tired", "wiped"] = "normal"
    sickness_signal: Literal["none", "recovering", "active"] = "none"
    motivation_signal: Literal["low", "normal", "high"] = "normal"

    # Free-text passthrough (always included for Layer 4 context)
    raw_text: str = ""

    # Confidence + ambiguity
    parser_confidence: Literal["high", "medium", "low"] = "high"
    ambiguity_notes: str | None = None


# ─── Layer 1 — athlete profile aggregation (Layer1_Spec.md §7) ───────────────
#
# Typed mirror of the D-51 §3 storage shipped in D-73 Phase 1.2A/B/C
# (athlete_profile + 7 per-discipline 1:1 sub-tables + 8 multi-row tables +
# strength_benchmarks + daily_availability_windows + body_metrics +
# wellness_self_report joinpoints). Section-keyed sub-models follow the
# v5 §A-§L spec structure. Top-level convenience fields surface the keys
# Layer 4 entry points currently `.get(...)` from the opaque dict
# (experience_level / coaching_voice_preferences / available_days_per_week
# / travel_constraint / sleep_baseline / daily_availability_windows) so
# `.model_dump()` produces a dict consumable by Layer 4 unchanged per
# `Upstream_Implementation_Plan_v1.md` §6 item 3 mitigation.


# §A — identity
class Layer1Identity(_Base):
    date_of_birth: date | None = None
    sex: Literal["male", "female"] | None = None
    height_cm: float | None = None
    primary_sport: str | None = None
    weekly_hours_target: float | None = None
    notes: str | None = None


# §B — health status sub-records
#
# D-73 Phase 2.2 expanded InjuryRecord to mirror Athlete_Onboarding_Data_Spec_v5
# §B.1: injury_type (§B.1.1 11-enum), severity (§B.1 6-enum — replaces legacy
# 1-5 int), side (4-enum), movement_constraints (§B.3 11-enum multi-select).
# Layer 2D dispatches on injury_type × severity (§5.3.6) and severity → verdict
# (§5.3.4); movement_constraints drive §5.3.3 keyword matching against
# layer0.exercises.injury_flags_text. severity / injury_type / movement_constraints
# stay Optional because pre-Phase-2.2 rows may carry NULL during the migration
# transition window — Layer 2D treats NULL injury_type as the V1_FALLBACK bucket
# and NULL severity as a defensive fallthrough.
class InjuryRecord(_Base):
    injury_id: int
    body_part: str
    description: str | None = None
    severity: Literal[
        "Acute",
        "Recovering",
        "Chronic-Managed",
        "Post-surgical",
        "Structural-Permanent",
        "Resolved",
    ] | None = None
    injury_type: Literal[
        "Acute soft tissue (strain / sprain / tear)",
        "Tendinopathy / overuse",
        "Joint (mechanical) — non-surgical",
        "Joint (mechanical) — surgical",
        "Bone (fracture / contusion) — non-stress",
        "Bone — stress fracture",
        "Skin / surface (burn / abrasion / laceration)",
        "Nerve",
        "Inflammatory (bursitis / fasciitis)",
        "Post-surgical",
        "Other / uncertain",
    ] | None = None
    side: Literal["Left", "Right", "Both", "N/A"] = "N/A"
    movement_constraints: list[
        Literal[
            "Pain with loading",
            "Pain with impact",
            "Pain above specific joint angle",
            "Pain on descent / eccentric",
            "Pain on rotation",
            "Pain with grip / sustained hold",
            "Pain with wrist extension",
            "Pain with overhead movement",
            "Instability",
            "Reduced ROM",
            "Pain at high volume only",
        ]
    ] = Field(default_factory=list)
    status: Literal["Active", "Resolved", "Inactive"]
    start_date: date | None = None
    resolved_date: date | None = None
    modifications_needed: str | None = None


class HealthConditionRecord(_Base):
    condition_id: int
    system_category: Literal[
        "cardiac",
        "respiratory",
        "metabolic",
        "neurological",
        "gi_immune",
        "musculoskeletal",
        "endocrine",
        "other",
    ]
    condition_name: str
    severity: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    status: Literal["Active", "Resolved", "Inactive"]
    start_date: date | None = None
    resolved_date: date | None = None


class MedicationRecord(_Base):
    medication_id: int
    medication_class: Literal[
        "beta_blocker",
        "diuretic",
        "nsaid_chronic",
        "hrt",
        "ssri",
        "stimulant_adhd",
        "corticosteroid_chronic",
        "anticoagulant",
        "other",
    ]
    medication_name: str | None = None
    started_at: date | None = None
    stopped_at: date | None = None
    notes: str | None = None


class FoodAllergyRecord(_Base):
    allergy_id: int
    allergen_category: Literal[
        "tree_nut",
        "peanut",
        "dairy",
        "gluten",
        "egg",
        "shellfish",
        "fish",
        "soy",
        "nightshade",
        "fodmap",
        "caffeine_sensitivity",
        "other",
    ]
    severity: Literal["intolerance", "allergy", "anaphylaxis"]
    notes: str | None = None


class Layer1HealthStatus(_Base):
    current_injuries: list[InjuryRecord] = Field(default_factory=list)
    injury_history: list[InjuryRecord] = Field(default_factory=list)
    health_conditions_active: list[HealthConditionRecord] = Field(default_factory=list)
    health_conditions_history: list[HealthConditionRecord] = Field(default_factory=list)
    medications_active: list[MedicationRecord] = Field(default_factory=list)
    medications_history: list[MedicationRecord] = Field(default_factory=list)
    food_allergies: list[FoodAllergyRecord] = Field(default_factory=list)
    resting_hr_bpm: int | None = None


# §C — training history sub-records
class SecondarySportRecord(_Base):
    sport_slug: str
    experience_tier: Literal["under_1yr", "1_to_3yr", "3plus_yr"]


class DisciplineWeightRecord(_Base):
    discipline_slug: str
    weight_pct: int = Field(ge=0, le=100)


class RecentRaceResult(_Base):
    event_name: str
    event_date: date
    distance_km: float | None = None
    finish_time_seconds: int | None = Field(default=None, ge=0)
    result_notes: str | None = None
    source: str


class PackLoadRecord(_Base):
    pack_weight_kg: float = Field(ge=0)
    session_count_4wk: int | None = Field(default=None, ge=0)
    longest_session_hrs: float | None = Field(default=None, ge=0)
    terrain_type: str | None = None
    notes: str | None = None


class Layer1TrainingHistory(_Base):
    years_structured_training: int | None = Field(default=None, ge=0)
    peak_weekly_volume_hrs: float | None = Field(default=None, ge=0)
    peak_weekly_volume_year: int | None = None
    longest_event_completed: str | None = None
    training_consistency_disrupted_weeks: int | None = Field(default=None, ge=0, le=52)
    training_consistency_cause: str | None = None
    previous_coaching: Literal["self", "online_plan", "coach", "none"] | None = None
    secondary_sports: list[SecondarySportRecord] = Field(default_factory=list)
    discipline_weighting: list[DisciplineWeightRecord] = Field(default_factory=list)
    recent_race_results: list[RecentRaceResult] = Field(default_factory=list)
    pack_load_history: list[PackLoadRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_weighting_sum(self) -> "Layer1TrainingHistory":
        # §3.3 design wave invariant: per-user sum across rows = 100 when any
        # weighting rows exist (intermediate edit states would surface here as
        # builder-time mismatches, so the rule is application-validated; this
        # check fires only when the builder assembles a complete row set).
        if not self.discipline_weighting:
            return self
        total = sum(r.weight_pct for r in self.discipline_weighting)
        if total != 100:
            raise ValueError(
                f"discipline_weighting weight_pct must sum to 100 when any rows exist "
                f"(got {total} across {len(self.discipline_weighting)} rows)"
            )
        return self


# §D — discipline baselines
class RunningBaseline(_Base):
    easy_run_pace_sec_per_km: int | None = Field(default=None, ge=0)
    vertical_gain_weekly_m: float | None = Field(default=None, ge=0)
    vertical_gain_peak_session_m: float | None = Field(default=None, ge=0)
    trail_experience_terrain: list[
        Literal["moderate", "technical", "mountain", "moorland"]
    ] = Field(default_factory=list)
    downhill_adaptation: bool | None = None
    downhill_sessions_3mo: int | None = Field(default=None, ge=0)
    night_running: bool | None = None
    gut_training_g_per_hr_cho: int | None = Field(default=None, ge=0)
    gut_training_issues: str | None = None


class CyclingBaseline(_Base):
    bike_types_available: list[str] = Field(default_factory=list)
    mtb_skill: Literal["beginner", "intermediate", "advanced"] | None = None
    longest_ride_distance_km: float | None = Field(default=None, ge=0)
    longest_ride_hrs: float | None = Field(default=None, ge=0)
    saddle_endurance_hrs: float | None = Field(default=None, ge=0)
    aero_endurance_min: int | None = Field(default=None, ge=0)


class SwimmingBaseline(_Base):
    pool_100m_pace_sec: int | None = Field(default=None, ge=0)
    ow_experience: Literal["none", "limited", "experienced"] | None = None
    wetsuit_experience: bool | None = None
    cold_water_experience: bool | None = None
    ow_feeding_experience: bool | None = None
    weekly_swim_volume_km: float | None = Field(default=None, ge=0)


class PaddlingBaseline(_Base):
    longest_paddle_km: float | None = Field(default=None, ge=0)
    longest_paddle_hrs: float | None = Field(default=None, ge=0)
    paddle_craft_types: list[Literal["kayak", "canoe", "packraft", "surfski"]] = Field(
        default_factory=list
    )


class SkiingBaseline(_Base):
    ski_disciplines: list[Literal["classic_xc", "skate_xc", "skimo"]] = Field(
        default_factory=list
    )
    weekly_ski_volume_hrs: float | None = Field(default=None, ge=0)


class NavigationBaseline(_Base):
    experience_level: Literal["none", "map_only", "map_compass", "expert"] | None = None
    night_nav_experience: bool | None = None


class TechnicalBaseline(_Base):
    # rock_climbing_*_grade are free-text multi-system (Yosemite Decimal /
    # French Sport / UIAA) per Layer 4 Step 4a precedent — design wave §3.4
    # intentionally left these unconstrained.
    rock_climbing_outdoor_grade: str | None = None
    rock_climbing_indoor_grade: str | None = None
    abseiling_experience: bool | None = None


class Layer1DisciplineBaselines(_Base):
    running: RunningBaseline | None = None
    cycling: CyclingBaseline | None = None
    swimming: SwimmingBaseline | None = None
    paddling: PaddlingBaseline | None = None
    skiing: SkiingBaseline | None = None
    navigation: NavigationBaseline | None = None
    technical: TechnicalBaseline | None = None


# §E — strength benchmarks (1:1 strength_benchmarks)
class Layer1StrengthBenchmarks(_Base):
    front_plank_sec: int | None = Field(default=None, ge=0)
    dead_bug_max_reps: int | None = Field(default=None, ge=0)
    side_plank_left_sec: int | None = Field(default=None, ge=0)
    side_plank_right_sec: int | None = Field(default=None, ge=0)
    pushup_max_reps: int | None = Field(default=None, ge=0)
    bodyweight_squat_max_reps: int | None = Field(default=None, ge=0)
    single_leg_squat_left_max_reps: int | None = Field(default=None, ge=0)
    single_leg_squat_right_max_reps: int | None = Field(default=None, ge=0)
    pullup_max_reps: int | None = Field(default=None, ge=0)
    dead_hang_sec: int | None = Field(default=None, ge=0)
    grip_strength_left_kg: float | None = Field(default=None, ge=0)
    grip_strength_right_kg: float | None = Field(default=None, ge=0)
    last_tested_at: date | None = None


# §F — performance baselines
class Layer1Performance(_Base):
    body_weight_kg: float | None = Field(default=None, ge=0)
    hrmax_bpm: int | None = Field(default=None, ge=0)
    hrmax_source: str | None = None
    lactate_threshold_hr_bpm: int | None = Field(default=None, ge=0)
    lt_method: str | None = None
    vo2max: float | None = Field(default=None, ge=0)
    vo2max_source: str | None = None
    cycling_ftp_w: int | None = Field(default=None, ge=0)
    cycling_ftp_test_date: date | None = None
    running_threshold_pace_sec_per_km: int | None = Field(default=None, ge=0)
    running_threshold_test_date: date | None = None
    css_swim_sec_per_100m: int | None = Field(default=None, ge=0)
    css_test_date: date | None = None


# §G — per-week capacity scalars (per-day windows are at top-level
# `Layer1Payload.daily_availability_windows`).
class Layer1Availability(_Base):
    long_session_available: bool = False
    long_session_days: list[str] = Field(default_factory=list)
    long_session_max_hr: Literal[2, 3, 4, 5, 6, 8] | None = None
    doubles_feasible: Literal["regularly", "occasionally", "no"] | None = None
    preferred_rest_days: list[str] = Field(default_factory=list)


# §H — event/goal
class Layer1EventGoal(_Base):
    target_race_event_id: int | None = None
    plan_duration_weeks_no_event: Literal[8, 12, 16, 20, 24] | None = None
    non_event_goal_type: Literal[
        "endurance", "general_fitness", "strength", "mixed"
    ] | None = None


# §I — lifestyle
class Layer1Lifestyle(_Base):
    sleep_baseline_hours: float | None = Field(default=None, ge=0)
    work_stress_level: Literal["low", "moderate", "high", "variable"] | None = None
    dietary_pattern: list[str] = Field(default_factory=list)
    supplement_protocol_notes: str | None = None
    caffeine_tolerance: Literal["none", "low", "moderate", "high"] | None = None
    caffeine_daily_mg_estimate: int | None = Field(default=None, ge=0)
    caffeine_race_day_strategy: Literal[
        "caffeine_loading", "taper", "maintain", "avoid"
    ] | None = None
    altitude_acclimatization_history: bool | None = None
    altitude_max_exposure_m: int | None = Field(default=None, ge=0)
    altitude_exposure_count: int | None = Field(default=None, ge=0)
    fueling_format_preference: list[str] = Field(default_factory=list)
    gi_triggers_known: str | None = None
    salt_electrolyte_tolerance: Literal["low", "moderate", "high"] | None = None
    sleep_deprivation_max_hrs_continuous_awake: int | None = Field(default=None, ge=0)
    sleep_deprivation_strategy_notes: str | None = None


# §L — network
class AthleteNetworkLink(_Base):
    link_id: int
    partner_name: str
    linked_account_user_id: int | None = None
    relationship_types: list[
        Literal[
            "training_partner",
            "race_teammate",
            "coach",
            "family",
            "pacer",
            "crew",
        ]
    ] = Field(default_factory=list)
    partner_specific_rules: str | None = None
    race_event_id: int | None = None
    discipline_focus_on_team: str | None = None


class LinkedPartnerConsent(_Base):
    consent_id: int
    link_id: int
    consent_scope: Literal["none", "activity_summaries", "full_plan_access"]
    granted_at: datetime
    revoked_at: datetime | None = None


class Layer1Network(_Base):
    network_links: list[AthleteNetworkLink] = Field(default_factory=list)
    linked_partner_consents: list[LinkedPartnerConsent] = Field(default_factory=list)


# §A.1 — disclosures (latest-ack per disclosure_id)
class DisclosureAck(_Base):
    disclosure_id: str
    version_id: str | None = None
    scopes_granted: str | None = None
    delivery_method: Literal["in_app", "email"]
    acknowledged_at: datetime


class Layer1Disclosures(_Base):
    acknowledgments: list[DisclosureAck] = Field(default_factory=list)


# ─── Layer1Payload (top-level) ───────────────────────────────────────────────


class Layer1Payload(_Base):
    user_id: int
    as_of: datetime

    # Layer-4-consumed convenience fields (top-level so `.model_dump()` produces
    # a dict where Layer 4's `.get("experience_level")` etc. continue to work
    # per `Upstream_Implementation_Plan_v1.md` §8 mitigation). `experience_level`
    # / `coaching_voice_preferences` / `travel_constraint` carry no v1 storage —
    # builder leaves them None; derivation is a future Layer 1 enhancement.
    experience_level: Literal[
        "novice", "developing", "intermediate", "advanced", "elite"
    ] | None = None
    coaching_voice_preferences: str | None = None
    available_days_per_week: int | None = Field(default=None, ge=0, le=7)
    travel_constraint: str | None = None
    sleep_baseline: float | None = Field(default=None, ge=0)
    daily_availability_windows: list[DailyAvailabilityWindow] = Field(default_factory=list)

    # Full §A-§L mirror.
    identity: Layer1Identity
    health_status: Layer1HealthStatus
    training_history: Layer1TrainingHistory
    discipline_baselines: Layer1DisciplineBaselines
    strength_benchmarks: Layer1StrengthBenchmarks | None = None
    performance: Layer1Performance
    availability: Layer1Availability
    event_goal: Layer1EventGoal
    lifestyle: Layer1Lifestyle
    network: Layer1Network
    disclosures: Layer1Disclosures
