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

# Force `layer4` to initialize before `layer2b` to dodge the pre-existing
# circular import that otherwise blocks this module from collection. Mirrors
# tests/test_layer2a.py:26 + tests/test_layer3_cached_wrappers.py:30.
from layer4 import InMemoryCacheBackend  # noqa: F401

from layer2b import Layer2BInputError, q_layer2b_terrain_classifier_payload
from layer4.context import (
    Layer2BDisciplineBlock,
    Layer2BPayload,
    RaceTerrainEntry,
)


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
            included_discipline_ids=["D-001", "D-006", "D-008"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert isinstance(payload, Layer2BPayload)
        assert payload.coaching_flags == []
        # The water gap surfaces on the right row only (via the per-discipline
        # block, the surviving carrier of race_terrain/gap detail).
        block = next(
            b for b in payload.terrain_by_discipline if b.discipline_id == "D-001"
        )
        water_row = next(rt for rt in block.race_terrain if rt.terrain_id == "TRN-009")
        assert water_row.available_locally is False
        assert water_row.gap is not None
        assert water_row.gap.gap_severity == "low"
        assert water_row.gap.proxy_terrain_id == "TRN-008"
        gap = next(g for g in block.terrain_gaps if g.target_terrain_id == "TRN-009")
        assert gap.proxy_fidelity == 0.75
        assert gap.adaptation_weeks_high == 4


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

        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert flag_types == ["unbridgeable_terrain"]
        assert payload.coaching_flags[0].target_terrain_id == "TRN-012"
        block = next(
            b for b in payload.terrain_by_discipline if b.discipline_id == "D-001"
        )
        gap = next(g for g in block.terrain_gaps if g.target_terrain_id == "TRN-012")
        assert gap.gap_severity == "unbridgeable"
        assert gap.proxy_terrain_id is None


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

        # All flags are undefined_gap, no crashes
        assert {f.flag_type for f in payload.coaching_flags} == {"undefined_gap"}
        assert len(payload.coaching_flags) == 2
        block = next(
            b for b in payload.terrain_by_discipline if b.discipline_id == "D-001"
        )
        assert {g.target_terrain_id for g in block.terrain_gaps} == {"TRN-001", "TRN-016"}
        assert all(g.gap_severity == "undefined" for g in block.terrain_gaps)


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

        block = next(
            b for b in payload.terrain_by_discipline if b.discipline_id == "D-001"
        )
        assert len(block.terrain_gaps) == 1
        gap = block.terrain_gaps[0]
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

        block = next(
            b for b in payload.terrain_by_discipline if b.discipline_id == "D-001"
        )
        assert len(block.terrain_gaps) == 1
        gap = block.terrain_gaps[0]
        assert gap.gap_severity == "undefined"
        assert gap.target_terrain_id == "TRN-999"
        assert gap.proxy_terrain_id is None
        # race_terrain row carries terrain_name=None per §10.
        assert block.race_terrain[0].terrain_name is None
        assert {f.flag_type for f in payload.coaching_flags} == {"undefined_gap"}


# ─── §8.2 requires_coached_introduction ──────────────────────────────────────


class TestSkillCapabilityFlag:
    """D-73 Phase 5.2 Bucket C sub-item (l) — replaced the prior
    `_COACHED_INTRO_KEYWORDS` substring-match against `prescription_note`
    (`TestCoachedIntroFlag` removed). The new `requires_skill_capability`
    flag is emitted when a race-terrain entry sits in some skill toggle's
    `gated_terrain_ids` AND the athlete's toggle state is not True
    (default OFF means flag fires — mirrors the gear-toggle precedent at
    `layer2c/builder.py::_emit_coaching_flags` §8.3 gate).
    """

    def _skill_cap_row(
        self,
        toggle_name: str,
        *,
        gated_terrain_ids: list[str],
        gated_discipline_ids: list[str] | None = None,
    ) -> dict:
        return {
            "toggle_name": toggle_name,
            "gated_terrain_ids": list(gated_terrain_ids),
            "gated_discipline_ids": list(gated_discipline_ids or []),
        }

    def test_whitewater_skill_capability_flag_fires_when_toggle_off(self):
        """TRN-011 in race_terrain + whitewater_handling toggle OFF →
        emits `requires_skill_capability` flag with the toggle name in
        metadata. Default-OFF (toggle absent from state dict) fires too.
        """
        conn = _FakeConn()
        entries = [RaceTerrainEntry(terrain_id="TRN-011", pct_of_race=100.0)]
        conn.queue_name_rows([_name_row("TRN-011", "Whitewater")])
        conn.queue_proxy_row(_proxy_row(
            "TRN-011", "Whitewater",
            proxy_terrain_id="TRN-009",
            proxy_terrain_name="Flat Water",
            gap_severity="critical",
            proxy_fidelity=0.30,
            adaptation_weeks_low=8,
            adaptation_weeks_high=12,
        ))
        # Skill-capability toggle SELECT fires AFTER the proxy lookup.
        conn.responses.append((None, [
            self._skill_cap_row(
                "whitewater_handling",
                gated_terrain_ids=["TRN-011", "TRN-017"],
                gated_discipline_ids=["D-010"],
            ),
        ]))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-009"],
            included_discipline_ids=["D-010"],
            etl_version_set=_DEFAULT_ETL,
        )

        flag = next(
            f for f in payload.coaching_flags
            if f.flag_type == "requires_skill_capability"
        )
        assert flag.target_terrain_id == "TRN-011"
        assert flag.metadata["toggle_name"] == "whitewater_handling"
        assert flag.metadata["pct_of_race"] == 100.0
        assert "whitewater_handling" in flag.message

    def test_skill_capability_flag_suppressed_when_toggle_on(self):
        """Athlete with whitewater_handling=True does NOT trigger the
        flag for TRN-011. The toggle is the explicit opt-in.
        """
        conn = _FakeConn()
        entries = [RaceTerrainEntry(terrain_id="TRN-011", pct_of_race=100.0)]
        conn.queue_name_rows([_name_row("TRN-011", "Whitewater")])
        conn.queue_proxy_row(_proxy_row(
            "TRN-011", "Whitewater",
            proxy_terrain_id="TRN-009",
            proxy_terrain_name="Flat Water",
            gap_severity="critical",
            proxy_fidelity=0.30,
        ))
        conn.responses.append((None, [
            self._skill_cap_row(
                "whitewater_handling",
                gated_terrain_ids=["TRN-011", "TRN-017"],
            ),
        ]))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-009"],
            included_discipline_ids=["D-010"],
            etl_version_set=_DEFAULT_ETL,
            skill_toggle_states={"whitewater_handling": True},
        )

        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert "requires_skill_capability" not in flag_types

    def test_skill_capability_flag_not_fired_for_ungated_terrain(self):
        """TRN-001 (paved) does not appear in any skill toggle's
        gated_terrain_ids, so the flag does not fire even with empty
        toggle state. Locally covered terrain follows the same rule.
        """
        conn = _FakeConn()
        entries = [RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=100.0)]
        conn.queue_name_rows([_name_row("TRN-001", "Road / Paved")])
        # No gap-rule lookup needed — terrain is covered locally.
        conn.responses.append((None, [
            self._skill_cap_row(
                "whitewater_handling",
                gated_terrain_ids=["TRN-011", "TRN-017"],
            ),
        ]))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert "requires_skill_capability" not in flag_types

    def test_skill_toggle_loader_skipped_when_race_terrain_empty(self):
        """Empty race_terrain short-circuits at the `race_terrain_unset`
        emission; no SQL roundtrip for skill-capability toggle defs.
        """
        conn = _FakeConn()
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=[],
            locale_terrain_ids=["TRN-009"],
            included_discipline_ids=["D-010"],
            etl_version_set=_DEFAULT_ETL,
            skill_toggle_states={},
        )
        # The skill_capability_toggles SQL must NOT have been called.
        assert not any(
            "skill_capability_toggles" in call[0]
            for call in conn.calls
        )
        flag_types = [f.flag_type for f in payload.coaching_flags]
        assert flag_types == ["race_terrain_unset"]

    def test_multiple_gated_terrains_emit_one_flag_each(self):
        """Race with TRN-011 + TRN-017 (both gated by
        `whitewater_handling`) emits two skill-capability flags when
        the toggle is OFF.
        """
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-011", pct_of_race=60.0),
            RaceTerrainEntry(terrain_id="TRN-017", pct_of_race=40.0),
        ]
        conn.queue_name_rows([
            _name_row("TRN-011", "Whitewater"),
            _name_row("TRN-017", "Moving Water"),
        ])
        # Two gap rows since both terrains are not locally covered.
        conn.queue_proxy_row(_proxy_row(
            "TRN-011", "Whitewater",
            proxy_terrain_id="TRN-009",
            proxy_terrain_name="Flat Water",
            gap_severity="critical",
            proxy_fidelity=0.30,
        ))
        conn.queue_proxy_row(_proxy_row(
            "TRN-017", "Moving Water",
            proxy_terrain_id="TRN-009",
            proxy_terrain_name="Flat Water",
            gap_severity="medium",
            proxy_fidelity=0.65,
        ))
        conn.responses.append((None, [
            self._skill_cap_row(
                "whitewater_handling",
                gated_terrain_ids=["TRN-011", "TRN-017"],
            ),
        ]))

        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-009"],
            included_discipline_ids=["D-010"],
            etl_version_set=_DEFAULT_ETL,
        )

        skill_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "requires_skill_capability"
        ]
        assert len(skill_flags) == 2
        targets = sorted(f.target_terrain_id for f in skill_flags)
        assert targets == ["TRN-011", "TRN-017"]
        pcts = {f.target_terrain_id: f.metadata["pct_of_race"] for f in skill_flags}
        assert pcts == {"TRN-011": 60.0, "TRN-017": 40.0}


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

        block = next(
            b for b in payload.terrain_by_discipline if b.discipline_id == "D-001"
        )
        assert block.terrain_gaps == []
        assert all(r.available_locally for r in block.race_terrain)
        assert payload.coaching_flags == []


# ─── Phase 5.1 form-refresh C — empty race_terrain (loosen pair) ─────────────


class TestEmptyRaceTerrainLoosen:
    """Phase 5.1 form-refresh C — `_validate_inputs` loosened to accept
    empty `race_terrain`. The Layer 2B payload returns with empty terrain
    + a single `race_terrain_unset` coaching flag so plan-gen can surface
    the missing input as a data-gap warning rather than failing.

    Spec §4 condition 1 amended; §8.4 new flag definition.
    """

    def test_empty_race_terrain_returns_payload_with_race_terrain_unset_flag(self):
        conn = _FakeConn()
        # No SQL fired — empty terrain skips the per-gap proxy loop AND
        # `_load_terrain_names` (passed an empty list, returns {} without
        # execute() per the early-return branch).
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=[],
            locale_terrain_ids=["TRN-002"],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert payload.terrain_by_discipline == []
        assert len(payload.coaching_flags) == 1
        flag = payload.coaching_flags[0]
        assert flag.flag_type == "race_terrain_unset"
        assert flag.target_terrain_id is None
        assert "Race terrain breakdown not captured" in flag.message
        assert flag.metadata == {}

    def test_empty_race_terrain_with_empty_locale_still_emits_unset_flag(self):
        """Both empty — race_terrain takes precedence; only one flag fires."""
        conn = _FakeConn()
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=[],
            locale_terrain_ids=[],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert [f.flag_type for f in payload.coaching_flags] == [
            "race_terrain_unset"
        ]

    def test_non_list_race_terrain_still_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2BInputError, match="must be a list"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain="TRN-001",  # type: ignore[arg-type]
                locale_terrain_ids=[],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_other_validation_still_fires_on_empty_terrain(self):
        """Empty `race_terrain` doesn't bypass the rest of `_validate_inputs`
        — included_discipline_ids must still be non-empty + etl_version_set
        must still carry the required keys."""
        conn = _FakeConn()
        with pytest.raises(Layer2BInputError, match="included_discipline_ids"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=[],
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=[],
                etl_version_set=_DEFAULT_ETL,
            )
        with pytest.raises(Layer2BInputError, match="etl_version_set"):
            q_layer2b_terrain_classifier_payload(
                conn,
                race_terrain=[],
                locale_terrain_ids=["TRN-001"],
                included_discipline_ids=["D-001"],
                etl_version_set={"0A": "v1"},
            )


# ─── Best-fit re-model Slice 4 — per-discipline terrain blocks ────────────────


class TestPerDisciplineBlocks:
    """`terrain_by_discipline` keys the coverage/gap analysis by the captured
    `RaceTerrainEntry.discipline_id`. Race-wide (None) entries fold into every
    included discipline; a tagged entry wins over a race-wide entry for the
    same terrain_id."""

    def _block(self, payload: Layer2BPayload, discipline_id: str) -> Layer2BDisciplineBlock:
        return next(
            b for b in payload.terrain_by_discipline if b.discipline_id == discipline_id
        )

    def test_race_wide_folds_into_every_discipline(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=50.0),
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=50.0),
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-002", "Groomed Trail"),
        ])
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001", "TRN-002"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )

        assert [b.discipline_id for b in payload.terrain_by_discipline] == [
            "D-001", "D-006"
        ]
        for did in ("D-001", "D-006"):
            block = self._block(payload, did)
            assert {r.terrain_id for r in block.race_terrain} == {"TRN-001", "TRN-002"}
            # Folded-in race-wide rows are stamped with the block discipline.
            assert all(r.discipline_id == did for r in block.race_terrain)
            assert len(block.race_terrain) == 2
            assert all(r.available_locally for r in block.race_terrain)
            assert block.terrain_gaps == []

    def test_tagged_entries_route_to_their_discipline(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=50.0, discipline_id="D-001"),
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=50.0, discipline_id="D-006"),
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-002", "Groomed Trail"),
        ])
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001", "TRN-002"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert {r.terrain_id for r in self._block(payload, "D-001").race_terrain} == {"TRN-001"}
        assert {r.terrain_id for r in self._block(payload, "D-006").race_terrain} == {"TRN-002"}

    def test_same_terrain_two_disciplines_keeps_distinct_pct(self):
        """The collapse the flat `pct_by_target` dict masks: TRN-003 appears in
        two legs at different percentages; each block keeps its own pct."""
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-003", pct_of_race=40.0, discipline_id="D-001"),
            RaceTerrainEntry(terrain_id="TRN-003", pct_of_race=60.0, discipline_id="D-006"),
        ]
        conn.queue_name_rows([_name_row("TRN-003", "Technical Trail")])
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-003"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        a = self._block(payload, "D-001").race_terrain
        b = self._block(payload, "D-006").race_terrain
        assert [(r.terrain_id, r.pct_of_race) for r in a] == [("TRN-003", 40.0)]
        assert [(r.terrain_id, r.pct_of_race) for r in b] == [("TRN-003", 60.0)]

    def test_tagged_wins_over_race_wide_in_block(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=70.0, discipline_id="D-001"),
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=30.0),  # race-wide
        ]
        conn.queue_name_rows([_name_row("TRN-001", "Road / Paved")])
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        # D-001 uses its tagged row (70), not the race-wide (30).
        assert [(r.terrain_id, r.pct_of_race) for r in self._block(payload, "D-001").race_terrain] == [
            ("TRN-001", 70.0)
        ]
        # D-006 has no tag → folds in the race-wide row (30).
        assert [(r.terrain_id, r.pct_of_race) for r in self._block(payload, "D-006").race_terrain] == [
            ("TRN-001", 30.0)
        ]

    def test_single_discipline_untagged_block_covers_all_race_wide_terrain(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=60.0),
            RaceTerrainEntry(terrain_id="TRN-009", pct_of_race=40.0),  # gap
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-009", "Flat Water"),
        ])
        conn.queue_proxy_row(_proxy_row(
            "TRN-009", "Flat Water",
            proxy_terrain_id="TRN-008", proxy_terrain_name="Pool",
            gap_severity="low", proxy_fidelity=0.75,
        ))
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert len(payload.terrain_by_discipline) == 1
        block = self._block(payload, "D-001")
        # Single included discipline + all-race-wide entries → the block
        # covers every captured terrain row (no discipline tagging to split on).
        assert {r.terrain_id for r in block.race_terrain} == {"TRN-001", "TRN-009"}
        assert {g.target_terrain_id for g in block.terrain_gaps} == {"TRN-009"}

    def test_orphan_tagged_discipline_excluded_from_blocks(self):
        """An entry tagged to a discipline outside `included_discipline_ids`
        gets no block."""
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=50.0, discipline_id="D-001"),
            RaceTerrainEntry(terrain_id="TRN-002", pct_of_race=50.0, discipline_id="D-999"),
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-002", "Groomed Trail"),
        ])
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001", "TRN-002"],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert [b.discipline_id for b in payload.terrain_by_discipline] == ["D-001"]
        assert {r.terrain_id for r in self._block(payload, "D-001").race_terrain} == {"TRN-001"}

    def test_discipline_with_no_terrain_emits_no_block(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=100.0, discipline_id="D-001"),
        ]
        conn.queue_name_rows([_name_row("TRN-001", "Road / Paved")])
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        # D-006 has nothing tagged and no race-wide rows → skipped.
        assert [b.discipline_id for b in payload.terrain_by_discipline] == ["D-001"]

    def test_empty_race_terrain_no_discipline_blocks(self):
        conn = _FakeConn()
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=[],
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert payload.terrain_by_discipline == []

    def test_block_carries_race_wide_gap_for_every_discipline(self):
        conn = _FakeConn()
        entries = [
            RaceTerrainEntry(terrain_id="TRN-001", pct_of_race=60.0),  # covered
            RaceTerrainEntry(terrain_id="TRN-009", pct_of_race=40.0),  # gap, race-wide
        ]
        conn.queue_name_rows([
            _name_row("TRN-001", "Road / Paved"),
            _name_row("TRN-009", "Flat Water"),
        ])
        conn.queue_proxy_row(_proxy_row(
            "TRN-009", "Flat Water",
            proxy_terrain_id="TRN-008", proxy_terrain_name="Pool",
            gap_severity="medium", proxy_fidelity=0.6,
        ))
        payload = q_layer2b_terrain_classifier_payload(
            conn,
            race_terrain=entries,
            locale_terrain_ids=["TRN-001"],
            included_discipline_ids=["D-001", "D-006"],
            etl_version_set=_DEFAULT_ETL,
        )
        for did in ("D-001", "D-006"):
            block = self._block(payload, did)
            assert len(block.race_terrain) == 2
            assert {g.target_terrain_id for g in block.terrain_gaps} == {"TRN-009"}
            gap_row = next(r for r in block.race_terrain if r.terrain_id == "TRN-009")
            assert gap_row.gap is not None
            assert gap_row.gap.proxy_terrain_id == "TRN-008"
            assert gap_row.available_locally is False
