"""Layer 4 payload schemas per `aidstation-sources/Layer4_Spec.md` §7.

All §7.12 cross-field invariants are enforced at construction time via
`@model_validator(mode='after')`. Models reject unknown keys (`extra='forbid'`)
so untrusted LLM tool-use output that drifts from the schema raises with a
path-precise error rather than silently dropping fields.

Domain-level training-load rules (volume bands, ACWR forward projection,
intensity distribution drift, injury exclusions, two-hards-with-recovery,
etc.) are the §5.4 deterministic validator harness — out of scope here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ─── §7.3 IntensityTarget union (also §7.14 RaceSegment.pacing_target) ─────
#
# Closed set of 9 typed target shapes — v1 amendment per spec §7.3 narrowed
# "free-shape per-discipline" to "free across this enumerated set; tight
# within each shape." Smart-union dispatch on key+type match; garbage
# rejects against all branches.
#
# Convention: always range-based (low + high). Fixed prescriptions use
# low == high. Range fields are bounds-checked for sane physical limits;
# domain-level rules (e.g., "Z2 HR is 60-80% of athlete's HR_max") live
# in the §5.4 validator harness, not here.


_PACE_PATTERN = r"^\d{1,2}:[0-5]\d$"


class HRTarget(_Base):
    hr_bpm_low: int = Field(ge=30, le=230)
    hr_bpm_high: int = Field(ge=30, le=230)

    @model_validator(mode="after")
    def _check_range(self) -> "HRTarget":
        if self.hr_bpm_low > self.hr_bpm_high:
            raise ValueError("hr_bpm_low must be <= hr_bpm_high")
        return self


class PowerTarget(_Base):
    power_w_low: int = Field(ge=0, le=2000)
    power_w_high: int = Field(ge=0, le=2000)

    @model_validator(mode="after")
    def _check_range(self) -> "PowerTarget":
        if self.power_w_low > self.power_w_high:
            raise ValueError("power_w_low must be <= power_w_high")
        return self


class PaceTarget(_Base):
    pace_per_km_low: str = Field(pattern=_PACE_PATTERN)
    pace_per_km_high: str = Field(pattern=_PACE_PATTERN)


class SwimPaceTarget(_Base):
    pace_per_100m_low: str = Field(pattern=_PACE_PATTERN)
    pace_per_100m_high: str = Field(pattern=_PACE_PATTERN)


class RPETarget(_Base):
    rpe_low: int = Field(ge=1, le=10)
    rpe_high: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def _check_range(self) -> "RPETarget":
        if self.rpe_low > self.rpe_high:
            raise ValueError("rpe_low must be <= rpe_high")
        return self


class VerticalRateTarget(_Base):
    vert_m_per_hr_low: int = Field(ge=0, le=3000)
    vert_m_per_hr_high: int = Field(ge=0, le=3000)

    @model_validator(mode="after")
    def _check_range(self) -> "VerticalRateTarget":
        if self.vert_m_per_hr_low > self.vert_m_per_hr_high:
            raise ValueError("vert_m_per_hr_low must be <= vert_m_per_hr_high")
        return self


class StrokeRateTarget(_Base):
    strokes_per_min_low: int = Field(ge=0, le=200)
    strokes_per_min_high: int = Field(ge=0, le=200)

    @model_validator(mode="after")
    def _check_range(self) -> "StrokeRateTarget":
        if self.strokes_per_min_low > self.strokes_per_min_high:
            raise ValueError("strokes_per_min_low must be <= strokes_per_min_high")
        return self


class CadenceTarget(_Base):
    rpm_low: int = Field(ge=0, le=250)
    rpm_high: int = Field(ge=0, le=250)

    @model_validator(mode="after")
    def _check_range(self) -> "CadenceTarget":
        if self.rpm_low > self.rpm_high:
            raise ValueError("rpm_low must be <= rpm_high")
        return self


class ClimbingGradeTarget(_Base):
    grade_system: Literal["yosemite_decimal", "french_sport", "uiaa"]
    grade_min: str
    grade_max: str


IntensityTarget = Annotated[
    Union[
        HRTarget,
        PowerTarget,
        PaceTarget,
        SwimPaceTarget,
        RPETarget,
        VerticalRateTarget,
        StrokeRateTarget,
        CadenceTarget,
        ClimbingGradeTarget,
    ],
    Field(union_mode="smart"),
]


# ─── §7.3 CardioBlock ──────────────────────────────────────────────────────


class CardioBlock(_Base):
    block_kind: Literal["warmup", "main_set", "cooldown", "interval_set", "transition"]
    duration_min: int
    intensity_zone: Literal["Z1", "Z2", "Z3", "Z4", "Z5", "mixed"]
    intensity_target: IntensityTarget
    instructions: str
    repetitions: int | None = None
    rest_between_min: int | None = None
    rest_intensity_zone: Literal["Z1", "Z2"] | None = None

    @model_validator(mode="after")
    def _check_interval_fields(self) -> "CardioBlock":
        is_interval = self.block_kind == "interval_set"
        interval_fields_set = (
            self.repetitions is not None
            or self.rest_between_min is not None
            or self.rest_intensity_zone is not None
        )
        if is_interval:
            if (
                self.repetitions is None
                or self.rest_between_min is None
                or self.rest_intensity_zone is None
            ):
                raise ValueError(
                    "block_kind=='interval_set' requires repetitions, rest_between_min, "
                    "and rest_intensity_zone all non-None"
                )
        elif interval_fields_set:
            raise ValueError(
                f"block_kind=='{self.block_kind}' requires repetitions is None, "
                "rest_between_min is None, rest_intensity_zone is None"
            )
        return self


# ─── §7.4 StrengthExercise ─────────────────────────────────────────────────


class StrengthExercise(_Base):
    exercise_id: str
    exercise_name: str
    resolution_tier: Literal[1, 2, 3]
    substitute_text: str | None = None
    proxy_origin_id: str | None = None
    sets: int
    reps_per_set: int | str
    load_prescription: str
    rest_between_sets_sec: int
    tempo: str | None = None
    instructions: str
    coaching_flags: list[str]

    @model_validator(mode="after")
    def _check_resolution_tier(self) -> "StrengthExercise":
        if self.resolution_tier == 1:
            if self.substitute_text is not None or self.proxy_origin_id is not None:
                raise ValueError(
                    "resolution_tier==1 requires substitute_text is None and proxy_origin_id is None"
                )
        elif self.resolution_tier == 2:
            if self.substitute_text is None:
                raise ValueError("resolution_tier==2 requires substitute_text non-None")
        elif self.resolution_tier == 3:
            if self.proxy_origin_id is None:
                raise ValueError("resolution_tier==3 requires proxy_origin_id non-None")
        return self


# ─── §7.5 SessionPhaseMetadata ─────────────────────────────────────────────


class SessionPhaseMetadata(_Base):
    phase_name: Literal["Base", "Build", "Peak", "Taper"]
    week_in_phase: int
    total_weeks_in_phase: int
    intended_volume_band: tuple[float, float]
    intended_intensity_distribution: dict[str, float]


# ─── §7.2 PlanSession (discriminated by `kind` via §7.12 invariants) ───────


class PlanSession(_Base):
    session_id: str
    plan_version_id: int
    date: date
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    session_index_in_day: int = Field(ge=0, le=1)
    time_of_day: Literal["morning", "afternoon", "evening", "unspecified"]
    kind: Literal["cardio", "strength", "rest"]

    discipline_id: str | None = None
    discipline_name: str | None = None
    locale_id: str | None = None
    locale_name: str | None = None
    duration_min: int
    intensity_summary: Literal["easy", "moderate", "hard", "mixed", "rest"]

    cardio_blocks: list[CardioBlock] | None = None
    strength_exercises: list[StrengthExercise] | None = None
    rest_reason: (
        Literal[
            "planned_recovery",
            "overreach_protection",
            "travel_day",
            "athlete_unavailable",
            "taper_drop",
        ]
        | None
    ) = None

    phase_metadata: SessionPhaseMetadata | None = None

    session_notes: str
    coaching_intent: str
    coaching_flags: list[str]

    is_ad_hoc: bool = False
    ad_hoc_request_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_kind_invariants(self) -> "PlanSession":
        if self.kind == "cardio":
            if not self.cardio_blocks:
                raise ValueError("kind=='cardio' requires cardio_blocks non-None and non-empty")
            if self.strength_exercises is not None:
                raise ValueError("kind=='cardio' requires strength_exercises is None")
            if self.rest_reason is not None:
                raise ValueError("kind=='cardio' requires rest_reason is None")
        elif self.kind == "strength":
            if not self.strength_exercises:
                raise ValueError(
                    "kind=='strength' requires strength_exercises non-None and non-empty"
                )
            if self.cardio_blocks is not None:
                raise ValueError("kind=='strength' requires cardio_blocks is None")
            if self.rest_reason is not None:
                raise ValueError("kind=='strength' requires rest_reason is None")
        elif self.kind == "rest":
            if self.cardio_blocks is not None:
                raise ValueError("kind=='rest' requires cardio_blocks is None")
            if self.strength_exercises is not None:
                raise ValueError("kind=='rest' requires strength_exercises is None")
            if self.rest_reason is None:
                raise ValueError("kind=='rest' requires rest_reason non-None")
            if self.duration_min != 0:
                raise ValueError("kind=='rest' requires duration_min == 0")
            if self.discipline_id is not None:
                raise ValueError("kind=='rest' requires discipline_id is None")
            if self.locale_id is not None:
                raise ValueError("kind=='rest' requires locale_id is None")
        return self

    @model_validator(mode="after")
    def _check_ad_hoc(self) -> "PlanSession":
        if self.is_ad_hoc and self.ad_hoc_request_payload is None:
            raise ValueError("is_ad_hoc==True requires ad_hoc_request_payload non-None")
        return self


# ─── §7.6 PhaseStructure / PhaseSpec / SynthesisMetadata ───────────────────


class SynthesisMetadata(_Base):
    model: str
    temperature: float
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries_used: int
    cap_hit: bool


class PhaseSpec(_Base):
    phase_name: Literal["Base", "Build", "Peak", "Taper"]
    start_date: date
    end_date: date
    weeks: int
    intended_volume_band: tuple[float, float]
    intended_intensity_distribution: dict[str, float]
    synthesis_metadata: SynthesisMetadata


class PhaseStructure(_Base):
    phases: list[PhaseSpec]
    total_weeks: int
    derived_from: Literal[
        "3b_standard", "3b_compressed", "3b_extended", "3b_custom", "layer4_override"
    ]


# ─── §7.7 SeamReview ───────────────────────────────────────────────────────


class SeamReview(_Base):
    seam_index: int
    prior_phase_name: Literal["Base", "Build", "Peak"]
    next_phase_name: Literal["Build", "Peak", "Taper"]
    reviewer_verdict: Literal["approved", "flagged_minor", "flagged_major", "patched"]
    seam_issues: list[str]
    proposed_patch_direction: (
        Literal["re_prompt_prior", "re_prompt_next", "accept_with_observation"] | None
    ) = None
    triggered_resynthesis: bool
    re_prompted_phase_name: Literal["Base", "Build", "Peak", "Taper"] | None = None
    reviewer_model: str


# ─── §7.8 ShapeOverride ────────────────────────────────────────────────────


class ShapeOverride(_Base):
    original_shape_mode: str
    original_start_phase: str
    overridden_mode: str
    overridden_start_phase: str
    rationale_text: str
    evidence_basis: list[str]


# ─── §7.9 ValidatorResult / RuleFailure ────────────────────────────────────


class RuleFailure(_Base):
    rule_name: str
    phase_name: str | None = None
    severity: Literal["blocker", "warning"]
    detail: str
    affected_session_ids: list[str]


class ValidatorResult(_Base):
    pass_index: int
    accepted: bool
    rule_failures: list[RuleFailure]
    retried_phase_names: list[str]


# ─── §7.10 Observation ─────────────────────────────────────────────────────


class Observation(_Base):
    category: Literal[
        "warning",
        "opportunity",
        "data_gap",
        "data_hygiene",
        "shape_override",
        "best_effort_plan",
        "seam_unresolved",
        "intensity_modulated",
        "sport_unavailable_at_locale",
        "off_plan_day_note",
    ]
    text: str = Field(max_length=240)
    evidence_basis: list[str]
    elevates_to_hitl: bool


# ─── §7.13 RaceWeekBrief / KitItem ─────────────────────────────────────────


class KitItem(_Base):
    item: str
    purpose: str
    optional: bool
    layer0_canonical: bool = False


class RaceWeekBrief(_Base):
    days_to_event: int
    event_name: str
    event_date: date
    event_locale: str
    race_format: Literal["single_day", "continuous_multi_day", "stage_race"]
    goal_outcome: str

    pre_race_logistics: str
    drop_bag_strategy: str | None = None
    course_familiarization_notes: str | None = None

    kit_manifest: list[KitItem]
    kit_check_dates: list[date]

    race_day_fueling_plan: str
    pre_race_meal_strategy: str

    pacing_strategy_summary: str
    contingencies: list[str]
    mental_prep_cues: list[str]


# ─── §7.14 RacePlan + sub-types ────────────────────────────────────────────


class RaceSegment(_Base):
    segment_id: str
    segment_index: int
    sport: str
    estimated_start_offset_hr: float
    estimated_duration_min: int
    distance_km: float | None = None
    elevation_gain_m: float | None = None
    terrain_notes: str
    pacing_target: IntensityTarget
    coaching_notes: str


class TransitionSpec(_Base):
    from_segment_id: str
    to_segment_id: str
    estimated_duration_min: int
    gear_changes: list[str]
    is_fueling_window: bool
    notes: str


class PacingStrategy(_Base):
    overall_intensity_target: str
    night_section_adjustment: str | None = None
    pacing_milestones: list[str]
    rationale_text: str


class FuelingStrategy(_Base):
    cho_g_per_hr_low: int
    cho_g_per_hr_high: int
    sodium_mg_per_hr: int
    fluid_ml_per_hr: int
    caffeine_strategy: str
    night_section_strategy: str | None = None
    rationale_text: str


class Contingency(_Base):
    trigger: str
    action_plan: str
    threshold_to_invoke: str


class RacePlan(_Base):
    race_name: str
    race_start_datetime: datetime
    race_end_estimate_datetime: datetime
    race_format: Literal["continuous_multi_day", "stage_race"]
    locales: list[str]
    segments: list[RaceSegment]
    transitions: list[TransitionSpec]
    pacing_strategy: PacingStrategy
    fueling_strategy: FuelingStrategy
    contingencies: list[Contingency]

    @model_validator(mode="after")
    def _check_segments_chronological(self) -> "RacePlan":
        for i in range(1, len(self.segments)):
            if self.segments[i].segment_index <= self.segments[i - 1].segment_index:
                raise ValueError(
                    "RacePlan.segments must be chronologically ordered by segment_index"
                )
        return self


# ─── §7.1 Layer4Payload (top-level) ────────────────────────────────────────


class Layer4Payload(_Base):
    user_id: int
    mode: Literal[
        "plan_create", "plan_refresh", "single_session_synthesize", "race_week_brief"
    ]
    plan_version_id: int
    scope_start_date: date
    scope_end_date: date
    model_synthesizer: str
    model_seam_reviewer: str | None = None
    temperature: float
    pattern: Literal["A", "B"]
    latency_ms_total: int
    input_tokens_total: int
    output_tokens_total: int
    llm_call_count: int
    etl_version_set: dict[str, str]

    sessions: list[PlanSession]

    phase_structure: PhaseStructure | None = None
    seam_reviews: list[SeamReview] | None = None

    shape_override: ShapeOverride | None = None

    validator_results: list[ValidatorResult]

    notable_observations: list[Observation]

    suggestion_id: int | None = None

    race_week_brief: RaceWeekBrief | None = None
    race_plan: RacePlan | None = None

    @model_validator(mode="after")
    def _check_mode_invariants(self) -> "Layer4Payload":
        if self.mode == "plan_create":
            if self.phase_structure is None or self.seam_reviews is None:
                raise ValueError(
                    "mode=='plan_create' requires phase_structure non-None + seam_reviews non-None"
                )
        elif self.mode == "plan_refresh":
            if self.pattern == "A":
                if self.phase_structure is None or self.seam_reviews is None:
                    raise ValueError(
                        "mode=='plan_refresh' + pattern=='A' requires "
                        "phase_structure non-None + seam_reviews non-None"
                    )
            else:
                if self.phase_structure is not None or self.seam_reviews is not None:
                    raise ValueError(
                        "mode=='plan_refresh' + pattern=='B' requires "
                        "phase_structure is None + seam_reviews is None"
                    )
        elif self.mode == "single_session_synthesize":
            if self.pattern != "B":
                raise ValueError("mode=='single_session_synthesize' requires pattern=='B'")
            if len(self.sessions) != 1:
                raise ValueError("mode=='single_session_synthesize' requires len(sessions)==1")
            if not self.sessions[0].is_ad_hoc:
                raise ValueError(
                    "mode=='single_session_synthesize' requires sessions[0].is_ad_hoc==True"
                )
            if self.phase_structure is not None or self.seam_reviews is not None:
                raise ValueError(
                    "mode=='single_session_synthesize' requires "
                    "phase_structure is None + seam_reviews is None"
                )
            if self.suggestion_id is None:
                raise ValueError(
                    "mode=='single_session_synthesize' requires suggestion_id non-None"
                )
        elif self.mode == "race_week_brief":
            if self.pattern != "B":
                raise ValueError("mode=='race_week_brief' requires pattern=='B'")
            if self.race_week_brief is None:
                raise ValueError("mode=='race_week_brief' requires race_week_brief non-None")
            if self.phase_structure is not None or self.seam_reviews is not None:
                raise ValueError(
                    "mode=='race_week_brief' requires phase_structure is None + seam_reviews is None"
                )
            if self.race_week_brief.race_format == "single_day":
                if self.race_plan is not None:
                    raise ValueError(
                        "race_week_brief.race_format=='single_day' requires race_plan is None"
                    )
            else:
                if self.race_plan is None:
                    raise ValueError(
                        "race_week_brief.race_format != 'single_day' requires race_plan non-None"
                    )
        return self

    @model_validator(mode="after")
    def _check_two_per_day(self) -> "Layer4Payload":
        by_date: dict[date, list[PlanSession]] = defaultdict(list)
        for s in self.sessions:
            by_date[s.date].append(s)
        for d, ss in by_date.items():
            if len(ss) > 2:
                raise ValueError(f"{d}: max 2 sessions per day (got {len(ss)})")
            if len(ss) == 2:
                if all(s.kind == "strength" for s in ss):
                    raise ValueError(f"{d}: no strength+strength on same day")
                if all(s.intensity_summary == "hard" for s in ss):
                    raise ValueError(f"{d}: no two hard sessions on same day")
                if not any(s.kind == "cardio" for s in ss):
                    raise ValueError(
                        f"{d}: at least one of two sessions must have kind=='cardio'"
                    )
                indices = sorted(s.session_index_in_day for s in ss)
                if indices != [0, 1]:
                    raise ValueError(
                        f"{d}: two sessions same day must have session_index_in_day 0 and 1"
                    )
        return self

    @model_validator(mode="after")
    def _check_validator_results(self) -> "Layer4Payload":
        if not self.validator_results:
            raise ValueError("validator_results must be non-empty")
        if not self.validator_results[-1].accepted:
            raise ValueError("validator_results[-1].accepted must be True")
        return self

    @model_validator(mode="after")
    def _check_shape_override_observation(self) -> "Layer4Payload":
        if self.shape_override is not None:
            if not any(o.category == "shape_override" for o in self.notable_observations):
                raise ValueError(
                    "shape_override non-None requires notable_observations with category=='shape_override'"
                )
        return self

    @model_validator(mode="after")
    def _check_phase_metadata_per_mode(self) -> "Layer4Payload":
        # §7.12: phase_metadata non-None when producer was plan_create or Pattern-A plan_refresh;
        # None for Pattern-B plan_refresh + single_session_synthesize; race_week_brief preserves
        # prior-plan phase_metadata verbatim (so non-None in v1 since v1 only modifies existing
        # Pattern-A-produced Taper sessions per the C2 amendment).
        if self.mode == "plan_create" or (self.mode == "plan_refresh" and self.pattern == "A"):
            for s in self.sessions:
                if s.phase_metadata is None:
                    raise ValueError(
                        f"session {s.session_id}: mode=='{self.mode}' pattern=='{self.pattern}' "
                        "requires phase_metadata non-None"
                    )
        elif self.mode == "plan_refresh" and self.pattern == "B":
            for s in self.sessions:
                if s.phase_metadata is not None:
                    raise ValueError(
                        f"session {s.session_id}: mode=='plan_refresh' pattern=='B' "
                        "requires phase_metadata is None"
                    )
        elif self.mode == "single_session_synthesize":
            for s in self.sessions:
                if s.phase_metadata is not None:
                    raise ValueError(
                        f"session {s.session_id}: mode=='single_session_synthesize' "
                        "requires phase_metadata is None"
                    )
        elif self.mode == "race_week_brief":
            # §7.12 C2 amendment + v1 strict invariant: race_week_brief only modifies
            # existing Pattern-A-produced Taper sessions which carry phase_metadata
            # verbatim; all sessions in race_week_brief output must have it non-None.
            for s in self.sessions:
                if s.phase_metadata is None:
                    raise ValueError(
                        f"session {s.session_id}: mode=='race_week_brief' requires "
                        "phase_metadata non-None (v1: override-pass-through from prior plan)"
                    )
        return self
