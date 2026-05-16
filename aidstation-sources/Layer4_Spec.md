# Layer 4 — Plan Generation (LLM Synthesis + LLM Seam Review)

**Status:** Draft v1, 2026-05-16. Session 1 of an expected 3–5 sessions to land the full 14-section spec. This session covers §1 Purpose, §2 Boundaries, §3 Function signature (four entry points), and §7 Payload schema (including `RaceWeekBrief` + `RacePlan` for multi-day-event support). §§4–6 + §§8–14 are stubbed at the bottom of the file with brief targets so the next session has a clear scope. Mid-session refinements per Andy 2026-05-16 chat: added `race_week_brief` entry point (Decision 4), `RacePlan` multi-day schema (Decision 5), Layer 4.5 Joint Session Coordinator forward-pointer (Decision 6), tiered tight/loose horizon held (Decision 7), `session_index_in_day` + `time_of_day` on `PlanSession`.

**Type:** LLM. Two call patterns, picked per entry point + scope:
- **Pattern A — per-phase synthesis + LLM seam reviewer.** Used by `llm_layer4_plan_create` and by `llm_layer4_plan_refresh` T3 when the refresh window spans a phase boundary. One LLM synthesizer call per phase (Base → Build → Peak → Taper, skipping per 3B `start_phase`); one LLM seam-reviewer call per adjacent-phase boundary; deterministic validator on top of all of it.
- **Pattern B — single-call synthesis + deterministic validator.** Used by `llm_layer4_plan_refresh` T1/T2, by T3 when the scope is entirely inside a single phase, and by `llm_layer4_single_session_synthesize`. One LLM call with a tier-specific (or single-session-specific) prompt; no seams to review.

Both patterns wrap the synthesis in a capped correction loop (cap=2 retries per phase by default; surfaces a best-effort plan with a coaching observation if the cap is hit).

**Source decisions (this session, 2026-05-16):**

- **Decision 1 (topology):** Andy picked the per-phase synthesis + LLM seam reviewer architecture for the "big" calls (Pattern A above), explicitly accepting the latency tradeoff ("plan-gen is being taken seriously; 30–60s wait is fine") and the cost tradeoff ("design well, cut later if too costly"). Short-horizon calls use Pattern B with their own prompts.
- **Decision 2 (entry points):** Andy picked three distinct entry points (`plan_create`, `plan_refresh`, `single_session_synthesize`) so the expensive Pattern A only fires on `plan_create` and on T3 refreshes that span phase boundaries. T1/T2 refreshes and D-63 single-session each get their own tuned prompt under Pattern B. A fourth entry point (`llm_layer4_race_week_brief`) was added later in the same chat per the Decision-5 race-prep handling pick.
- **Decision 3 (session shape):** Andy picked the discriminated-union shape — a single `PlanSession` dataclass with `kind: Literal['cardio', 'strength', 'rest']` and conditional sub-blocks. One importable type for all downstream consumers (Layer 3A re-eval, plan view UI, D-63 storage handoff, D-64 diff rendering). Mid-session refinement: added `session_index_in_day: int` + `time_of_day` fields to support two sessions per day (strength + cardio, or two cardios of different types) with schema-level rules forbidding strength+strength and two-hards same day.
- **Decision 4 (race-prep handling):** Andy picked BOTH (a) Taper-phase coaching_flags auto-emitted (`race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) AND (b) a separate `llm_layer4_race_week_brief` entry point producing `RaceWeekBrief` + (for multi-day events) `RacePlan`. (a) lives inside existing `plan_create` / Pattern-A as auto-emit rules; (b) is a new fourth entry point with its own dedicated brief + multi-day-race schemas.
- **Decision 5 (race-day handling):** Andy picked the `RacePlan` entity for multi-day events. Single-day events: regular `PlanSession` with `coaching_flags=['race_day']` + 2E race-day fueling targets in `session_notes`. Multi-day events (expedition AR, stage races, multi-day ultras): `RacePlan` dataclass with segments + transitions + pacing + fueling + contingencies, produced by `race_week_brief`. v1 schema is intentionally lean (no per-segment athlete-checkin / actuals shape); session 2+ adds depth.
- **Decision 6 (multi-athlete coordination):** Andy picked the post-pass approach. Each athlete gets a solo Layer 4 run; a new **Layer 4.5 — Joint Session Coordinator** runs after Layer 4 for linked athletes, harmonizing joint-session days (shared shape + per-athlete intensity adjustments). Layer 4.5 is its own spec; Layer 4 §2 + §7 schemas are 4.5-ready (joint coordinator can supersede solo PlanSessions via a future `joint_session_id` FK addition).
- **Decision 7 (tiered tight/loose plan horizon — HELD):** Andy 2026-05-16: substantive direction held. Plan currently spec'd as uniform-quality across the full 3B periodization shape window. Proposed future direction (tight ~12 weeks + loose remainder + scheduled re-run as tight horizon decays) flagged as substantive open item in §12; revisit after Layer 4 v1 lands and cost/quality measured.

**Source decisions (predecessor specs):**

- `Layer3_3A_Spec.md` §7 — `Layer3APayload` (consumed input; `current_state.weak_links` drives accessory programming; `recent_trajectory` drives volume ramp shape; `data_density` drives confidence-weighted prescription).
- `Layer3_3B_Spec.md` §7 — `Layer3BPayload`, specifically `periodization_shape.mode + start_phase + phase_weeks` (consumed input; primary phase-sizing driver). `goal_viability.suggested_adjustments` surfaced for athlete-facing rationale rendering when Layer 4 overrides the shape.
- `Layer2A_Spec.md` §7 — `Layer2APayload`; discipline weights + `phase_load_bands` per discipline per phase. Drives session distribution + per-session volume bands.
- `Layer2B_Spec.md` §7 — `Layer2BPayload`; terrain × environment classification, cross-referenced with each 2C-resolved exercise's `terrain_required` pass-through.
- `Layer2C_Spec.md` §7 — `Layer2CPayload` per locale; resolved exercise pool with tier-1/2/3 substitution detail.
- `Layer2D_Spec.md` §7 — `Layer2DPayload`; injury exclusions + per-discipline downgrades applied at exercise-picking time.
- `Layer2E_Spec.md` §7 — `Layer2EPayload`; nutrition + supplement targets per phase + race-day fueling tier; surfaced in `PlanSession.session_notes` for race-rehearsal + long sessions.
- `OnDemand_Workout_D63_Design_v1.md` §4.3 — `SingleSessionRequest` (D-63 entry-point input).
- `Plan_Refresh_D64_Design_v1.md` §3 (tier definitions), §5 (`ParsedIntent` NL parser output), §6 (cascade execution + atomic version write), §7 (plan-version table — schema lands here in §7 below).

**Cross-references:**

- `Control_Spec_v8.md` §2 (Layer 4 owns / spec docs / type / HITL); §3 (Layer 3 → Layer 4 is 3D-gated; Layer 4 → Layer 5); §4 (partial-update model).
- `Athlete_Onboarding_Data_Spec_v5.md` §H (goal context source), §K (schedule — available days + per-day windows), §L (joint sessions / athlete network; out of v1 scope).
- `Athlete_Data_Integration_Spec_v5.md` — `Layer1Payload` and `q_layer1_payload` definitions.

---

## 1. Purpose

Layer 4 takes the gated outputs of Layers 2 and 3 (the five typed 2A–2E payloads, 3A's athlete state, 3B's goal viability + periodization shape) plus the athlete's Layer 1 profile and produces a structured, day-by-day training plan: a sequence of `PlanSession` records covering the requested date window, each session a fully-specified cardio block or strength block (or a rest day) ready for the athlete to execute.

Layer 4 owns the actual coaching synthesis: WHICH sport on WHICH day, at WHAT intensity, with WHICH exercises, for WHAT duration, at WHICH locale. Everything upstream is constraint and context; Layer 4 makes the coaching decision.

Layer 4 supports four entry points scoped to four different athlete intents:

- **`llm_layer4_plan_create`** — initial plan generation, called when no plan exists for the athlete (post-onboarding) or when a major upstream re-eval has invalidated the entire plan (T3 refresh of an athlete whose 3B periodization shape changed materially). Pattern A always. The single most expensive Layer 4 invocation. Output covers the full periodization window 3B sized.
- **`llm_layer4_plan_refresh`** — D-64 athlete-initiated refresh scoped to T1 (next 2 days), T2 (next 7 days), or T3 (next 28 days). T1 + T2 are Pattern B with tier-specific prompts. T3 is Pattern A when the 28-day scope spans a phase boundary (the common case mid-plan); T3 falls back to Pattern B with a per-phase prompt when the scope is entirely inside a single phase (e.g., athlete is mid-Base with 6+ weeks of Base remaining).
- **`llm_layer4_single_session_synthesize`** — D-63 on-demand workout. Off-plan, no phase context, no 3B/3C/3D dependency. Athlete picks sport + duration + intensity + locale (or "Somewhere else" with quick-equipment); Layer 4 produces one `PlanSession` (`is_ad_hoc=True`) consistent with the athlete's profile + current state + the picked location's equipment view. Pattern B.
- **`llm_layer4_race_week_brief`** — event-mode-only. Fires when `days_to_event ≤ 14` (orchestrator-triggered as the athlete approaches the event; also athlete-triggerable via a "Generate race-week brief" surface). Produces (a) modified Taper-phase sessions with race-week `coaching_flags` (`race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`) auto-populated, plus (b) a structured `RaceWeekBrief` (logistics, drop-bag strategy, kit manifest, pre-race meal, pacing summary, contingencies, mental prep cues), plus (c) for multi-day events (expedition AR, stage races, multi-day ultras), a structured `RacePlan` covering segments, transitions, pacing strategy, fueling strategy, and contingencies across the race itself. Pattern B with a longer max_tokens budget. Single-day events get only (a) + (b); multi-day events get (a) + (b) + (c).

All four entry points return `Layer4Payload` records. The `mode` discriminator + (for race_week_brief) the `race_plan` field distinguish the produced shape. Downstream consumers (Layer 3A re-eval on the next refresh, Layer 5 advisors, the athlete-facing plan view, D-63's `ad_hoc_workout_suggestions` storage handoff, D-64's diff renderer, race-week-brief surface) read the same `PlanSession` shape for session content regardless of which entry point produced the payload.

**Multi-athlete coordination is out of Layer 4's scope.** Joint sessions per §L are produced by a separate post-pass — **Layer 4.5 — Joint Session Coordinator** — which reads two or more linked athletes' Layer 4 payloads and harmonizes the joint-session days into a shared shape with per-athlete intensity adjustments. Layer 4.5 is its own spec; v1 Layer 4 produces solo plans only. Per Andy 2026-05-16 direction (post-pass coordinator approach picked over pre-pass-in-Layer-4 + cross-athlete-entry-point alternatives); see §12 forward-pointer.

The periodization validator wraps every synthesis call. Deterministic rule checks on every pass: weekly volume inside 2A `phase_load_bands` per discipline; ACWR forward-projection across the scope window stays inside the safe band (0.8–1.3 typical; per-phase tunable); rest-day spacing per discipline (no two consecutive hard sessions for the same discipline without an explicit rationale); intensity distribution matches the phase intent (Base ≈ 80/15/5 Z1-Z2/Z3/Z4-Z5; Build, Peak, Taper tunable). On Pattern A, an additional LLM seam-review pass runs between each pair of adjacent phases: the reviewer reads both phase outputs + the intended boundary state (volume + intensity exit/entry per 3B + 2A) and either approves the seam, flags it (minor or major), or proposes a patch direction (re-prompt the prior phase, re-prompt the next phase, or accept-with-observation). Validator failures trigger capped re-synthesis at the per-phase granularity; persistent failure surfaces a best-effort plan with a `best_effort_plan` coaching observation.

## 2. What Layer 4 does NOT do

Boundary clarifications. Each line is a piece of work that lives elsewhere and that Layer 4 must not absorb.

- **Does not classify the race or the disciplines.** That's 2A (discipline mix + weights, phase position) and 2B (terrain × environment). Layer 4 consumes the typed 2A/2B payloads as constraints; it does not re-derive disciplines, weights, or terrain from §H/§C/§J.
- **Does not resolve equipment.** 2C resolves the equipment-available exercise pool per locale, including tier-1/2/3 substitution chains. Layer 4 picks WHICH exercise from 2C's pool to prescribe per session — it does not re-resolve equipment, compute substitution chains, or evaluate `also_satisfies` toggle implications.
- **Does not evaluate injury risk or generate injury HITL items.** That's 2D. Layer 4 consumes 2D's exclusion/downgrade list and applies it during exercise picking; it does not generate new injury observations. If a 2D exclusion makes a planned session unworkable (e.g., wrist-loaded strength on the only strength day available), Layer 4 substitutes within the session — it does not escalate.
- **Does not compute nutrition targets, BMR, or fueling tiers.** That's 2E. Layer 4 may surface 2E's targets in `PlanSession.session_notes` for race-rehearsal + long sessions (e.g., "Practice race-day fueling: 60g CHO/hr from gels"); it does not derive them.
- **Does not judge goal viability or pick the periodization shape.** That's 3B. Layer 4 consumes 3B's `periodization_shape.mode + start_phase + phase_weeks` as the sizing input. Layer 4 may invoke the override path if the shape is structurally infeasible after capped re-synthesis (e.g., 3B says `compressed` but the athlete's §K schedule plus 2D exclusions leave no viable Build-week structure inside the window) — overrides are flagged via `shape_override` in `Layer4Payload` for athlete-facing rationale rendering per 3B §6.3.
- **Does not run the 3D HITL gate.** Layer 4 only runs after 3D returns `gate_status = green`. Layer 4 may produce `notable_observations` with `elevates_to_hitl=True` that 3D considers for the NEXT plan invocation — the current run does not block on its own observations.
- **Does not own the plan-version table's `plan_version_id` allocation policy.** The plan-gen orchestrator allocates `plan_version_id` before invoking Layer 4 and passes it in. Layer 4 writes session rows pointing to that ID. The orchestrator owns the atomic-write boundary per D-64 §6.2 (commit-or-rollback). Plan-version table SCHEMA is defined in §7.7 below (lifting the D-64 §7.2 stub).
- **Does not own the partial-update orchestrator.** Per Control_Spec §4, the orchestrator outside Layer 4 decides which upstream layers re-run on data changes; Layer 4 just gets called with the updated payloads.
- **Does not coordinate joint sessions across linked athletes.** §L of the Onboarding spec carves out joint training overlays for athletes with linked accounts. Layer 4 produces solo plans only; **Layer 4.5 — Joint Session Coordinator** runs as a post-pass over multiple athletes' Layer 4 payloads and harmonizes joint-session days (picks shared session shape, adjusts per-athlete intensity within fitness levels). Layer 4.5 spec is its own work item; see §12 forward-pointer.
- **Does not write to integration tables.** When the athlete LOGS a session (completes it), the plan-execution surface writes to `cardio_log` / `training_log`. Layer 4 produces the spec; execution stores it; logging captures completion. The `is_ad_hoc=True` D-63 session is written to `ad_hoc_workout_suggestions` by D-63's caller (not Layer 4); Layer 4 only returns the `PlanSession` for the caller to persist.
- **Does not re-evaluate the plan on a schedule.** Time-based re-eval cadence is D-57 (deferred). Layer 4 runs when invoked.
- **Does not parse free-text athlete input.** That's the D-64 NL intent parser. Layer 4 consumes the parsed `ParsedIntent` dataclass + the `raw_text` passthrough; it does not re-classify the NL itself.
- **Does not generate Layer 5 supplemental outputs.** Layer 5 (parallel: daily nutrition, supplements, 7-day clothing/conditions advisor) consumes Layer 4 output. Layer 4 does not generate these surfaces — it produces only the training plan.

## 3. Function signature

Three entry points. All three return `Layer4Payload`; the payload's `mode` discriminator tells consumers which entry point produced it. The orchestrator above Layer 4 picks the entry point based on caller intent (initial plan vs. D-64 refresh vs. D-63 single-session).

### 3.1 Plan create

```python
def llm_layer4_plan_create(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    plan_start_date: date,
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens_per_phase: int = 4000,
    capped_retries_per_phase: int = 2,
) -> Layer4Payload:
    ...
```

**Parameters:**

| Param | Type | Source | Notes |
|---|---|---|---|
| `user_id` | int | Plan-gen orchestrator | Cache key + prompt logging; not exposed to the LLM directly. |
| `layer1_payload` | `Layer1Payload` | `q_layer1_payload(user_id, as_of)` | Full Layer 1 dataclass. Layer 4 consumes §A demographics (age, sex for contextual coaching voice); §B (injury exclusions are 2D-resolved but §B context is read for session-notes copy); §H (goal context for coaching voice + race-rehearsal scheduling); §I (sleep/stress/lifestyle for daily intensity modulation); §J (locale picker context — which locale to use per session per athlete's per-day availability); §K (schedule — available days + per-day windows; drives session-on-which-day picking); §L (joint sessions — read but not consumed in v1 per §2). |
| `layer2a_payload` | `Layer2APayload` | 2A node output | Discipline weights + `phase_load_bands` per discipline per phase. Drives session distribution across disciplines per week + per-session volume bands. |
| `layer2b_payload` | `Layer2BPayload` | 2B node output | Terrain × environment classification per the athlete's race + locale set. Layer 4 reads `terrain_required` on each 2C-resolved exercise and cross-references 2B's per-locale terrain availability when picking a locale for a session. |
| `layer2c_payloads` | `dict[str, Layer2CPayload]` | One 2C call per locale in the athlete's cluster | Keyed by `locale_id`. Layer 4 picks the locale per session (driven by §K schedule + travel windows + 2B terrain fit) and reads that locale's resolved exercise pool when prescribing strength or specific cardio session types. |
| `layer2d_payload` | `Layer2DPayload` | 2D node output | Injury exclusions + per-discipline downgrades. Applied to every 2C exercise pool at picking time; never silently overridden. |
| `layer2e_payload` | `Layer2EPayload` | 2E node output | Nutrition + supplement targets per phase + race-day fueling tier. Surfaced in `session_notes` for race-rehearsal + long sessions; not used for session-structure decisions. |
| `layer3a_payload` | `Layer3APayload` | 3A node output | Current state (aerobic + strength assessments + confidence) + `recent_trajectory` (drives volume ramp shape) + `weak_links` (drives accessory programming priority) + `data_density` (drives confidence-weighted intensity prescription — sparse-data athletes get more conservative ramps). |
| `layer3b_payload` | `Layer3BPayload` | 3B node output | `periodization_shape.mode` + `start_phase` + (when `mode == 'custom'`) `phase_weeks`. Primary phase-sizing driver. `goal_viability.suggested_adjustments` surfaced in `notable_observations` for the athlete-facing rationale. |
| `plan_start_date` | `date` | Plan-gen orchestrator | Anchor for phase week numbering. Typically today or the next valid day per §K schedule. |
| `plan_version_id` | int | Plan-gen orchestrator | Allocated by the orchestrator before invocation per D-64 §6.2 atomic-write semantics. Layer 4 writes all session rows pointing to this ID; orchestrator commits the whole set or rolls back. |
| `etl_version_set` | `dict[str, str]` | Plan-gen pin | Per Control_Spec §6. Validated against every input payload's `etl_version_set` field; mismatch is a precondition failure (§4 stub). |
| `model_synthesizer` | str | Default Sonnet 4.6 | Used for per-phase synthesis calls. Overridable for cost/experiments; bumping requires regression test pass on §13 (stub). |
| `model_seam_reviewer` | str | Default Sonnet 4.6 | Used for the LLM seam-review pass between adjacent phases. Same model is fine as v1 default; could downgrade to Haiku for cost if the reviewer's job is simple enough — measure post-launch. |
| `temperature` | float | Default 0.2 | Low for reproducibility. Operating band 0.1–0.3. Applied to both synthesizer and reviewer. |
| `max_tokens_per_phase` | int | Default 4000 | Per-phase output budget. A 4-phase plan totals ~12–20k output tokens; the per-phase decomposition keeps each call inside Sonnet's reliable structured-output window. |
| `capped_retries_per_phase` | int | Default 2 | Per-phase validator-failure retry budget. After cap, that phase outputs best-effort with a coaching observation; subsequent phases still run. |

**Returns:** `Layer4Payload` with `mode='plan_create'`, `phase_structure` non-None, `seam_reviews` non-None (one entry per phase boundary; empty when there's only one phase to synthesize).

### 3.2 Plan refresh

```python
def llm_layer4_plan_refresh(
    user_id: int,
    tier: Literal['T1', 'T2', 'T3'],
    refresh_scope_start: date,
    refresh_scope_end: date,
    layer1_payload: Layer1Payload,
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload | None,
    prior_plan_session_window: list[PlanSession],
    parsed_intent: ParsedIntent | None,
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens: int = 4000,
    capped_retries: int = 2,
) -> Layer4Payload:
    ...
```

**Parameters:**

| Param | Type | Source | Notes |
|---|---|---|---|
| `user_id` | int | D-64 caller | — |
| `tier` | `Literal['T1', 'T2', 'T3']` | D-64 caller | Drives prompt template + Pattern picking. T1/T2 → Pattern B with tier-specific prompts. T3 → Pattern A when scope spans a phase boundary; Pattern B with a long-window prompt otherwise. |
| `refresh_scope_start` | date | D-64 caller | Start of refresh window. Typically today, or next uncompleted day for T1 if today's session is already complete. |
| `refresh_scope_end` | date | D-64 caller | End of refresh window. Length per tier: T1 = start + 2 days; T2 = start + 7 days; T3 = start + 28 days. Validated in §4 stub. |
| `layer1_payload` | `Layer1Payload` | Per `q_layer1_payload` | Same as `plan_create`. |
| `layer2_bundle` | `Layer2Bundle` | Bundle of conditionally-re-run 2A/2B/2C/2D/2E payloads | Typed wrapper that exposes each payload as an attribute (`bundle.a`, `bundle.b`, `bundle.c`, `bundle.d`, `bundle.e`) or `None` if that layer wasn't re-run for this refresh. T1 default cascade: only 3A re-runs, so all five attributes are None except as added by `parsed_intent`. T2 default: 3A + 3B (Layer 2 still None unless intent-triggered). T3 default: all five Layer 2 attributes populated. Per D-64 §3 cascade definitions. |
| `layer3a_payload` | `Layer3APayload` | 3A re-run output | All three tiers re-run 3A. |
| `layer3b_payload` | `Layer3BPayload \| None` | 3B re-run output (T2/T3) or None (T1) | T1 doesn't re-run 3B. T2 + T3 do. When None, Layer 4 falls back to the prior plan's periodization shape (read from `prior_plan_session_window[*].phase_metadata` — see §7). |
| `prior_plan_session_window` | `list[PlanSession]` | Plan-gen orchestrator | The current plan's `PlanSession` records covering `[refresh_scope_start - 7, refresh_scope_end + 7]` (the refresh window plus 7 days of context on each side). Layer 4 reads for continuity (what intensity the athlete was already doing, what's coming after the refresh window). Sessions outside the refresh window are NOT modified; they remain pointed at their prior `plan_version_id`. |
| `parsed_intent` | `ParsedIntent \| None` | D-64 NL parser output | When non-None, drives soft signals (fatigue / sickness / motivation enums) + the NL `raw_text` is passed through to the synthesizer prompt for context weighting. `None` when athlete refreshed without NL text or when the parser was unavailable (per D-64 §5.4 degraded path). |
| `plan_version_id` | int | Plan-gen orchestrator | New version ID per D-64 §6.2. Layer 4 writes all session rows in the refresh window pointing to this ID; out-of-window sessions keep their prior ID (per-day version pointer per D-64 §6.3). |
| `etl_version_set` | dict[str, str] | Plan-gen pin | Per Control_Spec §6. |
| `model_synthesizer` / `model_seam_reviewer` / `temperature` / `max_tokens` / `capped_retries` | various | Defaults per §3.1 framing | `model_seam_reviewer` only used when T3 + scope spans phase boundary (Pattern A). T1/T2/single-phase-T3 are Pattern B, no seam reviewer. |

**Returns:** `Layer4Payload` with `mode='plan_refresh'`. `phase_structure` non-None only when Pattern A activated (T3 + scope spans phase boundary); `seam_reviews` non-None on the same condition.

### 3.3 Single session synthesize

```python
def llm_layer4_single_session_synthesize(
    user_id: int,
    request: SingleSessionRequest,
    layer1_payload: Layer1Payload,
    layer2c_payload_for_locale: Layer2CPayload | None,
    layer2d_payload: Layer2DPayload,
    layer3a_payload: Layer3APayload,
    suggestion_id: int,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.3,
    max_tokens: int = 1500,
    capped_retries: int = 2,
) -> Layer4Payload:
    ...
```

**Parameters:**

| Param | Type | Source | Notes |
|---|---|---|---|
| `user_id` | int | D-63 caller | — |
| `request` | `SingleSessionRequest` | D-63 §4.3 contract | Athlete-supplied: `sport`, `duration_min`, `intensity`, `locale_slug` (athlete's locale slug, OR None for "Somewhere else"), `quick_equipment` (list of equipment tokens when `locale_slug is None`), `notes_for_synthesizer` (optional). |
| `layer1_payload` | `Layer1Payload` | Per `q_layer1_payload` | Athlete profile for constraint resolution. |
| `layer2c_payload_for_locale` | `Layer2CPayload \| None` | One 2C call for the picked locale | None when `request.locale_slug` is None (athlete picked "Somewhere else" — equipment resolved from `request.quick_equipment` directly without going through 2C). When non-None, supplies the resolved exercise pool for the picked locale. |
| `layer2d_payload` | `Layer2DPayload` | 2D node output (cached) | Active injury exclusions; D-63 §6.1 framing — profile-level constraints not user-overridable per-request. |
| `layer3a_payload` | `Layer3APayload` | 3A node output (cached) | Current state + recent trajectory. Drives intensity modulation per D-63 §6.2 (athlete picks "hard" but recent ACWR + just-did-a-hard-session signals push toward moderate; coaching voice surfaces the modulation in `session_notes`). |
| `suggestion_id` | int | D-63 caller | Allocated by D-63 (`ad_hoc_workout_suggestions.id`); Layer 4 writes it into `Layer4Payload.suggestion_id` for the storage handoff. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | — |
| `model` | str | Default Sonnet 4.6 | Single LLM call (Pattern B). |
| `temperature` | float | Default 0.3 | Higher than Pattern A's 0.2 — athlete-facing [Regenerate] benefits from more variation. |
| `max_tokens` | int | Default 1500 | One session output; fits comfortably. |
| `capped_retries` | int | Default 2 | Validator-failure retry budget. |

**Returns:** `Layer4Payload` with `mode='single_session_synthesize'`, `len(sessions) == 1`, `sessions[0].is_ad_hoc == True`, `suggestion_id` populated, `phase_structure is None`, `seam_reviews is None`.

### 3.4 Race-week brief

```python
def llm_layer4_race_week_brief(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    prior_plan_session_window: list[PlanSession],
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens: int = 6000,
    capped_retries: int = 2,
) -> Layer4Payload:
    ...
```

Fires when `days_to_event ≤ 14` (orchestrator-triggered as the athlete approaches the event) OR when the athlete explicitly requests a race-week brief via the dedicated surface. Event-mode only (`layer3b_payload.mode == 'event'`); raises `Layer4InputError('race_week_brief_requires_event_mode')` otherwise.

**Parameters:**

| Param | Type | Source | Notes |
|---|---|---|---|
| `user_id` | int | Orchestrator | — |
| `layer1_payload` | `Layer1Payload` | Per `q_layer1_payload` | Full Layer 1; §H.2 event details + §J event-locale equipment view + §I lifestyle for pre-race sleep/recovery guidance. |
| `layer2a_payload` | `Layer2APayload` | 2A node output | Discipline weights for race-segment sport classification (multi-day events). |
| `layer2b_payload` | `Layer2BPayload` | 2B node output | Race terrain × environment classification; drives pacing/kit guidance per segment. |
| `layer2c_payloads` | `dict[str, Layer2CPayload]` | 2C call per locale (including race locale) | Equipment view for kit-check + race-locale equipment availability. |
| `layer2d_payload` | `Layer2DPayload` | 2D node output | Active injury exclusions applied to race-rehearsal session content + flagged in contingencies. |
| `layer2e_payload` | `Layer2EPayload` | 2E node output | Race-day fueling tier + macro/sodium/fluid targets; drives `RaceWeekBrief.race_day_fueling_plan` + `RacePlan.fueling_strategy`. |
| `layer3a_payload` | `Layer3APayload` | 3A node output | Current state + recent trajectory; modulates pacing-strategy aggressiveness + contingency depth. |
| `layer3b_payload` | `Layer3BPayload` | 3B node output | `goal_viability` + `periodization_shape.phase_weeks['Taper']` drives Taper-session race-week flag distribution. |
| `prior_plan_session_window` | `list[PlanSession]` | Plan-gen orchestrator | The current plan's Taper-phase sessions (typically the last 14–21 days of the plan). Layer 4 may modify these in place (adding race-week `coaching_flags`) and return the modified set in `Layer4Payload.sessions`. |
| `plan_version_id` | int | Orchestrator | New version ID per D-64 §6.2 atomic-write. |
| `etl_version_set` | dict[str, str] | Plan-gen pin | — |
| `model` / `temperature` / `max_tokens` / `capped_retries` | various | Defaults | `max_tokens=6000` is higher than other Pattern B paths because the brief + (for multi-day events) the RacePlan can be substantial output. |

**Returns:** `Layer4Payload` with `mode='race_week_brief'`, `pattern='B'`, `sessions` = modified Taper-phase sessions, `race_week_brief` non-None, `race_plan` non-None for multi-day events (`race_format` ∈ `{'expedition_ar', 'stage_race', 'multi_day_ultra'}`) and None for single-day events (`race_format == 'single_day'`), `phase_structure is None`, `seam_reviews is None`.

### 3.5 Errors raised

All four entry points raise typed errors. Detail in §4 stub.

- `Layer4InputError(code)` — precondition violations. Includes `race_week_brief_requires_event_mode` for §3.4 misuse.
- `Layer4OutputError(code)` — validator could not produce an accepted plan within the retry cap AND the best-effort fallback could not be assembled (rare).
- `Layer4ShapeInfeasibleError(...)` — 3B periodization shape is structurally impossible for the athlete's §K availability + 2D exclusions; surfaces to 3D for the next gate, not handled by Layer 4 itself.

---

## 7. Payload schema

### 7.1 Layer4Payload

```python
@dataclass
class Layer4Payload:
    # ─── Metadata ──────────────────────────────────────────────────────
    user_id: int
    mode: Literal['plan_create', 'plan_refresh', 'single_session_synthesize', 'race_week_brief']
    plan_version_id: int
    scope_start_date: date                 # First date covered by sessions[]
    scope_end_date: date                   # Last date covered by sessions[] (inclusive)
    model_synthesizer: str                 # Model used for synthesis call(s)
    model_seam_reviewer: str | None        # None when Pattern B (no seam review ran)
    temperature: float
    pattern: Literal['A', 'B']             # Which call pattern ran; convenience field for consumers
    latency_ms_total: int                  # End-to-end including all per-phase calls + seam reviews + validator retries
    input_tokens_total: int                # Summed across all LLM calls
    output_tokens_total: int               # Summed across all LLM calls
    llm_call_count: int                    # 1 for Pattern B; 1 per phase + 1 per seam for Pattern A (modulo retries)
    etl_version_set: dict[str, str]

    # ─── Core output ───────────────────────────────────────────────────
    sessions: list[PlanSession]            # Day-by-day; sorted by date; includes rest-day placeholders for days with no session

    # ─── Periodization context (Pattern A only; None for Pattern B) ───
    phase_structure: PhaseStructure | None
    seam_reviews: list[SeamReview] | None  # One entry per adjacent-phase boundary reviewed

    # ─── Layer 4 overrides (populated only when Layer 4 overrode 3B's shape) ─
    shape_override: ShapeOverride | None

    # ─── Validator output ──────────────────────────────────────────────
    validator_results: list[ValidatorResult]   # One entry per validator pass; last entry is the accepted output

    # ─── Coaching observations (downstream-actionable notes) ──────────
    notable_observations: list[Observation]

    # ─── D-63 handoff metadata (populated only for single_session_synthesize mode) ─
    suggestion_id: int | None

    # ─── Race-week brief (populated only for race_week_brief mode) ─────────
    race_week_brief: RaceWeekBrief | None
    race_plan: RacePlan | None             # Multi-day events only; None for single-day events even in race_week_brief mode
```

### 7.2 PlanSession (discriminated union)

```python
@dataclass
class PlanSession:
    # ─── Identity + scheduling ───────────────────────────────────────
    session_id: str                        # UUID; unique per session row
    plan_version_id: int                   # FK to the plan version this session was written under
    date: date
    day_of_week: Literal['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    session_index_in_day: int              # 0 = first session of the day; 1 = second; v1 max = 1 (two sessions per day)
    time_of_day: Literal['morning', 'afternoon', 'evening', 'unspecified']
    kind: Literal['cardio', 'strength', 'rest']

    # ─── Discipline + locale + summary ───────────────────────────────
    discipline_id: str | None              # Layer 1 discipline ID; None for rest days
    discipline_name: str | None
    locale_id: str | None                  # Picked locale; None for rest days
    locale_name: str | None
    duration_min: int                      # 0 for rest; otherwise the prescribed session length
    intensity_summary: Literal['easy', 'moderate', 'hard', 'mixed', 'rest']

    # ─── Cardio sub-block (populated only when kind == 'cardio') ─────
    cardio_blocks: list[CardioBlock] | None

    # ─── Strength sub-block (populated only when kind == 'strength') ─
    strength_exercises: list[StrengthExercise] | None

    # ─── Rest sub-block (populated only when kind == 'rest') ─────────
    rest_reason: Literal['planned_recovery', 'overreach_protection', 'travel_day', 'athlete_unavailable', 'taper_drop'] | None

    # ─── Phase-context metadata (populated for plan_create + Pattern-A T3; None otherwise) ─
    phase_metadata: SessionPhaseMetadata | None

    # ─── Coaching surface (athlete-facing + Layer 3A interpretation input) ─
    session_notes: str                     # Athlete-facing summary (1–3 sentences, direct voice)
    coaching_intent: str                   # Why this session exists in the plan (1 sentence; consumed by Layer 3A interpretation)
    coaching_flags: list[str]              # e.g. ['race_rehearsal', 'fueling_practice', 'first_introduction_to_<discipline>', 'weak_link_targeted']

    # ─── Ad-hoc context (populated only when produced via single_session_synthesize) ─
    is_ad_hoc: bool                        # True for D-63 sessions; False for planned + refreshed sessions
    ad_hoc_request_payload: dict | None    # Mirror of the SingleSessionRequest when is_ad_hoc; None otherwise
```

### 7.3 CardioBlock

```python
@dataclass
class CardioBlock:
    block_kind: Literal['warmup', 'main_set', 'cooldown', 'interval_set', 'transition']
    duration_min: int
    intensity_zone: Literal['Z1', 'Z2', 'Z3', 'Z4', 'Z5', 'mixed']
    intensity_target: dict                 # Free-shape per-discipline: e.g. {'pace_per_km': '5:30'} | {'power_w': 220} | {'hr_bpm_low': 140, 'hr_bpm_high': 155} | {'rpe': 6}
    instructions: str                      # Athlete-facing block text
    # Interval-block-specific (None for non-interval blocks):
    repetitions: int | None
    rest_between_min: int | None
    rest_intensity_zone: Literal['Z1', 'Z2'] | None    # Active recovery between intervals
```

### 7.4 StrengthExercise

```python
@dataclass
class StrengthExercise:
    exercise_id: str                       # 2C-resolved exercise ID (or 2C-Tier-3 proxy exercise ID)
    exercise_name: str                     # 2C-resolved exercise name (or proxy name)
    resolution_tier: Literal[1, 2, 3]      # From 2C
    substitute_text: str | None            # Populated for Tier 2 substitutes per 2C resolution
    proxy_origin_id: str | None            # Populated for Tier 3 — original exercise this is proxying for
    sets: int
    reps_per_set: int | str                # Int for fixed reps; str for "AMRAP" or range like "8–12"
    load_prescription: str                 # Free-shape: '70% 1RM' | 'bodyweight' | '15 kg dumbbells' | 'progress from week 1 load'
    rest_between_sets_sec: int
    tempo: str | None                      # e.g. '3-1-1-0' (eccentric-bottom-concentric-top); None for unspecified
    instructions: str                      # Athlete-facing exercise text
    coaching_flags: list[str]              # e.g. ['weak_link_targeted', 'eccentric_emphasis', 'unilateral_focus']
```

### 7.5 SessionPhaseMetadata

```python
@dataclass
class SessionPhaseMetadata:
    phase_name: Literal['Base', 'Build', 'Peak', 'Taper']
    week_in_phase: int                     # 1-indexed
    total_weeks_in_phase: int
    intended_volume_band: tuple[float, float]    # Hours/week (low, high) per 2A
    intended_intensity_distribution: dict        # e.g. {'Z1-Z2': 0.80, 'Z3': 0.15, 'Z4-Z5': 0.05}
```

### 7.6 PhaseStructure (Pattern A only)

```python
@dataclass
class PhaseStructure:
    phases: list[PhaseSpec]                # Ordered (subset of) Base → Build → Peak → Taper per 3B start_phase
    total_weeks: int
    derived_from: Literal['3b_standard', '3b_compressed', '3b_extended', '3b_custom', 'layer4_override']

@dataclass
class PhaseSpec:
    phase_name: Literal['Base', 'Build', 'Peak', 'Taper']
    start_date: date
    end_date: date
    weeks: int
    intended_volume_band: tuple[float, float]
    intended_intensity_distribution: dict
    synthesis_metadata: SynthesisMetadata

@dataclass
class SynthesisMetadata:
    model: str
    temperature: float
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries_used: int                      # 0 to capped_retries_per_phase
    cap_hit: bool                          # True if capped_retries_per_phase was exhausted and best-effort was accepted
```

### 7.7 SeamReview (Pattern A only)

```python
@dataclass
class SeamReview:
    seam_index: int                        # 0 = first seam in phases[] order; 1 = next; ...
    prior_phase_name: Literal['Base', 'Build', 'Peak']
    next_phase_name: Literal['Build', 'Peak', 'Taper']
    reviewer_verdict: Literal['approved', 'flagged_minor', 'flagged_major', 'patched']
    seam_issues: list[str]                 # Free-text per issue; empty when approved
    proposed_patch_direction: Literal['re_prompt_prior', 're_prompt_next', 'accept_with_observation'] | None
    triggered_resynthesis: bool            # True if seam review caused a phase re-prompt
    re_prompted_phase_name: Literal['Base', 'Build', 'Peak', 'Taper'] | None
    reviewer_model: str
    reviewer_input_tokens: int
    reviewer_output_tokens: int
    reviewer_latency_ms: int
```

### 7.8 ShapeOverride

```python
@dataclass
class ShapeOverride:
    original_shape_mode: str               # From 3B periodization_shape.mode
    original_start_phase: str              # From 3B
    overridden_mode: str                   # Layer 4's choice
    overridden_start_phase: str            # Layer 4's choice
    rationale_text: str                    # Athlete-facing — surfaces in plan-view diff per 3B §6.3
    evidence_basis: list[str]              # Field references
```

### 7.9 ValidatorResult

```python
@dataclass
class ValidatorResult:
    pass_index: int                        # 0 = first attempt; 1, 2... after retries
    accepted: bool
    rule_failures: list[RuleFailure]       # Empty when accepted
    retried_phase_names: list[str]         # Phases re-prompted after this pass; empty on accepted

@dataclass
class RuleFailure:
    rule_name: str                         # e.g. 'volume_band_exceeded_week_3' | 'acwr_forward_projection_above_1_4' | 'hard_session_pair_no_recovery' | 'intensity_distribution_drift_phase_build'
    phase_name: str | None                 # None for cross-phase rules (e.g. ACWR forward projection across the whole window)
    severity: Literal['blocker', 'warning']
    detail: str                            # Free-text explanation
    affected_session_ids: list[str]
```

### 7.10 Observation

```python
@dataclass
class Observation:
    category: Literal[
        'warning',
        'opportunity',
        'data_gap',
        'data_hygiene',
        'shape_override',
        'best_effort_plan',
        'intensity_modulated',           # D-63 §6.2 — synthesizer modulated athlete's picked intensity
        'sport_unavailable_at_locale',   # D-63 §6.3 — error case
        'off_plan_day_note',             # D-63 §6.4 — informational
    ]
    text: str                              # Human-readable, ≤ 240 chars
    evidence_basis: list[str]
    elevates_to_hitl: bool                 # Considered for the NEXT plan's 3D gate
```

### 7.11 plan_versions table (lifts D-64 §7.2 stub)

```sql
CREATE TABLE plan_versions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_via TEXT NOT NULL CHECK (created_via IN ('plan_create', 'plan_refresh_t1', 'plan_refresh_t2', 'plan_refresh_t3', 'single_session_synthesize')),
    scope_start_date DATE NOT NULL,
    scope_end_date DATE NOT NULL,
    pattern CHAR(1) NOT NULL CHECK (pattern IN ('A', 'B')),
    superseded_at TIMESTAMPTZ,             -- Set when a subsequent plan version covers any of this version's date range
    superseded_by_version_id BIGINT REFERENCES plan_versions(id),
    notes JSONB                            -- Free-form metadata (model/temperature snapshot, seam_reviews summary, etc.)
);

CREATE INDEX plan_versions_user_created_idx ON plan_versions (user_id, created_at DESC);
CREATE INDEX plan_versions_user_scope_idx ON plan_versions (user_id, scope_start_date, scope_end_date);
```

Each `plan_session` row carries a `plan_version_id` FK; the per-day version pointer per D-64 §6.3 is implemented by `plan_session.date` + `plan_session.plan_version_id` — the resolver picks the most-recent-version row per date when surfacing the plan. The `superseded_at` / `superseded_by_version_id` columns are denormalized convenience fields for the revert UX; the per-day pointer is the source of truth.

### 7.12 Schema-level rules

- `Layer4Payload.mode == 'plan_create'` requires `phase_structure` non-None + `seam_reviews` non-None (may be empty list when there's only one phase to synthesize per 3B `start_phase`).
- `Layer4Payload.mode == 'plan_refresh'` + `pattern == 'A'` requires `phase_structure` non-None + `seam_reviews` non-None.
- `Layer4Payload.mode == 'plan_refresh'` + `pattern == 'B'` requires `phase_structure is None` + `seam_reviews is None`.
- `Layer4Payload.mode == 'single_session_synthesize'` requires `pattern == 'B'` + `len(sessions) == 1` + `sessions[0].is_ad_hoc == True` + `phase_structure is None` + `seam_reviews is None` + `suggestion_id` non-None.
- `Layer4Payload.mode == 'race_week_brief'` requires `pattern == 'B'` + `race_week_brief` non-None + `phase_structure is None` + `seam_reviews is None`. `race_plan` non-None iff `race_week_brief.race_format != 'single_day'`.
- `PlanSession` natural key is `(plan_version_id, date, session_index_in_day)`. v1 invariant: `0 ≤ session_index_in_day ≤ 1` (max two sessions per day).
- On any given `(plan_version_id, date)` pair: if `count(sessions) == 2`, NOT both `kind == 'strength'` (no strength+strength same day); NOT both `intensity_summary == 'hard'` (no two hard sessions same day, regardless of `kind`). At least one of the two sessions must have `kind == 'cardio'`.
- `time_of_day == 'unspecified'` is allowed; consumers default to ordering by `session_index_in_day` when time is unspecified.
- `PlanSession.kind == 'cardio'` requires `cardio_blocks` non-None and non-empty + `strength_exercises is None` + `rest_reason is None`.
- `PlanSession.kind == 'strength'` requires `strength_exercises` non-None and non-empty + `cardio_blocks is None` + `rest_reason is None`.
- `PlanSession.kind == 'rest'` requires `cardio_blocks is None` + `strength_exercises is None` + `rest_reason` non-None + `duration_min == 0` + `discipline_id is None` + `locale_id is None`.
- `PlanSession.is_ad_hoc == True` requires `ad_hoc_request_payload` non-None and that the producer was `single_session_synthesize` (the orchestrator must not create `is_ad_hoc=True` sessions through other entry points).
- `PlanSession.phase_metadata` non-None when the producer was `plan_create` or Pattern-A `plan_refresh`; None for Pattern-B refreshes (no phase decomposition) and for `single_session_synthesize`.
- `CardioBlock.block_kind == 'interval_set'` requires `repetitions`, `rest_between_min`, and `rest_intensity_zone` all non-None.
- `CardioBlock.block_kind` ∈ `{'warmup', 'main_set', 'cooldown', 'transition'}` requires `repetitions is None` + `rest_between_min is None` + `rest_intensity_zone is None`.
- `StrengthExercise.resolution_tier == 2` requires `substitute_text` non-None.
- `StrengthExercise.resolution_tier == 3` requires `proxy_origin_id` non-None.
- `StrengthExercise.resolution_tier == 1` requires `substitute_text is None` + `proxy_origin_id is None`.
- `ShapeOverride` non-None requires the corresponding `Layer4Payload.notable_observations` contains an entry with `category == 'shape_override'`.
- `ValidatorResult` list is non-empty and the LAST entry has `accepted == True` (the final pass is always the accepted one — including the best-effort acceptance after the retry cap, in which case the corresponding pass has `accepted=True` + `rule_failures` retains the unresolved failures as `warning` severity + `notable_observations` carries a `best_effort_plan` entry).

### 7.13 RaceWeekBrief (race_week_brief mode only)

Produced by `llm_layer4_race_week_brief` for all event-mode invocations (single-day and multi-day). The brief is athlete-facing; consumed by the race-week-brief surface (UI TBD) and by Layer 5's clothing/conditions advisor for race-day kit overlays.

```python
@dataclass
class RaceWeekBrief:
    days_to_event: int
    event_name: str                        # From §H.2
    event_date: date
    event_locale: str                      # Locale ID; resolves to lat/lon/name via Layer 1 §J
    race_format: Literal['single_day', 'expedition_ar', 'stage_race', 'multi_day_ultra']
    goal_outcome: str                      # From 3B + §H.2 (e.g., 'Finish', 'Compete mid-pack', 'Podium attempt')

    # Pre-race logistics
    pre_race_logistics: str                # Travel + arrival timing + sleep strategy (1–3 sentences)
    drop_bag_strategy: str | None          # For events with drop-bag systems; None when not applicable
    course_familiarization_notes: str | None  # Recon recommendations + critical course sections

    # Equipment
    kit_manifest: list[KitItem]            # Per-locale + per-segment equipment to bring
    kit_check_dates: list[date]            # When to verify kit (typically days_to_event-7, -3, -1)

    # Fueling
    race_day_fueling_plan: str             # From 2E race-day fueling tier; athlete-facing summary
    pre_race_meal_strategy: str            # Last 24h fueling + race-morning meal timing

    # Pacing + mental
    pacing_strategy_summary: str           # 1–2 sentences; defers to RacePlan.pacing_strategy for multi-day depth
    contingencies: list[str]               # Pre-thought-through plans for known failure modes
    mental_prep_cues: list[str]            # Direct, evidence-grounded — no platitudes per CLAUDE.md coaching voice

@dataclass
class KitItem:
    item: str                              # Canonical equipment name from layer0.equipment_items where applicable; free-text otherwise
    purpose: str                           # Why it's on the list (e.g., 'mandatory by race rules', 'nutrition transport', 'safety')
    optional: bool                         # False = must-have; True = nice-to-have
```

### 7.14 RacePlan (race_week_brief mode, multi-day events only)

Produced by `llm_layer4_race_week_brief` only when `event_format != 'single_day'`. Captures the multi-segment execution shape of expedition AR, stage races, and multi-day ultras. Athletes consume during the race itself (typically printed / loaded offline) and the post-pass coordinator (D-64 NL parser when athlete uses race-week NL refresh) reads it for context.

```python
@dataclass
class RacePlan:
    race_name: str
    race_start_datetime: datetime          # Includes timezone
    race_end_estimate_datetime: datetime   # Estimated; per §H.2 estimated_duration_hr
    race_format: Literal['expedition_ar', 'stage_race', 'multi_day_ultra']
    locales: list[str]                     # Locale IDs covering the race route (in route order)
    segments: list[RaceSegment]            # Chronologically ordered
    transitions: list[TransitionSpec]      # Between adjacent segments
    pacing_strategy: PacingStrategy
    fueling_strategy: FuelingStrategy
    contingencies: list[Contingency]

@dataclass
class RaceSegment:
    segment_id: str                        # UUID; stable per RacePlan
    segment_index: int                     # 0-indexed chronological order
    sport: str                             # Layer 0A canonical sport name
    estimated_start_offset_hr: float       # Hours from race_start_datetime
    estimated_duration_min: int
    distance_km: float | None              # None when not applicable (e.g., a nav-puzzle segment)
    elevation_gain_m: float | None
    terrain_notes: str                     # Surface + technical features + key landmarks
    pacing_target: dict                    # Same shape as CardioBlock.intensity_target (zone + measure)
    coaching_notes: str                    # Per-segment direct guidance

@dataclass
class TransitionSpec:
    from_segment_id: str
    to_segment_id: str
    estimated_duration_min: int
    gear_changes: list[str]                # e.g., ['swap pack to MTB pack', 'change shoes to MTB shoes']
    is_fueling_window: bool                # True when this transition is a 'eat substantially' opportunity
    notes: str

@dataclass
class PacingStrategy:
    overall_intensity_target: str          # e.g., 'Z2 dominant; no Z4 unless emergency'
    night_section_adjustment: str | None   # For multi-day events crossing night hours; None when not applicable
    pacing_milestones: list[str]           # Per-segment expected splits or check-in times
    rationale_text: str                    # Why this strategy fits the athlete + race + 3A current state

@dataclass
class FuelingStrategy:
    cho_g_per_hr_low: int                  # Range; varies by intensity zone (Z1-Z2 lower; Z3+ higher)
    cho_g_per_hr_high: int
    sodium_mg_per_hr: int                  # From 2E race-day fueling + heat_acclim_state
    fluid_ml_per_hr: int                   # Adjustable per RaceSegment.terrain_notes (hot vs. cool)
    caffeine_strategy: str
    night_section_strategy: str | None     # Multi-day events; sleep deprivation fueling per 2E §I sleep_dep
    rationale_text: str

@dataclass
class Contingency:
    trigger: str                           # Specific observable signal (e.g., 'GI distress past hour 12', 'rain onset + temp drop')
    action_plan: str                       # What to do
    threshold_to_invoke: str               # When to act (e.g., 'persists >30min and Pepto fails')
```

The `RacePlan` schema is intentionally lean for v1 — it captures the load-bearing structure (segments + transitions + strategy + contingencies) without over-specifying. Session 2 may add per-segment athlete-checkin shape (logging actual time/pace per segment for post-race analysis) once the race-execution surface is designed.

---

## 4. Input validation (preconditions) — to be drafted in session 2

Per-entry-point precondition tables. `plan_create` requires all 8 upstream payloads non-None + 3B periodization shape valid (mode ∈ enum; `phase_weeks` populated when `mode == 'custom'`) + `etl_version_set` matches across all payloads. `plan_refresh` requires `tier` matches the scope-window length within tolerance (T1: 2 ± 1 days; T2: 7 ± 2; T3: 28 ± 4); `prior_plan_session_window` non-empty (refreshing an athlete who has no prior plan is a `plan_create` call, not a refresh); `parsed_intent` schema-valid when present. `single_session_synthesize` requires `request.duration_min ∈ [30, 360]`; `request.intensity` in enum; `request.locale_slug` xor `request.quick_equipment` populated; `layer2c_payload_for_locale` non-None iff `request.locale_slug` non-None. Typed `Layer4InputError(code)` raised on failure; orchestrator catches and routes per code.

## 5. Algorithm — to be drafted in session 2

Three execution paths. **Pattern A (per-phase + LLM seam reviewer)** for `plan_create` and `plan_refresh` T3 with cross-phase scope: synthesizer prompt per phase invoked sequentially (Base → Build → Peak → Taper, skipping phases per 3B `start_phase`); each phase's accepted output fed as context to the next; LLM seam-reviewer call between each pair of adjacent phases reads both phase outputs + the intended boundary state (volume + intensity exit/entry per 3B + 2A) and either (a) approves, or (b) flags specific seam issues with a proposed patch direction (`re_prompt_prior` / `re_prompt_next` / `accept_with_observation`). Capped re-prompts per phase (counter increments on seam-reviewer-triggered re-prompts AND on deterministic-validator-triggered re-prompts; same cap). **Pattern B (single-call synthesis)** for `plan_refresh` T1/T2, `plan_refresh` T3 within a single phase, and `single_session_synthesize`: one synthesizer call with the tier-specific (or single-session) prompt; deterministic validator only (no LLM seam reviewer — no seams). Capped re-synthesis on validator failure. **Deterministic validator** common to both patterns: 2A volume-band check per week, ACWR forward-projection check across the scope window, rest-day-spacing check per discipline (no two consecutive hard sessions for the same discipline without explicit rationale), intensity-distribution check against the phase intent (Base ≈ 80/15/5 default; per-phase tunable). Validator failures trigger re-prompt at per-phase granularity (Pattern A) or whole-call granularity (Pattern B); persistent failure surfaces best-effort plan + `best_effort_plan` coaching observation.

## 6. Periodization decomposition + seam-review semantics — to be drafted in session 2

Layer-4-specific design decisions. (a) Phase boundary identification — given 3B `periodization_shape.mode + start_phase + phase_weeks` and `plan_start_date`, compute per-phase date windows (standard proportions when `mode` ∈ `{standard, compressed, extended}`; `phase_weeks` dict when `mode == 'custom'`). (b) Seam-reviewer authority — flag-only vs. propose-patch vs. force-re-prompt. Recommendation in §6 draft: propose-patch (reviewer outputs verdict + direction; synthesizer-layer code decides whether to act on the direction, with the per-phase retry cap as the budget bound). (c) Single-phase T3 special case — when T3 refresh scope is entirely inside one phase, falls through to Pattern B (single-call); when it spans a boundary, Pattern A activates with the affected phases re-synthesized + the seam between them reviewed; other phases in `prior_plan_session_window` are not re-synthesized. (d) Override path when 3B periodization shape is structurally infeasible — Layer 4 may produce `shape_override` in the payload with explicit rationale; surfaces to athlete via the diff view; per 3B §6.3 the override propagates back to the user-facing rationale alongside 3B's `reasoning_text`. (e) `start_phase != 'Base'` handling — when 3B sets `start_phase` to Build/Peak/Taper (skipping Base for an already-fit athlete), `phase_structure.phases` begins at that phase; seam reviewer still runs at subsequent boundaries.

## 8. Coaching flag rules — to be drafted in session 2

Auto-emit triggers for `notable_observations` + per-session `coaching_flags`. Required observations include `best_effort_plan` (validator hit cap), `shape_override` (Layer 4 overrode 3B), `intensity_modulated` (D-63 synthesizer modulated picked intensity per §6.2 of D-63), `sport_unavailable_at_locale` (D-63 §6.3 error case). Per-session `coaching_flags` like `race_rehearsal` (race-day fueling practice session), `fueling_practice` (2E target surfaced in session_notes), `weak_link_targeted` (strength session prescribes accessory work for a 3A `weak_links` entry), `first_introduction_to_<discipline>` (first session for a discipline newly in 2A inclusion).

**Taper-phase auto-emit rules** (to be detailed in session 2 — committed direction per Andy 2026-05-16 race-prep handling):

| Trigger | Auto-emitted on | Flag |
|---|---|---|
| Phase is Taper AND `days_to_event ≤ 14` AND session is a long session | One Taper session per week | `race_rehearsal` (full race-day fueling + pacing + kit practice) |
| Phase is Taper AND session is a long-or-moderate cardio session | All Taper cardio sessions ≥ 60min | `fueling_practice` (use race-day fueling tier from 2E) |
| `days_to_event == 7` | One Taper session (typically a light easy day) | `kit_check` (verify equipment per RaceWeekBrief.kit_manifest) |
| `days_to_event ∈ [3, 5]` AND session is a moderate-or-easy run/ride | One Taper session | `pacing_lock` (rehearse race-day pacing for ≥30 min at race target zone) |
| `days_to_event ≤ 2` AND session exists | All remaining Taper sessions | `pre_race_taper` (mobility, easy spinning, no novel stimulus) |

These flags apply on every Layer 4 invocation that touches Taper-phase sessions (`plan_create` covering Taper, `plan_refresh` T2/T3 that includes Taper days, `race_week_brief`). The `race_week_brief` entry point may modify already-existing Taper flags in `prior_plan_session_window` based on the brief's contents (e.g., kit_check date moves if the brief picks a different verification cadence).

## 9. Caching & determinism — to be drafted in session 2

Cache key per entry point. **Plan create:** `sha256(user_id || layer1_hash || all 5 layer2 hashes || layer3a_hash || layer3b_hash || plan_start_date || etl_version_set_json || model_synthesizer || model_seam_reviewer || str(temperature))`. **Plan refresh:** `sha256(user_id || tier || refresh_scope_start || refresh_scope_end || layer1_hash || layer2_bundle_hash || layer3a_hash || (layer3b_hash or '') || prior_plan_session_window_hash || (parsed_intent_hash or '') || etl_version_set_json || model_synthesizer || (model_seam_reviewer or '') || str(temperature))`. **Single session synthesize:** `sha256(user_id || request_canonical_json || layer1_hash || (layer2c_locale_hash or '') || layer2d_hash || layer3a_hash || etl_version_set_json || model || str(temperature))`. Per-phase cache for Pattern A so a partial re-prompt only re-synthesizes the affected phase + downstream phases that depend on its exit state. Invalidation triggers per Control_Spec §4 partial-update model. Note: `suggestion_id` is NOT in the single-session cache key — same (request, profile, state) should return the same session shape, and the orchestrator handles persisting to a new suggestion_id row.

## 10. Edge cases — to be drafted in session 2

Degenerate timelines (4-week event-mode plan with `start_phase == 'Taper'` → effectively single-phase Pattern A with empty `seam_reviews`); athlete with all rest days available per §K → emit `shape_infeasible` observation + raise `Layer4ShapeInfeasibleError`; D-63 single-session against a sport not present in any of the athlete's locales' effective equipment view → `sport_unavailable_at_locale` observation + error session per D-63 §6.3; refresh in mid-phase when the prior plan was Pattern-B-generated → `phase_metadata` reconstruction from 3B's current shape; refresh that crosses a `start_phase` boundary that 3B just shifted → Pattern A activates even for T2; `prior_plan_session_window` empty for a refresh → precondition failure (refresh requires prior plan); seam reviewer disagrees with itself across retries → cap on re-prompt budget bounds the loop; LLM synthesizer returns malformed structured output → schema-validation retry (1) then `Layer4OutputError('schema_violation')`.

## 11. Performance budget — to be drafted in session 2

Per-call-pattern targets. **Pattern A `plan_create` (4 phases + 3 seams + 1 deterministic-validator pass):** p50 ~25s, p95 ~60s end-to-end (per-phase ~5–8s × 4 sequential + ~3–5s × 3 seam reviews + ~100ms deterministic validator + small retry headroom). Andy 2026-05-16: accepted this latency as "plan-gen is being taken seriously." **Pattern B `plan_refresh` T1/T2:** p50 ~4s, p95 ~8s. **Pattern A `plan_refresh` T3 (cross-phase):** p50 ~12s (typically 2 phases + 1 seam), p95 ~25s. **Pattern B `plan_refresh` T3 (single-phase):** p50 ~6s, p95 ~10s. **`single_session_synthesize`:** p50 ~3s, p95 ~6s. Cost estimates at Sonnet 4.6 pricing: Pattern A `plan_create` ~$0.50–1.00 per invocation (sum across phases + seams + validator retries); Pattern B refresh T1/T2 ~$0.04–0.08; `single_session_synthesize` ~$0.02–0.04. Caching coverage assumption: refreshes hit ~30% cache (same (athlete, prior payloads) within day-granular `as_of`); plan_create is always a fresh run by definition.

## 12. Open items / forward references — to be drafted in session 2

- LLM seam-reviewer authority semantics (decision point flagged in §6 stub above).
- Per-phase synthesizer prompt body design (defer to its own session; stop-and-ask trigger #2 — this spec defines the contract).
- Per-tier T1/T2 synthesizer prompt body design (same defer).
- Single-session synthesizer prompt body design (same defer).
- Seam-reviewer prompt body design (same defer; smaller scope — reads two phase outputs + boundary state, emits verdict).
- Race-week-brief prompt body design (same defer; produces RaceWeekBrief + optional RacePlan).
- Plan-revert UX (per-day pointer flip; storage shape in §7.11 supports it; UI lands separately).
- **Layer 4.5 — Joint Session Coordinator** — its own spec, separate file. Andy 2026-05-16 picked the post-pass approach: each athlete gets a solo Layer 4 run; 4.5 reads two-or-more linked athletes' Layer 4 payloads + §L joint-session definitions and harmonizes the joint-session days (picks shared session shape, adjusts per-athlete intensity within fitness levels, resolves per-athlete equipment differences). Lands when team-features track activates. Layer 4 §2 + §7 schemas are joint-coordinator-ready (PlanSession has session_id + plan_version_id; 4.5 can supersede a solo `PlanSession` with a joint one via a new `joint_session_id` FK on `plan_session` rows — schema addition deferred to 4.5 spec).
- **Tiered tight/loose plan horizon** — Andy 2026-05-16: substantive direction change held. Currently spec'd as 'plan_create produces sessions for the full 3B periodization shape window at uniform quality'. Proposed future direction: `plan_create` produces tight ~12 weeks at Pattern A quality + loose weeks 13+ at degraded quality (smaller model? weekly-summary granularity? fewer inputs?); scheduled refresh ~1–2 weeks before tight horizon expires; T3 horizon becomes variable ("extend the tight window") rather than fixed 28 days. Un-defers D-57 (scheduled re-evaluation cadence). Substantial; revisit after Layer 4 v1 lands and we have measured cost/quality data on uniform-quality long-horizon plans.
- **Multi-day race plan post-race analytics** — `RacePlan.segments[*]` doesn't include athlete-checkin shape (actual vs. expected time/pace per segment). Once the race-execution surface is designed, add per-segment actuals. Out of v1.
- Layer 5 consumption — Layer 5 advisors (daily nutrition, supplements, clothing) consume `PlanSession.session_notes` + `cardio_blocks` for fuel timing; for race-week, Layer 5 reads `RaceWeekBrief.race_day_fueling_plan` + (multi-day) `RacePlan.fueling_strategy` for kit/conditions overlays. Contract details defer to Layer 5 spec.
- Validator's `intended_intensity_distribution` per-phase defaults — currently default to Base 80/15/5; need to pin Build/Peak/Taper defaults in §5 algorithm draft.
- Cost-cap interaction with D-64 frequency caps — if validator hits cap on a Pattern A plan, the cost of that one call exceeds expected; should the soft-cap warning factor expected vs. actual cost? Defer.
- `Layer4ShapeInfeasibleError` routing — does this surface as a 3D gate item for the next run, or as an inline athlete-facing error in the current run? Defer.
- Seam-reviewer model downgrade (Haiku for cheaper reviewing) — measure post-launch.
- `race_week_brief` trigger policy — orchestrator auto-fires when `days_to_event ≤ 14`, but exact firing cadence (daily? once at 14, again at 7, again at 1?) needs explicit policy. Currently flagged as "single fire at 14 + athlete-triggerable re-runs"; tune post-launch.

## 13. Test scenarios — to be drafted in session 2

Full coverage across all three entry points × periodization shapes × tier × validator pass/fail paths. Indicative scenarios: (a) Andy's actual case — Pocket Gopher Extreme, 9 weeks out, 15 disciplines, Pattern A `plan_create` with `start_phase='Build'` (3A says aerobic 'good' / strength 'moderate' → 3B picks `compressed` + `start_phase='Build'`); (b) Same athlete, T1 refresh "I'm tired" → Pattern B, single 3A re-eval, plan covers next 2 days only; (c) Same athlete, T3 refresh crossing Build→Peak boundary → Pattern A on the 2 affected phases; (d) D-63 single-session request for MTB at home gym (no bike) → `sport_unavailable_at_locale` observation + error session; (e) D-63 single-session for strength at hotel gym with wrist injury → no wrist-loaded exercises in output; (f) Validator-cap hit on Build phase due to athlete's §K leaving only 3 days/week available → best-effort plan + `best_effort_plan` observation + Build's `synthesis_metadata.cap_hit == True`; (g) Pattern A with `start_phase='Taper'` and `time_to_event_weeks == 1` → degenerate single-phase, `seam_reviews == []`, fast path.

## 14. Gut check — to be drafted in session 2

End-of-spec retrospective per the 14-section template. Topics expected to land: what this spec gets right (the discriminated-union session shape collapses 3 downstream consumer paths into 1; the per-phase + seam-reviewer architecture matches the coaching intuition that seams are where periodization actually goes wrong; three entry points keep the expensive Pattern A out of the cheap-call paths); risks (per-phase decomposition may exhibit the same dependency-on-prior-phase coupling that makes parallelism impossible; the seam reviewer's verdict authority is the single most likely place to over-spec or under-spec; cost is real and unmeasured; intensity-distribution defaults across phases are policy not data); what might be missing (joint sessions, Layer 5 consumption contract, the prompt bodies themselves); best argument against this spec's scope (the three-entry-point shape is a complexity multiplier; a unified entry point with a `mode` discriminator would be simpler if the per-mode prompts can be parameterized; counter — Andy explicitly picked separate functions per Decision 2, and the prompts ARE the per-mode complexity that separation makes inspectable).

---

*End of Layer 4 spec draft v1 (session 1 of expected 3–5). Sections drafted: §1 Purpose, §2 What 4 does NOT do, §3 Function signature (3 entry points), §7 Payload schema. Sections §§4–6 + §§8–14 stubbed with brief targets so the next session has a clear scope. Next session: §§4–6 (input validation, algorithm including Pattern A per-phase + LLM seam reviewer details, periodization decomposition + seam-review semantics including the seam-reviewer authority decision).*
