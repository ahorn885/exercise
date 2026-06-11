"""D-64 plan-refresh NL intent parser runtime.

Companion contract: `aidstation-sources/prompts/NLParser_v1.md`.
Design source: `aidstation-sources/designs/Plan_Refresh_D64_Design_v1.md` §5.

Single LLM-backed classifier: athlete's free-text plan-refresh note +
tier + closed-vocab locale list + active-injury summary → `ParsedIntent`
(5 trigger flags + 3 soft signals + parser_confidence + ambiguity_notes;
`raw_text` driver-stamped post-call per D7).

Routing contract:
- Empty/whitespace-only NL text → short-circuit; no LLM call; return
  default-flag ParsedIntent.
- Schema-violation → single capped retry with the validation error
  injected into the user prompt; on second failure raise
  `NLParserError("schema_violation", ...)`.
- Network/SDK error → no retry inside the parser; raise
  `NLParserError("network", ...)`.

The caller (`routes/plan_refresh.py`) catches `NLParserError` and
substitutes `layer4.plan_refresh._default_parsed_intent()` per D-64 §5.4.

Caching per D-64 §5.3 + NLParser_v1.md §10: key derived from
`(user_id, sha256(normalize(nl_text)), NL_PARSER_PROMPT_VERSION)`. Cache
backend is the shared `layer4.cache.CacheBackend`; entry-point label is
`nl_parser_parse_intent` (registered in `VALID_ENTRY_POINTS` superset,
NOT `LAYER4_ENTRY_POINTS` — parser cache is athlete-scoped, not
Layer-4-scoped, so it stays out of Layer 4 invalidation cascades).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import ValidationError

from layer4.cache import CacheBackend, PER_ENTRY_PHASE_IDX_SENTINEL
from layer4.context import ParsedIntent


# ─── Constants ───────────────────────────────────────────────────────────────


NL_PARSER_PROMPT_VERSION = 1
"""Bumped on any behaviourally-significant prompt change; invalidates the
parser cache for all athletes. Per NLParser_v1.md D12 the constant lives
in the runtime module, not the markdown — the markdown is a design doc."""

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_MAX_TOKENS = 1024
_DEFAULT_THINKING_BUDGET = 0
_DEFAULT_CAPPED_RETRIES = 1

_AMBIGUITY_NOTES_MAX_CHARS = 240

_TOOL_NAME = "record_parsed_intent"
_ENTRY_POINT_LABEL = "nl_parser_parse_intent"


# ─── Input dataclass + errors ───────────────────────────────────────────────


@dataclass(frozen=True)
class IntentParserInput:
    """Per `Plan_Refresh_D64_Design_v1.md` §5.1."""

    nl_text: str
    tier: str  # 'T1' | 'T2' | 'T3' — validated at call time
    athlete_locales: tuple[str, ...] = field(default_factory=tuple)
    athlete_active_injuries: tuple[str, ...] = field(default_factory=tuple)


class NLParserError(RuntimeError):
    """Raised by `parse_intent` on unrecoverable schema-violation OR
    network/SDK failure. The route layer catches this + substitutes
    `_default_parsed_intent()` per D-64 §5.4."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        msg = f"NL parser error: {code}"
        if detail:
            msg = f"{msg} — {detail}"
        super().__init__(msg)


# ─── LLM caller protocol (mirrors layer3a/builder.py shape) ─────────────────


@dataclass
class _LLMOutput:
    """Raw output from the LLM call before payload assembly."""

    tool_args: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int


LLMCaller = Callable[
    [str, str, dict[str, Any], str, float, int, int],
    _LLMOutput,
]
"""Signature: `(system_prompt, user_prompt, tool_schema, model, temperature,
max_tokens, extended_thinking_budget) -> _LLMOutput`. Production default is
`_default_llm_caller` (Anthropic SDK); tests inject a stub."""


def _default_llm_caller(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> _LLMOutput:
    """Production LLM caller — Anthropic SDK with forced tool-use per D3,
    no extended thinking per D2. Tests inject a stub instead."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise NLParserError(
            "network",
            detail="ANTHROPIC_API_KEY environment variable is not set",
        )
    client = anthropic.Anthropic(api_key=api_key)

    request_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "tools": [tool_schema],
        "tool_choice": {"type": "tool", "name": tool_schema["name"]},
    }
    if extended_thinking_budget > 0:
        request_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": extended_thinking_budget,
        }

    start = time.monotonic()
    try:
        msg = client.messages.create(**request_kwargs)
    except Exception as exc:
        raise NLParserError("network", detail=str(exc)) from exc
    latency_ms = int((time.monotonic() - start) * 1000)

    tool_args: dict[str, Any] | None = None
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_schema["name"]:
            tool_args = dict(block.input)
            break
    if tool_args is None:
        raise NLParserError(
            "schema_violation",
            detail=f"LLM did not emit a {tool_schema['name']} tool_use block",
        )

    return _LLMOutput(
        tool_args=tool_args,
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
        latency_ms=latency_ms,
    )


# ─── Tool schema (full ParsedIntent mirror sans raw_text per D4) ─────────────


def build_record_parsed_intent_tool() -> dict[str, Any]:
    """Tool schema mirrors `ParsedIntent` MINUS `raw_text` (driver-stamped
    post-hoc per D7). Full `additionalProperties: false` at every level
    per D3."""
    return {
        "name": _TOOL_NAME,
        "description": (
            "Emit the structured intent classification for an athlete's "
            "natural-language plan-refresh context. Required."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "triggers_2a_discipline",
                "triggers_2b_terrain",
                "triggers_2c_equipment",
                "triggers_2d_injury",
                "triggers_2e_nutrition",
                "fatigue_signal",
                "sickness_signal",
                "motivation_signal",
                "parser_confidence",
                "ambiguity_notes",
            ],
            "properties": {
                "triggers_2a_discipline": {
                    "type": "boolean",
                    "description": (
                        "TRUE if the athlete mentions starting / adopting a "
                        "new discipline (e.g., 'I'm starting kayaking', "
                        "'switching to triathlon'). Existing-discipline "
                        "mentions ('I'm running tomorrow') do NOT trigger."
                    ),
                },
                "triggers_2b_terrain": {
                    "type": "boolean",
                    "description": (
                        "TRUE if the athlete mentions a new terrain context "
                        "that changes the race or training surface (e.g., "
                        "'I'll be in the mountains', 'event moved to a sand "
                        "course'). Routine training-day terrain ('quick trail "
                        "run') does NOT trigger."
                    ),
                },
                "triggers_2c_equipment": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of locale slugs (from the closed athlete_locales "
                        "vocabulary) the athlete mentioned. Empty list if no "
                        "locale-context shift. NEVER emit slugs not present "
                        "in the athlete_locales input — surface unknown "
                        "locations via ambiguity_notes."
                    ),
                },
                "triggers_2d_injury": {
                    "type": "boolean",
                    "description": (
                        "TRUE if the athlete mentions a NEW injury or fresh "
                        "aggravation. Conservative bias: ambiguous phrasings "
                        "→ TRUE + ambiguity_notes. Pure update-on-existing "
                        "('my ankle feels better', 'lower back healing') → "
                        "FALSE."
                    ),
                },
                "triggers_2e_nutrition": {
                    "type": "boolean",
                    "description": (
                        "TRUE if the athlete mentions a nutrition-context "
                        "shift (e.g., 'GI issues during long runs', "
                        "'switching to plant-based', 'cutting weight for "
                        "race'). Generic energy mentions ('I'm hungry') do "
                        "NOT trigger; those route to fatigue_signal."
                    ),
                },
                "fatigue_signal": {
                    "type": "string",
                    "enum": ["fresh", "normal", "tired", "wiped"],
                    "description": (
                        "Athlete's stated energy level. 'normal' is the "
                        "default for unclassifiable / silent input."
                    ),
                },
                "sickness_signal": {
                    "type": "string",
                    "enum": ["none", "recovering", "active"],
                    "description": (
                        "'active' for current sickness ('I have the flu'). "
                        "'recovering' for tail-of-illness ('coming off a "
                        "cold'). 'none' is the default."
                    ),
                },
                "motivation_signal": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": (
                        "'low' for explicit demotivation. 'high' for "
                        "explicit drive. 'normal' is the default."
                    ),
                },
                "parser_confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": (
                        "'high' when the NL text contains clear signals "
                        "matching the schema. 'medium' for partial signals "
                        "or single-axis ambiguity. 'low' when the parser "
                        "had to guess across multiple axes — paired with "
                        "ambiguity_notes."
                    ),
                },
                "ambiguity_notes": {
                    "type": ["string", "null"],
                    "maxLength": _AMBIGUITY_NOTES_MAX_CHARS,
                    "description": (
                        "Single-sentence explanation when the parser could "
                        "not classify cleanly OR routed conservatively under "
                        "ambiguity OR mentioned an out-of-vocab "
                        "location/injury. NULL when classification was "
                        "unambiguous."
                    ),
                },
            },
        },
    }


# ─── Prompts (verbatim from NLParser_v1.md §5 + §6) ─────────────────────────


_SYSTEM_PROMPT = """\
You are an intent classifier for an endurance-training app's plan-refresh
surface. The athlete writes a free-text note ("I'm tired" / "tweaked my
ankle" / "at my in-laws this weekend") and your job is to route that note
to the right downstream actions via the `record_parsed_intent` tool.

You are NOT a coach. You do not give advice. You do not narrate. You
classify the input into the schema and emit a tool call. That's the whole
job.

Hard rules:

1. Output mechanism: emit exactly one `record_parsed_intent` tool call.
   No free-form text outside the tool. No partial fills — every field in
   the schema is required.

2. Conservative bias on routing flags. The 5 trigger flags (2A, 2B, 2C,
   2D, 2E) cause downstream LLM re-runs. Over-firing wastes compute but
   produces a correct refresh; under-firing skips a re-run the athlete
   needed. When in doubt, fire the flag AND populate ambiguity_notes
   explaining what you weren't sure about.

3. Trigger flag rules (each is a separate decision):
   - triggers_2a_discipline: TRUE when the athlete mentions starting,
     adopting, dropping, or switching a discipline. FALSE for routine
     training-day mentions of an existing discipline. Existing
     disciplines come from the athlete's profile (not shown here — you
     infer from "starting" / "switching" / "new" language).
   - triggers_2b_terrain: TRUE when the athlete mentions a NEW terrain
     context (event moved, going to a different terrain region for
     training, course surface changed). FALSE for routine training-day
     terrain ("trail run this morning").
   - triggers_2c_equipment: list of locale slugs FROM the closed
     athlete_locales vocabulary the athlete mentioned. If the athlete
     mentions a location NOT in the configured vocabulary ("hotel gym",
     "the new gym downtown"), leave this list empty and explain in
     ambiguity_notes. NEVER invent slugs.
   - triggers_2d_injury: TRUE on new-injury or fresh-aggravation language
     ("tweaked", "hurt", "strained", "started hurting", "sharp pain",
     "sudden", "twisted", "pulled", "feels off"). FALSE on
     update-on-existing language ("feels better", "healing well", "less
     pain", "PT cleared me"). If the athlete mentions a body part that
     is in athlete_active_injuries AND uses ambiguous language ("my back
     again"), default TRUE and populate ambiguity_notes ("Re-aggravation
     vs. existing-injury update unclear from 'my back again'; routing
     conservatively to 2D.").
   - triggers_2e_nutrition: TRUE on nutrition-context shifts ("GI issues
     during long runs", "switching to plant-based", "cutting for race",
     "fueling experiment"). FALSE on generic energy ("I'm hungry",
     "low blood sugar this morning" — those are fatigue, not 2E).

4. Soft-signal rules (each is a separate dimension; signals never override
   triggers; multiple signals can fire simultaneously):
   - fatigue_signal:
     * "fresh"   — explicit fresh-feeling ("feeling great", "fully
                   recovered", "sharp", "primed", "popped off the line").
     * "tired"   — moderate fatigue ("a bit tired", "low energy",
                   "sluggish", "heavy legs").
     * "wiped"   — explicit-extreme ("cooked", "destroyed", "wrecked",
                   "blown up", "shattered", "nuked", "I'm done",
                   "completely smoked").
     * "normal"  — default; no fatigue signal in the text.
   - sickness_signal:
     * "active"     — current sickness ("I have the flu", "fever today",
                      "sick as a dog", "throwing up").
     * "recovering" — tail of illness ("coming off a cold", "still
                      congested but better", "post-flu").
     * "none"       — default.
   - motivation_signal:
     * "high"   — explicit drive ("feeling super motivated", "ready to
                  push", "want to crush this week").
     * "low"    — explicit demotivation ("not feeling it", "dreading
                  workouts", "lost my mojo", "going through the
                  motions").
     * "normal" — default.

5. parser_confidence:
   - "high"   — text contains clear signals matching the schema with no
                ambiguity. Single-axis input ("I'm tired") classifies
                cleanly and is "high" even though it's terse.
   - "medium" — single-axis ambiguity. E.g., "I'm at my in-laws" — clear
                location signal but the specific slug match is unclear.
   - "low"    — multi-axis ambiguity OR garbled input you cannot
                classify confidently. Paired with substantive
                ambiguity_notes.

6. ambiguity_notes:
   - Populate with a single sentence when:
     (a) You routed a trigger conservatively under ambiguity (D5 case).
     (b) The athlete mentioned an out-of-vocab location (D6 case).
     (c) The athlete mentioned multiple axes and you had to choose
         which to elevate.
     (d) You set parser_confidence='low'.
   - Leave NULL when classification was unambiguous.
   - Cap: 240 chars. One sentence. No coaching tone — internal-flag
     style ("Re-aggravation vs. update unclear from 'my back again'").

7. Tier context. The tier input ('T1', 'T2', 'T3') tells you the refresh
   horizon. Most NL classification is tier-agnostic — "I'm tired" means
   tired on any tier. BUT: if the athlete's text contradicts the tier
   (e.g., T1 with "regenerate the next month" — that's T3 phrasing on a
   2-day tier), note the mismatch in ambiguity_notes and classify the
   in-tier signals only. Do NOT re-tier; the caller picked the tier.

8. Empty / silent input: this should not reach you (the runtime
   short-circuits empty input before invoking you). If it does, default
   every field to its default value (all flags FALSE, signals 'normal' /
   'none' / 'normal', parser_confidence='high', ambiguity_notes=NULL).

9. Forbidden output:
   - No coaching advice. Not your job.
   - No injury diagnosis ("sounds like IT band syndrome") — Layer 2D's
     territory.
   - No discipline recommendations ("you should try cycling") — Layer 4.
   - No re-tiering ("I'd suggest T3 instead") — caller decides.
   - No speculation beyond the text. If the athlete didn't say something,
     you don't infer it.

10. Voice for ambiguity_notes: terse, factual, internal-flag style. NOT
    athlete-facing — but the athlete MAY see it in the refresh diff per
    D-64 §9. Examples of good ambiguity_notes:
    - "Re-aggravation vs. existing-injury update unclear from 'my back
      again'; routing conservatively to 2D."
    - "Athlete mentioned 'hotel gym' which is not in their configured
      locales; no 2C re-run triggered."
    - "Tier mismatch: T1 selected but athlete asked to regenerate the
      next month; classified 2-day signals only."
    Avoid: "I'm not totally sure but..." / "It seems like..." / any
    first-person hedge."""


_USER_PROMPT_TEMPLATE = """\
Athlete's plan-refresh note:

```
{nl_text}
```

Tier: {tier_label}
Configured locales (closed vocabulary for triggers_2c_equipment):
{athlete_locales_block}

Active injuries (read-only context for triggers_2d_injury disambiguation):
{athlete_active_injuries_block}

Classify the note via the `record_parsed_intent` tool. Apply the
conservative-bias rule on triggers; default soft signals to 'normal' /
'none' / 'normal' when not explicitly signaled. Populate ambiguity_notes
only when you routed conservatively, mentioned out-of-vocab terms, or set
parser_confidence='low'."""


_RETRY_AUGMENTATION = """\

Previous attempt failed schema validation: {error_message}

Re-emit a valid `record_parsed_intent` tool call addressing the error
above. Do not change unrelated fields."""


_TIER_LABELS = {
    "T1": "T1 (next 2 days)",
    "T2": "T2 (next 7 days)",
    "T3": "T3 (next 28 days)",
}


# ─── Helpers ────────────────────────────────────────────────────────────────


def _normalize_nl_text(text: str) -> str:
    """Lowercase + whitespace-collapse per NLParser_v1.md §10.1."""
    return " ".join(text.lower().split())


def _short_circuit_empty(nl_text: str) -> ParsedIntent | None:
    """Per §1.3: empty/whitespace-only input bypasses the LLM call and
    returns a default-flag ParsedIntent. Caller passes the raw nl_text
    so `raw_text` is post-stamped at the parse_intent seam."""
    if nl_text.strip() == "":
        return ParsedIntent(parser_confidence="high", ambiguity_notes=None)
    return None


def _render_tier_label(tier: str) -> str:
    label = _TIER_LABELS.get(tier)
    if label is None:
        raise NLParserError(
            "input_validation",
            detail=f"tier={tier!r} not in {sorted(_TIER_LABELS)}",
        )
    return label


def _render_block(entries: tuple[str, ...] | list[str], empty_text: str) -> str:
    if not entries:
        return empty_text
    return "\n".join(entries)


def _render_user_prompt(
    parser_input: IntentParserInput, *, retry_error: str | None = None
) -> str:
    body = _USER_PROMPT_TEMPLATE.format(
        nl_text=parser_input.nl_text,
        tier_label=_render_tier_label(parser_input.tier),
        athlete_locales_block=_render_block(
            parser_input.athlete_locales, "(none configured)"
        ),
        athlete_active_injuries_block=_render_block(
            parser_input.athlete_active_injuries, "(none active)"
        ),
    )
    if retry_error is not None:
        body += _RETRY_AUGMENTATION.format(error_message=retry_error)
    return body


def _enforce_closed_locale_vocab(
    parsed: ParsedIntent,
    allowed_slugs: tuple[str, ...] | list[str],
) -> ParsedIntent:
    """Strip any triggers_2c_equipment entries not in allowed_slugs.
    Append a telemetry note to ambiguity_notes when stripping fires.
    NLParser_v1.md §8.2."""
    allowed_set = set(allowed_slugs)
    invalid = [s for s in parsed.triggers_2c_equipment if s not in allowed_set]
    if not invalid:
        return parsed
    stripped = [s for s in parsed.triggers_2c_equipment if s in allowed_set]
    note_suffix = f"Parser emitted unknown locale slug(s) {invalid}; stripped."
    if parsed.ambiguity_notes:
        new_notes = f"{parsed.ambiguity_notes} {note_suffix}".strip()
    else:
        new_notes = note_suffix
    return parsed.model_copy(
        update={
            "triggers_2c_equipment": stripped,
            "ambiguity_notes": new_notes[:_AMBIGUITY_NOTES_MAX_CHARS],
        }
    )


def nl_parser_cache_key(*, user_id: int, nl_text: str) -> str:
    """Per NLParser_v1.md §10.1: sha256(user_id || sha256(normalize(text))
    || NL_PARSER_PROMPT_VERSION). Tier is intentionally omitted per the
    ratified design — tier-conditioned classification (e.g., the §5 rule
    7 tier-mismatch ambiguity_notes) may cache-leak across tiers; tracked
    in NLParser_v1.md §12 NL-2 as a v2 tuning candidate."""
    normalized = _normalize_nl_text(nl_text)
    text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    components = (str(user_id), text_hash, str(NL_PARSER_PROMPT_VERSION))
    return hashlib.sha256("||".join(components).encode("utf-8")).hexdigest()


# ─── Entry point ────────────────────────────────────────────────────────────


def parse_intent(
    parser_input: IntentParserInput,
    *,
    user_id: int,
    cache_backend: CacheBackend | None = None,
    llm_caller: LLMCaller | None = None,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = _DEFAULT_THINKING_BUDGET,
    capped_retries: int = _DEFAULT_CAPPED_RETRIES,
) -> ParsedIntent:
    """Classify NL text → ParsedIntent.

    Pipeline (per NLParser_v1.md §2):
    1. `_short_circuit_empty` — empty input bypasses the LLM call.
    2. Cache lookup (when `cache_backend` supplied).
    3. `_render_user_prompt` + single LLM call via the SDK adapter.
    4. Pydantic validation; on failure, single capped retry with the
       schema error injected into the user prompt; second-fail raises
       `NLParserError("schema_violation", ...)`.
    5. `_enforce_closed_locale_vocab` post-LLM transform.
    6. Driver stamps `raw_text` per D7.
    7. Cache write (when `cache_backend` supplied).

    Errors:
    - `NLParserError("network", ...)` — SDK/transport failure (no retry).
    - `NLParserError("schema_violation", ...)` — second schema fail.
    - `NLParserError("input_validation", ...)` — unknown tier.

    The route layer catches `NLParserError` + substitutes
    `layer4.plan_refresh._default_parsed_intent()` per D-64 §5.4.
    """
    short_circuit = _short_circuit_empty(parser_input.nl_text)
    if short_circuit is not None:
        return short_circuit.model_copy(update={"raw_text": parser_input.nl_text})

    cache_key = nl_parser_cache_key(user_id=user_id, nl_text=parser_input.nl_text)
    if cache_backend is not None:
        entry = cache_backend.get(cache_key, PER_ENTRY_PHASE_IDX_SENTINEL)
        if entry is not None:
            return ParsedIntent.model_validate_json(entry.payload_json)

    tool_schema = build_record_parsed_intent_tool()
    caller: LLMCaller = llm_caller or _default_llm_caller
    retry_error: str | None = None
    last_error: ValidationError | None = None

    for attempt in range(capped_retries + 1):
        user_prompt = _render_user_prompt(parser_input, retry_error=retry_error)
        llm_output = caller(
            _SYSTEM_PROMPT,
            user_prompt,
            tool_schema,
            model,
            temperature,
            max_tokens,
            extended_thinking_budget,
        )
        try:
            parsed = ParsedIntent.model_validate(
                llm_output.tool_args | {"raw_text": parser_input.nl_text}
            )
        except ValidationError as exc:
            last_error = exc
            retry_error = str(exc)
            continue
        parsed = _enforce_closed_locale_vocab(
            parsed, parser_input.athlete_locales
        )
        if cache_backend is not None:
            cache_backend.put(
                cache_key=cache_key,
                phase_idx=PER_ENTRY_PHASE_IDX_SENTINEL,
                user_id=user_id,
                entry_point=_ENTRY_POINT_LABEL,
                phase_name=None,
                payload_json=parsed.model_dump_json(),
            )
        return parsed

    raise NLParserError(
        "schema_violation",
        detail=f"schema validation failed after {capped_retries + 1} attempts: {last_error}",
    )


__all__ = [
    "IntentParserInput",
    "LLMCaller",
    "NL_PARSER_PROMPT_VERSION",
    "NLParserError",
    "build_record_parsed_intent_tool",
    "nl_parser_cache_key",
    "parse_intent",
]
