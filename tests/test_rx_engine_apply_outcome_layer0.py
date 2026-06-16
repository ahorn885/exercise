"""Tests for `rx_engine.apply_session_outcome`'s layer0 EX-id write path
(#430 Slice C). The progression key is sourced from `layer0.exercises.
movement_patterns` via the EX-id, and `current_rx.layer0_exercise_id` is
self-healed on every write — the exercise_inventory name read is now only a
fallback for un-migrated names."""

from rx_engine import apply_session_outcome


class _Cursor:
    def __init__(self, row=None):
        self._row = row
        self.lastrowid = 1

    def fetchone(self):
        return self._row


class _FakeDb:
    """Routes the three reads (current_rx / exercise_inventory / layer0.exercises)
    and records the current_rx write (its SQL + params) for assertions."""

    def __init__(self, current_rx_row=None, ei_row=None, layer0_patterns=None):
        self._current_rx_row = current_rx_row
        self._ei_row = ei_row
        # layer0_patterns: {ex_id: [patterns]} — None row when ex_id absent.
        self._layer0_patterns = layer0_patterns or {}
        self.writes = []  # (sql, params) for INSERT/UPDATE current_rx
        self.committed = False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT") and "FROM current_rx" in s:
            return _Cursor(self._current_rx_row)
        if s.startswith("SELECT") and "FROM exercise_inventory" in s:
            return _Cursor(self._ei_row)
        if "FROM layer0.exercises" in s:
            ex_id = params[0]
            if ex_id in self._layer0_patterns:
                return _Cursor({"movement_patterns": self._layer0_patterns[ex_id]})
            return _Cursor(None)
        if s.startswith("INSERT INTO current_rx") or s.startswith("UPDATE current_rx"):
            self.writes.append((s, tuple(params)))
            return _Cursor()
        raise AssertionError(f"unexpected query: {s[:80]}")

    def commit(self):
        self.committed = True


def _rx_row(**over):
    row = {
        "movement_pattern": "Various", "weight_increment": None,
        "consecutive_failures": 0, "sessions_since_progress": 0,
        "layer0_exercise_id": None,
        "current_sets": 3, "current_reps": 5,
        "current_weight": 60.0, "current_duration": None,
    }
    row.update(over)
    return row


def _sets(weight=62.5, reps=5, n=3):
    return [{"set_number": i, "reps": reps, "weight_kg": weight, "duration_sec": None}
            for i in range(1, n + 1)]


class TestLayer0ProgressionSource:
    def test_existing_row_ex_id_drives_progression_over_stale_pattern(self):
        # Stored movement_pattern is stale ("Hinge"); layer0 EX001 → Squat wins.
        db = _FakeDb(
            current_rx_row=_rx_row(movement_pattern="Hinge", layer0_exercise_id="EX001"),
            layer0_patterns={"EX001": ["Squat"]},
        )
        res = apply_session_outcome(db, "Back Squat", "2026-06-16", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert res["movement_pattern"] == "Squat"
        assert any(s.startswith("UPDATE current_rx") for s, _ in db.writes)

    def test_new_exercise_resolves_ex_id_from_name_map_and_persists(self):
        # No current_rx row, no exercise_inventory row — the curated name map
        # resolves "Squat" → EX001 → layer0 Squat, and the INSERT records it.
        db = _FakeDb(layer0_patterns={"EX001": ["Squat"]})
        res = apply_session_outcome(db, "Squat", "2026-06-16", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert res["movement_pattern"] == "Squat"
        insert = next(s for s, _ in db.writes if s.startswith("INSERT"))
        params = next(p for s, p in db.writes if s.startswith("INSERT"))
        assert "layer0_exercise_id" in insert
        assert "EX001" in params  # the resolved EX-id is written

    def test_unmapped_name_falls_back_to_exercise_inventory_pattern(self):
        # No EX-id resolvable → layer0 is never queried; legacy ei pattern used.
        db = _FakeDb(ei_row={"id": 42, "discipline": "Bike", "type": "Staple",
                             "movement_pattern": "Hinge", "suggested_volume": "3x8"})
        res = apply_session_outcome(db, "Some Obscure Lift", "2026-06-16", _sets(),
                                    rx_source="From Training Log", user_id=1)
        assert res["movement_pattern"] == "Hinge"
        params = next(p for s, p in db.writes if s.startswith("INSERT"))
        assert None in params  # layer0_exercise_id written as None

    def test_existing_ex_id_preserved_via_coalesce(self):
        db = _FakeDb(
            current_rx_row=_rx_row(layer0_exercise_id="EX001"),
            layer0_patterns={"EX001": ["Squat"]},
        )
        apply_session_outcome(db, "Back Squat", "2026-06-16", _sets(),
                              rx_source="From FIT Import", user_id=1)
        update = next(s for s, _ in db.writes if s.startswith("UPDATE"))
        assert "layer0_exercise_id=COALESCE(layer0_exercise_id, ?)" in update

    def test_ex_id_present_but_unknown_to_layer0_falls_back(self):
        # EX-id resolves from name map but layer0 has no such row (e.g. superseded)
        # → fall back to the stored/legacy pattern, no crash.
        db = _FakeDb(current_rx_row=_rx_row(movement_pattern="Pull",
                                            layer0_exercise_id="EX999"),
                     layer0_patterns={})
        res = apply_session_outcome(db, "Back Squat", "2026-06-16", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert res["movement_pattern"] == "Pull"
