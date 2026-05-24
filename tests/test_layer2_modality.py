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

    def test_modality_ids_unique_per_discipline(self):
        for d_id, opt_defs in _MODALITY_OPTIONS_PER_DISCIPLINE.items():
            ids = [opt.modality_id for opt in opt_defs]
            assert len(ids) == len(set(ids)), (
                f"{d_id}: duplicate modality_id in vocab"
            )

    def test_spec_representative_disciplines_present(self):
        # Spec ships D-001, D-006, D-010 verbatim. Lock the floor.
        for d_id in ("D-001", "D-006", "D-010"):
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
