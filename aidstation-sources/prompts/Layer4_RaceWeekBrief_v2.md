# Layer 4 — Race-Week Brief Synthesizer Prompt Body

**Prompt name:** `Layer4_RaceWeekBrief`
**Entry point:** `llm_layer4_race_week_brief` (`Layer4_Spec.md` §3.4)
**Pattern:** B (single LLM call + deterministic validator; no seam reviewer; no phase decomposition — Taper window is ≤ 1 phase per §5.1)
**Caller:** Orchestrator-triggered when `days_to_event ≤ 14`, OR athlete-triggered via the dedicated race-week-brief surface
**Status:** v2 — D-66 paired amendment (Step 4e implementation pairing 2026-05-18)
**Date:** 2026-05-18 (v2); 2026-05-17 (v1 base)
**Position in arc:** Fifth and last of 5 prompt bodies (after `Layer4_SeamReviewer_v1.md`, `Layer4_PerPhase_v1.md`, `Layer4_SingleSession_v2.md`, `Layer4_RefreshT1_v2.md` + `Layer4_RefreshT2_v1.md` + `Layer4_RefreshT3_v1.md`).
**v2 changes:** (1) §3.1 source pointers for `race_rules_summary` + `mandatory_gear_text` + race-route locale list updated from Layer 1 §H.2 to `race_event_payload` per D-66 (paired `Layer4_Spec.md` §3.4 amendment); (2) NEW §3.11 "Route locales (D-66 structured graph)" describing the typed `RaceEventPayload.route_locales[]` input — replaces the v1 flat `event.locales[]` for multi-day events; (3) §4.1 tool schema `pacing_target` (per-`RaceSegment`) updated from pre-D1 free-shape dict to typed `IntensityTarget` 9-shape `oneOf` union per `Layer4_Spec.md` §7.3.1 (Step 4a-precedent fidelity); (4) §4.1 tool schema `kit_manifest[].layer0_canonical: bool` field surfaced (paired `Layer4_Spec.md` §7.13 amendment 2026-05-18); (5) §6 user prompt template gains a new "Route locales" rendering block that interpolates the structured `RaceEventPayload.route_locales[]` with role + sequence_idx + per-locale equipment items. All v1 §§1–2 + §§5 system prompt + §§7–14 carry over unchanged; v1 coaching policy + Taper-session modulation tiers + race-week brief synthesis policy + race plan synthesis policy + iteration discipline + output discipline are unaffected.

This v2 file documents the surgical amendments to v1. **Sections explicitly shown below replace the corresponding v1 sections.** Sections not shown below are unchanged from v1 — read `Layer4_RaceWeekBrief_v1.md` for those (v1 retained as in-project history per Rule #12).

---

## Source decisions (v2 amendments — paired Step 4e implementation 2026-05-18)

The v1 source-decision table D1–D13 stays in force. v2 adds two new rows:

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D14 (v2 2026-05-18) | D-66 race-event data model integration | **Source `race_rules_summary` + `mandatory_gear_text` + structured `route_locales[]` graph from the new `RaceEventPayload` typed contract per `Race_Events_D66_Design_v1.md` §4.** Replaces v1's source pointer to Layer 1 §H.2 free-text fields. Route locales render structurally per role + sequence_idx + per-locale equipment in §6. | Andy 2026-05-18 D-66 design wave Pick 4 (new `race_event_payload: RaceEventPayload` arg on §3.4). Layer 4 §3.4 amendment is the paired contract change; this prompt body's §3 source pointers update to match. Layer 1 §H.2 free-text columns are deprecated per `Race_Events_D66_Design_v1.md` §3.4. |
| D15 (v2 2026-05-18) | `pacing_target` typed IntensityTarget union | **Replace pre-D1 free-shape `pacing_target` in §4.1 tool schema with the typed 9-shape `IntensityTarget` `oneOf` union per `Layer4_Spec.md` §7.3.1.** Same union the per-segment `RaceSegment.pacing_target` field consumes in `payload.py`; same union used by single-session synthesizer's `intensity_target`. | Step 4a precedent (Andy 2026-05-17 Option 2 — full payload-contract mirror). v1 sketched `pacing_target` as free-shape `{'zone': ..., 'measure': ..., 'low': ..., 'high': ...}` pre-D1; D1 amendment landed 2026-05-17 narrowing IntensityTarget to a closed v1 set of 9 typed shapes. Updating tool schema to the typed union closes the v1 reconciliation gap. |
| D16 (v2 2026-05-18) | KitItem.layer0_canonical field surfaced | **Tool schema includes `kit_manifest[].layer0_canonical: bool` per the paired `Layer4_Spec.md` §7.13 amendment 2026-05-18 adding the field to `KitItem`.** Default `false`; `true` when synthesizer-emitted `item` matches a `layer0.equipment_items.canonical_name`. Validator rule 13 (canonical-name check per §4 cross-output schema rules) becomes evaluable. | v1 §4.1 already sketched the field but the typed `KitItem` model in `payload.py` lacked it; v2 closes the contract gap by amending §7.13 + landing the field on the typed contract. |

**Companion contract sections (`Layer4_Spec.md`):** All v1 references stay valid + §3.4 D-66 amendment 2026-05-18 (new `race_event_payload: RaceEventPayload` positional arg) + §4.5 D-66 amendment 2026-05-18 (2 new precondition rows `race_event_payload_missing` + `race_event_date_mismatch_3b` + §K → §H.4 source-pointer fix on row 9 + D-66-active rebinding of `kit_manifest_inputs_incomplete`) + §5.4 D-66 amendment 2026-05-18 (rule body rebinding: 3 outcomes — skip on single_day/None, emit `_no_route_locales`, emit `_no_route_locale_equipment`) + §7.13 D-66 paired amendment 2026-05-18 (KitItem.layer0_canonical field).

---

## v2 amendments inline

### 3. Inputs (template variables) — §3.1 source-pointer updates

The §3.1 Event metadata table is amended as follows (changed rows shown; unchanged rows omitted — see v1 §3.1 for the full table):

| Variable | Source | Notes |
|---|---|---|
| `event.race_rules_summary` | **`race_event_payload.race_rules_summary` (D-66 amendment 2026-05-18; v1 pointed to Layer 1 §H.2)** | Mandatory-gear list, cut-off times, segment-specific rules. Drives `kit_manifest` mandatory entries. Free-text per `Race_Events_D66_Design_v1.md` Decision 3; LLM consumes verbatim per D9 hybrid. |
| `event.mandatory_gear_text` | **`race_event_payload.mandatory_gear_text` (D-66 amendment 2026-05-18; new v2 source pointer)** | Free-text mandatory gear list as the athlete pasted from the race director's published guide. LLM extracts items into `kit_manifest` per D9 hybrid + flags non-canonical items with `layer0_canonical=false`. |
| `event.locales[]` | **DEPRECATED (D-66 amendment 2026-05-18).** Replaced by structured `route_locales[]` from `race_event_payload.route_locales` per new §3.11 below. Single-day events with no route-locale graph fall through to empty (rendered as "Single-day event; no structured route-locale graph"). | — |

### 3.11 NEW — Route locales (D-66 structured graph)

Added 2026-05-18 (paired D-66 implementation Step 4e). Replaces v1's flat `event.locales[]` reference.

| Variable | Source | Notes |
|---|---|---|
| `race_event_payload.route_locales[]` | `layer4/context.py` `RaceEventPayload.route_locales` (D-66 typed contract) | Ordered (sorted ascending by `sequence_idx`) list of `RouteLocale` records. Each entry: `role` (closed 7-element enum: start / transition_area / aid_station / drop_bag_point / bivvy / finish / other), `sequence_idx` (1-indexed; gaps allowed), `name`, optional `mile_marker`, optional `lat`/`lng`/`mapbox_id` (Mapbox anchoring; v1 does not consume coordinates), optional `notes`, nested `equipment: list[RouteLocaleEquipment]` (each with `equipment_name`, optional `quantity_text`, optional `notes`). |
| `race_event_payload.route_locales[].role`-anchor invariant | Enforced at construction (per `Race_Events_D66_Design_v1.md` §4.2) | When `route_locales` non-empty: first entry has `role='start'` and last has `role='finish'`. Single-day events that fill in start + finish only meet this trivially; multi-day events fill in intermediate aid stations / transition areas / drop bag points / bivvy points. |
| Single-day events with empty `route_locales` | Legal per `Race_Events_D66_Design_v1.md` §4.2 structural invariant 4 | Validator rule `kit_manifest_inputs_incomplete` skips when `race_format == 'single_day'` per §5.4 D-66 active branch. The synthesizer reads `mandatory_gear_text` (free-text) for kit_manifest construction. |
| Multi-day events with empty `route_locales` | Soft warning per validator rule `kit_manifest_inputs_incomplete_no_route_locales` | Synthesizer renders the kit_manifest from `mandatory_gear_text` only; orchestrator emits `Observation(category='data_gap')` post-validation; brief ships as-drafted. |

**Coaching consumption pattern (synthesizer-side):** when route_locales is non-empty, render kit_manifest items grouped by route-locale role (start kit / aid-station resupply / transition gear / drop-bag contents / finish-line recovery). When route_locales is empty + multi-day, kit_manifest degrades to a flat list extracted from `mandatory_gear_text`.

### 4.1 Tool schema (v2 surgical amendments)

Two surgical changes to the v1 tool schema (otherwise unchanged — see v1 §4.1 for the full schema):

1. **`pacing_target` shape (per `RaceSegment` in `race_plan.segments[]`):** replaced free-shape dict with typed `IntensityTarget` 9-shape `oneOf` union per `Layer4_Spec.md` §7.3.1. The 9 shapes per the D1 amendment 2026-05-17:

```json
"pacing_target": {
  "oneOf": [
    {"type": "object", "additionalProperties": false, "required": ["hr_bpm_low", "hr_bpm_high"], "properties": {"hr_bpm_low": {"type": "integer", "minimum": 30, "maximum": 230}, "hr_bpm_high": {"type": "integer", "minimum": 30, "maximum": 230}}},
    {"type": "object", "additionalProperties": false, "required": ["power_w_low", "power_w_high"], "properties": {"power_w_low": {"type": "integer", "minimum": 0, "maximum": 2000}, "power_w_high": {"type": "integer", "minimum": 0, "maximum": 2000}}},
    {"type": "object", "additionalProperties": false, "required": ["pace_per_km_low", "pace_per_km_high"], "properties": {"pace_per_km_low": {"type": "string", "pattern": "^\\d{1,2}:[0-5]\\d$"}, "pace_per_km_high": {"type": "string", "pattern": "^\\d{1,2}:[0-5]\\d$"}}},
    {"type": "object", "additionalProperties": false, "required": ["pace_per_100m_low", "pace_per_100m_high"], "properties": {"pace_per_100m_low": {"type": "string", "pattern": "^\\d{1,2}:[0-5]\\d$"}, "pace_per_100m_high": {"type": "string", "pattern": "^\\d{1,2}:[0-5]\\d$"}}},
    {"type": "object", "additionalProperties": false, "required": ["rpe_low", "rpe_high"], "properties": {"rpe_low": {"type": "integer", "minimum": 1, "maximum": 10}, "rpe_high": {"type": "integer", "minimum": 1, "maximum": 10}}},
    {"type": "object", "additionalProperties": false, "required": ["vert_m_per_hr_low", "vert_m_per_hr_high"], "properties": {"vert_m_per_hr_low": {"type": "integer", "minimum": 0, "maximum": 3000}, "vert_m_per_hr_high": {"type": "integer", "minimum": 0, "maximum": 3000}}},
    {"type": "object", "additionalProperties": false, "required": ["strokes_per_min_low", "strokes_per_min_high"], "properties": {"strokes_per_min_low": {"type": "integer", "minimum": 0, "maximum": 200}, "strokes_per_min_high": {"type": "integer", "minimum": 0, "maximum": 200}}},
    {"type": "object", "additionalProperties": false, "required": ["rpm_low", "rpm_high"], "properties": {"rpm_low": {"type": "integer", "minimum": 0, "maximum": 250}, "rpm_high": {"type": "integer", "minimum": 0, "maximum": 250}}},
    {"type": "object", "additionalProperties": false, "required": ["grade_system", "grade_min", "grade_max"], "properties": {"grade_system": {"type": "string", "enum": ["yosemite_decimal", "french_sport", "uiaa"]}, "grade_min": {"type": "string"}, "grade_max": {"type": "string"}}}
  ]
}
```

Per-shape discipline guidance per `Layer4_Spec.md` §7.3.1: HRTarget = universal endurance; PowerTarget = bike/run/skimo/row; PaceTarget = run/hike/paddle/ski; SwimPaceTarget = swim; RPETarget = universal fallback; VerticalRateTarget = skimo/hiking/scrambling; StrokeRateTarget = swim/paddle/row; CadenceTarget = cycling; ClimbingGradeTarget = outdoor rock (Yosemite Decimal / French Sport / UIAA). Pick the shape that best matches the segment's discipline + 3A data density. RPE is the fallback when conditions degrade hard targets (night sections, technical terrain, fatigue past hour N per D5 hybrid policy).

2. **`kit_manifest[].layer0_canonical: bool` field surfaced** per paired `Layer4_Spec.md` §7.13 amendment 2026-05-18 (`KitItem.layer0_canonical: bool` field added; default `false`). The v1 prompt body §4.1 already sketched this field; v2 confirms it is load-bearing for validator rule 13 (per-item canonical-name check) and lands on the typed `KitItem` contract.

### 6. User prompt template — v2 route-locales rendering block

Added to the v1 §6 template after the existing Event-metadata header block, before "# Athlete profile":

```
{{#race_event_payload.race_rules_summary}}
**Race rules summary (verbatim from athlete):**
```
{{race_event_payload.race_rules_summary}}
```
{{/race_event_payload.race_rules_summary}}

{{#race_event_payload.mandatory_gear_text}}
**Mandatory gear text (verbatim from athlete):**
```
{{race_event_payload.mandatory_gear_text}}
```
{{/race_event_payload.mandatory_gear_text}}

{{#race_event_payload.route_locales}}
# Route locales (D-66 structured graph)

Ordered by sequence_idx. Per-locale equipment populated by the athlete via onboarding §H.4 or the profile race-events tab. Synthesize kit_manifest items + RacePlan.segments references from this graph.

{{#each route_locales}}
- [{{sequence_idx}}] {{role}}: {{name}}{{#mile_marker}} (mile {{mile_marker}}){{/mile_marker}}
{{#notes}}    notes: {{notes}}{{/notes}}
{{#equipment}}    equipment:
{{#each equipment}}      - {{equipment_name}}{{#quantity_text}} ({{quantity_text}}){{/quantity_text}}{{#notes}}
          notes: {{notes}}{{/notes}}{{/each}}{{/equipment}}
{{/each}}
{{/race_event_payload.route_locales}}
```

The driver implementation in `layer4/race_week_brief.py:_render_user_prompt()` does the inline-Python rendering equivalent (no Mustache dependency).

---

## Sections unchanged from v1 — see `Layer4_RaceWeekBrief_v1.md`

- §1 Purpose + scope (§1.1, §1.2, §1.3)
- §2 Pipeline placement
- §3.2 Athlete + race-week context
- §3.3 Athlete state (drives Taper modulation)
- §3.4 Periodization context (Taper phase intent)
- §3.5 Multi-locale equipment view (Layer 2C — race-week-specific load-bearing)
- §3.6 Prior plan Taper window (full verbatim per D4)
- §3.7 Race-day fueling tier (Layer 2E — load-bearing for race-day plan)
- §3.8 Terrain + environment (Layer 2B — drives pacing + kit)
- §3.9 Retry context (only present on retry pass)
- §3.10 Intentionally NOT passed
- §4 Output schema + tool definition (everything except §4.1 pacing_target shape + kit_manifest.layer0_canonical surfacing — both amended above; §4.2 cross-output schema rules unchanged)
- §5 System prompt (verbatim — no coaching policy change)
- §6 User prompt template (everything except the new Route-locales rendering block shown above; the existing event-metadata header + athlete profile + active injuries + 3A summary + 3B Taper context + 2E fueling tier + 2C equipment view + prior taper sessions + retry context + task blocks all carry over unchanged)
- §7 Sampling configuration (model + temperature + max_tokens + extended_thinking + tool_choice + capped_retries)
- §8 Coaching flag emission rules (§8.1 LLM-emittable + §8.2 spec-auto Taper + §8.3 observations)
- §9 Coaching guidance (§9.1 Taper-session modulation policy + §9.2 hybrid pacing + §9.3 mixed contingency + §9.4 kit manifest resolution + §9.5 mental prep cues evidence-grounded + §9.6 race-day fueling plan derivation)
- §10 Edge cases
- §11 Validator + retry contract (§11.1 validator rules applied + §11.2 retry context rendering + §11.3 cap-hit behavior)
- §12 Test scenarios (PSS-RWB-prefix v1 test scenarios — Step 4e implementation tests in `tests/test_layer4_race_week_brief.py` exercise the D-66-active surface)
- §13 Performance budget
- §14 Open items + gut check

---

**End of v2 amendment.**
