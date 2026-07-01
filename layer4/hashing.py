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
# "18" = #339 follow-on — the variety carve-out generalized from foot-only to ANY
# within-mode equivalent (adds the wheel group: road-bike ↔ MTB ↔ gravel, the
# cycling analog of road ↔ trail run), and the cross-mode exclusion corrected to
# mean foot↔wheel↔water (not the within-cycling road↔MTB swap). Prompt body
# changed, so cached plans + refreshes regenerate.
# "19" = #803 strength resolution metadata derived deterministically — the
# per_phase SYSTEM_PROMPT strength bullet no longer asks the LLM to set
# resolution_tier / substitute_text / proxy_origin_id (the synthesizer sets them
# from each pick's 2C resolution before StrengthExercise construction). Prompt
# body changed, so cached plans regenerate.
# "20" = #954 coach_notes retired — the free-text `Coach notes:` athlete-context
# line is removed from every synthesizer (per_phase / plan_refresh T1-T3 /
# single_session / race_week_brief); the content was merged into Coaching memory
# (`coaching_preferences`, still rendered). The `coach_notes` field also leaves
# the Layer 1 payload, so `layer1_hash` shifts independently; this tag closes the
# prompt-body determinant so cached plans + refreshes regenerate.
# "21" = T-2.9, WS-2 upstream-signal wiring, folded in as one bump per R1
# (never bump per-issue): #301 — new `format_terrain_gap_detail()` renders
# per-discipline terrain-gap `uncoverable_stimulus`/`proxy_methods` across all
# 5 synthesizer prompts; #302 — `goal_viability.reasoning_text` now also
# renders in per_phase (race_week_brief already had it), and Layer3B's
# `notable_observations` tool-schema field + its auto-emit prompt instructions
# are removed (nothing downstream read it); #306 — `race_url` now renders in
# race_week_brief. (#297's Layer2B trim and #299's no-op left no prompt-body
# change of their own.) Cached plans + refreshes regenerate.
LAYER4_PROMPT_REVISION = "21"

# Prompt-body revision tag for the Layer 3A/3B LLM stages, mixed into the Layer 3D
# gate's "Reading B" staleness fingerprint (`compute_gate_input_fingerprint`).
# The gate's verdict is a function of the upstream 2A/2C/2D/2E/3B payloads; 3B
# (and 2E's start_phase) ride on the 3A/3B LLM outputs, which depend on the 3A/3B
# PROMPT bodies in addition to their inputs. The staleness fingerprint hashes the
# raw INPUTS those stages consume (so it never has to re-run the LLM just to
# re-check) — this revision tag closes the one determinant the inputs don't carry:
# a redeployed 3A/3B prompt while a plan sits parked at the review screen. Bump it
# whenever a 3A or 3B prompt-body change could shift the gate verdict, so a parked
# plan re-evaluates against the new prompt on review re-entry / [Generate].
# "1" = initial (#213 Layer 3D gate staleness, Reading B).
LAYER3_GATE_PROMPT_REVISION = "1"


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
    unavailable_locale, away_locale, brought_gear)` — the declared inputs, NOT
    the derived resolutions (the cluster terrain/equipment that resolution
    depends on is already keyed via `compute_terrain_feasibility_hash`; an away
    destination's equipment edit evicts the plan caches via the locale-edit
    path). The brought-gear set (Slice 4, the (c) surface) is a declared window
    field, so it belongs here; the standing gear↔locale (b) surface is
    athlete-level data covered by `evict_plan_caches_on_craft_locale_change`, not
    this hash. **The fold dict key is deliberately kept as the legacy string
    `"brought_craft"` even though the `EventWindow` attribute renamed to
    `brought_gear` in 6c-1: `canonical_json` serializes dict *keys* into the
    digest (`sort_keys=True`), so renaming the key would change
    `compute_event_windows_hash` for every athlete with an overlapping window — a
    one-time plan-cache invalidation for zero behavioural gain (the data is
    byte-identical). Keeping the key string stable keeps the digest stable.**
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
                # Key kept as the legacy "brought_craft" for digest stability
                # (see docstring); value reads the renamed `brought_gear` attr.
                "brought_craft": sorted(getattr(w, "brought_gear", ()) or ()),
                # Slice 6 (#593) — the per-window volume slider; a change must
                # invalidate the overlapping synthesis. None on non-volume types
                # → no effect on the existing no-windows / feasibility-only keys.
                "volume_pct": getattr(w, "volume_pct", None),
                # #889 — the per-DATE volume schedule. Flattened to a sorted
                # [iso_date, pct] list so editing one day's level invalidates the
                # overlapping synthesis. Empty/absent → []; a window with no
                # schedule stays byte-identical to the pre-#889 key.
                "volume_by_date": sorted(
                    (
                        d_.isoformat() if hasattr(d_, "isoformat") else str(d_),
                        p_,
                    )
                    for d_, p_ in (getattr(w, "volume_by_date", None) or {}).items()
                ),
                # #237 — the per-DATE restrictions. Flattened per day to a sorted
                # tuple so editing a locale-lock / indoor flag invalidates the
                # overlapping synthesis. Empty/absent → []; a window with no
                # restrictions stays byte-identical to the pre-#237 key.
                "restrictions_by_date": sorted(
                    (
                        d_.isoformat() if hasattr(d_, "isoformat") else str(d_),
                        r_.get("locale_lock") or "",
                        bool(r_.get("indoor_only")),
                    )
                    for d_, r_ in (getattr(w, "restrictions_by_date", None) or {}).items()
                ),
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
            d["volume_pct"] if d["volume_pct"] is not None else -1.0,
            tuple(tuple(pair) for pair in d["volume_by_date"]),
            tuple(tuple(row) for row in d["restrictions_by_date"]),
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
    everything else rides on `call_cache_key`. The iteration-2 (re-synthesis-
    driven) review of the same seam is cached under a distinct key — see
    `compute_seam_review_iter2_cache_key`.
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


def compute_week_seam_review_cache_key(
    *,
    call_cache_key: str,
    week_seam_index: int,
    prior_week_sessions: list[PlanSession],
    next_week_sessions: list[PlanSession],
    model: str,
    max_tokens: int,
    extended_thinking_budget: int,
) -> str:
    """Per §9.2 (D-77 Slice 3) — cache key for an iteration-1 INTRA-PHASE
    week-seam review. Mirrors `compute_seam_review_cache_key`: the iter-1 review
    is a pure function of the two weeks' synthesized session outputs plus the
    upstream inputs already folded into `call_cache_key` (layer2a/2d, discipline
    mix, periodization mode, race format, event date — and, via the per-block
    chain that produced those sessions, the per-week planned multipliers) plus
    the reviewer model + token config. `week_seam_index` is the global,
    monotonic intra-phase seam index (disjoint from the phase-seam `seam_index`
    namespace). Only the per-call-variable week session lists are hashed here.
    Iteration-2 reviews are NOT cached (they follow the rare flagged path)."""
    components = [
        call_cache_key,
        "week_seam",
        str(week_seam_index),
        _sha256_hex(canonical_json([s.model_dump(mode="json") for s in prior_week_sessions])),
        _sha256_hex(canonical_json([s.model_dump(mode="json") for s in next_week_sessions])),
        model,
        str(max_tokens),
        str(extended_thinking_budget),
    ]
    return _sha256_hex("||".join(components))


def compute_seam_review_iter2_cache_key(
    *,
    call_cache_key: str,
    seam_index: int,
    prior_phase_sessions: list[PlanSession],
    next_phase_sessions: list[PlanSession],
    prior_seam_issues: list[str],
    seam_direction: str | None,
    model: str,
    max_tokens: int,
    extended_thinking_budget: int,
) -> str:
    """Per §9.2 — cache key for an iteration-2 (re-synthesis-driven) seam review.

    The iter-2 review re-runs once (per §6.2 cap) after seam `seam_index`
    flagged in iter-1 and drove a re-synthesis of one of its phases. It is a
    pure function of the (now re-synthesized) two phases' session outputs —
    which are themselves deterministically reproduced from the seam-resynth
    block cache on a resumed pass — plus the iter-1 seam issues threaded into
    the prompt (`prior_seam_issues`), the re-prompt direction that drove the
    re-synthesis (`seam_direction`), and the upstream inputs already folded
    into `call_cache_key`. This closes the §9.2 gap where the iter-2 seam
    review tail re-ran whole on every resumable pass.

    Keyed distinctly from the iter-1 review (`compute_seam_review_cache_key`)
    via the "seam_iter2" tag plus the extra iter-1-issues / direction
    components, so the two iterations of the same seam can never collide.
    """
    components = [
        call_cache_key,
        "seam_iter2",
        str(seam_index),
        _sha256_hex(canonical_json([s.model_dump(mode="json") for s in prior_phase_sessions])),
        _sha256_hex(canonical_json([s.model_dump(mode="json") for s in next_phase_sessions])),
        _sha256_hex("␟".join(prior_seam_issues)),
        seam_direction or "",
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
