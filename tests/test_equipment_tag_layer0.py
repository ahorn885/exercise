"""Catalog unification (Slice B3): the purchases impacted-exercise count is
re-sourced from layer0 via the public-tag → layer0-equipment-token crosswalk."""

from __future__ import annotations

from equipment_tag_layer0 import (
    EQUIPMENT_TAG_TO_LAYER0_TOKEN,
    layer0_token_for_tag,
    layer0_equipment_exercise_counts,
)


def test_known_tag_maps_to_layer0_token():
    assert layer0_token_for_tag('barbell') == 'Barbell'
    assert layer0_token_for_tag('dumbbells') == 'Dumbbell'      # plural drift
    assert layer0_token_for_tag('sled') == 'Weighted sled'      # qualifier drift
    assert layer0_token_for_tag('plyo_box') == 'Plyo box'       # casing drift


def test_unmapped_tag_is_none():
    # Cardio / craft / generically-modelled equipment has no layer0 strength home.
    for tag in ('treadmill_NOPE', 'kayak', 'elliptical', 'smith_machine'):
        assert layer0_token_for_tag(tag) is None


def test_every_token_is_titlecase_layer0_shape():
    # Values are layer0 equipment_required tokens (not snake_case tags).
    for tag, token in EQUIPMENT_TAG_TO_LAYER0_TOKEN.items():
        assert '_' not in token, token
        assert token[0].isupper(), token


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        assert 'layer0.exercises' in sql and 'unnest(equipment_required)' in sql
        return _Cursor(self._rows)


def test_counts_index_by_token():
    conn = _Conn([
        {'equip': 'Barbell', 'cnt': 25},
        {'equip': 'Kettlebell', 'cnt': 38},
    ])
    counts = layer0_equipment_exercise_counts(conn)
    assert counts == {'Barbell': 25, 'Kettlebell': 38}
    # A recommendation bound to the 'barbell' tag reports 25 unlocked.
    assert counts.get(layer0_token_for_tag('barbell'), 0) == 25
    # An unmapped tag → 0 (no layer0 home).
    assert counts.get(layer0_token_for_tag('elliptical'), 0) == 0
