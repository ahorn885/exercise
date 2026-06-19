# Unified Layer-3A Wellness Record (#757) — Design v1

**Status:** ratified + built (2026-06-19). Closes follow-up **#757** ("wire Garmin
daily metrics into Layer-3A sleep/HRV/RHR coaching inputs"), filed out of the
#681 §4 Slice 3 consolidation.

## 1. Problem

Layer-3A's integration substrate read recovery data from Polar + COROS
(`provider_raw_record`) and `wellness_self_report` only. Garmin's daily metrics
— the richest, highest-fidelity source, and the only one Andy actually wears —
sat in `daily_wellness_metrics` and never reached coaching state (deliberately
deferred in Slice 3 to keep that slice behavior-preserving).

Two findings reframed the fix from "add a source" to a substrate change:

1. **The 3A prompt render was summary-only.** `_render_integration_summary`
   emitted `recent_sleep: count=N sources={polar:5,coros:3}` — counts + a
   source histogram, never per-night *values*. Adding Garmin as a fourth source
   would only bump a count; the actual numbers (7.2h, HRV 42, RHR 48) would
   still never inform the LLM's reasoning.
2. **Per-source record lists fragmented the same night.** A single night could
   produce a Garmin row, a Polar row and a COROS row, each partial. The LLM was
   left to reconcile duplicate partial rows with no provenance to weigh them.

## 2. Decisions (Andy, ratified)

- **Unified per-day record.** One `DailyWellnessRecord` per calendar day merging
  sleep / HRV / resting-HR across providers — not parallel per-source lists.
- **Per-field provenance.** Each metric carries a `*_source` tag (typed parallel
  field, not a dict — type-safe and trivial to render).
- **Freshest-non-null coalesce.** Per field, the value from the source with the
  newest ingest timestamp wins; a NULL or older source never clobbers a
  populated or newer one; ties break on a fixed device priority
  garmin>polar>coros (deterministic — the bundle hash folds into the 3A cache
  key).
- **Self-report stays separate.** Device coalesce is objective-only;
  `wellness_self_report` sleep rides in its own `recent_self_report_sleep` lane
  so §6.1's objective-vs-subjective weighting (objective→integration dominates,
  subjective→self-report dominates) is preserved rather than silently merged.
- **Prompt render (Trigger #1, ratified verbatim).** Per metric: latest value +
  provenance + 14d-average + populated-day count, suppress-on-empty; plus a §4
  weighting addendum adding resting HR + HRV to the objective-metrics bullet.

## 3. Schema (`layer4/context.py`)

```python
WellnessSource = Literal["garmin", "polar", "coros"]

class DailyWellnessRecord(_Base):
    date: date
    total_sleep_hours: float | None;  total_sleep_hours_source: WellnessSource | None
    hrv_rmssd_ms: float | None;       hrv_rmssd_ms_source: WellnessSource | None
    resting_hr: int | None;           resting_hr_source: WellnessSource | None
```

Bundle change: `recent_sleep` + `recent_hrv` → `recent_wellness:
list[DailyWellnessRecord]` + `recent_self_report_sleep: list[SleepRecord]`.
`SleepRecord` narrowed to self-report only (`SleepSource =
Literal["wellness_self_report"]`); `HRVRecord`/`HRVSource` removed (folded in).

## 4. Coalesce (`layer3a/integration.py`)

`q_layer3A_recent_wellness` reads four queries — Garmin `daily_wellness_metrics`
(sleep span via `sleep_end_ms - sleep_start_ms`, `hrv_overnight_avg_ms`,
`resting_hr`, ts=`updated_at`); Polar sleep + Polar HRV + COROS daily summary
(all `provider_raw_record`, ts=`fetched_at`) — buckets non-null candidates per
`(day, field)` as `(timestamp, value, source)`, and picks
`max(key=(ts or datetime.min, priority))`. Garmin's `updated_at` and
`provider_raw_record.fetched_at` are the comparable ingest axis.

`q_layer3A_recent_self_report_sleep` reads `wellness_self_report` unchanged.

**Window:** 14d (matches prior sleep/HRV). Workouts (28d) + combined_load
untouched.

## 5. Render + behavioral coupling (`layer3a/builder.py`)

- `_render_integration_summary`: `recent_wellness` block (per-metric latest +
  provenance + `14d-avg` + `nights=/days=`, suppress-on-empty) + a
  `self_report_sleep` line (count + latest hours/quality). §4 objective bullet
  gains resting HR + HRV and a note that wellness is per-field coalesced with
  tagged sources.
- `_build_prep_dict` evidence-basis allowlist: `integration.recent_sleep` /
  `recent_hrv` → `integration.recent_wellness` + `recent_self_report_sleep`.
- §6.2 Floor 3 ("no recent HRV → trajectory ≤ medium") now tests
  `any(r.hrv_rmssd_ms is not None for r in recent_wellness)`.

**Deliberately unchanged:** the LLM *output* schema (`data_density.
recent_sleep_count` / `recent_hrv_count`) stays stable — the new render exposes
per-metric `nights=N` so the LLM still fills them. This bounds the blast radius
to the *input* contract.

## 6. Scope boundaries / follow-ups

- **`connected_providers` left untouched.** Garmin authenticates via
  `garmin_auth`, not `provider_auth` (which the accessor reads), so attaching
  Garmin coverage flags would require resolving Garmin's auth surface — out of
  scope and not worth guessing. Consequence: garmin-only wellness does not yet
  satisfy the §6.2 high-confidence Gate 1 (`active provider with recent data`).
  Filed as a follow-up.
- **`resting_hr` is garmin-only.** Polar/COROS RHR payload fields are
  unconfirmed; adding them would be inventing data. Provenance is always
  `garmin` for RHR until a second source is confirmed.
- **Sleep duration = bedtime span** (`end - start`), matching the existing COROS
  convention, not deep+light+rem summed. Consistent across sources; revisit if
  the LLM needs true asleep-time.

## 7. Test scenarios (`tests/test_layer3a_integration.py`)

Empty; 14d window; Garmin all-three-metrics; freshest-non-null across providers
(fresher Polar sleep wins, garmin-only HRV survives); NULL-never-clobbers;
equal-timestamp priority tiebreak (garmin>coros); COROS sleep+HRV; multi-day
desc sort; self-report lane. Full suite: **2700 passed / 30 skipped**.

## 8. Gut check

- **Risk:** the prompt now carries per-night-ish detail (latest + avg) rather
  than a one-line count — more tokens, and the LLM could over-index on a single
  latest value. Mitigated by also showing the 14d-avg + count so a one-off night
  is visible as such. If it proves noisy, the ratified fallback was "latest-only
  no trend."
- **Best argument against:** the freshest-non-null timestamp axis assumes
  `updated_at`/`fetched_at` are trustworthy ingest times; a backfill that
  rewrites `updated_at` could let a re-synced old row win. Acceptable — backfills
  are rare and the priority tiebreak + non-null guard bound the damage; the
  alternative (fixed source priority only) loses genuine "fresher correction
  wins" semantics Andy asked for.
- **What might be missing:** garmin not surfacing as a connected provider (§6)
  means high-confidence gating still can't credit device data Andy wears — the
  coaching *state* sees it, the *confidence ceiling* doesn't yet. Tracked.
