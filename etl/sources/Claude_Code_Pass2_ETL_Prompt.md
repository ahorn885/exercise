# Claude Code — ETL Re-run After Pass 2 Equipment Cleanup

## Context

The exercise database source has been updated from v17 → v19 by two cleanup passes that normalized the Equipment column. The ETL pipeline was paused mid-run (after vocab transforms, before full population) to allow this cleanup. This session resumes that run.

**Key change:** `etl/sources/AR_Exercise_Database_v17.xlsx` is replaced by `etl/sources/AR_Exercise_Database_v19.xlsx`. The v19 file has:
- 211 exercises (down from 245 — 34 exercises deleted)
- 105 unique equipment tokens (down from ~245)
- All equipment tokens normalized to canonical vocabulary

**Do not modify any schema.** Schema is locked at Layer0_ETL_Spec_v3.md.

---

## Step 1 — Run the K2 SQL patch

Run `scripts/populate_equipment_items_K2_additions.sql` against the database.

```bash
psql $DATABASE_URL -f scripts/populate_equipment_items_K2_additions.sql
```

Or for SQLite:
```bash
sqlite3 instance/training.db < scripts/populate_equipment_items_K2_additions.sql
```

**Expected output:** `NOTICE: K2 verify OK — all 19 required entries present in equipment_items`

If the verify block raises an exception, do not proceed. Report which entries are missing.

---

## Step 2 — Update source path

In `etl/run.py` (or `etl/config.py` — wherever the source xlsx path is pinned), update the exercise database filename:

```python
# Before
EXERCISE_DB_PATH = "etl/sources/AR_Exercise_Database_v17.xlsx"
# After
EXERCISE_DB_PATH = "etl/sources/AR_Exercise_Database_v19.xlsx"
```

Also update the `etl_version` tag for exercise DB rows from `0B-v17.*` to `0B-v19.*` so the version lineage is correct.

Search for any other hardcoded references to `v17` in the ETL codebase and update them.

---

## Step 3 — Run the full ETL

```bash
python etl/run.py
```

The ETL run should:
- Read `Sports_Framework_v10.xlsx` (0A source — unchanged)
- Read `AR_Exercise_Database_v19.xlsx` (0B source — updated)
- Apply `vocabulary_transforms.py` (J patch already applied — 133 tests passing)
- Populate all Layer 0 tables
- Set `superseded_at` on prior version rows
- Write a report to `etl/reports/`

---

## Step 4 — Run populate_substitutes_structured.py

```bash
python scripts/populate_substitutes_structured.py
```

This script has a runtime canonical vocab check. If it errors on unknown equipment tokens, the token is not in `layer0.equipment_items`. Fix by adding it to K2 SQL and re-running Step 1, then retry.

---

## Step 5 — Triage the ETL report

Walk through these checks in order. Report results for each.

### Check 1 — Run completed cleanly?
- ETL exit code 0
- Report file written
- All phases logged without errors

### Check 2 — Row counts

| Table | Expected | Flag if |
|---|---|---|
| exercises | **211** | Any other number — deletion cascade didn't apply |
| sport_exercise_map | **1008** | Any other number — map not updated |
| sports | 38 | Wrong: source path or sheet issue |
| equipment_items | ≥ prior count + 19 | Less than expected: K2 partial |
| disciplines | prior count (unchanged) | |
| sport_discipline_map | ~74 | |
| phase_load_allocation | ~178 | |

**Note:** exercises = 211 and sport_exercise_map = 1008 are the key new expectations. Prior run expected 245 / 1068. If you see those old numbers, the ETL is still reading v17 — check Step 2.

### Check 3 — Validators

| Validator | Expected |
|---|---|
| `vocab_alignment` | 0 WARN — all equipment tokens in v19 are now canonical |
| `sum_to_100` | 33 PASS, 0 WARN |
| `validate_substitution_fks` | 0 ERROR |
| `validate_contraindicated_conditions` | 0 WARN |
| `validate_default_inclusion` | 0 ERROR |

If `vocab_alignment` WARNs on any equipment token:
1. Check if the token appears in v19 (it shouldn't if cleanup was applied correctly)
2. If it does, it's a new token not in the canonical list — add to K2 SQL and re-run

### Check 4 — populate_substitutes_structured.py result

Report:
- Exit code
- Number of substitutes inserted
- Any vocab validation errors (token not found in equipment_items)

### Check 5 — Spot-check specific exercises

Verify these exercises have the correct equipment in the DB:

| Exercise ID | Expected Equipment |
|---|---|
| EX020 | NULL (empty) |
| EX056 | NULL (empty) |
| EX073 | Road bike, Mountain bike, Bike trainer, TT Bike, Gravel bike |
| EX104 | Rice bucket |
| EX114 | Climbing Wall |
| EX148 | Mountaineering kit |
| EX216 | Weighted vest |

---

## Step 6 — Report back

Paste the report with results for each check. Format as:

```
CHECK 1 — PASS/FAIL
CHECK 2 — PASS/FAIL (table: expected X, got Y)
CHECK 3 — PASS/FAIL (any WARN/ERROR details)
CHECK 4 — PASS/FAIL (substitutes inserted: N)
CHECK 5 — PASS/FAIL (any mismatches)
```

If all checks pass, ETL is done and Layer 0 is canonical on v19.

---

## What NOT to do

- Do not modify `Sports_Framework_v10.xlsx` — that source is unchanged and correct
- Do not modify the schema — it is locked at ETL Spec v3
- Do not delete and re-create Layer 0 tables — use the versioning pattern (set `superseded_at`, insert new rows)
- Do not run `pass2_cleanup.py` — that script has already been applied to produce v19; running it again would be a no-op but is unnecessary
