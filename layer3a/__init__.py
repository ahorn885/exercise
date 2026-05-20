"""Layer 3A — Athlete State Evaluation (LLM node).

Substrate (this module, shipped 2026-05-20): five query-node accessors that
compose a `Layer3AIntegrationBundle` per `Athlete_Data_Integration_Spec_v6.md`
§10. Pure SQL — no LLM involvement.

Driver (next session): `llm_layer3a_athlete_state` per `Layer3_3A_Spec.md`
§3 — consumes the bundle plus `Layer1Payload` + `Layer2APayload` + an
Anthropic SDK adapter.
"""

from layer3a.integration import (
    assemble_layer3a_integration_bundle,
    q_layer3A_combined_load,
    q_layer3A_connected_providers,
    q_layer3A_recent_hrv,
    q_layer3A_recent_sleep,
    q_layer3A_recent_workouts,
)

__all__ = [
    "assemble_layer3a_integration_bundle",
    "q_layer3A_combined_load",
    "q_layer3A_connected_providers",
    "q_layer3A_recent_hrv",
    "q_layer3A_recent_sleep",
    "q_layer3A_recent_workouts",
]
