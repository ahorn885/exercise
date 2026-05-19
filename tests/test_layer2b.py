"""Tests for `layer2b.builder.q_layer2b_terrain_classifier_payload`.

Coverage matches `Layer2B_Spec.md` §13 test scenarios + §10 edge cases:
- §4 input validation (TRN pattern, pct ranges, sum bounds, ETL key)
- §13.1 PGE MN baseline — all-covered + one water-gap with high-fidelity proxy
- §13.2 Alpine race — unbridgeable gap surfaces flag + summary.any_unbridgeable
- §13.3 Empty locale — every race terrain becomes a gap
- §13.4 Controlled-vocab violation — non-TRN id fails validation
- §10 multiple gap rules — ORDER BY picks highest fidelity (single SQL call)
- §10 terrain id not in terrain_types — terrain_name=None + undefined_gap
- §8.2 requires_coached_introduction flag fires on whitewater note token

All tests use the `_FakeConn` / `_FakeCursor` pattern matching
`tests/test_layer2a.py` + `tests/test_layer2d.py`. Each call issues
1 + N SELECTs: 1 for the terrain-name lookup, N for per-gap proxy
resolution. Tests queue responses in that order.
"""

from __future__ import annotations

import pytest

from layer2b import Layer2BInputError, q_layer2b_terrain_classifier_payload
from layer4.context import Layer2BPayload, RaceTerrainEntry


# ─── Fakes (mirror tests/test_layer2a.py) ────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []

    def queue_name_rows(self, rows):
        self.responses.append((None, list(rows)))

    def queue_proxy_row(self, row):
        # Per-gap _load_best_proxy returns a single row (or None).
        self.responses.append((row, []))

    def queue_no_proxy(self):
        self.responses.append((None, []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

    def commit(self):  # not used by 2B but matches the _FakeConn shape
        pass


_DEFAULT_ETL = {"0A": "v19", "0B": "v15", "0C": "v7"}


def _name_row(terrain_id: str, canonical_name: str) -> dict:
    return {"terrain_id": terrain_id, "canonical_name": canonical_name}


def _proxy_row(
    target_terrain_id: str,
    target_terrain_name: str,
    *,
    proxy_terrain_id: str | None,
    proxy_terrain_name: str | None,
    gap_severity: str,
    proxy_fidelity: float | None,
    adaptation_weeks_low: int | None = None,
    adaptation_weeks_high: int | None = None,
    proxy_methods: list[str] | None = None,
    uncoverable_stimulus: list[str] | None = None,
    prescription_note: str = "",
) -> dict:
    return {
        "target_terrain_id": target_terrain_id,
        "target_terrain_name": target_terrain_name,
        "proxy_terrain_id": proxy_terrain_id,
        "proxy_terrain_name": proxy_terrain_name,
        "gap_severity": gap_severity,
        "adaptation_weeks_low": adaptation_weeks_low,
        "adaptation_weeks_high": adaptation_weeks_high,
        "proxy_fidelity": proxy_fidelity,
        "proxy_methods": list(proxy_methods or []),
        "uncoverable_stimulus": list(uncoverable_stimulus or []),
        "prescription_note": prescription_note,
    }


# ─── §4 input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_race_terrain_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2BInputError, match="non-empty"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=[],
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_invalid_trn_pattern_raises(self):
        conn = _FakeConn()
        bad = RaceTerrainEntry(terrain_id="trail", pct_of_race=100.0)
        with pytest.raises(Layer2BInputError, match="TRN"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=[bad],
                locale_terrain_ids=[],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_pct_sum_too_low_raises(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=30.0),
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=20.0),
        ]
        with pytest.raises(Layer2BInputError, match="sum"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=entries,
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_pct_sum_too_high_raises(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=80.0),
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=50.0),
        ]
        with pytest.raises(Layer2BInputError, match="sum"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=entries,
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_invalid_locale_id_raises(self):
        conn = _FakeConn()
        entries = [RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=100.0)]
        with pytest.raises(Layer2BInputError, match="locale_terrain_ids"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=entries,
                locale_terrain_ids=["road"],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_empty_disciplines_raises(self):
        conn = _FakeConn()
        entries = [RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=100.0)]
        with pytest.raises(Layer2BInputError, match="included_discipline_ids"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=entries,
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=[],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_missing_etl_key_raises(self):
        conn = _FakeConn()
        entries = [RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=100.0)]
        with pytest.raises(Layer2BInputError, match="etl_version_set"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=entries,
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=["D-001"],
                etl_version_set={"0A": "v19"},
            )


# ─── §13.1 PGE MN baseline ───────────────────────────────────────────────────


class TestPGEBaseline:
    """Andy's PGE 2026 — Minnesota: 4 covered terrains + 1 water gap with
    high-fidelity Pool proxy. Deployed migration has TRN-008=Pool and
    TRN-009=Flat Water (spec §13.1 swap noted in CARRY_FORWARD nits)."""

    def test_pge_baseline(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=35.0),  # Groomed
            RaceTerrainEntry(terrain_id="TRN-003", pct_of_race=30.0),  # Technical
            RaceTerrainEntry(terrain_id="TRN-004", pct_of_race=15.0),  # Hill
            RaceTerrainEntry(terrain_id="TRN-009", pct_of_race=15.0),  # Flat Water (gap)
            RaceTerrainEntry(terrain_id="TRN-016", pct_of_race=5.0),   # Indoor
        ]
        locale = ["TRN-002", "TRN-003", "TRN-004", "TRN-008", "TRN-016"]

        conn.queue_name_rows([
            _name_row("TRN-002", "Groomed Trail"),
            _name_row("TRN-003", "Technical Trail"),
            _name_row("TRN-004", "Hill / Rolling"),
            _name_row("TRN-009", "Flat Water"),
            _name_row("TRN-016", "Indoor / Gym"),
        ])
        conn.queue_proxy_row(_proxy_row(
            "TRN-009", "Flat Water",
            proxy_terrain_id="TRN-008",
            proxy_terrain_name="Pool",
            gap_severity="low",
            proxy_fidelity=0.75,
            adaptation_weeks_low=2,
            adaptation_weeks_high=4,
            proxy_methods=["Pool swimming", "Paddling ergometer"],
            uncoverable_stimulus=["cold_exposure"],
            prescription_note="Pool is a high-fidelity proxy for flat water aerobic base.",
        ))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=locale,
            included_discipline_ids=["D-001", "D-005", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert isinstance(payload, Layer2BPayload)
        assert payload.summary.total_race_terrain_count == 5
        assert payload.summary.covered_count == 4
        assert payload.summary.gap_count == 1
        assert payload.summary.bridgeable_count == 1
        assert payload.summary.unbridgeable_count == 0
        assert payload.summary.pct_of_race_uncovered == 15.0
        assert payload.summary.any_unbridgeable is False
        assert payload.summary.worst_fidelity == 0.75
        assert payload.summary.min_adaptation_weeks_needed == 4
        assert payload.coaching_flags == []
        # The water gap surfaces on the right row only.
        water_row = next(rt for rt in payload.race_terrain if rt.terrain_id == "TRN-009")
        assert water_row.available_locally is False
        assert water_row.gap is not None
        assert water_row.gap.gap_severity == "low"
        assert water_row.gap.proxy_terrain_id == "TRN-008"


# ─── §13.2 Alpine race — unbridgeable ────────────────────────────────────────


class TestUnbridgeableAlpine:
    def test_alpine_descent_unbridgeable_flag(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=40.0),
            RaceTerrainEntry(terrain_id="TRN-012", pct_of_race=30.0),  # Snow alpine
            RaceTerrainEntry(terrain_id="TRN-004", pct_of_race=30.0),
        ]
        locale = ["TRN-001", "TRN-004", "TRN-016"]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-004", "Hill / Rolling"),
            _name_row("TRN-012", "Snow / Winter Alpine"),
        ])
        conn.queue_proxy_row(_proxy_row(
            "TRN-012", "Snow / Winter Alpine",
            proxy_terrain_id=None,
            proxy_terrain_name=None,
            gap_severity="unbridgeable",
            proxy_fidelity=None,
            uncoverable_stimulus=["technical_descent", "balance_dynamic"],
            prescription_note="Alpine descent skill cannot be developed off-snow.",
        ))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=locale,
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert payload.summary.any_unbridgeable is True
        assert payload.summary.unbridgeable_count == 1
        assert payload.summary.bridgeable_count == 0
        assert payload.summary.pct_of_race_uncovered == 30.0
        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert flag_types == ["unbridgeable_terrain"]
        assert payload.coaching_flags[0].target_terrain_id == "TRN-012"


# ─── §13.3 Empty locale degenerate ───────────────────────────────────────────


class TestEmptyLocale:
    def test_no_locale_terrain_all_gaps(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=50.0),
            RaceTerrainEntry(terrain_id="TRN-016", pct_of_race=50.0),
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-016", "Indoor / Gym"),
        ])
        # Both targets have no rules whose proxy is in the empty locale set
        # AND no NULL-proxy unbridgeable row → both go undefined.
        conn.queue_no_proxy()
        conn.queue_no_proxy()

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=[],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert payload.summary.gap_count == 2
        assert payload.summary.pct_of_race_uncovered == 100.0
        assert payload.summary.any_undefined is True
        # All flags are undefined_gap, no crashes
        assert {f.flag_type for f in payload.coaching_flags} == {"undefined_gap"}
        assert len(payload.coaching_flags) == 2


# ─── §10 multiple gap rules — ORDER BY picks best ────────────────────────────


class TestMultipleProxyRules:
    """When the same target has multiple proxy rules with different
    fidelities, the SQL ORDER BY clause picks the highest. This test
    verifies the per-gap _load_best_proxy issues exactly ONE SELECT
    (LIMIT 1) and the test fixture only needs to queue the winning row."""

    def test_best_proxy_returned(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-005", pct_of_race=100.0),
        ]
        # Athlete has Hill + Road; per deployed rules TRN-005 has multiple
        # gap rules with proxies TRN-001 (0.40) and TRN-004 (0.60). The
        # SQL ORDER BY picks 0.60 — test fixture supplies the winning row.
        locale = ["TRN-001", "TRN-004"]
        conn.queue_name_rows([_name_row("TRN-005", "Mountain / Alpine")])
        conn.queue_proxy_row(_proxy_row(
            "TRN-005", "Mountain / Alpine",
            proxy_terrain_id="TRN-004",
            proxy_terrain_name="Hill / Rolling",
            gap_severity="medium",
            proxy_fidelity=0.60,
            adaptation_weeks_low=6,
            adaptation_weeks_high=10,
        ))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=locale,
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert payload.summary.bridgeable_count == 1
        gap = payload.terrain_gaps[0]
        assert gap.proxy_terrain_id == "TRN-004"
        assert gap.proxy_fidelity == 0.60
        assert gap.gap_severity == "medium"


# ─── §10 unknown terrain id — undefined_gap surfacing ────────────────────────


class TestUnknownTerrainId:
    def test_unknown_terrain_id_undefined_gap(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-999", pct_of_race=100.0),
        ]
        # Name lookup returns nothing for TRN-999 (not in terrain_types).
        conn.queue_name_rows([])
        # Proxy lookup also returns nothing (no rule rows for TRN-999).
        conn.queue_no_proxy()

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert len(payload.terrain_gaps) == 1
        gap = payload.terrain_gaps[0]
        assert gap.gap_severity == "undefined"
        assert gap.target_terrain_id == "TRN-999"
        assert gap.proxy_terrain_id is None
        assert payload.summary.any_undefined is True
        # `any_unbridgeable` does NOT fire for undefined gaps per §5.5 split.
        assert payload.summary.any_unbridgeable is False
        # race_terrain row carries terrain_name=None per §10.
        assert payload.race_terrain[0].terrain_name is None
        assert {f.flag_type for f in payload.coaching_flags} == {"undefined_gap"}


# ─── §8.2 requires_coached_introduction ──────────────────────────────────────


class TestCoachedIntroFlag:
    def test_whitewater_coached_intro_flag(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-011", pct_of_race=100.0),
        ]
        locale = ["TRN-009"]
        conn.queue_name_rows([_name_row("TRN-011", "Whitewater")])
        conn.queue_proxy_row(_proxy_row(
            "TRN-011", "Whitewater",
            proxy_terrain_id="TRN-009",
            proxy_terrain_name="Flat Water",
            gap_severity="critical",
            proxy_fidelity=0.55,  # >= 0.5 threshold
            adaptation_weeks_low=8,
            adaptation_weeks_high=12,
            prescription_note=(
                "Whitewater technique requires coached introduction "
                "before race. Pool rolling is a useful foundation."
            ),
        ))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=locale,
            included_discipline_ids=["D-008b"],
            etl_version_set=_DEFAULT_ETL,
        )

        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert "requires_coached_introduction" in flag_types
        coached = next(
            f for f in payload.coaching_flags
            if f.flag_type == "requires_coached_introduction"
        )
        assert coached.metadata["fidelity"] == 0.55
        assert coached.target_terrain_id == "TRN-011"

    def test_coached_intro_does_not_fire_below_fidelity_threshold(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-011", pct_of_race=100.0),
        ]
        conn.queue_name_rows([_name_row("TRN-011", "Whitewater")])
        conn.queue_proxy_row(_proxy_row(
            "TRN-011", "Whitewater",
            proxy_terrain_id="TRN-009",
            proxy_terrain_name="Flat Water",
            gap_severity="critical",
            proxy_fidelity=0.30,  # < 0.5 threshold — no coached flag
            prescription_note=(
                "Whitewater technique requires coached introduction."
            ),
        ))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-009"],
            included_discipline_ids=["D-008b"],
            etl_version_set=_DEFAULT_ETL,
        )

        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert "requires_coached_introduction" not in flag_types


# ─── Smoke / clean baseline ──────────────────────────────────────────────────


class TestCleanBaseline:
    """All race terrain available locally — fast path, no SQL beyond names."""

    def test_all_covered_no_gaps(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=60.0),
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=40.0),
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-002", "Groomed Trail"),
        ])

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001", "TRN-002", "TRN-016"],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert payload.summary.gap_count == 0
        assert payload.summary.covered_count == 2
        assert payload.summary.worst_fidelity == 1.0
        assert payload.summary.pct_of_race_uncovered == 0.0
        assert payload.summary.any_unbridgeable is False
        assert payload.summary.any_undefined is False
        assert payload.terrain_gaps == []
        assert payload.coaching_flags == []
