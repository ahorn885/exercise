# D-73 Phase 5.2 Walkthrough — BM-3 Layer 4 Prompt-Body Integration — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Activates the BestFitModalityImpl slice that shipped earlier today (PR #144). Resolver output (`Layer2ModalityPayload`) was flowing through the cone + cached wrappers but unread by any Layer 4 prompt. This slice wires the payload into all three plan-gen entry-point prompt bodies (single_session + per_phase + race_week_brief) per F2 per-renderer-native rendering, and extends all three matching cache keys with a modality hash component (closes DI4 from the impl slice).

**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BestFitModalityImpl_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/v5-d73-phase-5-2-walkthrough-RSwRg` (harness-pinned this session; generic enough to cover BM-3 scope per CLAUDE.md branch-naming rule)
**Status:** 9 substantive files (7 source + 2 test; ceiling break ratified at G4 gate; precedent BucketC_l=12, BucketC_i=12, SkillCaptureSurface=12, BestFitModalityImpl=7) + 3 bookkeeping. Reproducer subset 1580 → 1601 + 16 skipped (+21 net new: 12 render-helper tests in `test_layer2_modality.py` + 9 cache-key tests in `test_layer4_hashing.py`); `test_layer1_builder.py` standalone unchanged at 22; ETL `etl/tests/` unchanged at 139. All 7 edited Python files pass `python3 -m py_compile`.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: `CLAUDE.md` → `CURRENT_STATE.md` (line 9 → predecessor BestFitModalityImpl handoff) → `CARRY_FORWARD.md` (located BM-3 forward-pointer at line 112) → predecessor BestFitModalityImpl handoff → `BestFitModality_Spec_v1.md` (re-read §7 payload schema + §12 BM-3 forward-pointer) → `./aidstation-sources/scripts/verify-handoff.sh`. The anchor sweep returned all 19 ✅ on predecessor §8 with the single long-standing false-positive (`tests/test_extractor_parsers.py` lives under `etl/tests/`, not `tests/`).

Andy had just merged PR #144 (BestFitModalityImpl) — my local branch was 3 commits behind. Pulled `origin/main` into the harness branch (clean fast-forward; no conflict).

| Claim | Anchor | Result |
|---|---|---|
| Predecessor's §8 anchor table all ✅ on disk | `./aidstation-sources/scripts/verify-handoff.sh` | ✅ 19/19 (1 long-standing false-positive carried) |
| Branch synced with origin/main | `git rev-list --left-right --count HEAD...origin/main` | ✅ 0/0 post-pull |
| `layer2_modality/` module present on disk | `ls layer2_modality/` | ✅ |
| `_render_modality_section_*` helpers NOT yet shipped pre-this-session | `grep -r "_render_modality_section\|_format_modality_recommendations" layer4/ 2>/dev/null` | ✅ 0 hits pre-this-session |
| `layer2_modality_hash` cache key component NOT yet in hashing.py | `grep "layer2_modality_hash\|layer2_modality_locale_hash" layer4/hashing.py` | ✅ 0 hits pre-this-session |

**Reconciliation note:** Clean. No drift between predecessor handoff and on-disk state.

Andy picked **BM-3 Layer 4 prompt-body integration** at the recommendations gate over per-discipline vocab population (BM-1) + BM-5 equipment canonicalisation + smaller mechanical slices. Rationale at recommendation time: without BM-3 the impl slice ships dormant — `Layer2ModalityPayload` flows through the cone but no prompt reads it. Per Trigger #1 (LLM prompt design) + Trigger #5 (architectural alternatives) plan-mode gate, 4 nested decisions ratified at AskUserQuestion gates:

| # | Gate | Andy's pick | Notes |
|---|---|---|---|
| G1 | Wire scope | **A3 = full wire (single_session + per_phase + race_week_brief)** | Over A1 single_session only / A2 + per_phase / A4 no wire. Activates all three entry points that consume the full cone today; plan_refresh tier renderers (T1/T2/T3-intra-phase) explicitly excluded since they consume bundled payloads without 2C and adding modality there would be a divergent contract. Seam_review N/A — it doesn't see locale. |
| G2 (R) | Render shape | **R2 = top-pick + ranked menu + coaching flags + guidance line** | Over R1 top-pick only / R3 flags only. Preserves the spec's menu-not-decision pattern — LLM sees the full option space and applies phase/race context. Guidance line tells the LLM not to cite `modality_id` strings in athlete-facing copy. |
| G2 (F) | Render style | **F2 = per-renderer-native copy** | Over F1 shared render helper. Each renderer gets its own conversion + formatting matching its convention (`#` markdown for single_session; `=== Section ===` for per_phase; `#` + `**bold:**` for race_week_brief). Tradeoff: 3 copies of the prompt copy to maintain; tuning happens 3x. Honored per the spec's intent to keep prompt language native to each surface. |
| G3 | Cache key scope | **C2 = all 3 cache keys (single_session + plan_create + race_week_brief)** | Over C1 single_session only. Safe across BM-1 vocab follow-ons: when `_MODALITY_OPTIONS_PER_DISCIPLINE` changes in a code deploy, PostgresCacheBackend entries for all 3 entry points invalidate cleanly. Closes DI4 from the impl slice + closes the vocab-addition staleness gap before it ships. |
| G4 | File ceiling | **~8-10 file ceiling break ratified** | Over Tighten-to-5 cuts (would have contradicted G1/G2/G3). Final: 9 substantive files. Well below 12-file precedents. |

---

## 2. Session narrative

Three exploration phases:

**(a) Map the integration surface.** I delegated an `Explore` agent to find: prompt-body renderers per entry point + where `Layer2ModalityPayload` flows (orchestrator → cached wrappers → driver) + cache-key construction sites + existing section-header conventions + whether "modality" already appears in any prompt body. Report came back with file:line precision: 6 renderers exist (single_session.py:486, per_phase.py:639, plan_refresh_t1/t2/t3 ×3, race_week_brief.py:809, seam_review.py:270); 3 cache keys in `hashing.py`; payload already flows through cone + single-session driver kwarg per the impl slice but is ignored at `single_session.py:871`. "Modality" already appears in 3 prompts in the *injury-accommodation* context (`AccommodationModality.modality_type`) — different semantic from BM-3, so the new section must use a distinct name to avoid confusion.

**(b) Plan-mode gate.** Presented G1-G4 to Andy. Andy picked A3 + R2 + F2 + C2 + ratify ceiling break. The picks together expand the slice from the spec §6.1 "~3-5 files" estimate to ~9 files because F2 (per-renderer-native copy) + C2 (all 3 cache keys) both add concrete code surface.

**(c) Implementation.** Near-mechanical from the explorer's map + the spec's §7 payload schema. Three render helpers (one per file, F2-per-renderer-native); three cache-key extensions in `hashing.py` (optional `layer2_modality_hash` / `layer2_modality_locale_hash` collapsing None → '' for cache forward-compat with pre-BM-3 entries); three cached-wrapper extensions (single_session re-uses the kwarg the impl slice already plumbed; plan_create + race_week_brief add new `layer2_modality_payload` kwarg + hash computation + thread to driver); driver signatures extended (per_phase + plan_create + race_week_brief add optional kwarg defaulting to None; single_session already had the kwarg from the impl slice — just consumes it now); orchestrator threads `cone.layer2_modality_payload` into the two new cached-wrapper call sites.

One nuance worth flagging: the `layer4.context.Layer3APayload` schema is structured enough that the new `TestRendererSpliceIntoFullPrompts` tests had to bypass pydantic validation via `model_construct` + duck-typed attribute holders for the nested `current_state` / `recent_trajectory` / `data_density` shape. The renderer only reads ~6 specific attributes off Layer3A, so the bypass is semantically safe and avoids a 30-line fixture cascade for tests that only verify the modality splice site (not Layer3A's structure).

Another nuance: the spec's example D-010 vocab references granular climbing gear (`Rope`, `Quickdraws`, `Crash pad`, `Climbing gym membership`) not all in canonical 0B `equipment_items.canonical_name` — this is the open BM-5 from the impl slice and remains open after BM-3. The renderer prints whatever the `ModalityOption.modality_id` is verbatim, so vocab additions (BM-1) and equipment canonicalisation (BM-5) propagate to the prompts without renderer changes.

---

## 3. File-by-file edits

### 3.1 MOD `layer4/hashing.py`

+30 lines net. Three cache-key helpers extended with an optional modality-hash component per G3 (C2):

- `plan_create_key` — new `layer2_modality_hash: str | None = None` kwarg appended after `capped_retries_per_phase`; collapses None → '' inside the components concat so pre-BM-3 callers and default-None callers produce stable keys identical to pre-this-slice behavior.
- `single_session_synthesize_key` — new `layer2_modality_locale_hash: str | None = None` kwarg appended after `capped_retries`; same None → '' collapse.
- `race_week_brief_key` — new `layer2_modality_hash: str | None = None` kwarg appended after `capped_retries`; same None → '' collapse.

Docstrings updated to flag the None → '' forward-compat semantic.

### 3.2 MOD `layer4/cached_wrappers.py`

+~35 lines net. Three cached wrappers extended:

- `llm_layer4_single_session_synthesize_cached` — existing `layer2_modality_payload_for_locale` kwarg (shipped in impl slice for pass-through) now also gets hashed: `compute_payload_hash(layer2_modality_payload_for_locale)` when non-None, threaded into `single_session_synthesize_key(layer2_modality_locale_hash=…)`. Replaced the impl-slice "intentionally NOT extended" comment with a BM-3 activation comment.
- `llm_layer4_plan_create_cached` — NEW `layer2_modality_payload: Layer2ModalityPayload | None = None` kwarg added between `race_event_payload` and `model_synthesizer`; hashed + threaded into `plan_create_key(layer2_modality_hash=…)`; threaded into `_synthesize()` closure's kwargs dict so it flows into `llm_layer4_plan_create`.
- `llm_layer4_race_week_brief_cached` — NEW `layer2_modality_payload: Layer2ModalityPayload | None = None` kwarg added after `cache` keyword-only marker; hashed + threaded into `race_week_brief_key(layer2_modality_hash=…)`; threaded into `_synthesize()` closure's call to `llm_layer4_race_week_brief(…, layer2_modality_payload=layer2_modality_payload)`.

### 3.3 MOD `layer4/orchestrator.py`

+4 lines net. Two call sites updated:

- `orchestrate_race_week_brief` (line ~438) — passes `layer2_modality_payload=cone.layer2_modality_payload` to `llm_layer4_race_week_brief_cached`.
- `orchestrate_plan_create` (line ~746) — passes `layer2_modality_payload=cone.layer2_modality_payload` to `llm_layer4_plan_create_cached`.

`orchestrate_single_session_synthesize` was already wired in the impl slice — no change needed.

### 3.4 MOD `layer4/single_session.py`

+~75 lines. NEW `_render_modality_section_single_session(payload)` helper at module level: `#` / `##` markdown convention with `### D-XXX Discipline Name at Locale` per-recommendation subsection blocks. Renders top-pick line with rationale-hint + alternates as `(score N); (score M)`. Coaching flags rendered in dedicated `## Coaching flags` subsection. Guidance line on `modality_id` citation discipline. Empty payload renders an explanatory placeholder line.

`_render_user_prompt` signature gains `layer2_modality_payload_for_locale: Layer2ModalityPayload | None = None` kwarg; new section splices in after the existing `# Equipment` section / before `# Recent training context`. `llm_layer4_single_session_synthesize` driver threads the existing kwarg into the renderer call; the impl-slice "doesn't consume yet" comment replaced with the BM-3 activation comment.

### 3.5 MOD `layer4/per_phase.py`

+~70 lines. NEW `_format_modality_recommendations_per_phase(payload)` helper at module level: `=== Best-fit modality menu (per discipline, per locale) ===` header + tight one-line-per-recommendation format matching per_phase's compressed convention: `D-001 Trail Running @ home: top=outdoor_trail_run (90); alts=outdoor_road_run (60); rationale=…`. Coaching flags rendered as a separate sub-list after the recommendations. Phase-aware guidance line (Peak / Taper bias hint) — this is the prompt where phase context matters most.

`render_user_prompt` signature gains `layer2_modality_payload: Layer2ModalityPayload | None = None` kwarg; new section splices in after the existing `=== Race + locale + equipment ===` section / before `=== Schedule ===`. `synthesize_phase` signature gains matching kwarg; threaded into the `render_user_prompt` call inside the retry loop.

### 3.6 MOD `layer4/race_week_brief.py`

+~75 lines. NEW `_render_modality_section_race_week_brief(payload)` helper at module level: `# Heading` + `**Purpose:**` / `**Recommendations:**` / `**Modality coaching flags:**` `**bold:**` sub-labels matching the brief's mixed markdown idiom. Per-recommendation one-line entries: `- D-001 ... @ home — top: outdoor_trail_run (rationale: …); alts: outdoor_road_run, treadmill_run`. Section ends with guidance line on natural-name modality citation.

`_render_user_prompt` signature gains `layer2_modality_payload: Layer2ModalityPayload | None = None` kwarg; new section splices in before the existing `# Race-day fueling tier (2E)` section. `llm_layer4_race_week_brief` driver signature gains matching kwarg; threaded into the `_render_user_prompt` call inside the retry loop.

### 3.7 MOD `layer4/plan_create.py`

+5 lines net. Three threading sites:

- `_run_pattern_a_engine` — new `layer2_modality_payload: Layer2ModalityPayload | None = None` kwarg appended.
- Two `synthesize_phase` call sites (line ~489 main loop + line ~794 seam-driven re-synth) — both forward the kwarg.
- `llm_layer4_plan_create` — new kwarg added between `executor` and the implicit `**kwargs`; forwarded to `_run_pattern_a_engine`.

### 3.8 MOD `tests/test_layer4_hashing.py`

+50 lines. Three new test classes worth of additions:

- `test_plan_create_key_modality_hash_none_equals_empty_string` + `test_plan_create_key_modality_hash_set_distinguishes` — assert the None → '' forward-compat collapse + the populated-hash distinguishes from baseline.
- `test_single_session_key_modality_locale_hash_none_equals_empty_string` + `test_single_session_key_modality_locale_hash_set_distinguishes` — same shape for the single-session key.
- `test_race_week_brief_key_modality_hash_none_equals_empty_string` + `test_race_week_brief_key_modality_hash_set_distinguishes` — same shape for the race-week-brief key.
- All three `test_*_key_depends_on_each_component` parametrized tests extended with the new modality-hash slot so mutating the hash flips the key (negative-case coverage).

### 3.9 MOD `tests/test_layer2_modality.py`

+~300 lines. NEW BM-3 render-helper test surface at the bottom of the file (after the existing 30 resolver tests):

- Module-level `_populated_payload()` helper builds a representative `Layer2ModalityPayload` with one `ModalityRecommendation` (D-001 Trail Running at home with `outdoor_trail_run` top pick + `outdoor_road_run` alternate) and one `ModalityCoachingFlag` (`skill_capability_blocks_specific_modality` at D-010 home).
- Module-level `_empty_payload()` helper builds an empty payload for placeholder-render tests.
- `TestSingleSessionRenderer` (3 tests) — header convention + top-pick/alternates render + coaching-flag scope + empty-payload placeholder.
- `TestPerPhaseRenderer` (4 tests) — `=== Section ===` convention + compressed one-line format + flag rendering + empty-payload placeholder + phase-aware guidance line presence.
- `TestRaceWeekBriefRenderer` (3 tests) — `#` heading + `**bold:**` convention + coaching-flag scope + empty-payload placeholder.
- `TestRendererSpliceIntoFullPrompts` (2 tests) — calls the actual `_render_user_prompt` on `single_session.py` with + without a modality payload to verify the splice site renders the section when supplied and omits it when None. Uses `model_construct` + duck-typed attribute holders for Layer3APayload's nested structure (the renderer only reads ~6 attributes; full fixture would have been ~30 lines of pydantic boilerplate for no semantic gain).

12 new tests total (3 + 4 + 3 + 2).

---

## 4. Code / tests results

**Reproducer subset** (whole `tests/` excluding `test_layer1_builder.py`):
- Predecessor: 1580 passed + 16 skipped.
- This slice: 1601 passed + 16 skipped (+21 net new: 12 render tests + 9 hashing tests).
- Zero regressions across any prior surface (302 entry-point tests across single_session / race_week_brief / plan_create / plan_refresh / orchestrator all green).

**`test_layer1_builder.py` standalone:** 22 passed (unchanged).

**ETL `etl/tests/`:** 139 passed (unchanged).

**`python3 -m py_compile`:** clean on all 7 edited Python files (`layer4/hashing.py`, `layer4/cached_wrappers.py`, `layer4/orchestrator.py`, `layer4/single_session.py`, `layer4/per_phase.py`, `layer4/race_week_brief.py`, `layer4/plan_create.py`).

---

## 5. Manual §5.0 verification steps

NEW Manual §5.0 walkthrough scenario added — first BM-3 prompt-body §5.0:

1. **Single-session prompt body includes modality section**: Drive a single-session generate via `/workouts/build` (cardio or strength) with a real `request.locale_slug`. After the LLM responds, capture the rendered user prompt (debugger or log) and confirm the `# Best-fit modality recommendations` section is present with per-(discipline, locale) `### D-XXX … at …` subsection blocks listing top-pick + alternates + rationale. For Andy's home locale with default-OFF skill toggles, the D-010 section should show "no satisfying modality" since TRN-013 + TRN-014 are absent.
2. **Per-phase prompt body includes modality section**: Drive a plan-create from `/plans/v2/new` for Andy's PGE 2026 context with `plan_start_date=2026-04-01`. The orchestrator fires Pattern A; capture the rendered user prompt for ANY phase (e.g. Base phase 0) and confirm the `=== Best-fit modality menu (per discipline, per locale) ===` section is present after the `=== Race + locale + equipment ===` section with the compressed one-line format. Phase-aware guidance line (`Peak biases outdoor + sport-specific; Taper biases lower-stimulus options`) should be visible.
3. **Race-week brief prompt body includes modality section**: Once Andy's PGE 2026 is inside the auto-fire window (or via test fixture flipping `event_date`), run `orchestrate_race_week_brief` and capture the rendered prompt. Confirm the `# Best-fit modality (Layer 2 modality resolver)` section is present before `# Race-day fueling tier (2E)` with `**Purpose:**` / `**Recommendations:**` / `**Modality coaching flags:**` bold sub-labels.
4. **Cache key extension fires invalidation on modality change**: With a cached single-session for Andy at home, manually flip `_MODALITY_OPTIONS_PER_DISCIPLINE['D-001']` to add a new option (simulate a vocab follow-on), restart, re-invoke the same `/workouts/build` request. Confirm the cache MISSES (the new modality_hash slot flips the key); the LLM re-runs; the new option appears in the prompt cite material. Revert the dict change after the test.
5. **Backward-compat: pre-BM-3 cache entries with `layer2_modality_hash=None` collapse to '' inside the key helper**: Verify by inspection that `single_session_synthesize_key(..., layer2_modality_locale_hash=None)` == `single_session_synthesize_key(...)` (default-None) == `single_session_synthesize_key(..., layer2_modality_locale_hash='')` — covered by 6 unit tests in `test_layer4_hashing.py` (the `*_modality_hash_none_equals_empty_string` family).

§5.0 walkthrough scenario count carried at 101 + 1 = **102**.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Per-discipline VOCAB POPULATION — D-008b Outdoor Paddling slice** as the natural first vocab follow-on. Spec §12 BM-1 explicitly defers this; with BM-3 shipped, vocab additions now have observable effect in all 3 plan-gen prompts (and the cache invalidates cleanly on the dict shape change per G3). Trigger #2 padding scrutiny gate to ratify the modality option set: `{outdoor_paddle_packraft, outdoor_paddle_kayak, outdoor_paddle_sup, pool_paddle_drill}` with terrain mappings (TRN-008 pool / TRN-009 flat water / TRN-010 ocean / TRN-011 whitewater / TRN-017 moving water) + equipment mappings (Packraft / Kayak / Canoe / SUP) + skill_toggle mappings (whitewater_handling gates TRN-011/TRN-017 options per BucketC_l mapping). ~2 files: `layer2_modality/resolver.py` (extend `_MODALITY_OPTIONS_PER_DISCIPLINE`) + `tests/test_layer2_modality.py` (extend `TestStaticLint` + add D-008b scenario). Same shape applies to the remaining 8 AR disciplines.

### 6.2 Alternative pivots

- **Phase-aware ranking inside Layer 4 (BM-2)** — now that per_phase prompts cite the modality menu with a phase-aware guidance line, the next refinement is for the LLM to actually encode "Peak bias → specific outdoor over indoor; Taper bias → lower-stimulus options" as structured prompt copy. Pairs naturally with vocab population. Trigger #1 prompt-design gate.
- **BM-5 equipment-name canonicalisation** — `requires_equipment_all_of` entries in `_MODALITY_OPTIONS_PER_DISCIPLINE` use spec-literal canonical-style names (`Gravel bike`, `Rope`, `Crash pad`, `Climbing gym membership`). The renderer prints them verbatim; the LLM may cite athlete-facing copy that references gear names that don't match the canonical 0B vocab. Static lint test currently scoped to terrain + skill-toggle only. Resolution: extend lint to query canonical equipment vocab OR ratify the resolver's equipment name set as the canonical surface (driving an ETL populate). Trigger #2 + #3 likely.
- **Multi-locale cluster ingestion** — orchestrator currently feeds primary locale only (`cluster_locale_ids=[primary_locale]`); resolver takes `list[ClusterLocaleInput]` so it handles multi-locale internally. Wire-side aggregation is a separate downstream slice pairing with Layer 2C's broader cluster expansion.
- **plan_refresh tier renderers (T1/T2/T3-intra-phase) modality wire** — explicitly excluded from BM-3 because those renderers consume bundled payloads without 2C. If/when Andy wants modality cite material in mid-plan refresh prompts, this is a separate slice that would either (a) extend the `Layer2Bundle` shape to carry a modality entry or (b) re-derive the resolver on refresh inputs.
- **#8 locales→locations rename** — remains the lowest-risk mechanical slice; ~9 templates; now also touches the resolver's `locale_id` terminology + the 3 NEW renderer copies + their tests (all use "at locale" / "@ locale" phrasing that the rename would unify).
- **Bounce-back UX from `/locales/new`** — small SkillCaptureSurface D6 follow-on; ~1-2 files.
- **Layer 2B per-discipline gap reasoning** — Trigger #1 prompt-body update consuming Layer 2C's `discipline_id`. ~3-5 files. Carried from BucketE_B2_C1.
- **#6 + #4 injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.
- **Bucket D legacy hardcoded locales** — unblocked since Bucket C fully closed.
- **Manual §5.0 walkthrough** — 101 → 102 after this slice's add; queue still pending.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (BM-3 prompt-body integration now ✅ shipped; per-discipline vocab population still queued; BM-5 equipment canonicalisation still queued; 102 §5.0 scenarios pending after this slice's add).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BM3_PromptBodyIntegration_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `aidstation-sources/BestFitModality_Spec_v1.md` — load-bearing for vocab-population follow-on slices. §5.1 representative-disciplines section is the pattern; BM-1 names the 9 deferred AR disciplines.
6. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Backward-compat note for next deploy:** all changes are additive at the runtime contract layer. The 3 new render-helper functions only fire when their respective driver receives a non-None modality payload — which only the orchestrator's full-cone path supplies. Direct callers of `llm_layer4_plan_create` / `llm_layer4_race_week_brief` / `llm_layer4_single_session_synthesize` that don't pass the new kwarg get default-None → no modality section in the prompt → identical pre-BM-3 LLM behavior. **Cache keys are forward-compatible**: pre-BM-3 cache entries written without a modality-hash slot continue to hit on default-None calls (the `or ""` collapse in each `*_key` helper makes the components string identical to pre-this-slice). The first POST-BM-3 deploy will see fresh keys for any orchestrator-driven call that supplies a modality payload; cache misses will trigger one round of re-synthesis with the modality section in the prompt, then settle on the new keys.

**Manual §5.0 walkthrough sequencing:** Andy should walk steps 1-3 (prompt body inspection per entry point) before relying on the modality cites in real coaching output. Step 4 (cache invalidation on dict change) needs a vocab-follow-on slice to actually exercise; can defer until BM-1 ships its first new discipline.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **G1** | Wire scope = A3 full wire (single_session + per_phase + race_week_brief) | Andy at first AskUserQuestion gate | Over A1 single_session only / A2 + per_phase / A4 no wire. Activates all 3 cone-consuming entry points; plan_refresh tier renderers + seam_review correctly excluded. |
| **G2 (R)** | Render shape = R2 top-pick + ranked menu + coaching flags + guidance line | Andy at second AskUserQuestion gate | Over R1 top-pick only / R3 flags only. Preserves the spec's menu-not-decision pattern. |
| **G2 (F)** | Render style = F2 per-renderer-native copy | Andy at second AskUserQuestion gate | Over F1 shared render helper. Each renderer's prompt copy matches its native idiom (`#` markdown / `===` boxes / mixed `#` + `**bold:**`). Tradeoff: 3 copies to maintain. |
| **G3** | Cache key scope = C2 all 3 cache keys (single_session + plan_create + race_week_brief) | Andy at third AskUserQuestion gate | Over C1 single_session only. Closes DI4 from the impl slice + closes the BM-1 vocab-addition staleness gap before it ships. |
| **G4** | ~8-10 file ceiling break ratified | Andy at fourth AskUserQuestion gate | Over Tighten-to-5 cuts (would have contradicted G1/G2/G3). Final: 9 substantive files; well below 12-file precedents. |
| **DI1** | All 3 new key helpers' modality-hash kwargs default to None and collapse None → '' | Architect at code-time | Forward-compat with pre-BM-3 cache entries: default-None callers produce stable keys identical to pre-this-slice; populated-hash callers produce new keys that invalidate on payload or dict shape change. |
| **DI2** | Per-renderer-native prompt copy emphasizes phase-awareness in per_phase only | Architect at code-time | Phase-bias guidance (`Peak biases outdoor + sport-specific; Taper biases lower-stimulus`) lives in per_phase's prompt copy where phase context is structurally available. single_session has no phase concept (one-off workout); race_week_brief is exclusively Taper-window (one phase). Avoids duplicate phase-bias hints in surfaces where they'd be redundant or noise. |
| **DI3** | Guidance line on `modality_id` citation discipline mirrored across all 3 renderers | Architect at code-time | Same risk in all 3: LLM cites internal `modality_id` strings in athlete-facing copy. The guidance line ("Cite … using natural names … never the internal `modality_id`") is short and worth duplicating across the 3 renderers despite the F2 / F1 tradeoff. |
| **DI4** | Empty payload renders a placeholder line (not omission) | Architect at code-time | When the resolver returns no recommendations + no flags (e.g. all disciplines absent from `_MODALITY_OPTIONS_PER_DISCIPLINE`), the section header still renders with `_No modality recommendations available_` placeholder so the LLM doesn't infer a silent section drop and start hallucinating modality reasoning. Trivial cost; clearer signal. |
| **DI5** | `TestRendererSpliceIntoFullPrompts` uses `model_construct` + duck-typed attribute holders for Layer3APayload | Architect at test-time | Layer3APayload's nested `current_state` / `recent_trajectory` / `data_density` shape is pydantic-validated; a full fixture would have been ~30 lines for no semantic gain since the renderer reads ~6 attributes. `model_construct` bypasses validation; duck-typed `type("X", (), {...})()` builds the attribute surface. Safe because the renderer's read set is small and well-known. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/single_session.py` defines `_render_modality_section_single_session` | ✅ `grep -n "^def _render_modality_section_single_session" layer4/single_session.py` returns 1 |
| `layer4/per_phase.py` defines `_format_modality_recommendations_per_phase` | ✅ `grep -n "^def _format_modality_recommendations_per_phase" layer4/per_phase.py` returns 1 |
| `layer4/race_week_brief.py` defines `_render_modality_section_race_week_brief` | ✅ `grep -n "^def _render_modality_section_race_week_brief" layer4/race_week_brief.py` returns 1 |
| `single_session_synthesize_key` carries `layer2_modality_locale_hash` kwarg | ✅ `grep "layer2_modality_locale_hash" layer4/hashing.py` returns 5 |
| `plan_create_key` carries `layer2_modality_hash` kwarg | ✅ `grep -E "layer2_modality_hash" layer4/hashing.py` returns 5 (3 in race_week_brief_key + plan_create_key + their docstrings) |
| `race_week_brief_key` carries `layer2_modality_hash` kwarg | ✅ (same grep above; the helper appears in both functions) |
| `llm_layer4_plan_create_cached` carries `layer2_modality_payload` kwarg + hashes it | ✅ `grep "layer2_modality_payload" layer4/cached_wrappers.py` returns 8 |
| `llm_layer4_race_week_brief_cached` carries `layer2_modality_payload` kwarg + hashes it | ✅ (same grep above) |
| `llm_layer4_single_session_synthesize_cached` hashes `layer2_modality_payload_for_locale` into the key | ✅ `grep "layer2_modality_locale_hash" layer4/cached_wrappers.py` returns 2 |
| `orchestrate_race_week_brief` threads `cone.layer2_modality_payload` to the cached wrapper | ✅ `grep "layer2_modality_payload=cone.layer2_modality_payload" layer4/orchestrator.py` returns 2 |
| `orchestrate_plan_create` threads `cone.layer2_modality_payload` to the cached wrapper | ✅ (same grep above; 2 = race_week_brief + plan_create) |
| `llm_layer4_plan_create` carries `layer2_modality_payload` kwarg | ✅ `grep "layer2_modality_payload" layer4/plan_create.py` returns 5 |
| `_run_pattern_a_engine` carries + threads `layer2_modality_payload` | ✅ (same grep above; engine signature + 2 synthesize_phase forwards) |
| `synthesize_phase` carries `layer2_modality_payload` kwarg | ✅ `grep "layer2_modality_payload" layer4/per_phase.py` returns 6 |
| `tests/test_layer2_modality.py` ships 42 tests (30 from impl slice + 12 NEW BM-3 render tests) | ✅ `PYTHONPATH=. pytest tests/test_layer2_modality.py --collect-only -q 2>&1 \| tail -1` shows "42 tests collected" |
| `tests/test_layer4_hashing.py` ships 103 tests (94 prior + 9 NEW BM-3 cache-key tests) | ✅ `PYTHONPATH=. pytest tests/test_layer4_hashing.py --collect-only -q 2>&1 \| tail -1` shows "103 tests collected" |
| Reproducer subset 1580 → 1601 + 16 skipped (+21 net) | ✅ `PYTHONPATH=. pytest tests/ --ignore=tests/test_layer1_builder.py --no-header -q 2>&1 \| tail -1` shows "1601 passed, 16 skipped" |
| `test_layer1_builder.py` standalone unchanged at 22 | ✅ `PYTHONPATH=. pytest tests/test_layer1_builder.py --no-header -q 2>&1 \| tail -1` shows "22 passed" |
| ETL `etl/tests/` unchanged at 139 | ✅ `PYTHONPATH=. pytest etl/tests/ --no-header -q 2>&1 \| tail -1` shows "139 passed" |
| All 7 edited Python files compile | ✅ `python3 -m py_compile layer4/hashing.py layer4/cached_wrappers.py layer4/orchestrator.py layer4/single_session.py layer4/per_phase.py layer4/race_week_brief.py layer4/plan_create.py` returns 0 |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ `head -10 aidstation-sources/CURRENT_STATE.md` shows BM3_PromptBodyIntegration handoff name |
| `CURRENT_STATE.md` exactly 1 "## Last shipped session" header | ✅ `grep -c "^## Last shipped session" aidstation-sources/CURRENT_STATE.md` returns 1 |
| `CURRENT_STATE.md` predecessor demoted to "**Predecessor:**" entry | ✅ `grep -c "^\*\*Predecessor:" aidstation-sources/CURRENT_STATE.md` returns 42 (previous 41 + this slice's demoted BestFitModalityImpl = 42) |
| `CARRY_FORWARD.md` BM-3 forward-pointer flipped to ✅ Shipped | ✅ `grep "Prompt-body integration shipped 2026-05-24.*BM3" aidstation-sources/CARRY_FORWARD.md` returns 1 |

---

## 9. Files shipped this session

**Substantive (9 files; ceiling break ratified at G4 gate):**

1. MOD `layer4/hashing.py` — +30 lines; 3 cache-key helpers gained optional `layer2_modality_hash` / `layer2_modality_locale_hash` kwargs with None → '' forward-compat collapse.
2. MOD `layer4/cached_wrappers.py` — +35 lines; 3 cached wrappers gained modality hash computation + key wire + driver kwarg thread.
3. MOD `layer4/orchestrator.py` — +4 lines; 2 call sites pass `cone.layer2_modality_payload` to the cached wrappers.
4. MOD `layer4/single_session.py` — +75 lines; NEW `_render_modality_section_single_session` + driver consumes existing kwarg in render call.
5. MOD `layer4/per_phase.py` — +70 lines; NEW `_format_modality_recommendations_per_phase` + new render kwarg + `synthesize_phase` kwarg threaded.
6. MOD `layer4/race_week_brief.py` — +75 lines; NEW `_render_modality_section_race_week_brief` + driver new kwarg + render call threaded.
7. MOD `layer4/plan_create.py` — +5 lines; `_run_pattern_a_engine` + `llm_layer4_plan_create` + 2 `synthesize_phase` call sites accept + thread the kwarg.
8. MOD `tests/test_layer4_hashing.py` — +50 lines; 6 new tests covering modality-hash None-collapse + populated-hash distinguish + parametrized mutation coverage.
9. MOD `tests/test_layer2_modality.py` — +300 lines; 12 new tests across 4 classes covering all 3 render helpers + the splice site at single_session.

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

10. MOD `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BestFitModalityImpl line preserved by being demoted to the first "**Predecessor:**" entry. 1 "## Last shipped session" header; 42 "**Predecessor:**" entries.
11. MOD `aidstation-sources/CARRY_FORWARD.md` — BM-3 forward-pointer flipped from "Trigger #1 prompt-design gate; ~3-5 files" to ✅ "Prompt-body integration shipped 2026-05-24 (BM3)"; §5.0 walkthrough scenario count flipped 101 → 102 (NEW BM-3 §5.0 added).
12. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BM3_PromptBodyIntegration_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **BM-3 Layer 4 prompt-body integration ✅ Shipped**. `Layer2ModalityPayload` now renders into all 3 plan-gen prompt bodies (single_session + per_phase + race_week_brief) per F2 per-renderer-native; matching cache keys extended with `layer2_modality_hash` / `layer2_modality_locale_hash` slots per G3 (closes DI4 from the impl slice). Resolver is no longer dormant — Andy's PGE 2026 race-week brief + plan-create + on-demand workouts all cite the modality menu when the resolver returns recommendations for an included discipline at the primary locale.
- **DI4 from the impl slice ✅ Closed.** Single-session cache key now includes the modality payload hash; the 1-line follow-on landed inside this slice's broader cache-key extension work.
- **Per-discipline vocab population (BM-1) — 9 deferred AR disciplines** carry forward unchanged. With BM-3 shipped, vocab additions now have observable LLM-facing effect in 3 prompts (and the cache invalidates cleanly on the dict shape change).
- **NEW Phase-aware ranking inside Layer 4 (BM-2) is now more actionable** — per_phase's prompt copy includes a Peak / Taper bias hint guidance line. The next refinement (BM-2) is structured prompt copy that operationalizes the bias per phase rather than a one-line hint.
- **BM-5 equipment-name canonicalisation** carries forward unchanged; renderer prints `modality_id` verbatim so vocab additions + canonicalisation both propagate without renderer changes.
- **Multi-locale cluster ingestion** carries forward unchanged; orchestrator still feeds primary locale only.
- **plan_refresh tier renderers (T1/T2/T3-intra-phase) modality wire** is now a NEW open forward-pointer (intentionally not wired in BM-3 per G1=A3; explicit deferral with rationale).
- **§5.0 walkthrough scenario count 101 → 102** — NEW BM-3 §5.0 added (5 steps: single_session prompt inspection / per_phase prompt inspection / race_week_brief prompt inspection / cache invalidation on `_MODALITY_OPTIONS_PER_DISCIPLINE` change / forward-compat None → '' cache-key collapse).
- **Pre-existing forward-pointers carried** — #8 locales→locations rename (now also touches the 3 NEW renderer copies + their tests); bounce-back UX follow-on (~1-2 files; SkillCaptureSurface D6); Layer 2B per-discipline gap reasoning; #6+#4 injury form refresh; #2b race-URL site-parse; §I.1 structured supplements; Bucket D legacy hardcoded locales.

**End of handoff.**
