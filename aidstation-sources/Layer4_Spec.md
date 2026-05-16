# Layer 4 — Plan Generation (LLM Synthesis + LLM Seam Review)

**Status:** Draft v1, 2026-05-16. Session 4 of an expected 3–5 sessions to land the full 14-section spec. Session 1 covered §§1–3 + §7 Payload schema (including `RaceWeekBrief` + `RacePlan`). Session 2 added §§4–6 + Decision 8 (seam-reviewer authority = β propose-patch). Session 3 covered §§8–9 (coaching flag rules + caching/determinism). **Session 4 (this update) covers §10 Edge cases, §11 Performance budget, and §13 Test scenarios** — including concrete detection algorithms for the four `Layer4ShapeInfeasibleError` classes that the session-3 calibration round-2 flagged forward. §§12 + §14 + end-of-arc CLAUDE.md/backlog bump land in session 5. No new source decisions this session — §§10/11/13 are mechanical fleshing-out of session-1/2/3 contracts.

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
- **Decision 8 (seam-reviewer authority — propose-patch / β):** Andy 2026-05-16 (session 2): the LLM seam reviewer carries propose-patch authority. On a `flagged_major`/`patched` verdict with a `re_prompt_*` direction, the orchestrator re-prompts the targeted phase with the reviewer's `seam_issues` merged into context as constraint statements, subject to the per-phase retry cap. Rejected alternatives: flag-only (loses reviewer value when seams are real); force-re-prompt (risks unbounded retry chains). Mixed verdict-tier authority was offered but Andy picked clean β rather than the multi-tier blend. See §6.2 for the full authority semantics + bounds.

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
        'seam_unresolved',               # §6.2 — per-seam iteration cap exhausted or seam patch blocked by retry budget
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

## 4. Input validation (preconditions)

All four entry points validate inputs before any LLM call. Failures raise `Layer4InputError(code)`; orchestrator catches and routes per code (see §3.5). Validation is fail-fast — the first failing rule raises; no error accumulation across rules. Implementation lives in `_validate_<entry_point>_inputs()` helpers per entry point, with a shared `_validate_cross_entry_invariants()` helper for §4.1.

### 4.1 Cross-entry rules

Apply to every entry point before per-entry rules run.

| Rule | Code | Detail |
|---|---|---|
| Single user scope | `mixed_user_scope` | Every payload's `user_id` matches the call-site `user_id`. Implementation-level guard against accidental cross-account contamination. |
| Consistent `etl_version_set` | `etl_version_set_mismatch` | All upstream payloads were generated under the same `etl_version_set` (one canonical dict; mismatch raises). Orchestrator must re-run prerequisite layers before invoking Layer 4 if versions drift mid-pipeline. |
| Non-stale payloads | `stale_input_payload` | Each upstream payload's `created_at` is after the most-recent invalidation event for its (user, layer) pair per Control_Spec §4 partial-update model. Implementation calls `is_payload_stale()` per payload. |
| Locale resolution | `locale_unresolved` | Every locale_id referenced in 2C bundle (and in `prior_plan_session_window` when present) resolves to a `locale_profiles` row scoped to the call-site user. |
| Active injuries surfaced | `active_injury_data_gap` | `layer3a_payload.current_state.active_injuries` is a list (possibly empty); if non-empty, every entry has `body_part` + `severity` + `restriction_text` populated. Layer 4 reads these to compute the §5.4 injury-exclusion validator rule; missing fields would silently bypass exclusion. |

### 4.2 `llm_layer4_plan_create`

| Rule | Code | Detail |
|---|---|---|
| All upstream payloads non-None | `missing_upstream_payload` | `layer1_payload`, `layer2a_payload` through `layer2e_payload` (all 5), `layer3a_payload`, `layer3b_payload` each non-None. |
| `plan_start_date` not in past | `plan_start_date_in_past` | `plan_start_date ≥ today` (orchestrator-supplied date; backdating not supported in v1). |
| `plan_version_id` allocated | `plan_version_id_unset` | Caller pre-allocated a `plan_versions` row with `created_via='plan_create'`; row exists. |
| 3B periodization shape valid | `periodization_shape_invalid` | `mode ∈ {'standard', 'compressed', 'extended', 'custom'}`; when `mode == 'custom'`, `phase_weeks` is a non-empty dict whose keys are a subset of `{Base, Build, Peak, Taper}` with positive integer values. |
| 3B `start_phase` valid | `start_phase_invalid` | `start_phase ∈ {'Base', 'Build', 'Peak', 'Taper'}`. |
| 3B `time_to_event_weeks` consistent | `time_to_event_weeks_mismatch` | When 3B `mode == 'event'`: `time_to_event_weeks > 0` and matches (within ±1 wk) the gap between `plan_start_date` and `event_date`. |
| 3A state enum-valid | `layer3a_state_missing` | `layer3a_payload.current_state.aerobic_state` + `strength_state` are enum-valid. |
| 2A discipline weights consistent | `discipline_weights_invalid` | 2A `discipline_weights` sum to ≈1.0 (±0.05 rounding tolerance); every weighted discipline appears in `phase_load_bands`. |

### 4.3 `llm_layer4_plan_refresh`

| Rule | Code | Detail |
|---|---|---|
| All upstream payloads non-None | `missing_upstream_payload` | Same set as plan_create. `layer3b_payload` required even on T1/T2 — Pattern B's validator still reads phase intent for the intensity-distribution check. |
| `tier ∈ enum` | `tier_invalid` | `tier ∈ {'T1', 'T2', 'T3'}`. |
| `refresh_scope_*` ordered | `refresh_scope_inverted` | `refresh_scope_start ≤ refresh_scope_end`. |
| Tier matches scope length | `tier_scope_mismatch` | `T1`: scope ≤ 3 days; `T2`: scope ≤ 9 days; `T3`: scope ≤ 32 days. Tolerances absorb day-of-week + leap edges. |
| `prior_plan_session_window` non-empty | `prior_plan_window_empty` | Refresh requires a prior plan covering the scope window (else orchestrator should route to `plan_create`). |
| `plan_version_id_parent` exists | `plan_version_id_parent_missing` | FK check against `plan_versions`; the refresh writes a child version that supersedes parts of the parent via per-day pointer flips per §7.11. |
| `parsed_intent` schema-valid | `parsed_intent_schema_invalid` | When non-None, conforms to D-64 §3 schema (mode, scope_directive, modifications list). |
| `prior_plan_session_window` sessions resolve | `prior_session_orphaned` | Every session's `plan_version_id` exists; every `locale_id` resolves; every `discipline_id` is in current 2A `discipline_inclusion` (or has been retired with an `intensity_modulated` / `shape_override` rationale on the producing plan — that branch is allowed). |

### 4.4 `llm_layer4_single_session_synthesize`

| Rule | Code | Detail |
|---|---|---|
| Upstream payloads non-None | `missing_upstream_payload` | `layer1_payload`, `layer2a_payload`, `layer2d_payload`, `layer3a_payload` non-None. `layer3b_payload` optional — D-63 doesn't require periodization context. |
| Duration in range | `duration_out_of_range` | `30 ≤ request.duration_min ≤ 360`. |
| Intensity enum-valid | `intensity_invalid` | `request.intensity ∈ {'easy', 'moderate', 'hard'}`. |
| Locale XOR quick_equipment | `locale_and_quick_equipment_both_set` / `locale_and_quick_equipment_both_unset` | Exactly one of `request.locale_slug` and `request.quick_equipment` is populated. |
| 2C payload for picked locale present | `layer2c_payload_for_locale_missing` | When `request.locale_slug` non-None, `layer2c_payload_for_locale` non-None and its `locale_slug` matches the request. |
| Sport in 2A inclusion | `sport_not_in_inclusion` | `request.sport ∈ layer2a_payload.discipline_inclusion`. |
| Athlete owns the locale | `locale_not_athlete_scoped` | When `request.locale_slug` specified, the locale's `user_id` matches the call-site user. |

### 4.5 `llm_layer4_race_week_brief`

| Rule | Code | Detail |
|---|---|---|
| Event mode required | `race_week_brief_requires_event_mode` | `layer3b_payload.mode == 'event'`. Non-event-mode plans have no target race; brief is nonsensical. (Already declared in §3.4.) |
| Event within window | `race_week_brief_too_early` | `days_to_event ≤ 14`. Orchestrator should not auto-fire outside this window; athlete-manual fires outside the window raise. |
| Event date in future | `event_date_in_past` | `event_date > today`. Post-race briefs are not in scope. |
| 2E payload required | `layer2e_payload_missing` | 2E race-day fueling tier is mandatory for `RaceWeekBrief.race_day_fueling_plan` + `RacePlan.fueling_strategy`. |
| Event locale resolves | `event_locale_unresolved` | `layer3b_payload.event_locale` resolves to a `locale_profiles` row (athlete-scoped or platform-scoped). |
| `race_format` set | `race_format_unset` | `layer3b_payload.race_format ∈ {'single_day', 'expedition_ar', 'stage_race', 'multi_day_ultra'}`. |
| Kit data prerequisites (soft) | `kit_manifest_inputs_incomplete` | When `race_format != 'single_day'`: at least one locale (event_locale or any locale in the route) has `equipment_overrides` populated. **Soft warning** — does not raise; emits a `data_gap` notable_observation; kit_manifest synthesis degrades gracefully with free-text items. |

## 5. Algorithm

Three execution paths. Routing per `(mode, tier, scope)` is deterministic (§5.1). Per-pattern flow lives in §5.2 (Pattern A) and §5.3 (Pattern B). The deterministic validator wrapping both is in §5.4. The shared capped-retry mechanic is in §5.5.

### 5.1 Pattern routing

| Entry point | Tier / scope | Pattern |
|---|---|---|
| `plan_create` | — | A |
| `plan_refresh` | T1 | B |
| `plan_refresh` | T2 | B |
| `plan_refresh` | T3, scope inside a single phase | B |
| `plan_refresh` | T3, scope spans a phase boundary | A |
| `single_session_synthesize` | — | B |
| `race_week_brief` | single-day event | B |
| `race_week_brief` | multi-day event | B |

Pattern A is effectively `N × Pattern B` calls + seam reviews + a final cross-phase validator pass; the distinguishing feature is per-phase decomposition with LLM seam review between adjacent phases.

`race_week_brief` is Pattern B in v1 even for multi-day events: the brief covers the Taper window only (≤ 14 days = ≤ 1 phase). Pattern A's per-phase machinery is unnecessary for a single phase.

### 5.2 Pattern A — per-phase synthesis + LLM seam review

Used by `plan_create` and by `plan_refresh` T3 with cross-phase scope.

**Algorithm:**

1. **Compute phase structure.** Call `phase_structure_from_3b(layer3b_payload, plan_start_date)` (§6.1). Output: ordered list of `PhaseSpec` starting from 3B `start_phase`. Phases earlier than `start_phase` are not in the list.
2. **Determine phases to synthesize.**
   - `plan_create`: every phase in `phase_structure.phases`.
   - `plan_refresh` T3 cross-phase: the subset whose date window overlaps `[refresh_scope_start, refresh_scope_end]`. Phases outside the scope keep their prior-plan sessions and serve as boundary context.
3. **Per-phase synthesis loop, sequential, in order.** For each phase `p` to synthesize:
   1. Build context: 3A + 3B + all five 2x payloads + 1 + prior phase's accepted output (when `p` is not the first synthesized phase) + intended exit state of the prior phase + intended entry state of `p` (volume + intensity per `PhaseSpec.intended_*`) + any seam-driven `seam_issues` constraint deltas merged in (§6.2 propose-patch path).
   2. Call synthesizer LLM (`model_synthesizer`, `temperature`) with the per-phase prompt. (Prompt body deferred per stop-and-ask trigger #2.)
   3. Parse structured output into `list[PlanSession]` for `p` + per-phase `synthesis_metadata`.
   4. Run deterministic validator (§5.4) scoped to phase `p`.
   5. If validator fails: capped retry per §5.5 within `p`. Each retry re-prompts with the prior pass's `RuleFailure` list merged into context as constraint statements.
   6. On accepted (or cap-hit best-effort): append `p`'s sessions to the cumulative plan; record `PhaseSpec.synthesis_metadata` with `retries_used` + `cap_hit`.
4. **Seam review loop, after per-phase synthesis completes.** For each adjacent phase pair `(p_i, p_{i+1})` in `phases_synthesized`:
   1. Call LLM seam reviewer (`model_seam_reviewer`, lower `temperature`) with: both phase outputs + intended boundary state (`p_i` exit volume/intensity per 2A `phase_load_bands`; `p_{i+1}` intended entry).
   2. Reviewer emits a `SeamReview` row per §7.7: `reviewer_verdict ∈ {approved, flagged_minor, flagged_major, patched}`; on `flagged_major`/`patched`, emits `seam_issues` (free-text constraint statements) + `proposed_patch_direction ∈ {re_prompt_prior, re_prompt_next, accept_with_observation}`.
   3. Apply per §6.2 authority semantics (β propose-patch). Summary: `approved` / `flagged_minor` are record-only; `flagged_major` / `patched` with a `re_prompt_*` direction trigger one re-synthesis of the targeted phase iff that phase's retry budget per §5.5 is not exhausted.
   4. After a patch is applied: re-run §5.4 validator on the re-synthesized phase, then re-run THIS seam review exactly once. Per-seam total iterations capped at 2 (initial + 1 patched-re-review). If the second iteration still flags: accept the patched version + emit a `seam_unresolved` notable_observation (severity `warning`).
5. **Final validator pass** over the union of all sessions across all synthesized phases + carried-over prior-plan sessions for non-synthesized phases. Catches cross-phase rules (ACWR forward projection across the full scope window). Failures here cannot be retried by re-prompting individual phases (the rule failures may span phases); they surface as `RuleFailure` rows; any `blocker`-severity cross-phase failure elevates to a `best_effort_plan` notable_observation.
6. **Compose `Layer4Payload`** with `pattern='A'`, `phase_structure` populated, `seam_reviews` populated (one entry per adjacent pair reviewed; empty list when only one phase was synthesized), `validator_results` non-empty (last entry has `accepted=True`), `notable_observations` populated, `sessions` populated.

**Concurrency.** Per-phase synthesis is sequential by design — each phase consumes the prior phase's exit state. Seam reviews COULD parallelize across non-overlapping pairs (with N synthesized phases, seams `0..N-2` are independent in their LLM-call inputs). v1 implementation is sequential for simplicity; parallelism is a §11 performance-budget optimization to revisit post-launch.

**Latency expectation.** N synthesized phases × per-phase LLM ~5–8s + (N-1) seam reviews × ~3–5s + deterministic validator (~100ms) + retry headroom. For Andy's `plan_create` case (4 phases, 3 seams): p50 ~25s, p95 ~60s. Per Andy 2026-05-16: accepted ("plan-gen is being taken seriously").

### 5.3 Pattern B — single-call synthesis + deterministic validator

Used by `plan_refresh` T1/T2, `plan_refresh` T3 intra-phase, `single_session_synthesize`, `race_week_brief`.

**Algorithm:**

1. **Build context per entry point.** Mode/tier-specific prompt body + relevant payloads:
   - `plan_refresh` T1: 3A + 2A/2D + 1 + `prior_plan_session_window` + `parsed_intent` (when present).
   - `plan_refresh` T2: above + 2B/2C/2E.
   - `plan_refresh` T3 intra-phase: above + 3B current periodization shape (read but not decomposed).
   - `single_session_synthesize`: 3A + 2A/2D + 1 + `request` payload + `layer2c_payload_for_locale` (when locale-specified).
   - `race_week_brief`: 3A + 3B + all five 2x payloads + 1 + Taper-phase sessions from `prior_plan_session_window` + event metadata (`event_date`, `event_locale`, `race_format`).
2. **Single LLM call** (`model_synthesizer`, `temperature`) with the mode-specific prompt.
3. **Parse structured output.** Shape varies by mode:
   - Refresh: `list[PlanSession]` covering `[refresh_scope_start, refresh_scope_end]`.
   - Single-session: exactly one `PlanSession` with `is_ad_hoc=True`.
   - Race-week-brief: modified Taper-phase sessions (PlanSession overrides) + `RaceWeekBrief` + (multi-day only) `RacePlan`.
4. **Deterministic validator** (§5.4) on the output. Scope varies:
   - Refresh: validate the refreshed sessions against the intended phase intent (validator reads 3B periodization shape even on Pattern B); cross-validate continuity with non-refreshed prior-plan sessions adjacent to the scope window.
   - Single-session: minimal validation — duration, intensity, locale equipment availability, injury exclusions; no weekly-volume or ACWR checks (one ad-hoc session doesn't carry periodization context).
   - Race-week-brief: validate Taper-session overrides against Taper phase intent; validate `RaceWeekBrief.kit_manifest` items exist in layer0 equipment registry (or are flagged free-text); validate `RacePlan.segments` chronological ordering when multi-day; validate fueling-strategy macro ranges against 2E tier.
5. **Capped retry** per §5.5 on validator failure. Re-prompt with `RuleFailure` context merged in.
6. **Compose `Layer4Payload`** with `pattern='B'`, `phase_structure=None`, `seam_reviews=None`, mode-specific fields populated (`suggestion_id` for single-session; `race_week_brief` + `race_plan` for race-week-brief).

**Latency expectation.** T1/T2 ~4–8s; T3 intra-phase ~6–10s; single-session ~3–6s; race-week-brief ~8–15s (larger output budget, more context).

### 5.4 Deterministic validator

Pure-function rule set; no LLM. Runs after every synthesis call in both patterns; runs once more as a final pass over the cumulative plan in Pattern A step 5.

**Rule set:**

| Rule | Code prefix | Scope | Detail |
|---|---|---|---|
| Weekly volume in 2A band | `volume_band_*` | (week, discipline, phase) | Per-(week, discipline) total volume (hours or km per 2A measure) inside `phase_load_bands[discipline][phase].(low, high)`. Severity: `blocker` if outside ±15%; `warning` if outside ±5%. |
| ACWR forward projection | `acwr_*` | Cross-window | Acute-to-chronic workload ratio projected across the scope window stays inside 0.8–1.3 (per-phase tunable; Base/Build tighter, Peak slightly wider, Taper anchored low). `blocker` outside 0.7–1.4; `warning` outside 0.8–1.3. |
| Rest-day spacing | `rest_spacing_*` | Per discipline per (date, date+1) | No two consecutive hard sessions for the same discipline without `coaching_flags` containing an explicit rationale (`overreach_test`, `race_rehearsal`). |
| Intensity distribution match | `intensity_dist_*` | Per phase | Per-phase total hours by zone vs. intended distribution. **v1 defaults** (per-phase tunable; flagged in §12): Base ≈ 80/15/5 (Z1-Z2/Z3/Z4-Z5); Build ≈ 70/20/10; Peak ≈ 70/20/10; Taper ≈ 75/15/10. Tolerance ±10pp per zone. Peak shares Build's zone distribution (per Andy 2026-05-16 session-3 calibration: pyramidal-polarized stays flat through Peak for the endurance / ultra / AR / multi-sport disciplines this spec serves; race-pace work in Peak surfaces via the `race_pace_specific` per-session flag per §8.4 rather than via a zone-distribution shift). Differentiation between Build and Peak is via volume shape (Peak typically holds higher absolute volume, with the highest-volume week tagged `peak_volume_marker` per §8.4) + race-specific intensity placement (LLM-emitted `race_pace_specific`), not zone-distribution. |
| Two-sessions-per-day rules | `two_per_day_*` | Per date | Per §7.12: max 2 sessions per date; no strength+strength same day; no two `intensity_summary=='hard'` same day; at least one of two must be `kind=='cardio'`. |
| Equipment availability | `equipment_unavailable_*` | Per session | Every prescribed exercise / cardio sport-equipment requirement resolves in the picked locale's effective equipment view (per 2C resolution tiers). Tier-3 proxy substitution is allowed; raw unavailable is a blocker. |
| Injury exclusion | `injury_violation_*` | Per session | No exercise hits a body part in 3A `active_injuries` with `restriction_text` indicating exclusion. Wrist-extension-loaded check is the v1 motivating example. |
| Schedule availability | `schedule_violation_*` | Per date | Sessions per date fit §K available-days + per-day window count; sessions for a date with `available=False` raise unless explicitly flagged `athlete_self_scheduled` (D-63 path). |
| Discipline inclusion | `discipline_excluded_*` | Per session | `discipline_id` is in 2A `discipline_inclusion`. Catches stale prior-plan sessions referencing a retired discipline. |
| Sport-locale compatibility | `sport_locale_incompatible_*` | Per session | `discipline_id` is supported at `locale_id` per 2C equipment view (e.g., no MTB session at a hotel gym locale). |

Each failed rule emits a `RuleFailure` per §7.9 with `rule_name`, `phase_name` (when phase-scoped), `severity`, `detail`, `affected_session_ids`.

**Output:** `ValidatorResult` per §7.9 — `pass_index`, `accepted: bool`, `rule_failures` (empty when accepted), `retried_phase_names` (empty when accepted or when called from Pattern B).

**Tolerance defaults are v1; tune post-launch.** The ±15%/±5% volume thresholds and the ±10pp intensity-distribution tolerance are evidence-grounded starting points; measured retry rates in production should drive a follow-up tuning session.

### 5.5 Capped retry semantics

Shared budget across both patterns.

- **Per-phase cap** (`capped_retries_per_phase`, default 2). Pattern A: applies per phase across BOTH validator-driven retries AND seam-reviewer-driven re-syntheses. Pattern B: applies to the whole single call (the call has only one "phase" conceptually).
- **Counter increments on every re-synthesis** triggered by either validator failure or seam-reviewer patch direction. Once `retries_used >= cap`, no further re-synthesis on that phase; the latest output is accepted as best-effort.
- **Best-effort acceptance.** When cap is hit: latest synthesis is accepted; `PhaseSpec.synthesis_metadata.cap_hit=True`; an `Observation(category='best_effort_plan')` is added to `notable_observations`; outstanding `RuleFailure` rows in the cap-hit pass are demoted to `severity='warning'` (visible in the diff view but do not block plan write).
- **Cross-phase rule failures** (e.g., cumulative ACWR) cannot be retried — they surface in the final-pass `validator_result` only; severity stays as-emitted; persistent `blocker`-severity cross-phase failures elevate to a `best_effort_plan` observation.
- **Schema-violation special case.** When the synthesizer returns malformed structured output (per output parser): one schema-validation retry (counter does NOT consume the per-phase budget — schema retries are separate); on second failure, raise `Layer4OutputError('schema_violation')` and bail out of the call.
- **Latency tax.** Each retry adds one synthesizer-call latency (~5–8s Pattern A per-phase; ~4–6s Pattern B); cap of 2 retries adds at most ~16s worst case per phase. Surfaces in `latency_ms_total`.

## 6. Periodization decomposition + seam-review semantics

Layer-4-specific design decisions that don't live in §5's algorithm flow.

### 6.1 Phase boundary computation

Pure-function helper `phase_structure_from_3b(layer3b_payload, plan_start_date) -> PhaseStructure`.

**Inputs read:**
- `layer3b_payload.periodization_shape.mode`
- `layer3b_payload.periodization_shape.start_phase`
- `layer3b_payload.periodization_shape.phase_weeks` (when `mode == 'custom'`)
- `layer3b_payload.time_to_event_weeks` (when event mode)
- `layer3b_payload.mode` (event vs. open-ended)
- `plan_start_date` (orchestrator-supplied)

**Total horizon resolution.** Event mode: `total_weeks = layer3b_payload.time_to_event_weeks`. Open-ended mode: v1 defaults to 12 weeks (one mesocycle) rolling forward (per Andy 2026-05-16 session-3 calibration). Extension is via T3 refresh as the 12-week horizon approaches its end — orchestrator-triggered scheduled re-eval is D-57 (currently deferred); athlete-initiated T3 is supported on the existing refresh path per §3.2. The broader tiered tight/loose horizon question (D7 HELD per header) is unaffected; this is just the v1 fixed-horizon length.

**Per-mode proportions** (applied to `total_weeks` for the phases that the athlete still needs to traverse from `start_phase` onward):

| Mode | Base | Build | Peak | Taper |
|---|---|---|---|---|
| `standard` | 50% | 30% | 15% | 5% |
| `compressed` | 30% | 35% | 25% | 10% |
| `extended` | 60% | 25% | 10% | 5% |
| `custom` | per `phase_weeks` dict (verbatim) | | | |

Proportions round to whole weeks with the remainder allocated to Base (most flexible phase). When `start_phase != 'Base'`, the skipped earlier phases' percentages are simply dropped — the remaining phases keep their relative proportions and re-normalize to fit `total_weeks`.

**Taper duration — synthesizer-picked within proportion budget.** Per Andy 2026-05-16 session-3 calibration: the hard 1–4 week Taper bounds are removed. Taper length is duration-based coaching judgment (race format + §H.2 `estimated_duration_hr` are the primary drivers; not discipline alone). The §6.1 mode proportions allocate a Taper budget; the synthesizer prompt picks the actual Taper length within that budget informed by race context. v1 prompt guidance to surface (informational, not enforced): typical 1–2 weeks for sub-marathon events; 2–3 weeks for marathon / half-IM class; 3+ weeks for expedition AR + multi-day ultras + full-IM class. The synthesizer can compress or extend within the mode proportion when athlete state or race format warrants. Prompt body design deferred per stop-and-ask trigger #2; this paragraph is the spec contract for the prompt to honor.

**`start_phase` handling.** When `start_phase != 'Base'`, earlier phases are excluded from `phase_structure.phases` (athlete is already past them); `phase_structure.phases[0].start_date = plan_start_date`; subsequent phases follow the proportional weeks. The synthesizer prompt for the starting phase receives an "athlete is starting at `<phase>`; prior phases assumed to have established `<intended exit state per 2A>`" context block — prompt body design deferred per stop-and-ask trigger #2.

**Output:** `PhaseStructure` per §7.6 with `phases: list[PhaseSpec]` ordered Base → Build → Peak → Taper (subset starting from `start_phase`); each `PhaseSpec` has `start_date`, `end_date`, `weeks`, `intended_volume_band` (from 2A `phase_load_bands`), `intended_intensity_distribution` (per §5.4 v1 defaults; tunable per future cleanup).

**`derived_from` provenance** tracks the shape source for downstream rationale rendering: `'3b_standard' | '3b_compressed' | '3b_extended' | '3b_custom' | 'layer4_override'`.

### 6.2 Seam-reviewer authority — propose-patch (β)

Per Andy 2026-05-16 (Decision 8 — recorded in header): the seam reviewer carries **propose-patch authority**. Verdicts of `flagged_major` or `patched` with a `re_prompt_*` direction cause the orchestrator to re-prompt the targeted phase with the reviewer's `seam_issues` merged into context as constraint statements. Flag-only and force-re-prompt were considered and rejected (flag-only loses reviewer value when seams are real; force-re-prompt risks unbounded retry chains).

**Reviewer output recap (per §7.7):**

- `reviewer_verdict: Literal['approved', 'flagged_minor', 'flagged_major', 'patched']`
- `seam_issues: list[str]` — free-text constraint statements, one per identified seam problem (e.g., "Build week 4 ends at ~9 hr/wk Z2 volume; Peak week 1 starts at ~6 hr/wk Z3 — volume cliff and intensity jump on the same boundary; recommend Peak week 1 hold Z2 dominance with one Z3 introduction session"). Empty list on `approved`.
- `proposed_patch_direction: Literal['re_prompt_prior', 're_prompt_next', 'accept_with_observation'] | None` — None on `approved` / `flagged_minor`; populated on `flagged_major` / `patched`.

**Orchestrator authority semantics:**

| Verdict | Direction | Action |
|---|---|---|
| `approved` | None | Record SeamReview; no observation; continue. |
| `flagged_minor` | None | Record SeamReview; emit `Observation(category='warning', text=<seam_issues summary>, elevates_to_hitl=False)`; continue (no retry). |
| `flagged_major` | `re_prompt_prior` / `re_prompt_next` | If targeted phase's `retries_used < cap`: re-synthesize that phase with `seam_issues` merged into context as constraint deltas; increment counter; re-validate; re-run THIS seam review once. If cap exhausted: accept current synthesis + emit `seam_unresolved` observation; `triggered_resynthesis=False`. |
| `flagged_major` | `accept_with_observation` | Record SeamReview; emit `Observation(category='warning')` with `elevates_to_hitl=True` (the seam is notably bad but the reviewer judges re-synthesis won't help — escalate to next-run HITL gate). |
| `patched` | `re_prompt_prior` / `re_prompt_next` | Same as `flagged_major` + `re_prompt_*`. The verdict-name distinction is informational — `patched` signals reviewer confidence that the patch direction will resolve; `flagged_major` signals reviewer is offering the patch but is less certain. |
| `patched` | `accept_with_observation` | Not a valid combination — a `patched` verdict implies the reviewer is proposing a re-prompt. The output parser raises `Layer4OutputError('seam_reviewer_invalid_verdict_combination')`; orchestrator treats as schema-violation per §5.5 (one schema retry; bail on second failure). |

**Per-seam iteration cap.** Each adjacent-phase seam is reviewed at most twice: initial review + at most one patched-re-review. If the second review still emits a `flagged_*` or `patched` verdict, accept the latest synthesis + emit a `seam_unresolved` notable_observation. This bounds total Pattern A latency.

**Seam-driven retry interaction with validator-driven retry.** Both share the per-phase retry counter (`capped_retries_per_phase`, default 2). A phase that consumed 2 retries to pass its deterministic validator has zero remaining budget for seam-driven re-prompts; the seam reviewer's patch direction is recorded but not applied; `seam_unresolved` observation emitted.

**Authority bounds — what the reviewer CANNOT do:**

- Cannot request changes to phases more than one hop from the seam (reviewer reads only the two adjacent phases; cannot mutate distant phases).
- Cannot force re-synthesis of a phase whose retry budget is exhausted.
- Cannot insert or delete phases (`phase_structure` is fixed by §6.1 at the start of the call).
- Cannot change `mode` or `start_phase` (those routes via `shape_override` per §6.4 only).
- Cannot directly modify individual sessions outside the targeted phase's re-synthesis (the synthesizer LLM, not the reviewer, produces session content).

### 6.3 Single-phase T3 special case

When `plan_refresh` T3's `[refresh_scope_start, refresh_scope_end]` falls entirely within a single phase (no boundary crossing): routes to Pattern B per §5.1 — no seams to review means no Pattern A point. Validator-only.

When the scope spans a phase boundary: Pattern A activates on the affected phases only. Concrete behavior:

- Phases overlapping the scope window are re-synthesized.
- Phases outside the scope window keep their prior-plan sessions (read from `prior_plan_session_window`).
- Seam reviews run on adjacent-phase pairs WHERE AT LEAST ONE PHASE WAS RE-SYNTHESIZED. For a seam between an unaffected phase and a re-synthesized one: the unaffected phase's prior output serves as the boundary state (not re-synthesized); the seam reviewer evaluates whether the newly-synthesized phase fits cleanly against the prior context.
- Seams between two unaffected phases are NOT re-reviewed (they were reviewed during the original `plan_create`).

Minimizes per-refresh latency: a typical T3 cross-phase refresh hits 2 affected phases + 1 seam ≈ ~12s p50 vs. plan_create's ~25s p50.

### 6.4 `shape_override` path

When 3B's periodization shape is structurally infeasible given 3A current state — narrow rule set (four v1 triggers; revisit only if production cases surface a fifth):

| Trigger | Override | Rationale |
|---|---|---|
| 3B `mode == 'standard'` + `time_to_event_weeks < 8` | `mode = 'compressed'` | Standard proportions require ≥8 weeks for meaningful Base; below that, Build dominance is mandatory. |
| 3B `mode == 'compressed'` + `time_to_event_weeks < 4` | `mode = 'extended'`, `start_phase = 'Peak'` | Sub-4-week compressed is nonsense; Peak-only with synthesizer-picked Taper (~1 week per v1 prompt guidance per §6.1) is the only viable shape. |
| 3B `start_phase == 'Base'` + 3A `aerobic_state ∈ {'high', 'very_high'}` + `time_to_event_weeks < 12` | `start_phase = 'Build'` (keep `mode`) | Athlete is already aerobically prepared; Base would waste weeks. |
| 3A `data_density == 'very_sparse'` + 3B `start_phase != 'Base'` | `start_phase = 'Base'` (keep `mode`) | Starting at Build/Peak without baseline training-load data is unsafe — ramp-rate prescription depends on knowing current capacity. Coaching practice: always re-establish Base when data is missing. Per Andy 2026-05-16 session-3 calibration. |

**Constraints on override:**

- Only fires at `plan_create` time (not refresh — overriding mid-plan would re-shuffle phase boundaries, breaking the per-day version-pointer revert UX).
- Override produces `ShapeOverride` per §7.8 + `Observation(category='shape_override', elevates_to_hitl=True)`.
- The override propagates to athlete-facing rationale via 3B `reasoning_text` + `ShapeOverride.rationale_text` (per 3B §6.3 contract).
- Beyond the rule-set above, no override: Layer 4 synthesizes against the 3B-given shape even when suboptimal. Override is for structural infeasibility only, not preference.

**Infeasibility cases that do NOT shape_override — escalate via `Layer4ShapeInfeasibleError`:**

Per Andy 2026-05-16 session-3 calibration: the following infeasibility classes do NOT auto-shape-override. The athlete is making a real choice (more days, drop a discipline, more weeks) that Layer 4 should not silently rearrange. These escalate via `Layer4ShapeInfeasibleError(...)` per §3.5 and surface either to the next 3D gate or as an inline athlete-facing error per orchestrator routing (concrete routing tracked in §12; §10 in session 4 enumerates detection algorithms).

| Class | Detection (informal; pin in §10) | Why not auto-fix |
|---|---|---|
| Schedule-volume infeasibility | §K available-windows total time < 2A `phase_load_bands.low` for the upcoming phase | Athlete needs more available days or longer plan; not Layer 4's call. |
| Discipline-frequency infeasibility | N disciplines × min-frequency-per-discipline > §K available days/week | Drop a discipline (2A re-eval) or merge as cross-training; not Layer 4's call. |
| Skill-acquisition infeasibility | Skill-heavy discipline newly in 2A inclusion + insufficient Base weeks for skill consolidation (coaching heuristic; threshold TBD in §10) | Extend Base via upstream re-eval, or defer discipline introduction; needs human coaching input. |
| Cumulative load + active injury | 2D exclusions remove enough session options that remaining set cannot meet 2A volume × race demand | Extend Build (more weeks under restriction) or escalate to HITL re-evaluation. |

### 6.5 `start_phase != 'Base'` handling

When 3B sets `start_phase` to Build/Peak/Taper:

- `phase_structure.phases` begins at that phase (`phases[0].phase_name = start_phase`).
- Earlier phases are skipped entirely — not in the output, not re-synthesizable on refresh.
- The synthesizer prompt for the starting phase receives an "athlete is starting at `<start_phase>`; prior phases assumed to have established `<intended exit state per 2A>`" context block. Prompt body content deferred per stop-and-ask trigger #2.
- Seam reviewer operates normally at subsequent boundaries (Build→Peak, Peak→Taper). If only one phase exists in `phase_structure.phases` (e.g., `start_phase == 'Taper'` + 4-week event window), `seam_reviews` is an empty list and no seam review runs.
- `phases[0].synthesis_metadata` reflects the "starting phase" synthesis call; no prior-phase context blob exists in this call's input.

Refresh-path implication: a T3 refresh whose scope predates the original `start_phase`'s start_date (e.g., athlete started at Build; refresh wants to cover dates before the Build start) raises `Layer4InputError('refresh_predates_start_phase')` — Layer 4 does not synthesize phases the athlete was supposed to have completed before plan_create.

## 8. Coaching flag rules

Two distinct surfaces:

- **`PlanSession.coaching_flags`** — per-session string list per §7.2; consumed by the athlete-facing plan view (rendering chips/badges next to sessions) and by Layer 3A interpretation (driving "what was this session for" rationale on re-eval). Closed set per §§8.2–8.6.
- **`Layer4Payload.notable_observations`** — call-level `Observation` rows per §7.10; consumed by Layer 3A re-eval (forward-pointer to next call's 3D gate via `elevates_to_hitl`) and by the athlete-facing plan-diff renderer. Closed set per §7.10 `Observation.category` enum + §8.7 trigger table.

### 8.1 Convention — LLM-emitted vs. spec-auto-emitted

Each flag and observation is one of two kinds:

- **LLM-emitted.** The synthesizer prompt instructs the LLM to emit the flag when its coaching reasoning matches the trigger (e.g., "if you prescribe accessory work for a 3A `weak_links` entry, emit `weak_link_targeted`"). The flag travels in the synthesizer's structured output. The orchestrator does NOT add LLM-emitted flags post-hoc.
- **Spec-auto-emitted.** The orchestrator computes the flag deterministically AFTER synthesis (with full session content + phase context + plan metadata in hand) and adds it to the relevant `coaching_flags` list or `notable_observations`. The synthesizer is NOT instructed to emit these; if it does (echoing visible session metadata), the orchestrator's merge is idempotent.

The taxonomy below tags every flag with its kind. A flag is never both — duplication would create ambiguity about which side owns correctness.

**Enforcement.** The orchestrator post-synthesis pass:

1. Computes the spec-auto-emitted flag set per the rules in §§8.2–8.6.
2. Merges into `PlanSession.coaching_flags` (idempotent set-union; preserves LLM-emitted entries on the same session).
3. Computes spec-auto-emitted `notable_observations` per §8.7; appends to `Layer4Payload.notable_observations`.

The deterministic validator (§5.4) additionally checks: if a spec-auto-emit rule's trigger condition is met AND the orchestrator failed to add the flag, raise `coaching_flag_missing_<flag>` (`blocker`). This is a defensive check against orchestrator regressions; never fires in normal operation.

**Closed-set rule.** The synthesizer may only emit flags from §§8.2–8.6 (LLM-emitted entries). Unknown flag names raise `unknown_coaching_flag_<name>` as a schema-violation per §5.5 (one schema retry; bail on second failure). New flags require a spec amendment.

### 8.2 Base-phase per-session flags

| Trigger | Auto-emitted on | Flag | Kind |
|---|---|---|---|
| Discipline newly in 2A `discipline_inclusion` vs. prior plan (or always on `plan_create`) | First session for that discipline in the plan | `first_introduction_to_<discipline>` | Spec-auto |
| Phase is Base AND session is a cardio session | Every Base-phase cardio session | `aerobic_base_focus` | Spec-auto |
| Synthesizer prescribes drill/skill work for a 3A `weak_links` entry of skill type (e.g., bike-handling, swim technique) | The session containing the drill block | `technique_emphasis` | LLM-emitted |
| 3A `data_density` ∈ `{'sparse', 'very_sparse'}` AND week is a Base ramp week | Every cardio session in the ramp week | `volume_ramp_conservative` | Spec-auto |
| Synthesizer prescribes the canonical weekly long-duration aerobic session for a discipline (the "long run" / "long ride" / "long swim" cornerstone of Base) | The session | `long_slow_distance` | LLM-emitted (per Andy 2026-05-16 session-3 calibration: added so the athlete-facing UI can highlight the weekly cornerstone session and Layer 3A re-eval can read it as "this was the LSD anchor of the week") |
| The most-recent prior session within the plan carries the `long_slow_distance` flag AND this session is on the next §K-available calendar day | That session | `recovery_day_after_long` | Spec-auto (per Andy 2026-05-16 session-3 calibration: reinforces "this easy day is intentional, not laziness" for the athlete-facing surface) |

### 8.3 Build-phase per-session flags

| Trigger | Auto-emitted on | Flag | Kind |
|---|---|---|---|
| Synthesizer prescribes strength accessory work for a 3A `weak_links` entry | The strength session | `weak_link_targeted` | LLM-emitted |
| Synthesizer prescribes an intentional brief overreach week (typically last Build week before deload) | All sessions in the overreach week | `overreach_test` | LLM-emitted |
| Synthesizer prescribes race-discipline-specific intensity work for the first time in the plan (e.g., race-pace intervals) | The first such session | `discipline_specific_intensity` | LLM-emitted |
| ACWR forward projection for the week reaches ≥ 1.25 AND is still inside the blocker threshold (≤ 1.4) | Every cardio session in the week | `volume_ramp_aggressive` | Spec-auto (per Andy 2026-05-16 session-3 calibration: threshold raised from ≥ 1.15 to ≥ 1.25 so the flag fires only on genuinely aggressive ramps, not on every mid-band Build week) |

### 8.4 Peak-phase per-session flags

| Trigger | Auto-emitted on | Flag | Kind |
|---|---|---|---|
| Synthesizer prescribes a cardio session at exact race-target pace/power | The session | `race_pace_specific` | LLM-emitted |
| §H.2 lists a tune-up event date falling inside Peak phase | The session nearest the tune-up date | `tune_up_race` | Spec-auto |
| Week contains the highest planned weekly volume in the Peak phase | Every session in that week | `peak_volume_marker` | Spec-auto |

### 8.5 Taper-phase per-session flags

Committed direction per Andy 2026-05-16 race-prep handling (Decision 4). Preserved verbatim from session-1 draft; all five entries are **spec-auto-emitted** (computed from `days_to_event` + session shape post-synthesis).

| Trigger | Auto-emitted on | Flag | Kind |
|---|---|---|---|
| Phase is Taper AND `days_to_event ≤ 14` AND session is a long session | One Taper session per week | `race_rehearsal` (full race-day fueling + pacing + kit practice) | Spec-auto |
| Phase is Taper AND session is a long-or-moderate cardio session | All Taper cardio sessions ≥ 60min | `fueling_practice` (use race-day fueling tier from 2E) | Spec-auto |
| `days_to_event == 7` | One Taper session (typically a light easy day) | `kit_check` (verify equipment per RaceWeekBrief.kit_manifest) | Spec-auto |
| `days_to_event ∈ [3, 5]` AND session is a moderate-or-easy run/ride | One Taper session | `pacing_lock` (rehearse race-day pacing for ≥30 min at race target zone) | Spec-auto |
| `days_to_event ≤ 2` AND session exists | All remaining Taper sessions | `pre_race_taper` (mobility, easy spinning, no novel stimulus) | Spec-auto |

These flags apply on every Layer 4 invocation that touches Taper-phase sessions (`plan_create` covering Taper, `plan_refresh` T2/T3 that includes Taper days, `race_week_brief`). The `race_week_brief` entry point may modify already-existing Taper flags in `prior_plan_session_window` based on the brief's contents (e.g., `kit_check` date moves if the brief picks a different verification cadence).

### 8.6 Cross-phase per-session flags

| Trigger | Auto-emitted on | Flag | Kind |
|---|---|---|---|
| `PlanSession.date == event_date` (event-mode plans) | The race-day session | `race_day` | Spec-auto |
| Synthesizer modulated athlete's picked D-63 intensity per §6.2 of D-63 | The synthesized single session | `intensity_modulated` | LLM-emitted |
| Week is a periodic deload week per standard periodization (typically every 4th week in standard mode; cycle lengths per mode TBD in prompt body) | All sessions in the deload week | `recovery_week` | Spec-auto (per Andy 2026-05-16 session-3 calibration: canonical periodization concept; absence was a real gap) |

### 8.7 Call-level observations — auto-emit rules

Maps the `Observation.category` enum per §7.10 to triggers. Unless noted, observations below are **spec-auto-emitted** (computed by the orchestrator from validator output + synthesis metadata + entry-point context); the synthesizer does not directly emit `Observation` rows.

| Category | Trigger | `elevates_to_hitl` | Kind |
|---|---|---|---|
| `best_effort_plan` | Any `PhaseSpec.synthesis_metadata.cap_hit == True` in this call OR any cross-phase `RuleFailure` with `severity='blocker'` survives the final validator pass | True | Spec-auto |
| `shape_override` | §6.4 `shape_override` path activated | True | Spec-auto |
| `seam_unresolved` | A seam's per-seam iteration cap was exhausted with a non-`approved` final verdict OR a `flagged_major`/`patched` verdict's `re_prompt_*` direction could not be applied because the targeted phase's retry budget was exhausted | True | Spec-auto |
| `intensity_modulated` | Synthesizer emitted the `intensity_modulated` session flag per §8.6 (D-63 path) | False | Spec-auto (triggered by LLM-emitted session flag) |
| `sport_unavailable_at_locale` | D-63 §6.3 error case — picked sport not in any of the athlete's locale equipment views | False (error session carries the surface; observation is informational) | Spec-auto |
| `off_plan_day_note` | D-63 single-session request fell on a day with a planned session AND athlete chose to do the ad-hoc session anyway | False | Spec-auto |
| `warning` | Seam reviewer `flagged_minor` verdict | False | Spec-auto |
| `warning` (with `elevates_to_hitl=True`) | Seam reviewer `flagged_major` + `accept_with_observation` direction per §6.2 authority table | True | Spec-auto |
| `opportunity` | Synthesizer surfaces a coaching opportunity not tied to a rule (e.g., "athlete's MTB volume is climbing; consider adding a technical skill session") | False | **LLM-emitted exception**: synthesizer may emit `Observation(category='opportunity', text=...)` directly; orchestrator passes through. |
| `data_gap` | Any §4 soft-fail (e.g., §4.5 `kit_manifest_inputs_incomplete`) OR 3A `data_density == 'very_sparse'` AND `plan_create` was invoked | False | Spec-auto |
| `data_hygiene` | Validator detected an input-data hygiene issue worth surfacing to athlete (e.g., 3A `weak_links` references a discipline not in 2A inclusion — silently dropped during synthesis, but worth a note) | False | Spec-auto |

The `opportunity` category is the single LLM-emitted exception. All other observation categories are orchestrator-computed.

### 8.8 v1 scope caveats

- Flag taxonomy is closed set (§§8.2–8.6) + observation taxonomy is closed set (§7.10 enum + §8.7 triggers). Adding a flag or observation category is a spec amendment requiring stop-and-ask trigger #5.
- Spec-auto-emit thresholds are v1 defaults: ACWR aggressive-ramp threshold (§8.3 `volume_ramp_aggressive` at ≥ 1.15), the `volume_ramp_conservative` data_density trigger (§8.2), and the Peak-phase `peak_volume_marker` "highest-volume week" definition (§8.4) are evidence-grounded starting points. Tune post-launch with measured flag firing rates.
- Joint-session coordination flags are out of v1 — Layer 4.5 owns that surface. Layer 4 produces solo sessions only; the joint-coordinator overlay (per §2 + §12 forward-pointer) adds its own flag set in the 4.5 spec.

## 9. Caching & determinism

The cache wraps Layer 4 at the orchestrator boundary — the orchestrator computes the cache key from Layer 4's input set, checks the cache, and invokes Layer 4 only on miss. Layer 4 spec defines the canonical key formula per entry point; orchestrator owns cache backend + storage shape + observability.

### 9.1 Per-entry cache keys

All payload hashes are SHA-256 of canonical-JSON encoding of the typed payload (sorted keys; stable serialization for sets/dates/Decimals). All cache keys are SHA-256 of the concatenation of the listed components separated by `||`.

**`llm_layer4_plan_create`:**

```
key = sha256(
    user_id ||
    layer1_hash ||
    layer2a_hash || layer2b_hash || layer2c_bundle_hash || layer2d_hash || layer2e_hash ||
    layer3a_hash || layer3b_hash ||
    plan_start_date.isoformat() ||
    etl_version_set_canonical_json ||
    model_synthesizer || model_seam_reviewer ||
    str(temperature) ||
    str(max_tokens_per_phase) || str(capped_retries_per_phase)
)
```

`layer2c_bundle_hash` is `sha256` of the canonical-JSON encoding of `dict[locale_id → layer2c_hash]` (sorted by `locale_id`). `plan_version_id` is NOT in the key — it's allocated per call and would prevent any cache reuse; rebinding on hit is handled per §9.4.

**`llm_layer4_plan_refresh`:**

```
key = sha256(
    user_id ||
    tier ||
    refresh_scope_start.isoformat() || refresh_scope_end.isoformat() ||
    layer1_hash ||
    layer2_bundle_canonical_hash ||
    layer3a_hash ||
    layer3b_hash ||
    prior_plan_session_window_hash ||
    (parsed_intent_hash or '') ||
    etl_version_set_canonical_json ||
    model_synthesizer ||
    (model_seam_reviewer or '') ||
    str(temperature) ||
    str(max_tokens) || str(capped_retries)
)
```

`layer2_bundle_canonical_hash` is `sha256` of canonical-JSON encoding of `{attr → layer2x_hash or null}` for attr ∈ `{'a', 'b', 'c', 'd', 'e'}` (sorted; null entries preserved so the cache differentiates "T1 cascade with 2A re-run" from "T1 cascade with no Layer 2 re-run"). `prior_plan_session_window_hash` is `sha256` of canonical-JSON encoding of `prior_plan_session_window` (PlanSession list sorted by `(date, session_index_in_day)`); the ±7-day context window per §3.2 IS included in the hashed set. `model_seam_reviewer` only contributes to the key when the call actually routes to Pattern A (T3 cross-phase per §5.1) — otherwise it's `''` to prevent gratuitous cache misses on the model field for Pattern B refreshes.

**`llm_layer4_single_session_synthesize`:**

```
key = sha256(
    user_id ||
    request_canonical_json ||
    layer1_hash ||
    (layer2c_locale_hash or '') ||
    layer2d_hash ||
    layer3a_hash ||
    etl_version_set_canonical_json ||
    model ||
    str(temperature) ||
    str(max_tokens) || str(capped_retries)
)
```

`request_canonical_json` is canonical-JSON of the `SingleSessionRequest` dataclass per D-63 §4.3. `suggestion_id` is intentionally NOT in the key — the same `(request, athlete profile, current state)` should return the same session shape; the orchestrator persists the cached output to a new `suggestion_id` row on a fresh request (rebinding per §9.4).

**`llm_layer4_race_week_brief`:**

```
key = sha256(
    user_id ||
    layer1_hash ||
    layer2a_hash || layer2b_hash || layer2c_bundle_hash || layer2d_hash || layer2e_hash ||
    layer3a_hash || layer3b_hash ||
    prior_plan_session_window_hash ||
    etl_version_set_canonical_json ||
    model ||
    str(temperature) ||
    str(max_tokens) || str(capped_retries)
)
```

`plan_version_id` excluded for the same reason as `plan_create`. The brief's date-anchored output (`days_to_event`, `kit_check_dates`) re-derives from `layer3b_payload.event_date` and `today()`; today's date is NOT in the key — the orchestrator instead invalidates `race_week_brief` caches at midnight UTC (`days_to_event` shifts daily). See §9.3.

### 9.2 Per-phase cache for Pattern A

Pattern A composes the plan from N sequential per-phase synthesis calls. Each per-phase call has its own derived key:

```
phase_key[i] = sha256(
    call_cache_key ||
    phases[i].phase_name ||
    str(i) ||
    (phases[i-1].accepted_output_hash if i > 0 else '')
)
```

`phases[i-1].accepted_output_hash` is `sha256` of canonical-JSON of phase `i-1`'s accepted `list[PlanSession]` + the `PhaseSpec.synthesis_metadata` for that phase. This chains per-phase caches: any change in phase `i`'s prior-phase output invalidates phase `i`'s cache.

**Per-phase cache hit semantics.** During Pattern A execution:

1. Check `phase_key[0]`. If hit: skip synthesis, reuse the cached `(sessions, synthesis_metadata)` tuple; compute `phases[0].accepted_output_hash` from the cached output.
2. Check `phase_key[1]`. If hit: skip; ...
3. First miss along the chain: re-synthesize THAT phase and all downstream phases (downstream `phase_key[]` values depend on this phase's output and will miss).

**Seam reviews are NOT cached.** Each seam review depends on both adjacent phase outputs + boundary state; re-runs on any phase re-synthesis. Seam-review LLM call cost is small relative to a per-phase synthesizer call; the bookkeeping overhead of a separate per-seam cache isn't justified for v1.

**Practical usefulness.** Per-phase cache is primarily a within-call optimization: when a phase's validator-driven retry succeeds, downstream phases can hit if the orchestrator persists per-phase output between retries within the call. Across-call per-phase reuse (e.g., re-running `plan_create` with byte-identical upstreams) is rare in practice — `plan_create` typically only re-fires after an upstream invalidation, which changes the call cache key and invalidates the whole chain.

**Pattern A T3 cross-phase refresh.** When the scope spans a phase boundary, Pattern A re-synthesizes only the phases overlapping the scope window (§6.3). Phases outside the scope keep their prior-plan sessions; their per-phase cache is irrelevant (no synthesizer call is made for them).

### 9.3 Invalidation triggers

Per Control_Spec §4 partial-update model. Layer 4 cache invalidation is triggered by:

| Upstream change | Invalidates |
|---|---|
| `Layer1Payload` changes (any §A–§L field re-derived) | All Layer 4 caches for the affected user (all four entry points). |
| `Layer2APayload` / `Layer2BPayload` / any `Layer2CPayload` / `Layer2DPayload` / `Layer2EPayload` changes | All Layer 4 caches for the affected user except `single_session_synthesize` keys that don't reference the changed Layer 2 payload (D-63 consumes 2A + 2C-for-locale + 2D only; a 2B/2E change does not invalidate D-63 caches). |
| `Layer3APayload` changes (3A re-eval) | All Layer 4 caches for the affected user. |
| `Layer3BPayload` changes (3B re-eval) | `plan_create`, `plan_refresh` T2/T3, `race_week_brief` caches. T1 `plan_refresh` keys still reference `layer3b_hash` per §9.1 (3B is read for the intensity-distribution validator even on T1 per §4.3); 3B re-eval invalidates T1 entries as well. `single_session_synthesize` keys do NOT reference 3B; not invalidated. |
| `etl_version_set` bumps | Every Layer 4 cache (`etl_version_set` is in every key). |
| Model version bump (`model_synthesizer`, `model_seam_reviewer`, `model`) | Cache entries whose key references the bumped model. |
| Tunable change (`temperature`, `max_tokens*`, `capped_retries*`) | Cache entries whose key references the changed tunable. |
| Date rollover (midnight UTC) | `race_week_brief` caches only — brief output is `days_to_event`-anchored and shifts daily. Plan/refresh/single-session caches survive date rollover; their date anchoring (e.g., `plan_create`'s `plan_start_date`) is in the key explicitly. |

Invalidation is orchestrator-side: when an upstream layer's payload is re-derived (Control_Spec §4), the orchestrator MUST evict downstream Layer 4 cache entries before the next invocation. v1 implementation strategy: orchestrator tracks `(user_id, layer, version)` triples per upstream layer and constructs an eviction predicate over Layer 4 cache entries. Alternative strategies (event-driven eviction queues, TTL with input-version stamping) are orchestrator concerns outside this spec.

### 9.4 Determinism guarantees

- **Same inputs + same model + same temperature → same cache key → cache hit returns byte-identical Layer4Payload** (modulo per-call rebinding below).
- On cache miss, the synthesizer is NOT deterministic even at `temperature=0.2`. The cache is an output cache, not a derivation guarantee.
- When the Anthropic API exposes a `seed` parameter for hard determinism, add it to every entry-point cache key (next to `temperature`) and forward to the API call. v1 does not use `seed`.
- **Per-call rebinding on cache hit.** `plan_version_id` is allocated per call by the orchestrator and is never in the cache key. A cache hit on any Pattern A or B plan/refresh/brief entry returns the cached `Layer4Payload` with `plan_version_id` overwritten to the call's allocated value; all `PlanSession.plan_version_id` fields are likewise overwritten. `suggestion_id` is rebound the same way for `single_session_synthesize`. Rebinding is byte-precise — no other fields change on a cache hit.

### 9.5 Cache scope + lifetime

- **Scope:** keyed by `(cache_key)` — `user_id` is in every cache_key, so cross-user contamination is impossible. Cache MAY be shared across processes/instances (no per-process state); backend is the orchestrator's choice (Redis, Postgres JSONB, in-memory LRU).
- **Lifetime:** entries live as long as their inputs are valid per §9.3. No time-based TTL in v1 (except the `race_week_brief` midnight-UTC rollover). If a time-based TTL is added by the orchestrator, the spec recommends an upper bound aligned with typical 3A re-eval cadence (~7 days) so stale plans don't persist when no explicit invalidation event fires.
- **Storage shape:** Layer 4 returns a complete `Layer4Payload` dataclass; orchestrator serializes (canonical-JSON or equivalent) for cache write and deserializes for cache hit. Per-phase cache (§9.2) stores `(list[PlanSession], PhaseSpec.synthesis_metadata)` tuples keyed by `phase_key[i]`.

### 9.6 Observability

The cache layer is observable via orchestrator-side metrics:

- Hit rate per entry point.
- Per-phase hit rate (Pattern A only).
- Cache-driven latency savings per entry point (compare cache-hit return time to cache-miss synthesis time).
- Invalidation event count per upstream-layer change, surfaced for cache-thrash detection.

Layer 4 itself emits NO cache metrics — Layer 4 only runs on miss, so it cannot observe hits. `Layer4Payload.latency_ms_total` is synthesis-only; the orchestrator stamps cache-hit returns with a separate `cache_hit_ms` measurement if end-to-end latency surfacing is wanted.

## 10. Edge cases

Section organized by failure-mode class. Each case names the trigger, the spec contract that governs it, and the expected Layer 4 behavior (observation emitted, error raised, or graceful degradation). Cases marked **(carry-forward)** trace back to §§4–9 contracts; cases marked **(new this session)** were uncovered during §11/§13 drafting and round back to §6.4 + §9 closures the session-3 calibration flagged forward.

### 10.1 Degenerate timelines

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| Single-phase Pattern A | `plan_create` with `time_to_event_weeks ≤ 4` AND 3B `start_phase == 'Taper'` (e.g., athlete onboarding 3 weeks out from a marathon) | §5.1, §6.5 | Pattern A runs; `phase_structure.phases` has exactly one entry (`Taper`); `seam_reviews == []` (empty list, not None — `seam_reviews is None` is reserved for Pattern B); no seam reviewer LLM call fires; `pattern == 'A'` per §7.12 invariants. Latency near the lower bound of §11.1 (~6–10s p50). |
| Two-phase Pattern A | `plan_create` with `start_phase == 'Peak'` + remaining `Peak` + `Taper` (e.g., 6-week event window) | §5.1, §6.5 | Pattern A runs; `phase_structure.phases` has Peak + Taper; one seam review fires (Peak→Taper). |
| Open-ended mode at exactly 12-week horizon | `plan_create` with `layer3b_payload.mode == 'open-ended'` | §6.1 | `total_weeks = 12`; all `standard` mode proportions apply (Base 6w / Build 4w / Peak 1w / Taper 1w with whole-week rounding pushing remainder to Base); the 12-week boundary is the synthesis horizon, not a re-eval trigger (D-57 still deferred). |
| Open-ended mode at horizon decay | Athlete is 10 weeks into a 12-week open-ended plan; T3 refresh fires | §3.2, §6.1 | T3 refresh's `refresh_scope_end` is allowed to extend past the original 12-week horizon (rolling-forward semantics); orchestrator computes `total_weeks` afresh from `plan_start_date = today`; Pattern A or B per §5.1 routing on the new shape. |
| Single-day event in event mode | `plan_create` with `time_to_event_weeks == 1` AND `start_phase == 'Taper'` AND event 5 days out | §6.1 | Single-phase Taper Pattern A as above; `event_date` falls inside `scope_end_date`; the race-day session carries `coaching_flags=['race_day']` per §8.6; if `days_to_event ≤ 14`, `race_week_brief` should fire in parallel (orchestrator-driven, not Layer 4's call). |

### 10.2 Shape-infeasibility detection algorithms

Concrete detection rules for the four `Layer4ShapeInfeasibleError` classes flagged in §6.4. Each rule is a pure-function check; Layer 4 evaluates after `phase_structure_from_3b()` returns and before per-phase synthesis. Failure raises `Layer4ShapeInfeasibleError(class, evidence)` with `class` set to the matched detection name and `evidence` containing the inputs that triggered it.

| Class | Detection algorithm | Tolerance |
|---|---|---|
| `schedule_volume_infeasible` | For each phase `p`, sum `available_window_hours_per_week` across §K days marked `available=True` (per-day windows from `daily_availability_windows`). If `sum_hours < 2A.phase_load_bands[<dominant_discipline>][p].low × 0.85`, raise. The 0.85 factor allows the synthesizer some slack — sub-band-low by ≤15% is a `warning` not a `blocker`. | 0.85 × `phase_load_bands.low` |
| `discipline_frequency_infeasible` | Compute `min_frequency_per_discipline = ceil(2A.discipline_weights × 7)` (each discipline needs at least 1 session per week if its weight ≥ 0.15, else allowed to skip weeks). If `sum(min_frequency_per_discipline) > §K available_days_per_week + 2 × at-least-2-sessions-per-day-days`, raise. Two-sessions-per-day capacity per §7.12 contributes extra slot capacity but capped at 1 strength + 1 cardio. | Strict — no tolerance; if the math doesn't fit, athlete must drop a discipline (2A re-eval) or add days (§K edit). |
| `skill_acquisition_infeasible` | For each newly-introduced discipline (in 2A `discipline_inclusion` but NOT in any prior plan's discipline set), if 3B `start_phase != 'Base'` AND remaining Base weeks `< 4` (v1 default; skill-consolidation minimum), raise. Skill-heavy disciplines per Layer 2A tags (`requires_skill_acquisition=True`): swim, MTB, packraft, rock climbing, skimo. | 4 weeks Base minimum for skill-heavy disciplines. |
| `cumulative_load_injury_infeasible` | After applying 2D exclusions to each phase's exercise pool, if any phase has `len(available_strength_exercises) < ceil(2A.discipline_weights[strength] × 7) × 2` (each strength session needs ≥2 distinct exercises; v1 floor), raise. Cardio analogue: if 2D excludes the only cardio modality for a discipline (e.g., all-running-banned wrist-fall injury), raise. | Strict — exclusions that empty a phase's modality pool are unworkable. |

When raised, `Layer4ShapeInfeasibleError` propagates per §3.5: orchestrator catches and surfaces to the next 3D HITL gate (with athlete-facing message derived from `evidence`) or to an inline error in the current `plan_create` flow per orchestrator routing decision (still tracked in §12 as open). No Layer 4 sessions are written; `plan_versions` row is rolled back per D-64 §6.2 atomic-write semantics.

### 10.3 Refresh edge cases

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| Refresh into Pattern-B-generated prior plan | T3 refresh; prior plan was a T2 refresh (Pattern B; `phase_metadata is None` on prior `PlanSession` rows) | §3.2, §7.12 | Layer 4 reconstructs `phase_metadata` from the CURRENT 3B shape (`layer3b_payload.periodization_shape`) for the refresh scope, not from the prior plan's missing metadata. Out-of-scope prior sessions remain pointed at their prior `plan_version_id` per D-64 §6.3 per-day-pointer; their `phase_metadata` stays None. |
| Refresh crosses 3B-shifted `start_phase` | T2 or T3 refresh; 3B re-eval shifted `start_phase` from Build → Peak between the prior plan and the refresh | §5.1, §6.5 | Pattern A activates even on T2 if the new `start_phase` falls inside the refresh scope (otherwise the refresh would silently skip the phase transition). Concrete: route via §5.1 by comparing `scope` against the recomputed `phase_structure.phases[].start_date`; if scope spans any new boundary, Pattern A. |
| Refresh predates start_phase | T3 refresh; `refresh_scope_start < phase_structure.phases[0].start_date` (athlete asks for "next 28 days" but the new 3B shape puts those 28 days before Build started) | §6.5 | Raises `Layer4InputError('refresh_predates_start_phase')` per §6.5 — Layer 4 does not synthesize pre-`start_phase` sessions. Orchestrator must either advance the scope or route to `plan_create`. |
| Empty `prior_plan_session_window` | T1/T2/T3 refresh with no prior plan covering the scope | §4.3 | Raises `Layer4InputError('prior_plan_window_empty')`. Orchestrator must route to `plan_create` instead. |
| Prior plan references retired discipline | T3 refresh; prior session has `discipline_id` no longer in 2A `discipline_inclusion`, AND no `intensity_modulated` / `shape_override` rationale | §4.3 | Raises `Layer4InputError('prior_session_orphaned')`. The allowed branch is when the prior session was already flagged with an override rationale (athlete dropped the discipline mid-plan); silent retired-discipline references raise. |
| ParsedIntent contradicts validator output | T1/T2 refresh; `parsed_intent` says "make Wednesday harder" but ACWR forward projection blows past 1.4 if Wednesday is intensified | §5.4, §5.5 | Validator-driven retry fires with the failure context; synthesizer reconciles by adjusting other days to keep ACWR in band, OR best-effort accepts (cap hit) + emits `best_effort_plan` observation with `text` referencing the intent / validator conflict. |
| Concurrent refresh + plan_create | Race condition: athlete fires T1 refresh; orchestrator concurrently fires `plan_create` (e.g., scheduled re-eval) | §7.11, D-64 §6.2 | Orchestrator-owned per the atomic-write semantics — both calls allocate distinct `plan_version_id` values; the second-to-commit supersedes the first via `superseded_at` / `superseded_by_version_id`. Layer 4 itself has no race-condition exposure (it doesn't read or write `plan_versions` outside the orchestrator's allocated row). |

### 10.4 Single-session (D-63) edge cases

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| Sport unavailable at any locale | `request.sport` not present in any locale's effective equipment view AND not satisfiable via `quick_equipment` | D-63 §6.3 | Returns `Layer4Payload` with `len(sessions) == 1`, session shape is an "error session" carrying `kind=='rest'` + `rest_reason='athlete_unavailable'` + `session_notes` explaining sport unavailability + `notable_observations` contains `Observation(category='sport_unavailable_at_locale', ...)`. Athlete-facing surface renders the error inline. |
| Locale equipment changed mid-request | Athlete edits `locale_equipment_overrides` between D-63 request submission and Layer 4 invocation | §4.1 | Caught by `etl_version_set_mismatch` precondition — if the 2C re-resolution bumps `etl_version_set['layer2c']`, raises `Layer4InputError('etl_version_set_mismatch')`. Orchestrator catches, re-runs 2C, re-invokes Layer 4 with updated payloads. v1 doesn't retry transparently; surfaces to the athlete with a "your equipment list changed; retrying" inline message. |
| Wrist injury + only-strength-day request | D-63 `request.intensity == 'hard'`, strength sport, but 3A `active_injuries` excludes every available compound lift | §5.4 `injury_violation_*` | Validator fails with `injury_violation_blocker`; capped retry fires; synthesizer substitutes per 2C Tier-2/3 to body-part-safe alternatives. If retry cap exhausts, best-effort session emitted + `Observation(category='warning', elevates_to_hitl=True, text='all standard upper-body strength options blocked by active wrist injury; recommended rest day')`. |
| Athlete picks "Somewhere else" with empty `quick_equipment` | `request.locale_slug is None` AND `len(request.quick_equipment) == 0` | §4.4 | Raises `Layer4InputError('locale_and_quick_equipment_both_unset')`. D-63 frontend should pre-validate, but Layer 4 enforces. |
| Intensity modulation contradicts request | Athlete picks `intensity='hard'` but 3A shows just-completed hard session yesterday + elevated ACWR | D-63 §6.2 | Synthesizer modulates intensity downward (e.g., to `moderate`); emits `intensity_modulated` LLM-emitted flag per §8.6 (auto-bubbled to `Observation(category='intensity_modulated', elevates_to_hitl=False)` per §8.7). `session_notes` explains the modulation in direct voice. |
| Two D-63 sessions same day | Athlete fires D-63 twice on the same date (different sports or times) | §7.12 | Layer 4 doesn't enforce — each D-63 call is independent. The two-per-day rule (§7.12) applies to `PlanSession` rows persisted under a `plan_version_id`, but ad-hoc sessions are stored in `ad_hoc_workout_suggestions` (separate table per D-63 §4.3). Orchestrator decides whether to surface a "you've already done a workout today" prompt; Layer 4 produces the session if input validation passes. |

### 10.5 Race-week brief edge cases

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| No Taper-phase sessions in window | `race_week_brief` fires; `prior_plan_session_window` covers Taper window but `phase_structure` puts athlete still in Peak (e.g., compressed mode + late Peak transition + race in 14 days) | §3.4, §5.3 | Brief is still produced — Taper-flag set is applied to whatever sessions exist in the brief window regardless of phase tagging; `RaceWeekBrief.race_day_fueling_plan` + `kit_manifest` produced from 2E + 2C; `RaceWeekBrief.pre_race_logistics` reflects actual phase (`Peak transitioning to Taper`). Edge surfaces via `data_gap` observation: "still in Peak with 14 days to event — race-week prep advice may differ from a true Taper window". |
| race_week_brief fires > 14 days out | Athlete-manual fire at `days_to_event = 20` | §4.5 | Raises `Layer4InputError('race_week_brief_too_early')`. UI surface should disable the trigger button outside the window; if disabled-state is bypassed, error surfaces inline. |
| Event date already passed | `event_date < today` | §4.5 | Raises `Layer4InputError('event_date_in_past')`. Post-race brief is not in scope; analytics handoff lives in Layer 5 / a future post-race-analysis surface. |
| Multi-day event with no locale equipment data | `race_format == 'expedition_ar'` + every locale in the route has empty `equipment_overrides` | §4.5 | Soft warning per `kit_manifest_inputs_incomplete`; emits `data_gap` notable_observation; `kit_manifest` is still produced but with free-text items (not `layer0.equipment_items`-resolved); `KitItem.item` strings come straight from synthesizer prompt without canonical-name verification. |
| Brief re-fire on midnight UTC boundary | `race_week_brief` cached; athlete re-fires 1 minute past midnight UTC | §9.3 | Cache invalidates per midnight-UTC rule (`days_to_event` shifted from N to N-1); fresh synthesis runs. `kit_check_dates` re-derive from new `today`; pre-race meal timing re-anchors. |
| Single-day event in multi-day code path | `race_format == 'single_day'` but caller mistakenly populates `race_plan` request shape | §3.4, §7.12 | `RacePlan` is None on output per §7.12 (multi-day-events-only rule); orchestrator can't force `race_plan` non-None for single-day events. Layer 4 silently drops any caller-supplied multi-day hints. |

### 10.6 Cache + concurrency edge cases

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| Cache-hit-with-rebind collision | Two concurrent `plan_create` calls from same user (e.g., orchestrator retries an in-flight call after a timeout) with identical inputs → both hit the same cache entry; orchestrator allocates two different `plan_version_id` values | §9.4 | Both calls return byte-identical `Layer4Payload` except for `plan_version_id` rebinding per §9.4; both `plan_version_id` values reference valid `plan_versions` rows; the second-to-commit supersedes the first per D-64 §6.2 atomic-write. No Layer 4 contract violation. |
| Per-phase cache hit on phase 0 + miss on phase 1 | Pattern A within-call: phase 0 synthesizer call succeeds; phase 1 first-pass synthesis fails validator; retry rebuilds context; phase 0 cache still hits (same `phase_key[0]`); phase 1 second pass is a fresh synthesizer call | §9.2 | Per §9.2 step 3: phase 1 cache check on the retry computes a NEW `phase_key[1]` because phase 1's retry context (RuleFailure constraints merged in) differs from first-pass context — but the chain dependency (`phase_key[1]` includes `phases[0].accepted_output_hash`) is unchanged; the miss is on the retry-context-dependent component, not the chain dependency. Phase 0 remains cached; phase 1 re-synthesizes; phase 2+ re-check cache against new `phase_key[2]` etc. |
| Per-phase cache hit on phase 0 + seam review re-prompts phase 0 | Pattern A: phase 0 hits cache; phase 1 hits cache; seam review (0→1) verdict `flagged_major` with `re_prompt_prior`; re-synthesizes phase 0 with `seam_issues` constraint context | §6.2, §9.2 | New `phase_key[0]` computed with seam-issue-merged context; cache miss; fresh phase 0 synthesis; phase 0's new `accepted_output_hash` differs; phase 1's `phase_key[1]` recomputes and misses; full downstream re-synthesis. The cache was helpful only on the first pass; the seam-driven re-prompt invalidates the whole chain. |
| Cache hit serves stale upstream payload | Orchestrator regression — fails to evict cache on upstream Layer 2 re-run | §9.3 | Spec is defensive but not bulletproof: if the orchestrator violates §9.3 invalidation, Layer 4 silently returns the stale cached payload. The `etl_version_set` in the cached payload would still reflect the OLD version set; the deterministic validator (§5.4) does NOT re-run on cache hit (the cached `validator_results` are returned verbatim). Caller-side defense: orchestrator should sanity-check returned `Layer4Payload.etl_version_set` against current pin and surface a `cache_stale` warning if mismatched. Not enforced by Layer 4 spec — this is the only orchestrator-trust point in §9. |
| Concurrent plan_refresh + plan_create on overlapping windows | T3 refresh fires; orchestrator concurrently fires `plan_create` for a future window that overlaps | D-64 §6.2 | Same handling as §10.3 "Concurrent refresh + plan_create": two distinct `plan_version_id` values, last commit wins via `superseded_*`. No Layer 4 read-write race. |
| Cache backend transient failure | Redis timeout / Postgres deadlock on cache write | §9.5 | Orchestrator concern, not Layer 4's — Layer 4 produces the payload regardless of cache backend health. Failed cache write degrades to "miss on next call"; no data loss. |

### 10.7 Validator + retry edge cases

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| Seam reviewer disagrees with itself | Pattern A: seam (0→1) reviewed initial verdict `flagged_major` + `re_prompt_next`; phase 1 re-synthesized; second seam review verdict `flagged_major` + `re_prompt_prior` (opposite direction!) | §6.2 | Per §6.2 per-seam iteration cap: each seam is reviewed at most twice. Second `flagged_*` verdict triggers `seam_unresolved` notable_observation (severity `warning`, `elevates_to_hitl=True`); current synthesis accepted; no further re-prompting. The "disagreement direction" is recorded in `SeamReview.proposed_patch_direction` for both passes but not acted on. |
| Validator-retry budget exhausted by seam path | Pattern A: phase 1 consumed 2 validator-driven retries; seam reviewer then emits `re_prompt_next` for phase 1 | §6.2, §5.5 | Per §6.2 seam-driven-retry-interaction paragraph: phase 1's `retries_used == cap`; seam reviewer's patch direction is recorded but NOT applied; `seam_unresolved` observation emitted; `SeamReview.triggered_resynthesis = False`. |
| Best-effort accepted with blocker rule failure | Cap exhausted on phase 2; latest pass has `blocker`-severity rule failure (e.g., `volume_band_blocker_week_3`) | §5.5 | Per §5.5 best-effort acceptance: outstanding `blocker` rule failures are demoted to `warning` severity in the `ValidatorResult.rule_failures` list; `Observation(category='best_effort_plan', elevates_to_hitl=True)` emitted; plan still writes. The blocker failure is visible in the diff view but does not block plan commit. |
| Cross-phase rule failure on final pass | Pattern A: per-phase validators all accept; final cross-window ACWR projection fails (cumulative trajectory across all phases exceeds 1.4) | §5.2 step 5 | Cross-phase failures cannot be retried (the rule spans phases; no single phase to re-prompt). `RuleFailure` emitted with `phase_name=None` + `severity='blocker'`; elevates to `best_effort_plan` observation per §5.5; plan writes with the cross-phase failure recorded. The unresolved cross-phase failure flows to 3D HITL on the next gate via `elevates_to_hitl=True`. |
| Schema-violation on first retry too | Synthesizer returns malformed structured output twice in a row (e.g., missing `kind` field on a `PlanSession`) | §5.5 | First malformed output triggers a schema-validation retry (counter does NOT consume per-phase budget); second malformed output raises `Layer4OutputError('schema_violation')` and bails out of the call. Caller surfaces a "synthesis failed; try again" inline error; the partial cumulative plan (if Pattern A) is rolled back. |
| Unknown coaching flag from synthesizer | Synthesizer emits `coaching_flags=['some_novel_flag_not_in_§§8.2_8.6']` on a session | §8.1, §5.5 | Per §8.1 closed-set rule: caught by the deterministic validator as `unknown_coaching_flag_<name>` (`blocker` severity, treated as schema-violation per §5.5). One schema retry fires; on second failure, `Layer4OutputError('schema_violation')`. Adding a new flag requires a spec amendment per §8.8. |
| Spec-auto-emit rule missed by orchestrator | Orchestrator regression: spec-auto-emit trigger condition met but flag not added to `coaching_flags` post-synthesis | §8.1 | Caught by the defensive validator check: emits `RuleFailure(rule_name='coaching_flag_missing_<flag>', severity='blocker')`. This rule never fires in normal operation; it's a regression guard for orchestrator behavior. |

### 10.8 ETL + version drift edge cases

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| ETL version set mismatch across payloads | One payload was generated under `etl_version_set['layer0a'] = 'v7'`, another under `'v8'` | §4.1 | `Layer4InputError('etl_version_set_mismatch')`. Fail-fast precondition; orchestrator must re-run prerequisite layers before retrying. |
| ETL version set bumps mid-synthesis | Layer 0 ETL re-runs (e.g., new exercise data) AFTER Layer 4 starts but BEFORE the call completes | §4.1, §9.3 | Layer 4 doesn't re-read `etl_version_set` mid-call; the pin in the inputs is the only version reference. The call completes with the old version set. The next invocation will detect the mismatch via §4.1; if cached, the cached entry's `etl_version_set` will diverge from the orchestrator's current pin (see §10.6 "cache hit serves stale upstream payload" defense). |
| Stale Layer 3A payload | 3A re-eval happened after the timestamp on the supplied `layer3a_payload.created_at` | §4.1 | `Layer4InputError('stale_input_payload')` per `is_payload_stale()` check. |
| `created_at` clock skew across services | Two services on different VMs produce payloads with clocks off by ~30s; comparison hits a false "stale" | §4.1 | v1 accepts the false-fail risk — `is_payload_stale()` is a strict timestamp comparison. Orchestrator should NTP-sync producing services; if drift surfaces in practice, add a ±60s tolerance to `is_payload_stale()` (deferred to §12). |

### 10.9 Multi-athlete / joint-session boundary edge cases (Layer 4.5 forward-pointer)

Layer 4 is solo-only per §2 + §12. Edge cases that PROBE the boundary:

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| Joint session in §L on a refresh boundary | Athlete has §L joint sessions configured (Layer 4.5 territory); T3 refresh covers a date with a joint session | §2 (joint coordination out of v1) | Layer 4 produces a SOLO session for that date based on the athlete's solo plan; ignores §L. Layer 4.5 (when shipped) will run as a post-pass and supersede the solo session with a coordinated joint session via a future `joint_session_id` FK addition per §2 narrative. v1: athlete sees the solo session; no joint coordination. |
| Linked athletes refreshing simultaneously | Two athletes linked via §L both fire T1 refresh at the same time | §2, §7.11 | Each athlete's Layer 4 call is independent — they consume separate `Layer4Payload` rows under separate `plan_version_id` values per athlete. Layer 4.5 (when shipped) will need to re-harmonize post-refresh; v1 Layer 4 has no coordination responsibility. |
| §L join_strength_session toggle flipped mid-plan | Athlete edits §L to add a new joint session day after plan_create | §2 | No Layer 4 behavior change in v1 — Layer 4 reads §L for context (per §3.1 `layer1_payload` notes) but does not act on it. Layer 4.5 will react when shipped. |

### 10.10 Misc / cross-section catch-all

| Case | Trigger | Spec contract | Expected behavior |
|---|---|---|---|
| All days marked unavailable per §K | Athlete has `available=False` on every day of the week | §4.1, §6.4 detection | `schedule_volume_infeasible` shape-infeasibility per §10.2 — `available_window_hours_per_week == 0` < phase load bands' low. Raises `Layer4ShapeInfeasibleError(class='schedule_volume_infeasible', ...)`. |
| Athlete in event mode with `time_to_event_weeks > 26` | Onboarding scenario: athlete signed up for a race 9 months out | §6.1 | Layer 4 honors `total_weeks = time_to_event_weeks` (no upper cap on event-mode horizon). Pattern A runs across all phases proportionally. Latency at the higher end of §11.1 — a 26-week plan is still 4 phases + 3 seams + final validator pass; latency dominated by phase count, not week count within phases. Long-horizon caveats fold into the D7 tiered tight/loose discussion (held). |
| Athlete with zero historical training data | 3A `data_density == 'very_sparse'` + first plan_create | §6.4, §8.7 | If `start_phase != 'Base'`, shape-override per §6.4 fires (force Base); coaching flag `volume_ramp_conservative` auto-emitted per §8.2; `data_gap` observation per §8.7 (`elevates_to_hitl=False`); plan proceeds conservatively. |
| Race-day session falls on athlete-unavailable day per §K | `event_date` falls on a §K `available=False` day | §5.4 `schedule_violation_*` | Special-case: `race_day` flag overrides `schedule_violation`; the schedule-availability validator rule allows `coaching_flags` containing `race_day` to bypass the §K availability check. v1 codifies this exception inline in the rule implementation; no further override needed. |
| 3B suggested_adjustments contradicts validator | 3B says "athlete should drop trail running"; validator finds plan without trail running fails 2A discipline-coverage rule | §3.1 `layer3b_payload` notes | 3B suggestions are surfaced for athlete-facing rationale (per §3.1) but NOT enforced by Layer 4. Layer 4 synthesizes against the shape 3B picked, not against `suggested_adjustments`. If the suggestion + the shape conflict, the suggestion text is recorded in the synthesis context but the shape wins. |
| Athlete with no locales (orphaned account) | `layer2c_payloads == {}` AND no race locale per §J | §4.1 | `locale_unresolved` precondition failure on `plan_create` (every referenced locale must resolve; empty dict means no locales to pick from). Orchestrator routes athlete back to §J locale-config flow. |

## 11. Performance budget

Per-call-pattern targets for latency, tokens, and cost. All targets are v1 design budgets; production measurements drive a tuning pass post-launch (same posture as the §5.4 tolerance defaults). Andy 2026-05-16 (session 1): accepted the headline Pattern A `plan_create` budget ("plan-gen is being taken seriously; 30–60s wait is fine"). Numbers below honor that commitment.

### 11.1 Latency targets per entry point

| Entry point | Pattern | Composition | p50 | p95 | Notes |
|---|---|---|---|---|---|
| `plan_create` (4 phases + 3 seams) | A | 4 × per-phase synthesizer + 3 × seam reviewer + 1 final validator + retry headroom | ~25s | ~60s | Per-phase: ~5–8s synthesizer LLM call. Per-seam: ~3–5s reviewer LLM call. Deterministic validator: ~100ms. Retry headroom: ~0–16s (cap × per-phase latency). |
| `plan_create` (3 phases + 2 seams, e.g., `start_phase='Build'`) | A | 3 × per-phase + 2 × seam + validator | ~18s | ~45s | Linear scaling with phase count. |
| `plan_create` (2 phases + 1 seam, e.g., `start_phase='Peak'`) | A | 2 × per-phase + 1 × seam + validator | ~12s | ~25s | |
| `plan_create` (1 phase, e.g., `start_phase='Taper'` + 4-week window) | A | 1 × per-phase + 0 seams + validator | ~6s | ~12s | Degenerate Pattern A per §10.1. |
| `plan_refresh` T1 | B | 1 × synthesizer + validator | ~4s | ~8s | Smaller context + smaller output. |
| `plan_refresh` T2 | B | 1 × synthesizer + validator | ~5s | ~10s | Larger context than T1; output size similar. |
| `plan_refresh` T3 (intra-phase) | B | 1 × synthesizer + validator | ~6s | ~12s | Largest Pattern B output (~28 days). |
| `plan_refresh` T3 (cross-phase) | A | Typically 2 × per-phase + 1 × seam + validator | ~12s | ~25s | Affected phases only per §6.3; full plan_create latency is the worst case. |
| `single_session_synthesize` | B | 1 × synthesizer + validator | ~3s | ~6s | Smallest context + smallest output. |
| `race_week_brief` (single-day event) | B | 1 × synthesizer + validator | ~8s | ~15s | Larger `max_tokens` (6000) to accommodate the brief body. |
| `race_week_brief` (multi-day event) | B | 1 × synthesizer + validator | ~10s | ~18s | RacePlan adds segment/transition/strategy content; same `max_tokens` budget but more output token consumption. |
| Cache-hit on any entry | — | Cache lookup + deserialize + rebind | <50ms | <200ms | Per §9.4 — byte-precise rebind; orchestrator-side. Layer 4 doesn't run. |

**Latency hygiene rules:**

- A p95 latency above 2× p50 indicates retry exhaustion or schema-violation paths firing more than expected; surfaces as a cache-stats + retry-stats investigation, not a budget bump.
- `plan_create` p99 should not exceed 2× p95 (~120s); if it does, the per-phase max_tokens budget may be too tight, forcing schema-violation retries.
- Pattern A retry tax is bounded: ~16s worst case per phase (cap=2 × ~8s synthesizer) × 4 phases = ~64s worst case retry tax. Combined with the base ~25s p50 budget, absolute worst case for `plan_create` is ~90s — under the p99 ceiling above.

### 11.2 Token budget per entry point

Token estimates at Sonnet 4.6 (input + output budgets per LLM call). Per-phase synthesizer prompts include 3A + 3B + all five 2x payloads + prior phase output + accumulated seam-issues context — substantial input shape per call.

| Entry point | Avg input tokens (per LLM call) | Avg output tokens (per LLM call) | Total LLM calls (no retries) | Total input tokens (full call) | Total output tokens (full call) |
|---|---|---|---|---|---|
| `plan_create` (4 phases + 3 seams) | Synth: ~8000; Seam: ~6000 | Synth: ~3000; Seam: ~800 | 4 + 3 = 7 | ~50000 | ~14400 |
| `plan_create` (1 phase) | Synth: ~7000 | Synth: ~3000 | 1 | ~7000 | ~3000 |
| `plan_refresh` T1 | ~6000 | ~1500 | 1 | ~6000 | ~1500 |
| `plan_refresh` T2 | ~8000 | ~2000 | 1 | ~8000 | ~2000 |
| `plan_refresh` T3 (intra-phase) | ~10000 | ~3500 | 1 | ~10000 | ~3500 |
| `plan_refresh` T3 (cross-phase, 2 phases + 1 seam) | Synth: ~9000; Seam: ~6000 | Synth: ~3000; Seam: ~800 | 2 + 1 = 3 | ~24000 | ~6800 |
| `single_session_synthesize` | ~3500 | ~800 | 1 | ~3500 | ~800 |
| `race_week_brief` (single-day) | ~9000 | ~3500 | 1 | ~9000 | ~3500 |
| `race_week_brief` (multi-day) | ~11000 | ~5500 | 1 | ~11000 | ~5500 |

Retry tax on tokens: each retry duplicates the input (with added RuleFailure context, ~+200 tokens per failure) + generates fresh output. Worst case `plan_create` (every phase hits cap = 2 retries): ~150000 total input tokens + ~43200 total output tokens.

### 11.3 Cost per invocation

At Sonnet 4.6 pricing ($3/MTok input + $15/MTok output as of 2026-05; subject to vendor pricing changes). Cost = `input_tokens × $3e-6 + output_tokens × $15e-6`.

| Entry point | No-retry cost | Worst-case (cap-hit) cost | Notes |
|---|---|---|---|
| `plan_create` (4 phases + 3 seams) | ~$0.37 | ~$1.10 | Headline range $0.50–1.10 per invocation. |
| `plan_create` (1 phase) | ~$0.07 | ~$0.18 | |
| `plan_refresh` T1 | ~$0.04 | ~$0.10 | |
| `plan_refresh` T2 | ~$0.05 | ~$0.13 | |
| `plan_refresh` T3 (intra-phase) | ~$0.08 | ~$0.20 | |
| `plan_refresh` T3 (cross-phase) | ~$0.18 | ~$0.50 | |
| `single_session_synthesize` | ~$0.02 | ~$0.05 | |
| `race_week_brief` (single-day) | ~$0.08 | ~$0.20 | |
| `race_week_brief` (multi-day) | ~$0.12 | ~$0.30 | |
| Cache-hit on any entry | $0 | $0 | Orchestrator-side; no LLM call. |

**Cost hygiene rules:**

- Average per-athlete `plan_create` cost: ~$0.50 (assuming p50 retry rate and 4-phase typical case). Athletes do `plan_create` rarely (onboarding + occasional major re-eval) — typical athlete cost from `plan_create` is < $2/year.
- Average per-athlete refresh cost: athletes are expected to refresh ~1–3×/week (D-64 §6 frequency caps shape this). Worst case unmitigated: 7 refreshes/week × ~$0.10 ≈ ~$0.70/week ≈ ~$36/year per athlete.
- Average per-athlete `single_session_synthesize` cost: ~$0.02 × estimated 3–5 ad-hoc workouts/week ≈ ~$0.10/week ≈ ~$5/year.
- `race_week_brief` cost: one-shot per race event; ~$0.10–0.30 per event.

**Combined per-athlete LLM cost from Layer 4 alone:** ~$40–60/year/athlete at typical usage with no caching. With caching (see §11.4), the marginal cost on cache hits is $0; effective cost depends on hit rate.

### 11.4 Cache hit-rate assumptions + amortized cost

Per §9 cache spec, hit-rate assumptions and resulting amortized cost:

| Entry point | Assumed hit rate (v1 design assumption; measure post-launch) | Rationale |
|---|---|---|
| `plan_create` | <5% | `plan_create` typically re-fires only after a major upstream change (invalidates the cache key). Cache hit is the rare case of orchestrator retry (e.g., timeout-then-redo with identical inputs). |
| `plan_refresh` T1 | ~10% | Same-day-repeat refresh with identical 3A re-eval — rare; most refreshes have a fresh 3A. |
| `plan_refresh` T2 | ~15% | Same-day-repeat with same Layer 2 cascade — slightly more common (athletes who refresh-then-edit-then-refresh). |
| `plan_refresh` T3 | ~5% | Heavy upstream invalidation; cache rarely intact. |
| `single_session_synthesize` | ~25% | The most cacheable surface — same (sport, duration, intensity, locale) request from same athlete with same 3A/2D should return the same session. Athlete-driven [Regenerate] explicitly bypasses cache (different `suggestion_id` → cached body returned; orchestrator may add a re-randomization hint to bust cache for [Regenerate] specifically per §9.4 forward-pointer). |
| `race_week_brief` | <5% | Midnight-UTC invalidation per §9.3 limits within-day reuse; race weeks are short. |

**Per-phase cache hit rate (Pattern A only):** assumed ~10% within-call (helps when a phase's validator-driven retry succeeds — downstream phases stay valid against the same prior-phase output hash). Across-call per-phase reuse: ~<5% — `plan_create` rarely re-fires with byte-identical chain.

**Amortized cost estimate (per athlete per year, with assumed cache rates):**

```
plan_create:             ~$0.50 × 2 calls × 0.95 miss = ~$0.95
plan_refresh T1:         ~$0.04 × 100 calls × 0.90 miss = ~$3.60
plan_refresh T2:         ~$0.05 × 50 calls × 0.85 miss = ~$2.13
plan_refresh T3:         ~$0.20 × 20 calls × 0.95 miss = ~$3.80
single_session:          ~$0.02 × 200 calls × 0.75 miss = ~$3.00
race_week_brief:         ~$0.20 × 3 calls × 0.95 miss = ~$0.57
TOTAL Layer 4 alone:     ~$14/year/athlete (mid-range)
```

This is well under the $40–60/year no-cache estimate; cache pays for itself with even modest hit rates. **Hit-rate assumptions above are unmeasured v1 estimates** — production telemetry per §9.6 drives a true amortized-cost re-estimate post-launch.

### 11.5 Cumulative ceilings — what bounds a runaway

Per-athlete-day and per-athlete-week soft ceilings. These are NOT enforced by Layer 4; they're guardrails the orchestrator should apply via D-64 frequency caps + a future per-athlete cost monitor.

| Window | Soft ceiling | Hard ceiling | Action on breach |
|---|---|---|---|
| Per athlete per day | ~$0.50/day | ~$2.00/day | Soft: surface "you've refreshed a lot today; the AI cost is adding up" inline message. Hard: rate-limit (next refresh fires `cost_cap_exceeded` warning + delays). |
| Per athlete per week | ~$2.00/week | ~$10.00/week | Same staircase. |
| Per athlete per month | ~$8.00/month | ~$30.00/month | Hard cap surfaces account-level support escalation. |

Note: these ceilings interact with D-64 §6 frequency caps (which limit refreshes per-week, not cost). Frequency caps + cost ceilings are complementary: frequency caps prevent UX abuse; cost ceilings prevent runaway LLM spend. Concrete cost-monitor implementation deferred — not Layer 4's responsibility per §2.

### 11.6 Frequency-cap interaction (D-64 §6)

D-64 §6 (when defined) limits refresh frequency per athlete (e.g., T1 max 3×/day; T2 max 1×/day; T3 max 1×/week). Layer 4 honors these caps transparently — when a frequency cap is hit, the orchestrator does NOT invoke Layer 4 at all; the cap fires upstream. Layer 4 has no cap-awareness logic itself.

When the cap is approaching: the orchestrator may pre-warm the cache via a speculative invocation (orchestrator concern). Layer 4 simply receives the call, returns the payload, and caches it per §9.

### 11.7 Concurrency + scale assumptions

v1 single-tenant single-athlete (Andy) — concurrency is effectively N=1. Scale-out assumptions for the v1→v2 selective rebuild path:

- Per-process concurrency: Layer 4 is stateless (apart from the cache, which lives in the orchestrator); a single Python process can handle ~10 concurrent Layer 4 calls in flight (LLM API call latency dominates; CPU is idle most of the time).
- Multi-process scale: horizontal scale via standard Flask + gunicorn / Vercel serverless. No Layer 4 shared state.
- LLM API rate limits: Anthropic per-account RPM + TPM limits apply. At scale (>100 active athletes), batched API access (Anthropic Batch API or rotating API keys) becomes relevant — deferred to scale-track work.

### 11.8 Performance regression detection

Surfaces per §9.6 observability: cache hit rate per entry point + per-phase hit rate (Pattern A) + cache-driven latency savings + invalidation event count. Layer 4 emits `Layer4Payload.latency_ms_total` + `input_tokens_total` + `output_tokens_total` + `llm_call_count` per §7.1 — orchestrator aggregates these to per-entry-point dashboards.

**Alert thresholds (v1 design defaults):**

- Per-entry p95 latency >2× design target for 5 consecutive measurements → investigate cache invalidation thrash or LLM API degradation.
- Per-entry retry rate >20% → investigate prompt-body issues (synthesizer struggling to produce schema-valid output) or validator tolerance tightening.
- Per-entry cost per invocation >2× design target for 24h rolling window → investigate cap-hit rate (best-effort acceptance still costs full retry tax).
- Cache hit rate <50% of assumed rate (§11.4) for 7 consecutive days → investigate orchestrator invalidation logic + cache backend health.

All threshold tuning is v1 default; production rates drive re-tuning per §12.

## 12. Open items / forward references — to be drafted in a later session

- ~~LLM seam-reviewer authority semantics~~ — **Resolved 2026-05-16 (session 2, Decision 8): propose-patch / β.** See §6.2.
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

## 13. Test scenarios

Full TS-N coverage matrix across (entry_point × periodization_shape × tier × validator_pass/fail × cache_hit/miss × coaching_flag_emit_path). Each scenario names: inputs (athlete shape + 3A/3B state + scope), expected outputs (Pattern, sessions count, flags emitted, observations, validator path), and the specific spec contracts it exercises. Scenarios are grouped by entry point with cross-cutting categories (cache + flag + edge) at the end.

Implementation note: each TS will land as one or more pytest cases in `tests/layer4/test_<entry_point>_<scenario>.py` post-spec; the LLM call is mocked via a deterministic fixture (or vcrpy-style recorded response) per scenario. The deterministic validator runs against the fixture output unmocked.

### 13.1 Coverage matrix

| Axis | Values |
|---|---|
| Entry point | `plan_create`, `plan_refresh` T1, `plan_refresh` T2, `plan_refresh` T3 intra-phase, `plan_refresh` T3 cross-phase, `single_session_synthesize`, `race_week_brief` single-day, `race_week_brief` multi-day |
| Periodization shape | `standard`, `compressed`, `extended`, `custom`, shape-overridden (4 trigger classes) |
| `start_phase` | `Base`, `Build`, `Peak`, `Taper` |
| 3A `data_density` | `very_sparse`, `sparse`, `moderate`, `dense` |
| Validator path | first-pass accept, single-retry accept, cap-hit best-effort, schema-violation retry, cross-phase blocker on final pass |
| Seam review path | all approved, flagged_minor record-only, flagged_major + re_prompt_prior, flagged_major + re_prompt_next, flagged_major + accept_with_observation, patched, second-pass seam_unresolved |
| Cache path | miss, hit (no rebind), hit (rebind only), per-phase chain miss after phase 0 hit, per-phase invalidation on seam re-prompt |
| Flag emit path | all spec-auto, all LLM-emitted, mixed, unknown LLM flag (schema-violation), missing spec-auto (defensive validator) |

Full Cartesian is impractical; the TS set below picks high-signal coverage (~50 scenarios across categories).

### 13.2 `plan_create` scenarios

| TS | Inputs | Expected outputs | Contracts exercised |
|---|---|---|---|
| **TS-1** | Andy's actual case: Pocket Gopher Extreme 2026 (expedition AR, 48–56hr), 9 weeks out, 15 disciplines, 3A `aerobic='good' / strength='moderate' / data_density='moderate'`, 3B picks `compressed` + `start_phase='Build'`, no active injuries | `plan_create` Pattern A; 3 phases (Build/Peak/Taper); 2 seams; all approved; `phase_structure.derived_from='3b_compressed'`; ~63 sessions across 9 weeks; `pattern='A'`; `notable_observations` empty | §3.1, §5.1, §5.2, §6.1, §7.1, §7.6 |
| **TS-2** | Same as TS-1 + active wrist injury (Andy's actual May 2026 context): 2D excludes wrist-extension-loaded strength | Same Pattern A flow; strength sessions use 2C Tier-2 substitutes (fist-position pushups, no wrist-extension loads); validator passes; no `injury_violation_*` failures | §5.4 `injury_violation_*`, 2D consumption |
| **TS-3** | New athlete, 12 weeks out, no race target (open-ended mode), `data_density='very_sparse'`, 3B picks `standard` + `start_phase='Base'` | Pattern A; 4 phases (Base/Build/Peak/Taper) proportionally sized; ramp-conservative flag emitted per §8.2; `data_gap` observation per §8.7; `total_weeks=12` per §6.1 v1 default | §6.1 (open-ended 12-week default), §8.2, §8.7 |
| **TS-4** | Athlete 24 weeks out from an Ironman, 3B picks `extended` + `start_phase='Base'`, `data_density='dense'` | Pattern A; 4 phases at extended proportions (Base 14.4 → 14w, Build 6w, Peak 2w, Taper 2w with whole-week rounding); no conservative-ramp flags (dense data); validator accepts first pass | §6.1 extended proportions, §8.2 |
| **TS-5** | Marathon athlete 16 weeks out, 3B sets `mode='custom'` with `phase_weeks={'Base':6,'Build':6,'Peak':2,'Taper':2}` | Pattern A; 4 phases at custom proportions verbatim; `phase_structure.derived_from='3b_custom'`; validator accepts | §6.1 custom mode |
| **TS-6** | 3B `mode='standard'` + `time_to_event_weeks=6` → triggers shape_override per §6.4 row 1 | `shape_override` fires; `ShapeOverride(original_shape_mode='standard', overridden_mode='compressed', ...)`; `Observation(category='shape_override', elevates_to_hitl=True)`; plan synthesizes against the overridden compressed shape | §6.4, §7.8, §8.7 |
| **TS-7** | 3B `mode='compressed'` + `time_to_event_weeks=3` → triggers shape_override per §6.4 row 2 | `shape_override` to `extended` + `start_phase='Peak'`; Peak-only plan + synthesizer-picked ~1wk Taper per §6.1 v1 prompt guidance | §6.4, §6.1 Taper synthesizer-picked |
| **TS-8** | 3A `aerobic_state='very_high'` + `data_density='moderate'` + 3B `start_phase='Base'` + `time_to_event_weeks=10` → shape_override per §6.4 row 3 | `shape_override` to `start_phase='Build'` keeping mode; Build/Peak/Taper plan; rationale_text references "athlete is already aerobically prepared" | §6.4 |
| **TS-9** | 3A `data_density='very_sparse'` + 3B `start_phase='Build'` → shape_override per §6.4 row 4 (calibration round 2) | `shape_override` to `start_phase='Base'` keeping mode; rationale references "baseline training-load data missing"; `data_gap` observation also fires | §6.4 row 4 |
| **TS-10** | §K availability: athlete has only 3 days/week available; 2A `phase_load_bands.low=10hr` for Build dominant discipline → `schedule_volume_infeasible` | `Layer4ShapeInfeasibleError(class='schedule_volume_infeasible', evidence=...)` raised; no sessions written; orchestrator catches | §6.4, §10.2 |
| **TS-11** | Athlete has 6 disciplines each weighted ≥ 0.15; §K has 5 available days/week; even with 2-per-day allowance, frequency exceeds capacity → `discipline_frequency_infeasible` | `Layer4ShapeInfeasibleError(class='discipline_frequency_infeasible', ...)` raised | §6.4, §10.2 |
| **TS-12** | Newly-introduced MTB discipline in 2A; 3B `start_phase='Build'` + remaining Base = 0 weeks → `skill_acquisition_infeasible` | `Layer4ShapeInfeasibleError(class='skill_acquisition_infeasible', ...)` raised | §6.4, §10.2 |
| **TS-13** | 2D excludes every available compound lift (severe shoulder + wrist injury); strength sessions have no exercise pool → `cumulative_load_injury_infeasible` | `Layer4ShapeInfeasibleError(class='cumulative_load_injury_infeasible', ...)` raised | §6.4, §10.2 |
| **TS-14** | Pattern A first-pass validator fails on Build phase ACWR (1.42 forward-projected > 1.4 blocker); single retry with RuleFailure context fixes the over-ramp; second pass accepts | `phases[1].synthesis_metadata.retries_used=1`, `cap_hit=False`; `validator_results` has 2 entries; last has `accepted=True` | §5.4 `acwr_*`, §5.5 |
| **TS-15** | Same as TS-14 but BOTH retries hit ACWR blocker; cap exhausted; best-effort accepted | `phases[1].synthesis_metadata.retries_used=2`, `cap_hit=True`; `validator_results` last entry has `accepted=True` with demoted-to-warning failures; `Observation(category='best_effort_plan', elevates_to_hitl=True)` | §5.5, §8.7 |
| **TS-16** | Pattern A, Build→Peak seam reviewer verdict `flagged_major` + `re_prompt_next`; Peak's retry budget unused; one re-synthesis; second seam review verdict `approved` | `seam_reviews` has 2 entries for that seam (initial + re-review); `triggered_resynthesis=True`; `re_prompted_phase_name='Peak'`; final verdict `approved` | §6.2, §7.7 |
| **TS-17** | Same as TS-16 but second seam review still `flagged_major` | `seam_reviews` 2 entries; second still flagged; `Observation(category='seam_unresolved', elevates_to_hitl=True)` | §6.2 per-seam cap, §8.7 |
| **TS-18** | Pattern A, seam reviewer verdict `flagged_major` + `re_prompt_prior`; prior phase's retry budget exhausted | `SeamReview.triggered_resynthesis=False`; `Observation(category='seam_unresolved', elevates_to_hitl=True)`; `seam_issues` text recorded but not acted on | §6.2 seam/validator-retry interaction |
| **TS-19** | Pattern A, seam reviewer verdict `patched` + `accept_with_observation` — invalid combination per §6.2 | `Layer4OutputError('seam_reviewer_invalid_verdict_combination')` first time → one schema retry → if second time still invalid, raise + bail | §6.2 invalid combination, §5.5 |
| **TS-20** | Pattern A `plan_create`, all 4 phases synthesize cleanly + all 3 seams approve + final cross-phase validator passes → ideal happy path | `pattern='A'`, validator_results len=1 with `accepted=True`, `notable_observations` empty (no warnings/data_gaps), no retries | All §§5–7 contracts on happy path |
| **TS-21** | Single-phase Pattern A: `start_phase='Taper'` + 3-week event window | `phase_structure.phases` len=1; `seam_reviews == []` (empty list, not None); no seam reviewer LLM call fires; `pattern='A'` | §10.1 degenerate timeline, §6.5 |

### 13.3 `plan_refresh` scenarios

| TS | Inputs | Expected outputs | Contracts exercised |
|---|---|---|---|
| **TS-22** | T1 refresh: Andy's plan day 14; `parsed_intent.mode='softer'` ("I'm tired today"); scope = next 2 days | Pattern B; single LLM call; 2 sessions output with intensity reduced one notch from prior plan; `intensity_modulated` LLM-flag on each modified session; corresponding observation | §3.2, §5.3, §8.6 |
| **TS-23** | T2 refresh: athlete edited §K to drop Wednesday availability; scope = next 7 days; 3A re-eval shows no other changes | Pattern B; 1 LLM call; 7 sessions; Wednesday session removed/redistributed; remaining days adjusted to fit 2A bands | §3.2, §5.3, §5.4 `schedule_violation_*` |
| **TS-24** | T3 refresh intra-phase: athlete mid-Build with 6 Build weeks remaining; T3 scope = next 28 days (all within Build); `parsed_intent.mode='harder'` | Pattern B (single-phase T3 per §5.1 routing); validator passes; ACWR forward projection nears but does not breach upper threshold | §3.2, §5.1 routing, §6.3 |
| **TS-25** | T3 refresh cross-phase: athlete last week of Build; T3 scope crosses Build→Peak | Pattern A on affected phases (Build remainder + Peak start); 1 seam reviewed; out-of-scope prior sessions retain their `plan_version_id` per D-64 §6.3 | §3.2, §5.1, §6.3, §6.5 |
| **TS-26** | T2 refresh with 3B re-eval shifting `start_phase` from Build → Peak inside the refresh window | Pattern A activates on T2 (per §10.3 refresh-crosses-3B-shifted-start_phase); plan rebuilds against new phase structure | §10.3, §5.1 |
| **TS-27** | T1 refresh with empty `prior_plan_session_window` (no prior plan covers the scope) | `Layer4InputError('prior_plan_window_empty')` | §4.3 |
| **TS-28** | T3 refresh whose `refresh_scope_start` predates `phase_structure.phases[0].start_date` (e.g., athlete started at Build but T3 covers a date before Build started) | `Layer4InputError('refresh_predates_start_phase')` | §6.5, §10.3 |
| **TS-29** | T3 refresh where prior plan was Pattern B (T2-generated); prior `PlanSession.phase_metadata` is None | Layer 4 reconstructs `phase_metadata` from current 3B for the refresh scope; out-of-scope sessions retain their (None) phase_metadata | §10.3, §7.12 |
| **TS-30** | T3 refresh with prior session referencing a discipline no longer in 2A `discipline_inclusion`, no `intensity_modulated`/`shape_override` rationale on that session | `Layer4InputError('prior_session_orphaned')` | §4.3, §10.3 |
| **TS-31** | T2 refresh with `parsed_intent=None` (athlete refreshed without NL text, e.g., onboarding "regenerate" button or D-64 §5.4 parser unavailable) | Pattern B runs; synthesizer prompt receives the no-intent variant; produces plan refresh without NL-driven modifications | §3.2 `parsed_intent` None path |
| **TS-32** | T1 refresh; `parsed_intent` says "make Wednesday harder" but Wednesday's intensification blows ACWR to 1.45; validator fails; retry reconciles by softening other days | Single retry; final pass accepts with mixed-direction intensity adjustments; `intensity_modulated` flag on affected sessions | §5.4 acwr, §5.5, §10.3 |

### 13.4 `single_session_synthesize` scenarios

| TS | Inputs | Expected outputs | Contracts exercised |
|---|---|---|---|
| **TS-33** | Andy: D-63 request for MTB at home gym (no bike per locale's equipment view) | Returns `Layer4Payload` with `len(sessions)==1`, error session (`kind='rest'`, `rest_reason='athlete_unavailable'`), `Observation(category='sport_unavailable_at_locale', ...)`; `is_ad_hoc=True`; `suggestion_id` populated | §3.3, §10.4, D-63 §6.3 |
| **TS-34** | Andy: D-63 strength session at hotel gym; wrist injury active | Returns one strength session; wrist-extension-loaded exercises excluded via 2D; Tier-2 substitutes appear in `StrengthExercise.substitute_text` | §3.3, §5.4 `injury_violation_*` |
| **TS-35** | Andy: D-63 `intensity='hard'` but 3A shows yesterday was hard + elevated ACWR | Synthesizer modulates intensity to `moderate`; `coaching_flags=['intensity_modulated']` LLM-emitted; `Observation(category='intensity_modulated', elevates_to_hitl=False)` auto-emitted | §3.3, §8.6, §8.7, D-63 §6.2 |
| **TS-36** | D-63 with `locale_slug=None` AND `quick_equipment=[]` | `Layer4InputError('locale_and_quick_equipment_both_unset')` | §4.4 |
| **TS-37** | D-63 with `locale_slug='home_gym'` AND `quick_equipment=['dumbbells','bench']` (both set) | `Layer4InputError('locale_and_quick_equipment_both_set')` | §4.4 |
| **TS-38** | D-63 `duration_min=400` (out of [30, 360] range) | `Layer4InputError('duration_out_of_range')` | §4.4 |
| **TS-39** | D-63 happy path: athlete picks "run, 60 min, easy" at home base locale; no injuries; cache miss | Returns 1 cardio session, `is_ad_hoc=True`, validator passes minimal checks, suggestion_id populated, latency ~3s | §3.3, §5.3 (single-session validator scope), §5.4 |
| **TS-40** | D-63 second fire same day with byte-identical request | Cache hit per §9.4; same session body returned with new `suggestion_id` rebound; no LLM call | §9.4 rebinding, §9.1 single-session cache key |

### 13.5 `race_week_brief` scenarios

| TS | Inputs | Expected outputs | Contracts exercised |
|---|---|---|---|
| **TS-41** | Andy: 14 days before Pocket Gopher Extreme; `race_format='expedition_ar'`; full Taper phase + 2E race-day fueling tier present | `mode='race_week_brief'`, `pattern='B'`, `race_week_brief` non-None, `race_plan` non-None (multi-day event); Taper-phase sessions modified with race-week flags (`race_rehearsal`, `fueling_practice`, etc. per §8.5); `RacePlan.segments` chronologically ordered; `kit_manifest` populated from 2C | §3.4, §7.13, §7.14, §8.5 |
| **TS-42** | Marathon athlete, 10 days before event, `race_format='single_day'` | `race_plan is None`; `race_week_brief` includes single-day-event fields only; Taper sessions get flags | §3.4, §7.12 race_plan rule |
| **TS-43** | Race-week brief fires at `days_to_event=20` (out of window) | `Layer4InputError('race_week_brief_too_early')` | §4.5, §10.5 |
| **TS-44** | Race-week brief for `race_format='single_day'` but caller's `layer3b_payload.mode='open-ended'` | `Layer4InputError('race_week_brief_requires_event_mode')` | §3.4, §4.5 |
| **TS-45** | Multi-day event with empty `equipment_overrides` on every locale → soft `kit_manifest_inputs_incomplete` | Brief produced; `kit_manifest` items are free-text (not layer0-resolved); `Observation(category='data_gap', text='kit manifest synthesized from free-text', elevates_to_hitl=False)` | §4.5, §10.5 |
| **TS-46** | Race-week brief cache miss at noon UTC; same call fires again at 23:59 UTC same day | Cache hit (same `days_to_event`); byte-identical brief returned (no rebind needed — `plan_version_id` unchanged) | §9.1, §9.4 |
| **TS-47** | Race-week brief cached at 23:59 UTC; same call fires at 00:01 UTC next day | Cache miss per §9.3 midnight-UTC rollover; fresh synthesis; `days_to_event` decremented | §9.3, §10.5 |
| **TS-48** | Race-week brief with no Taper-phase sessions in window (athlete still in Peak per phase_structure but 14 days from event) | Brief produced; Taper flags applied to available sessions; `data_gap` observation: "still in Peak with 14 days to event" | §10.5 |

### 13.6 Coaching-flag emit scenarios

Each row exercises one spec-auto-emit trigger from §§8.2–8.6 + the LLM-emitted exception in §8.7.

| TS | Trigger | Expected flag | Kind |
|---|---|---|---|
| **TS-49** | Newly-included discipline in 2A on `plan_create` | `first_introduction_to_<discipline>` on first session for that discipline | Spec-auto |
| **TS-50** | Base-phase cardio session | `aerobic_base_focus` | Spec-auto |
| **TS-51** | 3A `data_density='sparse'` + Base ramp week | `volume_ramp_conservative` on every cardio session in week | Spec-auto |
| **TS-52** | Synthesizer prescribes long-run/ride/swim cornerstone session (LLM-emitted) | `long_slow_distance` on the session | LLM-emitted |
| **TS-53** | Session is on next §K-available day after a `long_slow_distance` session | `recovery_day_after_long` (spec-auto follow-on) | Spec-auto |
| **TS-54** | Build phase, ACWR forward proj = 1.27 (just past 1.25 threshold; under 1.4 blocker) | `volume_ramp_aggressive` on every cardio session in week | Spec-auto |
| **TS-55** | Build phase, synthesizer prescribes weak-link strength accessory work | `weak_link_targeted` (LLM-emitted) on the strength session | LLM-emitted |
| **TS-56** | Peak phase, synthesizer prescribes race-target-pace intervals | `race_pace_specific` (LLM-emitted) | LLM-emitted |
| **TS-57** | Tune-up event in §H.2 falls inside Peak | `tune_up_race` on the nearest session (spec-auto) | Spec-auto |
| **TS-58** | Peak's highest-weekly-volume week | `peak_volume_marker` on every session in that week | Spec-auto |
| **TS-59** | Race-day session (`PlanSession.date == event_date`) | `race_day` | Spec-auto |
| **TS-60** | Periodic deload week (every 4th week in standard mode) | `recovery_week` on every session | Spec-auto |
| **TS-61** | Taper, `days_to_event ≤ 14`, long session | `race_rehearsal` | Spec-auto |
| **TS-62** | Taper, `days_to_event == 7`, light session | `kit_check` | Spec-auto |
| **TS-63** | Taper, `days_to_event ∈ [3,5]`, moderate run/ride | `pacing_lock` | Spec-auto |
| **TS-64** | Synthesizer emits `coaching_flags=['some_undefined_flag']` | Caught by validator as `unknown_coaching_flag_<name>` (`blocker`); one schema retry; bail on second failure | §8.1 closed-set, §5.5 |
| **TS-65** | Orchestrator regression: spec-auto-emit trigger met but flag missing from session post-synthesis | `RuleFailure(rule_name='coaching_flag_missing_<flag>', severity='blocker')` from defensive validator | §8.1 |
| **TS-66** | Synthesizer emits `Observation(category='opportunity', text='consider adding a technical skill session')` directly | Pass-through; orchestrator does NOT compute or block; observation lands in `Layer4Payload.notable_observations` as-emitted | §8.7 LLM-emitted exception |

### 13.7 Cache hit/miss scenarios

| TS | Trigger | Expected behavior | Contracts |
|---|---|---|---|
| **TS-67** | `plan_create` with byte-identical inputs to a prior successful call; cache populated | Hit; `plan_version_id` rebound to call's new ID; all `PlanSession.plan_version_id` overwritten; no LLM call; latency <50ms | §9.1, §9.4 |
| **TS-68** | `plan_create` cache hit then concurrent second call with same inputs (race condition) | Both return same body; each rebinds to its own `plan_version_id`; second-to-commit supersedes first via D-64 §6.2 | §9.4, §10.6 |
| **TS-69** | Pattern A `plan_create`: phase 0 hits cache; phase 1 misses (chain dependency unchanged but retry context different on second pass) | Phase 0 not re-synthesized; phase 1 fresh synthesis; phase 2+ recompute cache key against new prior-phase hash | §9.2, §10.6 |
| **TS-70** | Pattern A: phase 0 + phase 1 both hit cache; seam 0→1 flagged_major + re_prompt_prior; phase 0 re-synthesized with seam-issues constraint context → new `phase_key[0]` misses cache | Cache misses on re-prompt; phase 1's `phase_key[1]` recomputes (depends on new phase 0 hash) → misses; downstream phases re-synthesize | §6.2, §9.2, §10.6 |
| **TS-71** | Cache populated; Layer 2A re-runs (etl_version_set bumps); next Layer 4 call | Orchestrator-side eviction per §9.3 invalidates cache; Layer 4 call is a miss | §9.3 |
| **TS-72** | Cache populated; tunable bump (e.g., `temperature` raised from 0.2 to 0.3); next call | Cache miss (key includes `temperature`); fresh synthesis | §9.3 |
| **TS-73** | T1 refresh cache hit; same athlete fires `single_session_synthesize` with byte-identical D-63 request — keys differ (different entry_point key formula); both cached independently | Both hits work; cross-entry-point cache contamination impossible (key formula differences) | §9.1 |
| **TS-74** | Orchestrator regression: fails to evict cache when Layer 3A re-runs; stale cache hit | Layer 4 returns stale cached payload; `Layer4Payload.etl_version_set` reflects old version set; orchestrator should detect via §10.6 defense | §10.6 "cache hit serves stale upstream payload" |

### 13.8 Edge-case scenarios (cross-reference §10)

| TS | Edge case | §10 reference |
|---|---|---|
| **TS-75** | All §K days marked unavailable → `schedule_volume_infeasible` per §10.2 | §10.10, §10.2 |
| **TS-76** | Open-ended-mode athlete at horizon decay (10 weeks into 12-week plan); T3 refresh extends beyond original horizon | §10.1 |
| **TS-77** | Event 9 months out (`time_to_event_weeks=39`); long-horizon Pattern A | §10.10 |
| **TS-78** | Zero historical training data + plan_create + `start_phase != 'Base'` → shape_override force-Base | §10.10, §6.4 row 4 |
| **TS-79** | `event_date` falls on §K-unavailable day | §10.10 race-day-overrides-schedule |
| **TS-80** | 3B `suggested_adjustments` contradicts validator (suggests drop discipline; plan-without-discipline fails 2A coverage) | §10.10 — suggestions are advisory only |
| **TS-81** | `etl_version_set` mismatch between two upstream payloads | §10.8 |
| **TS-82** | Stale `layer3a_payload` (created_at before recent 3A re-eval timestamp) | §10.8 |
| **TS-83** | Joint session day on refresh boundary (Layer 4.5 territory) | §10.9 — Layer 4 produces solo session; ignores §L |
| **TS-84** | `prior_plan_session_window` orphaned: retired discipline reference without override rationale | §10.3, §10.10 |

### 13.9 Smoke tests for production

A handful of end-to-end happy-path scenarios that should always pass in CI / staging. If these regress, deploy is blocked.

| TS | Scope |
|---|---|
| **TS-S1** | TS-1 (Andy's actual case) end-to-end with mocked LLM fixture; full Pattern A flow; payload schema validation; serialization round-trip |
| **TS-S2** | TS-22 (T1 refresh "I'm tired") end-to-end with mocked LLM fixture; Pattern B; intensity modulation |
| **TS-S3** | TS-39 (D-63 happy path) end-to-end; single-session synthesis; suggestion_id round-trip |
| **TS-S4** | TS-41 (race-week brief Andy's case) end-to-end; multi-day RacePlan generation; kit_manifest population from 2C |
| **TS-S5** | TS-20 (plan_create ideal happy path) end-to-end; all 4 phases approve first-pass; no observations |

### 13.10 Coverage gaps tracked forward

- **Live-LLM integration tests** (no mock fixture; real Anthropic API calls) — gated to a separate test suite tagged `slow + costs_money`; runs on release candidate branches only.
- **Multi-athlete joint session tests** — out of v1; lands with Layer 4.5 spec + implementation.
- **Garmin-data-flowing integration tests** — D-55 paused; tests gated on D-55 reopening.
- **Cost telemetry assertions** — once orchestrator-side cost tracking is implemented, add per-TS cost-ceiling assertions per §11.5.
- **Per-prompt-body regression tests** — gated on prompt-body design landing (stop-and-ask trigger #2; deferred to its own spec session per §12).

## 14. Gut check — to be drafted in a later session

End-of-spec retrospective per the 14-section template. Topics expected to land: what this spec gets right (the discriminated-union session shape collapses 3 downstream consumer paths into 1; the per-phase + seam-reviewer architecture matches the coaching intuition that seams are where periodization actually goes wrong; three entry points keep the expensive Pattern A out of the cheap-call paths); risks (per-phase decomposition may exhibit the same dependency-on-prior-phase coupling that makes parallelism impossible; the seam reviewer's verdict authority is the single most likely place to over-spec or under-spec; cost is real and unmeasured; intensity-distribution defaults across phases are policy not data); what might be missing (joint sessions, Layer 5 consumption contract, the prompt bodies themselves); best argument against this spec's scope (the three-entry-point shape is a complexity multiplier; a unified entry point with a `mode` discriminator would be simpler if the per-mode prompts can be parameterized; counter — Andy explicitly picked separate functions per Decision 2, and the prompts ARE the per-mode complexity that separation makes inspectable).

---

*End of Layer 4 spec draft v1 (session 4 of expected 3–5). Sections drafted after session 4: §§1–9 unchanged from session 3 close. **§10 Edge cases** (10 subsections covering degenerate timelines, shape-infeasibility detection algorithms for the four `Layer4ShapeInfeasibleError` classes, refresh edge cases, D-63 single-session, race-week brief, cache + concurrency, validator + retry, ETL + version drift, Layer-4.5-boundary cases, misc catch-all). **§11 Performance budget** (8 subsections: latency targets per entry point, token budgets, cost per invocation, cache hit-rate assumptions + amortized cost, cumulative ceilings, frequency-cap interaction, concurrency assumptions, performance-regression detection thresholds). **§13 Test scenarios** (84 numbered TS rows organized by entry point + coaching-flag emit + cache + edge-case categories + 5 smoke tests gating CI + coverage gaps tracked forward). §§12 + §14 remain stubbed for session 5. Next session: §12 open-items maintenance + §14 gut check + end-of-arc CLAUDE.md/backlog bump + PR. No new source decisions this session.*
