"""Layer 4 orchestrator — Phase 5.1 race_week_brief vertical slice.

First end-to-end composition of the v2 upstream pipeline. Drives:

    Layer 1 → Layer 2A/2B/2D/2C → Layer 3A → Layer 3B → Layer 2E →
    llm_layer4_race_week_brief_cached

See `Upstream_Implementation_Plan_v1.md` §4 row 5.1 + `Layer4_Spec.md` §4.5
for the entry-point contract; this module is the orchestrator-side composer
that all five Layer 4 entry points will eventually share substrate with
(Phase 5.2 extracts the shared upstream-pipeline helper once
`single_session_synthesize` + `plan_refresh` tiers land).

Vertical-slice limitations carried as forward-pointers:
- Layer 2B `race_terrain` + `locale_terrain_ids` are empty until §H.2
  race-terrain capture form ships (L3B-P-2 deployed-shape gap). Brief
  still ships; Layer 2B surfaces a coaching flag.
- `prior_plan_session_window` is empty until v2 plan-gen lands (Phase 5.2
  will wire `plan_create`/`plan_refresh` into the same orchestrator).
- `plan_version_id` is hardcoded `1` pending the plan-versioning surface.
- Layer 3A + Layer 3B run uncached at the orchestrator level. The Layer 4
  cache (race_week_brief key) sits in front of the whole pipeline, so a
  cache hit short-circuits both. Upstream caching becomes load-bearing
  only when multiple Layer 4 entry points share user-scoped 3A/3B outputs.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from layer1.builder import build_layer1_payload
from layer2a.builder import q_layer2a_discipline_classifier_payload
from layer2b.builder import q_layer2b_terrain_classifier_payload
from layer2c.builder import q_layer2c_equipment_mapper_payload
from layer2d.builder import q_layer2d_injury_risk_profile_payload
from layer2e.builder import q_layer2e_nutrition_baseline_payload
from layer3a.builder import llm_layer3a_athlete_state
from layer3a.integration import assemble_layer3a_integration_bundle
from layer3b.builder import llm_layer3b_goal_timeline_viability
from layer4.cache import Layer4Cache
from layer4.cached_wrappers import llm_layer4_race_week_brief_cached
from layer4.context import Layer2ETargetEvent
from layer4.payload import Layer4Payload
from race_events_repo import load_target_race_event_payload


_AUTO_FIRE_DAYS_TO_EVENT_MAX = 14

# TODO(plan-versioning): replace once the v2 plan-versioning surface lands;
# every cache row currently keys on plan_version_id=1 for race-week-brief.
_RACE_WEEK_BRIEF_PLAN_VERSION_ID_PLACEHOLDER = 1

# Coarse race-format-based duration estimate for Layer 2E's TargetEvent
# (estimated_duration_hr > 0 is required). When the §H.2 race-terrain
# capture form ships with a per-race duration field, source from there.
_DURATION_HR_BY_RACE_FORMAT: dict[str, float] = {
    "single_day": 8.0,
    "stage_race": 24.0,
    "multi_day_ultra": 24.0,
    "expedition_ar": 56.0,
}


class OrchestrationError(RuntimeError):
    """Pre-flight / upstream-discovery error before any LLM call.

    Distinct from `Layer4InputError` (Layer-4-internal preconditions raised
    by `llm_layer4_race_week_brief`'s `_validate_inputs`); `OrchestrationError`
    surfaces when the orchestrator's own composition cannot proceed — no
    target race, no primary locale, etl_version_set undiscoverable,
    out-of-window auto-fire, etc.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def orchestrate_race_week_brief(
    db: Any,
    user_id: int,
    *,
    cache: Layer4Cache,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end race_week_brief pipeline for `user_id`.

    Algorithm:
    1. Load target race event; raise `OrchestrationError('no_target_event')`
       when the athlete has no `is_target_event=true` race row.
    2. Pre-flight auto-fire gate: raise
       `OrchestrationError('race_week_brief_too_early')` when
       `days_to_event > 14`. This is a cheap optimization that saves the
       3A + 3B LLM calls on out-of-window invocations; `_validate_inputs`
       in `llm_layer4_race_week_brief` will also reject the same case.
    3. Discover the active `etl_version_set` triplet from Layer 0.
    4. Build upstream payloads in dependency order: Layer 1 → 2A → 2B →
       2D → 2C → 3A → 3B → 2E → race_week_brief. Layer 2E runs after 3B
       because it consumes `start_phase` from 3B's `periodization_shape`.
    5. Compose via `llm_layer4_race_week_brief_cached` — the Layer 4
       per-entry-point cache sits in front of the synthesizer call.

    Failures from any upstream layer propagate verbatim; the orchestrator
    does not try/except them. Layer-3A / Layer-3B LLM failures surface as
    their respective driver errors; Layer 4 validator failures surface as
    `Layer4OutputError` or `Layer4InputError`.
    """
    if today is None:
        today = date.today()

    race_event = load_target_race_event_payload(db, user_id)
    if race_event is None:
        raise OrchestrationError(
            "no_target_event",
            f"user_id={user_id} has no race_events row with is_target_event=true",
        )

    days_to_event = (race_event.event_date - today).days
    if days_to_event > _AUTO_FIRE_DAYS_TO_EVENT_MAX:
        raise OrchestrationError(
            "race_week_brief_too_early",
            f"days_to_event={days_to_event} > {_AUTO_FIRE_DAYS_TO_EVENT_MAX}",
        )

    etl_version_set = _q_current_etl_version_set(db)
    as_of = datetime.combine(today, time.min)

    layer1_payload = build_layer1_payload(db, user_id)
    framework_sport = layer1_payload.identity.primary_sport
    if not framework_sport:
        raise OrchestrationError(
            "framework_sport_missing",
            f"layer1.identity.primary_sport is empty for user_id={user_id}",
        )

    layer2a_payload = q_layer2a_discipline_classifier_payload(
        db,
        framework_sport=framework_sport,
        etl_version_set=etl_version_set,
    )
    included_discipline_ids = [
        d.discipline_id
        for d in layer2a_payload.disciplines
        if d.inclusion == "included"
    ]

    layer2b_payload = q_layer2b_terrain_classifier_payload(
        db,
        race_terrain=[],
        locale_terrain_ids=[],
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
    )

    layer2d_payload = q_layer2d_injury_risk_profile_payload(
        db,
        injuries=layer1_payload.health_status.current_injuries,
        conditions=layer1_payload.health_status.health_conditions_active,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
    )

    primary_locale = _q_primary_locale(db, user_id)
    locale_equipment_pool = _q_locale_equipment_pool(db, user_id, primary_locale)
    layer2c_payload = q_layer2c_equipment_mapper_payload(
        db,
        locale_id=primary_locale,
        locale_equipment_pool=locale_equipment_pool,
        cluster_locale_ids=[primary_locale],
        cluster_gear_toggle_states={},
        included_discipline_ids=included_discipline_ids,
        layer2d_payload=layer2d_payload,
        etl_version_set=etl_version_set,
    )

    integration_bundle = assemble_layer3a_integration_bundle(db, user_id, as_of)
    layer3a_payload = llm_layer3a_athlete_state(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        integration_bundle=integration_bundle,
        as_of=as_of,
        etl_version_set=etl_version_set,
    )

    layer3b_payload = llm_layer3b_goal_timeline_viability(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer3a_payload=layer3a_payload,
        layer2a_payload=layer2a_payload,
        race_event_payload=race_event,
        current_date=today,
        etl_version_set=etl_version_set,
    )

    target_events = [
        Layer2ETargetEvent(
            event_id=str(race_event.race_event_id),
            event_name=race_event.name,
            event_date=race_event.event_date,
            framework_sport=framework_sport,
            estimated_duration_hr=_DURATION_HR_BY_RACE_FORMAT.get(
                race_event.race_format, 8.0
            ),
            aid_stations=None,
        )
    ]
    included_disciplines = [
        d for d in layer2a_payload.disciplines if d.inclusion == "included"
    ]
    layer2e_payload = q_layer2e_nutrition_baseline_payload(
        db,
        identity=layer1_payload.identity,
        health_status=layer1_payload.health_status,
        performance=layer1_payload.performance,
        target_events=target_events,
        lifestyle=layer1_payload.lifestyle,
        included_disciplines=included_disciplines,
        framework_sport=framework_sport,
        current_phase=layer3b_payload.periodization_shape.start_phase,
        etl_version_set=etl_version_set,
        athlete_id=str(user_id),
        today=today,
    )

    return llm_layer4_race_week_brief_cached(
        user_id=user_id,
        layer1_payload=layer1_payload.model_dump(mode="json"),
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payloads={primary_locale: layer2c_payload},
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        race_event_payload=race_event,
        prior_plan_session_window=[],
        plan_version_id=_RACE_WEEK_BRIEF_PLAN_VERSION_ID_PLACEHOLDER,
        etl_version_set=etl_version_set,
        cache=cache,
        today=today,
    )


def _q_current_etl_version_set(db: Any) -> dict[str, str]:
    """Discover the active Layer 0 ETL version triplet.

    v1 approximation: query `MAX(etl_version)` from `layer0.sports` (a
    representative table) and apply the same version to all three sub-arc
    keys. Coordinated Layer 0 rollouts ship aligned versions, so the v1
    approximation matches production. Promote to per-sub-arc when
    independent versioning ships.
    """
    cur = db.execute(
        "SELECT MAX(etl_version) AS v FROM layer0.sports WHERE superseded_at IS NULL"
    )
    row = cur.fetchone()
    if row is None or row["v"] is None:
        raise OrchestrationError(
            "etl_version_set_undiscoverable",
            "layer0.sports has no non-superseded rows",
        )
    v = row["v"]
    return {"0A": v, "0B": v, "0C": v}


def _q_primary_locale(db: Any, user_id: int) -> str:
    """Return the athlete's primary locale slug per the v1 `locale='home'`
    convention (matches `routes/dashboard.py:31`, `routes/plans.py:625`).

    Multi-locale clusters are out of scope for the vertical slice; raise
    when the athlete has no 'home' locale row.
    """
    cur = db.execute(
        "SELECT locale FROM locale_profiles WHERE user_id = ? AND locale = 'home' LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise OrchestrationError(
            "primary_locale_missing",
            f"user_id={user_id} has no locale_profiles row with locale='home'",
        )
    return row["locale"]


def _q_locale_equipment_pool(db: Any, user_id: int, locale: str) -> list[str]:
    """Return canonical `equipment_items.tag` tokens available at `locale`."""
    cur = db.execute(
        """SELECT ei.tag
           FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.user_id = ? AND le.locale = ?
           ORDER BY ei.tag""",
        (user_id, locale),
    )
    return [row["tag"] for row in cur.fetchall()]


__all__ = [
    "OrchestrationError",
    "orchestrate_race_week_brief",
]
