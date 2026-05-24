# D-73 Phase 5.2 Walkthrough — Bucket C sub-item (g) Terrain↔Equipment Merge — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — picks up the §6.2 alt-pivot menu from the predecessor BucketC_i_MapboxRequired slice. Closes Bucket C sub-item (g) end-to-end via NEW TRN-020 Gravel canonical terrain row + retirement of the 9 display-only "Outdoor & Terrain" equipment tags + idempotent `_PG_MIGRATIONS` translation that maps existing `locale_equipment` + `locale_equipment_overrides` picks for the retired tags into `locale_profiles.locale_terrain_ids` then deletes the source rows + the 9 `equipment_items` rows themselves. Pins the architectural principle that **terrain rows describe SURFACE only**; modality (foot / bike / paddle) is captured discipline-side + equipment-side via a future best-fit cross-reference. Closes the second-to-last open Bucket C sub-item; only (l) skill toggles remains.
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_i_MapboxRequired_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/v5-phase-5-2-walkthrough-DoBxL` (harness-pinned)
**Status:** 6 substantive files (ceiling break ratified at AskUserQuestion gate; precedents BucketC_i=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13). Container-runnable subset 901 → 906 (+5 net new in NEW `TestGravelTerrainAdd`). ETL `etl/tests/` 139 → 139 unchanged. No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → predecessor BucketC_i_MapboxRequired handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep ✅ clean — the 4 ❌ entries on `tests/test_extractor_parsers.py` / `tests/test_sum_to_100.py` / `tests/test_v10_parsers.py` / `tests/test_vocabulary_md.py` are the known false-positives (those files live under `etl/tests/`, not `tests/`; the script doesn't know about the nested test tree, confirmed via `ls etl/tests/`). Working tree clean on the harness-pinned branch. Predecessor §8 anchors spot-checked: `_check_event_locale_mapbox_id_required` validator present in `layer4/context.py`; Mapbox-required gates present on all 4 POST handlers (`new_race`, `update_race`, `set_locale`, `target_race_save`); `_race_row` fixture default carries `event_locale_mapbox_id="poi.test_anchor"`. 901 baseline confirmed (901 passed + 12 skipped on the predecessor's reproducer subset in 1.86s) + 139 ETL confirmed. No drift between predecessor handoff narrative and on-disk state.

Andy picked **Bucket C sub-item (g) terrain↔equipment merge** at the first AskUserQuestion gate over the architect-recommended #8 locales→locations rename + Bucket C (l) skill toggles + Layer 2B per-discipline gap reasoning.

---

## 2. Session narrative

The (g) sub-item lived as a forward-pointer through every Bucket C session since the TerrainVocabAuditClosure slice: "Terrain accessible from this location" multi-checkbox grid + "Outdoor & Terrain" equipment fieldset on the locale-edit form ask overlapping questions of the athlete. The terrain grid (17 TRN-xxx rows pre-this-slice) is the canonical vocab; the 9-tag equipment fieldset (trail_running / road_running / road_cycling / mtb_trails / gravel_routes / open_water_paddle / open_water_swim / pool_swim / hills) is a v1-era display surface. CARRY_FORWARD line 106 flagged this as Trigger #3 cross-layer schema (crosses `layer0.terrain_types` vs `layer0.equipment_items`); plan-mode gate needed before implementation.

**Plan-mode design pass — three nested AskUserQuestion gates:**

| # | Gate | Andy's pick | Notes |
|---|---|---|---|
| G1 | First-gate (slice picking) — what to work on? | **Bucket C (g) terrain↔equipment merge** | Over #8 locales→locations rename + (l) skill toggles + Layer 2B per-discipline gap reasoning. |
| G2 | Second-gate (merge direction) — three architectural classes? | **B-prime: expand terrain vocab, retire equipment category** | Over D-narrow (hide+derive 4 mappable tags, keep 5 vehicle/elevation tags in renamed fieldset) + C (cross-reference mapping only, both surfaces still visible). B-prime gives single source of truth + single form checkbox grid. |
| G3 | Third-gate (vocab scope shape) — how many new TRN rows? | **S2: +1 row (TRN-020 Gravel) only** | Over S1 (zero new rows; accept the gravel gap) + S3 (3 cycling-category rows + ceiling-break larger). S2 minimum vocab additions; Trigger #2 clean (gravel is the unambiguous gap; cycling-on-paved is the same surface as running-on-paved). |

**Slice-shape ratification gate (post-design):** ratify the 6-file scope + judgment calls on conservative open_water_paddle mapping ({TRN-009} only) + hard DELETE of the 9 equipment_items rows + ceiling break. Andy ratified plus added a critical clarification: **terrain should be surface-specific; modality (foot / bike / paddle) should be cross-referenced elsewhere via a best-fit concept** — e.g., athlete with gravel_bike + road terrain + gravel terrain → planner recommends a gravel ride since it's a better fit to the equipment than the road. This validates the S2 framing (1 row, no modality split) and goes in §7 D-decisions + §6 forward-pointers as the next-architectural-slice concept.

**Critical pre-code finding (changed the design):** the 9 "Outdoor & Terrain" equipment tags are *display-only* venue markers with NO downstream consumer. `validator.py:139,143` hits for `trail_running` / `outdoor_road_cycling` are DISCIPLINE names (frozen-set of `_OUTDOOR_ONLY_DISCIPLINES`), not equipment tags. Garmin/FIT files use `trail_running` as a sport-type string in `garmin_connect.py:32,51` + `garmin_fit_parser.py:11,49,64,69,281` + `fit_workout_generator.py:27` — also not equipment tags. NO Layer 2C exercise gate reads these as equipment availability. This means the merge surface is much smaller than B-prime first implied: no Layer 2C re-routing needed; the 9 tags can just be retired with translation to terrain ids.

**Coverage map of the 9 retired tags against the existing 17 TRN rows (pre-this-slice):**
- `trail_running` → TRN-002 (Groomed Trail) + TRN-003 (Technical Trail) ✅
- `road_running` → TRN-001 (Road / Paved) ✅
- `road_cycling` → TRN-001 (same paved surface; modality is discipline-side)
- `mtb_trails` → TRN-002 + TRN-003 (same dirt singletrack; modality is discipline-side)
- `gravel_routes` → ❌ **genuine vocab gap** — no TRN row covers compacted-gravel surface (TRN-001 is paved, TRN-002 is dirt singletrack, TRN-004 is elevation-keyed not surface-keyed)
- `open_water_paddle` → TRN-009/010/011/017 all cover paddle-water access; conservative mapping uses {TRN-009 only}
- `open_water_swim` → TRN-009 (Flat Water) + TRN-010 (Ocean / Tidal) ✅
- `pool_swim` → TRN-008 (Pool) ✅
- `hills` → TRN-004 (Hill / Rolling); NOT TRN-005 Mountain/Alpine (much more demanding)

So TRN-020 Gravel becomes the one canonical row to add. TRN-018 and TRN-019 are intentionally reserved for future cycling-vocab expansion if Andy ratifies S3 later — the audit test locks in the sequence gap so an accidental TRN-018/019 addition without ratification surfaces loudly.

---

## 3. File-by-file edits

### 3.1 `etl/layer0/extractors/vocabulary.py` — NEW TRN-020 Gravel row

Inserted after TRN-007 (last Foot row) in the source-order Foot section so Foot category stays contiguous. Attributes: Foot category, `requires_elevation=False`, `technical_surface=False`, `environment="Outdoor"`, `simulatable="partial"`. Comment block above the row pins the surface-only architectural principle + the modality-via-future-best-fit-cross-reference forward-pointer. `simulation_note` explicitly covers both treadmill-for-running and trainer-for-cycling substitutes with gravel-specific surface gap. `notes` distinguishes gravel from TRN-001 (paved) + TRN-002 (singletrack), names both gravel-running and gravel-cycling use cases. `_parse_terrain` docstring count flipped 16 → 18 (also corrects pre-existing drift from WaterVocab slice that left docstring saying 16 when actual was 17).

### 3.2 `etl/sources/populate_terrain_gap_rules.sql` — 2 NEW gap rules + drift fix

NEW "Foot: Gravel gaps" section inserted between Fell/Moorland and Ocean/Tidal sections:
- TRN-020 → TRN-002 (Groomed Trail) proxy fidelity 0.70 `low` band — singletrack covers unpaved-surface gait at high fidelity; only the loose-aggregate stimulus is gravel-specific; 1-2 sessions close it.
- TRN-020 → TRN-001 (Road / Paved) proxy fidelity 0.65 `medium` band — paved covers gait + aerobic at full fidelity; gravel-specific surface adaptation requires real exposure; 2-4 sessions in final 4 weeks before race.

Both rows comment-explain the modality-agnostic use (gravel-cycling works the same way via MTB / gravel bike on any compacted-aggregate surface). Classifier ORDER BY proxy_fidelity DESC picks whichever proxy the athlete has access to.

**Drift fix:** the file's header comment ("12 canonical gap rows") + §2 comment ("Insert 12 gap rules") + verify-block row-count assertion (`IF row_count <> 12 THEN RAISE EXCEPTION`) + RAISE NOTICE were all stale at 12 after the WaterVocabExpansion slice landed 2 new rows. A clean re-deploy of this file would have RAISED. Bumped all 4 references to 16 (= 12 original + 2 WaterVocab + 2 BucketC_g) and added an inline header annotation citing the row-count audit trail.

### 3.3 `init_db.py` — 3 changes

**(a) NEW `_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` module-level dict** (defined above _PG_MIGRATIONS alongside the precedent `_seed_purchase_recommendations` helper). Documents the SURFACE-only principle + the conservative open_water_paddle pick + the future best-fit cross-reference forward-pointer. Mapping:
```python
{
    "trail_running":     ["TRN-002", "TRN-003"],
    "road_running":      ["TRN-001"],
    "road_cycling":      ["TRN-001"],
    "mtb_trails":        ["TRN-002", "TRN-003"],
    "gravel_routes":     ["TRN-020"],
    "pool_swim":         ["TRN-008"],
    "open_water_swim":   ["TRN-009", "TRN-010"],
    "open_water_paddle": ["TRN-009"],  # conservative
    "hills":             ["TRN-004"],  # NOT TRN-005 Mountain/Alpine
}
```

**(b) NEW `_retire_outdoor_terrain_equipment_tags(cur)` migration callable** (~85 LOC). 5-step idempotent translation+delete:
1. UPDATE `locale_profiles` translating `locale_equipment` (private-locale) picks tied to retired tags via a JOIN-LATERAL-unnest with the mapping injected as a VALUES CTE; UNION dedupe-sort into `locale_terrain_ids`.
2. UPDATE `locale_profiles` translating `locale_equipment_overrides` (shared-profile) action='add' picks via the same CTE; action='remove' overrides are no-ops against a retired baseline.
3. DELETE locale_equipment rows for retired tags (parameterised `equipment_tag = ANY(%s)` via psycopg2 `cur.execute(sql, (retired_tags,))`).
4. DELETE locale_equipment_overrides rows for retired tags (both action='add' and action='remove').
5. DELETE the 9 equipment_items rows themselves — no exercise_equipment FK risk verified at scope (no EXERCISE_EQUIPMENT seed entry references any of the 9 retired tags).

Idempotency: re-run after a successful pass is a no-op because the retired tag rows no longer exist in equipment_items, so the JOINs return 0 rows and the UPDATE matches zero locales; the DELETEs are also no-ops. Safe on fresh deploys where the tags never existed.

**(c) Removed lines 1826-1836 from `EQUIPMENT_CATEGORIES`** — the entire `('Outdoor & Terrain', [ … ])` entry deleted and replaced with a multi-line comment citing the Bucket C (g) ratification + retained-as-is Cycling Equipment + Paddling Equipment categories which are real gear, not venue markers.

**(d)** Migration callable wired into `_PG_MIGRATIONS` as the final entry (after the `cap_overridden` ALTER), referenced by name so the runner's `if callable(stmt): stmt(cur)` branch fires.

### 3.4 `tests/test_bucket_c_terrain_vocab_audit.py` — TestCanonicalTerrainVocab updates + NEW TestGravelTerrainAdd

- `TestCanonicalTerrainVocab` class docstring updated to reflect 18-row shape + TRN-018/019 reserved-gap rationale.
- `test_canonical_row_count_is_17` → `test_canonical_row_count_is_18`; assertion flipped.
- `test_canonical_ids_are_sequential_TRN_001_through_TRN_017` → `test_canonical_ids_are_TRN_001_through_017_plus_020`; expected list = `sorted([f"TRN-{i:03d}" for i in range(1, 18)] + ["TRN-020"])`.

NEW `TestGravelTerrainAdd` (5 tests):
1. `test_gravel_row_exists` — TRN-020 with canonical_name "Gravel" exists.
2. `test_gravel_row_is_foot_category_surface_only` — Foot category + Outdoor + simulatable=partial + technical_surface=False + requires_elevation=False. Pins the SURFACE-only principle in the test layer.
3. `test_gravel_notes_describe_surface_not_modality` — `notes` contains "compacted" or "unpaved" + acknowledges both "gravel-running" and "gravel-cycling" use cases.
4. `test_gravel_simulation_note_does_not_request_coaching` — forward-compat with Bucket C (l) skill-toggle pivot (same pattern as the WaterVocab slice's TRN-017 no-coaching-language test).
5. `test_outdoor_terrain_equipment_tags_retired_from_init_db` — imports `init_db.EQUIPMENT_CATEGORIES`, asserts "Outdoor & Terrain" not in category names AND none of the 9 retired tags reappear in any other category. Locks in the retirement guarantee mechanically — a future re-introduction would fail this test loudly.

Module docstring updated with NEW "Sub-item closure (added by the BucketC_g_TerrainEquipmentMerge slice 2026-05-24)" block + NEW "Sub-items recently closed (forward-pointer audit trail)" block citing the BucketC_i closure (since the audit-trail keeps the file useful for grep-by-bucket-letter).

### 3.5 `etl/tests/test_vocabulary_md.py` — terrain-section updates

- `test_terrain_count` 17 → 18 + comment updated with bump audit trail (16 → 17 from WaterVocab + 17 → 18 from BucketC_g).
- `test_terrain_ids_unique_and_sequential` expected list rewritten as `[TRN-001..TRN-017] + [TRN-020]` with comment documenting the reserved-gap intent.
- `test_terrain_known_canonical_names_present` adds "Gravel" to the presence list.

### 3.6 `tests/test_locales.py` — UNCHANGED, verified zero regressions

27 → 27 passing. The `TestEvictLayer2cOnEquipmentChange` class is keyed on the parent equipment-edit eviction surface, not on the specific retired tags. The template-render path is auto-skip via the existing `{% for category, items in equipment_categories %}` for-loop since `EQUIPMENT_CATEGORIES` no longer contains the "Outdoor & Terrain" entry.

(File counted in the substantive total because it's part of the regression-verification surface — the locale form is the primary athlete-visible touchpoint of the slice, and the unchanged-but-verified state is the contract pin.)

---

## 4. Code / tests

**Tests:** container-runnable subset 901 → 906 (+5 net new: 5 in NEW TestGravelTerrainAdd; 0 regressions); ETL `etl/tests/` 139 → 139 unchanged. No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a / layer2b surfaces; 12 NL parser smoke + 4 Layer 3 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

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
  tests/test_layer2a.py tests/test_layer2b.py tests/test_bucket_c_terrain_vocab_audit.py
# 906 passed, 12 skipped in 1.71s
```

ETL: `PYTHONPATH=. python3 -m pytest etl/tests/ # 139 passed in 0.53s`.

**py_compile:** `init_db.py` clean (`python3 -m py_compile init_db.py`).

---

## 5. Manual §5.0 verification — owed step

NEW 4-step walkthrough scenario added to `CARRY_FORWARD.md` §5.0 list. Summarized:

1. **Locale-edit form fieldset count + new layout** — confirm `/locales/home/edit` + `/locales/<shared_locale>/edit` no longer show the "Outdoor & Terrain" equipment fieldset; the locale-terrain grid shows 18 options including the NEW "TRN-020 — Gravel" entry.
2. **Post-migration data spot-check** — `SELECT user_id, locale, locale_terrain_ids FROM locale_profiles WHERE user_id=<andy>` shows translated TRN-xxx ids unioned in; `SELECT COUNT(*) FROM equipment_items WHERE tag IN (...9 retired tags...)` returns 0; no FK violations.
3. **TRN-020 selectable from race-event terrain editor** — confirm `/profile/race-events/<id>/edit` + `/onboarding/target-race` both show "TRN-020 — Gravel" as a selectable option in the per-row terrain dropdown.
4. **Layer 2B gap-rule round-trip for TRN-020** — temporarily edit a test race row (NOT PGE 2026) to have TRN-020 in race_terrain; confirm Layer 2B picks TRN-002 as proxy (fidelity 0.70 low) since it ORDERs DESC; prescription_note mentions gravel-specific surface adaptation.

Andy's PGE 2026 row is not affected by this slice (no terrain-vocab semantics change for the rows he's already picked); only the locale-edit form layout and the migrated locale_terrain_ids would change for him.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**#8 "locales" → "locations" terminology rename** remains the lowest-risk next-slice candidate (carried forward through every recent handoff; ~9 templates, mechanical, no `/plan` triggers). Affected templates pinned at `CARRY_FORWARD.md`.

### 6.2 Alternative pivots

- **Bucket C sub-item (l): skill-capability toggles** — Trigger #3 + Trigger #5 plan-mode gate. Defaults pre-pinned by Andy at the WaterVocabExpansion gate (assume-not-skilled; narrow vocab = climbing/whitewater/swim ability). ~6-8 substantive files. Now the *only* open Bucket C sub-item.
- **NEW best-fit modality cross-reference design** — surfaced by Andy at this slice's gate. Design pass that lets a planner read `{locale_terrain_ids + cluster_equipment + included_disciplines}` and return per-session "recommended modality" (gravel-bike + TRN-020 → gravel ride; only road bike + TRN-001 → road ride; etc.). Concrete shape TBD (mapping table vs derived join vs Layer 4 prompt-side reasoning). Not blocking any current open Bucket items but unlocks athlete-facing reasoning that's currently latent. Plan-mode gate required (Trigger #1 if prompt-side; Trigger #3 if schema-side; Trigger #5 either way for picking among shapes).
- **Layer 2B per-discipline gap reasoning (consume C1)** — Trigger #1 prompt-body update. Now unblocked since C1 shipped the data shape; ~3-5 files including spec + prompt + tests.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.
- **Bucket D — legacy hardcoded locales (a + b)** — now unblocked (Bucket C terrain-vocab decisions are landed; the dependency was on (g) being resolved, and (g) just shipped).
- **Manual §5.0 walkthrough** — accumulated 90 scenarios pending; this slice's 4-step scenario joins the list. The most recent shipped surfaces (BucketC_i_MapboxRequired + BucketE_B2_C1 + WaterVocabExpansion + RouteLocalesAnchorFlags + ETLTerrainVocabDriftFix) are all unwalked.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C (g) flipped ✅; Bucket C still has (l) open; 90 §5.0 scenarios pending).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_g_TerrainEquipmentMerge_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. The script's 4 ❌ false-positives on ETL test files still present (script doesn't know about `etl/tests/`); verify via `ls etl/tests/`.

**No outstanding production warnings.** Bucket C: now 10 of 11 sub-items closed (a/b/c/d/e/f/g/h/i/j + k); 1 still open — (l) skill toggles (Trigger #3 + #5 plan-mode). Bucket E: fully closed.

**Backward-compat note for next deploy:** the new `_retire_outdoor_terrain_equipment_tags` migration runs on next Neon boot. Fully idempotent (re-runnable; safe on fresh deploys). After the migration:
- Athletes who previously picked any of the 9 retired tags in the Outdoor & Terrain fieldset will have those picks translated to TRN-xxx ids in `locale_profiles.locale_terrain_ids` (union with existing picks, deduped).
- The 9 `equipment_items` rows will be deleted along with all `locale_equipment` + `locale_equipment_overrides` rows that referenced them.
- No FK violations expected — verified at scope that no exercise_equipment seed entry references any of the 9 retired tags.
- Spot-check Andy's home locale: `SELECT locale_terrain_ids FROM locale_profiles WHERE user_id=<andy> AND locale='home'` should show terrain ids including any translations from his prior Outdoor & Terrain picks.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Merge direction = B-prime (expand terrain vocab + retire equipment fieldset) | Andy at second AskUserQuestion gate | Over D-narrow (hide+derive 4 mappable tags; keep 5 vehicle/elevation tags in renamed fieldset — still athlete-visible dup of the abstraction) + C (cross-reference mapping only; both fieldsets stay visible, just sync-checked — doesn't fully solve UX dup). B-prime gives single source of truth + single form checkbox grid. The dup is the trigger; resolving it via vocab consolidation is the cleanest answer. |
| **D2** | Scope shape = S2 (+1 row TRN-020 Gravel only; sunset 9 equipment tags) | Andy at third AskUserQuestion gate | Over S1 (zero new rows; accept the gravel gap) + S3 (3 cycling-category rows TRN-018+019+020 + ceiling-break larger). S2 passes Trigger #2 cleanly because gravel IS an unambiguous surface that maps to no existing TRN row (TRN-001 is paved, TRN-002 is dirt singletrack, TRN-004 is elevation-keyed). S3's cycling-modality rows would pad the vocab where the surface-vs-modality split semantically belongs elsewhere (per D3). TRN-018/019 intentionally reserved for future S3 ratification if Andy reverses; sequence gap locked in by the audit test. |
| **D3** | Architectural principle: terrain rows describe SURFACE only; modality (foot/bike/paddle) is captured discipline-side + equipment-side; future best-fit cross-reference does the joining | Andy at slice-shape ratification gate | Andy: "terrain should be surface specific. we should cross reference what modalities can be trained on a surface elsewhere with a best-fit concept. for example, that way a plan could see the user has a gravel bike, road terrain, and gravel terrain. and select that the planned session should recommend a gravel ride since it is a better fit to the equipment than the road." This pinned principle validates the S2 1-row scope and seeds a NEW forward-pointer for a separate slice that designs the best-fit cross-reference (concrete shape TBD: mapping table vs derived join vs Layer 4 prompt-side reasoning). |
| **D4** | Conservative open_water_paddle mapping = {TRN-009} only (Flat Water) | Andy at slice-shape ratification gate | Over full-union {TRN-009/010/011/017}. Over-granting water-access fakes skill access the athlete may not have — TRN-010 Ocean/Tidal carries salt/cold/swell stimuli + TRN-011 Whitewater has coached-intro semantics + TRN-017 Moving Water has river-current handling. Athlete who only paddled a lake shouldn't be auto-granted ocean access. Athlete can add the other water rows explicitly on next locale edit. |
| **D5** | hills mapping = {TRN-004} only (Hill / Rolling); NOT TRN-005 Mountain/Alpine | Architect at code-time (same logic as D4) | TRN-005 represents much more demanding sustained vertical with technical_surface=True + Above-Treeline territory. Athlete who checked the generic `hills` equipment tag almost certainly meant local rolling terrain, not alpine. Conservative mapping prevents over-granting. |
| **D6** | Hard DELETE of the 9 equipment_items rows (not tombstone-with-superseded_at) | Andy at slice-shape ratification gate | equipment_items is a v1-era vocab table without `superseded_at` semantics (no version-row pattern). The 9 rows are display-only venue markers with zero downstream consumers verified at scope (no exercise_equipment FK, no Layer 2C gate). Clean DELETE matches the existing FK behavior. Re-introduction would require an explicit migration to re-insert. |
| **D7** | 6-file ceiling break ratified | Andy at slice-shape ratification gate | 6 substantive files (1 vocab + 1 SQL + 1 init_db + 2 tests + 1 verified-unchanged locale test). Precedents: BucketC_i=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13. Modest break; nature of the work spans vocab + migration + tests so the file fan-out is inherent. |
| **D8** | Fix pre-existing WaterVocab gap-rule-SQL drift in passing | Architect at code-time | The WaterVocabExpansion slice (2026-05-24 earlier) added 2 new gap rules but didn't bump the file's `<>12` verify assertion or "12 canonical gap rows" comments. A clean re-deploy of the SQL file would RAISE. Since I'm editing the same file anyway to add 2 more rows, bumping all 4 references to 16 is a low-cost trap-removal that prevents the next ETL session from hitting it. Doc-sweep nit upgrades to in-line fix. |
| **D9** | Migration callable rather than multi-SQL-string | Architect at code-time | The _PG_MIGRATIONS runner supports both. The 5-step translate-then-delete logic with two parallel CTEs (locale_equipment private + locale_equipment_overrides shared) is materially cleaner as one callable than 5 raw SQL strings. Each callable runs in its own transaction same as a string. Sets a precedent for any future migration with non-trivial multi-step logic. |
| **D10** | TRN-020 placed in Foot category (not a new "Mixed" or "Cycling" category) | Architect at code-time | The existing 17 rows treat category as descriptive of the typical activity context (TRN-001 Road / Paved is Foot category even though the surface serves both running and cycling). Adding a new category for one row would over-classify. Foot maintains the existing convention. The `Layer 2B classifier` doesn't key on category anyway — it keys on terrain_id, gap_severity, proxy_fidelity. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| TRN-020 Gravel row added to `_TERRAIN_STRUCTURED_ROWS` | ✅ `grep -n "TRN-020" etl/layer0/extractors/vocabulary.py` returns hits in row block + docstring |
| `_parse_terrain` docstring count bumped to 18 | ✅ `grep -n "Returns the 18" etl/layer0/extractors/vocabulary.py` returns hit |
| 2 NEW gap rules for TRN-020 in populate_terrain_gap_rules.sql | ✅ `grep -c "'TRN-020', 'Gravel'" etl/sources/populate_terrain_gap_rules.sql` returns 2 |
| Gap-rule verify block updated to expect 16 rows | ✅ `grep -n "expected 16 rows" etl/sources/populate_terrain_gap_rules.sql` returns hit |
| `_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` mapping defined in init_db.py | ✅ `grep -n "_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS" init_db.py` returns 2 hits (dict + migration use) |
| `_retire_outdoor_terrain_equipment_tags` callable defined | ✅ `grep -n "def _retire_outdoor_terrain_equipment_tags" init_db.py` returns hit |
| Migration callable wired into `_PG_MIGRATIONS` list | ✅ `grep -B1 "_retire_outdoor_terrain_equipment_tags,$" init_db.py` returns the entry inside the migrations list |
| "Outdoor & Terrain" category removed from EQUIPMENT_CATEGORIES | ✅ `grep -n "'Outdoor & Terrain'" init_db.py` returns 0 hits |
| 9 retired tags absent from EQUIPMENT_CATEGORIES | ✅ `grep -E "'(trail_running\|road_running\|road_cycling\|mtb_trails\|gravel_routes\|open_water_paddle\|open_water_swim\|pool_swim\|hills)'" init_db.py` returns hits only in `_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` (migration mapping) |
| NEW `TestGravelTerrainAdd` (5 tests) | ✅ pytest run in 0.42s |
| TestCanonicalTerrainVocab row count assertion flipped to 18 | ✅ `grep -n "test_canonical_row_count_is_18" tests/test_bucket_c_terrain_vocab_audit.py` returns hit |
| ETL test_terrain_count bumped to 18 | ✅ `grep -n "len(parsed\[\"terrain_types\"\]) == 18" etl/tests/test_vocabulary_md.py` returns hit |
| ETL terrain known names list includes "Gravel" | ✅ `grep -A12 "test_terrain_known_canonical_names_present" etl/tests/test_vocabulary_md.py` shows "Gravel" in the for-loop list |
| `tests/test_locales.py` UNCHANGED + still passes | ✅ 27 passed in 0.54s — no regressions from equipment-fieldset retirement |
| Container-runnable subset 901 → 906 pass + 12 skipped | ✅ pytest run in 1.71s |
| ETL `etl/tests/` 139 → 139 pass | ✅ pytest run in 0.53s |
| `init_db.py` passes `py_compile` | ✅ |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C (g) line 106 flipped ✅ shipped + §5.0 walkthrough scenario added (4 steps) + scenario count 86 → 90 | ✅ |

---

## 9. Files shipped this session

**Substantive (6 files; ceiling break ratified at AskUserQuestion gate; precedents BucketC_i=12, BucketE_B2_C1=11+5, RaceLocaleMapbox=13):**

1. MODIFIED `etl/layer0/extractors/vocabulary.py` — NEW TRN-020 Gravel row in `_TERRAIN_STRUCTURED_ROWS`; `_parse_terrain` docstring count 16 → 18.
2. MODIFIED `etl/sources/populate_terrain_gap_rules.sql` — 2 NEW gap rules (TRN-020 → TRN-002 fidelity 0.70 low + TRN-020 → TRN-001 fidelity 0.65 medium); pre-existing WaterVocab drift fixed (header count + §2 comment + verify-block row-count + RAISE NOTICE all bumped from 12 to 16).
3. MODIFIED `init_db.py` — NEW `_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` mapping dict + NEW `_retire_outdoor_terrain_equipment_tags(cur)` migration callable + 9-tag removal from `EQUIPMENT_CATEGORIES` ("Outdoor & Terrain" entry deleted entirely, replaced with comment block) + migration wired as final `_PG_MIGRATIONS` entry.
4. MODIFIED `tests/test_bucket_c_terrain_vocab_audit.py` — TestCanonicalTerrainVocab row count + sequence assertion updates (17 → 18; sequence list adjusted for TRN-018/019 reserved gap); NEW `TestGravelTerrainAdd` class (5 tests); module docstring updated.
5. MODIFIED `etl/tests/test_vocabulary_md.py` — `test_terrain_count` 17 → 18; `test_terrain_ids_unique_and_sequential` expected list adjusted; `test_terrain_known_canonical_names_present` adds "Gravel".
6. UNCHANGED-BUT-VERIFIED `tests/test_locales.py` — 27 → 27 passing; verified zero regressions from the equipment-fieldset retirement.

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

7. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BucketC_i_MapboxRequired line preserved.
8. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket C (g) line 106 flipped ✅ shipped (long-form rationale + decisions + forward-pointers inline); NEW 4-step Manual §5.0 walkthrough scenario added; scenario count 86 → 90.
9. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_g_TerrainEquipmentMerge_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C sub-item (g) closed end-to-end** ✅ — Bucket C now: 10 of 11 sub-items closed (a/b/c/d/e/f/g/h/i/j + k); 1 still open — (l) skill toggles (Trigger #3 + #5 plan-mode; spec pre-pinned at WaterVocabExpansion gate).
- **NEW 4-step Manual §5.0 walkthrough scenario** — locale-edit form fieldset count + 18-row terrain grid / post-migration data spot-check / TRN-020 selectable from race-event editor + onboarding mirror / Layer 2B gap-rule round-trip with TRN-020.
- **NEW best-fit modality cross-reference forward-pointer** — design slice that lets a planner read `{locale_terrain_ids + cluster_equipment + included_disciplines}` and return per-session "recommended modality" (gravel-bike + TRN-020 → gravel ride; only road bike + TRN-001 → road ride; etc.). Concrete shape TBD.
- **WaterVocab gap-rule SQL drift fixed in passing** — file's row-count assertion + comments bumped from 12 to 16 (= 12 original + 2 WaterVocab + 2 BucketC_g). Removes a trap for the next ETL session.
- **Pre-existing forward-pointers carried** — #8 locales→locations rename remains the architect-recommended next-slice candidate; (l) still gated; Layer 2B per-discipline gap reasoning (consume C1) still queued; #6 + #4 injury form refresh / #2b race-URL site-parse / §I.1 structured supplements / Bucket D legacy hardcoded locales all carry.

**End of handoff.**
