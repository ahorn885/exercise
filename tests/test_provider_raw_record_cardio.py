"""Tests for the inbound indoor-machine flag → provider_raw_record (#681 §4 Slice 2c).

Covers:
  - `resolve_indoor_machine` — the provider indoor token → canonical machine map
    (the inbound analog of Layer-4's `_DISCIPLINE_INDOOR_MACHINES`), incl. the
    "no new vocab" guard (every machine is a real `equipment_items` value).
  - `garmin_connect.normalize_activity` attaching the `_provider_raw` passthrough
    (raw signal + indoor flag) the writer consumes.
  - `routes.garmin._record_provider_raw_cardio` — the table's first writer:
    idempotent INSERT, broad scope (a row for EVERY cardio ingest, indoor flag
    set only when applicable), no-op on a falsy payload.
"""

import json

from layer4.session_feasibility import _DISCIPLINE_INDOOR_MACHINES
from provider_cardio_resolve import INDOOR_MACHINE_MAP, resolve_indoor_machine


# Every canonical machine the cascade can route a discipline to (the only legal
# values the inbound flag may use — "no new vocab").
_CANONICAL_MACHINES = {m for machines in _DISCIPLINE_INDOOR_MACHINES.values()
                       for m in machines}


class TestResolveIndoorMachine:
    def test_garmin_fit_sub_sports_map_to_machines(self):
        # FIT sub_sport tokens (the live single-file / bulk path).
        assert resolve_indoor_machine("garmin", "indoor_cycling") == "Cycling trainer"
        assert resolve_indoor_machine("garmin", "spin") == "Cycling trainer"
        assert resolve_indoor_machine("garmin", "treadmill") == "Treadmill"
        assert resolve_indoor_machine("garmin", "indoor_rowing") == "Rowing ergometer"

    def test_garmin_connect_type_keys_map_to_machines(self):
        # Garmin Connect typeKeys (the API-sync path).
        assert resolve_indoor_machine("garmin", "virtual_ride") == "Cycling trainer"
        assert resolve_indoor_machine("garmin", "treadmill_running") == "Treadmill"
        assert resolve_indoor_machine("garmin", "indoor_running") == "Treadmill"
        assert resolve_indoor_machine("garmin", "stair_climbing") == "Stair climber"

    def test_outdoor_and_unknown_are_none(self):
        assert resolve_indoor_machine("garmin", "trail_running") is None
        assert resolve_indoor_machine("garmin", "cycling") is None
        assert resolve_indoor_machine("garmin", "") is None
        assert resolve_indoor_machine("garmin", None) is None
        assert resolve_indoor_machine("strava", "VirtualRide") is None  # not wired yet
        assert resolve_indoor_machine("nonesuch", "treadmill") is None

    def test_provider_key_is_case_insensitive(self):
        assert resolve_indoor_machine("GARMIN", "treadmill") == "Treadmill"

    def test_no_new_vocab_every_machine_is_canonical(self):
        # Slice 2c adds NO equipment vocab — every mapped machine must already be
        # a canonical `equipment_items` value the feasibility cascade emits.
        for provider, mapping in INDOOR_MACHINE_MAP.items():
            for token, machine in mapping.items():
                assert machine in _CANONICAL_MACHINES, f"{provider}:{token}={machine}"


class TestNormalizeActivityProviderRaw:
    def test_indoor_activity_carries_machine_and_raw(self):
        from garmin_connect import normalize_activity
        norm = normalize_activity({
            "activityType": {"typeKey": "virtual_ride"},
            "activityId": 555,
            "startTimeLocal": "2026-06-01 07:30:00",
        })
        raw = norm["_provider_raw"]
        assert raw["provider"] == "garmin"
        assert raw["observed_at"] == "2026-06-01"
        assert raw["bucket"] == 1
        assert raw["canonical_ref"] == "D-006"          # indoor ride → cycling D-id
        assert raw["payload"]["type_key"] == "virtual_ride"
        assert raw["payload"]["indoor_machine"] == "Cycling trainer"
        assert raw["payload"]["plan_sport_type"] == "cycling"

    def test_outdoor_activity_has_raw_but_no_machine(self):
        from garmin_connect import normalize_activity
        norm = normalize_activity({
            "activityType": {"typeKey": "trail_running"},
            "activityId": 556,
            "startTimeLocal": "2026-06-02 06:00:00",
        })
        raw = norm["_provider_raw"]
        assert raw["canonical_ref"] == "D-001"
        assert raw["payload"]["indoor_machine"] is None


# ─── _record_provider_raw_cardio (the writer) ───────────────────────────────


class _FakeCursor:
    lastrowid = 1


class _FakeConn:
    """Records SQL; optionally raises on any statement containing `fail_on`."""
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")
        return _FakeCursor()


def _insert_call(conn):
    return next((c for c in conn.calls if "provider_raw_record" in c[0]), None)


def _raw(machine, *, bucket=1, canonical_ref="D-006", observed_at="2026-06-01"):
    return {
        "provider": "garmin",
        "observed_at": observed_at,
        "bucket": bucket,
        "canonical_ref": canonical_ref,
        "payload": {"type_key": "virtual_ride", "indoor_machine": machine},
    }


class TestRecordProviderRawCardio:
    def test_writes_indoor_row_with_machine_in_payload(self):
        from routes.garmin import _record_provider_raw_cardio
        conn = _FakeConn()
        _record_provider_raw_cardio(conn, _raw("Cycling trainer"), uid=3, external_id="555")
        sqls = [c[0] for c in conn.calls]
        assert any("SAVEPOINT provider_raw_cardio" in s for s in sqls)   # best-effort wrap
        assert any("RELEASE SAVEPOINT provider_raw_cardio" in s for s in sqls)
        sql, params = _insert_call(conn)
        assert "ON CONFLICT" in sql                       # idempotent
        assert params[0] == 3                             # user_id
        assert params[1:4] == ("garmin", "cardio", "555")  # provider/type/external_id
        assert params[4] == "2026-06-01"                  # observed_at
        assert json.loads(params[5])["indoor_machine"] == "Cycling trainer"
        assert params[6] == 1                             # bucket
        assert params[7] == "D-006"                       # canonical_ref

    def test_writes_outdoor_row_too_broad_scope(self):
        # Andy's call: record-don't-drop for EVERY cardio ingest, not only indoor.
        from routes.garmin import _record_provider_raw_cardio
        conn = _FakeConn()
        _record_provider_raw_cardio(
            conn, _raw(None, canonical_ref="D-001"), uid=3, external_id="fit:abc")
        params = _insert_call(conn)[1]
        assert json.loads(params[5])["indoor_machine"] is None
        assert params[7] == "D-001"

    def test_empty_observed_at_coerced_to_null(self):
        # A FIT whose session timestamp didn't parse → date '' must become NULL,
        # not an invalid TIMESTAMP literal that 500s the whole import.
        from routes.garmin import _record_provider_raw_cardio
        conn = _FakeConn()
        _record_provider_raw_cardio(conn, _raw(None, observed_at=""), uid=3, external_id="z")
        assert _insert_call(conn)[1][4] is None

    def test_db_error_is_swallowed_and_rolled_back(self):
        # Best-effort: a failing corroboration write must NOT propagate (which
        # would abort the cardio_log import) — it rolls back to the savepoint.
        from routes.garmin import _record_provider_raw_cardio
        conn = _FakeConn(fail_on="INSERT INTO provider_raw_record")
        _record_provider_raw_cardio(conn, _raw("Treadmill"), uid=3, external_id="555")
        sqls = [c[0] for c in conn.calls]
        assert any("ROLLBACK TO SAVEPOINT provider_raw_cardio" in s for s in sqls)

    def test_falsy_payload_is_noop(self):
        from routes.garmin import _record_provider_raw_cardio
        conn = _FakeConn()
        _record_provider_raw_cardio(conn, None, uid=3, external_id="x")
        _record_provider_raw_cardio(conn, {}, uid=3, external_id="x")
        assert conn.calls == []
