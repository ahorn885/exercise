# Batch C Done → 2D Kickoff Handoff

**Date:** 2026-05-10 (long session)
**Predecessor:** `Batch_B_Done_Batch_C_Kickoff_Handoff.md`
**Status:** Batch C shipped to prod. Per-node spec framework established. 2A, 2B, 2C specs all exist at the depth standard. Control Spec drafted. Project Backlog established and populated.
**Next session starts with:** Layer 2D — Injury Risk Profile (design from scratch at full depth)

---

## TL;DR

This session split into two phases:

**Phase 1 — Batch C ship.** Spec drift sweep introspection executed, v2 drift report produced (after Andy correctly pushed back on a sloppy v1), Batch C migration deployed (10 exercises curated to `0B-v19.C`), three verification checks confirmed all open drift items are AR-safe.

**Phase 2 — Spec framework retrofit.** Realized mid-session that per-node consolidated specs hadn't been the working pattern. Backfilled `Layer2A_Spec.md` and `Layer2B_Spec.md` from handoff content. Drafted `Control_Spec.md` as architecture overview. Renamed `Layer0_Drift_Backlog.md` to `Project_Backlog.md` and broadened scope. Three memory rules added to enforce the spec-doc-per-node pattern going forward.

Net state: Layer 2 design 60% complete (2A, 2B, 2C locked; 2D and 2E remaining). One Batch C migration in production. Cross-layer drift inventory complete and categorized, all items deferred and AR-safe.

---

## What shipped this session

### Production state

Batch C migration ran clean. 10 exercises now at `etl_version = '0B-v19.C'`:

| ID | Exercise | Change summary |
|---|---|---|
| EX073 | Threshold Intervals (Bike) | Primary `[Road bike]`, 4 bike variants as Tier 2 substitutes |
| EX074 | VO2 Max Intervals (Bike) | Same pattern |
| EX075 | Sweet Spot Training (Bike) | Same pattern |
| EX117 | Loaded Step-Down (Eccentric Box) | Primary `[Plyo box, Dumbbell]`, KB/Vest variants as subs |
| EX119 | Weighted Step-Up (High Box) | Primary `[Plyo box, Dumbbell]`, Plyo box authoring fix, Barbell variant dropped |
| EX174 | Aero / TT Position Hold | Primary `[TT Bike]`, bike-trainer-in-aero added |
| EX185 | Climb Pacing & Cadence Management | Primary `[Road bike]`, Treadmill dropped entirely |
| EX186 | High Cadence Spin Drill | Primary `[Road bike]`, 4 bike variants |
| EX197 | Double Brick / Run-Bike-Run Pacing Drill | Primary `[Road bike]`, 4 bike variants |
| EX229 | Bench Press (Barbell / DB) | Primary `[Barbell, Bench, Squat rack]`, DB Bench Press split out as sub |

Active count: 159 (unchanged). Total: 234 (was 224 pre-Batch-C; +10 reinserts).

3-bucket substitute merge order locked: new equipment variants → existing non-improvised → existing improvised. Per Andy's choice (b) on the ordering decision.

### Documents added to project

| File | Purpose |
|---|---|
| `Layer0_Deployed_Schema_and_Drift_Report.md` (v2) | Authoritative deployed schema reference. v1 was wrong on several calls; v2 corrected after spec end-to-end read + xlsx inspection. |
| `Project_Backlog.md` | Renamed from `Layer0_Drift_Backlog.md`. Single rolling cross-layer deferred-work tracker. 17 items categorized; 0 blockers. |
| `Layer2C_Spec.md` | First per-node consolidated spec. Established depth standard (14 sections incl. edge cases, test scenarios, gut check). |
| `Layer2A_Spec.md` | Backfilled from handoff content at the same depth standard. |
| `Layer2B_Spec.md` | Same. |
| `Control_Spec.md` | Architecture overview. Pipeline diagram, per-layer responsibilities, standing rules, doc map. |
| `Layer0_ETL_Spec_v3_Patch_Batch_C.md` | Batch C spec patch — documents the 10-row curation and Open Item R resolution. |
| `verify_drift_specifics.sql` | Verification SQL committed for reproducibility. |

### Memory rules added

Three durable memory entries to enforce going forward:

- **#4** — Every layer/sublayer gets its own `LayerNX_Spec.md` at the `Layer2C_Spec.md` depth standard. Handoff docs are session bookkeeping; specs are source of truth.
- **#5** — `Project_Backlog.md` is the single rolling tracker. Update between layer sessions. Categories: Blocker / Deferred / Cleanup. Promote-only blocker status.
- **#6** — `Control_Spec.md` is the architecture overview. Maintain as new layers land.

---

## Resolutions this session

### Drift items verified — all AR-safe, all deferred

| ID | Verified specifics | Status |
|---|---|---|
| D-05 | All 33 sports have aggregator rows polluting `phase_load_allocation`, including AR (NULL percentages — noise, not garbage). **Standing rule:** every query touching PLA must include `AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`. Already in 2A §5.2 SQL. | Deferred + standing filter |
| D-07 | 4 sports missing from `phase_load_weekly_totals`: Off-Road / Adventure Multisport (Non-Nav), Open Water Marathon Swimming (10km), Open Water Marathon Swimming (25km), Swimrun. AR has all 4 phase rows ✓ | Deferred |
| D-08 | 3 rows missing in `sport_discipline_map`: Long Distance / Endurance Cycling (-2), Triathlon (-1). AR has all 15 disciplines ✓ | Deferred |
| D-17 | Sport naming mismatch between `sport_discipline_map` (top-level) and `phase_load_allocation` (sub-format). AR uses same name in both ✓. Workaround in 2A §5.1. Owner is Layer 1 race-goal capture, not FC. | Deferred (design req, not cleanup) |
| R | `primary_muscles` / `secondary_muscles` both `TEXT[]`. v20 xlsx keeps comma-separated strings; ETL splits on `', '`. | RESOLVED |

### Open Item R closed

Added to v4 §4.12 schema block requirements: `primary_muscles TEXT[]`, `secondary_muscles TEXT[]` with ETL transform `string_to_array(value, ', ')`.

---

## Open items still requiring Andy's input

### Before 2C implementation begins

Two `[DECISION POINT]` markers embedded in `Layer2C_Spec.md`:

1. **§5.1 — Toggle definition lookup at runtime vs pre-resolved by Layer 1.** Should 2C query `layer0.sport_specific_gear_toggles` at runtime for `paired_equipment_categories[]` and `also_satisfies[]`, or should Layer 1 pre-resolve and pass an `implied_equipment: list[str]` per toggle? My recommendation: runtime (simpler, no Layer 1 state duplication). Andy decision needed.
2. **§8.3 — Discipline-to-toggle mapping location.** The "Rock Climbing requires Climbing toggle" mapping doesn't currently live in any Layer 0 table. Hard-code in 2C Python (v1) or add `gated_discipline_ids TEXT[]` column to `sport_specific_gear_toggles` (cleaner, FC-1 work)? My recommendation: hard-code for v1, structured column in FC-1.

### Layer 2A review request

Andy explicitly flagged 2A backfill as the area with highest extrapolation risk. Worth eyeing:

- **§5.3 conditional rules** — currently described as code-side, not table-side. Confirm or revise.
- **§5.4 discipline weighting** — `load_weight = midpoint of race_time_pct band` as system default. Confirm.
- **§5.5 rationale generation** — templated, not LLM-generated. Confirm.
- **Function signature additions** — added `athlete_discipline_overrides`, `estimated_race_duration_hours`, `navigation_required`, `team_format` because the handoff body referenced them as invalidation triggers but they weren't in the original 2-param signature. Confirm.

---

## State of Layer 2

| Node | Spec status | Type | Tables consumed |
|---|---|---|---|
| 2A Discipline Classifier | ✅ Backfilled | Query | `sports`, `sport_discipline_map`, `phase_load_allocation`, `discipline_training_gaps` |
| 2B Terrain Classifier | ✅ Backfilled | Query | `terrain_types`, `terrain_gap_rules` |
| 2C Equipment Mapper | ✅ Drafted | Query | `exercises`, `sport_exercise_map`, `sport_discipline_bridge` (+ `sport_specific_gear_toggles` pending §5.1 decision) |
| 2D Injury Risk Profile | ⏳ Not started | TBD — apply standing protocol | TBD — preliminary: `disciplines.injury_patterns`, `exercises.contraindicated_*`, `discipline_substitutes` (for substitution under injury) |
| 2E Nutrition Baseline | ⏳ Not started | TBD | TBD — preliminary: `phase_load_weekly_totals`, `phase_load_allocation` (with D-05 filter), `cross_sport_properties` (LIT_RATIO), `sports.endurance_profile` |

Layer 2 cleanup work queued in `Project_Backlog.md` for FC-1 (ETL fixes) and FC-2 (spec v4 rewrite). Both happen at end of Layer 2 before Layer 3 starts. Don't attempt before 2D and 2E are locked.

---

## Standing rules now in force

From `Control_Spec.md` §8.2 — every node design must respect these:

1. **D-05 aggregator filter:** every query against `layer0.phase_load_allocation` MUST include `AND discipline_name NOT LIKE '%WEEKLY TOTAL%'`. 2A §5.2 has it. 2D and 2E will need it. Layer 4 will need it.
2. **Sport naming (D-17):** non-AR sub-format sports use top-level name for SDM queries, sub-format name for PLA queries. AR is name-aligned in both. Code-side strip logic in 2A §5.1 is the pattern.
3. **No FKs anywhere in layer0:** TEXT-based relationships by design. Be careful when superseding rows.
4. **Pre-flight introspection before any Layer 0 migration:** verify column existence + types before INSERT/UPDATE. Pattern from `update_retype_keeper_exercises.sql` v2 and `migrate_batch_c_bike_load_curation.sql`.
5. **Standing protocol — Query vs LLM:** every node design starts with the DB field audit + query-vs-LLM test before considering LLM implementation. 2A, 2B, 2C all dropped to query nodes under this pressure. Apply to 2D, 2E.
6. **Spec depth standard:** every new node gets a `LayerNX_Spec.md` at the 14-section depth from `Layer2C_Spec.md`. Handoffs are bookkeeping; specs are source of truth.

---

## Next session agenda — 2D Injury Risk Profile

### Pre-work checklist (apply before designing)

1. **DB field audit.** Scan all Layer 0 tables for fields relevant to injury risk: `disciplines.common_injury_patterns`, `disciplines.injury_preceding_behaviors`, `exercises.contraindicated_parts`, `exercises.contraindicated_conditions`, `discipline_substitutes` (for injury-driven substitution), `body_parts`, `health_condition_categories`. Confirm column types from drift report §2.
2. **Layer 1 inputs.** Read `Athlete_Onboarding_Data_Spec_v2.md` §B Health Conditions and Injury Records. Determine the structured shape of injury inputs (active vs resolved, severity, body part, side).
3. **Query vs LLM test.** Most of 2D should drop to query under this protocol — set operations on body parts, contraindication filters, severity scoring. Reach for LLM only on genuine reasoning (e.g., "is this combination of injury + planned discipline genuinely risky" if no structured rule covers it).
4. **Output contract.** What does Layer 4 need from 2D? Filtered exercise pool? Risk-flagged disciplines? Both?

### Probable 2D scope

- **Contraindication filter** — exercises with `contraindicated_parts` intersecting active injuries or `contraindicated_conditions` intersecting health conditions are excluded or downgraded.
- **Discipline injury-risk profiling** — `disciplines.common_injury_patterns` matched against athlete's injury history; surface elevated-risk disciplines.
- **Substitution under injury** — when an active injury blocks an exercise's primary discipline, suggest discipline-level substitutes via `discipline_substitutes`.
- **Severity scoring** — combine recency + severity + sport-coupling into a single risk score per discipline (deferred design question).

### What 2D probably does NOT do

- Decide whether to include a discipline (that's 2A).
- Decide which exercises to schedule (that's Layer 4).
- Manage equipment substitution (that's 2C).
- Surface injury content for athlete review (that's Layer 3 / UI).

### Deliverable

`Layer2D_Spec.md` at the 14-section depth standard. Update `Control_Spec.md` §9 doc map when done.

---

## Files for pickup (next-session reading order)

For the **2D design session:**

1. **This handoff** — for context on what's locked and what's queued.
2. **`Control_Spec.md`** — for the architectural framing and standing rules.
3. **`Layer2C_Spec.md`** — depth-standard reference. Drafting 2D follows this pattern exactly.
4. **`Layer2A_Spec.md`** — closest analog to 2D (both consume Layer 1 athlete data + Layer 0 reference tables; both produce filter + flag payloads).
5. **`Layer0_Deployed_Schema_and_Drift_Report.md`** — for the actual schema of `disciplines`, `exercises`, `discipline_substitutes`, `body_parts`, `health_condition_categories`.
6. **`Project_Backlog.md`** — to confirm no D-XX items have promoted to blocker since this session.
7. **`Athlete_Onboarding_Data_Spec_v2.md`** §B Injuries + Health Conditions — the input shape Layer 1 provides.
8. **`Layer1_2A_Kickoff_Handoff.md`** — has predecessor design notes that may have anticipated 2D inputs.

Optional context (not blockers):
- `Vocabulary_Audit_v2.md` §1 (body parts canonical list)
- `Layer0_ETL_Spec_v3.md` §4.3 (disciplines) for the injury-related fields (with the drift report corrections in mind)

---

## Open items still tracked

Carried in `Project_Backlog.md`. Summary of state:

| Category | Count | Notes |
|---|---|---|
| 🔴 Blocker | 0 | Nothing currently blocks design progress |
| 🟡 Deferred | 11 | All AR-safe; defer to FC-1 or design-time when each lands |
| 🟢 Cleanup | 6 | Pure doc/cosmetic; FC-2 spec rewrite |
| ✅ Resolved | 1 | Open Item R (muscle column types) |

Final cleanup batches scheduled at end of Layer 2:
- **FC-1: ETL bug fixes** — D-05 aggregator filter, D-07 4-sport weekly totals parser, D-08 3 missing SDM rows, D-13 Batch B patch correction, D-14 cross_sport_properties source_text, D-15 discipline_substitutes UNIQUE, D-03 phase_load_allocation derived fields decision
- **FC-2: Spec v4 rewrite** — fold Batches A/B/C patches + drift report into unified `Layer0_ETL_Spec_v4.md`; add missing §4 sections for `terrain_gap_rules`, `sport_name_aliases`, `discipline_technique_foci`; apply §8 consumer table corrections

---

## Working preferences (carry-forward, unchanged from prior handoffs)

Andy's preferences (from `userPreferences`):
- Direct, useful, no praise/hype/filler
- Match confidence to reality; flag uncertainty briefly
- Tell the truth even if an idea is weak
- Recommendations: focus on judgment, key tradeoffs, second-order effects
- End plans/evaluations with: risks, what we might be missing, best argument against
- Flag assumptions and blind spots
- When chat gets long or messy: prompt for a handoff and start fresh

Process notes:
- Spec-first philosophy — architecture → prompts → implementation; resist shortcuts
- Idempotent SQL with verify blocks is house style
- Pre-flight introspection mandatory before any column-touching migration
- Files staged in `/home/claude/<batch>/` then copied to `/mnt/user-data/outputs/` then `present_files`
- Andy runs scripts and reports back; Claude doesn't have DB access
- New spec docs go to project; handoffs are session bookkeeping
- When in doubt about drift, read the actual source not snippets (lesson from this session)

---

*End of handoff. Start fresh with this + `Control_Spec.md` + `Layer2C_Spec.md` (depth reference) at the next session.*
