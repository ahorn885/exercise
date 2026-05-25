"""Best-Fit Modality resolver — public surface.

Pure-Python deterministic resolver. Given the planner inputs
(`cluster_locale_inputs` carrying per-locale terrain + equipment,
`included_discipline_ids`, `skill_toggle_states`), returns a menu of
viable training modalities ranked by preference per
`(discipline_id, locale_id)` pair, with a top-pick + rationale-hint
that Layer 4 consumes.

Design canonical doc: `aidstation-sources/BestFitModality_Spec_v1.md`.
Architectural placement ratified at AskUserQuestion gate per Trigger
#5 — A2 algorithmic Python resolver (mirrors gear-toggle /
skill-toggle Python-rule precedent).

Output schemas live in `layer4.context` alongside `Layer2CPayload`
(matches the existing payload-contract convention); the resolver +
vocab + input dataclass + exception live here.
"""

from layer2_modality.resolver import (
    ClusterLocaleInput,
    Layer2ModalityInputError,
    ModalityOptionDef,
    resolve_best_fit_modality,
)
from layer2_modality.substitution import resolve_training_substitution

__all__ = [
    "ClusterLocaleInput",
    "Layer2ModalityInputError",
    "ModalityOptionDef",
    "resolve_best_fit_modality",
    "resolve_training_substitution",
]
