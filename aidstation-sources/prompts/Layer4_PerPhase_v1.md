# Layer 4 Per-Phase Synthesizer Prompt — v1

**Status:** Draft v1, 2026-05-16. Second of 5 queued Layer 4 prompt-body designs per `Layer4_Spec.md` §12.2 + CLAUDE.md "Next forward move." Sibling files: `Layer4_SeamReviewer_v1.md` (done); per-tier T1/T2 synthesizer, single-session synthesizer (D-63), race-week-brief (queued).
**Purpose:** The LLM call that synthesizes one periodization phase (Base / Build / Peak / Taper) into a day-by-day `list[PlanSession]` in Layer 4 Pattern A — emits `PlanSession` rows per §7.2 inside a `record_phase_sessions` tool call.
**Companion spec sections:** `Layer4_Spec.md` §5.2 step 3 (call site), §5.4 (deterministic validator the synthesizer's output must clear), §5.5 (capped retry semantics), §6.1 (phase boundary computation — feeds the `intended_*` inputs), §6.2 (seam-reviewer re-prompt path — feeds `seam_issues` retry context), §6.5 (`start_phase != 'Base'` handling), §7.2 (`PlanSession` discriminated union — output schema), §7.3/§7.4 (sub-blocks), §7.6 (`PhaseSpec` + `SynthesisMetadata` — orchestrator-filled metadata), §8 (closed-set coaching flag taxonomy), §11.2 (token budget ~8000 input / ~3000 output per call).

**Source decisions (this session, Andy 2026-05-16):**

- **D1 — output mechanism:** tool-use. `record_phase_sessions` tool with the §7.2 nested schema. No free-form output. (Inherits seam-reviewer convention per `Layer4_SeamReviewer_v1.md` §6.2 carry-forward.)
- **D2 — reasoning style:** extended thinking ON, ~5000 budget tokens (max-defensive). Synthesizer is both judgment-heavy AND combinatorial (placing N sessions × 7 days × M weeks across multiple disciplines + locales); reasoning headroom matters more here than for the reviewer.
- **D3 — input format:** hybrid. Small payloads (Layer 1 trimmed, 3A, 3B, 2A, 2D, 2E tier slice) pass through ~full; large payloads (2C equipment view, 2B terrain) trim to athlete-relevant per-locale + per-format slices. Keeps the §11.2 ~8000 input estimate realistic for multi-locale / multi-discipline athletes.
- **D4 — prior-phase output rendering:** hybrid. Weekly rollup for the full prior phase + full `PlanSession` dumps for the prior phase's last week (the seam-in). Mirrors seam-reviewer D3.
- **D5 — coaching-flag closed-set enforcement:** JSON-schema enum union across all LLM-emitted flags per §§8.2–8.6 (6 flags total — see §10); schema rejects unknown flags. Phase-appropriate use is prompt-instructed; closed-set rule per §8.8 is load-bearing.
- **D6 — deload-week placement:** coaching judgment + anchor table per mode (every 4th wk standard / 3rd wk compressed / 5th wk extended; custom = judgment). Anchors are overridable with rationale recorded in `phase_synthesis_notes`.
- **D7 — Taper-length picking:** coaching judgment + anchor table per race format (1–2wk sub-marathon / 2–3wk marathon-IM-class / 3+wk expedition-AR-multi-day). Anchors overridable with rationale per §6.1 ("informed by race context").
- **D8 — RuleFailure retry context:** hybrid — `rule_name + severity + detail` from each `RuleFailure` + a constraint statement re-framing per failure. Mirrors seam-reviewer's "Observed: X. Constraint: Y" pattern.
- **D9 — `session_notes` / `coaching_intent` length caps:** schema-enforced `maxLength` (600 chars notes / 240 chars intent). Defense against output-token budget runaway.
- **D10 — file location:** `aidstation-sources/prompts/Layer4_PerPhase_v1.md` per the `prompts/` subdir convention from `Layer4_SeamReviewer_v1.md` §6.2.

None of D1–D10 are spec contracts — they are prompt-design choices. Adjustable without touching `Layer4_Spec.md`. D2 + D9 are the primary tuning levers post-launch.

---

## 1. Purpose + scope

Pattern A (`plan_create` + `plan_refresh` T3 cross-phase) synthesizes phases independently — one LLM call per phase, sequentially, with the prior phase's accepted output passed as context for the next. The per-phase synthesizer is THAT call: produces the day-by-day `PlanSession` list for one phase given the athlete's full upstream context + the phase's intended exit/entry state + (when not the first phase) the prior phase's output for continuity.

**What this prompt produces:**

- A `list[PlanSession]` covering `phase_start_date → phase_end_date` (inclusive), one row per day per session_index_in_day (max 2 per day per §7.12).
- Each `PlanSession` is one of `kind ∈ {cardio, strength, rest}` with the appropriate sub-block populated (`cardio_blocks` / `strength_exercises` / `rest_reason`).
- `session_notes` (1–3 sentences, athlete-facing) + `coaching_intent` (1 sentence, Layer 3A re-eval input) + closed-set `coaching_flags` per §§8.2–8.6 (LLM-emitted only — see §10).
- A `phase_synthesis_notes` rationale (≤600 chars) recording the synthesizer's coaching reasoning for this phase (lands in `plan_versions.notes` JSONB per §7.11).
- Optionally up to 3 `Observation(category='opportunity')` entries via the `opportunities` field (per §8.7 LLM-emitted exception).

**Failure modes the prompt design + retry semantics catch:**

- **Volume out of band.** Volume drift outside 2A `phase_load_bands` ±15% → §5.4 `volume_band_*` blocker; retried per §5.5 with constraint context.
- **Intensity distribution drift.** Zone breakdown outside intended ±10pp → §5.4 `intensity_dist_*` blocker; same retry path.
- **ACWR runaway.** Forward ACWR > 1.4 → §5.4 `acwr_*` blocker; constraint re-prompt.
- **Schedule violations.** Sessions on unavailable days, two-per-day rule breaks → §5.4 `schedule_violation_*` / `two_per_day_*` blockers.
- **Injury / locale / discipline violations.** All §5.4 deterministic rules — synthesizer's prompt rules + the retry-context rendering address these.
- **Unknown coaching flag.** Schema enum rejects → `unknown_coaching_flag_<name>` schema-violation per §5.5 (one schema retry; bail on second).
- **Seam-driven re-prompt.** When the seam reviewer emits `flagged_major + re_prompt_*` per §6.2, the orchestrator re-prompts THIS synthesizer call with the reviewer's `seam_issues` merged in as constraint statements.

**Out of scope for this prompt (other prompt-body sessions own these):**

- Seam-reviewer LLM call — `Layer4_SeamReviewer_v1.md`.
- Pattern B refresh paths (T1, T2, T3 intra-phase) — per-tier prompts (queued).
- Single-session ad-hoc workouts (D-63) — single-session prompt (queued).
- Race-week brief — separate prompt (queued).
- Phase boundary computation — `phase_structure_from_3b()` pure helper per §6.1; not an LLM concern.
- Phase shape override decisions — §6.4 pure-rule path; not an LLM concern.
- Spec-auto coaching flag emission — orchestrator post-synthesis pass per §8.1.
- Notable observation emission (except `category='opportunity'`) — orchestrator-computed per §8.7.

---

## 2. Where this runs in the Layer 4 pipeline

Per `Layer4_Spec.md` §5.2 step 3, for each phase `p` in `phase_structure.phases` (sequential, in order):

1. Orchestrator builds inputs per §3 below — combines Layer 1/2/3 payloads with the prior phase's accepted output (when `p` is not the first) + §6.1 intended exit/entry state + (on retry) `rule_failures` from the prior pass's validator + (on seam-driven retry) `seam_issues` from the seam reviewer.
2. Orchestrator calls THIS prompt with `model_synthesizer` + sampling config per §7.
3. Synthesizer responds via the `record_phase_sessions` tool with a complete `list[PlanSession]` for the phase + `phase_synthesis_notes` + optional `opportunities`.
4. Orchestrator parses; runs §5.4 validator scoped to phase `p`.
5. On validator failure: re-call THIS prompt with `rule_failures` populated (counter increments per §5.5; cap = 2 retries per phase by default).
6. On accepted (or cap-hit best-effort): append sessions to cumulative plan; record `SynthesisMetadata` per §7.6.
7. Seam reviewer fires on the `(p, p+1)` boundary after `p+1` is synthesized (per §5.2 step 4 + `Layer4_SeamReviewer_v1.md`). If the seam reviewer emits `flagged_major + re_prompt_*`, THIS prompt is re-called for the targeted phase with `seam_issues` populated.

**T3 cross-phase refresh** (§6.3): same call shape; only affected phases (overlapping the refresh scope) are re-synthesized. Phases outside the scope are NOT re-called — their prior-plan sessions serve as boundary context.

**`start_phase != 'Base'` handling** (§6.5): when this prompt synthesizes the first phase of a plan starting at Build/Peak/Taper, `is_first_phase_in_plan=True` AND the orchestrator passes a synthetic "assumed prior exit state" derived from the 2A `phase_load_bands` for the skipped earlier phases. The prompt's "PRIOR PHASE CONTEXT" block uses these synthetic values; no real prior-phase session detail exists.

**Pattern B routes do NOT invoke this prompt.** T1, T2, T3 intra-phase, single-session, race-week-brief all use their own prompt bodies (queued).

---

## 3. Inputs (template variables)

Orchestrator interpolates the following when building the user prompt. All values come from contracts already pinned in `Layer4_Spec.md` or upstream Layer-1/2/3 payloads.

### 3.1 Phase + plan context

| Variable | Type | Source | Notes |
|---|---|---|---|
| `phase_name` | `'Base'` / `'Build'` / `'Peak'` / `'Taper'` | §7.6 `PhaseSpec.phase_name` | |
| `phase_weeks` | int | §7.6 `PhaseSpec.weeks` | |
| `phase_start_date` | date | §7.6 `PhaseSpec.start_date` | |
| `phase_end_date` | date | §7.6 `PhaseSpec.end_date` (inclusive) | |
| `phase_index_in_plan` | int | derived (0 = first synthesized phase) | Drives whether prior-phase context is populated. |
| `is_first_phase_in_plan` | bool | `phase_index_in_plan == 0` | When True, prior-phase block is synthetic (`start_phase != 'Base'`) or absent (full plan starting at Base). |
| `mode` | str | 3B `periodization_shape.mode` | `standard` / `compressed` / `extended` / `custom`. Drives deload cadence anchor (§9). |
| `start_phase` | str | 3B `periodization_shape.start_phase` | When `start_phase != 'Base'` AND this is the first phase: signals athlete-starting-partway; prior-phase block is synthetic. |
| `intended_volume_band` | dict[discipline → (low, high) hrs/wk] | 2A `phase_load_bands[discipline][phase_name]` | The band this phase must land within (per-week per-discipline). |
| `intended_intensity_distribution` | dict[zone → pct] | §5.4 v1 defaults per `phase_name` | E.g., Base = `{Z1-Z2: 0.80, Z3: 0.15, Z4-Z5: 0.05}`. Peak shares Build's distribution (70/20/10) per §5.4 — see §9 calibration. |

### 3.2 Prior-phase continuity context (None on first phase)

| Variable | Type | Source | Notes |
|---|---|---|---|
| `prior_phase_name` | str \| None | prior `PhaseSpec.phase_name` | None when `is_first_phase_in_plan == True` AND `start_phase == 'Base'`. |
| `prior_phase_intended_exit_volume` | dict[discipline → (low, high)] \| None | 2A `phase_load_bands[discipline][prior_phase]` | When `start_phase != 'Base'` AND first phase: synthetic (2A band for the immediately-prior skipped phase). |
| `prior_phase_intended_exit_intensity` | dict[zone → pct] \| None | §5.4 v1 defaults for `prior_phase` | Same synthetic-when-skipped behavior. |
| `prior_phase_weekly_rollup` | table \| None | computed from prior phase's accepted `PlanSession` list | Per-(week, discipline): total volume (hours), zone breakdown (Z1-Z2 / Z3 / Z4-Z5 hours), session count, key per-session flag list. None for synthetic prior (no real sessions to roll up). |
| `prior_phase_last_week_sessions` | list[PlanSession] \| None | tail slice of prior phase's accepted output (last 7 dates) | Full session objects — the actual seam-in content. None for synthetic prior. |

### 3.3 Athlete context (Layers 1, 3A, schedule)

| Variable | Type | Source | Notes |
|---|---|---|---|
| `athlete_profile_summary` | dict | trimmed from Layer 1 | Form-input summary + performance-stat highlights (recent FTP / VO2max / 5K time / max-lifts) + body metrics summary. Excludes raw integration ingest data. |
| `aerobic_state` | str | 3A `current_state.aerobic_state` | `low` / `moderate` / `high` / `very_high`. Drives volume-ramp aggressiveness. |
| `strength_state` | str | 3A `current_state.strength_state` | Same enum. |
| `data_density` | str | 3A `current_state.data_density` | `dense` / `typical` / `sparse` / `very_sparse`. `sparse` / `very_sparse` triggers conservative ramping (see §9 + §11). |
| `active_injuries` | list[dict] | 3A `active_injuries` (validated non-empty per §4.1) | Each: `{body_part, severity, restriction_text}`. Synthesizer must NOT prescribe sessions that violate `restriction_text` (validator catches `injury_violation_*` but the prompt enforces upstream). |
| `weak_links` | list[dict] | 3A `weak_links` | Each: `{type, discipline, description}`. Synthesizer emits `technique_emphasis` (skill-type weak link) or `weak_link_targeted` (strength accessory) when prescribing addressing work. |
| `available_days_per_week` | int | Layer 1 §K | |
| `daily_availability_windows` | list[dict] | Layer 1 §K | Per-day: `{day_of_week, available, windows: list[{start, end, duration_min}]}`. Session duration_min ≤ window minutes. |

### 3.4 Race + locale + equipment context

| Variable | Type | Source | Notes |
|---|---|---|---|
| `discipline_mix` | list[str] | 2A `discipline_inclusion` | |
| `discipline_weights` | dict[str → float] | 2A `discipline_weights` | Drives per-discipline volume allocation within the phase's volume band. |
| `race_format` | str | event metadata or `'open_ended'` | E.g., `'expedition_ar_48_72h'` / `'marathon'` / `'ironman_70_3'` / `'open_ended'`. Open-ended mode: synthesizer does NOT emit `race_pace_specific` (no race-pace target). |
| `event_date` | date \| None | event metadata | None on open-ended. |
| `event_locale` | str \| None | event metadata | None on open-ended. |
| `days_to_event_at_phase_end` | int \| None | `event_date - phase_end_date` | None on open-ended. Sharpens Taper-length picking (§9). |
| `estimated_duration_hr` | float \| None | §H.2 `estimated_duration_hr` | Drives Taper anchor selection (multi-day → longer Taper). |
| `locales` | dict[locale_id → {locale_name, locale_kind, summary}] | trimmed from 2C bundle | Athlete-scoped locales relevant to phase prescriptions. Excludes locales the synthesizer is unlikely to prescribe against (heuristic: per discipline_mix). |
| `equipment_per_locale` | dict[locale_id → effective_equipment_view] | trimmed from 2C resolution output | Per-locale exercise + sport availability (resolution tier 1/2/3). Trim heuristic: only locales in `locales`. |
| `terrain_summary` | dict | trimmed from 2B | Race-format-relevant terrain features (elevation profile, surface mix, technical sections). Trim heuristic: relevant per `race_format`. |
| `nutrition_tier` | dict | trimmed from 2E | Race-day fueling + heat-acclim tier. Synthesizer reads to inform session-level fueling cues (`fueling_practice` flag is spec-auto on Taper; per-phase synth references for context only). |

### 3.5 Retry context (populated on retries only)

| Variable | Type | Source | Notes |
|---|---|---|---|
| `retries_used` | int (0 to cap) | orchestrator §5.5 counter | 0 on initial call; 1+ on validator- or seam-driven retry. |
| `cap` | int | `capped_retries_per_phase` (v1 default 2) | Surfaces to the prompt so the model knows whether further retry is possible. |
| `rule_failures` | list[dict] \| None | None on initial; populated on validator-driven retry | Each: `{rule_name, severity, detail, affected_session_ids, suggested_constraint}` (per D8 hybrid). |
| `seam_issues` | list[str] \| None | None on initial / validator retry; populated on seam-driven retry per §6.2 | Constraint statements from the seam reviewer. |
| `seam_direction` | `'re_prompt_prior'` / `'re_prompt_next'` \| None | None on initial / validator retry; populated on seam-driven retry | Tells the synthesizer whether the prior or next phase's boundary triggered the retry (i.e., whether to shift the START or the END of this phase). |

### 3.6 Intentionally NOT passed (scope discipline)

These would either bloat the §11.2 ~8000 input budget or push the synthesizer outside its authority:

- **Phases other than `p`'s immediate predecessor.** Synthesizer reasons about one phase; cross-phase coherence is the seam reviewer's + final-validator's job.
- **Spec-auto coaching-flag computation rules.** Synthesizer must NOT emit spec-auto flags; passing the rules would invite drift. The closed-set enum (D5) is the only flag taxonomy the synthesizer sees.
- **Layer 0 reference data verbatim.** 2C resolution output (per-locale effective equipment view) is the trimmed surface; the raw Layer 0 exercise library + sports framework are NOT passed.
- **PR_Verification_Status / Project_Backlog / CLAUDE.md context.** Process-level documents; no synthesis bearing.
- **The seam-reviewer's authority bounds / verdict semantics.** Passed only as `seam_issues` constraint statements when re-prompted; reviewer's prompt body is internal to that surface.
- **Prior plan versions other than the immediate parent.** When `plan_refresh` T3 cross-phase routes here, only the current-parent `prior_plan_session_window` slices matter; deeper history adds noise.

---

## 4. Output schema + tool definition

The synthesizer MUST respond by invoking the `record_phase_sessions` tool exactly once. No free-form output. Tool input schema mirrors §7.2 `PlanSession` (per-call subset) plus a `phase_synthesis_notes` rationale field and an optional `opportunities` array (per §8.7 LLM-emitted exception). Orchestrator-filled metadata fields are NOT in the tool schema: `session_id` (UUID assigned post-parse), `plan_version_id` (assigned by orchestrator), `is_ad_hoc` (always False for per-phase synth — orchestrator post-fills), `ad_hoc_request_payload` (always None — orchestrator post-fills), `phase_metadata` (orchestrator post-fills from `PhaseSpec`).

```json
{
  "name": "record_phase_sessions",
  "description": "Record the synthesized PlanSession list for this phase. Call this tool exactly once. Do not emit free-form text outside the tool call.",
  "input_schema": {
    "type": "object",
    "required": ["sessions", "phase_synthesis_notes"],
    "additionalProperties": false,
    "properties": {
      "sessions": {
        "type": "array",
        "minItems": 1,
        "items": {
          "type": "object",
          "required": [
            "date", "day_of_week", "session_index_in_day", "time_of_day",
            "kind", "duration_min", "intensity_summary",
            "session_notes", "coaching_intent", "coaching_flags"
          ],
          "additionalProperties": false,
          "properties": {
            "date": {"type": "string", "format": "date"},
            "day_of_week": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
            "session_index_in_day": {"type": "integer", "minimum": 0, "maximum": 1},
            "time_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening", "unspecified"]},
            "kind": {"type": "string", "enum": ["cardio", "strength", "rest"]},
            "discipline_id": {"type": ["string", "null"]},
            "discipline_name": {"type": ["string", "null"]},
            "locale_id": {"type": ["string", "null"]},
            "locale_name": {"type": ["string", "null"]},
            "duration_min": {"type": "integer", "minimum": 0, "maximum": 480},
            "intensity_summary": {"type": "string", "enum": ["easy", "moderate", "hard", "mixed", "rest"]},
            "cardio_blocks": {
              "type": ["array", "null"],
              "items": {
                "type": "object",
                "required": ["block_kind", "duration_min", "intensity_zone", "intensity_target", "instructions"],
                "additionalProperties": false,
                "properties": {
                  "block_kind": {"type": "string", "enum": ["warmup", "main_set", "cooldown", "interval_set", "transition"]},
                  "duration_min": {"type": "integer", "minimum": 1, "maximum": 360},
                  "intensity_zone": {"type": "string", "enum": ["Z1", "Z2", "Z3", "Z4", "Z5", "mixed"]},
                  "intensity_target": {"type": "object", "description": "Free-shape per-discipline: {pace_per_km: '5:30'} | {power_w: 220} | {hr_bpm_low: 140, hr_bpm_high: 155} | {rpe: 6}"},
                  "instructions": {"type": "string", "minLength": 1, "maxLength": 400},
                  "repetitions": {"type": ["integer", "null"], "minimum": 1},
                  "rest_between_min": {"type": ["integer", "null"], "minimum": 0},
                  "rest_intensity_zone": {"type": ["string", "null"], "enum": ["Z1", "Z2", null]}
                }
              }
            },
            "strength_exercises": {
              "type": ["array", "null"],
              "items": {
                "type": "object",
                "required": ["exercise_id", "exercise_name", "resolution_tier", "sets", "reps_per_set", "load_prescription", "rest_between_sets_sec", "instructions", "coaching_flags"],
                "additionalProperties": false,
                "properties": {
                  "exercise_id": {"type": "string"},
                  "exercise_name": {"type": "string"},
                  "resolution_tier": {"type": "integer", "enum": [1, 2, 3]},
                  "substitute_text": {"type": ["string", "null"]},
                  "proxy_origin_id": {"type": ["string", "null"]},
                  "sets": {"type": "integer", "minimum": 1, "maximum": 10},
                  "reps_per_set": {"type": ["integer", "string"]},
                  "load_prescription": {"type": "string", "minLength": 1, "maxLength": 120},
                  "rest_between_sets_sec": {"type": "integer", "minimum": 0, "maximum": 600},
                  "tempo": {"type": ["string", "null"]},
                  "instructions": {"type": "string", "minLength": 1, "maxLength": 400},
                  "coaching_flags": {"type": "array", "items": {"type": "string"}, "maxItems": 6}
                }
              }
            },
            "rest_reason": {"type": ["string", "null"], "enum": ["planned_recovery", "overreach_protection", "travel_day", "athlete_unavailable", "taper_drop", null]},
            "session_notes": {"type": "string", "minLength": 1, "maxLength": 600},
            "coaching_intent": {"type": "string", "minLength": 1, "maxLength": 240},
            "coaching_flags": {
              "type": "array",
              "items": {
                "type": "string",
                "enum": [
                  "technique_emphasis",
                  "long_slow_distance",
                  "weak_link_targeted",
                  "overreach_test",
                  "discipline_specific_intensity",
                  "race_pace_specific"
                ]
              },
              "maxItems": 4
            }
          }
        }
      },
      "phase_synthesis_notes": {
        "type": "string",
        "minLength": 1,
        "maxLength": 600,
        "description": "Brief synthesis rationale for this phase: what shape you picked + why. Lands in plan_versions.notes JSONB per §7.11. Cite continuity decisions (volume entry, intensity ramp), deload placement, and any anchor overrides. Direct voice."
      },
      "opportunities": {
        "type": "array",
        "maxItems": 3,
        "items": {
          "type": "object",
          "required": ["text", "evidence_basis"],
          "additionalProperties": false,
          "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 240},
            "evidence_basis": {"type": "array", "items": {"type": "string"}, "minItems": 1}
          }
        },
        "description": "Optional Observation(category='opportunity') entries per §8.7 LLM-emitted exception. Max 3. Direct voice; cite evidence_basis (field references)."
      }
    }
  }
}
```

**Cross-session schema rules** (enforced post-parse by the orchestrator + by the §5.4 validator; rule_failures merged into the retry context per §3.5):

| Combination | Why invalid (catches in) |
|---|---|
| `kind == 'cardio'` + (`cardio_blocks` null OR empty) | §7.12 schema rule — output parser raises `Layer4OutputError('schema_violation')`. |
| `kind == 'cardio'` + (`strength_exercises` non-null OR `rest_reason` non-null) | Same. |
| `kind == 'strength'` + (`strength_exercises` null OR empty) | Same. |
| `kind == 'strength'` + (`cardio_blocks` non-null OR `rest_reason` non-null) | Same. |
| `kind == 'rest'` + (`cardio_blocks` non-null OR `strength_exercises` non-null OR `rest_reason` null OR `duration_min != 0` OR `discipline_id` non-null OR `locale_id` non-null) | Same. |
| Two sessions on same date + both `kind == 'strength'` | §5.4 `two_per_day_*` blocker. |
| Two sessions on same date + both `intensity_summary == 'hard'` | §5.4 `two_per_day_*` blocker. |
| Two sessions on same date + neither `kind == 'cardio'` | §5.4 `two_per_day_*` blocker. |
| `cardio_blocks[*].block_kind == 'interval_set'` with any of `repetitions` / `rest_between_min` / `rest_intensity_zone` null | §7.12 schema rule. |
| `cardio_blocks[*].block_kind ∈ {warmup, main_set, cooldown, transition}` with any of `repetitions` / `rest_between_min` / `rest_intensity_zone` non-null | §7.12 schema rule. |
| `strength_exercises[*].resolution_tier == 2` + `substitute_text` null | §7.12 schema rule. |
| `strength_exercises[*].resolution_tier == 3` + `proxy_origin_id` null | §7.12 schema rule. |
| `strength_exercises[*].resolution_tier == 1` + (`substitute_text` non-null OR `proxy_origin_id` non-null) | §7.12 schema rule. |
| `coaching_flags` contains a value not in the §10 closed-set enum | Schema enum rejects → `Layer4OutputError('schema_violation')` → one schema retry per §5.5, bail on second. |
| Session `date` outside `phase_start_date → phase_end_date` (inclusive) | §5.4 `phase_date_out_of_range_*` blocker (not in current rule list — prompt-only enforcement; flag for §5.4 expansion in §13). |

Schema retries do NOT consume the per-phase retry budget per §5.5.

---

## 5. System prompt (verbatim)

```
You are the per-phase synthesizer for an endurance and multi-sport training pipeline. Your job is to produce the day-by-day PlanSession list for ONE periodization phase (Base, Build, Peak, or Taper) given the athlete's full upstream context, the phase's intended volume + intensity targets, and (when not the first phase) the prior phase's accepted output for continuity.

You read upstream payloads (Layers 1, 2A–2E, 3A, 3B) trimmed to athlete-relevant slices, the phase's intended exit/entry state, optional prior-phase weekly rollup + last-week session detail, and (on retry) prior validator failures or seam-reviewer constraints. You emit exactly one tool call: record_phase_sessions, with sessions + phase_synthesis_notes + optional opportunities. No free-form text outside the tool call.

PHASE INTENT ANCHORS:

- BASE — aerobic capacity foundation. Volume builds gradually (per ACWR forward projection ≤ 1.25 wk-over-wk; sparse/very_sparse data_density requires even more conservative ramp). Intensity distribution 80/15/5 (Z1-Z2 / Z3 / Z4-Z5) ±10pp. The weekly cornerstone is a long_slow_distance session per primary discipline (emit the flag). Skill/technique work for skill-type weak_links surfaces via technique_emphasis.

- BUILD — phase-intent transition to higher intensity tolerance + race-specificity scaffolding. Intensity distribution 70/20/10 ±10pp. Last Build week may be an intentional brief overreach (emit overreach_test on all sessions in that week). First race-discipline-specific intensity work in the plan surfaces via discipline_specific_intensity. Strength accessory work for non-skill weak_links surfaces via weak_link_targeted.

- PEAK — top-end load + race-specific intensity placement. Intensity distribution 70/20/10 — SAME AS BUILD per §5.4 (do NOT shift to Z3+ dominant; that would break the validator's intensity_dist check). Differentiation from Build is via (a) volume shape — the highest-volume week of Peak is the "peak volume week" (orchestrator auto-flags peak_volume_marker; you don't emit it) — and (b) race-pace placement (you emit race_pace_specific on cardio sessions prescribed at exact race-target pace/power). Open-ended mode (race_format == 'open_ended'): you do NOT emit race_pace_specific (no race-pace target exists).

- TAPER — volume reduction + race-readiness consolidation. Taper length is YOUR coaching pick within the §6.1 mode-proportion budget — informed by race format + estimated_duration_hr (anchors below). Intensity distribution 75/15/10 ±10pp (slight Z3 retention; full intensity-drop is a coaching error — leg-snap risk on race day). Spec-auto Taper flags (race_rehearsal, fueling_practice, kit_check, pacing_lock, pre_race_taper) are computed by the orchestrator from days_to_event — DO NOT emit any of these yourself; the schema enum will reject them.

TAPER-LENGTH ANCHORS (use coaching judgment around these; record any override in phase_synthesis_notes):

- Sub-marathon single-day events (≤marathon distance): typical 1–2 weeks.
- Marathon-class / half-IM-class single-day events: typical 2–3 weeks.
- Full-IM-class single-day events: typical 3 weeks.
- Stage races / multi-day ultras / expedition AR (48–72h class): typical 3 weeks.
- Expedition AR >72h: typical 3–4 weeks.
- Open-ended mode (race_format == 'open_ended'): Taper applies only if 3B mode allocated Taper weeks (rare on open-ended); when present, default to 1 week as a deload-style drop.

DELOAD WEEK PLACEMENT (recovery_week — orchestrator-auto-flagged; you decide WHEN, orchestrator flags WHICH week):

- Standard mode: every 4th week is a deload week (typically 60–70% of preceding week's volume).
- Compressed mode: every 3rd week (denser progression).
- Extended mode: every 5th week.
- Custom mode: judgment — anchor on weekly volume curve + 3A aerobic_state/fatigue indicators.
- Override anchor with rationale when 3A state or schedule constraints warrant. Record the override in phase_synthesis_notes.
- Deload week is NOT a rest week — sessions still occur; volume is reduced ~30–40%; intensity may stay or drop slightly (judgment).

PRIOR-PHASE CONTINUITY (when prior_phase_weekly_rollup is provided):

- Volume entry: open within ~10% of prior_phase_intended_exit_volume per discipline. Ramp per ACWR ≤ 1.25 wk-over-wk.
- Intensity distribution shifts toward THIS phase's intended_intensity_distribution GRADUALLY across week 1 (do not jump distribution day 1 of week 1).
- If prior_phase_last_week ended with a hard session: week 1 day 1 of this phase should NOT be hard (unless coaching_flags contains overreach_test or race_rehearsal rationale).
- Cite continuity-relevant decisions in phase_synthesis_notes (e.g., "Build wk 1 opens at ~7hr/wk Z2 to match Base wk N exit; Z3 introduction begins wk 2 with one tempo session.").

SCHEDULE RESPECT:

- Place sessions ONLY on §K-available days. session_index_in_day ∈ {0, 1} (max 2 sessions per day per §7.12).
- Two-per-day rules: NOT both kind == 'strength'; NOT both intensity_summary == 'hard'; at least one of the two must be kind == 'cardio'.
- session.duration_min ≤ available window duration_min for that day.
- No two consecutive hard sessions for the SAME discipline without coaching_flags containing overreach_test or race_rehearsal (validator catches rest_spacing_*; the prompt enforces upstream).
- Rest days: kind == 'rest', duration_min == 0, discipline_id == null, locale_id == null, rest_reason populated. Use rest days for full-rest days; use low-intensity easy cardio sessions for active recovery days (NOT rest days).

LOCALE + EQUIPMENT:

- (discipline_id, locale_id) pairs must be supported by equipment_per_locale[locale_id]. Validator catches sport_locale_incompatible_*.
- Strength exercises: prefer 2C resolution_tier 1 (canonical exercise available at locale); resolution_tier 2 substitute when locale lacks the canonical (populate substitute_text); resolution_tier 3 proxy as last resort (populate proxy_origin_id).
- Cardio sport-equipment requirements (e.g., bike for MTB session) must resolve in the locale's effective equipment view.

INJURY RESPECT:

- active_injuries lists current restrictions. Do NOT prescribe exercises that violate the restriction_text. Examples:
  - "left wrist: avoid wrist-extension-loaded exercises" → no pushups (allow fist-position pushups only), no overhead press with bar, no plank with extended wrists, no front-rack work; climbing grip-dominant moves OK.
  - "right knee: no high-impact" → no plyometric box jumps, no maximal-effort hill repeats; cycling + swimming OK.
- Reduced intensity / volume that's injury-driven is EXPECTED — do NOT inflate volume to "make up" for injury restrictions.

COACHING-FLAG EMISSION (LLM-EMITTED CLOSED SET ONLY — schema enum will reject unknowns):

PlanSession.coaching_flags may contain only:
- technique_emphasis — drill/skill work for a skill-type weak_link. Base phase typically.
- long_slow_distance — the weekly cornerstone long-duration aerobic session per primary discipline. Base phase typically (Build may carry a long session but flag less canonically).
- weak_link_targeted — strength accessory work for a non-skill 3A weak_link. Build phase typically; may carry into Peak for retention.
- overreach_test — intentional brief overreach week (typically last Build week before deload). Apply to ALL sessions in that week.
- discipline_specific_intensity — first race-discipline-specific intensity work in the plan (e.g., first race-pace interval session for the goal discipline). Build phase typically — apply to the FIRST such session, not subsequent ones.
- race_pace_specific — cardio session at exact race-target pace/power. Peak phase only. Open-ended mode: do NOT emit.

StrengthExercise.coaching_flags is open-set (per §7.4 examples): may include weak_link_targeted plus exercise-specific descriptors (e.g., 'eccentric_emphasis', 'unilateral_focus', 'plyometric'). No closed-set enforcement at the exercise level.

Spec-auto flags the orchestrator computes (DO NOT emit these — schema will reject):
- aerobic_base_focus (every Base-phase cardio session)
- recovery_day_after_long (day after long_slow_distance)
- volume_ramp_conservative (sparse data_density Base ramp)
- volume_ramp_aggressive (Build ACWR ≥ 1.25)
- peak_volume_marker (Peak's highest-volume week)
- tune_up_race (Peak with §H.2 tune-up date)
- race_day (event_date sessions)
- recovery_week (deload weeks per your placement)
- first_introduction_to_<discipline> (per-discipline first session)
- All Taper flags (race_rehearsal, fueling_practice, kit_check, pacing_lock, pre_race_taper)
- intensity_modulated (D-63 path only — not per-phase synth)

OPPORTUNITIES (optional, max 3 — LLM-emitted Observation exception per §8.7):

You may emit up to 3 Observation(category='opportunity') entries via the opportunities field — coaching observations NOT tied to a §5.4 rule (e.g., "athlete's MTB volume is climbing through Build; consider adding a technical-skill MTB session in Peak when bandwidth opens"). Direct voice; ≤240 chars per entry; cite evidence_basis (field references like 'layer2a.discipline_weights.mtb' or 'layer3a.weak_links[0]'). Skip the field if no opportunities surface.

RETRY CONTEXT (when retries_used > 0):

- If rule_failures is populated: prior pass's validator failures. Address each failure in this attempt. Common patterns: volume_band_exceeded → reduce session count or duration in the affected week; intensity_dist_drift → shift one Z3 session to Z2 (or vice versa); acwr_above_threshold → moderate the ramp; rest_spacing_violation → swap a hard session to easy or insert recovery.
- If seam_issues is populated: seam reviewer flagged a boundary problem with the prior or next phase. seam_direction tells you which side (re_prompt_prior → this phase's END needs adjustment; re_prompt_next → this phase's START needs adjustment).
- If retries_used == cap: this is your last attempt. Prioritize accepting validator-acceptable output over coaching-ideal — best-effort acceptance is the orchestrator's fallback when you cap out, but a passing plan is better than a marginal one.

VOICE FOR session_notes + coaching_intent:

- session_notes (1–3 sentences, ≤600 chars): athlete-facing summary of WHAT this session is + what to focus on. Direct coaching voice per CLAUDE.md. No platitudes. No "great job" / "consider trying" hedging. Example: "90min steady Z2 trail run, RPE 3-4. Hold conversational pace throughout. Focus on relaxed shoulders + steady cadence on climbs."
- coaching_intent (1 sentence, ≤240 chars): one tight sentence stating WHY this session exists in the plan structure. Consumed by Layer 3A re-eval — must be unambiguous and structural, not generic. Example: "Builds aerobic base capacity at trail-specific intensity to anchor Base wk 3 long-day cornerstone."

VOICE FOR phase_synthesis_notes (≤600 chars):

- Brief synthesis rationale for this phase. Cite: (1) how you handled prior-phase continuity (volume entry, intensity ramp shape); (2) deload placement + any anchor override; (3) Taper-length pick + rationale (Taper phase only); (4) any structural compromises forced by injuries/schedule/locale. Direct voice; no narrative padding. Example: "Build wk 1 opens 7hr/wk Z2 to match Base wk 8 exit; Z3 introduction wk 2 (one tempo run); standard-mode deload at wk 4 with 65% volume. Wrist injury restricts overhead strength wk 1-3 (no front-rack work; horizontal pushes only)."

AUTHORITY BOUNDS — WHAT YOU CANNOT DO:

- You cannot change phase boundaries, mode, or start_phase. Those are fixed by Layer 3B + §6.1/§6.4 before this call.
- You cannot prescribe sessions outside phase_start_date → phase_end_date.
- You cannot emit spec-auto coaching flags. The schema enum union will reject them.
- You cannot emit notable observations other than category='opportunity'. The schema only has the opportunities field.
- You cannot exceed 2 sessions per day (session_index_in_day capped at 1).
- You cannot prescribe to §K-unavailable days.
- You cannot violate active_injury restrictions or prescribe sports/exercises unavailable at the picked locale.
- You cannot emit more than 4 coaching_flags per session (schema cap; if more apply, prioritize the most distinctive).
- You cannot prescribe a duration exceeding the day's available window minutes.

ITERATION DISCIPLINE:

On retry (retries_used > 0): address EVERY entry in rule_failures + EVERY constraint in seam_issues. Do not silently drop or partially-address. If you judge a failure cannot be addressed without violating another rule, explain the conflict in phase_synthesis_notes — the orchestrator will surface this in best_effort_plan observation context when cap is hit.

VOICE: direct, evidence-grounded. No cheerleading. No hedging. Match a real endurance coach prescribing a phase to a serious athlete.
```

---

## 6. User prompt template (verbatim, with `{{var}}` placeholders)

```
PHASE SYNTHESIS REQUEST — {{phase_name}} ({{phase_weeks}} weeks) — attempt {{retries_used + 1}} of {{cap + 1}}

Plan context:
- Mode: {{mode}} (start_phase: {{start_phase}})
- Race format: {{race_format}}{{#if event_date}}, event {{event_date}} ({{days_to_event_at_phase_end}} days from this phase's end){{/if}}{{#if estimated_duration_hr}}, estimated race duration {{estimated_duration_hr}}hr{{/if}}
- Discipline mix: {{discipline_mix}} (weights: {{discipline_weights}})

THIS PHASE:
- Dates: {{phase_start_date}} → {{phase_end_date}} ({{phase_weeks}} weeks)
- Intended volume band per discipline (hr/wk): {{intended_volume_band}}
- Intended intensity distribution (Z1-Z2 / Z3 / Z4-Z5): {{intended_intensity_distribution}}

ATHLETE PROFILE (Layer 1):
{{athlete_profile_summary}}

ATHLETE STATE (Layer 3A):
- Aerobic state: {{aerobic_state}}
- Strength state: {{strength_state}}
- Data density: {{data_density}}
- Active injuries:
{{#each active_injuries}}  - {{this.body_part}} ({{this.severity}}): {{this.restriction_text}}
{{/each}}{{#unless active_injuries}}  (none)
{{/unless}}- Weak links:
{{#each weak_links}}  - [{{this.type}}, {{this.discipline}}] {{this.description}}
{{/each}}{{#unless weak_links}}  (none)
{{/unless}}

SCHEDULE (Layer 1 §K):
- Available days/week: {{available_days_per_week}}
- Daily windows:
{{#each daily_availability_windows}}  - {{this.day_of_week}}: {{#if this.available}}{{this.windows}}{{else}}unavailable{{/if}}
{{/each}}

LOCALES + EQUIPMENT (Layer 2C, athlete-relevant slices):
{{#each locales}}
- {{this.locale_id}} ({{this.locale_name}}, {{this.locale_kind}}): {{this.summary}}
  Equipment view: {{lookup equipment_per_locale this.locale_id}}
{{/each}}

TERRAIN (Layer 2B, race-format slice): {{terrain_summary}}

NUTRITION TIER (Layer 2E): {{nutrition_tier}}

{{#unless is_first_phase_in_plan}}
PRIOR PHASE CONTEXT — {{prior_phase_name}}:

Intended exit state:
- Volume per discipline: {{prior_phase_intended_exit_volume}}
- Intensity distribution: {{prior_phase_intended_exit_intensity}}

{{#if prior_phase_weekly_rollup}}
Weekly rollup (full prior phase):
{{prior_phase_weekly_rollup}}

Last week sessions (full detail — this is the seam-in):
{{prior_phase_last_week_sessions}}
{{else}}
(start_phase != 'Base' AND this is the first synthesized phase — prior-phase context is synthetic per §6.5; no real session detail.)
{{/if}}
{{/unless}}{{#if is_first_phase_in_plan}}
(This is the first synthesized phase{{#if start_phase}} (start_phase == '{{start_phase}}'){{/if}} — no prior-phase context.)
{{/if}}

{{#if seam_issues}}
SEAM CONSTRAINTS (from prior seam review — re-synthesis triggered; seam_direction = {{seam_direction}}):
{{#each seam_issues}}- {{this}}
{{/each}}
{{/if}}

{{#if rule_failures}}
PRIOR VALIDATOR FAILURES (address each in this attempt):
{{#each rule_failures}}- [{{this.rule_name}}, {{this.severity}}] {{this.detail}}
  Affected sessions: {{this.affected_session_ids}}
  Suggested constraint: {{this.suggested_constraint}}
{{/each}}
{{/if}}

Synthesize this phase. Call `record_phase_sessions` with the day-by-day PlanSession list, phase_synthesis_notes rationale, and any opportunities observations.
```

Template variables interpolate as plain text. Tables (`prior_phase_weekly_rollup`, `intended_volume_band`, `intended_intensity_distribution`, `equipment_per_locale`, `nutrition_tier`, `terrain_summary`) and structured lists (`prior_phase_last_week_sessions`) are rendered as Markdown tables / JSON blocks by the orchestrator at prompt-build time. Mustache-style `{{#if}}` / `{{#each}}` / `{{#unless}}` / `{{lookup}}` blocks are pseudo-code for the orchestrator's template engine — actual rendering language is an implementation detail (Python f-string + conditional concat is fine for v1).

---

## 7. Model + sampling config

| Setting | Value | Source |
|---|---|---|
| `model` | `claude-sonnet-4-6` | `Layer4_Spec.md` §3.1 v1 default `model_synthesizer`. |
| `temperature` | 0.2 | `Layer4_Spec.md` §3.1 v1 default `temperature` (synthesizer default; not lowered like the reviewer per §5.2 step 4.1). |
| `max_tokens` | 6000 | Headroom over §11.2 ~3000 output token estimate to accommodate (a) extended thinking tokens counted toward output, (b) worst-case dense session text for 4-week phases with 2-a-day sessions, (c) `phase_synthesis_notes` + `opportunities`. |
| Extended thinking | Enabled, ~5000 budget tokens | D2 — max defensive. Latency tax ~3–5s, fits inside the §11.1 ~5–8s per-phase budget envelope (we're tight on p50 but well inside p95). |
| Tool choice | `{"type": "tool", "name": "record_phase_sessions"}` | Forces tool use. |
| Stop sequences | (none) | Tool-use natural stop. |

**Token accounting per call (rough, no retries):** ~8000 input + ~5000 extended thinking + ~3000 tool-use output = ~8000 input / ~8000 total output (with thinking). Cost at v1 Sonnet 4.6 pricing ($3/MTok in + $15/MTok out): ~$0.024 + ~$0.120 = ~$0.144 per phase. For Andy's `plan_create` case (4 phases): ~$0.58 synthesizer + ~$0.18 seam-review = ~$0.76 total (no retries). Matches §11.3 headline range $0.50–1.10 per invocation.

**Latency budget per call (no retries):** ~5–8s per §11.1 — base LLM call ~3–4s + extended thinking ~3–5s + parse ~50ms. Worst case retry: 2× cap = ~16s added per phase. Total `plan_create` worst case: ~25s base + ~64s retry tax = ~89s, inside the §11.1 p99 ~120s ceiling.

---

## 8. Authority bounds — explicit forbid list (recap)

The system prompt §5 above carries the authority-bound rules in-band. This subsection mirrors the §5 "AUTHORITY BOUNDS" block, with prompt-design notes on how each is enforced:

| Bound | Enforcement in this prompt |
|---|---|
| Cannot change phase boundaries / mode / start_phase | Inputs are read-only; schema does not accept phase-override fields. Orchestrator post-fills `phase_metadata` from `PhaseSpec`. |
| Cannot prescribe outside phase_start_date → phase_end_date | Prompt rule + post-parse check by orchestrator. (Validator §5.4 expansion candidate per §13.) |
| Cannot emit spec-auto coaching flags | Schema `coaching_flags` enum union excludes all spec-auto flag names (closed set of 6 LLM-emitted only — see §10). |
| Cannot emit notable observations other than category='opportunity' | Schema only has `opportunities` array (max 3); other observation categories not in tool schema. |
| Cannot exceed 2 sessions per day | `session_index_in_day` schema cap (max 1, i.e., 0 or 1). |
| Cannot prescribe to §K-unavailable days | Validator §5.4 `schedule_violation_*`; prompt rule enforces upstream. |
| Cannot violate injury restrictions | Validator §5.4 `injury_violation_*`; prompt rule enumerates examples. |
| Cannot prescribe sports/exercises unavailable at picked locale | Validator §5.4 `sport_locale_incompatible_*` + `equipment_unavailable_*`; prompt rule enforces upstream. |
| Cannot exceed 4 `coaching_flags` per session | Schema `maxItems: 4` (matches seam-reviewer convention; if 5+ apply, prioritize most distinctive). |
| Cannot exceed daily window duration | Validator does NOT currently check this (§13 candidate); prompt rule + validator §5.4 `schedule_violation_*` covers most cases via window-fit check. |
| Cannot emit free-form text alongside the tool call | Tool-choice forcing + prompt rule "No free-form text outside the tool call." |

Drift on prose-only rules (e.g., spec-auto flag in `coaching_flags`, free-form text alongside) surfaces as schema-violation in production telemetry. Per §11.8 alert thresholds, retry-rate > 20% triggers prompt-tightening investigation.

---

## 9. Calibration anchors (D6 deload + D7 Taper)

Per D6 + D7: anchored coaching judgment, NOT thresholds. Pure-cadence rules invite gaming ("standard mode = every 4th week"); pure judgment invites drift across calls. Anchors-with-override is the v1 calibration.

### 9.1 Deload cadence anchors per mode

| Mode | Anchor cadence | Anchor deload volume | Override triggers |
|---|---|---|---|
| `standard` | Every 4th week | 60–70% of preceding week's volume | 3A `aerobic_state == 'low'` → consider earlier deload (every 3rd wk); athlete travel/schedule disruption → shift cadence by ±1 wk; phase < 4 weeks → no deload (one-cycle phase). |
| `compressed` | Every 3rd week | 60–70% | Same set; phase < 3 weeks → no deload. |
| `extended` | Every 5th week | 65–75% (longer cycle, slightly less aggressive cut) | Same set. |
| `custom` | Judgment | Judgment | Anchor on weekly volume curve + 3A state. Record placement rationale in `phase_synthesis_notes`. |

The orchestrator auto-flags `recovery_week` per §8.6 on every session in a week where volume is ≥30% below the rolling-3-week average — the synthesizer doesn't emit the flag; placement is the synthesizer's call.

### 9.2 Taper-length anchors per race format

| Race format | Anchor Taper length | Notes |
|---|---|---|
| Sub-marathon single-day (≤marathon distance — half-marathon, 10K, criterium, time-trial, sub-marathon trail) | 1–2 wk | Shorter races recover faster; 1 wk for fast-recovery athletes, 2 wk for older/lower-fitness athletes. |
| Marathon-class single-day | 2–3 wk | Marathon-distance running + similar-duration single-day events (long-course MTB, Olympic-distance triathlon). |
| Half-IM-class single-day | 2–3 wk | |
| Full-IM-class single-day | 3 wk | |
| Multi-day ultra | 3 wk | |
| Stage race | 3 wk | |
| Expedition AR 48–72h | 3 wk | Andy's case (Pocket Gopher Extreme). |
| Expedition AR >72h | 3–4 wk | Longer freshness window for ultra-endurance recovery debt. |
| Open-ended (no race) | 1 wk if 3B allocated Taper weeks at all (rare) | Open-ended plans typically don't taper; if Taper weeks exist, treat as a deload-extension. |

Anchors are evidence-grounded starting points. Override with rationale in `phase_synthesis_notes` when athlete-specific factors warrant (e.g., recent illness → longer taper; very high aerobic_state + young athlete → shorter taper).

### 9.3 Volume ramp anchors per data_density

Drives Base-phase opening week volume:

| `data_density` | Week-1 volume target | Rationale |
|---|---|---|
| `dense` | Within 10% of 2A `phase_load_bands[discipline][Base].low` | Athlete has solid baseline data; can open near band low. |
| `typical` | Within 20% below 2A band low | Modest conservatism. |
| `sparse` | 30–50% below band low | Conservative ramp; protect against unmeasured deconditioning. |
| `very_sparse` | 50–70% below band low | Maximum conservatism; orchestrator auto-flags `volume_ramp_conservative` per §8.2. |

These anchors apply to the FIRST week of Base only (or Build/Peak/Taper when `start_phase != 'Base'` AND this is the first synthesized phase — same ramp logic applies). Subsequent weeks ramp per ACWR ≤ 1.25.

---

## 10. `coaching_flags` closed-set rules (D5)

The synthesizer's LLM-emitted closed set per §§8.2–8.6:

| Flag | Phase | Emit on | Frequency | Conflicts |
|---|---|---|---|---|
| `technique_emphasis` | Base typically | A session containing a drill/skill block for a skill-type 3A `weak_link` | Per session (one flag per session emitting it) | None. |
| `long_slow_distance` | Base typically (may carry into Build) | The weekly long-duration aerobic cornerstone per primary discipline | One per discipline per week | None — but the FOLLOWING day's session gets the spec-auto `recovery_day_after_long` flag. |
| `weak_link_targeted` | Build typically (may carry into Peak) | A strength accessory exercise OR a cardio session addressing a non-skill 3A `weak_link` | Per session/exercise (the flag may live on either `PlanSession.coaching_flags` OR `StrengthExercise.coaching_flags` depending on whether the whole session is weak-link-targeted or just one exercise within it) | None. |
| `overreach_test` | Build typically (last Build wk before deload) | ALL sessions in the overreach week | Whole week | Mutually exclusive with `recovery_week` (orchestrator auto-flagged); a week cannot be both. |
| `discipline_specific_intensity` | Build | The FIRST race-discipline-specific intensity work in the plan | Once per plan (per discipline) — flag the first such session, not subsequent ones | None. |
| `race_pace_specific` | Peak only | Cardio session prescribed at exact race-target pace/power | Per session | Mutually exclusive with `race_format == 'open_ended'` (no race-pace target exists). |

Other flag names: `Layer4OutputError('schema_violation')` → one schema retry per §5.5; bail on second failure.

**StrengthExercise.coaching_flags** is OPEN-SET per §7.4 examples — synthesizer may use any descriptor (e.g., `'eccentric_emphasis'`, `'unilateral_focus'`, `'plyometric'`, `'weak_link_targeted'`). No closed-set enforcement at the exercise level.

---

## 11. Edge cases + invalid combinations

### 11.1 First phase in plan (no prior_phase context)

`is_first_phase_in_plan == True` AND `start_phase == 'Base'` (no prior plan to continue from). Prompt's "PRIOR PHASE CONTEXT" block is replaced with "(This is the first synthesized phase — no prior-phase context.)". Synthesizer opens Base wk 1 at the §9.3 ramp anchor for the athlete's `data_density`.

### 11.2 `start_phase != 'Base'` AND first phase

`is_first_phase_in_plan == True` AND `start_phase ∈ {'Build', 'Peak', 'Taper'}`. Prompt's PRIOR PHASE CONTEXT block uses synthetic `prior_phase_intended_exit_volume` + `prior_phase_intended_exit_intensity` from 2A `phase_load_bands` for the immediately-prior skipped phase (no real session detail). Synthesizer opens this phase as if the athlete completed the prior phase at intended exit state. Note in `phase_synthesis_notes`: "Starting at {start_phase}; assumed prior {prior_phase_name} exit state per 2A bands."

### 11.3 Single-phase Pattern A (e.g., Taper-only)

Per §6.5: when `phase_structure.phases` has only one entry (e.g., `start_phase='Taper'` + 4-week event window), this prompt is called once. No seam review fires (per `Layer4_SeamReviewer_v1.md` §1 single-phase skip).

### 11.4 Retry with `rule_failures`

`retries_used > 0` AND `rule_failures` non-empty. Synthesizer reads each failure + suggested_constraint and re-synthesizes addressing each. Common patterns:

- `volume_band_exceeded_week_3` → reduce session count or duration in wk 3 to land inside band.
- `intensity_dist_drift_phase_build` → shift one Z3 session to Z2 (or vice versa) to land inside ±10pp tolerance.
- `acwr_forward_projection_above_1_4` → moderate the wk-over-wk ramp.
- `rest_spacing_violation` → swap a hard session to easy or insert a recovery session.
- `equipment_unavailable_<exercise>` → use 2C resolution_tier 2 substitute or tier 3 proxy.
- `injury_violation_<body_part>` → swap the exercise for an injury-compatible alternative.

### 11.5 Seam-driven retry with `seam_issues`

`seam_issues` non-empty AND `seam_direction` populated. Per §6.2: seam reviewer flagged a boundary issue; orchestrator re-prompts THIS phase (the targeted side per `seam_direction`):

- `seam_direction == 're_prompt_prior'` → THIS phase's END (last week) needs adjustment. Common: prior phase ends too high in volume → taper down THIS phase's last week toward a cleaner seam with the next phase.
- `seam_direction == 're_prompt_next'` → THIS phase's START (first week) needs adjustment. Common: next phase opens too aggressive → ramp in THIS phase's first week more gradually.

Seam-driven retries SHARE the per-phase retry counter with validator retries per §5.5 — a phase that already consumed 2 retries on validator failures has zero budget for seam-driven retries (orchestrator records the seam direction but does not re-call this prompt; emits `seam_unresolved` observation per §6.2).

### 11.6 Active injury severely restricting a primary discipline

Example: Andy's wrist injury + climbing-heavy phase. Synthesizer reduces climbing intensity (no grip-extension moves) but maintains climbing volume via grip-dominant routes. Does NOT inflate other-discipline volume to "compensate." `phase_synthesis_notes` cites the restriction's impact.

### 11.7 Sparse / very_sparse data_density

Per §9.3: wk 1 volume opens 30–70% below 2A band low. Validator's `volume_band_*` is `warning` severity at ±5%, `blocker` at ±15% — sparse-density wk 1 will trigger `warning` (intentional; not retried). Orchestrator auto-flags `volume_ramp_conservative` on each cardio session per §8.2; synthesizer does NOT emit this flag.

### 11.8 Custom mode `phase_weeks`

3B `mode == 'custom'` passes `phase_weeks` dict verbatim. Synthesizer honors the dict's value for `phase_name`. Deload cadence anchor (§9.1) falls back to coaching judgment.

### 11.9 Open-ended mode (no event)

`race_format == 'open_ended'` AND `event_date is None`. Synthesizer:

- Does NOT emit `race_pace_specific` (no race-pace target exists).
- May NOT prescribe a Taper at all if 3B did not allocate Taper weeks (most open-ended cases). If Taper weeks exist, treat as a deload extension (§9.2).
- `phase_synthesis_notes` cites the open-ended framing.

### 11.10 Unknown coaching flag emission

Synthesizer emits a flag not in the §10 closed set → schema enum rejects → output parser raises `Layer4OutputError('schema_violation')`. Per §5.5: one schema retry (counter does NOT consume per-phase budget); on second failure, bail out of the Layer 4 call. Surfaces in §11.8 alert thresholds.

### 11.11 Two-per-day combo violations

Synthesizer prescribes two sessions on the same date violating §7.12 (both strength, both hard, neither cardio). Validator §5.4 catches as `two_per_day_*` blocker; retry per §11.4. Prompt's "two-per-day rules" block in §5 system prompt is the primary defense.

### 11.12 No tool call emitted

Synthesizer responds with free-form text instead of invoking `record_phase_sessions` (e.g., explains its reasoning narratively): parser raises `Layer4OutputError('schema_violation')`. Same retry/bail policy as 11.10. Tool-choice forcing + prompt's "No free-form text outside the tool call" are the defenses.

### 11.13 phase_synthesis_notes overflow

Synthesizer emits a `phase_synthesis_notes` exceeding 600 chars. Schema `maxLength: 600` rejects → schema retry per §5.5. The 600 cap is the v1 default; tunable per §13.

### 11.14 Sessions outside phase date range

Synthesizer emits a session with `date` outside `phase_start_date → phase_end_date`. Currently NOT in §5.4 validator rule set (§13 candidate); orchestrator post-parse check rejects → `Layer4OutputError('phase_date_out_of_range')`. Defensive prompt rule + post-parse check; no special telemetry yet.

---

## 12. Test scenarios (v1)

Maps to `Layer4_Spec.md` §13 — primarily §13.2 (plan_create scenarios TS-1..TS-14) + §13.6 (coaching-flag emit scenarios). Adds prompt-body-specific tests with PPS- prefix.

| # | Scenario | Setup | Expected output behavior |
|---|---|---|---|
| PPS-1 | Clean first Base phase, standard mode, typical data_density | 4-discipline athlete, dense data, no injuries, full Base 8wk per 3B | wk 1 opens within 10% of 2A band low; ramp ≤1.25 ACWR; deload at wk 4; `long_slow_distance` flag on weekly cornerstone; `technique_emphasis` on skill weak_link sessions |
| PPS-2 | Build with prior Base context | Continuation from PPS-1's Base; prior_phase_weekly_rollup + prior_phase_last_week_sessions populated | wk 1 opens at ~Base wk 8 exit volume; intensity distribution shifts gradually toward 70/20/10; deload at wk 4 of Build (if Build ≥ 4wk); `discipline_specific_intensity` on first race-pace session |
| PPS-3 | Peak with race_pace_specific placements | Build complete; race in 6 weeks; marathon format | Volume shape produces highest-volume week (orchestrator auto-flags `peak_volume_marker`); intensity stays 70/20/10 (NOT shifted to Z3 dominant); `race_pace_specific` flag on cardio sessions at race-target pace |
| PPS-4 | Taper picking for marathon (anchor 2–3wk) | race_format='marathon', estimated_duration_hr=3.5, 3B allocated 2 Taper weeks | Synthesizer uses 2wk Taper; intensity 75/15/10 maintained (NOT zero-intensity); `phase_synthesis_notes` cites "2wk Taper matches marathon-class anchor" |
| PPS-5 | Taper picking for expedition AR 48-72h (anchor 3wk) | race_format='expedition_ar_48_72h', estimated_duration_hr=58, 3B allocated 3 Taper weeks | Synthesizer uses 3wk Taper; intensity 75/15/10; phase_synthesis_notes cites anchor |
| PPS-6 | Deload placement standard mode (every 4th wk) | 8wk Build in standard mode | Deload at wk 4 with volume 60–70% of wk 3; orchestrator auto-flags `recovery_week`; synthesizer does NOT emit the flag |
| PPS-7 | Active wrist injury in climbing-heavy mix | active_injuries=[{body_part:'left wrist', restriction_text:'avoid wrist-extension-loaded'}], discipline_mix includes climbing + strength | No overhead press / front-rack / extended-plank work; pushups in fist position only; climbing grip-dominant routes prescribed; phase_synthesis_notes cites restriction impact |
| PPS-8 | Sparse data_density Base ramp | data_density='sparse' | wk 1 volume 30–50% below 2A band low; subsequent ramp ≤1.25 ACWR; orchestrator auto-flags `volume_ramp_conservative` on cardio sessions |
| PPS-9 | Custom mode phase_weeks | mode='custom', phase_weeks={Base:6, Build:4, Peak:3, Taper:2} for this Build call | 4-week Build per dict verbatim; deload at wk 3 or 4 per coaching judgment (no fixed anchor); phase_synthesis_notes cites custom-mode rationale |
| PPS-10 | start_phase='Peak', first phase synth | is_first_phase_in_plan=True, start_phase='Peak', synthetic prior Build exit state | wk 1 opens at synthetic Build exit; phase_synthesis_notes cites "Starting at Peak; assumed prior Build exit per 2A bands" |
| PPS-11 | Validator-driven retry — volume band exceeded | rule_failures=[{rule_name:'volume_band_exceeded_week_2', severity:'blocker', suggested_constraint:'wk 2 volume ≤ 9hr/wk for trail_running'}] | Retry reduces wk 2 trail_running session count or duration; phase_synthesis_notes acknowledges the failure addressed |
| PPS-12 | Seam-driven retry — re_prompt_next direction | seam_issues=['Peak wk 1 must hold ≥60% Z2 with at most one Z3 intro session'], seam_direction='re_prompt_next' | Retry adjusts THIS phase's first week (Peak wk 1) to hold Z2 dominance with one Z3 intro session |
| PPS-13 | Unknown coaching flag emission defense | Synthetic: prompt-stress where the model emits 'super_long_distance' (not in §10 closed set) | Schema enum rejects → Layer4OutputError('schema_violation'); one schema retry; bail on second |
| PPS-14 | Open-ended mode Base→Build | race_format='open_ended', event_date=None | No `race_pace_specific` emitted (Peak phase); Taper may not exist; phase_synthesis_notes cites open-ended framing |
| PPS-15 | Two-per-day strength+strength violation defense | Synthetic: model places two strength sessions on same date | Validator §5.4 `two_per_day_*` blocker; retry; synthesizer fixes by swapping one strength to cardio |

These slot into `Layer4_Spec.md` §13 under §13.2 `plan_create` scenarios + §13.6 coaching-flag emit scenarios when the next §13 expansion happens; they're prompt-body-specific tests that don't belong in the spec body.

---

## 13. Open items / tuning candidates

All v1; tune post-launch per the §12.4 catch-all in `Layer4_Spec.md`.

- **Extended thinking budget (5000 tokens, D2)** — max-defensive starting point. If quality is stable at lower budgets (e.g., 3000–4000), drop to claw back ~1–2s latency per phase.
- **`max_tokens` cap (6000)** — derived from §11.2 output estimate + extended-thinking headroom. May need to raise for dense 5-discipline AR phases (Andy's case at peak weeks) — measure actual output sizes post-launch.
- **Closed-set flag enum (D5)** — 6 LLM-emitted flags is the v1 set per §§8.2–8.6. Adding flags requires stop-and-ask trigger #5 schema change. Watch for production cases where the synthesizer wants to emit a flag we don't have (e.g., race-specific gear-rehearsal); add via spec amendment.
- **Deload cadence anchors (D6, §9.1)** — every 4th / 3rd / 5th wk per mode is conventional periodization; tune from measured fatigue/performance data once telemetry exists.
- **Taper-length anchors (D7, §9.2)** — race-format-specific anchors are evidence-grounded starting points. Expedition AR anchors (Andy's case) will get the first stress test.
- **Volume-ramp anchors per data_density (§9.3)** — 30–70% below band low for sparse/very_sparse is conservative. Measure athlete-reported readiness post-Base to validate.
- **`session_notes` / `coaching_intent` length caps (D9)** — 600 / 240 chars. If synthesizer routinely hits caps, raise; if entries are routinely well under, lower to save tokens.
- **Per-locale equipment trim heuristic (D3)** — currently "locales in `locales` field." May need refinement if athletes have many locales and the trim drops one the synthesizer would have used.
- **Prior-phase weekly rollup shape (D4)** — currently per-(week, discipline) table. May need expansion (e.g., per-day intensity-distribution columns) if continuity quality drifts.
- **RuleFailure retry context (D8)** — `suggested_constraint` field is new; relies on orchestrator generating it (out of scope for this prompt). Synthesizer reads if populated; falls back to `detail` if absent.
- **`phase_date_out_of_range` validator rule** — currently prompt-only + post-parse defensive check; promote to §5.4 validator rule on next §5.4 expansion.
- **Validator daily-window-fit rule** — currently NOT in §5.4 rule list. Synthesizer enforces via prompt rule. Promote to §5.4 if production cases show drift.
- **Synthesizer-emit observability** — `phase_synthesis_notes` lands in `plan_versions.notes` JSONB per §7.11. Schema for the JSONB structure (e.g., `{"phase_synthesis_notes": {"Base": "...", "Build": "...", ...}}`) is orchestrator-side and not pinned here.

None are spec-contract decisions — all are prompt-design choices Andy can adjust by editing this file without touching `Layer4_Spec.md`. A v2 would be `Layer4_PerPhase_v2.md` per Rule #12.

---

## 14. Gut check — deferred to Layer 4 §14 retro

Per `Layer4_Spec.md` §12.6, the spec's §14 retrospective is deferred to a fresh-eyes follow-on session before Layer 4 implementation begins. This prompt-body's gut check folds into that retro: the per-phase synthesizer is the load-bearing prompt of the 5-prompt arc — `plan_create` does not work without it — and conventions established here (tool-use, extended thinking, hybrid input, closed-set flag enum, schema length caps) propagate forward to the remaining 3 (per-tier T1/T2, single-session, race-week-brief). The retro is the right venue to evaluate whether those conventions held up across all 5 — premature to retro this one prompt in isolation.

Inline risks worth flagging for the §14 retro to fold in:

1. **Token-budget margin for multi-discipline AR athletes.** §11.2 ~8000 input estimate assumes 3–4 discipline / 2–3 locale athletes. 5-discipline AR athletes with 4+ locales may push input toward 12000+ tokens once equipment views + prior-phase rollups are rendered. If budget breach is frequent, D3 hybrid trim needs sharper heuristics (e.g., drop equipment views for locales not used in the current phase).
2. **Extended-thinking 5000 may be over-budgeted.** D2 was the max-defensive choice. Reasoning-heavy phases (Build with intensity ramp + race-pace introduction + weak-link strength work) probably benefit; clean Base phases may not. Production telemetry on thinking-token utilization will tell us if we can drop to 3000.
3. **Closed-set flag enum's phase-applicability is prompt-only.** Schema rejects unknown flags but allows any LLM-emitted flag in any phase. Misuse (e.g., `race_pace_specific` in Base) won't be caught by the validator. Promote to §5.4 rule (`coaching_flag_phase_mismatch_*`) if production shows drift.
4. **Continuity coupling to seam-reviewer expectations.** Both prompts must honor each other's framing — the synthesizer prescribes within bands the reviewer evaluates against. If the reviewer's calibration anchors (§9 of `Layer4_SeamReviewer_v1.md`: 10%/8pp/25% drift thresholds) tune away from the synthesizer's continuity rules (§5 system prompt's ACWR ≤ 1.25, intensity distribution ±10pp), the two will conflict — flagging more re-prompts than necessary. Joint tuning is the right call.
5. **Deload-week judgment under custom mode.** §9.1 falls back to "judgment" for custom mode. If athletes pick custom mode for legitimate reasons (e.g., constrained schedule), deload placement quality is unmeasured. Production telemetry on cap_hit rate for custom-mode plans will be the leading indicator.
6. **`phase_synthesis_notes` orphan risk.** It lands in `plan_versions.notes` JSONB but no consumer reads it yet. If we don't wire a downstream consumer (e.g., the diff renderer per D-64 §6.3, or the §14 retro's qualitative review surface), the synthesizer's reasoning is write-only. Track in §14 retro.

---

*End of Layer 4 Per-Phase Synthesizer Prompt v1. Next prompt body (Andy's pick from queue): per-tier T1/T2 synthesizer / single-session synthesizer (D-63) / race-week-brief.*
