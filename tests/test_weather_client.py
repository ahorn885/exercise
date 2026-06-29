"""Tests for `weather_client.get_expected_conditions`.

The fetcher is dependency-injected so no test touches the network. Covers:
- aggregation across the multi-year window (mean temps + wet-day probability)
- graceful None on missing coords / empty sample / fetch failure
- the summary_line athlete-facing rendering
"""

from __future__ import annotations

from datetime import date

from weather_client import ExpectedConditions, get_expected_conditions

_LAT = 44.32
_LNG = -93.20
_EVENT = date(2026, 7, 17)
_TODAY = date(2026, 5, 25)


def _daily(tmax, tmin, precip):
    return {
        "daily": {
            "temperature_2m_max": tmax,
            "temperature_2m_min": tmin,
            "precipitation_sum": precip,
        }
    }


class TestAggregation:
    def test_means_and_wet_probability(self):
        # Every yearly call returns the same 3-day window.
        def fetch(url, params):
            return _daily([30.0, 32.0, 28.0], [18.0, 20.0, 16.0], [0.0, 5.0, 0.5])

        ec = get_expected_conditions(_LAT, _LNG, _EVENT, today=_TODAY, fetcher=fetch)
        assert isinstance(ec, ExpectedConditions)
        # 5 years × 3 days = 15 samples; means are stable across identical windows.
        assert ec.temp_max_c == 30.0
        assert ec.temp_min_c == 18.0
        assert ec.sample_days == 15
        assert ec.sample_years == 5
        # Wet day = precip >= 1.0mm → 1 of every 3 days → 33%.
        assert ec.wet_day_probability_pct == 33

    def test_queries_five_recent_years_with_window(self):
        calls: list[dict] = []

        def fetch(url, params):
            calls.append(params)
            return _daily([25.0], [10.0], [0.0])

        get_expected_conditions(_LAT, _LNG, _EVENT, today=_TODAY, fetcher=fetch)
        # 5 yearly calls: 2021..2025 (ref_year=2026, exclusive).
        assert len(calls) == 5
        years = sorted({p["start_date"][:4] for p in calls})
        assert years == ["2021", "2022", "2023", "2024", "2025"]
        # ±3-day window around Jul 17.
        assert calls[0]["start_date"].endswith("-07-14")
        assert calls[0]["end_date"].endswith("-07-20")
        assert calls[0]["latitude"] == round(_LAT, 3)


class TestGracefulNone:
    def test_missing_coords_returns_none_without_fetching(self):
        def fetch(url, params):  # pragma: no cover - must not be called
            raise AssertionError("should not fetch without coords")

        assert get_expected_conditions(None, None, _EVENT, fetcher=fetch) is None
        assert get_expected_conditions(_LAT, None, _EVENT, fetcher=fetch) is None

    def test_all_fetches_fail_returns_none(self):
        assert (
            get_expected_conditions(
                _LAT, _LNG, _EVENT, today=_TODAY, fetcher=lambda u, p: None
            )
            is None
        )

    def test_empty_daily_returns_none(self):
        def fetch(url, params):
            return _daily([], [], [])

        assert (
            get_expected_conditions(_LAT, _LNG, _EVENT, today=_TODAY, fetcher=fetch)
            is None
        )

    def test_partial_years_still_aggregate(self):
        # Only the first call returns data; the rest fail. Still produces a result.
        state = {"n": 0}

        def fetch(url, params):
            state["n"] += 1
            if state["n"] == 1:
                return _daily([20.0, 22.0], [10.0, 12.0], [3.0, 0.0])
            return None

        ec = get_expected_conditions(_LAT, _LNG, _EVENT, today=_TODAY, fetcher=fetch)
        assert ec is not None
        assert ec.sample_days == 2
        assert ec.wet_day_probability_pct == 50


class TestSummaryLine:
    def test_summary_line_human_readable(self):
        ec = ExpectedConditions(
            temp_max_c=30.2,
            temp_min_c=18.4,
            wet_day_probability_pct=40,
            sample_days=35,
            sample_years=5,
        )
        line = ec.summary_line()
        assert "~30°C" in line
        assert "~18°C" in line
        assert "40%" in line
        assert "5-yr" in line

    def test_summary_line_metric_explicit(self):
        ec = ExpectedConditions(
            temp_max_c=30.2,
            temp_min_c=18.4,
            wet_day_probability_pct=40,
            sample_days=35,
            sample_years=5,
        )
        line = ec.summary_line('metric')
        assert "~30°C" in line
        assert "~18°C" in line
        assert "°F" not in line

    def test_summary_line_imperial_renders_fahrenheit(self):
        # Issue #946 — imperial athletes see °F, not °C.
        ec = ExpectedConditions(
            temp_max_c=30.0,  # 86°F
            temp_min_c=10.0,  # 50°F
            wet_day_probability_pct=40,
            sample_days=35,
            sample_years=5,
        )
        line = ec.summary_line('imperial')
        assert "~86°F" in line
        assert "~50°F" in line
        assert "°C" not in line
