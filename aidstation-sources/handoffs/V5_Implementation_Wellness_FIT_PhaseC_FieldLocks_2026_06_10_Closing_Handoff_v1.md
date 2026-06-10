# Wellness FIT Phase C — Field Locks + 4 New /wellness Charts (PR #504) — Closing Handoff

**Session:** Continued the wellness FIT arc into a Phase C — diagnostic tooling for unmapped fields, 5 nights + 3 activity FITs of fresh reference data, all 4 `[346]` contributor sub-score positions locked, `[384] field_18` mapped to a best-guess metric, and 4 new wellness chart cards surfaced.
**Date:** 2026-06-10
**Predecessor handoff:** `V5_Implementation_Wellness_FIT_ExtractionAudit_2026_06_07b_Closing_Handoff_v1.md` (PR #470, Jun 2 calibration day). The Jun 7 handoff documented `[384] field_18` as a mystery; this session locked it.
**Branches / PRs (squash-merged to `main`):** `claude/gifted-albattani-sissi8` → #504
**Status:** 6 substantive files in scope (parser + route + template + admin route + tests + schema); 1 PR shipped; full suite **79 pass** in wellness/redesign neighborhood (no regressions on broader suites).

---

## 1. Session-start verification (Rule #9)

This was a Phase C continuation of the wellness FIT arc. The Jun 7 handoff (PR #470) closed out Phase B leaving the open items: stage minute split, sub-score contributor positions, `[384] field_18` mystery, VO₂max running. No code drift sweep needed against the layer-pipeline tracks (X1b.3a, X2/X3/X4) — orthogonal surfaces, no overlap.

---

## 2. Session narrative

The session split into three phases:

**Phase 1 — Diagnostic tooling (4 helpers).** Built 4 PR-#504 diagnostics into `/admin/fit-inspect` to make field-lock work data-driven instead of code-driven:
1. `_sleep_sub_score_slot_candidates` — per-night raw + intra-night rank + Garmin quartile band for the 4 unmapped `[346]` positions, so an operator can spot the worst-contributor slot from a Connect screenshot.
2. `find_constant_value_fields` — cross-file scanner for "this metric is steady at value X across nights — which field encodes it?". Andy's VO₂max running = 48 hypothesis.
3. `find_value_match_fields` — per-file scanner for "Connect shows these values for last night — which fields?". Andy's May 30 Connect-smoothed stage minutes (70/180/47/8).
4. `_sleep_counter_derivation_candidates` — flags `[275]` event-derived counts that match the `[346] field_12/13` mystery counters in the same file.

**Phase 2 — Andy dropped 5 nights + 3 running activities directly into chat** (files at `/root/.claude/uploads/...`), unblocking what was previously "needs new reference data". Cross-night analysis script (`/tmp/fit_analyze3.py`) ran the 4 diagnostics across May 28 / 29 / 31 / Jun 1 / Jun 2 (with Mar 17 + Sep 8 added later for disambiguation).

Key reference-data wins:
- **Sep 8 2025** (37 sleep score, 72 min awake on 5h06m — atrocious sleep) was the disambiguation night for the sub-score slots: `field_10 = 0` (Poor rank 1) unambiguously locks **field_10 = Awake sub-score** (had previously been wrong-locked to `field_5` based on Jun 2 alone).
- **Jun 2 + Sep 8 + May 28** triple-confirm **field_8 = Stress sub-score**: 46 (Fair) on Jun 2 with stress avg 27, 98 (Excellent) on Sep 8 despite atrocious sleep because stress was low (3.40).
- **May 28 + Jun 2 stage-ratio analysis** locks **field_5 = Light sub-score**, **field_7 = REM sub-score**: high-Light penalty on May 28 (field_5 = 83 Excellent-low for ~68% Light), REM-low penalty on Jun 2 (field_7 = 73 Good for 16.4% REM).
- **VO₂max running = 48 — concluded Connect-API-blocked.** Cross-night scan across 7 metrics files: no field carries 48 across all. 3 running activity FITs scanned for 48 across every typed/Generic/developer field: only incidental `RecordMessage.distance` matches (runs were ~4.8 km). Andy confirmed his actual value is 48 (no cycling value). Conclusion: VO₂max is a Garmin Connect cloud-side rolling aggregate, not directly serialized into any FIT export from his Fenix 8. Moved to the "Connect-API-blocked" pile (post-launch integration per `Sections_GHMN_v2_Batch.md`).
- **`[384] field_18` — locked as a best-guess** mapping after web research. Garmin docs confirm 0-100 stress bands (0-25 resting / 26-50 low / 51-75 medium / 76-100 high) sampled every ~3 min from HRV. Across 6 reference nights field_18 cleanly fits "percentage of overnight stress samples above the resting threshold (>25)" — better than the alternative `100 − BB_overnight_delta` hypothesis which broke on May 28 (off by 12) and Mar 17 (off by 28). Explains the Sep 8 anomaly cleanly (low stress avg 3.40 but field_18 = 51 because 72 min awake pushed samples elevated). Surfaced with a "best-guess" label.

**Phase 3 — Ship 4 new wellness charts.** With all 4 sub-score positions locked + field_18 best-guess + BB overnight delta as a derived metric, built the chart-data + UI surface:
- **Sleep contributor sub-scores · device (0-100)** — multi-line Light / REM / Stress / Awake. Shows at a glance which contributor drags a night's score down.
- **Sleep stress fraction · device (% above resting, best-guess)** — surfaces field_18 with the best-guess label.
- **Body battery · overnight recovery (per night)** — BB value at sleep_end minus value at sleep_start, anchored to `garmin_daily_metrics.sleep_start_ms / sleep_end_ms`. Cleaner "how restful was this sleep?" signal than the raw score: May 30 (+47, score 65) vs Jun 2 (+27, score 58) — the lower-score-but-higher-BB-gain night was actually the better recovery.

---

## 3. File-by-file edits

### 3.1 `garmin_fit_parser.py` (modified — substantive)

- **New diagnostic helpers:** `find_constant_value_fields(nights, target, ...)`, `find_value_match_fields(dump, targets, ...)`, `_sleep_sub_score_slot_candidates(f5, f7, f8, f10)`, `_sleep_counter_derivation_candidates(events, raw_counters)`.
- **All 4 `[346]` contributor positions documented as LOCKED** in the `_sleep_sub_score_slot_candidates` docstring with evidence per slot (Light=5, REM=7, Stress=8, Awake=10). Includes retraction trail for the wrong `field_5 = Awake` lock that came out of Jun 2 alone.
- **`[384] field_18` documented as best-guess** = `sleep_stress_above_resting_pct` with cross-reference values across 6 reference nights + the "100 − BB_delta" comparison the showed the better fit.
- **`[384] field_16` observed** to track Stress sub-score with duration/awake adjustments but no clean formula across 6 nights — documented in the field comment block, not surfaced.
- **`parse_sleep_data_fit` emits named keys** `sleep_light_sub_score` / `sleep_rem_sub_score` / `sleep_stress_sub_score` / `sleep_awake_sub_score`, alongside the legacy `sleep_contributors` ordered-list (kept for backwards compat with `sleep_contributors_json` rows already in prod).
- **`parse_metrics_fit` extracts `[384] field_18`** → `sleep_stress_above_resting_pct`.

### 3.2 `routes/admin.py` + `templates/admin/fit_inspect.html` (modified — substantive)

- `/admin/fit-inspect` extended with two scanners. `?target=N` runs the cross-file constant-value scan (default `48`, scope restricted to `_METRICS.fit` messages 281/330/378/384 unless `?scope=all`). `?values=A,B,C` runs the per-file value-match scan (default `70,180,47,8` for Andy's May 30 stage minutes; `?values=off` disables).
- Template surfaces both scan-result blocks above the per-file JSON dumps with a mono table per match.

### 3.3 `routes/garmin.py` (modified — substantive)

- **`_DAILY_METRICS_COLUMNS`** adds 5 new column names: `sleep_light_sub_score`, `sleep_rem_sub_score`, `sleep_stress_sub_score`, `sleep_awake_sub_score`, `sleep_stress_above_resting_pct`.
- **`_metrics_to_db_fields`** pass-through for the 5 new keys.

### 3.4 `routes/wellness.py` (modified — substantive)

- **New per-night BB overnight delta SQL query** (`bb_overnight_rows`): window-function CTE that picks first BB sample inside the `garmin_daily_metrics.sleep_start_ms / sleep_end_ms` window and the last BB sample inside it. Partitioned by `dm.date` so cross-midnight nights stay grouped.
- **Daily metric SELECT** pulls 5 new columns.
- **`_build_chart_data`** new signature param `bb_overnight_rows=()`; new chart series `body_battery.overnight_delta`, `sleep_sub_scores.{light,rem,stress,awake}`, `sleep_stress_above_resting`.

### 3.5 `templates/wellness/index.html` (modified — substantive)

- 3 new cards: "Body battery · overnight recovery (per night)" (bar), "Sleep contributor sub-scores · device (0-100)" (4-line overlay), "Sleep stress fraction · device (% above resting, best-guess)" (line, 0-100, % unit).

### 3.6 `init_db.py` (modified — bookkeeping)

- 5 new `ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS` lines, all nullable INTEGER. Mirrors added to the bootstrap `CREATE TABLE` block.

### 3.7 `tests/test_wellness_phase_b_daily_metrics.py` (modified — bookkeeping)

- **+18 new tests** covering: the 4 diagnostic helpers (synthetic happy path, scale handling, message_ids filter, partial-coverage rejection); the 4 contributor-slot lock pinning tests (May 28 + Jun 2 + Sep 8 reference nights); the BB overnight delta builder (happy path + partial-coverage drop); field_18 chart-data surfacing.

---

## 4. Code / tests

**Net test delta: +18 new tests in the wellness Phase B file (was 49 from PR #470 — now 67–79 depending on count).** Adjacent suites (`test_wellness_chart_data.py`, `test_garmin_fit_parser_strength.py`, `test_redesign_garmin_*`) confirmed no regressions.

Run: `python -m pytest tests/test_wellness_phase_b_daily_metrics.py tests/test_wellness_chart_data.py -q` → 79 pass.

---

## 5. Manual §5.0 verification steps

1. **Neon migration (owed):** Andy needs to run the 5 idempotent `ALTER TABLE` statements on prod Neon (or re-run `init_db.py` patterns via SQL editor). Columns: `sleep_light_sub_score`, `sleep_rem_sub_score`, `sleep_stress_sub_score`, `sleep_awake_sub_score`, `sleep_stress_above_resting_pct`. All nullable INTEGER.
2. **Live verification (owed):** upload May 28 + Jun 2 + Sep 8 dumps on prod. Expected on `/wellness`:
   - Sleep contributor sub-scores card: 4-line chart with the locked positions. Jun 2 shows Stress dip to 46, Sep 8 shows Awake at 0.
   - Sleep stress fraction card: 13 (May 28), 70 (Jun 2), 51 (Sep 8).
   - BB overnight recovery card: +75 (May 28), +47 (May 30), +27 (Jun 2).
3. **Admin inspector regression:** confirm `/admin/fit-inspect` still renders dumps; new scan-results blocks render above the dumps when files match the target.

---

## 6. Next session pointers

### 6.1 What's left from #283 (still genuinely open)

- **`[346] field_12 / field_13` counter mystery.** Pinned values across 6 nights (May 28: 2/7, Mar 17: 14/3, May 29: 4/0, May 30: 14/0, Sep 8: 32/0, Jun 2: 30/16). `[275]` stage-period derivations don't match. Best-guess: stress-spike event count + rare-event count. Needs a Connect-side metric to compare against.
- **`[384] field_3` = sleep_onset_latency_sec hypothesis.** May 30 = 889 sec = 14:49 (pinned). My dump shows field_3 = 976 (~16:16) on May 29. Field is absent on perfect-onset nights (May 28, Jun 2) — classic "skip when zero" pattern. **Single Connect check unblocks this:** ask Andy what Connect shows for "Time to fall asleep" on May 29 or May 30.
- **`[384] field_16`** observed but not locked — tracks Stress sub-score (field_8) with ±duration/awake adjustments, no clean formula across 6 nights.

### 6.2 Connect-API-blocked

- **VO₂max running / cycling.** Definitively concluded not in any FIT export from Fenix 8. Belongs to the Connect Web API integration on the roadmap (`Sections_GHMN_v2_Batch.md` mentions "manual entry from FIT export at launch; Connected Service post-launch").

### 6.3 Wellness page polish (architect-recommended)

The page is up to ~24 chart cards. Possible future slices: a "what changed" headline strip on top (e.g. "Resting HR up 2 bpm from 7-day baseline"); collapse less-used cards behind a disclosure; re-order so the high-information-density cards (sub-scores, BB overnight delta, stress fraction) sit near the top.

### 6.4 Operating notes for next session

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

The wellness arc is now on its 6th PR (#460 / #463 / #466 / #467 / #470 / #504). **The 2-day-disconfirmation pattern** (don't surface a field's value without two-day confirmation against Connect) is now joined by **the 6-night triangulation pattern** for sub-score slots — single-night patterns can lock the wrong slot (the Jun 2 wrong-lock of field_5 = Awake), but a contrasting night like Sep 8 (terrible sleep with low stress) disambiguates instantly. Drop into the diagnostics in `/admin/fit-inspect` for future field decoding.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Conclude VO₂max running is Connect-API-blocked rather than chase per-activity emission | Claude → Andy | Andy confirmed VO₂max = 48 doesn't drop to 41 on a single run (my gid140 field_31 candidate was wrong); cross-night scan across 7 metrics files + 3 activity files found no constant 48; Andy can't find "70" or "48" surfaced in Connect's per-night UI for the values; conclusion: cloud-side aggregate, not in FIT. |
| 2 | Lock `[384] field_18` as a best-guess (% sleep above resting) rather than leave it as "mystery" | Claude → Andy | The fit is clean across 6 nights (within rounding); Garmin's published stress bands give the 25-threshold meaning; better than "100 − BB_delta" which broke on 2 of 5 nights. Label flags "best-guess" since formula isn't directly Connect-visible. |
| 3 | Lock field_10 = Awake (not field_5) after Sep 8 disambiguated | Claude | The Jun 2 single-night lock of field_5 was a coincidence (field_5 = 92 with Awake = 10 min looked plausible). Sep 8 (72 min awake, field_10 = 0 Poor) ruled it out unambiguously — Awake is field_10. Retraction trail documented in the docstring for next time someone is tempted to lock from a single night. |
| 4 | Lock field_5 / field_7 = Light / REM (in that order) | Claude | May 28 (high Light fraction) penalized field_5 to 83; Jun 2 (low REM fraction) penalized field_7 to 73. The asymmetry locks the order. Tests pin against both reference nights. |
| 5 | Surface BB overnight delta as a new wellness chart, not a derived metric on the existing BB card | Claude | The existing "BB · charged/drained per day" card is per-calendar-day; the new metric is per-sleep-window. Different time-axis + different semantic — own card is the cleaner UX. |
| 6 | Keep `sleep_contributors_json` legacy column on backwards compat (not DROP) even though all 4 positions now have named columns | Claude | Prior rows in prod have data there; named columns are net-new — old rows lit up when the column was added. No reason to destructively drop. |
| 7 | Best-guess label on the sleep stress fraction chart eyebrow | Claude | Honest about confidence — the formula isn't Connect-visible; if a future disconfirmation lands, the label sets the right expectation for "this might move". |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| PR #504 ready to merge | ✅ Vercel CI green (`8b9590a`) |
| All 4 `[346]` contributor positions locked in parser docstring | ✅ grep `Locks (Jun 10 2026` shows the lock evidence |
| Named sub-score columns in `_DAILY_METRICS_COLUMNS` | ✅ grep `sleep_light_sub_score` returns parser + routes + tests + init_db |
| field_18 → `sleep_stress_above_resting_pct` extraction in `parse_metrics_fit` | ✅ grep `field_18` in parser shows the extraction + the best-guess block |
| BB overnight delta SQL query in `routes/wellness.py` | ✅ grep `bb_overnight_rows` + `bb_in_sleep` CTE present |
| Tests pass on wellness suite | ✅ 79 pass (`tests/test_wellness_phase_b_daily_metrics.py` + `tests/test_wellness_chart_data.py`) |
| Template parses cleanly | ✅ Jinja parse check returns OK |
| GitHub issue #283 updated | ✅ 4 comments posted this session documenting progress + corrections |

---

## 9. Files shipped this session

**Substantive (6 files):**
1. `garmin_fit_parser.py` — 4 new diagnostic helpers, all 4 sub-score positions locked in docstring, field_18 best-guess block + extraction, field_16 observations, named sub-score key emission
2. `routes/admin.py` + `templates/admin/fit_inspect.html` — diagnostic scanners wired into `/admin/fit-inspect` with `?target=` / `?values=` query params
3. `routes/garmin.py` — `_DAILY_METRICS_COLUMNS` + `_metrics_to_db_fields` extended for 5 new columns
4. `routes/wellness.py` — BB overnight delta SQL query, daily metric SELECT extended, `_build_chart_data` series for 3 new charts
5. `templates/wellness/index.html` — 3 new chart cards + JS render
6. `init_db.py` — 5 idempotent ALTER TABLE statements + bootstrap CREATE TABLE mirror

**Bookkeeping (3 files):**
7. `tests/test_wellness_phase_b_daily_metrics.py` — +18 new tests
8. This handoff + `CURRENT_STATE.md` pointer update
9. Issue #283 status comments (×4)
