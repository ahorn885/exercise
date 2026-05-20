"""Layer 3A — Athlete State Evaluation (LLM node).

Substrate (`integration.py`, shipped 2026-05-20): five query-node accessors
that compose a `Layer3AIntegrationBundle` per
`Athlete_Data_Integration_Spec_v6.md` §10. Pure SQL — no LLM involvement.

Driver (`builder.py`, shipped 2026-05-20): `llm_layer3a_athlete_state` per
`Layer3_3A_Spec.md` §3 — consumes the bundle plus `Layer1Payload` +
`Layer2APayload` + an Anthropic SDK adapter, applies §6.2 confidence-floor
clamping post-LLM.

Cache wrapper (`cached_wrapper.py`, shipped 2026-05-20):
`llm_layer3a_athlete_state_cached` per spec §9 — reuses the generic
`CacheBackend` from `layer4/cache.py` with 3A-specific
`Layer3APayload`-serialization helpers.
"""

from layer3a.builder import (
    Layer3AEvidenceBasisWarning,
    Layer3AInputError,
    Layer3AOutputError,
    LLMCaller,
    build_record_athlete_state_tool,
    llm_layer3a_athlete_state,
)
from layer3a.cached_wrapper import (
    layer3a_athlete_state_key,
    llm_layer3a_athlete_state_cached,
)
from layer3a.integration import (
    assemble_layer3a_integration_bundle,
    q_layer3A_combined_load,
    q_layer3A_connected_providers,
    q_layer3A_recent_hrv,
    q_layer3A_recent_sleep,
    q_layer3A_recent_workouts,
)

__all__ = [
    "Layer3AEvidenceBasisWarning",
    "Layer3AInputError",
    "Layer3AOutputError",
    "LLMCaller",
    "assemble_layer3a_integration_bundle",
    "build_record_athlete_state_tool",
    "layer3a_athlete_state_key",
    "llm_layer3a_athlete_state",
    "llm_layer3a_athlete_state_cached",
    "q_layer3A_combined_load",
    "q_layer3A_connected_providers",
    "q_layer3A_recent_hrv",
    "q_layer3A_recent_sleep",
    "q_layer3A_recent_workouts",
]
