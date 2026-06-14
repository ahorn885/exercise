"""Tests for the training-substitution resolver (BestFitModality_Spec_v4 §5 /
re-model Slice 5, 2026-05-25).

Covers the §13 scenarios that the deterministic node owns: terrain emphasis
ranking, untrainable-terrain routing, low-fidelity flagging, and the craft
candidate set handed to the LLM. Craft *selection* is LLM-side (R1 / gate Q2),
so there's no deterministic craft-substitution assertion — only that the
candidate set is surfaced verbatim.

`§13.6` skill-gated terrain and `§13.7` pure-craft collapse are out of scope
for this build (no skill→terrain map; the D-010/b collapse is the deferred R6
id-change session).
"""

from __future__ import annotations

import pytest

from layer4 import InMemoryCacheBackend  # noqa: F401  (forces layer4 init first)
from layer4.context import (
    Layer2BDisciplineBlock,
    Layer2BSummaryBlock,
    RaceTerrainOutput,
    TerrainGap,
)
from layer2_modality import Layer2ModalityInputError, resolve_training_substitution

_ETL = {"0A": "0A-v1", "0B": "0B-v1", "0C": "0C-v2.0-r2"}


def _summary() -> Layer2BSummaryBlock:
    # Field values are irrelevant to the substitution resolver (it reads
    # race_terrain rows, not the block summary); kept schema-valid.
    return Layer2BSummaryBlock(
        total_race_terrain_count=0,
        covered_count=0,
        gap_count=0,
        bridgeable_count=0,
        unbridgeable_count=0,
        min_adaptation_weeks_needed=0,
        worst_fidelity=1.0,
        pct_of_race_uncovered=0.0,
        any_unbridgeable=False,
        any_undefined=False,
    )


def _gap(
    target_id: str,
    *,
    proxy: str | None,
    fidelity: float | None,
    severity: str,
    proxy_name: str | None = None,
    methods: list[str] | None = None,
    uncoverable: list[str] | None = None,
    weeks: tuple[int, int] | None = (2, 4),
) -> TerrainGap:
    return TerrainGap(
        target_terrain_id=target_id,
        target_terrain_name=target_id.replace("TRN-", "").title(),
        proxy_terrain_id=proxy,
        proxy_terrain_name=proxy_name if proxy else None,
        gap_severity=severity,
        adaptation_weeks_low=weeks[0] if weeks else None,
        adaptation_weeks_high=weeks[1] if weeks else None,
        proxy_fidelity=fidelity,
        proxy_methods=methods or [],
        uncoverable_stimulus=uncoverable or [],
        prescription_note="",
    )


def _terrain(
    terrain_id: str,
    pct: float,
    *,
    name: str | None = None,
    available: bool = False,
    gap: TerrainGap | None = None,
    discipline_id: str = "D-009",
) -> RaceTerrainOutput:
    return RaceTerrainOutput(
        terrain_id=terrain_id,
        terrain_name=name or terrain_id,
        pct_of_race=pct,
        available_locally=available,
        gap=gap,
        discipline_id=discipline_id,
    )


def _block(discipline_id: str, race_terrain: list[RaceTerrainOutput]) -> Layer2BDisciplineBlock:
    return Layer2BDisciplineBlock(
        discipline_id=discipline_id,
        race_terrain=race_terrain,
        terrain_gaps=[],
        summary=_summary(),
    )


def _packraft_block() -> Layer2BDisciplineBlock:
    """§13.1 — Packrafting leg: 80% river (local), 10% lake (low-fid proxy),
    10% whitewater (unbridgeable)."""
    return _block(
        "D-009",
        [
            _terrain("TRN-river", 80.0, name="River", available=True),
            _terrain(
                "TRN-lake",
                10.0,
                name="Lake",
                gap=_gap("TRN-lake", proxy="TRN-pool", proxy_name="Pool", fidelity=0.40, severity="high"),
            ),
            _terrain(
                "TRN-ww",
                10.0,
                name="Whitewater",
                gap=_gap("TRN-ww", proxy=None, fidelity=None, severity="unbridgeable"),
            ),
        ],
    )


class TestPackraftScenario:
    def test_race_craft_is_pure_craft_label(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak", "canoe"],
            etl_version_set=_ETL,
        )
        rec = p.recommendations[0]
        assert rec.discipline_id == "D-009"
        assert rec.race_craft == "Packrafting"

    def test_candidate_crafts_surfaced_verbatim_sorted(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak", "canoe"],
            etl_version_set=_ETL,
        )
        assert p.recommendations[0].candidate_training_crafts == ["canoe", "kayak"]

    def test_river_ranks_top_by_pct_times_fidelity(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak"],
            etl_version_set=_ETL,
        )
        emph = p.recommendations[0].terrain_emphasis
        assert [e.race_terrain_id for e in emph] == ["TRN-river", "TRN-lake"]
        assert emph[0].fidelity == 1.0 and emph[0].emphasis_score == 80.0
        assert emph[1].emphasis_score == pytest.approx(10.0 * 0.40)

    def test_whitewater_is_untrainable_with_pct(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak"],
            etl_version_set=_ETL,
        )
        untr = p.recommendations[0].untrainable_terrain
        assert len(untr) == 1
        assert untr[0].race_terrain_id == "TRN-ww"
        assert untr[0].pct == 10.0
        assert untr[0].reason == "unbridgeable"

    def test_flags_cover_low_fidelity_and_untrainable(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak"],
            etl_version_set=_ETL,
        )
        by_type = {(f.flag_type, f.race_terrain_id) for f in p.coaching_flags}
        assert ("terrain_low_fidelity", "TRN-lake") in by_type
        assert ("terrain_untrainable", "TRN-ww") in by_type


class TestCraftCandidates:
    def test_owns_race_craft_appears_in_candidates(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["packraft", "kayak"],
            etl_version_set=_ETL,
        )
        assert "packraft" in p.recommendations[0].candidate_training_crafts

    def test_no_crafts_emits_craft_unavailable_once(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=[],
            etl_version_set=_ETL,
        )
        unavail = [f for f in p.coaching_flags if f.flag_type == "craft_unavailable"]
        assert len(unavail) == 1
        assert p.recommendations[0].candidate_training_crafts == []
        assert unavail[0].metadata["included_discipline_ids"] == ["D-009"]

    def test_owned_crafts_deduped(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak", "kayak", "canoe"],
            etl_version_set=_ETL,
        )
        assert p.recommendations[0].candidate_training_crafts == ["canoe", "kayak"]


class TestTerrainEmphasis:
    def test_available_locally_is_full_fidelity(self):
        block = _block("D-001", [_terrain("TRN-trail", 100.0, available=True, discipline_id="D-001")])
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=[], etl_version_set=_ETL
        )
        e = p.recommendations[0].terrain_emphasis[0]
        assert e.fidelity == 1.0
        assert e.gap_severity == "none"
        assert e.proxy_terrain_id == "TRN-trail"

    def test_proxy_at_floor_is_trainable_below_floor_is_not(self):
        block = _block(
            "D-008",
            [
                _terrain("TRN-at", 50.0, gap=_gap("TRN-at", proxy="TRN-x", fidelity=0.25, severity="critical"), discipline_id="D-008"),
                _terrain("TRN-below", 50.0, gap=_gap("TRN-below", proxy="TRN-y", fidelity=0.20, severity="critical"), discipline_id="D-008"),
            ],
        )
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=[], etl_version_set=_ETL
        )
        rec = p.recommendations[0]
        assert [e.race_terrain_id for e in rec.terrain_emphasis] == ["TRN-at"]
        assert [g.race_terrain_id for g in rec.untrainable_terrain] == ["TRN-below"]

    def test_low_fidelity_flag_carries_adaptation_weeks(self):
        block = _block(
            "D-008",
            [_terrain("TRN-x", 100.0, gap=_gap("TRN-x", proxy="TRN-y", fidelity=0.45, severity="high", weeks=(3, 6)), discipline_id="D-008")],
        )
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=[], etl_version_set=_ETL
        )
        flag = next(f for f in p.coaching_flags if f.flag_type == "terrain_low_fidelity")
        assert flag.metadata["adaptation_weeks_low"] == 3
        assert flag.metadata["adaptation_weeks_high"] == 6

    def test_good_proxy_does_not_flag_low_fidelity(self):
        block = _block(
            "D-008",
            [_terrain("TRN-x", 100.0, gap=_gap("TRN-x", proxy="TRN-y", fidelity=0.85, severity="low"), discipline_id="D-008")],
        )
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=[], etl_version_set=_ETL
        )
        assert not any(f.flag_type == "terrain_low_fidelity" for f in p.coaching_flags)
        assert p.recommendations[0].terrain_emphasis[0].fidelity == 0.85

    def test_missing_gap_data_is_untrainable(self):
        # available_locally False but no gap record → data hole → untrainable.
        block = _block("D-008", [_terrain("TRN-x", 100.0, available=False, gap=None, discipline_id="D-008")])
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=[], etl_version_set=_ETL
        )
        assert p.recommendations[0].terrain_emphasis == []
        assert p.recommendations[0].untrainable_terrain[0].reason == "no proxy data"


class TestEdgeCases:
    def test_empty_terrain_block_is_craft_only(self):
        block = _block("D-011", [])
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=["canoe"], etl_version_set=_ETL
        )
        rec = p.recommendations[0]
        assert rec.terrain_emphasis == []
        assert rec.untrainable_terrain == []
        assert rec.candidate_training_crafts == ["canoe"]
        assert p.coaching_flags == []

    def test_all_terrain_untrainable(self):
        block = _block(
            "D-009",
            [
                _terrain("TRN-a", 60.0, gap=_gap("TRN-a", proxy=None, fidelity=None, severity="unbridgeable")),
                _terrain("TRN-b", 40.0, gap=_gap("TRN-b", proxy=None, fidelity=None, severity="unbridgeable")),
            ],
        )
        p = resolve_training_substitution(
            terrain_by_discipline=[block], athlete_crafts=["kayak"], etl_version_set=_ETL
        )
        rec = p.recommendations[0]
        assert rec.terrain_emphasis == []
        assert {g.race_terrain_id for g in rec.untrainable_terrain} == {"TRN-a", "TRN-b"}

    def test_empty_blocks_no_recommendations(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[], athlete_crafts=["kayak"], etl_version_set=_ETL
        )
        assert p.recommendations == []
        assert p.coaching_flags == []

    def test_multiple_disciplines_one_recommendation_each(self):
        p = resolve_training_substitution(
            terrain_by_discipline=[
                _block("D-001", [_terrain("TRN-trail", 100.0, available=True, discipline_id="D-001")]),
                _packraft_block(),
            ],
            athlete_crafts=["kayak"],
            etl_version_set=_ETL,
        )
        assert [r.discipline_id for r in p.recommendations] == ["D-001", "D-009"]

    def test_deterministic(self):
        args = dict(
            terrain_by_discipline=[_packraft_block()],
            athlete_crafts=["kayak", "canoe"],
            etl_version_set=_ETL,
        )
        assert resolve_training_substitution(**args).model_dump() == (
            resolve_training_substitution(**args).model_dump()
        )

    def test_discipline_names_fallback_used_for_uncurated_id(self):
        block = _block("D-999", [_terrain("TRN-x", 100.0, available=True, discipline_id="D-999")])
        p = resolve_training_substitution(
            terrain_by_discipline=[block],
            athlete_crafts=[],
            etl_version_set=_ETL,
            discipline_names={"D-999": "Bridge Fallback Name"},
        )
        assert p.recommendations[0].race_craft == "Bridge Fallback Name"

    def test_empty_etl_version_set_raises(self):
        with pytest.raises(Layer2ModalityInputError):
            resolve_training_substitution(
                terrain_by_discipline=[_packraft_block()],
                athlete_crafts=["kayak"],
                etl_version_set={},
            )


# ---------------------------------------------------------------------------
# X1b.3b — craft → modality-group candidate narrowing (Modality_Group_Spec §6)
# ---------------------------------------------------------------------------

# Membership + alias maps mirroring the live v14 seed (bike + paddle subset).
_DISC_GROUPS = {
    "D-006": ["bike_pavement"],
    "D-007": ["bike_pavement"],
    "D-008": ["bike_offroad"],
    "D-030": ["bike_pavement", "bike_offroad"],
    "D-031": ["bike_offroad"],
    "D-009": ["paddle_flatwater", "paddle_whitewater"],
    "D-010": ["paddle_flatwater", "paddle_whitewater"],
    "D-011": ["paddle_flatwater"],
    "D-001": ["foot"],
}
_CRAFT_ALIASES = {
    "kayak": ["D-010"],
    "canoe": ["D-011"],
    "packraft": ["D-009"],
    "road_bike": ["D-006"],
    "gravel_bike": ["D-006", "D-030", "D-031"],
    "mountain_bike": ["D-008", "D-031"],
}


def _flat(discipline_id: str) -> Layer2BDisciplineBlock:
    # One locally-available terrain → no terrain flags; isolates craft logic.
    return _block(
        discipline_id,
        [_terrain("TRN-x", 100.0, name="X", available=True, discipline_id=discipline_id)],
    )


def _resolve(discipline_id, crafts):
    return resolve_training_substitution(
        terrain_by_discipline=[_flat(discipline_id)],
        athlete_crafts=crafts,
        etl_version_set=_ETL,
        discipline_modality_groups=_DISC_GROUPS,
        craft_discipline_aliases=_CRAFT_ALIASES,
    )


class TestX1b3bCraftNarrowing:
    def test_mtb_block_narrows_to_offroad_crafts(self):
        # Race MTB (bike_offroad): road bike drops, MTB stays → craft_substitution.
        p = _resolve("D-008", ["road_bike", "mountain_bike"])
        assert p.recommendations[0].candidate_training_crafts == ["mountain_bike"]
        flags = [f.flag_type for f in p.coaching_flags]
        assert "craft_substitution" in flags

    def test_gravel_bike_qualifies_for_both_road_and_offroad(self):
        # Gravel bike pools road + gravel + XC → matches pavement AND off-road.
        for disc in ("D-006", "D-008"):
            p = _resolve(disc, ["gravel_bike"])
            assert p.recommendations[0].candidate_training_crafts == ["gravel_bike"]
        # sole matching craft → no narrowing flag
        assert not [f for f in _resolve("D-006", ["gravel_bike"]).coaching_flags
                    if f.flag_type in ("craft_substitution", "craft_unavailable")]

    def test_paddle_only_athlete_unavailable_for_bike_block(self):
        # Owns only a kayak; race needs MTB → empty + per-block craft_unavailable.
        p = _resolve("D-008", ["kayak"])
        assert p.recommendations[0].candidate_training_crafts == []
        assert any(f.flag_type == "craft_unavailable" and f.discipline_id == "D-008"
                   for f in p.coaching_flags)

    def test_foot_discipline_not_filtered_or_flagged(self):
        # A running block isn't craft-based — crafts pass through, no craft flag.
        p = _resolve("D-001", ["road_bike", "kayak"])
        assert p.recommendations[0].candidate_training_crafts == ["kayak", "road_bike"]
        assert not [f for f in p.coaching_flags
                    if f.flag_type in ("craft_substitution", "craft_unavailable")]

    def test_backcompat_no_maps_surfaces_all_crafts(self):
        # No maps → pre-X1b.3b behavior: every craft surfaced, no new flags.
        p = resolve_training_substitution(
            terrain_by_discipline=[_flat("D-008")],
            athlete_crafts=["road_bike", "kayak"],
            etl_version_set=_ETL,
        )
        assert p.recommendations[0].candidate_training_crafts == ["kayak", "road_bike"]
        assert not [f for f in p.coaching_flags
                    if f.flag_type in ("craft_substitution", "craft_unavailable")]
