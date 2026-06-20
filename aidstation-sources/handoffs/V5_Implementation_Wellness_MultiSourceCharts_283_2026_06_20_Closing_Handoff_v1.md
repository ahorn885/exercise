# V5 Implementation — Wellness Multi-Source Charts (#283 expansion) — Closing Handoff v1

**Date:** 2026-06-20
**Type:** Build (v1 app, `/wellness` dashboard). One branch, PR pending.
**Branch:** `claude/optimistic-keller-g5j1oe` (harness-pinned for this task).
**Issue:** [#283](https://github.com/ahorn885/exercise/issues/283) — "Wellness: device data not showing on multi-metric charts." Scope expanded by Andy: *"wire metrics from all external sources and our own internally-derived/captured metrics into the charts, not just Garmin."*

---

## §1 — Problem

The `/wellness` dashboard charted **only** Garmin (`wellness_log` per-second + `daily_wellness_metrics` daily) plus internal self-report / body / training. Everything else an athlete connects landed in `provider_raw_record` — **Polar** (sleep / nightly-recharge HRV / cardio-load), **COROS** (daily summary: rhr / ppg_hrv / steps / calories / sleep span), **Whoop** (daily cycle: sleep / HRV / resting HR / recovery / strain, the CSV track that *just* shipped #767 slices 4–5) — and **was never read by the chart builder.** The internal `body_metrics.vo2_max` was likewise ignored while a dead "VO₂max" scaffold sat empty.

So a non-Garmin athlete (or Andy testing the new Whoop CSV upload) saw blank charts — the live symptom on #283's Jun 17 comment ("uploaded data isn't reaching the charts"). The same Jun-17 Garmin symptom most-plausibly traces to the schema-init prod incident fixed in #742 (Jun 19, *after* the report) — unverifiable from the container (Neon egress blocked, Rule #14), and non-regressive under this change since Garmin still wins the coalesce.

## §2 — Decision (taken, not balloted — no stop-and-ask trigger)

Mirror the **Andy-ratified Layer-3A coalesce** (`layer3a/integration.py` `q_layer3A_recent_wellness`): for metrics several devices all report, coalesce **per (day, metric) by device priority — garmin>whoop>polar>coros>body** — so whichever device the athlete wears charts its value rather than leaving a Garmin-only blank. Charts and coaching state now agree on provenance. Garmin's richer native sub-metrics (HRV highest-5min, sleep sub-scores, body battery, stress zones) stay Garmin-only on their own cards. No schema change, no contract/cache/prompt change.

## §3 — Files (substantive: 2 code/template + 1 test)

- **`routes/wellness.py`** —
  - New `_provider_wellness_rows(db, uid, cutoff)`: 5 `provider_raw_record` SELECTs (Polar sleep / hrv / cardio_load, COROS daily_summary, Whoop daily_summary) with the same `raw_payload->>'…'` JSON extraction Layer-3A uses, normalised to a uniform per-row dict (sleep minutes → hours; COROS start/end ms span → hours). Called in `index()` inside a `try/except` that logs (Rule #15 `[wellness] provider_raw_record read failed`) and falls back to `[]` so a missing/empty provider table can never break the dashboard.
  - New module-level `_SOURCE_PRIORITY` + `_coalesce_series(candidates)` — per-date highest-priority-non-null winner → sorted `[{x,y}]`.
  - `_build_chart_data(…, provider_rows=())`: new keyword arg; a consolidated coalesce block builds candidate lists from `daily_by_date` (Garmin) + `garmin_rows` (wellness_log steps/cal) + `body_rows` (vo2_max) + `provider_rows`, then **overrides** `hrv.overnight`, `heart_rate.resting`, `daily_activity.steps`/`active_cal` and **adds** `sleep_hours_device`, `vo2max_running` (now live), `vo2max_cycling`, `recovery`, `strain`, `cardio_load{daily,acute,chronic}`.
  - SELECT widening: `body_metrics` += `vo2_max`; `daily_wellness_metrics` += `sleep_start_ms, sleep_end_ms, vo2max_running, vo2max_cycling`.
  - `_HEADLINE_METRICS` += `('recovery', 'Recovery', '', 'up')`. (`hrv.overnight` headline now works for any device for free.)
- **`templates/wellness/index.html`** — Sleep-hours card overlays device duration (self vs device); new cards (gated on data): **Recovery** (0–100), **Training strain** (0–21), **Cardio load** (Polar daily/acute/chronic); VO₂max run/bike cards now render (added the missing JS draw blocks + relabelled the dead "#283 pending" notes); `sleep_has` section-gate += `sleep_hours_device`; HRV empty-state copy mentions Polar/COROS/Whoop.
- **`tests/test_wellness_multisource.py`** (NEW) — 10 tests: `_coalesce_series` priority/null-skip; provider rows coalesce across sources (Garmin wins shared days, Whoop/COROS fill Garmin-blank days, Whoop RHR outranks COROS); Polar cardio-load; VO₂max from internal `body_metrics` (+ Garmin outranks manual); `_has_any_data` lights for a provider-only athlete; `_provider_wellness_rows` normalization via a fake DB (sleep-min→hours, COROS span→7h, all 5 queries bound to `(uid, cutoff)`).

**Bookkeeping (ceiling-exempt):** this handoff, `CURRENT_STATE.md`, `CARRY_FORWARD.md`, #283 comment.

## §4 — Verification

- Full Python suite **2838 passed / 30 skipped** (2828 baseline + 10 new). `routes.wellness` imports clean; `templates/wellness/index.html` Jinja-parses clean.
- Coalesce is non-regressive: every pre-existing `tests/test_wellness_chart_data.py` assertion still holds (Garmin-only inputs → identical series; resting-HR override path preserved; scaffold keys still empty on empty input).

## §5 — Manual verification owed (Andy)

- **Live-verify the expansion:** with Whoop CSV already uploaded (#767 slice-4/5 track), open `/wellness` → the **Recovery / Training strain / Sleep-hours "Device" / HRV** cards should now carry the Whoop days; if Polar/COROS are connected, their sleep/HRV/RHR/steps/recovery surface too. (Container can't reach Neon — this is the only proof for the data half, Rule #14.)
- **Optional diagnostic** to confirm the underlying #283 Garmin symptom is the #742 prod-incident (now fixed): a `neon-query` of `SELECT count(*) FROM daily_wellness_metrics WHERE user_id=<andy>` + same for `provider_raw_record` per provider. If Garmin rows exist and now chart, the residual #283 tail is closed.

## §6 — Next session pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Next moves:** (1) Andy live-verify §5. (2) Provider integrations & API thread (#681/#682) continues — this change is the read-side payoff of the `provider_raw_record` canonical store. (3) If a provider needs a metric not yet surfaced (Polar breathing rate, COROS sleep_avg_hr, Whoop sleep_performance_pct), it's a one-line add to `_provider_wellness_rows` + a card.

## §7 — Decisions pinned (this session)

| # | Decision | Pick |
|---|---|---|
| W-1 | Overlapping metrics (sleep/HRV/RHR/VO₂max/steps/cal) across devices | **Coalesce per-day by device priority** (garmin>whoop>polar>coros>body), mirroring Layer-3A — over per-provider overlay series (cleaner for a single-device-at-a-time athlete; never leaves a Garmin-only blank). |
| W-2 | Provider read failure on `/wellness` | **Log + fall back to `[]`** (dashboard must never 500 on a provider-table gap; the #742 incident class). |

## §8 — Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Provider reader | `routes/wellness.py` | `def _provider_wellness_rows` — 5 `provider_raw_record` SELECTs; `index()` wraps it in `try/except` → `[wellness] provider_raw_record read failed` |
| Coalesce | `routes/wellness.py` | `_SOURCE_PRIORITY = {'garmin': 4, 'whoop': 3, 'polar': 2, 'coros': 1, 'body': 0}` + `def _coalesce_series` |
| Builder wiring | `routes/wellness.py` | `_build_chart_data(…, provider_rows=())`; return dict carries `sleep_hours_device`/`recovery`/`strain`/`cardio_load`; `vo2max_running` no longer hardcoded `[]` |
| Template cards | `templates/wellness/index.html` | `chart-recovery`, `chart-strain`, `chart-cardio-load`, `chart-vo2-run`/`chart-vo2-bike` draw blocks; sleep-hours "self vs device" |
| Tests | `tests/test_wellness_multisource.py` | 10 tests; full suite 2838 passed / 30 skipped |
| Issue | #283 | commented; stays open until Andy live-verifies §5 |

## §9 — Carry-forward

- **#283 stays open** pending Andy's §5 live-verify (data half unprovable from the container).
- The field-decode tail of #283 (`[346] field_12/13` mystery counters, `[384] field_16` formula) is untouched here — orthogonal to the charts-wiring scope.
- **Lesson (unchanged):** a green suite proves the chart *logic*; only a prod `neon-query` / Andy's eyes prove the *data* reaches it (Rule #14). This change is built to be safe either way (defensive read, Garmin-non-regressive coalesce).
