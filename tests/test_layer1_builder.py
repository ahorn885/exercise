"""Tests for `layer1.build_layer1_payload` (Layer1_Spec.md §13).

Coverage:
- Empty user (no rows anywhere) — every sub-model None or empty default.
- Fully-populated user — every section populated; per-day windows correct;
  per-week capacity denormalized onto each day; split-by-status for injuries
  + conditions + medications.
- Sparse discipline baselines — partial coverage (3 of 7 disciplines).
- Comma-separated columns split correctly (empty / single / multi).
- Disclosure dedup — latest acknowledgment per disclosure_id surfaces only.
- Layer-4 dict round-trip — `.model_dump()` produces a dict where
  `.get("experience_level")` etc. continue to work per Layer1_Spec.md §3.

All tests use the `_FakeConn` / `_FakeCursor` pattern from
`tests/test_race_events_repo.py` — no real DB connection. The builder issues
24 SELECTs in a fixed order; tests queue 24 responses to match.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from layer1 import build_layer1_payload
from layer4.context import (
    DailyAvailabilityWindow,
    Layer1Payload,
)


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
    """Stand-in for `database._PgConn`. Each `execute()` returns a `_FakeCursor`
    from the head of `.responses` (a queue of (row, rows) tuples in the order
    the builder invokes execute).
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
        return _FakeCursor(row=row, rows=rows)


def _queue_empty_athlete(conn: _FakeConn) -> None:
    """Queue 24 empty responses — every SELECT returns no rows."""
    for _ in range(24):
        conn.queue_response()


# ─── empty user ──────────────────────────────────────────────────────────────


class TestEmptyUser:
    def test_returns_layer1_payload_with_section_defaults(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)

        payload = build_layer1_payload(conn, user_id=42)

        assert isinstance(payload, Layer1Payload)
        assert payload.user_id == 42
        assert isinstance(payload.as_of, datetime)
        # Top-level convenience fields.
        assert payload.experience_level is None
        assert payload.coaching_voice_preferences is None
        assert payload.available_days_per_week == 0
        assert payload.travel_constraint is None
        assert payload.sleep_baseline is None
        # 7 windows, all disabled, doubles_feasible defaulted to "no".
        assert len(payload.daily_availability_windows) == 7
        for w in payload.daily_availability_windows:
            assert w.enabled is False
            assert w.doubles_feasible == "no"
            assert w.preferred_rest_day is False
        # Section sub-models.
        assert payload.identity.date_of_birth is None
        assert payload.identity.primary_sport is None
        assert payload.health_status.current_injuries == []
        assert payload.health_status.injury_history == []
        assert payload.health_status.food_allergies == []
        assert payload.health_status.resting_hr_bpm is None
        assert payload.training_history.years_structured_training is None
        assert payload.training_history.secondary_sports == []
        assert payload.training_history.discipline_weighting == []
        assert payload.discipline_baselines.running is None
        assert payload.discipline_baselines.cycling is None
        assert payload.discipline_baselines.technical is None
        assert payload.strength_benchmarks is None
        assert payload.performance.hrmax_bpm is None
        assert payload.availability.long_session_available is False
        assert payload.event_goal.target_race_event_id is None
        assert payload.lifestyle.sleep_baseline_hours is None
        assert payload.network.network_links == []
        assert payload.disclosures.acknowledgments == []

    def test_24_selects_issued(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        build_layer1_payload(conn, user_id=1)
        assert len(conn.calls) == 24

    def test_user_id_required(self):
        conn = _FakeConn()
        with pytest.raises(ValueError, match="user_id required"):
            build_layer1_payload(conn, user_id=None)


# ─── fully-populated athlete ─────────────────────────────────────────────────


class TestFullyPopulated:
    def _queue_andy(self, conn: _FakeConn) -> None:
        # 1) athlete_profile
        conn.queue_response(row={
            "date_of_birth": date(1985, 6, 15),
            "sex": "male",
            "height_cm": 180.0,
            "primary_sport": "adventure_racing",
            "weekly_hours_target": 14.0,
            "notes": "PGE 2026 prep",
            "body_weight_kg": 78.5,
            "hrmax_bpm": 188,
            "lactate_threshold_hr_bpm": 168,
            "vo2max": 55.0,
            "cycling_ftp_w": 280,
            "long_session_available": True,
            "long_session_days": "sat,sun",
            "long_session_max_hr": 8,
            "doubles_feasible": "occasionally",
            "preferred_rest_days": "mon",
            "years_structured_training": 8,
            "peak_weekly_volume_hrs": 18.0,
            "peak_weekly_volume_year": 2024,
            "longest_event_completed": "Pocket Gopher Extreme 2024 finisher",
            "training_consistency_disrupted_weeks": 3,
            "training_consistency_cause": "wrist injury",
            "previous_coaching": "self",
            "running_threshold_pace_sec_per_km": 250,
            "running_threshold_test_date": date(2026, 3, 1),
            "css_swim_sec_per_100m": 105,
            "css_test_date": date(2026, 2, 15),
            "cycling_ftp_test_date": date(2026, 4, 1),
            "hrmax_source": "field_test",
            "lt_method": "field_test_30min",
            "vo2max_source": "cooper_test",
            "plan_duration_weeks_no_event": None,
            "non_event_goal_type": None,
            "work_stress_level": "moderate",
            "dietary_pattern": "omnivore,low_fodmap",
            "supplement_protocol_notes": "iron + vit D",
            "caffeine_tolerance": "high",
            "caffeine_daily_mg_estimate": 400,
            "caffeine_race_day_strategy": "maintain",
            "altitude_acclimatization_history": False,
            "altitude_max_exposure_m": 2400,
            "altitude_exposure_count": 2,
            "fueling_format_preference": "gel,bar",
            "gi_triggers_known": "high-fat solids late in long sessions",
            "salt_electrolyte_tolerance": "high",
            "sleep_deprivation_max_hrs_continuous_awake": 36,
            "sleep_deprivation_strategy_notes": "30-min naps at PGE",
        })
        # 2) body_metrics
        conn.queue_response(row={"resting_hr": 48})
        # 3) wellness_self_report
        conn.queue_response(row={"sleep_hours": 7.5})
        # 4) daily_availability_windows — sat (dow=6) + sun (dow=0) enabled
        conn.queue_response(rows=[
            {"day_of_week": 0, "window_index": 0, "enabled": True,
             "window_start": "06:00:00", "window_duration_min": 240},
            {"day_of_week": 6, "window_index": 0, "enabled": True,
             "window_start": "05:30:00", "window_duration_min": 300},
        ])
        # 5) injury_log — one active wrist, one resolved.
        # Phase 2.2 schema: severity flips int→6-enum; new columns
        # injury_type (11-enum), side (4-enum), movement_constraints (JSONB
        # multi-select). Layer 1 builder returns Optional fields so legacy
        # NULL rows still load.
        conn.queue_response(rows=[
            {"id": 1, "body_part": "left wrist", "description": "extension pain",
             "severity": "Chronic-Managed", "injury_type": "Tendinopathy / overuse",
             "side": "Left",
             "movement_constraints": ["Pain with wrist extension", "Pain with loading"],
             "status": "Active", "start_date": date(2026, 3, 1),
             "resolved_date": None, "modifications_needed": "fist pushups only"},
            {"id": 2, "body_part": "knee", "description": "patellar",
             "severity": "Resolved", "injury_type": "Tendinopathy / overuse",
             "side": "Right", "movement_constraints": [],
             "status": "Resolved", "start_date": date(2025, 9, 1),
             "resolved_date": date(2025, 12, 1), "modifications_needed": None},
        ])
        # 6) health_conditions_log
        conn.queue_response(rows=[
            {"id": 10, "system_category": "respiratory", "condition_name": "exercise-induced asthma",
             "severity": 2, "notes": None, "status": "Active",
             "start_date": date(2010, 1, 1), "resolved_date": None},
        ])
        # 7) medications_log — one active, one stopped
        conn.queue_response(rows=[
            {"id": 100, "medication_class": "stimulant_adhd", "medication_name": "Adderall XR",
             "started_at": date(2020, 5, 1), "stopped_at": None, "notes": None},
            {"id": 101, "medication_class": "nsaid_chronic", "medication_name": "ibuprofen",
             "started_at": date(2026, 3, 1), "stopped_at": date(2026, 4, 1), "notes": "wrist flare"},
        ])
        # 8) food_allergies
        conn.queue_response(rows=[
            {"id": 200, "allergen_category": "shellfish", "severity": "anaphylaxis", "notes": None},
        ])
        # 9) athlete_secondary_sports
        conn.queue_response(rows=[
            {"sport_slug": "trail_running", "experience_tier": "3plus_yr"},
            {"sport_slug": "mountain_biking", "experience_tier": "1_to_3yr"},
        ])
        # 10) athlete_discipline_weighting — sums to 100
        conn.queue_response(rows=[
            {"discipline_slug": "trail_running", "weight_pct": 40},
            {"discipline_slug": "hiking", "weight_pct": 25},
            {"discipline_slug": "mtb", "weight_pct": 20},
            {"discipline_slug": "packrafting", "weight_pct": 15},
        ])
        # 11) recent_race_results
        conn.queue_response(rows=[
            {"event_name": "PGE 2024", "event_date": date(2024, 7, 19),
             "distance_km": 180.0, "finish_time_seconds": 180000,
             "result_notes": "finisher", "source": "self_report"},
        ])
        # 12) pack_load_history
        conn.queue_response(rows=[
            {"pack_weight_kg": 8.0, "session_count_4wk": 6, "longest_session_hrs": 4.0,
             "terrain_type": "moorland", "notes": None},
        ])
        # 13) strength_benchmarks
        conn.queue_response(row={
            "front_plank_sec": 180, "dead_bug_max_reps": 20,
            "side_plank_left_sec": 90, "side_plank_right_sec": 95,
            "pushup_max_reps": 45, "bodyweight_squat_max_reps": 80,
            "single_leg_squat_left_max_reps": 12, "single_leg_squat_right_max_reps": 14,
            "pullup_max_reps": 15, "dead_hang_sec": 60,
            "grip_strength_left_kg": 48.0, "grip_strength_right_kg": 52.0,
            "last_tested_at": date(2026, 4, 1),
        })
        # 14) discipline_baseline_running
        conn.queue_response(row={
            "easy_run_pace_sec_per_km": 330, "vertical_gain_weekly_m": 800.0,
            "vertical_gain_peak_session_m": 1200.0,
            "trail_experience_terrain": "technical,mountain,moorland",
            "downhill_adaptation": True, "downhill_sessions_3mo": 8,
            "night_running": True, "gut_training_g_per_hr_cho": 80,
            "gut_training_issues": None,
        })
        # 15) discipline_baseline_cycling
        conn.queue_response(row={
            "bike_types_available": "mountain_bike,gravel_bike",
            "mtb_skill": "intermediate", "longest_ride_distance_km": 120.0,
            "longest_ride_hrs": 6.5, "saddle_endurance_hrs": 5.0,
            "aero_endurance_min": 45,
        })
        # 16) discipline_baseline_swimming — sparse (one field set)
        conn.queue_response(row={
            "pool_100m_pace_sec": 110, "ow_experience": None,
            "wetsuit_experience": None, "cold_water_experience": None,
            "ow_feeding_experience": None, "weekly_swim_volume_km": None,
        })
        # 17) discipline_baseline_paddling
        conn.queue_response(row={
            "longest_paddle_km": 30.0, "longest_paddle_hrs": 5.0,
            "paddle_craft_types": "packraft,kayak",
        })
        # 18) discipline_baseline_skiing — absent
        conn.queue_response()
        # 19) discipline_baseline_navigation
        conn.queue_response(row={
            "experience_level": "expert", "night_nav_experience": True,
        })
        # 20) discipline_baseline_technical
        conn.queue_response(row={
            "rock_climbing_outdoor_grade": "5.10a", "rock_climbing_indoor_grade": "V3",
            "abseiling_experience": True,
        })
        # 21) race_events target
        conn.queue_response(row={"id": 99})
        # 22) athlete_network_links
        conn.queue_response(rows=[
            {"id": 500, "partner_name": "Alex", "linked_account_user_id": None,
             "relationship_types": "race_teammate,training_partner",
             "partner_specific_rules": None, "race_event_id": 99,
             "discipline_focus_on_team": "navigation"},
        ])
        # 23) linked_partner_consents
        conn.queue_response(rows=[
            {"id": 600, "link_id": 500, "consent_scope": "activity_summaries",
             "granted_at": datetime(2026, 5, 1, 10, 0, 0), "revoked_at": None},
        ])
        # 24) disclosure_acknowledgments
        conn.queue_response(rows=[
            {"disclosure_id": "account_creation_ack", "version_id": "v1",
             "scopes_granted": None, "delivery_method": "in_app",
             "acknowledged_at": datetime(2026, 4, 1, 9, 0, 0)},
        ])

    def test_identity_populated(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.identity.sex == "male"
        assert payload.identity.height_cm == 180.0
        assert payload.identity.primary_sport == "adventure_racing"

    def test_health_status_split_by_status(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert len(payload.health_status.current_injuries) == 1
        assert payload.health_status.current_injuries[0].body_part == "left wrist"
        assert len(payload.health_status.injury_history) == 1
        assert payload.health_status.injury_history[0].body_part == "knee"
        assert len(payload.health_status.medications_active) == 1
        assert payload.health_status.medications_active[0].medication_class == "stimulant_adhd"
        assert len(payload.health_status.medications_history) == 1
        assert payload.health_status.food_allergies[0].severity == "anaphylaxis"
        assert payload.health_status.resting_hr_bpm == 48

    def test_training_history_weighting_sum_validates(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        total = sum(r.weight_pct for r in payload.training_history.discipline_weighting)
        assert total == 100
        assert len(payload.training_history.secondary_sports) == 2
        assert payload.training_history.previous_coaching == "self"

    def test_daily_windows_denormalize_per_week_capacity(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert len(payload.daily_availability_windows) == 7
        # Sun (dow=0) + Sat (dow=6) enabled.
        sun = payload.daily_availability_windows[0]
        sat = payload.daily_availability_windows[6]
        assert sun.day_of_week == "Sun"
        assert sun.enabled is True
        assert sun.window_start == "06:00"
        assert sun.window_duration == 240
        assert sat.day_of_week == "Sat"
        assert sat.enabled is True
        # Per-week capacity denormalized.
        for w in payload.daily_availability_windows:
            assert w.doubles_feasible == "occasionally"
            assert w.long_session_max_duration == 8
        # Preferred-rest-day on Monday only.
        mon = payload.daily_availability_windows[1]
        assert mon.day_of_week == "Mon"
        assert mon.preferred_rest_day is True
        assert sun.preferred_rest_day is False
        # available_days_per_week derived count.
        assert payload.available_days_per_week == 2

    def test_discipline_baselines_partial(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.discipline_baselines.running is not None
        assert payload.discipline_baselines.running.night_running is True
        assert "moorland" in payload.discipline_baselines.running.trail_experience_terrain
        assert payload.discipline_baselines.cycling.mtb_skill == "intermediate"
        assert payload.discipline_baselines.skiing is None  # absent
        assert payload.discipline_baselines.technical.rock_climbing_outdoor_grade == "5.10a"

    def test_event_goal_event_mode(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.event_goal.target_race_event_id == 99
        assert payload.event_goal.plan_duration_weeks_no_event is None

    def test_lifestyle_multi_select_split(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.dietary_pattern == ["omnivore", "low_fodmap"]
        assert payload.lifestyle.fueling_format_preference == ["gel", "bar"]
        assert payload.lifestyle.caffeine_tolerance == "high"

    def test_network_and_consents(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert len(payload.network.network_links) == 1
        link = payload.network.network_links[0]
        assert link.relationship_types == ["race_teammate", "training_partner"]
        assert link.race_event_id == 99
        assert len(payload.network.linked_partner_consents) == 1
        assert payload.network.linked_partner_consents[0].consent_scope == "activity_summaries"

    def test_disclosures(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert len(payload.disclosures.acknowledgments) == 1
        assert payload.disclosures.acknowledgments[0].disclosure_id == "account_creation_ack"
        assert payload.disclosures.acknowledgments[0].delivery_method == "in_app"

    def test_layer4_dict_compatibility(self):
        """`.model_dump()` produces a dict where Layer 4's `.get(...)`
        consumers continue to work (per Layer1_Spec.md §3)."""
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        dumped = payload.model_dump()
        # Layer 4 reads these keys via `.get(...)` today.
        assert "experience_level" in dumped
        assert "coaching_voice_preferences" in dumped
        assert "available_days_per_week" in dumped
        assert "travel_constraint" in dumped
        assert "sleep_baseline" in dumped
        assert "daily_availability_windows" in dumped
        assert dumped["available_days_per_week"] == 2
        assert dumped["sleep_baseline"] == 7.5
        assert len(dumped["daily_availability_windows"]) == 7

    def test_strength_benchmarks_populated(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.strength_benchmarks is not None
        assert payload.strength_benchmarks.front_plank_sec == 180
        assert payload.strength_benchmarks.last_tested_at == date(2026, 4, 1)

    def test_performance_populated(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.performance.body_weight_kg == 78.5
        assert payload.performance.cycling_ftp_w == 280
        assert payload.performance.running_threshold_pace_sec_per_km == 250


# ─── csv splitting edge cases ────────────────────────────────────────────────


class TestCsvSplitting:
    def test_empty_csv_yields_empty_list(self):
        conn = _FakeConn()
        # Profile row with various empty/whitespace csv fields.
        empty_profile = {col: None for col in _PROFILE_COL_NAMES}
        empty_profile["dietary_pattern"] = ""
        empty_profile["fueling_format_preference"] = "   "
        empty_profile["long_session_days"] = None
        empty_profile["preferred_rest_days"] = ",,,"
        conn.queue_response(row=empty_profile)
        for _ in range(23):
            conn.queue_response()

        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.dietary_pattern == []
        assert payload.lifestyle.fueling_format_preference == []
        assert payload.availability.long_session_days == []
        assert payload.availability.preferred_rest_days == []

    def test_csv_whitespace_stripped(self):
        conn = _FakeConn()
        prof = {col: None for col in _PROFILE_COL_NAMES}
        prof["dietary_pattern"] = " omnivore , gluten_free "
        conn.queue_response(row=prof)
        for _ in range(23):
            conn.queue_response()

        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.dietary_pattern == ["omnivore", "gluten_free"]


# ─── weighting sum invariant ─────────────────────────────────────────────────


class TestWeightingSumInvariant:
    def test_non_summing_weights_raise(self):
        conn = _FakeConn()
        for _ in range(9):
            conn.queue_response()
        # 10) discipline_weighting — sums to 90, should raise.
        conn.queue_response(rows=[
            {"discipline_slug": "trail_running", "weight_pct": 50},
            {"discipline_slug": "mtb", "weight_pct": 40},
        ])
        for _ in range(14):
            conn.queue_response()

        with pytest.raises(Exception, match="weight_pct must sum to 100"):
            build_layer1_payload(conn, user_id=1)

    def test_no_weighting_rows_is_valid(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.training_history.discipline_weighting == []


# Helper: full athlete_profile column list (mirrors layer1.builder._PROFILE_COLS).
_PROFILE_COL_NAMES = (
    "date_of_birth", "sex", "height_cm", "primary_sport",
    "weekly_hours_target", "notes", "body_weight_kg", "hrmax_bpm",
    "lactate_threshold_hr_bpm", "vo2max", "cycling_ftp_w",
    "long_session_available", "long_session_days", "long_session_max_hr",
    "doubles_feasible", "preferred_rest_days", "years_structured_training",
    "peak_weekly_volume_hrs", "peak_weekly_volume_year",
    "longest_event_completed", "training_consistency_disrupted_weeks",
    "training_consistency_cause", "previous_coaching",
    "running_threshold_pace_sec_per_km", "running_threshold_test_date",
    "css_swim_sec_per_100m", "css_test_date", "cycling_ftp_test_date",
    "hrmax_source", "lt_method", "vo2max_source",
    "plan_duration_weeks_no_event", "non_event_goal_type",
    "work_stress_level", "dietary_pattern", "supplement_protocol_notes",
    "caffeine_tolerance", "caffeine_daily_mg_estimate",
    "caffeine_race_day_strategy", "altitude_acclimatization_history",
    "altitude_max_exposure_m", "altitude_exposure_count",
    "fueling_format_preference", "gi_triggers_known",
    "salt_electrolyte_tolerance",
    "sleep_deprivation_max_hrs_continuous_awake",
    "sleep_deprivation_strategy_notes",
)
