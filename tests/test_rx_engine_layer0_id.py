"""Tests for `rx_engine.current_rx_by_layer0_id` — the EX-id-keyed read of a
current prescription (#335 Phase 2b identity slice)."""

from rx_engine import current_rx_by_layer0_id


class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeDb:
    """Maps (layer0_exercise_id, user_id) → dict-like row; None for misses."""

    def __init__(self, rows=None):
        self._rows = rows or {}
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, tuple(params)))
        assert "layer0_exercise_id=?" in sql  # keyed off the EX-id, not name
        ex_id, uid = params[0], params[1]
        return _Cursor(self._rows.get((ex_id, uid)))


def _row(sets=3, reps=5, weight=61.235, duration=None, mp="Squat"):
    return {
        'current_sets': sets, 'current_reps': reps,
        'current_weight': weight, 'current_duration': duration,
        'movement_pattern': mp,
    }


class TestCurrentRxByLayer0Id:
    def test_hit_returns_baseline_dict(self):
        db = _FakeDb({("EX001", 1): _row()})
        rx = current_rx_by_layer0_id(db, 1, "EX001")
        assert rx == {
            'sets': 3, 'reps': 5, 'weight_kg': 61.235,
            'duration_sec': None, 'movement_pattern': "Squat",
        }

    def test_miss_returns_none(self):
        db = _FakeDb({("EX001", 1): _row()})
        assert current_rx_by_layer0_id(db, 1, "EX999") is None

    def test_scoped_by_user(self):
        db = _FakeDb({("EX001", 1): _row()})
        assert current_rx_by_layer0_id(db, 2, "EX001") is None

    def test_empty_ex_id_short_circuits_without_query(self):
        db = _FakeDb()
        assert current_rx_by_layer0_id(db, 1, None) is None
        assert current_rx_by_layer0_id(db, 1, "") is None
        assert db.queries == []  # no DB round-trip on an absent EX-id

    def test_sparse_row_no_weight_no_duration_falls_through(self):
        db = _FakeDb({("EX001", 1): _row(weight=None, duration=None)})
        assert current_rx_by_layer0_id(db, 1, "EX001") is None

    def test_duration_only_row_is_a_hit(self):
        db = _FakeDb({("EX-PLANK", 1): _row(weight=None, duration=60, mp="Core")})
        rx = current_rx_by_layer0_id(db, 1, "EX-PLANK")
        assert rx['duration_sec'] == 60 and rx['weight_kg'] is None
