"""Tests for #681 §4 Slice 3 — Polar/COROS wellness consolidation.

The per-provider bespoke wellness tables (polar_sleep / polar_nightly_recharge /
polar_cardio_load / polar_continuous_hr_samples / coros_daily_summary /
coros_hrv_samples) were retired. Daily wellness now records into the canonical
`provider_raw_record` (provider-tagged, record-don't-drop) and per-sample HR into
`wellness_log`.

These assert the writers emit well-formed SQL against the canonical tables (right
columns, ::jsonb cast, ON CONFLICT) and never touch a dropped table. The Slice 2c
lesson (#752) was that a fake-DB unit test must at least verify the SQL/params,
since the real SQL never runs in CI — the live JSONB-extraction read path is the
carried coverage gap (no public-schema Postgres test).
"""
import json

import routes.coros_ingest as coros
import routes.polar_ingest as polar


class _FakeCursor:
    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakeCursor()


def _raw_insert(conn):
    return next((c for c in conn.calls if "INSERT INTO provider_raw_record" in c[0]), None)


def _wellness_insert(conn):
    return next((c for c in conn.calls if "INSERT INTO wellness_log" in c[0]), None)


_BESPOKE = ("polar_sleep", "polar_nightly_recharge", "polar_cardio_load",
            "polar_continuous_hr_samples", "coros_daily_summary", "coros_hrv_samples")


def _no_bespoke_writes(conn):
    for sql, _ in conn.calls:
        for t in _BESPOKE:
            assert t not in sql, f"writer still touches dropped table {t}: {sql[:60]!r}"


# ── Polar ──────────────────────────────────────────────────────────────────

class TestPolarSleep:
    def test_records_into_provider_raw_record(self, monkeypatch):
        monkeypatch.setattr(polar, "_get_json", lambda url, tok: {"nights": [
            {"date": "2026-06-02", "total_sleep_min": 432, "light_sleep_min": 200,
             "deep_sleep_min": 90, "rem_sleep_min": 100, "continuity": 2.1}]})
        conn = _FakeConn()
        polar._ingest_sleep(conn, 7, "pu", "tok", {})
        sql, params = _raw_insert(conn)
        assert "::jsonb" in sql and "ON CONFLICT" in sql
        assert params[0] == 7
        assert params[1:4] == ("polar", "sleep", "2026-06-02")
        assert params[4] == "2026-06-02"                 # observed_at mirrors the day
        payload = json.loads(params[5])
        assert payload["total_sleep_min"] == 432
        assert payload["deep_sleep_min"] == 90
        assert payload["_raw"]["date"] == "2026-06-02"   # record-don't-drop
        _no_bespoke_writes(conn)


class TestPolarNightlyRecharge:
    def test_records_hrv_data_type(self, monkeypatch):
        monkeypatch.setattr(polar, "_get_json", lambda url, tok: {"recharges": [
            {"date": "2026-06-02", "hrv_rmssd_ms": 58.5, "ans_charge": 3,
             "breathing_rate": 13.2}]})
        conn = _FakeConn()
        polar._ingest_nightly_recharge(conn, 7, "pu", "tok", {})
        sql, params = _raw_insert(conn)
        assert params[1:4] == ("polar", "hrv", "2026-06-02")
        assert json.loads(params[5])["hrv_rmssd_ms"] == 58.5
        _no_bespoke_writes(conn)


class TestPolarCardioLoad:
    def test_records_cardio_load_data_type(self, monkeypatch):
        monkeypatch.setattr(polar, "_get_json", lambda url, tok: {"loads": [
            {"date": "2026-06-02", "daily_load": 120.0, "acute_load": 80.0,
             "chronic_load": 95.0, "cardio_load_status": "MAINTAINING",
             "strain": 1.1}]})
        conn = _FakeConn()
        polar._ingest_cardio_load(conn, 7, "pu", "tok", {})
        sql, params = _raw_insert(conn)
        assert params[1:4] == ("polar", "cardio_load", "2026-06-02")
        p = json.loads(params[5])
        assert p["acute_load"] == 80.0 and p["chronic_load"] == 95.0
        assert p["cardio_load_status"] == "MAINTAINING"
        _no_bespoke_writes(conn)


class TestPolarContinuousHr:
    def test_records_into_wellness_log_with_source(self, monkeypatch):
        monkeypatch.setattr(polar, "_get_json", lambda url, tok: {"samples": [
            {"timestamp_ms": 1779959815000, "heart_rate": 61}]})
        conn = _FakeConn()
        polar._ingest_continuous_hr(conn, 7, "pu", "tok", {})
        sql, params = _wellness_insert(conn)
        assert "ON CONFLICT (user_id, timestamp_ms)" in sql
        assert params[0] == 7
        assert params[2] == 1779959815000           # timestamp_ms (already ms)
        assert params[3] == 61                       # heart_rate
        assert params[4] == "polar"                  # source
        assert _raw_insert(conn) is None             # HR samples don't go to raw
        _no_bespoke_writes(conn)


# ── COROS ──────────────────────────────────────────────────────────────────

class TestCorosDailySummary:
    def test_records_into_provider_raw_record(self):
        conn = _FakeConn()
        coros._ingest_daily_summary(conn, 9, {
            "happenDay": "2026-06-03", "rhr": 48, "steps": 8200, "calories": 540,
            "ppgHrv": 62, "sleepAvgHr": 52, "sleepStartTime": 1000,
            "sleepEndTime": 2000})
        sql, params = _raw_insert(conn)
        assert "::jsonb" in sql and "ON CONFLICT" in sql
        assert params[0] == 9
        assert params[1:4] == ("coros", "daily_summary", "2026-06-03")
        p = json.loads(params[5])
        assert p["rhr"] == 48 and p["ppg_hrv"] == 62 and p["steps"] == 8200
        assert p["sleep_start_ms"] == 1000 and p["sleep_end_ms"] == 2000
        _no_bespoke_writes(conn)

    def test_integer_happen_day_normalised_to_iso(self):
        conn = _FakeConn()
        coros._ingest_daily_summary(conn, 9, {"happenDay": 20260603, "rhr": 50})
        assert _raw_insert(conn)[1][3] == "2026-06-03"


class TestCorosHrvSample:
    def test_hr_into_wellness_log_seconds_to_ms(self):
        conn = _FakeConn()
        coros._ingest_hrv_sample(conn, 9, {"timestamp": 1779959815, "hrv": 40, "hr": 58})
        sql, params = _wellness_insert(conn)
        assert params[2] == 1779959815 * 1000        # COROS HRV ts is seconds → ms
        assert params[3] == 58                        # hr (the per-sample HRV is dropped)
        assert params[4] == "coros"                   # source
        assert _raw_insert(conn) is None              # no raw row for a bare HRV sample
        _no_bespoke_writes(conn)
