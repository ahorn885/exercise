"""Layer 3D — HITL aggregation + gate (query/orchestration node, no LLM).

Per `aidstation-sources/specs/Layer3D_Spec.md`. Sits between Layer 3B and Layer
4: aggregates the human-review items the upstream nodes (2A/2D/2E/3B) already
emit into one typed `GateItem` list, applies the athlete's prior resolutions,
and computes a `gate_status` that gates Layer 4 synthesis.

Slice 1 (shipped): the deterministic aggregation + resolution/status rules +
gate-status computation (`gate.py`). The §5.2/§5.3 feasibility detectors and the
3C source are deferred to later slices (see spec §13); the aggregator is written
so they drop in with no contract change.
"""

from layer3d.gate import (
    GateItem,
    GateResolution,
    GateStatus,
    Layer3DGate,
    Layer3DGateBlocked,
    Layer3DGateError,
    compute_gate_status,
    evaluate_layer3d_gate,
    make_item_key,
    map_2a_items,
    map_2d_items,
    map_2e_items,
    map_3b_items,
    resolved_status,
)

__all__ = [
    "GateItem",
    "GateResolution",
    "GateStatus",
    "Layer3DGate",
    "Layer3DGateBlocked",
    "Layer3DGateError",
    "compute_gate_status",
    "evaluate_layer3d_gate",
    "make_item_key",
    "map_2a_items",
    "map_2d_items",
    "map_2e_items",
    "map_3b_items",
    "resolved_status",
]
