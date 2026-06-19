"""Tests for `layer3a/cached_wrapper.py` + `layer3b/cached_wrapper.py`.

Coverage:
- 3A wrapper hit/miss flow + cache key composition (day-granular `as_of`,
  user / hash / etl invariants, round-trip serialization).
- 3B wrapper hit/miss flow + cache key composition (event vs no-event
  mode, race_event_id discriminant, `current_date` granularity,
  `section_h2_kwargs` slot per D11).

Note on imports: `tests.test_layer4_orchestrator` is imported first to
force `layer4/__init__.py` to fully load before touching
`layer3a.cached_wrapper` directly — without this, the
`layer4/__init__.py` → `layer4.orchestrator` → `layer3a.cached_wrapper`
→ `layer3a.builder` → `layer4.context` chain triggers the pre-existing
circular import that blocks `tests/test_layer3a_builder.py` collection
(see predecessor handoff §4 "Pre-existing layer1/layer4 circular import").
The orchestrator test module is the canonical pattern for navigating
around this; reusing its fake-payload builders keeps the substrate
small.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest

# Pre-load layer4 to break the layer3a → layer4 → layer3a cycle (see header).
from layer4 import InMemoryCacheBackend

from layer3a.cached_wrapper import (
    layer3a_athlete_state_key,
    llm_layer3a_athlete_state_cached,
)
from layer3b.cached_wrapper import (
    layer3b_goal_timeline_viability_key,
    llm_layer3b_goal_timeline_viability_cached,
)
from layer4.context import (
    CombinedLoadReport,
    Layer3AIntegrationBundle,
    RaceEventPayload,
)

# Reuse fake-payload builders from the orchestrator test module rather than
# duplicating ~200 LOC of pydantic constructors.
from tests.test_layer4_orchestrator import (
    _fake_layer1_payload,
    _fake_layer2a_payload,
    _fake_layer3a_payload,
    _fake_layer3b_payload,
)


_USER_ID = 42
_TODAY = date(2026, 6, 1)
_AS_OF = datetime.combine(_TODAY, datetime.min.time())
_ETL = {"0A": "v7", "0B": "v7", "0C": "v7"}


def _make_integration_bundle() -> Layer3AIntegrationBundle:
    return Layer3AIntegrationBundle(
        as_of=_AS_OF,
        recent_workouts=[],
        recent_wellness=[],
        recent_self_report_sleep=[],
        combined_load=CombinedLoadReport(per_discipline={}, combined=None),
        connected_providers=[],
    )


def _make_race_event(*, race_event_id: int = 7) -> RaceEventPayload:
    return RaceEventPayload(
        race_event_id=race_event_id,
        user_id=_USER_ID,
        name="Test Race 2026",
        event_date=date(2026, 7, 18),
        race_format="continuous_multi_day",
        event_locale_id="home",
        event_locale_mapbox_id="poi.test_anchor",
        is_target_event=True,
    )


# ─── Layer 3A cached wrapper ────────────────────────────────────────────────


class TestLayer3ACachedWrapper:
    def test_miss_invokes_driver_then_hit_serves_cached(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            integration_bundle=_make_integration_bundle(),
            as_of=_AS_OF,
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        fake_payload = _fake_layer3a_payload()
        with patch(
            "layer3a.cached_wrapper.llm_layer3a_athlete_state",
            return_value=fake_payload,
        ) as driver:
            r1 = llm_layer3a_athlete_state_cached(**kwargs)
            r2 = llm_layer3a_athlete_state_cached(**kwargs)
        assert driver.call_count == 1
        assert r1.user_id == r2.user_id == _USER_ID
        assert (
            r1.current_state.aerobic_capacity.level
            == r2.current_state.aerobic_capacity.level
        )

    def test_day_granular_as_of_collapses_intraday_calls(self):
        backend = InMemoryCacheBackend()
        common = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            integration_bundle=_make_integration_bundle(),
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        with patch(
            "layer3a.cached_wrapper.llm_layer3a_athlete_state",
            return_value=_fake_layer3a_payload(),
        ) as driver:
            llm_layer3a_athlete_state_cached(
                as_of=datetime(2026, 6, 1, 0, 5), **common
            )
            llm_layer3a_athlete_state_cached(
                as_of=datetime(2026, 6, 1, 14, 30), **common
            )
        assert driver.call_count == 1

    def test_different_user_id_distinct_keys(self):
        common = dict(
            layer1_hash="h1",
            layer2a_hash="h2",
            integration_bundle_hash="h3",
            as_of=_AS_OF,
            etl_version_set=_ETL,
            model="claude-opus-4-7",
            temperature=0.0,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k_user_1 = layer3a_athlete_state_key(user_id=1, **common)
        k_user_2 = layer3a_athlete_state_key(user_id=2, **common)
        assert k_user_1 != k_user_2

    def test_different_layer1_hash_distinct_keys(self):
        common = dict(
            user_id=_USER_ID,
            layer2a_hash="h2",
            integration_bundle_hash="h3",
            as_of=_AS_OF,
            etl_version_set=_ETL,
            model="claude-opus-4-7",
            temperature=0.0,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k_a = layer3a_athlete_state_key(layer1_hash="abc", **common)
        k_b = layer3a_athlete_state_key(layer1_hash="def", **common)
        assert k_a != k_b

    def test_serialization_round_trip_preserves_payload(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            integration_bundle=_make_integration_bundle(),
            as_of=_AS_OF,
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        original = _fake_layer3a_payload()
        with patch(
            "layer3a.cached_wrapper.llm_layer3a_athlete_state",
            return_value=original,
        ):
            llm_layer3a_athlete_state_cached(**kwargs)  # warm cache
            hit = llm_layer3a_athlete_state_cached(**kwargs)  # round-trip
        assert hit.model_dump_json() == original.model_dump_json()

    def test_entry_point_label_stored_with_row(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            integration_bundle=_make_integration_bundle(),
            as_of=_AS_OF,
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        with patch(
            "layer3a.cached_wrapper.llm_layer3a_athlete_state",
            return_value=_fake_layer3a_payload(),
        ):
            llm_layer3a_athlete_state_cached(**kwargs)
        # cache row should be stored under the 3A entry_point label so the
        # extended _EVICTION_POLICY routes correctly
        all_rows = list(backend._rows.values())
        assert len(all_rows) == 1
        assert all_rows[0].entry_point == "llm_layer3a_athlete_state"


# ─── Layer 3B cached wrapper ────────────────────────────────────────────────


class TestLayer3BCachedWrapper:
    def test_miss_invokes_driver_then_hit_serves_cached(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer3a_payload=_fake_layer3a_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            race_event_payload=_make_race_event(),
            current_date=_TODAY,
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        with patch(
            "layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability",
            return_value=_fake_layer3b_payload(),
        ) as driver:
            r1 = llm_layer3b_goal_timeline_viability_cached(**kwargs)
            r2 = llm_layer3b_goal_timeline_viability_cached(**kwargs)
        assert driver.call_count == 1
        assert r1.user_id == r2.user_id == _USER_ID
        assert r1.periodization_shape.start_phase == r2.periodization_shape.start_phase

    def test_event_mode_defaults_goal_outcome_to_finish_when_omitted(self):
        # Regression: the orchestrator's shared full cone (race_week_brief /
        # plan_refresh / plan_create) calls this wrapper in event-mode WITHOUT
        # goal_outcome. 3B's event-mode _validate_inputs hard-requires one, so
        # the omission raised Layer3BInputError("event_mode_missing_goal_outcome")
        # — which escaped the route's *OutputError-only catch and surfaced to
        # the athlete as "Plan generation failed unexpectedly". The wrapper now
        # back-fills the conservative "Finish" tier.
        backend = InMemoryCacheBackend()
        with patch(
            "layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability",
            return_value=_fake_layer3b_payload(),
        ) as driver:
            llm_layer3b_goal_timeline_viability_cached(
                user_id=_USER_ID,
                layer1_payload=_fake_layer1_payload(),
                layer3a_payload=_fake_layer3a_payload(),
                layer2a_payload=_fake_layer2a_payload(),
                race_event_payload=_make_race_event(),
                current_date=_TODAY,
                etl_version_set=_ETL,
                cache_backend=backend,
            )
        assert driver.call_args.kwargs["goal_outcome"] == "Finish"

    def test_event_mode_preserves_explicit_goal_outcome(self):
        # An explicitly supplied goal_outcome must NOT be clobbered by the
        # deployed-shape-gap default.
        backend = InMemoryCacheBackend()
        with patch(
            "layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability",
            return_value=_fake_layer3b_payload(),
        ) as driver:
            llm_layer3b_goal_timeline_viability_cached(
                user_id=_USER_ID,
                layer1_payload=_fake_layer1_payload(),
                layer3a_payload=_fake_layer3a_payload(),
                layer2a_payload=_fake_layer2a_payload(),
                race_event_payload=_make_race_event(),
                current_date=_TODAY,
                etl_version_set=_ETL,
                cache_backend=backend,
                goal_outcome="Podium",
            )
        assert driver.call_args.kwargs["goal_outcome"] == "Podium"

    def test_event_vs_no_event_distinct_keys(self):
        common = dict(
            user_id=_USER_ID,
            layer1_hash="h1",
            layer3a_hash="h3a",
            layer2a_hash="h2a",
            current_date=_TODAY,
            non_event_goal_type=None,
            etl_version_set=_ETL,
            section_h2_kwargs=None,
            model="claude-opus-4-7",
            temperature=0.0,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k_event = layer3b_goal_timeline_viability_key(race_event_id=7, **common)
        k_no_event = layer3b_goal_timeline_viability_key(race_event_id=None, **common)
        assert k_event != k_no_event

    def test_different_race_event_id_distinct_keys(self):
        common = dict(
            user_id=_USER_ID,
            layer1_hash="h1",
            layer3a_hash="h3a",
            layer2a_hash="h2a",
            current_date=_TODAY,
            non_event_goal_type=None,
            etl_version_set=_ETL,
            section_h2_kwargs=None,
            model="claude-opus-4-7",
            temperature=0.0,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k_7 = layer3b_goal_timeline_viability_key(race_event_id=7, **common)
        k_8 = layer3b_goal_timeline_viability_key(race_event_id=8, **common)
        assert k_7 != k_8

    def test_section_h2_kwargs_distinct_keys(self):
        common = dict(
            user_id=_USER_ID,
            layer1_hash="h1",
            layer3a_hash="h3a",
            layer2a_hash="h2a",
            race_event_id=7,
            current_date=_TODAY,
            non_event_goal_type=None,
            etl_version_set=_ETL,
            model="claude-opus-4-7",
            temperature=0.0,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k_empty = layer3b_goal_timeline_viability_key(section_h2_kwargs=None, **common)
        k_populated = layer3b_goal_timeline_viability_key(
            section_h2_kwargs={"goal_outcome": "podium"}, **common
        )
        assert k_empty != k_populated

    def test_current_date_distinct_keys(self):
        common = dict(
            user_id=_USER_ID,
            layer1_hash="h1",
            layer3a_hash="h3a",
            layer2a_hash="h2a",
            race_event_id=7,
            non_event_goal_type=None,
            etl_version_set=_ETL,
            section_h2_kwargs=None,
            model="claude-opus-4-7",
            temperature=0.0,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k_today = layer3b_goal_timeline_viability_key(current_date=_TODAY, **common)
        k_tomorrow = layer3b_goal_timeline_viability_key(
            current_date=date(2026, 6, 2), **common
        )
        assert k_today != k_tomorrow

    def test_serialization_round_trip_preserves_payload(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer3a_payload=_fake_layer3a_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            race_event_payload=_make_race_event(),
            current_date=_TODAY,
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        original = _fake_layer3b_payload()
        with patch(
            "layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability",
            return_value=original,
        ):
            llm_layer3b_goal_timeline_viability_cached(**kwargs)  # warm cache
            hit = llm_layer3b_goal_timeline_viability_cached(**kwargs)  # round-trip
        assert hit.model_dump_json() == original.model_dump_json()

    def test_entry_point_label_stored_with_row(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=_USER_ID,
            layer1_payload=_fake_layer1_payload(),
            layer3a_payload=_fake_layer3a_payload(),
            layer2a_payload=_fake_layer2a_payload(),
            race_event_payload=_make_race_event(),
            current_date=_TODAY,
            etl_version_set=_ETL,
            cache_backend=backend,
        )
        with patch(
            "layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability",
            return_value=_fake_layer3b_payload(),
        ):
            llm_layer3b_goal_timeline_viability_cached(**kwargs)
        all_rows = list(backend._rows.values())
        assert len(all_rows) == 1
        assert all_rows[0].entry_point == "llm_layer3b_goal_timeline_viability"
