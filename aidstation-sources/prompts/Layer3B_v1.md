# Layer 3B — Goal-Timeline-Viability Prompt Body

**Prompt name:** `Layer3B`
**Entry point:** `llm_layer3b_goal_timeline_viability` (`Layer3_3B_Spec.md` §3)
**Pattern:** Single LLM call wrapped in input prep → invoke → schema-retry → mode-discriminator → evidence-basis check → HITL auto-emit → confidence-floor clamp → periodization-sanity loop → metadata stamp (`Layer3_3B_Spec.md` §5).
**Caller:** Layer 3 orchestrator (downstream of Layer 1 builder + Layer 2A runtime + Layer 3A driver + the orchestrator-side target-`race_events` join).
**Status:** v1 — first 3B prompt body shipped alongside Phase 4 implementation.
**Date:** 2026-05-20
**Position in arc:** Second Layer 3 prompt body (3A shipped same day; 3B closes Phase 3+4 LLM-driver pair).

---

## Source decisions (this session, Andy 2026-05-20)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Forced tool-use** — single tool `emit_layer3b_payload`; `tool_choice={"type":"tool","name":"emit_layer3b_payload"}`; strict JSON schema with `additionalProperties: false` at every nesting level. | Spec §5.4 names this exact tool name + forced-tool-use shape. Inherits the 3A D1 precedent + Step 4a Layer 4 precedent. |
| D2 | Extended thinking budget | **3000 tokens** (lighter than 3A's 4000). | 3B reads 3A's already-synthesized output + 2A's discipline structure + applies §6 guardrails to decide viability + shape. Less interpretive synthesis than 3A (which is the "interpretive synthesis between state and trajectory" per spec §1). Spec §11 input budget <3,500 tokens supports a smaller thinking pass. |
| D3 | Payload rendering | **Inline Python** via per-block helper functions in `layer3b/builder.py` (`_render_block_1_timeline`, `_render_block_2_goal_context`, `_render_block_3_state_excerpt`, `_render_block_4_discipline_load`). | Spec §5.1's 4 blocks map one-to-one to helpers. Same as 3A D3 + Step 4a precedent. |
| D4 | Retry shape | **Two independent capped retries** — (a) single retry on schema violation per spec §5.5 step 1; (b) single retry on periodization-shape sanity violation per spec §5.5 step 4 with fallback-to-standard on persistent failure. Worst case 3 LLM attempts. | Spec §5.5 explicitly defines both retry paths. Schema-retry mirrors 3A's; sanity-retry is 3B-specific because §6.2 `custom`-mode phase_weeks has a hard semantic invariant beyond pydantic. |
| D5 | Tool-schema fidelity | **Full `Layer3BPayload` mirror** — GoalViability + PeriodizationShape + Layer3BHITLItem + Layer3Observation + the 4 D-66 event-metadata fields. All §7 schema-level rules (mode-discriminator on event-metadata; suggested_adjustments non-empty when viability≠'achievable'; phase_weeks iff mode=='custom'; hitl_surface unique labels; acknowledge_option None when severity=='blocker') are pydantic model_validators on the deployed payload + cross-validated in the driver. | Same as 3A D5 + Step 4a Option 2 precedent. Post-process fill of canonical fields is brittle. |
| D6 | `max_tokens` default | **2000.** | Spec §5.4 literal. Layer3BPayload output is smaller than Layer3APayload (no 7-field data_density, no per-discipline ACWR dicts). |
| D7 | Default model | **`claude-sonnet-4-6`** per spec §3 + §11. | Spec already names the canonical model (no §3.3 stale literal like 3A had). |
| D8 | Confidence-floor enforcement | **Post-LLM clamp + auto-append `confidence_clamped_by_data_signal` observation.** 4 floor rules per spec §6.5: (1) first_time + competitive goal → ≤medium; (2) 3A `recent_trajectory.confidence == 'low'` → ≤medium; (3) no-event + no providers + self_report_freshness >30d → ≤low; (4) event-mode + no previous_attempts + first_time → ≤medium. | Same shape as 3A D8 + spec §6.5. LLM proposes; validator enforces floors. |
| D9 | Evidence-basis cross-check | **Name-existence check (warn-only) + mode-discriminator on evidence_basis paths (warn-only).** §7 schema rule: event-mode `goal_viability.evidence_basis` must reference at least one §H.2 field; no-event must reference §H.3 fields only. Telemetry-grade enforcement (no fail). | Stricter than 3A's single-rule evidence_basis (3A is name-existence only). 3B's mode-discriminator on paths is spec §7 mandatory but enforcing as hard error breaks v1 §H.2 deployed-shape gap (see D11). Warn now; tighten post-form-refresh. |
| D10 | Voice | **CLAUDE.md voice + spec §5.2 system prompt verbatim** (direct, evidence-grounded, no platitudes; §6.1 HITL thresholds + §6.2 periodization vocab + §6.5 floor rules + §6.6 no-event heuristics + §8.1 required-observation triggers + §8.2 observation budget inlined). | Same as 3A D10 + spec §5.2 names the verbatim inline. |
| D11 | **Input-shape** (3B-specific) | **Raw payloads** — driver takes `Layer1Payload + Layer3APayload + Layer2APayload + RaceEventPayload \| None + current_date + etl_version_set` plus optional kwargs for the §H.2 fields not yet on deployed schema (`goal_outcome`, `first_time_at_distance`, `previous_attempts`, `time_goal`, `race_distance_km`, `race_duration_hr`, `race_terrain`, `race_pack_weight_kg`, `navigation_required`). Mode determination: `mode = "event" if race_event_payload is not None else "no-event"`. No new `SectionHGoalContext`/`SectionCContext` types — driver slices §H + §C internally. | Spec §3's `SectionHGoalContext`/`SectionCContext` naming is design-time scaffolding. Mirrors 3A precedent (raw `Layer1Payload`). The deployed §H.2 fields gap (none of `goal_outcome` / `first_time_at_distance` / `previous_attempts` / etc. exist on `Layer1EventGoal` or `RaceEventPayload`) is captured in CARRY_FORWARD as Phase 3.1-Driver/Phase 4 deferred onboarding-form work; v1 kwargs are `None`-tolerant. |
| D12 | **HITL auto-emit** (3B-specific) | **Validator-enforced auto-emit** of the 4 spec §6.1 HITL items when conditions met, even if the LLM omitted them. Validator checks the spec §6.1 conditions against the input plus the LLM-emitted viability + periodization_shape, appends missing-but-required items in dedup. | Spec §5.5 step 3 names this as mandatory. Mirrors 3A's required-observation pattern but for HITL items — the LLM proposes; the validator enforces the contract. |
| D13 | **Periodization-shape sanity loop** (3B-specific) | **Per spec §5.5 step 4** — for `mode == 'custom'`, phase_weeks must sum to `time_to_event_weeks` (event-mode) or `plan_duration_weeks` (no-event) within ±1. Out-of-range → re-prompt once with the deviation error; persistent failure → fall back to `mode='standard'` (preserving LLM's `start_phase` + `reasoning_text`) + auto-append `periodization_shape_fallback` observation. | Spec §5.5 step 4 — the only place 3B has a hard semantic validator beyond schema. Fallback path keeps the call non-fatal; observation surfaces the override to downstream. |
| D14 | **Event metadata population** (D-66 paired amendment) | **Driver populates the 4 event-metadata fields from `race_event_payload` when `mode=='event'`**: `event_date = race_event_payload.event_date`; `event_locale_id = race_event_payload.event_locale_id`; `race_format = race_event_payload.race_format`; `time_to_event_weeks = max(0, (event_date - current_date).days // 7)`. When `mode=='no-event'`, all 4 fields stay None (pydantic model_validator enforces this). | Spec §7 D-66 paired amendment + `Layer3BPayload._check_event_mode_consistency`. Closes the former "Layer 3B caller-side rewire" D-72 forward-pointer half. |

**Companion contract sections (`Layer3_3B_Spec.md`):** §2 (boundary clarifications — what 3B does NOT do), §3 (function signature), §4 (input validation preconditions), §5.1 (block assembly), §5.2 (system prompt skeleton), §5.3 (time-to-event phase bands), §5.4 (LLM call shape), §5.5 (post-LLM validation + payload assembly), §6.1 (HITL trigger thresholds), §6.2 (periodization-shape vocabulary), §6.4 (race-date-in-past as fatal), §6.5 (confidence-floor rules), §6.6 (no-event-mode handling), §7 (payload schema + schema-level rules + D-66 paired amendment), §8.1 (required observation auto-emit triggers), §8.2 (observation budget), §11 (performance budget), §13 (test scenarios TS-1..TS-8).

**Companion contract sections (`Race_Events_D66_Design_v1.md`):** §8.1 (3B reads target row), §8.2 (output shape unchanged), §8.3 (no-target case — paired doc-sweep fix this session: `mode='open_ended'` → `mode='no-event'` to match canonical `Layer3BPayload.mode: Literal["event","no-event"]`).

---

## 1. Purpose + scope

### 1.1 What this prompt produces

A single `Layer3BPayload` per spec §7. The payload carries:

- `goal_viability` — viability enum (`achievable` / `achievable-with-adjustment` / `unrealistic-as-stated`) + confidence + reasoning_text + evidence_basis + suggested_adjustments.
- `periodization_shape` — mode (`standard` / `compressed` / `extended` / `custom`) + start_phase (`Base` / `Build` / `Peak` / `Taper`) + optional `phase_weeks` (custom-mode only) + reasoning_text + evidence_basis.
- `hitl_surface` — list of `Layer3BHITLItem` (the LLM's proposed items + validator-auto-emitted §6.1 items, deduplicated by `item_label`).
- `notable_observations` — downstream-actionable notes only, bounded to 6 items per §8.2 priority ordering.

Metadata fields (model, temperature, prompt_hash, latency_ms, token counts, etl_version_set) are stamped by the driver post-hoc — NOT emitted by the LLM. The D-66 event-metadata fields (event_date, event_locale_id, race_format, time_to_event_weeks) are populated by the driver from `race_event_payload` per D14 — NOT emitted by the LLM (the LLM doesn't have date-arithmetic-against-current_date as a job).

### 1.2 What this prompt does NOT produce

Per spec §2:

- **No plan generation.** That's Layer 4. 3B produces the *shape* (mode + phase sizes), not the session contents.
- **No exercise enumeration.** That's Layer 4 against 2C's exercise pool.
- **No re-derivation of 3A's current_state or recent_trajectory.** Read as given.
- **No injury-vs-discipline calls.** That's 2D. 3B treats 2A's discipline list as authoritative.
- **No interpretation of Layer 0 reference data.** Reads 2A's typed payload only.
- **No pivot to "results mode" if race already happened.** Race-date-in-past is a fatal validation error per spec §6.4 + §4 rule 1.
- **No intermediate-race scheduling.** 3B may flag the opportunity (per §8.1 row 3) but Layer 4 decides specifics.
- **No partial-update invalidation logic.** Orchestrator owns cache invalidation per spec §9.2.

### 1.3 Failure modes this prompt + retry semantics catch

- **Schema violation** (LLM emits invalid enum, missing required field, extra field, mode-discriminator mismatch): retry once with the schema error in the user prompt; second failure raises `Layer3BOutputError("schema_violation")`.
- **Periodization-sanity violation** (custom mode + phase_weeks sum outside ±1 of timeline): retry once with the deviation error; persistent failure falls back to `mode='standard'` + auto-append `periodization_shape_fallback` observation. NON-fatal.
- **Confidence over-claim**: post-LLM clamp applies §6.5 floor rules. The LLM cannot return `goal_viability.confidence == 'high'` when data density doesn't support it; clamp rewrites to the ceiling + appends `confidence_clamped_by_data_signal` observation.
- **HITL omission**: validator auto-emits missing-but-required §6.1 items on the conditions; LLM cannot suppress a `blocker` by omitting it.
- **Hallucinated evidence_basis fields**: name-existence check warns but does not fail. Mode-discriminator on evidence_basis paths also warn-only (3B-specific stricter check, but warn-grade until §H.2 form-refresh lands).
- **Race-date-in-past**: caught at input-validation step, never reaches the LLM. Raises `Layer3BInputError("event_date_in_past")`.

---

## 2. Pipeline placement

**Call site:** `llm_layer3b_goal_timeline_viability` per `Layer3_3B_Spec.md` §3. Invoked by the Layer 3 orchestrator after:

1. Layer 1 builder produces `Layer1Payload` via `build_layer1_payload(db, user_id, as_of)`.
2. Layer 2A produces `Layer2APayload` via `q_layer2a_discipline_classifier_payload(...)`.
3. Layer 3A produces `Layer3APayload` via `llm_layer3a_athlete_state_cached(...)`.
4. Orchestrator loads target `RaceEventPayload | None` via `load_target_race_event_payload(db, user_id)`.

The orchestrator passes typed payloads directly; no dict pass-through. `race_event_payload is None` => no-event-mode; non-None => event-mode (D11).

**Pattern:** Single LLM call + post-LLM transforms per spec §5.

- Step 1: `_validate_inputs(...)` — §4 preconditions → `Layer3BInputError(code)` on fail.
- Step 2: `_render_user_prompt(...)` — assemble Blocks 1-4 per §5.1 + spec §6 guardrails as system-prompt context. Capture the prep dict for the evidence-basis cross-check.
- Step 3: Up to 2 attempts on schema violation (single capped retry per §5.5 step 1).
- Step 4: Schema validation via `Layer3BPayload.model_validate(tool_args + driver_metadata)`. Pydantic enforces all §7 schema rules including mode-discriminator on event-metadata fields.
- Step 5: `_check_evidence_basis(payload, prep_dict, mode)` — name-existence + mode-discriminator on path prefixes (`h2.*` event, `h3.*` no-event). Warn-only per D9.
- Step 6: `_enforce_hitl_auto_emit(payload, inputs)` — validator appends missing-but-required §6.1 HITL items. Dedup by `item_label`.
- Step 7: `_apply_confidence_floors(payload, inputs)` — §6.5 4 floor rules + auto-append `confidence_clamped_by_data_signal`.
- Step 8: `_enforce_periodization_sanity_loop(payload, inputs, caller, ...)` — §5.5 step 4. Up to 1 sanity retry; persistent failure → fallback-to-standard with observation.
- Step 9: Stamp metadata + populate D-66 event-metadata fields per D14 + return `Layer3BPayload`.

**Out-of-pipeline cases:**

- Cache hit per spec §9.1 → no LLM call; orchestrator returns the hydrated cached payload directly via `llm_layer3b_goal_timeline_viability_cached`.
- Input validation failure per spec §4 → raises `Layer3BInputError(code)`; no LLM call.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following prep blocks per spec §5.1.

### 3.1 Block 1 — Mode + timeline (spec §5.1 Block 1)

| Variable | Source | Notes |
|---|---|---|
| `mode` | derived: `"event" if race_event_payload is not None else "no-event"` | Mode-discriminator for the entire prompt. |
| `event_date` | `race_event_payload.event_date` (event-mode only) | None in no-event mode. |
| `time_to_event_weeks` | `(event_date - current_date).days // 7`, floor at 0 (event-mode only) | Derived by driver; D14. |
| `time_to_event_phase_band` | `_time_to_event_phase_band(time_to_event_weeks)` per spec §5.3 | Guidance string the LLM is told ("< 4 weeks → compressed; 4–8 → compressed; 8–16 → standard; 16–24 → standard or extended; > 24 → extended"). |
| `plan_duration_weeks` | caller kwarg OR `layer1_payload.event_goal.plan_duration_weeks_no_event` (no-event-mode only) | One of `{8, 12, 16, 20, 24}` per spec §4 rule 3. |
| `non_event_goal_type` | caller kwarg OR `layer1_payload.event_goal.non_event_goal_type` (no-event-mode only) | One of `{endurance, general_fitness, strength, mixed}` per `Layer1EventGoal` Literal. |

### 3.2 Block 2 — Goal context (spec §5.1 Block 2)

**Event-mode (when `race_event_payload is not None`):**

| Variable | Source | Notes |
|---|---|---|
| `goal_outcome` | caller kwarg (v1 not on schema; None-tolerant) | `Finish` / `Compete mid-pack` / `Podium` per spec §6.1. None ⇒ "unknown" framing in prompt. |
| `time_goal` | caller kwarg | Optional string (e.g., "sub-12h"). |
| `first_time_at_distance` | caller kwarg | Bool. None ⇒ "unknown" framing. |
| `previous_attempts` | caller kwarg | List of `{outcome, dnf_cause}` dicts. None / empty ⇒ no previous-DNF cross-checks fire. |
| `race_distance_km` | `race_event_payload.distance_km` OR caller kwarg | Deployed `RaceEventPayload.distance_km` covers; kwarg override for fixtures. |
| `race_duration_hr` | caller kwarg | Estimated event duration (e.g., 56h for PGE 2026). v1 not on `RaceEventPayload`. |
| `race_terrain` | caller kwarg | List of TRN-xxx ids. v1 not on `RaceEventPayload`. |
| `race_pack_weight_kg` | caller kwarg | v1 not on `RaceEventPayload`. |
| `navigation_required` | caller kwarg | Bool. v1 not on `RaceEventPayload`. |
| `race_event_name` | `race_event_payload.name` | Human-readable label for the prompt. |
| `race_format` | `race_event_payload.race_format` | `single_day` / `expedition_ar` / `stage_race` / `multi_day_ultra`. |

**No-event-mode (when `race_event_payload is None`):**

| Variable | Source | Notes |
|---|---|---|
| `primary_sport` | `layer1_payload.identity.primary_sport` | For §6.6 cross-check (e.g., Strength goal + Trail Running primary). |
| `secondary_sports` | `layer1_payload.training_history.secondary_sports` | Compact list for sport-context framing. |

### 3.3 Block 3 — Current state excerpt (spec §5.1 Block 3, from 3A)

| Variable | Source | Notes |
|---|---|---|
| `current_state.aerobic_capacity` | `layer3a_payload.current_state.aerobic_capacity` | Level + confidence + reasoning_text. Read as-given. |
| `current_state.strength` | `layer3a_payload.current_state.strength` | Same. |
| `current_state.weak_links` | `layer3a_payload.current_state.weak_links` | Up to 5 items. |
| `current_state.skill_assessments` | `layer3a_payload.current_state.skill_assessments` | Filtered to disciplines in 2A's included list. |
| `recent_trajectory.short_term.direction` | `layer3a_payload.recent_trajectory.short_term.direction` | + reasoning_text. |
| `recent_trajectory.medium_term.direction` | `layer3a_payload.recent_trajectory.medium_term.direction` | + reasoning_text. |
| `recent_trajectory.confidence` | `layer3a_payload.recent_trajectory.confidence` | Drives §6.5 floor rule 2. |
| `data_density.connected_providers` | `layer3a_payload.data_density.connected_providers` | Counts only — drives §6.5 floor rule 3. |
| `data_density.self_report_freshness_days` | `layer3a_payload.data_density.self_report_freshness_days` | Drives §6.5 floor rule 3. |

### 3.4 Block 4 — Discipline + load context (spec §5.1 Block 4, from 2A)

| Variable | Source | Notes |
|---|---|---|
| Per-discipline lines | `layer2a_payload.disciplines` (filtered to `inclusion == 'included'`) | Each line: `discipline_name`, `role`, `load_weight.value`. |
| `framework_sport` | `layer2a_payload.framework_sport` | Phase context. |
| `training_gaps_summary.flagged_count` | `layer2a_payload.training_gaps_summary.flagged_count` | Single integer. |

### 3.5 `current_date` line

Single line: "Today is YYYY-MM-DD." Anchors all `time_to_event_weeks` framing in the LLM's reasoning.

---

## 4. Tool schema

### 4.1 Tool name

`emit_layer3b_payload` (per spec §5.4).

### 4.2 Top-level shape

The tool accepts the `Layer3BPayload` contract sans metadata + sans D-66 event-metadata fields (those are stamped post-LLM per D14). Pydantic on the driver side validates via `Layer3BPayload.model_validate(tool_args | driver_metadata | event_metadata)`. The tool schema specifies what the LLM must emit:

```jsonc
{
  "name": "emit_layer3b_payload",
  "description": "Emit the structured goal-timeline-viability evaluation. Required.",
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["mode", "goal_viability", "periodization_shape", "hitl_surface", "notable_observations"],
    "properties": {
      "mode": { "type": "string", "enum": ["event", "no-event"] },
      "goal_viability": { /* ─── §4.3 ─── */ },
      "periodization_shape": { /* ─── §4.4 ─── */ },
      "hitl_surface": { /* ─── §4.5 ─── */ },
      "notable_observations": { /* ─── §4.6 ─── */ }
    }
  }
}
```

### 4.3 `goal_viability`

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["viability", "confidence", "reasoning_text", "evidence_basis", "suggested_adjustments"],
  "properties": {
    "viability": {
      "type": "string",
      "enum": ["achievable", "achievable-with-adjustment", "unrealistic-as-stated"]
    },
    "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
    "reasoning_text": { "type": "string" },
    "evidence_basis": { "type": "array", "items": { "type": "string" } },
    "suggested_adjustments": { "type": "array", "items": { "type": "string" } }
  }
}
```

Schema rule: `suggested_adjustments` non-empty when `viability != 'achievable'`; empty when `viability == 'achievable'` (pydantic `GoalViability._check_adjustments`).

### 4.4 `periodization_shape`

```jsonc
{
  "type": "object",
  "additionalProperties": false,
  "required": ["mode", "start_phase", "reasoning_text", "evidence_basis"],
  "properties": {
    "mode": { "type": "string", "enum": ["standard", "compressed", "extended", "custom"] },
    "start_phase": { "type": "string", "enum": ["Base", "Build", "Peak", "Taper"] },
    "phase_weeks": {
      "anyOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Base": { "type": "integer", "minimum": 0 },
            "Build": { "type": "integer", "minimum": 0 },
            "Peak": { "type": "integer", "minimum": 0 },
            "Taper": { "type": "integer", "minimum": 0 }
          }
        },
        { "type": "null" }
      ]
    },
    "reasoning_text": { "type": "string" },
    "evidence_basis": { "type": "array", "items": { "type": "string" } }
  }
}
```

Schema rule: `phase_weeks` non-None iff `mode == 'custom'` (pydantic `PeriodizationShape._check_phase_weeks`). Periodization-sanity loop per D13 + §5.5 step 4 enforces phase_weeks sum within ±1 of timeline.

### 4.5 `hitl_surface`

```jsonc
{
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["source", "item_label", "severity", "description", "recommended_action", "revise_option", "revise_target"],
    "properties": {
      "source": { "type": "string", "enum": ["3B"] },
      "item_label": { "type": "string" },
      "severity": { "type": "string", "enum": ["blocker", "warning", "informational"] },
      "description": { "type": "string" },
      "recommended_action": { "type": "string" },
      "acknowledge_option": { "type": ["string", "null"] },
      "revise_option": { "type": "string" },
      "revise_target": { "type": "string" }
    }
  }
}
```

Schema rules (pydantic): `acknowledge_option is None` when `severity == 'blocker'`; `hitl_surface` item_labels unique. Validator post-emits missing required items per D12.

### 4.6 `notable_observations`

```jsonc
{
  "type": "array",
  "maxItems": 6,
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

The driver may append a `confidence_clamped_by_data_signal` observation (category=`data_gap`, elevates_to_hitl=False) per §6.5 + D8, OR a `periodization_shape_fallback` observation (category=`data_hygiene`, elevates_to_hitl=False) per D13 + §5.5 step 4, when applicable.

---

## 5. System prompt

```
You are AIDSTATION's goal-timeline-viability evaluator (Layer 3 Node 3B).

Your job: judge whether the athlete's stated goal is achievable in the
time available, and produce a periodization shape that Layer 4 will use
to size and order training phases.

You will receive (in the user prompt):
  - Mode (event vs no-event) + timeline
  - Goal context (event details OR plan duration + goal type)
  - Athlete current state and recent trajectory (from Layer 3A)
  - Included disciplines + load weights (from Layer 2A)

You will produce a structured Layer3BPayload via the `emit_layer3b_payload`
tool. You cannot return free-form text outside the tool call.

Hard rules:

1. Ground every viability + periodization judgment in specific evidence
   from the input. Cite the field name(s) in `reasoning_text` and list
   them in `evidence_basis` (e.g., "h2.goal_outcome", "3a.current_state.
   aerobic_capacity", "2a.discipline.D-001.load_weight").

2. Mode-discriminator on evidence_basis paths: in event-mode, at least
   one `goal_viability.evidence_basis` entry must reference an §H.2
   field (prefix `h2.`); in no-event-mode, references must use §H.3
   prefix (`h3.`) only — no §H.2 references.

3. Periodization-shape vocabulary (§6.2):
   - `standard` — use 2A's phase load bands as-is. Default for most
     cases.
   - `compressed` — shorter phases or skipped Base. For event-mode
     `time_to_event_weeks < 8`, or no-event mode when Goal Type strongly
     mismatches current state and Plan Duration is short.
   - `extended` — lengthened phases. May include double-Base for
     `time_to_event_weeks > 20` with athlete starting from low aerobic
     state.
   - `custom` — explicit `phase_weeks` dict override. Used when
     standard/compressed/extended don't fit; phase_weeks MUST sum to
     `time_to_event_weeks` (event) or `plan_duration_weeks` (no-event)
     within ±1.

   `start_phase` ∈ {Base, Build, Peak, Taper}. If 3A shows
   aerobic_capacity ∈ {good, strong} and short-term trajectory is
   building/steady, `start_phase = Build` is appropriate (skip Base for
   already-fit athletes). Compressed timelines (<4 weeks) typically
   start at Peak or Taper.

   `phase_weeks` MUST be null unless `mode == 'custom'`.

4. Time-to-event phase band guidance (event-mode only; advisory, not
   mandatory — your judgment subject to §6 guardrails wins):
   - < 4 weeks → `compressed`, Peak + Taper only; skip Base/Build.
   - 4–8 weeks → `compressed`, truncated Build + Peak + Taper.
   - 8–16 weeks → `standard`, Base + Build + Peak + Taper at typical
     proportions.
   - 16–24 weeks → `standard` or `extended` depending on 3A state.
   - > 24 weeks → `extended`, double Base + Build + Peak + Taper.

5. HITL trigger thresholds (§6.1) — emit a `hitl_surface` item with the
   exact `item_label` when ANY of these conditions hold:
   - `goal_viability.viability == 'unrealistic-as-stated'` →
     `3B.unrealistic_goal`, severity=blocker. `acknowledge_option`
     MUST be null (blocker items cannot be acknowledged — athlete
     must revise).
   - `viability == 'achievable-with-adjustment'` AND
     `first_time_at_distance == True` AND `goal_outcome ∈
     {Compete mid-pack, Podium}` → `3B.first_time_competitive_goal`,
     severity=warning.
   - event-mode AND `previous_attempts` contains a DNF entry AND
     `time_to_event_weeks < dnf_recovery_window_weeks` →
     `3B.dnf_recurrence_risk`, severity=warning. The window per
     dnf_cause: quad_failure=12, nutrition_blowup=4,
     injury_during_event=16, weather/timeout=4, other=8.
   - `periodization_shape.mode == 'compressed'` AND 3A
     `recent_trajectory.short_term.direction ∈ {overreached, fatigued}`
     → `3B.compressed_on_fatigued_athlete`, severity=warning.

   `viability == 'achievable'` with no qualifiers → no HITL.

6. Confidence calibration (§6.5) — the validator post-clamps
   `goal_viability.confidence` down when any of these signals fire:
   - `first_time_at_distance == True` AND `goal_outcome ∈
     {Compete mid-pack, Podium}` → ≤ medium.
   - 3A `recent_trajectory.confidence == 'low'` → ≤ medium.
   - no-event mode AND 3A `data_density.connected_providers` empty AND
     `self_report_freshness_days > 30` → ≤ low.
   - event-mode AND `previous_attempts` empty AND
     `first_time_at_distance == True` → ≤ medium.
   When any of the above hold and you emit `high`, the validator clamps
   you down. Be conservative: prefer `medium` when in doubt.

7. No-event-mode heuristics (§6.6) — guidance, not hard rules:
   - `non_event_goal_type == 'strength'` AND 3A
     `current_state.strength.level == 'low'` AND
     `plan_duration_weeks <= 12` → likely
     `achievable-with-adjustment`, periodization `extended` (or
     recommend extending Plan Duration).
   - `non_event_goal_type == 'endurance'` AND 3A
     `current_state.aerobic_capacity.level ∈ {low, moderate}` AND
     `plan_duration_weeks >= 16` → typically `achievable`,
     periodization `standard`.
   - `non_event_goal_type == 'mixed'` → no specific guardrail; shape
     based on the weaker capacity.
   - `non_event_goal_type == 'general_fitness'` → almost always
     `achievable`, periodization `standard`, minimal HITL.
   - Cross-check Non-Event Goal Type vs §C Primary Sport: if Goal Type
     is `strength` but Primary Sport is pure-endurance (Trail Running,
     Road Cycling, Swimming, etc.), auto-emit observation
     `goal_type_primary_sport_mismatch` (category=data_hygiene,
     elevates_to_hitl=False).

8. Required observation auto-emit triggers (§8.1) — emit when condition
   met:
   - `first_time_at_distance == True` (event-mode) → category=warning;
     elevates_to_hitl=True only when paired with the §6.1 row 2
     condition.
   - `previous_attempts` contains DNF in same event → category=warning;
     elevates_to_hitl per §6.1 row 3.
   - event-mode AND `time_to_event_weeks > 30` → category=opportunity;
     elevates_to_hitl=False. Suggest intermediate-test-race scheduling.
   - `periodization_shape.mode == 'compressed'` → category=warning;
     elevates_to_hitl=False unless §6.1 row 4 condition.
   - no-event mode AND Goal Type vs §C Primary Sport mismatch (per
     rule 7 cross-check) → category=data_hygiene;
     elevates_to_hitl=False.
   - confidence clamped by floor rule (§6.5) →
     category=data_gap; elevates_to_hitl=False. (The validator
     auto-appends this one; you don't need to emit it.)

9. Observation budget (§8.2): `notable_observations` is capped at 6
   items. Priority order if you exceed: warning > opportunity >
   data_gap > data_hygiene. Within category, required-trigger items
   outrank discretionary observations.

10. Forbidden observations (never emit):
    - Generic encouragement.
    - State-assessment claims ("your aerobic capacity is low") — that's
      Layer 3A's territory; read it, don't restate it.
    - Injury-risk statements ("your wrist injury limits packing") —
      that's Layer 2D's territory.
    - Exercise prescriptions ("do 4×4 VO2 intervals") — that's Layer 4.
    - Specific session designs or plan dates — that's Layer 4.
    - Speculation beyond evidence.

11. Race-date-in-past is fatal (§6.4). If you see `time_to_event_weeks <
    0` (which the validator should catch first; this is a defensive
    fallback), do NOT pivot to post-race-results mode. The input is
    invalid; the athlete must edit §H. (In practice, validation catches
    this before you see the prompt — this rule is here for defense in
    depth.)

12. Plan duration cap: §H.3 caps no-event Plan Duration at 24 weeks.
    Event-mode can exceed (e.g., 32-week build to an A-race) — use
    `extended` mode.

Voice: direct, evidence-grounded, no platitudes. Match the cadence of a
real endurance coach evaluating a goal. No hedging language ("might
possibly", "could potentially"). If a goal is unrealistic, say so and
explain why. If a periodization shape is non-standard, justify the
deviation. No "great choice!" or marketing tone.
```

---

## 6. User prompt template

```
Mode + timeline:
{block_1_timeline}

Goal context:
{block_2_goal_context}

Current state (from Layer 3A):
{block_3_state_excerpt}

Discipline + load context (from Layer 2A):
{block_4_discipline_load}

Today is {current_date}.

Produce a `Layer3BPayload` via the `emit_layer3b_payload` tool. Ground
every viability + periodization judgment in evidence_basis citations.
Apply the §6 guardrails — be conservative on confidence; emit HITL items
when conditions trigger; pick periodization mode per §5.3 phase bands
plus 3A state.
```

On schema retry, the user prompt is augmented with:

```
Previous attempt failed schema validation: {error_message}

Re-emit a valid `emit_layer3b_payload` tool call addressing the error
above. Do not change unrelated fields.
```

On periodization-sanity retry, the user prompt is augmented with:

```
Previous attempt's periodization_shape.mode=='custom' but phase_weeks
sums to {actual_sum} which is outside ±1 of {target_weeks}
({sum_kind}). Re-emit with either (a) mode=='custom' AND phase_weeks
summing within ±1 of {target_weeks}, OR (b) a non-custom mode
('standard' / 'compressed' / 'extended') with phase_weeks=null.
```

---

## 7. Sampling config

| Param | Value | Source |
|---|---|---|
| `model` | `claude-sonnet-4-6` | D7 + spec §3 default. |
| `temperature` | `0.0` | Spec §3 + §9.3 (determinism). |
| `max_tokens` | `2000` | D6 + spec §5.4 literal. |
| `extended_thinking_budget` | `3000` | D2. |
| `capped_retries_schema` | `1` | D4 + spec §5.5 step 1 ("retried once"). |
| `capped_retries_periodization` | `1` | D4 + spec §5.5 step 4 ("re-prompt once; persistent failure → fall back to standard"). |
| `tool_choice` | `{"type": "tool", "name": "emit_layer3b_payload"}` | D1 + spec §5.4. |

---

## 8. Post-LLM transforms

### 8.1 Schema validation (§5.5 step 1)

`Layer3BPayload.model_validate({...tool_args, ...driver_metadata, ...event_metadata})` — pydantic enforces the full contract including the mode-discriminator on event-metadata fields, suggested_adjustments-vs-viability rule, phase_weeks-iff-custom rule, hitl_surface-unique-labels rule, blocker-acknowledge-None rule. On failure, single capped retry per §5.5 step 1 with the validation error in the user prompt. Second failure raises `Layer3BOutputError("schema_violation", detail=<error>)`.

### 8.2 Mode-discriminator enforcement (§5.5 step 2)

Driver checks `payload.mode == "event" iff race_event_payload is not None`. Mismatch raises `Layer3BOutputError("mode_mismatch")` immediately — no retry. The LLM is told the mode in the prompt + the tool schema requires it, so a mismatch indicates a deeper failure mode worth surfacing.

### 8.3 Evidence-basis cross-check (D9, §5.5)

`_check_evidence_basis(payload, prep_dict, mode)` walks every `goal_viability.evidence_basis` + `periodization_shape.evidence_basis` + per-observation `evidence_basis` entry. For each entry:

- **Name-existence check**: if the path is not a key in `prep_dict`, emit `Layer3BEvidenceBasisWarning`. No fail.
- **Mode-discriminator check** (3B-specific): in event-mode, `goal_viability.evidence_basis` must include at least one `h2.*`-prefixed path; in no-event-mode, must NOT include any `h2.*` paths. Violation emits `Layer3BEvidenceBasisWarning`. No fail (D9 — telemetry until §H.2 form-refresh lands).

### 8.4 HITL auto-emit (§5.5 step 3 + §6.1 + D12)

`_enforce_hitl_auto_emit(payload, inputs)` checks the 4 spec §6.1 conditions against the inputs + LLM-emitted viability/periodization. For each condition that holds, ensures the corresponding `item_label` is present in `payload.hitl_surface`; appends a synthetic `Layer3BHITLItem` if missing. Dedup by `item_label`. Append-only — LLM-emitted items are kept in priority order.

Synthetic items use spec-canonical labels:

- `3B.unrealistic_goal` — severity=blocker, acknowledge_option=None.
- `3B.first_time_competitive_goal` — severity=warning.
- `3B.dnf_recurrence_risk` — severity=warning.
- `3B.compressed_on_fatigued_athlete` — severity=warning.

`description` + `recommended_action` + `revise_option` + `revise_target` use spec-suggested wording.

### 8.5 Confidence-floor clamp (§6.5 + D8)

`_apply_confidence_floors(payload, inputs)` applies the 4 spec §6.5 floor rules:

| Signal | Ceiling | Target field |
|---|---|---|
| `first_time_at_distance == True` AND `goal_outcome ∈ {Compete mid-pack, Podium}` | `medium` | `goal_viability.confidence` |
| 3A `recent_trajectory.confidence == 'low'` | `medium` | `goal_viability.confidence` |
| no-event mode AND 3A `data_density.connected_providers` empty AND `self_report_freshness_days > 30` | `low` | `goal_viability.confidence` |
| event-mode AND `previous_attempts` empty AND `first_time_at_distance == True` | `medium` | `goal_viability.confidence` |

Multiple floors stack via `min(level)` (high > medium > low). When any clamps fire, a `confidence_clamped_by_data_signal` observation is appended:

```python
Layer3Observation(
    category="data_gap",
    text=f"Confidence clamped by data signal: {signal_summary}",
    evidence_basis=[signal_field, ...],
    elevates_to_hitl=False,
)
```

`signal_summary` enumerates the firing signals (e.g., "first_time_competitive_goal, layer3a_trajectory_confidence_low").

### 8.6 Periodization-sanity loop (§5.5 step 4 + D13)

`_enforce_periodization_sanity_loop(payload, inputs, caller, ...)`:

```
if payload.periodization_shape.mode == 'custom':
    target = time_to_event_weeks (event-mode) or plan_duration_weeks (no-event-mode)
    actual = sum(payload.periodization_shape.phase_weeks.values())
    if abs(actual - target) > 1:
        # Single retry: re-prompt with deviation error
        # If still mismatched: fallback
        new_payload = retry_once(...)
        if new_payload still mismatched OR retry fails:
            # Fallback path: rebuild payload with mode='standard' + phase_weeks=None
            # Preserve LLM's start_phase + reasoning_text
            # Auto-append `periodization_shape_fallback` observation
            payload = payload.model_copy(update={
                "periodization_shape": payload.periodization_shape.model_copy(update={
                    "mode": "standard",
                    "phase_weeks": None,
                    "reasoning_text": payload.periodization_shape.reasoning_text +
                        " [Validator fallback: custom phase_weeks sum mismatched timeline by >1 week]",
                }),
                "notable_observations": payload.notable_observations + [
                    Layer3Observation(
                        category="data_hygiene",
                        text=f"Periodization shape fell back from custom to standard: phase_weeks sum {actual} vs target {target} weeks (±1 tolerance).",
                        evidence_basis=["validator.periodization_sanity"],
                        elevates_to_hitl=False,
                    )
                ],
            })
```

### 8.7 Metadata stamping + event-metadata population (D14)

After all transforms, the driver assembles the final payload:

```python
event_metadata = {}
if race_event_payload is not None:
    event_metadata = {
        "event_date": race_event_payload.event_date,
        "event_locale_id": race_event_payload.event_locale_id,
        "race_format": race_event_payload.race_format,
        "time_to_event_weeks": max(0, (race_event_payload.event_date - current_date).days // 7),
    }

Layer3BPayload(
    user_id=user_id,
    as_of=datetime.combine(current_date, time.min),
    mode=mode,
    model=model,
    temperature=temperature,
    prompt_hash=sha256_hex(system_prompt + user_prompt),
    latency_ms=llm_out.latency_ms,
    input_tokens=llm_out.input_tokens,
    output_tokens=llm_out.output_tokens,
    etl_version_set=etl_version_set,
    goal_viability=clamped_goal_viability,
    periodization_shape=clamped_periodization_shape,
    hitl_surface=hitl_surface_with_auto_emits,
    notable_observations=clamped_observations,
    **event_metadata,  # event-mode populates; no-event leaves None per pydantic default
)
```

---

## 9. Performance budget

Per spec §11:

| Stage | Target |
|---|---|
| Input prep + prompt render | <50ms |
| LLM call (cold, p50) | <2.5s (Sonnet 4.6, ~3,500 input, ~1,200 output) |
| LLM call (cold, p95) | <4s |
| Schema validation + evidence check + HITL auto-emit + floor clamp | <30ms |
| Periodization-sanity loop (when fires) | +1 LLM call OR direct fallback ~5ms |
| **Total p95 (cold, no sanity retry)** | ~4s |
| **Total p95 (cached via `_cached` wrapper)** | <100ms |

Cost estimate: ~$0.03 per cold invocation (cheaper than 3A's ~$0.05-0.10 due to smaller input + smaller output + smaller thinking budget). Plan-gen cadence: 3B re-runs on goal/timeline edits + on 3A re-run; cold-rate similar to 3A.

---

## 10. Caching

Per spec §9 + this session's `layer3b/cached_wrapper.py`:

**Cache key** per §9.1:

```
sha256(
    user_id ||
    compute_payload_hash(layer1_payload) ||
    compute_payload_hash(layer3a_payload) ||
    compute_payload_hash(layer2a_payload) ||
    (race_event_payload.race_event_id if event-mode else "no-event") ||
    current_date.isoformat() ||
    non_event_goal_type or "" ||
    canonical_json(etl_version_set) ||
    canonical_json(spec_§H.2_kwargs_dict) ||  # forward-compatibility hash slot
    model ||
    str(temperature) ||
    str(max_tokens) ||
    str(extended_thinking_budget)
)
```

**Day-granular `current_date`**: re-runs on the same calendar day with identical inputs return the cached payload. Same-day `time_to_event_weeks` recomputes to the same value (date arithmetic is whole-day).

**Wrapper:** `llm_layer3b_goal_timeline_viability_cached(...)` in `layer3b/cached_wrapper.py` reuses the `CacheBackend` from `layer4/cache.py` plus 3B-specific serialize/hydrate helpers built on pydantic's `model_dump_json` / `model_validate_json`.

**Invalidation triggers** per spec §9.2: §H.1 has_event toggle; §H.2 fields (event-mode); §H.3 fields (no-event-mode); §C Primary/Secondary/Discipline-Weighting changes; `layer3a_payload` re-run (new `prompt_hash`); `layer2a_payload` re-run; `current_date` crosses a phase boundary; `etl_version_set` repin. Cache invalidation propagation lives in the orchestrator; the wrapper just handles the get/put.

---

## 11. Test scenarios

Per spec §13's 8 scenarios. Each scenario in `tests/test_layer3b_builder.py` uses a stub `llm_caller` returning pre-shaped tool args + verifies the round-trip through validation + evidence-basis check + HITL auto-emit + floor clamping + periodization sanity + assembly.

The stubbed tool args validate that the contract holds; they do NOT exercise that a real Sonnet 4.6 emits specific enums for specific fixtures. Real-LLM regression (§13 model swap) is deferred to Step 7/8 telemetry tuning per `Upstream_Implementation_Plan_v1.md` §4 row Step 7.

TS coverage:

- TS-1 (AR finisher, 9 weeks, Andy's PGE case) → TestS13Scenarios::test_ts1_ar_finisher_compressed
- TS-2 (AR podium, 4 weeks, unrealistic) → TestS13Scenarios::test_ts2_ar_podium_unrealistic_blocker_hitl
- TS-3 (trail half, first-time, 12 weeks) → TestS13Scenarios::test_ts3_first_time_competitive_clamps_confidence
- TS-4 (no-event endurance, 24 weeks) → TestS13Scenarios::test_ts4_no_event_endurance_standard
- TS-5 (no-event strength, 8 weeks low strength) → TestS13Scenarios::test_ts5_no_event_strength_mismatch_observation
- TS-6 (ultra prior DNF, 12 weeks) → TestS13Scenarios::test_ts6_dnf_recurrence_warning
- TS-7 (event 1 week away) → TestS13Scenarios::test_ts7_compressed_taper
- TS-8 (race date in past) → TestS13Scenarios::test_ts8_race_date_in_past_fatal_no_llm

---

## 12. Open items

| ID | Item | Disposition |
|---|---|---|
| L3B-P-1 | Real-LLM regression on §13's 8 scenarios | Defer to Step 7/8 — requires `ANTHROPIC_API_KEY` env scaffolding (same as 3A's L3A-P-1). |
| L3B-P-2 | §H.2 deployed-shape gap (`goal_outcome`, `first_time_at_distance`, `previous_attempts`, `time_goal`, `race_pack_weight_kg`, `navigation_required`, `race_terrain`, `race_duration_hr`) | Defer to the `§H.2 / §J / §I.1 form-refresh PR` already tracked in CARRY_FORWARD. v1 driver accepts these as `None`-tolerant kwargs; v1 HITL auto-emit logic no-ops when fields are None (e.g., `3B.first_time_competitive_goal` doesn't fire if `first_time_at_distance is None`). Closing the gap tightens D9 to fail-hard mode-discriminator on evidence_basis paths. |
| L3B-P-3 | Mode-discriminator on evidence_basis paths as HARD fail (not warn) | Defer until L3B-P-2 closes. Currently warn-only so v1 tests pass with `None` §H.2 kwargs. |
| L3B-P-4 | `dnf_recovery_window_weeks` calibration (currently spec §6.1 reasoned defaults: quad_failure=12, nutrition_blowup=4, injury_during_event=16, weather/timeout=4, other=8) | Iterate post-launch when DNF data accumulates. |
| L3B-P-5 | Layer 4 plan-gen periodization contract | Spec §6.3 forward-pointer. Revisit when Layer 4 input contract for periodization solidifies (Phase 5.1 orchestrator vertical slice). |
| L3B-P-6 | Re-evaluation cadence in final 8 weeks pre-event | Spec §12 — should 3B auto-re-run weekly regardless of input changes? Not in v1 (re-run on input change only). |
| L3B-P-7 | Multi-event athletes (v2) | Spec §12 — v1 supports one A-race per plan. Material spec revisit if multi-A-race support lands. |
| L3B-P-8 | Plan duration cap (24 weeks) for no-event mode | Spec §H.3 hard cap. Revisit if athletes request >24-week no-event plans post-launch. |

---

## 13. Gut check

**What this prompt body gets right.**

The 4 spec §6.5 floor rules are inlined as system-prompt rule 6 AND enforced post-LLM via `_apply_confidence_floors` (D8) — same dual-enforcement pattern as 3A (LLM proposes, validator enforces). The validator is the hard guarantee; the prompt hint reduces validator firings + observation-append rate.

The 4 spec §6.1 HITL items are inlined as system-prompt rule 5 AND auto-emitted post-LLM via `_enforce_hitl_auto_emit` (D12) — same dual pattern. Spec §5.5 step 3 explicitly mandates this for the contract guarantee that a blocker can't be suppressed by LLM omission.

The periodization-sanity loop (D13 + §5.5 step 4) is the only place 3B has a hard semantic invariant beyond pydantic. The fallback-to-standard path keeps the call non-fatal — the athlete gets a usable payload even when the LLM emits an inconsistent custom-mode shape.

Mode-discriminator on event-metadata fields is pydantic-enforced (`Layer3BPayload._check_event_mode_consistency`); driver-side D14 population just fills the 4 fields when event-mode + leaves None when no-event-mode. Single source of truth at the schema level.

The §H.2 deployed-shape gap (D11 + L3B-P-2) is handled via None-tolerant kwargs — v1 tests + Andy's PGE 2026 use case work today; the form-refresh PR de-stubs the kwargs to actual database-sourced values. No data padding (CLAUDE.md trigger #2 honored).

**Risks.**

**§H.2 fields are None-tolerant in v1, which means the HITL auto-emit logic for `3B.first_time_competitive_goal` + `3B.dnf_recurrence_risk` is unreachable for production callers until the form-refresh PR lands.** The validator code paths exist + are covered by tests via fixture kwarg injection. The risk is that the HITL pathways won't fire in real onboarding flows — but real onboarding flows can't supply the needed input either, so the validator correctly no-ops. Captured in L3B-P-2.

**The 4 floor rules in §6.5 depend on 3A's `data_density` self-report being approximately accurate.** Per `Layer3A_v1.md` §13 risk, 3A's `data_density` is LLM self-reported, not driver-computed. If the LLM mis-counts the prompt's connected providers, 3B's floor rule 3 may misfire. Mitigation: same as 3A's L3A-P-4 — defer driver-side override to Step 7/8.

**The mode-discriminator on evidence_basis paths (D9 warn-only) means a no-event-mode LLM could cite an h2.* field and we'd only log a warning, not fail.** Tighten when L3B-P-2 + L3B-P-3 close. v1 risk accepted because the form-refresh blocks the fail-hard tightening.

**The periodization-sanity loop's fallback path silently rewrites the LLM's structured output.** The `periodization_shape_fallback` observation surfaces it to downstream (Layer 4 + 3D + UI), but the original LLM-emitted custom-mode payload is lost. Step 8 telemetry could log the discarded payload for calibration.

**`current_date: date` vs 3A's `as_of: datetime`** — minor type-discipline drift. Spec §3 says `current_date: date`; we honor it. `Layer3BPayload.as_of: datetime` requires conversion via `datetime.combine(current_date, time.min)` in the driver. Single conversion point; not load-bearing but worth a note.

**What might be missing.**

- A `prompt_hash`-based dedup at cache-write time (spec §9.2 mentions content-hash dedup). Not implemented in v1; same as 3A.
- Telemetry helper for "how many times did the periodization-sanity loop fall back today". Step 8 territory.
- Real `dnf_recovery_window_weeks` calibration (currently L3B-P-4 — reasoned defaults).

**Best argument against.**

You could argue the periodization-sanity loop should fail-hard rather than fall back to standard. Counter: the fallback path is non-fatal by design per spec §5.5 step 4 ("persistent failure → fall back to `standard`") — the alternative (raise `Layer3BOutputError`) would make 3B brittle on a relatively recoverable inconsistency.

You could argue D11 should define `SectionHGoalContext` + `SectionCContext` as proper typed contexts per spec §3 wording. Counter: same as 3A precedent — raw Layer1Payload + RaceEventPayload is sufficient; defining types for stubs creates schema-versioning churn when the §H.2 form-refresh lands. Defer to L3B-P-2.

You could argue D2's 3000-token thinking budget is too low for the open-ended judgment 3B has to make. Counter: spec §11 input budget is <3,500 tokens — there's less to think about than 3A (no 8-section prep + integration bundle synthesis). If telemetry shows 3B retry rates higher than 3A's, bump to 4000 in v2.

---

*End of Layer3B_v1.md.*
