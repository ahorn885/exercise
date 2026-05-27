"""Layer 4 — Plan generation payload schemas + upstream context.

See `aidstation-sources/Layer4_Spec.md` §7 for the output contract; this
package implements:

- `payload.py` — Layer 4's typed output schemas (Layer4Payload + PlanSession
  discriminated-union + IntensityTarget union + RacePlan / RaceWeekBrief).
- `hashing.py` — canonical-JSON encoder + 4 per-entry-point SHA-256
  cache-key helpers per §9.1.
- `context.py` — typed pydantic v2 mirrors of the upstream contracts Layer 4
  consumes (Layer 2A / 2B / 2C / 2D / 2E / 3A / 3B / DailyAvailabilityWindow
  / RaceEventPayload / PerDateRestriction). Includes AccommodationModality
  discriminated-union per the 2026-05-17 PR-C-followon amendment to
  Layer 2D §5.3.6 + Layer 2C §5.6 + the 2026-05-18 D-66 race-event data model
  per `Race_Events_D66_Design_v1.md` §4.

Domain-level training-load / ACWR / injury rules live in the §5.4 validator
harness (Step 3 PR-E of §14.3.4), not here.
"""

from layer4.context import (
    ACWREntry,
    ACWRStatus,
    AccommodationModality,
    Assessment,
    CaffeineRacedayPlan,
    CurrentState,
    DailyAvailabilityWindow,
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DataDensity,
    DietaryPatternFlag,
    DisciplineCoverage,
    DisciplineRisk,
    Evidence,
    ExerciseRisk,
    ExerciseSubstitutionModality,
    FrequencyReductionModality,
    GoalViability,
    HeatAcclimEventAdjustment,
    IntegratedSupplement,
    IntensityReductionModality,
    Layer2ACoachingFlag,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2BCoachingFlag,
    Layer2BDisciplineBlock,
    Layer2BPayload,
    Layer2BSummaryBlock,
    Layer2Bundle,
    Layer2CCoachingFlag,
    Layer2CPayload,
    Layer2DCoachingFlag,
    Layer2DHitlItem,
    Layer2DPayload,
    Layer2ECoachingFlag,
    Layer2EHitlItem,
    Layer2EPayload,
    Layer3AIntegrationBundle,
    Layer3APayload,
    Layer3BHITLItem,
    Layer3BPayload,
    Layer3Observation,
    LoadingTypeChangeModality,
    MacroTargets,
    MatchedBodyPart,
    ParsedIntent,
    PerDateRestriction,
    PeriodizationShape,
    PhaseLoadBands,
    RaceDayFueling,
    RaceDaySupplementSuggestion,
    RaceEventPayload,
    RaceFormat,
    RaceTerrainOutput,
    RouteLocale,
    RouteLocaleEquipment,
    RouteLocaleRole,
    RationaleMetadata,
    RecentTrajectory,
    ResolutionDetail,
    ResolvedExercise,
    SleepDepFuelingOverlay,
    SubstituteRecommendation,
    SupplementIntegrationPayload,
    TempoModificationModality,
    TerrainGap,
    TrainingGap,
    TrainingGapsSummary,
    TrajectoryWindow,
    UnresolvedFlag,
    VolumeReductionModality,
    WeightResult,
    WorkoutRecord,
    HRVRecord,
    SleepRecord,
    CombinedLoadReport,
    PolarCardioLoadCrossRef,
    ProviderStatus,
)
from layer4.cache import (
    CacheBackend,
    CacheEntry,
    CacheMetrics,
    InMemoryCacheBackend,
    LAYER4_ENTRY_POINTS,
    Layer4Cache,
    PER_ENTRY_PHASE_IDX_SENTINEL,
    VALID_ENTRY_POINTS,
)
from layer4.cache_invalidation import (
    evict_on_layer_change,
    evict_on_midnight_rollover,
    policy_for_layer,
)
from layer4.orchestrator import (
    OrchestrationError,
    orchestrate_plan_create,
    orchestrate_plan_refresh,
    orchestrate_race_week_brief,
    orchestrate_single_session_synthesize,
)
from layer4.cache_postgres import PostgresCacheBackend
from layer4.cached_wrappers import (
    llm_layer4_plan_create_cached,
    llm_layer4_plan_refresh_cached,
    llm_layer4_race_week_brief_cached,
    llm_layer4_single_session_synthesize_cached,
)
from layer4.hashing import (
    canonical_json,
    compute_accepted_output_hash,
    compute_block_cache_key,
    compute_layer2_bundle_canonical_hash,
    compute_layer2c_bundle_hash,
    compute_payload_hash,
    compute_phase_cache_key,
    compute_prior_plan_session_window_hash,
    plan_create_key,
    plan_refresh_key,
    race_week_brief_key,
    single_session_synthesize_key,
)
from layer4.errors import (
    Layer4Error,
    Layer4InputError,
    Layer4OutputError,
)
from layer4.per_phase import (
    build_record_phase_sessions_tool,
    synthesize_phase,
)
from layer4.phase_structure import (
    phase_for_date,
    phase_structure_from_3b,
    scope_spans_phase_boundary,
)
from layer4.plan_create import (
    llm_layer4_plan_create,
    synthesize_pattern_a_for_refresh,
)
from layer4.plan_refresh import (
    build_record_refresh_sessions_tool,
    llm_layer4_plan_refresh,
)
from layer4.seam_review import (
    build_record_seam_review_tool,
    review_seam,
)
from layer4.race_week_brief import (
    build_record_race_week_brief_tool,
    llm_layer4_race_week_brief,
)
from layer4.single_session import (
    SingleSessionRequest,
    build_record_single_session_tool,
    llm_layer4_single_session_synthesize,
)
from layer4.telemetry import (
    CallMetrics,
    MODEL_PRICING_USD_PER_M,
    TelemetryAggregator,
)
from layer4.validator import (
    ValidatorContext,
    validate_layer4_payload,
)
from layer4.payload import (
    CadenceTarget,
    CardioBlock,
    ClimbingGradeTarget,
    Contingency,
    FuelingStrategy,
    HRTarget,
    IntensityTarget,
    KitItem,
    Layer4Payload,
    Observation,
    PaceTarget,
    PacingStrategy,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    PowerTarget,
    RPETarget,
    RacePlan,
    RaceSegment,
    RaceWeekBrief,
    RuleFailure,
    SeamReview,
    SessionPhaseMetadata,
    ShapeOverride,
    StrengthExercise,
    StrokeRateTarget,
    SwimPaceTarget,
    SynthesisMetadata,
    TransitionSpec,
    ValidatorResult,
    VerticalRateTarget,
)

__all__ = [
    # Layer 4 output schemas (payload.py)
    "CadenceTarget",
    "CardioBlock",
    "ClimbingGradeTarget",
    "Contingency",
    "FuelingStrategy",
    "HRTarget",
    "IntensityTarget",
    "KitItem",
    "Layer4Payload",
    "Observation",
    "PaceTarget",
    "PacingStrategy",
    "PhaseSpec",
    "PhaseStructure",
    "PlanSession",
    "PowerTarget",
    "RPETarget",
    "RacePlan",
    "RaceSegment",
    "RaceWeekBrief",
    "RuleFailure",
    "SeamReview",
    "SessionPhaseMetadata",
    "ShapeOverride",
    "StrengthExercise",
    "StrokeRateTarget",
    "SwimPaceTarget",
    "SynthesisMetadata",
    "TransitionSpec",
    "ValidatorResult",
    "VerticalRateTarget",
    # Hashing helpers (hashing.py)
    "canonical_json",
    "compute_accepted_output_hash",
    "compute_block_cache_key",
    "compute_layer2_bundle_canonical_hash",
    "compute_layer2c_bundle_hash",
    "compute_payload_hash",
    "compute_phase_cache_key",
    "compute_prior_plan_session_window_hash",
    "plan_create_key",
    "plan_refresh_key",
    "race_week_brief_key",
    "single_session_synthesize_key",
    # Cache layer (cache.py + cache_postgres.py + cache_invalidation.py +
    # cached_wrappers.py) — Layer 4 Step 5 per §9.
    "CacheBackend",
    "CacheEntry",
    "CacheMetrics",
    "InMemoryCacheBackend",
    "Layer4Cache",
    "LAYER4_ENTRY_POINTS",
    "PER_ENTRY_PHASE_IDX_SENTINEL",
    "PostgresCacheBackend",
    "VALID_ENTRY_POINTS",
    "evict_on_layer_change",
    "evict_on_midnight_rollover",
    "llm_layer4_plan_create_cached",
    "llm_layer4_plan_refresh_cached",
    "llm_layer4_race_week_brief_cached",
    "llm_layer4_single_session_synthesize_cached",
    "policy_for_layer",
    # Orchestrator (orchestrator.py) — Phase 5.1 + Phase 5.2 vertical slices
    "OrchestrationError",
    "orchestrate_plan_create",
    "orchestrate_plan_refresh",
    "orchestrate_race_week_brief",
    "orchestrate_single_session_synthesize",
    # AccommodationModality discriminated union (context.py)
    "AccommodationModality",
    "ExerciseSubstitutionModality",
    "FrequencyReductionModality",
    "IntensityReductionModality",
    "LoadingTypeChangeModality",
    "TempoModificationModality",
    "VolumeReductionModality",
    # Layer 2A
    "Layer2ACoachingFlag",
    "Layer2ADiscipline",
    "Layer2APayload",
    "PhaseLoadBands",
    "RationaleMetadata",
    "TrainingGap",
    "TrainingGapsSummary",
    "UnresolvedFlag",
    "WeightResult",
    # Layer 2B
    "Layer2BCoachingFlag",
    "Layer2BDisciplineBlock",
    "Layer2BPayload",
    "Layer2BSummaryBlock",
    "Layer2Bundle",
    "RaceTerrainOutput",
    "TerrainGap",
    # Layer 2C
    "DisciplineCoverage",
    "Layer2CCoachingFlag",
    "Layer2CPayload",
    "ResolutionDetail",
    "ResolvedExercise",
    # Layer 2D
    "DisciplineRisk",
    "Evidence",
    "ExerciseRisk",
    "Layer2DCoachingFlag",
    "Layer2DHitlItem",
    "Layer2DPayload",
    "MatchedBodyPart",
    "SubstituteRecommendation",
    # Layer 2E
    "CaffeineRacedayPlan",
    "DailyNutritionBaseline",
    "DailyPhaseTargets",
    "DietaryPatternFlag",
    "HeatAcclimEventAdjustment",
    "IntegratedSupplement",
    "Layer2ECoachingFlag",
    "Layer2EHitlItem",
    "Layer2EPayload",
    "MacroTargets",
    "RaceDayFueling",
    "RaceDaySupplementSuggestion",
    "SleepDepFuelingOverlay",
    "SupplementIntegrationPayload",
    # Layer 3 (shared)
    "Layer3Observation",
    # Layer 3A
    "ACWREntry",
    "ACWRStatus",
    "Assessment",
    "CurrentState",
    "DataDensity",
    "Layer3APayload",
    "Layer3AIntegrationBundle",
    "WorkoutRecord",
    "SleepRecord",
    "HRVRecord",
    "CombinedLoadReport",
    "PolarCardioLoadCrossRef",
    "ProviderStatus",
    "RecentTrajectory",
    "TrajectoryWindow",
    # Layer 3B
    "GoalViability",
    "Layer3BHITLItem",
    "Layer3BPayload",
    "PeriodizationShape",
    # Onboarding / forward-pointers
    "DailyAvailabilityWindow",
    "PerDateRestriction",
    # Race events (D-66 design wave 2026-05-18)
    "RaceEventPayload",
    "RaceFormat",
    "RouteLocale",
    "RouteLocaleEquipment",
    "RouteLocaleRole",
    # Plan-refresh inputs (context.py)
    "ParsedIntent",
    # Validator harness (validator.py)
    "ValidatorContext",
    "validate_layer4_payload",
    # Typed errors (errors.py)
    "Layer4Error",
    "Layer4InputError",
    "Layer4OutputError",
    # Plan-refresh synthesizer (plan_refresh.py + plan_refresh_t1.py + plan_refresh_t2.py + plan_refresh_t3.py)
    "build_record_refresh_sessions_tool",
    "llm_layer4_plan_refresh",
    # Phase structure helper (phase_structure.py)
    "phase_for_date",
    "phase_structure_from_3b",
    "scope_spans_phase_boundary",
    # Pattern A — per-phase synthesizer + seam reviewer + plan_create driver (Step 4f)
    "build_record_phase_sessions_tool",
    "build_record_seam_review_tool",
    "llm_layer4_plan_create",
    "review_seam",
    "synthesize_pattern_a_for_refresh",
    "synthesize_phase",
    # Single-session synthesizer (single_session.py)
    "SingleSessionRequest",
    "build_record_single_session_tool",
    "llm_layer4_single_session_synthesize",
    # Race-week brief synthesizer (race_week_brief.py)
    "build_record_race_week_brief_tool",
    "llm_layer4_race_week_brief",
    # Per-call telemetry (telemetry.py) — Step 6c per §9.6 + §14.3.5.
    "CallMetrics",
    "MODEL_PRICING_USD_PER_M",
    "TelemetryAggregator",
]
