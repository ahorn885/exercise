# NL Parser — Plan-Refresh Intent Classifier Prompt Body

**Prompt name:** `NLParser`
**Entry point:** `nl_parser.parse_intent(input: IntentParserInput) -> ParsedIntent` (`Plan_Refresh_D64_Design_v1.md` §5; runtime module lands in the paired D-64 caller-side session).
**Pattern:** Single LLM call wrapped in input prep → invoke → schema validate. On schema-violation single retry; on second-fail OR network error the caller substitutes `_default_parsed_intent()` per D-64 §5.4 (already implemented at `layer4/plan_refresh.py:1207`).
**Caller:** `routes/plan_refresh.py` (forthcoming) — invokes the parser BEFORE `orchestrate_plan_refresh(...)` and threads the resulting `ParsedIntent` into the orchestrator's `parsed_intent` kwarg.
**Status:** v1 — prompt body design only. Runtime + Flask route land in the paired session.
**Date:** 2026-05-21
**Position in arc:** First (and only) prompt body for the D-64 plan-refresh surface. Sits ahead of `Layer4_RefreshT1_v2.md` / `T2_v1.md` / `T3_v1.md` in the cascade. Sized for a classification task, not interpretive synthesis — materially lighter than the Layer 3 prompt bodies.

---

## Source decisions (this session, Andy 2026-05-21)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| D1 | Model | **`claude-sonnet-4-6`**. Haiku 4.5 migration tracked as §12 open item gated on a smoke-eval harness. | NL parsing is classic Haiku territory (12-field structured classification, no reasoning depth). But the parser is load-bearing — wrong classification routes the wrong cascade. Ship Sonnet for accuracy parity with the rest of the L3/L4 family; document Haiku migration as a cost-optimization tuning candidate once evals exist. |
| D2 | Extended thinking budget | **0 tokens (no extended thinking).** | Classification is shallow; no reasoning chain required. Matches single-session (also 0). |
| D3 | Output mechanism | **Forced tool-use.** Single tool `record_parsed_intent`; `tool_choice={"type":"tool","name":"record_parsed_intent"}`; strict JSON schema with `additionalProperties: false` at every nesting level. | L3/L4 family precedent. JSON-mode text output would force regex parsing; forced tool-use is the established contract. |
| D4 | Tool-schema fidelity | **Full `ParsedIntent` mirror MINUS `raw_text` (driver-stamped post-hoc).** Tool schema covers the 5 trigger flags + 3 soft signals + parser_confidence + ambiguity_notes (10 fields). | Layer 3A D5 precedent — metadata fields the LLM doesn't need to author are post-hoc stamped. `raw_text` is just the input echoed; the LLM doesn't add value by re-emitting it. |
| D5 | Injury disambiguation rule | **Middle path.** New-injury keywords ("tweaked", "hurt", "strained", "started hurting", "sharp", "sudden", "twisted") → `triggers_2d_injury=TRUE`. Pure update-on-existing keywords ("feels better", "healing", "less pain") → `triggers_2d_injury=FALSE`. Ambiguous → TRUE + populate `ambiguity_notes`. `athlete_active_injuries` is passed as context for the parser to disambiguate "my ankle hurts again" (already-active) vs "I just tweaked my ankle" (new). | Conservative bias toward firing 2D (it's cheap — query node, not LLM). Ambiguity surfaced via `ambiguity_notes` flows into the athlete-facing diff per D-64 Decision #9; athlete spots mis-routing and reverts. |
| D6 | Locale-slug matching | **Strict closed vocabulary.** `triggers_2c_equipment` may contain ONLY slugs present in `athlete_locales`. NL mentions an unknown location ("my hotel gym") → leave the list empty + populate `ambiguity_notes` ("Athlete mentioned 'hotel gym' which is not in their configured locales; no 2C re-run triggered."). | Layer 2C only knows configured slugs (per `locale_profiles` rows). Soft matching would emit slugs Layer 2C cannot resolve. Closed-vocab + ambiguity escape valve is the right contract. |
| D7 | `raw_text` field population | **Driver-stamped post-hoc.** The driver passes `nl_text` into the LLM via the user prompt but ALSO writes `ParsedIntent.raw_text = input.nl_text` post-call. | L3A D5 precedent for metadata fields. LLM doesn't need to echo the input. |
| D8 | Retry semantics | **Single capped retry on schema violation.** On second-fail OR network error, the parser raises `NLParserError`; the route catches + substitutes `_default_parsed_intent()` per D-64 §5.4. | Schema-violation retry matches L3A precedent (§5.3 step 1). D-64 §5.4 mandates degraded fallback rather than raise-to-caller. The route layer is the seam where the fallback substitution happens; the parser itself emits the error. |
| D9 | Voice | **Classification-only voice. No CLAUDE.md coaching-voice inheritance.** System prompt = closed-enum rules + decision criteria + ambiguity-notes guidance. No athlete-facing tone. | Parser doesn't write athlete-visible copy. The `ambiguity_notes` field can surface to athlete in diff view but is single-sentence-flag style, not coaching tone. |
| D10 | Sampling | **`temperature=0` for determinism + matches caching contract.** | Classification task; identical input must produce identical output to satisfy D-64 §5.3 cache key shape. |
| D11 | Document shape | **13-section mirror of Layer3A_v1.md.** Material weight ~400-500 LOC (lighter than Layer3A at 707 because classification has fewer prep transforms + less voice content). | Consistency with existing prompt-body docs. The 13-section depth standard is named in CLAUDE.md Working Principles. |
| D12 | Prompt version constant | **`NL_PARSER_PROMPT_VERSION = 1` lives in the runtime module `nl_parser.py`**, not in this markdown. | D-64 §5.3 cache key includes `parser_prompt_version`; the runtime module is the canonical source. Markdown is a design doc. The next session that touches the prompt bumps the constant. |
| D13 | Performance budget | **~150-300 input tokens / ~100-200 output tokens / ~500-800ms wall-clock cached, ~1-2s cold.** | Empirical estimate based on Sonnet 4.6 classification calls of similar shape (Layer 2A discipline classifier neighborhood). |
| D14 | Smoke-eval harness | **Tracked as §12 open item; NOT shipped this session.** | Spec-first sequencing: design the prompt; build evals when there's a route to feed traffic into. ~10-15 hand-labeled NL→ParsedIntent fixtures planned for the route-session companion. |

**Companion contract sections (`Plan_Refresh_D64_Design_v1.md`):** §5.1 (input dataclass), §5.2 (output dataclass), §5.3 (caching), §5.4 (failure mode), §11 (test scenario forward-pointers — items 2, 3, 4, 10 exercise the parser).

**Companion runtime references (`layer4/`):** `context.py:1176` (`ParsedIntent` pydantic model — the schema target), `plan_refresh.py:1207` (`_default_parsed_intent()` — the degraded fallback the route substitutes on parser failure).

---

## 1. Purpose + scope

### 1.1 What this prompt produces

A single `ParsedIntent` per `Plan_Refresh_D64_Design_v1.md` §5.2. The payload carries:
- **5 trigger flags** (added to the tier's default cascade; never subtractive):
  - `triggers_2a_discipline: bool` — new discipline mention ("I'm starting kayaking").
  - `triggers_2b_terrain: bool` — new terrain context ("I'll be in the mountains next month").
  - `triggers_2c_equipment: list[str]` — list of locale slugs from the closed `athlete_locales` vocabulary.
  - `triggers_2d_injury: bool` — new-injury signal (per D5 rule).
  - `triggers_2e_nutrition: bool` — nutrition-context shift ("GI issues last race", "switching to plant-based").
- **3 soft signals** (passed to Layer 4 as context, not full re-runs):
  - `fatigue_signal: Literal['fresh', 'normal', 'tired', 'wiped']` (default `'normal'`).
  - `sickness_signal: Literal['none', 'recovering', 'active']` (default `'none'`).
  - `motivation_signal: Literal['low', 'normal', 'high']` (default `'normal'`).
- **Confidence + ambiguity:**
  - `parser_confidence: Literal['high', 'medium', 'low']`.
  - `ambiguity_notes: str | None` — single-sentence explanation when the parser could not classify cleanly OR routed conservatively under ambiguity.

The driver post-stamps `raw_text = input.nl_text` after the call returns.

### 1.2 What this prompt does NOT produce

- **No coaching advice.** The parser routes; it does not advise. Athlete-facing coaching emerges from Layer 4 plan synthesis.
- **No injury diagnosis.** "I tweaked my knee" triggers 2D; it does NOT produce a diagnosis. Layer 2D owns severity / verdict.
- **No locale resolution outside the closed vocabulary.** Unknown locations get flagged via `ambiguity_notes`, not invented as slugs.
- **No new soft-signal enums.** The 3 soft signals use closed enums; the parser cannot return "exhausted" — it picks `'wiped'`.
- **No tier override.** Tier is an input (caller decides via UI button); parser does not re-tier.

### 1.3 Failure modes this prompt + retry semantics catch

- **Schema violation** (LLM emits invalid enum, missing required field, extra field): retry once with the schema error in the user prompt; on second fail, raise `NLParserError("schema_violation", detail=<error>)`. Route substitutes `_default_parsed_intent()`.
- **Network / API error** (timeout, 5xx, auth): no retry inside the parser; raise `NLParserError("network", detail=<error>)`. Route substitutes `_default_parsed_intent()`.
- **Empty / whitespace-only NL input**: parser short-circuits BEFORE the LLM call and returns a default-flag `ParsedIntent(parser_confidence='high', ambiguity_notes=None)` — no API call, no cost. The LLM is only invoked when there's text to classify.
- **Out-of-vocab locale mention**: NOT a failure mode. Handled in-prompt per D6 — parser leaves `triggers_2c_equipment` empty + populates `ambiguity_notes`.
- **Ambiguous injury phrasing**: NOT a failure mode. Handled in-prompt per D5 — parser routes conservatively (TRUE) + populates `ambiguity_notes`.

---

## 2. Pipeline placement

**Call site:** `nl_parser.parse_intent(input: IntentParserInput) -> ParsedIntent`. Invoked by `routes/plan_refresh.py` (forthcoming) BEFORE `orchestrate_plan_refresh(...)`:

```python
# routes/plan_refresh.py (forthcoming — D-64 caller-side session)
nl_text = request.form.get('nl_context', '').strip()
parser_input = IntentParserInput(
    nl_text=nl_text,
    tier=tier,
    athlete_locales=_athlete_locale_slugs(db, user_id),
    athlete_active_injuries=_athlete_active_injury_summary(db, user_id),
)
try:
    parsed_intent = nl_parser.parse_intent(parser_input)
except NLParserError:
    parsed_intent = _default_parsed_intent()  # imported from layer4.plan_refresh

payload = orchestrate_plan_refresh(
    db, user_id,
    tier=tier,
    parsed_intent=parsed_intent,
    # ... other kwargs ...
)
```

**Pattern:** Single LLM call + post-LLM schema validation + driver-stamped `raw_text`. No prep transforms beyond the 4 input fields rendered into the user prompt.

- Step 1: `_short_circuit_empty(input)` — if `nl_text.strip() == ""`, return default `ParsedIntent` immediately. No LLM call.
- Step 2: `_render_user_prompt(input)` — assemble the 4 input fields into the user prompt string per §6.
- Step 3: Single LLM call via `_default_llm_caller` (Anthropic SDK, forced tool-use, no extended thinking). On schema-violation, single capped retry with the schema error message in the user prompt.
- Step 4: Schema validation via `ParsedIntent.model_validate(tool_args | {"raw_text": input.nl_text})` — driver injects `raw_text` post-hoc per D7.
- Step 5: Return validated payload.

No confidence-floor clamping (parser self-reports confidence; the route + Layer 4 consume it directly). No evidence-basis cross-check (parser doesn't cite evidence).

---

## 3. Inputs (template variables)

The user prompt renders 4 template variables from `IntentParserInput`:

| Variable | Source field | Rendering |
|---|---|---|
| `{nl_text}` | `input.nl_text` | Verbatim, wrapped in triple-backtick block. No normalization (the caching layer normalizes for the cache key, but the prompt sees the athlete's original text so case + punctuation signal intent — "I'M WIPED" vs "i'm a bit tired" can carry different fatigue levels). |
| `{tier}` | `input.tier` | One of `T1`, `T2`, `T3`. Rendered as `Tier: T1 (next 2 days)` / `T2 (next 7 days)` / `T3 (next 28 days)` with the horizon context the LLM may need for ambiguous phrasings ("regenerate the rest of the week" is unambiguous on T2 + Wednesday; on T1 it's a mis-tier signal that goes into `ambiguity_notes`). |
| `{athlete_locales}` | `input.athlete_locales` | List of slugs rendered as a comma-separated list with no labels (slugs are athlete-edited; "home" / "in_laws_mn" / "gym_downtown" style). Empty list rendered as `(none configured)`. |
| `{athlete_active_injuries}` | `input.athlete_active_injuries` | List of injury-summary strings ("left wrist — chronic-managed", "lower back — recovering"). Empty list rendered as `(none active)`. |

The driver also captures the prep dict for telemetry (not for evidence-basis cross-check; parser doesn't emit evidence_basis). Prep dict is logged alongside the parsed output for `plan_refresh_log.parsed_intent` debugging.

---

## 4. Tool schema

### 4.1 Tool name

`record_parsed_intent`

### 4.2 Top-level shape

The tool accepts the full `ParsedIntent` payload contract MINUS `raw_text` (driver-stamped per D7). Pydantic on the driver side validates via `ParsedIntent.model_validate(tool_args | {"raw_text": input.nl_text})`. The tool schema below specifies what the LLM must emit:

```jsonc
{
  "name": "record_parsed_intent",
  "description": "Emit the structured intent classification for an athlete's natural-language plan-refresh context. Required.",
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
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
      "ambiguity_notes"
    ],
    "properties": {
      "triggers_2a_discipline": {
        "type": "boolean",
        "description": "TRUE if the athlete mentions starting / adopting a new discipline (e.g., 'I'm starting kayaking', 'switching to triathlon'). Existing-discipline mentions ('I'm running tomorrow') do NOT trigger."
      },
      "triggers_2b_terrain": {
        "type": "boolean",
        "description": "TRUE if the athlete mentions a new terrain context that changes the race or training surface (e.g., 'I'll be in the mountains', 'event moved to a sand course'). Routine training-day terrain ('quick trail run') does NOT trigger."
      },
      "triggers_2c_equipment": {
        "type": "array",
        "items": { "type": "string" },
        "description": "List of locale slugs (from the closed athlete_locales vocabulary) the athlete mentioned. Empty list if no locale-context shift. NEVER emit slugs not present in the athlete_locales input — surface unknown locations via ambiguity_notes."
      },
      "triggers_2d_injury": {
        "type": "boolean",
        "description": "TRUE if the athlete mentions a NEW injury or fresh aggravation. Conservative bias: ambiguous phrasings → TRUE + ambiguity_notes. Pure update-on-existing ('my ankle feels better', 'lower back healing') → FALSE."
      },
      "triggers_2e_nutrition": {
        "type": "boolean",
        "description": "TRUE if the athlete mentions a nutrition-context shift (e.g., 'GI issues during long runs', 'switching to plant-based', 'cutting weight for race'). Generic energy mentions ('I'm hungry') do NOT trigger; those route to fatigue_signal."
      },
      "fatigue_signal": {
        "type": "string",
        "enum": ["fresh", "normal", "tired", "wiped"],
        "description": "Athlete's stated energy level. 'normal' is the default for unclassifiable / silent input. 'wiped' for explicit-extremes ('I'm cooked', 'destroyed', 'wrecked', 'blown up'). 'tired' for moderate fatigue ('a bit tired', 'low energy'). 'fresh' for explicit fresh-feeling ('feeling great', 'fully recovered', 'sharp')."
      },
      "sickness_signal": {
        "type": "string",
        "enum": ["none", "recovering", "active"],
        "description": "'active' for current sickness ('I have the flu', 'fever today'). 'recovering' for tail-of-illness ('coming off a cold'). 'none' is the default."
      },
      "motivation_signal": {
        "type": "string",
        "enum": ["low", "normal", "high"],
        "description": "'low' for explicit demotivation ('not feeling it', 'dreading workouts'). 'high' for explicit drive ('feeling super motivated', 'ready to push'). 'normal' is the default."
      },
      "parser_confidence": {
        "type": "string",
        "enum": ["high", "medium", "low"],
        "description": "'high' when the NL text contains clear signals matching the schema. 'medium' for partial signals or single-axis ambiguity. 'low' when the parser had to guess across multiple axes — paired with ambiguity_notes."
      },
      "ambiguity_notes": {
        "type": ["string", "null"],
        "maxLength": 240,
        "description": "Single-sentence explanation when the parser could not classify cleanly OR routed conservatively under ambiguity OR mentioned an out-of-vocab location/injury. NULL when classification was unambiguous."
      }
    }
  }
}
```

### 4.3 Why `ambiguity_notes` is part of the LLM-emitted contract (not driver-stamped)

`ambiguity_notes` carries the LLM's reason for the routing decision — context only the LLM has at the moment of classification. Driver-stamping would require the driver to re-derive the reasoning, which defeats the point. The 240-char cap keeps it single-sentence + cheap.

### 4.4 Locale-slug enum constraint (D6 closed vocabulary)

The tool schema cannot statically constrain `triggers_2c_equipment` to the athlete's specific locale slugs (the slug list is runtime-per-athlete). The system prompt enforces the rule + post-LLM validation in the runtime module checks `set(parsed.triggers_2c_equipment) ⊆ set(input.athlete_locales)`. On violation, the runtime strips unknown slugs + appends a sentence to `ambiguity_notes` ("Parser emitted unknown locale slug '<slug>'; stripped.") — telemetry signal for prompt-tuning, no caller-visible failure.

---

## 5. System prompt

```
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
    first-person hedge.
```

---

## 6. User prompt template

```
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
parser_confidence='low'.
```

Where:
- `{tier_label}` renders to one of:
  - `T1 (next 2 days)`
  - `T2 (next 7 days)`
  - `T3 (next 28 days)`
- `{athlete_locales_block}` renders the slug list as one slug per line, or `(none configured)` when empty.
- `{athlete_active_injuries_block}` renders the injury summary list as one entry per line, or `(none active)` when empty.

On retry after schema violation, the user prompt is augmented with:

```
Previous attempt failed schema validation: {error_message}

Re-emit a valid `record_parsed_intent` tool call addressing the error
above. Do not change unrelated fields.
```

---

## 7. Sampling config

| Param | Value | Source |
|---|---|---|
| `model` | `claude-sonnet-4-6` | D1. |
| `temperature` | `0` | D10 — deterministic classification + cache contract. |
| `max_tokens` | `1024` | Generous headroom for the 10-field tool output + ambiguity_notes cap. |
| `extended_thinking_budget` | `0` (disabled) | D2. |
| `capped_retries` | `1` | D8 — schema-violation single retry. |
| `tool_choice` | `{"type": "tool", "name": "record_parsed_intent"}` | D3. |

---

## 8. Post-LLM transforms

### 8.1 Schema validation

`ParsedIntent.model_validate(tool_args | {"raw_text": input.nl_text})` — pydantic enforces the contract. The driver injects `raw_text` post-hoc per D7. On schema-validation failure, single capped retry per §5.3 step 1 with the validation error in the user prompt. Second failure raises `NLParserError("schema_violation", detail=<error>)`.

### 8.2 Locale-slug closed-vocabulary check (D6)

```python
def _enforce_closed_locale_vocab(
    parsed: ParsedIntent,
    allowed_slugs: list[str],
) -> ParsedIntent:
    """Strip any triggers_2c_equipment entries not in allowed_slugs.
    Append a telemetry note to ambiguity_notes when stripping fires."""
    allowed_set = set(allowed_slugs)
    invalid = [s for s in parsed.triggers_2c_equipment if s not in allowed_set]
    if not invalid:
        return parsed
    stripped = [s for s in parsed.triggers_2c_equipment if s in allowed_set]
    note_suffix = (
        f"Parser emitted unknown locale slug(s) {invalid}; stripped."
    )
    new_notes = (
        f"{parsed.ambiguity_notes} {note_suffix}".strip()
        if parsed.ambiguity_notes else note_suffix
    )
    return parsed.model_copy(update={
        "triggers_2c_equipment": stripped,
        "ambiguity_notes": new_notes[:240],  # respect schema cap
    })
```

### 8.3 No confidence-floor clamp

The parser self-reports `parser_confidence`. The runtime trusts it (the rules are simple enough that LLM self-reporting is reliable). Floor-clamping would require post-hoc heuristics that don't have a meaningful basis at the parser layer.

### 8.4 No evidence-basis cross-check

Parser doesn't emit `evidence_basis` — the schema doesn't include it. Layer 3/4 evidence_basis is for downstream debugging of synthesizer reasoning; classification is shallow enough that field-citation doesn't add value.

---

## 9. Performance budget

| Dimension | Estimate | Source |
|---|---|---|
| Input tokens (system + user) | 150-300 | System prompt ~120 tokens; user prompt 30-180 tokens depending on NL text length + locale/injury list size. |
| Output tokens | 100-200 | 10-field tool output + ambiguity_notes cap at ~240 chars (~60 tokens). |
| Wall-clock (cold) | 1-2s | Sonnet 4.6 single tool call, no extended thinking. |
| Wall-clock (cached) | 50-150ms | Cache hit — no LLM call, just hydration. |
| Cost (cold) | ~$0.003-$0.005 | Sonnet 4.6 pricing: ~$3/M input + ~$15/M output tokens × estimate. |
| Cost (cached) | $0 | Cache hit. |

**Budget vs alternative (Haiku 4.5):** Haiku at ~$0.25/M input + ~$1.25/M output would be ~10× cheaper (~$0.0003-$0.0005/cold call) with ~500ms wall-clock. Tracked as §12 migration candidate; gates on smoke-eval harness.

---

## 10. Caching

### 10.1 Cache key (D-64 §5.3)

```python
cache_key = (
    user_id,
    sha256(_normalize_nl_text(nl_text).encode("utf-8")).hexdigest(),
    NL_PARSER_PROMPT_VERSION,  # constant in nl_parser.py per D12
)
```

Where:
- `_normalize_nl_text(text)` returns `" ".join(text.lower().split())` — lowercase + collapse all whitespace runs. "I'm   TIRED!" and "i'm tired!" hash identically.
- `NL_PARSER_PROMPT_VERSION` is an integer constant in `nl_parser.py` (NOT in this markdown). Bumped on any behaviorally-significant prompt change. Bumping invalidates all prior parses, forcing re-classification under the new prompt — per-D-64 §5.3 intent.

### 10.2 Cache backend

Same `PostgresCacheBackend` infrastructure as Layer 4 entry points (see `layer4/cache.py`). The parser registers a new cache scope `"nl_parser"` with an entry point of `"nl_parser_parse_intent"` (sized into `VALID_ENTRY_POINTS` in the runtime session, not the LAYER4_ENTRY_POINTS subset — parser cache is athlete-scoped, not Layer-4-scoped, so it stays out of Layer 4 invalidation cascades).

### 10.3 Cache invalidation

- Prompt version bump (`NL_PARSER_PROMPT_VERSION += 1`) invalidates ALL parses across all athletes (cache key includes the version).
- Athlete-level invalidation: when `athlete_locales` or `athlete_active_injuries` change, prior parses MAY be stale (e.g., "my back" now matches an active injury that wasn't in the list before). v1 does NOT invalidate on these changes — the cache key doesn't include them, so an athlete re-pasting the same NL text gets the same (potentially-stale) parse. This is intentional: the trigger flags would be the same regardless (conservative bias fires TRUE either way), and athlete-locale changes are infrequent. Tracked as §12 tuning candidate.

---

## 11. Test scenarios

The runtime session (paired) ships stub-LLM unit tests + a real-LLM smoke harness. Below are the fixture cases that exercise classification correctness:

### 11.1 Stub-LLM unit tests (no real API)

Built into `tests/test_nl_parser.py` (forthcoming, paired session) with `_FakeAnthropicCaller` returning canned tool args:

| # | Input | Expected output | Reason |
|---|---|---|---|
| TS1 | nl_text="I'm tired", tier=T1 | fatigue_signal='tired', all flags FALSE, confidence='high', ambiguity_notes=None | Clean single-signal classification. |
| TS2 | nl_text="I tweaked my ankle", tier=T1, active_injuries=[] | triggers_2d_injury=TRUE, ambiguity_notes=None | New-injury keyword on a body part with no active record. |
| TS3 | nl_text="my ankle hurts again", tier=T1, active_injuries=["right ankle — recovering"] | triggers_2d_injury=TRUE, ambiguity_notes populated | Conservative routing on re-aggravation phrasing. |
| TS4 | nl_text="my ankle feels better", tier=T1, active_injuries=["right ankle — recovering"] | triggers_2d_injury=FALSE, ambiguity_notes=None | Update-on-existing language. |
| TS5 | nl_text="I'm at my in-laws", tier=T1, athlete_locales=["home", "in_laws_mn"] | triggers_2c_equipment=["in_laws_mn"], confidence='medium' | Slug match against closed vocab. |
| TS6 | nl_text="I'm at my hotel gym", tier=T1, athlete_locales=["home"] | triggers_2c_equipment=[], ambiguity_notes mentions "hotel gym" | Out-of-vocab location surfaced. |
| TS7 | nl_text="cooked from yesterday's race", tier=T1 | fatigue_signal='wiped' | Extreme-fatigue keyword. |
| TS8 | nl_text="I have the flu", tier=T1 | sickness_signal='active' | Current-sickness signal. |
| TS9 | nl_text="I'm starting kayaking next month", tier=T3 | triggers_2a_discipline=TRUE | New-discipline mention on long horizon. |
| TS10 | nl_text="GI issues during the long runs lately", tier=T2 | triggers_2e_nutrition=TRUE | Nutrition-context shift. |
| TS11 | nl_text="regenerate the next month", tier=T1 | ambiguity_notes populated with tier-mismatch language | T1 with T3 phrasing. |
| TS12 | nl_text="not feeling it this week", tier=T2 | motivation_signal='low' | Explicit demotivation. |
| TS13 | nl_text="" (empty), tier=T1 | Default ParsedIntent (no LLM call) | Short-circuit per §1.3. |
| TS14 | nl_text="my back again", tier=T1, active_injuries=["lower back — chronic-managed"] | triggers_2d_injury=TRUE, ambiguity_notes populated | Ambiguous re-aggravation; conservative routing. |
| TS15 | nl_text="travel Wed-Fri", tier=T2 | All flags FALSE, all signals default, confidence='medium', ambiguity_notes populated with "travel context unclear without locale slug" | Travel mention without a slug — soft signal, surface via notes. |

### 11.2 Closed-vocab violation post-LLM transform

`tests/test_nl_parser.py::TestClosedLocaleVocab` exercises §8.2 — the LLM returns `triggers_2c_equipment=["nonexistent_slug"]`; the post-LLM transform strips it + appends to `ambiguity_notes`. No caller-visible failure.

### 11.3 Real-LLM smoke harness (env-gated)

`tests/test_nl_parser_smoke.py` (forthcoming, paired session) with `@requires_anthropic_api_key` decorator. ~10-15 hand-labeled NL → ParsedIntent fixtures derived from Andy's training-context vocab (PGE 2026 + AR + multi-sport phrasing). Skips cleanly when `ANTHROPIC_API_KEY` unset.

---

## 12. Open items / tuning candidates

| # | Item | Tracking |
|---|---|---|
| NL-1 | **Haiku 4.5 migration eval.** Build the smoke-eval harness (§11.3) with ~15 hand-labeled fixtures; run both Sonnet 4.6 + Haiku 4.5 against the fixtures; pick whichever holds ≥95% agreement on triggers + soft signals. Cost gain ~10×. | Tracked in `CARRY_FORWARD.md` post-runtime-session. |
| NL-2 | **Athlete-level invalidation on athlete_locales / athlete_active_injuries change.** v1 does not invalidate; the cache key omits these. May produce stale parses ("my back" matches a newly-added active injury). Conservative-bias rule means the impact is small (parser already over-fires 2D on ambiguity), but worth instrumenting. | Tracked here. |
| NL-3 | **Out-of-vocab location auto-add suggestion.** When the parser surfaces an out-of-vocab location ("hotel gym"), the route could offer the athlete an "Add 'hotel gym' as a locale?" CTA. UX surface deferred. | Pair with Dashboard CTAs work or D-64 v2 polish. |
| NL-4 | **Multi-signal density telemetry.** When the LLM populates multiple soft signals AND multiple triggers, the resulting cascade can be large. Telemetry should track average-triggers-per-parse to spot prompt drift (parser becoming too conservative-trigger-happy over time). | Add to `plan_refresh_log.parsed_intent` analytics in a later session. |
| NL-5 | **Tier-mismatch policy.** §5 rule 7 says "classify in-tier signals only" + note in ambiguity_notes. Alternative: surface tier-mismatch as a soft caller signal (`tier_mismatch: bool` field on ParsedIntent), so the route can show a "Did you mean T3?" prompt. Deferred. | v2 polish candidate. |
| NL-6 | **Soft-signal granularity.** 4 fatigue levels + 3 sickness + 3 motivation is the v1 enum split. May need finer-grained signals (e.g., "wiped-but-still-going" vs "wiped-and-stopping") once Layer 4 starts conditioning on them. Defer until Layer 4 produces signal-conditioned outputs. | v2 candidate, paired with Layer 4 conditioning work. |
| NL-7 | **NL_PARSER_PROMPT_VERSION constant location convention.** Lives in `nl_parser.py`; bumping requires a code edit + cache invalidation. For prompt-engineering iteration during evals tuning, this is friction. Consider exporting via env var override for dev experimentation. | Add to runtime session §12. |
| NL-8 | **Streaming-mode infeasibility note.** Forced tool-use + small output schema means streaming buys nothing here (no partial-output UX). Stay non-streaming. | Pinned; no action. |

---

## 13. Gut check

**What's right:**
- **Classification voice in classification surfaces.** No coaching voice inheritance, no platitudes. The parser does one job — route the cascade. Voice rules in the system prompt match the job.
- **Conservative bias + ambiguity_notes is the right escape valve.** Over-firing 2D (cheap query node) is much less costly than under-firing 2D (athlete's injury context missed); the diff-view UX per D-64 Decision #9 surfaces the over-fire so athlete can spot mis-routing.
- **Closed-vocab locale matching honors the L2C contract.** L2C only knows configured slugs; emitting unknown slugs would silently no-op downstream. Closed vocab + ambiguity escape is the right shape.
- **`raw_text` driver-stamped + LLM doesn't echo input.** Matches L3A precedent; halves output tokens on the trivial passthrough field.
- **Cache key shape per D-64 §5.3 is sound.** Normalized text + prompt version means trivial whitespace edits hit cache; behaviorally-significant prompt changes force re-classification.

**Risks:**
- **Accuracy unproven.** No evals. The first time a route fires this in production, classification errors will surface. Mitigation: smoke-eval harness in paired session before traffic; ambiguity_notes surfaces routing decisions to athlete; revert path is the safety valve.
- **Sonnet cost at scale.** $0.003-$0.005/call × athletes × refreshes-per-week scales fast. Haiku migration (§12 NL-1) is the cost-control plan but it's eval-gated.
- **Out-of-vocab phrasings will reach production.** Endurance athletes use rich vernacular ("smashed", "buried", "schwacked", "blown the doors off"). The fatigue/motivation enum keyword lists in §5 are starting points; expect to expand based on real-traffic telemetry.
- **Tier-mismatch handling is soft.** Athlete picks T1 but writes T3-shaped text; parser classifies in-tier signals only and notes the mismatch. UX may need to escalate ("Did you mean T3?") in a polish pass.
- **Existing-injury phrasing is genuinely ambiguous.** "My back again" without injury history → trigger TRUE (new). With injury history → conservative TRUE + ambiguity_notes. A more confident parser would distinguish; this parser routes-then-flags. Acceptable v1 tradeoff.

**What might be missing:**
- **Cross-locale ambiguity.** Athlete has slugs `["home", "lake_cabin", "in_laws_mn"]` and writes "at the cabin". Likely match: `lake_cabin`. But the LLM has only the slug list, not human-friendly labels (cabin / in-laws / home). Soft mitigation: the system prompt could include slug-with-label rendering. Skipping v1 — slugs are athlete-edited so they're already semantically meaningful. Track as §12 NL-3 candidate.
- **Athlete vernacular drift.** v1 keyword lists in §5 are starting points; production traffic will surface phrasing we missed. The smoke-eval harness will exercise this once it lands.
- **Layer 5 supplement re-runs.** Layer 5 (nutrition / supplements / clothing) isn't specced yet. When it lands, some NL signals (e.g., "switching supplements") may need a `triggers_5_supplements` flag. v1 routes those to `triggers_2e_nutrition`; revisit when L5 specs land.
- **Coaching observations from repeated parses.** If the athlete reports fatigue 4 times in a week (4× T1 with fatigue_signal='tired'), there's a coaching observation to surface ("consider a recovery week"). That's not the parser's job; lives in a future Layer 5 advisory surface. Flagged as D-64 §12 open item already.

**Best argument against this scope:**
Designing the prompt before there's a runtime to test against means the v2 bump may be unavoidable. Counter (same as Layer 3A's gut check): the design doc is cheap to revise; landing v1 unblocks the runtime session. Standard prompt-engineering loop — v1 lands the contract + scaffolding; v2 tunes against eval signal.

Counter to the counter: prompt-engineering work without an eval harness is closer to opinion than design. The runtime session should pair the smoke-eval harness build with the route implementation, so v1 prompt edits can be measured before v2 ships.

Net: ship v1 as designed; commit to the smoke-eval harness in the runtime session; treat v1→v2 as a routine prompt-tuning loop driven by Andy's eval-fixture labels.

---

*End of NLParser_v1.md.*
