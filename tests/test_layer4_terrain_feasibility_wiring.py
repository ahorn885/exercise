"""#540 slice 2c.2 — wiring of the deterministic terrain-feasibility cascade
into the plan-create synthesis prompt + cache key.

The pure cascade is covered by `test_layer4_session_feasibility.py`. This file
covers the wiring landed on top of it:

  - `_q_terrain_gap_rules` — the orchestrator's gap-rules reader.
  - `_build_terrain_feasibility` — per-discipline exercise-pool extraction +
    ranking, skill-gated exclusion (composition with #336), unconstrained drop.
  - the prompt render (`feasibility_line` / `grid_annotation` /
    `_format_session_feasibility`) per tier.
  - the cache-key fold (`compute_terrain_feasibility_hash` / `plan_create_key`).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from layer4 import orchestrator
from layer4 import per_phase
from layer4.hashing import (
    compute_terrain_feasibility_hash,
    plan_create_key,
    plan_refresh_key,
)
from layer4.session_feasibility import (
    TerrainResolution,
    feasibility_line,
    grid_annotation,
    resolve_terrain_feasibility,
)


# ─── _q_terrain_gap_rules reader ─────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows
        self.sql = None

    def execute(self, sql, params=()):
        self.sql = sql
        return _FakeCursor(self._rows)


def test_q_terrain_gap_rules_groups_by_target():
    db = _FakeDb(
        [
            {"target_terrain_id": "TRN-015", "proxy_terrain_id": "TRN-001", "proxy_fidelity": 0.55},
            {"target_terrain_id": "TRN-015", "proxy_terrain_id": "TRN-002", "proxy_fidelity": 0.80},
            {"target_terrain_id": "TRN-009", "proxy_terrain_id": "TRN-017", "proxy_fidelity": 0.40},
        ]
    )
    out = orchestrator._q_terrain_gap_rules(db)
    assert out == {
        "TRN-015": [("TRN-001", 0.55), ("TRN-002", 0.80)],
        "TRN-009": [("TRN-017", 0.40)],
    }
    # Reads only active rows with a proxy.
    assert "superseded_at IS NULL" in db.sql
    assert "proxy_terrain_id IS NOT NULL" in db.sql


def test_q_terrain_gap_rules_skips_null_fidelity():
    db = _FakeDb(
        [
            {"target_terrain_id": "TRN-015", "proxy_terrain_id": "TRN-001", "proxy_fidelity": None},
            {"target_terrain_id": "TRN-015", "proxy_terrain_id": "TRN-002", "proxy_fidelity": 0.5},
        ]
    )
    out = orchestrator._q_terrain_gap_rules(db)
    assert out == {"TRN-015": [("TRN-002", 0.5)]}


# ─── _build_terrain_feasibility ──────────────────────────────────────────────


def _ex(exercise_id, discipline_ids, tier, priorities, name=None):
    return SimpleNamespace(
        exercise_id=exercise_id,
        exercise_name=name or exercise_id,
        discipline_ids=discipline_ids,
        tier=tier,
        priority_per_discipline=priorities,
    )


def _flag(discipline_id, toggle):
    return SimpleNamespace(
        flag_type="requires_skill_capability",
        discipline_id=discipline_id,
        metadata={"toggle_name": toggle},
    )


def _cone(
    *, exercises, flags, disciplines, primary_locale="Home",
    bike_crafts=None, paddle_crafts=None,
):
    cycling = SimpleNamespace(bike_types_available=bike_crafts) if bike_crafts else None
    paddling = (
        SimpleNamespace(paddle_craft_types=paddle_crafts) if paddle_crafts else None
    )
    return SimpleNamespace(
        primary_locale=primary_locale,
        layer1_payload=SimpleNamespace(
            discipline_baselines=SimpleNamespace(paddling=paddling, cycling=cycling)
        ),
        # #780 — the cone carries one 2C payload per cluster locale (keyed by
        # locale_id). `_gather_feasibility_inputs` reads the primary entry for the
        # strength pool + the full dict for skill-gating, so the primary locale
        # must be present as a key.
        layer2c_payloads={
            primary_locale: SimpleNamespace(
                exercises_resolved=exercises, coaching_flags=flags
            )
        },
        layer2a_payload=SimpleNamespace(disciplines=disciplines),
    )


def _patch_cluster(monkeypatch, *, cluster, terrain, equipment, gaps):
    monkeypatch.setattr(
        orchestrator.locations, "cluster_locale_ids", lambda db, uid: cluster
    )
    monkeypatch.setattr(
        orchestrator.locations, "cluster_terrain_by_locale", lambda db, uid, c: terrain
    )
    monkeypatch.setattr(
        orchestrator.locations, "cluster_equipment_by_locale", lambda db, uid, c: equipment
    )
    monkeypatch.setattr(orchestrator, "_q_terrain_gap_rules", lambda db: gaps)
    # Deterministic venue display (#624): meta + terrain names. Trivial stubs —
    # name = slug, no distance — so these wiring tests stay focused on tier/locale
    # routing (the venue-menu rendering is covered in test_layer4_session_feasibility).
    monkeypatch.setattr(
        orchestrator.locations,
        "cluster_locale_meta",
        lambda db, uid, c, anchor_locale=None: {
            loc: {"name": loc, "distance_km": None} for loc in c
        },
    )
    monkeypatch.setattr(orchestrator, "_q_terrain_names", lambda db: {})


# Craft/terrain cascade maps (#586 WS-I). Default: empty → craft cascade tiers
# 1–4 all miss (the terrain tests above don't patch it, and _FakeDb([]) also
# yields empty maps), so non-craft disciplines fall back to the terrain cascade.
_BIKE_GROUPS = {"D-008": ["bike_offroad"], "D-006": ["bike_pavement"]}
_BIKE_GROUP_KIND = {"bike_offroad": "bike", "bike_pavement": "bike"}


def _patch_craft(
    monkeypatch, *, craft_disc, craft_kind, disc_groups, group_kind, craft_terrain=None
):
    monkeypatch.setattr(orchestrator, "_q_craft_discipline_aliases", lambda db: craft_disc)
    monkeypatch.setattr(orchestrator, "_q_craft_group_kind", lambda db: craft_kind)
    monkeypatch.setattr(orchestrator, "_q_modality_groups", lambda db: disc_groups)
    monkeypatch.setattr(orchestrator, "_q_modality_group_kind", lambda db: group_kind)
    monkeypatch.setattr(
        orchestrator, "_q_craft_terrain_compatibility", lambda db: craft_terrain or {}
    )


def test_build_craft_swap_road_bike_for_mtb(monkeypatch):
    # Race wants MTB (D-008); athlete owns only a road bike, which can't ride any
    # MTB terrain. The cluster has road (TRN-001) + groomed trail (TRN-002). The
    # unified cascade can't ride the trail on a road bike (tier 3 misses), so it
    # rides the road bike on the road and swaps the allocation to Road Cycling
    # (tier 4). The owned-outright road discipline resolves exact on TRN-001.
    cone = _cone(
        exercises=[],
        flags=[],
        disciplines=[
            SimpleNamespace(discipline_id="D-008", discipline_name="Mountain Biking", inclusion="included"),
            SimpleNamespace(discipline_id="D-006", discipline_name="Road Cycling", inclusion="included"),
        ],
        bike_crafts=["road_bike"],
    )
    _patch_cluster(
        monkeypatch,
        cluster=["Home"],
        terrain={"Home": {"TRN-001", "TRN-002"}},  # road + trail both present
        equipment={"Home": set()},
        gaps={},
    )
    _patch_craft(
        monkeypatch,
        craft_disc={"road_bike": ["D-006"]},
        craft_kind={"road_bike": "bike"},
        disc_groups=_BIKE_GROUPS,
        group_kind=_BIKE_GROUP_KIND,
        craft_terrain={"road_bike": {"TRN-001", "TRN-004"}},  # no off-road terrain
    )
    feas = orchestrator._build_terrain_feasibility(_FakeDb([]), 1, cone)
    mtb = feas["D-008"]
    assert mtb.craft_tier == "swap"
    assert mtb.owned_craft == "road_bike"
    assert mtb.craft_swap_to_name == "Road Cycling"
    # Ride the proxy on its OWN terrain (road, TRN-001), not MTB's trail.
    assert mtb.tier == "exact" and mtb.terrain_id == "TRN-001"
    # The owned-outright road discipline carries no craft action.
    assert feas["D-006"].craft_tier == "" and feas["D-006"].tier == "exact"


def test_build_craft_strength_when_no_bike_owned(monkeypatch):
    # Own no bike at all and no indoor machine: even though the cluster has MTB
    # terrain (TRN-002), tiers 1–5 all miss (no craft, no trainer) → strength
    # from the discipline's own pool, at the equipment-bearing locale.
    cone = _cone(
        exercises=[_ex("EX-SQUAT", ["D-008"], 1, {"D-008": "Critical"}, "Back Squat")],
        flags=[],
        disciplines=[
            SimpleNamespace(discipline_id="D-008", discipline_name="Mountain Biking", inclusion="included"),
        ],
        bike_crafts=None,
    )
    _patch_cluster(
        monkeypatch,
        cluster=["Home", "Gym"],
        terrain={"Home": {"TRN-002"}, "Gym": set()},
        equipment={"Home": set(), "Gym": {"Barbell"}},
        gaps={},
    )
    _patch_craft(
        monkeypatch,
        craft_disc={"road_bike": ["D-006"]},
        craft_kind={"road_bike": "bike"},
        disc_groups=_BIKE_GROUPS,
        group_kind=_BIKE_GROUP_KIND,
    )
    feas = orchestrator._build_terrain_feasibility(_FakeDb([]), 1, cone)
    res = feas["D-008"]
    assert res.craft_tier == "strength" and res.tier == "strength"
    assert res.craft_kind == "bike"
    assert res.substitute_exercise_ids == ["EX-SQUAT"]
    assert res.locale_id == "Gym"


def test_build_terrain_feasibility_climbing_no_gym_to_strength(monkeypatch):
    # Cluster has road + strength gear but no climbing terrain → climbing
    # resolves STRENGTH from its own mapped pool, ranked Critical→High→Medium.
    cone = _cone(
        exercises=[
            _ex("EX-GRIP", ["D-012"], 1, {"D-012": "Medium"}, "Hangboard"),
            _ex("EX-PULL", ["D-012"], 1, {"D-012": "Critical"}, "Weighted Pull-up"),
            _ex("EX-CORE", ["D-012"], 2, {"D-012": "High"}, "Hanging Leg Raise"),
            _ex("EX-UNAVAIL", ["D-012"], 0, {"D-012": "Critical"}, "Unavailable"),
        ],
        flags=[],
        disciplines=[
            SimpleNamespace(discipline_id="D-012", discipline_name="Rock Climbing", inclusion="included"),
        ],
    )
    _patch_cluster(
        monkeypatch,
        cluster=["Home", "Home Gym"],
        terrain={"Home": {"TRN-001"}, "Home Gym": set()},
        equipment={"Home": set(), "Home Gym": {"Pull-up bar"}},
        gaps={},
    )
    feas = orchestrator._build_terrain_feasibility(_FakeDb([]), 1, cone)
    assert set(feas) == {"D-012"}
    res = feas["D-012"]
    assert res.tier == "strength"
    # Placed at the equipment-bearing locale (the gym), not home.
    assert res.locale_id == "Home Gym"
    # Ranked best-first; tier-0 (unavailable) excluded.
    assert res.substitute_exercise_ids == ["EX-PULL", "EX-CORE", "EX-GRIP"]


def test_build_terrain_feasibility_excludes_skill_gated(monkeypatch):
    # A skill-gated discipline is owned by #336 (strength substitution at the
    # session level) — the terrain cascade must NOT also resolve it.
    cone = _cone(
        exercises=[_ex("EX-PULL", ["D-012"], 1, {"D-012": "Critical"})],
        flags=[_flag("D-012", "lead_climb")],
        disciplines=[
            SimpleNamespace(discipline_id="D-012", discipline_name="Rock Climbing", inclusion="included"),
        ],
    )
    _patch_cluster(
        monkeypatch,
        cluster=["Home"],
        terrain={"Home": set()},
        equipment={"Home": {"Pull-up bar"}},
        gaps={},
    )
    feas = orchestrator._build_terrain_feasibility(_FakeDb([]), 1, cone)
    assert feas == {}


def test_build_terrain_feasibility_drops_unconstrained_and_excluded(monkeypatch):
    cone = _cone(
        exercises=[],
        flags=[],
        disciplines=[
            # Unconstrained (no required terrain) → resolver returns None → drop.
            SimpleNamespace(discipline_id="D-027", discipline_name="OCR", inclusion="included"),
            # Not included → never resolved.
            SimpleNamespace(discipline_id="D-001", discipline_name="Trail Running", inclusion="excluded"),
            # Included + constrained + has the terrain → EXACT.
            SimpleNamespace(discipline_id="D-002", discipline_name="Road Running", inclusion="included"),
        ],
    )
    _patch_cluster(
        monkeypatch,
        cluster=["Home"],
        terrain={"Home": {"TRN-001"}},  # road
        equipment={"Home": set()},
        gaps={},
    )
    feas = orchestrator._build_terrain_feasibility(_FakeDb([]), 1, cone)
    assert set(feas) == {"D-002"}
    assert feas["D-002"].tier == "exact"


def test_build_terrain_feasibility_no_cluster_returns_empty(monkeypatch):
    cone = _cone(exercises=[], flags=[], disciplines=[])
    _patch_cluster(monkeypatch, cluster=[], terrain={}, equipment={}, gaps={})
    assert orchestrator._build_terrain_feasibility(_FakeDb([]), 1, cone) == {}


# ─── render — feasibility_line + grid_annotation ─────────────────────────────


def test_feasibility_line_per_tier():
    exact = TerrainResolution("D-001", "exact", "Cedar", terrain_id="TRN-003")
    assert 'real terrain available at "Cedar" (TRN-003)' in feasibility_line(
        exact, discipline_name="Trail Running"
    )

    proxy = TerrainResolution("D-008", "proxy", "Home", terrain_id="TRN-001", proxy_fidelity=0.55)
    line = feasibility_line(proxy, discipline_name="Mountain Biking")
    assert "nearest surface (TRN-001, fidelity 0.55)" in line and '"Home"' in line

    indoor = TerrainResolution("D-002", "indoor", "Gym", machine="Treadmill")
    assert "indoors on the Treadmill" in feasibility_line(indoor, discipline_name="Road Running")

    strength = TerrainResolution(
        "D-012", "strength", "Home", substitute_exercise_ids=["EX-1", "EX-2"]
    )
    line = feasibility_line(
        strength, discipline_name="Rock Climbing", exercise_names={"EX-1": "Pull-up"}
    )
    assert "STRENGTH session" in line
    # Names resolved when known, id fallback otherwise.
    assert "Pull-up" in line and "EX-2" in line

    realloc = TerrainResolution("D-004", "reallocate", None)
    assert "do NOT prescribe" in feasibility_line(realloc, discipline_name="Swimming")


def test_grid_annotation_only_for_kind_changing_tiers():
    assert grid_annotation(TerrainResolution("D", "exact", "Home")) == ""
    assert grid_annotation(TerrainResolution("D", "proxy", "Home")) == ""
    assert grid_annotation(TerrainResolution("D", "indoor", "Home")) == ""
    assert "STRENGTH substitution" in grid_annotation(
        TerrainResolution("D", "strength", "Home")
    )
    assert "reallocate" in grid_annotation(
        TerrainResolution("D", "reallocate", None)
    )


def test_feasibility_line_and_grid_craft_swap():
    # SWAP: craft prefix + the terrain detail for the swapped-to discipline.
    swap = TerrainResolution(
        "D-006", "exact", "Home", terrain_id="TRN-001",
        craft_tier="swap", owned_craft="road_bike", craft_swap_to_name="Road Cycling",
    )
    line = feasibility_line(swap, discipline_name="Mountain Biking")
    assert "you own a road bike" in line
    assert "train this allocation as Road Cycling" in line
    assert 'real terrain available at "Home" (TRN-001)' in line
    tag = grid_annotation(swap)
    assert "CRAFT-SWAP" in tag and "compose as Road Cycling" in tag


def test_feasibility_line_and_grid_craft_strength():
    # Craft STRENGTH terminal: reason is the missing craft, not missing terrain.
    cstr = TerrainResolution(
        "D-008", "strength", "Gym", substitute_exercise_ids=["EX-1"],
        craft_tier="strength", craft_kind="bike",
    )
    line = feasibility_line(
        cstr, discipline_name="Mountain Biking", exercise_names={"EX-1": "Back Squat"}
    )
    assert "you own no bike for this discipline" in line and "Back Squat" in line
    tag = grid_annotation(cstr)
    assert "NO CRAFT" in tag and "you own no bike" in tag


def test_format_session_feasibility_block_renders_names_and_skips_when_empty():
    assert per_phase._format_session_feasibility(None, None, {}) == []
    assert per_phase._format_session_feasibility({}, None, {}) == []

    feas = {
        "D-012": TerrainResolution(
            "D-012", "strength", "Home", substitute_exercise_ids=["EX-PULL"]
        )
    }
    l2a = SimpleNamespace(
        disciplines=[SimpleNamespace(discipline_id="D-012", discipline_name="Rock Climbing")]
    )
    l2c = {
        "Home Gym": SimpleNamespace(
            exercises_resolved=[
                SimpleNamespace(exercise_id="EX-PULL", exercise_name="Weighted Pull-up")
            ]
        )
    }
    block = per_phase._format_session_feasibility(feas, l2a, l2c)
    text = "\n".join(block)
    assert "=== Session feasibility" in text
    assert "Rock Climbing" in text and "Weighted Pull-up" in text


# ─── cache key ───────────────────────────────────────────────────────────────


def _base_key_kwargs():
    return dict(
        user_id=1,
        layer1_hash="l1",
        layer2a_hash="l2a",
        layer2b_hash="l2b",
        layer2c_bundle_hash="l2c",
        layer2d_hash="l2d",
        layer2e_hash="l2e",
        layer3a_hash="l3a",
        layer3b_hash="l3b",
        plan_start_date=date(2026, 6, 11),
        etl_version_set={"0A": "v7"},
        model_synthesizer="m",
        model_seam_reviewer="m",
        temperature=0.2,
        max_tokens_per_phase=0,
        capped_retries_per_phase=2,
    )


def test_terrain_feasibility_hash_is_deterministic_and_order_independent():
    a = {
        "D-012": TerrainResolution("D-012", "strength", "Home", substitute_exercise_ids=["EX-1"]),
        "D-008": TerrainResolution("D-008", "proxy", "Home", terrain_id="TRN-001", proxy_fidelity=0.55),
    }
    b = dict(reversed(list(a.items())))
    assert compute_terrain_feasibility_hash(a) == compute_terrain_feasibility_hash(b)

    c = dict(a)
    c["D-012"] = TerrainResolution("D-012", "strength", "Home", substitute_exercise_ids=["EX-2"])
    assert compute_terrain_feasibility_hash(a) != compute_terrain_feasibility_hash(c)


def test_plan_create_key_folds_terrain_feasibility():
    base = plan_create_key(**_base_key_kwargs())
    with_feas = plan_create_key(
        **_base_key_kwargs(),
        terrain_feasibility_hash="abc123",
    )
    assert base != with_feas
    # None collapses to '' → identical to omitting it (stable for legacy callers).
    assert plan_create_key(**_base_key_kwargs(), terrain_feasibility_hash=None) == base


def _base_refresh_key_kwargs():
    return dict(
        user_id=1,
        tier="T1",
        refresh_scope_start=date(2026, 6, 12),
        refresh_scope_end=date(2026, 6, 13),
        layer1_hash="l1",
        layer2_bundle_canonical_hash="l2",
        layer3a_hash="l3a",
        layer3b_hash="l3b",
        prior_plan_session_window_hash="pw",
        parsed_intent_hash=None,
        etl_version_set={"0A": "v7"},
        model_synthesizer="m",
        model_seam_reviewer=None,
        temperature=0.4,
        max_tokens=0,
        capped_retries=2,
    )


def test_plan_refresh_key_folds_terrain_feasibility():
    # #557 — the refresh cache key must invalidate when terrain feasibility
    # changes (a moved/edited locale → different prescription), and stay stable
    # for legacy callers that don't supply it.
    base = plan_refresh_key(**_base_refresh_key_kwargs())
    with_feas = plan_refresh_key(
        **_base_refresh_key_kwargs(),
        terrain_feasibility_hash="abc123",
    )
    assert base != with_feas
    assert (
        plan_refresh_key(**_base_refresh_key_kwargs(), terrain_feasibility_hash=None)
        == base
    )


# ─── integration — climbing-no-gym cone → strength → rendered prompt ─────────


def test_climbing_no_gym_resolution_surfaces_in_rendered_prompt():
    res = resolve_terrain_feasibility(
        "D-012",
        locale_order=["Home", "Home Gym"],
        cluster_terrain_by_locale={"Home": {"TRN-001"}, "Home Gym": set()},
        cluster_equipment_by_locale={"Home": set(), "Home Gym": {"Pull-up bar"}},
        gap_rules={},
        discipline_exercise_ids=["EX-PULL", "EX-GRIP"],
    )
    assert res.tier == "strength"
    feas = {"D-012": res}
    l2a = SimpleNamespace(
        disciplines=[SimpleNamespace(discipline_id="D-012", discipline_name="Rock Climbing")]
    )
    l2c = {
        "Home Gym": SimpleNamespace(
            exercises_resolved=[
                SimpleNamespace(exercise_id="EX-PULL", exercise_name="Weighted Pull-up"),
                SimpleNamespace(exercise_id="EX-GRIP", exercise_name="Hangboard Repeaters"),
            ]
        )
    }
    text = "\n".join(per_phase._format_session_feasibility(feas, l2a, l2c))
    assert "Weighted Pull-up" in text and "Hangboard Repeaters" in text
    assert "compose as strength" in text
