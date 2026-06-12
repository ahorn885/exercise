# Layer 0

Platform-level reference data (sport rule sets, exercise library, canonical
vocabularies, terrain, equipment, …) lives in a `layer0` schema in Postgres
(Neon for prod). Postgres-only — does not share code with the existing app.

**The `layer0.*` DB tables are the source of truth** (epic
[#488](https://github.com/ahorn885/exercise/issues/488)). Edits are authored as
reviewed SQL migrations and validated by an integrity gate before they reach the
database. The legacy "edit a spreadsheet → re-run the ETL" authoring path has been
**retired** — see [_frozen_xlsx_authoring/](#frozen-legacy-xlsx-authoring) below.

## Layout

```
etl/
├── README.md                  ← this file
├── layer0/                    ← the live gate + serving substrate
│   ├── schema.sql             ← idempotent CREATE TABLEs (the substrate)
│   ├── validate_layer0.py     ← the integrity gate (CLI: python -m etl.layer0.validate_layer0)
│   ├── validation/            ← the gate's checks (sum_to_100, vocab_alignment,
│   │                            fk_checks, terrain_types, … )
│   ├── layer0_validation_waivers.json
│   ├── export_xlsx.py         ← read-only DB→xlsx bulk-review export (#545)
│   ├── db.py                  ← psycopg2 helpers (connect, versioned insert)
│   ├── discipline_canon.py / sport_canon.py / sport_name_aliases.py
│   └── vocabulary_transforms.py
├── migrations/
│   └── layer0/                ← THE AUTHORING LOOP — reviewed SQL edits + README
│       ├── 0001_*.sql … 0003_*.sql
│       └── README.md          ← how to write a Layer 0 migration
├── output/
│   └── layer0_etl_v1.6.7.sql  ← the frozen genesis snapshot (baseline for migrations)
├── tests/                     ← pytest tests for the gate + validators
├── reports/                   ← run reports (markdown, gitignored)
├── sources/                   ← legacy ETL scratch (specs, one-shot SQL); not an input anymore
└── _frozen_xlsx_authoring/    ← the retired spreadsheet ETL (history; not run, not in CI)
```

## Authoring Layer 0 data

Write a reviewed SQL migration under `etl/migrations/layer0/` and let the gate
validate it. The full edit flow, naming convention, and the
invalidation-not-overwrite versioning model are documented in
**[`etl/migrations/layer0/README.md`](migrations/layer0/README.md)**. The design
rationale is `aidstation-sources/designs/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md`
(epic #488).

In short:

```
1. write etl/migrations/layer0/NNNN_<slug>.sql
2. CI "Layer 0 integrity gate" loads schema + genesis snapshot, applies every
   migration in order, then runs validate_layer0 — a bad migration fails here
   BEFORE it reaches the database
3. review the .sql diff in the PR
4. on merge, Andy applies the migration in the Neon SQL editor
   (the container has no Neon egress, so the apply stays a hands-on step)
5. the app picks it up automatically (every serving query filters
   `WHERE superseded_at IS NULL`) — no restart, no redeploy
```

## Prereqs

- Python 3.11+
- `pip install psycopg2-binary` (already in `requirements.txt`); `openpyxl` too if you run the DB→xlsx export
- Pytest for the test suite (`pip install pytest`)
- Access to a Postgres instance (Neon for prod; any Postgres works locally)

## Environment variables

| Name           | Required | Purpose                                   |
|----------------|----------|-------------------------------------------|
| `DATABASE_URL` | yes      | Postgres connection string (e.g. `postgresql://user:pass@host:5432/db`) |

No other env vars are read. Layer 0 never touches the existing app's `public`
schema.

## Versioning model

Layer 0 rows are versioned by **invalidation, not overwrite**: every row carries
`(etl_version, etl_run_at, superseded_at)`; a row is retired by setting
`superseded_at` (it stays as history, leaves the active set) and a new value
arrives as a fresh `INSERT … superseded_at = NULL`. **Serving always reads the
active set** (`WHERE superseded_at IS NULL`); it does not match on `etl_version`.
The `etl_version` string survives only as the per-table cache-invalidation signal
(slice 3b). The two migration shapes (cache-neutral vs serving-relevant) and the
per-table digest are spelled out in `etl/migrations/layer0/README.md`.

## The gate (validation)

`python -m etl.layer0.validate_layer0` is the integrity backstop. The CI
`layer0-gate` job (`.github/workflows/ci.yml`) stands up a throwaway Postgres,
loads `etl/layer0/schema.sql` + the genesis snapshot, applies every migration in
`etl/migrations/layer0/` in order, then runs the gate — so a migration that
introduces a dangling FK, a canon violation, a sub-100 phase load, a malformed
terrain id, etc. fails CI before it can be applied to Neon. Disposition is owned
by `etl/layer0/validate_layer0.py` (decision C: every check FAIL, `sum_to_100`
the only waiver bucket — see `layer0_validation_waivers.json`).

The checks live in `etl/layer0/validation/` (`sum_to_100`, `vocab_alignment`,
`fk_checks`, `contraindicated_conditions`, `default_inclusion`,
`discipline_canon_check`, `modality_group_orphan`, `terrain_types`). Each emits
stable violation ids; the orchestrator filters waivers and exits non-zero on any
remaining violation.

## DB → xlsx bulk-review export

`python -m etl.layer0.export_xlsx` projects the active `layer0.*` tables into a
read-only workbook (one sheet per table, active rows only) for eyeballing all the
reference data at once. It is a **review convenience, not an authoring input** —
edits still arrive as migrations. Output defaults to
`etl/output/layer0_db_export.xlsx` (gitignored).

## Tests

```bash
python -m pytest etl/tests/ -v
```

Covers the gate orchestrator and each validator (including the DB-free
`check_*` helpers and the export serializer). The frozen parser/canon tests under
`_frozen_xlsx_authoring/tests/` are **not** collected.

## <a name="frozen-legacy-xlsx-authoring"></a>Frozen: legacy xlsx authoring

`etl/_frozen_xlsx_authoring/` holds the retired spreadsheet ETL — the extractors,
`run.py` (the `python -m etl.layer0.run` runner), `emit_sql.py`, and the last
authoring workbooks (`Sports_Framework_v14.xlsx`, `AR_Exercise_Database_v19.xlsx`).
Layer 0 reference data used to be authored in those spreadsheets and projected
into Postgres by that one-time ETL; epic #488 inverted it so the DB is the source
of truth. The frozen tree is **not run, not imported by anything live, and not
collected by CI** — kept only as history. Do **not** revive it; recovering the
workbooks from git history is the escape hatch if a wholesale re-curation is ever
needed. See `etl/_frozen_xlsx_authoring/README.md`.

## What's NOT here (per spec §7 / non-goals)

- A web/admin UI to author Layer 0 — SQL migrations only (admin UI deferred).
- Alembic / SQLAlchemy — direct psycopg2 + plain SQL.
- SQLite parity — Postgres only.
