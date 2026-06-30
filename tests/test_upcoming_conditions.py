"""Tests for the #289 live upcoming-conditions producer + #964 consumer plumbing.

Covers:
- `weather_client.get_upcoming_forecast` — parse, best-effort degrade, null/bad-day skip.
- `upcoming_conditions_repo` — upsert SQL/params + prune.
- `layer5.upcoming_conditions` — the producer (day-window, representative locale,
  empty-forecast no-op, no-plan / no-coords guards) + the batch's per-user isolation.
- `routes.conditions.cron_refresh_conditions` — token gate + clean commit.

A `_FakeConn` serves queued responses in execute order so the assembly runs
without a real DB; a stub `fetcher` feeds `weather_client` canned data so no
network is touched.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest  # noqa: F401  (monkeypatch fixture)

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-conditions')
os.environ['DATABASE_URL'] = ''

from layer4.payload import CardioBlock, HRTarget, PlanSession
from weather_client import DayForecast, get_upcoming_forecast

USER_ID = 7
PVID = 99
TODAY = date(2026, 6, 28)
IN_WINDOW = date(2026, 7, 1)      # 3 days out — inside the 7-day horizon
OUT_OF_WINDOW = date(2026, 7, 20)  # 22 days out — beyond the horizon


# ─── fake connection ─────────────────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []
        self.commits = 0

    def queue(self, row=None, rows=None):
        self.responses.append((row, rows or []))
        return self

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        row, rows = self.responses.pop(0) if self.responses else (None, [])
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        self.commits += 1


# ─── fixtures ────────────────────────────────────────────────────────────────


def _session(d: date, locale_id: str | None = "park") -> PlanSession:
    return PlanSession(
        session_id=f"c-{d.isoformat()}",
        plan_version_id=PVID,
        date=d,
        day_of_week="Wed",
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Running",
        locale_id=locale_id,
        locale_name="City Park" if locale_id else None,
        duration_min=60,
        intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=140),
                instructions="steady",
            )
        ],
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _row(d: date, locale_id="park"):
    return {"payload_json": _session(d, locale_id).model_dump(mode="json")}


def _forecast_fetcher(url, params):
    """Canned Open-Meteo forecast: one hot, wet day on IN_WINDOW."""
    return {
        "daily": {
            "time": [IN_WINDOW.isoformat()],
            "temperature_2m_max": [33.0],
            "temperature_2m_min": [18.0],
            "precipitation_probability_max": [70],
        }
    }


def _empty_fetcher(url, params):
    return None


# ─── weather_client.get_upcoming_forecast ────────────────────────────────────


def test_forecast_parses_per_day_triple():
    def fetcher(url, params):
        return {
            "daily": {
                "time": ["2026-07-01", "2026-07-02"],
                "temperature_2m_max": [33.0, 21.4],
                "temperature_2m_min": [18.0, 9.9],
                "precipitation_probability_max": [70, 10],
            }
        }

    out = get_upcoming_forecast(51.5, -0.12, date(2026, 7, 1), date(2026, 7, 2),
                                fetcher=fetcher)
    assert out == {
        date(2026, 7, 1): DayForecast(33.0, 18.0, 70),
        date(2026, 7, 2): DayForecast(21.4, 9.9, 10),
    }


def test_forecast_missing_coords_returns_empty():
    # No fetch attempted when coordinates are absent.
    sentinel = {"called": False}

    def fetcher(url, params):
        sentinel["called"] = True
        return {}

    assert get_upcoming_forecast(None, -0.12, TODAY, IN_WINDOW, fetcher=fetcher) == {}
    assert sentinel["called"] is False


def test_forecast_network_fault_returns_empty():
    assert get_upcoming_forecast(1.0, 2.0, TODAY, IN_WINDOW, fetcher=_empty_fetcher) == {}


def test_forecast_skips_days_with_a_null_or_bad_value():
    def fetcher(url, params):
        return {
            "daily": {
                "time": ["2026-07-01", "2026-07-02", "not-a-date"],
                "temperature_2m_max": [33.0, None, 20.0],
                "temperature_2m_min": [18.0, 9.0, 8.0],
                "precipitation_probability_max": [70, 10, 5],
            }
        }

    out = get_upcoming_forecast(1.0, 2.0, date(2026, 7, 1), date(2026, 7, 3),
                                fetcher=fetcher)
    # Day 2 dropped (null high); day 3 dropped (unparseable date); day 1 kept.
    assert out == {date(2026, 7, 1): DayForecast(33.0, 18.0, 70)}


# ─── upcoming_conditions_repo ─────────────────────────────────────────────────


def test_repo_upsert_writes_each_row_with_params():
    import upcoming_conditions_repo as repo

    conn = _FakeConn()
    n = repo.upsert_upcoming_conditions(conn, USER_ID, [
        {"forecast_date": IN_WINDOW, "locale_id": "park",
         "temp_max_c": 33.0, "temp_min_c": 18.0, "precip_prob_pct": 70},
    ])
    assert n == 1
    sql, params = conn.calls[0]
    assert "INSERT INTO upcoming_conditions" in sql
    assert "ON CONFLICT (user_id, forecast_date) DO UPDATE" in sql
    assert params == (USER_ID, IN_WINDOW, "park", 33.0, 18.0, 70)


def test_repo_prune_deletes_past_only():
    import upcoming_conditions_repo as repo

    conn = _FakeConn()
    repo.prune_past(conn, USER_ID, TODAY)
    sql, params = conn.calls[0]
    assert sql.startswith("DELETE FROM upcoming_conditions")
    assert "forecast_date < ?" in sql
    assert params == (USER_ID, TODAY)


# ─── producer: refresh_upcoming_conditions_for_user ───────────────────────────


def _producer():
    import layer5.upcoming_conditions as mod
    return mod


def test_producer_happy_path_writes_in_window_day():
    conn = _FakeConn()
    conn.queue()                                    # prune DELETE
    conn.queue(row={"id": PVID})                    # active plan version
    conn.queue(rows=[_row(IN_WINDOW)])              # sessions
    conn.queue(row={"lat": 44.0, "lng": -93.0})    # coords for "park"
    conn.queue()                                    # upsert INSERT

    n = _producer().refresh_upcoming_conditions_for_user(
        conn, USER_ID, today=TODAY, fetcher=_forecast_fetcher
    )
    assert n == 1
    insert_sql, params = conn.calls[-1]
    assert "INSERT INTO upcoming_conditions" in insert_sql
    assert params == (USER_ID, IN_WINDOW, "park", 33.0, 18.0, 70)


def test_producer_no_active_plan_writes_nothing():
    conn = _FakeConn()
    conn.queue()                 # prune
    conn.queue(row=None)         # no active plan version
    assert _producer().refresh_upcoming_conditions_for_user(
        conn, USER_ID, today=TODAY, fetcher=_forecast_fetcher) == 0
    # Pruned + checked the plan; no sessions/coords/insert.
    assert not any("INSERT INTO upcoming_conditions" in c[0] for c in conn.calls)


def test_producer_ignores_out_of_window_and_localeless_sessions():
    conn = _FakeConn()
    conn.queue()                                   # prune
    conn.queue(row={"id": PVID})                   # active plan
    conn.queue(rows=[                               # sessions: none usable
        _row(OUT_OF_WINDOW),                        # in plan but beyond horizon
        _row(IN_WINDOW, locale_id=None),           # in window but no locale
    ])
    assert _producer().refresh_upcoming_conditions_for_user(
        conn, USER_ID, today=TODAY, fetcher=_forecast_fetcher) == 0
    # Bailed before any coord lookup (empty in-window located set).
    assert not any("locale_profiles" in c[0] for c in conn.calls)


def test_producer_no_coords_writes_nothing():
    conn = _FakeConn()
    conn.queue()                          # prune
    conn.queue(row={"id": PVID})          # active plan
    conn.queue(rows=[_row(IN_WINDOW)])    # sessions
    conn.queue(row=None)                  # coords missing for "park"
    assert _producer().refresh_upcoming_conditions_for_user(
        conn, USER_ID, today=TODAY, fetcher=_forecast_fetcher) == 0
    assert not any("INSERT INTO upcoming_conditions" in c[0] for c in conn.calls)


def test_producer_empty_forecast_writes_nothing():
    conn = _FakeConn()
    conn.queue()                                   # prune
    conn.queue(row={"id": PVID})                   # active plan
    conn.queue(rows=[_row(IN_WINDOW)])             # sessions
    conn.queue(row={"lat": 44.0, "lng": -93.0})   # coords
    assert _producer().refresh_upcoming_conditions_for_user(
        conn, USER_ID, today=TODAY, fetcher=_empty_fetcher) == 0
    # Forecast came back empty → no row upserted.
    assert not any("INSERT INTO upcoming_conditions" in c[0] for c in conn.calls)


# ─── batch: refresh_all_upcoming_conditions ───────────────────────────────────


def test_refresh_all_counts_users_and_isolates_failures(monkeypatch):
    mod = _producer()
    conn = _FakeConn()
    conn.queue(rows=[{"user_id": 1}, {"user_id": 2}])  # DISTINCT users

    def fake_per_user(db, uid, *, today=None, fetcher=None):
        if uid == 2:
            raise RuntimeError("forecast blew up")
        return 3

    monkeypatch.setattr(mod, "refresh_upcoming_conditions_for_user", fake_per_user)
    result = mod.refresh_all_upcoming_conditions(conn, today=TODAY)
    # User 1 counted (3 rows); user 2's exception swallowed, not counted.
    assert result == {"users": 1, "rows": 3}


# ─── route: cron_refresh_conditions ───────────────────────────────────────────


def _cron_client(monkeypatch, conn):
    import app as _appmod
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    return _appmod.app.test_client()


def test_cron_unauthorized_touches_no_db(monkeypatch):
    monkeypatch.delenv('CRON_SECRET', raising=False)
    conn = _FakeConn()
    client = _cron_client(monkeypatch, conn)
    resp = client.get('/cron/conditions/refresh')
    assert resp.status_code == 401
    assert conn.calls == []


def test_cron_authorized_refreshes_and_commits(monkeypatch):
    monkeypatch.setenv('CRON_SECRET', 's3cret')
    conn = _FakeConn()
    conn.queue(rows=[])  # DISTINCT users → none with an active plan
    client = _cron_client(monkeypatch, conn)
    resp = client.get('/cron/conditions/refresh',
                      headers={'Authorization': 'Bearer s3cret'})
    assert resp.status_code == 200
    assert resp.get_json()['refreshed'] == {'users': 0, 'rows': 0}
    assert conn.commits == 1
