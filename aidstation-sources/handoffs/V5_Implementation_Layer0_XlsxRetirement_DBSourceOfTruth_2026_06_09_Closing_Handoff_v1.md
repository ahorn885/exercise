# V5 Implementation — Layer 0 xlsx retirement → DB as source of truth (spec + prune)

**Date:** 2026-06-09
**Branch:** `claude/xlsx-to-database-migration-2g2rdu` · **PR [#487](https://github.com/ahorn885/exercise/pull/487)** · **Epic [#488](https://github.com/ahorn885/exercise/issues/488)**

## 1. What this session was

Andy asked: "how do we stop relying on our legacy xlsx foundational doc and transition to the app's database as our source of truth?" Then directed: spec the change, prune the older xlsx versions, retire v10/v11, fix the ETL-tests CI gap, write this handoff, and merge.

## 2. Shipped (PR #487)

- **Design spec** — `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` (DRAFT, pending sign-off). Core finding: **the xlsx is already not a runtime dependency** — every serving path reads `layer0.*` Postgres (77 refs across 11 modules; zero `read_excel`/`openpyxl` reads in `app.py`/`routes/`/`layer*`; the `init_db.py:1633` hit is a comment). So this is an **authoring-loop flip**, not a serving change. The load-bearing work is porting the ETL validators (`sum_to_100`, `vocab_alignment`, `fk_checks`, `discipline_canon_check`, `modality_group_orphan`, …) to a DB-side `validate_layer0` gate — today they only run because the ETL re-runs. Phased plan + 3 open decisions in the doc.
- **Pruned every superseded workbook.** `etl/sources/` now holds exactly the two current authoritative sources — `Sports_Framework_v14.xlsx` + `AR_Exercise_Database_v19.xlsx` — plus `Vocabulary_Audit_v2.md`. Deleted: SF v6/v10/v11/v12/v13, AR v17, the `aidstation-sources/data/` dup folder, and `etl/sources/migrate_discipline_ids_R6.py` (the already-run one-off). All recoverable from git history.
- **Retired the v10/v11 pins (the deliberate pass).** `test_v11_parsers.py` → renamed `test_sports_framework_parsers.py`, repointed to v14 (fixture `v14_wb`); `test_discipline_canon.py` repointed to v14 (took `main`'s version on merge — 24 disciplines). Parser counts (89 substitutes / 3 gaps / 1 cross-sport) held against v14. Three `etl/layer0` docstrings naming v11 as "the source" de-dangled to "the Sports Framework workbook".
- **Closed the CI gap.** `ci.yml` ran `pytest tests/` only — `etl/tests/` (the Layer 0 parser + canon suite) had **zero CI coverage**. Now `pytest tests/ etl/tests/`. `psycopg2` is already present via `requirements.txt`; the ETL tests read the workbooks directly (no live DB).
- **Filed epic #488** ("Retire legacy xlsx foundational docs → DB as source of truth", `layer:0`/`area:etl`/`v2`) with the task checklist + open decisions A/B/C.

## 3. Mid-flight merge reconciliation (the one surprise)

`main` advanced **v13 → v14** while this branch was open (Vocabulary V1; canon 21 → 24 disciplines; `run.py` repointed; `emit_sql.py` made to derive the source name dynamically from `SPORTS_XLSX`). Merged `origin/main` in and resolved:
- `etl/layer0/emit_sql.py` — took `main`'s dynamic `SPORTS_XLSX.name` (strictly better than the hardcoded version this branch had).
- `etl/tests/test_discipline_canon.py` — took `main`'s v14 / 24-discipline version.
- Re-applied our intent on top: repointed the parser test to **v14** (not v13) and **also pruned v13** (now itself a superseded version — consistent with the "delete old versions" directive).

## 4. Stop-and-ask status

The spec is **DRAFT, not approved** — it trips triggers #3 (cross-layer / `etl_version_set`) + #5 (architectural alternatives). The prune/CI/test work is mechanical cleanup and shipped; **no implementation slice starts before Andy signs off on the spec + decisions A/B/C.**

## 5. Owed / next move

- **Decisions A/B/C** (spec §8): A admin UI (rec: defer) · B DB→xlsx export hedge (rec: phase 4) · C which validators go WARN→FAIL (rec: FK + canon + orphan FAIL, rest WARN).
- **Slice 1** — port the ETL validators → standalone `validate_layer0` + CI wire. The integrity gate; prerequisite for any DB-authored change. Tracked in #488.
- Then: `etl/migrations/layer0/` convention + first proof migration; phase-4 extractor/xlsx freeze.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. Then read the spec + #488 before touching Layer 0 authoring.

## 6. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Design spec exists | `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | `## 1. Purpose` + §10 CI note |
| Only v14 + v19 remain | `etl/sources/` | `ls etl/sources/*.xlsx` → 2 files |
| Parser test repointed | `etl/tests/test_sports_framework_parsers.py` | `V14_PATH` + fixture `v14_wb` |
| Canon test on v14 | `etl/tests/test_discipline_canon.py` | `Sports_Framework_v14.xlsx`; `== 24` |
| CI runs etl/tests | `.github/workflows/ci.yml` | `pytest tests/ etl/tests/` |
| emit_sql dynamic source | `etl/layer0/emit_sql.py` | `SPORTS_XLSX as _sports_xlsx` |
| Epic filed | GitHub | `#488` |

## 7. Summary

The DB is already the serving source of truth; the spec lays out flipping the *authoring* loop (validators-to-DB-gate first) and is pending approval. The xlsx cruft is gone — `etl/sources/` is down to the two live workbooks — `etl/tests/` is finally CI-gated, and the v13→v14 advance on `main` is reconciled. PR #487; epic #488.
