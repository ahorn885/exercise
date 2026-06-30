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
26 SELECTs in a fixed order; tests queue 26 responses to match.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

# Force `layer4` to initialize before `layer1` to dodge the pre-existing
# circular import that otherwise blocks this module from collection.
# Mirrors tests/test_layer2a.py:26 + tests/test_layer2b.py:26.
from layer4 import InMemoryCacheBackend  # noqa: F401

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
    """Queue empty responses — every SELECT returns no rows.
    (D-73 Phase 5.2 Bucket C (l) added the `_load_skill_toggle_states`
    query; the dead `food_allergies` load was later removed; 2E-6 §I.1 added
    the `_load_supplements` query; #690 added the `_load_coaching_preferences`
    query; #884 slice 3b added the `_load_owned_gear` query; #304 Part B
    removed the `_load_disclosures` query from the payload build; #223 added
    the `_load_pregnancy_status` query.)"""
    for _ in range(27):
        conn.queue_response()


class _FixedClock(datetime):
    """datetime subclass with a controllable utcnow() — only utcnow is
    overridden, so combine/fromisoformat/etc. behave normally."""
    _now = datetime(2026, 5, 27, 6, 11, 31, 123456)

    @classmethod
    def utcnow(cls):
        return cls._now


class TestCacheKeyDeterminism:
    def test_as_of_day_anchored_so_layer1_hash_is_stable(self, monkeypatch):
        """Regression (D-77): `Layer1Payload.as_of` is hashed into
        `layer1_hash`, which keys EVERY Layer 4 cache entry. It must be
        day-granular so re-builds within a calendar day hash identically —
        else the cone re-runs cold on every resumable pass and a multi-pass
        plan can never converge. A microsecond `utcnow()` was the bug."""
        from layer4.hashing import compute_payload_hash

        monkeypatch.setattr("layer1.builder.datetime", _FixedClock)

        _FixedClock._now = datetime(2026, 5, 27, 6, 11, 31, 123456)
        conn1 = _FakeConn()
        _queue_empty_athlete(conn1)
        p1 = build_layer1_payload(conn1, user_id=42)
        # No sub-day precision survives into the hashed field.
        assert (
            p1.as_of.hour,
            p1.as_of.minute,
            p1.as_of.second,
            p1.as_of.microsecond,
        ) == (0, 0, 0, 0)
        h1 = compute_payload_hash(p1)

        # Same calendar day, very different wall-clock time → identical hash.
        _FixedClock._now = datetime(2026, 5, 27, 18, 45, 9, 987654)
        conn2 = _FakeConn()
        _queue_empty_athlete(conn2)
        p2 = build_layer1_payload(conn2, user_id=42)
        assert compute_payload_hash(p2) == h1


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
        assert payload.coaching_preferences == []
        assert payload.available_days_per_week == 0
        assert payload.travel_constraint is None
        assert payload.sleep_baseline is None
        # 7 windows, all disabled, doubles_feasible defaulted to "no".
        assert len(payload.daily_availability_windows) == 7
        for w in payload.daily_availability_windows:
            assert w.enabled is False
            assert w.doubles_feasible == "no"
        # Section sub-models.
        assert payload.identity.date_of_birth is None
        assert payload.identity.primary_sport is None
        assert payload.health_status.current_injuries == []
        assert payload.health_status.injury_history == []
        assert payload.health_status.resting_hr_bpm is None
        assert payload.training_history.years_structured_training is None
        assert payload.training_history.secondary_sports == []
        assert payload.training_history.discipline_weighting == []
        assert payload.discipline_baselines.running is None
        assert payload.discipline_baselines.cycling is None
        assert payload.discipline_baselines.technical is None
        assert payload.strength_benchmarks is None
        assert payload.performance.hrmax_bpm is None
        assert payload.doubles_feasible is None
        assert payload.event_goal.plan_duration_weeks_no_event is None
        assert payload.lifestyle.sleep_baseline_hours is None
        assert payload.network.network_links == []

    def test_27_selects_issued(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        build_layer1_payload(conn, user_id=1)
        # 25 → 24 after the dead `food_allergies` load was removed (the
        # skill-toggle SELECT added by D-73 Phase 5.2 Bucket C (l) stays);
        # back to 25 with the 2E-6 §I.1 `_load_supplements` SELECT. #304 swapped
        # the retired `_load_target_race_event_id` SELECT for the event-windows
        # `travel_constraint` SELECT — net-zero, 25. #690 added the
        # `_load_coaching_preferences` SELECT — 26. #884 slice 3b added the
        # `_load_owned_gear` SELECT — 27. #304 Part B dropped the
        # `_load_disclosures` SELECT (disclosures removed from the payload;
        # the `disclosure_acknowledgments` table is retained) — 26. #223 added
        # `_load_pregnancy_status` SELECT — 27.
        assert len(conn.calls) == 27

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
            "body_weight_kg": 78.5,
            "body_weight_trend": "stable",  # #257 V3-I-10
            "hrmax_bpm": 188,
            "lactate_threshold_hr_bpm": 168,
            "vo2max": 55.0,
            "cycling_ftp_w": 280,
            "doubles_feasible": "occasionally",
            "two_a_day_preference": "regularly",
            "peak_sessions_max": 12,
            "years_structured_training": 8,
            "peak_weekly_volume_hrs": 18.0,
            "peak_weekly_volume_year": 2024,
            "longest_event_completed": "Pocket Gopher Extreme 2024 finisher",
            "training_consistency_disrupted_weeks": 3,
            "training_consistency_cause": "wrist injury",
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
            "sweat_rate_level": "high",  # #257 V3-I-4
            "daily_hydration_baseline": "moderate",  # #257 V3-I-9
            "sleep_deprivation_max_hrs_continuous_awake": 36,
            "sleep_deprivation_strategy_notes": "30-min naps at PGE",
            "sleep_consistency": "mostly_consistent",  # #257 V3-I-1
            "experience_level": "advanced",
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
             "movement_constraints": ["Pain above specific joint angle", "Pain with loading"],
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
        # 8) athlete_secondary_sports
        conn.queue_response(rows=[
            {"sport_slug": "trail_running", "experience_tier": "3plus_yr"},
            {"sport_slug": "mountain_biking", "experience_tier": "1_to_3yr"},
        ])
        # 9) athlete_discipline_weighting — sums to 100
        conn.queue_response(rows=[
            {"discipline_slug": "trail_running", "weight_pct": 40},
            {"discipline_slug": "hiking", "weight_pct": 25},
            {"discipline_slug": "mtb", "weight_pct": 20},
            {"discipline_slug": "packrafting", "weight_pct": 15},
        ])
        # 10) recent_race_results
        conn.queue_response(rows=[
            {"event_name": "PGE 2024", "event_date": date(2024, 7, 19),
             "distance_km": 180.0, "finish_time_seconds": 180000,
             "result_notes": "finisher", "source": "self_report"},
        ])
        # 11) pack_load_history
        conn.queue_response(rows=[
            {"pack_weight_kg": 8.0, "session_count_4wk": 6, "longest_session_hrs": 4.0,
             "terrain_type": "moorland", "notes": None},
        ])
        # 12) strength_benchmarks
        conn.queue_response(row={
            "front_plank_sec": 180, "dead_bug_max_reps": 20,
            "side_plank_left_sec": 90, "side_plank_right_sec": 95,
            "pushup_max_reps": 45, "bodyweight_squat_max_reps": 80,
            "single_leg_squat_left_max_reps": 12, "single_leg_squat_right_max_reps": 14,
            "pullup_max_reps": 15, "dead_hang_sec": 60,
            "grip_strength_left_kg": 48.0, "grip_strength_right_kg": 52.0,
            "last_tested_at": date(2026, 4, 1),
        })
        # 13) discipline_baseline_running
        conn.queue_response(row={
            "easy_run_pace_sec_per_km": 330, "vertical_gain_weekly_m": 800.0,
            "vertical_gain_peak_session_m": 1200.0,
            "trail_experience_terrain": "technical,mountain,moorland",
            "downhill_adaptation": True, "downhill_sessions_3mo": 8,
            "night_running": True, "gut_training_g_per_hr_cho": 80,
            "gut_training_issues": None,
        })
        # 14) discipline_baseline_cycling
        conn.queue_response(row={
            "bike_types_available": "mountain_bike,gravel_bike",
            "mtb_skill": "intermediate", "longest_ride_distance_km": 120.0,
            "longest_ride_hrs": 6.5, "saddle_endurance_hrs": 5.0,
            "aero_endurance_min": 45,
        })
        # 15) discipline_baseline_swimming — sparse (one field set)
        conn.queue_response(row={
            "pool_100m_pace_sec": 110, "ow_experience": None,
            "wetsuit_experience": None, "cold_water_experience": None,
            "ow_feeding_experience": None, "weekly_swim_volume_km": None,
        })
        # 16) discipline_baseline_paddling
        conn.queue_response(row={
            "longest_paddle_km": 30.0, "longest_paddle_hrs": 5.0,
            "paddle_craft_types": "packraft,kayak",
        })
        # 17) discipline_baseline_skiing — absent
        conn.queue_response()
        # 18) discipline_baseline_navigation
        conn.queue_response(row={
            "experience_level": "expert", "night_nav_experience": True,
        })
        # 19) discipline_baseline_technical
        conn.queue_response(row={
            "rock_climbing_outdoor_grade": "5.10a", "rock_climbing_indoor_grade": "V3",
            "abseiling_experience": True,
        })
        # 20) athlete_network_links
        conn.queue_response(rows=[
            {"id": 500, "partner_name": "Alex", "linked_account_user_id": None,
             "relationship_types": "race_teammate,training_partner",
             "partner_specific_rules": None, "race_event_id": 99,
             "discipline_focus_on_team": "navigation"},
        ])
        # 21) linked_partner_consents
        conn.queue_response(rows=[
            {"id": 600, "link_id": 500, "consent_scope": "activity_summaries",
             "granted_at": datetime(2026, 5, 1, 10, 0, 0), "revoked_at": None},
        ])
        # 22) athlete_skill_toggles — D-73 Phase 5.2 Bucket C (l). Andy
        # has the climbing_roped + whitewater_handling toggles enabled
        # (PGE 2026 athlete with real AR experience), the rest implicit
        # OFF since they're not in the athlete_skill_toggles table.
        conn.queue_response(rows=[
            {"toggle_name": "climbing_roped", "enabled": True},
            {"toggle_name": "whitewater_handling", "enabled": True},
        ])
        # 23b) athlete_gear — #884 slice 3b owned gear/craft store, read by
        # _load_owned_gear into Layer1Payload.owned_gear (the cardio-drill gear
        # gate + slice-4 cascade consume it). Andy's backfilled crafts.
        conn.queue_response(rows=[
            {"gear_id": "gravel_bike", "group_kind": "bike", "access": "own"},
            {"gear_id": "kayak", "group_kind": "paddle", "access": "own"},
        ])
        # 24) athlete_supplements — 2E-6 §I.1 structured protocol. Two records;
        # frequency/timing are closed-vocab tokens, dose/notes free text.
        conn.queue_response(rows=[
            {"supplement_id": "creatine_monohydrate",
             "canonical_name": "Creatine monohydrate", "category": "Performance",
             "dose": "5 g", "frequency": "daily", "timing": "post_exercise",
             "notes": "micronized"},
            {"supplement_id": "electrolyte_mix",
             "canonical_name": "Electrolyte mix", "category": "Race-day",
             "dose": "1 scoop", "frequency": "as_needed",
             "timing": "during_exercise", "notes": None},
        ])
        # 25) athlete_event_windows — #304 travel_constraint source. One 'away'
        # window with brought gear + one 'indoor_only' window.
        conn.queue_response(rows=[
            {"id": 1, "user_id": 1, "start_date": date(2026, 7, 1),
             "end_date": date(2026, 7, 5), "override_type": "away",
             "unavailable_locale": None, "away_locale": "Moab",
             "brought_gear": "gravel_bike", "volume_pct": None,
             "volume_by_date": None, "notes": "training camp"},
            {"id": 2, "user_id": 1, "start_date": date(2026, 7, 10),
             "end_date": date(2026, 7, 12), "override_type": "indoor_only",
             "unavailable_locale": None, "away_locale": None,
             "brought_gear": "", "volume_pct": None, "volume_by_date": None,
             "notes": ""},
        ])
        # 26) coaching_preferences — #690 Coaching Memory. One permanent
        # high-variety pref + one advisory avoid note; ordered created_at ASC.
        conn.queue_response(rows=[
            {"category": "training",
             "content": "Wants high exercise variety; dislikes repeating the "
                        "same strength sessions.",
             "permanent": 1},
            {"category": "avoid_exercise",
             "content": "No overhead pressing for now.",
             "permanent": 0},
        ])
        # 27) health_screening — #223 pregnancy flag. Andy has no PREGNANCY flag.
        conn.queue_response(row={"flags": []})

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
        assert payload.health_status.resting_hr_bpm == 48

    def test_training_history_weighting_sum_validates(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        total = sum(r.weight_pct for r in payload.training_history.discipline_weighting)
        assert total == 100
        assert len(payload.training_history.secondary_sports) == 2

    def test_daily_windows_denormalize_doubles_and_infer_rest(self):
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
        # doubles_feasible denormalized onto every day.
        for w in payload.daily_availability_windows:
            assert w.doubles_feasible == "occasionally"
        # Rest days are inferred from the disabled days (FormRefresh Slice C):
        # Monday is not in the enabled set, so it's a rest day.
        mon = payload.daily_availability_windows[1]
        assert mon.day_of_week == "Mon"
        assert mon.enabled is False
        # available_days_per_week derived count.
        assert payload.available_days_per_week == 2
        # Slice 2b.2b — the §G session-ceiling scalars round-trip from
        # athlete_profile onto top-level Layer1Payload fields (read by per_phase).
        assert payload.two_a_day_preference == "regularly"
        assert payload.peak_sessions_max == 12

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
        # Event mode → the no-event plan-duration field stays None (the target
        # race is threaded via RaceEventPayload, not off event_goal — #304).
        assert payload.event_goal.plan_duration_weeks_no_event is None

    def test_convenience_fields_threaded(self):
        # #304 — experience_level round-trips from athlete_profile;
        # travel_constraint is summarized from event windows. (#954 — the
        # free-text coach_notes field was retired into coaching_preferences.)
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.experience_level == "advanced"
        assert payload.travel_constraint is not None
        assert "2026-07-01–2026-07-05: training at Moab" in payload.travel_constraint
        assert "brings gravel_bike" in payload.travel_constraint
        assert "training camp" in payload.travel_constraint
        assert "2026-07-10–2026-07-12: indoor only" in payload.travel_constraint

    def test_coaching_preferences_thread_through(self):
        # #690 — durable Coaching Memory rows surface as typed
        # Layer1CoachingPreference (int `permanent` normalized to bool),
        # ordered created_at ASC, so the synthesizer can honor a high-variety
        # request + avoid/prefer notes.
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert len(payload.coaching_preferences) == 2
        first = payload.coaching_preferences[0]
        assert first.category == "training"
        assert first.permanent is True
        assert "high exercise variety" in first.content
        assert payload.coaching_preferences[1].permanent is False

    def test_lifestyle_multi_select_split(self):
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.dietary_pattern == ["omnivore", "low_fodmap"]
        assert payload.lifestyle.fueling_format_preference == ["gel", "bar"]
        assert payload.lifestyle.caffeine_tolerance == "high"

    def test_v3_profile_fields_thread_through(self):
        # #257 — sleep consistency (V3-I-1), sweat rate (V3-I-4, split from
        # salt loss), daily hydration (V3-I-9), and body-weight trend (V3-I-10)
        # reach the Layer-1 payload; salt stays distinct from sweat.
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.salt_electrolyte_tolerance == "high"
        assert payload.lifestyle.sweat_rate_level == "high"
        assert payload.lifestyle.daily_hydration_baseline == "moderate"
        assert payload.lifestyle.sleep_consistency == "mostly_consistent"
        assert payload.performance.body_weight_trend == "stable"

    def test_v3_profile_fields_default_none_when_absent(self):
        # Empty athlete → every new #257 field is None (no spurious default).
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.sweat_rate_level is None
        assert payload.lifestyle.daily_hydration_baseline is None
        assert payload.lifestyle.sleep_consistency is None
        assert payload.performance.body_weight_trend is None

    def test_supplements_structured_records_thread_through(self):
        # 2E-6 §I.1 — athlete_supplements rows surface as structured
        # AthleteSupplementRecord on lifestyle.supplements (the shape Layer 2E
        # §5.5 consumes), preserving order + the closed-vocab frequency/timing.
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        supps = payload.lifestyle.supplements
        assert [s.supplement_id for s in supps] == [
            "creatine_monohydrate", "electrolyte_mix"]
        creatine = supps[0]
        assert creatine.canonical_name == "Creatine monohydrate"
        assert creatine.category == "Performance"
        assert creatine.dose == "5 g"
        assert creatine.frequency == "daily"
        assert creatine.timing == "post_exercise"
        assert creatine.notes == "micronized"
        # Optional fields tolerate NULL (electrolyte mix has no notes).
        assert supps[1].notes is None

    def test_empty_athlete_has_no_supplements(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.supplements == []

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

    def test_disclosures_dropped_from_payload(self):
        # #304 Part B — `disclosures` was loaded-but-unused; removed from the
        # Layer-1 payload (the `disclosure_acknowledgments` table is retained as
        # the legal consent record, still written by the route handlers). The
        # payload model no longer carries the field and the build issues no
        # disclosures SELECT.
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert not hasattr(payload, "disclosures")
        assert "disclosures" not in payload.model_dump()

    def test_layer4_dict_compatibility(self):
        """`.model_dump()` produces a dict where Layer 4's `.get(...)`
        consumers continue to work (per Layer1_Spec.md §3)."""
        conn = _FakeConn()
        self._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        dumped = payload.model_dump()
        # Layer 4 reads these keys via `.get(...)` today.
        assert "experience_level" in dumped
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


# ─── D-73 Phase 5.2 Bucket C (l) — athlete_skill_toggles loader ──────────────


class TestSkillToggleStates:
    """`_load_skill_toggle_states` reads athlete_skill_toggles and threads
    the per-toggle bool dict into Layer1Lifestyle.skill_toggle_states.
    Absent rows mean OFF (the table only stores explicit picks)."""

    def test_empty_athlete_yields_empty_dict(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        payload = build_layer1_payload(conn, user_id=42)
        assert payload.lifestyle.skill_toggle_states == {}

    def test_populated_toggles_thread_through(self):
        """Andy's _queue_andy populates climbing_roped + whitewater_handling
        as True; the rest stay absent (= OFF)."""
        conn = _FakeConn()
        TestFullyPopulated()._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.skill_toggle_states == {
            "climbing_roped": True,
            "whitewater_handling": True,
        }


# ─── #884 slice 3b — athlete_gear loader (owned_gear) ────────────────────────


class TestOwnedGear:
    """`_load_owned_gear` reads athlete_gear and threads the sorted gear_id list
    into Layer1Payload.owned_gear (the cardio-drill gear gate + slice-4 cascade
    consume it). Empty on athletes with no captured/backfilled gear."""

    def test_empty_athlete_yields_empty_list(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        payload = build_layer1_payload(conn, user_id=42)
        assert payload.owned_gear == []

    def test_populated_gear_threads_through_sorted(self):
        conn = _FakeConn()
        TestFullyPopulated()._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        # _queue_andy seeds gravel_bike + kayak; sorted for a stable hash.
        assert payload.owned_gear == ["gravel_bike", "kayak"]

    def test_explicit_off_rows_preserved(self):
        """An athlete who toggled ON then toggled OFF surfaces as
        {toggle_name: False} — distinguishable from never-touched
        (absent from dict) at the consumer if it cares. Layer 2B/2C
        currently treat both as OFF so the semantics collapse."""
        conn = _FakeConn()
        # Queue 21 empty + 1 populated for the toggle SELECT (#22 of 27 after
        # #223 added the _load_pregnancy_status SELECT); gear + supplements +
        # event-windows + coaching_preferences + health_screening trail it and
        # read empty from the fallback.
        for _ in range(21):
            conn.queue_response()
        conn.queue_response(rows=[
            {"toggle_name": "climbing_roped", "enabled": False},
            {"toggle_name": "via_ferrata", "enabled": False},
        ])
        payload = build_layer1_payload(conn, user_id=7)
        assert payload.lifestyle.skill_toggle_states == {
            "climbing_roped": False,
            "via_ferrata": False,
        }


# ─── csv splitting edge cases ────────────────────────────────────────────────


class TestCsvSplitting:
    def test_empty_csv_yields_empty_list(self):
        conn = _FakeConn()
        # Profile row with various empty/whitespace csv fields.
        empty_profile = {col: None for col in _PROFILE_COL_NAMES}
        empty_profile["dietary_pattern"] = ""
        empty_profile["fueling_format_preference"] = "   "
        conn.queue_response(row=empty_profile)
        for _ in range(23):
            conn.queue_response()

        payload = build_layer1_payload(conn, user_id=1)
        assert payload.lifestyle.dietary_pattern == []
        assert payload.lifestyle.fueling_format_preference == []

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
        for _ in range(8):
            conn.queue_response()
        # 9) discipline_weighting — sums to 90, should raise.
        conn.queue_response(rows=[
            {"discipline_slug": "trail_running", "weight_pct": 50},
            {"discipline_slug": "mtb", "weight_pct": 40},
        ])
        for _ in range(15):
            conn.queue_response()

        with pytest.raises(Exception, match="weight_pct must sum to 100"):
            build_layer1_payload(conn, user_id=1)

    def test_no_weighting_rows_is_valid(self):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.training_history.discipline_weighting == []


# ─── #223 pregnancy status ───────────────────────────────────────────────────


class TestPregnancyStatus:
    """_load_pregnancy_status reads health_screening.flags (SELECT #27)."""

    def _build(self, flags_row=None):
        conn = _FakeConn()
        _queue_empty_athlete(conn)
        if flags_row is not None:
            conn.responses[-1] = (flags_row, [])
        return build_layer1_payload(conn, user_id=1)

    def test_no_screening_row_returns_none(self):
        payload = self._build()
        assert payload.health_status.pregnancy_status is None

    def test_empty_flags_returns_false(self):
        payload = self._build({"flags": []})
        assert payload.health_status.pregnancy_status is False

    def test_pregnancy_flag_returns_true(self):
        payload = self._build({"flags": ["PREGNANCY"]})
        assert payload.health_status.pregnancy_status is True

    def test_pregnancy_flag_among_others_returns_true(self):
        payload = self._build({"flags": ["CARDIO_CHEST_PAIN", "PREGNANCY"]})
        assert payload.health_status.pregnancy_status is True

    def test_other_flags_only_returns_false(self):
        payload = self._build({"flags": ["CARDIO_CONDITION", "MSK_CONDITION"]})
        assert payload.health_status.pregnancy_status is False

    def test_andy_fixture_has_no_pregnancy_flag(self):
        conn = _FakeConn()
        TestFullyPopulated()._queue_andy(conn)
        payload = build_layer1_payload(conn, user_id=1)
        assert payload.health_status.pregnancy_status is False


# Helper: full athlete_profile column list (mirrors layer1.builder._PROFILE_COLS).
_PROFILE_COL_NAMES = (
    "date_of_birth", "sex", "height_cm", "primary_sport",
    "weekly_hours_target", "body_weight_kg", "body_weight_trend", "hrmax_bpm",
    "lactate_threshold_hr_bpm", "vo2max", "cycling_ftp_w",
    "doubles_feasible", "two_a_day_preference", "peak_sessions_max",
    "years_structured_training",
    "peak_weekly_volume_hrs", "peak_weekly_volume_year",
    "longest_event_completed", "training_consistency_disrupted_weeks",
    "training_consistency_cause",
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
    "sweat_rate_level", "daily_hydration_baseline",
    "sleep_deprivation_max_hrs_continuous_awake",
    "sleep_deprivation_strategy_notes",
    "sleep_consistency",
    "experience_level",
)
