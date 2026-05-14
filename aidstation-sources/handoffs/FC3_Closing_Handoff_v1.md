# FC-3 Closing Handoff — Spec v5 Schema Corrections + §5 Query-Layer Rewrite

**Session:** FC-3 (Final Cleanup batch 3 — Neon-verified schema corrections + §5 query-layer narrative refresh)
**Date:** 2026-05-13
**Predecessor handoff:** `FC2_Closing_Handoff_v1.md`
**Status:** ✅ All FC-3 in-scope items closed except D-41 (`terrain_types` schema dump), which is carried forward with mechanically-applicable instructions for FC-4. Three files in `/mnt/user-data/outputs/` ready for upload.
**Time-on-task:** Single coherent session. A (schema dumps) and B (§5 rewrite) ran in parallel — Andy ran Neon queries while Claude drafted §5 edits.

---

## 1. Session-start verification (rule #9 — completed)

Per rule #9, FC-2 handoff's claimed file updates were spot-checked at session start:

| Claimed by FC-2 handoff | Verified on disk | Notes |
|---|---|---|
| `Vocabulary_Audit_v3.md` (Collarbone + Total 51) | ✅ Present | v3 header, Section 1 line 60 Collarbone row, line 147 per-subsection breakdown |
| `Layer2D_Spec_v1.md` (§5.3.3/§5.4/§5.5 set-intersect; 2D-1/2/6 closed) | ✅ Present | v1 status line 3, "What changed in v1" line 9, set-intersect rewrites and Path B lock all present |
| `Layer0_ETL_Spec_v4.md` (§4.3 body_parts_at_risk + GIN; §4.12 movement_components + GIN; §4.15-4.18 new tables; §6.6 process note) | ✅ Present | All anchors verified |
| `Project_Backlog_v6.md` (D-39 closed; D-40/41/42/43 added) | ✅ Present | All rows present, FC-2 closure section line 137 |
| `Control_Spec_v2.md` (v2 header + §9 doc map all-promotions) | ✅ Present | v2 header, change log, doc map all updated |

**Gap reconciliation result:** zero. FC-2 state matched reality.

---

## 2. Scope at session start

Andy chose all-in: **A** (schema-dump cleanup — D-40/41/42 + sport_name_aliases verification) **+** **B** (§5 query-layer narrative rewrite, paired with per-layer 2A–2E spec consumption).

Sequencing: A was front-loaded (4 Neon queries given to Andy at start of session); Andy ran them in parallel with Claude drafting B. When Neon output landed, the §4 edits and §5 edits were folded into a single v5 ship.

---

## 3. Files shipped (in `/mnt/user-data/outputs/`)

### 3.1 `Layer0_ETL_Spec_v5.md`

File-revision bump v4 → v5. Schema version stays at v3 (no schema fork; v5 is corrections + narrative refresh).

**Header → v5** with new `## What changed in v5 vs v4` section enumerating 8 items across three buckets: schema corrections from FC-3 Neon dumps (D-40, D-42, D-44), schema verification deferred (D-41), and §5 query-layer refresh items.

Per-section edits:

- **§4.8 `cross_sport_properties` — D-42 closed.** Confirmed v4 column list correct (v3 baseline 6 + `source_evidence` + `notes` + `confidence`). **Type correction:** `confidence` changed from `NUMERIC` (v4 spec) → `TEXT` (deployed; qualitative labels, not numeric scores). Batch D v2 §3 alternate columns (`property_type`/`value`/`unit`/etc.) confirmed not deployed — drift report was authoritative.

- **§4.16 `sport_name_aliases` — D-44 opened and closed.** UNIQUE corrected from 2-col `(exercise_db_sport, etl_version)` (v4 spec) → 3-col `(exercise_db_sport, framework_sport, etl_version)` (deployed). The "one-to-one enforced inversely" claim is retracted; deployed permits many-to-many at a given `etl_version`. Added Consumer Impact note flagging that §4.11 `sport_discipline_bridge` derivation must treat the alias join as one-to-many. Tracked as follow-up D-46.

- **§4.17 `terrain_gap_rules` — D-40 closed.** Placeholder replaced with full deployed schema: 12 functional columns (`target_terrain_id`/`name`, `proxy_terrain_id`/`name` [nullable], `gap_severity`, `adaptation_weeks_low`/`high`, `proxy_fidelity`, `proxy_methods TEXT[]`, `uncoverable_stimulus TEXT[]`, `prescription_note`, `audit_log`). UNIQUE `(target_terrain_id, proxy_terrain_id, etl_version)`. Documented UNIQUE-with-NULLs semantics (multiple uncoverable rows permitted per target).

- **§5.1 Architecture, Decision 1 primitives** — two touches: `_filter_exercise_pool` annotated to reflect `movement_components` set-intersect (D-22) per Layer2D_Spec_v1 §5.3.3; `_resolve_substitutes` param name aligned with §5.4 (`available_discipline_ids`).

- **§5.2 — D-45 opened and closed.** Full rewrite to mirror per-layer 2A–2E spec signatures verbatim with "Mirror of LayerXX_Spec §3" attribution above each block. Formalizes §6.6 spec-of-spec rule at signature level. Reconciliation log table shows v4 vs v5 per-function diff. Layer 3 family stays as forward-looking stub (no Layer 3 spec yet). Layer 5 family stays as stubs with note that 5B will consume `supplement_vocabulary` once 5B spec is written.

- **§5.3 Layer 4 canonical payload** — three targeted JSON-shape edits:
  - Discipline-level: `injury_patterns` → `common_injury_patterns` (column rename per §4.3); new `body_parts_at_risk` field surfaces the structured 51-token list for plan-gen prompting.
  - Exercise-pool level: new `movement_components` field surfaces the structured 11-token constraint vocabulary alongside the biomechanical `movement_patterns` (different things).
  - Input example: `active_conditions` field shape aligned to `HealthConditionRecord` canonical (`name`/`system_category`/`status`), replacing the stale `category`/`severity` shape; `active_injuries` example expanded to include `movement_constraints`.

- **§5.4 substitution resolution** — annotated D-15 variant-key semantics: `_resolve_substitutes` returns all variant rows in `candidates[]` with no `(target_id, substitute_id)` deduplication; plan-gen picks by athlete context.

- **Project_Backlog refs** bumped v6 → v7 throughout.

### 3.2 `Project_Backlog_v7.md`

Surgical edits to v6:

- **Header → v7** with FC-3 close note.
- **D-40 → ✅ Resolved (FC-3, 2026-05-13).** Full enumeration recorded with column list and UNIQUE.
- **D-41 → 🟢 Cleanup, "FC-3 retry pending"** with `information_schema.columns` query form recorded for next session.
- **D-42 → ✅ Resolved (FC-3, 2026-05-13).** Column list confirmed; `confidence` type correction documented.
- **D-44 added (Med, ✅ Resolved FC-3, 2026-05-13).** `sport_name_aliases` UNIQUE 2-col → 3-col correction.
- **D-45 added (Med, ✅ Resolved FC-3, 2026-05-13).** §5.2 signatures mirror per-layer specs.
- **D-46 added (Med, 🟢 Cleanup).** `sport_discipline_bridge` row-multiplication audit (follow-up from D-44 closure).
- **Session FC-3 closure block** added with item-by-item summary; **FC-4 tentative scope** outlined (D-41 retry, D-46 audit, D-03/D-07 CC tasks, Layer 3 design kickoff).
- "Layer 2 family substantively spec-complete through 2D" carried forward as still-accurate.

### 3.3 `Control_Spec_v3.md`

Surgical edits to v2:

- **Header → v3** with new `## What changed in v3 vs v2` section.
- **§2 Layer 0 spec doc list** refreshed: v3-era references replaced with v5 canonical pointer; v3 patches noted as folded; Vocabulary_Audit reference bumped v2 → v3.
- **§3 query-layer narrative** — pointer rephrased to cite both `Layer0_ETL_Spec` §5 and the per-layer `Layer2X_Spec` §3 as authoritative for signatures.
- **§9 Doc map:** Layer 0 spec promoted v4 → v5 (FC-3); v4 marked historical predecessor; Control_Spec → v3; Project_Backlog → v7 with FC-3 closure summary.

§§1, §§4-8, §§10-11 unchanged from v2.

---

## 4. Session-end verification (rule #10 — completed)

Each claimed file edit was spot-checked against the on-disk file before composing this handoff:

| File | Critical anchors verified | Status |
|---|---|---|
| `Layer0_ETL_Spec_v5.md` | v5 header; `What changed in v5 vs v4` section; §4.8 `confidence TEXT`; §4.16 3-col UNIQUE + retraction; §4.17 12-col enumeration with UNIQUE; §5.1 `_filter_exercise_pool` note; 5 "Mirror of Layer2X_Spec" attributions in §5.2; §5.3 `common_injury_patterns` + `body_parts_at_risk` + `movement_components`; §5.4 D-15 variant-key paragraph | ✅ |
| `Project_Backlog_v7.md` | v7 header; D-40/D-42/D-44/D-45 each marked "closed"; D-41 "FC-3 retry pending"; D-46 row present; Session FC-3 closure block | ✅ |
| `Control_Spec_v3.md` | v3 header; `What changed in v3 vs v2` section; §9 doc map shows Layer0_ETL_Spec_v5 canonical, v4 historical, Project_Backlog_v7 active, Control_Spec_v3 self | ✅ |

No drift between this handoff narrative and committed file state.

---

## 5. Deferred work with mechanically-applicable instructions (rule #11)

### 5.1 D-41 — `terrain_types` schema dump retry

**Why deferred:** Neon `\d layer0.terrain_types` failed in FC-3 on a client-side quoting artifact (the `\d` shorthand got fragmented; the client reported `Did not find any relation named "layer0.\d"` with `terrain_types` ignored as extra argument).

**Retry SQL (information_schema form, works in any client):**

```sql
-- Query 1: column enumeration
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'layer0' AND table_name = 'terrain_types'
ORDER BY ordinal_position;

-- Query 2: UNIQUE / PK constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'layer0.terrain_types'::regclass
  AND contype IN ('u','p');
```

**Expected output shape:** ~9 functional columns per drift report §2.10 — `canonical_name`, `notes`, plus 7 enrichment cols (`terrain_id`, `category`, `requires_elevation`, `technical_surface`, `environment`, `simulatable`, `simulation_note`). Two UNIQUE constraints expected: primary `(canonical_name, etl_version)` and secondary `(terrain_id, etl_version)`.

**str_replace target — `Layer0_ETL_Spec_v5.md` §4.14:**

Replace the existing `terrain_types` drift note (lines ~778-779 in v5) with a full sub-section block. The current `old_string`:

```
- **`terrain_types` (drift report §2.10):** deployed has 9 functional columns vs the 2 in v2 spec (`canonical_name`, `notes`). Spec missing: `terrain_id`, `category`, `requires_elevation`, `technical_surface`, `environment`, `simulatable`, `simulation_note`. Plus a secondary UNIQUE `(terrain_id, etl_version)`. 16 superseded rows out of 31 total indicate hand-curation outside Vocab Audit doc, likely tied to `terrain_gap_rules` curation (§4.17). Action: a column-by-column terrain_types schema block belongs in v4 §4.14 but requires a Neon dump (`\d layer0.terrain_types`) to enumerate authoritatively. Tracked as D-10 in Project_Backlog v6.
```

Becomes (template — fill from Neon output):

```
- **`terrain_types` (D-41 resolved FC-4, [DATE]):** Deployed schema enumerated. 9 functional columns + versioning:

\`\`\`sql
CREATE TABLE layer0.terrain_types (
  id                    SERIAL PRIMARY KEY,
  canonical_name        TEXT NOT NULL,           -- per Vocabulary_Audit_v3 §3
  notes                 TEXT,
  terrain_id            TEXT NOT NULL,           -- canonical TRN-xxx
  category              TEXT,                    -- e.g. 'foot', 'water', 'mixed'
  requires_elevation    BOOLEAN,
  technical_surface     BOOLEAN,
  environment           TEXT,                    -- e.g. 'outdoor', 'indoor', 'mixed'
  simulatable           BOOLEAN,
  simulation_note       TEXT,

  etl_version           TEXT NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (canonical_name, etl_version),
  UNIQUE (terrain_id, etl_version)
);
\`\`\`

  Adjust column types and constraints to match the deployed schema dump exactly. 16 superseded rows of 31 total indicate hand-curation history; likely tied to `terrain_gap_rules` curation re-runs (§4.17). Active row count after superseded-filter: 15.
```

**Also update in Project_Backlog_v7 — D-41 row:**
- Status: 🟢 Cleanup → ✅ Resolved (FC-4, [DATE])
- Add resolution sentence referencing the §4.14 update.

**Project_Backlog → v8 bump required.** Doc map bump in Control_Spec → v4 if v8 ships in FC-4.

### 5.2 D-46 — `sport_discipline_bridge` row-multiplication audit

Single query, no spec edit unless results require it:

```sql
SELECT exercise_db_sport, COUNT(*) AS framework_mapping_count
FROM layer0.sport_name_aliases
WHERE superseded_at IS NULL
GROUP BY exercise_db_sport
HAVING COUNT(*) > 1;
```

**Decision matrix:**
- **Empty result** → close D-46 as "no multi-mapping in active data; UNIQUE constraint is permissive but unused in practice." Document in Project_Backlog_v8 §4.16 reference.
- **Non-empty result** → for each multi-mapped row, decide:
  - **Intentional** (e.g., "Trail Running" legitimately spans multiple framework sports) → document the case in `Layer0_ETL_Spec_v5` §4.16 with rationale; consider whether `sport_discipline_bridge` row multiplication is OK or needs deduplication at consumption.
  - **Accidental** (dict duplication in `sport_name_aliases.py`) → tighten the source dict and re-run ETL.

---

## 6. Gut check

**What this session got right.**

- Parallel sequencing worked: Andy ran Neon queries while Claude drafted §5; output landed and was folded into one v5 ship. Saved a round trip.
- The §5.2 rewrite caught **five** signature divergences from per-layer specs, not just the two FC-2 attempted to fix. D-45 surfaces this as a discrete drift item with a generalized fix (spec-of-spec rule at signature level) rather than chasing each one individually.
- D-44 is the clearest win from the Neon dump pass: a real semantic bug (2-col vs 3-col UNIQUE) that the spec had wrong, with a follow-up consumer-side audit (D-46) flagged for FC-4. Without the dump, the §4.11 bridge derivation would have run against a faulty mental model.
- All three deferred items (D-41, D-46, the per-layer spec drift) have mechanically-applicable instructions per rule #11. FC-4 doesn't have to re-derive anything.

**Risks.**

- **D-46 may surface uncomfortable rework.** If active `sport_name_aliases` rows do have multi-mappings, the `sport_discipline_bridge` ETL may have been producing multiplied rows since Batch D landed. Layer 2A queries against the bridge could be over-counting. Lower-priority for this scenario than D-22/D-23 ever were, but worth running early in FC-4.
- **§5.3 canonical payload now has fields that no consumer has been built to use** (`body_parts_at_risk`, `movement_components` in exercise_pool). They're forward-looking surface area for Layer 4 plan-gen. If the eventual Layer 4 spec rejects them or shapes them differently, §5.3 will need another touch. Low risk — the columns exist, the question is just whether plan-gen prompts consume them directly.
- **The §5.2 "Mirror of LayerXX_Spec §3" attribution introduces a tighter coupling.** When a per-layer spec revises its signature, §5.2 needs to re-sync immediately or it falls out of date. The discipline is the cost of having one source of truth — but it depends on session-start verification (rule #9) catching drift. Mitigation: the reconciliation log table in §5.2 makes a "what's the canonical vs the mirror" check a 30-second exercise.

**What might be missing.**

- **Layer 4 plan-gen consumer of the new §5.3 fields.** The fields are surfaced but no spec consumes them yet. Should be queued for Layer 4 design (whenever that lands) as "make sure to read §5.3 first."
- **A diff visualizer for FC-3.** v4 → v5 is 8 substantive edits, plus a meta-decision (signature mirror rule). A side-by-side renderer would help future-Andy or future-Claude see the impact at a glance. Not a near-term priority; the change log + reconciliation table do the work for now.

**Best argument against this session's scope.**

A pure schema-dump session (just D-40/41/42 + sport_name_aliases verification) would have been ~30 minutes and produced a clean closure of FC-2's outstanding cleanup items, leaving §5 for a dedicated session. The §5 rewrite turned out to be larger than expected (D-45 surfaced from the per-layer comparison; original plan thought it was just patching §5.2 stubs). Splitting the session would have given §5 a dedicated context window for the Layer 5 family stub decisions, the §5.3 design call about `body_parts_at_risk` surfacing, and a fuller pass at §5.1 primitive descriptions. Counter-argument: schema dumps and §5 are tightly coupled — v5 §5.3 needed the §4 column-name corrections to be accurate, and v5 §5.2 needed the §6.6 spec-of-spec rule to be applied consistently. Folding them was defensible. The session was long but coherent.

---

## 7. Forward pointers

- **FC-4 tentative scope** (`Project_Backlog_v7` §"Session FC-4 (next): tentative scope"):
  1. **D-41 retry** — `terrain_types` schema dump via `information_schema.columns`; ~10 min Neon + str_replace.
  2. **D-46 audit** — `sport_name_aliases` multi-mapping COUNT query; ~10 min + decision branch.
  3. **D-03 / D-07** — ETL parser fixes pending v20 re-run (CC task; can run in parallel with spec-side work).
  4. **Layer 3 design kickoff** — primary forward move. Discovery doc / sub-prompt boundary decisions before per-sub-prompt spec work.

- **Rules in force, unchanged this session:** #9 session-start verification, #10 session-end verification, #11 mechanically-applicable deferred edits, #12 numeric version suffixes.

- **No new memory rules proposed.** The §5.2 spec-of-spec rule is codified in `Layer0_ETL_Spec_v5` §5.2 prose; it's a project-internal policy, not a session-loop behavior change.

---

*End of FC-3 closing handoff.*
