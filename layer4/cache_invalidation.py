"""Layer 4 cache invalidation policy per `Layer4_Spec.md` §9.3.

This module owns the routing: when upstream layer X re-derives for user Y,
which Layer 4 cache entries get evicted? It does NOT own storage — that's
`CacheBackend`'s job — it composes the eviction primitives the
`Layer4Cache` facade exposes.

§9.3 invalidation matrix (verbatim from spec, normalized to entry_point
tuples this module routes against):

| Upstream change           | Evicts (entry_points)                                                  |
|---------------------------|------------------------------------------------------------------------|
| Layer 1                   | all four entry points                                                  |
| Layer 2A                  | all four (single_session consumes 2A)                                  |
| Layer 2B                  | all EXCEPT single_session (D-63 doesn't consume 2B)                    |
| Layer 2C                  | all four (single_session consumes 2C-for-locale)                       |
| Layer 2D                  | all four (single_session consumes 2D)                                  |
| Layer 2E                  | all EXCEPT single_session (D-63 doesn't consume 2E)                    |
| Layer 3A                  | all four                                                                |
| Layer 3B                  | all EXCEPT single_session (single_session doesn't consume 3B)          |
| etl_version_set bump      | all four (etl_version_set is in every cache key)                       |
| midnight-UTC rollover     | race_week_brief only (output is days_to_event-anchored)                |

Model + tunable changes ARE in cache keys → natural miss; this module
doesn't route them (they invalidate themselves).

Public API:

- `evict_on_layer_change(cache, user_id, layer)` — the orchestrator's
  one-call hook when an upstream layer re-derives.
- `evict_on_midnight_rollover(cache, user_id=None)` — race-week-brief
  daily eviction.

The orchestrator is responsible for emitting the trigger events; this
module just routes them.
"""

from __future__ import annotations

from typing import Literal

from layer4.cache import EntryPoint, Layer4Cache


UpstreamLayer = Literal[
    "layer1",
    "layer2a",
    "layer2b",
    "layer2c",
    "layer2d",
    "layer2e",
    "layer3a",
    "layer3b",
    "etl_version_set",
]


_ALL_ENTRY_POINTS: tuple[EntryPoint, ...] = (
    "plan_create",
    "plan_refresh",
    "single_session_synthesize",
    "race_week_brief",
)


_NON_SINGLE_SESSION: tuple[EntryPoint, ...] = (
    "plan_create",
    "plan_refresh",
    "race_week_brief",
)


# §9.3 row → evicted entry_points. Layers not in this dict raise via
# evict_on_layer_change's validation (caller bug).
_EVICTION_POLICY: dict[str, tuple[EntryPoint, ...]] = {
    "layer1": _ALL_ENTRY_POINTS,
    "layer2a": _ALL_ENTRY_POINTS,
    "layer2b": _NON_SINGLE_SESSION,
    "layer2c": _ALL_ENTRY_POINTS,
    "layer2d": _ALL_ENTRY_POINTS,
    "layer2e": _NON_SINGLE_SESSION,
    "layer3a": _ALL_ENTRY_POINTS,
    "layer3b": _NON_SINGLE_SESSION,
    "etl_version_set": _ALL_ENTRY_POINTS,
}


def evict_on_layer_change(
    cache: Layer4Cache,
    user_id: int,
    layer: UpstreamLayer,
) -> int:
    """Evict Layer 4 cache rows that consume `layer` for `user_id`.

    Returns the count of evicted rows so callers can record observability
    events. Records the eviction against `cache.metrics` tagged by layer.
    """
    if layer not in _EVICTION_POLICY:
        raise ValueError(
            f"unknown upstream layer={layer!r}; expected one of "
            f"{sorted(_EVICTION_POLICY.keys())}"
        )
    entry_points = _EVICTION_POLICY[layer]

    # Optimization: when the policy covers every entry_point, skip the
    # filter (passing None to the backend deletes all user rows).
    filter_entry_points: tuple[EntryPoint, ...] | None
    if set(entry_points) == set(_ALL_ENTRY_POINTS):
        filter_entry_points = None
    else:
        filter_entry_points = entry_points

    return cache.invalidate_user(
        user_id,
        layer=layer,
        entry_points=filter_entry_points,
    )


def evict_on_midnight_rollover(
    cache: Layer4Cache,
    *,
    user_id: int | None = None,
) -> int:
    """Race-week-brief daily eviction per §9.3.

    The brief's `days_to_event` field shifts at midnight UTC; cached
    outputs become stale even if all upstream layers are unchanged. The
    orchestrator schedules this call once per day. When `user_id` is
    None, evicts every user's race_week_brief rows; otherwise scoped to
    the user.

    Returns the count of evicted rows.
    """
    return cache.invalidate_entry_point(
        "race_week_brief",
        layer="midnight_rollover",
        user_id=user_id,
    )


def policy_for_layer(layer: UpstreamLayer) -> tuple[EntryPoint, ...]:
    """Return the tuple of entry_points evicted when `layer` re-derives.

    Exposed for tests + orchestrator dashboards; the routing function
    above is the load-bearing call site.
    """
    if layer not in _EVICTION_POLICY:
        raise ValueError(f"unknown upstream layer={layer!r}")
    return _EVICTION_POLICY[layer]
