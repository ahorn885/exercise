# V5 Implementation — Data-Pipeline Campaign, Phase 4: #229 + #233 — Nutrition/Fueling Constants → Layer 0 — Closing Handoff (2026-06-30)

**Branch:** `claude/data-pipeline-phase-3-migration-ku6mjh`
**Commit:** `ecdd2a6` (squashed to `54e29c7` on main via PR #1080)
**PR:** [#1080](https://github.com/ahorn885/exercise/pull/1080) — **MERGED** (squash, 2026-06-30)
**Migration applied:** `0036` applied to prod Neon via `layer0-apply` GitHub Action (Andy, 2026-06-30)
**Campaign kickoff:** `handoffs/DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`
**Issues closed:** [#229](https://github.com/ahorn885/exercise/issues/229), [#233](https://github.com/ahorn885/exercise/issues/233)

---

## 1. What shipped

### (a) Migration `0036_nutrition_fueling_tables.sql`

Four new family-0A Layer 0 tables, all seeded verbatim from the hardcoded constants in `layer2e/builder.py`. Behavior-preserving at deploy time — no output changes.

| Table | Rows | Seeds from |
|---|---|---|
| `layer0.sport_met_values` | 16 (4 phases × 4 tier indices) | `_MULTIPLIER_BANDS` |
| `layer0.race_fueling_bands` | 5 (tier_short → tier_extended_expedition) | `_FUELING_BANDS` |
| `layer0.sport_profile_cho_mod` | 7 (running/cycling/swimming/paddling/multi_sport/skimo/default) | `_SPORT_PROFILE_CHO_MOD` |
| `layer0.dietary_pattern_flags` | 4 (3 Vegan flags + 1 Low-FODMAP) | `_dietary_pattern_adjustments()` |

All tables: `UNIQUE (key_col(s), etl_version)` + `ON CONFLICT DO NOTHING` (idempotent). `etl_version = '0A-v1.0'`, `etl_run_at = '2026-06-30 00:00:00+00'`.

The `dietary_pattern_flags` protein column encoding: `protein_after_hr_threshold INT`, `protein_g_per_hr_flat NUMERIC`, `protein_g_initial NUMERIC` — reconstructed into the `(threshold, flat, initial)` tuple in the loader.

### (b) Four soft-fail loaders — `layer2e/builder.py`

Added `_load_all_sport_met_values`, `_load_all_race_fueling_bands`, `_load_all_sport_profile_cho_mods`, `_load_all_dietary_pattern_rules` — each wraps the DB query in `try/except Exception`, returning `None` on any fault. Pre-migration window: table absent → exception → `None` → caller falls back to hardcoded dict. Post-migration: tables present → live data.

All four loaders fire once at the top of `q_layer2e_nutrition_baseline_payload()` and pass through to the inner helpers:
- `_compute_activity_multiplier(db, sport, phase, smet_bands=smet_bands)`
- `_build_race_day_fueling(..., fueling_table=fueling_table, cho_mod_table=cho_mod_table)`
- `_sport_modifier(..., cho_mod_table=cho_mod_table)`
- `_dietary_pattern_adjustments(lifestyle, dpf_rules=dpf_rules)`

### (c) Orchestrator registration — `layer4/orchestrator.py`

Added 4 entries to `_LAYER0_TABLE_FAMILY` under family `"0A"`:
```python
"sport_met_values": "0A",
"race_fueling_bands": "0A",
"sport_profile_cho_mod": "0A",
"dietary_pattern_flags": "0A",
```
The 0A digest now advances when these tables change → plan-gen caches correctly invalidate.

### (d) Gate check `run_sport_met_values` — check #14

`etl/layer0/validation/sport_met_values.py`: verifies all 16 phase×tier rows are present in `layer0.sport_met_values WHERE superseded_at IS NULL`. A missing row fails the gate (fix-not-waive).

Registered in `etl/layer0/validate_layer0.py` as check #14 (CHECKS tuple now 14 entries). Extractor `_v_sport_met_values` maps `{"id": "Phase/tier_N", "detail": "..."}` → `Violation`.

### (e) Test fixes — `tests/test_layer2e.py`

**Root cause fixed:** the 4 new loaders fire at the START of `q_layer2e_nutrition_baseline_payload()` — before the 4 PLA SELECTs. `_FakeConn`'s FIFO response queue was consuming PLA rows for nutrition queries → PLA got `None` → phase-default multiplier (1.75) instead of table value (1.90 for Build).

**Fix:** added `_NUTRITION_TABLES` frozenset + `_nutrition_table_rows: dict[str, list]` to `_FakeConn`. `execute()` now checks if any nutrition table name appears in the SQL; if so, returns rows from `_nutrition_table_rows` (default `[]` → soft-fail fallback) without consuming from the FIFO queue.

**New `queue_nutrition_table(table_name, rows)` helper** for parity tests.

**3 parity tests added** (`TestNutritionTableParity`): `test_smet_table_multiplier_matches_hardcoded`, `test_fueling_table_output_matches_hardcoded`, `test_dpf_table_vegan_flags_match_hardcoded` — each confirms that with table rows matching the hardcoded constants, output is byte-for-byte identical to the no-table path.

---

## 2. Verification

- **`pytest tests/ etl/tests/ -q`** → **4019 passed, 30 skipped** (pre-existing warnings only)
- **`etl/tests/test_validate_layer0.py`** → 17 passed (incl. `test_sport_met_values_missing_row_fails_the_gate`, `test_registry_has_all_logical_checks` count=14)
- **CI on PR #1080** → Python unit suite ✅, Layer 0 integrity gate ✅, JS harness ✅ — all green
- **Migration applied to prod** via `layer0-apply` — run `28469893926`, status: `completed / success`
- No `race_fueling_bands` / `sport_profile_cho_mod` / `dietary_pattern_flags` gate checks (those tables have no missing-row invariant beyond the seed; the soft-fail fallback handles any temporary gap)

---

## 3. Owed after merge

Nothing. Migration applied. Issues closed.

---

## 4. NEXT — Phase 5: #240 (THIS IS THE NEXT STEP — CONTINUE HERE)

**Issue [#240](https://github.com/ahorn885/exercise/issues/240):** promote the hardcoded injury-flag categories into `layer0.injury_flag_categories`. Per the kickoff handoff's §"Remaining work":
- New table `layer0.injury_flag_categories` (family 0A)
- Seed with the injury flag category constants from `layer2d/builder.py` (or wherever they live)
- Add a soft-fail loader + fallback to hardcoded
- Register in `_LAYER0_TABLE_FAMILY["0A"]`
- Add a gate check if there's a completeness invariant
- **Next migration = `0037`**
- Parity tests

Phase 6 after: close epics #261 / #228.

---

## 5. Bookkeeping (Rule #10)

### §5 anchor table

| Claim | File | Anchor |
|---|---|---|
| Migration 0036 present | `etl/migrations/layer0/0036_nutrition_fueling_tables.sql` | exists; 4 `CREATE TABLE IF NOT EXISTS`; `ON CONFLICT … DO NOTHING` |
| 4 loaders in builder | `layer2e/builder.py` | `grep "_load_all_sport_met_values\|_load_all_race_fueling\|_load_all_sport_profile\|_load_all_dietary" layer2e/builder.py` → 4 hits |
| 4 tables in orchestrator | `layer4/orchestrator.py` | `grep "sport_met_values\|race_fueling_bands\|sport_profile_cho_mod\|dietary_pattern_flags" layer4/orchestrator.py` → ≥4 |
| Gate check registered | `etl/layer0/validate_layer0.py` | `grep "sport_met_values" etl/layer0/validate_layer0.py` → 3 hits (import + extractor + CHECKS) |
| Gate check impl | `etl/layer0/validation/sport_met_values.py` | exists |
| CHECKS count = 14 | `etl/tests/test_validate_layer0.py` | `assert len(v.CHECKS) == 14` |
| FakeConn fix | `tests/test_layer2e.py` | `grep "_NUTRITION_TABLES" tests/test_layer2e.py` → frozenset present |
| Suite green | `tests/` + `etl/tests/` | `python3 -m pytest tests/ etl/tests/ -q` → 4019 passed / 30 skipped |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (data-pipeline campaign entry)
4. This handoff + the campaign kickoff (`DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`)
5. `./scripts/verify-handoff.sh` — automated anchor sweep
