# Handoff — D-26 Done / D-22 Pass 1 Done / FC-1a Kickoff

**Date:** 2026-05-11
**Outgoing session:** §I/J/K/L re-integration (drift recovery) + D-26 deployment + D-22 Pass 1 sampling
**Next session:** FC-1a — ETL bug fixes batch (D-04, D-05, D-06, D-07, D-08, D-12, D-13, D-14, D-15, D-16) + D-03 build-or-drop decision

---

## TL;DR

1. **Drift recovered.** Session-start verification (rule #9) caught that the prior session's claimed §I/J/K/L integration + D-36 + Control_Spec §9/§10 edits never landed. Recovered prior session's actual content via `conversation_search` and re-applied. All three files (`Athlete_Onboarding_Data_Spec_v2.md`, `Project_Backlog.md`, `Control_Spec.md`) uploaded.
2. **D-26 deployed.** `layer0.supplement_vocabulary` table + 25 seed entries shipped to Neon dev. Migration SQL already in `main` from commit 50785df (prior session committed but never deployed); Andy ran it manually in Neon UI this session (CC sandbox can't reach Neon). Verified: 25 active rows, category distribution matches spec exactly. D-26 resolution edit applied to `Project_Backlog.md`.
3. **D-22 Pass 1 sampling done.** 57 of 159 rows classified. 11 house rules locked, all confirmed by Andy. Major findings: population is 159, not ~600 as handoff originally estimated; 100% flag-rate (every row has non-empty `injury_flags_text`); ~14% ambiguity rate at calibrated state.
4. **D-37 added** to backlog: source-data hygiene for `injury_flags_text`. Preserve non-movement signals (Cardiac, Skin, Blister, Cognitive) by relocating to separate structured columns rather than dropping.
5. **FC-1a / FC-1b split confirmed.** Next session is FC-1a (ETL bug fixes). D-22 batch 2 + D-23 + migration SQL land in FC-1b.
6. **Session-start verification (rule #9): one drift caught and resolved.** Loop is functioning.

---

## Work completed this session

### Drift recovery (§I/J/K/L + bookkeeping)

The prior session's handoff claimed:
- §I/§J/§K/§L integrated into `Athlete_Onboarding_Data_Spec_v2.md` with 4 deltas (Δ-1 weight sub-field, Δ-2 K.1 enum extension, Δ-3 drop J.5, Δ-4 icebox D-36)
- D-36 added to `Project_Backlog.md`
- `Control_Spec.md` §9 doc map flipped, §10 file-diff rule bullet added
- Memory rule #11 added (this was the only thing that actually landed)

Verification at session start showed **only the memory rule landed**. Recovered prior session's actual integration content via `conversation_search` (chat `c57c7542`). Re-applied all edits including verbatim 8 curated weight-range items (Dumbbell, Kettlebell, Weight Plate, Resistance Band, Medicine Ball, Sandbag, Weight Vest, Slam Ball), verbatim D-36 row, verbatim Control_Spec §9 flip. Composed the §10 file-diff bullet (this part wasn't recovered verbatim).

All three files uploaded and re-verified on disk.

### D-26 — `supplement_vocabulary` deployed

- Generated migration SQL `migrate_supplement_vocabulary.sql` matching `Supplement_Vocabulary_Spec.md`.
- Andy uploaded to `etl/sources/` on GitHub (no diff vs existing — prior session had already committed the SQL).
- Andy ran SQL manually in Neon (CC sandbox can't reach Neon over TCP/5432).
- Pre-check confirmed table did not exist. Migration ran clean inside `BEGIN; ... COMMIT;`. Post-run distribution matches spec: 5 Performance, 9 Recovery, 5 Health, 3 Race-day, 1 GI, 1 Sleep, 1 Hormonal-Stress = 25 total.
- Verify NOTICE not captured in buffer, but transaction-semantics ensure functional confirmation (RAISE EXCEPTION would have aborted; COMMIT didn't).
- D-26 resolution edit applied to `Project_Backlog.md` (line 60, plus consolidation edits at lines 121, 125, 127).

### D-22 — Pass 1 sampling

- Direct workflow (skipped CC for sampling queries since CC can't run Neon SQL; Andy ran queries in Neon UI).
- **Population discovery:** 159 active rows in `layer0.exercises`. Handoff's "~600 cells" estimate was wrong. Memory's "245" was stale. Correct count is 159.
- **100% flag rate:** every row has non-empty `injury_flags_text`. No empty-flag cohort. Every row is real classification work.
- **Length distribution:** 91 medium (31-100 chars), 67 long (101-300), 1 verbose (>300), 0 short (<=30).
- **14 `exercise_type` values** with skew (top 3 = 60% of table).
- **Stratified sample of 57 rows** pulled (slight overshoot vs 50 target — fine for our purposes).
- **57 rows classified by Claude, reviewed and edited by Andy.** 8 rows had real judgment calls during Pass 1, all resolved.
- **11 house rules locked.** Documented in `D22_Curation_Reference.md`.
- **Pass 1 baseline** preserved verbatim in `D22_Curation_Reference.md` for direct use in eventual migration SQL.

### Bookkeeping edits

- `Project_Backlog.md`:
  - D-22 row updated with correct population (159, not 600), Pass 1 progress note, FC-1b targeting
  - D-26 marked ✅ Resolved (3 places)
  - D-36 added (this session, recovered from drift)
  - D-37 added (this session, new — source-data hygiene)
  - FC-1 work plan section updated: FC-1a/FC-1b split confirmed, ETL fixes named explicitly
- `Control_Spec.md`:
  - §9 doc map flipped (I/J/K/L now drafted)
  - §10 file-diff handoff bullet added
- `Athlete_Onboarding_Data_Spec_v2.md`:
  - §I/§J/§K/§L integrated with 4 deltas applied
  - Drafting status table flipped

---

## FC-1a scope (next session)

ETL bug fixes batch. Mostly mechanical SQL/spec changes, lower review burden than D-22 curation.

| ID | Item | Type |
|---|---|---|
| D-04 | `phase_load_allocation.phase_` prefix removal (pure rename) | SQL migration |
| D-05 | Aggregator-row filter into ETL itself (removes WEEKLY TOTAL rows; retires the defensive standing-rule filter) | ETL code change |
| D-06 | `phase_load_weekly_totals` rename `hours_low/high` → `weekly_low_hours/high_hours` | SQL migration |
| D-07 | 4 sports missing weekly_totals rows (Off-Road/AR Non-Nav, Open Water Swim 10km, 25km, Swimrun) — parser bug investigation | ETL parser fix |
| D-08 | 3 missing rows in `sport_discipline_map` (LDE Cycling -2, Triathlon -1) — data investigation | Data investigation |
| D-12 | Add `sport_name_aliases` schema to v4 §4 | Spec doc only |
| D-13 | `discipline_technique_foci` patch correction (`source_exercise_ids[]` array; `audit_log` col) | SQL migration |
| D-14 | `cross_sport_properties` `source_text` dedup decision | Data decision + maybe SQL |
| D-15 | `discipline_substitutes` UNIQUE constraint review | SQL inspection + maybe migration |
| D-16 | `primary_muscles` / `secondary_muscles` cols added to v4 §4.12 schema block | Spec doc only |
| D-03 | Build-or-drop decision on `is_conditional` / `vertical_gain_notes` (spec-defined, not deployed) | Decision + spec |

**Sequencing recommendation:**
1. Spec-only items first (D-12, D-16) — pure markdown updates, no deployed-DB risk. ~30 min.
2. Pure renames (D-04, D-06) — quick SQL migrations, easy verify. ~30 min.
3. Filter promotion (D-05) — ETL code change + retire query-layer defensive filter. ~30 min.
4. Investigation items (D-07, D-08, D-14, D-15) — varying scope, surface findings inline. ~1-2 hr depending on what's found.
5. Patch corrections (D-13) — SQL migration. ~30 min.
6. Decision item (D-03) — depends on what investigation reveals; may park as deferred. ~15 min.

**Total estimated effort:** 3-5 hours focused work. Splittable if needed; no item depends on another.

---

## FC-1b scope (session after FC-1a)

Pure curation work. Heavy review burden.

| ID | Item |
|---|---|
| D-22 | D-22 Pass 2 — classify remaining 102 rows; write & deploy migration SQL |
| D-23 | `disciplines.body_parts_at_risk TEXT[]` — ~150 cells curation; same workflow pattern as D-22 |

D-22 Pass 1 baseline (57 rows already classified, locked) is in `D22_Curation_Reference.md`. Pass 2 starts by querying the remaining 102 rows (`exercise_id NOT IN (Pass 1 list)`).

---

## File edits the next session will need to make (rule #11)

Apply each one only after the corresponding work is complete and verified.

### When D-04 (`phase_load_allocation.phase_` prefix removal) lands

**File:** `/mnt/project/Project_Backlog.md`

```
old_string:
| D-04 | **`phase_load_allocation` ETL emitting wrong column names** — using `phase_*` prefixed names (e.g., `phase_1_hours_low`) when spec and code consumers expect un-prefixed names (e.g., `phase_1_lower_bound`). Workaround in 2A code is the existing rename mapper. **STATUS: pending FC-1 ETL fix.** | High | 🟡 Deferred | 2A, 2D, 2E, 4 | Pure rename via ETL re-run with corrected output. Mandatory: re-run ETL after fix; verify column rename in deployed schema; retire rename mapper in 2A code. |

new_string:
| D-04 | **`phase_load_allocation` ETL column naming fixed in FC-1a.** | High | ✅ Resolved (FC-1a, [DATE]) | 2A, 2D, 2E, 4 | ETL re-run produced correctly-named columns. 2A rename mapper retired. Migration: see commit [SHA]. |
```

### When D-05 (aggregator filter in ETL) lands

**File:** `/mnt/project/Control_Spec.md`

```
old_string:
- **D-05 aggregator filter** until ETL fix lands (will retire in FC-1 per file edits above).

new_string:
- **D-05 aggregator filter — REMOVED (FC-1a, [DATE]).** ETL now drops `WEEKLY TOTAL TARGET` rows at load time. Existing query-layer filters are now redundant but harmless; leave in place until FC-2 spec rewrite to keep diffs scoped.
```

**File:** `/mnt/project/Project_Backlog.md` — mark D-05 resolved with the same pattern as D-04.

### When other D-items land

Same resolution-edit pattern as D-04 / D-05. For each item:
1. Find the row in `Project_Backlog.md` Open items table.
2. Replace the row content with a one-line "Resolved (FC-1a, [DATE])" status + brief notes (migration commit SHA, what changed).
3. Keep the row in place (don't delete) — ID stability for cross-references.

---

## Files NOT to touch in FC-1a

- `Athlete_Onboarding_Data_Spec_v2.md` — §§I/J/K/L locked. §§D-F pending but not FC-1 scope.
- `Layer2A_Spec.md` through `Layer2E_Spec.md` — drafted. ETL fixes may render some spec footnotes redundant; address those in FC-2, not FC-1a.
- `D22_Curation_Reference.md` — locked baseline. Don't touch until FC-1b.
- `Supplement_Vocabulary_Spec.md` — D-26 done. No further changes needed.

---

## Pre-work reading order for FC-1a

1. **`Project_Backlog.md`** — Open items table, focus on D-03 through D-17.
2. **`Layer0_Deployed_Schema_and_Drift_Report.md`** — current schema state. Each FC-1a item references a section.
3. **`Build_Prep_Handoff.md`** — workflow for ETL re-runs and report-file inspection.
4. **`populate_equipment_items_K2_additions.sql`** — house style for idempotent SQL with verify blocks.

---

## Standing rules (still in effect — Control_Spec §8.2)

- **D-05 aggregator filter** until ETL fix lands (will retire in FC-1a per file edits above).
- **Sport naming convention** (D-17): top-level vs sub-format split between Sheet 3 and Sheet 5 tables. Code-side strip pattern in 2A §5.1.
- **D-21 reconciliation:** 2D/2E match on enum *values*, not column names.
- **No FKs in layer0:** TEXT-based by design.
- **Pre-flight introspection before any Layer 0 migration.**

## Memory rules in effect

- **#9** session-start verification — spot-check prior handoff against on-disk state (worked this session, caught 4-of-5 claimed edits hadn't landed)
- **#10** session-end verification — don't claim edits landed unless they did
- **#11** handoff-as-file-diff — defer with mechanically-applicable instructions, not narrative

---

## Workflow notes

**Andy's setup:** Doing all work via the web Claude chat + Claude Code on web (not desktop apps, not CLI). CC has GitHub access but cannot reach Neon over TCP/5432. For Neon work, the pattern is:
1. Claude (here) generates SQL or query
2. Andy uploads SQL to GitHub `/etl/sources/` if it's a migration file; pastes query directly into Neon UI if it's a one-off query
3. Andy runs the SQL/query manually in Neon
4. Andy pastes results back to Claude (here) — not CC

CC's role is repo work: file location conventions, commits, branch management. CC's role is NOT DB execution.

**Implication for FC-1a:** ETL bug fixes that require running migrations against Neon will need Andy to execute manually after Claude (here) writes the SQL. CC can stage files and commit, but the DB-touching step lives with Andy. **Make sure any handoff that claims a migration deployed actually documents whether deploy happened — that was the IJKL-drift root cause (committed but not deployed, no surface tracked it).**

---

## State of files in project as of this handoff

| File | Status |
|---|---|
| `Control_Spec.md` | ✅ Current (§9 doc map + §10 file-diff rule updated this session) |
| `Project_Backlog.md` | ✅ Current (D-22 progress, D-26 resolved, D-36 added, D-37 added) |
| `Athlete_Onboarding_Data_Spec_v2.md` | ⏳ Partial — §§A-C/G-H/I/J/K/L/M/N drafted; §§D-F pending (not blocking FC-1) |
| `Layer2A_Spec.md` through `Layer2E_Spec.md` | ✅ All drafted |
| `Supplement_Vocabulary_Spec.md` | ✅ Drafted (D-26 deployed) |
| `Section_I_Audit.md` | ✅ Drafted |
| `D22_Curation_Reference.md` | ✅ **NEW THIS SESSION** — house rules locked, 57-row Pass 1 baseline |
| `Sections_IJKL_Groups23_v2_Batch.md` | ✅ Source material — content now in canonical spec; keep for history |
| `Layer0_ETL_Spec_v3.md` | ✅ Current (v4 pending FC-2) |
| `Layer0_Deployed_Schema_and_Drift_Report.md` | ✅ Current |

**Deployed Neon state changes this session:**
- New table `layer0.supplement_vocabulary` (25 active rows, etl_version `supp_vocab.v1.FC1`)

---

## Open items requiring Andy decision before or during next session

| # | Item | When |
|---|---|---|
| 1 | D-03 build-or-drop: do `is_conditional` and `vertical_gain_notes` get built in ETL, or get dropped from spec? | During FC-1a |
| 2 | D-14 dedup decision: how to handle duplicate `source_text` in `cross_sport_properties` | During FC-1a |
| 3 | D-15 UNIQUE constraint review: tighten or leave wide on `discipline_substitutes` | During FC-1a |

---

## Gut check

**What this session got right:**
- Session-start verification (rule #9) caught the drift cleanly. The loop works.
- Recovered prior session's actual content via `conversation_search` instead of regenerating from scratch — preserved the 8 weight items and D-36 verbatim text that were already approved.
- D-26 deployed despite CC sandbox limitations. Workflow worked.
- D-22 Pass 1 surfaced a major recalibration (population 159, not 600) before we committed to a wrong-scope curation plan.
- House rules locked with Andy's review on each — Pass 2 inherits real constraints, not Claude's speculation.

**Risks:**
- FC-1a has 11 items. If any one of them surfaces a deeper issue (e.g., D-07's parser bug is more than a 30-min fix), the session balloons. Build in checkpoints — after each item lands, decide whether to continue or pause.
- The "Andy runs migrations manually in Neon" workflow is the single biggest source of drift risk. The IJKL-drift root cause was a migration that got committed but not deployed because that surface wasn't tracked. **Recommendation:** every handoff that includes a migration commit must explicitly state whether the migration was deployed to Neon, with timestamp. Treat "committed but not deployed" as a real intermediate state, not the same as "shipped."
- D-22 Pass 1 baseline depends on Claude's classification + Andy's review pace remaining consistent. If Pass 2 reveals systematic Pass 1 errors, we revisit. Low risk given Pass 1 already had ~14% review rate.

**What might be missing:**
- D-23 (`body_parts_at_risk` curation) hasn't been scoped at the same depth as D-22 was today. We know population is ~31 disciplines × N body parts each, but the actual curation pattern isn't documented yet. May want a brief D-23 reference doc analogous to `D22_Curation_Reference.md` before kicking off FC-1b.
- D-37 (source-data hygiene) is now a real Layer 0 design question. Where do Cardiac/Skin/Cognitive flags live? Probably new structured columns, but exact schema TBD. Should be discussed before FC-1b or it'll snag the migration design.

**Best argument against today's plan:**
We committed a lot to documentation today (3 spec files re-uploaded, 1 new reference doc, 1 handoff doc). If any of those didn't actually save to project knowledge, we're back in IJKL-drift territory next session. **Rule #9 verification at FC-1a session start should explicitly check the D-22 reference doc + D-37 backlog row + D-22 row update landed.** Make that the first action of the next session.

---

*End of handoff. Next session: FC-1a. Read `Project_Backlog.md` Open items D-03 through D-17 first. Start with spec-only items (D-12, D-16), then pure renames (D-04, D-06), then progressively harder items.*
