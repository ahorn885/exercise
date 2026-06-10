"""Deterministic post-synthesis rx wiring — Track 2 slice 2d
(§7 of `Layer4_DeterminismFirst_Synthesis_Design_v1.md`).

The synthesizer emits `StrengthExercise.load_prescription` as advisory text.
This module runs deterministically after locale assignment and overwrites
`load_prescription` with the precise baseline read from `current_rx`. When
there's no `current_rx` row (first exposure for this athlete + exercise),
it writes a category-keyed RPE template and appends a `first_exposure`
coaching flag so the UI can render the calibration framing.

NO LLM in this path. The first-exposure templates are a deterministic
lookup off a 5-bucket categorisation derived from the exercise's
`movement_patterns` (from the 2C `ResolvedExercise` side) + its name.

Track 3 dependency: `rx_engine.current_rx` reads `public.exercise_inventory`
via the `current_rx.exercise` (TEXT name) column; Track 3 moves rx storage
to layer0 ids. Until then, a layer0-only exercise (no public-catalog name
match) falls through to first-exposure. Acceptable v1 behaviour; full
coverage follows Track 3.

Observability (Rule #14): every `apply_current_rx` call returns an
`RxWireDiagnostic` summarising per-exercise outcomes (rx hit, first-exposure
category, db-error skips). Log lines are prefixed `rx_wire:` for grep
legibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from layer4.context import Layer2CPayload, ResolvedExercise
from layer4.payload import Layer4Payload, PlanSession, StrengthExercise

_log = logging.getLogger(__name__)

_FIRST_EXPOSURE_FLAG = "first_exposure"

# Movement patterns that mark an exercise as a compound lift. Lower-cased +
# whitespace-stripped for robust matching against 0B data ('Single-Leg'
# vs 'single-leg'). Patterns outside this set classify as accessory.
_COMPOUND_PATTERNS: frozenset[str] = frozenset({
    "squat", "hinge", "push", "pull", "lunge",
})

# Category → first-exposure calibration template (spec §7).
_FIRST_EXPOSURE_TEMPLATES: dict[str, str] = {
    "compound_barbell": (
        "Calibration set — pick a weight that feels RPE 6 for 8 reps; "
        "log to set baseline"
    ),
    "compound_dumbbell": (
        "Calibration — pick DBs that feel RPE 6 for 10 reps; log to set baseline"
    ),
    "accessory_dumbbell": (
        "Calibration — pick DBs that feel RPE 7 for 12 reps; log to set baseline"
    ),
    "accessory_cable": (
        "Calibration — pick a load that feels RPE 7 for 12 reps; log to set baseline"
    ),
    "bodyweight": (
        "3 sets × max reps with 2 reps in reserve; log to set baseline"
    ),
}


# ─── Diagnostic dataclasses ────────────────────────────────────────────────


@dataclass(frozen=True)
class ExerciseRxOutcome:
    """Per-exercise rx-wire decision."""

    session_id: str
    exercise_id: str
    path: str  # "current_rx" | "first_exposure" | "skipped"
    category: str | None = None  # populated for first_exposure
    rendered: str | None = None  # the load_prescription we wrote


@dataclass(frozen=True)
class RxWireDiagnostic:
    """Summary surfaced to the plan-gen caller for `synthesis_metadata`
    inclusion. Empty `outcomes` when called with no strength sessions."""

    outcomes: list[ExerciseRxOutcome] = field(default_factory=list)
    current_rx_hits: int = 0
    first_exposure_count: int = 0
    skipped_count: int = 0

    def to_metadata(self) -> dict[str, Any]:
        """JSON-safe dict for `synthesis_metadata` inclusion."""
        return {
            "track2_slice2d_rx_wire": {
                "exercise_count": len(self.outcomes),
                "current_rx_hits": self.current_rx_hits,
                "first_exposure_count": self.first_exposure_count,
                "skipped_count": self.skipped_count,
                "outcomes": [
                    {
                        "session_id": o.session_id,
                        "exercise_id": o.exercise_id,
                        "path": o.path,
                        "category": o.category,
                    }
                    for o in self.outcomes
                ],
            }
        }


# ─── Internal helpers ──────────────────────────────────────────────────────


def _build_cluster_resolved_index(
    layer2c_payloads: dict[str, Layer2CPayload],
) -> dict[str, ResolvedExercise]:
    """Union of all locales' exercises_resolved keyed by exercise_id.
    Locale-agnostic — we only use this for movement_pattern + tier lookup
    on the ORIGINAL emitted exercise (which classifies the same way at any
    locale). First occurrence wins on collision."""
    index: dict[str, ResolvedExercise] = {}
    for l2c in layer2c_payloads.values():
        for ex in l2c.exercises_resolved:
            if ex.exercise_id not in index:
                index[ex.exercise_id] = ex
    return index


def _classify_category(
    exercise: StrengthExercise,
    resolved: ResolvedExercise | None,
) -> str:
    """Map a `StrengthExercise` to one of the 5 first-exposure template
    categories (§7). Deterministic; no fallback to LLM.

    Logic:
      1. If resolved 2C tier ∈ {0, 3} → bodyweight (substitution band).
      2. Else inspect the exercise name (canonical 0B name) for equipment cue.
      3. Compound = a movement pattern in {squat, hinge, push, pull, lunge}.

    Default when no equipment cue is found: bodyweight (the conservative pick —
    the calibration template is "max reps with 2 RIR" which never recommends
    a load the athlete shouldn't pick).
    """
    # Layer 2C uses tier 0/3 for the bodyweight/improvised substitution band.
    if resolved is not None and getattr(resolved, "tier", None) in (0, 3):
        return "bodyweight"

    patterns = frozenset(
        (p or "").strip().lower()
        for p in (resolved.movement_patterns if resolved else [])
        if p
    )
    is_compound = bool(patterns & _COMPOUND_PATTERNS)

    name_lower = exercise.exercise_name.lower()
    if "barbell" in name_lower:
        return "compound_barbell"  # barbell lifts are compound by convention
    if "dumbbell" in name_lower:
        return "compound_dumbbell" if is_compound else "accessory_dumbbell"
    if "cable" in name_lower or "machine" in name_lower:
        return "accessory_cable"
    if "bodyweight" in name_lower:
        return "bodyweight"
    # No equipment cue and no compound pattern → conservative bodyweight.
    # An accessory dumbbell pick here would invite the athlete to guess a
    # load when none is implied by the exercise name.
    return "compound_barbell" if is_compound else "bodyweight"


def _render_current_rx(rx: dict[str, Any], unit_pref: str | None = None) -> str | None:
    """Format `{sets, reps, weight_kg}` as `"{sets} × {reps} @ {wt} {unit}"`.

    `unit_pref` selects the athlete's display unit (`imperial` → lb, `metric`
    → kg). Storage is canonical kg; the `units.format_weight` helper handles
    rounding so imperial loads still read as whole numbers.

    Returns None when the row is too sparse to render meaningfully
    (no weight + no duration); the caller falls through to first-exposure.
    """
    from units import format_weight  # local import — module load order

    sets = rx.get("sets")
    reps = rx.get("reps")
    weight = rx.get("weight_kg")
    duration = rx.get("duration_sec")

    if weight is not None and weight > 0:
        try:
            weight_str = format_weight(float(weight), unit_pref)
        except (TypeError, ValueError):
            return None
        if not weight_str:
            return None
        if sets and reps:
            return f"{sets} × {reps} @ {weight_str}"
        if reps:
            return f"{reps} reps @ {weight_str}"
        return weight_str
    if duration is not None and duration > 0:
        # Duration-target exercise (e.g. plank). Render as time per set.
        try:
            dur_str = f"{int(round(float(duration)))}s"
        except (TypeError, ValueError):
            return None
        if sets:
            return f"{sets} × {dur_str}"
        return dur_str
    return None


# ─── Public API ────────────────────────────────────────────────────────────


def apply_current_rx(
    payload: Layer4Payload,
    db: Any,
    user_id: int,
    layer2c_payloads: dict[str, Layer2CPayload],
) -> tuple[Layer4Payload, RxWireDiagnostic]:
    """Per spec §7. Returns (mutated_payload, diagnostic).

    For each strength exercise across all sessions:
      - Look up `current_rx(db, user_id, exercise_name)`.
      - If hit + renderable: overwrite `load_prescription` with the precise
        baseline (`"3 × 8 @ 185 lbs"`).
      - Else first-exposure: classify category from name + cluster_index,
        write the calibration template, append `first_exposure` to
        `coaching_flags`.

    Cardio + rest sessions are untouched (no strength exercises). The
    `_apply_rx_wire` orchestrator wrapper catches exceptions and returns the
    original payload (degraded pass-through) so an rx-wire defect can never
    wedge plan generation.
    """
    # Import lazily to avoid circular-import risk at module load.
    from rx_engine import current_rx
    from athlete import get_athlete_profile
    from units import normalize_unit_preference

    # #469 — read the athlete's unit_preference once; pass it to every
    # `_render_current_rx` call so the prescribed-load text matches the
    # athlete-facing display unit ("185 lb" vs "84 kg"). Falls back to the
    # `units` default on missing profile rows or DB hiccups — rx_wire is
    # degradable; a DB error here must not wedge plan generation.
    try:
        profile = get_athlete_profile(db, user_id) or {}
    except Exception:  # noqa: BLE001 — degraded path
        profile = {}
    unit_pref = normalize_unit_preference(profile.get("unit_preference"))

    resolved_index = _build_cluster_resolved_index(layer2c_payloads)

    outcomes: list[ExerciseRxOutcome] = []
    hits = 0
    first_exposure = 0
    skipped = 0

    new_sessions: list[PlanSession] = []
    for session in payload.sessions:
        if session.kind != "strength" or not session.strength_exercises:
            new_sessions.append(session)
            continue

        new_exercises: list[StrengthExercise] = []
        session_flags_to_add: list[str] = []

        for ex in session.strength_exercises:
            rx = None
            try:
                rx = current_rx(db, user_id, ex.exercise_name)
            except Exception as exc:  # noqa: BLE001 — degraded path
                _log.warning(
                    "rx_wire: session=%s exercise_id=%s current_rx lookup failed: %s",
                    session.session_id, ex.exercise_id, exc,
                )
                skipped += 1
                outcomes.append(ExerciseRxOutcome(
                    session_id=session.session_id,
                    exercise_id=ex.exercise_id,
                    path="skipped",
                ))
                new_exercises.append(ex)
                continue

            rendered = _render_current_rx(rx, unit_pref=unit_pref) if rx else None
            if rendered:
                new_ex = ex.model_copy(update={"load_prescription": rendered})
                new_exercises.append(new_ex)
                hits += 1
                outcomes.append(ExerciseRxOutcome(
                    session_id=session.session_id,
                    exercise_id=ex.exercise_id,
                    path="current_rx",
                    rendered=rendered,
                ))
                continue

            resolved = resolved_index.get(ex.exercise_id)
            category = _classify_category(ex, resolved)
            template = _FIRST_EXPOSURE_TEMPLATES[category]
            new_flags = list(ex.coaching_flags)
            if _FIRST_EXPOSURE_FLAG not in new_flags:
                new_flags.append(_FIRST_EXPOSURE_FLAG)
            new_ex = ex.model_copy(update={
                "load_prescription": template,
                "coaching_flags": new_flags,
            })
            new_exercises.append(new_ex)
            first_exposure += 1
            outcomes.append(ExerciseRxOutcome(
                session_id=session.session_id,
                exercise_id=ex.exercise_id,
                path="first_exposure",
                category=category,
                rendered=template,
            ))
            if _FIRST_EXPOSURE_FLAG not in session_flags_to_add:
                session_flags_to_add.append(_FIRST_EXPOSURE_FLAG)

        # The session itself stays — only its strength_exercises list changes.
        new_session = session.model_copy(update={
            "strength_exercises": new_exercises,
        })
        new_sessions.append(new_session)

    diag = RxWireDiagnostic(
        outcomes=outcomes,
        current_rx_hits=hits,
        first_exposure_count=first_exposure,
        skipped_count=skipped,
    )
    _log.info(
        "rx_wire: hits=%d first_exposure=%d skipped=%d (exercise_count=%d)",
        hits, first_exposure, skipped, len(outcomes),
    )
    # No-op short-circuit: if no exercises were touched (no current_rx hit + no
    # first-exposure write), the payload is semantically identical to the input
    # — return the original object to preserve `is` identity for callers that
    # round-trip a sentinel through the orchestrator wire (matches the empty-
    # input no-op contract). The skipped-only case is also a no-op (the
    # original prescription survives the try/except).
    if not outcomes or (hits == 0 and first_exposure == 0):
        return payload, diag
    return payload.model_copy(update={"sessions": new_sessions}), diag
