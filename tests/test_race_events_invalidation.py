"""Tests for `race_events_invalidation.py` D-66 §9 cache eviction helpers.

Each helper builds (or accepts) a `Layer4Cache` and routes the §9
invalidation matrix entry to the right backend primitive. Tests use the
in-memory backend so the routing is observable without a real DB.

Coverage:
- Each helper evicts the expected entry-point set for the user.
- Each helper leaves other users' cache rows untouched.
- Each helper accepts an injected cache via `cache=` kwarg (tests path).
- The default-cache builder produces a working `Layer4Cache` against a
  fake db_conn_factory shape — verified via monkeypatching to avoid
  importing the real psycopg2-backed `PostgresCacheBackend` codepath.
"""

from __future__ import annotations

import pytest

from layer4.cache import (
    PER_ENTRY_PHASE_IDX_SENTINEL,
    InMemoryCacheBackend,
    Layer4Cache,
)
from race_events_invalidation import (
    _build_default_cache,
    evict_on_target_event_brief_field_change,
    evict_on_target_event_framework_sport_change,
    evict_on_target_event_included_discipline_ids_change,
    evict_on_target_event_locale_change,
    evict_on_target_event_periodization_change,
)


_USER_ID = 42
_OTHER_USER_ID = 99


def _seed_all_entry_points(backend: InMemoryCacheBackend, user_id: int) -> None:
    """Put one row per entry_point for `user_id` so eviction is observable."""
    for ep in (
        "plan_create",
        "plan_refresh",
        "single_session_synthesize",
        "race_week_brief",
    ):
        backend.put(
            cache_key=f"k-{user_id}-{ep}",
            phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
            user_id=user_id,
            entry_point=ep,
            phase_name=None,
            payload_json='{"seed": true}',
        )


def _remaining_entry_points(backend: InMemoryCacheBackend, user_id: int) -> set[str]:
    """Set of entry_points that still have a row for `user_id`."""
    found: set[str] = set()
    for (_key, _phase_idx), entry in backend._rows.items():  # noqa: SLF001
        if entry.user_id == user_id:
            found.add(entry.entry_point)
    return found


# ─── evict_on_target_event_periodization_change ─────────────────────────────


class TestPeriodizationChange:
    def test_evicts_plan_create_plan_refresh_race_week_brief_preserves_single_session(self):
        """layer3b policy = _NON_SINGLE_SESSION. single_session stays."""
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        count = evict_on_target_event_periodization_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert count == 3
        assert _remaining_entry_points(backend, _USER_ID) == {
            "single_session_synthesize",
        }

    def test_returns_zero_when_no_user_rows(self):
        backend = InMemoryCacheBackend()
        cache = Layer4Cache(backend)
        count = evict_on_target_event_periodization_change(
            db=None, user_id=_USER_ID, cache=cache
        )
        assert count == 0

    def test_scoped_to_user(self):
        """Other users' rows survive."""
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        _seed_all_entry_points(backend, _OTHER_USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_periodization_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert _remaining_entry_points(backend, _OTHER_USER_ID) == {
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        }

    def test_metrics_tagged_with_layer3b(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_periodization_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        # Routes through evict_on_layer_change(cache, uid, 'layer3b') so
        # metrics record the eviction tagged by the upstream-layer label.
        assert cache.metrics.evictions_per_layer.get("layer3b") == 3


# ─── evict_on_target_event_brief_field_change ───────────────────────────────


class TestBriefFieldChange:
    def test_evicts_race_week_brief_only(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        count = evict_on_target_event_brief_field_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert count == 1
        assert _remaining_entry_points(backend, _USER_ID) == {
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
        }

    def test_returns_zero_when_no_brief_rows(self):
        backend = InMemoryCacheBackend()
        # Seed everything EXCEPT race_week_brief.
        for ep in ("plan_create", "plan_refresh", "single_session_synthesize"):
            backend.put(
                cache_key=f"k-{ep}",
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=_USER_ID,
                entry_point=ep,
                phase_name=None,
                payload_json="{}",
            )
        cache = Layer4Cache(backend)

        count = evict_on_target_event_brief_field_change(
            db=None, user_id=_USER_ID, cache=cache
        )
        assert count == 0

    def test_scoped_to_user(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        _seed_all_entry_points(backend, _OTHER_USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_brief_field_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert _remaining_entry_points(backend, _OTHER_USER_ID) == {
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        }

    def test_metrics_tagged_with_brief_field_label(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_brief_field_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert cache.metrics.evictions_per_layer.get("race_events_brief_field") == 1


# ─── evict_on_target_event_locale_change ────────────────────────────────────


class TestLocaleChange:
    def test_evicts_all_four_entry_points(self):
        """layer2c policy = _ALL_ENTRY_POINTS — broadest of the three helpers."""
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        count = evict_on_target_event_locale_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert count == 4
        assert _remaining_entry_points(backend, _USER_ID) == set()

    def test_scoped_to_user(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        _seed_all_entry_points(backend, _OTHER_USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_locale_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert _remaining_entry_points(backend, _OTHER_USER_ID) == {
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        }

    def test_metrics_tagged_with_layer2c(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_locale_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert cache.metrics.evictions_per_layer.get("layer2c") == 4


# ─── evict_on_target_event_framework_sport_change ───────────────────────────


class TestFrameworkSportChange:
    """D-73 Phase 5.2 Bucket E.(b) — framework_sport override change on
    the target row routes through `layer2a` policy, the widest cut
    (all 4 entry points + Layer 3A/3B caches).
    """

    def test_evicts_all_four_entry_points(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        count = evict_on_target_event_framework_sport_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert count == 4
        assert _remaining_entry_points(backend, _USER_ID) == set()

    def test_scoped_to_user(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        _seed_all_entry_points(backend, _OTHER_USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_framework_sport_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert _remaining_entry_points(backend, _OTHER_USER_ID) == {
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        }

    def test_metrics_tagged_with_layer2a(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_framework_sport_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert cache.metrics.evictions_per_layer.get("layer2a") == 4


# ─── evict_on_target_event_included_discipline_ids_change ──────────────────


class TestIncludedDisciplineIdsChange:
    """D-73 Phase 5.2 Bucket E.(b)-B2 — `included_discipline_ids` override
    change on the target row uses the same `layer2a` policy as
    framework_sport: both reshape Layer 2A's discipline output, cascading
    through all 4 entry points + Layer 3A/3B caches.
    """

    def test_evicts_all_four_entry_points(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        count = evict_on_target_event_included_discipline_ids_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert count == 4
        assert _remaining_entry_points(backend, _USER_ID) == set()

    def test_scoped_to_user(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        _seed_all_entry_points(backend, _OTHER_USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_included_discipline_ids_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert _remaining_entry_points(backend, _OTHER_USER_ID) == {
            "plan_create",
            "plan_refresh",
            "single_session_synthesize",
            "race_week_brief",
        }

    def test_metrics_tagged_with_layer2a(self):
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        cache = Layer4Cache(backend)

        evict_on_target_event_included_discipline_ids_change(
            db=None, user_id=_USER_ID, cache=cache
        )

        assert cache.metrics.evictions_per_layer.get("layer2a") == 4


# ─── Default-cache builder ──────────────────────────────────────────────────


class TestBuildDefaultCache:
    def test_builds_layer4cache_wrapping_postgres_backend(self):
        """Verifies the production path constructs a usable Layer4Cache
        wrapping a `PostgresCacheBackend` over the request-scoped db.
        The factory closure captures `db` so each backend op routes
        through that connection."""
        from layer4.cache_postgres import PostgresCacheBackend

        sentinel_db = object()
        cache = _build_default_cache(sentinel_db)

        assert isinstance(cache, Layer4Cache)
        assert isinstance(cache.backend, PostgresCacheBackend)

    def test_helpers_default_to_built_cache_when_kwarg_omitted(self, monkeypatch):
        """When `cache=None`, the helper invokes `_build_default_cache(db)`
        with the passed db. We monkeypatch the builder to capture the
        call + return an in-memory cache, then verify the helper used it.
        """
        backend = InMemoryCacheBackend()
        _seed_all_entry_points(backend, _USER_ID)
        injected_cache = Layer4Cache(backend)
        captured: dict = {}

        def fake_builder(db):
            captured["db"] = db
            return injected_cache

        monkeypatch.setattr(
            "race_events_invalidation._build_default_cache",
            fake_builder,
        )

        sentinel_db = object()
        evict_on_target_event_periodization_change(
            db=sentinel_db, user_id=_USER_ID
        )

        assert captured["db"] is sentinel_db
        # periodization eviction left only single_session standing.
        assert _remaining_entry_points(backend, _USER_ID) == {
            "single_session_synthesize",
        }
