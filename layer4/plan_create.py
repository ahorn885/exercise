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

import json
import uuid
from collections import defaultdict
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
    Layer3APayload,
    Layer3BPayload,
    RaceEventPayload,
    TrainingSubstitutionPayload,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.hashing import (
    compute_accepted_output_hash,
    compute_block_cache_key,
    compute_seam_resynth_block_cache_key,
    compute_seam_review_cache_key,
    compute_week_seam_review_cache_key,
)
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
from layer4.session_feasibility import EventWindowSegment, TerrainResolution
from layer4.seam_review import (
    DEFAULT_EXTENDED_THINKING_BUDGET as _SEAM_THINKING_DEFAULT,
    DEFAULT_MAX_TOKENS as _SEAM_MAX_TOKENS_DEFAULT,
    SeamReviewCallResult,
    SeamReviewerCaller,
    compose_seam_review_row,
    review_seam,
)
from layer4.week_seam_review import review_week_seam
from layer4 import periodization
from layer4.validator import (
    ValidatorContext,
    daily_windows_from_layer1,
    validate_layer4_payload,
    weekly_capacity_hours,
)


# D-77 §4.1 (decision D4): the per-phase synthesis loop decomposes into
# per-week-block units so every unit fits the 300s Vercel function ceiling and
# each resumable pass caches ≥1 new block (monotonic convergence). `_BLOCK_WEEKS`
# is the tunable block size — 1 week is the smallest safe unit / max convergence
# margin (Andy's gate); raise to 2+ if per-block call-count overhead proves high
# after the §5.0 real-LLM latency walk.
_BLOCK_WEEKS = 1


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
        # Fallback only (3B field absent): mirror 3B's #334 race-day-inclusive
        # ceil so this path agrees with the primary one above.
        days = (race_event_payload.event_date - plan_start_date).days
        return max(1, -(-(days + 1) // 7))  # ceil((days + 1) / 7)
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
    *,
    plan_version_id: int,
) -> tuple[PhaseSynthesisResult, SynthesisMetadata]:
    """Reverse of `_serialize_phase_result_with_meta`. The returned
    PhaseSynthesisResult carries ZERO token/latency/llm_call_count fields
    because no LLM call fired on this code path; the cached
    `synthesis_metadata` keeps the original call's accounting for
    chain-hashing fidelity per §9.2.

    REBINDS `plan_version_id` on every hydrated session (§9.4). The per-block
    cache key folds in only the athlete's INPUTS (via `call_cache_key`), not the
    plan_version_id, so the SAME cached block is shared across every plan version
    for an athlete — but the cached payload has each session stamped with the
    plan_version_id of the run that first synthesized it. Without this rebind a
    later plan replaying an older plan's cached block (e.g. pv=45 hitting a block
    first cached under pv=39) persists sessions stamped with the STALE id, which
    collides with the original plan's rows on the `plan_sessions` natural-key
    UNIQUE `(plan_version_id, date, session_index_in_day)` -> UniqueViolation at
    persist. The whole-payload cache path already rebinds (`_rebind_payload_dict`,
    §9.4); the per-block hydrate path did not — this closes that gap for BOTH the
    primary block loop and the D-77 Slice 3 seam-resynth loop."""
    result = PhaseSynthesisResult(
        phase_name=cached["phase_name"],
        sessions=[
            PlanSession.model_validate(s).model_copy(
                update={"plan_version_id": plan_version_id}
            )
            for s in cached["sessions"]
        ],
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


def _aggregate_block_results(
    phase_name: str,
    block_results: list[tuple[PhaseSynthesisResult, SynthesisMetadata]],
) -> tuple[PhaseSynthesisResult, SynthesisMetadata]:
    """Concatenate a phase's per-week-block synthesis results (D-77 §4) into
    the single PhaseSynthesisResult + SynthesisMetadata the rest of the engine
    consumes (seam review, composition, phase_structure metadata).

    Token/latency accounting mirrors the per-unit cache contract (§9.6): the
    RESULT sums the per-block result totals (cache-zeroed on the cache-wired
    path, real otherwise), while the META sums the per-block metadata (which
    retains the original call's real accounting even on a cache hit) so the
    phase_structure row keeps a faithful per-phase cost."""
    if not block_results:
        empty_meta = SynthesisMetadata(
            model="",
            temperature=0.0,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            retries_used=0,
            cap_hit=False,
        )
        return (
            PhaseSynthesisResult(
                phase_name=phase_name,
                sessions=[],
                phase_synthesis_notes="",
                opportunities=[],
                validator_results=[],
                cap_hit=False,
                retries_used=0,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                llm_call_count=0,
            ),
            empty_meta,
        )

    sessions: list[PlanSession] = []
    notes: list[str] = []
    opportunities: list[str] = []
    validator_results: list[ValidatorResult] = []
    cap_hit = False
    retries_used = 0
    r_in = r_out = r_lat = r_calls = 0
    m_in = m_out = m_lat = m_retries = 0
    m_cap = False
    model = block_results[0][1].model
    temperature = block_results[0][1].temperature
    for r, m in block_results:
        sessions.extend(r.sessions)
        if r.phase_synthesis_notes:
            notes.append(r.phase_synthesis_notes)
        opportunities.extend(r.opportunities)
        validator_results.extend(r.validator_results)
        cap_hit = cap_hit or r.cap_hit
        retries_used = max(retries_used, r.retries_used)
        r_in += r.input_tokens
        r_out += r.output_tokens
        r_lat += r.latency_ms
        r_calls += r.llm_call_count
        m_in += m.input_tokens
        m_out += m.output_tokens
        m_lat += m.latency_ms
        m_retries = max(m_retries, m.retries_used)
        m_cap = m_cap or m.cap_hit

    sessions.sort(key=lambda s: (s.date, s.session_index_in_day))
    result = PhaseSynthesisResult(
        phase_name=phase_name,
        sessions=sessions,
        phase_synthesis_notes=" | ".join(notes),
        opportunities=opportunities[:3],
        validator_results=validator_results,
        cap_hit=cap_hit,
        retries_used=retries_used,
        input_tokens=r_in,
        output_tokens=r_out,
        latency_ms=r_lat,
        llm_call_count=r_calls,
    )
    meta = SynthesisMetadata(
        model=model,
        temperature=temperature,
        input_tokens=m_in,
        output_tokens=m_out,
        latency_ms=m_lat,
        retries_used=m_retries,
        cap_hit=m_cap,
    )
    return result, meta


# Cache `phase_idx` namespaces (all share the `plan_create`/`plan_refresh`
# entry_point storage; disjoint ranges keep the row classes from colliding):
#   [0, 500)     — primary per-week-block synthesis (the global block index `u`,
#                  0..W-1; W = total synthesized weeks, far below 500).
#   [500, 1000)  — D-77 Slice 3 SEAM-DRIVEN re-synthesis blocks, sub-keyed by
#                  the triggering seam (base + seam_idx*stride + week-1). Kept
#                  BELOW the seam-review base (i.e. still < _SEAM_CACHE_PHASE_IDX_BASE)
#                  ON PURPOSE: the stall-backstop progress counter
#                  (`routes._count_cached_blocks` / `_generation_stalled`) counts
#                  rows in [0, _SEAM_CACHE_PHASE_IDX_BASE), so a long seam
#                  re-synth registers as progress and resumes instead of stalling
#                  — no route SQL change needed.
#   [1000, 2000) — iter-1 PHASE-seam-review cache rows (base + seam_idx).
#   [2000, ...)  — iter-1 WEEK-seam-review cache rows (base + week_seam_idx),
#                  the D-77 Slice 3 intra-phase reviewer. Disjoint from the
#                  phase-seam rows; like them, NOT counted by the stall-backstop
#                  progress counter (it counts [0, _SEAM_CACHE_PHASE_IDX_BASE)),
#                  since a review is not a synthesis block.
_SEAM_RESYNTH_BLOCK_IDX_BASE = 500
_SEAM_RESYNTH_BLOCK_IDX_STRIDE = 100
_SEAM_CACHE_PHASE_IDX_BASE = 1000
_WEEK_SEAM_CACHE_PHASE_IDX_BASE = 2000


def _seam_resynth_block_phase_idx(seam_idx: int, week_in_phase: int) -> int:
    """Disjoint per-(seam, week) cache `phase_idx` for a seam-driven re-synth
    block, in [500, 1000). `week_in_phase` is 1-based. Asserts the result stays
    inside the seam-resynth band so it can never alias a primary block (< 500)
    or a seam-review row (>= 1000) under realistic phase counts/lengths."""
    idx = (
        _SEAM_RESYNTH_BLOCK_IDX_BASE
        + seam_idx * _SEAM_RESYNTH_BLOCK_IDX_STRIDE
        + (week_in_phase - 1)
    )
    assert _SEAM_RESYNTH_BLOCK_IDX_BASE <= idx < _SEAM_CACHE_PHASE_IDX_BASE, (
        f"seam-resynth phase_idx {idx} (seam={seam_idx}, week={week_in_phase}) "
        "escaped the [500, 1000) band"
    )
    return idx


def _serialize_seam_call_result(result: SeamReviewCallResult) -> dict[str, Any]:
    """Project the verdict-bearing fields of an iter-1 `SeamReviewCallResult`
    for the seam-review cache. Token / latency accounting is NOT stored —
    mirroring the per-phase cache, a cache hit contributes ZERO to the
    synthesis-only token/latency totals (§9.6), so there is nothing to keep."""
    return {
        "verdict": result.verdict,
        "seam_issues": list(result.seam_issues),
        "proposed_patch_direction": result.proposed_patch_direction,
    }


def _hydrate_seam_call_result(cached: dict[str, Any]) -> SeamReviewCallResult:
    """Reverse of `_serialize_seam_call_result`; zeros token/latency because
    no LLM call fired on a cache hit (§9.6)."""
    return SeamReviewCallResult(
        verdict=cached["verdict"],
        seam_issues=list(cached["seam_issues"]),
        proposed_patch_direction=cached["proposed_patch_direction"],
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
    )


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
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    terrain_feasibility: dict[str, TerrainResolution] | None = None,
    event_window_segments: list[EventWindowSegment] | None = None,
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

    # §9.2 (D-77) per-block cache chain — `prev_accepted_output_hash` rolls
    # forward through each accepted week-block output (None for the first block,
    # collapsing to '' inside `compute_block_cache_key`). Only used when `cache`
    # + `call_cache_key` are both provided.
    prev_accepted_output_hash: str | None = None
    cache_entry_point: Literal["plan_create", "plan_refresh"] = (
        "plan_create" if mode == "plan_create" else "plan_refresh"
    )

    # --- Per-(phase, week-block) synthesis (sequential) — D-77 §4 ---------
    # The synthesis unit is one week-block (`_BLOCK_WEEKS` weeks) so it always
    # fits the 300s function ceiling. A global, monotonic block index `u` is the
    # cache `phase_idx` (0..W-1, W = total synthesized weeks; well below the seam
    # namespace base of 1000). The §9.2 chain hash rolls forward PER BLOCK across
    # the whole plan (spanning phase boundaries), so a change at week k
    # invalidates k+1..end only. Threading passes the immediately-preceding
    # block's accepted sessions as the prompt's continuity context.
    u = 0
    prior_block_sessions: list[PlanSession] = []
    # D-77 per-invocation budget: count blocks THIS pass synthesizes (cache
    # misses route through `_serialize_block` below; HITs don't). Gates only
    # NEW syntheses, never the cheap HIT replay, and never the first synthesis
    # of a pass -- so every pass makes >=1 block of progress and the function
    # returns cleanly before the duration cap instead of 504-ing mid-synthesis.
    from .generation_budget import (
        Layer4GenerationIncomplete,
        generation_deadline_passed,
    )
    synth_count = [0]
    # Rule #15 observability (once per synthesis-driver entry): the 3B
    # periodization shape + 2D injury constraints are upstream inputs that shape
    # volume/intensity targets and which exercises are off-limits — log them so a
    # mis-periodized or over-excluded plan is attributable upstream of synthesis.
    _phases_dbg = [
        f"{p.phase_name}:{p.weeks}w vol={p.intended_volume_band} "
        f"int={p.intended_intensity_distribution}"
        for p in phase_structure.phases
    ]
    print(
        f"plan_create 3B phase_structure: derived_from={phase_structure.derived_from} "
        f"total_weeks={phase_structure.total_weeks} phases={_phases_dbg}"
    )
    _excl_2d = layer2d_payload.excluded_exercises if layer2d_payload else []
    _acc_2d = layer2d_payload.accommodated_exercises if layer2d_payload else []
    print(
        f"plan_create 2D injury inputs: excluded_n={len(_excl_2d)} "
        f"excluded_ids={[getattr(e, 'exercise_id', '?') for e in _excl_2d][:20]} "
        f"accommodated_n={len(_acc_2d)}"
    )
    for i, phase in enumerate(phase_structure.phases):
        if i not in phase_indices_to_synthesize:
            # Carryover phase (T3 cross-phase): not synthesized this call, but
            # seed the threading context so the next synthesized phase's first
            # block threads off this phase's last week. The §9.2 chain hash is
            # NOT rolled for carryover (mirrors the prior per-phase contract).
            if i in carryover_sessions_by_phase_index:
                prior_block_sessions = carryover_sessions_by_phase_index[i]
            continue

        block_results: list[tuple[PhaseSynthesisResult, SynthesisMetadata]] = []
        week = 1
        while week <= phase.weeks:
            week_end = min(week + _BLOCK_WEEKS - 1, phase.weeks)
            week_range = (week, week_end)

            def _synth_this_block(
                _i: int = i,
                _phase: PhaseSpec = phase,
                _prior: list[PlanSession] = prior_block_sessions,
                _wr: tuple[int, int] = week_range,
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
                    prior_block_sessions=_prior,
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
                    session_id_prefix=f"{session_id_prefix}-p{_i}-w{_wr[0]}",
                    training_substitution_payload=training_substitution_payload,
                    terrain_feasibility=terrain_feasibility,
                    event_window_segments=event_window_segments,
                    week_range=_wr,
                )

            if cache is not None and call_cache_key is not None:
                # §9.2 (D-77): per-block cache key chains via the running
                # prev_accepted_output_hash; phase_idx = the global block index.
                block_key = compute_block_cache_key(
                    call_cache_key=call_cache_key,
                    phase_name=phase.phase_name,
                    phase_index=i,
                    week_in_phase=week,
                    prev_accepted_output_hash=prev_accepted_output_hash,
                )
                # Rule #15 observability: the per-block key CHAINS on
                # prev_accepted_output_hash, so if an upstream block re-synthesizes
                # to different content this block's key changes and it MISSes again
                # — the "re-synthesizes every drive" churn (#202 class). Log the
                # chain input + key so churn is attributable to the chain vs. a
                # stable-but-uncached block.
                print(
                    f"compute_block_cache_key: {phase.phase_name}:w{week} idx={i} "
                    f"key={block_key} prev_accepted_output_hash={prev_accepted_output_hash}"
                )

                def _serialize_block(
                    _synth=_synth_this_block,
                ) -> dict[str, Any]:
                    # D-77 budget gate -- runs only on a cache MISS (this
                    # closure IS the synthesizer). Never gates the first
                    # synthesis of a pass (synth_count==0), so each pass caches
                    # >=1 new block; past that, stop before starting one we
                    # can't finish within the function budget -- the blocks
                    # cached so far persist and the next pass resumes from them.
                    if synth_count[0] >= 1 and generation_deadline_passed():
                        raise Layer4GenerationIncomplete(blocks_cached=u)
                    r = _synth()
                    synth_count[0] += 1
                    m = build_synthesis_metadata_from_result(
                        r, model=model_synthesizer, temperature=temperature
                    )
                    return _serialize_phase_result_with_meta(r, m)

                cached_dict = cache.get_phase_or_synthesize(
                    phase_key=block_key,
                    phase_idx=u,
                    phase_name=f"{phase.phase_name}:w{week}",
                    user_id=user_id,
                    entry_point=cache_entry_point,
                    synthesizer=_serialize_block,
                )
                block_result, block_meta = _hydrate_phase_result_with_meta(
                    cached_dict, plan_version_id=plan_version_id
                )
            else:
                block_result = _synth_this_block()
                block_meta = build_synthesis_metadata_from_result(
                    block_result, model=model_synthesizer, temperature=temperature
                )

            block_results.append((block_result, block_meta))
            # Roll the §9.2 chain hash forward PER BLOCK + thread this block's
            # accepted sessions into the next block's continuity context.
            prev_accepted_output_hash = compute_accepted_output_hash(
                block_result.sessions, block_meta
            )
            prior_block_sessions = block_result.sessions
            u += 1
            week = week_end + 1

        # Aggregate the phase's week-blocks into one PhaseSynthesisResult + meta.
        result, meta = _aggregate_block_results(phase.phase_name, block_results)
        results_by_index[i] = result
        synthesis_metadata_by_index[i] = meta
        retries_used_per_phase[i] = result.retries_used
        validator_results.extend(result.validator_results)
        total_input_tokens += result.input_tokens
        total_output_tokens += result.output_tokens
        total_latency_ms += result.latency_ms
        llm_call_count += result.llm_call_count

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
    def _seam_prior_sessions(seam_idx: int) -> list[PlanSession]:
        if seam_idx in phase_indices_to_synthesize:
            return results_by_index[seam_idx].sessions
        return carryover_sessions_by_phase_index.get(seam_idx, [])

    def _seam_next_sessions(seam_idx: int) -> list[PlanSession]:
        if (seam_idx + 1) in phase_indices_to_synthesize:
            return results_by_index[seam_idx + 1].sessions
        return carryover_sessions_by_phase_index.get(seam_idx + 1, [])

    def _iter1_task(
        seam_idx: int,
    ) -> tuple[int, SeamReviewCallResult]:
        call_1_local = review_seam(
            seam_index=seam_idx,
            prior_phase_spec=phase_structure.phases[seam_idx],
            next_phase_spec=phase_structure.phases[seam_idx + 1],
            prior_phase_sessions=_seam_prior_sessions(seam_idx),
            next_phase_sessions=_seam_next_sessions(seam_idx),
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

    # §9.2 iter-1 seam cache: each iteration-1 review is a pure function of the
    # two phases' (per-phase-cached, stable-across-resumes) session outputs +
    # the inputs already folded into `call_cache_key`. Cache them individually
    # so a resumed pass replays the iter-1 LLM calls from cache and only the
    # rare iter-2 re-synth path (intentionally uncached — it mutates phase
    # state) recomputes. Closes the §9.2 Step-6 gap where the whole uncached
    # seam tail re-ran on every resume. Reads are sequential + cheap; only the
    # uncached seams fire the parallel LLM calls, so a cold run keeps the §5.2
    # cross-seam parallelism. All cache get/put happen here, BEFORE the
    # processing loop runs any iter-2 re-synth, so the key always hashes the
    # original (per-phase-cached) sessions on both cold + resume.
    seam_cache_enabled = cache is not None and call_cache_key is not None
    cached_seam_indices: set[int] = set()

    def _seam_cache_key(seam_idx: int) -> str:
        return compute_seam_review_cache_key(
            call_cache_key=call_cache_key,  # type: ignore[arg-type]
            seam_index=seam_idx,
            prior_phase_sessions=_seam_prior_sessions(seam_idx),
            next_phase_sessions=_seam_next_sessions(seam_idx),
            model=model_seam_reviewer,
            max_tokens=seam_max_tokens,
            extended_thinking_budget=seam_thinking_budget,
        )

    iter1_results: list[tuple[int, SeamReviewCallResult]] = []
    uncached_pairs: list[int] = list(pairs_to_review)
    if seam_cache_enabled:
        uncached_pairs = []
        for seam_idx in pairs_to_review:
            entry = cache.backend.get(
                _seam_cache_key(seam_idx), _SEAM_CACHE_PHASE_IDX_BASE + seam_idx
            )
            if entry is not None:
                cache.metrics.record_hit(cache_entry_point, is_phase=True)
                cached_seam_indices.add(seam_idx)
                iter1_results.append(
                    (seam_idx, _hydrate_seam_call_result(json.loads(entry.payload_json)))
                )
            else:
                cache.metrics.record_miss(cache_entry_point, is_phase=True)
                uncached_pairs.append(seam_idx)

    fresh_results: list[tuple[int, SeamReviewCallResult]] = []
    if len(uncached_pairs) >= 2 and executor is not None:
        fresh_results = list(executor.map(_iter1_task, uncached_pairs))
    elif len(uncached_pairs) >= 2:
        with ThreadPoolExecutor(
            max_workers=min(4, len(uncached_pairs))
        ) as _default_exe:
            fresh_results = list(_default_exe.map(_iter1_task, uncached_pairs))
    elif len(uncached_pairs) == 1:
        fresh_results = [_iter1_task(uncached_pairs[0])]
    # else: no uncached seams (all cached on resume, or none to review).

    if seam_cache_enabled:
        for seam_idx, res in fresh_results:
            cache.backend.put(
                cache_key=_seam_cache_key(seam_idx),
                phase_idx=_SEAM_CACHE_PHASE_IDX_BASE + seam_idx,
                user_id=user_id,
                entry_point=cache_entry_point,
                phase_name=f"__seam_{seam_idx}__",
                payload_json=json.dumps(
                    _serialize_seam_call_result(res),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
    iter1_results.extend(fresh_results)
    iter1_results.sort(key=lambda t: t[0])

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
        # A cache hit contributes ZERO (no LLM call fired) per §9.6, mirroring
        # the per-phase cache; only a fresh iter-1 call counts.
        if seam_idx not in cached_seam_indices:
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

        # D-77 Slice 3: re-synthesize the targeted phase WEEK-BY-WEEK, mirroring
        # the primary per-block loop — each block gets `week_range` (so its output
        # budget is sized to one week's session ceiling, ~21.6k, not the raw 4000
        # whole-phase default that truncated the seam re-synth) plus the seam
        # constraints. The blocks are cache-wired (disjoint seam-resynth phase_idx
        # namespace + a seam-aware key) and budget-gated exactly like the primary
        # loop, so a multi-week phase resumes across passes instead of blowing the
        # function duration cap on one oversized call. Threading seeds from the
        # prior phase's sessions, then rolls per re-synth block.
        retries_already_used_seam = retries_used_per_phase[target_idx] + 1
        seam_block_results: list[tuple[PhaseSynthesisResult, SynthesisMetadata]] = []
        resynth_prior_sessions = target_prior_phase_sessions
        resynth_prev_hash: str | None = None
        rs_week = 1
        while rs_week <= target_phase.weeks:
            rs_week_end = min(rs_week + _BLOCK_WEEKS - 1, target_phase.weeks)
            rs_week_range = (rs_week, rs_week_end)

            def _synth_seam_block(
                _phase: PhaseSpec = target_phase,
                _idx: int = target_idx,
                _prior: list[PlanSession] = resynth_prior_sessions,
                _wr: tuple[int, int] = rs_week_range,
                _issues: list[str] = call_1.seam_issues,
                _dir: str = direction,
                _retries_used: int = retries_already_used_seam,
            ) -> PhaseSynthesisResult:
                return synthesize_phase(
                    user_id=user_id,
                    phase_spec=_phase,
                    phase_structure=phase_structure,
                    phase_index_in_plan=_idx,
                    layer1_payload=layer1_payload,
                    layer2a_payload=layer2a_payload,
                    layer2b_payload=layer2b_payload,
                    layer2c_payloads=layer2c_payloads,
                    layer2d_payload=layer2d_payload,
                    layer2e_payload=layer2e_payload,
                    layer3a_payload=layer3a_payload,
                    layer3b_payload=layer3b_payload,
                    race_event_payload=race_event_payload,
                    prior_block_sessions=_prior,
                    plan_version_id=plan_version_id,
                    etl_version_set=etl_version_set,
                    mode=mode,
                    model=model_synthesizer,
                    temperature=temperature,
                    max_tokens=max_tokens_per_phase,
                    extended_thinking_budget=extended_thinking_budget,
                    capped_retries=capped_retries_per_phase,
                    seam_issues=_issues,
                    seam_direction=_dir,  # type: ignore[arg-type]
                    retries_already_used=_retries_used,
                    llm_caller=phase_caller,
                    session_id_prefix=(
                        f"{session_id_prefix}-p{_idx}-seamretry"
                        f"-s{seam_idx}-w{_wr[0]}"
                    ),
                    training_substitution_payload=training_substitution_payload,
                    terrain_feasibility=terrain_feasibility,
                    week_range=_wr,
                )

            if cache is not None and call_cache_key is not None:
                rs_block_key = compute_seam_resynth_block_cache_key(
                    call_cache_key=call_cache_key,
                    phase_name=target_phase.phase_name,
                    phase_index=target_idx,
                    week_in_phase=rs_week,
                    prev_accepted_output_hash=resynth_prev_hash,
                    seam_index=seam_idx,
                    seam_issues=call_1.seam_issues,
                    seam_direction=direction,
                )

                def _serialize_seam_block(
                    _synth=_synth_seam_block,
                ) -> dict[str, Any]:
                    # Same budget gate as the primary loop: never gates the first
                    # synthesis of a pass (so each pass caches >=1 new block), then
                    # stops before starting one that can't finish in the function
                    # budget — the seam-resynth blocks cached so far persist and the
                    # next pass resumes from them.
                    if synth_count[0] >= 1 and generation_deadline_passed():
                        raise Layer4GenerationIncomplete(blocks_cached=u)
                    r = _synth()
                    synth_count[0] += 1
                    m = build_synthesis_metadata_from_result(
                        r, model=model_synthesizer, temperature=temperature
                    )
                    return _serialize_phase_result_with_meta(r, m)

                rs_cached_dict = cache.get_phase_or_synthesize(
                    phase_key=rs_block_key,
                    phase_idx=_seam_resynth_block_phase_idx(seam_idx, rs_week),
                    phase_name=f"{target_phase.phase_name}:seam{seam_idx}:w{rs_week}",
                    user_id=user_id,
                    entry_point=cache_entry_point,
                    synthesizer=_serialize_seam_block,
                )
                rs_block_result, rs_block_meta = _hydrate_phase_result_with_meta(
                    rs_cached_dict, plan_version_id=plan_version_id
                )
            else:
                rs_block_result = _synth_seam_block()
                rs_block_meta = build_synthesis_metadata_from_result(
                    rs_block_result, model=model_synthesizer, temperature=temperature
                )

            seam_block_results.append((rs_block_result, rs_block_meta))
            resynth_prev_hash = compute_accepted_output_hash(
                rs_block_result.sessions, rs_block_meta
            )
            resynth_prior_sessions = rs_block_result.sessions
            rs_week = rs_week_end + 1

        re_result, re_meta = _aggregate_block_results(
            target_phase.phase_name, seam_block_results
        )
        results_by_index[target_idx] = re_result
        # The aggregated meta carries the re-synthesis's token/latency/retries
        # accounting so the final PhaseStructure row reflects the re-synth rather
        # than the initial synthesis.
        synthesis_metadata_by_index[target_idx] = re_meta
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

    # --- Intra-phase WEEK-seam reviews (D-77 Slice 3) -------------------
    # The per-week-block decomposition (Slices 1+2) generates each week
    # independently, so weeks within a phase can show abrupt week-to-week
    # cliffs. This reviewer blends them: for each adjacent week pair WITHIN a
    # synthesized phase it judges whether the actual week-over-week change
    # tracks the planned periodization grid (`periodization.py`) — a planned
    # recovery week's dip is correct, only UNJUSTIFIED divergence is flagged
    # (ratified design §5.2 + `Layer4_WeekSeamReviewer_v1.md`).
    #
    # v1 ships in REVIEW-AND-ESCALATE mode: a non-clean verdict surfaces a
    # `notable_observation` (HITL-escalated for major). The β auto-resynth of a
    # week-block is gated on the real-LLM walk (design §7 cascade-invalidation
    # watch item + §14) and tracked as a fast-follow — the propose-patch
    # direction is still emitted + recorded so that wiring is a later
    # orchestrator-only change with no prompt revision. Only intra-phase seams of
    # synthesized phases are reviewed (a phase is synthesized as a whole, so a
    # week seam never straddles a synthesized + carryover boundary — that
    # boundary is the PHASE seam, handled above).
    @dataclass
    class _WeekSeam:
        phase_index: int
        phase: PhaseSpec
        prior_week: int
        next_week: int
        prior_sessions: list[PlanSession]
        next_sessions: list[PlanSession]
        global_index: int

    week_seams: list[_WeekSeam] = []
    _ws_global = 0
    for i in sorted(phase_indices_to_synthesize):
        phase = phase_structure.phases[i]
        sessions_i = results_by_index[i].sessions if i in results_by_index else []
        by_week: dict[int, list[PlanSession]] = defaultdict(list)
        for s in sessions_i:
            if s.phase_metadata is not None:
                by_week[s.phase_metadata.week_in_phase].append(s)
        for w in range(1, phase.weeks):
            prior_ss = by_week.get(w, [])
            next_ss = by_week.get(w + 1, [])
            if not prior_ss or not next_ss:
                # A week with no sessions either side -> no seam to blend.
                continue
            week_seams.append(
                _WeekSeam(
                    phase_index=i,
                    phase=phase,
                    prior_week=w,
                    next_week=w + 1,
                    prior_sessions=prior_ss,
                    next_sessions=next_ss,
                    global_index=_ws_global,
                )
            )
            _ws_global += 1

    def _week_planned(phase_name: str, w: int) -> tuple[float, bool]:
        return (
            periodization.week_volume_multiplier(
                phase_structure, phase_name, w, layer3a_payload
            ),
            periodization.is_deload_week_for(phase_structure, phase_name, w),
        )

    def _week_seam_cache_key(ws: "_WeekSeam") -> str:
        return compute_week_seam_review_cache_key(
            call_cache_key=call_cache_key,  # type: ignore[arg-type]
            week_seam_index=ws.global_index,
            prior_week_sessions=ws.prior_sessions,
            next_week_sessions=ws.next_sessions,
            model=model_seam_reviewer,
            max_tokens=seam_max_tokens,
            extended_thinking_budget=seam_thinking_budget,
        )

    def _week_seam_task(ws: "_WeekSeam") -> tuple[int, SeamReviewCallResult]:
        prior_mult, prior_recovery = _week_planned(ws.phase.phase_name, ws.prior_week)
        next_mult, next_recovery = _week_planned(ws.phase.phase_name, ws.next_week)
        res = review_week_seam(
            phase_name=ws.phase.phase_name,
            prior_week_in_phase=ws.prior_week,
            next_week_in_phase=ws.next_week,
            prior_week_sessions=ws.prior_sessions,
            next_week_sessions=ws.next_sessions,
            prior_planned_multiplier=prior_mult,
            next_planned_multiplier=next_mult,
            prior_is_recovery=prior_recovery,
            next_is_recovery=next_recovery,
            phase_volume_band=ws.phase.intended_volume_band,
            prior_intended_intensity=ws.phase.intended_intensity_distribution,
            next_intended_intensity=ws.phase.intended_intensity_distribution,
            layer2d_payload=layer2d_payload,
            discipline_mix=discipline_mix,
            mode=mode_str,
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
        return (ws.global_index, res)

    ws_cache_enabled = cache is not None and call_cache_key is not None
    ws_cached_indices: set[int] = set()
    ws_results: list[tuple[int, SeamReviewCallResult]] = []
    ws_uncached: list[_WeekSeam] = list(week_seams)
    if ws_cache_enabled:
        ws_uncached = []
        for ws in week_seams:
            entry = cache.backend.get(
                _week_seam_cache_key(ws),
                _WEEK_SEAM_CACHE_PHASE_IDX_BASE + ws.global_index,
            )
            if entry is not None:
                cache.metrics.record_hit(cache_entry_point, is_phase=True)
                ws_cached_indices.add(ws.global_index)
                ws_results.append(
                    (ws.global_index, _hydrate_seam_call_result(json.loads(entry.payload_json)))
                )
            else:
                cache.metrics.record_miss(cache_entry_point, is_phase=True)
                ws_uncached.append(ws)

    ws_fresh: list[tuple[int, SeamReviewCallResult]] = []
    if len(ws_uncached) >= 2 and executor is not None:
        ws_fresh = list(executor.map(_week_seam_task, ws_uncached))
    elif len(ws_uncached) >= 2:
        with ThreadPoolExecutor(max_workers=min(4, len(ws_uncached))) as _ws_exe:
            ws_fresh = list(_ws_exe.map(_week_seam_task, ws_uncached))
    elif len(ws_uncached) == 1:
        ws_fresh = [_week_seam_task(ws_uncached[0])]

    if ws_cache_enabled:
        ws_by_index = {ws.global_index: ws for ws in week_seams}
        for ws_idx, res in ws_fresh:
            ws = ws_by_index[ws_idx]
            cache.backend.put(
                cache_key=_week_seam_cache_key(ws),
                phase_idx=_WEEK_SEAM_CACHE_PHASE_IDX_BASE + ws_idx,
                user_id=user_id,
                entry_point=cache_entry_point,
                phase_name=f"__week_seam_{ws_idx}__",
                payload_json=json.dumps(
                    _serialize_seam_call_result(res),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
    ws_results.extend(ws_fresh)
    ws_results.sort(key=lambda t: t[0])

    ws_by_index = {ws.global_index: ws for ws in week_seams}
    for ws_idx, res in ws_results:
        ws = ws_by_index[ws_idx]
        total_input_tokens += res.input_tokens
        total_output_tokens += res.output_tokens
        total_latency_ms += res.latency_ms
        if ws_idx not in ws_cached_indices:
            llm_call_count += 1
        seam_label = (
            f"{ws.phase.phase_name} wk{ws.prior_week}→wk{ws.next_week}"
        )
        # Rule #15: log the verdict + the planned-vs-actual inputs the reviewer
        # decided on, so a surprising flag (or a silent miss) is attributable.
        print(
            f"week_seam_review: {seam_label} verdict={res.verdict} "
            f"direction={res.proposed_patch_direction} "
            f"issues={len(res.seam_issues)}"
        )
        if res.verdict == "approved":
            continue
        # flagged_minor: record-only warning. flagged_major / patched (any
        # direction) + accept_with_observation: escalate to HITL in v1
        # review-and-escalate mode (no auto-resynth this slice).
        elevates = res.verdict in ("flagged_major", "patched")
        summary = "; ".join(res.seam_issues)[:240] or (
            f"week seam {seam_label}: {res.verdict}"
        )
        notable_observations.append(
            Observation(
                category="warning" if not elevates else "seam_unresolved",
                text=summary,
                evidence_basis=[f"week_seam_review {seam_label}"],
                elevates_to_hitl=elevates,
            )
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
        capacity_hours=weekly_capacity_hours(layer1_payload),
        daily_availability_windows=daily_windows_from_layer1(layer1_payload),
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
        # Rule #15 — the final cross-phase pass demotes surviving blockers to
        # warnings (best_effort_plan) and was otherwise SILENT: a degraded plan
        # shipped with no log signal as to which rule failed or why. Log each
        # failure (rule_name + detail) so a best-effort plan is diagnosable from
        # logs — esp. the #698 Slice-3b availability rules (daily_window_fit /
        # recovery_placement_match) newly active in prod.
        for _f in final_validator.rule_failures:
            print(
                f"_run_pattern_a_engine: final cross-phase pass FAILED — "
                f"{_f.severity} {_f.rule_name} demoted→warning: {_f.detail}"
            )
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
    # Training-substitution resolver payload threaded through
    # `_run_pattern_a_engine` → `synthesize_phase` → `render_user_prompt`.
    # Default None preserves existing call sites.
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    # #540 — per-discipline terrain-feasibility resolutions, threaded the same
    # path into the session-grid render. Default None preserves call sites.
    terrain_feasibility: dict[str, TerrainResolution] | None = None,
    # Event Windows Slice 1 (#581 WS-H) — date-scoped reduced-environment
    # segments, threaded the same path into the per-phase overlay render.
    event_window_segments: list[EventWindowSegment] | None = None,
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
        training_substitution_payload=training_substitution_payload,
        terrain_feasibility=terrain_feasibility,
        event_window_segments=event_window_segments,
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
    terrain_feasibility: dict[str, TerrainResolution] | None = None,
    event_window_segments: list[EventWindowSegment] | None = None,
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
        terrain_feasibility=terrain_feasibility,
        event_window_segments=event_window_segments,
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
