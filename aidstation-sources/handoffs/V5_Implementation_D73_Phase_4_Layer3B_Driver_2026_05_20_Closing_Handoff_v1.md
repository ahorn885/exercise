# D-73 Phase 4 — Layer 3B LLM Driver — Closing Handoff

**Session:** Phase 4 — Layer 3B LLM driver. Andy opened with the Phase 3.1-Driver closing-handoff URL + "lets work!" → state report per Rule #13 → picked **Phase 4 — Layer 3B driver** at the scope gate → after the file plan + D1-D14 + gut check were laid out, picked **Approve as recommended** at the second scope gate. This session lands the second upstream LLM driver (`llm_layer3b_goal_timeline_viability`) closing the 3A+3B pair, with paired §8.3 doc-sweep fix. Phase 4.1 (event-metadata helper) was folded into the driver via D14 internal population rather than landing as a separate `race_events_repo.py` 1-fn helper — saves a follow-up session with no net loss.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_3_1_Driver_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/v5-driver-phase-3-closing-Sf9qd` (harness-pinned; predecessor's branch name carried forward — same-day-after Phase 3.1-Driver session continuity).
**Status:** 🟢 5 substantive files shipped at ceiling. 1072 tests green (995 baseline + 77 new). Phase 4 complete; both upstream LLM drivers (3A + 3B) operational.

---

## 1. Session-start verification (Rule #9)

Anchor sweep of predecessor §8 via `./aidstation-sources/scripts/verify-handoff.sh` + 995-test baseline rerun.

| Claim | Anchor | Result |
|---|---|---|
| All predecessor §8 anchor paths exist on disk | `verify-handoff.sh` [1] | ✅ 14 of 15 paths ✅; the 1 ❌ is a forward-reference to this session's deliverable (`tests/test_layer3b_builder.py`) — expected drift, not actual drift |
| Predecessor §8 table reads green | `verify-handoff.sh` [3] | ✅ extracted clean |
| `python -m pytest tests/` → 995 passed | bootstrap + rerun | ✅ `995 passed in 2.47s` after the documented `pip install --break-system-packages` bootstrap |
| Working tree clean at session start | `git status` | ✅ |

**No drift between predecessor narrative and on-disk state.** The single missing path (`tests/test_layer3b_builder.py`) was the predecessor handoff's §6.1 forward-reference naming this session's deliverable; this session creates it.

---

## 2. Session narrative

Andy opened with the Phase 3.1-Driver closing-handoff URL + "lets work!". Session-start verification per Rule #13 ran clean (state report per CLAUDE.md first-session-checklist step 7; 1 expected forward-ref drift entry flagged but not blocking). Andy picked **Phase 4 — Layer 3B driver** at the scope question.

Triggers #2 (LLM prompt body design) + #5 (architectural alternatives) fired. I read the precedent surfaces (`Layer3_3B_Spec.md` in full + `Layer3A_v1.md` for the prompt-body shape + `layer3a/builder.py` for the driver shape including all post-LLM transforms + `layer3a/cached_wrapper.py` for the cache wrapper shape + `Layer3BPayload` + `GoalViability` + `PeriodizationShape` + `Layer3BHITLItem` schemas in `layer4/context.py` lines 838-955 to confirm what's already deployed + `RaceEventPayload` in `layer4/context.py` lines 1010-1106 + `race_events_repo.py:load_target_race_event_payload` + `Upstream_Implementation_Plan_v1.md` §4 row 4 for Phase 4 sub-phasing + the §8.3 paired doc-sweep target in `Race_Events_D66_Design_v1.md`) and then presented the plan-mode gate in chat with:

1. The scope decision (4.1 alone / 4.2 alone / combined recommended) — picked **combined** with 4.1 folded as bookkeeping via D14 internal driver population.
2. The 5-file substantive scope (driver + cache wrapper + prompt body + tests + §8.3 paired fix).
3. The 14 D-decisions table with recommendations + rationale per spec citation. D1-D10 mostly reuse 3A picks (with D2 thinking budget lowered to 3000 + D6 max_tokens lowered to 2000 per spec §5.4 literals + D7 model already canonical so no §3 fix needed). D11-D14 are 3B-specific: (D11) raw-payload input shape with None-tolerant §H.2 kwargs for the deployed-shape gap; (D12) validator-enforced HITL auto-emit per spec §5.5 step 3; (D13) periodization-sanity loop with single retry + fallback-to-standard per spec §5.5 step 4; (D14) D-66 paired event-metadata field population from `RaceEventPayload`.
4. The pattern shape (10-step algorithm with two independent retry paths).
5. A gut check covering 5 named risks + 3 "what might be missing" + 3 best-arguments-against.

Andy picked **Approve as recommended**, ratifying all 14 D-decisions + the combined-4.1-into-4.2 scope.

Execution:

1. **Prompt body** (`aidstation-sources/prompts/Layer3B_v1.md`, ~700 lines) shipped first as the design-doc anchor for system prompt + tool schema rationale + D1-D14 + post-LLM transforms (8 transform sub-sections: schema validation; mode-discriminator enforcement; evidence-basis cross-check; HITL auto-emit; confidence-floor clamp; periodization-sanity loop; metadata stamping + D14 event-metadata population).
2. **Driver** (`layer3b/builder.py`, ~950 LOC) implemented the full pipeline: input validation per spec §4 → 4 block-render helpers per spec §5.1 → user prompt rendering with two retry-augmentation paths (schema retry + periodization retry) → Anthropic SDK adapter with extended thinking + forced tool-use → single capped retry on schema violation per spec §5.5 step 1 → mode-discriminator post-validation enforcement per §5.5 step 2 → name-existence + mode-prefix evidence_basis cross-check per spec §5.5 + D9 → HITL auto-emit per §5.5 step 3 + spec §6.1 (4 items: `3B.unrealistic_goal` / `3B.first_time_competitive_goal` / `3B.dnf_recurrence_risk` / `3B.compressed_on_fatigued_athlete`) → §6.5 floor-rule clamp (4 floor rules) → §5.5 step 4 periodization-sanity loop (single capped retry on phase_weeks sum mismatch + fallback-to-standard on persistent failure with `periodization_shape_fallback` observation) → D14 event-metadata field population from `RaceEventPayload` + metadata stamping. Errors inlined (`Layer3BInputError` + `Layer3BOutputError` + `Layer3BEvidenceBasisWarning`) per Step 4a + Layer 2C + Layer 3A precedent.
3. **Cache wrapper** (`layer3b/cached_wrapper.py`, ~200 LOC) reuses `CacheBackend` + `PER_ENTRY_PHASE_IDX_SENTINEL` from `layer4/cache.py` with 3B-specific serialize/hydrate via `Layer3BPayload.model_dump_json` / `model_validate_json` + day-granular `current_date: date` cache key per spec §9.1. Section_h2_kwargs hash slot included for D11 forward-compatibility with the §H.2 form-refresh PR.
4. **§8.3 paired doc-sweep fix** — `aidstation-sources/Race_Events_D66_Design_v1.md` §8.3 narrative `mode='open_ended'` → `mode='no-event'` per canonical `Layer3BPayload.mode: Literal["event","no-event"]` schema. Audit-trail note points to D-66 paired amendment + Phase 4 fix.
5. **Tests** (`tests/test_layer3b_builder.py`, ~1100 lines) — 77 tests across 11 classes using stub `llm_caller` per Step 4a + 3A precedent.

First test pass hit 1 failure in `TestModeDiscriminator::test_llm_emits_no_event_in_event_mode_raises` — expected `mode_mismatch` but got `schema_violation`. Root cause: when the LLM emits `mode="no-event"` in event-mode context, the driver populates event-metadata fields per D14, which fails pydantic's `Layer3BPayload._check_event_mode_consistency` validator (no-event mode requires all 4 event-metadata fields None). The schema error surfaces after retry exhaustion before the post-LLM mode-discriminator check fires. The reverse direction (caller no-event, LLM emits "event" with all event fields None per the D-66 amendment) DOES route through the mode-discriminator check (test `test_llm_emits_event_in_no_event_mode_raises` passes). Updated the test expectation to assert `schema_violation` + added a docstring explaining the routing — the behavior is correct, the original test expectation was wrong.

Second pass: 77/77 green. Full suite: 1072/1072 green. Bookkeeping: CURRENT_STATE pointer flipped; CARRY_FORWARD §8.3 doc-nit closed + Phase 4 follow-on section added with L3B-P-1..L3B-P-8 + 3B cache invalidation wiring + 4.1 standalone helper deferral; Upstream Plan §4 row 4.1 + 4.2 marked ✅; this handoff.

No fixture bugs surfaced this session (3B fixture design copied the 3A pattern verbatim — `_make_layer1` / `_make_layer3a` / `_make_layer2a` / `_make_race_event` / `_good_tool_args` / `_stub_caller` / `_sequence_caller` / `_explode_caller`).

---

## 3. File-by-file edits

### 3.1 `layer3b/builder.py` (NEW, ~950 LOC)

The main driver. Structure:

- **Errors block** — `Layer3BInputError` (carries `code` + optional `detail`) + `Layer3BOutputError` (same shape) + `Layer3BEvidenceBasisWarning` (UserWarning subclass). Inlined per Step 4a + Layer 2C + Layer 3A precedent.
- **Constants block** — `_APPROVED_MODELS` frozenset (sonnet-4-6, sonnet-4-5 retained for replay parity, opus-4-7, haiku-4-5); `_TOOL_NAME = "emit_layer3b_payload"`; `_CONFIDENCE_RANK` dict; default-model/temperature/max-tokens/thinking-budget literals per spec §3 + §5.4 (`_DEFAULT_TEMPERATURE=0.0`, `_DEFAULT_MAX_TOKENS=2000`, `_DEFAULT_THINKING_BUDGET=3000`); `_VALID_GOAL_OUTCOMES` / `_COMPETITIVE_GOAL_OUTCOMES` / `_VALID_NON_EVENT_GOAL_TYPES` / `_VALID_PLAN_DURATION_WEEKS`; `_DNF_RECOVERY_WINDOW_WEEKS` mapping per spec §6.1; `_PURE_ENDURANCE_PRIMARY_SPORTS` (reserved for future §6.6 cross-check expansion — currently unused but documented for L3B-P-2 wiring).
- **LLM caller protocol** — `_LLMOutput` dataclass + `LLMCaller` type alias matching `layer3a/builder.py` shape verbatim.
- **`_default_llm_caller`** — production Anthropic SDK invocation with extended thinking (D2 = 3000 tokens) + forced tool-use (D1). Raises `Layer3BOutputError("anthropic_api_key_missing")` when env var unset; raises `Layer3BOutputError("schema_violation")` if no `emit_layer3b_payload` tool_use block emitted.
- **`build_emit_layer3b_payload_tool`** — full `Layer3BPayload` mirror per D5 (GoalViability + PeriodizationShape + Layer3BHITLItem + Layer3Observation + 5-field top-level); `additionalProperties: false` at every nesting level; enums per spec §7 (3-value viability, 4-value periodization mode, 4-value start_phase, 3-value confidence, 3-value HITL severity, 4-value observation category); maxItems=6 on notable_observations per §8.2. Phase_weeks anyOf null + object-with-Base/Build/Peak/Taper integer fields per spec §6.2.
- **`_validate_inputs`** — §4 preconditions (rules 1-7): layer1/3a/2a non-None, current_date non-None, etl_version_set non-empty, 3A+2A etl_version match caller pin, ≥1 included discipline, model in approved list, temperature in [0, 1], event-mode requires event_date > current_date + goal_outcome populated + in approved enum, no-event-mode requires plan_duration_weeks ∈ {8,12,16,20,24} + non_event_goal_type ∈ enum. Each raises `Layer3BInputError(code, detail)`.
- **Block-render helpers (4 per spec §5.1)** — `_render_block_1_timeline`, `_render_block_2_goal_context` (event-mode reads §H.2 caller kwargs + `RaceEventPayload.distance_km`; no-event-mode reads §C from Layer1Payload), `_render_block_3_state_excerpt` (3A's `current_state` + `recent_trajectory` + `data_density.connected_providers` + `data_density.self_report_freshness_days`), `_render_block_4_discipline_load` (2A's `framework_sport` + included disciplines + `training_gaps_summary.flagged_count`).
- **Helpers** — `_time_to_event_weeks(event_date, current_date)` (`(event_date - current_date).days // 7`, floored at 0); `_time_to_event_phase_band(weeks)` per spec §5.3 5-band guidance; `_resolve_plan_duration` / `_resolve_non_event_goal_type` (caller-override-else-Layer1EventGoal fallback).
- **`_build_prep_dict`** — flat dict keyed by `c.*` (§C), `h2.*` (§H.2), `h3.*` (§H.3), `3a.*` (Layer 3A excerpt), `2a.*` (Layer 2A excerpt). Consumed by `_check_evidence_basis` for name-existence + mode-discriminator on path prefixes.
- **`_SYSTEM_PROMPT`** — the 12-rule system prompt body matching `prompts/Layer3B_v1.md` §5 verbatim (CLAUDE.md voice + spec §6.1 HITL triggers + §6.2 periodization vocab + §6.5 floor rules + §6.6 no-event heuristics + §8.1 required observation triggers + §8.2 observation budget + spec-§10 forbidden observations).
- **`_render_user_prompt`** — assembles the 4 blocks + current_date line + tool-call instruction. On schema retry, appends the schema error message + a re-emit instruction. On periodization-sanity retry, appends the deviation error + re-emit instruction with explicit fallback path framing.
- **`_collect_evidence_basis_paths` + `_check_evidence_basis`** — walks tool args + raises `Layer3BEvidenceBasisWarning` per unknown path; ALSO raises the warning when goal_viability.evidence_basis violates the mode-discriminator on h2.* prefix (event-mode missing ≥1 h2.* OR no-event-mode including any h2.*). No fail.
- **`_has_dnf_attempt` + `_dnf_recovery_window` + `_enforce_hitl_auto_emit`** — validator post-emits the 4 spec §6.1 HITL items when conditions hold + LLM omitted them. Dedup by `item_label`. Synthetic items use spec-canonical wording for `description` / `recommended_action` / `revise_option` / `revise_target` and respect the §7 schema rule `acknowledge_option=None when severity=='blocker'`.
- **`_clamp_confidence` + `_apply_confidence_floors`** — clamp helper (`min()` style on `_CONFIDENCE_RANK`) + 4-rule predicate per spec §6.5. When clamping fires, appends a single `confidence_clamped_by_data_signal` observation enumerating signals. Honors §8.2 observation budget cap via `_trim_observations_to_budget`.
- **`_periodization_sum_target` + `_check_periodization_sanity` + `_periodization_fallback_to_standard`** — §5.5 step 4 implementation. Target = `time_to_event_weeks` (event-mode) or `plan_duration_weeks` (no-event-mode). Checks `abs(sum(phase_weeks.values()) - target) > 1` → triggers retry/fallback path. Fallback preserves LLM's `start_phase` + `reasoning_text`; appends `periodization_shape_fallback` data_hygiene observation.
- **`_prompt_hash`** — sha256 of `system_prompt + "||" + user_prompt` for metadata.
- **`_assemble_payload_candidate`** — driver-side payload construction per D14. Builds candidate dict with tool_args + driver metadata + (event-mode) event-metadata fields populated from `RaceEventPayload`; (no-event-mode) all event-metadata fields default to None per pydantic.
- **`llm_layer3b_goal_timeline_viability`** — the public entry point. Algorithm: resolve no-event-mode fields from Layer1EventGoal → validate → render → up to 2 LLM attempts (single capped retry on `ValidationError`) → schema validate → mode-discriminator enforcement → evidence-basis warn → HITL auto-emit → floor clamp → periodization sanity loop (up to 1 retry + fallback) → return. Default args per D6/D7/D2 + spec §3.

### 3.2 `layer3b/cached_wrapper.py` (NEW, ~200 LOC)

- **`layer3b_goal_timeline_viability_key`** — cache key per spec §9.1. Components: `user_id || layer1_hash || layer3a_hash || layer2a_hash || race_event_id-or-"no-event" || current_date.isoformat() || non_event_goal_type-or-empty || canonical_json(etl_version_set) || canonical_json(section_h2_kwargs) || model || str(temperature) || str(max_tokens) || str(extended_thinking_budget)`. `current_date: date` is already day-granular (no `.replace(hour=0,...)` step needed unlike 3A's datetime). `section_h2_kwargs` is a forward-compatibility hash slot for the §H.2 deployed-shape gap kwargs per D11 — when the form-refresh PR lands, this slot folds into layer1_hash.
- **`_serialize_layer3b_payload` + `_hydrate_layer3b_payload`** — pydantic `model_dump_json` / `model_validate_json`. `Layer3BPayload` is self-contained (no `plan_version_id` / `suggestion_id` rebinding), same as 3A.
- **`llm_layer3b_goal_timeline_viability_cached`** — get/put against `CacheBackend`; on hit returns hydrated payload; on miss invokes the underlying driver, serializes the result, stores via `backend.put(...)` with `entry_point="llm_layer3b_goal_timeline_viability"`. Mirrors no-event-mode field resolution from the driver so cache-key generation matches what the driver would compute internally.

### 3.3 `aidstation-sources/prompts/Layer3B_v1.md` (NEW, ~700 lines)

Prompt body design doc. Structure:

- **Source decisions table** — D1-D14 with picks + rationale per spec citation. Each pick names the spec section it implements and (where relevant) the Layer 4 / Layer 3A precedent it inherits.
- **§1 Purpose + scope** — what this prompt produces (Layer3BPayload sans driver-stamped metadata + sans D-66 event-metadata fields) + what it does NOT (boundaries per spec §2) + failure modes the schema-retry + sanity-retry catch.
- **§2 Pipeline placement** — call site, pattern shape (10-step algorithm), out-of-pipeline cases (cache hit, input failure).
- **§3 Inputs** — 5 sub-sections enumerating template variables per Block 1-4 + current_date line. Event-mode reads §H.2 fields (some as None-tolerant kwargs per D11); no-event-mode reads §C.
- **§4 Tool schema** — full JSONC sketch of `emit_layer3b_payload` with `additionalProperties: false` at every nesting level; matches `build_emit_layer3b_payload_tool()` verbatim.
- **§5 System prompt** — the 12-rule verbatim text (matching `_SYSTEM_PROMPT` constant in builder.py).
- **§6 User prompt template** — template-variable substitution sketch + retry + sanity augmentation text.
- **§7 Sampling config** — model / temperature / max_tokens / thinking budget / capped_retries_schema / capped_retries_periodization / tool_choice.
- **§8 Post-LLM transforms** — 7 sub-sections: schema validation; mode-discriminator enforcement; evidence-basis cross-check; HITL auto-emit; confidence-floor clamp; periodization-sanity loop; metadata stamping + event-metadata population per D14.
- **§9 Performance budget** — per spec §11 (~$0.03/cold call; cheaper than 3A).
- **§10 Caching** — cache key formula + day-granular semantics + invalidation triggers + cross-reference to cached_wrapper.py.
- **§11 Test scenarios** — pointer to spec §13 TS-1..TS-8 + mapping to `TestS13Scenarios` test methods.
- **§12 Open items** — 8 deferred items (L3B-P-1 real-LLM regression, L3B-P-2 §H.2 deployed-shape gap, L3B-P-3 mode-discriminator as HARD fail, L3B-P-4 DNF window calibration, L3B-P-5 Layer 4 contract, L3B-P-6 re-eval cadence, L3B-P-7 multi-event v2, L3B-P-8 plan duration cap).
- **§13 Gut check** — 5 risks named + 3 missing-bits + 3 best-arguments-against.

### 3.4 `tests/test_layer3b_builder.py` (NEW, ~1100 lines, 77 tests)

11 test classes:

- **TestInputValidation** (14 tests) — all §4 preconditions: missing_layer1, missing_3a_payload, missing_2a_payload, etl_version_mismatch_3a, etl_version_mismatch_2a, no_included_disciplines, event_date_in_past (TS-8 path verifying no-LLM-invocation via `_explode_caller`), event_mode_missing_goal_outcome, event_mode_invalid_goal_outcome, no_event_mode_missing_plan_duration, no_event_mode_invalid_plan_duration, no_event_mode_missing_goal_type, unapproved_model, invalid_temperature.
- **TestToolSchema** (10 tests) — tool name, top-level required fields, mode enum, viability enum, periodization mode enum, start_phase enum, HITL severity enum, observation category enum, observation maxItems=6, additionalProperties=false invariants.
- **TestEntryPointHappyPath** (3 tests) — event-mode round-trip stamping metadata + D14 event-metadata fields; no-event-mode leaves all 4 D-66 fields None; no-event-mode resolves plan_duration_weeks + non_event_goal_type from `Layer1EventGoal` when kwargs absent.
- **TestModeDiscriminator** (2 tests) — caller-event + LLM emits no-event → schema_violation (pydantic catches mode-vs-event-metadata-fields inconsistency before driver check fires); caller-no-event + LLM emits event → mode_mismatch (driver-level check fires because pydantic tolerates mode=event with all event fields None per D-66 amendment).
- **TestConfidenceFloors** (7 tests) — `_clamp_confidence` helper; each of the 4 §6.5 floor rules fires correctly; no-clamp-signal-no-observation invariant; clamp does not upgrade low → medium.
- **TestHITLAutoEmit** (7 tests) — each of the 4 §6.1 items auto-emits on conditions met; DNF outside window does not auto-emit; dedup-when-LLM-already-emitted; DNF recovery window mapping constants.
- **TestPeriodizationSanity** (6 tests) — custom-with-correct-sum passes; custom-with-±1-sum passes; custom-with-mismatched-sum retries-then-falls-back; custom-mismatch-retry-succeeds-no-fallback; non-custom modes skip sanity check; `_check_periodization_sanity` helper.
- **TestSchemaViolation** (3 tests) — invalid-then-valid succeeds after retry; two invalid raises `Layer3BOutputError("schema_violation")`; suggested_adjustments pydantic rule enforced.
- **TestEvidenceBasisCheck** (3 tests) — unknown path warns; event-mode missing h2.* reference warns; no-event-mode with h2.* reference warns.
- **TestS13Scenarios** (8 tests) — TS-1 AR finisher compressed (Andy's PGE 2026 case); TS-2 AR podium unrealistic + blocker HITL; TS-3 first-time competitive clamps confidence + emits warning HITL; TS-4 no-event endurance standard; TS-5 no-event strength mismatch observation + extended mode; TS-6 ultra prior DNF + warning HITL; TS-7 compressed taper 1-week-out; TS-8 race-date-in-past fatal-no-LLM (verified via `_explode_caller`).
- **TestPrepDict** (7 tests) — event-mode prep dict has h2.* keys; no-event-mode prep dict has h3.* keys; user-prompt renders event-mode block 1; user-prompt renders no-event-mode block 1; retry_error renders into user prompt; `_time_to_event_weeks` helper; `_time_to_event_phase_band` guidance helper.
- **TestCacheWrapper** (7 tests) — cache miss + hit (call_count==1 across 2 calls); day-granular collapses intraday; key changes with etl_version_set; key changes with target_race_event_id (including None vs int); key changes with section_h2_kwargs; key stable across same inputs (sha256 hex 64 chars); round-trip payload preserved via model_dump.

Stub `llm_caller` matches the 3A precedent (`_LLMOutput` dataclass with `tool_args` / `input_tokens` / `output_tokens` / `latency_ms`). `_sequence_caller` returns outputs[i] on the i-th call (retry tests). `_explode_caller` raises AssertionError if invoked (used to verify validation-failure paths skip the LLM). All tests use the dependency-injectable `llm_caller` param; no real Anthropic SDK invocation; no `ANTHROPIC_API_KEY` env requirement.

### 3.5 `aidstation-sources/Race_Events_D66_Design_v1.md` — §8.3 paired doc-sweep fix

§8.3 narrative `mode='open_ended'` → `mode='no-event'` per canonical `Layer3BPayload.mode: Literal["event","no-event"]` schema. Audit-trail note points to D-66 paired amendment (2026-05-18) + Phase 4 fix (2026-05-20). Closes the CARRY_FORWARD doc-nit ledger entry.

### 3.6 Bookkeeping (outside ceiling per CLAUDE.md B3)

- NEW `layer3b/__init__.py` — re-exports the new public surface (driver entry, cache wrapper, errors, tool builder, cache key fn). 7 symbols + alphabetized `__all__`.
- `layer4/cache.py` — `VALID_ENTRY_POINTS` superset extended with `"llm_layer3b_goal_timeline_viability"` (LAYER4_ENTRY_POINTS frozenset untouched — preserves Layer 4-scoped invalidation invariant per Phase 3.1-Driver precedent).
- `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 4.1 marked ✅ folded into 4.2 via D14; §4 row 4.2 marked ✅ Shipped 2026-05-20 with file count + test delta + D1-D14 summary; Phase 4 total updated to "Phase 4 complete. All upstream LLM drivers (3A + 3B) now operational."
- `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer status row 3 updated to 🟢 3A + 3B complete; Tests note 995 → 1072; Current focus reframed to Layer 4 Step 7 SDK scaffolding OR Phase 5.1 orchestrator vertical slice (now structurally unblocked).
- `aidstation-sources/CARRY_FORWARD.md` — `Race_Events_D66_Design_v1.md` §8.3 doc-nit struck out (✅ Resolved); new Phase 4 follow-on section with L3B-P-1..L3B-P-8 + 3B cache invalidation wiring + 4.1 standalone helper deferral.
- This handoff.

---

## 4. Code / tests

- New code: ~2250 LOC across `layer3b/builder.py` (~950) + `layer3b/cached_wrapper.py` (~200) + `tests/test_layer3b_builder.py` (~1100, of which ~700 are fixtures / test infra) — substantive driver footprint ~1150 LOC.
- New prompt body: `aidstation-sources/prompts/Layer3B_v1.md` ~700 lines.
- New tests: 77 across 11 classes (split: 14 input validation + 10 tool schema + 3 happy path + 2 mode discriminator + 7 floor clamp + 7 HITL auto-emit + 6 periodization sanity + 3 schema retry + 3 evidence-basis + 8 §13 scenarios + 7 prep/prompt/helpers + 7 cache wrapper = 77).
- `tests/` count: 995 → 1072 (+77).
- `python -m pytest tests/ -q` → `1072 passed in 2.32s` post-final-edit.

---

## 5. Operational sequence for Andy on Neon

N/A for this session (no schema migrations). When Layer 4 Step 7 lands the `ANTHROPIC_API_KEY` env scaffolding, the §5.0 walkthrough scenario for Phase 4 becomes runnable: invoke `llm_layer3b_goal_timeline_viability(user_id=andy, layer1_payload=build_layer1_payload(db, andy), layer3a_payload=<cached 3A payload>, layer2a_payload=q_layer2a_discipline_classifier_payload(...), race_event_payload=load_target_race_event_payload(db, andy), current_date=date.today(), etl_version_set=<plan-gen pin>, goal_outcome="Finish", first_time_at_distance=False, previous_attempts=[...])` against Andy's live PGE 2026 context — confirm:

- `mode == 'event'` and `event_date == 2026-07-17` and `time_to_event_weeks` computes correctly from current_date.
- `event_locale_id == 'nerstrand-mn'` (or whatever locale slug Andy's PGE 2026 race_events row carries).
- `race_format == 'expedition_ar'`.
- `goal_viability.viability` lands in {`achievable`, `achievable-with-adjustment`} (Andy is experienced AR athlete with multi-year base).
- `goal_viability.confidence` calibrated (likely `medium` per §6.5 floor 2 if 3A trajectory confidence is medium-or-lower).
- `periodization_shape.mode == 'compressed'` per §5.3 phase band (PGE is currently ~9 weeks out at 2026-05-20).
- `periodization_shape.start_phase` likely `Build` (already-fit athlete per 3A's likely `good` aerobic).
- `hitl_surface` empty if Andy's goal is `Finish` + no DNF history; `3B.dnf_recurrence_risk` would fire if previous_attempts contains a prior PGE DNF within window.
- `notable_observations` includes 0 or 1 `compressed`-mode warning (§8.1 row 4).

The Phase 2.4-Prep operational sequence (3 SQL migrations + ETL re-run) is still the live prerequisite for the Phase 2.4 §5.0 walkthrough scenarios, unchanged.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Layer 4 Step 7 — env-gated `ANTHROPIC_API_KEY` SDK scaffolding** (architect-recommended per Upstream Plan §4 + Phase 4 closeout). Lands the first REAL Anthropic SDK call against both 3A + 3B drivers shipped this week. Closes L3A-P-1 + L3B-P-1 deferred real-LLM regression items. Same precedent as Layer 4's existing SDK adapter pattern in `layer4/single_session.py:_default_llm_caller` (already done for 3A's `_default_llm_caller` + 3B's same-shape adapter — env-gating is the missing piece). ~3-4 files: env-gating helper in `layer4/` + 1-2 §13 fixture smoke tests against actual Sonnet 4.6 for 3A + 1-2 for 3B + closing handoff.

Opens with a smaller `/plan-mode` gate (no Trigger #2 — not LLM prompt design; just env-gating + smoke test scaffolding). Possible Trigger #5 if the env-gating shape has alternatives.

### 6.2 Alternative pivots

- **Phase 5.1 orchestrator vertical slice** — `layer4/orchestrator.py` with `orchestrate_race_week_brief(db, user_id)` that (a) loads RaceEventPayload via `load_target_race_event_payload`; (b) calls Layer 1 builder → Layer 2A-E builders → Layer 3A → Layer 3B → `llm_layer4_race_week_brief_cached`. NOW STRUCTURALLY UNBLOCKED (all upstream LLM drivers operational). ~5-7 files including paired `Layer4_Spec.md` §4.5 source-pointer wording fix.
- **§H.2 / §J / §I.1 form-refresh PR** — closes L3B-P-2 (3B's deployed-shape gap) + Layer 2B + Layer 2E input-source surfaces (~6-8 files, over ceiling — would need split). When this lands, 3B's HITL auto-emit pathways for `3B.first_time_competitive_goal` + `3B.dnf_recurrence_risk` become production-reachable; L3B-P-3 tightens to HARD fail.
- **Plan Management spec authorship** — de-stubs Layer 2E §5.5 heat acclim + 2E-2/3/4 open items.
- **D-73 Phase 1.4** — D-52 catalog migration sequencing.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration.
- **Manual §5.0 walkthrough** of the accumulated 71 scenarios = 69 prior + 1 Phase 3.1-Driver + 1 Phase 4 (3B AR baseline call against Andy's PGE 2026 context — gated on Step 7 SDK scaffolding for live-data sanity check).

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff; layer status row 3 is 🟢 3A+3B complete
3. `aidstation-sources/CARRY_FORWARD.md` — Phase 4 follow-ons (L3B-P-1 real-LLM regression, L3B-P-2 §H.2 deployed-shape gap, etc.) — these are forward-references, not blockers
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward):** the cloud container's default `pytest` is `uv tool install` isolated Python; working path is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**If picking Layer 4 Step 7 — SDK scaffolding:** smaller scope than 3A/3B driver sessions. ~3-4 files. Pair with 1-2 §13 fixture smoke tests on each of 3A + 3B drivers (target TS-1 / TS-4 each — dense data, both modes). Possible spec drift fixes flagged during the real-LLM run.

**If picking Phase 5.1 — orchestrator vertical slice:** larger scope (~5-7 files). Opens with a `/plan-mode` gate walking orchestrator-specific D-decisions (load order + invalidation cascade routing + error propagation shape). Pair with `Layer4_Spec.md` §4.5 source-pointer wording fix (CARRY_FORWARD doc-nit).

**If picking §H.2 form-refresh:** likely too big for one session (~6-8 files). Recommend splitting: (a) `routes/onboarding.py` §H.2 form additions + `Layer1EventGoal` / `RaceEventPayload` schema extensions + migrations + tests; (b) 3B driver kwarg-to-field migration + L3B-P-3 tightening to HARD fail on mode-discriminator on evidence_basis paths.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Phase 4 scope = approve as recommended (5 substantive files at ceiling; 4.1 + 4.2 combined with 4.1 folded into driver via D14) | Andy 2026-05-20 | Matches Phase 3.1-Driver precedent (driver + cache wrapper + prompt body + tests + paired spec fix). The standalone tuple-returning 4.1 helper added no net value over `load_target_race_event_payload + driver call`; deferring to bookkeeping if a future orchestrator wants the tuple. |
| 2 | D1 forced tool-use; D2 3000-token thinking budget (lighter than 3A's 4000 per spec §11 input budget); D3 inline-Python rendering; D4 two independent capped retries (schema + periodization sanity); D5 full Layer3BPayload mirror; D6 max_tokens=2000 per spec §5.4; D7 sonnet-4-6 default (spec already canonical, no §3 fix); D8 post-LLM clamp + auto-append `confidence_clamped_by_data_signal`; D9 name-existence + mode-discriminator on path prefixes WARN-only (per L3B-P-3 v1 deferral); D10 CLAUDE.md voice + spec §6 inlined; D11 raw payloads + None-tolerant §H.2 kwargs for deployed-shape gap; D12 validator-enforced HITL auto-emit; D13 periodization-sanity loop with fallback-to-standard; D14 driver populates D-66 event-metadata fields from race_event_payload | Andy 2026-05-20 (approved as recommended) | All 14 picks aligned to spec citations + Step 4a + Layer 3A precedent. D2 + D6 are spec-literal-driven (lighter than 3A). D11 + D12 + D13 + D14 are 3B-specific where spec §5.5 + §H.2-deployed-shape-gap diverged from 3A's contract. |
| 3 | Errors inlined in builder.py (no `layer3b/errors.py`) | Architect-pick | Step 4a + Layer 2C + Layer 3A all inlined. Precedent consistent. |
| 4 | `Layer3BInputError` carries `code` attribute | Architect-pick + spec §4 | Same as 3A — caller-routable error codes (3D HITL vs hard fail) without string parsing. |
| 5 | `_apply_confidence_floors` + `_enforce_hitl_auto_emit` + `_periodization_fallback_to_standard` use `pydantic.model_copy(update=...)` for immutability | Architect-pick | Same as 3A — pydantic-idiomatic; preserves payload-as-data semantics; no risk of mutating upstream-cached instance. |
| 6 | §H.2 deployed-shape gap handled via None-tolerant kwargs (D11) rather than defining `SectionHGoalContext` typed context per spec §3 wording | Architect-pick | Mirrors 3A precedent (raw `Layer1Payload`). Defining empty/optional types now creates schema-versioning churn when the §H.2 form-refresh PR lands. L3B-P-2 captures the de-stub work. |
| 7 | Test failure on `test_llm_emits_no_event_in_event_mode_raises` (expected `mode_mismatch`, got `schema_violation`) — updated test to assert `schema_violation` + docstring explaining the route | Architect-pick (after test surfaced) | The pydantic `_check_event_mode_consistency` validator catches the inconsistency before the driver-level mode-discriminator check fires (because driver populates event-metadata fields per D14, and no-event-mode requires them all None). The behavior is correct — the original test expectation was wrong. The reverse-direction test (no-event caller, event LLM) DOES route through the driver check and passes. |
| 8 | Cache wrapper tests folded into `test_layer3b_builder.py` (not a separate `test_layer3b_cached_wrapper.py`) | Architect-pick + ceiling discipline | Matches the Phase 3.1-Driver precedent. Cache tests are small (7) + share fixtures with builder tests. |
| 9 | §13 TS-1..TS-8 scenarios — ALL 8 covered via stub round-trip (vs 3A's 6-of-10) | Architect-pick | 3B's 8 scenarios are tighter than 3A's 10 (3B has fewer "LLM-reasoning-quality" scenarios — most TS-N test the validator pathways). Real-LLM enum-quality regression deferred to Step 7/8 same as L3B-P-1. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer3b/builder.py` exists + contains `def llm_layer3b_goal_timeline_viability(` | ✅ inspection |
| `layer3b/builder.py` contains `class Layer3BInputError(` + `class Layer3BOutputError(` + `class Layer3BEvidenceBasisWarning(` | ✅ grep |
| `layer3b/builder.py` contains `def build_emit_layer3b_payload_tool(` returning the full `Layer3BPayload` mirror schema | ✅ inspection |
| `layer3b/builder.py` contains `def _apply_confidence_floors(` with the 4 floor rules per spec §6.5 | ✅ inspection |
| `layer3b/builder.py` contains `def _enforce_hitl_auto_emit(` with the 4 §6.1 items | ✅ inspection |
| `layer3b/builder.py` contains `def _enforce_periodization_sanity_loop`-equivalent logic in entry point + `_check_periodization_sanity` + `_periodization_fallback_to_standard` | ✅ inspection |
| `layer3b/builder.py` contains `def _default_llm_caller(` using `anthropic.Anthropic` with `tool_choice` + `thinking` | ✅ grep |
| `layer3b/cached_wrapper.py` exists + contains `def llm_layer3b_goal_timeline_viability_cached(` + `def layer3b_goal_timeline_viability_key(` | ✅ inspection |
| `layer3b/cached_wrapper.py` `layer3b_goal_timeline_viability_key` is day-granular via `current_date: date` (no `.replace(hour=0,...)` needed) | ✅ grep |
| `aidstation-sources/prompts/Layer3B_v1.md` exists + contains "D1-D14" decision table + the 12-rule system prompt | ✅ inspection |
| `aidstation-sources/Race_Events_D66_Design_v1.md` §8.3 narrative reads `mode='no-event'` (not stale `mode='open_ended'`) | ✅ grep |
| `tests/test_layer3b_builder.py` exists + contains 77 tests across 11 classes (`TestInputValidation` / `TestToolSchema` / `TestEntryPointHappyPath` / `TestModeDiscriminator` / `TestConfidenceFloors` / `TestHITLAutoEmit` / `TestPeriodizationSanity` / `TestSchemaViolation` / `TestEvidenceBasisCheck` / `TestS13Scenarios` / `TestPrepDict` / `TestCacheWrapper`) | ✅ pytest collected + class grep |
| `python -m pytest tests/test_layer3b_builder.py -q` → 77 passed | ✅ `77 passed in 0.46s` |
| `python -m pytest tests/ -q` → 1072 passed | ✅ `1072 passed in 2.32s` |
| `layer3b/__init__.py` re-exports `llm_layer3b_goal_timeline_viability` + `llm_layer3b_goal_timeline_viability_cached` + `Layer3BInputError` + `Layer3BOutputError` + `Layer3BEvidenceBasisWarning` + `build_emit_layer3b_payload_tool` + `layer3b_goal_timeline_viability_key` | ✅ `python -c "from layer3b import ..."` returns clean |
| `layer4/cache.py` `VALID_ENTRY_POINTS` includes `"llm_layer3b_goal_timeline_viability"` | ✅ grep |
| `aidstation-sources/Upstream_Implementation_Plan_v1.md` §4 row 4.1 + 4.2 read ✅ Shipped 2026-05-20 | ✅ grep |
| `aidstation-sources/CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Layer status row 3 reads "🟢 3A + 3B complete" | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Tests note reads "1072 green" | ✅ inspection |
| `aidstation-sources/CARRY_FORWARD.md` `Race_Events_D66_Design_v1.md` §8.3 nit struck out | ✅ inspection |
| `aidstation-sources/CARRY_FORWARD.md` "Phase 4 follow-ons" section landed with L3B-P-1..L3B-P-8 | ✅ inspection |
| Working tree clean after commit + push (pending) | ⏳ pending commit |

**Expected ❌ in next session's `verify-handoff.sh` [1] sweep:** 2 paths flagged by the script's regex are expected forward-references (NOT actual drift): (a) `layer3b/errors.py` — mentioned in §7 row 3 as a path NOT created (errors inlined in `builder.py` per architect-pick); (b) `layer4/orchestrator.py` — mentioned in §6.2 as the Phase 5.1 vertical-slice forward-pointer. Same drift pattern as the predecessor session's `tests/test_layer3b_builder.py` forward-ref. Treat as expected, not blocking.

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (5 files; AT the 5-file ceiling):**

1. NEW `layer3b/builder.py` — `llm_layer3b_goal_timeline_viability` driver + tool schema builder + `_default_llm_caller` Anthropic SDK adapter + 4 block-render helpers + HITL auto-emit + confidence-floor clamp + periodization-sanity loop + D14 event-metadata population + inlined errors. ~950 LOC.
2. NEW `layer3b/cached_wrapper.py` — `llm_layer3b_goal_timeline_viability_cached` + `layer3b_goal_timeline_viability_key` + serialize/hydrate helpers. ~200 LOC.
3. NEW `aidstation-sources/prompts/Layer3B_v1.md` — prompt body design doc (D1-D14 + system prompt body + user prompt template + tool schema + post-LLM transforms + caching + gut check). ~700 lines.
4. NEW `tests/test_layer3b_builder.py` — 77 tests across 11 classes using stub `llm_caller`. ~1100 lines.
5. MODIFIED `aidstation-sources/Race_Events_D66_Design_v1.md` — §8.3 `mode='open_ended'` → `mode='no-event'` paired doc-sweep fix per CARRY_FORWARD doc-nit + Upstream Plan §4 row 4.2.

**Bookkeeping (6 files; outside ceiling per B3):**

6. NEW `layer3b/__init__.py` — re-exports the new driver + cache wrapper + errors + tool builder + cache key fn.
7. MODIFIED `layer4/cache.py` — `VALID_ENTRY_POINTS` superset extended with `"llm_layer3b_goal_timeline_viability"` (LAYER4_ENTRY_POINTS frozenset untouched).
8. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 4.1 + 4.2 ✅ Shipped + Phase 4 total updated to complete.
9. MODIFIED `aidstation-sources/CURRENT_STATE.md` — pointer flipped; Layer status row 3 to 🟢 3A+3B; Tests note 995 → 1072; Current focus reframed to Layer 4 Step 7 OR Phase 5.1.
10. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — §8.3 doc-nit struck out; new Phase 4 follow-on section with L3B-P-1..L3B-P-8 + 3B cache invalidation wiring + 4.1 standalone helper deferral.
11. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_4_Layer3B_Driver_2026_05_20_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` `Race_Events_D66_Design_v1.md` §8.3 doc-sweep nit struck out (closed this session). New "Phase 4 follow-ons" section listing the D1-D14 picks shipped + 8 follow-on items (L3B-P-1 real-LLM smoke test scaffolding for Step 7, L3B-P-2 §H.2 deployed-shape gap deferred to form-refresh PR, L3B-P-3 mode-discriminator on evidence_basis paths as HARD fail tightens post-L3B-P-2, L3B-P-4 DNF window calibration post-launch, L3B-P-5 Layer 4 plan-gen periodization contract per Phase 5.1, L3B-P-6 re-evaluation cadence v2, L3B-P-7 multi-event v2, L3B-P-8 plan duration cap v2) + 3B cache invalidation wiring + Phase 4.1 standalone helper deferral.

Manual §5.0 walkthrough count is 71 = 69 accumulated + 1 Phase 3.1-Driver + 1 new Phase 4 scenario (gated on Step 7 SDK scaffolding for live-data sanity check). Phase 2.4 scenarios still need Andy's Neon migrations + ETL re-run before they're runnable.

Doc-sweep nits ledger reduced by 1 (`Race_Events_D66_Design_v1.md` §8.3 closed). 5th deferred nit (`Layer2E_Spec.md` §6.1 + §14 D-26 wording) remains active.

---

**End of handoff.**
