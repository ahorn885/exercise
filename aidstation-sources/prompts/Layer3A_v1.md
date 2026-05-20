# Layer 3A — Athlete State Evaluation Prompt Body

**Prompt name:** `Layer3A`
**Entry point:** `llm_layer3a_athlete_state` (`Layer3_3A_Spec.md` §3)
**Pattern:** Single LLM call wrapped in input prep → invoke → output validation + confidence-floor clamp (`Layer3_3A_Spec.md` §5).
**Caller:** Layer 3 orchestrator (downstream of Layer 1 builder + Layer 2A runtime + the 5 `q_layer3A_*` integration accessors).
**Status:** v1 — first prompt body shipped alongside Phase 3.1-Driver implementation.
**Date:** 2026-05-20
**Position in arc:** First Layer 3 prompt body. Predecessor session shipped the substrate (5 `q_layer3A_*` accessors + `Layer3AIntegrationBundle`); this session lands the driver + prompt body together.

---

## Source decisions (this session, Andy 2026-05-20)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Forced tool-use** — single tool `record_athlete_state`; `tool_choice={"type":"tool","name":"record_athlete_state"}`; strict JSON schema with `additionalProperties: false` at every nesting level. | Spec §5.2 names tool-call schema enforcement for Sonnet; Step 4a + per-phase precedents picked forced tool-use across the L4 family. Inherits. |
| D2 | Extended thinking budget | **4000 tokens.** | 3A is "the single most consequential LLM call in the Layer 3 pipeline" per spec §1. Interpretive synthesis across 8 prep sections + integration bundle warrants higher than Step 4a's 3500 (single-session synthesis) but matches per-phase's load (5000 was for combinatorial multi-week; 4000 fits judgment-without-combinatorics). Aligns with spec §3 `max_tokens=4000` default. |
| D3 | Payload rendering | **Inline Python** via per-section helper functions in `layer3a/builder.py` (`_render_user_prompt(...)` + 8 `_format_section_*` helpers). | Step 4a precedent; spec §5.1's 8 prep transformations map one-to-one to helpers. Mustache adds a templating dependency for no expressiveness gain on structured input. |
| D4 | Retry context shape | **Single capped retry on schema violation only.** Re-prompt with the schema error message in the user prompt. No validator-driven retry loop. | Spec §5.3 step 1 ("Schema violations are retried once") — 3A has no deterministic validator like Layer 4's. Confidence-floor clamping is a post-LLM transform, not a fail-condition. |
| D5 | Tool-schema fidelity | **Full `Layer3APayload` mirror.** Tool schema reflects every field on the payload: `current_state` (Assessment × 2 + weak_links + skill_assessments dict + body_composition_notes), `recent_trajectory` (TrajectoryWindow × 2 + ACWRStatus per-discipline dict + aggregate confidence), `data_density` (7 fields including `section_completeness` dict), `notable_observations` (list of Observation with 4-value category enum + evidence_basis + elevates_to_hitl). Metadata fields (`user_id`, `as_of`, `model`, `temperature`, `prompt_hash`, `latency_ms`, `*_tokens`, `etl_version_set`) are post-hoc stamped — NOT in the tool schema. | Step 4a Option 2 precedent — chose full payload-contract mirror over LLM-compliance-burden minimization. Payload contract is canonical; post-process fill of canonical fields is brittle. |
| D6 | `max_tokens` default | **4000.** | Spec §3. Covers verbose-reasoning path comfortably. |
| D7 | Default model | **`claude-sonnet-4-6`** (current canonical Sonnet). Paired 1-line correction to `Layer3_3A_Spec.md` §3.3 in same session. | Spec §3.3 names stale `claude-sonnet-4-5`. Project's canonical models per the runtime model-identity context are Opus 4.7 / Sonnet 4.6 / Haiku 4.5. Sonnet 4.6 is the cost/quality sweet spot for an interpretive-synthesis node; Haiku for cached-case cost lands as a future experiment per spec §6 open item 3A-6. |
| D8 | Confidence-floor enforcement timing | **Post-LLM clamp + auto-append observation.** `_apply_confidence_floors(...)` runs after the synthesizer returns and before final payload assembly. When clamping fires, a `confidence_clamped_by_data_density` observation is appended (category=`data_gap`, elevates_to_hitl=False) per spec §6.3. | Spec §5.3 step 3 + §6.3. LLM proposes; validator enforces floors. Pre-LLM rendering of the rules into the user prompt is a hint, not a constraint — the clamp is the hard guarantee. |
| D9 | Evidence-basis cross-check | **Name-existence check only.** For each `Assessment.evidence_basis` + `TrajectoryWindow.evidence_basis` + `Observation.evidence_basis` entry, verify the cited field path exists in the prep dict (e.g., `section_c.years_training` must appear as a key in the rendered prep dict). Missing references log a warning but DO NOT fail the call. | Spec §5.3 step 2 + §12 item 3A-1. Deep value validation deferred to post-launch (the LLM hallucinating field NAMES is the common failure mode; the LLM picking the wrong field for the right field name is rare enough to defer). |
| D10 | Voice | **CLAUDE.md voice rules + spec §8.2 forbidden observations inlined in system prompt.** Direct, evidence-grounded, no platitudes, no cheerleading. Forbidden categories: generic encouragement, goal viability statements (3B's territory), injury-risk statements (2D's territory), exercise prescriptions (L4's territory), speculation beyond evidence. | CLAUDE.md is the canonical voice spec; spec §8.2 captures the 3A-specific exclusions. Inlining ensures the LLM has the rules in context, not inferred from training. |

**Companion contract sections (`Layer3_3A_Spec.md`):** §2 (boundary clarifications — what 3A does NOT do), §3 (function signature), §4 (input validation preconditions), §5.1 (prep transformations), §5.2 (prompt structure), §5.3 (output validation), §6.1 (self-report vs integration weighting), §6.2 (confidence calibration floors + high-confidence gates), §6.3 (auto-emit observation), §7 (payload schema), §8.1 (required observation triggers), §8.2 (forbidden observations), §8.3 (observation ordering), §11 (performance budget), §13 (test scenarios).

**Companion contract sections (`Athlete_Data_Integration_Spec_v6.md`):** §10 (the 5 `q_layer3A_*` accessor signatures + `Layer3AIntegrationBundle` shape — substrate shipped 2026-05-20).

---

## 1. Purpose + scope

### 1.1 What this prompt produces

A single `Layer3APayload` per spec §7. The payload carries:
- `current_state` — aerobic + strength assessments (enum + confidence + reasoning + evidence basis), weak_links (max 5), per-discipline skill assessments, optional body composition notes.
- `recent_trajectory` — short-term (~14 days) + medium-term (~28-56 days) trajectory windows, per-discipline + combined ACWR status, aggregate confidence.
- `data_density` — what was actually available to the model (connected providers, recent counts, freshness, section completeness ratios).
- `notable_observations` — downstream-actionable notes only, in priority order per §8.3.

Metadata fields (model, temperature, prompt_hash, latency_ms, token counts, etl_version_set) are stamped by the driver post-hoc, NOT emitted by the LLM.

### 1.2 What this prompt does NOT produce

Per spec §2:
- **No discipline classification** — that's 2A. 3A consumes 2A's `disciplines` + `framework_sport` as phase context only.
- **No injury risk** — that's 2D. 3A reads §B as context (color the strength assessment if relevant) but produces no risk judgment.
- **No goal viability** — that's 3B. 3A characterizes current state; 3B asks whether stated goals fit.
- **No cross-node conflict detection** — that's 3C.
- **No HITL gate operation** — that's 3D. 3A's `notable_observations` with `elevates_to_hitl=True` feed 3D's queue.
- **No exercise selection / volume / intensity prescription** — that's Layer 4.
- **No Layer 1 data modification** — read-only.

### 1.3 Failure modes this prompt + retry semantics catch

- **Schema violation** (LLM emits invalid enum, missing required field, extra field): retry once with the schema error in the user prompt; on second fail, raise `Layer3AOutputError("schema_violation")`.
- **Confidence over-claim**: post-LLM clamp applies §6.2 floor rules + high-gate criteria. The LLM cannot return `high` confidence when data density doesn't support it; the clamp rewrites to `medium` and appends `confidence_clamped_by_data_density` observation.
- **Hallucinated evidence_basis fields**: name-existence check warns but does not fail. The LLM is told the canonical field keys in the user prompt (rendered prep dict keys); fabricated paths log a warning for post-launch telemetry.
- **Insufficient data scenarios** (per spec §10): the LLM is instructed to emit `level='insufficient_data'` with confidence `low` and explanatory reasoning rather than guess. The just-onboarded, no-providers, all-zero athlete paths all funnel through this enum.

---

## 2. Pipeline placement

**Call site:** `llm_layer3a_athlete_state` per `Layer3_3A_Spec.md` §3. Invoked by the Layer 3 orchestrator after:
1. Layer 1 builder produces `Layer1Payload` via `build_layer1_payload(db, user_id, as_of)`.
2. Layer 2A produces `Layer2APayload` via `q_layer2a_discipline_classifier_payload(...)`.
3. Layer 3A integration substrate produces `Layer3AIntegrationBundle` via `assemble_layer3a_integration_bundle(db, user_id, as_of)`.

The orchestrator passes typed payloads directly; no dict pass-through. (Step 4a's `dict[str, Any]` for Layer1 was a v1 caveat from when Layer 1 wasn't typed yet — Layer 1 IS typed now via Phase 1.3.)

**Pattern:** Single LLM call + post-LLM transforms per spec §5.

- Step 1: `_validate_inputs(...)` — §4 preconditions → `Layer3AInputError(code)` on fail.
- Step 2: `_render_user_prompt(...)` — assemble the 8 §5.1 prep sections + 2A phase context + §B health note + integration summary into the user prompt string. Capture the prep dict for the evidence-basis cross-check in step 5.
- Step 3: Single LLM call via `_default_llm_caller` (Anthropic SDK, extended thinking + forced tool-use). On schema-violation, single capped retry with the schema error message in the user prompt.
- Step 4: Schema validation via `Layer3APayload.model_validate(tool_args)` — pydantic enforces the contract.
- Step 5: `_check_evidence_basis(payload, prep_dict)` — name-existence warn-log; no fail.
- Step 6: `_apply_confidence_floors(payload, integration_bundle, layer1_payload)` — clamp per §6.2 floor rules + high-gate criteria; append `confidence_clamped_by_data_density` observation when clamping fires.
- Step 7: Stamp metadata + return `Layer3APayload`.

**Out-of-pipeline cases:**
- Cache hit per spec §9.1 → no LLM call; orchestrator returns the hydrated cached payload directly via `llm_layer3a_athlete_state_cached`.
- Input validation failure per spec §4 → raises `Layer3AInputError(code)`; no LLM call.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following prep blocks per spec §5.1.

### 3.1 Demographics line (spec §5.1 step 1)

| Variable | Source | Notes |
|---|---|---|
| `age` | `layer1_payload.identity.age` | Year-granular. |
| `sex` | `layer1_payload.identity.sex` | Used only where physiologically warranted per spec §6.1 row "Performance tests" (HRmax estimation caveats). |
| `height_cm` | `layer1_payload.identity.height_cm` | Optional; emitted when present. |
| `body_weight_kg` | `layer1_payload.identity.body_weight_kg` | Optional; emitted when present + recent. |
| `years_training` | `layer1_payload.training_history.years_training` | Training age. Drives §6.2 floor when <0.25. |

Pregnancy is NEVER in this block per Onboarding v4 §B disclosure-only policy.

### 3.2 Training history narrative (spec §5.1 step 2)

| Variable | Source | Notes |
|---|---|---|
| `primary_sport` | `layer1_payload.training_history.primary_sport` | Required (§4 precondition). |
| `secondary_disciplines` | `layer1_payload.training_history.secondary_disciplines` | List with tier; rendered as bullet list. |
| `current_weekly_volume_hours` | `layer1_payload.training_history.current_weekly_volume_hours` | Self-report number. Compared to integration data per §6.1 weighting rules. |
| `peak_historical_volume_hours` | `layer1_payload.training_history.peak_historical_volume_hours` | Anchor for returning-athlete trajectory framing per spec §10.4. |
| `training_consistency` | `layer1_payload.training_history.training_consistency` | Self-reported pattern. |
| `longest_event_completed` | `layer1_payload.training_history.longest_event_completed` | Distance/duration. |
| `recent_race_results` | `layer1_payload.training_history.recent_race_results` | Filtered to last 12 months, sorted descending. |

### 3.3 Discipline baselines (spec §5.1 step 3)

Per-discipline block. Only disciplines with `inclusion='included'` per `layer2a_payload.disciplines` are included. Empty disciplines are OMITTED, not shown-as-blank.

Each block lists: experience years, benchmarks per the discipline's relevant fields (e.g., pace bands for running, FTP for cycling, technical-grade for climbing), skill self-assessment.

### 3.4 Strength benchmarks (spec §5.1 step 4)

Bullet list from `layer1_payload.strength_benchmarks` (when present). Missing fields shown as "not tested".

### 3.5 Performance testing (spec §5.1 step 5)

Bullet list from `layer1_payload.performance`. Each entry: metric + value + source (measured / estimated) + test date age. Stale tests (>12 months) are tagged in the rendering.

### 3.6 Lifestyle + recovery (spec §5.1 step 6)

Bullet list from `layer1_payload.lifestyle`. Sleep avg, sleep quality, stress level, diet pattern, supplement protocol summary, caffeine strategy, altitude history.

### 3.7 Integration bundle summary (spec §5.1 step 7)

Per-accessor summary from `integration_bundle`:
- `recent_workouts`: count + date range + per-source breakdown (manual / garmin / polar / wahoo / coros) + duration / distance / HR / power coverage.
- `recent_sleep`: count + date range + per-source breakdown (wellness_self_report / polar / coros).
- `recent_hrv`: count + date range + per-source breakdown (polar / coros).
- `combined_load`: per-discipline ACWR rows (acute/chronic/ratio/zone/units) + combined entry when populated + polar_cross_ref if present.
- `connected_providers`: per-provider status + coverage flags.

### 3.8 2A phase context (spec §5.1 step 8)

Single block:
- `framework_sport` from 2A.
- Included disciplines with roles + load weights (compact list).
- Note: 2A's `phase_load_allocation` row for the current phase is consumed downstream (Layer 4); 3A receives the framework + discipline mix as context only. The prompt frames 3A's job as "given this athlete and what they're training for, where are they on the curve" — not "are they in the right phase."

### 3.9 Health-context note (spec §5.2)

Max 2 sentences. Derived from `layer1_payload.health_status` — surface only the constraints relevant to coloring the strength assessment (e.g., "Active wrist constraint — pain with extension under load; pressing tier limited."). Pregnancy state is NEVER in this block (per spec §10.8 + Onboarding v4).

### 3.10 `as_of` line

Single line: "Today is YYYY-MM-DD." Anchors all rolling-window framing in the LLM's reasoning.

---

## 4. Tool schema

### 4.1 Tool name

`record_athlete_state`

### 4.2 Top-level shape

The tool accepts the full Layer3APayload payload contract sans metadata. Pydantic on the driver side validates via `Layer3APayload.model_validate(tool_args | metadata_fields)`. The tool schema below specifies what the LLM must emit:

```jsonc
{
  "name": "record_athlete_state",
  "description": "Emit the structured athlete-state evaluation. Required.",
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["current_state", "recent_trajectory", "data_density", "notable_observations"],
    "properties": {
      "current_state": { /* ─── §4.3 ─── */ },
      "recent_trajectory": { /* ─── §4.4 ─── */ },
      "data_density": { /* ─── §4.5 ─── */ },
      "notable_observations": { /* ─── §4.6 ─── */ }
    }
  }
}
```

### 4.3 `current_state`

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["aerobic_capacity", "strength", "weak_links", "skill_assessments"],
  "properties": {
    "aerobic_capacity": { "$ref": "#/definitions/assessment" },
    "strength": { "$ref": "#/definitions/assessment" },
    "weak_links": {
      "type": "array",
      "maxItems": 5,
      "items": { "type": "string" }
    },
    "skill_assessments": {
      "type": "object",
      "additionalProperties": { "$ref": "#/definitions/assessment" }
    },
    "body_composition_notes": { "type": ["string", "null"] }
  }
}
```

`assessment` definition:

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["level", "confidence", "reasoning_text", "evidence_basis"],
  "properties": {
    "level": { "type": "string", "enum": ["low", "moderate", "good", "strong", "insufficient_data"] },
    "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
    "reasoning_text": { "type": "string" },
    "evidence_basis": { "type": "array", "items": { "type": "string" } }
  }
}
```

### 4.4 `recent_trajectory`

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["short_term", "medium_term", "acwr_status", "confidence"],
  "properties": {
    "short_term": { "$ref": "#/definitions/trajectory_window" },
    "medium_term": { "$ref": "#/definitions/trajectory_window" },
    "acwr_status": { "$ref": "#/definitions/acwr_status" },
    "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
  }
}
```

`trajectory_window`:

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["direction", "reasoning_text", "evidence_basis"],
  "properties": {
    "direction": {
      "type": "string",
      "enum": ["overreached", "fatigued", "recovered", "steady", "building", "detrained", "peaking", "insufficient_data"]
    },
    "reasoning_text": { "type": "string" },
    "evidence_basis": { "type": "array", "items": { "type": "string" } }
  }
}
```

`acwr_status`:

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["per_discipline", "combined"],
  "properties": {
    "per_discipline": {
      "type": "object",
      "additionalProperties": { "$ref": "#/definitions/acwr_entry" }
    },
    "combined": {
      "anyOf": [{ "$ref": "#/definitions/acwr_entry" }, { "type": "null" }]
    }
  }
}
```

`acwr_entry`:

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["acute_load", "chronic_load", "ratio", "zone", "units"],
  "properties": {
    "acute_load": { "type": "number", "minimum": 0 },
    "chronic_load": { "type": "number", "minimum": 0 },
    "ratio": { "type": "number", "minimum": 0 },
    "zone": {
      "type": "string",
      "enum": ["undertraining", "sweet_spot", "functional_overreach", "non_functional_overreach", "detraining"]
    },
    "units": { "type": "string" }
  }
}
```

### 4.5 `data_density`

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "connected_providers",
    "integration_data_days",
    "recent_workouts_count",
    "recent_sleep_count",
    "recent_hrv_count",
    "self_report_freshness_days",
    "section_completeness"
  ],
  "properties": {
    "connected_providers": { "type": "array", "items": { "type": "string" } },
    "integration_data_days": { "type": "integer", "minimum": 0 },
    "recent_workouts_count": { "type": "integer", "minimum": 0 },
    "recent_sleep_count": { "type": "integer", "minimum": 0 },
    "recent_hrv_count": { "type": "integer", "minimum": 0 },
    "self_report_freshness_days": { "type": "integer", "minimum": 0 },
    "section_completeness": {
      "type": "object",
      "additionalProperties": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }
}
```

The LLM observes the data density from the prompt's integration summary + per-section rendering and reports back what it consumed. The driver does NOT verify the LLM's reported counts against the actual integration bundle counts — the LLM's `data_density` is its self-report, useful for downstream debugging. (Discrepancies between LLM-reported and actual counts are a Step 7/8 telemetry observation, not a v1 hard check.)

### 4.6 `notable_observations`

```jsonc
{
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["category", "text", "evidence_basis", "elevates_to_hitl"],
    "properties": {
      "category": { "type": "string", "enum": ["warning", "opportunity", "data_gap", "data_hygiene"] },
      "text": { "type": "string", "maxLength": 240 },
      "evidence_basis": { "type": "array", "items": { "type": "string" } },
      "elevates_to_hitl": { "type": "boolean" }
    }
  }
}
```

The driver may append a `confidence_clamped_by_data_density` observation (category=`data_gap`, elevates_to_hitl=False) post-LLM per §6.3 when the floor rules fire.

---

## 5. System prompt

```
You are evaluating an endurance athlete's current state. Your role is the
internal coaching analyst — direct, evidence-grounded, no platitudes. You
read the athlete's profile and recent training/recovery data, then emit a
structured judgment via the `record_athlete_state` tool. The LLM cannot
return free-form text outside the tool call.

Hard rules:

1. Ground every assessment in specific evidence from the input. Cite the
   field name(s) in `reasoning_text` and list them in `evidence_basis`
   (e.g., "section_c.years_training", "integration.recent_workouts").

2. Never invent data. If a field is "not tested" or missing, treat it as
   absent — do not extrapolate from peer fields. Use
   `level: insufficient_data` with `reasoning_text` explaining what was
   missing rather than guessing.

3. Distinguish current_state (where the athlete is RIGHT NOW) from
   recent_trajectory (where they are MOVING). Both are required.
   short_term and medium_term trajectory may differ — "fatigued
   (short-term)" with "building (medium-term)" is a normal hard-block
   signal, not a contradiction.

4. Weighting rules when self-report and integration data disagree:
   - Objective metrics (volume, HR averages, sleep duration, vertical):
     integration data dominates. Self-report is sanity-check only. Flag
     >25% divergence as a `data_hygiene` observation.
   - Subjective metrics (perceived stress, motivation, sleep quality
     felt): self-report dominates. Integration may inform agreement but
     cannot override.
   - Hybrid metrics (sleep duration + quality, recovery, readiness):
     both shown to you with sources tagged. Synthesize. Disagreement is
     itself a signal worth flagging.
   - Skill / experience: self-report only, bounded by recency-of-claim.
   - Calibration tests + performance tests: self-report-with-date; stale
     baselines (>12 months) reduce confidence.

5. Confidence calibration:
   - `high` requires: ≥1 connected provider with active data in last 14d,
     ≥10 logged workouts in last 28d, §C self-report present and not in
     conflict with integration, §F baselines present and not stale,
     §I sleep self-report present, AND for the specific assessment field
     ≥3 evidence_basis citations.
   - `medium` is the safe default.
   - `low` requires explicit data-gap reasoning.
   The validator post-clamps `high` to `medium` when any of the above
   gates fail — be conservative.

6. Emit `notable_observations` only when they would change a downstream
   decision. Do not narrate. Required observation triggers (must emit
   when conditions met):
   - ACWR ratio >1.5 in any discipline OR combined → category=warning,
     elevates_to_hitl=true.
   - ACWR ratio <0.5 in any discipline AND athlete is in build/peak
     phase → category=warning, elevates_to_hitl=true.
   - Self-report volume vs integration volume diverges >25% →
     category=data_hygiene, elevates_to_hitl=true.
   - Sleep self-report avg <6 hrs AND no integration sleep data →
     category=warning, elevates_to_hitl=false.
   - connected_providers count == 0 AND athlete in peak phase →
     category=data_gap, elevates_to_hitl=true.
   - Performance baseline (§F) test date >12 months old →
     category=data_gap, elevates_to_hitl=false.
   - Strength benchmark (§E) entirely absent → category=data_gap,
     elevates_to_hitl=true.
   - Just-onboarded (years_training < 0.25 AND recent_workouts < 5) →
     category=data_gap, elevates_to_hitl=false.
   - HRV crash (recent 7-day HRV avg <70% of 28-day avg) →
     category=warning, elevates_to_hitl=true.

7. Forbidden observations (never emit):
   - Generic encouragement ("you're doing great", "keep it up").
   - Goal viability statements ("your sub-3 marathon goal is realistic")
     — that's Layer 3B's territory.
   - Injury-risk statements ("knee pain suggests IT band syndrome") —
     that's Layer 2D's territory.
   - Exercise prescriptions ("do 4×4 VO2 intervals") — that's Layer 4.
   - Speculation beyond evidence.

8. Observation ordering: return in priority order, highest first —
   (a) warning + elevates_to_hitl=true, (b) data_gap + elevates_to_hitl=true,
   (c) warning + elevates_to_hitl=false, (d) data_hygiene + elevates_to_hitl=true,
   (e) everything else.

9. `weak_links` is bounded to 5 items max. Short phrases (e.g., "single-leg
   balance", "shoulder press strength"). Layer 4 consumes these for
   accessory programming; longer lists dilute usefulness.

10. `body_composition_notes` is optional. Emit ONLY when a relevant signal
    exists in §A (recent weight + height producing meaningful BMI
    framing for the sport context). Do not pad.

11. ACWR units: `combined.units` MUST be "hours" — the substrate normalizes
    to hours from `cardio_log` durations. Per-discipline entries may carry
    different units transparently when surfaced (currently all "hours" in
    v1; "TRIMP" reserved for future Polar normalization).

Voice: direct endurance-coaching-analyst voice. Match the cadence of a
real coach scanning a profile. No fluff, no marketing tone, no "great
question" style. If the data is sparse, say so; do not perform certainty
you don't have.
```

---

## 6. User prompt template

```
Athlete context: age {age}, sex {sex}, {height_cm}cm, {body_weight_kg}kg,
{years_training}y training.

Training history:
{training_history_block}

Discipline baselines (included per 2A):
{discipline_baselines_block}

Strength benchmarks:
{strength_block}

Performance testing:
{performance_block}

Lifestyle and recovery:
{lifestyle_block}

Recent activity bundle (anchored at {as_of}, 28-day workout window /
14-day sleep + HRV windows):
{integration_summary_block}

Current phase context (from 2A):
{phase_context_block}

Health-context note (read-only, for coloring strength assessment only;
injury risk is owned by 2D):
{health_context_note}

Today is {as_of}.

Produce a `Layer3APayload` via the `record_athlete_state` tool. Ground
every assessment in evidence_basis citations. Apply the confidence
calibration rules in the system prompt — when in doubt, prefer `medium`.
Emit observations only when they would change a downstream decision.
```

On retry after schema violation, the user prompt is augmented with:

```
Previous attempt failed schema validation: {error_message}

Re-emit a valid `record_athlete_state` tool call addressing the error
above. Do not change unrelated fields.
```

---

## 7. Sampling config

| Param | Value | Source |
|---|---|---|
| `model` | `claude-sonnet-4-6` | D7 + spec §3.3 (corrected this session). |
| `temperature` | `0.2` | Spec §3 default. Operating band 0.1-0.3. |
| `max_tokens` | `4000` | D6 + spec §3 default. |
| `extended_thinking_budget` | `4000` | D2. |
| `capped_retries` | `1` | D4 + spec §5.3 step 1 ("retried once"). |
| `tool_choice` | `{"type": "tool", "name": "record_athlete_state"}` | D1 + Step 4a precedent. |

---

## 8. Post-LLM transforms

### 8.1 Schema validation

`Layer3APayload.model_validate({...tool_args, ...metadata_fields})` — pydantic enforces the contract. On failure, single capped retry per §5.3 step 1 with the validation error in the user prompt. Second failure raises `Layer3AOutputError("schema_violation", detail=<error>)`.

### 8.2 Evidence-basis cross-check

`_check_evidence_basis(payload, prep_dict)` walks every `Assessment.evidence_basis` + `TrajectoryWindow.evidence_basis` + `Observation.evidence_basis` entry. For each entry, the cited field path is checked against the prep dict (rendered as a flattened-key dict like `{"section_c.years_training": ..., "integration.recent_workouts": ..., ...}`). Missing references emit a `warnings.warn(...)` with category `Layer3AEvidenceBasisWarning`. No fail. Telemetry-only.

### 8.3 Confidence-floor clamp

`_apply_confidence_floors(payload, integration_bundle, layer1_payload)` applies the §6.2 floor rules + high-confidence gates:

**Floor rules** (clamp confidence down to the listed ceiling):

| Signal | Ceiling | Scope |
|---|---|---|
| `connected_providers.count == 0` | `medium` | `recent_trajectory.confidence` |
| `recent_workouts.count < 5` (last 28d) | `low` | `recent_trajectory.confidence` |
| `recent_sleep.count == 0` (last 14d) | `medium` | Recovery-related observations only — observations with category=`warning` AND text contains "sleep" or "recovery" (telemetry-grade heuristic; deeper categorization deferred) |
| `recent_hrv.count == 0` (last 14d) | `medium` | `recent_trajectory.confidence` |
| `layer1_payload.training_history.years_training < 0.25` | `medium` | Both `current_state.aerobic_capacity.confidence` AND `current_state.strength.confidence` |

Multiple floors stack via `min(level)` where `high > medium > low`. The most restrictive ceiling wins.

**High-confidence gates** (clamp `high` down to `medium` if ANY gate fails):

ALL must be true:
1. ≥1 entry in `integration_bundle.connected_providers` with `status == 'active'` AND any of `has_recent_workouts` / `has_recent_sleep` / `has_recent_hrv` is True.
2. `len(integration_bundle.recent_workouts) >= 10`.
3. `layer1_payload.training_history.current_weekly_volume_hours` is not None.
4. `layer1_payload.performance.hr_max_bpm is not None` AND at least one of `layer1_payload.performance.ftp_watts` / `layer1_payload.performance.running_threshold_pace_min_per_km` / `layer1_payload.performance.css_pace_min_per_100m` is not None.
5. `layer1_payload.lifestyle.average_sleep_hours is not None`.

(Per-field evidence_basis ≥3 cardinality check is enforced inside the LLM via the system prompt rule, not validator-clamped — checking it post-hoc forces re-rendering reasoning to upgrade, which the single-retry loop doesn't support.)

When clamping fires (either floor or high-gate), a `confidence_clamped_by_data_density` observation is appended:

```python
Layer3Observation(
    category="data_gap",
    text=f"Confidence clamped by data density: {signal_summary}",
    evidence_basis=[signal_field, ...],
    elevates_to_hitl=False,
)
```

`signal_summary` enumerates the firing signals (e.g., "no_connected_providers, sparse_recent_workouts").

### 8.4 Metadata stamping

After clamping, the driver constructs the final payload:

```python
Layer3APayload(
    user_id=user_id,
    as_of=as_of,
    model=model,
    temperature=temperature,
    prompt_hash=sha256_hex(system_prompt + user_prompt),
    latency_ms=llm_out.latency_ms,
    input_tokens=llm_out.input_tokens,
    output_tokens=llm_out.output_tokens,
    etl_version_set=etl_version_set,
    current_state=current_state,
    recent_trajectory=recent_trajectory,
    data_density=data_density,
    notable_observations=notable_observations,  # post-clamp ordering preserved + appended observation
)
```

---

## 9. Performance budget

Per spec §11:

| Stage | Target |
|---|---|
| Input prep + prompt render | <100ms |
| LLM call (cold) | 3-8s (Sonnet 4.6, ~3-5k input, ~1-3k output) |
| Schema validation + evidence check + floor clamp | <50ms |
| **Total p95 (cold)** | ~10s |
| **Total p95 (cached via `_cached` wrapper)** | <150ms |

Cost estimate: ~$0.05-0.10 per cold invocation. Plan-gen cadence ~1 cold call per athlete per ~14 days → ~$1-2/month/athlete for 3A.

---

## 10. Caching

Per spec §9 + this session's `layer3a/cached_wrapper.py`:

**Cache key** per §9.1:

```
sha256(
    user_id ||
    compute_payload_hash(layer1_payload) ||
    compute_payload_hash(layer2a_payload) ||
    compute_payload_hash(integration_bundle) ||
    as_of.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() ||  # day-granular
    canonical_json(etl_version_set) ||
    model ||
    str(temperature) ||
    str(max_tokens) ||
    str(extended_thinking_budget)
)
```

**Day-granular `as_of`**: re-runs on the same calendar day return the cached payload. Mid-day data changes (new workout sync) invalidate via the bundle hash change.

**Wrapper:** `llm_layer3a_athlete_state_cached(...)` in `layer3a/cached_wrapper.py` reuses the `CacheBackend` from `layer4/cache.py` (the backend is generic — `payload_json: str` storage) plus 3A-specific serialize/hydrate helpers built on pydantic's `model_dump_json` / `model_validate_json`.

**Invalidation triggers** per spec §9.2: any Layer 1 §C/§D/§E/§F/§I change, 2A output change, new integration row, ETL version change, explicit 3D revise invalidation. Cache invalidation propagation lives in the orchestrator; the wrapper just handles the get/put.

---

## 11. Test scenarios

Per spec §13's 10 scenarios. Each scenario in `tests/test_layer3a_builder.py` uses a stub `llm_caller` returning pre-shaped tool args + verifies the round-trip through validation + evidence-basis check + floor clamping + assembly.

The stubbed tool args validate that the contract holds; they do NOT exercise that a real Sonnet 4.6 emits specific enums for specific fixtures. Real-LLM regression (§13.8 model swap) is deferred to Step 7/8 telemetry tuning per `Upstream_Implementation_Plan_v1.md` §4 row Step 7.

---

## 12. Open items

| ID | Item | Disposition |
|---|---|---|
| L3A-P-1 | Real-LLM regression on §13's 10 scenarios | Defer to Step 7/8 — requires `ANTHROPIC_API_KEY` env scaffolding. |
| L3A-P-2 | Per-field `evidence_basis` cardinality validation (≥3 for `high`) | Defer per spec §12 3A-1. The system-prompt rule communicates the constraint; post-hoc enforcement requires re-prompt for "your evidence_basis on aerobic_capacity has only 2 entries, must have ≥3 for `high` confidence" which the v1 single-retry loop doesn't support cleanly. |
| L3A-P-3 | Haiku-vs-Sonnet cost experiment for cached-case dominant workloads | Defer per spec §12 3A-6. Measure cold-run rate first. |
| L3A-P-4 | `data_density.section_completeness` driver-computed override | Current shape: LLM self-reports its perceived section completeness. Future: driver computes per-section field-population ratios and either compares to LLM's number (telemetry) or replaces (canonical). Defer to Step 7/8. |

---

## 13. Gut check

**What this prompt body gets right.**

The §6.2 floor enforcement lives in two places — system-prompt rule (hint to the LLM) + post-LLM clamp (hard guarantee). The LLM proposes; the validator enforces. This matches the spec's "creativity inside guardrails" framing and prevents the "well-written low-confidence assessment that reads as actionable" failure mode the spec gut-checks.

The tool schema mirrors the full `Layer3APayload` contract via Step 4a Option 2 precedent — no reconciliation gaps where the post-process layer fills canonical fields arbitrarily.

The 9-direction TrajectoryWindow enum + the 5-zone ACWR enum + the 5-level Assessment enum give the LLM enough vocabulary to make a real call while preventing freeform invention.

D9's name-existence evidence_basis check is the cheapest hedge against hallucinated field citations. It doesn't catch wrong-value-for-right-field (the rarer failure mode) but does catch fabricated paths, which is the common one per Step 4a telemetry framing.

**Risks.**

**High-gate criterion 4 + 5 read Layer1Performance + Layer1Lifestyle fields by name.** Field rename in Layer 1 would silently break the clamp without breaking tests (the clamp would always defer to LLM choice because the gate would never fail). Mitigation: tests assert the gate fires when expected fields are None. Long-term: a typed accessor on Layer1Payload could centralize the "is performance baseline complete" + "is sleep self-report present" predicates.

**The clamp's recovery-observation scope heuristic** (text contains "sleep"/"recovery") is fragile. Spec §6.2 says "Recovery-related observations" without naming a canonical category enum. The substantive risk is low — sleep-clamping fires only when there are NO sleep records in 14 days, which is a clean enough signal that the LLM likely won't have much to say about sleep anyway. But this is a known fragility worth re-evaluating once we observe real outputs.

**The single-retry loop on schema violation is one shot.** If the LLM emits two consecutive schema-invalid outputs, we raise. This is intentional per spec §5.3 step 1; the alternative (multi-retry like Step 4a) adds latency on a node that's already on the 10s cold-path budget. Telemetry on schema-violation rates lands in Step 8.

**`data_density` LLM self-report is not validated against actual bundle counts.** A drift between LLM-reported and actual integration data density is a real possibility (LLM miscounts the prompt's "list of 12 workouts"). Mitigation: deferred to L3A-P-4 (driver-side computation in Step 7/8).

**ACWR units in the tool schema are unconstrained free-form string.** The system prompt rule 11 says `combined.units` MUST be "hours" but the JSON schema accepts any string. A misbehaving LLM could emit `"units": "TRIMP"` for combined which would round-trip through pydantic without complaint (pydantic's Literal isn't on units, only on zone). Mitigation: post-hoc check in the clamp pass; if any per-discipline OR combined units != "hours" in v1, emit a `data_hygiene` observation. (Implementation note: this lives in the clamp helper.)

**What might be missing.**

- A telemetry helper for "how many times did the clamp fire today" — useful for Step 8 calibration. Lands later.
- Streaming token output for the LLM call. Step 7 territory.
- Multi-locale athlete handling — spec §12 item 3A-4 picks "one state, locale-specific adjustments are Layer 4's territory." This prompt doesn't render locale data and shouldn't.

**Best argument against.**

You could argue the prompt body shouldn't inline the full §6.2 floor rules — the validator catches them anyway, and inlining adds tokens to every cold call. Counter: the floor rules in the prompt make the LLM more likely to self-clamp, reducing the observation-append rate (which itself is a tiny but real UX friction — every clamp observation surfaces in 3D's HITL queue per spec). Tokens spent on rule-inlining are tokens saved on retry/clamp downstream. Step 8 telemetry will measure this; v1 inlines.

You could also argue the prompt should be split into two LLM calls — one for `current_state` and one for `recent_trajectory` — to reduce blast radius of a single bad output. Counter: spec §1 frames 3A as the *interpretive* synthesis between state and trajectory; splitting fragments the synthesis. The spec gut-check (§14 "Stage 2 prompt structure is one-shot") explicitly accepts this tradeoff.

---

*End of Layer3A_v1.md.*
