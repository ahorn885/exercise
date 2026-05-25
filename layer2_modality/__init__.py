"""Best-Fit training-substitution resolver — public surface.

Pure-Python deterministic resolver. Given the Layer 2B per-discipline
terrain blocks (`terrain_by_discipline`) + the athlete's owned crafts,
`resolve_training_substitution` produces a per-discipline
`TrainingSubstitutionPayload` — closest trainable terrain emphasis
(ranked `pct × fidelity`), untrainable-terrain gaps, and the craft
candidate set Layer 4 picks from.

Design canonical doc: `aidstation-sources/BestFitModality_Spec_v4.md`.
Output schemas live in `layer4.context` alongside `Layer2CPayload`
(matches the existing payload-contract convention).
"""

from layer2_modality.substitution import (
    Layer2ModalityInputError,
    resolve_training_substitution,
)

__all__ = [
    "Layer2ModalityInputError",
    "resolve_training_substitution",
]
