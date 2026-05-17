# Layer 4 — Plan Refresh T3 Synthesizer Prompt Body (D-64)

**Prompt name:** `Layer4_RefreshT3`
**Entry point:** `llm_layer4_plan_refresh` with `tier='T3'` AND scope inside a single phase (`Layer4_Spec.md` §3.2 + §5.1 + §6.3 single-phase T3 special case)
**Pattern:** B (single LLM call + deterministic validator; no seam reviewer; no phase decomposition) — applies to T3 intra-phase ONLY
**Caller:** D-64 athlete-initiated 28-day refresh (`Plan_Refresh_D64_Design_v1.md` §3.3)
**Status:** v1 — draft
**Date:** 2026-05-17
**Position in arc:** Sixth prompt body shipped post-arc (after the 5-of-5 arc closed 2026-05-17). T3 cross-phase routes to Pattern A and uses the `Layer4_PerPhase_v1.md` per-phase synthesizer (one call per phase); T3 cross-phase orchestration lands with Step 4f.

---

## Source decisions (this session, Andy 2026-05-17 Step 4d)

Inherits Step 4a/4b/4c source-decision conventions (tool-use, closed coaching-flag enum, `additionalProperties: false`, hybrid prior-window rendering). T3-specific picks captured below.

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Output mechanism | **Tool-use** (`record_refresh_sessions`); single tool, single call; the `sessions` argument is a `list[PlanSession]` (0..56 entries — up to 2/day × 28 days). Strict JSON schema with `additionalProperties: false` at every nesting level. | Same tool name as T1/T2; schema differs only in `maxItems` (56 for T3 vs 14 for T2 vs 4 for T1). |
| D2 | Extended thinking budget | **~6500 tokens.** | Larger than T2's 4500 — T3 covers a 4-week mesocycle and reasons about phase trajectory (mid-phase progression toward exit state), deload cadence placement (4 weeks typically includes one deload), and 4 weekly aggregates instead of 1. Larger than per-phase's 5000 because T3 has to simultaneously satisfy weekly aggregate guardrails for all 4 weeks AND coherent mesocycle progression. |
| D3 | Sampling `max_tokens` | **10000.** | Up to 56 sessions × ~140 tokens/session average. Generous headroom; the `intensity_modulated`-with-rationale path emits longer `session_notes`. |
| D4 | Input format | **Full payloads verbatim** for all five Layer 2 payloads (2A + 2B + 2C + 2D + 2E) + 3A + 3B + 1 + `request` + `parsed_intent`. T3's default cascade per `Plan_Refresh_D64_Design_v1.md` §3.3 re-runs ALL upstream Layer 2 nodes; the prompt receives the freshly-re-run state. `prior_plan_session_window` rendered hybrid per D5. | T3's ~9000-11000 input token budget per `Layer4_Spec.md` §11.2 absorbs full payloads. T3 reshapes the mesocycle, which needs every upstream-layer signal — discipline mix shifts, terrain changes, equipment availability changes, injury accommodations, nutrition tier shifts all surface in the re-run cascade. Trimming would risk losing signal that drives the reshape direction. |
| D5 | `prior_plan_session_window` rendering | **Tiered: refresh-window-prior (the 14 days BEFORE refresh) as weekly rollup (2 rollups: prior-week-1 + prior-week-2) + last-week verbatim; refresh-window-after (days 29-35) as summary table.** | T3 covers 28 days; the prior context is 2 weeks (load + recent shape), not 1 week. Older prior-week (days -14..-8) rolls up to "week summary: 12.5h, 9 sessions, intensity counts: easy=5 / moderate=3 / hard=1" — fits ~50 tokens. Last-week (days -7..-1) verbatim drives recovery + recency reasoning. Refresh-window-after (days 29-35) is summary-table because T3's reshape is mesocycle-internal — continuity to days 29-35 matters less than phase trajectory (Andy 2026-05-17 Pick: phase-trajectory-aware). |
| D6 | `parsed_intent` weighting policy | **Strong-bias toward intent** (Andy 2026-05-17 carried from T1/T2 Pick 2). The athlete's `raw_text` + `parsed_intent` signals dominate the direction of the mesocycle reshape. 3A objective signals ground the magnitude. T3's larger scope means intent can reshape WEEKLY structure (e.g., athlete says "I want more bike, less run for the next month" → discipline mix shifts across all 4 weeks). | Athlete-explicit framing of D-64 (Decision 2). T3 is the athlete-explicit "regenerate the next month" surface — intent-led reshape is the whole point. |
| D7 | Continuity-with-adjacent-sessions policy | **Phase-trajectory-aware reshape** (Andy 2026-05-17 Step 4d Pick 4). Reshape the mesocycle for phase progress + the inherited periodization shape; continuity to days 29-35 sessions is secondary (the athlete clicked "refresh next month" — they're inviting a fuller reshape). Refresh-window-after is rendered as summary-table not verbatim per D5. | T3's intent is mesocycle reshape. T1/T2's "minimally disruptive by default" doesn't fit T3 — a month is enough scope to materially shift training shape, and the athlete invited that shift by clicking the T3 button. Phase trajectory (mid-phase progression toward exit state) is the load-bearing constraint, not session-by-session continuity with the un-refreshed week 5. |
| D8 | Coaching flag enum | **Full per-phase + cross-phase LLM-emittable set** (Layer 4 §§8.2–8.6 LLM-emitted entries only): `technique_emphasis`, `long_slow_distance`, `weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `race_pace_specific`, `intensity_modulated`. | Same enum as T1/T2. T3 is more likely to emit `overreach_test` (an entire intentional overreach week as part of the mesocycle shape) and `peak_volume_marker` (the highest-volume week of the mesocycle, when Peak phase). |
| D9 | `RuleFailure` retry context rendering | **Hybrid:** `rule_name + severity + detail + affected_session_id(s) + suggested_constraint`. | Same as T1/T2. T3 retry context is more likely to involve mesocycle-level rule failures (`volume_band_*` across 4 weeks; `acwr_*` forward projection across the full 28-day scope; `intensity_dist_*` across the dominant phase). The orchestrator's `suggested_constraint` for these rules names the mesocycle-level constraint. |
| D10 | Schema-enforced length caps | **Tight: 240 chars `session_notes` / 200 chars `coaching_intent` / 120 chars `load_prescription` / 240 chars `instructions`.** | Same as T1/T2 + single-session. `max_tokens=10000` budget (up from T2's 4000) absorbs the wider session count, not longer per-session prose. |
| D11 | NL `raw_text` passthrough | **Always rendered in §6 user prompt under explicit "athlete's words" framing.** Same as T1/T2. | Strong-bias-toward-intent (D6) means the prose is primary signal; structured flags are scaffolding. |
| D12 | Cross-phase routing | **NOT IN SCOPE FOR THIS PROMPT.** The `plan_refresh.py` driver detects scope crossing a phase boundary via `phase_structure_from_3b()` + `scope_spans_phase_boundary()` (§6.1 helper); on cross-phase scope it raises `Layer4InputError('tier_t3_cross_phase_requires_pattern_a')` until Step 4f lands Pattern A orchestration for T3 cross-phase. This prompt is invoked ONLY when the scope is entirely inside one phase. | Per `Layer4_Spec.md` §5.1 + §6.3: T3 routes to Pattern B only when the scope is intra-phase; cross-phase requires Pattern A per-phase synthesis + seam review. Step 4d ships intra-phase Pattern B; Step 4f ships cross-phase Pattern A. |
| D13 | File location | `aidstation-sources/prompts/Layer4_RefreshT3_v1.md` per the `prompts/` subdir convention. | Inherits. |

**Companion contract sections (`Layer4_Spec.md`):** §3.2 (call signature — `tier='T3'`; `plan_start_date` added Step 4d), §4.3 (input validation — refresh preconditions including `tier_scope_mismatch` for T3 ≤ 32 days), §5.1 (pattern routing — T3 → B intra-phase, A cross-phase), §5.3 (Pattern B algorithm), §5.4 (deterministic validator — full rule set on refresh; weekly-aggregate rules × 4 weeks; ACWR forward projection across full 28-day scope), §5.5 (capped retry semantics), §6.3 (single-phase T3 special case — routes to Pattern B), §7.2/§7.3/§7.4 (`PlanSession` discriminated union + sub-blocks), §7.5 (`SessionPhaseMetadata` — None on Pattern B refresh per §7.12 schema rule, including T3 intra-phase), §8.6 (`intensity_modulated` cross-phase flag — trigger broadened in Step 4b/c), §11.1 / §11.2 / §11.3 (latency / token / cost — ~12s / ~9500 input + ~5500 output / ~$0.22 typical).

**Paired spec amendment this session:** `Layer4_Spec.md` §3.2 — `plan_start_date` parameter added to `llm_layer4_plan_refresh` signature (required when `tier='T3'`; ignored on T1/T2). Per §6.1's "orchestrator-supplied" framing for `phase_structure_from_3b()`. Trigger #5 routed through the Step 4d AskUserQuestion gate per the Step 4a/4b/4c precedent.

---

## 1. Purpose + scope

### 1.1 What this prompt produces

A list of `PlanSession` records (typically 14–28 entries depending on athlete availability + discipline mix; max 56) covering `[refresh_scope_start, refresh_scope_end]` — 28 calendar days (rolling, today through today+27). Each session is athlete-facing and immediately renderable. The sessions emit `is_ad_hoc=False`, `plan_version_id=<new T3 version id>`, and `phase_metadata=None` (Pattern B refreshes don't write phase metadata per `Layer4_Spec.md` §7.12; T3 intra-phase is Pattern B per §6.3).

The synthesizer reads the freshly-re-run full upstream cascade (2A + 2B + 2C + 2D + 2E + 3A + 3B), the athlete's NL context, the prior plan's sessions for the refresh window (now superseded), and the surrounding ±14 days of plan context. It produces sessions that honor the refresh trigger, reshape the mesocycle for phase progress (Andy 2026-05-17 Step 4d Pick: phase-trajectory-aware reshape), respect the inherited periodization shape, and hand off into the still-planned sessions for week 5+ as a soft (not strict) continuity constraint.

### 1.2 What this prompt does NOT produce

- **Phase decomposition.** T3 reads the freshly-re-run 3B periodization shape but does not synthesize a `PhaseStructure`. The shape is consumed as constraint; the prompt produces session content within the dominant phase that covers the refresh window. (T3 cross-phase routes to Pattern A and uses `Layer4_PerPhase_v1.md` — Step 4f.)
- **Sessions outside the refresh window.** The prompt produces sessions for `[refresh_scope_start, refresh_scope_end]` (28 days). Refresh-window-after sessions (days 29-35) stay pointed at their prior `plan_version_id`; the synthesizer reads them as soft continuity constraint but does not modify them.
- **NL intent re-classification.** Same as T1/T2 §1.2: parsed_intent is consumed verbatim; the prompt does not re-parse.
- **Observations or opportunities** other than the LLM-emitted `category='opportunity'` exception per `Layer4_Spec.md` §8.7.
- **Cross-phase reasoning.** When the refresh window spans a phase boundary, the driver raises BEFORE reaching this prompt. This prompt is invoked only when the scope is intra-phase. Phase boundary at day 0 or day 27 inclusive counts as intra-phase iff both `phase_for_date(scope_start)` and `phase_for_date(scope_end)` return the same `phase_name` (the `scope_spans_phase_boundary()` helper is the source of truth).

### 1.3 Failure modes this prompt + retry semantics catch

- Athlete signals fatigue / overtraining (`parsed_intent.fatigue_signal='wiped'` or 3A `acwr_status` out of band) but the synthesizer prescribes a normal mesocycle → validator catches via ACWR forward projection (across the 28-day scope, this is load-bearing — short windows can hide load).
- Synthesizer's weekly volume in any of the 4 weeks falls outside the phase's `volume_band_*` per 2A `phase_load_bands` → validator `volume_band_blocker` triggers capped retry.
- Synthesizer's intensity distribution (Z1-Z2 / Z3 / Z4-Z5 hour-share) across the dominant phase drifts outside target ±10pp → validator `intensity_dist_*` triggers capped retry.
- Synthesizer's prescription conflicts with active injuries (2D excluded list) → `injury_violation_blocker` triggers capped retry.
- Synthesizer prescribes hard-back-to-back across multiple days without explicit `overreach_test` / `race_rehearsal` flag → `rest_spacing_blocker` triggers capped retry.
- Synthesizer omits the deload week when the cadence anchor falls inside the 28-day scope → no validator catch; surfaces as `Observation(category='opportunity')` via the system prompt's deload-cadence reminder (T3 is the natural place to land a deload; missing it is a coaching gap).

---

## 2. Pipeline placement

**Call site:** `llm_layer4_plan_refresh(user_id, tier='T3', ...)` per `Layer4_Spec.md` §3.2. Invoked by the D-64 orchestrator after:

1. Cascade execution per `Plan_Refresh_D64_Design_v1.md` §6.1 — all five Layer 2 nodes + 3A + 3B + 3C + 3D re-run (full upstream re-eval per §3.3).
2. Input validation per `Layer4_Spec.md` §4.3 — including `tier ∈ enum`, `refresh_scope_*` ordered, `tier_scope_mismatch` (T3 scope ≤ 32 days), `plan_version_id_parent` exists, **`plan_start_date` non-None per Step 4d spec amendment**.
3. Phase-boundary detection per `phase_structure_from_3b()` + `scope_spans_phase_boundary()`. If scope spans a phase boundary, the driver raises `Layer4InputError('tier_t3_cross_phase_requires_pattern_a')` (Step 4f surface). If scope is intra-phase, this prompt is invoked.

**Pattern:** B per `Layer4_Spec.md` §5.3 step 1 sub-bullet (T3 intra-phase):

> `plan_refresh` T3 intra-phase: above + 3B current periodization shape (read but not decomposed).

- Step 1: build context (this prompt's §3 inputs).
- Step 2: single LLM call (this prompt's §5 system + §6 user + §7 sampling config).
- Step 3: parse `record_refresh_sessions` tool output as `list[PlanSession]`.
- Step 4: deterministic validator (`Layer4_Spec.md` §5.4) — full rule set, scoped over the 28-day refresh window with weekly-aggregate rules running for each of the 4 weeks individually. ACWR forward projection across the full scope. Cross-validate adjacent-day continuity with prior_plan_session_window adjacent to scope.
- Step 5: capped retry per `Layer4_Spec.md` §5.5 on validator failure; cap=2 (default).
- Step 6: compose `Layer4Payload` with `mode='plan_refresh'`, `pattern='B'`, `phase_structure=None`, `seam_reviews=None`, sessions covering the refresh window, `plan_version_id` set to the new T3 version id.

---

## 3. Inputs (template variables)

This prompt's user-prompt template (§6) interpolates the following variables. All are required unless marked optional. Token-budget realism per `Layer4_Spec.md` §11.2: ~9500 input tokens total worst case.

### 3.1 Refresh request

| Variable | Source | Notes |
|---|---|---|
| `refresh.tier` | D-64 caller | `'T3'`. |
| `refresh.scope_start` | D-64 caller | Typically today. |
| `refresh.scope_end` | D-64 caller | `scope_start + 27 days` (28-day rolling window; both ends inclusive). Validated per `Layer4_Spec.md` §4.3 (`tier_scope_mismatch` if length > 32 days). |
| `refresh.triggered_at` | D-64 caller | Timestamp. Used for recency reasoning. |
| `refresh.dominant_phase` | Driver (`phase_for_date(scope_midpoint)`) | The phase covering the midpoint of the refresh window. Used for weekly aggregate guardrails + LSD anchor placement + deload-cadence reasoning. |

### 3.2 NL context + parsed intent

Identical structure to T1/T2 §3.2 — `parsed_intent.raw_text`, `fatigue_signal`, `sickness_signal`, `motivation_signal`, the 5 trigger booleans/lists, `parser_confidence`, `ambiguity_notes`.

T3-specific notes: T3's mesocycle scope means soft signals can drive multi-week reshape (e.g., `fatigue_signal='tired'` AND `parser_confidence='high'` → bias the mesocycle toward a deload week placement OR reduced overall volume across all 4 weeks). The NL parser's raw_text is the primary signal per D6.

### 3.3 Athlete + locale context

Identical structure to T1/T2 §3.3 — `athlete.user_id`, `coaching_voice_preferences`, `experience_level`, `discipline_inclusion` (from freshly-re-run 2A), `active_injuries` (from freshly-re-run 2D — excluded + accommodated), `locales`, `default_locale_for_date_window` (now 28 days; per-day assignment per athlete travel pattern).

T3-specific note: full upstream re-eval means 2A discipline_inclusion may have shifted (athlete added or dropped a discipline), 2B terrain may have refined, 2C equipment view per locale may have re-resolved (new gym profiles, new equipment overrides), 2D injury list may have evolved (new injuries, healed injuries removed), 2E nutrition baseline may have re-tiered. The synthesizer reads the post-cascade state.

### 3.4 Athlete state — drives modulation reasoning

Identical structure to T1/T2 §3.4 — `acwr_7_28`, `seven_day_load`, `last_hard_session_date`, `last_hard_session_sport`, `fatigue_markers`, `data_density`, `aerobic_state`.

T3-specific note: 3A is re-run as part of the T3 cascade. The values reflect the post-refresh-trigger state.

### 3.5 Periodization shape — freshly-re-run 3B + dominant phase

T3 re-runs 3B as part of its default cascade. The synthesizer reads the fresh 3B output for the periodization shape governing the refresh window.

| Variable | Source | Notes |
|---|---|---|
| `layer3b.periodization_shape.mode` | Layer 3B (re-run) | `'standard' \| 'compressed' \| 'extended' \| 'custom'`. T3 may inherit a new mode if 3B's re-eval shifted it (e.g., 3A picked up a major fitness signal). |
| `layer3b.periodization_shape.start_phase` | Layer 3B (re-run) | The phase the plan is currently entering / continuing. |
| `layer3b.dominant_phase` | Driver | The single phase covering the refresh window. T3 intra-phase guarantees this is well-defined; cross-phase routes to Pattern A before reaching this prompt. |
| `layer3b.dominant_phase_volume_band` | Layer 3B + 2A `phase_load_bands` | Per-phase volume band the dominant phase targets. The refresh window's 4 weekly volume totals each aim inside the band. |
| `layer3b.dominant_phase_intensity_distribution` | Layer 4 §5.4 v1 defaults | Per-phase target distribution. Refresh window's intensity distribution (across the dominant phase) validator reads against this. |
| `layer3b.dominant_phase_end_date` | Driver (`phase_for_date(scope_midpoint).end_date`) | When the dominant phase ends. If refresh scope ends well before phase end (mid-phase refresh), the synthesizer reshapes for phase progress; if refresh scope ends close to phase end, the synthesizer may bias the last week toward phase-exit-state preparation. |
| `layer3b.days_to_event` | 3B `time_to_event_weeks` × 7 (when present) | Optional. When ≤ 14 within the refresh scope, the synthesizer should default the affected days to Taper-shape (rare for T3 intra-phase since Taper is typically 1-3 weeks; only fires when the dominant phase IS Taper). |
| `layer3b.deload_cadence_anchor` | 3B periodization mode (per `Layer4_PerPhase_v1.md` D6 anchor table) | Per-mode deload cadence (every 4th week standard; every 3rd compressed; every 5th extended; custom = judgment). T3's 28-day scope typically contains ONE deload week. The synthesizer prescribes that week's deload-shape sessions. |

### 3.6 Prior plan session window (drives recency + soft continuity)

| Variable | Source | Notes |
|---|---|---|
| `prior_plan.week_minus_2_rollup` | `prior_plan_session_window` filtered to `[scope_start - 14d, scope_start - 8d]` | Older prior-week — weekly rollup line (total hours + session count + intensity counts). Drives the "what's the athlete's baseline coming into this refresh" reading. |
| `prior_plan.week_minus_1_verbatim` | `prior_plan_session_window` filtered to `[scope_start - 7d, scope_start - 1d]` | Most recent prior week — verbatim with all fields. Drives recency / recovery reasoning. |
| `prior_plan.refresh_window_during_prior` | `prior_plan_session_window` filtered to `[scope_start, scope_end]` | The prior-plan sessions the refresh is replacing (max ~56 sessions). Rendered as summary table (date / sport / kind / duration / intensity) — T3 is intent-led reshape, so verbatim isn't load-bearing on the replaced sessions. |
| `prior_plan.refresh_window_after_summary` | `prior_plan_session_window` filtered to `[scope_end + 1d, scope_end + 7d]` | Week 5 (days 29-35), still planned, not refreshed. Rendered as summary table per D5 + D7 (phase-trajectory-aware reshape — soft continuity to week 5, not strict). |

### 3.7 Retry context (only present on retry pass)

Identical to T1/T2 §3.7.

### 3.8 Intentionally NOT passed

- `phase_structure` — Pattern B has no phase decomposition; T3 intra-phase reads 3B's shape directly without synthesizing per-phase week-by-week breakouts. The dominant_phase variable is the relevant phase-context handle.
- `seam_issues` / `seam_direction` — Pattern B has no seam reviewer. (Cross-phase T3 routes to Pattern A which DOES have seam review; this prompt is intra-phase only.)
- `event_date` / `race_format` — surfaced indirectly via `layer3b.days_to_event` when relevant; race-week specifics handled by `Layer4_RaceWeekBrief`.

---

## 4. Output schema + tool definition

The synthesizer emits exactly one tool call to `record_refresh_sessions`. Schema is identical to T1/T2's §4.1 except `sessions.maxItems = 56` (vs 14 for T2 vs 4 for T1).

### 4.1 Tool schema (diff from T2)

```diff
- "maxItems": 14,
+ "maxItems": 56,
```

Everything else — session shape, `additionalProperties: false`, the closed coaching-flag enum, cardio blocks + strength exercises, `notable_observations` with `opportunity` only — matches T1/T2 §4.1 verbatim. Runtime schema follows the full payload contract via `build_record_refresh_sessions_tool(tier='T3')` per `layer4/plan_refresh.py`.

### 4.2 Output invariants the prompt must honor

- `len(sessions)` in `[0, 56]`. Typical T3 produces 14–28 sessions (4 weeks × 4-7 sessions/week × discipline variety + rest days respected).
- Each session's `date` falls inside `[refresh_scope_start, refresh_scope_end]`.
- Per-date max 2 sessions per `Layer4_Spec.md` §7.12 (same constraints as T1/T2).
- `coaching_flags` closed set per D8.
- `intensity_modulated` MUST be emitted on every session where the prescription deviates from natural periodization-shape reading due to intent or 3A signal. Mesocycle-level modulation (e.g., entire mesocycle pulled back due to fatigue) emits the flag on every affected session.
- `notable_observations[].category` restricted to `'opportunity'`.

T3-specific invariants:

- **Per-week volume** (× 4): each week's total volume should land inside the dominant phase's `volume_band` per 2A `phase_load_bands`. Validator enforces with `volume_band_*` rules running per-week.
- **Mesocycle intensity distribution**: the full 28-day distribution of hours across (Z1-Z2 / Z3 / Z4-Z5) should land inside the dominant phase's target ±10pp tolerance. Validator enforces with `intensity_dist_*` rules (the rule is per-phase, and the dominant phase is the only phase in scope).
- **ACWR forward projection**: the 28-day scope is long enough that ACWR (acute=trailing-7d, chronic=trailing-28d) must stay inside band per Gabbett 2016 across the entire window. Validator enforces with `acwr_*` (blocker outside 0.7-1.4; warning outside 0.8-1.3).
- **Deload week placement**: when the deload cadence anchor falls inside the 28-day scope (typical), the synthesizer prescribes that week's sessions as deload-shape (volume to lower edge of band; intensity bias toward Z1-Z2). The orchestrator emits the `recovery_week` flag spec-auto on all sessions in the deload week.
- **Long-session anchor (× 4)**: in Base + Build phases, each of the 4 weeks should contain exactly one `long_slow_distance`-flagged session per discipline that has a weekly LSD cornerstone (per `Layer4_Spec.md` §8.2). Missing an LSD on a non-deload Base/Build week is a coaching gap (not validator-enforced but surfaced via `Observation(category='opportunity')`).
- **Mesocycle progression**: the 4 weeks should reflect coherent mesocycle progression toward the phase exit state. For Base/Build: typically week 1 = build / week 2 = build / week 3 = peak-volume / week 4 = deload (or week-3 deload depending on cadence anchor alignment). For Peak: typically intensity progresses week-over-week. For Taper: progressive volume reduction with quality preservation.

---

## 5. System prompt

```
You are AIDSTATION's Layer 4 plan-refresh T3 synthesizer.

You are called when an athlete clicks "Refresh the next 4 weeks" on their training plan. The athlete has typed an optional free-text note explaining why they want the refresh. Your job is to produce 0-56 PlanSession records covering the next 28 calendar days that:

1. Honor the athlete's stated intent (their words are the primary signal — see §9 policy).
2. Stay inside the freshly-re-run periodization phase's intent — volume band + intensity distribution within phase tolerance, applied per-week (× 4) AND mesocycle-wide.
3. Reshape the mesocycle for phase progress (Andy 2026-05-17 Pick: phase-trajectory-aware reshape) — the 4 weeks should reflect coherent mesocycle progression toward the phase exit state.
4. Place the deload week when the cadence anchor falls inside the scope (typical — most 28-day windows contain one deload).
5. Hand off softly into the sessions already planned for days 29-35 after the refresh window. Continuity to week 5 is secondary to phase progress — this is a mesocycle reshape, not a session-by-session adjustment.
6. Never violate hard constraints — active injuries, equipment availability, schedule availability.

VOICE: Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Match a real endurance coach talking to a serious athlete. Short sentences. Plain English. No emoji.

PROCESS:
- Read the athlete's `raw_text` and `parsed_intent` first. These drive WHY you're reshaping the mesocycle.
- Read the freshly-re-run full upstream cascade (2A + 2B + 2C + 2D + 2E + 3A + 3B) for current state.
- Read the prior 2 weeks of training (week -2 rollup + week -1 verbatim) to ground the modulation in recent training.
- Read the dominant phase's intent + volume band + intensity distribution + deload cadence anchor + days-to-event (when applicable).
- Decide the mesocycle shape: which week is the highest-volume; where the deload lands; whether intent calls for an overreach week; how the 4-week intensity distribution sums to phase target.
- Decide each week's shape: session count per day (1 or 2 per availability); discipline mix; long-session anchor placement; hard-vs-easy day spacing.
- For each session, prescribe sport / duration / intensity + structured content (cardio_blocks or strength_exercises).

INTENSITY-MODULATION POLICY:
- The athlete's words and the parsed signals dominate the prescription DIRECTION (mesocycle reshape direction + per-session modulation).
- 3A objective signals (ACWR, recent load, last-hard-session) ground the MAGNITUDE but never override the direction.
- Hard safety constraints (active injuries, equipment availability, schedule availability) are never overridden.
- When sickness_signal='active': prescribe rest-shape across the entire scope (athlete must clear sickness before resuming load — no T3-scale reshape during active illness).
- Mesocycle-level modulation (entire mesocycle pulled back due to overreach recovery, illness recent-recovery, intent reshape) emits `intensity_modulated` on every affected session.
- Emit `intensity_modulated` on each session where the prescription deviates from what the periodization shape + dominant-phase intent would naturally call for. Briefly explain in `session_notes`.

WEEKLY-AGGREGATE GUARDRAILS (per-week, × 4):
- Each week's volume inside dominant phase's `volume_band` per 2A `phase_load_bands` (validator: `volume_band_*` per-week).
- Mesocycle-wide intensity distribution inside dominant phase's target ±10pp (validator: `intensity_dist_*` per-phase).
- Base + Build weeks: include exactly one long-session anchor per discipline per week with weekly LSD cornerstone (flagged `long_slow_distance`).
- Deload week (cadence-anchor aligned): reduce volume to lower edge of band; bias intensity toward Z1-Z2. Orchestrator emits `recovery_week` spec-auto.

ACWR FORWARD PROJECTION:
- The 28-day window is long enough for ACWR to be load-bearing. Acute (trailing 7d) / chronic (trailing 28d) ratio must stay inside 0.7-1.4 across the scope; aim 0.8-1.3 for warning-clean.
- A ramp from the prior 2-week baseline that pushes ACWR > 1.4 by week 3 will fail validation. Pace the load increase across the mesocycle.

OUTPUT DISCIPLINE:
- Emit exactly one tool call to `record_refresh_sessions`. The tool's `sessions` argument is your list of 0-56 PlanSession records.
- Every cardio block requires an explicit `intensity_zone` (Z1-Z5 or mixed) and an `intensity_target` shape matching the sport: HRTarget for endurance, PowerTarget for bike/run/skimo/row, PaceTarget for running/paddle/ski, SwimPaceTarget for swim, RPETarget as universal fallback, VerticalRateTarget for skimo/hiking, StrokeRateTarget for swim/paddle/row, CadenceTarget for cycling, ClimbingGradeTarget for outdoor rock.
- For interval_set cardio_blocks: emit `repetitions`, `rest_between_min`, `rest_intensity_zone`. For other block_kinds: leave those three fields null.
- Strength exercises reference Layer 0B exercise IDs; populate `exercise_name`; `reps_per_set` accepts integer or string.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- Do not emit prose outside the tool call.
```

---

## 6. User prompt (template)

The driver's `render_user_prompt()` produces this prompt at call time by interpolating the §3 variables. The template structure follows T1/T2 with T3-specific blocks added (week -2 rollup, dominant phase metadata, mesocycle shape reminders, ACWR projection guidance).

```
=== Refresh request ===
Tier: T3 (28-day rolling window — mesocycle)
Scope: {{ refresh.scope_start }} through {{ refresh.scope_end }} ({{ scope_days }} days)
Dominant phase: {{ refresh.dominant_phase.name }} ({{ refresh.dominant_phase_start_date }} through {{ refresh.dominant_phase_end_date }})

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

=== Athlete profile (post-cascade) ===
Experience level: {{ layer1.experience_level }}
Disciplines (from freshly-re-run 2A): {{ layer2a.disciplines }}
Active injuries (hard constraints — never overridable):
{{ active_injuries_block }}

=== Periodization shape (3B — re-run as part of T3 cascade) ===
Mode: {{ layer3b.periodization_shape.mode }}
Start phase (athlete's overall plan): {{ layer3b.periodization_shape.start_phase }}
Dominant phase covering this refresh: {{ layer3b.dominant_phase }}
Dominant phase volume band: {{ layer3b.dominant_phase_volume_band }}
Dominant phase intensity distribution target: {{ layer3b.dominant_phase_intensity_distribution }}
Dominant phase end date: {{ layer3b.dominant_phase_end_date }}
{{#layer3b.days_to_event}}
Days to event: {{ layer3b.days_to_event }}
{{/layer3b.days_to_event}}

Deload cadence reminder: For mode={{ layer3b.periodization_shape.mode }}, deload weeks fall every {{ deload_cadence_n }}th week (standard=4, compressed=3, extended=5; custom=coaching judgment). When the cadence anchor falls inside the 28-day scope, prescribe that week as deload-shape; the orchestrator emits the `recovery_week` flag spec-auto.

=== Athlete state (3A — re-run as part of T3 cascade) ===
Aerobic capacity: {{ layer3a.current_state.aerobic_capacity.level }} ({{ layer3a.current_state.aerobic_capacity.confidence }})
Strength: {{ layer3a.current_state.strength.level }} ({{ layer3a.current_state.strength.confidence }})
{{#layer3a.weak_links}}
Weak links: {{ layer3a.weak_links }}
{{/layer3a.weak_links}}
Short-term trajectory: {{ layer3a.recent_trajectory.short_term.direction }}
Medium-term trajectory: {{ layer3a.recent_trajectory.medium_term.direction }}
{{#layer3a.acwr_status.combined}}
ACWR (combined): ratio={{ layer3a.acwr_status.combined.ratio }}, zone={{ layer3a.acwr_status.combined.zone }}, acute={{ layer3a.acwr_status.combined.acute_load }} chronic={{ layer3a.acwr_status.combined.chronic_load }} {{ layer3a.acwr_status.combined.units }}
{{/layer3a.acwr_status.combined}}
Data density: {{ layer3a.data_density.recent_workouts_count }} recent workouts, {{ layer3a.data_density.integration_data_days }} days of integration data

=== Recent training — week -2 rollup ({{ week_minus_2_start }} through {{ week_minus_2_end }}) ===
{{ week_minus_2_rollup_line }}

=== Recent training — last week verbatim ({{ week_minus_1_start }} through {{ week_minus_1_end }}) ===
| Date | Sport | Kind | Duration | Intensity | Coaching flags | Completed |
|---|---|---|---|---|---|---|
{{ week_minus_1_verbatim_rows }}

=== Sessions previously planned for the 28-day refresh window (being replaced) ===
| Date | Sport | Kind | Duration | Intensity |
|---|---|---|---|---|
{{ refresh_window_during_prior_summary_rows }}

=== Sessions planned for week 5 ({{ week_5_start }} through {{ week_5_end }}) — SOFT CONTINUITY ONLY ===
| Date | Sport | Kind | Duration | Intensity |
|---|---|---|---|---|
{{ refresh_window_after_summary_rows }}

This is a phase-trajectory-aware reshape: the 4-week mesocycle should reflect coherent progression toward the dominant phase's exit state. Continuity to week 5 is soft (the athlete invited the reshape). If week 5 contains a planned hard week, the mesocycle's last week may need to deload or otherwise prepare; if week 5 is uneventful, the mesocycle has freer rein.

{{#retries_used}}
=== Retry context (pass {{ retries_used }} of cap=2) ===
Prior pass failed deterministic validator with these rule failures:
{{ rule_failure_block }}

Repair pass: address each constraint above while keeping the rest of the prescription intact. Mesocycle-aggregate failures (volume_band_*, intensity_dist_*, acwr_*) may require shifting volume across multiple weeks; do the minimum needed to clear the constraint.
{{/retries_used}}

=== Output ===
Emit one tool call to `record_refresh_sessions` with your list of 0-56 PlanSession records covering the 28-day refresh window.
```

---

## 7. Sampling configuration

Per `Layer4_Spec.md` §11.2 + this prompt's D2/D3 picks:

- `model`: `claude-sonnet-4-6` (Anthropic Sonnet 4.6) per Layer 4 default.
- `temperature`: 0.4 (matches T1/T2 default).
- `max_tokens`: 10000 (D3).
- `extended_thinking.budget_tokens`: 6500 (D2). Extended thinking on.
- `tool_choice`: forced — `{type: 'tool', name: 'record_refresh_sessions'}`. Single tool call required.
- `capped_retries`: 2 (default; per `Layer4_Spec.md` §5.5).

Latency expectation: ~12s p50, ~18s p95. Token expectation: ~9500 input + ~5500 output average. Cost expectation: ~$0.22 typical per invocation (Sonnet 4.6 rates).

---

## 8. Coaching policy carve-outs (T3-specific)

### 8.1 Phase-trajectory-aware reshape (Andy 2026-05-17 Step 4d Pick)

T3 is the mesocycle reshape surface. The athlete clicked "refresh the next 4 weeks" — they're inviting a substantive shift. The synthesizer should:

- **Read the dominant phase's intent first.** Where is this phase in its arc? Base mid-phase = build progressively; Build mid-phase = intensify within volume; Peak mid-phase = race-specific intensity; Taper mid-phase = progressive volume reduction with quality preservation.
- **Compose the 4 weeks as a coherent mesocycle.** Not 4 independent weeks. Each week's role contributes to the phase's exit state.
- **Treat week 5 continuity as soft.** If week 5 contains a planned key workout (long ride, race-pace day, overreach), bias the mesocycle's last week toward supporting it. If week 5 is uneventful, the mesocycle has freer rein.

### 8.2 Deload week placement

T3's 28-day scope typically contains one deload week (per-mode cadence: every 4th in standard; every 3rd in compressed; every 5th in extended; custom = coaching judgment). The synthesizer should:

- **Identify which week is the deload.** Read the deload cadence anchor + the parent plan's prior deload week timing. The cadence is a soft anchor — coaching judgment can shift ±1 week when athlete state (3A overreach signal, recent illness, intent) justifies.
- **Prescribe deload-shape sessions for that week.** Volume to lower edge of `volume_band`; intensity bias toward Z1-Z2; reduce hard sessions; preserve sport variety + frequency.
- **Orchestrator emits `recovery_week` spec-auto.** The synthesizer doesn't emit this flag; the orchestrator stamps it post-synthesis per `Layer4_Spec.md` §8.5.

### 8.3 ACWR forward projection awareness

The 28-day window is the natural granularity for ACWR (chronic = trailing 28 days per Gabbett 2016). The synthesizer should:

- **Read the current ACWR from 3A.** If `acwr_status.combined.ratio > 1.2`, bias the mesocycle toward consolidating recent gains (less load increase, more recovery).
- **Pace load increases.** A 4-week ramp that pushes ACWR > 1.4 by week 3 will fail the `acwr_*` validator rule. Steady increases (≤10-15% week-over-week) are safer.
- **Recovery weeks reduce ACWR mechanically.** A deload week brings the acute denominator down; ACWR drops naturally without explicit synthesizer action.

### 8.4 Mesocycle intent shifts surface as `intensity_modulated` × all sessions

When the athlete's intent reshapes the mesocycle's direction (e.g., "back off the next month — I want a true recovery block before the race build"), every session in the mesocycle that reflects that reshape emits `intensity_modulated`. The flag is emitted at session level; the system prompt's policy reinforces that mesocycle-level modulation cascades to every session.

---

## 9. Coaching voice + forbidden phrasings

Inherits T1/T2 §9 + the CLAUDE.md coaching voice:

- Direct, focused, evidence-grounded.
- No platitudes ("trust the process", "you've got this", "crush it", "stay consistent").
- No cheerleading. No hype.
- Match a real endurance coach talking to a serious athlete.

T3-specific note: T3 outputs are 4-week mesocycles; the synthesizer's `session_notes` should reflect coaching judgment at the mesocycle level when relevant ("Week 1 builds volume; week 2 holds with a midweek tempo session; week 3 is the peak-volume week with the cornerstone long ride; week 4 is the deload"). Per-session notes still apply but should reference the mesocycle context when modulating.

---

## 10. Token + cost budget

Per `Layer4_Spec.md` §11.2:

- Input: ~9500 tokens worst case (full payloads × 7 layers + prior 2 weeks + dominant phase context + retry context on retry).
- Output: ~5500 tokens worst case (56 sessions × ~100 tokens/session structured + observations).
- Extended thinking: 6500 tokens budget (D2).
- Sonnet 4.6 pricing: $3/Mtok input, $15/Mtok output, $3/Mtok thinking.
- Per-call cost worst case: 9500 × $3/M + 5500 × $15/M + 6500 × $3/M = $0.0285 + $0.0825 + $0.0195 = ~$0.13 per pass.
- With cap=2 retries: ~$0.26-0.39 worst case (all 3 passes fire). Typical (first-pass-accept): ~$0.13.
- Headline per `Layer4_Spec.md` §11.3: ~$0.22 typical (between first-pass and cap-hit).

---

## 11. Performance + latency

- p50 ~12s end-to-end per `Layer4_Spec.md` §11.1.
- p95 ~18s (single retry + extended thinking variance).
- Compare to T2 ~7s p50 (lighter): T3 is ~1.7× slower due to wider output + more reasoning.
- Compare to per-phase ~5-8s (Pattern A): T3 intra-phase trades the seam-review pass for a single larger LLM call. v1 measurement post-launch.

---

## 12. Test scenarios (v1 draft)

PSS-T3-prefix scenarios; v1 draft pending measurement post-launch.

| # | Scenario | Expected behavior |
|---|---|---|
| PSS-T3-1 | Pocket Gopher Extreme 2026 baseline — Andy's mid-Build mesocycle | Synthesizer produces 4 weeks: week 1 build / week 2 build / week 3 peak-volume / week 4 deload. Wrist injury respected (no bench press / no wrist-extension-loaded). LSD anchors landed on Sat across both Run and MTB. |
| PSS-T3-2 | Athlete enters mid-Base; refresh scope is days 7-34 of Base (Base has 8 weeks remaining) | Intra-phase Base. Mesocycle reflects mid-Base build (progressive volume; ACWR steady increase). Deload on week 4 per standard-mode cadence. |
| PSS-T3-3 | Athlete enters mid-Peak; refresh covers days 8-35 of Peak (Peak has 10 weeks) | Intra-phase Peak. Mesocycle includes race-pace work + intensity progression. `race_pace_specific` flag emitted on key sessions. |
| PSS-T3-4 | Cross-phase refresh — scope spans Build→Peak transition | Driver raises `tier_t3_cross_phase_requires_pattern_a`; this prompt is NOT invoked. |
| PSS-T3-5 | Cross-phase refresh — scope spans last 3 days of Base + first 25 days of Build | Same as PSS-T3-4 — driver raises; prompt not invoked. |
| PSS-T3-6 | Intent: "back off the next month — I'm cooked from the recent block" | Strong-bias-toward-intent fires. All 28 days emit `intensity_modulated`. Mesocycle is deload-shape — volume across all 4 weeks at lower edge of band; intensity Z1-Z2 dominant; one true rest week mid-mesocycle. |
| PSS-T3-7 | Intent: "I want more bike, less run for the next 4 weeks — focus on the MTB" | Mesocycle reshape — discipline mix shifts (more bike sessions, fewer run sessions); `intensity_modulated` fires on sessions where discipline shift drives the modulation. Phase intent (volume + intensity targets) honored. |
| PSS-T3-8 | Intent: empty raw_text; parser_confidence='high' fatigue_signal='normal' | Standard mesocycle reshape against dominant phase. Minimal `intensity_modulated` emission (only when prescription deviates from phase intent for other reasons). |
| PSS-T3-9 | `sickness_signal='active'` | All 28 days are rest-shape. Synthesizer prescribes ZERO hard sessions across the mesocycle. `intensity_modulated` fires on every session that would normally have been hard. |
| PSS-T3-10 | Validator pass 1 fails `volume_band_blocker` on week 3; retry context flags it | Retry pass shifts volume from week 3 to week 2 (or trims week 3 directly); resolves blocker. |
| PSS-T3-11 | Validator pass 1 fails `acwr_blocker` (forward projection exceeds 1.4 by week 3); retry context flags it | Retry pass reduces load growth across the mesocycle — typically reduces week 2 + week 3 volume to bring chronic up before acute grows. |
| PSS-T3-12 | Cap-hit on week 3 `volume_band` retry × 2 | Cap hit; outstanding blocker demoted to warning; `Observation(category='best_effort_plan', elevates_to_hitl=True)` emitted; payload still produced + accepted. |
| PSS-T3-13 | Schema violation on first pass; retry; accepts | Schema-only retry path. Doesn't consume per-call retry budget (per §5.5). |
| PSS-T3-14 | `parsed_intent=None` | Driver substitutes degraded `ParsedIntent(parser_confidence='low')`; prompt renders with the degraded-default values; synthesizer treats as "no signal — proceed against phase intent only." |
| PSS-T3-15 | Empty `prior_plan_session_window` (initial plan generation use case per D-64 §3.3) | Athlete onboarded but no plan exists yet. T3 refresh fires as initial-plan-gen. v1 behavior: synthesizer prescribes 4 weeks of Base-shape sessions against 3B's `start_phase` (which is 'Base' for athletes starting their plan). `prior_plan.week_minus_*` blocks render as empty placeholders. |
| PSS-T3-16 | Refresh scope ends 5 days before dominant phase end | Mesocycle's last week biases toward phase-exit-state preparation; the synthesizer may compress the deload or place it earlier to leave week 4 as a phase-exit transition week. |
| PSS-T3-17 | days_to_event=21 within Taper phase | Refresh scope is 28 days; athletes are mid-Taper. Synthesizer prescribes Taper-shape with progressive volume reduction toward race week 4. `peak_volume_marker` does NOT fire (Taper, not Peak). `race_pace_specific` may fire on race-rehearsal sessions. |
| PSS-T3-18 | Per-day availability shows athletes is unavailable days 8-10 (travel block) | Synthesizer respects availability — no sessions on days 8-10. Weekly volume aggregate accommodates the missed days (typically by shifting volume to surrounding days within the week). |

---

## 13. Edge cases

| Case | Handling |
|---|---|
| Athlete is in Taper phase and scope_end falls on/past event date | The orchestrator's `phase_for_date()` returns Taper for scope_start through event date; post-event has no phase (returns None per the helper). This is a cross-phase scope (intra → exit horizon) and the driver raises `tier_t3_cross_phase_requires_pattern_a`. Step 4f handles this; v1 athlete-facing flow surfaces the error as "Refresh scope spans your event — please refresh after the event." |
| Empty `prior_plan_session_window` (initial plan generation) | Initial-plan-gen use case per `Plan_Refresh_D64_Design_v1.md` §3.3. Week -2 / week -1 blocks render empty; synthesizer prescribes against phase intent + athlete state. Validator's continuity-cross-validation skips (no prior sessions). |
| Mode=custom but custom phase_weeks don't sum to a valid mesocycle (e.g., 0-week Taper for an event athlete) | 3B should not emit this shape; if observed, `phase_structure_from_3b()` may raise during phase decomposition. v1 driver propagates the error as `Layer4InputError`. v2 may add a defensive fallback. |
| Athlete refreshed T3 < 7 days ago (soft-cap hit per `Plan_Refresh_D64_Design_v1.md` §6) | Orchestrator handles the soft-cap UX (warning + override); this prompt is invoked after the override decision. No prompt-level handling required. |
| Validator's ACWR rule trips on a thin chronic baseline (less than 28 days of prior data) | Validator soft-skips when chronic load can't be computed (per PR-E `_rule_acwr` policy — returns empty when `prior_session_loads_by_date` is None or sparse). Synthesizer doesn't need special handling. |

---

## 14. Gut check

- **Right.** Mesocycle reshape with phase trajectory awareness; deload anchor reasoning; ACWR forward projection guardrails; per-week + mesocycle-aggregate validator coverage. The 4-week scope is the natural granularity for the periodization model.
- **Risks.** (1) T3 cost (~$0.22/call) is the highest of the refresh tiers; soft-cap is the cost control. (2) Phase-trajectory-aware reshape is harder to validate than "match surrounding shape" — the validator catches aggregate violations but not "is this a coherent mesocycle." Coaching gaps (missing LSD, awkward deload placement) surface as `Observation(category='opportunity')`, not validator failures. (3) Initial-plan-gen path (empty prior_plan_session_window) is a less-traveled code path; the v1 prompt prescribes against 3B + 3A state without continuity context; needs telemetry to validate the output quality. (4) Cross-phase routing happens at driver level (BEFORE this prompt); cross-phase scope is a common case in practice (mid-build → mid-peak crossover; mid-peak → taper crossover) and v1 raises until Step 4f. The athlete-facing UX should explain when cross-phase routes to Pattern A (long-running) vs intra-phase routes to Pattern B (fast).
- **Best argument against.** "T3 intra-phase doesn't justify its own prompt body — it's just T2 with a wider window; subsume into T2 with a tier-dispatched maxItems extension and call it done." Counter: the per-week × 4 + mesocycle-aggregate guardrails are different reasoning from T2's single-week aggregate; the deload week placement is a T3-only concern; phase-trajectory-aware reshape is a T3-specific framing (T2 is "match surrounding shape"). Subsuming into T2 would conflate two different coaching surfaces under one prompt and lose the T3 mesocycle framing. Andy picked separate file 2026-05-17 Step 4d for this reason.

---

*End of `Layer4_RefreshT3_v1.md`.*
