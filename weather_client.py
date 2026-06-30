"""Open-Meteo climate-normals client for race-week expected conditions.

The race-week brief fires ~14 days out — too far for a reliable point
forecast — so we derive *expected conditions* from multi-year historical
climate normals at the race location around the event's calendar date.
Open-Meteo's archive API is open (no key required).

Best-effort by design: missing coordinates, a network error, a malformed
response, or an empty sample all return ``None``, and the brief degrades to
the synthesizer's intrinsic climate reasoning from the location + date it
already sees.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean
from typing import Any, Callable

try:  # pragma: no cover - requests is a hard runtime dependency
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore[assignment]

_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_NORMALS_YEARS = 5  # recent complete years to average
_WINDOW_DAYS = 3  # +/- days around the event's month/day
_TIMEOUT_S = 6
_WET_DAY_MM = 1.0  # daily precipitation_sum >= this counts as a wet day

# (url, query params) -> parsed JSON dict, or None on any failure.
Fetcher = Callable[[str, "dict[str, Any]"], "dict[str, Any] | None"]


@dataclass(frozen=True)
class ExpectedConditions:
    """Aggregated climate normals around a race date + location."""

    temp_max_c: float
    temp_min_c: float
    wet_day_probability_pct: int
    sample_days: int
    sample_years: int

    def summary_line(self, unit_pref: str | None = None) -> str:
        """Athlete-facing one-liner, rendered in the athlete's temperature unit.

        Canonical storage is °C (Open-Meteo's native unit). Imperial athletes
        see °F so the weather display honors the same unit toggle as the rest
        of the app (issue #946). `unit_pref` of None means canonical metric —
        the LLM-prompt caller reasons in °C and is unaffected; only an explicit
        athlete preference flips the rendering.
        """
        from units import IMPERIAL, c_to_f, normalize_unit_preference

        imperial = (
            unit_pref is not None
            and normalize_unit_preference(unit_pref) == IMPERIAL
        )
        if imperial:
            high, low, unit = c_to_f(self.temp_max_c), c_to_f(self.temp_min_c), "°F"
        else:
            high, low, unit = self.temp_max_c, self.temp_min_c, "°C"
        return (
            f"Climate normals near the race date "
            f"({self.sample_years}-yr historical, n={self.sample_days} days): "
            f"typical high ~{high:.0f}{unit}, "
            f"low ~{low:.0f}{unit}, "
            f"~{self.wet_day_probability_pct}% of days saw measurable precipitation."
        )


def _default_fetch(url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    if requests is None:
        return None
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT_S)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def get_expected_conditions(
    latitude: float | None,
    longitude: float | None,
    event_date: date,
    *,
    today: date | None = None,
    fetcher: Fetcher | None = None,
) -> ExpectedConditions | None:
    """Expected conditions for ``event_date`` at ``(latitude, longitude)``.

    Averages ``_NORMALS_YEARS`` recent years of archive data within
    ``_WINDOW_DAYS`` of the event's calendar date. Returns ``None`` when
    coordinates are missing or the sample is empty.
    """
    if latitude is None or longitude is None:
        return None

    fetch = fetcher or _default_fetch
    ref_year = (today or date.today()).year

    maxs: list[float] = []
    mins: list[float] = []
    wet_days = 0
    precip_days = 0

    for year in range(ref_year - _NORMALS_YEARS, ref_year):
        try:
            center = event_date.replace(year=year)
        except ValueError:  # Feb 29 in a non-leap year -> clamp to Feb 28
            center = event_date.replace(year=year, month=2, day=28)
        start = center - timedelta(days=_WINDOW_DAYS)
        end = center + timedelta(days=_WINDOW_DAYS)
        data = fetch(
            _ARCHIVE_URL,
            {
                "latitude": round(float(latitude), 3),
                "longitude": round(float(longitude), 3),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
        )
        if not data:
            continue
        daily = data.get("daily") or {}
        for v in daily.get("temperature_2m_max") or []:
            if v is not None:
                maxs.append(float(v))
        for v in daily.get("temperature_2m_min") or []:
            if v is not None:
                mins.append(float(v))
        for v in daily.get("precipitation_sum") or []:
            if v is not None:
                precip_days += 1
                if float(v) >= _WET_DAY_MM:
                    wet_days += 1

    if not maxs or not mins or precip_days == 0:
        return None

    return ExpectedConditions(
        temp_max_c=round(mean(maxs), 1),
        temp_min_c=round(mean(mins), 1),
        wet_day_probability_pct=round(100 * wet_days / precip_days),
        sample_days=precip_days,
        sample_years=_NORMALS_YEARS,
    )


def get_forecast_high(
    latitude: float | None,
    longitude: float | None,
    target_date: date,
    *,
    fetcher: Fetcher | None = None,
) -> float | None:
    """Forecast daily-high °C for ``target_date`` at ``(latitude, longitude)``.

    The forecast leg of `Plan_Management_Spec_v1.md` §5.3.2 — the sibling to
    `get_expected_conditions` for events inside Open-Meteo's ~14-day forecast
    horizon. Hits the forecast endpoint (no key required, same `Fetcher`
    injection) and returns the `temperature_2m_max` for the target day, or
    ``None`` on missing coordinates / network error / malformed-or-empty
    response. Best-effort by design: a ``None`` lets §5.3 fall back to the
    climate normal (`_blend`).
    """
    if latitude is None or longitude is None:
        return None

    fetch = fetcher or _default_fetch
    data = fetch(
        _FORECAST_URL,
        {
            "latitude": round(float(latitude), 3),
            "longitude": round(float(longitude), 3),
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
            "daily": "temperature_2m_max",
            "timezone": "auto",
        },
    )
    if not data:
        return None
    highs = (data.get("daily") or {}).get("temperature_2m_max") or []
    if not highs or highs[0] is None:
        return None
    return round(float(highs[0]), 1)


@dataclass(frozen=True)
class DayForecast:
    """One day's live forecast — the per-day signal the conditions advisory fires on."""

    temp_max_c: float
    temp_min_c: float
    precip_prob_pct: int


def get_upcoming_forecast(
    latitude: float | None,
    longitude: float | None,
    start_date: date,
    end_date: date,
    *,
    fetcher: Fetcher | None = None,
) -> dict[date, DayForecast]:
    """Per-day live forecast for ``[start_date, end_date]`` at ``(lat, lng)``.

    The producer leg of the #964 conditions advisory (#289 Layer-5 surface): one
    Open-Meteo forecast call yielding, per day, the daily high/low (°C) and the
    max precipitation probability (%). Returns an **empty dict** on missing
    coordinates, a network error, a malformed response, or a range with no usable
    days — best-effort by design, the same degrade contract as the functions
    above (the caller writes nothing and the advisory rides the last good rows).

    Only days carrying all three values are included; a day with a null in any
    series is skipped (an incomplete row can't be thresholded reliably).
    """
    if latitude is None or longitude is None:
        return {}

    fetch = fetcher or _default_fetch
    data = fetch(
        _FORECAST_URL,
        {
            "latitude": round(float(latitude), 3),
            "longitude": round(float(longitude), 3),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
        },
    )
    if not data:
        return {}
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    probs = daily.get("precipitation_probability_max") or []

    out: dict[date, DayForecast] = {}
    for i, day_iso in enumerate(times):
        if i >= len(highs) or i >= len(lows) or i >= len(probs):
            break
        hi, lo, pp = highs[i], lows[i], probs[i]
        if hi is None or lo is None or pp is None:
            continue
        try:
            d = date.fromisoformat(day_iso)
        except (ValueError, TypeError):
            continue
        out[d] = DayForecast(
            temp_max_c=round(float(hi), 1),
            temp_min_c=round(float(lo), 1),
            precip_prob_pct=int(round(float(pp))),
        )
    return out
