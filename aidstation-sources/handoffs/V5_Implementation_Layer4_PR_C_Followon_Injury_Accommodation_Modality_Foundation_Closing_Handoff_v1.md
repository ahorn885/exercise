# V5 Implementation — Layer 4 PR-C Follow-on: Injury-Accommodation Modality Foundation Amendment Closing Handoff

**Session:** Single chat. Scope-expanded from PR-D (Layer 4 implementation Step 3 context schemas — architect-recommended next per PR-C closing handoff §5) into a foundational evidence-based amendment of 2D + 2C + Layer 4 specs around accommodation modalities. Spec-only PR.
**Date:** 2026-05-17
**Predecessor handoff:** `V5_Implementation_Layer4_Step3_PR_C_Spec_Amendments_Closing_Handoff_v1.md` (PR-C — `Layer4_Spec.md` §5.4 amendments + D-66/D-67/D-68 backlog rows).
**Branch:** `claude/spec-amendments-implementation-tTUn7` (harness-pinned for this session — same precedent as PR-A → PR-B → PR-C; Andy confirmed leaving the harness-pinned name as-is at session start).
**Status:** 🟢 3 substantive spec amendments + 3 bookkeeping files. 159 pytest cases still green (no code change). PR ready to open.

---

## 1. Session-start verification (Rule #9)

Predecessor (PR-C) handoff §7 claimed: `Layer4_Spec.md` §5.4 amended with volume_band ±20/±10 + acwr trailing 28-day window + Gabbett 2016 + rule 6 split into 6a/6b/6c locale-cluster invariants + indoor_only_violation_* NEW row + D-66/67/68 forward-pointer summary block; `Project_Backlog_v41.md` exists with D-66/67/68 rows; `CLAUDE.md` Backlog ref reads v41; PR-C substantive commit `cc51d40` pushed; merge commit `63a1ff9` for PR #70 on `origin/main`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `Layer4_Spec.md` §5.4 `volume_band_*` row reads ±20/±10 + Andy 2026-05-17 attribution | grep | ✅ line 890 |
| `Layer4_Spec.md` §5.4 `acwr_*` row references trailing 28 days + Gabbett 2016 | grep | ✅ line 891 |
| `Layer4_Spec.md` §5.4 has rules 6a + 6b + 6c separately | grep | ✅ lines 895–897 |
| `Layer4_Spec.md` §5.4 has `indoor_only_violation_*` row | grep | ✅ line 909 |
| `Layer4_Spec.md` §5.4 has D-66/67/68 forward-pointer summary block | grep | ✅ lines 919–920 |
| `Project_Backlog_v41.md` exists, file-revision-header is v41, D-66/67/68 rows present | grep | ✅ lines 137–139 |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v41.md` | grep | ✅ |
| `CLAUDE.md` Layer 4 row mentions "Step 3 PR-C of E landed" | grep | ✅ |
| PR #70 merged on `origin/main` at `63a1ff9` | `git log --oneline -10` | ✅ |
| 159 pytest cases still pass | `pytest tests/` after `pip install pytest pydantic` | ✅ 0.28s |
| Working tree clean | `git status` | ✅ |
| No drift between handoff narrative and on-disk state | Rule #9 reconciliation | ✅ |

**No drift found.** PR-C state on disk matches the handoff narrative exactly. Branch is a fresh `claude/spec-amendments-implementation-tTUn7` cut off main post-PR #70 merge (harness-pinned; precedent: PR-A → PR-B → PR-C all harness-pinned with name mismatching scope).

---

## 2. Session narrative — Andy-driven scope expansion, two contract gaps surfaced, 6-modality framework specced

Andy opened with a URL pointer to the PR-C closing handoff and "lets work". I followed §5 operating notes — re-read CLAUDE.md, ran Rule #9 verification, reported state + next focus + drift (none). Asked Andy to confirm scope: architect-recommended Step 3 PR-D (context schemas) vs other candidates. Andy picked PR-D.

### 2.1 PR-D scoping audit surfaced two contract gaps

I launched a research agent to extract the upstream §7 payload schemas (Layer 2A/2C/2E/3A/3B per PR-C handoff §5 sketch). While the agent ran, I read the existing `layer4/payload.py` to confirm pydantic v2 conventions. When the agent returned, I cross-checked the sketched 5 payloads against Layer 4 spec's actual references and found:

**Gap 1 — PR-C handoff sketch missed Layer 2B + 2D payloads.** The handoff §5 listed 5 Layer payloads (2A + 2C + 2E + 3A + 3B). But `Layer4_Spec.md` lines 29 + 92 + 187 + 228 explicitly consume `Layer2DPayload` (injury exclusions) and 2B (terrain). PR-D should ship 7 Layer payloads.

**Gap 2 — `active_injuries` source contradicts itself within Layer 4 spec.**
- `Layer4_Spec.md` §3.2 line 29 + line 118 say injuries come from **`Layer2DPayload`**.
- BUT lines 753, 898, 1360 say injuries come from **`layer3a_payload.current_state.active_injuries`** with structured `body_part` + `severity` + `restriction_text`.
- The **`Layer3_3A_Spec.md` §7 payload schema does NOT have an `active_injuries` field** — only `current_state.weak_links` + `notable_observations`.

I surfaced both gaps in chat with proposed paths (Path 1: mirror upstream verbatim, defer; Path 2: surgical spec sweep + 7 payloads; Path 3: ship 5, defer 2B+2D; Path 4: 7 payloads + Rule #11 mechanically-applicable str_replace for PR-E to apply). Andy initially picked "Discuss further."

### 2.2 The scope expansion — Andy's 4-step injury-accommodation framing

Andy then surfaced a deeper framing: "we are supposed to be working multiple things together for injury acclimation. the injury is logged (layer zero?) → the injury is interpreted (what movements should be restricted, what muscle groups are impacted) → exercises are interpreted (this exercise uses a muscle group or movement that is restricted, it needs to be swapped OR this exercise has high volume but lower volume is recommended) → accommodations are made (good equivalent exercise OR volume reduced). im not sure if any of your proposals mirror this concept - but we should have the foundational data specced to support it."

This expanded the scope beyond fixing the 3 spec drafting errors. I mapped Andy's 4-step lifecycle against current coverage:

| Step | Where it lives | v1 coverage |
|---|---|---|
| 1 — Logging | Layer 1 athlete onboarding (`InjuryRecord` per `Layer2D_Spec.md` §3) + Layer 0 `body_parts` vocab + `movement_constraints` vocab B.3 | ✅ fully wired |
| 2 — Interpretation | Layer 2D §5 (body-part / condition / movement-constraint matching → EXCLUDE/DOWNGRADE/CLEAN verdict) | ✅ EXCLUDE path fully wired; ⚠️ DOWNGRADE partial — binary signal with no structured quantification |
| 3 — Exercise interpretation | 2D EXCLUDE → 2C Tier 2/3 (swap path) ✅; 2D DOWNGRADE → ⚠️ no structured "reduce volume by N%" or "switch to eccentric tempo" signal; just "this should be downgraded" | ⚠️ gap |
| 4 — Accommodation | Layer 4 synthesizer prescribes; Layer 4 validator checks | ⚠️ no validator backstop for DOWNGRADE path |

The gap was at the Step 3→4 handoff — DOWNGRADE verdict carried no actionable quantification for Layer 4. Andy clarified that Step 3 has MORE than just {swap, volume_reduction} — intensity, tempo, loading-type-change, frequency, ROM, and others — and "this should be based on science/evidence - how much do sports therapists, doctors, etc. recommend to accommodate exercises in scenarios like these."

### 2.3 Path II ratified — research-grounded single amendment session

I presented three paths:
- **Path I** — full Layer 0 reference-data wave for accommodation modalities (LLM generates enum + parameter ranges + injury-pattern mappings from cited literature; HITL review + lock; new Layer 0 tables). ~4-6 sessions.
- **Path II** — single research-grounded amendment session (WebSearch + WebFetch scan of ACSM + NSCA + Cook/Purdam + sports med review papers; propose v1 closed enum of 5-8 modalities; lock 2D + 2C + Layer 4 amendments). ~1-2 sessions.
- **Path III** — spec architectural shape with `modality_type: str` open enum; defer enum lock to v2 based on observation. ~1 session.

Andy picked Path II — pragmatic evidence-grounded balance. Tool capability note flagged: I'm not a sports medicine researcher; the v1 enum will likely need v2 corrections.

### 2.4 Research scan + 6-modality framework ratified

Launched general-purpose research agent for the literature scan via WebSearch + WebFetch. Agent returned a 7-modality proposal with parameter shapes + evidence citations + use cases + phase-dependent contraindications. I proposed tightening to 5–6 modalities (drop `range_of_motion_restriction` because parameterization is condition-specific; drop `exercise_substitution` because it overlaps with existing 2D EXCLUDE → 2C Tier 2/3 wiring).

Andy ratified: **drop ROM, include swap as already wired, plus 5 from research = 6 modalities total**. Phase sequencing: **current-time only (v1)**. Muscle-group concept: **defer — body_part vocab is sufficient for v1**.

v1 closed modality enum (6 variants — see §4.1 below for full schema):
1. `volume_reduction`
2. `intensity_reduction`
3. `tempo_modification`
4. `loading_type_change`
5. `frequency_reduction`
6. `exercise_substitution` (included for unified-enum completeness; NOT directly 2D-emitted)

### 2.5 Stop-and-ask triggers fired

- **Trigger #5** (schema/inter-layer-contract amendments) — fired on Layer 2D + 2C + Layer 4 schema amendments. Routed through `/plan` mode discussion before any spec edit applied. Per Andy 2026-05-17 amendment-authoring directive, amendment authoring goes through `/plan` mode even when the substantive design pick is settled.
- **Trigger #11** (new D-rows with cross-layer scope) — fired three times (D-69 ✅ Resolved + D-70 + D-71 🟡 Deferred). All three are cross-layer (Layer 2D + 2C + Layer 4 + 1 athlete onboarding extension). Routed through the same `/plan` mode discussion.

### 2.6 Architectural deviations on the record

- **Verdict rename DOWNGRADE → ACCOMMODATE** in 2D's Verdict enum — semantically cleaner ("accommodate with modalities" vs binary "downgrade somehow") but breaks any consumer that string-compares the enum value. No production consumers yet (2D is unimplemented; spec-only). Clean rename, no backward-compat shim needed.
- **`downgraded_exercises` → `accommodated_exercises` field rename** in `Layer2DPayload` for consistency with the verdict rename. Same backward-compat reasoning.
- **`accommodations: list[AccommodationModality]` field added to both `ExerciseRisk` (Layer 2D) and `ResolvedExercise` (Layer 2C)** — these are additive, not breaking; consumers that don't read the field are unaffected.

### 2.7 Scope NOT changed this session

Per Andy's earlier picks:
- **PR-D is the next-session forward move** — context schemas now mirror the AMENDED 2D + 2C specs (so PR-D's `Layer2DPayload` includes `AccommodationModality` typed union + `accommodated_exercises`; `Layer2CPayload.resolved_exercises[].accommodations` field populated). Adds ~12 accommodation-specific tests to PR-D's projection (~50 tests now, was ~30).
- **PR-E becomes 19 rules** (17 from original §5.4 post-amendment + `indoor_only_violation_*` from PR-C + new `injury_accommodation_violation_*` from this session).
- **D-50 wiring + v5 onboarding implementation + Layer 5 spec + Layer 4.5 Joint Session Coordinator** all unchanged.

---

## 3. Files shipped this session

One commit on `claude/spec-amendments-implementation-tTUn7` — 3 substantive spec amendments + 3 bookkeeping bundled (precedented by PR-A 8-file + PR-B 7-file + PR-C 4-file bundles).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Layer2D_Spec.md` | Modified | §5.3.2 + §5.3.3 + §5.3.4 + §5.3.5 verdict-rename (DOWNGRADE → ACCOMMODATE); NEW §5.3.6 accommodation modality recommendation (~150 lines, 6 sub-sections); §6 D-2D-4 drift item update; §7 ExerciseRisk + Layer2DPayload + new AccommodationModality typed union (~85 lines for 6 modality variants); §10 example narratives (Andy wrist + multi-injury) updated. |
| 2 | `aidstation-sources/Layer2C_Spec.md` | Modified | NEW §5.6 accommodation modality pass-through (~15 lines); §5.7 = original §5.6 per-discipline coverage aggregation (renumbered); §7 `ResolvedExercise.accommodations: list[AccommodationModality]` field added. |
| 3 | `aidstation-sources/Layer4_Spec.md` | Modified | §3.2/§4.1 line 753 input-validation rule rewritten (`active_injury_data_gap` → `injury_data_inconsistent`; canonical source pivot to 2D); §5.4 `injury_violation_*` rewritten (set-membership against 2D excluded_exercises); NEW §5.4 `injury_accommodation_violation_*` rule (per-modality compliance checks); §5.4 summary block extension (accommodation modality framework); §13.4 wrist-injury edge case rewrite. |
| 4 | `aidstation-sources/Project_Backlog_v42.md` | New | Copy of v41 + new v42 file-revision-header narrative + 3 new D-rows (D-69 ✅ Resolved + D-70 🟡 Deferred + D-71 🟡 Deferred) appended after D-68. v41 demoted inline as most-recent predecessor. |
| 5 | `aidstation-sources/CLAUDE.md` | Modified | Layer 4 pipeline row updated (PR-C-followon added after PR-C); last-shipped narrative replaced with this session's summary (PR-C demoted to predecessor); Backlog ref v41 → v42; authoritative-current-files: Layer 4 line extended with PR-C-followon note + Layer 2D + Layer 2C lines added (both done v1 + amendment); Next-forward-move + PR-D candidate description + PR-E candidate description all updated for amended-spec context. |
| 6 | `aidstation-sources/handoffs/V5_Implementation_Layer4_PR_C_Followon_Injury_Accommodation_Modality_Foundation_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**6 files total. Over the 5-file ceiling intentionally** (Andy explicit direction at session start; precedented by PR-A 8 files, PR-B 7 files, PR17 7 files). No code changes — amendment is spec-only.

---

## 4. What the specs now commit to

### 4.1 `Layer2D_Spec.md` amendments

**§5.3.4 severity → verdict mapping (renamed):**

| Severity | Verdict |
|---|---|
| Acute | EXCLUDE |
| Recovering | **ACCOMMODATE** (was DOWNGRADE) |
| Chronic-Managed | **ACCOMMODATE** (was DOWNGRADE) |
| Post-surgical | EXCLUDE (also triggers HITL clearance gate §5.7) |
| Structural-Permanent | **ACCOMMODATE** (was DOWNGRADE) |
| Resolved | CLEAN |

Verdict enum widened: `Verdict ∈ {EXCLUDE, ACCOMMODATE, CLEAN}`.

**NEW §5.3.6 Accommodation modality recommendation** — 6 sub-sections (~150 lines):
- **§5.3.6.1** v1 closed modality set (6 variants in markdown table with parameter shapes + evidence basis + use case columns)
- **§5.3.6.2** v1 default modality table — sparse `dict[(injury_type, severity), list[AccommodationModality]]` mapping. Covers Tendinopathy/overuse × {Acute, Recovering, Chronic-Managed}; Muscle/tendon strain × {Acute, Recovering}; Stress fracture/bone stress × {Acute, Recovering}; Joint sprain × {Acute, Recovering}; Post-surgical × Post-surgical.
- **§5.3.6.3** Fallback recommendation (v1: `volume_reduction(0.7, sets) + intensity_reduction(0.7, percent_1rm)` per IOC moderate-deload position)
- **§5.3.6.4** Phase-dependent contraindications (3 rules — acute reactive tendinopathy → isometric_only enforced; bone stress → intensity_reduction alone INSUFFICIENT; post-surgical first 6wk → loading_type_change preferred)
- **§5.3.6.5** v1 lookup function `recommend_accommodations(exercise, current_injuries, evidence) → list[AccommodationModality]`
- **§5.3.6.6** What v1 explicitly does NOT do (deferred items mapped to D-70 + D-71 + general v2 follow-ons)

**§7 AccommodationModality typed union** — 6 variants:

```python
@dataclass
class VolumeReductionModality:
    modality_type: str  # Literal['volume_reduction']
    factor: float                                # 0.3-1.0
    applies_to: str                              # 'sets' | 'reps' | 'duration'
    rationale: str
    evidence_basis: list[str]

@dataclass
class IntensityReductionModality:
    modality_type: str  # Literal['intensity_reduction']
    factor: float                                # 0.4-1.0
    target_metric: str                           # 'percent_1rm' | 'rpe' | 'pace' | 'power' | 'hr_zone'
    rationale: str
    evidence_basis: list[str]

@dataclass
class TempoModificationModality:
    modality_type: str  # Literal['tempo_modification']
    tempo_pattern: str                           # 'eccentric_focus' | 'isometric_only' | 'heavy_slow_resistance'
    eccentric_s: int | None                      # tempo tuple — populated for eccentric_focus + heavy_slow_resistance
    isometric_bottom_s: int | None
    concentric_s: int | None
    isometric_top_s: int | None
    hold_s: int | None                           # isometric_only — 15-60s per Rio 2015
    sets: int | None                             # 5 per Rio 2015
    rest_s: int | None                           # ~120s
    intensity_pct_mvc: int | None                # 30-100; 70 typical per Rio 2015
    rationale: str
    evidence_basis: list[str]

@dataclass
class LoadingTypeChangeModality:
    modality_type: str  # Literal['loading_type_change']
    from_type: str                               # 'bilateral' | 'barbell' | 'free_weight' | 'machine' | 'cable' | 'dumbbell'
    to_type: str                                 # 'bilateral' | 'unilateral_contralateral' | 'unilateral_ipsilateral' | 'dumbbell' | 'machine' | 'cable' | 'assisted'
    rationale: str
    evidence_basis: list[str]

@dataclass
class FrequencyReductionModality:
    modality_type: str  # Literal['frequency_reduction']
    factor: float | None                         # 0.0-1.0 (relative)
    sessions_per_week_cap: int | None            # absolute (supersedes factor when set)
    discipline_id: str | None                    # which discipline (None = global)
    rationale: str
    evidence_basis: list[str]

@dataclass
class ExerciseSubstitutionModality:
    modality_type: str  # Literal['exercise_substitution']
    # No parameters; included for unified-enum completeness; NOT directly 2D-emitted.
    # 2D emits Verdict.EXCLUDE → 2C Tier 2/3 substitution handles it.
    rationale: str
    evidence_basis: list[str]

AccommodationModality = Union[
    VolumeReductionModality,
    IntensityReductionModality,
    TempoModificationModality,
    LoadingTypeChangeModality,
    FrequencyReductionModality,
    ExerciseSubstitutionModality,
]
```

**§7 `Layer2DPayload` + `ExerciseRisk` updates:**
- `Layer2DPayload.downgraded_exercises` → `accommodated_exercises` (clean rename)
- `ExerciseRisk.verdict: str` widened to `'exclude' | 'accommodate' | 'clean'`
- `ExerciseRisk.accommodations: list[AccommodationModality]` (non-empty iff verdict='accommodate')

### 4.2 `Layer2C_Spec.md` amendments

**NEW §5.6 Accommodation modality pass-through:**

```python
def resolve_accommodations(resolved, layer2d_payload) -> list[ResolvedExercise]:
    accommodated_map = {er.exercise_id: er.accommodations for er in layer2d_payload.accommodated_exercises}
    for r in resolved:
        r.accommodations = accommodated_map.get(r.exercise_id, [])
    return resolved
```

Pass-through is mechanical; 2C does not interpret modalities. Layer 4 reads `ResolvedExercise.accommodations` alongside the substitution Tier.

**§5.7** = original §5.6 per-discipline coverage aggregation (renumbered).

**§7 `ResolvedExercise` extended:**
- `accommodations: list[AccommodationModality]` field added (pass-through from 2D).

### 4.3 `Layer4_Spec.md` amendments

**§3.2 / §4.1 line 753 rewritten** — old `active_injury_data_gap` rule referenced non-existent `layer3a_payload.current_state.active_injuries.body_part + severity + restriction_text` field; new `injury_data_inconsistent` rule references canonical `layer2d_payload.excluded_exercises + accommodated_exercises` with structural checks (verdict ∈ closed enum; accommodations non-empty when verdict='accommodate'). Amendment note inline.

**§5.4 `injury_violation_*` rewritten** — old wording "No exercise hits a body part in 3A `active_injuries` with `restriction_text` indicating exclusion" replaced with clean set-membership "every prescribed `cardio_blocks[].exercise_id` + `strength_exercises[].exercise_id` is NOT IN `layer2d_payload.excluded_exercises[].exercise_id`". Severity: `blocker`. Amendment note inline.

**NEW §5.4 `injury_accommodation_violation_*` rule** — per-modality validator checks for prescribed exercises that appear in `accommodated_exercises[].exercise_id`:
- **volume_reduction** — prescribed volume (sets × reps for strength; duration_min for cardio) ≤ baseline × `factor` + 10% tolerance
- **intensity_reduction** — prescribed intensity (load % 1RM; intensity_target midpoint) ≤ baseline × `factor` + 10% tolerance
- **tempo_modification** — `StrengthExercise.tempo` field matches modality tuple within ±1s per component (eccentric_focus / heavy_slow_resistance) OR matches isometric notation (isometric_only)
- **loading_type_change** — prescribed implement / laterality matches modality `to_type` per 2C ResolvedExercise metadata
- **frequency_reduction** — per-discipline (or global) weekly session count ≤ `sessions_per_week_cap` or baseline × `factor`
- **exercise_substitution** — covered by `injury_violation_*` (set-membership against excluded_exercises)

Severity: `warning` (not blocker) in v1 — avoids over-triggering on LLM baseline-volume fuzziness; bubbles to plan-diff observations for athlete review. v2 may promote to blocker once measured retry rates inform calibration.

**§5.4 summary block extension** — new subsection "Injury accommodation modality framework" enumerating the 6-modality closed set + per-modality validator checks + deferred items (ROM = D-70; phase sequencing = D-71).

**§13.4 wrist-injury edge case rewrite** — references 2D excluded_exercises as canonical source (per the §5.4 rewrite).

### 4.4 Three new D-rows (Project_Backlog_v42.md)

**D-69 — Injury-accommodation modality foundation** (Med severity, ✅ Resolved 2026-05-17).
- Scope: spec the AccommodationModality typed union + per-injury-type-and-severity decision matrix + Layer 2D §5.3.6 logic + Layer 2C pass-through + Layer 4 validator rule.
- Closes the "we should have the foundational data specced to support [the 4-step injury-accommodation lifecycle]" Andy directive.
- Resolution shipped in this session via Path II (research-grounded single amendment session, 6 v1 modalities from evidence scan).

**D-70 — Range-of-motion restriction accommodation modality** (Low severity, 🟡 Deferred v2).
- Scope: add `RangeOfMotionRestrictionModality` to AccommodationModality typed union with mode ∈ {pain_free, partial_specified} + max_flexion_deg + max_extension_deg + rom_fraction parameters.
- Defer trigger: first real ROM-restriction case (post-op or shoulder-impingement athlete) surfaces.
- Excluded from v1 because parameterization is condition-specific (post-ACL "0–90° flexion" vs shoulder impingement "<90° abduction"); no clean cross-condition shape per the D-69 literature scan.

**D-71 — Phase-sequencing for tendinopathy progression (Cook & Purdam staged loading)** (Low severity, 🟡 Deferred v2).
- Scope: extend AccommodationModality to emit modality SEQUENCE per Cook & Purdam staged progression (isometric → HSR → energy-storage → return-to-sport).
- Defer trigger: first chronic-tendinopathy case with multi-stage progression needs surfaces.
- v1 captures progression implicitly via T1 refresh + 3A re-assessment re-running 2D against updated severity — sufficient until then.

---

## 5. Next session pointers — Step 3 PR-D against amended specs

**Architect-recommended next per `CLAUDE.md` "Next forward move":**

### Step 3 PR-D scope: upstream-layer context schemas (5–6 files projected; ~50 tests)

New `layer4/context.py` defining typed pydantic v2 `BaseModel` payloads for the 8 upstream-layer inputs the validator consumes — mirroring the AMENDED specs:

1. **`Layer2APayload`** — per `Layer2A_Spec.md` §7. `disciplines: list[Layer2ADiscipline]` with per-discipline `inclusion`/`role`/`load_weight`/`phase_load`/`training_gap`/`rationale`; plus `training_gaps_summary` + `hitl_required` + `unresolved_flags` + `coaching_flags` + `rationale_metadata`. `discipline_inclusion` derived at use-site (no top-level field).

2. **`Layer2BPayload`** — per `Layer2B_Spec.md` §7. `race_terrain: list[RaceTerrainOutput]` + `terrain_gaps: list[TerrainGap]` + `coaching_flags` + `summary: SummaryBlock`. PR-C handoff missed this; consumed for cross-ref with 2C exercise `terrain_required`.

3. **`Layer2CPayload`** (per locale) — per `Layer2C_Spec.md` §7 + new §5.6 amendment. `effective_pool` + `discipline_coverage: list[DisciplineCoverage]` + `exercises_resolved: list[ResolvedExercise]` (**now includes `accommodations: list[AccommodationModality]` field per PR-C-followon §5.6**) + `coaching_flags`.

4. **`Layer2DPayload`** — per `Layer2D_Spec.md` §7 (post-amendment). `excluded_exercises` + `accommodated_exercises` (renamed) + `clean_exercise_ids` + `discipline_risk_profiles` + `coaching_flags` + `hitl_items` + audit fields. `ExerciseRisk` includes `accommodations: list[AccommodationModality]`. Plus full `AccommodationModality` discriminated-union mirror (6 typed variants: VolumeReductionModality, IntensityReductionModality, TempoModificationModality, LoadingTypeChangeModality, FrequencyReductionModality, ExerciseSubstitutionModality) with smart-union dispatch.

5. **`Layer2EPayload`** — per `Layer2E_Spec.md` §7. `daily_nutrition_baseline.per_phase` + `race_day_fueling: list[RaceDayFueling]` + `supplement_integration: SupplementIntegrationPayload` + `sleep_dep_overlay` + `heat_acclim_adjustments` + `hitl_items` + audit fields.

6. **`Layer3APayload`** — per `Layer3_3A_Spec.md` §7. `current_state` (with `weak_links` + `skill_assessments` + `body_composition_notes`) + `recent_trajectory` (with ACWR) + `data_density` + `notable_observations`. NOTE: no `active_injuries` field (that lives in 2D per amendment).

7. **`Layer3BPayload`** — per `Layer3_3B_Spec.md` §7. `goal_viability: GoalViability` + `periodization_shape: PeriodizationShape` + `hitl_surface: list[HITLItem]` + `notable_observations`.

8. **`DailyAvailabilityWindow`** — per `Athlete_Onboarding_Data_Spec_v5.md` §G.1. `day_of_week` (Sun–Sat) + `enabled` + `window_start` + `window_duration` (30-360 min) + `second_window_start | None` + `second_window_duration | None` + `long_session_available | None` + `long_session_max_duration | None` + `doubles_feasible` enum + `preferred_rest_day`.

9. **`RaceEventStub`** — minimal v1 pending D-66. `event_name` + `event_date` + `race_format` + `event_locale_id | None`.

10. **`PerDateRestriction`** — placeholder pending D-67. `date` + `locale_lock | None` + `discipline_exclusions: set[str]` + `indoor_only` + `max_total_minutes | None`. Always-empty in v1.

Plus `tests/test_layer4_context.py` (~50 tests — happy-path per payload × 8 + extra='forbid' rejection × 8 + JSON round-trip × 4 + cross-field validation × 6 + AccommodationModality smart-union dispatch × 12 + accommodation-on-ExerciseRisk invariants × 6 + accommodation pass-through-to-ResolvedExercise × 6). Plus re-exports in `layer4/__init__.py`. Plus closing handoff. Plus Project_Backlog v42 → v43 bump.

**5–6 files projected; under-ceiling.**

**Stop-and-ask risk:** Low. Contract gaps surfaced by PR-D scoping are now closed via the spec amendments in this session. If a NEW gap surfaces (e.g., 2B has a field reference Layer 4 needs that I missed), surface via `/plan` mode.

### Step 3 PR-E scope: deterministic validator harness (4–5 files projected; ~120 tests)

New `layer4/validator.py` with:
- `ValidatorContext` (bundles all 8 upstream payloads from PR-D)
- `validate_layer4_payload(payload, context, pass_index=0) → ValidatorResult` driver
- **19 rule functions** (was 18 per PR-C handoff; +1 for `injury_accommodation_violation_*`):
  - `_rule_volume_band` (PR-C ±20/±10)
  - `_rule_acwr` (PR-C 28-day chronic)
  - `_rule_rest_spacing`
  - `_rule_intensity_dist`
  - `_rule_two_per_day`
  - `_rule_equipment_resolves_at_locale` (6a)
  - `_rule_single_locale_per_session` (6b)
  - `_rule_session_locale_in_cluster` (6c — D-67-aware)
  - `_rule_injury_violation` (rewritten — 2D excluded_exercises set-membership)
  - `_rule_injury_accommodation_violation` (NEW — per-modality compliance)
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

(Recount: rule 6 split into 3 + injury_violation + new injury_accommodation_violation + indoor_only_violation = 19 distinct rule functions; some rules have D-67-aware branches that no-op until D-67 lands.)

Plus `tests/test_layer4_validator.py` (~120 tests — per rule: 1 happy-path + 1 blocker case + 1 warning case + 1 mode-gated no-op + boundary tests; per-modality compliance test sets for `injury_accommodation_violation_*` covering all 6 variants).

**Mode-gating policy (settled in PR-C):** each rule function checks `payload.mode` at entry and returns `[]` if not applicable. Driver iterates all rules.

**Missing-input policy (settled in PR-C):** Soft (`Observation(category='data_gap')`) when input is missing-but-tolerable; `ValueError` when input must always be present.

**Stop-and-ask risk:** Low after this session's amendments. If a rule's pseudo-code surfaces real ambiguity not resolved in PR-C or PR-C-followon, route through `/plan` mode.

### Operating notes for next session

1. **First re-read** (Rule #13): re-read `aidstation-sources/CLAUDE.md` fully before any other context-load. Rule #9 verification needs the full CLAUDE.md context.
2. **Second re-read**: this handoff.
3. **Third re-read**: `Layer2D_Spec.md` §5.3.6 + §7 (the new accommodation modality framework that PR-D mirrors) + `Layer2C_Spec.md` §5.6 + §7 (the pass-through + ResolvedExercise.accommodations field) + `Layer4_Spec.md` §3.2 + §5.4 (the rewritten injury_violation_* + new injury_accommodation_violation_*).
4. **Fourth re-read**: the 7 upstream-layer specs §7 (2A + 2B + 2C + 2D + 2E + 3A + 3B) that PR-D context schemas mirror.
5. **Branch**: stay on `claude/spec-amendments-implementation-tTUn7` (harness-pinned through the rest of the Step 3 PR series) OR cut a new branch off post-merge main, whichever the harness pins.
6. **Test convention**: put `test_layer4_context.py` at top-level `tests/` alongside `test_layer4_payload.py` + `test_layer4_hashing.py` (matches PR-A + PR-B + PR-C conventions; PR-C-followon had no test changes).
7. **No D-70 / D-71 design wave kicks off in PR-D or PR-E** — those land later when first cases surface. PR-D ships the AccommodationModality typed union with the 6 v1 variants only.
8. **Stop-and-ask trigger #5**: contract surface mostly closed; if a rule's pseudo-code surfaces a real interpretation question, route through `/plan` mode.

---

## 6. Open items / decisions pinned this session

### 6.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Path II (research-grounded single amendment session) over Path I (full Layer 0 reference-data wave) or Path III (open-ended `modality_type: str`) | Andy 2026-05-17 | Pragmatic balance — evidence-grounded; sized to current state (one test athlete, one injury type); avoids 4-6 session delay of Path I. |
| 2 | v1 closed modality enum = 6 variants (drop ROM from research's 7; include exercise_substitution for unified-enum completeness even though it's already wired) | Andy 2026-05-17 | ROM parameterization is condition-specific; defer to v2 when first real case surfaces. Substitution as unified-enum representation gives Layer 4 + downstream consumers a single coherent view. |
| 3 | Phase sequencing: v1 emits current-time only; defer modality sequence to v2 (D-71) | Andy 2026-05-17 | Implicit via T1 refresh + 3A re-assessment re-running 2D against updated severity. Avoids spec complexity until first chronic-tendinopathy case forces it. |
| 4 | Muscle-group concept: NOT a v1 first-class concept; body_parts vocab + movement_constraints sufficient | Andy 2026-05-17 | Andy's wrist case maps cleanly to body_part='Wrist' + movement_constraint='Pain with wrist extension'. Muscle-group granularity (Quads/Hamstrings/Lats) is v2 when a second injury type forces it. |
| 5 | Verdict rename DOWNGRADE → ACCOMMODATE + field rename downgraded_exercises → accommodated_exercises | Andy 2026-05-17 (implicit via ratifying the modality framework) | Semantically aligned with new modality framework; clean rename since 2D is unimplemented in code; no backward-compat shim. |
| 6 | `injury_accommodation_violation_*` severity = warning (not blocker) in v1 | Architect-recommended; ratified by Andy via the amendment ratification | LLM baseline-volume fuzziness would over-trigger blocker; warning + plan-diff surfacing is appropriate v1 calibration. v2 may promote to blocker once retry rate data informs. |
| 7 | Bookkeeping bundled into this session (CLAUDE.md + backlog v42 + closing handoff) | Andy 2026-05-17 (continues PR-A + PR-B + PR-C precedent) | 6 files total; over ceiling by 1; precedented. |
| 8 | Branch stays harness-pinned `claude/spec-amendments-implementation-tTUn7` | Andy 2026-05-17 (continues PR-B + PR-C precedent) | Harness override; no rename. |

### 6.2 Stop-and-ask trigger retrospective

- **Trigger #5 fired** on Layer 2D + 2C + Layer 4 schema amendments — routed through `/plan` mode discussion before applying. Per directive: amendment authoring goes through `/plan` mode even when the substantive design pick is settled. Applied as intended.
- **Trigger #11 fired three times** (D-69 + D-70 + D-71) — routed through same `/plan` mode discussion. All three have genuine cross-layer scope (Layer 2D + 2C + Layer 4 + onboarding/Layer 1 InjuryRecord chain in various combinations). Applied as intended.

### 6.3 Carried forward to PR-D / PR-E

- **PR-D context schemas mirror the AMENDED 2D + 2C specs** — `AccommodationModality` typed union with smart-union dispatch + `accommodated_exercises` field rename + `ResolvedExercise.accommodations` propagation. Plus the 2 additional payloads (2B + 2D) the PR-C handoff sketch missed.
- **PR-E adds `injury_accommodation_violation_*` rule function** — per-modality compliance checks. Specifically calibrates: volume baseline-estimation logic (for `volume_reduction` factor enforcement); intensity baseline-estimation logic (parses `load_prescription` % 1RM + `intensity_target` midpoint per `target_metric`); tempo tuple comparison logic (±1s tolerance per component); loading-type enum cross-reference with 2C `ResolvedExercise` metadata; weekly-frequency aggregation per discipline_id.
- **`injury_violation_*` rule semantic** — clean set-membership check `every prescribed exercise_id NOT IN layer2d_payload.excluded_exercises[].exercise_id`. No body-part recomputation in Layer 4 — that's 2D's job upstream.

### 6.4 Carried forward to D-69 / D-70 / D-71 design waves

- **D-69 closed** — implementation tasks for the modality enum + decision matrix flow forward as PR-D + PR-E + future synthesizer prompt-body updates (synthesizer prompts already have closed-set coaching-flag pattern; the modality framework adds parallel structure).
- **D-70 design wave** — when first ROM-restriction case surfaces. Will need: (a) condition-specific parameter table (post-ACL flexion arcs vs shoulder impingement abduction arcs); (b) InjuryRecord schema extension for capturing pain-free arc data; (c) Layer 4 validator branch for ROM enforcement.
- **D-71 design wave** — when first chronic-tendinopathy multi-stage progression case surfaces. Will need: (a) extend AccommodationModality with modality SEQUENCE vs introducing AccommodationProgram container; (b) phase enum (`isometric` | `isotonic_hsr` | `energy_storage` | `return_to_sport`); (c) stage-transition trigger logic (symptom-based vs time-based vs hybrid); (d) 3A may need explicit recovery-phase tracking beyond severity tier.

---

## 7. Session-end verification (Rule #10)

Final pass before committing:

| Check | Result |
|---|---|
| `Layer2D_Spec.md` §5.3.4 severity_to_verdict maps to ACCOMMODATE (not DOWNGRADE) | ✅ grep |
| `Layer2D_Spec.md` §5.3.6 exists with the 6-modality table + decision matrix + fallback + contraindications + lookup function + deferred items | ✅ inspection |
| `Layer2D_Spec.md` §7 has AccommodationModality typed union with 6 variants + ExerciseRisk.accommodations field + Layer2DPayload.accommodated_exercises field rename | ✅ grep |
| `Layer2C_Spec.md` §5.6 has accommodation modality pass-through; §5.7 = renumbered coverage aggregation | ✅ grep |
| `Layer2C_Spec.md` §7 ResolvedExercise.accommodations field added | ✅ grep |
| `Layer4_Spec.md` §3.2 line 753 references 2D excluded_exercises + accommodated_exercises (not 3A active_injuries) | ✅ grep |
| `Layer4_Spec.md` §5.4 injury_violation_* rule references 2D excluded_exercises set-membership | ✅ grep |
| `Layer4_Spec.md` §5.4 has new injury_accommodation_violation_* rule | ✅ grep |
| `Layer4_Spec.md` §5.4 summary block has Injury accommodation modality framework subsection | ✅ grep |
| `Layer4_Spec.md` §13.4 wrist-injury edge case references 2D excluded_exercises | ✅ grep |
| `Project_Backlog_v42.md` exists; file-revision-header is v42; v41 inline-demoted | ✅ inspection |
| `Project_Backlog_v42.md` has D-69 + D-70 + D-71 rows | ✅ grep |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v42.md` | ✅ grep |
| `CLAUDE.md` Layer 4 row mentions "PR-C follow-on landed" | ✅ grep |
| `CLAUDE.md` Last-shipped is PR-C-followon; PR-C demoted to first Predecessor | ✅ inspection |
| `CLAUDE.md` authoritative-current-files mentions Layer 2D + 2C amendments | ✅ grep |
| `CLAUDE.md` Next-forward-move recommends PR-D against amended specs | ✅ grep |
| 159 pytest cases still pass (no code change — sanity check) | ✅ `pytest tests/` |
| Working tree shows 6 files modified / created | ✅ `git status` |
| No code changes — amendment is spec-only | ✅ inspection |

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session. Unchanged.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; no new PR §5.0 surface added (spec-only PR has no UI surface).
- Step 3 PR-D context schemas — queued next session against amended specs per §5 above.
- Step 3 PR-E validator harness — queued after PR-D; now 19 rules including new `injury_accommodation_violation_*`.

---

**End of handoff.**
