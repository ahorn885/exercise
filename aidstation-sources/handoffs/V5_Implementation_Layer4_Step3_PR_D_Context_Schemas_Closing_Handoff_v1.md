# V5 Implementation — Layer 4 Step 3 PR-D Context Schemas Closing Handoff

**Session:** Single chat. Scope: Step 3 PR-D of `Layer4_Spec.md` §14.3.4 — new `layer4/context.py` typed pydantic v2 mirrors of the 7 upstream-layer §7 contracts + onboarding §G.1 daily-window + 2 D-66/D-67 forward-pointer placeholders that Layer 4's §5.4 validator harness consumes. Mirrors the AMENDED 2D + 2C specs from PR-C-followon (AccommodationModality typed union + `accommodated_exercises` rename + `ResolvedExercise.accommodations` propagation).
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_PR_C_Followon_Injury_Accommodation_Modality_Foundation_Closing_Handoff_v1.md` (PR-C-followon — injury-accommodation modality foundation amendment to Layer 2D §5.3 + §7, Layer 2C §5 + §7, Layer 4 §3.2 + §5.4; D-69/D-70/D-71 backlog rows).
**Branch:** `claude/injury-accommodation-modality-BPYOC` (harness-pinned for this session; name carried over from PR-C-followon's modality theme even though this PR is the context-schema follow-on rather than another modality amendment; precedent: PR-A → PR-B → PR-C → PR-C-followon all harness-pinned).
**Status:** 🟢 3 substantive code files + 3 bookkeeping. 50 new tests; combined `tests/` count 159 → 209, all green. PR ready to open.

---

## 1. Session-start verification (Rule #9)

Predecessor (PR-C-followon) handoff §7 claimed: `Layer2D_Spec.md` §5.3.4 maps to ACCOMMODATE + §5.3.6 6-modality framework + §7 AccommodationModality typed union + ExerciseRisk.accommodations + Layer2DPayload.accommodated_exercises rename; `Layer2C_Spec.md` §5.6 pass-through + §5.7 renumbered + §7 ResolvedExercise.accommodations field; `Layer4_Spec.md` §3.2 line 753 `injury_data_inconsistent` 2D-references + §5.4 `injury_violation_*` set-membership rewrite + NEW `injury_accommodation_violation_*` rule + §5.4 modality-framework summary block + §13.4 wrist-injury edge-case rewrite; `Project_Backlog_v42.md` D-69 ✅ + D-70 🟡 + D-71 🟡; `CLAUDE.md` Backlog ref v42 + last-shipped is PR-C-followon; 159 pytest cases pass; PR-C-followon merge commit `ed1cc73` on `origin/main`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `Layer2D_Spec.md` §5.3.4 ACCOMMODATE mapping | grep | ✅ lines 259-262 |
| `Layer2D_Spec.md` §5.3.6 + 6-modality framework | grep | ✅ lines 302-443 |
| `Layer2D_Spec.md` §7 AccommodationModality typed union + ExerciseRisk.accommodations + Layer2DPayload.accommodated_exercises | grep | ✅ lines 678, 699, 713, 785 |
| `Layer2C_Spec.md` §5.6 pass-through + ResolvedExercise.accommodations | grep | ✅ lines 207, 294 |
| `Layer4_Spec.md` §3.2 line 753 `injury_data_inconsistent` references 2D | grep | ✅ |
| `Layer4_Spec.md` §5.4 `injury_violation_*` set-membership rewrite | grep | ✅ line 898 |
| `Layer4_Spec.md` §5.4 NEW `injury_accommodation_violation_*` rule | grep | ✅ line 899 |
| `Layer4_Spec.md` §5.4 modality-framework summary block | grep | ✅ line 925 |
| `Layer4_Spec.md` §13.4 wrist-injury edge-case rewrite | grep | ✅ line 1373 |
| `Project_Backlog_v42.md` D-69 ✅ + D-70 🟡 + D-71 🟡 | grep | ✅ lines 145-147 |
| `CLAUDE.md` Backlog ref reads v42 + last-shipped is PR-C-followon | grep | ✅ |
| 159 pytest cases pass | `python -m pytest tests/` | ✅ 0.33s |
| Working tree clean | `git status` | ✅ |
| PR-C-followon merge commit on origin/main | `git log` | ✅ `ed1cc73` |
| No drift between handoff narrative and on-disk state | Rule #9 reconciliation | ✅ |

**No drift found.** PR-C-followon state on disk matches the handoff narrative exactly. Fresh branch cut off post-merge main.

---

## 2. Session narrative — Andy-confirmed scope; one contract gap surfaced + closed in-session

Andy opened with a URL pointer to the PR-C-followon closing handoff and "lets work". I followed §5 operating notes — re-read CLAUDE.md, ran Rule #9 verification, surfaced state + next focus + drift (none), asked Andy to confirm scope. Andy picked Step 3 PR-D (architect-recommended).

### 2.1 Single-pass implementation against the spec contracts

Read `layer4/payload.py` to anchor the established pydantic v2 conventions (`_Base` with `model_config = ConfigDict(extra='forbid')`, `Literal` for closed enums, `model_validator(mode='after')` for cross-field invariants, smart-union dispatch where shape-discriminates). Read §7 of all 7 upstream specs (Layer 2A + 2B + 2C + 2D + 2E + 3A + 3B) + §G.1 of `Athlete_Onboarding_Data_Spec_v5.md` to extract the verbatim type shapes the new `context.py` mirrors.

Wrote `layer4/context.py` (~570 lines, ~55 types). Wrote `layer4/__init__.py` adding 55 re-exports for the new types. Wrote `tests/test_layer4_context.py` (50 tests, matching the handoff §5 projection of ~50). Combined `tests/` count: 159 → 209, all green in 0.32s.

### 2.2 Contract gap surfaced: Layer2EHitlItem shape (closed in-session)

Per the predecessor handoff §5 forward-pointer "Stop-and-ask risk: Low. If a NEW gap surfaces, surface via `/plan` mode" — first draft of `context.py` made a reasonable guess at `Layer2EHitlItem` (the spec's §7 only declares the field `hitl_items: list[Layer2EHitlItem]` without inline class definition near the top of §7). A late-pass cross-reference against `Layer2E_Spec.md` line 810 surfaced the actual class shape (which lives further down in §7):

```python
@dataclass
class Layer2EHitlItem:
    item_id: str
    gate_number: int                    # 1–5 per table above
    block_level: str                    # 'block' (others may be added in v2)
    affected_supplement_id: str | None
    affected_event_id: str | None
    affected_condition_category: str | None
    rationale_for_athlete: str
    rationale_for_layer3: str
    resolution_options: list[str]
```

Updated `context.py` Layer2EHitlItem to the spec-accurate shape. Not a `/plan`-mode candidate — this was implementation-fidelity drift (I'd misread §7 by stopping at the field declaration), not a contract amendment. Surfaced for the record.

### 2.3 Architectural choices on the record

- **`AccommodationModality` as tagged-union (not smart-union)** — the modality_type literal field makes the tagged-union pattern idiomatic. `IntensityTarget` (in `payload.py`) uses smart-union because it has no discriminator field; the modality case has one, so `Annotated[Union[...], Field(discriminator='modality_type')]` is cleaner. Smart-union would also work but is slower (it tries each variant).
- **Per-modality bounds enforced at the leaf model** — VolumeReductionModality.factor (0.3-1.0), IntensityReductionModality.factor (0.4-1.0), TempoModificationModality.hold_s (15-60) + intensity_pct_mvc (30-100), FrequencyReductionModality factor (0.0-1.0) — all from `Layer2D_Spec.md` §5.3.6.1 evidence ranges. Bounds are physical-sanity not domain-policy; domain rules (e.g., "isometric_only hold ≥30s for analgesia") would live in §5.4 validator harness.
- **`Layer2DHitlItem.injury` + `.condition` typed `dict[str, Any]`** — InjuryRecord + HealthConditionRecord are Layer 1 / onboarding contracts. Layer 4 doesn't read into those structures (Layer 4 reads `excluded_exercises[].exercise_id` + `accommodated_exercises[].accommodations` + HITL-block-status; HITL routes through Layer 3.5 gates). Opaque dict avoids pulling Layer 1 onboarding types into Layer 4's typing surface; v2 may type these explicitly if Layer 4 starts consuming the structured form.
- **`Layer3Observation` shared between 3A + 3B** — both specs define identical shape (4-element category enum + text ≤ 240 chars + evidence_basis + elevates_to_hitl). Single type with both consumers. The Layer 4 output `Observation` in `payload.py` has a broader category enum (10 vs 4) and is its own type for the Layer 4 output side.
- **`ExerciseRisk._check_verdict_accommodations`** — enforces §5.3.6 invariant: accommodations non-empty iff verdict='accommodate'. Empty for verdict='exclude' or 'clean'. This is the load-bearing structural enforcement of the modality framework's verdict-to-modality contract.
- **`Layer2DPayload._check_excluded_verdict`** — defensive: every ExerciseRisk parked in `excluded_exercises` carries verdict='exclude'; every one in `accommodated_exercises` carries verdict='accommodate'. Synthesizer drift (putting an accommodated risk in excluded list, or vice versa) raises at construction.
- **`DailyAvailabilityWindow._check_enabled_invariants` + `_check_second_window_pair`** — §G.1: if disabled, window fields must be absent; primary window required if enabled; second window must be jointly-set or jointly-null; second window requires `doubles_feasible != 'no'`.
- **`GoalViability._check_adjustments`** + **`PeriodizationShape._check_phase_weeks`** + **`Layer3BPayload._check_hitl_unique_labels`** — verbatim §7 schema-rule enforcement from `Layer3_3B_Spec.md` lines 318-322.

### 2.4 Stop-and-ask triggers — none fired

Trigger #5 (schema/inter-layer-contract amendments): would have fired if the Layer2EHitlItem gap had required a spec amendment; it didn't — `Layer2E_Spec.md` line 810 contains the canonical shape, so the fix was implementation-fidelity not contract-amendment.

Other triggers — none applicable (no new vocabulary, no new exercise db rows, no new HITL trigger, no new partial-update invalidation rule, no Control_Spec change, no new D-row).

### 2.5 Scope NOT changed this session

- **PR-E** (validator harness) — queued next. 19 rules including `injury_accommodation_violation_*` from PR-C-followon.
- **D-70 / D-71** — not touched. ROM modality + tendinopathy phase-sequencing remain Deferred v2.
- **D-66 / D-67** — RaceEventStub + PerDateRestriction landed as PR-D placeholders per the handoff; the full schemas (D-66 race event data model + D-67 per-date athlete restrictions) remain Deferred. Layer 4 validator harness rules with D-67-aware branches will no-op against PerDateRestriction's `always-empty in v1` posture until D-67 implementation lands.

---

## 3. Files shipped this session

One commit on `claude/injury-accommodation-modality-BPYOC` — 3 substantive code + 3 bookkeeping bundled (precedented by PR-A 8-file + PR-B 7-file + PR-C 4-file + PR-C-followon 6-file bundles).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `layer4/context.py` | New | ~570 lines, ~55 types. Mirrors Layer 2A / 2B / 2C / 2D / 2E / 3A / 3B §7 + onboarding §G.1; AccommodationModality discriminated-union with 6 typed variants + verdict-to-accommodations invariant on ExerciseRisk + accommodations field on ResolvedExercise; RaceEventStub + PerDateRestriction placeholders for D-66/D-67. |
| 2 | `layer4/__init__.py` | Modified | 55 re-exports added (Layer2APayload, Layer2BPayload, Layer2CPayload, Layer2DPayload, Layer2EPayload, Layer3APayload, Layer3BPayload, DailyAvailabilityWindow, RaceEventStub, PerDateRestriction, AccommodationModality + 6 variants, all nested types). Existing payload.py + hashing.py re-exports preserved. |
| 3 | `tests/test_layer4_context.py` | New | 50 tests, all green. Coverage: AccommodationModality dispatch × 12 (6 variants + bounds + invariants + unknown-type-rejected), ExerciseRisk accommodation invariants × 6, ResolvedExercise pass-through × 6, happy-path × 8 payloads, extra='forbid' × 8, JSON round-trip × 4 (incl. multi-modality + tagged-union survival), cross-field validation × 6. |
| 4 | `aidstation-sources/Project_Backlog_v43.md` | New | Copy of v42 + new v43 file-revision-header narrative; no new D-rows (PR-D doesn't surface any; the Layer2EHitlItem gap was implementation-fidelity, not a contract gap requiring a D-row). v42 demoted inline. |
| 5 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 pipeline row extended (PR-D landed after PR-C-followon); last-shipped narrative replaced with this session's summary (PR-C-followon demoted to predecessor); Backlog ref v42 → v43; authoritative-current-files: Layer 4 implementation line extended with `layer4/context.py` + `tests/test_layer4_context.py`; Next-forward-move recommends PR-E validator harness against PR-D context schemas. |
| 6 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step3_PR_D_Context_Schemas_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**6 files total. Over the 5-file ceiling intentionally** (Andy explicit precedent from PR-A 8 + PR-B 7 + PR-C 4 + PR-C-followon 6).

---

## 4. What `layer4/context.py` now commits to

### 4.1 AccommodationModality discriminated union (6 variants)

```python
AccommodationModality = Annotated[
    Union[
        VolumeReductionModality,
        IntensityReductionModality,
        TempoModificationModality,
        LoadingTypeChangeModality,
        FrequencyReductionModality,
        ExerciseSubstitutionModality,
    ],
    Field(discriminator="modality_type"),
]
```

Each variant carries `modality_type: Literal[...]` (the discriminator), `rationale: str`, `evidence_basis: list[str]`, plus shape-specific parameters with physical-sanity bounds. TempoModificationModality + FrequencyReductionModality additionally enforce mode-specific field invariants (`isometric_only` requires protocol fields; `factor` or `sessions_per_week_cap` must be set).

### 4.2 ExerciseRisk + ResolvedExercise accommodations

- **`ExerciseRisk.accommodations: list[AccommodationModality]`** — non-empty iff `verdict == 'accommodate'`; empty for `verdict ∈ {exclude, clean}`. Enforced via `_check_verdict_accommodations` at construction.
- **`ResolvedExercise.accommodations: list[AccommodationModality]`** — pass-through from 2D per Layer 2C §5.6 amendment. No tier-coupling — accommodations apply at any tier where the upstream verdict is 'accommodate'.
- **`Layer2DPayload.excluded_exercises` vs `accommodated_exercises`** — defensive partition; each ExerciseRisk's verdict matches its bucket via `_check_excluded_verdict`.

### 4.3 Layer 2A — Layer2APayload

Mirrors `Layer2A_Spec.md` §7. Disciplines carry per-discipline inclusion/role/load_weight/phase_load/training_gap/rationale; payload-level training_gaps_summary + hitl_required + unresolved_flags + coaching_flags + rationale_metadata.

### 4.4 Layer 2B — Layer2BPayload

Mirrors `Layer2B_Spec.md` §7. race_terrain + terrain_gaps + coaching_flags + summary + etl_version_set. Consumed by Layer 4 for cross-ref with `ResolvedExercise.terrain_required`.

### 4.5 Layer 2C — Layer2CPayload (per locale, post-amendment)

Mirrors `Layer2C_Spec.md` §7 + §5.6 amendment. `exercises_resolved[].accommodations` populated per-exercise from upstream 2D pass-through.

### 4.6 Layer 2D — Layer2DPayload (post-amendment)

Mirrors `Layer2D_Spec.md` §7 + §5.3.6 amendment. excluded_exercises + accommodated_exercises (post-rename from downgraded_exercises) + clean_exercise_ids + discipline_risk_profiles + coaching_flags + hitl_items + audit (body_part_vocab_misses + condition_vocab_misses).

### 4.7 Layer 2E — Layer2EPayload

Mirrors `Layer2E_Spec.md` §7. Full daily_nutrition_baseline.per_phase + race_day_fueling + supplement_integration + dietary_pattern_adjustments + sleep_dep_overlay + heat_acclim_adjustments + hitl_items + audit. Layer2EHitlItem uses the spec-accurate 9-field shape (per line 810) not the field-set inferred from the §7 declaration alone.

### 4.8 Layer 3A — Layer3APayload

Mirrors `Layer3_3A_Spec.md` §7. current_state (aerobic_capacity + strength assessments + weak_links + skill_assessments + body_composition_notes) + recent_trajectory (short-term + medium-term + ACWR status + confidence) + data_density + notable_observations (Layer3Observation shared with 3B). **No `active_injuries` field** — that field never existed in 3A per the PR-C-followon spec audit; canonical injury source is 2D.

### 4.9 Layer 3B — Layer3BPayload

Mirrors `Layer3_3B_Spec.md` §7. goal_viability + periodization_shape + hitl_surface + notable_observations. Schema rules enforced: GoalViability achievable ↔ suggested_adjustments empty; PeriodizationShape custom ↔ phase_weeks non-None; Layer3BHITLItem severity='blocker' ↔ acknowledge_option None; HITL labels unique.

### 4.10 DailyAvailabilityWindow

Mirrors `Athlete_Onboarding_Data_Spec_v5.md` §G.1. Per-day-of-week window with enabled + window_start + window_duration + optional second window (gated on `doubles_feasible != 'no'`) + long_session fields + preferred_rest_day. Cross-field invariants enforce enabled-vs-window-presence + second-window pairing.

### 4.11 RaceEventStub + PerDateRestriction (forward-pointers)

- **RaceEventStub** — minimal v1 shape (event_name + event_date + race_format + event_locale_id). Pending D-66 (race-event data model). Layer 4 validator rules `kit_manifest_inputs_incomplete` + `race_plan_segments_unordered` + `contingency_anchor_category_missing` read against this stub until D-66 ships the full schema.
- **PerDateRestriction** — placeholder (date + locale_lock + discipline_exclusions + indoor_only + max_total_minutes). Pending D-67 (per-date athlete restrictions). Always-empty in v1; Layer 4 D-67-aware validator branches (`session_locale_not_in_cluster`, `discipline_excluded`, `daily_window_fit`, `indoor_only_violation`) no-op against an empty list until D-67 ships.

---

## 5. Next session pointers — Step 3 PR-E validator harness

**Architect-recommended next per `CLAUDE.md` "Next forward move":**

### Step 3 PR-E scope: deterministic validator harness (4–5 files projected; ~120 tests)

New `layer4/validator.py` with:
- `ValidatorContext` (bundles the 10 upstream payloads from PR-D — Layer2APayload + Layer2BPayload + per-locale Layer2CPayload bundle + Layer2DPayload + Layer2EPayload + Layer3APayload + Layer3BPayload + list[DailyAvailabilityWindow] + RaceEventStub | None + list[PerDateRestriction])
- `validate_layer4_payload(payload: Layer4Payload, context: ValidatorContext, pass_index: int = 0) → ValidatorResult` driver
- **19 rule functions** (was 18 per PR-C handoff; +1 for `injury_accommodation_violation_*` from PR-C-followon):
  - `_rule_volume_band` (PR-C ±20/±10)
  - `_rule_acwr` (PR-C 28-day chronic)
  - `_rule_rest_spacing`
  - `_rule_intensity_dist`
  - `_rule_two_per_day`
  - `_rule_equipment_resolves_at_locale` (6a)
  - `_rule_single_locale_per_session` (6b)
  - `_rule_session_locale_in_cluster` (6c — D-67-aware)
  - `_rule_injury_violation` (PR-C-followon — 2D excluded_exercises set-membership)
  - `_rule_injury_accommodation_violation` (NEW per PR-C-followon — per-modality compliance)
  - `_rule_schedule_violation`
  - `_rule_discipline_excluded` (D-67-aware)
  - `_rule_sport_locale_incompatible`
  - `_rule_taper_phase_intent_violation`
  - `_rule_kit_manifest_inputs_incomplete` (D-66-aware)
  - `_rule_race_plan_segments_unordered`
  - `_rule_fueling_strategy_2e_tier_mismatch`
  - `_rule_contingency_anchor_category_missing`
  - `_rule_phase_date_out_of_range`
  - `_rule_daily_window_fit` (D-67-aware)
  - `_rule_indoor_only_violation` (PR-C — D-67-aware)

(Recount: rule 6 split into 3 + injury_violation + injury_accommodation_violation + indoor_only_violation + 13 others = 19 distinct rule functions. Some D-67-aware branches no-op until D-67 lands.)

Plus `tests/test_layer4_validator.py` (~120 tests — per rule: 1 happy-path + 1 blocker case + 1 warning case + 1 mode-gated no-op + boundary tests; per-modality compliance test sets for `injury_accommodation_violation_*` covering all 6 variants × 2 cases each).

**Mode-gating policy (settled in PR-C):** each rule function checks `payload.mode` at entry and returns `[]` if not applicable. Driver iterates all rules.

**Missing-input policy (settled in PR-C):** Soft (`Observation(category='data_gap')`) when input is missing-but-tolerable; `ValueError` when input must always be present.

**Stop-and-ask risk:** Low. PR-D closes the typed-context surface; PR-E reads against the established types. If a rule's pseudo-code surfaces ambiguity not already resolved in PR-C or PR-C-followon, route through `/plan` mode.

### Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (PR-D).
3. **Third re-read**: `Layer4_Spec.md` §5.4 (all 19 rules + summary block + injury-accommodation modality framework subsection) + §3.2 / §4.1 / §13.4 (the surfaces that reference 2D excluded/accommodated exercises).
4. **Fourth re-read**: `layer4/context.py` (the typed payloads PR-E reads against) + `layer4/payload.py` §7.12 invariants (the structural rules PR-E layers domain rules on top of).
5. **Branch**: stay on `claude/injury-accommodation-modality-BPYOC` or cut a fresh branch off post-merge main, per harness pinning.
6. **Test convention**: top-level `tests/test_layer4_validator.py` alongside `test_layer4_payload.py` + `test_layer4_hashing.py` + `test_layer4_context.py` (matches PR-A → PR-D conventions).
7. **`AccommodationModality` consumption in PR-E**: the new `_rule_injury_accommodation_violation` rule dispatches on `modality_type` (closed 6-element enum); each branch reads the variant-specific fields. Spec calls for warning severity (not blocker) in v1 — avoids over-triggering on LLM baseline-volume fuzziness; v2 may promote to blocker once retry-rate data informs calibration.
8. **D-67-aware branches**: 4 rules ship in v1 validator harness with D-67-aware branches that no-op against PerDateRestriction's always-empty-list v1 posture. When D-67 implementation lands, the branches activate without further validator-code changes (defensive forward-compatibility).
9. **Stop-and-ask trigger #5**: contract surface mostly closed; if a rule's pseudo-code surfaces real interpretation ambiguity, route through `/plan` mode.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = Step 3 PR-D context schemas (architect-recommended) | Andy 2026-05-17 | Picked from 4-option scope question; PR-D was the architect's queued next per the PR-C-followon §5 forward-pointer + CLAUDE.md "Next forward move". |
| 2 | `AccommodationModality` as tagged-union (discriminator on `modality_type`) | Architect-pick; spec-aligned | Modality variants carry a literal discriminator field; tagged-union is the idiomatic + faster pattern. Smart-union also works but is slower (tries each variant). |
| 3 | `Layer2DHitlItem.injury` + `.condition` typed `dict[str, Any]` (opaque) | Architect-pick | Layer 1 onboarding contracts (InjuryRecord + HealthConditionRecord) aren't consumed by Layer 4's validator. Opaque dict avoids pulling onboarding types into Layer 4 typing surface; v2 may type explicitly if Layer 4 starts consuming the structured form. |
| 4 | `Layer3Observation` shared between 3A + 3B | Architect-pick; spec-aligned | 3A + 3B specs define identical observation shape. Single shared type rather than per-layer aliases. (Layer 4's own `Observation` in `payload.py` has a broader category enum and remains its own type.) |
| 5 | Layer2EHitlItem field set per `Layer2E_Spec.md` line 810 (corrected from first-pass guess) | Spec-fidelity correction | First pass mirrored the field declaration only; cross-reference to line 810 surfaced the actual 9-field class shape. Implementation-fidelity correction, not contract amendment. |
| 6 | RaceEventStub + PerDateRestriction landed as PR-D placeholders | Per PR-C-followon handoff §5 + CLAUDE.md "Next forward move" | D-66 + D-67 still Deferred. v1 validator harness branches against the placeholders no-op until D-67 implementation lands. |
| 7 | Bookkeeping bundled into this session | Continues PR-A → PR-B → PR-C → PR-C-followon precedent | 6 files total; over ceiling by 1; precedented. |

### 6.2 Stop-and-ask trigger retrospective

- **Trigger #5 did NOT fire this session** — the Layer2EHitlItem gap was implementation-fidelity drift (I'd misread §7's class definitions by stopping early), not a contract amendment. `Layer2E_Spec.md` line 810 contains the canonical shape; the fix preserves spec contract verbatim.
- Other triggers — none applicable (no new vocabulary, no exercise db rows, no HITL trigger, no partial-update invalidation rule, no Control_Spec change, no new D-row).

### 6.3 Carried forward to PR-E

- **`ValidatorContext` bundles PR-D's 10 typed payloads.** PR-E doesn't re-derive — it imports + composes.
- **`_rule_injury_violation` reads `Layer2DPayload.excluded_exercises[].exercise_id`** for set-membership against prescribed `cardio_blocks[].exercise_id` + `strength_exercises[].exercise_id`.
- **`_rule_injury_accommodation_violation` reads `Layer2DPayload.accommodated_exercises[].accommodations`** for per-modality compliance. Dispatches on `modality_type` (closed 6-element enum). Severity=warning (not blocker) in v1.
- **`AccommodationModality.evidence_basis: list[str]`** — free-text citation IDs (e.g., 'soligard_2016_bjsm'). Validator doesn't enforce vocab; v2 may add an evidence-citation registry.
- **D-67-aware branches** — 4 rules carry D-67-aware code that activates only when PerDateRestriction list is non-empty. v1 no-ops cleanly.

### 6.4 Carried forward to D-66 / D-67 design waves

- **D-66 design wave** — `race_events` + `race_route_locales` tables + onboarding/profile UI. RaceEventStub in `context.py` migrates to the full schema. Layer 4 rules `kit_manifest_inputs_incomplete` + `race_plan_segments_unordered` + `contingency_anchor_category_missing` pick up structured fields.
- **D-67 design wave** — `daily_restrictions` table (locale_lock + discipline_exclusions + indoor_only + max_total_minutes) + onboarding/profile UI. PerDateRestriction in `context.py` migrates to the full schema. 4 D-67-aware validator branches activate.

---

## 7. Session-end verification (Rule #10)

Final pass before committing:

| Check | Result |
|---|---|
| `layer4/context.py` exists with 10 upstream-mirror types + 6 AccommodationModality variants + tagged-union dispatch | ✅ inspection |
| `ExerciseRisk._check_verdict_accommodations` enforces §5.3.6 invariant | ✅ test_exercise_risk_accommodate_*_rejected × 3 pass |
| `Layer2DPayload._check_excluded_verdict` defensive partition | ✅ test_layer2d_*_wrong_verdict_rejected × 2 pass |
| `Layer2EHitlItem` matches `Layer2E_Spec.md` line 810 shape (9 fields) | ✅ inspection of `context.py` |
| All Layer3_3B_Spec.md §7 schema rules enforced (achievable ↔ adjustments empty; custom ↔ phase_weeks non-None; blocker ↔ acknowledge_option None; HITL labels unique) | ✅ test_goal_viability_*, test_periodization_shape_*, test_layer3b_hitl_unique_labels_enforced pass |
| `DailyAvailabilityWindow` enabled-vs-window invariants enforced | ✅ inspection (no failing test required — covered by happy-path) |
| `layer4/__init__.py` re-exports all 55 new types alongside existing payload + hashing exports | ✅ grep `__all__` |
| `tests/test_layer4_context.py` 50 tests, all green | ✅ `python -m pytest tests/test_layer4_context.py` |
| Combined `tests/` (test_layer4_payload + test_layer4_hashing + test_layer4_context) = 209 tests, all green | ✅ `python -m pytest tests/` 0.32s |
| No regression in PR-A + PR-B + PR-C + PR-C-followon work | ✅ same 159 PR-A/PR-B tests + 50 new = 209 |
| `Project_Backlog_v43.md` exists; file-revision-header is v43; v42 inline-demoted | ✅ inspection |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v43.md` | ✅ grep |
| `CLAUDE.md` Layer 4 row mentions "PR-D context schemas landed" | ✅ grep |
| `CLAUDE.md` Last-shipped is PR-D; PR-C-followon demoted to first Predecessor | ✅ inspection |
| `CLAUDE.md` Next-forward-move recommends PR-E validator harness | ✅ grep |
| Working tree shows 6 files modified / created | ✅ `git status` |
| Branch is `claude/injury-accommodation-modality-BPYOC` (harness-pinned) | ✅ |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; PR-D is implementation-layer (no UI surface; no new §5.0 row needed).
- Step 3 PR-E validator harness — queued next session against PR-D context schemas; 19 rules; ~120 tests projected.
- Step 4a `llm_layer4_single_session_synthesize` (D-63) — queued after PR-E (simplest entry point per §14.3.4).
- v5 onboarding implementation PR — independent of Layer 4 implementation track; can run in parallel.
- D-50 wiring resumption — now unblocked by D-58; can run in parallel.

---

**End of handoff.**
