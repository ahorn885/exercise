# V5 Implementation — Layer 4 Step 4e Race-Week Brief D-66 Integration Closing Handoff

**Session:** Single chat. Scope: Layer 4 implementation Step 4e — `llm_layer4_race_week_brief` D-66 caller integration (Pattern B; race-week brief synthesizer + RacePlan for multi-day events). Closes the D-66 design wave's primary consumer + the Layer 4 Step 4 implementation sub-arc (4a/4b/4c/4d/4e). Paired contract amendments: `layer4/context.py` Layer3BPayload extension + RaceEventStub→RaceEventPayload replacement; `layer4/payload.py` KitItem.layer0_canonical field; `layer4/validator.py` rule rebinding; `Layer4_Spec.md` §4.5 source-pointer note + §7.13 KitItem.layer0_canonical + §K→§H.4 drift fix + §5.4 D-66 forward-pointer flip; `Layer3_3B_Spec.md` §7 event-metadata fields amendment; `Layer4_RaceWeekBrief_v1.md` → `_v2.md` surgical prompt body amendment per Rule #12.
**Date:** 2026-05-18
**Predecessor handoff:** `V5_Design_D66_Race_Events_Closing_Handoff_v1.md` (D-66 design wave shipped 2026-05-18 earlier same day; commit `7a834aa` on origin/main via PR #77).
**Branch:** `claude/review-race-events-design-Pjjea` (harness-pinned for this session — name carried over from the harness even though this session is Step 4e implementation; precedent: harness names mismatched with scope across PR-A → Step 4a → Step 4b/c → Step 4d → D-66 design wave → Step 4e).
**Status:** 🟢 5 substantive code + 3 spec/prompt + 1 test + 3 bookkeeping = 10 files. Combined `tests/` 445 → 501 net new in 0.66s. **D-66 contract fully integrated end-to-end.** Step 4f `plan_create` Pattern A is the architect-recommended next forward move (heaviest remaining; closes the Layer 4 Step 4 sub-arc completely).

---

## 1. Session-start verification (Rule #9)

Predecessor D-66 design wave handoff §6 claimed: 6 files on disk (`Race_Events_D66_Design_v1.md` + `Layer4_Spec.md` §3.4/§4.5/§5.4 amendments + `Athlete_Onboarding_Data_Spec_v5.md` §A.1/§H.2/§H.4 + `Project_Backlog_v48.md` + CLAUDE.md + closing handoff); commit `7a834aa` on origin/main; working tree clean on fresh-cut branch `claude/review-race-events-design-Pjjea`.

Verified at session start (before any edits):

| Claim | Anchor | Result |
|---|---|---|
| `Race_Events_D66_Design_v1.md` exists | `ls -la` | ✅ 58.8KB |
| `Layer4_Spec.md` §3.4 has `race_event_payload: RaceEventPayload` arg | grep line 234 | ✅ |
| `Layer4_Spec.md` §4.5 has 2 new D-66 preconditions | grep lines 810-811 | ✅ |
| `Layer4_Spec.md` §5.4 D-66 forward-pointer block | grep line 927 | ✅ flipped to "Design wave shipped 2026-05-18" |
| `Athlete_Onboarding_Data_Spec_v5.md` §H.2 + §H.4 + §A.1 amendments | grep | ✅ |
| `Project_Backlog_v48.md` exists | `ls -la` | ✅ 261.3KB |
| Combined `tests/` 445 green | `python -m pytest tests/ -q` | ✅ 445 passed in 0.82s |
| Working tree clean on fresh-cut branch `claude/review-race-events-design-Pjjea` | `git status` | ✅ |
| Commit `7a834aa` on origin/main | `git log --oneline -5` | ✅ |

**1 drift found:** `Layer4_Spec.md` line 812 had 2 stale `§K` references that should have been `§H.4` per the D-66 closing handoff §2.3 rename narrative ("§A/§K → §H.2/§H.4 was applied to the design doc but missed in Layer4_Spec.md cross-references"). The handoff's §6 verification table claimed ✅ on this row via grep but didn't read the wording. Fixed inline this session as a bundled cleanup.

---

## 2. Session narrative — Step 4e race-week-brief implementation (Andy 2026-05-18)

Andy opened with the URL to the D-66 design wave closing handoff + "let's go." I followed §5 operating notes — re-read CLAUDE.md (Rule #13), ran Rule #9 verification, surfaced state + focus + drift, and offered scope options via `AskUserQuestion`.

### 2.1 Scope pick

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **Step 4e race-week-brief implementation** (architect-recommended next forward move per the D-66 handoff §4).

### 2.2 Contract gap surfacing — 4-question AskUserQuestion gate

During the load-bearing-file re-read (Rule #13: `Race_Events_D66_Design_v1.md` + `Layer4_Spec.md` §3.4/§4.5/§5.4/§7.13/§7.14 + `Layer4_RaceWeekBrief_v1.md` + `layer4/single_session.py` analog + `layer4/plan_refresh.py` analog), I discovered **2 pre-existing contract gaps** + the **expected Trigger #2 prompt-body amendment**:

- **Gap 1**: `Layer3BPayload` (in `layer4/context.py:767`) lacks the 4 event-metadata fields the spec §4.5 + the design doc §8.2 reference (`event_date`, `event_locale_id`, `race_format`, `time_to_event_weeks`). Same shape as the PR-C-followon `Layer3APayload.current_state.active_injuries` gap (referenced in spec, never existed in typed contract).
- **Gap 2**: `KitItem` (in `payload.py:409`) lacks the `layer0_canonical: bool` field that `Layer4_RaceWeekBrief_v1.md` §4.1 tool schema has + §4 cross-output rule 13 makes load-bearing for validator.
- **Trigger #2** (pre-flagged in D-66 handoff §4.2): prompt body §4.1 `pacing_target` is pre-D1 free-shape dict; payload uses typed `IntensityTarget` 9-shape union per §7.3.1. §3/§6 of the prompt have no route-locale-aware rendering surface for the new `RaceEventPayload.route_locales[]` structured input.

Surfaced via 4-question AskUserQuestion (per Step 4a/4b/c/4d precedent):

1. **Layer3BPayload gap**: Path A (race_event_payload exclusively + defer 3B extension) vs **Path B (extend Layer3BPayload now + paired Layer3_3B_Spec.md §7 amendment)** vs Path C (silently skip §4.5 rows). **Andy picked Path B.**
2. **KitItem gap**: **Add `layer0_canonical: bool` to KitItem in payload.py + paired §7.13 amendment** vs drop from tool schema. **Andy picked Path A (add now).**
3. **Prompt body amendment**: **v1 → v2 surgical amendment per Step 4a precedent** vs driver-folds-flatly minimum-viable. **Andy picked surgical v2 amendment.**
4. **File ceiling break**: **Yes** vs trim scope to fit. **Andy picked yes.**

### 2.3 Implementation order

1. `layer4/payload.py` — add `KitItem.layer0_canonical: bool = False` field (1-line additive change).
2. `layer4/context.py` — replace `RaceEventStub` with `RouteLocaleEquipment` + `RouteLocale` + `RaceEventPayload` typed pydantic v2 models + 2 Literal aliases (`RaceFormat` + `RouteLocaleRole`); extend `Layer3BPayload` with 4 optional event-metadata fields + paired model_validator (`mode == 'no-event'` requires all 4 fields None).
3. `layer4/validator.py` — swap `RaceEventStub` import → `RaceEventPayload`; update `ValidatorContext.race_event` type; rebind `_rule_kit_manifest_inputs_incomplete` body from pre-D-66 always-warn to D-66-active 3-outcome rule per spec §5.4 line 912.
4. `layer4/__init__.py` — 7 new re-exports + drop retired `RaceEventStub`.
5. `tests/test_layer4_validator.py` — swap `RaceEventStub` import to `RaceEventPayload`; replace pre-D-66 `test_kit_manifest_inputs_incomplete_warns_on_multi_day` with 2 D-66-active tests (`_skipped_when_race_event_none` + `_no_route_locales_warns`).
6. `layer4/race_week_brief.py` (NEW) — driver per Step 4a/4b/c/4d precedent (~1100 lines).
7. `tests/test_layer4_race_week_brief.py` (NEW) — 55 tests covering RaceEventPayload pydantic + tool schema + §4.5 input validation + entry-point happy path + observation emission + capped retry + schema violation + Layer4Payload composition + prompt rendering + Layer3BPayload event-metadata.
8. Spec amendments: `Layer4_Spec.md` line 812 §K → §H.4 drift fix + §7.13 KitItem.layer0_canonical + §4.5 source-pointer amendment + §5.4 D-66 forward-pointer ✅ Step 4e shipped; `Layer3_3B_Spec.md` §7 event-metadata fields + schema-rule.
9. Prompt body v2 amendment: new `Layer4_RaceWeekBrief_v2.md` (surgical; v1 retained per Rule #12).
10. Bookkeeping: CLAUDE.md + Project_Backlog v48 → v49 + this handoff.

### 2.4 Files shipped

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `layer4/race_week_brief.py` | New | ~1100 lines; driver + tool schema + prompt rendering + LLM caller + capped-retry loop + Layer4Payload composition. |
| 2 | `layer4/context.py` | Modified | Replace RaceEventStub with RaceEventPayload + RouteLocale + RouteLocaleEquipment + 2 Literal aliases; extend Layer3BPayload with 4 optional event-metadata fields + paired model_validator. |
| 3 | `layer4/validator.py` | Modified | Import swap RaceEventStub → RaceEventPayload + ValidatorContext.race_event type swap + kit_manifest_inputs_incomplete rebinding to D-66-active 3-outcome rule. |
| 4 | `layer4/payload.py` | Modified | KitItem.layer0_canonical: bool = False field (additive). |
| 5 | `layer4/__init__.py` | Modified | 7 new re-exports (RaceEventPayload + RaceFormat + RouteLocale + RouteLocaleEquipment + RouteLocaleRole + build_record_race_week_brief_tool + llm_layer4_race_week_brief); drop RaceEventStub. |
| 6 | `tests/test_layer4_validator.py` | Modified | RaceEventStub import → RaceEventPayload; replace pre-D-66 kit_manifest test with 2 D-66-active tests. |
| 7 | `tests/test_layer4_race_week_brief.py` | New | ~1200 lines, 55 tests. |
| 8 | `aidstation-sources/Layer4_Spec.md` | Modified | §K → §H.4 drift fix on line 812; §4.5 source-pointer amendment for rows 3/5/6/8; §7.13 KitItem.layer0_canonical field; §5.4 D-66 forward-pointer flipped to "✅ Design wave shipped 2026-05-18 + Step 4e race-week-brief implementation shipped 2026-05-18". |
| 9 | `aidstation-sources/Layer3_3B_Spec.md` | Modified | §7 Layer3BPayload event-metadata fields + paired no-event-mode-requires-None schema-level rule. |
| 10 | `aidstation-sources/prompts/Layer4_RaceWeekBrief_v2.md` | New | Surgical amendment per Rule #12 (v1 retained as in-project history). v2 changes: §3.1 source pointers updated to race_event_payload + NEW §3.11 route_locales structured graph + §4.1 pacing_target typed IntensityTarget oneOf + §4.1 KitItem.layer0_canonical surfaced + §6 user prompt template route-locales rendering block. System prompt + all coaching policy unchanged. |
| 11 | `aidstation-sources/Project_Backlog_v48.md` → `_v49.md` | New (per Rule #12) | Step 4e narrative; v48 demoted to predecessor. |
| 12 | `aidstation-sources/CLAUDE.md` | Modified | Step 4e narrative; D-66 design wave demoted to predecessor (compressed). Backlog ref v48 → v49. Authoritative files updated (Layer 4 implementation list gains Step 4e files; prompt body list gains v2). Next-forward-move recommends Step 4f. |
| 13 | `aidstation-sources/handoffs/V5_Implementation_Layer4_Step4e_RaceWeekBrief_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**10 substantive + 3 bookkeeping = 13 files total. Over the 5-file ceiling intentionally** — Andy confirmed at session start via AskUserQuestion question #4; precedented across Step 4d 13 + Step 4b/c 10 + PR-A 8 + Step 4a 8 + PR-C-followon 6 + PR-D 6 + PR-E 6 + D-66 design wave 6.

### 2.5 Architectural choices on the record

- **Session merging at the driver level.** Race-week-brief returns the FULL merged Taper-week session set in `Layer4Payload.sessions` (override sessions replace prior by session_id; non-overridden prior sessions pass through verbatim; result sorted by date + session_index_in_day). The §5.4 validator's volume_band / intensity_dist / acwr rules see the complete Taper-week shape. Alternative ("overrides only") would make those rules un-evaluable on the typical race-week scenario where the synthesizer modifies 1-2 sessions out of a 7-14-day Taper window.
- **RaceEventPayload model_validator** enforces all 4 §4.2 structural invariants at construction (sequence_idx unique + sorted ascending + first role='start' + last role='finish' when route_locales non-empty). Empty route_locales is structurally legal; validator surfaces the soft-warning via `kit_manifest_inputs_incomplete_no_route_locales`.
- **Layer3BPayload event-metadata fields default to None** for backwards compatibility with legacy 3B-non-event-mode + pre-D-66 callers. v1 implementation prefers `race_event_payload` as source-of-truth for downstream consumption per the §4.5 source-pointer amendment. The 3B `event_date` field is read defensively only for the `race_event_date_mismatch_3b` precondition (skipped when None).
- **`_emit_data_gap_observations` text trimmed** to fit Observation.text 240-char cap (raised pydantic ValidationError on the first pass; tightened wording to "{rule_name}: kit-manifest synthesis degraded; athlete may complete route-locale equipment via /profile?tab=race-events.").
- **Schema-violation handling**: missing `race_week_brief` OR multi-day-without-`race_plan` OR `session_id_to_override` referencing an unknown prior session all raise `Layer4OutputError('schema_violation')` after one schema-only-retry per §5.5; cap-hit raises.
- **`_default_llm_caller`** follows the `single_session.py` precedent: Anthropic SDK + extended_thinking (budget 5500 default per §3.4) + forced tool_choice; dependency-injectable via `LLMCaller` type alias for tests.
- **Pre-rendered prompt context** includes all 8 upstream payloads (1 + 2A + 2B + 2C-per-locale + 2D + 2E + 3A + 3B) + race_event_payload + prior_plan_session_window — full payload verbatim per the v1 prompt body D3 (no trimming).
- **Best-effort cap-hit semantics**: outstanding blocker-severity rule failures demoted to warnings + synthesized accepted ValidatorResult appended so the `validator_results[-1].accepted=True` Layer4Payload invariant holds; `Observation(category='best_effort_plan', elevates_to_hitl=True)` per §5.5.

### 2.6 Stop-and-ask triggers — #2 + #5 + #8 fired

- **Trigger #2 (designing or significantly modifying an LLM prompt body):** fired on the `Layer4_RaceWeekBrief_v1.md → v2.md` amendment (Andy picked surgical v2 per Step 4a precedent over driver-folds-flatly minimum-viable). Routed via this session's AskUserQuestion gate #3.
- **Trigger #5 (schema/inter-layer-contract amendments):** fired twice — Layer3BPayload extension with 4 event-metadata fields + paired `Layer3_3B_Spec.md` §7 amendment (gate #1); KitItem.layer0_canonical field + paired `Layer4_Spec.md` §7.13 amendment (gate #2). Both routed via AskUserQuestion.
- **Trigger #8 (architectural alternatives with real tradeoffs):** fired on all 3 gates × 2-3 alternatives each; Andy picked Path B / Path A / Path A.
- **Trigger #11 (cross-layer D-rows):** did NOT fire — D-66 + the 2 paired field-gap-closure amendments fall under existing tracked scope (no new cross-layer D-row).
- Other triggers — none applicable.

### 2.7 Scope NOT changed this session

- **Step 4f `plan_create` Pattern A orchestration** — deferred to next session (architect-recommended).
- **v5 onboarding implementation PR** — consumes §H.2 + §H.4 + §A.1 amendments from D-66 design wave; independent of Layer 4 implementation track; can run in parallel.
- **DDL migrations** for `race_events` + `race_route_locales` + `race_route_locale_equipment` tables per `Race_Events_D66_Design_v1.md` §3 + the migration script in §10 — both deferred to v5 onboarding implementation PR (D-66 design doc §10 specifies the migration verbatim; not landed in `init_db.py _PG_MIGRATIONS` this session because the implementation track depends on onboarding wiring + Andy hasn't OAuth'd D-50 yet).
- **D-67 / D-68 / D-70 / D-71** — not touched.
- **Layer 4.5 Joint Session Coordinator** — out of scope.
- **Layer 5 spec** — out of scope (consumes RaceEventPayload when speced).

---

## 3. Spec amendments paired this session — surgical edit summary

### 3.1 `Layer4_Spec.md`

- **Line 812 (§4.5 row 9 `kit_manifest_inputs_incomplete` activation note):** §K → §H.4 in 2 occurrences (drift fix carried from D-66 closing handoff §2.3 rename narrative).
- **Line 927 (§5.4 D-66 forward-pointer block):** flipped from "✅ Design wave shipped 2026-05-18" alone to "✅ Design wave shipped 2026-05-18 + **Step 4e race-week-brief implementation shipped 2026-05-18**" with full implementation-side description (rule 3-outcome branch + closing handoff reference).
- **§4.5 source-pointer amendment block (new):** added before the §4.5 race-week-brief precondition table describing the D-66 source-of-truth amendments — rows 3 (event_date_in_past), 5 (event_locale_unresolved), 6 (race_format_unset), 8 (race_event_date_mismatch_3b) all source from race_event_payload exclusively in v1; row 8 defensively skips when `layer3b_payload.event_date is None`. Row text amendments inline.
- **§7.13 KitItem extension:** `KitItem` model gains `layer0_canonical: bool` field (paired Trigger #5 amendment); validator rule 13 (per-item canonical-name check per prompt body §4 cross-output rule 13) becomes evaluable.

### 3.2 `Layer3_3B_Spec.md`

- **§7 Layer3BPayload extension:** 4 new optional fields (`event_date: date | None`, `event_locale_id: str | None`, `race_format: str | None enum`, `time_to_event_weeks: int | None`) per the D-66 paired amendment. Sourced from the orchestrator-joined target `race_events` row (`is_target_event=true`) per `Race_Events_D66_Design_v1.md` §8.
- **§7 schema-level rules**: new rule — "D-66 paired amendment 2026-05-18 (event-metadata fields)": `mode == 'no-event'` requires all 4 fields None; `mode == 'event'` SHOULD populate them but pre-amendment 3B implementations may leave them None (Layer 4 race-week-brief sources from race_event_payload exclusively per `Layer4_Spec.md` §4.5 source-pointer note).

### 3.3 `Layer4_RaceWeekBrief_v1.md` → `_v2.md` (per Rule #12)

Surgical amendment document (~330 lines vs v1's 955 lines). v1 retained as in-project history; v2 documents the changes inline + explicitly lists which v1 sections are unchanged.

- File header status block + v2 changes summary.
- 3 new source-decision rows: D14 (D-66 race-event data model integration), D15 (pacing_target typed IntensityTarget union), D16 (KitItem.layer0_canonical surfaced).
- §3.1 source-pointer updates table (3 changed rows).
- NEW §3.11 "Route locales (D-66 structured graph)" describing the typed `RaceEventPayload.route_locales[]` input.
- §4.1 tool schema surgical changes (`pacing_target` typed IntensityTarget oneOf + `kit_manifest[].layer0_canonical` surfaced).
- §6 user prompt template route-locales rendering block.
- Pointer to v1 for all unchanged sections (§1, §2, §3.2-3.10, §4 minus the changes above, §5 system prompt, §6 unchanged sections, §7-14).

### 3.4 `Project_Backlog_v48.md` → `_v49.md`

- File-revision-header bumped to v49 with full Step 4e narrative; v48 demoted to predecessor.
- D-66 row already at 🟢 Design wave shipped (D-66 design wave handoff) — implementation row added stating "🟢 Step 4e race-week-brief D-66 caller integration shipped 2026-05-18".
- No new D-rows.

### 3.5 `CLAUDE.md`

- Last-shipped-session narrative replaced with Step 4e block; D-66 design wave demoted to predecessor (compressed but preserved).
- Backlog ref v48 → v49.
- Authoritative current files: Layer 4 implementation list gains `layer4/race_week_brief.py` + `tests/test_layer4_race_week_brief.py` + extended context.py annotation. Layer 4 prompt bodies gains `Layer4_RaceWeekBrief_v2.md` (v1 retained as in-project history).
- Layer pipeline status row 4 updated to "Steps 4a + 4b + 4c + 4d + 4e of 8 COMPLETE."
- Race-event design wave authoritative line: gains "🟢 Step 4e race-week-brief implementation shipped 2026-05-18 — D-66 contract fully integrated end-to-end".
- Next-forward-move recommends Step 4f as architect-recommended.

---

## 4. Next session pointers — Step 4f `plan_create` Pattern A orchestration

**Architect-recommended next forward move:**

### 4.1 Step 4f scope: `llm_layer4_plan_create` Pattern A orchestration

Heaviest remaining sub-step. Closes the Layer 4 Step 4 sub-arc (4a/4b/4c/4d/4e shipped; 4f closes 4 of 4 entry points). Per `Layer4_Spec.md` §5.2 Pattern A:

1. Compute `phase_structure_from_3b(layer3b_payload, plan_start_date)` (already shipped via Step 4d's `layer4/phase_structure.py`).
2. Per-phase synthesis loop (sequential, in order): call synthesizer LLM with `Layer4_PerPhase_v1.md` per phase + prior phase's accepted output as context + intended exit/entry state + seam-driven `seam_issues` constraint deltas merged in. Each phase has its own retry budget per §5.5.
3. Seam-review loop (after per-phase synthesis completes): call LLM seam-reviewer (`Layer4_SeamReviewer_v1.md`) per adjacent-phase pair; β propose-patch authority per §6.2 (re_prompt_prior / re_prompt_next / accept_with_observation).
4. Final cross-phase validator pass over the union of all sessions; cross-phase blockers elevate to `best_effort_plan` notable_observation.
5. Compose Layer4Payload with `pattern='A'`, `phase_structure` populated, `seam_reviews` populated.

**T3 cross-phase Pattern A** naturally lands here as a consumer of the same per-phase machinery — closes the `tier_t3_cross_phase_requires_pattern_a` raise path from Step 4d's `plan_refresh.py` driver.

### 4.2 Projected file plan (~6-8 files)

1. NEW `layer4/plan_create.py` (~1500 lines projected) — per-phase synthesis loop + seam-review loop + final cross-phase validator pass + best-effort cap-hit; consumes `phase_structure_from_3b()` + `phase_for_date()` from Step 4d.
2. Modify `layer4/plan_refresh.py` to swap `tier_t3_cross_phase_requires_pattern_a` raise for a delegate call to `plan_create.synthesize_phases()` once Pattern A orchestration is available (or extract the per-phase machinery to a shared helper module per architectural pick).
3. Modify `layer4/__init__.py` re-exports.
4. NEW `tests/test_layer4_plan_create.py` (~80-100 tests projected; cross-phase scope = wider per-phase coverage + seam-review behavior + final-pass cross-phase validator + best-effort cap-hit at seam vs phase scope).
5. Modify `tests/test_layer4_plan_refresh.py` to remove the T3-cross-phase-raises-pattern_a placeholder + add T3-cross-phase happy path tests.
6. Possibly NEW `layer4/seam_review.py` (~400 lines projected) — LLM seam-reviewer call + propose-patch authority application per §6.2.
7. Possibly NEW `layer4/per_phase.py` (~600 lines projected) — per-phase synthesizer module; clean separation from `plan_create.py`'s orchestration loop; reusable by T3 cross-phase Pattern A.
8. Bookkeeping (CLAUDE.md + Project_Backlog v49 → v50 + closing handoff).

**Combined `tests/` projected: 501 → ~600+.**

### 4.3 Stop-and-ask risk for Step 4f

- **Trigger #2** — `Layer4_PerPhase_v1.md` + `Layer4_SeamReviewer_v1.md` may need amendments for v2 prompt body update similar to Step 4a's `Layer4_SingleSession_v1 → v2` (Step 4a precedent). Pre-flag for the implementation session; v1 prompt bodies were drafted pre-D1 typed IntensityTarget union + pre-PR-C-followon AccommodationModality + pre-D-66 RaceEventPayload — re-grounding against the current typed contracts may be needed.
- **Trigger #5** — likely fires on the per-phase synthesizer's typed input contracts (per-phase scope + prior-phase context shape) if any structural-invariant surprises surface during implementation. Route via implementation-session AskUserQuestion gate.
- **Trigger #8** — architectural alternatives expected: (a) `plan_create.py` monolithic vs split into `per_phase.py` + `seam_review.py` + thin orchestration; (b) Sequential per-phase synthesis (spec v1 default) vs parallel where seams are independent (§5.2 concurrency optimization); (c) Seam-review retry budget scoping (per-seam vs shared with phase retries); (d) T3 cross-phase Pattern A reuses plan_create's per-phase machinery vs duplicates.
- **Trigger #11** — not expected.

### 4.4 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff (Step 4e closing).
3. **Third re-read**: `Layer4_Spec.md` §5.2 Pattern A + §6.1 phase structure + §6.2 seam-review authority + §6.3 routing.
4. **Fourth re-read**: `aidstation-sources/prompts/Layer4_PerPhase_v1.md` (~764 lines) + `Layer4_SeamReviewer_v1.md` (~436 lines).
5. **Fifth re-read**: `layer4/phase_structure.py` + `layer4/single_session.py` + `layer4/plan_refresh.py` (closest implementation analogs).
6. **Branch**: cut fresh off post-merge main OR stay on the harness pin (precedent).
7. **Test convention**: top-level `tests/test_layer4_plan_create.py` for Step 4f.

---

## 5. Open items / decisions pinned this session

### 5.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Layer3BPayload event-metadata gap = Path B (extend now with 4 optional fields + paired §7 amendment) | Andy 2026-05-18 | Cleaner long-term contract; closes the Trigger #5 contract gap properly; matches design doc §8.2 framing. Defaults to None preserve backwards compat. |
| 2 | KitItem.layer0_canonical = add to typed KitItem in payload.py now + paired §7.13 amendment | Andy 2026-05-18 | Small additive change; validator rule 13 (per-item canonical-name check) becomes evaluable; follows Step 4a full-fidelity precedent. |
| 3 | Prompt body amendment = v1 → v2 surgical amendment per Step 4a precedent | Andy 2026-05-18 | Full fidelity; Trigger #2 fires properly; route via AskUserQuestion gate. Rule #12 v2 bump with v1 retained as in-project history. |
| 4 | File ceiling = break (10 files projected) | Andy 2026-05-18 | Precedented across the Layer 4 implementation arc. Single PR captures D-66-active surface end-to-end. |
| 5 | Session merging at driver level (overrides + non-overridden prior sessions = merged Taper-week view) | Architect-pick | Validator's volume_band / intensity_dist / acwr rules need the full Taper-week shape; alternative would make them un-evaluable. |
| 6 | §4.5 row 5 (event_locale_unresolved) handled caller-side | Architect-pick (paired with Andy Pick 1) | Orchestrator resolves race_event_payload.event_locale_id against locale_profiles before Layer 4 invocation. Layer 4 doesn't re-resolve. |
| 7 | `_emit_data_gap_observations` text trimmed to fit 240-char Observation.text cap | Architect-pick | Pydantic raised ValidationError on first pass; tightened wording. |

### 5.2 Stop-and-ask trigger retrospective

- **Triggers #2, #5 × 2, #8** fired and routed properly via the 4-question AskUserQuestion gate per the Step 4a/4b/c/4d precedent. AskUserQuestion-based gating substitutes for formal `/plan` mode.
- **No other triggers fired.**

### 5.3 No carry-forward expected for Step 4f session

Step 4f implementation is self-contained against:
- `Layer4_Spec.md` §5.2 Pattern A + §6.1 phase structure + §6.2 seam-review authority + §6.3 routing (all shipped).
- `phase_structure_from_3b()` + `phase_for_date()` + `scope_spans_phase_boundary()` (shipped via Step 4d).
- `Layer4_PerPhase_v1.md` + `Layer4_SeamReviewer_v1.md` prompt bodies (shipped 2026-05-16 + 2026-05-16).
- All typed context payloads (shipped via PR-D).
- Validator harness (shipped via PR-E).
- Layer4Payload + RaceEventPayload + Layer3BPayload event-metadata fields (this session).

Trigger #2 (prompt body amendments) is the most-likely fire surface during Step 4f if v2 amendments needed for `Layer4_PerPhase_v1.md` + `Layer4_SeamReviewer_v1.md` per the Step 4a/RaceWeekBrief precedent. Pre-flagged in §4.3 above.

### 5.4 Carried forward — Layer 1 typed payload

Still deferred. `Layer1Payload` is `dict[str, Any]` opaque pass-through across all entry points. Lands as typed pydantic model when Layer 1 implementation arc begins.

### 5.5 Carried forward — DDL migrations + onboarding/profile UI implementation

`race_events` + `race_route_locales` + `race_route_locale_equipment` table DDLs (per `Race_Events_D66_Design_v1.md` §3) + the migration script per §10 deferred to the v5 onboarding implementation PR. The Step 4e implementation works against the typed `RaceEventPayload` contract in `layer4/context.py`; the orchestrator joins from the DB tables when they're shipped. v1 unit tests build `RaceEventPayload` directly via the pydantic constructor without DB roundtrip.

---

## 6. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/race_week_brief.py` exists (~1100 lines) | ✅ inspection |
| `RaceEventPayload` + `RouteLocale` + `RouteLocaleEquipment` defined in `layer4/context.py` | ✅ grep |
| `Layer3BPayload` carries 4 event-metadata fields | ✅ grep |
| `RaceEventStub` removed from codebase (no remaining references) | ✅ grep — empty |
| `ValidatorContext.race_event: RaceEventPayload \| None` | ✅ grep validator.py:111 |
| `_rule_kit_manifest_inputs_incomplete` D-66-active 3-outcome branch | ✅ grep validator.py |
| `KitItem.layer0_canonical: bool = False` in payload.py | ✅ grep |
| `layer4/__init__.py` re-exports 7 new symbols + drops RaceEventStub | ✅ inspection |
| `tests/test_layer4_validator.py` import swap RaceEventStub → RaceEventPayload | ✅ grep |
| `tests/test_layer4_race_week_brief.py` exists with 55 tests | ✅ inspection |
| Combined `tests/` 501 green | `python -m pytest tests/ -q` | ✅ 501 passed in 0.66s |
| `Layer4_Spec.md` §K → §H.4 drift fix on line 812 | ✅ grep |
| `Layer4_Spec.md` §7.13 KitItem.layer0_canonical field | ✅ grep |
| `Layer4_Spec.md` §4.5 source-pointer amendment block | ✅ grep |
| `Layer4_Spec.md` §5.4 D-66 forward-pointer flipped to "✅ Design wave shipped + Step 4e shipped" | ✅ grep |
| `Layer3_3B_Spec.md` §7 event-metadata fields + paired schema rule | ✅ grep |
| `Layer4_RaceWeekBrief_v2.md` exists; v1 retained per Rule #12 | ✅ inspection |
| `Project_Backlog_v49.md` exists | ✅ inspection |
| `Project_Backlog_v49.md` file-revision-header bumped to v49 | ✅ grep line 5 |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v49.md` | ✅ grep line 84 |
| `CLAUDE.md` Last-shipped-session is Step 4e; D-66 design wave demoted to Predecessor | ✅ inspection |
| `CLAUDE.md` Authoritative files lists Step 4e files + Layer4_RaceWeekBrief_v2.md | ✅ grep |
| `CLAUDE.md` Next-forward-move recommends Step 4f | ✅ inspection |
| Branch is `claude/review-race-events-design-Pjjea` (harness-pinned) | ✅ |

---

## 7. Files shipped this session

One commit (or multiple bundled) on `claude/review-race-events-design-Pjjea`:

**Substantive code + spec + prompt (10 files):**
1. New `layer4/race_week_brief.py` (~1100 lines)
2. Modified `layer4/context.py` (RaceEventStub → RaceEventPayload + Layer3BPayload extension)
3. Modified `layer4/validator.py` (import swap + ValidatorContext field type + rule rebinding)
4. Modified `layer4/payload.py` (KitItem.layer0_canonical field)
5. Modified `layer4/__init__.py` (7 new re-exports)
6. Modified `tests/test_layer4_validator.py` (import swap + 2 D-66-active tests)
7. New `tests/test_layer4_race_week_brief.py` (~1200 lines, 55 tests)
8. Modified `aidstation-sources/Layer4_Spec.md` (§K → §H.4 + §7.13 KitItem + §4.5 source-pointer + §5.4 ✅ Step 4e)
9. Modified `aidstation-sources/Layer3_3B_Spec.md` (§7 event-metadata fields + schema-rule)
10. New `aidstation-sources/prompts/Layer4_RaceWeekBrief_v2.md` (surgical amendment; v1 retained)

**Bookkeeping (3 files):**
11. New `aidstation-sources/Project_Backlog_v49.md` (per Rule #12; v48 retained as predecessor)
12. Modified `aidstation-sources/CLAUDE.md`
13. New `aidstation-sources/handoffs/V5_Implementation_Layer4_Step4e_RaceWeekBrief_Closing_Handoff_v1.md` (this file)

**13 files total. Over the 5-file ceiling intentionally** — Andy confirmed at session start via AskUserQuestion question #4; precedented across Step 4d 13 + Step 4b/c 10 + PR-A 8 + Step 4a 8 + PR-C-followon 6 + PR-D 6 + PR-E 6 + D-66 design wave 6.

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- `PR_Verification_Status.md` aggregate — unchanged this session; Step 4e is implementation-layer (no UI surface yet; v5 onboarding implementation PR will add §5.0 row for the new `/profile?tab=race-events` tab + onboarding §H.2 + §H.4 walks per the D-66 design wave §7).
- **Step 4f `plan_create` Pattern A orchestration** — architect-recommended next forward move; heaviest remaining sub-step; closes the Layer 4 Step 4 sub-arc; T3 cross-phase Pattern A lands here naturally.
- v5 onboarding implementation PR — consumes §H.2 + §H.4 + §A.1 extensions per D-66 design wave; independent of Layer 4 implementation track.
- Migration script per `Race_Events_D66_Design_v1.md` §10 — deferred to v5 onboarding implementation PR.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.

---

**End of handoff.**
