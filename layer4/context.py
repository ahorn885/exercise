"""Layer 4 upstream-context payload schemas — typed pydantic v2 mirrors of the
contracts Layer 4 consumes.

See:
- `aidstation-sources/Layer2A_Spec.md` §7 → `Layer2APayload`
- `aidstation-sources/Layer2B_Spec.md` §7 → `Layer2BPayload`
- `aidstation-sources/Layer2C_Spec.md` §7 (+ §5.6 amendment) → `Layer2CPayload`
- `aidstation-sources/Layer2D_Spec.md` §7 (+ §5.3.6 amendment) → `Layer2DPayload`
  + `AccommodationModality` discriminated union (6 variants).
- `aidstation-sources/Layer2E_Spec.md` §7 → `Layer2EPayload`
- `aidstation-sources/Layer3_3A_Spec.md` §7 → `Layer3APayload`
- `aidstation-sources/Layer3_3B_Spec.md` §7 → `Layer3BPayload`
- `aidstation-sources/Athlete_Onboarding_Data_Spec_v5.md` §G.1 → `DailyAvailabilityWindow`
- `Layer4_Spec.md` §5.4 forward-pointers — `RaceEventStub` (pending D-66),
  `PerDateRestriction` (pending D-67; always-empty in v1).

All models reject unknown keys (`extra='forbid'`) so untrusted upstream output
that drifts from the schema raises at construction. Domain-level rules
(volume bands, ACWR, injury exclusions, per-modality compliance, etc.) live
in the Layer 4 §5.4 validator harness, not here.
"""

from __future__ import annotations

from datetime import datetime
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
    terrain_name: str
    pct_of_race: float = Field(ge=0.0, le=1.0)
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
    pct_of_race_uncovered: float = Field(ge=0.0, le=1.0)
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


# ─── Layer 2E — nutrition baseline (Layer2E_Spec.md §7) ──────────────────────


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

    @model_validator(mode="after")
    def _check_hitl_unique_labels(self) -> "Layer3BPayload":
        # §7 schema rule: hitl_surface items have unique item_label.
        labels = [h.item_label for h in self.hitl_surface]
        if len(labels) != len(set(labels)):
            raise ValueError("hitl_surface item_labels must be unique")
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


# ─── RaceEventStub (minimal v1; full schema pending D-66) ────────────────────


class RaceEventStub(_Base):
    event_name: str
    event_date: datetime
    race_format: Literal[
        "single_day", "expedition_ar", "stage_race", "multi_day_ultra"
    ]
    event_locale_id: str | None = None


# ─── PerDateRestriction (placeholder pending D-67; always-empty in v1) ───────


class PerDateRestriction(_Base):
    date: datetime
    locale_lock: str | None = None
    discipline_exclusions: list[str] = Field(default_factory=list)
    indoor_only: bool = False
    max_total_minutes: int | None = Field(default=None, ge=0)
