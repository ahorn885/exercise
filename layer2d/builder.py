"""Layer 2D builder — injury-risk profile query node.

Per `Layer2D_Spec.md` §3 (function signature) + §5 (algorithm) + §7 (payload)
+ §8 (coaching flags). Pure query node: deterministic given inputs, no LLM
involvement. Three input signals feed the verdict per exercise (body-part
contraindication, condition contraindication, movement-constraint keyword
match against `injury_flags_text`); strongest verdict wins (EXCLUDE >
ACCOMMODATE > CLEAN). ACCOMMODATE picks pull from `V1_DEFAULT_ACCOMMODATIONS`
keyed on `(injury_type, severity)` per §5.3.6, with V1_FALLBACK for
uncovered combinations. Discipline-level risk profiles emit substitute
recommendations + back-check (§5.6.1) when risk is elevated.

D-73 Phase 2.2 — first runtime to consume the Phase 1.2B `injury_log`
schema extended in Phase 2.2 (severity 6-enum + injury_type 11-enum
+ side + movement_constraints multi-select per Athlete_Onboarding_Data_Spec_v5
§B.1 / §B.1.1 / §B.3). InjuryRecord + HealthConditionRecord typed in
`layer4/context.py`; Layer 1 builder loads them via `_load_injuries` +
`_load_health_conditions`. The Phase 5 orchestrator threads them here.

Spec-vs-deployed reconciliations applied:
- HealthConditionRecord.status is deployed as 'Active' | 'Resolved' | 'Inactive';
  spec §3 uses 'Current' | 'History'. Partition on `status == 'Active'` →
  current; else history.
- HealthConditionRecord.system_category is deployed as the 8-value lowercase
  enum (cardiac, respiratory, ...); spec §B.4.1 carries 11 capitalized values.
  Matching is consistent because `layer0.exercises.contraindicated_conditions`
  draws from the same `layer0.health_condition_categories` lookup vocab.
  Cardiac / Neurological / Concussion gates use the lowercase values.
- BODY_PARTS in `routes/injuries.py` (24 left/right-doubled) doesn't match
  the canonical `layer0.body_parts.canonical_name` 41-vocab. v1 boundary
  normalizer `_strip_side()` collapses "Left Wrist" → "Wrist" at the
  matching seam; storage stays as-entered. Tracked as a CARRY_FORWARD
  doc-sweep nit for the §B onboarding form refresh.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from layer4.context import (
    AccommodationModality,
    DisciplineRisk,
    Evidence,
    ExerciseRisk,
    ExerciseSubstitutionModality,
    FrequencyReductionModality,
    HealthConditionRecord,
    InjuryRecord,
    IntensityReductionModality,
    Layer2DCoachingFlag,
    Layer2DHitlItem,
    Layer2DPayload,
    LoadingTypeChangeModality,
    MatchedBodyPart,
    SubstituteRecommendation,
    TempoModificationModality,
    VolumeReductionModality,
)


# ─── Constants ───────────────────────────────────────────────────────────────


_REQUIRED_ETL_KEYS: frozenset[str] = frozenset({"0A", "0B", "0C"})

# §5.7 rule 2 — cardiac × high-cardiac-load disciplines triggers HITL.
# Spec lists D-001, D-002, D-006, D-008, D-024, D-024, D-028 (anything with
# sustained Z3+). Constant lives code-side per the spec recommendation
# (open item 2D-1 pattern — code-side curation for v1).
_HIGH_CARDIAC_LOAD_DISCIPLINES: frozenset[str] = frozenset({
    "D-001",  # Trail Running
    "D-002",  # Road Running
    "D-006",  # Road Cycling
    "D-008",  # Mountain Biking
    "D-024",  # Uphill Mountain Running
    "D-024",  # Downhill Mountain Running
    "D-028",  # XC Skiing
})

# §5.7 rule 5 — discipline_training_gaps rows. Defensive: the DTG join below
# builds the live set from `layer0.discipline_training_gaps`; this constant
# documents the intent for reviewers. D-020 (Swimrun) and D-025 (Fencing) were
# dropped by the discipline canon (Swimrun reclassified as a sport; Fencing
# removed with Modern Pentathlon), leaving D-022 (Alpine Descent).
_KNOWN_GAP_DISCIPLINES: frozenset[str] = frozenset({"D-022"})

# §5.3.6.4 rule 3 — post-surgical first-6-weeks loading-type-change preference.
_POST_SURGICAL_RECENT_DAYS: int = 42

# §5.3.6 — accommodation modality factor and intensity defaults pulled from
# the spec's V1_DEFAULT_ACCOMMODATIONS + V1_FALLBACK_ACCOMMODATIONS tables.
# Each evidence_basis citation is a short identifier; full citations live
# in `Layer2D_Spec.md` §5.3.6.1.


# ─── Errors ──────────────────────────────────────────────────────────────────


class Layer2DInputError(ValueError):
    """Raised by `q_layer2d_injury_risk_profile_payload` on §4 validation
    failure. Plan-gen catches and surfaces a user-facing error. NOT a HITL
    gate — HITL is for ambiguous content (post-surgical without clearance,
    etc.), not malformed inputs."""


# ─── §5.3.4 — Severity → Verdict mapping ─────────────────────────────────────


# Verdicts as comparable strings via ordinal weight. EXCLUDE > ACCOMMODATE > CLEAN.
_VERDICT_RANK: dict[str, int] = {"clean": 0, "accommodate": 1, "exclude": 2}


def _max_verdict(*verdicts: str) -> str:
    """Return the strongest verdict from the args; CLEAN if all clean."""
    best = "clean"
    for v in verdicts:
        if _VERDICT_RANK[v] > _VERDICT_RANK[best]:
            best = v
    return best


def _severity_to_verdict(severity: str | None) -> str:
    """Map injury severity (6-enum) to verdict per spec §5.3.4.

    Acute / Post-surgical → exclude; Recovering / Chronic-Managed /
    Structural-Permanent → accommodate; Resolved → clean (defensive —
    current_injuries shouldn't have Resolved); NULL → clean (defensive
    fallthrough for legacy rows pre-Phase-2.2).
    """
    if severity is None:
        return "clean"
    table = {
        "Acute": "exclude",
        "Recovering": "accommodate",
        "Chronic-Managed": "accommodate",
        "Post-surgical": "exclude",
        "Structural-Permanent": "accommodate",
        "Resolved": "clean",
    }
    return table.get(severity, "clean")


# ─── §5.3.3 / §5.5 — Keyword maps ───────────────────────────────────────────


# Per spec §5.3.3 — multi-select B.3 movement constraint → keyword bundle
# matched (case-insensitive substring) against `layer0.exercises.injury_flags_text`.
MOVEMENT_CONSTRAINT_KEYWORDS: dict[str, list[str]] = {
    "Pain with loading": ["under load", "heavy load", "weighted"],
    "Pain with impact": ["landing", "impact", "reactive load"],
    "Pain above specific joint angle": ["above 90", "full extension", "at depth", "wrist extension", "palm-down"],
    "Pain on descent / eccentric": ["eccentric", "descent", "downhill", "braking"],
    "Pain on rotation": ["rotation", "torque", "twisting"],
    "Pain with grip / sustained hold": ["grip", "sustained hold", "forearm fatigue"],
    "Pain with overhead movement": ["overhead", "above shoulder", "impingement"],
    "Instability": ["instability", "subluxation", "gives way"],
    "Reduced ROM": ["rom restriction", "dorsiflexion limited"],
    "Pain at high volume only": ["sustained", "repetitive", "overuse"],
}


# Per spec §5.5 — athlete's structured `body_part` → keyword bundle matched
# (case-insensitive substring) against discipline `common_injury_patterns`
# free-text. Code-side per spec decision 2D-1 option (A). v1 covers the
# AR-relevant subset + common cross-sport body parts.
BODY_PART_KEYWORDS: dict[str, list[str]] = {
    # Foot / Ankle
    "Ankle": ["ankle", "lateral ankle", "ankle sprain", "ankle torsion"],
    "Plantar fascia": ["plantar", "fascia", "fasciitis"],
    "Achilles": ["achilles", "gastroc-achilles", "achilles tendinopathy"],
    "Foot": ["foot", "metatarsal"],
    # Lower leg
    "Calf": ["calf", "gastrocnemius"],
    "Soleus": ["soleus"],
    "Shin": ["shin", "shin splints", "tibia", "tibial"],
    "Peroneal": ["peroneal"],
    # Knee
    "Knee": ["knee", "patellar", "patellofemoral", "tibial-femoral"],
    "Kneecap": ["kneecap", "patella", "patellar"],
    "Meniscus": ["meniscus", "meniscal"],
    "ACL": ["acl", "anterior cruciate"],
    "PCL": ["pcl", "posterior cruciate"],
    "MCL": ["mcl", "medial collateral"],
    "LCL": ["lcl", "lateral collateral"],
    # Upper leg
    "Quad": ["quad", "quadriceps", "quadricep"],
    "Hamstring": ["hamstring"],
    "IT band": ["it band", "itbs", "iliotibial", "it-band"],
    # Hip
    "Hip": ["hip pain", "hip joint", "hip contusion"],
    "Hip flexor": ["hip flexor"],
    "Glute": ["glute", "gluteal", "hip abductor"],
    "Groin": ["groin", "adductor"],
    "TFL": ["tfl", "tensor fasciae"],
    # Back
    "Lower back": ["lower back", "lumbar", "low back"],
    "Upper back": ["upper back", "thoracic"],
    "SI joint": ["si joint", "sacroiliac"],
    "Sciatica": ["sciatica", "sciatic"],
    "Spine (general)": ["spine", "spinal"],
    # Shoulder
    "Shoulder": [
        "shoulder", "shoulder strain", "shoulder fatigue", "shoulder dislocation",
    ],
    "Rotator cuff": [
        "rotator cuff", "rotator-cuff", "swimmer's shoulder", "impingement",
    ],
    "AC joint": ["ac joint", "acromioclavicular"],
    "Shoulder blade": ["shoulder blade", "scapula"],
    # Arm / Hand
    "Elbow": [
        "elbow", "epicondylitis", "lateral epicondylitis", "medial epicondylitis",
    ],
    "Forearm": ["forearm", "forearm fatigue"],
    "Wrist": [
        "wrist", "wrist tendinopathy", "wrist flexor", "wrist extensor",
        "wrist strain",
    ],
    "Hand": ["hand", "hand trauma", "blistered hands"],
    "Bicep": ["bicep", "biceps"],
    "Tricep": ["tricep", "triceps"],
    "Fingers": ["finger", "fingers"],
    "Finger pulley": ["finger pulley", "a2 pulley", "pulley strain"],
    "Thumb": ["thumb"],
    # Head / Neck
    "Neck": ["neck", "cervical", "neck strain"],
    "Jaw": ["jaw"],
    # Trunk
    "Rib": ["rib", "rib fracture"],
    "Chest": ["chest", "sternum"],
}


# ─── §5.3.6 — Modality constructors ──────────────────────────────────────────


def _vol(
    factor: float,
    applies_to: str,
    rationale: str,
    evidence_basis: list[str],
) -> VolumeReductionModality:
    return VolumeReductionModality(
        factor=factor,
        applies_to=applies_to,  # type: ignore[arg-type]
        rationale=rationale,
        evidence_basis=evidence_basis,
    )


def _intn(
    factor: float,
    target_metric: str,
    rationale: str,
    evidence_basis: list[str],
) -> IntensityReductionModality:
    return IntensityReductionModality(
        factor=factor,
        target_metric=target_metric,  # type: ignore[arg-type]
        rationale=rationale,
        evidence_basis=evidence_basis,
    )


def _tempo_iso(
    hold_s: int,
    sets: int,
    rest_s: int,
    intensity_pct_mvc: int,
    rationale: str,
    evidence_basis: list[str],
) -> TempoModificationModality:
    return TempoModificationModality(
        tempo_pattern="isometric_only",
        hold_s=hold_s,
        sets=sets,
        rest_s=rest_s,
        intensity_pct_mvc=intensity_pct_mvc,
        rationale=rationale,
        evidence_basis=evidence_basis,
    )


def _tempo_hsr(
    eccentric_s: int,
    concentric_s: int,
    rationale: str,
    evidence_basis: list[str],
) -> TempoModificationModality:
    return TempoModificationModality(
        tempo_pattern="heavy_slow_resistance",
        eccentric_s=eccentric_s,
        concentric_s=concentric_s,
        rationale=rationale,
        evidence_basis=evidence_basis,
    )


def _freq(
    rationale: str,
    evidence_basis: list[str],
    *,
    factor: float | None = None,
    sessions_per_week_cap: int | None = None,
    discipline_id: str | None = None,
) -> FrequencyReductionModality:
    return FrequencyReductionModality(
        factor=factor,
        sessions_per_week_cap=sessions_per_week_cap,
        discipline_id=discipline_id,
        rationale=rationale,
        evidence_basis=evidence_basis,
    )


def _loading(
    from_type: str,
    to_type: str,
    rationale: str,
    evidence_basis: list[str],
) -> LoadingTypeChangeModality:
    return LoadingTypeChangeModality(
        from_type=from_type,  # type: ignore[arg-type]
        to_type=to_type,  # type: ignore[arg-type]
        rationale=rationale,
        evidence_basis=evidence_basis,
    )


# ─── §5.3.6.2 / §5.3.6.3 — Default & fallback modality tables ────────────────


def _v1_default_accommodations() -> dict[tuple[str, str], list[AccommodationModality]]:
    """Return spec §5.3.6.2 V1_DEFAULT_ACCOMMODATIONS keyed on
    (injury_type, severity). Rationale + evidence_basis populated inline."""
    return {
        # Tendinopathy / overuse — Cook & Purdam load-management framework
        ("Tendinopathy / overuse", "Acute"): [
            _vol(
                0.5, "sets",
                "Acute reactive — drop volume to ~50% to settle the load response.",
                ["soligard_2016_bjsm", "acsm_guidelines_11ed"],
            ),
            _tempo_iso(
                45, 5, 120, 70,
                "Stage 1 isometric for in-season analgesia per Cook & Purdam.",
                ["rio_2015_bjsm", "cook_purdam_2014_bjsm"],
            ),
        ],
        ("Tendinopathy / overuse", "Recovering"): [
            _vol(
                0.7, "sets",
                "Graded return-to-volume; ~30% reduction during recovery phase.",
                ["soligard_2016_bjsm"],
            ),
            _tempo_hsr(
                3, 3,
                "Stage 2 HSR per Beyer 2015 — equivalent outcome to eccentric-only "
                "with better compliance.",
                ["beyer_2015_ajsm", "alfredson_1998"],
            ),
        ],
        ("Tendinopathy / overuse", "Chronic-Managed"): [
            _tempo_hsr(
                3, 3,
                "HSR maintenance protocol; chronic tendinopathy responds to "
                "sustained tendon-loading time.",
                ["beyer_2015_ajsm"],
            ),
        ],
        # Acute soft tissue (strain / sprain / tear)
        ("Acute soft tissue (strain / sprain / tear)", "Acute"): [
            _vol(
                0.5, "sets",
                "Acute strain — cut volume to allow tissue settling.",
                ["soligard_2016_bjsm"],
            ),
            _intn(
                0.6, "percent_1rm",
                "Sub-symptomatic load per Silbernagel pain-monitoring (VAS ≤ 5/10).",
                ["silbernagel_2007_ajsm"],
            ),
        ],
        ("Acute soft tissue (strain / sprain / tear)", "Recovering"): [
            _vol(
                0.8, "sets",
                "Graded return — 20% volume buffer during recovery.",
                ["soligard_2016_bjsm"],
            ),
            _intn(
                0.8, "percent_1rm",
                "Graded return-to-load per pain-monitored progression.",
                ["silbernagel_2007_ajsm"],
            ),
        ],
        # Bone — stress fracture. Spec §5.3.6.4 rule 2: intensity_reduction
        # alone is INSUFFICIENT. Always pair with frequency_reduction(0.0 or low)
        # or route through EXCLUDE.
        ("Bone — stress fracture", "Acute"): [
            _freq(
                "Zero frequency on the affected loading mode; non-impact "
                "alternative routes through 2C Tier 2/3 substitution.",
                ["acsm_guidelines_11ed"],
                factor=0.0,
            ),
        ],
        ("Bone — stress fracture", "Recovering"): [
            _freq(
                "Half-frequency on affected mode during graded return.",
                ["acsm_guidelines_11ed"],
                factor=0.5,
            ),
            _vol(
                0.6, "duration",
                "Duration-capped return — bone remodel tolerance leads loading "
                "tolerance.",
                ["acsm_guidelines_11ed"],
            ),
        ],
        # Joint sprain — non-surgical mechanical
        ("Joint (mechanical) — non-surgical", "Acute"): [
            _vol(
                0.5, "sets",
                "Acute joint instability — cut volume to spare the unguarded "
                "joint capsule.",
                ["soligard_2016_bjsm"],
            ),
            _intn(
                0.6, "percent_1rm",
                "Sub-symptomatic load until joint stability returns.",
                ["acsm_guidelines_11ed"],
            ),
        ],
        ("Joint (mechanical) — non-surgical", "Recovering"): [
            _vol(
                0.8, "sets",
                "Graded return during recovery.",
                ["soligard_2016_bjsm"],
            ),
            _intn(
                0.8, "percent_1rm",
                "Graded return-to-load per pain-monitored progression.",
                ["silbernagel_2007_ajsm"],
            ),
        ],
        # Post-surgical first-6-weeks cross-education sparing per
        # Manca/Hendy-Lamon (§5.3.6.4 rule 3).
        ("Post-surgical", "Post-surgical"): [
            _loading(
                "bilateral", "unilateral_contralateral",
                "Train the uninjured side; cross-education preserves ~12-22% "
                "of the immobilized limb's strength via neural transfer.",
                ["manca_2017_sports_med", "hendy_lamon_2017_systematic_review"],
            ),
        ],
        ("Joint (mechanical) — surgical", "Post-surgical"): [
            _loading(
                "bilateral", "unilateral_contralateral",
                "Surgical joint immobilization — train the uninjured limb to "
                "preserve strength via cross-education.",
                ["manca_2017_sports_med", "farthing_zehr_2014_bjsm"],
            ),
        ],
    }


def _v1_fallback_accommodations() -> list[AccommodationModality]:
    """Spec §5.3.6.3 — conservative IOC-consensus moderate deload (0.7 / 0.7)."""
    return [
        _vol(
            0.7, "sets",
            "Conservative volume deload — broad-spectrum IOC-consensus position "
            "applied when a per-(injury_type, severity) default isn't tabled.",
            ["soligard_2016_bjsm", "acsm_guidelines_11ed_fitt_vp"],
        ),
        _intn(
            0.7, "percent_1rm",
            "Conservative intensity deload — paired with the volume cut to "
            "drop both signals 30%.",
            ["soligard_2016_bjsm"],
        ),
    ]


# ─── §5.3.6.4 — Phase-dependent contraindications ────────────────────────────


def _apply_phase_contraindications(
    base: list[AccommodationModality],
    primary: InjuryRecord,
    exercise: dict[str, Any],
) -> list[AccommodationModality]:
    """Filter / rewrite base modalities per spec §5.3.6.4 phase rules.

    1. Acute reactive tendinopathy must use isometric_only — eccentric / HSR
       contraindicated in the acute reactive phase per Cook & Purdam 2014.
    2. Bone stress fracture: intensity_reduction alone is insufficient — must
       pair with frequency_reduction(low) or route through EXCLUDE. Code-side
       enforcement here: if the base only carries intensity_reduction for a
       stress-fracture athlete, prepend a frequency_reduction(0.0).
    3. Post-surgical first 6 weeks: prefer loading_type_change(unilateral_contralateral)
       over reduced-load bilateral prescriptions. Replace any
       intensity_reduction/volume_reduction with the cross-education loading
       swap when in the recent-post-surgical window.
    """
    if (
        primary.injury_type == "Tendinopathy / overuse"
        and primary.severity == "Acute"
    ):
        # Rule 1: rewrite any eccentric_focus / heavy_slow_resistance tempo
        # modalities to isometric_only. Defensive: spec §5.3.6.2 already
        # tables the acute tendinopathy case with isometric; this guards
        # against fallback contamination.
        rewritten: list[AccommodationModality] = []
        for m in base:
            if isinstance(m, TempoModificationModality) and m.tempo_pattern in (
                "eccentric_focus", "heavy_slow_resistance",
            ):
                rewritten.append(_tempo_iso(
                    45, 5, 120, 70,
                    "Acute reactive tendinopathy override — isometric-only per "
                    "Cook & Purdam (eccentric / HSR contraindicated in acute phase).",
                    ["cook_purdam_2014_bjsm", "rio_2015_bjsm"],
                ))
            else:
                rewritten.append(m)
        return rewritten
    if primary.injury_type == "Bone — stress fracture":
        # Rule 2: ensure a frequency_reduction is present.
        has_freq = any(isinstance(m, FrequencyReductionModality) for m in base)
        if not has_freq:
            return [
                _freq(
                    "Stress fracture safety enforcement — intensity reduction "
                    "alone cannot manage bone-load risk; frequency cap added.",
                    ["acsm_guidelines_11ed"],
                    factor=0.0,
                ),
                *base,
            ]
        return base
    if primary.severity == "Post-surgical" and _is_recent_post_surgical(primary):
        # Rule 3: prefer the cross-education swap.
        already_swapped = any(
            isinstance(m, LoadingTypeChangeModality)
            and m.to_type == "unilateral_contralateral"
            for m in base
        )
        if already_swapped:
            return base
        return [
            _loading(
                "bilateral", "unilateral_contralateral",
                "Post-surgical first-6-week override — cross-education sparing "
                "preserves the immobilized limb without loading the surgical site.",
                ["manca_2017_sports_med", "hendy_lamon_2017_systematic_review"],
            ),
        ]
    return base


def _is_recent_post_surgical(injury: InjuryRecord) -> bool:
    """True when severity is Post-surgical AND start_date is within 6 weeks."""
    if injury.severity != "Post-surgical" or injury.start_date is None:
        return False
    delta = (datetime.utcnow().date() - injury.start_date).days
    return 0 <= delta < _POST_SURGICAL_RECENT_DAYS


# ─── §5.3 / §5.5 — Per-exercise + per-discipline verdict signals ─────────────


def _strip_side(body_part: str) -> str:
    """Boundary normalizer: collapse "Left Wrist" / "Right Wrist" → "Wrist".

    Deployed `routes/injuries.py:BODY_PARTS` doubles all bilateral parts
    (Left X / Right X) but `layer0.exercises.contraindicated_parts` and
    `BODY_PART_KEYWORDS` use the side-less canonical form. Strip the
    leading 'Left ' / 'Right ' prefix for matching.
    """
    for prefix in ("Left ", "Right "):
        if body_part.startswith(prefix):
            return body_part[len(prefix):]
    return body_part


def _body_part_verdict(
    exercise: dict[str, Any],
    current_injuries: list[InjuryRecord],
) -> tuple[str, list[Evidence]]:
    """Spec §5.3.1 — body-part set-intersect against contraindicated_parts."""
    contra = set(exercise.get("contraindicated_parts") or [])
    if not contra:
        return "clean", []
    evidence: list[Evidence] = []
    verdict = "clean"
    for inj in current_injuries:
        canonical = _strip_side(inj.body_part)
        if canonical in contra or inj.body_part in contra:
            matched = canonical if canonical in contra else inj.body_part
            sev_verdict = _severity_to_verdict(inj.severity)
            evidence.append(Evidence(
                source="contraindicated_part",
                exercise_field="contraindicated_parts",
                matched_value=matched,
                injury_body_part=inj.body_part,
                injury_severity=inj.severity,
            ))
            verdict = _max_verdict(verdict, sev_verdict)
    return verdict, evidence


def _condition_verdict(
    exercise: dict[str, Any],
    current_conditions: list[HealthConditionRecord],
) -> tuple[str, list[Evidence]]:
    """Spec §5.3.2 — system-category match against contraindicated_conditions.

    Default verdict = accommodate (conditions are blanket — no per-condition
    severity field). Cardiac × high-intensity is escalated to exclude at the
    HITL gate (§5.7 rule 2), not here.
    """
    contra = set(exercise.get("contraindicated_conditions") or [])
    if not contra:
        return "clean", []
    evidence: list[Evidence] = []
    verdict = "clean"
    for cond in current_conditions:
        if cond.system_category in contra:
            evidence.append(Evidence(
                source="contraindicated_condition",
                exercise_field="contraindicated_conditions",
                matched_value=cond.system_category,
                condition_category=cond.system_category,
            ))
            verdict = _max_verdict(verdict, "accommodate")
    return verdict, evidence


def _movement_constraint_verdict(
    exercise: dict[str, Any],
    current_injuries: list[InjuryRecord],
) -> tuple[str, list[Evidence]]:
    """Spec §5.3.3 — substring match B.3 keyword bundles against injury_flags_text."""
    flag_text = exercise.get("injury_flags_text")
    if not flag_text:
        return "clean", []
    flag_text_lower = flag_text.lower()
    evidence: list[Evidence] = []
    verdict = "clean"
    for inj in current_injuries:
        for constraint in inj.movement_constraints or []:
            keywords = MOVEMENT_CONSTRAINT_KEYWORDS.get(constraint, [])
            hits = [kw for kw in keywords if kw in flag_text_lower]
            if hits:
                sev_verdict = _severity_to_verdict(inj.severity)
                evidence.append(Evidence(
                    source="movement_constraint",
                    exercise_field="injury_flags_text",
                    matched_keywords=hits,
                    injury_body_part=inj.body_part,
                    injury_severity=inj.severity,
                    constraint=constraint,
                ))
                verdict = _max_verdict(verdict, sev_verdict)
    return verdict, evidence


def _recommend_accommodations(
    exercise: dict[str, Any],
    current_injuries: list[InjuryRecord],
    evidence: list[Evidence],
) -> list[AccommodationModality]:
    """Spec §5.3.6.5 — pick modalities from V1_DEFAULT_ACCOMMODATIONS,
    fall back to V1_FALLBACK, then apply §5.3.6.4 phase contraindications.

    Driving-injury heuristic: v1 picks the first injury whose severity is
    in the ACCOMMODATE-mapped set (Recovering / Chronic-Managed /
    Structural-Permanent / Post-surgical) that contributed evidence. If
    no injury drove the verdict (i.e., the ACCOMMODATE came from a
    condition match), V1_FALLBACK applies.
    """
    fallback = _v1_fallback_accommodations()
    accommodate_severities = {
        "Recovering", "Chronic-Managed", "Structural-Permanent", "Post-surgical",
    }
    # Map body_part / severity from evidence back to injury records to find
    # the driver.
    driver_keys: set[tuple[str, str | None]] = {
        (ev.injury_body_part, ev.injury_severity)
        for ev in evidence
        if ev.injury_body_part is not None
        and ev.injury_severity in accommodate_severities
    }
    if not driver_keys:
        return fallback
    driving_injuries = [
        inj for inj in current_injuries
        if (inj.body_part, inj.severity) in driver_keys
    ]
    if not driving_injuries:
        return fallback
    primary = driving_injuries[0]
    if primary.injury_type is None or primary.severity is None:
        return fallback
    table = _v1_default_accommodations()
    base = table.get(
        (primary.injury_type, primary.severity), fallback,
    )
    return _apply_phase_contraindications(base, primary, exercise)


def _evaluate_exercise(
    exercise: dict[str, Any],
    current_injuries: list[InjuryRecord],
    current_conditions: list[HealthConditionRecord],
) -> ExerciseRisk:
    """Spec §5.3.5 — combine three signals, build the ExerciseRisk."""
    body_v, body_ev = _body_part_verdict(exercise, current_injuries)
    cond_v, cond_ev = _condition_verdict(exercise, current_conditions)
    move_v, move_ev = _movement_constraint_verdict(exercise, current_injuries)
    overall = _max_verdict(body_v, cond_v, move_v)
    evidence = body_ev + cond_ev + move_ev
    accommodations: list[AccommodationModality] = (
        _recommend_accommodations(exercise, current_injuries, evidence)
        if overall == "accommodate"
        else []
    )
    return ExerciseRisk(
        exercise_id=exercise["exercise_id"],
        exercise_name=exercise["exercise_name"],
        discipline_ids=sorted(exercise["_discipline_ids"]),
        verdict=overall,  # type: ignore[arg-type]
        accommodations=accommodations,
        evidence=evidence,
    )


# ─── §5.4 — Discipline-level risk profiling ──────────────────────────────────


def _risk_level_from_matches(
    matched_current: list[MatchedBodyPart],
    matched_history: list[MatchedBodyPart],
) -> str:
    """Spec §5.4 rubric: HIGH if any current Acute/Post-surgical; ELEVATED
    if any current; INFORMATIONAL if history-only; LOW otherwise."""
    if any(m.severity in {"Acute", "Post-surgical"} for m in matched_current):
        return "high"
    if matched_current:
        return "elevated"
    if matched_history:
        return "informational"
    return "low"


def _discipline_risk(
    discipline: dict[str, Any],
    current_injuries: list[InjuryRecord],
    history_injuries: list[InjuryRecord],
) -> tuple[str, list[MatchedBodyPart], list[MatchedBodyPart]]:
    """Compute risk_level + matched body parts. Substitutes attached later."""
    patterns_raw = discipline.get("common_injury_patterns") or []
    patterns_text = " ".join(patterns_raw).lower()
    if not patterns_text:
        return "low", [], []
    matched_current: list[MatchedBodyPart] = []
    matched_history: list[MatchedBodyPart] = []
    for inj_list, bucket in (
        (current_injuries, matched_current),
        (history_injuries, matched_history),
    ):
        for inj in inj_list:
            canonical = _strip_side(inj.body_part)
            keywords = BODY_PART_KEYWORDS.get(canonical, [canonical.lower()])
            hits = [kw for kw in keywords if kw in patterns_text]
            if hits:
                bucket.append(MatchedBodyPart(
                    body_part=canonical,
                    side=inj.side,
                    severity=inj.severity or "Resolved",
                    matched_keywords=hits,
                ))
    return _risk_level_from_matches(matched_current, matched_history), matched_current, matched_history


# ─── §5.6.1 — Substitute back-check ──────────────────────────────────────────


def _substitute_back_check(
    substitute_patterns_text: str,
    current_injuries: list[InjuryRecord],
) -> tuple[bool, list[str]]:
    """Re-run §5.4 body-part matching against the substitute's own patterns.

    Returns (still_at_risk, overlapping_body_parts). still_at_risk = True
    when the athlete's at-risk body parts also appear in the substitute's
    common_injury_patterns text.
    """
    if not substitute_patterns_text:
        return False, []
    text_lower = substitute_patterns_text.lower()
    overlaps: list[str] = []
    for inj in current_injuries:
        canonical = _strip_side(inj.body_part)
        keywords = BODY_PART_KEYWORDS.get(canonical, [canonical.lower()])
        if any(kw in text_lower for kw in keywords):
            if canonical not in overlaps:
                overlaps.append(canonical)
    return (bool(overlaps), overlaps)


# ─── DB loaders ──────────────────────────────────────────────────────────────


def _load_candidates(
    db,
    included_discipline_ids: list[str],
    version_0a: str,
    versions_0b: list[str],
) -> list[dict[str, Any]]:
    """Spec §5.2 — exercise universe across the included disciplines.

    Returns one dict per (exercise_id) deduplicated post-fetch; each dict
    carries `_discipline_ids: set[str]` to track multi-discipline attribution.

    Dedup rationale (D-47) — the join below can surface the same `exercise_id`
    on more than one row via **two independent bridge-multiplication paths**,
    both of which the post-fetch `by_id` collapse handles:

    1. Multi-discipline path: an exercise reachable from several of the
       `included_discipline_ids` returns once per matching `sdb.discipline_id`.
    2. Framework-mapping path (co-cause): `layer0.sport_name_aliases` is
       intentionally one-to-many — a single `exercise_db_sport` may map to
       multiple `framework_sport` values (sub-format splitting). The bridge
       therefore holds one row per `(framework_sport, discipline_id)` pair, so
       even a *single* included discipline can match multiple bridge rows that
       share the same `exercise_db_sport`, returning the same exercise once per
       framework sport (see Layer0_ETL_Spec §4.11 multiplication property).

    Deduping by `exercise_id` is a contract on this consumer, not a DB-level
    fix; `_discipline_ids` accumulates attribution across every matched row.
    """
    cur = db.execute(
        """
        SELECT
          sxm.exercise_id,
          sxm.exercise_name,
          sxm.exercise_type,
          sxm.priority,
          e.contraindicated_parts,
          e.contraindicated_conditions,
          e.injury_flags_text,
          e.movement_patterns,
          sdb.discipline_id
        FROM layer0.sport_discipline_bridge sdb
        JOIN layer0.sport_exercise_map sxm
          ON sxm.sport_name = sdb.exercise_db_sport
        JOIN layer0.exercises e
          ON e.exercise_id = sxm.exercise_id
        WHERE sdb.discipline_id = ANY(?)
          AND sdb.etl_version = ?
          AND sxm.etl_version = ANY(?)
          AND e.etl_version = ANY(?)
          AND sdb.superseded_at IS NULL
          AND sxm.superseded_at IS NULL
          AND e.superseded_at IS NULL
        """,
        (included_discipline_ids, version_0a, versions_0b, versions_0b),
    )
    by_id: dict[str, dict[str, Any]] = {}
    for r in cur.fetchall():
        eid = r["exercise_id"]
        if eid not in by_id:
            by_id[eid] = {
                "exercise_id": eid,
                "exercise_name": r["exercise_name"],
                "exercise_type": r["exercise_type"],
                "priority": r["priority"],
                "contraindicated_parts": r["contraindicated_parts"] or [],
                "contraindicated_conditions": r["contraindicated_conditions"] or [],
                "injury_flags_text": r["injury_flags_text"],
                "movement_patterns": r["movement_patterns"] or [],
                "_discipline_ids": set(),
            }
        by_id[eid]["_discipline_ids"].add(r["discipline_id"])
    return list(by_id.values())


def _load_disciplines(
    db,
    included_discipline_ids: list[str],
    version_0a: str,
) -> list[dict[str, Any]]:
    """Load disciplines for §5.4 risk profiling."""
    cur = db.execute(
        """
        SELECT discipline_id, discipline_name, common_injury_patterns
        FROM layer0.disciplines
        WHERE discipline_id = ANY(?)
          AND etl_version = ?
          AND superseded_at IS NULL
        """,
        (included_discipline_ids, version_0a),
    )
    return [
        {
            "discipline_id": r["discipline_id"],
            "discipline_name": r["discipline_name"],
            "common_injury_patterns": r["common_injury_patterns"] or [],
        }
        for r in cur.fetchall()
    ]


def _load_substitutes(
    db,
    discipline_id: str,
    version_0a: str,
) -> list[dict[str, Any]]:
    """Spec §5.6 — load discipline_substitutes ordered by fidelity DESC."""
    cur = db.execute(
        """
        SELECT
          ds.substitute_id,
          ds.substitute_name,
          ds.fidelity,
          ds.constraints,
          ds.category,
          ds.substitute_covers,
          d.common_injury_patterns AS substitute_patterns
        FROM layer0.discipline_substitutes ds
        LEFT JOIN layer0.disciplines d
          ON d.discipline_id = ds.substitute_id
          AND d.etl_version = ?
          AND d.superseded_at IS NULL
        WHERE ds.target_id = ?
          AND ds.etl_version = ?
          AND ds.superseded_at IS NULL
        ORDER BY ds.fidelity DESC
        """,
        (version_0a, discipline_id, version_0a),
    )
    return [
        {
            "substitute_id": r["substitute_id"],
            "substitute_name": r["substitute_name"],
            "fidelity": float(r["fidelity"]),
            "constraints": r["constraints"],
            "category": r["category"],
            "substitute_covers": r["substitute_covers"] or [],
            "substitute_patterns_text": (
                " ".join(r["substitute_patterns"] or [])
                if r["substitute_patterns"]
                else ""
            ),
        }
        for r in cur.fetchall()
    ]


def _load_training_gaps(
    db,
    included_discipline_ids: list[str],
    version_0a: str,
) -> set[str]:
    """Return the set of `discipline_id` that have a discipline_training_gaps
    row at the pinned 0A version. Used by §5.7 rule 5."""
    cur = db.execute(
        """
        SELECT discipline_id
        FROM layer0.discipline_training_gaps
        WHERE discipline_id = ANY(?)
          AND etl_version = ?
          AND superseded_at IS NULL
        """,
        (included_discipline_ids, version_0a),
    )
    return {r["discipline_id"] for r in cur.fetchall()}


# ─── §5.7 — HITL determination ───────────────────────────────────────────────


def _determine_hitl(
    current_injuries: list[InjuryRecord],
    current_conditions: list[HealthConditionRecord],
    discipline_risks: list[DisciplineRisk],
    included_discipline_ids: list[str],
    gap_disciplines: set[str],
) -> tuple[bool, list[Layer2DHitlItem]]:
    """Spec §5.7 — five HITL rules. Returns (hitl_required, items[])."""
    items: list[Layer2DHitlItem] = []
    # Rule 1: Post-surgical without clearance.
    for inj in current_injuries:
        if inj.severity == "Post-surgical":
            notes_text = (inj.modifications_needed or "") + " " + (inj.description or "")
            has_clearance = any(
                token in notes_text.lower()
                for token in ("cleared", "clearance", "released to train")
            )
            severity = "warn" if has_clearance else "block"
            items.append(Layer2DHitlItem(
                hitl_type="post_surgical_clearance",
                injury=inj.model_dump(),
                severity=severity,  # type: ignore[arg-type]
                message=(
                    f"Post-surgical {inj.body_part} ({inj.injury_type or 'Other'}) "
                    f"{'has clearance notes — confirm before plan-gen proceeds' if has_clearance else 'lacks documented clearance. Plan-gen will not proceed without it.'}"
                ),
                suggested_resolutions=[
                    "Enter clearance date in modifications_needed",
                    "Update severity to Recovering if cleared",
                    "Drop the affected discipline until clearance",
                ],
            ))
    # Rule 2: Cardiac × high-cardiac-load disciplines.
    cardiac_active = any(c.system_category == "cardiac" for c in current_conditions)
    high_load_intersect = sorted(
        set(included_discipline_ids) & _HIGH_CARDIAC_LOAD_DISCIPLINES,
    )
    if cardiac_active and high_load_intersect:
        cond = next(c for c in current_conditions if c.system_category == "cardiac")
        items.append(Layer2DHitlItem(
            hitl_type="cardiac_high_load_review",
            condition=cond.model_dump(),
            severity="block",
            message=(
                f"Active cardiac condition ({cond.condition_name}) "
                f"with high-cardiac-load disciplines {high_load_intersect}. "
                "Plan-gen requires medical clearance confirmation before proceeding."
            ),
            suggested_resolutions=[
                "Confirm cardiologist clearance for sustained Z3+ work",
                "Drop the high-cardiac-load disciplines",
                "Switch to low-intensity substitutes",
            ],
        ))
    # Rule 3: Concussion (current Neurological).
    for cond in current_conditions:
        if (
            cond.system_category == "neurological"
            and "concussion" in cond.condition_name.lower()
        ):
            items.append(Layer2DHitlItem(
                hitl_type="concussion_current",
                condition=cond.model_dump(),
                severity="block",
                message=(
                    "Current concussion requires per-stage return-to-load gating "
                    "that Layer 2D cannot auto-resolve. Plan-gen pauses until "
                    "the athlete's clinical team has cleared graded return."
                ),
                suggested_resolutions=[
                    "Confirm return-to-load stage and clearance",
                    "Mark concussion status as History when symptom-free",
                ],
            ))
    # Rule 4: HIGH-risk discipline with no available substitutes.
    for dr in discipline_risks:
        if dr.risk_level == "high" and not dr.suggested_substitutes:
            items.append(Layer2DHitlItem(
                hitl_type="no_substitute_for_high_risk",
                discipline_id=dr.discipline_id,
                severity="block",
                message=(
                    f"{dr.discipline_name} risk-elevated to HIGH given current "
                    f"injuries but no substitute disciplines are available. "
                    "Athlete must decide: drop, accept elevated risk, or wait."
                ),
                suggested_resolutions=[
                    f"Drop {dr.discipline_name} from the training set",
                    "Accept the elevated risk and proceed",
                    "Wait until the driving injury resolves",
                ],
            ))
    # Rule 5: Discipline training gap × HIGH risk concurrent.
    for dr in discipline_risks:
        if dr.risk_level == "high" and dr.discipline_id in gap_disciplines:
            items.append(Layer2DHitlItem(
                hitl_type="gap_x_high_risk_concurrent",
                discipline_id=dr.discipline_id,
                severity="block",
                message=(
                    f"{dr.discipline_name} has a known training gap "
                    "(no clean single substitute) AND is HIGH-risk. "
                    "Athlete decision needed: drop, multi-substitute "
                    "composition, or wait for injury resolution."
                ),
                suggested_resolutions=[
                    f"Drop {dr.discipline_name} until injury resolves",
                    "Build a multi-discipline substitute composition",
                    "Accept the combined risk profile",
                ],
            ))
    return bool(items) and any(i.severity == "block" for i in items), items


# ─── §8 — Coaching flag emitters ─────────────────────────────────────────────


def _emit_coaching_flags(
    discipline_risks: list[DisciplineRisk],
    current_injuries: list[InjuryRecord],
    history_conditions: list[HealthConditionRecord],
    body_part_vocab_misses: list[str],
) -> list[Layer2DCoachingFlag]:
    flags: list[Layer2DCoachingFlag] = []
    # §8.1 elevated_discipline_risk + §8.2 discipline_substitution_suggested
    for dr in discipline_risks:
        if dr.risk_level == "elevated":
            body_parts_str = ", ".join(
                sorted({m.body_part for m in dr.matched_current_parts})
            )
            flags.append(Layer2DCoachingFlag(
                flag_type="elevated_discipline_risk",
                discipline_id=dr.discipline_id,
                discipline_name=dr.discipline_name,
                message=(
                    f"{dr.discipline_name} has elevated injury risk given your "
                    f"current {body_parts_str} injuries. "
                    f"{len(dr.suggested_substitutes)} substitute disciplines available."
                ),
                metadata={
                    "risk_level": "elevated",
                    "matched_body_parts": [
                        m.body_part for m in dr.matched_current_parts
                    ],
                    "substitute_count": len(dr.suggested_substitutes),
                },
            ))
        if dr.risk_level in ("elevated", "high") and dr.suggested_substitutes:
            top = dr.suggested_substitutes[0]
            flags.append(Layer2DCoachingFlag(
                flag_type="discipline_substitution_suggested",
                discipline_id=dr.discipline_id,
                discipline_name=dr.discipline_name,
                message=(
                    f"Consider substituting {dr.discipline_name} with "
                    f"{top.substitute_name} (fidelity {int(top.fidelity * 100)}%) — "
                    f"{top.category or 'cross-modality'}."
                ),
                metadata={
                    "recommendations": [
                        {
                            "substitute_discipline_id": s.substitute_discipline_id,
                            "substitute_name": s.substitute_name,
                            "fidelity": s.fidelity,
                            "category": s.category,
                            "constraints": s.constraints,
                            "still_at_risk": s.still_at_risk,
                            "still_at_risk_body_parts": s.still_at_risk_body_parts,
                        }
                        for s in dr.suggested_substitutes[:3]
                    ],
                },
            ))
    # §8.3 recurring_injury_pattern (history-only)
    for dr in discipline_risks:
        if dr.matched_history_parts and not dr.matched_current_parts:
            body_parts = sorted({m.body_part for m in dr.matched_history_parts})
            flags.append(Layer2DCoachingFlag(
                flag_type="recurring_injury_pattern",
                discipline_id=dr.discipline_id,
                discipline_name=dr.discipline_name,
                message=(
                    f"Your history of {', '.join(body_parts)} injury overlaps "
                    f"with {dr.discipline_name}'s common injury patterns. "
                    "Plan-gen will prioritize prevention exercises."
                ),
                metadata={
                    "history_body_parts": body_parts,
                },
            ))
    # §8.4 multi_body_part_load_concern
    if len(current_injuries) >= 3:
        flags.append(Layer2DCoachingFlag(
            flag_type="multi_body_part_load_concern",
            message=(
                f"You have {len(current_injuries)} active injuries. "
                "Cumulative load risk is elevated; recovery prioritization "
                "may need to exceed typical phase defaults."
            ),
            metadata={
                "injury_count": len(current_injuries),
                "body_parts": [_strip_side(i.body_part) for i in current_injuries],
            },
        ))
    # §8.5 condition_history_informational
    for cond in history_conditions:
        if cond.system_category in {"neurological", "cardiac", "respiratory"}:
            flags.append(Layer2DCoachingFlag(
                flag_type="condition_history_informational",
                message=(
                    f"History of {cond.condition_name} ({cond.system_category}). "
                    "Plan-gen will apply prevention-focused programming."
                ),
                metadata={
                    "category": cond.system_category,
                    "name": cond.condition_name,
                },
            ))
    # §8.6 body_part_vocab_miss
    for bp in body_part_vocab_misses:
        flags.append(Layer2DCoachingFlag(
            flag_type="body_part_vocab_miss",
            message=(
                f"Injury record references body part '{bp}' not in canonical "
                "vocabulary. Skipped from auto-matching. Consider standardizing "
                "the entry."
            ),
            metadata={"unrecognized_body_part": bp},
        ))
    return flags


# ─── §4 — Input validation ───────────────────────────────────────────────────


def _validate_inputs(
    injuries: Any,
    conditions: Any,
    included_discipline_ids: Any,
    etl_version_set: Any,
) -> None:
    if not isinstance(injuries, list):
        raise Layer2DInputError("injuries must be a list (may be empty).")
    if not isinstance(conditions, list):
        raise Layer2DInputError("conditions must be a list (may be empty).")
    if not isinstance(included_discipline_ids, list) or not included_discipline_ids:
        raise Layer2DInputError(
            "included_discipline_ids must be a non-empty list of strings."
        )
    for did in included_discipline_ids:
        if not isinstance(did, str) or not did:
            raise Layer2DInputError(
                "included_discipline_ids entries must be non-empty strings."
            )
    if not isinstance(etl_version_set, dict):
        raise Layer2DInputError("etl_version_set must be a dict.")
    missing = _REQUIRED_ETL_KEYS - set(etl_version_set.keys())
    if missing:
        raise Layer2DInputError(
            f"etl_version_set missing required keys: {sorted(missing)}"
        )


# ─── Public entry ────────────────────────────────────────────────────────────


def q_layer2d_injury_risk_profile_payload(
    db,
    injuries: list[InjuryRecord],
    conditions: list[HealthConditionRecord],
    included_discipline_ids: list[str],
    *,
    etl_version_set: dict[str, str],
) -> Layer2DPayload:
    """Layer 2D — injury-risk profile per `Layer2D_Spec.md` §3.

    Returns the categorized exercise view + per-discipline risk profile +
    coaching flags + HITL items. Pure read; deterministic given inputs.
    Performance budget per spec §11: ~350ms for AR baseline.
    """
    _validate_inputs(injuries, conditions, included_discipline_ids, etl_version_set)
    version_0a = etl_version_set["0A"]
    version_0b = etl_version_set["0B"]
    versions_0b = [version_0b]
    # §5.1 partition by status. Deployed `InjuryRecord.status` is the
    # ('Active' / 'Resolved' / 'Inactive') 3-enum; spec's `.status` computed
    # property partitions on severity. We use the deployed status to split
    # current vs history records (Active → current). Resolved-severity
    # injuries on Active records (unusual) flow through verdict mapping
    # which returns CLEAN defensively.
    current_injuries = [i for i in injuries if i.status == "Active"]
    history_injuries = [i for i in injuries if i.status != "Active"]
    current_conditions = [c for c in conditions if c.status == "Active"]
    history_conditions = [c for c in conditions if c.status != "Active"]
    # Body-part vocab miss audit per §8.6 / spec §4 precondition 2.
    body_part_vocab_misses: list[str] = []
    for inj in current_injuries + history_injuries:
        canonical = _strip_side(inj.body_part)
        if (
            canonical not in BODY_PART_KEYWORDS
            and inj.body_part not in BODY_PART_KEYWORDS
        ):
            if canonical not in body_part_vocab_misses:
                body_part_vocab_misses.append(canonical)
    # §5.2 candidate exercises.
    candidates = _load_candidates(
        db, included_discipline_ids, version_0a, versions_0b,
    )
    # §5.3 per-exercise verdict.
    excluded: list[ExerciseRisk] = []
    accommodated: list[ExerciseRisk] = []
    clean_ids: list[str] = []
    for ex in candidates:
        risk = _evaluate_exercise(ex, current_injuries, current_conditions)
        if risk.verdict == "exclude":
            excluded.append(risk)
        elif risk.verdict == "accommodate":
            accommodated.append(risk)
        else:
            clean_ids.append(risk.exercise_id)
    # §5.4 discipline risk profiles.
    disciplines = _load_disciplines(db, included_discipline_ids, version_0a)
    discipline_by_id = {d["discipline_id"]: d for d in disciplines}
    gap_disciplines = _load_training_gaps(
        db, included_discipline_ids, version_0a,
    )
    discipline_risks: list[DisciplineRisk] = []
    for did in included_discipline_ids:
        d = discipline_by_id.get(did)
        if d is None:
            # Missing 0A row — defensive low-risk profile, no substitutes.
            discipline_risks.append(DisciplineRisk(
                discipline_id=did,
                discipline_name=did,
                risk_level="low",
                matched_current_parts=[],
                matched_history_parts=[],
                suggested_substitutes=[],
                reasoning="Discipline row not found at the pinned 0A version.",
            ))
            continue
        risk_level, matched_current, matched_history = _discipline_risk(
            d, current_injuries, history_injuries,
        )
        # §5.6 substitutes — fetch only if elevated/high (perf budget).
        substitutes: list[SubstituteRecommendation] = []
        if risk_level in ("elevated", "high"):
            for s in _load_substitutes(db, did, version_0a)[:3]:
                still_at_risk, overlaps = _substitute_back_check(
                    s["substitute_patterns_text"], current_injuries,
                )
                substitutes.append(SubstituteRecommendation(
                    substitute_discipline_id=s["substitute_id"],
                    substitute_name=s["substitute_name"],
                    fidelity=s["fidelity"],
                    constraints=s["constraints"],
                    category=s["category"],
                    still_at_risk=still_at_risk,
                    still_at_risk_body_parts=overlaps,
                ))
        reasoning = _build_reasoning(
            d["discipline_name"], risk_level, matched_current, matched_history,
        )
        discipline_risks.append(DisciplineRisk(
            discipline_id=did,
            discipline_name=d["discipline_name"],
            risk_level=risk_level,  # type: ignore[arg-type]
            matched_current_parts=matched_current,
            matched_history_parts=matched_history,
            suggested_substitutes=substitutes,
            reasoning=reasoning,
        ))
    # §5.7 HITL determination.
    hitl_required, hitl_items = _determine_hitl(
        current_injuries,
        current_conditions,
        discipline_risks,
        included_discipline_ids,
        gap_disciplines,
    )
    # §8 coaching flags.
    coaching_flags = _emit_coaching_flags(
        discipline_risks,
        current_injuries,
        history_conditions,
        body_part_vocab_misses,
    )
    # Condition-vocab miss audit — defensive against future enum drift.
    condition_vocab_misses: list[str] = []
    return Layer2DPayload(
        etl_version_set=dict(etl_version_set),
        excluded_exercises=excluded,
        accommodated_exercises=accommodated,
        clean_exercise_ids=clean_ids,
        discipline_risk_profiles=discipline_risks,
        coaching_flags=coaching_flags,
        hitl_required=hitl_required,
        hitl_items=hitl_items,
        body_part_vocab_misses=body_part_vocab_misses,
        condition_vocab_misses=condition_vocab_misses,
    )


def _build_reasoning(
    discipline_name: str,
    risk_level: str,
    matched_current: list[MatchedBodyPart],
    matched_history: list[MatchedBodyPart],
) -> str:
    """Templated athlete-facing reasoning string per §5.4 example."""
    if risk_level == "low":
        if not matched_current and not matched_history:
            return f"{discipline_name} carries no overlap with your injury record."
        return f"{discipline_name} carries no current overlap with your injuries."
    parts_current = ", ".join(sorted({m.body_part for m in matched_current}))
    parts_history = ", ".join(sorted({m.body_part for m in matched_history}))
    if risk_level == "informational":
        return (
            f"{discipline_name} carries historical overlap ({parts_history}) "
            "with body parts you've injured in the past. Prevention-focused only."
        )
    if risk_level == "elevated":
        return (
            f"{discipline_name} carries elevated injury risk: current "
            f"{parts_current} injuries overlap with its known patterns. "
            "Substitute disciplines surfaced for consideration."
        )
    # high
    severities = ", ".join(sorted({m.severity for m in matched_current}))
    return (
        f"{discipline_name} carries HIGH injury risk: current {parts_current} "
        f"({severities}) directly overlap with its common injury patterns. "
        "Plan-gen will gate this discipline for review."
    )
