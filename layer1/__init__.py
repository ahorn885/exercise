"""Layer 1 — athlete profile aggregation.

Reads the D-51 §3 storage shipped in D-73 Phase 1.2A/B/C (athlete_profile +
7 per-discipline 1:1 sub-tables + 8 multi-row tables + strength_benchmarks
+ daily_availability_windows) plus existing companion tables (body_metrics,
wellness_self_report, race_events, injury_log, disclosure_acknowledgments)
and assembles a typed `Layer1Payload` per `Layer1_Spec.md` §3.

See:
- `aidstation-sources/Layer1_Spec.md` — full spec (purpose, signature,
  validation, algorithm, payload schema, edge cases, test scenarios).
- `layer4/context.py` — `Layer1Payload` + section sub-models.
- `aidstation-sources/Layer1_D51_Design_v1.md` §3 — storage design wave.

Per `Upstream_Implementation_Plan_v1.md` §6 item 3 + §8 mitigation, Layer 4
entry points keep `layer1_payload: dict[str, Any]` for v1; the orchestrator
(Phase 5) calls `payload.model_dump()` before threading. Top-level
convenience fields on `Layer1Payload` mirror the keys Layer 4 currently
reads via `.get(...)` so the dict round-trip is transparent.
"""

from layer1.builder import build_layer1_payload

__all__ = ["build_layer1_payload"]
