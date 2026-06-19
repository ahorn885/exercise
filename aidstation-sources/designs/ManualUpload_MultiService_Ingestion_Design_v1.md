# Multi-Service Manual Upload Ingestion — Design v1

**Status:** ratified (2026-06-19, Andy). Follows #757 (Garmin wellness →
Layer-3A). Goal: let an athlete feed Layer-3A from **file exports** of services
whose live API/webhook isn't connected (or doesn't exist), the way Garmin `.fit`
upload already works.

> **Correction (2026-06-19, Andy) — slice 3 retired.** During slice-3 scoping
> the premise broke: **neither Polar nor COROS offers a wellness *file* to
> upload.** Polar's "export all your data" (GDPR) ZIP **omits sleep + nightly
> recharge** — those are algorithm-derived and live **only** behind the
> AccessLink API (confirmed: Polar support "activity and sleep information are
> not included in the exported file"; intervals.icu users report the export
> carries activities but no sleep/recharge). COROS wellness is app-only (§3) —
> no export file either. Both providers' wellness already flows in via their
> live webhooks (`routes/polar_ingest.py`, `routes/coros_ingest.py`), so there
> is **no artifact to parse and nothing to build**. Slice 3 is closed
> `not_planned` on #767. The wellness-upload value moves to **slice 4 (Whoop)** —
> the only non-Garmin service with a real single-file wellness export
> (`physiological_cycles.csv`). See the per-section notes below.

**Ratified decisions:** slice order as in §7 (FIT-generalize first); Strava gets
a dedicated `cardio_log.strava_activity_id` column (§4.3); Whoop wellness
extends `WellnessSource` with priority garmin > whoop > polar > coros (§6).
**Groundwork landed this session:** `strava_activity_id` column +
`WorkoutSource`/`_detect_workout_source` Strava support (the foundation every
activity-upload slice writes to). Importer-generalization + parsers are the
remaining slices.

## 1. Purpose + problem

Today only **Garmin** has a manual-file path (`/garmin/import*` → `parse_fit` →
`cardio_log` / `daily_wellness_metrics` / `wellness_log`), independent of any
API. Polar/COROS are **webhook-only** (`provider_raw_record`); Strava/Whoop are
unwired OAuth stubs. When those connections are down or unavailable, the
athlete's exported data can't get in — including the sleep/HRV/RHR that now
feeds the coalesced `recent_wellness` record.

This design specifies a general manual-upload subsystem: which formats, where
each lands, how source-tagging + dedup work, and the one contract change it
forces.

## 2. Scope / boundaries

**In:** file-export ingestion for COROS, Polar, Wahoo, Strava, Whoop into the
tables Layer-3A already reads (`cardio_log`, `provider_raw_record`,
`daily_wellness_metrics`), reusing existing write helpers and readers.

**Out:** new live OAuth/webhook wiring (separate track); changing Layer-3A
readers beyond the one `WellnessSource` extension (§6); plan-file imports
(`wahoo_plans`/`coros_plans` retained but not in scope); any LLM prompt change
(activities + wellness flow through existing renders — `recent_workouts` and
`recent_wellness` are already rendered).

## 3. Export-format landscape (what each service actually offers)

| Service | Activity export | Wellness export (sleep/HRV/RHR) |
|---|---|---|
| Garmin | FIT ✓ done | FIT ✓ done |
| COROS | FIT / TCX / GPX per activity | thin (app-only) |
| Polar | TCX / GPX / CSV per session; GDPR JSON bundle | **none in any export** — sleep/recharge are algorithm-derived, AccessLink-API-only (the GDPR ZIP omits them; corrected 2026-06-19) |
| Wahoo | FIT per activity | none |
| Strava | bulk archive: original FIT/GPX/TCX + `activities.csv` | none |
| Whoop | CSV (workouts) | **CSV ✓ — recovery (HRV+RHR) + sleep** |

**Two orthogonal efforts fall out of this:**
- **A. Activities → `cardio_log`** (feeds `recent_workouts` + ACWR). FIT is
  common; TCX/GPX cover the rest. No wellness.
- **B. Wellness → `recent_wellness`** (sleep/HRV/RHR). Bespoke per platform;
  **Whoop CSV is the only rich non-Garmin single-file source** — and, per the
  2026-06-19 correction, the *only* non-Garmin wellness source with an uploadable
  file at all (Polar/COROS wellness is webhook-only, no export file).

## 4. Architecture

### 4.1 Where uploaded data lands (matches the existing readers)

| Data | Table | Reader | Source tag |
|---|---|---|---|
| Activities (any service) | `cardio_log` | `q_layer3A_recent_workouts` (`_detect_workout_source` reads the provider-id column) | write the dedup hash into the matching id column (`polar_exercise_id` / `coros_label_id` / `wahoo_workout_id`; Strava → see §4.3) |
| Polar/COROS wellness | `provider_raw_record` (`data_type` ∈ sleep/hrv/daily_summary) | `q_layer3A_recent_wellness` | provider column |
| Garmin wellness | `daily_wellness_metrics` | `q_layer3A_recent_wellness` | garmin |
| Whoop wellness | **decision in §6** | — | whoop (new) |

**Principle:** uploaded data must be indistinguishable to Layer-3A from
webhook/API data of the same provider — same table, same source tag — so no
reader changes are needed (except the Whoop contract extension). Reuse
`_record_raw` (polar/coros) and `_upsert_garmin_daily_metrics` verbatim.

### 4.2 Source tagging

`_detect_workout_source` infers the provider from which `*_id` column is
populated. So an uploaded Polar TCX must write its dedup key into
`polar_exercise_id`, not `garmin_activity_id`. Generalize `_fit_dedup_id`'s
`'fit:'` convention to a per-provider `'<provider>-file:'` prefix written to the
provider's id column, keeping it collision-free with real API ids.

### 4.3 Dedup

Content-hash of the file bytes (the existing `_fit_dedup_id` pattern), written
to the provider id column, `ON CONFLICT` skip. Covers re-dropping the same
export/zip. **Cross-source dedup** (same ride exported from both Strava and
Garmin) is explicitly *out* — the LLM already arbitrates duplicate workouts, and
provider-id columns differ so the UNIQUE keys won't collide. Strava archives
carry original device files (often FIT) → tagged `source='strava'` via the
dedicated **`cardio_log.strava_activity_id`** column (added this session) with a
`strava-file:<hash>` dedup key, ranked last in `_detect_workout_source` so a
co-present native-device id wins.

### 4.4 Routing / UI

One generalized upload entry point rather than five bespoke routes: extend the
connections-page drop zone to a **provider + file-type picker** (provider chosen
explicitly; format sniffed from extension/content). Dispatch:
`.fit`→`parse_fit`; `.tcx`/`.gpx`→new XML parser (§5); `.csv`→provider-specific
CSV parser (§5); `.zip`→expand and route each entry. Reuse the existing
preview→confirm flow where it adds value; bulk/no-preview for wellness.

## 5. Parsers to build

- **TCX** (XML): `<Activity Sport>`, `<Lap>`, `<Trackpoint>` (time, HR, distance,
  cadence, power ext). → activity dict shaped like `parse_fit`'s output so the
  `cardio_log` writer is unchanged. Polar/COROS/Strava activities.
- **GPX** (XML): track points + extensions (HR/cadence/power via Garmin TPX
  namespace). Thinner than TCX (often no summary) — derive duration/distance
  from trackpoints.
- **Whoop CSV**: map `recovery.csv` (HRV ms, RHR bpm) + `sleep.csv` (duration) →
  per-day wellness rows. The highest-value wellness parser.
- **Strava `activities.csv`**: index/metadata; actual streams come from the
  archived original files.

Each parser emits the **same normalized dict shape** the FIT path already
produces, so the DB-write + dedup + provider-raw recording stay shared.

## 6. The one contract change (Trigger #3 — needs ratification)

`recent_wellness` coalesces `WellnessSource = Literal["garmin","polar","coros"]`.
Whoop wellness (the marquee value of effort B) requires **extending
`WellnessSource` to include `"whoop"`** plus:
- the coalesce priority tuple (where does whoop rank? proposed: garmin > whoop >
  polar > coros, since Whoop is a dedicated recovery device — **open**),
- a reader source for Whoop in `q_layer3A_recent_wellness` (land Whoop in
  `provider_raw_record` under `data_type='sleep'`/`'hrv'` so it reads like Polar,
  **or** a `whoop`-specific branch),
- spec updates (Layer3_3A §5.1/§6.1, Integration §10), and
- the prompt render already handles it (provenance is just a tag) — **no prompt
  body change**, so not Trigger #1.

Polar/COROS/Wahoo manual uploads need **no** contract change (existing sources).

## 7. Sequencing (proposed slices, each ≤5 substantive files + tests)

1. **FIT source-generalize** — let the importer tag a chosen source → `cardio_log`
   with `<provider>-file:` dedup. Covers COROS/Wahoo/Strava-from-FIT activities.
   Reuses `parse_fit`. No new format, no contract change. *(Cheapest real win.)*
2. **TCX/GPX activity parser** — Polar/Strava per-session exports → `cardio_log`.
3. ~~**Polar/COROS wellness upload** — GDPR/app exports → `provider_raw_record` via
   `_record_raw`.~~ **RETIRED (2026-06-19, `not_planned`):** no wellness export
   file exists for either provider (Polar GDPR ZIP omits sleep/recharge; COROS
   wellness is app-only). Both already ingest via their live webhooks — nothing
   to parse. See the top-of-doc correction.
4. **Whoop CSV wellness** — `recovery.csv`+`sleep.csv` → `recent_wellness`;
   includes the §6 `WellnessSource` extension. *(Highest wellness value.)*
5. **Unified upload UI** — provider+format picker, zip expansion, preview/bulk.

## 8. Caching / invalidation

New `cardio_log` / `provider_raw_record` / `daily_wellness_metrics` rows already
invalidate Layer-3A via the day-keyed recency windows + the integration-bundle
hash (the #757 path). Manual uploads ride the same invalidation — no new wiring.
`updated_at`/`fetched_at = NOW()` on write means an upload correctly wins the
freshest-non-null coalesce.

## 9. Edge cases

- Re-dropped same file / zip → content-hash dedup skips.
- Wellness export with partial fields (sleep-only) → COALESCE upsert preserves
  other columns (existing `_upsert_garmin_daily_metrics` behavior; replicate for
  any new wellness writer).
- TCX/GPX with no power/HR → null columns, not failure.
- Timezone: export day boundaries vary; key `provider_raw_record.external_id` /
  `daily_wellness_metrics.date` on the export's local date as the webhook path does.
- Strava archive provider attribution ambiguity → fall back to `manual`.

## 10. Open items

- ~~Strava activity source tagging / dedup column~~ — **resolved:** dedicated
  `cardio_log.strava_activity_id` added this session.
- ~~Whoop coalesce priority rank~~ — **resolved:** garmin > whoop > polar > coros.
  Landing table still open: reuse `provider_raw_record` (`provider='whoop'`,
  `data_type='sleep'`/`'hrv'`) read by a whoop branch in `q_layer3A_recent_wellness`
  (recommended — mirrors Polar) vs a dedicated table.
- ~~Polar GDPR JSON bundle schema still needs a real export sample to map~~ —
  **moot (2026-06-19):** the Polar export omits sleep/recharge entirely (not a
  schema-unknown, an absence), so there is nothing to map. Slice 3 retired.
- Whether to surface uploaded-but-unconnected providers on the connections page
  as "file-import only."

### 10.1 Verified online sample sources (Andy has no personal exports)

Andy lacks personal exports for the non-Garmin formats, so parser slices build
against these public samples (fetch + commit as `tests/fixtures/` alongside the
parser that consumes them — not committed yet to avoid unused fixtures):

- **TCX:** `aaron-schroeder/activereader` (`testdata.tcx`), `dblock/tcx`,
  `mlt/schwinn810` wiki — running activities with HR/cadence/power trackpoints.
- **GPX:** Garmin TPX-extension samples in the same TCX repos + standard GPX
  track exports.
- **Whoop CSV:** `Philipp0205/whoop-dashboard` + `rowesk/Whoop-Data-Downloader`
  — export bundle is `physiological_cycles.csv` (recovery score, **HRV ms**,
  **resting HR**, strain) + `sleeps.csv` (duration/stages) + `recoveries.csv` +
  `workouts.csv`. `physiological_cycles.csv` is the row-per-day source for
  `recent_wellness` (HRV + RHR + sleep summary in one file).

## 11. Test scenarios

Per slice: parser unit tests (golden export → normalized dict); writer tests
(correct table + source tag + dedup skip on re-upload); a Layer-3A integration
test that an uploaded Polar TCX shows up in `recent_workouts` with
`source='polar'`, and (slice 4) an uploaded Whoop recovery row shows up in
`recent_wellness` with `hrv_rmssd_ms_source='whoop'`.

## 12. Gut check

- **Biggest risk:** scope sprawl — five services × three formats × two data axes
  is large. The slicing (§7) keeps each PR small and independently shippable;
  start with FIT-generalize which needs zero new parsing.
- **Best argument against building all of it:** activity uploads (effort A) feed
  ACWR, which already works from manual `cardio_log` entries — the *marginal*
  coaching value over a manually-logged workout is the rich streams, not the
  existence of the workout. **Effort B (wellness, esp. Whoop) is where manual
  upload unlocks data we otherwise can't get** — so if forced to pick, wellness
  > activities for coaching impact, even though activities are cheaper to build.
- **What might be missing:** real export samples. Several parsers (Polar GDPR
  JSON, Whoop CSV, COROS TCX) should be built against an actual file Andy
  exports, not a guessed schema (Rule #14). Recommend collecting one sample per
  target before building that slice.
