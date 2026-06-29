"""Tests for `source_preference_apply.apply_wellness_pin_change` (#196 P5 B2).

The apply helper is the side-effect half of a pin change: re-materialize the
user's `canonical_daily_wellness` (idempotent backfill scope), then evict the
user's Layer-3A-dependent caches. A fake db serves the backfill discovery union +
a no-data materialize per target; a fake cache captures the eviction. No live
Postgres / cache backend (egress is blocked in the container).
"""
from __future__ import annotations

import source_preference_apply as spa


class _Cursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return None


class _FakeDb:
    """Serves the backfill discovery UNION, then a no-data materialize per target
    (so each target clears rather than upserts). Records the (uid, date) pairs
    materialize ran for, via the daily_wellness_metrics read params."""

    def __init__(self, targets):
        self.targets = targets
        self.materialized: list[tuple[int, str]] = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "UNION" in s:                       # backfill discovery work-list
            return _Cursor(rows=[{"user_id": u, "date": d} for u, d in self.targets])
        if "FROM daily_wellness_metrics" in s:
            self.materialized.append((params[0], params[1]))
            return _Cursor()                   # fetchone() -> None -> no-data path
        return _Cursor()                       # prr read / DELETE canonical / pref read


class _FakeCache:
    """Captures `invalidate_user` calls (the eviction primitive
    `evict_on_layer_change` composes)."""

    def __init__(self, evicted=3):
        self.evicted = evicted
        self.invalidations: list[tuple] = []

    def invalidate_user(self, user_id, layer=None, entry_points=None):
        self.invalidations.append((user_id, layer, entry_points))
        return self.evicted


def test_apply_rematerializes_user_and_evicts_layer3a():
    db = _FakeDb([(7, "2026-06-20"), (7, "2026-06-21")])
    cache = _FakeCache(evicted=5)
    n = spa.apply_wellness_pin_change(db, cache, 7)

    # Re-materialized exactly the user's wellness days.
    assert db.materialized == [(7, "2026-06-20"), (7, "2026-06-21")]
    # Evicted the user's Layer-3A-dependent caches, returning the backend count.
    assert n == 5
    assert len(cache.invalidations) == 1
    uid, layer, _entry_points = cache.invalidations[0]
    assert uid == 7
    assert layer == "layer3a"


def test_apply_is_user_scoped():
    # Discovery is filtered to the one user (backfill passes uid through); the
    # eviction is the same user. A second user's rows are never touched.
    db = _FakeDb([(42, "2026-06-20")])
    cache = _FakeCache()
    spa.apply_wellness_pin_change(db, cache, 42)
    assert db.materialized == [(42, "2026-06-20")]
    assert cache.invalidations[0][0] == 42


class _FakeCardioDb:
    """Serves the cluster discovery, then a no-member materialize per cluster (so
    each clears rather than upserts). Records the cluster ids materialize ran for,
    via the `cardio_log WHERE cluster_id` read params."""

    def __init__(self, cluster_ids):
        self.cluster_ids = cluster_ids
        self.materialized: list[int] = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM activity_clusters WHERE user_id" in s:   # discovery work-list
            return _Cursor(rows=[{"id": cid} for cid in self.cluster_ids])
        if "FROM cardio_log WHERE cluster_id" in s:
            self.materialized.append(params[0])
            return _Cursor()                              # fetchall() -> [] -> clear path
        return _Cursor()                                  # pin read / DELETE canonical


def test_apply_cardio_rematerializes_user_clusters_and_evicts_layer3a():
    db = _FakeCardioDb([11, 12, 13])
    cache = _FakeCache(evicted=4)
    n = spa.apply_cardio_pin_change(db, cache, 7)

    # Re-materialized exactly the user's clusters.
    assert db.materialized == [11, 12, 13]
    # Evicted the user's Layer-3A-dependent caches, returning the backend count.
    assert n == 4
    assert len(cache.invalidations) == 1
    uid, layer, _entry_points = cache.invalidations[0]
    assert uid == 7
    assert layer == "layer3a"


def test_apply_cardio_is_user_scoped():
    # Discovery is filtered to the one user (WHERE user_id); the eviction is the
    # same user. A second user's clusters are never touched.
    db = _FakeCardioDb([21])
    cache = _FakeCache()
    spa.apply_cardio_pin_change(db, cache, 42)
    assert db.materialized == [21]
    assert cache.invalidations[0][0] == 42
