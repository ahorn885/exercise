# V5 Implementation — Layer 0 phase 4: DB→xlsx bulk-review export (decision B)

**Date:** 2026-06-11
**Branch:** `claude/beautiful-clarke-rgsgnm` · **Epic [#488](https://github.com/ahorn885/exercise/issues/488)**

## 1. What this session was

Picked up off the slice-3b closing handoff. The handoff named **phase 4** as next; I flagged that phase 4 is two parts with a dependency order, and that the headline part (the §6.4 *freeze* of the extractors/workbooks) is **gated by the spec itself on "2–3 migrations gone through"** — only `0001` has, so freezing now is premature. Andy confirmed the phase-4 track anyway. The ripe, ungated, low-regret slice is the other half: **decision B, the DB→xlsx export** (design §3.5 / §6.5), which §8's own gut check calls the prerequisite that makes full xlsx retirement *safe*. Built that; left the freeze owed-and-gated.

Session start was clean: `verify-handoff.sh` all-green, working tree clean, slice 3b (`#544`) merged at the tip of `main`. No Rule #9 drift.

## 2. What shipped (code)

- **`etl/layer0/export_xlsx.py`** — read-only DB→xlsx export. One sheet per `layer0.*` table, **active rows only** (`WHERE superseded_at IS NULL` on tables that carry the column). Tables are discovered from `information_schema` (no maintained list → `terrain_gap_rules` / `supplement_vocabulary` and any future table are picked up automatically). Structure mirrors `validate_layer0.py`: pure, unit-tested serialization + workbook assembly; `collect(conn)` is the only DB-touching step; `main()` imports `db` lazily so the pure logic carries no psycopg2 / live-connection dependency. CLI: `python -m etl.layer0.export_xlsx [--out PATH]`, default `etl/output/layer0_db_export.xlsx`.
  - **`cell_value`** flattens the psycopg2 type landscape to xlsx-legal scalars: `Decimal`→float, **tz-aware `datetime`→ISO string** (the load-bearing case — openpyxl *raises* on tz-aware datetimes, and `TIMESTAMPTZ` columns return them), `TEXT[]`→comma-joined, `JSONB` dict/list→JSON. Scalars pass through.
- **`etl/tests/test_export_xlsx.py`** — 12 DB-free unit tests: `cell_value` per type (incl. the tz-aware-datetime crash case), `safe_sheet_name` (31-char truncation / reserved-char scrub / dedupe), and `build_workbook` round-trips (header + freeze panes + complex-cell serialization end-to-end + the empty-schema-still-saveable guard).
- **`Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md`** (in-place edit, matching slice 3b's §5.3 precedent — no version bump): §6.5 + §8 decision B marked built; §9 checklist box `[x]` for the export and an explicit "still owed / gated" note on the §6.4 freeze.

The generated `.xlsx` is **not committed** — `.gitignore`'s global `*.xlsx` ignores it; it's a regenerate-on-demand review artifact, not a reproducible genesis artifact (the committed v1.6.x SQL snapshot under `etl/output/` is).

**Tests:** `etl/tests/` **197 passed** (185 prior + 12 new). CLI `--help` runs with no DB (lazy import confirmed). Main `tests/` suite untouched (no app-code change).

## 3. Owed / next move

1. **Andy's-hands — first live run.** Container egress to Neon is blocked, so the end-to-end `collect()`/SELECT path is unexercised here (the pure layer is fully unit-tested). Run `python -m etl.layer0.export_xlsx` against the Neon `DATABASE_URL` once and eyeball the workbook (≈25 sheets; `exercises` ~211 rows, `sports` ~36). No DDL, nothing to apply — pure read.
2. **Carried owed from slice 3b (unchanged):** cold-plan post-deploy verify (`ready` + non-empty terrain + real exercise pool). No migration owed.
3. **Phase 4 §6.4 freeze — still owed AND still gated.** Freeze `etl/layer0/extractors/`, `run.py`, `emit_sql.py` + the two workbooks (v14/v19) into an archive **only after 2–3 migrations have gone through cleanly** (only `0001` has). The export now exists, so the freeze is *safe* whenever the gate clears — but don't pull it forward.
4. **Off-track go-live blockers still open** (from the pv=65 review, higher on the 4-tier order than the rest of phase 4): **#539** (tab-closed plan-gen crawl) and **#540** (terrain-infeasible locale routing). I recommended #539 at session start; Andy chose phase 4 this round.

## 4. Stop-and-ask status

None pending. The export is read-only, additive, no LLM / schema / contract / HITL surface — no trigger fired. The one judgment call (build the export before the freeze, and not the freeze itself) is recorded in §1 + the design-doc §6.5 edit.

### 4.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. Then epic #488 + `Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` (§6.4 freeze is the remaining phase-4 item, gated on migration count).

## 5. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Export module exists, pure-logic + lazy-DB shape | `etl/layer0/export_xlsx.py` | `def cell_value` / `def build_workbook` (pure) · `def collect` ("only DB-touching step") · `main()` does `from etl.layer0 import db` lazily |
| Schema discovered, not listed | `etl/layer0/export_xlsx.py` | `def discover_tables` → `information_schema.tables WHERE table_schema = 'layer0'` |
| Active-rows-only filter | `etl/layer0/export_xlsx.py` | `def fetch_table` → `WHERE superseded_at IS NULL` guarded by an `information_schema.columns` check |
| tz-aware datetime → ISO string (openpyxl crash guard) | `etl/layer0/export_xlsx.py` | `cell_value`: `isinstance(value, datetime)` → `value.isoformat()` |
| Tests, DB-free, 12 | `etl/tests/test_export_xlsx.py` | `test_cell_value_tz_aware_datetime_becomes_iso_string` + `test_build_workbook_*` round-trips |
| Design doc synced | `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | §6 item 5 "built 2026-06-11"; §9 `[x] DB→xlsx export`; §9 freeze line "still owed" |

## 6. Summary

Phase 4 has two halves; this session shipped the ripe one. **`etl/layer0/export_xlsx.py`** is a read-only DB→xlsx projection (one sheet per `information_schema`-discovered `layer0.*` table, active rows only) that recovers the spreadsheet's only genuine advantage — bulk visual review of all ~36 sports / ~211 exercises at once — without re-introducing it as an authoring input. It mirrors `validate_layer0`'s pure-logic + lazy-DB shape, so it's fully unit-tested DB-free (12 tests; `etl/tests/` 197 green) despite the Neon egress block. The motivating subtlety is the serializer: `TIMESTAMPTZ` hands back tz-aware datetimes that openpyxl refuses to write, so `cell_value` flattens datetimes to ISO strings (and `Decimal`→float, `TEXT[]`→joined, `JSONB`→JSON). The §6.4 extractor/workbook **freeze stays owed and gated** on 2–3 migrations going through (only `0001` has); the export existing is what makes that freeze safe when the gate clears. Only owed-hands item is a one-time live run of the exporter against Neon.
