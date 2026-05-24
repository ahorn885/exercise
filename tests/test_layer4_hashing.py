"""Tests for Layer 4 canonical-JSON encoder + SHA-256 cache-key helpers per §9.1.

Three test concerns per the §14.3.4 Step 2 PR-B brief:
  - determinism: same inputs → same hash, every time
  - key stability across input orderings: dict iteration order doesn't matter;
    session list pre-sort is enforced before hashing
  - dependency on each cache-key input: mutating each component flips the hash
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from layer4.hashing import (
    canonical_json,
    compute_layer2_bundle_canonical_hash,
    compute_layer2c_bundle_hash,
    compute_payload_hash,
    compute_prior_plan_session_window_hash,
    plan_create_key,
    plan_refresh_key,
    race_week_brief_key,
    single_session_synthesize_key,
)
from layer4.payload import (
    CardioBlock,
    HRTarget,
    PaceTarget,
    PlanSession,
    PowerTarget,
)


# ─── builders ───────────────────────────────────────────────────────────────


def _cardio_block(intensity_target=None) -> CardioBlock:
    return CardioBlock(
        block_kind="main_set",
        duration_min=45,
        intensity_zone="Z2",
        intensity_target=intensity_target or HRTarget(hr_bpm_low=140, hr_bpm_high=160),
        instructions="Steady Z2 effort.",
    )


def _plan_session(
    *,
    session_id: str = "s1",
    plan_version_id: int = 100,
    d: date = date(2026, 5, 18),
    session_index_in_day: int = 0,
) -> PlanSession:
    return PlanSession(
        session_id=session_id,
        plan_version_id=plan_version_id,
        date=d,
        day_of_week="Mon",
        session_index_in_day=session_index_in_day,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Trail running",
        locale_id="home",
        locale_name="Home",
        duration_min=45,
        intensity_summary="easy",
        cardio_blocks=[_cardio_block()],
        session_notes="Easy aerobic.",
        coaching_intent="Aerobic base.",
        coaching_flags=[],
    )


# ─── canonical_json ─────────────────────────────────────────────────────────


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_no_whitespace() -> None:
    assert canonical_json({"a": 1, "b": [2, 3]}) == '{"a":1,"b":[2,3]}'


def test_canonical_json_date_iso() -> None:
    assert canonical_json(date(2026, 5, 17)) == '"2026-05-17"'


def test_canonical_json_datetime_iso() -> None:
    dt = datetime(2026, 5, 17, 12, 30, tzinfo=timezone.utc)
    assert canonical_json(dt) == '"2026-05-17T12:30:00+00:00"'


def test_canonical_json_decimal_string() -> None:
    assert canonical_json(Decimal("1.234")) == '"1.234"'


def test_canonical_json_set_sorted() -> None:
    assert canonical_json({3, 1, 2}) == "[1,2,3]"


def test_canonical_json_tuple_to_list() -> None:
    assert canonical_json((1, 2, 3)) == "[1,2,3]"


def test_canonical_json_nested_dict_sorted() -> None:
    a = {"z": {"b": 1, "a": 2}, "a": {"y": 3, "x": 4}}
    b = {"a": {"x": 4, "y": 3}, "z": {"a": 2, "b": 1}}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_pydantic_model() -> None:
    hr = HRTarget(hr_bpm_low=140, hr_bpm_high=160)
    assert canonical_json(hr) == '{"hr_bpm_high":160,"hr_bpm_low":140}'


def test_canonical_json_nested_pydantic() -> None:
    block = _cardio_block()
    encoded = canonical_json(block)
    assert '"intensity_target":{"hr_bpm_high":160,"hr_bpm_low":140}' in encoded
    assert '"block_kind":"main_set"' in encoded


# ─── compute_payload_hash ───────────────────────────────────────────────────


def test_payload_hash_deterministic() -> None:
    block = _cardio_block()
    assert compute_payload_hash(block) == compute_payload_hash(block)


def test_payload_hash_distinguishes_fields() -> None:
    a = _cardio_block(HRTarget(hr_bpm_low=140, hr_bpm_high=160))
    b = _cardio_block(HRTarget(hr_bpm_low=141, hr_bpm_high=160))
    assert compute_payload_hash(a) != compute_payload_hash(b)


def test_payload_hash_intensitytarget_shape_distinguished() -> None:
    """Different IntensityTarget union members hash differently even at same numeric values."""
    hr_block = _cardio_block(HRTarget(hr_bpm_low=140, hr_bpm_high=160))
    power_block = _cardio_block(PowerTarget(power_w_low=140, power_w_high=160))
    assert compute_payload_hash(hr_block) != compute_payload_hash(power_block)


def test_payload_hash_dict_input_equivalent_to_model() -> None:
    """Hashing a dict shape equal to the model dump gives the same hash."""
    block = _cardio_block()
    as_dict = block.model_dump(mode="json")
    assert compute_payload_hash(block) == compute_payload_hash(as_dict)


def test_payload_hash_pace_target_round_trip() -> None:
    a = _cardio_block(PaceTarget(pace_per_km_low="5:00", pace_per_km_high="5:30"))
    b = _cardio_block(PaceTarget(pace_per_km_low="5:00", pace_per_km_high="5:30"))
    assert compute_payload_hash(a) == compute_payload_hash(b)


# ─── compute_layer2c_bundle_hash ────────────────────────────────────────────


def test_layer2c_bundle_hash_dict_order_irrelevant() -> None:
    a = {"home": "hash_a", "hotel": "hash_b", "partner": "hash_c"}
    b = {"partner": "hash_c", "home": "hash_a", "hotel": "hash_b"}
    assert compute_layer2c_bundle_hash(a) == compute_layer2c_bundle_hash(b)


def test_layer2c_bundle_hash_distinguishes_content() -> None:
    a = {"home": "hash_a"}
    b = {"home": "hash_b"}
    assert compute_layer2c_bundle_hash(a) != compute_layer2c_bundle_hash(b)


def test_layer2c_bundle_hash_distinguishes_membership() -> None:
    a = {"home": "hash_a"}
    b = {"home": "hash_a", "hotel": "hash_b"}
    assert compute_layer2c_bundle_hash(a) != compute_layer2c_bundle_hash(b)


# ─── compute_layer2_bundle_canonical_hash ───────────────────────────────────


def test_layer2_bundle_canonical_hash_all_keys_required() -> None:
    with pytest.raises(ValueError, match="layer2_hashes must have keys"):
        compute_layer2_bundle_canonical_hash({"a": "x", "b": "y"})


def test_layer2_bundle_canonical_hash_extra_key_rejected() -> None:
    with pytest.raises(ValueError, match="layer2_hashes must have keys"):
        compute_layer2_bundle_canonical_hash(
            {"a": "x", "b": "y", "c": "z", "d": "w", "e": "v", "f": "u"}
        )


def test_layer2_bundle_canonical_hash_null_preserved() -> None:
    """T1-cascade-with-2A-re-run differentiates from T1-cascade-with-no-Layer-2-re-run per §9.1."""
    re_ran_2a = {"a": "hash_a", "b": None, "c": None, "d": None, "e": None}
    no_re_run = {"a": None, "b": None, "c": None, "d": None, "e": None}
    assert compute_layer2_bundle_canonical_hash(re_ran_2a) != compute_layer2_bundle_canonical_hash(
        no_re_run
    )


def test_layer2_bundle_canonical_hash_dict_order_irrelevant() -> None:
    a = {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}
    b = {"e": "5", "d": "4", "c": "3", "b": "2", "a": "1"}
    assert compute_layer2_bundle_canonical_hash(a) == compute_layer2_bundle_canonical_hash(b)


# ─── compute_prior_plan_session_window_hash ─────────────────────────────────


def test_prior_plan_session_window_hash_sort_order_irrelevant() -> None:
    s_mon = _plan_session(session_id="mon", d=date(2026, 5, 18))
    s_tue = _plan_session(session_id="tue", d=date(2026, 5, 19))
    s_wed = _plan_session(session_id="wed", d=date(2026, 5, 20))
    forward = [s_mon, s_tue, s_wed]
    reversed_input = [s_wed, s_tue, s_mon]
    assert compute_prior_plan_session_window_hash(
        forward
    ) == compute_prior_plan_session_window_hash(reversed_input)


def test_prior_plan_session_window_hash_distinguishes_content() -> None:
    s_a = _plan_session(session_id="s1", d=date(2026, 5, 18))
    s_b = _plan_session(session_id="s2", d=date(2026, 5, 18), session_index_in_day=1)
    assert compute_prior_plan_session_window_hash(
        [s_a]
    ) != compute_prior_plan_session_window_hash([s_a, s_b])


def test_prior_plan_session_window_hash_empty_list() -> None:
    h = compute_prior_plan_session_window_hash([])
    assert h == compute_prior_plan_session_window_hash([])


def test_prior_plan_session_window_hash_sort_handles_same_day_indices() -> None:
    """Same date, different session_index_in_day — sort key (date, idx) keeps it stable."""
    s_idx0 = _plan_session(session_id="am", d=date(2026, 5, 18), session_index_in_day=0)
    s_idx1 = _plan_session(session_id="pm", d=date(2026, 5, 18), session_index_in_day=1)
    assert compute_prior_plan_session_window_hash(
        [s_idx0, s_idx1]
    ) == compute_prior_plan_session_window_hash([s_idx1, s_idx0])


# ─── plan_create_key ────────────────────────────────────────────────────────


_PLAN_CREATE_BASE = dict(
    user_id=1,
    layer1_hash="l1",
    layer2a_hash="l2a",
    layer2b_hash="l2b",
    layer2c_bundle_hash="l2cb",
    layer2d_hash="l2d",
    layer2e_hash="l2e",
    layer3a_hash="l3a",
    layer3b_hash="l3b",
    plan_start_date=date(2026, 6, 1),
    etl_version_set={"layer1": "v1", "layer2a": "v1"},
    model_synthesizer="claude-opus-4-7",
    model_seam_reviewer="claude-sonnet-4-6",
    temperature=0.2,
    max_tokens_per_phase=8000,
    capped_retries_per_phase=2,
)


def test_plan_create_key_deterministic() -> None:
    assert plan_create_key(**_PLAN_CREATE_BASE) == plan_create_key(**_PLAN_CREATE_BASE)


def test_plan_create_key_etl_version_set_dict_order_irrelevant() -> None:
    a = {**_PLAN_CREATE_BASE, "etl_version_set": {"layer1": "v1", "layer2a": "v1"}}
    b = {**_PLAN_CREATE_BASE, "etl_version_set": {"layer2a": "v1", "layer1": "v1"}}
    assert plan_create_key(**a) == plan_create_key(**b)


def test_plan_create_key_modality_hash_none_equals_empty_string() -> None:
    """BM-3: modality_hash=None must equal modality_hash='' (forward-compat
    with pre-BM-3 cache entries written without the hash component)."""
    none_variant = plan_create_key(**{**_PLAN_CREATE_BASE, "layer2_modality_hash": None})
    empty_variant = plan_create_key(**{**_PLAN_CREATE_BASE, "layer2_modality_hash": ""})
    default_variant = plan_create_key(**_PLAN_CREATE_BASE)
    assert none_variant == empty_variant == default_variant


def test_plan_create_key_modality_hash_set_distinguishes() -> None:
    """BM-3: a populated modality_hash flips the cache key vs the unset (None) baseline."""
    bare = plan_create_key(**_PLAN_CREATE_BASE)
    with_hash = plan_create_key(**{**_PLAN_CREATE_BASE, "layer2_modality_hash": "mod_x"})
    assert bare != with_hash


def test_plan_create_key_race_modality_hints_hash_none_equals_empty_string() -> None:
    """Spec v2 §E: race_modality_hints_hash=None must equal ='' (forward-
    compat with pre-v2 cache entries written without the hash component)."""
    none_variant = plan_create_key(
        **{**_PLAN_CREATE_BASE, "race_modality_hints_hash": None}
    )
    empty_variant = plan_create_key(
        **{**_PLAN_CREATE_BASE, "race_modality_hints_hash": ""}
    )
    default_variant = plan_create_key(**_PLAN_CREATE_BASE)
    assert none_variant == empty_variant == default_variant


def test_plan_create_key_race_modality_hints_hash_set_distinguishes() -> None:
    """Spec v2 §E: populated race_modality_hints_hash flips the cache key
    vs the unset (None) baseline."""
    bare = plan_create_key(**_PLAN_CREATE_BASE)
    with_hash = plan_create_key(
        **{**_PLAN_CREATE_BASE, "race_modality_hints_hash": "hints_x"}
    )
    assert bare != with_hash


@pytest.mark.parametrize(
    "field, mutated",
    [
        ("user_id", 2),
        ("layer1_hash", "l1_x"),
        ("layer2a_hash", "l2a_x"),
        ("layer2b_hash", "l2b_x"),
        ("layer2c_bundle_hash", "l2cb_x"),
        ("layer2d_hash", "l2d_x"),
        ("layer2e_hash", "l2e_x"),
        ("layer3a_hash", "l3a_x"),
        ("layer3b_hash", "l3b_x"),
        ("plan_start_date", date(2026, 6, 2)),
        ("etl_version_set", {"layer1": "v2"}),
        ("model_synthesizer", "claude-opus-4-6"),
        ("model_seam_reviewer", "claude-sonnet-4-5"),
        ("temperature", 0.3),
        ("max_tokens_per_phase", 8001),
        ("capped_retries_per_phase", 1),
        ("layer2_modality_hash", "mod_x"),
        ("race_modality_hints_hash", "hints_x"),
    ],
)
def test_plan_create_key_depends_on_each_component(field: str, mutated: object) -> None:
    """Mutating any cache-key input flips the hash."""
    base = plan_create_key(**_PLAN_CREATE_BASE)
    mutated_args = {**_PLAN_CREATE_BASE, field: mutated}
    assert plan_create_key(**mutated_args) != base


# ─── plan_refresh_key ───────────────────────────────────────────────────────


_PLAN_REFRESH_BASE = dict(
    user_id=1,
    tier="T2",
    refresh_scope_start=date(2026, 6, 1),
    refresh_scope_end=date(2026, 6, 7),
    layer1_hash="l1",
    layer2_bundle_canonical_hash="l2b",
    layer3a_hash="l3a",
    layer3b_hash="l3b",
    prior_plan_session_window_hash="pp",
    parsed_intent_hash=None,
    etl_version_set={"layer1": "v1"},
    model_synthesizer="claude-opus-4-7",
    model_seam_reviewer=None,  # Pattern B refresh (T2)
    temperature=0.2,
    max_tokens=4000,
    capped_retries=2,
)


def test_plan_refresh_key_deterministic() -> None:
    assert plan_refresh_key(**_PLAN_REFRESH_BASE) == plan_refresh_key(**_PLAN_REFRESH_BASE)


def test_plan_refresh_key_none_seam_reviewer_equals_empty_string() -> None:
    """Pattern B refresh: model_seam_reviewer=None must equal model_seam_reviewer='' (§9.1)."""
    none_variant = plan_refresh_key(**_PLAN_REFRESH_BASE)
    empty_variant = plan_refresh_key(**{**_PLAN_REFRESH_BASE, "model_seam_reviewer": ""})
    assert none_variant == empty_variant


def test_plan_refresh_key_none_parsed_intent_equals_empty_string() -> None:
    none_variant = plan_refresh_key(**_PLAN_REFRESH_BASE)
    empty_variant = plan_refresh_key(**{**_PLAN_REFRESH_BASE, "parsed_intent_hash": ""})
    assert none_variant == empty_variant


def test_plan_refresh_key_pattern_a_seam_reviewer_distinguishes() -> None:
    """T3 cross-phase routes to Pattern A and the seam-reviewer model matters."""
    pattern_b = plan_refresh_key(**_PLAN_REFRESH_BASE)
    pattern_a = plan_refresh_key(
        **{**_PLAN_REFRESH_BASE, "model_seam_reviewer": "claude-sonnet-4-6"}
    )
    assert pattern_b != pattern_a


def test_plan_refresh_key_parsed_intent_set_distinguishes() -> None:
    bare = plan_refresh_key(**_PLAN_REFRESH_BASE)
    with_intent = plan_refresh_key(**{**_PLAN_REFRESH_BASE, "parsed_intent_hash": "intent_x"})
    assert bare != with_intent


@pytest.mark.parametrize(
    "field, mutated",
    [
        ("user_id", 2),
        ("tier", "T1"),
        ("refresh_scope_start", date(2026, 6, 2)),
        ("refresh_scope_end", date(2026, 6, 8)),
        ("layer1_hash", "l1_x"),
        ("layer2_bundle_canonical_hash", "l2b_x"),
        ("layer3a_hash", "l3a_x"),
        ("layer3b_hash", "l3b_x"),
        ("prior_plan_session_window_hash", "pp_x"),
        ("etl_version_set", {"layer1": "v2"}),
        ("model_synthesizer", "claude-opus-4-6"),
        ("temperature", 0.3),
        ("max_tokens", 4001),
        ("capped_retries", 1),
    ],
)
def test_plan_refresh_key_depends_on_each_component(field: str, mutated: object) -> None:
    base = plan_refresh_key(**_PLAN_REFRESH_BASE)
    assert plan_refresh_key(**{**_PLAN_REFRESH_BASE, field: mutated}) != base


# ─── single_session_synthesize_key ──────────────────────────────────────────


_SINGLE_SESSION_BASE = dict(
    user_id=1,
    request={"sport": "run", "duration_min": 45, "intensity": "easy"},
    layer1_hash="l1",
    layer2c_locale_hash="l2c_home",
    layer2d_hash="l2d",
    layer3a_hash="l3a",
    etl_version_set={"layer1": "v1"},
    model="claude-opus-4-7",
    temperature=0.2,
    max_tokens=1500,
    capped_retries=2,
)


def test_single_session_key_deterministic() -> None:
    assert single_session_synthesize_key(
        **_SINGLE_SESSION_BASE
    ) == single_session_synthesize_key(**_SINGLE_SESSION_BASE)


def test_single_session_key_request_dict_order_irrelevant() -> None:
    """request encoded via canonical_json — dict iteration order shouldn't matter."""
    a = {**_SINGLE_SESSION_BASE, "request": {"sport": "run", "duration_min": 45}}
    b = {**_SINGLE_SESSION_BASE, "request": {"duration_min": 45, "sport": "run"}}
    assert single_session_synthesize_key(**a) == single_session_synthesize_key(**b)


def test_single_session_key_none_layer2c_locale_equals_empty_string() -> None:
    """Quick-equipment mode skips Layer 2C; None and '' must hash equivalently."""
    none_variant = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "layer2c_locale_hash": None}
    )
    empty_variant = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "layer2c_locale_hash": ""}
    )
    assert none_variant == empty_variant


def test_single_session_key_modality_locale_hash_none_equals_empty_string() -> None:
    """BM-3: quick-equipment mode + pre-BM-3 callers don't supply the modality hash;
    None and '' must collapse identically."""
    none_variant = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "layer2_modality_locale_hash": None}
    )
    empty_variant = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "layer2_modality_locale_hash": ""}
    )
    default_variant = single_session_synthesize_key(**_SINGLE_SESSION_BASE)
    assert none_variant == empty_variant == default_variant


def test_single_session_key_modality_locale_hash_set_distinguishes() -> None:
    """BM-3: populated modality_locale_hash flips the cache key vs unset baseline."""
    bare = single_session_synthesize_key(**_SINGLE_SESSION_BASE)
    with_hash = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "layer2_modality_locale_hash": "mod_locale_x"}
    )
    assert bare != with_hash


def test_single_session_key_race_modality_hints_hash_none_equals_empty_string() -> None:
    """Spec v2 §E: None and '' collapse for the single-session key."""
    none_variant = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "race_modality_hints_hash": None}
    )
    empty_variant = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "race_modality_hints_hash": ""}
    )
    default_variant = single_session_synthesize_key(**_SINGLE_SESSION_BASE)
    assert none_variant == empty_variant == default_variant


def test_single_session_key_race_modality_hints_hash_set_distinguishes() -> None:
    """Spec v2 §E: populated race_modality_hints_hash flips the key."""
    bare = single_session_synthesize_key(**_SINGLE_SESSION_BASE)
    with_hash = single_session_synthesize_key(
        **{**_SINGLE_SESSION_BASE, "race_modality_hints_hash": "hints_x"}
    )
    assert bare != with_hash


@pytest.mark.parametrize(
    "field, mutated",
    [
        ("user_id", 2),
        ("request", {"sport": "run", "duration_min": 60, "intensity": "easy"}),
        ("layer1_hash", "l1_x"),
        ("layer2c_locale_hash", "l2c_hotel"),
        ("layer2d_hash", "l2d_x"),
        ("layer3a_hash", "l3a_x"),
        ("etl_version_set", {"layer1": "v2"}),
        ("model", "claude-opus-4-6"),
        ("temperature", 0.3),
        ("max_tokens", 1501),
        ("capped_retries", 1),
        ("layer2_modality_locale_hash", "mod_locale_x"),
        ("race_modality_hints_hash", "hints_x"),
    ],
)
def test_single_session_key_depends_on_each_component(field: str, mutated: object) -> None:
    base = single_session_synthesize_key(**_SINGLE_SESSION_BASE)
    assert single_session_synthesize_key(**{**_SINGLE_SESSION_BASE, field: mutated}) != base


# ─── race_week_brief_key ────────────────────────────────────────────────────


_RACE_WEEK_BASE = dict(
    user_id=1,
    layer1_hash="l1",
    layer2a_hash="l2a",
    layer2b_hash="l2b",
    layer2c_bundle_hash="l2cb",
    layer2d_hash="l2d",
    layer2e_hash="l2e",
    layer3a_hash="l3a",
    layer3b_hash="l3b",
    prior_plan_session_window_hash="pp",
    etl_version_set={"layer1": "v1"},
    model="claude-opus-4-7",
    temperature=0.2,
    max_tokens=6000,
    capped_retries=2,
)


def test_race_week_brief_key_deterministic() -> None:
    assert race_week_brief_key(**_RACE_WEEK_BASE) == race_week_brief_key(**_RACE_WEEK_BASE)


def test_race_week_brief_key_modality_hash_none_equals_empty_string() -> None:
    """BM-3: pre-BM-3 callers don't supply the modality hash; None and ''
    must collapse identically."""
    none_variant = race_week_brief_key(
        **{**_RACE_WEEK_BASE, "layer2_modality_hash": None}
    )
    empty_variant = race_week_brief_key(
        **{**_RACE_WEEK_BASE, "layer2_modality_hash": ""}
    )
    default_variant = race_week_brief_key(**_RACE_WEEK_BASE)
    assert none_variant == empty_variant == default_variant


def test_race_week_brief_key_modality_hash_set_distinguishes() -> None:
    """BM-3: populated modality_hash flips the cache key vs unset baseline."""
    bare = race_week_brief_key(**_RACE_WEEK_BASE)
    with_hash = race_week_brief_key(
        **{**_RACE_WEEK_BASE, "layer2_modality_hash": "mod_x"}
    )
    assert bare != with_hash


def test_race_week_brief_key_race_modality_hints_hash_none_equals_empty_string() -> None:
    """Spec v2 §E: None and '' collapse for the race_week_brief key."""
    none_variant = race_week_brief_key(
        **{**_RACE_WEEK_BASE, "race_modality_hints_hash": None}
    )
    empty_variant = race_week_brief_key(
        **{**_RACE_WEEK_BASE, "race_modality_hints_hash": ""}
    )
    default_variant = race_week_brief_key(**_RACE_WEEK_BASE)
    assert none_variant == empty_variant == default_variant


def test_race_week_brief_key_race_modality_hints_hash_set_distinguishes() -> None:
    """Spec v2 §E: populated race_modality_hints_hash flips the key."""
    bare = race_week_brief_key(**_RACE_WEEK_BASE)
    with_hash = race_week_brief_key(
        **{**_RACE_WEEK_BASE, "race_modality_hints_hash": "hints_x"}
    )
    assert bare != with_hash


@pytest.mark.parametrize(
    "field, mutated",
    [
        ("user_id", 2),
        ("layer1_hash", "l1_x"),
        ("layer2a_hash", "l2a_x"),
        ("layer2b_hash", "l2b_x"),
        ("layer2c_bundle_hash", "l2cb_x"),
        ("layer2d_hash", "l2d_x"),
        ("layer2e_hash", "l2e_x"),
        ("layer3a_hash", "l3a_x"),
        ("layer3b_hash", "l3b_x"),
        ("prior_plan_session_window_hash", "pp_x"),
        ("etl_version_set", {"layer1": "v2"}),
        ("model", "claude-opus-4-6"),
        ("temperature", 0.3),
        ("max_tokens", 6001),
        ("capped_retries", 1),
        ("layer2_modality_hash", "mod_x"),
        ("race_modality_hints_hash", "hints_x"),
    ],
)
def test_race_week_brief_key_depends_on_each_component(field: str, mutated: object) -> None:
    base = race_week_brief_key(**_RACE_WEEK_BASE)
    assert race_week_brief_key(**{**_RACE_WEEK_BASE, field: mutated}) != base


# ─── cross-helper sanity ────────────────────────────────────────────────────


def test_different_entry_point_keys_differ_even_when_overlapping_inputs() -> None:
    """plan_create / race_week_brief share most inputs but produce different keys
    because their component lists differ (race_week_brief lacks plan_start_date +
    model_seam_reviewer; uses single `model` slot vs synthesizer/reviewer split)."""
    pc = plan_create_key(**_PLAN_CREATE_BASE)
    rw = race_week_brief_key(**_RACE_WEEK_BASE)
    assert pc != rw
