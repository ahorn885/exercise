# Handoff — §I §J §K §L Integrated / FC-1 Kickoff

**Date:** 2026-05-11
**Outgoing session:** Onboarding §I/§J/§K/§L review-and-integrate; memory rule #11 (handoff-as-file-diff) added
**Next session:** FC-1 — final cleanup batch 1 (ETL bug fixes + column promotions blocking 2D/2E implementation)

---

## TL;DR

1. §I, §J, §K, §L are **drafted in `Athlete_Onboarding_Data_Spec_v2.md`** (this session). The 4 deltas from the kickoff handoff (Δ-1 weight sub-field, Δ-2 K.1 enum extension, Δ-3 drop J.5, Δ-4 icebox Role on Team as D-36) all applied.
2. **D-36 added to `Project_Backlog.md`** as ⚪ Wont-Fix (v1) — Role on Team icebox.
3. **`Control_Spec.md` §9 doc map flipped** for §I/J/K/L; §10 Process notes updated to include the new file-diff handoff rule.
4. **Memory rule #11 added** — handoffs that defer file edits must include mechanically-applicable instructions (str_replace blocks or verbatim "replace X with [...]"), not narrative summaries. Companion to #9/#10.
5. **Next session is FC-1.** Three blockers must resolve for 2D/2E implementation: D-22, D-23, D-26. Plus the ETL fix queue (D-04 through D-16 cleanup tier).
6. **Session-start verification (rule #9): clean.** Prior handoff's claimed file updates all landed; no drift detected this session. First time the verify loop returned clean since rule was added.

---

## Work completed this session

### §I/§J/§K/§L integration

| Section | Source | Deltas applied | Lines |
|---|---|---|---|
| §I Lifestyle & Recovery | `Sections_IJKL_Groups23_v2_Batch.md` lines 16–73 | Supplement Protocol field clarified as structured list (FK to `supplement_vocabulary`); §I structured-form contract pointer added (Layer2E §3 + Section_I_Audit) | ~50 |
| §J Locales | Same batch, lines 76–161 (minus J.5) | Δ-1 J.2.1 sub-section added with 8 curated weight-range items; Δ-3 J.5 dropped with explicit note | ~85 |
| §K Locale Schedule | Same batch, lines 166–225 | Δ-2 K.1 constraint enum extended with "Exclude specific locale(s)" + conditional Excluded Locales FK multi-select sub-field | ~55 |
| §L Athlete Network | Same batch, lines 231–262 | Δ-4 backlog pointer added (D-36); Partner-specific Rules description hardened — soft constraint on joint sessions, not just coaching tone | ~25 |

**Drafting status table** at end of canonical spec updated. §§D-F remain ⏳ Pending (lower priority than FC since no Layer 2 node consumes them; they feed Layer 4 plan-gen).

### Bookkeeping
- `Control_Spec.md` §9 doc map: `Athlete_Onboarding_Data_Spec_v2.md` description updated — "§§A-C/G-H/M/N + §§I/J/K/L complete; §§D-F pending"
- `Control_Spec.md` §10 Process notes: new bullet for the file-diff handoff rule
- `Project_Backlog.md` open items table: D-36 added after D-35

### Memory rule #11 added
> When a handoff defers edits, include mechanically-applicable instructions — str_replace-style old_string/new_string blocks for surgical edits, or "replace section X with verbatim content [...]" for restructures. No narrative summaries like "update §2/§3 of Control_Spec" without the new text. Next session executes spec'd edits, doesn't re-derive. Failure is loud (str_replace mismatch) not silent (interpretive drift).

Companion to:
- Rule #9: session-start verification (spot-check prior handoff against on-disk state)
- Rule #10: session-end verification (don't claim edits landed unless they did)

Together: #11 prevents drift from accumulating; #9/#10 catch it if it does.

---

## Open verification notes (not blocking)

**Δ-3 (drop J.5) downstream check:** grepped `Layer2B_Spec.md` and `Layer2C_Spec.md` for any J.5 / session-length references. Zero hits. Δ-3 is safe.

**Δ-1 (weight sub-field) downstream check:** 2C only reads `canonical_name` and `is_universal`; weight sub-field is invisible to 2C. Layer 4 plan-gen consumes it. Documented inline in J.2.1.

**§J shape vs 2B / 2C input contracts:** 2B expects `locale_terrain_ids` as canonical TRN-xxx (✓ matches §J.4); 2C expects `locale_equipment_pool` as canonical equipment names (✓ matches §J.2). No mismatches.

---

## FC-1 scope (next session)

Final cleanup batch 1. Three categories.

### A. Blockers for 2D / 2E implementation (must land before any 2D/2E code)

| ID | Item | Effort estimate |
|---|---|---|
| **D-22** | Curate `exercises.injury_flags_text` → `movement_components TEXT[]` for ~600 cells. Required for 2D set-intersect against B.3 enum tokens. Spec'd in `Layer2D_Spec.md` §5.5/§6. | Largest single item — possible FC-1 / FC-1b split point |
| **D-23** | Curate `disciplines.body_parts_at_risk TEXT[]` for ~150 cells. Required for per-discipline risk via set-intersect. Seed draft in `Layer2D_Spec.md` §5.5. | Medium |
| **D-26** | Implement `supplement_vocabulary` Layer 0 table. Schema + 25 seed entries spec'd in `Supplement_Vocabulary_Spec.md`. Required for 2E supplement FK reads. | ~30-45 min |

### B. ETL bug fixes (cleanup tier — quality / consistency)

| ID | Item |
|---|---|
| D-04 | `phase_load_allocation.phase_` prefix removal (pure rename) |
| D-05 | Aggregator-row filter into ETL itself (removes WEEKLY TOTAL rows; eliminates standing-rule defensive filter) |
| D-06 | `phase_load_weekly_totals` rename `hours_low/high` → `weekly_low_hours/high_hours` |
| D-07 | 4 sports missing weekly_totals rows (Off-Road/AR Non-Nav, Open Water Swim 10km, 25km, Swimrun) — parser bug investigation |
| D-08 | 3 missing rows in `sport_discipline_map` (LDE Cycling -2, Triathlon -1) |
| D-12 | Add `sport_name_aliases` schema to v4 §4 |
| D-13 | `discipline_technique_foci` patch correction (`source_exercise_ids[]` array; `audit_log` col) |
| D-14 | `cross_sport_properties` `source_text` dedup decision |
| D-15 | `discipline_substitutes` UNIQUE constraint review |
| D-16 | `primary_muscles` / `secondary_muscles` cols added to v4 §4.12 schema block |

### C. FC-1 vs FC-1a/FC-1b split contingency
If D-22 curation balloons (cell-by-cell review of injury_flags_text is slow), promote split: FC-1a = D-22 alone; FC-1b = D-23 + D-26 + ETL fixes. Decide at FC-1 session start after sampling D-22 difficulty on the first 50 rows.

### D. Out of scope for FC-1 (deferred to FC-2)
- Spec v4 full rewrite — `Layer0_ETL_Spec_v4.md`. Reads `Project_Backlog.md` as input.
- §§D-F onboarding sections. Independent of FC; could be a parallel pass.

---

## File edits the next session will need to make (rule #11)

These are the mechanically-applicable edits the FC-1 session executes once each item lands. Apply each one only after the corresponding work is complete and verified.

### When D-26 (`supplement_vocabulary` table) lands

**File:** `/mnt/project/Project_Backlog.md`
**Edit:** mark D-26 resolved.

```
old_string:
| D-26 | **`supplement_vocabulary` Layer 0 table not yet implemented.** 2E reads athlete supplements via FK to this table. 25 seed entries + full schema drafted in `Supplement_Vocabulary_Spec.md`. | High | 🔴 **Blocker for 2E implementation (FC-1)** | 2E | Hard blocker for 2E ship. ~30-45 min implementation. Lowest-cost of the three FC-1 promotions. |

new_string:
| D-26 | **`supplement_vocabulary` Layer 0 table implemented in FC-1.** | High | ✅ Resolved (FC-1, [DATE]) | 2E | Table deployed with 25 seed entries per `Supplement_Vocabulary_Spec.md`. 2E supplement FK reads now valid. |
```

### When D-22 (movement_components curation) lands

**File:** `/mnt/project/Project_Backlog.md`
**Edit:** mark D-22 resolved (template — fill row count actually curated).

```
old_string:
| D-22 | **`exercises.injury_flags_text` → structured `movement_components TEXT[]` promotion.** Free text in this column is the only source of "movement constraint × exercise" overlap for 2D. Keyword matching is heuristic with known false-negative risk. Promotion to structured TEXT[] enables set-intersect against B.3 enum tokens (mathematically exact). ~600 cells curation. Cross-layer note exists in `Athlete_Onboarding_Data_Spec_v2.md` §B.3. | High | 🔴 **Blocker for 2D implementation (FC-1)** | 2D | Largest single item in FC-1 by curation volume. May force FC-1a / FC-1b split if FC-1 capacity overflows. Spec'd in Layer2D_Spec §5.5 / §6. |

new_string:
| D-22 | **`exercises.movement_components TEXT[]` deployed in FC-1.** | High | ✅ Resolved (FC-1, [DATE]) | 2D | [N] rows curated. 2D set-intersect path now operational; keyword-matching fallback removed from spec. |
```

### When D-23 (body_parts_at_risk curation) lands

**File:** `/mnt/project/Project_Backlog.md`
**Edit:**

```
old_string:
| D-23 | **`disciplines.body_parts_at_risk TEXT[]` companion column** to `common_injury_patterns`. Enables per-discipline risk via set-intersect against athlete injuries instead of hand-curated keyword map. ~150 cells curation. Seed drafted in Layer2D_Spec §5.5. | High | 🔴 **Blocker for 2D implementation (FC-1)** | 2D | Smaller curation than D-22 but same pattern. v1 fallback path is code-side hand-curated keyword map; structured column is the durable solution. |

new_string:
| D-23 | **`disciplines.body_parts_at_risk TEXT[]` deployed in FC-1.** | High | ✅ Resolved (FC-1, [DATE]) | 2D | [N] disciplines curated. Hand-curated keyword map fallback retired. |
```

### When D-05 ETL fix lands (aggregator filter in ETL)

**File:** `/mnt/project/Control_Spec.md`
**Edit:** remove the D-05 standing rule from §8.2 (filter is no longer needed defensively because ETL now drops aggregator rows at load time).

```
old_string:
- **D-05 aggregator filter** (`AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`): every query touching `layer0.phase_load_allocation` MUST include this filter until ETL fix lands (FC-1). Currently applied in 2A; required for 2D and 2E and Layer 4.

new_string:
- **D-05 aggregator filter — REMOVED (FC-1, [DATE]).** ETL now drops `WEEKLY TOTAL TARGET` rows at load time. Existing query-layer filters are now redundant but harmless; leave in place until FC-2 spec rewrite to keep diffs scoped.
```

**File:** `/mnt/project/Project_Backlog.md`
**Edit:** mark D-05 resolved.

```
old_string:
| D-05 | **`phase_load_allocation` ETL not filtering aggregator rows.** 33 WEEKLY TOTAL TARGET rows present alongside 162 discipline rows. **Verified 2026-05-10:** all 33 sports affected, including AR (AR's aggregator row has all-NULL percentages — noise row, not garbage data). | High | 🟡 Deferred — **STANDING RULE** | 2A, 2D, 2E, 4 | **MANDATORY defensive filter** in every query-layer node spec that touches `phase_load_allocation`: `AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`. Real fix in ETL during FC-1. |

new_string:
| D-05 | **`phase_load_allocation` ETL aggregator filter in ETL.** | High | ✅ Resolved (FC-1, [DATE]) | 2A, 2D, 2E, 4 | ETL drops 33 WEEKLY TOTAL TARGET rows at load. Defensive query-layer filters can be retired in FC-2 spec rewrite. |
```

(Apply the analogous resolution edits for D-04, D-06, D-07, D-08, D-12, D-13, D-14, D-15, D-16 as each lands. Same shape — replace the row's Status column with `✅ Resolved (FC-1, [DATE])`.)

---

## Files NOT to touch in FC-1

- `Athlete_Onboarding_Data_Spec_v2.md` — §I/J/K/L are locked this session. §§D-F deferred but not FC-1 scope.
- `Layer2A_Spec.md` through `Layer2E_Spec.md` — drafted; FC-1 doesn't rewrite them. ETL fixes may render some spec footnotes redundant; address those in FC-2 not FC-1.
- `Sections_IJKL_Groups23_v2_Batch.md` — superseded by integrated content in canonical spec. Keep for historical context; do not edit.

---

## Pre-work reading order for FC-1

1. **`Project_Backlog.md`** — full read. The Open items table is the FC-1 worklist.
2. **`Layer0_Deployed_Schema_and_Drift_Report.md`** — current schema state.
3. **`Supplement_Vocabulary_Spec.md`** — D-26 implementation reference.
4. **`Layer2D_Spec.md`** §5.5 + §6 — D-22 / D-23 curation requirements.
5. **`Batch B`** and **`Batch C`** migration scripts (referenced in project) — house style for idempotent SQL with verify blocks.

---

## Standing rules (still in effect — Control_Spec §8.2)

- **D-05 aggregator filter** until ETL fix lands (will retire in FC-1 per file edits above).
- **Sport naming convention** (D-17): top-level vs sub-format split between Sheet 3 and Sheet 5 tables. Code-side strip pattern in 2A §5.1.
- **D-21 reconciliation**: 2D/2E match on enum *values*, not column names.
- **No FKs in layer0**: TEXT-based by design.
- **Pre-flight introspection before any Layer 0 migration.**

## Memory rules in effect

- **#9** session-start verification — spot-check prior handoff against on-disk state
- **#10** session-end verification — don't claim edits landed unless they did
- **#11** (new) handoff-as-file-diff — defer with mechanically-applicable instructions, not narrative

---

## Critical context

**Andy is the test athlete** for PGE 2026 (July 17–19, 48–56 hr expedition AR). Active Chronic-Managed left wrist injury.

**Spec-first philosophy.** Architecture → prompts → implementation. FC-1 is implementation work but bounded — it doesn't touch any spec design; it brings the deployed ETL into compliance with what the specs already assume.

**Andy preferences (userPreferences):** Direct, no praise/hype/filler. Match confidence to reality. End plans with quick gut check. Flag long chats for handoff.

---

## State of files in project as of this handoff

| File | Status |
|---|---|
| `Control_Spec.md` | ✅ Current (§9 doc map + §10 file-diff rule updated this session) |
| `Project_Backlog.md` | ✅ Current (D-36 added this session) |
| `Athlete_Onboarding_Data_Spec_v2.md` | ⏳ Partial — §§A-C/G-H/I/J/K/L/M/N drafted; §§D-F pending (not blocking FC-1) |
| `Layer2A_Spec.md` through `Layer2E_Spec.md` | ✅ All drafted |
| `Supplement_Vocabulary_Spec.md` | ✅ Drafted (D-26 implementation = FC-1) |
| `Section_I_Audit.md` | ✅ Drafted |
| `Sections_IJKL_Groups23_v2_Batch.md` | ✅ Source material — content now in canonical spec; keep for history |
| `Athlete_Onboarding_Data_Spec_v2_INTEGRATION_BLOCK.md` | ✅ Predecessor material — superseded by canonical spec; keep for history |
| `Layer0_ETL_Spec_v3.md` | ✅ Current (v4 pending FC-2) |
| `Layer0_Deployed_Schema_and_Drift_Report.md` | ✅ Current |

---

## Open items requiring Andy decision before or during next session

| # | Item | When |
|---|---|---|
| 1 | FC-1 vs FC-1a/FC-1b split — confirm after first 50 rows of D-22 curation sampling | At FC-1 session start |
| 2 | D-22 curation: any rows where movement_component classification is genuinely ambiguous → surface for Andy decision | During FC-1 work |

No design-level decisions pending.

---

## Gut check

**What this handoff gets right:**
- All 4 deltas applied with explicit citations to source batch lines and downstream consumer checks.
- D-36 lands with operational substitute (Discipline Focus on Team) documented, so the icebox isn't lossy.
- Memory rule #11 forms a closed loop with #9/#10: prevent drift at write time (#11), catch it at next session start (#9), don't propagate it (#10).
- The "file edits next session will make" section demonstrates the new rule in the document that introduces it.

**Risks:**
- FC-1 effort estimate is soft. D-22 curation could be much slower than 600 rows suggests if the source text quality varies. Sampling-then-decide at FC-1 session start is the protection.
- Rule #11 only helps when handoffs are *deferring* edits. The rule does nothing for sessions where deferral isn't planned but emerges (chat runs long, edits half-applied). For those, #9/#10 still carry the load.
- The pre-spec'd edits in this handoff assume the next session executes them post-work. If FC-1 work changes the row content of D-22/D-23/D-26 before the resolution edit runs (e.g., new context appended), the str_replace will fail loudly — which is the intended failure mode, not a bug.

**What might be missing:**
- §§D-F sequencing decision. They're not FC blockers but they're also not formally scheduled. Andy may want to slot them between FC-1 and FC-2, or after FC-2, or in parallel. Worth a one-line call at FC-1 session start.
- The Adherence_Drop_Spec_v2 (Plan Management subsystem) is referenced in §K Joint Training Generation and elsewhere. The formal Plan Management spec is tracked as D-27 (post-Layer-3). FC-1 doesn't touch it; just flagging continuity.

**Best argument against the plan:**
The new rule #11 is structurally sound but adds writing burden to the outgoing session. If outgoing sessions skip the file-diff section because they're tired, the rule degrades silently — same failure mode as #10 (rule exists, doesn't get enforced). The mitigation is the same: spot-check at session start (#9). The system depends on Andy noticing when a handoff is missing the file-diff section and pushing back. Worth being explicit about that: rules #9/#10/#11 are a system; #11 alone doesn't fix anything.

---

*End of handoff. Next session: FC-1. Read `Project_Backlog.md` Open items first. Start with D-26 (lowest effort, unblocks 2E ship). Then sample 50 rows of D-22; decide FC-1 vs FC-1a/b split based on curation pace.*
