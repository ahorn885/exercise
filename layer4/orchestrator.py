"""Layer 4 orchestrator — Phase 5.1 race_week_brief + Phase 5.2 single_session.

End-to-end composition of the v2 upstream pipeline. Two entry points:

    `orchestrate_race_week_brief` (Phase 5.1, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_race_week_brief_cached

    `orchestrate_single_session_synthesize` (Phase 5.2, slice 1, 2026-05-20):
        Layer 1 → 2A → 2D → 2C (locale-only) → 3A →
        llm_layer4_single_session_synthesize_cached

Single-session's cone is materially narrower than race-week-brief's (no
2B / 2E / 3B); the two pipelines stay inline rather than share a flag-driven
`_upstream_pipeline` helper. The Rule-of-Three trigger for refactor lands
with the 3rd entry point (`plan_refresh`); module-level `_q_*` helpers are
shared today (`_q_current_etl_version_set`, `_q_locale_equipment_pool`).

See `Upstream_Implementation_Plan_v1.md` §4 row 5.1 + 5.2 + `Layer4_Spec.md`
§3.3 / §3.4 / §4.5 for the entry-point contracts.

Vertical-slice limitations carried as forward-pointers:
- Layer 2B inputs now flow end-to-end per Phase 5.1 form-refresh A/B/C
  (2026-05-20): `race_terrain` from `RaceEventPayload.race_terrain`
  (Form-refresh A + B, Open Item 2B-3 closed); `locale_terrain_ids` from
  the home `locale_profiles.locale_terrain_ids` TEXT[] column (Form-refresh
  C, Open Item 2B-2 closed). Athletes who haven't yet captured race
  terrain surface as `race_terrain=[]`, which Layer 2B's loosened
  `_validate_inputs` accepts and emits a `race_terrain_unset` coaching
  flag instead of failing (paired loosen shipped with Form-refresh C).
  Empty `locale_terrain_ids` was already a supported case per spec §4
  condition 5 + §13.3. Multi-locale cluster union for `locale_terrain_ids`
  remains spec §3 future work (v1 wires the home locale only — matches
  the existing `_q_locale_equipment_pool` pattern).
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
from layer2a.builder import Layer2AInputError, q_layer2a_discipline_classifier_payload
from layer2b.builder import q_layer2b_terrain_classifier_payload
from layer2c.builder import q_layer2c_equipment_mapper_payload
from layer2d.builder import q_layer2d_injury_risk_profile_payload
from layer2e.builder import q_layer2e_nutrition_baseline_payload
from layer3a.builder import llm_layer3a_athlete_state
from layer3a.integration import assemble_layer3a_integration_bundle
from layer3b.builder import llm_layer3b_goal_timeline_viability
from layer4.cache import Layer4Cache
from layer4.cached_wrappers import (
    llm_layer4_race_week_brief_cached,
    llm_layer4_single_session_synthesize_cached,
)
from layer4.context import Layer2ETargetEvent
from layer4.payload import Layer4Payload
from layer4.single_session import SingleSessionRequest
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

    primary_locale = _q_primary_locale(db, user_id)
    locale_terrain_ids = _q_locale_terrain_ids(db, user_id, primary_locale)

    layer2b_payload = q_layer2b_terrain_classifier_payload(
        db,
        race_terrain=race_event.race_terrain,
        locale_terrain_ids=locale_terrain_ids,
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
            aid_stations=race_event.aid_stations,
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


def orchestrate_single_session_synthesize(
    db: Any,
    user_id: int,
    request: SingleSessionRequest,
    suggestion_id: int,
    *,
    cache: Layer4Cache,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end D-63 on-demand workout pipeline for `user_id`.

    Algorithm:
    1. Discover the active `etl_version_set` triplet from Layer 0.
    2. Build Layer 1.
    3. Call Layer 2A with `framework_sport=request.sport` — the athlete's
       per-request sport pick overrides their primary discipline mix
       (single-session is athlete-overriding behavior per D-63 §6.1; e.g.,
       Andy can pick Rowing for cross-training even though his primary
       sport is Adventure Racing). Layer2A's `Layer2AInputError` on an
       unknown framework_sport surfaces as
       `OrchestrationError('request_sport_unavailable')`.
    4. Compute `included_discipline_ids` from 2A; call Layer 2D.
    5. Locale branch (XOR per `SingleSessionRequest._check_locale_xor_quick_equipment`):
       - When `request.locale_slug` is non-None: validate the slug exists
         via `_q_locale_by_slug` (raise
         `OrchestrationError('locale_unknown')` on miss); read the locale's
         equipment pool; call Layer 2C against it; pass the resulting
         payload as `layer2c_payload_for_locale`.
       - When `request.locale_slug` is None ("Somewhere else"): skip Layer
         2C entirely; pass `layer2c_payload_for_locale=None`. The driver
         resolves equipment from `request.quick_equipment` directly per
         spec §3.3 row 4.
    6. Build the Layer 3A integration bundle + call `llm_layer3a_athlete_state`
       (uncached at the orchestrator level — matches race_week_brief
       precedent; Phase 5.2 will revisit 3A caching policy once multiple
       Layer 4 entry points share user-scoped outputs).
    7. Compose via `llm_layer4_single_session_synthesize_cached`.

    No `no_target_event` / `race_week_brief_too_early` gates — single-session
    is off-plan, off-race, and athlete-driven by definition. The driver's
    own `_validate_inputs` (`layer4/single_session.py` §4.4) covers
    locale-XOR-quick + 2C-payload-presence rules.

    Failures from any upstream layer propagate verbatim; the orchestrator
    does not try/except them (except for the targeted Layer2AInputError
    catch documented above).
    """
    if today is None:
        today = date.today()

    etl_version_set = _q_current_etl_version_set(db)
    as_of = datetime.combine(today, time.min)

    layer1_payload = build_layer1_payload(db, user_id)

    try:
        layer2a_payload = q_layer2a_discipline_classifier_payload(
            db,
            framework_sport=request.sport,
            etl_version_set=etl_version_set,
        )
    except Layer2AInputError as exc:
        raise OrchestrationError(
            "request_sport_unavailable",
            f"request.sport={request.sport!r} is not a known framework_sport: {exc}",
        ) from exc

    included_discipline_ids = [
        d.discipline_id
        for d in layer2a_payload.disciplines
        if d.inclusion == "included"
    ]

    layer2d_payload = q_layer2d_injury_risk_profile_payload(
        db,
        injuries=layer1_payload.health_status.current_injuries,
        conditions=layer1_payload.health_status.health_conditions_active,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
    )

    layer2c_payload_for_locale = None
    if request.locale_slug is not None:
        if not _q_locale_by_slug(db, user_id, request.locale_slug):
            raise OrchestrationError(
                "locale_unknown",
                f"user_id={user_id} has no locale_profiles row with "
                f"locale={request.locale_slug!r}",
            )
        locale_equipment_pool = _q_locale_equipment_pool(
            db, user_id, request.locale_slug
        )
        layer2c_payload_for_locale = q_layer2c_equipment_mapper_payload(
            db,
            locale_id=request.locale_slug,
            locale_equipment_pool=locale_equipment_pool,
            cluster_locale_ids=[request.locale_slug],
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

    return llm_layer4_single_session_synthesize_cached(
        user_id=user_id,
        request=request,
        layer1_payload=layer1_payload.model_dump(mode="json"),
        layer2c_payload_for_locale=layer2c_payload_for_locale,
        layer2d_payload=layer2d_payload,
        layer3a_payload=layer3a_payload,
        suggestion_id=suggestion_id,
        etl_version_set=etl_version_set,
        cache=cache,
        session_date=today,
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


def _q_locale_by_slug(db: Any, user_id: int, locale: str) -> bool:
    """Return True when `(user_id, locale)` has a `locale_profiles` row.

    Used by `orchestrate_single_session_synthesize` to validate the
    athlete-picked `request.locale_slug` before composing the 2C call.
    Distinct from `_q_primary_locale` (which is hard-coded to `'home'`):
    single-session athletes pick any locale they've configured.
    """
    cur = db.execute(
        "SELECT 1 AS hit FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    )
    return cur.fetchone() is not None


def _q_locale_terrain_ids(db: Any, user_id: int, locale: str) -> list[str]:
    """Return canonical TRN-xxx terrain ids available at `locale`.

    Reads `locale_profiles.locale_terrain_ids` (TEXT[]) for the
    (user_id, locale) row. Returns `[]` when the row carries an empty
    array or NULL (athlete hasn't yet captured terrain via Form-refresh C);
    Layer 2B's `_validate_inputs` accepts the empty case (spec §4
    condition 5 + §13.3). Psycopg2 hydrates TEXT[] to a Python list
    directly; the SQLite shim path returns the JSON-ish text representation
    that `_hydrate_locale_terrain_ids` already covers route-side, but the
    orchestrator is PG-only so the list-path is the only live shape here.
    Tolerates the JSON-string SQLite shim for completeness (mirrors
    `race_events_repo.get_race_event` adapter tolerance for race_terrain).
    """
    cur = db.execute(
        """SELECT locale_terrain_ids
             FROM locale_profiles
            WHERE user_id = ? AND locale = ?
            LIMIT 1""",
        (user_id, locale),
    )
    row = cur.fetchone()
    if row is None:
        return []
    raw = row["locale_terrain_ids"]
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s in ("{}", "[]"):
            return []
        # SQLite shim path — tolerate JSON-string array. Postgres TEXT[]
        # arrives as a list already.
        import json as _json
        try:
            parsed = _json.loads(s)
        except (ValueError, TypeError):
            return []
        if isinstance(parsed, list):
            return [v for v in parsed if isinstance(v, str)]
    return []


__all__ = [
    "OrchestrationError",
    "orchestrate_race_week_brief",
    "orchestrate_single_session_synthesize",
]
