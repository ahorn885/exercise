# V5 Implementation — Layer 4 Step 3 PR-E Validator Harness Closing Handoff

**Session:** Single chat. Scope: Step 3 PR-E of `Layer4_Spec.md` §14.3.4 — new `layer4/validator.py` pure-function deterministic validator harness implementing 21 rule functions per the post-PR-C / post-PR-C-followon §5.4 table, with `ValidatorContext` bundling PR-D's 10 typed upstream payloads.
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step3_PR_D_Context_Schemas_Closing_Handoff_v1.md` (PR-D — typed upstream-layer context schemas; 50 tests; combined 209 green).
**Branch:** `claude/implement-context-schemas-zQkGJ` (harness-pinned for this session; name carried over from PR-D scoping even though this PR is PR-E — precedent: PR-A → PR-B → PR-C → PR-C-followon → PR-D all harness-pinned).
**Status:** 🟢 3 substantive code files + 3 bookkeeping. 96 new tests; combined `tests/` count 209 → 305, all green in 0.45s. **Layer 4 implementation Step 3 of 8 closes here entirely.** PR ready to open.

---

## 1. Session-start verification (Rule #9)

Predecessor (PR-D) handoff §7 claimed: `layer4/context.py` (~570 lines / ~55 types) on disk with 10 upstream-mirror types + 6 AccommodationModality variants + tagged-union dispatch + ExerciseRisk verdict-accommodations invariant + Layer2DPayload defensive partition + Layer2EHitlItem 9-field shape + Layer3B schema rules; `layer4/__init__.py` re-exports all 55 new types; `tests/test_layer4_context.py` 50 tests green; `Project_Backlog_v43.md` exists; CLAUDE.md Backlog ref reads v43; PR-D merge commit on `origin/main`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `layer4/context.py` exists with the 10 upstream-mirror types + 6 AccommodationModality variants | grep + line count | ✅ 864 lines / 64 classes (handoff said ~570/~55 — modest scale-up, no missing content) |
| `layer4/__init__.py` re-exports 55 new types | inspection | ✅ |
| `tests/test_layer4_context.py` 50 tests, combined `tests/` 209 green | `python -m pytest tests/` | ✅ 209 passed in 0.47s |
| `Project_Backlog_v43.md` exists | `ls` | ✅ |
| CLAUDE.md Backlog ref reads v43 | grep | ✅ line 72 |
| PR-D merge commit `5be9771` on `origin/main` | `git log` | ✅ |
| Working tree clean | `git status` | ✅ |
| Current branch `claude/implement-context-schemas-zQkGJ` (fresh-cut off post-merge main) | `git branch` | ✅ |

**No drift found.** PR-D state on disk matches the handoff narrative. Branch name `claude/implement-context-schemas-zQkGJ` is a harness pin from the original PR-D scoping; surfaced to Andy at session start; he confirmed the PR-E scope on that branch (mismatch on the record per the harness-name-vs-scope precedent established in PR-B / PR-C / PR-D).

---

## 2. Session narrative — Andy-confirmed scope; implementation-of-spec PR; no stop-and-ask triggers fired

Andy opened with a URL pointer to the PR-D closing handoff and "lets work." I followed §5 operating notes — re-read CLAUDE.md, ran Rule #9 verification, surfaced state + next focus + drift (none), surfaced the branch-name-vs-scope harness pin, asked Andy to confirm scope. Andy picked PR-E (architect-recommended).

### 2.1 Single-pass implementation against the spec

Read `Layer4_Spec.md` §5.4 (the 21-row rule table, the tolerance-defaults paragraph, the D-66/D-67/D-68 forward-pointer summary, and the new injury-accommodation-modality-framework subsection), §3.5 (errors), §7.9 (ValidatorResult + RuleFailure), §7.10 (Observation), §7.12 (schema-level rules — to confirm which invariants are pydantic-enforced + which the validator needs to defensively re-check). Read `layer4/context.py` (~865 lines) + `layer4/payload.py` §7.1-§7.14 to anchor field names + types + cross-field validators the rules read against. Read `tests/test_layer4_context.py` to inherit the fixture-helper patterns (factories, `model_validate_json` round-trips, etc.).

Wrote `layer4/validator.py` (~1370 lines). Wrote `layer4/__init__.py` adding 2 re-exports (`ValidatorContext` + `validate_layer4_payload`). Wrote `tests/test_layer4_validator.py` (96 tests). Combined `tests/` count: 209 → 305, all green in 0.45s.

### 2.2 No contract gaps surfaced

Per the predecessor PR-D handoff §5: "Stop-and-ask risk: Low. PR-D closes the typed-context surface; PR-E reads against the established types. If a rule's pseudo-code surfaces ambiguity not already resolved in PR-C or PR-C-followon, route through `/plan` mode." Confirmed in practice — none of the 21 rules surfaced a contract gap requiring spec amendment. Two pragmatic v1 choices that are documented inline (and called out below in §2.3) but did NOT require spec amendments because the spec acknowledges them via the v1 warning-severity-with-baseline-fuzziness framing.

### 2.3 Architectural choices on the record

- **`ValidatorContext` as frozen `@dataclass` not pydantic `BaseModel`** — internal-only struct, no untrusted JSON crossing this boundary. Dataclass is lighter, frozen-by-default prevents accidental mutation between passes. PR-A / PR-D set the pydantic-everywhere precedent at the payload-data boundary, but the validator's context bundle is a different layer of the stack (driver-internal struct).
- **`_ALL_RULES` as tuple constant rather than decorator registry** — 21 rules, simpler + IDE-friendly. No metaprogramming complexity for what's effectively a static list. New rules added by appending to the tuple.
- **Rule 5 (`two_per_day`) implemented defensively despite Layer4Payload pydantic `_check_two_per_day` enforcing the same invariants at construction** — load-bearing for the `model_construct` bypass + downstream-injection case (when sessions are inserted into a payload post-construction). The §5.4 rule re-runs the same checks; on a properly-constructed Layer4Payload it always returns []. The test surface includes a `model_construct`-bypass case to exercise the rule positively.
- **Rule 4 (`intensity_dist`) adds a v1 3-hour-minimum-per-phase threshold not in the spec** — distribution comparison is statistically meaningless for thin data (a single 1-hour Z2 session would otherwise fire as 100% Z1-Z2 vs intended 80%). Pragmatic v1 default; documented inline; v2 may revisit.
- **Driver returns `retried_phase_names=[]` always** — orchestrator owns the retry decision per §5.5. The validator is stateless and reports only what failed in this pass.
- **`_check_modality` helper centralizes per-AccommodationModality dispatch** via `isinstance` branches against the 6 typed variants. Concrete pydantic instances after upstream construction; isinstance is the clean dispatch primitive (alternative: match on `.modality_type` literal — equivalent semantics, isinstance is slightly more typesafe).
- **`_zone_bucket` collapses `mixed` cardio zone into `Z3`** — single-mode bucket assignment matches the §5.4 `intended_intensity_distribution` key convention (Z1-Z2 / Z3 / Z4-Z5). Z3 is the natural midpoint for "mixed" which typically means tempo or threshold work.
- **`injury_accommodation_violation_*` v1 baseline sentinels are conservative hardcoded constants** — `_BASELINE_STRENGTH_VOLUME_REPS = 40` (4 sets × 10 reps), `_BASELINE_CARDIO_DURATION_MIN = 60`, `_BASELINE_PCT_1RM = 80.0`, `_BASELINE_RPE_MIDPOINT = 8.0`, `_BASELINE_FREQUENCY_SESSIONS_PER_WEEK = 3`. Chosen to catch egregious violations while tolerating LLM baseline drift. The spec acknowledges this fuzziness explicitly at line 933 — severity is `warning` not `blocker` in v1; v2 may calibrate from measured retry rates.
- **`loading_type_change` enforcement silently skipped in v1** — `ResolvedExercise` lacks implement/laterality metadata needed to enforce per spec line 929. v2 lands when 2C extends `ResolvedExercise` with the metadata (D-70-adjacent work).
- **`tempo_modification.isometric_only` matching uses substring check (`iso` / `isometric` in tempo string)** since the spec doesn't define a canonical isometric tempo notation. v2 may tighten to a specific notation (e.g., `iso-Ns`).
- **Mode-gating per spec** — rules 1/2/4/19 (volume / acwr / intensity_dist / phase_date) skip when `mode=='single_session_synthesize'`; rules 14-18 (taper / kit / race_plan / fueling / contingency) skip when `mode != 'race_week_brief'`. Implemented as the first guard in each affected rule function.
- **Missing-input policy — soft skip** when a required upstream payload is None. Rules NEVER raise; caller is expected to attach `Observation(category='data_gap')` at the payload level. Matches the PR-C settled policy.

### 2.4 Stop-and-ask triggers — none fired

- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire. No spec amendments; the v1 baseline sentinels are internal-only and documented inline. The pragmatic 3-hour minimum threshold on `_rule_intensity_dist` is also internal-only — it's a v1 default for thin-data robustness, not a contract change.
- **Trigger #11 (new cross-layer D-rows):** did NOT fire. No new D-rows; existing D-66/D-67/D-68 (PR-C) + D-69/D-70/D-71 (PR-C-followon) cover all forward-pointer cases the validator's D-67-aware branches need.
- Other triggers — none applicable.

### 2.5 Scope NOT changed this session

- **Step 4a `llm_layer4_single_session_synthesize` (D-63 caller)** — queued next. The Pattern B Claude-API call site wiring + tool-use schema + parse-validate-retry loop + 2-retry cap. Now ready since payload schema (PR-A) + canonical-JSON cache keys (PR-B) + context schemas (PR-D) + validator harness (PR-E) are all closed.
- **D-70 / D-71** — not touched. ROM modality + tendinopathy phase-sequencing remain Deferred v2.
- **D-66 / D-67** — not touched. v1 validator harness D-66/D-67-aware branches no-op against always-empty input until the design waves ship.

---

## 3. Files shipped this session

One commit on `claude/implement-context-schemas-zQkGJ` — 3 substantive code + 3 bookkeeping bundled (precedented by PR-A 8-file + PR-B 7-file + PR-C 4-file + PR-C-followon 6-file + PR-D 6-file bundles).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `layer4/validator.py` | New | ~1370 lines. `ValidatorContext` frozen dataclass + 21 `_rule_*` functions + `_ALL_RULES` tuple registry + `validate_layer4_payload` driver. All 21 rules from the §5.4 table post-PR-C / post-PR-C-followon; mode-gating + missing-input policy + D-67-aware no-op branches honored. |
| 2 | `layer4/__init__.py` | Modified | 2 re-exports added (`ValidatorContext`, `validate_layer4_payload`) alongside existing 32 payload + 9 hashing + 55 context exports. |
| 3 | `tests/test_layer4_validator.py` | New | 96 tests, all green. Coverage: ValidatorContext × 3 (defaults / payload-bound / frozen-rejects-mutation) + driver × 6 (empty accepted / pass_index / accepted=False on blocker / accepted=True with warnings / multi-rule aggregation / retried_phase_names empty) + per-rule × 21 (happy-path + blocker/warning case + mode-gated/missing-input skip × ~3 each) + per-AccommodationModality × 13 (all 6 variants × happy + violation cases + loading_type_change v1-skipped sentinel + frequency cap-vs-factor + substitution-covered-by-injury_violation) + mode-gating × 4 + parametrized boundary × 2 (volume_band 8 cases + injury_accommodation_volume 6 cases). |
| 4 | `aidstation-sources/Project_Backlog_v44.md` | New | Copy of v43 + new v44 file-revision-header narrative; no new D-rows (PR-E doesn't surface any). v43 demoted to first predecessor. |
| 5 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 pipeline row updated to "SPEC + IMPLEMENTATION Step 3 of 8 COMPLETE"; last-shipped narrative replaced with this session's summary (PR-D demoted to predecessor); Backlog ref v43 → v44; authoritative-current-files Layer 4 implementation line extended with `layer4/validator.py` + `tests/test_layer4_validator.py`; Next-forward-move recommends Step 4a single-session integration. |
| 6 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step3_PR_E_Validator_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**6 files total. Over the 5-file ceiling intentionally** (Andy explicit precedent from PR-A 8 + PR-B 7 + PR-C-followon 6 + PR-D 6).

---

## 4. What `layer4/validator.py` now commits to

### 4.1 ValidatorContext

```python
@dataclass(frozen=True)
class ValidatorContext:
    layer2a_payload: Layer2APayload | None = None
    layer2b_payload: Layer2BPayload | None = None
    layer2c_payloads: dict[str, Layer2CPayload] = field(default_factory=dict)
    layer2d_payload: Layer2DPayload | None = None
    layer2e_payload: Layer2EPayload | None = None
    layer3a_payload: Layer3APayload | None = None
    layer3b_payload: Layer3BPayload | None = None
    daily_availability_windows: tuple[DailyAvailabilityWindow, ...] = ()
    race_event: RaceEventStub | None = None
    per_date_restrictions: tuple[PerDateRestriction, ...] = ()
    prior_session_loads_by_date: dict[date, float] | None = None
```

Every field optional. Different entry-point modes populate different subsets. Rules whose required payload is None no-op silently. `layer2c_payloads` keys form the implicit "athlete locale cluster" set for rule 6c. `per_date_restrictions` is always empty in v1 (D-67 deferred); D-67-aware rule branches no-op against empty input. `prior_session_loads_by_date` provides trailing-window historical data for ACWR (rule 2); when None, ACWR rule emits no failures.

### 4.2 21 rule functions

Listed in order of execution per `_ALL_RULES`:

1. `_rule_volume_band` — per (ISO week, discipline, phase): actual hours vs 2A `phase_load_bands`. ±20% blocker / ±10% warning per spec line 890.
2. `_rule_acwr` — trailing-7d acute / trailing-28d chronic average per Gabbett 2016. Blocker outside 0.7-1.4; warning outside 0.8-1.3 per spec line 891.
3. `_rule_rest_spacing` — no two consecutive hard sessions per discipline without `overreach_test` / `race_rehearsal` exempt flag. Blocker.
4. `_rule_intensity_dist` — per-phase Z1-Z2 / Z3 / Z4-Z5 zone-bucket distribution within ±10pp of `intended_intensity_distribution`. Warning. (v1: 3-hour-minimum phase threshold for statistical sanity.)
5. `_rule_two_per_day` — defensive idempotent of Layer4Payload pydantic invariants. Blocker (covers `model_construct` bypass).
6. `_rule_equipment_unavailable` (6a) — strength exercise_id ∈ Layer2CPayload.effective_pool ∪ exercises_resolved at session.locale_id. Blocker.
7. `_rule_session_multi_locale` (6b) — defensive: detect sessions where NO prescribed exercise resolves at locale_id (degenerate split-locale edge). Blocker.
8. `_rule_session_locale_not_in_cluster` (6c) — locale_id ∈ keys(layer2c_payloads). Blocker. +D-67 `locale_lock` branch (no-op in v1).
9. `_rule_injury_violation` — exercise_id ∉ Layer2DPayload.excluded_exercises[].exercise_id set. Blocker. Per PR-C-followon §5.4 rewrite.
10. `_rule_injury_accommodation_violation` — dispatches on AccommodationModality discriminated union; v1 baseline-sentinel checks per variant; severity warning per spec line 933.
11. `_rule_schedule_violation` — sessions on `enabled=False` days unless coaching_flags contains `athlete_self_scheduled`. Blocker.
12. `_rule_discipline_excluded` — in 2A `inclusion=='included'` set. Blocker. +D-67 per-date `discipline_exclusions` branch (no-op in v1).
13. `_rule_sport_locale_incompatible` — Layer2CPayload.discipline_coverage has total_exercises>0 AND coverage_pct>0 for session.discipline_id. Blocker.
14. `_rule_taper_phase_intent_violation` — race_week_brief mode only. intensity_summary=='hard' ≤ 2d to event blocker; duration_min>90 ≤ 2d to event blocker.
15. `_rule_kit_manifest_inputs_incomplete` — race_week_brief mode + race_format ≠ 'single_day' → always-warns per spec pre-D-66.
16. `_rule_race_plan_segments_unordered` — segments[].estimated_start_offset_hr monotonicity. Blocker. (segment_index monotonicity already enforced at pydantic construction.)
17. `_rule_fueling_strategy_2e_tier_mismatch` — RacePlan.fueling_strategy.cho/sodium/fluid within 2E RaceDayFueling tier bands matched by event_name. Blocker per band.
18. `_rule_contingency_anchor_category_missing` — per race_format required anchor categories (single_day: gi/hydration/mechanical; multi_day_ultra +cumulative_fatigue; expedition_ar +nav/sleep_dep/weather; stage_race +between_stage_recovery). Substring matching in contingencies haystack. Warning.
19. `_rule_phase_date_out_of_range` — session.date within `phase_structure.phases[].(start_date, end_date)` for session.phase_metadata.phase_name. Blocker.
20. `_rule_daily_window_fit` — per-date duration sum ≤ enabled DailyAvailabilityWindow window_duration+second_window_duration sum. Blocker. +D-67 `max_total_minutes` branch.
21. `_rule_indoor_only_violation` — D-67 indoor_only=True dates require non-outdoor discipline (outdoor-only set: trail_running, outdoor_rock_climbing, packrafting, abseiling, mtb_outdoor, etc.). Blocker. Locale-category half of the rule skipped pending Layer2CPayload category metadata in v2.

### 4.3 Driver

```python
def validate_layer4_payload(
    payload: Layer4Payload,
    context: ValidatorContext,
    pass_index: int = 0,
) -> ValidatorResult:
    ...
```

Iterates `_ALL_RULES`, aggregates RuleFailures; `accepted=False` iff any blocker-severity failure; warnings do not block acceptance. `retried_phase_names=[]` always — orchestrator owns the retry decision per §5.5. Stateless; no I/O.

### 4.4 Module-level constants

- `_INDOOR_LOCALE_CATEGORIES` — frozen set of 8 per-spec indoor categories used by rule 21.
- `_OUTDOOR_ONLY_DISCIPLINES` — frozen set of 13 outdoor-only discipline names (mtb_outdoor, trail_running, outdoor_rock_climbing, packrafting, abseiling, outdoor_road_cycling, outdoor_gravel_cycling, skimo, ski_tour, marathon_canoe, open_water_swim, kayak_outdoor, sup_outdoor) used by rule 21.
- `_CONTINGENCY_ANCHORS_PER_FORMAT` — dict mapping race_format → required anchor categories per rule 18 D6 mixed-contingency anchor table from `Layer4_RaceWeekBrief_v1.md`.
- v1 baseline sentinels for `injury_accommodation_violation_*` — 40 reps strength volume, 60 min cardio, 80%1RM, RPE 8 midpoint, 3 sessions/week. Documented inline as conservative; severity = warning per spec.

---

## 5. Next session pointers — Step 4a single-session integration

**Architect-recommended next per `CLAUDE.md` "Next forward move":**

### Step 4a scope: `llm_layer4_single_session_synthesize` (D-63 caller; Pattern B; 4-5 files projected; ~40-60 tests)

New code (likely `layer4/single_session.py` or extension of `coaching.py`) with:
- Claude API client integration (Anthropic SDK; reuse `coaching.py` patterns where possible)
- `record_single_session` tool-use schema definition (per `Layer4_SingleSession_v1.md` §3 D1)
- Input validation per `Layer4_Spec.md` §4.4 (precondition checks including the new `request_sport_unavailable_at_locale` precondition from PR-C)
- Layer4Payload construction from synthesizer output (`mode='single_session_synthesize'`, `pattern='B'`, `len(sessions)==1`, `is_ad_hoc=True`)
- `ValidatorContext` construction (Layer 2C for the picked locale + Layer 2D + Layer 3A + DailyAvailabilityWindow)
- Validator harness invocation (`validate_layer4_payload(payload, ctx, pass_index=0)`)
- 2-retry cap per §5.5 capped-retry semantics with RuleFailure context fed back into the retry prompt
- Observation emission for sport_unavailable_at_locale / off_plan_day_note / intensity_modulated per §8.7
- Cache lookup via `single_session_synthesize_key` (shipped in PR-B `layer4/hashing.py`); cache hit returns cached payload with `plan_version_id` + `suggestion_id` rebound per §9.4

Plus `tests/test_layer4_single_session.py` (~40-60 tests — happy-path per discipline × 3-4 + validator-retry × 2 + cache-hit × 2 + sport-unavailable precondition × 1 + cap-hit best-effort × 1).

**Stop-and-ask risk:** Low-medium. The prompt body is shipped and the spec contracts are closed. Risk surfaces if the actual LLM tool-use output deviates from the §7 schema in ways pydantic can't recover from — but that's a runtime tuning concern, not a spec amendment.

### Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (PR-E).
3. **Third re-read**: `Layer4_Spec.md` §3.3 (single_session function signature) + §4.4 (input validation preconditions) + §5.3 (Pattern B algorithm) + §5.5 (capped retry semantics) + §8.7 (call-level observations) + §9.1 (single_session_synthesize_key cache formula) + §9.4 (rebinding semantics).
4. **Fourth re-read**: `aidstation-sources/prompts/Layer4_SingleSession_v1.md` (the prompt body) + `layer4/payload.py` + `layer4/context.py` + `layer4/validator.py`.
5. **Branch**: cut a fresh branch off post-merge main; or stay on `claude/implement-context-schemas-zQkGJ` per harness pinning.
6. **Test convention**: top-level `tests/test_layer4_single_session.py` alongside the existing `test_layer4_*` tests.
7. **Claude API integration**: reuse `coaching.py` patterns (Anthropic SDK setup, prompt caching, extended thinking budgets); D2 spec calls for extended_thinking ~3500 tokens.
8. **Stop-and-ask trigger #5**: contract surface is closed; if the LLM tool-use output surfaces a schema gap that requires loosening Layer4Payload's `extra='forbid'` or other invariants, route through `/plan` mode.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Step 3 PR-E validator harness (architect-recommended) | Andy 2026-05-17 | Picked from 3-option scope question; PR-E was queued next per the PR-D §5 forward-pointer + CLAUDE.md "Next forward move". |
| 2 | `ValidatorContext` as frozen `@dataclass` (not pydantic BaseModel) | Architect-pick | Internal-only struct; no untrusted JSON crossing this boundary; dataclass is lighter; frozen prevents accidental mutation between passes. |
| 3 | `_ALL_RULES` as tuple constant (not decorator registry) | Architect-pick | 21 rules; simpler + IDE-friendly; no metaprogramming complexity. |
| 4 | Rule 5 (`two_per_day`) implemented defensively despite pydantic enforcement | Architect-pick | Load-bearing for the `model_construct` bypass + downstream-injection case; the spec lists it as a §5.4 rule independently of the schema-level invariants in §7.12. |
| 5 | Rule 4 (`intensity_dist`) v1 3-hour-minimum threshold | Architect-pick | Pragmatic v1 default for statistical sanity on thin data; documented inline; not in spec but doesn't change contract; v2 may revisit. |
| 6 | `_check_modality` v1 baseline sentinels (40 reps / 60 min / 80%1RM / RPE 8 / 3 sessions/week) | Architect-pick; spec-aligned | Spec acknowledges baseline fuzziness at line 933 (severity = warning not blocker for v1); sentinels chosen conservatively to catch egregious violations; v2 may calibrate from measured retry rates. |
| 7 | `loading_type_change` enforcement silently skipped in v1 | Architect-pick | ResolvedExercise lacks implement/laterality metadata per spec; D-70-adjacent v2 work. |
| 8 | `tempo_modification.isometric_only` substring matching | Architect-pick | Spec doesn't define a canonical isometric notation; substring check (`iso` / `isometric` in tempo) is a defensible v1 heuristic; v2 may tighten. |
| 9 | Driver returns `retried_phase_names=[]` always | Architect-pick; spec-aligned | §5.5 places retry decisions on the orchestrator; the validator is stateless. |
| 10 | Bookkeeping bundled into this session (6 files) | Continues PR-A → PR-B → PR-C → PR-C-followon → PR-D precedent | 6 files total; over ceiling by 1; precedented. |

### 6.2 Stop-and-ask trigger retrospective

- **Trigger #5 did NOT fire this session** — implementation-of-spec; no contract changes. The v1 baseline sentinels are internal-only; the 3-hour minimum threshold on `_rule_intensity_dist` is a pragmatic v1 default for thin-data robustness; neither modifies a spec contract.
- **Trigger #11 did NOT fire** — no new D-rows; existing D-66/D-67/D-68/D-70/D-71 cover all forward-pointer cases.
- Other triggers — none applicable.

### 6.3 Carried forward to Step 4a single-session integration

- **`ValidatorContext` construction in Step 4a**: caller bundles Layer 2C (picked locale only) + Layer 2D + Layer 3A + DailyAvailabilityWindow; Layer 2B / 2E / 3B / RaceEventStub / per_date_restrictions can be None.
- **Cache key**: `single_session_synthesize_key` from `layer4/hashing.py` (PR-B).
- **Capped-retry semantics**: Step 4a wires the 2-retry cap per §5.5; on cap-hit, latest synthesis is accepted with `cap_hit=True` + `Observation(category='best_effort_plan')`.
- **Mode-gating in validator**: rules 1/2/4/19 already skip when `mode=='single_session_synthesize'`; Step 4a doesn't need additional guard logic.

### 6.4 Carried forward to D-66 / D-67 / D-70 / D-71 design waves

- **D-66 design wave** — race-event data model. Rule `kit_manifest_inputs_incomplete` continues to always-warn until D-66 ships per spec.
- **D-67 design wave** — per-date athlete restrictions. 4 D-67-aware rule branches (locale_lock / per-date discipline exclusions / max_total_minutes / indoor_only) activate when restrictions are populated.
- **D-68 design wave** — default equipment profiles per locale category. Layer 2C fallback resolution softens `equipment_unavailable_*` on travel paths.
- **D-70 design wave** — ROM modality. AccommodationModality typed union gains a `range_of_motion_restriction` variant; validator gains a new sub-branch in `_check_modality`.
- **D-71 design wave** — phase-sequencing for tendinopathy progression. 2D emits modality sequences; validator dispatches on current-phase modality only (sequencing implicit via T1 refresh + 3A re-assessment).
- **`loading_type_change` validator enforcement** — currently silently skipped; lands when ResolvedExercise gets implement/laterality metadata (D-70-adjacent).

---

## 7. Session-end verification (Rule #10)

Final pass before committing:

| Check | Result |
|---|---|
| `layer4/validator.py` exists with `ValidatorContext` + 21 `_rule_*` functions + `_ALL_RULES` tuple + `validate_layer4_payload` driver | ✅ inspection |
| All 21 rules covered: volume_band / acwr / rest_spacing / intensity_dist / two_per_day / equipment_unavailable (6a) / session_multi_locale (6b) / session_locale_not_in_cluster (6c) / injury_violation / injury_accommodation_violation / schedule_violation / discipline_excluded / sport_locale_incompatible / taper_phase_intent_violation / kit_manifest_inputs_incomplete / race_plan_segments_unordered / fueling_strategy_2e_tier_mismatch / contingency_anchor_category_missing / phase_date_out_of_range / daily_window_fit / indoor_only_violation | ✅ inspection of `_ALL_RULES` |
| Driver `validate_layer4_payload` returns `ValidatorResult` with `accepted=False` iff any blocker-severity failure | ✅ test_driver_accepted_false_on_blocker passes |
| `retried_phase_names=[]` always | ✅ test_driver_retried_phase_names_always_empty passes |
| Mode-gating: rules 1/2/4/19 skip when mode=='single_session_synthesize' | ✅ test_mode_gate_single_session_skips_volume_acwr_intensity passes |
| Missing-input policy: rules NEVER raise; soft-skip when upstream payload None | ✅ test_*_skipped_without_2* / test_*_skipped_when_no_* pass |
| Per-AccommodationModality compliance dispatches correctly via isinstance | ✅ 13 test_accommodation_* tests pass (all 6 variants covered) |
| D-67-aware branches no-op against empty per_date_restrictions | ✅ test_session_locale_lock_d67_empty_no_fire + test_indoor_only_no_restrictions_no_fire pass |
| D-67-aware branches activate when restrictions populated | ✅ test_session_locale_lock_d67_violation + test_discipline_excluded_d67_per_date_blocker + test_daily_window_fit_d67_max_total_minutes_blocker + test_indoor_only_violation_outdoor_discipline_blocker pass |
| `layer4/__init__.py` re-exports `ValidatorContext` + `validate_layer4_payload` alongside existing 32 payload + 9 hashing + 55 context exports | ✅ grep `__all__` |
| `tests/test_layer4_validator.py` 96 tests, all green | ✅ `python -m pytest tests/test_layer4_validator.py` |
| Combined `tests/` (test_layer4_payload + test_layer4_hashing + test_layer4_context + test_layer4_validator) = 305 tests, all green | ✅ `python -m pytest tests/` 0.45s |
| No regression in PR-A + PR-B + PR-C-followon + PR-D work | ✅ same 209 prior tests + 96 new = 305 |
| `Project_Backlog_v44.md` exists; file-revision-header is v44; v43 inline-demoted | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v44.md` | ✅ grep |
| `CLAUDE.md` Layer 4 row mentions "SPEC + IMPLEMENTATION Step 3 of 8 COMPLETE" | ✅ grep |
| `CLAUDE.md` Last-shipped is PR-E; PR-D demoted to first Predecessor | ✅ inspection |
| `CLAUDE.md` Next-forward-move recommends Step 4a single-session integration | ✅ grep |
| Working tree shows 6 files modified / created | ✅ `git status` |
| Branch is `claude/implement-context-schemas-zQkGJ` (harness-pinned) | ✅ |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; PR-E is implementation-layer (no UI surface; no new §5.0 row needed).
- Step 4a `llm_layer4_single_session_synthesize` (D-63) — queued next session against the now-complete payload + context + validator surfaces.
- Step 4b-4f (other 3 entry-point call sites: plan_create, plan_refresh, race_week_brief) — queued after Step 4a per §14.3.4 sequencing.
- Step 5-8 (cache layer, Pattern A orchestration, live LLM integration, T3/auto-fire picks) — queued post-Step-4.
- v5 onboarding implementation PR — independent of Layer 4 implementation track; can run in parallel.
- D-50 wiring resumption — now unblocked by D-58; can run in parallel.

---

**End of handoff.**
