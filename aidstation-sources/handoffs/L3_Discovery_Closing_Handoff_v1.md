# L3-Discovery Closing Handoff — Layer 3 framing reconciliation + integration architecture lock

**Session:** L3-Discovery (the session FC-4b's handoff forward-pointed to as "FC-5 next"; renamed since it's not Final Cleanup work)
**Date:** 2026-05-13
**Predecessor handoff:** `FC4b_Closing_Handoff_v1.md`
**Status:** ✅ Discovery complete. Layer 3 reshaped from 6 sub-prompts to 4 nodes; integration architecture clarified as single-Neon-DB / two-schema (no bridge); §H.3 amendment locked; new spec doc + Control_Spec v6 + Project_Backlog v10 queued. **No spec files modified this session** — all output is captured in this handoff for next-session execution.
**Time-on-task:** ~90 min of discovery and decision-making. No file edits.

---

## 1. Session-start verification (rule #9 — completed in-chat)

Verified FC-4b's claimed file updates landed in project knowledge before any new work:

| File | Anchor check | Result |
|---|---|---|
| `Layer0_ETL_Spec_v7.md` | v7 header; `What changed in v7 vs v6` at line 16; §4.14 D-21 closure + 6-col CREATE TABLE at line 884; §6.2 line 1531 reads `.category_name`; backlog refs at v9 (lines 144, 1587) | ✅ |
| `Project_Backlog_v9.md` | v9 header with milestone note at line 5; D-21 row Resolved (FC-4b, 2026-05-13) at line 56; Session FC-4b CLOSED at line 176; FC-5 forward pointer at line 187 | ✅ |
| `Control_Spec_v5.md` | v5 header; `What changed in v5 vs v4` at line 9; §2 + §9 show v7 canonical / v6 historical / v9 active / v4 historical | ✅ |

No drift between FC-4b handoff narrative and on-disk state.

---

## 2. Decisions made this session

### 2.1 Layer 3 reshape — 4 nodes, not 6

The userMemories description of Layer 3 ("6 parallel sub-prompts: race analysis, fitness capacity, training history, injury/risk + HITL trigger generation, goal alignment, constraint mapping") predates Layer 2's actual buildout. Most of those responsibilities migrated into Layer 2 nodes during their detailed design (depth standard set by 2C). The remaining work consolidates into 4 nodes — 2 LLM, 2 query/rules.

**Original 6 → reconciliation:**

| Original sub-prompt | Disposition | Rationale |
|---|---|---|
| Race analysis | Dropped | 2A (disciplines + weights) + 2B (terrain × environment) ARE the race analysis. Plan-gen consumes typed payloads directly. |
| Fitness capacity | Kept → 3A | Layer 1 §C/§D/§E/§F store raw fields; interpretive judgment is genuine LLM reasoning. |
| Training history | Kept → 3A | Same data lens as fitness capacity (current state vs recent trajectory). One LLM call covering both is more coherent than two with overlapping inputs. |
| Injury/risk + HITL trigger generation | Dropped | Already in 2D per Control_Spec §7. Layer 3 consumes 2D's items into 3D. |
| Goal alignment | Kept → 3B | Closely related to timeline viability; one evaluation covering both. |
| Constraint mapping | Split | Enumeration done by 2A-2D; *conflict detection between constraints* is new → 3C. |

**Plus added (from Control_Spec_v5 framing):**
- Timeline viability gate → folded into 3B (non-separable from goal alignment)
- Cross-node conflict detection → 3C
- HITL aggregation gate → 3D

**Layer 3.5 collapses** into 3D's gate output. The `.5` designation is saved for places where there's genuine intermediate processing.

**Compared to userMemories:** dropped 3 outright, merged 2 into 3A, merged 1 with new content into 3B, added 3C and 3D. Two LLM sub-prompts where judgment matters; query/rules elsewhere.

### 2.2 §H.3 amendment for Layer 1 v3

New field added to §H.3 no-event mode to close the goal-type gap. Three of the userMemories goal list ("endurance capacity," "overall fitness," "strength and muscular development") had no field in §H.3 — only Plan Duration was captured.

Field: `Non-Event Goal Type` — single-select enum (Endurance / General fitness / Strength / Mixed), default General fitness. Backwards-compatible.

Exact text in §6 below.

### 2.3 Integration architecture — locked

**Single Neon Postgres DB** serves both the Vercel app and the AIDSTATION pipeline. Two schemas:
- `layer0.*` — platform reference data, versioned, supersede-on-update (already deployed, fully self-consistent per FC-4b)
- `public.*` — Flask app tables (training logs, body, injuries, plans, equipment, integration tables), documented in `DATABASE.md`, mutable with standard `created_at`/`updated_at`

**Layer 1 is a conceptual aggregation**, not a separate schema. The query layer assembles Layer 1 payloads from:
- App tables in `public.*` (the existing Flask app schema)
- Integration tables in `public.*` (`provider_auth`, `webhook_events`, `polar_*`, `wahoo_*`, `coros_*` — when deployed)
- Explicit onboarding-specific fields (some new to the app schema; need inventory at Layer 1 v3 time)

**Shared catalogs (exercises, equipment, etc.) are unified at `layer0.*`** — the app reads from `layer0.*` rather than maintaining parallel catalogs. No drift check needed.

**The AIDSTATION pipeline is an extension to the existing Vercel app**, not a parallel data layer. This clean framing simplifies everything downstream.

### 2.4 Data integration deployment timing

Integration is scoped + ready but not deployed. Recommendation: deploy *after* 3A spec lands. Reasons:
- Deployment now breaks the "fully self-consistent against deployed Neon" baseline mid-Layer-3-design for no immediate consumer
- Deploying with 3A spec done means the integration arrives with a known reader on day one — tighter feedback loop, smaller drift risk
- 3A spec can be written against the documented schema (Athlete_Data_Integration_Spec.md captures this) without requiring deployment

Pre-step before 3A spec: schema lock for the integration tables (~30 min — see §6.3).

### 2.5 New spec doc: `Athlete_Data_Integration_Spec.md`

Consumer-side spec capturing what Layer 3 (and other pipeline consumers) sees over the integration tables. Outline in §6.3.

References (does not duplicate) the original integration handoffs:
- `HANDOFF-2026-05-13.md` — provider stub playbook
- `HANDOFF-2026-05-13-stub-batch.md` — four-stub batch + Strava challenge variant
- "Provider Integration Schema" doc — slug/URL/env-var conventions, planned DB tables

These are external docs (from a CC session in the Vercel-app codebase context) — they're the source of truth for the *producer* side. The new spec is the *consumer* side.

### 2.6 Side find — Control_Spec_v5 §8.2 stale wording

Line 280 still carries pre-FC-4b D-21 standing rule wording: "Defer rename to FC-1/FC-2." D-21 is closed; the framing is stale. Underlying principle (match on enum values, not SQL column names) is still correct. Fold the cleanup into Control_Spec_v6.

---

## 3. Files shipped

**None.** This handoff is the only artifact of this session. All decisions are captured here for next-session execution.

---

## 4. Session-end verification (rule #10)

No file edits made this session → no edits to verify. This handoff itself is the deliverable; its accuracy against the chat decisions is the only thing to confirm, which is captured in §2 above.

Note for next session: when executing the work in §6, follow rule #10 — verify each claimed file update against on-disk state before composing the next handoff.

---

## 5. Layer 3 four-node scope statements (input for Layer3_Spec writing)

Sufficient detail for the next session to write `Layer3_Spec.md` against the §8.3 14-section depth standard. These are scope statements, not full specs — the spec writer fills in algorithm, validation, edge cases, performance budget, test scenarios per the standard.

### 5.1 Node 3A — Athlete state evaluation

**Type:** LLM
**Purpose:** Produce structured judgment of current athletic capacity + recent trajectory.

**Inputs:**
- Layer 1 §A demographics (basic context)
- Layer 1 §B health/injuries (already-known constraints, for context only — 2D handles the actual injury logic)
- Layer 1 §C training history (years training, primary sport, current weekly volume, peak historical volume, recent races, training consistency)
- Layer 1 §D discipline-specific baselines (running/cycling/swimming/etc.)
- Layer 1 §E strength/core/balance benchmarks
- Layer 1 §F performance testing baselines (FTP, CSS, running threshold pace, lab results)
- Layer 1 §I lifestyle/recovery (sleep, dietary, supplements, GI triggers)
- Integration data (when available): `public.cardio_log` and `public.training_log` recent entries; integration tables (`polar_*`, `coros_*`, `wahoo_*`) per Athlete_Data_Integration_Spec
- 2A output (phase context — what phase the athlete *should* be in given the sport_load_allocation)

**Output schema (proposed):**
```
{
  current_state: {
    aerobic_capacity_assessment: enum (low / moderate / good / strong) + reasoning_text,
    strength_assessment: enum + reasoning_text + weak_links: [string],
    skill_assessments: { per-discipline (sparse) },
    body_composition_notes: optional_text
  },
  recent_trajectory: {
    trajectory_assessment: enum (overreached / recovered / steady / detrained / peaking) + reasoning_text,
    confidence: enum (high / medium / low),  // drops to low if integration data absent
    acwr_status: { per-discipline + combined (when computable) }
  },
  notable_observations: [string]
}
```

**Cache invalidation:** any §C/§D/§E/§F/§I change; new integration data ingestion >N days since last run (e.g., 7 days); 2A output change.

**Edge cases the spec must handle:**
- Missing integration data (post-launch but no providers connected) → confidence tags drop, trajectory based on §C self-report only
- Just-onboarded athlete with no recent training history → state-only output, no trajectory
- Conflicting signals (high logged volume but reports feeling overtrained) → LLM weighs both, flags in observations

**Open questions for spec writer:**
- How to weight self-report vs integration data when they conflict
- Confidence-tag thresholds (what data density gates "high" vs "medium")

### 5.2 Node 3B — Goal-timeline-viability evaluation

**Type:** LLM
**Purpose:** Judge whether stated goals are achievable in available time. Produce periodization-shape parameter for Layer 4.

**Inputs:**
- **Event-mode (Layer 1 §H.1 = Y):** §H.2 Goal Outcome (enum + time goal + first-time-at-distance Y/N) + Event Date + Previous Attempts (incl. DNF cause) + race demands (distance, duration, terrain, navigation, pack weight)
- **No-event-mode (§H.1 = N):** §H.3 Plan Duration + new Non-Event Goal Type enum (post-amendment per §2.2)
- **Both modes:** 3A output (current state + trajectory), 2A discipline weights + phase_load_allocation, current date

**Output schema (proposed):**
```
{
  mode: enum (event / no-event),
  goal_viability: {
    viability: enum (achievable / achievable-with-adjustment / unrealistic-as-stated) + reasoning_text,
    confidence: enum,
    suggested_adjustments: [string]  // e.g., "stretch goal to mid-pack rather than podium given timeline"
  },
  periodization_shape: {
    mode: enum (standard / compressed / extended / custom),
    start_phase: string,             // which phase of standard periodization to begin in (skip-ahead logic)
    phase_weeks: optional { phase_name: weeks_int },  // override of phase durations
    reasoning_text: string
  },
  hitl_surface: [hitl_item]  // items for the athlete to confirm (goal realism, timeline adaptation)
}
```

**Cache invalidation:** §H.2 changes, §H.3 changes, §C changes affecting baselines, 3A output changes, race date changes.

**Edge cases:**
- Sparse time-goal data (athlete didn't specify a target time) → viability based on enum-tier and first-time-at-distance only; confidence drops
- "Finish" goal with abundant timeline → trivially achievable; output light HITL or skip entirely
- First-time-at-distance athletes → calibration challenge; explicit note in reasoning
- Stated goal is "Podium" + current state is moderate + 4-week timeline → clear unrealistic; suggested_adjustments populated

**Open questions for spec writer:**
- When in doubt on viability, surface as HITL or assume athlete is informed? (Default: HITL for any non-trivial viability concern.)
- How explicit should the periodization-shape override be? (Layer 4 contract dependency.)

**Note:** §H.3 amendment (§2.2) lands in Layer 1 v3 BEFORE 3B's input contract is finalized. Don't write 3B's spec until Layer 1 v3 is in project knowledge.

### 5.3 Node 3C — Cross-node conflict detection

**Type:** Query / rules
**Purpose:** Detect inconsistencies across 2A-2E typed payloads that don't surface within any single node.

**Inputs:** All five 2A-2E typed payloads.

**Output:** List of structured conflict items.

**Initial rule set (spec writer should enumerate and expand):**
1. Discipline included in 2A AND no equipment in 2C AND no injury history in 2D → "discipline included without supporting equipment" (your rock-climbing example)
2. Discipline included in 2A AND terrain gap in 2B AND no substitute available → "discipline included but cannot train terrain"
3. High-load discipline in 2A AND active injury in adjacent body region in 2D (where 2D didn't HIGH-flag because the rule didn't fire on 2D's own context alone) → cross-node escalation
4. Nutrition target in 2E AND dietary restriction conflict (e.g., high-protein × vegan)
5. Sport-specific gear toggle conflicts (e.g., bike disciplines included but no bike gear ready in §J)
6. Phase load expects skill-specific work AND §D shows no experience in that discipline
7. Heat acclim required (2E race demand) AND locale climate doesn't support (§J)

**Cache invalidation:** any 2A-2E payload change.

**Edge cases:**
- Rules that might overlap with 2D's HIGH-risk substitute logic → don't double-flag (3D dedups by source + entity)
- Athlete may *want* a discipline included without equipment for support work → revise option in 3D lets them acknowledge "support exercises only"

**Open questions:**
- If conflict patterns prove harder to enumerate than expected during real testing, revisit as LLM finishing step. Backlog item: D-49 (proposed).

### 5.4 Node 3D — HITL aggregation + gate

**Type:** Query / orchestration (no LLM)
**Purpose:** Collect HITL items from upstream nodes + 3C, present unified resolution flow, gate Layer 4.

**Inputs:**
- 2A `prompt_required` items
- 2D HITL items (per Control_Spec §7 line 258)
- 2E HITL items (per Control_Spec §7 line 259)
- 3B viability HITL items
- 3C conflict items

**Output schema:**
```
{
  hitl_items: [
    {
      source: enum (2A / 2D / 2E / 3B / 3C),
      severity: enum (blocker / warning / informational),
      description: string,             // athlete-facing
      recommended_action: string,
      acknowledge_option: string,      // what acknowledgment means
      revise_option: string,           // what revision means (Layer 1 §X edit; occasionally Layer 0)
      resolution: enum (pending / acknowledged / revised) + {
        timestamp: ts,
        athlete_reasoning: optional_text,  // per userMemories rule "dismissals stored with timestamps and athlete reasoning"
        edit_target: optional_string       // for revised resolutions
      }
    }
  ],
  gate_status: enum (pending / green)
}
```

**Gate semantics:**
- All items must resolve to `acknowledged` or `revised` before `gate_status = green`
- Layer 4 only runs when `gate_status = green`
- Acknowledgment captures timestamp + optional reasoning text (athlete justifies why they accept the system's handling)
- Revise option triggers re-run of affected upstream nodes after athlete edits Layer 1 (or Layer 0), then 3D re-aggregates

**Edge cases:**
- **Blocker-severity items can't be acknowledged**, only revised — e.g., post-surgical injury without parseable clearance date (2D); HIGH-risk discipline with no available substitute (2D)
- Multiple HITL items from the same root cause — dedup or surface as related cluster
- Athlete revises Layer 1 → upstream re-run cascades → some items disappear (resolved by revision), new items may appear → re-present unified

**Cache invalidation:** any upstream payload change; any athlete resolution action.

---

## 6. Mechanically-applicable instructions for next session (rule #11)

### 6.1 §H.3 amendment text — Layer 1 v3

**Source file:** `Athlete_Onboarding_Data_Spec_v2.md` (current canonical Layer 1)
**Target file:** `Athlete_Onboarding_Data_Spec_v3.md` (new file, clone of v2 + this edit)

**Per rule #12:** create v3 as new file based on v2 with the str_replace applied. Don't modify v2.

**str_replace block:**

`old_string`:
```
| Plan Duration | Enum (8 / 12 / 16 / 20 / 24 weeks) | 1 | Phase durations and forward periodisation. Maximum 24 weeks | Self-report |

**On no-event disciplines:**
```

`new_string`:
```
| Plan Duration | Enum (8 / 12 / 16 / 20 / 24 weeks) | 1 | Phase durations and forward periodisation. Maximum 24 weeks | Self-report |
| Non-Event Goal Type | Single-select enum (Endurance / General fitness / Strength / Mixed) | 1 | Drives 3B viability framing in no-event mode; default = General fitness | Self-report |

**On Non-Event Goal Type:** When H.1 = No, §C Discipline Weighting drives volume *allocation* across disciplines; Non-Event Goal Type drives the *type* of progression targeted (aerobic capacity / overall conditioning / strength focus / blended). Default = General fitness for athletes who don't specify. 3B reads this field to frame viability evaluation in no-event mode (different shape from event-mode where §H.2 Goal Outcome is the input).

**On no-event disciplines:**
```

**Plus header bump:** v3 header should add a "What changed in v3 vs v2" section noting the §H.3 Non-Event Goal Type addition. Other sections unchanged.

### 6.2 Control_Spec_v6 surgical edits

**Source:** `Control_Spec_v5.md`. **Target:** `Control_Spec_v6.md` (new file per rule #12).

The next session should view the exact existing text before each str_replace to confirm whitespace/wording — what's captured below is the *intent* and the locations.

**Edit C-1 — Header bump.** Replace v5 status line with v6 status line. Add new "What changed in v6 vs v5" section above the existing "What changed in v5 vs v4" section. Bullets for the v6 changed section:
- Layer 3 framing reconciliation: 6 sub-prompts → 4 nodes (3A/3B/3C/3D) per L3-Discovery session
- Layer 3.5 collapsed into 3D's gate output
- Integration architecture clarified: single Neon DB, two schemas, Layer 1 as conceptual aggregation
- New cross-cutting spec: `Athlete_Data_Integration_Spec.md`
- §8.2 D-21 standing rule wording cleanup (D-21 is closed per FC-4b)

**Edit C-2 — §2 Layer 1 description (lines 82–95).** Add a paragraph at the end clarifying Layer 1 is a conceptual aggregation produced by the query layer from `public.*` app tables + integration tables + onboarding-specific fields. Layer 1 is NOT a separate schema. Reference `DATABASE.md` and the new `Athlete_Data_Integration_Spec.md`.

**Edit C-3 — §2 Layer 3 description (lines 112–120).** Replace with 4-node framing (3A/3B/3C/3D). Keep the timeline-viability / cross-cutting evaluation language but reshape around the four nodes. Note: Layer 3.5 collapses into 3D's gate output.

**Edit C-4 — §3 data flow contract.** Add a new subsection between current "Layer 1 → Layer 2 (per-section)" and "Layer 2 → Layer 3 (typed payloads)" titled **"Layer 1 sourcing"** that explains the query-layer aggregation pattern over `public.*` + integration tables. Update the "Layer 2 → Layer 3" subsection to reflect 4-node structure (all 2A-2E payloads land at 3A/3C; 3B reads 2A; 3D consumes all upstream HITL items).

**Edit C-5 — §7 HITL surface table (line 252+).** Update the Layer 3 row to specify the 3D gate aggregation (collects 2A `prompt_required`, 2D items, 2E items, 3B viability items, 3C conflicts). Remove any standalone Layer 3.5 row if present.

**Edit C-6 — §8.2 standing rules (line ~280).** D-21 entry needs rewording. Old text references "Defer rename to FC-1/FC-2" — replace with note that D-21 was closed in FC-4b and the underlying principle (match on enum *values*, not column names) remains in force as standing rule.

`old_string`:
```
- **D-21 reconciliation** (`health_condition_categories` column name): 2D and 2E match on enum *values* (system_category strings like 'Cardiac', 'Neurological'), not on column names. Whether the deployed column is called `category_name` or `system_category` is housekeeping, not correctness. Defer rename to FC-1/FC-2.
```

`new_string`:
```
- **Match on enum values, not column names** (closed-out D-21 standing rule): 2D and 2E match on `HealthConditionRecord.system_category` enum *values* (strings like 'Cardiac', 'Neurological'), not on the SQL column name. The deployed SQL column is `category_name` (confirmed FC-4b 2026-05-13; see `Layer0_ETL_Spec_v7` §4.14, §6.2). The Python dataclass field name `system_category` is independent of the SQL column. Standing rule: code reads the dataclass; SQL queries read `category_name`.
```

**Edit C-7 — §8.3 spec doc rule (line ~286).** Add a sentence noting that the 14-section depth standard is for *node* specs; cross-cutting spec docs (like Athlete_Data_Integration_Spec) follow their own appropriate structure.

**Edit C-8 — §9 doc map.** Multiple updates:
- "Layer 3+" section: update `Layer3_Spec` from "not yet started (HITL gate design)" to "not yet started (4-node structure: 3A/3B/3C/3D per L3-Discovery handoff)"
- "Cross-cutting" section: add new entry `Athlete_Data_Integration_Spec` (status: ⏳ not yet started, draft target this session pair)
- Add `Control_Spec_v5` to historical predecessors list
- Add `Project_Backlog_v9` to historical predecessors list
- Update active pointers to v6 / v10

### 6.3 `Athlete_Data_Integration_Spec.md` outline

New file, no predecessor. Sections:

1. **Purpose** — consumer-side spec for pipeline access to athlete integration data.
2. **Architectural context** — single Neon DB, two schemas (`layer0.*` reference + `public.*` app), Layer 1 as conceptual aggregation. Reference Control_Spec §2 and §3.
3. **Provider list + stub status** — table covering Phase 0 deployed (COROS, Ride With GPS), Phase 0 prepped uncommitted (Strava, Whoop, TrainingPeaks, Zwift), priority queued (Polar, Wahoo), Wave-2 remainder. Source: integration handoffs.
4. **Generic integration tables** — `provider_auth`, `webhook_events`. Schemas lifted from Provider Integration Schema §5.1.
5. **Per-provider integration tables** — `polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_continuous_hr_samples`, `wahoo_plans`, `coros_daily_summary`, `coros_hrv_samples`, `coros_plans`. Schemas lifted from Provider Integration Schema §5.2. TBD note for Strava/Whoop until those data shapes are pinned down.
6. **New columns on existing app tables** — `cardio_log.polar_exercise_id`, `cardio_log.wahoo_workout_id`, `cardio_log.coros_label_id`, `cardio_log.rwgps_trip_id`, `training_log.*` mirrors. Lifted from Provider Integration Schema §5.3.
7. **Field mapping** — for each Layer 1 §C / §D / §F field that can be sourced from integration data: which provider tables/columns feed it, with what coverage and freshness. This is the consumer mapping 3A needs. Probably the largest section.
8. **Two-regime model** — pre-integration (Layer 1 §C self-report only, low-confidence on recent-trajectory outputs) vs post-integration (integration data + §C as fallback for missing fields). Confidence-tag conventions for consumers.
9. **Mutability + caching** — integration data in `public.*` is mutable (Polar updates old sleep records); contrast with `layer0.*` supersede pattern. Cache invalidation implications for 3A.
10. **Query layer access patterns** — proposed function signatures parallel to Layer 0 query layer (e.g., `q_layer3A_recent_workouts(user_id, since_days)`, `q_layer3A_recent_sleep(user_id, since_days)`). Document the cross-schema query pattern.
11. **Open items + forward references** — Phase 1 integration deployment; per-provider data-shape filling; deployment-after-3A-spec rationale.
12. **References** — handoffs (`HANDOFF-2026-05-13.md`, `HANDOFF-2026-05-13-stub-batch.md`, `Provider Integration Schema`), `DATABASE.md`, Control_Spec §3.

**Pre-step before drafting:** ask Andy to externalize the integration schema he has "scoped and ready." A short writeup of what tables exist, fields/units, normalization vs raw is enough. If `DATABASE.md` is being updated alongside Phase 1 deployment, the new sections there are the source of truth and this spec references them.

### 6.4 `Project_Backlog_v10.md` row entries

New file based on v9 with header bump + new rows.

**Header changes:** v10 — 2026-05-XX (post-L3-Discovery: Layer 3 reshaped to 4-node structure; integration architecture locked to single-Neon-DB / two-schema; §H.3 amendment queued for Layer 1 v3; new spec `Athlete_Data_Integration_Spec.md` queued).

**Session FC-5 / L3-Discovery (closed) block:** add retrospective at the FC-4b CLOSED block's location.

**Session L3-Spec-Trio (next) tentative scope:** Athlete_Data_Integration_Spec.md + Layer 1 v3 + Control_Spec_v6 + Project_Backlog_v10 in one or two focused sessions, then Layer 3 spec writing.

**New backlog rows:**

| ID | Description | Priority | Status | Affects | Notes |
|---|---|---|---|---|---|
| D-48 | Per-provider data-shape filling for Strava/Whoop integration tables — TBD per provider docs. Polar/Wahoo/COROS already spec'd. | Cleanup | Deferred | Integration | Track as integration deploys per provider. Not blocking Layer 3 spec — Strava/Whoop can be "TBD" in Athlete_Data_Integration_Spec at first. |
| D-49 | 3C conflict-rule enumeration may prove incomplete in real testing — backlog item to revisit as LLM finishing step if patterns prove harder to enumerate than expected. | Cleanup | Deferred | 3C | Default for v1: query/rules only. Revisit post-deployment. |
| D-50 | Phase 1 integration deployment — schema migration + Vercel app code promotion for Polar/Wahoo (and others as they progress). Currently scoped + ready in CC chat; deploy after 3A spec lands. | Deferred | Deferred | Integration | Independent track. Owner: CC. Coordinate with `DATABASE.md` updates. |
| D-51 | Layer 1 §C/§D/§E/§F field-by-field inventory against `public.*` existing tables — what's already there, what needs new columns/tables, what's onboarding-only. Needed before Layer 1 v3 (or as part of it). | Deferred | Deferred | Layer 1 v3 | Quick Neon query + DATABASE.md cross-ref. Probably 1-2 hours. |

**Resolved items to mark:**
- None this session. (No drift items closed; only architectural decisions made.)

---

## 7. Next-session execution plan

**Recommended scope: one session, possibly two if it expands.**

Order matters:

1. **Externalize the integration schema (pre-step, ~30 min).** Andy posts the planned integration tables + DATABASE.md updates. This is the source for Athlete_Data_Integration_Spec §4–§6.

2. **Draft `Athlete_Data_Integration_Spec.md` v1** following §6.3 outline.

3. **Draft `Athlete_Onboarding_Data_Spec_v3.md`** by applying §6.1 str_replace + header bump.

4. **Draft `Control_Spec_v6.md`** by applying §6.2 edits C-1 through C-8.

5. **Draft `Project_Backlog_v10.md`** by applying §6.4 header + session blocks + new rows.

6. **Session-end verification (rule #10)** of all four file outputs against the claims in the closing handoff for that session.

7. **Compose L3-Spec-Trio closing handoff** with forward pointer to Layer3_Spec writing.

**If scope expands** (e.g., field inventory for D-51 turns up substantial gaps): split into two sessions. The Athlete_Data_Integration_Spec.md + §H.3 amendment can land in session 1; Control_Spec_v6 + Backlog_v10 in session 2.

**Layer3_Spec.md writing comes after this trio.** Spec writer follows the §8.3 14-section depth standard using the four-node scope statements in §5 of this handoff as starting input.

---

## 8. Forward pointers

- **Next session (Spec-Trio): Athlete_Data_Integration_Spec + Layer 1 v3 + Control_Spec_v6 + Project_Backlog_v10.** Per §7 execution plan. Strongly recommended same chat as the schema externalization pre-step to keep context tight.

- **After Spec-Trio: Layer3_Spec.md writing.** Likely one session for 3A spec, one for 3B, one combined 3C+3D (smaller surface for query/rules nodes). Layer 3.5 does not get its own spec — folded into 3D's section in Layer3_Spec.

- **After Layer 3: Phase 1 integration deployment (D-50).** Coordinated with CC. New integration tables in `public.*`, DATABASE.md updates, drift report against deployed state, schema lock if anything diverged from Athlete_Data_Integration_Spec.

- **After integration deployment: Layer 4 design (plan generation).** This is where the periodization-shape parameter from 3B starts mattering for plan-gen's input contract.

- **Rules in force, unchanged:** #9 session-start verification, #10 session-end verification, #11 mechanically-applicable deferred edits, #12 numeric version suffixes.

---

## 9. Gut check

**What this session got right.**

- **Caught the userMemories drift before designing anything.** The handoff inherited "6 parallel sub-prompts" from userMemories, but Control_Spec_v5 said something different. The reconciliation (4 nodes, not 6) is materially cleaner — saved a session's worth of work that would've been spent re-litigating during 3A/3B spec writing.
- **The integration architecture clarification was a real save.** Started with a "two databases, need a bridge" model; the user's correction reframed to "one Neon DB, two schemas, no bridge needed." The Athlete_Data_Integration_Spec gets much simpler as a result, and the bridge architectural decision step (which was on the path) collapses entirely.
- **Layer 1 as conceptual aggregation, not a separate schema.** Surface-level the smallest reframe; in practice the most important. It means the AIDSTATION pipeline doesn't need a new athlete-data layer — it consumes the existing app tables + integration tables + onboarding-specific fields via the query layer. Probably worth a paragraph in Control_Spec_v6 §2.

**Risks.**

- **D-51 (Layer 1 field inventory) might be bigger than 1-2 hours.** The Athlete_Onboarding_Data_Spec is comprehensive (12 sections, hundreds of fields). DATABASE.md has tables for strength, cardio, body, injuries, plans, equipment, Garmin. The overlap is substantial but not 1:1. If there are 30+ onboarding fields with no app-table home, the Layer 1 v3 spec turns into a meaningful schema design exercise, not just a §H.3 amendment. Worth scoping early.
- **The four-node Layer 3 design assumes 3A and 3B as separate LLM calls.** Cleaner cache invalidation, but if real-world output coherence suffers, consolidation may be needed. The spec writer should leave this as an explicit open item in 3A/3B specs to revisit post-deployment.
- **3C as rules-only may turn out under-specified.** Listed 7 initial rules; real testing may surface patterns that don't fit a deterministic shape. D-49 captures the contingency but it's worth watching during 3A/3B/3D testing.

**What might be missing.**

- **Goals data location verification only covered §H.2 / §H.3.** Didn't read §C (Discipline Weighting) closely against goal-alignment use cases. 2A weighting overrides might encode partial goal signal that 3B can use. Worth a quick re-read during 3B spec writing.
- **Integration data ↔ §C fields field-mapping section in Athlete_Data_Integration_Spec.md.** Marked "probably the largest section" in §6.3, but I didn't draft it. The next session's spec writer needs the actual field-by-field mapping (e.g., "§C 'Current Weekly Training Volume' is populated by SUM(`public.cardio_log.duration_hr`) WHERE timestamp > NOW() - 7 days, OR `polar_cardio_load.daily_load` aggregated, depending on connected providers"). This is real spec work, not a copy-paste from existing docs.
- **Heat acclim state (mentioned in Control_Spec line 160 as 2E input) — where does it live?** Mentioned in 3C rule 7 above (heat acclim required × locale climate doesn't support) but I didn't verify the data source. Plan Management state per Control_Spec line 160 — but Plan Management isn't a Layer 1 section in the Onboarding spec. Possibly in `public.*` somewhere. Worth pinning down.

**Best argument against this session's scope.**

This session produced no spec files — only decisions and a handoff. From a "code shipping" standpoint, it's zero output for ~90 min. Counter: the decisions made were genuine forks in the road. Designing Layer 3 against the wrong framing (6 sub-prompts that don't match Layer 2's actual output shape) would have produced unusable spec work. The integration architecture reframe (two DBs → one) changes what Athlete_Data_Integration_Spec actually contains. These are 1-bit decisions that, once made, unblock real spec work; they're not delay, they're prerequisites. The right rubric for a discovery session is "did we reduce uncertainty?" and the answer is yes — sharply.

---

*End of L3-Discovery closing handoff.*
