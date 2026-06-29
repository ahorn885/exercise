"""Helper-level tests for the #256/#592 race-detail auto-fill endpoints'
testable cores in routes/race_events.py (Slice 3).

Per this module's convention (test_routes_race_events.py): no Flask test_client
— the `run_*` cores are pure over a db + injected engines, so the route
handlers stay thin and full integration is the manual walkthrough. The DB is a
fake that routes execute() by SQL substring; the LLM engines, the page fetcher,
and the weather client are all injected.
"""

from __future__ import annotations

from datetime import date

from routes.race_events import (
    _all_disciplines,
    _terrain_vocab_entries,
    run_terrain_inference,
    run_url_parse,
)
from race_url_parser import DistanceOption, RaceURLParseError, RaceURLParseResult, TerrainEntry
from race_terrain_inference import (
    TerrainInferenceEntry,
    TerrainInferenceError,
    TerrainInferenceResult,
)

_TODAY = date(2026, 6, 22)


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class _FakeDB:
    """Routes execute() to canned rows by SQL substring."""

    def __init__(self, terrain_rows=None, discipline_rows=None):
        self._terrain = terrain_rows if terrain_rows is not None else [
            {'terrain_id': 'TRN-001', 'canonical_name': 'Flat road', 'notes': None},
            {'terrain_id': 'TRN-020', 'canonical_name': 'Gravel doubletrack', 'notes': None},
            {'terrain_id': 'TRN-014', 'canonical_name': 'Technical singletrack', 'notes': None},  # race-ineligible
        ]
        self._disc = discipline_rows if discipline_rows is not None else [
            {'discipline_id': 'D-001', 'discipline_name': 'Trail running'},
            {'discipline_id': 'D-010', 'discipline_name': 'Mountain biking'},
        ]

    def execute(self, sql, params=()):
        if 'terrain_types' in sql:
            return _Cursor(self._terrain)
        if 'sport_discipline_bridge' in sql:
            return _Cursor(self._disc)
        return _Cursor([])


# ─── loaders ─────────────────────────────────────────────────────────────────


def test_terrain_vocab_excludes_race_ineligible():
    vocab = _terrain_vocab_entries(_FakeDB())
    ids = {e.terrain_id for e in vocab}
    assert 'TRN-001' in ids and 'TRN-020' in ids
    assert 'TRN-014' not in ids          # race-ineligible filtered out


def test_all_disciplines_shape():
    out = _all_disciplines(_FakeDB())
    assert {d['id'] for d in out} == {'D-001', 'D-010'}
    assert all('label' in d for d in out)


# ─── run_url_parse ───────────────────────────────────────────────────────────


def _ok_fetcher(url):
    return (200, 'text/html', b'<h1>Big Race</h1><p>50K trail race</p>')


def test_run_url_parse_success_payload():
    canned = RaceURLParseResult(
        name='Big Race', event_date=date(2026, 9, 5), race_format='single_day',
        distance_options=[DistanceOption('50K', 50.0, None, 1600.0)],
        location_text='Lutsen, MN', framework_sport='Trail Running',
        included_discipline_ids=['D-001'],
        race_terrain=[TerrainEntry('TRN-020', 100.0, None)],
        terrain_pct_basis='estimated', rules_notes='9-hour cutoff.',
        confidence='high', summary='Got it — pick your distance.',
    )
    out = run_url_parse(_FakeDB(), 'https://example.com/race', today=_TODAY,
                        fetcher=_ok_fetcher, parser=lambda inp: canned)
    assert out['ok'] is True
    assert out['fields']['name'] == 'Big Race'
    assert out['fields']['event_date'] == '2026-09-05'
    # #948 — the form JS toggles the discipline checkbox grid from this field
    # and pre-fills the terrain editor from terrain.entries; keep both in the
    # payload so the auto-fill has data to thread into the form.
    assert out['fields']['included_discipline_ids'] == ['D-001']
    assert out['distance_options'][0]['label'] == '50K'
    assert out['terrain']['pct_basis'] == 'estimated'
    assert out['terrain']['entries'][0]['terrain_id'] == 'TRN-020'
    assert out['terrain']['entries'][0]['discipline_id'] is None
    assert out['confidence'] == 'high'


def test_run_url_parse_passes_loaded_vocab_and_bridge_to_parser():
    captured = {}

    def _parser(inp):
        captured['vocab'] = {e.terrain_id for e in inp.terrain_vocab}
        captured['bridge'] = {d.discipline_id for d in inp.sport_bridge}
        return RaceURLParseResult(name='X', confidence='low', summary='')

    run_url_parse(_FakeDB(), 'https://example.com/race', today=_TODAY,
                  fetcher=_ok_fetcher, parser=_parser)
    assert captured['vocab'] == {'TRN-001', 'TRN-020'}     # race-eligible only
    assert captured['bridge'] == {'D-001', 'D-010'}


def test_run_url_parse_fetch_failure_returns_hint():
    out = run_url_parse(_FakeDB(), 'https://example.com/race', today=_TODAY,
                        fetcher=lambda u: None, parser=lambda inp: None)
    assert out['ok'] is False
    assert 'hint' in out


def test_run_url_parse_parser_error_returns_hint():
    def _boom(inp):
        raise RaceURLParseError('anthropic_api_error', detail='503')

    out = run_url_parse(_FakeDB(), 'https://example.com/race', today=_TODAY,
                        fetcher=_ok_fetcher, parser=_boom)
    assert out['ok'] is False
    assert 'hint' in out


def test_run_url_parse_terrain_none_serializes_null():
    canned = RaceURLParseResult(name='X', confidence='low', summary='', race_terrain=None)
    out = run_url_parse(_FakeDB(), 'https://example.com/race', today=_TODAY,
                        fetcher=_ok_fetcher, parser=lambda inp: canned)
    assert out['terrain'] is None


# ─── run_terrain_inference ───────────────────────────────────────────────────


class _FakeConditions:
    def summary_line(self):
        return "Climate normals near the race date: typical high ~22C."


def _ok_infer(inp):
    return TerrainInferenceResult(
        terrain_breakdown=[TerrainInferenceEntry('D-001', 'TRN-020', 100.0, 'gravel region')],
        confidence='medium', summary='Mostly gravel — train for it.',
    )


def test_run_terrain_inference_with_coords_returns_terrain_and_conditions():
    out = run_terrain_inference(
        _FakeDB(), lat=47.6, lng=-90.7, event_date=date(2026, 9, 5),
        framework_sport='Trail Running', today=_TODAY,
        infer=_ok_infer, weather=lambda lat, lng, d: _FakeConditions(),
    )
    assert out['ok'] is True
    assert out['terrain']['entries'][0] == {'terrain_id': 'TRN-020', 'pct_of_race': 100.0, 'discipline_id': 'D-001'}
    assert out['terrain']['confidence'] == 'medium'
    assert 'Climate normals' in out['conditions']


def test_run_terrain_inference_failure_returns_terrain_none_but_conditions():
    def _boom(inp):
        raise TerrainInferenceError('validation', detail='off_vocab')

    out = run_terrain_inference(
        _FakeDB(), lat=47.6, lng=-90.7, event_date=date(2026, 9, 5),
        today=_TODAY, infer=_boom, weather=lambda lat, lng, d: _FakeConditions(),
    )
    assert out['terrain'] is None
    assert 'Climate normals' in out['conditions']     # weather is independent


def test_run_terrain_inference_no_coords_skips_both():
    calls = {'infer': 0, 'weather': 0}

    def _infer(inp):
        calls['infer'] += 1
        return _ok_infer(inp)

    def _weather(lat, lng, d):
        calls['weather'] += 1
        return _FakeConditions()

    out = run_terrain_inference(
        _FakeDB(), lat=None, lng=None, event_date=date(2026, 9, 5),
        today=_TODAY, infer=_infer, weather=_weather,
    )
    assert out['terrain'] is None and out['conditions'] is None
    assert calls == {'infer': 0, 'weather': 0}        # no coords → neither runs


def test_run_terrain_inference_no_weather_when_no_date():
    out = run_terrain_inference(
        _FakeDB(), lat=47.6, lng=-90.7, event_date=None, framework_sport='Trail Running',
        today=_TODAY, infer=_ok_infer, weather=lambda lat, lng, d: _FakeConditions(),
    )
    # coords but no date → terrain runs, weather (needs a date) does not
    assert out['terrain'] is not None
    assert out['conditions'] is None
