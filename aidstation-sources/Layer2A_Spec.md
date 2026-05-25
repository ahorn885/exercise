# Layer 2A — Discipline Classifier (Query Node)

**Status:** Consolidated spec, backfilled 2026-05-10 from design notes in `Layer1_2B_Done_2C_Kickoff_Handoff.md` §"Node 2A — Discipline Classifier — LOCKED" and predecessor handoffs.
**Type:** Query node. Pure read, deterministic given inputs, no LLM involvement.
**Predecessor decisions:** All design calls from the 2A locking session are folded in. Drift items D-05 and D-17 incorporated.

---

## 1. Purpose

Given an athlete's stated target sport (e.g., "Adventure Racing", "Triathlon (Standard / Olympic)"), resolve to the canonical set of disciplines that sport involves, with role assignments, load weights, conditional flags, training gaps, and athlete-facing rationale. This is the **first node** of every plan-generation pipeline — its output drives which exercise pool, terrain set, phase load, and substitution map every downstream node operates against.

For AR specifically: input "Adventure Racing" → output the AR discipline set (D-001 Trail Running through D-018 Mountaineering) with their AR-specific roles (Primary / Secondary / Minor / *Conditional).

## 2. What 2A does NOT do

Clarifying boundaries:

- **Does not enumerate exercises.** That's 2C. 2A returns disciplines only.
- **Does not resolve terrain.** That's 2B. 2A doesn't touch `terrain_types` or `terrain_gap_rules`.
- **Does not resolve equipment.** That's 2C.
- **Does not check injury / health filters.** That's 2D.
- **Does not run any LLM call.** All operations are deterministic table joins + rule application. Dropped from LLM under the §"Standing protocol" (query-vs-LLM) test.
- **Does not resolve sport name aliases.** Input is a structured enum from `§H.2 Target Sport / Format`. No NL parsing.
- **Does not derive `stimulus_components` per discipline.** 2C and 2D query that field directly when needed. Passing through 2A would bundle data 2A doesn't own.

## 3. Function signature

```python
def q_layer2a_discipline_classifier_payload(
    framework_sport: str,
    athlete_discipline_overrides: dict[str, dict] | None,
    estimated_race_duration_hours: float | None,
    team_format: str | None,
    etl_version_set: dict[str, str]
) -> Layer2APayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `framework_sport` | str | `§H.2 Target Sport / Format` | Canonical name. For AR: `"Adventure Racing"`. For other sports, see **§5.1 sport naming caveat (D-17)**. |
| `athlete_discipline_overrides` | dict\|None | `§C Discipline Weighting` (athlete overrides) | Optional. Athletes can override system-default weights or exclude `*Conditional` disciplines. Shape: `{discipline_id: {weight: float, included: bool}}`. |
| `estimated_race_duration_hours` | float\|None | `§H.2 Estimated Duration` | Used for certain sleep-deprivation flags. |
| `team_format` | str\|None | `§H.2 Team Format` | Affects relay-leg discipline selection for relay sports. AR is not a relay sport — typically None for AR. |
| `etl_version_set` | dict[str,str] | Plan-gen pin | Per ETL spec v3 §5.1 Decision 2. Locks Layer 0 version for the plan. |

### Return type

See §7 below.

## 4. Input validation (preconditions)

1. `framework_sport` non-empty string. (No alias resolution. If athlete picked from the canonical sport list in `§H.2`, the value arrives clean.)
2. `etl_version_set` contains keys for `0A`, `0B`, `0C` at minimum.
3. `estimated_race_duration_hours` if provided, is positive numeric.
4. `team_format` if provided, matches one of the known enums (Solo / Unified / Relay) — vocabulary owned by `§H.2`.

Validation failure → raise `Layer2AInputError`. Plan-gen catches and surfaces a user-facing error.

## 5. Algorithm

### 5.1 Sport naming caveat (D-17)

For AR, `framework_sport = "Adventure Racing"` matches in both `sport_discipline_map` (top-level) and `phase_load_allocation` (sub-format). No naming mismatch. Algorithm proceeds straightforward.

For non-AR sports with sub-format expansions — Triathlon, Skimo, Long Distance / Endurance Cycling, Canoe / Kayak Marathon, Open Water Marathon Swimming — `sport_discipline_map` uses the top-level name ("Triathlon") and `phase_load_allocation` uses sub-format ("Triathlon (Standard / Olympic)"). The input `framework_sport` for non-AR sports must be the sub-format name. The §H.2 onboarding spec must collect sub-format up front (via race-goal capture or explicit picker). Tracked as D-17 in `Project_Backlog.md`.

**For v1 implementation:** assume input is whatever name appears in `phase_load_allocation` (the more specific table). For AR this is "Adventure Racing"; for Triathlon this is e.g. "Triathlon (Standard / Olympic)". `sport_discipline_map` lookups for non-AR sports require an additional step to strip the sub-format suffix and match the top-level name — implementation detail handled in §5.2.

### 5.2 Primary query — disciplines for sport

```sql
WITH sport_disciplines AS (
  SELECT
    sdm.discipline_id,
    sdm.discipline_name,
    sdm.applicability,
    sdm.role,
    sdm.race_time_pct_low,
    sdm.race_time_pct_high,
    sdm.sport_specific_context,
    sdm.phase_load_text
  FROM layer0.sport_discipline_map sdm
  WHERE sdm.sport_name = %(top_level_sport)s
    AND sdm.applicability = 'INCLUDED'
    AND sdm.etl_version = %(version_0a)s
    AND sdm.superseded_at IS NULL
)
SELECT
  sd.*,
  pla.base_pct_low,    pla.base_pct_high,
  pla.build_pct_low,   pla.build_pct_high,
  pla.peak_pct_low,    pla.peak_pct_high,
  pla.taper_pct_low,   pla.taper_pct_high,
  pla.role            AS pla_role,
  pla.notes_conditions,
  dtg.gap_type,
  dtg.notes           AS gap_notes,
  dtg.multi_substitute_candidate
FROM sport_disciplines sd
LEFT JOIN layer0.phase_load_allocation pla
  ON pla.sport_name = %(framework_sport)s              -- sub-format-named where applicable
 AND pla.discipline_id = sd.discipline_id
 AND pla.etl_version = %(version_0a)s
 AND pla.superseded_at IS NULL
 AND pla.discipline_name NOT LIKE '%%WEEKLY TOTAL%%'   -- D-05 STANDING FILTER (aggregator rows polluting PLA)
LEFT JOIN layer0.discipline_training_gaps dtg
  ON dtg.discipline_id = sd.discipline_id
 AND dtg.etl_version = %(version_0a)s
 AND dtg.superseded_at IS NULL;
```

**Key points:**

- `top_level_sport` = if AR or any non-sub-format sport, same as `framework_sport`. If sub-format, strip the parenthetical (e.g., `"Triathlon (Standard / Olympic)"` → `"Triathlon"`). Code-side regex.
- `framework_sport` for the PLA join uses the full sub-format name — that's how PLA indexes.
- **D-05 standing filter** applied on PLA: `AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`. Mandatory per drift backlog.
- `applicability = 'INCLUDED'` filter on SDM matches the spec §4.4 rule — EXCLUDED rows are loaded for documentation but not consumed at runtime.
- LEFT JOINs on PLA and DTG — a discipline may legitimately have no phase-load row for a specific sub-format sport, and most disciplines don't have a training gap entry.
- `default_inclusion` is **not** a column on `layer0.phase_load_allocation` (an earlier draft of this spec referenced `pla.default_inclusion`; the column was never added). 2A derives it code-side from `notes_conditions` text per §5.3 — rows whose `notes_conditions` starts with `*CONDITIONAL` map to `'prompt_required'`; otherwise `'included'`. The typed payload field (`SportDisciplineRow.default_inclusion`) is populated from this derivation.

### 5.3 Conditional resolution

After the query, each discipline is one of:

- **Unconditionally included** — `role` does not contain `(*Conditional)` and `notes_conditions` doesn't start with `*CONDITIONAL`. Discipline is in.
- **Conditional — athlete-opt-in** — `default_inclusion = 'prompt_required'`. Plan-gen prompts the athlete; 2A surfaces this in `hitl_required` (see §8). An explicit `athlete_discipline_overrides` entry resolves it to `included`/`excluded` (`conditional_resolution = 'athlete_opt_in'`).
  - **Relay-only legs** — depend on `team_format`. Not applicable to AR; relay-leg filtering deferred (no current consumer sport).

> **Race-rule auto-resolution retired (2026-05-25).** Earlier revisions auto-included/excluded the navigation discipline (D-015) from a `navigation_required` input. That input was removed end-to-end; the navigation discipline is now a plain `*Conditional` (athlete opt-in like any other), and the `race_rule_auto_in`/`race_rule_auto_out` resolutions + the `conditional_auto_resolved` flag no longer exist.

The detailed conditional rule table per sport lives in code, not the data model. Reasoning: rules are tightly coupled to race-specific business logic and easier to maintain in versioned code than in a normalized table. (If this gets unwieldy, candidate for a future `discipline_conditional_rules` table — tracked as future open item.)

### 5.4 Discipline weighting

Each discipline gets a `load_weight` computed as:

```python
def compute_load_weight(discipline, overrides):
    # System default: midpoint of race_time_pct band
    default_weight = (discipline.race_time_pct_low + discipline.race_time_pct_high) / 2 if discipline.race_time_pct_low else None
    
    # Athlete override wins if present
    if overrides and discipline.discipline_id in overrides:
        ov = overrides[discipline.discipline_id]
        if 'weight' in ov:
            return WeightResult(value=ov['weight'], source='athlete_override', system_default=default_weight)
    
    return WeightResult(value=default_weight, source='system_default', system_default=default_weight)
```

The output payload returns BOTH system default AND athlete override (when present), so Layer 4 can render explanations like "Your Trail Running weight is 28% (you adjusted up from system default 22%)."

### 5.5 Rationale text generation

Each discipline gets a `rationale` string for athlete-facing display. Templated, not LLM-generated:

```
"{discipline_name} is a {role_modifier} discipline of {sport_name}. {role_context}"
```

Where:
- `role_modifier` = `"core"` for Primary, `"supporting"` for Secondary, `"minor"` for Minor.
- `role_context` = role-specific paragraph from a code-side template library; integrates `sport_specific_context` field when non-NULL.

Example: `"Trail Running is a core discipline of Adventure Racing. It accounts for an estimated 25–40% of race time and forms the foundation of cardiovascular conditioning for the sport."`

**Open item B (from 2A locking handoff):** rationale text quality must meet athlete-facing bar — feeds the plan confirmation UI step. "Default included for Adventure Racing" is not good enough. Treat templates as content that needs review.

### 5.6 HITL gate determination

`hitl_required = True` if any of:

- A `default_inclusion = 'prompt_required'` discipline can't be resolved from event context (athlete didn't pre-answer)
- `unresolved_flags[]` non-empty (athlete selected disciplines not found in canonical framework)

HITL does NOT fire on:
- Conditional disciplines that auto-resolve from race parameters (those are handled deterministically)
- Training gaps alone (gaps surface as informational warnings, not gates)

## 6. Drift items affecting 2A

| ID | Description | Status |
|---|---|---|
| D-05 | `phase_load_allocation` has 33 aggregator rows polluting the table. **Standing filter `AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`** is applied in §5.2 query. Mandatory until ETL fix lands. | Mitigated by filter |
| D-08 | 3 rows missing in `sport_discipline_map` (LDC -2, Triathlon -1). AR has all 15 disciplines. | Non-blocking for AR |
| D-17 | Sport naming convention mismatch — AR uses same name in both tables, but non-AR sports use top-level in SDM and sub-format in PLA. Handled in §5.1 by strip-and-re-lookup logic. | Workaround in place; design owner is Layer 1 race-goal capture |

## 7. Payload schema

```python
@dataclass
class Layer2APayload:
    framework_sport: str                 # Echoed input
    etl_version_set: dict[str, str]
    disciplines: list[Layer2ADiscipline]
    training_gaps_summary: TrainingGapsSummary
    hitl_required: bool
    unresolved_flags: list[UnresolvedFlag]
    coaching_flags: list[CoachingFlag]
    rationale_metadata: RationaleMetadata

@dataclass
class Layer2ADiscipline:
    discipline_id: str
    discipline_name: str
    inclusion: str                       # 'included' | 'excluded' | 'prompt_required'
    role: str                            # 'Primary' | 'Secondary' | 'Minor' | 'Technical' (with *Conditional suffix preserved)
    is_conditional: bool
    conditional_resolution: str | None   # 'athlete_opt_in' | None
    load_weight: WeightResult
    race_time_pct_low: float | None
    race_time_pct_high: float | None
    sport_specific_context: str | None
    phase_load: PhaseLoadBands | None    # Bands per phase from PLA; None if no PLA row
    sleep_deprivation_relevant: bool
    training_gap: TrainingGap | None     # Populated if discipline_training_gaps row exists
    rationale: str                       # Templated athlete-facing text

@dataclass
class WeightResult:
    value: float | None
    source: str                          # 'system_default' | 'athlete_override'
    system_default: float | None         # Always populated for transparency

@dataclass
class PhaseLoadBands:
    base_low: float | None
    base_high: float | None
    build_low: float | None
    build_high: float | None
    peak_low: float | None
    peak_high: float | None
    taper_low: float | None
    taper_high: float | None
    notes_conditions: str | None
    default_inclusion: str               # 'included' | 'excluded' | 'prompt_required'

@dataclass
class TrainingGap:
    gap_type: str
    notes: str
    multi_substitute_candidate: bool

@dataclass
class TrainingGapsSummary:
    flagged_count: int
    any_no_substitute: bool              # True if any gap has gap_type indicating no substitute
    any_multi_substitute_candidate: bool

@dataclass
class UnresolvedFlag:
    raw_input: str
    suggested_match: str | None          # Best fuzzy match if any
    severity: str                        # 'error' | 'warning'

@dataclass
class CoachingFlag:
    flag_type: str                       # see §8
    discipline_id: str | None
    message: str
    metadata: dict

@dataclass
class RationaleMetadata:
    template_version: str                # For audit
    generated_at: str                    # ISO timestamp; useful for cache invalidation
```

## 8. Coaching flag rules

Three triggers in 2A:

### 8.1 Training gap surfaced

Any included discipline with a `discipline_training_gaps` entry. Surfaces the gap as informational warning so downstream nodes (especially Layer 4 plan-gen) can render to athlete.

```python
CoachingFlag(
    flag_type='training_gap',
    discipline_id=d.discipline_id,
    message=f"{d.discipline_name} has a known training gap: {d.training_gap.notes}",
    metadata={
        'gap_type': d.training_gap.gap_type,
        'multi_substitute_candidate': d.training_gap.multi_substitute_candidate
    }
)
```

For AR specifically: D-018 Mountaineering does not currently have a `training_gaps` entry, but D-022 Alpine Descent and D-025 Épée Fencing do (not AR-relevant). For AR-relevant sports later, this flag is the primary signal.

### 8.2 Conditional discipline auto-resolved — RETIRED (2026-05-25)

This flag fired when a `*Conditional` discipline was resolved by race rule (the `navigation_required`-driven D-015 auto-in/out). That input was removed end-to-end; conditionals now resolve only via athlete prompt or explicit override, so this flag type is no longer emitted.

### 8.3 Override divergence

If athlete override deviates from system default by more than 50%, surface a flag so plan-gen can explain.

```python
CoachingFlag(
    flag_type='weight_override_divergence',
    discipline_id=d.discipline_id,
    message=f"Your {d.discipline_name} weight of {ov}% is significantly higher/lower than system default of {default}%.",
    metadata={'override_pct': ov, 'default_pct': default, 'divergence': abs(ov - default)}
)
```

## 9. Caching & determinism

**Cache key:**
```
(athlete_id, framework_sport, hash(athlete_discipline_overrides), estimated_race_duration_hours, team_format, hash(etl_version_set))
```

**Invalidation triggers** (mirror the "re-run conditions" in §10):
- `§H.2 Target Sport / Format` changes
- `§H.2 Constituent Disciplines` changes (when this UI exists)
- `§H.2 Navigation Requirement` changes
- `§H.2 Estimated Duration` crosses 20hr threshold (not on every duration change — only threshold crossings)
- `§H.2 Team Format` changes to/from relay or relay legs change
- `§C Discipline Weighting` overrides change
- ETL version set changes

**Does NOT re-run when:**
- Fitness baselines change (§D, §E, §F)
- Injury records change (§B)
- Locale/equipment changes (§J, §K) — that's 2C scope
- Schedule changes (§G)

## 10. Edge cases

| Case | Behavior |
|---|---|
| `framework_sport` is a sub-format name (e.g., "Triathlon (Standard / Olympic)") | Strip parenthetical for SDM lookup; use full name for PLA lookup. Code-side regex. |
| `framework_sport` not in canonical list | Validation failure (or fuzzy match → UnresolvedFlag if we add fuzzy matching). Per §4, validation fails fast. |
| Sport has no disciplines in SDM (extreme — shouldn't happen for a launched sport) | Return empty `disciplines[]`, set `hitl_required=True`, surface a `no_disciplines_for_sport` flag. |
| `estimated_race_duration_hours` is None and a duration-conditional discipline is in the set | Mark that discipline `conditional_resolution='athlete_opt_in'`. Set `hitl_required=True`. |
| Athlete override targets a discipline not in the sport's set | Log warning; ignore the override; do not fail the call. |
| Discipline has SDM row but no PLA row (legitimate gap, e.g., D-010 for some sub-format sports) | `phase_load` is None on that discipline entry. Layer 4 uses defaults or surfaces a flag. |
| Sport name matches in PLA but not SDM (D-08 carries this risk for LDC/Triathlon) | LEFT JOIN returns nothing from SDM side; discipline doesn't appear in payload. Log INFO. Not a 2A failure. |

## 11. Performance budget

Single query with two LEFT JOINs and a CTE. For AR's 15 disciplines:
- Query: <50ms
- Conditional resolution: <5ms (pure Python on small lists)
- Rationale generation: <30ms (template rendering)
- Serialization: <20ms

**Total: ~100ms.** Well under typical 500ms latency target.

For non-AR sports with sub-format mapping, add ~10ms for the regex strip. Negligible.

## 12. Open items / forward references

| # | Item | Owner | Status |
|---|---|---|---|
| 2A-1 | Rationale template quality bar — needs content review pass per athlete-facing UX | Product / content | 🟡 Partial-close 2026-05-20. v1 templates shipped Andy-quality 2026-05-19 (Phase 2.1) per Andy's "don't defer" call. Full athlete-facing content review naturally falls out of Phase 5.1 orchestrator vertical slice when `race_week_brief` surfaces the strings to Andy in production. |
| 2A-2 | Conditional rule encoding — currently code-side; candidate for `discipline_conditional_rules` table if rules proliferate | Future | Defer until rule count grows |
| 2A-3 | D-17 resolution path for non-AR sports — sub-format selection in onboarding spec | Layer 1 race-goal capture | Tracked in `Project_Backlog.md` |
| 2A-4 | D-05 ETL fix to filter aggregator rows from PLA — will allow removing the defensive `LIKE` filter | FC-1 | Tracked in `Project_Backlog.md` |
| 2A-5 | D-08 LDC/Triathlon SDM missing rows — when those sports come online | FC-1 | Tracked in `Project_Backlog.md` |

## 13. Test scenarios

### 13.1 AR baseline (Andy's plan)

Inputs:
- `framework_sport = "Adventure Racing"`
- `estimated_race_duration_hours = 56` (PGE 2026 duration estimate)
- No overrides

Expected:
- The full AR discipline set returned (the R6 kayak collapse merged the two former kayak rows into D-010, so the count is one lower than the pre-R6 15)
- D-001, D-003, D-006, D-008, D-009 marked Primary
- The navigation discipline (D-015) is `*Conditional` → `prompt_required` (no override) → `hitl_required = True`
- `training_gaps_summary.flagged_count = 0`
- No `conditional_auto_resolved` flags (race-rule auto-resolution retired)

### 13.2 AR with override

Same as 13.1 but with `athlete_discipline_overrides = {'D-008': {'weight': 25.0}}` and the system default for D-008 was 15%.

Expected:
- D-008 entry shows `load_weight.value=25.0`, `source='athlete_override'`, `system_default=15.0`
- A `weight_override_divergence` flag fires (divergence > 50% relative)

### 13.3 Short AR — RETIRED (2026-05-25)

This scenario exercised the duration/nav race-rule auto-resolution path, which no longer exists. Conditional disciplines resolve to `prompt_required` regardless of duration; see §13.1.

### 13.4 Triathlon (non-AR, exercises D-17 path)

Inputs: `framework_sport = "Triathlon (Standard / Olympic)"`.

Expected:
- §5.1 strip logic: top_level = "Triathlon" for SDM lookup; framework_sport = "Triathlon (Standard / Olympic)" for PLA lookup
- 4 disciplines returned: swim/bike/run + transitions
- Phase load bands match the (Standard / Olympic) sub-format band, not other Triathlon sub-formats
- Flags: none specific to the naming mismatch — D-17 workaround is silent when working correctly

## 14. Gut check

**What this spec gets right:**
- D-17 sport-naming mismatch is explicitly addressed at §5.1 with a code-side workaround. Doesn't punt the problem.
- D-05 aggregator filter is mandatory and called out as such. No silent assumption.
- AR baseline test scenario is concrete enough to drive integration test fixture creation.
- Rationale generation explicitly noted as quality-sensitive (Open Item 2A-1).

**Risks:**
- Conditional rules being code-side means they're harder to audit than table-side rules. Tradeoff for v1; revisit if rule count grows past ~10 unique cases.
- Test 13.4 (Triathlon) is the canonical D-17 test. If §5.1 strip logic breaks for sports with parenthetical suffixes that AREN'T sub-format expansions (does any non-sub-format sport have parens in its name?), false-positive strips would happen. Mitigation: explicit list of sub-format-using sports in code rather than blanket regex.
- The `team_format` parameter is plumbed through but not used for AR or any of Andy's near-term sports. For relay sports (Triathlon team relay, Modern Pentathlon team formats) it'll matter. Spec doesn't go deep on relay logic — that's for the future-Triathlon design session.

**What might be missing:**
- I'm assuming `§H.2 Constituent Disciplines` is a feature that may or may not exist. The 2A locking handoff mentions it as an invalidation trigger. If it's an onboarding field, athlete-selected disciplines could conflict with the sport's canonical disciplines — need explicit collision rule. Currently spec assumes the sport's canonical list wins.
- No "default rationale template" content drafted. Templates are referenced but not provided. That's a content-side deliverable, not spec-side.

**Best argument against:** the spec encodes a lot of business logic (conditional rules per sport, weight overrides, rationale templates) that may be more code than this spec is for. Counter: every consumer downstream needs to know what 2A guarantees about its output. Spec documents the interface contract, not the implementation details — but it does need to be specific enough that two different implementers would build the same thing.
