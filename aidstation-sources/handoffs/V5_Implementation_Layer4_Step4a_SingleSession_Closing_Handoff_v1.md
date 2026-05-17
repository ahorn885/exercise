# V5 Implementation — Layer 4 Step 4a Single-Session D-63 Closing Handoff

**Session:** Single chat. Scope: Step 4a of `Layer4_Spec.md` §14.3.4 — `llm_layer4_single_session_synthesize` (D-63 caller integration). Pattern B single-call algorithm per §5.3 + capped-retry per §5.5 + `intensity_modulated` observation emission per §8.7. Paired prompt-body amendment `Layer4_SingleSession_v1.md` → `_v2.md` (§4.1 tool-schema fidelity per D13 Andy Option 2 pick).
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step3_PR_E_Validator_Closing_Handoff_v1.md` (PR-E — `layer4/validator.py` 21-rule §5.4 deterministic validator harness; 96 tests; combined 305 green).
**Branch:** `claude/implement-v5-validator-WelCn` (harness-pinned for this session — name carried over from a prior validator-scoped branch even though this PR is Step 4a single-session integration; precedent: PR-A → PR-B → PR-C → PR-C-followon → PR-D → PR-E all harness-pinned with mismatched names).
**Status:** 🟢 5 substantive code/spec + 3 bookkeeping = 8 files. 49 new tests; combined `tests/` count 305 → 354, all green in 0.64s. **Layer 4 implementation Step 4a closes here; Step 4 (per-entry-point LLM call sites) opens.**

---

## 1. Session-start verification (Rule #9)

Predecessor (PR-E) handoff §7 claimed: `layer4/validator.py` (~1370 lines) on disk with `ValidatorContext` frozen dataclass + 21 `_rule_*` functions + `_ALL_RULES` tuple + `validate_layer4_payload` driver; `layer4/__init__.py` re-exports `ValidatorContext` + `validate_layer4_payload`; `tests/test_layer4_validator.py` 96 tests green; combined 305 green; `Project_Backlog_v44.md` exists; CLAUDE.md Backlog ref reads v44; PR-E merge commit on `origin/main`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `layer4/validator.py` exists with 21 `_rule_*` functions + `_ALL_RULES` tuple + `validate_layer4_payload` driver | grep + line count | ✅ 1371 lines |
| `layer4/__init__.py` re-exports `ValidatorContext` + `validate_layer4_payload` | inspection | ✅ |
| `tests/test_layer4_validator.py` 96 tests, combined `tests/` 305 green | `python -m pytest tests/` | ✅ 305 passed in 0.57s |
| `Project_Backlog_v44.md` exists | `ls` | ✅ |
| CLAUDE.md Backlog ref reads v44 | grep | ✅ |
| PR-E merge commits `0a58f53` + `600ba41` on `origin/main` | `git log` | ✅ |
| Working tree clean on fresh-cut branch | `git status` | ✅ clean |
| Current branch `claude/implement-v5-validator-WelCn` (harness pin) | `git branch` | ✅ |

**No drift found.** PR-E state on disk matches the handoff narrative. Branch name `claude/implement-v5-validator-WelCn` is a harness pin; surfaced to Andy at session start; Andy confirmed Step 4a scope on that branch (matches the harness-name-vs-scope precedent established in PR-B → PR-E).

---

## 2. Session narrative — Andy-confirmed scope; implementation-of-spec PR; trigger #8 + #2 fired and routed

Andy opened with a URL pointer to the PR-E closing handoff and "let's work." I followed §5 operating notes — re-read CLAUDE.md (Rule #13), ran Rule #9 verification, surfaced state + next focus + drift (none), surfaced the branch-name-vs-scope harness pin, asked Andy to confirm scope via `AskUserQuestion`. Andy picked Step 4a (architect-recommended). Then I surfaced a load-bearing architectural call — tool-schema fidelity — via a second `AskUserQuestion` round; Andy picked Option 2 (full payload-contract mirror) + bundled 8 files (precedented).

### 2.1 Single-pass implementation against the spec

Read `Layer4_Spec.md` §3.3 (single_session function signature; ~30 lines), §3.5 (errors raised), §4.4 (input validation preconditions; ~20 lines), §5.3 (Pattern B algorithm; ~30 lines), §5.5 (capped retry semantics; ~12 lines), §8.7 (call-level observations triggers; ~20 lines), §9.1 (single_session_synthesize_key cache formula), §9.4 (rebinding semantics). Read `Layer4_SingleSession_v1.md` (~590 lines) for source decisions D1–D12 + tool schema sketch + system prompt + user prompt template + edge cases + test scenarios. Read `layer4/payload.py` (~682 lines) for the canonical `Layer4Payload` + `PlanSession` + `CardioBlock` + `StrengthExercise` + `IntensityTarget` union shapes. Read `layer4/validator.py` to anchor the `ValidatorContext` construction shape + the mode-gating policy. Read `layer4/context.py` for `Layer2CPayload` / `Layer2DPayload` / `Layer3APayload` field shapes the user prompt needs. Read `routes/coaching.py` for the existing Anthropic SDK reuse pattern (`anthropic.Anthropic(api_key=...).messages.create(...)`).

Wrote `layer4/errors.py` (~30 lines) — `Layer4Error` base + `Layer4InputError` + `Layer4OutputError` per spec §3.5. Wrote `layer4/single_session.py` (~720 lines) — `SingleSessionRequest` pydantic v2 model + `build_record_single_session_tool()` (full payload-mirror tool schema) + `_validate_inputs()` (§4.4 preconditions) + `_render_user_prompt()` (inline Python rendering of `Layer4_SingleSession_v2.md` §6 user-prompt template) + `_default_llm_caller` (Anthropic SDK adapter) + `_build_plan_session()` (parses tool args → typed PlanSession) + `_build_layer4_payload()` (composes the final payload) + `_emit_intensity_modulated_observation()` (§8.7) + main `llm_layer4_single_session_synthesize()` driver (retry loop + best-effort fallback). Modified `layer4/__init__.py` adding 6 re-exports. Wrote `tests/test_layer4_single_session.py` (~720 lines, 49 tests). Wrote `Layer4_SingleSession_v2.md` (~570 lines — v1 copy + surgical header bump + D13 row + §4.1 rewrite). Combined `tests/` count: 305 → 354, all green in 0.64s.

### 2.2 Contract gap surfaced + handled inline

**`Layer1Payload` is not a typed contract in `layer4/context.py`.** Layer 1 typed schemas are out of scope for the current implementation arc (Layer 1 is "In progress — D-51 field inventory pending" per CLAUDE.md line 39). The §3.3 signature references `Layer1Payload` but no shape exists. Decision: define the parameter as `dict[str, Any]` opaque pass-through per the PR-D precedent for unmapped upstream shapes (`Layer2DHitlItem.injury` / `.condition` typed `dict[str, Any]`). The user-prompt template reads `experience_level` + `coaching_voice_preferences` keys; missing keys render as `"unknown"` / omit silently. No spec amendment — the spec contract is preserved verbatim; the implementation handles the unmapped type via opaque dict.

### 2.3 Architectural choices on the record

- **`SingleSessionRequest` as pydantic v2 BaseModel with `extra='forbid'`** — D-63's input crosses an untrusted JSON boundary (frontend → backend); pydantic + extra='forbid' + Literal enum validation + Field bounds + `_check_locale_xor_quick_equipment` model_validator gives path-precise validation at construction. Caller can also pass it through API → Layer 4 → cache key building (`single_session_synthesize_key` consumes the request as canonical-JSON).
- **Tool-schema = full `PlanSession` payload-contract mirror (Andy 2026-05-17 Option 2 pick).** Three architectural alternatives surfaced via `AskUserQuestion` per stop-and-ask trigger #8 (architectural alternatives with real tradeoffs); Andy picked maximal fidelity. Tradeoff: larger LLM output budget on what was already a 1500-token-cap entry; v1 sketch (Option 1) would have required arbitrary post-process defaults for intensity_zone per block, intensity_target shape, exercise_name, rest_between_sets_sec. Spec contract preserved — no `Layer4_Spec.md` amendment required since v1 prompt body's §4.1 was explicitly v1-scoped (line 134 references the canonical `PlanSession` shape; reconciling to the on-disk pydantic contract is implementation-of-spec).
- **9-shape `IntensityTarget` `oneOf` union in tool schema with smart-union dispatch at parse.** The LLM picks the shape matching the sport (HR for endurance, Power for bike, Pace for running, RPETarget as universal fallback, etc.); pydantic's smart-union resolves at `CardioBlock(**block_dict)` construction. Per-block flexibility is a v1 strength — different blocks within one session can use different target shapes (e.g., a brick workout's run block uses PaceTarget, the bike block uses PowerTarget).
- **`_default_llm_caller` dependency injection via `LLMCaller` type alias.** Tests pass a stub closure that returns canned `_SynthesizerOutput`; production callers leave `llm_caller=None` and the function loads `ANTHROPIC_API_KEY` from env at call time. The `_default_llm_caller` issues `client.messages.create(model=..., max_tokens=..., temperature=..., system=..., messages=..., tools=[tool_schema], tool_choice={'type':'tool','name':'record_single_session'}, thinking={'type':'enabled','budget_tokens':3500})` then extracts the `tool_use` block matching the tool name.
- **`plan_version_id=0` v1 sentinel for D-63 ad-hoc outputs.** Spec §3.3 calls for `plan_version_id=None` on D-63 outputs but `Layer4Payload.plan_version_id` is typed as `int` (non-None) at the payload contract level. v1 uses 0 as the sentinel for "ad-hoc, no plan pinning"; the function signature accepts `plan_version_id: int = 0` so the orchestrator can override; documented inline. v2 may revisit (loosen `Layer4Payload.plan_version_id: int | None` to match spec) once the orchestrator surface is built and the sentinel rate is measured.
- **`sport_not_in_inclusion` §4.4 row 6 NOT checked at Layer 4.** No `layer2a_payload` parameter in the §3.3 signature — caller pre-checks per D-63 §6.3. The §4.4 spec row says "Caller-side pre-check expected per D-63 §6.3: D-63 catches this case before invoking Layer 4 and returns the sport unavailable response with [Pick another location] / [Pick another sport] affordances directly to the frontend. Layer 4 raises this code defensively if the caller-side pre-check is missed — the LLM is never invoked on impossible requests." But Layer 4 can't raise it defensively without the data. Documented inline as a v1 limitation.
- **Best-effort fallback synthesizes a final accepted ValidatorResult with demoted warnings.** The `Layer4Payload._check_validator_results` invariant requires `validator_results[-1].accepted=True`. On cap-hit with unresolved blockers, the driver demotes blocker → warning per §5.5 "outstanding `RuleFailure` rows in the cap-hit pass are demoted to `severity='warning'`" and appends a new accepted ValidatorResult so the invariant holds. Plus emits `Observation(category='best_effort_plan', elevates_to_hitl=True)`.
- **Schema-violation handled per §5.5 "Schema-violation special case".** When `_build_plan_session()` fails (pydantic ValidationError, KeyError, or ValueError on tool args parse), the driver enters one schema-only retry that does NOT consume the per-call budget. On second schema failure raises `Layer4OutputError('schema_violation')` and bails. Tested via `test_malformed_session_retries_then_raises` + `test_malformed_then_valid_recovers`.
- **`_render_user_prompt()` inline Python rendering instead of Mustache.** The prompt body uses Mustache syntax (`{{#var}}` / `{{^var}}`) but the implementation builds the prompt with Python f-strings + conditional `if/else` blocks. The rendered output matches the Mustache template's intent; avoids pulling in a Mustache library dependency.
- **`_emit_intensity_modulated_observation()` orchestrator-side emission per §8.7.** The synthesizer emits the `intensity_modulated` session coaching_flag (per §5 system prompt Tier 3 modulation policy); the orchestrator side (this driver) emits the paired `Observation(category='intensity_modulated', elevates_to_hitl=False)` row. The `sport_unavailable_at_locale` + `off_plan_day_note` categories from §8.7 are NOT emitted here — `sport_unavailable_at_locale` is the §4.4 raise path (no Layer4Payload returned); `off_plan_day_note` is D-63 §6.4 caller-side check (orchestrator-side concern). Spec-aligned.
- **`Layer1Payload` opaque `dict[str, Any]`** — see §2.2.

### 2.4 Stop-and-ask triggers — #8 + #2 fired and routed; #5 did NOT fire

- **Trigger #8 (architectural alternatives with real tradeoffs):** fired and routed properly via `AskUserQuestion` — three tool-schema-fidelity options surfaced; Andy picked Option 2 (full payload-contract mirror). Then a second `AskUserQuestion` round for file-count budget; Andy bundled bookkeeping per precedent.
- **Trigger #2 (designing or significantly modifying an LLM prompt body):** fired indirectly via the Option 2 pick. The v2 amendment is scoped to §4.1 tool schema + D13 source-decision row only; no coaching-policy / §5 system prompt / §6 user prompt changes. Rule #12 (numeric version suffix) honored — `Layer4_SingleSession_v1.md` retained as in-project history; new `_v2.md` saved. The amendment is implementation-of-spec (the v1 §4.1 sketch was explicitly v1-scoped per line 134 "matching the `PlanSession` discriminated union per `Layer4_Spec.md` §7.2"; reconciling to the on-disk pydantic contract is the literal intent of "matching"). Considered the formal `/plan` mode gating per the PR-A Andy 2026-05-17 amendment-authoring directive — concluded `/plan` mode was already exercised via the two-round `AskUserQuestion` flow (architectural picks + bookkeeping picks both Andy-confirmed before edits applied).
- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire. `Layer4_Spec.md` untouched. The v1 baseline sentinels in v2's tool schema are implementation-of-spec, not contract changes — the canonical contract lives in `layer4/payload.py` (`Layer4Payload`) which is unchanged; the v2 tool schema mirrors it.
- **Trigger #11 (new cross-layer D-rows):** did NOT fire. No new D-rows; existing D-66 / D-67 / D-68 / D-70 / D-71 cover all forward-pointer cases.
- Other triggers — none applicable.

### 2.5 Scope NOT changed this session

- **Step 4b/c (`llm_layer4_plan_refresh` T1+T2)** — queued next. Pattern B refresh; consumes `Layer4_RefreshT1_v1.md` + `Layer4_RefreshT2_v1.md` prompt bodies + the now-complete Layer 4 implementation surface. T3 intra-phase also Pattern B; T3 cross-phase requires Pattern A (defer to Step 4d/4f).
- **Step 4e race-week-brief integration** — depends on D-66 race-event data model design.
- **Step 4f `plan_create` Pattern A orchestration** — heaviest of the 4 entry points (per-phase + seam reviewer; ~6-8 files). Step 5 cache layer + Step 6 Pattern A orchestration + Step 7 live LLM integration + Step 8 picks (T3/auto-fire/error-routing) queued after Step 4 closes.
- **Layer 1 typed payload** — out of v1 scope; `dict[str, Any]` opaque pass-through is the standing v1 contract.
- **D-70 / D-71 / D-66 / D-67 / D-68** — not touched.

---

## 3. Files shipped this session

One commit on `claude/implement-v5-validator-WelCn` — 5 substantive code/spec + 3 bookkeeping bundled (precedented by PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `layer4/single_session.py` | New | ~720 lines. `SingleSessionRequest` + `build_record_single_session_tool()` + `_validate_inputs()` + `_render_user_prompt()` + `_default_llm_caller` + `_build_plan_session()` + `_build_layer4_payload()` + main entry-point. Implements §3.3 + §4.4 + §5.3 + §5.5 + §8.7. |
| 2 | `layer4/errors.py` | New | ~30 lines. `Layer4Error` base + `Layer4InputError` + `Layer4OutputError` per §3.5; carries stable `code` string the orchestrator routes on. |
| 3 | `layer4/__init__.py` | Modified | 6 new re-exports — `SingleSessionRequest`, `build_record_single_session_tool`, `llm_layer4_single_session_synthesize`, `Layer4Error`, `Layer4InputError`, `Layer4OutputError`. |
| 4 | `tests/test_layer4_single_session.py` | New | ~720 lines, 49 tests, all green. Coverage: SingleSessionRequest validation × 9 + tool schema basics × 5 + §4.4 input validation × 4 + entry-point happy path × 8 + observation emission × 2 + capped retry × 4 + schema violation × 3 + Layer4Payload composition × 9 + prompt rendering × 5. LLM calls mocked via `_stub_caller` / `_sequence_caller` closures — no live API calls in tests. |
| 5 | `aidstation-sources/prompts/Layer4_SingleSession_v2.md` | New | ~570 lines. v1 copy + surgical header bump (status / date / v2-changes block) + D13 source-decision row + §4.1 rewrite (tool schema sketch → reference to `layer4.single_session.build_record_single_session_tool()` + field-by-field spec listing the full PlanSession contract). v1 §§1–3 + §§5–14 carry over unchanged. v1 retained as in-project history per Rule #12. |
| 6 | `aidstation-sources/Project_Backlog_v45.md` | New | Copy of v44 + file-revision-header bumped to v45 with Step 4a narrative; v44 demoted to first predecessor. No new D-rows (no contract gaps surfaced). |
| 7 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 row → "Step 4a of 8 COMPLETE"; PR-E narrative compressed to predecessor entry; new Step 4a "Last shipped" narrative; Authoritative current files updated (Backlog v44 → v45; prompt body v1 → v2 note; new `layer4/errors.py` + `layer4/single_session.py` + `tests/test_layer4_single_session.py`); Next forward move recommends Step 4b/c (T1+T2 refresh). |
| 8 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step4a_SingleSession_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**8 files total. Over the 5-file ceiling intentionally** (Andy explicit confirmation at session start; precedent from PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6).

---

## 4. What `layer4/single_session.py` commits to

### 4.1 Function signature

```python
def llm_layer4_single_session_synthesize(
    user_id: int,
    request: SingleSessionRequest,
    layer1_payload: dict[str, Any],
    layer2c_payload_for_locale: Layer2CPayload | None,
    layer2d_payload: Layer2DPayload,
    layer3a_payload: Layer3APayload,
    suggestion_id: int,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.3,
    max_tokens: int = 1500,
    capped_retries: int = 2,
    extended_thinking_budget: int = 3500,
    plan_version_id: int = 0,
    session_date: date | None = None,
    llm_caller: LLMCaller | None = None,
) -> Layer4Payload:
    ...
```

Deviates from spec §3.3 signature in two ways:
1. `layer1_payload: dict[str, Any]` (not `Layer1Payload`) — Layer 1 typed schema out of v1 scope.
2. Adds `extended_thinking_budget`, `plan_version_id`, `session_date`, `llm_caller` keyword params for implementation flexibility (defaults match spec semantics; `llm_caller` is dependency-injectable for tests).

### 4.2 SingleSessionRequest

D-63 §4.3 contract:

```python
class SingleSessionRequest(BaseModel):
    sport: str
    duration_min: int  # 30 <= n <= 360
    intensity: Literal["easy", "moderate", "hard", "race_pace"]
    locale_slug: str | None = None
    quick_equipment: list[str] = []
    notes_for_synthesizer: str | None = None
```

Locale XOR quick_equipment enforced at construction via `_check_locale_xor_quick_equipment` model_validator. `race_pace` intensity per D-63 §4.3 schema; the prompt treats it as `'hard'` with `discipline_specific_intensity` flag per `Layer4_SingleSession_v1.md` §11 row 5.

### 4.3 Tool schema (full payload-contract mirror per D13)

`build_record_single_session_tool()` returns a strict JSON schema with `additionalProperties: false` at every nesting level, mirroring the full `Layer4Payload.PlanSession` contract from `layer4/payload.py`:

- **Required top-level `session` fields:** `date`, `day_of_week`, `session_index_in_day`, `time_of_day`, `kind`, `duration_min`, `intensity_summary`, `session_notes`, `coaching_intent`, `coaching_flags`.
- **Optional:** `discipline_id`, `discipline_name`, `locale_id`, `locale_name`, `cardio_blocks` (cardio sessions), `strength_exercises` (strength sessions), `rest_reason`.
- **`cardio_blocks[]`:** `block_kind`, `duration_min`, `intensity_zone` (Z1-Z5/mixed), `intensity_target` (one of 9 `oneOf` shapes), `instructions`. Conditional on interval_set: `repetitions`, `rest_between_min`, `rest_intensity_zone`.
- **`strength_exercises[]`:** `exercise_id`, `exercise_name`, `resolution_tier` (1/2/3), `sets`, `reps_per_set` (int or string), `load_prescription`, `rest_between_sets_sec`, `instructions`, `coaching_flags`. Optional: `substitute_text`, `proxy_origin_id`, `tempo`.
- **`coaching_flags`:** closed enum `[intensity_modulated, technique_emphasis, discipline_specific_intensity]` per D5 of the prompt body. Phase-tied flags excluded.

The 9-shape `IntensityTarget` `oneOf` union lets the LLM pick the shape matching the sport (HRTarget for endurance, PowerTarget for bike, PaceTarget for running, etc.); pydantic smart-union resolves at parse time.

### 4.4 Algorithm (driver behavior)

1. **Validate inputs** per §4.4 — raises `Layer4InputError` on first failing precondition.
2. **Build user prompt** with full payload context (athlete request, Layer 1 athlete context, 2D injury list, 2C equipment view or quick_equipment list, 3A current state + recent trajectory + ACWR + data_density, optional retry context with `RuleFailure` rows).
3. **Invoke synthesizer** via `_default_llm_caller` (or test stub) — Anthropic SDK `messages.create` with forced tool-use + extended thinking.
4. **Parse tool output** into `PlanSession` via pydantic smart-union dispatch.
5. **Construct `Layer4Payload`** with mode='single_session_synthesize', pattern='B', phase_structure=None, seam_reviews=None.
6. **Run §5.4 validator** via `validate_layer4_payload(payload, ctx, pass_index)` with `ValidatorContext` bundling 2C (single locale) + 2D + 3A.
7. **On validator failure**, retry up to `capped_retries` (default 2) with `RuleFailure` context merged into the user prompt's "Retry context" section.
8. **On cap-hit with unresolved blockers**, demote blocker → warning per §5.5; append a new accepted ValidatorResult so the Layer4Payload invariant holds; emit `Observation(category='best_effort_plan', elevates_to_hitl=True)`.
9. **On schema-violation** (tool args parse failure), one schema-only retry per §5.5 (doesn't consume per-call budget); on second failure raises `Layer4OutputError('schema_violation')`.
10. **Emit `Observation(category='intensity_modulated', elevates_to_hitl=False)`** per §8.7 when the synthesizer emitted the matching session coaching_flag.

---

## 5. Next session pointers — Step 4b/c T1+T2 refresh integration

**Architect-recommended next per `CLAUDE.md` "Next forward move":**

### Step 4b/c scope: `llm_layer4_plan_refresh` T1+T2 (D-64 caller; Pattern B; 3-4 files projected; ~40-60 tests)

New code (likely `layer4/plan_refresh.py` or split into `layer4/plan_refresh_t1.py` + `layer4/plan_refresh_t2.py`) with:
- Claude API client integration (reuse `_default_llm_caller` pattern from `single_session.py`)
- `record_refresh_sessions` tool-use schema (full payload-mirror per Step 4a precedent) — emits `list[PlanSession]` (T1: ≤4 sessions; T2: ≤14 sessions per §7.12 max-2-per-day × 7 days)
- Input validation per `Layer4_Spec.md` §4.3 (precondition checks: `tier_scope_mismatch`, `prior_plan_window_empty`, `plan_version_id_parent_missing`, `parsed_intent_schema_invalid`)
- Layer4Payload construction with `mode='plan_refresh'`, `pattern='B'`, `phase_structure=None`, `seam_reviews=None`
- `ValidatorContext` construction (T1: 3A + 2A + 2D + 1; T2: adds 3B + 2B/2C/2E)
- Validator harness invocation — at T2 scope the weekly-aggregate rules (`volume_band_*` + `intensity_dist_*`) fire load-bearing on the 7-day window
- 2-retry cap per §5.5 with `RuleFailure` context fed back into the retry prompt
- `prior_plan_session_window` rendering hybrid per D4 of the prompt bodies (refresh-window-prior as summary table; refresh-window-after verbatim — the load-bearing hand-off target)
- Observation emission for `intensity_modulated` per §8.7 (broadened to T1/T2 per the 2026-05-17 §8.6/§8.7 amendment)

Plus `tests/test_layer4_plan_refresh.py` (~40-60 tests — T1 happy path × 3 + T2 happy path × 3 + validator-retry × 4 + cap-hit × 2 + each §4.3 precondition × 1 + intensity_modulated emission × 2).

**Stop-and-ask risk:** Low. The contract surface is closed; the call site reuses Step 4a's tool-use plumbing + validator + retry shapes. Risk surfaces if T1's prior-plan-window rendering surfaces a shape gap the prompt body assumes but the implementation can't materialize (e.g., per-session completion-status data Layer 3A doesn't actually emit) — but that's a runtime data-quality concern, not a spec amendment.

### Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (Step 4a).
3. **Third re-read**: `Layer4_Spec.md` §3.2 (plan_refresh function signature) + §4.3 (input validation preconditions) + §5.1 (pattern routing — T1/T2 → B always; T3 → B intra-phase, A cross-phase) + §5.3 (Pattern B algorithm) + §5.5 (capped retry) + §8.6 (intensity_modulated trigger broadened to T1/T2) + §8.7 (call-level observations) + §9.1 (plan_refresh_key cache formula).
4. **Fourth re-read**: `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` + `Layer4_RefreshT2_v1.md` (prompt bodies) + `layer4/single_session.py` (Step 4a reference implementation) + `layer4/payload.py` + `layer4/context.py` + `layer4/validator.py`.
5. **Branch**: cut a fresh branch off post-merge main; or stay on a harness pin per precedent.
6. **Test convention**: top-level `tests/test_layer4_plan_refresh.py` alongside the existing `test_layer4_*` tests.
7. **Reuse pattern**: copy `_default_llm_caller` + `LLMCaller` type alias + tool-use invocation pattern from `layer4/single_session.py`; consider extracting to a shared `layer4/_llm.py` helper if the duplication is load-bearing.
8. **Stop-and-ask trigger #5**: if the LLM tool-use output for T1/T2 surfaces a contract gap that requires loosening `Layer4Payload`'s `extra='forbid'` or other invariants, route through `/plan` mode.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Step 4a single-session integration (architect-recommended) | Andy 2026-05-17 | Picked from the 4-option scope question; Step 4a was queued next per CLAUDE.md "Next forward move" + the PR-E §5 forward-pointer. |
| 2 | Tool-schema fidelity = full `PlanSession` payload-contract mirror (Option 2) | Andy 2026-05-17 | Picked from a 3-option `AskUserQuestion`; Andy chose maximal fidelity over LLM-compliance-burden minimization. Tool schema is what the orchestrator pins; payload contract is canonical. v1 sketch had reconciliation gaps the post-process layer would have had to fill arbitrarily. |
| 3 | Bookkeeping bundle = 8 files | Andy 2026-05-17 | Andy explicit at session start; precedent from PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6. |
| 4 | `Layer1Payload` as opaque `dict[str, Any]` | Architect-pick | PR-D precedent for unmapped upstream shapes; Layer 1 typed schema out of v1 scope. Caller passes any dict; template renders keys conditionally. |
| 5 | `_default_llm_caller` dependency-injectable via `LLMCaller` type alias | Architect-pick | Tests cannot make real API calls; clean DI pattern; production callers leave `llm_caller=None` and `ANTHROPIC_API_KEY` loaded from env. |
| 6 | `plan_version_id=0` v1 sentinel for D-63 ad-hoc outputs | Architect-pick | Spec §3.3 calls for None but `Layer4Payload.plan_version_id` typed `int` non-None at the payload contract level; v1 uses 0 as the sentinel; orchestrator can override; v2 may loosen the payload contract. |
| 7 | `sport_not_in_inclusion` §4.4 row 6 NOT defensively checked | Architect-pick; spec-aligned | No `layer2a_payload` in §3.3 signature; caller pre-checks per D-63 §6.3; documented inline as v1 limitation. |
| 8 | Best-effort fallback synthesizes a final accepted ValidatorResult with demoted warnings | Architect-pick; spec-aligned | Required by `Layer4Payload._check_validator_results` (validator_results[-1].accepted=True); demotes blockers → warnings per §5.5; pairs with `best_effort_plan` Observation emission. |
| 9 | Schema-violation special case: one schema-only retry that doesn't consume per-call budget | Architect-pick; spec-aligned | Per §5.5 "Schema-violation special case: When the synthesizer returns malformed structured output (per output parser): one schema-validation retry (counter does NOT consume the per-phase budget — schema retries are separate); on second failure, raise `Layer4OutputError('schema_violation')` and bail out of the call." |
| 10 | `_render_user_prompt()` inline Python rendering instead of Mustache | Architect-pick | Mustache library would be a new dependency; the prompt template's conditional blocks are simple enough to render with Python `if/else` + f-strings; rendered output matches the Mustache template's intent. |
| 11 | `Layer4_SingleSession_v1.md` → `_v2.md` per Rule #12 | Architect-pick; precedent | Rule #12 numeric versioning convention; v1 retained as in-project history. |
| 12 | v2 amendment scope = §4.1 tool schema + D13 row only | Architect-pick | Coaching policy unchanged; §§1–3 + §§5–14 carry over verbatim. Smaller blast radius. |

### 6.2 Stop-and-ask trigger retrospective

- **Trigger #8** fired and routed properly via two `AskUserQuestion` rounds — tool-schema fidelity (Andy picked Option 2) + file-count budget (Andy bundled 8 files).
- **Trigger #2** fired indirectly via the Option 2 pick; the v2 amendment is scoped to §4.1 + D13 only; no coaching-policy / §5 system prompt / §6 user prompt changes. Per the PR-A directive (amendment-authoring goes through `/plan` mode), the two-round `AskUserQuestion` flow exercised the gate before edits applied.
- **Trigger #5** did NOT fire — `Layer4_Spec.md` untouched; the v2 prompt body amendment is implementation-of-spec, not contract change.
- **Trigger #11** did NOT fire — no new D-rows; existing D-66/D-67/D-68/D-70/D-71 cover all forward-pointer cases.
- Other triggers — none applicable.

### 6.3 Carried forward to Step 4b/c plan_refresh integration

- **`_default_llm_caller` + `LLMCaller` type alias**: copy or extract to shared `layer4/_llm.py` helper; T1/T2 reuse the Anthropic SDK invocation pattern.
- **Tool-schema = full payload-contract mirror precedent**: T1/T2 `record_refresh_sessions` tool emits `list[PlanSession]`; each session matches the full PlanSession contract. 9-shape IntensityTarget `oneOf` reused.
- **Retry loop + best-effort fallback shape**: reusable across all Pattern B entry points.
- **Schema-violation special case handling**: reusable.

### 6.4 Carried forward to D-66 / D-67 / D-70 / D-71 design waves

- **D-66 design wave** — race-event data model. Step 4e race-week-brief depends on this.
- **D-67 design wave** — per-date athlete restrictions. Validator harness D-67-aware branches activate when restrictions are populated.
- **D-68 design wave** — default equipment profiles per locale category.
- **D-70 design wave** — ROM modality.
- **D-71 design wave** — phase-sequencing for tendinopathy progression.

### 6.5 Carried forward to Layer 1 typed payload (deferred)

- **`Layer1Payload`** is currently `dict[str, Any]` opaque pass-through. Lands as a typed pydantic model when the Layer 1 implementation arc begins (currently "In progress — D-51 field inventory pending" per CLAUDE.md). At that point the §3.3 signature can tighten to `layer1_payload: Layer1Payload` and the `_render_user_prompt()` template can drop the `.get(...)` defensive reads.

---

## 7. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/single_session.py` exists with `SingleSessionRequest` + `build_record_single_session_tool` + `llm_layer4_single_session_synthesize` + `Layer4OutputError` raised on schema_violation + all driver helpers | ✅ inspection |
| 9-shape `IntensityTarget` `oneOf` union in tool schema | ✅ `test_intensity_target_oneof_nine_shapes` passes |
| Required top-level session fields cover payload invariants | ✅ `test_session_required_fields_cover_payload_invariants` passes |
| `coaching_flags` closed enum [intensity_modulated, technique_emphasis, discipline_specific_intensity] | ✅ `test_coaching_flags_closed_set` passes |
| `SingleSessionRequest` locale XOR quick_equipment enforced at construction | ✅ test_both_locale_and_quick_rejected + test_neither_locale_nor_quick_rejected pass |
| §4.4 preconditions raise `Layer4InputError` on missing 2D + missing 3A + locale-without-2C + locale-mismatch | ✅ 4 TestInputValidation tests pass |
| Entry-point happy path produces Layer4Payload with mode='single_session_synthesize' + pattern='B' + sessions[0].is_ad_hoc=True + phase_structure=None + seam_reviews=None + suggestion_id populated | ✅ TestEntryPointHappyPath × 8 + TestLayer4PayloadComposition × 9 pass |
| Validator retry: fail then pass retries once | ✅ test_validator_fail_then_pass_retries_once passes |
| Validator cap-hit emits best_effort_plan Observation + demotes blockers to warnings | ✅ test_cap_hit_emits_best_effort_observation passes |
| Schema-violation: one schema-only retry doesn't consume budget; second failure raises | ✅ test_malformed_then_valid_recovers + test_malformed_session_retries_then_raises pass |
| intensity_modulated flag → Observation emitted; no flag → no Observation | ✅ TestObservationEmission × 2 pass |
| `layer4/errors.py` exists with Layer4Error base + Layer4InputError + Layer4OutputError | ✅ inspection |
| `layer4/__init__.py` re-exports 6 new symbols alongside existing 32 payload + 9 hashing + 55 context + 2 validator | ✅ grep `__all__` |
| `tests/test_layer4_single_session.py` 49 tests, all green | ✅ `python -m pytest tests/test_layer4_single_session.py` |
| Combined `tests/` (payload + hashing + context + validator + single_session) = 354 tests, all green | ✅ `python -m pytest tests/` 0.64s |
| No regression in PR-A + PR-B + PR-C-followon + PR-D + PR-E work | ✅ same 305 prior tests + 49 new = 354 |
| `Layer4_SingleSession_v2.md` exists; v1 retained as in-project history | ✅ `ls aidstation-sources/prompts/` |
| `Project_Backlog_v45.md` exists; file-revision-header is v45; v44 demoted inline | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v45.md` | ✅ grep |
| `CLAUDE.md` Layer 4 row mentions "SPEC + IMPLEMENTATION Step 4a of 8 COMPLETE" | ✅ grep |
| `CLAUDE.md` Last-shipped is Step 4a; PR-E demoted to first Predecessor | ✅ inspection |
| `CLAUDE.md` Next-forward-move recommends Step 4b/c (T1+T2 refresh) | ✅ inspection |
| Working tree shows 8 files modified / created | ✅ `git status` |
| Branch is `claude/implement-v5-validator-WelCn` (harness-pinned) | ✅ |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; Step 4a is implementation-layer (no UI surface; no new §5.0 row needed).
- Step 4b/c `llm_layer4_plan_refresh` T1+T2 — queued next session against the now-complete payload + context + validator + Step 4a reference implementation surfaces.
- Step 4d/e/f (T3 refresh + race-week-brief + plan_create) — queued after Step 4b/c.
- Step 5–8 (cache layer, Pattern A orchestration, live LLM integration, T3/auto-fire picks) — queued post-Step-4.
- v5 onboarding implementation PR — independent of Layer 4 implementation track; can run in parallel.
- D-50 wiring resumption — now unblocked by D-58; can run in parallel.

---

**End of handoff.**
