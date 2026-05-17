# V5 Implementation — Layer 4 Step 4d T3 Plan-Refresh Closing Handoff

**Session:** Single chat. Scope: Step 4d of `Layer4_Spec.md` §14.3.4 — `llm_layer4_plan_refresh` T3 intra-phase (D-64 caller integration; Pattern B per §6.3 single-phase T3 special case). Paired `Layer4_Spec.md` §3.2 + §4.3 surgical amendment (Step 4d) — `plan_start_date` parameter + `tier_t3_cross_phase_requires_pattern_a` precondition. §6.3 carry-forward from Step 4b/c bundled (`Plan_Refresh_D64_Design_v1.md` §3 + `Layer4_RefreshT1_v1.md` → `_v2.md` per Rule #12 reflecting the §4.3-wins 3B-required ripple). New `Layer4_RefreshT3_v1.md` prompt body (sixth post-arc).
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step4b_4c_PlanRefresh_Closing_Handoff_v1.md` (Step 4b/c — T1+T2 plan_refresh; 58 tests; combined 412 green).
**Branch:** `claude/implement-plan-refresh-closing-oJTxn` (harness-pinned for this session — name carried over from a prior Step 4b/c harness pin per the precedent across PR-A → Step 4a → Step 4b/c).
**Status:** 🟢 8 substantive code + 1 prompt body + 1 spec amendment + 2 carry-forward + 3 bookkeeping = 13 files. 33 new tests; combined `tests/` 412 → 445, all green in 0.57s. **Layer 4 implementation Step 4d closes here; Step 4e race-week-brief queued behind D-66; Step 4f `plan_create` Pattern A + T3 cross-phase queued next as the heaviest remaining.**

---

## 1. Session-start verification (Rule #9)

Predecessor (Step 4b/c) handoff §7 claimed: `layer4/plan_refresh.py` + `_t1.py` + `_t2.py` on disk; `layer4/context.py` Layer2Bundle + ParsedIntent appended; `layer4/__init__.py` exposes 4 new re-exports; combined `tests/` 412 green; `Project_Backlog_v46.md` exists; CLAUDE.md Backlog ref reads v46; PR #75 merge commit `d49aec7` on `origin/main`; working tree clean on a fresh-cut branch.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `layer4/plan_refresh.py` exists (~750 lines) | inspection | ✅ |
| `layer4/plan_refresh_t1.py` + `_t2.py` exist | inspection | ✅ |
| `layer4/context.py` exports Layer2Bundle + ParsedIntent | grep | ✅ |
| `tests/test_layer4_plan_refresh.py` 58 tests, combined 412 green | `python -m pytest tests/` | ✅ 412 passed in 0.89s |
| `Project_Backlog_v46.md` exists | `ls` | ✅ |
| CLAUDE.md Backlog ref reads v46 | grep | ✅ |
| Step 4b/c PR #75 merge commit `d49aec7` on `origin/main` | `git log --oneline` | ✅ |
| Working tree clean on fresh-cut branch | `git status` | ✅ clean |
| `Layer4_Spec.md` §3.2 signature drops `\| None` on `layer3b_payload` | grep line 144 | ✅ |

**No drift found.** Step 4b/c state on disk matches the handoff narrative. Branch name `claude/implement-plan-refresh-closing-oJTxn` is a harness pin (name carried over per the precedent across PR-A → Step 4a → Step 4b/c → Step 4d; mismatch with scope acknowledged + ratified).

---

## 2. Session narrative — Andy-confirmed scope; triggers #2 + #5 + #8 fired and routed

Andy opened with a URL pointer to the Step 4b/c closing handoff and "let's go." I followed §5 operating notes — re-read CLAUDE.md (Rule #13), ran Rule #9 verification, surfaced state + next focus (Step 4d architect-recommended) + drift (none), and surfaced four design picks via `AskUserQuestion`.

### 2.1 Picks surfaced via AskUserQuestion

**Round 1 (2026-05-17, 4-question batch):** scope confirmation + T3 prompt body posture.
1. **Scope = Step 4d T3 + §6.3 carry-forward** (bundles the §4.3-wins ripple into the same session).
2. **T3 prompt body = New `Layer4_RefreshT3_v1.md`** (Andy chose new file over subsuming into T2 long-window prompt).

**Round 2 (2026-05-17, 2-question batch after I asked Andy for plain-language explanations of the harder picks):**
3. **Phase-boundary detection = Build named `phase_structure_from_3b()` helper per §6.1 now** (vs lightweight in-module detection or inline math). Reusable by Step 4f Pattern A.
4. **`plan_start_date` plumbing = Add to entry-point signature as keyword + paired §3.2 amendment** (vs heuristic derivation from prior_plan_session_window).

**Round 3 (2026-05-17, 2-question batch — same session, separate AskUserQuestion call):**
5. **T3 sampling defaults = `max_tokens=10000`, `extended_thinking=6500`** (most generous; absorbs phase-trajectory reasoning + 4 weekly aggregates + deload-cadence picks).
6. **T3 continuity policy = Phase-trajectory-aware reshape (T3-specific)** (Andy 2026-05-17 Step 4d Pick 4) — the 4 weeks compose a coherent mesocycle toward the dominant phase's exit state; continuity to days 29-35 is soft (summary-table not verbatim).

### 2.2 Single-pass implementation against the spec

After Andy's picks, I read the spec/prompt-body anchors needed for implementation:
- `Layer4_Spec.md` §3.2 (function signature; post-Step-4b/c §4.3-wins amendment), §4.3 (input validation preconditions), §5.1 (pattern routing — T3 intra-phase → B, cross-phase → A), §5.3 (Pattern B algorithm), §6.1 (`phase_structure_from_3b()` helper spec), §6.3 (single-phase T3 special case)
- `aidstation-sources/prompts/Layer4_RefreshT2_v1.md` (closest analog for T3 prompt body shape)
- `aidstation-sources/Plan_Refresh_D64_Design_v1.md` §3.3 (T3 horizon + cascade)
- `layer4/plan_refresh.py` + `_t1.py` + `_t2.py` (existing driver shape + tier-module pattern to mirror)
- `layer4/context.py` (Layer3BPayload + PeriodizationShape types)
- `layer4/payload.py` (PhaseSpec + PhaseStructure pydantic models)

**§6.3 carry-forward (mechanically-spec'd in Step 4b/c handoff §6.3) — done first:**

1. `aidstation-sources/Plan_Refresh_D64_Design_v1.md` §2 Decision 4 + §3.1 — T1 default cascade now includes 3B re-run; amendment-rationale block citing the §4.3-wins resolution.
2. `aidstation-sources/prompts/Layer4_RefreshT1_v1.md` → `_v2.md` per Rule #12 — v1 retained as in-project history. Surgical edits: header status line v2 amendment summary; D3 source-decision row (3B added to T1 payload set); §3.5 header changed "inherited from adjacent sessions" → "freshly-re-run 3B" with variables re-grounded against `layer3b_payload.periodization_shape`; §3.8 — `layer3b_payload` row removed; `inherited_phase` template variable renamed to `current_phase` throughout (~9 occurrences).

**`layer4/phase_structure.py` (~250 lines):**
- `_MODE_PROPORTIONS` dict (standard 50/30/15/5; compressed 30/35/25/10; extended 60/25/10/5)
- `_INTENDED_INTENSITY_DISTRIBUTION` dict (Base 80/15/5; Build 70/20/10; Peak 70/20/10; Taper 75/15/10)
- `_OPEN_ENDED_DEFAULT_TOTAL_WEEKS = 12`
- `_zero_synthesis_metadata()` — placeholder for unsynthesized phases (PhaseSpec.synthesis_metadata required at pydantic level)
- `_allocate_weeks_standard(mode, total_weeks, start_phase)` — per-mode proportions × total; round to whole weeks; remainder to Base (or earliest remaining phase when Base skipped)
- `_allocate_weeks_custom(phase_weeks, start_phase)` — custom mode uses phase_weeks verbatim; filters to phases at or after start_phase
- `phase_structure_from_3b(layer3b_payload, plan_start_date, total_weeks=None) -> PhaseStructure` — main helper per §6.1
- `phase_for_date(phase_structure, target_date) -> PhaseSpec | None` — date lookup helper
- `scope_spans_phase_boundary(phase_structure, scope_start, scope_end) -> bool` — T3 dispatch helper

**`layer4/plan_refresh_t3.py` (~280 lines):**
- `DEFAULT_MAX_TOKENS = 10000`, `DEFAULT_EXTENDED_THINKING_BUDGET = 6500`
- `_DELOAD_CADENCE` dict (standard=4, compressed=3, extended=5, custom=None)
- `_format_deload_cadence_line(mode)` helper for §6 template
- `SYSTEM_PROMPT` — full text matching `Layer4_RefreshT3_v1.md` §5
- `render_user_prompt()` — accepts T3-specific `dominant_phase_*` kwargs; reuses T1's `_format_active_injuries` + `_format_prior_window_summary` + `_format_window_verbatim` + T2's `_format_weekly_aggregate`

**`Layer4_RefreshT3_v1.md` (~467 lines):**
- Source decisions D1-D13 captured in file header
- §1 purpose + scope, §2 pipeline placement, §3 inputs, §4 output schema, §5 system prompt, §6 user prompt template (Mustache), §7 sampling configuration, §8 coaching policy carve-outs, §9 voice + forbidden phrasings, §10 token + cost budget, §11 performance + latency, §12 test scenarios (PSS-T3-prefix × 18), §13 edge cases, §14 gut check

**`layer4/plan_refresh.py` modifications:**
- `build_record_refresh_sessions_tool()` typing extended to `Literal["T1", "T2", "T3"]`; maxItems via dict lookup (T1=4, T2=14, T3=56)
- `_validate_inputs()` gains `_T3_MAX_SCOPE_DAYS=32` constant + T3 scope precondition + new `plan_start_date_missing` precondition (raises when tier='T3' AND plan_start_date is None)
- Entry-point signature gains `plan_start_date: date | None = None` keyword argument
- T3 dispatch (replaces the prior `tier_t3_not_yet_implemented` raise): computes `phase_structure_from_3b()` + `scope_spans_phase_boundary()`; intra-phase routes to `plan_refresh_t3` module + extracts `dominant_phase_*` from `phase_for_date(scope_start)`; cross-phase raises `Layer4InputError('tier_t3_cross_phase_requires_pattern_a')` until Step 4f
- `render_user_prompt()` call unified via lazy import + `extra_kwargs` dict for the T3-only dominant-phase prompt args

**`layer4/__init__.py`** gains 3 new re-exports — `phase_for_date`, `phase_structure_from_3b`, `scope_spans_phase_boundary`.

**`Layer4_Spec.md` amendments:**
- §3.2 signature: `plan_start_date: date | None = None` added as keyword parameter
- §3.2 parameter table: new row for `plan_start_date` with full notes
- §4.3 precondition table: two new rows — `plan_start_date_missing` + `tier_t3_cross_phase_requires_pattern_a`

**`tests/test_layer4_phase_structure.py` (~290 lines, 24 tests):**
- TestPhaseStructureStandardMode × 4 (12wks corner case + 20wks clean + start_phase=Build + chained dates)
- TestPhaseStructureCompressedMode × 2 (15wks + no-zero-phases at 20wks)
- TestPhaseStructureExtendedMode × 1 (20wks exact proportions)
- TestPhaseStructureCustomMode × 4 (verbatim + start_phase=Peak drops earlier + skips zero entries + all-zero-raises)
- TestPhaseStructureDefaults × 2 (open-ended defaults to 12 + negative_total_weeks_raises)
- TestPhaseForDate × 5 (inside Base + at phase start + at phase end + before plan start returns None + after plan end returns None)
- TestScopeSpansPhaseBoundary × 6 (intra-phase + cross-phase + scope-starts-before-plan + scope-ends-after-plan + single-day-intra-phase + inverted-scope-raises)

**`tests/test_layer4_plan_refresh.py` modifications (9 new tests):**
- TestToolSchema gains `test_t3_maxitems_56`
- TestInputValidation gains `test_t3_plan_start_date_missing_raises` + `test_t3_scope_too_long_raises` + `test_t3_cross_phase_raises_pattern_a` (replacing the prior `test_t3_not_yet_implemented`)
- New TestT3IntraPhase × 6 — `test_intra_phase_routes_to_pattern_b` + `test_intra_phase_sessions_inside_scope` + `test_intra_phase_validator_results_accepted` + `test_intra_phase_empty_sessions_allowed` + `test_intra_phase_t3_uses_t3_max_tokens_default` (captures sampling defaults via stub caller) + `test_intra_phase_extended_mode_routes_correctly`

All 33 new tests green. Combined `tests/` count: 412 → 445, all green in 0.57s.

### 2.3 Architectural choices on the record

- **`phase_structure_from_3b()` lands as a full §6.1 helper now (not lighter inline detection)** per Andy 2026-05-17 Step 4d Pick 1. Reusable by Step 4f Pattern A which needs the same decomposition for per-phase synthesis.
- **`plan_start_date` plumbed through entry-point signature as keyword** per Andy 2026-05-17 Step 4d Pick 2. Over heuristic derivation from `prior_plan_session_window` minimum date (brittle — T3's prior window covers only the last 28 days) or `phase_metadata.start_date` (brittle — None on Pattern-B-only prior plans). Trigger #5 fires; routes through AskUserQuestion gate.
- **Cross-phase T3 raises `tier_t3_cross_phase_requires_pattern_a`** until Step 4f's per-phase orchestration ships — clean Pattern B / Pattern A routing surface per §5.1 + §6.3. The alternative (force Pattern B over full 28 days with single-phase intent) would violate §5.1 routing + lose seam-review at phase boundaries.
- **New `Layer4_RefreshT3_v1.md` prompt body** per Andy 2026-05-17 Step 4d Pick 4 (over subsuming into T2 long-window prompt). ~467 lines; sixth post-arc prompt body. T2's "match surrounding shape" framing doesn't fit T3's mesocycle-reshape coaching surface.
- **T3 sampling defaults `max_tokens=10000` + `extended_thinking_budget=6500`** per Andy 2026-05-17 Step 4d Pick 3. Generous for 4-week mesocycle reasoning. Typical cost ~$0.22/call.
- **Phase-trajectory-aware reshape** per Andy 2026-05-17 Step 4d Pick 4. T3 reshape is mesocycle-internal; continuity to week 5 is soft (summary-table not verbatim per D5 + D7).
- **Open-ended-mode horizon defaults to 12 weeks** per `Layer4_Spec.md` §6.1 v1 default. Event-mode caller would pass `total_weeks=time_to_event_weeks` override once the typed `Layer3BPayload.time_to_event_weeks` field lands; current helper accepts `total_weeks` kwarg override.
- **`_zero_synthesis_metadata()` placeholder** for unsynthesized phases at decomposition time — `PhaseSpec.synthesis_metadata` is required at the pydantic level; orchestrator overwrites each entry after the corresponding synthesizer call completes (per-phase synthesis is Step 4f Pattern A).
- **T1/T2/T3 dispatch unified via lazy import + `extra_kwargs` dict** for the T3-only dominant-phase prompt args — T1/T2's `render_user_prompt()` don't accept those kwargs, so the driver builds `extra_kwargs={}` for T1/T2 and `extra_kwargs={'dominant_phase_name': ..., 'dominant_phase_start_date': ..., 'dominant_phase_end_date': ...}` for T3.
- **12-week standard-mode corner case** documented inline — at 12 weeks, the 5% Taper proportion rounds to 0 weeks (`int(12 * 0.05) = 0`); Taper phase is dropped from the decomposition. Remainder (2 weeks) goes to Base. Test asserts this behavior explicitly. Not a bug — the spec §6.1 proportions are documented to round to whole weeks, and short horizons (≤12 weeks) naturally squeeze out Taper at the standard mode.

### 2.4 Stop-and-ask triggers — #2 + #5 + #8 fired and routed; #11 did NOT fire

- **Trigger #2 (designing or significantly modifying an LLM prompt body):** fired on the new `Layer4_RefreshT3_v1.md` prompt body. Routed via the 4-question AskUserQuestion gate (sampling defaults + continuity policy). Andy picked `max_tokens=10000` / `extended_thinking=6500` + phase-trajectory-aware continuity. The two-round AskUserQuestion gate substitutes for formal `/plan` mode per the precedent from Step 4a/4b/c.
- **Trigger #5 (schema/inter-layer-contract amendments):** fired on the `plan_start_date` parameter addition to §3.2 + the two new §4.3 precondition rows. Routed via the same AskUserQuestion gate. Andy picked Option a (named helper + signature plumbing) over the heuristic-derivation alternatives.
- **Trigger #8 (architectural alternatives with real tradeoffs):** fired on the phase-boundary detection landing choice (full §6.1 helper vs lightweight inline detection vs inline math without naming the helper). Routed via the same AskUserQuestion gate. Andy picked Option a (full helper now; reusable by Step 4f).
- **Trigger #11 (new cross-layer D-rows):** did NOT fire. No new D-rows; the §3.2 + §4.3 amendments are surgical contract-tightening, not new cross-layer dependencies. The existing D-66/D-67/D-68/D-70/D-71 forward-pointer cases are unaffected.
- Other triggers — none applicable.

### 2.5 Scope NOT changed this session

- **Step 4e race-week-brief** — queued behind D-66 race-event data model design wave.
- **Step 4f `plan_create` Pattern A orchestration** — heaviest remaining; per-phase synthesizer + seam reviewer wiring; ~6-8 files projected. T3 cross-phase Pattern A naturally lands here as a same-shape consumer of the per-phase orchestration.
- **Layer 1 typed payload** — out of v1 scope; `dict[str, Any]` opaque pass-through is the standing v1 contract.
- **D-66 / D-67 / D-68 / D-70 / D-71** — not touched.
- **`Layer3BPayload.time_to_event_weeks` field** — not yet typed in `layer4/context.py`; `phase_structure_from_3b()` accepts `total_weeks` as an explicit override kwarg as a forward-pointer.

---

## 3. Files shipped this session

One commit on `claude/implement-plan-refresh-closing-oJTxn` — 8 substantive code + 1 prompt body + 1 spec amendment + 2 carry-forward + 3 bookkeeping bundled (precedented by Step 4b/c 10 + PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6 + Step 4a 8).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `layer4/phase_structure.py` | New | ~250 lines. `phase_structure_from_3b()` per §6.1 — per-mode proportions + start_phase handling + open-ended 12-week default + chained per-phase date ranges; companion `phase_for_date()` + `scope_spans_phase_boundary()` helpers. |
| 2 | `layer4/plan_refresh_t3.py` | New | ~280 lines. T3 intra-phase tier module — `DEFAULT_MAX_TOKENS=10000`, `DEFAULT_EXTENDED_THINKING_BUDGET=6500`, per-mode `_DELOAD_CADENCE`, `_format_deload_cadence_line`, `SYSTEM_PROMPT`, `render_user_prompt()` with T3-specific dominant_phase_* kwargs. Reuses T1's formatting helpers + T2's `_format_weekly_aggregate`. |
| 3 | `layer4/plan_refresh.py` | Modified | Tool schema extended for T3 (maxItems=56); `_validate_inputs()` gains T3 scope cap + `plan_start_date_missing`; entry-point signature gains `plan_start_date` keyword; T3 dispatch routes intra-phase to `plan_refresh_t3` and raises `tier_t3_cross_phase_requires_pattern_a` on cross-phase; unified `render_user_prompt()` call via `extra_kwargs` for T3-only dominant-phase args. |
| 4 | `layer4/__init__.py` | Modified | 3 new re-exports — `phase_for_date`, `phase_structure_from_3b`, `scope_spans_phase_boundary`. |
| 5 | `tests/test_layer4_phase_structure.py` | New | ~290 lines, 24 tests. Standard/compressed/extended/custom mode coverage; phase_for_date × 5; scope_spans_phase_boundary × 6. |
| 6 | `tests/test_layer4_plan_refresh.py` | Modified | 9 new tests: `test_t3_maxitems_56` (TestToolSchema); 3 new T3 input-validation tests replacing the prior `test_t3_not_yet_implemented`; new TestT3IntraPhase class × 6. |
| 7 | `aidstation-sources/prompts/Layer4_RefreshT3_v1.md` | New | ~467 lines. Sixth post-arc prompt body. D1-D13 source decisions + §§1-14 sections matching the T1/T2/per-phase structure. |
| 8 | `aidstation-sources/prompts/Layer4_RefreshT1_v2.md` | New (carry-forward) | v1 retained as in-project history per Rule #12. Surgical edits: header v2 summary; D3 source-decision row; §3.5 (periodization shape re-grounded against freshly-re-run 3B); §3.8 (removed layer3b_payload not-passed line); `inherited_phase` → `current_phase` renamed throughout. |
| 9 | `aidstation-sources/Plan_Refresh_D64_Design_v1.md` | Modified (carry-forward) | §2 Decision 4 + §3.1 — T1 default cascade now includes 3B re-run per §4.3-wins amendment. Amendment-rationale block citing the validator-contract-vs-decision-surface conflation. |
| 10 | `aidstation-sources/Layer4_Spec.md` | Modified | §3.2 signature gains `plan_start_date: date \| None = None` keyword parameter; §3.2 parameter table gains corresponding row; §4.3 gains two new precondition rows (`plan_start_date_missing` + `tier_t3_cross_phase_requires_pattern_a`). |
| 11 | `aidstation-sources/Project_Backlog_v47.md` | New | Copy of v46 + file-revision-header bumped to v47 with Step 4d narrative; v46 demoted to first predecessor. No new D-rows. |
| 12 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 row → "Steps 4a + 4b + 4c + 4d of 8 COMPLETE"; Step 4b/c narrative compressed to predecessor entry; new Step 4d "Last shipped" narrative; Authoritative current files updated (Backlog v46 → v47; new `layer4/phase_structure.py` + `plan_refresh_t3.py` + `tests/test_layer4_phase_structure.py` + `Layer4_RefreshT3_v1.md` + `Layer4_RefreshT1_v2.md`); Next forward move recommends Step 4f Pattern A. |
| 13 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step4d_T3_PlanRefresh_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**13 files total. Over the 5-file ceiling intentionally** (precedent from Step 4b/c 10 + PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6 + PR-E 6 + Step 4a 8).

---

## 4. What `phase_structure.py` + `plan_refresh_t3.py` + updated `plan_refresh.py` commit to

### 4.1 `phase_structure_from_3b()` signature

```python
def phase_structure_from_3b(
    layer3b_payload: Layer3BPayload,
    plan_start_date: date,
    total_weeks: int | None = None,
) -> PhaseStructure:
    ...
```

Behavior per `Layer4_Spec.md` §6.1:
- Per-mode proportions applied to `total_weeks` for the phases the athlete still needs to traverse from `start_phase` onward.
- Custom mode uses `phase_weeks` verbatim.
- `start_phase != 'Base'`: earlier phases dropped; remaining phases re-normalize.
- Proportions round to whole weeks; remainder allocated to Base (or earliest remaining phase if Base skipped).
- Open-ended mode (`total_weeks=None`): defaults to 12 weeks per §6.1 v1 default.
- Returns a `PhaseStructure` with `phases` ordered Base→Build→Peak→Taper (subset starting from `start_phase`), `total_weeks` set, and `derived_from` reflecting the mode origin.
- Each `PhaseSpec.synthesis_metadata` is a `_zero_synthesis_metadata()` placeholder; orchestrator overwrites after per-phase synthesis.

### 4.2 `phase_for_date()` + `scope_spans_phase_boundary()` signatures

```python
def phase_for_date(
    phase_structure: PhaseStructure, target_date: date
) -> PhaseSpec | None:
    ...

def scope_spans_phase_boundary(
    phase_structure: PhaseStructure,
    scope_start: date,
    scope_end: date,
) -> bool:
    ...
```

`phase_for_date()` returns the `PhaseSpec` whose `[start_date, end_date]` contains `target_date`, or None when the date falls outside every phase's window. `scope_spans_phase_boundary()` returns True iff the scope straddles at least one phase boundary OR either endpoint falls outside the plan horizon (treated as cross-phase since the unseen-future-phase is different from any current phase).

### 4.3 Updated `llm_layer4_plan_refresh()` signature

```python
def llm_layer4_plan_refresh(
    user_id: int,
    tier: Literal['T1', 'T2', 'T3'],
    refresh_scope_start: date,
    refresh_scope_end: date,
    layer1_payload: dict[str, Any],
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    prior_plan_session_window: list[PlanSession],
    parsed_intent: ParsedIntent | None,
    plan_version_id: int,
    plan_version_id_parent: int,
    etl_version_set: dict[str, str],
    *,
    plan_start_date: date | None = None,    # NEW Step 4d
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str | None = None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    capped_retries: int = 2,
    extended_thinking_budget: int | None = None,
    llm_caller: LLMCaller | None = None,
) -> Layer4Payload:
    ...
```

Deviations from `Layer4_Spec.md` §3.2 (post-amendment):
1. `layer1_payload: dict[str, Any]` (not `Layer1Payload`) — Layer 1 typed schema out of v1 scope (PR-D precedent).
2. Added `plan_version_id_parent: int` positional parameter (Step 4b/c precedent).
3. Added `plan_start_date: date | None = None` keyword parameter (Step 4d amendment — required when tier='T3').

### 4.4 T3 algorithm (driver behavior)

1. **Validate inputs** per §4.3 — raises `Layer4InputError` on first failing precondition. T3-specific: `tier_scope_mismatch` (≤32 days) + `plan_start_date_missing`.
2. **Dispatch on tier** — T1/T2 unchanged from Step 4b/c. T3:
   - Compute `phase_structure_from_3b(layer3b_payload, plan_start_date)`.
   - Compute `scope_spans_phase_boundary(phase_structure, scope_start, scope_end)`. If True: raise `tier_t3_cross_phase_requires_pattern_a` (Step 4f surface).
   - Extract `dominant_phase_*` from `phase_for_date(scope_start)`.
3. **Load tier-specific defaults** — `max_tokens=10000`, `extended_thinking_budget=6500`. Build tool schema with `maxItems=56`.
4. **Build user prompt** via `plan_refresh_t3.render_user_prompt(..., dominant_phase_name=..., dominant_phase_start_date=..., dominant_phase_end_date=...)`.
5. **Invoke synthesizer** + parse + validate + capped retry — unchanged from T1/T2 driver flow.
6. **Compose Layer4Payload** with `mode='plan_refresh'`, `pattern='B'`, `phase_structure=None`, `seam_reviews=None`, per-session `phase_metadata=None`.

---

## 5. Next session pointers — Step 4e (queued behind D-66) or Step 4f (heaviest remaining)

**Architect-recommended next per `CLAUDE.md` "Next forward move":**

### Step 4f scope: `llm_layer4_plan_create` Pattern A orchestration

Step 4f is the heaviest remaining sub-step. It implements Pattern A:
- Per-phase synthesis loop (`Layer4_PerPhase_v1.md` per phase) — one LLM call per phase
- Seam-reviewer loop (`Layer4_SeamReviewer_v1.md` per adjacent-phase pair) — one LLM call per seam
- Cross-phase validator final pass
- Best-effort cap-hit semantics + propose-patch authority semantics per §6.2

Consumes `phase_structure_from_3b()` (now shipped via Step 4d). T3 cross-phase Pattern A lands here as a natural consumer of the same per-phase machinery; closes the `tier_t3_cross_phase_requires_pattern_a` raise path. ~6-8 files projected.

**Stop-and-ask risk:** High. Pattern A is the most architecturally complex surface in Layer 4. Triggers likely:
- Trigger #2 — none expected (per-phase + seam-reviewer prompt bodies already shipped)
- Trigger #5 — possible on seam-driven re-prompt budget interaction (validator retry vs seam re-prompt share a budget per §5.5 + §6.2)
- Trigger #8 — likely on per-phase synthesis concurrency (sequential by design per §5.2; ratify or revisit) + seam-review iteration cap interaction with validator retry cap

### Step 4e scope: `llm_layer4_race_week_brief`

Blocked until D-66 race-event data model design wave lands. Once D-66 lands, ~3-4 files projected. Consumes the already-shipped `Layer4_RaceWeekBrief_v1.md` prompt body.

### Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (Step 4d).
3. **Third re-read**: `Layer4_Spec.md` §5.2 (Pattern A algorithm), §5.5 (capped retry interaction), §6.1 (phase_structure_from_3b — now shipped; reference for Pattern A's per-phase loop), §6.2 (seam-driven re-prompt authority semantics), §6.5 (start_phase non-Base case).
4. **Fourth re-read**: `Layer4_PerPhase_v1.md` (per-phase prompt body) + `Layer4_SeamReviewer_v1.md` (seam-reviewer prompt body) + the Step 4d reference impl `layer4/plan_refresh_t3.py` + `phase_structure.py`.
5. **Branch**: cut a fresh branch off post-merge main; or stay on a harness pin per precedent.
6. **Test convention**: top-level `tests/test_layer4_plan_create.py` for Step 4f.
7. **Reuse pattern**: `layer4/plan_create.py` mirroring the shape of `plan_refresh.py` driver; `phase_structure_from_3b()` already shipped is the per-phase loop's anchor.

### Carry-forward edits expected for Step 4f (preliminary)

None mechanically-spec'd at this time. Step 4f's architectural picks will surface via AskUserQuestion as the session progresses.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Step 4d T3 + bundle §6.3 carry-forward | Andy 2026-05-17 | Picked from a 4-option scope question; bundles the §4.3-wins ripple into the same session. |
| 2 | New `Layer4_RefreshT3_v1.md` prompt body | Andy 2026-05-17 | Picked from a 4-option file-scope question; T3's mesocycle-reshape coaching surface doesn't fit T2's "match surrounding shape" framing. |
| 3 | Build named `phase_structure_from_3b()` helper now | Andy 2026-05-17 | Picked from a 3-option phase-detection question; reusable by Step 4f Pattern A. |
| 4 | `plan_start_date` plumbed through entry-point signature | Andy 2026-05-17 | Picked from a 4-option plumbing question; trigger #5 fires; routes through AskUserQuestion gate per the Step 4a/4b/c precedent. |
| 5 | T3 sampling defaults `max_tokens=10000` + `extended_thinking=6500` | Andy 2026-05-17 | Picked from a 4-option sampling question; generous for 4-week mesocycle reasoning. |
| 6 | T3 continuity = phase-trajectory-aware reshape | Andy 2026-05-17 | Picked from a 3-option continuity question; T3 reshape is mesocycle-internal; days 29-35 are soft continuity. |
| 7 | Cross-phase T3 raises `tier_t3_cross_phase_requires_pattern_a` | Architect-pick; spec-aligned | Per §5.1 + §6.3; Step 4f cross-phase Pattern A surface. |
| 8 | Open-ended-mode horizon defaults to 12 weeks | Architect-pick; spec-aligned | Per §6.1 v1 default; helper accepts `total_weeks` kwarg override for event-mode. |
| 9 | T1/T2/T3 dispatch unified via `extra_kwargs` dict | Architect-pick | Avoids changing T1/T2 `render_user_prompt()` signatures. |
| 10 | `_zero_synthesis_metadata()` placeholder at decomposition time | Architect-pick | `PhaseSpec.synthesis_metadata` required at pydantic level; orchestrator overwrites after per-phase synthesis. |

### 6.2 Stop-and-ask trigger retrospective

- **Triggers #2, #5, #8** fired and routed properly via the 4-question + 2-question + 2-question `AskUserQuestion` rounds (scope confirmation + T3 prompt body posture; phase detection + plan_start_date plumbing; T3 sampling + T3 continuity).
- **Trigger #11** did NOT fire — no new D-rows.

### 6.3 No carry-forward expected for Step 4f session

Step 4f's architectural picks will surface fresh via AskUserQuestion. The §6.3 carry-forward from Step 4b/c closed in this session; no new carry-forward bundle is queued.

### 6.4 Carried forward to Layer 1 typed payload (deferred)

- `Layer1Payload` is currently `dict[str, Any]` opaque pass-through across all 4 entry points. Lands as a typed pydantic model when the Layer 1 implementation arc begins.

### 6.5 Carried forward to typed `Layer3BPayload.time_to_event_weeks` field

- `phase_structure_from_3b()` accepts `total_weeks` as an explicit override kwarg; once `Layer3BPayload` gains a `time_to_event_weeks` field (event-mode horizon), the helper can default to that value internally instead of relying on caller plumbing. v1 deferred; not blocking Step 4d.

---

## 7. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/phase_structure.py` exists with `phase_structure_from_3b()` + `phase_for_date()` + `scope_spans_phase_boundary()` | ✅ inspection |
| `layer4/plan_refresh_t3.py` exists with `SYSTEM_PROMPT` + `DEFAULT_MAX_TOKENS=10000` + `DEFAULT_EXTENDED_THINKING_BUDGET=6500` + `render_user_prompt()` accepting `dominant_phase_*` kwargs | ✅ inspection |
| `layer4/plan_refresh.py` driver: T3 dispatch routes intra-phase to Pattern B + raises cross-phase | ✅ inspection |
| `build_record_refresh_sessions_tool('T3')` returns maxItems=56 | ✅ `test_t3_maxitems_56` passes |
| §4.3 preconditions: `plan_start_date_missing` raises when tier='T3' and plan_start_date=None | ✅ `test_t3_plan_start_date_missing_raises` passes |
| §4.3 preconditions: `tier_scope_mismatch` raises when T3 scope > 32 days | ✅ `test_t3_scope_too_long_raises` passes |
| §4.3 preconditions: `tier_t3_cross_phase_requires_pattern_a` raises on cross-phase scope | ✅ `test_t3_cross_phase_raises_pattern_a` passes |
| T3 intra-phase happy path returns Pattern B Layer4Payload | ✅ TestT3IntraPhase × 6 pass |
| `Layer4_RefreshT3_v1.md` exists | ✅ inspection |
| `Layer4_RefreshT1_v2.md` exists; v1 retained | ✅ inspection |
| `Plan_Refresh_D64_Design_v1.md` §2 Decision 4 + §3.1 carry-forward amendments applied | ✅ grep |
| `Layer4_Spec.md` §3.2 signature gains `plan_start_date` | ✅ grep |
| `Layer4_Spec.md` §4.3 gains `plan_start_date_missing` + `tier_t3_cross_phase_requires_pattern_a` precondition rows | ✅ grep |
| `layer4/__init__.py` re-exports 3 new symbols | ✅ grep |
| `tests/test_layer4_phase_structure.py` 24 tests, all green | ✅ `python -m pytest tests/test_layer4_phase_structure.py` |
| `tests/test_layer4_plan_refresh.py` 9 new tests, all green | ✅ `python -m pytest tests/test_layer4_plan_refresh.py` |
| Combined `tests/` 445 tests, all green in 0.57s | ✅ `python -m pytest tests/` |
| No regression in prior 412 tests | ✅ same 412 prior tests + 33 new = 445 |
| `Project_Backlog_v47.md` exists; file-revision-header is v47; v46 demoted inline | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v47.md` | ✅ grep |
| `CLAUDE.md` Layer 4 row mentions "Steps 4a + 4b + 4c + 4d of 8 COMPLETE" | ✅ grep |
| `CLAUDE.md` Last-shipped is Step 4d; Step 4b/c demoted to Predecessor | ✅ inspection |
| `CLAUDE.md` Next-forward-move recommends Step 4f (heaviest remaining) | ✅ inspection |
| Working tree shows 13 files modified / created | ✅ `git status` |
| Branch is `claude/implement-plan-refresh-closing-oJTxn` (harness-pinned) | ✅ |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; Step 4d is implementation-layer (no UI surface; no new §5.0 row needed).
- Step 4e race-week-brief — queued behind D-66 race-event data model design wave.
- Step 4f `plan_create` Pattern A orchestration — queued next session as the heaviest remaining; T3 cross-phase Pattern A naturally lands here.
- Step 5-8 (cache layer, Pattern A orchestration, live LLM integration, T3/auto-fire picks) — queued post-Step-4.
- v5 onboarding implementation PR — independent of Layer 4 implementation track; can run in parallel.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.

---

**End of handoff.**
