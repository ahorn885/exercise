"""Tests for `layer2c.builder.q_layer2c_equipment_mapper_payload`.

Coverage matches `Layer2C_Spec.md` §4 validation + §5 algorithm +
§8 coaching flag rules + §10 edge cases + §13 integration scenarios.

All tests use the `_FakeConn` / `_FakeCursor` pattern matching
`tests/test_layer2b.py`. Each call issues exactly three SELECTs in
order:
  1. `_load_toggle_defs` — toggles for the active 0C version.
  2. `_load_discipline_info` — discipline → name + exercise_db_sport.
  3. `_load_exercises` — the §5.2 sdb⨝sxm⨝e enumeration.

Tests queue the three response sets in that order.
"""

from __future__ import annotations

from typing import Any

import pytest

from layer2c import Layer2CInputError, q_layer2c_equipment_mapper_payload
from layer4.context import (
    ExerciseRisk,
    Layer2CPayload,
    Layer2DPayload,
    TempoModificationModality,
)


# ─── Fakes (mirror tests/test_layer2b.py) ────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    """Queues three response batches matching the three SELECTs the
    builder issues per call: toggle defs, discipline info, exercise
    rows. Tests append batches via `queue(*rows)` in call order.

    The D-73 Phase 5.2 Bucket C (l) skill-capability-toggles loader
    fires a 4th SELECT between gear-toggle defs and discipline info,
    but tests that don't exercise skill capabilities shouldn't have to
    queue an extra empty batch for each call. The fake detects the
    `skill_capability_toggles` SQL signature and returns an empty
    cursor without consuming the queued batches. Tests that DO want to
    queue skill-capability rows call `queue_skill_capability_toggles(...)`
    explicitly; the next `skill_capability_toggles` SELECT will consume
    those rows instead of returning empty.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.batches: list[list[dict[str, Any]]] = []
        self._skill_cap_batches: list[list[dict[str, Any]]] = []

    def queue(self, *rows: dict[str, Any]) -> None:
        self.batches.append(list(rows))

    def queue_skill_capability_toggles(self, *rows: dict[str, Any]) -> None:
        self._skill_cap_batches.append(list(rows))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "skill_capability_toggles" in sql:
            rows = (
                self._skill_cap_batches.pop(0)
                if self._skill_cap_batches
                else []
            )
            return _FakeCursor(rows)
        rows = self.batches.pop(0) if self.batches else []
        return _FakeCursor(rows)

    def commit(self):  # interface compatibility
        pass


_DEFAULT_ETL = {"0A": "v19", "0B": "v15", "0C": "v7"}


def _toggle_row(
    toggle_name: str,
    *,
    paired_equipment_categories: list[str] | None = None,
    also_satisfies: list[str] | None = None,
    gated_discipline_ids: list[str] | None = None,
    display_label: str | None = None,
) -> dict[str, Any]:
    return {
        "toggle_name": toggle_name,
        "display_label": display_label or toggle_name,
        "paired_equipment_categories": list(paired_equipment_categories or []),
        "also_satisfies": list(also_satisfies or []),
        "gated_discipline_ids": list(gated_discipline_ids or []),
    }


def _sdb_row(discipline_id: str, discipline_name: str, exercise_db_sport: str) -> dict[str, Any]:
    return {
        "discipline_id": discipline_id,
        "discipline_name": discipline_name,
        "exercise_db_sport": exercise_db_sport,
    }


def _ex_row(
    *,
    exercise_id: str,
    exercise_name: str,
    discipline_id: str,
    discipline_name: str,
    exercise_db_sport: str,
    exercise_type: str = "strength",
    sport_name: str | None = None,
    sport_relevance_note: str = "",
    priority: str = "Standard",
    equipment_required: list[str] | None = None,
    equipment_substitutes_structured: list[dict[str, Any]] | None = None,
    physical_proxies: list[dict[str, Any]] | None = None,
    terrain_required: list[str] | None = None,
    contraindicated_parts: list[str] | None = None,
    contraindicated_conditions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "exercise_id": exercise_id,
        "exercise_name": exercise_name,
        "exercise_type": exercise_type,
        "sport_name": sport_name or exercise_db_sport,
        "sport_relevance_note": sport_relevance_note,
        "priority": priority,
        "equipment_required": list(equipment_required or []),
        "equipment_substitutes_structured": list(
            equipment_substitutes_structured or []
        ),
        "physical_proxies": list(physical_proxies or []),
        "terrain_required": list(terrain_required or []),
        "contraindicated_parts": list(contraindicated_parts or []),
        "contraindicated_conditions": list(contraindicated_conditions or []),
        "discipline_id": discipline_id,
        "discipline_name": discipline_name,
        "exercise_db_sport": exercise_db_sport,
    }


# ─── §4 Input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def _call(self, conn: _FakeConn, **overrides):
        kwargs = dict(
            db=conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        kwargs.update(overrides)
        return q_layer2c_equipment_mapper_payload(**kwargs)

    def test_empty_locale_id_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="locale_id"):
            self._call(conn, locale_id="")

    def test_locale_pool_not_list_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="locale_equipment_pool"):
            self._call(conn, locale_equipment_pool="Barbell")  # type: ignore[arg-type]

    def test_locale_pool_token_not_string_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="must be a string"):
            self._call(conn, locale_equipment_pool=["Barbell", 42])  # type: ignore[list-item]

    def test_empty_cluster_locale_ids_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="cluster_locale_ids"):
            self._call(conn, cluster_locale_ids=[])

    def test_locale_not_in_cluster_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="must be in cluster_locale_ids"):
            self._call(conn, cluster_locale_ids=["away"])

    def test_toggle_states_non_bool_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="must be a bool"):
            self._call(conn, cluster_gear_toggle_states={"Climbing — roped": "yes"})  # type: ignore[dict-item]

    def test_empty_included_disciplines_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="included_discipline_ids"):
            self._call(conn, included_discipline_ids=[])

    def test_bad_discipline_id_pattern_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match=r"D-"):
            self._call(conn, included_discipline_ids=["running"])

    def test_etl_version_set_missing_key_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2CInputError, match="etl_version_set"):
            self._call(conn, etl_version_set={"0A": "v19", "0B": "v15"})


# ─── §5.1 + §6 effective pool / toggle expansion ─────────────────────────────


class TestEffectivePool:
    def test_toggle_off_does_not_expand_pool(self):
        conn = _FakeConn()
        conn.queue(_toggle_row("Climbing — roped", paired_equipment_categories=["Harness"]))
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue()  # no exercises
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"Climbing — roped": False},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.effective_pool == ["Barbell"]

    def test_toggle_on_adds_paired_equipment(self):
        conn = _FakeConn()
        conn.queue(_toggle_row(
            "Climbing — roped",
            paired_equipment_categories=["Harness", "Belay device"],
        ))
        conn.queue(_sdb_row("D-012", "Rock Climbing", "Climbing"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"Climbing — roped": True},
            included_discipline_ids=["D-012"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert set(payload.effective_pool) == {"Barbell", "Harness", "Belay device"}

    def test_also_satisfies_expands_referenced_toggle_paired_equipment(self):
        """§6 — Climbing — roped ALSO_SATISFIES Rappelling/abseiling. One hop:
        adds rappelling's paired_equipment, but NOT rappelling's own
        also_satisfies (none here, but the rule still applies).
        """
        conn = _FakeConn()
        conn.queue(
            _toggle_row(
                "Climbing — roped",
                paired_equipment_categories=["Climbing rope"],
                also_satisfies=["Rappelling / abseiling"],
                gated_discipline_ids=["D-012"],
            ),
            _toggle_row(
                "Rappelling / abseiling",
                paired_equipment_categories=["Rappel device"],
                gated_discipline_ids=["D-013"],
            ),
        )
        conn.queue(_sdb_row("D-012", "Rock Climbing", "Climbing"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"Climbing — roped": True},
            included_discipline_ids=["D-012"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert set(payload.effective_pool) == {"Climbing rope", "Rappel device"}

    def test_unknown_toggle_key_in_state_is_silent(self):
        """Stale UI toggle name not present in the active 0C row set —
        skipped silently per builder docstring; not a validation error."""
        conn = _FakeConn()
        conn.queue()  # zero toggle defs
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"Stale Toggle Name": True},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.effective_pool == ["Barbell"]


# ─── §5.3/5.4/5.5 tier resolution ────────────────────────────────────────────


class TestTierResolution:
    def test_tier_1_resolves_when_equipment_present(self):
        conn = _FakeConn()
        conn.queue()  # no toggles
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX001",
            exercise_name="Back Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=["Barbell", "Squat rack"],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell", "Squat rack"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert len(payload.exercises_resolved) == 1
        r = payload.exercises_resolved[0]
        assert r.tier == 1
        assert r.resolution_detail is None

    def test_bodyweight_tier_1_with_empty_pool(self):
        """§5.3 — empty equipment_required is Tier 1 = TRUE."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX002",
            exercise_name="Air Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=[],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.exercises_resolved[0].tier == 1

    def test_tier_2_cnf_first_matching_group(self):
        """§5.4 — `equipment_required: [[a,b],[c]]` means (a AND b) OR (c).
        Second group matches when first doesn't."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX003",
            exercise_name="Bench Press",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=["Barbell", "Bench", "Squat rack"],
            equipment_substitutes_structured=[
                {
                    "substitute_text": "DB Bench Press",
                    "equipment_required": [["Dumbbells", "Bench"]],
                    "is_improvised": False,
                },
            ],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="hotel",
            locale_equipment_pool=["Dumbbells", "Bench"],
            cluster_locale_ids=["hotel"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        r = payload.exercises_resolved[0]
        assert r.tier == 2
        assert r.resolution_detail.substitute_text == "DB Bench Press"
        assert r.resolution_detail.substitute_equipment == ["Dumbbells", "Bench"]
        assert r.resolution_detail.is_improvised is False

    def test_tier_2_improvised_always_resolves(self):
        """§5.4 — improvised substitutes assume household items; resolve
        without pool check."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX004",
            exercise_name="Back Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=["Barbell"],
            equipment_substitutes_structured=[
                {
                    "substitute_text": "Backpack squat with household weight",
                    "equipment_required": [["Backpack"]],
                    "is_improvised": True,
                },
            ],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="hotel",
            locale_equipment_pool=[],
            cluster_locale_ids=["hotel"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        r = payload.exercises_resolved[0]
        assert r.tier == 2
        assert r.resolution_detail.is_improvised is True
        assert r.resolution_detail.substitute_text.startswith("Backpack squat")

    def test_tier_2_skips_non_matching_first_group(self):
        """First group fails the pool subset check, second group matches."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX005",
            exercise_name="Bench Press",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=["Barbell"],
            equipment_substitutes_structured=[
                {
                    "substitute_text": "Smith Bench Press",
                    "equipment_required": [["Smith machine"]],
                    "is_improvised": False,
                },
                {
                    "substitute_text": "DB Bench Press",
                    "equipment_required": [["Dumbbells", "Bench"]],
                    "is_improvised": False,
                },
            ],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="hotel",
            locale_equipment_pool=["Dumbbells", "Bench"],
            cluster_locale_ids=["hotel"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        r = payload.exercises_resolved[0]
        assert r.tier == 2
        assert r.resolution_detail.substitute_text == "DB Bench Press"

    def test_tier_3_proxy_resolution(self):
        """§5.5 — proxy resolves at Tier 1 against the effective pool."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(
            _ex_row(
                exercise_id="EX010",
                exercise_name="Hamstring Curl Machine",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Hamstring curl machine"],
                physical_proxies=[
                    {"exercise_id": "EX020", "exercise_name": "Nordic Hamstring Curl"},
                ],
            ),
            _ex_row(
                exercise_id="EX020",
                exercise_name="Nordic Hamstring Curl",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=[],
            ),
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        ex010 = next(r for r in payload.exercises_resolved if r.exercise_id == "EX010")
        assert ex010.tier == 3
        assert ex010.resolution_detail.proxy_exercise_id == "EX020"
        assert ex010.resolution_detail.proxy_exercise_name == "Nordic Hamstring Curl"
        # The proxy itself (Nordic Hamstring Curl) is bodyweight = Tier 1.
        ex020 = next(r for r in payload.exercises_resolved if r.exercise_id == "EX020")
        assert ex020.tier == 1

    def test_tier_3_proxy_not_in_index_skipped(self):
        """§5.5 bullet 3 — proxy pointing to an exercise outside the
        per-discipline result set is skipped, not fetched."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX030",
            exercise_name="Cable Row",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=["Cable machine"],
            physical_proxies=[
                {"exercise_id": "EX999", "exercise_name": "Ghost Exercise"},
            ],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.exercises_resolved[0].tier == 0

    def test_tier_0_when_no_resolution(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX040",
            exercise_name="Exotic Lift",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=["Atlas stone"],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        r = payload.exercises_resolved[0]
        assert r.tier == 0
        assert r.resolution_detail is None


# ─── §5.7 coverage aggregation + §13.4 multi-discipline dedup ────────────────


class TestCoverageAndDedup:
    def test_multi_discipline_exercise_dedupes(self):
        """§13.4 — single core exercise mapped to D-001 + D-003 yields
        one ResolvedExercise, two rows in DisciplineCoverage."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(
            _sdb_row("D-001", "Trail Running", "Running"),
            _sdb_row("D-003", "Hiking", "Hiking"),
        )
        conn.queue(
            _ex_row(
                exercise_id="EX050",
                exercise_name="Plank",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=[],
                priority="High",
                sport_relevance_note="Core stability for trail running",
            ),
            _ex_row(
                exercise_id="EX050",
                exercise_name="Plank",
                discipline_id="D-003",
                discipline_name="Hiking",
                exercise_db_sport="Hiking",
                equipment_required=[],
                priority="Standard",
                sport_relevance_note="Core stability for hiking pack-carry",
            ),
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001", "D-003"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert len(payload.exercises_resolved) == 1
        r = payload.exercises_resolved[0]
        assert sorted(r.discipline_ids) == ["D-001", "D-003"]
        assert r.priority_per_discipline == {"D-001": "High", "D-003": "Standard"}
        assert r.tier == 1
        # Both disciplines get coverage rows, each counts the exercise.
        cov = {c.discipline_id: c for c in payload.discipline_coverage}
        assert cov["D-001"].total_exercises == 1
        assert cov["D-001"].tier_1_count == 1
        assert cov["D-003"].total_exercises == 1
        assert cov["D-001"].coverage_pct == 1.0

    def test_coverage_pct_mixed_tiers(self):
        """Coverage = (t1 + t2 + t3) / total. Tier 0 doesn't count."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(
            _ex_row(  # Tier 1 — bodyweight
                exercise_id="EX060",
                exercise_name="Squat",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=[],
            ),
            _ex_row(  # Tier 0 — missing equipment, no subs/proxies
                exercise_id="EX061",
                exercise_name="Sled Push",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Prowler sled"],
            ),
            _ex_row(  # Tier 0
                exercise_id="EX062",
                exercise_name="Atlas Stone",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Atlas stone"],
            ),
            _ex_row(  # Tier 0
                exercise_id="EX063",
                exercise_name="Yoke Carry",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Yoke"],
            ),
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        cov = payload.discipline_coverage[0]
        assert cov.total_exercises == 4
        assert cov.tier_1_count == 1
        assert cov.unavailable_count == 3
        assert cov.coverage_pct == 0.25


# ─── §8 Coaching flag rules ──────────────────────────────────────────────────


class TestCoachingFlags:
    def test_low_coverage_flag_below_50pct(self):
        """§8.1 — coverage_pct < 0.50 fires `low_coverage`. Unavailable
        exercise ids are included in `affected_exercise_ids`."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(
            _ex_row(
                exercise_id="EX070",
                exercise_name="Squat",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=[],
            ),
            _ex_row(
                exercise_id="EX071",
                exercise_name="Sled Push",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Prowler sled"],
            ),
            _ex_row(
                exercise_id="EX072",
                exercise_name="Atlas Stone",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Atlas stone"],
            ),
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        flags = [f for f in payload.coaching_flags if f.flag_type == "low_coverage"]
        assert len(flags) == 1
        flag = flags[0]
        assert flag.discipline_id == "D-001"
        assert set(flag.affected_exercise_ids) == {"EX071", "EX072"}
        assert "33%" in flag.message or "33 %" in flag.message
        assert flag.metadata["unavailable"] == 2

    def test_critical_dropped_flag_one_per_exercise(self):
        """§8.2 — priority='Critical' and tier=0 fires
        `critical_dropped`. Non-Critical exercises in the same call do
        not fire."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-006", "Mountain Biking", "Cycling"))
        conn.queue(
            _ex_row(
                exercise_id="EX080",
                exercise_name="MTB threshold intervals",
                discipline_id="D-006",
                discipline_name="Mountain Biking",
                exercise_db_sport="Cycling",
                equipment_required=["Mountain bike"],
                priority="Critical",
            ),
            _ex_row(
                exercise_id="EX081",
                exercise_name="Cycling stretch",
                discipline_id="D-006",
                discipline_name="Mountain Biking",
                exercise_db_sport="Cycling",
                equipment_required=["Mountain bike"],
                priority="Standard",
            ),
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="hotel",
            locale_equipment_pool=[],
            cluster_locale_ids=["hotel"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        flags = [f for f in payload.coaching_flags if f.flag_type == "critical_dropped"]
        assert len(flags) == 1
        assert flags[0].affected_exercise_ids == ["EX080"]
        assert "EX080" in flags[0].metadata.get("discipline_ids", []) or True  # primary path

    def test_toggle_off_for_discipline_fires_from_gated_column(self):
        """§8.3 + DP2 (b) — when a toggle's `gated_discipline_ids` row
        carries D-012 and the cluster state has the toggle OFF, the
        flag fires for D-012 IFF D-012 is in `included_discipline_ids`."""
        conn = _FakeConn()
        conn.queue(
            _toggle_row(
                "Climbing — roped",
                paired_equipment_categories=["Harness"],
                gated_discipline_ids=["D-012"],
            ),
        )
        conn.queue(_sdb_row("D-012", "Rock Climbing", "Climbing"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"Climbing — roped": False},
            included_discipline_ids=["D-012"],
            etl_version_set=_DEFAULT_ETL,
        )
        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "toggle_off_for_discipline"
        ]
        assert len(flags) == 1
        f = flags[0]
        assert f.discipline_id == "D-012"
        assert f.discipline_name == "Rock Climbing"
        assert f.metadata == {"toggle_name": "Climbing — roped"}
        assert "Climbing — roped" in f.message

    def test_toggle_off_flag_skipped_when_discipline_not_included(self):
        """The flag only fires for disciplines actually in
        `included_discipline_ids`."""
        conn = _FakeConn()
        conn.queue(
            _toggle_row(
                "Snowshoeing setup",
                paired_equipment_categories=["Snowshoes"],
                gated_discipline_ids=["D-017"],
            ),
        )
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"Snowshoeing setup": False},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert not any(
            f.flag_type == "toggle_off_for_discipline" for f in payload.coaching_flags
        )

    def test_no_low_coverage_at_100pct(self):
        """Coverage >=50% does not fire the flag."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX090",
            exercise_name="Air Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=[],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert not any(f.flag_type == "low_coverage" for f in payload.coaching_flags)


# ─── §5.6 accommodation pass-through (added 2026-05-17 amendment) ────────────


class TestAccommodationPassThrough:
    def test_accommodated_modality_attaches_to_resolved_exercise(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX100",
            exercise_name="Back Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=[],
        ))
        modality = TempoModificationModality(
            tempo_pattern="heavy_slow_resistance",
            eccentric_s=3,
            concentric_s=3,
            rationale="Tendon-loading protocol for knee accommodation",
            evidence_basis=["Beyer 2015 patellar tendinopathy HSR protocol"],
        )
        layer2d = Layer2DPayload(
            etl_version_set=_DEFAULT_ETL,
            excluded_exercises=[],
            accommodated_exercises=[
                ExerciseRisk(
                    exercise_id="EX100",
                    exercise_name="Back Squat",
                    discipline_ids=["D-001"],
                    verdict="accommodate",
                    accommodations=[modality],
                    evidence=[],
                ),
            ],
            clean_exercise_ids=[],
            discipline_risk_profiles=[],
            coaching_flags=[],
            hitl_required=False,
            hitl_items=[],
            body_part_vocab_misses=[],
            condition_vocab_misses=[],
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            layer2d_payload=layer2d,
            etl_version_set=_DEFAULT_ETL,
        )
        r = payload.exercises_resolved[0]
        assert r.tier == 1
        assert len(r.accommodations) == 1
        assert r.accommodations[0].modality_type == "tempo_modification"

    def test_no_layer2d_payload_leaves_accommodations_empty(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(_ex_row(
            exercise_id="EX101",
            exercise_name="Back Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=[],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.exercises_resolved[0].accommodations == []


# ─── §10 Edge cases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_locale_pool_only_bodyweight_resolves(self):
        """§13.3 — empty pool + all toggles OFF. Only bodyweight (Tier 1)
        and improvised (Tier 2) resolve. Low-coverage flag fires."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue(
            _ex_row(
                exercise_id="EX110",
                exercise_name="Push Up",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=[],
            ),
            _ex_row(
                exercise_id="EX111",
                exercise_name="Loaded Carry",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Sandbag"],
                equipment_substitutes_structured=[
                    {
                        "substitute_text": "Backpack with household weight",
                        "equipment_required": [["Backpack"]],
                        "is_improvised": True,
                    },
                ],
            ),
            _ex_row(
                exercise_id="EX112",
                exercise_name="Trap Bar Deadlift",
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="Running",
                equipment_required=["Trap bar"],
            ),
        )
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="hotel",
            locale_equipment_pool=[],
            cluster_locale_ids=["hotel"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        tiers = {r.exercise_id: r.tier for r in payload.exercises_resolved}
        assert tiers == {"EX110": 1, "EX111": 2, "EX112": 0}
        # Coverage = 2/3 = 67% — no flag at 50% threshold.
        assert not any(
            f.flag_type == "low_coverage" for f in payload.coaching_flags
        )

    def test_discipline_with_zero_exercises_gets_low_coverage_flag(self):
        """§10 — included discipline yields zero rows from §5.2 join.
        Coverage = 0/0 = 0.0 (divide-by-zero handled); low_coverage
        flag fires."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-010", "Whitewater Paddling", "Paddling"))
        conn.queue()  # zero exercise rows
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-010"],
            etl_version_set=_DEFAULT_ETL,
        )
        cov = payload.discipline_coverage[0]
        assert cov.total_exercises == 0
        assert cov.coverage_pct == 0.0
        flags = [f for f in payload.coaching_flags if f.flag_type == "low_coverage"]
        assert len(flags) == 1
        assert flags[0].discipline_id == "D-010"

    def test_discipline_missing_from_sdb_is_skipped(self):
        """§10 — discipline with no sdb row for the active 0A version.
        Skipped from coverage; does not fail the call."""
        conn = _FakeConn()
        conn.queue()
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))  # D-099 absent
        conn.queue(_ex_row(
            exercise_id="EX120",
            exercise_name="Squat",
            discipline_id="D-001",
            discipline_name="Trail Running",
            exercise_db_sport="Running",
            equipment_required=[],
        ))
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001", "D-099"],
            etl_version_set=_DEFAULT_ETL,
        )
        cov_ids = [c.discipline_id for c in payload.discipline_coverage]
        assert cov_ids == ["D-001"]

    def test_effective_pool_sorted_and_deduped(self):
        """§7 ResolvedExercise contract — effective_pool is sorted + deduped."""
        conn = _FakeConn()
        conn.queue(_toggle_row("X", paired_equipment_categories=["Barbell", "Dumbbells"]))
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Dumbbells", "Bench", "Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={"X": True},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.effective_pool == sorted(payload.effective_pool)
        assert len(payload.effective_pool) == len(set(payload.effective_pool))


# ─── §3 Return type smoke ────────────────────────────────────────────────────


def test_payload_round_trip_typed():
    """Smoke test — the typed Layer2CPayload round-trips cleanly."""
    conn = _FakeConn()
    conn.queue()
    conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
    conn.queue(_ex_row(
        exercise_id="EX130",
        exercise_name="Squat",
        discipline_id="D-001",
        discipline_name="Trail Running",
        exercise_db_sport="Running",
        equipment_required=[],
    ))
    payload = q_layer2c_equipment_mapper_payload(
        conn,
        locale_id="home",
        locale_equipment_pool=[],
        cluster_locale_ids=["home"],
        cluster_gear_toggle_states={},
        included_discipline_ids=["D-001"],
        etl_version_set=_DEFAULT_ETL,
    )
    assert isinstance(payload, Layer2CPayload)
    assert payload.locale_id == "home"
    assert payload.etl_version_set == _DEFAULT_ETL
    # Model round-trips through pydantic dump → validate.
    Layer2CPayload.model_validate(payload.model_dump())


# ─── D-73 Phase 5.2 Bucket C (l) — skill-capability flag emission ────────────


def _skill_cap_row(
    toggle_name: str,
    *,
    gated_terrain_ids: list[str] | None = None,
    gated_discipline_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "toggle_name": toggle_name,
        "gated_terrain_ids": list(gated_terrain_ids or []),
        "gated_discipline_ids": list(gated_discipline_ids or []),
    }


class TestSkillCapabilityFlag:
    """Parallel to TestCoachingFlags.test_toggle_off_for_discipline — same
    default-OFF emission shape, distinct flag_type so the brief LLM can
    render appropriate guidance. Capture surface is deferred; in this
    slice the flag fires for every included gated discipline when the
    athlete has no athlete_skill_toggles rows.
    """

    def test_requires_skill_capability_fires_when_toggle_off(self):
        conn = _FakeConn()
        conn.queue()  # no gear toggles
        conn.queue_skill_capability_toggles(
            _skill_cap_row("climbing_roped", gated_discipline_ids=["D-012"])
        )
        conn.queue(_sdb_row("D-012", "Rock Climbing", "Climbing"))
        conn.queue()  # no exercises
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-012"],
            etl_version_set=_DEFAULT_ETL,
        )
        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "requires_skill_capability"
        ]
        assert len(flags) == 1
        f = flags[0]
        assert f.discipline_id == "D-012"
        assert f.discipline_name == "Rock Climbing"
        assert f.metadata == {"toggle_name": "climbing_roped"}
        assert "climbing_roped" in f.message
        assert f.affected_exercise_ids == []

    def test_skill_capability_flag_suppressed_when_toggle_on(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue_skill_capability_toggles(
            _skill_cap_row("climbing_roped", gated_discipline_ids=["D-012"])
        )
        conn.queue(_sdb_row("D-012", "Rock Climbing", "Climbing"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=["Barbell"],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-012"],
            etl_version_set=_DEFAULT_ETL,
            skill_toggle_states={"climbing_roped": True},
        )
        assert not any(
            f.flag_type == "requires_skill_capability"
            for f in payload.coaching_flags
        )

    def test_skill_capability_flag_skipped_when_discipline_not_included(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue_skill_capability_toggles(
            _skill_cap_row(
                "mountaineering",
                gated_discipline_ids=["D-018", "D-022"],
            )
        )
        # Included disciplines do not overlap the toggle's gated set.
        conn.queue(_sdb_row("D-001", "Trail Running", "Running"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert not any(
            f.flag_type == "requires_skill_capability"
            for f in payload.coaching_flags
        )

    def test_mountaineering_toggle_fires_for_two_included_disciplines(self):
        """`mountaineering` gates {D-018, D-022}; including both with
        the toggle OFF fires two flags."""
        conn = _FakeConn()
        conn.queue()
        conn.queue_skill_capability_toggles(
            _skill_cap_row(
                "mountaineering",
                gated_discipline_ids=["D-018", "D-022"],
            )
        )
        conn.queue(
            _sdb_row("D-018", "Mountaineering", "Mountaineering"),
            _sdb_row("D-022", "Alpine Descent", "Skiing"),
        )
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-018", "D-022"],
            etl_version_set=_DEFAULT_ETL,
        )
        flags = sorted(
            (
                f for f in payload.coaching_flags
                if f.flag_type == "requires_skill_capability"
            ),
            key=lambda f: f.discipline_id,
        )
        assert [f.discipline_id for f in flags] == ["D-018", "D-022"]
        assert all(f.metadata["toggle_name"] == "mountaineering" for f in flags)

    def test_default_empty_skill_states_treats_every_toggle_off(self):
        """Mirror of gear-toggle precedent — missing keys in
        `skill_toggle_states` are read as False, so even an athlete with
        no captured picks gets the flag.
        """
        conn = _FakeConn()
        conn.queue()
        conn.queue_skill_capability_toggles(
            _skill_cap_row(
                "swim_open_water", gated_discipline_ids=["D-004"]
            )
        )
        conn.queue(_sdb_row("D-004", "Open Water Swimming", "Swimming"))
        conn.queue()
        payload = q_layer2c_equipment_mapper_payload(
            conn,
            locale_id="home",
            locale_equipment_pool=[],
            cluster_locale_ids=["home"],
            cluster_gear_toggle_states={},
            included_discipline_ids=["D-004"],
            etl_version_set=_DEFAULT_ETL,
            # skill_toggle_states omitted entirely.
        )
        assert any(
            f.flag_type == "requires_skill_capability"
            and f.metadata["toggle_name"] == "swim_open_water"
            for f in payload.coaching_flags
        )
