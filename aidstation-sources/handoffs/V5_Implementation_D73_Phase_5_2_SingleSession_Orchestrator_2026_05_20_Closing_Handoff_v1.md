# D-73 Phase 5.2 Slice 1 — `orchestrate_single_session_synthesize` — Closing Handoff

**Session:** D-73 Phase 5.2 slice 1 — second Layer 4 entry-point orchestrator (`orchestrate_single_session_synthesize`) atop the same-day Phase 5.1 form-refresh trilogy completion. First slice of Phase 5.2 per predecessor handoff §6.1(b) architect-recommended sequence (`single_session_synthesize` → `plan_refresh` → `plan_create`); ratified at plan-mode gate per Trigger #5.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_1_FormRefresh_C_Locale_Loosen_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/form-refresh-locale-phase5-O5XLg` (harness-pinned; branch name reflects the previous form-refresh arc but the session scope is Phase 5.2; not renamed per task instructions "NEVER push to a different branch without explicit permission")
**Status:** 2 substantive files (well under 5-file ceiling); container-runnable subset 468 → 478 (+10 net new `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesize*`); production count 1135 → 1145 (+10); 4 SDK smoke tests still skip cleanly. **Phase 5.2 slice 1 complete; orchestrator now exposes 2 of 4 Layer 4 entry points** (race_week_brief 5.1 + single_session_synthesize 5.2.S1).

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `init_db.py` has new `locale_terrain_ids` migration | `grep -n "locale_terrain_ids TEXT\[\] NOT NULL DEFAULT" init_db.py` | ✅ |
| `routes/locales.py` imports Layer 4 cache hooks | `grep -n "from layer4.cache\|from layer4.cache_invalidation\|from layer4.cache_postgres" routes/locales.py` | ✅ |
| `routes/locales.py` has 5 new helpers | `grep -n "^_TRN_PATTERN\|^def _terrain_choices\|^def _parse_locale_terrain\|^def _hydrate_locale_terrain_ids\|^def _evict_layer2b_on_terrain_change" routes/locales.py` | ✅ 5 hits |
| `routes/locales.py` `_edit_legacy_locale` upserts terrain + invalidates | `grep -n "locale_terrain_ids=excluded.locale_terrain_ids\|sorted(new_terrain_ids) != sorted(prior_terrain_ids)" routes/locales.py` | ✅ |
| `templates/locales/form.html` renders new fieldset | `grep -n "Terrain accessible from this location\|name=\"locale_terrain_ids\"" templates/locales/form.html` | ✅ |
| `layer2b/builder.py` accepts empty + emits flag | `grep -n "may be empty\|if race_terrain:\|race_terrain_unset" layer2b/builder.py` | ✅ |
| `layer4/orchestrator.py` reads `locale_terrain_ids` via helper | `grep -n "def _q_locale_terrain_ids\|locale_terrain_ids=locale_terrain_ids" layer4/orchestrator.py` | ✅ |
| NEW `tests/test_locales.py` has 5 classes / 21 tests | `grep -n "^class Test" tests/test_locales.py` | ✅ 5 classes |
| `tests/test_layer2b.py` has `TestEmptyRaceTerrainLoosen` (4 tests) | `grep -n "class TestEmptyRaceTerrainLoosen" tests/test_layer2b.py` | ✅ |
| `tests/test_layer4_orchestrator.py` has `TestLocaleTerrainIdsWireUp` (4 tests) | `grep -n "class TestLocaleTerrainIdsWireUp" tests/test_layer4_orchestrator.py` | ✅ |
| Container-runnable subset 468 baseline at session start | `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` | ✅ (468 green; baseline verified post my-changes-stashed) |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1.C → ✅ Shipped 2026-05-20 | `grep -n "5.1.C.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` | ✅ |
| `Layer2B_Spec.md` §12 Open Item 2B-2 → ✅ Resolved | `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh C" aidstation-sources/Layer2B_Spec.md` | ✅ |

`./scripts/verify-handoff.sh` flagged 3 ❌ — all pre-explained in the predecessor §1 reconciliation note (forward-pointer placeholders, not actual drift): `aidstation-sources/migrations/migrate_locale_terrain_ids.sql` (routed via `_PG_MIGRATIONS` per D9), `templates/onboarding/_race_terrain_editor.html` (actually at root `templates/_race_terrain_editor.html`), `templates/profile/...locale_edit...html` (placeholder pattern; actual is `templates/locales/form.html`).

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state.

---

## 2. Session narrative

Andy opened the session with the predecessor handoff loaded (FormRefresh C closing). First-session checklist ran per CLAUDE.md; reported current state + Phase 5.1 trilogy closure + 3 verify-handoff `❌`s already explained by the predecessor.

Andy picked **Phase 5.2 — `single_session`** at the AskUserQuestion gate (over Form-refresh D supplements, L3B-P-2 kwarg trim, or the routes/locales.py equipment-edit 2C invalidation gap). Per CLAUDE.md Trigger #5 (architectural alternatives with real tradeoffs), the session entered the plan-mode gate before implementation. The pre-implementation state survey checked:

- `layer4/single_session.py` already exists (Step 4a precedent — driver shipped earlier in the Layer 4 arc, ~1120 LOC).
- `layer4/cached_wrappers.py:llm_layer4_single_session_synthesize_cached` already exists (Step 5 cache layer, line 93).
- `layer4/orchestrator.py:orchestrate_race_week_brief` already shipped (Phase 5.1, 2026-05-20) — the orchestrator-side precedent for entry-point composers.
- `Layer4_Spec.md` §3.3 documents the driver entry-point contract (signature + parameters); no separate orchestrator-side composer spec.

9 D-decisions surfaced + ratified before implementation:

- **D1:** refactor scope — extract shared `_upstream_pipeline` helper now (per predecessor §6.1b architect recommendation) vs defer to 3rd entry point. **Ratified: defer.** Single_session's cone is materially narrower than race_week_brief's (no 2B/2E/3B); a flag-driven shared bundle is premature with 2 consumers having intersecting-but-different needs; Rule of Three lands cleanly with `plan_refresh` (slice 2). Refactoring race_week_brief now would carry regression risk on a tested-and-shipped surface. Module-level `_q_*` helpers (`_q_current_etl_version_set`, `_q_locale_equipment_pool`) stay shared inline.
- **D2:** framework-sport source for Layer 2A — `request.sport` vs `layer1.identity.primary_sport`. **Ratified: `request.sport`.** D-63 athlete-overriding behavior per §6.1 — athlete picks Rowing for cross-training even though primary is AR. Layer 2A's `Layer2AInputError` on unknown framework_sport gets caught + re-raised as `OrchestrationError('request_sport_unavailable', detail=...)`.
- **D3:** `quick_equipment` path — skip Layer 2C entirely vs synthesize transient 2C. **Ratified: skip 2C.** Per spec §3.3 row 4: `layer2c_payload_for_locale=None` when `request.locale_slug is None`; driver handles None.
- **D4:** `suggestion_id` allocation — orchestrator-internal INSERT vs caller-supplied kwarg. **Ratified: kwarg.** `ad_hoc_workout_suggestions` table queued per D-63 §5.3 (not yet shipped); driver signature already requires `suggestion_id: int`; decouples orchestrator from D-63 persistence shape.
- **D5:** pre-flight gates — `request_sport_unavailable` + `locale_unknown` (only when `locale_slug` non-None) + `etl_version_set_undiscoverable`. NO `no_target_event` / `race_week_brief_too_early` (don't apply to ad-hoc). Reuse `_q_current_etl_version_set`. Driver's own `_validate_inputs` covers locale-XOR-quick + 2C-payload-presence.
- **D6:** locale resolution — query `locale_profiles` to validate slug vs trust + pass through. **Ratified: query.** New `_q_locale_by_slug(db, uid, locale) -> bool` helper. Cleaner error contract than empty-pool downstream surface.
- **D7:** `today` / `session_date` plumbing — orchestrator accepts `today: date | None = None` kwarg matching race_week_brief signature.
- **D8:** test coverage — ~10 tests matching race_week_brief precedent across 6 classes (HappyPath / PreflightGates / DiscoveryFailures / Defaults / SportSemantics / ReturnValue).
- **D9:** call cached wrapper at orchestrator level — `llm_layer4_single_session_synthesize_cached` not the raw driver. Matches race_week_brief precedent.

Implementation flow:

1. **Orchestrator** — Added `orchestrate_single_session_synthesize(db, user_id, request, suggestion_id, *, cache, today=None) -> Layer4Payload` to `layer4/orchestrator.py`. Module docstring updated to reflect two-entry-point shape + the Rule-of-Three refactor decision. Algorithm: (a) discover `etl_version_set`; (b) build Layer 1; (c) call 2A with `framework_sport=request.sport` inside try/except for `Layer2AInputError`; (d) compute `included_discipline_ids`; (e) call 2D; (f) locale branch — `_q_locale_by_slug` validation + `_q_locale_equipment_pool` + 2C call when `locale_slug` non-None, else `layer2c_payload_for_locale=None`; (g) build 3A integration bundle + LLM call; (h) call cached wrapper. Reused `_q_current_etl_version_set` + `_q_locale_equipment_pool` from race_week_brief. New `_q_locale_by_slug` helper distinct from `_q_primary_locale` (which hard-codes `'home'` — single_session athletes pick any configured locale). Added `Layer2AInputError` import + `llm_layer4_single_session_synthesize_cached` + `SingleSessionRequest` imports.
2. **Re-export** — `layer4/__init__.py` re-exports `orchestrate_single_session_synthesize` alongside `orchestrate_race_week_brief` + `OrchestrationError`; `__all__` block updated.
3. **Tests** — Added 10 tests across 6 `TestOrchestrateSingleSessionSynthesize*` classes to `tests/test_layer4_orchestrator.py`. New `_single_session_patches()` patch-stack patches 7 import sites (build_layer1_payload + q_layer2a + q_layer2c + q_layer2d + assemble_layer3a_integration_bundle + llm_layer3a_athlete_state + llm_layer4_single_session_synthesize_cached) — narrower than race_week_brief's `_patches()`. New `_fake_single_session_layer4_payload(suggestion_id=99)` helper constructs a valid single-session-mode Layer4Payload (mode invariants: `len(sessions)==1` + `sessions[0].is_ad_hoc==True` + `suggestion_id` non-None). Reused the existing `_FakeConn` + `_fake_layer1_payload` / `_fake_layer2a_payload` / `_fake_layer2c_payload` / `_fake_layer2d_payload` / `_fake_layer3a_payload` factories. Coverage: happy path × 2 (locale + quick_equipment) + preflight gates × 2 (request_sport_unavailable + locale_unknown) + discovery failure × 1 (etl_version_set_undiscoverable) + defaults × 2 (today default + 2D-into-2C threading) + sport semantics × 2 (request.sport overrides primary_sport + quick_equipment path skips locale_by_slug SELECT) + return value pass-through × 1.
4. **Test suite** — Container-runnable subset 468 → 478 passing in ~0.9s (`pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py`). The pre-existing `layer1/layer4` circular-import remains; verified via `git stash` round-trip that the import is unchanged by this slice — `tests/test_layer2a.py` + `tests/test_layer1_builder.py` + `tests/test_layer2b.py` fail identically pre-stash. The +10 new tests count toward the 1145 production total at the spec/regression run.
5. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count (1135 → 1145) + current-focus arc summary; `CARRY_FORWARD.md` new "Phase 5.2 orchestrator follow-ons" section with slice 2 + slice 3 + D-63 caller-side wiring + shared `_upstream_pipeline` extract + 3A/3B caching policy entries; `Upstream_Implementation_Plan_v1.md` §4 new row 5.2.S1; this closing handoff.

No additional `/plan-mode` triggers fired during implementation past the initial gate (no prompt body, no schema, no HITL gate, no padding refusal — D1-D9 were ratified before edits started; D2's `request.sport` semantics fully ratified before the Layer 2A import dependency was added).

---

## 3. File-by-file edits

### 3.1 `layer4/orchestrator.py` (MODIFIED, +~150 LOC)

- Module docstring rewritten from "Phase 5.1 race_week_brief vertical slice" → "Phase 5.1 race_week_brief + Phase 5.2 single_session" with both algorithms summarized + the Rule-of-Three refactor decision documented.
- Imports: added `Layer2AInputError` from `layer2a.builder` (alongside existing `q_layer2a_discipline_classifier_payload`); added `llm_layer4_single_session_synthesize_cached` to the `layer4.cached_wrappers` import block; new `from layer4.single_session import SingleSessionRequest`.
- New public `orchestrate_single_session_synthesize(db, user_id, request, suggestion_id, *, cache, today=None) -> Layer4Payload` — see §2 narrative step 1 for the algorithm.
- New private `_q_locale_by_slug(db, user_id, locale) -> bool` — `SELECT 1 AS hit FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1`; returns `True` when `fetchone()` is non-None. Docstring contrasts with `_q_primary_locale` (which hard-codes `'home'`).
- `__all__` updated to add `"orchestrate_single_session_synthesize"`.

### 3.2 `tests/test_layer4_orchestrator.py` (MODIFIED, +~400 LOC)

- Imports: added `SingleSessionRequest` + `orchestrate_single_session_synthesize` to the `from layer4 import (...)` block; added `from layer2a.builder import Layer2AInputError`; added `PlanSession` + `CardioBlock` + `HRTarget` to the `from layer4.payload import` block (used by the new `_fake_single_session_layer4_payload` helper to construct a valid single-session-mode Layer4Payload).
- New helpers:
  - `_single_session_patches(*, layer4_return)` — 7-patch stack (build_layer1_payload + q_layer2a + q_layer2c + q_layer2d + assemble_layer3a_bundle + llm_layer3a + llm_layer4_single_session_synthesize_cached). Narrower than `_patches()` for race_week_brief — no 2B / 2E / 3B / race_week_brief_cached patches.
  - `_fake_single_session_layer4_payload(suggestion_id=99)` — returns a valid single-session-mode Layer4Payload with one ad-hoc PlanSession (kind=cardio + Z2 main_set + HRTarget) satisfying the `mode == 'single_session_synthesize' ⇒ len(sessions)==1 + is_ad_hoc==True + suggestion_id non-None` invariants.
  - `_request_with_locale()` — `SingleSessionRequest(sport='AR', duration_min=60, intensity='moderate', locale_slug='home')`.
  - `_request_with_quick_equipment()` — `SingleSessionRequest(sport='AR', duration_min=45, intensity='hard', locale_slug=None, quick_equipment=['Dumbbells', 'Bench'])`.
  - `_queue_locale_by_slug_hit(conn)` / `_queue_locale_by_slug_miss(conn)` — queue the new `_q_locale_by_slug` SELECT response.
- 10 new tests across 6 classes:
  - `TestOrchestrateSingleSessionSynthesizeHappyPath` (2): `test_locale_path_threads_payloads_in_dependency_order` (asserts D2: 2A gets `request.sport`; 2C gets `locale_id='home'` + `cluster_locale_ids=['home']` + `included_discipline_ids=['D-trail']`; driver gets dict-shaped layer1_payload + non-None `layer2c_payload_for_locale` + `suggestion_id=99`); `test_quick_equipment_path_skips_layer2c` (asserts D3: 2C `call_count == 0`; driver gets `layer2c_payload_for_locale=None`).
  - `TestOrchestrateSingleSessionSynthesizePreflightGates` (2): `test_request_sport_unavailable_when_layer2a_raises` (asserts D2 + D5: `Layer2AInputError` becomes `OrchestrationError('request_sport_unavailable')`); `test_locale_unknown_when_slug_not_in_locale_profiles` (asserts D5 + D6: missing slug → `OrchestrationError('locale_unknown')` before 2C / 3A / Layer 4 fire).
  - `TestOrchestrateSingleSessionSynthesizeDiscoveryFailures` (1): `test_etl_version_set_undiscoverable` (asserts D5: NULL `MAX(etl_version)` → `OrchestrationError('etl_version_set_undiscoverable')` before any upstream call).
  - `TestOrchestrateSingleSessionSynthesizeDefaults` (2): `test_today_defaults_to_date_today` (asserts D7: `today=None` → orchestrator uses `date.today()`; `session_date` kwarg threads to wrapper); `test_layer2c_kwargs_include_layer2d_payload` (verifies 2D payload threads into 2C call for accommodation modality pass-through per `Layer2C_Spec.md` §5.6).
  - `TestOrchestrateSingleSessionSynthesizeSportSemantics` (2): `test_request_sport_overrides_layer1_primary_sport` (asserts D2: athlete picks Rowing → 2A gets `framework_sport='Rowing'`, NOT the layer1.identity.primary_sport='AR'); `test_quick_equipment_path_no_locale_by_slug_select` (asserts D6: quick_equipment path doesn't fire `_q_locale_by_slug` or `_q_locale_equipment_pool` — only 1 SELECT total: etl_version_set).
  - `TestOrchestrateSingleSessionSynthesizeReturnValue` (1): `test_returns_cached_wrapper_output_verbatim` (asserts D9: orchestrator returns wrapper output `is` sentinel — no wrap/modify/validate at orchestrator level).

### 3.3 `layer4/__init__.py` (MODIFIED, +2 LOC)

- `from layer4.orchestrator import` block extended with `orchestrate_single_session_synthesize`.
- `__all__` entry added (comment line bumped to "Phase 5.1 + Phase 5.2 vertical slices").

(Re-export only; bookkeeping per CLAUDE.md "5-file ceiling = substantive files only" — does NOT count against the ceiling.)

---

## 4. Code / tests

**Test count delta:** 1135 → 1145 in production count (+10 net new tests, all in `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesize*` across 6 classes); 4 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

**Container-runnable subset:** 468 → 478 passing (layer4 + race_events + onboarding + locales) in ~0.9s.

Run reproducer (container-runnable subset):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                                tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py \
                                tests/test_onboarding_race_events.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py
# 478 passed in ~0.9s
```

The +10 new tests:

- `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesizeHappyPath::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesizePreflightGates::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesizeDiscoveryFailures::*` (1)
- `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesizeDefaults::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesizeSportSemantics::*` (2)
- `tests/test_layer4_orchestrator.py::TestOrchestrateSingleSessionSynthesizeReturnValue::*` (1)

Pre-existing `layer1/layer4` circular import remains (per CURRENT_STATE.md historical note + Phase 5.1.B/C handoffs §4); verified by `git stash` round-trip that this slice did NOT introduce or worsen it — `tests/test_layer2a.py` + `tests/test_layer1_builder.py` + `tests/test_layer2b.py` fail identically pre-stash and post-changes with identical error messages.

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.2 slice 1 — single_session orchestrator** — 2-step verification (executable once D-63 caller-side route + `ad_hoc_workout_suggestions` table land):

**Step 1: Locale-path E2E.** From a Python REPL or test harness (no Flask UI yet — D-63 caller-side queued):

```python
from datetime import date
from layer4 import (
    orchestrate_single_session_synthesize,
    Layer4Cache, InMemoryCacheBackend, SingleSessionRequest,
)
result = orchestrate_single_session_synthesize(
    db, andy_user_id,
    SingleSessionRequest(sport="Adventure Racing", duration_min=60,
                         intensity="moderate", locale_slug="home"),
    suggestion_id=1,
    cache=Layer4Cache(InMemoryCacheBackend()),
    today=date(2026, 6, 1),
)
```

Confirm: (a) no `OrchestrationError` raised; (b) `result.mode == 'single_session_synthesize'`; (c) `len(result.sessions) == 1`; (d) `result.sessions[0].is_ad_hoc is True`; (e) `result.suggestion_id == 1`; (f) `result.sessions[0].locale_id == 'home'`; (g) Layer 2C `effective_pool` reflects Andy's Nerstrand home gym inventory.

**Step 2: Quick_equipment-path E2E.** Same harness; `locale_slug=None`, `quick_equipment=['Dumbbells', 'Bench', 'Pull-up bar']`. Confirm: (a) no `OrchestrationError`; (b) `result.sessions[0].locale_id is None` or matches "Somewhere else" sentinel; (c) prescribed exercises only use the 3 quick_equipment items + bodyweight movements (no barbell, no machine); (d) `session_notes` mentions the equipment constraint per system-prompt §466-468.

**Real-LLM cost:** ~$0.02/run when `ANTHROPIC_API_KEY` set; ~$0 with mocked LLM caller.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**(a) Phase 5.2 slice 2 — `plan_refresh` T1/T2/T3 orchestrator.** Wires D-64 plan-refresh tier dispatch. Per `Layer4_Spec.md` §3.2 + the D-64 design, the orchestrator routes `parsed_intent` to one of three Pattern B (T1/T2 + T3 intra-phase) or Pattern A (T3 cross-phase) synthesizers. `ParsedIntent` is already in `layer4/context.py` from Phase 5.1 prep. Pre-flight gates: parsed_intent validation + tier classification + cache-key derivation. The **shared `_upstream_pipeline(db, user_id, today)` helper extract folds naturally here** — slice 2 is the 3rd entry point and `plan_refresh` has the full upstream cone (Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E), so the cone variance across the 3 entry points (race_week_brief = full, single_session = no 2B/2E/3B, plan_refresh = full) becomes visible. Likely shape: a dataclass `UpstreamPayloads` with Optional fields for the layers single_session doesn't need. ~4-6 files (orchestrator additions + shared helper + tests + bookkeeping). **`/plan` gate per Trigger #5** on tier dispatch policy + the shared-helper extract decision.

Files (est. 4-6):

1. `layer4/orchestrator.py` — new `orchestrate_plan_refresh` entry-point + new `_upstream_pipeline` helper (extracts from `orchestrate_race_week_brief` + `orchestrate_single_session_synthesize`); both 5.1 + 5.2.S1 entry points get refactored to consume the new helper.
2. `tests/test_layer4_orchestrator.py` — new `TestOrchestratePlanRefresh*` classes (~10-12 tests across T1/T2/T3 dispatch + happy paths + preflight gates); existing `TestHappyPath` / `TestOrchestrateSingleSessionSynthesizeHappyPath` regression-tested against the refactor.
3. (Possibly) `layer4/__init__.py` — re-export `orchestrate_plan_refresh` + any new helper types.
4. (Possibly) NEW `layer4/_upstream_pipeline.py` — if the shared helper grows enough that inlining in `orchestrator.py` becomes unwieldy. Default = inline; split only if file becomes >500 LOC.

Closes Phase 5.2 row in `Upstream_Implementation_Plan_v1.md` partially (T1/T2/T3 covered; plan_create remains for slice 3).

### 6.2 Alternative pivots

- **Phase 5.2 slice 3 — `plan_create` Pattern A orchestrator** (final orchestrator entry point; ~6-8 files; heaviest; can land after slice 2). Wires per-phase synthesizer + seam reviewer + cross-phase reconciliation. `plan_version_id` allocation moves from hardcoded `1` to real D-64 versioning surface.
- **D-63 caller-side route + `ad_hoc_workout_suggestions` table** — slice 1's orchestrator is structurally complete + tested in isolation but not E2E-reachable from the v1 UI. ~3-4 files: `init_db.py` migration (table per D-63 §5.3) + NEW `routes/ad_hoc_workouts.py` + NEW `templates/workouts/single_session_request.html` + NEW `templates/workouts/single_session_view.html` + tests.
- **Form-refresh D — §I.1 structured supplements** (Layer 2E §5.5 de-stub; ~6-8 files; `/plan` gate per Triggers #1 + #3 + #5 — table vs JSONB schema choice).
- **Layer 3B None-tolerant kwargs L3B-P-2** — with Form-refresh A/B/C closure, all 8 None-tolerant kwargs can flip to populated-from-payload. ~3-4 files.
- **`routes/locales.py` equipment-edit Layer 2C invalidation gap** — surfaced as a doc-sweep nit during Phase 5.1 form-refresh C. Locale-equipment edits don't fire `evict_on_layer_change(cache, uid, 'layer2c')`. ~1-2 files.
- **Manual §5.0 walkthrough** of the accumulated scenarios + Phase 5.1 orchestrator + Phase 5.2 slice 1 end-to-end (once D-63 caller-side ships). Real-LLM ~$0.50/pass.
- **Real-LLM Layer 4 regression** parity to race_week_brief / single_session / plan_refresh / plan_create entry points (~$2/full smoke pass).
- **Plan Management spec authorship** to land 2E-2/3/4 contracts.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (now includes Phase 5.2 orchestrator follow-ons section with slice 2 + slice 3 + D-63 caller-side wiring + shared `_upstream_pipeline` extract + 3A/3B caching policy entries).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_SingleSession_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` (from `aidstation-sources/scripts/`) — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Refactor scope: defer shared `_upstream_pipeline` helper extract until 3rd entry point lands | Andy ratified plan-mode gate | Single_session's cone (Layer 1 → 2A → 2D → 2C → 3A) is materially narrower than race_week_brief's (adds 2B/2E/3B). A flag-driven shared bundle with 2 consumers is premature; Rule of Three lands cleanly with `plan_refresh`. Refactoring race_week_brief now risks regression on a tested surface. Module-level `_q_*` helpers (`_q_current_etl_version_set`, `_q_locale_equipment_pool`) stay shared inline today. |
| **D2** | Framework-sport source for Layer 2A: `request.sport` (not `layer1.identity.primary_sport`) | Andy | D-63 athlete-overriding behavior per §6.1. Athlete picks Rowing for cross-training even though primary is AR. 2A's `Layer2AInputError` on unknown framework_sport gets caught + re-raised as `OrchestrationError('request_sport_unavailable')`. The D-63 frontend constrains the picker to known framework_sports — not Layer 4's concern. |
| **D3** | `quick_equipment` path: skip Layer 2C entirely; pass `layer2c_payload_for_locale=None` | Andy | Per spec §3.3 row 4. Driver handles None; equipment resolves from `request.quick_equipment` directly. |
| **D4** | `suggestion_id` allocation: caller-supplied kwarg (not orchestrator-internal INSERT) | Andy | `ad_hoc_workout_suggestions` table queued per D-63 §5.3 (not yet shipped). Driver signature already requires `suggestion_id: int`. Decouples orchestrator from D-63 persistence shape. Slice 1 is tested in isolation; D-63 caller-side route lands separately. |
| **D5** | Pre-flight gates: 3 codes — `request_sport_unavailable` + `locale_unknown` + `etl_version_set_undiscoverable` | Andy | Minimal set. NO `no_target_event` / `race_week_brief_too_early` (don't apply to ad-hoc — single-session is off-plan, off-race, athlete-driven). Driver's own `_validate_inputs` covers locale-XOR-quick + 2C-payload-presence. |
| **D6** | Locale resolution: query `locale_profiles` to validate slug (new `_q_locale_by_slug` helper) | Andy | Cleaner error contract than trust-and-let-empty-pool-emerge. Mirrors `primary_locale_missing` gate in race_week_brief. Distinct from `_q_primary_locale` which hard-codes `'home'` — single-session athletes pick any configured locale. |
| **D7** | `today` plumbing: `today: date | None = None` kwarg | Andy | Mirrors race_week_brief signature. Defaults to `date.today()`. Tests inject deterministic dates via `today=date(2026, 6, 1)`. Threads through to driver as `session_date`. |
| **D8** | Test coverage: ~10 tests across 6 classes | Andy | Matches race_week_brief test density precedent. 6-class organization keeps test failures isolated to a specific D-decision (e.g., a D2 regression surfaces in `TestSportSemantics` only). |
| **D9** | Orchestrator calls cached wrapper (`llm_layer4_single_session_synthesize_cached`), not the raw driver | Andy | Matches race_week_brief precedent. Per-entry-point cache sits in front of the synthesizer; orchestrator gets cache rebinding (suggestion_id + plan_version_id) for free per §9.4. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/orchestrator.py` has new `orchestrate_single_session_synthesize` function | ✅ `grep -n "^def orchestrate_single_session_synthesize" layer4/orchestrator.py` |
| `layer4/orchestrator.py` has new `_q_locale_by_slug` helper | ✅ `grep -n "^def _q_locale_by_slug" layer4/orchestrator.py` |
| `layer4/orchestrator.py` imports `Layer2AInputError` + `SingleSessionRequest` + `llm_layer4_single_session_synthesize_cached` | ✅ `grep -n "Layer2AInputError\|SingleSessionRequest\|llm_layer4_single_session_synthesize_cached" layer4/orchestrator.py` |
| `layer4/orchestrator.py` catches `Layer2AInputError` + re-raises as `OrchestrationError('request_sport_unavailable')` | ✅ `grep -n "except Layer2AInputError\|request_sport_unavailable" layer4/orchestrator.py` |
| `layer4/orchestrator.py` raises `OrchestrationError('locale_unknown')` when `_q_locale_by_slug` returns False | ✅ `grep -n "locale_unknown" layer4/orchestrator.py` |
| `layer4/orchestrator.py` `__all__` includes `orchestrate_single_session_synthesize` | ✅ `grep -n "\"orchestrate_single_session_synthesize\"" layer4/orchestrator.py` |
| `layer4/__init__.py` re-exports `orchestrate_single_session_synthesize` | ✅ `grep -n "orchestrate_single_session_synthesize" layer4/__init__.py` (returns 2 hits — import + `__all__`) |
| `tests/test_layer4_orchestrator.py` has 6 new `TestOrchestrateSingleSessionSynthesize*` classes | ✅ `grep -c "^class TestOrchestrateSingleSessionSynthesize" tests/test_layer4_orchestrator.py` returns 6 |
| `tests/test_layer4_orchestrator.py` has 10 new tests in single_session test classes | ✅ `grep -c "^    def test_" tests/test_layer4_orchestrator.py` (verified via pytest collected count delta: 17 pre → 27 post for the orchestrator file) |
| `tests/test_layer4_orchestrator.py` imports `SingleSessionRequest` + `orchestrate_single_session_synthesize` + `Layer2AInputError` + `PlanSession` + `CardioBlock` + `HRTarget` | ✅ `grep -n "SingleSessionRequest\|orchestrate_single_session_synthesize\|Layer2AInputError\|PlanSession,\|CardioBlock,\|HRTarget," tests/test_layer4_orchestrator.py` |
| Container-runnable subset green at 478 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py tests/test_locales.py` reports 478 passed |
| `Upstream_Implementation_Plan_v1.md` §4 has new row 5.2.S1 → ✅ Shipped 2026-05-20 | ✅ `grep -n "5.2.S1.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `CURRENT_STATE.md` last-shipped pointer flipped to Phase 5.2 SingleSession handoff | ✅ `grep -n "Phase_5_2_SingleSession_Orchestrator" aidstation-sources/CURRENT_STATE.md` |
| `CURRENT_STATE.md` tests count flipped 1135 → 1145 | ✅ `grep -n "1145 green" aidstation-sources/CURRENT_STATE.md` |
| `CARRY_FORWARD.md` has new "Phase 5.2 orchestrator follow-ons" section | ✅ `grep -n "Phase 5.2 orchestrator follow-ons" aidstation-sources/CARRY_FORWARD.md` |

---

## 9. Files shipped this session

**Substantive (2 files; well under 5-file ceiling):**

1. MODIFIED `layer4/orchestrator.py` (+~150 LOC) — new `orchestrate_single_session_synthesize` entry point + new `_q_locale_by_slug` helper + new imports (`Layer2AInputError`, `SingleSessionRequest`, `llm_layer4_single_session_synthesize_cached`); module docstring rewritten to reflect two-entry-point shape + Rule-of-Three refactor decision; `__all__` extended.
2. MODIFIED `tests/test_layer4_orchestrator.py` (+~400 LOC) — 10 tests across 6 `TestOrchestrateSingleSessionSynthesize*` classes; new `_single_session_patches()` + `_fake_single_session_layer4_payload()` + `_request_with_locale()` + `_request_with_quick_equipment()` + `_queue_locale_by_slug_hit/miss()` helpers; imports extended (`SingleSessionRequest`, `orchestrate_single_session_synthesize`, `Layer2AInputError`, `PlanSession`, `CardioBlock`, `HRTarget`).

**Bookkeeping (4 files):**

3. MODIFIED `layer4/__init__.py` — re-export `orchestrate_single_session_synthesize` + `__all__` entry.
4. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flip + tests count + current-focus arc summary + Layer 4 status row bump.
5. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — new "Phase 5.2 orchestrator follow-ons" section before D-66 Layer 3B caller-side rewire entry.
6. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §4 row 5.2.S1.
7. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_SingleSession_Orchestrator_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- New section "Phase 5.2 orchestrator follow-ons (slice 1 — single_session shipped 2026-05-20)" with slice 2 + slice 3 + D-63 caller-side wiring + shared `_upstream_pipeline` extract + 3A/3B caching policy entries.
- Phase 5.1 form-refresh follow-on "Phase 5.2 first entry point" item is implicitly closed (slice 1 shipped; remaining slices tracked in the new Phase 5.2 section).

Phase 5.2 slice 1 closes the 9 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions.

**Phase 5.2 slice 1 complete; orchestrator now exposes 2 of 4 Layer 4 entry points (race_week_brief 5.1 + single_session_synthesize 5.2.S1). Remaining: `plan_refresh` T1/T2/T3 (slice 2) + `plan_create` (slice 3).**

---

**End of handoff.**
