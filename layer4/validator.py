"""Layer 4 deterministic validator harness per `Layer4_Spec.md` §5.4.

Pure-function rule set; no LLM, no I/O, no state. Runs after every synthesis
call in both Pattern A and Pattern B; runs once more as a final pass over the
cumulative plan in Pattern A step 5.

Implements 21 rules per the §5.4 table (post-PR-C ±20/±10 volume bands +
28-day ACWR chronic window + rule-6 split into 6a/6b/6c + new
`indoor_only_violation_*` + post-PR-C-followon `injury_violation_*`
rewrite + new `injury_accommodation_violation_*`).

Mode-gating policy (settled in PR-C): each rule checks `payload.mode` at
entry and returns `[]` when not applicable. The driver iterates all rules.

Missing-input policy (settled in PR-C): soft (return empty + caller may
later attach `Observation(category='data_gap')` at the payload level) when
input is missing-but-tolerable. Rules NEVER raise.

D-66 / D-67 / D-68 forward-compatibility: 4 rules carry D-67-aware branches
that no-op against the always-empty `per_date_restrictions` list in v1.
When D-67 implementation ships, the branches activate without further
validator-code changes. D-70 (ROM modality) + D-71 (phase-sequencing) are
formally deferred per `Layer2D_Spec.md` §5.3.6.6.

**Accommodation-modality baseline caveat (v1).** The
`injury_accommodation_violation_*` rule formulas (per §5.3.6 + §5.4 line
925-933) compare prescribed prescription against a "baseline" (typical
un-accommodated volume/intensity). The LLM's effective baseline is
inherently fuzzy and the v1 validator uses conservative hardcoded
sentinels — 4 sets × 10 reps strength volume, 60 min cardio volume, 80%
1RM intensity, RPE 8 intensity — chosen to catch egregiously
non-compliant prescriptions while tolerating LLM baseline drift. Severity
is `warning` (not `blocker`) per spec; v2 may promote to blocker once
measured retry rates inform calibration. `loading_type_change` enforcement
is silently skipped because `ResolvedExercise` lacks implement/laterality
metadata in v1 (D-70-adjacent v2 work).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from layer4.context import (
    DailyAvailabilityWindow,
    ExerciseSubstitutionModality,
    FrequencyReductionModality,
    IntensityReductionModality,
    Layer2APayload,
    Layer2BPayload,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3APayload,
    Layer3BPayload,
    LoadingTypeChangeModality,
    PerDateRestriction,
    RaceEventPayload,
    TempoModificationModality,
    VolumeReductionModality,
)
from layer4.payload import (
    HRTarget,
    Layer4Payload,
    PaceTarget,
    PlanSession,
    PowerTarget,
    RPETarget,
    RuleFailure,
    StrengthExercise,
    SwimPaceTarget,
    ValidatorResult,
)


# ─── ValidatorContext ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidatorContext:
    """Bundles the upstream-layer payloads + onboarding/restriction data the
    §5.4 rules read against.

    Every field is optional. Different entry-point modes populate different
    subsets (e.g., T1 refresh = 3A + 2A + 2D + 1 per `Layer4_RefreshT1_v1.md`
    §6). Rules whose required upstream payload is None no-op silently per the
    PR-C missing-input policy.

    `layer2c_payloads` is a dict keyed by `locale_id` — one entry per locale
    in the athlete's saved locale cluster. The keys form the implicit
    "cluster" set for rule 6c (`session_locale_not_in_cluster_*`).

    `per_date_restrictions` is always empty in v1 (D-67 deferred); D-67-aware
    rule branches (6c locale_lock; 12 discipline_exclusions; 20
    max_total_minutes; 21 indoor_only) no-op against empty input.

    `prior_session_loads_by_date` provides trailing-window historical data
    for ACWR (rule 2). When None, ACWR rule emits no failures.
    """

    layer2a_payload: Layer2APayload | None = None
    layer2b_payload: Layer2BPayload | None = None
    layer2c_payloads: dict[str, Layer2CPayload] = field(default_factory=dict)
    layer2d_payload: Layer2DPayload | None = None
    layer2e_payload: Layer2EPayload | None = None
    layer3a_payload: Layer3APayload | None = None
    layer3b_payload: Layer3BPayload | None = None
    daily_availability_windows: tuple[DailyAvailabilityWindow, ...] = ()
    race_event: RaceEventPayload | None = None
    per_date_restrictions: tuple[PerDateRestriction, ...] = ()
    prior_session_loads_by_date: dict[date, float] | None = None


# ─── Constants + classifiers ────────────────────────────────────────────────


# Per-spec indoor locale categories (rule 21 — `indoor_only_violation_*`).
_INDOOR_LOCALE_CATEGORIES = frozenset(
    {
        "home_gym",
        "hotel_gym",
        "commercial_chain_gym",
        "independent_gym",
        "climbing_gym_chain",
        "climbing_gym_indie",
        "pool_indoor",
        "other_residence",
    }
)

# Per-spec outdoor-only disciplines (rule 21 — names align with v1
# discipline framework). Anything not on this list is treated as indoor-
# capable for the rule's purposes.
_OUTDOOR_ONLY_DISCIPLINES = frozenset(
    {
        "mtb_outdoor",
        "trail_running",
        "outdoor_rock_climbing",
        "packrafting",
        "abseiling",
        "outdoor_road_cycling",
        "outdoor_gravel_cycling",
        "skimo",
        "ski_tour",
        "marathon_canoe",
        "open_water_swim",
        "kayak_outdoor",
        "sup_outdoor",
    }
)

# Contingency anchor categories per race_format (rule 18 — D6 mixed
# contingency anchor table from `Layer4_RaceWeekBrief_v1.md`).
# FormRefresh A1 (2026-05-25) — keyed on the structural race_format axis.
# `continuous_multi_day` collapses the old `expedition_ar` + `multi_day_ultra`
# values. The merge keeps the anchors STRUCTURALLY implied by going
# continuously for >24h (cumulative_fatigue + sleep_dep) on top of the
# universal gi/hydration/mechanical set.
#
# `weather` is a UNIVERSAL anchor (2026-05-25): every race happens outdoors at
# a known location on a known date, so a weather contingency is always
# required. The synthesizer anchors it to the climate normals surfaced in the
# brief prompt (`weather_client`). The old `expedition_ar`-only `nav` anchor
# was removed entirely — the `navigation_required` concept it keyed on was
# retired end-to-end.
_CONTINGENCY_ANCHORS_PER_FORMAT: dict[str, tuple[str, ...]] = {
    "single_day": ("gi", "hydration", "mechanical", "weather"),
    "continuous_multi_day": (
        "gi",
        "hydration",
        "mechanical",
        "weather",
        "cumulative_fatigue",
        "sleep_dep",
    ),
    "stage_race": (
        "gi",
        "hydration",
        "mechanical",
        "weather",
        "between_stage_recovery",
    ),
}

# Conservative v1 baselines for `injury_accommodation_violation_*` (rule 10).
# The LLM's effective baseline is fuzzy; these sentinels catch egregious
# violations while tolerating drift. Severity is `warning` not `blocker`.
_BASELINE_STRENGTH_VOLUME_REPS = 40  # 4 sets × 10 reps
_BASELINE_CARDIO_DURATION_MIN = 60  # 60 min
_BASELINE_PCT_1RM = 80.0  # typical heavy strength load
_BASELINE_RPE_MIDPOINT = 8.0  # typical hard cardio
_BASELINE_FREQUENCY_SESSIONS_PER_WEEK = 3  # used when factor-form

_PCT_1RM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*1rm", re.IGNORECASE)


def _pct_1rm_from_load(load_prescription: str) -> float | None:
    """Extract %1RM from a free-shape load_prescription string (e.g.,
    '70% 1RM', '5x5 @ 80% 1RM'). Returns None when no match."""
    m = _PCT_1RM_PATTERN.search(load_prescription)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:  # pragma: no cover — regex guarantees float-parseable
        return None


def _parse_tempo_tuple(tempo: str) -> tuple[int | None, int | None, int | None, int | None]:
    """Parse `StrengthExercise.tempo` like '3-1-1-0' into (E, IB, C, IT)
    components. Returns (None, None, None, None) when the string doesn't
    match the convention."""
    parts = tempo.strip().split("-")
    if len(parts) != 4:
        return (None, None, None, None)
    out: list[int | None] = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
        else:
            out.append(None)
    return (out[0], out[1], out[2], out[3])


def _iso_week(d: date) -> tuple[int, int]:
    """Return (iso_year, iso_week) for a date — used to bucket sessions."""
    iso = d.isocalendar()
    return (iso.year, iso.week)


def _hard_session(s: PlanSession) -> bool:
    """True for sessions counted toward two-hard-in-a-row recovery rules."""
    return s.intensity_summary == "hard"


def _session_volume_hours(s: PlanSession) -> float:
    """Approximate session volume in hours; rest sessions = 0."""
    if s.kind == "rest":
        return 0.0
    return s.duration_min / 60.0


def _intensity_target_rpe_midpoint(target: object) -> float | None:
    """Best-effort midpoint extraction for `intensity_reduction` checking.
    Returns RPE midpoint when target is an RPETarget; None otherwise. v1
    keeps it simple — HR/pace/power baseline comparison would need per-
    athlete max/threshold data from 3A which isn't reliably populated."""
    if isinstance(target, RPETarget):
        return (target.rpe_low + target.rpe_high) / 2.0
    return None


def _phase_band_for_discipline(
    layer2a: Layer2APayload, discipline_id: str, phase_name: str
) -> tuple[float, float] | None:
    """Look up (low, high) load band from 2A `phase_load` for a discipline
    in a phase. Returns None if discipline missing, phase_load missing, or
    bounds incomplete."""
    for d in layer2a.disciplines:
        if d.discipline_id != discipline_id:
            continue
        pl = d.phase_load
        if pl is None:
            return None
        if phase_name == "Base":
            low, high = pl.base_low, pl.base_high
        elif phase_name == "Build":
            low, high = pl.build_low, pl.build_high
        elif phase_name == "Peak":
            low, high = pl.peak_low, pl.peak_high
        elif phase_name == "Taper":
            low, high = pl.taper_low, pl.taper_high
        else:
            return None
        if low is None or high is None:
            return None
        return (low, high)
    return None


def _zone_bucket(zone: str) -> str:
    """Map CardioBlock.intensity_zone to the spec's intensity-distribution
    bucket keys (`Z1-Z2`, `Z3`, `Z4-Z5`). `mixed` collapses to Z3."""
    if zone in ("Z1", "Z2"):
        return "Z1-Z2"
    if zone in ("Z4", "Z5"):
        return "Z4-Z5"
    return "Z3"  # Z3 + mixed


# ─── Rule 1: volume_band ────────────────────────────────────────────────────


def _rule_volume_band(payload: Layer4Payload, ctx: ValidatorContext) -> list[RuleFailure]:
    if payload.mode == "single_session_synthesize":
        return []
    if ctx.layer2a_payload is None:
        return []
    out: list[RuleFailure] = []
    by_week_disc: dict[
        tuple[tuple[int, int], str, str], list[PlanSession]
    ] = {}
    for s in payload.sessions:
        if s.kind == "rest":
            continue
        if s.discipline_id is None or s.phase_metadata is None:
            continue
        wk = _iso_week(s.date)
        key = (wk, s.discipline_id, s.phase_metadata.phase_name)
        by_week_disc.setdefault(key, []).append(s)
    for (wk, disc, phase), sessions in by_week_disc.items():
        band = _phase_band_for_discipline(ctx.layer2a_payload, disc, phase)
        if band is None:
            continue
        low, high = band
        actual = sum(_session_volume_hours(s) for s in sessions)
        blocker_low, blocker_high = low * 0.8, high * 1.2
        warning_low, warning_high = low * 0.9, high * 1.1
        if actual < blocker_low or actual > blocker_high:
            severity = "blocker"
        elif actual < warning_low or actual > warning_high:
            severity = "warning"
        else:
            continue
        direction = "below" if actual < low else "above"
        out.append(
            RuleFailure(
                rule_name=f"volume_band_{direction}_week_{wk[1]}_{disc}_{phase.lower()}",
                phase_name=phase,
                severity=severity,
                detail=(
                    f"week {wk[1]} ({disc}, {phase}): actual {actual:.1f}h vs "
                    f"band ({low:.1f}-{high:.1f}h)"
                ),
                affected_session_ids=[s.session_id for s in sessions],
            )
        )
    return out


# ─── Rule 2: acwr ───────────────────────────────────────────────────────────


def _rule_acwr(payload: Layer4Payload, ctx: ValidatorContext) -> list[RuleFailure]:
    if payload.mode == "single_session_synthesize":
        return []
    if ctx.prior_session_loads_by_date is None:
        return []
    if not payload.sessions:
        return []
    payload_by_date: dict[date, float] = {}
    for s in payload.sessions:
        payload_by_date[s.date] = payload_by_date.get(s.date, 0.0) + _session_volume_hours(s)
    out: list[RuleFailure] = []
    anchor = max(payload_by_date.keys())  # latest date in scope
    acute_start = anchor - timedelta(days=6)
    chronic_start = anchor - timedelta(days=27)

    def _sum_window(start: date, end: date) -> float:
        total = 0.0
        d = start
        while d <= end:
            total += payload_by_date.get(d, 0.0)
            total += ctx.prior_session_loads_by_date.get(d, 0.0)  # type: ignore[union-attr]
            d += timedelta(days=1)
        return total

    acute = _sum_window(acute_start, anchor)
    chronic_total = _sum_window(chronic_start, anchor)
    if chronic_total <= 0:
        return []
    chronic_avg_per_week = chronic_total / 4.0
    if chronic_avg_per_week <= 0:
        return []
    ratio = acute / chronic_avg_per_week
    if ratio < 0.7 or ratio > 1.4:
        severity = "blocker"
    elif ratio < 0.8 or ratio > 1.3:
        severity = "warning"
    else:
        return out
    direction = "below" if ratio < 1.0 else "above"
    out.append(
        RuleFailure(
            rule_name=f"acwr_forward_projection_{direction}_{ratio:.2f}".replace(".", "_"),
            phase_name=None,
            severity=severity,
            detail=f"ACWR ratio {ratio:.2f} (acute {acute:.1f}h / chronic-avg {chronic_avg_per_week:.1f}h/wk)",
            affected_session_ids=[s.session_id for s in payload.sessions],
        )
    )
    return out


# ─── Rule 3: rest_spacing ───────────────────────────────────────────────────


_REST_SPACING_EXEMPT_FLAGS = frozenset({"overreach_test", "race_rehearsal"})


def _rule_rest_spacing(payload: Layer4Payload, ctx: ValidatorContext) -> list[RuleFailure]:
    out: list[RuleFailure] = []
    by_disc: dict[str, list[PlanSession]] = {}
    for s in payload.sessions:
        if s.discipline_id is None or not _hard_session(s):
            continue
        by_disc.setdefault(s.discipline_id, []).append(s)
    for disc, sessions in by_disc.items():
        sessions_sorted = sorted(sessions, key=lambda x: x.date)
        for i in range(1, len(sessions_sorted)):
            prev, cur = sessions_sorted[i - 1], sessions_sorted[i]
            if (cur.date - prev.date).days != 1:
                continue
            if _REST_SPACING_EXEMPT_FLAGS & set(cur.coaching_flags):
                continue
            if _REST_SPACING_EXEMPT_FLAGS & set(prev.coaching_flags):
                continue
            out.append(
                RuleFailure(
                    rule_name=f"rest_spacing_consecutive_hard_{disc}_{cur.date.isoformat()}",
                    phase_name=cur.phase_metadata.phase_name if cur.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"two consecutive hard sessions in {disc} on {prev.date} + {cur.date} "
                        "without overreach_test/race_rehearsal rationale flag"
                    ),
                    affected_session_ids=[prev.session_id, cur.session_id],
                )
            )
    return out


# ─── Rule 4: intensity_dist ─────────────────────────────────────────────────


def _rule_intensity_dist(payload: Layer4Payload, ctx: ValidatorContext) -> list[RuleFailure]:
    if payload.mode == "single_session_synthesize":
        return []
    out: list[RuleFailure] = []
    by_phase: dict[str, dict[str, float]] = {}
    by_phase_dist: dict[str, dict[str, float]] = {}
    by_phase_sessions: dict[str, list[str]] = {}
    for s in payload.sessions:
        if s.phase_metadata is None or s.kind != "cardio" or not s.cardio_blocks:
            continue
        phase = s.phase_metadata.phase_name
        by_phase_dist[phase] = s.phase_metadata.intended_intensity_distribution
        by_phase_sessions.setdefault(phase, []).append(s.session_id)
        bucket_hours = by_phase.setdefault(phase, {})
        for b in s.cardio_blocks:
            bucket = _zone_bucket(b.intensity_zone)
            bucket_hours[bucket] = bucket_hours.get(bucket, 0.0) + b.duration_min / 60.0
    for phase, buckets in by_phase.items():
        total = sum(buckets.values())
        # Distribution comparison is statistically meaningless for thin data.
        # The rule needs at least ~3 hours of phase cardio to be informative.
        if total < 3.0:
            continue
        intended = by_phase_dist.get(phase, {})
        for bucket_key, expected_fraction in intended.items():
            actual_fraction = buckets.get(bucket_key, 0.0) / total
            delta_pp = abs(actual_fraction - expected_fraction) * 100.0
            if delta_pp > 10.0:
                out.append(
                    RuleFailure(
                        rule_name=f"intensity_dist_drift_{phase.lower()}_{bucket_key.lower().replace('-', '_')}",
                        phase_name=phase,
                        severity="warning",
                        detail=(
                            f"{phase}/{bucket_key}: actual {actual_fraction:.2f} vs intended "
                            f"{expected_fraction:.2f} (Δ {delta_pp:.1f}pp; tolerance ±10pp)"
                        ),
                        affected_session_ids=by_phase_sessions[phase],
                    )
                )
    return out


# ─── Rule 5: two_per_day ────────────────────────────────────────────────────


def _rule_two_per_day(payload: Layer4Payload, ctx: ValidatorContext) -> list[RuleFailure]:
    """Defensive — pydantic Layer4Payload._check_two_per_day enforces these
    invariants at construction. The §5.4 rule re-runs them as a load-bearing
    independent check (covers `model_construct` bypass + downstream-injected
    sessions). Empty result is the expected case for any payload that passed
    pydantic validation."""
    out: list[RuleFailure] = []
    by_date: dict[date, list[PlanSession]] = {}
    for s in payload.sessions:
        by_date.setdefault(s.date, []).append(s)
    for d, sessions in by_date.items():
        if len(sessions) > 2:
            out.append(
                RuleFailure(
                    rule_name=f"two_per_day_max_exceeded_{d.isoformat()}",
                    phase_name=None,
                    severity="blocker",
                    detail=f"{d}: {len(sessions)} sessions (max 2)",
                    affected_session_ids=[s.session_id for s in sessions],
                )
            )
            continue
        if len(sessions) == 2:
            if all(s.kind == "strength" for s in sessions):
                out.append(
                    RuleFailure(
                        rule_name=f"two_per_day_double_strength_{d.isoformat()}",
                        phase_name=None,
                        severity="blocker",
                        detail=f"{d}: strength+strength forbidden on same day",
                        affected_session_ids=[s.session_id for s in sessions],
                    )
                )
            if all(s.intensity_summary == "hard" for s in sessions):
                out.append(
                    RuleFailure(
                        rule_name=f"two_per_day_double_hard_{d.isoformat()}",
                        phase_name=None,
                        severity="blocker",
                        detail=f"{d}: two hard sessions same day forbidden",
                        affected_session_ids=[s.session_id for s in sessions],
                    )
                )
            if not any(s.kind == "cardio" for s in sessions):
                out.append(
                    RuleFailure(
                        rule_name=f"two_per_day_no_cardio_{d.isoformat()}",
                        phase_name=None,
                        severity="blocker",
                        detail=f"{d}: at least one of two sessions must be cardio",
                        affected_session_ids=[s.session_id for s in sessions],
                    )
                )
    return out


# ─── Rule 6a: equipment_unavailable ────────────────────────────────────────


def _rule_equipment_unavailable(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    out: list[RuleFailure] = []
    if not ctx.layer2c_payloads:
        return out
    for s in payload.sessions:
        if s.kind != "strength" or s.locale_id is None or s.strength_exercises is None:
            continue
        l2c = ctx.layer2c_payloads.get(s.locale_id)
        if l2c is None:
            continue  # rule 6c surfaces the unknown-locale case
        resolved_ids = {rx.exercise_id for rx in l2c.exercises_resolved}
        pool_ids = set(l2c.effective_pool)
        for ex in s.strength_exercises:
            if ex.exercise_id in resolved_ids or ex.exercise_id in pool_ids:
                continue
            out.append(
                RuleFailure(
                    rule_name=f"equipment_unavailable_{ex.exercise_id}_at_{s.locale_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"exercise {ex.exercise_id} not in effective_pool at locale {s.locale_id}"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 6b: session_multi_locale ─────────────────────────────────────────


def _rule_session_multi_locale(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    """A session has a single `locale_id` field, so the literal "all exercises
    resolve at the same locale" assertion is enforced by construction. The
    §5.4 rule defensively detects cases where the session's chosen locale
    contains NO exercises in its effective pool (a degenerate "multi-locale"
    edge — the synthesizer would have to split the session)."""
    out: list[RuleFailure] = []
    if not ctx.layer2c_payloads:
        return out
    for s in payload.sessions:
        if s.kind != "strength" or s.locale_id is None or s.strength_exercises is None:
            continue
        if not s.strength_exercises:
            continue
        l2c = ctx.layer2c_payloads.get(s.locale_id)
        if l2c is None:
            continue
        resolved_ids = {rx.exercise_id for rx in l2c.exercises_resolved}
        pool_ids = set(l2c.effective_pool)
        prescribed = {ex.exercise_id for ex in s.strength_exercises}
        if not (prescribed & (resolved_ids | pool_ids)):
            out.append(
                RuleFailure(
                    rule_name=f"session_multi_locale_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"session {s.session_id}: none of {len(prescribed)} prescribed exercises "
                        f"resolve at locale {s.locale_id}; would require multi-locale execution"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 6c: session_locale_not_in_cluster ────────────────────────────────


def _rule_session_locale_not_in_cluster(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    out: list[RuleFailure] = []
    cluster = set(ctx.layer2c_payloads.keys())
    locks_by_date: dict[date, str] = {
        r.date.date(): r.locale_lock for r in ctx.per_date_restrictions if r.locale_lock
    }
    for s in payload.sessions:
        if s.locale_id is None:
            continue
        if cluster and s.locale_id not in cluster:
            out.append(
                RuleFailure(
                    rule_name=f"session_locale_not_in_cluster_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"session locale {s.locale_id} not in athlete's saved cluster "
                        f"({sorted(cluster)})"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
            continue
        # D-67-aware branch: when a date has locale_lock set, locale_id must match.
        lock = locks_by_date.get(s.date)
        if lock is not None and s.locale_id != lock:
            out.append(
                RuleFailure(
                    rule_name=f"session_locale_lock_violation_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"session locale {s.locale_id} on {s.date} violates D-67 locale_lock={lock}"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 9: injury_violation ──────────────────────────────────────────────


def _rule_injury_violation(payload: Layer4Payload, ctx: ValidatorContext) -> list[RuleFailure]:
    if ctx.layer2d_payload is None:
        return []
    excluded = {er.exercise_id for er in ctx.layer2d_payload.excluded_exercises}
    if not excluded:
        return []
    out: list[RuleFailure] = []
    for s in payload.sessions:
        if s.kind != "strength" or s.strength_exercises is None:
            continue
        for ex in s.strength_exercises:
            if ex.exercise_id not in excluded:
                continue
            out.append(
                RuleFailure(
                    rule_name=f"injury_violation_{ex.exercise_id}_in_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"prescribed exercise {ex.exercise_id} ('{ex.exercise_name}') is in "
                        "Layer2D excluded_exercises (injury contraindication)"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 10: injury_accommodation_violation ───────────────────────────────


def _rule_injury_accommodation_violation(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if ctx.layer2d_payload is None:
        return []
    accommodated_by_id = {
        er.exercise_id: er for er in ctx.layer2d_payload.accommodated_exercises
    }
    if not accommodated_by_id:
        return []
    out: list[RuleFailure] = []
    # Count weekly sessions by discipline up-front for frequency_reduction.
    weekly_count_by_disc: dict[tuple[tuple[int, int], str | None], int] = {}
    for s in payload.sessions:
        if s.kind == "rest":
            continue
        key = (_iso_week(s.date), s.discipline_id)
        weekly_count_by_disc[key] = weekly_count_by_disc.get(key, 0) + 1
    weekly_total_per_week: dict[tuple[int, int], int] = {}
    for (wk, _), n in weekly_count_by_disc.items():
        weekly_total_per_week[wk] = weekly_total_per_week.get(wk, 0) + n
    for s in payload.sessions:
        if s.kind != "strength" or s.strength_exercises is None:
            continue
        for ex in s.strength_exercises:
            risk = accommodated_by_id.get(ex.exercise_id)
            if risk is None:
                continue
            for modality in risk.accommodations:
                out.extend(_check_modality(ex, s, modality, weekly_count_by_disc, weekly_total_per_week))
    return out


def _check_modality(
    ex: StrengthExercise,
    s: PlanSession,
    modality: object,
    weekly_count_by_disc: dict[tuple[tuple[int, int], str | None], int],
    weekly_total_per_week: dict[tuple[int, int], int],
) -> list[RuleFailure]:
    """Per-modality compliance check. Each variant has v1 baseline sentinels
    documented at the module level; severity is `warning` per spec line 933."""
    out: list[RuleFailure] = []

    def _emit(rule_suffix: str, detail: str) -> None:
        out.append(
            RuleFailure(
                rule_name=f"injury_accommodation_violation_{rule_suffix}_{ex.exercise_id}_in_{s.session_id}",
                phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                severity="warning",
                detail=detail,
                affected_session_ids=[s.session_id],
            )
        )

    if isinstance(modality, VolumeReductionModality):
        try:
            reps_per_set = int(ex.reps_per_set) if isinstance(ex.reps_per_set, int) else 0
        except (TypeError, ValueError):
            reps_per_set = 0
        prescribed_reps = ex.sets * reps_per_set
        if reps_per_set == 0:
            return out  # AMRAP / range — can't compute baseline cleanly
        threshold = _BASELINE_STRENGTH_VOLUME_REPS * modality.factor * 1.10
        if prescribed_reps > threshold:
            _emit(
                "volume",
                f"prescribed volume {prescribed_reps} reps > {threshold:.0f} threshold "
                f"(baseline {_BASELINE_STRENGTH_VOLUME_REPS} × factor {modality.factor} × 1.10)",
            )
        return out

    if isinstance(modality, IntensityReductionModality):
        pct = _pct_1rm_from_load(ex.load_prescription)
        if pct is not None:
            threshold = _BASELINE_PCT_1RM * modality.factor * 1.10
            if pct > threshold:
                _emit(
                    "intensity",
                    f"prescribed intensity {pct:.0f}%1RM > {threshold:.0f}%1RM threshold "
                    f"(baseline {_BASELINE_PCT_1RM:.0f}% × factor {modality.factor} × 1.10)",
                )
        return out

    if isinstance(modality, TempoModificationModality):
        if modality.tempo_pattern == "isometric_only":
            tempo = (ex.tempo or "").lower()
            if "iso" not in tempo and "isometric" not in tempo:
                _emit(
                    "tempo",
                    f"tempo_pattern==isometric_only requires StrengthExercise.tempo to encode "
                    f"isometric notation; got '{ex.tempo or ''}'",
                )
            return out
        if not ex.tempo:
            _emit(
                "tempo",
                f"tempo_pattern=={modality.tempo_pattern} requires StrengthExercise.tempo non-None "
                "(missing tempo notation)",
            )
            return out
        prescribed = _parse_tempo_tuple(ex.tempo)
        expected = (
            modality.eccentric_s,
            modality.isometric_bottom_s,
            modality.concentric_s,
            modality.isometric_top_s,
        )
        for i, (p, e) in enumerate(zip(prescribed, expected)):
            if e is None or p is None:
                continue
            if abs(p - e) > 1:
                _emit(
                    "tempo",
                    f"tempo component {i} mismatch: prescribed {p}s vs expected {e}s "
                    "(±1s tolerance)",
                )
                return out
        return out

    if isinstance(modality, LoadingTypeChangeModality):
        # Skipped silently in v1 — ResolvedExercise lacks implement/laterality
        # metadata needed to enforce. v2 lands with the metadata extension.
        return out

    if isinstance(modality, FrequencyReductionModality):
        wk = _iso_week(s.date)
        if modality.discipline_id is None:
            actual = weekly_total_per_week.get(wk, 0)
            scope = "all_disciplines"
        else:
            actual = weekly_count_by_disc.get((wk, modality.discipline_id), 0)
            scope = modality.discipline_id
        if modality.sessions_per_week_cap is not None:
            if actual > modality.sessions_per_week_cap:
                _emit(
                    "frequency",
                    f"week {wk[1]} ({scope}): {actual} sessions > cap {modality.sessions_per_week_cap}",
                )
        elif modality.factor is not None:
            threshold = _BASELINE_FREQUENCY_SESSIONS_PER_WEEK * modality.factor * 1.10
            if actual > threshold:
                _emit(
                    "frequency",
                    f"week {wk[1]} ({scope}): {actual} sessions > {threshold:.1f} "
                    f"(baseline {_BASELINE_FREQUENCY_SESSIONS_PER_WEEK} × factor {modality.factor} × 1.10)",
                )
        return out

    if isinstance(modality, ExerciseSubstitutionModality):
        # Covered by injury_violation_* (exercise_id NOT IN excluded_exercises).
        return out

    return out


# ─── Rule 11: schedule_violation ───────────────────────────────────────────


_DAY_OF_WEEK_LOOKUP = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun",
}


def _rule_schedule_violation(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if not ctx.daily_availability_windows:
        return []
    enabled_by_dow = {w.day_of_week: w.enabled for w in ctx.daily_availability_windows}
    out: list[RuleFailure] = []
    for s in payload.sessions:
        if s.kind == "rest":
            continue
        dow = _DAY_OF_WEEK_LOOKUP.get(s.date.weekday())
        if dow is None:
            continue
        if not enabled_by_dow.get(dow, True):
            if "athlete_self_scheduled" in s.coaching_flags:
                continue
            out.append(
                RuleFailure(
                    rule_name=f"schedule_violation_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"session on {s.date} ({dow}) but day is enabled=False in §G availability"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 12: discipline_excluded ──────────────────────────────────────────


def _rule_discipline_excluded(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    out: list[RuleFailure] = []
    included: set[str] | None = None
    if ctx.layer2a_payload is not None:
        included = {
            d.discipline_id
            for d in ctx.layer2a_payload.disciplines
            if d.inclusion == "included"
        }
    excl_by_date: dict[date, set[str]] = {}
    for r in ctx.per_date_restrictions:
        d = r.date.date() if hasattr(r.date, "date") else r.date
        excl_by_date.setdefault(d, set()).update(r.discipline_exclusions)
    for s in payload.sessions:
        if s.discipline_id is None or s.kind == "rest":
            continue
        if included is not None and s.discipline_id not in included:
            out.append(
                RuleFailure(
                    rule_name=f"discipline_excluded_{s.discipline_id}_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"discipline {s.discipline_id} not in 2A discipline_inclusion=='included' set"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
            continue
        date_excl = excl_by_date.get(s.date, set())
        if s.discipline_id in date_excl:
            out.append(
                RuleFailure(
                    rule_name=f"discipline_excluded_per_date_{s.discipline_id}_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"discipline {s.discipline_id} excluded on {s.date} via D-67 "
                        f"discipline_exclusions"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 13: sport_locale_incompatible ────────────────────────────────────


def _rule_sport_locale_incompatible(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if not ctx.layer2c_payloads:
        return []
    out: list[RuleFailure] = []
    for s in payload.sessions:
        if s.discipline_id is None or s.locale_id is None or s.kind == "rest":
            continue
        l2c = ctx.layer2c_payloads.get(s.locale_id)
        if l2c is None:
            continue
        supported = False
        for cov in l2c.discipline_coverage:
            if cov.discipline_id != s.discipline_id:
                continue
            if cov.total_exercises > 0 and cov.coverage_pct > 0.0:
                supported = True
            break
        if not supported:
            out.append(
                RuleFailure(
                    rule_name=f"sport_locale_incompatible_{s.discipline_id}_{s.locale_id}_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"discipline {s.discipline_id} not supported at locale {s.locale_id} "
                        "(2C discipline_coverage has 0 exercises or 0 coverage)"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 14: taper_phase_intent_violation ─────────────────────────────────


def _rule_taper_phase_intent_violation(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if payload.mode != "race_week_brief":
        return []
    if payload.race_week_brief is None:
        return []
    event_date = payload.race_week_brief.event_date
    out: list[RuleFailure] = []
    for s in payload.sessions:
        days_to_event = (event_date - s.date).days
        if days_to_event < 0:
            continue
        if days_to_event <= 2 and s.intensity_summary == "hard":
            out.append(
                RuleFailure(
                    rule_name=f"taper_phase_intent_violation_hard_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"session on {s.date} ({days_to_event}d to event) is intensity_summary=='hard'; "
                        "Taper §8.5 intent forbids hard sessions within 2d of event"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
        # "Long-duration session within 48h" — interpret long-duration as
        # duration_min > 90 (~1.5h+).
        if days_to_event <= 2 and s.duration_min > 90:
            out.append(
                RuleFailure(
                    rule_name=f"taper_phase_intent_violation_long_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"session on {s.date} ({days_to_event}d to event) is "
                        f"duration_min={s.duration_min} (>90); Taper §8.5 forbids long sessions "
                        "within 48h of event"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 15: kit_manifest_inputs_incomplete ───────────────────────────────


def _rule_kit_manifest_inputs_incomplete(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    # D-66 active branch (Layer4_Spec.md §5.4 + Race_Events_D66_Design_v1.md §5.4):
    # skip when ctx.race_event is None OR race_format == 'single_day';
    # emit `kit_manifest_inputs_incomplete_no_route_locales` when route_locales
    # empty; emit `kit_manifest_inputs_incomplete_no_route_locale_equipment` when
    # route_locales populated but all `equipment` lists empty; pass when at least
    # one route_locale has equipment populated.
    if payload.mode != "race_week_brief":
        return []
    if ctx.race_event is None:
        return []
    if ctx.race_event.race_format == "single_day":
        return []
    if not ctx.race_event.route_locales:
        return [
            RuleFailure(
                rule_name="kit_manifest_inputs_incomplete_no_route_locales",
                phase_name=None,
                severity="warning",
                detail=(
                    f"race_format=={ctx.race_event.race_format}: route_locales empty; "
                    "kit_manifest synthesis degraded to free-text gear list only"
                ),
                affected_session_ids=[],
            )
        ]
    if all(not rl.equipment for rl in ctx.race_event.route_locales):
        return [
            RuleFailure(
                rule_name="kit_manifest_inputs_incomplete_no_route_locale_equipment",
                phase_name=None,
                severity="warning",
                detail=(
                    f"race_format=={ctx.race_event.race_format}: "
                    f"{len(ctx.race_event.route_locales)} route_locales populated but "
                    "no per-locale equipment items; kit_manifest synthesis degraded"
                ),
                affected_session_ids=[],
            )
        ]
    return []


# ─── Rule 16: race_plan_segments_unordered ─────────────────────────────────


def _rule_race_plan_segments_unordered(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if payload.mode != "race_week_brief" or payload.race_plan is None:
        return []
    # segment_index monotonicity is enforced at pydantic construction;
    # check estimated_start_offset_hr monotonicity defensively.
    out: list[RuleFailure] = []
    segs = payload.race_plan.segments
    for i in range(1, len(segs)):
        if segs[i].estimated_start_offset_hr < segs[i - 1].estimated_start_offset_hr:
            out.append(
                RuleFailure(
                    rule_name=f"race_plan_segments_unordered_{segs[i].segment_id}",
                    phase_name=None,
                    severity="blocker",
                    detail=(
                        f"segment {segs[i].segment_index} estimated_start_offset_hr "
                        f"{segs[i].estimated_start_offset_hr} < prior {segs[i - 1].estimated_start_offset_hr}"
                    ),
                    affected_session_ids=[],
                )
            )
    return out


# ─── Rule 17: fueling_strategy_2e_tier_mismatch ────────────────────────────


def _rule_fueling_strategy_2e_tier_mismatch(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if payload.mode != "race_week_brief" or payload.race_plan is None:
        return []
    if ctx.layer2e_payload is None:
        return []
    rdfs = ctx.layer2e_payload.race_day_fueling
    if not rdfs:
        return []
    # Match RaceDayFueling by event_name — race_event_payload's name lives
    # on ctx.race_event when populated; on this output-side rule the
    # canonical match is against payload.race_plan.race_name; use the first
    # entry as a defensive fallback when none match by name.
    rdf = next(
        (r for r in rdfs if r.event_name == payload.race_plan.race_name),
        rdfs[0],
    )
    fs = payload.race_plan.fueling_strategy
    out: list[RuleFailure] = []

    def _out_of_band(low: float, high: float, val: float) -> bool:
        return val < low or val > high

    if _out_of_band(rdf.cho_g_per_hr_low, rdf.cho_g_per_hr_high, fs.cho_g_per_hr_low):
        out.append(
            RuleFailure(
                rule_name="fueling_strategy_2e_tier_mismatch_cho_low",
                phase_name=None,
                severity="blocker",
                detail=(
                    f"cho_g_per_hr_low {fs.cho_g_per_hr_low} outside 2E tier band "
                    f"({rdf.cho_g_per_hr_low}-{rdf.cho_g_per_hr_high})"
                ),
                affected_session_ids=[],
            )
        )
    if _out_of_band(rdf.cho_g_per_hr_low, rdf.cho_g_per_hr_high, fs.cho_g_per_hr_high):
        out.append(
            RuleFailure(
                rule_name="fueling_strategy_2e_tier_mismatch_cho_high",
                phase_name=None,
                severity="blocker",
                detail=(
                    f"cho_g_per_hr_high {fs.cho_g_per_hr_high} outside 2E tier band "
                    f"({rdf.cho_g_per_hr_low}-{rdf.cho_g_per_hr_high})"
                ),
                affected_session_ids=[],
            )
        )
    if _out_of_band(rdf.na_mg_per_hr_low, rdf.na_mg_per_hr_high, fs.sodium_mg_per_hr):
        out.append(
            RuleFailure(
                rule_name="fueling_strategy_2e_tier_mismatch_sodium",
                phase_name=None,
                severity="blocker",
                detail=(
                    f"sodium_mg_per_hr {fs.sodium_mg_per_hr} outside 2E tier band "
                    f"({rdf.na_mg_per_hr_low}-{rdf.na_mg_per_hr_high})"
                ),
                affected_session_ids=[],
            )
        )
    if rdf.fluid_ml_per_hr_low is not None and rdf.fluid_ml_per_hr_high is not None:
        if _out_of_band(
            rdf.fluid_ml_per_hr_low, rdf.fluid_ml_per_hr_high, fs.fluid_ml_per_hr
        ):
            out.append(
                RuleFailure(
                    rule_name="fueling_strategy_2e_tier_mismatch_fluid",
                    phase_name=None,
                    severity="blocker",
                    detail=(
                        f"fluid_ml_per_hr {fs.fluid_ml_per_hr} outside 2E tier band "
                        f"({rdf.fluid_ml_per_hr_low}-{rdf.fluid_ml_per_hr_high})"
                    ),
                    affected_session_ids=[],
                )
            )
    return out


# ─── Rule 18: contingency_anchor_category_missing ──────────────────────────


def _rule_contingency_anchor_category_missing(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if payload.mode != "race_week_brief" or payload.race_week_brief is None:
        return []
    race_format = payload.race_week_brief.race_format
    required = _CONTINGENCY_ANCHORS_PER_FORMAT.get(race_format, ())
    if not required:
        return []
    # Collect contingency text from both RaceWeekBrief and (when present) RacePlan.
    haystack = " ".join(payload.race_week_brief.contingencies).lower()
    if payload.race_plan is not None:
        for c in payload.race_plan.contingencies:
            haystack += " " + c.trigger.lower() + " " + c.action_plan.lower()
    out: list[RuleFailure] = []
    for anchor in required:
        # Compare with underscores stripped — handles "sleep_dep" vs "sleep dep".
        anchor_loose = anchor.replace("_", " ")
        if anchor not in haystack and anchor_loose not in haystack:
            out.append(
                RuleFailure(
                    rule_name=f"contingency_anchor_category_missing_{anchor}",
                    phase_name=None,
                    severity="warning",
                    detail=(
                        f"race_format=={race_format}: anchor category '{anchor}' missing from "
                        "contingencies"
                    ),
                    affected_session_ids=[],
                )
            )
    return out


# ─── Rule 19: phase_date_out_of_range ──────────────────────────────────────


def _rule_phase_date_out_of_range(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if payload.mode == "single_session_synthesize":
        return []
    if payload.phase_structure is None:
        return []
    bounds_by_phase = {
        p.phase_name: (p.start_date, p.end_date) for p in payload.phase_structure.phases
    }
    out: list[RuleFailure] = []
    for s in payload.sessions:
        if s.phase_metadata is None:
            continue
        bounds = bounds_by_phase.get(s.phase_metadata.phase_name)
        if bounds is None:
            continue
        start, end = bounds
        if s.date < start or s.date > end:
            out.append(
                RuleFailure(
                    rule_name=f"phase_date_out_of_range_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name,
                    severity="blocker",
                    detail=(
                        f"session date {s.date} outside {s.phase_metadata.phase_name} bounds "
                        f"[{start}, {end}]"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule 20: daily_window_fit ─────────────────────────────────────────────


def _rule_daily_window_fit(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    if not ctx.daily_availability_windows:
        return []
    minutes_by_dow: dict[str, int] = {}
    for w in ctx.daily_availability_windows:
        if not w.enabled:
            continue
        total = (w.window_duration or 0) + (w.second_window_duration or 0)
        minutes_by_dow[w.day_of_week] = total
    max_total_by_date: dict[date, int | None] = {}
    for r in ctx.per_date_restrictions:
        d = r.date.date() if hasattr(r.date, "date") else r.date
        max_total_by_date[d] = r.max_total_minutes
    out: list[RuleFailure] = []
    duration_by_date: dict[date, int] = {}
    sessions_by_date: dict[date, list[str]] = {}
    for s in payload.sessions:
        duration_by_date[s.date] = duration_by_date.get(s.date, 0) + s.duration_min
        sessions_by_date.setdefault(s.date, []).append(s.session_id)
    for d, dur in duration_by_date.items():
        dow = _DAY_OF_WEEK_LOOKUP.get(d.weekday())
        cap = minutes_by_dow.get(dow) if dow else None
        if cap is not None and dur > cap:
            out.append(
                RuleFailure(
                    rule_name=f"daily_window_fit_window_{d.isoformat()}",
                    phase_name=None,
                    severity="blocker",
                    detail=(
                        f"{d}: total session duration {dur}min > available window {cap}min"
                    ),
                    affected_session_ids=sessions_by_date[d],
                )
            )
        d67_cap = max_total_by_date.get(d)
        if d67_cap is not None and dur > d67_cap:
            out.append(
                RuleFailure(
                    rule_name=f"daily_window_fit_d67_max_{d.isoformat()}",
                    phase_name=None,
                    severity="blocker",
                    detail=(
                        f"{d}: total session duration {dur}min > D-67 max_total_minutes {d67_cap}"
                    ),
                    affected_session_ids=sessions_by_date[d],
                )
            )
    return out


# ─── Rule 21: indoor_only_violation ────────────────────────────────────────


def _rule_indoor_only_violation(
    payload: Layer4Payload, ctx: ValidatorContext
) -> list[RuleFailure]:
    indoor_dates: set[date] = set()
    for r in ctx.per_date_restrictions:
        if not r.indoor_only:
            continue
        d = r.date.date() if hasattr(r.date, "date") else r.date
        indoor_dates.add(d)
    if not indoor_dates:
        return []
    locale_category_by_id: dict[str, str] = {}
    # Layer 2C payload doesn't carry locale category directly in v1 (the
    # category lives on locale_profiles per onboarding). Without a per-locale
    # category lookup we can't enforce the locale half of the rule; we
    # enforce the discipline half (outdoor-only discipline on an indoor-only
    # date) and skip the locale half pending the D-67 design wave.
    out: list[RuleFailure] = []
    for s in payload.sessions:
        if s.date not in indoor_dates or s.discipline_id is None or s.kind == "rest":
            continue
        if s.discipline_id in _OUTDOOR_ONLY_DISCIPLINES:
            out.append(
                RuleFailure(
                    rule_name=f"indoor_only_violation_{s.session_id}",
                    phase_name=s.phase_metadata.phase_name if s.phase_metadata else None,
                    severity="blocker",
                    detail=(
                        f"discipline {s.discipline_id} is outdoor-only but date {s.date} has "
                        "D-67 indoor_only=True"
                    ),
                    affected_session_ids=[s.session_id],
                )
            )
    return out


# ─── Rule registry + driver ────────────────────────────────────────────────


_ALL_RULES: tuple[Callable[[Layer4Payload, ValidatorContext], list[RuleFailure]], ...] = (
    _rule_volume_band,
    _rule_acwr,
    _rule_rest_spacing,
    _rule_intensity_dist,
    _rule_two_per_day,
    _rule_equipment_unavailable,
    _rule_session_multi_locale,
    _rule_session_locale_not_in_cluster,
    _rule_injury_violation,
    _rule_injury_accommodation_violation,
    _rule_schedule_violation,
    _rule_discipline_excluded,
    _rule_sport_locale_incompatible,
    _rule_taper_phase_intent_violation,
    _rule_kit_manifest_inputs_incomplete,
    _rule_race_plan_segments_unordered,
    _rule_fueling_strategy_2e_tier_mismatch,
    _rule_contingency_anchor_category_missing,
    _rule_phase_date_out_of_range,
    _rule_daily_window_fit,
    _rule_indoor_only_violation,
)


def validate_layer4_payload(
    payload: Layer4Payload,
    context: ValidatorContext,
    pass_index: int = 0,
) -> ValidatorResult:
    """Run all 21 §5.4 rules against `payload` + `context`; return a
    `ValidatorResult` with aggregated `RuleFailure` rows.

    `accepted` is True iff no `blocker`-severity failures fired. `warning`-
    severity failures do not block acceptance; they bubble to the validator
    output for orchestrator-side review.

    `retried_phase_names` is always empty here — that field is set by the
    orchestrator when it decides which phases to re-prompt per the §5.5
    capped-retry semantics. The validator is stateless and reports only
    what failed in this pass.
    """
    failures: list[RuleFailure] = []
    for rule in _ALL_RULES:
        failures.extend(rule(payload, context))
    accepted = not any(f.severity == "blocker" for f in failures)
    return ValidatorResult(
        pass_index=pass_index,
        accepted=accepted,
        rule_failures=failures,
        retried_phase_names=[],
    )
