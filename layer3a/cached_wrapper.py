"""Layer 3A cache adapter per `Layer3_3A_Spec.md` §9.

Single per-entry-point `_cached()` wrapper around `llm_layer3a_athlete_state`.
Reuses `layer4.cache.CacheBackend` (generic JSON storage) + `layer4.hashing`
primitives (`compute_payload_hash`, `canonical_json`, `_sha256_hex`) for
canonical cache-key derivation.

Cache key per spec §9.1:

    sha256(
        user_id ||
        layer1_payload_hash ||
        layer2a_payload_hash ||
        integration_bundle_hash ||
        as_of (day-granular) ||
        etl_version_set_json ||
        model ||
        str(temperature) ||
        str(max_tokens) ||
        str(extended_thinking_budget)
    )

Day-granular `as_of`: re-runs on the same calendar day return the cached
payload. Mid-day data changes invalidate via the bundle hash change per
spec §9.2 invalidation triggers.

Hit/miss flow mirrors `layer4.cache.Layer4Cache.get_or_synthesize` but
without the `Layer4Payload`-specific `_hydrate_layer4_payload` /
`_rebind_payload_dict` machinery — `Layer3APayload` is fully self-contained
(no `plan_version_id` / `suggestion_id` rebinding) so a hit just round-trips
through `model_dump_json` / `model_validate_json`.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Callable

from layer3a.builder import (
    _DEFAULT_MAX_TOKENS,
    _DEFAULT_MODEL,
    _DEFAULT_TEMPERATURE,
    _DEFAULT_THINKING_BUDGET,
    LLMCaller,
    llm_layer3a_athlete_state,
)
from layer4.cache import CacheBackend, PER_ENTRY_PHASE_IDX_SENTINEL
from layer4.context import (
    Layer1Payload,
    Layer2APayload,
    Layer3AIntegrationBundle,
    Layer3APayload,
)
from layer4.hashing import canonical_json, compute_payload_hash


_LAYER3A_ENTRY_POINT_LABEL = "llm_layer3a_athlete_state"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def layer3a_athlete_state_key(
    *,
    user_id: int,
    layer1_hash: str,
    layer2a_hash: str,
    integration_bundle_hash: str,
    as_of: datetime,
    etl_version_set: dict[str, str],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> str:
    """Per `Layer3_3A_Spec.md` §9.1 — cache key for `llm_layer3a_athlete_state`.

    `as_of` is collapsed to day-granular (hour/minute/second/microsecond
    zeroed) before hashing so multi-call-per-day on identical inputs all
    hit the same cache entry."""
    day_anchor = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    components = [
        str(user_id),
        layer1_hash,
        layer2a_hash,
        integration_bundle_hash,
        day_anchor.isoformat(),
        canonical_json(etl_version_set),
        model,
        str(temperature),
        str(max_tokens),
        str(extended_thinking_budget),
    ]
    return _sha256_hex("||".join(components))


def _serialize_layer3a_payload(payload: Layer3APayload) -> str:
    """Pydantic-driven canonical JSON for cache storage."""
    return payload.model_dump_json()


def _hydrate_layer3a_payload(payload_json: str) -> Layer3APayload:
    """Inverse of `_serialize_layer3a_payload`."""
    return Layer3APayload.model_validate_json(payload_json)


def llm_layer3a_athlete_state_cached(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    integration_bundle: Layer3AIntegrationBundle,
    as_of: datetime,
    etl_version_set: dict[str, str],
    *,
    cache_backend: CacheBackend,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = _DEFAULT_THINKING_BUDGET,
    llm_caller: LLMCaller | None = None,
) -> Layer3APayload:
    """Cache wrapper around `llm_layer3a_athlete_state` per spec §9.

    On hit: deserialize stored Layer3APayload JSON, return.
    On miss: call the underlying synthesizer, serialize result, store, return.

    The wrapper is a sibling to `llm_layer3a_athlete_state`, not a
    modification — the entry point stays cache-unaware per the spec's
    "cache wraps at orchestrator boundary" framing (same shape as the
    Layer 4 `_cached` wrappers in `layer4/cached_wrappers.py`)."""
    layer1_hash = compute_payload_hash(layer1_payload)
    layer2a_hash = compute_payload_hash(layer2a_payload)
    integration_bundle_hash = compute_payload_hash(integration_bundle)
    cache_key = layer3a_athlete_state_key(
        user_id=user_id,
        layer1_hash=layer1_hash,
        layer2a_hash=layer2a_hash,
        integration_bundle_hash=integration_bundle_hash,
        as_of=as_of,
        etl_version_set=etl_version_set,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        extended_thinking_budget=extended_thinking_budget,
    )

    entry = cache_backend.get(cache_key, PER_ENTRY_PHASE_IDX_SENTINEL)
    if entry is not None:
        return _hydrate_layer3a_payload(entry.payload_json)

    payload = llm_layer3a_athlete_state(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        integration_bundle=integration_bundle,
        as_of=as_of,
        etl_version_set=etl_version_set,
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
        entry_point=_LAYER3A_ENTRY_POINT_LABEL,
        phase_name=None,
        payload_json=_serialize_layer3a_payload(payload),
    )
    return payload


__all__ = [
    "layer3a_athlete_state_key",
    "llm_layer3a_athlete_state_cached",
]
