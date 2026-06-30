# Data-Pipeline Campaign — Phase 1–2 Done, Phase 3–6 Kickoff

**Date:** 2026-06-30
**Branch:** `claude/data-pipeline-issues-plan-ml47g4` → merged via PR
[#1069](https://github.com/ahorn885/exercise/pull/1069)
**Origin:** "Look at all open data-pipeline issues and build a plan to get them
done once and for all." 9 open `data-pipeline` issues, planned as 6 phases.

This handoff lets a fresh session resume the campaign. It is self-contained —
the working plan also lives at `~/.claude/plans/look-at-all-of-witty-falcon.md`
(local to the originating session; not in the repo).

---

## The 9 issues

| # | Title (short) | Phase | Status |
|---|---|---|---|
| #285 | Sync `DATABASE.md` to real schema | 1 | ✅ DONE (PR #1069) |
| #747 | Harden `init_db.py` seeds + splitter lint | 1 | ✅ DONE (PR #1069) |
| #269 | Retire `phase_load_allocation` aggregator workaround | 2 | ⚠️ PARTIAL (PR #1069) — see follow-up |
| #340 | Off-trail / trackless terrain vocab | 3 | ⏸ PENDING (decision made) |
| #229 | Move race-fueling & diet rules → Layer 0 tables | 4 | ⏸ PENDING |
| #233 | Add `sport_mets_table` (MET multiplier) | 4 | ⏸ PENDING |
| #240 | Structure free-text injury flags → Layer 0 | 5 | ⏸ PENDING (decision made) |
| #261 | EPIC: Layer 0 reference-data & spec reconciliation | 6 | ⏸ close-out (only open child was #269) |
| #228 | EPIC: upstream plan-gen pipeline | 6 | ⏸ tracking (open child #237 is out-of-scope `layer:4`) |

---

## What shipped in PR #1069 (Phases 1–2)

- **#285** — `DATABASE.md` lifecycle example said outcome is
  `PROGRESS / REPEAT / FAIL`; corrected to the literal stored strings
  `'PROGRESS ↑'` / `'REPEAT →'` / `'REDUCE ↓'` (or `NULL` bootstrap). `admin_audit`,
  `api_tokens`, NLP-bypass sections re-verified as already accurate.
- **#747** — In `init_db.py:init_postgres()`, each post-migration seed
  (`provider_value_map`, `evidence_sources`, the `equipment_items` +
  `purchase_recommendations` trio) is now wrapped in its own
  try/commit/except-rollback + Rule #15 log, mirroring the migration loop so one
  failing seed can't silently abort the tail of init. Added a lint in
  `tests/test_init_db_schema.py` forbidding a `;` inside any `PG_SCHEMA` line
  comment (the #681 §4 root cause).
- **#269** — Migration
  `etl/migrations/layer0/0034_supersede_phase_load_allocation_aggregators.sql`
  supersedes the **31 still-active** `WEEKLY TOTAL TARGET` aggregator rows
  (cache-neutral; they're never served). New gate check
  `etl/layer0/validation/phase_load_allocation_aggregators.py` (registered in
  `etl/layer0/validate_layer0.py`, +unit test in
  `etl/tests/test_validate_layer0.py`) fails the gate if any aggregator row is
  active again. The D-05 filter in `layer2a/builder.py` was **kept** (see below).

Verified: full pytest suites green; `#269` proven end-to-end against a throwaway
Postgres + the committed baseline (31 violations → `0034` → `UPDATE 31` → gate
PASS; idempotent re-run `UPDATE 0`). CI on #1069 fully green.

---

## ‼️ IMMEDIATE FOLLOW-UP (do first)

1. **Apply migration `0034` in the Neon SQL editor.** The container has no Neon
   egress, so this is a hands-on step (per `etl/migrations/layer0/README.md`).
   Until applied, the nightly `layer0-validate-live` workflow will FAIL on the 31
   active aggregator rows — that's the intended prompt.
2. **After `0034` is live and `layer0-validate-live` is green**, finish #269:
   delete the D-05 filter (`AND pla.discipline_name NOT LIKE '%%WEEKLY TOTAL%%'`
   in `layer2a/builder.py` `_load_disciplines`) and the aggregator exemption in
   `etl/layer0/validation/default_inclusion.py` (lines ~28–32). Update the
   asserting tests in `tests/test_layer2a.py` (the `%%WEEKLY TOTAL%%` checks) and
   the spec notes (`Layer2A_Spec.md` §5.2, `Control_Spec_v8.md` §8.2). The new
   gate check makes this safe. **Do not remove the filter before `0034` is live**
   — 31 aggregator rows would leak into Layer 2A's discipline load.

---

## Locked design decisions (Andy, 2026-06-30)

- **Cadence:** PAUSE after Phases 1–2. Resume Phase 3+ only once #1069 is merged
  AND `0034` is applied to prod.
- **#340:** Add `TRN-021` "Off-Trail / Trackless" (after confirming no existing
  terrain covers the trackless stimulus). Attach to Trail Running (D-001),
  Trekking (D-003), Mountain Running (D-024), Mountaineering (D-018).
- **#240:** Use a **separate `layer0.injury_flag_categories` table** keyed by
  exercise (cardiac / cognitive / skin / recovery), NOT columns on
  `layer0.exercises`.

---

## How Layer 0 changes ship (read before Phases 3–5)

Layer 0 is DB-native (`layer0.*` on Neon), edited via **versioned SQL
migrations** — full recipe in `etl/migrations/layer0/README.md`:

- File: `etl/migrations/layer0/NNNN_<slug>.sql` (next is `0035`). Wrap in
  `BEGIN; … COMMIT;`, make idempotent.
- Rows are versioned by **invalidation, not overwrite**: `etl_version`
  (`0A`/`0B`/`0C` family prefix), `etl_run_at`, `superseded_at`. Serving reads
  `WHERE superseded_at IS NULL`. *Cache-neutral* edit (no version bump) when
  output is unchanged; *serving-relevant* edit (supersede + re-insert at bumped
  version) when it changes plan-gen output.
- A **new** versioned table must be added to `_LAYER0_TABLE_FAMILY` in
  `layer4/orchestrator.py` (~line 2214), family `0A`/`0B`/`0C` — or to
  `_FAMILY_MAP_EXCEPTIONS` if it sits outside that cone; the
  `TestLayer0TableFamilyMap` guard in `tests/test_layer4_orchestrator.py`
  enforces this.
- **CI** `layer0-gate` (`.github/workflows/ci.yml`) loads the genesis baseline
  `etl/output/layer0_etl_v1.10.1.sql`, applies every `etl/migrations/layer0/*`,
  and runs `python -m etl.layer0.validate_layer0` — fully verifiable here. The
  prod apply itself is manual (Andy, Neon).
- **Layer 0 reader pattern** (replicate when moving code → tables; exemplar
  `_load_phase_weekly_hours` in `layer2e/builder.py`):
  `db.execute("SELECT … FROM layer0.<t> WHERE … AND superseded_at IS NULL", (…))`,
  soft-fail to `None`/`[]`.
- **Gate-check pattern**: add `etl/layer0/validation/<check>.py` returning
  `{"errors":[{"id","detail"}], …}`; import + add a `Check(...)` to `CHECKS` in
  `validate_layer0.py`; add the clean-result key + count bump + a failure test in
  `etl/tests/test_validate_layer0.py` (it asserts `len(CHECKS)` — currently 13).

You can spin up a throwaway local Postgres to run the real gate (PG16 installed;
`initdb`/`pg_ctl` must run as the `postgres` user, data dir under
`/var/lib/postgresql/`). Load baseline (strip `\restrict`/`\unrestrict`/
`SET transaction_timeout` lines per the CI step), apply the migration, run
`validate_layer0`. Local test deps: `pip install pytest pydantic openpyxl`
(pytest must be installed into the same interpreter that has the project deps —
the `uv`-tool pytest is isolated; run `PYTHONPATH=. python3 -m pytest`).

---

## Remaining work (Phases 3–6)

- **Phase 3 — #340 terrain:** migration `0035` inserting `TRN-021` into
  `layer0.terrain_types` + `layer0.terrain_gap_rules` proxy rows; update
  `_DISCIPLINE_REQUIRED_TERRAINS` in `layer4/session_feasibility.py` (~63–87) for
  D-001/003/024/018. `terrain_types` already in family `0C`; gate's
  `terrain_types` check covers format/uniqueness.
- **Phase 4 — #229 + #233 (`layer2e/builder.py`):** promote `_FUELING_BANDS`
  (~145–176), `_SPORT_PROFILE_CHO_MOD` (~180–188), `_MULTIPLIER_BANDS` (~107–116)
  and the dietary-pattern rules in `_dietary_pattern_adjustments` (~993–1047) into
  Layer 0 tables; add `layer0.sport_met_values` + a MET path in
  `_compute_activity_multiplier()` (~437–456). Seed with current constants verbatim
  (behavior-preserving), add loaders, register tables in family `0A`, add gate
  checks, add a test that table-driven output == old hardcoded output.
- **Phase 5 — #240 injury:** migration adding `layer0.injury_flag_categories`
  (separate table, per decision); ETL-style deterministic classification from
  `layer0.exercises.injury_flags_text`; refactor `layer2d/builder.py`
  (`MOVEMENT_CONSTRAINT_KEYWORDS` ~150–159; `_movement_constraint_injury_verdict`
  ~652–670) to read structured fields, free text as fallback.
- **Phase 6 — epics:** close #261 once #269 fully lands; comment on #228 noting
  the only open child (#237) is out-of-pipeline-scope and close or keep as a thin
  tracking umbrella per Andy.

Each phase = its own PR on `claude/data-pipeline-issues-plan-ml47g4` (restart it
from `origin/main` after #1069 merges), one migration applied per phase by Andy.
