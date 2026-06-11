# ETL Parser Fix — AR Exercise DB Header Row Offset

**Date:** 2026-05-09
**Driver:** Layer 1 Node 2C design audit found a parser-bug residue row in `layer0.sport_exercise_map` (`sport_name = 'Sport'`). Root cause is a row-offset mismatch between the extractor and the actual xlsx structure.
**Pairs with:** `cleanup_sport_exercise_map_header_residue.sql` (one-shot DB cleanup; becomes a no-op after this fix lands and ETL re-runs).
**Scope:** AR_Exercise_Database_v19.xlsx ETL extractors only. Sports_Framework xlsx is correctly structured and needs no change.

---

## Bug

The xlsx structure for AR_Exercise_Database_v19.xlsx differs from what the current extractors assume.

### Actual structure (verified in v19)

Both ETL-source sheets in the workbook follow the same pattern:

| Sheet | Row 1 | Row 2 | Row 3+ |
|---|---|---|---|
| Exercise Master | Banner: `'ADVENTURE RACING — EXERCISE MASTER DATABASE'` (single cell, rest of row NULL) | Column headers: `Exercise ID, Exercise Name, Exercise Type, Movement Pattern, Primary Muscles, ...` | Data rows: `EX001, Back Squat (Barbell), Strength, Squat, ...` |
| Sport-Exercise Map | Banner: `'ADVENTURE RACING — SPORT-EXERCISE CROSS REFERENCE'` (single cell, rest of row NULL) | Column headers: `Exercise ID, Exercise Name, Exercise Type, Sport, Sport Relevance Note, Priority` | Data rows: `EX001, Back Squat (Barbell), Strength, Trail Running, ...` |

Sport Summary and Legend are non-tabular and are not ETL inputs — leave their handling alone.

### Current extractor behavior (what's wrong)

The extractor treats Row 1 as headers and Row 2 as the first data row. Two consequences:

1. **Sport-Exercise Map:** Row 2 leaks through as data. The cell under the "Sport" column header is the literal string `'Sport'`, producing a junk row with `sport_name = 'Sport'` (and `exercise_id = 'Exercise ID'`, etc.). This is the row that surfaced in the Node 2C audit.

2. **Exercise Master:** Row 2 also leaks through, producing a junk row with `exercise_id = 'Exercise ID'`. This row has been silently dropped downstream because the EX-prefix format validator on `exercise_id` rejects it. **The data is right by accident.** Any future change that loosens the EX-prefix validator (or adds a non-EX-prefixed exercise) would re-introduce the same bug.

The reliance on a downstream validator to filter parser garbage is the structural problem, not just the specific Sport-Exercise Map symptom.

---

## Required change

Update both AR Exercise DB extractors to:

- **Skip Row 1** (banner) entirely.
- **Use Row 2** as the header row.
- **Read data starting at Row 3.**

Apply uniformly to both sheets (Exercise Master, Sport-Exercise Map). Do not rely on type validators to silently drop the header-row leakage; fix the offset structurally.

### If using openpyxl directly

Look for code like:

```python
ws = wb['Sport-Exercise Map']
headers = [c.value for c in ws[1]]                                   # WRONG: row 1 is banner
for row in ws.iter_rows(min_row=2, values_only=True):                 # WRONG: row 2 is headers
    ...
```

Change to:

```python
ws = wb['Sport-Exercise Map']
headers = [c.value for c in ws[2]]                                   # row 2 is headers
for row in ws.iter_rows(min_row=3, values_only=True):                 # data starts row 3
    ...
```

Same edit pattern for Exercise Master.

### If using pandas.read_excel

Look for code like:

```python
df = pd.read_excel(path, sheet_name='Sport-Exercise Map')              # WRONG: defaults to header=0
```

Change to:

```python
df = pd.read_excel(path, sheet_name='Sport-Exercise Map', header=1)    # header is the second row (zero-indexed)
```

Same edit for Exercise Master sheet.

### If extractor uses a config file

Whatever config drives the row-offset (e.g., `header_row`, `skip_rows`, `start_row`), set it explicitly per sheet:

```yaml
sources:
  ar_exercise_database:
    file: AR_Exercise_Database_v19.xlsx
    sheets:
      Exercise Master:
        header_row: 2          # 1-indexed; was implicitly 1
        first_data_row: 3
      Sport-Exercise Map:
        header_row: 2
        first_data_row: 3
```

Use whatever convention the codebase uses (1-indexed or 0-indexed); the key fact is that headers are on the second row, data on the third.

---

## Verification

After the change, before re-running the full ETL:

1. **Smoke check the extractor in isolation** against v19:
   ```python
   # Expected post-fix:
   #   Exercise Master: ~211 data rows, all exercise_id values match /^EX\d+$/
   #   Sport-Exercise Map: ~1068 data rows, all exercise_id values match /^EX\d+$/,
   #     sport_name distinct values = 36 (after Sport placeholder cleanup) or 37
   #     (if cleanup hasn't run yet — and 'Sport' should NOT be among them post-fix)
   ```

2. **Confirm no header-row leakage:**
   ```python
   # Both extracted DataFrames should have zero rows where exercise_id == 'Exercise ID'
   assert (df_exercise_master['exercise_id'] == 'Exercise ID').sum() == 0
   assert (df_sport_exercise_map['exercise_id'] == 'Exercise ID').sum() == 0
   assert (df_sport_exercise_map['sport_name'] == 'Sport').sum() == 0
   ```

3. **Run the full ETL re-load** with `etl_version` bumped (whatever the next 0B revision is — suggest `0B-v19.r2` or per local convention).

4. **Validate against `cleanup_sport_exercise_map_header_residue.sql`** post-load:
   - Run the cleanup script. Expected: `RAISE NOTICE: 0 rows removed`. The cleanup is now a no-op because the parser fix prevents the junk row from appearing.

---

## Test row counts (expected post-fix)

| Table | Expected count | Compared to current |
|---|---|---|
| `layer0.exercises` | 211 (active rows from v19) | Same — junk row was already filtered by EX-prefix validator |
| `layer0.sport_exercise_map` | 1067 (active rows from v19) | One row less than current (1068 → 1067 after Sport placeholder is filtered at extract time, not at cleanup time) |

Note the Sport-Exercise Map count goes down by exactly 1 — the difference between current state (with junk row) and post-fix state (without). If the count drops by more than 1, the parser fix is also affecting legitimate data and needs review.

---

## Defensive guidance for future xlsx ingests

The AR Exercise DB convention is: title banner on row 1, headers on row 2, data on row 3+. This is one acceptable convention, but it's worth pinning down across all source workbooks:

- **Sports Framework v10:** headers on row 1, data on row 2. Extractors should use `header_row = 1` for these sheets.
- **AR Exercise Database v19:** banner on row 1, headers on row 2. Extractors should use `header_row = 2`.

Recommend an explicit per-sheet `header_row` config rather than a workbook-wide default. New source files in the future may follow either convention; explicit config eliminates the ambiguity that produced this bug.

Also recommend adding to the post-ETL validators a check that's specific to this class of bug:

```python
def validate_no_header_leakage(df, schema):
    """For each text column in schema, assert no value equals the column name itself
    (which would indicate a header row leaked through as data)."""
    for col in df.columns:
        if df.dtypes[col] == 'object':
            assert not (df[col] == col).any(), (
                f"Header leakage: column {col!r} has a row containing the literal "
                f"column name as its value. Likely cause: header row offset mismatch."
            )
```

Run this against every extracted DataFrame before insert. Cheap, catches the specific failure mode generically, and would have caught this bug at ETL time.

---

## Status checklist for the over-there session

- [ ] Locate the Exercise Master extractor and update header offset
- [ ] Locate the Sport-Exercise Map extractor and update header offset
- [ ] (Optional but recommended) Add the `validate_no_header_leakage` validator
- [ ] (Optional but recommended) Convert hardcoded offsets to explicit per-sheet config
- [ ] Smoke test extraction in isolation against v19
- [ ] Run full ETL re-load
- [ ] Verify cleanup_sport_exercise_map_header_residue.sql is now a no-op
- [ ] Report row counts back to the design session for confirmation
