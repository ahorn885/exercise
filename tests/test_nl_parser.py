"""Tests for `nl_parser.py` D-64 plan-refresh intent parser runtime.

Stub-LLM unit tests covering the 15 fixtures in `NLParser_v1.md` §11.1
(TS1-TS15) + the §11.2 closed-vocab violation transform + retry / network /
short-circuit / cache semantics. No real Anthropic SDK invocation —
`_FakeAnthropicCaller` returns canned tool args per the layer3a test
precedent.

Real-LLM smoke harness against actual Sonnet 4.6 lives in
`tests/test_nl_parser_smoke.py` (env-gated via the shared
`@requires_anthropic_api_key` decorator from `tests/conftest.py`).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

import nl_parser
from layer4.cache import PER_ENTRY_PHASE_IDX_SENTINEL
from layer4.context import ParsedIntent
from nl_parser import (
    IntentParserInput,
    NL_PARSER_PROMPT_VERSION,
    NLParserError,
    _enforce_closed_locale_vocab,
    _normalize_nl_text,
    _render_user_prompt,
    _short_circuit_empty,
    build_record_parsed_intent_tool,
    nl_parser_cache_key,
    parse_intent,
)


# ─── Test doubles ───────────────────────────────────────────────────────────


_DEFAULT_TOOL_ARGS: dict[str, Any] = {
    "triggers_2a_discipline": False,
    "triggers_2b_terrain": False,
    "triggers_2c_equipment": [],
    "triggers_2d_injury": False,
    "triggers_2e_nutrition": False,
    "fatigue_signal": "normal",
    "sickness_signal": "none",
    "motivation_signal": "normal",
    "parser_confidence": "high",
    "ambiguity_notes": None,
}


def _llm_output(**overrides: Any) -> nl_parser._LLMOutput:
    args = _DEFAULT_TOOL_ARGS | overrides
    return nl_parser._LLMOutput(
        tool_args=args,
        input_tokens=120,
        output_tokens=80,
        latency_ms=900,
    )


class _FakeLLMCaller:
    """Returns canned tool args. On retry, returns the next queued response."""

    def __init__(self, responses: list[nl_parser._LLMOutput | Exception]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def __call__(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        extended_thinking_budget: int,
    ) -> nl_parser._LLMOutput:
        self.calls.append((system_prompt, user_prompt, tool_schema))
        if not self.responses:
            raise AssertionError("FakeLLMCaller exhausted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeCacheBackend:
    """Minimal in-memory CacheBackend stub. Stores one row per key."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, int], Any] = {}
        self.get_calls: list[tuple[str, int]] = []
        self.put_calls: list[dict[str, Any]] = []

    def get(self, cache_key: str, phase_idx: int = PER_ENTRY_PHASE_IDX_SENTINEL):
        self.get_calls.append((cache_key, phase_idx))
        return self.rows.get((cache_key, phase_idx))

    def put(
        self,
        *,
        cache_key: str,
        phase_idx: int,
        user_id: int,
        entry_point: str,
        phase_name: str | None,
        payload_json: str,
    ) -> None:
        self.put_calls.append(
            {
                "cache_key": cache_key,
                "phase_idx": phase_idx,
                "user_id": user_id,
                "entry_point": entry_point,
                "phase_name": phase_name,
                "payload_json": payload_json,
            }
        )

        class _Entry:
            def __init__(self, pj: str) -> None:
                self.payload_json = pj

        self.rows[(cache_key, phase_idx)] = _Entry(payload_json)


# ─── _normalize_nl_text ─────────────────────────────────────────────────────


class TestNormalizeNLText:
    def test_lowercases(self):
        assert _normalize_nl_text("I'M TIRED") == "i'm tired"

    def test_collapses_whitespace(self):
        assert _normalize_nl_text("hello\n  world\t!") == "hello world !"

    def test_empty_input(self):
        assert _normalize_nl_text("") == ""

    def test_pure_whitespace(self):
        assert _normalize_nl_text("   \n\t  ") == ""


# ─── _short_circuit_empty ───────────────────────────────────────────────────


class TestShortCircuitEmpty:
    def test_empty_returns_default(self):
        result = _short_circuit_empty("")
        assert result is not None
        assert result.parser_confidence == "high"
        assert result.ambiguity_notes is None
        assert result.fatigue_signal == "normal"
        assert result.triggers_2d_injury is False

    def test_whitespace_only_returns_default(self):
        assert _short_circuit_empty("   \n\t  ") is not None

    def test_nonempty_returns_none(self):
        assert _short_circuit_empty("I'm tired") is None


# ─── nl_parser_cache_key ────────────────────────────────────────────────────


class TestNLParserCacheKey:
    def test_deterministic(self):
        k1 = nl_parser_cache_key(user_id=42, nl_text="I'm tired")
        k2 = nl_parser_cache_key(user_id=42, nl_text="I'm tired")
        assert k1 == k2

    def test_normalization_means_whitespace_irrelevant(self):
        k1 = nl_parser_cache_key(user_id=42, nl_text="I'M    TIRED")
        k2 = nl_parser_cache_key(user_id=42, nl_text="i'm tired")
        assert k1 == k2

    def test_user_id_scopes_key(self):
        k1 = nl_parser_cache_key(user_id=42, nl_text="I'm tired")
        k2 = nl_parser_cache_key(user_id=43, nl_text="I'm tired")
        assert k1 != k2

    def test_different_text_different_key(self):
        k1 = nl_parser_cache_key(user_id=42, nl_text="I'm tired")
        k2 = nl_parser_cache_key(user_id=42, nl_text="I'm fresh")
        assert k1 != k2

    def test_sha256_hex_shape(self):
        key = nl_parser_cache_key(user_id=42, nl_text="I'm tired")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ─── _render_user_prompt ────────────────────────────────────────────────────


class TestRenderUserPrompt:
    def test_renders_tier_label_t1(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="x", tier="T1")
        )
        assert "T1 (next 2 days)" in prompt

    def test_renders_tier_label_t2(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="x", tier="T2")
        )
        assert "T2 (next 7 days)" in prompt

    def test_renders_tier_label_t3(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="x", tier="T3")
        )
        assert "T3 (next 28 days)" in prompt

    def test_unknown_tier_raises(self):
        with pytest.raises(NLParserError) as ei:
            _render_user_prompt(IntentParserInput(nl_text="x", tier="T4"))
        assert ei.value.code == "input_validation"

    def test_renders_nl_text_in_backtick_block(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="I'm tired", tier="T1")
        )
        assert "```\nI'm tired\n```" in prompt

    def test_empty_locales_renders_placeholder(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="x", tier="T1", athlete_locales=())
        )
        assert "(none configured)" in prompt

    def test_locales_render_one_per_line(self):
        prompt = _render_user_prompt(
            IntentParserInput(
                nl_text="x",
                tier="T1",
                athlete_locales=("home", "in_laws_mn"),
            )
        )
        assert "home\nin_laws_mn" in prompt

    def test_empty_injuries_renders_placeholder(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="x", tier="T1")
        )
        assert "(none active)" in prompt

    def test_injuries_render_one_per_line(self):
        prompt = _render_user_prompt(
            IntentParserInput(
                nl_text="x",
                tier="T1",
                athlete_active_injuries=("left wrist — chronic", "lower back — recovering"),
            )
        )
        assert "left wrist — chronic\nlower back — recovering" in prompt

    def test_retry_augmentation_appended(self):
        prompt = _render_user_prompt(
            IntentParserInput(nl_text="x", tier="T1"),
            retry_error="ambiguity_notes too long",
        )
        assert "Previous attempt failed schema validation" in prompt
        assert "ambiguity_notes too long" in prompt


# ─── _enforce_closed_locale_vocab ───────────────────────────────────────────


class TestEnforceClosedLocaleVocab:
    def test_all_valid_passthrough(self):
        parsed = ParsedIntent(
            triggers_2c_equipment=["home", "in_laws_mn"],
            ambiguity_notes=None,
        )
        result = _enforce_closed_locale_vocab(parsed, ["home", "in_laws_mn"])
        assert result.triggers_2c_equipment == ["home", "in_laws_mn"]
        assert result.ambiguity_notes is None

    def test_strips_unknown_slugs(self):
        parsed = ParsedIntent(
            triggers_2c_equipment=["home", "hotel_gym"],
            ambiguity_notes=None,
        )
        result = _enforce_closed_locale_vocab(parsed, ["home"])
        assert result.triggers_2c_equipment == ["home"]
        assert result.ambiguity_notes is not None
        assert "hotel_gym" in result.ambiguity_notes
        assert "stripped" in result.ambiguity_notes

    def test_appends_to_existing_ambiguity_notes(self):
        parsed = ParsedIntent(
            triggers_2c_equipment=["home", "hotel_gym"],
            ambiguity_notes="Routed 2D conservatively.",
        )
        result = _enforce_closed_locale_vocab(parsed, ["home"])
        assert "Routed 2D conservatively." in result.ambiguity_notes
        assert "hotel_gym" in result.ambiguity_notes

    def test_respects_240_char_cap(self):
        long_existing = "x" * 230
        parsed = ParsedIntent(
            triggers_2c_equipment=["foo"],
            ambiguity_notes=long_existing,
        )
        result = _enforce_closed_locale_vocab(parsed, ["home"])
        assert len(result.ambiguity_notes) <= 240

    def test_empty_slug_list_strips_all(self):
        parsed = ParsedIntent(triggers_2c_equipment=["home"], ambiguity_notes=None)
        result = _enforce_closed_locale_vocab(parsed, [])
        assert result.triggers_2c_equipment == []
        assert result.ambiguity_notes is not None


# ─── build_record_parsed_intent_tool ────────────────────────────────────────


class TestBuildRecordParsedIntentTool:
    def test_tool_name_matches_spec(self):
        tool = build_record_parsed_intent_tool()
        assert tool["name"] == "record_parsed_intent"

    def test_schema_requires_10_fields(self):
        tool = build_record_parsed_intent_tool()
        required = tool["input_schema"]["required"]
        assert len(required) == 10
        assert "raw_text" not in required

    def test_additional_properties_false(self):
        tool = build_record_parsed_intent_tool()
        assert tool["input_schema"]["additionalProperties"] is False

    def test_soft_signal_enums(self):
        tool = build_record_parsed_intent_tool()
        props = tool["input_schema"]["properties"]
        assert props["fatigue_signal"]["enum"] == ["fresh", "normal", "tired", "wiped"]
        assert props["sickness_signal"]["enum"] == ["none", "recovering", "active"]
        assert props["motivation_signal"]["enum"] == ["low", "normal", "high"]

    def test_parser_confidence_enum(self):
        tool = build_record_parsed_intent_tool()
        assert tool["input_schema"]["properties"]["parser_confidence"]["enum"] == [
            "high",
            "medium",
            "low",
        ]

    def test_ambiguity_notes_nullable_with_cap(self):
        tool = build_record_parsed_intent_tool()
        prop = tool["input_schema"]["properties"]["ambiguity_notes"]
        assert prop["type"] == ["string", "null"]
        assert prop["maxLength"] == 240

    def test_prompt_version_constant_is_one(self):
        assert NL_PARSER_PROMPT_VERSION == 1


# ─── parse_intent — TS1..TS15 fixtures per NLParser_v1.md §11.1 ─────────────


class TestParseIntentFixtures:
    """Mirror the 15 fixtures in NLParser_v1.md §11.1 (TS1..TS15)."""

    def _run(self, parser_input: IntentParserInput, **tool_overrides: Any) -> ParsedIntent:
        caller = _FakeLLMCaller([_llm_output(**tool_overrides)])
        return parse_intent(parser_input, user_id=1, llm_caller=caller)

    def test_ts1_im_tired(self):
        result = self._run(
            IntentParserInput(nl_text="I'm tired", tier="T1"),
            fatigue_signal="tired",
        )
        assert result.fatigue_signal == "tired"
        assert result.triggers_2d_injury is False
        assert result.parser_confidence == "high"
        assert result.ambiguity_notes is None
        assert result.raw_text == "I'm tired"

    def test_ts2_tweaked_my_ankle(self):
        result = self._run(
            IntentParserInput(nl_text="I tweaked my ankle", tier="T1"),
            triggers_2d_injury=True,
        )
        assert result.triggers_2d_injury is True
        assert result.ambiguity_notes is None

    def test_ts3_my_ankle_hurts_again(self):
        result = self._run(
            IntentParserInput(
                nl_text="my ankle hurts again",
                tier="T1",
                athlete_active_injuries=("right ankle — recovering",),
            ),
            triggers_2d_injury=True,
            ambiguity_notes="Re-aggravation vs. update unclear; routing conservatively to 2D.",
        )
        assert result.triggers_2d_injury is True
        assert result.ambiguity_notes is not None

    def test_ts4_my_ankle_feels_better(self):
        result = self._run(
            IntentParserInput(
                nl_text="my ankle feels better",
                tier="T1",
                athlete_active_injuries=("right ankle — recovering",),
            ),
            triggers_2d_injury=False,
        )
        assert result.triggers_2d_injury is False
        assert result.ambiguity_notes is None

    def test_ts5_at_my_in_laws(self):
        result = self._run(
            IntentParserInput(
                nl_text="I'm at my in-laws",
                tier="T1",
                athlete_locales=("home", "in_laws_mn"),
            ),
            triggers_2c_equipment=["in_laws_mn"],
            parser_confidence="medium",
        )
        assert result.triggers_2c_equipment == ["in_laws_mn"]
        assert result.parser_confidence == "medium"

    def test_ts6_hotel_gym_out_of_vocab(self):
        result = self._run(
            IntentParserInput(
                nl_text="I'm at my hotel gym",
                tier="T1",
                athlete_locales=("home",),
            ),
            triggers_2c_equipment=[],
            ambiguity_notes="Athlete mentioned 'hotel gym'; out of vocab.",
        )
        assert result.triggers_2c_equipment == []
        assert "hotel gym" in result.ambiguity_notes

    def test_ts7_cooked_from_race(self):
        result = self._run(
            IntentParserInput(nl_text="cooked from yesterday's race", tier="T1"),
            fatigue_signal="wiped",
        )
        assert result.fatigue_signal == "wiped"

    def test_ts8_i_have_the_flu(self):
        result = self._run(
            IntentParserInput(nl_text="I have the flu", tier="T1"),
            sickness_signal="active",
        )
        assert result.sickness_signal == "active"

    def test_ts9_starting_kayaking(self):
        result = self._run(
            IntentParserInput(nl_text="I'm starting kayaking next month", tier="T3"),
            triggers_2a_discipline=True,
        )
        assert result.triggers_2a_discipline is True

    def test_ts10_gi_issues(self):
        result = self._run(
            IntentParserInput(nl_text="GI issues during the long runs lately", tier="T2"),
            triggers_2e_nutrition=True,
        )
        assert result.triggers_2e_nutrition is True

    def test_ts11_tier_mismatch(self):
        result = self._run(
            IntentParserInput(nl_text="regenerate the next month", tier="T1"),
            ambiguity_notes="Tier mismatch: T1 selected but T3 phrasing.",
        )
        assert "Tier mismatch" in result.ambiguity_notes

    def test_ts12_not_feeling_it(self):
        result = self._run(
            IntentParserInput(nl_text="not feeling it this week", tier="T2"),
            motivation_signal="low",
        )
        assert result.motivation_signal == "low"

    def test_ts13_empty_short_circuit(self):
        caller = _FakeLLMCaller([])
        result = parse_intent(
            IntentParserInput(nl_text="", tier="T1"),
            user_id=1,
            llm_caller=caller,
        )
        assert caller.calls == []
        assert result.parser_confidence == "high"
        assert result.ambiguity_notes is None
        assert result.raw_text == ""
        assert result.fatigue_signal == "normal"

    def test_ts13_whitespace_only_short_circuit(self):
        caller = _FakeLLMCaller([])
        result = parse_intent(
            IntentParserInput(nl_text="   \n  \t ", tier="T1"),
            user_id=1,
            llm_caller=caller,
        )
        assert caller.calls == []
        assert result.parser_confidence == "high"

    def test_ts14_my_back_again_with_active_injury(self):
        result = self._run(
            IntentParserInput(
                nl_text="my back again",
                tier="T1",
                athlete_active_injuries=("lower back — chronic-managed",),
            ),
            triggers_2d_injury=True,
            ambiguity_notes="Re-aggravation vs. existing-injury update unclear.",
        )
        assert result.triggers_2d_injury is True
        assert result.ambiguity_notes is not None

    def test_ts15_travel_without_slug(self):
        result = self._run(
            IntentParserInput(nl_text="travel Wed-Fri", tier="T2"),
            parser_confidence="medium",
            ambiguity_notes="Travel context unclear without locale slug.",
        )
        assert result.parser_confidence == "medium"
        assert "Travel" in result.ambiguity_notes


# ─── §11.2 closed-vocab violation post-LLM transform ────────────────────────


class TestClosedLocaleVocabViolation:
    def test_unknown_slug_stripped_and_noted(self):
        caller = _FakeLLMCaller(
            [_llm_output(triggers_2c_equipment=["nonexistent_slug"])]
        )
        result = parse_intent(
            IntentParserInput(
                nl_text="I'm somewhere",
                tier="T1",
                athlete_locales=("home",),
            ),
            user_id=1,
            llm_caller=caller,
        )
        assert result.triggers_2c_equipment == []
        assert result.ambiguity_notes is not None
        assert "nonexistent_slug" in result.ambiguity_notes
        assert "stripped" in result.ambiguity_notes


# ─── Retry semantics ────────────────────────────────────────────────────────


class TestParseIntentRetry:
    def test_first_attempt_invalid_second_attempt_valid(self):
        caller = _FakeLLMCaller(
            [
                _llm_output(fatigue_signal="exhausted"),  # invalid enum
                _llm_output(fatigue_signal="wiped"),  # valid retry
            ]
        )
        result = parse_intent(
            IntentParserInput(nl_text="I'm cooked", tier="T1"),
            user_id=1,
            llm_caller=caller,
        )
        assert result.fatigue_signal == "wiped"
        assert len(caller.calls) == 2
        # Retry user prompt carries the validation error
        assert "Previous attempt failed schema validation" in caller.calls[1][1]

    def test_second_failure_raises_nlparser_error(self):
        caller = _FakeLLMCaller(
            [
                _llm_output(fatigue_signal="bogus_1"),
                _llm_output(fatigue_signal="bogus_2"),
            ]
        )
        with pytest.raises(NLParserError) as ei:
            parse_intent(
                IntentParserInput(nl_text="I'm cooked", tier="T1"),
                user_id=1,
                llm_caller=caller,
            )
        assert ei.value.code == "schema_violation"

    def test_zero_retries_raises_on_first_failure(self):
        caller = _FakeLLMCaller([_llm_output(fatigue_signal="bogus")])
        with pytest.raises(NLParserError) as ei:
            parse_intent(
                IntentParserInput(nl_text="x", tier="T1"),
                user_id=1,
                llm_caller=caller,
                capped_retries=0,
            )
        assert ei.value.code == "schema_violation"


class TestParseIntentNetworkError:
    def test_caller_exception_propagates_as_network_error(self):
        net_err = NLParserError("network", detail="connection refused")
        caller = _FakeLLMCaller([net_err])
        with pytest.raises(NLParserError) as ei:
            parse_intent(
                IntentParserInput(nl_text="x", tier="T1"),
                user_id=1,
                llm_caller=caller,
            )
        assert ei.value.code == "network"


# ─── Cache integration ──────────────────────────────────────────────────────


class TestParseIntentCache:
    def test_miss_writes_then_hit_returns_cached(self):
        cache = _FakeCacheBackend()
        caller = _FakeLLMCaller([_llm_output(fatigue_signal="tired")])
        parser_input = IntentParserInput(nl_text="I'm tired", tier="T1")

        first = parse_intent(
            parser_input, user_id=42, cache_backend=cache, llm_caller=caller
        )
        assert first.fatigue_signal == "tired"
        assert len(caller.calls) == 1
        assert len(cache.put_calls) == 1
        assert cache.put_calls[0]["entry_point"] == "nl_parser_parse_intent"
        assert cache.put_calls[0]["user_id"] == 42

        caller2 = _FakeLLMCaller([])
        second = parse_intent(
            parser_input, user_id=42, cache_backend=cache, llm_caller=caller2
        )
        assert second.fatigue_signal == "tired"
        assert caller2.calls == []

    def test_short_circuit_does_not_consult_cache(self):
        cache = _FakeCacheBackend()
        caller = _FakeLLMCaller([])
        parse_intent(
            IntentParserInput(nl_text="", tier="T1"),
            user_id=42,
            cache_backend=cache,
            llm_caller=caller,
        )
        assert cache.get_calls == []
        assert cache.put_calls == []

    def test_cache_round_trip_preserves_payload(self):
        cache = _FakeCacheBackend()
        caller = _FakeLLMCaller(
            [
                _llm_output(
                    triggers_2d_injury=True,
                    ambiguity_notes="conservative routing on 'my back again'",
                    parser_confidence="medium",
                )
            ]
        )
        parser_input = IntentParserInput(
            nl_text="my back again",
            tier="T1",
            athlete_active_injuries=("lower back — chronic",),
        )
        first = parse_intent(
            parser_input, user_id=42, cache_backend=cache, llm_caller=caller
        )
        second = parse_intent(
            parser_input, user_id=42, cache_backend=cache, llm_caller=_FakeLLMCaller([])
        )
        assert second.triggers_2d_injury == first.triggers_2d_injury
        assert second.ambiguity_notes == first.ambiguity_notes
        assert second.parser_confidence == first.parser_confidence
        assert second.raw_text == first.raw_text


# ─── raw_text driver-stamping ───────────────────────────────────────────────


class TestRawTextStamping:
    def test_raw_text_stamped_post_call(self):
        caller = _FakeLLMCaller([_llm_output()])
        result = parse_intent(
            IntentParserInput(nl_text="I'M  TIRED!", tier="T1"),
            user_id=1,
            llm_caller=caller,
        )
        # Verbatim — no normalization on the stamped field.
        assert result.raw_text == "I'M  TIRED!"

    def test_short_circuit_raw_text_stamped(self):
        caller = _FakeLLMCaller([])
        result = parse_intent(
            IntentParserInput(nl_text="", tier="T1"),
            user_id=1,
            llm_caller=caller,
        )
        assert result.raw_text == ""
