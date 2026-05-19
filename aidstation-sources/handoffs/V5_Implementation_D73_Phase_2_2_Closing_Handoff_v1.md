# D-73 Phase 2.2 — Layer 2D Injury Risk Classifier — Closing Handoff

**Session:** D-73 Phase 2.2 per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.2. Second Layer 2 runtime — `q_layer2d_injury_risk_profile_payload` per `Layer2D_Spec.md` §3-§8. Phase 2 now 2 of 5 nodes shipped.
**Date:** 2026-05-19
**Predecessor handoff:** `V5_Implementation_D73_Phase_2_1_Closing_Handoff_v1.md`
**Branch:** `claude/d73-phase-2-2` (renamed from harness-pinned `claude/v5-phase-2-implementation-56xoH` at session start per H1).
**Status:** 🟢 8 substantive files (over 5-ceiling per Andy 2026-05-19 explicit stretch authorization; precedent Layer 4 Step 4a 6-8 files). 804 tests green (784 baseline + 20 new Layer 2D tests). D-73 status note extended; Phase 2.2 closed.

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_2_1_Closing_Handoff_v1.md` §8 via `./aidstation-sources/scripts/verify-handoff.sh` + targeted greps + 784-test baseline.

| Claim | Anchor | Result |
|---|---|---|
| `layer2a/__init__.py` + `layer2a/builder.py` exist with the public entry | grep | ✅ |
| `layer2a/builder.py` SQL references the three Layer 2A catalog tables | grep | ✅ |
| `tests/test_layer2a.py` has 14 tests | `grep -c "def test_"` = 14 | ✅ |
| `python -m pytest tests/` → 784 passed | 784 passed in 1.49s | ✅ |
| `CURRENT_STATE.md` `Last shipped session` points at 2.1 handoff | inspection | ✅ |
| Backlog D-73 status note names Phase 2.1 as shipped | grep | ✅ |
| `verify-handoff.sh` reports all paths ✅ except one false-positive | `tests/test_layer2d.py` flagged ❌ — regex captured the §6.1 forward-pointer (Phase 2.2 target, not a missed claim) | ✅ (reconciled as expected false-positive — same pattern as Phase 1.3 → 2.1 transition) |

**Reconciliation note:** clean wrt predecessor. The runtime-env quirk surfaced again — cloud container's default `pytest` binary is the `uv tool install` isolated Python; documented working path is `pip install --break-system-packages pytest` + project requirements then `python -m pytest`. Same as Phase 2.1 §1.

---

## 2. Session narrative

Andy opened with the Phase 2.1 closing-handoff URL + "Check it out and let's work." After reading CLAUDE → CURRENT_STATE → CARRY_FORWARD → predecessor handoff → `verify-handoff.sh` + 784-test baseline confirmation, architect-recommended next move was **D-73 Phase 2.2 — Layer 2D injury risk** per `Upstream_Implementation_Plan_v1.md` §4 + the predecessor §6.1 forward-pointer.

Andy picked **Phase 2.2 / plan-first** (4-option AskUserQuestion gate). During /plan-first reconnaissance two substantial drifts surfaced:

**Drift 1 — outdated plan §4 table names (mitigated).** `Upstream_Implementation_Plan_v1.md` §4 row 2.2 names Layer 2D's reads as "`conditions_log` + Layer 0 `injury_profiles` + `exercise_risk_assessments`." Neither `injury_profiles` nor `exercise_risk_assessments` exist in `etl/layer0/schema.sql`. The actual `Layer2D_Spec.md` §5.2 / §5.4 / §5.6 SQL targets tables that DO exist (`sport_discipline_bridge` + `sport_exercise_map` + `exercises` + `disciplines` + `discipline_substitutes` + `discipline_training_gaps`). Conclusion: plan §4 row 2.2 is outdated text, no storage blocker. Queued as a doc-sweep nit in `CARRY_FORWARD.md`.

**Drift 2 — InjuryRecord cross-layer schema drift (Trigger #3 + #5).** `Layer2D_Spec.md` §3 + §5.3.4 + §5.3.6 depend on `InjuryRecord` fields that the deployed `injury_log` + `layer4/context.py` don't carry: `severity` 6-enum (Acute / Recovering / Chronic-Managed / Post-surgical / Structural-Permanent / Resolved — replaces the deployed 1-5 int), `injury_type` 11-enum per §B.1.1, `movement_constraints` multi-select per §B.3, `side` 4-enum. The full §5.3.6 evidence-based accommodation framework (the value-add of PR-C-followon 2026-05-17) is gated on `(injury_type, severity)` dispatch — without those columns, every accommodation collapses to the V1_FALLBACK shape.

**Stopped and surfaced 4 options to Andy** via the /plan-mode-equivalent AskUserQuestion gate: (A) pivot to Phase 2.3; (B) adapt 2D down to deployed shape (degrades modality framework); (C) bridging Phase 1.4 schema-evolution session then Phase 2.2; (D) two-layered v1+v2 impl (anti-pattern). Architect-recommended (C).

**Andy's response reframed the gap:** "existing data is test only — can be deleted; some of the fields were not necessarily meant to be user facing. in our original design things like movement constraints were meant to be referenced based on the injured body part, not entered by the user. I'm not positive that's the way we should do it. but some of this should be behind the scenes to reduce the volume of data the user has to enter."

This reduced the schema friction (no migration data risk) and surfaced an architectural question on movement_constraints user-facing vs body-part-derived. Re-survey produced a follow-up 2-question gate:

1. **Shape:** Andy picked "single session, stretch to include UI surface (~7 files)" → all of (schema evolution + pydantic + L1 builder + §B form UI + Layer 2D builder + tests) ships this session.
2. **Spec pivot:** Andy picked **keep §B.3 user-facing per spec literal** → `movement_constraints` stays a multi-select multi-checkbox in the §B injury entry form (NOT body-part-derived).

Then implemented as planned. 8 substantive files. 20 Layer 2D tests green. Full suite 784 → 804.

---

## 3. File-by-file edits

### 3.1 `init_db.py` (modified — `_PG_MIGRATIONS` extension)

5 new migration entries at the tail of `_PG_MIGRATIONS` (before the closing `]` at line 1483):

1. A callable migration (`lambda cur: ...`) that introspects `information_schema.columns` to detect whether `injury_log.severity` is still the legacy `INTEGER` type; if so, `DELETE FROM injury_log` (Andy's test-data authorization), `ALTER TABLE injury_log DROP COLUMN severity`, `ALTER TABLE injury_log ADD COLUMN severity TEXT`. Idempotent on re-run because the introspection guard sees `TEXT` and skips.
2. `ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS injury_type TEXT`
3. `ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS side TEXT NOT NULL DEFAULT 'N/A'`
4. `ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS movement_constraints JSONB`

### 3.2 `athlete.py` (modified — 4 new closed-enum constants)

After the existing `DOUBLES_FEASIBLE_CHOICES` block + before `KNOWN_SYSTEM_CATEGORIES`:

- `KNOWN_INJURY_TYPES` — 11-tuple per `Athlete_Onboarding_Data_Spec_v5.md` §B.1.1 (Acute soft tissue / Tendinopathy / Joint mechanical non-surgical / Joint mechanical surgical / Bone non-stress / Bone stress fracture / Skin surface / Nerve / Inflammatory / Post-surgical / Other-uncertain)
- `KNOWN_INJURY_SEVERITIES` — 6-tuple per §B.1 (Acute / Recovering / Chronic-Managed / Post-surgical / Structural-Permanent / Resolved)
- `KNOWN_MOVEMENT_CONSTRAINTS` — 11-tuple per §B.3
- `KNOWN_INJURY_SIDES` — 4-tuple (Left / Right / Both / N/A)

### 3.3 `layer4/context.py` (modified — `InjuryRecord` evolution)

`InjuryRecord` (line 1074) evolves:
- `severity: int | None = Field(default=None, ge=1, le=5)` → `severity: Literal[6 values] | None = None`
- New `injury_type: Literal[11 values] | None = None`
- New `side: Literal['Left', 'Right', 'Both', 'N/A'] = 'N/A'`
- New `movement_constraints: list[Literal[11 values]] = Field(default_factory=list)`
- Kept: `injury_id`, `body_part`, `description`, `status`, `start_date`, `resolved_date`, `modifications_needed`

Severity / injury_type / movement_constraints stay Optional because pre-Phase-2.2 NULL rows pass through Layer 1 cleanly (Layer 2D treats NULL injury_type as fallback bucket, NULL severity as defensive clean).

### 3.4 `layer1/builder.py` (modified — `_load_injuries`)

SELECT extended to include `severity, injury_type, side, movement_constraints` (in addition to existing columns). `InjuryRecord` construction populates the new fields; defensive `mc = r["movement_constraints"] or []` coerces JSONB NULL to empty list to satisfy `default_factory`.

### 3.5 `routes/injuries.py` (modified — UI form handler)

- Imports `KNOWN_INJURY_TYPES`, `KNOWN_INJURY_SEVERITIES`, `KNOWN_MOVEMENT_CONSTRAINTS`, `KNOWN_INJURY_SIDES` from `athlete`.
- `new_entry()` + `edit_entry()` pass the 4 enum lists to `render_template`. `edit_entry()` additionally parses `movement_constraints` JSONB → Python list (handles psycopg2 parsed-list + SQLite raw-string fallback) and passes as `entry_movement_constraints`.
- `_save()` rewritten — `enum_or_none()` helper validates each closed-enum field; `request.form.getlist('movement_constraints')` collects the multi-check; out-of-enum entries silently coerce to NULL (UI selects guarantee in-enum). 11-column INSERT / UPDATE (was 7).

### 3.6 `templates/injuries/form.html` (modified — form widgets)

- Severity field: replaced the 1-5 int select with the `severities` 6-value select; placeholder `—` allowed for nullable.
- New Injury Type 11-value select with placeholder.
- New Side 4-value select (defaults to N/A).
- New Movement Constraints multi-checkbox section (11 checkboxes in a 3-column responsive grid, populated from `movement_constraints` enum list; pre-check from `entry_movement_constraints`).
- Help text inline ("Drives Layer 2D's exercise-level keyword filtering against the injury_flags_text" etc.).

### 3.7 `layer2d/__init__.py` (new)

11 lines. Module docstring + re-exports `q_layer2d_injury_risk_profile_payload` + `Layer2DInputError`.

### 3.8 `layer2d/builder.py` (new)

~830 lines. Public entry: `q_layer2d_injury_risk_profile_payload(db, injuries, conditions, included_discipline_ids, *, etl_version_set) -> Layer2DPayload`.

**Constants block:**
- `_REQUIRED_ETL_KEYS = frozenset({"0A", "0B", "0C"})`
- `_HIGH_CARDIAC_LOAD_DISCIPLINES = frozenset({D-001, D-002, D-005, D-006, D-022, D-023, D-028})` per §5.7 rule 2
- `_KNOWN_GAP_DISCIPLINES = frozenset({D-018, D-020, D-024})` (documentation only; live set joined from `layer0.discipline_training_gaps`)
- `_POST_SURGICAL_RECENT_DAYS = 42` per §5.3.6.4 rule 3 (6 weeks)
- `_VERDICT_RANK = {clean: 0, accommodate: 1, exclude: 2}`
- `MOVEMENT_CONSTRAINT_KEYWORDS` — 11-entry per §5.3.3
- `BODY_PART_KEYWORDS` — ~45-entry per §5.5

**Modality constructors** (6 spec §5.3.6.1 modalities):
- `_vol(factor, applies_to, rationale, evidence_basis) → VolumeReductionModality`
- `_intn(factor, target_metric, rationale, evidence_basis) → IntensityReductionModality`
- `_tempo_iso(hold_s, sets, rest_s, intensity_pct_mvc, rationale, evidence_basis) → TempoModificationModality(isometric_only)`
- `_tempo_hsr(eccentric_s, concentric_s, rationale, evidence_basis) → TempoModificationModality(heavy_slow_resistance)`
- `_freq(rationale, evidence_basis, *, factor, sessions_per_week_cap, discipline_id) → FrequencyReductionModality`
- `_loading(from_type, to_type, rationale, evidence_basis) → LoadingTypeChangeModality`

**Modality tables:**
- `_v1_default_accommodations()` — 9 covered `(injury_type, severity)` permutations: Tendinopathy × (Acute / Recovering / Chronic-Managed), Acute soft tissue × (Acute / Recovering), Bone stress fracture × (Acute / Recovering), Joint non-surgical × (Acute / Recovering), Post-surgical × Post-surgical, Joint surgical × Post-surgical. Each entry carries rationale + evidence_basis citations (Rio 2015 / Cook-Purdam 2014 / Beyer 2015 / Alfredson 1998 / Silbernagel 2007 / Manca 2017 / Hendy-Lamon 2017 / Soligard 2016 / ACSM 11ed / Farthing-Zehr 2014).
- `_v1_fallback_accommodations()` — 0.7 vol + 0.7 intn IOC-consensus deload per §5.3.6.3.

**Algorithm helpers:**
- `_max_verdict(*verdicts)` + `_severity_to_verdict(severity)` (§5.3.4)
- `_strip_side(body_part)` — boundary normalizer "Left Wrist" → "Wrist" (resolves the `routes/injuries.py:BODY_PARTS` ↔ canonical 41-vocab drift code-side)
- `_body_part_verdict(exercise, current_injuries)` (§5.3.1)
- `_condition_verdict(exercise, current_conditions)` (§5.3.2)
- `_movement_constraint_verdict(exercise, current_injuries)` (§5.3.3)
- `_recommend_accommodations(exercise, current_injuries, evidence)` (§5.3.6.5) — picks driver injury from evidence → table lookup → fallback
- `_apply_phase_contraindications(base, primary, exercise)` (§5.3.6.4) — 3 rules
- `_is_recent_post_surgical(injury)` — utility for rule 3
- `_evaluate_exercise(exercise, current_injuries, current_conditions)` (§5.3.5)
- `_discipline_risk(discipline, current_injuries, history_injuries)` (§5.4) + `_risk_level_from_matches`
- `_substitute_back_check(substitute_patterns_text, current_injuries)` (§5.6.1)
- `_load_candidates(db, included_discipline_ids, version_0a, versions_0b)` (§5.2)
- `_load_disciplines(db, included_discipline_ids, version_0a)` (§5.4 source)
- `_load_substitutes(db, discipline_id, version_0a)` (§5.6; LEFT JOIN `disciplines` for back-check patterns)
- `_load_training_gaps(db, included_discipline_ids, version_0a)` (§5.7 rule 5 source)
- `_determine_hitl(current_injuries, current_conditions, discipline_risks, included_discipline_ids, gap_disciplines)` (§5.7 — 5 rules)
- `_emit_coaching_flags(discipline_risks, current_injuries, history_conditions, body_part_vocab_misses)` (§8 — 6 flag types)
- `_build_reasoning(discipline_name, risk_level, matched_current, matched_history)` (§5.4 templated text)
- `_validate_inputs(injuries, conditions, included_discipline_ids, etl_version_set)` (§4)

**Public entry orchestration:**
§4 validation → §5.1 partition records (current/history by deployed `status` semantics — Active = current, Resolved/Inactive = history) → body-part vocab miss audit → §5.2 candidates → §5.3 per-exercise verdict → §5.4 per-discipline risk profiling with on-demand substitute fetch (only when elevated/high per §11 perf budget) → §5.7 HITL → §8 flag emission → `Layer2DPayload` assembly.

### 3.9 `tests/test_layer2d.py` (new)

~570 lines. 20 tests across 11 test classes:

- **`TestInputValidation`** (5) — non-list injuries / non-list conditions / empty disciplines / missing ETL keys / non-dict etl_version_set
- **`TestCleanBaseline`** (1) — spec §13.5 fast path
- **`TestAndyBaseline`** (1) — spec §13.1 Chronic-Managed Tendinopathy on Left Wrist; asserts pushup accommodated with `tempo_modification(heavy_slow_resistance)`; D-010 elevated with substitute back-check still_at_risk
- **`TestSeverityToVerdict`** (2) — Acute → exclude; Recovering → accommodate with V1_DEFAULT (vol + intn)
- **`TestAcuteTendinopathyOverride`** (1) — spec §5.3.6.4 rule 1; Acute severity routes through EXCLUDE not ACCOMMODATE
- **`TestPostSurgicalHitl`** (2) — spec §13.2 + warn-variant (notes contain 'cleared'/'clearance'/'released to train' → severity warn not block)
- **`TestConcussionHistory`** (2) — spec §13.3 informational; current-concussion block variant
- **`TestCardiacHighLoadHitl`** (1) — §5.7 rule 2 active cardiac + D-001 → block
- **`TestRespiratoryAccommodation`** (1) — spec §13.4; contraindicated_conditions match → V1_FALLBACK (condition-driven, no driving injury)
- **`TestMultiInjuryCumulativeLoad`** (1) — spec §13.6 `multi_body_part_load_concern` fires at 3+ active
- **`TestGapTimesHighRisk`** (1) — spec §13.7 Swimrun shoulder Acute → HIGH + DTG → `gap_x_high_risk_concurrent`
- **`TestBodyPartVocabMiss`** (1) — §10 unknown body part flags + audit, no failure
- **`TestSmokeEmptyDB`** (1) — defensive: empty candidate / discipline rows → valid Layer2DPayload

All 20 green; full suite 784 → 804. Fixture pattern matches `tests/test_layer2a.py` `_FakeConn`/`_FakeCursor`.

### 3.10 `tests/test_layer1_builder.py` (test-fixture glue — not counted as substantive)

Injury fixture rows in `_queue_andy()` updated to include the new `injury_type`, `side`, `movement_constraints` keys + flip `severity` from int to enum string. Existing 19 Layer 1 tests stay green.

---

## 4. Code / tests

`tests/` count: 784 → 804 (+20). All in the new `tests/test_layer2d.py`.

Modified-file import check: `python -c "from layer2d import q_layer2d_injury_risk_profile_payload, Layer2DInputError; from layer4.context import Layer2DPayload, InjuryRecord; print('OK')"` succeeds.

`python -m pytest tests/` → **804 passed in 1.28s**.

---

## 5. Manual §5.0 verification steps (Vercel, post-merge)

3 testable steps for the manual walkthrough after this PR deploys to Neon production. Appended to `CARRY_FORWARD.md` (scenario count 57 → 60).

1. **Re-log Andy's left wrist injury via the evolved /injuries/new form.** Confirm:
   (a) `Severity Stage` select shows the 6 enum values (Acute / Recovering / Chronic-Managed / Post-surgical / Structural-Permanent / Resolved);
   (b) `Injury Type` select shows the 11 enum values per §B.1.1;
   (c) `Side` defaults to `N/A` with 4 options;
   (d) `Movement Constraints` multi-checkbox renders all 11 values from §B.3 — tick `Pain with wrist extension`, `Pain with loading`, `Pain with grip / sustained hold`;
   (e) form saves cleanly; Neon `SELECT severity, injury_type, side, movement_constraints FROM injury_log WHERE user_id = <andy>` returns the populated row with `movement_constraints` as a JSONB array.

2. **AR baseline 2D call against Andy's PGE 2026 context:**
   ```python
   from layer2d import q_layer2d_injury_risk_profile_payload
   from layer1 import build_layer1_payload
   from database import get_db
   l1 = build_layer1_payload(get_db(), <andy_user_id>)
   payload = q_layer2d_injury_risk_profile_payload(
       get_db(),
       l1.health_status.current_injuries,
       l1.health_status.health_conditions_active,
       ["D-001","D-005","D-006","D-007","D-008a","D-008b","D-010","D-011","D-013","D-014","D-015","D-016"],
       etl_version_set=<current plan-gen pin>,
   )
   ```
   Confirm: (a) no exception; (b) Pushup-class exercises in `payload.accommodated_exercises` carry `tempo_modification(heavy_slow_resistance)`; (c) `D-010` Rock Climbing → `risk_level == 'elevated'`; (d) at least one substitute with `still_at_risk=True` containing 'Wrist' in `still_at_risk_body_parts`; (e) `coaching_flags` contain `elevated_discipline_risk` + `discipline_substitution_suggested`; (f) `hitl_required is False` (Chronic-Managed isn't a §5.7 trigger).

3. **Edit-injury round-trip.** Open /injuries/{id}/edit on the row from step 1. Confirm: severity / injury_type / side selects pre-populate from the persisted row; movement_constraints checkboxes pre-check the 3 selected values; saved edits round-trip cleanly without losing fields.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**D-73 Phase 2.3 — Layer 2B terrain classifier** per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.3. Reads target event terrain description (Layer 1 §H — accessible via `race_events` row + `route_locales` shipped via D-66) + Layer 0 terrain taxonomy (`layer0.terrain_types`). Spec is 🟢 complete; no new design needed. ~4-5 files (new `layer2b/__init__.py` + `layer2b/builder.py` + `tests/test_layer2b.py` + bookkeeping). **Trigger #8 unlikely to fire** — Layer 2B's spec carries less surface than 2D.

**Soft sub-decisions to surface at 2.3 session start:**
- 2A precedent: builder signature spec-verbatim with `db` first positional.
- Phase 2.2 precedent: schema-vs-spec drift surfaced + bridged in-session. 2B's input is the `race_events.terrain` text + `route_locales.terrain_tags`; both shipped via D-66 and pydantic-typed in `layer4/context.py:RouteLocale`. Pre-recon expected to find no drift.

### 6.2 Alternative pivots

- **D-73 Phase 2.4 — Layer 2C equipment mapper** (~5-7 files, **ceiling break expected**). **/plan-mode gate** for §5 Decision Points (runtime vs pre-resolved toggle lookup; discipline-to-toggle mapping). Triggers #5 + #8 expected.
- **D-73 Phase 2.5 — Layer 2E nutrition baseline** (~4-5 files). Reads §B + §H + §I + 2A `framework_sport` + `discipline_ids` + Layer 0 fueling-tier bands (from `Layer2E_Spec.md` §3 constants until a DB table lands).
- **D-73 Phase 1.4 — D-52 catalog migration sequencing** — /plan-mode gate per plan §6 item 2. Less urgent now that Phase 2.1 + 2.2 both confirmed Layer 2 catalog reads are unaffected by D-52.
- **§B form-refresh PR** — paired alignment work for the Phase 2.2 carry-forwards: `HealthConditionRecord.system_category` 8 → 11 enum alignment + `routes/injuries.py:BODY_PARTS` canonical 41-vocab swap + `Layer2D_Spec.md` §3 "9-value enum" nit fix. ~3-4 files; doesn't move the upstream arc forward but tidies the spec-vs-deployed seam.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration (~6-8 files). Orthogonal to D-73 arc.
- **Layer 4 Step 7 env-gated scaffolding** — `ANTHROPIC_API_KEY` plumbing without a real call (~3-4 files). Strategic value: unblocks Phase 5 vertical slice.
- **Manual §5.0 walkthrough of accumulated 60 scenarios** — Andy's call when to batch-walk.

### 6.3 Operating notes for next session

Read order per Rule #13:
1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — 60 walkthrough scenarios + 8 doc nits (4 new from this session) + orthogonal tracks
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward from 1.3 §6.3 / 2.1 §6.3):** the cloud container's default `pytest` binary is `uv tool install pytest` with isolated Python; working test command is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

If picking Phase 2.3: re-read `Layer2B_Spec.md` (🟢 complete) + `layer4/context.py` `Layer2BPayload` + sub-types + `Upstream_Implementation_Plan_v1.md` §4 Phase 2.3. The Phase 2.2 cross-layer drift pattern is unlikely to repeat for 2B since 2B's inputs come from D-66 race_events / route_locales storage which was design-first.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Branch renamed `claude/v5-phase-2-implementation-56xoH` → `claude/d73-phase-2-2` | Andy 2026-05-19 (implicit per H1 precedent) | H1 rule. Matches 1.2A/B/C/1.3/2.1 precedent. |
| 2 | Builder signature spec-verbatim 4 params + `db` first positional | Architect-pick during plan-first gate | Mirrors Layer 1 builder + Layer 2A precedent. Caller (Phase 5 orchestrator) sources injuries / conditions from `Layer1HealthStatus.current_injuries` + `health_conditions_active` already loaded by `build_layer1_payload`; included_discipline_ids from Layer 2A output; etl_version_set from plan-gen pin. |
| 3 | Single-session ship at ~8 substantive files (over 5-ceiling) | Andy 2026-05-19 ("ship it all in one session") | Phase 1.4 + 2.2 collapsed into one session. Schema evolution + pydantic + L1 builder reads + §B form UI + Layer 2D builder + tests all together. Precedent: Layer 4 Step 4a 6-8 files. |
| 4 | Keep `movement_constraints` user-facing per `Athlete_Onboarding_Data_Spec_v5` §B.3 spec literal | Andy 2026-05-19 ("Keep §B.3 user-facing per spec literal") | Multi-checkbox in the §B injury entry form per spec. Alternative — body-part-derived backend lookup — would have reduced athlete data-entry burden but contradicts the spec. Andy considered both; spec literal won. Existing onboarding form burden tolerated; spec doesn't constrain Tier (assumed Tier 2 — surface to athlete on focus, optional). |
| 5 | Drop deployed test injury data + INT→TEXT severity column swap | Andy 2026-05-19 ("existing data is test only — can be deleted / lost without impact") | Clean schema swap without data migration. Lambda-callable migration introspects `information_schema.columns` for the legacy INTEGER type → only runs DELETE+DROP+ADD on first ALTER; idempotent on re-run. |
| 6 | `_HIGH_CARDIAC_LOAD_DISCIPLINES` code-side constant | Architect-pick per spec §5.7 rule 2 | Spec enumerates the disciplines (D-001/D-002/D-005/D-006/D-022/D-023/D-028). Constant lives in `layer2d/builder.py`; pattern matches Layer 2A's `_SUB_FORMAT_SPORTS`. Promotion to a Layer 0 table candidate if the set grows. |
| 7 | `_strip_side()` boundary normalizer for `routes/injuries.py:BODY_PARTS` ↔ canonical drift | Architect-pick (drift mitigation) | Existing `BODY_PARTS = ['Left Hand', 'Right Hand', ..., 'Other']` is 24 left/right-doubled; canonical `layer0.body_parts` is 41 side-less. Layer 2D normalizes "Left Wrist" → "Wrist" at the matching seam (`_body_part_verdict` / `_discipline_risk` / `_substitute_back_check`); storage stays as-entered. Alignment to canonical vocab queued as a follow-up onboarding form refresh in `CARRY_FORWARD.md`. |
| 8 | `HealthConditionRecord.system_category` 8-enum kept; spec 11-enum alignment deferred | Architect-pick | Deployed `KNOWN_SYSTEM_CATEGORIES` is lowercase 8-value; spec §B.4.1 is 11-value capitalized. Layer 2D matches the deployed enum (shared vocab between `KNOWN_SYSTEM_CATEGORIES` and `layer0.exercises.contraindicated_conditions`). §5.7 rule 2 keys on `'cardiac'` lowercase. Alignment to spec 11-enum belongs in the §B health-condition form refresh PR — outside Phase 2.2 scope. |
| 9 | Post-surgical HITL clearance detection via heuristic substring match | Architect-pick per spec §5.7 rule 1 | Spec text says "notes does not contain a parseable clearance date or the notes are empty." V1: substring scan `notes_text.lower()` for tokens `cleared` / `clearance` / `released to train`. If hit → severity=`warn`; else → `block`. Structured `cleared_at: date` field on InjuryRecord deferred to Layer 1 onboarding (spec open item 2D-10). |
| 10 | `V1_DEFAULT_ACCOMMODATIONS` covers 9 permutations (5 injury_types × 6 severities cross-product is 30; 9 covered + fallback for the rest) | Per spec §5.3.6.2 | Spec tables the high-confidence permutations only — Tendinopathy × 3 severities, Acute soft tissue × 2, Bone stress fracture × 2, Joint mechanical non-surgical × 2, Post-surgical × Post-surgical, Joint surgical × Post-surgical. Uncovered combinations fall through to V1_FALLBACK (0.7/0.7 IOC-consensus deload). Per-exercise tailoring + ROM-restriction modality + phase-sequencing all deferred to v2 per spec §5.3.6.6. |
| 11 | Substitute fetch only when discipline risk ≥ elevated (perf budget) | Architect-pick per spec §11 | Spec §11 budgets ~100ms for the §5.6 substitute queries; for AR baseline that's 15 disciplines × indexed lookup. By gating on `risk_level in {elevated, high}`, low-risk disciplines skip the round-trip entirely. The savings matter when a clean-injury athlete has all-low disciplines and Layer 2D becomes near-zero-cost. |
| 12 | 20 tests landed (over Phase 2.1's 14-test precedent) | Andy 2026-05-19 ("ship it all in one session"; test count uncalled) | Spec §13 has 7 named scenarios; landed all 7 + 5 input-validation tests + 4 severity/verdict/modality dispatch tests + 2 HITL-variant tests (block + warn for post-surgical; informational + block for concussion) + 1 body-part vocab miss + 1 smoke. Test density right-sized to the 5-rule HITL + 6-flag coaching surface + 3-signal verdict combinator. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `layer2d/__init__.py` exists and exports `q_layer2d_injury_risk_profile_payload` + `Layer2DInputError` | ✅ grep |
| `layer2d/builder.py` exists with `def q_layer2d_injury_risk_profile_payload(db, injuries, conditions, included_discipline_ids` | ✅ grep |
| `layer2d/builder.py` SQL references `layer0.sport_discipline_bridge` + `layer0.sport_exercise_map` + `layer0.exercises` + `layer0.disciplines` + `layer0.discipline_substitutes` + `layer0.discipline_training_gaps` | ✅ grep |
| `layer2d/builder.py` `_HIGH_CARDIAC_LOAD_DISCIPLINES` has 7 entries (D-001/D-002/D-005/D-006/D-022/D-023/D-028) | ✅ inspection |
| `layer2d/builder.py` `MOVEMENT_CONSTRAINT_KEYWORDS` has 11 entries per §B.3 | ✅ inspection |
| `layer2d/builder.py` `BODY_PART_KEYWORDS` has ~45 entries per §5.5 | ✅ inspection |
| `layer2d/builder.py` `_v1_default_accommodations()` returns 9 (injury_type, severity) keys | ✅ inspection |
| `layer2d/builder.py` `_apply_phase_contraindications` implements 3 spec §5.3.6.4 rules (acute tendinopathy / stress fracture / post-surgical first-6) | ✅ inspection |
| `layer2d/builder.py` `_determine_hitl` implements 5 spec §5.7 rules | ✅ inspection |
| `layer2d/builder.py` `_emit_coaching_flags` emits 6 spec §8 flag types | ✅ inspection |
| `tests/test_layer2d.py` exists with 20 tests | ✅ `grep -c "def test_" tests/test_layer2d.py` = 20 |
| `python -m pytest tests/test_layer2d.py` → 20 passed | ✅ `20 passed in 0.24s` |
| `python -m pytest tests/` → 804 passed | ✅ `804 passed in 1.28s` |
| Branch is `claude/d73-phase-2-2` (renamed per H1) | ✅ `git branch --show-current` |
| `init_db.py` `_PG_MIGRATIONS` carries the Phase 2.2 lambda migration + 3 ALTER COLUMN entries | ✅ grep |
| `athlete.py` has `KNOWN_INJURY_TYPES` (11) + `KNOWN_INJURY_SEVERITIES` (6) + `KNOWN_MOVEMENT_CONSTRAINTS` (11) + `KNOWN_INJURY_SIDES` (4) | ✅ grep |
| `layer4/context.py:InjuryRecord` has `severity: Literal[6 values] \| None` + `injury_type: Literal[11 values] \| None` + `side: Literal[4 values] = 'N/A'` + `movement_constraints: list[Literal[11 values]]` | ✅ grep |
| `layer1/builder.py:_load_injuries` SELECT reads `severity, injury_type, side, movement_constraints` | ✅ grep |
| `routes/injuries.py` imports the 4 new closed-enum lists + `_save()` writes the 4 new columns | ✅ grep |
| `templates/injuries/form.html` has injury_type / severity / side selects + movement_constraints multi-checkbox | ✅ grep |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `CURRENT_STATE.md` Layer status row 2 reads "2A + 2D runtime shipped 2026-05-19" | ✅ inspection |
| `CURRENT_STATE.md` Tests note bumped 784 → 804 | ✅ inspection |
| Backlog D-73 status note extended to name Phase 2.2 as shipped | ✅ grep |
| Backlog `## Changelog` H2 has a new 2026-05-19 Phase 2.2 entry above the 2.1 entry | ✅ grep |
| `CARRY_FORWARD.md` Manual §5.0 walkthrough count rose 57 → 60 (+3 Phase 2.2 scenarios) | ✅ inspection |
| `CARRY_FORWARD.md` doc-sweep nits gains 4 new entries (Layer2D §3 11-enum / Upstream plan §4 row 2.2 / HealthConditionRecord system_category 8-vs-11 / BODY_PARTS canonical alignment) | ✅ inspection |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (8 files; over the 5-file ceiling per Andy's explicit stretch authorization):**

1. Modified `init_db.py` — `_PG_MIGRATIONS` extended with 1 callable migration + 3 ALTER COLUMN ADD entries for `injury_log` schema evolution.
2. Modified `athlete.py` — 4 new closed-enum tuples (`KNOWN_INJURY_TYPES` 11 / `KNOWN_INJURY_SEVERITIES` 6 / `KNOWN_MOVEMENT_CONSTRAINTS` 11 / `KNOWN_INJURY_SIDES` 4) per `Athlete_Onboarding_Data_Spec_v5.md` §B.1.1 / §B.1 / §B.3.
3. Modified `layer4/context.py` — `InjuryRecord` evolved: severity int → Literal-6; new injury_type / side / movement_constraints typed fields.
4. Modified `layer1/builder.py` — `_load_injuries` SELECT + InjuryRecord construction read the new columns.
5. Modified `routes/injuries.py` — UI form handler imports the 4 enum lists; `_save()` parses + validates + writes the 4 new columns; `edit_entry()` parses movement_constraints JSONB for template pre-check.
6. Modified `templates/injuries/form.html` — severity-enum select replaces 1-5; new injury_type / side / movement_constraints multi-check widgets.
7. New `layer2d/__init__.py` — module init exporting `q_layer2d_injury_risk_profile_payload` + `Layer2DInputError`.
8. New `layer2d/builder.py` — runtime builder per `Layer2D_Spec.md` §3-§8.
9. New `tests/test_layer2d.py` — 20 tests across 11 test classes.

**Bookkeeping (5 files; outside ceiling per B3):**

10. Modified `tests/test_layer1_builder.py` — `_queue_andy()` injury fixture rows updated for the new schema (test glue, not a runtime/spec change).
11. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer 2 + Layer 1 status notes extended; Tests note bumped to 804; D-73 arc note extended.
12. Modified `aidstation-sources/Project_Backlog_v62.md` — in-place: D-73 status note extended to name Phase 2.2 as shipped; new 2026-05-19 Phase 2.2 entry in `## Changelog` (above the 2.1 entry).
13. Modified `aidstation-sources/CARRY_FORWARD.md` — Manual §5.0 walkthrough gains 3 Phase 2.2 scenarios (count 57 → 60); doc-sweep nits gains 4 entries (Layer2D §3 11-enum fix / Upstream plan §4 row 2.2 table names / HealthConditionRecord system_category alignment / BODY_PARTS canonical alignment).
14. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_2_2_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gains 3 new §5.0 walkthrough scenarios under a "D-73 Phase 2.2" sub-bullet. Scenario count rises 57 → 60.

`CARRY_FORWARD.md` doc-sweep nits section gains 4 entries:
- `Layer2D_Spec.md` §3 — "9-value enum" → 11-enum per §B.1.1 canonical.
- `Upstream_Implementation_Plan_v1.md` §4 row 2.2 — refs `injury_profiles + exercise_risk_assessments` which don't exist; fix to reference the actual spec §5.2 tables.
- `HealthConditionRecord.system_category` 8-vs-11 enum drift between deployed and `Athlete_Onboarding_Data_Spec_v5.md` §B.4.1 — alignment work for the §B health-condition form refresh PR.
- `routes/injuries.py:BODY_PARTS` 24 left/right-doubled vs canonical `layer0.body_parts` 41-vocab — alignment work for the §B injury form refresh PR.

No new orthogonal carry-forwards this session.

Layer 4 Step 4f + Step 7 + Step 8 still queued per the existing list.

---

**End of handoff.**
