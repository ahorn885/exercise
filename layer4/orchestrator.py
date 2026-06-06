"""Layer 4 orchestrator — Phase 5.1 race_week_brief + Phase 5.2 single_session +
plan_refresh + plan_create.

End-to-end composition of the v2 upstream pipeline. Four entry points:

    `orchestrate_race_week_brief` (Phase 5.1, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_race_week_brief_cached

    `orchestrate_single_session_synthesize` (Phase 5.2, slice 1, 2026-05-20):
        Layer 1 → 2A → 2D → 2C (locale-only) → 3A →
        llm_layer4_single_session_synthesize_cached

    `orchestrate_plan_refresh` (Phase 5.2, slice 2, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_plan_refresh_cached
        (driver dispatches T1/T2/T3 internally; T3 cross-phase routes to
        Pattern A via `_route_t3_cross_phase_to_pattern_a`)

    `orchestrate_plan_create` (Phase 5.2, slice 3, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_plan_create_cached
        (Pattern A — per-phase synthesis loop + seam reviews internal to the
        driver; cached wrapper composes the per-entry §9.1 cache key)

Race_week_brief, plan_refresh, and plan_create share the full upstream cone
via the private `_upstream_full_cone` helper extracted at slice 2 (D1). The
helper covers the 3 shared pre-flight gates
(`etl_version_set_undiscoverable`, `framework_sport_missing`,
`primary_locale_missing`) plus the Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B →
2E composition. Race_week_brief retains its two brief-specific cheap pre-LLM
gates inline (`no_target_event` + `race_week_brief_too_early`);
plan_refresh and plan_create skip both (no-event mode is supported;
refresh/create fire on demand, not on a calendar window).

Single-session's cone is materially narrower (no 2B / 2E / 3B, uses
`request.sport` not `primary_sport`, uses `request.locale_slug` not the
hard-coded `'home'`, and skips Layer 2C entirely on the quick_equipment
path) — too many points of divergence to share `_upstream_full_cone`, so
it stays inline.

See `Upstream_Implementation_Plan_v1.md` §4 rows 5.1 + 5.2 + `Layer4_Spec.md`
§3.1 / §3.2 / §3.3 / §3.4 / §4.5 for the entry-point contracts.

Vertical-slice limitations carried as forward-pointers:
- Layer 2B inputs now flow end-to-end per Phase 5.1 form-refresh A/B/C
  (2026-05-20): `race_terrain` from `RaceEventPayload.race_terrain`
  (Form-refresh A + B, Open Item 2B-3 closed); `locale_terrain_ids` from
  the home `locale_profiles.locale_terrain_ids` TEXT[] column (Form-refresh
  C, Open Item 2B-2 closed). Athletes who haven't yet captured race
  terrain surface as `race_terrain=[]`, which Layer 2B's loosened
  `_validate_inputs` accepts and emits a `race_terrain_unset` coaching
  flag instead of failing (paired loosen shipped with Form-refresh C).
  No-event-mode plan_refresh + plan_create calls pass `race_terrain=[]`
  for the same reason (no target race → empty terrain input). Multi-locale
  cluster union for `locale_terrain_ids` remains spec §3 future work (v1
  wires the home locale only).
- `prior_plan_session_window` + `plan_version_id` + `plan_version_id_parent`
  + `parsed_intent` + `plan_start_date` are caller-supplied kwargs on
  `orchestrate_plan_refresh` + `orchestrate_plan_create` pending the
  D-64 caller-side route + `plan_versions` table (matches the slice 1 D4
  precedent for D-63's `suggestion_id`). Race_week_brief continues to pass
  `prior_plan_session_window=[]` + `plan_version_id=1` placeholders.
- Layer 3A + Layer 3B run through the cached wrappers
  (`layer3a.cached_wrapper.llm_layer3a_athlete_state_cached` +
  `layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability_cached`)
  as of Phase 5.2 Layer 3 caching slice (2026-05-21). The wrappers reuse
  the shared `layer4_cache` table via `cache.backend` and per-layer
  invalidation policy lives in `layer4.cache_invalidation` per the
  extended §9.3 matrix. Wiring covers all 4 entry points (3A+3B in
  `_upstream_full_cone`; 3A only in `orchestrate_single_session_synthesize`
  since single_session doesn't consume 3B).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal

from layer1.builder import build_layer1_payload
from layer2_modality import resolve_training_substitution
from layer2a.builder import Layer2AInputError, q_layer2a_discipline_classifier_payload
from layer2b.builder import q_layer2b_terrain_classifier_payload
from layer2c.builder import q_layer2c_equipment_mapper_payload
from layer2d.builder import q_layer2d_injury_risk_profile_payload
from layer2e.builder import q_layer2e_nutrition_baseline_payload
from layer3a.cached_wrapper import llm_layer3a_athlete_state_cached
from layer3a.integration import assemble_layer3a_integration_bundle
from layer3b.cached_wrapper import llm_layer3b_goal_timeline_viability_cached
from layer4.cache import Layer4Cache
from layer4.cached_wrappers import (
    llm_layer4_plan_create_cached,
    llm_layer4_plan_refresh_cached,
    llm_layer4_race_week_brief_cached,
    llm_layer4_single_session_synthesize_cached,
)
from layer4.locale_assign import assign_locales
from layer4.rx_wire import apply_current_rx
from layer4.context import (
    Layer1Payload,
    Layer2APayload,
    Layer2BPayload,
    Layer2Bundle,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer2ETargetEvent,
    Layer3APayload,
    Layer3BPayload,
    ParsedIntent,
    RaceEventPayload,
    TrainingSubstitutionPayload,
)
from layer4.payload import Layer4Payload, PlanSession
from layer4.single_session import SingleSessionRequest
import locations
from race_events_repo import load_target_race_event_payload


_AUTO_FIRE_DAYS_TO_EVENT_MAX = 14

# TODO(plan-versioning): replace once the v2 plan-versioning surface lands;
# every cache row currently keys on plan_version_id=1 for race-week-brief.
_RACE_WEEK_BRIEF_PLAN_VERSION_ID_PLACEHOLDER = 1

# Coarse race-format-based duration estimate for Layer 2E's TargetEvent
# (estimated_duration_hr > 0 is required). FALLBACK ONLY — the per-race
# `estimated_duration_hr` column (FormRefresh A1) is now the primary
# source; this map fires only when the athlete left duration blank.
# continuous_multi_day spans ~24h (continuous ultra) to 100h+ (expedition
# AR), so 48 is a deliberately mid-range placeholder pending the explicit
# value.
_DURATION_HR_BY_RACE_FORMAT: dict[str, float] = {
    "single_day": 8.0,
    "stage_race": 24.0,
    "continuous_multi_day": 48.0,
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


@dataclass(frozen=True)
class _UpstreamFullCone:
    """Composed upstream-payload set returned by `_upstream_full_cone`.

    Shared by `orchestrate_race_week_brief` + `orchestrate_plan_refresh` —
    the two full-cone entry points. Single_session is NOT a consumer (its
    narrower cone has too many divergence points to fit a shared helper —
    see module docstring for the cone-shape variance).

    Field shapes match the upstream payload types verbatim; consumers
    reshape into entry-point-specific kwargs (e.g., race_week_brief wraps
    layer2c_payload into a `{primary_locale: payload}` dict; plan_refresh
    packs all 5 layer-2 payloads into a `Layer2Bundle`).
    """

    etl_version_set: dict[str, str]
    framework_sport: str
    primary_locale: str
    layer1_payload: Layer1Payload
    layer2a_payload: Layer2APayload
    layer2b_payload: Layer2BPayload
    layer2c_payload: Layer2CPayload
    layer2d_payload: Layer2DPayload
    layer2e_payload: Layer2EPayload
    # Training-substitution resolver output (terrain emphasis + craft candidate
    # set per discipline), consuming the Layer 2B `terrain_by_discipline`
    # blocks. Threaded into the race_week_brief + plan_create + plan_refresh
    # prompts + cache keys.
    training_substitution_payload: TrainingSubstitutionPayload
    layer3a_payload: Layer3APayload
    layer3b_payload: Layer3BPayload


def _collect_athlete_crafts(layer1_payload: Layer1Payload) -> list[str]:
    """Flatten the athlete's owned crafts across discipline baselines.

    Today only paddle + bike baselines carry craft inventories; the
    training-substitution resolver hands the union to the Layer 4 LLM as the
    candidate set (gate Q2 — no family filtering here). Deduped + sorted for a
    stable cache hash.
    """
    crafts: list[str] = []
    baselines = layer1_payload.discipline_baselines
    if baselines.paddling and baselines.paddling.paddle_craft_types:
        crafts.extend(baselines.paddling.paddle_craft_types)
    if baselines.cycling and baselines.cycling.bike_types_available:
        crafts.extend(baselines.cycling.bike_types_available)
    return sorted(set(crafts))


def _upstream_full_cone(
    db: Any,
    user_id: int,
    today: date,
    *,
    cache: Layer4Cache,
    target_race_event: RaceEventPayload | None,
    viability_current_date: date | None = None,
) -> _UpstreamFullCone:
    """Compose the full upstream cone (Layer 1 → 2A → 2B → 2D → 2C → 3A →
    3B → 2E) shared by race_week_brief + plan_refresh + plan_create.

    Pipeline ordering note: Layer 2E runs after Layer 3B because it
    consumes `start_phase` from 3B's `periodization_shape`. `primary_locale`
    + `locale_terrain_ids` are read before Layer 2B (terrain pipeline);
    `locale_equipment_pool` is read before Layer 2C.

    `cache` threads through to the Layer 3A + 3B cached wrappers
    (`cache.backend` exposes the shared `layer4_cache` storage). The
    wrappers compose per-spec cache keys + handle hit/miss directly; the
    Layer 4 per-entry-point wrapper still wraps the whole pipeline so a
    Layer-4 cache hit short-circuits 3A/3B entirely.

    Pre-flight gates raised here (3, shared across all 3 consumers):
    `etl_version_set_undiscoverable`, `framework_sport_missing`,
    `primary_locale_missing`.

    `target_race_event=None` is supported for the no-event-mode plan_refresh
    path: Layer 2B's `race_terrain` becomes `[]` (loosened per Phase 5.1
    form-refresh C), Layer 2E's `target_events` becomes `[]`, and Layer 3B's
    `race_event_payload` becomes `None`. The orchestrator never raises
    `no_target_event` here — that gate belongs to entry points that
    require a race (race_week_brief inlines it before calling the helper).
    """
    etl_version_set = _q_current_etl_version_set(db)
    as_of = datetime.combine(today, time.min)

    layer1_payload = build_layer1_payload(db, user_id)
    # D-73 Phase 5.2 Bucket E.(b) — race-row override takes precedence over
    # athlete-profile primary_sport. When set on the target race, Layer 2A
    # classifies for the race's own sport (e.g. trail runner doing one AR
    # race) without churning the athlete's profile. Falls back to
    # primary_sport when the override is unset OR no target race exists.
    framework_sport = (
        target_race_event.framework_sport if target_race_event is not None else None
    )
    if not framework_sport:
        framework_sport = layer1_payload.identity.primary_sport
    if not framework_sport:
        raise OrchestrationError(
            "framework_sport_missing",
            f"layer1.identity.primary_sport is empty for user_id={user_id}",
        )

    # D-73 Phase 5.2 Bucket E.(b)-B2 — race-row `included_discipline_ids`
    # narrows the bridge-derived discipline list when supplied. Layer 2A
    # post-filters and the rest of the cone (2B/2C/2D/3A/3B) reads the
    # narrowed list naturally via `included_discipline_ids` below. The
    # route layer auto-clears `included_discipline_ids` on framework_sport
    # change so the filter never references stale IDs.
    discipline_id_filter = (
        target_race_event.included_discipline_ids
        if target_race_event is not None
        else None
    )
    layer2a_payload = q_layer2a_discipline_classifier_payload(
        db,
        framework_sport=framework_sport,
        discipline_id_filter=discipline_id_filter,
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
        race_terrain=(
            target_race_event.race_terrain if target_race_event is not None else []
        ),
        locale_terrain_ids=locale_terrain_ids,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
        # D-73 Phase 5.2 Bucket C (l) — thread athlete skill-capability
        # state into 2B so `requires_skill_capability` flags can fire
        # for terrains the athlete hasn't acquired the matching skill
        # for. Capture surface deferred; default state is the empty
        # dict (every toggle OFF), mirroring the gear-toggle precedent.
        skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states,
    )

    layer2d_payload = q_layer2d_injury_risk_profile_payload(
        db,
        injuries=layer1_payload.health_status.current_injuries,
        conditions=layer1_payload.health_status.health_conditions_active,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
    )

    cluster = locations.cluster_locale_ids(db, user_id)
    locale_equipment_pool = locations.cluster_effective_tags(db, user_id, cluster)
    layer2c_payload = q_layer2c_equipment_mapper_payload(
        db,
        locale_id=primary_locale,
        locale_equipment_pool=locale_equipment_pool,
        cluster_locale_ids=cluster,
        cluster_gear_toggle_states={},
        included_discipline_ids=included_discipline_ids,
        layer2d_payload=layer2d_payload,
        etl_version_set=etl_version_set,
        # D-73 Phase 5.2 Bucket C (l) — mirror of the 2B wire above.
        skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states,
    )

    integration_bundle = assemble_layer3a_integration_bundle(db, user_id, as_of)
    layer3a_payload = llm_layer3a_athlete_state_cached(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        integration_bundle=integration_bundle,
        as_of=as_of,
        etl_version_set=etl_version_set,
        cache_backend=cache.backend,
    )

    # 3B reasons about goal/timeline viability, so its `current_date` anchors
    # the training timeline. plan_create passes the (possibly future)
    # `plan_start_date` via `viability_current_date` so 3B's
    # `time_to_event_weeks` is measured from when training actually begins —
    # matching Layer 4's `_validate_plan_create_inputs` check
    # `(event_date - plan_start_date) // 7`. race_week_brief / plan_refresh
    # leave it None and anchor on `today`. 3A's `as_of` + 2E stay on `today`
    # (athlete state + nutrition baseline are "now", not the plan start).
    # §H.2 goal context (2026-05-26) — thread the athlete's captured goal
    # fields off the target race row into Layer 3B's event-mode goal block +
    # HITL triggers (3B.first_time_competitive_goal). Closes the deployed-shape
    # gap: 3B previously saw only the cached wrapper's hardcoded
    # goal_outcome="Finish". `race_duration_hr` / `race_terrain` are already on
    # the payload (so the cache key already varies on them) but never reached
    # 3B's prompt — the builder reads them from kwargs — so thread them too.
    # `race_distance_km` is left out: the builder already falls back to
    # `RaceEventPayload.distance_km`. `previous_attempts` (Slice 2) threads as
    # plain dicts the builder consumes via `.get("outcome")` / `.get("dnf_cause")`
    # — it unblocks the `3B.dnf_recurrence_risk` HITL flag. All None / empty in
    # no-event mode (the cached wrapper then falls back to the conservative
    # "Finish" tier for legacy / uncaptured rows).
    section_h2_kwargs: dict[str, Any] = {}
    if target_race_event is not None:
        section_h2_kwargs = {
            "goal_outcome": target_race_event.goal_outcome,
            "first_time_at_distance": target_race_event.first_time_at_distance,
            "time_goal": target_race_event.time_goal,
            "race_pack_weight_kg": (
                float(target_race_event.race_pack_weight_kg)
                if target_race_event.race_pack_weight_kg is not None
                else None
            ),
            "race_duration_hr": (
                float(target_race_event.estimated_duration_hr)
                if target_race_event.estimated_duration_hr is not None
                else None
            ),
            "race_terrain": (
                [e.terrain_id for e in target_race_event.race_terrain] or None
            ),
            "previous_attempts": (
                [
                    {"outcome": a.outcome, "dnf_cause": a.dnf_cause or ""}
                    for a in target_race_event.previous_attempts
                ]
                or None
            ),
        }
    layer3b_payload = llm_layer3b_goal_timeline_viability_cached(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer3a_payload=layer3a_payload,
        layer2a_payload=layer2a_payload,
        race_event_payload=target_race_event,
        current_date=(
            viability_current_date if viability_current_date is not None else today
        ),
        etl_version_set=etl_version_set,
        cache_backend=cache.backend,
        **section_h2_kwargs,
    )

    target_events: list[Layer2ETargetEvent] = []
    if target_race_event is not None:
        target_events.append(
            Layer2ETargetEvent(
                event_id=str(target_race_event.race_event_id),
                event_name=target_race_event.name,
                event_date=target_race_event.event_date,
                framework_sport=framework_sport,
                estimated_duration_hr=(
                    float(target_race_event.estimated_duration_hr)
                    if target_race_event.estimated_duration_hr is not None
                    else _DURATION_HR_BY_RACE_FORMAT.get(
                        target_race_event.race_format, 8.0
                    )
                ),
            )
        )
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

    # Best-fit re-model — training-substitution resolver. Consumes the Layer 2B
    # per-discipline terrain blocks (no extra SQL) + the athlete's owned crafts
    # (handed verbatim; the LLM picks — gate Q2). Pure Python; safe to run
    # unconditionally (empty terrain → empty recommendations).
    training_substitution_payload = resolve_training_substitution(
        terrain_by_discipline=layer2b_payload.terrain_by_discipline,
        athlete_crafts=_collect_athlete_crafts(layer1_payload),
        etl_version_set=etl_version_set,
        discipline_names={
            d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines
        },
    )

    return _UpstreamFullCone(
        etl_version_set=etl_version_set,
        framework_sport=framework_sport,
        primary_locale=primary_locale,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payload=layer2c_payload,
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        training_substitution_payload=training_substitution_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
    )


def _apply_locale_assign(
    db: Any,
    user_id: int,
    payload: Layer4Payload,
    layer2c_payloads: dict[str, "Layer2CPayload"],
) -> Layer4Payload:
    """Track 2 slice 2c — run the deterministic post-synthesis locale-assign
    pipeline (`layer4/locale_assign.py`) on the synthesized payload, swap the
    payload's sessions for the assigned-and-substituted set. Cardio + rest
    sessions are untouched (cardio routing deferred to slice 2c.2).

    Runs OUTSIDE the cached engine — locale-only edits already invalidate
    Layer 2C and transitively Layer 4 (Track 1 eviction policy), so this
    is a pure post-hydrate transform. Failure here is non-fatal: a degraded
    pass-through preserves the original payload + logs the cause, so a
    locale-assign defect can never wedge plan generation.
    """
    try:
        new_sessions, _diag = assign_locales(
            sessions=list(payload.sessions),
            layer2c_payloads=layer2c_payloads,
            db=db,
            user_id=user_id,
            llm_substitute_caller=None,  # in-flight wiring; deterministic ladder ships first
        )
        return payload.model_copy(update={"sessions": new_sessions})
    except Exception as exc:  # noqa: BLE001 — see docstring on the degraded path
        import logging
        logging.getLogger(__name__).warning(
            "_apply_locale_assign: degraded pass-through after exception: %s", exc,
        )
        return payload


def _apply_rx_wire(
    db: Any,
    user_id: int,
    payload: Layer4Payload,
    layer2c_payloads: dict[str, "Layer2CPayload"],
) -> Layer4Payload:
    """Track 2 slice 2d — run the deterministic post-synth rx wiring
    (`layer4/rx_wire.py`) on the synthesized payload. For each strength
    exercise: overwrite `load_prescription` with the precise `current_rx`
    baseline when one exists; else write a category-keyed RPE template and
    append `first_exposure` to `coaching_flags`. NO LLM in this path.

    Runs AFTER `_apply_locale_assign` on the same hydrated payload (per
    spec §10 slice-2d row): substitutions decided by the locale-assign step
    can change which exercise we look up rx for, so rx wiring must see the
    post-substitution exercise list. `current_rx` reads are per-athlete
    state, intentionally outside the block synthesis cache (a `current_rx`
    edit updates the rendered prescription on next read without
    invalidating Layer 4 blocks — spec §9).

    Degraded pass-through on exception: an rx-wire defect can never wedge
    plan generation.
    """
    try:
        new_payload, _diag = apply_current_rx(
            payload, db, user_id, layer2c_payloads,
        )
        return new_payload
    except Exception as exc:  # noqa: BLE001 — see docstring on the degraded path
        import logging
        logging.getLogger(__name__).warning(
            "_apply_rx_wire: degraded pass-through after exception: %s", exc,
        )
        return payload


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
    3. Compose upstream cone via `_upstream_full_cone` (shared with
       `orchestrate_plan_refresh` per Phase 5.2 slice 2 D1 extract).
    4. Compose via `llm_layer4_race_week_brief_cached`.

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

    cone = _upstream_full_cone(
        db, user_id, today, cache=cache, target_race_event=race_event
    )

    return llm_layer4_race_week_brief_cached(
        user_id=user_id,
        layer1_payload=cone.layer1_payload.model_dump(mode="json"),
        layer2a_payload=cone.layer2a_payload,
        layer2b_payload=cone.layer2b_payload,
        layer2c_payloads={cone.primary_locale: cone.layer2c_payload},
        layer2d_payload=cone.layer2d_payload,
        layer2e_payload=cone.layer2e_payload,
        layer3a_payload=cone.layer3a_payload,
        layer3b_payload=cone.layer3b_payload,
        race_event_payload=race_event,
        prior_plan_session_window=[],
        plan_version_id=_RACE_WEEK_BRIEF_PLAN_VERSION_ID_PLACEHOLDER,
        etl_version_set=cone.etl_version_set,
        cache=cache,
        # Thread the training-substitution payload from the cone into the
        # brief's prompt body + cache key.
        training_substitution_payload=cone.training_substitution_payload,
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
    6. Build the Layer 3A integration bundle + call
       `llm_layer3a_athlete_state_cached` (shares the Layer 4 cache backend
       via `cache.backend` per Phase 5.2 Layer 3 caching slice 2026-05-21 —
       same wrapper as the `_upstream_full_cone` call sites).
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
            # D-73 Phase 5.2 Bucket C (l) — same wire as full-cone path.
            skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states,
        )

    integration_bundle = assemble_layer3a_integration_bundle(db, user_id, as_of)
    layer3a_payload = llm_layer3a_athlete_state_cached(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        integration_bundle=integration_bundle,
        as_of=as_of,
        etl_version_set=etl_version_set,
        cache_backend=cache.backend,
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


def orchestrate_plan_refresh(
    db: Any,
    user_id: int,
    *,
    tier: Literal["T1", "T2", "T3"],
    refresh_scope_start: date,
    refresh_scope_end: date,
    plan_version_id: int,
    plan_version_id_parent: int,
    prior_plan_session_window: list[PlanSession],
    cache: Layer4Cache,
    parsed_intent: ParsedIntent | None = None,
    plan_start_date: date | None = None,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end D-64 plan-refresh pipeline for `user_id`.

    Algorithm:
    1. Load target race event (None OK — no-event-mode plans refresh fine
       without a target race; Layer 3B's `mode='no-event'` branch handles
       this downstream).
    2. Compose upstream cone via `_upstream_full_cone` (shared with
       `orchestrate_race_week_brief` per Phase 5.2 slice 2 D1 extract).
    3. Pack the 5 Layer 2 payloads into a `Layer2Bundle` — D-64 driver
       expects the bundled input shape, not individual payloads (see
       `llm_layer4_plan_refresh` signature in `layer4/plan_refresh.py`).
    4. Compose via `llm_layer4_plan_refresh_cached`. The driver dispatches
       T1/T2/T3 internally; T3 cross-phase routes to Pattern A via
       `_route_t3_cross_phase_to_pattern_a` (shipped at Step 4f 2026-05-18).

    Pre-flight gates (3, all emitted by `_upstream_full_cone`):
    `etl_version_set_undiscoverable`, `primary_locale_missing`,
    `framework_sport_missing`. The orchestrator does NOT raise
    `no_target_event` (no-event refresh is supported) and does NOT pre-flight
    the auto-fire window (refresh fires on demand). `tier`/`refresh_scope_*`/
    `plan_version_id_parent`/`plan_start_date` validity is enforced by the
    driver's `_validate_inputs` per `Layer4_Spec.md` §4.3 — `Layer4InputError`
    propagates verbatim; the orchestrator does not wrap.

    `plan_version_id` + `plan_version_id_parent` + `prior_plan_session_window`
    + `parsed_intent` + `plan_start_date` are all caller-supplied kwargs
    pending the D-64 caller-side route + `plan_versions` table (matches the
    slice 1 D4 precedent for D-63's `suggestion_id`).

    `parsed_intent=None` is permitted — D-64 §5.4 documents graceful
    degradation when the NL parser is unavailable.
    """
    if today is None:
        today = date.today()

    race_event = load_target_race_event_payload(db, user_id)
    cone = _upstream_full_cone(
        db, user_id, today, cache=cache, target_race_event=race_event
    )

    layer2_bundle = Layer2Bundle(
        a=cone.layer2a_payload,
        b=cone.layer2b_payload,
        c={cone.primary_locale: cone.layer2c_payload},
        d=cone.layer2d_payload,
        e=cone.layer2e_payload,
    )

    payload = llm_layer4_plan_refresh_cached(
        user_id=user_id,
        tier=tier,
        refresh_scope_start=refresh_scope_start,
        refresh_scope_end=refresh_scope_end,
        layer1_payload=cone.layer1_payload.model_dump(mode="json"),
        layer2_bundle=layer2_bundle,
        layer3a_payload=cone.layer3a_payload,
        layer3b_payload=cone.layer3b_payload,
        prior_plan_session_window=prior_plan_session_window,
        parsed_intent=parsed_intent,
        plan_version_id=plan_version_id,
        plan_version_id_parent=plan_version_id_parent,
        etl_version_set=cone.etl_version_set,
        cache=cache,
        plan_start_date=plan_start_date,
        # Thread the training-substitution payload from the cone into the
        # refresh prompt body + cache key.
        training_substitution_payload=cone.training_substitution_payload,
    )
    payload = _apply_locale_assign(db, user_id, payload, layer2_bundle.c)
    payload = _apply_rx_wire(db, user_id, payload, layer2_bundle.c)
    return payload


def orchestrate_plan_create(
    db: Any,
    user_id: int,
    *,
    plan_start_date: date,
    plan_version_id: int,
    cache: Layer4Cache,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end Pattern A plan-create pipeline for `user_id`.

    Algorithm:
    1. Load target race event (None OK — open-ended plans are first-class;
       Layer 3B's `mode='no-event'` branch handles this downstream and the
       driver accepts `race_event_payload=None` per `Layer4_Spec.md` §3.1).
    2. Compose upstream cone via `_upstream_full_cone` (shared with
       `orchestrate_race_week_brief` + `orchestrate_plan_refresh`).
    3. Compose via `llm_layer4_plan_create_cached`. The driver runs the
       per-phase synthesis loop (sequential, in order) + seam reviews +
       final cross-phase validator pass internally per §5.2; the
       orchestrator does not see per-phase internals.

    Pre-flight gates (3, all emitted by `_upstream_full_cone`):
    `etl_version_set_undiscoverable`, `primary_locale_missing`,
    `framework_sport_missing`. The orchestrator does NOT raise
    `no_target_event` (open-ended plans are supported) and does NOT
    pre-flight `plan_start_date_in_past` / `plan_version_id_unset` /
    `time_to_event_weeks_mismatch` / `discipline_weights_invalid` — the
    driver's `_validate_plan_create_inputs` covers all four per §4.2;
    `Layer4InputError` propagates verbatim, the orchestrator does not wrap
    (matches the slice 1 + slice 2 + race_week_brief precedent of not
    wrapping driver-level input errors).

    `plan_start_date` + `plan_version_id` are caller-supplied kwargs
    pending the D-64 caller-side route + `plan_versions` table (matches
    the slice 1 D4 + slice 2 D3 precedent for D-63/D-64 caller-side
    deferral). The route handler is the right place to resolve
    "athlete picks future start" vs "today" + allocate the `plan_versions`
    row.

    Note: this is the heaviest entry point. Pattern A fires N per-phase
    synthesizer calls (one per phase in `phase_structure_from_3b` output,
    typically 3-4) + (N-1) seam reviewer calls. Real-LLM cost ~$0.30-$0.50
    per cold synthesis; the per-entry §9.1 cache + per-phase §9.2 cache
    inside the engine short-circuit most repeat invocations.
    """
    if today is None:
        today = date.today()

    race_event = load_target_race_event_payload(db, user_id)
    cone = _upstream_full_cone(
        db, user_id, today, cache=cache, target_race_event=race_event,
        viability_current_date=plan_start_date,
    )

    layer2c_payloads = {cone.primary_locale: cone.layer2c_payload}
    payload = llm_layer4_plan_create_cached(
        user_id=user_id,
        layer1_payload=cone.layer1_payload.model_dump(mode="json"),
        layer2a_payload=cone.layer2a_payload,
        layer2b_payload=cone.layer2b_payload,
        layer2c_payloads=layer2c_payloads,
        layer2d_payload=cone.layer2d_payload,
        layer2e_payload=cone.layer2e_payload,
        layer3a_payload=cone.layer3a_payload,
        layer3b_payload=cone.layer3b_payload,
        plan_start_date=plan_start_date,
        plan_version_id=plan_version_id,
        etl_version_set=cone.etl_version_set,
        cache=cache,
        race_event_payload=race_event,
        # Thread the training-substitution payload from the cone into the
        # per-phase prompt bodies + cache key.
        training_substitution_payload=cone.training_substitution_payload,
    )
    payload = _apply_locale_assign(db, user_id, payload, layer2c_payloads)
    payload = _apply_rx_wire(db, user_id, payload, layer2c_payloads)
    return payload


def _max_etl_version(versions: list[str]) -> str:
    """Return the highest ETL version by numeric ordering.

    Versions look like `0A-v11.0` / `0A-v9.0` / `0C-v2.0-r2`. A lexical MAX
    mis-sorts at a digit-width boundary (`'0A-v9.0' > '0A-v11.0'`), so compare
    the integer components as a tuple instead: `0A-v11.0` → `(0, 11, 0)`. A
    revision suffix (`-r2`) extends the tuple, so it correctly outranks the
    un-revised base of the same version.
    """
    return max(versions, key=lambda v: tuple(int(n) for n in re.findall(r"\d+", v)))


def _q_current_etl_version_set(db: Any) -> dict[str, str]:
    """Discover the active Layer 0 ETL version triplet.

    v1 approximation: take the highest `etl_version` from `layer0.sports` (a
    representative table) and apply it to all three sub-arc keys. Coordinated
    Layer 0 rollouts ship aligned versions, so the v1 approximation matches
    production. Promote to per-sub-arc when independent versioning ships.

    The max is computed by numeric component (see `_max_etl_version`), not a
    lexical SQL `MAX` — the latter ranks `0A-v11.0` below `0A-v9.0` at a
    digit-width boundary.
    """
    cur = db.execute(
        "SELECT DISTINCT etl_version AS v FROM layer0.sports WHERE superseded_at IS NULL"
    )
    versions = [row["v"] for row in cur.fetchall() if row["v"]]
    if not versions:
        raise OrchestrationError(
            "etl_version_set_undiscoverable",
            "layer0.sports has no non-superseded rows",
        )
    v = _max_etl_version(versions)
    return {"0A": v, "0B": v, "0C": v}


def _q_primary_locale(db: Any, user_id: int) -> str:
    """Return the athlete's home locale slug — the `locale_profiles` row with
    `preferred = TRUE` (Locations_Consolidation_Design_v1 §5.1). Replaces the
    hardcoded `locale = 'home'` convention. Delegates to the authoritative
    `locations.primary_locale`; re-raises its domain error as the
    layer-contract `OrchestrationError("primary_locale_missing")`.
    """
    try:
        return locations.primary_locale(db, user_id)
    except locations.PrimaryLocaleMissing as exc:
        raise OrchestrationError("primary_locale_missing", str(exc)) from exc


def _q_locale_equipment_pool(db: Any, user_id: int, locale: str) -> list[str]:
    """Return the canonical-name equipment pool effective at a single
    `locale`, via the authoritative `locations.locale_effective_tags`. Used by
    the single-session path (one athlete-picked locale); the full plan-gen
    cone unions across the cluster (`locations.cluster_effective_tags`)."""
    return sorted(locations.locale_effective_tags(db, user_id, locale))


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
    "orchestrate_plan_create",
    "orchestrate_plan_refresh",
    "orchestrate_race_week_brief",
    "orchestrate_single_session_synthesize",
]
