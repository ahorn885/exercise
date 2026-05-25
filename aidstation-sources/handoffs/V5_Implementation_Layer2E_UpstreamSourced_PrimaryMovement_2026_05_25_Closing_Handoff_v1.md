# Layer 2E — Upstream-Sourced Discipline Classification + `primary_movement` Column — Closing Handoff

**Session:** Started from a question about what references the Layer 2E "sport" category. Investigation found Layer 2E hand-maintained two `discipline_id`-keyed dicts (`_ENDURANCE_PROFILE`, `_DISCIPLINE_PROFILE_VOTE`) that **duplicated authoritative Layer 0 data it never read** and had drifted off the post-R6 taxonomy: `D-016` (now Swimming) labelled `"Strength"`, endurance label `"Technical"` instead of canonical `"Technical-dominant"`, a duplicate `D-010` key, and ~12 disciplines covered only by silent defaults. Andy ratified (three gates) the most thorough fix: source the classification from upstream `layer0.disciplines`.

**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_D74_D75_Cleanup_VersionSort_PopulateIdempotency_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/tender-thompson-yB6kN` → **PR #156 (draft)**
**Status:** Shipped to branch. Code + tests green (51 in touched suites; 1340 importable-suite, 10 pre-existing `flask`-not-installed failures unrelated). **Migration `migrate_disciplines_add_primary_movement_v1.sql` is owed-deploy on Neon — and unlike a routine populate-deploy it is a HARD prerequisite for the code (see §6.1).**

---

## 1. The finding (why this session happened)

`_resolve_sport_profile` / `_cho_band_position` / `_protein_band_position` in `layer2e/builder.py` looked up two module-level dicts keyed by `discipline_id`. Those dicts were authored against the pre-R6 placeholder taxonomy and never re-mapped after the D-001..D-029 renumber. Net effect: Swimming voted as "Strength", several disciplines mapped to the wrong sport, the endurance value used a non-canonical label, and a duplicate `D-010` key silently shadowed. Layer 2E read **none** of the Layer 0 classifications (`discipline_category`, `endurance_profile`) that already exist and are validated upstream.

## 2. Why a new `primary_movement` column (not just `discipline_category`)

The only per-discipline upstream classification with data is `discipline_category` — a **terrain** axis (`Foot / *`, `Water / *`, `Snow / *`, `Vertical/VK`, `Mixed / Technical`). The §5.4.3 CHO modifier needs the **movement** axis (running vs **swimming** vs **paddling** vs skiing): `Water / Ocean` (swim, ×0.6) and `Water / River` (paddle, ×0.9) share a terrain category but differ in fueling. The movement vocabulary (`ENUM_MOVEMENTS`) existed only per-**sport** (`layer0.sports.constituent_movements`), not per-discipline; `stimulus_components` is unpopulated; `sport_discipline_map` has neither. So terrain cannot faithfully source the vote — hence a new per-discipline `primary_movement` column.

## 3. Changes by layer

- **Layer 0** — `primary_movement TEXT` added to `layer0.disciplines` (`etl/layer0/schema.sql`); extractor carries the key as `None` from the sheet (`extract_disciplines`), and `etl/layer0/run.py`'s `disciplines_columns` includes it. Populated by new `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` — 29 idempotent UPDATEs grouped by movement family + a `DO $$` verification block (all active rows non-NULL and ∈ `ENUM_MOVEMENTS`). Follows the `body_parts_at_risk` / `stimulus_components` migration pattern.
- **Layer 2A** — `_load_disciplines` adds `LEFT JOIN layer0.disciplines dl … AND dl.etl_version = ?` (a 6th `version_0a` param) and selects `dl.discipline_category, dl.primary_movement`; both are passed onto `Layer2ADiscipline` via `row.get(...)`.
- **Layer 4** — `Layer2ADiscipline` gains `discipline_category: str | None = None` and `primary_movement: str | None = None`.
- **Layer 2E** — `_ENDURANCE_PROFILE` / `_DISCIPLINE_PROFILE_VOTE` / `_STRENGTH_DOMINANT_IDS` **deleted**. New `_endurance_profile(d)` derives the §5.3.3 band from `discipline_category` (prefix → `_CATEGORY_ENDURANCE`); `_movement_sport_profile(d)` derives the §5.4.3 vote from `primary_movement` (→ `_MOVEMENT_SPORT_PROFILE`); the protein band treats `primary_movement == 'climbing'` as strength-biased (`_STRENGTH_MOVEMENTS`). Missing values → `Mixed` / `multi_sport`; present-but-unrecognised values log a warning (module `logger`).

## 4. Mapping decisions pinned (ratified plan)

`primary_movement`: D-003 Hiking→`hiking`; **D-015 Orienteering→`running`** (locomotion; nav is a skill overlay); **D-018 Mountaineering→`climbing`** (→multi_sport bucket, Technical-dominant endurance); **D-020 Swimrun→`swimming`** (swim-limited fueling); **D-026 Laser Run / D-027 Obstacle Racing→`running`** (run-dominant); D-025 Fencing / D-029 Rifle Shooting→`other_skill`. Movement→bucket: hiking→running, skiing→skimo, climbing/navigation/other_skill→multi_sport.

## 5. Code / test results

- **Touched suites `tests/test_layer2a.py tests/test_layer2e.py`: 51 passed** (incl. new `test_discipline_category_and_primary_movement_plumb_through`; the running-dominant ×0.85 path now sourced from `primary_movement`).
- **Full importable suite: 1340 passed / 16 skipped.** 10 failures are all `ModuleNotFoundError: No module named 'flask'` — pre-existing env gaps (route tests), confirmed identical on the unmodified tree; unrelated to this change.
- **Sandbox:** `pip install pydantic pytest`, then `PYTHONPATH=. python -m pytest …`. Note: a direct `import layer2e` hits a **pre-existing** circular import (`layer2e.builder → layer4.context → layer4.orchestrator → layer2e.builder`) unless `layer4` is imported first; the normal `pytest tests/` run avoids it (alphabetically-earlier suites import `layer4` first). Run `test_layer2a` before `test_layer2e` if invoking them alone.

## 6. Next session pointers

### 6.1 Owed to Andy — RUN THE MIGRATION ON NEON **BEFORE** the code deploy
This is **not** a routine "owed-deploy." The Layer 2A query now `SELECT`s `dl.primary_movement`. If PR #156 merges (Vercel deploys) **before** `migrate_disciplines_add_primary_movement_v1.sql` runs on Neon, every Layer 2A invocation errors with *column `dl.primary_movement` does not exist*. Order: **run the `ALTER`/populate migration on Neon first (or atomically), then merge/deploy.** Until the migration runs, Layer 2E falls back to `multi_sport`/`Mixed` for all disciplines (`primary_movement` NULL) but only once the column exists.

### 6.2 Spec doc drift (left for Andy's call)
`aidstation-sources/Layer2E_Spec.md` §5.3.3 still reads "For v1: hard-coded by endurance_profile lookup" and §5.4.3 "Sport profile resolved from weighted discipline mix" — both now describe upstream-sourced derivation. Updating is a versioned-spec edit (Rule #12) — not done unilaterally.

### 6.3 Carried items
All R6 / D-74-D-76 carried items unchanged (per predecessor §6.3). New: the spec-narrative sweep should also cover §5.3.3/§5.4.3 (§6.2 above).

### 6.4 Operating notes — read order (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. this handoff 5. `Project_Backlog_v62.md` 6. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **direction** | Source classification from upstream (not patch local dicts) | Andy at gate | Single source of truth; ends the duplication/drift. |
| **mechanism** | Add per-discipline `primary_movement` to Layer 0 | Andy at gate | Terrain `discipline_category` can't express swim-vs-paddle; movement vocab was per-sport only. |
| **D-015 / D-018 / D-020 / D-026 / D-027** | running / climbing / swimming / running / running | Andy at gate | Locomotion-dominant resolution; flagged as lossy single-movement calls. |
| **migration pattern** | SQL `ALTER`+populate in `etl/sources/` (not edit the xlsx) | this agent | Mirrors `body_parts_at_risk` / `stimulus_components`; binary source-of-record untouched. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_ENDURANCE_PROFILE` / `_DISCIPLINE_PROFILE_VOTE` / `_STRENGTH_DOMINANT_IDS` removed | ✅ no refs (`grep`) |
| `_endurance_profile` / `_movement_sport_profile` derive from upstream fields + warn | ✅ `layer2e/builder.py` |
| `Layer2ADiscipline` carries the two new optional fields | ✅ `layer4/context.py` |
| Layer 2A query joins `layer0.disciplines` + 6th param + plumbs both fields | ✅ `layer2a/builder.py` (param assertion updated) |
| `primary_movement` in schema + extractor + run.py column list | ✅ |
| Migration: 29 rows, `ENUM_MOVEMENTS`-validated, `DO $$` verify | ✅ `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` |
| Touched suites green | ✅ 51 passed |
| Full importable suite green (10 pre-existing flask gaps) | ✅ 1340 passed |
| Migration run on Neon | ❌ owed — **hard prerequisite, see §6.1** |
| `CURRENT_STATE.md` pointer bumped | ❌ owed (large-file edit deferred; this handoff is the record) |

## 9. Files shipped this session

**Code:** `layer2e/builder.py`, `layer2a/builder.py`, `layer4/context.py`, `etl/layer0/schema.sql`, `etl/layer0/run.py`, `etl/layer0/extractors/sports_framework.py`. **SQL (owed-deploy, prerequisite):** `etl/sources/migrate_disciplines_add_primary_movement_v1.sql`. **Tests:** `tests/test_layer2e.py`, `tests/test_layer2a.py`. **Bookkeeping:** this handoff. (7 code files — over the soft 5-file ceiling; one cohesive cross-layer change.)

**End of handoff.**
