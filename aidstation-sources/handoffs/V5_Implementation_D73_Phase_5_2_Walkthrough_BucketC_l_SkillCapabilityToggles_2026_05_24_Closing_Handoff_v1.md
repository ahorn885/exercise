# D-73 Phase 5.2 Walkthrough — Bucket C sub-item (l) Skill-Capability Toggles — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — picks up the §6.1 architect-recommended next-slice menu from the predecessor BucketC_g_TerrainEquipmentMerge slice. Closes Bucket C sub-item (l) — the final open Bucket C sub-item — via NEW `layer0.skill_capability_toggles` vocab table (5 rows) + NEW `athlete_skill_toggles` athlete-state table + Layer 1 builder threading + Layer 2B/2C rip-and-replace of the `_COACHED_INTRO_KEYWORDS` keyword-substring branch with explicit toggle-gated `requires_skill_capability` flag emission. Pins the architectural principle that **coach-need / skill-prerequisite is an athlete-capability property, not a derived terrain property**. Athlete-side capture surface deferred to a focused follow-on (mirrors gear-toggle status quo where the orchestrator passes `cluster_gear_toggle_states={}`). **Bucket C now FULLY CLOSED (11 of 11 sub-items shipped).**

**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_g_TerrainEquipmentMerge_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/skill-capability-toggles-bucketc-l` (renamed at session start from harness-pinned `claude/terrain-equipment-merge-hGi4Q` per CLAUDE.md branch-naming rule; old name mismatched scope since BucketC_g already shipped in PR #140)
**Status:** 12 substantive files (9 code + 3 test; ceiling break ratified at AskUserQuestion gate; precedents BucketC_i=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13). Predecessor reproducer subset 941 → 949 (+8 net new). test_layer1_builder.py separately 19 → 22 (+3 net new + import-order workaround unblocks single-module collection of the pre-existing circular import). ETL `etl/tests/` 139 → 139 unchanged. No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → predecessor BucketC_g handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep ✅ clean — the 4 ❌ entries on `tests/test_extractor_parsers.py` / `tests/test_sum_to_100.py` / `tests/test_v10_parsers.py` / `tests/test_vocabulary_md.py` are the known false-positives (those files live under `etl/tests/`, not `tests/`; the script searches relative paths from `aidstation-sources/` working dir + doesn't know about the nested test tree, confirmed via `ls /home/user/exercise/etl/tests/`). Working tree clean. Branch at `origin/main` HEAD — predecessor BucketC_g shipped via PR #140 (merge commit `49f420b`) and is already on the branch base; no drift between predecessor handoff narrative and on-disk state. Predecessor §8 anchors spot-checked: `_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` mapping present in `init_db.py`; `_retire_outdoor_terrain_equipment_tags` callable wired as final `_PG_MIGRATIONS` entry; `TestGravelTerrainAdd` 5 tests collected + passing; container subset 941 baseline confirmed (different from predecessor's stated 906 — explained by `git stash` baseline check showing 941 on the current branch HEAD; the predecessor figure was from a session with a different deps state).

Andy picked **Bucket C sub-item (l) skill-capability toggles** at the first AskUserQuestion gate over the architect-recommended #8 locales→locations rename + the NEW best-fit modality cross-reference + Layer 2B per-discipline gap reasoning.

---

## 2. Session narrative

The (l) sub-item carried forward through every recent Bucket C handoff with a Trigger #3 + Trigger #5 plan-mode pre-pin from the WaterVocabExpansion AskUserQuestion gate (2026-05-24 earlier same day). The pre-pin nominated 3 toggles (climbing, whitewater, swim) + onboarding-step capture + Layer 2B keyword-match fallback semantics. The fresh plan-mode design pass diverged from the pre-pin on three counts that Andy ratified at the gates:

**Plan-mode design pass — three nested AskUserQuestion gates:**

| # | Gate | Andy's pick | Notes |
|---|---|---|---|
| G1 | Replacement scope — keyword-match rip strategy? | **Rip + extend to Layer 2C** | Over rip-replace-2B-only + layer-on-top-keep-fallback. Both 2B race-terrain side and 2C included-discipline side now consult skill state with parallel `requires_skill_capability` flags. The semantic honesty wins: skill is athlete-side, capability gating should be uniform across the layer pair. |
| G2 | Vocab scope — toggle count? | **5 toggles (broader than 3-toggle pre-pin)** | Over the WaterVocab pre-pin's narrow 3 (climbing, whitewater, swim). Adds via_ferrata + mountaineering. Andy accepted Trigger #2 padding scrutiny since each addition has genuine athlete-side capability semantics not derivable from gear toggle state (e.g. via_ferrata cable-clipping + exposure tolerance is distinct from gear availability; mountaineering glacier travel + crampon technique is distinct from snowshoe + ski toggles). |
| G3 | Capture surface — same slice or follow-on? | **DEFERRED to follow-on** | Over profile-edit-in-same-slice (+3 files) + onboarding-only (+~3 files). Mirrors gear-toggle status quo where the orchestrator passes `cluster_gear_toggle_states={}` until UI ships. All athletes get default-OFF flags fire for every included gated discipline / race-terrain entry; nuisance shape identical to existing gear-toggle precedent, not a new regression. |

**Mapping tightening (post-G2):** Andy ratified tightened gated_discipline_ids for two toggles after the proposal. (a) `climbing_roped` drops D-011 Rappelling — athlete may know how to abseil without lead-climbing technique; forces a future separate `rappelling_skill` toggle if AR rappel sections need explicit gating. (b) `swim_open_water` drops D-014 (Swimming Open Water / River Crossing) + D-018 (Swimrun) — gates only D-004 Open Water Swimming. Reduces noise for AR athletes whose river-crossing swims don't require dedicated OW competence (river crossings are short + supported, the OW skill threshold targets dedicated distance racing).

**Critical pre-code finding (changed the design framing):** The Layer 2B `_COACHED_INTRO_KEYWORDS` keyword-substring match against `prescription_note.lower()` is **effectively dead code today** under deployed data. The only rule that names coached-intro keywords (TRN-011 → TRN-009 whitewater) has `proxy_fidelity=0.30`, which sits BELOW the `_COACHED_INTRO_FIDELITY_MIN=0.5` gate. The WaterVocabExpansion-added TRN-017 rules deliberately omit coached-intro language (per the forward-compat test). TRN-013 → TRN-014 climbing-gym rule also has no coached-intro keywords. So the flag literally never fires against current data. This makes the rip safe: no athletes lose a flag they were getting. Same default-OFF semantics under the new scheme means the flag now WILL fire for every athlete by default until they enable the matching skill toggle — strictly more honest than the keyword-match path.

**Architectural principle pinned (D-decision):** Coach-need / skill-prerequisite is an athlete-capability property, not a derived terrain property. Storing capabilities as explicit toggle rows joining `gated_terrain_ids` + `gated_discipline_ids` arrays cleanly replaces fragile substring sniffing on prose authored by ETL. Layer 2B reads the terrain side, Layer 2C reads the discipline side, with identical default-OFF semantics so coaching-flag emission is uniform across the layer pair.

---

## 3. File-by-file edits

### 3.1 `etl/layer0/schema.sql` — NEW `layer0.skill_capability_toggles` table

Inserted after `layer0.sport_specific_gear_toggles` to keep toggle-class tables co-located. 9-column shape mirrors gear-toggle minus the gear-specific cols (`paired_equipment_categories`, `also_satisfies`) plus the NEW `gated_terrain_ids TEXT[]` for the 2B race-terrain consumer. Same versioning shape (`etl_version` + `etl_run_at` + `superseded_at` + `UNIQUE (toggle_name, etl_version)`). Multi-line comment block above the CREATE pins the architectural principle (SURFACE / SKILL split) + cites the WaterVocab gate where the (l) sub-item was first surfaced.

### 3.2 NEW `etl/sources/populate_skill_capability_toggles.sql` — 5 vocab rows

5 INSERT rows tagged `0C-v2.0-r2` matching the canonical 0C version per existing populate files. Each row carries an athlete-facing `display_label` (longer prose) + a 2-3 sentence `description` (purpose + boundary of the skill) + the explicit `gated_terrain_ids` and `gated_discipline_ids` arrays per Andy's tightened mappings. `ON CONFLICT (toggle_name, etl_version) DO NOTHING` guards re-runs; trailing `DO $$ ... END $$` verify block asserts `COUNT(*)=5` active rows and RAISES on shortfall (catches missed inserts during cross-deploy debugging). Naming convention is **snake_case identifiers** (climbing_roped, via_ferrata, whitewater_handling, swim_open_water, mountaineering) — explicit deviation from the gear-toggle em-dash display strings (`'Climbing — roped'`) noted in the file comment as a fragility-trap dodge per `populate_gear_toggles_batch_a.sql:23-30`.

**Tightened mappings:**
- `climbing_roped` → `{TRN-013}` + `{D-010}` (dropped D-011 — separate skill from lead-climbing)
- `via_ferrata` → `{}` (no canonical via-ferrata terrain row) + `{D-012}` (skill surfaces only on discipline side)
- `whitewater_handling` → `{TRN-011, TRN-017}` + `{D-008b}`
- `swim_open_water` → `{TRN-009, TRN-010}` + `{D-004}` (dropped D-014 + D-018 — reduces noise)
- `mountaineering` → `{TRN-005, TRN-012}` + `{D-016, D-020}`

### 3.3 `init_db.py` — NEW `athlete_skill_toggles` migration

Single new entry in `_PG_MIGRATIONS` (appended after the BucketC_g `_retire_outdoor_terrain_equipment_tags` callable). 6-column table: `id SERIAL PRIMARY KEY` + `user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE` + `toggle_name TEXT NOT NULL` + `enabled BOOLEAN NOT NULL DEFAULT FALSE` + `created_at TIMESTAMP DEFAULT NOW()` + `updated_at TIMESTAMP DEFAULT NOW()` with `UNIQUE (user_id, toggle_name)`. Plus a separate `CREATE INDEX IF NOT EXISTS ast_user_idx ON athlete_skill_toggles (user_id)` statement for fast per-athlete lookups (Layer 1 builder's loader is keyed on user_id). Comment block above the migration documents the deferred capture surface + the mirror-of-`locale_toggle_overrides`-minus-locale-axis shape rationale.

### 3.4 `layer4/context.py` — `Layer1Lifestyle.skill_toggle_states` + `Layer2CCoachingFlag.flag_type`

Two edits in one file:

**(a) `Layer1Lifestyle`** gains `skill_toggle_states: dict[str, bool] = Field(default_factory=dict)`. Field doc block cites Bucket C (l) + names the default-OFF (assume-not-skilled) opt-in semantic + mentions the canonical-source table.

**(b) `Layer2CCoachingFlag.flag_type`** Literal extended from `["low_coverage", "critical_dropped", "toggle_off_for_discipline"]` to add `"requires_skill_capability"`. Comment block above the addition cites parallel-surface intent to gear-toggle `toggle_off_for_discipline` — same payload shape, distinct `flag_type` so the brief LLM can render appropriate (skill-vs-gear) guidance.

**Note:** No change to `Layer2BCoachingFlag` — its `flag_type` is already typed as bare `str` (not Literal), so the new `"requires_skill_capability"` value drops in without a typing change. The string-typed approach was an earlier design call that paid off here.

### 3.5 `layer1/builder.py` — NEW `_load_skill_toggle_states` helper

~10 LOC helper placed next to `_load_resting_hr` (similar 1-SELECT lookup pattern). Reads `SELECT toggle_name, enabled FROM athlete_skill_toggles WHERE user_id = ?` and returns the dict comp `{r["toggle_name"]: bool(r["enabled"]) for r in cur.fetchall()}`. Empty dict on fresh athletes (no rows). Wired into `build_layer1_payload` between `_load_disclosures` and the `Layer1Lifestyle(...)` constructor; constructor call updated to pass `skill_toggle_states=skill_toggle_states`. Increases Layer 1's total SELECT count from 24 to 25.

### 3.6 `layer2b/builder.py` — rip keyword-match + add skill-capability flag emission

**Rip block:** deleted `_COACHED_INTRO_FIDELITY_MIN: float = 0.5`, `_COACHED_INTRO_KEYWORDS: tuple[str, ...] = (5 substrings)`, the `_mentions_coached_intro` helper, and the fidelity-gated keyword-match branch in `_emit_coaching_flags` that emitted `requires_coached_introduction` flags. Replaced with a single multi-line comment block explaining the rip + naming the canonical-source table + citing the Bucket C (l) gate.

**Additions:**
- NEW `_load_skill_capability_toggle_defs(db, version_0c) -> dict[str, dict[str, list[str]]]` SQL loader reading `layer0.skill_capability_toggles` for the active 0C version. Returns dict keyed by `toggle_name` carrying both `gated_terrain_ids` and `gated_discipline_ids` (Layer 2B reads the terrain side; Layer 2C has its own copy of the same loader reading the discipline side — minor duplication matches the existing pattern where 2B and 2C each own their own DB queries against shared tables).
- Public function `q_layer2b_terrain_classifier_payload` signature gains `skill_toggle_states: dict[str, bool] | None = None` kwarg with `skill_toggle_states = skill_toggle_states or {}` normalization.
- `_emit_coaching_flags` signature extended with `skill_toggle_defs` + `skill_toggle_states` params; NEW emission block at the tail iterates skill_toggle_defs × race_terrain entries and emits `requires_skill_capability` for every (race_terrain entry, matching toggle) pair where the athlete state is not True. The match condition is `entry.terrain_id ∈ toggle.gated_terrain_ids`. The metadata payload includes `toggle_name` + `pct_of_race` (from the race-terrain entry, not the gap, since the flag fires regardless of locale coverage — the athlete needs the skill to safely race on the terrain whether or not their locale terrain set covers the proxy).
- Loader call site is `if race_terrain: skill_toggle_defs = _load_skill_capability_toggle_defs(...)`. Empty `race_terrain` skips the SQL roundtrip — covered by the existing `race_terrain_unset` short-circuit branch in `_emit_coaching_flags`.

### 3.7 `layer2c/builder.py` — parallel `_load_skill_capability_toggle_defs` + capability-flag emission

**Additions** (parallel to layer2b but owns its own SQL loader matching the existing precedent where 2C owns `_load_toggle_defs` independent of 2B):
- NEW `_load_skill_capability_toggle_defs(db, version_0c)` (own copy of the same SQL; both layers use the same shape).
- Public function `q_layer2c_equipment_mapper_payload` signature gains `skill_toggle_states: dict[str, bool] | None = None` kwarg with `skill_toggle_states = skill_toggle_states or {}` normalization.
- Loader call at the top of the public function (unconditional; every 2C call hits the table once, parallel to the existing gear-toggle loader).
- `_emit_coaching_flags` signature extended with `skill_toggle_defs` + `skill_toggle_states` params; NEW emission block placed right after the existing `toggle_off_for_discipline` block (semantically parallel — both fire flags for included gated disciplines when the relevant athlete state is not True; metadata payload includes `toggle_name`).

### 3.8 `layer4/orchestrator.py` — 3 call site threadings

All three call sites add `skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states`:
1. `_upstream_full_cone` Layer 2B call (line ~261).
2. `_upstream_full_cone` Layer 2C call (line ~283).
3. `orchestrate_single_session_synthesize` Layer 2C call inside the `if request.locale_slug is not None:` branch (line ~519).

Each site has an inline comment citing Bucket C (l). All 3 callers `_upstream_full_cone` (which feeds race_week_brief + plan_refresh + plan_create) and the single_session path (which feeds ad-hoc-workouts) now thread athlete-side skill state into the layer 2 coaching-flag emission.

### 3.9 `etl/sources/populate_terrain_gap_rules.sql` — TRN-011 prescription_note text strip

The TRN-011 → TRN-009 whitewater rule's `prescription_note` previously included `"requires supervised instruction in moving water. Cannot self-teach safely — flag as requiring coached introduction to moving water before race."` — those substrings were the ONLY ones in the deployed gap-rule corpus matching `_COACHED_INTRO_KEYWORDS`. Rewrote to drop both triggers + credit the new `whitewater_handling` skill toggle as the capability-gating surface. New text retains the substantive guidance (flat-water maintains fitness only; pool rolling is a foundation but not a substitute; whitewater technique cannot be acquired from flat-water alone). The gap rule's `proxy_fidelity=0.30` and `gap_severity='partial'` stay unchanged — this is a doc-string-style edit, not a behavior change. No other prescription_note rows in the file contained the keyword-match triggers (verified by grep against the file).

### 3.10 `tests/test_layer2b.py` — remove TestCoachedIntroFlag + add TestSkillCapabilityFlag

**Removed:** `TestCoachedIntroFlag` class (2 tests: `test_whitewater_coached_intro_flag` + `test_coached_intro_does_not_fire_below_fidelity_threshold`). Both asserted on the ripped keyword-match behavior; no path forward to migrate them since the flag_type itself is gone.

**Added:** NEW `TestSkillCapabilityFlag` class (5 tests):
1. `test_whitewater_skill_capability_flag_fires_when_toggle_off` — TRN-011 in race_terrain + `whitewater_handling` toggle queued with `{TRN-011, TRN-017}` gated terrains → flag fires with `toggle_name=whitewater_handling` + `pct_of_race=100.0` in metadata.
2. `test_skill_capability_flag_suppressed_when_toggle_on` — same shape but `skill_toggle_states={"whitewater_handling": True}` → flag does NOT fire.
3. `test_skill_capability_flag_not_fired_for_ungated_terrain` — TRN-001 (paved) in race_terrain + same toggle queued → flag does NOT fire (TRN-001 not in gated_terrain_ids).
4. `test_skill_toggle_loader_skipped_when_race_terrain_empty` — empty `race_terrain` short-circuits at `race_terrain_unset` branch; the `skill_capability_toggles` SQL is verified absent from `conn.calls` (loader gate works).
5. `test_multiple_gated_terrains_emit_one_flag_each` — race with TRN-011 (60%) + TRN-017 (40%) both gated by `whitewater_handling` → 2 flags emitted with correct `pct_of_race` per entry (60.0 and 40.0).

### 3.11 `tests/test_layer2c.py` — _FakeConn extension + add TestSkillCapabilityFlag

**`_FakeConn` extension:** detects `skill_capability_toggles` in the SQL string at `execute()` and returns an empty cursor without consuming a queued batch. This preserves all 35 existing tests untouched as the new SELECT slots into the call sequence (between gear-toggle defs and discipline info) without disrupting batch ordering. NEW `queue_skill_capability_toggles(*rows)` method on `_FakeConn` for tests that DO want to queue capability vocab rows; the dedicated batches are consumed by `skill_capability_toggles` SQL matches in FIFO order.

**Added:** NEW top-level `_skill_cap_row(toggle_name, ...)` helper + NEW `TestSkillCapabilityFlag` class (5 tests):
1. `test_requires_skill_capability_fires_when_toggle_off` — climbing_roped gating D-010 included + toggle OFF → flag with `discipline_id=D-010` + `toggle_name=climbing_roped` + `affected_exercise_ids=[]`.
2. `test_skill_capability_flag_suppressed_when_toggle_on` — same shape with `skill_toggle_states={"climbing_roped": True}` → no flag.
3. `test_skill_capability_flag_skipped_when_discipline_not_included` — mountaineering gating D-016/D-020 + only D-001 included → no flag.
4. `test_mountaineering_toggle_fires_for_two_included_disciplines` — both D-016 and D-020 included with toggle OFF → 2 flags emitted (one per discipline) with same toggle_name.
5. `test_default_empty_skill_states_treats_every_toggle_off` — swim_open_water gating D-004 included + no `skill_toggle_states` kwarg passed at all → flag fires (mirrors gear-toggle default-OFF precedent).

### 3.12 `tests/test_layer1_builder.py` — pre-existing circular import workaround + TestSkillToggleStates

**Pre-existing fix:** Added `from layer4 import InMemoryCacheBackend  # noqa: F401` import-order workaround at the top of the file (mirrors `tests/test_layer2a.py:26` + `tests/test_layer2b.py:26` precedent). Unblocks single-module collection (`pytest tests/test_layer1_builder.py` standalone) of the pre-existing circular import between `layer1.builder` and `layer4.orchestrator`. The 19 existing tests in this file were always passing when collected alongside other layer4-importing modules; this workaround makes single-module runs work too. Pure additive fix, not slice-specific.

**Counter updates:**
- `_queue_empty_athlete` bumped 24 → 25 responses (the new `_load_skill_toggle_states` adds one SELECT).
- `test_24_selects_issued` renamed to `test_25_selects_issued` + assertion `len(conn.calls) == 25`.
- `TestFullyPopulated._queue_andy` extended with 25th queue_response carrying climbing_roped=True + whitewater_handling=True (Andy is an AR athlete with real climbing + paddle experience; populating realistic state in the fully-populated fixture path).

**Added:** NEW `TestSkillToggleStates` class (3 tests):
1. `test_empty_athlete_yields_empty_dict` — empty athlete → `payload.lifestyle.skill_toggle_states == {}`.
2. `test_populated_toggles_thread_through` — Andy's `_queue_andy` → `{climbing_roped: True, whitewater_handling: True}` (the rest implicit OFF since they're not in the table).
3. `test_explicit_off_rows_preserved` — `{toggle: False}` rows are preserved in the dict, not collapsed to absent. Layer 2B/2C currently treat absent and explicit-False the same (both as OFF), but the distinction is preserved at the Layer 1 boundary in case future consumers care.

---

## 4. Code / tests

**Tests:** predecessor reproducer subset (24 test files, excludes test_layer1_builder.py per predecessor convention) 941 → 949 (+8 net new: 5 in 2C TestSkillCapabilityFlag + 3 net in 2B TestSkillCapabilityFlag = 5 added - 2 removed = +3 net). `test_layer1_builder.py` separately 19 → 22 (+3 in TestSkillToggleStates; the import-order workaround unblocks single-module collection of the 19 existing tests but they were always passing when collected alongside other layer4-importing modules). ETL `etl/tests/` 139 → 139 unchanged. No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a / layer2b / layer2c / layer1 builder / bucket_c_terrain_vocab_audit surfaces; 12 NL parser smoke + 4 Layer 3 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

Reproducer (full container subset, mirrors predecessor's exact invocation):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
  tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
  tests/test_onboarding_race_events.py tests/test_layer4_context.py \
  tests/test_layer4_payload.py tests/test_layer4_hashing.py tests/test_layer4_cache.py \
  tests/test_layer4_race_week_brief.py tests/test_plan_sessions_repo.py \
  tests/test_routes_ad_hoc_workouts.py tests/test_routes_plan_create.py \
  tests/test_nl_parser.py tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
  tests/test_routes_dashboard.py tests/test_routes_admin.py \
  tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
  tests/test_layer2a.py tests/test_layer2b.py tests/test_layer2c.py \
  tests/test_bucket_c_terrain_vocab_audit.py
# 949 passed, 12 skipped in 1.45s
```

Layer 1 builder standalone (with the new import-order workaround):

```
PYTHONPATH=. python3 -m pytest tests/test_layer1_builder.py
# 22 passed in 0.37s
```

ETL: `PYTHONPATH=. python3 -m pytest etl/tests/ # 139 passed in 0.49s`.

**py_compile:** all 6 edited Python files (`init_db.py`, `layer4/context.py`, `layer1/builder.py`, `layer2b/builder.py`, `layer2c/builder.py`, `layer4/orchestrator.py`) pass `python3 -m py_compile`.

---

## 5. Manual §5.0 verification — owed step

NEW 5-step walkthrough scenario added to `CARRY_FORWARD.md` §5.0 list. Summarized:

1. **Neon schema spot-check on first deploy** — `\d athlete_skill_toggles` returns 6-col shape with UNIQUE (user_id, toggle_name) + `ast_user_idx` index; `\d layer0.skill_capability_toggles` returns 9-col shape per schema.sql; `SELECT COUNT(*) FROM layer0.skill_capability_toggles WHERE etl_version='0C-v2.0-r2' AND superseded_at IS NULL` returns 0 until populate script is applied manually (populate scripts ship via ETL pipeline, not `_PG_MIGRATIONS`); after applying, COUNT(*) = 5.

2. **Orchestrator surfaces default-OFF skill-capability flags for Andy's PGE 2026** — invoke `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026,7,3))`; confirm `layer2c_payload.coaching_flags` includes `requires_skill_capability` rows for D-010 (climbing_roped) + D-008b (whitewater_handling) + D-016 + D-020 (mountaineering); confirm `layer2b_payload.coaching_flags` does NOT include any `requires_skill_capability` flags (PGE 2026 race terrain TRN-002/003/004/009/016 has no skill-gated members).

3. **Enable two toggles + re-orchestrate** — `INSERT INTO athlete_skill_toggles ... VALUES (<andy>, 'climbing_roped', TRUE), (<andy>, 'whitewater_handling', TRUE)`; re-orchestrate; confirm those 2 flags disappear, mountaineering flags still fire.

4. **TRN-011 race terrain test** — set test race row's `race_terrain = [{"terrain_id":"TRN-011","pct_of_race":100}]`; orchestrate; confirm 2B's `coaching_flags` includes `requires_skill_capability(target_terrain_id=TRN-011, toggle_name=whitewater_handling)` with `pct_of_race=100.0` in metadata. Set whitewater_handling=TRUE and re-orchestrate; flag disappears.

5. **Populate script idempotency** — run `psql -f etl/sources/populate_skill_capability_toggles.sql` twice; second run no-ops via `ON CONFLICT DO NOTHING`; verify block RAISES NOTICE both times; TRN-011 prescription_note text in Layer 2B prompt reads the cleaner whitewater_handling-crediting language.

Andy's PGE 2026 row is not affected directly (no terrain-vocab change for his picked terrains); the orchestrator output will surface ~3-4 new nuisance flags until he sets toggles ON via direct DB UPDATE or the capture-surface follow-on lands.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Skill-capability toggle capture surface** is the natural follow-on — without it, every athlete gets ~3-4 nuisance `requires_skill_capability` flags by default. Scope: profile-edit tab `?tab=skills` with 5-checkbox grid + POST handler + cache invalidation policy (skill-toggle edits should evict Layer 2B + 2C entry points = `_NON_SINGLE_SESSION` mirror, plus single-session orchestrator since 2C is in its cone). ~3-4 substantive files. Could pair with onboarding-step integration as a single onboarding+profile-edit slice if Andy wants both surfaces shipped together.

Alternative: **#8 "locales" → "locations" terminology rename** remains the lowest-risk mechanical slice (carried forward through every recent handoff; ~9 templates, no `/plan` triggers).

### 6.2 Alternative pivots

- **NEW best-fit modality cross-reference design** — open from BucketC_g. Lets a planner read `{locale_terrain_ids + cluster_equipment + included_disciplines + skill_toggle_states}` and return per-session "recommended modality". Skill toggle state is now an additional input to this reasoning. Plan-mode gate required (Trigger #1 if prompt-side; Trigger #3 if schema-side; Trigger #5 either way).
- **Layer 2B per-discipline gap reasoning (consume C1)** — Trigger #1 prompt-body update. ~3-5 files including spec + prompt + tests.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.
- **Bucket D — legacy hardcoded locales (a + b)** — now unblocked (Bucket C fully closed; the dependency on (g)/(l) is satisfied).
- **Manual §5.0 walkthrough** — accumulated 95 scenarios pending; this slice's 5-step scenario joins the list. The most recent shipped surfaces (BucketC_g + BucketC_i + BucketE_B2_C1 + WaterVocabExpansion + RouteLocalesAnchorFlags + ETLTerrainVocabDriftFix) are all unwalked.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C now FULLY CLOSED; capture-surface follow-on queued as the natural next slice; 95 §5.0 scenarios pending).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_l_SkillCapabilityToggles_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. The script's 4 ❌ false-positives on ETL test files still present (script doesn't know about `etl/tests/`); verify via `ls /home/user/exercise/etl/tests/`.

**No outstanding production warnings.** Bucket C: **FULLY CLOSED — all 11 of 11 sub-items shipped (a/b/c/d/e/f/g/h/i/j/k/l)**. Bucket E: fully closed (from earlier slices).

**Backward-compat note for next deploy:** the new `athlete_skill_toggles` table CREATE runs on next Neon boot via `_PG_MIGRATIONS`. The `layer0.skill_capability_toggles` table CREATE lives in `etl/layer0/schema.sql` and is applied via `apply_schema()` (the ETL pipeline boot path); the populate script `etl/sources/populate_skill_capability_toggles.sql` ships with the ETL run — operators need to apply it manually (or wire into the ETL pipeline as a post-step) the first time. **Until the populate script is applied AND `_load_skill_capability_toggle_defs` returns the 5 rows**, the orchestrator will fire NO `requires_skill_capability` flags (the loader returns empty dict on no active rows). **After the populate script applies**, every existing athlete will start getting default-OFF flags for every included gated discipline / race-terrain entry — strictly more flags than today, but each one is informative + dismissible via the future capture-surface follow-on.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Replacement scope = rip + extend to Layer 2C | Andy at first AskUserQuestion gate | Over rip-replace-2B-only + layer-on-top-keep-fallback. The keyword-match path is effectively dead code today (TRN-011 fidelity 0.30 < 0.5 gate filters it out; no other rule has the trigger keywords at fidelity ≥ 0.5). The rip is safe; the 2C extension makes capability gating uniform across the layer pair so the brief LLM gets consistent guidance on skill prerequisites. |
| **D2** | Vocab scope = 5 toggles | Andy at second AskUserQuestion gate | Over the WaterVocab pre-pin's narrow 3 (climbing, whitewater, swim). Adds via_ferrata + mountaineering. Andy accepted Trigger #2 padding scrutiny since each addition has genuine athlete-side capability semantics not derivable from gear toggles. |
| **D3** | Mappings tightened — drop D-011 from climbing_roped + drop D-014/D-018 from swim_open_water | Andy at mapping-ratification gate | (a) Rappelling is a separate skill from lead climbing despite the gear-toggle precedent treating them as one — forces a future `rappelling_skill` toggle if AR rappel sections need separate gating. (b) River-crossing swims (D-014) + Swimrun (D-018) don't require dedicated OW competence the way dedicated OW racing (D-004) does — reduces noise for AR athletes. |
| **D4** | Capture surface DEFERRED to follow-on slice | Andy at capture-surface gate | Over profile-edit-in-same-slice (+3 files) + onboarding-only (+~3 files). Mirrors gear-toggle status quo where orchestrator passes `cluster_gear_toggle_states={}` until UI ships. Same nuisance shape as existing gear-toggle precedent, not a new regression; capture-surface follow-on resolves cleanly when it ships. |
| **D5** | 12-file ceiling break ratified | Andy at ceiling-ratification gate | 12 substantive files (9 code + 3 test). Precedents: BucketC_i=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13. Andy explicitly chose ceiling break over PR split since the runtime + schema + ETL + tests are tightly coupled and split would mean shipping a half-wired runtime (Layer 2B/2C consult a table that doesn't exist yet, or schema lands without consumers). |
| **D6** | Naming convention = snake_case (not em-dash display strings) | Architect at code-time | The gear-toggle precedent uses em-dash display strings (`'Climbing — roped'`) as primary keys — fragile against normalization drift (see `populate_gear_toggles_batch_a.sql:23-30` audit-trail comment on em-dash exact-matching). Skill toggles use snake_case identifiers (climbing_roped, etc.) with a separate `display_label` column for athlete-facing UI. Trades off perfect-symmetry-with-gear-precedent for resilience. |
| **D7** | Layer 2B + Layer 2C own independent SQL loaders | Architect at code-time | Each module has its own `_load_skill_capability_toggle_defs` helper (same SQL, separate copies). Matches the existing pattern where 2C owns `_load_toggle_defs` for gear toggles + 2B doesn't access it; modules stay independent for testability + parallel queryability. The duplication is ~15 LOC; sharing would require either an extracted layer0-side query module (new file) or a cross-module import that breaks the layer-isolation pattern. |
| **D8** | TRN-011 prescription_note rewritten in same slice | Architect at code-time | The WaterVocab forward-pointer ("Prescription_note coached-intro language stripped... once toggles wire end-to-end") becomes mechanical once the keyword-match is ripped. The dead-code trigger text is doc rot; cleaning in the same slice (1 LOC edit) prevents a future ETL session from hitting it. |
| **D9** | Layer 2B + 2C kwargs default-`None`-normalized-to-empty-dict | Architect at code-time | Both public functions accept `skill_toggle_states: dict[str, bool] | None = None` then `skill_toggle_states = skill_toggle_states or {}`. Allows existing callers to keep working without API changes (existing tests in the layer2c suite that don't pass `skill_toggle_states` continue to work via the default). Net effect: every caller still has to consciously thread the kwarg if they want skill-state-aware flag emission, but the absence of the kwarg gracefully degrades to "no skill state = every toggle treated as OFF = flags fire for default-OFF athletes" — matches the gear-toggle precedent semantically. |
| **D10** | Pre-existing test_layer1_builder.py circular import workaround folded into same slice | Architect at code-time | The slice already touches test_layer1_builder.py for the new TestSkillToggleStates class + the `_queue_empty_athlete` bump. While there, adding the 4-line workaround (`from layer4 import InMemoryCacheBackend` import-order forcing) is a free fix that unblocks single-module collection. Pure additive; doesn't expand scope. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer0.skill_capability_toggles` table CREATE added to schema.sql | ✅ `grep -n "skill_capability_toggles" etl/layer0/schema.sql` returns table CREATE + comment block |
| 5-row populate script created | ✅ `grep -c "INTO layer0.skill_capability_toggles" etl/sources/populate_skill_capability_toggles.sql` returns 1 (single INSERT with 5 VALUES tuples) |
| populate script idempotency guard present | ✅ `grep -n "ON CONFLICT (toggle_name, etl_version) DO NOTHING" etl/sources/populate_skill_capability_toggles.sql` returns hit |
| populate script verify block asserts 5 rows | ✅ `grep -n "row_count <> 5" etl/sources/populate_skill_capability_toggles.sql` returns hit |
| `athlete_skill_toggles` migration added to `_PG_MIGRATIONS` | ✅ `grep -n "athlete_skill_toggles" init_db.py` returns CREATE TABLE entry + ast_user_idx index entry |
| `Layer1Lifestyle.skill_toggle_states` field defined | ✅ `grep -n "skill_toggle_states" layer4/context.py` returns Field on Layer1Lifestyle |
| `Layer2CCoachingFlag.flag_type` extended with `"requires_skill_capability"` | ✅ `grep -n "requires_skill_capability" layer4/context.py` returns Literal addition |
| `_load_skill_toggle_states` defined in layer1/builder.py + wired into Layer1Lifestyle | ✅ `grep -n "_load_skill_toggle_states\|skill_toggle_states=" layer1/builder.py` returns 3 hits (def + call + constructor pass) |
| `_COACHED_INTRO_KEYWORDS` + `_mentions_coached_intro` ripped from layer2b/builder.py | ✅ `grep -n "_COACHED_INTRO_KEYWORDS\|_mentions_coached_intro" layer2b/builder.py` returns 0 hits |
| `_load_skill_capability_toggle_defs` defined in layer2b/builder.py | ✅ `grep -n "def _load_skill_capability_toggle_defs" layer2b/builder.py` returns hit |
| `_load_skill_capability_toggle_defs` defined in layer2c/builder.py | ✅ `grep -n "def _load_skill_capability_toggle_defs" layer2c/builder.py` returns hit |
| Layer 2B + 2C public functions accept `skill_toggle_states` kwarg | ✅ `grep -n "skill_toggle_states:" layer2b/builder.py layer2c/builder.py` returns both function defs + or-normalize lines |
| Orchestrator threads `skill_toggle_states` at 3 call sites | ✅ `grep -c "skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states" layer4/orchestrator.py` returns 3 |
| TRN-011 prescription_note keyword triggers stripped | ✅ `grep -n "requires supervised instruction\|requiring coached introduction" etl/sources/populate_terrain_gap_rules.sql` returns 0 hits |
| TRN-011 prescription_note credits whitewater_handling toggle | ✅ `grep -n "whitewater_handling" etl/sources/populate_terrain_gap_rules.sql` returns hit |
| NEW `TestSkillCapabilityFlag` in test_layer2b.py (5 tests) | ✅ pytest run in 0.42s; 5 tests under TestSkillCapabilityFlag |
| Old `TestCoachedIntroFlag` removed from test_layer2b.py | ✅ `grep -n "TestCoachedIntroFlag\|test_whitewater_coached_intro_flag" tests/test_layer2b.py` returns 0 hits |
| NEW `TestSkillCapabilityFlag` in test_layer2c.py (5 tests) | ✅ pytest run in 0.45s; 5 tests under TestSkillCapabilityFlag |
| `_FakeConn` in test_layer2c.py handles skill_capability_toggles SQL | ✅ `grep -n "skill_capability_toggles" tests/test_layer2c.py` returns hits in _FakeConn + queue helpers + test rows |
| import-order workaround added to test_layer1_builder.py | ✅ `grep -n "from layer4 import InMemoryCacheBackend" tests/test_layer1_builder.py` returns hit |
| `_queue_empty_athlete` bumped 24 → 25 + test renamed | ✅ `grep -n "range(25)\|test_25_selects_issued" tests/test_layer1_builder.py` returns 2 hits |
| NEW `TestSkillToggleStates` in test_layer1_builder.py (3 tests) | ✅ pytest run in 0.37s; 3 tests under TestSkillToggleStates |
| Predecessor reproducer subset 941 → 949 + 12 skipped | ✅ pytest run in 1.45s |
| test_layer1_builder.py standalone 19 → 22 | ✅ pytest run in 0.37s |
| ETL `etl/tests/` 139 → 139 | ✅ pytest run in 0.49s |
| All 6 edited Python files pass `py_compile` | ✅ `python3 -m py_compile init_db.py layer4/context.py layer1/builder.py layer2b/builder.py layer2c/builder.py layer4/orchestrator.py` clean |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C (l) line flipped ✅ shipped + Bucket C marked FULLY CLOSED + §5.0 walkthrough scenario added (5 steps) + scenario count 90 → 95 | ✅ |
| Branch renamed from harness-pinned scope-mismatch to scope-matching | ✅ `git branch --show-current` returns `claude/skill-capability-toggles-bucketc-l` (was `claude/terrain-equipment-merge-hGi4Q`) |

---

## 9. Files shipped this session

**Substantive (12 files; ceiling break ratified at AskUserQuestion gate; precedents BucketC_i=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13):**

1. MODIFIED `etl/layer0/schema.sql` — NEW `CREATE TABLE IF NOT EXISTS layer0.skill_capability_toggles` mirroring sport_specific_gear_toggles shape minus gear-specific cols + plus `gated_terrain_ids TEXT[]`.
2. NEW `etl/sources/populate_skill_capability_toggles.sql` — 5 vocab rows at `0C-v2.0-r2` with display_label + description + tightened gated arrays + ON CONFLICT idempotency + verify block.
3. MODIFIED `init_db.py` — NEW `athlete_skill_toggles` table CREATE wired as new `_PG_MIGRATIONS` entry + `ast_user_idx` index.
4. MODIFIED `layer4/context.py` — Layer1Lifestyle gains `skill_toggle_states` field + Layer2CCoachingFlag.flag_type Literal extended with `"requires_skill_capability"`.
5. MODIFIED `layer1/builder.py` — NEW `_load_skill_toggle_states` helper + wire into `Layer1Lifestyle(...)` constructor.
6. MODIFIED `layer2b/builder.py` — rip keyword-match block + NEW `_load_skill_capability_toggle_defs` SQL loader + new `skill_toggle_states` kwarg + new emission block in `_emit_coaching_flags`.
7. MODIFIED `layer2c/builder.py` — parallel `_load_skill_capability_toggle_defs` + new `skill_toggle_states` kwarg + new emission block after `toggle_off_for_discipline`.
8. MODIFIED `layer4/orchestrator.py` — 3 call sites threaded (2B in `_upstream_full_cone` + 2C in `_upstream_full_cone` + 2C in single-session orchestrator).
9. MODIFIED `etl/sources/populate_terrain_gap_rules.sql` — TRN-011 prescription_note text rewritten to drop keyword-match triggers + credit whitewater_handling toggle.
10. MODIFIED `tests/test_layer2b.py` — removed TestCoachedIntroFlag (2 tests) + NEW TestSkillCapabilityFlag (5 tests).
11. MODIFIED `tests/test_layer2c.py` — _FakeConn extended with skill_capability_toggles SQL detection + NEW TestSkillCapabilityFlag (5 tests).
12. MODIFIED `tests/test_layer1_builder.py` — import-order workaround for pre-existing circular import + counter bumps + NEW TestSkillToggleStates (3 tests).

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

13. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BucketC_g line preserved.
14. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket C (l) line flipped ✅ shipped; Bucket C marked FULLY CLOSED; NEW 5-step Manual §5.0 walkthrough scenario added; scenario count 90 → 95.
15. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_l_SkillCapabilityToggles_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C sub-item (l) closed end-to-end** ✅ — runtime contract shipped, athlete-side capture surface deferred to focused follow-on. **Bucket C now FULLY CLOSED — all 11 sub-items (a/b/c/d/e/f/g/h/i/j/k/l) shipped end-to-end.**
- **NEW 5-step Manual §5.0 walkthrough scenario** — schema spot-check + orchestrator-surfaces-default-OFF-flags-for-Andy / enable-two-toggles-flag-disappear / TRN-011-race-terrain-test / populate-script-idempotency.
- **NEW capture-surface forward-pointer** — profile-edit tab `?tab=skills` 5-checkbox grid + POST handler + cache invalidation policy. ~3-4 substantive files; could pair with onboarding-step integration as a single combined slice.
- **Best-fit modality cross-reference forward-pointer (carried from BucketC_g) gains skill_toggle_states as input** — design slice will reason `{locale_terrain_ids + cluster_equipment + included_disciplines + skill_toggle_states} → recommended modality per session`.
- **Pre-existing forward-pointers carried** — #8 locales→locations rename remains the lowest-risk mechanical slice; Layer 2B per-discipline gap reasoning (consume C1) still queued; #6 + #4 injury form refresh / #2b race-URL site-parse / §I.1 structured supplements / Bucket D legacy hardcoded locales (now unblocked since Bucket C is fully closed) all carry.

**End of handoff.**
