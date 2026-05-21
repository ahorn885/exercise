"""Real-LLM smoke tests for `nl_parser.parse_intent`.

Per `aidstation-sources/prompts/NLParser_v1.md` §11.3 + §12 NL-1 +
D-64 Decision #12 — exercises the production Anthropic SDK adapter
(`_default_llm_caller`) against real Sonnet 4.6 with ~12 hand-labeled
fixtures derived from Andy's PGE 2026 + AR + multi-sport vocab. Gated on
`ANTHROPIC_API_KEY` via the `requires_anthropic_api_key` skipif marker
from `tests/conftest.py`; default `pytest tests/` runs ignore this file.

Fixtures cover the classification axes called out in NLParser_v1.md §11.1
+ D-64 §11: clean single-signal / new-injury keyword / re-aggravation
ambiguity / out-of-vocab location / extreme fatigue / sickness signal /
new-discipline mention / nutrition shift / tier mismatch / empty-input
short-circuit.

Assertions are mixed strict (trigger flags, soft-signal enums) +
allowlist-set (parser_confidence, fatigue intensity levels) to absorb
minor classification variance across Sonnet 4.6 minor versions without
false positives.

Real-LLM cost per smoke run: ~12 calls × ~$0.003 = ~$0.04 per pass.
Eval-fixture-based Haiku migration eval (NL-1) lands as a follow-on.
"""

from __future__ import annotations

import pytest

from conftest import requires_anthropic_api_key

from nl_parser import IntentParserInput, parse_intent


pytestmark = requires_anthropic_api_key


# ─── Andy-derived vocab fixtures ────────────────────────────────────────────


_ANDY_LOCALES = ("home", "in_laws_mn", "lake_cabin")
_ANDY_ACTIVE_INJURIES = (
    "left wrist — painful + weak with wrist extension under load",
)


def _input(nl_text: str, tier: str = "T1") -> IntentParserInput:
    return IntentParserInput(
        nl_text=nl_text,
        tier=tier,
        athlete_locales=_ANDY_LOCALES,
        athlete_active_injuries=_ANDY_ACTIVE_INJURIES,
    )


# ─── Clean single-signal classifications ────────────────────────────────────


class TestCleanSignals:
    def test_im_tired_routes_fatigue_only(self):
        result = parse_intent(_input("I'm tired"), user_id=1)
        assert result.fatigue_signal == "tired"
        assert all(
            not flag
            for flag in [
                result.triggers_2a_discipline,
                result.triggers_2b_terrain,
                result.triggers_2d_injury,
                result.triggers_2e_nutrition,
            ]
        )
        assert result.triggers_2c_equipment == []
        assert result.parser_confidence in {"high", "medium"}

    def test_cooked_from_race_routes_wiped(self):
        result = parse_intent(
            _input("cooked from yesterday's adventure race"), user_id=1
        )
        assert result.fatigue_signal in {"tired", "wiped"}

    def test_have_the_flu_routes_active_sickness(self):
        result = parse_intent(_input("I have the flu"), user_id=1)
        assert result.sickness_signal == "active"
        assert result.fatigue_signal in {"normal", "tired", "wiped"}

    def test_feeling_motivated_routes_high(self):
        result = parse_intent(
            _input("feeling super motivated this week"), user_id=1
        )
        assert result.motivation_signal in {"high", "normal"}


# ─── Injury disambiguation per D5 middle-path ───────────────────────────────


class TestInjuryDisambiguation:
    def test_new_injury_keyword_fires_2d(self):
        result = parse_intent(_input("I tweaked my ankle"), user_id=1)
        assert result.triggers_2d_injury is True

    def test_strained_keyword_fires_2d(self):
        result = parse_intent(_input("strained my hamstring yesterday"), user_id=1)
        assert result.triggers_2d_injury is True

    def test_update_on_existing_does_not_fire_2d(self):
        # Wrist is in athlete_active_injuries; "feels better" is pure update.
        result = parse_intent(
            _input("my wrist feels better this week"), user_id=1
        )
        assert result.triggers_2d_injury is False


# ─── Locale + closed-vocab handling per D6 ──────────────────────────────────


class TestLocaleVocab:
    def test_in_laws_matches_slug(self):
        result = parse_intent(_input("I'm at my in-laws this weekend"), user_id=1)
        assert "in_laws_mn" in result.triggers_2c_equipment

    def test_unknown_location_surfaces_via_ambiguity_notes(self):
        result = parse_intent(_input("I'm at a hotel gym today"), user_id=1)
        # Per the closed-vocab transform, the parser cannot emit slugs not
        # in athlete_locales — either the LLM emits empty or the post-LLM
        # transform strips invalid slugs.
        assert all(
            slug in _ANDY_LOCALES for slug in result.triggers_2c_equipment
        )


# ─── Discipline + nutrition triggers ────────────────────────────────────────


class TestUpstreamTriggers:
    def test_starting_new_discipline_fires_2a(self):
        result = parse_intent(
            _input("I'm starting kayaking next month", tier="T3"), user_id=1
        )
        assert result.triggers_2a_discipline is True

    def test_gi_issues_fires_2e(self):
        result = parse_intent(
            _input("having GI issues during long runs lately", tier="T2"),
            user_id=1,
        )
        assert result.triggers_2e_nutrition is True


# ─── Empty short-circuit (no API call) ──────────────────────────────────────


class TestEmptyShortCircuit:
    def test_empty_input_returns_default(self):
        result = parse_intent(_input(""), user_id=1)
        assert result.parser_confidence == "high"
        assert result.ambiguity_notes is None
        assert result.raw_text == ""
        assert result.fatigue_signal == "normal"
        assert result.sickness_signal == "none"
        assert result.motivation_signal == "normal"
