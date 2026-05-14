# FC-4a Closing Handoff — Spec v6: D-41 terrain_types + D-46 multi-mapping audit

**Session:** FC-4a (Final Cleanup batch 4a — D-41 retry + D-46 audit completion; mid-chat continuation of the FC-3 session)
**Date:** 2026-05-13
**Predecessor handoff:** `FC3_Closing_Handoff_v1.md`
**Status:** ✅ All FC-4a in-scope items closed. D-21 carried to FC-4b with mechanically-applicable instructions. Three files in `/mnt/user-data/outputs/` ready for upload.
**Time-on-task:** Run as a mid-chat continuation of the FC-3 session — Andy chose Option B ("bank D-41 and D-46 here before fresh thread") rather than break to a new thread. Two Neon queries + three file bumps + this handoff.

---

## 1. Session-start verification (rule #9 — not applicable this session)

FC-4a started as a mid-chat continuation of the FC-3 session, working from in-memory `/home/claude` files (v5, v7, v3) rather than uploaded `/mnt/project` versions. The FC-3 outputs were composed and verified in the immediately-preceding turn but **not yet uploaded to project knowledge at FC-4a start.** The rule-#9 verification will run at the start of the next fresh session (FC-4b or later) against whatever has been uploaded by then.

**Andy: when uploading, upload both the FC-3 outputs (v5/v7/v3) AND the FC-4a outputs (v6/v8/v4) before the next session.** FC-4b session-start verification will then check v6 anchors directly.

---

## 2. Scope at session start

Andy returned with:
- A.2 retry output for `terrain_types` (the FC-3 deferred query) — **D-41 query result**
- D-41/D-46 paste — duplicate `terrain_types` output (same data) + D-46 `sport_name_aliases` COUNT result

Net inputs: one `terrain_types` schema dump + one multi-mapping COUNT.

---

## 3. Files shipped (in `/mnt/user-data/outputs/`)

### 3.1 `Layer0_ETL_Spec_v6.md`

File-revision bump v5 → v6. Schema version stays at v3.

**Header → v6** with new `## What changed in v6 vs v5` section. Four substantive edits:

- **§4.14 `terrain_types` — D-41 closed.** Replaced 2-bullet drift note with full deployed schema (9 functional columns + 2 UNIQUE constraints). **Drift report correction surfaced:** §2.10 listed `simulatable` as `BOOLEAN`; deployed is `TEXT` (permits values like 'yes' / 'no' / 'partial' / 'conditional'). Documented `terrain_id` as nullable with NULL-distinct UNIQUE semantics permitting unlabeled-during-curation rows. Active row count after superseded-filter: 15 of 31.

- **§4.16 `sport_name_aliases` Consumer Impact block — D-46 closed.** Replaced the speculative v5 "investigate at next bridge re-derivation" paragraph with full audit findings: 21 multi-mapped `exercise_db_sport` values confirmed **intentional** for framework sub-format splitting. Added a categorized table:
  - General Conditioning: 38 framework mappings (broadly applicable)
  - Swimming: 11 contexts (pool / OW / marathon / swimrun / triathlon-swim / etc.)
  - SkiMo / Rowing / Triathlon: 5 each (sub-format variants)
  - XC Skiing / Kayaking / Trail Running: 4 each
  - Six rows at 3 mappings each (Mountaineering, Marathon, etc.)
  - Eight rows at 2 mappings each (Road Cycling, MTB, etc.)
  
  Conclusion: no `sport_name_aliases.py` tightening required; curation is correct as-is.

- **§4.11 `sport_discipline_bridge` — Multiplication property block added.** Direct consequence of D-46 closure. Documented the multiplication property in detail (one-to-many alias × shared-discipline-across-framework-sports → bridge produces multiple rows for the same `(exercise_id, discipline_id)` pair). Added explicit **consumer dedup requirement** with reference SQL pattern (`SELECT DISTINCT ON (e.exercise_id)`) and Python idiom. Cited Layer 2D §5.2 as a known compliant consumer; tracked rationale-comment update as D-47.

- **D-47 surfaced.** New cleanup item: Layer 2D §5.2 SQL rationale comment cites multi-discipline path only; needs to cite framework-mapping path too. Functional behavior already correct (dedup-by-exercise_id handles both); comment-only fix. Low priority, queued for next Layer 2D revision.

- **Project_Backlog refs** bumped v7 → v8 throughout.

### 3.2 `Project_Backlog_v8.md`

Surgical edits to v7:

- **Header → v8** with FC-4a close note.
- **D-41 → ✅ Resolved (FC-4a, 2026-05-13).** 9-column enumeration recorded; `simulatable TEXT` correction noted as drift-report error; nullable `terrain_id` semantics documented.
- **D-46 → ✅ Resolved (FC-4a, 2026-05-13).** 21 multi-mapped rows confirmed intentional; full audit summary recorded.
- **D-47 added (Low, 🟢 Cleanup).** Layer 2D §5.2 rationale-comment update. Includes mechanically-applicable suggested wording for next 2D revision.
- **Session FC-4a closure block** added with item-by-item summary.
- **FC-4b tentative scope** outlined: D-21 retry (with the SQL query inline per rule #11), D-03/D-07 CC tasks, D-47 fold-in, Layer 3 design kickoff recommended for a fresh chat.

### 3.3 `Control_Spec_v4.md`

Surgical edits to v3:

- **Header → v4** with new `## What changed in v4 vs v3` section.
- **§2 Layer 0 spec doc list** updated: v5 canonical pointer → v6.
- **§9 Doc map:** Layer 0 spec promoted v5 → v6; v5 marked historical; Control_Spec → v4; Project_Backlog → v8 with FC-4a closure summary.

§§1, §§3-8, §§10-11 unchanged from v3.

---

## 4. Session-end verification (rule #10 — completed)

Each claimed file edit was spot-checked before composing this handoff:

| File | Critical anchors verified | Status |
|---|---|---|
| `Layer0_ETL_Spec_v6.md` | v6 header; `What changed in v6 vs v5` section; §4.14 9-column schema with `simulatable TEXT`; §4.16 21-row multi-mapping table + "No `sport_name_aliases.py` tightening required"; §4.11 Multiplication property block + reference SQL pattern; D-47 surfaced and cross-referenced | ✅ (11 anchor hits, expected ≥6) |
| `Project_Backlog_v8.md` | v8 header; D-41 "closed" + drift correction noted; D-46 "closed" + intentional finding; D-47 row present with suggested wording; Session FC-4a CLOSED block; Session FC-4b tentative scope with D-21 SQL inline | ✅ (8 hits, expected ≥6) |
| `Control_Spec_v4.md` | v4 header; `What changed in v4 vs v3` section; §9 doc map shows Layer0_ETL_Spec_v6 canonical, v5 historical, Project_Backlog_v8 active | ✅ (5 hits, expected ≥4) |

No drift between this handoff narrative and committed file state.

---

## 5. Deferred work with mechanically-applicable instructions (rule #11)

### 5.1 D-21 — `health_condition_categories` column name reconciliation

**Why deferred:** FC-2 originally grouped D-21 with the terrain_types schema-dump session, but the table is different and was not queried in FC-3 or FC-4a. Tractable next session with a single `information_schema.columns` query.

**Retry SQL:**

```sql
-- Column enumeration
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'layer0' AND table_name = 'health_condition_categories'
ORDER BY ordinal_position;

-- UNIQUE / PK constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'layer0.health_condition_categories'::regclass
  AND contype IN ('u','p');
```

**Expected disambiguation:** the column is either `category_name` (v3 spec §4.14 / v2 §4.12.2) or `system_category` (v3 §6.2 validation reference). Drift report claimed "no drift" on this table without resolving which.

**str_replace target — `Layer0_ETL_Spec_v6.md` §4.14:**

Replace the D-21 bullet currently reading:

```
- **`health_condition_categories` column name uncertainty (D-21):** v3 §4.14 references `category_name`; v3 §6.2 validation references `system_category`. Drift report flagged the table as "no drift" but didn't reconcile the column name. Standing rule (FC-1a): consumers match on enum values, not column names. **Carried to FC-4b** — needs its own `information_schema.columns` query against `health_condition_categories`. Listed in `Project_Backlog_v8`.
```

With (template — fill from Neon output):

```
- **`health_condition_categories` (D-21 resolved FC-4b, [DATE]):** Deployed column name is `[category_name | system_category]`. The other reference in spec/code is stale and should be updated. [If category_name:] Layer 2D §3 / Layer 2E §3 HealthConditionRecord uses `system_category` as the dataclass field; the dataclass field name is independent of the column name, so this is a column-name fix only — no consumer change required.

\`\`\`sql
CREATE TABLE layer0.health_condition_categories (
  id              SERIAL PRIMARY KEY,
  [column_name]   TEXT NOT NULL,            -- canonical system_category enum (per Vocabulary_Audit_v3 §2)
  ...

  etl_version     TEXT NOT NULL,
  etl_run_at      TIMESTAMPTZ NOT NULL,
  superseded_at   TIMESTAMPTZ,

  UNIQUE ([column_name], etl_version)
);
\`\`\`
```

Adjust to match deployed shape. If the column is `category_name`, also do a project-wide grep for any `system_category` references that point at column reads (vs dataclass field reads) and fix them.

**Also update in Project_Backlog_v9 — D-21 row:**
- Status: 🟢 Cleanup → ✅ Resolved (FC-4b, [DATE])
- Add resolution sentence referencing the §4.14 update.

**Project_Backlog → v9 bump required.** Doc map bump in Control_Spec → v5 if v9 ships.

### 5.2 D-47 — Layer 2D §5.2 rationale comment

Comment-only fix; queue for next Layer 2D revision. Suggested wording already recorded in `Project_Backlog_v8` D-47 row:

> "An exercise may appear in the join output multiple times for two reasons: (1) it maps to multiple included disciplines, and (2) its `exercise_db_sport` maps to multiple `framework_sport` values whose disciplines overlap (`Layer0_ETL_Spec` §4.11 multiplication property). Post-query dedup by `exercise_id` handles both; track `discipline_ids[]` per exercise for risk attribution."

No spec bump just for this; fold into the next Layer 2D update (Layer2D_Spec → v2) whenever that happens.

---

## 6. Gut check

**What this session got right.**

- **The D-46 audit produced a non-trivial finding.** Without the audit, the v5 §4.16 "investigate at next bridge re-derivation" placeholder would have lingered. The multiplication property in §4.11 is now documented with consumer pattern and reference SQL — that's content engineers need at query-build time, not at audit time.
- **The drift-report `simulatable BOOLEAN` error was caught.** This is exactly the kind of small spec-vs-deployed mismatch that the §6.6 "code is authoritative" rule exists to surface. If a consumer had built a `WHERE simulatable = true` filter against deployed `TEXT`, it would have silently failed (or worked correctly by accident — the boolean coercion behavior here is undefined). D-41 closure ships the spec with deployed reality.
- **D-47 was tracked, not absorbed.** The temptation was to also bump Layer 2D §5.2 inline as part of this session. Instead D-47 is a discrete cleanup item with suggested wording — bumping Layer 2D for a comment-only change would have been over-scope. The session stayed focused.

**Risks.**

- **The "Multiplication property" §4.11 paragraph is dense.** It's correct, but engineers reading it cold might miss the practical implication ("just dedup by exercise_id"). The reference SQL pattern at the bottom mitigates this. If anyone is confused on first read, the right fix is to move the dedup pattern higher up.
- **Layer 2D §5.2 has a working but mis-attributed comment.** This is a latent footgun — someone debugging a row-multiplication bug in Layer 2D would look at §5.2's comment, see "multi-discipline path" as the only cited reason, and miss the framework-mapping path. D-47 should be closed at the first opportunity that touches Layer 2D, not deferred indefinitely.
- **The mid-chat continuation pattern.** This session ran inside the FC-3 chat, working from `/home/claude` files. If anything had gone wrong (e.g., I needed to re-read a v4 anchor and v4 wasn't in /home/claude), there would have been a confusing slip. It worked here because the work was tight and I copied v5 → v6 explicitly. Lesson for future "Continue" sessions: copy the previous-session outputs into the working directory at session start, then edit in place.

**What might be missing.**

- **The full bridge dedup-pattern propagation.** §4.11 now documents the multiplication property and dedup requirement. But the only consumer that's been explicitly audited for compliance is Layer 2D §5.2. If Layer 2A, 2C, or any future query also joins through the bridge, those need to be checked. **Recommend at Layer 3 design kickoff:** include a one-line audit of all Layer 2x query SQL against the §4.11 dedup contract.
- **D-21 is one of the last `\d` uncertainties** in Layer 0. After FC-4b, the Layer 0 spec should be fully self-consistent against Neon — every table column, type, and constraint accounted for. Worth doing as the formal "Layer 0 done" milestone.

**Best argument against this session's scope.**

The FC-3 closing handoff already had Option A (fresh thread) as the recommended path. Continuing into FC-4a in the same chat means the FC-3 outputs are now stale-on-disk (v5 sits in `/mnt/user-data/outputs/` but the v6 update has already obsoleted parts of it). If Andy uploads v5 but forgets v6, the project knowledge will have an inconsistent doc map. **Mitigation:** explicitly call out the upload-order dependency in this handoff (done in §1) and recommend uploading both batches before the next session.

Counter-argument: FC-4a closed two real backlog items in ~15 minutes of additional session work — that's high efficiency. The natural break is now genuinely clean (Layer 0 is one D-21 query away from full self-consistency; Layer 3 design is the next big arc). Splitting D-41/D-46 across two sessions would have spread the same work across two session-start verifications and two handoffs for marginal benefit.

---

## 7. Forward pointers

- **FC-4b tentative scope** (`Project_Backlog_v8` §"Session FC-4b (next): tentative scope"):
  1. **D-21 retry** — `health_condition_categories` `information_schema.columns` query; ~5 min Neon + str_replace. Closes the last `\d` uncertainty in Layer 0.
  2. **D-03 / D-07** — ETL parser fixes pending v20 re-run (CC task; orthogonal).
  3. **D-47 rationale-comment fix** — fold into next Layer 2D revision (Layer2D_Spec → v2 if material; or piggyback on Layer 3 design when 3D depends on 2D output).
  4. **Layer 3 design kickoff** — primary forward move. **Recommended for a fresh chat** — biggest scope item, six sub-prompts + Layer 3.5 HITL gate, deserves dedicated context window.

- **Upload sequencing:** Upload **all six** files from FC-3 + FC-4a before the next fresh session:
  1. `Layer0_ETL_Spec_v5.md` (FC-3)
  2. `Layer0_ETL_Spec_v6.md` (FC-4a, canonical)
  3. `Project_Backlog_v7.md` (FC-3 historical)
  4. `Project_Backlog_v8.md` (FC-4a, canonical)
  5. `Control_Spec_v3.md` (FC-3 historical)
  6. `Control_Spec_v4.md` (FC-4a, canonical)

  v5/v7/v3 become historical predecessors immediately; the canonical refs in the doc map are v6/v8/v4.

- **Rules in force, unchanged this session:** #9 session-start verification (will run next session against uploaded v6), #10 session-end verification (done), #11 mechanically-applicable deferred edits (D-21 instructions included), #12 numeric version suffixes (followed).

---

*End of FC-4a closing handoff.*
