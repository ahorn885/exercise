# Layer 1 Kickoff — Session Handoff

**Date:** 2026-05-08
**Predecessor:** `Layer0_Done_Layer1_Kickoff_Handoff.md`
**Status:** Open Items #9 and #10 closed. All Layer 0 open items resolved or documented. Layer 1 prompt design unblocked with no remaining prerequisites.
**Next chat starts with:** Layer 1 prompt design — Prompt 2A (Discipline Classifier).

---

## What happened this session

Two deferred Layer 0 populate tasks completed directly against the DB (targeted UPDATE, no ETL re-run needed):

**#9 — `stimulus_components` on `layer0.disciplines`**
- Enum finalized at 14 values (12 starter + 2 additions):
  `aerobic_low | aerobic_high | muscular_endurance_legs | muscular_endurance_upper | pack_carry_load | vertical_gain | technical_descent | technical_handwork | grip_strength | balance_dynamic | cold_exposure | fueling_practice | cognitive_navigation | explosive_power`
- `cognitive_navigation` added: needed for D-013, D-016, D-022 — plan-gen must surface that no substitute covers this stimulus
- `explosive_power` added: needed for D-024 (fencing), D-026 (OCR) — distinct from any endurance stimulus
- All 31 active disciplines tagged and written via `populate_stimulus_components.sql`
- Scripts committed to `etl/sources/` in repo

**#10 — `substitute_covers` on `layer0.discipline_substitutes`**
- Computed as `target.stimulus_components ∩ substitute.stimulus_components` with one manual override rule: remove `grip_strength` when a paddle sport (D-007/008a/008b/009/017) is substitute for a climbing/mountaineering target (D-010/011/012/016) — paddle grip pattern doesn't transfer to climbing grip
- Override triggered 0 times across 91 rows (no such pairings exist in the substitution table — correct, those would be sub-0.3 fidelity and were never added)
- 91 rows updated, 0 NULL remaining, 0 warnings
- Script: `populate_substitute_covers.py` in `etl/sources/`

---

## Full Layer 0 open items state (carry-forward)

| # | Item | Status |
|---|---|---|
| 1 | Governing Bodies | Carryover; FAQ-feature-pending |
| 2 | Race / Event Formats | Carryover; Layer 1 review |
| 3 | Pairing Matrix gap (D-018+) | Carryover; Sheet 4 doesn't cover D-018+ |
| 4 | Vertical Gain in Layer 1 | Carryover; Layer 1 design |
| 5 | exercise_db_sport vocab alignment | RESOLVED |
| 6 | Sheet 3 col 7 deprecation | Carryover |
| 7 | Cross-Sport Properties extension | Parser tightened in v3; data still 1 row |
| 8 | Vocabulary cleanup transforms | RESOLVED |
| 9 | `stimulus_components` populate | **CLOSED this session** |
| 10 | `substitute_covers` populate | **CLOSED this session** |
| 11 | Multi-substitute composition algorithm | Deferred to plan-gen workstream |
| 12 | D-008b pairing matrix review | Not blocking; whitewater coach review |
| 13 | AR D-008b phase load tuning | Not blocking; whitewater AR race data |
| 14 | Sport-context substitution overrides | Deferred until plan-gen testing signal |
| 15 | Health Conditions UI gap | Launch-blocker; product workstream |
| 16 | D-020 Alpine Descent training gap | Captured in `discipline_training_gaps` |
| 17 | D-024 Épée Fencing training gap | Captured |
| 18 | D-018 Swimrun training gap | Captured |
| 19 | Sub-ID naming convention | Process note |
| 20 | Caching layer | Deferred; design cache-friendly from day 1 |
| 21 | Sheet 7 deprecation | Banner applied; full deletion deferred |

---

## Layer 0 canonical state (unchanged from predecessor handoff)

| Layer | Source | Version | Location |
|---|---|---|---|
| 0A (Sports Framework) | `Sports_Framework_v10.xlsx` | v10.0 | repo `etl/sources/` |
| 0B (Exercise Database) | `AR_Exercise_Database_v17.xlsx` | v17.0-r3 | repo `etl/sources/` |
| 0C (Vocabulary) | `Vocabulary_Audit_v2.md` | v2.0-r1 | repo `etl/sources/` |
| ETL Spec | `Layer0_ETL_Spec_v3.md` | v1.3.1 | project |

DB: dev and prod both at v1.3.1. All validators 0/0/0. `stimulus_components` and `substitute_covers` now populated (these were NULL at v1.3.1 ETL time — populate scripts ran post-ETL directly against DB).

---

## Next workstream — Layer 1 prompt design, starting with 2A

**Read before starting:**
1. This handoff
2. `Athlete_Onboarding_Data_Spec_v2.md` (v2.5) — the data model Layer 1 is built against
3. `Layer0_to_PlanGen_Contract_Preview.md` — what plan-gen needs to consume from Layer 0
4. `Layer0_Query_Decisions_Handoff.md` — the 11 typed query functions and their consumer assignments

**Design pattern for each prompt (established in prior sessions):**
For each prompt, define in order:
1. Input contract (what comes from upstream)
2. Layer 0 queries needed (which typed functions, what they return)
3. LLM prompt structure
4. Output payload contract (what goes downstream)
5. Partial-update invalidation rules (what upstream changes force this prompt to re-run)

Do NOT shortcut to LLM prompt text first. Define interfaces first.

**Why 2A first:**
- Small input surface: athlete-stated sport / event / target race
- Well-bounded output: resolved discipline IDs + applicability flags
- Hits multiple Layer 0 tables: `sports`, `disciplines`, `sport_discipline_map`, `sport_name_aliases`
- Real integration test of the query layer
- Outputs feed directly into all downstream Layer 1 prompts

---

## Process notes (carry-forward)

- Andy's preferences: direct, judgment-focused, no praise/hype, gut check at end of recommendations
- No artifact / no document creation for explanations — read in chat; documents only for real deliverables
- Don't propose Layer 0 schema changes unless Layer 1 design genuinely demands one — Layer 0 is canonical
- Sports Framework xlsx is source of truth — never reconstruct from prose
- Versioning rule: every change increments; never overwrite
