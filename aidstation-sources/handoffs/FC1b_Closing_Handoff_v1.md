# FC-1b Closing Handoff

**Date:** 2026-05-12
**Predecessor:** `D22_Pass2_Done_MigSQL_D23_Kickoff_Handoff_v1.md`
**Scope of this session:** D-22 migration SQL + deploy → D-23 curation + migration SQL + deploy → FC-1b closure
**Status:** FC-1b closed. Both Layer 2D blocker columns (`movement_components`, `body_parts_at_risk`) deployed with GIN indexes. Layer 2D implementation now unblocked.

---

## §0. Scope summary

This session executed the two remaining FC-1b column promotions in a single thread:

1. **D-22 migration deploy.** Locked baseline from `D22_Curation_Reference_v2.md` (159 rows = 57 Pass 1 + 102 Pass 2) → script-generated `migrate_exercises_add_movement_components_v1.sql` → ran in Neon → `NOTICE: OK — 159 rows populated, 11 canonical tokens, GIN index in place`.

2. **D-23 full curation + migration deploy.** Recon → curation proposal (31 disciplines) → Andy review with 5 row-level edits + 1 vocabulary amendment + D-39 reduction → locked baseline `D23_Curation_Reference_v1.md` → script-generated `migrate_disciplines_add_body_parts_at_risk_v1.sql` → ran in Neon → `NOTICE: OK — 31 rows populated, 51 canonical body parts, GIN index in place`.

Both migrations passed all six DO $$ verification checks (row count, baseline ID coverage, NULL check, canonical token check, duplicate check, off-baseline check).

---

## §1. Resolution status

| ID | Status | Details |
|---|---|---|
| D-22 | ✅ Resolved (FC-1b, 2026-05-12) | `layer0.exercises.movement_components TEXT[]` deployed; 159 active rows populated; GIN index `idx_exercises_movement_components` in place |
| D-23 | ✅ Resolved (FC-1b, 2026-05-12) | `layer0.disciplines.body_parts_at_risk TEXT[]` deployed; 31 rows populated; GIN index `idx_disciplines_body_parts_at_risk` in place |
| D-38 | 🟢 Cleanup (carried) | Wrist deviation token gap — 2 data points, sub-threshold for vocabulary expansion. Force-mapped to Angle. Track for v2 vocabulary review. |
| D-39 (new) | 🟢 Cleanup | `Vocabulary_Audit` v3 rewrite: Collarbone added to canonical body parts per D-23; "Total: 41" header is stale (now 51). |
| D-26 | ✅ Resolved (FC-1, 2026-05-11) | (unchanged — carried for FC-1b summary completeness) |

**FC-1b closed.** Three of three blockers resolved. **Layer 2D implementation unblocked.**

---

## §2. Decisions locked this session

**D-23 house rules (Rules 1–7).** Locked at recon-time per Andy. Documented in §"House rules (locked)" of `D23_Curation_Reference_v1.md`.

**D-23 drafting-time calibration:** "Shoulder impingement" and "Swimmer's shoulder" both → `{Shoulder, Rotator cuff}` consistently across 8 disciplines. Falls under Rule 1; no separate rule needed.

**D-23 inheritance scope decisions (Rule 5 applications):**
- D-005a (TT/Tri Bike): expand to D-005 baseline union (per Andy override of literal-only initial draft).
- D-008b: full D-008a set + Forearm.
- D-009: shoulder/wrist/elbow/RC from D-008a + Lower back. Hand NOT inherited.
- D-016 (Mountaineering): D-003 ∪ D-010 ∪ literal Ankle (per Andy override of literal-only initial draft).
- D-025: only the four parenthesized inherits from D-002.
- D-026: literal Fingers + Forearm; Finger pulley NOT inherited from D-010.

**D-23 vocabulary amendment.** `Collarbone` added to canonical body parts list (Shoulder region). New total: 51. Drove D-006 (Mountain Biking) mapping. Formal `Vocabulary_Audit` v3 rewrite tracked as D-39.

**D-23 permanent skips (per Andy, no backlog tracking):**
- Head (D-020 helmet-mediated head injury) — mode-of-injury, not training-prescription-relevant
- Eye (D-029 scope/sight strain) — not a body-part risk pattern
- Perineum / sit bones (D-005a saddle zone) — D-37 skin/nerve territory

**D-22 retroactive consistency precedent.** EX024 → `{Angle, Load, Impact}` per EX119 consistency. Baseline corrected before migration deployed.

---

## §3. Files produced this session — Andy upload checklist

### Project knowledge (markdown)

| File | Status | Notes |
|---|---|---|
| `Project_Backlog_v5.md` | **Upload** | D-23 ✅ Resolved, D-39 added, FC-1b section closed |
| `D23_Curation_Reference_v1.md` | **Upload** | Locked baseline (house rules + 31 mappings + synonym table + inheritance log) |
| `FC1b_Closing_Handoff_v1.md` | **Upload** | This doc |
| ~~`D23_Curation_Proposal_v1.md`~~ | **Skip** | Superseded by `D23_Curation_Reference_v1.md`. Old proposal stays in outputs as session history but doesn't need to land in project knowledge. |

Intra-session files already uploaded between turns (verify present):
- `Project_Backlog_v3.md`, `Project_Backlog_v4.md` — superseded by v5 but kept as version history per rule #12
- `D22_Curation_Reference_v2.md` — locked at start of session, unchanged

### SQL migration files (repo `etl/sources/`)

| File | Status | Deployed? |
|---|---|---|
| `migrate_exercises_add_movement_components_v1.sql` | **Upload + commit** | ✅ Ran 2026-05-12, all checks passed |
| `migrate_disciplines_add_body_parts_at_risk_v1.sql` | **Upload + commit** | ✅ Ran 2026-05-12, all checks passed |
| `generate_movement_components_migration.py` | **Upload + commit** | Generator script — companion to D-22 SQL |
| `generate_body_parts_at_risk_migration.py` | **Upload + commit** | Generator script — companion to D-23 SQL |

### Files superseded — do NOT upload as canonical (old versions stay as project history)

- `Project_Backlog_v2.md`, `Project_Backlog_v3.md`, `Project_Backlog_v4.md` — superseded by v5
- `D22_Curation_Reference.md` — superseded by `_v2.md` (Pass 2 closure)
- `D23_Curation_Proposal_v1.md` — superseded by `D23_Curation_Reference_v1.md` (curation lock)

---

## §4. Memory rules — current state

All six standing rules followed cleanly this session:

- **Rule #9 (session-start verification):** Verified prior handoff's claimed file state before starting work. `D22_Curation_Reference_v2.md` confirmed Pass 2 appended + EX024 correction landed; `Project_Backlog_v2.md` confirmed §6 edits NOT yet applied; applied them as first action of session.
- **Rule #10 (session-end verification):** Spot-checked all files in §3 before composing this handoff. No drift between handoff claims and on-disk state.
- **Rule #11 (machine-applicable edits):** §6 of predecessor handoff used str_replace blocks for `Project_Backlog` edits. This session's edits to backlog v2→v3→v4→v5 used the same pattern. No narrative summaries; all edits exact.
- **Rule #12 (numeric version suffix):** Followed for all revised files (`Project_Backlog_v3/4/5`, `D22_Curation_Reference_v2`, `D23_Curation_Reference_v1`, `FC1b_Closing_Handoff_v1`).

No rule changes proposed this session.

---

## §5. Spec docs that now lag deployed state

These are not blockers — "code is authoritative; spec catches up" pattern. To be folded into **FC-2 spec v4 rewrite**:

| Spec doc | Lag item |
|---|---|
| `Layer2D_Spec.md` §5.5 | Decision Point B locked. `BODY_PART_KEYWORDS` keyword map (path A) is no longer the primary path. Replace with `body_parts_at_risk` set-intersect description. Keep keyword map as historical reference or delete. |
| `Layer2D_Spec.md` §5.4.1 | Movement-component set-intersect path: ensure spec language matches deployed `movement_components` column (not the older heuristic keyword-match against `injury_flags_text`). |
| `Vocabulary_Audit_v2.md` | Section 1 needs Collarbone formally added; "Total: 41" header is stale (enumerated = 51 with Collarbone). Tracked as D-39. |
| `Layer0_ETL_Spec_v3` §4.3 / §4.exercises | Add `body_parts_at_risk TEXT[]` to `disciplines` schema; add `movement_components TEXT[]` to `exercises` schema. Both are deployed-ahead-of-spec drift items now. |

---

## §6. FC-2 kickoff scope (next session)

Per `Project_Backlog_v5.md` "Session FC-2: Spec v4 rewrite — UPCOMING":

- Fold Batches A, B, C, D, B-Correction, drift report items into unified `Layer0_ETL_Spec_v4`
- Add missing §4 sections (`terrain_gap_rules`, verify `sport_name_aliases` and `discipline_technique_foci` landed)
- Apply consumer table corrections from `ETL_Spec_v3_Corrections_2ABC_v2`
- Document "code is authoritative; spec catches up" as §6 process note
- **Add this session's drift items** (§5 above): Layer2D_Spec §5.5 / §5.4.1 updates, schema additions for both new columns
- **Optionally fold D-39 in** (Vocabulary v3 rewrite) since it's a documentation-cleanup task that pairs with spec rewrite work

### Session-start checklist (rule #9, for the FC-2 session)

When picking up:

1. **Verify uploads landed:**
   - `Project_Backlog_v5.md` in project knowledge (most-recent-numeric)
   - `D23_Curation_Reference_v1.md` in project knowledge
   - `FC1b_Closing_Handoff_v1.md` in project knowledge
   - Spot-check: backlog v5 D-22 and D-23 both show ✅ Resolved (FC-1b, 2026-05-12); D-39 row exists
2. **Verify Neon deployed state:**
   - `\d layer0.exercises` shows `movement_components text[]` column
   - `\d layer0.disciplines` shows `body_parts_at_risk text[]` column
   - Both GIN indexes exist (`idx_exercises_movement_components`, `idx_disciplines_body_parts_at_risk`)
3. **Pre-flight token coverage spot-check** (optional, 10 sec):
   ```sql
   SELECT array_agg(DISTINCT t) FROM layer0.exercises e,
          unnest(e.movement_components) AS t WHERE e.superseded_at IS NULL;
   ```
   Expected: 11 canonical tokens.
   ```sql
   SELECT array_agg(DISTINCT t) FROM layer0.disciplines d,
          unnest(d.body_parts_at_risk) AS t;
   ```
   Expected: 28 distinct body parts (subset of canonical 51).
4. **No D-22/D-23 follow-up needed.** Both columns are sealed for v1.

---

## §7. Open audit items (track but not blocking)

| Item | Where | Action |
|---|---|---|
| Vocabulary 41-vs-51 count discrepancy | `Vocabulary_Audit_v2.md` | D-39 — formal v3 rewrite. Cleanup. |
| EX024/EX119 consistency precedent | D-22 baseline | Closed this session; baseline shipped with correction. No further action. |
| D-38 wrist deviation force-map (2 data points) | `Layer2D_Spec` / vocabulary | Track. Third surfacing crosses threshold for 12th canonical token. |
| Pre-flight schema drift assumption | Both migrations | Migrations assumed `discipline_id` / `exercise_id` are string PKs on respective tables. Deploys passed cleanly → confirmed. |
| Inheritance scope of D-016 may over-include Finger pulley | `D23_Curation_Reference_v1.md` | Andy's call ("tag same as hiking + climbing"). Trail-it for first-cohort feedback. Finger pulley is a small-edge sport-climbing risk that may not map to mountaineering hold positions. Easy revert: edit D-016 row in curation reference, regen SQL via D-23 generator. |
| Vocabulary v3 rewrite folds well with Layer 1 §B onboarding refinements (D-25) | D-39 row | Note for whoever owns the Vocabulary doc rewrite. |

---

## §8. Gut check

**What this session got right:**
- D-22 migration ran clean on first try — all six DO $$ checks passed without a rollback. House-style RAISE EXCEPTION pattern (vs informational SELECTs) caught the empty-array bug pre-deployment.
- Generator script pattern (`generate_*_migration.py`) was reused identically for D-23 — proved the "data-driven SQL from curation markdown" approach scales. Two columns deployed this session; pattern works for the FC-29/D-30/D-31 future promotions too.
- D-23 curation completed in one batch, not split into Pass 1/Pass 2 — recon was right that source data was cleaner than D-22's.
- Andy edits on D-005a, D-016, D-021, D-022 surfaced one new calibration (Shoulder/Rotator-cuff normalization) which got documented inline rather than as a separate rule — kept the rule set tight.
- Collarbone vocabulary addition handled cleanly: amendment noted in curation reference, included in generator's canonical set, formal Vocabulary doc rewrite tracked as D-39 instead of blocking D-23.
- D-39 scope reduction (Head/Eye/perineum permanent skips) prevented backlog inflation with items Andy explicitly didn't want tracked.

**Risks:**
- **D-016 Mountaineering may over-include Finger pulley.** Tagged per Andy's "tag same as hiking + climbing" instruction, but mountaineering hand positions (ice axe, broad edges, glove-mediated grip) don't really expose A2 pulley load the way sport climbing does. Sub-threshold concern; surface if first-cohort feedback flags it. Easy to revert (one row edit + regen).
- **D-005a = D-005 exactly.** The expanded D-005a set is byte-identical to D-005. This is correct given the source text but means an athlete's body-part injury would match both rows identically. If 2D plan-gen ever treats D-005 and D-005a as alternative paths for the same race (rather than additive disciplines for the same athlete), the identical sets are fine. If they're ever treated as distinct contexts with different risk profiles, this would need revisiting.
- **Spec lag in Layer2D_Spec §5.5.** Decision Point B is locked but spec still has the `BODY_PART_KEYWORDS` keyword map as path A documented. A naive reader of the spec might think the keyword map is the v1 path. The FC-2 rewrite needs to remove or demote it.
- **No CHECK constraints on either new column.** Both migrations chose to defer CHECK constraints to v2 (per the canonical-token-set + canonical-body-part-set discussions). Validation block catches violations at migration time only; future writes are uncontrolled. Cheap to add later; sub-threshold risk for v1.

**What might be missing:**
- **No 2D smoke test against the new columns.** The set-intersect queries that 2D will use (`array_agg(...) & ARRAY[...]`) haven't been exercised against the deployed columns yet. The columns exist with correct values, but the join from athlete `Injury Record.body_part` → discipline `body_parts_at_risk` → discipline_risk_level hasn't been wired. That's 2D implementation work, not FC-1b. But worth noting that "FC-1b deployed clean" ≠ "2D works end-to-end yet."
- **No regression check on existing 2D paths.** If any current 2D code path still references the heuristic keyword-match against `injury_flags_text` or the in-code `BODY_PART_KEYWORDS`, those paths haven't been updated. FC-2 spec rewrite is the natural place; 2D implementation work depends on it.
- **Generator-script tests.** The two generator scripts have assert-based sanity checks but no formal test suite. If the curation markdown format ever shifts (e.g., the row regex breaks on a future doc edit), the script would either parse wrong or fail loudly. Loud failure is the design, but still worth a unit test pass before reusing for D-29/D-30/D-31 if those happen.

**Best argument against this session structure:**

This session bundled "D-22 migration deploy" + "D-23 full curation + deploy" into a single thread. That's a meaningful amount of work — two columns deployed, one vocabulary amendment, five row-level edits, one calibration discovered, four files produced for each migration. The reason it worked is the generator-script pattern: most of the cognitive load on D-23 was the 31-row curation pass, not the SQL writing or validation. If the pattern hadn't carried, we'd have needed two sessions.

Mitigation forward: when the next column-promotion column comes up (D-29 / D-30 / D-31 / future), the same pattern applies. Curate → generate → deploy. The recipe is now repeatable.

---

*End of FC-1b Closing Handoff. Next session: FC-2 (spec v4 rewrite). After FC-2: Layer 3 design.*
