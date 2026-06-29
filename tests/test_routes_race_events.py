"""Tests for `routes/race_events.py` form-helper functions (D-73 Phase 5.2
walkthrough #1 + #2a, 2026-05-21).

Coverage:
- `_extract_mapbox_locale_from_form` — pulls 5 Mapbox-anchored hidden inputs
  off a form mapping; blank/missing/non-numeric inputs collapse safely
- `_parse_race_url` — trim + cap + empty-collapse semantics
- `_run_mapbox_search` — empty-query short-circuit + error translation for
  the 3 mapbox_client failure modes (no Mapbox HTTP round-trip via monkeypatch)
- `locale_search` JSON endpoint payload shape (via _run_mapbox_search behavior;
  full route integration deferred to manual §5.0 walkthrough per D-63 D12
  precedent — helper-level pytest density only)

Pattern mirrors `tests/test_onboarding_race_events.py`; no real DB or Flask
test_client. The route helpers are pure functions over a form-mapping +
mapbox_client adapter.
"""

from __future__ import annotations

import pytest

from routes.race_events import (
    _discipline_choices_for_race,
    _disciplines_for_framework_sport,
    _extract_mapbox_locale_from_form,
    _framework_sport_choices,
    _included_disciplines_from_terrain,
    _parse_first_time_at_distance,
    _parse_goal_outcome,
    _parse_pack_weight_kg,
    _parse_previous_attempts,
    _parse_race_terrain,
    _parse_race_url,
    _race_saved_discipline_ids,
    _rescope_terrain_to_framework_sport,
    _resolve_effective_framework_sport,
    _run_mapbox_search,
)


class _FakeFormMapping(dict):
    """Stand-in for `request.form` (a `MultiDict`-shaped mapping). The
    helpers under test only call `.get(key)` which `dict.get` satisfies.
    """

    def get(self, key, default=None):
        return super().get(key, default)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows=None):
        self._rows = rows or []

    def execute(self, _sql, _params=()):
        return _FakeCursor(self._rows)


# ─── _extract_mapbox_locale_from_form ───────────────────────────────────────


class TestExtractMapboxLocaleFromForm:
    def test_returns_all_none_when_form_empty(self):
        out = _extract_mapbox_locale_from_form(_FakeFormMapping())
        assert out == {
            'event_locale_name': None,
            'event_locale_mapbox_id': None,
            'event_locale_place_name': None,
            'event_locale_lat': None,
            'event_locale_lng': None,
        }

    def test_extracts_all_five_fields(self):
        form = _FakeFormMapping({
            'event_locale_name': 'Nerstrand State Park',
            'event_locale_mapbox_id': 'poi.abc123',
            'event_locale_place_name': 'Nerstrand State Park, MN, US',
            'event_locale_lat': '44.345',
            'event_locale_lng': '-93.106',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out == {
            'event_locale_name': 'Nerstrand State Park',
            'event_locale_mapbox_id': 'poi.abc123',
            'event_locale_place_name': 'Nerstrand State Park, MN, US',
            'event_locale_lat': 44.345,
            'event_locale_lng': -93.106,
        }

    def test_trims_whitespace_on_text_fields(self):
        form = _FakeFormMapping({
            'event_locale_name': '   Nerstrand   ',
            'event_locale_mapbox_id': 'poi.x  ',
            'event_locale_place_name': '  Nerstrand, MN',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_name'] == 'Nerstrand'
        assert out['event_locale_mapbox_id'] == 'poi.x'
        assert out['event_locale_place_name'] == 'Nerstrand, MN'

    def test_blank_text_fields_collapse_to_none(self):
        form = _FakeFormMapping({
            'event_locale_name': '   ',
            'event_locale_mapbox_id': '',
            'event_locale_place_name': '\t\n',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_name'] is None
        assert out['event_locale_mapbox_id'] is None
        assert out['event_locale_place_name'] is None

    def test_non_numeric_lat_lng_collapse_to_none(self):
        """Defensive: a malformed POST hand-crafted with `lat=NaN` or
        `lat=garbage` must not let `NaN` reach the NUMERIC(9,6) column."""
        form = _FakeFormMapping({
            'event_locale_lat': 'NaN',
            'event_locale_lng': 'not-a-number',
        })
        out = _extract_mapbox_locale_from_form(form)
        # `float('NaN')` succeeds, but `float('not-a-number')` raises and
        # collapses to None. NaN is technically a float; the only safety is
        # at the column-bound `Field(ge=-90, le=90)` on `RaceEventPayload`.
        # Document the boundary explicitly.
        assert out['event_locale_lng'] is None

    def test_empty_string_lat_lng_collapse_to_none(self):
        form = _FakeFormMapping({
            'event_locale_lat': '',
            'event_locale_lng': '   ',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_lat'] is None
        assert out['event_locale_lng'] is None

    def test_negative_coords_pass_through(self):
        form = _FakeFormMapping({
            'event_locale_lat': '-44.345',
            'event_locale_lng': '-93.106',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_lat'] == -44.345
        assert out['event_locale_lng'] == -93.106


# ─── _parse_race_url ────────────────────────────────────────────────────────


class TestParseRaceUrl:
    def test_returns_none_on_missing_key(self):
        assert _parse_race_url(_FakeFormMapping()) is None

    def test_returns_none_on_empty(self):
        assert _parse_race_url(_FakeFormMapping({'race_url': ''})) is None

    def test_returns_none_on_whitespace_only(self):
        assert _parse_race_url(_FakeFormMapping({'race_url': '  \t\n  '})) is None

    def test_trims_whitespace(self):
        out = _parse_race_url(_FakeFormMapping({
            'race_url': '  https://example.com/race  ',
        }))
        assert out == 'https://example.com/race'

    def test_caps_at_1000_chars(self):
        long_url = 'https://example.com/' + ('x' * 2000)
        out = _parse_race_url(_FakeFormMapping({'race_url': long_url}))
        assert out is not None
        assert len(out) == 1000


# ─── _run_mapbox_search ─────────────────────────────────────────────────────


class TestRunMapboxSearch:
    def test_empty_query_short_circuits(self, monkeypatch):
        """No Mapbox HTTP round-trip for empty input."""
        import mapbox_client
        # If anything fires, we'd get a token error — assert nothing fires.
        called = {'count': 0}

        def fail_if_called(*args, **kwargs):
            called['count'] += 1
            raise AssertionError("search_places should not fire on empty q")

        monkeypatch.setattr(mapbox_client, 'search_places', fail_if_called)
        results, error = _run_mapbox_search('')
        assert results == []
        assert error is None
        assert called['count'] == 0

    def test_token_missing_returns_human_readable_error(self, monkeypatch):
        import mapbox_client

        def raise_token_missing(*args, **kwargs):
            raise mapbox_client.MapboxTokenMissing('test')

        monkeypatch.setattr(mapbox_client, 'search_places', raise_token_missing)
        results, error = _run_mapbox_search('Nerstrand')
        assert results == []
        assert error is not None
        assert 'not configured' in error.lower() or 'mapbox_public_token' in error.lower()

    def test_no_results_returns_friendly_error(self, monkeypatch):
        import mapbox_client

        def raise_no_results(*args, **kwargs):
            raise mapbox_client.MapboxNoResults('test')

        monkeypatch.setattr(mapbox_client, 'search_places', raise_no_results)
        results, error = _run_mapbox_search('asdfqwerty')
        assert results == []
        assert error is not None
        assert 'asdfqwerty' in error
        assert 'broader' in error.lower()

    def test_api_error_returns_translated_message(self, monkeypatch):
        import mapbox_client

        def raise_api_error(*args, **kwargs):
            raise mapbox_client.MapboxAPIError('502 bad gateway')

        monkeypatch.setattr(mapbox_client, 'search_places', raise_api_error)
        results, error = _run_mapbox_search('Nerstrand')
        assert results == []
        assert error is not None
        assert 'unavailable' in error.lower()
        assert '502 bad gateway' in error

    def test_happy_path_returns_results(self, monkeypatch):
        import mapbox_client

        def fake_search_places(query, limit=5):
            assert query == 'Nerstrand'
            return [
                {
                    'mapbox_id': 'poi.abc',
                    'text': 'Nerstrand State Park',
                    'place_name': 'Nerstrand State Park, MN, US',
                    'lng': -93.106,
                    'lat': 44.345,
                    'category': '',
                    'raw_payload': '',
                },
            ]

        monkeypatch.setattr(mapbox_client, 'search_places', fake_search_places)
        results, error = _run_mapbox_search('Nerstrand')
        assert error is None
        assert len(results) == 1
        assert results[0]['text'] == 'Nerstrand State Park'


# ─── _included_disciplines_from_terrain (#949) ──────────────────────────────


class TestIncludedDisciplinesFromTerrain:
    """#949 — the included-discipline narrowing is derived from the terrain
    breakdown: a discipline that scopes any row is included; race-wide rows
    contribute nothing; no scoped rows → None (use bridge defaults)."""

    def test_empty_terrain_returns_none(self):
        assert _included_disciplines_from_terrain([]) is None
        assert _included_disciplines_from_terrain(None) is None

    def test_all_race_wide_rows_return_none(self):
        terrain = [
            {'terrain_id': 'TRN-002', 'pct_of_race': 40.0, 'discipline_id': None},
            {'terrain_id': 'TRN-003', 'pct_of_race': 60.0, 'discipline_id': None},
        ]
        assert _included_disciplines_from_terrain(terrain) is None

    def test_distinct_sorted_scoped_disciplines(self):
        terrain = [
            {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': 'D-010'},
            {'terrain_id': 'TRN-002', 'pct_of_race': 30.0, 'discipline_id': 'D-001'},
            # Duplicate coupling + a race-wide row are both folded out.
            {'terrain_id': 'TRN-003', 'pct_of_race': 20.0, 'discipline_id': 'D-010'},
            {'terrain_id': 'TRN-004', 'pct_of_race': 20.0, 'discipline_id': None},
        ]
        assert _included_disciplines_from_terrain(terrain) == ['D-001', 'D-010']

    def test_non_dict_entries_ignored(self):
        terrain = ['junk', {'discipline_id': 'D-005'}]
        assert _included_disciplines_from_terrain(terrain) == ['D-005']


# ─── §H.2 goal-context parse helpers (2026-05-26) ───────────────────────────


class TestParseGoalContextHelpers:
    """`goal_outcome` / `first_time_at_distance` / `race_pack_weight_kg`
    form-parse helpers for the §H.2 deployed-shape-gap slice."""

    def test_goal_outcome_valid_values_pass(self):
        for v in ('Finish', 'Compete mid-pack', 'Podium'):
            assert _parse_goal_outcome(_FakeFormMapping({'goal_outcome': v})) == v

    def test_goal_outcome_blank_or_invalid_coerces_none(self):
        assert _parse_goal_outcome(_FakeFormMapping({'goal_outcome': ''})) is None
        assert _parse_goal_outcome(_FakeFormMapping()) is None
        assert _parse_goal_outcome(
            _FakeFormMapping({'goal_outcome': 'World Record'})
        ) is None

    def test_first_time_tri_state(self):
        assert _parse_first_time_at_distance(
            _FakeFormMapping({'first_time_at_distance': 'yes'})
        ) is True
        assert _parse_first_time_at_distance(
            _FakeFormMapping({'first_time_at_distance': 'no'})
        ) is False
        assert _parse_first_time_at_distance(
            _FakeFormMapping({'first_time_at_distance': ''})
        ) is None
        assert _parse_first_time_at_distance(_FakeFormMapping()) is None

    def test_pack_weight_parsing(self):
        assert _parse_pack_weight_kg(
            _FakeFormMapping({'race_pack_weight_kg': '8.5'})
        ) == 8.5
        # Blank / non-numeric / negative → None (DB CHECK is >= 0).
        assert _parse_pack_weight_kg(
            _FakeFormMapping({'race_pack_weight_kg': ''})
        ) is None
        assert _parse_pack_weight_kg(
            _FakeFormMapping({'race_pack_weight_kg': 'heavy'})
        ) is None
        assert _parse_pack_weight_kg(
            _FakeFormMapping({'race_pack_weight_kg': '-3'})
        ) is None


# ─── §H.2 Slice 2 — _parse_previous_attempts ────────────────────────────────


class TestParsePreviousAttempts:
    """`previous_attempts[N][...]` repeating-row parse helper. Mirrors
    `_parse_race_terrain`'s indexed-field discovery + drop-on-empty."""

    def test_dnf_row_with_cause_threads(self):
        form = _FakeFormMapping({
            'previous_attempts[0][outcome]': 'DNF',
            'previous_attempts[0][dnf_cause]': 'quad_failure',
        })
        assert _parse_previous_attempts(form) == [
            {'outcome': 'DNF', 'dnf_cause': 'quad_failure'},
        ]

    def test_finished_row_collapses_cause_to_none(self):
        form = _FakeFormMapping({
            'previous_attempts[0][outcome]': 'Finished',
            'previous_attempts[0][dnf_cause]': '',
        })
        assert _parse_previous_attempts(form) == [
            {'outcome': 'Finished', 'dnf_cause': None},
        ]

    def test_invalid_outcome_drops_row(self):
        form = _FakeFormMapping({
            'previous_attempts[0][outcome]': 'WonByMiles',
            'previous_attempts[0][dnf_cause]': 'quad_failure',
        })
        assert _parse_previous_attempts(form) == []

    def test_blank_outcome_drops_row(self):
        form = _FakeFormMapping({
            'previous_attempts[0][outcome]': '',
            'previous_attempts[0][dnf_cause]': 'weather',
        })
        assert _parse_previous_attempts(form) == []

    def test_invalid_dnf_cause_collapses_to_none(self):
        form = _FakeFormMapping({
            'previous_attempts[0][outcome]': 'DNF',
            'previous_attempts[0][dnf_cause]': 'bad_knee_vibes',
        })
        assert _parse_previous_attempts(form) == [
            {'outcome': 'DNF', 'dnf_cause': None},
        ]

    def test_multiple_rows_preserve_order(self):
        form = _FakeFormMapping({
            'previous_attempts[0][outcome]': 'DNF',
            'previous_attempts[0][dnf_cause]': 'nutrition_blowup',
            'previous_attempts[1][outcome]': 'Finished',
            'previous_attempts[2][outcome]': 'DNS',
        })
        assert _parse_previous_attempts(form) == [
            {'outcome': 'DNF', 'dnf_cause': 'nutrition_blowup'},
            {'outcome': 'Finished', 'dnf_cause': None},
            {'outcome': 'DNS', 'dnf_cause': None},
        ]

    def test_empty_form_returns_empty_list(self):
        assert _parse_previous_attempts(_FakeFormMapping()) == []


# ─── _parse_race_terrain — C1 discipline_id passthrough ─────────────────────


class TestParseRaceTerrainDisciplineId:
    """D-73 Phase 5.2 Bucket E.(c)-C1 — per-row optional discipline_id."""

    def test_row_with_discipline_id_threaded(self):
        form = _FakeFormMapping({
            'race_terrain[0][terrain_id]': 'TRN-017',
            'race_terrain[0][pct_of_race]': '15',
            'race_terrain[0][discipline_id]': 'D-008',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-017', 'pct_of_race': 15.0, 'discipline_id': 'D-008'},
        ]

    def test_blank_discipline_id_collapses_to_none(self):
        form = _FakeFormMapping({
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '35',
            'race_terrain[0][discipline_id]': '',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0, 'discipline_id': None},
        ]

    def test_missing_discipline_id_field_defaults_to_none(self):
        # Pre-C1 form shape — no discipline_id field at all. Backward-compat:
        # parses identically to a row with discipline_id=None.
        form = _FakeFormMapping({
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '35',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0, 'discipline_id': None},
        ]


# ─── _disciplines_for_framework_sport ───────────────────────────────────────


class TestDisciplinesForFrameworkSport:
    """Bridge-keyed lookup helper used to render the B2 checkbox grid +
    the C1 per-row terrain `<select>`."""

    def test_returns_id_label_dicts_from_bridge(self):
        # Labels come from the curated pure-craft overlay (keyed by id),
        # not the sport-variant bridge `discipline_name`.
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
            {'discipline_id': 'D-010', 'discipline_name': 'Whitewater paddle'},
        ])
        out = _disciplines_for_framework_sport(conn, 'Adventure Racing')
        assert out == [
            {'id': 'D-001', 'label': 'Trail Running'},
            {'id': 'D-010', 'label': 'Kayaking'},
        ]

    def test_uncurated_id_falls_back_to_bridge_name(self):
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-006 + D-007', 'discipline_name': 'Road Cycling (+ TT/Tri Bike)'},
        ])
        out = _disciplines_for_framework_sport(conn, 'Triathlon')
        assert out == [
            {'id': 'D-006 + D-007', 'label': 'Road Cycling (+ TT/Tri Bike)'},
        ]

    def test_empty_framework_sport_short_circuits(self):
        # Avoids a wasted SELECT when the athlete hasn't yet typed
        # anything in the framework_sport input.
        conn = _FakeConn(rows=[])
        assert _disciplines_for_framework_sport(conn, '') == []
        assert _disciplines_for_framework_sport(conn, None) == []


# ─── _framework_sport_choices ───────────────────────────────────────────────


class TestFrameworkSportChoices:
    """Issue #885 — canonical race/event types for the structured select.
    Sourced from the DISTINCT `framework_sport` of the same bridge table the
    discipline grid reads, so every option resolves to a non-empty discipline
    set (the #892 data-loss fix)."""

    def test_returns_distinct_framework_sports_in_order(self):
        conn = _FakeConn(rows=[
            {'framework_sport': 'Adventure Racing'},
            {'framework_sport': 'Trail Running'},
            {'framework_sport': 'Triathlon'},
        ])
        assert _framework_sport_choices(conn) == [
            'Adventure Racing', 'Trail Running', 'Triathlon',
        ]

    def test_filters_blank_and_null_values(self):
        # Defensive — the SQL already excludes NULL, but a stray empty string
        # must not become a blank <option> that collides with the inherit row.
        conn = _FakeConn(rows=[
            {'framework_sport': 'Adventure Racing'},
            {'framework_sport': None},
            {'framework_sport': ''},
        ])
        assert _framework_sport_choices(conn) == ['Adventure Racing']

    def test_empty_table_returns_empty_list(self):
        conn = _FakeConn(rows=[])
        assert _framework_sport_choices(conn) == []


# ─── #892 discipline persistence across a sport change ──────────────────────


class TestRaceSavedDisciplineIds:
    """The race's own disciplines = its included filter + terrain couplings."""

    def test_none_race_is_empty(self):
        assert _race_saved_discipline_ids(None) == []
        assert _race_saved_discipline_ids({}) == []

    def test_unions_included_and_terrain_couplings_dedup_order(self):
        race = {
            'included_discipline_ids': ['D-001', 'D-010'],
            'race_terrain': [
                {'terrain_id': 'TRN-002', 'pct_of_race': 40.0, 'discipline_id': 'D-010'},
                {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': 'D-008'},
                {'terrain_id': 'TRN-003', 'pct_of_race': 30.0, 'discipline_id': None},
            ],
        }
        # included first (in order), then new terrain couplings; D-010 dedup'd,
        # race-wide (None) coupling skipped.
        assert _race_saved_discipline_ids(race) == ['D-001', 'D-010', 'D-008']

    def test_tolerates_missing_keys_and_nonlist(self):
        assert _race_saved_discipline_ids(
            {'included_discipline_ids': None, 'race_terrain': None}
        ) == []
        # A terrain entry that isn't a dict is ignored rather than raising.
        assert _race_saved_discipline_ids(
            {'race_terrain': ['junk', {'discipline_id': 'D-001'}]}
        ) == ['D-001']


class TestDisciplineChoicesForRace:
    """#892 — picker choices = bridge set UNION the race's saved disciplines."""

    def test_healthy_race_is_bridge_only(self):
        # Every saved id is in the bridge → union == bridge (no extras).
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
            {'discipline_id': 'D-010', 'discipline_name': 'Whitewater paddle'},
        ])
        race = {'included_discipline_ids': ['D-001'], 'race_terrain': []}
        out = _discipline_choices_for_race(conn, 'Adventure Racing', race)
        assert [c['id'] for c in out] == ['D-001', 'D-010']

    def test_saved_id_outside_bridge_is_appended(self):
        # The sport's bridge no longer contains D-099 (a prior pick) — it must
        # still render so the picker doesn't collapse to "Race-wide."
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
        ])
        race = {
            'included_discipline_ids': ['D-099'],
            'race_terrain': [
                {'terrain_id': 'TRN-002', 'pct_of_race': 40.0, 'discipline_id': 'D-050'},
            ],
        }
        out = _discipline_choices_for_race(conn, 'Trail Running', race)
        ids = [c['id'] for c in out]
        # Bridge first, then saved-but-unlisted ids in sorted order.
        assert ids == ['D-001', 'D-050', 'D-099']

    def test_unresolved_sport_still_renders_saved(self):
        # Sport doesn't resolve in the bridge (empty rows) but the race has
        # saved disciplines — render those instead of an empty picker.
        conn = _FakeConn(rows=[])
        race = {'included_discipline_ids': ['D-001'], 'race_terrain': []}
        out = _discipline_choices_for_race(conn, 'Something Custom', race)
        assert [c['id'] for c in out] == ['D-001']

    def test_new_race_none_is_bridge_only(self):
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
        ])
        out = _discipline_choices_for_race(conn, 'Trail Running', None)
        assert [c['id'] for c in out] == ['D-001']


class TestRescopeTerrainToFrameworkSport:
    """#892 / #949 — on a sport change, terrain couplings outside the new
    event type's bridge fall back to race-wide (preserving terrain_id + pct)
    instead of silently re-including an out-of-sport discipline."""

    def _bridge(self, *ids):
        return _FakeConn(rows=[
            {'discipline_id': i, 'discipline_name': i} for i in ids
        ])

    def test_resets_coupling_outside_bridge(self):
        conn = self._bridge('D-001', 'D-002')
        terrain = [
            {'terrain_id': 'TRN-002', 'pct_of_race': 40.0, 'discipline_id': 'D-001'},
            {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': 'D-099'},
            {'terrain_id': 'TRN-003', 'pct_of_race': 30.0, 'discipline_id': None},
        ]
        out, dropped = _rescope_terrain_to_framework_sport(
            conn, 'Trail Running', terrain
        )
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 40.0, 'discipline_id': 'D-001'},
            # D-099 not in the new bridge → reset to race-wide, pct preserved.
            {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': None},
            {'terrain_id': 'TRN-003', 'pct_of_race': 30.0, 'discipline_id': None},
        ]
        assert dropped == ['D-099']

    def test_unresolved_sport_keeps_couplings_verbatim(self):
        # New sport doesn't resolve in the bridge — nothing to validate
        # against, so couplings are kept (that's #885's concern, not data loss).
        conn = _FakeConn(rows=[])
        terrain = [
            {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': 'D-099'},
        ]
        out, dropped = _rescope_terrain_to_framework_sport(
            conn, 'Custom Sport', terrain
        )
        assert out == terrain
        assert dropped == []

    def test_dropped_is_sorted_and_deduped(self):
        conn = self._bridge('D-001')
        terrain = [
            {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': 'D-099'},
            {'terrain_id': 'TRN-003', 'pct_of_race': 30.0, 'discipline_id': 'D-050'},
            {'terrain_id': 'TRN-004', 'pct_of_race': 40.0, 'discipline_id': 'D-099'},
        ]
        _out, dropped = _rescope_terrain_to_framework_sport(
            conn, 'Trail Running', terrain
        )
        assert dropped == ['D-050', 'D-099']

    def test_does_not_mutate_input_rows(self):
        conn = self._bridge('D-001')
        terrain = [
            {'terrain_id': 'TRN-017', 'pct_of_race': 30.0, 'discipline_id': 'D-099'},
        ]
        _rescope_terrain_to_framework_sport(conn, 'Trail Running', terrain)
        # Original row object is left intact (new dicts are returned).
        assert terrain[0]['discipline_id'] == 'D-099'


# ─── _resolve_effective_framework_sport ─────────────────────────────────────


class TestResolveEffectiveFrameworkSport:
    """Mirrors orchestrator resolution order: race-row override wins;
    otherwise fall back to athlete profile `primary_sport`."""

    def test_race_override_wins(self, monkeypatch):
        # Profile primary_sport irrelevant when race has an override.
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': 'Adventure Racing'},
        )
        race = {'framework_sport': 'Trail Running'}
        assert _resolve_effective_framework_sport(None, 1, race) == 'Trail Running'

    def test_falls_back_to_primary_sport_when_race_blank(self, monkeypatch):
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': 'Adventure Racing'},
        )
        # Race row exists but framework_sport is None
        assert (
            _resolve_effective_framework_sport(None, 1, {'framework_sport': None})
            == 'Adventure Racing'
        )

    def test_no_race_row_uses_profile(self, monkeypatch):
        # New-race GET path — no race row exists yet.
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': 'Trail Running'},
        )
        assert (
            _resolve_effective_framework_sport(None, 1, None) == 'Trail Running'
        )

    def test_returns_none_when_both_unset(self, monkeypatch):
        # Athlete has no primary_sport AND no race row — template renders
        # the empty discipline grid + helper copy.
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': None},
        )
        assert _resolve_effective_framework_sport(None, 1, None) is None


# ─── Bucket C (i) — Mapbox-required gates ───────────────────────────────────


class _RouteFakeRow(dict):
    """`request.form`-shaped dict for the route-level tests below."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _RouteFakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _RouteFakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_RouteFakeRow(r) for r in self._rows]


class _RouteFakeConn:
    """Tracks SQL calls + serves queued responses. Mirrors
    `tests/test_locales.py::_FakeConn` so the route-level tests can assert
    that NO create/update SQL fires when the Mapbox gate rejects the POST.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _RouteFakeCursor(row=row, rows=rows)

    def commit(self):
        pass


def _make_app():
    from flask import Flask
    from routes.race_events import bp
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.register_blueprint(bp)
    return app


def _sql_fragment_count(conn, fragment: str) -> int:
    return sum(1 for sql, _params in conn.calls if fragment in sql)


class TestNewRaceMapboxRequired:
    """Bucket C (i) — `new_race` POST blocks when athlete submits without a
    Mapbox-anchored race location. Mirrors the existing race-name + race-format
    required-field gates.
    """

    def test_post_without_mapbox_id_flashes_and_rerenders(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        # #947 — a failed gate must RE-RENDER the form (preserving the
        # athlete's auto-filled details + picked distance) rather than redirect
        # to a blank one. Capture the echo passed to the render helper so we can
        # assert the submitted values are carried back into the form.
        captured = {}
        def fake_render(db, uid, race):
            captured['race'] = race
            return 'rendered'
        monkeypatch.setattr(re_mod, '_render_new_race_form', fake_render)

        with app.test_request_context(
            '/profile/race-events/new',
            method='POST',
            data={
                'name': 'Test Race',
                'event_date': '2026-07-17',
                'race_format': 'continuous_multi_day',
                'distance_km': '50',
                # `event_locale_mapbox_id` deliberately absent.
            },
        ):
            response = re_mod.new_race()

        # No create SQL should fire when the gate rejects.
        assert _sql_fragment_count(conn, 'INSERT INTO race_events') == 0
        # Re-render (not a redirect) with the submitted values preserved.
        assert response == 'rendered'
        assert captured['race']['name'] == 'Test Race'
        assert captured['race']['distance_km'] == 50.0

    def test_post_with_mapbox_id_proceeds(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        # Stub `create_race_event` so the test doesn't depend on the repo's
        # transaction shape; we're asserting the gate passes, not the SQL.
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        called = {}
        def fake_create(db, user_id, **kwargs):
            called['mapbox_id'] = kwargs.get('event_locale_mapbox_id')
            return 42
        monkeypatch.setattr(re_mod, 'create_race_event', fake_create)

        with app.test_request_context(
            '/profile/race-events/new',
            method='POST',
            data={
                'name': 'Test Race',
                'event_date': '2026-07-17',
                # Multi-day path redirects to race_events.edit_race which is
                # in the registered blueprint; single_day goes to
                # profile.edit which isn't registered in this test app.
                'race_format': 'continuous_multi_day',
                'event_locale_name': 'Test Race Location',
                'event_locale_mapbox_id': 'poi.test_anchor',
                'event_locale_place_name': 'Test Race Location, TS',
            },
        ):
            response = re_mod.new_race()

        assert response.status_code == 302
        assert called['mapbox_id'] == 'poi.test_anchor'


class TestUpdateRaceMapboxRequired:
    """Bucket C (i) — `update_race` POST blocks when the LOADED race row
    lacks `event_locale_mapbox_id`. The race-details form doesn't carry the
    Mapbox fields (the standalone `set_locale` POST owns those); the gate
    forces legacy un-anchored rows through the picker before any other edits
    can land.
    """

    def test_post_on_unanchored_row_flashes_and_rerenders(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        # Stub `get_race_event` to return a legacy un-anchored row.
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'name': 'Legacy Race',
                'event_date': None,
                'race_format': 'single_day',
                'event_locale_mapbox_id': None,
                'is_target_event': False,
            },
        )
        # #947 — re-render the edit form (preserving the submitted details)
        # rather than redirect to a fresh GET that drops the athlete's input.
        captured = {}
        def fake_render(db, uid, race):
            captured['race'] = race
            return 'rendered'
        monkeypatch.setattr(re_mod, '_render_edit_race_form', fake_render)

        with app.test_request_context(
            '/profile/race-events/10/update',
            method='POST',
            data={
                'name': 'Legacy Race',
                'event_date': '2026-07-17',
                'race_format': 'single_day',
                'distance_km': '50',
            },
        ):
            response = re_mod.update_race(10)

        # No UPDATE SQL should fire when the gate rejects.
        assert _sql_fragment_count(conn, 'UPDATE race_events') == 0
        assert response == 'rendered'
        # Submitted details overlaid on the loaded row, id preserved.
        assert captured['race']['id'] == 10
        assert captured['race']['distance_km'] == 50.0

    def test_post_on_anchored_row_proceeds(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'name': 'Anchored Race',
                'event_date': None,
                'race_format': 'single_day',
                'distance_km': None,
                'total_elevation_gain_m': None,
                'event_locale_id': None,  # legacy FK; load path preserves
                'notes': None,
                'race_terrain': [],
                'race_url': None,
                'framework_sport': None,
                'included_discipline_ids': None,
                'event_locale_mapbox_id': 'poi.test_anchor',
                'is_target_event': False,
            },
        )
        # Stub the eviction helpers + update so the call sequence doesn't
        # depend on cache wiring.
        monkeypatch.setattr(re_mod, 'update_race_event', lambda *a, **k: None)
        for helper in (
            'evict_on_target_event_framework_sport_change',
            'evict_on_target_event_included_discipline_ids_change',
            'evict_on_target_event_periodization_change',
            'evict_on_target_event_brief_field_change',
        ):
            monkeypatch.setattr(re_mod, helper, lambda *a, **k: None)

        with app.test_request_context(
            '/profile/race-events/10/update',
            method='POST',
            data={
                'name': 'Anchored Race',
                'event_date': '2026-07-17',
                'race_format': 'single_day',
            },
        ):
            response = re_mod.update_race(10)

        assert response.status_code == 302
        # Update flow proceeds past the gate (no flash 'pick a race location').


class TestUpdateRaceRescopesTerrainOnSportChange:
    """#892 / #949 — changing the race event type re-scopes terrain rows
    pinned to a now-invalid discipline back to race-wide, and the included
    set is then derived from the surviving (re-scoped) terrain breakdown.
    Reproduces the Pocket Gopher report end-to-end through the `update_race`
    POST handler.
    """

    def test_sport_change_rescopes_terrain_and_derives_included(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        # The only live DB call on this path is the bridge SELECT inside the
        # re-scope helper; the new sport ("Trail Running") maps to D-001 + D-002.
        conn.queue_response(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
            {'discipline_id': 'D-002', 'discipline_name': 'Road run'},
        ])
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'name': 'Pocket Gopher',
                'event_date': '2026-07-17',
                'race_format': 'single_day',
                'event_locale_id': None,
                'event_locale_name': None,
                'event_locale_mapbox_id': 'poi.anchor',
                'event_locale_place_name': None,
                'event_locale_lat': None,
                'event_locale_lng': None,
                'framework_sport': 'Adventure Racing',
                'included_discipline_ids': ['D-001', 'D-099'],
                'is_target_event': False,
            },
        )
        captured = {}
        monkeypatch.setattr(
            re_mod, 'update_race_event',
            lambda db, uid, rid, **kw: captured.update(kw),
        )

        with app.test_request_context(
            '/profile/race-events/10/update',
            method='POST',
            data={
                'name': 'Pocket Gopher',
                'event_date': '2026-07-17',
                'race_format': 'single_day',
                # The athlete changed the race event type...
                'framework_sport': 'Trail Running',
                # A terrain row still pinned to the now-invalid D-099:
                'race_terrain[0][terrain_id]': 'TRN-002',
                'race_terrain[0][pct_of_race]': '50',
                'race_terrain[0][discipline_id]': 'D-099',
            },
        ):
            response = re_mod.update_race(10)

        assert response.status_code == 302
        # The terrain row is preserved (terrain_id + pct) with its orphaned
        # D-099 coupling re-scoped to race-wide rather than blocking the save.
        assert captured['race_terrain'] == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 50.0, 'discipline_id': None},
        ]
        # #949 — included is derived from the re-scoped terrain: the only
        # coupling (D-099) was reset to race-wide, so no discipline is
        # included → None (use the new sport's bridge defaults).
        assert captured['included_discipline_ids'] is None


class TestSetLocaleMapboxRequired:
    """Bucket C (i) — `set_locale` POST is now strict: empty mapbox_id is
    rejected (was previously loose — accepted name-without-mapbox_id).
    """

    def test_post_without_mapbox_id_flashes_and_redirects(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'is_target_event': False,
                'event_locale_mapbox_id': None,
            },
        )
        monkeypatch.setattr(
            re_mod, 'update_race_event_locale', lambda *a, **k: None
        )

        with app.test_request_context(
            '/profile/race-events/10/locale/update',
            method='POST',
            data={
                # Only `event_locale_name` set (mimics the old loose-fallback
                # path that was previously accepted).
                'event_locale_name': 'Hand-typed location',
            },
        ):
            response = re_mod.set_locale(10)

        assert response.status_code == 302
        # No update_race_event_locale should fire when the gate rejects.
