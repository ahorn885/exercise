"""Tests for `routes/ad_hoc_workouts.py` D-63 caller-side helpers.

Exercises the inline helpers (`_athlete_sport_choices`,
`_allocate_suggestion`, `_persist_generated_session`, `_get_suggestion`,
`_mark_status`, `_decode_jsonb`, `_parse_request_form`) directly via
`_FakeConn` — same precedent as `tests/test_onboarding_race_events.py`
+ `tests/test_race_events_repo.py`. End-to-end Flask test-client
walkthrough is captured in the §5.0 manual verification steps rather
than pytest fixtures (matches every existing route module's test
pattern).
"""

from __future__ import annotations

import json

import pytest

from routes.ad_hoc_workouts import (
    VALID_INTENSITIES,
    _allocate_suggestion,
    _athlete_sport_choices,
    _decode_jsonb,
    _get_suggestion,
    _mark_status,
    _orchestration_error_message,
    _parse_request_form,
    _persist_generated_session,
)
from layer4 import OrchestrationError


# ─── Shared fake conn ───────────────────────────────────────────────────────


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
        self.commits: int = 0
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        self.commits += 1


# ─── _athlete_sport_choices ─────────────────────────────────────────────────


class TestAthleteSportChoices:
    def test_returns_sorted_distinct_framework_sports(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'framework_sport': 'Running'},
            {'framework_sport': 'Cycling'},
            {'framework_sport': 'Adventure Racing'},
        ])
        result = _athlete_sport_choices(conn)
        # Repo trusts the SQL ORDER BY; just confirm pass-through.
        assert result == ['Running', 'Cycling', 'Adventure Racing']
        assert 'SELECT DISTINCT framework_sport' in conn.calls[0][0]
        assert 'layer0.sports' in conn.calls[0][0]
        assert 'superseded_at IS NULL' in conn.calls[0][0]

    def test_filters_empty_framework_sport_values(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'framework_sport': 'Running'},
            {'framework_sport': ''},
            {'framework_sport': None},
        ])
        assert _athlete_sport_choices(conn) == ['Running']

    def test_empty_rows_returns_empty_list(self):
        conn = _FakeConn()
        assert _athlete_sport_choices(conn) == []


# ─── _allocate_suggestion ───────────────────────────────────────────────────


class TestAllocateSuggestion:
    def test_returns_new_id(self):
        conn = _FakeConn()
        conn.queue_response(row={'id': 42})
        request_payload = {
            'sport': 'Running', 'duration_min': 60,
            'intensity': 'hard', 'locale_slug': 'home',
            'quick_equipment': [], 'notes_for_synthesizer': None,
        }
        result = _allocate_suggestion(conn, user_id=7, request_payload=request_payload)
        assert result == 42
        assert 'INSERT INTO ad_hoc_workout_suggestions' in conn.calls[0][0]
        assert 'RETURNING id' in conn.calls[0][0]
        # request_payload is JSON-encoded so JSONB accepts it.
        params = conn.calls[0][1]
        assert params[0] == 7
        assert json.loads(params[1]) == request_payload

    def test_raises_runtimeerror_when_no_returning_row(self):
        conn = _FakeConn()  # no response queued → fetchone returns None
        with pytest.raises(RuntimeError, match='returned no row'):
            _allocate_suggestion(conn, user_id=7, request_payload={})

    def test_does_not_commit(self):
        conn = _FakeConn()
        conn.queue_response(row={'id': 1})
        _allocate_suggestion(conn, user_id=7, request_payload={})
        assert conn.commits == 0  # caller owns the transaction


# ─── _persist_generated_session ─────────────────────────────────────────────


class TestPersistGeneratedSession:
    def test_updates_generated_session_column(self):
        conn = _FakeConn()
        _persist_generated_session(conn, suggestion_id=42, session_json='{"k":"v"}')
        sql, params = conn.calls[0]
        assert 'UPDATE ad_hoc_workout_suggestions' in sql
        assert 'SET generated_session' in sql
        assert params == ('{"k":"v"}', 42)
        assert conn.commits == 0  # caller owns commit


# ─── _get_suggestion ────────────────────────────────────────────────────────


class TestGetSuggestion:
    def test_returns_dict_on_hit(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 5,
            'user_id': 7,
            'requested_at': 'ts',
            'request_payload': {'sport': 'Running'},
            'generated_session': {'session_id': 'abc'},
            'status': 'suggested',
            'regenerated_into_id': None,
        })
        result = _get_suggestion(conn, user_id=7, suggestion_id=5)
        assert result is not None
        assert result['id'] == 5
        assert result['user_id'] == 7
        assert result['request_payload'] == {'sport': 'Running'}
        assert result['generated_session'] == {'session_id': 'abc'}
        assert result['status'] == 'suggested'
        assert result['regenerated_into_id'] is None
        # Scoped by user_id in the WHERE clause.
        sql, params = conn.calls[0]
        assert 'WHERE id = ? AND user_id = ?' in sql
        assert params == (5, 7)

    def test_returns_none_on_miss(self):
        conn = _FakeConn()
        assert _get_suggestion(conn, user_id=7, suggestion_id=999) is None

    def test_hydrates_jsonb_string_path(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 5, 'user_id': 7, 'requested_at': 'ts',
            'request_payload': '{"sport": "Running"}',  # SQLite-shim path
            'generated_session': '{"session_id": "abc"}',
            'status': 'suggested',
            'regenerated_into_id': None,
        })
        result = _get_suggestion(conn, 7, 5)
        assert result['request_payload'] == {'sport': 'Running'}
        assert result['generated_session'] == {'session_id': 'abc'}

    def test_generated_session_none_when_not_yet_persisted(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 5, 'user_id': 7, 'requested_at': 'ts',
            'request_payload': {'sport': 'Running'},
            'generated_session': None,
            'status': 'suggested',
            'regenerated_into_id': None,
        })
        assert _get_suggestion(conn, 7, 5)['generated_session'] is None


# ─── _mark_status ───────────────────────────────────────────────────────────


class TestMarkStatus:
    def test_discarded_sets_status_and_discarded_at(self):
        conn = _FakeConn()
        _mark_status(conn, suggestion_id=5, user_id=7, status='discarded')
        sql, params = conn.calls[0]
        assert 'status = ?' in sql
        assert 'discarded_at = NOW()' in sql
        assert params == ('discarded', 5, 7)
        assert conn.commits == 0  # caller owns commit

    def test_regenerated_sets_status_and_link(self):
        conn = _FakeConn()
        _mark_status(
            conn, suggestion_id=5, user_id=7,
            status='regenerated', regenerated_into_id=11,
        )
        sql, params = conn.calls[0]
        assert 'regenerated_into_id = ?' in sql
        assert params == ('regenerated', 11, 5, 7)

    def test_rejects_unsupported_status(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match='only handles discarded/regenerated'):
            _mark_status(conn, suggestion_id=5, user_id=7, status='logged')


# ─── _decode_jsonb ──────────────────────────────────────────────────────────


class TestDecodeJsonb:
    def test_none_passes_through(self):
        assert _decode_jsonb(None) is None

    def test_dict_passes_through(self):
        assert _decode_jsonb({'k': 'v'}) == {'k': 'v'}

    def test_list_passes_through(self):
        assert _decode_jsonb([1, 2, 3]) == [1, 2, 3]

    def test_string_parsed_as_json(self):
        assert _decode_jsonb('{"k": "v"}') == {'k': 'v'}

    def test_unexpected_type_raises(self):
        with pytest.raises(TypeError):
            _decode_jsonb(42)


# ─── _parse_request_form ────────────────────────────────────────────────────


class TestParseRequestForm:
    def _valid_form(self, **overrides):
        form = {
            'sport': 'Running',
            'duration_min': '60',
            'intensity': 'hard',
            'locale_slug': 'home',
            'notes_for_synthesizer': '',
        }
        form.update(overrides)
        return form

    def test_happy_path(self):
        req, err = _parse_request_form(self._valid_form())
        assert err is None
        assert req is not None
        assert req.sport == 'Running'
        assert req.duration_min == 60
        assert req.intensity == 'hard'
        assert req.locale_slug == 'home'
        assert req.notes_for_synthesizer is None  # empty → None
        assert req.quick_equipment == []  # XOR satisfied by locale_slug

    def test_notes_preserved_when_set(self):
        req, err = _parse_request_form(
            self._valid_form(notes_for_synthesizer='focus on hill climbs')
        )
        assert err is None
        assert req.notes_for_synthesizer == 'focus on hill climbs'

    def test_missing_sport_rejected(self):
        _, err = _parse_request_form(self._valid_form(sport=''))
        assert err is not None
        assert 'sport' in err.lower()

    def test_missing_locale_rejected(self):
        _, err = _parse_request_form(self._valid_form(locale_slug=''))
        assert err is not None
        assert 'location' in err.lower()

    def test_invalid_intensity_rejected(self):
        _, err = _parse_request_form(self._valid_form(intensity='unknown'))
        assert err is not None
        assert 'intensity' in err.lower()

    def test_non_int_duration_rejected(self):
        _, err = _parse_request_form(self._valid_form(duration_min='abc'))
        assert err is not None
        assert 'duration' in err.lower()

    def test_out_of_range_duration_rejected_by_pydantic(self):
        _, err = _parse_request_form(self._valid_form(duration_min='10'))
        assert err is not None
        assert 'invalid request' in err.lower() or '30' in err

    def test_valid_intensities_constant(self):
        assert set(VALID_INTENSITIES) == {'easy', 'moderate', 'hard', 'race_pace'}


# ─── _orchestration_error_message ───────────────────────────────────────────


class TestOrchestrationErrorMessage:
    def test_known_codes_have_messages(self):
        for code in (
            'request_sport_unavailable',
            'locale_unknown',
            'etl_version_set_undiscoverable',
            'framework_sport_missing',
        ):
            msg = _orchestration_error_message(OrchestrationError(code))
            assert msg
            assert 'failed' in msg.lower() or 'pick' in msg.lower() or 'set' in msg.lower() or 'unavailable' in msg.lower() or 'try' in msg.lower() or 'platform' in msg.lower()

    def test_unknown_code_falls_back_to_generic(self):
        msg = _orchestration_error_message(OrchestrationError('some_new_code'))
        assert 'some_new_code' in msg
