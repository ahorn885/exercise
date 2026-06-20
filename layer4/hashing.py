"""Canonical-JSON + SHA-256 cache-key helpers per `Layer4_Spec.md` §9.1.

Pure-function module — no I/O, no state. All hashes are SHA-256 hex digests
of canonical-JSON (sorted keys, stable serialization for dates/Decimals/sets);
all cache keys are SHA-256 of the listed components concatenated with `||`
per the spec formulas.

Per-call rebinding (§9.4): `plan_version_id` and `suggestion_id` are allocated
per call by the orchestrator and intentionally NOT in any cache key — a cache
hit returns the cached payload with those fields overwritten to the new
allocated values. None of the helpers below accept them.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from layer4.payload import PlanSession


_LAYER2_BUNDLE_ATTRS = frozenset({"a", "b", "c", "d", "e"})

# Prompt-body revision tag mixed into the plan-create / plan-refresh cache keys.
# The synthesis/refresh PROMPT TEXT is not otherwise part of the key (the key is
# keyed on payload + model + sampling, not prompt content), so a prompt-only
# change does not invalidate cached plans on its own. Bump this when a Layer 4
# synthesis or refresh prompt body changes in a way that should re-synthesize
# cached plans. "2" = #335 Phase 2 strength two-template restructure
# (per_phase + plan_refresh T1/T2 + shared strength_guidance).
# "3" = #618 humanize skill-gate wording — drop the raw toggle slug from the
# per_phase grid annotation + the validator correction feedback, + a VOICE rule
# (per_phase + T1/T2/T3) barring internal ids/slugs in athlete-facing text.
# "4" = #624 / #618-7 deterministic venue pick — the EXACT feasibility line now
# names the nearest saved locale per terrain (display name + distance) instead of
# one slug, so the synthesizer cites real nearby venues (no 'no nearby groomed
# trail' / invented park) and uses the locale's display name consistently.
# "5" = #624 surface-specific routing — the EXACT feasibility line now routes
# each session purpose (easy/long aerobic vs hill/vert vs technical) to the
# nearest venue carrying the matching surface, so the synthesizer stops
# collapsing every session onto the nearest surface.
# "6" = #624 Slice 2 grid session-typing — the session grid now types each
# cardio discipline's count into long/easy/quality slots, binding the surface
# routing to deterministic per-slot counts; the synthesis prompt directs
# long+easy → aerobic surface, quality → vert/technical surface.
# "7" = #624 Slice 3 craft-discipline surface routing — craft own/proxy EXACT
# resolutions now get the per-purpose surface routing too, constrained to the
# resolved craft's rideable terrains (a bike/paddle session is never routed to
# a required surface its craft can't traverse).
# "8" = #698 Track 1 Slice 2 recovery session kind — the synthesis prompt gains
# a `# Recovery programming` section, a rendered recovery-exercise pool + a
# deterministic per-week recovery dose block (off the training cap), and the
# tool schema gains the `recovery` kind + `recovery_exercises` enum-bound block;
# all change synthesis output, so cached plans must regenerate.
# "9" = #698 Track 1 Slice 3b deterministic recovery placement (D6) — the
# recovery block changes from a per-week COUNT to the explicit assigned DATES
# (`compute_recovery_placement`), and the recovery instruction is suppressed when
# the pool is empty; both change synthesis output, so cached plans must regenerate.
# "10" = #698 Track 1 race-week-brief recovery — the race_week_brief synthesizer
# gains a recovery instruction, renders prior `recovery_exercises`, and its tool
# schema gains the `recovery` kind + enum-bound `recovery_exercises` block; all
# change synthesis output, so cached plans must regenerate.
# "11" = #698 Track 2 (A2) cardio drills pool — the per-phase synthesizer gains a
# `# Cardio drills` instruction + a `=== Cardio drill pool ===` render, and its
# tool schema gains the enum-bound `cardio_drills` block (maxItems:1); changes
# synthesis output, so cached plans must regenerate.
# "12" = #698 Track 2 (Slice C2) cardio drills on the plan-refresh path — the T1/
# T2/T3 refresh synthesizers gain the same `# Cardio drills` instruction + the
# `=== Cardio drill pool ===` render + enum-bound `cardio_drills` block (same
# fidelity as plan generation); changes refresh synthesis output, so cached
# refreshes must regenerate. (single_session Slice C1 needs no bump — ad-hoc,
# not cache-keyed.)
# "13" = #337 structured cardio prescription — both the plan-create (per_phase)
# and plan-refresh synthesizers gain the `# Cardio programming` instruction
# (warm-up/work/cool-down structure + ground intensity targets in measured
# physiology) plus a measured-physiology block in the rendered prompt; changes
# synthesis output, so cached plans + refreshes must regenerate. (single_session
# needs no bump — ad-hoc, not cache-keyed.)
# "14" = #307 upstream coaching_flags render — the plan-create (per_phase) and
# plan-refresh synthesizers gain an `Upstream coaching flags` block surfacing the
# 2A/2B/2C/2D advisory flags (suppress-on-empty); changes the rendered prompt, so
# cached plans + refreshes must regenerate. (single_session needs no bump — ad-hoc,
# not cache-keyed.)
# "15" = #690 strength variety + Coaching Memory — the per_phase synthesizer gains
# a `Coaching memory` render block (durable `coaching_preferences`, suppress-on-
# empty) and a stronger strength rotation/variety directive (shared
# `strength_guidance` + per_phase), so the high-variety preference is honored and
# accessory work spans the resolved pool. Changes the rendered prompt; cached
# plans must regenerate. (The pref VALUES also ride `layer1_hash` now, so a
# preference edit invalidates independently of this tag.)
# "16" = #691 tier-0 equipment-gate fix — the strength / recovery / cardio-drill
# pools (both the SDK enums `compute_*_pool_ids` and the rendered `_format_*_pool`
# menus) now drop tier-0 (equipment-infeasible, no substitute/proxy) exercises, so
# an unavailable-gear exercise can no longer be prescribed. Changes the feasible
# enum + rendered pool, so cached plans + refreshes must regenerate. (single_session
# needs no bump — ad-hoc, not cache-keyed — but reads the same corrected fns.)
# "17" = #339 cross-discipline variety — (A) the durable Coaching Memory block
# (#690 / `_format_coaching_memory`) is now rendered on the plan_refresh +
# single_session + race_week_brief paths too (was per_phase-only), and (B) all
# four synthesizers gain the `VARIETY_CARVEOUT_PROMPT_SECTION` (gated on a stated
# variety preference; easy foot-based sessions only — counts / long / quality
# preserved). Changes the rendered prompt, so cached plans + refreshes regenerate.
LAYER4_PROMPT_REVISION = "17"


def _to_jsonable(obj: Any) -> Any:
    """Recursive conversion to JSON-safe types with stable serialization.

    - pydantic BaseModel  → model_dump(mode='json') (recurse)
    - dict                → recurse values; json.dumps sorts keys
    - list / tuple        → list of converted items
    - set / frozenset     → sorted list (elements must be comparable)
    - datetime / date     → ISO 8601 string
    - Decimal             → str(value)
    - other scalars       → passthrough
    """
    if isinstance(obj, BaseModel):
        return _to_jsonable(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_to_jsonable(x) for x in obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


def canonical_json(obj: Any) -> str:
    """SHA-256-stable JSON encoding: sorted keys, no whitespace, ISO dates."""
    return json.dumps(
        _to_jsonable(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_payload_hash(payload: Any) -> str:
    """SHA-256 hex of canonical-JSON of a typed payload (typically a pydantic model).

    Building block for the per-layer hashes (`layer1_hash`, `layer2a_hash`,
    etc.) that the orchestrator pre-computes and passes into the cache-key
    helpers below.
    """
    return _sha256_hex(canonical_json(payload))


def compute_terrain_feasibility_hash(terrain_feasibility: dict[str, Any]) -> str:
    """#540 slice 2c.2 — SHA-256 of the per-discipline terrain resolutions.

    Folds into `plan_create_key` so a feasibility change (e.g. a newly-tagged
    locale terrain) invalidates the cached plan. Values are `TerrainResolution`
    frozen dataclasses; `asdict` flattens each to a jsonable mapping and
    `canonical_json` sorts by discipline_id for a stable digest.
    """
    flat = {d: dataclasses.asdict(r) for d, r in terrain_feasibility.items()}
    return _sha256_hex(canonical_json(flat))


def compute_event_windows_hash(windows: list[Any]) -> str:
    """Event Windows Slice 1 (#581 WS-H) — SHA-256 of the declared event windows
    overlapping the plan span.

    Each window contributes `(override_type, start_date, end_date,
    unavailable_locale, away_locale, brought_craft)` — the declared inputs, NOT
    the derived resolutions (the cluster terrain/equipment that resolution
    depends on is already keyed via `compute_terrain_feasibility_hash`; an away
    destination's equipment edit evicts the plan caches via the locale-edit
    path). `brought_craft` (Slice 4, the (c) surface) is a declared window field,
    so it belongs here; the standing craft↔locale (b) surface is athlete-level
    data covered by `evict_plan_caches_on_craft_locale_change`, not this hash.
    Sorted for a stable digest. Folds into `plan_create_key` / `plan_refresh_key`;
    the caller passes None when no window overlaps the span so the key collapses
    to '' and stays byte-identical to the pre-Slice-1 key (the no-windows
    regression criterion).
    """
    flat = sorted(
        (
            {
                "override_type": w.override_type,
                "start_date": w.start_date,
                "end_date": w.end_date,
                "unavailable_locale": w.unavailable_locale,
                "away_locale": getattr(w, "away_locale", None),
                "brought_craft": sorted(getattr(w, "brought_craft", ()) or ()),
            }
            for w in windows
        ),
        key=lambda d: (
            d["start_date"],
            d["end_date"],
            d["override_type"],
            d["unavailable_locale"] or "",
            d["away_locale"] or "",
            tuple(d["brought_craft"]),
        ),
    )
    return _sha256_hex(canonical_json(flat))


def compute_layer2c_bundle_hash(locale_to_hash: dict[str, str]) -> str:
    """Per §9.1 — SHA-256 of canonical-JSON of {locale_id: layer2c_hash}, sorted by locale_id.

    Used by both `plan_create_key` and `race_week_brief_key` to fold a
    user's per-locale Layer 2C hashes into a single bundle hash component.
    """
    return _sha256_hex(canonical_json(locale_to_hash))


def compute_layer2_bundle_canonical_hash(layer2_hashes: dict[str, str | None]) -> str:
    """Per §9.1 `plan_refresh` — SHA-256 of canonical-JSON of {attr: layer2x_hash or None}.

    Keys MUST be exactly {'a', 'b', 'c', 'd', 'e'}; null entries preserved
    so the cache differentiates 'T1 cascade with 2A re-run' from 'T1 cascade
    with no Layer 2 re-run'.
    """
    if set(layer2_hashes.keys()) != _LAYER2_BUNDLE_ATTRS:
        raise ValueError(
            f"layer2_hashes must have keys exactly {sorted(_LAYER2_BUNDLE_ATTRS)}; "
            f"got {sorted(layer2_hashes.keys())}"
        )
    return _sha256_hex(canonical_json(layer2_hashes))


def compute_prior_plan_session_window_hash(sessions: list[PlanSession]) -> str:
    """Per §9.1 — SHA-256 of canonical-JSON of PlanSession list sorted by (date, session_index_in_day).

    The ±7-day context window per §3.2 IS included in the hashed set; the
    orchestrator should pass the full window (not the refresh scope only).
    """
    sorted_sessions = sorted(
        sessions, key=lambda s: (s.date, s.session_index_in_day, s.plan_version_id)
    )
    return _sha256_hex(canonical_json(sorted_sessions))


def plan_create_key(
    *,
    user_id: int,
    layer1_hash: str,
    layer2a_hash: str,
    layer2b_hash: str,
    layer2c_bundle_hash: str,
    layer2d_hash: str,
    layer2e_hash: str,
    layer3a_hash: str,
    layer3b_hash: str,
    plan_start_date: date,
    etl_version_set: dict[str, str],
    model_synthesizer: str,
    model_seam_reviewer: str,
    temperature: float,
    max_tokens_per_phase: int,
    capped_retries_per_phase: int,
    training_substitution_hash: str | None = None,
    terrain_feasibility_hash: str | None = None,
    event_windows_hash: str | None = None,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_plan_create`.

    `plan_version_id` is intentionally absent (allocated per call; rebinding
    on hit per §9.4). `layer2c_bundle_hash` is the bundle hash from
    `compute_layer2c_bundle_hash`.

    `training_substitution_hash` + `terrain_feasibility_hash` +
    `event_windows_hash` collapse None → '' so callers that don't supply those
    payloads retain stable keys.
    """
    components = [
        str(user_id),
        layer1_hash,
        layer2a_hash,
        layer2b_hash,
        layer2c_bundle_hash,
        layer2d_hash,
        layer2e_hash,
        layer3a_hash,
        layer3b_hash,
        plan_start_date.isoformat(),
        canonical_json(etl_version_set),
        model_synthesizer,
        model_seam_reviewer,
        str(temperature),
        str(max_tokens_per_phase),
        str(capped_retries_per_phase),
        training_substitution_hash or "",
        terrain_feasibility_hash or "",
    ]
    # Appended only when an event window overlaps the plan span, so a no-windows
    # plan keeps a key byte-identical to the pre-Slice-1 form (regression (a)).
    # LAYER4_PROMPT_REVISION stays the last component either way.
    if event_windows_hash:
        components.append(event_windows_hash)
    components.append(LAYER4_PROMPT_REVISION)
    return _sha256_hex("||".join(components))


def plan_refresh_key(
    *,
    user_id: int,
    tier: str,
    refresh_scope_start: date,
    refresh_scope_end: date,
    layer1_hash: str,
    layer2_bundle_canonical_hash: str,
    layer3a_hash: str,
    layer3b_hash: str,
    prior_plan_session_window_hash: str,
    parsed_intent_hash: str | None,
    etl_version_set: dict[str, str],
    model_synthesizer: str,
    model_seam_reviewer: str | None,
    temperature: float,
    max_tokens: int,
    capped_retries: int,
    training_substitution_hash: str | None = None,
    terrain_feasibility_hash: str | None = None,
    event_windows_hash: str | None = None,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_plan_refresh`.

    `model_seam_reviewer` MUST be None for Pattern B refreshes (T1, T2, T3
    intra-phase); only T3 cross-phase routes to Pattern A and contributes
    the seam-reviewer model to the key. None → '' in the key to prevent
    gratuitous cache misses on the model field for Pattern B refreshes.

    `training_substitution_hash` + `terrain_feasibility_hash` +
    `event_windows_hash` collapse None → '' so callers that don't supply those
    payloads retain stable keys.
    """
    components = [
        str(user_id),
        tier,
        refresh_scope_start.isoformat(),
        refresh_scope_end.isoformat(),
        layer1_hash,
        layer2_bundle_canonical_hash,
        layer3a_hash,
        layer3b_hash,
        prior_plan_session_window_hash,
        parsed_intent_hash or "",
        canonical_json(etl_version_set),
        model_synthesizer,
        model_seam_reviewer or "",
        str(temperature),
        str(max_tokens),
        str(capped_retries),
        training_substitution_hash or "",
        terrain_feasibility_hash or "",
    ]
    # Appended only when an event window overlaps the refresh span, keeping
    # no-windows refresh keys byte-identical to the pre-Slice-1 form.
    if event_windows_hash:
        components.append(event_windows_hash)
    components.append(LAYER4_PROMPT_REVISION)
    return _sha256_hex("||".join(components))


def single_session_synthesize_key(
    *,
    user_id: int,
    request: Any,
    layer1_hash: str,
    layer2c_locale_hash: str | None,
    layer2d_hash: str,
    layer3a_hash: str,
    etl_version_set: dict[str, str],
    model: str,
    temperature: float,
    max_tokens: int,
    capped_retries: int,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_single_session_synthesize`.

    `request` is the `SingleSessionRequest` shape per D-63 §4.3; passed
    through `canonical_json` so dicts / pydantic models / dataclasses all
    encode stably. `suggestion_id` is intentionally absent — rebinding
    on hit per §9.4.
    """
    components = [
        str(user_id),
        canonical_json(request),
        layer1_hash,
        layer2c_locale_hash or "",
        layer2d_hash,
        layer3a_hash,
        canonical_json(etl_version_set),
        model,
        str(temperature),
        str(max_tokens),
        str(capped_retries),
    ]
    return _sha256_hex("||".join(components))


def compute_accepted_output_hash(
    sessions: list[PlanSession],
    synthesis_metadata: Any,
) -> str:
    """Per §9.2 — SHA-256 of canonical-JSON of a phase's accepted
    `list[PlanSession]` + `PhaseSpec.synthesis_metadata`.

    Used as the chaining hash for the next phase's `phase_cache_key`.
    Phase i's accepted output is hashed once at end-of-phase and threaded
    into phase i+1's key via `compute_phase_cache_key(prev_accepted=...)`.
    """
    payload = {
        "sessions": [s.model_dump(mode="json") for s in sessions],
        "synthesis_metadata": synthesis_metadata.model_dump(mode="json")
        if hasattr(synthesis_metadata, "model_dump")
        else synthesis_metadata,
    }
    return _sha256_hex(canonical_json(payload))


def compute_phase_cache_key(
    *,
    call_cache_key: str,
    phase_name: str,
    phase_index: int,
    prev_accepted_output_hash: str | None,
) -> str:
    """Per §9.2 — chained per-phase cache key.

    Formula: `sha256(call_cache_key || phase_name || str(i) || prev_hash)`.

    `prev_accepted_output_hash` is None for the first phase (i == 0);
    None collapses to '' in the concatenation so the first phase's key is
    deterministic against the call cache key alone.
    """
    components = [
        call_cache_key,
        phase_name,
        str(phase_index),
        prev_accepted_output_hash or "",
    ]
    return _sha256_hex("||".join(components))


def compute_block_cache_key(
    *,
    call_cache_key: str,
    phase_name: str,
    phase_index: int,
    week_in_phase: int,
    prev_accepted_output_hash: str | None,
) -> str:
    """Per §9.2 (D-77) — chained per-week-block cache key.

    Same shape as `compute_phase_cache_key` plus `week_in_phase`, so the
    per-block chain rolls at week granularity: block `u`'s key folds in
    block `u-1`'s accepted-output hash, and a change at week `k` invalidates
    `k+1..end` only. `prev_accepted_output_hash` is None for the very first
    block of the plan (collapses to '' so its key is deterministic against
    the call cache key alone).
    """
    components = [
        call_cache_key,
        phase_name,
        str(phase_index),
        str(week_in_phase),
        prev_accepted_output_hash or "",
    ]
    return _sha256_hex("||".join(components))


def compute_seam_review_cache_key(
    *,
    call_cache_key: str,
    seam_index: int,
    prior_phase_sessions: list[PlanSession],
    next_phase_sessions: list[PlanSession],
    model: str,
    max_tokens: int,
    extended_thinking_budget: int,
) -> str:
    """Per §9.2 — cache key for an iteration-1 seam review.

    The iter-1 review is a pure function of the two phases' synthesized
    session outputs plus the upstream inputs already folded into
    `call_cache_key` (layer2a/2d, discipline mix, periodization mode +
    start_phase, race format, event date) plus the reviewer model + token
    config. Only the per-call-variable session lists are hashed here;
    everything else rides on `call_cache_key`. Iteration-2 (re-synthesis-
    driven) reviews are NOT cached — they mutate phase state and are the
    rare flagged path.
    """
    components = [
        call_cache_key,
        "seam",
        str(seam_index),
        _sha256_hex(canonical_json([s.model_dump(mode="json") for s in prior_phase_sessions])),
        _sha256_hex(canonical_json([s.model_dump(mode="json") for s in next_phase_sessions])),
        model,
        str(max_tokens),
        str(extended_thinking_budget),
    ]
    return _sha256_hex("||".join(components))


def compute_seam_resynth_block_cache_key(
    *,
    call_cache_key: str,
    phase_name: str,
    phase_index: int,
    week_in_phase: int,
    prev_accepted_output_hash: str | None,
    seam_index: int,
    seam_issues: list[str],
    seam_direction: str | None,
) -> str:
    """Per §9.2 (D-77 Slice 3) — chained per-week-block cache key for a
    SEAM-DRIVEN re-synthesis block.

    Same chained shape as `compute_block_cache_key` (so the re-synth's own
    blocks roll a week-granular chain), but additionally folds in the seam
    that triggered the re-synthesis (`seam_index`) and its constraint payload
    (`seam_issues` + `seam_direction`). This closes the §9.2 gap the prior
    whole-phase seam re-synth carried: a seam-fix block for (phase, week) must
    NOT collide with — or false-HIT — the ORIGINAL primary block at the same
    (phase, week), and two different seams targeting the same phase (e.g.
    re_prompt_next from seam i and re_prompt_prior from seam i+1) must key
    distinctly. The block is also stored under a disjoint `phase_idx`
    namespace; this key makes the content hash itself unambiguous so a change
    in the seam constraints invalidates the cached re-synth.
    """
    components = [
        call_cache_key,
        "seam_resynth",
        phase_name,
        str(phase_index),
        str(week_in_phase),
        prev_accepted_output_hash or "",
        str(seam_index),
        seam_direction or "",
        _sha256_hex("␟".join(seam_issues)),
    ]
    return _sha256_hex("||".join(components))


def race_week_brief_key(
    *,
    user_id: int,
    layer1_hash: str,
    layer2a_hash: str,
    layer2b_hash: str,
    layer2c_bundle_hash: str,
    layer2d_hash: str,
    layer2e_hash: str,
    layer3a_hash: str,
    layer3b_hash: str,
    prior_plan_session_window_hash: str,
    etl_version_set: dict[str, str],
    model: str,
    temperature: float,
    max_tokens: int,
    capped_retries: int,
    training_substitution_hash: str | None = None,
) -> str:
    """Per §9.1 — cache key for `llm_layer4_race_week_brief`.

    `today()` is intentionally absent — `days_to_event` shifts daily so the
    orchestrator invalidates `race_week_brief` caches at midnight UTC (per
    §9.3) rather than baking today's date into the key.

    `training_substitution_hash` collapses None → '' so callers that don't
    supply the payload retain stable keys.
    """
    components = [
        str(user_id),
        layer1_hash,
        layer2a_hash,
        layer2b_hash,
        layer2c_bundle_hash,
        layer2d_hash,
        layer2e_hash,
        layer3a_hash,
        layer3b_hash,
        prior_plan_session_window_hash,
        canonical_json(etl_version_set),
        model,
        str(temperature),
        str(max_tokens),
        str(capped_retries),
        training_substitution_hash or "",
    ]
    return _sha256_hex("||".join(components))
