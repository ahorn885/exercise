"""Layer 4 — `llm_layer4_plan_create` Pattern A orchestration (Step 4f).

Implements `Layer4_Spec.md` §3.1 (entry-point signature), §4.2 (input
validation), §5.1 (pattern routing — A always), §5.2 (Pattern A algorithm:
per-phase synthesis loop + seam-review loop + final cross-phase validator
pass), §5.5 (capped retry shared across validator-driven + seam-driven
re-syntheses per phase), §6.1 (phase boundary computation), §6.2 (β
propose-patch authority).

Pattern A is the per-phase decomposition pattern — sequential per-phase
synthesis with the prior phase's accepted output passed as context, followed
by LLM seam review between adjacent-phase pairs (β propose-patch authority),
followed by a final cross-phase validator pass over the union of sessions.

The driver also exposes `synthesize_pattern_a_for_refresh()` — the shared
engine consumed by `plan_refresh.py`'s T3 cross-phase routing per §6.3
(Step 4f closes the `tier_t3_cross_phase_requires_pattern_a` raise path
shipped in Step 4d).
"""

from __future__ import annotations

import uuid
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date as _date_type
from typing import Any, Literal

from layer4.cache import Layer4Cache
from layer4.context import (
    Layer2APayload,
    Layer2BPayload,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer2ModalityPayload,
    Layer3APayload,
    Layer3BPayload,
    RaceEventPayload,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.hashing import compute_accepted_output_hash, compute_phase_cache_key
from layer4.payload import (
    Layer4Payload,
    Observation,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    RuleFailure,
    SeamReview,
    SynthesisMetadata,
    ValidatorResult,
)
from layer4.per_phase import (
    DEFAULT_EXTENDED_THINKING_BUDGET as _PHASE_THINKING_DEFAULT,
    DEFAULT_MAX_TOKENS as _PHASE_MAX_TOKENS_DEFAULT,
    LLMCaller as _PhaseLLMCaller,
    PhaseSynthesisResult,
    build_synthesis_metadata_from_result,
    synthesize_phase,
)
from layer4.phase_structure import phase_structure_from_3b
from layer4.seam_review import (
    DEFAULT_EXTENDED_THINKING_BUDGET as _SEAM_THINKING_DEFAULT,
    DEFAULT_MAX_TOKENS as _SEAM_MAX_TOKENS_DEFAULT,
    SeamReviewCallResult,
    SeamReviewerCaller,
    compose_seam_review_row,
    review_seam,
)
from layer4.validator import ValidatorContext, validate_layer4_payload


# ─── Input validation (Layer4_Spec.md §4.2) ──────────────────────────────────


def _validate_plan_create_inputs(
    user_id: int,
    layer1_payload: dict[str, Any] | None,
    layer2a_payload: Layer2APayload | None,
    layer2b_payload: Layer2BPayload | None,
    layer2c_payloads: dict[str, Layer2CPayload] | None,
    layer2d_payload: Layer2DPayload | None,
    layer2e_payload: Layer2EPayload | None,
    layer3a_payload: Layer3APayload | None,
    layer3b_payload: Layer3BPayload | None,
    plan_start_date: _date_type,
    plan_version_id: int,
    race_event_payload: RaceEventPayload | None,
) -> None:
    """Apply §4.2 plan_create preconditions. Fail-fast — raises
    `Layer4InputError` on first failing rule."""
    if layer1_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer1_payload is None"
        )
    if layer2a_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer2a_payload is None"
        )
    if layer2b_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer2b_payload is None"
        )
    if not layer2c_payloads:
        raise Layer4InputError(
            "missing_upstream_payload",
            detail="layer2c_payloads is None or empty",
        )
    if layer2d_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer2d_payload is None"
        )
    if layer2e_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer2e_payload is None"
        )
    if layer3a_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer3a_payload is None"
        )
    if layer3b_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer3b_payload is None"
        )

    today = _date_type.today()
    if plan_start_date < today:
        raise Layer4InputError(
            "plan_start_date_in_past",
            detail=(
                f"plan_start_date={plan_start_date.isoformat()} is before today "
                f"({today.isoformat()}); backdating not supported in v1"
            ),
        )

    if plan_version_id <= 0:
        raise Layer4InputError(
            "plan_version_id_unset",
            detail=(
                f"plan_version_id={plan_version_id} is not a positive int; caller "
                "must pre-allocate a plan_versions row"
            ),
        )

    # 3B mode-consistency: when race_event_payload non-None, check
    # time_to_event_weeks matches the gap between plan_start_date and
    # event_date (when 3B has been re-run to populate the field).
    if (
        race_event_payload is not None
        and layer3b_payload.time_to_event_weeks is not None
    ):
        expected_weeks = (race_event_payload.event_date - plan_start_date).days // 7
        delta = abs(layer3b_payload.time_to_event_weeks - expected_weeks)
        if delta > 1:
            raise Layer4InputError(
                "time_to_event_weeks_mismatch",
                detail=(
                    f"layer3b_payload.time_to_event_weeks="
                    f"{layer3b_payload.time_to_event_weeks} differs from "
                    f"(event_date - plan_start_date) // 7 = {expected_weeks} by "
                    f"more than ±1 week"
                ),
            )

    # 2A discipline_weights sum to ~1.0 — pydantic doesn't enforce; check
    # here as a defensive read against drift.
    included = [
        d for d in layer2a_payload.disciplines if d.inclusion == "included"
    ]
    if included:
        weight_sum = sum(d.load_weight.value for d in included)
        if abs(weight_sum - 1.0) > 0.05:
            raise Layer4InputError(
                "discipline_weights_invalid",
                detail=(
                    f"2A included disciplines load_weight sum={weight_sum:.3f}; "
                    "must be ≈1.0 within ±0.05 tolerance"
                ),
            )


# ─── Pattern A engine: synthesize all phases + seam reviews ──────────────────


@dataclass
class _PatternAResult:
    """Internal Pattern A engine output. Carries everything the caller needs
    to compose a Layer4Payload (mode + scope dates filled by the caller)."""

    all_sessions: list[PlanSession]
    """Union of all phases' accepted sessions, sorted by date."""

    phase_structure: PhaseStructure
    """The PhaseStructure with each PhaseSpec.synthesis_metadata overwritten
    from the per-phase synthesis call results."""

    seam_reviews: list[SeamReview]
    """One entry per adjacent-phase pair reviewed; empty when only one phase
    was synthesized."""

    validator_results: list[ValidatorResult]
    """Cumulative — per-phase validator passes + the final cross-phase pass.
    Last entry has accepted=True."""

    notable_observations: list[Observation]
    """Best-effort, seam-unresolved, intensity-modulated, cross-phase
    failures — populated as encountered during orchestration."""

    input_tokens_total: int
    output_tokens_total: int
    latency_ms_total: int
    llm_call_count: int


def _compute_total_weeks(
    layer3b_payload: Layer3BPayload,
    plan_start_date: _date_type,
    race_event_payload: RaceEventPayload | None,
) -> int | None:
    """Per `Layer4_Spec.md` §6.1: event-mode uses layer3b.time_to_event_weeks
    (or event_date - plan_start_date when 3B field is None). Open-ended mode
    defaults to 12 weeks via phase_structure_from_3b's helper default."""
    if layer3b_payload.time_to_event_weeks is not None:
        return layer3b_payload.time_to_event_weeks
    if race_event_payload is not None:
        return max(1, (race_event_payload.event_date - plan_start_date).days // 7)
    return None  # phase_structure_from_3b defaults to 12


def _index_for_re_prompt(
    direction: Literal["re_prompt_prior", "re_prompt_next"],
    seam_index: int,
) -> int:
    """Map a seam reviewer's direction to the phase index to re-synthesize.
    Seam `seam_index` sits between phases [seam_index] and [seam_index+1].
    """
    if direction == "re_prompt_prior":
        return seam_index
    return seam_index + 1


def _serialize_phase_result_with_meta(
    result: PhaseSynthesisResult,
    meta: SynthesisMetadata,
) -> dict[str, Any]:
    """Project a PhaseSynthesisResult + its SynthesisMetadata into a
    JSON-serializable dict for the per-phase cache (`Layer4_Spec.md` §9.2).

    The cached shape covers everything the engine needs to reconstruct a
    PhaseSynthesisResult on a hit. Token / latency / llm_call_count fields
    are NOT cached — those reflect the original LLM call, and per §9.6
    cache hits stamp ZERO on `Layer4Payload.latency_ms_total` for the
    skipped synthesis (synthesis-only metric)."""
    return {
        "phase_name": result.phase_name,
        "sessions": [s.model_dump(mode="json") for s in result.sessions],
        "synthesis_metadata": meta.model_dump(mode="json"),
        "phase_synthesis_notes": result.phase_synthesis_notes,
        "opportunities": list(result.opportunities),
        "validator_results": [
            vr.model_dump(mode="json") for vr in result.validator_results
        ],
        "cap_hit": result.cap_hit,
        "retries_used": result.retries_used,
    }


def _hydrate_phase_result_with_meta(
    cached: dict[str, Any],
) -> tuple[PhaseSynthesisResult, SynthesisMetadata]:
    """Reverse of `_serialize_phase_result_with_meta`. The returned
    PhaseSynthesisResult carries ZERO token/latency/llm_call_count fields
    because no LLM call fired on this code path; the cached
    `synthesis_metadata` keeps the original call's accounting for
    chain-hashing fidelity per §9.2."""
    result = PhaseSynthesisResult(
        phase_name=cached["phase_name"],
        sessions=[PlanSession.model_validate(s) for s in cached["sessions"]],
        phase_synthesis_notes=cached["phase_synthesis_notes"],
        opportunities=list(cached["opportunities"]),
        validator_results=[
            ValidatorResult.model_validate(vr) for vr in cached["validator_results"]
        ],
        cap_hit=cached["cap_hit"],
        retries_used=cached["retries_used"],
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
        llm_call_count=0,
    )
    meta = SynthesisMetadata.model_validate(cached["synthesis_metadata"])
    return result, meta


def _build_final_payload_for_validation(
    *,
    user_id: int,
    sessions: list[PlanSession],
    plan_version_id: int,
    scope_start: _date_type,
    scope_end: _date_type,
    model: str,
    temperature: float,
    etl_version_set: dict[str, str],
    phase_structure: PhaseStructure,
    seam_reviews: list[SeamReview],
    mode: Literal["plan_create", "plan_refresh"],
    model_seam_reviewer: str | None,
) -> Layer4Payload:
    """Construct a Layer4Payload for the FINAL cross-phase validator pass.
    Stub validator_results with one accepted entry so the payload
    invariants hold; the real validator pass runs against this payload."""
    return Layer4Payload(
        user_id=user_id,
        mode=mode,
        plan_version_id=plan_version_id,
        scope_start_date=scope_start,
        scope_end_date=scope_end,
        model_synthesizer=model,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        pattern="A",
        latency_ms_total=0,
        input_tokens_total=0,
        output_tokens_total=0,
        llm_call_count=0,
        etl_version_set=etl_version_set,
        sessions=sessions,
        phase_structure=phase_structure,
        seam_reviews=seam_reviews,
        shape_override=None,
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


def _build_phase_structure_with_metadata(
    phase_structure: PhaseStructure,
    synthesis_metadata_by_index: dict[int, SynthesisMetadata],
) -> PhaseStructure:
    """Return a new PhaseStructure with synthesis_metadata overwritten for
    each phase that was synthesized (or hit-from-cache) this call. Phases
    not in `synthesis_metadata_by_index` keep their (zero or carryover)
    metadata.

    Note the per-phase metadata is supplied as a separate dict (vs derived
    from the PhaseSynthesisResult) because cache hits return zeroed
    PhaseSynthesisResult.input_tokens/etc but the canonical metadata for
    the §9.2 chain hash + downstream observability is the cached one with
    the original LLM-call accounting preserved."""
    new_phases: list[PhaseSpec] = []
    for i, phase in enumerate(phase_structure.phases):
        if i in synthesis_metadata_by_index:
            new_phases.append(
                PhaseSpec(
                    phase_name=phase.phase_name,
                    start_date=phase.start_date,
                    end_date=phase.end_date,
                    weeks=phase.weeks,
                    intended_volume_band=phase.intended_volume_band,
                    intended_intensity_distribution=phase.intended_intensity_distribution,
                    synthesis_metadata=synthesis_metadata_by_index[i],
                )
            )
        else:
            new_phases.append(phase)
    return PhaseStructure(
        phases=new_phases,
        total_weeks=phase_structure.total_weeks,
        derived_from=phase_structure.derived_from,
    )


def _emit_intensity_modulated_observation(
    sessions: list[PlanSession],
) -> Observation | None:
    """§8.6/§8.7: when ANY session carries `intensity_modulated`, emit a
    single orchestrator-side observation referencing the affected count."""
    affected = [
        s.session_id for s in sessions if "intensity_modulated" in s.coaching_flags
    ]
    if not affected:
        return None
    return Observation(
        category="intensity_modulated",
        text=(
            "Synthesizer modulated intensity on "
            f"{len(affected)} session(s); see session_notes for the rationale."
        ),
        evidence_basis=["Layer4_Spec.md §8.6 + §8.7"],
        elevates_to_hitl=False,
    )


def _run_pattern_a_engine(
    *,
    user_id: int,
    phase_structure: PhaseStructure,
    phase_indices_to_synthesize: list[int],
    carryover_sessions_by_phase_index: dict[int, list[PlanSession]],
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    layer2b_payload: Layer2BPayload | None,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
    layer2e_payload: Layer2EPayload | None,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload | None,
    plan_version_id: int,
    etl_version_set: dict[str, str],
    mode: Literal["plan_create", "plan_refresh"],
    model_synthesizer: str,
    model_seam_reviewer: str,
    temperature: float,
    max_tokens_per_phase: int,
    extended_thinking_budget: int,
    capped_retries_per_phase: int,
    seam_max_tokens: int,
    seam_thinking_budget: int,
    phase_caller: _PhaseLLMCaller | None,
    seam_caller: SeamReviewerCaller | None,
    cache: Layer4Cache | None = None,
    call_cache_key: str | None = None,
    executor: Executor | None = None,
    layer2_modality_payload: Layer2ModalityPayload | None = None,
) -> _PatternAResult:
    """Run the Pattern A loop per `Layer4_Spec.md` §5.2.

    `phase_indices_to_synthesize` is the subset of phase_structure.phases to
    actually invoke the synthesizer on. For plan_create: every phase. For
    T3 cross-phase plan_refresh: only phases overlapping the refresh scope.

    `carryover_sessions_by_phase_index` provides sessions for phases NOT in
    `phase_indices_to_synthesize` (T3 cross-phase carry-over from
    prior_plan_session_window). Empty for plan_create.
    """
    session_id_prefix = uuid.uuid4().hex[:8]
    results_by_index: dict[int, PhaseSynthesisResult] = {}
    synthesis_metadata_by_index: dict[int, SynthesisMetadata] = {}
    notable_observations: list[Observation] = []
    seam_reviews_by_index: dict[int, SeamReview] = {}
    validator_results: list[ValidatorResult] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0
    llm_call_count = 0
    retries_used_per_phase: dict[int, int] = {}

    # §9.2 per-phase cache chain — `prev_accepted_output_hash` rolls forward
    # through each accepted phase output (None for phase 0, collapsing to ''
    # inside `compute_phase_cache_key`). Only used when `cache` +
    # `call_cache_key` are both provided.
    prev_accepted_output_hash: str | None = None
    cache_entry_point: Literal["plan_create", "plan_refresh"] = (
        "plan_create" if mode == "plan_create" else "plan_refresh"
    )

    # --- Per-phase synthesis (sequential) ---------------------------------
    for i, phase in enumerate(phase_structure.phases):
        if i not in phase_indices_to_synthesize:
            continue

        # Determine prior-phase sessions for the prompt's continuity context.
        prior_phase_sessions: list[PlanSession] = []
        if i > 0:
            prev_idx = i - 1
            if prev_idx in results_by_index:
                prior_phase_sessions = results_by_index[prev_idx].sessions
            elif prev_idx in carryover_sessions_by_phase_index:
                prior_phase_sessions = carryover_sessions_by_phase_index[prev_idx]
            # else: synthetic prior (start_phase != 'Base' first-phase case);
            # per_phase.render_user_prompt handles None/empty gracefully.

        def _synth_this_phase(
            _i: int = i,
            _phase: PhaseSpec = phase,
            _prior: list[PlanSession] = prior_phase_sessions,
        ) -> PhaseSynthesisResult:
            return synthesize_phase(
                user_id=user_id,
                phase_spec=_phase,
                phase_structure=phase_structure,
                phase_index_in_plan=_i,
                layer1_payload=layer1_payload,
                layer2a_payload=layer2a_payload,
                layer2b_payload=layer2b_payload,
                layer2c_payloads=layer2c_payloads,
                layer2d_payload=layer2d_payload,
                layer2e_payload=layer2e_payload,
                layer3a_payload=layer3a_payload,
                layer3b_payload=layer3b_payload,
                race_event_payload=race_event_payload,
                prior_phase_sessions=_prior,
                plan_version_id=plan_version_id,
                etl_version_set=etl_version_set,
                mode=mode,
                model=model_synthesizer,
                temperature=temperature,
                max_tokens=max_tokens_per_phase,
                extended_thinking_budget=extended_thinking_budget,
                capped_retries=capped_retries_per_phase,
                retries_already_used=0,
                llm_caller=phase_caller,
                session_id_prefix=f"{session_id_prefix}-p{_i}",
                layer2_modality_payload=layer2_modality_payload,
            )

        if cache is not None and call_cache_key is not None:
            # Per §9.2: cache key chains via prev_accepted_output_hash.
            phase_key = compute_phase_cache_key(
                call_cache_key=call_cache_key,
                phase_name=phase.phase_name,
                phase_index=i,
                prev_accepted_output_hash=prev_accepted_output_hash,
            )

            def _serialize_synth(
                _phase_name: str = phase.phase_name,
            ) -> dict[str, Any]:
                r = _synth_this_phase()
                m = build_synthesis_metadata_from_result(
                    r, model=model_synthesizer, temperature=temperature
                )
                return _serialize_phase_result_with_meta(r, m)

            cached_dict = cache.get_phase_or_synthesize(
                phase_key=phase_key,
                phase_idx=i,
                phase_name=phase.phase_name,
                user_id=user_id,
                entry_point=cache_entry_point,
                synthesizer=_serialize_synth,
            )
            result, meta = _hydrate_phase_result_with_meta(cached_dict)
        else:
            result = _synth_this_phase()
            meta = build_synthesis_metadata_from_result(
                result, model=model_synthesizer, temperature=temperature
            )

        results_by_index[i] = result
        synthesis_metadata_by_index[i] = meta
        retries_used_per_phase[i] = result.retries_used
        validator_results.extend(result.validator_results)
        total_input_tokens += result.input_tokens
        total_output_tokens += result.output_tokens
        total_latency_ms += result.latency_ms
        llm_call_count += result.llm_call_count
        # Roll the §9.2 chain hash forward for the next phase's key.
        prev_accepted_output_hash = compute_accepted_output_hash(
            result.sessions, meta
        )

        if result.cap_hit:
            notable_observations.append(
                Observation(
                    category="best_effort_plan",
                    text=(
                        f"Phase {phase.phase_name}: validator cap hit; best-effort accepted."
                    ),
                    evidence_basis=["Layer4_Spec.md §5.5"],
                    elevates_to_hitl=True,
                )
            )
        for opp in result.opportunities:
            notable_observations.append(
                Observation(
                    category="opportunity",
                    text=opp[:240],
                    evidence_basis=[f"per_phase synthesizer ({phase.phase_name})"],
                    elevates_to_hitl=False,
                )
            )

    # --- Seam reviews (iter-1 parallel; iter-2 + re-synth sequential
    #     per §6.2 + §6.3 per-seam cap + per §5.2 closing-note concurrency
    #     framing) ---------------------------------------------------------
    discipline_mix = (
        [
            d.discipline_id
            for d in layer2a_payload.disciplines
            if d.inclusion == "included"
        ]
        if layer2a_payload is not None
        else []
    )
    mode_str = layer3b_payload.periodization_shape.mode
    start_phase_str = layer3b_payload.periodization_shape.start_phase
    race_format_str = (
        race_event_payload.race_format if race_event_payload else "open_ended"
    )
    event_date = race_event_payload.event_date if race_event_payload else None

    # Identify seams to review per §6.3: skip pairs where NEITHER side was
    # synthesized this call (carryover-only boundaries were reviewed during
    # the original plan_create + don't repeat here).
    pairs_to_review: list[int] = []
    for seam_idx in range(len(phase_structure.phases) - 1):
        prior_synthesized = seam_idx in phase_indices_to_synthesize
        next_synthesized = (seam_idx + 1) in phase_indices_to_synthesize
        if not prior_synthesized and not next_synthesized:
            continue
        pairs_to_review.append(seam_idx)

    # Iter-1 LLM calls fire in parallel (per `Layer4_Spec.md` §5.2 closing
    # note: "Seam reviews COULD parallelize across non-overlapping pairs ...
    # seams 0..N-2 are independent in their LLM-call inputs"). Semantic
    # tradeoff: when seam i iter-1 triggers a re-synthesis of phase i+1,
    # seam i+1's iter-1 — already fired in parallel against the ORIGINAL
    # phase i+1 — does not re-fire. The §5.2 step-5 final cross-phase
    # validator pass + seam i+1's iter-2 (if its iter-1 ALSO flagged) still
    # catch downstream issues. Schema-violations from iter-1 raise via
    # `Layer4OutputError` and propagate through the executor.
    def _iter1_task(
        seam_idx: int,
    ) -> tuple[int, SeamReviewCallResult]:
        prior_phase_local = phase_structure.phases[seam_idx]
        next_phase_local = phase_structure.phases[seam_idx + 1]
        prior_synthesized_local = seam_idx in phase_indices_to_synthesize
        next_synthesized_local = (seam_idx + 1) in phase_indices_to_synthesize
        prior_sessions_local = (
            results_by_index[seam_idx].sessions
            if prior_synthesized_local
            else carryover_sessions_by_phase_index.get(seam_idx, [])
        )
        next_sessions_local = (
            results_by_index[seam_idx + 1].sessions
            if next_synthesized_local
            else carryover_sessions_by_phase_index.get(seam_idx + 1, [])
        )
        call_1_local = review_seam(
            seam_index=seam_idx,
            prior_phase_spec=prior_phase_local,
            next_phase_spec=next_phase_local,
            prior_phase_sessions=prior_sessions_local,
            next_phase_sessions=next_sessions_local,
            layer2a_payload=layer2a_payload,
            layer2d_payload=layer2d_payload,
            discipline_mix=discipline_mix,
            mode=mode_str,
            start_phase=start_phase_str,
            race_format=race_format_str,
            event_date=event_date,
            seam_iteration=1,
            prior_seam_issues=[],
            model=model_seam_reviewer,
            temperature=0.15,
            max_tokens=seam_max_tokens,
            extended_thinking_budget=seam_thinking_budget,
            caller=seam_caller,
        )
        return (seam_idx, call_1_local)

    iter1_results: list[tuple[int, SeamReviewCallResult]] = []
    if len(pairs_to_review) >= 2 and executor is not None:
        iter1_results = list(executor.map(_iter1_task, pairs_to_review))
    elif len(pairs_to_review) >= 2:
        with ThreadPoolExecutor(
            max_workers=min(4, len(pairs_to_review))
        ) as _default_exe:
            iter1_results = list(_default_exe.map(_iter1_task, pairs_to_review))
    elif len(pairs_to_review) == 1:
        iter1_results = [_iter1_task(pairs_to_review[0])]
    # else: no seams to review (single-phase plan or all-carryover T3 edge).

    # Process iter-1 results sequentially in seam_idx order — verdict
    # semantics + per-seam iter-2 re-synthesis when triggered. Per-phase
    # retry budget is shared with validator-driven retries (§5.5) and is
    # consumed in seam_idx order, so a phase targeted by two seams may
    # exhaust budget on the second.
    for seam_idx, call_1 in iter1_results:
        prior_phase = phase_structure.phases[seam_idx]
        next_phase = phase_structure.phases[seam_idx + 1]
        total_input_tokens += call_1.input_tokens
        total_output_tokens += call_1.output_tokens
        total_latency_ms += call_1.latency_ms
        llm_call_count += 1

        verdict = call_1.verdict
        direction = call_1.proposed_patch_direction
        triggered_resynthesis = False
        re_prompted_phase_name: (
            Literal["Base", "Build", "Peak", "Taper"] | None
        ) = None

        if verdict in ("approved", "flagged_minor"):
            # Record-only. Emit Observation on flagged_minor per §6.2.
            if verdict == "flagged_minor" and call_1.seam_issues:
                summary = "; ".join(call_1.seam_issues)[:240]
                notable_observations.append(
                    Observation(
                        category="warning",
                        text=summary,
                        evidence_basis=[
                            f"seam_review {prior_phase.phase_name}→{next_phase.phase_name}"
                        ],
                        elevates_to_hitl=False,
                    )
                )
            seam_reviews_by_index[seam_idx] = compose_seam_review_row(
                seam_index=seam_idx,
                prior_phase_name=prior_phase.phase_name,  # type: ignore[arg-type]
                next_phase_name=next_phase.phase_name,  # type: ignore[arg-type]
                call_result=call_1,
                reviewer_model=model_seam_reviewer,
                triggered_resynthesis=False,
                re_prompted_phase_name=None,
            )
            continue

        if direction == "accept_with_observation":
            # Per §6.2: emit Observation(warning, elevates_to_hitl=True).
            summary = "; ".join(call_1.seam_issues)[:240]
            notable_observations.append(
                Observation(
                    category="warning",
                    text=summary,
                    evidence_basis=[
                        f"seam_review {prior_phase.phase_name}→{next_phase.phase_name}"
                    ],
                    elevates_to_hitl=True,
                )
            )
            seam_reviews_by_index[seam_idx] = compose_seam_review_row(
                seam_index=seam_idx,
                prior_phase_name=prior_phase.phase_name,  # type: ignore[arg-type]
                next_phase_name=next_phase.phase_name,  # type: ignore[arg-type]
                call_result=call_1,
                reviewer_model=model_seam_reviewer,
                triggered_resynthesis=False,
                re_prompted_phase_name=None,
            )
            continue

        # verdict ∈ {flagged_major, patched} with direction ∈
        # {re_prompt_prior, re_prompt_next}: apply propose-patch authority.
        assert direction in ("re_prompt_prior", "re_prompt_next")
        target_idx = _index_for_re_prompt(direction, seam_idx)

        # Only re-synthesize a phase that was actually synthesized this call
        # (cannot re-synthesize carryover/unaffected phases per §6.2 bounds).
        target_in_scope = target_idx in phase_indices_to_synthesize
        target_budget_remaining = (
            capped_retries_per_phase - retries_used_per_phase.get(target_idx, 0)
        )

        if not target_in_scope or target_budget_remaining <= 0:
            # Cannot re-synthesize — emit seam_unresolved per §6.2.
            summary = "; ".join(call_1.seam_issues)[:240]
            notable_observations.append(
                Observation(
                    category="seam_unresolved",
                    text=summary,
                    evidence_basis=[
                        f"seam_review {prior_phase.phase_name}→{next_phase.phase_name}; "
                        f"retry budget exhausted"
                    ],
                    elevates_to_hitl=True,
                )
            )
            seam_reviews_by_index[seam_idx] = compose_seam_review_row(
                seam_index=seam_idx,
                prior_phase_name=prior_phase.phase_name,  # type: ignore[arg-type]
                next_phase_name=next_phase.phase_name,  # type: ignore[arg-type]
                call_result=call_1,
                reviewer_model=model_seam_reviewer,
                triggered_resynthesis=False,
                re_prompted_phase_name=None,
            )
            continue

        # Re-synthesize the targeted phase with the seam issues merged in.
        target_phase = phase_structure.phases[target_idx]
        target_prior_phase_sessions: list[PlanSession] = []
        if target_idx > 0:
            prev_idx = target_idx - 1
            if prev_idx in results_by_index:
                target_prior_phase_sessions = results_by_index[prev_idx].sessions
            elif prev_idx in carryover_sessions_by_phase_index:
                target_prior_phase_sessions = carryover_sessions_by_phase_index[prev_idx]

        re_result = synthesize_phase(
            user_id=user_id,
            phase_spec=target_phase,
            phase_structure=phase_structure,
            phase_index_in_plan=target_idx,
            layer1_payload=layer1_payload,
            layer2a_payload=layer2a_payload,
            layer2b_payload=layer2b_payload,
            layer2c_payloads=layer2c_payloads,
            layer2d_payload=layer2d_payload,
            layer2e_payload=layer2e_payload,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            race_event_payload=race_event_payload,
            prior_phase_sessions=target_prior_phase_sessions,
            plan_version_id=plan_version_id,
            etl_version_set=etl_version_set,
            mode=mode,
            model=model_synthesizer,
            temperature=temperature,
            max_tokens=max_tokens_per_phase,
            extended_thinking_budget=extended_thinking_budget,
            capped_retries=capped_retries_per_phase,
            seam_issues=call_1.seam_issues,
            seam_direction=direction,
            retries_already_used=retries_used_per_phase[target_idx] + 1,
            llm_caller=phase_caller,
            session_id_prefix=f"{session_id_prefix}-p{target_idx}-seamretry",
            layer2_modality_payload=layer2_modality_payload,
        )
        results_by_index[target_idx] = re_result
        # Refresh the per-phase metadata so the final PhaseStructure carries
        # the re-synthesis's token/latency/retries accounting rather than the
        # initial synthesis's. Seam-driven re-synth is NOT cache-wired per
        # §9.2 — the spec gap on chaining new context-with-seam-issues into
        # phase_key is tracked as a Step 6 carry-forward.
        synthesis_metadata_by_index[target_idx] = build_synthesis_metadata_from_result(
            re_result, model=model_synthesizer, temperature=temperature
        )
        retries_used_per_phase[target_idx] = re_result.retries_used
        validator_results.extend(re_result.validator_results)
        total_input_tokens += re_result.input_tokens
        total_output_tokens += re_result.output_tokens
        total_latency_ms += re_result.latency_ms
        llm_call_count += re_result.llm_call_count
        triggered_resynthesis = True
        re_prompted_phase_name = target_phase.phase_name  # type: ignore[assignment]

        # Re-run THIS seam review exactly once (iteration 2) per §6.2 cap.
        prior_sessions_iter2 = (
            results_by_index[seam_idx].sessions
            if seam_idx in results_by_index
            else carryover_sessions_by_phase_index.get(seam_idx, [])
        )
        next_sessions_iter2 = (
            results_by_index[seam_idx + 1].sessions
            if (seam_idx + 1) in results_by_index
            else carryover_sessions_by_phase_index.get(seam_idx + 1, [])
        )

        call_2 = review_seam(
            seam_index=seam_idx,
            prior_phase_spec=prior_phase,
            next_phase_spec=next_phase,
            prior_phase_sessions=prior_sessions_iter2,
            next_phase_sessions=next_sessions_iter2,
            layer2a_payload=layer2a_payload,
            layer2d_payload=layer2d_payload,
            discipline_mix=discipline_mix,
            mode=mode_str,
            start_phase=start_phase_str,
            race_format=race_format_str,
            event_date=event_date,
            seam_iteration=2,
            prior_seam_issues=call_1.seam_issues,
            model=model_seam_reviewer,
            temperature=0.15,
            max_tokens=seam_max_tokens,
            extended_thinking_budget=seam_thinking_budget,
            caller=seam_caller,
        )
        total_input_tokens += call_2.input_tokens
        total_output_tokens += call_2.output_tokens
        total_latency_ms += call_2.latency_ms
        llm_call_count += 1

        # Per-seam cap = 2; if iteration 2 still flags, emit
        # seam_unresolved. Otherwise the record is the final verdict.
        if call_2.verdict in ("flagged_major", "patched") and call_2.seam_issues:
            summary = "; ".join(call_2.seam_issues)[:240]
            notable_observations.append(
                Observation(
                    category="seam_unresolved",
                    text=summary,
                    evidence_basis=[
                        f"seam_review {prior_phase.phase_name}→{next_phase.phase_name}; "
                        f"iter-2 still flagged"
                    ],
                    elevates_to_hitl=True,
                )
            )
        seam_reviews_by_index[seam_idx] = compose_seam_review_row(
            seam_index=seam_idx,
            prior_phase_name=prior_phase.phase_name,  # type: ignore[arg-type]
            next_phase_name=next_phase.phase_name,  # type: ignore[arg-type]
            call_result=call_2,
            reviewer_model=model_seam_reviewer,
            triggered_resynthesis=triggered_resynthesis,
            re_prompted_phase_name=re_prompted_phase_name,
        )

    # --- Compose all_sessions (synthesized + carryover) sorted by date ---
    all_sessions: list[PlanSession] = []
    for i in range(len(phase_structure.phases)):
        if i in results_by_index:
            all_sessions.extend(results_by_index[i].sessions)
        elif i in carryover_sessions_by_phase_index:
            all_sessions.extend(carryover_sessions_by_phase_index[i])
    all_sessions.sort(key=lambda s: (s.date, s.session_index_in_day))

    # --- Update PhaseStructure with the per-phase synthesis metadata -----
    updated_phase_structure = _build_phase_structure_with_metadata(
        phase_structure, synthesis_metadata_by_index
    )

    # --- Final cross-phase validator pass (§5.2 step 5) ------------------
    seam_reviews_list = [
        seam_reviews_by_index[i]
        for i in sorted(seam_reviews_by_index)
    ]
    if all_sessions:
        scope_start = all_sessions[0].date
        scope_end = all_sessions[-1].date
    else:
        scope_start = phase_structure.phases[0].start_date
        scope_end = phase_structure.phases[-1].end_date

    final_payload = _build_final_payload_for_validation(
        user_id=user_id,
        sessions=all_sessions,
        plan_version_id=plan_version_id,
        scope_start=scope_start,
        scope_end=scope_end,
        model=model_synthesizer,
        temperature=temperature,
        etl_version_set=etl_version_set,
        phase_structure=updated_phase_structure,
        seam_reviews=seam_reviews_list,
        mode=mode,
        model_seam_reviewer=model_seam_reviewer,
    )
    ctx = ValidatorContext(
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payloads=dict(layer2c_payloads),
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        race_event=race_event_payload,
    )
    final_validator = validate_layer4_payload(
        final_payload, ctx, pass_index=len(validator_results)
    )

    # Per §5.5: cross-phase blocker failures cannot be retried; demote to
    # warnings + emit best_effort_plan observation; append a synthesized
    # accepted ValidatorResult so the Layer4Payload invariant holds.
    if final_validator.accepted:
        validator_results.append(final_validator)
    else:
        # Distinguish: if a blocker survives the final pass after per-phase
        # retries, emit best_effort_plan + demote.
        demoted = [
            RuleFailure(
                rule_name=f.rule_name,
                phase_name=f.phase_name,
                severity="warning",
                detail=f.detail,
                affected_session_ids=f.affected_session_ids,
            )
            for f in final_validator.rule_failures
        ]
        validator_results.append(final_validator)
        validator_results.append(
            ValidatorResult(
                pass_index=final_validator.pass_index + 1,
                accepted=True,
                rule_failures=demoted,
                retried_phase_names=[],
            )
        )
        already_have_best_effort = any(
            o.category == "best_effort_plan" for o in notable_observations
        )
        if not already_have_best_effort:
            notable_observations.append(
                Observation(
                    category="best_effort_plan",
                    text=(
                        "Final cross-phase validator pass failed; cross-phase "
                        "blocker failures demoted to warning per §5.5."
                    ),
                    evidence_basis=["Layer4_Spec.md §5.5"],
                    elevates_to_hitl=True,
                )
            )

    intensity_obs = _emit_intensity_modulated_observation(all_sessions)
    if intensity_obs is not None:
        notable_observations.append(intensity_obs)

    return _PatternAResult(
        all_sessions=all_sessions,
        phase_structure=updated_phase_structure,
        seam_reviews=seam_reviews_list,
        validator_results=validator_results,
        notable_observations=notable_observations,
        input_tokens_total=total_input_tokens,
        output_tokens_total=total_output_tokens,
        latency_ms_total=total_latency_ms,
        llm_call_count=llm_call_count,
    )


# ─── Layer4Payload composition (Pattern A plan_create) ───────────────────────


def _build_plan_create_payload(
    *,
    user_id: int,
    result: _PatternAResult,
    plan_version_id: int,
    model_synthesizer: str,
    model_seam_reviewer: str,
    temperature: float,
    etl_version_set: dict[str, str],
) -> Layer4Payload:
    """Compose the final Layer4Payload for plan_create per §3.1:
    `mode='plan_create'`, `pattern='A'`, `phase_structure` non-None,
    `seam_reviews` non-None (possibly empty list)."""
    if result.all_sessions:
        scope_start = result.all_sessions[0].date
        scope_end = result.all_sessions[-1].date
    else:
        scope_start = result.phase_structure.phases[0].start_date
        scope_end = result.phase_structure.phases[-1].end_date
    return Layer4Payload(
        user_id=user_id,
        mode="plan_create",
        plan_version_id=plan_version_id,
        scope_start_date=scope_start,
        scope_end_date=scope_end,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        pattern="A",
        latency_ms_total=result.latency_ms_total,
        input_tokens_total=result.input_tokens_total,
        output_tokens_total=result.output_tokens_total,
        llm_call_count=result.llm_call_count,
        etl_version_set=etl_version_set,
        sessions=result.all_sessions,
        phase_structure=result.phase_structure,
        seam_reviews=result.seam_reviews,
        shape_override=None,
        validator_results=result.validator_results,
        notable_observations=result.notable_observations,
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


def _build_plan_refresh_a_payload(
    *,
    user_id: int,
    result: _PatternAResult,
    plan_version_id: int,
    scope_start: _date_type,
    scope_end: _date_type,
    model_synthesizer: str,
    model_seam_reviewer: str,
    temperature: float,
    etl_version_set: dict[str, str],
) -> Layer4Payload:
    """Compose the Pattern A plan_refresh Layer4Payload (T3 cross-phase)
    per `Layer4_Spec.md` §3.2 + §6.3."""
    return Layer4Payload(
        user_id=user_id,
        mode="plan_refresh",
        plan_version_id=plan_version_id,
        scope_start_date=scope_start,
        scope_end_date=scope_end,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        pattern="A",
        latency_ms_total=result.latency_ms_total,
        input_tokens_total=result.input_tokens_total,
        output_tokens_total=result.output_tokens_total,
        llm_call_count=result.llm_call_count,
        etl_version_set=etl_version_set,
        sessions=result.all_sessions,
        phase_structure=result.phase_structure,
        seam_reviews=result.seam_reviews,
        shape_override=None,
        validator_results=result.validator_results,
        notable_observations=result.notable_observations,
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


# ─── Entry point: llm_layer4_plan_create ─────────────────────────────────────


def llm_layer4_plan_create(
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
    race_event_payload: RaceEventPayload | None = None,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens_per_phase: int = _PHASE_MAX_TOKENS_DEFAULT,
    capped_retries_per_phase: int = 2,
    extended_thinking_budget: int = _PHASE_THINKING_DEFAULT,
    seam_max_tokens: int = _SEAM_MAX_TOKENS_DEFAULT,
    seam_thinking_budget: int = _SEAM_THINKING_DEFAULT,
    phase_caller: _PhaseLLMCaller | None = None,
    seam_caller: SeamReviewerCaller | None = None,
    cache: Layer4Cache | None = None,
    call_cache_key: str | None = None,
    executor: Executor | None = None,
    # D-73 Phase 5.2 BM3 2026-05-24 — Layer 2 modality resolver payload
    # threaded through `_run_pattern_a_engine` → `synthesize_phase` →
    # `render_user_prompt`. Default None preserves existing call sites.
    layer2_modality_payload: Layer2ModalityPayload | None = None,
) -> Layer4Payload:
    """Pattern A plan-create entry point per `Layer4_Spec.md` §3.1.

    Algorithm (§5.2 Pattern A):
    1. Validate inputs per §4.2.
    2. Compute `phase_structure_from_3b()` per §6.1.
    3. Per-phase synthesis loop (sequential, in order). Each phase consumes
       the prior phase's accepted output as continuity context.
    4. Seam-review loop. For each adjacent-phase pair: review verdict
       triggers either record-only, observation-emit, or re-synthesis per
       §6.2 propose-patch authority (within per-phase retry budget).
    5. Final cross-phase validator pass over the union of all sessions.
       Cross-phase blocker failures elevate to `best_effort_plan` per §5.5.
    6. Compose Layer4Payload with `mode='plan_create'`, `pattern='A'`,
       `phase_structure` populated, `seam_reviews` populated.

    `race_event_payload` is optional — open-ended plans (no event_date) pass
    None; event-mode plans pass the RaceEventPayload from the D-66 design wave.
    """
    _validate_plan_create_inputs(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payloads=layer2c_payloads,
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        plan_start_date=plan_start_date,
        plan_version_id=plan_version_id,
        race_event_payload=race_event_payload,
    )

    total_weeks = _compute_total_weeks(
        layer3b_payload, plan_start_date, race_event_payload
    )
    phase_structure = phase_structure_from_3b(
        layer3b_payload, plan_start_date, total_weeks=total_weeks
    )

    # plan_create synthesizes every phase in phase_structure.
    phase_indices_to_synthesize = list(range(len(phase_structure.phases)))

    result = _run_pattern_a_engine(
        user_id=user_id,
        phase_structure=phase_structure,
        phase_indices_to_synthesize=phase_indices_to_synthesize,
        carryover_sessions_by_phase_index={},
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payloads=layer2c_payloads,
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        race_event_payload=race_event_payload,
        plan_version_id=plan_version_id,
        etl_version_set=etl_version_set,
        mode="plan_create",
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        max_tokens_per_phase=max_tokens_per_phase,
        extended_thinking_budget=extended_thinking_budget,
        capped_retries_per_phase=capped_retries_per_phase,
        seam_max_tokens=seam_max_tokens,
        seam_thinking_budget=seam_thinking_budget,
        phase_caller=phase_caller,
        seam_caller=seam_caller,
        cache=cache,
        call_cache_key=call_cache_key,
        executor=executor,
        layer2_modality_payload=layer2_modality_payload,
    )

    return _build_plan_create_payload(
        user_id=user_id,
        result=result,
        plan_version_id=plan_version_id,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        etl_version_set=etl_version_set,
    )


# ─── T3 cross-phase shared engine entry point ────────────────────────────────


def synthesize_pattern_a_for_refresh(
    *,
    user_id: int,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    layer2b_payload: Layer2BPayload | None,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
    layer2e_payload: Layer2EPayload | None,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload | None,
    phase_structure: PhaseStructure,
    phase_indices_to_synthesize: list[int],
    carryover_sessions_by_phase_index: dict[int, list[PlanSession]],
    refresh_scope_start: _date_type,
    refresh_scope_end: _date_type,
    plan_version_id: int,
    etl_version_set: dict[str, str],
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens_per_phase: int = _PHASE_MAX_TOKENS_DEFAULT,
    capped_retries_per_phase: int = 2,
    extended_thinking_budget: int = _PHASE_THINKING_DEFAULT,
    seam_max_tokens: int = _SEAM_MAX_TOKENS_DEFAULT,
    seam_thinking_budget: int = _SEAM_THINKING_DEFAULT,
    phase_caller: _PhaseLLMCaller | None = None,
    seam_caller: SeamReviewerCaller | None = None,
    cache: Layer4Cache | None = None,
    call_cache_key: str | None = None,
    executor: Executor | None = None,
) -> Layer4Payload:
    """Pattern A engine for `plan_refresh` T3 cross-phase routing per §6.3.

    Called by `plan_refresh.py` when scope spans a phase boundary. Closes
    the `tier_t3_cross_phase_requires_pattern_a` raise path from Step 4d.

    Caller is responsible for:
    - Computing `phase_structure_from_3b()` + `scope_spans_phase_boundary()`
      to determine cross-phase routing.
    - Building `phase_indices_to_synthesize` from the phases overlapping the
      refresh scope (typically 2; could be more on edge cases).
    - Building `carryover_sessions_by_phase_index` from
      `prior_plan_session_window` for phases outside the refresh scope.
    """
    result = _run_pattern_a_engine(
        user_id=user_id,
        phase_structure=phase_structure,
        phase_indices_to_synthesize=phase_indices_to_synthesize,
        carryover_sessions_by_phase_index=carryover_sessions_by_phase_index,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payloads=layer2c_payloads,
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        race_event_payload=race_event_payload,
        plan_version_id=plan_version_id,
        etl_version_set=etl_version_set,
        mode="plan_refresh",
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        max_tokens_per_phase=max_tokens_per_phase,
        extended_thinking_budget=extended_thinking_budget,
        capped_retries_per_phase=capped_retries_per_phase,
        seam_max_tokens=seam_max_tokens,
        seam_thinking_budget=seam_thinking_budget,
        phase_caller=phase_caller,
        seam_caller=seam_caller,
        cache=cache,
        call_cache_key=call_cache_key,
        executor=executor,
    )

    return _build_plan_refresh_a_payload(
        user_id=user_id,
        result=result,
        plan_version_id=plan_version_id,
        scope_start=refresh_scope_start,
        scope_end=refresh_scope_end,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        etl_version_set=etl_version_set,
    )


__all__ = [
    "llm_layer4_plan_create",
    "synthesize_pattern_a_for_refresh",
]
