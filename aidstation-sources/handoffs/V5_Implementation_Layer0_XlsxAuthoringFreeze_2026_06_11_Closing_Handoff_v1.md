# V5 Implementation — Layer 0 §6.4 freeze: retire the xlsx authoring path (epic #488 complete)

**Date:** 2026-06-11
**Branch:** `claude/layer0-xlsx-authoring-freeze`

## 1. What this session was

The last open item of epic [#488](https://github.com/ahorn885/exercise/issues/488): the §6.4 freeze of the legacy xlsx → DB Layer 0 authoring toolchain, gated on 2–3 migrations through cleanly (cleared by `0001`+`0002`+`0003` earlier this day). Andy chose **Option 3** (full retirement) and directed execution after a keep-vs-retire classification. Investigating it produced the load-bearing finding: **no constants needed relocating** — every symbol the freeze set exposes is imported *only by tests*; the live equivalents stand on their own (the route keeps its own `RACE_INELIGIBLE_TERRAIN_IDS`; terrain/toggle/substitute data lives in the DB). So Option 3 collapsed to **archive the ETL + retire the ETL-guard tests**, no risky relocation refactor.

## 2. What shipped

**Archived → `etl/_frozen_xlsx_authoring/`** (with a `README.md` marker explaining the retirement + what stayed live):
- `extractors/` (`sports_framework.py`, `exercise_db.py`, `vocabulary.py`, `__init__.py`) — the spreadsheet parsers.
- `run.py` (the ETL runner) + `emit_sql.py` (the snapshot emitter).
- `sources/Sports_Framework_v14.xlsx` + `sources/AR_Exercise_Database_v19.xlsx` — the last authoring workbooks.
- The 6 ETL-only tests (`test_extractor_parsers`, `test_sports_framework_parsers`, `test_discipline_canon`, `test_vocabulary_md`, `test_run_versioning`, `test_equipment_token_coverage`) — they tested the parsers/canon against the workbooks. Frozen alongside the code they exercised (not collected by CI — `pytest tests/ etl/tests/` doesn't reach the frozen dir).

**Three main-suite tests resolved** (kept their live parts):
- `tests/test_onboarding_race_events.py` — `TestRaceIneligibleTerrainConsistency` was an ETL-vocab-vs-route cross-check; narrowed to assert the **live route set** == `{TRN-014,015,016}` (the ETL mirror is gone; the route keeps its own; terrain race-eligibility is also a `terrain_types.race_eligible` DB column now).
- `tests/test_layer2c_prep.py` — retired the parser classes (`TestGearToggleParser`, `TestParsedSubstitutesLoader`) + their imports/fixture; **kept `TestSchemaSubstrate`** (reads `schema.sql` + the archived migration + constructs `Layer2CPayload`).
- `etl/_frozen_xlsx_authoring/tests/test_bucket_c_terrain_vocab_audit.py` (was `tests/`) — **frozen whole** with the freeze: it is built end-to-end on `_TERRAIN_STRUCTURED_ROWS` (the ETL terrain source, consumed only by the now-frozen `run.py`). **Coverage note (owed/optional):** terrain-vocab integrity (19-row count, TRN ids, climbing split, water expansion, layer2b boundary) is no longer guarded; the clean rebuild is a DB-side `validate_layer0` terrain check — flagged, not built.

**Stayed live (untouched):** `etl/layer0/schema.sql`, `validate_layer0.py` + `validation/` + waivers, `export_xlsx.py` (the DB→xlsx hedge, #545), `db.py`, the canon/transform modules (`discipline_canon`/`sport_canon`/`vocabulary_transforms`/`sport_name_aliases` — imported by the gate), `etl/migrations/layer0/`, the genesis snapshot. The `layer0-gate` is the integrity net going forward; authoring is now SQL migrations only.

Design doc §6.4 + §9 marked DONE (epic complete); CLAUDE.md needed no change (no ETL-run references).

## 3. Verification

- **Full-suite collection clean:** `pytest tests/ etl/tests/ --co` → **2364 tests collected, no import errors** (confirms nothing live imported the freeze set; the dependency map held).
- Edited/remaining tests pass: `tests/test_layer2c_prep.py` + `tests/test_onboarding_race_events.py` + `etl/tests/` → **123 passed**.
- Gate + hedge import clean: `import etl.layer0.{validate_layer0,export_xlsx,db}` OK.
- The `layer0-gate` (schema + genesis + migrations + `validate_layer0`) is untouched by the freeze (verified green earlier this day on the 0002/0003 work; the freeze removed none of its inputs).
- No app code or CI workflow changed; `extractors/` dir removed (empty after the moves).

## 4. Owed / next move

1. **(Optional) Terrain-vocab integrity guard, DB-side.** The frozen `test_bucket_c_terrain_vocab_audit` was the only coverage of terrain-row integrity; if wanted, rebuild as a `validate_layer0` check over `layer0.terrain_types` (count / TRN-id pattern / climbing+water categories). Filed as a note here; not built.
2. **Epic #488 — close on merge** (PR body carries `Closes #488`).
3. **Carried (unchanged):** `0003` Neon re-apply optional; cold-plan post-deploy verify (slice 3b/#521); go-live blockers **#539** (tab-closed plan-gen crawl) + **#540** (terrain-infeasible locale routing) are the top of the 4-tier order now that the Layer 0 epic is done.

## 5. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| ETL toolchain frozen | `etl/_frozen_xlsx_authoring/` | `extractors/`, `run.py`, `emit_sql.py`, `sources/*.xlsx`, `tests/` + `README.md` marker present |
| Freeze set gone from live tree | `etl/layer0/` | no `extractors/`, `run.py`, `emit_sql.py`; gate + canon + `export_xlsx` remain |
| Gate untouched + imports clean | `etl/layer0/validate_layer0.py` | `import etl.layer0.validate_layer0` OK; `layer0-gate` inputs (schema/genesis/migrations) intact |
| Main-suite tests resolved | `tests/test_onboarding_race_events.py`, `tests/test_layer2c_prep.py` | `test_route_filter_is_the_three_training_only_terrains`; `TestSchemaSubstrate` kept, parser classes gone |
| No live import of the freeze set | full suite | `pytest tests/ etl/tests/ --co` → 2364 collected, 0 errors |
| Epic complete in the spec | `aidstation-sources/designs/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | §6 item 4 "DONE — frozen"; §9 `[x]` freeze "Epic #488 complete" |

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. **Epic #488 is complete** — Layer 0 is DB-authoritative, authored via `etl/migrations/layer0/`, gated by `validate_layer0`; the legacy xlsx toolchain is in `etl/_frozen_xlsx_authoring/` (do not revive). Next focus is the go-live blockers **#539 / #540**.

## 6. Stop-and-ask status

Trigger #6 (architecture/status promotion — retiring the ETL authoring path): surfaced the keep-vs-retire classification + the `etl/_frozen_xlsx_authoring/` location + the one coverage-loss judgment (terrain-vocab audit) and got Andy's explicit "execute" before moving anything. No LLM / HITL / cross-layer-contract surface; the gate + serving are untouched.

## 7. Summary

Closed epic #488: retired the legacy xlsx → DB Layer 0 authoring toolchain. The classification's key finding — every freeze-set symbol is test-only, with live equivalents standing alone — meant Option 3 needed **no constant relocation**, just archival + ETL-guard-test retirement. Moved `extractors/`, `run.py`, `emit_sql.py`, the two workbooks, and their 6 parser/canon tests to `etl/_frozen_xlsx_authoring/` (README-marked, CI-uncollected); narrowed the route-terrain cross-check to the live route set; kept `TestSchemaSubstrate`; froze the `_TERRAIN_STRUCTURED_ROWS` terrain-vocab audit whole (flagging the lone coverage loss as an optional DB-side rebuild). The gate (`schema.sql` + genesis + migrations + `validate_layer0`), the canon modules it imports, and the `export_xlsx` hedge are untouched; full suite collects clean (2364, 0 import errors) and the edited/remaining tests pass (123). Layer 0 is now DB-authoritative end-to-end — authored via SQL migrations, validated by the gate, with the spreadsheet path frozen as history.
