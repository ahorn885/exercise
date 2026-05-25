# D-73 Phase 5.2 — R6 Discipline-ID Renumber + Two Collapses — Closing Handoff

**Session:** D-73 Phase 5.2 follow-on. The deferred **R6** dedicated id-change session: clean sequential discipline-ID renumber to **D-001..D-029** (suffixes absorbed, gaps closed) **plus** the two craft collapses — kayak D-008a/b → **D-010 "Kayaking"**, mountain-running D-022/D-023 → **D-024 "Mountain Running"**. Ratified at two AskUserQuestion gates (full R6 scope + clean-sequential scheme), after a surface map surfaced — and Andy accepted — that the collapse flattens injury/stimulus/skill data the terrain re-model never absorbed.

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitRemodel_Slice6_RendererMigration_V2Retirement_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/brave-lovelace-nLUyM` (PR draft)
**Status:** Shipped. 37 code/SQL/test files renumbered (551 token rewrites) + workbook → v11 (409 cell rewrites + 2-row collapse) + collapse data unions + whitewater-conditional retirement + design doc + bookkeeping. **Neon re-extract owed to Andy** (no DATABASE_URL in the build container). Tests 1631 → **1630**.

---

## 1. Session-start verification (Rule #9)

Continued on the Slice 6 closing handoff. Ran `scripts/verify-handoff.sh`: all ✅ except one expected ❌ (`tests/test_layer2_modality.py` MISSING — the intended Slice-6 deletion; the script lists deleted-but-referenced paths). Read `CLAUDE.md` / `CURRENT_STATE.md` / `CARRY_FORWARD.md` / Slice-6 handoff / `PR_Verification_Status.md`. Working tree clean on `claude/brave-lovelace-nLUyM` (== `origin/main`, Slice 6 PR #153 merged). **No drift.**

## 2. Session narrative + the premise finding

Andy opened "lets work" on the Slice-6 handoff and picked **R6** (the architect-recommended next move) from the next-move menu. R6 is a Trigger #2 + #3 + #5 task, so before any code I ran a thorough Explore surface map (169 reference sites) + verified the load-bearing claims firsthand.

**The map contradicted R6's stated premise.** The Slice-6 handoff said R6 was unblocked because "the terrain axis is fully consumed → the gate is satisfied." But that only covers the **terrain** axis. Verified on disk, both collapse pairs carry **disjoint** data on three axes the terrain re-model never touched: **injury** (`layer0.disciplines.body_parts_at_risk` — uphill hip-flexor/calf/achilles vs downhill quad/IT-band eccentric; whitewater adds forearm), **stimulus** (`stimulus_components`), and **skill + conditional inclusion** (`whitewater_handling` toggle gated to D-008b only; Layer 2A auto-includes whitewater only when duration ≥ 20h / nav). None of 2D/L3/2A reads the Layer 2B terrain axis, so collapsing flattens that data with no recovery path.

I put this finding to Andy with options (mtn-run-only/hold-kayak · collapse-both · hold-both/re-scope · full-R6) + recommendation (mtn-run only, hold kayak, drop the cosmetic renumber) + gut check. **Andy picked Full R6 as written.** A second gate on the numbering scheme (minimal-safe in-place · clean-sequential · collapses-only) → **clean sequential** (the max-churn option; ~24 of 29 ids change meaning), chosen with the silent-mismap risk laid out explicitly.

## 3. Approach (de-risked)

1. **Authoritative artifact first:** `Discipline_ID_Renumber_R6_Design_v1.md` — the old→new map (§2), collapse-union spec (§3), file scope (§4), execution order (§5), verification (§6), owed-to-Andy Neon steps (§7). The map is the single source of truth; everything derives from it.
2. **Mechanical renumber via collision-safe script** (`/tmp/renum.py`, not committed): single-pass `re.sub(r"D-\d{3}[a-z]?", map-lookup)` — re.sub never re-scans its output, so `D-005→D-006` can't double-apply, and the greedy `[a-z]?` makes `D-005a` match as a whole token. 551 rewrites across 37 `.py`/`.sql` files. Sentinels (`D-030/031/099/997/999`) absent from the map → untouched.
3. **Workbook via a committed, reviewable openpyxl transform** (`etl/sources/migrate_discipline_ids_R6.py`) → `Sports_Framework_v11.xlsx` (both `etl/sources/` + `aidstation-sources/data/`): renumber all string cells + collapse the Discipline Library rows. (Chosen over silently rewriting a non-reviewable binary I can't ETL-validate.)
4. **Hand surgery** for the non-mechanical parts: collapse data unions, the whitewater conditional retirement, display-name survivors, count assertions.
5. **Verify:** full suite green + grep-clean of suffix ids.

## 4. File-by-file edits

### Mechanical renumber (script, 37 files)
All of `layer1..4/`, `layer2*/`, `routes/`, repo-root `.py` referencing ids; all `tests/test_layer2*.py` / `test_layer4_*.py` / `test_routes_race_events.py` / `test_race_events_repo.py` / `test_discipline_display_names.py`; `etl/layer0/extractors/*.py`, `etl/layer0/run.py`, `etl/sources/*.py`, `etl/tests/test_v11_parsers.py`; live `.sql` in `etl/sources/` + `aidstation-sources/migrations/`.

### Collapse hand-surgery
- **`discipline_display_names.py`** — merged dup D-010 → "Kayaking", dup D-024 → "Mountain Running"; rewrote the (renumber-mangled) docstring; pruned to 29 entries.
- **`etl/sources/populate_stimulus_components.sql`** + **`aidstation-sources/migrations/`** copy — unioned the two D-010 + two D-024 UPDATEs.
- **`etl/sources/migrate_disciplines_add_body_parts_at_risk_v1.sql`** — unioned D-010 (+Forearm) + D-024 (uphill ∪ downhill); fixed the verification block (`v_total_rows <> 29`, baseline array deduped to 29, count comments/NOTICE 31→29).
- **`etl/sources/populate_discipline_technique_foci.sql`** — deduped intra-array `D-010`/`D-024` repeats (`<> 35` TF-row check unaffected).
- **`etl/sources/populate_substitute_covers.py`** (+ aidstation-sources copy) — deduped `GRIP_OVERCLAIM_SOURCES` set literal.
- **`populate_skill_capability_toggles.sql`** — `whitewater_handling` now gates D-010 (mechanical renumber; the design's intended retarget).

### Whitewater conditional retirement (the substantive code change + accepted regression)
- **`layer2a/builder.py`** — removed `_WHITEWATER_DISCIPLINE_ID` + `_AR_DURATION_THRESHOLD_HOURS` and all 5 usage sites (resolve-inclusion block, both rationale branches, the coaching-flag branch, the sleep-dep clause). Kayaking (D-010) is now an ordinary discipline; only the **nav** conditional (D-015) remains. (`race_duration_hours` is now threaded-but-unused in 3 internal helpers — left as-is to avoid 3-signature churn in a high-risk migration.)
- **`tests/test_layer2a.py`** — fixture D-010 → ordinary "Kayaking"; reworked `TestARBaseline` assertions (D-010 plain included; 1 conditional flag not 2); **deleted** `TestShortAR` (whitewater auto-out); reworked the unresolved-conditional edge test to nav-only.

### Workbook + ETL
- **NEW `Sports_Framework_v11.xlsx`** (×2 locations) via **NEW `etl/sources/migrate_discipline_ids_R6.py`**.
- **`etl/layer0/run.py`** — `SPORTS_XLSX` → v11; `SOURCE_VERSION_0A` → `0A-v11.0` + rationale comment.
- **`etl/layer0/extractors/sports_framework.py`** — module + pairing-matrix docstrings de-mangled (v10→v11; "D-008 split" narrative removed).
- **`etl/tests/test_v10_parsers.py` → `test_v11_parsers.py`** (git mv) — repointed at v11.

### Test count fixes
- **`tests/test_discipline_display_names.py`** — count 31→29; replaced the two now-tautological "kept distinct" tests with collapse-confirmation tests.
- **`tests/test_routes_race_events.py`** — D-010 label expectation "Whitewater Kayaking" → "Kayaking".

### Design + bookkeeping
- NEW `Discipline_ID_Renumber_R6_Design_v1.md`; `CARRY_FORWARD.md` (R6 → SHIPPED + owed-Neon); `BestFitModality_Spec_v4.md` (R6 row → SHIPPED + premise note); `CURRENT_STATE.md`; this handoff.

## 5. Code / test results

- **Full suite `python -m pytest tests/`: 1630 passed / 16 skipped** (−1 vs 1631 = the deleted `TestShortAR.test_8h_duration_excludes_whitewater`; all other whitewater fallout reworked in place). `etl/tests/`: 139 passed. **Zero unexplained regressions.**
- **Grep-clean:** no live `.py`/`.sql` references a retired suffix id (`D-004b|D-005a|D-008a|D-008b`) outside explanatory comments + the transform script's map. v11 workbook: 0 suffix-form ids, 29 disciplines, survivor names correct, no dup ids in Discipline Library.
- All touched `.py` compile; the renumber is collision-safe + prefix-safe (single-pass map-lookup).
- **Sandbox:** `python -m pip install -r requirements.txt --ignore-installed blinker && python -m pip install pytest && python -m pip install openpyxl`, then `python -m pytest tests/`.

## 6. Next session pointers

### 6.1 OWED TO ANDY — Neon re-extract (blocks go-live; cannot run in the build container — no DATABASE_URL)
Runtime reads `layer0.*` by pinned `etl_version_set`; new-id code against an un-re-extracted Neon (old ids) breaks every discipline lookup, so this MUST ship with the code:
1. `python -m etl.layer0.run` against the v11 workbook → `0A-v11.0` rows.
2. Apply the renumbered populate scripts (stimulus / body_parts / technique foci / skill toggles / terrain gaps).
3. Re-pin the deployed `etl_version_set` `0A` → `0A-v11.0`.
4. **Validate:** (a) `SELECT COUNT(*) FROM layer0.disciplines WHERE superseded_at IS NULL` = 29; (b) **pairing-count guard** — `discipline_pairing` row-count non-decreasing vs the v10 baseline (the `extract_pairing_b2b_fallback` name→id lookup silently drops unresolved pairings); (c) reconcile the duplicate D-010/D-024 rows the collapse leaves in the **Pairing Matrix / Substitution Map / Training Gaps / Cross-Sport Properties** sheets against each table's UNIQUE-constraint first-seen-wins dedup (the transform script intentionally did NOT hand-merge these — they need the live ETL loop to validate; see design §4 + §7).

### 6.2 Known follow-ons (low priority)
- **`etl/sources/generate_body_parts_at_risk_migration.py`** + its source `D23_Curation_Reference_v1.md` are **pre-R6 authoring artifacts** (the generator writes to a non-repo `/mnt/user-data/outputs/` path and reads the curation MD). The deployed `.sql` was hand-reconciled (29 rows, unions); regeneration would need the curation doc renumbered + the two collapses merged first. Stale-but-harmless (not in the deploy path).
- **Spec narrative sweep:** per-layer specs (`Layer2A/B/C/D_Spec.md`, `Layer0_ETL_Spec_v7.md`) still cite old discipline ids in prose/examples. Not runtime-load-bearing (the design doc is the normative map). A doc-sweep can renumber them; mechanical rewrite risks corrupting historical examples, so do it deliberately.
- **Kayak regression watch:** whitewater skill-gating + cold-exposure stimulus now apply to *all* Kayaking (D-010), including flat-water-only contexts. If real plan/brief output over-applies whitewater prep to a flat race, that's the accepted regression surfacing — the fix would be a net-new terrain-conditional skill/stimulus path (its own design), not a re-split.

### 6.3 Other carried items (unchanged)
- K3 equipment ETL deploy on Neon (still owed). Deferred form-feedback batch. M-7 multi-locale cluster ingestion; #8 locales→locations rename; BM-5 equipment-canon tail. Best-fit §14 craft-family escape hatch (only if the LLM over-substitutes).

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `Discipline_ID_Renumber_R6_Design_v1.md` (the old→new map + owed-Neon steps) 6. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **R6-scope** | Full R6 (both collapses + clean renumber) | Andy at gate | Over mtn-run-only/hold-kayak, collapse-no-renumber, hold-both/re-scope — chosen knowing the collapse flattens injury/stimulus/skill data the terrain axis never absorbed (the whitewater conditional retirement = accepted regression). |
| **R6-scheme** | Clean sequential D-001..D-029 | Andy at gate | Over minimal-safe in-place (~6 ids change) + collapses-only — chose the tidiest scheme knowing ~24 of 29 ids change meaning (max silent-mismap risk; mitigated by the authoritative map + collision-safe script + green suite + grep sweep). |
| **whitewater** | Retire the Layer 2A whitewater conditional | follows from collapse | D-010 Kayaking is one discipline now; the duration≥20h gate + `_WHITEWATER_DISCIPLINE_ID` special-casing can't survive the merge. Nav conditional (D-015) retained. |
| **workbook** | Committed openpyxl transform → v11 (not a silent binary rewrite) | architect | Reviewable text transform + my structural read-back; the unvalidatable per-sheet dedup is handed to Andy's owed ETL loop where it can be validated live. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| Authoritative old→new map exists | ✅ `Discipline_ID_Renumber_R6_Design_v1.md` §2 (29 rows, both collapses) |
| Renumber applied across code/SQL/tests | ✅ 551 rewrites / 37 files; grep-clean of suffix ids (live) |
| `discipline_display_names.py` collapsed to 29 + survivor labels | ✅ D-010 "Kayaking", D-024 "Mountain Running", `len==29` |
| Collapse data unioned (stimulus / body_parts / technique) | ✅ one UPDATE per survivor; body_parts baseline=29 + `<>29` check |
| Layer 2A whitewater conditional retired; nav retained | ✅ `_WHITEWATER_DISCIPLINE_ID`/`_AR_DURATION_THRESHOLD_HOURS` gone; compiles |
| Workbook → v11 (renumber + Discipline Library collapse) | ✅ `Sports_Framework_v11.xlsx` ×2; 29 disciplines, 0 suffix ids |
| ETL retargeted v10→v11 + `0A-v11.0` | ✅ `etl/layer0/run.py` + extractor docstrings + `test_v11_parsers.py` |
| Full suite green | ✅ 1630 passed / 16 skipped; etl/tests 139 passed |
| Neon re-extract demarcated as owed | ✅ design §7 + CARRY_FORWARD R6 + §6.1 here |
| CARRY_FORWARD R6 + Spec v4 R6 row flipped to SHIPPED | ✅ |

## 9. Files shipped this session

**Renumber (mechanical, 37):** all in-scope `.py` + live `.sql` (see §4). **Collapse + code (substantive):** `discipline_display_names.py`, `layer2a/builder.py`, `etl/sources/populate_stimulus_components.sql` (+ migrations copy), `etl/sources/migrate_disciplines_add_body_parts_at_risk_v1.sql`, `etl/sources/populate_discipline_technique_foci.sql`, `etl/sources/populate_substitute_covers.py` (+ aidstation-sources copy), `etl/layer0/run.py`, `etl/layer0/extractors/sports_framework.py`, `tests/test_layer2a.py`, `tests/test_discipline_display_names.py`, `tests/test_routes_race_events.py`. **NEW:** `Sports_Framework_v11.xlsx` (×2), `etl/sources/migrate_discipline_ids_R6.py`, `aidstation-sources/Discipline_ID_Renumber_R6_Design_v1.md`. **Renamed:** `etl/tests/test_v10_parsers.py` → `test_v11_parsers.py`. **Bookkeeping:** `CARRY_FORWARD.md`, `BestFitModality_Spec_v4.md`, `CURRENT_STATE.md`, this handoff.

## 10. Carry-forward updates

- **R6 SHIPPED — discipline ids are now clean sequential D-001..D-029; kayak + mountain-running collapsed.** The best-fit re-model + R6 are both complete.
- **Neon re-extract is the gating owed step** (§6.1) — code/SQL/workbook are internally consistent and ready; the live ETL + the pairing-count + per-sheet-dedup validation are Andy's (no DB in the build container).

## 11. Deploy addendum (same session — Neon re-extract completed)

The §6.1 "owed to Andy" Neon step was executed this session (Andy ran it against Neon; this agent drove the fixes). **Deploy complete + validated.**

- **Sequence run:** pulled PR #154 → `python -m etl.layer0.run --version-tag 1.3` (lands `0A-v11.0`, 29 disciplines) → 5 populate scripts → validate. Re-pin was a no-op: runtime auto-discovers the active version via `_q_current_etl_version_set` (orchestrator.py:757 = `MAX(etl_version) FROM layer0.sports WHERE superseded_at IS NULL`); `race_events.etl_version_set` is row provenance, not the Layer-0 pin.
- **Validations:** active disciplines = 29 ✅; no duplicate active discipline ids ✅; `discipline_pairing` 325 → 273 (−52, fully explained by the collapse: 18→16 matrix header ids + the dedup of double-counted survivor pairs; matches this agent's local v11-workbook extraction of 272 matrix + 1 b2b fallback) ✅.
- **3 latent bugs surfaced by the first clean re-extract — all fixed on PR #154:**
  1. `migrate_disciplines_add_body_parts_at_risk_v1.sql` verify block (4a–4f + the 29 UPDATEs) was version-naive (counted superseded rows → "expected 31, found 124"); scoped all to `superseded_at IS NULL` (commit `093fb74`).
  2. `extract_discipline_pairing_matrix` + `extract_discipline_substitutes` emitted collapse-duplicate keys (UniqueViolation) + self-pairs; deduped first-seen-wins + skip self-pairs, with regression tests (commits `3ab4c18`, `a86804d`).
  3. The "re-pin etl_version_set" instruction was wrong (no such deployed pin); design doc §7 corrected (commit `35132a6`).
- **One non-R6 Neon-data snag (logged, not a code bug):** `populate_terrain_gap_rules.sql` (0C family) tripped its `<> 16` verify with "found 17" — a `(TRN-013, NULL)` orphan from a prior terrain session, left because the populate scripts use `ON CONFLICT DO NOTHING` with no `DELETE`. Superseded the orphan by hand; the script then verified 16.
- **Two Cleanup follow-ons opened:** backlog **D-74** (give the standalone `populate_*.sql` scripts `DELETE`-by-version idempotency like `insert_versioned`) + **D-75** (`_q_current_etl_version_set` string-`MAX` sort breaks at a digit-width boundary).

**R6 is fully shipped and deployed. PR #154 merged.**

**End of handoff.**
