# Layer 3 Node 3B — Goal-Timeline-Viability Evaluation (LLM Node)

**Status:** Draft v1, 2026-05-14. Second of four Layer 3 node specs. Follows 14-section depth standard (Control_Spec §8.3) matching `Layer3_3A_Spec.md`, `Layer2C_Spec.md`, `Layer2D_Spec_v1.md`, `Layer2E_Spec.md`.
**Type:** LLM. Genuine judgment on goal achievability and periodization shape — not reducible to deterministic rules.
**Source decisions:**
- `L3_Discovery_Closing_Handoff_v1.md` §5.2 — scope, inputs, proposed output schema, open questions
- `L3_Spec_Trio_R2_Closing_Handoff_v1.md` §6 — pre-step reading + 3B forward plan
- `Layer3_3A_Spec.md` §7 — input contract on the 3A side
- `Athlete_Onboarding_Data_Spec_v4.md` §H — event vs no-event mode field definitions
- `Layer2A_Spec.md` §7 — input contract on the 2A side
- This session 2026-05-14 — open-question resolutions (HITL triggers, periodization-shape vocabulary, no-event handling, race-in-past handling) approved by Andy before spec writing

**Cross-references:**
- `Control_Spec_v7.md` §3 (data flow), §4 (partial-update model), §7 (HITL surface)
- `Layer3_3A_Spec.md` (input contract; payload schema this spec consumes)
- `Layer2A_Spec.md` (input contract; payload schema this spec consumes)
- `Athlete_Onboarding_Data_Spec_v4.md` §H.1 / §H.2 / §H.3 (mode + goal field source)

---

## 1. Purpose

Judge whether the athlete's stated goal is achievable in the available time, and emit a periodization-shape parameter that Layer 4 (plan generation) uses to size and order training phases.

Two first-class branches:
- **Event-mode** (§H.1 = Y) — viability is framed against Event Date + Goal Outcome + race demands. Periodization shape sizes Base/Build/Peak/Taper across the time-to-event window.
- **No-event-mode** (§H.1 = N) — viability is framed against Plan Duration + Non-Event Goal Type. Periodization shape sizes phases across Plan Duration with no Peak/Taper unless the Goal Type calls for one.

The output is consumed by Layer 4 plan-gen and by 3D's HITL aggregation gate. 3B does not run plan-gen and does not enumerate sessions.

## 2. What 3B does NOT do

Clarifying boundaries:

- **Does not generate a plan.** That's Layer 4. 3B produces the *shape* (mode + phase sizes), not the contents.
- **Does not enumerate exercises or sessions.** That's Layer 4 against 2C's exercise pool.
- **Does not re-derive 3A's state assessment.** Reads `Layer3APayload.current_state` and `recent_trajectory` as given.
- **Does not make injury-vs-discipline calls.** That's 2D. 3B treats 2D's discipline list as authoritative.
- **Does not propose intermediate test races.** Layer 4 designs the build-up race cadence if any. 3B may flag the absence of one as an observation when the timeline is long.
- **Does not interpret Layer 0 reference data.** Reads 2A's typed payload only.
- **Does not pivot to "results mode" if the race already happened.** Race date in the past is a validation error (§4). Athlete must re-scope.

## 3. Function signature

```python
def llm_layer3b_goal_timeline_viability(
    user_id: int,
    layer1_section_h: SectionHGoalContext,
    layer1_section_c: SectionCContext,
    layer3a_payload: Layer3APayload,
    layer2a_payload: Layer2APayload,
    current_date: date,
    etl_version_set: dict[str, str],
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.0,
) -> Layer3BPayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `user_id` | int | Plan-gen context | Used for prompt logging + cache key |
| `layer1_section_h` | `SectionHGoalContext` | Layer 1 sourcing | Includes §H.1 has_event, §H.2 fields (event-mode), §H.3 fields (no-event-mode). See §7 schema. |
| `layer1_section_c` | `SectionCContext` | Layer 1 sourcing | §C Primary Sport, Secondary Sports, Discipline Weighting overrides. Read for goal-type-vs-sport consistency check (no-event mode) and weighting context (both modes). |
| `layer3a_payload` | `Layer3APayload` | 3A node output | Same etl_version_set as 3B; consumed for `current_state` + `recent_trajectory` + `data_density.connected_providers`. |
| `layer2a_payload` | `Layer2APayload` | 2A node output | Same etl_version_set; consumed for included disciplines + per-discipline `phase_load_bands` + `load_weight`. |
| `current_date` | `date` | Plan-gen context | Used for `time_to_event_weeks` calculation in event mode. Frozen at plan-gen time. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Per Control_Spec §6. Validates 3A + 2A payloads were produced against the same pin. |

### Return

`Layer3BPayload` — see §7.

## 4. Input validation (preconditions)

Validation runs before the LLM call. Failures raise typed errors; plan-gen catches and surfaces to the HITL gate or as a fatal error per severity.

| # | Condition | Severity | Error |
|---|---|---|---|
| 1 | `layer1_section_h.has_event == True` requires `event_date` populated and `event_date > current_date` | Fatal | `Layer3BInputError('event_date_in_past')` (or `'event_date_missing'`) |
| 2 | `has_event == True` requires `goal_outcome` populated | Fatal | `Layer3BInputError('event_mode_missing_goal_outcome')` |
| 3 | `has_event == False` requires `plan_duration_weeks ∈ {8, 12, 16, 20, 24}` and `non_event_goal_type ∈ enum` | Fatal | `Layer3BInputError('no_event_mode_missing_fields')` |
| 4 | `layer3a_payload` not None | Fatal | `Layer3BInputError('missing_3a_payload')` |
| 5 | `layer3a_payload.etl_version_set == etl_version_set` | Fatal | `Layer3BInputError('etl_version_mismatch_3a')` |
| 6 | `layer2a_payload` not None and `etl_version_set` matches | Fatal | `Layer3BInputError('etl_version_mismatch_2a')` |
| 7 | At least one discipline in `layer2a_payload.disciplines` has `inclusion == 'included'` | Fatal | `Layer3BInputError('no_included_disciplines')` |

Note on validation #1: race-date-in-past is a fatal error per the open-question resolution in §6.4. The athlete edits §H (new event date or switches to no-event mode), partial-update invalidation re-runs 2A then 3A then 3B.

## 5. Algorithm

### 5.1 Assemble prompt context

Strip the inputs down to what the LLM needs. Avoid passing data the LLM doesn't use — bloated context degrades structured-output reliability.

**Block 1 — Mode + timeline.**
- `has_event` boolean
- If event: `event_date`, `time_to_event_weeks = (event_date - current_date).days / 7`, `time_to_event_phase_band` derived from time_to_event_weeks (see §5.3)
- If no-event: `plan_duration_weeks`, `non_event_goal_type`

**Block 2 — Goal context.**
- Event-mode: `goal_outcome` (Finish / Compete mid-pack / Podium), `time_goal` (optional, string), `first_time_at_distance` (bool), `previous_attempts` (list of {outcome, dnf_cause_text}), `race_distance_km`, `race_duration_hr`, `race_terrain` (multi-select), `race_pack_weight_kg`, `navigation_required` enum
- No-event-mode: `non_event_goal_type` enum + `§C` primary sport name + secondary sports list

**Block 3 — Current state (from 3A).**
- `current_state.aerobic_capacity` (level + confidence + reasoning_text)
- `current_state.strength` (level + confidence + reasoning_text + weak_links)
- `current_state.skill_assessments` filtered to disciplines in 2A's included list
- `recent_trajectory.short_term.direction` + reasoning
- `recent_trajectory.medium_term.direction` + reasoning
- `recent_trajectory.confidence`
- `data_density.connected_providers` (counts only, for confidence framing)

**Block 4 — Discipline + load context (from 2A).**
- For each included discipline: `discipline_name`, `load_weight.value`, `phase_load_bands` (base/build/peak/taper low+high)
- `training_gaps_summary.flagged_count`

**Block 5 — §6 rules verbatim.** The HITL trigger thresholds (§6.1), periodization-shape vocabulary (§6.2), and confidence-floor rules (§6.5) go into the system prompt as explicit rules the LLM follows. Validator-side enforcement provides backstop.

### 5.2 System prompt structure

```
You are AIDSTATION's goal-timeline-viability evaluator (Layer 3 Node 3B).

Your job: judge whether the athlete's stated goal is achievable in the
time available, and produce a periodization shape that Layer 4 will
use to size and order training phases.

You will receive:
  - Mode (event vs no-event) + timeline
  - Goal context (event details OR plan duration + goal type)
  - Athlete current state and recent trajectory (from 3A)
  - Included disciplines + load weights + phase bands (from 2A)

You will produce a structured Layer3BPayload.

[§6 of this spec — quoted in the prompt: HITL trigger thresholds,
 periodization-shape vocabulary, confidence-floor rules.]

Apply the rules. Cite evidence in reasoning_text. Be direct — no
hedging language ("might possibly," "could potentially"). If a goal
is unrealistic as stated, say so and explain why. If a periodization
shape is non-standard, justify the deviation.

Coaching voice: direct, evidence-grounded, no platitudes.
```

### 5.3 Time-to-event phase bands (event-mode only)

Used to inform the LLM's `periodization_shape.mode` choice. The LLM is told the bands as guidance; final choice is the LLM's, subject to §6 guardrails.

| `time_to_event_weeks` | Default phase shape guidance |
|---|---|
| < 4 | `compressed` — Peak + Taper only; Base/Build are skipped (athlete is in whatever shape they're in) |
| 4–8 | `compressed` — Truncated Build + Peak + Taper; minimal or no Base |
| 8–16 | `standard` — Base + Build + Peak + Taper at standard proportions |
| 16–24 | `standard` or `extended` — May add second Base block depending on 3A state |
| > 24 | `extended` — Double Base + Build + Peak + Taper. Note: §H.3 caps plan duration at 24 weeks; event-mode can exceed this. |

### 5.4 LLM call

```python
response = anthropic.messages.create(
    model=model,
    max_tokens=2000,
    temperature=temperature,
    system=SYSTEM_PROMPT_LAYER3B,  # includes §6 verbatim
    messages=[{"role": "user", "content": _assemble_user_message(blocks_1_through_4)}],
    tools=[LAYER3B_OUTPUT_TOOL],
    tool_choice={"type": "tool", "name": "emit_layer3b_payload"},
)
```

Produce a `Layer3BPayload` via the structured-output tool.

### 5.5 Post-LLM validation + payload assembly

1. **Schema validation.** Tool-call output parsed against `Layer3BPayload`. Required fields, enum values, mode-discriminator consistency validated. Schema violations retried once with the error message; failure → `Layer3BOutputError('schema_violation')`.
2. **Mode-discriminator enforcement.** `payload.mode` must equal `'event'` iff `has_event == True`. Mismatch → fail.
3. **§6 guardrail enforcement.** HITL items mandatory under §6.1 conditions are auto-emitted if the LLM omitted them. Confidence floors per §6.5 clamp `goal_viability.confidence` down if data-density signals require.
4. **Periodization-shape sanity.** If `mode == 'custom'` then `phase_weeks` dict must be populated and sum to either `time_to_event_weeks` (event-mode) or `plan_duration_weeks` (no-event-mode), within ±1 week. Out-of-range → re-prompt once; persistent failure → fall back to `standard` with an `observation: 'periodization_shape_fallback'`.
5. **Dataclass assembly.** Final `Layer3BPayload` constructed with metadata (model, temperature, prompt_hash, latency_ms, token_counts).

## 6. Open-question resolution

These are the resolutions confirmed by Andy 2026-05-14 before spec writing. They are encoded in the system prompt verbatim (§5.2 Block 5) and enforced by validators (§5.5 step 3).

### 6.1 HITL trigger thresholds

Surface a HITL item when **any** of:

| Condition | Item severity | Source label |
|---|---|---|
| `goal_viability.viability == 'unrealistic-as-stated'` | `blocker` | `3B.unrealistic_goal` |
| `viability == 'achievable-with-adjustment'` AND `first_time_at_distance == True` AND `goal_outcome ∈ {'Compete mid-pack', 'Podium'}` | `warning` | `3B.first_time_competitive_goal` |
| event-mode AND `previous_attempts` contains a DNF entry AND `time_to_event_weeks < dnf_recovery_window_weeks` | `warning` | `3B.dnf_recurrence_risk` |
| `periodization_shape.mode == 'compressed'` AND 3A `recent_trajectory.short_term.direction ∈ {'overreached', 'fatigued'}` | `warning` | `3B.compressed_on_fatigued_athlete` |

`dnf_recovery_window_weeks` is computed from `previous_attempts.dnf_cause` via a small mapping: `quad_failure → 12`, `nutrition_blowup → 4`, `injury_during_event → 16`, `weather/timeout → 4`, `other → 8` (default).

**Blocker-severity items cannot be acknowledged by the athlete — they must be revised** (§H goal edit, switch mode, or extend timeline). Per 3D gate semantics inherited from L3-Discovery §5.4.

`viability == 'achievable'` with no qualifiers → no HITL.

### 6.2 Periodization-shape vocabulary

`periodization_shape.mode` enum:

| Value | Meaning |
|---|---|
| `standard` | Use 2A's `phase_load_allocation` bands as-is over the available timeline. Default for most cases. |
| `compressed` | Shorter phases or skipped Base. For event-mode `time_to_event_weeks < 8`, or no-event mode when Goal Type strongly mismatches current state and Plan Duration is short. |
| `extended` | Lengthened phases. May include double-Base for `time_to_event_weeks > 20` with athlete starting from low aerobic state. |
| `custom` | Explicit `phase_weeks: dict[phase_name, weeks_int]` override. Used when standard/compressed/extended don't fit (e.g., athlete needs 2 weeks of recovery before any phase starts, or a specific multi-week travel block requires phase boundaries to align). |

Plus `start_phase: enum (Base / Build / Peak / Taper)` — skip-ahead logic. If 3A shows aerobic_capacity ∈ {'good', 'strong'} and short-term trajectory is 'building' or 'steady', LLM may set `start_phase = 'Build'`, skipping Base for an already-fit athlete.

`phase_weeks` is `None` unless `mode == 'custom'`. For other modes, Layer 4 derives phase weeks from `time_to_event_weeks` (event) or `plan_duration_weeks` (no-event) and 2A's standard proportions.

### 6.3 Periodization-shape vs Layer 4 contract

Layer 4's input contract is not yet specced. 3B emits the shape parameter as defined here; Layer 4 may honor it directly or override it with its own justification under the capped correction loop (Control_Spec §4 partial-update model). If Layer 4 overrides 3B's shape, the override propagates back to the user-facing rationale — 3B's `reasoning_text` is preserved alongside Layer 4's override reasoning so the athlete sees both perspectives. Forward-reference flag in §12.

### 6.4 Race date in past

`event_date < current_date` is a fatal validation error (§4 rule 1). 3B does not pivot to "post-race results mode." Rationale: an event in the past changes the athlete's training story (completed race, possibly DNF, possibly injury) but the appropriate next step is to re-scope the goal (new event date, or switch to no-event mode), not auto-generate a plan against a goal that's already been attempted. Athlete edits §H, partial-update invalidation cascades, fresh 3B run produces a meaningful evaluation.

### 6.5 Confidence-floor rules

Mirroring 3A §6.2 pattern: validator-enforced floors prevent the LLM from claiming high confidence when data density doesn't support it.

| Signal | Force `goal_viability.confidence ≤` |
|---|---|
| `first_time_at_distance == True` AND `goal_outcome ∈ {'Compete mid-pack', 'Podium'}` | `medium` |
| 3A `recent_trajectory.confidence == 'low'` | `medium` |
| no-event mode AND 3A `data_density.connected_providers` is empty AND 3A `data_density.self_report_freshness_days > 30` | `low` |
| event-mode AND `previous_attempts` empty AND `first_time_at_distance == True` | `medium` |

When the LLM emits `confidence: 'high'` and a floor rule applies, the payload is rewritten to the floor and an observation auto-emits: `'confidence_clamped_by_data_signal'` with the specific signal name.

### 6.6 No-event mode handling

Viability in no-event mode reduces to: "is the Plan Duration + Non-Event Goal Type combination internally consistent given the athlete's current state?"

Heuristics for the LLM (in the system prompt, not hard rules):

- `non_event_goal_type == 'Strength'` AND 3A `current_state.strength.level == 'low'` AND `plan_duration_weeks ≤ 12` → likely `achievable-with-adjustment`. Periodization shape: `extended` (or recommend Plan Duration extension).
- `non_event_goal_type == 'Endurance'` AND 3A `current_state.aerobic_capacity.level ∈ {'low', 'moderate'}` AND `plan_duration_weeks ≥ 16` → typically `achievable`. Periodization: `standard`.
- `non_event_goal_type == 'Mixed'` → no specific guardrail; shape based on which capacity (aerobic vs strength) is weaker.
- `non_event_goal_type == 'General fitness'` → almost always `achievable` regardless of state; periodization `standard`; minimal HITL.

Cross-check against §C Primary Sport: if Non-Event Goal Type is `Strength` but Primary Sport is a pure endurance discipline (Trail Running, Road Cycling, Swimming, etc.), auto-emit observation `'goal_type_primary_sport_mismatch'` with `elevates_to_hitl=False` (informational only — athletes are allowed to train strength while running their sport).

## 7. Payload schema

```python
@dataclass
class Layer3BPayload:
    # ─── Metadata ──────────────────────────────────────────────────────
    user_id: int
    as_of: datetime
    mode: str                          # 'event' | 'no-event'
    model: str
    temperature: float
    prompt_hash: str                   # sha256 of assembled prompt string
    latency_ms: int
    input_tokens: int
    output_tokens: int
    etl_version_set: dict[str, str]

    # ─── Core outputs ──────────────────────────────────────────────────
    goal_viability: GoalViability
    periodization_shape: PeriodizationShape
    hitl_surface: list[HITLItem]

    # ─── Observations (downstream-actionable notes) ───────────────────
    notable_observations: list[Observation]

    # ─── Event metadata (D-66 paired amendment 2026-05-18) ────────────
    # Sourced from `race_events WHERE user_id=? AND is_target_event=true`
    # per `Race_Events_D66_Design_v1.md` §8 (Layer 3B reads the target row).
    # All four fields are None when `mode == 'no-event'`. When `mode ==
    # 'event'`, populated fields drive Layer 4 race-week-brief §4.5
    # preconditions + Layer 3B's own mode='event' periodization decisions.
    # The fields are optional in v1 — the 3B implementation populates them
    # when the orchestrator joins from the race_events row; legacy 3B
    # outputs without the join leave them None and Layer 4 race-week-brief
    # sources from race_event_payload exclusively.
    event_date: date | None                # None iff mode == 'no-event'
    event_locale_id: str | None
    race_format: str | None                # enum: single_day / expedition_ar / stage_race / multi_day_ultra; None iff mode == 'no-event'
    time_to_event_weeks: int | None        # ≥ 0; None iff mode == 'no-event'

@dataclass
class GoalViability:
    viability: str                     # enum: achievable / achievable-with-adjustment / unrealistic-as-stated
    confidence: str                    # enum: high / medium / low
    reasoning_text: str                # short paragraph; cites evidence
    evidence_basis: list[str]          # field names referenced (e.g., '3a.current_state.aerobic_capacity', '2a.discipline.D-001.phase_load.peak_high', 'h2.goal_outcome')
    suggested_adjustments: list[str]   # short phrases when viability != 'achievable'; e.g., "stretch goal to mid-pack rather than Podium given timeline"

@dataclass
class PeriodizationShape:
    mode: str                          # enum: standard / compressed / extended / custom
    start_phase: str                   # enum: Base / Build / Peak / Taper
    phase_weeks: dict[str, int] | None # populated only when mode == 'custom'; keys ∈ {Base, Build, Peak, Taper}
    reasoning_text: str                # short paragraph justifying mode + start_phase
    evidence_basis: list[str]

@dataclass
class HITLItem:
    source: str                        # always '3B'
    item_label: str                    # e.g., '3B.unrealistic_goal'
    severity: str                      # enum: blocker / warning / informational
    description: str                   # athlete-facing
    recommended_action: str            # athlete-facing
    acknowledge_option: str | None     # None when severity == 'blocker'
    revise_option: str                 # what revision means; e.g., "Edit §H.2 Goal Outcome to 'Finish'"
    revise_target: str                 # field path; e.g., 'h2.goal_outcome'

@dataclass
class Observation:
    category: str                      # enum: warning / opportunity / data_gap / data_hygiene
    text: str                          # human-readable, ≤ 240 chars
    evidence_basis: list[str]
    elevates_to_hitl: bool             # if True, 3D considers surfacing in the gate
```

**Schema-level rules:**

- `mode == 'event'` requires `goal_viability.evidence_basis` to reference at least one §H.2 field.
- `mode == 'no-event'` requires `goal_viability.evidence_basis` to reference §H.3 fields only (no §H.2 references).
- `periodization_shape.phase_weeks` is non-None iff `mode == 'custom'`.
- `suggested_adjustments` is non-empty when `viability != 'achievable'`; empty when `viability == 'achievable'`.
- `hitl_surface` items have unique `item_label` (no duplicates from the same condition firing twice).
- **D-66 paired amendment 2026-05-18 (event-metadata fields):** `mode == 'no-event'` requires all 4 event-metadata fields (`event_date`, `event_locale_id`, `race_format`, `time_to_event_weeks`) to be `None`. `mode == 'event'` SHOULD populate them from the orchestrator-joined target `race_events` row (`is_target_event=true`); pre-amendment 3B implementations may leave them `None` and Layer 4 race-week-brief will source from `race_event_payload` exclusively per `Layer4_Spec.md` §4.5 source-pointer note.

## 8. Coaching flag rules

3B emits `notable_observations` that feed 3D's HITL queue (when `elevates_to_hitl=True`) and Layer 4's commentary surface. Rules below define required observation auto-emit triggers.

### 8.1 Required observations (auto-emit)

| Trigger | Observation category | `elevates_to_hitl` | Notes |
|---|---|---|---|
| `first_time_at_distance == True` (event-mode) | `warning` | True when paired with competitive goal (see §6.1 HITL rule) | "First time at this distance — pacing calibration is the dominant risk." |
| `previous_attempts` contains DNF in same event | `warning` | True per §6.1 conditions | Reference `dnf_cause` text in `evidence_basis`. |
| `time_to_event_weeks > 30` (event-mode) | `opportunity` | False | Suggests intermediate-test-race scheduling. Layer 4 decides specifics. |
| `periodization_shape.mode == 'compressed'` | `warning` | False (unless §6.1 fatigue condition triggers) | Note adherence/injury risk; Layer 4 incorporates load caps. |
| `non_event_goal_type` mismatches §C primary sport (per §6.6 cross-check) | `data_hygiene` | False | Informational; athlete can still train strength while running. |
| confidence clamped by floor rule (§6.5) | `data_gap` | False | Item label `'confidence_clamped_by_data_signal'` + signal name. |

### 8.2 Observation budget

`notable_observations` is bounded by `max_items=6`. The validator drops lowest-priority items past the budget: priority order is `warning > opportunity > data_gap > data_hygiene`. Within category, items emitted by required triggers (§8.1) outrank LLM-discretionary observations.

## 9. Caching & determinism

### 9.1 Cache key

`(user_id, etl_version_set_pin, current_date, hash(input_state))` where `input_state` is the canonical JSON of:
- `layer1_section_h` + `layer1_section_c`
- `layer3a_payload.prompt_hash` (3A's hash, not full payload — 3A's caching covers its own determinism)
- `layer2a_payload.prompt_hash` (same logic)
- `current_date`

This means a re-run with identical inputs but a fresh `current_date` (next day) produces a fresh cache entry. Event-mode payloads are time-sensitive; `time_to_event_weeks` shifts daily.

### 9.2 Invalidation triggers

| Source change | Re-run 3B |
|---|---|
| §H.1 has_event toggle | Yes — mode flip; cache key changes |
| §H.2 fields (event-mode) | Yes |
| §H.3 fields (no-event-mode) | Yes |
| §C Primary Sport, Secondary Sports, Discipline Weighting | Yes |
| `layer3a_payload` re-run (new `prompt_hash`) | Yes |
| `layer2a_payload` re-run | Yes |
| `current_date` crosses a phase boundary (computed against `event_date`) | Yes |
| `etl_version_set` repin | Yes (treat as new plan) |

Re-runs that produce identical Layer3BPayload are skipped at cache-write time (content-hash dedup).

### 9.3 Determinism

`temperature=0.0` + stable system prompt + canonicalized user-message JSON = deterministic LLM output across repeated calls. `prompt_hash` is the sha256 of the assembled system + user prompt strings; verifies determinism in test scenarios.

## 10. Edge cases

| # | Scenario | Behavior |
|---|---|---|
| 1 | Sparse time-goal — Finish + no specified time | Viability evaluated on enum-tier + first_time_at_distance only; confidence drops per §6.5. |
| 2 | Finish goal + abundant timeline (`time_to_event_weeks > 20`) | Trivially achievable; emit `opportunity` observation for intermediate-test-race scheduling; minimal HITL. |
| 3 | Podium + moderate state + 4-week timeline | `unrealistic-as-stated`; suggested_adjustments populated with stretch-goal alternatives; blocker HITL. |
| 4 | First-time-at-distance + Compete mid-pack (10-week timeline) | `achievable-with-adjustment`; HITL warning per §6.1; confidence clamped to medium per §6.5. |
| 5 | Compressed timeline (`time_to_event_weeks == 3`) + 3A short-term overreached | `compressed` mode forced; HITL warning per §6.1; `start_phase = 'Taper'` likely. |
| 6 | Plan duration at 24-week cap + Mixed goal | `standard` mode; no HITL unless §C primary sport mismatches Goal Type strongly. |
| 7 | Race date in past | Fatal validation error (§4 rule 1). Plan-gen surfaces "Update your event date to continue." |
| 8 | No-event Strength goal + Trail Running primary §C | Observation `'goal_type_primary_sport_mismatch'` (informational); viability `achievable`; periodization `standard`. |
| 9 | Event-mode + prior DNF (quad failure mile 68) + 8-week timeline | HITL warning per §6.1 (dnf_recovery_window for quad_failure = 12 weeks > 8); `viability` likely `achievable-with-adjustment` with explicit "recover before resume" suggested adjustment. |
| 10 | Detraining mid-Taper: very long compressed plan ends in extended Taper | `notable_observation` `'extended_taper_detraining_risk'`; Layer 4 adapts taper structure. |

## 11. Performance budget

| Metric | Target |
|---|---|
| Model | `claude-sonnet-4-6` (per Control_Spec §6.1 default for Layer 3 LLM nodes) |
| Latency p50 | < 2.5 s |
| Latency p95 | < 4 s |
| Input tokens | < 3,500 (bounded by 3A excerpt + 2A excerpt + §H block + §6 rules verbatim) |
| Output tokens | < 1,200 (bounded by Layer3BPayload structured output) |
| Cost per call | < $0.04 at Sonnet 4.6 pricing |
| Validation retry budget | 1 (per §5.5 step 1); persistent failure raises `Layer3BOutputError` |

## 12. Open items / forward references

- **Layer 4 plan-gen periodization contract.** Layer 4 spec isn't written. 3B's `periodization_shape` vocabulary may need adjustment when Layer 4's input contract solidifies. Revisit during Layer 4 design.
- **>24-week plans.** §H.3 caps no-event Plan Duration at 24 weeks; event-mode can exceed (e.g., 32-week build to a key A-race). For now, `extended` mode handles event-mode >24-week cases; no-event-mode is bounded by the §H.3 cap. If athletes request >24-week no-event plans post-launch, Plan Duration cap revisits.
- **Re-evaluation cadence as event date approaches.** Should 3B auto-re-run weekly in the final 8 weeks pre-event regardless of input changes? Not in v1 — re-run on input change only. Track as forward consideration when Layer 4 plan-gen cadence is designed.
- **`dnf_recovery_window_weeks` mapping (§6.1).** Current values are reasoned defaults, not measured. Iterate post-launch when DNF data accumulates.
- **Intermediate test races (§8.1 row 3).** 3B observes the opportunity; Layer 4 designs the schedule. The handoff between 3B and Layer 4 on this is implicit through `notable_observations` — explicit contract may be needed.
- **Multi-event athletes (later in 2026?).** AIDSTATION supports one A-race per plan in v1. If multi-A-race support lands, 3B becomes multi-target — material spec revisit.

Forward references:
- Layer 3C consumes `Layer3BPayload.goal_viability.viability` + `periodization_shape.mode` for cross-node conflict detection (e.g., compressed periodization + 2D high-risk discipline → escalate).
- Layer 3D consumes `Layer3BPayload.hitl_surface` items into the unified HITL gate.
- Layer 4 consumes `Layer3BPayload.periodization_shape` as the primary phase-sizing input; consumes `goal_viability.suggested_adjustments` for athlete-facing rationale rendering.

## 13. Test scenarios

These are the 8 test cases the spec writer hands to the implementer. Each describes the input setup and the expected `Layer3BPayload` shape. Exact field values are determined by the LLM (this is an LLM node — outputs vary within enum vocabularies); the test asserts shape, not specific reasoning text.

### TS-1 — AR finisher, 16 weeks (Andy's actual case)

- Event: Pocket Gopher Extreme 2026, July 17–19, 48–56h expedition AR
- `time_to_event_weeks == 9` (current_date = 2026-05-14)
- `goal_outcome = 'Finish'`, `first_time_at_distance = False` (Andy has prior expedition AR)
- 3A: aerobic 'good', strength 'moderate', short_term 'building', medium_term 'building', confidence 'medium'
- 2A: 15 disciplines included, AR-specific roles

**Expected:** `viability == 'achievable'` with confidence 'medium' (clamped only if 3A confidence is low — not the case here). `periodization_shape.mode == 'compressed'` (9 weeks < 16; §5.3 bands). `start_phase` likely 'Build' (already-fit athlete). No HITL items. Observations: maybe `opportunity` for intermediate-test-race (e.g., a shorter AR or trail-run race in week 4-5).

### TS-2 — AR podium, 4 weeks (unrealistic)

- Event: same AR, but `goal_outcome = 'Podium attempt'`, `time_to_event_weeks == 4`
- 3A: aerobic 'moderate', strength 'moderate'
- 2A: same

**Expected:** `viability == 'unrealistic-as-stated'`, confidence 'high' (no floor rule triggers). `suggested_adjustments`: ["Stretch goal to Finish given 4-week window", "Reschedule podium attempt to a later AR with 24+ week build"]. HITL blocker emitted (§6.1 row 1). `periodization_shape.mode == 'compressed'`, `start_phase = 'Taper'` or 'Peak' depending on LLM judgment.

### TS-3 — Trail half-marathon, first-time, 12 weeks

- Event: 21km trail race, `goal_outcome = 'Compete mid-pack'`, `first_time_at_distance = True`, `time_to_event_weeks == 12`
- 3A: aerobic 'moderate', strength 'good', short_term 'steady', confidence 'high'

**Expected:** `viability == 'achievable-with-adjustment'`, confidence 'medium' (clamped per §6.5 row 1). HITL warning per §6.1 row 2 (`3B.first_time_competitive_goal`). `periodization_shape.mode == 'standard'`, `start_phase = 'Base'` or 'Build' depending on 3A weak_links.

### TS-4 — No-event endurance, 24 weeks

- `has_event = False`, `plan_duration_weeks = 24`, `non_event_goal_type = 'Endurance'`
- §C Primary Sport: Trail Running
- 3A: aerobic 'low', strength 'moderate', confidence 'medium'

**Expected:** `viability == 'achievable'`, confidence 'medium'. No HITL. `periodization_shape.mode == 'standard'`, `start_phase = 'Base'`. Observation: maybe `opportunity` for picking an event mid-plan once aerobic capacity rebuilds.

### TS-5 — No-event strength, 8 weeks, low strength state

- `plan_duration_weeks = 8`, `non_event_goal_type = 'Strength'`
- §C Primary Sport: Road Cycling
- 3A: strength 'low', aerobic 'good'

**Expected:** `viability == 'achievable-with-adjustment'`, confidence 'medium'. `suggested_adjustments`: ["Extend Plan Duration to 16+ weeks for meaningful strength gains from a low base"]. Observation `'goal_type_primary_sport_mismatch'` (informational, `elevates_to_hitl=False`). `periodization_shape.mode == 'extended'` (or `'custom'` with a longer Base-equivalent).

### TS-6 — Ultra prior DNF + 12 weeks

- Event: 100-mile ultra, `goal_outcome = 'Finish'`, `previous_attempts = [{outcome: 'DNF', dnf_cause: 'quad_failure'}]`, `time_to_event_weeks == 12`
- 3A: aerobic 'good', strength 'moderate'

**Expected:** `viability == 'achievable-with-adjustment'`, confidence 'medium'. HITL warning per §6.1 row 3 (`dnf_recovery_window_weeks` for quad_failure = 12; `time_to_event_weeks == 12` is borderline — emit warning, not blocker). `suggested_adjustments`: ["Eccentric quad work prioritized weeks 1–6 per documented DNF cause"]. `periodization_shape.mode == 'standard'`.

### TS-7 — Event 1 week away

- `time_to_event_weeks == 1`, any goal_outcome
- 3A: any state

**Expected:** `periodization_shape.mode == 'compressed'`, `start_phase = 'Taper'`. Viability depends on goal_outcome — Finish typically `achievable`, Podium typically `unrealistic-as-stated`. HITL may trigger per §6.1 row 4 if 3A short_term is overreached.

### TS-8 — Race date in past

- `event_date < current_date`

**Expected:** `Layer3BInputError('event_date_in_past')`. No LLM call. Plan-gen surfaces "Update your event date or switch to no-event mode."

## 14. Gut check

**What this spec gets right.**

- **Two modes as first-class branches, not afterthoughts.** Event-mode and no-event-mode have different goal-context shapes; the schema discriminates on `mode` and validators enforce mode-consistency. Avoids the failure mode where no-event-mode is bolted on as edge-case handling.
- **Periodization-shape vocabulary committed, not deferred.** §6.2 locks the enum (`standard`/`compressed`/`extended`/`custom` + `start_phase`). Layer 4 spec will either honor or override under the capped correction loop. Trying to leave the shape free-form to "let Layer 4 decide later" would have bloated Layer 4's own spec with vocabulary-design work.
- **HITL triggers grounded in concrete conditions (§6.1).** Each row of the table is a single boolean expression over typed inputs. No "use your judgment" language for the validator. The LLM has discretion within those bands but the floor is mechanical.
- **Race-date-in-past as a fatal error, not a soft pivot.** Matches the spec-first principle — if state is wrong, fix the input, don't compensate downstream. Athletes who finished their event move forward by editing §H, not by 3B doing it for them.
- **Confidence floors mirror 3A's pattern.** Downstream consumers (3C, 3D, Layer 4) can rely on `confidence` meaning the same thing across 3A and 3B.

**Risks.**

- **Periodization-shape vocabulary committed before Layer 4 exists.** `standard`/`compressed`/`extended`/`custom` are reasoned guesses at what Layer 4 will accept. Real risk that Layer 4 design forces revision. Mitigation: §12 forward-reference flag; the vocabulary is small enough that adding a 5th value or renaming one is a §6.2 patch, not a structural change.
- **HITL thresholds in §6.1 are policy, not data-validated.** Same shape as 3A's confidence-floor risk. `dnf_recovery_window_weeks` defaults (quad_failure→12 weeks, etc.) are reasoned, not measured. Post-launch DNF data will sharpen these.
- **`start_phase` skip-ahead logic relies on 3A's `current_state` being correctly tagged.** If 3A clamps to 'moderate' too aggressively, 3B never skips Base for already-fit athletes. Cross-spec coupling — 3A's calibration affects 3B's downstream behavior.
- **No-event-mode test scenarios are thinner than event-mode.** Most real athletes have events; no-event is the secondary mode. But for fitness coaches using AIDSTATION with general-fitness clients, no-event-mode is the primary path. Worth post-launch attention to whether no-event viability calls land well.

**What might be missing.**

- **3A short-term `direction == 'peaking'` interaction.** If 3A says the athlete is already peaking and event is 2 weeks away, the periodization shape should be Taper-only — but if event is 12 weeks away, peaking-now is a problem (athlete will detrain before event). 3B's prompt should reference this; the spec doesn't make it explicit.
- **Confidence aggregation across goal_viability + periodization_shape.** Currently `goal_viability.confidence` is the only confidence tag. `periodization_shape` has no confidence field. Should it? Argument for: shape choice is judgment too. Argument against: 4-enum + start_phase has small possible-output space; confidence is implicit.
- **No-event-mode + plan-duration ≤ 8 weeks edge case.** A "Strength" Goal Type in 8 weeks with low strength state is meaningfully different from 8 weeks of Endurance with low aerobic state. The §6.6 heuristic covers the strength case explicitly but not all combinations.
- **Multi-discipline first-time risk.** A triathlete first-time at a 70.3 distance is first-time-at-distance in three disciplines simultaneously. §6.1 row 2 fires once; the observation reasoning should call out the multi-discipline angle, but the schema treats it as a single field. Probably acceptable; flag if it surfaces in testing.

**Best argument against this spec's scope.**

You could argue 3B should fold the periodization-shape output into Layer 4 entirely — i.e., 3B only emits viability + reasoning, and Layer 4 picks the shape based on viability + raw inputs. Counter: 3B has 3A's state context that Layer 4 will have anyway, but the *judgment* of how to weight current_state vs timeline vs goal is genuine LLM reasoning that belongs in one place. Splitting it across two LLM nodes (3B for viability + Layer 4 for shape) means two LLM calls reasoning about the same trade-offs, which is wasteful and may produce contradictory shapes. Keeping shape in 3B is the smaller compound surface.

Alternatively, you could argue 3B should not commit to a shape vocabulary at all and instead emit a textual recommendation + parameter hints, letting Layer 4 parse those into its own shape model. Counter: parsing is brittle and the failure mode is silent (Layer 4 mis-parses 3B's hint and produces a wrong plan). Structured shape with a small enum + explicit reasoning_text is the loud-failure path — Layer 4 either accepts the enum or overrides explicitly, no parsing required.
