# V5 Implementation — #757 Unified Wellness + Manual-Upload Design — Closing Handoff (2026-06-19)

## 1. What shipped

Two things, on branch `claude/provider-translation-consolidation-3nw84k`:

1. **#757 — Garmin → Layer-3A unified wellness record (PR #763, MERGED to `main`).**
2. **Manual-upload multi-service design ratified + Strava-id groundwork (PR #765, on the same branch — auto-merge armed).**

Full suite **2701 passed / 30 skipped**.

## 2. #757 (merged — for context)

Replaced the per-source `recent_sleep` / `recent_hrv` bundle lists with a unified
**`DailyWellnessRecord`** (`layer4/context.py`): one coalesced row per calendar
day merging `total_sleep_hours` / `hrv_rmssd_ms` / `resting_hr` across
garmin/polar/coros, each with a typed `*_source` provenance field.

- **Coalesce** (`q_layer3A_recent_wellness`, `layer3a/integration.py`):
  freshest-non-null per field — newest ingest ts wins (`daily_wellness_metrics.
  updated_at` / `provider_raw_record.fetched_at`), NULL/older never clobbers,
  ties break garmin>polar>coros (deterministic for the cache key).
- **Garmin** read from `daily_wellness_metrics` (sleep span via `sleep_end_ms -
  sleep_start_ms`, `hrv_overnight_avg_ms`, `resting_hr`). `resting_hr` is
  garmin-only.
- **Self-report** kept separate (`recent_self_report_sleep` →
  `q_layer3A_recent_self_report_sleep`) to preserve §6.1 weighting.
- **Prompt render** (`layer3a/builder.py`, Trigger #1, ratified): per-metric
  latest + provenance + 14d-avg + count, suppress-on-empty; §4 objective bullet
  gained resting HR + HRV. **LLM output schema kept stable** (data_density
  counts) — bounded blast radius. §6.2 Floor 3 now reads `recent_wellness`.
- Specs: Layer3_3A §5.1/§6.1/§6.2, Integration §10. Design:
  `designs/ProviderTranslation_UnifiedWellnessRecord_757_Design_v1.md`.

**Verified:** manual Garmin `.fit` upload (`/garmin/import-wellness` →
`_metrics_to_db_fields` → `_upsert_garmin_daily_metrics`) populates exactly the
fields `recent_wellness` reads (`sleep_start/end_ms`, `hrv_overnight_avg_ms`,
`resting_hr`) with `updated_at=NOW()` → a manual upload wins the coalesce.

**Residual (#757 comment + CARRY_FORWARD):** `q_layer3A_connected_providers`
doesn't surface Garmin — Garmin auths via `garmin_auth`, not the `provider_auth`
that accessor reads — so garmin-only wellness informs coaching *state* but not
the §6.2 high-confidence Gate 1.

## 3. Manual-upload multi-service ingestion (this session)

**Design ratified:** `designs/ManualUpload_MultiService_Ingestion_Design_v1.md`.
Principle: uploaded data lands in the **same tables + source tags** the Layer-3A
readers already use, so readers need no change (except the Whoop `WellnessSource`
extension). Activities → `cardio_log`; Polar/COROS wellness → `provider_raw_record`
(`_record_raw`); Garmin → `daily_wellness_metrics`.

**Strava-id groundwork landed (PR #765):**
- `init_db.py`: `ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS strava_activity_id TEXT` (with the other provider-id migrations; auto-applies on deploy).
- `layer4/context.py`: `WorkoutSource = Literal[..., "strava"]`.
- `layer3a/integration.py`: `_detect_workout_source` adds a strava branch (ranked **last** — Strava archives carry other-device files); the `q_layer3A_recent_workouts` SELECT now includes `strava_activity_id`.
- `tests/test_layer3a_integration.py`: strava in `_workout_row` helper + `test_strava_source_detection` + extended priority/list tests.

## 4. Next slices (Rule #11 — mechanically-applicable pointers)

Tracked in **issue #767**. Build order:

1. **FIT source-generalize.** Parameterize `routes/garmin.py` `_bulk_insert_cardio(db, data, uid, gid, ...)` to also take a `source` and write `gid` to the matching id column instead of hardcoding `garmin_activity_id`:
   - map `source → (column, dedup-prefix)`: `garmin→garmin_activity_id/'fit:'`, `coros→coros_label_id/'coros-file:'`, `wahoo→wahoo_workout_id/'wahoo-file:'`, `polar→polar_exercise_id/'polar-file:'`, `strava→strava_activity_id/'strava-file:'`.
   - thread a `source` form field through the bulk-import endpoint (`/garmin/import/bulk` ~line 652) + UI (connections drop zone). Keep `_fit_dedup_id` but make the prefix a param.
   - Rule #15: log the chosen source + id-column per import.
2. **TCX/GPX parser** — new module emitting the **same normalized activity dict** `parse_fit` produces (so `_bulk_insert_cardio` is unchanged). TCX: `<Activity Sport>`/`<Lap>`/`<Trackpoint>` (time/HR/distance/cadence/power-ext). GPX: trackpoints + TPX extensions.
3. **Polar/COROS wellness upload** → `provider_raw_record` via `_record_raw` (data_type sleep/hrv/daily_summary). No contract change. Polar GDPR JSON needs a real sample first (§7).
4. **Whoop CSV wellness** — `physiological_cycles.csv` (HRV ms + resting HR + sleep) → `recent_wellness`. **Trigger #3:** `WellnessSource += "whoop"` in `layer4/context.py` + `_WELLNESS_SOURCE_PRIORITY = {"garmin":4,"whoop":3,"polar":2,"coros":1}` + a whoop read branch in `q_layer3A_recent_wellness` (land Whoop in `provider_raw_record` `provider='whoop'` so it reads like Polar) + spec updates (Layer3_3A §5.1, Integration §10). No prompt-body change (provenance is just a tag).
5. **Unified upload UI** — provider+format picker, zip expansion, preview/bulk.

## 5. Owed / live-verify

- **#757 residual:** `connected_providers` Garmin coverage (garmin_auth vs provider_auth). Small dedicated issue if/when reconciled.
- **#681 §4 Slice 3 live-verify** still owed (rename + bespoke drops; Andy-action, container can't reach Neon).
- Carried: post-#572 live T3 refresh re-verify; #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #698 Part A cardio_drills A2 (gated on Trigger-#1 wording); #732 parked.

## 6. Operating notes for next session

### 6.3 Read order (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session).
3. `CARRY_FORWARD.md` — #757 residual + the manual-upload track.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

Then pick up **issue #767 slice 1** (FIT source-generalize) — needs no samples and no contract decision; or **slice 4 (Whoop)** if wellness-into-coaching is the priority (Andy's gut-check: wellness > activities for impact).

## 7. Test samples (Andy has no personal exports)

Verified public samples (design §10.1): TCX `aaron-schroeder/activereader`
`testdata.tcx` + `dblock/tcx`; Whoop `Philipp0205/whoop-dashboard` /
`rowesk/Whoop-Data-Downloader` (`physiological_cycles.csv`); GPX standard
exports. **Polar GDPR JSON bundle has no public sample — ask Andy to export
one** before slice 3's Polar sub-part. Fetch + commit each as `tests/fixtures/`
alongside the parser that consumes it (not committed yet — avoid unused
fixtures).

## 8. Verification table (Rule #10 — inputs to next session's Rule #9 sweep)

| Claim | File | Anchor / check |
|---|---|---|
| Strava id column | `init_db.py` | `grep "strava_activity_id" init_db.py` → ALTER migration present |
| WorkoutSource += strava | `layer4/context.py` | `grep 'WorkoutSource = Literal' ` → ends `"coros", "strava"]` |
| Source detection | `layer3a/integration.py` | `_detect_workout_source` has `row["strava_activity_id"]` branch; SELECT includes `strava_activity_id` |
| Strava test | `tests/test_layer3a_integration.py` | `test_strava_source_detection` present |
| #757 unified record | `layer4/context.py` | `class DailyWellnessRecord` present (merged via #763) |
| Manual-upload design | `aidstation-sources/designs/ManualUpload_MultiService_Ingestion_Design_v1.md` | exists; status "ratified" |
| Suite | — | `python -m pytest tests/ -q` → 2701 passed / 30 skipped |
