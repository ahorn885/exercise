# V5 Implementation — #767 Manual-Upload Slice 2 (TCX/GPX activity parser) — Closing Handoff (2026-06-19)

## 1. What shipped

**#767 slice 2 — TCX/GPX activity parser.** The bulk activity drop zone now
ingests `.tcx` and `.gpx` per-session exports (Polar / COROS / Strava), not just
`.fit`. New parser module `tcx_gpx_parser.py` emits the **same normalized cardio
dict** `garmin_fit_parser.parse_fit` produces, so the existing
`routes/garmin._bulk_insert_cardio` writer + content-hash dedup + provider-raw
recording ingest it with **zero change**. Built on branch
`claude/fit-source-generalize-upload-6iwff4` (slice 1's branch, continued).
Full suite **2798 passed / 30 skipped**; JS harness **15/15**. **PR pending
Andy's go (PR-gated).**

Slice 1 (FIT source-generalize) is **merged** (`ad1eab2` / PR #771). Andy picked
slice 2 over slice 4 (Whoop) via AskUserQuestion: slice 2 needs no contract
change and was immediately actionable; slice 4 is Trigger #3 (ratify-first).

## 2. Design (no contract change)

Per `designs/ManualUpload_MultiService_Ingestion_Design_v1.md` §5: each new
parser emits the same activity dict shape as `parse_fit`, so the DB-write + dedup
+ provider-raw recording stay shared. TCX/GPX carry **activities only** (no
wellness variant). The chosen upload **source** (slice 1) still selects the
provider-id column + dedup prefix — the parser is source-agnostic; it only
produces the activity metrics + discipline + the `_provider_raw` corroboration
dict.

**Discipline resolution decision (documented).** TCX `<Activity Sport>` is a
3-value format enum (Running/Biking/Other); GPX `<trk><type>` is free text.
These are the **file format's** vocabulary, not a provider's, and the chosen
upload provider (coros/polar/strava) is orthogonal and unknown to the parser. So
discipline resolution uses a small parser-local `_SPORT_DISCIPLINE` map →
existing layer0 D-ids (no new disciplines/vocab — not Trigger #2), with unmapped
tokens → bucket-3 record-don't-drop (raw token kept in `provider_raw_record`).
The alternative — folding these into the consolidated
`provider_value_map_seed.CARDIO_DISCIPLINE_MAP` under a `tcx`/`gpx` key — was
**not** taken: it would materialize `provider_value_map` DB rows for a non-provider
key and broaden the blast radius into the seed + its tests, for an axis that is
genuinely format-level. Noted in CARRY_FORWARD as a possible later consolidation.

## 3. Files

1. **`tcx_gpx_parser.py`** (NEW) —
   - `parse_tcx(raw: bytes)` / `parse_gpx(raw: bytes)` → `{'log_type':'cardio','data':{…}}` (every `parse_fit` cardio key; running-dynamics fields → None — not in TCX/GPX).
   - Namespace-agnostic stdlib `xml.etree.ElementTree` parse (`_ln`/`_first`/`_all`/`_text` match on **local tag name** → tolerant of namespace/version drift across vendors).
   - TCX: lap summaries (timer time / distance / calories) + trackpoint streams (HR/cadence/power/altitude/cumulative-distance). GPX: trackpoint-only — distance integrated via `_haversine_m` from lat/lon (note: `_coord` allows negative lon; `_f`/`_i` reject ≤0 for metrics), elevation gain/loss with a `_ELEV_NOISE_M = 1.0` GPS-noise floor.
   - Unit conversion mirrors `parse_fit` (mi/mph/ft/min; one-leg cadence ×2 for foot sports; pace via the reused `garmin_fit_parser._pace_from_speed`, foot sports only).
   - `_SPORT_DISCIPLINE` format-level map + bucket; `_provider_raw` dict (`provider='manual'` fallback — overridden by the upload source at write time; `payload.format` = 'tcx'|'gpx'). Rule #15 `[cardio-ingest] {fmt} sport=… -> discipline_id=… coarse=… bucket=…` per parse.
2. **`routes/garmin.py`** —
   - `_iter_fit_blobs` → **`_iter_activity_blobs`** — yields `(name, bytes, ext, err)` where `ext ∈ {'fit','tcx','gpx'}`; expands .tcx/.gpx (and .fit) entries inside `.zip`. New `_blob_ext(name)` + `_ACTIVITY_EXTS = ('fit','tcx','gpx')`.
   - `import_bulk` — `_ACTIVITY_PARSERS = {'fit':parse_fit,'tcx':parse_tcx,'gpx':parse_gpx}`; **only `ext=='fit'` runs the wellness FileId classification** (TCX/GPX are always activities); phase-1 dispatches `_ACTIVITY_PARSERS[ext](raw)`; the FIT-only session→wellness fallback is now guarded by `ext=='fit'`. Docstring updated. (Dedup `_fit_dedup_id` is byte-hash → format-agnostic, unchanged.)
3. **`templates/connections/hub.html`** — drop-zone `data-accept` + 2× `<input accept>` widened to `.fit,.tcx,.gpx,.zip`; title/copy/hint updated. **No JS change** — the shared `[data-bulk-field]` uploader is format-agnostic.
4. **`tests/test_tcx_gpx_parser.py`** (NEW) — 16 tests: TCX run (metrics/units/cadence-doubling/pace/elevation/discipline D-002/`_provider_raw`), TCX bike (D-006 + power, no pace), TCX `Other`→bucket-3, malformed/no-Activity → ValueError; GPX run (haversine distance/streams/discipline), GPX no-type→bucket-3, no-trkpt/no-trk → ValueError; `_blob_ext` + `_iter_activity_blobs` (plain files carry ext, unsupported→error, zip expansion, zip-without-activities→error).

2 substantive code files + 1 template + 1 test — under the 5-file ceiling.

**Fixtures:** hand-authored, schema-faithful TCX (Garmin TCX v2) / GPX
(Topografix GPX 1.1 + Garmin TrackPointExtension) inline in the test. These are
documented public standards, so a schema-conformant fixture is license-clean and
deterministic — preferred over fetching/committing third-party sample files
(deviates from the slice-1 handoff's "fetch + commit as `tests/fixtures/`" note;
the design's fetch recommendation was for formats with uncertain/proprietary
schemas, e.g. Polar GDPR JSON — not the open TCX/GPX standards).

## 4. Live-verify owed (Andy-action — container can't reach Neon)

- Upload a non-Garmin `.tcx` (or `.gpx`, or a zip of them) with the **Source**
  picker set to e.g. COROS → confirm the `cardio_log` row carries the content-hash
  in `coros_label_id` (not `garmin_activity_id`), with correct
  distance/duration/HR/pace; `/admin/logs` shows `[cardio-ingest] tcx sport=…` +
  `[bulk-import] source=coros id_column=coros_label_id`; re-uploading the same
  file dedups (no duplicate).
- FIT regression: a Garmin `.fit` upload (activity + wellness files mixed) still
  classifies + lands exactly as before (the `ext=='fit'` guard preserves the
  whole FIT path).

## 5. Next slices (#767, build order)

3. **Polar/COROS wellness upload** → `provider_raw_record` via `_record_raw`.
   No contract change, **but BLOCKED**: Polar GDPR JSON has no public sample and
   Andy has none to export (Rule #14 — don't build against a guessed schema). Ask
   Andy for a sample or defer.
4. **Whoop CSV wellness** — `physiological_cycles.csv` → `recent_wellness`.
   **Trigger #3** (`WellnessSource += "whoop"` + coalesce priority
   garmin>whoop>polar>coros + a reader source + spec updates) — ratify before
   building. Highest wellness impact (Andy's gut-check: wellness > activities).
   Sample: `Philipp0205/whoop-dashboard` / `rowesk/Whoop-Data-Downloader`.
5. **Unified upload UI** — provider+format picker, zip expansion, preview/bulk.

## 6. Owed / live-verify (carried)

- **#757 residual:** `connected_providers` Garmin coverage (garmin_auth vs provider_auth).
- #337 measured-physiology live-verify; #698 C1/C2 + Part-A drill-render live-verify (item b); post-#572 live T3 refresh re-verify; #430 Slice C / #679 EX-id self-heal live-verify; #732 parked.

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session).
3. `CARRY_FORWARD.md` — manual-upload track (slices 1+2 shipped; 3–5 owed) + #757 residual.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

Then pick up **#767 slice 4 (Whoop CSV wellness)** if wellness-into-coaching is
the priority (Trigger #3 — ratify the `WellnessSource` extension first); or
**slice 3 (Polar/COROS wellness)** once a real Polar GDPR JSON sample exists.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| New parser | `tcx_gpx_parser.py` | `def parse_tcx(raw: bytes) -> dict:` + `def parse_gpx(raw: bytes) -> dict:`; both `return {'log_type': 'cardio', 'data': data}` |
| Format map | `tcx_gpx_parser.py` | `_SPORT_DISCIPLINE = {` with running→D-002 / biking→D-006 / hiking→D-003 / swimming→D-004; unmapped → `('Activity', None, None)` |
| GPX geometry | `tcx_gpx_parser.py` | `def _haversine_m(`; `_coord` (allows negative lon); `_ELEV_NOISE_M = 1.0` |
| Cadence parity | `tcx_gpx_parser.py` | `cadence_mult = 2 if is_foot else 1`; `_FOOT_SPORTS` |
| Rule #15 | `tcx_gpx_parser.py` | `print(  # Rule #15` → `[cardio-ingest] {fmt} sport=…` |
| Blob iterator | `routes/garmin.py` | `def _iter_activity_blobs(files):` yields `(name, …, ext, err)`; `def _blob_ext(`; `_ACTIVITY_EXTS = ('fit', 'tcx', 'gpx')` |
| Dispatch | `routes/garmin.py` | `import_bulk`: `_ACTIVITY_PARSERS = {'fit': parse_fit, 'tcx': parse_tcx, 'gpx': parse_gpx}`; `if ext == 'fit':` guards wellness classification; `result = _ACTIVITY_PARSERS[ext](raw)`; `if ext == 'fit' and 'session' in msg.lower():` |
| UI accept | `templates/connections/hub.html` | `data-accept=".fit,.tcx,.gpx,.zip"` + 2× `accept=".fit,.tcx,.gpx,.zip"` |
| Tests | `tests/test_tcx_gpx_parser.py` | `TestParseTcx`, `TestParseGpx`, `TestBlobExt`, `TestIterActivityBlobs` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2798 passed / 30 skipped; `npm test` → 15/15 (needs `npm install` for `jsdom`) |
| Issue | #767 (slice 2 checkbox ticked + comment with commit ref) | — |
