# Layer 4 — Race-Week Brief Synthesizer Prompt Body

**Prompt name:** `Layer4_RaceWeekBrief`
**Entry point:** `llm_layer4_race_week_brief` (`Layer4_Spec.md` §3.4)
**Pattern:** B (single LLM call + deterministic validator; no seam reviewer; no phase decomposition — Taper window is ≤ 1 phase per §5.1)
**Caller:** Orchestrator-triggered when `days_to_event ≤ 14`, OR athlete-triggered via the dedicated race-week-brief surface
**Status:** v1 — draft
**Date:** 2026-05-17
**Position in arc:** Fifth and last of 5 prompt bodies (after `Layer4_SeamReviewer_v1.md`, `Layer4_PerPhase_v1.md`, `Layer4_SingleSession_v1.md`, `Layer4_RefreshT1_v1.md` + `Layer4_RefreshT2_v1.md`). Closes the Layer 4 prompt-body arc.

---

## Source decisions (this session, Andy 2026-05-17)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Tool-use** (`record_race_week_brief`); single tool, single call per invocation; strict JSON schema with `additionalProperties: false` at every nesting level. The tool takes three top-level arguments: `taper_session_overrides` (list of modified PlanSessions), `race_week_brief` (RaceWeekBrief object), and `race_plan` (RacePlan object, omitted for single-day events). | Inherits the convention from all four prior prompts. A single tool gives the model full visibility into how the three outputs interrelate — kit_manifest must align with what segments demand; pacing_strategy must align with goal_outcome; Taper session overrides must align with the brief's emphasis (e.g., `kit_check` date moves if the brief picks a different verification cadence per `Layer4_Spec.md` §8.5). Split tools would require sequential calls and prevent the model from cross-checking. |
| D2 | Extended thinking budget | **~5500 tokens.** | Higher than per-phase's 5000 because race-week-brief's reasoning surface is the broadest in the pipeline: multi-locale equipment views (race locale + transitions + post-race) × multi-segment race execution × multi-hour fueling × contingency cross-product × athlete-specific 2D injury modulation. Multi-day events add segment + transition + night-section + sleep-deprivation reasoning that single-day events skip. Single-day events do not consume the budget headroom; thinking budget is set defensively for the multi-day case which is the load-bearing scenario for Andy's Pocket Gopher Extreme 2026 race. |
| D3 | Input format | **Full payloads verbatim** for 1 + 2A + 2B + 2C-per-locale + 2D + 2E + 3A + 3B + Taper-phase prior sessions + event metadata. No trimming. | Race-week brief is the only Layer 4 entry that consumes all five Layer 2 payloads. Input budget headroom is ~4500–6500 tokens; well within Sonnet's context window even with extended thinking. Trimming risks losing kit/equipment/fueling/terrain signal the brief is supposed to weave together. |
| D4 | Prior-plan Taper window rendering | **Full verbatim Taper window** (typically last 14–21 days; ≤42 sessions at the §7.12 max-2-per-day cap). | Taper is the load-bearing context for the brief; volume token-load is manageable (~1500–2500 tokens for a 21-day window with 8–14 actual sessions). Coaching reasoning needs full visibility into what was prescribed to know what to modify with race-week flags + which sessions become race-rehearsal candidates. Earlier phases (Build, Peak) are NOT rendered verbatim — 3A's recent-trajectory + 3B's periodization_shape carry the prior context. |
| D5 | Pacing strategy depth (**Andy's Pick 2 — hybrid**) | **Hybrid: hard numeric targets where 3A's recent training data supports them; RPE + qualitative heuristic where it doesn't.** Per-segment `pacing_target` uses whichever measure the discipline supports (pace/km for running, HR/power for cycling, RPE for nav-puzzle or technical segments). | Andy 2026-05-17 architectural pick (option a, recommended). Leverages 3A's data for races where the athlete has measurable race-pace history (single-day road events; well-trained disciplines); falls back to RPE for expedition AR night sections, technical terrain, and any segment where conditions degrade hard targets early. Rejects "hard targets across the board" (breaks in multi-day fatigue + condition variance) and "RPE only" (loses 3A's data leverage for short single-day races). |
| D6 | Contingency depth (**Andy's Pick 3 — mixed**) | **Mixed: short anchor table of must-have contingency categories per race_format + LLM expands within each + adds athlete-specific.** Anchor table: any race → GI distress / hydration / mechanical-or-gear-failure; outdoor AR + ultra → navigation error / sleep-deprivation / weather (cold + heat + rain onset); stage races → between-stage recovery; multi-day → cumulative fatigue + crew-pacing-mismatch. LLM expands within each + adds athlete-specific (e.g., wrist re-aggravation per 2D; known weak link per 3A `weak_links`). | Andy 2026-05-17 architectural pick (option a, recommended). Carries the anchor-table precedent from per-phase (deload cadence per mode; Taper-length per race format). Closed-set risks missing athlete-specific cases; synthesizer-only risks missing must-have categories. Mixed gets both — coverage guaranteed via anchor table, athlete-specific via LLM judgment. |
| D7 | File scope (**Andy's Pick 1 — unified**) | **Unified file with multi-day branch at the RacePlan slot.** One `Layer4_RaceWeekBrief_v1.md`; Mustache-style `{{#multi_day}}…{{/multi_day}}` block at the RacePlan emission slot in the user prompt. Coaching logic is shared (Taper-phase modulation, kit-check cadence, fueling strategy, contingency reasoning); the multi-day extension is structurally additive (segment + transition + night-section reasoning), not conceptually different. | Andy 2026-05-17 architectural pick (option a, recommended). Carries the single-session precedent (unified locale/quick_equipment branch). Rejects T1/T2's two-file precedent — that precedent was Andy's pick over the architect's recommendation; single-day vs multi-day race-week share more coaching surface than T1 vs T2 (T2 has weekly-volume-as-validator load-bearing constraints that don't apply to T1). |
| D8 | Closed-set `coaching_flags` enum + spec-auto interaction | **LLM-emittable cross-phase set:** `intensity_modulated` (per `Layer4_Spec.md` §8.6 broadened trigger — fires when synthesizer modulates Taper session intensity from prior-plan periodization shape, e.g., pulls back a Taper long-run because the athlete is sick) + `discipline_specific_intensity` (when prescribing race-discipline-specific intensity in a Taper session, e.g., race-pace rehearsal). **Spec-auto Taper flags handled orchestrator-side per `Layer4_Spec.md` §8.5:** `race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper` — the prompt prescribes the underlying session content; the orchestrator stamps these flags based on session shape + `days_to_event` post-synthesis. The prompt MUST produce session content that lets the orchestrator stamp the correct flags (e.g., the `kit_check` session should be a light easy day per §8.5 row 3; the `pacing_lock` session should be a moderate-or-easy run/ride at race target zone per §8.5 row 4). | Spec-auto flags are NOT in the LLM-emittable enum; the prompt is the upstream half of the spec-auto/orchestrator-stamp contract. `opportunity` observation is the single LLM-emitted exception per `Layer4_Spec.md` §8.7 — race-week-brief can emit `opportunity` for coaching surfaces not tied to a rule (e.g., "Consider a 20-min skill spin on the MTB course Friday — fresh legs + recon value"). |
| D9 | `kit_manifest` resolution policy | **Hybrid:** prompt instructs to prefer canonical names from `layer0.equipment_items` (joined via 2C equipment views for available locales); free-text fallback when no canonical exists (mandatory race-specific gear like "Petzl Tikkina headlamp w/ ≥150 lumens" or "Required: SPOT/inReach device per race rules"); validator flags non-canonical items as soft warnings emitting a `data_gap` notable_observation per `Layer4_Spec.md` §4.5 row 7 (`kit_manifest_inputs_incomplete`); kit_manifest synthesis degrades gracefully. | Matches `Layer4_Spec.md` §5.4 validator scope ("validate `RaceWeekBrief.kit_manifest` items exist in layer0 equipment registry (or are flagged free-text)"). Andy decision-load delegated — spec already pre-decided the policy; prompt body just encodes the convention. |
| D10 | `RuleFailure` retry context rendering | **Hybrid:** `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. | Mirrors all four prior prompts. Suggested-constraint field is orchestrator-generated. |
| D11 | Schema-enforced length caps | **Tight caps matched to field role + max_tokens=6000 budget:** RaceWeekBrief fields — `pre_race_logistics` 300 chars; `drop_bag_strategy` 240 chars (nullable); `course_familiarization_notes` 280 chars (nullable); `race_day_fueling_plan` 320 chars; `pre_race_meal_strategy` 280 chars; `pacing_strategy_summary` 200 chars; `contingencies[]` 180 chars each (max 8 entries); `mental_prep_cues[]` 120 chars each (max 5 entries); `kit_manifest[].item` 80 chars; `kit_manifest[].purpose` 120 chars; PlanSession overrides — same caps as single-session (240/200/120/240 for session_notes/coaching_intent/load_prescription/instructions). RacePlan fields — `segments[].terrain_notes` 240 chars; `segments[].coaching_notes` 240 chars; `transitions[].notes` 200 chars; `pacing_strategy.rationale_text` 300 chars; `fueling_strategy.rationale_text` 300 chars; `contingencies[].action_plan` 200 chars. | The brief + RacePlan are the largest outputs in the pipeline (`max_tokens=6000`); per-field caps prevent any single field from absorbing the whole budget. Telemetry will measure cap-hit rates post-launch. |
| D12 | Coaching voice | **Direct + evidence-grounded across all athlete-facing surfaces.** Same CLAUDE.md voice as single-session + T1/T2 + per-phase. `mental_prep_cues` field is explicitly "evidence-grounded — no platitudes" per `Layer4_Spec.md` §7.13 — allowed: "Trust the work you've done; review your 28-day chronic load if doubt creeps in"; forbidden: "You've got this!" / "Crush it!" / "Believe in yourself." Race-day-specific phrasings reference concrete signals (HR, RPE, pace, fueling intake, splits) rather than emotional framings. | Hard constraint from CLAUDE.md ("No platitudes. No cheerleading. No hype. Tone matches a real endurance coach talking to a serious athlete."). Race-week is precisely where commercial coaching apps tend to drift toward hype; prompt voice must resist. |
| D13 | File location | `aidstation-sources/prompts/Layer4_RaceWeekBrief_v1.md` per the `prompts/` subdir convention. | Inherits from all four prior prompts. |

**Companion contract sections (`Layer4_Spec.md`):** §3.4 (call signature — `llm_layer4_race_week_brief` parameters), §3.5 (errors — `race_week_brief_requires_event_mode`, plus the §4.5 input validation codes), §4.5 (input validation rules — event mode required, event within 14d window, event date in future, 2E payload required, event locale resolves, race_format set, kit data prerequisites soft-warning), §5.1 (pattern routing — B always for both single-day + multi-day; Pattern A's per-phase machinery unnecessary for ≤ 1 phase), §5.3 (Pattern B algorithm — context build, single LLM call, parse, validator, capped retry, payload compose), §5.4 (deterministic validator — race-week-brief scope: Taper-session overrides against Taper phase intent, kit_manifest items against layer0 equipment registry, RacePlan.segments chronological ordering when multi-day, fueling-strategy macro ranges against 2E tier), §5.5 (capped retry, cap=2 default for Pattern B), §7.2/§7.3/§7.4 (`PlanSession` discriminated union + `CardioBlock` + `StrengthExercise` — Taper session overrides), §7.5 (`SessionPhaseMetadata` — `phase_metadata` is Taper-phase metadata for the Taper-session overrides since the brief operates within an existing Taper phase; this differs from single-session + T1/T2 which set phase_metadata=None per §7.12), §7.13 (`RaceWeekBrief` schema), §7.14 (`RacePlan` schema; multi-day only — race_format ∈ `{expedition_ar, stage_race, multi_day_ultra}`), §8.5 (Taper-phase spec-auto coaching flags — orchestrator stamps `race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper` post-synthesis), §8.6 (`intensity_modulated` LLM-emitted cross-phase flag per the broadened trigger; `discipline_specific_intensity` LLM-emitted), §8.7 (call-level observations — `opportunity` LLM-emitted exception; `data_gap` orchestrator-emitted on §4.5 soft-fail), §9.1 (cache key — full payload set + Taper window hash; midnight-UTC invalidation per §9.3 since output is `days_to_event`-anchored), §11.1 (latency p50 ~8s / p95 ~15s), §11.2 (token budget — ~5500 input + ~3000–5000 output for multi-day; ~5500 input + ~1500 output for single-day), §11.3 (cost — ~$0.18 typical multi-day / ~$0.10 typical single-day, ~$0.35 worst-case multi-day with cap-hit retries).

---

## 1. Purpose + scope

### 1.1 What this prompt produces

Three coordinated outputs in a single tool call (`record_race_week_brief`):

1. **`taper_session_overrides`** — A list of modified Taper-phase `PlanSession` records (one per Taper-window day that already had a planned session). The brief may modify session_notes, coaching_intent, intensity, duration, cardio_blocks, or strength_exercises to match the race-week emphasis the brief synthesizes (e.g., shift Wednesday's run to a `pacing_lock` rehearsal at race-target HR; add `kit_check` framing to Saturday's light spin). The orchestrator post-stamps the spec-auto Taper coaching_flags per `Layer4_Spec.md` §8.5 based on session shape + `days_to_event`. Pre-existing Taper sessions from `prior_plan_session_window` that the brief does NOT modify are passed through unchanged (no override emitted).

2. **`race_week_brief`** — A structured `RaceWeekBrief` per `Layer4_Spec.md` §7.13. Always produced regardless of `race_format`. Fields: `days_to_event`, `event_name`, `event_date`, `event_locale`, `race_format`, `goal_outcome`, `pre_race_logistics`, `drop_bag_strategy` (nullable), `course_familiarization_notes` (nullable), `kit_manifest`, `kit_check_dates`, `race_day_fueling_plan`, `pre_race_meal_strategy`, `pacing_strategy_summary`, `contingencies`, `mental_prep_cues`. Athlete-facing; consumed by the race-week-brief UI surface + Layer 5 clothing/conditions advisor.

3. **`race_plan`** — A structured `RacePlan` per `Layer4_Spec.md` §7.14. **Multi-day events only** (`race_format ∈ {expedition_ar, stage_race, multi_day_ultra}`); omitted for single-day events. Fields: `race_name`, `race_start_datetime`, `race_end_estimate_datetime`, `race_format`, `locales`, `segments`, `transitions`, `pacing_strategy`, `fueling_strategy`, `contingencies`. Athletes consume during the race itself (typically printed / loaded offline); the D-64 NL parser reads it for context on race-week refresh fires.

### 1.2 What this prompt does NOT produce

- **New Taper-phase sessions.** The brief only modifies existing `prior_plan_session_window` Taper sessions — it does NOT add or remove sessions from the plan. Adding sessions belongs to `plan_refresh` T2 (re-shape weekly structure); removing sessions belongs to `plan_refresh` T1 (rest-day intervention). Race-week-brief operates within the existing Taper structure.
- **Phase re-decomposition.** No `PhaseStructure`, no `SeamReview`, no shape override. The Taper phase is already in place per the originating `plan_create`; the brief refines content within it.
- **Race-day FIT/TCX workout files.** The brief produces structured prescription text + segment pacing targets; converting those to FIT files (for Garmin/Wahoo/COROS upload) is downstream tooling, not Layer 4 scope.
- **Post-race recovery sessions.** Sessions dated `> event_date` are out of scope. Recovery prescription is `plan_refresh` territory once the athlete provides post-race state signals (3A re-eval).
- **Observations or notable_observations rows** other than the LLM-emitted `category='opportunity'` exception per `Layer4_Spec.md` §8.7. The `data_gap` observation for `kit_manifest_inputs_incomplete` is orchestrator-computed from the §4.5 soft-fail.
- **Goal-viability re-assessment.** 3B's `goal_viability` is the source of truth; the brief's `goal_outcome` field surfaces 3B's viability call to the athlete in plain language but does not re-derive it.

### 1.3 Failure modes this prompt + retry semantics catch

- LLM prescribes a Taper-session override at intensity that conflicts with `pre_race_taper` guidance (e.g., a hard interval session 2 days before the event) → validator `taper_phase_intent_violation_blocker` → capped retry with the intensity ceiling restated explicitly.
- LLM produces a `kit_manifest` with all free-text items (none resolving to `layer0.equipment_items`) → validator `kit_manifest_inputs_incomplete` (soft warning, per §4.5 row 7) → no retry; orchestrator emits `data_gap` observation; brief ships with the free-text manifest.
- LLM produces a `RacePlan.segments` list out of chronological order (segment_index gaps; estimated_start_offset_hr not monotonically increasing) → validator `race_plan_segments_unordered_blocker` → capped retry with ordering constraint restated.
- LLM produces a `RacePlan.fueling_strategy` with carb-per-hour ranges outside the 2E race-day fueling tier band (e.g., 90 g/hr for an athlete tiered at 40–60 g/hr) → validator `fueling_strategy_2e_tier_mismatch_blocker` → capped retry with the 2E tier restated as constraint.
- LLM omits a contingency category that the D6 anchor table requires (e.g., AR brief without a navigation-error contingency) → validator `contingency_anchor_category_missing_warning` → capped retry adding the missing category.

---

## 2. Pipeline placement

**Call site:** `llm_layer4_race_week_brief` per `Layer4_Spec.md` §3.4. Invoked by the orchestrator when `days_to_event ≤ 14` (auto-fire) OR by the athlete via the race-week-brief surface (manual fire). Event-mode plans only (`layer3b_payload.mode == 'event'`); §4.5 raises `race_week_brief_requires_event_mode` otherwise.

**Pattern:** B per `Layer4_Spec.md` §5.1 (race-week-brief is Pattern B for both single-day + multi-day; the Taper window is ≤ 1 phase, so Pattern A's per-phase machinery is unnecessary). Algorithm per `Layer4_Spec.md` §5.3:

- Step 1: build context (this prompt's §3 inputs — full payloads verbatim + full verbatim Taper window).
- Step 2: single LLM call (this prompt's §5 system + §6 user + §7 sampling config; `max_tokens=6000` per §3.4).
- Step 3: parse `record_race_week_brief` tool output into `(taper_session_overrides, race_week_brief, race_plan)`.
- Step 4: deterministic validator (`Layer4_Spec.md` §5.4 race-week-brief sub-bullet): Taper-session overrides against Taper phase intent; `kit_manifest` items against layer0 equipment registry; `RacePlan.segments` chronological ordering when multi-day; fueling-strategy macro ranges against 2E tier; contingency anchor-category coverage per D6.
- Step 5: capped retry per `Layer4_Spec.md` §5.5 on validator failure; cap=2 (default).
- Step 6: compose `Layer4Payload` with `mode='race_week_brief'`, `pattern='B'`, `sessions` = modified Taper-phase sessions (overrides applied + non-modified Taper sessions passed through), `race_week_brief` non-None, `race_plan` non-None for multi-day events / None for single-day, `phase_structure=None`, `seam_reviews=None`.

**Out-of-pipeline cases:**
- Cache hit per `Layer4_Spec.md` §9.1 race-week-brief cache key → no LLM call; orchestrator rebinds `plan_version_id` per §9.4. Note: midnight-UTC cache invalidation per §9.3 — output is `days_to_event`-anchored.
- Input validation failure per `Layer4_Spec.md` §4.5 → raises `Layer4InputError(code)`; no LLM call. Common pre-LLM raises: `race_week_brief_requires_event_mode`, `race_week_brief_too_early` (athlete-manual fire outside the 14d window), `event_date_in_past`, `layer2e_payload_missing`, `event_locale_unresolved`, `race_format_unset`.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following variables. All are required unless noted optional. Token-budget realism per `Layer4_Spec.md` §11.2: ~4500–6500 input tokens total.

### 3.1 Event metadata

| Variable | Source | Notes |
|---|---|---|
| `event.name` | Layer 1 §H.2 | Athlete-facing event name (e.g., "Pocket Gopher Extreme 2026"). |
| `event.date` | Layer 1 §H.2 | Calendar date; multi-day events use the start date. |
| `event.format` | Layer 3B | `'single_day' \| 'expedition_ar' \| 'stage_race' \| 'multi_day_ultra'`. Drives whether RacePlan is produced. |
| `event.estimated_duration_hr` | Layer 1 §H.2 | For multi-day events: total race duration estimate (48–56h for Pocket Gopher Extreme; pacing + fueling + contingency depth scales with this). |
| `event.locale_id` | Layer 3B | The race locale ID — resolves to a `locale_profiles` row scoped to the call-site user. |
| `event.locales[]` | Layer 1 §H.2 (when multi-day) | Ordered list of locale IDs covering the race route (for stage races and expedition AR with multiple geographic locales). Single-day events: length-1 list with just `event.locale_id`. |
| `event.race_rules_summary` | Layer 1 §H.2 (when populated) | Mandatory-gear list, cut-off times, segment-specific rules. Drives `kit_manifest` mandatory entries. |
| `days_to_event` | Computed | `event.date - today()`. In `[0, 14]` per §4.5. Drives `kit_check_dates` cadence (typically days_to_event-7, -3, -1). |

### 3.2 Athlete + race-week context

| Variable | Source | Notes |
|---|---|---|
| `athlete.user_id` | Layer 1 | Identification only. |
| `athlete.coaching_voice_preferences` | Layer 1 (when present) | Tone shading. |
| `athlete.experience_level` | Layer 1 | Beginner / intermediate / advanced / elite — drives contingency depth + mental_prep_cues sophistication. |
| `athlete.discipline_inclusion` | Layer 2A | Sports the athlete competes in / trains for. Drives `discipline_specific_intensity` flag emission when prescribing race-discipline-specific Taper sessions. |
| `athlete.active_injuries` | Layer 2D | Injury exclusions — hard constraints applied to Taper session overrides + flagged in `contingencies`. Andy's wrist injury per CLAUDE.md is the working example. |
| `athlete.sleep_baseline` | Layer 1 §I (when populated) | Race-week sleep strategy reference (typical bedtime, sleep duration target). |
| `athlete.travel_constraint` | Layer 1 §H.2 (when populated) | Travel window relative to event (drives `pre_race_logistics`). |

### 3.3 Athlete state (drives Taper modulation)

| Variable | Source | Notes |
|---|---|---|
| `athlete_state.aerobic_state` | Layer 3A | `'undertrained' \| 'fit' \| 'overtrained' \| 'unknown'` — drives whether Taper modulation pulls back (overtrained → more rest) or stays the course (fit). |
| `athlete_state.strength_state` | Layer 3A | Same enum as aerobic. |
| `athlete_state.recent_trajectory` | Layer 3A | Last 28d direction signal (improving / plateau / declining). |
| `athlete_state.active_injuries` | Layer 3A (mirrors 2D) | Cross-checked against 2D for consistency. |
| `athlete_state.acwr_7_28` | Layer 3A | ACWR for the primary discipline (or aggregate). Tapering athletes typically see ACWR dropping; values > 1.0 in race-week are a flag. |
| `athlete_state.weak_links` | Layer 3A (when populated) | Identified weak links from prior phase work. Drives athlete-specific `contingencies` entries. |
| `athlete_state.data_density` | Layer 3A | `'rich' \| 'moderate' \| 'sparse' \| 'very_sparse'` — when `'very_sparse'`, pacing depth defaults to RPE (D5 hybrid policy fallback) + brief notes the data-thin context. |

### 3.4 Periodization context (Taper phase intent)

| Variable | Source | Notes |
|---|---|---|
| `phase.name` | Layer 3B `periodization_shape.phase_weeks` | Always `'Taper'` for race-week-brief invocations within 14d of event. |
| `phase.weeks` | Layer 3B | Total Taper length per §J.2 anchor table (1–4 weeks per race format). |
| `phase.intended_volume_band` | Layer 3B | Taper weekly volume band (hours/week, low–high). Used to validate that Taper session overrides don't drift outside band. |
| `phase.intended_intensity_distribution` | Layer 3B | Taper intensity distribution (typically heavily Z1-Z2 dominant; some Z3 race-pace touches; minimal Z4-Z5). |
| `phase.deload_cadence_anchor` | Layer 3B | Used by the orchestrator to validate Taper consistency; the brief inherits the established Taper shape. |
| `phase.goal_viability` | Layer 3B | `'viable' \| 'stretch' \| 'unrealistic'` — drives `goal_outcome` field language ("Finish" vs "Compete mid-pack" vs "Podium attempt"). |

### 3.5 Multi-locale equipment view (Layer 2C — race-week-specific load-bearing)

For race-week-brief specifically, 2C payloads for multiple locales are passed:

| Variable | Source | Notes |
|---|---|---|
| `equipment.event_locale` | Layer 2C[event.locale_id] | Equipment view at the race locale itself (for course-rehearsal sessions during the Taper if the athlete is near the venue; for race-day kit verification). |
| `equipment.taper_locales[]` | Layer 2C[athlete-Taper-locales] | Equipment views for the locales where Taper sessions are happening (home gym, hotel gym if traveling, etc.). Used to confirm Taper session overrides are equipment-feasible. |
| `equipment.transit_locale` | Layer 2C (optional; when athlete travels) | Equipment view for the layover / transit hotel locale, if any. |

### 3.6 Prior plan Taper window (full verbatim per D4)

| Variable | Source | Notes |
|---|---|---|
| `prior_taper_sessions[]` | Plan-gen orchestrator | List of Taper-phase `PlanSession` records covering the Taper window (typically last 14–21 days of the plan). Each session rendered verbatim in §6 with: date, day_of_week, time_of_day, kind, discipline_name, locale_name, duration_min, intensity_summary, session_notes, coaching_intent, cardio_blocks (when cardio), strength_exercises (when strength), rest_reason (when rest), existing coaching_flags, phase_metadata.week_in_phase, phase_metadata.total_weeks_in_phase. The brief may modify these; non-modified sessions pass through unchanged. |

### 3.7 Race-day fueling tier (Layer 2E — load-bearing for race-day plan)

| Variable | Source | Notes |
|---|---|---|
| `fueling.race_day_tier` | Layer 2E | Athlete's race-day fueling tier (e.g., `'high_carb_loader'`, `'moderate_carb'`, `'fat_adapted'`). Drives `race_day_fueling_plan` + `RacePlan.fueling_strategy` macro targets. |
| `fueling.cho_g_per_hr_band` | Layer 2E | Carb-per-hour intake range for the athlete's tier. RacePlan.fueling_strategy.cho_g_per_hr_low/high must fall inside this band. |
| `fueling.sodium_mg_per_hr_target` | Layer 2E | Sodium target adjusted for heat_acclim_state. |
| `fueling.fluid_ml_per_hr_target` | Layer 2E | Fluid target — adjustable per terrain (hot vs cool, dry vs humid per 2B). |
| `fueling.caffeine_strategy` | Layer 2E (when populated) | Athlete-tested caffeine cadence — load + race-day deployment. |
| `fueling.sleep_dep_strategy` | Layer 2E (when multi-day populated) | Sleep-deprivation fueling strategy for multi-day events crossing night hours. |
| `fueling.gi_tolerance_notes` | Layer 2E (when populated) | Athlete's known GI sensitivity / tested products / failure modes. Drives the GI contingency. |

### 3.8 Terrain + environment (Layer 2B — drives pacing + kit)

| Variable | Source | Notes |
|---|---|---|
| `terrain.surface_profile` | Layer 2B[event.locale] | Trail / road / mixed / technical / water — drives pacing target shape (HR vs RPE) + kit_manifest mandatory items (e.g., trail shoes vs road; hydration vest vs handheld). |
| `terrain.elevation_profile` | Layer 2B | Climbing meters per km + max grade per segment (when multi-day). |
| `terrain.weather_window` | Layer 2B (when populated, race-week forecast) | Forecast temperature / precipitation / wind for race day; drives contingencies (rain onset, heat, cold). When unpopulated, brief defers detailed weather contingencies. |
| `terrain.night_section_present` | Layer 2B (multi-day) | Boolean — whether race crosses night hours. Drives `night_section_adjustment` in RacePlan.pacing_strategy + sleep-dep fueling. |

### 3.9 Retry context (only present on retry pass)

| Variable | Source | Notes |
|---|---|---|
| `retries_used` | Orchestrator | 0 on first pass; 1 or 2 on retry. Cap = 2 per `Layer4_Spec.md` §5.5. |
| `rule_failures` | Validator | List of `RuleFailure` records from the prior pass. Each: `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. Renders in §6 as constraint statements per D10. |

### 3.10 Intentionally NOT passed

- **Per-phase prior outputs** (Build / Peak phase sessions verbatim) — 3A's recent-trajectory + 3B's periodization_shape carry the prior context; session-level granularity for earlier phases is not coaching-relevant to the race-week brief.
- **`single_session_synthesize` ad-hoc sessions** — out-of-plan workouts are tracked via D-63 `ad_hoc_workout_suggestions` storage, not via `prior_plan_session_window`. The brief operates on the planned Taper structure.
- **Layer 4 `seam_reviews` from prior `plan_create`** — Pattern B; no seam reviewer; the brief inherits the established phase structure without re-reviewing seams.
- **`plan_version_id`** — never in the cache key per §9.1; the orchestrator allocates per call and rebinds on cache hit per §9.4. The brief itself doesn't need it for synthesis.
- **`today()` directly** — `days_to_event` is computed by the orchestrator before invocation; the prompt receives the integer, not the calendar date arithmetic. The cache key is `days_to_event`-anchored (midnight-UTC rollover per §9.3).

---

## 4. Output schema + tool definition

The synthesizer emits exactly one tool call to `record_race_week_brief`. The tool accepts three top-level arguments: `taper_session_overrides`, `race_week_brief`, `race_plan` (the last is omitted for single-day events).

### 4.1 Tool schema (strict JSON-schema, `additionalProperties: false` at every nesting level)

```json
{
  "name": "record_race_week_brief",
  "description": "Record the race-week brief — modified Taper-phase sessions, the structured RaceWeekBrief, and (for multi-day events only) the structured RacePlan.",
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["taper_session_overrides", "race_week_brief"],
    "properties": {
      "taper_session_overrides": {
        "type": "array",
        "maxItems": 42,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["session_id_to_override", "date", "kind", "duration_min", "intensity_summary", "session_notes", "coaching_intent"],
          "properties": {
            "session_id_to_override": {"type": "string", "description": "session_id from prior_taper_sessions[] that this override replaces."},
            "date": {"type": "string", "format": "date"},
            "kind": {"type": "string", "enum": ["cardio", "strength", "rest"]},
            "duration_min": {"type": "integer", "minimum": 0, "maximum": 240},
            "intensity_summary": {"type": "string", "enum": ["easy", "moderate", "hard", "mixed", "rest"]},
            "coaching_intent": {"type": "string", "maxLength": 200},
            "session_notes": {"type": "string", "maxLength": 240},
            "coaching_flags": {
              "type": "array",
              "items": {"type": "string", "enum": ["intensity_modulated", "discipline_specific_intensity"]},
              "maxItems": 2,
              "uniqueItems": true
            },
            "cardio_blocks": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["block_kind", "duration_min"],
                "properties": {
                  "block_kind": {"type": "string", "enum": ["warmup", "main_set", "cooldown", "interval_set", "transition"]},
                  "duration_min": {"type": "integer", "minimum": 1, "maximum": 240},
                  "intensity_zone": {"type": "string", "enum": ["Z1", "Z2", "Z3", "Z4", "Z5", "mixed"]},
                  "instructions": {"type": "string", "maxLength": 240}
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
                  "sets": {"type": "integer", "minimum": 1, "maximum": 6},
                  "reps": {"type": "string", "maxLength": 40},
                  "load_prescription": {"type": "string", "maxLength": 120},
                  "instructions": {"type": "string", "maxLength": 240}
                }
              }
            },
            "rest_reason": {"type": "string", "enum": ["planned_recovery", "taper_drop", "travel_day"]}
          }
        }
      },
      "race_week_brief": {
        "type": "object",
        "additionalProperties": false,
        "required": ["goal_outcome", "pre_race_logistics", "kit_manifest", "kit_check_dates", "race_day_fueling_plan", "pre_race_meal_strategy", "pacing_strategy_summary", "contingencies", "mental_prep_cues"],
        "properties": {
          "goal_outcome": {"type": "string", "maxLength": 120, "description": "Plain-language summary of the athlete's goal for this event, derived from 3B goal_viability + §H.2."},
          "pre_race_logistics": {"type": "string", "maxLength": 300, "description": "Travel + arrival timing + sleep strategy. 1–3 sentences."},
          "drop_bag_strategy": {"type": ["string", "null"], "maxLength": 240, "description": "For events with drop-bag systems; null when not applicable."},
          "course_familiarization_notes": {"type": ["string", "null"], "maxLength": 280, "description": "Recon recommendations + critical course sections; null when not applicable."},
          "kit_manifest": {
            "type": "array",
            "maxItems": 30,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["item", "purpose", "optional"],
              "properties": {
                "item": {"type": "string", "maxLength": 80, "description": "Canonical equipment name from layer0.equipment_items where applicable; free-text otherwise."},
                "purpose": {"type": "string", "maxLength": 120, "description": "Why it's on the list (mandatory by race rules, nutrition transport, safety, etc.)."},
                "optional": {"type": "boolean", "description": "False = must-have; True = nice-to-have."},
                "layer0_canonical": {"type": "boolean", "description": "True when item resolves to a layer0.equipment_items row; False when free-text fallback per D9."}
              }
            }
          },
          "kit_check_dates": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string", "format": "date"},
            "description": "Dates to verify kit (typically days_to_event-7, -3, -1)."
          },
          "race_day_fueling_plan": {"type": "string", "maxLength": 320, "description": "Athlete-facing summary derived from 2E race-day fueling tier."},
          "pre_race_meal_strategy": {"type": "string", "maxLength": 280, "description": "Last 24h fueling + race-morning meal timing."},
          "pacing_strategy_summary": {"type": "string", "maxLength": 200, "description": "1–2 sentences; defers to RacePlan.pacing_strategy for multi-day depth."},
          "contingencies": {
            "type": "array",
            "minItems": 3,
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 180, "description": "Pre-thought-through plan for a known failure mode. Anchor categories per D6 must be represented."}
          },
          "mental_prep_cues": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": {"type": "string", "maxLength": 120, "description": "Direct, evidence-grounded. No platitudes per CLAUDE.md coaching voice."}
          }
        }
      },
      "race_plan": {
        "type": ["object", "null"],
        "additionalProperties": false,
        "description": "Required when event.format != 'single_day'; null for single-day events.",
        "required": ["race_format", "locales", "segments", "transitions", "pacing_strategy", "fueling_strategy", "contingencies"],
        "properties": {
          "race_format": {"type": "string", "enum": ["expedition_ar", "stage_race", "multi_day_ultra"]},
          "locales": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "description": "Locale ID in route order."}
          },
          "segments": {
            "type": "array",
            "minItems": 2,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["segment_index", "sport", "estimated_start_offset_hr", "estimated_duration_min", "terrain_notes", "pacing_target", "coaching_notes"],
              "properties": {
                "segment_index": {"type": "integer", "minimum": 0, "description": "0-indexed chronological order. Must be strictly monotonic across segments."},
                "sport": {"type": "string", "description": "Layer 0A canonical sport name."},
                "estimated_start_offset_hr": {"type": "number", "minimum": 0, "description": "Hours from race_start_datetime. Must be strictly monotonic across segments."},
                "estimated_duration_min": {"type": "integer", "minimum": 5, "maximum": 1800},
                "distance_km": {"type": ["number", "null"], "minimum": 0},
                "elevation_gain_m": {"type": ["number", "null"], "minimum": 0},
                "terrain_notes": {"type": "string", "maxLength": 240},
                "pacing_target": {
                  "type": "object",
                  "additionalProperties": true,
                  "description": "Free-shape per discipline: {'zone': 'Z2', 'measure': 'HR', 'low': 140, 'high': 155} | {'zone': 'Z2', 'measure': 'RPE', 'value': 5} | {'zone': 'mixed', 'measure': 'pace_per_km', 'target': '5:30'}."
                },
                "coaching_notes": {"type": "string", "maxLength": 240, "description": "Per-segment direct guidance. Reference Andy's discipline-specific weak links or known failure modes when relevant."}
              }
            }
          },
          "transitions": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["from_segment_index", "to_segment_index", "estimated_duration_min", "gear_changes", "is_fueling_window", "notes"],
              "properties": {
                "from_segment_index": {"type": "integer", "minimum": 0},
                "to_segment_index": {"type": "integer", "minimum": 0},
                "estimated_duration_min": {"type": "integer", "minimum": 0, "maximum": 180},
                "gear_changes": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 8},
                "is_fueling_window": {"type": "boolean"},
                "notes": {"type": "string", "maxLength": 200}
              }
            }
          },
          "pacing_strategy": {
            "type": "object",
            "additionalProperties": false,
            "required": ["overall_intensity_target", "pacing_milestones", "rationale_text"],
            "properties": {
              "overall_intensity_target": {"type": "string", "maxLength": 160, "description": "e.g., 'Z2 dominant; no Z4 unless emergency'."},
              "night_section_adjustment": {"type": ["string", "null"], "maxLength": 200},
              "pacing_milestones": {"type": "array", "items": {"type": "string", "maxLength": 120}, "maxItems": 10},
              "rationale_text": {"type": "string", "maxLength": 300}
            }
          },
          "fueling_strategy": {
            "type": "object",
            "additionalProperties": false,
            "required": ["cho_g_per_hr_low", "cho_g_per_hr_high", "sodium_mg_per_hr", "fluid_ml_per_hr", "caffeine_strategy", "rationale_text"],
            "properties": {
              "cho_g_per_hr_low": {"type": "integer", "minimum": 0, "maximum": 200},
              "cho_g_per_hr_high": {"type": "integer", "minimum": 0, "maximum": 200},
              "sodium_mg_per_hr": {"type": "integer", "minimum": 0, "maximum": 3000},
              "fluid_ml_per_hr": {"type": "integer", "minimum": 0, "maximum": 2000},
              "caffeine_strategy": {"type": "string", "maxLength": 200},
              "night_section_strategy": {"type": ["string", "null"], "maxLength": 240},
              "rationale_text": {"type": "string", "maxLength": 300}
            }
          },
          "contingencies": {
            "type": "array",
            "minItems": 4,
            "maxItems": 12,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["trigger", "action_plan", "threshold_to_invoke"],
              "properties": {
                "trigger": {"type": "string", "maxLength": 160, "description": "Specific observable signal."},
                "action_plan": {"type": "string", "maxLength": 200},
                "threshold_to_invoke": {"type": "string", "maxLength": 120}
              }
            }
          }
        }
      },
      "opportunities": {
        "type": "array",
        "maxItems": 2,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["text"],
          "properties": {
            "text": {"type": "string", "maxLength": 240, "description": "LLM-emitted coaching opportunity per §8.7 — surfaces as Observation(category='opportunity') downstream."},
            "evidence_basis": {"type": "array", "items": {"type": "string"}, "maxItems": 3}
          }
        }
      }
    }
  }
}
```

### 4.2 Cross-output schema rules

| # | Rule | Enforcement |
|---|---|---|
| 1 | When `event.format == 'single_day'`: `race_plan` MUST be omitted (or `null`). When `event.format != 'single_day'`: `race_plan` MUST be present. | Prompt-rule + validator. |
| 2 | `taper_session_overrides[].session_id_to_override` MUST reference a `session_id` present in `prior_taper_sessions[]`. | Validator. |
| 3 | `taper_session_overrides[].coaching_flags` is a closed 2-flag enum per D8 (`intensity_modulated`, `discipline_specific_intensity`); spec-auto Taper flags are NOT emitted here — orchestrator stamps post-synthesis per §8.5. | Schema enum. |
| 4 | When `intensity_modulated` flag is present on any override, `session_notes` MUST explicitly explain the modulation per the broadened §8.6 trigger. | Prompt-rule (no programmatic check; coaching review surface). |
| 5 | `race_week_brief.kit_check_dates` MUST contain dates within `[today, event.date]` and SHOULD include `event.date - 7` (kit_check anchor per §8.5 row 3); two additional dates at `event.date - 3` and `event.date - 1` are recommended. | Prompt-rule. |
| 6 | `race_week_brief.contingencies` MUST cover the D6 anchor categories applicable to the race format (any race: GI / hydration / mechanical-or-gear-failure; AR + ultra: nav / sleep-dep / weather; stage races: between-stage recovery; multi-day: cumulative fatigue + crew-pacing-mismatch). | Validator (anchor-category coverage check). |
| 7 | `race_plan.segments[].segment_index` MUST be strictly monotonic from 0; `estimated_start_offset_hr` MUST also be strictly monotonic. | Validator. |
| 8 | `race_plan.transitions[].from_segment_index` MUST reference an existing `segments[].segment_index` and `to_segment_index == from_segment_index + 1`. | Validator. |
| 9 | `race_plan.fueling_strategy.cho_g_per_hr_low` and `cho_g_per_hr_high` MUST fall inside `fueling.cho_g_per_hr_band` (2E race-day tier). Outside-band ranges raise `fueling_strategy_2e_tier_mismatch_blocker`. | Validator. |
| 10 | `race_plan.fueling_strategy.cho_g_per_hr_low ≤ cho_g_per_hr_high`. | Schema implicit + validator. |
| 11 | `race_plan.pacing_strategy.night_section_adjustment` MUST be non-null when `terrain.night_section_present == True`; otherwise should be null. | Validator (soft warning if mismatch). |
| 12 | When 2D active injuries are present, `race_week_brief.contingencies` SHOULD include an injury re-aggravation entry (e.g., for Andy's wrist: "Wrist re-aggravation during packraft paddle"). | Prompt-rule. |
| 13 | `kit_manifest[].layer0_canonical=True` items MUST have `item` exactly matching a `layer0.equipment_items.canonical_name`; `layer0_canonical=False` items are free-text per D9 and trigger orchestrator-side `data_gap` observation aggregation. | Validator (per-item canonical check). |
| 14 | `mental_prep_cues[]` MUST NOT contain platitudes/cheerleading/hype phrases per CLAUDE.md voice. Forbidden tokens (case-insensitive): "you've got this", "crush it", "believe in yourself", "trust the process" (generic), "race day magic", emoji of any kind. | Prompt-rule (no programmatic check post-validator; coaching review surface). |
| 15 | `opportunities[]` is the LLM-emitted exception per `Layer4_Spec.md` §8.7; max 2 entries; only fires when a coaching opportunity is materially distinct from the brief's structured fields. | Schema cap + prompt-rule. |

---

## 5. System prompt (verbatim)

```
You are AIDSTATION's race-week brief synthesizer. The athlete is 14 or fewer days from a target event. Your job is to (1) modify their existing Taper-phase sessions to match race-week emphasis, (2) produce a structured race-week brief covering logistics + kit + fueling + pacing + contingencies + mental prep, and (3) for multi-day events only (expedition AR, stage races, multi-day ultras), produce a structured race plan covering segments + transitions + pacing strategy + fueling strategy + contingencies.

# What you produce

Exactly one tool call to `record_race_week_brief` with three arguments:
- `taper_session_overrides` — list of modified PlanSession records (only sessions you change; pass-throughs stay untouched)
- `race_week_brief` — the structured RaceWeekBrief, always emitted
- `race_plan` — the structured RacePlan, omitted for single-day events

Spec-auto Taper coaching flags (`race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) are stamped by the orchestrator post-synthesis based on session shape + `days_to_event`. You do not emit these. You DO emit `intensity_modulated` (when modulating a Taper session intensity from prior-plan periodization shape due to athlete signal) and `discipline_specific_intensity` (when prescribing race-discipline-specific intensity work in a Taper session).

# Coaching voice (apply to all athlete-facing text fields)

- Direct. Factual. Evidence-grounded.
- No platitudes ("great workout!"), no hype ("crush it!"), no cheerleading ("you've got this!"), no race-day magic, no emoji.
- Tone matches a real endurance coach talking to a serious athlete who has worked hard and earned this race-week.
- Short sentences. Plain English.
- `mental_prep_cues` are evidence-grounded mantras — reference concrete signals (HR, RPE, pace, fueling intake, splits) or concrete cognitive moves ("review your 28-day chronic load if doubt creeps in") rather than emotional framings.

# Taper session modulation

The athlete's Taper sessions are already in `prior_taper_sessions`. Modify only what needs modifying for race-week:

- Sessions at `days_to_event ≤ 2`: light + easy + no novel stimulus. Drop intensity if prior-plan had intensity. Drop volume if prior-plan was substantial. The orchestrator will stamp `pre_race_taper`.
- Sessions at `days_to_event ∈ [3, 5]`: include one moderate-or-easy run/ride with ≥30 min at race-target zone. The orchestrator will stamp `pacing_lock`. Structure: warmup + main_set at race-target HR/pace/RPE + cooldown.
- Sessions at `days_to_event == 7`: include one light easy day positioned as kit-verification day. Session content should be low-cognitive-load (recovery spin, easy walk) so the athlete can focus on kit checks. The orchestrator will stamp `kit_check`.
- One Taper session per week, typically the longest scheduled: structure as a race-rehearsal with full race-day fueling + pacing + kit practice. Adjust duration to 60–120 min (not race-distance; rehearsal, not race). The orchestrator will stamp `race_rehearsal`.
- All Taper cardio sessions ≥ 60 min: cue the athlete to use race-day fueling tier from 2E. The orchestrator will stamp `fueling_practice`.

When the athlete's recent state (3A signals — fatigue markers, ACWR elevated, sleep deficit, lingering illness) suggests pulling back further than the prior-plan Taper structure: modulate intensity downward, emit `intensity_modulated`, and explain the modulation in `session_notes` in two short sentences. Don't argue with the validator; the validator will catch Taper-phase intent violations on retry.

# Race-week brief synthesis

The `race_week_brief` is athlete-facing and consumed by the brief UI surface + Layer 5's clothing/conditions advisor. Fields:

- `goal_outcome` — Plain-language outcome statement derived from 3B `goal_viability`. "Finish" (viable), "Compete mid-pack" (stretch), or "Podium attempt" (only when 3B viability is `'viable'` AND athlete-stated goal in §H.2 supports it). Don't overpromise.
- `pre_race_logistics` — Travel + arrival timing + sleep strategy. Reference §H.2 travel window + athlete sleep baseline. 1–3 sentences.
- `drop_bag_strategy` — Only for events with drop-bag systems; identify what goes in each bag + when it's accessible. Null when not applicable.
- `course_familiarization_notes` — Recon recommendations + critical course sections (technical descents, navigation choke points, water sources). Null when athlete already knows the course or recon isn't feasible.
- `kit_manifest` — Per-locale + per-segment equipment list. Prefer canonical names from layer0.equipment_items (set `layer0_canonical=True`); free-text fallback for mandatory race-rule gear that doesn't resolve to layer0 (set `layer0_canonical=False`). Mark `optional=False` for mandatory race-rule gear + load-bearing items (headlamp for night, safety gear); `optional=True` for nice-to-haves (spare socks, extra battery).
- `kit_check_dates` — At minimum include `event.date - 7` (orchestrator stamps `kit_check` flag on the nearest Taper session). Recommend additional dates at `event.date - 3` and `event.date - 1` for verification of any gear changes.
- `race_day_fueling_plan` — Athlete-facing summary derived from 2E race-day fueling tier. Reference concrete intake targets (carbs per hour, sodium per hour, fluid per hour) drawn from `fueling.cho_g_per_hr_band` etc.
- `pre_race_meal_strategy` — Last 24h fueling cadence + race-morning meal timing. Reference athlete's known GI tolerance (`fueling.gi_tolerance_notes`) when populated.
- `pacing_strategy_summary` — 1–2 sentences. For single-day events, this is the load-bearing pacing guidance; for multi-day events, this is a summary that defers to `race_plan.pacing_strategy` for depth.
- `contingencies` — 3–8 pre-thought failure-mode plans. Per the D6 anchor table, cover the must-have categories for the race format:
  - Any race: GI distress / hydration mistake / mechanical-or-gear-failure.
  - Outdoor AR + ultra: navigation error / sleep-deprivation / weather (cold + heat + rain onset).
  - Stage races: between-stage recovery (sleep, food, mobility).
  - Multi-day: cumulative fatigue + crew-pacing-mismatch.
  - Athlete-specific (add to above): re-aggravation of any 2D active injury; failure of athlete's known weak link per 3A `weak_links`.
- `mental_prep_cues` — 2–5 direct, evidence-grounded mantras. Forbidden phrasings listed in coaching voice section above.

# Race plan synthesis (multi-day events only)

For `event.format ∈ {expedition_ar, stage_race, multi_day_ultra}`, produce `race_plan` covering the race itself. Athletes consume this during the race (typically printed / loaded offline). Fields:

- `race_format` + `locales` — Mechanical from event metadata.
- `segments` — Chronologically ordered segments. For expedition AR: one segment per sport-transition (run → MTB → packraft → climb → etc.); for stage races: one segment per stage; for multi-day ultras with discrete checkpoint-bound efforts: one segment per leg. `segment_index` starts at 0 and is strictly monotonic. `estimated_start_offset_hr` is strictly monotonic (no segment starts before the prior one ends, modulo transition time). `pacing_target` shape per segment — use hard numeric targets (HR / pace / power) where 3A has measurable data for the athlete in that discipline; use RPE + qualitative guidance where 3A is data-thin or where conditions degrade hard targets (night sections, technical terrain, fatigue states past hour N).
- `transitions` — Between adjacent segments. `from_segment_index → to_segment_index = from + 1`. `gear_changes` lists specific swaps (e.g., "swap trail-running pack to MTB pack; change shoes to MTB shoes; switch to hydration vest from handheld"). `is_fueling_window=True` for transitions that are substantial-eating opportunities (typically when stationary > 5 min); False for fast tag-and-go transitions.
- `pacing_strategy` — Overall strategy + per-segment milestones + rationale. `overall_intensity_target` is a 1-sentence anchor (e.g., "Z2 dominant; no Z4 unless emergency call; settle into pacing within first 2 hours"). `night_section_adjustment` is required when `terrain.night_section_present=True` and addresses pacing degradation across night hours (typical: drop one intensity zone; widen RPE band; allow more walking on climbs). `pacing_milestones` are check-in points (e.g., "Hour 6: HR averaging below 145 = pace sustainable"; "Hour 18: take 30 min stationary nap if SpO2 drops").
- `fueling_strategy` — Macro ranges derived from 2E race-day tier. `cho_g_per_hr_low/high` MUST fall inside `fueling.cho_g_per_hr_band`. `night_section_strategy` is required when night sections are present — typical: shift to easier-to-digest carbs (gels over chews; warm liquid calories), increase caffeine cadence per `fueling.caffeine_strategy`, slow sip-rate to prevent GI cooling.
- `contingencies` — 4–12 specific failure-mode plans. Each entry has a concrete trigger (observable signal), action plan (what to do), threshold to invoke (when to act). Examples for AR: GI distress past hour 12 → switch to fat-adapted backup; threshold: persists >30 min and Pepto fails. Navigation error → backtrack to last known checkpoint; threshold: course direction doubt > 10 min. Mechanical failure on MTB → field-fix kit deployment per race rules; threshold: any contact with rim. Cumulative fatigue > expected → drop pace one zone + extend transitions; threshold: HR drift > 8 bpm over 3 hours at constant pace.

# Iteration discipline (when `retries_used > 0`)

On retry, the orchestrator passes `rule_failures` describing what the validator caught. Treat each failure as a hard constraint: `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. Don't argue with the validator; adjust the output to clear the failure while preserving as much of the brief's structural coverage as possible. Severity `blocker` means the brief is unshippable as drafted; severity `warning` means optional adjustment.

Common retry scenarios:
- `taper_phase_intent_violation_blocker` — a Taper override prescribed intensity outside the Taper intensity-distribution band. Modify the offending session to fit the band; restate the rationale in `session_notes`.
- `race_plan_segments_unordered_blocker` — segments out of chronological order. Re-order; ensure both `segment_index` and `estimated_start_offset_hr` are strictly monotonic.
- `fueling_strategy_2e_tier_mismatch_blocker` — `cho_g_per_hr_low/high` outside 2E tier band. Clamp to band; restate in `fueling_strategy.rationale_text`.
- `contingency_anchor_category_missing_warning` — D6 anchor category not covered. Add a contingency entry covering the missing category.
- `kit_manifest_inputs_incomplete` (soft, no retry) — orchestrator emits `data_gap` observation; brief ships as-drafted.

After two retries the cap exhausts and best-effort output ships with an orchestrator-emitted `best_effort_plan` observation — your job on each retry is to maximize the chance of validator-pass while preserving the brief's coaching utility.

# Output discipline

- One tool call per invocation. Do not emit prose outside the tool call.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- Numeric durations always integers (or half-integer where the schema allows).
- Exercise IDs reference Layer 0B canonical IDs; if you use a Tier 2 substitute, populate `substitute_text`; if Tier 3, populate `proxy_origin_id`.
- Equipment items in `kit_manifest`: prefer canonical layer0 names (`layer0_canonical=True`); free-text fallback (`layer0_canonical=False`) only when no canonical exists.
- Don't reference the athlete's wrist injury (or any active injury) by name in athlete-facing text UNLESS the injury directly shapes a contingency or substitution the athlete will see. Routine substitutions stay silent.
```

---

## 6. User prompt (template — Mustache variables)

The user prompt is templated; the orchestrator interpolates per-call variables. The template structure:

```
# Race-week brief request

**Event:** {{event.name}} on {{event.date}} ({{event.format}}; {{event.estimated_duration_hr}} hr estimated for multi-day events)
**Days to event:** {{days_to_event}}
**Event locale:** {{event.locale_id}} ({{event.locales | join: " → "}} for multi-day route)
**Race rules summary:** {{event.race_rules_summary | default: "no specific race-rule gear mandated"}}

# Athlete profile

User ID {{athlete.user_id}}, experience level {{athlete.experience_level}}.
Discipline mix (Layer 2A): {{athlete.discipline_inclusion | as_weighted_list}}.
Active injuries (Layer 2D): {{athlete.active_injuries | as_concise_list}}.
Coaching voice preferences: {{athlete.coaching_voice_preferences | default: "default direct coaching voice"}}.
Travel constraint: {{athlete.travel_constraint | default: "no travel constraint known"}}.
Sleep baseline: {{athlete.sleep_baseline | default: "not populated"}}.

# Current athlete state (3A)

- Aerobic state: {{athlete_state.aerobic_state}}; Strength state: {{athlete_state.strength_state}}.
- Recent trajectory (28d): {{athlete_state.recent_trajectory}}.
- ACWR (7/28): {{athlete_state.acwr_7_28}}.
- Weak links: {{athlete_state.weak_links | default: "none identified"}}.
- Data density: {{athlete_state.data_density}}.

# Periodization phase (3B Taper context)

- Phase: {{phase.name}} (week {{phase.week_in_phase}} of {{phase.total_weeks_in_phase}}).
- Intended volume band: {{phase.intended_volume_band}} hr/wk.
- Intended intensity distribution: {{phase.intended_intensity_distribution | as_dict}}.
- Goal viability (3B): {{phase.goal_viability}}.

# Race-day fueling tier (2E)

- Tier: {{fueling.race_day_tier}}.
- CHO band: {{fueling.cho_g_per_hr_band.low}}–{{fueling.cho_g_per_hr_band.high}} g/hr.
- Sodium target: {{fueling.sodium_mg_per_hr_target}} mg/hr.
- Fluid target: {{fueling.fluid_ml_per_hr_target}} ml/hr.
- Caffeine: {{fueling.caffeine_strategy | default: "no athlete-tested cadence"}}.
- GI tolerance notes: {{fueling.gi_tolerance_notes | default: "no known GI sensitivity"}}.
{{#multi_day}}- Sleep-dep strategy: {{fueling.sleep_dep_strategy | default: "not populated — derive from generic sleep-dep fueling guidance"}}.{{/multi_day}}

# Terrain + environment (2B)

- Surface profile: {{terrain.surface_profile}}.
- Elevation profile: {{terrain.elevation_profile | as_summary}}.
- Weather window (race-week forecast): {{terrain.weather_window | default: "forecast not available yet"}}.
- Night section present (multi-day): {{terrain.night_section_present}}.

# Multi-locale equipment views (2C)

**Event locale ({{event.locale_id}}):** {{equipment.event_locale | as_effective_view}}
{{#multi_day}}**Route locales:** {{equipment.route_locales | as_per_locale_views}}{{/multi_day}}
**Taper-window locales:** {{equipment.taper_locales | as_per_locale_views}}
{{#transit}}**Transit locale ({{equipment.transit_locale.locale_id}}):** {{equipment.transit_locale | as_effective_view}}{{/transit}}

# Prior plan Taper sessions (verbatim, last {{phase.total_weeks_in_phase * 7}} days)

{{#prior_taper_sessions}}
| Date | Day | Sport | Locale | Kind | Duration | Intensity | Notes | Existing flags |
| {{date}} | {{day_of_week}} | {{discipline_name | default: "(rest)"}} | {{locale_name | default: "—"}} | {{kind}} | {{duration_min}} min | {{intensity_summary}} | {{session_notes | truncate: 80}} | {{coaching_flags | join: ", " | default: "—"}} |
{{/prior_taper_sessions}}

{{#retries_used > 0}}
# Validator feedback from prior pass

You produced output that failed validation. Each failure below is a hard constraint for this retry:

{{#rule_failures}}
- **{{rule_name}}** ({{severity}}): {{detail}} Affected: {{affected_session_ids | join: ", "}}. Suggested constraint: {{suggested_constraint}}.
{{/rule_failures}}

Adjust your output to clear every blocker; warnings are optional but acknowledge in `session_notes` if you decline.
{{/retries_used}}

# Your task

Emit one tool call to `record_race_week_brief` with:
1. `taper_session_overrides` — modify only Taper sessions that need race-week adjustment; pass-throughs not in this list stay unchanged. Spec-auto Taper flags (`race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) are stamped by the orchestrator post-synthesis — do NOT emit them.
2. `race_week_brief` — always emit; cover logistics + kit + fueling + pacing + contingencies + mental prep per system prompt + §4 schema.
3. {{#multi_day}}`race_plan` — emit for this multi-day event; cover segments + transitions + pacing strategy + fueling strategy + contingencies per system prompt + §4 schema.{{/multi_day}}{{^multi_day}}`race_plan` — omit (null); this is a single-day event.{{/multi_day}}

Coverage requirements:
- `race_week_brief.contingencies` MUST include the D6 anchor categories applicable to this race format (any race: GI / hydration / mechanical-or-gear-failure; AR + ultra: nav / sleep-dep / weather; stage races: between-stage recovery; multi-day: cumulative fatigue + crew-pacing-mismatch). Add athlete-specific entries per 2D active injuries + 3A weak links.
- `kit_check_dates` MUST include `event.date - 7` at minimum.
- `mental_prep_cues` must be evidence-grounded (no platitudes per coaching voice section).
{{#multi_day}}- `race_plan.fueling_strategy.cho_g_per_hr_low/high` MUST fall inside {{fueling.cho_g_per_hr_band.low}}–{{fueling.cho_g_per_hr_band.high}} g/hr.
- `race_plan.segments` MUST be chronologically ordered (strictly monotonic `segment_index` AND `estimated_start_offset_hr`).
- `race_plan.pacing_strategy.night_section_adjustment` MUST be non-null since `terrain.night_section_present == True`.{{/multi_day}}
```

---

## 7. Sampling configuration

| Parameter | Value | Rationale |
|---|---|---|
| `model` | `claude-sonnet-4-6` | Default per `Layer4_Spec.md` §3.4. |
| `temperature` | 0.2 | Lower than per-phase's 0.3 — race-week brief is structured output with hard schema constraints; deterministic-leaning sampling reduces validator-fail retries. |
| `max_tokens` | 6000 | Per `Layer4_Spec.md` §3.4. Multi-day events with full RacePlan can consume ~3000–5000 output tokens; single-day events ~1500–2500. |
| `extended_thinking.enabled` | True | Required for the cross-product reasoning (multi-locale × multi-segment × multi-hour × athlete-specific). |
| `extended_thinking.budget_tokens` | 5500 | Per D2. Higher than per-phase's 5000; race-week-brief has the broadest reasoning surface in the pipeline. |
| `tool_choice` | `{"type": "tool", "name": "record_race_week_brief"}` | Forced tool call; the model MUST emit `record_race_week_brief` and nothing else. |
| `capped_retries` | 2 | Pattern B default per `Layer4_Spec.md` §5.5. Validator-fail retries are capped; best-effort acceptance after cap. |

---

## 8. Coaching flag emission rules

### 8.1 LLM-emittable coaching flags (cross-phase set per `Layer4_Spec.md` §8.6)

| Flag | Trigger | Where emitted |
|---|---|---|
| `intensity_modulated` | Synthesizer modulated a Taper-session intensity from what the prior-plan periodization shape called for, due to athlete signal (3A fatigue markers, elevated ACWR, athlete-stated illness, recent overreach). | `taper_session_overrides[].coaching_flags` |
| `discipline_specific_intensity` | Synthesizer prescribed race-discipline-specific intensity in a Taper session (e.g., race-pace rehearsal, race-discipline-specific drill work). | `taper_session_overrides[].coaching_flags` |

The session-flag `coaching_flags` enum on `taper_session_overrides` is closed at these two values per the schema in §4.1. Unknown values raise `unknown_coaching_flag_<name>` per `Layer4_Spec.md` §5.5.

### 8.2 Spec-auto Taper coaching flags (handled orchestrator-side per `Layer4_Spec.md` §8.5)

The prompt prescribes the underlying session content; the orchestrator stamps these flags based on session shape + `days_to_event`:

| Flag | Trigger (orchestrator-side) | Prompt's role |
|---|---|---|
| `race_rehearsal` | Phase is Taper AND `days_to_event ≤ 14` AND session is a long session (per orchestrator's per-phase rolling long-session detector). One Taper session per week. | Prompt should structure one weekly Taper long session at 60–120 min with race-day fueling + pacing rehearsal in `session_notes`. |
| `fueling_practice` | Phase is Taper AND session is a long-or-moderate cardio session ≥ 60 min. | Prompt should cue race-day fueling tier from 2E in `session_notes` on all Taper cardio sessions ≥ 60 min. |
| `kit_check` | `days_to_event == 7`. One Taper session (typically a light easy day). | Prompt should structure the `days_to_event == 7` session as a light easy day with `kit_check` framing in `session_notes` referencing the `kit_manifest`. |
| `pacing_lock` | `days_to_event ∈ [3, 5]` AND session is a moderate-or-easy run/ride. One Taper session. | Prompt should structure one Taper session in days_to_event=[3,5] with ≥30 min at race-target zone. |
| `pre_race_taper` | `days_to_event ≤ 2` AND session exists. All remaining Taper sessions. | Prompt should structure all `days_to_event ≤ 2` sessions as mobility, easy spinning, no novel stimulus. |

The contract: **the prompt is the upstream half** — produces session content that lets the orchestrator stamp the correct flags. The validator does NOT check that spec-auto flags would be stamped correctly (that's the orchestrator's responsibility); the validator only checks Taper-phase intent (volume + intensity distribution).

### 8.3 Observations (LLM-emitted exception only)

Per `Layer4_Spec.md` §8.7, all observations are orchestrator-computed EXCEPT `opportunity`. The prompt may emit `opportunity` observations via the `opportunities[]` field on the tool output. Use sparingly — only when a coaching opportunity is materially distinct from the brief's structured fields. Example: "Andy's MTB pacing data is thin; consider a 30-min cruise on the actual race-course Tuesday for pacing calibration before the long Wednesday session."

The orchestrator separately emits:
- `data_gap` — when §4.5 soft-fail (`kit_manifest_inputs_incomplete`) fires.
- `best_effort_plan` — when validator retry cap exhausts.
- `intensity_modulated` (observation-bubble) — when the LLM emits `intensity_modulated` session flag.

---

## 9. Coaching guidance

### 9.1 Taper-session modulation policy

The athlete's Taper sessions are already in place from the originating `plan_create`. The brief refines them, doesn't restructure them. Modulation decision tree:

**Anchor signals for modulation:**
1. **3A fatigue / overtrained state** → pull intensity down one tier; emit `intensity_modulated`; reference the signal explicitly in `session_notes`.
2. **3A active illness flag** → drop the affected sessions to rest; emit `intensity_modulated` (whole-week-modulation per the §8.6 broadened trigger); reference illness in `session_notes` without medicalizing.
3. **3A elevated ACWR (> 1.0 in Taper week)** → this is unusual; Taper should be dropping ACWR. Investigate via 3A `data_density` — if rich, likely real and warrants pullback; if sparse, may be data artifact and warrants a watch-and-see note.
4. **Athlete-stated travel disruption** → adjust session locale + intensity + duration to match the disruption window; emit `intensity_modulated` only if intensity changes meaningfully.

**Anchor signals that do NOT modulate:**
- 2D injury flags that the prior-plan Taper already accommodates (no new modulation needed).
- 3A recent-trajectory `'declining'` if it's already reflected in the Taper structure.

### 9.2 Hybrid pacing depth (per D5 — Andy's Pick 2)

For each pacing surface (`race_week_brief.pacing_strategy_summary`, `race_plan.segments[].pacing_target`, `race_plan.pacing_strategy.pacing_milestones`), decide hard-numeric-vs-RPE per the data-density rule:

**Use hard numeric targets (HR, pace, power) when:**
- 3A `data_density ∈ {'rich', 'moderate'}` AND the athlete has training data in this discipline AND conditions are stable (single-day road events; short single-day trail races; well-trained Olympic-distance triathlon).
- The discipline supports hard targets natively (cycling power meters, running pace via GPS in flat terrain, swimming pace via lap counter).

**Use RPE + qualitative heuristic when:**
- 3A `data_density ∈ {'sparse', 'very_sparse'}` (data thin; hard targets unreliable).
- Conditions degrade hard targets early — night sections in expedition AR, technical mountain terrain, hot/humid races, fatigue states past hour N in multi-day events.
- The discipline doesn't support hard targets natively — nav-puzzle segments, technical descents, packraft sections with variable water level, abseiling.

**Hybrid within a single race plan is expected:** an expedition AR plan may have HR targets for the early MTB segment, RPE for the technical climbing segment, and "Z2 dominant; settle below RPE 5" for the night running section.

### 9.3 Mixed contingency depth (per D6 — Andy's Pick 3)

The D6 anchor table guarantees coverage of must-have categories; the LLM expands within each + adds athlete-specific.

**Anchor categories (must be covered when applicable):**

| Race format | Anchor categories |
|---|---|
| Any | GI distress, hydration mistake, mechanical-or-gear-failure |
| Single-day road race | Pacing-too-aggressive-early, late-race-bonk, weather (heat or rain) |
| Single-day trail / outdoor | + navigation error (when course not clearly marked), surface-condition surprise |
| Expedition AR | + sleep-deprivation, weather (cold + heat + rain onset), wildlife / hazards per terrain |
| Stage race | + between-stage recovery (sleep, food, mobility), cumulative fatigue across stages |
| Multi-day ultra | + cumulative fatigue, crew-pacing-mismatch, night-section pacing degradation |

**Athlete-specific expansion:**
- 2D active injuries → contingency for re-aggravation of each active injury (e.g., for Andy's wrist: "Wrist re-aggravation during packraft paddle or climbing section"). Trigger: specific observable signal (pain ≥ 6/10 OR strength loss); action: switch grip / drop affected sub-segment / consult per race medical rules; threshold: persists > 15 min after rest-position attempt.
- 3A `weak_links` → contingency for the weak link emerging under race fatigue (e.g., "Right hip flexor tightens past hour 12" → action: 5-min stretch routine; threshold: stride length drops perceptibly OR pain ≥ 4/10).
- `fueling.gi_tolerance_notes` → contingency for known GI failure modes (e.g., athlete-tested intolerance to specific products).

**Multi-day-only contingencies (in `race_plan.contingencies[]`, separate from `race_week_brief.contingencies[]`):**
- Sleep-deprivation cascade — typical multi-day failure mode where decision-quality degrades + pace falls + fueling errors compound; trigger: ≥ 2 of {missed calorie target by 30%, navigational hesitation > 10 min, RPE/HR decoupling}; action: 20-min stationary nap + 200 mg caffeine + warm liquid calories; threshold: invoke once and re-evaluate.
- Mechanical / gear failure where field-fix is bounded — trigger: any contact between MTB rim and rock OR drivetrain function loss; action: stop, assess, deploy field-fix kit per race rules (tube/CO2/multi-tool/chain link); threshold: function-restored vs unrideable decision in < 10 min.

### 9.4 Kit manifest resolution policy (per D9)

For each `kit_manifest[]` entry:

1. **Check layer0.equipment_items** (joined via 2C equipment views for available locales). If the item resolves to a canonical row: emit with `item` = canonical name + `layer0_canonical=True`.
2. **Free-text fallback** when the item is mandatory by race rules but doesn't resolve to layer0 (e.g., "Petzl Tikkina headlamp w/ ≥ 150 lumens"): emit with `item` = athlete-readable description + `layer0_canonical=False`. The orchestrator aggregates these into a `data_gap` observation per `Layer4_Spec.md` §4.5 row 7.
3. **`purpose` field**: state why the item is on the list. Examples: "mandatory by race rules" / "nutrition transport — race-day carb intake" / "safety — required for night segments" / "thermal regulation — forecast low temp 4°C".
4. **`optional` flag**: False for race-mandatory + load-bearing (headlamp, hydration vest, safety whistle); True for nice-to-haves (spare socks, extra battery pack, anti-chafe stick).

### 9.5 Mental prep cues — evidence-grounded only (per D12)

Allowed:
- "Review your 28-day chronic load if doubt creeps in — you've done the work."
- "First 90 minutes: settle into Z2; let HR tell you you're on pace."
- "On the long climb: count cadence in 4-minute blocks; that's a strong rhythm."
- "If GI flares: switch to backup fueling within 30 minutes — don't grit through it."
- "Night section: drop one zone; widen the RPE band; walking the climbs is on-plan."

Forbidden (will surface in coaching review):
- "You've got this!" / "Crush it!" / "Believe in yourself!"
- "Trust the process" (vague — what process? specific to this race?)
- "Race day magic" / any "magic"-based phrasing.
- "Mind over matter" (false dichotomy).
- "Leave it all on the course" / "No regrets" — vague, hype-adjacent.

Mantras reference: concrete signals (HR, pace, RPE, cadence), concrete cognitive moves (review chronic load, check fueling intake, count cadence), or concrete decision rules ("if X then Y").

### 9.6 Race-day fueling plan derivation

`race_week_brief.race_day_fueling_plan` is the athlete-facing summary; `race_plan.fueling_strategy` (multi-day) is the structured detail.

**Derivation from 2E:**
- `race_day_fueling_plan` cites carb-per-hour target (use the upper half of `fueling.cho_g_per_hr_band` for high-intensity races; the band midpoint for moderate-intensity multi-day events; lower half for fat-adapted athletes per `fueling.race_day_tier`).
- Sodium target from `fueling.sodium_mg_per_hr_target`, adjusted for forecast heat per 2B `terrain.weather_window`.
- Fluid target from `fueling.fluid_ml_per_hr_target`, adjusted for terrain heat / humidity per 2B.
- Caffeine cadence from `fueling.caffeine_strategy` — only deploy if the athlete has tested the cadence; never introduce caffeine novel to race-day.
- Pre-race-meal strategy: reference athlete's known tolerance (`fueling.gi_tolerance_notes`); typical: low-fiber + moderate-carb meal 3 hours pre-start; race-morning top-up 90 min pre-start.

**Multi-day fueling strategy (`race_plan.fueling_strategy`):**
- `cho_g_per_hr_low/high` MUST fall inside `fueling.cho_g_per_hr_band` (validator enforces).
- `night_section_strategy` required when `terrain.night_section_present=True`. Typical: shift to easier-to-digest carbs (gels over chews; warm liquid calories), increase caffeine cadence per athlete-tested deployment, slow sip-rate.
- `sleep_dep_strategy` (in `race_plan.fueling_strategy.night_section_strategy` or separate field): per `fueling.sleep_dep_strategy` from 2E when populated; otherwise generic — frequent small carb intakes + caffeine cadence + warm liquid calories during low-temp night hours.

---

## 10. Edge cases

| # | Case | Handling |
|---|---|---|
| 1 | Single-day event with no race rehearsal opportunity (athlete is traveling all week, no equipment access) | Modify the Taper week to all easy mobility + race-pace mental rehearsal (visualization cues in `mental_prep_cues`); `race_rehearsal` orchestrator-stamp won't fire; `race_week_brief.pre_race_logistics` references the travel constraint. No retry; this is a known degraded path. |
| 2 | Multi-day event with `terrain.weather_window` unpopulated (forecast not yet available at days_to_event=14) | `race_week_brief.contingencies` covers weather contingencies generically (cold + heat + rain onset) rather than forecast-specific; brief notes "Weather forecast not yet available; specific kit decisions will refine inside days_to_event=5." `race_plan.pacing_strategy.rationale_text` references the forecast gap. |
| 3 | Athlete in `'overtrained'` state at days_to_event=10 | Pull back Taper intensity aggressively: drop all Taper-week long sessions to easy + emit `intensity_modulated` on each modified session; `goal_outcome` may shift from "Compete" to "Finish" per 3B re-eval — but Layer 4 does NOT re-derive `goal_viability`, it surfaces 3B's call; `mental_prep_cues` references conserve-and-execute framing. |
| 4 | Active illness flag in 3A (e.g., URI symptoms) | Treat as hard-pullback signal; drop all Taper sessions in days_to_event ≤ 3 to rest or mobility; emit `intensity_modulated` on every modified session; `mental_prep_cues` doesn't reference illness directly; `contingencies` adds "Illness flare-up during race" entry. |
| 5 | Multi-day event where one route locale's 2C equipment view is missing (data gap) | `kit_manifest` for that locale falls back to free-text + `layer0_canonical=False`; orchestrator emits `data_gap` observation; brief surfaces "Equipment data for [locale] is thin; verify gear in person on arrival" in `pre_race_logistics`. |
| 6 | Athlete's race-rehearsal Taper session falls on a travel day | Compress the rehearsal to a 30–45 min light easy run + cue race-day fueling + mental rehearsal of race-day logistics + kit verification; emit `intensity_modulated` if the prior-plan session was longer/harder. |
| 7 | `days_to_event == 1` (athlete fires brief manually the day before) | All `pre_race_taper` framing; no race-rehearsal modification (too late); `race_week_brief.pre_race_meal_strategy` is the load-bearing output; emit `opportunity` observation noting "Brief generated <24h pre-race; future briefs at days_to_event=14 will have more lead time." |
| 8 | Multi-day event where 3B `goal_viability='unrealistic'` | `goal_outcome="Survive — secondary goal: gather race intelligence for next year"`; tone shifts toward damage-control + learning; contingencies emphasize cumulative fatigue + safety; mental_prep_cues references "today's race is a long training day — every checkpoint is a win" (evidence-grounded — references concrete behavior). |
| 9 | Race has mandatory gear list in `event.race_rules_summary` that exceeds the athlete's equipment registry | `kit_manifest` emits all mandatory items as free-text + `optional=False` + `layer0_canonical=False`; orchestrator emits `data_gap` observation; `contingencies` adds "Pre-race kit verification finds missing mandatory gear" with action plan "Source via [race vendor / local sport store / friend loan]." |
| 10 | Athlete's prior Taper window has fewer sessions than expected (e.g., gap due to travel or illness) | Pass-through the existing sessions; do not synthesize new sessions; `race_week_brief.pacing_strategy_summary` notes "Taper has been thinner than ideal; pace conservative in first third of race to compensate." `opportunity` observation: "Future plan_refresh should densify the Taper week if practicable." |
| 11 | Multi-day event with > 12 segments (large adventure race) | Cap `race_plan.segments[]` at 12 entries per schema; group sub-segments into logical units (e.g., "Trail running blocks 1+2+3" as one segment with terrain_notes covering all three sub-blocks). `coaching_notes` for the combined segment captures sub-block transitions. |
| 12 | Stage race with ≤ 4 stages | Render each stage as a `segments[]` entry; `transitions[]` covers between-stage recovery windows (typically 6–18 hours stationary); `is_fueling_window=True` on every transition; `pacing_strategy.pacing_milestones` includes between-stage recovery check-ins (sleep quality, RPE next morning). |
| 13 | Athlete fires the brief at days_to_event=14 then again at days_to_event=7 (refresh case) | Both fires produce a full brief from-scratch (no incremental update mechanism in v1); the second fire's cache key differs (Taper window has likely changed; midnight-UTC rollover invalidates anyway). v1 accepts the cost; future spec may add a brief-diff renderer. |
| 14 | Event in a discipline not in 2A `discipline_inclusion` (data hygiene flag) | Defensive fallback: synthesize the brief best-effort treating the race discipline as the discipline-of-the-day; `data_hygiene` observation emitted orchestrator-side per `Layer4_Spec.md` §8.7; `mental_prep_cues` notes the discipline gap. |
| 15 | `terrain.night_section_present=True` but `fueling.sleep_dep_strategy` not populated | Brief generates a generic sleep-dep fueling strategy in `race_plan.fueling_strategy.night_section_strategy` (frequent small carbs + caffeine + warm liquid calories); emit `opportunity` observation noting "2E sleep-dep strategy not populated — future plan should populate." |

---

## 11. Validator + retry contract

### 11.1 Validator rules applied (per `Layer4_Spec.md` §5.4 race-week-brief sub-bullet)

| Rule | Severity | Detail |
|---|---|---|
| `taper_phase_intent_violation` | Blocker | Any `taper_session_overrides[]` session with intensity outside `phase.intended_intensity_distribution` band OR duration outside `phase.intended_volume_band` per-session allocation. |
| `kit_manifest_inputs_incomplete` | Warning (soft, no retry) | Any `kit_manifest[]` items with `layer0_canonical=False`. Orchestrator emits `data_gap` observation; brief ships as-drafted. |
| `race_plan_segments_unordered` | Blocker (multi-day only) | `segments[]` not strictly monotonic by `segment_index` OR `estimated_start_offset_hr`. |
| `race_plan_transitions_misaligned` | Blocker (multi-day only) | Any `transitions[].from_segment_index → to_segment_index` not equal to `from + 1`. |
| `fueling_strategy_2e_tier_mismatch` | Blocker (multi-day only) | `cho_g_per_hr_low/high` outside `fueling.cho_g_per_hr_band`. |
| `fueling_strategy_macro_range_inverted` | Blocker (multi-day only) | `cho_g_per_hr_low > cho_g_per_hr_high`. |
| `contingency_anchor_category_missing` | Warning | A D6 anchor category for the race format not covered in `race_week_brief.contingencies[]`. |
| `kit_check_dates_missing_anchor` | Warning | `kit_check_dates[]` does not include `event.date - 7`. |
| `night_section_adjustment_missing` | Warning (multi-day only) | `terrain.night_section_present=True` but `race_plan.pacing_strategy.night_section_adjustment` is null. |
| `session_id_override_not_found` | Blocker | A `taper_session_overrides[].session_id_to_override` does not match any `prior_taper_sessions[].session_id`. |
| `coaching_flag_unknown` | Blocker | A `coaching_flags[]` value outside the closed 2-flag enum. |
| `mental_prep_cue_forbidden_phrasing` | Warning | A `mental_prep_cues[]` entry matches a forbidden phrasing pattern per §9.5 (case-insensitive). |

### 11.2 Retry context rendering (per D10)

On retry pass:

```
# Validator feedback from prior pass

You produced output that failed validation. Each failure below is a hard constraint for this retry:

- **{rule_name}** ({severity}): {detail} Affected: {affected_session_ids}. Suggested constraint: {suggested_constraint}.
```

Example suggested_constraints:
- `taper_phase_intent_violation`: "Reduce intensity_summary to 'easy' or 'moderate'; current 'hard' violates Taper intensity distribution band."
- `race_plan_segments_unordered`: "Re-order segments so segment_index is strictly monotonic from 0; estimated_start_offset_hr must also be strictly monotonic."
- `fueling_strategy_2e_tier_mismatch`: "Clamp cho_g_per_hr_low/high to inside the 2E race-day tier band {low}–{high} g/hr."

### 11.3 Cap-hit behavior

After 2 retries, the cap exhausts and the orchestrator accepts best-effort output:
- `Layer4Payload.validator_results[-1].accepted=True` + `rule_failures` retains the unresolved failures as `warning` severity.
- `Layer4Payload.notable_observations` gains a `best_effort_plan` entry with `elevates_to_hitl=True` per `Layer4_Spec.md` §8.7.
- Brief surfaces with the unresolved warnings as a UI flag.

---

## 12. Test scenarios

Each scenario is a triplet `(inputs, expected_LLM_behavior, validator_outcome)`. Scenarios prefix `PSS-RWB-NN` (Prompt Synth Spec — Race Week Brief — NN). Numbering aligns with `Layer4_Spec.md` §13 where overlapping; new scenarios use the next available index.

| # | Scenario | Expected LLM behavior | Expected validator outcome |
|---|---|---|---|
| PSS-RWB-01 | Andy + Pocket Gopher Extreme 2026 (48-56h expedition AR; days_to_event=14; 3A `fit`; data_density=rich for trail running, moderate for MTB, sparse for packrafting + climbing) | Full brief + RacePlan; segments span run/MTB/packraft/climb/abseil; pacing_target hard-numeric for run (HR + pace), hard-numeric for MTB (HR), RPE for packraft + climb + abseil; kit_manifest includes Tikkina headlamp + SPOT/inReach as mandatory free-text + race-vest as canonical; contingencies cover all anchor categories + wrist injury + sleep-dep cascade + cumulative fatigue; race_day_fueling_plan derived from 2E. | Accepted first pass. |
| PSS-RWB-02 | Single-day road marathon; days_to_event=14; athlete `fit`; data_density=rich; pre-race forecast 18°C / cloudy | Single-day brief; race_plan=None; pacing_strategy_summary uses hard pace targets (e.g., "Z2 dominant target pace 5:15/km for first 25K; HR sub-160"); kit_manifest minimal (race-day kit; no AR gear); contingencies cover anchor 3 + pacing-too-aggressive-early + late-race-bonk. | Accepted first pass. |
| PSS-RWB-03 | Single-day trail 50K; days_to_event=10; athlete `fit`; data_density=moderate for running; technical terrain | Single-day brief; race_plan=None; pacing_strategy_summary hybrid (HR target for first 20K + RPE-based on technical descents); kit_manifest includes trail shoes + hydration vest + handheld backup; contingencies cover anchor 4 + nav-error + surface-condition surprise. | Accepted first pass. |
| PSS-RWB-04 | Multi-day stage race (3 stages over 3 days); days_to_event=12; athlete `fit`; data_density=rich | Multi-day brief; race_plan.segments=3 (one per stage); transitions=2 (between stages, is_fueling_window=True with 12-18h durations); pacing_target hard-numeric for each stage; between-stage recovery contingencies; pacing_milestones include stage-2-morning RPE check. | Accepted first pass. |
| PSS-RWB-05 | Multi-day ultra (24h race, single locale); days_to_event=14; athlete `fit`; night-section present | Multi-day brief; race_plan.segments organized by intensity-window (first 6h moderate, 6-12h easy, 12-18h easy + walking climbs, 18-24h survival); pacing_target HR-based early + RPE-based after hour 12; night_section_adjustment populated (drop one zone + widen RPE band); fueling_strategy.night_section_strategy populated. | Accepted first pass. |
| PSS-RWB-06 | Andy's case + 3A `overtrained` state at days_to_event=12 | Pull Taper intensity back aggressively; drop both Wednesday + Saturday long sessions to easy; emit `intensity_modulated` on each modified session; goal_outcome may shift from "Compete mid-pack" to "Finish" if 3B viability has flipped; mental_prep_cues references conserve-and-execute. | Accepted first pass. |
| PSS-RWB-07 | Athlete has active illness flag in 3A at days_to_event=8 | Drop all Taper sessions in days_to_event ≤ 3 to rest or mobility; emit `intensity_modulated` whole-week; mental_prep_cues doesn't reference illness directly; contingencies add "Illness flare-up during race" entry. | Accepted first pass. |
| PSS-RWB-08 | Multi-day AR with 1 of 5 route locales missing 2C equipment view | kit_manifest for that locale emits free-text + `layer0_canonical=False`; orchestrator emits `data_gap` observation; brief surfaces "Equipment data for [locale] is thin; verify gear in person on arrival" in pre_race_logistics. | Accepted with warning (kit_manifest_inputs_incomplete soft). |
| PSS-RWB-09 | Validator retry: first pass emits a `taper_session_overrides[]` with intensity_summary='hard' on a `days_to_event=2` session | Validator rejects with `taper_phase_intent_violation_blocker`; retry passes with intensity_summary='easy'. | Accepted second pass. |
| PSS-RWB-10 | Validator retry: first pass emits race_plan.fueling_strategy.cho_g_per_hr_high=110 but 2E tier band is 60-90 | Validator rejects with `fueling_strategy_2e_tier_mismatch_blocker`; retry clamps to 90. | Accepted second pass. |
| PSS-RWB-11 | Validator retry: first pass emits AR contingencies missing nav-error category | Validator emits `contingency_anchor_category_missing_warning`; retry adds nav-error contingency. | Accepted second pass. |
| PSS-RWB-12 | Cap-hit: 2 retries fail to clear taper_phase_intent_violation | Best-effort acceptance; `best_effort_plan` observation emitted with `elevates_to_hitl=True`; brief ships with unresolved warnings. | Accepted at cap with best-effort flag. |
| PSS-RWB-13 | Andy + Pocket Gopher Extreme + days_to_event=14 + race-week forecast unavailable (`terrain.weather_window` empty) | Contingencies cover weather generically (cold + heat + rain onset); brief notes "Weather forecast not yet available; specific kit decisions will refine inside days_to_event=5"; race_plan.pacing_strategy.rationale_text references the forecast gap. | Accepted first pass. |
| PSS-RWB-14 | Athlete fires brief manually at days_to_event=1 | All `pre_race_taper` framing; no race-rehearsal modification; pre_race_meal_strategy is the load-bearing output; emit `opportunity` observation about lead-time. | Accepted first pass. |
| PSS-RWB-15 | Multi-day event with 3B `goal_viability='unrealistic'` | goal_outcome="Survive — secondary goal: gather race intelligence for next year"; tone shifts toward damage-control + learning; contingencies emphasize cumulative fatigue + safety; mental_prep_cues references "today's race is a long training day". | Accepted first pass. |
| PSS-RWB-16 | Race rules mandate gear not in athlete's equipment registry (e.g., "GPS-capable watch with ≥ 24h battery" not in their kit) | kit_manifest emits the item as free-text + `optional=False` + `layer0_canonical=False`; contingencies add "Pre-race kit verification finds missing mandatory gear" with action plan; orchestrator emits `data_gap`. | Accepted with warning. |
| PSS-RWB-17 | Athlete's prior Taper window is thinner than expected (5 sessions over 14 days due to travel) | Pass-through existing sessions; do not synthesize new sessions; brief notes "Taper has been thinner than ideal; pace conservative in first third of race"; opportunity observation about future plan_refresh densifying Taper. | Accepted first pass. |
| PSS-RWB-18 | Schema-violation retry: first pass emits 13 segments in race_plan | Schema caps at 12; the LLM tool call fails schema validation pre-validator (Anthropic SDK rejects); retry combines segments 11+12 into one with combined terrain_notes. | Accepted second pass after schema-driven retry. |
| PSS-RWB-19 | Athlete-specific 2D wrist injury at days_to_event=14 (Andy) | Contingencies include "Wrist re-aggravation during packraft paddle or climbing section" with specific trigger + action + threshold; Taper strength session prescribes fist-position pushups or substitutes; kit_manifest may add wrist brace as optional. | Accepted first pass. |
| PSS-RWB-20 | Multi-day event + 3A `data_density='very_sparse'` | Pacing_target defaults to RPE across all segments per D5 fallback; brief notes "Recent training data is thin; race pacing will rely on subjective effort calibration."; opportunity observation about populating 3A inputs for future plans. | Accepted first pass. |

---

## 13. Performance budget

Per `Layer4_Spec.md` §11.1 + §11.2 + §11.3:

**Latency (end-to-end including extended thinking + tool call):**
- Single-day events: p50 ~8s, p95 ~12s.
- Multi-day events: p50 ~12s, p95 ~18s.
- Cap-hit retry (2 retries): adds ~16-24s in worst case.

**Token budget per invocation:**
- Input tokens: ~4500-6500 (full payloads + Taper window verbatim; multi-locale 2C views push the high end for multi-day).
- Extended thinking budget: 5500 (per D2).
- Output tokens: ~1500 (single-day) to ~5000 (multi-day with full RacePlan + 12 segments + 12 contingencies + extensive transitions).
- Total per call: ~5500-12000 tokens (input + thinking + output).

**Cost per invocation (Sonnet 4.6 pricing):**
- Single-day: ~$0.08-0.12 typical; ~$0.18 worst-case with cap-hit retries.
- Multi-day: ~$0.15-0.22 typical; ~$0.35 worst-case with cap-hit retries.

**Cache hit rate expectation:**
- Cache invalidates daily at midnight UTC per `Layer4_Spec.md` §9.3 (output is `days_to_event`-anchored).
- Each day's brief is effectively a fresh call; cache hit rate ≈ 0% over multi-day windows.
- Within-day re-fires (e.g., athlete views brief twice on same day) hit cache with rebinding per §9.4.

**Cumulative ceiling (per athlete per race-event):**
- 14 daily brief regenerations × ~$0.18 average = ~$2.50 per race-event.
- Race-week-brief is a high-value low-frequency entry — cumulative cost is small relative to plan_create ($0.50-1.10 per fire) but per-call cost is highest of all four entries.

---

## 14. Open items + gut check

### 14.1 Open items (defer to telemetry / future spec)

- **Brief-diff renderer for incremental re-fires.** Currently each daily brief regeneration is from-scratch; an incremental "what's changed since yesterday's brief" surface would reduce athlete cognitive load. Defer until brief UI is built + telemetry shows daily-regen burden.
- **Per-segment athlete check-in shape (RacePlan post-pass).** `Layer4_Spec.md` §7.14 explicitly defers per-segment actual-time logging to session 2 of RacePlan spec; the brief produces the plan, the post-race surface logs against it. Out of v1 scope.
- **Race-week refresh integration with D-64 NL parser.** When the athlete fires a race-week NL refresh ("I'm tired today, drop tomorrow's race-rehearsal"), the brief's `taper_session_overrides[]` interacts with `plan_refresh` T1's output. Coordination contract: the more-recent fire wins per `Layer4_Spec.md` §7.11 per-day pointer; brief's Taper overrides supersede T1's same-date overrides if brief fires after T1. Confirm during D-64 implementation.
- **Multi-day RacePlan `pacing_milestones` validation.** Currently no validator rule on milestone count or content; future may add "at least one milestone per 4 hours of race duration" rule to ensure milestones are practically actionable.
- **Kit_manifest `layer0_canonical=False` items aggregation across athletes.** Telemetry should track which mandatory gear items frequently land as free-text — those are candidates for `layer0.equipment_items` additions per the catalog migration plan. Implementation-time hook.
- **Athlete-stated goal override.** Currently `goal_outcome` defers to 3B `goal_viability`. Future may allow athlete to override (e.g., "I want to attempt podium even though 3B says 'stretch'"); spec amendment needed.
- **Forecast-driven kit refinement.** When `terrain.weather_window` populates inside days_to_event=5 (forecast horizon narrows), kit_manifest should refine — currently each brief regen produces a fresh manifest, but no diff signal. Defer to brief-diff renderer.

### 14.2 Gut check

**What's right about this prompt:**
- Coverage is comprehensive: all 5 Layer 2 payloads + 3A + 3B + 2E + Taper window + event metadata are wired through to athlete-facing output.
- Three-output tool call lets the LLM cross-check kit_manifest vs RacePlan.segments + fueling_strategy vs race_day_fueling_plan vs 2E tier in one reasoning pass.
- The single-day vs multi-day branch is structurally additive (RacePlan extension); shared coaching surface lives in RaceWeekBrief; unified file kept narrow.
- Hybrid pacing depth + mixed contingency depth match the actual data-availability picture: leverage hard numbers when they're real, fall back to heuristics when they're not.
- Spec-auto Taper flag handoff is clean: prompt produces session content; orchestrator stamps the 5 spec-auto flags; no double-emission risk.
- The §9.5 forbidden-phrasing list is explicit + tied to CLAUDE.md voice; mental_prep_cues won't drift into cheerleading.

**Risks:**
- **Token budget tight on multi-day with 12 segments + 12 contingencies + extensive transitions.** Output budget is 6000 max_tokens; in worst case (12 segments × ~150 tokens each + 12 contingencies × ~50 tokens + transitions × 11 × ~80 tokens + structured fueling/pacing strategies + RaceWeekBrief base + Taper overrides) we're at ~5000-5800 output tokens. Headroom is thin; future revisions may need to cap RacePlan.segments at 10 or compress transition descriptions.
- **Mental_prep_cues forbidden-phrasing list is incomplete.** Other hype patterns exist that the regex won't catch (e.g., "Go get it!", "This is your moment!"). Validator-side phrasing detection is non-programmatic per Rule #14; relies on coaching review surface. Telemetry should track flagged cues post-launch.
- **Andy's Pocket Gopher Extreme 2026 is the canonical test case.** The prompt is tuned around expedition AR with multi-sport segments + wrist injury + sleep-dep. Single-day events have been considered but not stress-tested against the same depth of reasoning.
- **Multi-locale 2C bundle parsing complexity.** Race-week-brief is the only entry consuming multi-locale 2C views; the prompt expects the orchestrator to surface them in `equipment.event_locale` + `equipment.taper_locales[]` + `equipment.transit_locale`. If the orchestrator fails to populate or normalizes incorrectly, brief output degrades silently.
- **D-64 race-week NL refresh interaction is deferred.** If the athlete fires "drop tomorrow's race-rehearsal" via D-64 NL refresh during race week, the brief's Taper overrides + T1 refresh's overrides may conflict; per-day pointer wins, but coaching narrative consistency isn't guaranteed.
- **Spec-auto flag stamping timing.** If the orchestrator stamps `race_rehearsal` on a session that the brief intended NOT to be a rehearsal (because the brief shifted the rehearsal to a different day), there's a mismatch. The contract assumes orchestrator stamping is deterministic per `Layer4_Spec.md` §8.5; needs implementation verification.

**What might be missing:**
- A `pre_race_warm_up_protocol` field — race-day specific warm-up routine (15-min cardio activation + dynamic mobility + race-pace touches). Defer to v2; for v1 captured in `pre_race_meal_strategy` + `pacing_strategy_summary` as part of the race-morning sequence.
- A `post_race_immediate_action` field — first 30 min post-race recovery protocol (fueling, fluids, mobility, ice). Defer to v2 or to `plan_refresh` post-race entry.
- A `race_morning_decision_tree` — concrete "if X then Y" structure for race-morning calls (weather changes, illness, gear failure pre-start). Defer to v2.
- A `crew_coordination_notes` field for multi-day events with crew support — what info crew needs at each transition. Defer to v2.

**Best argument against the unified-file pick (Pick 1 = a):**
Andy's Pick 2 (T1/T2 file scope) chose two files over the architect's unified recommendation precisely because T2's longer scope had distinct guidance that didn't fit cleanly under conditional logic with T1. Race-week-brief multi-day vs single-day has the same structural gap — multi-day RacePlan adds segment + transition + night-section reasoning that single-day doesn't have. If the conditional branch at the RacePlan slot in §6 becomes large (e.g., >100 lines of multi-day-only coaching guidance inside the Mustache block), the unified file's coherence degrades + the case for splitting strengthens. Telemetry post-launch should measure: what fraction of race-week-brief fires are multi-day vs single-day, and how often the multi-day-only guidance fires for single-day events as dead-prompt-content. If multi-day >30% of fires AND the conditional block grows >150 lines, revisit the split decision.

**Best argument against the hybrid pacing depth pick (Pick 2 = a):**
Hybrid is a coaching-judgment-by-data-density rule; it gives the LLM discretion on when to use hard targets vs RPE. The risk is inconsistency across briefs — same athlete + similar race may get HR targets one race and RPE the next based on subtle data-density shifts. A stricter rule ("always RPE for races > 6 hours; always HR for races ≤ 6 hours") would be more predictable but loses leverage on 3A's data. v1 accepts the discretion; telemetry should track pacing-target-shape distribution across briefs to detect drift.

**Best argument against the mixed contingency pick (Pick 3 = a):**
The D6 anchor table is opinionated about must-have categories. If a race format we haven't anticipated emerges (e.g., a packrafting-only multi-day race with unique failure modes), the anchor table won't cover it; the LLM will produce contingencies but the must-have-coverage guarantee fails silently. v1 accepts; future may add a "race-format taxonomy" pattern where the anchor table is data-driven rather than hardcoded.

---

**End of prompt body.** 5 of 5 in the Layer 4 prompt-body arc. v1.
