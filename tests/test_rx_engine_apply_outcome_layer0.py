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


class TestStrength679Resolution:
    """#679 — the logged NAME resolves through alias → category-collapse →
    bucket-3 at the write chokepoint, and the outcome carries `match_kind` +
    `bucket3` so the completed-history record is tagged, not silently dropped."""

    def test_specific_subtype_resolves_to_specific_ex_id_via_alias(self):
        # "Dumbbell Hammer Curl" hits the specific hammer-curl EX234 via the
        # alias step — NOT collapsed to the coarse "Curl" (EX247).
        db = _FakeDb(layer0_patterns={"EX234": ["Pull-H"]})
        res = apply_session_outcome(db, "Dumbbell Hammer Curl", "2026-06-17", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert res["layer0_exercise_id"] == "EX234"
        assert res["match_kind"] == "alias"
        assert res["bucket3"] is False

    def test_unaliased_subtype_resolves_via_category_collapse(self):
        # "Barbell Bench Press" has no alias; its FIT category "Bench Press"
        # collapses through the coarse map to EX229 (real garmin_fit_parser map).
        db = _FakeDb(layer0_patterns={"EX229": ["Push-H"]})
        res = apply_session_outcome(db, "Barbell Bench Press", "2026-06-17", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert res["layer0_exercise_id"] == "EX229"
        assert res["match_kind"] == "category"
        assert res["bucket3"] is False

    def test_unmapped_name_is_explicit_bucket3_not_silent(self):
        # A legitimate but unmapped name resolves to None AND is tagged bucket-3
        # (record-don't-drop) rather than an ambiguous first-exposure row.
        db = _FakeDb(ei_row={"discipline": "Bike", "type": "Staple",
                             "movement_pattern": "Hinge", "suggested_volume": "3x8"})
        res = apply_session_outcome(db, "Some Obscure Lift", "2026-06-17", _sets(),
                                    rx_source="From Training Log", user_id=1)
        assert res["layer0_exercise_id"] is None
        assert res["bucket3"] is True
        assert res["match_kind"] == "bucket3"
        # Legacy exercise_inventory fallback preserved (no regression).
        assert res["movement_pattern"] == "Hinge"

    def test_existing_row_ex_id_marks_match_kind_existing(self):
        db = _FakeDb(current_rx_row=_rx_row(layer0_exercise_id="EX001"),
                     layer0_patterns={"EX001": ["Squat"]})
        res = apply_session_outcome(db, "Back Squat", "2026-06-17", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert res["match_kind"] == "existing"
        assert res["bucket3"] is False


class TestPublicFkRetired:
    """#430 Slice C (C2) — the public exercise_inventory.id FK is no longer
    read, written, or returned; the per-user tables key off the layer0 EX-id."""

    def test_result_returns_layer0_ex_id_not_public_id(self):
        db = _FakeDb(layer0_patterns={"EX001": ["Squat"]})
        res = apply_session_outcome(db, "Squat", "2026-06-16", _sets(),
                                    rx_source="From FIT Import", user_id=1)
        assert "exercise_id" not in res
        assert res["layer0_exercise_id"] == "EX001"

    def test_writes_never_reference_public_exercise_id(self):
        # Even with an exercise_inventory row present, no write sets exercise_id.
        db = _FakeDb(
            current_rx_row=_rx_row(layer0_exercise_id="EX001"),
            ei_row={"discipline": "Bike", "type": "Staple",
                    "movement_pattern": "Squat", "suggested_volume": "3x8"},
            layer0_patterns={"EX001": ["Squat"]},
        )
        apply_session_outcome(db, "Back Squat", "2026-06-16", _sets(),
                              rx_source="From FIT Import", user_id=1)
        for sql, _ in db.writes:
            # Strip the layer0_ column first so the substring check targets the
            # public `exercise_id` only (it's a substring of layer0_exercise_id).
            cleaned = sql.replace("layer0_exercise_id", "")
            assert "exercise_id" not in cleaned
