# AIDSTATION — Carry Forward

Rolling-state for items spanning multiple sessions. **Edit in place** — don't duplicate this content in handoff narratives. The handoff references this file; doesn't restate it.

---

## Manual §5.0 walkthrough (Vercel)

62 scenarios accumulated. Andy walks after PR merges.

- 12 onboarding (D-66 §H.2 / §H.4)
- 6 nudge UI
- 6 Layer 3B Scope A
- 6 Layer 3B Scope B
- 5 Layer 3B Scope C
- 1 D-72 (locale-FK alignment)
- 7 D-73 Phase 1.2A (Neon schema spot-checks + profile-tab form regression + provenance regression)
- 6 D-73 Phase 1.2B (Neon schema spot-checks for 8 new tables + idempotency + index existence + FK behavior + regression)
- 4 D-73 Phase 1.2C (Neon schema spot-checks for 7 per-discipline §D tables + PK = user_id 1:1 shape + idempotency + regression)
- 2 D-73 Phase 1.3 (`build_layer1_payload(db, andy_user_id)` against Andy's live production row — confirm 24 SELECTs return without error + payload constructs without ValidationError; spot-check `daily_availability_windows` denormalization Sun..Sat against Andy's actual configured days)
- 2 D-73 Phase 2.1 (`q_layer2a_discipline_classifier_payload(db, "Adventure Racing", estimated_race_duration_hours=56, navigation_required=True, etl_version_set=<current plan-gen pin>)` against Andy's PGE 2026 context — confirm `layer0.*` returns 15 AR disciplines + D-008b auto-in + D-013 auto-in + Andy-quality rationale strings render without weirdness; spot-check Triathlon `framework_sport="Triathlon (Standard / Olympic)"` produces the expected swim/bike/run set if the data is loaded)
- 3 D-73 Phase 2.2 (1: re-log Andy's left wrist injury via /injuries/new form — confirm severity-enum select shows the 6 values + injury_type 11-select renders + side defaults to N/A + movement_constraints multi-checkbox lets you tick "Pain with wrist extension" / "Pain with loading" / "Pain with grip / sustained hold" + form saves cleanly with all values persisted into `injury_log` row (Neon SELECT verifies the new columns populated); 2: `q_layer2d_injury_risk_profile_payload(db, [andy_wrist_injury], [], ["D-001","D-005","D-006","D-007","D-008a","D-008b","D-010","D-011","D-013","D-014","D-015","D-016"], etl_version_set=<plan-gen pin>)` against Andy's PGE 2026 included-discipline set — confirm Pushup-class exercises route to `accommodated_exercises` carrying `tempo_modification(heavy_slow_resistance)` per §5.3.6 Tendinopathy / Chronic-Managed default; D-010 Rock Climbing risk ELEVATED with substitute back-check flagging Packrafting `still_at_risk=True` for Wrist; coaching flags include `elevated_discipline_risk` + `discipline_substitution_suggested`; no HITL (Chronic-Managed isn't a §5.7 trigger); 3: edit the injury via /injuries/{id}/edit — confirm injury_type / severity / side / movement_constraints selectors pre-populate from the persisted row + saved edits round-trip cleanly)
- 2 D-73 Phase 2.3 (1: confirm `layer0.terrain_gap_rules` severity reclassification landed via the `_PG_MIGRATIONS` UPDATE on next Neon deploy — `SELECT gap_severity, COUNT(*) FROM layer0.terrain_gap_rules WHERE superseded_at IS NULL GROUP BY gap_severity` should return rows keyed on {low, medium, high, critical, unbridgeable} with zero 'partial' rows; spot-check a representative band — e.g., `SELECT target_terrain_id, proxy_terrain_id, proxy_fidelity, gap_severity FROM layer0.terrain_gap_rules WHERE target_terrain_id='TRN-005' AND etl_version='0C-v2.0-r2'` should show TRN-005 → TRN-004 fidelity 0.60 banded as 'medium', TRN-005 → TRN-001 fidelity 0.40 banded as 'high', TRN-005 → TRN-016 fidelity 0.30 banded as 'critical'; 2: AR baseline 2B call — once §H.2 and §J terrain capture surfaces land per Open Items 2B-3 + 2B-2, run `q_layer2b_terrain_classifier_payload(db, race_terrain=[RaceTerrainEntry('TRN-002', 35.0), RaceTerrainEntry('TRN-003', 30.0), RaceTerrainEntry('TRN-004', 15.0), RaceTerrainEntry('TRN-009', 15.0), RaceTerrainEntry('TRN-016', 5.0)], locale_terrain_ids=['TRN-002','TRN-003','TRN-004','TRN-008','TRN-016'], included_discipline_ids=<PGE 2026 set>, etl_version_set={'0A':...,'0B':...,'0C':'0C-v2.0-r2'})` and confirm Flat Water TRN-009 surfaces as the lone gap with Pool TRN-008 proxy at fidelity 0.75 / severity 'low'; summary.pct_of_race_uncovered == 15.0; coaching_flags == [] for the all-bridgeable case)

See `PR_Verification_Status.md` for the per-PR §5.0 step-by-step state (✅ done / ⏸ blocked / 🟡 owed / ⚪ N/A / 🔴 bug). D-73 Phase 1.2A + 1.2B + 1.2C + 1.3 steps are spelled out in §5 of their closing handoffs.

## Doc-sweep nits

Small drift items to fold into upcoming sessions rather than ship as their own PR.

- `routes/onboarding.py:710` — docstring tense (stale "legacy `athlete_profile.target_event_*`" reference after D-66 Scope B/C). Fold into upstream arc Phase 4 or 5.
- `Layer4_Spec.md` §4.5 — source-pointer wording reflects D-72 obsolescence. Fold into Phase 5.1 orchestrator vertical slice.
- `Race_Events_D66_Design_v1.md` §8.3 — `mode='open_ended'` drift vs canonical `mode='no-event'` (per `Layer3BPayload.mode: Literal["event","no-event"]`). Fold into Phase 4.2 Layer 3B prompt-body session.
- `Layer2A_Spec.md` §5.2 SQL — references `pla.default_inclusion` which doesn't exist on `layer0.phase_load_allocation` (the column isn't in `etl/layer0/schema.sql`). `layer2a/builder.py` derives `default_inclusion` from `notes_conditions` text per spec §5.3 (`*CONDITIONAL`-prefixed → `prompt_required`; else `included`). Fold a spec correction into the next session that touches `Layer2A_Spec.md` (likely Phase 2.4 Layer 2C if cross-spec sweep, or its own ~5-line edit anytime).
- `Layer2A_Spec.md` Open Item 2A-1 — rationale template content review. v1 templates shipped Andy-quality 2026-05-19 (Phase 2.1) per Andy's "don't defer" call; full athlete-facing content review naturally falls out of Phase 5.1 orchestrator vertical slice when race_week_brief surfaces the strings to Andy in production. Mark 2A-1 partial-close.
- `Layer2D_Spec.md` §3 — references "9-value enum" for `InjuryRecord.injury_type`. Canonical count per `Athlete_Onboarding_Data_Spec_v5.md` §B.1.1 (which §3 references) is **11**: Acute soft tissue / Tendinopathy / Joint mechanical non-surgical / Joint mechanical surgical / Bone non-stress / Bone stress fracture / Skin surface / Nerve / Inflammatory / Post-surgical / Other-uncertain. Deployed `injury_log.injury_type` + `athlete.KNOWN_INJURY_TYPES` + `layer4/context.py:InjuryRecord` all use the 11-value enum. Fold the §3 wording fix into the next session that touches `Layer2D_Spec.md` (~1-line edit).
- `Upstream_Implementation_Plan_v1.md` §4 row 2.2 — references `injury_profiles` + `exercise_risk_assessments` as Layer 2D's read tables. Neither exists in `etl/layer0/schema.sql`. Actual reads per `Layer2D_Spec.md` §5.2 + §5.4 + §5.6: `layer0.sport_discipline_bridge` + `sport_exercise_map` + `exercises` + `disciplines` + `discipline_substitutes` + `discipline_training_gaps`. Fold a §4 row 2.2 rewrite (~3-line edit) into the next plan-touching session.
- `HealthConditionRecord.system_category` enum drift — deployed `athlete.KNOWN_SYSTEM_CATEGORIES` is lowercase 8-value ({cardiac, respiratory, metabolic, neurological, gi_immune, musculoskeletal, endocrine, other}); `Athlete_Onboarding_Data_Spec_v5.md` §B.4.1 specs 11 capitalized values (Cardiac / Respiratory / Endocrine-Metabolic split / GI / Neurological / Cognitive-Mental Health / Musculoskeletal-chronic / Skin / Thermoregulation / Immune-Autoimmune / Other). Layer 2D matches the deployed lowercase enum (shared vocab between `KNOWN_SYSTEM_CATEGORIES` and `layer0.exercises.contraindicated_conditions`). Alignment to spec 11-enum is its own onboarding refresh PR — affects `athlete.KNOWN_SYSTEM_CATEGORIES` tuple + `layer4/context.py:HealthConditionRecord.system_category` Literal + `Layer2D_Spec.md` §5.7 rule 2 keying + UI surface. Not blocking Phase 2.3 / 2.4 / 2.5; queue for the §B health condition form refresh.
- `routes/injuries.py:BODY_PARTS` — hardcoded 24 left/right-doubled body parts (Left Hand / Right Hand / Left Wrist / Right Wrist / etc.); canonical `layer0.body_parts` vocab per `Vocabulary_Audit_v2.md` §1 is 41 side-less. Layer 2D Phase 2.2 boundary normalizer `_strip_side()` in `layer2d/builder.py` collapses "Left Wrist" → "Wrist" at the matching seam, so the drift doesn't break verdict logic. Alignment work (replace BODY_PARTS with `layer0.body_parts.canonical_name` query + add a separate side select) belongs in the §B onboarding form refresh PR alongside the system_category alignment.
- `Layer2B_Spec.md` §13.1 — test scenario references "Flat Water (TRN-008)". Canonical deployed vocab per `etl/sources/migrate_terrain_types.sql` is TRN-008 = Pool and TRN-009 = Flat Water (the IDs are swapped vs the spec example). Layer 2B Phase 2.3 tests use the deployed IDs. Fold a §13.1 wording correction (~2-line edit) into the next session that touches `Layer2B_Spec.md`.
- `Layer2B_Spec.md` §7 + §13 — pct unit convention: spec §3 signature uses `pct_of_race: float  # 0.0 – 100.0` and §13 examples use literal percentages ("35%, 30%, ..."), which Phase 2.3 honored by widening `RaceTerrainOutput.pct_of_race` + `Layer2BSummaryBlock.pct_of_race_uncovered` Field constraints from [0, 1] to [0, 100]. `proxy_fidelity` + `worst_fidelity` stay in [0, 1] (fidelity scores, not percentages). No spec edit needed — this is a "pydantic now matches spec literal" alignment, recorded here for the audit trail.
- §H.2 race-terrain capture surface — Open Item 2B-3 (`Layer2B_Spec.md` §12 — `§H.2 Race Terrain Type` must use canonical TRN-xxx IDs at onboarding time) remains open. The Phase 2.3 builder accepts `race_terrain: list[RaceTerrainEntry]` as caller-supplied; the Phase 5 orchestrator + `routes/onboarding.py` Step 3c form must be extended to (a) capture terrain breakdown with TRN-xxx options + percentages, (b) persist them to a yet-to-be-designed `race_events_terrain` table or `race_events.terrain_breakdown JSONB` column. Pair with the §J locale-terrain capture (Open Item 2B-2) into a single §H.2/§J form-refresh PR.
- §J locale-terrain capture surface — Open Item 2B-2 (`Layer2B_Spec.md` §12 — `§J Locale terrain access` must use canonical TRN-xxx IDs as a controlled vocabulary). `locale_profiles` carries free-text + tags today; need a multi-select against `layer0.terrain_types` keyed on `terrain_id`. Same form-refresh PR as 2B-3.

## Orthogonal carry-forwards (Layer 4 implementation track)

Layer 4 Steps 2 + 3 + 4a-4e of 8 COMPLETE. Remaining:

- **Step 4f** `llm_layer4_plan_create` Pattern A orchestration. Closes Layer 4 §14.3.4 Step 4 sub-arc. ~6-8 files. T3 cross-phase Pattern A lands here as a same-shape consumer.
- **Step 5** Cache layer — ✅ Shipped 2026-05-18.
- **Step 6** Pattern A orchestration polish — ✅ Shipped 2026-05-18.
- **Step 7** Live LLM integration — needs `ANTHROPIC_API_KEY`. Env-gated smoke test scaffolding can ship without the key; real call lands later.
- **Step 8** Telemetry tuning — calibrate validator thresholds against measured retry rates once Step 7 lands real data.

## D-66 Layer 3B caller-side rewire (queued)

Orchestrator currently reads `athlete_profile.target_event_*` for Layer 3B's event-mode input. Once the Layer 4 orchestrator is built (none exists yet — `layer4/` is the only runtime code), swap to `load_target_race_event_payload(db, user_id)`. ~3-4 files. Lands as Phase 5.1 of the upstream arc.

## Parallel tracks (independent of upstream arc)

- **D-50** wiring resumption — unblocked by D-58. PR1 scope: `provider_auth.py` helper + first real OAuth flow (COROS recommended) + COROS webhook recording + D-58 connect-step frontend integration.
- **D-52** Catalog Migration Phase 1 — fuzzy-match HITL alias audit.
- **D-54** SQLite collapse — ✅ Resolved 2026-05-16 (PR13).
- **D-55** Garmin onto `provider_auth` — **paused** until Garmin reopens API access.
- **D-57** Research re-evaluation cadence design.
- **D-58–D-61** Onboarding Design Wave — ✅ complete 2026-05-14.
- **D-62** `webhook_events` retention prune — tracked; lands alongside first real webhook handler.

## Tabled (not active)

- **Park-specific tag taxonomy** (PR18 follow-on) — `EQUIPMENT_CATEGORIES` is gym-centric; outdoor_park shared profiles render irrelevant gym checkboxes. Defer until park-locale usage exercises the seam.
- **Layer 4.5 — Joint Session Coordinator spec** — separate file; lands when team-features track activates.
- **Layer 5 spec** — parallel supplemental outputs (nutrition, supplements, 7-day clothing/conditions). Consumes `PlanSession.session_notes` + `cardio_blocks`.

---
