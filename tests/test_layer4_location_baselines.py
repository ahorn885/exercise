"""Event Windows Slice 3 (#581 WS-H / F8) — category equipment baselines.

A not-yet-logged locale (an away destination created inline, or a cold home
gym) whose CATEGORY has an authored baseline assumes that baseline's equipment
+ terrain until the athlete logs actuals (replace semantics — any logged value
wins). Tests `locations.load_category_baselines`, the substitution inside
`cluster_equipment_by_locale` / `cluster_terrain_by_locale`, the overlay-mark
helper `locale_assumed_baseline_display`, and the slug→baseline drift guard.
"""

from __future__ import annotations

import json

import locations
from routes.locales import MANUAL_CATEGORIES, RESIDENTIAL_CATEGORIES


class _Row(dict):
    pass


class _Cursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows if rows is not None else []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return list(self._rows)


# The four authored baselines (migration 0005), keyed by logical category.
_BASELINES = {
    "commercial": {"equipment": ["Barbell", "Treadmill", "Cable machine"],
                   "terrain": ["TRN-001", "TRN-016"]},
    "hotel": {"equipment": ["Dumbbell", "Treadmill"],
              "terrain": ["TRN-001", "TRN-016"]},
    "climbing": {"equipment": ["Climbing Wall", "Hangboard"],
                 "terrain": ["TRN-001", "TRN-016", "TRN-014"]},
    "pool": {"equipment": [], "terrain": ["TRN-008"]},
}


class _FakeDB:
    """In-memory locale model with the Slice-3 baseline table. `execute`
    dispatches on SQL shape, mirroring the exact queries `locations.py` issues.
    `with_baselines=False` simulates the pre-migration state (table absent →
    the query raises, which `load_category_baselines` swallows to {})."""

    def __init__(self, *, profiles=None, gym_profiles=None, overrides=None,
                 with_baselines=True):
        self.profiles = [_Row(p) for p in (profiles or [])]
        self.gym_profiles = gym_profiles or {}
        self.overrides = [_Row(o) for o in (overrides or [])]
        self.with_baselines = with_baselines

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM layer0.location_category_equipment_baseline" in s:
            if not self.with_baselines:
                raise RuntimeError('relation "..." does not exist')
            rows = [
                _Row({"category": k,
                      "equipment_tags": list(v["equipment"]),
                      "terrain_ids": list(v["terrain"])})
                for k, v in _BASELINES.items()
            ]
            return _Cursor(rows=rows)
        if "FROM gym_profiles WHERE id" in s:
            (gid,) = params
            return _Cursor(row=_Row({"equipment": self.gym_profiles.get(gid)}))
        if "category, locale_terrain_ids FROM locale_profiles" in s:
            uid, locale = params
            m = self._profile(uid, locale)
            return _Cursor(row=_Row({
                "category": m.get("category") if m else None,
                "locale_terrain_ids": m.get("locale_terrain_ids") if m else None,
            }) if m else None)
        if "SELECT category FROM locale_profiles" in s:
            uid, locale = params
            m = self._profile(uid, locale)
            return _Cursor(row=_Row({"category": m.get("category")}) if m else None)
        if "gym_profile_id FROM locale_profiles" in s:
            uid, locale = params
            m = self._profile(uid, locale)
            return _Cursor(
                row=_Row({"gym_profile_id": m.get("gym_profile_id")}) if m else None
            )
        if "locale_terrain_ids FROM locale_profiles" in s:
            uid, locale = params
            m = self._profile(uid, locale)
            return _Cursor(
                row=_Row({"locale_terrain_ids": m.get("locale_terrain_ids")})
                if m else None
            )
        if "FROM locale_equipment_overrides" in s:
            uid, locale = params
            rows = [o for o in self.overrides
                    if o["user_id"] == uid and o["locale"] == locale]
            return _Cursor(rows=rows)
        raise AssertionError(f"unexpected SQL: {s!r}")

    def _profile(self, uid, locale):
        return next((p for p in self.profiles
                     if p["user_id"] == uid and p["locale"] == locale), None)


_UID = 7


def _profile(locale, *, category=None, gym_profile_id=None, terrain=None):
    return {"user_id": _UID, "locale": locale, "preferred": False,
            "lat": None, "lng": None, "gym_profile_id": gym_profile_id,
            "category": category, "locale_terrain_ids": terrain}


# ── load_category_baselines ──────────────────────────────────────────────


def test_load_baselines_parses_rows_into_sets():
    out = locations.load_category_baselines(_FakeDB())
    assert out["hotel"]["equipment"] == {"Dumbbell", "Treadmill"}
    assert out["climbing"]["terrain"] == {"TRN-001", "TRN-016", "TRN-014"}
    assert out["pool"]["equipment"] == set()


def test_load_baselines_absent_table_degrades_to_empty():
    assert locations.load_category_baselines(_FakeDB(with_baselines=False)) == {}


# ── cluster_equipment_by_locale substitution ─────────────────────────────


def test_cold_baseline_category_assumes_equipment():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym")])
    out = locations.cluster_equipment_by_locale(db, _UID, ["belfast_hotel"])
    assert out["belfast_hotel"] == {"Dumbbell", "Treadmill"}


def test_logged_equipment_wins_over_baseline():
    db = _FakeDB(
        profiles=[_profile("home_box", category="commercial_chain_gym",
                            gym_profile_id=1)],
        gym_profiles={1: json.dumps(["Squat rack"])},
    )
    out = locations.cluster_equipment_by_locale(db, _UID, ["home_box"])
    assert out["home_box"] == {"Squat rack"}  # baseline NOT applied


def test_non_baseline_category_stays_empty():
    db = _FakeDB(profiles=[_profile("trailhead", category="outdoor_park")])
    out = locations.cluster_equipment_by_locale(db, _UID, ["trailhead"])
    assert out["trailhead"] == set()


def test_pool_has_no_equipment_baseline():
    db = _FakeDB(profiles=[_profile("rec_pool", category="pool_indoor")])
    out = locations.cluster_equipment_by_locale(db, _UID, ["rec_pool"])
    assert out["rec_pool"] == set()  # pool baseline is terrain-only


def test_absent_table_no_substitution():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym")],
                 with_baselines=False)
    out = locations.cluster_equipment_by_locale(db, _UID, ["belfast_hotel"])
    assert out["belfast_hotel"] == set()


# ── cluster_terrain_by_locale substitution ───────────────────────────────


def test_cold_baseline_category_assumes_terrain():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym")])
    out = locations.cluster_terrain_by_locale(db, _UID, ["belfast_hotel"])
    assert out["belfast_hotel"] == {"TRN-001", "TRN-016"}


def test_pool_assumes_pool_terrain():
    db = _FakeDB(profiles=[_profile("rec_pool", category="pool_indoor")])
    out = locations.cluster_terrain_by_locale(db, _UID, ["rec_pool"])
    assert out["rec_pool"] == {"TRN-008"}


def test_logged_terrain_wins_over_baseline():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym",
                                    terrain=["TRN-002"])])
    out = locations.cluster_terrain_by_locale(db, _UID, ["belfast_hotel"])
    assert out["belfast_hotel"] == {"TRN-002"}  # baseline NOT applied


# ── locale_assumed_baseline_display (overlay mark) ───────────────────────


def test_assumed_display_cold_destination():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym")])
    assert locations.locale_assumed_baseline_display(
        db, _UID, "belfast_hotel") == "hotel gym"


def test_assumed_display_none_when_equipment_logged():
    db = _FakeDB(
        profiles=[_profile("belfast_hotel", category="hotel_gym",
                            gym_profile_id=1)],
        gym_profiles={1: json.dumps(["Dumbbell"])},
    )
    assert locations.locale_assumed_baseline_display(
        db, _UID, "belfast_hotel") is None


def test_assumed_display_none_when_terrain_logged():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym",
                                    terrain=["TRN-001"])])
    assert locations.locale_assumed_baseline_display(
        db, _UID, "belfast_hotel") is None


def test_assumed_display_none_for_non_baseline_category():
    db = _FakeDB(profiles=[_profile("trailhead", category="outdoor_park")])
    assert locations.locale_assumed_baseline_display(
        db, _UID, "trailhead") is None


def test_assumed_display_none_when_table_absent():
    db = _FakeDB(profiles=[_profile("belfast_hotel", category="hotel_gym")],
                 with_baselines=False)
    assert locations.locale_assumed_baseline_display(
        db, _UID, "belfast_hotel") is None


# ── drift guard: slug→baseline map vs the live category vocabulary ───────


def test_baseline_key_covers_every_gym_and_pool_category():
    """Every non-residential, non-park MANUAL_CATEGORIES slug must map to a
    baseline (else a cold locale of that category silently degrades). Parks +
    residences intentionally have none."""
    no_baseline = RESIDENTIAL_CATEGORIES | {"outdoor_park"}
    expected = {slug for slug, _ in MANUAL_CATEGORIES if slug not in no_baseline}
    assert set(locations._CATEGORY_BASELINE_KEY) == expected


def test_baseline_keys_resolve_to_display_labels():
    for key in set(locations._CATEGORY_BASELINE_KEY.values()):
        assert key in locations._BASELINE_DISPLAY
