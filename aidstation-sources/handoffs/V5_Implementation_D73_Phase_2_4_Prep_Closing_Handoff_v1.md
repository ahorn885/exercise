# D-73 Phase 2.4-Prep — Layer 2C Data Substrate — Closing Handoff

**Session:** D-73 Phase 2.4-Prep per `Upstream_Implementation_Plan_v1.md` §4 Phase 2.4 (split into Prep + Builder per Andy 2026-05-19). Schema + ETL extractor work landing the 4 columns Layer 2C will read. Layer 2C builder itself (`q_layer2c_equipment_mapper_payload`) queued for the next session.
**Date:** 2026-05-19
**Predecessor handoff:** `V5_Implementation_D73_Phase_2_5_Closing_Handoff_v1.md`
**Branch:** `claude/implement-phase-2-5-handoff-04kYj` (harness-pinned for this session; mismatched scope — Phase 2.5 already merged in PR #101) → `claude/v5-phase-2-4-implementation-04kYj` (renamed per CLAUDE.md branch-naming rule + Andy 2026-05-19 explicit "Rename per scope" pick; matches Phase 2.5 H1 rename precedent).
**Status:** 🟢 6 substantive files (over the 5-ceiling per Andy 2026-05-19 explicit "Add exercise_db.py too" pick on the 6-vs-5 plan-mode gate). 866 tests green (850 baseline + 16 new Layer 2C prep tests). D-73 status note extended; Phase 2.4-Prep closed.

---

## 1. Session-start verification (Rule #9)

Anchor-check of `V5_Implementation_D73_Phase_2_5_Closing_Handoff_v1.md` §8 via `./aidstation-sources/scripts/verify-handoff.sh` + targeted greps + 850-test baseline.

| Claim | Anchor | Result |
|---|---|---|
| `layer2e/__init__.py` + `layer2e/builder.py` exist | grep | ✅ |
| `tests/test_layer2e.py` has 31 tests | `grep -c "def test_"` = 31 | ✅ |
| `python -m pytest tests/` → 850 passed | 850 passed in 2.72s after env bootstrap | ✅ |
| `CURRENT_STATE.md` `Last shipped session` points at 2.5 handoff | inspection | ✅ |
| Backlog D-73 status note names Phase 2.5 as shipped | grep | ✅ |
| `verify-handoff.sh` reports all paths ✅ | full report green | ✅ |
| Branch `claude/v5-phase-2-5-implementation-dVy1A` was merged via PR #101 + current harness-pinned branch is `claude/implement-phase-2-5-handoff-04kYj` (mismatched scope) | `git log --oneline -5` confirms PR #101 merge; `git branch --show-current` confirms harness-pinned name | ✅ surfaced + resolved via branch rename |

**Reconciliation note:** clean wrt predecessor. The runtime-env quirk repeated — cloud container's default `pytest` is `uv tool install` isolated Python; documented working path `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` then `python -m pytest tests/` per Phase 2.2 §1 / Phase 2.3 §1 / Phase 2.5 §1.

---

## 2. Session narrative

Andy opened with the Phase 2.5 closing-handoff URL + "check this out and lets work." After reading CLAUDE → CURRENT_STATE → CARRY_FORWARD → predecessor handoff → `verify-handoff.sh` + 850-test baseline confirmation, architect-recommended next move was **D-73 Phase 2.4 — Layer 2C equipment mapper** per the predecessor §6.1 forward-pointer.

Andy picked **Phase 2.4 — Layer 2C** + **rename branch to scope-matched name** (2-question session-start AskUserQuestion gate).

**Branch rename executed immediately**: `git branch -m claude/implement-phase-2-5-handoff-04kYj claude/v5-phase-2-4-implementation-04kYj`. Andy's explicit pick is the "explicit permission" the CLAUDE.md branch-naming guidance + the GitHub Action directive both reference.

**Recon surfaced a substantial drift inventory** between `Layer2C_Spec.md` §3-§8 spec inputs and deployed `layer0.*` types — larger than Phase 2.5's drift surface. Four substantive gaps:

| Spec reference | Deployed reality | Severity |
|---|---|---|
| `layer0.exercises.equipment_substitutes_structured JSONB` (§5.4 — CNF-structured `{substitute_text, equipment_required: [[a,b],[c]], is_improvised}`) | Migration `migrate_exercises_substitutes_structured.sql` exists on-disk but **NOT applied** to deployed schema + **NOT populated**. Deployed `equipment_substitutes` carries `{"standard": [...], "improvised": [...]}` flat text lists (no CNF). Populate JSON `etl/sources/parsed_substitutes.json` (154 exercises × 510 entries) already shipped from prior K-parser work. | **MAJOR — Tier 2 hard blocker** |
| `layer0.exercises.terrain_required TEXT[]` (§5.2 pass-through; §7 `ResolvedExercise.terrain_required`) | Migration exists, **NOT applied**. ETL extractor `exercise_db.py:extract_exercises` already extracts via `vocabulary_transforms.transform_equipment_string` (tuple return); `run.py` already includes the column in the INSERT column list. **Only the column-add was missing.** | minor (already wired everywhere except the column) |
| `layer0.sport_specific_gear_toggles.also_satisfies TEXT[]` (§6) | Column **doesn't exist + no migration**. Single use case in spec: `Climbing — roped` → `Rappelling/abseiling`. | minor (1 hard-coded case) |
| `layer0.sport_specific_gear_toggles.gated_discipline_ids TEXT[]` (§8.3) | Column **doesn't exist + no migration**. Discipline-to-toggle mapping for `toggle_off_for_discipline` coaching flag. | minor (3 known cases: Climbing—roped → D-010; Rappelling/abseiling → D-011; Snowshoeing setup → D-015) |

Layer 1 §J locale/cluster wiring (where the 2C builder's `locale_equipment_pool` + `cluster_locale_ids` + `cluster_gear_toggle_states` arguments come from in production) is **not 2C's concern** per spec §3 signature (2C takes primitives, not a Layer1Payload). The Phase 5 orchestrator will read deployed `locale_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides` + `gym_profiles` (already shipped per D-58/59/60/61) and pass primitives to 2C.

**Spec §5 Decision Points** (the named /plan-mode gates per `Upstream_Implementation_Plan_v1.md` §4 row 2.4 + `Layer2C_Spec.md` §5.1 + §8.3):

- **DP1 (§5.1)** — Toggle definition lookup at runtime vs pre-resolved by Layer 1. Spec recommends (A) runtime.
- **DP2 (§8.3)** — Discipline-to-toggle mapping location: (a) hard-code in 2C code vs (b) new column on `sport_specific_gear_toggles`. Spec recommends (a) for v1, defers (b) to FC-1.

**The 4-option scope gate routed to "Split: Prep first, then 2C":**

| Scope | Files | Tradeoff | Andy's pick |
|---|---|---|---|
| **A: Vertical slice 2C (Phase 2.5 pattern)** | 4-5 | Stub Tier 2 → degraded result; stub terrain pass-through as `[]`; hard-code single `also_satisfies`. Most of the §5.4 CNF algorithm never executes against real data. Tier 2 is the spec's core value (athlete does "bench press at hotel via DBs" instead of dropping the exercise); stubbing it guts the spec. | not picked |
| **B: Migrations + full 2C in one session** | 6-9 (over ceiling) | Most spec-faithful but cross-layer trigger + ETL re-run on Neon (operationally riskier than `_PG_MIGRATIONS` because Layer 0 lives outside the v1 app's deploy boundary). | not picked |
| **C: Split — Prep PR first, then 2C** | Prep ~3-4; 2.4 ~5-6 | Two sessions but each lands well-shaped. Lets Andy review migrations independently. **Picked by Andy 2026-05-19.** | ✅ |
| **D: Pivot — postpone 2.4 entirely** | n/a | Phase 2 arc stays at 4/5. Step 4f or 7 has cleaner dependencies. | not picked |

**DP1 = (A) Runtime lookup** picked (spec recommendation; cheap; no Layer 1 disturbance).

**DP2 = (b) Structured column** picked (Andy diverged from spec's hard-code-for-v1 recommendation; tradeoff: structured carries traceability + survives spec evolution across non-AR sports).

**Pre-work** in `layer4/context.py:307-361` was already complete: `DisciplineCoverage` / `ResolutionDetail` / `ResolvedExercise` / `Layer2CCoachingFlag` / `Layer2CPayload` all typed including the §5.6 amendment (`accommodations: list[AccommodationModality]` pass-through from 2D). No payload work needed in the Prep session; payload work also not needed in the Phase 2.4 Builder session.

**Pre-work in `etl/sources/`** also significant — `parsed_substitutes.json` (4510 lines, 154 exercises × 510 entries) + `populate_substitutes_structured.py` (186 lines) both pre-shipped from prior K-parser work. Phase 2.4-Prep's choice was whether to keep the populate script as a separate operational step (5-file scope) or route the structured data through the ETL extractor on the same code path as the rest of the workbook reads (6-file scope, over ceiling but operationally cleaner). Andy picked the 6-file scope on the plan-mode gate after recon surfaced the choice.

**Implementation landed as planned. 6 substantive files. 16 Layer 2C-prep tests green. Full suite 850 → 866.**

---

## 3. File-by-file edits

### 3.1 `etl/layer0/schema.sql` (modified — 4 columns added to canonical schema)

Two table blocks extended with inline spec-section anchor comments:

- `layer0.exercises` gains `terrain_required TEXT[]` (between `equipment_required` and `injury_flags_text`) + `equipment_substitutes_structured JSONB` (between `equipment_substitutes` and `physical_proxies`).
- `layer0.sport_specific_gear_toggles` gains `also_satisfies TEXT[]` + `gated_discipline_ids TEXT[]` (both between `paired_equipment_categories` and `etl_version`).

Comments inline cite `Layer2C_Spec.md §5.1 / §5.2 / §5.4 / §6 / §7 / §8.3` + the relevant migration filenames + the DP1/DP2 picks.

Canonical schema (fresh DB init); incremental migrations (existing Neon DB) live in `aidstation-sources/migrations/`.

### 3.2 `aidstation-sources/migrations/migrate_toggles_v3_columns.sql` (new — combined toggle migration)

Standard BEGIN/COMMIT pattern matching the existing `migrate_exercises_*` files:

1. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS also_satisfies TEXT[]`
2. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS gated_discipline_ids TEXT[]`
3. Three `UPDATE` statements populating active rows for `Climbing — roped`, `Rappelling / abseiling`, `Snowshoeing setup` per `Vocabulary_Audit_v2.md §4`.
4. `DO $$ ... $$` verification block: column-existence checks + Climbing — roped population sanity check. **Uses NOTICE-fallback** (not EXCEPTION) when no active row exists — safe to run pre-ETL on a fresh DB; the "ETL doesn't carry populated values" failure mode is caught by the test suite + by the ETL re-run carrying the data from the code-side constants in `vocabulary.py`.

Idempotent on re-run. Header block documents Andy's DP2 (b) divergence from spec's (a) recommendation + the 2C contract for both fields.

### 3.3 `etl/layer0/extractors/vocabulary.py` (modified — `_parse_gear_toggles` emits 2 new fields)

New module-level constants (10 LOC):

```python
_TOGGLE_ALSO_SATISFIES: dict[str, list[str]] = {
    "Climbing — roped": ["Rappelling / abseiling"],
}

_TOGGLE_GATED_DISCIPLINES: dict[str, list[str]] = {
    "Climbing — roped": ["D-010"],
    "Rappelling / abseiling": ["D-011"],
    "Snowshoeing setup": ["D-015"],
}
```

`_parse_gear_toggles` now attaches both fields per toggle dict row (falling to `[]` for toggles absent from the constants). Pattern matches Layer 2D's `_HIGH_CARDIAC_LOAD_DISCIPLINES` + Layer 2B's `_COACHED_INTRO_KEYWORDS` precedents. Promotion to a Layer 0 reference table is a future option if non-AR sports add enough cases.

### 3.4 `etl/layer0/extractors/exercise_db.py` (modified — structured substitutes loader)

New module-level constant + new function (~30 LOC):

- `_PARSED_SUBSTITUTES_JSON` — `Path(__file__).parent.parent.parent / "sources" / "parsed_substitutes.json"`
- `load_parsed_substitutes_structured(path=None) -> dict[str, list[dict[str, Any]]]` — reads the K-parser output (154 exercises × 510 entries) and returns `{exercise_id: substitutes[]}` map. Returns empty dict when file missing (loud-fallback pattern matching Layer 2E PLA missing-row handling).

`extract_exercises` modified to call `load_parsed_substitutes_structured()` once (top of function, outside the row loop) + attach `structured_by_ex_id.get(ex_id, [])` to each row's `equipment_substitutes_structured` field. Loader is intentionally not cached at module-level — re-loading per call is cheap (~4MB JSON), keeps test fixtures clean, and the `extract_exercises` function is itself only called once per ETL run.

### 3.5 `etl/layer0/run.py` (modified — INSERT column lists + value tuples extended)

Two INSERTs extended:

1. `layer0.exercises` INSERT — adds `equipment_substitutes_structured` to the column list (between `equipment_substitutes` and `physical_proxies`) + adds `to_jsonb(r["equipment_substitutes_structured"])` to the value tuple. `terrain_required` was already wired in both the column list (line 423 pre-edit) and value tuple (line 434 pre-edit) — no change needed there.
2. `layer0.sport_specific_gear_toggles` INSERT — adds `also_satisfies` + `gated_discipline_ids` to the column list (after `paired_equipment_categories`) + adds `r["also_satisfies"]` + `r["gated_discipline_ids"]` to the value tuple.

Inline comments anchor to Layer2C_Spec.md sections.

### 3.6 `tests/test_layer2c_prep.py` (new)

~290 lines. 16 tests across 3 test classes:

- **`TestGearToggleParser`** (6) — Climbing — roped also_satisfies + gates D-010; Rappelling gates D-011 + no also_satisfies; Snowshoeing setup emphasis stripped + gates D-015; unknown toggle gets empty lists; paired_equipment_categories regression-empty (Prep doesn't change extraction); constants self-consistency (every `also_satisfies` target is a `gated_discipline_ids` key — catches rename drift).
- **`TestParsedSubstitutesLoader`** (5) — default path loads EX001 ("Back Squat (Barbell)") with at least one substitute + at least one improvised; CNF list-of-lists shape per substitute; missing-path returns empty dict; custom-path round-trip (tmp_path JSON fixture with 2 entries); entry without ex_id silently skipped.
- **`TestSchemaSubstrate`** (5) — `schema.sql` declares `terrain_required` + `equipment_substitutes_structured` on `layer0.exercises`; declares `also_satisfies` + `gated_discipline_ids` on `layer0.sport_specific_gear_toggles`; `migrate_toggles_v3_columns.sql` carries all 3 known-case populations + `ARRAY[...]` shape + 3 discipline IDs; `Layer2CPayload` regression smoke covering shipped 5 sub-types end-to-end (including coaching-flag enum guard via `pytest.raises`).

All 16 green; full suite 850 → 866. Fixture pattern matches `tests/test_layer2b.py` style (pytest classes, minimal markdown fixtures, tmp_path for JSON round-trip).

---

## 4. Code / tests

`tests/` count: 850 → 866 (+16). All in the new `tests/test_layer2c_prep.py`.

Module-import sanity: `python -c "from etl.layer0.extractors.exercise_db import load_parsed_substitutes_structured; from etl.layer0.extractors.vocabulary import _TOGGLE_ALSO_SATISFIES, _TOGGLE_GATED_DISCIPLINES, _parse_gear_toggles; from layer4.context import Layer2CPayload; print('OK')"` succeeds.

`python -m pytest tests/` → **866 passed in 2.72s**.

---

## 5. Operational sequence for Andy on Neon

Phase 2.4-Prep ships the schema scaffolding + ETL extractor wiring + tests. The actual deployed Neon DB needs Andy to operationally apply the 3 SQL migrations + re-run ETL before the Phase 2.4 Layer 2C builder session can proceed.

**Sequence:**

```bash
# 1. Apply migration: equipment_substitutes_structured column (already on-disk, never applied)
psql $DATABASE_URL -f aidstation-sources/migrations/migrate_exercises_substitutes_structured.sql

# 2. Apply migration: terrain_required column (already on-disk, never applied)
psql $DATABASE_URL -f aidstation-sources/migrations/migrate_exercises_terrain_required.sql

# 3. Apply migration: also_satisfies + gated_discipline_ids columns (new this session)
psql $DATABASE_URL -f aidstation-sources/migrations/migrate_toggles_v3_columns.sql

# 4. Re-run ETL to populate the 4 new columns on a NEW etl_version
#    (equipment_substitutes_structured from parsed_substitutes.json via extractor;
#     terrain_required from vocabulary_transforms; also_satisfies +
#     gated_discipline_ids from the new code-side constants in vocabulary.py)
python -m etl.layer0.run
```

Note: step 3's migration uses NOTICE-fallback on missing active rows, so it's safe to run BEFORE step 4 even on a fresh DB. Steps 1 + 2 only add columns; existing rows have NULL until step 4 populates.

Note: for any fresh Neon DB that started from an old `0A-v1.3.1`-era schema, apply `aidstation-sources/migrations/migrate_schema_reconcile_2026_05_19.sql` between step 3 and step 4 to rename legacy `hours_low` / `hours_high` columns on `layer0.phase_load_weekly_totals` to canonical `weekly_low_hours` / `weekly_high_hours` (otherwise step 4 fails with `UndefinedColumn: weekly_low_hours`).

**Spot-check post-step-3** (independent of step 4):

```sql
SELECT toggle_name, also_satisfies, gated_discipline_ids
  FROM layer0.sport_specific_gear_toggles
 WHERE toggle_name IN ('Climbing — roped','Rappelling / abseiling','Snowshoeing setup')
   AND superseded_at IS NULL;
```

Expected: 3 rows with `also_satisfies={Rappelling / abseiling},{},{}` and `gated_discipline_ids={D-010},{D-011},{D-015}` respectively.

**Spot-check post-step-4:**

```sql
SELECT exercise_id, terrain_required, jsonb_array_length(equipment_substitutes_structured)
  FROM layer0.exercises
 WHERE superseded_at IS NULL
   AND exercise_id IN ('EX001','EX002','EX020')
 ORDER BY exercise_id;
```

Expected: 3 rows with non-null `terrain_required` (may be empty array if exercise has no terrain tokens) + populated `jsonb_array_length` for the known-populated exercises in `parsed_substitutes.json` (EX001 has 4 entries; EX002 should also have ≥1; EX020 should have a non-empty array).

Once steps 1-4 land green on Neon, Phase 2.4 Layer 2C builder session can proceed.

CARRY_FORWARD.md gains 3 §5.0 walkthrough scenarios for the on-Neon verification (count 64 → 67).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**D-73 Phase 2.4 — Layer 2C equipment mapper builder** per `Upstream_Implementation_Plan_v1.md` §4 row 2.4 + this session's Prep substrate. Builder ships `q_layer2c_equipment_mapper_payload(locale_id, locale_equipment_pool, cluster_locale_ids, cluster_gear_toggle_states, included_discipline_ids, etl_version_set) -> Layer2CPayload` per `Layer2C_Spec.md` §3.

**Decision Points already resolved** (no /plan-mode gate at session start):
- DP1 (A) Runtime lookup — 2C queries `layer0.sport_specific_gear_toggles` at call time to expand `paired_equipment_categories` + `also_satisfies`.
- DP2 (b) Structured column — 2C reads `gated_discipline_ids` from the toggle row directly; no hard-coded mapping in 2C code.

**Estimated 4-5 substantive files:**
1. NEW `layer2c/__init__.py` — re-exports `q_layer2c_equipment_mapper_payload` + `Layer2CInputError`
2. NEW `layer2c/builder.py` — full §5 algorithm + §8 coaching flags + §10 edge cases
3. NEW `tests/test_layer2c.py` — §4 input validation + §13 scenarios (Andy at home / Andy at hotel / empty pool / multi-discipline dedup) + §5.3-5.5 tier resolution + §8 coaching flags + §10 edge cases
4. Possibly `layer4/context.py` — minor type-tightening if any (existing `Layer2CPayload` shape ships unchanged per §7)
5. Closing handoff (bookkeeping; outside ceiling)

**Hard prerequisite:** Andy operationally applies the 3 SQL migrations + re-runs ETL on Neon per §5 of this handoff before the builder session can connect against real `layer0.*` data. The builder + tests can be developed against `_FakeConn` fixtures without Neon, but the §5.0 manual walkthrough scenarios for Andy's PGE 2026 context need real data.

**Spec touchpoint edits paired with the builder session** (per CARRY_FORWARD.md additions):
- `Layer2C_Spec.md` §5.1 + §8.3 Decision Point annotations ("✅ Resolved 2026-05-19 — DP1 (A) Runtime; DP2 (b) Structured column")
- `Layer2C_Spec.md` §10 edge case addition (exercise present in `layer0.exercises` but absent from `parsed_substitutes.json` → empty substitutes; Tier 2 returns None)
- `Layer2C_Spec.md` Open Item 2C-2 row flip ("✅ Resolved 2026-05-19 — structured column shipped via Phase 2.4-Prep")
- `Upstream_Implementation_Plan_v1.md` §4 row 2.4 update (file count revised down to ~4-5; /plan-mode gate removed since DPs resolved)

### 6.2 Alternative pivots

- **§H.2 / §J / §I.1 form-refresh PR** — paired alignment to wire Layer 2B + Layer 2E input-source surfaces simultaneously. Closes Open Items 2B-2 + 2B-3 + Layer 2E open items 2E-1 (FFM promotion) + 2E-6 (supplement_vocabulary integration via §I.1 structured supplements) + 2E-12 (pregnancy status capture). ~6-8 files (multi-section form refresh; over ceiling). De-stubs Layer 2E §5.5 supplements when shipped.
- **Plan Management spec authorship** — de-stubs Layer 2E §5.8 heat acclim. Per Layer 2E open items 2E-2/3/4, the `PlanManagementState` + `HeatAcclimState` contracts are unwritten. Spec session, no implementation. ~3-4 spec files.
- **D-73 Phase 1.4 — D-52 catalog migration sequencing** — /plan-mode gate per `Upstream_Implementation_Plan_v1.md` §6 item 2. Less urgent now that Phase 2.1 + 2.2 + 2.3 + 2.5 + Phase 2.4-Prep all confirmed Layer 2 catalog reads are unaffected by D-52.
- **§B form-refresh PR** — paired alignment for the Phase 2.2 carry-forwards: `HealthConditionRecord.system_category` 8 → 11 enum alignment + `routes/injuries.py:BODY_PARTS` canonical 41-vocab swap + `Layer2D_Spec.md` §3 "9-value enum" nit fix. ~3-4 files; doesn't move the upstream arc forward but tidies the spec-vs-deployed seam.
- **Layer 4 Step 4f** — `llm_layer4_plan_create` Pattern A orchestration (~6-8 files). Orthogonal to D-73 arc.
- **Layer 4 Step 7 env-gated scaffolding** — `ANTHROPIC_API_KEY` plumbing without a real call (~3-4 files). Strategic value: unblocks Phase 5 vertical slice.
- **Manual §5.0 walkthrough of accumulated 67 scenarios** — Andy's call when to batch-walk.

### 6.3 Operating notes for next session

Read order per Rule #13:

1. `aidstation-sources/CLAUDE.md` — stable rules
2. `aidstation-sources/CURRENT_STATE.md` — points at this handoff
3. `aidstation-sources/CARRY_FORWARD.md` — 67 walkthrough scenarios + ~20 doc nits (5 new from this session) + orthogonal tracks
4. This handoff
5. `./aidstation-sources/scripts/verify-handoff.sh` — should report all paths ✅ + working-tree clean

**Runtime-env note (carries forward from 1.3 / 2.1 / 2.2 / 2.3 / 2.5):** the cloud container's default `pytest` binary is `uv tool install pytest` with isolated Python; working test command is `pip install --break-system-packages pytest && pip install --break-system-packages --ignore-installed -r requirements.txt` (one-time per fresh container) then `python -m pytest tests/`.

**Branch-naming H1 rename precedent re-confirmed this session.** When the harness pins a name that mismatches scope (e.g. previous session's PR was merged + new session opens on a name that implies the previous session's scope), surface to Andy; rename per Andy's pick. Phase 2.5 re-established the rename precedent after Phase 2.3 deferred it; Phase 2.4-Prep continues the pattern.

**If picking Phase 2.4 builder:** re-read `Layer2C_Spec.md` (~515 lines; §5 Decision Points pre-resolved by this session's DP1 + DP2 picks) + `layer4/context.py:307-361` (`Layer2CPayload` + 5 sub-types already shipped; §5.6 amendment included) + this session's `etl/layer0/schema.sql` deltas + `etl/sources/parsed_substitutes.json` sample shape. Confirm Andy has run the 3 migrations + ETL re-run on Neon per §5 above before opening the builder session; if not, surface to Andy at session start.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Branch renamed `claude/implement-phase-2-5-handoff-04kYj` → `claude/v5-phase-2-4-implementation-04kYj` | Andy 2026-05-19 | Andy picked "Rename per scope" via session-start 2-question gate. Harness-pinned name implied "implement the 2.5 handoff" but Phase 2.5 was already merged via PR #101. CLAUDE.md branch-naming H1 guidance applied; matches Phase 2.5 + 1.2A/B/C/1.3/2.1/2.2 H1 rename precedent. |
| 2 | Scope = Split (Prep first, then 2C) | Andy 2026-05-19 | Drift inventory surfaced 4 substantive Layer 0 schema gaps. Alternatives considered: Vertical slice 2C (Phase 2.5 pattern — would have stubbed Tier 2 which is the spec's core value); Migrations-plus-full-2C in one session (over ceiling + cross-layer trigger + ETL re-run on Neon); Pivot to Step 4f or 7 (postpones 2.4 entirely; Phase 2 arc stays at 4/5). Split keeps each session well-shaped + lets Andy review migrations independently. Two-session cost acceptable vs the 10-week PGE 2026 forcing function (race_week_brief auto-fires 2026-07-03). |
| 3 | DP1 (§5.1 Toggle lookup) = (A) Runtime lookup in 2C | Andy 2026-05-19 + spec recommendation | 2C queries `layer0.sport_specific_gear_toggles` per call to expand `paired_equipment_categories` + `also_satisfies`. 1 extra cheap query (11 rows, indexed by UNIQUE (toggle_name, etl_version)). No Layer 1 disturbance vs alternative (B) which would have required typed toggle-state record on `Layer1Payload` carrying `implied_equipment[]`. Spec §5.1 explicitly recommends (A); v1 alignment. |
| 4 | DP2 (§8.3 Discipline-to-toggle mapping) = (b) Structured column on `sport_specific_gear_toggles` | Andy 2026-05-19 (divergence from spec recommendation) | Spec §8.3 says "For first implementation, use (a) hard-coded mapping. Add (b) during FC-1 spec v4 work." Andy picked (b) over (a) at session start. Tradeoff: structured carries traceability + survives spec evolution across non-AR sports (only 3 cases in AR but more come online for SkiMo, fencing-relay, swim disciplines later); hard-coded would have been faster but accumulates as tech debt. Open Item 2C-2 closes 2026-05-19 in a different way than spec anticipated — carries to closing-handoff doc-nit for §6.1 row flip in the Phase 2.4 builder session. |
| 5 | Add `etl/layer0/extractors/exercise_db.py` to scope (6-file vs 5-file gate) | Andy 2026-05-19 (over ceiling) | Plan-mode gate offered 5-file scope (route `equipment_substitutes_structured` via existing separate `populate_substitutes_structured.py` operational step) vs 6-file scope (route via ETL extractor on the same code path as the rest of the workbook reads). Andy picked 6-file. Rationale: deletes operational drift between schema migration + populate run; single ETL re-run lands all 4 columns populated vs the alternative requiring a separate populate-script invocation; existing `populate_substitutes_structured.py` becomes redundant after this PR but stays as audit-trail. Over ceiling acknowledged; precedent: Phase 2.2 shipped 8 substantive files with explicit Andy stretch authorization. |
| 6 | `also_satisfies` + `gated_discipline_ids` populate via code-side constants in `vocabulary.py` (not via SQL only) | Architect-pick per Layer 2D / 2B precedent | The migration carries the populated data for active rows, but next ETL re-run would create NEW versioned rows with NULL fields (per `UNIQUE (toggle_name, etl_version)` constraint) unless the extractor produces them. Code-side constants in `_parse_gear_toggles` mirror Layer 2D `_HIGH_CARDIAC_LOAD_DISCIPLINES` + Layer 2B `_COACHED_INTRO_KEYWORDS` patterns ("ship as code, promote to data when curation matters"). Promotion to a Layer 0 reference table is a future option. |
| 7 | Migration uses NOTICE-fallback (not EXCEPTION) on missing active rows | Architect-pick | The DO-block verification checks column existence (EXCEPTION on failure) and Climbing — roped population (NOTICE-fallback when no active row exists). Lets the migration run pre-ETL on a fresh DB without erroring. The "ETL doesn't carry populated values" failure mode is caught by the test suite (vocabulary._parse_gear_toggles tests assert emit shape) + by the next ETL re-run populating from code-side constants. |
| 8 | Combined toggle-column migration in a single SQL file (`migrate_toggles_v3_columns.sql`) over 2 separate files | Architect-pick | Both `also_satisfies` + `gated_discipline_ids` are tightly coupled to the same `sport_specific_gear_toggles` table + sourced from the same `Vocabulary_Audit_v2.md` §4 facts. One file keeps the audit trail compact. Existing `migrate_exercises_substitutes_structured.sql` + `migrate_exercises_terrain_required.sql` files (separate, both on `layer0.exercises`) NOT touched — already correct as-shipped; only `etl/layer0/schema.sql` adds those columns for fresh-DB init. |
| 9 | `terrain_required` ETL wiring required ZERO new code (only schema column-add) | Discovery, not a decision | Recon found that `exercise_db.py:extract_exercises` already extracts via `vocabulary_transforms.transform_equipment_string` (tuple return) + `run.py` already includes the column in the INSERT column list. Only the column-add to `schema.sql` was missing. Saved 2 files from the original 7-file scope estimate. |
| 10 | `load_parsed_substitutes_structured` re-loads JSON per call (not cached at module-level) | Architect-pick | Re-loading per call is cheap (~4MB JSON); `extract_exercises` is itself only called once per ETL run; module-level caching would complicate test fixtures (tmp_path round-trips need fresh state). Trade-off: small re-load cost vs simpler invariants. v1 picks simpler. |
| 11 | 16 tests landed | Architect-pick | Coverage: 6 gear-toggle parser tests (including constants self-consistency) + 5 JSON loader tests (default path + CNF shape + missing path + custom path + entry-without-ex_id skip) + 5 schema-substrate tests (all 4 columns declared in correct tables + migration carries all 3 known cases + Layer2CPayload regression smoke). Density right-sized to the substrate scope: most of the value lands in the existing shipped `Layer2CPayload` (5 sub-types) which the regression test exercises. Phase 2.4 builder session will add the ~30+ tests for §13 spec scenarios + §4 input validation + §5 tier resolution. |

---

## 8. Session-end verification (Rule #10)

Anchor sweep via on-disk grep + `python -m pytest`. Run `./aidstation-sources/scripts/verify-handoff.sh` at next session start.

| Check | Result |
|---|---|
| `etl/layer0/schema.sql` declares `terrain_required TEXT[]` on `layer0.exercises` | ✅ grep |
| `etl/layer0/schema.sql` declares `equipment_substitutes_structured JSONB` on `layer0.exercises` | ✅ grep |
| `etl/layer0/schema.sql` declares `also_satisfies TEXT[]` on `layer0.sport_specific_gear_toggles` | ✅ grep |
| `etl/layer0/schema.sql` declares `gated_discipline_ids TEXT[]` on `layer0.sport_specific_gear_toggles` | ✅ grep |
| `aidstation-sources/migrations/migrate_toggles_v3_columns.sql` exists with `ARRAY['Rappelling / abseiling']` + `'D-010'` + `'D-011'` + `'D-015'` populations | ✅ grep |
| `aidstation-sources/migrations/migrate_toggles_v3_columns.sql` carries DO-block verification | ✅ grep `RAISE NOTICE` + `RAISE EXCEPTION` both present |
| `etl/layer0/extractors/vocabulary.py` defines `_TOGGLE_ALSO_SATISFIES` with `'Climbing — roped': ['Rappelling / abseiling']` | ✅ grep |
| `etl/layer0/extractors/vocabulary.py` defines `_TOGGLE_GATED_DISCIPLINES` with 3 toggle entries | ✅ grep |
| `etl/layer0/extractors/vocabulary.py:_parse_gear_toggles` emits `also_satisfies` + `gated_discipline_ids` per row | ✅ grep |
| `etl/layer0/extractors/exercise_db.py` defines `load_parsed_substitutes_structured` function | ✅ grep |
| `etl/layer0/extractors/exercise_db.py:extract_exercises` calls the loader + attaches `equipment_substitutes_structured` per row | ✅ grep |
| `etl/layer0/run.py` `layer0.exercises` INSERT includes `equipment_substitutes_structured` + `to_jsonb(r["equipment_substitutes_structured"])` | ✅ grep |
| `etl/layer0/run.py` `layer0.sport_specific_gear_toggles` INSERT includes `also_satisfies` + `gated_discipline_ids` | ✅ grep |
| `tests/test_layer2c_prep.py` exists with 16 tests | ✅ `grep -c "def test_" tests/test_layer2c_prep.py` = 16 |
| `python -m pytest tests/test_layer2c_prep.py` → 16 passed | ✅ `16 passed in 0.48s` |
| `python -m pytest tests/` → 866 passed | ✅ `866 passed in 2.72s` |
| Branch is `claude/v5-phase-2-4-implementation-04kYj` (renamed this session per Decision 1) | ✅ `git branch --show-current` |
| `CURRENT_STATE.md` `Last shipped session` points at this handoff | ✅ inspection |
| `CURRENT_STATE.md` Layer status row 2 reads "2A + 2D + 2B + 2E runtime shipped … 2C spec done + Phase 2.4-Prep data substrate shipped … 2C builder queued for next session" | ✅ inspection |
| `CURRENT_STATE.md` Tests note bumped 850 → 866 | ✅ inspection |
| Backlog D-73 status note extended to name Phase 2.4-Prep as shipped | ✅ grep |
| Backlog `## Changelog` H2 has a new 2026-05-19 Phase 2.4-Prep entry above the 2.5 entry | ✅ grep |
| `CARRY_FORWARD.md` Manual §5.0 walkthrough count rose 64 → 67 (+3 Phase 2.4-Prep scenarios) | ✅ inspection |
| `CARRY_FORWARD.md` doc-sweep nits gains 5 new entries (DP1/DP2 resolution → spec §5.1 + §8.3 annotation; new §10 edge case; parsed_substitutes.json curation cadence; Open Item 2C-2 closure; Upstream plan §4 row 2.4 update) | ✅ inspection |

---

## 9. Files shipped this session

By the B3 rule (substantive = code/specs/designs/prompt bodies; bookkeeping outside the count):

**Substantive (6 files; over the 5-file ceiling per Andy 2026-05-19 explicit "Add exercise_db.py too" stretch authorization on the plan-mode gate):**

1. Modified `etl/layer0/schema.sql` — added 4 columns to canonical schema with spec-section anchor comments.
2. New `aidstation-sources/migrations/migrate_toggles_v3_columns.sql` — combined migration: ADD COLUMN IF NOT EXISTS for `also_satisfies` + `gated_discipline_ids` on `layer0.sport_specific_gear_toggles` + UPDATE the 3 known cases per `Vocabulary_Audit_v2.md` §4 + DO-block verification with NOTICE-fallback.
3. Modified `etl/layer0/extractors/vocabulary.py` — new code-side constants `_TOGGLE_ALSO_SATISFIES` + `_TOGGLE_GATED_DISCIPLINES`; `_parse_gear_toggles` emits both fields per row.
4. Modified `etl/layer0/extractors/exercise_db.py` — new `load_parsed_substitutes_structured()` helper + `extract_exercises` attaches structured substitutes per row from `etl/sources/parsed_substitutes.json`.
5. Modified `etl/layer0/run.py` — `layer0.exercises` INSERT now writes `equipment_substitutes_structured`; `layer0.sport_specific_gear_toggles` INSERT now writes `also_satisfies` + `gated_discipline_ids`.
6. New `tests/test_layer2c_prep.py` — 16 tests across 3 test classes.

**Bookkeeping (4 files; outside ceiling per B3):**

7. Modified `aidstation-sources/CURRENT_STATE.md` — pointer flipped to this handoff; Layer 2 status note extended; Tests note bumped to 866; D-73 arc note extended.
8. Modified `aidstation-sources/Project_Backlog_v62.md` — in-place: D-73 status note extended to name Phase 2.4-Prep as shipped; new 2026-05-19 Phase 2.4-Prep entry in `## Changelog` (above the 2.5 entry).
9. Modified `aidstation-sources/CARRY_FORWARD.md` — Manual §5.0 walkthrough gains 3 Phase 2.4-Prep scenarios (count 64 → 67); doc-sweep nits gains 5 entries (Layer2C_Spec.md §5.1 + §8.3 DP annotations / §10 edge case / parsed_substitutes.json curation / Open Item 2C-2 closure / Upstream plan §4 row 2.4 update).
10. New `aidstation-sources/handoffs/V5_Implementation_D73_Phase_2_4_Prep_Closing_Handoff_v1.md` (this file).

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` gains 3 new §5.0 walkthrough scenarios under a "D-73 Phase 2.4-Prep" sub-bullet. Scenario count rises 64 → 67.

`CARRY_FORWARD.md` doc-sweep nits section gains 5 entries:

- `Layer2C_Spec.md` §5.1 + §8.3 Decision Points — both resolved 2026-05-19. Annotate "✅ Resolved 2026-05-19 — DP1 (A) Runtime; DP2 (b) Structured column" with resolution rationale (~10-line edit total). Fold into the Phase 2.4 builder session.
- `Layer2C_Spec.md` §10 edge cases — additional implicit edge case (exercise present in `layer0.exercises` but absent from `parsed_substitutes.json` → empty substitutes; Tier 2 returns None). Document in §10 (~2-line addition).
- `etl/sources/parsed_substitutes.json` curation cadence — K-parser source location + re-run cadence not documented in this repo; track for future ETL spec touchpoint.
- `Layer2C_Spec.md` Open Item 2C-2 — closes 2026-05-19 via Phase 2.4-Prep (structured column) in a different way than spec anticipated (spec said "defer to FC-1"). Row flip + §8.3 docstring update (~2-line edit).
- `Upstream_Implementation_Plan_v1.md` §4 row 2.4 — stale text ("5-7 over ceiling — Decision Point gate adds 1 file" + "/plan-mode gate"). With Prep shipped + DPs resolved, builder session should be ~4-5 files and no /plan-mode gate. Row update (~3-line edit).

No new orthogonal carry-forwards this session.

Layer 4 Step 4f + Step 7 + Step 8 still queued per the existing list.

---

**End of handoff.**
