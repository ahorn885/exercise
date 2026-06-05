"""Tests for `locations.py` — the authoritative locations / equipment-pool
domain logic (Locations Consolidation, Track 1).

Covers the three public resolvers (`primary_locale`, `locale_effective_tags`,
`cluster_locale_ids`) + the cluster union (`cluster_effective_tags`) against a
table-backed fake DB that dispatches by SQL shape. Equipment is asserted in
layer0 canonical names (Title-case) — the vocabulary Layer 2C resolves
`exercises.equipment_required` against — which is the whole point of the
consolidation (no snake_case `public.equipment_items.tag`).
"""

from __future__ import annotations

import json

import pytest

import locations


class _Row(dict):
    """dict that also supports attribute-free `row["k"]` access (already a
    dict) — matches psycopg2 RealDictRow / sqlite3.Row used by the resolvers."""


class _Cursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows if rows is not None else []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return list(self._rows)


class _FakeDB:
    """In-memory locale model. `execute` dispatches on the SQL text + params,
    mirroring the exact queries `locations.py` issues."""

    def __init__(self, *, profiles=None, gym_profiles=None, overrides=None):
        # profiles: list of {user_id, locale, preferred, lat, lng, gym_profile_id}
        self.profiles = [_Row(p) for p in (profiles or [])]
        # gym_profiles: {id: equipment_json_or_none}
        self.gym_profiles = gym_profiles or {}
        # overrides: list of {user_id, locale, equipment_tag, action}
        self.overrides = [_Row(o) for o in (overrides or [])]

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM gym_profiles WHERE id" in s:
            (gid,) = params
            return _Cursor(row=_Row({"equipment": self.gym_profiles.get(gid)}))
        if "gym_profile_id FROM locale_profiles" in s:
            uid, locale = params
            match = self._profile(uid, locale)
            return _Cursor(
                row=_Row({"gym_profile_id": match["gym_profile_id"]}) if match else None
            )
        if "FROM locale_equipment_overrides" in s:
            uid, locale = params
            rows = [
                o for o in self.overrides
                if o["user_id"] == uid and o["locale"] == locale
            ]
            return _Cursor(rows=rows)
        if "FROM locale_profiles" in s and "preferred LIMIT 1" in s:
            (uid,) = params
            pref = next(
                (p for p in self.profiles if p["user_id"] == uid and p.get("preferred")),
                None,
            )
            return _Cursor(row=pref)
        if "FROM locale_profiles" in s and "locale != ?" in s:
            uid, home_locale = params
            rows = [
                p for p in self.profiles
                if p["user_id"] == uid
                and p["locale"] != home_locale
                and p.get("lat") is not None
                and p.get("lng") is not None
            ]
            return _Cursor(rows=rows)
        raise AssertionError(f"unexpected SQL: {s!r}")

    def _profile(self, uid, locale):
        return next(
            (p for p in self.profiles if p["user_id"] == uid and p["locale"] == locale),
            None,
        )


_UID = 7


# ── primary_locale ───────────────────────────────────────────────────────


def test_primary_locale_returns_preferred():
    db = _FakeDB(profiles=[
        {"user_id": _UID, "locale": "home", "preferred": True, "lat": None,
         "lng": None, "gym_profile_id": None},
        {"user_id": _UID, "locale": "downtown_gym", "preferred": False,
         "lat": None, "lng": None, "gym_profile_id": None},
    ])
    assert locations.primary_locale(db, _UID) == "home"


def test_primary_locale_missing_raises():
    db = _FakeDB(profiles=[
        {"user_id": _UID, "locale": "home", "preferred": False, "lat": None,
         "lng": None, "gym_profile_id": None},
    ])
    with pytest.raises(locations.PrimaryLocaleMissing):
        locations.primary_locale(db, _UID)


# ── locale_effective_tags ────────────────────────────────────────────────


def test_effective_tags_shared_plus_adds_minus_removes_canonical():
    db = _FakeDB(
        profiles=[{"user_id": _UID, "locale": "home", "preferred": True,
                   "lat": None, "lng": None, "gym_profile_id": 1}],
        gym_profiles={1: json.dumps(["Barbell", "Squat rack", "Bench"])},
        overrides=[
            {"user_id": _UID, "locale": "home", "equipment_tag": "Kettlebell",
             "action": "add"},
            {"user_id": _UID, "locale": "home", "equipment_tag": "Bench",
             "action": "remove"},
        ],
    )
    assert locations.locale_effective_tags(db, _UID, "home") == {
        "Barbell", "Squat rack", "Kettlebell",
    }


def test_effective_tags_empty_when_no_gym_and_no_overrides():
    db = _FakeDB(profiles=[
        {"user_id": _UID, "locale": "home", "preferred": True, "lat": None,
         "lng": None, "gym_profile_id": None},
    ])
    assert locations.locale_effective_tags(db, _UID, "home") == set()


def test_effective_tags_tolerates_malformed_gym_json():
    db = _FakeDB(
        profiles=[{"user_id": _UID, "locale": "home", "preferred": True,
                   "lat": None, "lng": None, "gym_profile_id": 1}],
        gym_profiles={1: "{not json"},
        overrides=[{"user_id": _UID, "locale": "home",
                    "equipment_tag": "Barbell", "action": "add"}],
    )
    # Malformed shared payload degrades to empty; overrides still apply.
    assert locations.locale_effective_tags(db, _UID, "home") == {"Barbell"}


# ── cluster_locale_ids ───────────────────────────────────────────────────


def test_cluster_home_only_when_no_coords():
    db = _FakeDB(profiles=[
        {"user_id": _UID, "locale": "home", "preferred": True, "lat": None,
         "lng": None, "gym_profile_id": None},
        {"user_id": _UID, "locale": "downtown_gym", "preferred": False,
         "lat": 44.98, "lng": -93.27, "gym_profile_id": None},
    ])
    # Home has no coords → no radius sweep → just home.
    assert locations.cluster_locale_ids(db, _UID) == ["home"]


def test_cluster_includes_within_radius_excludes_beyond():
    # Home in Minneapolis; one gym ~5 km away (in), one ~120 km away (out).
    db = _FakeDB(profiles=[
        {"user_id": _UID, "locale": "home", "preferred": True,
         "lat": 44.98, "lng": -93.27, "gym_profile_id": None},
        {"user_id": _UID, "locale": "near_gym", "preferred": False,
         "lat": 45.01, "lng": -93.20, "gym_profile_id": None},
        {"user_id": _UID, "locale": "rochester", "preferred": False,
         "lat": 44.02, "lng": -92.48, "gym_profile_id": None},
        {"user_id": _UID, "locale": "manual_no_coords", "preferred": False,
         "lat": None, "lng": None, "gym_profile_id": None},
    ])
    cluster = locations.cluster_locale_ids(db, _UID)
    assert cluster[0] == "home"
    assert "near_gym" in cluster
    assert "rochester" not in cluster
    assert "manual_no_coords" not in cluster


def test_cluster_empty_when_no_home():
    db = _FakeDB(profiles=[
        {"user_id": _UID, "locale": "home", "preferred": False, "lat": None,
         "lng": None, "gym_profile_id": None},
    ])
    assert locations.cluster_locale_ids(db, _UID) == []


# ── cluster_effective_tags ───────────────────────────────────────────────


def test_cluster_effective_tags_unions_sorted():
    db = _FakeDB(
        profiles=[
            {"user_id": _UID, "locale": "home", "preferred": True,
             "lat": 44.98, "lng": -93.27, "gym_profile_id": 1},
            {"user_id": _UID, "locale": "near_gym", "preferred": False,
             "lat": 45.01, "lng": -93.20, "gym_profile_id": 2},
        ],
        gym_profiles={
            1: json.dumps(["Kettlebell", "Pull-up bar"]),
            2: json.dumps(["Barbell", "Squat rack", "Kettlebell"]),
        },
    )
    cluster = locations.cluster_locale_ids(db, _UID)
    assert locations.cluster_effective_tags(db, _UID, cluster) == [
        "Barbell", "Kettlebell", "Pull-up bar", "Squat rack",
    ]
