# Wellness FIT Extraction Audit (PR #470) — Closing Handoff

**Session:** Audited the wellness FIT field mappings against Andy's Jun 2 calibration data (3rd reference day), retracted one wrong mapping, locked a new one, and extracted 4 metrics whose values had been sitting unparsed in `MonitoringMessage` standard attributes.
**Date:** 2026-06-07
**Predecessor handoff:** `V5_Implementation_Track2_SessionCountCeiling_Plan60Fix_2026_06_07_Closing_Handoff_v1.md` (Track 2 2b.2a — orthogonal track; this work continues the wellness arc from the earlier `V5_Implementation_Wellness_FIT_Ingestion_2026_06_07_Closing_Handoff_v1.md`)
**Branches / PRs (all merged to `main`):** `claude/wellness-fit-extraction-fixes` → #470 (`07f31e7`)
**Status:** 4 substantive files in scope (parser + route + template + tests); 1 PR shipped; full suite 2119 passed, 16 skipped post-merge.

---

## 1. Session-start verification (Rule #9)

Andy continued the wellness arc by dropping a 3rd day of FIT dumps (Jun 2) + Garmin Connect reference values. This is a `/wellness` follow-up, orthogonal to the Track 2 2b.2a work that landed in parallel. No anchor sweep against the Track 2 predecessor was required — different surface, different code. Verified `main` was on `c6963cd` (post-Track-2-2b.2a merge) before branching.

---

## 2. Session narrative

Andy provided Jun 2 reference data including a critical disconfirmation: he'd separately verified Garmin Connect's reported breath rate for Jun 2 was **12 brpm**, but my prior session's mapping had `[384] field_18` = sleep_avg_respiration based on May 28's coincidental 13/13 match. Jun 2's field_18 was **70** — way too high for respiration, and the 13 / 49 / 70 spread tracked inversely with sleep quality scores (96 / 65 / 58). Mapping retracted.

Andy then made a key observation: **all his uploaded files are the four known types (`_WELLNESS` / `_METRICS` / `_SLEEP_DATA` / `_HRV_STATUS`)** — there's no separate `_SPO2_DATA.fit` / `_TRAINING_STATUS.fit` from this Fenix 8. So the "missing" metrics must be in fields we're not extracting from the existing files.

That reframed the problem: the unmapped metrics (floors / intensity minutes / SpO₂) were almost certainly in `MonitoringMessage` standard attributes — the parser pulls only 5 (`steps` / `active_calories` / `active_time` / `distance` / `activity_type`), but FIT's `MonitoringMessage` typically carries `ascent` / `descent` / `moderate_activity_minutes` / `vigorous_activity_minutes` / `pulse_ox`. Extended `parse_wellness_daily_extras` to harvest them.

Spot-checked Jun 2's new METRICS files: 3 separate files for the same day with **acute_training_load 95 (morning) → 107 (midday) → 126 (evening)**. The bulk importer was UPSERTing in `_iter_fit_blobs` order (= zip filename order, NOT chronological), so an earlier ATL could clobber the latest. Fixed with a pre-pass + sort by `time_created_ms`.

Lastly identified a new locked mapping: `_SLEEP_DATA.fit` `GenericMessage[382] field_1` = restless_moments (May 28 = 28 ✓ vs Connect's "28 Restless Moments").

---

## 3. File-by-file edits

### 3.1 `garmin_fit_parser.py` (modified — substantive)

- **Retracted** the `[384] field_18` → `sleep_avg_respiration` mapping. Updated the module-level mapping comment to document the disconfirmation. `parse_metrics_fit` no longer reads field_18.
- **New** `_SLEEP_DATA_EVENTS_MSG = 382` constant + `parse_sleep_data_fit` branch to read `field_1` → `restless_moments`.
- **Extended** `parse_wellness_daily_extras` to walk every `MonitoringMessage` and capture: `MAX(ascent)` → `floors_climbed`; `MAX(descent)` → `floors_descended`; `MAX(moderate_activity_minutes) + 2 × MAX(vigorous_activity_minutes)` → `intensity_minutes`; opportunistic `pulse_ox` / `current_pulse_ox` / `spo2` attribute lookup → `spo2_avg` / `spo2_low`. Cumulative attributes use a running max (not sum) since they're already per-day running totals.
- **New** `fit_file_meta(fit_bytes)` helper returns `(kind, time_created_ms)` in a single parse pass. Old `detect_fit_type` is preserved as a back-compat wrapper.

### 3.2 `routes/garmin.py` (modified — substantive)

- **`_DAILY_METRICS_COLUMNS`** adds 4 new column names (`restless_moments`, `floors_climbed`, `floors_descended`, `intensity_minutes`). `sleep_avg_respiration` stays in the tuple but with a comment marking it as retired (old rows linger, new uploads don't touch it).
- **`_metrics_to_db_fields`** drops the `sleep_avg_respiration` key and adds the 4 new ones.
- **`import_wellness_bulk`** restructured: pre-pass calls `fit_file_meta` once per file to collect `(time_ms, name, raw, kind)` tuples → `pending.sort(key=lambda p: p[0])` → main pass dispatches in chronological order. Wellness-extras pass-through now also covers floors / intensity / spo2 columns.

### 3.3 `routes/wellness.py` (modified — substantive)

- The `garmin_daily_metrics` SELECT pulls 6 additional columns: `restless_moments`, `floors_climbed`, `floors_descended`, `intensity_minutes`, `spo2_avg`, `spo2_low`.
- `_build_chart_data` adds 4 new keys: `restless_moments`, `floors` (with `climbed` / `descended`), `intensity_minutes`, `spo2` (with `avg` / `low`). `active_minutes` (the Phase-B scaffold key) is removed — `intensity_minutes` now ships with real data.
- Brittle `r['sleep_score'] is not None` access in the sleep_score device builder was replaced with `_maybe_series` so test fixtures don't have to enumerate every column.

### 3.4 `templates/wellness/index.html` (modified — substantive)

- New cards: Restless moments (per-night bar chart), Floors (climbed + descended bars), Intensity minutes (bar), SpO₂ (avg + low line overlay with `min: 70, max: 100` axis).
- Phase-B "active & intensity minutes" scaffold card replaced with the real `intensity_minutes` card (no more "will appear once `_METRICS.fit` ingestion lands" placeholder).

### 3.5 `init_db.py` (modified — bookkeeping)

Four `ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS` lines for the new columns. All nullable. Andy ran the Neon migration via the SQL editor and verified via `information_schema.columns` — all 33 columns now present, nullability correct.

---

## 4. Code / tests

**Net test delta: +11 new tests, 2 modified.** Full suite 2119 passed / 16 skipped post-merge, up from 2106 / 16.

- `tests/test_wellness_phase_b_daily_metrics.py` — 11 new tests covering: restless moments surfacing (May 28 = 28 reference value); floors climbed/descended two-series shape (May 30 = 10/15, Jun 2 = 8/5); intensity minutes (May 30 = 5, Jun 2 = 204); SpO₂ overlay shape; `sleep_avg_respiration` no longer written (verifies the retirement); `_metrics_to_db_fields` pass-through for the 6 audit columns; `fit_file_meta` raise contract on garbage + happy-path round-trip with a synthetic `FileIdMessage`; chronological sort key verification using stand-in tuples in the Jun 2 ordering.
- `tests/test_wellness_chart_data.py` — updated the `active_minutes` empty-scaffold assertion (now retired since `intensity_minutes` ships with real data).
- `tests/test_wellness_phase_b_daily_metrics.py` — updated the `active_minutes` scaffold assertion the same way.

---

## 5. Manual §5.0 verification steps

1. **Neon migration:** Andy ran the idempotent ALTER block in the SQL editor; verified the 33-column schema in `information_schema.columns`. **DONE.**
2. **Live verification (owed):** upload Andy's full May 27 / 28 / 30 / Jun 2 dump on prod. Expected on `/wellness`:
   - Restless moments card: 28 (May 28), 15 (May 30), 32 (Jun 2).
   - Floors card: 10/15 (May 30), 8/5 (Jun 2).
   - Intensity minutes card: 5 (May 30), 204 (Jun 2).
   - SpO₂ card: populates if `MonitoringMessage.pulse_ox` is exposed on Fenix 8; otherwise stays absent (= signal that the attribute isn't on the typed message and we need to look elsewhere).
   - Acute training load (Jun 2): **126**, not 95 or 107 (proves the chronological sort fix).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Issue #283** stays open with documented remainders that all need *new* data, not new code:

- **Sleep stage Deep / Light / REM minute split.** `[384] field_5 / field_6 / field_7` are large packed values (May 28: `23412736 / 11425109 / 3543590`; May 30: `7165269 / 35711660 / 3440511`; Jun 2: `9797632 / 36590932 / 2558531`). Across 3 days the encoding still doesn't decode against any single-byte / double-byte / scaled-minute pattern. Would need a 4th day with *materially* different stage durations (e.g. a night with mostly deep + minimal REM) to crack.
- **Sub-score contributor positions** in `[346] field_5/7/8/9/10/14`. Garmin Connect labels them qualitatively ("Good" / "Excellent") and across May 28 / 30 / Jun 2 they didn't diverge enough to nail Light vs REM individually. Need a night where Connect rates one specifically "Poor" while others stay "Good".
- **`[384] field_18` mystery.** We *know* it tracks inversely with sleep quality (13 / 49 / 70 vs scores 96 / 65 / 58) but don't have a name. Most likely candidates: sleep onset latency in minutes, pre-sleep stress index, or restless-moments count (no — that's `[382] field_1`). Could ask Andy to check Connect for "Time to fall asleep" or similar.
- **Training readiness / VO₂max / fitness age.** Andy verified his Fenix 8 doesn't emit `_TRAINING_STATUS.fit` / `_SPO2_DATA.fit` / etc. — only the 4 known file types. So if these are tracked at all they're in unmapped fields. May genuinely not be on this watch model.

### 6.2 Alternative pivots

- **Plan-gen go-live track.** The predecessor (Track 2 2b.2a, PR #465) shipped the session-count ceiling fix for plan #60. Cold #60 re-run is owed Andy's-hands as the proof. Plus slice 2b.2b (athlete-fields onboarding + Neon migration) and #469 (lb/kg unit toggle) are open backlog.
- **Wellness page polish.** With 22 chart cards now, the page is getting long. Could add a "what changed" headline strip (e.g. "Resting HR up 2 bpm from 7-day baseline"), or collapse less-used cards behind a disclosure.

### 6.3 Operating notes for next session

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

The wellness arc is on its 5th PR now (#460 / #463 / #466 / #467 / #470). Field mapping refinements have a clear pattern: each new calibration day either confirms or disproves the previous session's locks. **Don't extend the parser to surface a field's value without two-day disconfirmation** — that's what got us field_18 last time. The 2-day verification pattern is documented in each parser's module-level constants.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Retract sleep_avg_respiration rather than try to salvage it | Claude | The 13/49/70 vs 96/65/58 inverse correlation is the OPPOSITE of what respiration should track — disconfirmation is unambiguous. |
| 2 | Keep `sleep_avg_respiration` *column* in schema (mark retired in code, don't DROP) | Claude | Old rows from PRs #460/#463/#466 may have wrong data, but the `/wellness` page reads respiration from `wellness_log` not from this column, so the bad data isn't displayed. Avoids a destructive DDL. |
| 3 | SpO₂ via opportunistic `MonitoringMessage` attribute lookup, not a dedicated parser | Claude | Andy verified no `_SPO2_DATA.fit` from his watch; opportunistic capture is the minimum-speculation approach. If the attribute isn't exposed on Fenix 8's typed message the columns stay null — that's the diagnostic signal we want. |
| 4 | Chronological sort via pre-pass + `fit_file_meta` helper, not "GREATEST" UPSERT semantics per-column | Claude | Per-column monotonic-merge is correct *only* for monotonic metrics (ATL increases through the day), but wrong for sleep_score (latest = current = correct, not maximum). Chronological order is universal and correct for every field. |
| 5 | Replace the `r['sleep_score'] is not None` brittle access with `_maybe_series` | Claude | The helper already existed for the other columns; consistency + test-fixture portability. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| PR #470 merged to `main` | ✅ `git log --oneline` shows `07f31e7` |
| Neon `garmin_daily_metrics` has all 33 columns | ✅ Andy ran the SQL editor verification |
| `parse_metrics_fit` no longer references field 18 | ✅ grep `field_18` in `garmin_fit_parser.py` returns only the retirement comment |
| `fit_file_meta` exposed + `detect_fit_type` still works (back-compat) | ✅ both importable from module |
| `[382] field_1` → `restless_moments` lands in `parse_sleep_data_fit` | ✅ grep `_SLEEP_DATA_EVENTS_MSG` |
| Test suite green | ✅ 2119 passed / 16 skipped |
| Working tree clean | ✅ `git status` on main pre-handoff-branch |

---

## 9. Files shipped this session

**Substantive (4 files):**
1. `garmin_fit_parser.py` — field_18 retirement, `[382] field_1` lock, MonitoringMessage attribute harvest, `fit_file_meta` helper
2. `routes/garmin.py` — new columns in `_DAILY_METRICS_COLUMNS`, `_metrics_to_db_fields` update, chronological pre-pass + sort
3. `routes/wellness.py` — SELECT new columns, build chart_data series for 4 new metrics, `_maybe_series` for sleep_score device
4. `templates/wellness/index.html` — 4 new chart cards, retired the active_minutes scaffold

**Bookkeeping (3 files):**
5. `init_db.py` — 4 new `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
6. `tests/test_wellness_phase_b_daily_metrics.py` + `tests/test_wellness_chart_data.py` — +11 new tests, 2 scaffold updates
7. This handoff + `CURRENT_STATE.md` pointer update + #283 status comment

5-file ceiling: 4 substantive, respected.

---

## 10. Carry-forward updates

None this session.

---

**End of handoff.**
