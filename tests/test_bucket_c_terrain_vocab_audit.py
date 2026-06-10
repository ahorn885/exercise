"""Bucket C terrain/locale vocab audit closure tests.

Closes Bucket C sub-items (a)-(e), (h), (j) from Andy's 2026-05-21 second-pass
manual walkthrough punch-list per the closing handoff sequence
(`V5_Implementation_D73_Phase_5_2_Walkthrough_V1CoachingRetire_...` originator
through `..._RouteLocalesAnchorFlags_2026_05_24_...` predecessor). The
predecessor §6.1 enumerated Bucket C as needing a Trigger #2 + #5 design pass;
the audit-and-close investigation confirmed (a)-(e) + (h) are already
mitigated defensively in `etl/layer0/vocabulary_transforms.py` +
`etl/layer0/extractors/vocabulary.py` + `etl/sources/parse_substitutes.py`.
These tests lock in the on-disk no-drift guarantees so future ETL or
vocab-source edits surface loudly via failing assertions rather than silently
re-introducing the punch-list items.

Sub-item closure:

  (a) Time-of-Day / Darkness — `SITUATIONAL_TOKENS`-routed discard;
      no canonical TRN-xxx row. `TestSituationalTokensNotTerrain`.
  (b) Social / Group Riding Environment — same. `TestSituationalTokensNotTerrain`.
  (c) Partner / Tandem / Team presence — same. `TestSituationalTokensNotTerrain`.
  (d) Generic / Varied Terrain — recognized by `TERRAIN_TOKENS` (so it
      doesn't leak into equipment) but has no canonical TRN-xxx (silent
      drop at terrain-name lookup). `TestLegacyTokensNotCanonical`.
  (e) Climbing gym vs outdoor split — TRN-013 (Outdoor) + TRN-014
      (Indoor Gym) are distinct canonical rows. `TestClimbingSplit`.
  (h) Cycling Trainer / Bike Trainer / Indoor Trainer dedup —
      aliased to 'Bike trainer' equipment item via
      etl/sources/parse_substitutes.py:58; not a terrain.
      `TestLegacyTokensNotCanonical`.
  (j) Layer 2B classifier vocab boundary — every canonical TRN-xxx row
      passes `_validate_inputs`; pattern validator + canonical vocab agree.
      `TestLayer2BClassifierVocabBoundary`.

Sub-item closure (added by the WaterVocabExpansion slice 2026-05-24):

  (f) Water-type expansion — 5-row split shipped: Pool (TRN-008) +
      Flat Water (TRN-009, retightened to still water only) + NEW
      Moving Water (TRN-017) + Ocean / Tidal (TRN-010, renamed from
      'Open Water / Ocean', retightened to saltwater/tidal only) +
      Whitewater (TRN-011, unchanged). `TestWaterRowExpansion`.

Sub-item closure (added by the BucketC_g_TerrainEquipmentMerge slice
2026-05-24):

  (g) Locale-terrain vs Outdoor-Terrain merge — locale form's
      'Outdoor & Terrain' equipment fieldset (9 display-only venue tags)
      retired in favour of the canonical terrain grid as the single
      'what's accessible from this location' surface. NEW TRN-020 Gravel
      added as the unambiguous surface gap (TRN-001 paved + TRN-002
      singletrack didn't cover compacted-gravel). Terrain rows describe
      SURFACE only; modality (foot/bike/etc.) is captured discipline-side
      + equipment-side via a future best-fit cross-reference. Equipment
      rows for cycling and paddling gear (road_bike / mountain_bike /
      gravel_bike / kayak / packraft / canoe) UNCHANGED — those are real
      equipment, not venue markers. `TestGravelTerrainAdd`.

Sub-items remaining open (forward-pointers, not in scope here):

  (l) Skill-capability toggles — replace the §8.2 `requires_coached_introduction`
      derivation with athlete-side toggles (default OFF/opt-in, mirror
      `sport_specific_gear_toggles` pattern). Narrow scope: climbing,
      whitewater, swim ability. Trigger #3 + #5 — plan-mode gate.

Sub-items recently closed (forward-pointer audit trail):

  (i) Mapbox-anchored race location required — closed end-to-end by the
      BucketC_i_MapboxRequired slice 2026-05-24 via NEW
      `_check_event_locale_mapbox_id_required` validator + route flash on
      4 POST handlers (race_events new/edit + set_locale + onboarding
      target_race_save).

(k) ETL drift fix already closed by the
`V5_Implementation_D73_Phase_5_2_Walkthrough_ETLTerrainVocabDriftFix_2026_05_24_...`
predecessor (canonical `_TERRAIN_STRUCTURED_ROWS` moved code-side).
"""

from __future__ import annotations

import pytest

# Force `layer4` to initialize before `layer2b` to dodge the pre-existing
# circular import that otherwise blocks this module from collection. Mirrors
# tests/test_layer2a.py:26 + tests/test_layer2b.py + tests/test_layer3_cached_wrappers.py:30.
from layer4 import InMemoryCacheBackend  # noqa: F401

from etl.layer0.extractors.vocabulary import _TERRAIN_STRUCTURED_ROWS
from etl.layer0.vocabulary_transforms import SITUATIONAL_TOKENS, TERRAIN_TOKENS
from layer2b.builder import _TRN_PATTERN, _validate_inputs
from layer4.context import RaceTerrainEntry


_CANONICAL_NAMES_LOWER: frozenset[str] = frozenset(
    row["canonical_name"].lower() for row in _TERRAIN_STRUCTURED_ROWS
)


# ─── Canonical vocab integrity ───────────────────────────────────────────────


class TestCanonicalTerrainVocab:
    """Locks in the 19-row TRN-001..TRN-018 + TRN-020 canonical shape so
    accidental additions, removals, or ID-pattern drift surface loudly.

    Row count bumped from 16 to 17 by the Bucket C (f) water-vocab
    expansion 2026-05-24 — NEW TRN-017 Moving Water added; TRN-009 and
    TRN-010 retightened in place (no count change for those two). Bumped
    from 17 to 18 by the Bucket C (g) terrain↔equipment merge 2026-05-24
    — NEW TRN-020 Gravel added as the unambiguous surface gap. Bumped
    from 18 to 19 by Vocabulary V3 — NEW TRN-018 Off Trail / Bushwhack
    (#340). TRN-019 remains intentionally reserved (gap in the sequence)
    — if Andy later ratifies the S3 cycling-vocab expansion, a cycling
    row would land at TRN-019."""

    def test_canonical_row_count_is_19(self):
        assert len(_TERRAIN_STRUCTURED_ROWS) == 19

    def test_every_canonical_row_has_TRN_pattern_id(self):
        for row in _TERRAIN_STRUCTURED_ROWS:
            assert _TRN_PATTERN.match(row["terrain_id"]), (
                f"terrain_id {row['terrain_id']!r} fails ^TRN-\\d{{3}}$"
            )

    def test_canonical_terrain_ids_unique(self):
        ids = [row["terrain_id"] for row in _TERRAIN_STRUCTURED_ROWS]
        assert len(ids) == len(set(ids))

    def test_canonical_names_unique(self):
        names = [row["canonical_name"] for row in _TERRAIN_STRUCTURED_ROWS]
        assert len(names) == len(set(names))

    def test_canonical_ids_are_TRN_001_through_018_plus_020(self):
        ids = sorted(row["terrain_id"] for row in _TERRAIN_STRUCTURED_ROWS)
        # TRN-018 now used (Vocabulary V3 — Off Trail / Bushwhack, #340).
        # TRN-019 remains intentionally reserved — see class docstring.
        expected = sorted([f"TRN-{i:03d}" for i in range(1, 19)] + ["TRN-020"])
        assert ids == expected


# ─── Sub-items (a)/(b)/(c): situational tokens are not terrain ───────────────


class TestSituationalTokensNotTerrain:
    """Bucket C (a)/(b)/(c): Darkness (time-of-day), Group Riding Environment
    (social), Partner/Tandem/Team (partner-presence) are race conditions,
    not terrain features. They live in `vocabulary_transforms.SITUATIONAL_TOKENS`
    and are discarded entirely during the ETL equipment-string transform.
    None must appear as a canonical TRN-xxx row."""

    @pytest.mark.parametrize(
        "token",
        [
            "Darkness",
            "Group Riding Environment",
            "Partner or Visual Cue",
            "Tandem Partner",
            "Team",
        ],
    )
    def test_token_is_in_situational_set(self, token):
        assert token in SITUATIONAL_TOKENS

    def test_no_situational_token_is_a_canonical_terrain_name(self):
        situational_lower = {t.lower() for t in SITUATIONAL_TOKENS}
        overlap = _CANONICAL_NAMES_LOWER & situational_lower
        assert overlap == set(), (
            f"SITUATIONAL_TOKENS overlaps canonical terrain names: {sorted(overlap)}"
        )

    def test_no_canonical_row_mentions_partner_tandem_or_team(self):
        for kw in ("partner", "tandem", "team"):
            assert not any(kw in n for n in _CANONICAL_NAMES_LOWER), (
                f"canonical terrain name contains social keyword {kw!r}"
            )


# ─── Sub-items (d) + (h): legacy aliases not canonical ───────────────────────


class TestLegacyTokensNotCanonical:
    """Bucket C (d): 'Varied Terrain' is generic — recognized by the
    legacy `TERRAIN_TOKENS` set during ETL transform (so it doesn't leak
    into equipment) but has no canonical TRN-xxx row (silently dropped
    at terrain-name resolution). Bucket C (h): Trainer / Bike Trainer /
    Cycling Trainer / Indoor Trainer is an equipment item aliased to
    'Bike trainer' via `etl/sources/parse_substitutes.py:58` — must NOT
    appear as a canonical terrain row."""

    def test_varied_terrain_recognized_during_etl(self):
        assert "Varied Terrain" in TERRAIN_TOKENS

    def test_varied_terrain_has_no_canonical_row(self):
        assert "varied terrain" not in _CANONICAL_NAMES_LOWER

    def test_no_canonical_row_mentions_trainer(self):
        # Catches "Trainer" / "Bike Trainer" / "Cycling Trainer" / "Indoor Trainer".
        assert not any("trainer" in n for n in _CANONICAL_NAMES_LOWER)

    def test_no_canonical_row_is_named_bike(self):
        # The MTB-category terrain row is TRN-015 Pump Track; no bike-equipment
        # term should have slipped in as a terrain canonical_name.
        assert "bike" not in _CANONICAL_NAMES_LOWER


# ─── Sub-item (e): climbing gym vs outdoor split ─────────────────────────────


class TestClimbingSplit:
    """Bucket C (e): the audit doc flagged Rock Wall and Climbing Gym as a
    single legacy 'Climbing terrain' alias in col-7. The canonical vocab
    carries them as TRN-013 (Outdoor) + TRN-014 (Indoor) so the classifier
    can resolve gym→outdoor adaptation correctly."""

    def test_outdoor_rock_wall_row_present(self):
        row = next(
            (r for r in _TERRAIN_STRUCTURED_ROWS if r["terrain_id"] == "TRN-013"),
            None,
        )
        assert row is not None
        assert row["environment"] == "Outdoor"
        assert row["category"] == "Climbing"
        assert "Rock Wall" in row["canonical_name"]

    def test_indoor_climbing_gym_row_present(self):
        row = next(
            (r for r in _TERRAIN_STRUCTURED_ROWS if r["terrain_id"] == "TRN-014"),
            None,
        )
        assert row is not None
        assert row["environment"] == "Indoor"
        assert row["category"] == "Climbing"
        assert row["canonical_name"] == "Climbing Gym"

    def test_climbing_category_has_both_indoor_and_outdoor(self):
        climbing_rows = [
            r for r in _TERRAIN_STRUCTURED_ROWS if r.get("category") == "Climbing"
        ]
        envs = {r["environment"] for r in climbing_rows}
        assert envs == {"Outdoor", "Indoor"}


# ─── Sub-item (j): Layer 2B classifier vocab boundary ────────────────────────


class TestLayer2BClassifierVocabBoundary:
    """Bucket C (j): the Layer 2B classifier's `_TRN_PATTERN` validator
    must accept every canonical TRN-xxx terrain_id without raising
    Layer2BInputError. The existing behavioral coverage in
    `tests/test_layer2b.py` (PGE baseline / Alpine unbridgeable / coached
    intro / empty-locale / multiple-proxy / unknown-id / clean-baseline /
    empty-race-terrain loosen) exercises the classifier paths; this test
    locks in the boundary — pattern validator and canonical vocab agree
    on what a terrain_id looks like."""

    def test_every_canonical_terrain_id_passes_validate_inputs(self):
        for row in _TERRAIN_STRUCTURED_ROWS:
            entry = RaceTerrainEntry(
                terrain_id=row["terrain_id"], pct_of_race=100.0
            )
            _validate_inputs(
                race_terrain=[entry],
                locale_terrain_ids=[row["terrain_id"]],
                included_discipline_ids=["D-001"],
                etl_version_set={"0C": "v7"},
            )


# ─── Sub-item (f): 5-row water vocab split ───────────────────────────────────


def _water_row(terrain_id: str) -> dict[str, object] | None:
    return next(
        (r for r in _TERRAIN_STRUCTURED_ROWS if r["terrain_id"] == terrain_id),
        None,
    )


class TestWaterRowExpansion:
    """Bucket C (f): the Water category was split from 4 rows to 5 rows
    so the Layer 2B classifier can differentiate stimulus on river-current
    handling vs lake/pool aerobic vs ocean/tidal vs whitewater. Locks in
    the 5-row shape + TRN-010 rename + TRN-009 retighten."""

    def test_water_category_has_five_rows(self):
        water = [r for r in _TERRAIN_STRUCTURED_ROWS if r.get("category") == "Water"]
        assert len(water) == 5

    def test_moving_water_row_exists(self):
        row = _water_row("TRN-017")
        assert row is not None
        assert row["canonical_name"] == "Moving Water"
        assert row["category"] == "Water"
        assert row["environment"] == "Outdoor"
        assert row["simulatable"] == "partial"
        # Moving water below Class II is not a technical surface (whitewater is).
        assert row["technical_surface"] is False
        assert row["requires_elevation"] is False

    def test_ocean_tidal_row_renamed(self):
        row = _water_row("TRN-010")
        assert row is not None
        assert row["canonical_name"] == "Ocean / Tidal"
        # The pre-split name 'Open Water / Ocean' must not appear anywhere
        # in the canonical vocab.
        names = {r["canonical_name"] for r in _TERRAIN_STRUCTURED_ROWS}
        assert "Open Water / Ocean" not in names

    def test_flat_water_row_no_longer_mentions_slow_river(self):
        row = _water_row("TRN-009")
        assert row is not None
        # Bucket C (f) retighten: TRN-009 is now still water only; the
        # 'slow river' framing migrated to the new TRN-017 row.
        notes_lower = row["notes"].lower()
        assert "slow river" not in notes_lower
        assert "still water" in notes_lower

    def test_moving_water_simulation_note_does_not_request_coaching(self):
        # Per Bucket C (l) forward-pointer: skill-capability gating moves
        # onto athlete-side toggles; the new Moving Water row must not
        # leak coached-intro language into the §8.2 keyword surface.
        row = _water_row("TRN-017")
        assert row is not None
        haystack = (row["simulation_note"] + " " + row["notes"]).lower()
        for kw in ("coached intro", "supervised instruction", "requires coached"):
            assert kw not in haystack

    def test_water_environment_split_unchanged(self):
        # Pool stays Indoor; the four outdoor rows stay Outdoor.
        envs_by_id = {
            r["terrain_id"]: r["environment"]
            for r in _TERRAIN_STRUCTURED_ROWS
            if r.get("category") == "Water"
        }
        assert envs_by_id == {
            "TRN-008": "Indoor",
            "TRN-009": "Outdoor",
            "TRN-010": "Outdoor",
            "TRN-011": "Outdoor",
            "TRN-017": "Outdoor",
        }


# ─── Sub-item (g): TRN-020 Gravel + Outdoor-Terrain fieldset retirement ──────


def _terrain_row(terrain_id: str) -> dict[str, object] | None:
    return next(
        (r for r in _TERRAIN_STRUCTURED_ROWS if r["terrain_id"] == terrain_id),
        None,
    )


class TestGravelTerrainAdd:
    """Bucket C (g): the locale form's 9-tag 'Outdoor & Terrain' equipment
    fieldset was redundant with the locale-terrain canonical grid; merge
    landed by retiring the equipment fieldset (init_db.py + _PG_MIGRATIONS
    translation) and adding TRN-020 Gravel as the one unambiguous surface
    gap that no existing TRN row covered. Pins the row exists, the row
    sits in the Foot category as a SURFACE-only entry (modality captured
    discipline-side + equipment-side), and the simulation_note doesn't
    leak any modality-specific language."""

    def test_gravel_row_exists(self):
        row = _terrain_row("TRN-020")
        assert row is not None
        assert row["canonical_name"] == "Gravel"

    def test_gravel_row_is_foot_category_surface_only(self):
        # SURFACE-only: Foot category matches the existing surface-typing
        # convention (TRN-001 Road/Paved, TRN-002 Groomed Trail, etc. are
        # all Foot category even though the surfaces are usable by both
        # running and cycling). Modality is captured by discipline +
        # equipment, not by the terrain row.
        row = _terrain_row("TRN-020")
        assert row is not None
        assert row["category"] == "Foot"
        assert row["environment"] == "Outdoor"
        assert row["simulatable"] == "partial"
        assert row["technical_surface"] is False
        assert row["requires_elevation"] is False

    def test_gravel_notes_describe_surface_not_modality(self):
        # Pins the SURFACE-only principle: the notes string must distinguish
        # gravel from paved + singletrack on surface terms; must not name a
        # specific modality (e.g. cycling-only or running-only) since the
        # row is meant to serve both.
        row = _terrain_row("TRN-020")
        assert row is not None
        notes_lower = row["notes"].lower()
        assert "compacted" in notes_lower or "unpaved" in notes_lower
        # Acknowledges both running and cycling use without scoping to
        # either exclusively.
        assert "gravel-running" in notes_lower or "gravel running" in notes_lower
        assert "gravel-cycling" in notes_lower or "gravel cycling" in notes_lower

    def test_gravel_simulation_note_does_not_request_coaching(self):
        # Same forward-compat pattern as the WaterVocab slice — Bucket C
        # (l) skill-toggle pivot means the §8.2 coached-intro flag stays
        # only on TRN-011 whitewater; new rows must not leak that language.
        row = _terrain_row("TRN-020")
        assert row is not None
        haystack = (row["simulation_note"] + " " + row["notes"]).lower()
        for kw in ("coached intro", "supervised instruction", "requires coached"):
            assert kw not in haystack

    def test_outdoor_terrain_equipment_tags_retired_from_init_db(self):
        # Bucket C (g) retired the 9 display-only 'Outdoor & Terrain'
        # equipment tags from init_db.EQUIPMENT_CATEGORIES. The locale form
        # now uses the locale-terrain canonical grid as the single
        # 'what's accessible from this location' surface.
        from init_db import EQUIPMENT_CATEGORIES

        category_names = {cat_name for cat_name, _ in EQUIPMENT_CATEGORIES}
        assert "Outdoor & Terrain" not in category_names, (
            "Bucket C (g) retired the 'Outdoor & Terrain' equipment fieldset; "
            "a re-introduction would re-create the locale-form dup."
        )
        # And the 9 individual tags must not have migrated into any other
        # equipment category by accident.
        all_tags = {tag for _, items in EQUIPMENT_CATEGORIES for tag, _ in items}
        retired_tags = {
            "trail_running",
            "road_running",
            "road_cycling",
            "mtb_trails",
            "gravel_routes",
            "open_water_paddle",
            "open_water_swim",
            "pool_swim",
            "hills",
        }
        overlap = all_tags & retired_tags
        assert overlap == set(), (
            f"Bucket C (g) retired tags reappeared in equipment vocab: "
            f"{sorted(overlap)}"
        )
