# Layer 4 — Plan Refresh T1 Synthesizer Prompt Body (D-64)

**Prompt name:** `Layer4_RefreshT1`
**Entry point:** `llm_layer4_plan_refresh` with `tier='T1'` (`Layer4_Spec.md` §3.2)
**Pattern:** B (single LLM call + deterministic validator; no seam reviewer; no phase decomposition)
**Caller:** D-64 athlete-initiated 2-day refresh (`Plan_Refresh_D64_Design_v1.md` §3.1)
**Status:** v2 — 2026-05-17 (Step 4d carry-forward — §4.3-wins amendment ripple)
**Date:** 2026-05-17
**Position in arc:** Fourth of 5 prompt bodies (after `Layer4_SeamReviewer_v1.md`, `Layer4_PerPhase_v1.md`, `Layer4_SingleSession_v1.md`; companion `Layer4_RefreshT2_v1.md` shipped same session).

**v2 amendment summary (2026-05-17, Step 4d carry-forward):** Per the `Layer4_Spec.md` §3.2 §4.3-wins amendment landed in Step 4b/c (`layer3b_payload` is required on every refresh tier), the T1 prompt body's "T1 doesn't re-run 3B; periodization shape inherited from adjacent-session metadata" framing is retired. Surgical edits: D3 source-decision row (3B added to T1 payload set); §3.5 (periodization shape header + variables re-grounded against freshly-re-run 3B); §3.8 (the "intentionally NOT passed" row for `layer3b_payload` removed). No other sections change. v1 retained as in-project history per Rule #12.

---

## Source decisions (this session, Andy 2026-05-17)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Tool-use** (`record_refresh_sessions`); single tool, single call; the `sessions` argument is a `list[PlanSession]` (0..4 entries for T1; empty when the refresh window is entirely rest by athlete schedule + coaching choice). Strict JSON schema with `additionalProperties: false` at every nesting level. | Inherits seam-reviewer + per-phase + single-session convention. Multi-session list output is the T1/T2 deviation from single-session's single-object output. |
| D2 | Extended thinking budget | **~3000 tokens.** | T1 is smaller-decision-space than per-phase (no multi-week combinatorics) but slightly larger than single-session (continuity-with-adjacent + multi-session coherence checks). Sits between single-session's 3500 (one session, no continuity) and per-phase's 5000 (multi-week combinatorial). Skews lower because T1 inherits the periodization shape rather than synthesizing it. |
| D3 | Input format | **Full payloads verbatim** for 3A + **3B (per §4.3-wins amendment 2026-05-17 — formerly inherited from adjacent-session metadata; now re-run as part of T1 cascade)** + 2A + 2D + 1 + `request` + `parsed_intent`. `prior_plan_session_window` rendered hybrid per D4. Layer 2B/2C/2E only present when `parsed_intent` triggered their re-run; full when present. | ~3500–4500 input token budget fits without trimming. T1 default cascade as of v2 includes 3A + 3B re-run; 3B is small (~200-300 tokens) and unblocks the validator's intensity-distribution + volume-band checks without depending on `prior_plan_session_window[*].phase_metadata` (which is None on Pattern-B-only prior plans). |
| D4 | `prior_plan_session_window` rendering | **Hybrid: ±7-day window split — refresh-window-prior (the 7 days BEFORE the refresh window) as summary table (date / sport / kind / duration / intensity / completion); refresh-window-after (the 7 days AFTER, planned but not refreshed) verbatim with all fields.** | Refresh-window-prior is "what just happened" (drives recency/recovery reasoning); summary fields capture the load shape. Refresh-window-after is the continuity constraint per Pick 3 — the synthesizer must produce T1 sessions that land cleanly into these. Verbatim rendering preserves the full session shape the synthesizer needs to match against. |
| D5 | `parsed_intent` weighting policy | **Strong-bias toward intent** (Andy 2026-05-17 Pick 2). When `parsed_intent` is non-None, its soft signals (`fatigue_signal`, `sickness_signal`, `motivation_signal`) dominate 3A objective signals. Athlete-said-tired → system goes easier even if 3A's `acwr_7_28` looks fine. `raw_text` is passed through and weighted as additional context. | Athlete-explicit framing of D-64 (`Plan_Refresh_D64_Design_v1.md` §2 Decision 2) — athlete owns the decision to refresh, including the direction. 3A signals override only on hard-safety (injury exclusion, blocker validator). The `intensity_modulated` flag (per spec amendment §8.6 this session) fires whenever the synthesizer's prescription deviates from what 3B periodization shape + adjacent-session context would naturally call for, due to intent. |
| D6 | Coaching flag enum | **Full per-phase + cross-phase LLM-emittable set** (Layer 4 §§8.2–8.6 LLM-emitted entries only — spec-auto flags are orchestrator-side): `technique_emphasis`, `long_slow_distance`, `weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `race_pace_specific`, `intensity_modulated`. | T1 is phase-aware (reads 3B even on Pattern B per §4.3); full phase-tied flag set applies. `intensity_modulated` trigger broadened this session to cover refresh-path modulation against athlete intent (paired spec amendment §8.6). |
| D7 | Continuity-with-adjacent-sessions policy | **Match surrounding training shape unless refresh trigger justifies a shift** (Andy 2026-05-17 Pick 3). Volume curve + intensity placement consistent with refresh-window-after sessions; only shift when 3A or `parsed_intent` gives an explicit signal. Refresh is minimally disruptive by default. | T1's 2-day scope makes shape preservation natural; the refresh window is too short to materially shift periodization. The refresh-window-after sessions are the load-bearing constraint — the synthesizer must produce T1 sessions that hand off cleanly to them. |
| D8 | `RuleFailure` retry context rendering | **Hybrid:** `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. | Mirrors seam-reviewer / per-phase / single-session D8 framing. Constraint statements clearly attribute "Observed: X / Constraint: Y" so the synthesizer's repair pass is targeted. |
| D9 | Schema-enforced length caps | **Tight: 240 chars `session_notes` / 200 chars `coaching_intent` / 120 chars `load_prescription` / 240 chars `instructions`.** | Matches single-session caps exactly. `max_tokens=2000` budget (slightly higher than single-session's 1500 to absorb up to 4 sessions worth of structured output). |
| D10 | NL `raw_text` passthrough | **Always rendered in §6 user prompt under explicit "athlete's words" framing.** Even when `parser_confidence='low'` per `Plan_Refresh_D64_Design_v1.md` §5.4 degraded path. The synthesizer should treat `raw_text` as primary signal when present; the structured `parsed_intent` flags are scaffolding for the synthesizer's reading, not a replacement for it. | Strong-bias-toward-intent (D5) means the athlete's actual words drive the synthesis. Structured signals are useful for the validator + downstream consumers; the prompt itself reads the prose. |
| D11 | File location | `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` per the `prompts/` subdir convention (`Layer4_SeamReviewer_v1.md` D7). | Inherits. |

**Companion contract sections (`Layer4_Spec.md`):** §3.2 (call signature), §4.3 (input validation — refresh preconditions), §5.1 (pattern routing — T1 → B), §5.3 (Pattern B algorithm), §5.4 (deterministic validator — full scope on refresh including continuity cross-validation), §5.5 (capped retry semantics), §7.2/§7.3/§7.4 (`PlanSession` discriminated union + `CardioBlock` + `StrengthExercise`), §7.5 (`SessionPhaseMetadata` — None on Pattern B refresh), §8.6 (`intensity_modulated` cross-phase flag — trigger broadened this session to cover refresh-path modulation), §8.7 (call-level observations — `intensity_modulated` orchestrator-side bubble from the LLM-emitted session flag), §11.1 / §11.2 / §11.3 (latency / token / cost — ~5s / ~4500 input + ~1500 output / ~$0.05 typical).

**Paired spec amendment this session:** `Layer4_Spec.md` §8.6 `intensity_modulated` trigger row broadened from D-63-only to also cover `plan_refresh` paths (T1/T2 strong-bias-toward-intent emits this flag when modulating against periodization-shape-natural intensity). §8.7 spec-auto observation trigger is unchanged in wording (still "LLM-emitted session flag per §8.6") but its scope follows §8.6.

---

## 1. Purpose + scope

### 1.1 What this prompt produces

A short list of `PlanSession` records (0 to ~4 entries) covering `[refresh_scope_start, refresh_scope_end]` — typically 2 calendar days. Each session is athlete-facing and immediately renderable: structured cardio blocks (warmup / main_set / cooldown / interval_set / transition) for cardio sports, or strength exercises with sets / reps / load prescription / form cues for strength sports. The sessions emit `is_ad_hoc=False`, `plan_version_id=<new T1 version id>`, and `phase_metadata=None` (Pattern B refreshes don't decompose phase shape; see §7.12 spec rule).

The synthesizer reads the prior plan's sessions for the refresh window (now superseded), the surrounding ±7 days of plan context, and the athlete's `parsed_intent` / `raw_text` from D-64. It produces sessions that honor the refresh trigger while landing cleanly into the still-planned sessions after the refresh window.

### 1.2 What this prompt does NOT produce

- **Phase decomposition.** T1 reads the periodization shape from the freshly-re-run 3B payload (per §4.3-wins amendment 2026-05-17 — 3B is now in the T1 default cascade); no `PhaseStructure` / `SeamReview` / per-phase decomposition. The synthesizer reads "what phase are we currently in?" from `layer3b_payload.periodization_shape` directly, no longer from adjacent-session `phase_metadata`.
- **Periodization re-shape.** T1 is too short a horizon to justify shifting the periodization. Volume bands + intensity distribution targets remain those of the inherited phase.
- **Sessions outside the refresh window.** The prompt produces sessions for `[refresh_scope_start, refresh_scope_end]` only. Refresh-window-after sessions stay pointed at their prior `plan_version_id`; the synthesizer reads them as constraint but does not modify them.
- **Multi-week or cross-phase commitment.** Notes like "you should taper from here" or "extend Base by 2 weeks" are out of scope — that's T3 territory.
- **NL intent re-classification.** The `parsed_intent` is consumed verbatim; the prompt does not re-parse the NL text into structured signals. (`raw_text` is rendered for the synthesizer's reading, but the structured signals come from D-64's intent parser.)
- **Observations or opportunities** other than the LLM-emitted `category='opportunity'` exception per §8.7. The `intensity_modulated` observation is orchestrator-computed from the LLM-emitted session flag.

### 1.3 Failure modes this prompt + retry semantics catch

- Athlete signals fatigue (`parsed_intent.fatigue_signal='wiped'`) but the synthesizer prescribes a hard session anyway → validator catches if it pushes ACWR over threshold; otherwise observation-only via `intensity_modulated` flag absence.
- Athlete reports a new injury via `raw_text` → if `parsed_intent.triggers_2d_injury=True` the cascade already re-ran 2D before this prompt fired; this prompt reads the updated `active_injuries`. If the NL parser missed the injury signal (`raw_text` says "tweaked knee" but `triggers_2d_injury=False`), the prompt's §9 guidance instructs the synthesizer to honor the explicit prose signal anyway — emit no exercises hitting the named body part — and surface in `session_notes`.
- Synthesizer prescribes a session that breaks continuity with the refresh-window-after sessions (e.g., athlete had a planned long ride on day 3 of refresh-window-after; synthesizer prescribes a high-intensity bike day on day 2 of refresh that would compromise the long ride) → validator `rest_spacing_blocker` or `acwr_warning` triggers capped retry with constraint added.
- Synthesizer prescribes a strength exercise hitting a known injury → validator `injury_violation_blocker` triggers capped retry.

---

## 2. Pipeline placement

**Call site:** `llm_layer4_plan_refresh(user_id, tier='T1', ...)` per `Layer4_Spec.md` §3.2. Invoked by the D-64 orchestrator after:

1. Cascade execution per `Plan_Refresh_D64_Design_v1.md` §6.1 — 3A re-run (always); optional 2A/2B/2C/2D/2E re-runs added by `parsed_intent` triggers.
2. Input validation per `Layer4_Spec.md` §4.3 — including `tier ∈ enum`, `refresh_scope_*` ordered, `tier_scope_mismatch` (T1 scope ≤ 3 days), `plan_version_id_parent` exists.

**Pattern:** B per `Layer4_Spec.md` §5.3 step 1 sub-bullet (T1):

> `plan_refresh` T1: 3A + 2A/2D + 1 + `prior_plan_session_window` + `parsed_intent` (when present).

- Step 1: build context (this prompt's §3 inputs).
- Step 2: single LLM call (this prompt's §5 system + §6 user + §7 sampling config).
- Step 3: parse `record_refresh_sessions` tool output as `list[PlanSession]`.
- Step 4: deterministic validator (`Layer4_Spec.md` §5.4) — full rule set, scoped over `[refresh_scope_start, refresh_scope_end]` plus adjacent-day continuity checks against `prior_plan_session_window`.
- Step 5: capped retry per `Layer4_Spec.md` §5.5 on validator failure; cap=2 (default).
- Step 6: compose `Layer4Payload` with `mode='plan_refresh'`, `pattern='B'`, `phase_structure=None`, `seam_reviews=None`, sessions covering the refresh window, `plan_version_id` set to the new T1 version id.

**Out-of-pipeline cases:**
- Cascade pre-LLM failure (e.g., 2D re-run raised a blocker HITL item) → no LLM call; D-64 returns "Refresh failed: open HITL item" per `Plan_Refresh_D64_Design_v1.md` §6.2 atomicity.
- Validator pre-LLM failure (`Layer4_Spec.md` §4.3) → raises `Layer4InputError(code)`; no LLM call.
- `parser_confidence='low'` per `Plan_Refresh_D64_Design_v1.md` §5.4 degraded path → LLM call proceeds with `parsed_intent` flags all FALSE, `raw_text` still rendered. Refresh proceeds with default cascade.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following variables. All are required unless marked optional. Token-budget realism per `Layer4_Spec.md` §11.2: ~4500 input tokens total worst case.

### 3.1 Refresh request

| Variable | Source | Notes |
|---|---|---|
| `refresh.tier` | D-64 caller | `'T1'`. Used in §6 framing only; sampling config is tier-specialized. |
| `refresh.scope_start` | D-64 caller | Typically today; can be tomorrow if today's session is already completed per `Plan_Refresh_D64_Design_v1.md` §3.1. |
| `refresh.scope_end` | D-64 caller | `scope_start + 1 day` (2-day rolling window; both calendar days inclusive). Validated per `Layer4_Spec.md` §4.3 (`tier_scope_mismatch` if length > 3 days for T1). |
| `refresh.triggered_at` | D-64 caller | Timestamp. Used in §6 framing for recency reasoning (e.g., "the athlete reported tired 90 minutes ago"). |

### 3.2 NL context + parsed intent

| Variable | Source | Notes |
|---|---|---|
| `parsed_intent.raw_text` | D-64 NL parser | Athlete's free-text input. Always rendered in §6 (D10). Empty string when athlete refreshed without NL context. |
| `parsed_intent.fatigue_signal` | D-64 parser | `'fresh' \| 'normal' \| 'tired' \| 'wiped'`. Default `'normal'`. |
| `parsed_intent.sickness_signal` | D-64 parser | `'none' \| 'recovering' \| 'active'`. Default `'none'`. Critical safety signal — when `'active'`, the synthesizer must prescribe rest-shape sessions (zero hard work) regardless of other signals. |
| `parsed_intent.motivation_signal` | D-64 parser | `'low' \| 'normal' \| 'high'`. Default `'normal'`. |
| `parsed_intent.triggers_2a_discipline` | D-64 parser | When TRUE, 2A re-ran upstream; `layer2a_payload` reflects the new state. The prompt does not re-trigger; it consumes. |
| `parsed_intent.triggers_2b_terrain` | D-64 parser | When TRUE, `layer2b_payload` reflects re-run output. T1 default cascade does NOT include 2B/2C/2E — they only appear when intent-triggered. |
| `parsed_intent.triggers_2c_equipment` | D-64 parser | List of locale slugs needing 2C re-run; the relevant `layer2c_payload_per_locale[slug]` reflects post-re-run state. |
| `parsed_intent.triggers_2d_injury` | D-64 parser | When TRUE, 2D re-ran; `layer2d_payload` + `athlete_state.active_injuries` reflect the new state. |
| `parsed_intent.triggers_2e_nutrition` | D-64 parser | When TRUE, `layer2e_payload` reflects re-run output. |
| `parsed_intent.parser_confidence` | D-64 parser | `'high' \| 'medium' \| 'low'`. When `'low'`, all flags should be treated as low-confidence; raw_text is primary. |
| `parsed_intent.ambiguity_notes` | D-64 parser | Optional free-text — when parser couldn't classify cleanly, what was ambiguous. Surfaced to the synthesizer for context. |

### 3.3 Athlete + locale context

| Variable | Source | Notes |
|---|---|---|
| `athlete.user_id` | Layer 1 | Identification only; never used for coaching judgment. |
| `athlete.coaching_voice_preferences` | Layer 1 (when present) | Tone shading (e.g., "athlete prefers minimal mid-workout cueing"). |
| `athlete.experience_level` | Layer 1 | Beginner / intermediate / advanced / elite — drives technical complexity ceiling for exercise selection + form cue depth. |
| `athlete.discipline_inclusion` | Layer 2A | List of sports the athlete competes in / trains for. Used to flag `discipline_specific_intensity` when refresh-window sessions hit race-relevant disciplines. |
| `athlete.active_injuries` | Layer 2D | Injury exclusions — hard constraints. Always respected; never overridable by `parsed_intent` or `raw_text` direction. |
| `athlete.locales` | Layer 2C | List of athlete's locales with effective equipment views (curated equipment list with Tier 1/2/3 substitution map per locale). Source of truth for equipment availability on each refresh-window day. |
| `athlete.default_locale_for_date_window` | Orchestrator-supplied | Pre-computed locale-per-date for the refresh window (driven by §K availability + athlete's most-recent locale signal). The synthesizer uses this as the equipment-resolution context per day. |

### 3.4 Athlete state — drives modulation reasoning

| Variable | Source | Notes |
|---|---|---|
| `athlete_state.acwr_7_28` | Layer 3A | Acute-chronic workload ratio. Anchor signal #1 for ACWR-based modulation per §9. |
| `athlete_state.seven_day_load` | Layer 3A | Total training load (TSS-equivalent or sport-specific) across the last 7 days. |
| `athlete_state.last_hard_session_date` | Layer 3A | Date of the most recent hard-intensity session (any sport). Anchor signal #2. |
| `athlete_state.last_hard_session_sport` | Layer 3A | Sport of last hard session. |
| `athlete_state.fatigue_markers` | Layer 3A (when present) | Subjective ratings (HRV trend, sleep score, RPE history). Drives modulation only when `parsed_intent` doesn't already signal fatigue (strong-bias-toward-intent — athlete-reported signal dominates). |
| `athlete_state.data_density` | Layer 3A | `'rich' \| 'normal' \| 'sparse' \| 'very_sparse'`. Drives ramp-rate conservatism when sparse. |
| `athlete_state.aerobic_state` | Layer 3A | `'low' \| 'normal' \| 'high' \| 'very_high'`. Reads the athlete's current aerobic conditioning. |

### 3.5 Periodization shape — read from freshly-re-run 3B (v2 amendment)

**Amended 2026-05-17 (v2; §4.3-wins ripple).** Prior wording cited `prior_plan_session_window[*].phase_metadata` as the periodization-shape source on the basis that T1 didn't re-run 3B. That framing is retired — `Layer4_Spec.md` §3.2 now requires `layer3b_payload` non-None on every tier, so T1 reads the periodization shape from the freshly-re-run 3B payload directly.

| Variable | Source | Notes |
|---|---|---|
| `current_phase.name` | `layer3b_payload.periodization_shape.start_phase` | Current phase from freshly-re-run 3B. v2 amendment retired the prior `phase_metadata`-inheritance path. |
| `current_phase.intended_volume_band` | Layer 4 §6.1 + 2A `phase_load_bands` | Phase-resolved volume band the current phase targets. The synthesizer aims T1 output volume to land inside the band when continuity is maintained. |
| `current_phase.intended_intensity_distribution` | Layer 4 §5.4 v1 defaults | Per-phase target distribution (Base ≈ 80/15/5; Build ≈ 70/20/10; Peak ≈ 70/20/10; Taper ≈ 75/15/10). T1 output's intensity placement reads against the phase's distribution but is not strictly enforced over a 2-day window (the validator's `intensity_dist_*` rule applies per-phase, not per-2-day-slice). |
| `current_phase.days_to_event` | `layer3b_payload.time_to_event_weeks` × 7 (when present) | Optional. When present + ≤ 14, the synthesizer should default to Taper-shape sessions per §8.5 even though Taper flags are spec-auto. |

### 3.6 Prior plan session window (drives continuity)

| Variable | Source | Notes |
|---|---|---|
| `prior_plan.refresh_window_prior` | `prior_plan_session_window` filtered to `[scope_start - 7d, scope_start - 1d]` | Last 7 days of training — summary table per D4 (date / sport / kind / duration / intensity / completion status). The recency-anchor that drives recovery reasoning. |
| `prior_plan.refresh_window_during_prior` | `prior_plan_session_window` filtered to `[scope_start, scope_end]` | The prior-plan sessions the refresh is replacing. Rendered verbatim (small set, max ~4) for the synthesizer's reading — "this is what was planned; the athlete is asking for a different shape." |
| `prior_plan.refresh_window_after` | `prior_plan_session_window` filtered to `[scope_end + 1d, scope_end + 7d]` | Next 7 days, still planned, not refreshed. Rendered verbatim per D4 — the continuity constraint. |

### 3.7 Retry context (only present on retry pass)

| Variable | Source | Notes |
|---|---|---|
| `retries_used` | Orchestrator | 0 on first pass; 1 or 2 on retry. Cap = 2 per `Layer4_Spec.md` §5.5. |
| `rule_failures` | Validator | List of `RuleFailure` records from the prior pass. Each: `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. Renders in §6 as constraint statements per D8. |

### 3.8 Intentionally NOT passed

- `layer2b_payload` / `layer2c_payload` / `layer2e_payload` — only present when `parsed_intent` triggered their re-run; otherwise None.
- `phase_structure` — Pattern B has no phase decomposition.
- `seam_issues` / `seam_direction` — Pattern B has no seam reviewer.
- `event_date` / `race_format` — surfaced indirectly via `current_phase.days_to_event` when relevant; race-week specifics are handled by `Layer4_RaceWeekBrief` (queued, last of 5 prompt bodies).

---

## 4. Output schema + tool definition

The synthesizer emits exactly one tool call to `record_refresh_sessions`. The tool accepts a `sessions` argument matching `list[PlanSession]` per `Layer4_Spec.md` §7.2 (minus orchestrator-filled metadata: `session_id`, `plan_version_id`, `is_ad_hoc`, `phase_metadata`).

### 4.1 Tool schema (strict JSON-schema, `additionalProperties: false` at every nesting level)

```json
{
  "name": "record_refresh_sessions",
  "description": "Record the synthesized sessions for the T1 refresh window. Output is a list of 0-4 PlanSession objects covering [refresh_scope_start, refresh_scope_end]. Empty list is allowed when the refresh window is entirely rest by athlete schedule + coaching choice.",
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["sessions"],
    "properties": {
      "sessions": {
        "type": "array",
        "minItems": 0,
        "maxItems": 4,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["date", "sport", "kind", "duration_min", "intensity", "coaching_intent", "session_notes", "coaching_flags"],
          "properties": {
            "date": {"type": "string", "format": "date"},
            "sport": {"type": "string"},
            "kind": {"type": "string", "enum": ["cardio", "strength"]},
            "duration_min": {"type": "integer", "minimum": 30, "maximum": 360},
            "intensity": {"type": "string", "enum": ["easy", "moderate", "hard"]},
            "coaching_intent": {"type": "string", "maxLength": 200},
            "session_notes": {"type": "string", "maxLength": 240},
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
                  "race_pace_specific",
                  "intensity_modulated"
                ]
              },
              "maxItems": 7,
              "uniqueItems": true
            },
            "locale_id": {"type": "string"},
            "cardio_blocks": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["block_kind", "duration_min"],
                "properties": {
                  "block_kind": {"type": "string", "enum": ["warmup", "main_set", "cooldown", "interval_set", "transition"]},
                  "duration_min": {"type": "integer", "minimum": 1, "maximum": 300},
                  "instructions": {"type": "string", "maxLength": 240},
                  "interval_reps": {"type": "integer", "minimum": 1, "maximum": 50},
                  "interval_work_min": {"type": "number", "minimum": 0.25, "maximum": 60},
                  "interval_recovery_min": {"type": "number", "minimum": 0.25, "maximum": 60}
                }
              }
            },
            "strength_exercises": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["exercise_id", "sets", "reps", "load_prescription"],
                "properties": {
                  "exercise_id": {"type": "string"},
                  "resolution_tier": {"type": "integer", "enum": [1, 2, 3]},
                  "substitute_text": {"type": "string", "maxLength": 240},
                  "proxy_origin_id": {"type": "string"},
                  "sets": {"type": "integer", "minimum": 1, "maximum": 10},
                  "reps": {"type": "string", "maxLength": 40},
                  "load_prescription": {"type": "string", "maxLength": 120},
                  "instructions": {"type": "string", "maxLength": 240},
                  "coaching_flags": {
                    "type": "array",
                    "items": {
                      "type": "string",
                      "enum": ["technique_emphasis", "weak_link_targeted"]
                    },
                    "maxItems": 2,
                    "uniqueItems": true
                  }
                }
              }
            },
            "rationale": {"type": "string", "maxLength": 240}
          }
        }
      },
      "notable_observations": {
        "type": "array",
        "maxItems": 2,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["category", "text"],
          "properties": {
            "category": {"type": "string", "enum": ["opportunity"]},
            "text": {"type": "string", "maxLength": 240}
          }
        }
      }
    }
  }
}
```

### 4.2 Output invariants the prompt must honor

- `len(sessions)` in `[0, 4]`. Most T1 refreshes produce 1–3 sessions. Empty list is rare but legitimate when athlete's schedule has both days at `available=False` AND no athlete override per §K.
- Each session's `date` falls inside `[refresh_scope_start, refresh_scope_end]` (inclusive both ends).
- Per-date max 2 sessions, with constraint per `Layer4_Spec.md` §7.12: no strength+strength same day; no two `intensity='hard'` same day; at least one of two must be `kind='cardio'`.
- `kind='cardio'` requires `cardio_blocks` non-empty + `strength_exercises` absent or empty.
- `kind='strength'` requires `strength_exercises` non-empty + `cardio_blocks` absent or empty.
- `coaching_flags` is a closed set per D6. Unknown flags raise `unknown_coaching_flag_<name>` (`blocker`) per `Layer4_Spec.md` §8.1 — treated as schema-violation per §5.5.
- `intensity_modulated` MUST be emitted on every session where the synthesizer's prescription deviates from what 3B periodization shape + adjacent-session continuity would naturally call for, due to `parsed_intent` or 3A signal direction. `session_notes` MUST briefly explain the modulation reasoning when this flag fires.
- `notable_observations[].category` is restricted to `'opportunity'` (the single LLM-emitted observation exception per `Layer4_Spec.md` §8.7). All other observation categories are orchestrator-computed.

---

## 5. System prompt

```
You are AIDSTATION's Layer 4 plan-refresh T1 synthesizer.

You are called when an athlete clicks "Refresh next 2 days" on their training plan. The athlete has typed an optional free-text note explaining why they want the refresh. Your job is to produce 0-4 PlanSession records covering the next 2 calendar days that:

1. Honor the athlete's stated intent (their words are the primary signal — see §9).
2. Hand off cleanly into the sessions already planned for days 3-7 after the refresh window.
3. Stay inside the inherited periodization phase's intent (volume band + intensity distribution) unless the athlete's intent justifies stepping outside.
4. Never violate hard constraints — active injuries, equipment availability, schedule availability.

VOICE: Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Match a real endurance coach talking to a serious athlete.

PROCESS:
- Read the athlete's `raw_text` and `parsed_intent` first. These drive WHY you're modulating.
- Read the recent training context (last 7 days summary + 3A state) to ground the modulation in objective signal where possible.
- Read the refresh-window-after sessions (the sessions planned for days 3-7) — these are the continuity constraint. Your output must hand off cleanly to them.
- Decide the shape of the refresh window (1 session per day / 2 per day / rest / mix). Honor the athlete's §K availability per the orchestrator's locale assignment per day.
- For each session, prescribe sport / duration / intensity + the structured content (cardio_blocks for cardio; strength_exercises for strength).
- Emit `intensity_modulated` whenever your prescription deviates from what the inherited phase + adjacent sessions would naturally call for, due to the athlete's intent or a 3A signal. Briefly explain the modulation in `session_notes`.

You emit exactly one tool call: `record_refresh_sessions`. The tool's `sessions` argument is your list of 0-4 PlanSession records. Optionally include `notable_observations` with up to 2 `opportunity` entries for coaching observations not tied to a rule.

Do not return any text outside the tool call.
```

---

## 6. User prompt (template — Mustache variables)

```
=== Refresh request ===
Tier: T1 (2-day rolling window)
Scope: {{ refresh.scope_start }} through {{ refresh.scope_end }}
Triggered at: {{ refresh.triggered_at }}

=== Athlete's words ===
{{#parsed_intent.raw_text}}
Athlete typed: "{{ parsed_intent.raw_text }}"
{{/parsed_intent.raw_text}}
{{^parsed_intent.raw_text}}
(Athlete refreshed without typing a note.)
{{/parsed_intent.raw_text}}

Parsed intent signals (from NL parser; confidence: {{ parsed_intent.parser_confidence }}):
- Fatigue: {{ parsed_intent.fatigue_signal }}
- Sickness: {{ parsed_intent.sickness_signal }}
- Motivation: {{ parsed_intent.motivation_signal }}
- Injury mentioned: {{ parsed_intent.triggers_2d_injury }}
- New discipline mentioned: {{ parsed_intent.triggers_2a_discipline }}
- Equipment / locale mentioned: {{ parsed_intent.triggers_2c_equipment }}
{{#parsed_intent.ambiguity_notes}}
Parser noted ambiguity: {{ parsed_intent.ambiguity_notes }}
{{/parsed_intent.ambiguity_notes}}

POLICY: The athlete's words and the parsed signals dominate the prescription direction. 3A objective signals (ACWR, recent load, last-hard-session) ground the magnitude but do not override the direction. Hard safety constraints (active injuries, equipment availability, schedule availability) are never overridden. When your prescription deviates from what the inherited phase + adjacent sessions would naturally call for due to intent, emit `intensity_modulated` on the affected sessions and briefly explain in `session_notes`.

=== Athlete profile ===
Experience level: {{ athlete.experience_level }}
Disciplines: {{ athlete.discipline_inclusion }}
Active injuries (hard constraints — never overridable):
{{#athlete.active_injuries}}
- {{ injury_site }} / {{ injury_type }}: {{ restriction_text }}
{{/athlete.active_injuries}}
{{^athlete.active_injuries}}
(No active injuries.)
{{/athlete.active_injuries}}
{{#athlete.coaching_voice_preferences}}
Voice notes: {{ athlete.coaching_voice_preferences }}
{{/athlete.coaching_voice_preferences}}

=== Inherited periodization phase ===
Phase: {{ current_phase.name }}
Intended volume band: {{ current_phase.intended_volume_band }}
Intended intensity distribution (Z1-Z2 / Z3 / Z4-Z5): {{ current_phase.intended_intensity_distribution }}
{{#current_phase.days_to_event}}
Days to event: {{ current_phase.days_to_event }}
{{/current_phase.days_to_event}}

Note: T1 does NOT re-run 3B. The periodization shape is read from the adjacent-session metadata. Stay inside the inherited phase's intent unless athlete intent justifies stepping outside (e.g., athlete reports active sickness → mandatory rest-shape regardless of phase).

=== Locale + equipment per refresh-window day ===
{{#refresh_window_days}}
- {{ date }}: locale `{{ locale_id }}` ({{ locale_label }}); equipment view: {{ effective_equipment_view_summary }}
{{/refresh_window_days}}

=== Athlete state (3A — just re-run as part of the refresh cascade) ===
ACWR (7d / 28d): {{ athlete_state.acwr_7_28 }}
Seven-day load: {{ athlete_state.seven_day_load }}
Last hard session: {{ athlete_state.last_hard_session_date }} ({{ athlete_state.last_hard_session_sport }})
Data density: {{ athlete_state.data_density }}
Aerobic state: {{ athlete_state.aerobic_state }}
{{#athlete_state.fatigue_markers}}
Fatigue markers: {{ athlete_state.fatigue_markers }}
{{/athlete_state.fatigue_markers}}

=== Recent training (last 7 days — summary) ===
| Date | Sport | Kind | Duration | Intensity | Completed |
|---|---|---|---|---|---|
{{#prior_plan.refresh_window_prior}}
| {{ date }} | {{ sport }} | {{ kind }} | {{ duration_min }}min | {{ intensity }} | {{ completion_status }} |
{{/prior_plan.refresh_window_prior}}

=== Sessions previously planned for the refresh window (being replaced) ===
{{#prior_plan.refresh_window_during_prior}}
- {{ date }} ({{ sport }} / {{ kind }} / {{ duration_min }}min / {{ intensity }}): {{ coaching_intent }}
{{/prior_plan.refresh_window_during_prior}}

=== Sessions planned for days 3-9 (continuity constraint — NOT being modified by this refresh) ===
{{#prior_plan.refresh_window_after}}
- {{ date }} ({{ sport }} / {{ kind }} / {{ duration_min }}min / {{ intensity }}): {{ coaching_intent }}{{#coaching_flags}} [{{ . }}]{{/coaching_flags}}
{{/prior_plan.refresh_window_after}}

Your T1 output must hand off cleanly into these. If any of the planned post-window sessions is a key workout (long ride, race-pace day, weak-link strength), the refresh must not compromise it (e.g., don't prescribe a hard intensity day 2 of refresh that would torch the legs for a planned long day 3 of refresh-window-after).

{{#retries_used}}
=== Retry context (pass {{ retries_used }} of cap=2) ===
Prior pass failed deterministic validator with these rule failures:
{{#rule_failures}}
- [{{ severity }}] `{{ rule_name }}` on session(s) {{ affected_session_ids }}: {{ detail }}
  Constraint to honor on this pass: {{ suggested_constraint }}
{{/rule_failures}}

Repair pass: address each constraint above while keeping the rest of the prescription intact. Do not regenerate from scratch.
{{/retries_used}}

=== Output ===
Emit one tool call to `record_refresh_sessions` with your list of 0-4 PlanSession records. Optionally include `notable_observations` with up to 2 `opportunity` entries.
```

---

## 7. Sampling configuration

| Parameter | Value | Rationale |
|---|---|---|
| `model` | `claude-sonnet-4-6` (default) | Per `Layer4_Spec.md` §3.2 framing. Opus optional for cost-sensitive accounts. |
| `temperature` | 0.4 | Coaching variation acceptable; not deterministic. Lower than per-phase (0.5) because T1's smaller surface area benefits from tighter sampling. |
| `max_tokens` | 2000 | Up to 4 sessions × ~400 tokens each = ~1600 + buffer. |
| `extended_thinking` | enabled, budget=3000 tokens | Per D2. Calibrates between single-session's 3500 and per-phase's 5000. |
| `tool_choice` | `{"type": "tool", "name": "record_refresh_sessions"}` | Forces the tool call; no free-text leakage. |
| `tools` | `[record_refresh_sessions]` | Per §4.1 schema. |
| Schema retry on parse failure | 1 attempt (separate from §5.5 capped retry per `Layer4_Spec.md` §5.5 schema-violation special case) | One retry on malformed JSON; bail with `Layer4OutputError('schema_violation')` on second failure. |

---

## 8. Coaching flag emission rules

The synthesizer emits per-session `coaching_flags` from the closed set per D6. Triggers per `Layer4_Spec.md` §§8.2–8.6 LLM-emitted entries (reproduced here for self-containment; spec is authoritative):

| Flag | Phase | Trigger |
|---|---|---|
| `technique_emphasis` | Any (skill-relevant disciplines) | Session contains drill/skill work for a 3A `weak_links` entry of skill type (bike-handling, swim technique, climbing technique, etc.). |
| `long_slow_distance` | Base (primarily); also valid in Build for cornerstone aerobic sessions | Session is the canonical weekly long-duration aerobic session for a discipline. |
| `weak_link_targeted` | Any (typically Build) | Strength session contains accessory work targeting a 3A `weak_links` entry. |
| `overreach_test` | Build (typically last week before deload) | Session is part of an intentional brief overreach. Rare on T1 — overreach weeks are planned at higher tiers; T1 doesn't introduce them. |
| `discipline_specific_intensity` | Build / Peak | First time in the plan a race-discipline-specific intensity prescription appears. Rare on T1 unless `parsed_intent` triggers a discipline shift. |
| `race_pace_specific` | Peak (primarily) | Cardio session at exact race-target pace/power. |
| `intensity_modulated` | Cross-phase | Synthesizer modulated this session's intensity from what 3B periodization shape + adjacent-session continuity would naturally call for, due to `parsed_intent` direction or 3A signal. **Per spec amendment §8.6 this session — broadened from D-63-only to also cover plan_refresh paths.** |

**Spec-auto-emitted flags are NOT the prompt's responsibility.** The orchestrator computes and merges them post-synthesis: `first_introduction_to_<discipline>`, `aerobic_base_focus`, `volume_ramp_conservative`, `volume_ramp_aggressive`, `recovery_day_after_long`, `tune_up_race`, `peak_volume_marker`, all Taper-phase flags per §8.5, `race_day`, `recovery_week`. If the synthesizer redundantly emits one of these as an LLM flag, the orchestrator's merge is idempotent (set-union).

**`intensity_modulated` is mandatory when applicable.** Do not silently modulate. If you emit a session whose intensity differs from the natural phase-shape + continuity reading, the flag fires and `session_notes` explains why.

---

## 9. Coaching guidance

### 9.1 Strong-bias-toward-intent — what it means in practice

The athlete's `raw_text` and `parsed_intent` dominate the direction of modulation. 3A signals (ACWR, recent load, last-hard-session, fatigue markers) ground the *magnitude* but not the direction.

Examples:

| Athlete says (`raw_text`) | Parsed | 3A | Prescription |
|---|---|---|---|
| "I'm tired" | fatigue=`tired` | ACWR 1.15 (normal-high) | Reduce intensity / volume vs. prior plan; `intensity_modulated` fires. Magnitude tuned by ACWR — already elevated, so go further than just "down a notch." |
| "I'm tired" | fatigue=`tired` | ACWR 0.9 (normal-low) | Reduce intensity / volume modestly; `intensity_modulated` fires. ACWR is fine, but athlete-reported fatigue is signal. |
| "I feel great" | motivation=`high` | ACWR 1.3 (elevated, near blocker) | Honor the energy with quality but cap the volume; ACWR override prevents pushing into blocker territory. `intensity_modulated` fires for the cap. `session_notes` explains: "Honored your energy on intensity; capped weekly volume given recent ramp." |
| "Travel Wed-Fri" | (locales triggered 2C re-run; `parsed_intent.triggers_2c_equipment=[travel_locale]`) | (normal) | Use the travel locale's equipment view for refresh-window days that fall in travel; substitute exercises per Tier 1/2/3. Not an `intensity_modulated` case — same coaching intent, different equipment. |
| "I tweaked my knee" | injury=True (2D re-ran; `active_injuries` updated) | (normal) | Read `active_injuries` for the new constraint; prescribe sessions that respect it. Knee-loaded exercises substituted via Tier 2/3 or replaced. Not necessarily `intensity_modulated` — different exercises, possibly same intensity. |
| (empty `raw_text`) | (all defaults) | ACWR 1.4 (elevated, blocker-edge) | No athlete signal → 3A drives. Modulate intensity down to bring ACWR back inside the warning band. `intensity_modulated` fires (3A is the modulation cause). `session_notes`: "Easing intensity — your recent load has ramped fast; this week aims to stabilize before pushing again." |

### 9.2 Sickness is a hard constraint

When `parsed_intent.sickness_signal == 'active'`: prescribe rest-shape sessions only (zero hard intensity; light walks or mobility max). This is the one signal that overrides "minimally disruptive continuity" — the refresh-window-after sessions are read as context but not as constraint to match.

When `parsed_intent.sickness_signal == 'recovering'`: tread carefully. Easy aerobic only; no hard work; emit `intensity_modulated` on every session.

### 9.3 Continuity hand-off

The refresh-window-after sessions are the continuity constraint per Pick 3. Concretely:

- If day 3 of refresh-window-after is a planned **hard** session (e.g., long ride / interval workout / race-pace work) → day 2 of refresh (the last day of the refresh window) must allow recovery before day 3. Don't prescribe hard intensity on day 2 unless athlete explicitly signals otherwise AND 3A supports it.
- If day 3 of refresh-window-after is a planned **rest** day → day 2 of refresh can absorb harder work if athlete signals (`motivation=high`, `fatigue=fresh`); recovery is already built in downstream.
- If the refresh-window-after pattern is a deload week (sessions are short/easy across the week) → the refresh window is the trailing edge of a hard block; reasonable to allow harder work on refresh days even if athlete reports tired (they're tired *because* of the hard block, and deload starts day 3 of refresh-window-after).

Read the patterns; don't apply rules mechanically.

### 9.4 Volume band + intensity distribution — soft constraints on T1

T1's 2-day window is too short for the validator's `volume_band_*` and `intensity_dist_*` rules to be tightly meaningful (those rules apply per-week). But the inherited phase's intent should guide your prescription:

- If the inherited phase is **Base**: aerobic-dominant; long-duration low-intensity sessions are the cornerstone (`long_slow_distance` flag on the long session if one falls in the refresh window).
- If the inherited phase is **Build**: harder intensity; volume holds; race-discipline-specific work may appear (`discipline_specific_intensity` flag on the first such session).
- If the inherited phase is **Peak**: highest volume retained; race-pace work appears (`race_pace_specific` flag).
- If the inherited phase is **Taper**: volume drops; intensity preserved or slightly elevated; recovery emphasized. T1 in Taper is typically a "make tomorrow easier so race-week prep stays clean" use case.

The validator's `volume_band_warning` / `volume_band_blocker` rules are still enforced on the refresh window's contribution to the week's total; staying inside the band is reasonable but not mandatory.

### 9.5 Exercise + cardio block selection

Same conventions as `Layer4_PerPhase_v1.md` §9 + `Layer4_SingleSession_v1.md` §9 — apply Tier 1/2/3 substitution per the locale equipment view; respect `active_injuries`; honor 3A `weak_links` when prescribing accessory work; balance discipline rotation across the refresh window.

For cardio sessions: structured blocks (warmup / main_set / cooldown / interval_set / transition) with explicit intensity guidance per block. Interval blocks include `interval_reps`, `interval_work_min`, `interval_recovery_min`.

For strength sessions: 4–8 exercises typical; compound first; accessories second; emit `weak_link_targeted` on exercises hitting 3A `weak_links`; emit `technique_emphasis` on drill/skill-focused exercises. Use Tier 2/3 substitution with `substitute_text` / `proxy_origin_id` per the locale equipment view.

### 9.6 Don't over-explain

`coaching_intent` (200 chars) is one sentence stating the session's purpose. `session_notes` (240 chars) is the "why this prescription specifically" — surface the `intensity_modulated` reasoning here when the flag fires; otherwise keep it tight.

Voice: Direct. No platitudes. Match a real endurance coach.

---

## 10. Edge cases

| Case | Handling |
|---|---|
| Athlete's `raw_text` contradicts `parsed_intent` (e.g., raw_text says "I tweaked my ankle yesterday" but `triggers_2d_injury=False`) | Honor the prose. Treat as if `triggers_2d_injury=True` for the prescription — avoid exercises hitting the ankle; substitute via Tier 2/3. Surface in `session_notes`: "Heard the ankle mention; avoided ankle-loaded work." Emit `Observation(category='opportunity', text='NL parser may have missed injury signal — recommend running 2D re-eval on next session')`. |
| `parser_confidence='low'` AND raw_text is non-empty | Treat raw_text as primary; ignore the structured flags (parser couldn't classify). Apply strong-bias-toward-intent reading from the prose. |
| `parser_confidence='low'` AND raw_text is empty | No athlete signal. 3A drives the modulation per §9.1 last row. |
| Refresh-window-after sessions include a `race_rehearsal` or `race_day` flag | Days_to_event is small. Treat the refresh window as Taper-shape regardless of inherited phase reading — recover into the rehearsal/race. No hard work; the athlete's pre-race intent is the priority. |
| Athlete's locale changed mid-refresh (day 1 home, day 2 travel) | Use per-day `locale_id` from `athlete.default_locale_for_date_window`. Different equipment views per day; prescriptions adapt. |
| `parsed_intent.triggers_2c_equipment` includes a locale not in `athlete.locales` | Should not happen post-cascade; orchestrator pre-validates. If observed, log to `notable_observations` as `opportunity` and prescribe from the union of available locales. |
| Refresh-window-after is empty (e.g., end-of-plan; athlete is on the last 9 days and refresh starts at day 7) | Continuity constraint is reduced. `current_phase` is still resolved from the freshly-re-run 3B payload per §3.5; the refresh proceeds against phase intent with reduced forward-continuity context. |
| `current_phase` cannot be derived | Should not happen on a refresh against an existing plan — 3B is re-run as part of the T1 cascade per v2 amendment and emits `periodization_shape.start_phase` non-None. If observed (3B re-run failed), the orchestrator raises before Layer 4 is invoked. |
| Multiple sessions on the same date (athlete §K allows 2 per day) | Honor §7.12 rules: no two strength; no two hard; at least one cardio. Order matters in `coaching_intent` text ("morning easy run, evening strength" vs. flipped) — surface ordering in `coaching_intent`. |
| Athlete's prior session today is already complete | Refresh covers tomorrow + day-after per `Plan_Refresh_D64_Design_v1.md` §3.1. Orchestrator pre-computes `scope_start = tomorrow`; the prompt reads it without re-deriving. |

---

## 11. Validator + retry contract

Reproduces `Layer4_Spec.md` §5.4 scope for T1 + the §5.5 capped retry mechanic. T1 inherits the **full** validator rule set since 3B periodization shape (read from inherited-phase metadata) is in scope.

**Rules applied to refresh-window output:**

| Rule | Severity tuning for T1 |
|---|---|
| `volume_band_*` | Applied per-week; the refresh window contributes a partial week. Severity standard. |
| `acwr_*` | Forward-projection across the refresh window + next 7 days (refresh-window-after). Severity standard. |
| `rest_spacing_*` | Cross-validates against adjacent-day refresh-window-after sessions per Pick 3 continuity. |
| `intensity_dist_*` | Applied per-phase; T1 window is small contribution. Severity standard. |
| `two_per_day_*` | Standard. |
| `equipment_unavailable_*` | Standard. Per-day locale resolution per §3.3. |
| `injury_violation_*` | Standard. Hard constraint. |
| `schedule_violation_*` | Standard. §K availability per day. |
| `discipline_excluded_*` | Standard. |
| `sport_locale_incompatible_*` | Standard. |

**Continuity cross-validation (T1-specific):**

- The `rest_spacing_*` rule extends across the refresh-window / refresh-window-after boundary. If T1 day-2 is hard AND refresh-window-after day-1 is hard for the same discipline → `rest_spacing_blocker` unless coaching flags justify (rare for T1).
- The `acwr_*` rule projects forward through refresh-window-after for the chronic-load denominator.

**Retry context rendering (D8):**

```
Pass {{ retries_used }} of cap=2 — repair these:
- [{{ severity }}] `{{ rule_name }}` on session(s) {{ affected_session_ids }}:
  Observed: {{ detail }}
  Constraint to honor on this pass: {{ suggested_constraint }}
```

`suggested_constraint` is orchestrator-generated per validator rule (e.g., for `injury_violation_blocker`: "Replace exercise `{exercise_id}` on session `{session_id}` with an alternative that does NOT hit `{injured_body_part}`."). The synthesizer treats it as a hard constraint on the repair pass.

**Cap behavior (`Layer4_Spec.md` §5.5):**

- Cap = 2 retries (default `capped_retries_per_phase`; Pattern B treats the whole call as one "phase").
- On cap-hit: latest synthesis accepted; outstanding `blocker` failures demoted to `warning`; orchestrator emits `Observation(category='best_effort_plan', elevates_to_hitl=True)`.
- Schema retry (malformed tool call): 1 attempt, separate budget; on second failure, `Layer4OutputError('schema_violation')` and bail.

---

## 12. Test scenarios

PSS-T1 prefix for v1 test scenarios. Maps to `Layer4_Spec.md` §13 test scenarios where overlap exists (the per-tier refresh paths weren't separately enumerated in §13 v1; this section is the v1 prompt-body test surface).

| ID | Scenario | Expected output |
|---|---|---|
| PSS-T1-01 | Athlete clicks T1 with empty NL note; 3A shows ACWR 1.0, last-hard 4 days ago; inherited phase Build. | 2 sessions matching refresh-window-after continuity; no `intensity_modulated`; standard Build-phase intensity placement. |
| PSS-T1-02 | Athlete: "I'm tired"; parsed fatigue=tired; 3A ACWR 1.0. | 2 sessions reduced from prior plan; `intensity_modulated` on at least one; `session_notes` explains "athlete reported tired; eased intensity." |
| PSS-T1-03 | Athlete: "I feel great let's push"; parsed motivation=high; 3A ACWR 1.35 (near blocker). | Sessions honor energy on intensity selection but cap volume so weekly ACWR stays inside warning band; `intensity_modulated` on the capped sessions; `session_notes` explains the ACWR cap. |
| PSS-T1-04 | Athlete: "I tweaked my left ankle"; parser caught triggers_2d_injury=True; 2D re-ran; active_injuries now contains `left_ankle / ligament_strain`. | Sessions avoid ankle-loaded work; substitutes via Tier 2/3 where needed; no `intensity_modulated` (different exercises, same intensity); `session_notes` mentions the ankle accommodation. |
| PSS-T1-05 | Athlete: "I tweaked my left ankle" but parser missed (triggers_2d_injury=False). | Per §10 edge case row 1: honor the prose; avoid ankle work; emit `Observation(category='opportunity', text='NL parser may have missed injury signal — recommend running 2D re-eval next session')`. |
| PSS-T1-06 | Athlete: "I'm sick"; parsed sickness=active. | Rest-shape sessions only (light mobility or empty list); `intensity_modulated` on any session emitted; `session_notes` explains. |
| PSS-T1-07 | Refresh-window-after day 1 is a planned long ride (LSD, `long_slow_distance` flag); T1 day 2 falls 1 day before it. | T1 day 2 prescribed as easy or rest — do not compromise the planned long ride. |
| PSS-T1-08 | Athlete: "Travel both days, only have a yoga mat"; parsed triggers_2c_equipment=[travel_locale]; 2C re-ran; per-day locale = travel_locale. | Sessions use travel_locale's equipment view; strength substituted to bodyweight + mat-only exercises. |
| PSS-T1-09 | First-pass validator returns `injury_violation_blocker` on a strength exercise hitting `left_wrist` active injury. | Retry pass replaces the offending exercise with Tier 2/3 substitute; validator passes; output accepted. |
| PSS-T1-10 | First-pass validator returns `rest_spacing_blocker` (T1 day 2 hard run + refresh-window-after day 1 hard run). | Retry pass eases day 2; validator passes. |
| PSS-T1-11 | First + second-pass both fail same `rest_spacing_blocker` (cap-hit case). | Latest synthesis accepted; failure demoted to warning; `Observation(category='best_effort_plan', elevates_to_hitl=True)` emitted by orchestrator. |
| PSS-T1-12 | `parser_confidence='low'` AND raw_text="i guess i could do more"; ambiguous. | Synthesizer reads raw_text as primary (low parser_confidence means flags unreliable); coaching judgment picks a slight-bump prescription; `intensity_modulated` fires if bump deviates from natural phase shape; `session_notes` notes the ambiguous read. |
| PSS-T1-13 | Athlete is in Taper with `days_to_event=5`; refresh-window-after day 1 has `race_rehearsal` flag. | T1 prescribes pre-rehearsal easy spinning + mobility; no hard work; `intensity_modulated` fires (Taper modulation due to imminent race rehearsal). |
| PSS-T1-14 | Empty refresh-window-after (athlete is at end-of-plan, refresh starts day 7 of remaining 9). | Continuity reads from refresh-window-during-prior + current_phase metadata; sessions prescribed without forward-continuity constraint. |
| PSS-T1-15 | `current_phase` cannot be derived (no `phase_metadata` in prior_plan_session_window). | Per §10 edge case: surface `Observation(category='opportunity', text='Phase metadata missing — refresh used Base defaults')`; prescribe Base-shape sessions. |

---

## 13. Performance budget

Per `Layer4_Spec.md` §§11.1–11.3:

| Budget | Value | Notes |
|---|---|---|
| Latency p50 | ~5s | Pattern B single call. `Layer4_Spec.md` §5.3 latency expectation for T1/T2 is 4–8s. |
| Latency p95 | ~9s | Includes one retry. Cap-hit (2 retries) worst case ~15s. |
| Input tokens (typical) | ~4500 | Full 3A + 2A + 2D + 1 + `parsed_intent` + `prior_plan_session_window ±7d`. |
| Input tokens (worst case) | ~6500 | With `parsed_intent` triggering 2C re-run (full equipment view for one locale) + slightly heavier `prior_plan_session_window`. |
| Extended thinking tokens | ~3000 (budget) | Per D2. |
| Output tokens | ~1500 | Up to 4 sessions × ~400 each = ~1600 max. |
| Cost per call (Sonnet 4.6 typical pricing) | ~$0.05 | ~$0.025 input + ~$0.025 output. |
| Cost per call (worst case) | ~$0.10 | With cap-hit retries. |
| Cache key per `Layer4_Spec.md` §9.x | `(athlete_id, tier, refresh_scope_start, sha256(normalized(parsed_intent.raw_text + parsed_intent flags + 3A pulse)))` | Identical inputs cache-hit; orchestrator rebinds `plan_version_id`. |

---

## 14. Open items + gut check

### 14.1 Open items

- **`intensity_modulated` trigger broadening.** This session's paired spec amendment to `Layer4_Spec.md` §8.6 broadens the trigger from D-63-only to also cover `plan_refresh` paths (T1/T2 strong-bias-toward-intent emits the flag when modulating against natural phase-shape + continuity reading). The amendment is small (one trigger row); verify §8.6 + §8.7 both reflect the broader scope after this session's PR lands.
- **`current_phase.intended_intensity_distribution`** — when 3B is not re-run on T1, the phase distribution is read from the §5.4 v1 defaults (Base 80/15/5 etc.). If 3B was custom-tuned for the athlete in the prior `plan_create` call, the T1 reading uses the default rather than the athlete-specific shape. Document as v1 limitation; full athlete-specific shape inheritance would require persisting the per-call `intended_intensity_distribution` in `prior_plan_session_window` metadata. Lands as a follow-up when T1 telemetry reveals the gap matters.
- **NL parser failure cascade.** §10 edge case row 1 (raw_text contradicts parsed_intent) flags the case but the prompt's recovery is conservative — honor the prose, surface as opportunity. If this fires often, a tighter feedback loop (orchestrator re-runs the parser with the prompt's contradiction signal) is the v2 improvement. v1 ships the conservative path.
- **Empty-sessions output validation.** `len(sessions)==0` is allowed per §4.2 but rare. Validator should not flag empty output as schema-violation; need to verify the §5.4 rule set handles empty input gracefully. Lands as a validator-implementation followup.

### 14.2 Gut check

**What's right:**
- **Strong-bias-toward-intent is the right philosophy for the refresh surface.** The athlete clicked "Refresh" because they have new context; the system's job is to honor that, not override it with stale objective signals. 3A signals are still the load-bearing magnitude calibrator, but direction comes from the athlete.
- **Continuity hand-off as the primary constraint** keeps T1 minimally disruptive. The 2-day window is too short to materially shift the periodization; reading refresh-window-after as a hand-off target ensures the refresh doesn't break the plan downstream.
- **`intensity_modulated` mandatory when applicable** prevents silent modulation. The flag is the audit trail for "the system did something different than the periodization would have called for, and here's why."
- **Closed coaching-flag enum** matches prior prompt-body precedent; orchestrator merge handles spec-auto flags so the prompt's surface stays narrow.

**Risks:**
- **Strong-bias may produce bad refreshes when athletes under-report fatigue.** Athlete: "I feel fine" + 3A says ACWR 1.4 — system honors fine, athlete digs deeper hole. Mitigation: the magnitude-calibration via 3A pulls back; the ACWR validator catches blocker territory. But the warning-band edge is athlete-honored.
- **Parser miss cases (raw_text contradicts parsed_intent)** are real and the conservative honor-the-prose path may miss the deeper signal (e.g., injury severity). v1 mitigation is the `opportunity` observation; v2 could re-fire the parser.
- **Inherited-phase reading from `prior_plan_session_window` metadata** depends on phase metadata being present + correctly populated by the prior `plan_create` or Pattern-A refresh. If the prior plan was Pattern-B refreshed (no phase_metadata per §7.12), inheritance fails — §10 edge case handles this but the fallback (Base defaults) is conservative. Real prevention is ensuring `plan_create` is the only producer of phase_metadata seeds, and refreshes preserve them on non-modified sessions.

**What might be missing:**
- **Multi-athlete coordination.** Joint-session overlays (Layer 4.5) are out of v1; T1 of athlete A doesn't propagate to athlete B's joint sessions. Same gap as §6.2 in single-session.
- **Refresh-while-doing-a-session.** Athlete is mid-workout, clicks Refresh. Should the in-progress session be regenerated? Per `Plan_Refresh_D64_Design_v1.md` §12 forward-pointer: no — in-progress sessions are immutable; refresh starts from the next session. Spec'd at session-state level; this prompt assumes the orchestrator already pre-computed the right `scope_start`.
- **NL signal richness.** v1 `parsed_intent` schema has 3 soft signals (fatigue / sickness / motivation) + 5 trigger booleans. Real athlete speech is richer ("I felt strong on Tuesday's run but the climb at the end was harder than expected — knee felt fine but quads were cooked"). Parser maps to the schema's vocabulary; signal loss is real. Mitigation: `raw_text` passthrough means the synthesizer reads the prose directly. v2 could expand the schema.

**Best argument against this scope:**

T1's 2-day window is the smallest, most surgical refresh. The minimum-viable T1 prompt could be one paragraph: "Take the next 2 days, honor the athlete's note, don't break adjacent sessions." Everything else in this file is scaffolding around that core. The 700-line spec investment is justified by the closed-set flag taxonomy + validator integration + retry-context rendering — those make the prompt programmable and testable. But for N=1 athlete at launch, a 100-line prompt would likely produce indistinguishable output 95% of the time, with the remaining 5% being the cap-hit / parser-miss / continuity-break edge cases where the scaffolding pays off.

Counter: the scaffolding pays off in the 5% of cases that are exactly where the athlete loses trust in the system. A bad refresh in those cases is a churn moment; a good refresh is a retention moment. The investment is justified at any non-trivial scale, and the cost of building it correctly once is lower than the cost of building it twice. Same logic as `Plan_Refresh_D64_Design_v1.md` §12 "build the right abstraction now."

---

*End of Layer4_RefreshT1_v1.md.*
