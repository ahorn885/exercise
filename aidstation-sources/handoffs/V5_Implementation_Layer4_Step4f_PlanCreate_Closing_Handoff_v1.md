# V5 Implementation — Layer 4 Step 4f `llm_layer4_plan_create` Pattern A Closing Handoff

**Session:** Single chat. Scope: Layer 4 Step 4f — `llm_layer4_plan_create` Pattern A orchestration + T3 cross-phase wiring (closes the `tier_t3_cross_phase_requires_pattern_a` placeholder raise from Step 4d). Paired prompt body v2 amendments: `Layer4_PerPhase_v1.md` → `_v2.md` (D1 typed IntensityTarget + PR-C-followon 2D injury source + D-66 RaceEventPayload integration) + `Layer4_SeamReviewer_v1.md` → `_v2.md` (PR-C-followon 2D injury source). Paired `Layer4_Spec.md` amendments: §3.2 plan_start_date row update; §4.3 row 9 tier_t3_cross_phase_requires_pattern_a flipped to ✅ Step 4f closed; §5.2 + §6.3 "Implementation status (2026-05-18): ✅ Step 4f shipped" blocks added.

**Date:** 2026-05-18

**Predecessor handoff:** `V5_Implementation_Layer4_Step4e_RaceWeekBrief_Closing_Handoff_v1.md` (Step 4e shipped 2026-05-18 earlier same day; commit `85ad4d7` on origin/main via PR #78).

**Branch:** `claude/race-week-brief-closing-GsPcB` (harness-pinned for this session — name carried over from the harness even though this session is Step 4f implementation; precedent: harness names mismatched with scope across PR-A → Step 4a → Step 4b/c → Step 4d → D-66 design wave → Step 4e → Step 4f).

**Status:** 🟢 3 new code modules + 1 modified driver + 1 modified __init__ + 1 new test + 1 modified test + 2 new prompt body v2 + 1 modified spec + 3 bookkeeping = 13 files. Combined `tests/` 501 → 547 net new in 0.61s. **Layer 4 Step 4 sub-arc COMPLETE — all 4 entry points integrated end-to-end (4a + 4b/c + 4d + 4e + 4f).**

---

## 1. Session-start verification (Rule #9)

Verified at session start before any edits:

| Claim | Anchor | Result |
|---|---|---|
| Step 4e shipped on `main` per Step 4e handoff | `git log --oneline -10` | ✅ commits `85ad4d7` (merge PR #78) + `a6388a2` |
| `layer4/race_week_brief.py` exists (~1737 lines) | `wc -l` | ✅ |
| `RaceEventPayload` in `layer4/context.py` | grep | ✅ at line 923 |
| `Layer3BPayload` event-metadata fields | grep | ✅ |
| `KitItem.layer0_canonical` field | grep | ✅ |
| Combined `tests/` 501 green | `python -m pytest tests/ -q` | ✅ 501 passed in 1.14s |
| Working tree clean on `claude/race-week-brief-closing-GsPcB` | `git status` | ✅ |
| `Project_Backlog_v49.md` exists | `ls` | ✅ |

**No drift found.**

---

## 2. Session narrative — Step 4f Pattern A orchestration (Andy 2026-05-18)

Andy opened with the URL to the Step 4e closing handoff + "let's work." I followed the operating model — read CLAUDE.md fully (Rule #13 first re-read, via system context), ran Rule #9 verification, surfaced state + scope.

### 2.1 Scope pick

**Round 1 (2026-05-18, 1-question):** session scope. Andy picked **Step 4f plan_create Pattern A** (architect-recommended next forward move per the Step 4e handoff §4).

### 2.2 Architectural choices — 4-question AskUserQuestion gate

During the load-bearing-file re-read (Rule #13: CLAUDE.md fully + Step 4e handoff + `Layer4_Spec.md` §5.2 + §6.1/§6.2/§6.3 + `Layer4_PerPhase_v1.md` + `Layer4_SeamReviewer_v1.md` + `layer4/phase_structure.py` + `layer4/single_session.py` analog + `layer4/plan_refresh.py` T3 raise location), surfaced 4 architectural decisions per Step 4a/4b/c/4d/4e precedent:

1. **Step 4f scope**: plan_create alone vs **plan_create + T3 cross-phase wiring**. **Andy picked plan_create + T3 cross-phase** (closes the Layer 4 Step 4 sub-arc completely; closes the `tier_t3_cross_phase_requires_pattern_a` raise from Step 4d).
2. **Module layout**: monolithic plan_create.py (single_session.py precedent) vs **Split into per_phase.py + seam_review.py + plan_create.py**. **Andy picked Split** — clean separation maps to spec §5.2 boundaries; T3 cross-phase reuse natural via shared engine.
3. **Prompt body amendments**: keep v1 + driver-folds-flatly vs PerPhase v2 only vs **Both v1 → v2 surgical amendments**. **Andy picked Both v2** (Trigger #2 PerPhase + SeamReviewer per the PR-C-followon 2D injury source ripple + Step 4e D-66 RaceEventPayload ripple + Step 4a D1 typed IntensityTarget ripple).
4. **File ceiling break**: trim to fit vs **Yes break (~10-13 files projected)**. **Andy picked break** — precedented across Step 4d 13 + Step 4b/c 10 + Step 4e 10 + Step 4a 8.

### 2.3 Implementation order

1. NEW `layer4/per_phase.py` (~900 lines) — per-phase synthesis loop module.
2. NEW `layer4/seam_review.py` (~500 lines) — seam-reviewer LLM call module.
3. NEW `layer4/plan_create.py` (~800 lines) — Pattern A orchestrator + shared engine for T3 cross-phase.
4. Modified `layer4/plan_refresh.py` — drop the `tier_t3_cross_phase_requires_pattern_a` raise + add `_route_t3_cross_phase_to_pattern_a()` helper + add `phase_caller`/`seam_caller` kwargs for test injection.
5. Modified `layer4/__init__.py` — 6 new re-exports.
6. NEW `tests/test_layer4_plan_create.py` — 46 tests.
7. Modified `tests/test_layer4_plan_refresh.py` — replaced `test_t3_cross_phase_raises_pattern_a` with `test_t3_cross_phase_routes_to_pattern_a` happy-path test.
8. NEW `aidstation-sources/prompts/Layer4_PerPhase_v2.md` + `Layer4_SeamReviewer_v2.md` (Rule #12; v1 retained).
9. Modified `Layer4_Spec.md` — §3.2 plan_start_date row + §4.3 row 9 + §5.2 + §6.3 implementation-status blocks.
10. Bookkeeping: CLAUDE.md + Project_Backlog_v49 → v50 + this handoff.

### 2.4 Architectural choices on the record

- **Three-module split** (per_phase + seam_review + plan_create) — per_phase + seam_review are reusable building blocks consumed by both `llm_layer4_plan_create` AND `plan_refresh.py`'s T3 cross-phase delegation. Clean separation matches spec §5.2 surface boundaries.
- **Per-phase retry budget shared across validator-driven AND seam-driven re-syntheses** per §5.5 + §6.2 — `synthesize_phase()` accepts `retries_already_used` kwarg propagating the running counter across the seam-driven trigger boundary; orchestrator tracks per-phase counter in `retries_used_per_phase: dict[int, int]`.
- **Per-seam iteration cap = 2** per §6.2 — iter-1 review → on flagged_major/patched + re_prompt_*: re-synth target + iter-2 review exactly once; if iter-2 still flags, emit `seam_unresolved` Observation.
- **Validator scope per-phase** — `synthesize_phase()` builds per-phase Layer4Payload (single phase's sessions + full phase_structure + empty seam_reviews) and runs `validate_layer4_payload()`; rules whose required upstream payload is None no-op silently per validator's missing-input policy. Final cross-phase validator pass runs on union of all sessions per §5.2 step 5.
- **Seam reviews on adjacent pairs WHERE AT LEAST ONE side was synthesized** per §6.3 — seams between two unaffected phases (T3 cross-phase edge case) are NOT re-reviewed since they were reviewed during the original plan_create.
- **`phase_metadata` filled by orchestrator from PhaseSpec** via `_build_session_phase_metadata()` — `week_in_phase` 1-indexed, clamped to `[1, phase.weeks]` defensively; validator's `phase_date_out_of_range_*` rule catches out-of-window dates separately.
- **Race-event `RaceEventPayload` optional kwarg** — open-ended plans pass None; event-mode plans pass the typed payload from D-66 design wave; per-phase prompt suppresses `race_pace_specific` flag when None.
- **Seam reviewer invalid verdict-direction combos** surface as `Layer4OutputError('seam_reviewer_invalid_verdict_combination')` (no auto-retry at orchestrator level v1 — re-runs unlikely to resolve at $0.06+/call).
- **T3 cross-phase delegate signature**: `plan_refresh.py:_route_t3_cross_phase_to_pattern_a()` identifies phase indices overlapping `[refresh_scope_start, refresh_scope_end]`, buckets `prior_plan_session_window` sessions into non-synthesized phases as carryover, and calls `synthesize_pattern_a_for_refresh()` shared engine.
- **`coaching_flags` enum for per-phase is closed 6-flag** (technique_emphasis / long_slow_distance / weak_link_targeted / overreach_test / discipline_specific_intensity / race_pace_specific). `intensity_modulated` excluded — that flag fires on refresh/single-session paths per §8.6/§8.7, not plan_create where there's no athlete-intent surface to deviate from. Spec-auto flags (recovery_week / peak_volume_marker / race_rehearsal / fueling_practice / kit_check / pacing_lock / pre_race_taper) are orchestrator-stamped post-synthesis per §8.1; never in this enum.

### 2.5 Stop-and-ask triggers — #2 + #8 fired

- **Trigger #2 (prompt body amendments):** fired and routed via AskUserQuestion gate × 2 — Andy picked Both PerPhase v2 + SeamReviewer v2 surgical amendments. v1 retained per Rule #12.
- **Trigger #8 (architectural alternatives):** fired and routed × 4 questions — scope, module layout, prompt bodies, file ceiling.
- **Trigger #5 (schema/inter-layer-contract amendments):** did NOT fire substantively. `Layer4_Spec.md` amendments are surgical implementation-status flips (forward-pointer → "✅ shipped"), not new contract surface.
- **Trigger #11 (new D-rows):** did NOT fire — no new D-rows.

---

## 3. Spec amendments paired this session

### 3.1 `Layer4_Spec.md`

- **§3.2 parameter table `plan_start_date` row** — updated note from "raises `tier_t3_cross_phase_requires_pattern_a` until Step 4f lands" to "**Step 4f shipped 2026-05-18 delegates to `layer4/plan_create.py:synthesize_pattern_a_for_refresh()`**".
- **§4.3 row 9 `tier_t3_cross_phase_requires_pattern_a`** — flipped from "raises this error until Step 4f lands" to "**Step 4f closed the placeholder 2026-05-18**: cross-phase T3 now delegates to `layer4/plan_create.py:synthesize_pattern_a_for_refresh()` shared engine"; code reserved for future re-use.
- **§5.2 Pattern A** — NEW "Implementation status (2026-05-18): ✅ Step 4f shipped" block describing module layout (per_phase.py + seam_review.py + plan_create.py thin orchestration) + prompt body v2 amendments + handoff reference.
- **§6.3 Single-phase T3 special case** — NEW "Implementation status (2026-05-18): ✅ Step 4f shipped" block describing T3 cross-phase delegate routing via `_route_t3_cross_phase_to_pattern_a()` helper.

### 3.2 `Layer4_PerPhase_v1.md` → `_v2.md` (per Rule #12)

Surgical amendment document. v1 retained as in-project history. v2 changes:

- File header v2 status block.
- v2 source decisions D11-D16 (delta from v1's D1-D10): D11 tool-schema fidelity re-affirmed; D12 typed IntensityTarget 9-shape oneOf per D1 amendment; D13 active_injury_summary source corrected to 2D excluded + accommodated per PR-C-followon (v1 referenced non-existent 3A field); D14 D-66 RaceEventPayload integration replacing scalar race_format/event_date/event_locale; D15 + D16 phase_synthesis_notes JSONB + orchestrator phase_metadata fill clarified.
- §3.3 input contract amendment (2D-sourced active_injury_summary + new accommodation_modalities row per PR-C-followon).
- §3.4 input contract amendment (race_event_payload replacing scalars + route_locales structured graph row per D-66).
- §4.1 tool schema oneOf surfaced (D1 amendment fidelity).
- §4.2 coaching_flags closed 6-set confirmed (intensity_modulated explicitly excluded for plan_create per §8.6/§8.7).
- System prompt + §6 user-prompt template structure + §5 voice + §7 sampling unchanged from v1.

### 3.3 `Layer4_SeamReviewer_v1.md` → `_v2.md` (per Rule #12)

Surgical amendment document. v1 retained. v2 changes:

- File header v2 status block.
- v2 source decision D8 (delta from v1's D1-D7): active_injury_summary source corrected to 2D excluded + accommodated per PR-C-followon.
- §3 input contract amendment.
- Renderer surfaces compact 1-line-per-injury summary via `seam_review._format_active_injury_summary()`.
- System prompt + §4 tool schema + §6 user-prompt template + §7 sampling unchanged.

### 3.4 `Project_Backlog_v49.md` → `_v50.md` (per Rule #12)

File-revision-header bumped to v50 with full Step 4f narrative. v49 demoted to predecessor.

### 3.5 `CLAUDE.md`

- Last-shipped-session narrative replaced with Step 4f block; Step 4e demoted to predecessor (compressed).
- Backlog ref v49 → v50.

---

## 4. Next session pointers

### 4.1 Architect-recommended next forward moves

**Layer 4 Step 4 sub-arc COMPLETE.** All 4 entry points integrated end-to-end:
- 4a `llm_layer4_single_session_synthesize` (D-63 caller, Pattern B) — shipped 2026-05-17
- 4b/c `llm_layer4_plan_refresh` T1+T2 (D-64 caller, Pattern B) — shipped 2026-05-17
- 4d `llm_layer4_plan_refresh` T3 intra-phase (Pattern B) — shipped 2026-05-17
- 4e `llm_layer4_race_week_brief` (D-66 caller, Pattern B) — shipped 2026-05-18
- 4f `llm_layer4_plan_create` (Pattern A) + T3 cross-phase delegate — shipped 2026-05-18 this session

**Architect-recommended next:**

1. **Step 5 cache layer** per `Layer4_Spec.md` §14.3.4 sequencing — orchestrator-side per-entry-point cache hit/miss + `plan_versions` rebinding semantics + first concrete consumers for the §9.1 cache-key helpers shipped in PR-B. Cleanly buildable now since all 4 entry points are integrated. ~6-8 files projected.

2. **v5 onboarding implementation PR** — substantial UI + DB work per `Athlete_Onboarding_Data_Spec_v5.md` (consolidated §H.2 + §H.3 + §H.4 with the D-66 race-events surface added; D-58/59/60/61 onboarding flow + `/profile?tab=race-events` tab). Independent of Layer 4 implementation. Can run in parallel.

3. **Step 6 Pattern A orchestration polish** per §14.3.4 — concurrency for non-overlapping seam reviews (§5.2 closing note); telemetry on verdict distribution + retry rates + cost/call.

4. **Step 7 live LLM integration** — first end-to-end test against real Anthropic API for a single entry point (single_session is the cheapest to validate; ~$0.075/call) before bulk testing the rest.

5. **D-50 wiring resumption** — independent track unblocked by D-58.

### 4.2 Stop-and-ask risk for next session

Depends on which next-forward-move is picked. Step 5 (cache layer) is most likely Trigger #5 risk — touches `plan_versions` schema invalidation + orchestrator boundary contract.

### 4.3 Operating notes for next session

1. **First re-read** (Rule #13): `aidstation-sources/CLAUDE.md` fully.
2. **Second re-read**: this handoff.
3. **Third re-read**: depends on scope.
4. **Branch**: cut fresh off post-merge `main` OR stay on the harness pin (precedent).
5. **Test convention**: top-level `tests/test_layer4_<feature>.py`.

---

## 5. Open items / decisions pinned this session

### 5.1 Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Scope = plan_create + T3 cross-phase wiring | Andy 2026-05-18 | Closes Layer 4 Step 4 sub-arc completely; closes the Step 4d placeholder raise; precedented file ceiling. |
| 2 | Module layout = Split into per_phase.py + seam_review.py + plan_create.py | Andy 2026-05-18 | Clean separation matches spec §5.2 boundaries; T3 cross-phase reuse natural via shared engine. |
| 3 | Prompt bodies = Both v1 → v2 surgical amendments | Andy 2026-05-18 | Trigger #2 fidelity for PR-C-followon 2D injury source + D-66 RaceEventPayload + D1 typed IntensityTarget ripple. Step 4a precedent. |
| 4 | File ceiling = break (13 files projected) | Andy 2026-05-18 | Precedented across Step 4d 13 + Step 4b/c 10 + Step 4e 10 + PR-A 8 + Step 4a 8. |
| 5 | Validator scope per-phase via per-phase Layer4Payload + final cross-phase pass | Architect-pick | Spec §5.2 step 4 (per-phase validator) + step 5 (final cross-phase) maps cleanly to two distinct validator invocations. |
| 6 | Per-phase retry budget shared across validator + seam-driven re-syntheses | Architect-pick (per §5.5 + §6.2) | Spec mandates shared counter; `synthesize_phase()` accepts `retries_already_used` kwarg for the seam-driven trigger boundary. |
| 7 | Seam reviewer invalid verdict-direction combos raise without auto-retry | Architect-pick | $0.06+/call cost makes re-run unlikely to resolve; orchestrator surfaces to caller per §5.5 schema-violation policy. |
| 8 | coaching_flags enum for per-phase = closed 6-flag (intensity_modulated excluded) | Architect-pick (per §8.6/§8.7 + v1 prompt body D5) | plan_create has no athlete-intent surface to deviate from; intensity_modulated fires on refresh/single-session paths. |

### 5.2 No carry-forward expected for next session

Step 4f is fully self-contained; everything paired with the implementation shipped this session.

### 5.3 Carried forward — Layer 1 typed payload

Still deferred. `Layer1Payload` is `dict[str, Any]` opaque pass-through across all entry points (including plan_create). Lands as typed pydantic model when Layer 1 implementation arc begins.

### 5.4 Carried forward — DDL migrations + onboarding/profile UI

`race_events` + `race_route_locales` + `race_route_locale_equipment` DDL (D-66 §3 + §10) deferred to v5 onboarding implementation PR. The Step 4f implementation works against the typed payloads; orchestrator joins from the DB tables when they ship.

---

## 6. Session-end verification (Rule #10)

Final pass before composing this handoff:

| Check | Result |
|---|---|
| `layer4/per_phase.py` exists (~900 lines) | ✅ inspection |
| `layer4/seam_review.py` exists (~500 lines) | ✅ inspection |
| `layer4/plan_create.py` exists (~800 lines) | ✅ inspection |
| `synthesize_phase()` + `synthesize_pattern_a_for_refresh()` + `llm_layer4_plan_create()` callable | ✅ smoke test |
| `tier_t3_cross_phase_requires_pattern_a` raise replaced with delegate | ✅ grep + test_t3_cross_phase_routes_to_pattern_a passes |
| `layer4/__init__.py` re-exports 6 new symbols | ✅ inspection |
| `tests/test_layer4_plan_create.py` exists with 46 tests | ✅ inspection |
| `tests/test_layer4_plan_refresh.py` T3 cross-phase test rewritten | ✅ grep |
| Combined `tests/` 547 green | `python -m pytest tests/ -q` | ✅ 547 passed in 0.61s |
| `Layer4_Spec.md` §3.2 plan_start_date row updated | ✅ grep |
| `Layer4_Spec.md` §4.3 row 9 flipped | ✅ grep |
| `Layer4_Spec.md` §5.2 implementation-status block added | ✅ grep "Step 4f shipped" |
| `Layer4_Spec.md` §6.3 implementation-status block added | ✅ grep "_route_t3_cross_phase_to_pattern_a" |
| `Layer4_PerPhase_v2.md` exists; v1 retained | ✅ ls |
| `Layer4_SeamReviewer_v2.md` exists; v1 retained | ✅ ls |
| `Project_Backlog_v50.md` exists | ✅ ls |
| `Project_Backlog_v50.md` file-revision-header bumped to v50 | ✅ grep line 5 |
| `CLAUDE.md` Backlog ref reads `Project_Backlog_v50.md` | ✅ grep |
| `CLAUDE.md` Last-shipped-session is Step 4f; Step 4e demoted | ✅ inspection |
| Branch is `claude/race-week-brief-closing-GsPcB` (harness-pinned) | ✅ |

---

## 7. Files shipped this session

One commit (or multiple bundled) on `claude/race-week-brief-closing-GsPcB`:

**Substantive code + tests + spec + prompt (10 files):**
1. New `layer4/per_phase.py` (~900 lines)
2. New `layer4/seam_review.py` (~500 lines)
3. New `layer4/plan_create.py` (~800 lines)
4. Modified `layer4/plan_refresh.py` (drop raise + add `_route_t3_cross_phase_to_pattern_a()` helper + phase_caller/seam_caller kwargs)
5. Modified `layer4/__init__.py` (6 new re-exports)
6. New `tests/test_layer4_plan_create.py` (46 tests)
7. Modified `tests/test_layer4_plan_refresh.py` (T3 cross-phase test rewritten as happy-path)
8. Modified `aidstation-sources/Layer4_Spec.md` (§3.2 + §4.3 + §5.2 + §6.3 implementation-status blocks)
9. New `aidstation-sources/prompts/Layer4_PerPhase_v2.md` (surgical amendment; v1 retained)
10. New `aidstation-sources/prompts/Layer4_SeamReviewer_v2.md` (surgical amendment; v1 retained)

**Bookkeeping (3 files):**
11. New `aidstation-sources/Project_Backlog_v50.md` (per Rule #12; v49 retained as predecessor)
12. Modified `aidstation-sources/CLAUDE.md`
13. New `aidstation-sources/handoffs/V5_Implementation_Layer4_Step4f_PlanCreate_Closing_Handoff_v1.md` (this file)

**13 files total. Over the 5-file ceiling intentionally** — Andy confirmed at session start via AskUserQuestion question #4; precedented across Step 4d 13 + Step 4b/c 10 + Step 4e 10 + PR-A 8 + Step 4a 8 + PR-C-followon 6 + PR-D 6 + PR-E 6 + D-66 design wave 6.

---

## 8. Carry-forward from prior PRs (informational)

- PR17 §5.0 `routes/body.py` `/body` POST round-trip on Vercel — passed in earlier session; not actioned this session.
- PR15 `/profile?tab=schedule` round-trip — status not confirmed; carry-forward.
- v5 onboarding implementation PR — consumes §H.2 + §H.4 + §A.1 extensions per D-66 design wave; independent of Layer 4 implementation track.
- Migration script per `Race_Events_D66_Design_v1.md` §10 — deferred to v5 onboarding implementation PR.
- D-50 wiring resumption — unblocked by D-58; can run in parallel.
- **Step 5 cache layer** — architect-recommended next forward move per §14.3.4 sequencing.

---

**End of handoff.**
