# AIDSTATION — Current State

Single rolling-state pointer. Changes on every shipped session. Long-form session narrative lives in `handoffs/`; rolling cross-session items live in `CARRY_FORWARD.md`.

---

## Last shipped session

`handoffs/V5_Implementation_D73_Phase_2_5_Closing_Handoff_v1.md` — 2026-05-19

D-73 Phase 2.5 — Layer 2E nutrition baseline (fourth upstream Layer 2 runtime; Phase 2 of 5 now 4 of 5 shipped). New `layer2e/__init__.py` + `layer2e/builder.py` — `q_layer2e_nutrition_baseline_payload(db, identity, health_status, performance, target_events, lifestyle, included_disciplines, framework_sport, current_phase, *, etl_version_set, athlete_id=None, today=None) -> Layer2EPayload`. **Vertical slice** per Andy 2026-05-19 scope pick: §5.2 BMR + per-phase activity multiplier (4 PLA SELECTs on `layer0.phase_load_weekly_totals`; Mifflin path; Cunningham auto-switch when `ffm_kg` lands on `Layer1Performance` per open item 2E-1) + §5.3 macro split (per-phase band table with fat-floor enforcement) + §5.4 race-day fueling per event (5-tier duration classification + sport-profile CHO modifier + salt-tolerance modifier + caffeine plan + format ranking with GI-trigger substring filter) + §5.6 dietary pattern adjustments (Vegan B12/iron/EPA + Low-FODMAP) + §5.7 simplified sleep-dep overlay (uses flat `Layer1Lifestyle.sleep_deprivation_*` fields). **Two named stubs**: §5.5 supplement integration returns empty + `supplements_not_structured` coaching flag (Layer 1 `supplement_protocol_notes: str` vs spec's structured `list[AthleteSupplementRecord]` — closed by §I.1 form refresh); §5.8 heat acclim returns `temp_signal='unknown'` + `race_temp_unknown` flag per event (PlanManagementState + HeatAcclimState contracts not yet written — open items 2E-2/3/4). §5.9 HITL gate 5 (anaphylaxis × aid-station-bound event) fires from deployed `FoodAllergyRecord.severity='anaphylaxis'` + new `Layer2ETargetEvent.aid_stations`; gates 1-4 deferred to post-§I.1-refresh. §8 coaching flags shipped: `pla_missing_for_sport_phase` (D-07 fallback path), `hrt_bmr_limitation`, `low_calorie_target_relative_to_rmr`, `supplements_not_structured`, `race_temp_unknown`, `sleep_dep_data_missing`. New `Layer2ETargetEvent` input type in `layer4/context.py` — vertical-slice subset of `Layer2E_Spec.md` §3 `TargetEvent` (event_id / event_name / event_date / framework_sport / estimated_duration_hr / aid_stations); deferred fields (race_terrain_pct, race_pack_weight_kg, team_format, race_specific_nutrition_restrictions) don't drive any v1 path. New `tests/test_layer2e.py` — 31 tests across §4 input validation + §13.1 PGE 2026 baseline + §13.3 vegan triggers + §13.7 time-based mode + §13.8 PLA fallback (Swimrun) + §13.9 Cunningham FFM + §13.10 multiple events + sport-modifier + salt-tolerance + caffeine + sleep-dep + heat-acclim stub + HITL gate 5 + clean baselines. Tests 819 → 850. 4 substantive files (under the 5-ceiling).

**Predecessor:** `V5_Implementation_D73_Phase_2_3_Closing_Handoff_v1.md` (Layer 2B terrain classifier — third upstream Layer 2 runtime).

## Current focus

Andy's pick. Architect-recommended next: **D-73 Phase 2.4 — Layer 2C equipment mapper** per `Upstream_Implementation_Plan_v1.md` §4 (last 2X runtime). /plan-mode gate for §5 Decision Points (runtime vs pre-resolved toggle lookup; discipline-to-toggle mapping location). Over-ceiling expected (~5-7 files). Alternatively: **§H.2 / §J form-refresh PR** to wire Layer 2B + Layer 2E input-source surfaces (closes Open Items 2B-2 + 2B-3 + Layer 2E open items 2E-1 + 2E-12 + the §I.1 structured-supplement refresh that de-stubs Layer 2E §5.5); **Plan Management spec authorship** to land 2E-2/3/4 contracts (de-stubs Layer 2E §5.8 heat acclim); **Phase 1.4** (D-52 catalog migration sequencing); orthogonal **Layer 4 Step 4f** (`llm_layer4_plan_create` Pattern A) / **Step 7** (env-gated `ANTHROPIC_API_KEY` scaffolding).

Orthogonal alternatives tracked in `CARRY_FORWARD.md`.

## Layer status

| Layer | Status |
|---|---|
| **0** | DEPLOYED |
| **1** | 🟢 v1 spec + typed payload + runtime builder shipped 2026-05-19 (D-51 design wave + Phase 1.2 schema arc + Phase 1.3 builder); 🟢 injury_log §B.1/§B.1.1/§B.3 extensions shipped 2026-05-19 (Phase 2.2 paired) |
| **2** | 🟡 2A + 2D + 2B + 2E runtime shipped 2026-05-19 (Phase 2.1 + 2.2 + 2.3 + 2.5); 2C spec done, runtime queued; 2E ships vertical-slice (§5.5 supplements + §5.8 heat acclim stubbed pending §I.1 refresh + Plan Management spec) |
| **3** | 3A SPEC DONE; 3B SPEC DONE |
| **3.5** | Designed; not yet implemented |
| **4** | SPEC COMPLETE §§1-14; Implementation Steps 2 + 3 + 4a-4e of 8 COMPLETE |
| **5** | Not yet specced |

## D-73 upstream implementation arc

Multi-session plan in `Upstream_Implementation_Plan_v1.md`. Phase 1.1 (D-51 design wave) + Phase 1.2A/B/C (schema arc) + Phase 1.3 (Layer 1 typed payload + builder + spec) + Phase 2.1 (Layer 2A discipline classifier) + Phase 2.2 (Layer 2D injury risk + paired injury_log §B schema evolution + §B form UI evolution) + Phase 2.3 (Layer 2B terrain classifier + paired Layer 0 terrain_gap_rules severity reclassification + paired pydantic widening) + Phase 2.5 (Layer 2E nutrition baseline vertical slice — daily targets + race-day fueling + dietary patterns + simplified sleep-dep; §5.5 + §5.8 stubbed) all shipped 2026-05-19. **Phase 1 complete + Phase 2 at 4 of 5 shipped.** 2C builder queued (~1 ceiling-breaking session). Phase 2.5 de-stubs (§I.1 form refresh + Plan Management spec) queued. Phases 3-5 (LLM drivers + orchestrator wiring) queued behind Phase 2.

**Forcing function:** Andy's PGE 2026 (2026-07-17). `race_week_brief` auto-fires 2026-07-03 (days_to_event = 14). ~10 weeks of runway from 2026-05-19.

## Tests

850 green (last measured 2026-05-19 after Phase 2.5 +31 Layer 2E builder tests; baseline 819 preserved).

---
