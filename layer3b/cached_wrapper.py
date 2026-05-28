"""Layer 3B cache adapter per `Layer3_3B_Spec.md` §9.

Single per-entry-point `_cached()` wrapper around
`llm_layer3b_goal_timeline_viability`. Reuses `layer4.cache.CacheBackend`
(generic JSON storage) + `layer4.hashing` primitives
(`compute_payload_hash`, `canonical_json`) for canonical cache-key
derivation.

Cache key per spec §9.1:

    sha256(
        user_id ||
        compute_payload_hash(layer1_payload) ||
        compute_payload_hash(layer3a_payload) ||
        compute_payload_hash(layer2a_payload) ||
        (race_event_payload.race_event_id if event-mode else "no-event") ||
        current_date.isoformat() ||
        (non_event_goal_type or "") ||
        canonical_json(etl_version_set) ||
        canonical_json(spec_§H.2_kwargs_dict) ||  # forward-compat hash slot
        model ||
        str(temperature) ||
        str(max_tokens) ||
        str(extended_thinking_budget)
    )

`current_date` is already day-granular (it's a `date`, not `datetime`).
Same-day calls with identical inputs hit the same cache entry. Mid-day
data changes invalidate via the 3A/2A payload hash change per spec §9.2.

Hit/miss flow mirrors `layer3a.cached_wrapper` — `Layer3BPayload` is
fully self-contained (no `plan_version_id` / `suggestion_id` rebinding),
so a hit just round-trips through `model_dump_json` /
`model_validate_json`.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from layer3b.builder import (
    _DEFAULT_MAX_TOKENS,
    _DEFAULT_MODEL,
    _DEFAULT_TEMPERATURE,
    _DEFAULT_THINKING_BUDGET,
    LLMCaller,
    llm_layer3b_goal_timeline_viability,
)
from layer4.cache import CacheBackend, PER_ENTRY_PHASE_IDX_SENTINEL
from layer4.context import (
    Layer1Payload,
    Layer2APayload,
    Layer3APayload,
    Layer3BPayload,
    RaceEventPayload,
)
from layer4.hashing import canonical_json, compute_payload_hash


_LAYER3B_ENTRY_POINT_LABEL = "llm_layer3b_goal_timeline_viability"

# Legacy / uncaptured-row default (§H.2 / D11). 3B's event-mode
# `_validate_inputs` hard-requires a `goal_outcome` (Finish / Compete mid-pack
# / Podium). The capture form + `race_events.goal_outcome` column shipped
# 2026-05-26, and the orchestrator now threads the stored value through — but
# rows created before that (or saved without a goal pick) carry NULL. Those
# event-mode callers fall back to the conservative "Finish" tier so generation
# proceeds (mirrors the no-event-mode back-fill from layer1.event_goal below).
_DEFAULT_EVENT_GOAL_OUTCOME = "Finish"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def layer3b_goal_timeline_viability_key(
    *,
    user_id: int,
    layer1_hash: str,
    layer3a_hash: str,
    layer2a_hash: str,
    race_event_id: int | None,
    current_date: date,
    non_event_goal_type: str | None,
    etl_version_set: dict[str, str],
    section_h2_kwargs: dict[str, Any] | None,
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> str:
    """Per `Layer3_3B_Spec.md` §9.1 — cache key for
    `llm_layer3b_goal_timeline_viability`.

    `current_date` is already day-granular (date, not datetime); intra-day
    calls with identical inputs collide on the same key.

    `race_event_id` distinguishes event-mode (the race_events.id PK)
    from no-event-mode (None → "no-event" string literal). Switching
    target event flips the key.

    `section_h2_kwargs` is a forward-compatibility hash slot per D11 —
    a dict of the v1 §H.2 deployed-shape-gap kwargs (goal_outcome,
    first_time_at_distance, previous_attempts, time_goal,
    race_distance_km, race_duration_hr, race_terrain, race_pack_weight_kg).
    When the form-refresh PR lands these on the deployed schema, they'll
    fold into layer1_hash and this slot can be deprecated. v1 callers pass
    whatever they have; canonical_json on None/empty produces a stable empty
    representation."""
    race_id_component = (
        str(race_event_id) if race_event_id is not None else "no-event"
    )
    components = [
        str(user_id),
        layer1_hash,
        layer3a_hash,
        layer2a_hash,
        race_id_component,
        current_date.isoformat(),
        non_event_goal_type or "",
        canonical_json(etl_version_set),
        canonical_json(section_h2_kwargs or {}),
        model,
        str(temperature),
        str(max_tokens),
        str(extended_thinking_budget),
    ]
    return _sha256_hex("||".join(components))


def _serialize_layer3b_payload(payload: Layer3BPayload) -> str:
    """Pydantic-driven canonical JSON for cache storage."""
    return payload.model_dump_json()


def _hydrate_layer3b_payload(payload_json: str) -> Layer3BPayload:
    """Inverse of `_serialize_layer3b_payload`."""
    return Layer3BPayload.model_validate_json(payload_json)


def llm_layer3b_goal_timeline_viability_cached(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer3a_payload: Layer3APayload,
    layer2a_payload: Layer2APayload,
    race_event_payload: RaceEventPayload | None,
    current_date: date,
    etl_version_set: dict[str, str],
    *,
    cache_backend: CacheBackend,
    # §H.2 deployed-shape gap kwargs (D11) — included in the cache key
    # via section_h2_kwargs hash slot
    goal_outcome: str | None = None,
    time_goal: str | None = None,
    first_time_at_distance: bool | None = None,
    previous_attempts: list[dict[str, Any]] | None = None,
    race_distance_km: float | None = None,
    race_duration_hr: float | None = None,
    race_terrain: list[str] | None = None,
    race_pack_weight_kg: float | None = None,
    # §H.3 — no-event-mode caller override
    plan_duration_weeks: int | None = None,
    non_event_goal_type: str | None = None,
    # Sampling knobs
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = _DEFAULT_THINKING_BUDGET,
    llm_caller: LLMCaller | None = None,
) -> Layer3BPayload:
    """Cache wrapper around `llm_layer3b_goal_timeline_viability` per spec §9.

    On hit: deserialize stored Layer3BPayload JSON, return.
    On miss: call the underlying synthesizer, serialize result, store, return.

    The wrapper is a sibling to `llm_layer3b_goal_timeline_viability`, not a
    modification — the entry point stays cache-unaware per the spec's
    "cache wraps at orchestrator boundary" framing (same shape as the
    Layer 4 `_cached` wrappers + Layer 3A precedent)."""
    layer1_hash = compute_payload_hash(layer1_payload)
    layer3a_hash = compute_payload_hash(layer3a_payload)
    layer2a_hash = compute_payload_hash(layer2a_payload)
    race_event_id = (
        race_event_payload.race_event_id if race_event_payload is not None else None
    )

    # Effective no-event-mode resolution (mirrors driver-side resolution)
    if race_event_payload is None:
        if plan_duration_weeks is None:
            plan_duration_weeks = layer1_payload.event_goal.plan_duration_weeks_no_event
        if non_event_goal_type is None:
            non_event_goal_type = layer1_payload.event_goal.non_event_goal_type
    # Effective event-mode resolution: default the not-yet-captured
    # goal_outcome to the conservative "Finish" tier (see
    # _DEFAULT_EVENT_GOAL_OUTCOME). Feeds both _validate_inputs and the
    # deterministic section_h2_kwargs / cache key below.
    elif goal_outcome is None:
        goal_outcome = _DEFAULT_EVENT_GOAL_OUTCOME

    section_h2_kwargs: dict[str, Any] = {}
    if race_event_payload is not None:
        section_h2_kwargs = {
            "goal_outcome": goal_outcome,
            "time_goal": time_goal,
            "first_time_at_distance": first_time_at_distance,
            "previous_attempts": previous_attempts,
            "race_distance_km": race_distance_km,
            "race_duration_hr": race_duration_hr,
            "race_terrain": race_terrain,
            "race_pack_weight_kg": race_pack_weight_kg,
        }

    cache_key = layer3b_goal_timeline_viability_key(
        user_id=user_id,
        layer1_hash=layer1_hash,
        layer3a_hash=layer3a_hash,
        layer2a_hash=layer2a_hash,
        race_event_id=race_event_id,
        current_date=current_date,
        non_event_goal_type=non_event_goal_type,
        etl_version_set=etl_version_set,
        section_h2_kwargs=section_h2_kwargs,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        extended_thinking_budget=extended_thinking_budget,
    )

    entry = cache_backend.get(cache_key, PER_ENTRY_PHASE_IDX_SENTINEL)
    # D-77 diagnostic: HIT/MISS + the 3A-output hash 3B keys on. 3B's key folds
    # in layer3a_hash, so a drifting l3a (e.g. the last_sync churn) cascades to
    # a 3B MISS every pass; this line confirms 3B caches once l3a is stable.
    print(
        f"{_LAYER3B_ENTRY_POINT_LABEL}: user={user_id} "
        f"{'HIT' if entry is not None else 'MISS'} key={cache_key[:12]} "
        f"l3a={layer3a_hash[:8]}"
    )
    if entry is not None:
        return _hydrate_layer3b_payload(entry.payload_json)

    payload = llm_layer3b_goal_timeline_viability(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer3a_payload=layer3a_payload,
        layer2a_payload=layer2a_payload,
        race_event_payload=race_event_payload,
        current_date=current_date,
        etl_version_set=etl_version_set,
        goal_outcome=goal_outcome,
        time_goal=time_goal,
        first_time_at_distance=first_time_at_distance,
        previous_attempts=previous_attempts,
        race_distance_km=race_distance_km,
        race_duration_hr=race_duration_hr,
        race_terrain=race_terrain,
        race_pack_weight_kg=race_pack_weight_kg,
        plan_duration_weeks=plan_duration_weeks,
        non_event_goal_type=non_event_goal_type,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        extended_thinking_budget=extended_thinking_budget,
        llm_caller=llm_caller,
    )
    cache_backend.put(
        cache_key=cache_key,
        phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
        user_id=user_id,
        entry_point=_LAYER3B_ENTRY_POINT_LABEL,
        phase_name=None,
        payload_json=_serialize_layer3b_payload(payload),
    )
    return payload


__all__ = [
    "layer3b_goal_timeline_viability_key",
    "llm_layer3b_goal_timeline_viability_cached",
]
