# Layer 0 Done → Layer 1 Kickoff — Session Handoff

**Date:** 2026-05-08 (prod ETL ran 2026-05-09 UTC)
**Predecessor:** `ETL_Rerun_Triage_Handoff.md`
**Status:** Layer 0 v1.3.1 canonical in dev and prod. All validators clean. Layer 1 prompt design unblocked.
**Next chat starts with:** Layer 1 prompt design kickoff. First decision is whether to design 2A (Discipline Classifier) directly or do small adjacent items first.

---

## TL;DR

Layer 0 ETL is done. Three sessions of work landed:
1. v1.3 ETL re-run on Neon `/dev` branch surfaced two real validator issues (taper-band undershoot on 9 sports, 5 unknown contraindicated_conditions tokens) and one schema fix needed for sub-variant substitutes
2. v1.3.1 ETL fixes (validator threshold, vocab transforms, new health category) shipped and re-validated on dev with all validators at 0 warnings
3. v1.3.1 ETL ran clean on prod — fresh schema bootstrap with widened constraint, all validators 0/0/0

Prod and dev are aligned. No drift, no pending migrations.

---

## Final state

| Layer | Source | Version | Location |
|---|---|---|---|
| 0A (Sports Framework) | `Sports_Framework_v10.xlsx` | v10.0 | repo `etl/sources/` |
| 0B (Exercise Database) | `AR_Exercise_Database_v17.xlsx` | v17.0-r3 | repo `etl/sources/` |
| 0C (Vocabulary) | `Vocabulary_Audit_v2.md` | v2.0-r1 | repo `etl/sources/` |
| ETL Spec | `Layer0_ETL_Spec_v3.md` | v1.3.1 | project |

**Key commits on `main`:**
- `c1e0e54` — `discipline_substitutes` UNIQUE widening (includes `substitute_name`)
- `224a776` — `.vercel/` in `.gitignore`
- `dea7eeb` — taper validator threshold + vocab transforms + Cognitive category
- `a3dcbeb` — v1.3.1 dev run report
- `19f81d6` — merged fixes branch tip

**Run reports:**
- Dev v1.3.1: `etl/reports/run-1.3.1-20260508-221304.md`
- Prod v1.3.1: `etl/reports/run-1.3.1-20260509-020249.md`

**Final validator state (both dev and prod):**
- `sum_to_100`: 33/33 PASS
- `vocab_alignment`: 245 exercises + 36 sport names, 0 WARN
- `substitution_fks`: 91/91 PASS
- `training_gap_fks`: 3/3 PASS
- `contraindicated_conditions`: 245/245 PASS
- `default_inclusion`: 195/195 PASS

127/127 unit tests pass.

---

## Decisions baked in this session — do NOT relitigate

- **`discipline_substitutes` UNIQUE key includes `substitute_name`.** Sub-variants of the same substitute discipline (e.g., D-023→D-001 with "(sustained downhill)" 0.85 vs. "(rolling)" 0.30) are disambiguated via `substitute_name`, not via sub-discipline IDs. Don't propose adding sub-IDs unless plan-gen testing surfaces a real problem.
- **Taper-phase threshold in `sum_to_100` is ≥90%, other phases ≥100%.** Taper-band undershoot is expected source-curation behavior because volume drops asymmetrically across disciplines during taper. Threshold lowering is the documented response, not source patching.
- **`Cognitive` is a 12th canonical health condition category, distinct from `Cognitive / Mental health`.** They mean different things:
  - `Cognitive / Mental health` — mood, anxiety, depression, ADHD
  - `Cognitive` — TBI, post-concussion processing-speed, cognitive impairment affecting drill execution
  
  Layer 1 prompts that filter on health conditions must handle both as distinct. **TODO for Layer 1: add a one-line disambiguation note in vocab spec the first time prompt design touches health-condition filtering.**
- **Vocab transforms in `vocabulary_transforms.py`:**
  - `Sciatica` → aliased to `Neurological`
  - `Lungs` → aliased to `Respiratory`
  - `Saddle`, `Goggle`, `Blister`, `Core Temperature` → in `_CONTRA_DROP` (gear/environmental tokens, not health conditions)
- **`phase_load_allocation` keeps all 195 rows** including aggregator and EXCLUDED-default rows; `sum_to_100` and `default_inclusion` validators exempt aggregators. Don't propose filtering at extract time.
- **Weekly-total expected count is `~116`, not `~152`.** PLA works at sub-format level (33 sport blocks), not Sports Index level (38 sports). Triage guide baseline updated. The 4 known parser failures (Swimrun, Off-Road Multisport, OWS 10km, OWS 25km) account for all 16 missing rows from the 132-row ceiling.

---

## Carryover — known leftovers

| # | Item | Status |
|---|---|---|
| 1 | Governing Bodies | Carryover; FAQ-feature-pending |
| 2 | Race / Event Formats | Carryover |
| 3 | Pairing Matrix gap (D-018+) | Carryover; Sheet 4 still doesn't cover D-018+ |
| 4 | Vertical Gain in Layer 1 | Carryover; Layer 1 design |
| 6 | Sheet 3 col 7 deprecation | Carryover |
| 9 | `stimulus_components` populate | Deferred; populate when plan-gen needs it |
| 10 | `substitute_covers` populate | Pairs with #9 |
| 11 | Multi-substitute composition algorithm | Deferred to plan-gen workstream |
| 12 | D-008b pairing matrix review | Not blocking; whitewater coach review |
| 13 | AR D-008b phase load tuning | Not blocking; whitewater AR data |
| 14 | Sport-context substitution overrides | Deferred until plan-gen testing signal |
| 15 | Health Conditions UI gap | Launch-blocker; product workstream |
| 19 | Sub-ID naming convention | Process note |
| 20 | Caching layer | Deferred; design cache-friendly from day 1 |
| 21 | Sheet 7 deprecation | Banner applied; full deletion deferred |

**New small carryover from this session:**
- 4 weekly-total parse failures (Swimrun, Off-Road Multisport, OWS 10km / 25km). Multi-tier and km-volume formats. Not in Layer 1 critical path. Treat as manually-handled overrides if plan-gen ever needs them.
- 3 dropped duplicates each in `sport_discipline_map` (Triathlon D-002, LDC D-005/D-006) and `sport_exercise_map` (EX163/Canoeing, EX023/Fencing, EX207/XC Skiing). Documented; first-seen wins.

---

## Next workstream — Layer 1 prompt design

The locked sequence has been: tactical populate → spec → ETL → **Layer 1 prompt design**. Layer 0 is now consumable; Layer 1 is unblocked.

Per `Athlete_Onboarding_Data_Spec_v2.md` v2.5, the Layer 1 data model is locked. What's not yet specified is the prompt-by-prompt design — how each onboarding step queries Layer 0, what payload it returns, how the LLM uses each query result, and how partial-update logic applies.

**Recommended first prompt: 2A — Discipline Classifier.**
- Small input surface (athlete-stated sport / event / target race)
- Well-bounded output (resolved discipline IDs + applicability flags)
- Hits multiple Layer 0 tables: `sports`, `disciplines`, `sport_discipline_map`, `sport_name_aliases`
- Real integration test of the Layer 0 query layer
- Outputs feed directly into downstream Layer 1 prompts

**Adjacent workstreams that could pull priority before 2A:**
- Open Item #9/#10: `stimulus_components` / `substitute_covers` populate — closes the Layer 0 → plan-gen contract earlier. ~60–90 min curation, not blocking either way.
- Open Item #21: Sheet 7 deletion — full migration audit + delete. ~30 min audit + delete. Pure cleanup.

These can fit before 2A without meaningfully delaying Layer 1. Andy's call on sequencing.

**Open architectural question for Layer 1 kickoff:**
Start with 2A directly, or do one of the small adjacent items first?

---

## Process notes for the new session

- **Andy's preferences:** direct, judgment-focused, no praise/hype, gut check at end of recommendations, plain-English when topics get technical
- **No artifact / no document creation for explanations.** Andy reads in chat. Documents only when there's a real artifact to share.
- **Read this doc + `Athlete_Onboarding_Data_Spec_v2.md` + `Layer0_to_PlanGen_Contract_Preview.md` before starting Layer 1 design.** The spec defines what to build; the contract preview shows what plan-gen needs to consume.
- **Layer 1 design pattern from earlier sessions:** for each prompt, define (a) input contract from upstream, (b) Layer 0 queries needed, (c) LLM prompt structure, (d) output payload contract for downstream, (e) partial-update invalidation rules. Don't shortcut to LLM-prompt-text first — define interfaces.

---

## Quick orientation when the new session opens

When Andy opens the new chat (most likely with a request to start Layer 1 design):

1. Read this handoff + spec v2.5 + contract preview before responding.
2. Confirm starting point: 2A directly, or adjacent item first.
3. If 2A: define the input/output contracts before drafting prompt text.
4. Don't propose schema changes to Layer 0 unless Layer 1 design genuinely demands one — Layer 0 is canonical.
5. Per Andy's preferences: end recommendations with a gut check (risks, what we might be missing, best argument against).
