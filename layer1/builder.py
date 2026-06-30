"""Layer 1 builder — reads D-51 storage and assembles a typed `Layer1Payload`.

Per `Layer1_Spec.md` §3 (function signature) + §5 (algorithm). All reads are
keyed on `user_id`; missing 1:1 sub-table rows surface as `None` on the
corresponding section sub-model; missing multi-row companions surface as
empty lists.

The builder issues one SELECT per source table (24 total). Order is fixed
so `tests/test_layer1_builder.py` can queue `_FakeConn` responses
deterministically. No JOINs across sub-tables — each SELECT is independent
and sparse-friendly.

Schema reference: `Layer1_D51_Design_v1.md` §3 + `init_db.py` _PG_MIGRATIONS
1.2A/1.2B/1.2C blocks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from athlete_event_windows_repo import load_event_windows
from layer4.context import (
    AthleteNetworkLink,
    AthleteSupplementRecord,
    CyclingBaseline,
    DailyAvailabilityWindow,
    DisclosureAck,
    DisciplineWeightRecord,
    HealthConditionRecord,
    InjuryRecord,
    Layer1CoachingPreference,
    Layer1Disclosures,
    Layer1DisciplineBaselines,
    Layer1EventGoal,
    Layer1HealthStatus,
    Layer1Identity,
    Layer1Lifestyle,
    Layer1Network,
    Layer1Payload,
    Layer1Performance,
    Layer1StrengthBenchmarks,
    Layer1TrainingHistory,
    LinkedPartnerConsent,
    MedicationRecord,
    NavigationBaseline,
    PackLoadRecord,
    PaddlingBaseline,
    RecentRaceResult,
    RunningBaseline,
    SecondarySportRecord,
    SkiingBaseline,
    SwimmingBaseline,
    TechnicalBaseline,
)


# Sunday=0 per Layer1_D51_Design_v1.md §6 #1 (Andy 2026-05-19 — matches v5 §G.1
# storage convention + athlete.DAY_TOKENS).
_DAY_LABELS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [tok.strip() for tok in value.split(",") if tok.strip()]


def _format_time(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    if isinstance(value, str) and len(value) >= 5:
        return value[:5]
    return str(value)


def build_layer1_payload(db, user_id: int) -> Layer1Payload:
    """Assemble a `Layer1Payload` for `user_id` from the D-51 storage tables.

    Returns a fully-typed payload. Missing 1:1 sub-table rows surface as
    `None` on the corresponding section sub-model; missing multi-row
    companions surface as empty lists. The top-level convenience fields
    (`available_days_per_week`, `sleep_baseline`, `daily_availability_windows`)
    are derived from the sub-model contents so `.model_dump()` produces a
    dict the Layer 4 `.get(...)` consumers can read transparently.

    Caller is responsible for authorizing the read (`user_id` not validated
    against the active session here).
    """
    if user_id is None:
        raise ValueError("user_id required")

    (identity, performance, training_scalars, event_scalars, lifestyle,
     availability_scalars, convenience) = _load_athlete_profile(db, user_id)
    resting_hr_bpm = _load_resting_hr(db, user_id)
    sleep_baseline_hours = _load_sleep_baseline(db, user_id)
    daily_windows = _load_daily_windows(db, user_id, availability_scalars)
    current_injuries, injury_history = _load_injuries(db, user_id)
    conditions_active, conditions_history = _load_health_conditions(db, user_id)
    medications_active, medications_history = _load_medications(db, user_id)
    secondary_sports = _load_secondary_sports(db, user_id)
    discipline_weighting = _load_discipline_weighting(db, user_id)
    recent_race_results = _load_recent_race_results(db, user_id)
    pack_load_history = _load_pack_load_history(db, user_id)
    strength_benchmarks = _load_strength_benchmarks(db, user_id)
    discipline_baselines = _load_discipline_baselines(db, user_id)
    network_links = _load_network_links(db, user_id)
    linked_partner_consents = _load_linked_partner_consents(db, user_id)
    disclosures = _load_disclosures(db, user_id)
    skill_toggle_states = _load_skill_toggle_states(db, user_id)
    owned_gear = _load_owned_gear(db, user_id)
    supplements = _load_supplements(db, user_id)
    travel_constraint = _summarize_travel_constraint(db, user_id)
    coaching_preferences = _load_coaching_preferences(db, user_id)

    health_status = Layer1HealthStatus(
        current_injuries=current_injuries,
        injury_history=injury_history,
        health_conditions_active=conditions_active,
        health_conditions_history=conditions_history,
        medications_active=medications_active,
        medications_history=medications_history,
        resting_hr_bpm=resting_hr_bpm,
    )
    training_history = Layer1TrainingHistory(
        **training_scalars,
        secondary_sports=secondary_sports,
        discipline_weighting=discipline_weighting,
        recent_race_results=recent_race_results,
        pack_load_history=pack_load_history,
    )
    event_goal = Layer1EventGoal(**event_scalars)
    lifestyle_model = Layer1Lifestyle(
        sleep_baseline_hours=sleep_baseline_hours,
        skill_toggle_states=skill_toggle_states,
        supplements=supplements,
        **lifestyle,
    )
    network = Layer1Network(
        network_links=network_links,
        linked_partner_consents=linked_partner_consents,
    )
    disclosures_model = Layer1Disclosures(acknowledgments=disclosures)

    available_days_per_week = sum(1 for w in daily_windows if w.enabled)

    return Layer1Payload(
        user_id=user_id,
        # Day-anchored, NOT full-precision: `as_of` is hashed into `layer1_hash`,
        # which keys EVERY Layer 4 cache entry (3A/3B + every per-block synthesis
        # row, across plan_create / plan_refresh / single_session / brief). A
        # microsecond `utcnow()` made those keys non-deterministic across
        # function invocations, so the cone re-ran cold on every resumable pass
        # and a multi-pass plan could never converge (D-77 stall). Day-granular
        # matches the Layer 3A `as_of` cache semantics (re-runs the same calendar
        # day hit the same entry).
        as_of=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
        # Layer-4-consumed convenience fields.
        experience_level=convenience["experience_level"],
        coaching_preferences=coaching_preferences,
        available_days_per_week=available_days_per_week,
        travel_constraint=travel_constraint,
        sleep_baseline=sleep_baseline_hours,
        daily_availability_windows=daily_windows,
        owned_gear=owned_gear,
        # §G per-week capacity scalars (promoted from the retired
        # Layer1Availability wrapper) — read top-level by the session grid.
        doubles_feasible=availability_scalars["doubles_feasible"],
        two_a_day_preference=availability_scalars["two_a_day_preference"],
        peak_sessions_max=availability_scalars["peak_sessions_max"],
        # Full §A-§L mirror.
        identity=identity,
        health_status=health_status,
        training_history=training_history,
        discipline_baselines=discipline_baselines,
        strength_benchmarks=strength_benchmarks,
        performance=performance,
        event_goal=event_goal,
        lifestyle=lifestyle_model,
        network=network,
        disclosures=disclosures_model,
    )


# ─── athlete_profile ─────────────────────────────────────────────────────────


_PROFILE_COLS = (
    "date_of_birth",
    "sex",
    "height_cm",
    "primary_sport",
    "weekly_hours_target",
    "body_weight_kg",
    "hrmax_bpm",
    "lactate_threshold_hr_bpm",
    "vo2max",
    "cycling_ftp_w",
    "doubles_feasible",
    "two_a_day_preference",
    "peak_sessions_max",
    "years_structured_training",
    "peak_weekly_volume_hrs",
    "peak_weekly_volume_year",
    "longest_event_completed",
    "training_consistency_disrupted_weeks",
    "training_consistency_cause",
    "running_threshold_pace_sec_per_km",
    "running_threshold_test_date",
    "css_swim_sec_per_100m",
    "css_test_date",
    "cycling_ftp_test_date",
    "hrmax_source",
    "lt_method",
    "vo2max_source",
    "plan_duration_weeks_no_event",
    "non_event_goal_type",
    "work_stress_level",
    "dietary_pattern",
    "supplement_protocol_notes",
    "caffeine_tolerance",
    "caffeine_daily_mg_estimate",
    "caffeine_race_day_strategy",
    "altitude_acclimatization_history",
    "altitude_max_exposure_m",
    "altitude_exposure_count",
    "fueling_format_preference",
    "gi_triggers_known",
    "salt_electrolyte_tolerance",
    "sleep_deprivation_max_hrs_continuous_awake",
    "sleep_deprivation_strategy_notes",
    # Layer-4 convenience fields, self-reported on the profile (#304).
    "experience_level",
)


def _load_athlete_profile(db, user_id: int):
    """Read athlete_profile and split into the six section dicts plus the
    top-level convenience dict.

    Returns (identity, performance, training_scalars, event_scalars,
    lifestyle_scalars, availability_scalars, convenience). Missing row returns
    section models with all-None scalars + a None-valued convenience dict
    (matching the "row absent = onboarding incomplete" convention).
    """
    cols = ", ".join(_PROFILE_COLS)
    cur = db.execute(
        f"SELECT {cols} FROM athlete_profile WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return (
            Layer1Identity(),
            Layer1Performance(),
            _empty_training_scalars(),
            _empty_event_scalars(),
            _empty_lifestyle(),
            _empty_availability_scalars(),
            {"experience_level": None},
        )

    identity = Layer1Identity(
        date_of_birth=row["date_of_birth"],
        sex=row["sex"],
        height_cm=row["height_cm"],
        primary_sport=row["primary_sport"],
        weekly_hours_target=row["weekly_hours_target"],
    )
    performance = Layer1Performance(
        body_weight_kg=row["body_weight_kg"],
        hrmax_bpm=row["hrmax_bpm"],
        hrmax_source=row["hrmax_source"],
        lactate_threshold_hr_bpm=row["lactate_threshold_hr_bpm"],
        lt_method=row["lt_method"],
        vo2max=row["vo2max"],
        vo2max_source=row["vo2max_source"],
        cycling_ftp_w=row["cycling_ftp_w"],
        cycling_ftp_test_date=row["cycling_ftp_test_date"],
        running_threshold_pace_sec_per_km=row["running_threshold_pace_sec_per_km"],
        running_threshold_test_date=row["running_threshold_test_date"],
        css_swim_sec_per_100m=row["css_swim_sec_per_100m"],
        css_test_date=row["css_test_date"],
    )
    training_scalars = {
        "years_structured_training": row["years_structured_training"],
        "peak_weekly_volume_hrs": row["peak_weekly_volume_hrs"],
        "peak_weekly_volume_year": row["peak_weekly_volume_year"],
        "longest_event_completed": row["longest_event_completed"],
        "training_consistency_disrupted_weeks": row["training_consistency_disrupted_weeks"],
        "training_consistency_cause": row["training_consistency_cause"],
    }
    event_scalars = {
        "plan_duration_weeks_no_event": row["plan_duration_weeks_no_event"],
        "non_event_goal_type": row["non_event_goal_type"],
    }
    lifestyle = {
        "work_stress_level": row["work_stress_level"],
        "dietary_pattern": _split_csv(row["dietary_pattern"]),
        "supplement_protocol_notes": row["supplement_protocol_notes"],
        "caffeine_tolerance": row["caffeine_tolerance"],
        "caffeine_daily_mg_estimate": row["caffeine_daily_mg_estimate"],
        "caffeine_race_day_strategy": row["caffeine_race_day_strategy"],
        "altitude_acclimatization_history": row["altitude_acclimatization_history"],
        "altitude_max_exposure_m": row["altitude_max_exposure_m"],
        "altitude_exposure_count": row["altitude_exposure_count"],
        "fueling_format_preference": _split_csv(row["fueling_format_preference"]),
        "gi_triggers_known": row["gi_triggers_known"],
        "salt_electrolyte_tolerance": row["salt_electrolyte_tolerance"],
        "sleep_deprivation_max_hrs_continuous_awake": row[
            "sleep_deprivation_max_hrs_continuous_awake"
        ],
        "sleep_deprivation_strategy_notes": row["sleep_deprivation_strategy_notes"],
    }
    availability_scalars = {
        "doubles_feasible": row["doubles_feasible"],
        "two_a_day_preference": row["two_a_day_preference"],
        "peak_sessions_max": row["peak_sessions_max"],
    }
    convenience = {
        "experience_level": row["experience_level"],
    }
    return (identity, performance, training_scalars, event_scalars, lifestyle,
            availability_scalars, convenience)


def _empty_training_scalars() -> dict[str, Any]:
    return {
        "years_structured_training": None,
        "peak_weekly_volume_hrs": None,
        "peak_weekly_volume_year": None,
        "longest_event_completed": None,
        "training_consistency_disrupted_weeks": None,
        "training_consistency_cause": None,
    }


def _empty_event_scalars() -> dict[str, Any]:
    return {
        "plan_duration_weeks_no_event": None,
        "non_event_goal_type": None,
    }


def _empty_lifestyle() -> dict[str, Any]:
    return {
        "work_stress_level": None,
        "dietary_pattern": [],
        "supplement_protocol_notes": None,
        "caffeine_tolerance": None,
        "caffeine_daily_mg_estimate": None,
        "caffeine_race_day_strategy": None,
        "altitude_acclimatization_history": None,
        "altitude_max_exposure_m": None,
        "altitude_exposure_count": None,
        "fueling_format_preference": [],
        "gi_triggers_known": None,
        "salt_electrolyte_tolerance": None,
        "sleep_deprivation_max_hrs_continuous_awake": None,
        "sleep_deprivation_strategy_notes": None,
    }


def _empty_availability_scalars() -> dict[str, Any]:
    return {
        "doubles_feasible": None,
        "two_a_day_preference": None,
        "peak_sessions_max": None,
    }


# ─── body_metrics — latest resting_hr ────────────────────────────────────────


def _load_resting_hr(db, user_id: int) -> int | None:
    cur = db.execute(
        "SELECT resting_hr FROM body_metrics "
        "WHERE user_id = ? AND resting_hr IS NOT NULL "
        "ORDER BY date DESC LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    return row["resting_hr"] if row else None


# ─── athlete_skill_toggles — D-73 Phase 5.2 Bucket C (l) ─────────────────────


def _load_skill_toggle_states(db, user_id: int) -> dict[str, bool]:
    """Read the athlete's per-toggle ON/OFF state from
    `athlete_skill_toggles`. Absent rows mean OFF (the table only stores
    explicit picks). Returns {toggle_name: enabled_bool}. Empty dict on
    fresh athletes who have never edited their skill capabilities.
    """
    cur = db.execute(
        "SELECT toggle_name, enabled FROM athlete_skill_toggles "
        "WHERE user_id = ?",
        (user_id,),
    )
    return {r["toggle_name"]: bool(r["enabled"]) for r in cur.fetchall()}


def _load_owned_gear(db, user_id: int) -> list[str]:
    """#884 slice 3b — the athlete's owned gear/craft as a sorted gear_id list,
    read from `athlete_gear` (the unified store, slice 3). Sorted for a stable
    `layer1_hash`. Consumed by the cardio-drill gear gate (per_phase); slice 4
    reads it for the full feasibility cascade. Empty on athletes with no gear
    (athlete_gear is backfilled with owned crafts; swim gear arrives via capture,
    slice 6). Lazy import keeps the Layer-0/4 cache deps out of the builder's
    import surface (the repo pulls in layer4.cache)."""
    from athlete_gear_repo import get_athlete_gear

    return sorted(g["gear_id"] for g in get_athlete_gear(db, user_id))


# ─── athlete_supplements — structured §I.1 protocol ──────────────────────────


def _load_supplements(db, user_id: int) -> list[AthleteSupplementRecord]:
    """The athlete's structured supplement protocol from `athlete_supplements`
    (§I.1), oldest first. Empty list for athletes who've added none. Rows
    soft-reference `layer0.supplement_vocabulary`; canonical_name/category are
    denormalized on the row, so no cross-schema join is needed here. Supersedes
    the free-text `supplement_protocol_notes` — consumed by Layer 2E §5.5.
    """
    cur = db.execute(
        "SELECT supplement_id, canonical_name, category, dose, frequency, "
        "timing, notes "
        "FROM athlete_supplements WHERE user_id = ? ORDER BY created_at, id",
        (user_id,),
    )
    return [
        AthleteSupplementRecord(
            supplement_id=r["supplement_id"],
            canonical_name=r["canonical_name"],
            category=r["category"],
            dose=r["dose"],
            frequency=r["frequency"],
            timing=r["timing"],
            notes=r["notes"],
        )
        for r in cur.fetchall()
    ]


# ─── wellness_self_report — latest sleep_hours ───────────────────────────────


def _load_sleep_baseline(db, user_id: int) -> float | None:
    cur = db.execute(
        "SELECT sleep_hours FROM wellness_self_report "
        "WHERE user_id = ? AND sleep_hours IS NOT NULL "
        "ORDER BY date DESC LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    return row["sleep_hours"] if row else None


# ─── daily_availability_windows ──────────────────────────────────────────────


def _load_daily_windows(
    db, user_id: int, availability_scalars: dict[str, Any]
) -> list[DailyAvailabilityWindow]:
    """Read daily_availability_windows + denormalize the doubles_feasible
    capacity flag onto each of the 7 days the typed `DailyAvailabilityWindow`
    model expects.

    Returns 7 entries Sunday..Saturday regardless of how many rows exist in
    the table — missing days surface as enabled=False. The weekly long
    session is the longest enabled window and the rest days are the disabled
    days (FormRefresh Slice C 2026-05-25 — inferred, not stored).
    """
    cur = db.execute(
        "SELECT day_of_week, window_index, enabled, window_start, window_duration_min "
        "FROM daily_availability_windows WHERE user_id = ?",
        (user_id,),
    )
    rows = list(cur.fetchall())
    by_day_idx: dict[tuple[int, int], Any] = {(r["day_of_week"], r["window_index"]): r for r in rows}

    doubles_feasible_raw = availability_scalars["doubles_feasible"]
    # DailyAvailabilityWindow requires non-null doubles_feasible; default "no"
    # when athlete_profile.doubles_feasible is NULL (interpretation: no doubles
    # when not configured).
    doubles_feasible = doubles_feasible_raw if doubles_feasible_raw is not None else "no"

    out: list[DailyAvailabilityWindow] = []
    for dow in range(7):
        primary = by_day_idx.get((dow, 0))
        secondary = by_day_idx.get((dow, 1))
        enabled = bool(primary["enabled"]) if primary else False
        window_start = _format_time(primary["window_start"]) if primary else None
        window_duration = primary["window_duration_min"] if primary else None
        second_start = _format_time(secondary["window_start"]) if secondary and secondary["enabled"] else None
        second_duration = (
            secondary["window_duration_min"] if secondary and secondary["enabled"] else None
        )
        # When window_start is set on a disabled primary row, drop it — the
        # typed model's invariant rejects disabled+populated.
        if not enabled:
            window_start = None
            window_duration = None

        out.append(
            DailyAvailabilityWindow(
                day_of_week=_DAY_LABELS[dow],
                enabled=enabled,
                window_start=window_start,
                window_duration=window_duration,
                second_window_start=second_start,
                second_window_duration=second_duration,
                doubles_feasible=doubles_feasible,
            )
        )
    return out


# ─── injury_log ──────────────────────────────────────────────────────────────


def _load_injuries(db, user_id: int) -> tuple[list[InjuryRecord], list[InjuryRecord]]:
    cur = db.execute(
        "SELECT id, body_part, description, severity, injury_type, side, "
        "movement_constraints, status, start_date, resolved_date, "
        "modifications_needed "
        "FROM injury_log WHERE user_id = ? ORDER BY start_date DESC, id DESC",
        (user_id,),
    )
    current: list[InjuryRecord] = []
    history: list[InjuryRecord] = []
    for r in cur.fetchall():
        # movement_constraints is JSONB; psycopg2 returns it parsed (list[str])
        # when populated, None when NULL. Defensive: coerce NULL to empty list
        # so the pydantic default_factory is honoured.
        mc = r["movement_constraints"] or []
        record = InjuryRecord(
            injury_id=int(r["id"]),
            body_part=r["body_part"],
            description=r["description"],
            severity=r["severity"],
            injury_type=r["injury_type"],
            side=r["side"] or "N/A",
            movement_constraints=mc,
            status=r["status"],
            start_date=r["start_date"],
            resolved_date=r["resolved_date"],
            modifications_needed=r["modifications_needed"],
        )
        if record.status == "Active":
            current.append(record)
        else:
            history.append(record)
    return current, history


# ─── health_conditions_log ───────────────────────────────────────────────────


def _load_health_conditions(
    db, user_id: int
) -> tuple[list[HealthConditionRecord], list[HealthConditionRecord]]:
    cur = db.execute(
        "SELECT id, system_category, condition_name, severity, notes, status, "
        "start_date, resolved_date "
        "FROM health_conditions_log WHERE user_id = ? "
        "ORDER BY created_at DESC, id DESC",
        (user_id,),
    )
    active: list[HealthConditionRecord] = []
    history: list[HealthConditionRecord] = []
    for r in cur.fetchall():
        record = HealthConditionRecord(
            condition_id=int(r["id"]),
            system_category=r["system_category"],
            condition_name=r["condition_name"],
            severity=r["severity"],
            notes=r["notes"],
            status=r["status"],
            start_date=r["start_date"],
            resolved_date=r["resolved_date"],
        )
        if record.status == "Active":
            active.append(record)
        else:
            history.append(record)
    return active, history


# ─── medications_log ─────────────────────────────────────────────────────────


def _load_medications(
    db, user_id: int
) -> tuple[list[MedicationRecord], list[MedicationRecord]]:
    cur = db.execute(
        "SELECT id, medication_class, medication_name, started_at, stopped_at, notes "
        "FROM medications_log WHERE user_id = ? "
        "ORDER BY started_at DESC NULLS LAST, id DESC",
        (user_id,),
    )
    active: list[MedicationRecord] = []
    history: list[MedicationRecord] = []
    for r in cur.fetchall():
        record = MedicationRecord(
            medication_id=int(r["id"]),
            medication_class=r["medication_class"],
            medication_name=r["medication_name"],
            started_at=r["started_at"],
            stopped_at=r["stopped_at"],
            notes=r["notes"],
        )
        if record.stopped_at is None:
            active.append(record)
        else:
            history.append(record)
    return active, history


# ─── athlete_secondary_sports ────────────────────────────────────────────────


def _load_secondary_sports(db, user_id: int) -> list[SecondarySportRecord]:
    cur = db.execute(
        "SELECT sport_slug, experience_tier "
        "FROM athlete_secondary_sports WHERE user_id = ? ORDER BY sport_slug",
        (user_id,),
    )
    return [
        SecondarySportRecord(
            sport_slug=r["sport_slug"],
            experience_tier=r["experience_tier"],
        )
        for r in cur.fetchall()
    ]


# ─── athlete_discipline_weighting ────────────────────────────────────────────


def _load_discipline_weighting(db, user_id: int) -> list[DisciplineWeightRecord]:
    cur = db.execute(
        "SELECT discipline_slug, weight_pct "
        "FROM athlete_discipline_weighting WHERE user_id = ? "
        "ORDER BY weight_pct DESC, discipline_slug",
        (user_id,),
    )
    return [
        DisciplineWeightRecord(
            discipline_slug=r["discipline_slug"],
            weight_pct=int(r["weight_pct"]),
        )
        for r in cur.fetchall()
    ]


# ─── recent_race_results ─────────────────────────────────────────────────────


def _load_recent_race_results(db, user_id: int) -> list[RecentRaceResult]:
    cur = db.execute(
        "SELECT event_name, event_date, distance_km, finish_time_seconds, "
        "result_notes, source "
        "FROM recent_race_results WHERE user_id = ? ORDER BY event_date DESC",
        (user_id,),
    )
    return [
        RecentRaceResult(
            event_name=r["event_name"],
            event_date=r["event_date"],
            distance_km=r["distance_km"],
            finish_time_seconds=r["finish_time_seconds"],
            result_notes=r["result_notes"],
            source=r["source"],
        )
        for r in cur.fetchall()
    ]


# ─── pack_load_history ───────────────────────────────────────────────────────


def _load_pack_load_history(db, user_id: int) -> list[PackLoadRecord]:
    cur = db.execute(
        "SELECT pack_weight_kg, session_count_4wk, longest_session_hrs, "
        "terrain_type, notes "
        "FROM pack_load_history WHERE user_id = ? "
        "ORDER BY pack_weight_kg DESC, created_at DESC",
        (user_id,),
    )
    return [
        PackLoadRecord(
            pack_weight_kg=r["pack_weight_kg"],
            session_count_4wk=r["session_count_4wk"],
            longest_session_hrs=r["longest_session_hrs"],
            terrain_type=r["terrain_type"],
            notes=r["notes"],
        )
        for r in cur.fetchall()
    ]


# ─── strength_benchmarks (1:1) ───────────────────────────────────────────────


def _load_strength_benchmarks(db, user_id: int) -> Layer1StrengthBenchmarks | None:
    cur = db.execute(
        "SELECT front_plank_sec, dead_bug_max_reps, side_plank_left_sec, "
        "side_plank_right_sec, pushup_max_reps, bodyweight_squat_max_reps, "
        "single_leg_squat_left_max_reps, single_leg_squat_right_max_reps, "
        "pullup_max_reps, dead_hang_sec, grip_strength_left_kg, "
        "grip_strength_right_kg, last_tested_at "
        "FROM strength_benchmarks WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return Layer1StrengthBenchmarks(
        front_plank_sec=row["front_plank_sec"],
        dead_bug_max_reps=row["dead_bug_max_reps"],
        side_plank_left_sec=row["side_plank_left_sec"],
        side_plank_right_sec=row["side_plank_right_sec"],
        pushup_max_reps=row["pushup_max_reps"],
        bodyweight_squat_max_reps=row["bodyweight_squat_max_reps"],
        single_leg_squat_left_max_reps=row["single_leg_squat_left_max_reps"],
        single_leg_squat_right_max_reps=row["single_leg_squat_right_max_reps"],
        pullup_max_reps=row["pullup_max_reps"],
        dead_hang_sec=row["dead_hang_sec"],
        grip_strength_left_kg=row["grip_strength_left_kg"],
        grip_strength_right_kg=row["grip_strength_right_kg"],
        last_tested_at=row["last_tested_at"],
    )


# ─── discipline_baseline_* (7 × 1:1) ─────────────────────────────────────────


def _load_discipline_baselines(db, user_id: int) -> Layer1DisciplineBaselines:
    running = _load_running_baseline(db, user_id)
    cycling = _load_cycling_baseline(db, user_id)
    swimming = _load_swimming_baseline(db, user_id)
    paddling = _load_paddling_baseline(db, user_id)
    skiing = _load_skiing_baseline(db, user_id)
    navigation = _load_navigation_baseline(db, user_id)
    technical = _load_technical_baseline(db, user_id)
    return Layer1DisciplineBaselines(
        running=running,
        cycling=cycling,
        swimming=swimming,
        paddling=paddling,
        skiing=skiing,
        navigation=navigation,
        technical=technical,
    )


def _load_running_baseline(db, user_id: int) -> RunningBaseline | None:
    cur = db.execute(
        "SELECT easy_run_pace_sec_per_km, vertical_gain_weekly_m, "
        "vertical_gain_peak_session_m, trail_experience_terrain, "
        "downhill_adaptation, downhill_sessions_3mo, night_running, "
        "gut_training_g_per_hr_cho, gut_training_issues "
        "FROM discipline_baseline_running WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return RunningBaseline(
        easy_run_pace_sec_per_km=row["easy_run_pace_sec_per_km"],
        vertical_gain_weekly_m=row["vertical_gain_weekly_m"],
        vertical_gain_peak_session_m=row["vertical_gain_peak_session_m"],
        trail_experience_terrain=_split_csv(row["trail_experience_terrain"]),
        downhill_adaptation=row["downhill_adaptation"],
        downhill_sessions_3mo=row["downhill_sessions_3mo"],
        night_running=row["night_running"],
        gut_training_g_per_hr_cho=row["gut_training_g_per_hr_cho"],
        gut_training_issues=row["gut_training_issues"],
    )


def _load_cycling_baseline(db, user_id: int) -> CyclingBaseline | None:
    cur = db.execute(
        "SELECT bike_types_available, mtb_skill, longest_ride_distance_km, "
        "longest_ride_hrs, saddle_endurance_hrs, aero_endurance_min "
        "FROM discipline_baseline_cycling WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return CyclingBaseline(
        bike_types_available=_split_csv(row["bike_types_available"]),
        mtb_skill=row["mtb_skill"],
        longest_ride_distance_km=row["longest_ride_distance_km"],
        longest_ride_hrs=row["longest_ride_hrs"],
        saddle_endurance_hrs=row["saddle_endurance_hrs"],
        aero_endurance_min=row["aero_endurance_min"],
    )


def _load_swimming_baseline(db, user_id: int) -> SwimmingBaseline | None:
    cur = db.execute(
        "SELECT pool_100m_pace_sec, ow_experience, wetsuit_experience, "
        "cold_water_experience, ow_feeding_experience, weekly_swim_volume_km "
        "FROM discipline_baseline_swimming WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return SwimmingBaseline(
        pool_100m_pace_sec=row["pool_100m_pace_sec"],
        ow_experience=row["ow_experience"],
        wetsuit_experience=row["wetsuit_experience"],
        cold_water_experience=row["cold_water_experience"],
        ow_feeding_experience=row["ow_feeding_experience"],
        weekly_swim_volume_km=row["weekly_swim_volume_km"],
    )


def _load_paddling_baseline(db, user_id: int) -> PaddlingBaseline | None:
    cur = db.execute(
        "SELECT longest_paddle_km, longest_paddle_hrs, paddle_craft_types "
        "FROM discipline_baseline_paddling WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return PaddlingBaseline(
        longest_paddle_km=row["longest_paddle_km"],
        longest_paddle_hrs=row["longest_paddle_hrs"],
        paddle_craft_types=_split_csv(row["paddle_craft_types"]),
    )


def _load_skiing_baseline(db, user_id: int) -> SkiingBaseline | None:
    cur = db.execute(
        "SELECT ski_disciplines, weekly_ski_volume_hrs "
        "FROM discipline_baseline_skiing WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return SkiingBaseline(
        ski_disciplines=_split_csv(row["ski_disciplines"]),
        weekly_ski_volume_hrs=row["weekly_ski_volume_hrs"],
    )


def _load_navigation_baseline(db, user_id: int) -> NavigationBaseline | None:
    cur = db.execute(
        "SELECT experience_level, night_nav_experience "
        "FROM discipline_baseline_navigation WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return NavigationBaseline(
        experience_level=row["experience_level"],
        night_nav_experience=row["night_nav_experience"],
    )


def _load_technical_baseline(db, user_id: int) -> TechnicalBaseline | None:
    cur = db.execute(
        "SELECT rock_climbing_outdoor_grade, rock_climbing_indoor_grade, "
        "abseiling_experience "
        "FROM discipline_baseline_technical WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return TechnicalBaseline(
        rock_climbing_outdoor_grade=row["rock_climbing_outdoor_grade"],
        rock_climbing_indoor_grade=row["rock_climbing_indoor_grade"],
        abseiling_experience=row["abseiling_experience"],
    )


# ─── athlete_event_windows — travel_constraint summary ───────────────────────


def _summarize_travel_constraint(db, user_id: int) -> str | None:
    """Condense the athlete's declared event windows into the free-text
    `travel_constraint` string Layer 4 renders ("Travel constraint: ..."). One
    phrase per window; `None` when the athlete has declared none (the prompt
    suppresses an empty constraint). Replaces the retired v1 `plan_travel`
    surface as the travel source (#304)."""
    windows = load_event_windows(db, user_id)
    if not windows:
        return None
    phrases = []
    for w in windows:
        span = f"{w.start_date.isoformat()}–{w.end_date.isoformat()}"
        if w.override_type == "indoor_only":
            what = "indoor only"
        elif w.override_type == "locale_unavailable":
            what = f"{w.unavailable_locale or 'a locale'} unavailable"
        elif w.override_type == "away":
            what = f"training at {w.away_locale or 'an away location'}"
            if w.brought_gear:
                what += f" (brings {', '.join(w.brought_gear)})"
        else:
            what = w.override_type
        if w.notes:
            what += f" — {w.notes}"
        phrases.append(f"{span}: {what}")
    summary = "; ".join(phrases)
    print(  # Rule #15 — deterministic summary of the event-window inputs.
        f"[layer1-travel] user={user_id} windows={len(windows)} "
        f"-> travel_constraint={summary!r}"
    )
    return summary


# ─── coaching_preferences (Coaching Memory) ──────────────────────────────────


def _load_coaching_preferences(db, user_id: int) -> list[Layer1CoachingPreference]:
    """#690 — durable Coaching Memory preferences. Ordered oldest-first with an
    `id` tiebreaker so the list (and therefore `layer1_hash`) is deterministic
    across reads even when two rows share a `created_at`. Mirrors the v1
    `coaching.py` read so manually-added + auto-extracted prefs surface the same
    way; the int `permanent` flag is normalized to bool for the typed model."""
    cur = db.execute(
        "SELECT category, content, permanent FROM coaching_preferences "
        "WHERE user_id = ? ORDER BY created_at ASC, id ASC",
        (user_id,),
    )
    prefs = [
        Layer1CoachingPreference(
            category=r["category"],
            content=r["content"],
            permanent=bool(r["permanent"]),
        )
        for r in cur.fetchall()
    ]
    print(  # Rule #15 — what reached the synthesizer's coaching-memory channel.
        f"[layer1-coaching-memory] user={user_id} prefs={len(prefs)} "
        f"permanent={sum(1 for p in prefs if p.permanent)}"
    )
    return prefs


# ─── athlete_network_links ───────────────────────────────────────────────────


def _load_network_links(db, user_id: int) -> list[AthleteNetworkLink]:
    cur = db.execute(
        "SELECT id, partner_name, linked_account_user_id, relationship_types, "
        "partner_specific_rules, race_event_id, discipline_focus_on_team "
        "FROM athlete_network_links WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    return [
        AthleteNetworkLink(
            link_id=int(r["id"]),
            partner_name=r["partner_name"],
            linked_account_user_id=r["linked_account_user_id"],
            relationship_types=_split_csv(r["relationship_types"]),
            partner_specific_rules=r["partner_specific_rules"],
            race_event_id=r["race_event_id"],
            discipline_focus_on_team=r["discipline_focus_on_team"],
        )
        for r in cur.fetchall()
    ]


# ─── linked_partner_consents ─────────────────────────────────────────────────


def _load_linked_partner_consents(db, user_id: int) -> list[LinkedPartnerConsent]:
    cur = db.execute(
        "SELECT id, link_id, consent_scope, granted_at, revoked_at "
        "FROM linked_partner_consents WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    return [
        LinkedPartnerConsent(
            consent_id=int(r["id"]),
            link_id=int(r["link_id"]),
            consent_scope=r["consent_scope"],
            granted_at=r["granted_at"],
            revoked_at=r["revoked_at"],
        )
        for r in cur.fetchall()
    ]


# ─── disclosure_acknowledgments — latest per disclosure_id ───────────────────


def _load_disclosures(db, user_id: int) -> list[DisclosureAck]:
    cur = db.execute(
        """
        SELECT disclosure_id, version_id, scopes_granted, delivery_method, acknowledged_at
          FROM (
            SELECT disclosure_id, version_id, scopes_granted, delivery_method, acknowledged_at,
                   ROW_NUMBER() OVER (PARTITION BY disclosure_id ORDER BY acknowledged_at DESC) AS rn
              FROM disclosure_acknowledgments
             WHERE user_id = ?
          ) latest
         WHERE rn = 1
         ORDER BY disclosure_id
        """,
        (user_id,),
    )
    return [
        DisclosureAck(
            disclosure_id=r["disclosure_id"],
            version_id=r["version_id"],
            scopes_granted=r["scopes_granted"],
            delivery_method=r["delivery_method"],
            acknowledged_at=r["acknowledged_at"],
        )
        for r in cur.fetchall()
    ]
