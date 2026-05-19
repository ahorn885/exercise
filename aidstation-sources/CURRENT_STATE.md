# AIDSTATION — Current State

Single rolling-state pointer. Changes on every shipped session. Long-form session narrative lives in `handoffs/`; rolling cross-session items live in `CARRY_FORWARD.md`.

---

## Last shipped session

`handoffs/V5_Implementation_D73_Phase_2_1_Closing_Handoff_v1.md` — 2026-05-19

D-73 Phase 2.1 — Layer 2A discipline classifier (first upstream Layer 2 runtime; Phase 2 of 5 kicked off). New `layer2a/__init__.py` + `layer2a/builder.py` — `q_layer2a_discipline_classifier_payload(db, framework_sport, *, athlete_discipline_overrides, estimated_race_duration_hours, navigation_required, team_format, etl_version_set) -> Layer2APayload` per `Layer2A_Spec.md` §3 verbatim. Pure query node, single SELECT with CTE + 2 LEFT JOINs against `layer0.sport_discipline_map` + `layer0.phase_load_allocation` + `layer0.discipline_training_gaps` (D-05 standing filter `discipline_name NOT LIKE '%WEEKLY TOTAL%'` applied per spec §6). Conditional resolution per spec §5.3 — D-008b (whitewater) auto-in iff `estimated_race_duration_hours >= 20`; D-013 (nav) auto-in iff `navigation_required=True`; both fall to `prompt_required` + HITL when signal is None; athlete-explicit overrides win. Weight computation per §5.4 (midpoint of `race_time_pct_low`/`high` is system default; override surfaces both `value` + `system_default`). Rationale templates v1 shipped Andy-quality (not deferred per Andy 2026-05-19) — direct, evidence-grounded, no platitudes per CLAUDE.md coaching voice; 4 role modifiers (core/supporting/minor/technical) × 3 inclusion states × conditional-resolution suffix; `sport_specific_context` appended verbatim when non-NULL. Coaching flags per §8 — `training_gap` per DTG entry; `conditional_auto_resolved` for race-rule auto-in/out (separate messages); `weight_override_divergence` when relative divergence > 50%. D-52 sub-decision **dissolved** — three Layer 2A catalog tables exist only under `layer0.*` (no `public.*` counterparts); spec §5.2 SQL targets `layer0.*` directly. D-17 sub-format strip via `_SUB_FORMAT_SPORTS` whitelist (Triathlon / Skimo / LDC / OWMS / Canoe-Kayak Marathon) per spec §14 gut-check; AR bypasses entirely. New `tests/test_layer2a.py` — 14 tests across input validation / AR baseline / override divergence / short AR / Triathlon strip / unknown sport / unmapped override / unresolved conditional. Tests 770 → 784. 3 substantive files; well under ceiling.

**Predecessor:** `V5_Implementation_D73_Phase_1_3_Closing_Handoff_v1.md` (Layer 1 spec + typed `Layer1Payload` + runtime builder — Phase 1 of upstream arc effectively complete).

## Current focus

Andy's pick. Architect-recommended next: **D-73 Phase 2.2 — Layer 2D injury risk** per `Upstream_Implementation_Plan_v1.md` §4. Consumes 2D's already-typed `ExerciseRisk` + `AccommodationModality` discriminated union in `layer4/context.py` (shipped via PR-C-followon 2026-05-17 — no new design). Reads `conditions_log` (Layer 1 §B injuries; D-51 storage) + Layer 0 `injury_profiles` + `exercise_risk_assessments`. ~4-5 files; under ceiling. Alternatively: 2B (terrain classifier) reads target event terrain + Layer 0 taxonomy; 2C (equipment mapper) needs /plan-mode gate for §5 Decision Points; 2E (nutrition baseline) reads §B + §H + §I + 2A `framework_sport` + `discipline_ids`.

Orthogonal alternatives tracked in `CARRY_FORWARD.md`.

## Layer status

| Layer | Status |
|---|---|
| **0** | DEPLOYED |
| **1** | 🟢 v1 spec + typed payload + runtime builder shipped 2026-05-19 (D-51 design wave + Phase 1.2 schema arc + Phase 1.3 builder) — Layer1_Spec.md canonical |
| **2** | 🟡 2A runtime shipped 2026-05-19 (Phase 2.1); 2B/2C/2D/2E specs done, runtime queued |
| **3** | 3A SPEC DONE; 3B SPEC DONE |
| **3.5** | Designed; not yet implemented |
| **4** | SPEC COMPLETE §§1-14; Implementation Steps 2 + 3 + 4a-4e of 8 COMPLETE |
| **5** | Not yet specced |

## D-73 upstream implementation arc

Multi-session plan in `Upstream_Implementation_Plan_v1.md`. Phase 1.1 (D-51 design wave) + Phase 1.2A/B/C (schema arc) + Phase 1.3 (Layer 1 typed payload + builder + spec) + Phase 2.1 (Layer 2A discipline classifier — first Layer 2 runtime) all shipped 2026-05-19. **Phase 1 complete + Phase 2 kicked off (1 of 5 nodes shipped).** 2B/2C/2D/2E builders queued (~4 sessions). Phases 3-5 (LLM drivers + orchestrator wiring) queued behind Phase 2.

**Forcing function:** Andy's PGE 2026 (2026-07-17). `race_week_brief` auto-fires 2026-07-03 (days_to_event = 14). ~10 weeks of runway from 2026-05-19.

## Tests

784 green (last measured 2026-05-19 after Phase 2.1 +14 Layer 2A builder tests; baseline 770 preserved).

---
