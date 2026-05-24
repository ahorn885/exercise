# D-73 Phase 5.2 Walkthrough — ETL Terrain-Vocab Drift Fix (Bucket C sub-item k) — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — closes the Layer 0 architecture debt surfaced by the predecessor RouteLocalesValidatorHotfix prod walkthrough. The `python -m etl.layer0.run` ETL was silently superseding the canonical TRN-xxx structured terrain vocab from `migrate_terrain_types.sql` on every re-run; this slice moves the structured rows code-side so re-runs are idempotent.
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_RouteLocalesValidatorHotfix_PR129Validation_2026_05_23_Closing_Handoff_v1.md`
**Branch:** `claude/optimistic-galileo-kSYys`
**Status:** 4 substantive files (under 5-file ceiling). Container-runnable subset 805 → 805 (no regressions). `etl/tests/test_vocabulary_md.py` 15 → 18 (+3 net: 1 deleted Section-K test, 3 new structured-shape tests; existing count flipped 15 → 16). Migration warning lifted.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md → predecessor handoff → `./scripts/verify-handoff.sh`. Anchor sweep returned all ✅ across 29 referenced files; working tree clean on `claude/optimistic-galileo-kSYys`; backlog pointer stable at `Project_Backlog_v62.md`; predecessor §8 table claims spot-checked (validator `role=='start'` raise removed, structural checks preserved, 2 tests renamed). No drift between handoff narrative and on-disk state.

---

## 2. Session narrative

Andy picked Bucket C sub-item (k) at the AskUserQuestion gate — the ETL terrain-vocab drift fix carried forward from the predecessor RouteLocalesValidatorHotfix slice. The investigation traced the root cause to two competing writers against `layer0.terrain_types`:

- **`etl.layer0.run`** (callable as `python -m etl.layer0.run`): `_parse_terrain()` in `etl/layer0/extractors/vocabulary.py:217-254` parsed the `Vocabulary_Audit_v2.md` Section 3 terrain table into 15 minimal-shape rows (`canonical_name` + `notes` only — the col-7 alias list joined with "; "). Then `etl/layer0/run.py:116-123` called `insert_versioned()` writing those rows tagged with the current `0C-vN` and supersededing every prior `0C-v*` row via `LIKE '0C-v%'` (`etl/layer0/db.py:122-130`).
- **`etl/sources/migrate_terrain_types.sql`** (one-shot script run 2026-05-09 against production Neon): added 7 enrichment columns + `UNIQUE (terrain_id, etl_version)` + inserted 16 hand-curated `TRN-001..TRN-016` structured rows tagged `0C-v2.0-r2`.

The collision: `0C-v2.0-r2` matches `LIKE '0C-v%'`, so the next `etl.layer0.run` invocation supersedes the migrate script's rows. May 10 and May 20 ETL re-runs each undid the May 9 migration. The defensive `terrain_id IS NOT NULL` filter shipped in the BucketE_TerrainNone_FrameworkSport slice kept the dropdown clean on the read side, but the underlying data drift kept resurfacing.

`/plan` Triggers fired:

- **Trigger #3 (cross-layer schema)** + **Trigger #5 (architectural alternatives)** — investigated 4 paths (A1 code-side constants / A2 promote-to-markdown-table / A3 run-migration-SQL-as-post-step / B skip-list-terrain-in-run.py) and presented options + tradeoffs + recommendation + gut check before any implementation. Andy picked **A1** at the AskUserQuestion gate.

A1's rationale: mirrors the D-73 Phase 2.4-Prep `_TOGGLE_ALSO_SATISFIES` / `_TOGGLE_GATED_DISCIPLINES` precedent at `etl/layer0/extractors/vocabulary.py:270-278` — Layer 2C facts that weren't in the markdown source moved code-side, and the ETL writes them directly. Same shape applies here: the structured terrain attributes (`simulatable='partial'` + 2-sentence `simulation_note` per row, structured enum-like `category` / `environment` values, boolean `requires_elevation` / `technical_surface` flags) aren't in `Vocabulary_Audit_v2.md` today and are closer to code than narrative markdown.

`/plan` Triggers DEFERRED to follow-on slices:

- **Coaching-flag emission for missing start/finish anchors** — companion to PR #131; ~1-2 file slice.
- **Bucket C sub-items (a)-(j)** — terrain/locale vocab cleanup design conversation (Time-of-Day not a terrain factor / Social not a terrain factor / Generic vocab cleanup / Climbing gym-vs-outdoor split / water-type expansion / terrain-vs-equipment merge / Cycling Trainer dedup / Mapbox free-text removal / Layer 2B classifier audit). Each needs Trigger #2 + #5 design pass.
- **Bucket E.(b)-B2 + E.(c)-C1 follow-on** — specs already pinned in CARRY_FORWARD; ~6-9 files.
- **#8 "locales" → "locations" rename** — ~9 templates, mechanical.

---

## 3. File-by-file edits

### 3.1 `etl/layer0/extractors/vocabulary.py` — code-side terrain constants

- NEW module-level `_TERRAIN_STRUCTURED_ROWS: list[dict[str, Any]]` (16 dicts × 9 keys each — `terrain_id` / `canonical_name` / `category` / `requires_elevation` / `technical_surface` / `environment` / `simulatable` / `simulation_note` / `notes`). Values lifted verbatim from `etl/sources/migrate_terrain_types.sql` §3 INSERT block. 24-line audit-trail comment above the constant explains the drift root cause + the Phase 2.4-Prep precedent mirror.
- `_parse_terrain(text)` body replaced. Old body parsed the audit markdown's terrain table (`_slice_section` → `_slice_block` → `_parse_md_table` → grouped-by-Section-K-label). New body: `return [dict(row) for row in _TERRAIN_STRUCTURED_ROWS]`. Docstring updated to note text arg is accepted for parser-signature parity but unused.

Net delta: ~205 lines added (the constant dominates), ~37 lines removed (old parsing logic). Function signature unchanged.

### 3.2 `etl/layer0/run.py` — extend insert columns

`layer0.terrain_types` `insert_versioned` call updated:

- Old columns list: `["canonical_name", "notes"]`.
- New columns list: `["terrain_id", "canonical_name", "category", "requires_elevation", "technical_surface", "environment", "simulatable", "simulation_note", "notes"]`.
- Old row-tuple comprehension: `[(r["canonical_name"], r["notes"]) for r in vocab["terrain_types"]]`.
- New row-tuple comprehension: extracts all 9 fields per row.

Net delta: +12 / -3 lines.

### 3.3 `etl/layer0/schema.sql` — fold the migration into canonical schema

Appended after the existing `phase_load_weekly_totals` ALTER block (at the end of the "Additive column migrations" section):

- 7 `ALTER TABLE layer0.terrain_types ADD COLUMN IF NOT EXISTS ...` statements (terrain_id / category / requires_elevation / technical_surface / environment / simulatable / simulation_note) — matches `migrate_terrain_types.sql` §1 verbatim.
- `DO $$ ... END $$` block that adds `CONSTRAINT terrain_types_terrain_id_etl_version_key UNIQUE (terrain_id, etl_version)` if not present (idempotent — uses `pg_constraint` lookup).
- 5-line preamble comment naming the slice + the code-side replacement origin at `vocabulary.py::_TERRAIN_STRUCTURED_ROWS`.

`apply_schema()` (`etl/layer0/db.py:42`) sends the full schema file via a single `cur.execute(sql)`; psycopg2 handles the DO block correctly. Idempotent across re-runs.

Net delta: +28 lines appended.

### 3.4 `etl/tests/test_vocabulary_md.py` — update terrain tests

- **DELETED** `test_terrain_canonical_uses_section_k_labels` — the Section-K labels (e.g. "Hill / mountain access", "Trail access") are no longer the canonical names; the audit terrain block is dead source for terrain_types.
- **MODIFIED** `test_terrain_count` — count assertion flipped from 15 to 16. New audit-trail comment names the slice + the code-side rationale.
- **NEW** `test_terrain_ids_unique_and_sequential` — asserts the 16 IDs are `TRN-001..TRN-016` with no gaps + no duplicates.
- **NEW** `test_terrain_known_canonical_names_present` — asserts 9 well-known names present (Road / Paved, Technical Trail, Mountain / Alpine, Pool, Whitewater, Snow / Winter Alpine, Climbing Gym, Pump Track / Skills Course, Indoor / Gym).
- **NEW** `test_terrain_structured_fields_populated` — for every row asserts: (a) all 9 expected keys present; (b) `requires_elevation` + `technical_surface` are bool; (c) `environment` ∈ {"Outdoor", "Indoor"}; (d) `simulatable` ∈ {"full", "partial", "none"}; (e) `category` ∈ {"Foot", "Water", "Snow", "Climbing", "MTB", "Gym"}.

Net delta: +30 lines (1 deleted ~10-line test; 3 new tests average ~12 lines each + count comment expanded).

### 3.5 `etl/sources/migrate_terrain_types.sql` — RETIRED tombstone

Header expanded with a 16-line RETIRED block explaining: the drift root cause, the 2026-05-09 + 2026-05-10 + 2026-05-20 timeline, the code-side replacement at `etl/layer0/extractors/vocabulary.py::_TERRAIN_STRUCTURED_ROWS`, the schema migration fold-in at `etl/layer0/schema.sql`, and the "do not run; kept for audit trail only" instruction. Original header preserved below for context. SQL body unchanged (the file is no longer expected to execute).

Net delta: +21 header lines.

---

## 4. Code / tests

**Tests:** ETL — `etl/tests/test_vocabulary_md.py` 15 → 18 (+3 net: 1 deleted, 3 added; existing count flipped). Non-etl container-runnable subset: 805 → 805 (no regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a surfaces).

Reproducer (ETL only):

```
PYTHONPATH=. pytest etl/tests/test_vocabulary_md.py
# 18 passed in 0.07s
```

Full container subset (predecessor's exact invocation):

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py tests/test_layer4_context.py \
                    tests/test_layer4_payload.py tests/test_layer4_hashing.py \
                    tests/test_layer4_cache.py tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
                    tests/test_layer2a.py
# 805 passed, 12 skipped in 1.49s
```

Including `etl/tests/` adds 139 more (4 test files): `etl/tests/test_extractor_parsers.py` 28 + `etl/tests/test_sum_to_100.py` 4 + `etl/tests/test_v10_parsers.py` 39 + `etl/tests/test_vocabulary_md.py` 18 + `etl/tests/test_vocabulary_transforms.py` 50 = 139. Combined run: **944 passed, 12 skipped in 3.10s**.

**Python syntax check:** `python3 -m py_compile etl/layer0/extractors/vocabulary.py etl/layer0/run.py` passes.

**No-regression confirmation:** All non-etl tests still pass with identical counts. The only changed test counts are in `etl/tests/test_vocabulary_md.py`.

---

## 5. Manual §5.0 verification — owed steps

**Step 1 — first post-merge prod Neon `python -m etl.layer0.run` invocation.** After this slice merges + reaches production, the next ETL run will write 16 structured rows under a fresh `0C-vN` etl_version and supersede the existing `0C-v2.0-r2` rows (Andy's 2026-05-23 manual data fix). Confirm:

- `SELECT COUNT(*) FROM layer0.terrain_types WHERE superseded_at IS NULL AND terrain_id IS NOT NULL` returns **16**.
- `SELECT COUNT(*) FROM layer0.terrain_types WHERE superseded_at IS NULL AND terrain_id IS NULL` returns **0**.
- `SELECT etl_version, COUNT(*) FROM layer0.terrain_types WHERE superseded_at IS NULL GROUP BY etl_version` returns 1 row at the new `0C-vN`.
- Spot-check `SELECT terrain_id, canonical_name, simulatable FROM layer0.terrain_types WHERE superseded_at IS NULL ORDER BY terrain_id` matches the 16 TRN-001..TRN-016 structured rows.
- `/locales/<any-slug>/edit` + `/profile/race-events/<id>/edit` + `/profile/race-events/new` + `/onboarding/target-race` all render the terrain dropdown / checkbox grid normally (no `None — <name>` entries; 16 structured TRN-xxx options).

Captured in `CARRY_FORWARD.md` Manual §5.0 walkthrough section as a 1-step scenario.

**Note on the lifted warning:** the predecessor's "do NOT run `python -m etl.layer0.run` against production Neon" warning is **lifted** by this slice. Re-runs are now idempotent for terrain_types — the new structured rows write under the fresh `0C-vN` and the prior `0C-v2.0-r2` rows supersede cleanly. Semantic content is identical (same 16 TRN-xxx rows); only the version label is fresher.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Coaching-flag emission for missing start/finish anchors** (companion to PR #131). The route-locales validator was loosened 2026-05-23 to silently accept missing start/finish anchors; downstream the Layer 4 race-week brief should now emit `route_locales_missing_start_anchor` / `route_locales_missing_finish_anchor` flags in `_validate_inputs` so the LLM has explicit signal rather than fabricating an anchor from inference. ~1-2 file slice (`layer4/orchestrator.py` or `layer4/context.py` flag-emission + `tests/test_layer4_orchestrator.py` coverage). No `/plan` triggers fire.

### 6.2 Alternative pivots

- **Bucket E.(b)-B2 + E.(c)-C1 follow-on slice** — specs already pinned in `CARRY_FORWARD.md` (race_events.included_discipline_ids TEXT[] NULL + RaceTerrainEntry.discipline_id: str | None). ~6-9 files; needs ceiling-break ratification at scope gate.
- **Bucket C sub-items (a)-(j)** — terrain/locale vocab cleanup design conversation. Trigger #5 + Trigger #2 + Trigger #3 each. Best done as a paired design pass + implementation slice; ratify scope at AskUserQuestion gate.
- **#8 "locales" → "locations" rename** — ~9 templates, mechanical. No triggers; lowest-risk next-slice candidate.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on the body-part-to-movement-constraints mapping.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C sub-item (k) annotated ✅ Shipped; migration warning lifted).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_ETLTerrainVocabDriftFix_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Forward-pointer (ETL run on prod Neon):** the next prod Neon `python -m etl.layer0.run` is safe to invoke and will leave terrain_types in the correct shape; recommend running it as part of the post-merge verification (§5 Step 1 above) so the manual-fix `0C-v2.0-r2` rows transition cleanly to the new ETL-managed `0C-vN`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Path **A1** (code-side TRN-xxx constants in `vocabulary.py`) over A2 (promote to structured markdown), A3 (run migration SQL as post-step), B (skip-list terrain_types in run.py) | Andy at AskUserQuestion gate | Mirrors the D-73 Phase 2.4-Prep `_TOGGLE_ALSO_SATISFIES` precedent already established in the same module. Single source of truth; re-runs become idempotent. Structured terrain attributes (`simulatable='partial'`, 2-sentence `simulation_note` per row, enum-like `category`/`environment` values) are closer to code than narrative markdown — promoting to a markdown table (A2) creates new authoring burden without ergonomic gain. A3 sequences around the architecture problem rather than fixing it; B accepts permanent drift and forces a new SQL migration per future terrain vocab addition. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `etl/layer0/extractors/vocabulary.py` `_TERRAIN_STRUCTURED_ROWS` contains 16 dicts | ✅ `grep -c "\"terrain_id\": \"TRN-" etl/layer0/extractors/vocabulary.py` returns 16 |
| `_parse_terrain` returns the structured rows code-side (text arg unused) | ✅ `grep -A1 "def _parse_terrain" etl/layer0/extractors/vocabulary.py \| head -3` shows updated docstring |
| `etl/layer0/run.py` `layer0.terrain_types` insert uses the 9-column list | ✅ `grep -A2 "layer0.terrain_types" etl/layer0/run.py \| head -5` shows the extended columns |
| `etl/layer0/schema.sql` carries 7 `ADD COLUMN IF NOT EXISTS` for `terrain_id` etc. | ✅ `grep "terrain_types_terrain_id_etl_version_key" etl/layer0/schema.sql` returns 2 hits (the DO-block guard + CONSTRAINT name) |
| `etl/sources/migrate_terrain_types.sql` carries RETIRED header | ✅ `grep "RETIRED 2026-05-24" etl/sources/migrate_terrain_types.sql` returns 1 hit |
| `etl/tests/test_vocabulary_md.py` test_terrain_count flipped to 16 | ✅ `grep "len(parsed\\[\"terrain_types\"\\]) == 16" etl/tests/test_vocabulary_md.py` returns 1 hit |
| `etl/tests/test_vocabulary_md.py` 3 new structured tests present | ✅ `grep "test_terrain_ids_unique_and_sequential\\|test_terrain_known_canonical_names_present\\|test_terrain_structured_fields_populated" etl/tests/test_vocabulary_md.py` returns 3 hits |
| `etl/tests/test_vocabulary_md.py` Section-K test deleted | ✅ `grep "test_terrain_canonical_uses_section_k_labels" etl/tests/test_vocabulary_md.py` returns 0 hits |
| `etl/layer0/extractors/vocabulary.py` + `etl/layer0/run.py` pass `python3 -m py_compile` | ✅ |
| ETL `test_vocabulary_md.py` 15 → 18 passed | ✅ pytest run |
| Container-runnable subset 805 → 805 passed + 12 skipped (unchanged) | ✅ pytest run in 1.49s |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C sub-item (k) annotated ✅ Shipped; migration warning lifted | ✅ |

---

## 9. Files shipped this session

**Substantive (4 files; under 5-file ceiling):**

1. `etl/layer0/extractors/vocabulary.py` — `_TERRAIN_STRUCTURED_ROWS` code-side constant + `_parse_terrain` body replaced. +205 / -37.
2. `etl/layer0/run.py` — terrain insert call extended to 9-column shape. +12 / -3.
3. `etl/layer0/schema.sql` — 7 `ADD COLUMN IF NOT EXISTS` + DO block for `UNIQUE (terrain_id, etl_version)` constraint. +28 / -0.
4. `etl/tests/test_vocabulary_md.py` — 1 deleted Section-K test; 3 new structured-shape tests; `test_terrain_count` count flipped 15 → 16. +30 / -10.

**Bookkeeping (4 files; do not count against ceiling):**

5. MODIFIED `etl/sources/migrate_terrain_types.sql` — RETIRED tombstone header added; SQL body kept for audit trail. +21 / -0.
6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor line preserved.
7. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket C sub-item (k) annotated ✅ Shipped with full slice summary; "do NOT run etl.layer0.run" warning lifted.
8. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_ETLTerrainVocabDriftFix_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C sub-item (k) ETL terrain-vocab drift fix shipped end-to-end** ✅ — 4 substantive files; code-side `_TERRAIN_STRUCTURED_ROWS` mirrors Phase 2.4-Prep `_TOGGLE_ALSO_SATISFIES` precedent. `python -m etl.layer0.run` invocations now idempotent for terrain_types. Re-runs against prod Neon are safe and recommended as part of post-merge verification (Andy's 2026-05-23 manual data fix transitions cleanly to the new ETL-managed `0C-vN` rows).
- **Manual §5.0 walkthrough §5 Step 1 added** — verify prod Neon row counts after first post-merge ETL run.
- **Migration warning lifted** — the predecessor's "do NOT run `python -m etl.layer0.run` against production Neon" carry-forward is closed.
- **Bucket C still carries sub-items (a)-(j)** — terrain/locale vocab cleanup design conversation deferred (each item needs Trigger #2 + #5 design pass).

**End of handoff.**
