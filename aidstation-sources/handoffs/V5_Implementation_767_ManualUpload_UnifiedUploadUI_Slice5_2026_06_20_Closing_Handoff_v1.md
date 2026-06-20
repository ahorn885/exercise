# V5 Implementation — #767 Manual-Upload Slice 5 (Unified upload UI) — Closing Handoff (2026-06-20)

## 1. What shipped

**#767 slice 5 — unified upload UI. The last manual-upload slice → the track is
COMPLETE.** Collapsed the standalone `/whoop/import` page (slice 4) into the
existing bulk drop zone so the connections **Data hub has ONE uploader that
auto-detects each file and routes it server-side** — activities and wellness
through a single drag-and-drop. No contract/cache/migration/prompt change; no
stop-and-ask trigger (the slice-4 handoff flagged slice 5 as "No trigger").

Built on branch `claude/whoop-csv-wellness-slice-5-qcb5h3`. Slice 4 merged first
(PR #783 → `23c8e95`) while slice 5 was in flight, so this branch **rebased onto
the post-merge `main`** (slice-4 code already present → slice-5-only diff). Full
suite **2829 passed / 30 skipped** (the +6 slice-5 tests on top of `main`). **PR
open, auto-merge armed.**

### Rule #9 at session start — the stacking, then the merge

The slice-4 Whoop work (`WellnessSource += "whoop"`, `whoop_csv_parser.py`, the
whoop writer, specs) started on its own branch. Since slice 5 *folds in* slice
4's `/whoop/import`, it was first built stacked on the slice-4 tip. **Mid-session
Andy merged slice 4** (PR #783 → squash `23c8e95` on `main`), so slice 5 was
**rebased onto the post-merge `main`** with `git rebase --onto origin/main
3b1d9b9` — clean, because all five slice-5 code/test files were byte-identical
between the slice-4 tip and the merged `main` (the squash carried slice 4's code
unchanged). Net: a slice-5-only diff on top of `main`.

### The design call (Andy, this session)

First cut put the WHOOP CSV in a *second* card next to the activity drop zone.
Andy: **"single uploader that auto detects."** So it's now ONE drop zone: the
backend (`garmin.import_bulk`) classifies every uploaded file by extension and
routes it — `.fit/.tcx/.gpx` → `cardio_log`; Garmin wellness/daily-metric FITs →
`wellness_log`/`daily_wellness_metrics`; a `.csv` (WHOOP `physiological_cycles`)
→ `provider_raw_record`. Drop a whole export folder (or zip) of mixed files and
each lands where it belongs.

## 2. How the auto-detect works

`routes.garmin.import_bulk` already iterates `_iter_activity_blobs` (expands
zips, yields `(name, bytes, ext, err)`), classifies FIT files by their
`FileIdMessage` kind, and routes wellness FITs vs activities. Slice 5 extends the
**recognized extension set** to include `csv` and adds one routing branch:

- `_blob_ext` / `_UPLOAD_EXTS` now recognize `csv` (→ ext `'csv'`); zip
  expansion picks up `.csv` entries for free (the filter keys off `_blob_ext`).
- The classify loop routes `ext == 'csv'` into `wellness_csv_pending`, processed
  after the wellness FITs by **`_ingest_wellness_csv`** — same `(results,
  summary)` contract as `_ingest_wellness_fit`, so a wellness CSV reports
  identically in the drag-and-drop UI (status `imported`, detail `WHOOP wellness
  · N day(s)`; `summary.metrics_days += N`). A `.csv` that isn't a usable WHOOP
  export is reported as an **error** (not silently dropped) — Rule #15 logs
  `[bulk-import] wellness-csv … ingested N day(s)`.
- The ingest itself reuses slice 4's writer via a new reusable
  `routes.whoop.ingest_whoop_csv(db, uid, raw) -> int` (parse + `_record_raw`
  per day; caller commits). Same `provider_raw_record` (`provider='whoop'`,
  `data_type='daily_summary'`) rows slice 4 wrote — so the Layer-3A coalesce is
  unchanged.

**The JS uploader needed no change** — it reads `data-accept`, filters the
dropped/selected files to those extensions, POSTs them, and renders the server's
`summary` + per-file `results`. Widening `data-accept` to `.csv` is the only
client touch.

**No wellness *provider* picker fabricated.** WHOOP is the only wellness export
that ships as a file (Garmin wellness rides the FIT classification; Polar/COROS
have no wellness file — slice 3 retired). A `.csv` == a WHOOP export; the
parser validates. The Source picker stays activity-only (it selects the
provider-id column for `cardio_log`); its copy now says wellness/CSV route
automatically regardless.

## 3. Files

1. **`routes/garmin.py`** (MOD) — `_WELLNESS_CSV_EXT='csv'` + `_UPLOAD_EXTS =
   _ACTIVITY_EXTS + ('csv',)`; `_blob_ext` iterates `_UPLOAD_EXTS` (recognizes
   `csv`); `_iter_activity_blobs` docstring + error strings widened to
   `.fit/.tcx/.gpx/.csv`. New `_ingest_wellness_csv(db, uid, name, raw, results,
   summary)` (mirrors `_ingest_wellness_fit`'s contract). `import_bulk`:
   `wellness_csv_pending` collected in the classify loop (`ext == 'csv'`) and
   ingested after the wellness FITs; docstring updated.
2. **`routes/whoop.py`** (MOD) — added reusable `ingest_whoop_csv(db, user_id,
   raw) -> int` (parse + `_record_raw` per day; no commit — caller owns the txn).
   **Removed** the `/whoop/import` route + its `_extract_csv` helper (folded into
   the one uploader). Trimmed imports to `Blueprint, jsonify` + `json` +
   `parse_whoop_physiological_cycles`. `webhook` stub + `_record_raw` unchanged.
3. **`templates/connections/hub.html`** (MOD) — single drop zone: `data-accept`
   + both `<input accept>` widened to `.fit,.tcx,.gpx,.csv,.zip`; title "Upload
   activity files" → "Upload your data"; copy + drag hint name the WHOOP
   `physiological_cycles.csv`; Source-picker note clarifies wellness/CSV
   auto-route. (The earlier separate "Upload wellness data" card was removed.)
   Hero subtitle reads "activity files and wellness exports".
4. The slice-4 standalone WHOOP import template (the `import.html` under
   `templates/whoop/`) is **deleted** — folded into the one uploader; that dir
   is now empty/gone. (Path not written in full so the anchor sweep doesn't
   flag an intentionally-removed file as missing.)
5. **`tests/test_tcx_gpx_parser.py`** (MOD) — blob tests updated for `csv`:
   `_blob_ext('…csv') == 'csv'` (+ `.txt`/`.zip` → None); a `.csv` blob carries
   ext `'csv'`; unsupported-file error uses `.txt`; zip-without-ingestibles error
   string now `.fit/.tcx/.gpx/.csv`.
6. **`tests/test_redesign_connections_render.py`** (MOD) — replaced the
   two-card/route tests with: unified uploader advertises `.csv`
   (`data-accept=".fit,.tcx,.gpx,.csv,.zip"`) + no `/whoop/import` form;
   `/whoop/import` route 404s (removed); a WHOOP CSV POSTed to
   `/garmin/import/bulk` auto-routes to wellness (`metrics_days==1`, status
   `imported`, "WHOOP wellness"); a non-WHOOP CSV reports an error. `_Conn` fake
   gained `rollback`; `_client` disables `WTF_CSRF_ENABLED` (the bulk endpoint
   isn't csrf-exempt — the real JS sends the `X-CSRFToken` header). `import io`.

4 substantive code/template + 2 test files. Over the soft 5-file ceiling by one
test file because the single-uploader rework touches the activity importer, the
whoop writer, the template, and **two** existing test files whose contracts the
extension-set change broke — one atomic slice. Flagged, not silently breached.

## 4. Merge order (done in order, per Andy)

Slice 4 merged first (PR #783 → `23c8e95`). Slice 5 then rebased onto `main` and
is its own PR (auto-merge armed) — a clean slice-5-only diff. The "merge both in
order" instruction is satisfied: 4 landed, 5 follows.

## 5. Live-verify owed (Andy-action — container can't reach Neon)

- **Whoop (carried from slice 4, now via the one uploader):** from the Data hub
  Sources tab, drop a real `physiological_cycles.csv` (mixed in with activity
  files / a zip is fine) → the results panel shows it `imported` as "WHOOP
  wellness · N day(s)"; `/admin/logs` shows `[whoop-wellness] … cols={…}`
  resolving HRV/RHR/sleep (a missing key = a header the tolerant matcher missed
  → tighten `whoop_csv_parser._COLUMN_MATCHERS`) + `[bulk-import] wellness-csv …
  ingested N day(s)`; `recent_wellness` carries `*_source='whoop'` for those days
  (whoop wins freshest-non-null vs polar/coros, loses to a fresher garmin).
  Re-dropping dedups in place. **Regression:** a mixed drop of `.fit` activities
  + Garmin wellness FITs + a WHOOP `.csv` routes each correctly in one batch.
- Carried: slice-1/slice-2 activity-upload live-verify.

## 6. Owed / carried

- #757 residual: `connected_providers` Garmin coverage (garmin_auth vs provider_auth).
- #337 measured-physiology live-verify; #698 C1/C2 + Part-A item (b) live-verify; post-#572 live T3 refresh re-verify; #430 Slice C / #679 EX-id self-heal live-verify; #732 parked.

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session).
3. `CARRY_FORWARD.md` — manual-upload track (now **COMPLETE**: 1+2 merged, 3 retired, 4+5 built/verify-owed) + #757 residual.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

The #767 manual-upload track is closed. Next focus is Andy's call — service a
live-verify (Whoop is the freshest), or pick the next issue by the 4-tier order.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Recognized exts | `routes/garmin.py` | `_WELLNESS_CSV_EXT = 'csv'`; `_UPLOAD_EXTS = _ACTIVITY_EXTS + (_WELLNESS_CSV_EXT,)`; `_blob_ext` loops `_UPLOAD_EXTS` |
| CSV route | `routes/garmin.py` | `import_bulk`: `if ext == 'csv': wellness_csv_pending.append(...)`; `for name, raw in wellness_csv_pending: _ingest_wellness_csv(...)` |
| CSV ingest | `routes/garmin.py` | `def _ingest_wellness_csv(db, uid, name, raw, results, summary):` → `from routes.whoop import ingest_whoop_csv`; detail `WHOOP wellness · {days} day(s)`; `print(  # Rule #15` → `[bulk-import] wellness-csv` |
| Reusable writer | `routes/whoop.py` | `def ingest_whoop_csv(db, user_id, raw) -> int:` (parse + `_record_raw` per day, no commit); `_record_raw` unchanged; **no** `import_wellness` / `_extract_csv` |
| Trimmed imports | `routes/whoop.py` | `from flask import Blueprint, jsonify`; only `/whoop/webhook` route remains |
| One drop zone | `templates/connections/hub.html` | `data-accept=".fit,.tcx,.gpx,.csv,.zip"` + 2× `accept=".fit,.tcx,.gpx,.csv,.zip"`; title "Upload your data"; names `physiological_cycles.csv`; no `whoop.import_wellness` / `name="csv_file"` |
| Blob tests | `tests/test_tcx_gpx_parser.py` | `test_recognizes_wellness_csv`; `test_csv_blob_carries_csv_ext`; zip-without error asserts `no .fit/.tcx/.gpx/.csv` |
| Routing tests | `tests/test_redesign_connections_render.py` | `test_sources_tab_unified_uploader_accepts_csv`, `test_whoop_import_route_is_removed`, `test_bulk_import_auto_routes_whoop_csv`, `test_bulk_import_rejects_non_whoop_csv`; `_Conn.rollback`; `WTF_CSRF_ENABLED` False |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2829 passed / 30 skipped |
| Base (slice 4) | `main` | slice 4 merged as `#783`/`23c8e95`; this branch rebased onto `main`; `grep 'WellnessSource = Literal' layer4/context.py` ends `"coros", "whoop"]` |
| Issue | #767 | slice-5 checkbox ticked + comment with the slice-5 commit ref |
