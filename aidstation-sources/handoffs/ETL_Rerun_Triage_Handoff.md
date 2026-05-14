# ETL Re-run Results — Triage Handoff

**Date:** 2026-05-07
**Predecessor:** `Layer0_Query_Decisions_Handoff.md` (architecture decisions) + `Session_Handoff.md` (mid-session state)
**Status:** v10 populated, v3 spec drafted, Claude Code over-there prompt sent. Awaiting ETL report.
**Next chat starts with:** ETL report pasted in. Triage warnings, surface anything needing spec follow-up, transition to next workstream.

---

## TL;DR

Three sessions of work landed:
1. Tactical populate of Sports Framework v9 → v10 (sport classifications, default_inclusion, D-004b fix, Sheet 7 banner)
2. Drafting `Layer0_ETL_Spec_v3.md` with five locked query-layer decisions, two new tables, four sets of new columns, two new pre-ETL parsers
3. Drafting Claude Code over-there prompt for the ETL re-run (`Claude_Code_ETL_Rerun_Prompt.md`)

The ETL re-run is now in flight in a separate Claude Code session. When it returns a report, paste it into the new chat. **First task in the new chat: triage the report against the expectations in §"Triage guide" below.** Don't iterate on spec or data until the report is triaged.

---

## Where everything lives

After Andy uploads the post-session deliverables to project, the new session will see:

| File | Role | Status |
|---|---|---|
| `Layer0_ETL_Spec_v3.md` | Authoritative ETL spec | Newest; replaces v2 |
| `Sports_Framework_v10.xlsx` | Layer 0A source | Newest; in `etl/sources/` in repo |
| `AR_Exercise_Database_v17.xlsx` | Layer 0B source | Unchanged content; new etl_version env |
| `Vocabulary_Audit_v2.md` | Layer 0C source | Unchanged content |
| `Tactical_Populate_Package.md` | Values applied to v9 → v10 | Reference for what was populated and why |
| `Layer0_to_PlanGen_Contract_Preview.md` | Why `stimulus_components` and `substitute_covers` columns were added NULL-able | Reference for downstream contract design |
| `1d_Exercise_DB_Audit.md` | Findings on `contraindicated_conditions` derivation | Reference for ETL behavior expected on 0B |
| `Sheets_7_8_Audit.md` | Findings on Sheet 7 drift and Sheet 8 commentary handling | Reference for ETL parser behavior |
| `Claude_Code_ETL_Rerun_Prompt.md` | The instructions sent to Claude Code | Reference for what the coding session was asked to do |
| `Layer0_Query_Decisions_Handoff.md` | Predecessor architecture decisions | Carryover; still valid |

---

## Triage guide — what to do when the ETL report lands

The over-there prompt requested a report at `etl/reports/run-1.3-*.md` with row counts and validation results. Walk through these checks in order.

### Check 1 — Run completed cleanly?

- ETL exit code 0
- Report file exists
- All Phase 1 / 2 / 3 steps logged

If any phase failed → read the failure, then the spec section that covers that phase, then propose the fix. Most likely failure modes:
- **Source path wrong** — config still points at v6.xlsx. Patch the config; rerun.
- **Sheet name mismatch** — v10 sheet names: `Sports Index`, `Discipline Library`, `Sport × Discipline Map`, `Discipline Pairing Matrix`, `Phase Load Allocation`, `Team Format Cross-Reference`, `Athlete Profile Data Points`, `Cross-Sport Properties`, `Discipline Substitution Map`, `Discipline Training Gaps`. The `×` in "Sport × Discipline Map" is a multiplication sign (U+00D7), not lowercase x. If the extractor opens the wrong sheet, that's why.
- **Missing module** — new extractors (`_extract_discipline_substitutes`, `_extract_discipline_training_gaps`) not wired into `run.py`. Wire them.

### Check 2 — Row counts sane?

Expected (from over-there prompt):

| Table | Expected | Triage if off |
|---|---|---|
| sports | 38 | Wrong: source path or sheet read issue |
| disciplines | prior count − 1 (D-030/D-031 removed; D-008 split adds 1) | Wrong: D-008b row missing OR D-030/D-031 still present |
| sport_discipline_map | ~74 | Wrong: applicability filter broken or sheet shifted |
| discipline_pairing | prior + ~30 | Way more = double-counted; way less = matrix dimension detection failed |
| phase_load_allocation | ~178 | After filtering aggregator rows + EXCLUDED applicability |
| phase_load_weekly_totals | ~152 (38 sports × 4 phases) | Less = parser failures (see Check 4) |
| cross_sport_properties | 1 | More than 1 = commentary rows leaked through Property ID regex |
| **discipline_substitutes** | **91** | Less = FK validator rejected rows; more = duplicate ingestion |
| **discipline_training_gaps** | **3** | |
| exercises | 245 | Should be unchanged from prior run |
| sport_exercise_map | ~1068 | Should be unchanged |

### Check 3 — Validators pass at expected levels?

| Validator | Expected | What to do if off |
|---|---|---|
| `sum_to_100` | 33 PASS, 0 WARN | Was clean in v6 audit. New WARNs likely come from `default_inclusion` interacting with the existing `is_conditional` filter. Compare logic — they should be aligned. |
| `vocab_alignment` | 0 WARN | If non-zero, most likely culprit: Trachea or Diaphragm (added in Round 2) not in canonical body_parts vocab. Check `layer0.body_parts` row count matches Vocab Audit §1 final count (54). |
| `validate_substitution_fks` | 0 ERROR | If non-zero, most likely cause: a row references D-030 or D-031 (removed). Check the broken rows; either fix the source data or confirm they were intentional. |
| `validate_training_gap_fks` | 0 ERROR | Same as above. |
| `validate_contraindicated_conditions` | 0 WARN | Per `1d_Exercise_DB_Audit.md`, only 5 system categories appear in source: Cardiac, Respiratory (from "Lungs"), GI, Skin, Neurological/Cognitive. All canonical. If non-zero, check transform mapping. |
| `validate_default_inclusion` | 0 ERROR | If ERROR, my populate mistyped a value. Valid set: `{included, excluded, prompt_required}`. |

### Check 4 — Heuristic parser quality signals

**Notes split extraction rate** — what % of Phase Load rows produced a non-NULL `prescription_note`?
- ≥ 70%: heuristic is fine
- 50–70%: prescription extraction is missing some good prefixes; iterate
- < 50%: heuristic needs rethinking; likely many notes start with audit-style text

If iteration needed, the easy lever is the `_AUDIT_PREFIXES` tuple in `_split_phase_load_notes`. Common false-audit-prefix patterns to watch for:
- Notes that start with capitalized prescription text but contain `[AUDIT...]` mid-sentence — should still extract the leading prescription
- Numeric leading text (e.g., "2 short rides per week") — currently treated as prescription, correct
- Notes that lead with em-dashes or other punctuation — verify trim handling

**Weekly Total Target parser failures** — any sport whose `WEEKLY TOTAL TARGET` row didn't yield 4 phases? Surface the sport name + the actual notes text. Likely culprits:
- Phase missing entirely (e.g., a sport's notes only specify Base/Build, not Peak/Taper)
- Non-standard delimiter (e.g., "Base 8 to 10 hrs" instead of "Base: 8–10 hrs")
- Hours expressed differently ("6h" vs "6 hrs")

If multiple sports fail, the regex is too strict. If one sport fails, fix that sport's notes in v10.

### Check 5 — D-008b pairing matrix verification

The over-there prompt called out one specific data point to verify:
- R18 (After D-008a) → C10 (D-008b) cell value should be `AVO`, not `N/A`

This was a hand-fix in v8. If the post-load `discipline_pairing` table shows N/A for `(D-008a, D-008b)`, the matrix dimension detection ran but didn't pick up the corrected cell. Investigate by reading the cell directly from v10.

### Check 6 — Sheet 7 confirmed untouched

Sheet 7 (Athlete Profile Data Points) has a new banner row at R1. If any code accidentally enumerates all sheets and reads R1 of Sheet 7, the banner could trip something. Confirm Phase 2 / 3 don't touch Sheet 7. If they do, that's a bug from the v2 spec era — fix.

---

## What "DONE" looks like

ETL re-run is closed when:
1. All row counts within tolerance of expected
2. All validators at expected levels (or any deviations explained and accepted)
3. Two new tables (`discipline_substitutes`, `discipline_training_gaps`) populated
4. New columns populated where expected; NULL where deferred (`stimulus_components`, `substitute_covers`)
5. Prior version's `superseded_at` set on all rows
6. No surprises in the report's "Things to surface" section that aren't documented as accepted

When all six are met, the v10 ETL is canonical. Layer 0 is then ready for Layer 1 prompt design to consume.

---

## Open Items state after ETL clean

| # | Item | Status after ETL re-run |
|---|---|---|
| 1 | Governing Bodies | Carryover; FAQ-feature-pending |
| 2 | Race / Event Formats | Carryover |
| 3 | Pairing Matrix gap (D-018+) | Carryover; Sheet 4 still doesn't cover D-018+ |
| 4 | Vertical Gain in Layer 1 | Carryover; Layer 1 design |
| 5 | exercise_db_sport vocab alignment | RESOLVED — alias map handled it |
| 6 | Sheet 3 col 7 deprecation | Carryover |
| 7 | Cross-Sport Properties extension | Parser tightened in v3; data still 1 row |
| 8 | Vocabulary cleanup transforms | RESOLVED Round 2 |
| 9 | `stimulus_components` populate | NEW — deferred; populate when plan-gen needs it |
| 10 | `substitute_covers` populate | NEW — pairs with #9 |
| 11 | Multi-substitute composition algorithm | Deferred to plan-gen workstream |
| 12 | D-008b pairing matrix review | Not blocking; whitewater coach review |
| 13 | AR D-008b phase load tuning | Not blocking; whitewater AR data |
| 14 | Sport-context substitution overrides | Deferred until plan-gen testing signal |
| 15 | Health Conditions UI gap | Launch-blocker; product workstream |
| 16 | D-020 Alpine Descent training gap | Captured in `discipline_training_gaps` |
| 17 | D-024 Épée Fencing training gap | Captured |
| 18 | D-018 Swimrun training gap | Captured |
| 19 | Sub-ID naming convention | Process note |
| 20 | Caching layer | Deferred; design cache-friendly from day 1 |
| 21 | Sheet 7 deprecation | Banner applied; full deletion deferred to spec hygiene pass |

---

## Next workstream — after ETL clean

The locked sequence is: tactical populate → spec → ETL re-run → **Layer 1 prompt design**.

Layer 1 is the athlete-onboarding prompt set. Per `Athlete_Onboarding_Data_Spec_v2.md` v2.5, the data model is locked. What's not yet specified is the prompt-by-prompt design — how each onboarding step queries Layer 0, what payload it returns, how the LLM uses it.

**Likely Layer 1 first question:** which prompt to design first? The eleven downstream consumers in v3 spec §9 give a starting list. Sensible first cut: 2A (Discipline Classifier) — small input surface, well-bounded output, hits multiple Layer 0 tables for a real integration test.

**Adjacent workstreams that could pull priority:**
- `stimulus_components` populate (Open Item #9) — if Andy wants to close the Layer 0 → plan-gen contract before Layer 1 design starts. ~60–90 min curation. Not blocking either way.
- Sheet 7 deletion (Open Item #21) — full migration audit + deletion. ~30 min audit + delete. Cleanup task.

These are both small enough they can fit before Layer 1 design without delaying it meaningfully. Andy's call on sequencing.

---

## Decisions made this session that the new session should NOT relitigate

- Two new schema columns (`stimulus_components`, `substitute_covers`) added NULL-able to v3 spec per contract preview reasoning. Population deferred. Don't second-guess by removing the columns.
- `default_inclusion` enum has three values; `prompt_required` is reserved for K/C-variant cases on Canoe/Kayak Marathon. Don't simplify to two values.
- Sheet 7 banner is the deprecation marker; full deletion deferred. Don't propose deleting Sheet 7 without the migration audit first.
- Sport classifications use four columns, not single `sport_family` label. Family groupings are derivable at query time. Don't propose collapsing.
- D-008 split into D-008a/D-008b, D-030 + D-031 removed — these are baked. Don't propose reverting.

---

## Process notes for the new session

- **Andy's preferences:** direct, judgment-focused, no praise/hype, gut check at end of recommendations, plain-English when topics get technical
- **No artifact / no document creation for explanations.** Andy reads in chat. Documents only when there's a real artifact to share.
- **Read this doc + spec v3 + the over-there prompt before responding to the report paste.** The triage guide above is what to actually run; the spec is the rationale.
- **Restructure caution:** if the ETL report surfaces a structural problem with the v10 sheet (not a bug in the ETL), survey impact across all affected sheets first, plan operations bottom-up to avoid row-shift issues, verify orphan references are zero before declaring done.

---

## Quick orientation when the new session opens

When Andy pastes in the ETL report (or says "results are in"):

1. Read the report. Walk through the six checks above in order.
2. For each deviation, look up the relevant spec section before proposing a fix.
3. Surface each finding as: **Status (PASS/WARN/ERROR/UNEXPECTED) + Likely cause + Proposed action**.
4. Don't propose schema changes unless a finding genuinely demands one — schema is locked at v3.
5. When all six checks pass: declare ETL re-run done, propose next workstream (Layer 1 design vs. one of the deferred adjacent items).
