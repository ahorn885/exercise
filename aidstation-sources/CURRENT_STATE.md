# AIDSTATION — Current State

Single rolling-state pointer. Changes on every shipped session. Long-form session narrative lives in `handoffs/`; rolling cross-session items live in `CARRY_FORWARD.md`.

---

## Last shipped session

`handoffs/V5_Implementation_D73_Phase_2_4_Prep_Closing_Handoff_v1.md` — 2026-05-19

D-73 Phase 2.4-Prep — Layer 2C data substrate (schema + ETL extractor work landing the 4 columns Layer 2C will read; **Phase 2.4 Layer 2C builder itself queued for next session** per Andy 2026-05-19 split-scope pick). Drift inventory between `Layer2C_Spec.md` §3-§8 and deployed `layer0.*` surfaced four substantive gaps: (a) `layer0.exercises.equipment_substitutes_structured JSONB` (Layer 2C §5.4 CNF Tier 2) — migration on-disk but unapplied + unpopulated; (b) `layer0.exercises.terrain_required TEXT[]` (§5.2 pass-through) — migration on-disk; ETL extractor already produces the field via `vocabulary_transforms.transform_equipment_string`, `run.py` already wires it into the INSERT column list — only the column-add was missing; (c) `layer0.sport_specific_gear_toggles.also_satisfies TEXT[]` (§5.1 + §6) — no migration; (d) `layer0.sport_specific_gear_toggles.gated_discipline_ids TEXT[]` (§8.3) — no migration. **Decision Points resolved** (3-question AskUserQuestion gate; `Layer2C_Spec.md` §5 + §8.3 + Open Items 2C-1/2C-2): **DP1 (§5.1 Toggle definition lookup) = (A) Runtime lookup in 2C** (spec recommendation); **DP2 (§8.3 Discipline-to-toggle mapping) = (b) Structured column on `sport_specific_gear_toggles`** (Andy diverged from spec's hard-code-for-v1 recommendation; structured carries traceability + survives spec evolution). **Scope = Split: Prep first, then 2C** (over Vertical-slice / Migrations-plus-full-2C / Pivot-to-Step-4f-or-Step-7). **6 substantive files** (over ceiling per Andy's "Add exercise_db.py too" pick on the 6-vs-5 gate; deletes operational drift between schema migration + populate run by routing structured substitutes through the ETL extractor): (1) `etl/layer0/schema.sql` adds the 4 columns + spec-section anchor comments; (2) NEW `aidstation-sources/migrations/migrate_toggles_v3_columns.sql` combined-migration (ADD COLUMN IF NOT EXISTS + UPDATE the 3 known cases — `Climbing — roped` also_satisfies `Rappelling / abseiling` + gates `D-010`; `Rappelling / abseiling` gates `D-011`; `Snowshoeing setup` gates `D-015` — + DO-block verification with NOTICE-fallback when no active row exists so safe to run pre-ETL); (3) `etl/layer0/extractors/vocabulary.py` new code-side constants `_TOGGLE_ALSO_SATISFIES` + `_TOGGLE_GATED_DISCIPLINES` (matches Layer 2D `_HIGH_CARDIAC_LOAD_DISCIPLINES` precedent; `_parse_gear_toggles` emits the 2 new fields per row so next ETL re-run preserves the data); (4) `etl/layer0/extractors/exercise_db.py` new `load_parsed_substitutes_structured()` function reading the shipped `etl/sources/parsed_substitutes.json` (154 exercises × 510 entries from prior K-parser work) + `extract_exercises` attaches per-row; loud-fallback empty dict when file missing; (5) `etl/layer0/run.py` extends both INSERTs (4 new columns total — 2 on `exercises` via `to_jsonb` for `equipment_substitutes_structured` + already-wired `terrain_required`; 2 on `sport_specific_gear_toggles`); (6) NEW `tests/test_layer2c_prep.py` 16 tests across 3 test classes (`TestGearToggleParser` 6 / `TestParsedSubstitutesLoader` 5 / `TestSchemaSubstrate` 5 — including `Layer2CPayload` regression smoke covering shipped 5 sub-types + coaching-flag enum guard). Tests 850 → 866 (+16). **Operational sequence for Andy on Neon** (closing handoff §5): (1) `migrate_exercises_substitutes_structured.sql` (existing pre-shipped); (2) `migrate_exercises_terrain_required.sql` (existing); (3) `migrate_toggles_v3_columns.sql` (new); (4) Re-run `python -m etl.layer0.run` to populate the 4 new columns on a new etl_version. Once those 4 steps complete on Neon, Phase 2.4 Layer 2C builder session proceeds.

**Predecessor:** `V5_Implementation_D73_Phase_2_5_Closing_Handoff_v1.md` (Layer 2E nutrition baseline vertical slice — fourth upstream Layer 2 runtime).

## Current focus

Andy's pick. Architect-recommended next: **D-73 Phase 2.4 — Layer 2C equipment mapper builder** per `Upstream_Implementation_Plan_v1.md` §4 + this session's Prep substrate. Phase 2.4-Prep this session shipped schema + ETL data substrate; the Layer 2C builder itself (`q_layer2c_equipment_mapper_payload` per `Layer2C_Spec.md` §3) lands next. Decision Points already resolved (DP1 (A) runtime lookup; DP2 (b) structured column) — no /plan-mode gate remaining. Estimated 4-5 substantive files (`layer2c/__init__.py` + `layer2c/builder.py` + `tests/test_layer2c.py` + maybe a small `layer4/context.py` input-type addition like Phase 2.5's `Layer2ETargetEvent`). Hard prerequisite: Andy operationally applies the 3 SQL migrations + re-runs ETL on Neon (sequence documented in this session's closing handoff §5). Alternatively: **§H.2 / §J form-refresh PR** to wire Layer 2B + Layer 2E input-source surfaces (closes Open Items 2B-2 + 2B-3 + Layer 2E open items 2E-1 + 2E-12 + the §I.1 structured-supplement refresh that de-stubs Layer 2E §5.5); **Plan Management spec authorship** to land 2E-2/3/4 contracts (de-stubs Layer 2E §5.8 heat acclim); **Phase 1.4** (D-52 catalog migration sequencing); orthogonal **Layer 4 Step 4f** (`llm_layer4_plan_create` Pattern A) / **Step 7** (env-gated `ANTHROPIC_API_KEY` scaffolding).

Orthogonal alternatives tracked in `CARRY_FORWARD.md`.

## Layer status

| Layer | Status |
|---|---|
| **0** | DEPLOYED |
| **1** | 🟢 v1 spec + typed payload + runtime builder shipped 2026-05-19 (D-51 design wave + Phase 1.2 schema arc + Phase 1.3 builder); 🟢 injury_log §B.1/§B.1.1/§B.3 extensions shipped 2026-05-19 (Phase 2.2 paired) |
| **2** | 🟡 2A + 2D + 2B + 2E runtime shipped 2026-05-19 (Phase 2.1 + 2.2 + 2.3 + 2.5); 2C spec done + Phase 2.4-Prep data substrate shipped 2026-05-19 (4 column adds + toggle migration + ETL extractor wiring); 2C builder queued for next session; 2E ships vertical-slice (§5.5 supplements + §5.8 heat acclim stubbed pending §I.1 refresh + Plan Management spec) |
| **3** | 3A SPEC DONE; 3B SPEC DONE |
| **3.5** | Designed; not yet implemented |
| **4** | SPEC COMPLETE §§1-14; Implementation Steps 2 + 3 + 4a-4e of 8 COMPLETE |
| **5** | Not yet specced |

## D-73 upstream implementation arc

Multi-session plan in `Upstream_Implementation_Plan_v1.md`. Phase 1.1 (D-51 design wave) + Phase 1.2A/B/C (schema arc) + Phase 1.3 (Layer 1 typed payload + builder + spec) + Phase 2.1 (Layer 2A discipline classifier) + Phase 2.2 (Layer 2D injury risk + paired injury_log §B schema evolution + §B form UI evolution) + Phase 2.3 (Layer 2B terrain classifier + paired Layer 0 terrain_gap_rules severity reclassification + paired pydantic widening) + Phase 2.5 (Layer 2E nutrition baseline vertical slice — daily targets + race-day fueling + dietary patterns + simplified sleep-dep; §5.5 + §5.8 stubbed) + Phase 2.4-Prep (Layer 2C data substrate — 4 column adds on `layer0.exercises` + `layer0.sport_specific_gear_toggles`; new toggle migration; ETL extractor wiring; structured substitutes routed via `etl/sources/parsed_substitutes.json`) all shipped 2026-05-19. **Phase 1 complete + Phase 2 at 4 of 5 runtimes shipped + Phase 2.4-Prep substrate landed.** 2C builder is the next single session (Decision Points pre-resolved; ~4-5 substantive files; hard prerequisite is Andy operationally applies 3 SQL migrations + ETL re-run on Neon). Phase 2.5 de-stubs (§I.1 form refresh + Plan Management spec) queued. Phases 3-5 (LLM drivers + orchestrator wiring) queued behind Phase 2.

**Forcing function:** Andy's PGE 2026 (2026-07-17). `race_week_brief` auto-fires 2026-07-03 (days_to_event = 14). ~10 weeks of runway from 2026-05-19.

## Tests

866 green (last measured 2026-05-19 after Phase 2.4-Prep +16 Layer 2C substrate tests; Phase 2.5 baseline 850 preserved).

---
