# AIDSTATION — Current State

Single rolling-state pointer. Changes on every shipped session. Long-form session narrative lives in `handoffs/`; rolling cross-session items live in `CARRY_FORWARD.md`.

> **Pointer hygiene (2026-05-25):** this file is the *current* pointer, not a narrative archive. The per-session predecessor chain below is a **dated index only** — open the named handoff in `handoffs/` for the full record. Don't paste session narrative back into this file; that's what `handoffs/` is for.

---

## Last shipped session

`handoffs/V5_Implementation_InjuryFormRefresh_2026_05_25_Closing_Handoff_v1.md` — 2026-05-25 (PR #158, merged)

Injury-form refresh (slice B of the form-feedback batch — picked over slices A/C because PR #156's `primary_movement` migration stays parked). Bundled feedback **#4 + #6**: (a) **dropped the Side `<select>`** from `templates/injuries/form.html` — it duplicated the Left/Right already in `body_part`; `routes/injuries.py:_save` now **derives `injury_log.side` from the `body_part` prefix** (Layer 2D still reads `InjuryRecord.side`, unchanged); (b) **folded** `"Pain with wrist extension"` into `"Pain above specific joint angle"` (`athlete.KNOWN_MOVEMENT_CONSTRAINTS` 11→10; the `wrist extension`/`palm-down` keyword bundle rides on the fold target in `layer2d/builder.py` so exercise matching is preserved; pydantic `InjuryRecord` enum in `layer4/context.py` trimmed); (c) NEW `athlete.BODY_PART_CONSTRAINTS` (16 side-less parts → relevant subset; `Other`=catch-all) + CSP-nonced JS narrows the visible constraint checkboxes to the selected body part, **keeping already-checked ones visible** (no silent data loss). Replaced the internal-jargon help text with athlete-facing copy. Specs: `Layer2D_Spec.md` §3/§5.3.3/§5.3.6/§13.1 + `Athlete_Onboarding_Data_Spec_v5.md` §B.3 (dated in-place amendment). Tests: NEW `tests/test_injury_form_constraints.py` (7) + fixture flips in `test_layer2d`/`test_layer1_builder`/`test_layer3a_builder`; **123 passed** on the affected suites. Decisions ratified at AskUserQuestion gates: Path A (drop Side), fold-vocab, bundle #4+#6, mapping-as-drafted, **no data migration** (Andy re-logs the existing wrist injury). Over the 5-file ceiling, authorized. **No deploy owed** beyond the standing PR #156 Neon migration; **manual UI eyeball owed** (no sandbox runtime). Rule #9 sweep on entry: clean (the 2 `verify-handoff.sh` ❌ are script artifacts — deleted modality suite + mis-parsed `v10/v11` shorthand).

## Predecessor index (newest first — full record in `handoffs/`)

The three most recent carry live state:

- `V5_Implementation_Layer2E_SpecSweep_UpstreamSourced_2026_05_25_Closing_Handoff_v1.md` — 2026-05-25. Layer 2E spec sweep (doc-only, in-place amend) reconciling §5.3.3/§5.4.3 narrative with the PR #156 as-built upstream-sourced classification; D-26 `supplement_vocabulary` "hard blocker" claim corrected across §6.1/§12/§14.
- `V5_Implementation_Layer2E_UpstreamSourced_PrimaryMovement_2026_05_25_Closing_Handoff_v1.md` — 2026-05-25 (**PR #156, shipped**). Sourced Layer 2E classification from upstream `layer0.disciplines` (`primary_movement TEXT` + `discipline_category`), deleting the drifted hand-maintained dicts. **⚠ OWED-DEPLOY (Andy's hands):** `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` must run on Neon BEFORE deploy — Layer 2A `SELECT`s `dl.primary_movement` (HARD prerequisite). This is the architect-recommended next forward move.
- `V5_Implementation_D74_D75_Cleanup_VersionSort_PopulateIdempotency_2026_05_25_Closing_Handoff_v1.md` — 2026-05-25. D-75 numeric ETL-version max (in-code, no deploy); D-74 DELETE-by-version idempotency added to 3 `etl/sources/` populate scripts (**owed-deploy** on next Neon run); D-76 opened + resolved (deleted the divergent `migrations/` terrain_gap_rules copy).

Older chain (dated index; topic is in the filename):

- 2026-05-24 — `V5_Implementation_D73_Phase_5_2_Walkthrough_BM1_D008b_RaceCraftAware_…`, `…_BM3_PromptBodyIntegration_…`, `…_BestFitModalityImpl_…`, `…_BestFitModalitySpec_…`, `…_SkillCaptureSurface_…`, `…_BucketC_l_SkillCapabilityToggles_…`, `…_BucketC_g_TerrainEquipmentMerge_…`, `…_BucketC_i_MapboxRequired_…`, `…_BucketE_B2_C1_…`, `…_WaterVocabExpansion_…`, `…_TerrainVocabAuditClosure_…`, `…_RouteLocalesAnchorFlags_…`, `…_ETLTerrainVocabDriftFix_…`
- 2026-05-23 — `…_RouteLocalesValidatorHotfix_PR129Validation_…`, `…_BucketE_TerrainNone_FrameworkSport_…`, `…_BucketB_500sBugfixes_…`
- 2026-05-21 — `…_V1CoachingRetire_…`, `…_RaceLocaleMapbox_…`, `…_PunchList_…`, `…_Layer3_Caching_…`, `…_Layer2C_Telemetry_…`, `…_TriggeredByAdHoc_…`, `…_FreqCaps_…`, `…_LogThis_T1Hook_…`, `…_Dashboard_CTAs_…`, `…_CallerSide_D64_Runtime_…`, `…_CallerSide_D64_NLParser_Prompt_…`, `…_CallerSide_D63_PlanCreate_Routes_…`
- 2026-05-20 — `…_CallerSide_PlanSessions_Substrate_…`, `…_PlanCreate_Orchestrator_…`, `…_PlanRefresh_Orchestrator_…`, `…_SingleSession_Orchestrator_…`, `…_FormRefresh_C_Locale_Loosen_…`, `…_FormRefresh_B_Onboarding_…`, `…_FormRefresh_A_RaceTerrain_…`, `…_Phase_5_1_Orchestrator_…`, `…_Layer4_Step7_SDK_Smoke_…`, `…_Phase_4_Layer3B_Driver_…`, `…_Phase_3_1_Driver_…`, `…_Phase_3_1_Substrate_…`, `…_Doc_Sweep_…`
- Earlier — `V5_Implementation_D73_Phase_2_4_Closing_Handoff_v1.md`, `…_Phase_2_4_Prep_…`, `…_Phase_2_5_…` (Layer 2C/2E vertical slices). Pre-D-73 PR1–PR19 + Layer 0–4 spec/design arc: see `handoffs/` + `Project_Backlog_v62.md` revision header.

## Current focus

Two arcs closed earlier on 2026-05-25 and have **no remaining build slices**: the **best-fit training re-model** (Slice 6 retired the v2 `Layer2ModalityPayload` resolver; `resolve_training_substitution` in `layer2_modality/substitution.py` is the sole best-fit node, threaded into race_week_brief + plan_create + plan_refresh with cache slots) and the **R6 discipline-ID renumber + the two craft collapses** (kayak D-008a/b → "Kayaking"; mountain-running D-022/D-023 → "Mountain Running"; shipped & deployed PR #154). Then **D-74/D-75 cleanup + D-76 resolution** and the **injury-form refresh (PR #158, above)**.

**Open next moves (Andy's pick; cross-layer items gate on a plan-mode design per Trigger #3):**
- **PR #156 Neon migration + deploy** — the architect-recommended forward move; HARD prerequisite, Andy's hands (no `DATABASE_URL` in the build container). See predecessor index above.
- **Owed Neon deploys** — D-74 populate-script DELETE-prefix idempotency; K3 equipment ETL.
- **Form-feedback slice A — race-event form** (items 1+2+3): distance-or-duration metric + format/`framework_sport` reconciliation; drop aid-stations count + derive fueling cadence from route locales (Layer 2E); mandatory-gear → pack-weight/portage. Multiple new/changed `race_events` columns + Layer 2A/2C/2E plumbing; likely splits. **Needs its own plan-mode design.**
- **Form-feedback slice C — schedule inference** (item 5): infer long-session + rest days instead of asking; changes Layer 1 derivation. **Needs its own plan-mode design.**
- **Spec narrative sweep** — per-layer specs still cite old discipline ids in prose (post-R6 prose drift).
- **Manual §5.0 real-LLM walk** — accumulated scenarios in `CARRY_FORWARD.md`.

Orthogonal alternatives + the manual §5.0 walkthrough backlog tracked in `CARRY_FORWARD.md`.

## Layer status

| Layer | Status |
|---|---|
| **0** | DEPLOYED |
| **1** | 🟢 v1 spec + typed payload + runtime builder shipped 2026-05-19 (D-51 design wave + Phase 1.2 schema arc + Phase 1.3 builder); 🟢 injury_log §B.1/§B.1.1/§B.3 extensions shipped 2026-05-19 (Phase 2.2 paired) |
| **2** | 🟢 All 5 of 5 runtimes shipped — 2A + 2D + 2B + 2E (Phase 2.1 + 2.2 + 2.3 + 2.5, 2026-05-19) + 2C (Phase 2.4-Prep substrate 2026-05-19 + Phase 2.4 builder 2026-05-20); 2E ships vertical-slice (§5.5 supplements + §5.8 heat acclim stubbed pending §I.1 refresh + Plan Management spec); 🟢 **2B per-discipline terrain gaps shipped 2026-05-25** (best-fit re-model Slice 4 — additive `Layer2BPayload.terrain_by_discipline` consuming `RaceTerrainEntry.discipline_id`; flat aggregate unchanged); 🟢 **training-substitution resolver is the sole best-fit node as of 2026-05-25** (re-model Slice 5 shipped `resolve_training_substitution` in `layer2_modality/substitution.py` consuming the 2B blocks → `TrainingSubstitutionPayload`, db-less; **Slice 6 retired the v2 `Layer2ModalityPayload` resolver entirely** — `layer2_modality/resolver.py` + `_MODALITY_OPTIONS_PER_DISCIPLINE` deleted) |
| **3** | 🟢 3A + 3B complete + cached wrappers wired at orchestrator (3A substrate + driver shipped 2026-05-20; 3B driver shipped same-day Phase 4 2026-05-20; 3A + 3B cached wrappers wired into orchestrator at 4 entry points + extended `_EVICTION_POLICY` 2026-05-21 Phase 5.2 Layer 3 caching slice). 3C + 3D + 3.5 designed, not yet implemented |
| **3.5** | Designed; not yet implemented |
| **4** | SPEC COMPLETE §§1-14; Implementation Steps 2 + 3 + 4a-4f + Step 7 SDK smoke + Phase 5.1 (race_week_brief) + Phase 5.2 slices 1–3 (single_session + plan_refresh T1/T2/T3 + plan_create Pattern A) + caller-side substrate (`plan_sessions` + repo) + caller-side D-63/plan-create/D-64 Flask routes (`routes/ad_hoc_workouts.py`, `routes/plan_create.py`, `routes/plan_refresh.py` + NL parser runtime/prompt) + dashboard CTAs + log-this/T1 hook + refresh frequency caps. **All 4 of 4 entry points wired; all 3 of 3 caller-side routes E2E-reachable, dashboard-surfaced, and cost-gated by per-tier caps. Best-fit re-model COMPLETE (Slice 6, 2026-05-25)** — `training_substitution_payload` threaded into race_week_brief + plan_create + plan_refresh (T1/T2/T3) with a `training_substitution_hash` cache slot per key; single_session intentionally carries no best-fit section (no Layer 2B in its cone) |
| **5** | Not yet specced |

## D-73 upstream implementation arc

Multi-session plan in `Upstream_Implementation_Plan_v1.md`. **Arc complete through Phase 5.2** — Phase 1 (Layer 1 design + schema + builder) → Phase 2 (all 5 Layer 2 runtimes) → Phase 3/4 (Layer 3A + 3B substrate + drivers) → Phase 5.1 (race_week_brief orchestrator + form-refresh A/B/C closing Layer2B_Spec §12 Open Items 2B-2/2B-3) → Phase 5.2 (single_session + plan_refresh + plan_create orchestrators; all 4 Layer 4 entry points wired; caller-side routes + dashboard CTAs + log-this/T1 hook + frequency caps). Per-phase detail lives in the dated predecessor index above. Remaining D-73 follow-ons: Phase 2.5 de-stubs (§I.1 structured-supplement form refresh + Plan Management spec) and the Phase 4 L3B-P-2 §H.2 deployed-shape gap.

**Forcing function:** Andy's PGE 2026 (2026-07-17). `race_week_brief` auto-fires 2026-07-03 (days_to_event = 14). ~7 weeks of runway from 2026-05-25.

## Tests

**1636 green + 16 skipped** (last measured 2026-05-25 after D-74/D-75 cleanup — 1630 post-R6 baseline + 6 new `TestMaxEtlVersion` cases). Run with `python -m pytest tests/` (deps live under `/usr/local/bin/python`, not the `~/.local/bin/pytest` shim). 12 NL parser smoke + 4 Layer 3 SDK smoke = 16 skipped when `ANTHROPIC_API_KEY` is unset. Per-session test deltas live in each handoff's §4; the older running-baseline chain was trimmed from this pointer 2026-05-25 (recoverable from the handoffs).

---
