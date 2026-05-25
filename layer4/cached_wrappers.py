"""Per-entry-point `_cached()` wrappers per `Layer4_Spec.md` §9.

Each wrapper:
1. Pre-computes the upstream-layer hashes from typed payloads via
   `layer4/hashing.py:compute_payload_hash` and the bundle helpers.
2. Builds the per-entry cache key via the matching `*_key()` helper in
   `layer4/hashing.py`.
3. Defines a closure that re-invokes the underlying entry-point function
   on cache miss.
4. Delegates to `Layer4Cache.get_or_synthesize()` which handles per-call
   rebinding (`plan_version_id` always; `suggestion_id` for single-session)
   on hit per §9.4.

The wrappers are siblings to the entry-point functions, not modifications
to them — the entry points stay cache-unaware per the spec's "cache wraps
at orchestrator boundary" framing.

Per-phase cache for Pattern A (§9.2) is wired INSIDE `_run_pattern_a_engine`
in `plan_create.py` via the `cache` kwarg threaded through; the wrapper
here just handles the top-level per-entry cache.
"""

from __future__ import annotations

from concurrent.futures import Executor
from datetime import date as _date_type
from typing import Any, Callable

from layer4.cache import Layer4Cache
from layer4.context import (
    Layer2APayload,
    Layer2BPayload,
    Layer2Bundle,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer2ModalityPayload,
    Layer3APayload,
    Layer3BPayload,
    ParsedIntent,
    RaceEventPayload,
    TrainingSubstitutionPayload,
)
from layer4.hashing import (
    compute_layer2_bundle_canonical_hash,
    compute_layer2c_bundle_hash,
    compute_payload_hash,
    compute_prior_plan_session_window_hash,
    plan_create_key,
    plan_refresh_key,
    race_week_brief_key,
    single_session_synthesize_key,
)
from layer4.payload import Layer4Payload, PlanSession
from layer4.plan_create import llm_layer4_plan_create
from layer4.plan_refresh import llm_layer4_plan_refresh
from layer4.race_week_brief import llm_layer4_race_week_brief
from layer4.single_session import SingleSessionRequest, llm_layer4_single_session_synthesize


# ─── helpers ───────────────────────────────────────────────────────────────


def _layer2c_bundle_hash(
    layer2c_payloads: dict[str, Layer2CPayload],
) -> str:
    """Compute the §9.1 bundle hash for `plan_create` + `race_week_brief`."""
    per_locale = {
        locale_id: compute_payload_hash(payload)
        for locale_id, payload in layer2c_payloads.items()
    }
    return compute_layer2c_bundle_hash(per_locale)


def _layer2_bundle_canonical_hash(bundle: Layer2Bundle) -> str:
    """Compute the §9.1 bundle hash for `plan_refresh`.

    Per `compute_layer2_bundle_canonical_hash`, the keys MUST be exactly
    {'a','b','c','d','e'} with null entries preserved (so a 2A-only T1
    refresh differentiates from a 0-Layer-2-cascade T1 refresh).
    """
    bundle_hashes: dict[str, str | None] = {
        "a": compute_payload_hash(bundle.a) if bundle.a is not None else None,
        "b": compute_payload_hash(bundle.b) if bundle.b is not None else None,
        "c": _layer2c_bundle_hash(bundle.c) if bundle.c else None,
        "d": compute_payload_hash(bundle.d) if bundle.d is not None else None,
        "e": compute_payload_hash(bundle.e) if bundle.e is not None else None,
    }
    return compute_layer2_bundle_canonical_hash(bundle_hashes)


# ─── llm_layer4_single_session_synthesize_cached ──────────────────────────


def llm_layer4_single_session_synthesize_cached(
    user_id: int,
    request: SingleSessionRequest,
    layer1_payload: dict[str, Any],
    layer2c_payload_for_locale: Layer2CPayload | None,
    layer2d_payload: Layer2DPayload,
    layer3a_payload: Layer3APayload,
    suggestion_id: int,
    etl_version_set: dict[str, str],
    *,
    cache: Layer4Cache,
    # D-73 Phase 5.2 Walkthrough BM3 2026-05-24 — resolver payload
    # threaded through to the driver's prompt-body renderer +
    # hashed into the cache key via `layer2_modality_locale_hash`.
    # Default None preserves quick-equipment mode + legacy call sites
    # (None collapses to '' inside the key helper for stability).
    layer2_modality_payload_for_locale: Layer2ModalityPayload | None = None,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.3,
    max_tokens: int = 1500,
    capped_retries: int = 2,
    extended_thinking_budget: int = 3500,
    plan_version_id: int = 0,
    session_date: _date_type | None = None,
    llm_caller: Callable | None = None,
) -> Layer4Payload:
    """Per-entry cache wrapper around `llm_layer4_single_session_synthesize`.

    On hit: returns the cached payload with `plan_version_id` +
    `suggestion_id` rebound to the caller-supplied values per §9.4.

    On miss: invokes the synthesizer; stores the result; returns.

    Cache key per §9.1 single_session formula. `suggestion_id` +
    `plan_version_id` are NOT in the key (allocated per call; rebinding
    on hit).
    """
    layer1_hash = compute_payload_hash(layer1_payload)
    layer2c_locale_hash = (
        compute_payload_hash(layer2c_payload_for_locale)
        if layer2c_payload_for_locale is not None
        else None
    )
    layer2d_hash = compute_payload_hash(layer2d_payload)
    layer3a_hash = compute_payload_hash(layer3a_payload)
    # BM-3: hash the resolver payload so cache invalidates on terrain /
    # equipment / skill-toggle changes AND on `_MODALITY_OPTIONS_PER_DISCIPLINE`
    # code-deploy shape changes (which existing transitive eviction misses).
    layer2_modality_locale_hash = (
        compute_payload_hash(layer2_modality_payload_for_locale)
        if layer2_modality_payload_for_locale is not None
        else None
    )

    key = single_session_synthesize_key(
        user_id=user_id,
        request=request,
        layer1_hash=layer1_hash,
        layer2c_locale_hash=layer2c_locale_hash,
        layer2d_hash=layer2d_hash,
        layer3a_hash=layer3a_hash,
        etl_version_set=etl_version_set,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        capped_retries=capped_retries,
        layer2_modality_locale_hash=layer2_modality_locale_hash,
    )

    def _synthesize() -> Layer4Payload:
        return llm_layer4_single_session_synthesize(
            user_id,
            request,
            layer1_payload,
            layer2c_payload_for_locale,
            layer2d_payload,
            layer3a_payload,
            suggestion_id,
            etl_version_set,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            capped_retries=capped_retries,
            extended_thinking_budget=extended_thinking_budget,
            plan_version_id=plan_version_id,
            session_date=session_date,
            llm_caller=llm_caller,
            layer2_modality_payload_for_locale=layer2_modality_payload_for_locale,
        )

    return cache.get_or_synthesize(
        cache_key=key,
        user_id=user_id,
        entry_point="single_session_synthesize",
        synthesizer=_synthesize,
        rebind_plan_version_id=plan_version_id,
        rebind_suggestion_id=suggestion_id,
    )


# ─── llm_layer4_plan_refresh_cached ───────────────────────────────────────


def llm_layer4_plan_refresh_cached(
    user_id: int,
    tier: str,
    refresh_scope_start: _date_type,
    refresh_scope_end: _date_type,
    layer1_payload: dict[str, Any],
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    prior_plan_session_window: list[PlanSession],
    parsed_intent: ParsedIntent | None,
    plan_version_id: int,
    plan_version_id_parent: int,
    etl_version_set: dict[str, str],
    *,
    cache: Layer4Cache,
    plan_start_date: _date_type | None = None,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str | None = None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    capped_retries: int = 2,
    extended_thinking_budget: int | None = None,
    llm_caller: Callable | None = None,
    phase_caller: Any | None = None,
    seam_caller: Any | None = None,
    executor: Executor | None = None,
) -> Layer4Payload:
    """Per-entry cache wrapper around `llm_layer4_plan_refresh`.

    On hit: rebinds `plan_version_id` only (`suggestion_id` is always None
    on refresh per §7.12).

    Cache key per §9.1 plan_refresh formula. `model_seam_reviewer` collapses
    None → '' inside the key helper for Pattern B refreshes (T1/T2/T3
    intra-phase). `parsed_intent` is hashed when present.

    `max_tokens` / `extended_thinking_budget` of None routes through the
    underlying entry point's tier defaults; the cache key uses the
    resolved values via the per-tier constants the entry point exposes.
    For caching purposes here we use `0` as the sentinel for "let tier
    pick" so that the cache key is stable across calls that don't
    override the tier defaults.
    """
    layer1_hash = compute_payload_hash(layer1_payload)
    layer2_bundle_hash = _layer2_bundle_canonical_hash(layer2_bundle)
    layer3a_hash = compute_payload_hash(layer3a_payload)
    layer3b_hash = compute_payload_hash(layer3b_payload)
    prior_window_hash = compute_prior_plan_session_window_hash(prior_plan_session_window)
    parsed_intent_hash = (
        compute_payload_hash(parsed_intent) if parsed_intent is not None else None
    )

    key = plan_refresh_key(
        user_id=user_id,
        tier=tier,
        refresh_scope_start=refresh_scope_start,
        refresh_scope_end=refresh_scope_end,
        layer1_hash=layer1_hash,
        layer2_bundle_canonical_hash=layer2_bundle_hash,
        layer3a_hash=layer3a_hash,
        layer3b_hash=layer3b_hash,
        prior_plan_session_window_hash=prior_window_hash,
        parsed_intent_hash=parsed_intent_hash,
        etl_version_set=etl_version_set,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        max_tokens=max_tokens if max_tokens is not None else 0,
        capped_retries=capped_retries,
    )

    def _synthesize() -> Layer4Payload:
        return llm_layer4_plan_refresh(
            user_id,
            tier,  # type: ignore[arg-type]
            refresh_scope_start,
            refresh_scope_end,
            layer1_payload,
            layer2_bundle,
            layer3a_payload,
            layer3b_payload,
            prior_plan_session_window,
            parsed_intent,
            plan_version_id,
            plan_version_id_parent,
            etl_version_set,
            plan_start_date=plan_start_date,
            model_synthesizer=model_synthesizer,
            model_seam_reviewer=model_seam_reviewer,
            temperature=temperature,
            max_tokens=max_tokens,
            capped_retries=capped_retries,
            extended_thinking_budget=extended_thinking_budget,
            llm_caller=llm_caller,
            phase_caller=phase_caller,
            seam_caller=seam_caller,
            cache=cache,
            call_cache_key=key,
            executor=executor,
        )

    return cache.get_or_synthesize(
        cache_key=key,
        user_id=user_id,
        entry_point="plan_refresh",
        synthesizer=_synthesize,
        rebind_plan_version_id=plan_version_id,
    )


# ─── llm_layer4_plan_create_cached ────────────────────────────────────────


def llm_layer4_plan_create_cached(
    user_id: int,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    plan_start_date: _date_type,
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    cache: Layer4Cache,
    race_event_payload: RaceEventPayload | None = None,
    # D-73 Phase 5.2 BM3 — full-cone modality payload (primary-locale today
    # per impl-slice scope). Hashed into the cache key + threaded into the
    # per-phase render. Default None preserves existing call sites.
    layer2_modality_payload: Layer2ModalityPayload | None = None,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens_per_phase: int | None = None,
    capped_retries_per_phase: int = 2,
    extended_thinking_budget: int | None = None,
    seam_max_tokens: int | None = None,
    seam_thinking_budget: int | None = None,
    phase_caller: Any | None = None,
    seam_caller: Any | None = None,
    executor: Executor | None = None,
) -> Layer4Payload:
    """Per-entry cache wrapper around `llm_layer4_plan_create`.

    On hit: rebinds `plan_version_id` on the top-level Layer4Payload and
    every PlanSession.

    Cache key per §9.1 plan_create formula. The per-phase cache for
    Pattern A (§9.2) is internal to the entry point and is wired via the
    `cache` kwarg threaded through to `_run_pattern_a_engine`.

    Tunable params with `None` defaults route through the entry-point
    defaults; cache key uses `0` as the "tier defaults" sentinel so
    callers that don't override them get stable cache keys.
    """
    layer1_hash = compute_payload_hash(layer1_payload)
    layer2a_hash = compute_payload_hash(layer2a_payload)
    layer2b_hash = compute_payload_hash(layer2b_payload)
    layer2c_bundle_hash_val = _layer2c_bundle_hash(layer2c_payloads)
    layer2d_hash = compute_payload_hash(layer2d_payload)
    layer2e_hash = compute_payload_hash(layer2e_payload)
    layer3a_hash = compute_payload_hash(layer3a_payload)
    layer3b_hash = compute_payload_hash(layer3b_payload)
    # BM-3: hash the resolver payload so cache invalidates on terrain /
    # equipment / skill-toggle changes AND on `_MODALITY_OPTIONS_PER_DISCIPLINE`
    # code-deploy shape changes.
    layer2_modality_hash = (
        compute_payload_hash(layer2_modality_payload)
        if layer2_modality_payload is not None
        else None
    )

    key = plan_create_key(
        user_id=user_id,
        layer1_hash=layer1_hash,
        layer2a_hash=layer2a_hash,
        layer2b_hash=layer2b_hash,
        layer2c_bundle_hash=layer2c_bundle_hash_val,
        layer2d_hash=layer2d_hash,
        layer2e_hash=layer2e_hash,
        layer3a_hash=layer3a_hash,
        layer3b_hash=layer3b_hash,
        plan_start_date=plan_start_date,
        etl_version_set=etl_version_set,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        max_tokens_per_phase=max_tokens_per_phase if max_tokens_per_phase is not None else 0,
        capped_retries_per_phase=capped_retries_per_phase,
        layer2_modality_hash=layer2_modality_hash,
    )

    # Build the synthesizer kwargs — pass None defaults through to let the
    # entry point pick its module-level constants. Step 6a (this session)
    # wires the §9.2 per-phase cache by passing `cache=cache, call_cache_key
    # =key` through to `_run_pattern_a_engine`. The per-phase chain rolls
    # forward inside the engine via `compute_phase_cache_key` + the
    # `prev_accepted_output_hash` running variable.
    def _synthesize() -> Layer4Payload:
        kwargs: dict[str, Any] = {
            "race_event_payload": race_event_payload,
            "layer2_modality_payload": layer2_modality_payload,
            "model_synthesizer": model_synthesizer,
            "model_seam_reviewer": model_seam_reviewer,
            "temperature": temperature,
            "capped_retries_per_phase": capped_retries_per_phase,
            "phase_caller": phase_caller,
            "seam_caller": seam_caller,
            "cache": cache,
            "call_cache_key": key,
            "executor": executor,
        }
        if max_tokens_per_phase is not None:
            kwargs["max_tokens_per_phase"] = max_tokens_per_phase
        if extended_thinking_budget is not None:
            kwargs["extended_thinking_budget"] = extended_thinking_budget
        if seam_max_tokens is not None:
            kwargs["seam_max_tokens"] = seam_max_tokens
        if seam_thinking_budget is not None:
            kwargs["seam_thinking_budget"] = seam_thinking_budget

        return llm_layer4_plan_create(
            user_id,
            layer1_payload,
            layer2a_payload,
            layer2b_payload,
            layer2c_payloads,
            layer2d_payload,
            layer2e_payload,
            layer3a_payload,
            layer3b_payload,
            plan_start_date,
            plan_version_id,
            etl_version_set,
            **kwargs,
        )

    return cache.get_or_synthesize(
        cache_key=key,
        user_id=user_id,
        entry_point="plan_create",
        synthesizer=_synthesize,
        rebind_plan_version_id=plan_version_id,
    )


# ─── llm_layer4_race_week_brief_cached ────────────────────────────────────


def llm_layer4_race_week_brief_cached(
    user_id: int,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload,
    prior_plan_session_window: list[PlanSession],
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    cache: Layer4Cache,
    # D-73 Phase 5.2 BM3 — full-cone modality payload. Hashed into the
    # cache key + threaded into the brief prompt. Default None preserves
    # existing call sites (notably test fixtures pre-BM-3).
    layer2_modality_payload: Layer2ModalityPayload | None = None,
    # Best-fit re-model Slice 5 — training-substitution payload. Hashed into
    # the cache key + threaded into the brief prompt. Default None preserves
    # existing call sites (additive, alongside the modality payload).
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens: int = 6000,
    capped_retries: int = 2,
    extended_thinking_budget: int = 5500,
    today: _date_type | None = None,
    llm_caller: Callable | None = None,
) -> Layer4Payload:
    """Per-entry cache wrapper around `llm_layer4_race_week_brief`.

    On hit: rebinds `plan_version_id` only.

    Cache key per §9.1 race_week_brief formula. Today's date is
    intentionally NOT in the key — the orchestrator evicts these caches
    at midnight UTC via `cache_invalidation.evict_on_midnight_rollover()`
    per §9.3.
    """
    layer1_hash = compute_payload_hash(layer1_payload)
    layer2a_hash = compute_payload_hash(layer2a_payload)
    layer2b_hash = compute_payload_hash(layer2b_payload)
    layer2c_bundle_hash_val = _layer2c_bundle_hash(layer2c_payloads)
    layer2d_hash = compute_payload_hash(layer2d_payload)
    layer2e_hash = compute_payload_hash(layer2e_payload)
    layer3a_hash = compute_payload_hash(layer3a_payload)
    layer3b_hash = compute_payload_hash(layer3b_payload)
    prior_window_hash = compute_prior_plan_session_window_hash(prior_plan_session_window)
    # BM-3: hash the resolver payload so cache invalidates on terrain /
    # equipment / skill-toggle changes AND on `_MODALITY_OPTIONS_PER_DISCIPLINE`
    # code-deploy shape changes.
    layer2_modality_hash = (
        compute_payload_hash(layer2_modality_payload)
        if layer2_modality_payload is not None
        else None
    )
    # Slice 5: hash the substitution payload so the cache invalidates on
    # terrain / craft-inventory changes (deterministic half rides the existing
    # Layer 1 + 2B eviction cone; the hash slot is belt-and-braces).
    training_substitution_hash = (
        compute_payload_hash(training_substitution_payload)
        if training_substitution_payload is not None
        else None
    )

    key = race_week_brief_key(
        user_id=user_id,
        layer1_hash=layer1_hash,
        layer2a_hash=layer2a_hash,
        layer2b_hash=layer2b_hash,
        layer2c_bundle_hash=layer2c_bundle_hash_val,
        layer2d_hash=layer2d_hash,
        layer2e_hash=layer2e_hash,
        layer3a_hash=layer3a_hash,
        layer3b_hash=layer3b_hash,
        prior_plan_session_window_hash=prior_window_hash,
        etl_version_set=etl_version_set,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        capped_retries=capped_retries,
        layer2_modality_hash=layer2_modality_hash,
        training_substitution_hash=training_substitution_hash,
    )

    def _synthesize() -> Layer4Payload:
        return llm_layer4_race_week_brief(
            user_id,
            layer1_payload,
            layer2a_payload,
            layer2b_payload,
            layer2c_payloads,
            layer2d_payload,
            layer2e_payload,
            layer3a_payload,
            layer3b_payload,
            race_event_payload,
            prior_plan_session_window,
            plan_version_id,
            etl_version_set,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            capped_retries=capped_retries,
            extended_thinking_budget=extended_thinking_budget,
            today=today,
            llm_caller=llm_caller,
            layer2_modality_payload=layer2_modality_payload,
            training_substitution_payload=training_substitution_payload,
        )

    return cache.get_or_synthesize(
        cache_key=key,
        user_id=user_id,
        entry_point="race_week_brief",
        synthesizer=_synthesize,
        rebind_plan_version_id=plan_version_id,
    )
