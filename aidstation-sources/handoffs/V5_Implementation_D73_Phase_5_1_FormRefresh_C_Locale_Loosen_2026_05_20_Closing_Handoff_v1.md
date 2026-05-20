# D-73 Phase 5.1 Form-Refresh C — §J Locale-Terrain Capture + Layer 2B Empty-race_terrain Loosen — Closing Handoff

**Session:** D-73 Phase 5.1 form-refresh C — closes Layer2B_Spec.md §12 Open Item 2B-2 (`§J Locale terrain access` controlled vocabulary on canonical TRN-xxx) + paired loosen on Layer 2B `_validate_inputs` for empty `race_terrain`. Third slice of the §H.2 / §J / §I.1 form-refresh PR per predecessor handoff §6.1 architect-recommended next move; ratified at plan-mode gate per Triggers #1 + #3.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_1_FormRefresh_B_Onboarding_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/form-refresh-aid-station-a79BN`
**Status:** 8 substantive files (ceiling break ratified, precedented by 5.1.A 8 files); container-runnable subset 443 → 468 (+25: +21 NEW `tests/test_locales.py` + 4 NEW `tests/test_layer4_orchestrator.py::TestLocaleTerrainIdsWireUp`); production count 1110 → 1135 (+25 net: the +25 above + 4 new `tests/test_layer2b.py::TestEmptyRaceTerrainLoosen` minus 1 removed `test_empty_race_terrain_raises`); 4 SDK smoke tests still skip cleanly. **Phase 5.1 form-refresh trilogy A + B + C complete; orchestrator has zero remaining Layer 2B input forward-pointers; Layer2B_Spec.md §12 Open Items 2B-2 + 2B-3 both ✅ Resolved.**

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `routes/onboarding.py` imports `json` + `re` | `grep -n "^import json\|^import re" routes/onboarding.py` | ✅ |
| `routes/onboarding.py` has `_TRN_PATTERN` + `_parse_race_terrain` + `_terrain_choices` | `grep -n "^_TRN_PATTERN\|^def _parse_race_terrain\|^def _terrain_choices" routes/onboarding.py` | ✅ |
| `_get_target_race_row` SELECT includes race_terrain + aid_stations + hydration block | `grep -n "race_terrain, aid_stations\|raw_terrain = result.get" routes/onboarding.py` | ✅ |
| `target_race()` GET passes `terrain_choices=terrain_choices` | `grep -n "terrain_choices=terrain_choices" routes/onboarding.py` | ✅ |
| `target_race_save()` threads new fields into both create + update branches | `grep -n "race_terrain=new_race_terrain\|aid_stations=new_aid_stations" routes/onboarding.py` | ✅ |
| `target_race_save()` brief-only diff extended with prior_terrain + prior_aid | `grep -n "prior_terrain != new_race_terrain\|prior_aid != new_aid_stations" routes/onboarding.py` | ✅ |
| NEW `templates/_race_terrain_editor.html` with rows + script | `test -f templates/_race_terrain_editor.html && grep -n "race-terrain-rows\|race-terrain-template" templates/_race_terrain_editor.html` | ✅ |
| `templates/onboarding/target_race.html` uses col-md-4 × 3 + aid_stations + include | `grep -n "col-md-4\|aid_stations\|_race_terrain_editor.html" templates/onboarding/target_race.html` | ✅ |
| `templates/profile/race_event_edit.html` uses include + no inline terrain block | `grep -n "_race_terrain_editor.html" templates/profile/race_event_edit.html` | ✅ |
| `tests/test_onboarding_race_events.py` has `TestParseRaceTerrain` + `TestTerrainChoices` + extended `TestGetTargetRaceRow` | `grep -n "class TestParseRaceTerrain\|class TestTerrainChoices\|class TestGetTargetRaceRow" tests/test_onboarding_race_events.py` | ✅ |
| Container-runnable subset 443 green at session start | `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py` | ✅ (443 passed before this session's changes; verified via working-tree clean at branch checkout) |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1.B Shipped 2026-05-20 | `grep -n "5.1.B.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` | ✅ |
| `Layer2B_Spec.md` §12 Open Item 2B-3 → ✅ Resolved | `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh A + B" aidstation-sources/Layer2B_Spec.md` | ✅ |
| `CARRY_FORWARD.md` Open Item 2B-3 entry → ✅ Resolved + Form-refresh B → ✅ Shipped | `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh A + B\|Form-refresh B.*Shipped 2026-05-20" aidstation-sources/CARRY_FORWARD.md` | ✅ |

`./scripts/verify-handoff.sh` flagged 3 ❌ — all are forward-pointers from the predecessor §6.1 (not actual drift): `aidstation-sources/migrations/migrate_locale_terrain_ids.sql` (this session's NEW-file forward-pointer; routed via `_PG_MIGRATIONS` per D9 instead), `templates/onboarding/_race_terrain_editor.html` (stale path from 5.1.A predecessor — D2 moved it to root `templates/_race_terrain_editor.html` already on disk), `templates/profile/...locale_edit...html` (placeholder pattern; actual locale-edit template is `templates/locales/form.html`).

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state.

---

## 2. Session narrative

Andy picked Form-refresh C + the paired Layer 2B loosen at the AskUserQuestion gate (over Form-refresh C alone, Phase 5.2 first entry point, or Form-refresh D supplements). Plan-mode gate fired per Triggers #1 (user-facing locale-edit form copy) + #3 (cross-layer schema change on `locale_profiles`). 11 D-decisions surfaced + ratified before implementation.

Implementation flow:

1. **Schema migration** — Added `_PG_MIGRATIONS` entry: `ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'`. TEXT[] over JSONB per D1 (flat list of strings, no per-entry metadata; matches `sport_specific_gear_toggles.also_satisfies` + `gated_discipline_ids` pattern on `layer0.*`). Idempotent; existing rows survive with default `'{}'`. No standalone SQL migration file (D9 — same `_PG_MIGRATIONS`-only precedent as 5.1.A).
2. **Routes** — Added 5 new helpers to `routes/locales.py`: `_TRN_PATTERN` + `_terrain_choices(db)` + `_parse_locale_terrain(form)` + `_hydrate_locale_terrain_ids(profile_row)` + `_evict_layer2b_on_terrain_change(db, uid)`. Route-local duplicate-with-cross-ref per D1 mirroring `routes/race_events.py` + `routes/onboarding.py`; the parser shape is simpler than form-refresh A/B's (flat `request.form.getlist('locale_terrain_ids')` vs the repeating `race_terrain[N][field]` pattern) since locale terrain is a multi-checkbox not a row-tuple editor. Threaded into both `_edit_legacy_locale` (GET + POST) + `_edit_shared_locale` (GET + POST per D4 — both edit branches save terrain since terrain is per-athlete + per-locale + geographic-access, not per-shared-gym-inventory; lives directly on `locale_profiles`, not on `gym_profiles`). POST upserts include `locale_terrain_ids=excluded.locale_terrain_ids`; both branches read `prior_terrain_ids` from `_hydrate_locale_terrain_ids(profile)` BEFORE the upsert + fire `_evict_layer2b_on_terrain_change` only when `sorted(new) != sorted(prior)` (D10 — field-change-gated; no-op saves stay silent). The invalidation primitive wraps `evict_on_layer_change(cache, uid, 'layer2b')` (policy = `_NON_SINGLE_SESSION` = plan_create + plan_refresh + race_week_brief; single_session doesn't consume Layer 2B per `layer4/cache_invalidation.py` §9.3 matrix).
3. **Template** — `templates/locales/form.html` gained a new "Terrain accessible from this location" fieldset between the equipment fieldsets and the city/notes inputs. Multi-checkbox grid (`col-12 col-md-6 col-lg-4` per terrain — same 3-col responsive shape as the equipment grid) keyed on canonical TRN-xxx via `terrain_choices`; pre-checked state from `active_terrain_ids` set. D2 picked checkbox-grid over reusing the race-terrain editor partial (pct doesn't apply to locale terrain — just "yes I have access"). Help text per D8: "Select terrain types you can train on from this locale. Include terrain reachable from here even if not on-property (e.g. trail near a hotel, lake near home)" — disambiguates property-vs-reachable; matches CLAUDE.md coaching voice (direct, no hype). D3 scope = terrain editor only (no separate partial for a 16-row checkbox grid; not worth the indirection).
4. **Layer 2B loosen** — `layer2b/builder.py:_validate_inputs` accepts empty `race_terrain` (per-entry + pct_sum checks skip when empty). Non-list / non-RaceTerrainEntry / invalid-TRN / out-of-range-pct / locale-id-shape / disciplines / etl checks still fire on non-empty. `_emit_coaching_flags` signature extended with `race_terrain: list[RaceTerrainEntry]` parameter; new short-circuit branch at the top emits a single `Layer2BCoachingFlag(flag_type='race_terrain_unset', target_terrain_id=None, message=..., metadata={})` and returns immediately when input is empty. Gap-driven flags (§8.1/§8.2/§8.3) cannot fire without race_terrain so this flag is mutually exclusive with them (documented in the new §8.4 spec entry). Call site updated to pass `race_terrain` through.
5. **Orchestrator** — `layer4/orchestrator.py` hoisted `primary_locale = _q_primary_locale(db, user_id)` up to BEFORE the Layer 2B call (was at the 2C boundary); added new `_q_locale_terrain_ids(db, uid, locale)` helper (mirrors `_q_locale_equipment_pool` shape — SELECT against `locale_profiles WHERE user_id, locale LIMIT 1`; returns Python list from psycopg2 native TEXT[] or `[]` for NULL / missing row / SQLite-shim JSON-string path). Flipped `locale_terrain_ids=[]` to `locale_terrain_ids=_q_locale_terrain_ids(db, user_id, primary_locale)` per D5 (v1 home-only — matches existing `_q_locale_equipment_pool` precedent; cluster-union spec §3 deferred). Module docstring forward-pointer block updated to reflect Open Items 2B-2 + 2B-3 closure + the loosen pair landing.
6. **Tests** — Existing `tests/test_layer2b.py::TestInputValidation::test_empty_race_terrain_raises` removed (asserted the now-flipped raise behavior); new `TestEmptyRaceTerrainLoosen` class with 4 tests covers the new contract (empty-race_terrain payload shape + both-empty case + non-list-still-raises + orthogonal-validation-still-fires). NEW `tests/test_locales.py` with 21 tests across 5 classes covering all new helpers + the invalidation primitive (monkeypatched Layer4Cache + PostgresCacheBackend constructors so the test injects an `InMemoryCacheBackend`-backed cache). Extended `tests/test_layer4_orchestrator.py` with `TestLocaleTerrainIdsWireUp` (4 tests) covering the new `_q_locale_terrain_ids` SELECT threading into Layer 2B kwargs + NULL column path + missing row path + SQLite-shim JSON-string path. Existing `TestRaceTerrainAndAidStationsWireUp::test_empty_race_terrain_still_passed_through_unchanged` docstring updated to reference the loosen landing in C (the test itself still passes verbatim — Layer 2B is mocked, so the loosen doesn't change orchestrator-level threading semantics).
7. **Test suite** — Container-runnable subset 443 → 468 passing in 1.00s (`pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py`). The new `tests/test_layer2b.py::TestEmptyRaceTerrainLoosen` 4 tests remain blocked from container collection by the pre-existing `layer1/layer4` circular import (same as the rest of `tests/test_layer2b.py`; verified via `git stash` round-trip that the circular import is not introduced by this slice — `python3 -c "from layer2b import Layer2BInputError"` failed identically before AND after my edits).
8. **Jinja syntax check** — All 4 affected templates compile cleanly via `jinja2.Environment.get_template()` smoke check (`locales/form.html` + `profile/race_event_edit.html` + `onboarding/target_race.html` + `_race_terrain_editor.html`).
9. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count + current-focus arc summary update; `CARRY_FORWARD.md` Open Item 2B-2 full-close annotation + new §5.1.C walkthrough entry + form-refresh C follow-on strikethrough + loosen-for-empty follow-on strikethrough + new doc-sweep nit on the pre-existing `routes/locales.py` equipment-edit Layer 2C invalidation gap; `Upstream_Implementation_Plan_v1.md` new §5.1.C row; `Layer2B_Spec.md` §4 condition 1 loosened with audit-trail pointer + new §8.4 `race_terrain_unset` flag entry + §10 new edge-case row + §12 Open Item 2B-2 flipped from open to ✅ Resolved; this closing handoff.

No additional `/plan-mode` triggers fired during implementation past the initial gate (no prompt body, no new schema beyond the one ratified, no HITL gate, no padding refusal — the form copy was D8-ratified before edits started).

---

## 3. File-by-file edits

### 3.1 `init_db.py` (MODIFIED, +9 LOC)

Added 1 new `_PG_MIGRATIONS` entry with cross-ref comment block:
```sql
ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'
```
Inserted directly after the Form-refresh A `race_events.race_terrain` / `race_events.aid_stations` migrations. Same idempotent-ALTER-pattern + idempotent default-shape preservation. No standalone SQL file (D9).

### 3.2 `routes/locales.py` (MODIFIED, +110 LOC)

- Imports: added `from layer4.cache import Layer4Cache` + `from layer4.cache_invalidation import evict_on_layer_change` + `from layer4.cache_postgres import PostgresCacheBackend`.
- New module constant `_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")` with explicit cross-ref comment block naming `routes/race_events.py` + `routes/onboarding.py` as source + drift-mitigation strategy (3 call sites; tests on all three; ~30 LOC duplication keeps the 8-file ceiling intact).
- New `_terrain_choices(db) -> list[dict]` — request-time SELECT against `layer0.terrain_types WHERE superseded_at IS NULL ORDER BY terrain_id`; returns `{id, label}` dicts. Mirrors `routes/race_events.py:_terrain_choices` + `routes/onboarding.py:_terrain_choices`.
- New `_parse_locale_terrain(form) -> list[str]` — scans `form.getlist('locale_terrain_ids')`; drops empty / malformed (non-TRN-pattern) entries; dedupes; returns sorted list. Simpler than form-refresh A/B's repeating-row parser since locale terrain is a multi-checkbox not a row-tuple.
- New `_hydrate_locale_terrain_ids(profile_row) -> list[str]` — tolerates the column-absent / NULL / native-list / JSON-string-shim shapes (mirrors `race_events_repo.get_race_event` adapter for `race_terrain` JSONB).
- New `_evict_layer2b_on_terrain_change(db, user_id)` — builds a transient `Layer4Cache(PostgresCacheBackend(lambda: db))` (matches `race_events_invalidation._build_default_cache` precedent for the Vercel stateless model) + calls `evict_on_layer_change(cache, user_id, 'layer2b')`.
- `_edit_legacy_locale(db, uid, locale, profile)`: GET render kwargs gained `terrain_choices=_terrain_choices(db)` + `active_terrain_ids=set(prior_terrain_ids)`; POST upsert SQL gained `locale_terrain_ids` column on both `INSERT ... ON CONFLICT (user_id, locale) DO UPDATE SET ... locale_terrain_ids=excluded.locale_terrain_ids ...`; reads `prior_terrain_ids = _hydrate_locale_terrain_ids(profile)` before the upsert + fires the invalidation when `sorted(new_terrain_ids) != sorted(prior_terrain_ids)`.
- `_edit_shared_locale(db, uid, locale, profile)`: identical threading on both the new-gym-profile branch + the inherit branch's UPDATE SQL; same GET render kwarg additions; same field-change-gated invalidation.

### 3.3 `templates/locales/form.html` (MODIFIED, +24 LOC)

Added a new `<fieldset>` block between the equipment-grid `</div>` and the `{% if mode == 'legacy' %}` city/notes section. Conditional on `terrain_choices` (so SQLite dev paths / template-direct-renders without the route hand-off don't render an empty section). Label: "Terrain accessible from this location". Help text per D8 (athletes select terrain reachable from this locale even if not on-property — disambiguates property-vs-reachable). Renders the 16-row TRN-xxx grid via `{% for choice in terrain_choices %}` with `<input type="checkbox" name="locale_terrain_ids" value="{{ choice.id }}" ... {% if choice.id in active_terrain_ids %}checked{% endif %}>`.

### 3.4 `layer2b/builder.py` (MODIFIED, +35 LOC)

- `_validate_inputs`: hoisted the type guard to ensure `race_terrain` is a list (still raises `Layer2BInputError("race_terrain must be a list of RaceTerrainEntry (may be empty)")` on non-list); wrapped the per-entry + pct_sum checks in `if race_terrain:` so the empty-list path skips them. Other preconditions (locale_terrain_ids shape, included_discipline_ids non-empty, etl_version_set keys) still fire. Pre-edit comment block documents the loosen + points at the paired `Layer2B_Spec.md` §4 condition 1 amendment.
- `_emit_coaching_flags`: signature extended with `race_terrain: list[RaceTerrainEntry]` parameter; new short-circuit at the top emits `Layer2BCoachingFlag(flag_type='race_terrain_unset', target_terrain_id=None, message='Race terrain breakdown not captured — terrain gap analysis skipped. Capture race terrain in onboarding §H.2 or the race-event edit form.', metadata={})` and returns when input is empty (D7 message + empty-metadata per D7 rationale).
- Public entry point `q_layer2b_terrain_classifier_payload`: updated the `_emit_coaching_flags(...)` call to pass `race_terrain` through.

### 3.5 `layer4/orchestrator.py` (MODIFIED, +57 LOC)

- Module docstring forward-pointer block updated: race_terrain flows from Form-refresh A/B; `locale_terrain_ids` flows from Form-refresh C via the home-locale row; empty `race_terrain` now accepted by Layer 2B with `race_terrain_unset` flag emission instead of raising; cluster-union spec §3 future work.
- Reordered the pipeline: `primary_locale = _q_primary_locale(db, user_id)` + new `locale_terrain_ids = _q_locale_terrain_ids(db, user_id, primary_locale)` query hoisted above Layer 2B (was after 2D in the original order). Layer 2D now follows Layer 2B; `locale_equipment_pool` query stays at its pre-2C spot. Sequence preserved per dependency rules (Layer 2B needs `locale_terrain_ids` BEFORE its call; Layer 2D / 2C / 3A / 3B / 2E unchanged in order).
- New private helper `_q_locale_terrain_ids(db, user_id, locale) -> list[str]` — SELECT `locale_terrain_ids FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1`; returns `[]` when row missing / column NULL / SQLite-shim JSON-string path; tolerates psycopg2 native TEXT[] (returns Python list directly).

### 3.6 `tests/test_layer2b.py` (MODIFIED, +91 LOC; -10 LOC)

- Removed `TestInputValidation::test_empty_race_terrain_raises` (the now-flipped raise behavior).
- Added new test class `TestEmptyRaceTerrainLoosen` with 4 tests:
  - `test_empty_race_terrain_returns_payload_with_race_terrain_unset_flag` — full payload shape on empty: race_terrain[] + terrain_gaps[] + summary all-zeros + worst_fidelity=1.0 + single race_terrain_unset flag with target_terrain_id=None + empty metadata.
  - `test_empty_race_terrain_with_empty_locale_still_emits_unset_flag` — both-empty case; only one flag fires.
  - `test_non_list_race_terrain_still_raises` — type guard remains (non-list raises with new "must be a list" message).
  - `test_other_validation_still_fires_on_empty_terrain` — included_discipline_ids + etl_version_set validation still fires when terrain is empty.

### 3.7 NEW `tests/test_locales.py` (+296 LOC)

21 tests across 5 classes:
- `TestTrnPattern` (2 tests): canonical match + non-canonical reject (including case-sensitivity).
- `TestParseLocaleTerrain` (8 tests): happy multi-select with sorted output, empty form, empty field, drop-blanks, drop-bad-TRN, dedupe-duplicates, strict sorted ordering across out-of-order input, whitespace strip.
- `TestTerrainChoices` (2 tests): SELECT shape + ORDER BY + dict mapping, empty-rows degenerate.
- `TestHydrateLocaleTerrainIds` (8 tests): None row / column-missing / NULL column / native list pass-through / native list drop-invalid / JSON-string path / empty-array literal `{}` / `[]` / malformed JSON.
- `TestEvictLayer2bOnTerrainChange` (1 test): seeds all 4 entry_points in `InMemoryCacheBackend` for the user; monkeypatches `Layer4Cache` + `PostgresCacheBackend` constructors to inject the seeded cache; invokes `_evict_layer2b_on_terrain_change(db=object(), user_id=42)`; asserts only `single_session_synthesize` remains (layer2b policy = `_NON_SINGLE_SESSION`).

### 3.8 `tests/test_layer4_orchestrator.py` (MODIFIED, +152 LOC)

- Updated `TestRaceTerrainAndAidStationsWireUp::test_empty_race_terrain_still_passed_through_unchanged` docstring to reference the form-refresh C loosen landing (`race_terrain_unset` flag now emitted by Layer 2B instead of raising); the test body still passes verbatim (Layer 2B is mocked at the orchestrator level).
- Added new test class `TestLocaleTerrainIdsWireUp` with 4 tests:
  - `test_locale_terrain_ids_thread_into_layer2b_call` — queues a `_q_locale_terrain_ids` SELECT response with `["TRN-002", "TRN-003", "TRN-016"]` (psycopg2 native TEXT[] path); asserts Layer 2B's kwargs contain the same list.
  - `test_locale_terrain_ids_empty_when_column_null` — NULL column path returns `[]`.
  - `test_locale_terrain_ids_empty_when_row_missing` — defensive against pre-migration / race-condition row absence (`fetchone()` returns None); returns `[]`.
  - `test_locale_terrain_ids_tolerates_json_string_path` — SQLite-shim JSON-string representation hydrates into the Python list shape.

---

## 4. Code / tests

**Test count delta:** 1110 → 1135 in production count (+25 net: +21 in NEW `tests/test_locales.py` + 4 in `tests/test_layer4_orchestrator.py::TestLocaleTerrainIdsWireUp` + 4 in `tests/test_layer2b.py::TestEmptyRaceTerrainLoosen` minus 1 removed `test_empty_race_terrain_raises`); 4 SDK smoke tests still skip cleanly.

**Container-runnable subset:** 443 → 468 passing (layer4 + race_events + onboarding race_events + locales) in 1.00s. The new `tests/test_layer2b.py::TestEmptyRaceTerrainLoosen` 4 tests remain blocked from container collection by the pre-existing `layer1/layer4` circular import (same as the rest of `tests/test_layer2b.py`; verified by `git stash` round-trip — the circular import is unchanged by this slice). They run at the spec-level / production regression run where pydantic + the full env is loaded outside the container constraints.

Run reproducer (container-runnable subset):
```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py
# 468 passed in 1.00s
```

The +25 new tests:
- `tests/test_locales.py::TestTrnPattern::*` (2 tests)
- `tests/test_locales.py::TestParseLocaleTerrain::*` (8 tests)
- `tests/test_locales.py::TestTerrainChoices::*` (2 tests)
- `tests/test_locales.py::TestHydrateLocaleTerrainIds::*` (8 tests)
- `tests/test_locales.py::TestEvictLayer2bOnTerrainChange::test_evicts_layer2b_consumers`
- `tests/test_layer4_orchestrator.py::TestLocaleTerrainIdsWireUp::*` (4 tests)
- `tests/test_layer2b.py::TestEmptyRaceTerrainLoosen::*` (4 tests, container-blocked)

Jinja partials compile-checked via `jinja2.Environment.get_template()` on all 4 affected templates.

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.1 form-refresh C** — 2-step walkthrough on Vercel:

**Step 1: Locale-edit terrain capture.** Navigate to `/locales/home/edit` for Andy's Nerstrand-area home locale. Confirm:
- The new "Terrain accessible from this location" multi-checkbox section renders between the equipment fieldsets and the city/notes inputs.
- All ~16 TRN-xxx terrain options render as a 3-column grid (`col-12 col-md-6 col-lg-4`).
- Check the terrain types reachable from Nerstrand: Road / Paved (TRN-001), Groomed Trail (TRN-002), Technical Trail (TRN-003), Hill / Rolling (TRN-004), Flat Water (TRN-009), Indoor / Gym (TRN-016) (estimate; finalize per Andy's spot-check of the Nerstrand-area).
- Save Profile.
- Confirm `SELECT locale_terrain_ids FROM locale_profiles WHERE user_id=<andy> AND locale='home'` returns the TEXT[] populated with sorted TRN-xxx ids.
- Reload `/locales/home/edit`; confirm checked state pre-populates from the persisted column.
- Confirm Layer 4 brief cache evicted: `SELECT entry_point FROM layer4_cache WHERE user_id=<andy> AND entry_point IN ('plan_create','plan_refresh','race_week_brief') AND superseded_at IS NULL` returns no rows.
- Repeat the same Save with no terrain change; confirm the cache is NOT evicted (`prior != new` field-change gate per D10).

**Step 2: Orchestrator end-to-end loosen verification.** Clear Andy's race_events `race_terrain` JSONB to empty: `UPDATE race_events SET race_terrain='[]'::jsonb WHERE user_id=<andy> AND is_target_event=TRUE` (paste-back a backup row before doing this). Invoke `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026,7,3), cache=Layer4Cache(InMemoryCacheBackend()))`. Confirm:
- No `Layer2BInputError` raised.
- Returns a `Layer4Payload` with `race_week_brief` non-None.
- Layer 2B output includes a single `Layer2BCoachingFlag(flag_type='race_terrain_unset')` with `target_terrain_id=None`.
- `terrain_gaps=[]` + `summary.total_race_terrain_count=0`.
- Restore Andy's race_terrain after the test.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Two equally good options — Andy's pick at session start.**

**(a) Form-refresh D — §I.1 structured supplements.** Closes Layer 2E §5.5 supplement-integration stub. Layer 1 deployed shape today is `Layer1Lifestyle.supplement_protocol_notes: str | None` (free text); Layer 2E spec calls for structured `list[AthleteSupplementRecord]` keyed on `supplement_vocabulary.supplement_id`. **Large slice — ~6-8 files; plan-mode gate required** at session start on the schema choice (table `athlete_supplement_records` vs JSONB column on `athlete_profile`).

Files (est. 6-8):
1. `init_db.py` — schema migration (table vs JSONB per plan-mode pick).
2. NEW or extended `routes/onboarding.py` / `routes/profile.py` — §I.1 capture form (structured per-supplement records: FK to `supplement_vocabulary`, dosage_amount, dosage_unit, timing, purpose).
3. NEW or extended `templates/onboarding/...` / `templates/profile/...` — supplement-records editor surface (likely rows-pattern editor mirroring `_race_terrain_editor.html`).
4. `layer1/builder.py` — extend `Layer1Lifestyle.supplements: list[AthleteSupplementRecord]` (alongside the existing `supplement_protocol_notes` field for backfill).
5. `layer2e/builder.py` — `_emit_supplement_integration_block` de-stub against `supplement_vocabulary`.
6. `tests/test_layer2e.py` — extended `TestSupplementIntegration` class with the de-stub path covered.

Closes Layer 2E §5.5 stub + open items 2E-6 (supplement_vocabulary integration) + arguably 2E-12 (pregnancy status capture pairs here if schema choice allows).

`/plan-mode` gate per Trigger #1 (user-facing form copy) + Trigger #3 (cross-layer schema change) + Trigger #5 (architectural choice on schema shape).

**(b) Phase 5.2 first entry point.** Pick one of `single_session_synthesize` / `plan_refresh` / `plan_create`. Each is structurally similar to Phase 5.1 (compose upstream-builder calls + thread inputs); architect-recommended sequence:
- Start with `single_session_synthesize` (D-63 on-demand workout) — simplest, no Layer 3B / 2B / 2E inputs, narrowest dependency cone.
- Then `plan_refresh` (T1/T2/T3 — D-64 tier dispatch).
- Then `plan_create` Pattern A (the heaviest).

Refactor pass extracts a shared `_upstream_pipeline(db, user_id, today) -> UpstreamPayloads` helper from `orchestrator.py` so the 4 entry points share the Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E composition (each entry point then picks its inputs from the bundle + composes its specific Layer 4 driver call). ~4-6 files per entry point; batchable.

`/plan-mode` gate per Trigger #5 (auto-fire policy decisions per Layer 4 §14.3.4 Step 8 — `race_week_brief` days_to_event ≤ 14 trigger is already wired; `plan_refresh` tier dispatch + `single_session_synthesize` on-demand path are new policy surfaces).

### 6.2 Alternative pivots

- **Layer 3B None-tolerant kwargs L3B-P-2** — with Form-refresh A/B/C closure, all 8 None-tolerant kwargs (`goal_outcome`, `first_time_at_distance`, `previous_attempts`, `race_distance_km`, `race_duration_hr`, `race_terrain`, `race_pack_weight_kg`, `navigation_required`) can flip from None-tolerant to populated-from-payload. ~3-4 files (`layer3b/builder.py` trim + `tests/test_layer3b_builder.py` regression sweep).
- **Manual §5.0 walkthrough** of the accumulated scenarios + new Phase 5.1 orchestrator + form-refresh C end-to-end (real-LLM ~$0.50 pass against Andy's PGE 2026 race row + Andy capturing PGE terrain + Nerstrand locale terrain via the new surfaces). The form-refresh trilogy closure makes this the highest-fidelity end-to-end run possible without Phase 5.2.
- **Real-LLM Layer 4 regression** parity to race_week_brief / single_session / plan_refresh / plan_create entry points (~$2/full smoke pass).
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — surfaced as a doc-sweep nit during this session's investigation. Locale-equipment edits don't fire `evict_on_layer_change(cache, uid, 'layer2c')` today, so equipment changes leave Layer 4 caches stale. ~1-2 files; fold into the next session that touches `routes/locales.py`.
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (now includes Phase 5.1 form-refresh C closure annotations on Open Item 2B-2 + the §5.1.C walkthrough entry + the new doc-sweep nit on `routes/locales.py` equipment-edit Layer 2C invalidation gap).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_FormRefresh_C_Locale_Loosen_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Helper-sharing strategy: route-local duplicate of `_TRN_PATTERN` + `_terrain_choices` + `_parse_locale_terrain` + `_hydrate_locale_terrain_ids` + `_evict_layer2b_on_terrain_change` (with explicit cross-ref comment) | Andy ratified plan-mode gate | Consistency with form-refresh A/B precedent (D1 from B). ~30 LOC duplication across 3 call sites keeps the 8-file ceiling intact and avoids forcing a cross-blueprint imports pattern (antipattern) or extracting to a new module (premature abstraction at 3 sites; the 4th site is the trigger). |
| **D2** | Edit-form widget shape: checkbox grid keyed by terrain_id | Andy | Reuses the equipment-tags grid pattern already in `templates/locales/form.html`. The race-terrain editor partial (rows + pct input) is the wrong shape — pct doesn't apply to locale terrain (just "yes I have access from here"). |
| **D3** | Partial scope: terrain editor only (no extraction) | Andy | At 16 rows of compact checkboxes inlined into `form.html`, extracting a `_locale_terrain_editor.html` partial would add indirection without saving LOC or enabling reuse (the only consumer is this template). Inline keeps the template scope clear. |
| **D4** | Coverage of both edit branches: `_edit_legacy_locale` + `_edit_shared_locale` | Andy | Terrain is per-athlete + per-locale + geographic-access — not commercial-equipment-inventory. Lives in `locale_profiles` directly (the D-60 shared `gym_profiles` table doesn't carry it). Both branches must save it. |
| **D5** | Orchestrator v1 = home-locale only via existing `_q_primary_locale` | Andy | Matches existing `_q_locale_equipment_pool(db, user_id, primary_locale)` precedent. Spec §3 "unioned across cluster" is tracked as a follow-on once a cluster-membership model lands (spec §14 gut-check already flags). |
| **D6** | Layer 2B loosen behavior: accept empty `race_terrain` + emit `race_terrain_unset` flag | Andy | Spec §4 condition 1 amended (paired Layer2B_Spec.md edit); pct_sum + per-entry checks short-circuit when empty; payload returns with `total_race_terrain_count=0`, empty gaps, empty race_terrain output, summary.worst_fidelity=1.0. Plan-gen consumes the new flag as a data-gap warning. |
| **D7** | `race_terrain_unset` flag wording + empty metadata | Andy | Message: "Race terrain breakdown not captured — terrain gap analysis skipped. Capture race terrain in onboarding §H.2 or the race-event edit form." (coaching voice: direct, actionable, no platitudes). Metadata `{}` — no pct_of_race / uncoverable_stimulus / fidelity available without input. |
| **D8** | Locale-edit form copy | Andy | Section heading "Terrain accessible from this location"; help text disambiguates property-vs-reachable ("Select terrain types you can train on from this locale. Include terrain reachable from here even if not on-property (e.g. trail near a hotel, lake near home). Used by the planner to identify race-vs-locale terrain gaps."). Trigger #1 explicit ratification. |
| **D9** | Migration path: `_PG_MIGRATIONS` entry only (no standalone SQL file) | Andy | Form-refresh A precedent. Idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS`; existing rows survive with default `'{}'`. Skips the operational "Andy runs SQL on Neon" step. |
| **D10** | Cache invalidation: `evict_on_layer_change(cache, uid, 'layer2b')` only when `sorted(new) != sorted(prior)` | Andy | Layer 2B is uncached at orchestrator level; brief is cache-load-bearing (`_NON_SINGLE_SESSION` = plan_create + plan_refresh + race_week_brief). Field-change detection mirrors form-refresh A/B precedent. Fires on edits to ANY locale (not just home) for forward-compat with cluster-union; over-eviction cost is one extra cache miss per non-home-locale save. |
| **D11** | Ceiling break: 8 substantive files ratified | Andy | Precedented by form-refresh A's 8 files. Schema + form + parser + validator loosen + orchestrator flip + 2 modified tests + 1 new test file = natural composition. Splitting (e.g., shipping the loosen as its own slice) would leave the empty-terrain case broken at the orchestrator → Layer 2B seam in the interim. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `init_db.py` has the new `locale_terrain_ids` migration | ✅ `grep -n "locale_terrain_ids TEXT\[\] NOT NULL DEFAULT" init_db.py` |
| `routes/locales.py` imports Layer 4 cache hooks | ✅ `grep -n "from layer4.cache\|from layer4.cache_invalidation\|from layer4.cache_postgres" routes/locales.py` |
| `routes/locales.py` has 5 new helpers (`_TRN_PATTERN` + `_terrain_choices` + `_parse_locale_terrain` + `_hydrate_locale_terrain_ids` + `_evict_layer2b_on_terrain_change`) | ✅ `grep -n "^_TRN_PATTERN\|^def _terrain_choices\|^def _parse_locale_terrain\|^def _hydrate_locale_terrain_ids\|^def _evict_layer2b_on_terrain_change" routes/locales.py` (5 hits) |
| `routes/locales.py` `_edit_legacy_locale` upserts `locale_terrain_ids` + fires field-change invalidation | ✅ `grep -n "locale_terrain_ids=excluded.locale_terrain_ids\|sorted(new_terrain_ids) != sorted(prior_terrain_ids)" routes/locales.py` |
| `routes/locales.py` `_edit_shared_locale` upserts `locale_terrain_ids` + fires field-change invalidation on both create + inherit branches | ✅ `grep -cn "_evict_layer2b_on_terrain_change(db, uid)" routes/locales.py` returns 3 (legacy + shared-create + shared-inherit) |
| `routes/locales.py` GET render kwargs threaded `terrain_choices` + `active_terrain_ids` on both branches | ✅ `grep -cn "terrain_choices=_terrain_choices(db)\|active_terrain_ids=set(prior_terrain_ids)" routes/locales.py` returns 4 (legacy GET + shared GET, 2 lines each) |
| `templates/locales/form.html` renders the new terrain fieldset with name='locale_terrain_ids' | ✅ `grep -n "Terrain accessible from this location\|name=\"locale_terrain_ids\"" templates/locales/form.html` |
| `layer2b/builder.py` `_validate_inputs` accepts empty `race_terrain` + still raises on non-list | ✅ `grep -n "may be empty\|if race_terrain:" layer2b/builder.py` |
| `layer2b/builder.py` `_emit_coaching_flags` emits `race_terrain_unset` on empty | ✅ `grep -n "race_terrain_unset" layer2b/builder.py` |
| `layer2b/builder.py` call site threads `race_terrain` into `_emit_coaching_flags` | ✅ `grep -n "_emit_coaching_flags(gaps_by_target, pct_by_target, race_terrain)" layer2b/builder.py` |
| `layer4/orchestrator.py` reads `locale_terrain_ids` via new helper | ✅ `grep -n "def _q_locale_terrain_ids\|locale_terrain_ids=locale_terrain_ids" layer4/orchestrator.py` |
| `layer4/orchestrator.py` docstring forward-pointer block updated for 2B-2 + 2B-3 closure | ✅ `grep -n "Open Item 2B-2 closed\|Form-refresh A/B/C" layer4/orchestrator.py` |
| NEW `tests/test_locales.py` has 5 classes / 21 tests | ✅ `grep -n "^class Test" tests/test_locales.py` returns 5 (`TestTrnPattern` + `TestParseLocaleTerrain` + `TestTerrainChoices` + `TestHydrateLocaleTerrainIds` + `TestEvictLayer2bOnTerrainChange`) |
| `tests/test_layer2b.py` has `TestEmptyRaceTerrainLoosen` (4 tests) + no `test_empty_race_terrain_raises` | ✅ `grep -n "class TestEmptyRaceTerrainLoosen\|test_empty_race_terrain_raises" tests/test_layer2b.py` returns 1 hit on the class + 0 on the removed test |
| `tests/test_layer4_orchestrator.py` has `TestLocaleTerrainIdsWireUp` (4 tests) | ✅ `grep -n "class TestLocaleTerrainIdsWireUp" tests/test_layer4_orchestrator.py` |
| Container-runnable subset green at 468 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` reports 468 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has new row 5.1.C → ✅ Shipped 2026-05-20 | ✅ `grep -n "5.1.C.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `Layer2B_Spec.md` §12 Open Item 2B-2 flipped to ✅ Resolved | ✅ `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh C" aidstation-sources/Layer2B_Spec.md` |
| `Layer2B_Spec.md` §4 condition 1 loosened + §8.4 new flag entry + §10 new edge-case row landed | ✅ `grep -n "race_terrain_unset\|may be empty\|amended 2026-05-20" aidstation-sources/Layer2B_Spec.md` |
| `CARRY_FORWARD.md` §J Open Item 2B-2 + Form-refresh C + Loosen all flipped + new §5.1.C walkthrough entry | ✅ `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh C\|Phase 5.1 form-refresh C.*§J locale-terrain" aidstation-sources/CARRY_FORWARD.md` |

---

## 9. Files shipped this session

**Substantive (8 files; ceiling break ratified):**

1. MODIFIED `init_db.py` (+9 LOC) — 1 ALTER TABLE migration for `locale_profiles.locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'` with cross-ref comment block.
2. MODIFIED `routes/locales.py` (+110 LOC) — 5 new helpers (`_TRN_PATTERN` + `_terrain_choices` + `_parse_locale_terrain` + `_hydrate_locale_terrain_ids` + `_evict_layer2b_on_terrain_change`) + threaded into both edit branches' GET + POST.
3. MODIFIED `templates/locales/form.html` (+24 LOC) — new "Terrain accessible from this location" multi-checkbox fieldset between equipment grid + city/notes.
4. MODIFIED `layer2b/builder.py` (+35 LOC) — `_validate_inputs` loosen + `_emit_coaching_flags` signature extension + `race_terrain_unset` flag emission.
5. MODIFIED `layer4/orchestrator.py` (+57 LOC) — module docstring forward-pointer update + reorder (hoist `_q_primary_locale` + new `_q_locale_terrain_ids` query above Layer 2B) + new `_q_locale_terrain_ids` helper.
6. MODIFIED `tests/test_layer2b.py` (+91 LOC, -10 LOC) — `TestEmptyRaceTerrainLoosen` (4 tests) + removed `test_empty_race_terrain_raises`.
7. NEW `tests/test_locales.py` (+296 LOC) — 21 tests across 5 classes covering `_TRN_PATTERN`, `_parse_locale_terrain`, `_terrain_choices`, `_hydrate_locale_terrain_ids`, `_evict_layer2b_on_terrain_change`.
8. MODIFIED `tests/test_layer4_orchestrator.py` (+152 LOC) — `TestLocaleTerrainIdsWireUp` (4 tests) + existing `test_empty_race_terrain_still_passed_through_unchanged` docstring updated.

**Bookkeeping (5 files):**

9. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + tests count + current-focus arc-summary updates.
10. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Open Item 2B-2 full-close annotation + new §5.1.C walkthrough entry + form-refresh C follow-on strikethrough + loosen-for-empty follow-on strikethrough + new doc-sweep nit on `routes/locales.py` equipment-edit Layer 2C invalidation gap.
11. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §5.1.C row.
12. MODIFIED `aidstation-sources/Layer2B_Spec.md` — §4 condition 1 loosen + §8.4 new flag entry + §10 new edge-case row + §12 Open Item 2B-2 → ✅ Resolved.
13. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_FormRefresh_C_Locale_Loosen_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- §J locale-terrain capture surface — Open Item 2B-2 ✅ **Resolved 2026-05-20** (Phase 5.1 form-refresh C).
- Layer 2B `_validate_inputs` loosen for empty race_terrain ✅ **Resolved 2026-05-20** (folded into Phase 5.1 form-refresh C).
- Form-refresh C follow-on flipped to ✅ Shipped under "Phase 5.1 form-refresh follow-ons" section.
- New §5.1.C walkthrough entry under "Manual §5.0 walkthrough" (locale-terrain capture + orchestrator loosen verification).
- New doc-sweep nit: `routes/locales.py` locale-equipment edits do NOT fire Layer 2C invalidation (pre-existing; predates form-refresh C; fold into next `routes/locales.py` session).

Phase 5.1 form-refresh C closes the 11 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions.

**Phase 5.1 form-refresh trilogy A + B + C complete. Orchestrator has zero remaining Layer 2B input forward-pointers. Layer2B_Spec.md §12 Open Items 2B-2 + 2B-3 both ✅ Resolved.**

---

**End of handoff.**
