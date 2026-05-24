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

Sub-items remaining open (forward-pointers, not in scope here):

  (f) Water-type expansion — design call. Trigger #2 + #5.
  (g) Locale-terrain vs Outdoor-Terrain merge — Trigger #3 cross-layer
      schema. Plan-mode gate.
  (i) Mapbox-anchored race location required (remove free-text fallback)
      — Trigger #5.

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
    """Locks in the 16-row TRN-001..TRN-016 canonical shape so accidental
    additions, removals, or ID-pattern drift surface loudly."""

    def test_canonical_row_count_is_16(self):
        assert len(_TERRAIN_STRUCTURED_ROWS) == 16

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

    def test_canonical_ids_are_sequential_TRN_001_through_TRN_016(self):
        ids = sorted(row["terrain_id"] for row in _TERRAIN_STRUCTURED_ROWS)
        assert ids == [f"TRN-{i:03d}" for i in range(1, 17)]


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
