# AIDSTATION — Current State

Single rolling-state pointer. Changes on every shipped session. Long-form session narrative lives in `handoffs/`; rolling cross-session items live in `CARRY_FORWARD.md`.

> **Pointer hygiene (2026-05-25):** this file is the *current* pointer, not a narrative archive. The per-session predecessor chain below is a **dated index only** — open the named handoff in `handoffs/` for the full record. Don't paste session narrative back into this file; that's what `handoffs/` is for.

---

## Last shipped session

`handoffs/V5_Implementation_FormRefresh_A1_RaceFormatTaxonomy_DurationAxis_2026_05_25_Closing_Handoff_v1.md` — 2026-05-25 (PR #159 merged; PR #160 the runner + bookkeeping)

FormRefresh A1 — form-feedback slice A, items 1+2. Collapsed `race_format` to a purely **structural** 3-value axis (`single_day`/`continuous_multi_day`/`stage_race`; sport stays on `framework_sport`) and added the **magnitude axis** (`estimated_duration_hr` + `primary_metric` distance/duration selector) on both the profile-edit and onboarding race forms. Orchestrator now prefers the explicit duration over the coarse format-keyed fallback for Layer 2E; validator rule 18 re-derived (`continuous_multi_day` = gi/hydration/mechanical/cumulative_fatigue/sleep_dep; nav/weather off the format axis). Idempotent enum-remap migration; **no `framework_sport` backfill** (format never sourced sport). ~14 substantive files (one-session ceiling break, authorized at gate). 1785 passed/16 skipped. Also shipped `etl/sources/run_owed_layer0_migrations.sql` (PR #160) — one ordered `psql` runner for the owed layer0 deploys. **Owed (Andy's hands):** `python init_db.py` (race_events migration) + the layer0 runner; **manual UI eyeball** of the distance/duration toggle. Full record + decisions in the handoff above.

## Predecessor index (newest first — full record in `handoffs/`)

The three most recent carry live state:

- `V5_Implementation_InjuryFormRefresh_2026_05_25_Closing_Handoff_v1.md` — 2026-05-25 (**PR #158, merged**). Injury-form refresh (feedback #4+#6): dropped the duplicate Side `<select>` (side now derived from `body_part` prefix); folded `wrist extension`→`above-joint-angle` constraint; NEW `athlete.BODY_PART_CONSTRAINTS` + JS narrowing the visible constraint checkboxes. No data migration.
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
- **Owed Neon deploys (Andy's hands — no `DATABASE_URL` in build container).** Two channels: (1) public schema — `python init_db.py` applies the FormRefresh A1 `race_events` migration; (2) layer0 — `psql "$DATABASE_URL" -f etl/sources/run_owed_layer0_migrations.sql` batches PR #156 `primary_movement` (HARD prereq — Layer 2A reads it), K3 equipment, + the D-74 idempotency re-runs in order.
- **Form-feedback slice A — race-event form, remainder** (item 3): items 1+2 (distance-or-duration metric + format/`framework_sport` reconciliation) shipped in FormRefresh A1. Still open: drop aid-stations count + derive fueling cadence from route locales (Layer 2E); mandatory-gear → pack-weight/portage. **Needs its own plan-mode design (Trigger #3).**
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

**1785 green + 16 skipped** (measured 2026-05-25 after FormRefresh A1; baseline this session was 1784 — the 1636 figure predated the InjuryFormRefresh + intervening 2026-05-25 work). Run with `python -m pytest tests/` (deps live under `/usr/local/bin/python`, not the `~/.local/bin/pytest` shim). 12 NL parser smoke + 4 Layer 3 SDK smoke = 16 skipped when `ANTHROPIC_API_KEY` is unset. Per-session test deltas live in each handoff's §4; the older running-baseline chain was trimmed from this pointer 2026-05-25 (recoverable from the handoffs).

---
