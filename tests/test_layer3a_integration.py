"""Tests for `layer3a.integration` — the five q_layer3A_* substrate
accessors + `assemble_layer3a_integration_bundle`.

Each accessor's expected SQL-call order is documented inline so the
`_FakeConn` batch queue lines up deterministically. The pattern mirrors
`tests/test_layer2c.py` (`_FakeConn` / `_FakeCursor` / `_FakeRow`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from layer3a import (
    assemble_layer3a_integration_bundle,
    q_layer3A_combined_load,
    q_layer3A_connected_providers,
    q_layer3A_recent_self_report_sleep,
    q_layer3A_recent_wellness,
    q_layer3A_recent_workouts,
)
from layer3a.integration import _classify_zone, _compute_acwr, _detect_workout_source
from layer4.context import (
    CombinedLoadReport,
    DailyWellnessRecord,
    Layer3AIntegrationBundle,
    ProviderStatus,
    WorkoutRecord,
)
from layer4.hashing import compute_payload_hash


# ─── Fakes (mirror tests/test_layer2c.py) ────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    """Queues response batches per ordered SELECT the accessor issues."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.batches: list[list[dict[str, Any]]] = []

    def queue(self, *rows: dict[str, Any]) -> None:
        self.batches.append(list(rows))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.batches.pop(0) if self.batches else []
        return _FakeCursor(rows)


_AS_OF = datetime(2026, 5, 20, 12, 0, 0)


def _workout_row(
    *,
    date_str: str = "2026-05-19",
    activity: str = "Trail Run",
    duration_min: float | None = 45.0,
    moving_time_min: float | None = None,
    distance_mi: float | None = None,
    avg_hr: int | None = None,
    max_hr: int | None = None,
    avg_power: int | None = None,
    elev_gain_ft: float | None = None,
    garmin_activity_id: str | None = None,
    polar_exercise_id: str | None = None,
    wahoo_workout_id: str | None = None,
    coros_label_id: str | None = None,
    strava_activity_id: str | None = None,
) -> dict[str, Any]:
    return {
        "date": date_str,
        "activity": activity,
        "duration_min": duration_min,
        "moving_time_min": moving_time_min,
        "distance_mi": distance_mi,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "avg_power": avg_power,
        "elev_gain_ft": elev_gain_ft,
        "garmin_activity_id": garmin_activity_id,
        "polar_exercise_id": polar_exercise_id,
        "wahoo_workout_id": wahoo_workout_id,
        "coros_label_id": coros_label_id,
        "strava_activity_id": strava_activity_id,
    }


# ─── q_layer3A_recent_workouts ───────────────────────────────────────────────


class TestRecentWorkouts:
    def test_empty(self):
        conn = _FakeConn()
        out = q_layer3A_recent_workouts(conn, user_id=1, as_of=_AS_OF)
        assert out == []
        assert len(conn.calls) == 1

    def test_window_cutoff_param(self):
        conn = _FakeConn()
        q_layer3A_recent_workouts(conn, user_id=1, as_of=_AS_OF, since_days=14)
        _, params = conn.calls[0]
        # 2026-05-20 inclusive 14-day window → cutoff 2026-05-07
        assert params == (1, "2026-05-07")

    def test_default_window_28d(self):
        conn = _FakeConn()
        q_layer3A_recent_workouts(conn, user_id=42, as_of=_AS_OF)
        _, params = conn.calls[0]
        assert params == (42, "2026-04-23")

    def test_source_detection_per_provider(self):
        conn = _FakeConn()
        conn.queue(
            _workout_row(date_str="2026-05-19", activity="manual_run", duration_min=30),
            _workout_row(
                date_str="2026-05-18", activity="garmin_run", garmin_activity_id="G1"
            ),
            _workout_row(
                date_str="2026-05-17", activity="polar_run", polar_exercise_id="P1"
            ),
            _workout_row(
                date_str="2026-05-16", activity="wahoo_ride", wahoo_workout_id="W1"
            ),
            _workout_row(
                date_str="2026-05-15", activity="coros_run", coros_label_id="C1"
            ),
            _workout_row(
                date_str="2026-05-14", activity="strava_run", strava_activity_id="S1"
            ),
        )
        out = q_layer3A_recent_workouts(conn, 1, _AS_OF)
        sources = [r.source for r in out]
        assert sources == ["manual", "garmin", "polar", "wahoo", "coros", "strava"]

    def test_source_priority_garmin_wins_over_others(self):
        # Defensive: garmin > polar > wahoo > coros > strava if multiple IDs present.
        row = _workout_row(
            garmin_activity_id="G1",
            polar_exercise_id="P1",
            wahoo_workout_id="W1",
            coros_label_id="C1",
            strava_activity_id="S1",
        )
        assert _detect_workout_source(_FakeRow(row)) == "garmin"

    def test_strava_source_detection(self):
        # Strava ranks last among providers, but a strava-only row tags strava.
        row = _workout_row(strava_activity_id="strava-file:abc123")
        assert _detect_workout_source(_FakeRow(row)) == "strava"

    def test_full_row_fields(self):
        conn = _FakeConn()
        conn.queue(
            _workout_row(
                date_str="2026-05-19",
                activity="MTB",
                duration_min=90.0,
                moving_time_min=85.0,
                distance_mi=18.5,
                avg_hr=145,
                max_hr=172,
                avg_power=180,
                elev_gain_ft=1200.0,
            )
        )
        out = q_layer3A_recent_workouts(conn, 1, _AS_OF)
        assert len(out) == 1
        w = out[0]
        assert w.activity == "MTB"
        assert w.duration_min == 90.0
        assert w.moving_time_min == 85.0
        assert w.distance_mi == 18.5
        assert w.avg_hr == 145
        assert w.max_hr == 172
        assert w.avg_power == 180
        assert w.elev_gain_ft == 1200.0
        assert w.date == date(2026, 5, 19)

    def test_as_of_accepts_date_or_datetime(self):
        conn = _FakeConn()
        q_layer3A_recent_workouts(conn, 1, date(2026, 5, 20))
        _, params = conn.calls[0]
        assert params == (1, "2026-04-23")


# ─── q_layer3A_recent_wellness ───────────────────────────────────────────────


def _garmin_wellness_row(
    *,
    date_str: str,
    sleep_start_ms: int | None = None,
    sleep_end_ms: int | None = None,
    hrv_overnight_avg_ms: float | None = None,
    resting_hr: int | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "date": date_str,
        "sleep_start_ms": sleep_start_ms,
        "sleep_end_ms": sleep_end_ms,
        "hrv_overnight_avg_ms": hrv_overnight_avg_ms,
        "resting_hr": resting_hr,
        "updated_at": updated_at,
    }


class TestRecentWellness:
    def test_empty_all_sources(self):
        conn = _FakeConn()
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert out == []
        # Five SELECTs: garmin, polar sleep, polar hrv, coros, whoop daily.
        assert len(conn.calls) == 5

    def test_default_window_14d(self):
        conn = _FakeConn()
        q_layer3A_recent_wellness(conn, 1, _AS_OF)
        # 14d inclusive window on 2026-05-20 → cutoff 2026-05-07.
        assert conn.calls[0][1] == (1, "2026-05-07")

    def test_garmin_all_three_metrics(self):
        conn = _FakeConn()
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-19",
                sleep_start_ms=0,
                sleep_end_ms=8 * 3_600_000,
                hrv_overnight_avg_ms=55.0,
                resting_hr=48,
                updated_at=datetime(2026, 5, 19, 9, 0),
            )
        )
        conn.queue()  # polar sleep
        conn.queue()  # polar hrv
        conn.queue()  # coros
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert len(out) == 1
        r = out[0]
        assert isinstance(r, DailyWellnessRecord)
        assert r.date == date(2026, 5, 19)
        assert r.total_sleep_hours == pytest.approx(8.0)
        assert r.total_sleep_hours_source == "garmin"
        assert r.hrv_rmssd_ms == 55.0
        assert r.hrv_rmssd_ms_source == "garmin"
        assert r.resting_hr == 48
        assert r.resting_hr_source == "garmin"

    def test_freshest_non_null_coalesce_across_providers(self):
        # Same day: Garmin sleep ingested earlier, Polar sleep ingested later →
        # Polar wins sleep_hours by freshness. HRV is garmin-only (no fresher
        # non-null to clobber it) so Garmin keeps HRV.
        conn = _FakeConn()
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-19",
                sleep_start_ms=0,
                sleep_end_ms=7 * 3_600_000,
                hrv_overnight_avg_ms=60.0,
                resting_hr=50,
                updated_at=datetime(2026, 5, 19, 6, 0),
            )
        )
        conn.queue(
            {
                "date": "2026-05-19",
                "total_sleep_min": 480,  # 8.0h
                "fetched_at": datetime(2026, 5, 19, 12, 0),  # fresher than garmin
            }
        )
        conn.queue()  # polar hrv
        conn.queue()  # coros
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert len(out) == 1
        r = out[0]
        assert r.total_sleep_hours == pytest.approx(8.0)
        assert r.total_sleep_hours_source == "polar"  # fresher ingest wins
        assert r.hrv_rmssd_ms == 60.0
        assert r.hrv_rmssd_ms_source == "garmin"  # only source
        assert r.resting_hr == 50
        assert r.resting_hr_source == "garmin"

    def test_null_field_never_clobbers_populated(self):
        # Polar sleep row is fresher but carries NULL minutes → it must not
        # overwrite the older but populated Garmin sleep value.
        conn = _FakeConn()
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-18",
                sleep_start_ms=0,
                sleep_end_ms=6 * 3_600_000,
                updated_at=datetime(2026, 5, 18, 6, 0),
            )
        )
        conn.queue(
            {
                "date": "2026-05-18",
                "total_sleep_min": None,
                "fetched_at": datetime(2026, 5, 18, 20, 0),
            }
        )
        conn.queue()  # polar hrv
        conn.queue()  # coros
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert len(out) == 1
        assert out[0].total_sleep_hours == pytest.approx(6.0)
        assert out[0].total_sleep_hours_source == "garmin"

    def test_priority_tiebreak_on_equal_timestamp(self):
        # Garmin + COROS report sleep for the same day with identical ingest
        # timestamps → garmin wins on the deterministic priority tiebreak.
        ts = datetime(2026, 5, 17, 7, 0)
        conn = _FakeConn()
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-17",
                sleep_start_ms=0,
                sleep_end_ms=7 * 3_600_000,
                updated_at=ts,
            )
        )
        conn.queue()  # polar sleep
        conn.queue()  # polar hrv
        conn.queue(
            {
                "date": "2026-05-17",
                "sleep_start_ms": 0,
                "sleep_end_ms": 9 * 3_600_000,
                "ppg_hrv": None,
                "fetched_at": ts,
            }
        )
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert out[0].total_sleep_hours == pytest.approx(7.0)
        assert out[0].total_sleep_hours_source == "garmin"

    def test_coros_contributes_sleep_and_hrv(self):
        conn = _FakeConn()
        conn.queue()  # garmin
        conn.queue()  # polar sleep
        conn.queue()  # polar hrv
        conn.queue(
            {
                "date": "2026-05-16",
                "sleep_start_ms": 0,
                "sleep_end_ms": 8 * 3_600_000,
                "ppg_hrv": 47.0,
                "fetched_at": datetime(2026, 5, 16, 8, 0),
            }
        )
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert len(out) == 1
        r = out[0]
        assert r.total_sleep_hours == pytest.approx(8.0)
        assert r.total_sleep_hours_source == "coros"
        assert r.hrv_rmssd_ms == 47.0
        assert r.hrv_rmssd_ms_source == "coros"
        # No device reports resting HR here → stays None.
        assert r.resting_hr is None
        assert r.resting_hr_source is None

    def test_whoop_contributes_sleep_hrv_and_resting_hr(self):
        # #767 slice 4: a Whoop daily_summary row feeds all three metrics —
        # and resting_hr from a non-Garmin source for the first time.
        conn = _FakeConn()
        conn.queue()  # garmin
        conn.queue()  # polar sleep
        conn.queue()  # polar hrv
        conn.queue()  # coros
        conn.queue(
            {
                "date": "2026-05-18",
                "total_sleep_min": 450.0,  # 7.5h
                "hrv_rmssd_ms": 72.0,
                "resting_hr": 44.0,
                "fetched_at": datetime(2026, 5, 18, 7, 0),
            }
        )
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert len(out) == 1
        r = out[0]
        assert r.total_sleep_hours == pytest.approx(7.5)
        assert r.total_sleep_hours_source == "whoop"
        assert r.hrv_rmssd_ms == 72.0
        assert r.hrv_rmssd_ms_source == "whoop"
        assert r.resting_hr == 44
        assert r.resting_hr_source == "whoop"

    def test_whoop_priority_below_garmin_above_polar_on_tie(self):
        # Equal ingest timestamps: garmin beats whoop (sleep); whoop beats polar
        # (HRV). Confirms the garmin>whoop>polar>coros tiebreak order.
        ts = datetime(2026, 5, 17, 7, 0)
        conn = _FakeConn()
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-17",
                sleep_start_ms=0,
                sleep_end_ms=7 * 3_600_000,
                updated_at=ts,
            )
        )
        conn.queue()  # polar sleep
        conn.queue(
            {"date": "2026-05-17", "hrv_rmssd_ms": 50.0, "fetched_at": ts}
        )  # polar hrv
        conn.queue()  # coros
        conn.queue(
            {
                "date": "2026-05-17",
                "total_sleep_min": 540.0,  # 9.0h — loses to garmin on tie
                "hrv_rmssd_ms": 65.0,      # beats polar on tie
                "resting_hr": None,
                "fetched_at": ts,
            }
        )
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert len(out) == 1
        r = out[0]
        assert r.total_sleep_hours == pytest.approx(7.0)
        assert r.total_sleep_hours_source == "garmin"  # garmin > whoop
        assert r.hrv_rmssd_ms == 65.0
        assert r.hrv_rmssd_ms_source == "whoop"  # whoop > polar

    def test_multi_day_sorted_desc(self):
        conn = _FakeConn()
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-17", sleep_start_ms=0, sleep_end_ms=7 * 3_600_000
            ),
            _garmin_wellness_row(
                date_str="2026-05-19", sleep_start_ms=0, sleep_end_ms=8 * 3_600_000
            ),
        )
        conn.queue()  # polar sleep
        conn.queue()  # polar hrv
        conn.queue()  # coros
        out = q_layer3A_recent_wellness(conn, 1, _AS_OF)
        assert [r.date for r in out] == [date(2026, 5, 19), date(2026, 5, 17)]


# ─── q_layer3A_recent_self_report_sleep ──────────────────────────────────────


class TestRecentSelfReportSleep:
    def test_empty(self):
        conn = _FakeConn()
        out = q_layer3A_recent_self_report_sleep(conn, 1, _AS_OF)
        assert out == []
        assert len(conn.calls) == 1

    def test_rows(self):
        conn = _FakeConn()
        conn.queue(
            {"date": "2026-05-19", "sleep_hours": 7.5, "sleep_quality": 8},
            {"date": "2026-05-18", "sleep_hours": 6.0, "sleep_quality": 5},
        )
        out = q_layer3A_recent_self_report_sleep(conn, 1, _AS_OF)
        assert len(out) == 2
        assert all(r.source == "wellness_self_report" for r in out)
        assert out[0].sleep_quality == 8
        assert out[0].total_sleep_hours == 7.5

    def test_default_window_14d(self):
        conn = _FakeConn()
        q_layer3A_recent_self_report_sleep(conn, 1, _AS_OF)
        assert conn.calls[0][1] == (1, "2026-05-07")


# ─── q_layer3A_combined_load ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ratio, expected_zone",
    [
        (0.0, "detraining"),
        (0.49, "detraining"),
        (0.5, "undertraining"),
        (0.79, "undertraining"),
        (0.8, "sweet_spot"),
        (1.0, "sweet_spot"),
        (1.3, "sweet_spot"),
        (1.31, "functional_overreach"),
        (1.5, "functional_overreach"),
        (1.51, "non_functional_overreach"),
        (2.5, "non_functional_overreach"),
    ],
)
def test_classify_zone(ratio, expected_zone):
    assert _classify_zone(ratio) == expected_zone


def test_compute_acwr_no_data_returns_none():
    assert _compute_acwr(0.0, 0.0, 28, 7) is None


def test_compute_acwr_no_base_sentinel():
    e = _compute_acwr(5.0, 0.0, 28, 7)
    assert e is not None
    assert e.zone == "non_functional_overreach"
    # ratio is the sentinel-class value
    assert e.ratio >= 100.0


def test_compute_acwr_steady_state_sweet_spot():
    # 10 hours/week chronic, 10 hours acute → ratio 1.0
    e = _compute_acwr(10.0, 40.0, 28, 7)
    assert e is not None
    assert e.ratio == pytest.approx(1.0)
    assert e.zone == "sweet_spot"
    assert e.units == "hours"


class TestCombinedLoad:
    def test_empty(self):
        conn = _FakeConn()
        conn.queue()  # cardio_log
        conn.queue()  # polar_cardio_load
        out = q_layer3A_combined_load(conn, 1, _AS_OF)
        assert isinstance(out, CombinedLoadReport)
        assert out.per_discipline == {}
        assert out.combined is None
        assert out.polar_cross_ref is None
        assert out.units == "hours"

    def test_single_discipline_sweet_spot(self):
        # 7 days × 60min/day acute = 7 hours acute; 28 days × 60min/day = 28
        # hours chronic; ratio = 7 / (28/4) = 1.0 → sweet_spot.
        rows = []
        for i in range(28):
            day = (_AS_OF.date().replace(day=1)).isoformat()  # placeholder
            d = (_AS_OF.date() - __import__("datetime").timedelta(days=i)).isoformat()
            rows.append({"date": d, "activity": "Run", "duration_min": 60.0, "moving_time_min": None})
        conn = _FakeConn()
        conn.queue(*rows)
        conn.queue()  # polar cross-ref empty
        out = q_layer3A_combined_load(conn, 1, _AS_OF)
        assert "Run" in out.per_discipline
        entry = out.per_discipline["Run"]
        # Acute = 7h (last 7 days incl _AS_OF), chronic = 28h
        assert entry.acute_load == pytest.approx(7.0)
        assert entry.chronic_load == pytest.approx(28.0)
        assert entry.ratio == pytest.approx(1.0)
        assert entry.zone == "sweet_spot"
        assert out.combined is not None
        assert out.combined.ratio == pytest.approx(1.0)

    def test_multi_discipline_independent_acwr(self):
        rows = [
            # Last 7 days: 5 Run sessions @ 60min, 0 MTB
            {"date": "2026-05-19", "activity": "Run", "duration_min": 60.0, "moving_time_min": None},
            {"date": "2026-05-18", "activity": "Run", "duration_min": 60.0, "moving_time_min": None},
            {"date": "2026-05-17", "activity": "Run", "duration_min": 60.0, "moving_time_min": None},
            # 8+ days ago: MTB only
            {"date": "2026-05-10", "activity": "MTB", "duration_min": 120.0, "moving_time_min": None},
            {"date": "2026-05-03", "activity": "MTB", "duration_min": 120.0, "moving_time_min": None},
        ]
        conn = _FakeConn()
        conn.queue(*rows)
        conn.queue()
        out = q_layer3A_combined_load(conn, 1, _AS_OF)
        # Run has 3h acute, 3h chronic → ratio = 3 / (3/4) = 4 → NFOR
        assert out.per_discipline["Run"].acute_load == pytest.approx(3.0)
        # MTB has 0h acute, 4h chronic → ratio = 0/(4/4) = 0 → detraining
        assert out.per_discipline["MTB"].acute_load == 0.0
        assert out.per_discipline["MTB"].zone == "detraining"

    def test_prefers_moving_time_over_duration(self):
        rows = [
            {
                "date": "2026-05-19",
                "activity": "Run",
                "duration_min": 60.0,
                "moving_time_min": 50.0,
            },
        ]
        conn = _FakeConn()
        conn.queue(*rows)
        conn.queue()
        out = q_layer3A_combined_load(conn, 1, _AS_OF)
        # 50min = 0.833h
        assert out.per_discipline["Run"].acute_load == pytest.approx(50.0 / 60.0, abs=0.01)

    def test_polar_cross_ref_populated(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(
            {
                "date": "2026-05-19",
                "daily_load": 220.0,
                "acute_load": 180.0,
                "chronic_load": 200.0,
                "cardio_load_status": "productive",
                "strain": 14.5,
            }
        )
        out = q_layer3A_combined_load(conn, 1, _AS_OF)
        assert out.polar_cross_ref is not None
        assert out.polar_cross_ref.daily_load == 220.0
        assert out.polar_cross_ref.cardio_load_status == "productive"

    def test_skips_null_duration_rows(self):
        conn = _FakeConn()
        conn.queue(
            {"date": "2026-05-19", "activity": "Run", "duration_min": None, "moving_time_min": None},
            {"date": "2026-05-18", "activity": "Run", "duration_min": 0, "moving_time_min": None},
            {"date": "2026-05-17", "activity": "Run", "duration_min": 30.0, "moving_time_min": None},
        )
        conn.queue()
        out = q_layer3A_combined_load(conn, 1, _AS_OF)
        # Only the 30-min row counts: 0.5h acute, 0.5h chronic → ratio = 4.0 → NFOR
        assert out.per_discipline["Run"].acute_load == pytest.approx(0.5)


# ─── q_layer3A_connected_providers ───────────────────────────────────────────


class TestConnectedProviders:
    def test_no_providers(self):
        conn = _FakeConn()
        for _ in range(7):
            conn.queue()  # all 7 queries return nothing
        out = q_layer3A_connected_providers(conn, 1, as_of=_AS_OF)
        assert out == []

    def test_polar_full_coverage(self):
        conn = _FakeConn()
        conn.queue({"provider": "polar", "status": "active", "updated_at": datetime(2026, 5, 20)})
        conn.queue({"provider": "polar", "last_received": datetime(2026, 5, 20, 8, 0)})
        # cardio_log filter counts
        conn.queue({"garmin_n": 0, "polar_n": 5, "wahoo_n": 0, "coros_n": 0})
        # polar_sleep count
        conn.queue({"n": 12})
        # coros_daily_summary sleep
        conn.queue({"n": 0})
        # polar_nightly_recharge hrv
        conn.queue({"n": 10})
        # coros_daily_summary hrv
        conn.queue({"n": 0})
        out = q_layer3A_connected_providers(conn, 1, as_of=_AS_OF)
        assert len(out) == 1
        p = out[0]
        assert p.provider == "polar"
        assert p.status == "active"
        assert p.has_recent_workouts is True
        assert p.has_recent_sleep is True
        assert p.has_recent_hrv is True
        # last_sync is day-anchored (cache-key determinism) — 08:00 → midnight.
        assert p.last_sync == datetime(2026, 5, 20, 0, 0)

    def test_coros_workouts_but_no_sleep_or_hrv(self):
        conn = _FakeConn()
        conn.queue({"provider": "coros", "status": "active", "updated_at": None})
        conn.queue()  # no webhook history
        conn.queue({"garmin_n": 0, "polar_n": 0, "wahoo_n": 0, "coros_n": 8})
        conn.queue({"n": 0})  # polar sleep
        conn.queue({"n": 0})  # coros sleep (no rows in window)
        conn.queue({"n": 0})  # polar hrv
        conn.queue({"n": 0})  # coros hrv
        out = q_layer3A_connected_providers(conn, 1, as_of=_AS_OF)
        assert len(out) == 1
        p = out[0]
        assert p.has_recent_workouts is True
        assert p.has_recent_sleep is False
        assert p.has_recent_hrv is False
        assert p.last_sync is None

    def test_none_as_of_fallback_uses_day_anchored_cutoffs(self):
        """`as_of=None` falls back to a day-anchored anchor (not full-precision
        `datetime.now()`), so the date cutoffs sent to SQL are stable within a
        calendar day. Those cutoffs drive the provider-coverage flags that ride
        in the integration bundle whose hash folds into the 3A cache key, so a
        sub-day fallback would drift that key across resumable passes."""
        def _cutoffs() -> list[Any]:
            conn = _FakeConn()
            for _ in range(7):
                conn.queue()
            q_layer3A_connected_providers(conn, 1)  # as_of omitted → fallback
            # Queries 3-5 (cardio_log / polar_sleep / polar_hrv) carry the
            # workout/sleep/hrv date cutoffs as their second bound param.
            return [conn.calls[i][1][1] for i in (2, 3, 5)]

        cutoffs = _cutoffs()
        # Each cutoff is a pure ISO date (YYYY-MM-DD), never a timestamp.
        assert all(len(c) == 10 and c.count("-") == 2 for c in cutoffs)
        # Stable across calls — the fallback is day-granular, not wall-clock.
        assert _cutoffs() == cutoffs

    def test_last_sync_is_day_anchored(self):
        """last_sync = MAX(received_at) folds (via the integration-bundle hash)
        into the 3A cache key; a sub-day value drifts that key when a provider
        checks in mid-generation, so 3A re-runs every resumable pass and every
        Layer 4 block is orphaned (the D-77 non-convergence reproduced on the
        prod re-run). MAX(received_at) values on the same calendar day at
        different times must collapse to one day-anchored last_sync."""
        def _last_sync(received_at: datetime):
            conn = _FakeConn()
            conn.queue({"provider": "polar", "status": "active", "updated_at": None})
            conn.queue({"provider": "polar", "last_received": received_at})
            conn.queue({"garmin_n": 0, "polar_n": 1, "wahoo_n": 0, "coros_n": 0})
            conn.queue({"n": 0}); conn.queue({"n": 0})
            conn.queue({"n": 0}); conn.queue({"n": 0})
            return q_layer3A_connected_providers(conn, 1, as_of=_AS_OF)[0].last_sync

        morning = _last_sync(datetime(2026, 5, 20, 8, 15, 30))
        night = _last_sync(datetime(2026, 5, 20, 23, 59, 59))
        assert morning == night == datetime(2026, 5, 20, 0, 0, 0)


# ─── assemble_layer3a_integration_bundle ─────────────────────────────────────


class TestAssembleBundle:
    def test_full_compose(self):
        conn = _FakeConn()
        # q_layer3A_recent_workouts: 1 query
        conn.queue(_workout_row(date_str="2026-05-19", activity="Run"))
        # q_layer3A_recent_wellness: 5 queries (garmin, polar sleep, polar hrv,
        # coros, whoop)
        conn.queue(
            _garmin_wellness_row(
                date_str="2026-05-19",
                sleep_start_ms=0,
                sleep_end_ms=8 * 3_600_000,
                hrv_overnight_avg_ms=55.0,
                resting_hr=48,
            )
        )
        conn.queue()
        conn.queue()
        conn.queue()
        conn.queue()
        # q_layer3A_recent_self_report_sleep: 1 query
        conn.queue({"date": "2026-05-19", "sleep_hours": 7.5, "sleep_quality": 8})
        # q_layer3A_combined_load: 2 queries
        conn.queue(
            {"date": "2026-05-19", "activity": "Run", "duration_min": 60.0, "moving_time_min": None}
        )
        conn.queue()
        # q_layer3A_connected_providers: 7 queries
        conn.queue({"provider": "polar", "status": "active", "updated_at": None})
        conn.queue()
        conn.queue({"garmin_n": 0, "polar_n": 0, "wahoo_n": 0, "coros_n": 0})
        conn.queue({"n": 0})
        conn.queue({"n": 0})
        conn.queue({"n": 0})
        conn.queue({"n": 0})

        bundle = assemble_layer3a_integration_bundle(conn, 1, _AS_OF)
        assert isinstance(bundle, Layer3AIntegrationBundle)
        assert bundle.as_of == _AS_OF
        assert len(bundle.recent_workouts) == 1
        assert len(bundle.recent_wellness) == 1
        assert bundle.recent_wellness[0].resting_hr == 48
        assert bundle.recent_wellness[0].hrv_rmssd_ms == 55.0
        assert len(bundle.recent_self_report_sleep) == 1
        assert bundle.combined_load.combined is not None
        assert len(bundle.connected_providers) == 1
        assert bundle.connected_providers[0].provider == "polar"

    def test_empty_bundle_compose(self):
        """No data anywhere — every accessor returns an empty/None shape, and
        the bundle still constructs (the §10.2 "no providers connected" + the
        §10.1 "just-onboarded athlete" path)."""
        conn = _FakeConn()
        for _ in range(16):  # 1 + 5 + 1 + 2 + 7
            conn.queue()
        bundle = assemble_layer3a_integration_bundle(conn, 1, _AS_OF)
        assert bundle.recent_workouts == []
        assert bundle.recent_wellness == []
        assert bundle.recent_self_report_sleep == []
        assert bundle.combined_load.per_discipline == {}
        assert bundle.combined_load.combined is None
        assert bundle.combined_load.polar_cross_ref is None
        assert bundle.connected_providers == []

    def test_bundle_hash_is_deterministic_across_passes(self):
        """The integration-bundle hash folds into the 3A cache key
        (`layer3a_athlete_state_key`); a fresh full-precision timestamp
        anywhere in the bundle or its accessors would drift that key on every
        resumable pass and re-run 3A cold — the c4f9160 / D-77 non-convergence
        class. Two assembles with the same day-anchored `as_of` and identical
        DB responses must hash identically."""
        def _assemble() -> Layer3AIntegrationBundle:
            conn = _FakeConn()
            for _ in range(16):  # 1 + 5 + 1 + 2 + 7
                conn.queue()
            return assemble_layer3a_integration_bundle(conn, 1, _AS_OF)

        assert compute_payload_hash(_assemble()) == compute_payload_hash(_assemble())
