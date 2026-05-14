# Layer 2D — Injury Risk Profile (Query Node)

**Status:** Consolidated spec, first draft 2026-05-10. Designed from scratch per `Batch_C_Done_2D_Kickoff_Handoff.md` agenda.
**Type:** Query node. Pure read, deterministic given inputs, no LLM involvement.
**Supersedes:** the stub `q_layer2d_injury_risk_profile_payload(disciplines, etl_version_set)` in `Layer0_ETL_Spec_v3.md` §5.2. That signature is unbuildable — 2D requires the athlete's injury and condition records as direct inputs. v4 spec rewrite (FC-2) folds in this signature.

---

## 1. Purpose

Given an athlete's injury records (current + history) and health condition records (current + history) plus the set of disciplines they're training, return:

- A categorized view of which exercises in the discipline-relevant pool should be **excluded** (hard contraindication) versus **downgraded** (soft concern, Layer 4 may include with modification)
- A per-discipline **injury-risk profile** with body-part overlap evidence, suggested discipline-level substitutes from `discipline_substitutes`, and severity tier
- **Coaching flags** for surfaces that aren't gates (history-based prevention focus, recurring patterns, multi-body-part load concerns)
- **HITL items** for genuinely ambiguous cases that should block plan-gen until the athlete confirms (post-surgical without clearance, severity mismatch, no-substitute disciplines with elevated risk)

2D's output, combined with 2C's equipment resolution, gives Layer 3 / Layer 4 a complete picture of *what's safe to prescribe* and *which disciplines need adapted programming or replacement*.

## 2. What 2D does NOT do

Clarifying boundaries:

- **Does not decide which disciplines to include.** That's 2A. 2D operates on the already-included set.
- **Does not schedule exercises.** Layer 4 picks what to prescribe; 2D returns flags and exclusions the plan-gen consumes.
- **Does not resolve equipment substitution.** That's 2C.
- **Does not consume 2C output.** Parallel-classifier architecture (Control_Spec §2): 2D queries Layer 0 directly. Layer 3 / 4 cross-references 2C and 2D outputs.
- **Does not modify Layer 0.** Pure read.
- **Does not surface to the athlete directly.** That's Layer 3 / UI. 2D produces structured `coaching_flags` and `hitl_items` for Layer 3 to render.
- **Does not enforce medical clearance.** §A.1 onboarding disclosure covers the legal posture; 2D flags post-surgical or chest-pain conditions but doesn't gate care.
- **Does not run any LLM call.** All matching is rule-based + keyword-pattern, deterministic given inputs.
- **Does not modify the athlete's records.** Status changes (Acute → Recovering → Resolved) happen via §B onboarding edits; 2D reads whatever current state is.

## 3. Function signature

```python
def q_layer2d_injury_risk_profile_payload(
    injuries: list[InjuryRecord],
    conditions: list[HealthConditionRecord],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str]
) -> Layer2DPayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `injuries` | list[InjuryRecord] | Layer 1 §B.1 (Current Injuries + Injury History) | All records, any status. 2D dispatches internally on `.status` (Acute / Recovering / Chronic-Managed / Post-surgical / Structural-Permanent / Resolved). Empty list is valid. |
| `conditions` | list[HealthConditionRecord] | Layer 1 §B.4 (Health Conditions) | All records, any status. 2D dispatches internally on `.status` (Current / History). Empty list is valid. |
| `included_discipline_ids` | list[str] | 2A output | Disciplines the athlete is training. Drives which exercises and risk profiles 2D considers. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Per ETL spec v3 §5.1 Decision 2. Locks Layer 0 version for the plan. |

### Input record shapes

`InjuryRecord` and `HealthConditionRecord` are typed dataclasses defined in `Athlete_Onboarding_Data_Spec_v2.md` §B.1 and §B.4. 2D imports them; their canonical shape (relevant fields only):

```python
@dataclass
class InjuryRecord:
    body_part: str                       # Canonical from body_parts vocab (B.2)
    side: str                            # 'Left' | 'Right' | 'Both' | 'N/A'
    injury_type: str                     # 9-value enum from B.1.1
    severity: str                        # 'Acute' | 'Recovering' | 'Chronic-Managed' | 'Post-surgical' | 'Structural-Permanent' | 'Resolved'
    movement_constraints: list[str]      # Multi-select from B.3 (e.g., 'Pain with wrist extension')
    date_of_onset: date
    status_history: list[dict] | None    # Not consumed by 2D
    notes: str | None                    # Not consumed by 2D

    @property
    def status(self) -> str:
        # 'Current' if severity in {Acute, Recovering, Chronic-Managed, Post-surgical, Structural-Permanent}
        # 'Resolved' if severity == 'Resolved'

@dataclass
class HealthConditionRecord:
    name: str                            # Free text — not consumed by 2D matching, surfaced in flags
    system_category: str                 # Single-select enum (B.4.1) — drives matching against contraindicated_conditions
    status: str                          # 'Current' | 'History'
    notes: str | None                    # Not consumed by 2D
```

### Return type

See §7 below.

## 4. Input validation (preconditions)

Fail-loud on bad inputs. Validation happens before any DB query.

1. `injuries` and `conditions` are lists (may be empty).
2. Each `InjuryRecord.body_part` is a string. Canonical-name validation against `layer0.body_parts.canonical_name` is **soft** — unknown body parts are logged at WARN and skipped from contraindication matching (but still attached to relevant `coaching_flags` so they aren't lost). Don't fail the call on a vocab miss.
3. Each `InjuryRecord.severity` is in the 6-value enum.
4. Each `InjuryRecord.injury_type` is in the 9-value enum (B.1.1) — fail-loud, since this is a closed enum collected at onboarding.
5. Each `HealthConditionRecord.system_category` is in the 11-value enum (B.4.1) — fail-loud, same reason.
6. Each `HealthConditionRecord.status` is `'Current'` or `'History'`.
7. `included_discipline_ids` is a non-empty list of strings.
8. `etl_version_set` contains keys for `0A`, `0B`, `0C` at minimum.

Validation failure → raise `Layer2DInputError`. Plan-gen catches and surfaces a user-facing error. This is NOT a HITL gate — HITL is for ambiguous *content* (e.g., post-surgical without clearance date), not malformed inputs.

**Note on body-part vocab miss:** soft handling rather than fail-loud because B.2's canonical list is athlete-facing and may legitimately need expansion as new injuries enter the system. Treating an unknown body part as fail-loud creates a denial-of-service vector on onboarding evolution.

## 5. Algorithm

### 5.1 Partition records by status

```python
current_injuries  = [i for i in injuries if i.severity != 'Resolved']
resolved_injuries = [i for i in injuries if i.severity == 'Resolved']
current_conditions  = [c for c in conditions if c.status == 'Current']
history_conditions  = [c for c in conditions if c.status == 'History']
```

`current_injuries` and `current_conditions` drive **filtering** (exclusion + downgrade).
`resolved_injuries` and `history_conditions` drive **prevention-focused coaching flags** but never exclude exercises.

### 5.2 Enumerate candidate exercises

Same query universe as 2C §5.2 — exercises mapped to any included discipline via `sport_discipline_bridge` × `sport_exercise_map`. Pulled independently of 2C since the architecture is parallel.

```sql
SELECT
  sxm.exercise_id,
  sxm.exercise_name,
  sxm.exercise_type,
  sxm.sport_name,
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
WHERE sdb.discipline_id = ANY(%(included_discipline_ids)s)
  AND sdb.etl_version = %(version_0a)s
  AND sxm.etl_version = ANY(%(versions_0b)s)
  AND e.etl_version   = ANY(%(versions_0b)s)
  AND sdb.superseded_at IS NULL
  AND sxm.superseded_at IS NULL
  AND e.superseded_at  IS NULL;
```

Notes:
- Same `etl_version = ANY` semantics as 2C — exercises may be at multiple active 0B versions concurrently (`0B-v1.3.1`, `0B-v19.B`, `0B-v19.C`).
- An exercise may appear under multiple included disciplines. Deduplicate by `exercise_id` after the query; track `discipline_ids[]` per exercise for risk attribution.
- D-05 aggregator filter not needed here — 2D doesn't touch `phase_load_allocation`.

### 5.3 Exercise-level contraindication filter

For each candidate exercise, evaluate three signals against the athlete's `current_injuries` and `current_conditions`. Each signal independently determines a verdict; the strongest verdict wins (`exclude` > `downgrade` > `clean`).

#### 5.3.1 Body-part contraindication

```python
def body_part_verdict(exercise, current_injuries) -> tuple[Verdict, list[Evidence]]:
    contra_parts = set(exercise.contraindicated_parts or [])
    if not contra_parts:
        return Verdict.CLEAN, []
    evidence = []
    verdict = Verdict.CLEAN
    for inj in current_injuries:
        if inj.body_part in contra_parts:
            sev_verdict = severity_to_verdict(inj.severity)
            evidence.append(Evidence(
                source='contraindicated_part',
                injury=inj,
                exercise_field='contraindicated_parts',
                matched_value=inj.body_part
            ))
            verdict = max(verdict, sev_verdict)
    return verdict, evidence
```

Set intersection on the canonical body-part vocab. Clean and deterministic.

#### 5.3.2 Condition contraindication

```python
def condition_verdict(exercise, current_conditions) -> tuple[Verdict, list[Evidence]]:
    contra_conds = set(exercise.contraindicated_conditions or [])
    if not contra_conds:
        return Verdict.CLEAN, []
    evidence = []
    verdict = Verdict.CLEAN
    for cond in current_conditions:
        if cond.system_category in contra_conds:
            evidence.append(Evidence(
                source='contraindicated_condition',
                condition=cond,
                exercise_field='contraindicated_conditions',
                matched_value=cond.system_category
            ))
            # Conditions are blanket - same verdict regardless of "severity" since conditions have no severity field
            # Treat as Downgrade by default; Cardiac with high-intensity exercises is Exclude (see §5.3.4)
            verdict = max(verdict, Verdict.DOWNGRADE)
    return verdict, evidence
```

Same set-intersect pattern. Cardiac × high-intensity exercises is a special-case escalation handled in §5.3.4.

#### 5.3.3 Movement-constraint keyword match

The athlete's `InjuryRecord.movement_constraints` (multi-select from B.3) map to keyword bundles. The exercise's `injury_flags_text` is free text that may contain those keywords.

```python
def movement_constraint_verdict(exercise, current_injuries) -> tuple[Verdict, list[Evidence]]:
    if not exercise.injury_flags_text:
        return Verdict.CLEAN, []
    flag_text_lower = exercise.injury_flags_text.lower()
    evidence = []
    verdict = Verdict.CLEAN
    for inj in current_injuries:
        for constraint in inj.movement_constraints or []:
            keywords = MOVEMENT_CONSTRAINT_KEYWORDS.get(constraint, [])
            hits = [kw for kw in keywords if kw.lower() in flag_text_lower]
            if hits:
                sev_verdict = severity_to_verdict(inj.severity)
                evidence.append(Evidence(
                    source='movement_constraint',
                    injury=inj,
                    exercise_field='injury_flags_text',
                    constraint=constraint,
                    matched_keywords=hits
                ))
                verdict = max(verdict, sev_verdict)
    return verdict, evidence
```

The `MOVEMENT_CONSTRAINT_KEYWORDS` table is the B.3 enumeration. Reproduced inline in the code module — single source of truth pending the Layer 0 vocab decision (see §12 open items).

```python
MOVEMENT_CONSTRAINT_KEYWORDS = {
    'Pain with loading':            ['under load', 'heavy load', 'weighted'],
    'Pain with impact':             ['landing', 'impact', 'reactive load'],
    'Pain above specific joint angle': ['above 90', 'full extension', 'at depth'],
    'Pain on descent / eccentric':  ['eccentric', 'descent', 'downhill', 'braking'],
    'Pain on rotation':             ['rotation', 'torque', 'twisting'],
    'Pain with grip / sustained hold': ['grip', 'sustained hold', 'forearm fatigue'],
    'Pain with wrist extension':    ['wrist extension', 'palm-down'],
    'Pain with overhead movement':  ['overhead', 'above shoulder', 'impingement'],
    'Instability':                  ['instability', 'subluxation', 'gives way'],
    'Reduced ROM':                  ['ROM restriction', 'dorsiflexion limited'],
    'Pain at high volume only':    ['sustained', 'repetitive', 'overuse'],
}
```

#### 5.3.4 Severity → verdict mapping

```python
def severity_to_verdict(severity: str) -> Verdict:
    return {
        'Acute':                 Verdict.EXCLUDE,
        'Recovering':            Verdict.DOWNGRADE,
        'Chronic-Managed':       Verdict.DOWNGRADE,
        'Post-surgical':         Verdict.EXCLUDE,   # also triggers HITL clearance gate (§5.7)
        'Structural-Permanent':  Verdict.DOWNGRADE,
        'Resolved':              Verdict.CLEAN,     # current_injuries shouldn't have these, but defensive
    }[severity]
```

**[DECISION POINT — severity → verdict mapping]**

This is judgment-call territory. Defaults above are conservative but plausible. Alternatives Andy may want:
- **More aggressive:** treat `Chronic-Managed` as Clean (athlete already manages it; programming-around-it is the athlete's job). Pro: less plan disruption. Con: misses load-spike risk.
- **Less aggressive:** treat `Acute` as Downgrade. Pro: lets athlete train through. Con: counter to standard injury management.
- **Per-injury-type override:** acute soft tissue stays Exclude; acute bone (stress fracture) is also Exclude; but inflammatory bursitis could be Downgrade. Tracked as 2D-3.

**Recommendation:** ship the conservative mapping above as v1. Revisit after first few athletes generate a-and-b feedback.

#### 5.3.5 Final verdict per exercise

```python
def evaluate_exercise(exercise, current_injuries, current_conditions) -> ExerciseRisk:
    body_verdict, body_ev      = body_part_verdict(exercise, current_injuries)
    cond_verdict, cond_ev      = condition_verdict(exercise, current_conditions)
    move_verdict, move_ev      = movement_constraint_verdict(exercise, current_injuries)
    overall = max(body_verdict, cond_verdict, move_verdict)
    return ExerciseRisk(
        exercise_id=exercise.exercise_id,
        verdict=overall,
        evidence=body_ev + cond_ev + move_ev,
    )
```

Three independent signals; strongest verdict wins. Evidence preserved so Layer 3 can render "*Bench Press excluded because: contraindicated_part 'Wrist' matches your active wrist injury (Recovering, Pain with loading).*"

### 5.4 Discipline-level risk profiling

For each `discipline_id` in `included_discipline_ids`, evaluate injury-pattern overlap against the athlete's current and resolved injury body parts.

Source data: `disciplines.common_injury_patterns TEXT[]` (deployed name; spec was `injury_patterns`). Free-text entries per discipline — see §10 edge cases for the parsing model.

```python
def discipline_risk(discipline, injuries, body_part_keywords) -> DisciplineRisk:
    patterns_text = ' '.join(discipline.common_injury_patterns or []).lower()
    if not patterns_text:
        return DisciplineRisk(
            discipline_id=discipline.discipline_id,
            risk_level=RiskLevel.LOW,
            matched_current_parts=[],
            matched_history_parts=[],
            suggested_substitutes=[],
            reasoning='No injury-pattern data for this discipline.'
        )

    matched_current = []
    matched_history = []
    for inj in injuries:
        keywords = body_part_keywords.get(inj.body_part, [inj.body_part.lower()])
        hits = [kw for kw in keywords if kw.lower() in patterns_text]
        if hits:
            target = matched_current if inj.severity != 'Resolved' else matched_history
            target.append(MatchedBodyPart(
                body_part=inj.body_part,
                side=inj.side,
                severity=inj.severity,
                matched_keywords=hits
            ))

    risk_level = risk_level_from_matches(matched_current, matched_history)
    substitutes = lookup_substitutes(discipline.discipline_id) if risk_level >= RiskLevel.ELEVATED else []
    return DisciplineRisk(
        discipline_id=discipline.discipline_id,
        risk_level=risk_level,
        matched_current_parts=matched_current,
        matched_history_parts=matched_history,
        suggested_substitutes=substitutes,
        reasoning=build_reasoning(...)
    )
```

**Risk-level rubric:**

```python
def risk_level_from_matches(current, history) -> RiskLevel:
    if any(m.severity in {'Acute', 'Post-surgical'} for m in current):
        return RiskLevel.HIGH
    if current:
        return RiskLevel.ELEVATED
    if history:
        return RiskLevel.INFORMATIONAL   # discipline carries known patterns the athlete has had before
    return RiskLevel.LOW
```

### 5.5 Body-part keyword map

The athlete's structured `body_part` (e.g., `'Knee'`) needs to match against the discipline's free-text `common_injury_patterns` (e.g., `'IT Band Syndrome · Plantar Fasciitis · Patellar Tendinopathy · Achilles Tendinopathy · Ankle sprains'`).

Bare substring match misses anatomical synonyms: an athlete with `'Knee'` injury wouldn't match `'Patellar Tendinopathy'` text even though both refer to the same anatomical region.

**v1 approach:** code-side hand-curated synonym map. Built once from inspecting all `common_injury_patterns` text across the 31 disciplines. Below: the AR-relevant subset (~20 body parts that appear in AR's 15 disciplines). Full map covers all 41 B.2 canonical body parts; entries added as new disciplines come online or new athlete injuries surface vocab gaps.

```python
BODY_PART_KEYWORDS = {
    # Foot / Ankle
    'Ankle':           ['ankle', 'lateral ankle', 'ankle sprain', 'ankle torsion'],
    'Plantar fascia':  ['plantar', 'fascia', 'fasciitis'],
    'Achilles':        ['achilles', 'gastroc-achilles', 'achilles tendinopathy'],
    'Foot':            ['foot', 'metatarsal'],

    # Lower leg
    'Calf':            ['calf', 'gastrocnemius'],
    'Soleus':          ['soleus'],
    'Shin':            ['shin', 'shin splints', 'tibia', 'tibial'],
    'Peroneal':        ['peroneal'],

    # Knee
    'Knee':            ['knee', 'patellar', 'patellofemoral', 'tibial-femoral'],
    'Kneecap':         ['kneecap', 'patella', 'patellar'],
    'Meniscus':        ['meniscus', 'meniscal'],
    'ACL':             ['acl', 'anterior cruciate'],
    'PCL':             ['pcl', 'posterior cruciate'],
    'MCL':             ['mcl', 'medial collateral'],
    'LCL':             ['lcl', 'lateral collateral'],

    # Upper leg
    'Quad':            ['quad', 'quadriceps', 'quadricep'],
    'Hamstring':       ['hamstring'],
    'IT band':         ['it band', 'itbs', 'iliotibial', 'it-band'],

    # Hip
    'Hip':             ['hip pain', 'hip joint', 'hip contusion'],
    'Hip flexor':      ['hip flexor'],
    'Glute':           ['glute', 'gluteal', 'hip abductor'],
    'Groin':           ['groin', 'adductor'],
    'TFL':             ['tfl', 'tensor fasciae'],

    # Back
    'Lower back':      ['lower back', 'lumbar', 'low back'],
    'Upper back':      ['upper back', 'thoracic'],
    'SI joint':        ['si joint', 'sacroiliac'],
    'Sciatica':        ['sciatica', 'sciatic'],
    'Spine (general)': ['spine', 'spinal'],

    # Shoulder
    'Shoulder':        ['shoulder', 'shoulder strain', 'shoulder fatigue', 'shoulder dislocation'],
    'Rotator cuff':    ['rotator cuff', 'rotator-cuff', 'swimmer\'s shoulder', 'impingement'],
    'AC joint':        ['ac joint', 'acromioclavicular'],
    'Shoulder blade':  ['shoulder blade', 'scapula'],

    # Arm / Hand
    'Elbow':           ['elbow', 'epicondylitis', 'lateral epicondylitis', 'medial epicondylitis'],
    'Forearm':         ['forearm', 'forearm fatigue'],
    'Wrist':           ['wrist', 'wrist tendinopathy', 'wrist flexor', 'wrist extensor', 'wrist strain'],
    'Hand':            ['hand', 'hand trauma', 'blistered hands'],
    'Bicep':           ['bicep', 'biceps'],
    'Tricep':          ['tricep', 'triceps'],
    'Fingers':         ['finger', 'fingers'],
    'Finger pulley':   ['finger pulley', 'a2 pulley', 'pulley strain'],
    'Thumb':           ['thumb'],

    # Head / Neck
    'Neck':            ['neck', 'cervical', 'neck strain'],
    'Jaw':             ['jaw'],

    # Trunk
    'Rib':             ['rib', 'rib fracture'],
    'Chest':           ['chest', 'sternum'],
}
```

**[DECISION POINT — body-part keyword map location]**

Two paths:

- **(A) Code-side hand-curated map** (drafted above). Built once from corpus inspection; updated as needed. Pro: simple, no new Layer 0 table. Con: not auditable from a query, splits "data" from "code" awkwardly.
- **(B) New Layer 0 column** `disciplines.body_parts_at_risk TEXT[]` populated by ETL or hand-curation from the `common_injury_patterns` text. Pro: queryable, auditable, removes the keyword-fuzzy step. Con: another curation task that competes with `stimulus_components` and `substitute_covers` for FC time. Also: needs maintenance whenever discipline injury patterns change.

**Recommendation:** ship (A) for v1; design (B) as the v2 promotion. The 2D code already isolates the map behind `BODY_PART_KEYWORDS` — promoting to a query later is a swap-in. Tracked as 2D-1.

If (B), the column-population task is roughly equivalent to the `substitute_covers` curation work — ~30 disciplines, structured against the 41 body parts. Could fold into FC-1.

### 5.6 Discipline-level substitution lookup

When a discipline's risk level is `ELEVATED` or `HIGH`, query `discipline_substitutes` for sport-agnostic alternatives:

```sql
SELECT
  substitute_id,
  substitute_name,
  fidelity,
  constraints,
  category,
  substitute_covers
FROM layer0.discipline_substitutes
WHERE target_id = %(discipline_id)s
  AND etl_version = %(version_0a)s
  AND superseded_at IS NULL
ORDER BY fidelity DESC;
```

Returns substitutes ordered by fidelity descending. 2D attaches the top 3 (or all if fewer) to the `DisciplineRisk.suggested_substitutes`.

#### 5.6.1 Substitute back-check

A naive substitute recommendation can recommend a discipline that *also* lists the athlete's at-risk body part in its `common_injury_patterns`. Example: athlete with wrist injury; D-010 Rock Climbing is elevated; D-008a Kayaking is a substitute candidate but also has "Wrist tendinopathy" in its patterns. Surfacing this matters.

For each suggested substitute, re-run §5.4's body-part matching against the substitute's own `common_injury_patterns`. Tag the recommendation with `still_at_risk: bool` and the matched body parts:

```python
@dataclass
class SubstituteRecommendation:
    substitute_discipline_id: str
    substitute_name: str
    fidelity: float
    constraints: str | None
    category: str | None
    still_at_risk: bool                     # True if substitute injury_patterns match athlete's at-risk body parts
    still_at_risk_body_parts: list[str]     # Which body parts overlap
```

Layer 4 uses `still_at_risk` to deprioritize self-defeating substitutes. 2D doesn't filter them out — it tags them. Athlete may still benefit from the substitute even with overlap (lower load on the at-risk part vs. avoidance entirely).

### 5.7 HITL determination

`hitl_required = True` if any of:

1. **Post-surgical injury without clearance date.** `InjuryRecord.severity == 'Post-surgical'` AND `notes` does not contain a parseable clearance date or the notes are empty. Plan-gen must not auto-prescribe under post-surgical state without affirmed clearance.
2. **Cardiac condition × high-load disciplines.** `current_conditions` includes `system_category == 'Cardiac'` AND `included_discipline_ids` intersects high-cardiac-load disciplines (D-001 Trail Running, D-002 Road Running, D-005 Road Cycling, D-006 Mountain Biking, D-022 Uphill Mountain Running, D-023 Downhill Mountain Running, D-028 XC Skiing — anything with sustained Z3+). Surface for athlete confirmation before plan-gen proceeds.
3. **Concussion (current).** `current_conditions` includes `system_category == 'Neurological'` AND `name` contains 'concussion' (case-insensitive). Concussion in current status requires per-stage return-to-load gating that 2D can't auto-resolve.
4. **High-risk discipline with no available substitute.** Any discipline at `RiskLevel.HIGH` whose `discipline_substitutes` lookup returns zero rows. The athlete needs to decide: drop the discipline, accept elevated risk, or wait until injury resolves.
5. **Discipline training gap × injury overlap.** Discipline has a `discipline_training_gaps` row (D-018 Swimrun, D-020 Alpine Descent, D-024 Épée Fencing currently) AND 2D flags it `HIGH` risk. Both gates concurrent → athlete decision.

Items surface as `HitlItem` records (§7). Plan-gen consumes them via Layer 3.

**Coaching flag vs HITL gate:**
- Coaching flag = informational; rendered in plan but doesn't block
- HITL gate = system stops, athlete must respond before Layer 4 runs

Examples that are **coaching flags only**, not HITL:
- Recurring pattern: athlete had IT band history; D-001 includes ITBS → informational flag
- Multi-body-part load concern: 3+ active injuries → "high cumulative load risk" flag
- Discipline elevation without HIGH: D-006 elevated due to lower-back history → coaching flag, plan-gen handles

## 6. Drift items affecting 2D

| ID | Description | Status |
|---|---|---|
| D-02 | `disciplines` deployed has `common_injury_patterns` (spec was `injury_patterns`) and `injury_preceding_behaviors` (spec was `preceding_behaviors`). 2D queries deployed names. | Mitigated — code uses deployed names |
| D-15 | `discipline_substitutes` UNIQUE constraint in deployed includes `substitute_name`, allowing in principle duplicate (target, substitute) with different names. Currently no conflicting rows. | Non-blocking; tighten in FC-1 |
| D-21 (new) | **`health_condition_categories` column name uncertainty.** v3 spec §4.14 / v2 §4.12.2 defines `category_name`; v3 §6.2 validation note references `system_category`. Drift report flagged this table as "no drift" but didn't reconcile the column name. 2D's input validation needs to align with deployed. | **NEW — add to backlog** |
| D-22 (new) | **`exercises.injury_flags_text` keyword matching is heuristic.** Free text in this column is the only source of "movement constraint × exercise" overlap. Keyword matching has known false-negative risk. Promotion to structured `movement_components TEXT[]` column flagged in `Athlete_Onboarding_Data_Spec_v2.md` §B.3 cross-layer note. | **NEW — add to backlog** |
| D-23 (new) | **`disciplines.common_injury_patterns` may benefit from structured `body_parts_at_risk TEXT[]`** companion column (see §5.5 [DECISION POINT B]). Tracked as enhancement, not current bug. | **NEW — add to backlog (Cleanup, not blocker)** |

## 7. Payload schema

```python
@dataclass
class Layer2DPayload:
    etl_version_set: dict[str, str]

    # Exercise-level filtering
    excluded_exercises: list[ExerciseRisk]      # verdict == EXCLUDE
    downgraded_exercises: list[ExerciseRisk]    # verdict == DOWNGRADE
    clean_exercise_ids: list[str]               # verdict == CLEAN (just IDs to keep payload small)

    # Discipline-level risk
    discipline_risk_profiles: list[DisciplineRisk]

    # Coaching flags + HITL
    coaching_flags: list[CoachingFlag]
    hitl_required: bool
    hitl_items: list[HitlItem]

    # Audit
    body_part_vocab_misses: list[str]            # body parts in athlete records not in B.2 canonical
    condition_vocab_misses: list[str]            # categories not in B.4.1

@dataclass
class ExerciseRisk:
    exercise_id: str
    exercise_name: str
    discipline_ids: list[str]                    # Which included disciplines this exercise serves
    verdict: str                                 # 'exclude' | 'downgrade' | 'clean'
    evidence: list[Evidence]                     # Why — for Layer 3 / 4 rendering

@dataclass
class Evidence:
    source: str                                  # 'contraindicated_part' | 'contraindicated_condition' | 'movement_constraint'
    exercise_field: str                          # which exercise column produced the match
    matched_value: str | None                    # the matched token (body part, system category)
    matched_keywords: list[str] | None           # for movement_constraint source
    injury_body_part: str | None                 # which injury record produced it (when source is injury-derived)
    injury_severity: str | None                  # propagated for downstream UI
    condition_category: str | None               # which condition produced it (when source is condition-derived)
    constraint: str | None                       # movement constraint label, when source is movement_constraint

@dataclass
class DisciplineRisk:
    discipline_id: str
    discipline_name: str
    risk_level: str                              # 'low' | 'informational' | 'elevated' | 'high'
    matched_current_parts: list[MatchedBodyPart]  # current injuries overlapping discipline patterns
    matched_history_parts: list[MatchedBodyPart]  # resolved injuries — prevention-focus signal
    suggested_substitutes: list[SubstituteRecommendation]  # empty if risk_level < elevated
    reasoning: str                               # templated athlete-facing text

@dataclass
class MatchedBodyPart:
    body_part: str                               # B.2 canonical name
    side: str                                    # from InjuryRecord
    severity: str                                # from InjuryRecord
    matched_keywords: list[str]                  # which keywords from the keyword map hit

@dataclass
class SubstituteRecommendation:
    substitute_discipline_id: str
    substitute_name: str
    fidelity: float                              # 0.0–1.0
    constraints: str | None                      # discipline_substitutes.constraints
    category: str | None                         # discipline_substitutes.category
    still_at_risk: bool                          # §5.6.1 back-check
    still_at_risk_body_parts: list[str]          # which body parts overlap if still_at_risk

@dataclass
class CoachingFlag:
    flag_type: str                               # see §8
    discipline_id: str | None
    discipline_name: str | None
    message: str                                 # human-readable for Layer 4 to surface
    metadata: dict                               # flag-specific structured data

@dataclass
class HitlItem:
    hitl_type: str                               # 'post_surgical_clearance' | 'cardiac_high_load_review' | 'concussion_current' | 'no_substitute_for_high_risk' | 'gap_x_high_risk_concurrent'
    discipline_id: str | None
    injury: InjuryRecord | None
    condition: HealthConditionRecord | None
    severity: str                                # 'block' (must resolve before Layer 4) | 'warn' (auto-pass with notice if athlete doesn't respond within plan-gen window)
    message: str                                 # human-readable
    suggested_resolutions: list[str]             # e.g., ['Enter clearance date', 'Drop discipline', 'Switch to substitute X']
```

## 8. Coaching flag rules

### 8.1 Elevated discipline risk

Trigger: any discipline at `RiskLevel.ELEVATED` (not HIGH — HIGH goes to HITL items via §5.7 rule 4).

```python
CoachingFlag(
    flag_type='elevated_discipline_risk',
    discipline_id=dr.discipline_id,
    discipline_name=dr.discipline_name,
    message=f"{dr.discipline_name} has elevated injury risk given your current {body_parts_str} injuries. {n_subs} substitute disciplines available.",
    metadata={
        'risk_level': 'elevated',
        'matched_body_parts': [m.body_part for m in dr.matched_current_parts],
        'severity_breakdown': Counter(m.severity for m in dr.matched_current_parts),
        'substitute_count': len(dr.suggested_substitutes),
    }
)
```

### 8.2 Discipline substitution available

Trigger: `DisciplineRisk` at ELEVATED or HIGH AND `suggested_substitutes` non-empty.

```python
CoachingFlag(
    flag_type='discipline_substitution_suggested',
    discipline_id=dr.discipline_id,
    message=f"Consider substituting {dr.discipline_name} with {top_sub.substitute_name} (fidelity {top_sub.fidelity:.0%}) — {top_sub.category}",
    metadata={
        'recommendations': [asdict(s) for s in dr.suggested_substitutes[:3]],
    }
)
```

One flag per elevated/high discipline; Layer 4 may render the top recommendation inline.

### 8.3 Recurring injury pattern (history match)

Trigger: any discipline whose `matched_history_parts` is non-empty AND `matched_current_parts` is empty (history-only signal — prevention focus, not active risk).

```python
CoachingFlag(
    flag_type='recurring_injury_pattern',
    discipline_id=dr.discipline_id,
    message=f"Your history of {body_part} injury overlaps with {dr.discipline_name}'s common injury patterns. Plan-gen will prioritize prevention exercises.",
    metadata={
        'history_body_parts': [m.body_part for m in dr.matched_history_parts],
        'patterns_text_excerpt': discipline_first_pattern_excerpt,
    }
)
```

### 8.4 Multi-body-part load concern

Trigger: `len(current_injuries) >= 3` regardless of which disciplines.

```python
CoachingFlag(
    flag_type='multi_body_part_load_concern',
    discipline_id=None,
    message=f"You have {len(current_injuries)} active injuries. Cumulative load risk is elevated; recovery prioritization may need to exceed typical phase defaults.",
    metadata={
        'injury_count': len(current_injuries),
        'body_parts': [i.body_part for i in current_injuries],
    }
)
```

Threshold rationale: 3+ concurrent injuries is rare and suggests a systemic issue (overtraining, under-recovery) that affects plan design beyond per-discipline filtering.

### 8.5 Condition history informational

Trigger: any `condition.status == 'History'` AND `condition.system_category in {Neurological, Cardiac, Respiratory}` (the high-consequence categories).

```python
CoachingFlag(
    flag_type='condition_history_informational',
    discipline_id=None,
    message=f"History of {cond.name} ({cond.system_category}). Plan-gen will apply prevention-focused programming.",
    metadata={'category': cond.system_category, 'name': cond.name}
)
```

Why this is informational and not gating: history conditions don't actively constrain prescription but they do change the prevention priority (e.g., concussion history → less risky-fall content; cardiac history → cardiac warm-ups maintained even in Build phase).

### 8.6 Body-part vocab miss

Trigger: any `InjuryRecord.body_part` not in `layer0.body_parts.canonical_name`.

```python
CoachingFlag(
    flag_type='body_part_vocab_miss',
    discipline_id=None,
    message=f"Injury record references body part '{bp}' not in canonical vocabulary. Skipped from auto-matching. Consider standardizing the entry.",
    metadata={'unrecognized_body_part': bp}
)
```

System-level signal — flagged so onboarding vocab can evolve.

## 9. Caching & determinism

**Cache key:**

```
(athlete_id, hash(sorted_injuries), hash(sorted_conditions), hash(sorted_included_discipline_ids), hash(etl_version_set))
```

`hash(sorted_injuries)` is a stable hash of the records (sorted by body_part + onset_date) including all relevant fields (body_part, side, severity, type, movement_constraints). Status change → cache miss.

**Invalidation triggers:**

- Any change to athlete's `§B.1 Current Injuries` or `§B.1 Injury History` records (add/edit/resolve) → invalidate all entries for that athlete
- Any change to athlete's `§B.4 Health Conditions` records → invalidate
- 2A output changes (different `included_discipline_ids`) → invalidate
- New ETL run → invalidate all entries with the old `etl_version_set` hash

**Does NOT re-run when:**
- Equipment / locale changes (§J) — that's 2C scope
- Schedule changes (§K) — Layer 4 only
- Nutrition prefs (§F) — 2E
- Movement Constraints definitions change (B.3 enum) — would re-run on full re-deploy, not per-athlete

**Sensitive data handling note:** caching keyed by hash, not by raw values. On-disk cache (if added) stores hashes only; cache value is the payload but evicted on any record change. Memory cache acceptable for transient use. No third-party telemetry on injury data.

**Latency target:** <500ms per call.

## 10. Edge cases

| Case | Behavior |
|---|---|
| Empty `injuries` AND empty `conditions` | Fast path — no exclusions, all disciplines `RiskLevel.LOW`, empty flags, `hitl_required=False`. |
| Empty `injuries`, non-empty `conditions` | Skip body-part matching; run condition matching only. Discipline risks all LOW (no body-part overlap source). |
| `included_discipline_ids` is empty | Validation failure (§4 precondition 7). |
| Discipline with no `common_injury_patterns` data (NULL or empty) | §5.4 returns `RiskLevel.LOW` with reasoning text noting the data gap. Don't fail. |
| Discipline with `common_injury_patterns` but no patterns match athlete's body parts | `RiskLevel.LOW`, empty matched parts. |
| Injury body part not in B.2 canonical | Skip from matching, log vocab miss (§8.6), include in `body_part_vocab_misses[]` audit field. Continue with other matches. |
| Injury body part = `'Spine (general)'` | Treated as canonical match for spine-related text. Substring 'spine' or 'spinal' in patterns text triggers. Less precise than Lower back / Upper back / SI joint — flagged in coaching message. |
| Movement constraint not in B.3 enum | Skip from matching, log warning. |
| Condition system category not in B.4.1 enum | Validation failure (§4 precondition 5) since enum is closed. |
| Athlete with single injury, single side (e.g., Left wrist), exercise contraindicates the body part regardless of side | Exclude. Spec does not currently consider side for exercise contraindication — `contraindicated_parts` is body-part only, no side. Tracked as future enhancement. |
| Athlete with bilateral injury (Side='Both') | Same as side-specific from 2D's perspective. Plan-gen may use side for in-plan modifications (e.g., single-arm work on uninjured side). |
| Discipline with elevated risk but `discipline_substitutes` lookup returns zero rows | If `RiskLevel.ELEVATED`: coaching flag noting no substitute available. If `RiskLevel.HIGH`: HITL item per §5.7 rule 4. |
| Substitute's own injury patterns also match the athlete's body parts | `still_at_risk=True`, listed body parts attached. Recommendation surfaced anyway (athlete decides). |
| Athlete has Post-surgical injury with no clearance notes | HITL item with `severity='block'`, `hitl_type='post_surgical_clearance'`. Plan-gen waits. |
| Athlete has Post-surgical injury WITH clearance notes mentioning a date | HITL item with `severity='warn'` — surfaces for athlete review, but doesn't block. Plan-gen proceeds with appropriate caution flags. |
| Athlete has current Cardiac condition + Trail Running in disciplines | HITL item per §5.7 rule 2. Plan-gen waits. |
| Athlete has Resolved concussion in injury history (modeled instead as B.4 History) | NOT in injuries list — concussions per §B.4 convention live as Neurological condition with Status=History. 2D treats as condition history, fires §8.5 informational flag. |
| Discipline appears under multiple included disciplines per exercise | Exercise's `discipline_ids[]` lists all; verdict evaluated once on the exercise; counted in all relevant disciplines for risk profiling. |
| Athlete history references body part not in B.2 (vocab evolution) | Same as current vocab miss — log + skip + flag. |

## 11. Performance budget

Single query for exercise universe + single query per elevated discipline for substitutes.

For AR baseline (15 disciplines, ~211 v19 exercises):
- §5.2 exercise query: 1 JOIN, indexed. <100ms.
- §5.3 per-exercise verdict: 3 set ops + keyword loop per record. With ~3 active injuries × 11 movement constraints, total <50ms across all 211 exercises.
- §5.4 per-discipline risk: keyword scan over 15 × ~5 patterns each. <20ms.
- §5.5 body-part keyword map: in-memory dict. ~0ms.
- §5.6 substitutes: up to ~15 queries × indexed lookup. <100ms in serial; could parallelize.
- Aggregation + coaching flags + HITL: <30ms.
- Serialization: <50ms.

**Total: ~350ms.** Within 500ms latency target.

If the athlete has many active injuries (5+) or many included disciplines (20+), keyword-matching scales linearly. Still well within budget for realistic loads.

## 12. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| 2D-1 | **Body-part keyword map location** (§5.5 decision point) — code-side hand-curated map vs. `disciplines.body_parts_at_risk TEXT[]` column | Andy / FC | Recommend ship (A) v1, design (B) for v2 |
| 2D-2 | **Movement-constraint keyword map location** — code-side (B.3 enum mirror) vs. Layer 0 vocab table | Andy / FC | Same pattern as 2D-1; recommend code-side for v1 |
| 2D-3 | **Severity → verdict mapping** (§5.3.4 decision point) — defaults are conservative; Andy may want per-injury-type override or different aggression | Andy | Recommend ship defaults; iterate after first athletes |
| 2D-4 | **Per-injury-type filter aggressiveness** — same data (injury_type from B.1.1) could inform finer-grained verdict (e.g., tendinopathy = downgrade by default, stress fracture = exclude even when Recovering) | Future | Defer until v1 produces feedback |
| 2D-5 | **`health_condition_categories` column name reconciliation** — spec v3 §4.14 references `category_name`; v3 §6.2 validation references `system_category`. Deployed name uncertain. | FC-1 | Backlog item D-21 |
| 2D-6 | **`exercises.injury_flags_text` → structured `movement_components TEXT[]`** — referenced as cross-layer enhancement in `Athlete_Onboarding_Data_Spec_v2.md` §B.3 | Future Layer 0 batch | Backlog item D-22 |
| 2D-7 | **Side-aware contraindication** — current `exercises.contraindicated_parts` has no side dimension. Future: `contraindicated_parts JSONB` with `{body_part, side}` shape. | Future | Defer |
| 2D-8 | **HITL item severity model** — current spec uses `block` / `warn`. Layer 3 design will need to consume both. Align with Layer 3 spec when drafted. | Layer 3 design | Forward reference |
| 2D-9 | **Concussion clearance protocol** — currently HITL-blocks for current concussion. Specific return-to-load protocol per-stage is out of scope for 2D; needs explicit Layer 4 hook. | Layer 4 design | Forward reference |
| 2D-10 | **Post-surgical clearance date parsing** — §5.7 rule 1 mentions "parseable clearance date" in notes. Notes are free text; structured `cleared_at: date` field on InjuryRecord would be cleaner. | Layer 1 onboarding | Forward reference; add to onboarding spec |

## 13. Test scenarios

These aren't unit tests yet — they're integration scenarios 2D must handle correctly. Spec'd here so test coverage is unambiguous when written.

### 13.1 Andy's baseline — left wrist injury, no conditions

Inputs:
- `injuries = [InjuryRecord(body_part='Wrist', side='Left', injury_type='Tendinopathy / overuse', severity='Chronic-Managed', movement_constraints=['Pain with wrist extension', 'Pain with loading'], date_of_onset=..., notes='Painful and weak with wrist extension; pushups require fist position.')]`
- `conditions = []`
- `included_discipline_ids = [D-001, D-002, D-003, D-005, D-006, D-007, D-008a, D-008b, D-010, D-011, D-013, D-014, D-015, D-016]` (AR's 14 base disciplines, no whitewater since chronic-managed wrist limits Class III)

Expected:
- **Excluded exercises:** any exercise with `'Wrist'` in `contraindicated_parts` OR `injury_flags_text` containing 'wrist extension' / 'palm-down' / 'palm-down' under load — including standard pushup, dips, plank-on-palms, bench press (the last is borderline — wrist supports load only at neutral). Verdict for Chronic-Managed = Downgrade default, so technically these would be downgrades not excludes per §5.3.4. **Wait**: §5.3.4 maps Chronic-Managed → DOWNGRADE. So most wrist-flagged exercises would be downgraded, not excluded. This is the right behavior — Andy's wrist is workable with modifications (fist pushups, etc.), not zero-loadable.
- **Downgraded exercises:** pushups, planks-on-palms, bench press, dips, pike pushups — all wrist-loading exercises. Layer 4 then substitutes fist pushups, planks-on-fists, neutral-grip DB press.
- **Discipline risks:**
  - D-007 Packrafting: ELEVATED (matches 'wrist tendinitis' in patterns)
  - D-008a Kayaking — Flat-water: ELEVATED (matches 'wrist tendinopathy')
  - D-008b Kayaking — Whitewater: ELEVATED (D-008a patterns inherited + wrist injury risk under bracing)
  - D-010 Rock Climbing: ELEVATED (matches 'wrist flexor/extensor strain')
  - D-001 Trail Running: LOW (no wrist patterns)
  - D-002 Road Running: LOW
  - D-003 Hiking: LOW (shoulder/trap fatigue from pack but not wrist-specific)
  - D-005 Road Cycling: LOW (numbness in hands listed but not wrist-specific)
  - D-006 Mountain Biking: ELEVATED — wait, MTB patterns are "Hand/wrist numbness" which substring-matches both 'hand' and 'wrist'. Reasonable elevation.
  - D-011 Abseiling: LOW (rope burns on brake hand, not wrist-specific)
  - D-013 Orienteering: LOW
  - D-014 Swimming: LOW (shoulder-specific patterns)
  - D-015 Snowshoeing: LOW
  - D-016 Mountaineering: LOW
- **Substitutes:** for the 5 elevated disciplines, queries `discipline_substitutes`. e.g., D-010 might return D-007 / D-011 / strength variants. Several substitutes will likely back-check as `still_at_risk=True` (paddle disciplines all hit wrist). Layer 4 handles the gap.
- **HITL:** False — no post-surgical, no Cardiac, no current concussion, no HIGH-without-substitute.
- **Coaching flags:** elevated_discipline_risk × 5 (one per elevated), discipline_substitution_suggested × 5, possibly multi_body_part_load_concern=False (only 1 injury).

### 13.2 Post-surgical scenario

Inputs:
- `injuries = [InjuryRecord(body_part='Knee', side='Right', injury_type='Post-surgical', severity='Post-surgical', movement_constraints=['Pain above specific joint angle', 'Pain with impact'], date_of_onset=2026-03-15, notes='ACL reconstruction')]`
- (No clearance date in notes)
- `conditions = []`
- 14 AR disciplines included

Expected:
- HITL item `post_surgical_clearance` with `severity='block'`. Layer 4 will not run.
- Until clearance: excluded exercises = all knee-contraindicated exercises (lots — squats, lunges, jumps).
- Discipline risks all D-XXX with knee in patterns elevated to HIGH (D-001, D-002, D-003, D-006, D-022, D-023 — most foot/cycling disciplines).
- Multiple substitutes for many; HITL takes precedence.

### 13.3 Concussion history

Inputs:
- `injuries = []`
- `conditions = [HealthConditionRecord(name='Concussion (2024)', system_category='Neurological', status='History')]`
- 14 AR disciplines

Expected:
- No exclusions (no current contraindications).
- No discipline risk elevations (no body-part overlap).
- Coaching flag `condition_history_informational` for the Neurological history.
- `hitl_required=False` — history-only is informational, not gating.

### 13.4 Current asthma (Respiratory, Current)

Inputs:
- `injuries = []`
- `conditions = [HealthConditionRecord(name='Mild EIB', system_category='Respiratory', status='Current')]`
- 14 AR disciplines

Expected:
- Excluded/downgraded exercises: any with `'Respiratory'` in `contraindicated_conditions` — none expected by default in v19 (Cardiac is more commonly flagged), but if an exercise has it (e.g., max-effort altitude simulation), downgraded.
- No discipline risk elevations from body parts (no injuries).
- No HITL items (asthma current isn't in §5.7 list — Cardiac is the high-consequence current condition gate).
- Coaching flag: none specific. Plan-gen handles intensity management via Layer 4 rules (out of 2D scope).
- *Reasonable concern*: should Respiratory current be a soft HITL surface for high-intensity disciplines? Tracked as 2D-3 follow-up.

### 13.5 Clean baseline — no injuries, no conditions

Inputs:
- `injuries = []`
- `conditions = []`
- 14 AR disciplines

Expected:
- All disciplines `RiskLevel.LOW`.
- Empty `excluded_exercises`, `downgraded_exercises`, `coaching_flags`, `hitl_items`.
- `hitl_required=False`.
- Fast path through algorithm (§10 edge case 1).

### 13.6 Multi-injury cumulative load

Inputs:
- `injuries = [Wrist (Recovering), Lower back (Chronic-Managed), Achilles (Recovering)]`
- `conditions = []`
- 14 AR disciplines

Expected:
- Multiple discipline elevations (D-007, D-008a, D-010 from wrist; D-001 from Achilles; multiple from lower back).
- `multi_body_part_load_concern` coaching flag fires (3 active injuries).
- Many downgraded exercises (wrist + Achilles overlap nearly all weight-bearing AR exercises).
- `hitl_required=False` unless any single discipline hits HIGH without substitute. Conservative: doesn't auto-gate but produces a content-heavy plan with caveats.

### 13.7 D-018 Swimrun gap × high risk

Inputs:
- `injuries = [Shoulder (Acute)]`
- `conditions = []`
- `included_discipline_ids = [D-001, D-004, D-018, ...]`

Expected:
- D-018 Swimrun: HIGH (shoulder patterns include shoulder overuse, paddle-required compensation).
- D-018 has `discipline_training_gaps` entry — no clean single substitute.
- HITL item `gap_x_high_risk_concurrent` per §5.7 rule 5.
- Layer 4 doesn't run until athlete decides: drop D-018, multi-substitute composition, or wait for shoulder resolution.

## 14. Gut check

**What this spec gets right:**
- Algorithm fully specified — three independent verdict sources, no ambiguity on combination order.
- Decision points called out inline (severity mapping, body-part keyword map location, movement-constraint keyword map location) instead of hidden in code.
- Discipline-level risk + substitute back-check is the kind of cross-cutting reasoning that's easy to miss; the spec makes it explicit.
- Body-part keyword map drafted inline so reviewers can spot gaps — not just a "to be curated later" stub.
- Test scenarios anchored in Andy's actual wrist injury — concrete enough to drive integration test fixtures.
- HITL surface tied to specific, named triggers; not a vague "ambiguous case" hand-wave.
- Edge cases enumerated for vocab evolution, side handling, history-only matches.

**Risks:**
- **The body-part keyword map is the biggest fragility.** Hand-curated mapping has known false-negative risk. If athlete logs "Knee — patellar tendon" as a body part free-text adjacent to the canonical "Knee", a strict match misses but the underlying mechanism is the same as 'patellar' in patterns. v1 mitigates by mapping `Knee` → `['knee', 'patellar', ...]`, but new injury types may introduce vocab gaps. Mitigation: §8.6 vocab miss flag surfaces these for curation.
- **Severity → verdict defaults are judgment calls.** I've chosen conservative (Acute=Exclude, Recovering=Downgrade, Chronic-Managed=Downgrade). Andy may want different. The mapping is one constant in code; easy to change. But the defaults shape the entire athlete experience.
- **Movement-constraint keyword matching against `injury_flags_text` is heuristic.** This is the weakest signal in §5.3. Better long-term: structured `movement_components` field on exercises (2D-6 / D-22). Until then, false negatives (real concerns missed) are more likely than false positives (over-restrictive).
- **`health_condition_categories` column name uncertainty** — caught D-21 but didn't resolve. 2D code will have to handle whichever name is deployed; ETL spec drift should be reconciled before implementation.
- **No side-awareness on exercise contraindication** (2D-7). For Andy specifically (left wrist), this means right-hand-only pushups would still be excluded under 2D's current logic. Layer 4 may need to render "modified for left wrist" — out of 2D scope but worth flagging.

**What might be missing:**
- **Cumulative-load HITL trigger.** §5.7 doesn't gate on multi-injury load count, only on individual injury severity. 5+ active injuries with multiple HIGH disciplines = a plan-gen problem 2D currently surfaces as a coaching flag, not HITL. Defensible — Layer 3 may decide to escalate to HITL based on aggregate.
- **Medication interactions.** §B Current Medications (per Onboarding Spec) includes beta blockers, NSAIDs, etc. Drug-side effects on plan design (RPE-not-HR for beta blockers, injury-masking for NSAIDs) aren't currently in 2D. They probably belong in 2D or a sibling Layer 2 node — TBD with Layer 3 / Layer 4 design.
- **Sex-specific injury risk.** Some patterns (ACL tear rate, stress fracture in low-energy-availability athletes) are sex-modulated. Not in 2D currently; tracked as a future enhancement when discipline patterns get structured.
- **Sport-context modulation.** The current `discipline_substitutes` lookup is sport-agnostic. A wrist-injured AR athlete might substitute D-008a Kayaking with strength work; a non-AR athlete might substitute with cycling. Currently 2D returns fidelity-ordered candidates regardless of athlete sport. Layer 4 has the context to filter further.

**Best argument against this spec as drafted:**
The body-part keyword map is essentially "data masquerading as code." Hand-curated lookup tables in code are common but they pollute the deterministic-data / deterministic-code boundary the system otherwise maintains. The Project_Backlog backlog item D-23 (promoting to `disciplines.body_parts_at_risk`) addresses this, but until then the spec is shipping a hand-curated thing pretending to be an algorithm.

Counter: every alternative for v1 is worse. Pre-populating a column means another curation pass that competes with FC-1. Using an LLM violates the standing protocol and adds latency without clearly better results. Keyword maps in code are a known pattern in real systems — the spec at least makes it explicit and auditable rather than hidden in implementation. Promote to data later; ship now.

---

*End of spec. Open items 2D-1, 2D-2, 2D-3 need Andy's decisions before implementation. Drift items D-21, D-22, D-23 added to Project_Backlog.md.*
