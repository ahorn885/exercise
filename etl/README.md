# Layer 0 ETL

Standalone CLI that lands platform-level reference data (sport rule sets,
exercise library, canonical vocabularies) into a `layer0` schema in
Postgres. Postgres-only — does not share code with the existing app.

## Layout

```
etl/
├── README.md                  ← this file
├── reports/                   ← run reports (markdown, gitignored)
├── sources/                   ← input files; do not modify
│   ├── Layer0_ETL_Spec_v2.md
│   ├── Sports_Framework_v6.xlsx
│   ├── AR_Exercise_Database_v17.xlsx
│   ├── Vocabulary_Audit_v2.md
│   └── Phase_Load_Allocation_Audit_Log.md
├── layer0/
│   ├── schema.sql             ← idempotent CREATE TABLEs
│   ├── db.py                  ← psycopg2 helpers (connect, versioned insert)
│   ├── run.py                 ← orchestrator (CLI entry point)
│   ├── vocabulary_transforms.py
│   ├── extractors/
│   │   ├── sports_framework.py
│   │   ├── exercise_db.py
│   │   └── vocabulary.py
│   └── validation/
│       ├── sum_to_100.py
│       ├── vocab_alignment.py
│       └── report.py
└── tests/                     ← pytest tests for transforms + parsers
```

## Prereqs

- Python 3.11+
- `pip install openpyxl psycopg2-binary` (already in `requirements.txt`)
- Pytest for the test suite (`pip install pytest`)
- Access to a Postgres instance (Neon for prod; any Postgres works locally)

## Environment variables

| Name           | Required | Purpose                                   |
|----------------|----------|-------------------------------------------|
| `DATABASE_URL` | yes      | Postgres connection string (e.g. `postgresql://user:pass@host:5432/db`) |

No other env vars are read. The ETL never touches the existing app's
`public` schema.

## Running

```bash
DATABASE_URL=postgresql://... python -m etl.layer0.run --version-tag 1.0
```

Sample output:

```
[layer0 ETL] Connecting to Neon...
[layer0 ETL] Phase 1 — Vocabularies
layer0.body_parts: inserted 50 rows
layer0.health_condition_categories: inserted 11 rows
layer0.equipment_items: inserted 121 rows
layer0.terrain_types: inserted 15 rows
layer0.sport_specific_gear_toggles: inserted 12 rows
[layer0 ETL] Phase 2 — Sports Framework
layer0.sports: inserted 38 rows
layer0.disciplines: inserted 32 rows
  [warn] sport_discipline_map: dropped 3 duplicate (sport, discipline_id) rows — see report
layer0.sport_discipline_map: inserted 68 rows
layer0.discipline_pairing: inserted 292 rows (289 matrix + 3 fallback)
layer0.phase_load_allocation: inserted 192 rows
layer0.team_formats: inserted 26 rows
layer0.cross_sport_properties: inserted 1 rows
[layer0 ETL] Phase 3 — Bridge + Exercise DB
layer0.sport_discipline_bridge: inserted 67 rows
layer0.exercises: inserted 245 rows
  [warn] sport_exercise_map: dropped 3 duplicate (exercise_id, sport_name) rows — see report
layer0.sport_exercise_map: inserted 1065 rows
[layer0 ETL] Validation
sum_to_100: 33 sports checked, 24 PASS, 9 WARN
vocab_alignment: 245 exercises checked, 217 PASS, 28 WARN; 36 sport names checked, 5 PASS, 31 WARN
[layer0 ETL] Report written to etl/reports/run-1.0-YYYYMMDD-HHMMSS.md
[layer0 ETL] Done.
```

## Versioning model

Each ETL run carries an `--version-tag`. The orchestrator turns it into
three independent version strings, one per source family:

| Source family | xlsx / md                       | Version string |
|---------------|---------------------------------|---------------|
| 0A            | `Sports_Framework_v6.xlsx`      | `0A-v1.0`     |
| 0B            | `AR_Exercise_Database_v17.xlsx` | `0B-v1.0`     |
| 0C            | `Vocabulary_Audit_v2.md`        | `0C-v1.0`     |

Every Layer 0 table carries `(etl_version, etl_run_at, superseded_at)`.
Queries always filter `WHERE superseded_at IS NULL` for current data.

### Re-running the same version is idempotent

```bash
# First run
python -m etl.layer0.run --version-tag 1.0   # inserts all rows

# Re-run with same version
python -m etl.layer0.run --version-tag 1.0   # deletes 1.0 rows, re-inserts
```

The orchestrator deletes rows of the matching `etl_version` before
inserting, so retrying a partial / interrupted run is safe.

### Releasing a new version supersedes the prior one

```bash
python -m etl.layer0.run --version-tag 1.1
```

After this:

- 1.0 rows have `superseded_at` set to the run timestamp
- 1.1 rows are current (`superseded_at IS NULL`)
- Supersede is **scoped per source family**: re-running only 0B (e.g. a
  new exercise database) does not supersede 0A or 0C

### Rolling back

To revert to a prior version:

```sql
-- Drop the new version's rows
DELETE FROM layer0.<table> WHERE etl_version = '0A-v1.1';

-- Un-supersede the prior version
UPDATE layer0.<table>
   SET superseded_at = NULL
 WHERE etl_version = '0A-v1.0';
```

Apply to every table whose source family was rolled back. No migration
needed — the schema is unchanged, only data versioning flips.

## Validation

Both validation passes are **informational only** — they never fail the
ETL. The report file documents exact mismatches.

### sum_to_100 (`etl/layer0/validation/sum_to_100.py`)

For each sport in `phase_load_allocation`, computes the adjusted stack:

- Rows whose `role` is `Conditional` or contains `(*Conditional)` → zeroed
- Among paddle disciplines (Packrafting, Kayaking, Canoeing, SUP, Rowing,
  Sea Kayak), only the maximum per-phase contribution is counted
  (interchangeable interpretation per the audit log's adjusted-stack
  pattern)
- The "Weekly Total Target" row is excluded from the sum

The HIGH band must reach ≥ 100% on every phase. Sports that fall short
are surfaced as WARN.

### vocab_alignment (`etl/layer0/validation/vocab_alignment.py`)

(a) Every `contraindicated_parts[]` entry on `layer0.exercises` is
checked against `layer0.body_parts.canonical_name`. The Vocab Audit §5
col-13 renames are applied at extract time, so warnings here are
typically genuine non-body-part filter flags (Cardiac, Cognitive, Saddle,
Goggle, Blister, Lungs, etc.) that the v2 query layer should route to
`health_condition_categories` instead.

(b) Every distinct `sport_name` in `layer0.sport_exercise_map` is checked
against `layer0.sport_discipline_bridge.exercise_db_sport`. Mismatches
resolve spec Open Item #5 — the exercise-DB sport vocabulary doesn't
fully overlap with the framework sport names by design (e.g. "Marathon"
in the exercise DB maps to multiple framework sports).

## Tests

```bash
python -m pytest etl/tests/ -v
```

Covers:
- `transform_equipment_string` rename + slash-decompose + rollup rules
- `transform_body_part_string` col-13 renames (Lumbar→Lower back, etc.)
- Sports framework regex parsers: pack weight, weeks, age-adjusted ramp,
  race time %, dot-list split, recovery modalities, YES/NO flags
- Exercise DB parsers: `EX### — Name` reference, `physical_proxies`,
  `equipment_substitutes` 🏠 prefix split

## Known divergences from the spec

The build surfaced a few places where the spec / source files don't fully
align. Each is documented in the run report; summary:

- `Vocabulary_Audit_v2.md` §1 says "Total: 41 canonical body parts" but
  the table contents enumerate 50. Source is the table; loaded as 50.
- Spec §4.12.2 says ~21 health condition categories; the audit's §2.2
  enum table has 11. Loaded as 11 (the audit is the source).
- `Sport × Discipline Map` (Sheet 3) has 3 rows with duplicate
  `(sport_name, discipline_id)` keys — one true dup (Triathlon D-002),
  two genuine sub-format splits (Long Distance / Endurance Cycling
  D-005 / D-006). The spec's UNIQUE constraint can't model the splits;
  ETL drops first-wins and surfaces in the report.
- `Sport-Exercise Map` (0B) has 3 rows with duplicate
  `(exercise_id, sport_name)` keys — accidental rephrasings during DB
  curation. Same first-wins treatment.
- Sheet 7 (Athlete Profile Data Points) is excluded per spec §2 (Layer 1
  territory).

## What's NOT built (per spec §7 / non-goals)

- The query layer (spec §5) — separate later build
- Any Flask integration — Layer 0 ETL is standalone
- A web/admin UI to trigger runs — CLI only
- Alembic / SQLAlchemy — direct psycopg2 + plain SQL
- SQLite parity — Postgres only (the v1 dual-backend pattern in
  `database.py` is being dropped at v2 cutover)
