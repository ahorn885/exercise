"""Deterministic post-synthesis locale assignment + substitution — Track 2
slice 2c (§5.5 of `Layer4_DeterminismFirst_Synthesis_Design_v1.md`).

The synthesizer picks the **ideal** strength exercise set per session,
locale-agnostic, from the cluster-union enum (slice 2a). This module then
runs deterministically post-synth, per strength session:

  1. Pick the cluster locale where the majority of the ideal set fits
     (highest `equipment_required ⊆ effective_pool` coverage; ties → home;
     second tie → lowest-slug alphabetical).
  2. Mutate non-fitting exercises via a 3-tier ladder:
       (a) pattern-match substitute from the chosen locale's resolved pool
           (movement-pattern overlap; matching/adjacent sport priority)
       (b) tier-3 bodyweight proxy from the chosen locale's pool (a
           bodyweight exercise sharing a movement_pattern with the original)
       (c) **small-call LLM substitute** (§5.5 step 6) — single-purpose Haiku
           call, enum-bounded by the locale pool. Last-resort path; ≤1 call
           per `assign_locales` invocation (budget).
       (d) Tail — emit `substitution_no_candidate` coaching flag, keep the
           original exercise; the LLM-text fallback (resolution_tier stays 1)
           is the synthesizer's already-emitted prescription.

Cardio-session locale routing (§5.5 final ¶) is deferred to slice 2c.2;
needs the discipline→required_terrain layer0 vocab work first. Cardio +
rest sessions are unchanged by this module — locale_id remains as the
synthesizer emitted it (typically None pre-assign).

Observability (Rule #14): every assign_locales call returns a
`LocaleAssignDiagnostic` summarizing per-session outcomes (chosen locale,
fit_count, substitution path taken per exercise, LLM call latency). Log
lines are prefixed `assign_locales:` for `grep` legibility against Vercel
runtime logs. Wire this dict into per-block `synthesis_metadata` so a
plan-gen failure that traces back here is identifiable in the diag JSON.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from layer4.context import Layer2CPayload, ResolvedExercise
from layer4.payload import PlanSession, StrengthExercise

_log = logging.getLogger(__name__)

# Budget: at most one small-call LLM substitution per assign_locales call.
# Per spec §5.5 step 6 — bounds latency / Anthropic-cost exposure on the
# rare impossible-tail path. Subsequent stuck exercises fall through to the
# coaching-flag tail.
_LLM_SUBSTITUTE_CALLS_PER_INVOCATION = 1

# Haiku model id (latest Claude 4.5 Haiku; per the project's model identity).
_LLM_SUBSTITUTE_MODEL = "claude-haiku-4-5-20251001"


# ─── Diagnostic dataclasses ─────────────────────────────────────────────────


@dataclass(frozen=True)
class SessionAssignment:
    """Per-session result. `chosen_locale` is None when the session wasn't
    a strength session (we don't touch cardio in slice 2c) or when the
    cluster was empty (degenerate input)."""

    session_id: str
    chosen_locale: str | None
    fit_count: int
    ideal_set_size: int
    substitutions: list["ExerciseSubstitution"] = field(default_factory=list)


@dataclass(frozen=True)
class ExerciseSubstitution:
    """Per-exercise substitution decision."""

    original_exercise_id: str
    path: str  # "kept" | "pattern_match" | "tier3_proxy" | "llm_substitute" | "no_candidate"
    substitute_exercise_id: str | None  # None for "kept" and "no_candidate"


@dataclass(frozen=True)
class LocaleAssignDiagnostic:
    """Summary surfaced to the plan-gen caller for `synthesis_metadata`
    inclusion. Empty `assignments` when called with no strength sessions."""

    assignments: list[SessionAssignment] = field(default_factory=list)
    llm_calls: int = 0
    llm_total_latency_ms: int = 0
    cluster_locale_ids: list[str] = field(default_factory=list)
    home_locale_id: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        """JSON-safe dict for `synthesis_metadata` inclusion."""
        return {
            "track2_slice2c_locale_assign": {
                "session_count": len(self.assignments),
                "llm_substitute_calls": self.llm_calls,
                "llm_substitute_latency_ms": self.llm_total_latency_ms,
                "cluster_locale_ids": self.cluster_locale_ids,
                "home_locale_id": self.home_locale_id,
                "assignments": [
                    {
                        "session_id": a.session_id,
                        "chosen_locale": a.chosen_locale,
                        "fit_count": a.fit_count,
                        "ideal_set_size": a.ideal_set_size,
                        "substitutions": [
                            {
                                "original": s.original_exercise_id,
                                "path": s.path,
                                "substitute": s.substitute_exercise_id,
                            }
                            for s in a.substitutions
                        ],
                    }
                    for a in self.assignments
                ],
            }
        }


# ─── Internal helpers ───────────────────────────────────────────────────────


def _movement_pattern_set(exercise: ResolvedExercise | StrengthExercise) -> frozenset[str]:
    """Case-folded, whitespace-stripped patterns set. Robust to inconsistent
    casing in 0B data ('Single-Leg' vs 'single-leg'). Payload `StrengthExercise`
    doesn't carry movement_patterns (it's on the 2C `ResolvedExercise` side) —
    callers look up patterns from the cluster-union resolved set, not the
    emitted strength exercise."""
    raw: list[str] | None = getattr(exercise, "movement_patterns", None)
    if not raw:
        return frozenset()
    return frozenset((p or "").strip().lower() for p in raw if p)


def _build_cluster_resolved_index(
    layer2c_payloads: dict[str, Layer2CPayload],
) -> dict[str, ResolvedExercise]:
    """Union of all locales' exercises_resolved keyed by exercise_id. When the
    same exercise_id appears in multiple locales (typical — same Layer 0B
    exercise resolved at different locales with potentially different
    equipment), the first wins; we only use this for movement_pattern lookup
    on the ORIGINAL emitted exercise (locale-agnostic per spec §5.5 step 1).
    """
    index: dict[str, ResolvedExercise] = {}
    for l2c in layer2c_payloads.values():
        for ex in l2c.exercises_resolved:
            if ex.exercise_id not in index:
                index[ex.exercise_id] = ex
    return index


def _resolved_by_id(layer2c: Layer2CPayload) -> dict[str, ResolvedExercise]:
    """Index a locale's resolved exercises by id for O(1) fit checks."""
    return {ex.exercise_id: ex for ex in layer2c.exercises_resolved}


def _pick_locale_by_majority_fit(
    ideal_set: frozenset[str],
    cluster_locale_ids: list[str],
    layer2c_payloads: dict[str, Layer2CPayload],
    home_locale_id: str,
) -> tuple[str, int]:
    """§5.5 step 2-3. Returns (chosen_locale, fit_count).

    Ties: home wins. Second tie: lowest locale_id alphabetically (deterministic;
    haversine sort needs lat/lng data we don't surface here in slice 2c —
    alphabetical is a deterministic stand-in until cardio routing lands and
    adds the haversine path).
    """
    best_locale = home_locale_id
    best_fit = -1  # -1 sentinel so even fit_count=0 picks a locale on first iter
    for loc in cluster_locale_ids:
        l2c = layer2c_payloads.get(loc)
        if l2c is None:
            continue  # no resolved pool for this locale (degenerate)
        resolved_ids = {ex.exercise_id for ex in l2c.exercises_resolved}
        fit = len(ideal_set & resolved_ids)
        if fit > best_fit:
            best_locale, best_fit = loc, fit
        elif fit == best_fit:
            if loc == home_locale_id:
                best_locale = loc
            elif best_locale != home_locale_id and loc < best_locale:
                best_locale = loc
    return best_locale, max(0, best_fit)


def _pattern_match_substitute(
    original: StrengthExercise,
    original_patterns: frozenset[str],
    locale_resolved: dict[str, ResolvedExercise],
    excluded_ids: set[str],
) -> str | None:
    """§5.5 step 4. Find a NON-bodyweight (tier 1/2) exercise from the locale's
    resolved pool that shares any movement pattern with `original` and isn't
    excluded. Ranks by (1) larger pattern overlap, (2) lower-numbered
    exercise_id (stable tiebreak). Bodyweight (tier 0/3) candidates are
    excluded here — they're the next ladder rung's job (`_tier3_bodyweight_proxy`).
    Returns substitute_exercise_id or None."""
    if not original_patterns:
        return None
    candidates: list[tuple[int, str]] = []
    for ex_id, ex in locale_resolved.items():
        if ex_id == original.exercise_id or ex_id in excluded_ids:
            continue
        # Bodyweight tiers (0/3) are reserved for the tier-3 proxy rung.
        # Tier-1 (ideal) and tier-2 (substitute) are valid pattern-match picks.
        if getattr(ex, "tier", None) in (0, 3):
            continue
        cand_patterns = _movement_pattern_set(ex)
        overlap = len(original_patterns & cand_patterns)
        if overlap > 0:
            candidates.append((overlap, ex_id))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (-t[0], t[1]))
    return candidates[0][1]


def _tier3_bodyweight_proxy(
    original_patterns: frozenset[str],
    locale_resolved: dict[str, ResolvedExercise],
    excluded_ids: set[str],
) -> str | None:
    """§5.5 step 5. Bodyweight proxy = a resolved exercise tagged tier=3 (the
    layer0 substitution-tier label, not the payload resolution_tier) that
    shares a movement pattern with the original. Falls back to any
    pattern-matching resolved exercise tagged tier=0/3 (which encode the
    "improvised / bodyweight" set in 2C). Returns substitute_exercise_id or
    None when no qualifying bodyweight option exists at the locale."""
    if not original_patterns:
        return None
    for ex_id, ex in locale_resolved.items():
        if ex_id in excluded_ids:
            continue
        if getattr(ex, "tier", None) not in (0, 3):
            continue
        cand_patterns = _movement_pattern_set(ex)
        if original_patterns & cand_patterns:
            return ex_id
    return None


def _hash_excluded(excluded_ids: set[str], pool_ids: list[str]) -> str:
    """Stable hash for the in-memory substitution cache key (§5.5 step 6).
    `(original_id, locale_id, hash) → substitute_id`. Stable across calls
    within one invocation — persistent across-athletes cache requires a new
    layer4_cache entry_point (v1.1 follow-up; not in 2c)."""
    payload = json.dumps(
        {"excluded": sorted(excluded_ids), "pool": sorted(pool_ids)},
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]


def _llm_substitute_tool_schema(pool_ids: list[str]) -> dict[str, Any]:
    """Single-purpose tool, enum-bounded by the locale pool minus excluded —
    invalid picks are structurally impossible at the SDK boundary, mirroring
    slice 2a's enum guarantee."""
    return {
        "name": "pick_substitute_exercise",
        "description": (
            "Pick the closest available substitute exercise from the locale's "
            "pool that preserves the original's training stimulus."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "substitute_exercise_id": {
                    "type": "string",
                    "enum": pool_ids,
                    "description": (
                        "ID of the substitute exercise from the locale's "
                        "available pool."
                    ),
                },
                "preserves_intent": {
                    "type": "boolean",
                    "description": (
                        "True if the substitute genuinely targets the "
                        "original's movement pattern; false if reaching."
                    ),
                },
            },
            "required": ["substitute_exercise_id", "preserves_intent"],
        },
    }


def _build_llm_substitute_prompt(
    original: StrengthExercise,
    original_patterns: frozenset[str],
    sport_priority: str | None,
    excluded_ids: set[str],
) -> str:
    """Tight system prompt — no periodization context, no week framing.
    Per spec §5.5 step 6 + Andy's Trigger-#1 sign-off (2026-06-06)."""
    patterns_str = ", ".join(sorted(original_patterns)) if original_patterns else "unknown"
    priority_str = sport_priority or "unspecified"
    excluded_str = ", ".join(sorted(excluded_ids)) if excluded_ids else "none"
    return (
        "You are an endurance-strength coach picking a substitute exercise.\n\n"
        f"The athlete prescribed exercise {original.exercise_id} "
        f"({original.exercise_name}) but the equipment isn't available at the "
        "chosen training locale. Pick the closest substitute from the locale's "
        "available exercises that preserves the training stimulus.\n\n"
        "Constraints:\n"
        f"- The original targets movement pattern(s): {patterns_str}.\n"
        f"- The original's sport-priority rank is {priority_str} (Critical / High / Medium / Low).\n"
        "- Prefer substitutes sharing at least one movement pattern.\n"
        "- Prefer same sport-priority tier; allow ±1 tier.\n"
        f"- Excluded ids (injury / equipment / 2D filters): {excluded_str} — never pick these.\n\n"
        "Use the pick_substitute_exercise tool. Set preserves_intent=true only "
        "if the substitute genuinely targets the original's movement pattern; "
        "false if you're stretching to find anything in the pool."
    )


def _invoke_llm_substitute(
    original: StrengthExercise,
    original_patterns: frozenset[str],
    sport_priority: str | None,
    pool_ids: list[str],
    excluded_ids: set[str],
    *,
    caller: Callable[..., Any] | None,
) -> tuple[str | None, bool, int]:
    """§5.5 step 6 small-call LLM substitution. Returns
    (substitute_exercise_id, preserves_intent, latency_ms).
    `caller` is the dependency-injected Anthropic client wrapper; None
    short-circuits to a no-candidate result (test path).

    Substitute is None when the LLM declines or the tool args don't parse.
    The caller treats None as "fell through to coaching-flag tail"."""
    if caller is None:
        _log.info(
            "assign_locales: llm_substitute_caller=None — skipping LLM fallback for ex=%s",
            original.exercise_id,
        )
        return None, False, 0
    if not pool_ids:
        _log.info(
            "assign_locales: empty pool_ids for ex=%s — skipping LLM fallback",
            original.exercise_id,
        )
        return None, False, 0
    tool_schema = _llm_substitute_tool_schema(pool_ids)
    prompt = _build_llm_substitute_prompt(
        original, original_patterns, sport_priority, excluded_ids
    )
    t0 = time.monotonic()
    try:
        tool_args = caller(
            model=_LLM_SUBSTITUTE_MODEL,
            system_prompt=prompt,
            tool=tool_schema,
            max_tokens=512,
        )
    except Exception as exc:  # caller may raise; we degrade to coaching-flag tail
        latency_ms = int((time.monotonic() - t0) * 1000)
        _log.warning(
            "assign_locales: llm_substitute raised for ex=%s latency_ms=%d: %s",
            original.exercise_id, latency_ms, exc,
        )
        return None, False, latency_ms
    latency_ms = int((time.monotonic() - t0) * 1000)
    if not isinstance(tool_args, dict):
        _log.warning(
            "assign_locales: llm_substitute returned non-dict tool_args for ex=%s",
            original.exercise_id,
        )
        return None, False, latency_ms
    sub_id = tool_args.get("substitute_exercise_id")
    preserves = bool(tool_args.get("preserves_intent", False))
    if not isinstance(sub_id, str) or sub_id not in pool_ids:
        _log.warning(
            "assign_locales: llm_substitute returned out-of-pool id %r for ex=%s",
            sub_id, original.exercise_id,
        )
        return None, preserves, latency_ms
    _log.info(
        "assign_locales: llm_substitute ex=%s -> %s preserves=%s latency_ms=%d",
        original.exercise_id, sub_id, preserves, latency_ms,
    )
    return sub_id, preserves, latency_ms


# ─── Public API ─────────────────────────────────────────────────────────────


def assign_locales(
    sessions: list[PlanSession],
    layer2c_payloads: dict[str, Layer2CPayload],
    db: Any,
    user_id: int,
    *,
    home_locale_id: str | None = None,
    cluster_locale_ids: list[str] | None = None,
    excluded_exercise_ids: set[str] | None = None,
    llm_substitute_caller: Callable[..., Any] | None = None,
) -> tuple[list[PlanSession], LocaleAssignDiagnostic]:
    """Per spec §5.5. Returns (mutated_sessions, diagnostic).

    Determinism boundaries:
      - Strength sessions: locale assigned + non-fitting exercises substituted.
      - Cardio sessions: untouched in slice 2c (cardio routing → 2c.2 follow-up).
      - Rest sessions: untouched (no locale by schema invariant).

    `home_locale_id` and `cluster_locale_ids` are optional injected args
    (mainly for tests); when omitted they're queried via the `locations`
    module against `db` / `user_id`. The LLM substitute fallback is
    bypassed when `llm_substitute_caller` is None (default), which keeps
    unit tests fast/offline and is also what plan_create.py passes today
    until a concrete Haiku wrapper is wired.
    """
    # Resolve cluster + home via locations (avoid circular imports at module load).
    if home_locale_id is None or cluster_locale_ids is None:
        from locations import (
            primary_locale,
            cluster_locale_ids as _cluster_locale_ids,
        )
        if home_locale_id is None:
            home_locale_id = primary_locale(db, user_id)
        if cluster_locale_ids is None:
            cluster_locale_ids = _cluster_locale_ids(db, user_id)

    excluded_exercise_ids = excluded_exercise_ids or set()
    cluster_locale_ids = cluster_locale_ids or [home_locale_id]
    diag = LocaleAssignDiagnostic(
        assignments=[],
        llm_calls=0,
        llm_total_latency_ms=0,
        cluster_locale_ids=list(cluster_locale_ids),
        home_locale_id=home_locale_id,
    )

    # Build name lookup once (one cheap query, batched).
    locale_names = _load_locale_names(db, user_id, cluster_locale_ids)

    # Build cluster-union resolved index ONCE per call; used to look up
    # movement_patterns for ORIGINAL emitted exercise ids (the payload
    # `StrengthExercise` doesn't carry patterns — those live on the 2C
    # `ResolvedExercise` side, locale-agnostic per spec §5.5 step 1).
    cluster_resolved_index = _build_cluster_resolved_index(layer2c_payloads)

    # Mutable diag counters (reassign to a new frozen dataclass at the end).
    llm_calls = 0
    llm_total_latency_ms = 0
    # In-memory substitution cache scoped to this invocation only —
    # `(original_id, locale_id, excluded_hash)` → substitute_id. v1.1
    # follow-up lifts this to a persistent layer4_cache entry_point.
    llm_sub_cache: dict[tuple[str, str, str], str | None] = {}

    new_sessions: list[PlanSession] = []
    assignments: list[SessionAssignment] = []

    for session in sessions:
        if session.kind != "strength" or not session.strength_exercises:
            new_sessions.append(session)
            continue

        ideal_set = frozenset(ex.exercise_id for ex in session.strength_exercises)

        chosen_locale, fit_count = _pick_locale_by_majority_fit(
            ideal_set=ideal_set,
            cluster_locale_ids=list(cluster_locale_ids),
            layer2c_payloads=layer2c_payloads,
            home_locale_id=home_locale_id,
        )

        chosen_l2c = layer2c_payloads.get(chosen_locale)
        if chosen_l2c is None:
            # Degenerate: chosen locale has no 2C payload — pass through
            # untouched but mark the assignment for diagnostics.
            _log.warning(
                "assign_locales: session=%s chosen_locale=%s has no Layer2CPayload "
                "— passing through unchanged",
                session.session_id, chosen_locale,
            )
            new_sessions.append(session)
            assignments.append(SessionAssignment(
                session_id=session.session_id,
                chosen_locale=chosen_locale,
                fit_count=0,
                ideal_set_size=len(ideal_set),
            ))
            continue

        resolved_at_chosen = _resolved_by_id(chosen_l2c)
        resolved_ids_at_chosen = set(resolved_at_chosen.keys())

        # Mutate non-fitting exercises.
        new_exercises: list[StrengthExercise] = []
        substitutions: list[ExerciseSubstitution] = []
        for ex in session.strength_exercises:
            if ex.exercise_id in resolved_ids_at_chosen:
                # Fits — keep as-is.
                new_exercises.append(ex)
                substitutions.append(ExerciseSubstitution(
                    original_exercise_id=ex.exercise_id,
                    path="kept",
                    substitute_exercise_id=ex.exercise_id,
                ))
                continue

            # Look up the ORIGINAL exercise's patterns from the cluster-union
            # 2C resolved set (locale-agnostic). The payload StrengthExercise
            # doesn't carry patterns — that data lives on ResolvedExercise.
            original_resolved = cluster_resolved_index.get(ex.exercise_id)
            patterns = (
                _movement_pattern_set(original_resolved)
                if original_resolved is not None
                else frozenset()
            )
            sport_priority = None
            # Layer 2C tracks per-discipline priority; we don't have the
            # session's discipline_id wired here (it's per-discipline; would
            # need session metadata threading). Pass None; the LLM prompt
            # documents that priority is "unspecified" if absent — Andy's
            # Trigger-#1 prompt explicitly handles the unspecified case.

            # (a) pattern-match substitute
            sub_id = _pattern_match_substitute(
                original=ex,
                original_patterns=patterns,
                locale_resolved=resolved_at_chosen,
                excluded_ids=excluded_exercise_ids,
            )
            if sub_id is not None:
                sub = resolved_at_chosen[sub_id]
                new_exercises.append(_swap_to_substitute(ex, sub, tier=2))
                substitutions.append(ExerciseSubstitution(
                    original_exercise_id=ex.exercise_id,
                    path="pattern_match",
                    substitute_exercise_id=sub_id,
                ))
                continue

            # (b) tier-3 bodyweight proxy
            sub_id = _tier3_bodyweight_proxy(
                original_patterns=patterns,
                locale_resolved=resolved_at_chosen,
                excluded_ids=excluded_exercise_ids,
            )
            if sub_id is not None:
                sub = resolved_at_chosen[sub_id]
                new_exercises.append(_swap_to_proxy(ex, sub))
                substitutions.append(ExerciseSubstitution(
                    original_exercise_id=ex.exercise_id,
                    path="tier3_proxy",
                    substitute_exercise_id=sub_id,
                ))
                continue

            # (c) small-call LLM substitute — budget-gated, cached per invocation
            pool_ids = sorted(resolved_ids_at_chosen - excluded_exercise_ids)
            cache_key = (
                ex.exercise_id,
                chosen_locale,
                _hash_excluded(excluded_exercise_ids, pool_ids),
            )
            llm_sub_id: str | None = None
            if cache_key in llm_sub_cache:
                llm_sub_id = llm_sub_cache[cache_key]
            elif (
                llm_substitute_caller is not None
                and llm_calls < _LLM_SUBSTITUTE_CALLS_PER_INVOCATION
            ):
                llm_sub_id, _preserves, latency_ms = _invoke_llm_substitute(
                    original=ex,
                    original_patterns=patterns,
                    sport_priority=sport_priority,
                    pool_ids=pool_ids,
                    excluded_ids=excluded_exercise_ids,
                    caller=llm_substitute_caller,
                )
                llm_calls += 1
                llm_total_latency_ms += latency_ms
                llm_sub_cache[cache_key] = llm_sub_id

            if llm_sub_id is not None:
                sub = resolved_at_chosen[llm_sub_id]
                new_exercises.append(_swap_to_substitute(ex, sub, tier=2))
                substitutions.append(ExerciseSubstitution(
                    original_exercise_id=ex.exercise_id,
                    path="llm_substitute",
                    substitute_exercise_id=llm_sub_id,
                ))
                continue

            # (d) coaching-flag tail — keep original, add flag
            new_flags = list(ex.coaching_flags)
            if "substitution_no_candidate" not in new_flags:
                new_flags.append("substitution_no_candidate")
            new_exercises.append(ex.model_copy(update={"coaching_flags": new_flags}))
            substitutions.append(ExerciseSubstitution(
                original_exercise_id=ex.exercise_id,
                path="no_candidate",
                substitute_exercise_id=None,
            ))
            _log.warning(
                "assign_locales: session=%s ex=%s — no substitute available at "
                "locale=%s; emitted substitution_no_candidate flag",
                session.session_id, ex.exercise_id, chosen_locale,
            )

        locale_name = locale_names.get(chosen_locale)
        new_session = session.model_copy(update={
            "locale_id": chosen_locale,
            "locale_name": locale_name,
            "strength_exercises": new_exercises,
        })
        new_sessions.append(new_session)
        assignments.append(SessionAssignment(
            session_id=session.session_id,
            chosen_locale=chosen_locale,
            fit_count=fit_count,
            ideal_set_size=len(ideal_set),
            substitutions=substitutions,
        ))
        _log.info(
            "assign_locales: session=%s -> locale=%s fit=%d/%d subs=%d",
            session.session_id, chosen_locale, fit_count, len(ideal_set),
            len([s for s in substitutions if s.path != "kept"]),
        )

    final_diag = LocaleAssignDiagnostic(
        assignments=assignments,
        llm_calls=llm_calls,
        llm_total_latency_ms=llm_total_latency_ms,
        cluster_locale_ids=list(cluster_locale_ids),
        home_locale_id=home_locale_id,
    )
    return new_sessions, final_diag


def _swap_to_substitute(
    original: StrengthExercise,
    sub: ResolvedExercise,
    *,
    tier: int,
) -> StrengthExercise:
    """Pattern-match / LLM substitute → resolution_tier=2, substitute_text
    set, proxy_origin_id None (per payload §7.4)."""
    return original.model_copy(update={
        "exercise_id": sub.exercise_id,
        "exercise_name": sub.exercise_name,
        "resolution_tier": tier,
        "substitute_text": (
            f"Substituted from {original.exercise_id} ({original.exercise_name}) — "
            "equipment not available at chosen locale."
        ),
        "proxy_origin_id": None,
    })


def _swap_to_proxy(
    original: StrengthExercise,
    sub: ResolvedExercise,
) -> StrengthExercise:
    """Tier-3 bodyweight proxy → resolution_tier=3, proxy_origin_id set,
    substitute_text None (per payload §7.4)."""
    return original.model_copy(update={
        "exercise_id": sub.exercise_id,
        "exercise_name": sub.exercise_name,
        "resolution_tier": 3,
        "substitute_text": None,
        "proxy_origin_id": original.exercise_id,
    })


def _load_locale_names(
    db: Any,
    user_id: int,
    cluster_locale_ids: list[str],
) -> dict[str, str]:
    """Batch lookup of display names. Returns {} on any error — locale_name
    is non-load-bearing (the assigned `locale_id` is the source of truth)."""
    if not cluster_locale_ids:
        return {}
    try:
        placeholders = ",".join("?" * len(cluster_locale_ids))
        cur = db.execute(
            f"SELECT locale, locale_name FROM locale_profiles "
            f"WHERE user_id = ? AND locale IN ({placeholders})",
            (user_id, *cluster_locale_ids),
        )
        return {r["locale"]: r["locale_name"] for r in cur.fetchall()}
    except Exception as exc:
        _log.warning("assign_locales: locale_name lookup failed: %s", exc)
        return {}


__all__ = [
    "ExerciseSubstitution",
    "LocaleAssignDiagnostic",
    "SessionAssignment",
    "assign_locales",
]
