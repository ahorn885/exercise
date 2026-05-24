"""Tests for `layer2_modality.resolver.resolve_best_fit_modality`.

Coverage matches `BestFitModality_Spec_v1.md` §4 input validation,
§5 algorithm, §8 coaching flag rules, §10 edge cases, and §13
integration scenarios (6 scenarios + the §13.6 static lint test).

The resolver issues exactly ONE SELECT per call
(`_load_discipline_info` against `layer0.sport_discipline_bridge`)
so the `_FakeConn` substrate here is simpler than 2C's: one queue,
no skill-capability sidetrack.
"""

from __future__ import annotations

from typing import Any

import pytest

# Pre-load layer4 to break the layer4.orchestrator → layer2_modality →
# layer4.context circular import that otherwise blocks single-module
# collection. Mirrors `tests/test_layer2a.py:26` + `tests/test_layer2b.py:26`
# precedent.
from layer4 import InMemoryCacheBackend  # noqa: F401

from layer2_modality import (
    ClusterLocaleInput,
    Layer2ModalityInputError,
    resolve_best_fit_modality,
)
from layer2_modality.resolver import _MODALITY_OPTIONS_PER_DISCIPLINE
from layer4.context import (
    Layer2ModalityPayload,
    ModalityCoachingFlag,
    ModalityOption,
    ModalityRecommendation,
)


# ─── Fakes ───────────────────────────────────────────────────────────────────


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
    """Single-queue fake: the resolver issues exactly one SELECT
    against `sport_discipline_bridge` per call.

    Tests queue the discipline-info rows via `queue(*rows)`.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.batches: list[list[dict[str, Any]]] = []

    def queue(self, *rows: dict[str, Any]) -> None:
        self.batches.append(list(rows))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.batches.pop(0) if self.batches else []
        return _FakeCursor(rows)

    def commit(self):  # interface compatibility
        pass


_DEFAULT_ETL = {"0A": "v19", "0B": "v15", "0C": "v7"}


def _sdb_row(discipline_id: str, discipline_name: str) -> dict[str, Any]:
    return {"discipline_id": discipline_id, "discipline_name": discipline_name}


def _locale(
    locale_id: str = "home",
    locale_name: str | None = "Home (Nerstrand MN)",
    *,
    terrain: list[str] | None = None,
    pool: list[str] | None = None,
) -> ClusterLocaleInput:
    return ClusterLocaleInput(
        locale_id=locale_id,
        locale_name=locale_name,
        locale_terrain_ids=list(terrain or []),
        effective_pool=list(pool or []),
    )


# ─── §4 input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_cluster_locale_inputs_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2ModalityInputError, match="non-empty"):
            resolve_best_fit_modality(
                conn,
                cluster_locale_inputs=[],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_duplicate_locale_ids_raise(self):
        conn = _FakeConn()
        with pytest.raises(Layer2ModalityInputError, match="duplicate"):
            resolve_best_fit_modality(
                conn,
                cluster_locale_inputs=[_locale("home"), _locale("home")],
                included_discipline_ids=["D-001"],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_empty_included_discipline_ids_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2ModalityInputError, match="included_discipline_ids"):
            resolve_best_fit_modality(
                conn,
                cluster_locale_inputs=[_locale()],
                included_discipline_ids=[],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_empty_discipline_id_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2ModalityInputError, match="non-empty string"):
            resolve_best_fit_modality(
                conn,
                cluster_locale_inputs=[_locale()],
                included_discipline_ids=[""],
                etl_version_set=_DEFAULT_ETL,
            )

    def test_skill_toggle_states_non_bool_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2ModalityInputError, match="must be bool"):
            resolve_best_fit_modality(
                conn,
                cluster_locale_inputs=[_locale()],
                included_discipline_ids=["D-001"],
                skill_toggle_states={"climbing_roped": "yes"},  # type: ignore[dict-item]
                etl_version_set=_DEFAULT_ETL,
            )

    def test_etl_version_set_missing_key_raises(self):
        conn = _FakeConn()
        with pytest.raises(Layer2ModalityInputError, match="0C"):
            resolve_best_fit_modality(
                conn,
                cluster_locale_inputs=[_locale()],
                included_discipline_ids=["D-001"],
                etl_version_set={"0A": "v1", "0B": "v1"},
            )


# ─── §13.1 Andy at home — full AR cluster, default-OFF skill toggles ─────────


class TestScenario13_1_AndyAtHome:
    """Per spec §13.1: home locale with running + cycling terrain +
    skill toggles default-OFF.

    Locale: TRN-001 (paved) + TRN-002 (singletrack) + TRN-016 (indoor).
    Pool: Treadmill + Road bike + Bike trainer (no climbing gear, no
    bouldering pad).
    Disciplines: D-001 + D-006 + D-010 (climbing).
    """

    def _call(self, skill_states: dict[str, bool] | None = None):
        conn = _FakeConn()
        conn.queue(
            _sdb_row("D-001", "Trail Running"),
            _sdb_row("D-006", "Outdoor Road Cycling"),
            _sdb_row("D-010", "Outdoor Rock Climbing"),
        )
        return resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    "home",
                    "Home (Nerstrand MN)",
                    terrain=["TRN-001", "TRN-002", "TRN-016"],
                    pool=["Treadmill", "Road bike", "Bike trainer"],
                )
            ],
            included_discipline_ids=["D-001", "D-006", "D-010"],
            skill_toggle_states=skill_states or {},
            etl_version_set=_DEFAULT_ETL,
        )

    def test_d001_trail_run_is_top_pick(self):
        payload = self._call()
        d001 = [r for r in payload.recommendations if r.discipline_id == "D-001"]
        assert len(d001) == 1
        assert d001[0].top_pick_modality_id == "outdoor_trail_run"
        # Three options surface (trail + road + treadmill), ranked by score.
        modality_ids = [opt.modality_id for opt in d001[0].menu]
        assert modality_ids == ["outdoor_trail_run", "outdoor_road_run", "treadmill_run"]

    def test_d006_road_ride_is_top_pick(self):
        payload = self._call()
        d006 = [r for r in payload.recommendations if r.discipline_id == "D-006"]
        assert len(d006) == 1
        assert d006[0].top_pick_modality_id == "outdoor_road_ride"
        modality_ids = [opt.modality_id for opt in d006[0].menu]
        # gravel needs TRN-020 + Gravel bike — neither present; outdoor_road_ride
        # + indoor_trainer surface.
        assert modality_ids == ["outdoor_road_ride", "indoor_trainer"]

    def test_d010_climbing_empty_menu_fires_no_modality_recommendation(self):
        payload = self._call()
        d010 = [r for r in payload.recommendations if r.discipline_id == "D-010"]
        assert len(d010) == 1
        assert d010[0].menu == []
        assert d010[0].top_pick_modality_id is None
        # Cluster-wide flag fires for D-010 (no climbing terrain at any locale).
        no_modality_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "no_modality_recommendation" and f.discipline_id == "D-010"
        ]
        assert len(no_modality_flags) == 1
        assert no_modality_flags[0].locale_id is None  # cluster-wide

    def test_no_skill_block_flag_when_no_eligible_terrain(self):
        # climbing_roped=False AND no TRN-013/TRN-014 in locale — the
        # blocker flag should NOT fire (no eligible option to block).
        payload = self._call()
        block_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "skill_capability_blocks_specific_modality"
        ]
        assert block_flags == []


# ─── §13.2 Andy enables climbing_roped + adds a climbing-gym locale ──────────


class TestScenario13_2_ClimbingGymPlusToggle:
    def _call(self):
        conn = _FakeConn()
        conn.queue(
            _sdb_row("D-001", "Trail Running"),
            _sdb_row("D-006", "Outdoor Road Cycling"),
            _sdb_row("D-010", "Outdoor Rock Climbing"),
        )
        return resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    "home",
                    "Home (Nerstrand MN)",
                    terrain=["TRN-001", "TRN-002", "TRN-016"],
                    pool=["Treadmill", "Road bike", "Bike trainer"],
                ),
                _locale(
                    "climbing_gym",
                    "Climbing Gym",
                    terrain=["TRN-014", "TRN-016"],
                    pool=["Climbing gym membership", "Hangboard"],
                ),
            ],
            included_discipline_ids=["D-001", "D-006", "D-010"],
            skill_toggle_states={"climbing_roped": True},
            etl_version_set=_DEFAULT_ETL,
        )

    def test_d010_at_climbing_gym_top_pick_is_lead(self):
        payload = self._call()
        d010_gym = [
            r for r in payload.recommendations
            if r.discipline_id == "D-010" and r.locale_id == "climbing_gym"
        ]
        assert len(d010_gym) == 1
        assert d010_gym[0].top_pick_modality_id == "gym_lead_climb"
        modality_ids = [opt.modality_id for opt in d010_gym[0].menu]
        assert "gym_lead_climb" in modality_ids
        assert "gym_top_rope" in modality_ids
        assert "gym_boulder" in modality_ids
        assert "gym_hangboard" in modality_ids

    def test_d010_no_cluster_wide_flag_when_gym_satisfies(self):
        payload = self._call()
        no_modality_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "no_modality_recommendation" and f.discipline_id == "D-010"
        ]
        assert no_modality_flags == []  # climbing_gym locale satisfies

    def test_no_skill_block_flag_when_toggle_on(self):
        payload = self._call()
        block_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "skill_capability_blocks_specific_modality"
        ]
        assert block_flags == []  # toggle ON → no blocked-specific flag


# ─── §13.3 Andy disables climbing_roped (after 13.2 setup) ───────────────────


class TestScenario13_3_DisableRopedToggle:
    def _call(self):
        conn = _FakeConn()
        conn.queue(
            _sdb_row("D-001", "Trail Running"),
            _sdb_row("D-010", "Outdoor Rock Climbing"),
        )
        return resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    "climbing_gym",
                    "Climbing Gym",
                    terrain=["TRN-014", "TRN-016"],
                    pool=["Climbing gym membership", "Hangboard"],
                )
            ],
            included_discipline_ids=["D-001", "D-010"],
            skill_toggle_states={"climbing_roped": False},
            etl_version_set=_DEFAULT_ETL,
        )

    def test_d010_top_pick_falls_back_to_top_rope(self):
        payload = self._call()
        d010 = [r for r in payload.recommendations if r.discipline_id == "D-010"]
        assert len(d010) == 1
        # gym_lead_climb is gated by climbing_roped — falls out.
        # gym_top_rope is the surviving specific top-pick.
        assert d010[0].top_pick_modality_id == "gym_top_rope"
        modality_ids = [opt.modality_id for opt in d010[0].menu]
        assert "gym_lead_climb" not in modality_ids

    def test_skill_block_flag_fires_for_lead_climb(self):
        payload = self._call()
        block_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "skill_capability_blocks_specific_modality"
        ]
        # gym_lead_climb is the blocked specific modality.
        lead_block = [
            f for f in block_flags
            if f.metadata.get("blocked_modality_id") == "gym_lead_climb"
        ]
        assert len(lead_block) == 1
        assert lead_block[0].metadata["blocking_skill_toggle"] == "climbing_roped"
        assert lead_block[0].metadata["currently_resolves_to"] == "gym_top_rope"
        assert lead_block[0].locale_id == "climbing_gym"


# ─── §13.4 Empty cluster — degenerate ────────────────────────────────────────


class TestScenario13_4_EmptyCluster:
    def test_three_no_modality_flags_no_failure(self):
        conn = _FakeConn()
        conn.queue(
            _sdb_row("D-001", "Trail Running"),
            _sdb_row("D-006", "Outdoor Road Cycling"),
            _sdb_row("D-010", "Outdoor Rock Climbing"),
        )
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale("empty", "Empty", terrain=[], pool=[])
            ],
            included_discipline_ids=["D-001", "D-006", "D-010"],
            etl_version_set=_DEFAULT_ETL,
        )
        # Every recommendation has an empty menu.
        for rec in payload.recommendations:
            assert rec.menu == []
            assert rec.top_pick_modality_id is None
        # One no_modality_recommendation flag per discipline (3 total).
        no_modality_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "no_modality_recommendation"
        ]
        assert len(no_modality_flags) == 3
        assert {f.discipline_id for f in no_modality_flags} == {"D-001", "D-006", "D-010"}


# ─── §13.5 Hotel locale — indoor-only ────────────────────────────────────────


class TestScenario13_5_HotelIndoorOnly:
    def _call(self):
        conn = _FakeConn()
        conn.queue(
            _sdb_row("D-001", "Trail Running"),
            _sdb_row("D-006", "Outdoor Road Cycling"),
            _sdb_row("D-010", "Outdoor Rock Climbing"),
        )
        return resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    "hotel",
                    "Hotel",
                    terrain=["TRN-016"],
                    pool=["Treadmill", "Dumbbells", "Bench"],
                )
            ],
            included_discipline_ids=["D-001", "D-006", "D-010"],
            skill_toggle_states={"climbing_roped": True},
            etl_version_set=_DEFAULT_ETL,
        )

    def test_d001_top_pick_is_treadmill_run(self):
        payload = self._call()
        d001 = [r for r in payload.recommendations if r.discipline_id == "D-001"]
        assert d001[0].top_pick_modality_id == "treadmill_run"
        assert [opt.modality_id for opt in d001[0].menu] == ["treadmill_run"]

    def test_d001_fires_only_generic_modality_available(self):
        payload = self._call()
        generic_flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "only_generic_modality_available"
            and f.discipline_id == "D-001"
        ]
        assert len(generic_flags) == 1
        assert generic_flags[0].metadata["generic_options_available"] == ["treadmill_run"]
        assert "outdoor_trail_run" in generic_flags[0].metadata["specific_options_unavailable"]

    def test_d006_and_d010_fire_no_modality(self):
        payload = self._call()
        # D-006: no bike + no bike-trainer in pool → empty menu → no_modality
        # D-010: TRN-013/14 absent → empty menu → no_modality
        no_modality_disciplines = {
            f.discipline_id for f in payload.coaching_flags
            if f.flag_type == "no_modality_recommendation"
        }
        assert no_modality_disciplines == {"D-006", "D-010"}


# ─── §13.6 Static lint — every option references known vocab ─────────────────


# Known canonical surfaces — kept in sync with the active ETL state. The
# spec calls for round-trip against the live DB; this slice ships a
# static-data alignment check that doesn't require live DB. Equipment
# canonicalisation (BM-5) is deferred — this test currently covers
# terrain + skill-toggle only, matching the spec's BM-5 acknowledgement
# that equipment alignment lands with the canonicalisation slice.

_KNOWN_TRN_IDS = {f"TRN-{n:03d}" for n in range(1, 18)} | {"TRN-020"}  # WaterVocab + BucketC_g

_KNOWN_SKILL_TOGGLES = {
    "climbing_roped",
    "mountaineering",
    "swim_open_water",
    "via_ferrata",
    "whitewater_handling",
}

# BestFitModality_Spec_v2.md §I — canonical equipment names referenced
# by `_MODALITY_OPTIONS_PER_DISCIPLINE`. Mirror of canonical 0B
# `equipment_items.canonical_name` after the K2 + K3 ETL additions land.
# Lint test `test_every_required_equipment_is_canonical` fails CI when
# the resolver dict references a name not in this set; the matching ETL
# slice (`populate_equipment_items_K3_additions.sql`) keeps the canonical
# 0B vocab in sync with this set.
_KNOWN_EQUIPMENT = {
    # K2 file (pre-v2)
    "Climbing gear",
    "XC ski kit",
    "Touring ski kit",
    "SUP",
    "Mountaineering kit",
    "Climbing Wall",
    "TT Bike",
    "Gravel bike",
    "Cable machine",
    "Plyo box",
    "Weighted vest",
    "Resistance band",
    "Bike trainer",
    "Pull buoy",
    "Rice bucket",
    "Pinch Block",
    "Wrist Roller",
    "Trekking Poles",
    "Packraft",
    # K3 file (this slice — Spec v2 §I)
    "Treadmill",
    "Road bike",
    "Rope",
    "Quickdraws",
    "Harness",
    "Crash pad",
    "Hangboard",
    "Climbing gym membership",
    "Kayak",
    "Canoe",
}


class TestStaticLint:
    def test_every_modality_option_def_has_required_fields(self):
        for d_id, opt_defs in _MODALITY_OPTIONS_PER_DISCIPLINE.items():
            assert opt_defs, f"discipline {d_id} has no modality options"
            for opt in opt_defs:
                assert opt.modality_id, f"{d_id}: empty modality_id"
                assert opt.modality_name, f"{d_id}/{opt.modality_id}: empty modality_name"
                assert 0 <= opt.base_preference_score <= 100, (
                    f"{d_id}/{opt.modality_id}: preference_score out of band"
                )

    def test_every_required_terrain_is_canonical_TRN(self):
        for d_id, opt_defs in _MODALITY_OPTIONS_PER_DISCIPLINE.items():
            for opt in opt_defs:
                for t in opt.requires_terrain_any_of:
                    assert t in _KNOWN_TRN_IDS, (
                        f"{d_id}/{opt.modality_id} references unknown terrain {t!r}"
                    )

    def test_every_required_skill_toggle_is_canonical(self):
        for d_id, opt_defs in _MODALITY_OPTIONS_PER_DISCIPLINE.items():
            for opt in opt_defs:
                if opt.requires_skill_toggle is None:
                    continue
                assert opt.requires_skill_toggle in _KNOWN_SKILL_TOGGLES, (
                    f"{d_id}/{opt.modality_id} references unknown skill toggle "
                    f"{opt.requires_skill_toggle!r}"
                )

    def test_every_required_equipment_is_canonical(self):
        # Spec v2 §I + §J §13.11. Every `requires_equipment_all_of` entry
        # in the resolver dict must appear in the test file's
        # `_KNOWN_EQUIPMENT` set (which mirrors canonical 0B after the K2
        # + K3 ETL additions). Catches resolver-vs-canonical drift at CI
        # time before runtime.
        for d_id, opt_defs in _MODALITY_OPTIONS_PER_DISCIPLINE.items():
            for opt in opt_defs:
                for equip in opt.requires_equipment_all_of:
                    assert equip in _KNOWN_EQUIPMENT, (
                        f"{d_id}/{opt.modality_id} references non-canonical "
                        f"equipment {equip!r} (add to populate_equipment_items "
                        f"ETL + the test's _KNOWN_EQUIPMENT set)"
                    )

    def test_modality_ids_unique_per_discipline(self):
        for d_id, opt_defs in _MODALITY_OPTIONS_PER_DISCIPLINE.items():
            ids = [opt.modality_id for opt in opt_defs]
            assert len(ids) == len(set(ids)), (
                f"{d_id}: duplicate modality_id in vocab"
            )

    def test_spec_representative_disciplines_present(self):
        # Spec v1 ships D-001, D-006, D-010 verbatim.
        # Spec v2 §H adds D-008b. Lock the floor.
        for d_id in ("D-001", "D-006", "D-008b", "D-010"):
            assert d_id in _MODALITY_OPTIONS_PER_DISCIPLINE


# ─── §10 edge cases (subset not covered by 13.x) ─────────────────────────────


class TestEdgeCases:
    def test_discipline_absent_from_dict_is_silent_pass_through(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-001", "Trail Running"), _sdb_row("D-013", "Wilderness Nav"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[_locale(terrain=["TRN-002"], pool=[])],
            included_discipline_ids=["D-001", "D-013"],
            etl_version_set=_DEFAULT_ETL,
        )
        # D-013 has no entries in _MODALITY_OPTIONS_PER_DISCIPLINE — no rec emitted.
        rec_disciplines = {r.discipline_id for r in payload.recommendations}
        assert rec_disciplines == {"D-001"}
        flag_disciplines = {f.discipline_id for f in payload.coaching_flags}
        assert "D-013" not in flag_disciplines

    def test_skill_toggle_states_none_treated_as_default_off(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-010", "Outdoor Rock Climbing"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    terrain=["TRN-013"],
                    pool=["Rope", "Quickdraws", "Harness", "Crash pad"],
                )
            ],
            included_discipline_ids=["D-010"],
            skill_toggle_states=None,
            etl_version_set=_DEFAULT_ETL,
        )
        d010 = payload.recommendations[0]
        modality_ids = [opt.modality_id for opt in d010.menu]
        # outdoor_lead_climb + outdoor_top_rope gated by climbing_roped (default OFF).
        # outdoor_boulder needs no skill toggle → surfaces.
        assert "outdoor_lead_climb" not in modality_ids
        assert "outdoor_top_rope" not in modality_ids
        assert "outdoor_boulder" in modality_ids

    def test_determinism_stable_modality_order(self):
        # Two options at the same preference_score should still come back
        # in stable alphabetical order by modality_id.
        conn = _FakeConn()
        conn.queue(_sdb_row("D-010", "Outdoor Rock Climbing"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    terrain=["TRN-014"],
                    pool=["Climbing gym membership"],
                )
            ],
            included_discipline_ids=["D-010"],
            skill_toggle_states={"climbing_roped": True},
            etl_version_set=_DEFAULT_ETL,
        )
        # gym_lead_climb (60) + gym_top_rope (55) + gym_boulder (50) — strict
        # by preference desc; alphabetic on tie. No ties at canonical scores
        # today; this test locks the comparator should future vocab tie.
        scores = [opt.preference_score for opt in payload.recommendations[0].menu]
        assert scores == sorted(scores, reverse=True)

    def test_payload_is_pydantic_validated_layer2_modality_payload(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-001", "Trail Running"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[_locale(terrain=["TRN-001"], pool=[])],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        assert isinstance(payload, Layer2ModalityPayload)
        assert isinstance(payload.recommendations[0], ModalityRecommendation)
        assert isinstance(payload.recommendations[0].menu[0], ModalityOption)

    def test_locale_name_fallback_to_locale_id_in_rationale(self):
        # When locale_name is None, the rationale_template's
        # {locale_name} should still render (using locale_id).
        conn = _FakeConn()
        conn.queue(_sdb_row("D-001", "Trail Running"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale("unnamed_locale", locale_name=None, terrain=["TRN-002"], pool=[])
            ],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        rec = payload.recommendations[0]
        assert "unnamed_locale" in rec.rationale_hint

    def test_discipline_name_falls_back_to_id_when_sdb_miss(self):
        # If SDB returns no row for an included discipline (shouldn't
        # happen in prod since the orchestrator sources discipline_ids
        # from SDB itself), the resolver still produces a row using
        # discipline_id as the name.
        conn = _FakeConn()
        conn.queue()  # zero rows
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[_locale(terrain=["TRN-001"], pool=[])],
            included_discipline_ids=["D-001"],
            etl_version_set=_DEFAULT_ETL,
        )
        rec = payload.recommendations[0]
        assert rec.discipline_name == "D-001"  # fallback


# ─── BM-3 render helpers (per-renderer-native copy per F2) ───────────────────


def _populated_payload() -> Layer2ModalityPayload:
    """Build a representative payload covering the three §8 flag triggers
    for use across the per-renderer render tests below."""
    rec = ModalityRecommendation(
        discipline_id="D-001",
        discipline_name="Trail Running",
        locale_id="home",
        locale_name="Home (Nerstrand MN)",
        menu=[
            ModalityOption(
                modality_id="outdoor_trail_run",
                modality_name="Outdoor trail run",
                preference_score=90,
                is_outdoor=True,
                is_specific=True,
                rationale_hint="trail terrain accessible from Home (Nerstrand MN)",
                satisfied_terrain=["TRN-002"],
                satisfied_equipment=[],
                satisfied_skill=None,
            ),
            ModalityOption(
                modality_id="outdoor_road_run",
                modality_name="Outdoor road run",
                preference_score=60,
                is_outdoor=True,
                is_specific=False,
                rationale_hint="paved surface accessible",
                satisfied_terrain=["TRN-001"],
                satisfied_equipment=[],
                satisfied_skill=None,
            ),
        ],
        top_pick_modality_id="outdoor_trail_run",
        rationale_hint="trail terrain accessible from Home (Nerstrand MN)",
    )
    flag = ModalityCoachingFlag(
        flag_type="skill_capability_blocks_specific_modality",
        discipline_id="D-010",
        discipline_name="Outdoor Rock Climbing",
        locale_id="home",
        locale_name="Home (Nerstrand MN)",
        message=(
            "Outdoor lead climbing is the best-fit modality at Home but "
            "requires the 'climbing_roped' skill toggle, which is currently OFF."
        ),
        metadata={
            "blocked_modality_id": "outdoor_lead_climb",
            "blocking_skill_toggle": "climbing_roped",
            "currently_resolves_to": "outdoor_boulder",
        },
    )
    return Layer2ModalityPayload(
        etl_version_set=_DEFAULT_ETL,
        recommendations=[rec],
        coaching_flags=[flag],
    )


def _empty_payload() -> Layer2ModalityPayload:
    return Layer2ModalityPayload(
        etl_version_set=_DEFAULT_ETL, recommendations=[], coaching_flags=[]
    )


# ─── Spec v2 §J — race-craft hint + D-008b paddling scenarios ────────────────


class TestScenario13_7_RaceCraftBumpAtAndysPGE:
    """Spec v2 §J §13.7 — race-craft bump fires for D-008b with
    `race_modality_hints={'D-008b': ['Packraft']}` at Andy's home locale.
    """

    def _setup(self, hints):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        return resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    terrain=[
                        "TRN-001", "TRN-002", "TRN-003", "TRN-004",
                        "TRN-008", "TRN-009", "TRN-016",
                    ],
                    pool=["Packraft", "Kayak", "SUP"],
                )
            ],
            included_discipline_ids=["D-008b"],
            skill_toggle_states={},
            race_modality_hints=hints,
            etl_version_set=_DEFAULT_ETL,
        )

    def test_packraft_top_pick_with_hint(self):
        payload = self._setup({"D-008b": ["Packraft"]})
        rec = payload.recommendations[0]
        assert rec.top_pick_modality_id == "outdoor_paddle_packraft"
        # Spec v2 §B: 75 × 1.2 = 90 (int-rounded; cap at 100).
        top = rec.menu[0]
        assert top.modality_id == "outdoor_paddle_packraft"
        assert top.preference_score == 90
        assert top.race_craft_match is True

    def test_kayak_and_sup_unchanged_without_hint(self):
        payload = self._setup({"D-008b": ["Packraft"]})
        rec = payload.recommendations[0]
        by_id = {opt.modality_id: opt for opt in rec.menu}
        assert by_id["outdoor_paddle_kayak"].preference_score == 75
        assert by_id["outdoor_paddle_kayak"].race_craft_match is False
        assert by_id["outdoor_paddle_sup"].preference_score == 65
        assert by_id["outdoor_paddle_sup"].race_craft_match is False

    def test_no_hint_packraft_and_kayak_tied(self):
        # Without race-craft hint, packraft + kayak tie at 75 → menu sort
        # is `(-score, modality_id)` so kayak sorts before packraft
        # alphabetically.
        payload = self._setup(None)
        rec = payload.recommendations[0]
        assert rec.top_pick_modality_id == "outdoor_paddle_kayak"
        for opt in rec.menu:
            assert opt.race_craft_match is False


class TestScenario13_8_HintWithUnknownEquipment:
    """Spec v2 §J §13.8 — hint with non-matching equipment name silently
    ignores (no bump, no error).
    """

    def test_silent_ignore(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    terrain=["TRN-009"],
                    pool=["Packraft", "Kayak"],
                )
            ],
            included_discipline_ids=["D-008b"],
            race_modality_hints={"D-008b": ["NonexistentCraft"]},
            etl_version_set=_DEFAULT_ETL,
        )
        # No bump applied.
        for opt in payload.recommendations[0].menu:
            assert opt.race_craft_match is False
            assert opt.preference_score in {75, 65}  # base scores untouched


class TestScenario13_9_HintForAbsentDiscipline:
    """Spec v2 §J §13.9 — hint for discipline not in
    `_MODALITY_OPTIONS_PER_DISCIPLINE` silently ignores.
    """

    def test_silent_ignore(self):
        conn = _FakeConn()
        conn.queue(
            _sdb_row("D-001", "Trail Running"),
            _sdb_row("D-008b", "Outdoor Paddling"),
        )
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    terrain=["TRN-002", "TRN-009"],
                    pool=["Packraft"],
                )
            ],
            included_discipline_ids=["D-001", "D-008b"],
            race_modality_hints={"D-099": ["Packraft"]},  # absent discipline
            etl_version_set=_DEFAULT_ETL,
        )
        # No bump for D-008b's packraft.
        d008b_rec = next(r for r in payload.recommendations if r.discipline_id == "D-008b")
        for opt in d008b_rec.menu:
            assert opt.race_craft_match is False
            assert opt.preference_score == 75


class TestScenario13_10_WhitewaterHintWithToggleOn:
    """Spec v2 §J §13.10 — whitewater_handling=True + Packraft hint at a
    moving-water locale bumps `outdoor_whitewater_packraft` to 96.
    """

    def test_whitewater_packraft_top_at_96(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    locale_id="river",
                    locale_name="River put-in",
                    terrain=["TRN-011", "TRN-017"],
                    pool=["Packraft", "Kayak"],
                )
            ],
            included_discipline_ids=["D-008b"],
            skill_toggle_states={"whitewater_handling": True},
            race_modality_hints={"D-008b": ["Packraft"]},
            etl_version_set=_DEFAULT_ETL,
        )
        rec = payload.recommendations[0]
        # 80 × 1.2 = 96 (int-rounded).
        top = rec.menu[0]
        assert top.modality_id == "outdoor_whitewater_packraft"
        assert top.preference_score == 96
        assert top.race_craft_match is True
        # Kayak option stays at base 80 (no bump; hint only mentions Packraft).
        kayak = next(opt for opt in rec.menu if opt.modality_id == "outdoor_whitewater_kayak")
        assert kayak.preference_score == 80
        assert kayak.race_craft_match is False


class TestScenarioD008b_BaseShape:
    """Lock the v2 §H D-008b vocab shape: 6 options, expected base scores,
    correct skill-gate on whitewater options. Mirror of `TestScenario13_1`
    for the D-008b row."""

    def test_six_options_in_dict(self):
        opt_defs = _MODALITY_OPTIONS_PER_DISCIPLINE["D-008b"]
        assert len(opt_defs) == 6
        ids = {opt.modality_id for opt in opt_defs}
        assert ids == {
            "outdoor_paddle_packraft",
            "outdoor_paddle_kayak",
            "outdoor_paddle_sup",
            "outdoor_whitewater_packraft",
            "outdoor_whitewater_kayak",
            "pool_paddle_drill",
        }

    def test_whitewater_options_skill_gated(self):
        for opt in _MODALITY_OPTIONS_PER_DISCIPLINE["D-008b"]:
            if "whitewater" in opt.modality_id:
                assert opt.requires_skill_toggle == "whitewater_handling"
            else:
                assert opt.requires_skill_toggle is None


class TestScenarioD008bScoreCap:
    """Spec v2 §L — score cap edge case. Score of 84+ multiplied by 1.2
    caps at 100.
    """

    def test_score_cap_at_100(self):
        # Manufactured scenario: synthesize a payload where a *1.2 bump
        # would otherwise blow past 100. The cap path uses min(100, ...),
        # so the test asserts the cap. None of the v2 vocab hits the cap
        # today (highest base is 90 for D-001/D-006/D-010; 90 * 1.2 = 108
        # → 100). Andy's PGE 2026 D-008b vocab tops out at 80 (whitewater)
        # which bumps to 96 < 100. We exercise the cap via D-010 climbing
        # at a hint-matched 90-base option.
        conn = _FakeConn()
        conn.queue(_sdb_row("D-010", "Outdoor Rock Climbing"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(
                    terrain=["TRN-013"],
                    pool=["Rope", "Quickdraws", "Harness"],
                )
            ],
            included_discipline_ids=["D-010"],
            skill_toggle_states={"climbing_roped": True},
            race_modality_hints={"D-010": ["Rope"]},  # bumps lead + top_rope
            etl_version_set=_DEFAULT_ETL,
        )
        rec = payload.recommendations[0]
        lead = next(opt for opt in rec.menu if opt.modality_id == "outdoor_lead_climb")
        # Base 90 * 1.2 = 108 → capped at 100.
        assert lead.preference_score == 100
        assert lead.race_craft_match is True


class TestRaceCraftHintBackwardCompat:
    """Spec v2 §N — default-None / empty-dict / empty-list hints all
    produce v1-identical resolver behavior.
    """

    def test_none_hint_no_bump(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(terrain=["TRN-009"], pool=["Packraft", "Kayak"])
            ],
            included_discipline_ids=["D-008b"],
            race_modality_hints=None,
            etl_version_set=_DEFAULT_ETL,
        )
        for opt in payload.recommendations[0].menu:
            assert opt.race_craft_match is False

    def test_empty_dict_no_bump(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(terrain=["TRN-009"], pool=["Packraft", "Kayak"])
            ],
            included_discipline_ids=["D-008b"],
            race_modality_hints={},
            etl_version_set=_DEFAULT_ETL,
        )
        for opt in payload.recommendations[0].menu:
            assert opt.race_craft_match is False

    def test_empty_list_per_discipline_no_bump(self):
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(terrain=["TRN-009"], pool=["Packraft", "Kayak"])
            ],
            included_discipline_ids=["D-008b"],
            race_modality_hints={"D-008b": []},
            etl_version_set=_DEFAULT_ETL,
        )
        for opt in payload.recommendations[0].menu:
            assert opt.race_craft_match is False

    def test_pool_paddle_drill_no_equipment_never_bumped(self):
        # Spec v2 §L: option with empty `requires_equipment_all_of` is
        # exempt from race-craft bump (no equipment to match against).
        # `pool_paddle_drill` has no equipment requirement.
        conn = _FakeConn()
        conn.queue(_sdb_row("D-008b", "Outdoor Paddling"))
        payload = resolve_best_fit_modality(
            conn,
            cluster_locale_inputs=[
                _locale(terrain=["TRN-008"], pool=[])
            ],
            included_discipline_ids=["D-008b"],
            # Even an empty list as the hint shouldn't bump pool_paddle_drill.
            # Add a hint and confirm the no-equip option stays unbumped.
            race_modality_hints={"D-008b": ["Packraft"]},
            etl_version_set=_DEFAULT_ETL,
        )
        rec = payload.recommendations[0]
        pool = next(opt for opt in rec.menu if opt.modality_id == "pool_paddle_drill")
        assert pool.race_craft_match is False
        assert pool.preference_score == 30


class TestSingleSessionRenderer:
    """`_render_modality_section_single_session` — markdown convention with
    `#` / `##` headers + `### Discipline at locale` per-recommendation
    subsection blocks."""

    def test_top_pick_and_alternates_render(self):
        from layer4.single_session import _render_modality_section_single_session

        lines = _render_modality_section_single_session(_populated_payload())
        text = "\n".join(lines)
        # Section header convention
        assert "# Best-fit modality recommendations" in text
        # Per-recommendation subsection
        assert "### D-001 Trail Running at Home (Nerstrand MN)" in text
        # Top pick line + rationale
        assert "Top pick: outdoor_trail_run (score 90)" in text
        assert "trail terrain accessible from Home (Nerstrand MN)" in text
        # Alternates rendered with preference score in parens
        assert "Alternates: outdoor_road_run (60)" in text
        # Guidance line on modality_id citation
        assert "natural modality name" in text
        assert "modality_id" in text

    def test_coaching_flag_renders_with_scope(self):
        from layer4.single_session import _render_modality_section_single_session

        lines = _render_modality_section_single_session(_populated_payload())
        text = "\n".join(lines)
        assert "## Coaching flags" in text
        assert "`skill_capability_blocks_specific_modality`" in text
        assert "D-010 at Home (Nerstrand MN)" in text

    def test_empty_payload_renders_placeholder_line(self):
        from layer4.single_session import _render_modality_section_single_session

        lines = _render_modality_section_single_session(_empty_payload())
        text = "\n".join(lines)
        assert "No modality recommendations available" in text
        # Section header still present so LLM knows the section was checked
        assert "# Best-fit modality recommendations" in text


class TestPerPhaseRenderer:
    """`_format_modality_recommendations_per_phase` — `=== Section ===`
    convention + tight one-line-per-recommendation format."""

    def test_top_pick_and_alternates_render(self):
        from layer4.per_phase import _format_modality_recommendations_per_phase

        lines = _format_modality_recommendations_per_phase(_populated_payload())
        text = "\n".join(lines)
        assert "=== Best-fit modality menu (per discipline, per locale) ===" in text
        # Compressed one-line rec
        assert "D-001 Trail Running @ Home (Nerstrand MN)" in text
        assert "top=outdoor_trail_run (90)" in text
        assert "alts=outdoor_road_run (60)" in text
        assert "rationale=trail terrain accessible" in text

    def test_coaching_flag_renders_inline(self):
        from layer4.per_phase import _format_modality_recommendations_per_phase

        lines = _format_modality_recommendations_per_phase(_populated_payload())
        text = "\n".join(lines)
        assert "Modality coaching flags:" in text
        assert "skill_capability_blocks_specific_modality" in text

    def test_empty_payload_renders_placeholder_line(self):
        from layer4.per_phase import _format_modality_recommendations_per_phase

        lines = _format_modality_recommendations_per_phase(_empty_payload())
        text = "\n".join(lines)
        assert "No recommendations or coaching flags" in text
        assert "=== Best-fit modality menu" in text

    def test_phase_aware_guidance_present(self):
        # per_phase is the prompt where phase-aware modality picking matters
        # (Peak / Taper biases). The guidance line should mention phase
        # intent so the LLM knows to apply phase context.
        from layer4.per_phase import _format_modality_recommendations_per_phase

        lines = _format_modality_recommendations_per_phase(_populated_payload())
        text = "\n".join(lines)
        assert "phase intent" in text
        assert "Peak" in text
        assert "Taper" in text


class TestRaceWeekBriefRenderer:
    """`_render_modality_section_race_week_brief` — `#` heading + `**bold:**`
    convention to match the brief's mixed markdown idiom."""

    def test_top_pick_and_alternates_render(self):
        from layer4.race_week_brief import _render_modality_section_race_week_brief

        lines = _render_modality_section_race_week_brief(_populated_payload())
        text = "\n".join(lines)
        assert "# Best-fit modality (Layer 2 modality resolver)" in text
        # **Bold:** convention for sub-labels
        assert "**Purpose:**" in text
        assert "**Recommendations:**" in text
        assert "**Modality coaching flags:**" in text
        # Per-rec one-line entry
        assert "D-001 Trail Running @ Home (Nerstrand MN)" in text
        assert "top: outdoor_trail_run" in text
        assert "alts: outdoor_road_run" in text

    def test_coaching_flag_renders_with_bold_scope(self):
        from layer4.race_week_brief import _render_modality_section_race_week_brief

        lines = _render_modality_section_race_week_brief(_populated_payload())
        text = "\n".join(lines)
        assert "`skill_capability_blocks_specific_modality`" in text
        # Verify the scope tag uses "at locale" phrasing per renderer style
        assert "D-010 at Home (Nerstrand MN)" in text

    def test_empty_payload_renders_placeholder_line(self):
        from layer4.race_week_brief import _render_modality_section_race_week_brief

        lines = _render_modality_section_race_week_brief(_empty_payload())
        text = "\n".join(lines)
        assert "No modality recommendations available" in text
        assert "# Best-fit modality (Layer 2 modality resolver)" in text


class TestRendererSpliceIntoFullPrompts:
    """The per-renderer modality section must actually appear in the full
    rendered prompt strings when the payload is threaded through. Catches
    the splice site (not just helper output)."""

    def _build_minimal_payloads(self):
        """Build the typed payloads single_session._render_user_prompt
        reads — using model_construct to bypass pydantic field-presence
        validation (the renderer only touches a small subset of fields)."""
        from layer4.context import (
            Layer2CPayload,
            Layer2DPayload,
            Layer3APayload,
        )

        l2c = Layer2CPayload.model_construct(
            locale_id="home",
            etl_version_set=_DEFAULT_ETL,
            effective_pool=["Treadmill"],
            exercises_resolved=[],
            discipline_coverage=[],
            coaching_flags=[],
        )
        l2d = Layer2DPayload.model_construct(
            etl_version_set=_DEFAULT_ETL,
            excluded_exercises=[],
            accommodated_exercises=[],
            coaching_flags=[],
            hitl_required=False,
        )

        class _Confidence:
            def __init__(self, level, confidence):
                self.level = level
                self.confidence = confidence

        class _Direction:
            def __init__(self, direction):
                self.direction = direction

        class _ACWR:
            combined = None
            per_discipline: dict = {}

        class _CS:
            aerobic_capacity = _Confidence("moderate", "high")
            strength = _Confidence("moderate", "high")
            weak_links: list = []

        class _RT:
            short_term = _Direction("stable")
            medium_term = _Direction("stable")
            acwr_status = _ACWR()

        class _DD:
            recent_workouts_count = 5
            integration_data_days = 30

        l3a = Layer3APayload.model_construct(
            user_id=1,
            current_state=_CS(),
            recent_trajectory=_RT(),
            data_density=_DD(),
        )
        return l2c, l2d, l3a

    def test_single_session_full_prompt_includes_modality_section(self):
        from datetime import date as _date_type

        from layer4.single_session import SingleSessionRequest, _render_user_prompt

        req = SingleSessionRequest(
            sport="Trail Running",
            duration_min=60,
            intensity="moderate",
            locale_slug="home",
            quick_equipment=[],
            notes_for_synthesizer=None,
        )
        l2c, l2d, l3a = self._build_minimal_payloads()
        text = _render_user_prompt(
            request=req,
            layer1_payload={"experience_level": "intermediate"},
            layer2c_payload_for_locale=l2c,
            layer2d_payload=l2d,
            layer3a_payload=l3a,
            session_date=_date_type(2026, 5, 24),
            retries_used=0,
            rule_failures=[],
            layer2_modality_payload_for_locale=_populated_payload(),
        )
        assert "# Best-fit modality recommendations" in text
        assert "outdoor_trail_run" in text

    def test_single_session_full_prompt_omits_section_when_payload_none(self):
        from datetime import date as _date_type

        from layer4.single_session import SingleSessionRequest, _render_user_prompt

        req = SingleSessionRequest(
            sport="Trail Running",
            duration_min=60,
            intensity="moderate",
            locale_slug=None,
            quick_equipment=["Treadmill"],
            notes_for_synthesizer=None,
        )
        _, l2d, l3a = self._build_minimal_payloads()
        text = _render_user_prompt(
            request=req,
            layer1_payload={"experience_level": "intermediate"},
            layer2c_payload_for_locale=None,
            layer2d_payload=l2d,
            layer3a_payload=l3a,
            session_date=_date_type(2026, 5, 24),
            retries_used=0,
            rule_failures=[],
            # No modality payload — must NOT render the section
        )
        assert "Best-fit modality" not in text
