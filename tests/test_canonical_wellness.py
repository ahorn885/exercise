"""Tests for the #196 Phase 2 canonical daily-wellness writer
(`canonical_wellness.materialize_canonical_wellness`).

A fake connection feeds canned Garmin (`daily_wellness_metrics`) + non-Garmin
(`provider_raw_record`) rows and captures the upsert, so the coalesce + context
copy + idempotent-upsert SQL are verified without a live Postgres (Neon egress
is blocked in the container). The behavioural collapse against real data is the
Slice-2.3 reader-equality test + a prod live-verify.
"""
from __future__ import annotations

from datetime import datetime

import canonical_wellness as cw


class _Cursor:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Routes the writer's reads by table/params; records every call."""

    def __init__(self, garmin=None, prr=None):
        self.garmin = garmin            # dict (one daily_wellness_metrics row) or None
        self.prr = prr or {}            # {(provider, data_type): [rows]}
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        s = " ".join(sql.split())
        if "FROM daily_wellness_metrics" in s:
            return _Cursor(one=self.garmin)
        if "FROM provider_raw_record" in s:
            return _Cursor(rows=self.prr.get((params[1], params[2]), []))
        return _Cursor()  # DELETE / INSERT canonical_daily_wellness


def _garmin_row(**kw):
    base = {
        "sleep_start_ms": None, "sleep_end_ms": None, "hrv_overnight_avg_ms": None,
        "resting_hr": None, "hrv_7d_avg_ms": None, "resting_hr_7day_avg": None,
        "sleep_score": None, "training_readiness": None, "vo2max_running": None,
        "vo2max_cycling": None, "acute_training_load": None,
        "updated_at": datetime(2026, 6, 20, 8, 0, 0),
    }
    base.update(kw)
    return base


def _prr_row(payload, fetched_at):
    return {"raw_payload": payload, "fetched_at": fetched_at}


def _upsert(conn):
    """The captured INSERT … ON CONFLICT call, as a {column: value} dict."""
    sql, params = next((c for c in conn.calls if "INSERT INTO canonical_daily_wellness" in c[0]), (None, None))
    if sql is None:
        return None
    cols = ("user_id", "date", *cw._COALESCED_COLS, *cw._GARMIN_CTX_COLS)
    return dict(zip(cols, params)), sql


class TestCoalesce:
    def test_freshest_non_null_wins_per_field(self):
        # Garmin carries all three (older ingest); Whoop carries a FRESHER hrv +
        # rhr. Sleep stays Garmin (only it has sleep that day); hrv/rhr flip Whoop.
        conn = _FakeConn(
            garmin=_garmin_row(
                sleep_start_ms=0, sleep_end_ms=8 * 3600_000,  # 8.0 h
                hrv_overnight_avg_ms=55.0, resting_hr=48,
                updated_at=datetime(2026, 6, 20, 6, 0, 0)),
            prr={("whoop", "daily_summary"): [_prr_row(
                {"hrv_rmssd_ms": 70.0, "resting_hr": 45},
                datetime(2026, 6, 20, 9, 0, 0))]},
        )
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        row, _ = _upsert(conn)
        assert row["total_sleep_hours"] == 8.0
        assert row["total_sleep_hours_source"] == "garmin"
        assert row["hrv_rmssd_ms"] == 70.0 and row["hrv_rmssd_ms_source"] == "whoop"
        assert row["resting_hr"] == 45 and row["resting_hr_source"] == "whoop"

    def test_priority_tiebreak_when_timestamps_equal(self):
        # Equal ingest timestamps → garmin (priority 5) beats coros (priority 1).
        ts = datetime(2026, 6, 20, 7, 0, 0)
        conn = _FakeConn(
            garmin=_garmin_row(hrv_overnight_avg_ms=60.0, updated_at=ts),
            prr={("coros", "daily_summary"): [_prr_row({"ppg_hrv": 99}, ts)]},
        )
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        row, _ = _upsert(conn)
        assert row["hrv_rmssd_ms"] == 60.0 and row["hrv_rmssd_ms_source"] == "garmin"

    def test_resting_hr_rounded_to_int(self):
        conn = _FakeConn(prr={("oura", "daily_summary"): [_prr_row(
            {"resting_hr": 47.6}, datetime(2026, 6, 20, 5, 0, 0))]})
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        row, _ = _upsert(conn)
        assert row["resting_hr"] == 48 and row["resting_hr_source"] == "oura"


class TestContextFields:
    def test_garmin_context_copied(self):
        conn = _FakeConn(garmin=_garmin_row(
            hrv_7d_avg_ms=58.0, resting_hr_7day_avg=49, sleep_score=82,
            training_readiness=71, vo2max_running=54.0, vo2max_cycling=49.0,
            acute_training_load=320))
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        row, _ = _upsert(conn)
        assert row["training_readiness"] == 71
        assert row["hrv_7d_avg_ms"] == 58.0
        assert row["vo2max_running"] == 54.0
        assert row["acute_training_load"] == 320

    def test_context_fields_alone_still_write_a_row(self):
        # A day with only Garmin context (no coalesced sleep/hrv/rhr) still
        # materializes — readiness/vo2max are Phase-4 inputs worth persisting.
        conn = _FakeConn(garmin=_garmin_row(training_readiness=65))
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        assert _upsert(conn) is not None


class TestUpsertShape:
    def test_upsert_is_idempotent_on_user_date(self):
        conn = _FakeConn(garmin=_garmin_row(resting_hr=50))
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        _, sql = _upsert(conn)
        assert "ON CONFLICT (user_id, date) DO UPDATE" in " ".join(sql.split())

    def test_no_data_clears_and_skips_insert(self):
        conn = _FakeConn(garmin=None)  # no Garmin row, no provider rows
        cw.materialize_canonical_wellness(conn, 1, "2026-06-20")
        assert _upsert(conn) is None
        assert any("DELETE FROM canonical_daily_wellness" in c[0] for c in conn.calls)


class TestProviderHook:
    """`materialize_wellness_for_provider` — the ingest-route gate (Slice 2.2).
    A wellness-feeding (provider, data_type) re-materializes; anything else is a
    no-op (no canonical read/write), so non-wellness ingests stay cheap."""

    def _fired(self, provider, data_type):
        # Empty conn → if the hook fires, materialize issues its reads (+ a
        # no-data DELETE); if gated out, the conn sees zero calls.
        conn = _FakeConn(garmin=None)
        cw.materialize_wellness_for_provider(conn, 1, provider, data_type, "2026-06-20")
        return any("FROM daily_wellness_metrics" in c[0] for c in conn.calls), conn

    def test_wellness_data_types_fire(self):
        for provider, data_type in (
            ("polar", "sleep"), ("polar", "hrv"),
            ("coros", "daily_summary"), ("whoop", "daily_summary"),
            ("oura", "daily_summary"),
        ):
            fired, _ = self._fired(provider, data_type)
            assert fired, f"{provider}/{data_type} should re-materialize"

    def test_non_wellness_writes_are_no_ops(self):
        for provider, data_type in (
            ("polar", "cardio_load"), ("whoop", "workout"),
            ("coros", "exercise"), ("garmin", "daily_summary"),  # garmin not in the map
            ("oura", "tags"),
        ):
            fired, conn = self._fired(provider, data_type)
            assert not fired, f"{provider}/{data_type} must not re-materialize"
            assert conn.calls == [], f"{provider}/{data_type} touched the DB"


class _BackfillConn:
    """Serves the backfill discovery UNION its work-list, then routes each
    per-(uid, date) materialize read. Records which (uid, date) materialize ran
    for (via the daily_wellness_metrics read params)."""

    def __init__(self, targets):
        self.targets = targets            # [(user_id, date), ...] the union returns
        self.calls: list[tuple[str, tuple]] = []
        self.materialized: list[tuple[int, str]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        s = " ".join(sql.split())
        if "UNION" in s:                  # the discovery query
            return _Cursor(rows=[{"user_id": u, "date": d} for u, d in self.targets])
        if "FROM daily_wellness_metrics" in s:
            self.materialized.append((params[0], params[1]))
            return _Cursor(one=None)      # no Garmin row → no-data path
        if "FROM provider_raw_record" in s:
            return _Cursor(rows=[])
        return _Cursor()                  # DELETE canonical (no-data clear)


class TestBackfill:
    def test_targets_parsed_from_union(self):
        conn = _BackfillConn([(1, "2026-06-20"), (1, "2026-06-21"), (2, "2026-06-20")])
        targets = cw._wellness_backfill_targets(conn)
        assert targets == [(1, "2026-06-20"), (1, "2026-06-21"), (2, "2026-06-20")]
        # The discovery query unions both wellness homes.
        disco = next(c for c in conn.calls if "UNION" in " ".join(c[0].split()))[0]
        assert "FROM daily_wellness_metrics" in disco
        assert "FROM provider_raw_record" in disco

    def test_backfill_materializes_each_target(self):
        targets = [(1, "2026-06-20"), (1, "2026-06-21"), (7, "2026-06-19")]
        conn = _BackfillConn(targets)
        n = cw.backfill_canonical_wellness(conn)
        assert n == 3
        assert conn.materialized == targets  # materialize ran once per (user, date)

    def test_backfill_user_scope_filters_query(self):
        conn = _BackfillConn([(5, "2026-06-20")])
        cw._wellness_backfill_targets(conn, uid=5)
        disco_sql, disco_params = next(
            c for c in conn.calls if "UNION" in " ".join(c[0].split()))
        assert disco_params == (5, 5)             # filter bound to both union halves
        assert "user_id = %s" in disco_sql
