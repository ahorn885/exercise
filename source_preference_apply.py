"""Apply-side orchestration for a source-precedence pin change (#196 Phase 5, B2).

`source_preferences_repo` is pure storage — kept behaviour-inert since B1. This
module is the SIDE-EFFECT half: when an athlete sets / changes / clears a pin, the
affected canonical layer must be re-derived and the downstream caches evicted, so
the next plan / athlete-state read reflects the new precedence. The B4 picker route
calls this right after `source_preferences_repo.set/clear_source_preference`.

Wellness (B2): re-materialize the user's `canonical_daily_wellness` over every day
that carries wellness data — each multi-source day re-coalesces under the current
pin (most-complete primary, hard-pin override) — then evict the user's Layer-3A-
dependent Layer-4 + 3B caches. The Layer-3A cache entry itself needs no explicit
eviction: its key includes `integration_bundle_hash`, which is derived from
`canonical_daily_wellness`, so a re-materialized day natural-misses (Layer3A spec
§9.2). The downstream L4 / 3B rows are keyed on `layer3a_hash` and are cleared here
as hygiene so a stale plan/state isn't served before they natural-miss.

Cardio (B3): re-materialize every `canonical_activity` cluster the user owns — each
cluster re-picks its primary under the current pin (a copy from the pinned provider
when present, else most-complete) + per-field gap-fill — then evict the SAME Layer-3A-
dependent caches. The cardio merge feeds the 3A integration bundle too (recent-workouts
+ ACWR read `canonical_cardio_feed`, a view over `canonical_activity`), so a
re-materialized cluster natural-misses the 3A row via `integration_bundle_hash`.

Transaction: the re-materialize writes run in the caller's `db` transaction — the
caller commits. The cache backend is a separate store; its eviction is committed by
the backend. Re-materialize THEN evict (order is not load-bearing — the recompute
is lazy on the next read, by which point the caller has committed).

Design: `aidstation-sources/designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md`
(§5 cross-layer cache implication). The B4 picker route calls these right after
`source_preferences_repo.set/clear_source_preference`.
"""
from __future__ import annotations

from typing import Any

from canonical_wellness import backfill_canonical_wellness


def apply_wellness_pin_change(db: Any, cache: Any, uid: int) -> int:
    """Re-derive + evict after the wellness source pin for `uid` changed.

    Re-materializes the user's `canonical_daily_wellness` (idempotent; re-coalesces
    every day under the current pin) in the caller's transaction, then evicts the
    user's Layer-3A-dependent caches. Returns the evicted-row count. Caller commits
    `db`. Safe on a clear too (re-coalesce falls back to the automatic merge)."""
    # Lazy import keeps this module importable in the unit tests without dragging
    # in the Layer-4 cache backend until a real eviction is wired (B4).
    from layer4.cache_invalidation import evict_on_layer_change

    n_days = backfill_canonical_wellness(db, uid)
    evicted = evict_on_layer_change(cache, uid, "layer3a")
    print(  # Rule #15 — pin-change fan-out is diagnosable from /admin/logs
        f"[source-pref] user={uid} wellness pin applied: "
        f"re-materialized {n_days} day(s), evicted {evicted} cache row(s)"
    )
    return evicted


def apply_cardio_pin_change(db: Any, cache: Any, uid: int) -> int:
    """Re-derive + evict after the cardio source pin for `uid` changed.

    Re-materializes every `canonical_activity` cluster the user owns (idempotent;
    each cluster re-picks its primary under the current pin, then per-field gap-fill)
    in the caller's transaction, then evicts the user's Layer-3A-dependent caches.
    Returns the evicted-row count. Caller commits `db`. Safe on a clear too (the
    re-merge falls back to the automatic most-complete pick)."""
    # Lazy imports: routes.garmin pulls in the Flask blueprint graph, and the cache
    # backend isn't needed until B4 wires a real eviction — keep both off the module
    # import path (mirrors apply_wellness_pin_change).
    from layer4.cache_invalidation import evict_on_layer_change
    from routes.garmin import materialize_canonical_activity

    clusters = db.execute(
        "SELECT id FROM activity_clusters WHERE user_id = ?", (uid,)
    ).fetchall()
    for c in clusters:
        materialize_canonical_activity(db, uid, c["id"])
    evicted = evict_on_layer_change(cache, uid, "layer3a")
    print(  # Rule #15 — pin-change fan-out is diagnosable from /admin/logs
        f"[source-pref] user={uid} cardio pin applied: "
        f"re-materialized {len(clusters)} cluster(s), evicted {evicted} cache row(s)"
    )
    return evicted
