# FROZEN — legacy xlsx → DB Layer 0 authoring toolchain (retired 2026-06-11)

This directory is an **archive**. The code and workbooks here are the retired
xlsx-authoring ETL for Layer 0 reference data. They are **not run, not imported
by anything live, and not collected by CI**. They are kept only as history.

## Why this was frozen

Layer 0 reference data (sports, exercises, vocabularies, terrain, …) used to be
**authored in spreadsheets** and projected into the `layer0.*` Postgres tables by
a one-time ETL:

```
edit Sports_Framework_v14.xlsx / AR_Exercise_Database_v19.xlsx / Vocabulary_Audit
  → python -m etl.layer0.run --version-tag X     (extract + canon-transform + validate)
  → emit_sql.py → etl/output/layer0_etl_vX.sql   → paste into Neon
```

Epic [#488](https://github.com/ahorn885/exercise/issues/488) inverted that: **the
`layer0.*` DB tables are now the source of truth.** Edits arrive as reviewed SQL
migrations under `etl/migrations/layer0/`, validated by the CI `layer0-gate`
(`etl/layer0/schema.sql` + the frozen genesis snapshot + the migrations +
`etl/layer0/validate_layer0.py`). With migrations `0001`+`0002`+`0003` through the
gate cleanly, the freeze gate (§6.4 of
`aidstation-sources/designs/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md`)
cleared, and this authoring path was retired.

## What's here

- `extractors/` — the regex/string parsers (`sports_framework.py`, `exercise_db.py`,
  `vocabulary.py`) that turned spreadsheet columns into canonical JSONB/FK shape.
- `run.py` — the ETL runner (`python -m etl.layer0.run`).
- `emit_sql.py` — the SQL snapshot emitter.
- `sources/Sports_Framework_v14.xlsx`, `sources/AR_Exercise_Database_v19.xlsx` — the
  last authoring workbooks.
- `tests/` — the parser/canon/versioning tests that exercised the above against the
  workbooks (frozen alongside the code they tested; their `etl.layer0.extractors`
  imports point at the pre-freeze location and are not expected to run).

## What stayed live (NOT here)

- `etl/layer0/schema.sql` — canonical schema (the substrate).
- `etl/layer0/validate_layer0.py` + `validation/` + `layer0_validation_waivers.json` — the integrity gate.
- `etl/layer0/export_xlsx.py` — the read-only DB→xlsx bulk-review hedge (#545).
- `etl/layer0/db.py`, `discipline_canon.py`, `sport_canon.py`, `vocabulary_transforms.py`, `sport_name_aliases.py` — still imported by the gate.
- `etl/migrations/layer0/` — the DB-native authoring loop.
- `etl/output/layer0_etl_v1.6.7.sql` — the frozen genesis snapshot.

## To author Layer 0 data now

Write a reviewed SQL migration under `etl/migrations/layer0/` (see its `README.md`);
the `layer0-gate` validates it; Andy applies it in the Neon SQL editor. Do **not**
revive this toolchain — recovering the workbooks/extractors from git history is the
escape hatch if a wholesale re-curation is ever needed.
