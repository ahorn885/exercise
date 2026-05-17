# V5 Implementation — Layer 4 Step 4b/c Plan-Refresh T1+T2 Closing Handoff

**Session:** Single chat. Scope: Steps 4b + 4c of `Layer4_Spec.md` §14.3.4 — `llm_layer4_plan_refresh` T1 + T2 (D-64 caller integration). Pattern B refresh per §5.1 routing + Pattern B single-call algorithm per §5.3 + capped-retry per §5.5 + `intensity_modulated` observation emission per §8.6/§8.7 (broadened to plan_refresh). Paired `Layer4_Spec.md` §3.2 surgical amendment for the §4.3-wins contract gap on `layer3b_payload` (3B required on every tier).
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step4a_SingleSession_Closing_Handoff_v1.md` (Step 4a — `layer4/single_session.py` D-63 caller integration; 49 tests; combined 354 green).
**Branch:** `claude/implement-layer4-closing-YPmyc` (harness-pinned for this session — name carried over from a prior harness pin even though this PR is Step 4b/c plan-refresh integration; precedent: PR-A → PR-B → PR-C → PR-C-followon → PR-D → PR-E → Step 4a all harness-pinned with mismatched names).
**Status:** 🟢 6 substantive code + 1 spec + 3 bookkeeping = 10 files. 58 new tests; combined `tests/` count 354 → 412, all green in 0.56s. **Layer 4 implementation Steps 4b + 4c close here; Step 4d (T3 — Pattern B intra-phase) opens, with cross-phase T3 deferred to Step 4f.**

---

## 1. Session-start verification (Rule #9)

Predecessor (Step 4a) handoff §7 claimed: `layer4/single_session.py` (~720 lines) + `layer4/errors.py` (~30 lines) + `tests/test_layer4_single_session.py` (49 tests) on disk; `layer4/__init__.py` exposes 6 new re-exports alongside the existing payload + hashing + context + validator surfaces; combined `tests/` 354 green; `Project_Backlog_v45.md` exists; CLAUDE.md Backlog ref reads v45; PR #74 merge commit `5976c04` on `origin/main`; working tree clean on a fresh-cut branch.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `layer4/single_session.py` exists with `SingleSessionRequest` + `build_record_single_session_tool` + `llm_layer4_single_session_synthesize` + all driver helpers | inspection | ✅ 1121 lines |
| `layer4/errors.py` exists with `Layer4Error` + `Layer4InputError` + `Layer4OutputError` | inspection | ✅ |
| `tests/test_layer4_single_session.py` 49 tests, combined `tests/` 354 green | `python -m pytest tests/` | ✅ 354 passed in 0.43s |
| `Project_Backlog_v45.md` exists | `ls` | ✅ |
| CLAUDE.md Backlog ref reads v45 | grep | ✅ |
| Step 4a PR #74 merge commit `5976c04` on `origin/main` | `git log --oneline` | ✅ |
| Working tree clean on fresh-cut branch | `git status` | ✅ clean |
| Current branch `claude/implement-layer4-closing-YPmyc` (harness pin) | `git branch` | ✅ |

**No drift found.** Step 4a state on disk matches the handoff narrative. Branch name `claude/implement-layer4-closing-YPmyc` is a harness pin; surfaced inline; matches the harness-name-vs-scope precedent.

---

## 2. Session narrative — Andy-confirmed scope; trigger #5 + #8 fired and routed; spec-amendment ripple

Andy opened with a URL pointer to the Step 4a closing handoff and "let's work." I followed §5 operating notes — re-read CLAUDE.md (Rule #13), ran Rule #9 verification, surfaced state + next focus (Step 4b/c architect-recommended) + drift (none), and surfaced two load-bearing findings that needed Andy's call before any edits.

### 2.1 Findings surfaced via AskUserQuestion

**Finding 1 (trigger #5 candidate): §3.2 vs §4.3 contradiction on `layer3b_payload` for T1.** §3.2 signature line 144 + the parameter table notes column (line 170) explicitly said T1 doesn't re-run 3B; `Layer3BPayload | None` accepted; falls back to prior session phase_metadata. §4.3 row 1 (line 772) flatly contradicted: "`layer3b_payload` required even on T1/T2 — Pattern B's validator still reads phase intent for the intensity-distribution check." Three resolution options surfaced via `AskUserQuestion`:
1. **§3.2 wins** — 3B optional on T1; surgical amendment to §4.3 carve-out for T1
2. **§4.3 wins** — 3B required for all tiers; surgical amendment to §3.2 signature (drop `| None`)
3. **Defer** — implement strict-3B; leave spec inconsistent; track as v2 carry-forward

**Finding 2 (trigger #8 — load-bearing missing types).** `Layer2Bundle` + `ParsedIntent` referenced in §3.2 signature but never defined as pydantic v2 models anywhere in `layer4/`. Spec referenced both in narrative; `ParsedIntent` was sketched as a `@dataclass` in `Plan_Refresh_D64_Design_v1.md` §5.2 (lines 181-202) but never landed as code. Two location options surfaced:
1. **Add to `layer4/context.py`** — alongside existing upstream-payload mirrors; reusable across all refresh entry points
2. **Inline in `layer4/plan_refresh.py`** — tighter cohesion with consumer; harder to share with T3 / Pattern A entry points

**Finding 3 (trigger #8).** File organization — single `plan_refresh.py` bundling T1+T2 vs two-file split with shared driver vs shared-helper extract.

**4-question `AskUserQuestion` batch (2026-05-17):**
1. Scope confirmation: **Step 4b/c bundled T1+T2** (architect-recommended)
2. 3B-T1 gap: **§4.3 wins** (3B required for T1/T2)
3. Bundle types location: **Add to `layer4/context.py`**
4. File organization: **Two files — `_t1.py` + `_t2.py`** (driver entrypoint dispatches on tier)

### 2.2 Single-pass implementation against the spec

After Andy's picks, I read the spec/prompt-body anchors needed for implementation:
- `Layer4_Spec.md` §3.2 (function signature; ~50 lines), §4.3 (input validation preconditions; ~13 lines), §5.1 (pattern routing — T1/T2 always B), §5.3 (Pattern B algorithm), §5.5 (capped-retry semantics + schema-violation special case + best-effort fallback)
- `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` §3 (input variables) + §4.1 (tool schema sketch) + §5 (system prompt) + §6 (user prompt template)
- `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` (same sections; differences captured for T2 implementation)
- `aidstation-sources/Plan_Refresh_D64_Design_v1.md` §5.2 (`ParsedIntent` dataclass shape)
- `layer4/single_session.py` (~720 lines; full reference implementation pattern to mirror)
- `layer4/payload.py` (Layer4Payload + PlanSession + validator-result invariants for plan_refresh mode)
- `layer4/context.py` (Layer3BPayload + other upstream payload shapes; finding the file end for Layer2Bundle + ParsedIntent appends)
- `layer4/validator.py` (ValidatorContext signature)
- `tests/test_layer4_single_session.py` (test patterns/helpers — `_stub_caller` + `_sequence_caller` + fixture shapes)

Wrote `layer4/plan_refresh.py` (~750 lines) — driver entrypoint + shared Pattern B plumbing:
- `_SynthesizerOutput` dataclass + `LLMCaller` type alias (copy of Step 4a's shape)
- `_intensity_target_schema()` — 9-shape `IntensityTarget` `oneOf` (copy of Step 4a)
- `_REFRESH_COACHING_FLAGS` — closed 7-flag enum per `Layer4_RefreshT1_v1.md` D6 (vs Step 4a's 3-flag enum)
- `_session_schema()` — full PlanSession contract mirror per the Option 2 precedent
- `build_record_refresh_sessions_tool(tier: Literal['T1','T2']) -> dict` — wraps `_session_schema()` in a `sessions` array with `maxItems=4` (T1) or `maxItems=14` (T2)
- `_validate_inputs()` — §4.3 preconditions: invalid tier; scope_inverted; tier_scope_mismatch (T1 ≤ 3, T2 ≤ 9); missing_upstream_payload for 1, 2bundle, 3A, **3B (per Andy's §4.3-wins pick)**; prior_plan_window_empty; plan_version_id_parent_missing
- `_default_llm_caller()` — Anthropic SDK adapter (copy of Step 4a's shape)
- `_parse_date()` + `_build_plan_session()` — tool-args → typed PlanSession via pydantic smart-union dispatch; fills `phase_metadata=None` (Pattern B §7.12) + `is_ad_hoc=False` (refresh outputs aren't ad-hoc) + `ad_hoc_request_payload=None`
- `_build_layer4_payload()` + `_build_payload_for_validation()` — Layer4Payload composition with `mode='plan_refresh'` + `pattern='B'` + `phase_structure=None` + `seam_reviews=None` + `suggestion_id=None`
- `_emit_intensity_modulated_observation()` — per §8.6/§8.7 broadening: ONE Observation emitted when ANY session carries the flag; text references the affected count
- `_build_validator_context()` — bundles Layer2Bundle.a/b/c/d/e + 3A + 3B into ValidatorContext for the §5.4 harness
- Main `llm_layer4_plan_refresh()` driver — validates inputs → dispatches on tier (T3 raises `tier_t3_not_yet_implemented`; T1/T2 lazy-imports the tier module) → loads tier-specific `SYSTEM_PROMPT` + defaults + `render_user_prompt()` → retry loop with schema-violation special case + cap-hit best-effort acceptance + observation emission
- `_default_parsed_intent()` — degraded-parser graceful-degrade per `Plan_Refresh_D64_Design_v1.md` §5.4 (substituted when caller passes `parsed_intent=None`)

Wrote `layer4/plan_refresh_t1.py` (~280 lines) — T1-specific plumbing:
- `DEFAULT_MAX_TOKENS=2000`, `DEFAULT_EXTENDED_THINKING_BUDGET=3000` per T1 prompt body §7
- `SYSTEM_PROMPT` — full text matching `Layer4_RefreshT1_v1.md` §5
- `_format_active_injuries()`, `_format_prior_window_summary()`, `_format_window_verbatim()` — shared helpers (also used by T2)
- `render_user_prompt()` — inline Python rendering of §6 template (Mustache replaced by f-string + conditional blocks); covers refresh request + athlete's words + parsed_intent signals + athlete profile + 3B periodization shape + 3A athlete state + 7-day prior summary table + sessions-being-replaced verbatim + sessions-after verbatim + conditional retry context

Wrote `layer4/plan_refresh_t2.py` (~280 lines) — T2-specific plumbing:
- `DEFAULT_MAX_TOKENS=4000`, `DEFAULT_EXTENDED_THINKING_BUDGET=4500` per T2 prompt body §7
- `SYSTEM_PROMPT` — full text matching `Layer4_RefreshT2_v1.md` §5 (different from T1: reshape-the-week language + weekly-aggregate guardrails + LSD anchor + deload-cadence-shape rules)
- `_format_weekly_aggregate()` — T2-only helper rendering total hours + session count + intensity distribution counts
- `render_user_prompt()` — mirrors T1 with T2-specific additions: weekly aggregate summary line of prior week, deload-cadence reminder, 7-day window scope, 7-day after-window continuity context. Reuses T1's `_format_*` helpers.

Modified `layer4/context.py` (~95 lines added) — `Layer2Bundle` + `ParsedIntent` pydantic v2 models at file end. Modified `layer4/__init__.py` adding 4 new re-exports (`Layer2Bundle`, `ParsedIntent`, `build_record_refresh_sessions_tool`, `llm_layer4_plan_refresh`).

Wrote `tests/test_layer4_plan_refresh.py` (~1000 lines, 58 tests):
- TestLayer2Bundle × 4 (empty + partial + full + extra-field-forbidden)
- TestParsedIntent × 3 (defaults + with text and flags + invalid signal rejected)
- TestToolSchema × 6 (T1 vs T2 maxItems + name + required fields + closed 7-flag enum + 9-shape IntensityTarget oneOf + intensity_zone enum)
- TestInputValidation × 11 (one per §4.3 row + T3-not-implemented)
- TestEntryPointHappyPath × 7 (T1 cardio single + T1 two-day + T1 empty + T2 full week + T2 mixed + telemetry + scope dates)
- TestObservationEmission × 3 (intensity_modulated emit + no flag + multi-session single observation)
- TestCappedRetry × 4 (validator fail then pass + cap-hit best-effort + first-pass accept + capped_retries=0)
- TestSchemaViolation × 3 (missing key + malformed all-the-way + malformed-then-valid recovers)
- TestLayer4PayloadComposition × 9 (mode + pattern + phase_structure-None + seam_reviews-None + suggestion_id-None + per-session phase_metadata-None + per-session is_ad_hoc-False + model_synthesizer + etl_version_set)
- TestPromptRendering × 7 (T1 athlete words + T1 placeholder + T1 retry conditional + T2 weekly aggregate + T1-vs-T2 differ + active injuries + parsed_intent=None default)

All 58 new tests green. Combined `tests/` count: 354 → 412, all green in 0.56s.

Amended `Layer4_Spec.md` §3.2 — surgical edit per Andy's §4.3-wins pick:
- Signature line 144 `Layer3BPayload | None` → `Layer3BPayload`
- Parameter table notes column for 3B rewritten — 3B required on every tier; T1's prior-narrative of "falls back to phase_metadata" retired; amendment dated 2026-05-17 inline.

### 2.3 Architectural choices on the record

- **Two-file tier split (`_t1.py` + `_t2.py`) per Andy's pick.** Mirrors the prompt-body D7 two-files pick (Andy 2026-05-17 prior session). Thin `plan_refresh.py` driver dispatches on tier; each tier file owns its `SYSTEM_PROMPT` + sampling defaults + `render_user_prompt()`. Shared formatting helpers (`_format_active_injuries` / `_format_prior_window_summary` / `_format_window_verbatim`) live in `plan_refresh_t1.py` and are imported by `plan_refresh_t2.py` (single source of truth; avoids duplication).
- **`Layer2Bundle` + `ParsedIntent` in `layer4/context.py` per Andy's pick.** Pydantic v2 models with `extra='forbid'`. Reusable across T3 (Step 4d) + Pattern A (Step 4f) + any future refresh entry points. Re-exported via `layer4/__init__.py`.
- **Tool schema = full PlanSession contract mirror (Step 4a Option 2 precedent).** `additionalProperties: false` at every nesting level; 9-shape `IntensityTarget` `oneOf` per cardio block; closed 7-flag refresh `coaching_flags` enum (`technique_emphasis`, `long_slow_distance`, `weak_link_targeted`, `overreach_test`, `discipline_specific_intensity`, `race_pace_specific`, `intensity_modulated`) — distinct from single_session's 3-flag enum since refresh covers phase-tied flags. T1's sessions array `maxItems=4` (2-day × max 2/day); T2's `maxItems=14` (7-day × max 2/day).
- **3B required for all tiers per Andy 2026-05-17 §4.3-wins pick.** Picked from a 3-option `AskUserQuestion` round. Tradeoff: heavier ripple — D-64's T1 default cascade now includes 3B re-run, contradicting `Plan_Refresh_D64_Design_v1.md` §3's T1 default. The design doc + T1 prompt body amendments are carried forward to next session (mechanically-spec'd; see §6.3). Spec contract preserved by amending §3.2 to drop the `| None`.
- **Pattern B Layer4Payload invariants honored:** `mode='plan_refresh'` + `pattern='B'` + `phase_structure=None` + `seam_reviews=None` + per-session `phase_metadata=None` (per §7.12 Pattern B rule) + per-session `is_ad_hoc=False` (refresh outputs aren't ad-hoc) + `suggestion_id=None` (D-63-only).
- **`parsed_intent=None` accepted at the entry-point boundary.** When caller passes None, driver substitutes a degraded `ParsedIntent(parser_confidence='low', ambiguity_notes='Parser unavailable; running default cascade only.')` per `Plan_Refresh_D64_Design_v1.md` §5.4. Tests cover this path explicitly.
- **Empty sessions output short-circuits validator.** When the LLM returns `{'sessions': []}` (entire window is rest by athlete schedule + coaching choice — explicitly allowed by prompt body D9), the driver synthesizes an accepted ValidatorResult inline (validator has nothing to validate) so the Layer4Payload `validator_results[-1].accepted=True` invariant holds.
- **`plan_version_id_parent` shape check defensive.** §4.3 row 6 `plan_version_id_parent_missing` requires an FK check against `plan_versions`; the orchestrator owns the FK, so Layer 4 does a defensive shape check (positive int) only. Documented inline in the function docstring.
- **`prior_plan_session_window` uses `kind='rest'` fixtures in tests** (with `duration_min=0` per the PlanSession schema invariant). Prior sessions are context-only — not validated for content shape; the rest-kind shape avoids the cardio_blocks-non-empty / strength_exercises-non-empty invariants.
- **T3 raises `tier_t3_not_yet_implemented`.** Pattern B intra-phase and Pattern A cross-phase both deferred to Step 4d / 4f per `Layer4_Spec.md` §14.3.4. Tested explicitly.
- **Schema-violation handling per §5.5.** When `_build_plan_session()` fails on any session in the list (pydantic ValidationError, KeyError, ValueError, TypeError), the driver enters a schema-only retry that doesn't consume the per-call budget. On second schema failure raises `Layer4OutputError('schema_violation')` and bails. Tested via `test_malformed_session_retries_then_raises` + `test_malformed_then_valid_recovers`.

### 2.4 Stop-and-ask triggers — #5 + #8 fired and routed; #2 + #11 did NOT fire

- **Trigger #5 (schema/inter-layer-contract amendments):** fired on the §3.2 vs §4.3 contradiction. Routed via the 4-question `AskUserQuestion` batch; Andy picked §4.3-wins. The surgical amendment to `Layer4_Spec.md` §3.2 (drop `| None`; rewrite notes column) is implementation-of-pick, not redesign. The two-round AskUserQuestion gate (4 questions in one batch) substitutes for formal `/plan` mode per the precedent from Step 4a §2.4.
- **Trigger #8 (architectural alternatives with real tradeoffs):** fired on the bundle-types-location pick + file-organization pick. Same `AskUserQuestion` batch; Andy picked `layer4/context.py` + two-file split.
- **Trigger #2 (designing or significantly modifying an LLM prompt body):** did NOT fire substantively this session. The T1 prompt body amendments (D3 + §3.5 + §3.8 reflecting 3B-now-always-included) are carried forward to next session per §6.3 (mechanically-spec'd surgical edits). T2 prompt body needs no v2 since it already documents "3B re-run as part of T2 cascade."
- **Trigger #11 (new cross-layer D-rows):** did NOT fire. No new D-rows; existing D-66/D-67/D-68/D-70/D-71 cover all forward-pointer cases.
- Other triggers — none applicable.

### 2.5 Scope NOT changed this session

- **Step 4d T3** — queued next. Pattern B intra-phase reuses the now-shipped Step 4b/c plumbing; cross-phase T3 routes to Pattern A and depends on Step 4f's per-phase orchestration.
- **Step 4e race-week-brief** — depends on D-66 race-event data model design wave.
- **Step 4f `plan_create` Pattern A orchestration** — heaviest of the 4 entry points.
- **Layer 1 typed payload** — out of v1 scope; `dict[str, Any]` opaque pass-through is the standing v1 contract.
- **D-66 / D-67 / D-68 / D-70 / D-71** — not touched.
- **`Plan_Refresh_D64_Design_v1.md` §3 T1 cascade amendment** — carried forward (mechanically-spec'd; see §6.3).
- **`Layer4_RefreshT1_v1.md` → `_v2.md`** — carried forward (mechanically-spec'd; see §6.3). T2 prompt body needs no v2.

---

## 3. Files shipped this session

One commit on `claude/implement-layer4-closing-YPmyc` — 6 substantive code + 1 spec + 3 bookkeeping bundled (precedented by PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6 + Step 4a 8).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `layer4/plan_refresh.py` | New | ~750 lines. Driver entrypoint + shared Pattern B plumbing — input validation, tool schema builder, Anthropic SDK adapter, tool-output parser, payload composition, observation emission, retry loop with schema-violation special case + best-effort acceptance. Dispatches on tier to `_t1` / `_t2` modules. |
| 2 | `layer4/plan_refresh_t1.py` | New | ~280 lines. T1 sampling defaults + `SYSTEM_PROMPT` + `render_user_prompt()` per `Layer4_RefreshT1_v1.md` §5/§6 + shared formatting helpers `_format_active_injuries` / `_format_prior_window_summary` / `_format_window_verbatim`. |
| 3 | `layer4/plan_refresh_t2.py` | New | ~280 lines. T2 sampling defaults + `SYSTEM_PROMPT` + `render_user_prompt()` per `Layer4_RefreshT2_v1.md` §5/§6 + T2-only `_format_weekly_aggregate` helper. Imports T1's `_format_*` helpers. |
| 4 | `layer4/context.py` | Modified | `Layer2Bundle` + `ParsedIntent` pydantic v2 models appended (~95 lines). |
| 5 | `layer4/__init__.py` | Modified | 4 new re-exports — `Layer2Bundle`, `ParsedIntent`, `build_record_refresh_sessions_tool`, `llm_layer4_plan_refresh`. |
| 6 | `tests/test_layer4_plan_refresh.py` | New | ~1000 lines, 58 tests, all green. Coverage: Layer2Bundle × 4 + ParsedIntent × 3 + tool schema × 6 + §4.3 input validation × 11 + entry-point happy path × 7 + observation emission × 3 + capped retry × 4 + schema violation × 3 + Layer4Payload composition × 9 + prompt rendering × 7. LLM calls mocked via `_stub_caller` / `_sequence_caller` closures — no live API calls. |
| 7 | `aidstation-sources/Layer4_Spec.md` | Modified | §3.2 surgical amendment — signature `Layer3BPayload \| None` → `Layer3BPayload`; parameter table notes column rewritten with §4.3-wins resolution citation (2026-05-17). |
| 8 | `aidstation-sources/Project_Backlog_v46.md` | New | Copy of v45 + file-revision-header bumped to v46 with Step 4b/c narrative; v45 demoted to first predecessor. No new D-rows. |
| 9 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 row → "Steps 4a + 4b + 4c of 8 COMPLETE"; Step 4a narrative compressed to predecessor entry; new Step 4b/c "Last shipped" narrative; Authoritative current files updated (Backlog v45 → v46; new `layer4/plan_refresh.py` + `_t1.py` + `_t2.py` + `tests/test_layer4_plan_refresh.py`); Next forward move recommends Step 4d (T3). |
| 10 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step4b_4c_PlanRefresh_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**10 files total. Over the 5-file ceiling intentionally** (precedent from PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6 + Step 4a 8).

---

## 4. What `layer4/plan_refresh.py` + `_t1.py` + `_t2.py` commit to

### 4.1 Function signature

```python
def llm_layer4_plan_refresh(
    user_id: int,
    tier: Literal['T1', 'T2', 'T3'],
    refresh_scope_start: date,
    refresh_scope_end: date,
    layer1_payload: dict[str, Any],
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,         # NON-OPTIONAL per Andy 2026-05-17 §4.3-wins
    prior_plan_session_window: list[PlanSession],
    parsed_intent: ParsedIntent | None,      # None → degraded default substituted
    plan_version_id: int,
    plan_version_id_parent: int,
    etl_version_set: dict[str, str],
    *,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str | None = None,  # T3 cross-phase Pattern A only
    temperature: float = 0.4,
    max_tokens: int | None = None,           # None → tier default
    capped_retries: int = 2,
    extended_thinking_budget: int | None = None,  # None → tier default
    llm_caller: LLMCaller | None = None,
) -> Layer4Payload:
    ...
```

Deviations from `Layer4_Spec.md` §3.2 (post-amendment):
1. `layer1_payload: dict[str, Any]` (not `Layer1Payload`) — Layer 1 typed schema out of v1 scope (PR-D precedent).
2. Added `plan_version_id_parent: int` positional parameter — orchestrator-supplied per §4.3 row 6 + §7.11 superseded_at/superseded_by_version_id FK relationship. The spec doesn't formally type this in §3.2 but §4.3 row 6 validates it; surfacing as a parameter makes the contract explicit.
3. `max_tokens` + `extended_thinking_budget` default `None` (tier-specific defaults loaded at dispatch); spec §3.2 sets defaults at the function-signature level (`max_tokens=4000`) but tier-distinct defaults are more accurate to the per-tier prompt-body §7 sampling.

### 4.2 Layer2Bundle + ParsedIntent

```python
class Layer2Bundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: Layer2APayload | None = None
    b: Layer2BPayload | None = None
    c: dict[str, Layer2CPayload] = Field(default_factory=dict)
    d: Layer2DPayload | None = None
    e: Layer2EPayload | None = None


class ParsedIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triggers_2a_discipline: bool = False
    triggers_2b_terrain: bool = False
    triggers_2c_equipment: list[str] = Field(default_factory=list)
    triggers_2d_injury: bool = False
    triggers_2e_nutrition: bool = False
    fatigue_signal: Literal["fresh", "normal", "tired", "wiped"] = "normal"
    sickness_signal: Literal["none", "recovering", "active"] = "none"
    motivation_signal: Literal["low", "normal", "high"] = "normal"
    raw_text: str = ""
    parser_confidence: Literal["high", "medium", "low"] = "high"
    ambiguity_notes: str | None = None
```

### 4.3 Tool schema (per the Step 4a Option 2 precedent)

`build_record_refresh_sessions_tool(tier)` returns a strict JSON schema:
- Top-level `sessions: array` with `minItems=0`, `maxItems=4` (T1) or `maxItems=14` (T2)
- Each session = full `PlanSession` contract mirror (same shape as `single_session.py`'s tool schema modulo the closed coaching_flags enum)
- Closed 7-flag coaching_flags enum (refresh-scope): technique_emphasis / long_slow_distance / weak_link_targeted / overreach_test / discipline_specific_intensity / race_pace_specific / intensity_modulated
- 9-shape `IntensityTarget` `oneOf` per cardio block (HRTarget / PowerTarget / PaceTarget / SwimPaceTarget / RPETarget / VerticalRateTarget / StrokeRateTarget / CadenceTarget / ClimbingGradeTarget)

### 4.4 Algorithm (driver behavior)

1. **Validate inputs** per §4.3 — raises `Layer4InputError` on first failing precondition (fail-fast).
2. **Dispatch on tier** — T3 raises `tier_t3_not_yet_implemented`; T1/T2 lazy-import the corresponding tier module.
3. **Load tier-specific defaults** — `SYSTEM_PROMPT`, `max_tokens`, `extended_thinking_budget`. Build tool schema with `maxItems` per tier.
4. **Build user prompt** with full payload context via the tier module's `render_user_prompt()`.
5. **Invoke synthesizer** via `_default_llm_caller` (or test stub) — Anthropic SDK `messages.create` with forced tool-use + extended thinking.
6. **Parse tool output** — each session dict → typed `PlanSession` via pydantic smart-union dispatch.
7. **Run §5.4 validator** via `validate_layer4_payload(payload, ctx, pass_index)` with `ValidatorContext` bundling Layer2Bundle.a/b/c/d/e + 3A + 3B.
8. **On validator failure**, retry up to `capped_retries` (default 2) with `RuleFailure` context merged into the user prompt's retry-context section.
9. **On cap-hit with unresolved blockers**, demote blocker → warning per §5.5; append a new accepted ValidatorResult so the Layer4Payload invariant holds; emit `Observation(category='best_effort_plan', elevates_to_hitl=True)`.
10. **On schema-violation** (tool args parse failure), one schema-only retry per §5.5 (doesn't consume per-call budget); on second failure raises `Layer4OutputError('schema_violation')`.
11. **Emit `Observation(category='intensity_modulated', elevates_to_hitl=False)`** per §8.6/§8.7 when ANY session in the refresh output carries the matching coaching_flag. ONE observation emitted regardless of how many sessions; text references the affected count.

---

## 5. Next session pointers — Step 4d T3 integration

**Architect-recommended next per `CLAUDE.md` "Next forward move":**

### Step 4d scope: `llm_layer4_plan_refresh` T3 (D-64 caller, 28-day refresh)

T3 is the largest scope refresh; routes to:
- **Pattern B** when scope is entirely inside one phase (e.g., athlete is mid-Base with 6+ weeks of Base remaining)
- **Pattern A** when scope spans a phase boundary (the common mid-plan case)

Pattern B intra-phase reuses the Step 4b/c plumbing — driver + tool schema + retry loop + best-effort fallback + observation emission all carry over. The only T3-specific work is:
- New prompt body `Layer4_RefreshT3_v1.md` (or subsume into the T2 long-window prompt per `Layer4_Spec.md` §5.1's "T3 falls back to Pattern B with a per-phase prompt" note)
- Tool schema `maxItems` increase (28-day × max 2/day = 56)
- T3 input validation (`tier_scope_mismatch` ≤ 32 days)
- Phase-boundary detection in the driver — when scope_start..scope_end crosses a `PhaseStructure.phases[].(start_date, end_date)` boundary, route to Pattern A instead

Pattern A cross-phase depends on Step 4f's per-phase orchestration + seam reviewer wiring; defer to that session.

**Stop-and-ask risk:** Moderate. The Pattern A scaffolding (per-phase synthesis loop + seam reviewer loop + cross-phase validator pass) is new architectural surface. Trigger #8 likely on the per-phase orchestration shape. Trigger #2 fires if a new T3 prompt body is needed.

### Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (Step 4b/c).
3. **Third re-read**: `Layer4_Spec.md` §3.2 (signature; post-amendment), §4.3 (preconditions; T3 specifically), §5.1 (T3 routing — Pattern B intra-phase + Pattern A cross-phase), §5.2 (Pattern A algorithm), §5.4 (validator harness), §5.5 (capped retry), §6.1 (phase_structure_from_3b helper), §6.2 (seam-driven re-prompt path), §6.5 (start_phase non-Base case).
4. **Fourth re-read**: `Plan_Refresh_D64_Design_v1.md` §3 (T3 default cascade) + the Step 4b/c reference impl `layer4/plan_refresh.py` + `_t1.py` + `_t2.py`.
5. **Branch**: cut a fresh branch off post-merge main; or stay on a harness pin per precedent.
6. **Test convention**: top-level `tests/test_layer4_plan_refresh_t3.py` alongside the existing Step 4b/c test file; OR extend `tests/test_layer4_plan_refresh.py` with T3 classes.
7. **Reuse pattern**: extend `llm_layer4_plan_refresh()` dispatch on tier — T3 case should call a new `layer4/plan_refresh_t3.py` module with the same shape as `_t1.py` / `_t2.py`.

### Carry-forward edits to land before Step 4d (mechanically-spec'd)

These edits are deferred from this session per Rule #11; they ARE the §4.3-wins ripple that wasn't bundled here:

**Edit 1: `aidstation-sources/Plan_Refresh_D64_Design_v1.md` §3 — T1 default cascade includes 3B re-run.**

Old text (line ~80, exact pattern):
```
- **T1 — Today + tomorrow (2 days).** Re-run only 3A by default. Layer 4 reads inherited phase from adjacent-session metadata in `prior_plan_session_window`.
```
New text:
```
- **T1 — Today + tomorrow (2 days).** Re-run 3A + 3B by default. Per `Layer4_Spec.md` §4.3 (Andy 2026-05-17 §4.3-wins amendment), Pattern B's validator reads phase intent from a freshly-re-run 3B for the intensity-distribution check; the prior-session-metadata fallback path was retired.
```

**Edit 2: `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` → `_v2.md` per Rule #12** — v1 retained as in-project history.

Surgical edits in `_v2.md`:
- Header status line: add "v2 — 2026-05-17 (Andy 2026-05-17 §4.3-wins amendment per `Layer4_Spec.md` §3.2 — 3B now always passed; T1 inherits-from-prior-sessions fallback retired)"
- D3 source decision row: change "T1: full payloads verbatim (3A + 2A + 2D + 1 + request + `parsed_intent`)" to "T1: full payloads verbatim (3A + **3B (per §4.3-wins amendment)** + 2A + 2D + 1 + request + `parsed_intent`)"
- §3.5 (Periodization shape): change "T1 doesn't re-run 3B; periodization shape is inherited from adjacent-session metadata" to "T1 re-runs 3B per the 2026-05-17 §4.3-wins amendment; the periodization shape is read from the freshly-re-run 3B payload"
- §3.8 (Intentionally NOT passed): remove the "`layer3b_payload` — T1 default cascade doesn't re-run 3B" line entirely

T2 prompt body needs no amendment — already reads "Periodization shape — freshly-re-run 3B" (line 114 of `Layer4_RefreshT2_v1.md`).

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Step 4b/c bundled T1+T2 (architect-recommended) | Andy 2026-05-17 | Picked from the 3-option scope question; T1+T2 share Pattern B plumbing. |
| 2 | §4.3 wins — 3B required for T1/T2 (heavier ripple than §3.2-wins) | Andy 2026-05-17 | Picked from a 3-option `AskUserQuestion`; Andy chose the validator-side authority over the signature-side narrative. Implies surgical amendments to §3.2 + D-64 §3 + T1 prompt body D3 + §3.5 + §3.8 (some carried forward). |
| 3 | `Layer2Bundle` + `ParsedIntent` in `layer4/context.py` | Andy 2026-05-17 | Reusable across all refresh entry points + T3 + Pattern A; pydantic v2 mirrors of spec types. |
| 4 | Two-file tier split (`_t1.py` + `_t2.py`) | Andy 2026-05-17 | Mirrors the prompt-body D7 two-files pick; clear separation of T1 vs T2 surface; thin driver dispatcher. |
| 5 | Tool schema = full PlanSession contract mirror | Architect-pick (Step 4a precedent) | Same fidelity as `single_session.py`; LLM emits the full contract; no post-process default-filling. |
| 6 | `parsed_intent=None` accepted; driver substitutes degraded default | Architect-pick; spec-aligned | Per `Plan_Refresh_D64_Design_v1.md` §5.4 parser-unavailable graceful degrade. |
| 7 | `plan_version_id_parent` as explicit positional parameter | Architect-pick | §4.3 row 6 requires the FK check; surfacing as a parameter makes the contract explicit. |
| 8 | T3 raises `tier_t3_not_yet_implemented` | Architect-pick; spec-aligned | Per §14.3.4 sequencing — Step 4d Pattern B intra-phase + Step 4f Pattern A cross-phase are separate sessions. |
| 9 | Empty sessions output short-circuits validator | Architect-pick | Prompt body D9 explicitly allows 0-N sessions; validator has nothing to validate; inline synthesizes accepted ValidatorResult. |
| 10 | `kind='rest'` fixtures in tests for `prior_plan_session_window` | Architect-pick | Prior sessions are context-only; rest-kind avoids the cardio_blocks-non-empty / strength_exercises-non-empty invariants. |
| 11 | Shared formatting helpers in `_t1.py`; imported by `_t2.py` | Architect-pick | Single source of truth for `_format_active_injuries` / `_format_prior_window_summary` / `_format_window_verbatim`. |

### 6.2 Stop-and-ask trigger retrospective

- **Trigger #5 + #8** fired and routed properly via the 4-question `AskUserQuestion` batch (scope + 3B-T1 gap + bundle types location + file organization).
- **Trigger #2** did NOT fire substantively this session (T1 prompt body amendments are carry-forward).
- **Trigger #11** did NOT fire — no new D-rows.

### 6.3 Carry-forward to Step 4d session (mechanically-spec'd per Rule #11)

| # | Edit | File | Surgical pattern |
|---|---|---|---|
| 1 | T1 default cascade includes 3B re-run | `aidstation-sources/Plan_Refresh_D64_Design_v1.md` §3 | See §5 "Edit 1" above for exact old_text / new_text |
| 2 | T1 prompt body v1 → v2 (D3 + §3.5 + §3.8) | `aidstation-sources/prompts/Layer4_RefreshT1_v2.md` (new; v1 retained) | See §5 "Edit 2" above for exact pattern |

T2 prompt body needs no v2 amendment — already documents 3B as a T2 input.

### 6.4 Carried forward to Step 4d / 4e / 4f

- **Step 4d T3 intra-phase** — Pattern B; reuses Step 4b/c plumbing; new `layer4/plan_refresh_t3.py` projected. ~2-3 substantive code files.
- **Step 4d T3 cross-phase** — Pattern A; defers to Step 4f's per-phase orchestration.
- **Step 4e race-week-brief** — depends on D-66 race-event data model.
- **Step 4f `plan_create`** — heaviest; per-phase synthesis + seam reviewer.

### 6.5 Carried forward to Layer 1 typed payload (deferred)

- `Layer1Payload` is currently `dict[str, Any]` opaque pass-through across all 4 entry points. Lands as a typed pydantic model when the Layer 1 implementation arc begins.

---

## 7. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/plan_refresh.py` exists with `llm_layer4_plan_refresh` + `build_record_refresh_sessions_tool` + `_validate_inputs` + driver helpers | ✅ inspection |
| `layer4/plan_refresh_t1.py` exists with `SYSTEM_PROMPT` + `DEFAULT_MAX_TOKENS=2000` + `DEFAULT_EXTENDED_THINKING_BUDGET=3000` + `render_user_prompt` | ✅ inspection |
| `layer4/plan_refresh_t2.py` exists with `SYSTEM_PROMPT` + `DEFAULT_MAX_TOKENS=4000` + `DEFAULT_EXTENDED_THINKING_BUDGET=4500` + `render_user_prompt` + `_format_weekly_aggregate` | ✅ inspection |
| Tool schema T1 maxItems=4; T2 maxItems=14 | ✅ `test_t1_maxitems_4` + `test_t2_maxitems_14` pass |
| 9-shape `IntensityTarget` `oneOf` in tool schema | ✅ `test_intensity_target_oneof_nine_shapes` passes |
| Closed 7-flag coaching_flags enum | ✅ `test_coaching_flags_closed_7_set` passes |
| `Layer2Bundle` + `ParsedIntent` in `layer4/context.py` with `extra='forbid'` | ✅ `TestLayer2Bundle` + `TestParsedIntent` pass |
| §4.3 preconditions raise `Layer4InputError` on each row | ✅ 11 TestInputValidation tests pass |
| Entry-point happy path: Layer4Payload with mode='plan_refresh' + pattern='B' + phase_structure=None + seam_reviews=None + suggestion_id=None + per-session phase_metadata=None + per-session is_ad_hoc=False | ✅ TestEntryPointHappyPath × 7 + TestLayer4PayloadComposition × 9 pass |
| Validator retry: fail then pass retries once | ✅ test_validator_fail_then_pass_retries_once passes |
| Validator cap-hit emits best_effort_plan Observation + demotes blockers to warnings | ✅ test_cap_hit_emits_best_effort_observation passes |
| Schema-violation: one schema-only retry; second failure raises | ✅ test_malformed_then_valid_recovers + test_malformed_session_retries_then_raises pass |
| intensity_modulated flag → Observation emitted (one observation regardless of count) | ✅ TestObservationEmission × 3 pass |
| T3 raises `tier_t3_not_yet_implemented` | ✅ test_t3_not_yet_implemented passes |
| `Layer4_Spec.md` §3.2 signature drops `\| None` on `layer3b_payload` | ✅ grep |
| `Layer4_Spec.md` §3.2 notes column rewritten with §4.3-wins amendment citation | ✅ grep |
| `layer4/__init__.py` re-exports 4 new symbols alongside existing | ✅ grep `__all__` |
| `tests/test_layer4_plan_refresh.py` 58 tests, all green | ✅ `python -m pytest tests/test_layer4_plan_refresh.py` |
| Combined `tests/` (payload + hashing + context + validator + single_session + plan_refresh) = 412 tests, all green | ✅ `python -m pytest tests/` 0.56s |
| No regression in prior 354 tests | ✅ same 354 prior tests + 58 new = 412 |
| `Project_Backlog_v46.md` exists; file-revision-header is v46; v45 demoted inline | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v46.md` | ✅ grep |
| `CLAUDE.md` Layer 4 row mentions "Steps 4a + 4b + 4c of 8 COMPLETE" | ✅ grep |
| `CLAUDE.md` Last-shipped is Step 4b/c; Step 4a demoted to Predecessor | ✅ inspection |
| `CLAUDE.md` Next-forward-move recommends Step 4d (T3) | ✅ inspection |
| Working tree shows 10 files modified / created | ✅ `git status` |
| Branch is `claude/implement-layer4-closing-YPmyc` (harness-pinned) | ✅ |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; Step 4b/c is implementation-layer (no UI surface; no new §5.0 row needed).
- Step 4d T3 — queued next session against the now-complete refresh plumbing surface.
- Step 4e race-week-brief — depends on D-66 race-event data model design wave.
- Step 4f `plan_create` Pattern A orchestration — queued post-Step-4d.
- Step 5–8 (cache layer, Pattern A orchestration, live LLM integration, T3/auto-fire picks) — queued post-Step-4.
- v5 onboarding implementation PR — independent of Layer 4 implementation track; can run in parallel.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.

---

**End of handoff.**
