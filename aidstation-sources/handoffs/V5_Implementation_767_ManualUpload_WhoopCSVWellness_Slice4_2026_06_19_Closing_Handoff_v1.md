# V5 Implementation — #767 Manual-Upload Slice 3 retired + Slice 4 (Whoop CSV wellness) — Closing Handoff (2026-06-19)

## 1. What shipped

Two things on branch `claude/tcx-gpx-parser-upload-cph7nd` (continued from the
slice-2 handoff; slice 2 was already **merged** `16f8250`/#773):

**A. Slice 3 (Polar/COROS wellness upload) RETIRED `not_planned`** (commit
`79398f6`). Scoping broke the premise: **no wellness *file* exists** for either
provider. Polar's "export all your data" (GDPR) ZIP **omits sleep + nightly
recharge** — they're algorithm-derived and live only behind the AccessLink API
(Polar's own support page: "activity and sleep information are not included in
the exported file"; intervals.icu users confirm the export carries activities
but no sleep/recharge). COROS wellness is app-only. Both already ingest via
their live webhooks (`routes/polar_ingest.py`, `routes/coros_ingest.py`), so
there is nothing to parse. Design doc §3/§5/§7/§10 corrected; issue #767 slice-3
checkbox closed. (Also fixed the slice-2 "PR pending" → merged `16f8250`/#773
drift in CURRENT_STATE + the issue.)

**B. Slice 4 (Whoop CSV wellness) BUILT** (commit `cad526f`). A WHOOP
`physiological_cycles.csv` export → the same `provider_raw_record` → Layer-3A
coalesce path Polar/COROS already use, so `recent_wellness` gains Whoop sleep /
HRV (RMSSD) / resting-HR. **Trigger #3** (cross-layer surface) — ratified by
Andy 2026-06-19 (AskUserQuestion ×3). Full suite **2815 passed / 30 skipped**
(+15 whoop parser, +2 whoop reader). **PR pending Andy's go (PR-gated).**

## 2. Design / ratified decisions (slice 4)

The **target** payload schema was already fully pinned by the existing reader
`q_layer3A_recent_wellness` (it reads `total_sleep_min` / `hrv_rmssd_ms` /
`resting_hr` / sleep-span / `ppg_hrv` out of `provider_raw_record`). Slice 4
only adds a new **source** (Whoop) feeding that machinery. Andy's three calls:

1. **RHR multi-source — YES.** `resting_hr` was garmin-only; Whoop
   (`physiological_cycles.csv` carries resting HR) joins it. First non-Garmin
   resting-HR source; same freshest-non-null logic.
2. **Landing shape — one uniform `daily_summary` row** ("all done the same"):
   provider='whoop', data_type='daily_summary', carrying sleep+hrv+rhr together
   (COROS-style), all metrics treated identically. The existing live Polar/COROS
   writers were **not** refactored (out of scope, risky to working webhook code).
3. **Scope — parser + minimal upload route.** `/whoop/import` endpoint now;
   polished provider+format picker stays slice 5.

Priority **garmin>whoop>polar>coros** (design §10, already ratified). **Not
Trigger #1** (no prompt-body change — provenance is just a tag the #757 render
already handles). **No cache bump** (the bundle hash shifts naturally when whoop
data appears). **Sample (Rule #14):** built against WHOOP's *documented*
`physiological_cycles.csv` schema with a **tolerant normalized-token column
matcher** (robust to casing/unit/version drift) — a real-file live-verify is
owed (see §4).

## 3. Files (slice 4)

1. **`whoop_csv_parser.py`** (NEW) — `parse_whoop_physiological_cycles(raw: bytes) -> list[dict]`; one record/day `{date, total_sleep_min, hrv_rmssd_ms, resting_hr, recovery_score, day_strain, sleep_performance_pct}`. `_resolve_columns` maps target keys to columns via `_norm` (lowercase + alphanumeric-only) + a per-key *contains* predicate (`_COLUMN_MATCHERS`); "asleep duration" matched, NOT "in bed duration". `_pos` (>0 else None) for metrics, `_num` (≥0) for corroboration. Raises ValueError on no-date-col / no-metric-col / no-usable-rows. Rule #15 `[whoop-wellness] … cols={resolved map}` per parse.
2. **`layer4/context.py`** — `WellnessSource = Literal["garmin","polar","coros","whoop"]`; `DailyWellnessRecord` docstring (resting_hr multi-source, ties garmin>whoop>polar>coros).
3. **`layer3a/integration.py`** — `_WELLNESS_SOURCE_PRIORITY = {"garmin":4,"whoop":3,"polar":2,"coros":1}`; new whoop `daily_summary` SELECT after the COROS branch feeding sleep_cand/hrv_cand/rhr_cand; accessor docstring updated.
4. **`routes/whoop.py`** — `/whoop/import` (GET form, POST process; `.csv` or `.zip` bundle via `_extract_csv`) + `_record_raw(db,uid,'daily_summary',date,payload)` writer (provider='whoop', idempotent ON CONFLICT) + Rule #15 `[whoop-import] … ingested N day(s)`. Blueprint already registered + csrf-exempt.
5. **`templates/whoop/import.html`** (NEW) — minimal upload form (extends `base.html`).
6. **`tests/test_whoop_csv_parser.py`** (NEW, 15) — full-row, asleep-not-in-bed, RHR-round, multi-day, blank/zero→None, BOM, tolerant header variant, rejects (empty/no-date/no-metric/header-only/all-unusable), column-resolution.
7. **`tests/test_layer3a_integration.py`** (MOD) — `test_empty_all_sources` 4→5 SELECTs; +2 whoop tests (sleep/hrv/rhr contribution; garmin>whoop>polar tie order); bundle-compose queue counts 15→16 (1+5+1+2+7).
8. **specs** — `Layer3_3A_Spec.md` §7; `Athlete_Data_Integration_Spec_v6.md` §5.5 + the §10 coalesce mirror.

5 code/template + 2 spec + 2 test. Larger than the soft 5-file ceiling because a
Trigger #3 contract change is intrinsically cross-cutting (parser + Literal +
reader + route + specs are one atomic slice — splitting would ship a half-wired
contract). Flagged, not silently breached.

## 4. Live-verify owed (Andy-action — container can't reach Neon)

- **Whoop (Rule #14, the key one):** upload a **real** `physiological_cycles.csv`
  at `/whoop/import` → `/admin/logs` shows `[whoop-wellness] … cols={…}` with
  HRV/RHR/sleep columns **resolved** (a missing key = a header the matcher
  didn't catch → tighten `_COLUMN_MATCHERS`), then `[whoop-import] … ingested N
  day(s)`; `recent_wellness` carries `hrv_rmssd_ms_source='whoop'` /
  `resting_hr_source='whoop'` for those days (whoop wins freshest-non-null vs
  polar/coros; loses to a fresher garmin). Re-uploading dedups in place.
- Carried: slice-1 / slice-2 activity-upload live-verify (still owed).

## 5. Next slices (#767)

5. **Unified upload UI** — provider+format picker on the connections page, zip
   expansion, preview/bulk. The **last** manual-upload slice. Would fold
   `/whoop/import` + the activity drop zone into one entry point. No trigger.

(Slices 1+2 merged; 3 retired; 4 built, live-verify owed.)

## 6. Owed / carried

- #757 residual: `connected_providers` Garmin coverage (garmin_auth vs provider_auth).
- #337 measured-physiology live-verify; #698 C1/C2 + Part-A item (b) live-verify; post-#572 live T3 refresh re-verify; #430 Slice C / #679 EX-id self-heal live-verify; #732 parked.

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session).
3. `CARRY_FORWARD.md` — manual-upload track (1+2 shipped, 3 retired, 4 built/verify-owed, 5 owed) + #757 residual.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

Then pick up **#767 slice 5 (unified upload UI)** — or service a live-verify.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Contract | `layer4/context.py` | `WellnessSource = Literal["garmin", "polar", "coros", "whoop"]` |
| Priority | `layer3a/integration.py` | `_WELLNESS_SOURCE_PRIORITY` = `{"garmin": 4, "whoop": 3, "polar": 2, "coros": 1}` |
| Reader branch | `layer3a/integration.py` | `WHERE user_id = %s AND provider = 'whoop' AND data_type = 'daily_summary'`; appends to sleep_cand/hrv_cand/rhr_cand with source `"whoop"` |
| Parser | `whoop_csv_parser.py` | `def parse_whoop_physiological_cycles(raw: bytes) -> list[dict]:`; `_COLUMN_MATCHERS`; `_resolve_columns`; `print(  # Rule #15` → `[whoop-wellness]` |
| Asleep-not-in-bed | `whoop_csv_parser.py` | `_COLUMN_MATCHERS["total_sleep_min"]` matches `"asleep duration"` (not "in bed") |
| Route | `routes/whoop.py` | `@bp.route('/import', …)` `def import_wellness`; `def _record_raw(` → `provider='whoop'`, `'daily_summary'`; `print(  # Rule #15` → `[whoop-import]` |
| Template | `templates/whoop/import.html` | form posts `url_for('whoop.import_wellness')`, input `name="csv_file"` |
| Specs | `specs/Layer3_3A_Spec.md` §7; `specs/Athlete_Data_Integration_Spec_v6.md` §5.5/§10 | "garmin/polar/coros/whoop" + "garmin>whoop>polar>coros" |
| Design | `designs/ManualUpload_MultiService_Ingestion_Design_v1.md` | top-of-doc "Correction (2026-06-19) — slice 3 retired"; §7 slice 3 struck |
| Tests | `tests/test_whoop_csv_parser.py`, `tests/test_layer3a_integration.py` | `TestParseWhoop`/`TestRejects`/`TestColumnResolution`; `test_whoop_contributes_sleep_hrv_and_resting_hr`, `test_whoop_priority_below_garmin_above_polar_on_tie` |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2815 passed / 30 skipped |
| Issue | #767 | slice 3 closed `not_planned`; slice 4 checkbox ticked + comment with `cad526f` |
