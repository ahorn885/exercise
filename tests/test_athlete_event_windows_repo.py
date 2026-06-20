"""Tests for `athlete_event_windows_repo.resolve_weather_city` (#787 / #304 PR B).

`resolve_weather_city` is the single city resolver the weather + clothing
read-sites (`routes/dashboard.py`, `routes/plans.py`) call after the legacy
`plan_travel` table was retired. It answers "which city is the athlete training
in on this date" by preferring an `away` event window covering the date (its
`away_locale` -> `locale_profiles.city`) over the preferred-home city, and
returns `''` when neither yields a non-empty city so the caller can apply its
own fallback (the `WEATHER_LOCATION` env default).

The fake DB faithfully evaluates the two queries the helper issues (away-window
JOIN + preferred-home SELECT) against seeded rows — so date-overlap boundaries,
the `override_type='away'` filter, the empty-city fall-through, and the
away-beats-home precedence are all exercised, not just stubbed.
"""

from __future__ import annotations

from datetime import date

import pytest

from athlete_event_windows_repo import resolve_weather_city

UID = 7
TODAY = date(2026, 6, 20)


class _Row(dict):
    """dict row — matches psycopg RealDictRow / sqlite3.Row subscripting."""


class _Cursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeDB:
    """In-memory event-windows + locale model. `execute` dispatches on the SQL
    shape and applies the same filters the real queries would."""

    def __init__(self, *, windows=None, profiles=None):
        # windows: dicts {user_id, start_date, end_date, override_type,
        #                 away_locale, id?}
        self.windows = [_Row(w) for w in (windows or [])]
        # profiles: dicts {user_id, locale, city, preferred?}
        self.profiles = [_Row(p) for p in (profiles or [])]

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM athlete_event_windows w JOIN locale_profiles lp" in s:
            user_id, on_date, on_date2 = params
            assert on_date == on_date2  # both range bounds bind the same date
            cands = []
            for w in self.windows:
                if w["user_id"] != user_id or w["override_type"] != "away":
                    continue
                if not (w["start_date"] <= on_date <= w["end_date"]):
                    continue
                lp = next(
                    (p for p in self.profiles
                     if p["user_id"] == user_id and p["locale"] == w["away_locale"]),
                    None,
                )
                if lp is None or (lp.get("city") or "") == "":
                    continue  # mirrors the AND lp.city != '' filter
                cands.append((w["start_date"], w.get("id", 0), lp["city"]))
            cands.sort(key=lambda c: (c[0], c[1]))  # ORDER BY start_date, id
            return _Cursor(_Row({"city": cands[0][2]}) if cands else None)
        if "FROM locale_profiles WHERE preferred AND user_id" in s:
            (user_id,) = params
            pref = next(
                (p for p in self.profiles
                 if p["user_id"] == user_id and p.get("preferred")),
                None,
            )
            if pref and (pref.get("city") or ""):
                return _Cursor(_Row({"city": pref["city"]}))
            return _Cursor(None)
        raise AssertionError(f"unexpected SQL: {s}")


def _home(city="Boulder, CO"):
    return {"user_id": UID, "locale": "home", "city": city, "preferred": True}


def _away_window(locale="moab", start=date(2026, 6, 18), end=date(2026, 6, 25)):
    return {
        "user_id": UID, "start_date": start, "end_date": end,
        "override_type": "away", "away_locale": locale, "id": 1,
    }


def test_away_window_covering_date_wins():
    db = _FakeDB(
        windows=[_away_window()],
        profiles=[_home(), {"user_id": UID, "locale": "moab", "city": "Moab, UT"}],
    )
    assert resolve_weather_city(db, UID, TODAY) == "Moab, UT"


def test_no_window_falls_back_to_preferred_home():
    db = _FakeDB(windows=[], profiles=[_home()])
    assert resolve_weather_city(db, UID, TODAY) == "Boulder, CO"


def test_window_outside_date_is_ignored():
    past = _away_window(start=date(2026, 1, 1), end=date(2026, 1, 10))
    db = _FakeDB(
        windows=[past],
        profiles=[_home(), {"user_id": UID, "locale": "moab", "city": "Moab, UT"}],
    )
    assert resolve_weather_city(db, UID, TODAY) == "Boulder, CO"


def test_away_window_with_empty_city_falls_through_to_home():
    # Destination locale exists but has no recorded city — preserve the v1
    # plan_travel behaviour: defer to the home city rather than blanking.
    db = _FakeDB(
        windows=[_away_window()],
        profiles=[_home(), {"user_id": UID, "locale": "moab", "city": ""}],
    )
    assert resolve_weather_city(db, UID, TODAY) == "Boulder, CO"


def test_no_city_anywhere_returns_empty_string():
    db = _FakeDB(windows=[], profiles=[_home(city="")])
    assert resolve_weather_city(db, UID, TODAY) == ""


def test_no_profiles_at_all_returns_empty_string():
    db = _FakeDB(windows=[], profiles=[])
    assert resolve_weather_city(db, UID, TODAY) == ""


def test_boundary_dates_are_inclusive():
    win = _away_window(start=TODAY, end=TODAY)  # single-day window == today
    db = _FakeDB(
        windows=[win],
        profiles=[_home(), {"user_id": UID, "locale": "moab", "city": "Moab, UT"}],
    )
    assert resolve_weather_city(db, UID, TODAY) == "Moab, UT"


def test_earliest_window_wins_when_multiple_overlap():
    early = _away_window(locale="moab", start=date(2026, 6, 1), end=date(2026, 6, 30))
    early["id"] = 1
    late = _away_window(locale="tahoe", start=date(2026, 6, 19), end=date(2026, 6, 22))
    late["id"] = 2
    db = _FakeDB(
        windows=[late, early],  # unsorted on purpose
        profiles=[
            _home(),
            {"user_id": UID, "locale": "moab", "city": "Moab, UT"},
            {"user_id": UID, "locale": "tahoe", "city": "Tahoe City, CA"},
        ],
    )
    assert resolve_weather_city(db, UID, TODAY) == "Moab, UT"


def test_other_users_window_is_not_visible():
    # Another athlete's away window must not leak into UID's lookup: UID
    # resolves to its own preferred-home city, never the foreign destination.
    foreign = _away_window()
    foreign["user_id"] = UID + 1
    db = _FakeDB(
        windows=[foreign],
        profiles=[
            _home(),
            {"user_id": UID + 1, "locale": "moab", "city": "Moab, UT"},
        ],
    )
    assert resolve_weather_city(db, UID, TODAY) == "Boulder, CO"
