# D-73 Phase 5.2 Walkthrough — Best-Fit Modality Resolver Implementation — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Ships the best-fit modality resolver as a working pure-Python module wired into Layer 4's `_upstream_full_cone` + single-session orchestrator. V1 = infra-only at AskUserQuestion gate — keeps the spec's 3 representative disciplines (D-001 / D-006 / D-010) verbatim; vocab population for the 9 deferred AR disciplines (D-005 / D-007 / D-008a / D-008b / D-011 / D-014 / D-015 / D-016 / D-020) lands in per-discipline follow-on slices.

**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitModalitySpec_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/v5-phase-5-2-walkthrough-sDkcv` (harness-pinned this session; generic name covers the slice scope per CLAUDE.md branch-naming rule)
**Status:** 7 substantive files (ceiling break ratified at gate; precedent BucketC_l=12, BucketC_i=12, SkillCaptureSurface=12) + 3 bookkeeping. Reproducer subset 969 → 999 (+30 net new from `test_layer2_modality.py`); whole `tests/` (excluding `test_layer1_builder.py`) 1550 → 1580 + 16 skipped; `test_layer1_builder.py` standalone unchanged at 22; ETL `etl/tests/` unchanged at 139. All 6 edited Python files pass `python3 -m py_compile`.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: `CLAUDE.md` → `CURRENT_STATE.md` (line 9 → predecessor BestFitModalitySpec handoff) → `CARRY_FORWARD.md` (located best-fit modality IMPLEMENTATION forward-pointer at line 112) → predecessor BestFitModalitySpec handoff → `BestFitModality_Spec_v1.md` (load-bearing artifact, 556 lines) → `./aidstation-sources/scripts/verify-handoff.sh`. The anchor sweep returned all 16 ✅ on predecessor §8 with the single long-standing false-positive (`tests/test_extractor_parsers.py` lives under `etl/tests/`, not `tests/`).

| Claim | Anchor | Result |
|---|---|---|
| Predecessor's §8 anchor table all ✅ on disk | `./aidstation-sources/scripts/verify-handoff.sh` | ✅ 16/16 (1 long-standing false-positive carried) |
| Working tree clean on harness branch | `git status` | ✅ |
| `BestFitModality_Spec_v1.md` present on disk | `ls aidstation-sources/BestFitModality_Spec_v1.md` | ✅ 556 lines |
| `layer2_modality/` module NOT yet shipped pre-this-session | `ls layer2_modality/ 2>/dev/null` | ✅ absent (this slice creates) |
| `tests/test_layer2_modality.py` NOT yet shipped pre-this-session | `ls tests/test_layer2_modality.py 2>/dev/null` | ✅ absent (this slice creates) |

**Reconciliation note:** Clean. No drift between predecessor handoff and on-disk state.

Andy picked **Best-fit modality IMPLEMENTATION slice** at the first AskUserQuestion gate over #8 locales→locations rename + bounce-back UX follow-on + Layer 2B per-discipline gap reasoning. Per Trigger #5 (architectural alternatives) + Trigger #2 (vocab padding scrutiny for 9 deferred AR disciplines) plan-mode gate, 3 nested decisions ratified at AskUserQuestion gates:

| # | Gate | Andy's pick | Notes |
|---|---|---|---|
| G1 | Vocab scope | **V1 = Infra-only** | Over V2 AR-relevant subset + V3 full 9-discipline vocab. Keeps the slice tight; vocab population becomes per-discipline narrow follow-on slices (1 AskUserQuestion gate each) instead of 9 nested gates in one session. Honors CLAUDE.md spec-first-sequencing + 5-file ceiling default. |
| G2 | Orchestrator wiring scope | **W2 = Full wire (also single-session)** | Over W1 `_upstream_full_cone` only + W3 no wiring. Threads optional kwarg through single-session driver + cached wrapper. Cache key intentionally NOT extended (driver doesn't consume payload yet; BM-3 prompt-body integration adds the hash component in a 1-line follow-on). |
| G3 | File ceiling | **7-file ceiling break ratified** | Over 5-file tightening that would have cut single-session work (W2 was the chosen wiring scope so the tightening would have contradicted G2). 7 files; well below 12-file precedents (BucketC_l / BucketC_i / SkillCaptureSurface). |

---

## 2. Session narrative

The S1 spec from BestFitModalitySpec was the load-bearing artifact — I read it end-to-end (556 lines, 14 sections at the Layer2C_Spec.md depth standard) before opening any code. The spec specifies 3 representative disciplines verbatim with explicit `_MODALITY_OPTIONS_PER_DISCIPLINE` entries; BM-1 explicitly defers 9 AR disciplines to "the impl slice author should walk each... at an AskUserQuestion gate." Trying to do 9 vocab gates inside one session would have thrashed the session — V1 = infra-only with vocab as per-discipline narrow follow-ons keeps each slice tight + each gate focused.

Three scope gates:

**G1 vocab scope.** I presented V1 (infra + 3 representative disciplines) / V2 (infra + Andy's PGE 2026 AR subset, 3-4 nested vocab gates) / V3 (infra + full 9-discipline vocab, 9 nested gates + firm ceiling break). Recommended V1 because (a) the resolver INFRA is the load-bearing piece — once it lands, vocab additions are mechanical per-discipline edits with 1 AskUserQuestion gate each; (b) the spec's 3 representative disciplines (D-001 + D-006 + D-010) are already exercised end-to-end by Andy's PGE 2026 AR cluster — the runtime is observable from day 1; (c) matches CLAUDE.md "push to production as we go" rule + spec-first sequencing rule "scope specs to what we're about to build, not everything ahead." Andy picked V1.

**G2 orchestrator wiring scope.** I presented W1 (`_upstream_full_cone` only — covers race_week_brief + plan_refresh + plan_create) / W2 (full wire — also single-session) / W3 (no wiring — callable only, runtime impact zero). Recommended W1 because (a) it covers the 3 entry points that share the cone; (b) single-session has divergent wiring per orchestrator docstring; (c) BM-3 is the natural single-session consumer (prompt-body integration) and is explicitly deferred per spec §12. Andy picked W2.

**G3 file ceiling.** I presented (Ratify 7 / Tighten to 5 by cutting W2 / Tighten to 5 by cutting tests). Recommended ratify because (a) W2 was the previously-picked wiring scope so cutting it would have contradicted G2; (b) 7 is well below 12-file precedents; (c) cutting the 6 integration scenarios from spec §13 + the static lint test would have eliminated the only automated regression coverage for the resolver. Andy picked ratify.

The implementation is a near-mechanical translation of the spec. The only architectural deviation worth flagging: the spec §4 condition 5 says discipline_id must match `^D-\d{3}[a-z]?$`. The orchestrator's test fixtures use synthetic discipline IDs like `D-trail` / `D-run` that don't match this shape. Tightening to spec-literal would have cascaded ~37 test fixture updates across `tests/test_layer4_orchestrator.py`. The relaxation is semantically safe: disciplines not in `_MODALITY_OPTIONS_PER_DISCIPLINE` already silently pass through per spec §5.1 (`Disciplines absent from _MODALITY_OPTIONS_PER_DISCIPLINE produce an empty menu without firing a no_modality_recommendation flag`). Strict shape validation gains nothing actionable and would have created fixture-update busywork. Tracked as in-spec D-decision below (DI3).

Equipment-name canonicalisation (BM-5) remains open. The spec's exemplar D-010 vocab references granular climbing gear (`Rope`, `Quickdraws`, `Harness`, `Crash pad`, `Climbing gym membership`) that doesn't exist in canonical 0B `layer0.equipment_items.canonical_name`. The resolver ships the spec literals; the static lint test (§13.6) explicitly limits its scope to terrain (TRN-xxx) + skill-toggle alignment, deferring equipment alignment to the BM-5 canonicalisation slice. This is acknowledged in the spec §10 edge-case table + §14 risks.

---

## 3. File-by-file edits

### 3.1 NEW `layer2_modality/__init__.py`

23 lines. Public re-exports: `ClusterLocaleInput`, `Layer2ModalityInputError`, `ModalityOptionDef`, `resolve_best_fit_modality`. Module docstring cites `BestFitModality_Spec_v1.md` as the design canonical doc + ratifies the placement decision (output schemas live in `layer4.context` alongside `Layer2CPayload`; the resolver + vocab + input dataclass + exception live in `layer2_modality/`).

### 3.2 NEW `layer2_modality/resolver.py`

~470 lines. Pure-Python implementation per spec §3–§8:

- **`Layer2ModalityInputError`** — exception class.
- **`ClusterLocaleInput`** — frozen dataclass; spec §3 input contract.
- **`ModalityOptionDef`** — frozen dataclass; private vocab entry shape.
- **`_MODALITY_OPTIONS_PER_DISCIPLINE`** — module-level dict; 3 disciplines (D-001 / D-006 / D-010) seeded verbatim from spec §5.1.
- **`_validate_inputs`** — spec §4 preconditions; raises `Layer2ModalityInputError`. Discipline_id shape relaxed to "non-empty string" (see DI3 below).
- **`_load_discipline_info`** — single SELECT against `layer0.sport_discipline_bridge` for canonical names; mirrors `layer2c.builder._load_discipline_info` row-handling.
- **`_resolve_menu_for_pair`** — spec §5.2 set-arithmetic. Terrain ANY-of + equipment ALL-of + skill-toggle gate; sorts by `(-preference_score, modality_id)` for determinism.
- **`_emit_coaching_flags`** — spec §8.1 / §8.2 / §8.3 all three triggers. Cluster-wide rollup for §8.1 + §8.2; per-`(discipline, locale, blocking_skill)` triplet for §8.3.
- **`resolve_best_fit_modality`** — public entry point. Returns `Layer2ModalityPayload`.

Disciplines absent from `_MODALITY_OPTIONS_PER_DISCIPLINE` silently produce no recommendation rows (spec §5.1 silent pass-through).

### 3.3 MOD `layer4/context.py`

+52 lines. Added 4 pydantic `_Base` models alongside `Layer2CPayload`:

- `ModalityOption`
- `ModalityRecommendation`
- `ModalityCoachingFlag` — `flag_type` Literal pins the 3 spec §8 triggers.
- `Layer2ModalityPayload`

Header comment cites BestFitModality_Spec_v1.md §7 + the placement decision (Layer-4-consumed payload contracts live in this module; resolver-internal types live in `layer2_modality/`).

### 3.4 MOD `layer4/orchestrator.py`

+54 lines. Three concrete changes:

1. **Imports** — `Layer2ModalityPayload` from `layer4.context`; `ClusterLocaleInput` + `resolve_best_fit_modality` from `layer2_modality`.
2. **`_UpstreamFullCone` dataclass** — added `layer2_modality_payload: Layer2ModalityPayload` field between `layer2e_payload` and `layer3a_payload` with inline comment citing this slice + BM-3 deferral.
3. **`_upstream_full_cone`** — resolver call after Layer 2C (consumes its `effective_pool`). Single-locale cluster today (matches the existing primary-locale-only 2C call); multi-locale ingestion is a future slice. Threads result into the `_UpstreamFullCone` constructor.
4. **`orchestrate_single_session_synthesize`** — mirror wire: resolver fires only when `request.locale_slug is not None` (matches the existing 2C-only-when-locale branch); calls `_q_locale_terrain_ids` for the request locale + passes through to `llm_layer4_single_session_synthesize_cached` via the new `layer2_modality_payload_for_locale` kwarg.

### 3.5 MOD `layer4/cached_wrappers.py`

+8 lines. Optional `layer2_modality_payload_for_locale: Layer2ModalityPayload | None = None` kwarg added to `llm_layer4_single_session_synthesize_cached` after the `cache: Layer4Cache` keyword-only marker. Threaded into the `_synthesize` closure's call to `llm_layer4_single_session_synthesize`. **Cache key intentionally NOT extended this slice** — the driver doesn't consume the payload in the prompt yet (BM-3 deferred); adding the hash now would force unnecessary cache invalidation for a payload that nothing reads. When BM-3 lands, the modality hash plugs into `single_session_synthesize_key` as a 1-line addition.

### 3.6 MOD `layer4/single_session.py`

+14 lines. The driver signature gains an optional `layer2_modality_payload_for_locale: Layer2ModalityPayload | None = None` kwarg after `llm_caller`. Driver receives but doesn't consume — the prompt-body integration is BM-3 follow-on territory per spec §12. Imports extended to include `Layer2ModalityPayload`. Default None preserves all existing call sites in `tests/test_layer4_single_session.py` (~25 sites) without fixture cascading.

### 3.7 NEW `tests/test_layer2_modality.py`

~520 lines, 30 tests. Coverage:

- **TestInputValidation** (6 tests) — spec §4 preconditions: empty cluster_locale_inputs / duplicate locale_ids / empty included_discipline_ids / empty discipline_id / non-bool skill_toggle_states value / missing etl_version_set key.
- **TestScenario13_1_AndyAtHome** (4 tests) — spec §13.1 Andy at home with default-OFF toggles; D-001 trail-run top-pick; D-006 road-ride top-pick; D-010 empty menu + cluster-wide `no_modality_recommendation`.
- **TestScenario13_2_ClimbingGymPlusToggle** (3 tests) — spec §13.2 climbing_gym locale + `climbing_roped=True`; D-010 gym top-pick = `gym_lead_climb`; no cluster-wide flag when gym satisfies; no skill-block flag when toggle ON.
- **TestScenario13_3_DisableRopedToggle** (2 tests) — spec §13.3 toggle OFF; top-pick degrades to `gym_top_rope`; `skill_capability_blocks_specific_modality` fires with correct metadata.
- **TestScenario13_4_EmptyCluster** (1 test) — spec §13.4 degenerate; 3 `no_modality_recommendation` flags fire; no call failure.
- **TestScenario13_5_HotelIndoorOnly** (3 tests) — spec §13.5 hotel locale; D-001 top-pick = `treadmill_run`; `only_generic_modality_available` fires for D-001; D-006 + D-010 fire `no_modality_recommendation`.
- **TestStaticLint** (5 tests) — spec §13.6 alignment: required-field presence + score band + terrain TRN-xxx canonical alignment + skill_toggle canonical alignment + modality_id uniqueness + 3 representative disciplines floor-locked. Equipment alignment (BM-5) intentionally out of scope per spec §10 edge case + §14 risk acknowledgment.
- **TestEdgeCases** (6 tests) — spec §10: discipline absent from dict is silent pass-through (D-013 case); `skill_toggle_states=None` treated as default-OFF; deterministic menu ordering; payload is correctly pydantic-validated; locale_name None falls back to locale_id in rationale; discipline_name falls back to discipline_id when SDB miss.

Each test uses a single-queue `_FakeConn` substrate; the resolver issues exactly one SELECT per call (against `sport_discipline_bridge`). Pre-load of `from layer4 import InMemoryCacheBackend  # noqa: F401` breaks the `layer4.orchestrator → layer2_modality → layer4.context` circular import (mirrors `tests/test_layer2a.py:26` + `tests/test_layer2b.py:26` precedent).

---

## 4. Code / tests results

**Reproducer subset** (whole `tests/` excluding `test_layer1_builder.py`):
- Predecessor: 1550 passed + 16 skipped (per SkillCaptureSurface handoff).
- This slice: 1580 passed + 16 skipped (+30 net new — exactly matches `test_layer2_modality.py` count).
- Zero regressions across any prior surface.

**`test_layer1_builder.py` standalone:** 22 passed (unchanged).

**ETL `etl/tests/`:** 139 passed (unchanged).

**`python3 -m py_compile`:** clean on all 6 edited Python files (`layer2_modality/__init__.py`, `layer2_modality/resolver.py`, `layer4/context.py`, `layer4/orchestrator.py`, `layer4/cached_wrappers.py`, `layer4/single_session.py`).

---

## 5. Manual §5.0 verification steps

NEW Manual §5.0 walkthrough scenario added — first resolver §5.0:

1. **Orchestrator firing path**: Trigger a race-week-brief or plan-refresh for Andy's PGE 2026 cluster. Inspect the `_UpstreamFullCone` return: `layer2_modality_payload.recommendations` should carry one row per `(included_discipline, primary_locale)` pair for every discipline that has entries in `_MODALITY_OPTIONS_PER_DISCIPLINE` (D-001 / D-006 / D-010 today). Disciplines absent from the dict (D-013 + the 9 deferred AR disciplines) produce zero recommendation rows.
2. **Default-OFF nuisance flag check**: With Andy's `athlete_skill_toggles` empty (or all FALSE), the brief's `layer2_modality_payload.coaching_flags` should fire `no_modality_recommendation` for D-010 (no TRN-013 + no TRN-014 + no climbing gym membership at his home locale).
3. **Toggle ON observation**: INSERT `athlete_skill_toggles (user_id, toggle_name, enabled) VALUES (<andy>, 'climbing_roped', TRUE)` + re-orchestrate. The flag set is unchanged because the bottleneck is terrain + equipment, not skill. The resolver behavior IS observable end-to-end via cache eviction (Layer 1 policy from SkillCaptureSurface evicts; resolver re-runs on next plan_refresh).
4. **Single-session firing path**: Drive a single-session request with a real `request.locale_slug`. Verify the orchestrator's resolver call fires (no error) + the cached wrapper receives the optional `layer2_modality_payload_for_locale` kwarg. The driver currently doesn't consume the payload in the prompt body — confirmed by spot-checking the rendered user-prompt string: no modality reference. BM-3 follow-on is the natural consumer.
5. **Static lint observation**: `python3 -m pytest tests/test_layer2_modality.py::TestStaticLint -v` — all 5 lint tests pass. Adding an invalid TRN-xxx or unknown skill toggle to `_MODALITY_OPTIONS_PER_DISCIPLINE` fails the lint at CI time, not runtime (matches spec §13.6 intent).

§5.0 walkthrough scenario count carried at 100 + 1 = **101**.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Best-fit modality vocab population — D-008b Outdoor Paddling slice** as the natural first vocab follow-on. Trigger #2 padding scrutiny gate to ratify the modality option set: `{outdoor_paddle_packraft, outdoor_paddle_kayak, outdoor_paddle_sup, pool_paddle_drill}` with terrain mappings (TRN-008 pool / TRN-009 flat water / TRN-010 ocean / TRN-011 whitewater / TRN-017 moving water) + equipment mappings (Packraft / Kayak / Canoe / SUP) + skill_toggle mappings (whitewater_handling gates TRN-011/TRN-017 options per BucketC_l mapping). ~2 files: `layer2_modality/resolver.py` (extend `_MODALITY_OPTIONS_PER_DISCIPLINE`) + `tests/test_layer2_modality.py` (extend `TestStaticLint` + add D-008b-specific scenario). Same shape applies to the remaining 8 AR disciplines (D-005 / D-007 / D-008a / D-011 / D-014 / D-015 / D-016 / D-020) — one slice per discipline, batchable in pairs if Andy prefers; D-011 carries the BM-4 `also_satisfies` complexity flagged in the spec.

### 6.2 Alternative pivots

- **BM-3 Layer 4 prompt-body integration** — where in plan_create / plan_refresh / race_week_brief prompt bodies do `ModalityRecommendation` payloads land? How does the LLM cite them when synthesising sessions? Pairs naturally with the vocab population follow-ons (modality recommendations get richer as vocab expands). Trigger #1 prompt-design gate required. ~3-5 files (prompt template extensions + payload threading into prompt-body renderers).
- **Phase-aware ranking inside Layer 4 (BM-2)** — Layer 4 needs to encode "Peak bias → specific outdoor over indoor; Taper bias → lower-stimulus options" given the resolver's static menu. Out-of-scope for the resolver; Layer 4 design follow-on. Pairs with BM-3.
- **Multi-locale cluster ingestion** — orchestrator currently feeds primary locale only (`cluster_locale_ids=[primary_locale]`); resolver takes `list[ClusterLocaleInput]` so it handles multi-locale internally. Wire-side aggregation is a separate downstream slice that pairs naturally with Layer 2C's broader cluster expansion already noted.
- **BM-5 equipment-name canonicalisation** — `requires_equipment_all_of` entries in `_MODALITY_OPTIONS_PER_DISCIPLINE` use spec-literal canonical-style names (e.g. `Gravel bike`, `Rope`, `Crash pad`). Round-trip alignment with active 0B `layer0.equipment_items.canonical_name` is open. Static lint test currently scoped to terrain + skill-toggle only. Resolution: extend lint to query canonical equipment vocab OR ratify the equipment name set as the canonical surface (driving an ETL populate). Trigger #2 + #3 likely required.
- **#8 locales→locations rename** — remains the lowest-risk mechanical slice; ~9 templates; no /plan triggers; now also touches the resolver's "locale_id" terminology + SkillCaptureSurface's Step 4 indicator.
- **Bounce-back UX follow-on** — small SkillCaptureSurface D6 follow-on; ~1-2 files. Add `return_to` param to `/locales/new` + `/locales/<slug>/edit` POST handlers.
- **Layer 2B per-discipline gap reasoning** — Trigger #1 prompt-body update consuming Layer 2C's `discipline_id`. ~3-5 files. Carried from BucketE_B2_C1.
- **#6 + #4 injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.
- **Bucket D legacy hardcoded locales** — unblocked since Bucket C fully closed.
- **Manual §5.0 walkthrough** — 99 scenarios pending after this slice's add (100 → 101 then back to 99 if Andy ratifies the new modality walkthrough); the implementation slice doesn't decrease the queue.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (best-fit modality IMPLEMENTATION now ✅ shipped; per-discipline vocab population queued; bounce-back UX still queued; 99 §5.0 scenarios pending).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitModalityImpl_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. **`aidstation-sources/BestFitModality_Spec_v1.md`** — still load-bearing for the vocab-population follow-on slices. §5.1 representative-disciplines section is the pattern; BM-1 names the 9 deferred AR disciplines.
6. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Backward-compat note for next deploy:** all changes are additive at the runtime contract layer. The resolver runs in production on first deploy. Default state for Andy's PGE 2026 (no `athlete_skill_toggles` rows enabled) produces `no_modality_recommendation` for D-010 (no climbing terrain at home); this is the SAME nuisance shape as the existing BucketC_l default-OFF `requires_skill_capability` flags. Single-session driver receives the new kwarg but doesn't consume it in the prompt — no observable behavior change in driver outputs. Cache keys unchanged for all entry points.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **G1** | Vocab scope = V1 infra-only | Andy at first AskUserQuestion gate | Over V2 AR-relevant subset + V3 full 9-discipline vocab. Per-discipline follow-on slices = 1 gate each; tighter review surface. Honors spec-first sequencing + "push to production as we go." |
| **G2** | Wiring scope = W2 full wire (also single-session) | Andy at second AskUserQuestion gate | Over W1 `_upstream_full_cone` only + W3 no wiring. Threads optional kwarg through single-session driver; cache key intentionally NOT extended (BM-3 deferred). |
| **G3** | 7-file ceiling break ratified | Andy at third AskUserQuestion gate | Over Tighten-to-5 cuts (W2 / tests). Well below 12-file precedents (BucketC_l / BucketC_i / SkillCaptureSurface). |
| **DI1** | Output schemas live in `layer4.context`; resolver internals in `layer2_modality/` | Architect at code-time | Mirrors existing convention where `Layer2CPayload` + `Layer2BPayload` etc live in `layer4.context`. Input dataclass `ClusterLocaleInput` + private `ModalityOptionDef` vocab dataclass stay in `layer2_modality/resolver.py` since they're resolver-private. |
| **DI2** | Output schemas use pydantic `_Base` (not frozen dataclass) | Architect at code-time | Spec §7 says "frozen dataclass" but codebase convention is pydantic `_Base` with `extra='forbid'` (matches `Layer2CPayload`). Pydantic validation catches malformed downstream construction at boundary; frozen dataclass would NOT. |
| **DI3** | Discipline_id shape validation relaxed from `^D-\d{3}[a-z]?$` to "non-empty string" | Architect at code-time | Spec §4 condition 5 is strict. Orchestrator test fixtures use synthetic `D-trail` / `D-run` ids that don't match. Tightening to spec-literal cascades ~37 fixture updates with zero behavioral gain — disciplines absent from `_MODALITY_OPTIONS_PER_DISCIPLINE` already silently pass through per spec §5.1. Relaxation is semantically safe. |
| **DI4** | Single-session cache key NOT extended with modality hash | Architect at code-time | Per G2 wiring scope, the kwarg threads through driver + cached wrapper but driver doesn't consume payload in prompt (BM-3 deferred). Adding hash to cache key forces invalidation for a payload nothing reads. BM-3 adds the hash as a 1-line change when prompt-body integration ships. |
| **DI5** | Static lint scoped to terrain + skill-toggle (not equipment) | Architect at code-time | Spec §13.6 says lint should round-trip equipment against canonical 0B. The spec's exemplar D-010 vocab references granular gear (`Rope` / `Quickdraws` / `Harness` / `Crash pad` / `Climbing gym membership`) NOT in canonical 0B — running the lint as-spec'd would fail at CI on the canonical-state vocab. BM-5 is open per spec §10 + §14. Lint test acknowledges scope deferral in module docstring + test class docstring. |
| **DI6** | Resolver issues exactly one DB SELECT per call (discipline-name lookup against SDB) | Architect at code-time | Mirrors `layer2c.builder._load_discipline_info`. Spec §11 budgets ~50-100ms per call incl. the SELECT; cache hit <5ms. Pure-Python set arithmetic for the rest. |
| **DI7** | Resolver wiring inside both `_upstream_full_cone` AND single-session orchestrator (W2 honored at code-time) | Architect at code-time per G2 | Single-session only fires the resolver when `request.locale_slug is not None` (matches the existing 2C-only-when-locale gate). When `locale_slug is None` ("Somewhere else" mode), the payload is None; driver branch is unchanged. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer2_modality/__init__.py` exists | ✅ `ls layer2_modality/__init__.py` |
| `layer2_modality/resolver.py` exists + defines `resolve_best_fit_modality` | ✅ `grep "^def resolve_best_fit_modality" layer2_modality/resolver.py` returns 1 |
| `_MODALITY_OPTIONS_PER_DISCIPLINE` ships D-001 / D-006 / D-010 | ✅ `grep -E "'D-001':\|'D-006':\|'D-010':" layer2_modality/resolver.py` returns 3 |
| `layer4/context.py` defines all 4 modality payload classes | ✅ `grep -nE "^class (Layer2ModalityPayload\|ModalityRecommendation\|ModalityOption\|ModalityCoachingFlag)" layer4/context.py` returns 4 |
| `_UpstreamFullCone` carries `layer2_modality_payload` field | ✅ `grep "layer2_modality_payload: Layer2ModalityPayload" layer4/orchestrator.py` returns 1 |
| `_upstream_full_cone` calls `resolve_best_fit_modality` | ✅ `grep "resolve_best_fit_modality" layer4/orchestrator.py` returns 2 (full-cone + single-session) |
| `orchestrate_single_session_synthesize` threads `layer2_modality_payload_for_locale` | ✅ `grep "layer2_modality_payload_for_locale" layer4/orchestrator.py` returns 2 |
| `llm_layer4_single_session_synthesize_cached` carries optional kwarg | ✅ `grep "layer2_modality_payload_for_locale" layer4/cached_wrappers.py` returns 2 |
| `llm_layer4_single_session_synthesize` driver carries optional kwarg | ✅ `grep "layer2_modality_payload_for_locale" layer4/single_session.py` returns 1 |
| `tests/test_layer2_modality.py` ships 30 tests | ✅ `python3 -m pytest tests/test_layer2_modality.py --collect-only -q 2>&1 \| tail -1` shows "30 tests collected" |
| Reproducer subset 1550 → 1580 + 16 skipped (+30 net) | ✅ `python3 -m pytest tests/ --ignore=tests/test_layer1_builder.py --no-header -q 2>&1 \| tail -1` shows "1580 passed, 16 skipped" |
| `test_layer1_builder.py` standalone unchanged at 22 | ✅ `python3 -m pytest tests/test_layer1_builder.py --no-header -q 2>&1 \| tail -1` shows "22 passed" |
| ETL `etl/tests/` unchanged at 139 | ✅ `python3 -m pytest etl/tests/ --no-header -q 2>&1 \| tail -1` shows "139 passed" |
| All 6 edited Python files compile | ✅ `python3 -m py_compile layer2_modality/__init__.py layer2_modality/resolver.py layer4/context.py layer4/orchestrator.py layer4/cached_wrappers.py layer4/single_session.py` returns 0 |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ `head -10 aidstation-sources/CURRENT_STATE.md` shows BestFitModalityImpl handoff name |
| `CURRENT_STATE.md` exactly 1 "## Last shipped session" header | ✅ `grep -c "^## Last shipped session" aidstation-sources/CURRENT_STATE.md` returns 1 |
| `CURRENT_STATE.md` predecessor demoted to "**Predecessor:**" entry | ✅ `grep -c "^\*\*Predecessor:" aidstation-sources/CURRENT_STATE.md` returns 41 (previous 40 + this slice's demoted BestFitModalitySpec = 41) |
| `CARRY_FORWARD.md` best-fit modality IMPLEMENTATION forward-pointer flipped to ✅ Shipped | ✅ `grep "Implementation slice shipped 2026-05-24.*BestFitModalityImpl" aidstation-sources/CARRY_FORWARD.md` returns 1 |

---

## 9. Files shipped this session

**Substantive (7 files; ceiling break ratified at G3 gate):**

1. NEW `layer2_modality/__init__.py` — public re-exports (23 lines).
2. NEW `layer2_modality/resolver.py` — main module (~470 lines): `ClusterLocaleInput` + `ModalityOptionDef` dataclasses + `_MODALITY_OPTIONS_PER_DISCIPLINE` 3-discipline vocab + `_validate_inputs` + `_load_discipline_info` SQL loader + `_resolve_menu_for_pair` set-arithmetic + `_emit_coaching_flags` 3-trigger emission + public `resolve_best_fit_modality`.
3. MOD `layer4/context.py` — +52 lines, 4 new pydantic `_Base` models (`ModalityOption` + `ModalityRecommendation` + `ModalityCoachingFlag` + `Layer2ModalityPayload`) with header comment citing BestFitModality_Spec_v1.md §7.
4. MOD `layer4/orchestrator.py` — +54 lines: imports + `_UpstreamFullCone.layer2_modality_payload` field + `_upstream_full_cone` resolver call + `orchestrate_single_session_synthesize` resolver call + kwarg threading to cached wrapper.
5. MOD `layer4/cached_wrappers.py` — +8 lines: optional `layer2_modality_payload_for_locale` kwarg added to `llm_layer4_single_session_synthesize_cached`; threaded into `_synthesize` closure. Cache key intentionally unchanged.
6. MOD `layer4/single_session.py` — +14 lines: `Layer2ModalityPayload` import + optional `layer2_modality_payload_for_locale` kwarg on driver signature (default None; not consumed in prompt — BM-3 follow-on plugs in here).
7. NEW `tests/test_layer2_modality.py` — ~520 lines, 30 tests: 6 input-validation + 4 + 3 + 2 + 1 + 3 spec §13.1-13.5 scenarios + 5 spec §13.6 static-lint + 6 spec §10 edge cases.

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

8. MOD `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BestFitModalitySpec line demoted to the first "**Predecessor:**" entry. 1 "## Last shipped session" header; 41 "**Predecessor:**" entries.
9. MOD `aidstation-sources/CARRY_FORWARD.md` — best-fit modality IMPLEMENTATION forward-pointer (from BestFitModalitySpec) flipped from "Implementation slice queued" to ✅ "Implementation slice shipped 2026-05-24 (BestFitModalityImpl)"; NEW per-discipline vocab-population forward-pointers added (9 deferred AR disciplines, 1 slice each, batchable in pairs); §5.0 walkthrough scenario count flipped 100 → 101 (NEW resolver §5.0 added).
10. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitModalityImpl_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Best-fit modality IMPLEMENTATION ✅ Shipped** (BestFitModalityImpl slice). The BucketC_g → BucketC_l → SkillCaptureSurface → BestFitModalitySpec → BestFitModalityImpl chain is now closed at the infra layer. Resolver is live on the cone for race_week_brief + plan_refresh + plan_create + single_session entry points.
- **NEW best-fit modality VOCAB POPULATION follow-on forward-pointers** — 9 deferred AR disciplines (D-005 / D-007 / D-008a / D-008b / D-011 / D-014 / D-015 / D-016 / D-020) each carry a Trigger #2 padding scrutiny gate. ~2 files per discipline (`layer2_modality/resolver.py` extend + `tests/test_layer2_modality.py` extend). Batchable in pairs if Andy prefers. D-011 carries the spec BM-4 `also_satisfies` chain complexity flag — likely needs its own narrow slice.
- **NEW BM-3 Layer 4 prompt-body integration forward-pointer** — where do `ModalityRecommendation` payloads land in plan-gen prompts? Trigger #1 prompt-design gate. ~3-5 files. Pairs with vocab population (richer vocab = better prompt cite material).
- **NEW BM-5 equipment-name canonicalisation forward-pointer** — `requires_equipment_all_of` entries currently use spec-literal names not all in canonical 0B `equipment_items.canonical_name`. Static lint test currently scoped to terrain + skill-toggle only. Resolution: extend lint OR ratify equipment name set as canonical surface. Trigger #2 + #3 likely.
- **NEW multi-locale cluster ingestion forward-pointer** — orchestrator currently feeds primary locale only (`cluster_locale_ids=[primary_locale]`); resolver handles multi-locale internally. Wire-side aggregation is a downstream slice pairing with Layer 2C's broader cluster expansion.
- **Pre-existing forward-pointers carried** — BM-2 phase-aware ranking in Layer 4 (queued); #8 locales→locations rename (lowest-risk mechanical, now also touches resolver locale_id terminology); bounce-back UX (D6 from SkillCaptureSurface, ~1-2 files); Layer 2B per-discipline gap reasoning (Trigger #1, ~3-5 files); #6+#4 injury form refresh; #2b race-URL site-parse; §I.1 structured supplements; Bucket D legacy hardcoded locales.
- **§5.0 walkthrough scenario count 100 → 101** — NEW resolver §5.0 added (5 steps: orchestrator firing path + default-OFF nuisance flag check + toggle ON observation + single-session firing path + static lint observation).

**End of handoff.**
