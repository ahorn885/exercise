# Layer 3A — Athlete State Evaluation (LLM Node)

**Status:** Consolidated spec, first draft 2026-05-13. Drafted in the L3-Spec-Trio Round 2 session after the absorption pass (Onboarding v4, Integration v2, Catalog Migration v2, Backlog v11 shipped earlier same session).
**Type:** LLM node. Single LLM call per invocation. Deterministic-by-construction: same inputs + same model + same temperature → same output (within model stability bounds).
**Predecessor decisions:** L3-Discovery handoff §5.1 (scope), L3-Spec-Trio handoff (integration architecture, 4-node framing in Control_Spec v6 §2). Open questions from L3-Discovery §5.1 are resolved in §6 of this spec.

---

## 1. Purpose

Produce a structured judgment of an athlete's **current athletic capacity** and **recent trajectory** from the assembled Layer 1 payload, recent integration data, and the 2A phase context. The output is a typed payload consumed by Layer 3B (goal-timeline viability), Layer 3C (cross-node conflicts), Layer 3D (HITL gate), and Layer 4 (plan generation).

3A is the *interpretive* layer between raw athlete data and downstream coaching decisions. Layer 1 stores what the athlete reported and what providers ingested; 2A-2E classify race demands and constraints; 4 builds the plan. 3A is the node that says: *given what we know about this athlete right now, where are they on the fitness curve, and what direction are they moving?*

The judgment is grounded in evidence and tagged with confidence — never invented. Where data is sparse, 3A says so explicitly and flags the gap in `data_density` and `notable_observations`. Downstream nodes treat low-confidence outputs differently from high-confidence ones (3B reduces its viability assertion strength; 3D may surface a data-density HITL prompt; Layer 4 prefers conservative phase prescription).

3A is the single most consequential LLM call in the Layer 3 pipeline. Its output frames every downstream decision about the athlete's current readiness. The spec's job is to make that call repeatable, evidence-anchored, and honest about uncertainty.

## 2. What 3A does NOT do

Boundary clarifications to prevent scope creep — particularly the kind that would let 3A duplicate work that lives elsewhere in the pipeline.

- **Does not classify the race or the disciplines.** That's 2A (discipline mix + weights, phase position) and 2B (terrain × environment). 3A consumes 2A's output as phase context; it does not re-derive disciplines or weights from §C.
- **Does not evaluate injury risk or generate injury HITL items.** That's 2D. 3A reads §B health/injuries as context only — to color the strength assessment if relevant constraints exist (e.g., "shoulder injury limits pressing tier") — but produces no risk judgment.
- **Does not judge goal viability or timeline feasibility.** That's 3B. 3A characterizes current state; 3B asks whether stated goals fit. The split matters: 3A may run when no event is scoped at all (no-event mode), in which case 3B receives the state output and pivots accordingly.
- **Does not flag cross-node constraint conflicts.** That's 3C. 3A is a single-node evaluator; it doesn't compare its output against 2A/2D/2E outputs for inconsistency.
- **Does not aggregate HITL items or operate a gate.** That's 3D. 3A may emit observations that look like HITL prompts (e.g., "no integration data — confidence is low — consider connecting Garmin or Polar") but they live in `notable_observations`, not in a HITL queue. 3D pulls from `notable_observations` if it elevates them.
- **Does not pick exercises, prescribe volume, or set intensity targets.** That's Layer 4. 3A produces qualitative state ("aerobic capacity is good for the athlete's training age") and ACWR ratios as evidence; it doesn't say "athlete should do 6 × 1km at 4:00/km."
- **Does not modify Layer 1 data.** Read-only. Any data correction is a 3D HITL revise-and-cascade flow, not a 3A side effect.
- **Does not produce per-discipline workout-by-workout commentary.** 3A summarizes; it does not audit. If the user wants per-workout observations, that's a different feature (Plan Management commentary, post-launch).

## 3. Function signature

```python
def llm_layer3a_athlete_state(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    integration_bundle: Layer3AIntegrationBundle,
    as_of: datetime,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-5",      # plan-gen pin; overridable for cost or experiments
    temperature: float = 0.2,
    max_tokens: int = 4000,
    cache_key_override: str | None = None,  # for replay / determinism testing
) -> Layer3APayload:
    ...
```

### Parameters

| Param | Type | Source | Notes |
|---|---|---|---|
| `user_id` | int | Pipeline driver | The athlete being evaluated. Used in cache key and for logging; not exposed to the LLM. |
| `layer1_payload` | `Layer1Payload` | `q_layer1_payload(user_id, as_of)` | Full Layer 1 dataclass: §A demographics, §B health (context only), §C training history, §D discipline baselines, §E strength benchmarks, §F performance testing, §I lifestyle/recovery. Other sections present but not consumed by 3A. |
| `layer2a_payload` | `Layer2APayload` | Prior cached 2A run for the same plan | Phase context: discipline weights, current phase position, `phase_load_allocation` row for current phase. Drives the "what phase should they be in" framing. |
| `integration_bundle` | `Layer3AIntegrationBundle` | Composed from 5 `q_layer3A_*` calls (see §10 of Integration Spec) | Recent workouts, sleep, HRV, combined load, provider coverage. May be empty (no providers connected). |
| `as_of` | datetime | Pipeline driver | Anchors all rolling windows. Defaults to NOW() at the caller, but always passed explicitly here for replay determinism. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Per spec v3 §5.1 Decision 2. Locks Layer 0 reference data version. Read-through to any layer0 lookups (e.g., resolving primary_sport name from `layer0.sports`). |
| `model` | str | Default per plan-gen pin | Claude Sonnet 4 is the default. Bumping requires regression test pass on §13 scenarios. |
| `temperature` | float | Default 0.2 | Low temperature for reproducibility. Not zero — small variance is acceptable; the cost of pure determinism via temp=0 is degraded reasoning quality on long inputs. Range 0.1–0.3 is the operating band. |
| `max_tokens` | int | Default 4000 | Output is structured + reasoning text. 4000 covers a verbose-reasoning path comfortably. |
| `cache_key_override` | str \| None | Test / replay | For deterministic re-runs against the cache; production should leave as None. |

### Returns

`Layer3APayload` dataclass — see §7. Includes the structured judgment, evidence basis per field, confidence tags, `data_density` block, and `notable_observations`.

## 4. Input validation (preconditions)

Run before the LLM call. Failure modes raise `Layer3AInputError` with a specific code so the caller can decide whether to surface to the athlete, route through 3D as HITL, or fail the plan-gen run entirely.

| Check | Required | On fail |
|---|---|---|
| `layer1_payload` non-None | ✓ | `Layer3AInputError("missing_layer1")` — pipeline bug; never expected in production |
| `layer1_payload.section_a` present (demographics) | ✓ | `Layer3AInputError("incomplete_onboarding")` — surface to 3D HITL: "complete onboarding §A before plan generation" |
| `layer1_payload.section_c.primary_sport` populated | ✓ | Same as above (§C completion gate) |
| `layer2a_payload` non-None | ✓ | `Layer3AInputError("missing_2a")` — pipeline ordering bug |
| `layer2a_payload.discipline_weights` non-empty | ✓ | Same — 2A failed to produce usable output |
| `integration_bundle` non-None (may be empty) | ✓ | Empty bundle is valid; None is a pipeline bug |
| `as_of` non-None and ≤ NOW() + 1 hour skew | ✓ | `Layer3AInputError("invalid_as_of")` — caller bug |
| `etl_version_set` non-empty | ✓ | `Layer3AInputError("missing_etl_pin")` — caller bug |
| `model` in approved-models list | ✓ | `Layer3AInputError("unapproved_model")` — config drift |
| `temperature` in [0.0, 1.0] | ✓ | Reject with `Layer3AInputError("invalid_temp")` |

**Soft preconditions (warnings, not errors):**

- §C `years_training` < 0.25 (less than 3 months) → log warning; output will tag confidence `low` automatically per §6
- §C `current_weekly_volume_hours == 0` AND `integration_bundle.recent_workouts == []` → log warning; "just-onboarded, no data" edge case per §10
- Conflicting unit fields (e.g., §D.1 Easy Run Pace in min:sec/km but §C peak volume in miles) → coerce silently; log as data-hygiene observation

## 5. Algorithm

3A is a single LLM call wrapped in three stages: **input prep** (transform raw dataclasses into a prompt-friendly summary), **LLM invocation** (single call, structured output), and **output validation + dataclass assembly**.

### 5.1 Stage 1 — Input prep

The Layer 1 payload, 2A payload, and integration bundle are summarized into prompt sections. Raw dataclasses are not serialized verbatim — the LLM gets a coach-readable summary that mirrors what a human coach would scan before evaluating an athlete.

Prep transformations:

1. **Demographics → context line.** Age, sex (only if explicitly used for relevant assessment — see §6), height, weight (if recent), training-age-in-years. Pregnancy is never in this block (per Onboarding v4 §B disclosure-only policy).
2. **§C Training History → narrative block.** Years training, primary sport, secondary disciplines with tier, current weekly volume, peak historical volume, training consistency, longest event completed, recent race results (filtered to last 12 months, sorted descending).
3. **§D Discipline Baselines → per-discipline table.** Only disciplines with `included = True` per 2A. Each block lists experience + benchmarks + skill calls. Empty disciplines are omitted, not shown-as-blank.
4. **§E Strength Benchmarks → bullet list.** Front plank, dead bug, side plank, push-ups, BW squat, single-leg squat, pull-up max, dead hang, grip strength. Missing values shown as "not tested".
5. **§F Performance Testing → bullet list.** HRmax, LT HR, VO2max, FTP, Running Threshold Pace, CSS — with source (measured / estimated) and test date age.
6. **§I Lifestyle → bullet list.** Sleep avg, sleep quality, stress, diet pattern, supplement protocol summary, caffeine strategy, altitude history.
7. **Integration bundle → summary table.** Per accessor (recent_workouts, recent_sleep, recent_hrv, combined_load, connected_providers): record counts, date ranges, per-source breakdown. ACWR per-discipline shown as ratio + risk zone (per `q_layer3A_combined_load` output).
8. **2A phase context → single block.** Current phase name, weeks into phase, target weekly volume range for current phase, phase_load_allocation row for the current phase.

The prep output is a structured prompt-ready dict; templating into the actual prompt string is deterministic.

### 5.2 Stage 2 — LLM invocation

Single LLM call. Structured output via tool-call or JSON schema enforcement (whichever the model supports cleanly — Sonnet 4 uses tool-call schema enforcement).

**Prompt structure:**

```
[SYSTEM]
You are evaluating an endurance athlete's current state. Your role is the
internal coaching analyst — direct, evidence-grounded, no platitudes. You
read the athlete's profile and recent training/recovery data, then produce
a structured judgment with explicit confidence tags.

Hard rules:
1. Ground every assessment in specific evidence from the input. Cite the
   field name(s) in your reasoning_text.
2. Never invent data. If a field is "not tested" or missing, treat it as
   absent — do not extrapolate from peer fields.
3. Distinguish current state (where the athlete is right now) from recent
   trajectory (where they are moving). Both are required.
4. When self-report and integration data conflict, follow the rule set
   in [§6 of this spec — quoted in the prompt].
5. Confidence is calibrated to data density per the rule set in §6. Be
   conservative: "high" requires explicit thresholds being met.
6. Emit notable_observations only when they would change a downstream
   decision. Do not narrate.

[USER]
Athlete context: [demographics line]

Training history:
[§C narrative block]

Discipline baselines:
[§D per-discipline blocks]

Strength benchmarks:
[§E bullet list]

Performance testing:
[§F bullet list]

Lifestyle and recovery:
[§I bullet list]

Recent activity bundle (last 28 days):
[integration summary table]

Current phase context (from 2A):
[2A phase block]

Health-context note (read-only): [§B summary, max 2 sentences — for
context coloring strength assessments only; injury risk is owned by 2D]

Today is [as_of].

Produce a Layer3APayload via the structured output tool.
```

The structured output tool defines the payload schema (see §7). The LLM cannot return free-form text outside the tool call.

### 5.3 Stage 3 — Output validation + dataclass assembly

1. **Schema validation.** Tool-call output is parsed against `Layer3APayload`. Required fields, enum values, and confidence-tag values are validated. Schema violations are retried once (re-prompt with the error message) and then fail with `Layer3AOutputError("schema_violation")`.
2. **Evidence-basis cross-check.** For each assessment field, the `evidence_basis` list must reference field names that actually exist in the input. The check is name-based: "section_c.years_training" must exist in the prep dict. Missing references log a warning but don't fail.
3. **Confidence-tag floor enforcement.** Per §6, certain data-density signals force a confidence ceiling. If the LLM returned `high` but the floor rule says `medium` max, the payload is rewritten to `medium` and an observation is added: `"confidence_clamped_by_data_density"`.
4. **Dataclass assembly.** Final `Layer3APayload` is constructed with metadata (model, temperature, prompt_hash, latency_ms, token_counts).

The output is then ready for caching and consumption.

## 6. Self-report vs integration data weighting + confidence calibration

L3-Discovery §5.1 left two open questions: how to weight conflicting self-report vs integration data, and where the confidence thresholds sit. This section resolves both.

### 6.1 Self-report vs integration weighting

Different field categories follow different rules. The LLM is told the rules explicitly in the system prompt.

| Field category | Examples | Weighting rule |
|---|---|---|
| **Objective metrics** | Volume hours, distance, HR averages, sleep duration, vertical gain, activity count | **Integration data dominates when present.** Self-report is informative only as a sanity check. If self-report and integration diverge by >25%, flag in `notable_observations` as data-hygiene issue (athlete may have misremembered, or provider may be misconfigured). |
| **Subjective metrics** | Perceived fitness, stress level, motivation, sleep quality (felt), perceived recovery | **Self-report dominates.** Integration may inform (e.g., low HRV alongside reported low energy = high-confidence agreement) but cannot override. There is no objective measure of "how the athlete feels." |
| **Hybrid metrics** | Sleep (duration objective + quality subjective), recovery status, readiness | **Both shown to the LLM with sources tagged.** The LLM synthesizes. Disagreement (athlete reports good sleep; provider records 4h actual) is itself a signal — flag in observations. |
| **Skill / experience fields** | Trail running experience, MTB technical skill, climbing grade | **Self-report only.** No integration source covers these. Confidence is bounded by recency-of-claim (if athlete reports "Advanced" but hasn't logged a relevant activity in 18 months, confidence drops). |
| **Calibration tests** | Push-up max, dead hang seconds, plank hold, single-leg squat Y/N | **Self-report only, dated.** Treat as snapshot at test date. If test is >12 months old, confidence drops; if >24 months, observation suggests retest. |
| **Performance tests** | FTP, CSS, Running Threshold Pace, HRmax | **Self-report or measured both valid.** Decays per the standard decay model (FTP: 5–7% over 6–8 wk without maintenance; per §F). If test is stale and recent training contradicts (e.g., FTP from 2 years ago + 0 cycling in 6 months), treat as "stale baseline — not usable" rather than "true FTP." |

### 6.2 Confidence calibration

Each assessment field carries a `confidence` enum (high / medium / low). The LLM proposes; the validator enforces floors.

**Confidence floor rules (validator-enforced):**

| Signal | Effect on confidence |
|---|---|
| `connected_providers.count == 0` | Trajectory confidence ≤ medium. State confidence not affected. |
| `recent_workouts.count < 5` in last 28 days | Trajectory confidence ≤ low. |
| `recent_sleep.count == 0` in last 14 days | Recovery-related observations ≤ medium confidence. |
| `recent_hrv.count == 0` in last 14 days | Trajectory confidence ≤ medium. (Not low — workouts alone support medium-confidence trajectory.) |
| `§C.years_training < 0.25` | All current_state assessments ≤ medium (insufficient training history to characterize). |
| `§F.HRmax.source == 'estimated'` | Aerobic capacity assessment caveat: "HRmax estimated, not measured" — confidence not auto-reduced but noted. |
| ETL data older than 12 months feeding any assessment | That assessment ≤ medium. |

**Confidence-high gates (LLM may emit; validator does not reduce):**

`high` confidence requires ALL of:
- ≥1 connected provider with active data in the last 14 days
- ≥10 logged workouts in the last 28 days (across all disciplines)
- §C self-report present and not in conflict with integration data
- §F performance baselines present (at least HRmax + one threshold metric) and not stale
- §I sleep self-report present
- For the specific assessment field: evidence_basis cites ≥3 input fields

`medium` is the safe default. `low` requires explicit data-gap reasoning.

### 6.3 Surfaced as observations

When the floor rules clamp the LLM's confidence proposal, a `notable_observation` is auto-appended:

- `"confidence_clamped_by_data_density"` with the specific signal name (e.g., "no_connected_providers", "sparse_recent_workouts").

These observations feed 3D's HITL queue. 3D may surface a prompt like "Connect a wearable for higher-confidence trajectory analysis" or "Confirm sleep self-report — only 2 entries logged in last 14 days."

## 7. Payload schema

```python
@dataclass
class Layer3APayload:
    # ─── Metadata ──────────────────────────────────────────────────────
    user_id: int
    as_of: datetime
    model: str
    temperature: float
    prompt_hash: str            # sha256 of the assembled prompt string
    latency_ms: int
    input_tokens: int
    output_tokens: int
    etl_version_set: dict[str, str]

    # ─── Current state ─────────────────────────────────────────────────
    current_state: CurrentState

    # ─── Recent trajectory ─────────────────────────────────────────────
    recent_trajectory: RecentTrajectory

    # ─── Data density (what was actually available to the model) ──────
    data_density: DataDensity

    # ─── Observations (downstream-actionable notes only) ──────────────
    notable_observations: list[Observation]


@dataclass
class CurrentState:
    aerobic_capacity: Assessment            # enum: low / moderate / good / strong
    strength: Assessment                    # enum: low / moderate / good / strong
    weak_links: list[str]                   # short phrases, e.g. "shoulder press strength", "single-leg balance"
    skill_assessments: dict[str, Assessment]  # discipline_id → Assessment; sparse — only included disciplines
    body_composition_notes: str | None      # optional, only when relevant signal exists

@dataclass
class Assessment:
    level: str                  # enum: low / moderate / good / strong / insufficient_data
    confidence: str             # enum: high / medium / low
    reasoning_text: str         # short paragraph; cites specific fields
    evidence_basis: list[str]   # field names referenced (e.g., "section_f.ftp", "integration.combined_load")

@dataclass
class RecentTrajectory:
    short_term: TrajectoryWindow        # last ~14 days
    medium_term: TrajectoryWindow       # last ~28-56 days
    acwr_status: ACWRStatus
    confidence: str                     # high / medium / low — aggregate over both windows

@dataclass
class TrajectoryWindow:
    direction: str        # enum: overreached / fatigued / recovered / steady / building / detrained / peaking / insufficient_data
    reasoning_text: str
    evidence_basis: list[str]

@dataclass
class ACWRStatus:
    per_discipline: dict[str, ACWREntry]  # discipline_id → entry
    combined: ACWREntry | None            # None if not computable (no integration data + no manual log)

@dataclass
class ACWREntry:
    acute_load: float        # acute load (last 7 days)
    chronic_load: float      # chronic load (last 28 days)
    ratio: float
    zone: str                # enum: undertraining / sweet_spot / functional_overreach / non_functional_overreach / detraining
    units: str               # "hours" or "TRIMP" or "TSS" — per source

@dataclass
class DataDensity:
    connected_providers: list[str]              # provider names with active data
    integration_data_days: int                  # length of integration window with non-zero data
    recent_workouts_count: int                  # last 28 days
    recent_sleep_count: int                     # last 14 days
    recent_hrv_count: int                       # last 14 days
    self_report_freshness_days: int             # days since most recent wellness_self_report
    section_completeness: dict[str, float]      # §C/§D/§E/§F/§I → 0.0-1.0 ratio of populated fields

@dataclass
class Observation:
    category: str           # enum: warning / opportunity / data_gap / data_hygiene
    text: str               # human-readable, ≤ 240 chars
    evidence_basis: list[str]
    elevates_to_hitl: bool  # if True, 3D considers surfacing in the gate
```

**Schema-level rules:**

- `Assessment.level == 'insufficient_data'` is valid for any assessment. When emitted, `reasoning_text` must explain what was missing.
- `RecentTrajectory.short_term.direction` and `medium_term.direction` can differ — e.g., "fatigued (short-term)" with "building (medium-term)" indicates a hard training block.
- `ACWRStatus.combined` is None when no integration data exists AND `cardio_log` is empty. Per-discipline may still populate from self-reported §C.
- `weak_links` is bounded by `max_items=5`. Plan-gen consumes these for accessory programming; longer lists dilute usefulness.

## 8. Coaching flag rules

3A doesn't manage flags directly — it emits `notable_observations` that feed 3D's HITL queue and Layer 4's commentary surface. The rules below define when 3A *must* emit specific observation types.

### 8.1 Required observations (auto-emit)

| Trigger | Observation category | Text shape | `elevates_to_hitl` |
|---|---|---|---|
| ACWR ratio > 1.5 in any discipline OR combined | warning | "Acute:chronic load ratio in [discipline] is [ratio] — overreaching risk per ACWR meta-analysis 2020-2025." | True |
| ACWR ratio < 0.5 in any discipline AND athlete is in build/peak phase per 2A | warning | "Acute load in [discipline] is below detraining threshold for current phase — review whether intentional." | True |
| Self-report volume vs integration volume diverges >25% | data_hygiene | "Self-reported weekly volume ([X] hrs) diverges from logged volume ([Y] hrs) by >25% — verify provider sync or update self-report." | True |
| Sleep self-report avg <6 hrs AND no integration sleep data | warning | "Self-reported sleep averages <6 hrs without provider confirmation. Recovery quality is a foundation; consider connecting a wearable or revisiting sleep target." | False |
| `connected_providers.count == 0` AND athlete is in peak phase | data_gap | "No integration data and athlete is in peak phase — trajectory confidence is bounded; consider connecting Garmin, Polar, COROS, or Wahoo for higher-fidelity readiness assessment." | True |
| Performance baseline (§F) test date >12 months old | data_gap | "[Metric] last tested [N] months ago — value may be stale; retest recommended for accurate zone prescription." | False |
| Strength benchmark (§E) entirely absent (no fields populated) | data_gap | "Strength benchmarks not captured — Layer 4 will not prescribe progression-gated exercises until baseline established." | True |
| Just-onboarded (`years_training < 0.25` AND `recent_workouts.count < 5`) | data_gap | "Insufficient training history for trajectory assessment. State output is profile-based; trajectory will populate after ~4 weeks of logging." | False |
| HRV crash signal (recent 7-day HRV avg <70% of 28-day avg) | warning | "HRV trending sharply downward — early autonomic stress signal. Consider easing the next 3-5 days." | True |

### 8.2 Forbidden observations (never emit)

- Generic encouragement ("You're doing great!" / "Keep it up!"). 3A is an analytical node, not a cheerleader. This is hard-coded in the system prompt voice rules.
- Goal-related observations ("Your goal of sub-3 marathon is realistic"). That's 3B's territory.
- Injury-risk observations ("Knee pain pattern suggests IT band syndrome"). That's 2D's territory.
- Exercise prescriptions ("Do 4×4 VO2 intervals"). That's Layer 4.
- Speculation beyond evidence ("Based on your name, you might enjoy ultra running"). LLM is bound by the "ground in evidence" rule.

### 8.3 Observation ordering

Observations are returned in priority order, highest first:

1. `warning` with `elevates_to_hitl=True`
2. `data_gap` with `elevates_to_hitl=True`
3. `warning` with `elevates_to_hitl=False`
4. `data_hygiene` with `elevates_to_hitl=True`
5. Everything else

Plan-gen and 3D consume in this order; truncation favors high-priority items.

## 9. Caching & determinism

LLM nodes are not naturally deterministic. 3A's contract makes them deterministic-enough via the caching layer plus a fixed temperature operating band.

### 9.1 Cache key

```
sha256(
    user_id ||
    layer1_payload_hash ||
    layer2a_payload_hash ||
    integration_bundle_hash ||
    as_of.replace(hour=0, minute=0, second=0, microsecond=0) ||  # day-granular
    etl_version_set_json ||
    model ||
    str(temperature)
)
```

Day-granular `as_of` means re-running on the same calendar day returns the cached payload. Re-running with new training data ingested mid-day invalidates because `integration_bundle_hash` changes.

### 9.2 Invalidation triggers

3A re-runs when:
- Any Layer 1 §C/§D/§E/§F/§I field changes
- 2A output changes (phase progression, discipline weight revision)
- Integration data lands that was not in the prior bundle (e.g., new workout sync, new sleep record)
- `etl_version_set` changes (Layer 0 data refresh)
- Explicit invalidation by 3D after an athlete's "revise" action

3A does NOT re-run on:
- §A demographics changes (irrelevant — only used for context, not assessment)
- §B health/injury changes (read-only context; if material, 2D re-runs and updates color; 3A picks up the new color on its next natural invalidation)
- §H goal changes (3B's territory)
- §J locale or equipment changes (Layer 4's territory)
- Time passing alone (until day-granular `as_of` advances and integration data refreshes — but a no-op cache hit on the same data is fine)

### 9.3 Determinism caveats

- Same inputs + same model + same temperature → within-model output stability bounds. Sonnet 4 at temp=0.2 is empirically stable on structured outputs across thousands of calls (per Anthropic's published behavior); we treat it as deterministic.
- Model changes invalidate cache (model is in the key).
- Temperature changes invalidate cache (temp is in the key).
- Prompt template changes (different field formatting, reordering) invalidate cache — the `prompt_hash` in the payload metadata helps debug whether a cache miss is due to data or prompt.

## 10. Edge cases

### 10.1 Just-onboarded athlete

`years_training < 0.25`, `recent_workouts.count < 5`, no integration data.

3A outputs:
- `current_state`: profile-based assessments only; all confidence = low; reasoning explicitly cites "insufficient training history"
- `recent_trajectory`: `short_term.direction = 'insufficient_data'`, `medium_term.direction = 'insufficient_data'`, confidence = low, ACWR null per-discipline and combined
- `data_density`: low scores across the board
- `notable_observations`: data_gap observation about needing 4 weeks of logging

### 10.2 No integration providers connected

Self-report only, but otherwise complete.

3A outputs:
- `current_state`: normal assessments, confidence may reach medium for assessments grounded in §F + §E
- `recent_trajectory`: bounded to medium confidence per §6.2; ACWR computed from `cardio_log` if present
- `notable_observations`: data_gap about provider connection, elevates_to_hitl=True

### 10.3 Conflicting signals

High logged volume (provider) + reports feeling overtrained (self-report §I stress).

3A outputs:
- LLM synthesizes — both signals are valid and inform different aspects
- `current_state.aerobic_capacity` likely 'good' or 'strong' (volume objective)
- `recent_trajectory.short_term.direction` likely 'fatigued' or 'overreached' (subjective signal corroborated by ACWR ratio if >1.3)
- `notable_observations`: warning about subjective-objective divergence; suggests reviewing recovery

### 10.4 Returning athlete after long gap

Athlete has rich §C historical baseline (peak 12 hrs/wk 2 years ago) but no recent activity (0 workouts last 90 days).

3A outputs:
- `current_state`: aerobic_capacity downgraded vs historical peak; reasoning cites detraining; weak_links populated based on time-since-last-strength-work
- `recent_trajectory.medium_term.direction`: 'detrained'
- `notable_observations`: opportunity about leveraging prior training base; data_gap about stale §F baselines

### 10.5 Peak phase with strong signals

Connected provider, ACWR 1.2 combined, HRV stable, sleep good.

3A outputs:
- `current_state.aerobic_capacity`: 'strong' with high confidence (all gates met)
- `recent_trajectory.short_term.direction`: 'building' or 'peaking' per 2A phase context
- ACWR per-discipline + combined populated
- Few or no observations beyond the routine context

### 10.6 All-zero athlete

Account created, no fields populated beyond §A demographics. (Should fail §4 preconditions on `section_c.primary_sport` — but defensively if it doesn't:)

3A returns minimal output:
- All assessments `level = 'insufficient_data'`, confidence = low
- `notable_observations` = single data_gap about needing onboarding completion, `elevates_to_hitl=True`
- Downstream 3D gates plan-gen until onboarding completes

### 10.7 Provider connected but no data flowing

Garmin OAuth completed, but no FIT files synced yet (or webhook subscription lagging).

`integration_bundle.connected_providers` shows Garmin; all five accessor outputs are empty for Garmin source.

3A outputs:
- Treats as "no integration data" per §6.2 floor rules
- `notable_observations`: data_hygiene observation about Garmin connection without data flow; suggests forcing a sync or checking permissions

### 10.8 Female athlete RHR + pregnancy disclosure

Per Onboarding v4 §B: pregnancy status is never captured. 3A never references pregnancy state. If RHR is elevated, 3A applies the standard Rule 2 elevation observation; if the athlete is pregnant, the UI disclosure (not 3A) carries the contextual note.

3A does not branch on pregnancy state and does not need a "pregnancy possible" code path. Standard observation rules apply.

## 11. Performance budget

| Stage | Target | Notes |
|---|---|---|
| Stage 1 input prep | <100ms | Pure dataclass-to-dict transformation; no I/O |
| Stage 2 LLM call (cold) | 3-8s | Sonnet 4 streaming, ~3-5k input tokens, ~1-3k output tokens |
| Stage 3 validation + assembly | <50ms | Schema check + floor enforcement |
| **Total p95 (cold)** | **~10s** | Acceptable for plan generation cadence |
| **Total p95 (cached)** | **<150ms** | Cache hit returns serialized payload |

**Caching coverage assumption:** ~70% of 3A invocations are cache hits in steady-state operation (plan-gen, plan-update, athlete self-check). The remaining 30% are cold runs after Layer 1 / 2A / integration data changes.

**Cost note.** Sonnet 4 input pricing at the expected ~5k input tokens / ~2k output tokens per call places 3A at roughly $0.05-0.10 per cold invocation (per current pricing — verify at deployment time). Plan-gen cadence: 1 cold call per athlete per ~14 days on average → ~$1-2/month/athlete for 3A alone.

## 12. Open items / forward references

| ID | Item | Disposition |
|---|---|---|
| 3A-1 | Per-field `evidence_basis` validation against a static field catalog | Defer to post-launch; current name-existence check is sufficient |
| 3A-2 | Coherence concern with 3B as separate LLM calls (per L3-Spec-Trio gut check) | Open. Revisit post-deployment after observing whether 3B's outputs drift from 3A's framing. Mitigation today: 3B's prompt includes 3A's output as input. |
| 3A-3 | Female-athlete HRmax adjustment factor (literature suggests sex-specific HRmax formulas) | Defer to post-launch when data density supports analysis |
| 3A-4 | Multi-locale athletes (different equipment / climate per locale) — does 3A produce one state or per-locale? | One state. Locale-specific adjustments are Layer 4's territory. |
| 3A-5 | Returning-from-injury athletes — how does 3A frame trajectory when 2D output says "returning to sport"? | Read 2D's `return_to_sport_phase` field (when 2D adds it) as additional context; for now, manual reasoning by the LLM using §B context |
| 3A-6 | LLM model choice — Sonnet 4 default; investigate cheaper Haiku for the routine cached case (90% of calls are cache hits, so model cost matters only on cold runs) | Defer; first measure actual cold-run rate in production |
| D-56 (existing) | `cardio_log.is_race`, `cardio_log.start_time` columns | Affects 3A's race-result and night-running observations; track in Backlog v11 |
| D-58 (existing) | Account-first onboarding flow | Reshapes which §C/§D/§F fields are prefilled; affects 3A's confidence calibration when prefilled-vs-manually-entered |

**Forward refs:**
- Layer 3B consumes `Layer3APayload`; see `Layer3_3B_Spec.md` (next session) for the input contract on 3B's side.
- Layer 3C consumes `Layer3APayload` alongside 2A/2D/2E payloads for cross-node conflict detection.
- Layer 3D consumes `Layer3APayload.notable_observations` (filtered to `elevates_to_hitl=True`) for the HITL gate.
- Layer 4 consumes the full payload for plan generation — `current_state.weak_links` drives accessory work; `recent_trajectory` drives volume ramp shape; `data_density` drives confidence-weighted prescription.

## 13. Test scenarios

A regression set 3A must pass before deployment. Each scenario is a fixture (Layer1Payload + Layer2APayload + IntegrationBundle) plus expected output shape (not exact text — the LLM has reasoning latitude — but specific enums and observation presence).

### 13.1 Dense data — adventure racer in peak phase

Fixture: AR athlete, 5 years training, 12 disciplines included, connected to Garmin + Polar, 28+ days of integration data, ACWR 1.18 combined.

Expected:
- `current_state.aerobic_capacity.level == 'strong'`, confidence = high
- `current_state.strength.level in ['good', 'strong']`
- `recent_trajectory.short_term.direction in ['building', 'peaking']`
- `recent_trajectory.confidence == 'high'`
- `acwr_status.combined.ratio` in [1.15, 1.21]
- `notable_observations` contains no warnings (clean state)

### 13.2 Sparse data — new athlete, 2 weeks logged

Fixture: 6 weeks training history total, 8 manual cardio_log entries, no providers, no §F testing complete.

Expected:
- All assessments confidence ≤ medium; aerobic and strength `level in ['moderate', 'insufficient_data']`
- `recent_trajectory.short_term.direction == 'building'` or `'insufficient_data'`
- `recent_trajectory.confidence == 'low'`
- At least 1 `data_gap` observation, `elevates_to_hitl=True`
- `acwr_status.combined is None`

### 13.3 Conflicting signals

Fixture: 12 hrs/wk logged volume (provider), §I stress reported as "very high", §I sleep avg 5.5 hrs, ACWR 1.45.

Expected:
- `current_state.aerobic_capacity.level in ['good', 'strong']`
- `recent_trajectory.short_term.direction in ['fatigued', 'overreached']`
- At least 1 `warning` observation about ACWR
- At least 1 `warning` or `data_hygiene` observation about subjective-objective tension

### 13.4 Returning athlete

Fixture: 8 years training history, peak volume 14 hrs/wk in §C, 0 workouts last 90 days, §F baselines from 2 years ago.

Expected:
- `current_state.aerobic_capacity.level` downgraded vs historical
- `recent_trajectory.short_term.direction == 'detrained'`
- `recent_trajectory.medium_term.direction == 'detrained'`
- `notable_observations` contains `opportunity` (prior base) and `data_gap` (stale §F)

### 13.5 Pregnancy-relevant fixture

Fixture: Female athlete, age 31, RHR elevated +12 from baseline. Pregnancy NOT captured (per v4).

Expected:
- 3A applies standard RHR-elevation observation (per §B trigger rules)
- No reference to pregnancy state in payload or reasoning
- No branching based on sex except where physiologically warranted (e.g., §F HRmax estimation caveats)

### 13.6 No providers but rich self-report

Fixture: 4 years training, rich §C/§D/§F/§I self-report, no providers connected, `cardio_log` has 35 entries last 28d (manual log).

Expected:
- `current_state.aerobic_capacity.level == 'good'` plausible with medium confidence
- `recent_trajectory.confidence == 'medium'` (no HRV / no provider-validated sleep)
- `notable_observations` contains `data_gap` about provider connection, `elevates_to_hitl=True`
- `acwr_status.combined` populated from cardio_log

### 13.7 All-zero athlete (defensive)

Fixture: §A complete, §C primary_sport missing.

Expected: §4 precondition fails with `Layer3AInputError("incomplete_onboarding")` before the LLM is called. (Test that the error code is correct and the LLM is not invoked.)

### 13.8 Model swap regression

Fixture: any scenario; run with model A and model B (e.g., Sonnet 4 vs Opus 4.7).

Expected: output schemas validate; enums in approved ranges; no schema errors. Drift in reasoning text is acceptable; drift in enum classifications by >1 step (e.g., 'good' → 'low') flags the swap as breaking.

### 13.9 Conflict-flag emission

Fixture: integration shows 10 hrs/wk, self-report says 6 hrs/wk (>25% divergence).

Expected: `data_hygiene` observation in `notable_observations` referencing both values; `evidence_basis` cites `integration.recent_workouts` and `section_c.current_weekly_volume_hours`.

### 13.10 ACWR red zone

Fixture: ACWR combined = 1.62 in build phase.

Expected: `warning` observation `elevates_to_hitl=True`; text references the specific ratio; `recent_trajectory.short_term.direction in ['overreached', 'fatigued']`.

## 14. Gut check

**What this spec gets right.**

The biggest win is collapsing L3-Discovery's two open questions (self-report vs integration weighting, confidence thresholds) into a single rule set in §6 that's prompted into the LLM and enforced by the validator. The LLM proposes; the floor enforces. This is the right shape for an LLM node where we want creativity inside guardrails — analogous to how 2A's LLM call respects deterministic constraints from `phase_load_allocation`.

The output schema separating `current_state` from `recent_trajectory`, and surfacing `data_density` as a first-class block, makes downstream consumption clean. 3B can read `recent_trajectory.confidence` and adjust its viability assertion strength; 3D can pull `notable_observations` filtered by `elevates_to_hitl=True`; Layer 4 can read `data_density` to choose between aggressive and conservative volume ramps. Nothing is implicit.

`evidence_basis` per assessment is the cheapest hedge against hallucination. The validator doesn't deeply check that the field's value supports the assessment, but it does check that the field exists — which catches the most common LLM failure mode (citing a field that doesn't appear in the input).

**Risks.**

**The LLM might still produce plausible-sounding but wrong reasoning, especially on sparse-data athletes.** Confidence floors help bound this, but a well-written `low confidence` assessment can still convince a downstream consumer it's actionable when it shouldn't be. Mitigation: 3D's HITL gate surfaces low-confidence trajectory before plan-gen. Athletes see and can dismiss/revise.

**Self-report vs integration weighting in §6.1 is a policy, not a tested rule.** "Subjective dominates for fatigue" is intuitively right but unproven. Athletes may chronically over- or under-report stress; the rule treats them as ground truth anyway. We'll learn the right calibration only after observing real outputs against athlete-confirmed reality.

**ACWR ratios in §7's ACWREntry assume `units` is consistent within a `q_layer3A_combined_load` output.** If `cardio_log` provides hours and Polar's `cardio_load` provides TRIMP, the combined ratio is meaningless. Mitigation: `q_layer3A_combined_load` normalizes to one unit (hours, by default — TRIMP requires a conversion factor with per-athlete calibration that isn't available pre-launch). 3A consumes a single-unit `combined`; the per-discipline rows may carry different units transparently.

**Stage 2 prompt structure is one-shot.** No iterative refinement, no chain-of-thought delegation. A single call produces the structured output. This is fast and cheap but means a single bad-input edge case can produce an unfortunate output. Mitigation: schema validation catches the worst categorical errors; confidence floors prevent over-claiming.

**Determinism is conditional.** Day-granular cache key is sound, but if Layer 1 data changes mid-day (athlete edits a §C field), the cache invalidates and the next call runs. This is correct behavior, but plan-gen consumers shouldn't assume "two calls within an hour return the same payload" — they might not.

**What might be missing.**

- **Sex-specific physiology beyond HRmax estimation.** Females have different fueling needs, different injury patterns, different recovery curves. 3A treats sex as context only. Future spec versions may need explicit branching for menstrual-cycle-aware recovery interpretation (when athletes opt-in to cycle tracking). Out of v1 scope.
- **Aging-athlete adjustments.** Recovery time, max HR, and strength curves all shift with age. 3A reads age but doesn't currently adjust thresholds by decade. The LLM may reason about it implicitly; explicit rules could be added.
- **Multi-event seasons.** §H may have two A-races in a year. 3A doesn't see §H at all (3B's territory). If the event spacing produces unusual trajectory shapes, 3A's interpretation may not flag the unusualness because it doesn't know about the spacing.
- **Detraining-while-cross-training detection.** An athlete who shifts from running to swimming for 8 weeks looks "detrained" in run-discipline ACWR but isn't truly detrained overall. The LLM may handle this via narrative reasoning but no rule enforces the synthesis.

**Best argument against this spec's approach.**

You could argue 3A should be split into a deterministic "summarize the data" step + a smaller LLM call for "interpret the summary." The split would make the LLM call cheaper and the reasoning more inspectable (you'd see the summary the LLM saw). Counter: the integration-bundle and Layer 1 payload are already structured; the LLM is consuming structured prompt sections, not raw rows. The summarization-step abstraction adds complexity without changing the inspection surface — `prompt_hash` in the metadata gives the same forensic capability.

Alternatively, you could argue 3A should produce *quantitative* assessments (e.g., aerobic capacity as a percentile or score, not an enum). Quantitative outputs are more precise and easier to compare across runs. Counter: the underlying data quality doesn't support quantitative precision — most §F baselines are stale, self-reported, or estimated. Enums force the LLM to make a judgment call it can defend in `reasoning_text`; a number would be false precision.

---

*End of Layer3_3A_Spec.*
