"""Layer 4 orchestrator-side cache per `Layer4_Spec.md` §9.

The cache wraps Layer 4 at the orchestrator boundary — the orchestrator
computes the cache key from Layer 4's input set, checks the cache, and
invokes Layer 4 only on miss. This module defines:

- `CacheBackend` — abstract storage interface (Postgres impl in
  `layer4/cache_postgres.py`; an `InMemoryCacheBackend` fake lives here
  for tests + ephemeral use).
- `CacheEntry` — the stored row shape (cache_key + entry_point + user_id
  + payload_json + per-phase metadata).
- `CacheMetrics` — per-`Layer4Cache` instance hit/miss/eviction counters
  per §9.6 observability.
- `Layer4Cache` — the orchestrator-facing API. `get_or_synthesize(...)`
  is the load-bearing call site each per-entry-point `_cached()` wrapper
  delegates to; on hit it rebinds `plan_version_id` (and `suggestion_id`
  for single-session) per §9.4 before returning.
- `_rebind_payload()` — pure-function helper that takes a deserialized
  `Layer4Payload` JSON dict and overwrites `plan_version_id` on the
  top-level + every session, plus `suggestion_id` when provided.

Per-phase cache for Pattern A (§9.2) uses the same `CacheBackend` rows
with `phase_idx >= 0`. The orchestrator chains the per-phase keys per the
spec formula (call_cache_key || phase_name || idx || prev_accepted_hash).

Invalidation (§9.3) is owned by `layer4/cache_invalidation.py`; this
module exposes the `evict_*()` primitives the invalidation tracker calls.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from layer4.payload import Layer4Payload


PER_ENTRY_PHASE_IDX_SENTINEL = -1
"""`phase_idx` sentinel for per-entry-point cache rows (§9.1).

Per-phase Pattern A rows (§9.2) carry `phase_idx >= 0`.
"""


EntryPoint = str
"""One of 'plan_create' | 'plan_refresh' | 'single_session_synthesize' | 'race_week_brief'."""


LAYER4_ENTRY_POINTS = frozenset(
    {"plan_create", "plan_refresh", "single_session_synthesize", "race_week_brief"}
)
"""Original Layer 4 per-entry-point set used by `Layer4Cache.get_or_synthesize`
+ `cache_invalidation.evict_on_layer_change` policy matrix (§9.3). The
invalidation policies are Layer-4-scoped; non-Layer-4 entry points that
reuse the generic `CacheBackend` storage do NOT participate."""


VALID_ENTRY_POINTS = LAYER4_ENTRY_POINTS | frozenset(
    {
        # Layer 3A cache wrapper extension (Phase 3.1-Driver, 2026-05-20) —
        # `layer3a/cached_wrapper.py` reuses the generic CacheBackend storage
        # but is NOT a Layer4Payload entry point; Layer4Cache.get_or_synthesize
        # is not used (Layer3APayload has no plan_version_id/suggestion_id
        # rebinding, so the wrapper hits the backend directly).
        "llm_layer3a_athlete_state",
        # Layer 3B cache wrapper extension (Phase 4, 2026-05-20) —
        # `layer3b/cached_wrapper.py`; same shape as 3A (Layer3BPayload is
        # self-contained, no plan_version_id/suggestion_id rebinding).
        "llm_layer3b_goal_timeline_viability",
        # D-64 NL parser cache (Phase 5.2 caller-side D-64 runtime,
        # 2026-05-21) — `nl_parser.parse_intent` per
        # `aidstation-sources/prompts/NLParser_v1.md` §10. Athlete-scoped
        # (not Layer-4-scoped) so it deliberately stays out of
        # LAYER4_ENTRY_POINTS + the §9.3 Layer-4 invalidation matrix.
        "nl_parser_parse_intent",
    }
)
"""Superset of allowable entry_point labels for `CacheBackend.put` validation.
Includes both Layer 4 entry points + sibling layers (currently Layer 3A) that
reuse the storage primitives."""


# ─── Stored row shape ──────────────────────────────────────────────────────


@dataclass
class CacheEntry:
    """One stored cache row.

    `payload_json` is the canonical-JSON-serialized `Layer4Payload` for
    per-entry-point rows (§9.1); for per-phase Pattern A rows (§9.2) it's
    the canonical-JSON of `{"sessions": [...], "synthesis_metadata": ...}`
    tuple per the spec.
    """

    cache_key: str
    phase_idx: int
    user_id: int
    entry_point: EntryPoint
    phase_name: str | None
    payload_json: str
    created_at: datetime
    last_hit_at: datetime
    hit_count: int

    def is_per_phase(self) -> bool:
        return self.phase_idx >= 0


# ─── Observability counters per §9.6 ───────────────────────────────────────


@dataclass
class CacheMetrics:
    """Per-`Layer4Cache` instance counters; tests + orchestrator dashboards
    read these directly. Per-entry-point breakdowns kept in dicts; per-phase
    rolls into the same `phase_*` counter set."""

    hits_total: int = 0
    misses_total: int = 0
    evictions_total: int = 0
    hits_per_entry_point: dict[str, int] = field(default_factory=dict)
    misses_per_entry_point: dict[str, int] = field(default_factory=dict)
    evictions_per_layer: dict[str, int] = field(default_factory=dict)
    phase_hits_total: int = 0
    phase_misses_total: int = 0

    def record_hit(self, entry_point: EntryPoint, *, is_phase: bool = False) -> None:
        if is_phase:
            self.phase_hits_total += 1
        else:
            self.hits_total += 1
            self.hits_per_entry_point[entry_point] = (
                self.hits_per_entry_point.get(entry_point, 0) + 1
            )

    def record_miss(self, entry_point: EntryPoint, *, is_phase: bool = False) -> None:
        if is_phase:
            self.phase_misses_total += 1
        else:
            self.misses_total += 1
            self.misses_per_entry_point[entry_point] = (
                self.misses_per_entry_point.get(entry_point, 0) + 1
            )

    def record_eviction(self, layer: str, count: int = 1) -> None:
        if count <= 0:
            return
        self.evictions_total += count
        self.evictions_per_layer[layer] = self.evictions_per_layer.get(layer, 0) + count


# ─── Abstract backend ──────────────────────────────────────────────────────


class CacheBackend(ABC):
    """Storage interface for Layer 4 cache entries.

    Implementations decide where rows live (Postgres, Redis, in-memory).
    All methods are synchronous; orchestrator owns concurrency. Eviction
    methods return the number of rows actually removed so the metrics
    layer can record observability events accurately.
    """

    @abstractmethod
    def get(self, cache_key: str, phase_idx: int = PER_ENTRY_PHASE_IDX_SENTINEL) -> CacheEntry | None:
        """Return the entry for (`cache_key`, `phase_idx`) or None on miss.

        Implementations should increment `hit_count` + bump `last_hit_at` on
        a successful read so retention/TTL policies can use it.
        """

    @abstractmethod
    def put(
        self,
        *,
        cache_key: str,
        phase_idx: int,
        user_id: int,
        entry_point: EntryPoint,
        phase_name: str | None,
        payload_json: str,
    ) -> None:
        """Upsert a cache entry. Existing rows are replaced (no merge)."""

    @abstractmethod
    def evict_for_user(
        self,
        user_id: int,
        *,
        entry_points: tuple[EntryPoint, ...] | None = None,
    ) -> int:
        """Delete all rows for `user_id`, optionally filtering by entry_point.

        When `entry_points` is None all entry points are evicted; otherwise
        only rows whose entry_point matches one of the listed values.
        Returns the count of rows deleted.
        """

    @abstractmethod
    def evict_entry_point(
        self,
        entry_point: EntryPoint,
        *,
        user_id: int | None = None,
    ) -> int:
        """Delete all rows for `entry_point` (e.g., midnight UTC rollover for
        race_week_brief per §9.3). When `user_id` is None evicts globally.
        Returns the count of rows deleted.
        """

    @abstractmethod
    def clear_all(self) -> int:
        """Test/dev utility — drop every cache row. Returns the count."""


# ─── In-memory backend (tests + ephemeral use) ─────────────────────────────


class InMemoryCacheBackend(CacheBackend):
    """Process-local dict-backed backend; thread-safe via a single lock.

    Useful for tests, single-process dev runs, and as the reference impl
    against which `PostgresCacheBackend` is validated. NOT useful for the
    Vercel serverless deployment where each invocation is a fresh process
    (always-empty cache) — use `PostgresCacheBackend` for production.
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[str, int], CacheEntry] = {}
        self._lock = threading.Lock()

    def get(
        self, cache_key: str, phase_idx: int = PER_ENTRY_PHASE_IDX_SENTINEL
    ) -> CacheEntry | None:
        with self._lock:
            entry = self._rows.get((cache_key, phase_idx))
            if entry is None:
                return None
            entry.hit_count += 1
            entry.last_hit_at = _utcnow()
            return entry

    def put(
        self,
        *,
        cache_key: str,
        phase_idx: int,
        user_id: int,
        entry_point: EntryPoint,
        phase_name: str | None,
        payload_json: str,
    ) -> None:
        if entry_point not in VALID_ENTRY_POINTS:
            raise ValueError(f"unknown entry_point={entry_point!r}")
        if phase_idx < 0 and phase_idx != PER_ENTRY_PHASE_IDX_SENTINEL:
            raise ValueError(f"phase_idx must be >= 0 for per-phase rows or {PER_ENTRY_PHASE_IDX_SENTINEL} for per-entry; got {phase_idx}")
        if phase_idx >= 0 and phase_name is None:
            raise ValueError("phase_name is required for per-phase rows")
        if phase_idx == PER_ENTRY_PHASE_IDX_SENTINEL and phase_name is not None:
            raise ValueError("phase_name must be None for per-entry rows")
        now = _utcnow()
        with self._lock:
            self._rows[(cache_key, phase_idx)] = CacheEntry(
                cache_key=cache_key,
                phase_idx=phase_idx,
                user_id=user_id,
                entry_point=entry_point,
                phase_name=phase_name,
                payload_json=payload_json,
                created_at=now,
                last_hit_at=now,
                hit_count=0,
            )

    def evict_for_user(
        self,
        user_id: int,
        *,
        entry_points: tuple[EntryPoint, ...] | None = None,
    ) -> int:
        with self._lock:
            keys_to_drop = [
                k
                for k, v in self._rows.items()
                if v.user_id == user_id
                and (entry_points is None or v.entry_point in entry_points)
            ]
            for k in keys_to_drop:
                del self._rows[k]
            return len(keys_to_drop)

    def evict_entry_point(
        self,
        entry_point: EntryPoint,
        *,
        user_id: int | None = None,
    ) -> int:
        with self._lock:
            keys_to_drop = [
                k
                for k, v in self._rows.items()
                if v.entry_point == entry_point
                and (user_id is None or v.user_id == user_id)
            ]
            for k in keys_to_drop:
                del self._rows[k]
            return len(keys_to_drop)

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._rows)
            self._rows.clear()
            return count

    def __len__(self) -> int:
        """Test convenience — total stored rows."""
        with self._lock:
            return len(self._rows)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Rebinding per §9.4 ────────────────────────────────────────────────────


def _rebind_payload_dict(
    payload_dict: dict[str, Any],
    *,
    plan_version_id: int,
    suggestion_id: int | None = None,
) -> dict[str, Any]:
    """Overwrite `plan_version_id` on the top-level + every session, plus
    `suggestion_id` when provided. Operates on the deserialized JSON dict
    directly (faster than round-tripping through pydantic + the rebound
    fields don't change validator outcomes).

    The cached payload is NOT modified; this function returns a NEW dict
    with the rebind applied so the cache entry remains stable across
    calls.

    Per §9.4: rebinding is byte-precise — no other fields change.
    """
    # Shallow copy at the top-level; replace sessions list with a re-bound copy.
    rebound: dict[str, Any] = dict(payload_dict)
    rebound["plan_version_id"] = plan_version_id

    sessions = payload_dict.get("sessions") or []
    new_sessions: list[dict[str, Any]] = []
    for s in sessions:
        new_sessions.append({**s, "plan_version_id": plan_version_id})
    rebound["sessions"] = new_sessions

    if suggestion_id is not None:
        rebound["suggestion_id"] = suggestion_id

    return rebound


def _deserialize_payload(payload_json: str) -> dict[str, Any]:
    import json

    return json.loads(payload_json)


def _serialize_payload(payload: Layer4Payload) -> str:
    """Canonical-JSON serialization of a `Layer4Payload` for storage."""
    return payload.model_dump_json()


def _hydrate_layer4_payload(
    payload_dict: dict[str, Any],
) -> Layer4Payload:
    """Re-construct a `Layer4Payload` from a (possibly rebound) JSON dict.

    Pydantic re-runs all validators on construction. The rebound fields
    (`plan_version_id` per-session and top-level; `suggestion_id`) don't
    affect any validator outcomes.
    """
    return Layer4Payload.model_validate(payload_dict)


# ─── Orchestrator-side API ─────────────────────────────────────────────────


class Layer4Cache:
    """Layer 4 orchestrator-side cache facade.

    Wraps a `CacheBackend` + a `CacheMetrics` counter. Each per-entry-point
    `_cached()` wrapper delegates here via `get_or_synthesize()`. Per-phase
    Pattern A reads/writes (§9.2) go through `get_phase_or_synthesize()`.
    """

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend
        self.metrics = CacheMetrics()

    @property
    def backend(self) -> CacheBackend:
        return self._backend

    def get_or_synthesize(
        self,
        *,
        cache_key: str,
        user_id: int,
        entry_point: EntryPoint,
        synthesizer: Callable[[], Layer4Payload],
        rebind_plan_version_id: int,
        rebind_suggestion_id: int | None = None,
    ) -> Layer4Payload:
        """Per-entry-point cache hit/miss flow per §9.1 + §9.4.

        On hit: deserialize cached payload, rebind plan_version_id +
        suggestion_id, reconstruct typed `Layer4Payload`, return.

        On miss: invoke `synthesizer()`, serialize result, store, return.
        The synthesizer is expected to allocate its own plan_version_id
        (passed by the orchestrator); cached on miss, NOT rebound.

        Bytes-identity guarantee on hit (modulo rebinding): same cached
        payload returns the same Layer4Payload shape across calls — only
        the rebound fields change.
        """
        if entry_point not in VALID_ENTRY_POINTS:
            raise ValueError(f"unknown entry_point={entry_point!r}")

        entry = self._backend.get(cache_key, PER_ENTRY_PHASE_IDX_SENTINEL)
        if entry is not None:
            self.metrics.record_hit(entry_point)
            payload_dict = _deserialize_payload(entry.payload_json)
            rebound = _rebind_payload_dict(
                payload_dict,
                plan_version_id=rebind_plan_version_id,
                suggestion_id=rebind_suggestion_id,
            )
            return _hydrate_layer4_payload(rebound)

        # Miss — invoke synthesizer + store result.
        self.metrics.record_miss(entry_point)
        payload = synthesizer()
        self._backend.put(
            cache_key=cache_key,
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=user_id,
            entry_point=entry_point,
            phase_name=None,
            payload_json=_serialize_payload(payload),
        )
        return payload

    def get_phase_or_synthesize(
        self,
        *,
        phase_key: str,
        phase_idx: int,
        phase_name: str,
        user_id: int,
        entry_point: EntryPoint,
        synthesizer: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Per-phase cache hit/miss flow for Pattern A per §9.2.

        Stored payload shape is the JSON-encoded
        `{"sessions": [...PlanSession-as-dict...], "synthesis_metadata": {...}}`
        tuple per the spec. Caller (orchestrator) is responsible for
        constructing the chained `phase_key` per §9.2 formula.

        Per-phase rows do NOT participate in plan_version_id rebinding —
        the per-phase output is a raw `(sessions, synthesis_metadata)`
        tuple and the orchestrator stamps plan_version_id onto the
        sessions during composition into the final Layer4Payload (which
        then goes through the per-entry-point cache).
        """
        if entry_point not in VALID_ENTRY_POINTS:
            raise ValueError(f"unknown entry_point={entry_point!r}")
        if phase_idx < 0:
            raise ValueError(f"phase_idx must be >= 0 for per-phase rows; got {phase_idx}")

        entry = self._backend.get(phase_key, phase_idx)
        if entry is not None:
            self.metrics.record_hit(entry_point, is_phase=True)
            # D-77 diagnostic: a HIT means this block was reused from a prior
            # resumable pass (convergence working). Diagnostic only.
            print(
                f"layer4 cache: block idx={phase_idx} {phase_name} HIT "
                f"key={phase_key[:12]}"
            )
            return _deserialize_payload(entry.payload_json)

        self.metrics.record_miss(entry_point, is_phase=True)
        # D-77 diagnostic: a MISS for a block that a prior pass already
        # synthesized signals cache-key churn (the non-convergence loop) — pair
        # with the call_cache_key line to confirm. Diagnostic only.
        print(
            f"layer4 cache: block idx={phase_idx} {phase_name} MISS — "
            f"synthesizing key={phase_key[:12]}"
        )
        import json as _json

        result = synthesizer()
        self._backend.put(
            cache_key=phase_key,
            phase_idx=phase_idx,
            user_id=user_id,
            entry_point=entry_point,
            phase_name=phase_name,
            payload_json=_json.dumps(result, sort_keys=True, separators=(",", ":")),
        )
        return result

    def invalidate_user(
        self,
        user_id: int,
        *,
        layer: str,
        entry_points: tuple[EntryPoint, ...] | None = None,
    ) -> int:
        """Eviction primitive used by `cache_invalidation.evict_on_layer_change()`.

        `layer` is the upstream layer name (e.g., 'layer1', 'layer2b',
        'layer3a') — used purely for metrics tagging here; the actual
        eviction policy (which entry_points to evict) lives in
        `cache_invalidation.py` per §9.3. Callers pass the resolved
        `entry_points` tuple based on that policy.
        """
        count = self._backend.evict_for_user(user_id, entry_points=entry_points)
        self.metrics.record_eviction(layer, count)
        return count

    def invalidate_entry_point(
        self,
        entry_point: EntryPoint,
        *,
        layer: str,
        user_id: int | None = None,
    ) -> int:
        """Cross-user eviction for an entry_point (e.g., midnight-UTC
        rollover evicts ALL `race_week_brief` rows per §9.3).
        """
        count = self._backend.evict_entry_point(entry_point, user_id=user_id)
        self.metrics.record_eviction(layer, count)
        return count
