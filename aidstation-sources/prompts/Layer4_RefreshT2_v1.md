# Layer 4 — Plan Refresh T2 Synthesizer Prompt Body (D-64)

**Prompt name:** `Layer4_RefreshT2`
**Entry point:** `llm_layer4_plan_refresh` with `tier='T2'` (`Layer4_Spec.md` §3.2)
**Pattern:** B (single LLM call + deterministic validator; no seam reviewer; no phase decomposition)
**Caller:** D-64 athlete-initiated 7-day refresh (`Plan_Refresh_D64_Design_v1.md` §3.2)
**Status:** v1 — draft
**Date:** 2026-05-17
**Position in arc:** Fourth-and-a-half of 5 prompt bodies — companion to `Layer4_RefreshT1_v1.md` shipped same session (1 prompt body left: `Layer4_RaceWeekBrief`).

---

## Source decisions (this session, Andy 2026-05-17)

Identical Andy-level picks as `Layer4_RefreshT1_v1.md` (file scope = two files per tier; NL intent weighting = strong-bias toward intent; continuity = match surrounding shape unless triggered). Per-decision differences from T1 are flagged inline.

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Tool-use** (`record_refresh_sessions`); single tool, single call; the `sessions` argument is a `list[PlanSession]` (0..14 entries for T2 — up to 2 per day × 7 days). Strict JSON schema with `additionalProperties: false` at every nesting level. | Same tool name as T1; the schema differs only in `maxItems` (14 for T2 vs 4 for T1). |
| D2 | Extended thinking budget | **~4500 tokens.** | Larger than T1's 3000 — T2 covers a full week and is responsible for the week's intensity distribution + volume shape, which are combinatorial across 7 days. Smaller than per-phase's 5000 because T2 inherits a periodization shape from a freshly-re-run 3B (no phase decomposition needed; weekly placement is the load-bearing decision). |
| D3 | Input format | **Full payloads verbatim** for 3A + 3B + 2A + 2D + 1 + `request` + `parsed_intent`. Layer 2B/2C/2E only present when `parsed_intent` triggered their re-run; full when present. `prior_plan_session_window` rendered hybrid per D4. | ~5500–7500 input token budget per `Layer4_Spec.md` §11.2; full payload feasible. Trimming would risk losing signal on 2A discipline-distribution + 3B periodization-shape — both load-bearing for T2's weekly placement. |
| D4 | `prior_plan_session_window` rendering | **Hybrid: refresh-window-prior (the 7 days BEFORE refresh) as summary table (date / sport / kind / duration / intensity / completion); refresh-window-after (the 7 days AFTER refresh) verbatim with all fields.** | Same shape as T1 D4. The continuity-handoff target moves to days 8-14 for T2 (vs days 3-9 for T1); the constraint reading is the same — refresh-window-after sessions are unchanged by this call and the new T2 sessions must land cleanly into them. |
| D5 | `parsed_intent` weighting policy | **Strong-bias toward intent** (Andy 2026-05-17 Pick 2). Same as T1. The athlete's `raw_text` + `parsed_intent` signals dominate the direction; 3A objective signals ground the magnitude. `intensity_modulated` flag fires on sessions whose prescription deviates from natural periodization-shape reading due to intent. | T2's larger scope means the synthesizer can shift the week's *shape* (not just per-session intensity) in response to intent. Athlete says "back off the week, I'm sick" → entire week pulls back, not just one session. |
| D6 | Coaching flag enum | **Full per-phase + cross-phase LLM-emittable set** (Layer 4 §§8.2–8.6 LLM-emitted entries only): `technique_emphasis`, `long_slow_distance`, `weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `race_pace_specific`, `intensity_modulated`. | Same enum as T1. T2 is more likely to emit `long_slow_distance` (covers the weekly cornerstone) + `overreach_test` (covers a full intentional overreach week) + `discipline_specific_intensity` (Build/Peak week may introduce race-pace work). |
| D7 | Continuity-with-adjacent-sessions policy | **Match surrounding training shape unless refresh trigger justifies a shift** (Andy 2026-05-17 Pick 3). | T2's 7-day scope is large enough that a clean reshape of the week is reasonable when intent justifies (athlete: "regenerate the week — I want more bike, less run"). The refresh-window-after (days 8-14) remains the continuity target — T2 doesn't reshape the next week. |
| D8 | `RuleFailure` retry context rendering | **Hybrid:** `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. | Same as T1. T2 retry contexts are more likely to involve weekly-aggregate rule failures (`volume_band_*`, `intensity_dist_*`) — the orchestrator's `suggested_constraint` for those rules names the week-level constraint (e.g., "Reduce weekly Z3-Z5 hours from 4.2 to ≤ 3.1 to land in Build phase's 70/20/10 distribution with ±10pp tolerance"). |
| D9 | Schema-enforced length caps | **Tight: 240 chars `session_notes` / 200 chars `coaching_intent` / 120 chars `load_prescription` / 240 chars `instructions`.** | Same as T1 + single-session. `max_tokens=4000` budget (up from T1's 2000) to absorb up to 14 sessions worth of structured output. |
| D10 | NL `raw_text` passthrough | **Always rendered in §6 user prompt under explicit "athlete's words" framing.** Same as T1. | Strong-bias-toward-intent (D5) means the prose is primary signal; structured flags are scaffolding. |
| D11 | File location | `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` per the `prompts/` subdir convention. | Inherits. |

**Companion contract sections (`Layer4_Spec.md`):** §3.2 (call signature), §4.3 (input validation — refresh preconditions including `tier_scope_mismatch` for T2 ≤ 9 days), §5.1 (pattern routing — T2 → B), §5.3 (Pattern B algorithm), §5.4 (deterministic validator — full scope including weekly volume + intensity distribution; T2 is the smallest scope where these are load-bearing), §5.5 (capped retry semantics), §7.2/§7.3/§7.4 (`PlanSession` discriminated union + sub-blocks), §7.5 (`SessionPhaseMetadata` — None on Pattern B refresh per §7.12 schema rule), §8.6 (`intensity_modulated` cross-phase flag — trigger broadened this session per paired amendment), §11.1 / §11.2 / §11.3 (latency / token / cost — ~7s / ~6500 input + ~3000 output / ~$0.12 typical).

**Paired spec amendment this session:** same as T1 — `Layer4_Spec.md` §8.6 `intensity_modulated` trigger row broadened to also cover `plan_refresh` paths.

---

## 1. Purpose + scope

### 1.1 What this prompt produces

A list of `PlanSession` records (typically 4–10 entries, max 14) covering `[refresh_scope_start, refresh_scope_end]` — 7 calendar days (rolling, today through today+6). Each session is athlete-facing and immediately renderable. The sessions emit `is_ad_hoc=False`, `plan_version_id=<new T2 version id>`, and `phase_metadata=None` (Pattern B refreshes don't write phase metadata per `Layer4_Spec.md` §7.12).

The synthesizer reads the freshly-re-run 3A + 3B (T2's default cascade per `Plan_Refresh_D64_Design_v1.md` §3.2 includes 3B; this lets the periodization shape evolve), the athlete's NL context, the prior plan's sessions for the refresh window (now superseded), and the surrounding ±7 days of plan context. It produces sessions that honor the refresh trigger, reshape the week as needed within the inherited (or freshly-tuned by 3B) phase intent, and hand off cleanly into the still-planned sessions for the following week.

### 1.2 What this prompt does NOT produce

- **Phase decomposition.** T2 reads the freshly-re-run 3B periodization shape but does not synthesize a `PhaseStructure`. The shape is consumed as constraint; the prompt produces session content within it. (Per `Layer4_Spec.md` §5.1, T2 routes to Pattern B regardless of whether scope spans a phase boundary — T2's 7-day scope is too small to justify Pattern A's per-phase decomposition. Phase-boundary T3 refreshes route to Pattern A; T2 stays B.)
- **Sessions outside the refresh window.** The prompt produces sessions for `[refresh_scope_start, refresh_scope_end]` (7 days). Refresh-window-after sessions (days 8-14) stay pointed at their prior `plan_version_id`; the synthesizer reads them as continuity constraint but does not modify them.
- **Multi-week or cross-phase commitment.** T2 reshapes 1 week. Multi-week reshaping is T3 territory. If the refresh-window-after sessions look like they should shift (e.g., refresh-window-after week 1 is high volume but T2's refresh window is a deload — the athlete may want week 2's plan adjusted too), surface as `Observation(category='opportunity', text='Consider T3 refresh to extend reshape into next week')`.
- **NL intent re-classification.** Same as T1 §1.2: parsed_intent is consumed verbatim; the prompt does not re-parse.
- **Observations or opportunities** other than the LLM-emitted `category='opportunity'` exception per `Layer4_Spec.md` §8.7.

### 1.3 Failure modes this prompt + retry semantics catch

- Athlete signals sickness (`parsed_intent.sickness_signal='active'`) but the synthesizer prescribes a normal week → validator catches via continuity / rest-spacing / ACWR projection if intensity is preserved despite the signal.
- Synthesizer's weekly volume falls outside the phase's `volume_band_*` per 2A `phase_load_bands` → validator `volume_band_blocker` triggers capped retry.
- Synthesizer's intensity distribution drifts outside the phase target (Base 80/15/5 ±10pp; Build 70/20/10 ±10pp; etc.) → validator `intensity_dist_*` triggers capped retry.
- Synthesizer's prescription conflicts with active injuries → `injury_violation_blocker` triggers capped retry.
- Synthesizer prescribes a hard session adjacent to a refresh-window-after planned hard session → `rest_spacing_blocker` triggers capped retry.

---

## 2. Pipeline placement

**Call site:** `llm_layer4_plan_refresh(user_id, tier='T2', ...)` per `Layer4_Spec.md` §3.2. Invoked by the D-64 orchestrator after:

1. Cascade execution per `Plan_Refresh_D64_Design_v1.md` §6.1 — 3A + 3B re-run (always for T2); optional 2A/2B/2C/2D/2E re-runs added by `parsed_intent` triggers.
2. Input validation per `Layer4_Spec.md` §4.3 — including `tier ∈ enum`, `refresh_scope_*` ordered, `tier_scope_mismatch` (T2 scope ≤ 9 days), `plan_version_id_parent` exists.

**Pattern:** B per `Layer4_Spec.md` §5.3 step 1 sub-bullet (T2):

> `plan_refresh` T2: above + 2B/2C/2E. [Above = 3A + 2A/2D + 1 + `prior_plan_session_window` + `parsed_intent`. T2 adds 3B always; adds 2B/2C/2E when intent-triggered.]

- Step 1: build context (this prompt's §3 inputs).
- Step 2: single LLM call (this prompt's §5 system + §6 user + §7 sampling config).
- Step 3: parse `record_refresh_sessions` tool output as `list[PlanSession]`.
- Step 4: deterministic validator (`Layer4_Spec.md` §5.4) — full rule set, scoped over the 7-day refresh window with adjacent-day continuity checks against `prior_plan_session_window`. Weekly aggregate rules (`volume_band_*`, `intensity_dist_*`) are load-bearing — the refresh window is a full week.
- Step 5: capped retry per `Layer4_Spec.md` §5.5 on validator failure; cap=2 (default).
- Step 6: compose `Layer4Payload` with `mode='plan_refresh'`, `pattern='B'`, `phase_structure=None`, `seam_reviews=None`, sessions covering the refresh window, `plan_version_id` set to the new T2 version id.

**Out-of-pipeline cases:** same as T1 — cascade pre-LLM failure, validator pre-LLM failure, `parser_confidence='low'` degraded path.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following variables. All are required unless marked optional. Token-budget realism per `Layer4_Spec.md` §11.2: ~6500 input tokens total worst case.

### 3.1 Refresh request

| Variable | Source | Notes |
|---|---|---|
| `refresh.tier` | D-64 caller | `'T2'`. |
| `refresh.scope_start` | D-64 caller | Typically today. |
| `refresh.scope_end` | D-64 caller | `scope_start + 6 days` (7-day rolling window; both ends inclusive). Validated per `Layer4_Spec.md` §4.3 (`tier_scope_mismatch` if length > 9 days). |
| `refresh.triggered_at` | D-64 caller | Timestamp. Used for recency reasoning. |

### 3.2 NL context + parsed intent

Identical to `Layer4_RefreshT1_v1.md` §3.2 — `parsed_intent.raw_text`, `fatigue_signal`, `sickness_signal`, `motivation_signal`, the 5 trigger booleans/lists, `parser_confidence`, `ambiguity_notes`.

### 3.3 Athlete + locale context

Identical to T1 §3.3 — `athlete.user_id`, `coaching_voice_preferences`, `experience_level`, `discipline_inclusion`, `active_injuries`, `locales`, `default_locale_for_date_window`.

T2-specific note: `default_locale_for_date_window` now covers 7 days. The synthesizer reads per-day locale assignment (athlete may travel mid-week; equipment view shifts).

### 3.4 Athlete state — drives modulation reasoning

Identical to T1 §3.4 — `acwr_7_28`, `seven_day_load`, `last_hard_session_date`, `last_hard_session_sport`, `fatigue_markers`, `data_density`, `aerobic_state`.

T2-specific note: 3A is re-run as part of the T2 cascade — values reflect the post-refresh-trigger state. If `parsed_intent` triggered a 2D re-run, `active_injuries` in §3.3 reflects the post-2D update; 3A's reading of athlete state is informed by it.

### 3.5 Periodization shape — freshly-re-run 3B

T2 re-runs 3B as part of its default cascade. The synthesizer reads the fresh 3B output for the periodization shape governing the refresh window.

| Variable | Source | Notes |
|---|---|---|
| `layer3b.periodization_shape.mode` | Layer 3B (re-run) | `'standard' \| 'compressed' \| 'extended' \| 'custom'`. The shape governing the athlete's plan. T2 may inherit a new mode if 3B's re-eval shifted it (rare but possible when 3A's re-eval surfaced a new fitness signal). |
| `layer3b.periodization_shape.start_phase` | Layer 3B (re-run) | The phase the plan is currently entering / continuing. |
| `layer3b.current_phase_at_date` | Layer 3B (computed) | Map: `{date: phase_name}` for each day in the refresh window. Lets the synthesizer know "day 1-4 are still Build; day 5-7 cross into Peak." Helpful for cross-phase weeks. |
| `layer3b.intended_volume_band_per_phase` | Layer 3B + 2A | Per-phase volume band the plan targets (driven by 2A `phase_load_bands` + 3B periodization mode). The refresh window's weekly total volume aims inside the band for the dominant phase. |
| `layer3b.intended_intensity_distribution_per_phase` | Layer 4 §5.4 v1 defaults + 3B refinements (when available) | Per-phase target distribution. Refresh window's intensity distribution validator reads against this. |
| `layer3b.days_to_event` | 3B | Optional. When ≤ 14, the synthesizer should default to Taper-shape week regardless of inherited phase reading. |
| `layer3b.deload_cadence_anchor` | 3B periodization mode (per `Layer4_PerPhase_v1.md` D6 anchor table) | Per-mode deload cadence (every 4th week standard; every 3rd compressed; every 5th extended; custom = judgment). When the refresh week falls on a deload, the synthesizer prescribes deload-shape sessions (reduced volume + intensity). |

### 3.6 Prior plan session window (drives continuity)

| Variable | Source | Notes |
|---|---|---|
| `prior_plan.refresh_window_prior` | `prior_plan_session_window` filtered to `[scope_start - 7d, scope_start - 1d]` | Last 7 days — summary table per D4. Drives recency / recovery reasoning + lets the synthesizer read what just happened (e.g., athlete had a hard 4-hour ride 3 days ago; T2 needs to absorb that). |
| `prior_plan.refresh_window_during_prior` | `prior_plan_session_window` filtered to `[scope_start, scope_end]` | The prior-plan sessions the refresh is replacing (full week, max ~14 sessions). Rendered verbatim. The synthesizer reads "this is what was planned; the athlete is asking for a different shape." |
| `prior_plan.refresh_window_after` | `prior_plan_session_window` filtered to `[scope_end + 1d, scope_end + 7d]` | Next 7 days, still planned. Rendered verbatim per D4. The hand-off target. |

### 3.7 Retry context (only present on retry pass)

Identical to T1 §3.7.

### 3.8 Intentionally NOT passed

- `phase_structure` — Pattern B has no phase decomposition; T2 reads 3B's shape directly without synthesizing per-phase week-by-week breakouts.
- `seam_issues` / `seam_direction` — Pattern B has no seam reviewer.
- `event_date` / `race_format` — surfaced indirectly via `layer3b.days_to_event` when relevant; race-week specifics handled by `Layer4_RaceWeekBrief` (queued).

---

## 4. Output schema + tool definition

The synthesizer emits exactly one tool call to `record_refresh_sessions`. Schema is identical to T1's §4.1 except `sessions.maxItems = 14` (vs 4 for T1).

### 4.1 Tool schema (diff from T1)

```diff
- "maxItems": 4,
+ "maxItems": 14,
```

Everything else — session shape, `additionalProperties: false`, the closed coaching-flag enum, cardio blocks + strength exercises, `notable_observations` with `opportunity` only — matches T1 §4.1 verbatim. Reproduced fully in `Layer4_RefreshT1_v1.md` §4.1; not duplicated here.

### 4.2 Output invariants the prompt must honor

- `len(sessions)` in `[0, 14]`. Typical T2 produces 4–10 sessions (sport variety + rest days respected).
- Each session's `date` falls inside `[refresh_scope_start, refresh_scope_end]`.
- Per-date max 2 sessions per `Layer4_Spec.md` §7.12 (same constraints as T1: no strength+strength, no two `hard`, at least one cardio).
- `coaching_flags` closed set per D6.
- `intensity_modulated` MUST be emitted on every session where the prescription deviates from natural periodization-shape reading due to intent or 3A signal. Per-week-aggregate modulation (e.g., entire week pulled back due to sickness) emits the flag on every affected session.
- `notable_observations[].category` restricted to `'opportunity'`.

T2-specific invariants:

- **Weekly volume**: the refresh window's total volume should land inside the dominant phase's `volume_band` per 2A `phase_load_bands`. Validator enforces with `volume_band_*` rules.
- **Intensity distribution**: the refresh window's distribution of hours across (Z1-Z2 / Z3 / Z4-Z5) should land inside the dominant phase's target ±10pp tolerance. Validator enforces with `intensity_dist_*` rules.
- **Long-session anchor**: in Base + Build phases, the week should contain exactly one `long_slow_distance`-flagged session per discipline that has a weekly LSD cornerstone (per `Layer4_Spec.md` §8.2). Missing the LSD on a Base/Build week is a coaching gap (not validator-enforced but surfaced via `Observation(category='opportunity')` if missed).
- **Deload week**: when the refresh window aligns with the inherited periodization's deload cadence, the synthesizer prescribes deload-shape sessions (reduced volume per `intended_volume_band` lower edge; reduced intensity per phase target with bias toward Z1-Z2). The orchestrator emits the `recovery_week` flag spec-auto on all sessions in the week.

---

## 5. System prompt

```
You are AIDSTATION's Layer 4 plan-refresh T2 synthesizer.

You are called when an athlete clicks "Regenerate the rest of the week" on their training plan. The athlete has typed an optional free-text note explaining why they want the refresh. Your job is to produce 0-14 PlanSession records covering the next 7 calendar days that:

1. Honor the athlete's stated intent (their words are the primary signal — see §9).
2. Stay inside the inherited (and freshly-re-run-by-3B) periodization phase's intent — volume band + intensity distribution within phase tolerance.
3. Reshape the week's structure as needed (session count per day / discipline distribution / hard-vs-easy placement) when athlete intent justifies it.
4. Hand off cleanly into the sessions already planned for days 8-14 after the refresh window.
5. Never violate hard constraints — active injuries, equipment availability, schedule availability.

VOICE: Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Match a real endurance coach talking to a serious athlete.

PROCESS:
- Read the athlete's `raw_text` and `parsed_intent` first. These drive WHY you're reshaping the week.
- Read the freshly-re-run 3A + 3B output for current periodization shape + athlete state.
- Read the last 7 days summary to ground the modulation in recent training.
- Read the refresh-window-after sessions (days 8-14) — these are the continuity hand-off target.
- Decide the week's shape: how many sessions per day (1 or 2 per §K availability); which disciplines on which days; where the LSD anchor lands; whether the week is a deload, an overreach, or a standard build week given the inherited phase's cadence.
- For each session, prescribe sport / duration / intensity + structured content (cardio_blocks or strength_exercises).
- Aim weekly volume inside the dominant phase's volume_band ± tolerance; aim intensity distribution inside the phase target ±10pp.
- Emit `intensity_modulated` whenever a session's prescription deviates from what the periodization shape + continuity would naturally call for due to athlete intent or 3A signal. Briefly explain in `session_notes`.

You emit exactly one tool call: `record_refresh_sessions`. The tool's `sessions` argument is your list of 0-14 PlanSession records. Optionally include `notable_observations` with up to 2 `opportunity` entries.

Do not return any text outside the tool call.
```

---

## 6. User prompt (template — Mustache variables)

```
=== Refresh request ===
Tier: T2 (7-day rolling window)
Scope: {{ refresh.scope_start }} through {{ refresh.scope_end }}
Triggered at: {{ refresh.triggered_at }}

=== Athlete's words ===
{{#parsed_intent.raw_text}}
Athlete typed: "{{ parsed_intent.raw_text }}"
{{/parsed_intent.raw_text}}
{{^parsed_intent.raw_text}}
(Athlete refreshed without typing a note.)
{{/parsed_intent.raw_text}}

Parsed intent signals (NL parser; confidence: {{ parsed_intent.parser_confidence }}):
- Fatigue: {{ parsed_intent.fatigue_signal }}
- Sickness: {{ parsed_intent.sickness_signal }}
- Motivation: {{ parsed_intent.motivation_signal }}
- Injury mentioned: {{ parsed_intent.triggers_2d_injury }}
- New discipline mentioned: {{ parsed_intent.triggers_2a_discipline }}
- Equipment / locale mentioned: {{ parsed_intent.triggers_2c_equipment }}
{{#parsed_intent.ambiguity_notes}}
Parser noted ambiguity: {{ parsed_intent.ambiguity_notes }}
{{/parsed_intent.ambiguity_notes}}

POLICY: The athlete's words and the parsed signals dominate the prescription direction. 3A objective signals (ACWR, recent load, last-hard-session) ground the magnitude but do not override the direction. Hard safety constraints (active injuries, equipment availability, schedule availability) are never overridden. When the week's shape or any session's prescription deviates from what the inherited phase + adjacent-week continuity would naturally call for due to intent, emit `intensity_modulated` on the affected sessions and briefly explain in `session_notes`.

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

=== Periodization shape (3B — re-run as part of T2 cascade) ===
Mode: {{ layer3b.periodization_shape.mode }}
Start phase (when the plan started): {{ layer3b.periodization_shape.start_phase }}
Current phase per day in refresh window:
{{#layer3b.current_phase_at_date}}
  {{ date }}: {{ phase }}
{{/layer3b.current_phase_at_date}}
Intended volume band (dominant phase): {{ layer3b.dominant_phase_volume_band }}
Intended intensity distribution (dominant phase, Z1-Z2/Z3/Z4-Z5): {{ layer3b.dominant_phase_intensity_distribution }}
Deload cadence: {{ layer3b.deload_cadence_anchor }}
{{#layer3b.days_to_event}}
Days to event: {{ layer3b.days_to_event }}
{{/layer3b.days_to_event}}

Note: When the refresh window aligns with the deload cadence (e.g., 4th week in standard mode), prescribe deload-shape sessions — reduced volume to the lower edge of the band, reduced intensity with bias toward Z1-Z2. Orchestrator emits `recovery_week` spec-auto.

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

Weekly aggregate: {{ prior_plan.refresh_window_prior_summary.total_hours }}h across {{ prior_plan.refresh_window_prior_summary.session_count }} sessions; distribution {{ prior_plan.refresh_window_prior_summary.intensity_distribution }} (Z1-Z2/Z3/Z4-Z5).

=== Sessions previously planned for the refresh week (being replaced) ===
{{#prior_plan.refresh_window_during_prior}}
- {{ date }} ({{ sport }} / {{ kind }} / {{ duration_min }}min / {{ intensity }}): {{ coaching_intent }}{{#coaching_flags}} [{{ . }}]{{/coaching_flags}}
{{/prior_plan.refresh_window_during_prior}}

=== Sessions planned for days 8-14 (continuity constraint — NOT being modified by this refresh) ===
{{#prior_plan.refresh_window_after}}
- {{ date }} ({{ sport }} / {{ kind }} / {{ duration_min }}min / {{ intensity }}): {{ coaching_intent }}{{#coaching_flags}} [{{ . }}]{{/coaching_flags}}
{{/prior_plan.refresh_window_after}}

Your T2 output must hand off cleanly into these. If days 8-14 contain a key workout (long ride, race-pace day, overreach week, weak-link strength), the refresh week's last 1-2 days should support recovery into / preparation for it. Do not undermine the planned post-refresh week.

{{#retries_used}}
=== Retry context (pass {{ retries_used }} of cap=2) ===
Prior pass failed deterministic validator with these rule failures:
{{#rule_failures}}
- [{{ severity }}] `{{ rule_name }}` on session(s) {{ affected_session_ids }}: {{ detail }}
  Constraint to honor on this pass: {{ suggested_constraint }}
{{/rule_failures}}

Repair pass: address each constraint above while keeping the rest of the prescription intact. Weekly-aggregate failures (volume_band_*, intensity_dist_*) may require shifting multiple sessions; do the minimum needed to clear the constraint.
{{/retries_used}}

=== Output ===
Emit one tool call to `record_refresh_sessions` with your list of 0-14 PlanSession records. Optionally include `notable_observations` with up to 2 `opportunity` entries.
```

---

## 7. Sampling configuration

| Parameter | Value | Rationale |
|---|---|---|
| `model` | `claude-sonnet-4-6` (default) | Per `Layer4_Spec.md` §3.2 framing. |
| `temperature` | 0.5 | Slightly higher than T1's 0.4 — T2's larger surface benefits from more sampling variation for weekly-shape exploration. |
| `max_tokens` | 4000 | Up to 14 sessions × ~280 tokens each = ~3900 + buffer. |
| `extended_thinking` | enabled, budget=4500 tokens | Per D2. Calibrates between T1's 3000 and per-phase's 5000. |
| `tool_choice` | `{"type": "tool", "name": "record_refresh_sessions"}` | Forces the tool call. |
| `tools` | `[record_refresh_sessions]` | Per §4 schema (with `maxItems: 14`). |
| Schema retry on parse failure | 1 attempt (separate from §5.5) | One retry on malformed JSON; bail with `Layer4OutputError('schema_violation')` on second failure. |

---

## 8. Coaching flag emission rules

Identical enum + spec-auto vs LLM-emitted split as T1 §8. Reproduced briefly:

| Flag | Phase | T2-specific frequency note |
|---|---|---|
| `technique_emphasis` | Any | Likely on Base + Build weeks containing drill/skill work. |
| `long_slow_distance` | Base + Build | **Expected weekly** on Base + Build cornerstones. Missing the LSD on a non-deload Base/Build week is a coaching gap. |
| `weak_link_targeted` | Build (typically) | Strength accessory work for 3A `weak_links`. |
| `overreach_test` | Build (last week before deload) | Whole-week flag — every session in an overreach week emits this. Rare unless inherited cadence indicates the refresh week IS the overreach week. |
| `discipline_specific_intensity` | Build + Peak | First-time race-discipline-specific intensity prescription in the plan. |
| `race_pace_specific` | Peak | Cardio at race-target pace/power. |
| `intensity_modulated` | Cross-phase | Per spec amendment §8.6 this session — fires on every session whose prescription deviates from natural periodization-shape + continuity reading due to intent or 3A signal. |

**Spec-auto-emitted flags are orchestrator-side**, not the prompt's: `first_introduction_to_<discipline>`, `aerobic_base_focus`, `volume_ramp_conservative`, `volume_ramp_aggressive`, `recovery_day_after_long`, `peak_volume_marker`, `tune_up_race`, all Taper-phase flags per §8.5, `race_day`, `recovery_week`. If the synthesizer redundantly emits one, orchestrator merge is idempotent.

**`intensity_modulated` mandatory when applicable** — same as T1. On a whole-week modulation (athlete sick → week pulled back), emit the flag on every session.

---

## 9. Coaching guidance

### 9.1 Strong-bias-toward-intent — what it means in practice

Same philosophy as T1 §9.1, applied to the larger weekly surface. The athlete's words + signals dominate the direction; 3A grounds the magnitude.

Examples specific to T2's weekly scope:

| Athlete says (`raw_text`) | Parsed | 3A / 3B | Week-shape prescription |
|---|---|---|---|
| "Regenerate the week, I'm feeling great" | motivation=high | ACWR 1.0; Build phase | Normal Build-week shape; volume + intensity to upper edge of band; LSD on a high-availability day; race-pace work mid-week if discipline indicates. No `intensity_modulated`. |
| "Back off the week, I'm sick" | sickness=active | (3A reflects recent training; doesn't matter — sickness override) | Rest-shape week: easy spinning + mobility only; zero hard sessions; total volume to deload lower-edge or below. `intensity_modulated` on every session. `session_notes`: "Athlete reported active sickness; week structured as recovery." |
| "Travel Wed-Fri, only hotel gym" | triggers_2c_equipment=[hotel_gym]; 2C re-ran | Build phase | Wed-Fri sessions use hotel_gym equipment view; Tier 2/3 substitutions; LSD anchor moved to Sun or Mon. Not necessarily `intensity_modulated` — same intent, different equipment. |
| "Push hard, weak link is run economy" | motivation=high; `parsed_intent.triggers_2a_discipline=False` (no new discipline; the run focus is via existing inclusion) | Build phase; 3A `weak_links` includes run economy | Build-week shape; running-discipline focus increased; technique drills emitted with `technique_emphasis`; running volume to upper-edge. Possibly `intensity_modulated` on the elevated run-day if it pushes above natural Build placement. |
| "I have an unexpected travel day Wednesday" | (locale changed) | (normal) | Wed session reshaped for travel locale; other days unchanged. Not `intensity_modulated`. |
| "Just back from sickness, ease back in" | sickness=recovering; motivation=low | ACWR 0.6 (atrophied) | Easy-aerobic-only week; no hard sessions; volume to deload-band; rebuild intent. `intensity_modulated` on every session. `session_notes`: "Athlete recovering from illness — easy aerobic only this week." |
| (empty `raw_text`) | (all defaults) | ACWR 1.0; Build phase week 3 of 4 (next is deload) | Standard Build-week-3 shape: highest-volume of the block; harder sessions toward mid-week; LSD on weekend. No `intensity_modulated`. |
| (empty `raw_text`) | (all defaults) | Deload cadence indicates this IS the deload week | Deload-shape week: volume to lower edge; intensity preserved but Z3+ minimized; recovery emphasized. No `intensity_modulated` — this IS the natural phase reading (orchestrator emits `recovery_week` spec-auto on every session). |

### 9.2 Sickness is a hard constraint (week-level)

When `parsed_intent.sickness_signal == 'active'`: rest-shape week regardless of phase or continuity. Light walks + mobility only; zero hard sessions; total weekly volume far below the phase's volume_band lower edge is acceptable (validator's `volume_band_*` rule is `severity=warning` for ±5% / `blocker` for ±15%; a 50-80% volume reduction triggers warning that orchestrator demotes to observation given the sickness signal — actual validator behavior to be verified during implementation).

When `parsed_intent.sickness_signal == 'recovering'`: easy aerobic week. Daily volume below typical; no intervals; no race-pace; no overreach. Emit `intensity_modulated` on every session.

### 9.3 Weekly shape — what "match surrounding shape" means at T2 scope

The continuity constraint from Pick 3 applies at the boundary (last 1-2 days of refresh + first 1-2 days of refresh-window-after). Inside the week, the synthesizer has more latitude to reshape — that's why T2 exists.

Concrete shape decisions the synthesizer makes:

| Decision | Anchor signals |
|---|---|
| LSD anchor day | Athlete's §K weekend availability; refresh-window-after week's pattern; phase (Base/Build typically have weekly LSD). |
| Hard sessions per week | Phase-driven (Build typically 2 hard; Peak typically 2-3; Taper typically 1; Base typically 1 with focus on aerobic volume). `parsed_intent.fatigue_signal` shifts magnitude. |
| Discipline distribution across days | 2A `discipline_inclusion` weights; athlete preference from prior_plan_session_window patterns; equipment availability per day. |
| Strength session day | Typically 1-2 per week; not adjacent to hard cardio in same discipline; emits `weak_link_targeted` on accessories for 3A weak_links. |
| Rest day placement | At least 1 per week (matches §K typical); placed adjacent to hardest cardio day or before refresh-window-after's heaviest day. |

The synthesizer reads `prior_plan.refresh_window_prior_summary.intensity_distribution` to know what the athlete just did; the refresh week's distribution should land inside the phase target while also providing meaningful contrast where the prior week was unbalanced.

### 9.4 Volume band + intensity distribution — hard-ish constraints on T2

T2's 7-day window is exactly the granularity at which the validator's `volume_band_*` and `intensity_dist_*` rules are most meaningful. The synthesizer aims weekly totals inside the dominant phase's band/target ± tolerance:

| Phase | Volume band lookup | Intensity distribution target (Z1-Z2 / Z3 / Z4-Z5) |
|---|---|---|
| Base | 2A `phase_load_bands['Base']` per dominant discipline | 80 / 15 / 5 |
| Build | 2A `phase_load_bands['Build']` | 70 / 20 / 10 |
| Peak | 2A `phase_load_bands['Peak']` | 70 / 20 / 10 |
| Taper | 2A `phase_load_bands['Taper']` | 75 / 15 / 10 |

Tolerance per `Layer4_Spec.md` §5.4: volume ±5% warning / ±15% blocker; intensity distribution ±10pp tolerance per zone.

**Cross-phase weeks** (refresh window spans a phase boundary — rare but possible when the inherited shape transitions): use a weighted blend of the two phases' targets, weighted by day-count. E.g., 3 days Build + 4 days Peak → distribution target ≈ (3 × Build + 4 × Peak) / 7. Validator handles via per-day phase mapping; synthesizer's weekly aim is approximate.

### 9.5 Exercise + cardio block selection

Same conventions as T1 §9.5 + `Layer4_PerPhase_v1.md` §9. Tier 1/2/3 substitution per locale; 4–8 strength exercises per session; cardio blocks with structured intensity per block; interval blocks include reps + work/recovery durations.

### 9.6 Don't over-explain

Same as T1 §9.6 — `coaching_intent` (200 chars) is purpose; `session_notes` (240 chars) is the "why this prescription." Modulation reasoning surfaces in `session_notes` when `intensity_modulated` fires.

### 9.7 LSD anchor — the load-bearing weekly decision in Base/Build

In Base or Build phases, the week's LSD session is the cornerstone. The synthesizer:

1. Picks the day with longest §K window for the discipline's primary discipline (running's primary for run-focused athletes; cycling's primary for cycling-focused; etc.).
2. Prescribes duration at 2A `phase_load_bands[Base|Build]` upper-bound for the discipline's single longest session (typically 1.5-3× the next-longest session in the week).
3. Intensity easy / Z2 dominantly; emits `long_slow_distance` flag.
4. Builds the rest of the week around it — easier days adjacent, hard intervals mid-week away from the LSD.

If `parsed_intent.fatigue_signal in ('tired', 'wiped')` AND the LSD would push the athlete deep: shorten the LSD by 15-30% and emit `intensity_modulated` — keep the cornerstone but acknowledge the signal.

If `parsed_intent.sickness_signal == 'active'`: drop the LSD entirely; rest-shape week.

---

## 10. Edge cases

| Case | Handling |
|---|---|
| Refresh window spans a phase boundary (e.g., last 3 days of Build → first 4 days of Peak) | Per `Layer4_Spec.md` §5.1 routing: T2 stays Pattern B (Pattern A is only for T3 cross-phase). Synthesizer reads per-day `layer3b.current_phase_at_date`; targets weighted-blend intensity distribution per §9.4. The phase-shift session(s) carry phase metadata implicit in the date (orchestrator computes on write); LLM doesn't emit phase_metadata directly. |
| `parsed_intent.triggers_2a_discipline=True` (athlete reports starting a new discipline) | 2A re-ran upstream; `athlete.discipline_inclusion` reflects the new sport. Prescribe at least one session in the new discipline this week; emit `first_introduction_to_<discipline>` spec-auto on the first session (orchestrator-side; LLM doesn't need to emit). Volume conservative for the new discipline (athlete is `data_density=very_sparse` for it). |
| Refresh week aligns with deload cadence | Prescribe deload-shape week per §9.1 row 8. Orchestrator emits `recovery_week` spec-auto. The synthesizer's volume + intensity targets shift to the lower edge of the phase band. |
| Refresh week is an overreach week per inherited cadence | Per `Layer4_Spec.md` §8.3 LLM-emitted `overreach_test` flag: every session in the overreach week emits this flag. Volume pushes to or above upper-edge; intensity preserved or elevated. Validator's `volume_band_warning` may fire on the upper edge but is expected on overreach weeks. Athlete intent can override (if athlete reports tired during a scheduled overreach week, the synthesizer can pull back and skip the overreach — emits `intensity_modulated` on every session + `Observation(category='opportunity', text='Scheduled overreach week pulled back due to fatigue signal — consider re-attempting in 2 weeks')`. |
| Refresh-window-after contains a `race_rehearsal` flag (Taper phase, days_to_event ≤ 14) | Refresh window IS late Taper or the transition into Taper. Prescribe Taper-shape: volume down, intensity preserved, race-rehearsal preparation. Don't compromise the upcoming rehearsal session. |
| `parsed_intent.parser_confidence='low'` AND non-empty raw_text | Per T1 edge case: read raw_text as primary; structured flags unreliable. Apply strong-bias-toward-intent from the prose; emit modulation flags as the prose direction indicates. |
| `parsed_intent.parser_confidence='low'` AND empty raw_text | No athlete signal. 3A + 3B drive per natural periodization reading. No `intensity_modulated` unless 3A signals (e.g., elevated ACWR) require it. |
| Refresh-window-after is empty (athlete at end-of-plan, refresh starts at or near end) | Continuity constraint reduced. Inherited periodization shape from refresh-window-during-prior + 3B output. Surface as `Observation(category='opportunity', text='Plan approaching end — consider T3 refresh to extend periodization horizon')`. |
| 3B re-eval flipped periodization mode (e.g., `standard` → `compressed` due to time-to-event shift) | The refresh week reflects the new mode's phase proportions. The continuity hand-off to refresh-window-after may now be awkward (the old plan's phase assumptions differ from the new). Surface as `Observation(category='opportunity', text='Periodization mode shifted; consider T3 to re-shape the full plan')` and prescribe the refresh week per the new shape's intent. |
| Multiple per-day sessions throughout the week | Per §7.12: max 2 per day, no strength+strength, no two hard, at least one cardio. Synthesizer balances across the week — typically 1-2 days per week with double sessions; rest 1-per-day. |
| Athlete has no completed sessions in refresh-window-prior (zero recent training data) | `data_density='very_sparse'`. Conservative prescription: lower volume than band lower-edge is acceptable; ramp slowly; emit `volume_ramp_conservative` (spec-auto, orchestrator-side). |

---

## 11. Validator + retry contract

Full `Layer4_Spec.md` §5.4 rule set applies. T2's 7-day window makes the weekly-aggregate rules (`volume_band_*`, `intensity_dist_*`) load-bearing — these will be the most common retry triggers in production.

**Validator scope on T2:**

| Rule | T2 weight |
|---|---|
| `volume_band_*` | High. Weekly total volume vs. phase band, dominant discipline + cross-discipline. |
| `acwr_*` | High. Forward projection across refresh window + refresh-window-after. T2 may shift ACWR meaningfully (whole week reshape). |
| `rest_spacing_*` | Medium. Within-week constraint + boundary with refresh-window-after. |
| `intensity_dist_*` | High. Per-phase distribution target; weekly aggregate is the natural granularity. |
| `two_per_day_*` | Medium. Standard. |
| `equipment_unavailable_*` | High. 7 days × per-day locale. |
| `injury_violation_*` | High. Hard constraint. |
| `schedule_violation_*` | High. §K per day. |
| `discipline_excluded_*` | Medium. |
| `sport_locale_incompatible_*` | Medium. |

**Continuity cross-validation (T2-specific):**

- `rest_spacing_*` extends across the refresh / refresh-window-after boundary. T2 day 7 hard + refresh-window-after day 1 hard same-discipline → `rest_spacing_blocker` unless coaching flags justify.
- `acwr_*` projects forward through refresh-window-after for the chronic-load denominator. T2's elevated week can push the trailing 14-day ACWR into blocker territory if not modulated.

**Retry context rendering (D8):** same as T1 §11. Weekly-aggregate rule failures (`volume_band_*`, `intensity_dist_*`) include the `suggested_constraint` naming the aggregate adjustment ("Reduce weekly Z3-Z5 hours from 4.2 to ≤ 3.1") rather than per-session constraints.

**Cap behavior:** same as T1 §11 — cap=2, schema-retry separate.

---

## 12. Test scenarios

PSS-T2 prefix for v1 test scenarios.

| ID | Scenario | Expected output |
|---|---|---|
| PSS-T2-01 | Empty NL note; 3A ACWR 1.0; Build phase week 2 of 4 (next is overreach + deload). | Standard Build-week-2 shape: 2 hard sessions, LSD on weekend, 1 strength, ~6-7 sessions total; volume mid-band; intensity 70/20/10 ±5pp. No `intensity_modulated`. |
| PSS-T2-02 | "Back off the week, I'm sick"; sickness=active. | Rest-shape week: 2-3 light mobility/walking sessions max; zero hard; total volume < 30% of normal week; `intensity_modulated` on every session; `session_notes` notes the sickness. Empty `sessions` is also valid if §K availability is very low. |
| PSS-T2-03 | "Regenerate the week, feel strong"; motivation=high; 3A ACWR 1.0; Build phase. | Build-week shape; volume to upper-band-edge; 2 hard sessions; LSD with stretch goal duration; no `intensity_modulated` unless prescription deviates from natural Build reading. |
| PSS-T2-04 | "Travel Wed-Fri, hotel gym"; triggers_2c_equipment=[hotel_gym]; 2C re-ran. | Wed-Fri sessions use hotel_gym equipment view; substitutions via Tier 2/3; LSD anchor moved off Wed-Fri (likely Sat/Sun); strength sessions if any use hotel-gym equipment. No `intensity_modulated`. |
| PSS-T2-05 | "I have an unexpected travel day Wed"; one-day locale change. | Wed session reshaped for travel locale; other 6 days unchanged. No `intensity_modulated`. |
| PSS-T2-06 | Refresh week aligns with deload cadence (4th week, standard mode); no NL note. | Deload-shape: volume to lower edge; intensity slightly reduced with Z1-Z2 bias; LSD shortened or held; 1 strength typical; orchestrator emits `recovery_week` spec-auto. No `intensity_modulated`. |
| PSS-T2-07 | Refresh week is the overreach week per cadence; no NL note. | Overreach-shape: volume to upper-edge or slightly above; intensity preserved or +5pp; LLM emits `overreach_test` on every session. No `intensity_modulated`. |
| PSS-T2-08 | Refresh week is overreach week per cadence; athlete: "I'm tired"; fatigue=tired. | Synthesizer pulls back the overreach: standard Build-week shape instead of overreach; emits `intensity_modulated` on every session; `Observation(category='opportunity', text='Scheduled overreach pulled back; consider re-attempting in 2 weeks')`. |
| PSS-T2-09 | Refresh window crosses Build→Peak phase boundary (3 days Build + 4 days Peak). | Cross-phase week per §10 row 1: per-day phase mapping; weighted blend of distribution targets; first race-pace session emerges in the Peak portion with `discipline_specific_intensity` if first time in plan. |
| PSS-T2-10 | First-pass validator returns `volume_band_blocker` (weekly volume 25% above upper edge). | Retry pass reduces weekly volume to inside band; minimal session-content changes elsewhere; validator passes. |
| PSS-T2-11 | First-pass validator returns `intensity_dist_blocker` (week's Z4-Z5 hours = 18%, Build target 10% ±10pp = max 20% — wait, this is inside; needs steeper miss). Adjusted scenario: Z4-Z5 = 30%, Build target 10% ±10pp = max 20%. | Retry pass shifts 2 sessions' intensity down; validator passes. |
| PSS-T2-12 | First-pass + second-pass both fail `volume_band_blocker` (cap-hit). | Latest synthesis accepted; failure demoted to warning; `Observation(category='best_effort_plan', elevates_to_hitl=True)` emitted by orchestrator. |
| PSS-T2-13 | "I tweaked my knee" missed by parser (`triggers_2d_injury=False` but raw_text says it). | Per §10 edge case (same as T1): honor the prose; avoid knee-loaded sessions; emit `Observation(category='opportunity', text='NL parser missed injury signal — recommend 2D re-eval')`. |
| PSS-T2-14 | Athlete is in Taper, days_to_event=10; refresh-window-after contains `race_rehearsal` flag day 8. | Taper-shape week: volume down to Taper lower edge; intensity preserved; rehearsal-day preparation in days 6-7. No `intensity_modulated` (this IS natural Taper). |
| PSS-T2-15 | 3B re-eval flipped periodization mode (compressed → extended due to event date moving back). | Refresh week reflects extended mode's phase proportions; surface `Observation(category='opportunity', text='Mode shifted; consider T3 to re-shape full plan')`. |
| PSS-T2-16 | Refresh-window-after is empty (end-of-plan). | Continuity constraint reduced; prescribe per inherited phase + 3B; surface `Observation(category='opportunity', text='Plan approaching end — consider T3')`. |
| PSS-T2-17 | `data_density='very_sparse'`; 3A signals no recent training. | Conservative prescription: lower-edge volume or below; ramp slow; spec-auto `volume_ramp_conservative` (orchestrator-side) on cardio sessions. |
| PSS-T2-18 | "Push hard on running, weak link is run economy"; motivation=high; 3A weak_links includes run economy. | Running-discipline-heavy week; technique drills with `technique_emphasis`; strength accessory with `weak_link_targeted` on running-specific exercises (e.g., posterior chain); volume to upper-edge for running. Possibly `intensity_modulated` if total intensity pushed above natural Build week-2 reading. |

---

## 13. Performance budget

Per `Layer4_Spec.md` §§11.1–11.3:

| Budget | Value | Notes |
|---|---|---|
| Latency p50 | ~7s | Pattern B single call. `Layer4_Spec.md` §5.3 latency expectation 4–8s. |
| Latency p95 | ~12s | One retry. Cap-hit (2 retries) worst case ~20s. |
| Input tokens (typical) | ~6500 | Full 3A + 3B + 2A + 2D + 1 + `parsed_intent` + `prior_plan_session_window ±7d`. |
| Input tokens (worst case) | ~9000 | With `parsed_intent` triggering 2B + 2C (multi-locale) + 2E re-runs (full payloads). |
| Extended thinking tokens | ~4500 (budget) | Per D2. |
| Output tokens | ~3000 | Up to 14 sessions × ~250 each = ~3500 max. |
| Cost per call (Sonnet 4.6 typical pricing) | ~$0.12 | ~$0.04 input + ~$0.08 output. |
| Cost per call (worst case) | ~$0.22 | With cap-hit retries + heaviest intent triggers. |
| Cache key per `Layer4_Spec.md` §9.x | `(athlete_id, tier, refresh_scope_start, sha256(normalized(parsed_intent.raw_text + parsed_intent flags + 3A + 3B fingerprints)))` | Identical inputs cache-hit; orchestrator rebinds `plan_version_id`. |

---

## 14. Open items + gut check

### 14.1 Open items

- **`intensity_modulated` trigger broadening.** Same paired spec amendment as T1 — `Layer4_Spec.md` §8.6 broadened from D-63-only to also cover `plan_refresh` paths. Verify both §8.6 + §8.7 reflect the broader scope after this session's PR lands.
- **`intended_intensity_distribution` athlete-specific reading.** Same as T1 open item — 3B doesn't currently persist per-call athlete-specific distribution refinements; T2 reads the §5.4 v1 defaults. Athlete-specific tuning is a v2 follow-up.
- **Per-day phase mapping for cross-phase weeks (§10 row 1).** The weighted-blend approach for cross-phase weeks is approximate; the validator's `intensity_dist_*` rule applies per-phase. Behavior on cross-phase weeks needs telemetry validation post-implementation.
- **Weekly-volume validator under sickness signal (§9.2).** When sickness=active, the synthesizer prescribes <30% of normal volume. Validator's `volume_band_warning` will fire. Need orchestrator-side logic to demote the warning to observation given the sickness signal, OR adjust validator to read `parsed_intent` for severity calibration. Lands as a validator-implementation followup.
- **`overreach_test` flag interaction with athlete pullback (§10 row 4 + PSS-T2-08).** When the synthesizer pulls back a scheduled overreach due to fatigue signal, the flag is NOT emitted on the pulled-back sessions. Spec amendment to §8.3 may be needed to formalize "overreach can be skipped by intent" — currently spec assumes overreach is synthesizer-prescribed and athlete-honored. Defer to telemetry; v1 prompt handles the case correctly via `intensity_modulated` + opportunity observation.

### 14.2 Gut check

**What's right:**
- **T2 is the load-bearing refresh tier** — most athlete-driven refreshes will be T2 ("regenerate the week"). The full validator rule set being meaningful at this scope ensures quality.
- **Weekly-aggregate validator constraints are exactly the right granularity** for periodization adherence. T1's 2-day window is too small; T3's 28-day window is the realm of Pattern A. T2's 7-day window aligns with the natural training-week cadence + the validator's per-phase volume/intensity rules.
- **Strong-bias-toward-intent at week scope** lets athletes reshape the week meaningfully (athlete: "more bike, less run this week"; T2 honors). The prior plan's discipline distribution is context, not constraint.
- **LSD anchor as the load-bearing weekly decision** captures coaching practice — the long session is the cornerstone in Base/Build, and the rest of the week is built around it.
- **Deload + overreach week handling** captures the periodization cadence concept that validates against telemetry. Athletes refreshing on a deload week get a deload-shape output; those on an overreach week get the overreach unless they pull back.

**Risks:**
- **Weekly volume bands under sickness** — the validator may fire warnings the orchestrator needs to demote. v1 prompt handles by emitting `intensity_modulated` + brief notes; validator implementation needs to coordinate. Listed in §14.1.
- **Cross-phase week handling is approximate.** The weighted-blend distribution target may be off when phase boundary falls mid-week. Telemetry will reveal whether this causes spurious validator failures.
- **Cap-hit cases at T2 are more disruptive than T1.** Whole week of best-effort synthesis is a degraded UX. Two retries is the budget; if the synthesizer can't satisfy weekly-aggregate constraints in 2 passes, the athlete sees `best_effort_plan` observation. Mitigation: `suggested_constraint` retry context should be precise enough that 1 retry typically clears.
- **Discipline reshaping (athlete: "more bike, less run")** may conflict with 2A `discipline_inclusion` priorities. The athlete's intent dominates per Pick 2, but if 2A weights running higher (race-relevant discipline), the synthesizer's pull-back-on-running prescription may surface a coaching tension. v1 honors the intent; v2 could surface the tension to the athlete pre-write.

**What might be missing:**
- **Multi-athlete coordination.** Same as T1 — joint-session overlays out of v1.
- **NL signal richness.** Same as T1 — parser maps to schema's vocabulary; signal loss is real; `raw_text` passthrough partially mitigates.
- **Refresh-week-vs-following-week cascade.** Athlete may refresh T2 then realize the following week also needs adjustment. The opportunity observation flags this when detected (§10 row 8, row 9, row 16). v1 doesn't auto-cascade to next week.
- **Periodization-mode-shift handling (§10 row 9 + PSS-T2-15).** When 3B re-eval flips the periodization mode, T2 reshapes the week but doesn't propagate the shape change forward. The opportunity observation flags this. Real fix is T3 — surfacing this clearly in v1's UI is the followup.

**Best argument against this scope:**

T2 could be reduced to a thin wrapper over `Layer4_PerPhase_v1.md` — "take per-phase synthesis logic, apply to 1 week instead of N weeks, skip seam review." That framing is technically correct but loses the T2-specific affordances: weekly-shape reshape latitude, per-day phase mapping, cross-phase weighted distribution targets, deload/overreach cadence handling, athlete-intent dominance at week scope. These aren't reducible to per-phase logic-with-flags; they're a different prompt-engineering surface.

Counter: at N=1, athlete fires T2 maybe once per week. A simpler prompt would produce indistinguishable output 80% of the time. The 20% are exactly the cases where the framework pays off (sickness weeks, deload weeks, travel weeks, mid-week phase boundaries). Building the framework correctly once is the right investment.

Same logic as T1's §14.2 best-argument-against / counter. Per-tier investment justified at any non-trivial scale.

---

*End of Layer4_RefreshT2_v1.md.*
