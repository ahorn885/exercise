# V5 Implementation — #767 Manual-Upload Slice 1 (FIT source-generalize) — Closing Handoff (2026-06-19)

## 1. What shipped

**#767 slice 1 — FIT source-generalize.** The bulk `.FIT` drop zone now ingests
activities exported from **non-Garmin** services (COROS / Wahoo / Polar / Strava),
not just Garmin. Built on branch `claude/unified-wellness-manual-upload-cgbrya`;
**commit `0917c2d`; PR pending Andy's go (PR-gated).** Full suite **2782 passed /
30 skipped**; JS harness **15/15**.

This is the first build slice of issue **#767** (tracked from the #757 closing
handoff). The Strava-id groundwork (column + `WorkoutSource`) had already landed
in PR #765; this slice makes the *uploader* actually write to those columns.

## 2. Design (no contract change)

Principle (from `designs/ManualUpload_MultiService_Ingestion_Design_v1.md`):
uploaded data lands in the **same tables + source tags** the Layer-3A readers
already use, so readers need no change. A manually uploaded FIT has no provider
activity-id → hash the bytes for an idempotent dedup key, store it in the id
column matching the source, with a source-specific prefix so keys never collide
across providers.

`_SOURCE_MAP` (the allowlist):

| source | cardio/strength id column | dedup prefix |
|---|---|---|
| garmin (default) | `garmin_activity_id` | `fit:` |
| coros | `coros_label_id` | `coros-file:` |
| wahoo | `wahoo_workout_id` | `wahoo-file:` |
| polar | `polar_exercise_id` | `polar-file:` |
| strava | `strava_activity_id` | `strava-file:` |

All columns pre-exist in `cardio_log` (+ `training_log` for all but strava). The
column name is only ever drawn from this fixed allowlist — no user-supplied
identifier reaches the SQL string (the f-string interpolation is safe).

## 3. Files

1. **`routes/garmin.py`** —
   - `_SOURCE_MAP` + `_source_column(source)` / `_source_prefix(source)` (garmin = default for unknown).
   - `_fit_dedup_id(raw, prefix='fit:')` — prefix is now a param; the single-file Garmin path (`import_fit` ~line 60) keeps the default → unchanged behavior.
   - `_bulk_insert_cardio(..., source='garmin')` — writes `gid` to `{col}`; passes `provider=source` to the corroboration write.
   - `_bulk_insert_strength(..., source='garmin')` — same column selection (strava can't occur — no strength FITs).
   - `_record_provider_raw_cardio(..., provider=None)` — tags the `provider_raw_record` cardio corroboration row with the true source instead of the parser's garmin default; Rule #15 prints use it.
   - `_already_imported(db, gid, source='garmin')` — dedups against the source's column; **Strava skips the `training_log` query** (no strava column there; can't be a strength dup).
   - `_bulk_log_one(..., source='garmin')` — threads source to both inserters.
   - `import_bulk` — reads + validates `request.form.get('source')` (unknown → garmin), computes prefix, threads through dedup + insert, **Rule #15** `[bulk-import] source=… id_column=… files=…` log.
2. **`templates/connections/hub.html`** — `<select name="source" data-bulk-field>` (Garmin/COROS/Wahoo/Polar/Strava). The existing `app.js` auto-includes every `[data-bulk-field]` with each batch → **no JS change**.
3. **`tests/test_garmin_bulk_source.py`** (NEW) — source map distinctness + default fallback; `_fit_dedup_id` prefix; cardio writes the right column + tags provider; strength column selection; `_already_imported` per-source incl. cardio short-circuit, training_log fall-through, and the Strava skip.

2 substantive files + 1 test file — under the 5-file ceiling.

## 4. Live-verify owed (Andy-action — container can't reach Neon)

- Upload a non-Garmin `.FIT` (or zip) with the **Source** picker set to e.g. COROS → confirm the `cardio_log` row carries the hash in `coros_label_id` (not `garmin_activity_id`), `/admin/logs` shows `[bulk-import] source=coros id_column=coros_label_id`, and re-uploading the same file dedups (no duplicate).
- Garmin regression: a Garmin upload still lands in `garmin_activity_id` and still dedups (default path unchanged).

## 5. Next slices (#767, build order)

2. **TCX/GPX parser** — new module emitting the **same normalized activity dict** `parse_fit` produces, so `_bulk_insert_cardio` is unchanged. Needs public fixtures (verified available — design §10.1: TCX `aaron-schroeder/activereader` / `dblock/tcx`; GPX standard). Fetch + commit each as `tests/fixtures/` alongside the parser. *(After this, the UI source picker should also gain a format affordance, or the endpoint should sniff TCX/GPX vs FIT.)*
3. **Polar/COROS wellness upload** → `provider_raw_record` via `_record_raw`. Polar GDPR JSON has **no public sample — ask Andy to export one** first.
4. **Whoop CSV wellness** — `physiological_cycles.csv` → `recent_wellness`. **Trigger #3** (cross-layer `WellnessSource += "whoop"` + coalesce priority garmin>whoop>polar>coros + spec updates) — ratify before building. Highest wellness impact (Andy's gut-check: wellness > activities).
5. **Unified upload UI** — provider+format picker, zip expansion, preview/bulk.

## 6. Owed / live-verify (carried)

- **#757 residual:** `connected_providers` Garmin coverage (garmin_auth vs provider_auth).
- #681 §4 Slice 3 live-verify (rename + bespoke drops); #337 measured-physiology live-verify; #698 C1/C2 + Part-A drill-render live-verify; post-#572 live T3 refresh re-verify; #430 Slice C / #679 EX-id self-heal live-verify; #732 parked.

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session).
3. `CARRY_FORWARD.md` — #757 residual + the manual-upload track.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

Then pick up **#767 slice 2 (TCX/GPX parser)** — needs public fixtures, no contract decision; or **slice 4 (Whoop)** if wellness-into-coaching is the priority (Trigger #3 — ratify first).

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Source map | `routes/garmin.py` | `_SOURCE_MAP = {` with garmin/coros/wahoo/polar/strava → (column, prefix) |
| Helpers | `routes/garmin.py` | `def _source_column(source` + `def _source_prefix(source` |
| Dedup prefix param | `routes/garmin.py` | `def _fit_dedup_id(raw: bytes, prefix: str = 'fit:')` |
| Cardio column | `routes/garmin.py` | `def _bulk_insert_cardio(` … `source: str = 'garmin'`; INSERT uses `{col}`; `_record_provider_raw_cardio(..., provider=source)` |
| Strength column | `routes/garmin.py` | `def _bulk_insert_strength(` … `source: str = 'garmin'`; `col = _source_column(source)` |
| Provider tag | `routes/garmin.py` | `_record_provider_raw_cardio(..., provider: str \| None = None)`; `provider or raw.get('provider', 'garmin')` |
| Dedup per source | `routes/garmin.py` | `def _already_imported(db, gid: str, source: str = 'garmin')`; `if source == 'strava': return False` |
| Endpoint wiring | `routes/garmin.py` | `import_bulk`: `source = request.form.get('source', 'garmin')` + `[bulk-import] source=` print |
| UI picker | `templates/connections/hub.html` | `<select name="source" data-bulk-field` with 5 options |
| Tests | `tests/test_garmin_bulk_source.py` | `TestSourceMap`, `TestBulkInsertCardio`, `TestBulkInsertStrength`, `TestAlreadyImported` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2782 passed / 30 skipped; `npm test` → 15/15 |
| Issue | #767 (slice 1 checkbox ticked + comment with commit ref) | — |
