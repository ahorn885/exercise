# Layer 4 — Single-Session Synthesizer Prompt Body (D-63)

**Prompt name:** `Layer4_SingleSession`
**Entry point:** `llm_layer4_single_session_synthesize` (`Layer4_Spec.md` §3.3)
**Pattern:** B (single LLM call + deterministic validator; no seam reviewer; no phase context)
**Caller:** D-63 on-demand workout (`OnDemand_Workout_D63_Design_v1.md`)
**Status:** v2 — tool-schema fidelity amendment (Step 4a implementation pairing)
**Date:** 2026-05-17 (v2); 2026-05-16 (v1 base)
**Position in arc:** Third of 5 prompt bodies (after `Layer4_SeamReviewer_v1.md`, `Layer4_PerPhase_v1.md`).
**v2 changes:** §4.1 tool schema rewritten to match the full `Layer4Payload.PlanSession` contract from `layer4/payload.py` (Andy 2026-05-17 Step 4a Option 2 pick). Adds explicit `intensity_zone` + `intensity_target` per cardio block (9-shape `IntensityTarget` `oneOf` union), `exercise_name` + `rest_between_sets_sec` + `tempo` per strength exercise, top-level `day_of_week` / `session_index_in_day` / `time_of_day`. Field-naming reconciled to payload contract (`reps_per_set`, `repetitions`/`rest_between_min`/`rest_intensity_zone` on interval blocks). All v1 §§1–3 + §§5–14 carry over unchanged; v1 coaching policy + injury exclusions + intensity-modulation tiers are unaffected.

---

## Source decisions (this session, Andy 2026-05-16)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Tool-use** (`record_single_session`); single tool, single call per invocation; strict JSON schema with `additionalProperties: false` at every nesting level. | Inherits seam-reviewer + per-phase convention. |
| D2 | Extended thinking budget | **~3500 tokens.** | Intensity-modulation is the load-bearing judgment; per-phase's 5000 was for combinatorial multi-week scope which doesn't apply here. ~3500 sits between the seam-reviewer's 2000 (pure judgment) and per-phase's 5000 (judgment + combinatorial). |
| D3 | Input format | **Full payloads verbatim** for 1 + 2A + 2D + 3A + `request`. No trimming. | ~3500 input budget fits comfortably; trimming risks losing signal on a small payload. |
| D4 | Prior-session-window rendering | **Hybrid: summary stats (ACWR + 7-day load + last-hard-session date) + last 7 days verbatim.** | Mirrors per-phase D4. ACWR + recent-hard-session signal is the §6.2 modulation trigger; stats alone lose granularity; verbatim alone misses the trend. |
| D5 | Closed-set `coaching_flags` enum | **3-flag D-63-only set:** `intensity_modulated`, `technique_emphasis`, `discipline_specific_intensity`. | Phase-tied flags (`long_slow_distance` / `overreach_test` / `race_pace_specific` / `weak_link_targeted`) don't apply outside phase context. `intensity_modulated` is the D-63-only cross-phase flag per `Layer4_Spec.md` §8.6. |
| D6 | Intensity-modulation policy | **Judgment + anchor signals + must-explain in `session_notes` when modulating.** | `Layer4_Spec.md` §3.3 + D-63 §6.2 frame this as coaching judgment; anchors (ACWR, recent-hard-session lookback, fatigue markers) ground the call; "must explain" ensures the `intensity_modulated` flag never fires silently. |
| D7 | Sport-unavailable handling | **Pre-LLM precondition (γ).** D-63 caller pre-checks sport availability; if unavailable, returns the unavailable response directly to the frontend. Layer 4 raises `Layer4InputError('request_sport_unavailable_at_locale')` defensively per `Layer4_Spec.md` §4.4 if the caller-side pre-check is missed. The LLM is never invoked on impossible requests; the rest-shape is reserved for genuine coaching-chosen rest days. (Paired spec amendment this session: §3.5, §4.4, §10.4, §13.4 TS-33 in Layer 4; §6.3 + §9 scenario 5 in D-63.) |
| D8 | `RuleFailure` retry context rendering | **Hybrid:** `rule_name + severity + detail + affected_session_id + suggested_constraint`. | Mirrors seam-reviewer "Observed: X. Constraint: Y" framing + per-phase D8. Suggested-constraint field is orchestrator-generated. |
| D9 | Schema-enforced length caps | **Tight: 240 chars `session_notes` / 200 chars `coaching_intent` / 120 chars `load_prescription` / 240 chars `instructions`.** | `max_tokens=1500` budget; tight caps prevent cap-hit retries on a small-output entry. Telemetry will measure cap-hit rates post-launch. |
| D10 | `notes_for_synthesizer` handling | **Verbatim-respect-unless-safety-blocker + overreach warning.** Honor the athlete's stated intent unless it conflicts with safety (injury exclusion, blocker validator rule). If 3A signals push toward overreaching AND the note pushes hard, surface the overreach risk explicitly in `session_notes`. Modulate intensity via D6 anchors only when signals are clear; otherwise honor + warn. | Andy 2026-05-16 override on my initial coaching-judgment-trumps recommendation. Three-tier policy: full honor → honor-with-warning → modulate-with-explanation. |
| D11 | Locale vs `quick_equipment` branching | **Unified prompt with conditional equipment block.** One file; template branches at the equipment-injection slot in §6. | Coaching logic is identical regardless of equipment-resolution path; only the input shape differs. |
| D12 | File location | `aidstation-sources/prompts/Layer4_SingleSession_v1.md` per the `prompts/` subdir convention from `Layer4_SeamReviewer_v1.md` D7. | Inherits. |
| D13 (v2 2026-05-17) | Tool-schema fidelity | **Full payload-contract mirror.** §4.1 tool schema mirrors the canonical `Layer4Payload.PlanSession` shape from `layer4/payload.py` rather than the v1 smaller sketch. LLM picks every coaching-relevant field including `intensity_zone` per cardio block + the discriminated `intensity_target` shape (9-shape `oneOf` union: HR/Power/Pace/SwimPace/RPE/VerticalRate/StrokeRate/Cadence/ClimbingGrade) + `exercise_name` + `rest_between_sets_sec` + optional `tempo`. Reconciled field naming (`reps_per_set`; `repetitions`/`rest_between_min`/`rest_intensity_zone` on interval cardio blocks). | Andy 2026-05-17 Step 4a Option 2 pick — chose maximal fidelity over LLM-compliance-burden minimization. Tool schema is what the orchestrator pins; payload contract is canonical. Tradeoff: larger LLM output budget on what was already a 1500-token-cap entry; v1 sketch had reconciliation gaps the post-process layer would have had to fill arbitrarily (intensity_zone per block; intensity_target shape; rest_between_sets_sec; exercise_name). Spec contract preserved verbatim — no `Layer4_Spec.md` §3.3 / §7 amendment required since the v1 prompt body's §4.1 sketch was explicitly v1-scoped per `Layer4_SingleSession_v1.md` line 134: "matching the `PlanSession` discriminated union per `Layer4_Spec.md` §7.2." |

**Companion contract sections (`Layer4_Spec.md`):** §3.3 (call signature), §3.5 (errors raised — `request_sport_unavailable_at_locale` added this session), §4.4 (input validation — sport-availability precondition added this session), §5.3 (Pattern B algorithm), §5.4 (deterministic validator — single-session scope: duration, intensity, locale equipment availability, injury exclusions; no weekly-volume or ACWR validator checks), §5.5 (capped retry semantics), §7.2/§7.3/§7.4 (`PlanSession` discriminated union + `CardioBlock` + `StrengthExercise`), §8.6 (`intensity_modulated` cross-phase flag — D-63-emittable), §8.7 (call-level observations — `intensity_modulated` orchestrator-side bubble; `opportunity` LLM-emitted exception), §10.4 (single-session edge cases — sport-unavailable row amended this session), §11.1 / §11.2 / §11.3 (latency / token / cost budgets — ~3s / ~3500 input + ~800 output / ~$0.02 typical).

---

## 1. Purpose + scope

### 1.1 What this prompt produces

One `PlanSession` matching the athlete's D-63 request — sport, duration, intensity, location — produced as a single tool call (`record_single_session`). The session is athlete-facing and immediately renderable as a workout card: structured cardio blocks (warmup / main_set / cooldown / interval_set / transition) for cardio sports, or a list of strength exercises with sets / reps / load prescription / form cues for strength sports. The session emits `is_ad_hoc=True`; the orchestrator persists it to `ad_hoc_workout_suggestions` (D-63 §5.3), not to `plan_versions` (`plan_version_id` is `None` for D-63 outputs).

### 1.2 What this prompt does NOT produce

- **Phase context.** D-63 sessions are ad-hoc and standalone; no `PhaseStructure`, no `SeamReview`, no phase metadata. The synthesizer cannot rely on "what phase is this in?" because the athlete may fire D-63 from any phase (including pre-plan).
- **Multi-session output.** Exactly one `PlanSession`. `len(sessions) == 1` is a hard invariant per `Layer4_Spec.md` §3.3.
- **Periodization decisions.** D-63 does not move the athlete forward or backward in their plan. It does not consume "next planned hard session" budget; the orchestrator separately handles the off-plan-day check per D-63 §6.4.
- **Observations or opportunities** other than the LLM-emitted `category='opportunity'` exception per §8.7. The `intensity_modulated` observation is orchestrator-computed from the LLM-emitted session flag.
- **Coaching commitment beyond the requested session.** Notes like "you should be doing X next week" or "your training plan needs Y" are out of scope — single-session is one workout, not a plan refresh.
- **Equipment resolution errors.** Sport-unavailable cases never reach this prompt (D-63 caller pre-checks per §6.3; Layer 4 raises defensively per §4.4 if missed).

### 1.3 Failure modes this prompt + retry semantics catch

- Athlete picked an intensity that conflicts with active injuries → validator `injury_violation_blocker` → capped retry with substitute exercises.
- Athlete picked equipment beyond what's available (in "Somewhere else" mode, the model tries to prescribe a barbell when athlete listed only dumbbells) → validator `equipment_unavailable` → capped retry constrained to listed equipment.
- Athlete picked a duration outside reasonable session range for the sport (e.g., 30-min ultra running) → handled in §4.4 precondition (`duration_out_of_range`), pre-LLM raise.

---

## 2. Pipeline placement

**Call site:** `llm_layer4_single_session_synthesize` per `Layer4_Spec.md` §3.3. Invoked by D-63 caller after §4 input validation (including sport-availability pre-check per §4.4 / D-63 §6.3).

**Pattern:** B per `Layer4_Spec.md` §5.3.
- Step 1: build context (this prompt's §3 inputs).
- Step 2: single LLM call (this prompt's §5 system + §6 user + §7 sampling config).
- Step 3: parse `record_single_session` tool output as a `PlanSession`.
- Step 4: deterministic validator (`Layer4_Spec.md` §5.4) — minimal scope: duration, intensity, locale equipment availability, injury exclusions; **no weekly-volume / ACWR / phase-shape checks** (one ad-hoc session doesn't carry periodization context).
- Step 5: capped retry per `Layer4_Spec.md` §5.5 on validator failure; cap=2 (default).
- Step 6: compose `Layer4Payload` with `mode='single_session_synthesize'`, `len(sessions)==1`, `sessions[0].is_ad_hoc=True`, `suggestion_id` populated, `phase_structure=None`, `seam_reviews=None`.

**Out-of-pipeline cases:**
- Cache hit per `Layer4_Spec.md` §9.1 single-session cache key → no LLM call; orchestrator rebinds `suggestion_id` per §9.4.
- Sport-unavailable per D-63 §6.3 → no LLM call; D-63 caller returns the unavailable response directly.
- Input validation failure per `Layer4_Spec.md` §4.4 → raises `Layer4InputError(code)`; no LLM call.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following variables. All are required unless noted optional. Token-budget realism per `Layer4_Spec.md` §11.2: ~3500 input tokens total.

### 3.1 Request payload (athlete-supplied)

| Variable | Source | Notes |
|---|---|---|
| `request.sport` | D-63 `SingleSessionRequest` | Layer 0A canonical sport name. Resolved via 2A inclusion (§4.4 precondition). |
| `request.duration_min` | D-63 | `30 ≤ n ≤ 360`. Pre-validated. |
| `request.intensity` | D-63 | `'easy' \| 'moderate' \| 'hard'`. Pre-validated. (Note: D-63 §4.3 also lists `'race_pace'`; v1 prompt treats `'race_pace'` as `'hard'` with `discipline_specific_intensity` flag emission since pure race-pace work outside a Peak/Taper context is rare for D-63 fires.) |
| `request.locale_slug` | D-63 | Athlete's locale slug, OR `None` for "Somewhere else". Pre-validated locale-vs-quick-equipment XOR per §4.4. |
| `request.quick_equipment` | D-63 | List of equipment tokens when `locale_slug is None`. Pre-validated XOR. |
| `request.notes_for_synthesizer` | D-63 | Optional athlete free-text. Honored per D10 verbatim-respect-unless-safety policy. |

### 3.2 Athlete + locale context

| Variable | Source | Notes |
|---|---|---|
| `athlete.user_id` | Layer 1 | Identification only; never used for coaching judgment. |
| `athlete.coaching_voice_preferences` | Layer 1 (when present) | Tone shading (e.g., "athlete prefers minimal mid-workout cueing"). |
| `athlete.experience_level` | Layer 1 | Beginner / intermediate / advanced / elite — drives technical complexity ceiling for exercise selection + form cue depth. |
| `athlete.discipline_inclusion` | Layer 2A | List of sports the athlete competes in / trains for. Used to flag `discipline_specific_intensity` when D-63 sport matches event-relevant discipline. |
| `athlete.active_injuries` | Layer 2D | Injury exclusions — hard constraints. Always respected; never overridable by `notes_for_synthesizer`. |
| `locale.effective_equipment_view` | Layer 2C (when `request.locale_slug` non-None) | Curated equipment list with Tier 1/2/3 substitution map. Source of truth for what exercises / activities are doable here. |
| `locale.label` | Layer 2C | Athlete-facing locale name (e.g., "Home Gym," "Hotel Gym Munich"). |

### 3.3 Recent training context (drives intensity modulation)

| Variable | Source | Notes |
|---|---|---|
| `athlete_state.acwr_7_28` | Layer 3A | Acute-chronic workload ratio for the picked sport (or aggregate if cross-discipline). Anchor signal #1 for intensity modulation per §9. |
| `athlete_state.seven_day_load` | Layer 3A | Total training load (TSS-equivalent or sport-specific) across the last 7 days. |
| `athlete_state.last_hard_session_date` | Layer 3A | Date of the most recent hard-intensity session (any sport). Anchor signal #2. |
| `athlete_state.last_hard_session_sport` | Layer 3A | Sport of last hard session — same-sport-yesterday signals different stress than cross-sport-yesterday. |
| `athlete_state.fatigue_markers` | Layer 3A (when present) | Subjective ratings (e.g., HRV trend, sleep score, RPE history) if integration data populated them. |
| `prior_session_window_summary` | Layer 3A rollup | Last 28 days: total volume, intensity distribution (% easy / moderate / hard), distinct sports trained. |
| `prior_session_window_recent` | Layer 3A | Last 7 days verbatim — sport, duration, intensity, date, completion status per session. Renders in §6 as a small table. |

### 3.4 Retry context (only present on retry pass)

| Variable | Source | Notes |
|---|---|---|
| `retries_used` | Orchestrator | 0 on first pass; 1 or 2 on retry. Cap = 2 per `Layer4_Spec.md` §5.5. |
| `rule_failures` | Validator | List of `RuleFailure` records from the prior pass. Each: `rule_name + severity + detail + affected_session_id + suggested_constraint`. Renders in §6 as constraint statements per D8. |

### 3.5 Intentionally NOT passed

- `layer3b_payload` (periodization shape) — D-63 doesn't require phase context; the synthesizer is explicitly phase-agnostic.
- `prior_plan_session_window` (planned-session continuity) — D-63 doesn't compete with the planned-session timeline. The off-plan-day check (D-63 §6.4) is orchestrator-side, not LLM-side.
- `layer2b_payload` (terrain) / `layer2e_payload` (nutrition) — out of scope for one ad-hoc session.
- `phase_metadata` / `seam_issues` / `seam_direction` — Pattern B; no seam reviewer.
- `event_date` / `race_format` — not race-relevant context.

---

## 4. Output schema + tool definition

The synthesizer emits exactly one tool call to `record_single_session`. The tool accepts a single `session` argument matching the `PlanSession` discriminated union per `Layer4_Spec.md` §7.2 (minus orchestrator-filled metadata: `session_id`, `plan_version_id`, `is_ad_hoc`, `ad_hoc_request_payload`, `phase_metadata`).

### 4.1 Tool schema (v2 — full payload-contract mirror per D13)

The canonical machine-readable tool schema is built at runtime by `layer4.single_session.build_record_single_session_tool()` (`layer4/single_session.py`). It mirrors `Layer4Payload.PlanSession` from `layer4/payload.py` minus the orchestrator-filled metadata (`session_id`, `plan_version_id`, `is_ad_hoc`, `ad_hoc_request_payload`, `phase_metadata`). The v2 amendment moved the source-of-truth from this prompt body to the on-disk `layer4/` package so the LLM tool schema and the pydantic parse target cannot drift.

**Required top-level `session` fields:** `date` (ISO date string), `day_of_week` (Mon–Sun), `session_index_in_day` (0 or 1), `time_of_day` (`morning|afternoon|evening|unspecified`), `kind` (`cardio|strength`), `duration_min` (30–360), `intensity_summary` (`easy|moderate|hard|mixed`), `session_notes` (≤240 chars), `coaching_intent` (≤200 chars), `coaching_flags` (closed enum per D5; max 3).

**Optional top-level `session` fields:** `discipline_id`, `discipline_name`, `locale_id`, `locale_name`, `cardio_blocks` (when `kind=='cardio'`), `strength_exercises` (when `kind=='strength'`), `rest_reason` (`rest`-kind only; D-63 typically omits).

**`cardio_blocks[]` required:** `block_kind` (`warmup|main_set|cooldown|interval_set|transition`), `duration_min` (1–300), `intensity_zone` (`Z1|Z2|Z3|Z4|Z5|mixed`), `intensity_target` (one of nine `oneOf` shapes — see below), `instructions` (≤240 chars). **Conditional on `block_kind=='interval_set'`:** `repetitions` (1–50), `rest_between_min` (≥0), `rest_intensity_zone` (`Z1|Z2`). Other block kinds leave those three fields null.

**`intensity_target` — nine `oneOf` shapes** (smart-union dispatch at parse; LLM picks shape matching sport):
- `HRTarget`: `{hr_bpm_low, hr_bpm_high}` (30–230) — universal endurance
- `PowerTarget`: `{power_w_low, power_w_high}` (0–2000) — bike / run / skimo / row
- `PaceTarget`: `{pace_per_km_low, pace_per_km_high}` (M:SS pattern) — run / hike / paddle / ski
- `SwimPaceTarget`: `{pace_per_100m_low, pace_per_100m_high}` (M:SS pattern) — swim
- `RPETarget`: `{rpe_low, rpe_high}` (1–10) — universal fallback
- `VerticalRateTarget`: `{vert_m_per_hr_low, vert_m_per_hr_high}` (0–3000) — skimo / hiking
- `StrokeRateTarget`: `{strokes_per_min_low, strokes_per_min_high}` (0–200) — swim / paddle / row
- `CadenceTarget`: `{rpm_low, rpm_high}` (0–250) — cycling
- `ClimbingGradeTarget`: `{grade_system, grade_min, grade_max}` (`yosemite_decimal|french_sport|uiaa`) — outdoor rock

**`strength_exercises[]` required:** `exercise_id` (Layer 0B canonical ID), `exercise_name` (human-readable), `resolution_tier` (1|2|3), `sets` (1–10), `reps_per_set` (integer 1–100 OR string like "AMRAP"), `load_prescription` (≤120 chars; free-form per athlete-facing wording), `rest_between_sets_sec` (0–600), `instructions` (≤240 chars), `coaching_flags` (open enum per `Layer4_Spec.md` §7.4; max 4). **Optional:** `substitute_text` (Tier 2 required), `proxy_origin_id` (Tier 3 required), `tempo` (E-IB-C-IT tuple convention, e.g., `"3-1-1-0"`).

```python
from layer4.single_session import build_record_single_session_tool
tool_schema = build_record_single_session_tool()
# Pass as Anthropic SDK tools=[tool_schema] with tool_choice forced to record_single_session.
```

### 4.2 Cross-session schema rules

| # | Rule | Enforcement |
|---|---|---|
| 1 | `kind=='cardio'` requires `cardio_blocks` non-empty; `strength_exercises` absent. | Prompt-rule + validator. |
| 2 | `kind=='strength'` requires `strength_exercises` non-empty; `cardio_blocks` absent. | Prompt-rule + validator. |
| 3 | `cardio_blocks[*].block_kind=='interval_set'` requires `interval_reps + interval_work_min + interval_recovery_min` all non-null. | Schema (validator confirms). |
| 4 | `cardio_blocks[*].block_kind ∈ {warmup, main_set, cooldown, transition}` requires all three interval fields null. | Prompt-rule (schema can't conditionally forbid). |
| 5 | `strength_exercises[*].resolution_tier == 1` → `substitute_text` null + `proxy_origin_id` null. | Prompt-rule + validator. |
| 6 | `strength_exercises[*].resolution_tier == 2` → `substitute_text` non-null. | Prompt-rule + validator. |
| 7 | `strength_exercises[*].resolution_tier == 3` → `proxy_origin_id` non-null. | Prompt-rule + validator. |
| 8 | `coaching_flags` is a closed set per D5; no other values valid. Schema enforces. Unknown values raise `unknown_coaching_flag_<name>` per §5.5. | Schema enum. |
| 9 | Sum of `cardio_blocks[*].duration_min` must equal `session.duration_min ± 5 min` (cardio sessions). | Validator. |
| 10 | Strength session estimated duration (sets × reps × rest cadence per `Layer4_Spec.md` §5.4 timing model) must approximate `session.duration_min ± 10 min`. | Validator. |
| 11 | When `intensity_modulated` flag is present, `session_notes` must explicitly explain the modulation per D6 must-explain rule. | Prompt-rule (no programmatic check; coaching review surface). |
| 12 | `opportunities` is the LLM-emitted exception per `Layer4_Spec.md` §8.7; max 2 entries; only fires when a coaching opportunity is materially distinct from the session's `session_notes`. | Schema cap + prompt-rule. |

---

## 5. System prompt (verbatim)

```
You are AIDSTATION's single-session workout synthesizer. The athlete has fired an on-demand workout request through D-63: pick a sport, pick a duration, pick an intensity, pick a location (saved locale or "somewhere else" with quick equipment). Your job is to produce one structured workout matching the request, respecting active injuries and recent training load, in a direct coaching voice.

# What you produce

Exactly one PlanSession via the `record_single_session` tool. The session is athlete-facing and immediately renderable as a workout card. Use:
- `cardio_blocks` for cardio sports (warmup / main_set / cooldown structure; add interval_set blocks for interval work; add transition blocks for sport-transitions like brick workouts)
- `strength_exercises` for strength sports (sets / reps / load_prescription / instructions; exercise_id references Layer 0B exercise library)

`is_ad_hoc=True` is filled by the orchestrator; you do not emit it.

# Coaching voice (apply to all athlete-facing text fields: session_notes, coaching_intent, instructions)

- Direct. Factual. Evidence-grounded.
- No platitudes ("great workout!"), no hype ("crush it!"), no cheerleading ("you've got this!").
- Tone matches a real endurance coach talking to a serious athlete.
- Short sentences. Plain English. No emoji.

# Intensity modulation policy (three-tier)

The athlete's picked intensity is the structural intent. Honor it by default. When recent training load signals push back, apply this three-tier policy:

**Tier 1 — Full honor.** When recent-load signals are neutral or favorable (ACWR ≤ 1.10, no hard session in the last 36 hours, no fatigue-marker red flags): prescribe the session at the athlete's picked intensity. No flag emitted.

**Tier 2 — Honor with warning.** When signals show mild overreach risk (ACWR 1.10–1.25, OR a hard session 24–48 hours ago in the same sport, OR mild fatigue markers): prescribe the session at the athlete's picked intensity, but include an explicit overreach-risk note in `session_notes`. Example phrasing: "ACWR is climbing; back-to-back hard days carry overreach risk. Watch your subjective effort and pull back if it climbs above what the structure prescribes." No `intensity_modulated` flag (intensity wasn't modulated).

**Tier 3 — Modulate with explanation.** When signals are clear-cut overreach (ACWR > 1.25, OR a hard session in the last 24 hours in the same sport AND elevated 7-day load, OR strong fatigue-marker signals): modulate the prescribed intensity downward by one tier (hard → moderate; moderate → easy). Emit `intensity_modulated` in `coaching_flags`. Explain the modulation in `session_notes` in two sentences max — what the athlete picked, why you're modulating, what to expect from this session instead. Example: "You picked hard; recent ACWR is 1.31 and yesterday was a hard run. Prescribing moderate today to let the high-intensity stimulus consolidate."

The athlete's `notes_for_synthesizer` text is honored as structural intent (Tier 1) UNLESS Tier 3 signals are clear. Safety blockers (injury exclusion, validator hard-constraint) always override the athlete's note regardless of tier.

# Injury exclusions (hard constraints; never overridable)

Active injuries in `layer2d_payload` are hard constraints. Never prescribe exercises that load the affected joint / muscle / movement pattern. Substitute via Layer 2C Tier 2 (athlete-listed substitute) or Tier 3 (Layer 0B exercise-library nearest-neighbor proxy) — populate `substitute_text` or `proxy_origin_id` accordingly. If no safe substitute exists for a critical exercise, change the session structure (drop the offending block; add an alternative discipline-appropriate block); do not silently include the unsafe exercise.

# Equipment respect

When `request.locale_slug` is non-None: prescribe only from `layer2c_payload_for_locale.effective_equipment_view`. The Tier 1/2/3 substitution map applies. Tier 1 (direct match) preferred; Tier 2 (athlete-listed substitute) acceptable; Tier 3 (Layer 0B proxy) for fallback only.

When `request.quick_equipment` is non-empty (athlete is "Somewhere else"): prescribe only from `request.quick_equipment` plus bodyweight movements (always available). No Tier 2/3 substitution available — the athlete has supplied an exhaustive list. If a sport requires equipment beyond this list, fall back to bodyweight-doable variants in the same movement pattern. State the constraint explicitly in `session_notes`.

# Discipline-specific intensity flag

When `request.sport` matches the athlete's primary discipline (per `layer2a_payload.discipline_inclusion`) AND `request.intensity == 'hard'`: emit `discipline_specific_intensity` in `coaching_flags`. This signals to downstream consumers that the session counts as race-specific high-intensity training. If the sport is incidental to the athlete's discipline mix (e.g., a triathlete doing a strength session), do not emit this flag.

# Technique emphasis flag

When `request.notes_for_synthesizer` explicitly requests technique work ("focus on form," "drills only," "let's smooth out my MTB descents") OR the session structure prioritizes technique over volume/intensity (e.g., a 60-min run divided into form drills + low-intensity recovery jogging rather than steady-state running): emit `technique_emphasis` in `coaching_flags`. Coaching intent should reflect the technique focus in `session_notes`.

# Authority bounds — explicit forbid list

You MUST NOT:
1. Modify `request.sport` — if the sport is unavailable, the request was supposed to be pre-checked and never reach you. If you receive an impossible request, fall back to a sport-agnostic equipment-doable session and explain in `session_notes`; this is a defensive path, not normal operation.
2. Emit more than one session. `len(sessions) == 1` is the entry-point contract.
3. Emit phase-tied coaching flags (`long_slow_distance`, `overreach_test`, `weak_link_targeted`, `race_pace_specific`). These belong to per-phase synthesis, not single-session.
4. Emit `Observation` rows. The `opportunity` category is the only LLM-emitted exception; emit via the `opportunities` field on the session, not as a separate top-level entity.
5. Mutate the prescribed duration outside ±5 min for cardio or ±10 min for strength. The athlete's picked duration is a structural commitment.
6. Move the athlete forward or backward in their training plan. D-63 is one workout, not a periodization decision.
7. Reference the athlete's wrist injury or any active injury by name in athlete-facing text UNLESS the injury directly shapes a substitution decision the athlete will see (e.g., "Push-up variant: fist position — wrist-load substitute"). Routine substitutions stay silent; the athlete already knows their injury.
8. Use the verbatim wording of athlete-supplied phrases from `notes_for_synthesizer` as session text without paraphrasing — the note is signal for you, not copy for the athlete.

# Iteration discipline (when `retries_used > 0`)

On retry, the orchestrator passes `rule_failures` describing what the validator caught. Treat each failure as a hard constraint: `rule_name + severity + detail + suggested_constraint`. Don't argue with the validator; adjust the session to clear the failure while preserving as much of the athlete's request as possible. Severity `blocker` means the session is unshippable as drafted; severity `warn` means optional adjustment (but acknowledge in `session_notes` if you decline). After two retries the cap exhausts and best-effort output ships with an orchestrator-emitted `best_effort_plan` Observation — your job on each retry is to maximize the chance of validator-pass while still satisfying the athlete's structural request.

# Output discipline

- One tool call per invocation. Do not emit prose outside the tool call.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- `coaching_intent` is a one-line summary of the session's purpose; `session_notes` is 1–3 short sentences of context (modulation explanation, technique focus, location-specific cues).
- Numeric durations always integers (or half-integer where the schema allows).
- Exercise IDs reference Layer 0B canonical IDs; if you use a Tier 2 substitute, populate `substitute_text` with the human-readable substitution; if Tier 3, populate `proxy_origin_id` with the canonical ID of the parent exercise.
```

---

## 6. User prompt template (verbatim, Mustache-style)

```
# Athlete request

Sport: {{request.sport}}
Duration: {{request.duration_min}} min
Intensity: {{request.intensity}}
{{#request.locale_slug}}Location: {{locale.label}} (saved locale `{{request.locale_slug}}`){{/request.locale_slug}}
{{^request.locale_slug}}Location: Somewhere else (athlete-supplied equipment){{/request.locale_slug}}
{{#request.notes_for_synthesizer}}Athlete note: "{{request.notes_for_synthesizer}}"{{/request.notes_for_synthesizer}}

# Athlete context

User ID: {{athlete.user_id}}
Experience level: {{athlete.experience_level}}
{{#athlete.coaching_voice_preferences}}Voice preferences: {{athlete.coaching_voice_preferences}}{{/athlete.coaching_voice_preferences}}
Disciplines (Layer 2A inclusion): {{athlete.discipline_inclusion}}

## Active injuries (hard constraints)

{{#athlete.active_injuries}}
- {{name}}: {{description}} — avoid: {{exclusions}}
{{/athlete.active_injuries}}
{{^athlete.active_injuries}}
- None on file.
{{/athlete.active_injuries}}

# Equipment

{{#request.locale_slug}}
## Curated equipment view ({{locale.label}})

The locale's effective equipment view from Layer 2C — Tier 1 direct matches, Tier 2 athlete-listed substitutes, Tier 3 nearest-neighbor proxies from the Layer 0B exercise library. Prefer Tier 1 when present; Tier 2 acceptable; Tier 3 fallback.

{{locale.effective_equipment_view}}
{{/request.locale_slug}}
{{^request.locale_slug}}
## Athlete-supplied equipment (no curated substitutes; this list is exhaustive)

{{request.quick_equipment}}

The athlete has listed exactly this equipment. There are no Tier 2/3 substitutes available — the substitution map only exists for saved locales. If the sport requires equipment beyond this list, fall back to bodyweight-doable variants in the same movement pattern and state the constraint in `session_notes`.
{{/request.locale_slug}}

# Recent training context (drives intensity-modulation policy from §5)

## Summary statistics (last 28 days)

- ACWR (7d / 28d): {{athlete_state.acwr_7_28}}
- 7-day total load: {{athlete_state.seven_day_load}}
- Last hard session: {{athlete_state.last_hard_session_date}} ({{athlete_state.last_hard_session_sport}})
- Intensity distribution: {{prior_session_window_summary.intensity_distribution}}
- Distinct sports trained: {{prior_session_window_summary.distinct_sports}}
- Total 28-day volume: {{prior_session_window_summary.total_volume_min}} min
{{#athlete_state.fatigue_markers}}
- Fatigue markers: {{athlete_state.fatigue_markers}}
{{/athlete_state.fatigue_markers}}

## Last 7 days verbatim

| Date | Sport | Duration | Intensity | Completed |
|---|---|---|---|---|
{{#prior_session_window_recent}}
| {{date}} | {{sport}} | {{duration_min}} min | {{intensity}} | {{completion_status}} |
{{/prior_session_window_recent}}
{{^prior_session_window_recent}}
| (no sessions in window) |
{{/prior_session_window_recent}}

{{#retries_used}}
# Retry context (this is retry pass {{retries_used}} of 2)

The deterministic validator flagged the prior pass. Adjust to clear these failures while preserving as much of the athlete's request as possible.

{{#rule_failures}}
- Rule: `{{rule_name}}` | Severity: {{severity}} | Detail: {{detail}}
  Suggested constraint: {{suggested_constraint}}
{{/rule_failures}}
{{/retries_used}}

# Your task

Produce one workout session matching the athlete's request. Apply the intensity-modulation policy from §5. Respect injury exclusions absolutely. Stay within the equipment available. Emit via the `record_single_session` tool. One tool call. No prose outside the tool call.
```

---

## 7. Model + sampling config

| Param | Value | Rationale |
|---|---|---|
| `model` | `claude-sonnet-4-6` | Per `Layer4_Spec.md` §3.3 default. |
| `temperature` | `0.3` | Per `Layer4_Spec.md` §3.3 default — higher than Pattern A's 0.2; athlete-facing [Regenerate] benefits from variation. |
| `max_tokens` | `1500` | Per `Layer4_Spec.md` §3.3 default. Single-session output fits comfortably; tight cap discourages output bloat. |
| `extended_thinking.enabled` | `true` | Per D2. Intensity modulation needs deliberation. |
| `extended_thinking.budget_tokens` | `3500` | Per D2. Mid-defensive — judgment work but smaller scope than per-phase. |
| `tool_choice` | `{"type": "tool", "name": "record_single_session"}` | Forced single tool. |
| `stop_sequences` | (none) | Tool stops naturally. |

**Token + cost accounting per invocation:**

- Input tokens: ~3500 (system + user + tool schema)
- Extended thinking: ~3500 (counted toward output budget at Sonnet 4.6 pricing)
- Output tokens (tool call): ~800
- Total cost per `single_session_synthesize`: ~$3.5e-3 input + ~$15e-3 × (3.5+0.8)/1000 = ~$0.075 thinking + output = ~**$0.075 per invocation worst-case** (matches `Layer4_Spec.md` §11.3 ~$0.02 typical headline; the $0.02 figure assumes extended-thinking isn't counted toward output billing at typical reasoning depth — measure post-launch).

**Latency expectation:** ~3–6s per `Layer4_Spec.md` §11.1.

---

## 8. Authority bounds — explicit forbid list

Recap of §5 in-band rules + enforcement mechanism for downstream review.

| # | Rule | Enforcement |
|---|---|---|
| 1 | Never modify `request.sport`. | Prompt + validator (sport equality check). |
| 2 | Exactly one session. `len(sessions) == 1`. | Schema (one tool call; one session object). |
| 3 | Never emit phase-tied flags. | Schema enum (closed-set 3-flag). |
| 4 | Never emit `Observation` rows directly. | Schema (no Observation field at session level; `opportunities` is the LLM-emitted exception per §8.7). |
| 5 | Never mutate prescribed duration outside ±5 / ±10 min. | Validator (duration delta check). |
| 6 | Never move athlete forward/backward in plan. | Out-of-output-shape — `plan_version_id` is `None`; orchestrator-side enforcement. |
| 7 | Never name injuries in athlete-facing text unless directly shaping a substitution. | Prompt-rule (no programmatic check). |
| 8 | Never use `notes_for_synthesizer` verbatim as session text. | Prompt-rule. |
| 9 | Never include exercises that violate active injury exclusions. | Validator `injury_violation_blocker`. |
| 10 | Never prescribe equipment beyond what's in locale view or `quick_equipment`. | Validator `equipment_unavailable`. |
| 11 | When `intensity_modulated` flag present, must explain in `session_notes`. | Prompt-rule (coaching review surface). |

---

## 9. Verdict calibration — coaching anchors

### 9.1 Intensity-modulation anchor signals (drives §5 three-tier policy)

Concrete signal thresholds the model uses to determine which tier applies. Override-with-rationale is the v1 default — anchors ground the call but are not hard thresholds.

| Tier | ACWR (7d/28d) | Last-hard-session lookback | Same-sport flag | 7-day load vs 28-day baseline | Fatigue markers | Action |
|---|---|---|---|---|---|---|
| 1 — Full honor | ≤ 1.10 | > 36h ago | n/a | within ±15% | neutral / favorable | Prescribe at picked intensity; no flag |
| 2 — Honor with warning | 1.10–1.25 | 24–48h ago | n/a | up to +25% | mild signals | Prescribe at picked intensity; warn in `session_notes`; no flag |
| 3 — Modulate | > 1.25 | ≤ 24h ago | yes (same-sport amplifies) | > +25% | clear signals | Modulate down one tier (hard→moderate; moderate→easy); emit `intensity_modulated`; explain in `session_notes` |

Edge cases:
- Easy-intensity request never modulates (already at the lowest meaningful intensity for a workout). At most: warn in `session_notes` if ACWR > 1.25 ("consider taking a rest day instead").
- Cross-sport last-hard-session (e.g., yesterday was a hard run; today's request is hard strength) is weaker signal than same-sport. Tier 2 typical, Tier 3 only when other signals also fire.
- Missing data (e.g., `last_hard_session_date` is None because athlete is brand new) defaults to Tier 1. Don't manufacture signals from absent data.

### 9.2 `notes_for_synthesizer` interaction with the three-tier policy (D10)

The athlete's note is honored as structural intent (Tier 1 default). The interaction with anchor signals:

| Tier | `notes_for_synthesizer` behavior |
|---|---|
| 1 — Full honor | Note is honored as written (within safety constraints). Apply technique-emphasis / discipline-specific-intensity flags if applicable. |
| 2 — Honor with warning | Note is honored; the overreach warning lives in `session_notes` alongside any technique / discipline framing the note requested. Athlete sees both. |
| 3 — Modulate | Note is honored structurally (e.g., athlete asked for hill repeats → still prescribe hill repeats) but intensity is modulated (e.g., easier hills, fewer reps, lower-grade hills). Explain the modulation; reference the athlete's stated intent. |

**Safety blockers always override.** If the note pushes toward an unsafe option (e.g., "let's do heavy overhead presses today" + active wrist injury), substitute the unsafe exercise regardless of tier. Don't preserve unsafe exercises just because the athlete asked.

### 9.3 Substitution decision anchors

When picking Tier 1 vs Tier 2 vs Tier 3 for strength exercises (Layer 2C substitution map):

- **Tier 1** (direct match — exact exercise in locale's curated view): prefer when present. Highest fidelity to the athlete's expected experience.
- **Tier 2** (athlete-listed substitute — athlete has explicitly told 2C "I do X here instead of Y"): use when Tier 1 isn't available. Populate `substitute_text` with the human-readable mapping.
- **Tier 3** (Layer 0B exercise-library nearest-neighbor proxy): fallback only — when neither Tier 1 nor Tier 2 covers the movement pattern. Populate `proxy_origin_id` with the canonical exercise ID being proxied. State the substitution in `instructions`.

---

## 10. `coaching_flags` closed-set rules

D-63-emittable flags. The closed-set enum is enforced at the schema level; emitting any other flag string raises `unknown_coaching_flag_<name>` per `Layer4_Spec.md` §5.5.

| Flag | Phase tie | Emit on | Frequency | Conflicts |
|---|---|---|---|---|
| `intensity_modulated` | Cross-phase / D-63-only (§8.6) | Tier 3 modulation per §9.1 fires | At most once per session (D-63 produces one session, so always 0 or 1) | Mutually exclusive with no-modulation case (Tier 1 + Tier 2 forbid this flag) |
| `technique_emphasis` | Per-session (any phase) | Athlete note requests technique work OR session structure prioritizes form over volume/intensity | At most once per session | Compatible with all other flags |
| `discipline_specific_intensity` | Per-session (Build/Peak typical; D-63 fires it on any phase) | `request.sport` matches `layer2a_payload.discipline_inclusion` primary AND `request.intensity == 'hard'` | At most once per session | Compatible with `intensity_modulated` (note that intensity-modulated-from-hard-to-moderate may still flag discipline-specific if the athlete's stated intent was hard; surface in `session_notes` that the modulation softens the discipline-specific framing) |

**Phase-tied flags excluded from D-63:** `long_slow_distance`, `overreach_test`, `weak_link_targeted`, `race_pace_specific`. These require phase context the synthesizer doesn't have. If the athlete-requested session happens to look like one of these conceptually (e.g., a 4-hour easy run looks like LSD), the session structure conveys it in `coaching_intent` + `session_notes`; the flag doesn't fire. Per-phase synth retains exclusive authority over phase-tied flags.

**`StrengthExercise.coaching_flags`** stays open-set per `Layer4_Spec.md` §7.4 examples (e.g., `eccentric_emphasis`, `unilateral_focus`). No enum.

---

## 11. Edge cases + invalid combinations

| # | Case | Handling |
|---|---|---|
| 1 | Athlete picks intensity that conflicts with active injuries (e.g., hard upper-body strength + active wrist injury) | Validator `injury_violation_blocker` → capped retry with Tier 2/3 substitutes. If retry exhausts: best-effort session shipped + orchestrator-emitted `Observation(category='warning', elevates_to_hitl=True, text='all standard upper-body strength options blocked by active wrist injury; recommended rest day')`. |
| 2 | Athlete picks "Somewhere else" + lists equipment insufficient for sport (e.g., MTB but listed only running shoes) | The §4.4 sport-availability precondition catches this before LLM invocation per D7. If the pre-check is bypassed defensively: synthesizer falls back to bodyweight movements in the sport's movement pattern; states the constraint in `session_notes`. |
| 3 | Athlete picks `intensity='hard'` but anchor signals are Tier 3 overreach | Modulate to moderate; emit `intensity_modulated`; explain in `session_notes`. Honor the structural intent (e.g., if "hard hill repeats," prescribe moderate hill repeats — fewer / less steep). |
| 4 | Athlete picks `intensity='hard'` + Tier 2 (mild signals) + `notes_for_synthesizer = "let's go really hard today"` | Honor + warn per D10 + §9.2. Prescribe at hard; surface overreach risk in `session_notes`; reference the athlete's stated intent. No `intensity_modulated` flag. |
| 5 | Athlete picks `'race_pace'` intensity per D-63 §4.3 schema | Treat as `'hard'` with `discipline_specific_intensity` flag (if sport matches discipline). v1 doesn't have a separate race-pace prescription path outside per-phase Peak/Taper context. |
| 6 | Validator fires `equipment_unavailable` on retry pass 1 | Re-prompt with `suggested_constraint: "use only equipment from the listed pool: [...]"`. Re-emit the session. |
| 7 | Validator fires `duration_violation` (e.g., cardio_blocks sum to 75 min vs requested 60) | Re-prompt with `suggested_constraint: "cardio_blocks must sum to 60 min ± 5"`. Re-balance block durations. |
| 8 | Retry cap exhausts (2 retries failed) | Best-effort session ships; orchestrator emits `Observation(category='best_effort_plan', elevates_to_hitl=True)` per §8.7. The session is still produced; the athlete sees it with the warning surface. |
| 9 | Cache hit on byte-identical request | Per `Layer4_Spec.md` §9.4: orchestrator returns cached `Layer4Payload` with a freshly-allocated `suggestion_id` rebound; no LLM call; this prompt body doesn't run. |
| 10 | `request.sport` is technically in 2A inclusion but the athlete has no recent training in it (e.g., listed adventure racing but trained only running this year) | Synthesize normally; emit `discipline_specific_intensity` only when hard AND the sport is the athlete's primary discipline. Athlete-driven discovery via D-63 is allowed. |
| 11 | Athlete fires D-63 mid-Peak-week with `intensity='easy'` after a planned hard session yesterday | Anchor signals likely Tier 1 (easy intensity rarely modulates); prescribe an easy recovery-oriented session; note the recovery context in `session_notes`. Off-plan-day check is orchestrator-side (D-63 §6.4); not this prompt's concern. |
| 12 | `notes_for_synthesizer` requests something out of scope (e.g., "design my next 4 weeks") | Ignore the out-of-scope portion silently. Honor anything in-scope (e.g., if the same note says "and today focus on hills," do that). Don't lecture the athlete in `session_notes` about scope. |
| 13 | Empty or extremely sparse `prior_session_window_recent` (brand-new athlete, no logged sessions) | Default to Tier 1 honor; treat absent data as neutral signal per §9.1. Don't manufacture caution from absent data. |
| 14 | First-pass output is malformed (schema-level violation: e.g., `kind='cardio'` with no `cardio_blocks`) | Validator catches; orchestrator retries with `RuleFailure: schema_violation_<field>` + `suggested_constraint`. |

---

## 12. Test scenarios (v1)

PSS-prefix (Per-Single-Session). Map to existing `Layer4_Spec.md` §13.4 single-session scenarios + §13.6 coaching-flag emit scenarios + §13.7 cache hit/miss scenarios. These are LLM-output tests for the prompt itself; they slot under §13.4 / §13.6 / §13.7 if the spec ever expands per-prompt-body.

| # | Scenario | Inputs | Expected output |
|---|---|---|---|
| **PSS-1** | Happy path — locale, no modulation | Andy: run, 60min, easy, home_base; ACWR 0.95; no recent hard; no injuries | One cardio session; `cardio_blocks` sums to 60 min ±5; no flags; `coaching_intent` reflects easy aerobic; validator passes |
| **PSS-2** | Happy path — quick_equipment | Andy: strength, 45min, moderate, "somewhere else" with [dumbbells, bench]; no injuries | One strength session; exercises ∈ {dumbbell, bench-supported, bodyweight}; no Tier 2/3 — uses listed equipment only; `coaching_flags` empty |
| **PSS-3** | Intensity modulation Tier 3 | Andy: MTB, 90min, hard; ACWR 1.31; last hard ride yesterday | Modulated to moderate; `intensity_modulated` flag; `session_notes` explains: "you picked hard; recent ACWR + yesterday's hard ride suggest moderate today" |
| **PSS-4** | Tier 2 honor-with-warning | Andy: run, 45min, hard; ACWR 1.18; last hard run 36h ago | Prescribed at hard; no `intensity_modulated` flag; `session_notes` surfaces overreach risk |
| **PSS-5** | `notes_for_synthesizer` honored + technique flag | Andy: MTB, 60min, easy, home_base; note: "drills only — let's smooth out my descents" | One cardio session structured as technique drills + easy spinning; `technique_emphasis` flag; `coaching_intent` reflects skill focus |
| **PSS-6** | `discipline_specific_intensity` emit | Andy: trail running, 90min, hard; primary discipline includes trail running | One cardio session at hard intensity; `discipline_specific_intensity` flag |
| **PSS-7** | Wrist injury + upper-body strength request | Andy: strength, 60min, moderate, home_gym; active wrist injury | One strength session; exercises avoid wrist-extension loading; pushup variant in fist position (Tier 2 substitute); validator passes |
| **PSS-8** | Wrist injury + all-upper-body-strength-blocked retry path | Synthetic: strength, 60min, hard with active wrist injury blocking every standard upper-body lift | First pass fails `injury_violation_blocker`; retry with Tier 2/3 substitutes — lower-body focus + wrist-safe upper-body work emerges; if retry exhausts: best-effort + warning Observation per §10 row 1 |
| **PSS-9** | Equipment-fallback in quick_equipment mode | Andy: strength, 45min, hard, "somewhere else" with [dumbbells]; no bench | One strength session; no bench-supported exercises; uses dumbbell standing / floor variants + bodyweight; `session_notes` acknowledges the bench absence |
| **PSS-10** | Retry on `duration_violation` | First pass: cardio_blocks sum to 75 min vs requested 60 | Retry with `suggested_constraint: "cardio_blocks must sum to 60 min ±5"`; re-balanced output passes |
| **PSS-11** | `race_pace` intensity treatment | Andy: trail running, 60min, race_pace; primary discipline | Treated as `hard` with `discipline_specific_intensity` flag; `session_notes` notes race-pace framing |
| **PSS-12** | Brand-new athlete (no Layer 3A history) | Synthetic: run, 45min, moderate; ACWR null; last_hard_session_date null | Tier 1 honor (absent data = neutral); prescribed at moderate; no flags |
| **PSS-13** | Tier 3 modulation + athlete note pushing back | Andy: hill repeats, 60min, hard, home_base; note: "I want to crush these today"; ACWR 1.30 + yesterday hard | Modulated to moderate hill repeats (fewer / less steep); `intensity_modulated`; `session_notes` references both the athlete's intent and the modulation — honors structural intent, modulates intensity |
| **PSS-14** | `opportunities` LLM-emit exception | Andy: MTB, 60min, moderate, home_base; note hints at recurring climb-fatigue issue | One MTB session + one opportunity entry: "MTB climb volume has trended up over 3 weeks — consider a dedicated climb-strength session in the next plan refresh" |
| **PSS-15** | Cache-hit replay (verification — prompt should NOT run) | Same byte-identical request fired twice within cache TTL | Test fixture verifies cache layer returns cached payload with rebound `suggestion_id`; this prompt body should not execute |

---

## 13. Open items / tuning candidates

v1 defaults; measure post-launch.

1. **Extended thinking budget (D2 ~3500)** — drop to ~2000 if quality holds on intensity modulation; bump to ~5000 if Tier-3 calls feel rushed.
2. **`max_tokens=1500`** — bump to 2000 if cap-hits observed in telemetry, esp. on multi-block cardio sessions (5+ blocks) or detailed strength prescriptions (8+ exercises).
3. **Closed-set flag enum (D5: 3 flags)** — re-evaluate at 3-month telemetry checkpoint. If `weak_link_targeted` cases surface in D-63 fires that aren't well-served by `technique_emphasis`, consider adding (spec amendment per stop-and-ask trigger #5).
4. **Intensity-modulation anchor thresholds (§9.1)** — ACWR cut-offs 1.10/1.25, lookback windows 24h/36h/48h, ±15%/±25% load deltas. Tune from production data. Anchor table not hard threshold.
5. **Schema length caps (D9: 240/200/120/240)** — tighten or loosen based on cap-hit rates. Tight is the v1 default to discourage output bloat in a small-budget entry.
6. **`notes_for_synthesizer` overreach-warning phrasing** — the example phrasings in §5 are starting points. Refine from athlete feedback / coaching review.
7. **Tier 2 honor-with-warning calibration** — the ACWR 1.10–1.25 band is the v1 default; the band may need tightening if athletes report the warnings as nagging vs useful.
8. **Same-sport vs cross-sport hard-session weighting (§9.1)** — currently "amplifies" same-sport; quantify the amplification factor from data.
9. **`'race_pace'` intensity handling (§11 row 5)** — v1 treats as `'hard'` with `discipline_specific_intensity`. A future spec amendment could add `race_pace` as a distinct intensity tier with its own prescription pattern.
10. **Cache-key composition for D-63** — per `Layer4_Spec.md` §9.1; v1 includes request fields + 3A snapshot + 2C version. Verify hit rate matches §11.4 assumptions in production.
11. **Off-plan-day awareness** — D-63 §6.4 puts this orchestrator-side. If athletes want LLM-side framing (e.g., "you have a planned tempo run today; this ad-hoc session is in addition"), surface it in `session_notes` — but the v1 default keeps the synthesizer phase-agnostic.
12. **Equipment-resolution telemetry** — track Tier 1 / Tier 2 / Tier 3 distribution across D-63 fires. High Tier 3 rate signals 2C resolution gaps; high Tier 2 rate is fine (athletes correctly listing substitutes).

---

## 14. Gut check — deferred to Layer 4 §14 retro

Per `Layer4_Spec.md` §12.6, §14 retro is a fresh-eyes pass over the full Layer 4 spec arc that lands before implementation. This prompt body's gut check folds into that retro rather than living standalone here.

**Risks flagged for the retro to fold in:**

1. **Tier 2 honor-with-warning is a new pattern in the prompt-body arc.** Seam-reviewer + per-phase don't have a "honor + warn" middle ground (modulation is binary). Worth checking whether the three-tier policy generalizes back to per-phase intensity decisions or stays D-63-only.
2. **Intensity-modulation anchor thresholds (ACWR 1.10/1.25, etc.) are v1 defaults with no production calibration.** Per-phase has the same v1-defaults issue with deload cadence + Taper length, but the per-phase anchors are coarser-grained (week-level) than D-63 (session-level). Per-session anchors will likely need tuning sooner.
3. **`'race_pace'` intensity collapses to `'hard'` + flag** is a v1 simplification that may friction with athletes who specifically want race-pace work outside Peak/Taper context. v2 could split.
4. **`notes_for_synthesizer` honor-vs-modulate policy is intricate** (§9.2 + D10 three-tier). Risk that athletes feel the synthesizer is ignoring their note when modulation fires. Consider whether the explanation in `session_notes` is sufficient or whether a frontend-side affordance ("the system softened your request because of recent load — override?") helps.
5. **Cache-key composition includes 3A snapshot** which changes daily. Effective cache hit rate for D-63 will be low (most fires are unique) — the cache spec acknowledges this. Confirm in production that the orchestrator-side cache lookup overhead doesn't dominate the LLM-call cost.
6. **D-63 fires that look like phase-tied work (e.g., a 4hr easy run that's effectively LSD)** silently lose the flag because phase-tied flags are excluded. Some downstream consumers (e.g., weekly load aggregators) may benefit from a "looks like LSD" inference even outside phase context. Push to per-phase synth domain instead of widening D-63's flag set.

---

**End of prompt body.**
