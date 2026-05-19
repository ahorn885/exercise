# D-73 Phase 2.5 — Layer 2E Nutrition Baseline (Vertical Slice) — Closing Handoff

**Session:** D-73 Phase 2.5 per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.5. Fourth Layer 2 runtime — `q_layer2e_nutrition_baseline_payload` per `Layer2E_Spec.md` §3-§8 (vertical-slice scope per Andy 2026-05-19 — §5.5 supplement integration + §5.8 heat acclim STUBBED). Phase 2 now 4 of 5 shipped.
**Date:** 2026-05-19
**Predecessor handoff:** `V5_Implementation_D73_Phase_2_3_Closing_Handoff_v1.md`
**Branch:** `claude/v5-phase-2-3-implementation-dVy1A` → `claude/v5-phase-2-5-implementation-dVy1A` (H1 rename re-applied this session per Andy 2026-05-19 "Rename to scope-matched name" pick + CLAUDE.md branch-naming guidance — Phase 2.3 was shipped + merged in PR #100 so the harness-pinned name mismatched scope).
**Status:** 🟢 4 substantive files (under the 5-ceiling per CLAUDE.md). 850 tests green (819 baseline + 31 new Layer 2E tests). D-73 status note extended; Phase 2.5 closed.

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_2_3_Closing_Handoff_v1.md` §8 via `./aidstation-sources/scripts/verify-handoff.sh` + targeted greps + 819-test baseline.

| Claim | Anchor | Result |
|---|---|---|
| `layer2b/__init__.py` + `layer2b/builder.py` exist | grep | ✅ |
| `tests/test_layer2b.py` has 15 tests | `grep -c "def test_"` = 15 | ✅ |
| `python -m pytest tests/` → 819 passed | 819 passed in 2.79s after env bootstrap | ✅ |
| `CURRENT_STATE.md` `Last shipped session` points at 2.3 handoff | inspection | ✅ |
| Backlog D-73 status note names Phase 2.3 as shipped | grep | ✅ |
| `verify-handoff.sh` reports all paths ✅ except one false-positive | `tests/test_layer2e.py` flagged ❌ — regex captured §6.1 forward-pointer to Phase 2.5; same pattern as Phase 2.2 → 2.3 transition | ✅ (reconciled as expected false-positive) |
| Branch `claude/v5-phase-2-3-implementation-dVy1A` is harness-pinned but mismatches scope (Phase 2.3 was merged PR #100) | inspection | ✅ surfaced + resolved via Andy pick |

**Reconciliation note:** clean wrt predecessor. The runtime-env quirk repeated — cloud container's default `pytest` is `uv tool install` isolated Python; documented working path `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` then `python -m pytest tests/` per Phase 2.2 §1 / Phase 2.3 §1.

---

## 2. Session narrative

Andy opened with the Phase 2.3 closing-handoff URL + "check it out and let's work." After reading CLAUDE → CURRENT_STATE → CARRY_FORWARD → predecessor handoff → `verify-handoff.sh` + 819-test baseline confirmation, architect-recommended next move was **D-73 Phase 2.5 — Layer 2E nutrition baseline** per the predecessor §6.1 forward-pointer.

Andy picked **Phase 2.5** + **rename branch to scope-matched name** (2-question session-start AskUserQuestion gate).

**Branch rename executed immediately**: `git branch -m claude/v5-phase-2-3-implementation-dVy1A claude/v5-phase-2-5-implementation-dVy1A`. Andy's explicit pick is the "explicit permission" CLAUDE.md branch-naming guidance + the GitHub Action directive both reference.

**Recon surfaced a substantial drift inventory** between `Layer2E_Spec.md` §3 spec input shapes and deployed `Layer1*` types — substantially bigger than Phase 2.2/2.3 drift surfaces. The 4-option scope gate (vertical slice / land §I.1 + PM stubs first / pivot to 2.4 / form-refresh PR) routed to **Vertical slice 2E (recommended)**:

**Drift inventory** (spec §3 vs deployed `Layer1*`):

| Spec input | Spec shape | Deployed shape | Severity |
|---|---|---|---|
| `AthleteDemographics.sex` | `'M'`/`'F'` | `Layer1Identity.sex: 'male'/'female'` | minor (casing) |
| `AthleteDemographics.body_weight_kg` | required `float` | `Layer1Performance.body_weight_kg: float \| None` | None-handling |
| `AthleteDemographics.ffm_kg` | optional | not deployed (open item 2E-1) — Mifflin fallback | spec-anticipated |
| `HealthRecords.conditions[].system_category` | 11-value | 8-value lowercase (Phase 2.2 carry-forward) | medium |
| `HealthRecords.conditions[].status` | `'Current'`/`'History'` | `'Active'`/`'Resolved'`/`'Inactive'` | vocab translation |
| `FoodAllergyRecord.name` | free text + multi-select | `allergen_category: 12-value enum` | shape |
| `FoodAllergyRecord.severity` | 5-value enum | 3-value lowercase | vocab |
| `medications: list[str]` | string list | `list[MedicationRecord]` w/ class enum | shape |
| `LifestyleRecovery.supplements` | `list[AthleteSupplementRecord]` (structured FK to `supplement_vocabulary`) | `supplement_protocol_notes: str \| None` (free text!) | **MAJOR — §5.5 hard blocker** |
| `LifestyleRecovery.salt_tolerance` | `Low/Standard/High` | `low/moderate/high` | vocab |
| `LifestyleRecovery.caffeine_race_day_strategy` | `Same as daily/Loaded/Avoid/Variable` | `caffeine_loading/taper/maintain/avoid` | vocab |
| `LifestyleRecovery.{fueling_format_pref, fueling_shift_triggers, gi_triggers, sleep_dep, altitude_acclim}` | structured sub-types | flat fields on `Layer1Lifestyle` | shape |
| `PlanManagementState` + `HeatAcclimState` | spec §5.8 names contract | **does not exist** (spec itself says "Plan Management spec, not yet written") | **MAJOR — §5.8 blocker** |

**Spec staleness:** §6.1 + §14 names D-26 `supplement_vocabulary` as a "hard blocker for 2E implementation" — actually **resolved** per `Project_Backlog_v62.md` D-26 row (FC-1, 2026-05-11; 25 seed entries via `etl/sources/migrate_supplement_vocabulary.sql`). Phase 2.5 §5.5 stub is rooted in input shape gap (`Layer1Lifestyle.supplement_protocol_notes: str`), not vocab availability. Filed as carry-forward doc nit.

**Pre-work in `layer4/context.py`** (lines 489-628) was extensive: `MacroTargets`, `DailyPhaseTargets`, `DailyNutritionBaseline`, `CaffeineRacedayPlan`, `RaceDayFueling`, `IntegratedSupplement`, `RaceDaySupplementSuggestion`, `Layer2ECoachingFlag`, `Layer2EHitlItem`, `SupplementIntegrationPayload`, `DietaryPatternFlag`, `SleepDepFuelingOverlay`, `HeatAcclimEventAdjustment`, `Layer2EPayload` already typed. No 2E **output** scaffolding work required; only a new input type for `Layer2ETargetEvent`.

**Decision tree resolved as:**
- Vertical slice ships §5.2 + §5.3 + §5.4 + §5.6 + simplified §5.7
- Stub §5.5 + §5.8 with named coaching flags
- Add `Layer2ETargetEvent` to `layer4/context.py` as a vertical-slice subset of spec §3 `TargetEvent`
- Translate drift at the builder seam (not via wrapper types)
- 4 substantive files

Implementation landed as planned. 4 substantive files. 31 Layer 2E tests green. Full suite 819 → 850.

---

## 3. File-by-file edits

### 3.1 `layer4/context.py` (modified — `Layer2ETargetEvent` added)

New input type inserted just inside the `# ─── Layer 2E — nutrition baseline (Layer2E_Spec.md §3 + §7)` block (which previously held only output types):

```python
class Layer2ETargetEvent(_Base):
    event_id: str
    event_name: str
    event_date: date
    framework_sport: str
    estimated_duration_hr: float = Field(gt=0)
    aid_stations: int | None = None
```

Module-level comment names this as the vertical-slice subset of spec §3 `TargetEvent`. Deferred fields (`race_terrain_pct`, `race_pack_weight_kg`, `team_format`, `race_specific_nutrition_restrictions`) don't drive any v1 path; `aid_stations` retained because §5.9 gate 5 (anaphylaxis × aid-station-bound event) consumes it.

### 3.2 `layer2e/__init__.py` (new)

11 lines. Re-exports `q_layer2e_nutrition_baseline_payload` + `Layer2EInputError`.

### 3.3 `layer2e/builder.py` (new)

~640 lines. Public entry:

```python
def q_layer2e_nutrition_baseline_payload(
    db,
    identity: Layer1Identity,
    health_status: Layer1HealthStatus,
    performance: Layer1Performance,
    target_events: list[Layer2ETargetEvent],
    lifestyle: Layer1Lifestyle,
    included_disciplines: list[Layer2ADiscipline],
    framework_sport: str,
    current_phase: Literal["Base", "Build", "Peak", "Taper"],
    *,
    etl_version_set: dict[str, str],
    athlete_id: str | None = None,
    today: date | None = None,
) -> Layer2EPayload
```

**Module docstring** documents the vertical-slice scope explicitly: which sections ship full, which are stubbed (§5.5 + §5.8), the drift translations at each boundary, and the cross-phase-visibility decision for `current_phase`.

**Constants block:**

- `_REQUIRED_ETL_KEYS = frozenset({"0A"})` — vertical slice only needs 0A for the `phase_load_weekly_totals` lookup; 0B/0C requirements relax until §5.5 de-stubs.
- `_PHASES = ("Base", "Build", "Peak", "Taper")` — matches deployed `_PHASE_CANON` Title Case from `etl/layer0/extractors/sports_framework.py:64`.
- `_MULTIPLIER_BANDS` — spec §5.2.2 4×4 matrix (Phase × volume tier).
- `_PHASE_DEFAULT_MULTIPLIER` — spec §5.2.2 D-07 fallback.
- `_MACRO_BANDS` — spec §5.3.1 per-phase {cho_low, cho_high, protein_low, protein_high, fat_min} g/kg.
- `_FUELING_BANDS` — spec §5.4.2 5-tier × 7-col {cho_low/high, na_low/high, fluid_low/high, protein_after_hr}.
- `_SPORT_PROFILE_CHO_MOD` — spec §5.4.3 6-profile → upper CHO band modifier.
- `_ENDURANCE_PROFILE` — discipline_id → {Pure endurance / Mixed / Technical / Strength} for §5.3.3 CHO band position.
- `_DISCIPLINE_PROFILE_VOTE` — discipline_id → sport-profile vote (running / cycling / swimming / paddling / multi_sport / skimo).
- `_STRENGTH_DOMINANT_IDS = frozenset({"D-014"})` — §5.3.3 protein band position.
- `_SALT_TOLERANCE_NORM` — deployed `low/moderate/high` → spec `Low/Standard/High`.
- `_CAFFEINE_STRATEGY_NORM` — deployed `caffeine_loading/taper/maintain/avoid` → spec `Loaded/Same as daily/Same as daily/Avoid`. The `taper` → `Same as daily` mapping is documented as a v1 choice (deployed `taper` has no direct spec equivalent).
- `_FORMAT_OPTIONS` — spec §5.4.5 per-tier base options.
- `_SLEEP_DEP_DURATION_THRESHOLD_HR = 20.0` — spec §5.7 trigger.

**Algorithm helpers:**

- `_validate_inputs` — §4 preconditions (sex enum, body_weight floor, height floor, target_events list typing, non-empty disciplines, non-empty framework_sport, current_phase enum, etl_version_set keys).
- `_years_between(dob, today)` — age computation; defaults to 35 when dob is None (spec doesn't require dob for Mifflin coefficient).
- `_compute_bmr(identity, performance, today)` — Mifflin path is default; Cunningham auto-switches via `getattr(performance, 'ffm_kg', None)` per open item 2E-1.
- `_volume_tier_index(weekly_hours_mid)` — spec §5.2.2 4-bucket mapping.
- `_load_phase_weekly_hours(db, framework_sport, phase, etl_version)` — single SELECT on `layer0.phase_load_weekly_totals`.
- `_compute_activity_multiplier` — calls `_load_phase_weekly_hours`; falls back to `_PHASE_DEFAULT_MULTIPLIER` + sets `fallback=True` flag.
- `_compute_daily_calorie_target(bmr, multiplier)` — `round((bmr × multiplier) / 50) × 50`.
- `_discipline_weight(d)` — pulls `d.load_weight.value` with fallback to `system_default` then 0.
- `_cho_band_position` / `_protein_band_position` — spec §5.3.3 weighted-share computations.
- `_compute_macros_for_phase` — band-position lookup + fat-floor enforcement (sets `fat_floor_constrained=True` when triggered).
- `_classify_duration_tier(hours)` — spec §5.4.1 5-tier mapping.
- `_resolve_sport_profile(disciplines)` — weighted vote; <50% top-share falls to `multi_sport` per spec §5.4.3.
- `_sport_modifier(sport_profile)` / `_salt_tolerance_modifier(deployed_value)` — band modifier dispatchers.
- `_build_caffeine_plan(lifestyle, body_weight_kg, event)` — translates deployed → spec strategy; returns None for `Avoid` / None tolerance; `Same as daily` divides `caffeine_daily_mg_estimate` by 16 (wake window); `Loaded` ships 4.5 mg/kg pre-race midpoint.
- `_recommend_formats(duration_tier, fueling_format_pref, gi_triggers_known)` — substring scan on the free-text `gi_triggers_known` (deployed shape) → blocks gels for fructose/maltodext mentions, blocks chews for polyol/sorbitol mentions; ranks remaining by athlete pref.
- `_build_race_day_fueling` — composes one `RaceDayFueling` record per event.
- `_stub_supplement_integration(lifestyle, target_events)` — returns empty integrated/race_day_suggestions + `supplements_not_structured` coaching flag (only when `supplement_protocol_notes` non-empty).
- `_has_pattern` / `_dietary_pattern_adjustments` — case-insensitive substring matching against deployed `list[str]`; Vegan triggers 3 flags, Low-FODMAP triggers 1.
- `_build_sleep_dep_overlay` — for events >20hr, builds spec §5.7 overlay; surfaces `sleep_dep_data_missing` flag when flat `sleep_deprivation_*` fields are empty.
- `_stub_heat_acclim_adjustments` — every event surfaces `temp_signal='unknown'` + `race_temp_unknown` flag.
- `_emit_hitl_items` — §5.9 gate 5 only (anaphylaxis × aid_stations > 0). One item per (event × allergy) cross.
- `_emit_general_coaching_flags` — §8.1 `pla_missing_for_sport_phase` (per fallback phase); §8.6 `hrt_bmr_limitation`; §8.9 `low_calorie_target_relative_to_rmr` (per phase target < BMR × 1.2).

**Public entry orchestration:**

§4 validation → §5.2 BMR + per-phase activity multiplier (4 DB reads, one per phase) → §5.3 macros per phase → §5.4 race-day fueling per event → §5.5 stub → §5.6 dietary pattern flags → §5.7 sleep-dep overlay → §5.8 stub → §5.9 HITL items → §8 general flags → `Layer2EPayload` assembly with `hitl_required` derived from `block_level=='block'` items.

### 3.4 `tests/test_layer2e.py` (new)

~580 lines. 31 tests across 12 test classes:

- **`TestInputValidation`** (8) — missing sex / low body weight / low height / empty disciplines / empty framework_sport / bad phase / missing ETL key / target_events typed-list check.
- **`TestPGEBaseline`** (3) — Andy PGE 2026 baseline (BMR Mifflin ~1710 / Build mult 1.90 / extended_expedition tier / sleep_dep overlay / heat-acclim stub / no HITL); supplement_protocol_notes triggers stub flag; no notes → no flag.
- **`TestTimeBasedMode`** (1) — §13.7: empty target_events → daily baseline still computes; empty race_day_fueling; no overlay; no heat adjustments; no HITL.
- **`TestPLAFallback`** (1) — §13.8: Swimrun's missing PLA rows → all 4 phases fall to default multiplier (1.55/1.75/1.90/1.70); 4 `pla_missing_for_sport_phase` flags.
- **`TestCunninghamPath`** (1) — §13.9: `ffm_kg=62.0` injected via `object.__setattr__` (Layer1Performance doesn't carry the field yet); BMR 1709.2.
- **`TestDietaryPatternFlags`** (3) — vegan triggers `{b12, iron, epa_dha}`; Low-FODMAP triggers `race_fueling_format_constraint`; omnivore triggers nothing.
- **`TestRaceDayFueling`** (4) — short tier bands (running-dominant 0.85 × upper CHO = 76.5); salt-tolerance low shrinks Na 20%; caffeine 'caffeine_loading' produces 360 mg (4.5 × 80) pre-race; caffeine 'avoid' returns None.
- **`TestSleepDepOverlay`** (3) — fires for 27hr event; doesn't fire for 4.5hr event; `sleep_dep_data_missing` fires when flat fields empty.
- **`TestHeatAcclimStub`** (1) — every event surfaces `temp_signal='unknown'` + `race_temp_unknown` flag.
- **`TestHITLGate5`** (3) — anaphylaxis + aid_stations=8 → 1 HITL item, block_level='block'; aid_stations=0 → no HITL; non-anaphylaxis severity → no HITL.
- **`TestCoachingFlags`** (2) — `hrt_bmr_limitation` fires on HRT-class active medication + Mifflin path; `low_calorie_target_relative_to_rmr` gate exercised (structure assertion).
- **`TestMultipleEvents`** (1) — §13.10: 3 distinct tiers (short/long/extended_expedition); sleep_dep overlay applies only to WTM + PGE (both >20hr).

All 31 green; full suite 819 → 850. Fixture pattern matches `tests/test_layer2b.py` `_FakeConn`/`_FakeCursor`.

---

## 4. Code / tests

`tests/` count: 819 → 850 (+31). All in the new `tests/test_layer2e.py`.

Modified-file import check: `python -c "from layer2e import q_layer2e_nutrition_baseline_payload, Layer2EInputError; from layer4.context import Layer2EPayload, Layer2ETargetEvent; print('OK')"` succeeds.

`python -m pytest tests/` → **850 passed in 2.28s**.

---

## 5. Manual §5.0 verification steps (Vercel, post-merge)

2 testable steps appended to `CARRY_FORWARD.md` (scenario count 62 → 64):

1. **AR baseline 2E call against Andy's live PGE 2026 context** (once Layer 1 `Layer1Performance.body_weight_kg` is captured against Andy's live row — currently a v1 onboarding gap):

   ```python
   from layer2e import q_layer2e_nutrition_baseline_payload
   from layer4.context import Layer2ETargetEvent
   from layer1 import build_layer1_payload
   from layer2a import q_layer2a_discipline_classifier_payload
   from database import get_db
   from datetime import date

   db = get_db()
   layer1 = build_layer1_payload(db, andy_user_id)
   layer2a = q_layer2a_discipline_classifier_payload(
       db, "Adventure Racing",
       estimated_race_duration_hours=56,
       navigation_required=True,
       etl_version_set=<current plan-gen pin>,
   )
   payload = q_layer2e_nutrition_baseline_payload(
       db,
       identity=layer1.identity,
       health_status=layer1.health_status,
       performance=layer1.performance,
       target_events=[
           Layer2ETargetEvent(
               event_id="pge-2026",
               event_name="Pocket Gopher Extreme 2026",
               event_date=date(2026, 7, 17),
               framework_sport="Adventure Racing",
               estimated_duration_hr=56.0,
               aid_stations=0,
           ),
       ],
       lifestyle=layer1.lifestyle,
       included_disciplines=[d for d in layer2a.disciplines if d.inclusion == "included"],
       framework_sport="Adventure Racing",
       current_phase="Build",
       etl_version_set=<current plan-gen pin>,
       athlete_id=str(andy_user_id),
   )
   ```

   Confirm: (a) no exception; (b) `payload.bmr_method == 'mifflin_st_jeor'`; (c) `payload.daily_nutrition_baseline.per_phase` populated for all 4 phases; (d) `payload.race_day_fueling[0].duration_tier == 'tier_extended_expedition'`; (e) `payload.sleep_dep_overlay is not None` (PGE 56hr > 20hr threshold); (f) `payload.heat_acclim_adjustments[0].temp_signal == 'unknown'` + `race_temp_unknown` coaching flag (stub path until Plan Management spec lands); (g) `payload.hitl_required is False` (PGE `aid_stations=0` blocks gate 5; no anaphylaxis allergy on Andy's record); (h) `supplements_not_structured` flag fires iff Andy has `supplement_protocol_notes` populated.

2. **§I.1 form-refresh dry-run 2E call** — once `routes/onboarding.py` §I.1 captures structured supplements + Layer 1 builder emits a structured `supplements` list against `Layer1Lifestyle` (paired with `layer0.supplement_vocabulary`), re-run the same 2E call and confirm `payload.supplement_integration.integrated` populates non-empty with `is_known=True` records for each athlete-protocol supplement; `payload.supplement_integration.race_day_suggestions` populates with tier-appropriate suggestions; `supplements_not_structured` flag stops firing.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**D-73 Phase 2.4 — Layer 2C equipment mapper** per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.4. Last 2X runtime. Spec ~515 lines; the §5 Decision Points are flagged as `/plan-mode` gate triggers (#5 + #8 — runtime vs pre-resolved toggle lookup; discipline-to-toggle mapping location code vs DB). **Ceiling break expected** (5-7 substantive files per upstream plan §4). Closes the Phase 2 arc; unblocks Phase 5 orchestrator's per-locale-per-discipline coverage matrix.

**Soft sub-decisions to surface at 2.4 session start:**

- 2A / 2D / 2B / 2E precedent: builder signature spec-verbatim with `db` first positional.
- §5 Decision Points (~2 architectural choices) — `/plan-mode` first; don't implement before Andy picks.
- Cross-input drift watch: §J locale fields (Open Item 2B-2 — `locale_profiles` carries free-text + tags; canonical TRN-xxx multi-select required) overlaps with 2C; consider whether the §J refresh PR should land before 2C or paired with it.

### 6.2 Alternative pivots

- **§H.2 / §J / §I.1 form-refresh PR** — paired alignment to wire Layer 2B + Layer 2E input-source surfaces simultaneously. Closes Open Items 2B-2 + 2B-3 + Layer 2E open items 2E-1 (FFM promotion) + 2E-6 (supplement_vocabulary integration via §I.1 structured supplements) + 2E-12 (pregnancy status capture) + `Layer2B_Spec.md` §13.1 TRN-008/009 typo fix. ~6-8 files (multi-section form refresh; would be its own ceiling-break). De-stubs Layer 2E §5.5 supplements when shipped.
- **Plan Management spec authorship** — de-stubs Layer 2E §5.8 heat acclim. Per Layer 2E open items 2E-2/3/4, the `PlanManagementState` (current_phase, heat_acclim_state, expected_race_temp_c per event) + `HeatAcclimState` contracts are unwritten. PM spec is downstream of Layer 3 but its contract surfaces affect Layer 2E + Layer 4. Spec session, no implementation. ~3-4 spec files.
- **D-73 Phase 1.4 — D-52 catalog migration sequencing** — /plan-mode gate per `Upstream_Implementation_Plan_v1.md` §6 item 2. Less urgent now that Phase 2.1 + 2.2 + 2.3 + 2.5 all confirmed Layer 2 catalog reads are unaffected by D-52.
- **§B form-refresh PR** — paired alignment for the Phase 2.2 carry-forwards: `HealthConditionRecord.system_category` 8 → 11 enum alignment + `routes/injuries.py:BODY_PARTS` canonical 41-vocab swap + `Layer2D_Spec.md` §3 "9-value enum" nit fix. ~3-4 files; doesn't move the upstream arc forward but tidies the spec-vs-deployed seam.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration (~6-8 files). Orthogonal to D-73 arc.
- **Layer 4 Step 7 env-gated scaffolding** — `ANTHROPIC_API_KEY` plumbing without a real call (~3-4 files). Strategic value: unblocks Phase 5 vertical slice.
- **Manual §5.0 walkthrough of accumulated 64 scenarios** — Andy's call when to batch-walk.

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — 64 walkthrough scenarios + ~15 doc nits (6 new from this session) + orthogonal tracks
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward from 1.3 / 2.1 / 2.2 / 2.3):** the cloud container's default `pytest` binary is `uv tool install pytest` with isolated Python; working test command is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**Branch-naming H1 rename precedent re-confirmed this session.** When the harness pins a name that mismatches scope (e.g. previous session's PR was merged + new session opens on the old branch name), surface to Andy; rename per Andy's pick. Phase 2.3 deferred the rename per the GitHub Action's "explicit permission" wording; Phase 2.5 reverted to the H1 default of renaming after Andy gave the explicit permission via the 2-question gate.

If picking Phase 2.4: re-read `Layer2C_Spec.md` (~515 lines; §5 has named Decision Points) + `layer4/context.py` `Layer2CPayload` + sub-types + `Upstream_Implementation_Plan_v1.md` §4 Phase 2.4. The Phase 2.5 drift-inventory pattern may repeat — 2C's input shapes against deployed `locale_profiles` / `locale_equipment_overrides` / `locale_toggle_overrides` / `gym_profiles` need a recon pass before implementation.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Branch renamed `claude/v5-phase-2-3-implementation-dVy1A` → `claude/v5-phase-2-5-implementation-dVy1A` | Andy 2026-05-19 | Andy picked "Rename to scope-matched name" over "Keep harness-pinned name" via session-start 2-question gate. Phase 2.3 shipped + merged in PR #100, so the harness-pinned name was stale. CLAUDE.md branch-naming H1 guidance re-applied; the GitHub Action's "NEVER push to a different branch without explicit permission" honored by Andy's explicit pick. Matches 1.2A/B/C/1.3/2.1/2.2 precedent (Phase 2.3 was the outlier). |
| 2 | Scope = Vertical slice 2E (§5.5 + §5.8 stubbed) | Andy 2026-05-19 | Drift inventory between Layer2E_Spec.md §3 spec inputs and deployed `Layer1*` types surfaced two genuine blockers — `Layer1Lifestyle.supplement_protocol_notes: str` vs spec `list[AthleteSupplementRecord]` for §5.5; PlanManagementState + HeatAcclimState contracts not yet authored for §5.8. Vertical-slice covers ~70% of the algorithm with clearly-named stubs that fail loud via coaching flags. Alternatives considered: "Land §I.1 + PM stubs first" (de-stubs but ~5-7 files split across two sessions); "Pivot to Phase 2.4 (2C)" (over-ceiling); "§H.2/§J form-refresh PR" (smaller scope, no Phase 2 forward progress). |
| 3 | Builder signature spec-shape with `db` first positional + `*` keyword-only `etl_version_set` + optional `athlete_id` + optional `today` | Architect-pick per Phase 1.3 / 2.1 / 2.2 / 2.3 precedent | Spec §3 signature doesn't show `db` because spec §5 omits the SQL plumbing concern. Matching the established `q_layerN_*_payload(db, ...)` shape keeps the orchestrator's caller-side signatures uniform. `*` keyword-only on `etl_version_set` mirrors 2A + 2D + 2B precedent. `athlete_id` + `today` as optional kwargs serve as test-injection seams without polluting the spec-positional surface. |
| 4 | `Layer2ETargetEvent` introduced in `layer4/context.py` as vertical-slice subset of spec §3 `TargetEvent` | Architect-pick | Spec §3 `TargetEvent` has fields (race_terrain_pct, race_pack_weight_kg, team_format, race_specific_nutrition_restrictions) that don't drive any v1 builder path. Deployed `RaceEventPayload` has a meaningfully different shape (race_event_id: int vs event_id: str; no estimated_duration_hr field; no aid_stations field). Vertical-slice type ships event_id / event_name / event_date / framework_sport / estimated_duration_hr / aid_stations — minimum the builder needs. Closer to spec-full alignment lands with the §H.2 form refresh capturing the missing fields. |
| 5 | Cross-phase visibility per spec §5.2.3 — `current_phase` parameter retained for spec-shape but algorithm loops all 4 phases | Architect-pick per spec | Spec §5.2.3 says "2E computes targets for all four phases (Base / Build / Peak / Taper), not only current_phase." `current_phase` parameter is accepted for spec-shape compliance + validation gate, but the daily-baseline computation iterates `_PHASES` regardless. Documented in the module docstring. |
| 6 | Drift translation at the builder seam (not via wrapper types) | Architect-pick per Phase 2.2 / 2.3 precedent | Translation maps (`_SALT_TOLERANCE_NORM`, `_CAFFEINE_STRATEGY_NORM`) + helper functions (`_has_pattern`) live inside the builder rather than introducing aspirational `LifestyleRecovery` / `HealthRecords` translation wrapper types. Mirrors Phase 2.2 (2D's `_strip_side` normalizer) and Phase 2.3 (2B's TRN regex). Avoids a maintenance fork between deployed and spec-aspirational types. |
| 7 | §5.5 supplement integration STUBBED + §5.8 heat acclim STUBBED with named coaching flags | Per scope pick + spec | §5.5 stub roots in input shape gap (`Layer1Lifestyle.supplement_protocol_notes: str` vs spec's structured `list[AthleteSupplementRecord]`); fires `supplements_not_structured` flag when notes are non-empty. §5.8 stub roots in unwritten PlanManagementState + HeatAcclimState contracts (spec §5.8 itself names this open); every event surfaces `temp_signal='unknown'` + `race_temp_unknown` flag. NOT blocked by `supplement_vocabulary` table — D-26 resolved 2026-05-11 + 25 seeds shipped via `etl/sources/migrate_supplement_vocabulary.sql`; spec §6.1 + §14 "hard blocker" language is stale (filed as carry-forward doc nit). |
| 8 | `current_phase` validation runs but parameter is otherwise unused — kept for spec-shape compliance | Per spec §5.2.3 + decision 5 | Trade-off considered: prune the parameter (cleaner) vs retain (spec-shape). Retain wins because (a) future scope additions could consume current_phase (e.g., active-phase emphasis in race-day suggestions), (b) the parameter validates an enum constraint that catches caller-side typos, (c) removing it now would force a signature breakage when §5.5 / §5.8 de-stub. |
| 9 | Caffeine deployed `taper` → spec `Same as daily` translation | Architect-pick | Deployed `caffeine_race_day_strategy='taper'` (gradually reduce intake before race) has no direct spec equivalent. v1 maps to `Same as daily` (maintain pattern) over `Avoid` because: (a) taper-strategy athletes typically still consume caffeine on race day, just at reduced volume — `Same as daily` returns a per-hr trickle; (b) `Avoid` returns `None` which would suppress all caffeine planning; (c) future onboarding refresh can introduce a fifth spec value if the gap matters. Surfaces in test `test_caffeine_loaded_strategy` and the module docstring. |
| 10 | `_ENDURANCE_PROFILE` + `_DISCIPLINE_PROFILE_VOTE` + `_STRENGTH_DOMINANT_IDS` ship code-side | Per spec §6.2 promotion candidate pattern | Spec §6.2 names race-fueling bands, sport endurance modifier, dietary pattern adjustments as Layer 0 promotion candidates. v1 ships as code-side data per "ship as code, promote to data when curation matters" — mirrors 2D's `_HIGH_CARDIAC_LOAD_DISCIPLINES` + 2B's `_COACHED_INTRO_KEYWORDS`. Covers D-001..D-016 AR set + common non-AR ids; promotes to `sport_endurance_profile` Layer 0 table when curation pressure rises (currently zero pressure — Andy's PGE is the only active athlete). |
| 11 | HITL gate 5 emits one item per (event × anaphylaxis allergy) pair | Per spec §5.9 | Multi-allergy + multi-event athletes get multiple HITL crosses. Spec §5.9 gate 5 doesn't restrict pairing; defensive cross-product. Test `test_anaphylaxis_x_aid_stations_blocks` covers single pair; the per-pair semantics extend cleanly. |
| 12 | 31 tests landed | Andy 2026-05-19 (test count uncalled) | Spec §13 has 10 named scenarios; landed 6 (§13.1 / §13.3 / §13.7 / §13.8 / §13.9 / §13.10) + 8 input-validation tests + ~17 other coverage tests across drift translations, stub paths, HITL gate 5, and coaching flags. Test density right-sized to the 5-tier × 7-col fueling matrix + 4-phase × 5-col macro matrix + 3-flag dietary + sleep-dep overlay + stubs + HITL. Skipped §13.2 (hot marathon × low heat acclim — needs Plan Management input), §13.4 (Cardiac × race-day caffeine HITL gate 2 — needs structured supplements), §13.5 (pregnancy HITL gates 3+4 — needs pregnancy field), §13.6 (anaphylaxis × race aid — covered by HITL gate 5 generalization). |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer2e/__init__.py` exists and exports `q_layer2e_nutrition_baseline_payload` + `Layer2EInputError` | ✅ grep |
| `layer2e/builder.py` exists with `def q_layer2e_nutrition_baseline_payload(db, identity, health_status, performance, target_events, lifestyle, included_disciplines, framework_sport, current_phase` | ✅ grep |
| `layer2e/builder.py` SQL references `layer0.phase_load_weekly_totals` | ✅ grep |
| `layer2e/builder.py` `_REQUIRED_ETL_KEYS = frozenset({"0A"})` (vertical slice) | ✅ inspection |
| `layer2e/builder.py` `_PHASES = ("Base", "Build", "Peak", "Taper")` Title Case | ✅ inspection |
| `layer2e/builder.py` `_MULTIPLIER_BANDS` per spec §5.2.2 4-row × 4-col matrix | ✅ inspection |
| `layer2e/builder.py` `_FUELING_BANDS` per spec §5.4.2 5-tier × 7-col | ✅ inspection |
| `layer2e/builder.py` `_SALT_TOLERANCE_NORM` + `_CAFFEINE_STRATEGY_NORM` drift translations | ✅ inspection |
| `layer2e/builder.py` `_stub_supplement_integration` returns empty integrated + `supplements_not_structured` flag conditional on notes | ✅ inspection |
| `layer2e/builder.py` `_stub_heat_acclim_adjustments` returns `temp_signal='unknown'` per event + `race_temp_unknown` flag | ✅ inspection |
| `layer2e/builder.py` `_emit_hitl_items` fires §5.9 gate 5 only (anaphylaxis × aid_stations) | ✅ inspection |
| `layer2e/builder.py` per-phase loop in `q_layer2e_nutrition_baseline_payload` iterates `_PHASES` regardless of `current_phase` parameter | ✅ inspection |
| `layer2e/builder.py` `getattr(performance, 'ffm_kg', None)` for Cunningham auto-switch | ✅ grep |
| `layer4/context.py:Layer2ETargetEvent` exists with `event_id: str` + `event_name: str` + `event_date: date` + `framework_sport: str` + `estimated_duration_hr: float = Field(gt=0)` + `aid_stations: int \| None = None` | ✅ grep |
| `tests/test_layer2e.py` exists with 31 tests | ✅ `grep -c "def test_" tests/test_layer2e.py` = 31 |
| `python -m pytest tests/test_layer2e.py` → 31 passed | ✅ `31 passed in 0.35s` |
| `python -m pytest tests/` → 850 passed | ✅ `850 passed in 2.28s` |
| Branch is `claude/v5-phase-2-5-implementation-dVy1A` (renamed this session per Decision 1) | ✅ `git branch --show-current` |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `CURRENT_STATE.md` Layer status row 2 reads "2A + 2D + 2B + 2E runtime shipped 2026-05-19" | ✅ inspection |
| `CURRENT_STATE.md` Tests note bumped 819 → 850 | ✅ inspection |
| Backlog D-73 status note extended to name Phase 2.5 as shipped | ✅ grep |
| Backlog `## Changelog` H2 has a new 2026-05-19 Phase 2.5 entry above the 2.3 entry | ✅ grep |
| `CARRY_FORWARD.md` Manual §5.0 walkthrough count rose 62 → 64 (+2 Phase 2.5 scenarios) | ✅ inspection |
| `CARRY_FORWARD.md` doc-sweep nits gains 6 new entries (D-26 staleness audit / §I.1 structured-supplement form refresh / Plan Management contract authorship / Layer2ETargetEvent vertical-slice / Layer1Performance ffm_kg / spec §3 input shape drift) | ✅ inspection |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (4 files; under the 5-file ceiling per CLAUDE.md):**

1. Modified `layer4/context.py` — new `Layer2ETargetEvent` input type (vertical-slice subset of `Layer2E_Spec.md` §3 `TargetEvent`).
2. New `layer2e/__init__.py` — module init exporting `q_layer2e_nutrition_baseline_payload` + `Layer2EInputError`.
3. New `layer2e/builder.py` — vertical-slice runtime builder per `Layer2E_Spec.md` §3-§8 (§5.5 + §5.8 stubbed).
4. New `tests/test_layer2e.py` — 31 tests across 12 test classes.

**Bookkeeping (4 files; outside ceiling per B3):**

5. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer 2 status note extended; Tests note bumped to 850; D-73 arc note extended.
6. Modified `aidstation-sources/Project_Backlog_v62.md` — in-place: D-73 status note extended to name Phase 2.5 as shipped; new 2026-05-19 Phase 2.5 entry in `## Changelog` (above the 2.3 entry).
7. Modified `aidstation-sources/CARRY_FORWARD.md` — Manual §5.0 walkthrough gains 2 Phase 2.5 scenarios (count 62 → 64); doc-sweep nits gains 6 entries (D-26 staleness / §I.1 structured-supplement form refresh / Plan Management contract authorship / Layer2E §3 TargetEvent vertical-slice / Layer1Performance ffm_kg / spec §3 input shape drift).
8. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_2_5_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gains 2 new §5.0 walkthrough scenarios under a "D-73 Phase 2.5" sub-bullet. Scenario count rises 62 → 64.

`CARRY_FORWARD.md` doc-sweep nits section gains 6 entries:

- `Layer2E_Spec.md` §6.1 + §14 — D-26 `supplement_vocabulary` "hard blocker" language is stale (resolved 2026-05-11). Spec footnote ~3-line edit.
- §I.1 structured-supplement form refresh — Layer 2E §5.5 de-stub blocker. ~4-6 files including onboarding form + Layer 1 builder + storage schema.
- Plan Management contract authorship — Layer 2E §5.8 + open items 2E-2/3/4 de-stub blocker. Spec session, no implementation.
- `Layer2E_Spec.md` §3 `TargetEvent` shape vs deployed `RaceEventPayload` — Phase 2.5 introduced `Layer2ETargetEvent` vertical-slice subset; full alignment via §H.2 form refresh.
- `Layer1Performance.ffm_kg` field promotion — Layer 2E open item 2E-1; builder auto-switches to Cunningham via `getattr` at promotion.
- `Layer2E_Spec.md` §3 input shape drift — sex / status / allergy / salt_tolerance / caffeine_race_day_strategy / structured §I sub-types all translate at the builder seam. Spec §3 sub-shape rewrite (~25-line edit) belongs in the next session that touches `Layer2E_Spec.md` once Layer 1 §I.1 + §B form refresh land.

No new orthogonal carry-forwards this session.

Layer 4 Step 4f + Step 7 + Step 8 still queued per the existing list.

---

**End of handoff.**
