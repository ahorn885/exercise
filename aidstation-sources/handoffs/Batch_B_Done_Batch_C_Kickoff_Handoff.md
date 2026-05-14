# Batch B Done → Batch C Kickoff Handoff

**Date:** 2026-05-10
**Predecessor:** `Batch_A_Done_Batches_BC_Kickoff_Handoff.md`
**Next session priority:** Batch C (bike/load curation), then spec v4 consolidation

---

## What shipped this session

Batch B (technique-focus migration) is fully landed in production. Four scripts ran clean:

| Script | Result |
|---|---|
| `migrate_discipline_technique_foci.sql` | New table `layer0.discipline_technique_foci` created with GIN index on `discipline_ids` and partial index on active rows |
| `populate_discipline_technique_foci.sql` | 35 focus rows inserted at `etl_version = '0B-v19.B'` |
| `migrate_drop_technique_exercises.sql` | 52 rows superseded in `layer0.exercises` and corresponding rows in `sport_exercise_map` |
| `update_retype_keeper_exercises.sql` (v2) | 13 exercises retyped from `Technical / Skill` to load-bearing types via supersede + reinsert at `0B-v19.B` |

**Spec patch:** `Layer0_ETL_Spec_v3_Patch_Batch_B.md` documents the new table schema (§4.15), the `Technical / Skill` type deprecation (§4.12), the §4.12 spec-vs-deployed discrepancies, and three new §7 open items (O: Rowing discipline gap, P: Layer 4 foci selection logic, Q: foci edit workflow).

---

## Schema discoveries banked

### Production schema for `layer0.exercises` (verified 2026-05-10)

The v3 spec §4.12 has diverged materially from production. Use this column list as the reference for any future migration touching the table:

```
exercise_id, exercise_name, exercise_type,
movement_patterns, primary_muscles, secondary_muscles,
equipment_required, injury_flags_text,
contraindicated_parts, contraindicated_conditions,
equipment_substitutes, physical_proxies,
progression_exercise_id, progression_exercise_name,
regression_exercise_id, regression_exercise_name,
sport_count, coaching_cues,
terrain_required, equipment_substitutes_structured,
etl_version, etl_run_at, superseded_at
```

UNIQUE: `(exercise_id, etl_version)` — table-level only. No column-level UNIQUE on `exercise_id`. Multi-version coexistence works.

### Open verification

`primary_muscles` / `secondary_muscles` deployed type wasn't captured (TEXT vs TEXT[]). Doesn't matter for Batch B (SELECT copy is type-agnostic); worth confirming if a future migration needs to write to those columns.

---

## Process change: schema-introspection doctrine

Banked from this session. The pre-flight block in `update_retype_keeper_exercises.sql` v2 is the canonical pattern for any future Layer 0 migration that references columns by name in INSERT or UPDATE.

**Doctrine:**
1. Before writing column lists, dump the deployed schema (`\d layer0.<table>`).
2. If spec disagrees with deployed, **deployed wins for the script**; spec gets a correction in a patch document.
3. Open every column-touching script with a pre-flight `DO $$ ... $$` block that:
   - Verifies every expected column exists in `information_schema.columns`
   - Verifies any `ON CONFLICT` target exists in `pg_indexes` with the expected column ordering
   - Aborts the whole transaction with a specific error if either check fails
4. Treat lesson "trust spec over precedent" as scoped to spec-vs-legacy-code comparisons. It does not apply to spec-vs-deployed.

The K1/K2 bugs and the v1 retype script bug all fall in the same blast radius. The pre-flight pattern eliminates this class.

---

## Open items (carried + new)

### Carried from prior handoff

| # | Item | Status |
|---|---|---|
| — | Batch C (10-row bike/load curation per primary/substitute split table) | Scoped, not started — **next session priority** |
| — | 2C spec consolidation | Scoped, not written |
| — | ETL spec §8 corrections | Pending — fold into v4 |
| — | §J onboarding spec | Roadmap |
| — | UI design phase | Roadmap |
| — | Hotel-as-shared-entity feature | Roadmap |

### New from Batch B

| # | Item | Owner | Status |
|---|---|---|---|
| O | Rowing discipline missing from Sports Framework — TF-033 carries empty `discipline_ids[]` | Framework v11 | Flagged, not blocking |
| P | Layer 4 selection logic for foci (filter/priority algorithm + plan-gen integration) | Plan-gen design | Scoped, not started |
| Q | Foci edit workflow — decide whether to build a spreadsheet-sourced ETL pipeline or stay with hand-curated SQL | Roadmap | Deferred |
| R | Confirm `primary_muscles` / `secondary_muscles` types in deployed schema | This session's gap | Quick check on next DB session |
| S | Sweep other Layer 0 tables for spec drift before any further migrations against them | Process | Recommend before Batch C if it touches new tables |
| T | Exercise-name refresh pass — 13 retyped exercises still carry "Technique Drill" naming that's misleading after retype (e.g., EX051 "Uphill Running Technique Drill" is now Aerobic / Endurance) | Content pass | Future, not blocking |

### Spec v4 consolidation backlog

When v4 is written, fold in:
- Batch A patch (sport_exercise_map header residue cleanup, Climbing — roped also_satisfies, Bench press rack equipment)
- Batch B patch (this session — foci table, Technical/Skill deprecation, §4.12 schema corrections)
- All §8 consumer-table corrections that were batched for after Layer 2 nodes lock
- The schema-introspection doctrine as a §6 process note

Recommended trigger for v4 write: after 2D and 2E lock (still the prior handoff's recommendation; nothing in Batch B changes that).

---

## Suggested next-session sequence

1. **Pre-flight check:** confirm `primary_muscles` / `secondary_muscles` types and sweep other Layer 0 tables for any obvious spec drift (open items R, S).
2. **Batch C:** 10-row bike/load curation. Drop list and primary/substitute split table are in `Batch_A_Done_Batches_BC_Kickoff_Handoff.md`. Scripts will touch `layer0.exercises` (drops + retypes/edits) and `layer0.sport_exercise_map` (denormalized exercise_type sync). Use the pre-flight introspection pattern from Batch B.
3. **Spec v4 consolidation** OR continue with the next blocker (Layer 4 foci selection logic, 2C consolidation, etc.) — whatever's the highest-leverage thing next.

---

## Files referenced

**This session's outputs (in `/mnt/user-data/outputs/`, also worth committing to project):**
- `migrate_discipline_technique_foci.sql`
- `populate_discipline_technique_foci.sql`
- `migrate_drop_technique_exercises.sql`
- `update_retype_keeper_exercises.sql` (v2 — has the pre-flight pattern)
- `Layer0_ETL_Spec_v3_Patch_Batch_B.md`

**Authoritative project files:**
- `Layer0_ETL_Spec_v3.md` — has known §4.12 errors documented in the patch
- `Batch_A_Done_Batches_BC_Kickoff_Handoff.md` — Batch C spec lives here
- `AR_Exercise_Database_v19.xlsx` — Exercise Master + Sport-Exercise Map
- `Sports_Framework_v10.xlsx` — Discipline Library (Rowing gap noted)

---

## Working preferences (for fresh-session priming)

Andy's preferences (from `userPreferences`):
- Direct, useful, no praise/hype/filler
- Match confidence to reality; flag uncertainty briefly
- Tell the truth even if an idea is weak
- Recommendations: focus on judgment, key tradeoffs, second-order effects
- End plans/evaluations with: risks, what we might be missing, best argument against
- Flag assumptions and blind spots
- When chat gets long or messy: prompt for a handoff and start fresh

Other process notes from working with Andy:
- Spec-first philosophy — architecture → prompts → implementation; resists shortcuts
- Idempotent SQL with verify blocks is house style
- Files staged in `/home/claude/<batch>/` then copied to `/mnt/user-data/outputs/` then `present_files`
- Andy runs scripts and reports back; Claude doesn't have DB access

---

*End of Batch B handoff. Start fresh with this and `Batch_A_Done_Batches_BC_Kickoff_Handoff.md` (for the Batch C spec) at the next session.*
