"""Layer 4 cache invalidation hooks for race-event writes (D-66 §7.4 + §9).

Wires the writer-side surfaces in `routes/race_events.py` +
`routes/onboarding.py` (Step 3c target-race + Step 3d route-locales) into
the Layer 4 cache facade shipped in Step 5. The §9 invalidation matrix
maps each edit type on `race_events` / `race_route_locales` /
`race_route_locale_equipment` to the set of Layer 4 entry-point caches
that consume the affected fields:

| Edit type                                          | Helper                                           | Underlying eviction                                  |
|----------------------------------------------------|--------------------------------------------------|------------------------------------------------------|
| Target-flag flip / target-row event_date /         | `evict_on_target_event_periodization_change()`   | `evict_on_layer_change(cache, uid, 'layer3b')` —     |
| target-row race_format / target-row deletion       |                                                  | _NON_SINGLE_SESSION = plan_create + plan_refresh +   |
|                                                    |                                                  | race_week_brief (the periodization-grade set)        |
| Brief-only fields on target row (distance_km /     | `evict_on_target_event_brief_field_change()`     | `cache.invalidate_entry_point('race_week_brief')` —  |
| total_elevation_gain_m / race_rules_summary /      |                                                  | narrowest cut; only the brief reads these fields     |
| mandatory_gear_text / notes) + route_locales CRUD  |                                                  |                                                      |
| + route_locale_equipment CRUD on target race       |                                                  |                                                      |
| Any edit on a non-target race_events row           | (no helper — writer skips the call)              | No invalidation; race not in scope of any plan       |

Non-target edits (e.g., updating a future race that is not the athlete's
current target) emit no invalidation per the §9 matrix's final row.
Writers determine the target-vs-non-target state via the
`race_events_repo.get_race_event(db, uid, race_event_id)['is_target_event']`
field they already read for ownership.

Cache lifecycle: Vercel is stateless serverless, so each request gets a
fresh process. Each helper builds a transient `Layer4Cache` wrapping a
`PostgresCacheBackend` over the current Flask request-scoped `db`. Tests
inject a pre-built `Layer4Cache` (typically an `InMemoryCacheBackend`
fake) via the `cache=` keyword and skip the Postgres construction.

Return values are the count of evicted rows (so callers can record
observability events; currently no caller reads them, but matches the
shape of `cache_invalidation.evict_on_layer_change()`).
"""

from __future__ import annotations

from layer4.cache import Layer4Cache
from layer4.cache_invalidation import evict_on_layer_change
from layer4.cache_postgres import PostgresCacheBackend


def _build_default_cache(db) -> Layer4Cache:
    """Build a transient cache wrapping the current request-scoped `db`.

    Each helper invocation builds a fresh `Layer4Cache` for production
    use (Vercel = stateless; no shared instance across requests). Tests
    bypass this by passing a pre-built `cache=` kwarg.
    """
    return Layer4Cache(PostgresCacheBackend(lambda: db))


def evict_on_target_event_periodization_change(
    db,
    user_id: int,
    *,
    cache: Layer4Cache | None = None,
) -> int:
    """Target-flag flip, target-row `event_date`/`race_format` change, or
    target-row deletion. Re-uses the `layer3b` policy
    (`_NON_SINGLE_SESSION`) since these edits change Layer 3B's input
    set — periodization shape, time_to_event_weeks, mode flip.
    """
    if cache is None:
        cache = _build_default_cache(db)
    return evict_on_layer_change(cache, user_id, 'layer3b')


def evict_on_target_event_brief_field_change(
    db,
    user_id: int,
    *,
    cache: Layer4Cache | None = None,
) -> int:
    """Brief-rendering-only field change on the target row, or any
    route_locales / route_locale_equipment CRUD on the target race. Only
    the race-week brief reads these fields per design §9; the periodization
    chain (3B → plan_create / plan_refresh) is unaffected.
    """
    if cache is None:
        cache = _build_default_cache(db)
    return cache.invalidate_entry_point(
        'race_week_brief',
        layer='race_events_brief_field',
        user_id=user_id,
    )


def evict_on_target_event_framework_sport_change(
    db,
    user_id: int,
    *,
    cache: Layer4Cache | None = None,
) -> int:
    """`framework_sport` change on the target row (D-73 Phase 5.2 Bucket
    E.(b)). Re-uses the `layer2a` policy — the override flips which
    disciplines + classifier output Layer 2A returns, which cascades
    through every downstream entry point + Layer 3A/3B.
    """
    if cache is None:
        cache = _build_default_cache(db)
    return evict_on_layer_change(cache, user_id, 'layer2a')


def evict_on_target_event_included_discipline_ids_change(
    db,
    user_id: int,
    *,
    cache: Layer4Cache | None = None,
) -> int:
    """`included_discipline_ids` change on the target row (D-73 Phase 5.2
    Bucket E.(b)-B2). Re-uses the `layer2a` policy — the filter narrows
    which disciplines Layer 2A returns, which cascades through every
    downstream entry point + Layer 3A/3B. Same policy as framework_sport
    since both reshape the discipline input to the same layer.
    """
    if cache is None:
        cache = _build_default_cache(db)
    return evict_on_layer_change(cache, user_id, 'layer2a')
