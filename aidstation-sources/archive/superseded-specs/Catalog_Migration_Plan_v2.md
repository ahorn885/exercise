# Catalog Migration Plan — v2

**Version:** 2.0
**Status:** Draft. Strategy-level v2 — sequencing, key decisions, and Phase 1 alias workflow refinement. Per-phase execution detail to be added as each phase approaches.
**Last updated:** 2026-05-13 (v2: Phase 1 alias audit step refined — fuzzy-match + HITL workflow per L3-Spec-Trio feedback round 2)
**Supersedes:** `Catalog_Migration_Plan.md` (v1, 2026-05-13)
**Owner:** D-52 (Project_Backlog)
**Cross-references:**
- `Control_Spec_v6.md` §2 (architectural framing)
- `Athlete_Data_Integration_Spec_v2.md` §2.4 (target state)
- `Layer0_ETL_Spec_v7.md` (layer0 schema source of truth)
- `DATABASE.md` (Vercel-app schema source of truth for `public.*`)
- `L3-Discovery_Pre-Spec-Trio_Inventory` §C (drift findings that motivated this plan)

## What changed in v2 vs v1

**Phase 1 alias audit step refined (§4 Phase 1, step 3 and step 4).** v1 said "Identify perfect matches, near-matches, and unmatched. Output: alias table seed." v2 explicitly spells out the fuzzy-match + human-in-the-loop workflow: when a `public.*` alias has no exact `layer0.*` match, the audit tool runs a fuzzy search against `layer0` candidates, presents ranked matches to a human reviewer (Andy), and only writes an alias on confirmation. Unconfirmed entries land in a "needs review" bucket that becomes the gap list for new `layer0` additions or "pre-migration legacy" flags.

**No-user-preservation note (carried in from Athlete_Data_Integration_Spec v2).** Production user state is 1–2 test accounts. Phase 4 (per-user FK migration) can rebuild from scratch rather than backfilling — simplifies the rollout. Captured in §4 Phase 4.

No other structural changes to phase ordering, scope, or risk surfaces.

---

## 1. Purpose

Defines the migration plan for the Vercel app to read all catalog data from `layer0.*` instead of `public.*`. This is the "Option A" path confirmed 2026-05-13: app reads migrate to `layer0.*`; the parallel `public.*` catalogs are deprecated and eventually dropped.

This is **not** a Layer N node spec. It is a strategy document for a multi-phase application migration that lives alongside the AIDSTATION pipeline build. It can be executed independently and on a different cadence from the pipeline work; the pipeline does not block on it, and it does not block the pipeline.

**Scope:**
- All `public.*` catalogs that have a `layer0.*` counterpart: `exercise_inventory`, `equipment_items`, `exercise_equipment`, `training_modalities` (partial — see §3).
- All Vercel-app code paths that read those catalogs (`routes/references.py`, `routes/injuries.py`, `routes/rx.py`, `routes/natural_log.py`, `routes/locales.py`, `routes/purchases.py`, plus engine helpers).
- All per-user app tables that FK to the catalogs (`training_log.exercise_id`, `current_rx.exercise_id`, `injury_exercise_modifications.exercise_id` and `substitute_exercise_id`, `locale_equipment.equipment_id`, `exercise_equipment.exercise_id` and `equipment_id`, `purchase_recommendations.equipment_id`).

**Out of scope:**
- New catalog content design (owned by Layer 0 ETL spec).
- AIDSTATION pipeline node specs (Layer 1+).
- SQLite backend support — explicitly deprecated as part of this migration (D-54).

---

## 2. Why this is non-trivial

The two catalogs are not drop-in replacements for each other. Five categories of work:

### 2.1 Schema shape

| Field | `public.exercise_inventory` | `layer0.exercises` | Migration work |
|---|---|---|---|
| Equipment list | `equipment TEXT` (comma-separated string) | `equipment TEXT[]` | Code must learn to read TEXT[]; consumers that split on commas must use array syntax |
| Muscles worked | `muscles_worked TEXT` (comma-separated) | `primary_muscles TEXT[]` + `secondary_muscles TEXT[]` | Single col splits into two arrays |
| Skills AR carryover | `skills_ar_carryover TEXT` | `skills_ar_carryover TEXT[]` (per drift report) | Array migration |
| Equipment substitutes | (not present) | `equipment_substitutes TEXT[]` + structured columns per Batch B | Pure addition; app can adopt or ignore |
| Physical proxy exercises | (not present) | `physical_proxy_exercises TEXT[]` | Pure addition |
| Movement components | (not present) | `movement_components TEXT[]` (D-22 column) | Pure addition |
| Contraindicated body parts | (not present) | (in `disciplines.body_parts_at_risk` — different table) | Cross-table lookup |

### 2.2 Identity / keys

The `public.exercise_inventory.exercise` column (TEXT, UNIQUE) is the natural-language identifier used throughout the app:

- `training_log.exercise` (denormalized TEXT for stability across catalog edits)
- `current_rx.exercise` (same convention)
- `training_log.exercise_id` (numeric FK, but the denormalized TEXT is the user-facing label)

`layer0.exercises` uses `name` (or equivalent) as its identifier. The two `exercises` columns may or may not align verbatim. If `layer0` uses canonical-form names that differ from the conversational app names ("Push-up" vs "Pushup"), a name-mapping table is required.

**Hard question:** Should the per-user tables continue to denormalize the natural-language exercise name (and update it to match the new canonical), or migrate to a pure-ID reference model? Either is defensible. Denormalization is simpler for displays/logs; pure-ID is cleaner for catalog updates.

### 2.3 Equipment identity

`public.equipment_items.tag` is a freeform machine key seeded from `EQUIPMENT_CATEGORIES` in `init_db.py`. Values like `dumbbell`, `barbell`, `pull_up_bar`.

`layer0.equipment_items.canonical_name` is the canonical name used across all `layer0.*` tables.

These two are not coupled. `locale_equipment.equipment_id` FKs to `public.equipment_items.id`. Migrating to `layer0` means either:
- Building a `tag → canonical_name` mapping table and using it at join time, or
- Migrating `locale_equipment` rows to reference `layer0.equipment_items.id` directly (one-shot data migration).

The latter is cleaner but requires the mapping to be 100% complete and correct before cutover.

### 2.4 Per-user FK references

Several per-user app tables FK directly to `public.*` catalogs:

| Per-user table | Column | FK target | Migration impact |
|---|---|---|---|
| `training_log` | `exercise_id` | `public.exercise_inventory(id)` | High — heavy write path; must keep working through transition |
| `current_rx` | `exercise_id` | `public.exercise_inventory(id)` | High — write path on every plan execution |
| `injury_exercise_modifications` | `exercise_id` | `public.exercise_inventory(id)` | Medium — write path on injury report |
| `injury_exercise_modifications` | `substitute_exercise_id` | `public.exercise_inventory(id)` | Medium — same path |
| `exercise_equipment` | `exercise_id` | `public.exercise_inventory(id)` | Medium — catalog-side, populated once |
| `exercise_equipment` | `equipment_id` | `public.equipment_items(id)` | Medium — same |
| `locale_equipment` | `equipment_id` | `public.equipment_items(id)` | High — write path on locale equipment edit |
| `purchase_recommendations` | `equipment_id` | `public.equipment_items(id)` | Medium — catalog-side |

These FKs cannot all switch at once. The migration must support both schemas concurrently during transition.

### 2.5 Search path / schema qualification

The app's PostgreSQL session has `search_path` defaulting to `public`. Every unqualified `FROM exercise_inventory` resolves to `public.exercise_inventory`. To read from `layer0`, either:

- Change session-level `search_path` to include `layer0`, with `public` after it. Risk: any table that exists in both schemas resolves to whichever appears first; subtle bugs possible.
- Schema-qualify every catalog read: `FROM layer0.exercises`. Higher edit volume but explicit.

**Recommendation:** schema-qualify. Explicit > implicit when the cost is one repeated grep-and-replace pass.

---

## 3. Catalog-by-catalog scope

### 3.1 `exercise_inventory` → `exercises`

**Routes that read `public.exercise_inventory`:**
- `routes/references.py:31` — `SELECT * FROM exercise_inventory ORDER BY discipline, exercise`
- `routes/injuries.py:69` — `SELECT id, exercise, discipline, movement_pattern FROM exercise_inventory ORDER BY discipline, exercise`
- `routes/rx.py:38` — `SELECT ei.* FROM exercise_inventory ei ...`
- `routes/natural_log.py:320` — `SELECT id FROM exercise_inventory WHERE exercise=?`

Each query must be evaluated against `layer0.exercises` schema:
- `discipline` — `layer0.exercises` has discipline associations via `sport_discipline_bridge`. Direct column may not exist; query may need a join.
- `exercise` — likely renamed to `name` in `layer0`. Mapping required.
- `movement_pattern` — needs verification against `layer0.exercises` schema.

**Open verification needed:** dump `layer0.exercises` columns and confirm field-by-field mapping. This is the first sub-task before any route change.

### 3.2 `equipment_items` → `equipment_items`

Both schemas have a table called `equipment_items`. They are not the same:

- `public.equipment_items`: `id SERIAL`, `tag TEXT UNIQUE`, `label TEXT`, `category TEXT`
- `layer0.equipment_items`: per `etl/layer0/schema.sql:36` — `canonical_name`, `equipment_category`, `is_universal`, plus ETL version fields

**Migration approach:** new mapping table `equipment_item_alias` with `(tag TEXT, canonical_name TEXT)`. Seeded once from a manual reconciliation pass. Routes query both tables joined via the alias table. Eventually (post-cutover), per-user FKs migrate to `layer0` and the alias becomes vestigial.

### 3.3 `exercise_equipment` → `exercise_equipment_requirements`

`public.exercise_equipment` is a shared (no user_id) join table: `(exercise_id, equipment_id, option_group)`.

`layer0` has a different model: `exercises.equipment_substitutes TEXT[]` (an array of canonical equipment names per exercise) plus `exercises.equipment_substitutes_structured` (richer JSON structure per Batch D work).

**Migration approach:** drop `public.exercise_equipment`. App reads `layer0.exercises.equipment_substitutes` directly. `option_group` semantics (alternative equipment options) preserved via the structured form.

This is a conceptual model change, not just a schema swap. Worth a dedicated session before executing.

### 3.4 `training_modalities` — separate question

`public.training_modalities` is a flat list of activities (Running, Cycling, etc.) with category and benefits metadata. There is no direct `layer0` equivalent — `layer0` models sports + disciplines, not flat activities.

**Resolution:** decide whether `training_modalities` migrates to `layer0` (new table), or stays in `public.*` as an app-specific concern, or is replaced by `sport_discipline_bridge` queries.

**Recommendation:** stay in `public.*` for now. `training_modalities` is referenced by `coaching.py` context-assembly only, doesn't conflict with anything in `layer0.*`, and `layer0` doesn't have a clean equivalent. Out of scope for this migration. Revisit if the app needs to surface AIDSTATION-aware discipline information directly.

---

## 4. Migration phases

Strategy-level. Each phase needs its own detailed execution spec before it ships.

### Phase 1 — Verification and mapping (no app changes)

**Deliverable:** Field-by-field mapping document for each catalog: `public.exercise_inventory ↔ layer0.exercises`, `public.equipment_items ↔ layer0.equipment_items`. Plus a curated alias table seed file produced through fuzzy-match + human-in-the-loop review.

**Work:**

1. Dump deployed `layer0.exercises` schema (Neon `\d`).
2. Diff against `public.exercise_inventory` schema field-by-field. Output: mapping table.
3. **Alias audit — fuzzy-match + HITL workflow for `public.exercise_inventory.exercise` ↔ `layer0.exercises.name`:**
   1. First pass: exact case-insensitive string match. Anything that matches is auto-aliased and written to the seed file with `confidence = exact`.
   2. Second pass: for every `public.*` value with no exact match, run a fuzzy search against the full `layer0.exercises.name` list. Recommended algorithm: token-set ratio (rapidfuzz `WRatio` or equivalent), normalized to 0–100. Return the top-N candidates (N=5) above a floor threshold (e.g., 60).
   3. Build a review queue: one row per unmatched `public.*` value, with its top-N `layer0` candidates ranked by score.
   4. Present the queue to a human reviewer (Andy). For each `public.*` value, the reviewer either:
       - Picks a candidate → alias written with `confidence = manual_confirmed`.
       - Marks "no good match" → entry lands in the **gap list** for follow-up (new `layer0` addition OR `public.*` "pre-migration legacy" flag — decision per item).
       - Marks "duplicate of another public value" → entry is collapsed; alias points to whatever the canonical entry resolves to.
   5. Output: alias table seed + gap list. The gap list feeds back into Layer 0 ETL (potential new exercise additions) or stays as legacy flags.
4. Repeat step 3 for equipment: `public.equipment_items.tag` ↔ `layer0.equipment_items.canonical_name`. Same exact-then-fuzzy-then-HITL pattern. Equipment is likely a smaller and more constrained vocabulary so review effort is lower; expect more exact matches via the existing canonical-name normalization work (FC-1 / FC-2).
5. Decide naming convention for per-user denormalized fields (continue using app-style names, or adopt canonical names). Document the decision in the mapping file.

**Tooling note.** The fuzzy-match audit tool itself is a one-shot script (Python, rapidfuzz, dumps to a markdown or CSV review file). Not production code — no deployment, no CI integration. The output seed file is checked into the repo alongside this spec; the review session produces the curated final alias table that Phase 2 reads.

**Estimated effort:** 1-2 sessions, including the HITL review pass. Independent of any app or pipeline work.

### Phase 2 — Alias tables and sync ETL

**Deliverable:** Both catalogs coexist; per-user FKs continue pointing to `public.*`; app reads can use either.

**Work:**
1. Create `equipment_item_alias` (`tag TEXT, canonical_name TEXT, layer0_equipment_id INTEGER`).
2. Create `exercise_alias` (`public_exercise_name TEXT, layer0_exercise_name TEXT, layer0_exercise_id INTEGER`).
3. Seed both from Phase 1 mapping output.
4. Add validation routines: catch new `public.exercise_inventory` rows that don't have a `layer0` counterpart; catch new `layer0.exercises` rows that don't have an app alias.
5. Optionally: build a one-way sync ETL that updates `public.exercise_inventory` from `layer0.exercises` (treat `layer0` as source of truth; `public` is downstream). This lets the app catch new exercises without manual seeding.

**Estimated effort:** 1-2 sessions plus a few weeks of bake time to confirm aliases are complete and the sync ETL doesn't introduce bugs.

### Phase 3 — Route-by-route migration

**Deliverable:** App reads from `layer0.*` (via aliases where needed). `public.*` catalogs still exist but are no longer the source of truth.

**Work, in suggested order (lowest-risk first):**

1. **`routes/references.py`** — read-only listing endpoints. Lowest write-path risk. Migrate first as proof-of-concept.
2. **`routes/injuries.py:69`** — injury-modification lookup. Read-only.
3. **`routes/rx.py:38`** — rx fetch. Reads only.
4. **`routes/natural_log.py:320`** — exercise name → ID lookup. Used by AI parsing flows. Migrate to query `layer0.exercises` with name fallback to alias.
5. **`routes/locales.py:60` and equipment writes** — equipment-selection endpoint. Migrate to write via alias; reading already alias-based after Phase 2.
6. **`routes/purchases.py`** — purchase recommendations. Reads-only.
7. **Engine helpers** (`plan_match.py` etc.) — exercise matching logic. Carefully audit; this is where canonical-name choice matters most.

After each route migration: run regression suite. The migrations are reversible until per-user FKs change (Phase 4).

**Estimated effort:** Several sessions. Order can be reshuffled based on operational priorities.

### Phase 4 — Per-user FK migration

**Deliverable:** Per-user tables (`training_log`, `current_rx`, etc.) FK to `layer0.exercises.id` instead of `public.exercise_inventory.id`.

**No-user-preservation simplification (v2).** Production user state at the time of this migration is 1–2 test accounts. The dual-write + backfill + cutover dance described below is the safe pattern for a populated production system. With 1–2 test accounts, an acceptable alternative is: wipe the per-user tables, drop the old FK column, add the new one, regenerate test data against `layer0` FKs. Choose the dance for habit-building or for any production users that exist at migration time; choose the wipe for speed.

**Work (dance pattern, for reference and for once real users exist):**
1. Add `layer0_exercise_id INTEGER` to each per-user table.
2. Backfill from alias for all existing rows.
3. Update write paths to populate both `exercise_id` and `layer0_exercise_id` during transition.
4. Once `layer0_exercise_id` is populated for 100% of rows: switch read paths to `layer0_exercise_id`.
5. Once read paths are stable: drop `exercise_id`.
6. Repeat for `locale_equipment.equipment_id` → `layer0_equipment_id`, etc.

**Work (wipe pattern, viable today):**
1. Wipe per-user tables.
2. ALTER TABLE: drop `exercise_id`, add `layer0_exercise_id` FK to `layer0.exercises(id)`.
3. Regenerate test data against `layer0` IDs.
4. Repeat for `locale_equipment`, etc.

**Estimated effort:** Dance pattern: largest phase, 1–2 sessions per table. Wipe pattern: half a session total.

### Phase 5 — Drop `public.*` catalogs

**Deliverable:** `public.exercise_inventory`, `public.equipment_items`, `public.exercise_equipment` are dropped from `init_db.py`. `_PG_MIGRATIONS` adds the drops.

**Work:** Drop tables. Drop seed code. Drop alias tables (or keep them as a thin view for backward compat — decide at the time).

**Estimated effort:** One session. Final cleanup.

---

## 5. Decisions to lock before Phase 1

1. **Per-user denormalization:** Continue denormalizing exercise names on per-user tables (matching `layer0.exercises.name`), or migrate to pure-ID reference?
   - **Recommendation:** continue denormalizing, but adopt `layer0` canonical names as the source. Tradeoff: simpler reads; updates to `layer0.exercises.name` require cascade updates to per-user denormalized columns (rare event; can be a one-shot ETL).

2. **Schema-qualified vs `search_path`:**
   - **Recommendation:** schema-qualified. Already covered in §2.5.

3. **Sync ETL direction:** Is `layer0.*` the source of truth (and `public.*` is downstream until dropped), or is it the reverse during transition?
   - **Recommendation:** `layer0.*` as source of truth throughout. `public.*` is the deprecated tail. No reverse-sync.

4. **`training_modalities` migration:** stays in `public.*` (per §3.4) — confirm or override.

5. **SQLite backend:** Drop entirely as part of this migration. Affects `_SQLITE_MIGRATIONS`, `database.py` adapter, type-compat logic.
   - **Recommendation:** drop. Already locked per 2026-05-13 session.

6. **`exercise_equipment` model change** (§3.3): drop and read `layer0.exercises.equipment_substitutes` directly, or keep as a join table?
   - **Recommendation:** drop. Reduces schema surface area; matches `layer0` model.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Alias completeness — some `public.exercise_inventory` rows have no `layer0` counterpart | Phase 1 audit explicitly enumerates the gaps; missing entries get added to `layer0` or kept in `public` with a "pre-migration legacy" flag |
| Name drift — `layer0.exercises.name` updates break per-user denormalized strings | Sync ETL detects drift; cascade-update path for per-user tables on canonical-name change. Treat as rare event |
| Concurrent writes during dual-write windows (Phase 4) — `exercise_id` and `layer0_exercise_id` diverge | Single write path in route layer that populates both atomically; CI test asserting they always match |
| Foreign key cascade behavior changes — `public.exercise_inventory` rows being deleted while per-user FKs still reference them | Defer drop until Phase 5; until then `public` rows are never deleted, only `superseded` |
| Schema-qualified queries break if `layer0` schema gets renamed or restructured | Long-term: it doesn't. Layer 0 schema is stable per `Layer0_ETL_Spec_v7`. Short-term: search_path fallback as escape hatch |
| Test data and dev fixtures depend on `public.*` IDs | Update fixtures to use `layer0.*` IDs as Phase 4 progresses; this is part of the per-table migration work |

---

## 7. Open items

| ID | Item | Phase |
|---|---|---|
| D-52.1 | Phase 1 mapping document — `public.exercise_inventory ↔ layer0.exercises` | Phase 1 |
| D-52.2 | Phase 1 mapping document — `public.equipment_items ↔ layer0.equipment_items` | Phase 1 |
| D-52.3 | `exercise_alias` and `equipment_item_alias` schemas | Phase 2 |
| D-52.4 | Sync ETL spec — `layer0.exercises` → `public.exercise_inventory` | Phase 2 |
| D-52.5 | Route migration order and dependency map | Phase 3 |
| D-52.6 | Per-user FK migration sequence | Phase 4 |
| D-52.7 | Final `public.*` drop migration | Phase 5 |

These sub-items live under D-52 in `Project_Backlog`. Promote to top-level D-NN IDs when Phase 1 starts and the work surface clarifies.

---

## 8. Open dependencies and forward references

- **Athlete_Data_Integration_Spec §2.4** assumes the target state described here. Integration spec's field-mapping (§7) targets `layer0` for catalog resolution.
- **Layer 1 sourcing** (Control_Spec §3) depends on this migration only insofar as Layer 1's `q_layer1_payload` query reads from `public.*` plus `layer0.*` for catalog resolution. Pre-migration, it can use either; post-migration, exclusively `layer0` for catalogs.
- **Layer 4 plan generation** outputs against `layer0.exercises.name`. Plan_items table writes the canonical name; if denormalization conventions change, plan-gen output handling must follow.

---

## 9. Gut check

**What this plan gets right.**

- Phasing isolates the high-risk per-user FK migration (Phase 4) from the lower-risk route migrations (Phase 3). Each phase can stop or pause without blocking the next.
- Alias tables (Phase 2) let the app coexist with both schemas during transition; no flag day required.
- Explicit "out of scope" decisions (training_modalities, SQLite) prevent scope creep.

**Risks.**

- This is genuinely a multi-month project at the pace AIDSTATION work is progressing. It can run in parallel with Layer 3 / Layer 4 design but it will compete for execution-time attention.
- The audit in Phase 1 could turn up enough mismatches between `public.*` and `layer0.*` that the migration spec needs major revision. The phases assume the catalogs are conceptually close; if they've drifted further than `L3-Discovery_Pre-Spec-Trio_Inventory §C` suggests, this plan is wrong.
- The "denormalize using `layer0` canonical names" recommendation depends on `layer0.exercises.name` values being stable. If they churn, every per-user denormalized name churns with them — that's a lot of writes. Worth verifying ETL stability before committing.

**What might be missing.**

- No story for `training_methods` migration. Currently in `public.*`; no `layer0` equivalent. Probably out of scope but should be confirmed.
- No story for new exercises added by athletes or coaches (if/when that becomes a feature). The current model assumes catalogs are read-only at the app layer. Future-state user-generated catalog content would need its own design.
- No mention of indexing strategy on `layer0.*`. The current app indexes on `public.exercise_inventory.exercise` (UNIQUE) and `public.equipment_items.tag` (UNIQUE). Equivalent indexes on `layer0.exercises.name` / `layer0.equipment_items.canonical_name` need to exist before high-volume reads cut over.

**Best argument against this plan.**

A simpler approach: keep `public.*` catalogs as the app's source of truth permanently, sync from `layer0.*` periodically. AIDSTATION pipeline still reads `layer0.*` for plan generation; app reads `public.*` for app-facing UI. The two never directly interact at the catalog level.

This is Option B from the original L3-Discovery decision frame. It was rejected because it accepts permanent drift; the rejection still holds. But it's worth re-stating: if executing this migration becomes a multi-month tax that delays Layer 3 / Layer 4 work, Option B is a real fallback. The migration is the right long-term call; whether it's the right *now* call depends on capacity.

---

*End of Catalog_Migration_Plan v1.*
