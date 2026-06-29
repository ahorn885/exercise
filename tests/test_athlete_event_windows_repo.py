"""Tests for `athlete_event_windows_repo.resolve_weather_location` (#941).

`resolve_weather_location` is the single location resolver the weather +
clothing read-sites (`routes/dashboard.py`, `routes/plans.py`) call. It answers
"which place is the athlete training in on this date" by preferring an `away`
event window covering the date (its `away_locale` -> the Mapbox-anchored
`locale_profiles.lat`/`lng`) over the preferred-home coordinates, and returns a
bare `"lat,lng"` token wttr.in / Open-Meteo accept — or `''` when neither has
coordinates so the caller can apply its own fallback (the `WEATHER_LOCATION`
env default).

#941 repointed this off the free-text `locale_profiles.city` (now retired): a
travel locale left the typed city blank and the away window silently fell
through to *home* weather. Mapbox coordinates are captured on every geocoded
locale, so the away destination now resolves to its own conditions.

The fake DB faithfully evaluates the two queries the helper issues (away-window
JOIN + preferred-home SELECT) against seeded rows — so date-overlap boundaries,
the `override_type='away'` filter, the missing-coordinate fall-through, and the
away-beats-home precedence are all exercised, not just stubbed.
"""

from __future__ import annotations

from datetime import date

from athlete_event_windows_repo import resolve_weather_location

UID = 7
TODAY = date(2026, 6, 20)

# Mapbox coords -> the "lat,lng" token the helper emits (4-dp, see _latlng_token).
HOME = (40.0150, -105.2705)        # Boulder, CO
HOME_TOKEN = "40.0150,-105.2705"
MOAB = (38.5733, -109.5498)        # Moab, UT
MOAB_TOKEN = "38.5733,-109.5498"
TAHOE = (39.1660, -120.1414)       # Tahoe City, CA
TAHOE_TOKEN = "39.1660,-120.1414"


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
        # profiles: dicts {user_id, locale, lat, lng, preferred?}
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
                # mirrors the AND lp.lat IS NOT NULL AND lp.lng IS NOT NULL filter
                if lp is None or lp.get("lat") is None or lp.get("lng") is None:
                    continue
                cands.append((w["start_date"], w.get("id", 0), lp["lat"], lp["lng"]))
            cands.sort(key=lambda c: (c[0], c[1]))  # ORDER BY start_date, id
            if not cands:
                return _Cursor(None)
            return _Cursor(_Row({"lat": cands[0][2], "lng": cands[0][3]}))
        if "FROM locale_profiles WHERE preferred AND user_id" in s:
            (user_id,) = params
            pref = next(
                (p for p in self.profiles
                 if p["user_id"] == user_id and p.get("preferred")
                 and p.get("lat") is not None and p.get("lng") is not None),
                None,
            )
            if pref:
                return _Cursor(_Row({"lat": pref["lat"], "lng": pref["lng"]}))
            return _Cursor(None)
        raise AssertionError(f"unexpected SQL: {s}")


def _home(lat=HOME[0], lng=HOME[1]):
    return {"user_id": UID, "locale": "home", "lat": lat, "lng": lng,
            "preferred": True}


def _locale(locale, coords):
    return {"user_id": UID, "locale": locale, "lat": coords[0], "lng": coords[1]}


def _away_window(locale="moab", start=date(2026, 6, 18), end=date(2026, 6, 25)):
    return {
        "user_id": UID, "start_date": start, "end_date": end,
        "override_type": "away", "away_locale": locale, "id": 1,
    }


def test_away_window_covering_date_wins():
    db = _FakeDB(
        windows=[_away_window()],
        profiles=[_home(), _locale("moab", MOAB)],
    )
    assert resolve_weather_location(db, UID, TODAY) == MOAB_TOKEN


def test_no_window_falls_back_to_preferred_home():
    db = _FakeDB(windows=[], profiles=[_home()])
    assert resolve_weather_location(db, UID, TODAY) == HOME_TOKEN


def test_window_outside_date_is_ignored():
    past = _away_window(start=date(2026, 1, 1), end=date(2026, 1, 10))
    db = _FakeDB(
        windows=[past],
        profiles=[_home(), _locale("moab", MOAB)],
    )
    assert resolve_weather_location(db, UID, TODAY) == HOME_TOKEN


def test_away_window_without_coords_falls_through_to_home():
    # Destination locale exists but is un-anchored (manual entry, no geocode) —
    # defer to the home coordinates rather than blanking the lookup.
    db = _FakeDB(
        windows=[_away_window()],
        profiles=[_home(), {"user_id": UID, "locale": "moab",
                            "lat": None, "lng": None}],
    )
    assert resolve_weather_location(db, UID, TODAY) == HOME_TOKEN


def test_no_coords_anywhere_returns_empty_string():
    db = _FakeDB(windows=[], profiles=[_home(lat=None, lng=None)])
    assert resolve_weather_location(db, UID, TODAY) == ""


def test_no_profiles_at_all_returns_empty_string():
    db = _FakeDB(windows=[], profiles=[])
    assert resolve_weather_location(db, UID, TODAY) == ""


def test_boundary_dates_are_inclusive():
    win = _away_window(start=TODAY, end=TODAY)  # single-day window == today
    db = _FakeDB(
        windows=[win],
        profiles=[_home(), _locale("moab", MOAB)],
    )
    assert resolve_weather_location(db, UID, TODAY) == MOAB_TOKEN


def test_earliest_window_wins_when_multiple_overlap():
    early = _away_window(locale="moab", start=date(2026, 6, 1), end=date(2026, 6, 30))
    early["id"] = 1
    late = _away_window(locale="tahoe", start=date(2026, 6, 19), end=date(2026, 6, 22))
    late["id"] = 2
    db = _FakeDB(
        windows=[late, early],  # unsorted on purpose
        profiles=[_home(), _locale("moab", MOAB), _locale("tahoe", TAHOE)],
    )
    assert resolve_weather_location(db, UID, TODAY) == MOAB_TOKEN


def test_other_users_window_is_not_visible():
    # Another athlete's away window must not leak into UID's lookup: UID
    # resolves to its own preferred-home coords, never the foreign destination.
    foreign = _away_window()
    foreign["user_id"] = UID + 1
    db = _FakeDB(
        windows=[foreign],
        profiles=[
            _home(),
            {"user_id": UID + 1, "locale": "moab", "lat": MOAB[0], "lng": MOAB[1]},
        ],
    )
    assert resolve_weather_location(db, UID, TODAY) == HOME_TOKEN
