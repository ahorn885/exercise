# Layer 4 Per-Phase Synthesizer Prompt — v2

**Status:** Surgical amendment of `Layer4_PerPhase_v1.md` (2026-05-16). Shipped 2026-05-18 paired with Layer 4 implementation Step 4f (`llm_layer4_plan_create` Pattern A orchestration). v1 retained as in-project history per Rule #12 — the v1 file's coaching policy and §6 user-prompt template carry over unchanged; v2 documents the additive surface-area changes inline.

**Predecessor:** `Layer4_PerPhase_v1.md` (2026-05-16).

**Companion implementation:** `layer4/per_phase.py` (`build_record_phase_sessions_tool()` + `render_user_prompt()` + `synthesize_phase()` + `_default_llm_caller()`) + `layer4/plan_create.py` (`llm_layer4_plan_create()` + `synthesize_pattern_a_for_refresh()`).

**Companion spec sections:** `Layer4_Spec.md` §3.1 (entry-point signature), §4.2 (input validation), §5.1 (pattern routing — A always), §5.2 (Pattern A algorithm), §5.5 (capped retry shared across validator-driven + seam-driven re-syntheses), §6.1 (phase boundary computation), §6.2 (β propose-patch authority), §6.3 (T3 cross-phase routing).

---

## v2 changes summary

Three contract-amendment ripples land in v2 (paired with implementation Step 4f):

1. **D1 typed `IntensityTarget` union (2026-05-17 D1 amendment):** v1's §4 tool schema referenced `cardio_blocks[].intensity_target` as a free-shape dict. v2 surfaces the typed 9-shape `oneOf` union per `Layer4_Spec.md` §7.3.1 — `HRTarget` / `PowerTarget` / `PaceTarget` / `SwimPaceTarget` / `RPETarget` / `VerticalRateTarget` / `StrokeRateTarget` / `CadenceTarget` / `ClimbingGradeTarget`. Implementation in `layer4/per_phase.py:_intensity_target_schema()` mirrors single_session.py / plan_refresh.py / race_week_brief.py.

2. **PR-C-followon injury source-pointer (2026-05-17):** v1 §3.3 `active_injuries` referenced `Layer3APayload.current_state.active_injuries` which never existed in 3A's typed contract. The canonical injury source is `Layer2DPayload.excluded_exercises` + `Layer2DPayload.accommodated_exercises` per `Layer4_Spec.md` §3.2 line 753 (amended 2026-05-17) and the PR-C-followon `AccommodationModality` framework. v2's §3.3 input row reads from 2D. Driver `_format_active_injuries()` renders excluded + accommodated lists with per-modality `modality_type` summary.

3. **D-66 `RaceEventPayload` (2026-05-18):** v1 §3.4 referenced `race_format` + `event_date` + `event_locale` as scalar inputs. v2 adds the typed `RaceEventPayload` (per `Race_Events_D66_Design_v1.md` §4) as the source-of-truth — open-ended plans pass None; event-mode plans pass the structured `RaceEventPayload` with `race_format` + `event_date` + optional `route_locales[]` structured graph. Driver `_format_route_locales()` renders the sequenced graph (start / transition_area / aid_station / drop_bag_point / bivvy / finish) when present.

**System prompt + §6 user-prompt template structure + §5 voice + §7 sampling — unchanged from v1.** Only the typed-input / tool-schema surface evolves.

---

## v2 source decisions (delta from v1's D1–D10)

| # | Decision | Choice | Notes |
|---|---|---|---|
| D11 | Tool-schema fidelity | Full PlanSession contract mirror (Step 4a Option 2 precedent) | Same as v1 — re-affirmed; the contract surface now includes the typed IntensityTarget union. |
| D12 | `IntensityTarget` typing | 9-shape `oneOf` per `layer4/payload.py` §7.3.1 (D1 amendment) | v1 had free-shape dict at the `intensity_target` slot; v2 narrows to the 9 typed shapes per CardioBlock. Smart-union dispatch at parse time. |
| D13 | `active_injury_summary` source | `Layer2DPayload.excluded_exercises` + `accommodated_exercises` (PR-C-followon canonical) | v1 referenced non-existent 3A field; v2 corrects. Renderer surfaces per-modality `modality_type` summary for accommodated entries. |
| D14 | D-66 `RaceEventPayload` integration | `race_event_payload: RaceEventPayload \| None` input; None for open-ended | v1 had scalar `race_format` + `event_date` + `event_locale`; v2 adds the typed payload + route_locales structured graph. Open-ended plans (no event) pass None and prompt instructs no `race_pace_specific` flag. |
| D15 | `phase_synthesis_notes` JSONB target | Same as v1 (~600 char rationale; lands in `plan_versions.notes` JSONB) | Re-affirmed. |
| D16 | Driver-level `phase_metadata` fill | Orchestrator fills `SessionPhaseMetadata` from `PhaseSpec` after parse (§7.5) | v1 left ambiguous; v2 clarifies — `per_phase._build_session_phase_metadata()` computes `week_in_phase` from session_date + phase_start_date. |

D1–D10 from v1 carry forward unchanged: tool-use mechanism (D1), extended thinking ~5000 tokens (D2), hybrid input format (D3), hybrid prior-phase rendering (D4), closed-set 6-flag enum (D5; `intensity_modulated` excluded from per-phase per §8.6/§8.7 — that flag fires on refresh/single-session paths, not plan_create), deload-cadence anchors (D6), Taper-length anchors per race format (D7), hybrid `RuleFailure` retry context (D8), schema length caps (D9; 240/200/240/600 chars), file location (D10).

---

## §3 input contract — v2 amendments

### §3.3 Athlete context (Layers 1, 3A, 2D) — v2 amendment

| Variable | Type | Source | v2 amendment |
|---|---|---|---|
| `active_injury_summary` | list[str] | `Layer2DPayload.excluded_exercises` + `Layer2DPayload.accommodated_exercises` | v1 referenced `3A.active_injuries`; v2 corrects to 2D canonical source. Rendered as "- EXCLUDE {exercise_id} ({exercise_name})" + "- ACCOMMODATE {exercise_id} ({modality_type_list})" lines per `per_phase._format_active_injuries()`. |
| `accommodation_modalities` | list[`AccommodationModality`] (per-exercise) | `Layer2DPayload.accommodated_exercises[].accommodations` | NEW v2 row. The 6-variant modality framework (volume / intensity / tempo / loading-type / frequency / substitution) per `Layer2D_Spec.md` §5.3.6. Renderer emits the `modality_type` enum compactly; full parameters surfaced only when load-bearing for the prescribed exercise. |

### §3.4 Race + locale + equipment context — v2 amendment

| Variable | Type | Source | v2 amendment |
|---|---|---|---|
| `race_event_payload` | `RaceEventPayload \| None` | D-66 caller-supplied (orchestrator joins from `race_events WHERE is_target_event=true`) | NEW v2 row replacing v1's scalar `race_format` + `event_date` + `event_locale`. Open-ended plans pass None. When non-None: drives Taper anchor selection + `race_pace_specific` flag eligibility (Peak phase only when race_event_payload non-None). |
| `race_event_payload.route_locales` | list[`RouteLocale`] | D-66 structured graph (sequence_idx + role + name + mile_marker) | v2 NEW. Sequenced anchor locales (start / transition_area / aid_station / drop_bag_point / bivvy / finish). Per-phase synth reads but is not the primary consumer (that's race-week-brief per Step 4e); informs the per-phase coaching context for multi-day events. |

v1 §3.4 scalar rows for `race_format` / `event_date` / `event_locale` retired in favor of the typed `RaceEventPayload`. Driver code `per_phase._format_route_locales()` renders the structured graph when present.

---

## §4 tool schema — v2 surgical amendments

The `record_phase_sessions` tool definition lives in `layer4/per_phase.py:build_record_phase_sessions_tool()`. v2 changes the inline schema in two places:

### §4.1 `cardio_blocks[].intensity_target` — typed `oneOf` (D1 amendment fidelity)

v1 fragment (free-shape):
```json
"intensity_target": {"type": "object"}
```

v2 (9-shape `oneOf` per `Layer4_Spec.md` §7.3.1):
```json
"intensity_target": {
  "oneOf": [
    {"type": "object", "required": ["hr_bpm_low", "hr_bpm_high"], "properties": {...}},
    {"type": "object", "required": ["power_w_low", "power_w_high"], "properties": {...}},
    {"type": "object", "required": ["pace_per_km_low", "pace_per_km_high"], "properties": {...}},
    {"type": "object", "required": ["pace_per_100m_low", "pace_per_100m_high"], "properties": {...}},
    {"type": "object", "required": ["rpe_low", "rpe_high"], "properties": {...}},
    {"type": "object", "required": ["vert_m_per_hr_low", "vert_m_per_hr_high"], "properties": {...}},
    {"type": "object", "required": ["strokes_per_min_low", "strokes_per_min_high"], "properties": {...}},
    {"type": "object", "required": ["rpm_low", "rpm_high"], "properties": {...}},
    {"type": "object", "required": ["grade_system", "grade_min", "grade_max"], "properties": {...}}
  ]
}
```

See `layer4/per_phase.py:_intensity_target_schema()` for the verbatim shape definitions. Same union used across single_session / plan_refresh / race_week_brief / per_phase tool schemas.

### §4.2 `coaching_flags` closed set — 6 LLM-emittable flags (v2 confirms D5)

```json
"coaching_flags": {
  "type": "array",
  "items": {"type": "string", "enum": [
    "technique_emphasis",
    "long_slow_distance",
    "weak_link_targeted",
    "overreach_test",
    "discipline_specific_intensity",
    "race_pace_specific"
  ]},
  "maxItems": 6,
  "uniqueItems": true
}
```

`intensity_modulated` is NOT in this enum (per `Layer4_Spec.md` §8.6/§8.7 broadening — fires on refresh/single-session paths, not plan_create where there's no athlete-intent surface to deviate from). Spec-auto flags (`recovery_week`, `peak_volume_marker`, `race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) are orchestrator-stamped post-synthesis per §8.1; never LLM-emitted; not in the enum.

---

## §5 system prompt — unchanged from v1

The system prompt's coaching policy (intent + magnitude grounding, intensity modulation tiers, race-pace eligibility, deload cadence, Taper anchors, equipment respect, schedule respect, output discipline) lives verbatim in `layer4/per_phase.py:SYSTEM_PROMPT`. v2 adds inline guidance for the v2 input contract changes (race_event_payload presence/absence, 2D-sourced injury exclusions, accommodation modality respect) but the coaching tiers, voice, and policy are unchanged from v1's §5.

The single new policy line in v2's system prompt: "Open-ended mode (race_event_payload is None): use the open-ended 12-week horizon default; do not emit `race_pace_specific`." (v1 framed this as "open_ended" string check on the deprecated scalar `race_format`.)

---

## §6 user-prompt template — unchanged structure; minor variable renames

The §6 user prompt template structure (Phase + plan context block → Prior-phase continuity → Athlete context → Race + locale + equipment → Schedule → Retry context → Output instruction) is unchanged from v1. Variable rename:

- `active_injuries` → `active_injury_summary` (sourced from 2D excluded/accommodated lists per v2 §3.3)
- `race_format` (scalar) → `race_event_payload.race_format` (typed payload field; rendered alongside the structured route_locales graph)

Driver code `layer4/per_phase.py:render_user_prompt()` does the inline Python rendering; no template engine.

---

## §7 sampling — unchanged from v1

`DEFAULT_MAX_TOKENS=4000` + `DEFAULT_EXTENDED_THINKING_BUDGET=5000` + temperature 0.2 (carried from `Layer4_Spec.md` §3.1 defaults). v1's D2 (max-defensive thinking budget) remains v2's posture.

---

## §§8–14 — carry over from v1 unchanged

- §8 authority bounds (recap) — v1 verbatim.
- §9 verdict calibration — N/A (per-phase synth has no verdict; that's seam-reviewer scope).
- §10 `seam_issues` writing rules — N/A.
- §11 edge cases — v1 verbatim.
- §12 test scenarios (PPS-prefix) — v1 verbatim.
- §13 open items — v1 verbatim.
- §14 gut check — v1 verbatim.

---

## Implementation references (Step 4f)

- `layer4/per_phase.py` — `synthesize_phase()` is the per-phase synthesis call site (one phase per invocation; validator-driven and seam-driven retries share the per-phase budget per §5.5 + §6.2).
- `layer4/plan_create.py` — `llm_layer4_plan_create()` Pattern A orchestrator + `synthesize_pattern_a_for_refresh()` shared engine (T3 cross-phase consumes this per §6.3).
- `tests/test_layer4_plan_create.py` — coverage of tool schema + §4.2 input validation + entry-point happy path + seam-review orchestration + Layer4Payload composition + prompt rendering.

---

*End of Layer 4 Per-Phase Synthesizer Prompt v2.*
