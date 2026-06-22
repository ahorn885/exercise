"""Tests for the Layer 4 Step 5 cache layer per `Layer4_Spec.md` §9.

Coverage:
- `CacheEntry` / `CacheMetrics` dataclass shape
- `InMemoryCacheBackend` — get/put/evict_for_user/evict_entry_point/clear_all
- `PostgresCacheBackend` — same interface against a fake connection
- `_rebind_payload_dict` — plan_version_id (top + sessions) + suggestion_id
- `Layer4Cache.get_or_synthesize` — miss synth+store; hit rebind+return; metrics
- `Layer4Cache.get_phase_or_synthesize` — per-phase cache flow per §9.2
- `Layer4Cache.invalidate_*` — metrics tagging
- `cache_invalidation.policy_for_layer` — all 9 layer mappings
- `evict_on_layer_change` — routes correctly per §9.3 matrix
- `evict_on_midnight_rollover` — race_week_brief only; user-scoped vs global
- `compute_accepted_output_hash` + `compute_phase_cache_key` — determinism +
  chaining + None-prev-hash boundary
- Cached wrappers (single_session, plan_refresh, plan_create, race_week_brief)
  — happy-path miss-then-hit with rebinding via dependency injection

All tests are pure-function or use the in-memory backend + a fake Postgres
connection; no real DB or LLM calls.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pytest

from layer4 import (
    CacheBackend,
    CacheEntry,
    CacheMetrics,
    InMemoryCacheBackend,
    Layer4Cache,
    Layer4Payload,
    PER_ENTRY_PHASE_IDX_SENTINEL,
    PlanSession,
    PostgresCacheBackend,
    LAYER4_ENTRY_POINTS,
    VALID_ENTRY_POINTS,
    canonical_json,
    compute_accepted_output_hash,
    compute_block_cache_key,
    compute_payload_hash,
    compute_phase_cache_key,
    evict_on_layer_change,
    evict_on_midnight_rollover,
    policy_for_layer,
)
from layer4.cache import _rebind_payload_dict


# ─── Fixtures ────────────────────────────────────────────────────────────────


_USER_ID = 42


def _minimal_session(*, plan_version_id: int = 1, session_id: str = "S-1") -> PlanSession:
    """Minimal rest session — easiest invariant-satisfying PlanSession."""
    return PlanSession(
        session_id=session_id,
        plan_version_id=plan_version_id,
        date=date(2026, 6, 1),
        day_of_week="Mon",
        session_index_in_day=0,
        time_of_day="morning",
        kind="rest",
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        session_notes="Rest day.",
        coaching_intent="Recovery.",
        coaching_flags=[],
    )


def _minimal_single_session(
    *,
    plan_version_id: int = 1,
    suggestion_id: int = 100,
) -> Layer4Payload:
    """Smallest valid Layer4Payload for mode='single_session_synthesize'."""
    from layer4 import (
        CardioBlock,
        HRTarget,
        Observation,
        RuleFailure,
        ValidatorResult,
    )

    session = PlanSession(
        session_id="S-1",
        plan_version_id=plan_version_id,
        date=date(2026, 6, 1),
        day_of_week="Mon",
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="D-run",
        discipline_name="Running",
        locale_id="home_gym",
        locale_name="Home gym",
        duration_min=60,
        intensity_summary="easy",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=130, hr_bpm_high=145),
                instructions="Steady aerobic.",
            )
        ],
        session_notes="Easy aerobic.",
        coaching_intent="Aerobic stimulus.",
        coaching_flags=[],
        is_ad_hoc=True,
        ad_hoc_request_payload={"source": "test"},
    )
    return Layer4Payload(
        user_id=_USER_ID,
        mode="single_session_synthesize",
        plan_version_id=plan_version_id,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 6, 1),
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.3,
        pattern="B",
        latency_ms_total=4200,
        input_tokens_total=3000,
        output_tokens_total=800,
        llm_call_count=1,
        etl_version_set={"layer0": "v7"},
        sessions=[session],
        validator_results=[
            ValidatorResult(pass_index=0, accepted=True, rule_failures=[], retried_phase_names=[])
        ],
        notable_observations=[],
        suggestion_id=suggestion_id,
    )


# ─── CacheEntry / CacheMetrics dataclasses ───────────────────────────────────


class TestCacheEntry:
    def test_per_entry_row_shape(self):
        entry = CacheEntry(
            cache_key="abc",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1,
            entry_point="single_session_synthesize",
            phase_name=None,
            payload_json='{"x": 1}',
            created_at=datetime(2026, 5, 18),
            last_hit_at=datetime(2026, 5, 18),
            hit_count=0,
        )
        assert not entry.is_per_phase()

    def test_per_phase_row_shape(self):
        entry = CacheEntry(
            cache_key="abc",
            phase_idx=2,
            user_id=1,
            entry_point="plan_create",
            phase_name="Build",
            payload_json="{}",
            created_at=datetime(2026, 5, 18),
            last_hit_at=datetime(2026, 5, 18),
            hit_count=0,
        )
        assert entry.is_per_phase()


class TestCacheMetrics:
    def test_starts_at_zero(self):
        m = CacheMetrics()
        assert m.hits_total == 0
        assert m.misses_total == 0
        assert m.evictions_total == 0

    def test_record_hit_per_entry(self):
        m = CacheMetrics()
        m.record_hit("plan_create")
        m.record_hit("plan_create")
        m.record_hit("single_session_synthesize")
        assert m.hits_total == 3
        assert m.hits_per_entry_point == {"plan_create": 2, "single_session_synthesize": 1}

    def test_record_miss_per_entry(self):
        m = CacheMetrics()
        m.record_miss("plan_refresh")
        assert m.misses_total == 1
        assert m.misses_per_entry_point == {"plan_refresh": 1}

    def test_record_phase_hits_and_misses(self):
        m = CacheMetrics()
        m.record_hit("plan_create", is_phase=True)
        m.record_miss("plan_create", is_phase=True)
        # phase counters don't bump per-entry counters
        assert m.hits_total == 0
        assert m.misses_total == 0
        assert m.phase_hits_total == 1
        assert m.phase_misses_total == 1

    def test_record_eviction(self):
        m = CacheMetrics()
        m.record_eviction("layer1", count=3)
        m.record_eviction("layer1", count=1)
        m.record_eviction("layer3a", count=2)
        assert m.evictions_total == 6
        assert m.evictions_per_layer == {"layer1": 4, "layer3a": 2}

    def test_record_eviction_zero_noop(self):
        m = CacheMetrics()
        m.record_eviction("layer1", count=0)
        assert m.evictions_total == 0
        assert "layer1" not in m.evictions_per_layer


# ─── InMemoryCacheBackend ────────────────────────────────────────────────────


class TestInMemoryCacheBackend:
    def test_get_miss_returns_none(self):
        b = InMemoryCacheBackend()
        assert b.get("nonexistent") is None

    def test_put_and_get_per_entry(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="k1",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID,
            entry_point="single_session_synthesize",
            phase_name=None,
            payload_json='{"x": 1}',
        )
        entry = b.get("k1")
        assert entry is not None
        assert entry.cache_key == "k1"
        assert entry.user_id == _USER_ID
        assert entry.entry_point == "single_session_synthesize"
        assert entry.phase_idx == PER_ENTRY_PHASE_IDX_SENTINEL
        assert entry.hit_count == 1  # bumped on read

    def test_put_per_phase(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="pk1",
            phase_idx=0,
            user_id=_USER_ID,
            entry_point="plan_create",
            phase_name="Base",
            payload_json='{"sessions": []}',
        )
        entry = b.get("pk1", phase_idx=0)
        assert entry is not None
        assert entry.is_per_phase()
        assert entry.phase_name == "Base"

    def test_per_entry_and_per_phase_isolated_by_phase_idx(self):
        """Same cache_key with different phase_idx values are different rows."""
        b = InMemoryCacheBackend()
        b.put(
            cache_key="shared",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID,
            entry_point="plan_create",
            phase_name=None,
            payload_json='{"top": true}',
        )
        b.put(
            cache_key="shared",
            phase_idx=0,
            user_id=_USER_ID,
            entry_point="plan_create",
            phase_name="Base",
            payload_json='{"phase": true}',
        )
        top = b.get("shared", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL)
        phase = b.get("shared", phase_idx=0)
        assert top is not None and phase is not None
        assert top.payload_json == '{"top": true}'
        assert phase.payload_json == '{"phase": true}'

    def test_put_rejects_unknown_entry_point(self):
        b = InMemoryCacheBackend()
        with pytest.raises(ValueError, match="unknown entry_point"):
            b.put(
                cache_key="k",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point="bogus",
                phase_name=None,
                payload_json="{}",
            )

    def test_put_rejects_per_phase_without_phase_name(self):
        b = InMemoryCacheBackend()
        with pytest.raises(ValueError, match="phase_name is required"):
            b.put(
                cache_key="k",
                phase_idx=0,
                user_id=_USER_ID,
                entry_point="plan_create",
                phase_name=None,
                payload_json="{}",
            )

    def test_put_rejects_per_entry_with_phase_name(self):
        b = InMemoryCacheBackend()
        with pytest.raises(ValueError, match="phase_name must be None"):
            b.put(
                cache_key="k",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point="plan_create",
                phase_name="Base",
                payload_json="{}",
            )

    def test_put_rejects_invalid_phase_idx(self):
        b = InMemoryCacheBackend()
        with pytest.raises(ValueError, match="phase_idx must be"):
            b.put(
                cache_key="k",
                phase_idx=-5,
                user_id=_USER_ID,
                entry_point="plan_create",
                phase_name="Base",
                payload_json="{}",
            )

    def test_put_upserts(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="k",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID,
            entry_point="plan_create",
            phase_name=None,
            payload_json='{"v": 1}',
        )
        b.put(
            cache_key="k",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID,
            entry_point="plan_create",
            phase_name=None,
            payload_json='{"v": 2}',
        )
        entry = b.get("k")
        assert entry is not None
        assert entry.payload_json == '{"v": 2}'
        assert entry.hit_count == 1
        # Total stored rows still 1.
        assert len(b) == 1

    def test_evict_for_user_unconditional(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="plan_create", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="single_session_synthesize", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k3", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=2, entry_point="plan_create", phase_name=None, payload_json="{}",
        )
        count = b.evict_for_user(1)
        assert count == 2
        assert b.get("k1") is None
        assert b.get("k2") is None
        assert b.get("k3") is not None  # different user

    def test_evict_for_user_filtered_by_entry_point(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="plan_create", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="single_session_synthesize", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k3", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        count = b.evict_for_user(1, entry_points=("plan_create", "race_week_brief"))
        assert count == 2
        assert b.get("k1") is None
        assert b.get("k2") is not None  # single_session_synthesize preserved
        assert b.get("k3") is None

    def test_evict_entry_point_globally(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=2, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k3", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="plan_create", phase_name=None, payload_json="{}",
        )
        count = b.evict_entry_point("race_week_brief")
        assert count == 2
        assert b.get("k3") is not None

    def test_evict_entry_point_user_scoped(self):
        b = InMemoryCacheBackend()
        b.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        b.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=2, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        count = b.evict_entry_point("race_week_brief", user_id=1)
        assert count == 1
        assert b.get("k1") is None
        assert b.get("k2") is not None  # different user

    def test_clear_all(self):
        b = InMemoryCacheBackend()
        for i in range(3):
            b.put(
                cache_key=f"k{i}", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=1, entry_point="plan_create", phase_name=None, payload_json="{}",
            )
        count = b.clear_all()
        assert count == 3
        assert len(b) == 0


# ─── _rebind_payload_dict ────────────────────────────────────────────────────


class TestRebindPayloadDict:
    def test_rebinds_top_level_plan_version_id(self):
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        d = json.loads(payload.model_dump_json())
        rebound = _rebind_payload_dict(d, plan_version_id=999)
        assert rebound["plan_version_id"] == 999

    def test_rebinds_each_session_plan_version_id(self):
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        d = json.loads(payload.model_dump_json())
        rebound = _rebind_payload_dict(d, plan_version_id=999)
        for s in rebound["sessions"]:
            assert s["plan_version_id"] == 999

    def test_rebinds_suggestion_id_when_provided(self):
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        d = json.loads(payload.model_dump_json())
        rebound = _rebind_payload_dict(d, plan_version_id=2, suggestion_id=555)
        assert rebound["suggestion_id"] == 555

    def test_suggestion_id_unchanged_when_omitted(self):
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        d = json.loads(payload.model_dump_json())
        rebound = _rebind_payload_dict(d, plan_version_id=2)
        assert rebound["suggestion_id"] == 100  # original preserved

    def test_input_dict_not_mutated(self):
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        d = json.loads(payload.model_dump_json())
        original_pv = d["plan_version_id"]
        original_session_pv = d["sessions"][0]["plan_version_id"]
        _ = _rebind_payload_dict(d, plan_version_id=999, suggestion_id=555)
        # Original dict untouched.
        assert d["plan_version_id"] == original_pv
        assert d["sessions"][0]["plan_version_id"] == original_session_pv

    def test_rebound_payload_revalidates(self):
        """Rebound payload should pass Layer4Payload validation (mode invariants
        still hold; the rebound suggestion_id is non-None for single_session)."""
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        d = json.loads(payload.model_dump_json())
        rebound_dict = _rebind_payload_dict(d, plan_version_id=42, suggestion_id=999)
        rebound = Layer4Payload.model_validate(rebound_dict)
        assert rebound.plan_version_id == 42
        assert rebound.suggestion_id == 999
        assert rebound.sessions[0].plan_version_id == 42


# ─── Layer4Cache.get_or_synthesize ───────────────────────────────────────────


class TestLayer4CacheGetOrSynthesize:
    def test_miss_invokes_synthesizer_and_stores(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        calls = {"n": 0}

        def synth() -> Layer4Payload:
            calls["n"] += 1
            return payload

        result = cache.get_or_synthesize(
            cache_key="k1",
            user_id=_USER_ID,
            entry_point="single_session_synthesize",
            synthesizer=synth,
            rebind_plan_version_id=1,
            rebind_suggestion_id=100,
        )
        assert calls["n"] == 1
        assert result.plan_version_id == 1
        assert cache.metrics.misses_total == 1
        assert cache.metrics.hits_total == 0

    def test_hit_skips_synthesizer_and_rebinds(self):
        backend = InMemoryCacheBackend()
        cache = Layer4Cache(backend)
        cached_payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)

        # Seed cache directly.
        backend.put(
            cache_key="k1",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID,
            entry_point="single_session_synthesize",
            phase_name=None,
            payload_json=cached_payload.model_dump_json(),
        )

        def synth() -> Layer4Payload:
            raise AssertionError("synthesizer should NOT be called on hit")

        rebound = cache.get_or_synthesize(
            cache_key="k1",
            user_id=_USER_ID,
            entry_point="single_session_synthesize",
            synthesizer=synth,
            rebind_plan_version_id=999,
            rebind_suggestion_id=555,
        )
        assert rebound.plan_version_id == 999
        assert rebound.suggestion_id == 555
        assert rebound.sessions[0].plan_version_id == 999
        assert cache.metrics.hits_total == 1
        assert cache.metrics.misses_total == 0

    def test_hit_metric_per_entry_point(self):
        backend = InMemoryCacheBackend()
        cache = Layer4Cache(backend)
        cached_payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        backend.put(
            cache_key="k1",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID,
            entry_point="single_session_synthesize",
            phase_name=None,
            payload_json=cached_payload.model_dump_json(),
        )
        cache.get_or_synthesize(
            cache_key="k1",
            user_id=_USER_ID,
            entry_point="single_session_synthesize",
            synthesizer=lambda: cached_payload,
            rebind_plan_version_id=2,
            rebind_suggestion_id=200,
        )
        assert cache.metrics.hits_per_entry_point["single_session_synthesize"] == 1

    def test_unknown_entry_point_rejected(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        with pytest.raises(ValueError, match="unknown entry_point"):
            cache.get_or_synthesize(
                cache_key="k1",
                user_id=_USER_ID,
                entry_point="bogus",
                synthesizer=lambda: _minimal_single_session(),
                rebind_plan_version_id=1,
                rebind_suggestion_id=1,
            )

    def test_miss_then_hit_full_flow(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        payload = _minimal_single_session(plan_version_id=1, suggestion_id=100)
        calls = {"n": 0}

        def synth() -> Layer4Payload:
            calls["n"] += 1
            return payload

        cache.get_or_synthesize(
            cache_key="k1", user_id=_USER_ID,
            entry_point="single_session_synthesize",
            synthesizer=synth,
            rebind_plan_version_id=1, rebind_suggestion_id=100,
        )
        rebound = cache.get_or_synthesize(
            cache_key="k1", user_id=_USER_ID,
            entry_point="single_session_synthesize",
            synthesizer=synth,
            rebind_plan_version_id=42, rebind_suggestion_id=999,
        )
        assert calls["n"] == 1  # synthesizer only called once
        assert cache.metrics.misses_total == 1
        assert cache.metrics.hits_total == 1
        assert rebound.plan_version_id == 42
        assert rebound.suggestion_id == 999


# ─── Layer4Cache.get_phase_or_synthesize (§9.2) ──────────────────────────────


class TestLayer4CachePerPhase:
    def test_miss_invokes_synthesizer_and_stores(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        calls = {"n": 0}

        def synth() -> dict[str, Any]:
            calls["n"] += 1
            return {"sessions": [], "synthesis_metadata": {"x": 1}}

        result = cache.get_phase_or_synthesize(
            phase_key="pk1",
            phase_idx=0,
            phase_name="Base",
            user_id=_USER_ID,
            entry_point="plan_create",
            synthesizer=synth,
        )
        assert calls["n"] == 1
        assert result == {"sessions": [], "synthesis_metadata": {"x": 1}}
        assert cache.metrics.phase_misses_total == 1

    def test_hit_skips_synthesizer(self):
        cache = Layer4Cache(InMemoryCacheBackend())

        def first_synth():
            return {"sessions": [{"a": 1}], "synthesis_metadata": {"m": 1}}

        cache.get_phase_or_synthesize(
            phase_key="pk1", phase_idx=0, phase_name="Base",
            user_id=_USER_ID, entry_point="plan_create",
            synthesizer=first_synth,
        )

        def fail_synth():
            raise AssertionError("should not be called")

        result = cache.get_phase_or_synthesize(
            phase_key="pk1", phase_idx=0, phase_name="Base",
            user_id=_USER_ID, entry_point="plan_create",
            synthesizer=fail_synth,
        )
        assert result == {"sessions": [{"a": 1}], "synthesis_metadata": {"m": 1}}
        assert cache.metrics.phase_hits_total == 1
        assert cache.metrics.phase_misses_total == 1

    def test_negative_phase_idx_rejected(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        with pytest.raises(ValueError, match="phase_idx must be >= 0"):
            cache.get_phase_or_synthesize(
                phase_key="pk1",
                phase_idx=-1,
                phase_name="Base",
                user_id=_USER_ID,
                entry_point="plan_create",
                synthesizer=lambda: {},
            )


# ─── Layer4Cache.invalidate_* ────────────────────────────────────────────────


class TestLayer4CacheInvalidate:
    def test_invalidate_user_records_metric(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        cache.backend.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=_USER_ID, entry_point="plan_create",
            phase_name=None, payload_json="{}",
        )
        count = cache.invalidate_user(_USER_ID, layer="layer1")
        assert count == 1
        assert cache.metrics.evictions_total == 1
        assert cache.metrics.evictions_per_layer == {"layer1": 1}

    def test_invalidate_entry_point_records_metric(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        cache.backend.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="race_week_brief",
            phase_name=None, payload_json="{}",
        )
        cache.backend.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=2, entry_point="race_week_brief",
            phase_name=None, payload_json="{}",
        )
        count = cache.invalidate_entry_point("race_week_brief", layer="midnight_rollover")
        assert count == 2
        assert cache.metrics.evictions_per_layer == {"midnight_rollover": 2}


# ─── cache_invalidation policy ───────────────────────────────────────────────


_LAYER3_BOTH_LABELS = frozenset(
    {"llm_layer3a_athlete_state", "llm_layer3b_goal_timeline_viability"}
)


class TestEvictionPolicy:
    def test_policy_layer1_covers_layer4_and_layer3(self):
        assert set(policy_for_layer("layer1")) == set(LAYER4_ENTRY_POINTS) | _LAYER3_BOTH_LABELS

    def test_policy_layer2a_covers_layer4_and_layer3(self):
        assert set(policy_for_layer("layer2a")) == set(LAYER4_ENTRY_POINTS) | _LAYER3_BOTH_LABELS

    def test_policy_layer2b_excludes_single_session(self):
        result = set(policy_for_layer("layer2b"))
        assert "single_session_synthesize" not in result
        assert "plan_create" in result and "plan_refresh" in result and "race_week_brief" in result
        # 3A/3B do not depend on Layer 2B → not in policy
        assert result.isdisjoint(_LAYER3_BOTH_LABELS)

    def test_policy_layer2c_all_entry_points(self):
        assert set(policy_for_layer("layer2c")) == set(LAYER4_ENTRY_POINTS)

    def test_policy_layer2d_all_entry_points(self):
        assert set(policy_for_layer("layer2d")) == set(LAYER4_ENTRY_POINTS)

    def test_policy_layer2e_excludes_single_session(self):
        assert "single_session_synthesize" not in set(policy_for_layer("layer2e"))

    def test_policy_layer3a_includes_layer3b(self):
        result = set(policy_for_layer("layer3a"))
        assert result == set(LAYER4_ENTRY_POINTS) | {"llm_layer3b_goal_timeline_viability"}
        # 3A re-running does not invalidate its own prior row through this
        # policy (the new key naturally orphans the old row); cleanup is
        # deferred.
        assert "llm_layer3a_athlete_state" not in result

    def test_policy_layer3b_excludes_single_session(self):
        result = set(policy_for_layer("layer3b"))
        assert "single_session_synthesize" not in result
        # 3A does not depend on 3B
        assert result.isdisjoint(_LAYER3_BOTH_LABELS)

    def test_policy_etl_version_set_covers_layer4_and_layer3(self):
        assert (
            set(policy_for_layer("etl_version_set"))
            == set(LAYER4_ENTRY_POINTS) | _LAYER3_BOTH_LABELS
        )

    def test_policy_unknown_layer_raises(self):
        with pytest.raises(ValueError, match="unknown upstream layer"):
            policy_for_layer("layer99")  # type: ignore[arg-type]


class TestEvictOnLayerChange:
    def test_layer1_evicts_layer4_and_layer3_preserves_nl_parser(self):
        """Layer 1 change → evict 4 Layer 4 + both Layer 3 entry points;
        leave NL parser cache alone (NL parser is athlete-scoped, not
        Layer-1-dependent)."""
        cache = Layer4Cache(InMemoryCacheBackend())
        for ep in VALID_ENTRY_POINTS:
            cache.backend.put(
                cache_key=f"k-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json="{}",
            )
        count = evict_on_layer_change(cache, _USER_ID, "layer1")
        # 4 Layer 4 + 2 Layer 3 = 6; NL parser preserved
        assert count == 6
        assert cache.backend.get("k-nl_parser_parse_intent") is not None
        assert cache.backend.get("k-llm_layer3a_athlete_state") is None
        assert cache.backend.get("k-llm_layer3b_goal_timeline_viability") is None
        assert cache.metrics.evictions_per_layer == {"layer1": 6}

    def test_layer3a_change_evicts_layer3b_preserves_layer3a(self):
        """3A re-running invalidates 3B (3B depends on 3A); 3A's own prior
        row stays (orphans naturally via key change — out of policy scope)."""
        cache = Layer4Cache(InMemoryCacheBackend())
        for ep in VALID_ENTRY_POINTS:
            cache.backend.put(
                cache_key=f"k-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json="{}",
            )
        count = evict_on_layer_change(cache, _USER_ID, "layer3a")
        # 4 Layer 4 + 3B = 5; 3A's own row + NL parser preserved
        assert count == 5
        assert cache.backend.get("k-llm_layer3a_athlete_state") is not None
        assert cache.backend.get("k-llm_layer3b_goal_timeline_viability") is None
        assert cache.backend.get("k-nl_parser_parse_intent") is not None

    def test_layer2b_preserves_single_session(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        for ep in VALID_ENTRY_POINTS:
            cache.backend.put(
                cache_key=f"k-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json="{}",
            )
        count = evict_on_layer_change(cache, _USER_ID, "layer2b")
        # 4 entry points → 3 evicted (all except single_session_synthesize).
        assert count == 3
        assert cache.backend.get("k-single_session_synthesize") is not None

    def test_layer3b_preserves_single_session(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        for ep in VALID_ENTRY_POINTS:
            cache.backend.put(
                cache_key=f"k-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json="{}",
            )
        count = evict_on_layer_change(cache, _USER_ID, "layer3b")
        assert count == 3
        assert cache.backend.get("k-single_session_synthesize") is not None

    def test_unknown_layer_raises(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        with pytest.raises(ValueError, match="unknown upstream layer"):
            evict_on_layer_change(cache, _USER_ID, "layer99")  # type: ignore[arg-type]

    def test_scoped_to_user(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        cache.backend.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="plan_create", phase_name=None, payload_json="{}",
        )
        cache.backend.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=2, entry_point="plan_create", phase_name=None, payload_json="{}",
        )
        count = evict_on_layer_change(cache, 1, "layer1")
        assert count == 1
        assert cache.backend.get("k2") is not None  # different user untouched


class TestEvictOnMidnightRollover:
    def test_evicts_only_race_week_brief(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        for ep in VALID_ENTRY_POINTS:
            cache.backend.put(
                cache_key=f"k-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json="{}",
            )
        count = evict_on_midnight_rollover(cache)
        assert count == 1
        assert cache.backend.get("k-race_week_brief") is None
        assert cache.backend.get("k-plan_create") is not None

    def test_user_scoped_rollover(self):
        cache = Layer4Cache(InMemoryCacheBackend())
        cache.backend.put(
            cache_key="k1", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        cache.backend.put(
            cache_key="k2", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=2, entry_point="race_week_brief", phase_name=None, payload_json="{}",
        )
        count = evict_on_midnight_rollover(cache, user_id=1)
        assert count == 1
        assert cache.backend.get("k1") is None
        assert cache.backend.get("k2") is not None


# ─── Per-phase hashing helpers (§9.2) ────────────────────────────────────────


class TestPerPhaseHelpers:
    def test_compute_phase_cache_key_deterministic(self):
        k1 = compute_phase_cache_key(
            call_cache_key="callkey",
            phase_name="Base",
            phase_index=0,
            prev_accepted_output_hash=None,
        )
        k2 = compute_phase_cache_key(
            call_cache_key="callkey",
            phase_name="Base",
            phase_index=0,
            prev_accepted_output_hash=None,
        )
        assert k1 == k2

    def test_compute_phase_cache_key_chains(self):
        """Different prev_accepted_output_hash → different phase key."""
        k1 = compute_phase_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=1,
            prev_accepted_output_hash="aaa",
        )
        k2 = compute_phase_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=1,
            prev_accepted_output_hash="bbb",
        )
        assert k1 != k2

    def test_compute_phase_cache_key_first_phase_none_prev(self):
        """First phase passes None for prev_accepted_output_hash; collapses
        to '' in the concatenation."""
        k1 = compute_phase_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            prev_accepted_output_hash=None,
        )
        k2 = compute_phase_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            prev_accepted_output_hash="",
        )
        assert k1 == k2

    def test_compute_phase_cache_key_differs_by_index(self):
        k0 = compute_phase_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            prev_accepted_output_hash=None,
        )
        k1 = compute_phase_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=1,
            prev_accepted_output_hash=None,
        )
        assert k0 != k1

    def test_compute_phase_cache_key_differs_by_phase_name(self):
        k_a = compute_phase_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            prev_accepted_output_hash=None,
        )
        k_b = compute_phase_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=0,
            prev_accepted_output_hash=None,
        )
        assert k_a != k_b

    def test_compute_block_cache_key_deterministic(self):
        k1 = compute_block_cache_key(
            call_cache_key="callkey", phase_name="Base", phase_index=0,
            week_in_phase=1, prev_accepted_output_hash=None,
        )
        k2 = compute_block_cache_key(
            call_cache_key="callkey", phase_name="Base", phase_index=0,
            week_in_phase=1, prev_accepted_output_hash=None,
        )
        assert k1 == k2

    def test_compute_block_cache_key_differs_by_week(self):
        """D-77: two blocks of the same phase differ only by week_in_phase."""
        k_w1 = compute_block_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            week_in_phase=1, prev_accepted_output_hash=None,
        )
        k_w2 = compute_block_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            week_in_phase=2, prev_accepted_output_hash=None,
        )
        assert k_w1 != k_w2

    def test_compute_block_cache_key_chains(self):
        """Different prev_accepted_output_hash → different block key (the
        per-block chain: a change at week k invalidates k+1)."""
        k1 = compute_block_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=1,
            week_in_phase=2, prev_accepted_output_hash="aaa",
        )
        k2 = compute_block_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=1,
            week_in_phase=2, prev_accepted_output_hash="bbb",
        )
        assert k1 != k2

    def test_compute_block_cache_key_first_block_none_prev(self):
        """First block of the plan passes None; collapses to '' (deterministic
        against the call key alone)."""
        k1 = compute_block_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            week_in_phase=1, prev_accepted_output_hash=None,
        )
        k2 = compute_block_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            week_in_phase=1, prev_accepted_output_hash="",
        )
        assert k1 == k2

    def test_compute_block_cache_key_differs_from_phase_key(self):
        """A block key (with week_in_phase) is distinct from the legacy
        whole-phase key, so the two namespaces never collide on a cache row."""
        block = compute_block_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            week_in_phase=1, prev_accepted_output_hash=None,
        )
        phase = compute_phase_cache_key(
            call_cache_key="c", phase_name="Base", phase_index=0,
            prev_accepted_output_hash=None,
        )
        assert block != phase

    def test_seam_resynth_block_key_distinct_from_primary_block(self):
        """D-77 Slice 3: a seam-driven re-synth block for (phase, week) must NOT
        share a key with the ORIGINAL primary block at the same (phase, week) —
        else the re-synth would false-HIT the un-fixed cached sessions. The two
        rows are also stored under disjoint phase_idx, but the key itself must
        differ so a seam-constraint change invalidates the re-synth content."""
        from layer4.hashing import compute_seam_resynth_block_cache_key

        primary = compute_block_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=1,
            week_in_phase=1, prev_accepted_output_hash=None,
        )
        resynth = compute_seam_resynth_block_cache_key(
            call_cache_key="c", phase_name="Build", phase_index=1,
            week_in_phase=1, prev_accepted_output_hash=None,
            seam_index=0, seam_issues=["tighten the taper"],
            seam_direction="re_prompt_next",
        )
        assert primary != resynth

    def test_seam_resynth_block_key_differs_by_seam_and_issues(self):
        """Two seams targeting the same phase (re_prompt_next from seam i,
        re_prompt_prior from seam i+1), and the same seam with different issue
        text, must key distinctly so neither false-HITs the other."""
        from layer4.hashing import compute_seam_resynth_block_cache_key

        base = dict(
            call_cache_key="c", phase_name="Build", phase_index=1,
            week_in_phase=1, prev_accepted_output_hash=None,
            seam_issues=["a"], seam_direction="re_prompt_next",
        )
        k_seam0 = compute_seam_resynth_block_cache_key(seam_index=0, **base)
        k_seam1 = compute_seam_resynth_block_cache_key(seam_index=1, **base)
        assert k_seam0 != k_seam1

        diff_issues = {**base, "seam_issues": ["b"]}
        k_issue_b = compute_seam_resynth_block_cache_key(seam_index=0, **diff_issues)
        assert k_seam0 != k_issue_b

    def test_seam_resynth_block_key_deterministic_and_chains(self):
        from layer4.hashing import compute_seam_resynth_block_cache_key

        kw = dict(
            call_cache_key="c", phase_name="Build", phase_index=1,
            week_in_phase=2, seam_index=0, seam_issues=["a"],
            seam_direction="re_prompt_next",
        )
        assert compute_seam_resynth_block_cache_key(
            prev_accepted_output_hash="aaa", **kw
        ) == compute_seam_resynth_block_cache_key(
            prev_accepted_output_hash="aaa", **kw
        )
        # The re-synth's own blocks chain week-to-week.
        assert compute_seam_resynth_block_cache_key(
            prev_accepted_output_hash="aaa", **kw
        ) != compute_seam_resynth_block_cache_key(
            prev_accepted_output_hash="bbb", **kw
        )

    def test_seam_iter2_key_distinct_from_iter1(self):
        """#209: the iter-2 (re-synthesis-driven) seam review must key distinctly
        from the iter-1 review of the SAME seam + sessions — else the iter-2
        lookup would false-HIT the iter-1 verdict (or vice-versa)."""
        from layer4.hashing import (
            compute_seam_review_cache_key,
            compute_seam_review_iter2_cache_key,
        )

        prior = [_minimal_session(session_id="P-1")]
        nxt = [_minimal_session(session_id="N-1")]
        common = dict(
            call_cache_key="c", seam_index=0,
            prior_phase_sessions=prior, next_phase_sessions=nxt,
            model="claude-sonnet-4-6", max_tokens=4000,
            extended_thinking_budget=2000,
        )
        iter1 = compute_seam_review_cache_key(**common)
        iter2 = compute_seam_review_iter2_cache_key(
            prior_seam_issues=["Peak entry too aggressive"],
            seam_direction="re_prompt_next", **common,
        )
        assert iter1 != iter2

    def test_seam_iter2_key_differs_by_issues_and_direction(self):
        """The iter-1 issues threaded into the prompt + the re-prompt direction
        that drove the re-synthesis are prompt inputs, so a change in either must
        invalidate the cached iter-2 verdict."""
        from layer4.hashing import compute_seam_review_iter2_cache_key

        base = dict(
            call_cache_key="c", seam_index=0,
            prior_phase_sessions=[_minimal_session(session_id="P-1")],
            next_phase_sessions=[_minimal_session(session_id="N-1")],
            seam_direction="re_prompt_next",
            model="claude-sonnet-4-6", max_tokens=4000,
            extended_thinking_budget=2000,
        )
        k_a = compute_seam_review_iter2_cache_key(prior_seam_issues=["a"], **base)
        k_b = compute_seam_review_iter2_cache_key(prior_seam_issues=["b"], **base)
        assert k_a != k_b

        k_dir = compute_seam_review_iter2_cache_key(
            prior_seam_issues=["a"],
            **{**base, "seam_direction": "re_prompt_prior"},
        )
        assert k_a != k_dir

    def test_seam_iter2_key_deterministic(self):
        from layer4.hashing import compute_seam_review_iter2_cache_key

        kw = dict(
            call_cache_key="c", seam_index=1,
            prior_phase_sessions=[_minimal_session(session_id="P-1")],
            next_phase_sessions=[_minimal_session(session_id="N-1")],
            prior_seam_issues=["tighten the taper"],
            seam_direction="re_prompt_prior",
            model="claude-sonnet-4-6", max_tokens=4000,
            extended_thinking_budget=2000,
        )
        assert (
            compute_seam_review_iter2_cache_key(**kw)
            == compute_seam_review_iter2_cache_key(**kw)
        )

    def test_compute_accepted_output_hash_deterministic(self):
        session = _minimal_session()
        from layer4 import SynthesisMetadata

        synthesis_metadata = SynthesisMetadata(
            model="claude-sonnet-4-6",
            temperature=0.2,
            input_tokens=2000,
            output_tokens=1500,
            latency_ms=8000,
            retries_used=0,
            cap_hit=False,
        )
        h1 = compute_accepted_output_hash([session], synthesis_metadata)
        h2 = compute_accepted_output_hash([session], synthesis_metadata)
        assert h1 == h2

    def test_compute_accepted_output_hash_differentiates(self):
        from layer4 import SynthesisMetadata

        synth = SynthesisMetadata(
            model="claude-sonnet-4-6",
            temperature=0.2,
            input_tokens=2000,
            output_tokens=1500,
            latency_ms=8000,
            retries_used=0,
            cap_hit=False,
        )
        s1 = _minimal_session(session_id="S-a")
        s2 = _minimal_session(session_id="S-b")
        assert compute_accepted_output_hash([s1], synth) != compute_accepted_output_hash([s2], synth)


# ─── PostgresCacheBackend with a fake conn ───────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row: dict | None = None, rows: list[dict] | None = None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    """Stand-in for `database._PgConn` — captures every execute() call so we
    can assert on the SQL + params. Each `execute()` returns a configured
    `_FakeCursor`; the test sets up `.next_row` / `.next_rows` before calling
    backend methods. Commits are no-ops + counted.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.next_row: dict | None = None
        self.next_rows: list[dict] = []

    def execute(self, sql: str, params: tuple = ()) -> _FakeCursor:
        self.calls.append((sql, params))
        # Order matters: each test seeds next_row + next_rows in the order
        # the backend method invokes execute().
        cur = _FakeCursor(row=self.next_row, rows=self.next_rows)
        # Consume the row/rows after one read so a second execute doesn't
        # return the same one accidentally.
        self.next_row = None
        self.next_rows = []
        return cur

    def commit(self):
        self.commits += 1


class TestPostgresCacheBackend:
    def test_get_miss_returns_none(self):
        conn = _FakeConn()
        conn.next_row = None  # first execute returns nothing
        backend = PostgresCacheBackend(lambda: conn)
        entry = backend.get("k1")
        assert entry is None
        # Should have run one SELECT; no UPDATE bump since miss.
        assert len(conn.calls) == 1
        assert "SELECT" in conn.calls[0][0]

    def test_get_hit_bumps_hit_count(self):
        conn = _FakeConn()
        now = datetime(2026, 5, 18)
        conn.next_row = {
            "cache_key": "k1",
            "phase_idx": PER_ENTRY_PHASE_IDX_SENTINEL,
            "user_id": 1,
            "entry_point": "plan_create",
            "phase_name": None,
            "payload_json": {"a": 1},
            "created_at": now,
            "last_hit_at": now,
            "hit_count": 5,
        }
        backend = PostgresCacheBackend(lambda: conn)
        entry = backend.get("k1")
        assert entry is not None
        assert entry.hit_count == 6  # bumped to reflect the UPDATE
        # 2 calls: SELECT + UPDATE.
        assert len(conn.calls) == 2
        assert "UPDATE" in conn.calls[1][0]
        assert conn.commits == 1

    def test_put_upserts_via_on_conflict(self):
        conn = _FakeConn()
        backend = PostgresCacheBackend(lambda: conn)
        backend.put(
            cache_key="k1",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=1,
            entry_point="plan_create",
            phase_name=None,
            payload_json="{}",
        )
        assert "ON CONFLICT" in conn.calls[0][0]
        assert conn.commits == 1

    def test_put_rejects_unknown_entry_point(self):
        backend = PostgresCacheBackend(lambda: _FakeConn())
        with pytest.raises(ValueError, match="unknown entry_point"):
            backend.put(
                cache_key="k", phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=1, entry_point="bogus", phase_name=None, payload_json="{}",
            )

    def test_put_rejects_per_phase_without_phase_name(self):
        backend = PostgresCacheBackend(lambda: _FakeConn())
        with pytest.raises(ValueError, match="phase_name required"):
            backend.put(
                cache_key="k", phase_idx=0,
                user_id=1, entry_point="plan_create", phase_name=None, payload_json="{}",
            )

    def test_evict_for_user_unconditional(self):
        conn = _FakeConn()
        conn.next_row = {"deleted": 7}
        backend = PostgresCacheBackend(lambda: conn)
        count = backend.evict_for_user(1)
        assert count == 7

    def test_evict_for_user_with_entry_points(self):
        conn = _FakeConn()
        conn.next_row = {"deleted": 3}
        backend = PostgresCacheBackend(lambda: conn)
        count = backend.evict_for_user(1, entry_points=("plan_create", "plan_refresh"))
        assert count == 3
        # The query should mention IN with the right number of placeholders.
        sql = conn.calls[0][0]
        assert "entry_point IN" in sql

    def test_evict_entry_point_global(self):
        conn = _FakeConn()
        conn.next_row = {"deleted": 2}
        backend = PostgresCacheBackend(lambda: conn)
        count = backend.evict_entry_point("race_week_brief")
        assert count == 2

    def test_evict_entry_point_user_scoped(self):
        conn = _FakeConn()
        conn.next_row = {"deleted": 1}
        backend = PostgresCacheBackend(lambda: conn)
        count = backend.evict_entry_point("race_week_brief", user_id=42)
        assert count == 1
        sql, params = conn.calls[0]
        assert "user_id = ?" in sql
        assert params == ("race_week_brief", 42)

    def test_clear_all(self):
        conn = _FakeConn()
        conn.next_row = {"deleted": 99}
        backend = PostgresCacheBackend(lambda: conn)
        count = backend.clear_all()
        assert count == 99


# ─── Cached wrappers ─────────────────────────────────────────────────────────


# These tests verify that the cache wrappers correctly:
# (a) compute the cache key from the input payloads,
# (b) miss → invoke the underlying entry point,
# (c) hit → skip the entry point + rebind plan_version_id / suggestion_id.
#
# We stub the underlying entry-point function via monkeypatch so no real LLM
# calls or full fixture trees are needed. The stub records the call count +
# returns a minimal Layer4Payload built by the test helpers above.


def _minimal_plan_refresh_payload(plan_version_id: int = 1) -> Layer4Payload:
    from layer4 import RuleFailure, ValidatorResult

    return Layer4Payload(
        user_id=_USER_ID,
        mode="plan_refresh",
        plan_version_id=plan_version_id,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 6, 7),
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.4,
        pattern="B",
        latency_ms_total=5000,
        input_tokens_total=4500,
        output_tokens_total=1500,
        llm_call_count=1,
        etl_version_set={"layer0": "v7"},
        sessions=[],
        validator_results=[
            ValidatorResult(pass_index=0, accepted=True, rule_failures=[], retried_phase_names=[])
        ],
        notable_observations=[],
    )


class TestSingleSessionCachedWrapper:
    def _setup(self, monkeypatch):
        from layer4 import cached_wrappers as mod

        calls = {"n": 0}

        def fake_synth(*args, **kwargs):
            calls["n"] += 1
            return _minimal_single_session(
                plan_version_id=kwargs.get("plan_version_id", 0),
                suggestion_id=args[6],  # suggestion_id is positional 7th arg
            )

        monkeypatch.setattr(mod, "llm_layer4_single_session_synthesize", fake_synth)
        return calls

    def test_miss_then_hit_full_flow(self, monkeypatch):
        from layer4 import (
            SingleSessionRequest,
            llm_layer4_single_session_synthesize_cached,
        )

        calls = self._setup(monkeypatch)
        cache = Layer4Cache(InMemoryCacheBackend())

        # Build fixtures inline.
        # Use the test helpers already defined in this file's earlier fixture
        # references — they're at module scope so test_layer4_single_session
        # can be imported.
        from tests.test_layer4_single_session import _layer2c, _layer2d, _layer3a, _layer1

        request = SingleSessionRequest(
            sport="running",
            duration_min=60,
            intensity="easy",
            locale_slug="home_gym",
        )

        kwargs = dict(
            user_id=_USER_ID,
            request=request,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            etl_version_set={"layer0": "v7"},
            cache=cache,
            plan_version_id=1,
        )

        # First call: miss → synthesize.
        result1 = llm_layer4_single_session_synthesize_cached(
            **kwargs, suggestion_id=100
        )
        assert calls["n"] == 1
        assert result1.suggestion_id == 100
        assert cache.metrics.misses_total == 1
        assert cache.metrics.hits_total == 0

        # Second call with same inputs but DIFFERENT suggestion_id +
        # plan_version_id → hit + rebind.
        kwargs["plan_version_id"] = 999
        result2 = llm_layer4_single_session_synthesize_cached(
            **kwargs, suggestion_id=555
        )
        assert calls["n"] == 1  # not re-synthesized
        assert result2.plan_version_id == 999  # rebound
        assert result2.suggestion_id == 555  # rebound
        assert cache.metrics.hits_total == 1
        assert cache.metrics.misses_total == 1

    def test_different_inputs_different_keys(self, monkeypatch):
        from layer4 import (
            SingleSessionRequest,
            llm_layer4_single_session_synthesize_cached,
        )
        from tests.test_layer4_single_session import _layer2c, _layer2d, _layer3a, _layer1

        calls = self._setup(monkeypatch)
        cache = Layer4Cache(InMemoryCacheBackend())

        base = dict(
            user_id=_USER_ID,
            layer1_payload=_layer1(),
            layer2c_payload_for_locale=_layer2c(),
            layer2d_payload=_layer2d(),
            layer3a_payload=_layer3a(),
            suggestion_id=100,
            etl_version_set={"layer0": "v7"},
            cache=cache,
            plan_version_id=1,
        )
        r1 = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        r2 = SingleSessionRequest(
            sport="strength", duration_min=45, intensity="moderate",
            locale_slug="home_gym",
        )

        llm_layer4_single_session_synthesize_cached(request=r1, **base)
        llm_layer4_single_session_synthesize_cached(request=r2, **base)
        # Different request → different cache key → 2 misses.
        assert calls["n"] == 2
        assert cache.metrics.misses_total == 2
        assert cache.metrics.hits_total == 0


class TestLayer4CacheEntryPointConstraint:
    """Guards the 2026-05-26 drift fix: the layer4_cache `entry_point` CHECK
    constraint in init_db must list exactly `cache.VALID_ENTRY_POINTS`. The
    3A/3B + NL-parser cached wrappers reuse this table; when their entry_point
    labels were added to VALID_ENTRY_POINTS but not the DB constraint, every
    such cache write raised CheckViolation — an uncaught 500 in plan
    generation. The suite uses the in-memory backend (no constraint), so only
    this static check catches the mismatch."""

    @staticmethod
    def _entry_points_in(sql: str) -> set[str]:
        import re
        m = re.search(r"entry_point\s+IN\s*\(([^)]*)\)", sql)
        assert m is not None, f"no `entry_point IN (...)` clause in: {sql[:80]!r}"
        return set(re.findall(r"'([^']+)'", m.group(1)))

    def _constraint_sqls(self) -> list[str]:
        import init_db
        return [
            s
            for s in init_db._PG_MIGRATIONS
            if isinstance(s, str) and "layer4_cache" in s and "entry_point IN" in s
        ]

    def test_ddl_and_repair_migration_cover_valid_entry_points(self):
        sqls = self._constraint_sqls()
        # Both the CREATE TABLE DDL and the constraint-repair migration must be
        # present + must each match VALID_ENTRY_POINTS exactly.
        assert len(sqls) >= 2, (
            "expected the layer4_cache CREATE TABLE DDL + the constraint-repair "
            f"migration to both pin entry_point; found {len(sqls)}"
        )
        for sql in sqls:
            assert self._entry_points_in(sql) == set(VALID_ENTRY_POINTS)
