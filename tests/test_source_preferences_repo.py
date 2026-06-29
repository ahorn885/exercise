"""Tests for `source_preferences_repo.py` (#196 Phase 5, Track B — slice B1).

Uses a `_FakeConn` (no real DB), mirroring test_athlete_gear_repo. Covers the
get/set/clear round-trip, the domain + provider-for-domain validation (writing
nothing on a violation), the upsert SQL shape, and the source-of-truth lockstep
between VALID_PROVIDERS and the merge layers' own provider lists.
"""
from __future__ import annotations

import pytest

import source_preferences_repo as spr
from source_preferences_repo import (
    CARDIO,
    DOMAINS,
    VALID_PROVIDERS,
    WELLNESS,
    SourcePreferenceError,
    clear_source_preference,
    get_source_preferences,
    set_source_preference,
)


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[list] = []

    def queue_response(self, rows=None):
        self.responses.append(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows)


# ─── get ─────────────────────────────────────────────────────────────────────

def test_get_empty_returns_empty_dict():
    db = _FakeConn()
    db.queue_response([])
    assert get_source_preferences(db, 7) == {}


def test_get_returns_domain_to_provider_map():
    db = _FakeConn()
    db.queue_response([
        {"domain": WELLNESS, "preferred_provider": "whoop"},
        {"domain": CARDIO, "preferred_provider": "wahoo"},
    ])
    assert get_source_preferences(db, 7) == {WELLNESS: "whoop", CARDIO: "wahoo"}


# ─── set ─────────────────────────────────────────────────────────────────────

def test_set_valid_upserts():
    db = _FakeConn()
    set_source_preference(db, 7, WELLNESS, "whoop")
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "INSERT INTO user_source_preferences" in sql
    assert "ON CONFLICT (user_id, domain) DO UPDATE" in sql
    assert params == (7, WELLNESS, "whoop")


def test_set_unknown_domain_raises_and_writes_nothing():
    db = _FakeConn()
    with pytest.raises(SourcePreferenceError):
        set_source_preference(db, 7, "sleep_only", "whoop")
    assert db.calls == []


def test_set_provider_not_valid_for_domain_raises():
    db = _FakeConn()
    # wahoo is a cardio provider, not a wellness source.
    with pytest.raises(SourcePreferenceError):
        set_source_preference(db, 7, WELLNESS, "wahoo")
    # whoop is a wellness provider, not a cardio source.
    with pytest.raises(SourcePreferenceError):
        set_source_preference(db, 7, CARDIO, "whoop")
    assert db.calls == []


# ─── clear ───────────────────────────────────────────────────────────────────

def test_clear_deletes_the_domain_row():
    db = _FakeConn()
    clear_source_preference(db, 7, CARDIO)
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "DELETE FROM user_source_preferences" in sql
    assert params == (7, CARDIO)


def test_clear_unknown_domain_raises_and_writes_nothing():
    db = _FakeConn()
    with pytest.raises(SourcePreferenceError):
        clear_source_preference(db, 7, "bogus")
    assert db.calls == []


# ─── source-of-truth lockstep ────────────────────────────────────────────────

def test_domains_cover_valid_providers():
    assert set(DOMAINS) == set(VALID_PROVIDERS)


def test_wellness_providers_match_source():
    # VALID_PROVIDERS[wellness] is built from _WELLNESS_SOURCE_PRIORITY, so this
    # guards an accidental hand-edit drift.
    from canonical_wellness import _WELLNESS_SOURCE_PRIORITY
    assert VALID_PROVIDERS[WELLNESS] == frozenset(_WELLNESS_SOURCE_PRIORITY)


def test_cardio_providers_match_source():
    # Pin the restated cardio set to the merge layer's own provider list so an
    # app/route drift fails loudly (the repo can't import the route module at
    # import time without pulling in Flask, hence the restated constant).
    from routes.garmin import _PROVIDER_ID_COLUMNS
    expected = {name for _col, name in _PROVIDER_ID_COLUMNS}
    assert VALID_PROVIDERS[CARDIO] == expected
