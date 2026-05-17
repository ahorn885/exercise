"""Layer 4 — Plan generation payload schemas.

See `aidstation-sources/Layer4_Spec.md` §7 for the contract; this package
implements the typed schemas + §7.12 cross-field invariants. Domain-level
training-load / ACWR / injury rules live in the §5.4 validator harness
(Step 3 of §14.3.4), not here.
"""

from layer4.payload import (
    CardioBlock,
    Contingency,
    FuelingStrategy,
    KitItem,
    Layer4Payload,
    Observation,
    PacingStrategy,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    RacePlan,
    RaceSegment,
    RaceWeekBrief,
    RuleFailure,
    SeamReview,
    SessionPhaseMetadata,
    ShapeOverride,
    StrengthExercise,
    SynthesisMetadata,
    TransitionSpec,
    ValidatorResult,
)

__all__ = [
    "CardioBlock",
    "Contingency",
    "FuelingStrategy",
    "KitItem",
    "Layer4Payload",
    "Observation",
    "PacingStrategy",
    "PhaseSpec",
    "PhaseStructure",
    "PlanSession",
    "RacePlan",
    "RaceSegment",
    "RaceWeekBrief",
    "RuleFailure",
    "SeamReview",
    "SessionPhaseMetadata",
    "ShapeOverride",
    "StrengthExercise",
    "SynthesisMetadata",
    "TransitionSpec",
    "ValidatorResult",
]
