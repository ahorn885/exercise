"""Layer 3B — Goal-Timeline-Viability Evaluation (LLM node).

Driver (`builder.py`, shipped 2026-05-20): `llm_layer3b_goal_timeline_viability`
per `Layer3_3B_Spec.md` §3 — consumes `Layer1Payload` + `Layer3APayload` +
`Layer2APayload` + `RaceEventPayload | None` + the §H.2 deployed-shape-gap
kwargs (per D11 + L3B-P-2 forward-compatibility), applies §6.5 confidence-floor
clamping + §6.1 HITL auto-emit + §5.5 step 4 periodization-sanity loop
post-LLM.

Cache wrapper (`cached_wrapper.py`, shipped 2026-05-20):
`llm_layer3b_goal_timeline_viability_cached` per spec §9 — reuses the
generic `CacheBackend` from `layer4/cache.py` with 3B-specific
`Layer3BPayload`-serialization helpers + day-granular cache key on
`current_date: date`.

Pairs with `aidstation-sources/prompts/Layer3B_v1.md` (system prompt body
+ D1-D14 source decisions).
"""

from layer3b.builder import (
    Layer3BEvidenceBasisWarning,
    Layer3BInputError,
    Layer3BOutputError,
    LLMCaller,
    build_emit_layer3b_payload_tool,
    llm_layer3b_goal_timeline_viability,
)
from layer3b.cached_wrapper import (
    layer3b_goal_timeline_viability_key,
    llm_layer3b_goal_timeline_viability_cached,
)

__all__ = [
    "Layer3BEvidenceBasisWarning",
    "Layer3BInputError",
    "Layer3BOutputError",
    "LLMCaller",
    "build_emit_layer3b_payload_tool",
    "layer3b_goal_timeline_viability_key",
    "llm_layer3b_goal_timeline_viability",
    "llm_layer3b_goal_timeline_viability_cached",
]
