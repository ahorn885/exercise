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
    HRVRecord,
    HRVSource,
    Layer3AIntegrationBundle,
    PolarCardioLoadCrossRef,
    ProviderStatus,
    SleepRecord,
    SleepSource,
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
    Garmin > Polar > Wahoo > COROS > manual."""
    if row["garmin_activity_id"]:
        return "garmin"
    if row["polar_exercise_id"]:
        return "polar"
    if row["wahoo_workout_id"]:
        return "wahoo"
    if row["coros_label_id"]:
        return "coros"
    return "manual"


# ─── 1. q_layer3A_recent_workouts ────────────────────────────────────────────


def q_layer3A_recent_workouts(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    since_days: int = _DEFAULT_WORKOUT_WINDOW_DAYS,
) -> list[WorkoutRecord]:
    """Recent workouts from `cardio_log` over the past `since_days`. Returns
    chronological-descending (newest first). Source-tagged per row via the
    provider foreign-id columns (`garmin_activity_id` / `polar_exercise_id`
    / `wahoo_workout_id` / `coros_label_id`). Manual entries (no foreign ID)
    surface as `source='manual'`.

    The deployed `cardio_log.date` column is TEXT; comparison via lexicographic
    string ordering on ISO-format dates works correctly."""
    cutoff = _window_cutoff(as_of, since_days)
    cur = db.execute(
        """
        SELECT date, activity, duration_min, moving_time_min, distance_mi,
               avg_hr, max_hr, avg_power, elev_gain_ft,
               garmin_activity_id, polar_exercise_id, wahoo_workout_id, coros_label_id
          FROM cardio_log
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


# ─── 2. q_layer3A_recent_sleep ───────────────────────────────────────────────


def q_layer3A_recent_sleep(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    since_days: int = _DEFAULT_SLEEP_WINDOW_DAYS,
) -> list[SleepRecord]:
    """Recent sleep across three sources: `wellness_self_report` (self-report,
    `sleep_hours` + `sleep_quality`), `polar_sleep` (`total_sleep_min`),
    `coros_daily_summary` (`sleep_start_ms` + `sleep_end_ms` deltas). Garmin
    wellness-log sleep is named in the spec but no Garmin sleep table is
    deployed; skipped in v1.

    Sleep quality is captured only from self-report (1-10 scale); provider
    rows leave it None. Integration Spec §10 says "LLM in 3A resolves
    conflicts" — no normalization here, the LLM weighs sources per §6.1."""
    cutoff = _window_cutoff(as_of, since_days)
    cutoff_iso = cutoff.isoformat()

    cur = db.execute(
        """
        SELECT date, sleep_hours, sleep_quality
          FROM wellness_self_report
         WHERE user_id = %s AND date >= %s
         ORDER BY date DESC
        """,
        (user_id, cutoff_iso),
    )
    self_report_rows = list(cur.fetchall())

    cur = db.execute(
        """
        SELECT date, total_sleep_min
          FROM polar_sleep
         WHERE user_id = %s AND date >= %s
         ORDER BY date DESC
        """,
        (user_id, cutoff_iso),
    )
    polar_rows = list(cur.fetchall())

    cur = db.execute(
        """
        SELECT happen_day AS date, sleep_start_ms, sleep_end_ms
          FROM coros_daily_summary
         WHERE user_id = %s AND happen_day >= %s
           AND sleep_start_ms IS NOT NULL
           AND sleep_end_ms IS NOT NULL
         ORDER BY happen_day DESC
        """,
        (user_id, cutoff_iso),
    )
    coros_rows = list(cur.fetchall())

    out: list[SleepRecord] = []
    for row in self_report_rows:
        out.append(
            SleepRecord(
                date=_as_date(row["date"]),
                total_sleep_hours=row["sleep_hours"],
                sleep_quality=row["sleep_quality"],
                source="wellness_self_report",
            )
        )
    for row in polar_rows:
        mins = row["total_sleep_min"]
        out.append(
            SleepRecord(
                date=_as_date(row["date"]),
                total_sleep_hours=(mins / 60.0) if mins is not None else None,
                sleep_quality=None,
                source="polar",
            )
        )
    for row in coros_rows:
        start_ms = row["sleep_start_ms"]
        end_ms = row["sleep_end_ms"]
        hours = (end_ms - start_ms) / 3600_000.0 if (start_ms and end_ms) else None
        out.append(
            SleepRecord(
                date=_as_date(row["date"]),
                total_sleep_hours=hours,
                sleep_quality=None,
                source="coros",
            )
        )

    out.sort(key=lambda r: (r.date, r.source), reverse=True)
    return out


# ─── 3. q_layer3A_recent_hrv ─────────────────────────────────────────────────


def q_layer3A_recent_hrv(
    db: Any,
    user_id: int,
    as_of: datetime | date,
    *,
    since_days: int = _DEFAULT_HRV_WINDOW_DAYS,
) -> list[HRVRecord]:
    """Recent HRV across two sources: `polar_nightly_recharge.hrv_rmssd_ms`
    (true RMSSD) and `coros_daily_summary.ppg_hrv` (nightly PPG-derived).
    High-resolution `coros_hrv_samples` is named in Integration Spec §10 with
    a "downsampled to nightly" note — out of substrate scope for v1; the
    nightly COROS summary suffices."""
    cutoff = _window_cutoff(as_of, since_days)
    cutoff_iso = cutoff.isoformat()

    cur = db.execute(
        """
        SELECT date, hrv_rmssd_ms
          FROM polar_nightly_recharge
         WHERE user_id = %s AND date >= %s AND hrv_rmssd_ms IS NOT NULL
         ORDER BY date DESC
        """,
        (user_id, cutoff_iso),
    )
    polar_rows = list(cur.fetchall())

    cur = db.execute(
        """
        SELECT happen_day AS date, ppg_hrv
          FROM coros_daily_summary
         WHERE user_id = %s AND happen_day >= %s AND ppg_hrv IS NOT NULL
         ORDER BY happen_day DESC
        """,
        (user_id, cutoff_iso),
    )
    coros_rows = list(cur.fetchall())

    out: list[HRVRecord] = []
    for row in polar_rows:
        out.append(
            HRVRecord(
                date=_as_date(row["date"]),
                hrv_rmssd_ms=row["hrv_rmssd_ms"],
                source="polar",
            )
        )
    for row in coros_rows:
        ppg = row["ppg_hrv"]
        out.append(
            HRVRecord(
                date=_as_date(row["date"]),
                hrv_rmssd_ms=float(ppg) if ppg is not None else None,
                source="coros",
            )
        )

    out.sort(key=lambda r: (r.date, r.source), reverse=True)
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
    over the chronic window. `polar_cardio_load` is read for the cross-
    reference (latest row only) but is NOT the primary load source per
    Integration Spec §10."""
    chronic_cutoff = _window_cutoff(as_of, window_days)
    acute_cutoff = _window_cutoff(as_of, acute_window_days)
    chronic_iso = chronic_cutoff.isoformat()
    acute_iso = acute_cutoff.isoformat()

    cur = db.execute(
        """
        SELECT date, activity, duration_min, moving_time_min
          FROM cardio_log
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

    cur = db.execute(
        """
        SELECT date, daily_load, acute_load, chronic_load, cardio_load_status, strain
          FROM polar_cardio_load
         WHERE user_id = %s
         ORDER BY date DESC
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
    # rows? Single query, bucketed via CASE.
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

    cur = db.execute(
        "SELECT COUNT(*) AS n FROM polar_sleep WHERE user_id = %s AND date >= %s",
        (user_id, sleep_cutoff),
    )
    polar_sleep_n = (cur.fetchone() or {}).get("n") or 0

    cur = db.execute(
        """
        SELECT COUNT(*) AS n
          FROM coros_daily_summary
         WHERE user_id = %s AND happen_day >= %s AND sleep_start_ms IS NOT NULL
        """,
        (user_id, sleep_cutoff),
    )
    coros_sleep_n = (cur.fetchone() or {}).get("n") or 0

    cur = db.execute(
        """
        SELECT COUNT(*) AS n
          FROM polar_nightly_recharge
         WHERE user_id = %s AND date >= %s AND hrv_rmssd_ms IS NOT NULL
        """,
        (user_id, hrv_cutoff),
    )
    polar_hrv_n = (cur.fetchone() or {}).get("n") or 0

    cur = db.execute(
        """
        SELECT COUNT(*) AS n
          FROM coros_daily_summary
         WHERE user_id = %s AND happen_day >= %s AND ppg_hrv IS NOT NULL
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
        out.append(
            ProviderStatus(
                provider=provider,
                status=row["status"],
                last_sync=last_sync_by_provider.get(provider),
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
        recent_sleep=q_layer3A_recent_sleep(db, user_id, as_of),
        recent_hrv=q_layer3A_recent_hrv(db, user_id, as_of),
        combined_load=q_layer3A_combined_load(db, user_id, as_of),
        connected_providers=q_layer3A_connected_providers(db, user_id, as_of=as_of),
    )


__all__ = [
    "assemble_layer3a_integration_bundle",
    "q_layer3A_combined_load",
    "q_layer3A_connected_providers",
    "q_layer3A_recent_hrv",
    "q_layer3A_recent_sleep",
    "q_layer3A_recent_workouts",
]
