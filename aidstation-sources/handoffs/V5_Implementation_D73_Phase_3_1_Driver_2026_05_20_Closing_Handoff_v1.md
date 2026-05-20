# D-73 Phase 3.1-Driver — Layer 3A LLM Driver — Closing Handoff

**Session:** Phase 3.1 split-scope second half. Andy opened with the substrate handoff URL + "lets go!" → state report per Rule #13 → picked **Phase 3.1-Driver** at the first scope gate → after the file plan + D1-D10 + gut check were laid out, picked **Approve + add caching** at the second scope gate. This session lands the first upstream LLM driver — `llm_layer3a_athlete_state` + paired prompt body + cache wrapper + 54 tests. First real Anthropic SDK call site in the codebase (production callers need `ANTHROPIC_API_KEY` once Step 7 scaffolding lands; tests use a stub).
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_3_1_Substrate_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/v5-substrate-phase-3-asZdL` (harness-pinned; substrate predecessor's branch name carried forward — second-half session continuity).
**Status:** 🟢 5 substantive files shipped at ceiling. 995 tests green (941 baseline + 54 new). Phase 3 complete for Layer 3A (substrate + driver same-day).

---

## 1. Session-start verification (Rule #9)

Anchor sweep of predecessor §8 via `./aidstation-sources/scripts/verify-handoff.sh` + 941-test baseline rerun.

| Claim | Anchor | Result |
|---|---|---|
| All §8 anchor paths from predecessor exist on disk | `verify-handoff.sh` [1] | ✅ 11 of 13 paths ✅; the 2 ❌ are forward-references to this session's deliverables (`prompts/Layer3A_v1.md` + `tests/test_layer3a_builder.py`) — expected drift, not actual drift |
| Predecessor §8 table reads green | `verify-handoff.sh` [3] | ✅ extracted clean |
| `python -m pytest tests/` → 941 passed | bootstrap + rerun | ✅ `941 passed in 3.11s` after the documented `pip install --break-system-packages` bootstrap |
| Working tree clean at session start | `git status` | ✅ |

**No drift between predecessor narrative and on-disk state.** The two missing paths (`prompts/Layer3A_v1.md` + `tests/test_layer3a_builder.py`) were §6.1 forward-references in the predecessor handoff naming next-session deliverables; this session creates them.

---

## 2. Session narrative

Andy opened with the predecessor handoff URL + "lets go". Session-start verification per Rule #13 ran clean (state report per CLAUDE.md first-session-checklist step 7; 2 expected forward-ref drift entries flagged but not blocking). Andy picked **Phase 3.1-Driver** at the scope question.

Triggers #2 (LLM prompt body design) + #5 (architectural alternatives) fired. I read the precedent surfaces (`layer4/single_session.py` for the Anthropic SDK adapter pattern + `layer4/hashing.py` for cache key primitives + `layer4/cached_wrappers.py` for the cache wrapper shape + `Layer3_3A_Spec.md` in full + `Layer4_SingleSession_v2.md` for the prompt body precedent + the existing `layer3a/integration.py` substrate shape + the `Layer3APayload` pydantic schema in `layer4/context.py` lines 656-738) and then presented the plan-mode gate in chat with:

1. The 5-file scope (substantive count) — builder.py + prompt body + tests + spec 1-line fix + __init__ re-exports (the last one is bookkeeping per B3).
2. The 10 D-decisions table with recommendations + rationale per spec citation.
3. The pattern shape (single LLM call wrapped in input prep → invoke → 1 capped retry on schema violation → evidence-basis check → confidence-floor clamp → metadata stamp).
4. A gut check covering 5 named risks + 3 "what might be missing" + best argument against (split into two calls).

Andy picked **Approve + add caching**, which adds a 6th substantive file (`layer3a/cached_wrapper.py`) reusing the generic `CacheBackend` from `layer4/cache.py`. To stay at 5 substantive files, the cache wrapper was sized small (~150 LOC) and its tests were combined into `test_layer3a_builder.py` rather than a separate file.

Execution:

1. **Prompt body** (`prompts/Layer3A_v1.md`, ~530 lines) shipped first as the design-doc anchor for system prompt + tool schema rationale + D1-D10 + post-LLM transforms.
2. **Driver** (`layer3a/builder.py`, ~900 LOC) implemented the full pipeline: input validation per spec §4 → 8 prep helpers per spec §5.1 → user prompt rendering → Anthropic SDK adapter with extended thinking + forced tool-use → single capped retry on schema violation per spec §5.3 step 1 → name-existence evidence_basis cross-check per spec §5.3 step 2 → §6.2 floor-rule clamp (4 floor rules) + §6.2 high-gate criteria (5 conditions) → §6.3 auto-appended observation → metadata stamping. Errors inlined (`Layer3AInputError` + `Layer3AOutputError` + `Layer3AEvidenceBasisWarning`) per Step 4a + Layer 2C precedent.
3. **Cache wrapper** (`layer3a/cached_wrapper.py`, ~150 LOC) reuses `CacheBackend` + `PER_ENTRY_PHASE_IDX_SENTINEL` from `layer4/cache.py` with 3A-specific serialize/hydrate via `Layer3APayload.model_dump_json` / `model_validate_json` + day-granular cache key per spec §9.1.
4. **Spec §3.3 model literal correction** — `claude-sonnet-4-5` → `claude-sonnet-4-6` per D7 + Phase 3.1-Driver D7 audit pointer.
5. **Tests** (`tests/test_layer3a_builder.py`, ~970 lines) — 54 tests across 8 classes using stub `llm_caller` per Step 4a precedent.

First test pass hit 6 failures, all in `tests/test_layer4_cache.py::TestEvictionPolicy` because I'd extended `VALID_ENTRY_POINTS` in `layer4/cache.py` (to allow `put()` with the new `"llm_layer3a_athlete_state"` entry point), which broke the invariant `set(policy_for_layer(...)) == set(VALID_ENTRY_POINTS)` that those tests assert (Layer 4 invalidation policies are scoped to the original 4 Layer 4 entry points; the new 3A entry doesn't participate in the §9.3 matrix). Fix: split `LAYER4_ENTRY_POINTS` (frozenset of the 4 originals) + `VALID_ENTRY_POINTS` (the superset), update the 6 failing test assertions, re-export `LAYER4_ENTRY_POINTS` from `layer4/__init__.py`. Second pass: 995/995 green. Bookkeeping: CURRENT_STATE pointer flipped; CARRY_FORWARD Phase 3.1-Driver section replaced with closeout + follow-on list; Upstream Plan §4 row 3.1-Driver marked ✅; this handoff.

Earlier test-fixture bugs (made-up `TrainingGapsSummary` field names + `InMemoryCacheBackend(max_entries=...)` kwarg that doesn't exist + `datetime(2026, 5, 20, 12, 0)` past the container's `now()` + `providers or [...]` defaulting on empty list) all surfaced + fixed during the first test pass.

---

## 3. File-by-file edits

### 3.1 `layer3a/builder.py` (NEW, ~900 LOC)

The main driver. Structure:

- **Errors block** — `Layer3AInputError` (carries `code` + optional `detail`) + `Layer3AOutputError` (same shape) + `Layer3AEvidenceBasisWarning` (UserWarning subclass). Inlined per Step 4a + Layer 2C precedent.
- **Constants block** — `_APPROVED_MODELS` frozenset (sonnet-4-6, sonnet-4-5 retained for replay, opus-4-7, haiku-4-5); `_TOOL_NAME = "record_athlete_state"`; `_CONFIDENCE_RANK` dict for `min()`-style clamping; default-model/temperature/max-tokens/thinking-budget literals.
- **LLM caller protocol** — `_LLMOutput` dataclass + `LLMCaller` type alias matching `layer4/single_session.py:_default_llm_caller`'s 7-arg signature.
- **`_default_llm_caller`** — production Anthropic SDK invocation with extended thinking (D2 = 4000 tokens) + forced tool-use (D1). Raises `Layer3AOutputError("anthropic_api_key_missing")` when env var unset; raises `Layer3AOutputError("schema_violation")` if no `record_athlete_state` tool_use block emitted.
- **`build_record_athlete_state_tool`** — full `Layer3APayload` mirror per D5 (CurrentState + RecentTrajectory + ACWRStatus per-discipline dict + DataDensity + Observation list); `additionalProperties: false` at every nesting level; enums per spec §7 (5-value Assessment level, 8-value TrajectoryWindow direction, 5-value ACWREntry zone, 4-value Observation category, 3-value confidence).
- **`_validate_inputs`** — §4 preconditions: layer1_payload non-None, identity present, primary_sport populated, layer2a_payload non-None + disciplines non-empty, bundle non-None, as_of non-None + within 1h-future-skew, etl_version_set non-empty, model in approved list, temperature in [0, 1]. Each raises `Layer3AInputError(code, detail)`.
- **`_compute_age`** — DOB → age (years) at as_of.
- **`_section_completeness_estimate`** — per-section field-population ratios for §C / §D / §E / §F / §I against the typed Layer1 shape. Not currently rendered into the prompt (LLM self-reports per its prompt-read counts) but exposed as a helper for future driver-side override.
- **8 prep-render helpers** per spec §5.1: `_render_demographics`, `_render_training_history`, `_render_discipline_baselines` (filters to 2A-included disciplines, omits empty), `_render_strength`, `_render_performance` (tags stale tests >12mo), `_render_lifestyle`, `_render_integration_summary` (per-accessor counts + per-source breakdowns + ACWR rows + provider coverage), `_render_phase_context` (framework_sport + included disciplines + roles + load_weight).
- **`_render_health_context_note`** — max-2-sentence §B summary per spec §5.2. Top-3-most-recent-active-injuries. Pregnancy NEVER referenced (Onboarding v4 disclosure-only).
- **`_build_prep_dict`** — flat `{section.field_path: value}` dict consumed by `_check_evidence_basis` for name-existence validation.
- **`_SYSTEM_PROMPT`** — the 11-rule system prompt body matching `prompts/Layer3A_v1.md` §5 verbatim (CLAUDE.md voice + spec §6.1 weighting + §6.2 calibration + §8.1 required observations + §8.2 forbidden observations + §8.3 ordering + §7 schema-level rules + the "units MUST be hours" §11 rule).
- **`_render_user_prompt`** — assembles the 8 prep blocks + 2A phase context + §B note + as_of line + tool-call instruction. On retry, appends the schema error message + a re-emit instruction.
- **`_collect_evidence_basis` + `_check_evidence_basis`** — walks the validated tool args + raises `Layer3AEvidenceBasisWarning` per unknown field path. No fail.
- **`_clamp_confidence` + `_check_high_confidence_gates`** — clamp helper (`min()` style on `_CONFIDENCE_RANK`) + 5-gate predicate (active provider with data, ≥10 recent workouts, §C years_structured_training non-null, §F hrmax + ≥1 threshold metric, §I sleep_baseline_hours non-null).
- **`_apply_confidence_floors`** — applies §6.2 floor rules (4 stackable) + high-gate clamp + §6.3 appends a single `confidence_clamped_by_data_density` observation enumerating fired signals. Uses pydantic `model_copy(update=...)` for immutable-update semantics.
- **`_prompt_hash`** — sha256 of `system_prompt + "||" + user_prompt` for metadata.
- **`llm_layer3a_athlete_state`** — the public entry point. Algorithm: validate → render → up to 2 LLM attempts (single capped retry on `ValidationError`) → evidence-basis warn → floor clamp → return. Default args per D6/D7/D2 + spec §3.

### 3.2 `layer3a/cached_wrapper.py` (NEW, ~150 LOC)

- **`layer3a_athlete_state_key`** — cache key per spec §9.1. Components: `user_id || layer1_hash || layer2a_hash || integration_bundle_hash || day_anchor.isoformat() || canonical_json(etl_version_set) || model || str(temperature) || str(max_tokens) || str(extended_thinking_budget)`. `day_anchor = as_of.replace(hour=0, minute=0, second=0, microsecond=0)` so intra-day calls on identical inputs collide on the same key.
- **`_serialize_layer3a_payload` + `_hydrate_layer3a_payload`** — pydantic `model_dump_json` / `model_validate_json`. Layer3APayload is self-contained (no `plan_version_id` / `suggestion_id` rebinding), so no `_rebind_payload_dict` analog needed.
- **`llm_layer3a_athlete_state_cached`** — get/put against `CacheBackend`; on hit returns hydrated payload; on miss invokes the underlying driver, serializes the result, stores via `backend.put(...)` with `entry_point="llm_layer3a_athlete_state"`.

### 3.3 `aidstation-sources/prompts/Layer3A_v1.md` (NEW, ~530 lines)

Prompt body design doc. Structure:

- **Source decisions table** — D1-D10 with picks + rationale per spec citation. Each pick names the spec section it implements and (where relevant) the Layer 4 precedent it inherits.
- **§1 Purpose + scope** — what this prompt produces (Layer3APayload sans metadata) + what it does NOT (boundaries per spec §2) + failure modes the retry catches.
- **§2 Pipeline placement** — call site, pattern shape (8-step algorithm), out-of-pipeline cases (cache hit, input failure).
- **§3 Inputs** — 10 sub-sections enumerating the prep variables from each Layer 1 section + 2A + bundle + as_of + §B health note + pregnancy-never reminder.
- **§4 Tool schema** — full JSONC sketch of the `record_athlete_state` tool with `additionalProperties: false` at every nesting level; matches `build_record_athlete_state_tool()` verbatim.
- **§5 System prompt** — the 11-rule verbatim text (matching `_SYSTEM_PROMPT` constant in builder.py).
- **§6 User prompt template** — template-variable substitution sketch + retry-augmentation text.
- **§7 Sampling config** — model / temperature / max_tokens / thinking budget / capped_retries / tool_choice.
- **§8 Post-LLM transforms** — schema validation + evidence-basis cross-check + confidence-floor clamp implementation notes including the 4 floor rules + 5 high-gate criteria + signal-summary observation shape.
- **§9 Performance budget** — per spec §11.
- **§10 Caching** — cache key formula + day-granular semantics + invalidation triggers + cross-reference to cached_wrapper.py.
- **§11 Test scenarios** — pointer to §13 spec scenarios + note that stubs test contract not real-LLM enums.
- **§12 Open items** — 4 deferred items (L3A-P-1 real-LLM regression, L3A-P-2 evidence-basis cardinality, L3A-P-3 Haiku experiment, L3A-P-4 driver-side section_completeness).
- **§13 Gut check** — 5 risks named + 3 missing-bits + 2 best-arguments-against.

### 3.4 `tests/test_layer3a_builder.py` (NEW, ~970 lines, 54 tests)

8 test classes:

- **TestInputValidation** (10 tests) — all §4 preconditions: missing_layer1, incomplete_onboarding (primary_sport None), missing_2a (None + empty disciplines), missing_integration_bundle, invalid_as_of (future), missing_etl_pin, unapproved_model, invalid_temp, and a defensive incomplete_onboarding variant.
- **TestToolSchema** (8 tests) — tool name, top-level required fields, Assessment level enum (5), TrajectoryWindow direction enum (8), ACWR zone enum (5), Observation category enum (4), weak_links maxItems=5, additionalProperties=false.
- **TestEntryPointHappyPath** (2 tests) — dense-data §13.1-like round trip + metadata stamping (user_id / as_of / model / temperature / token counts / prompt_hash sha256 hex).
- **TestConfidenceFloors** (11 tests) — each of the 4 floor rules fires; high-gate fails when each of the 5 conditions misses; clamp does not upgrade low → medium; `_clamp_confidence` helper; `_check_high_confidence_gates` helper; no-clamp-signal-no-observation invariant.
- **TestSchemaViolation** (3 tests) — invalid-then-valid succeeds after retry; two invalid raises `Layer3AOutputError("schema_violation")`; bad enum value triggers retry.
- **TestEvidenceBasisCheck** (1 test) — unknown evidence_basis paths emit `Layer3AEvidenceBasisWarning` but call succeeds.
- **TestS13Scenarios** (6 tests) — §13.2 sparse data / §13.3 conflicting signals / §13.4 returning athlete / §13.6 no providers rich self-report / §13.7 precondition failure (LLM not called via explode-stub) / §13.10 ACWR red zone. §13.1 / §13.5 / §13.8 / §13.9 are LLM-reasoning-quality scenarios deferred to Step 7/8 telemetry tuning (covered conceptually by TestEntryPointHappyPath + TestConfidenceFloors).
- **TestPrepDict** (5 tests) — prep dict contains expected section keys; prompt renders for full fixture; injury health note renders when injuries present; "no active injuries" rendered when none; retry-error text rendered when provided.
- **TestCacheWrapper** (7 tests in TestCacheWrapper class) — cache miss + hit (call_count==1 across 2 calls); day-granular collapses intraday calls on same key; key changes with etl_version_set / model / user_id; key stable across same inputs (sha256 hex 64 chars); round-trip payload metadata preserved.

Stub `llm_caller` matches Step 4a precedent (`_LLMOutput` dataclass with `tool_args` / `input_tokens` / `output_tokens` / `latency_ms`). `_sequence_caller` returns outputs[i] on the i-th call (retry tests). All tests use the dependency-injectable `llm_caller` param; no real Anthropic SDK invocation; no `ANTHROPIC_API_KEY` env requirement.

### 3.5 `aidstation-sources/Layer3_3A_Spec.md` — 1-line model literal correction

§3.3 `model: str = "claude-sonnet-4-5"` → `model: str = "claude-sonnet-4-6"` with paired comment pointing to Phase 3.1-Driver D7 audit.

### 3.6 Bookkeeping (outside ceiling per CLAUDE.md B3)

- `layer3a/__init__.py` — re-exports the new public surface (driver entry, cache wrapper, errors, tool builder, cache key fn). 6 new symbols + alphabetized `__all__`.
- `layer4/cache.py` — split `LAYER4_ENTRY_POINTS` (frozenset of 4 originals, used by `cache_invalidation.py` policy matrix) + `VALID_ENTRY_POINTS` (the superset that adds `"llm_layer3a_athlete_state"` for the 3A wrapper's `put()` validation). Single-purpose split; pure backward-compatible (VALID_ENTRY_POINTS still includes the 4).
- `layer4/__init__.py` — re-export `LAYER4_ENTRY_POINTS` (alphabetized into the cache section + the `__all__` list).
- `tests/test_layer4_cache.py` — 6 assertion swaps from `VALID_ENTRY_POINTS` → `LAYER4_ENTRY_POINTS` in `TestEvictionPolicy` (the §9.3 invalidation matrix is Layer 4-scoped, not the superset). Added the import to the existing `from layer4 import (...)` block.
- `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 3.1-Driver marked ✅ Shipped 2026-05-20 with file count + test delta + D1-D10 summary; Phase 3 total updated to "complete for Layer 3A".
- `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer status row 3 updated to 🟢 3A complete; Tests note 941 → 995; Current focus reframed to Phase 4 Layer 3B driver.
- `aidstation-sources/CARRY_FORWARD.md` — Phase 3.1-Driver section replaced with closeout (D1-D10 picks recorded) + remaining follow-on list (real-LLM scaffolding, §13 regression, evidence-basis cardinality, Haiku experiment, section_completeness override, 3A cache invalidation routing, Layer 3 orchestrator).
- This handoff.

---

## 4. Code / tests

- New code: ~1580 LOC across `layer3a/builder.py` (~900) + `layer3a/cached_wrapper.py` (~150) + `tests/test_layer3a_builder.py` (~970, of which ~530 are fixtures / test infra) — substantive driver footprint ~1050 LOC.
- New prompt body: `aidstation-sources/prompts/Layer3A_v1.md` ~530 lines.
- New tests: 54 across 8 classes (split: 10 input validation + 8 tool schema + 2 happy path + 11 floor clamp + 3 schema retry + 1 evidence-basis + 6 §13 scenarios + 5 prep/prompt + 7 cache wrapper + 1 evidence-basis = 54).
- `tests/` count: 941 → 995 (+54).
- `python -m pytest tests/ -q` → `995 passed in 1.46s` post-final-edit.

---

## 5. Operational sequence for Andy on Neon

N/A for this session (no schema migrations). When Step 7 lands the `ANTHROPIC_API_KEY` env scaffolding, the §5.0 walkthrough scenario for Phase 3.1-Driver becomes runnable: invoke `llm_layer3a_athlete_state(user_id=andy, layer1_payload=build_layer1_payload(db, andy), layer2a_payload=q_layer2a_discipline_classifier_payload(...), integration_bundle=assemble_layer3a_integration_bundle(db, andy, as_of=datetime.now()), as_of=datetime.now(), etl_version_set=<plan-gen pin>)` against Andy's live PGE 2026 context — confirm:

- `current_state.aerobic_capacity.level` lands in {`moderate`, `good`, `strong`} with confidence calibrated to data density (likely `medium` until providers fully connect — high-gate fails on "no active provider with all coverage").
- `current_state.weak_links` populated with athlete-relevant short phrases (e.g., "single-leg balance", "shoulder press strength").
- `current_state.skill_assessments` sparse — only included disciplines per 2A AR set (D-001, D-005, D-006, D-007, D-008b, D-013).
- `recent_trajectory.short_term.direction` calibrated to recent activity; if Andy hasn't logged in 7 days, expect `insufficient_data` or `detrained`.
- `recent_trajectory.acwr_status.combined` populated from `cardio_log` durations if any; `None` if empty log.
- `notable_observations` filtered to actionable items (no platitudes, no goal viability statements, no injury-risk claims).
- If clamping fires, `confidence_clamped_by_data_density` observation appended with the signal list (e.g., "no_connected_providers, sparse_recent_workouts").

The Phase 2.4-Prep operational sequence (3 SQL migrations + ETL re-run) is still the live prerequisite for the Phase 2.4 §5.0 walkthrough scenarios, unchanged.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Phase 4 — Layer 3B LLM driver** (architect-recommended per Upstream Plan §4 row 4.1). Same shape as 3.1-Driver:

- `llm_layer3b_*(...)` entry point in `layer3b/builder.py` (new module).
- Prompt body `aidstation-sources/prompts/Layer3B_v1.md` mirroring the 3A pattern.
- Cache wrapper `layer3b/cached_wrapper.py` reusing `CacheBackend` per spec §9.
- Tests in `tests/test_layer3b_builder.py` covering §4 preconditions + §13 scenarios + §6.x floor enforcement + cache wrapper round-trip.

Opens with a `/plan-mode` gate walking the 3B-specific D-decisions (likely similar D1-D10 list to 3A — recommend reusing the picks where the spec aligns + only re-litigating where 3B's semantics differ).

`Layer3BPayload` pydantic schema is already shipped (`layer4/context.py`) — no schema work.

### 6.2 Alternative pivots

- **Layer 4 Step 7** — env-gated `ANTHROPIC_API_KEY` scaffolding. Lands the first REAL SDK invocation against 3A (the driver just shipped). Unblocks the Phase 5 vertical slice in parallel. ~3-4 files. Pair with 1-2 §13 fixture runs as smoke tests.
- **§H.2 / §J / §I.1 form-refresh PR** — paired alignment to wire Layer 2B + Layer 2E input-source surfaces (~6-8 files, over ceiling).
- **Plan Management spec authorship** — de-stubs Layer 2E §5.8 heat acclim + 2E-2/3/4 open items.
- **D-73 Phase 1.4** — D-52 catalog migration sequencing.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration.
- **Manual §5.0 walkthrough** of the accumulated 69 scenarios + 1 new Phase 3.1-Driver scenario (paragraph above — gated on Step 7).

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff; layer status row 3 is 🟢
3. `aidstation-sources/CARRY_FORWARD.md` — Phase 3.1-Driver follow-ons (real-LLM scaffolding, §13 regression, etc.) — these are forward-references, not blockers
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward):** the cloud container's default `pytest` is `uv tool install` isolated Python; working path is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**If picking Phase 4 — Layer 3B LLM driver:** open with the `/plan-mode` gate walking the 3B D-decisions. Reuse the 3A D1-D10 picks as the starting point (they're spec-aligned and Layer 4 Step 4a-precedented) + identify where 3B's semantics diverge (likely D2 thinking budget — 3B is goal-viability synthesis which may want more budget; possibly D7 model — 3B may justify Opus 4.7 if its judgment is more consequential). Pair with any spec drift fixes flagged in `Layer3_3B_Spec.md`.

**If picking Layer 4 Step 7:** env-gating + Anthropic SDK smoke harness lands; pair with a 1-2 §13.x real-LLM regression run on the new 3A driver to flag any prompt-body misses early.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Phase 3.1-Driver scope = approve + add caching (5 substantive files at ceiling; cached_wrapper sized small to fit) | Andy 2026-05-20 | Caching closes spec §9 contract this session rather than deferring to a follow-on. The wrapper is small (~150 LOC) + reuses generic CacheBackend → fits cleanly alongside the driver. |
| 2 | D1 forced tool-use; D2 4000-token thinking budget; D3 inline-Python rendering; D4 single capped retry on schema violation only; D5 full Layer3APayload mirror; D6 max_tokens=4000; D7 sonnet-4-6 default + spec §3.3 1-line fix; D8 post-LLM clamp + auto-append observation; D9 name-existence evidence-basis check; D10 CLAUDE.md voice rules + spec §8.2 inlined | Andy 2026-05-20 (approved as recommended) | All 10 picks aligned to spec citations + Step 4a precedent. D7 is the only spec-drift correction (stale sonnet-4-5 literal). D4 is intentionally lighter than Step 4a (no validator-driven retry loop because 3A has no deterministic validator — only post-LLM confidence-floor clamping which is a transform, not a fail-condition). |
| 3 | Errors inlined in builder.py (no `layer3a/errors.py`) | Architect-pick | Step 4a inlined + Layer 2C inlined + Layer 3A is a single driver (not a multi-driver family yet). Precedent supports inlining. |
| 4 | `Layer3AInputError` carries `code` attribute (not just message string) | Architect-pick + spec §4 | Spec §4's error codes are caller-routable (3D HITL vs hard fail). `code` exposure lets the caller dispatch without string parsing. |
| 5 | `_apply_confidence_floors` uses `pydantic.model_copy(update=...)` for immutability | Architect-pick | Pydantic-idiomatic; preserves payload-as-data semantics; no risk of mutating an upstream-cached instance. |
| 6 | `LAYER4_ENTRY_POINTS` split from `VALID_ENTRY_POINTS` in `layer4/cache.py` rather than registering 3A as a Layer 4 entry point | Architect-pick (after test regression surfaced) | The Layer 4 invalidation policy matrix per spec §9.3 is Layer 4-scoped. Registering 3A as a Layer 4 entry would force a §9.3-equivalent policy row for 3A inside Layer 4's eviction module, which is the wrong owner. Split preserves the spec invariant + lets the 3A cache participate in the same storage backend. |
| 7 | Cache wrapper tests folded into `test_layer3a_builder.py` (not a separate `test_layer3a_cached_wrapper.py`) | Architect-pick + ceiling discipline | Keeps substantive file count at 5. Cache tests are small (7) + share fixtures with builder tests. Splitting would add a 6th substantive file without clarity gain. |
| 8 | §13 test scenarios — 6 of 10 covered via stub round-trip; 4 (§13.1/§13.5/§13.8/§13.9) deferred | Architect-pick + Step 7 territory | The 4 deferred scenarios test LLM reasoning quality (enum classifications), not contract. Real-LLM regression lives in Step 7/8 telemetry tuning per `Layer3A_v1.md` §12 item L3A-P-1. Stub tests verify contract (validation + clamp + assembly); they cannot verify "Sonnet picks `strong` for dense-data fixtures." |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer3a/builder.py` exists + contains `def llm_layer3a_athlete_state(` | ✅ inspection |
| `layer3a/builder.py` contains `class Layer3AInputError(` + `class Layer3AOutputError(` + `class Layer3AEvidenceBasisWarning(` | ✅ grep |
| `layer3a/builder.py` contains `def build_record_athlete_state_tool(` returning the full `Layer3APayload` mirror schema | ✅ inspection |
| `layer3a/builder.py` contains `def _apply_confidence_floors(` with the 4 floor rules + high-gate clamp | ✅ inspection |
| `layer3a/builder.py` contains `def _check_high_confidence_gates(` with the 5 gate criteria | ✅ inspection |
| `layer3a/builder.py` contains `def _default_llm_caller(` using `anthropic.Anthropic` with `tool_choice` + `thinking` | ✅ grep |
| `layer3a/cached_wrapper.py` exists + contains `def llm_layer3a_athlete_state_cached(` + `def layer3a_athlete_state_key(` | ✅ inspection |
| `layer3a/cached_wrapper.py` `layer3a_athlete_state_key` uses day-granular `as_of.replace(hour=0, minute=0, second=0, microsecond=0)` | ✅ grep |
| `aidstation-sources/prompts/Layer3A_v1.md` exists + contains "D1-D10" decision table + the 11-rule system prompt | ✅ inspection |
| `Layer3_3A_Spec.md` §3.3 model literal is `claude-sonnet-4-6` (not stale `claude-sonnet-4-5`) | ✅ grep |
| `tests/test_layer3a_builder.py` exists + contains 54 tests across 8 classes (`TestInputValidation` / `TestToolSchema` / `TestEntryPointHappyPath` / `TestConfidenceFloors` / `TestSchemaViolation` / `TestEvidenceBasisCheck` / `TestS13Scenarios` / `TestPrepDict` / `TestCacheWrapper`) | ✅ pytest collected + class grep |
| `python -m pytest tests/test_layer3a_builder.py -q` → 54 passed | ✅ `54 passed in 0.38s` |
| `python -m pytest tests/ -q` → 995 passed | ✅ `995 passed in 1.46s` |
| `layer3a/__init__.py` re-exports `llm_layer3a_athlete_state` + `llm_layer3a_athlete_state_cached` + `Layer3AInputError` + `Layer3AOutputError` + `build_record_athlete_state_tool` + `layer3a_athlete_state_key` | ✅ `python -c "from layer3a import llm_layer3a_athlete_state, llm_layer3a_athlete_state_cached, Layer3AInputError, Layer3AOutputError, build_record_athlete_state_tool, layer3a_athlete_state_key; print('ok')"` returns clean |
| `layer4/cache.py` exports both `LAYER4_ENTRY_POINTS` (4 originals) + `VALID_ENTRY_POINTS` (superset incl. `"llm_layer3a_athlete_state"`) | ✅ grep |
| `layer4/__init__.py` re-exports `LAYER4_ENTRY_POINTS` | ✅ grep |
| `tests/test_layer4_cache.py` `TestEvictionPolicy` uses `LAYER4_ENTRY_POINTS` for the policy-matches-Layer4 invariants | ✅ grep |
| `aidstation-sources/Upstream_Implementation_Plan_v1.md` §4 row 3.1-Driver reads "✅ Shipped 2026-05-20" with file/test summary | ✅ grep |
| `aidstation-sources/CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Layer status row 3 reads "🟢 3A complete" | ✅ inspection |
| `aidstation-sources/CURRENT_STATE.md` Tests note reads "995 green" | ✅ inspection |
| `aidstation-sources/CARRY_FORWARD.md` Phase 3.1-Driver section reframed as follow-on list (real-LLM scaffolding etc.) | ✅ inspection |
| Working tree clean after commit + push (pending) | ⏳ pending commit |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (5 files; AT the 5-file ceiling):**

1. NEW `layer3a/builder.py` — `llm_layer3a_athlete_state` driver + tool schema builder + `_default_llm_caller` Anthropic SDK adapter + 8 prep helpers + confidence-floor clamp + inlined errors. ~900 LOC.
2. NEW `layer3a/cached_wrapper.py` — `llm_layer3a_athlete_state_cached` + `layer3a_athlete_state_key` + serialize/hydrate helpers. ~150 LOC.
3. NEW `aidstation-sources/prompts/Layer3A_v1.md` — prompt body design doc (D1-D10 + system prompt body + user prompt template + tool schema + post-LLM transforms + caching + gut check). ~530 lines.
4. NEW `tests/test_layer3a_builder.py` — 54 tests across 8 classes using stub `llm_caller`. ~970 lines.
5. MODIFIED `aidstation-sources/Layer3_3A_Spec.md` — §3.3 `claude-sonnet-4-5` → `claude-sonnet-4-6` (1-line correction).

**Bookkeeping (7 files; outside ceiling per B3):**

6. MODIFIED `layer3a/__init__.py` — re-exports the new driver + cache wrapper + errors + tool builder + cache key fn.
7. MODIFIED `layer4/cache.py` — split `LAYER4_ENTRY_POINTS` (4 originals) + `VALID_ENTRY_POINTS` (superset adds `"llm_layer3a_athlete_state"`).
8. MODIFIED `layer4/__init__.py` — re-export `LAYER4_ENTRY_POINTS`.
9. MODIFIED `tests/test_layer4_cache.py` — 6 assertion swaps + import addition (preserves the Layer 4-scoped invalidation invariant against the broader VALID_ENTRY_POINTS).
10. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — §4 row 3.1-Driver ✅ Shipped + Phase 3 total updated.
11. MODIFIED `aidstation-sources/CURRENT_STATE.md` — pointer flipped; Layer status row 3 to 🟢; Tests note 941 → 995; Current focus reframed to Phase 4.
12. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Phase 3.1-Driver section replaced with closeout + follow-on list.
13. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_3_1_Driver_2026_05_20_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` Phase 3.1-Driver section replaced with closeout listing the D1-D10 picks shipped + 8 follow-on items (real-LLM smoke test scaffolding for Step 7, §13.1/§13.5/§13.8/§13.9 real-LLM regression deferred to Step 7/8, per-field evidence_basis cardinality enforcement L3A-P-2, Haiku-vs-Sonnet experiment L3A-P-3, driver-side `data_density.section_completeness` override L3A-P-4, 3A cache invalidation routing module, Layer 3 orchestrator wiring, §B health-context note text length trim policy).

Manual §5.0 walkthrough count is 70 = 69 accumulated + 1 new Phase 3.1-Driver scenario gated on Step 7 SDK scaffolding. Phase 2.4 scenarios still need Andy's Neon migrations + ETL re-run before they're runnable.

Doc-sweep nits ledger unchanged. The 5th deferred nit (`Layer2E_Spec.md` §6.1 + §14 D-26 wording) remains active.

---

**End of handoff.**
