# D-73 Phase 5.2 Walkthrough Bucket E.(a) Terrain "None" + (b)-B1 framework_sport Override — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — closes Bucket E.(a) (defensive `_terrain_choices` filter against un-migrated terrain rows) + Bucket E.(b)-B1 (per-race `framework_sport` override). Bucket E.(b)-B2 + Bucket E.(c)-C1 deferred to follow-on slice per R3 scope-split at the AskUserQuestion gate.
**Date:** 2026-05-23
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BucketB_500sBugfixes_2026_05_23_Closing_Handoff_v1.md`
**Branch:** `claude/v5-phase-5-2-walkthrough-rCGds` (harness-pinned; system-prompt rule forbids renaming).
**PR:** TBD — open as draft once pushed.
**Status:** 10 substantive files (R3-scope ceiling break ratified at AskUserQuestion gate). Container-runnable subset 793 → 805 (+12 net new tests). No regressions.

---

## 1. Session-start verification (Rule #9)

`./aidstation-sources/scripts/verify-handoff.sh` ran against the BucketB500sBugfixes predecessor handoff. One ❌ on `templates/coaching/generate.html` — false positive carried over from Bucket A's intentional deletion (already documented in the predecessor's §1). All other anchor claims verified on disk. No drift requiring reconciliation. Predecessor merged via PR #129 (`9631b4e`).

---

## 2. Session narrative

Andy opened the session by pointing at the BucketB500sBugfixes handoff and saying "let's work." Following CLAUDE.md first-session checklist + Rule #9: read CLAUDE / CURRENT_STATE / CARRY_FORWARD / predecessor handoff, ran verify-handoff.sh, summarized state + offered next-scope options.

Andy picked **Bucket E (full a+b+c)** at the AskUserQuestion gate. Per Trigger #5 (architectural alternatives with real tradeoffs on (b) and (c)), I presented an options matrix:

- **E.(a)** "None" prepending — investigation surfaced two suspects: (1) literal "None" row in `layer0.terrain_types` seed (ruled out — no such row in `etl/sources/migrate_terrain_types.sql`'s INSERT), (2) un-migrated pre-r2 rows where `terrain_id IS NULL` rendering as `{{ tc.id }}` → Python `None` → `None — <name>` in the dropdown. The standalone `migrate_terrain_types.sql` (NOT in `_PG_MIGRATIONS`, run manually on Neon) supersedes pre-r2 rows + inserts 16 TRN-xxx-keyed rows. If the migration hasn't run on production Neon, the SELECT returns pre-r2 rows. Three options: defensive filter, just confirm migration, both.
- **E.(b)** disciplines on race event creation — four options: B1 (framework_sport override only), B2 (included_discipline_ids include-list), B3 (both), B4 (read-only display).
- **E.(c)** terrain↔discipline coupling — four options: C1 (flat extended with optional discipline_id per terrain row), C2 (hierarchical [{discipline_id, terrain_breakdown:[…]}]), C3 (parallel column), C4 (defer).

Andy's picks: `(a)=defensive filter + also confirm migration`, `(b)=B3 both B1+B2`, `(c)=C1 flat extended`.

File-budget reality-check surfaced ~14 substantive files for the full slice. Presented 3 reduction options. Andy picked **R3 — ship (a) + B1 now, defer B2 + C1 to follow-on slice** (~8 files target, actual count landed at 10 with tests).

Implementation: 10 substantive files. 4 D-decisions ratified at AskUserQuestion gate per Trigger #5 (see §7).

`/plan` Triggers fired: #5 (twice — `(b)` discipline override architecture; `(c)` terrain↔discipline coupling shape).

`/plan` Triggers DEFERRED:

- **Bucket E.(b)-B2 + E.(c)-C1** carried as paired follow-on slice (shape pinned in CARRY_FORWARD entry).
- **Bucket C** (terrain vocab cleanup) — Triggers #2/#3/#5 still owed.
- **Bucket D** (legacy hardcoded `home/hotel/partner/airport`) — depends on C.

---

## 3. File-by-file edits

### 3.1 `init_db.py` — E.(b)-B1 migration

Single ALTER TABLE inserted between `event_locale_lng` and `locale_terrain_ids` migrations:

```python
"ALTER TABLE race_events ADD COLUMN IF NOT EXISTS framework_sport TEXT NULL",
```

8-line comment explaining the override semantics (`Layer 2A's discipline classifier keys on framework_sport via layer0.sport_discipline_bridge; pre-walkthrough the value was always sourced from athlete_profile.primary_sport. New column lets an athlete whose primary sport differs from the target race classify the race correctly without churning their profile. Orchestrator falls back to primary_sport when this is NULL.`).

### 3.2 `race_events_repo.py` — E.(b)-B1 kwarg threading

- `create_race_event` signature gains `framework_sport: str | None = None` kwarg between `race_url` and `is_target_event`. INSERT clause extended with the column at position 19 in the VALUES list (between `race_url` and the `etl_version_set` JSONB cast). Param tuple extended at the matching position. **Positional stability preserved** for all params at positions 0-10 → existing TestCreateRaceEvent positional assertions (`params[0]==user_id`, `params[1]==name`, etc.) pass unchanged.
- `update_race_event` signature gains `framework_sport: str | None = None` kwarg in the same slot. UPDATE clause extended with `framework_sport = ?`.
- `load_race_event_payload` SELECT clause extended with `re.framework_sport`; `RaceEventPayload(framework_sport=race_row['framework_sport'])` passthrough in the constructor.
- `get_race_event` SELECT clause extended with `framework_sport`; `dict(row)` includes it in the returned mapping (template + route consumers).

### 3.3 `race_events_invalidation.py` — new helper

NEW `evict_on_target_event_framework_sport_change(db, user_id, *, cache=None) -> int` helper appended after the existing 3 helpers. Routes through `evict_on_layer_change(cache, user_id, 'layer2a')` — the `layer2a` policy is `_ALL_ENTRY_POINTS + _LAYER3_BOTH` (broader than periodization's `_NON_SINGLE_SESSION` and broader than brief-only's `race_week_brief`-only cut). Rationale: framework_sport change flips Layer 2A's discipline classifier output, which cascades through every downstream entry point + the cached Layer 3A/3B rows that consume layer1 + layer2a hashes.

### 3.4 `layer4/context.py` — RaceEventPayload field

Field appended to `RaceEventPayload` between `race_url` and `route_locales`:

```python
framework_sport: str | None = Field(default=None, max_length=100)
```

5-line comment explaining override semantics + Layer 2A's error surfacing on unresolved values.

### 3.5 `layer4/orchestrator.py` — fallback chain

`_upstream_full_cone` rewrote the framework_sport resolution to a 3-step chain:

```python
framework_sport = (
    target_race_event.framework_sport if target_race_event is not None else None
)
if not framework_sport:
    framework_sport = layer1_payload.identity.primary_sport
if not framework_sport:
    raise OrchestrationError(
        "framework_sport_missing",
        f"layer1.identity.primary_sport is empty for user_id={user_id}",
    )
```

The `framework_sport_missing` error code is preserved (same `OrchestrationError.code`) — callers + tests that pin on this code still work. New path: an athlete with `primary_sport=None` whose target race carries `framework_sport='Adventure Racing'` resolves successfully (covered by `test_override_when_primary_sport_missing_still_classifies`).

### 3.6 `routes/race_events.py` — E.(a) filter + E.(b)-B1 form parsing

**E.(a) filter:** `_terrain_choices` SQL gained `AND terrain_id IS NOT NULL`. 8-line comment explains the root-cause hypothesis (pre-r2 rows un-migrated on Neon).

**E.(b)-B1:**

- Import extended with `evict_on_target_event_framework_sport_change`.
- `new_race` POST: `framework_sport=_parse_str(request.form, 'framework_sport')` threaded into `create_race_event(...)` kwargs.
- `update_race` POST: `new_framework_sport = _parse_str(request.form, 'framework_sport')` parsed; threaded into `update_race_event(...)` kwargs.
- Target-row diff: added `prior_framework_sport = race.get('framework_sport')` + `framework_sport_changed = prior_framework_sport != new_framework_sport`. Eviction chain restructured `if/elif/elif` so framework_sport fires first as the widest cut (periodization + brief-only are subsumed). 6-line comment explains the ordering.

### 3.7 `routes/onboarding.py` — E.(a) filter + E.(b)-B1 mirror

**E.(a) filter:** same `AND terrain_id IS NOT NULL` on the mirror `_terrain_choices`. Comment cross-references `routes/race_events.py:_terrain_choices` for rationale.

**E.(b)-B1:**

- Import extended with `evict_on_target_event_framework_sport_change`.
- `_get_target_race_row` SELECT extended with `framework_sport`.
- `target_race_save` POST: `new_framework_sport = _parse_str_field(request.form, 'framework_sport')` parsed; threaded into both branches (returning-athlete `update_race_event(...)` + fresh-target `create_race_event(...)`).
- Returning-athlete diff: added `prior_framework_sport = target.get('framework_sport')` + `framework_sport_changed` boolean. Same `if/elif/elif` cascade pattern as race_events route.

### 3.8 `routes/locales.py` — E.(a) filter only

`_terrain_choices` SELECT gained `AND terrain_id IS NOT NULL` + the rationale comment. This was the third surface affected by the same "None"-prepending bug (locale-terrain checkbox grid on `/locales/<slug>/edit`). No B1 framework_sport changes — locale-level edits don't carry a per-locale sport.

### 3.9 `templates/profile/race_event_edit.html` — framework_sport input

New `<div class="col-md-12">` block between `race_url` and `race_rules_summary` with:

```html
<input type="text" class="form-control" id="framework_sport" name="framework_sport"
       placeholder="e.g. Adventure Racing, Trail Running, Triathlon"
       maxlength="100"
       value="{{ race.framework_sport if race and race.framework_sport else '' }}">
<small class="text-muted">
  Leave blank to inherit your profile's primary sport. Set to a different sport when this specific race differs (e.g. a trail runner doing one AR race).
</small>
```

7-line comment explains the free-text precedent (mirrors `templates/profile/edit.html`'s `primary_sport` input) + the deferred Layer-2A-side error surface for unresolved values.

### 3.10 `templates/onboarding/target_race.html` — framework_sport input mirror

Same input shape in a `<div class="col-md-6">` block (onboarding form uses 2-col grid; race_url is the matching col-md-6 sibling).

---

## 4. Code / tests

**Tests:** 1446 → 1458 (+12 net new across 3 extended test files):

- `tests/test_race_events_repo.py` +6 in NEW `TestFrameworkSportOverride` class:
  - `test_load_payload_populates_framework_sport_when_present`
  - `test_load_payload_defaults_framework_sport_to_none`
  - `test_create_passes_framework_sport_kwarg`
  - `test_create_defaults_framework_sport_to_none`
  - `test_update_passes_framework_sport_kwarg`
  - `test_update_can_clear_framework_sport`
- `tests/test_race_events_invalidation.py` +3 in NEW `TestFrameworkSportChange` class:
  - `test_evicts_all_four_entry_points`
  - `test_scoped_to_user`
  - `test_metrics_tagged_with_layer2a`
- `tests/test_layer4_orchestrator.py` +3 in NEW `TestFrameworkSportOverride` class:
  - `test_target_race_override_wins_over_primary_sport`
  - `test_falls_back_to_primary_sport_when_override_unset`
  - `test_override_when_primary_sport_missing_still_classifies`

`_race_row` fixture in `test_race_events_repo.py` extended with `framework_sport: None` default. `_queue_target_race_event` in `test_layer4_orchestrator.py` extended with `framework_sport: str | None = None` kwarg.

Container-runnable subset: 793 → 805 in ~1.8s (+12: 6 repo + 3 invalidation + 3 orchestrator).

Reproducer:

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py \
                    tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py \
                    tests/test_layer4_context.py tests/test_layer4_payload.py \
                    tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                    tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py \
                    tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py \
                    tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py \
                    tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py \
                    tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py \
                    tests/test_routes_race_events.py \
                    tests/test_layer2a.py
# 805 passed, 12 skipped
```

**Python syntax check:** `python3 -m py_compile init_db.py race_events_repo.py race_events_invalidation.py layer4/context.py layer4/orchestrator.py routes/race_events.py routes/onboarding.py routes/locales.py` passes.

**No-regression confirmation:** All previously-passing tests still pass. Pre-existing tests in `tests/test_layer3a_builder.py::TestCacheWrapper` (7) + `tests/test_layer3b_builder.py::TestCacheWrapper` (7) remain pre-existing-circular-import-blocked from collection (separate scope; not touched by this slice).

---

## 5. Manual §5.0 verification steps

For Andy's next manual walkthrough pass against the preview deployment or post-merge against main:

**Step 1 — Terrain dropdown "None" cleanup.** Navigate to `/profile/race-events/<andy_pge_2026_id>/edit`. Click `[+ Add terrain]`. Confirm the new terrain row's dropdown shows entries shaped `TRN-001 — Road / Paved`, `TRN-002 — Groomed Trail`, etc., with NO entry shaped `None — <name>` prepended. Repeat at `/onboarding/target-race` (target-race form's `_race_terrain_editor` partial) and `/locales/home/edit` (locale-terrain checkbox grid).

Verify in Neon: `SELECT COUNT(*) FROM layer0.terrain_types WHERE terrain_id IS NULL AND superseded_at IS NULL` should return 0. If non-zero, re-run `etl/sources/migrate_terrain_types.sql` so the bridge tables (terrain_gap_rules + Layer 2B classifier) have the right rows to match against. (Defensive code-side filter keeps the dropdown clean regardless of migration state, but downstream bridge SELECTs against `terrain_gap_rules` still need the canonical TRN-xxx rows.)

**Step 2 — framework_sport override happy path.** Navigate to `/profile/race-events/<andy_pge_2026_id>/edit`. Confirm the new "Sport (override, optional)" field renders below the Race website URL field with placeholder `e.g. Adventure Racing, Trail Running, Triathlon`. Leave blank, save, confirm row's `framework_sport` column stays NULL (verify: `SELECT framework_sport FROM race_events WHERE id=<andy_pge_id>`). Type `Trail Running`, save, confirm column populated. Reload the edit page + confirm the input pre-populates with the saved value.

Verify cache eviction in Neon: `SELECT entry_point FROM layer4_cache WHERE user_id=<andy> AND superseded_at IS NULL` should return no rows after the framework_sport change (layer2a policy = `_ALL_ENTRY_POINTS + _LAYER3_BOTH` — wider than periodization + brief-only). Repeat the save with NO change and confirm cache NOT evicted (`prior != new` field-change gate).

**Step 3 — orchestrator end-to-end with override.** Run `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026,7,3), cache=Layer4Cache(InMemoryCacheBackend()))` against a target race with `framework_sport='Trail Running'` (override) but `Layer1Identity.primary_sport='Adventure Racing'`. Confirm Layer 2A receives `framework_sport='Trail Running'` (override wins). Then clear the override (`UPDATE race_events SET framework_sport=NULL WHERE id=<andy_pge_id>`); re-invoke; confirm Layer 2A receives `framework_sport='Adventure Racing'` (fallback to profile primary_sport).

Captured as 3 new steps in `CARRY_FORWARD.md` "Manual §5.0 walkthrough" section under D-73 Phase 5.2 Bucket E (a + b B1).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Bucket E.(b)-B2 + E.(c)-C1 paired follow-on slice.** This slice deferred B2 + C1 to keep the file count manageable. The follow-on shape is fully spec'd in `CARRY_FORWARD.md` "Bucket E.(b)-B2 + E.(c)-C1 follow-on slice" entry. Key points:

- **B2 first** so the discipline choices for the per-row terrain `<select>` (C1) can pull from the in-scope discipline set determined by B2's choice (or, when B2 is unset, from the bridge defaults of B1's framework_sport — falling through to athlete primary_sport when both are unset).
- **B2 spec:** `race_events.included_discipline_ids TEXT[] NULL`; `RaceEventPayload.included_discipline_ids: list[str] | None`; `q_layer2a_discipline_classifier_payload` accepts `discipline_id_filter: list[str] | None = None` kwarg (when supplied, replaces bridge-derived defaults); UI = `<select multiple>` keyed on bridge query for the chosen framework_sport.
- **C1 spec:** `RaceTerrainEntry.discipline_id: str | None` (backward-compat — existing rows have `discipline_id=None` meaning "race-wide"); form adds one `<select>` per terrain row in `_race_terrain_editor.html` (choices from B2's discipline list); Layer 2B input shape gains the optional coupling — initially passes through without behavior change; per-discipline gap reasoning is a separate Layer 2B prompt-body update (Trigger #1).
- **Estimated scope:** 6-9 substantive files. Ratify ceiling break at follow-on scope gate.

**If B2 + C1 wait for design conversations**, the architect-recommended alternative is:

1. **Confirm migrate_terrain_types.sql ran on Neon** (`SELECT COUNT(*) FROM layer0.terrain_types WHERE terrain_id IS NULL AND superseded_at IS NULL`) — if non-zero, re-run the migration. Required for E.(a) end-to-end (the defensive filter hides the symptom; the underlying bridge tables still need TRN-xxx-keyed rows to match against in Layer 2B).
2. **Bucket B Bug 3 walkthrough validation** (still pending from predecessor handoff) — confirm `?::text[]` cast fix resolves the persistence bug; if not, escalate per predecessor §6.3 (production diagnostic instrumentation).

### 6.2 Alternative pivots

- **#8 "locales" → "locations" rename** (~9 templates; mechanical; no Triggers) — lowest-risk highest-visibility candidate.
- **#6 + #4 paired injury form refresh** (~6-8 files; Trigger #5 on `BODY_PART_CONSTRAINTS` mapping design).
- **#2b LLM site-parse runtime** (~4-6 files; Trigger #2 on prompt design first).
- **Bucket C terrain vocab cleanup** (~10 sub-items; Triggers #2 + #3 + #5; large design slice).
- **Bucket D legacy hardcoded `home/hotel/partner/airport` wipe** (depends on Bucket C).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket E.(b)-B2 + E.(c)-C1 follow-on slice spec lives here as the next active punch list; Buckets B Bug 3 / C / D continue).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketE_TerrainNone_FrameworkSport_2026_05_23_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Forward-pointer (B2 + C1 follow-on slice):** when the next session opens this work, the `discipline_id_filter` kwarg threading for B2 means the existing `q_layer2a_discipline_classifier_payload` callers (orchestrator + single_session path) need to know whether to pass the filter (target-race override) or `None` (fall through to bridge defaults). Suggested signature in the orchestrator:

```python
discipline_id_filter = (
    target_race_event.included_discipline_ids if target_race_event is not None else None
)
layer2a_payload = q_layer2a_discipline_classifier_payload(
    db,
    framework_sport=framework_sport,
    discipline_id_filter=discipline_id_filter,
    etl_version_set=etl_version_set,
)
```

Similar cache-eviction pattern: when athlete edits `included_discipline_ids` on the target row, fire `evict_on_target_event_framework_sport_change` (or a new `evict_on_target_event_discipline_filter_change` helper if you want layer2a-specific telemetry — the underlying policy is the same).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | E.(a) defensive filter + also confirm migration | Andy at AskUserQuestion gate | Belt-and-suspenders since the dropdown rendering is athlete-facing and the migration state on production Neon is unconfirmed. Defensive filter is harmless when migration has run; decisive when it hasn't. |
| **D2** | E.(b) = B3 (both B1 + B2) — framework_sport override + included_discipline_ids override | Andy at AskUserQuestion gate | Full override surface. B1 alone doesn't help athletes who want to opt out of specific bridge-default disciplines within their framework_sport (e.g., AR athlete whose race has no packrafting); B2 alone doesn't help athletes whose race is a different sport from their profile primary_sport. |
| **D3** | E.(c) = C1 (flat extended) — RaceTerrainEntry.discipline_id field | Andy at AskUserQuestion gate | Smallest contract change; backward-compat (existing rows have discipline_id=None meaning "race-wide"); Layer 2B can opt to read or ignore. C2 (hierarchical) is conceptually cleaner but rougher form UX; C3 (parallel column) introduces redundancy. |
| **D4** | R3 slice scope — ship (a) + B1 now, defer B2 + C1 to paired follow-on slice | Andy at AskUserQuestion gate | Cleanest single-arc shape. (a) + B1 closes the immediately-visible "None"-prepending bug + the simpler framework_sport override in one cohesive slice; B2 + C1 pair naturally because C1's per-row discipline choices pull from B2's chosen-discipline-set. Avoids 14-file ceiling break + lets B2's framework_sport-keyed discipline UI inform C1's per-row picker. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS framework_sport TEXT NULL` present | ✅ `grep -n "framework_sport TEXT NULL" init_db.py` returns 1 hit |
| `race_events_repo.py` `framework_sport` threaded into create + update + load + get | ✅ `grep -c "framework_sport" race_events_repo.py` returns 8+ hits across all 4 functions |
| `race_events_invalidation.py` `evict_on_target_event_framework_sport_change` helper added | ✅ `grep -n "def evict_on_target_event_framework_sport_change" race_events_invalidation.py` returns 1 hit |
| `layer4/context.py` `RaceEventPayload.framework_sport: str \| None` field added | ✅ `grep -n "framework_sport: str \| None" layer4/context.py` returns 1 hit |
| `layer4/orchestrator.py` fallback chain `target_race.framework_sport → primary_sport → error` | ✅ `grep -n "target_race_event.framework_sport" layer4/orchestrator.py` returns 1 hit |
| `routes/race_events.py` defensive `terrain_id IS NOT NULL` filter on `_terrain_choices` | ✅ `grep -n "AND terrain_id IS NOT NULL" routes/race_events.py` returns 1 hit |
| `routes/race_events.py` framework_sport form parsing + eviction wired | ✅ `grep -c "framework_sport" routes/race_events.py` returns 7+ hits across new_race + update_race + import |
| `routes/onboarding.py` defensive `terrain_id IS NOT NULL` filter + framework_sport threading | ✅ `grep -n "AND terrain_id IS NOT NULL" routes/onboarding.py` + `grep -c "framework_sport" routes/onboarding.py` returns ≥7 |
| `routes/locales.py` defensive `terrain_id IS NOT NULL` filter | ✅ `grep -n "AND terrain_id IS NOT NULL" routes/locales.py` returns 1 hit |
| `templates/profile/race_event_edit.html` framework_sport `<input>` added | ✅ `grep -n 'name="framework_sport"' templates/profile/race_event_edit.html` returns 1 hit |
| `templates/onboarding/target_race.html` framework_sport `<input>` mirror added | ✅ `grep -n 'name="framework_sport"' templates/onboarding/target_race.html` returns 1 hit |
| `tests/test_race_events_repo.py` `TestFrameworkSportOverride` class added (6 tests) | ✅ `grep -n "class TestFrameworkSportOverride" tests/test_race_events_repo.py` returns 1 hit |
| `tests/test_race_events_invalidation.py` `TestFrameworkSportChange` class added (3 tests) | ✅ `grep -n "class TestFrameworkSportChange" tests/test_race_events_invalidation.py` returns 1 hit |
| `tests/test_layer4_orchestrator.py` `TestFrameworkSportOverride` class added (3 tests) | ✅ `grep -n "class TestFrameworkSportOverride" tests/test_layer4_orchestrator.py` returns 1 hit |
| All edited Python files pass `python3 -m py_compile` | ✅ `python3 -m py_compile init_db.py race_events_repo.py race_events_invalidation.py layer4/context.py layer4/orchestrator.py routes/race_events.py routes/onboarding.py routes/locales.py` |
| Container-runnable subset 805 passed + 12 skipped | ✅ pytest run |
| Tests 1446 → 1458 (+12 net new) | ✅ pytest count delta |
| `CURRENT_STATE.md` last-shipped pointer flipped to BucketE handoff | ✅ |
| `CARRY_FORWARD.md` Bucket E.(a) + (b)-B1 annotated ✅ Shipped; B2 + C1 follow-on slice spec recorded | ✅ |
| PR opened as draft + CI green (Vercel deploy success) | ⏸ pending push |
| Manual §5.0 verification (steps 1-3) | ⏸ pending Andy's walkthrough |

---

## 9. Files shipped this session

**Substantive (10 files; R3 scope, ratified ceiling break at AskUserQuestion gate):**

1. `init_db.py` — 1 ALTER TABLE migration. +9 / -0.
2. `race_events_repo.py` — `create_race_event` + `update_race_event` + `load_race_event_payload` + `get_race_event` threaded with framework_sport kwarg/column. +8 / -1.
3. `race_events_invalidation.py` — NEW `evict_on_target_event_framework_sport_change` helper. +15 / -0.
4. `layer4/context.py` — `RaceEventPayload.framework_sport` field. +6 / -0.
5. `layer4/orchestrator.py` — fallback chain in `_upstream_full_cone`. +9 / -1.
6. `routes/race_events.py` — `_terrain_choices` filter + framework_sport form parsing + diff + eviction. +24 / -3.
7. `routes/onboarding.py` — same mirror + `_get_target_race_row` SELECT extension. +18 / -3.
8. `routes/locales.py` — `_terrain_choices` filter. +3 / -1.
9. `templates/profile/race_event_edit.html` — framework_sport `<input>`. +16 / -0.
10. `templates/onboarding/target_race.html` — framework_sport `<input>` mirror. +12 / -0.

**Tests (3 files; consolidated into existing test files; not counted against the substantive ceiling):**

- `tests/test_race_events_repo.py` — +6 tests in NEW `TestFrameworkSportOverride` class + `_race_row` default + comment. +91 / 0.
- `tests/test_race_events_invalidation.py` — +3 tests in NEW `TestFrameworkSportChange` class + import. +49 / 0.
- `tests/test_layer4_orchestrator.py` — +3 tests in NEW `TestFrameworkSportOverride` class + `_queue_target_race_event` fixture extension. +124 / 0.

**Bookkeeping (3 files):**

11. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; session narrative appended.
12. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket E.(a) + (b)-B1 annotated ✅ Shipped with cross-reference to the migration verification step; B2 + C1 follow-on slice spec recorded inline.
13. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketE_TerrainNone_FrameworkSport_2026_05_23_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket E.(a) + (b)-B1 shipped 2026-05-23** ✅ — defensive `_terrain_choices` filter + per-race `framework_sport` override.
- **Bucket E.(b)-B2 + E.(c)-C1 follow-on slice** — spec recorded inline; agreed-upon shape pinned (B2 = `included_discipline_ids TEXT[]` with `discipline_id_filter` kwarg in Layer 2A; C1 = `RaceTerrainEntry.discipline_id: str | None` backward-compat); architect-recommended next forward move.
- **Bucket B Bug 3** continues open (pending Andy's manual walkthrough validation against the deployed branch).
- **Buckets C + D + #2b + #4/#6 + #8** continue as the active punch-list cohort.
- 3 new manual §5.0 walkthrough scenarios added (terrain dropdown "None" cleanup / framework_sport override happy path / orchestrator end-to-end with override).
- 1 forward-pointer added: confirm `migrate_terrain_types.sql` ran on production Neon (defensive filter hides the dropdown symptom; downstream Layer 2B bridge tables still need TRN-xxx-keyed rows).

**End of handoff.**
