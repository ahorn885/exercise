# Session Handoff — v3 Spec + Populate Package + Contract Preview

**Date:** 2026-05-07
**Predecessor:** `Layer0_Query_Decisions_Handoff.md`
**Status:** Three deliverables produced. Step 1d (contraindicated_conditions verify) requires `AR_Exercise_Database_v17.xlsx` upload. Sports Framework v9 → v10 populate either applied by Andy directly or by Claude on upload.
**Next chat starts with:** apply v10 populate, run 1d verification, ETL re-run.

---

## What shipped this session

### 1. `Layer0_ETL_Spec_v3.md`
Full spec rewrite. Replaces `Layer0_ETL_Spec_v2.md`. Covers:
- Source bump v6 → v10
- Two new tables (`discipline_substitutes`, `discipline_training_gaps`)
- Five new columns on existing tables (sports classifications x4, phase_load `default_inclusion`)
- Two new candidate columns from contract preview (`disciplines.stimulus_components`, `discipline_substitutes.substitute_covers`) — schema in, populate deferred
- Full §5 Query Layer spec with five locked decisions + per-consumer typed function signatures + canonical Layer 4 payload shape
- ETL run order updated (19 steps across 3 phases; 2 new tables in Phase 2)
- Validation passes updated for new tables and `contraindicated_conditions`
- ETL re-run plan from current state (~half a coding session)
- 20-row Open Items table (5 carryover from v2, 12 new)

### 2. `Tactical_Populate_Package.md`
Exact values for steps 1a, 1b, 1c. Andy applies to v9.xlsx → v10.xlsx, or uploads v9 and Claude applies.
- **1a:** Sport classifications for all 33 active sports (4 columns each)
- **1b:** `default_inclusion` rule + AR-specific lock + per-sport application notes
- **1c:** D-004b Pool Sprint Swimming substitute row (D-004b → D-004 at 0.5)
- **1d:** Verification approach pending xlsx upload

### 3. `Layer0_to_PlanGen_Contract_Preview.md`
The 30-min insurance task from the recommendation. Surfaced two columns Layer 0 needs to expose for plan-gen multi-substitute composition to work cleanly: `stimulus_components` on disciplines, `substitute_covers` on substitutes. Both added to v3 spec (NULL-able). Population deferred — not blocking ETL re-run.

---

## What's left

### Immediate (Andy's call to make)

1. **Apply v10 populate.** Either:
   - Upload `Sports_Framework_v9.xlsx` — Claude produces `Sports_Framework_v10.xlsx` with all 1a/1b/1c changes applied
   - Or apply manually using `Tactical_Populate_Package.md`
2. **Upload `AR_Exercise_Database_v17.xlsx`** — Claude runs 1d verification (5–10 exercise spot-check on `contraindicated_conditions`)
3. **Sanity-check 1a values** — particularly the judgment calls flagged in `Tactical_Populate_Package.md` §1a "Decisions worth a quick second look" (Modern Pentathlon = Mixed; Skimo Sprint = Technical-dominant; AR includes climbing; Fell Running = Both)

### Then (the build)

4. **Upload `Layer0_ETL_Spec_v3.md` to project.**
5. **ETL re-run.** Code session to:
   - Apply schema migration (new tables + cols, NULL-able where appropriate)
   - Build Sheet 5C Weekly Total Target parser
   - Build Sheet 5D Notes splitter
   - Re-extract all 0A sheets, write with new etl_version
   - Run validation passes
   - Triage warnings (expected near-zero given prior audit work)

### Deferred (not blocking)

6. `stimulus_components` populate (~60–90 min curation across 30 disciplines)
7. `substitute_covers` populate (~30 min after #6)
8. D-008b pairing matrix review (whitewater AR coach, when one is available)
9. AR D-008b phase load tuning (whitewater AR race data, when available)
10. Sport-context substitution overrides (when plan-gen testing shows v1 too coarse)

---

## Files in /mnt/user-data/outputs/

| File | Purpose |
|---|---|
| `Layer0_ETL_Spec_v3.md` | The new spec — replaces v2 in project |
| `Tactical_Populate_Package.md` | Values for 1a/1b/1c; instructions for 1d |
| `Layer0_to_PlanGen_Contract_Preview.md` | Contract design rationale; surfaces 2 columns added to v3 spec |
| `Session_Handoff.md` | This doc |

---

## Key design calls made this session

1. **`stimulus_components` and `substitute_covers` go in v3 spec, NULL-able.** Per contract preview — cheap insurance against a future re-ETL when plan-gen design surfaces the gap. Population deferred since plan-gen consumer doesn't exist yet.
2. **Four-column sport classification model covers everything `sport_family` would have done.** Confirmed via the `derived_sport_family` CASE expression in `Tactical_Populate_Package.md` §1a. No need for a single label column.
3. **`default_inclusion` rule simplified to two values in practice (`included` / `excluded`).** `prompt_required` reserved for future use; no current discipline needs it. AR's "athlete opts in to anything beyond the locked four" is the universal pattern.
4. **Sheet 5C and 5D parsers added to pre-ETL prep.** Weekly Total Target free-text → structured hour bands; Notes column → prescription_note + audit_log split. Both are net-new ETL code (~1–2 hrs).

---

## Process notes for next session

- Andy's preferences locked: direct, judgment-focused, no praise/hype, gut check at end of recommendations
- Sports Framework xlsx is the source of truth — never reconstruct from prose; always work from the actual file
- Versioning rule: every change increments. v9 → v10. Spec v2 → v3. Never overwrite.
- Project files are read-only at session start; deliverables go in `/mnt/user-data/outputs/` and Andy uploads to project to make them canonical
- The contract-preview pattern (think through downstream consumer needs before committing to schema) is worth keeping for future schema decisions

---

## Gut check on the session

- **What's strong:** v3 spec is comprehensive; populate package gives Andy real values not just instructions; contract preview surfaced two real schema gaps before they became re-ETL triggers
- **What's weak:** without seeing v9.xlsx, the per-sport conditional row identification in 1b is rule-based not row-by-row verified. If any sports have conditional rows I haven't anticipated, the values will be wrong on those rows. Mitigation: the rule itself is correct; the application step verifies row-by-row.
- **Best argument against the session's output:** the contract preview added two columns the system doesn't need yet. If plan-gen design surfaces a totally different shape, we re-ETL anyway. Defense: NULL-able cols cost nothing; the design exercise itself was worth doing whether or not the columns survive contact with plan-gen design.
- **What to flag for future-Claude:** if a session opens and `stimulus_components` is still unpopulated when plan-gen design starts, do that populate FIRST before plan-gen code. Don't try to build plan-gen against NULL columns — you'll end up with plan-gen logic that pretends the data exists, and then breaks.
