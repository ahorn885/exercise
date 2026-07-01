"""Layer 3A integration substrate — five query-node accessors composing a
`Layer3AIntegrationBundle` per `Athlete_Data_Integration_Spec_v6.md` §10
+ `Layer3_3A_Spec.md` §3 / §5.1 step 7.

Each accessor is a pure SQL query node — deterministic given inputs, no
LLM involvement, returns a typed list (or report). Source-tagging via the
`source` Literal on each record supports the §6.1 self-report-vs-integration
weighting rules without forcing the substrate to resolve conflicts; the LLM
is the arbiter.

ACWR computation in `q_layer3A_combined_load` uses `cardio_log.duration_min`
(converted to hours) as the primary load signal per Integration Spec §10:
"Polar's `cardio_load` is exposed as a cross-reference, not the primary
number." The per-discipline + combined ratios use the standard window
formula `acute / (chronic / (window_days / 7))`, defaulting to a 28-day
chronic window and a 7-day acute window. Zones map to the
`ACWREntry.zone` Literal per the spec §8.1 trigger thresholds (>1.5
non-functional, <0.5 detraining) plus the Gabbett-2016 sweet-spot band
(0.8-1.3).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from layer4.context import (
    ACWREntry,
    CombinedLoadReport,
    DailyWellnessRecord,
    Layer3AIntegrationBundle,
    PolarCardioLoadCrossRef,
    ProviderStatus,
    SleepRecord,
    WorkoutRecord,
    WorkoutSource,
)


# ─── Constants ───────────────────────────────────────────────────────────────

_DEFAULT_WORKOUT_WINDOW_DAYS = 28
_DEFAULT_SLEEP_WINDOW_DAYS = 14
_DEFAULT_HRV_WINDOW_DAYS = 14
_DEFAULT_ACUTE_WINDOW_DAYS = 7
_DEFAULT_CHRONIC_WINDOW_DAYS = 28

# ACWR zone thresholds. Sweet-spot band 0.8-1.3 per Gabbett 2016. Spec §8.1
# warning thresholds at >1.5 + <0.5 anchor the non-functional / detraining
# zones. Functional-overreach band sits between sweet-spot and warning
# trigger (1.3-1.5).
_ACWR_DETRAINING_MAX = 0.5
_ACWR_UNDERTRAINING_MAX = 0.8
_ACWR_SWEETSPOT_MAX = 1.3
_ACWR_FUNCTIONAL_OVERREACH_MAX = 1.5

# Sentinel ratio when acute_load > 0 but chronic_load == 0 (new-athlete-with-
# no-base case). Picked so it lands in the non-functional band; the actual
# warning is the absence of chronic base, not the literal ratio value.
_ACWR_NO_BASE_SENTINEL = 999.0


# ─── Date / source helpers ───────────────────────────────────────────────────


def _as_date(value: Any) -> date:
    """`cardio_log.date` / `wellness_self_report.date` / etc. are TEXT in
    deployed schema (per `init_db.py`). Tests pass `datetime.date`; production
    rows come back as strings."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"unparseable date value: {value!r}")


def _window_cutoff(as_of: datetime | date, days: int) -> date:
    """Inclusive cutoff date: `[cutoff, as_of_date]` contains exactly `days`
    calendar dates. `days=7` on 2026-05-20 returns 2026-05-14 (the 14th
    through the 20th inclusive = 7 dates)."""
    anchor = as_of.date() if isinstance(as_of, datetime) else as_of
    return anchor - timedelta(days=days - 1)


def _detect_workout_source(row: Any) -> WorkoutSource:
    """Source detection by foreign-id column presence. Order matters when a
    row carries multiple IDs (rare; provider de-dupe is supposed to merge):
    Garmin > Polar > Wahoo > COROS > Strava > manual. Strava ranks last among
    providers — its bulk export carries files originally from another device, so
    a native-device id (if also present) better identifies the true source."""
    if row["garmin_activity_id"]:
        return "garmin"
    if row["polar_exercise_id"]:
        return "polar"
    if row["wahoo_workout_id"]:
        return "wahoo"
    if row["coros_label_id"]:
        return "coros"
    if row["strava_activity_id"]:
        return "strava"
    return "manual"


# ─── 1. q_layer3A_recent_workouts ────────────────────────────────────────────


def q_layer3A_recent_workouts(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    since_days: int = _DEFAULT_WORKOUT_WINDOW_DAYS,
) -> list[WorkoutRecord]:
    """Recent workouts over the past `since_days`. Returns chronological-
    descending (newest first). Reads `canonical_cardio_feed` (#196 Slice 4),
    NOT raw `cardio_log`, so a single ride synced from N providers counts once
    — otherwise the recent_workouts_count + the trajectory floors that gate
    athlete state would over-read the cross-source duplicates. Source-tagged per
    row via the provider foreign-id columns (`garmin_activity_id` /
    `polar_exercise_id` / `wahoo_workout_id` / `coros_label_id`); for a merged
    activity these carry the cluster's richest (primary) copy's device, so the
    tag names the best source. Manual entries (no foreign ID) surface as
    `source='manual'`.

    The `date` column is TEXT; comparison via lexicographic string ordering on
    ISO-format dates works correctly."""
    cutoff = _window_cutoff(as_of, since_days)
    cur = db.execute(
        """
        SELECT date, activity, duration_min, moving_time_min, distance_mi,
               avg_hr, max_hr, avg_power, elev_gain_ft,
               garmin_activity_id, polar_exercise_id, wahoo_workout_id,
               coros_label_id, strava_activity_id
          FROM canonical_cardio_feed
         WHERE user_id = %s AND date >= %s
         ORDER BY date DESC, id DESC
        """,
        (user_id, cutoff.isoformat()),
    )
    out: list[WorkoutRecord] = []
    for row in cur.fetchall():
        out.append(
            WorkoutRecord(
                date=_as_date(row["date"]),
                activity=row["activity"],
                duration_min=row["duration_min"],
                moving_time_min=row["moving_time_min"],
                distance_mi=row["distance_mi"],
                avg_hr=row["avg_hr"],
                max_hr=row["max_hr"],
                avg_power=row["avg_power"],
                elev_gain_ft=row["elev_gain_ft"],
                source=_detect_workout_source(row),
            )
        )
    return out


# ─── 2. q_layer3A_recent_wellness ────────────────────────────────────────────

def q_layer3A_recent_wellness(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    since_days: int = _DEFAULT_SLEEP_WINDOW_DAYS,
) -> list[DailyWellnessRecord]:
    """Per-day device wellness for the recent window — one `DailyWellnessRecord`
    per calendar day (newest first), read straight from the materialized
    `canonical_daily_wellness` table (#196 Phase 2, Slice 2.3).

    The per-field freshest-non-null coalesce across the five device sources
    (garmin/whoop/oura/polar/coros) now lives in `canonical_wellness.py`, which
    rebuilds the merged row on every wellness ingest (Slice 2.2). This reader is
    a thin SELECT of those merged columns — it retired the inline six-source
    coalesce that used to live here. The output is byte-identical to that path
    for the same underlying data (canonical stores the same rounded doubles in
    DOUBLE PRECISION columns, so no round-trip drift), keeping the 3A bundle hash
    / cache key stable across the repoint.

    Self-report sleep is intentionally excluded — it rides separately via
    `q_layer3A_recent_self_report_sleep` so the §6.1 objective-vs-subjective
    weighting stays intact."""
    cutoff_iso = _window_cutoff(as_of, since_days).isoformat()
    cur = db.execute(
        """
        SELECT date, total_sleep_hours, total_sleep_hours_source,
               hrv_rmssd_ms, hrv_rmssd_ms_source, resting_hr, resting_hr_source
          FROM canonical_daily_wellness
         WHERE user_id = %s AND date >= %s
         ORDER BY date DESC
        """,
        (user_id, cutoff_iso),
    )
    out: list[DailyWellnessRecord] = []
    for row in cur.fetchall():
        sleep_h = row["total_sleep_hours"]
        hrv_v = row["hrv_rmssd_ms"]
        rhr_v = row["resting_hr"]
        # A canonical row that carries only Garmin context (training_readiness /
        # vo2max with no merged device sleep/HRV/resting-HR) is skipped: the old
        # coalesce emitted a record only for days with at least one device value.
        if sleep_h is None and hrv_v is None and rhr_v is None:
            continue
        out.append(
            DailyWellnessRecord(
                date=_as_date(row["date"]),
                total_sleep_hours=sleep_h,
                total_sleep_hours_source=row["total_sleep_hours_source"],
                hrv_rmssd_ms=hrv_v,
                hrv_rmssd_ms_source=row["hrv_rmssd_ms_source"],
                resting_hr=rhr_v,
                resting_hr_source=row["resting_hr_source"],
            )
        )
    return out


# ─── 3. q_layer3A_recent_self_report_sleep ───────────────────────────────────


def q_layer3A_recent_self_report_sleep(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    since_days: int = _DEFAULT_SLEEP_WINDOW_DAYS,
) -> list[SleepRecord]:
    """Recent self-report sleep from `wellness_self_report` (`sleep_hours` +
    `sleep_quality`), newest first. The stored `sleep_quality` column is on
    the athlete-facing check-in form's 1-5 scale (`routes/wellness.py`
    `_parse_int(..., lo=1, hi=5)`); it is doubled here to the 1-10 scale that
    the rest of the pipeline expects (`SleepRecord.sleep_quality` is
    `ge=1, le=10`, and `layer3a/builder.py` renders it as `.../10`). `None`
    (no self-report submitted) is passed through unconverted. Kept separate
    from the device coalesce in `q_layer3A_recent_wellness` so the §6.1
    weighting can treat subjective sleep_quality as self-report-dominant
    while objective sleep duration stays integration-dominant. No further
    normalization beyond the scale conversion — the LLM is the arbiter
    (Integration Spec §10)."""
    cutoff = _window_cutoff(as_of, since_days)
    cur = db.execute(
        """
        SELECT date, sleep_hours, sleep_quality
          FROM wellness_self_report
         WHERE user_id = %s AND date >= %s
         ORDER BY date DESC
        """,
        (user_id, cutoff.isoformat()),
    )
    out: list[SleepRecord] = []
    for row in cur.fetchall():
        raw_quality = row["sleep_quality"]
        out.append(
            SleepRecord(
                date=_as_date(row["date"]),
                total_sleep_hours=row["sleep_hours"],
                sleep_quality=raw_quality * 2 if raw_quality is not None else None,
                source="wellness_self_report",
            )
        )
    return out


# ─── 4. q_layer3A_combined_load ──────────────────────────────────────────────


def _classify_zone(ratio: float) -> str:
    if ratio < _ACWR_DETRAINING_MAX:
        return "detraining"
    if ratio < _ACWR_UNDERTRAINING_MAX:
        return "undertraining"
    if ratio <= _ACWR_SWEETSPOT_MAX:
        return "sweet_spot"
    if ratio <= _ACWR_FUNCTIONAL_OVERREACH_MAX:
        return "functional_overreach"
    return "non_functional_overreach"


def _compute_acwr(
    acute_hours: float,
    chronic_hours: float,
    chronic_window_days: int,
    acute_window_days: int,
) -> ACWREntry | None:
    """Standard ACWR: acute load (last `acute_window_days`) divided by the
    rolling chronic baseline (sum over `chronic_window_days` normalized to the
    acute-window length). Returns None when both acute and chronic are zero
    (no data → no signal to emit). When acute > 0 but chronic == 0, emits a
    sentinel ratio so the LLM sees the "new athlete, no base" case
    explicitly."""
    if acute_hours == 0.0 and chronic_hours == 0.0:
        return None

    if chronic_hours == 0.0:
        ratio = _ACWR_NO_BASE_SENTINEL
    else:
        chronic_normalized = chronic_hours / (chronic_window_days / acute_window_days)
        ratio = acute_hours / chronic_normalized if chronic_normalized > 0 else _ACWR_NO_BASE_SENTINEL

    return ACWREntry(
        acute_load=round(acute_hours, 2),
        chronic_load=round(chronic_hours, 2),
        ratio=round(ratio, 3),
        zone=_classify_zone(ratio),  # type: ignore[arg-type]
        units="hours",
    )


def q_layer3A_combined_load(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    window_days: int = _DEFAULT_CHRONIC_WINDOW_DAYS,
    acute_window_days: int = _DEFAULT_ACUTE_WINDOW_DAYS,
) -> CombinedLoadReport:
    """ACWR per discipline + combined, computed from `cardio_log.duration_min`
    over the chronic window. Polar cardio-load (now in `provider_raw_record`,
    data_type='cardio_load'; #681 §4 Slice 3) is read for the cross-reference
    (latest row only) but is NOT the primary load source per Integration
    Spec §10."""
    chronic_cutoff = _window_cutoff(as_of, window_days)
    acute_cutoff = _window_cutoff(as_of, acute_window_days)
    chronic_iso = chronic_cutoff.isoformat()
    acute_iso = acute_cutoff.isoformat()

    # Reads `canonical_cardio_feed` (#196 Slice 4), not raw cardio_log: ACWR sums
    # each row's hours into the acute/chronic load, so a ride synced from N
    # providers would otherwise inflate training load N-fold. The feed collapses
    # each cluster to its one best-of row (and still surfaces unclustered rows).
    cur = db.execute(
        """
        SELECT date, activity, duration_min, moving_time_min
          FROM canonical_cardio_feed
         WHERE user_id = %s AND date >= %s AND activity IS NOT NULL
        """,
        (user_id, chronic_iso),
    )
    rows = list(cur.fetchall())

    per_discipline_acute: dict[str, float] = defaultdict(float)
    per_discipline_chronic: dict[str, float] = defaultdict(float)
    combined_acute = 0.0
    combined_chronic = 0.0

    for row in rows:
        # Prefer moving_time_min when present (GPS-trimmed); fall back to
        # duration_min (clock-elapsed). Manual entries usually populate
        # duration_min only.
        minutes = row["moving_time_min"] or row["duration_min"]
        if minutes is None or minutes <= 0:
            continue
        hours = minutes / 60.0
        activity = row["activity"]
        row_date = _as_date(row["date"])

        per_discipline_chronic[activity] += hours
        combined_chronic += hours
        if row_date.isoformat() >= acute_iso:
            per_discipline_acute[activity] += hours
            combined_acute += hours

    per_discipline: dict[str, ACWREntry] = {}
    for activity in per_discipline_chronic:
        entry = _compute_acwr(
            per_discipline_acute.get(activity, 0.0),
            per_discipline_chronic[activity],
            window_days,
            acute_window_days,
        )
        if entry is not None:
            per_discipline[activity] = entry

    combined_entry = _compute_acwr(
        combined_acute, combined_chronic, window_days, acute_window_days
    )

    # Polar cardio-load now lives in `provider_raw_record` (#681 §4 Slice 3) —
    # latest day's normalised fields for the cross-reference.
    cur = db.execute(
        """
        SELECT external_id AS date,
               (raw_payload->>'daily_load')::float   AS daily_load,
               (raw_payload->>'acute_load')::float   AS acute_load,
               (raw_payload->>'chronic_load')::float AS chronic_load,
               raw_payload->>'cardio_load_status'    AS cardio_load_status,
               (raw_payload->>'strain')::float       AS strain
          FROM provider_raw_record
         WHERE user_id = %s AND provider = 'polar' AND data_type = 'cardio_load'
         ORDER BY external_id DESC
         LIMIT 1
        """,
        (user_id,),
    )
    polar_row = cur.fetchone()
    polar_cross_ref = None
    if polar_row is not None:
        polar_cross_ref = PolarCardioLoadCrossRef(
            date=_as_date(polar_row["date"]),
            daily_load=polar_row["daily_load"],
            acute_load=polar_row["acute_load"],
            chronic_load=polar_row["chronic_load"],
            cardio_load_status=polar_row["cardio_load_status"],
            strain=polar_row["strain"],
        )

    return CombinedLoadReport(
        per_discipline=per_discipline,
        combined=combined_entry,
        units="hours",
        polar_cross_ref=polar_cross_ref,
    )


# ─── 5. q_layer3A_connected_providers ────────────────────────────────────────


def q_layer3A_connected_providers(
    db: Any,
    user_id: int,
    *,
    as_of: datetime | date | None = None,
    workout_window_days: int = _DEFAULT_WORKOUT_WINDOW_DAYS,
    sleep_window_days: int = _DEFAULT_SLEEP_WINDOW_DAYS,
    hrv_window_days: int = _DEFAULT_HRV_WINDOW_DAYS,
) -> list[ProviderStatus]:
    """List of providers the user has authorized, with per-data-type coverage
    flags. Per Integration Spec §10: "Used by 3A to set confidence tags per
    §8." Drives the `data_density.connected_providers` block in the LLM's
    output.

    `last_sync` is computed as MAX(`webhook_events.received_at`) per provider
    (no dedicated column in `provider_auth`). Coverage flags use the same
    recency windows as the per-data accessors so the LLM's view of "is data
    actively flowing" stays consistent."""
    # Day-anchored fallback (not full-precision `datetime.now()`): this anchor
    # feeds the date cutoffs behind the day-granular provider-coverage flags,
    # which ride in the Layer3AIntegrationBundle whose hash folds into the 3A
    # cache key (`layer3a_athlete_state_key`) — a sub-day fallback would drift
    # that key every resumable pass. The sole production caller always passes a
    # day-anchored `as_of`, so this path is purely defensive.
    anchor = as_of or datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    workout_cutoff = _window_cutoff(anchor, workout_window_days).isoformat()
    sleep_cutoff = _window_cutoff(anchor, sleep_window_days).isoformat()
    hrv_cutoff = _window_cutoff(anchor, hrv_window_days).isoformat()

    cur = db.execute(
        """
        SELECT provider, status, updated_at
          FROM provider_auth
         WHERE user_id = %s
         ORDER BY provider
        """,
        (user_id,),
    )
    auth_rows = list(cur.fetchall())

    cur = db.execute(
        """
        SELECT provider, MAX(received_at) AS last_received
          FROM webhook_events
         WHERE user_id = %s
         GROUP BY provider
        """,
        (user_id,),
    )
    last_sync_by_provider: dict[str, datetime | None] = {}
    for row in cur.fetchall():
        last_sync_by_provider[row["provider"]] = row["last_received"]

    # Workout coverage: which provider IDs are populated on recent cardio_log
    # rows? Single query, bucketed via FILTER. DELIBERATELY reads raw cardio_log,
    # NOT canonical_cardio_feed (#196 Slice 4): this counts per-provider coverage,
    # so it needs the un-merged rows — the feed collapses a cross-source ride to
    # one row carrying only its primary copy's ids, which would under-count the
    # secondary providers' coverage. Do not repoint this at the feed.
    cur = db.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE garmin_activity_id IS NOT NULL) AS garmin_n,
          COUNT(*) FILTER (WHERE polar_exercise_id IS NOT NULL)  AS polar_n,
          COUNT(*) FILTER (WHERE wahoo_workout_id IS NOT NULL)   AS wahoo_n,
          COUNT(*) FILTER (WHERE coros_label_id IS NOT NULL)     AS coros_n
        FROM cardio_log
        WHERE user_id = %s AND date >= %s
        """,
        (user_id, workout_cutoff),
    )
    wrow = cur.fetchone() or {}
    workouts_by_provider = {
        "garmin": (wrow.get("garmin_n") or 0) > 0,
        "polar": (wrow.get("polar_n") or 0) > 0,
        "wahoo": (wrow.get("wahoo_n") or 0) > 0,
        "coros": (wrow.get("coros_n") or 0) > 0,
    }

    # Coverage counts now come from `provider_raw_record` (#681 §4 Slice 3),
    # same provider-tagged windows as the per-data accessors above.
    cur = db.execute(
        """
        SELECT COUNT(*) AS n FROM provider_raw_record
         WHERE user_id = %s AND provider = 'polar' AND data_type = 'sleep'
           AND external_id >= %s
        """,
        (user_id, sleep_cutoff),
    )
    polar_sleep_n = (cur.fetchone() or {}).get("n") or 0

    cur = db.execute(
        """
        SELECT COUNT(*) AS n FROM provider_raw_record
         WHERE user_id = %s AND provider = 'coros' AND data_type = 'daily_summary'
           AND external_id >= %s AND (raw_payload->>'sleep_start_ms') IS NOT NULL
        """,
        (user_id, sleep_cutoff),
    )
    coros_sleep_n = (cur.fetchone() or {}).get("n") or 0

    cur = db.execute(
        """
        SELECT COUNT(*) AS n FROM provider_raw_record
         WHERE user_id = %s AND provider = 'polar' AND data_type = 'hrv'
           AND external_id >= %s AND (raw_payload->>'hrv_rmssd_ms') IS NOT NULL
        """,
        (user_id, hrv_cutoff),
    )
    polar_hrv_n = (cur.fetchone() or {}).get("n") or 0

    cur = db.execute(
        """
        SELECT COUNT(*) AS n FROM provider_raw_record
         WHERE user_id = %s AND provider = 'coros' AND data_type = 'daily_summary'
           AND external_id >= %s AND (raw_payload->>'ppg_hrv') IS NOT NULL
        """,
        (user_id, hrv_cutoff),
    )
    coros_hrv_n = (cur.fetchone() or {}).get("n") or 0

    sleep_by_provider = {
        "polar": polar_sleep_n > 0,
        "coros": coros_sleep_n > 0,
    }
    hrv_by_provider = {
        "polar": polar_hrv_n > 0,
        "coros": coros_hrv_n > 0,
    }

    out: list[ProviderStatus] = []
    for row in auth_rows:
        provider = row["provider"]
        # Day-anchor last_sync: it's a raw MAX(received_at) timestamp that folds
        # (via the Layer3AIntegrationBundle hash → integration_bundle_hash) into
        # the 3A cache key. A sub-day value drifts that key whenever a provider
        # checks in mid-generation, so 3A re-runs every resumable pass and every
        # Layer 4 block is orphaned (D-77 non-convergence). Day-granular is
        # sufficient for the LLM's "is data flowing" view; genuine new training
        # data still invalidates via the day-keyed recent_workouts/sleep/hrv.
        raw_last_sync = last_sync_by_provider.get(provider)
        last_sync = (
            raw_last_sync.replace(hour=0, minute=0, second=0, microsecond=0)
            if isinstance(raw_last_sync, datetime)
            else raw_last_sync
        )
        out.append(
            ProviderStatus(
                provider=provider,
                status=row["status"],
                last_sync=last_sync,
                has_recent_workouts=workouts_by_provider.get(provider, False),
                has_recent_sleep=sleep_by_provider.get(provider, False),
                has_recent_hrv=hrv_by_provider.get(provider, False),
            )
        )
    return out


# ─── Aggregator ──────────────────────────────────────────────────────────────


def assemble_layer3a_integration_bundle(
    db: Any,
    user_id: int,
    as_of: datetime,
) -> Layer3AIntegrationBundle:
    """Convenience composer — runs all five accessors against the same
    `as_of` anchor and returns a populated `Layer3AIntegrationBundle`. The
    driver session's `llm_layer3a_athlete_state` accepts a bundle directly,
    so this function is the standard production-side composer."""
    return Layer3AIntegrationBundle(
        as_of=as_of,
        recent_workouts=q_layer3A_recent_workouts(db, user_id, as_of),
        recent_wellness=q_layer3A_recent_wellness(db, user_id, as_of),
        recent_self_report_sleep=q_layer3A_recent_self_report_sleep(db, user_id, as_of),
        combined_load=q_layer3A_combined_load(db, user_id, as_of),
        connected_providers=q_layer3A_connected_providers(db, user_id, as_of=as_of),
    )


__all__ = [
    "assemble_layer3a_integration_bundle",
    "q_layer3A_combined_load",
    "q_layer3A_connected_providers",
    "q_layer3A_recent_self_report_sleep",
    "q_layer3A_recent_wellness",
    "q_layer3A_recent_workouts",
]
