# L3-Spec-Trio Round 2 Closing Handoff — Feedback Absorption + 3A Spec

**Session:** L3-Spec-Trio Round 2 (continuation of same chat as L3-Spec-Trio Round 1; feedback round on 3 of 5 round-1 outputs, then forward move to Layer 3 spec writing)
**Date:** 2026-05-13
**Predecessor handoff:** `L3_Spec_Trio_Closing_Handoff_v1.md`
**Status:** ✅ All 5 files shipped (4 absorption + 1 new node spec). Layer 3 spec writing started. 3B is the next forward move.
**Time-on-task:** Single chat session, full context window.

---

## 1. Session-start verification (rule #9)

Verified the 5 files shipped in L3-Spec-Trio Round 1 actually landed on disk before any new work:

| File | Anchor check | Result |
|---|---|---|
| `Control_Spec_v6.md` | All 8 C-1 through C-8 anchors at expected locations; line count = 438 | ✅ |
| `Project_Backlog_v10.md` | All 9 D-48 through D-56 rows present; L3-Spec-Trio session block; line count = 277 | ✅ |
| `Athlete_Onboarding_Data_Spec_v3.md` | v3.0 header; "What changed in v3 vs v2"; §H.3 Non-Event Goal Type row at line 600; line count = 1059 | ✅ |
| `Athlete_Data_Integration_Spec.md` | 12 sections; line count = 735 | ✅ |
| `Catalog_Migration_Plan.md` | 9 sections; line count = 306 | ✅ |

No drift between Round 1 handoff narrative and on-disk state. Spot-check via grep against expected anchor strings (all matched).

---

## 2. Feedback received and disposition

Andy gave substantive feedback on three of the five Round 1 outputs, plus one new backlog item. Disposition was proposed in-chat (immediate surgical edits vs deferred architectural items) and confirmed before execution.

### 2.1 Onboarding feedback — 2 surgical, 4 architectural

**Surgical (landed in v4):**
- Pregnancy intentionally never captured as a profile field. Static disclosure to female athletes only. Rationale: privacy + medical-deference (pregnancy training is OB/midwife territory).
- No shooting or fencing technical readiness — at all, ever. §D.7 retains Rock Climbing + Abseiling only. §J.3 drops Fencing setup + Shooting setup gear toggles. AIDSTATION supports modern pentathletes and biathletes (endurance + strength + recovery) but does not program skill-discipline technique.

**Architectural (deferred to dedicated design sessions):**
- D-58: Account/integration connections precede onboarding data entry (OAuth-first flow + prefill from integration data).
- D-59: Location profiles via Google Maps Places API + chain-membership lookup (manual address as fallback).
- D-60: Per-locale gear readiness inferred from location proximity/category, not per-equipment self-report.
- D-61: Session time availability tied to plan only, not to locale.

All four reshape onboarding architecture meaningfully (§A flow, §B locales, §J equipment, §G/§J schedule). Out of scope for a surgical v4 pass; tracked as new D-rows in Backlog v11 so future spec versions don't re-litigate fields that will move.

### 2.2 Integration feedback — 2 surgical

**Both landed in v2:**
- Garmin reframed: not live, never functioned. Build onto `provider_auth` from scratch (drop migration narrative). D-55 reframed in Backlog v11.
- New athlete-integration-data retention rule (§2.7): retain until BOTH (newer record of same type exists) AND (90+ days elapsed). Either alone → retain. Designed for endurance athletes with one A-race per year — pre-race data must survive a multi-month off-season. Per-table "same type" definitions included; webhook_events keeps its 90-day operational rule (different concern).
- No-user-preservation note (1–2 test accounts only) carried throughout — removes "breaking change for existing users" language.

### 2.3 Catalog Migration feedback — 1 surgical

**Landed in v2:**
- §4 Phase 1 step 3 expanded to explicit fuzzy-match + HITL workflow: exact match → fuzzy search returning top-N candidates → human review queue → confirmed alias OR gap-list entry. Step 4 (equipment) follows the same pattern.
- §4 Phase 4 adds "wipe pattern" alternative to the dual-write dance (viable given 1–2 test accounts).

### 2.4 New backlog item

- D-57: Periodic research re-evaluation cadence per science-based area. AIDSTATION cites research across many domains (periodization, nutrition, recovery, ACWR, environmental physiology, supplementation, climbing prerequisites, etc.) that evolve at different rates. Need a defined cadence per domain + tracking mechanism + Layer 0 re-run trigger when domain content changes materially.

### 2.5 Judgment call confirmed before execution

Andy confirmed both:
1. 3A + 3B in one session would breach the 5-file ceiling and degrade quality. **Ship 3A this session; 3B in fresh session.**
2. Retention rule applies to integration data tables; webhook_events keeps its operational 90-day cron; event-style per-night/per-workout records effectively retain-indefinitely (no superseding); daily-aggregate records follow the both-conditions rule cleanly.

---

## 3. Files shipped

All 5 files in `/mnt/user-data/outputs/` and presented via `present_files`.

| File | Lines | Status | Notes |
|---|---|---|---|
| `Athlete_Onboarding_Data_Spec_v4.md` | 1077 | ✅ Shipped | v4 changelog section before v3 changelog. §B.4.2 pregnancy line rewritten (line 379). §D pre-amble updated (line 431). §D.7 trimmed to Rock Climbing + Abseiling + scope note (lines 497-505). §J.3 Fencing setup + Shooting setup rows removed. No tier changes elsewhere; no vocabulary changes elsewhere; no Layer 3 input contract changes beyond the field deletions. |
| `Athlete_Data_Integration_Spec_v2.md` | 780 | ✅ Shipped | v2 changelog block in header. §2.3 rewritten — build-from-scratch, not migration. New §2.7 retention rule with per-table "same type" definitions and table-by-table application guidance. §3 Garmin row corrected ("Scaffold only" not "Live ingestion"). Wave-1 paragraph corrected. §5.4 rewritten. No structural changes to §3–§12 beyond Garmin-specific reframing. |
| `Catalog_Migration_Plan_v2.md` | 334 | ✅ Shipped | v2 changelog block. §4 Phase 1 step 3 expanded (~25 lines added: explicit fuzzy + HITL workflow with sub-steps a–e). Step 4 follows same pattern. Phase 4 adds wipe-pattern alternative. Cross-reference updated to `Athlete_Data_Integration_Spec_v2`. |
| `Project_Backlog_v11.md` | 302 | ✅ Shipped | Header bump v10 → v11. D-55 reframed Garmin "migrate" → "build" (with explicit no-user-preservation rationale). D-57 (research re-eval cadence), D-58 (account-first onboarding), D-59 (Google Maps Places + chain), D-60 (gear from proximity), D-61 (session-locale unbinding) added. New "Session L3-Spec-Trio Round 2" close block. |
| `Layer3_3A_Spec.md` | 649 | ✅ Shipped | New file. 14-section depth standard matching Layer2C/2D/2E. Function signature `llm_layer3a_athlete_state(...)`. §6 resolves both L3-Discovery open questions: self-report vs integration weighting (per-field-category rules) + confidence calibration (validator-enforced floor rules). §7 payload schema includes `Layer3APayload`, `CurrentState`, `Assessment`, `RecentTrajectory` (split into short_term / medium_term TrajectoryWindow), `ACWRStatus`, `ACWREntry`, `DataDensity`, `Observation`. §8 lists required observations with auto-emit triggers; §10 covers 8 edge cases including the v4 pregnancy disclosure case. |

**Working-directory cleanup:** all files copied from `/home/claude/` to `/mnt/user-data/outputs/` and verified. No drafts left in working state.

---

## 4. Session-end verification (rule #10)

Final pass over all 5 files before composing this handoff. Captured in chat log; summary:

**`Athlete_Onboarding_Data_Spec_v4.md`:**
- v4 header + "What changed in v4 vs v3" section present (4 anchor checks pass)
- "Pregnancy intentionally never captured" appears in v4 changelog
- §B.4.2 pregnancy disclosure-only language at line 379
- §D.7 table has 2 rows (Rock Climbing + Abseiling); Fencing/Shooting rows gone
- §D.7 scope note present
- §J.3 table has Snowshoeing immediately after Skate XC ski setup (Fencing/Shooting setup rows gone)
- §E cross-ref says "Rock Climbing, Abseiling" only

**`Athlete_Data_Integration_Spec_v2.md`:**
- v2 header + "What changed in v2 vs v1" section present
- §2.3 rewritten — "build-from-scratch" appears; "Garmin status reality" subhead present
- §2.7 retention rule subsection with per-table definitions table
- §3 Garmin row reads "Scaffold only"; Wave-1 paragraph says "Garmin is built from scratch"
- §5.4 heading reads "Garmin (build-from-scratch)"

**`Catalog_Migration_Plan_v2.md`:**
- v2 header + "What changed in v2 vs v1" section present
- §4 Phase 1 step 3 has explicit sub-steps a–e for fuzzy + HITL workflow
- "fuzzy-match + human-in-the-loop" string present (5 anchor matches)
- §4 Phase 4 has "wipe pattern" subsection

**`Project_Backlog_v11.md`:**
- v11 header line with milestone note present
- D-55 reframed (Garmin "built onto" not "migration onto")
- D-57 through D-61 all present (5 new rows; verified via regex count)
- "Session L3-Spec-Trio Round 2" session-close block present
- Total D-row count = 58 (consistent with D-1 through D-61 minus D-18/19/20 never-assigned)

**`Layer3_3A_Spec.md`:**
- 14 H2 sections at numbered depth standard (verified via grep)
- 649 lines (between 2C @ 500 and 2D @ 952 — appropriate for the node's complexity)
- 46 references to key schema/algorithm anchors (Layer3APayload, integration_bundle, evidence_basis, ACWREntry, notable_observations, confidence_clamped_by_data_density)
- §6 contains both open-question resolutions (self-report vs integration weighting + confidence floors)

No drift between handoff narrative and on-disk state.

---

## 5. Mechanically-applicable instructions for next session (rule #11)

**N/A.** All in-scope work shipped this session. No deferred edits.

The work captured in D-57 through D-61 is forward design work, not deferred edits to existing specs. Each row is self-contained with enough context for a future session to scope and execute.

One forward Control_Spec touch worth calling out (not deferred — recommended for next session to handle):

**Control_Spec_v6 §9 doc map shows Layer 3 as "not yet started."** This is now stale after `Layer3_3A_Spec.md` shipped. Two options for next session:

- **Option A (recommended): batch the §9 update.** Wait until 3B / 3C / 3D all ship, then do a single Control_Spec_v7 with all four Layer 3 spec entries added + a v6/v7 changelog block. Less doc-map churn.
- **Option B: bump Control_Spec_v7 now** with just 3A. Adds 1 file to the next session for ~10 minutes of work.

Either is defensible. Recommended is Option A.

---

## 6. Next-session execution plan

### Primary forward move: `Layer3_3B_Spec.md`

Goal-timeline-viability evaluation. The second of the four Layer 3 specs. Reads:

- Layer 1 §H.1 / §H.2 (event mode) or §H.3 (no-event mode incl. Non-Event Goal Type from v3)
- Layer 1 §C for baseline context
- `Layer3APayload` (consumer of 3A's `current_state` + `recent_trajectory`)
- `Layer2APayload` for discipline weights + `phase_load_allocation`
- Current date / event date

**Pre-step reading for the 3B spec writer:**
1. `Athlete_Onboarding_Data_Spec_v4.md` §H (event vs no-event mode + Non-Event Goal Type field at §H.3, line 600+)
2. `Layer3_3A_Spec.md` — particularly §7 payload schema (3B's input contract on the 3A side)
3. `L3_Discovery_Closing_Handoff_v1.md` §5.2 — 3B scope statement, proposed output schema, open questions
4. `Layer2A_Spec.md` §7 payload schema — 3B consumes discipline_weights + phase_load_allocation
5. `Layer2C_Spec.md` — depth-standard reference (or this session's `Layer3_3A_Spec.md` as a more direct reference)

**Estimated length:** Smaller than 3A (~400–550 lines plausible). 3B has a tighter scope: viability judgment + periodization-shape parameter. No combined trajectory analysis; no integration-bundle consumption.

**Open questions 3B must resolve (from L3-Discovery §5.2):**
- When in doubt on viability, surface as HITL or assume athlete is informed? (L3-Discovery default: HITL for any non-trivial viability concern.)
- How explicit should the periodization-shape override be? (Layer 4 contract dependency — what does Layer 4 actually accept?)

### Then `Layer3_3C_Spec.md` and `Layer3_3D_Spec.md`

Likely one session for both, per L3-Spec-Trio Round 1 handoff §6 recommendation. Smaller surfaces — 3C is a rules-based cross-node conflict detector; 3D is the HITL aggregation gate.

### Independent tracks (can run in parallel)

- **D-50 Phase 1 integration deployment** — Vercel-app CC task. Schema migration + route promotion for `provider_auth` (with `session_blob`), `webhook_events`, `polar_*`, `wahoo_*`, `coros_*`, plus new columns on `cardio_log` (D-56) and `training_log`. Reframed by Round 2: Garmin builds onto `provider_auth` from scratch (D-55).
- **D-52 Catalog Migration Plan Phase 1** — verification + fuzzy-match HITL alias audit. Independent of pipeline work; Round 2's `Catalog_Migration_Plan_v2.md` §4 Phase 1 has the executable workflow.
- **D-57 Research re-evaluation cadence design** — out-of-cycle design session. Could be done anytime; ideally before Layer 0 v8 ETL is contemplated.
- **D-58 / D-59 / D-60 / D-61 onboarding architectural reshapes** — dedicated design sessions per item. None blocks Layer 3 spec writing.

### Dependencies

- Layer 3 spec writing does NOT depend on D-50, D-51, D-52, D-58–D-61. Specs can be written against future Layer 1 / locale / equipment shapes; implementation follows.
- `q_layer1_payload` implementation depends on D-51 (Layer 1 field inventory). Independent of Layer 3 spec writing.
- D-60 (gear from proximity) reshapes `locale_equipment` data model — Layer 4 plan-gen consumer; not a Layer 3 concern.

---

## 7. Forward pointers

- **Next session: `Layer3_3B_Spec.md`** in a fresh chat. Pre-step reads above.
- **After 3B: combined `Layer3_3C_Spec.md` + `Layer3_3D_Spec.md`** in one session.
- **After all 4 Layer 3 specs: Control_Spec_v7** — batch §9 doc map update with all four Layer 3 entries.
- **After Layer 3 specs: Layer 4 design** — plan generation. Largest LLM workload in the pipeline. Consumes 3A current_state + 3A weak_links, 3B viability + periodization_shape, 5 Layer 2 payloads, 3D gate state.
- **D-58 through D-61 onboarding restructures:** worth scoping as a single design "wave" rather than four isolated sessions, since the four items interact heavily (account-first flow feeds Google Maps location flow feeds gear-from-proximity feeds session-unbinding).
- **D-57 research re-eval cadence:** could be its own dedicated session anytime. Ideally before AIDSTATION pipeline goes to wider testing.

**Rules in force, unchanged:**
- #9 session-start verification (verify prior handoff's claimed file updates actually landed)
- #10 session-end verification (verify each claimed file update on-disk before composing handoff)
- #11 mechanically-applicable deferred edits (str_replace blocks or verbatim content, never narrative summaries)
- #12 numeric version suffixes (revised files save as `_vN.md`; logical names cross-referenced via `view` on highest-N)

---

## 8. Gut check

**What this session got right.**

- **Disposition before execution.** The feedback batch could have absorbed silently — pregnancy is a small edit; shooting/fencing trim is a small edit. But four of the eleven feedback items were genuinely architectural (D-58–D-61), and absorbing them into a single onboarding-v4 surgical pass would have produced a vN.5 that compiled but didn't reflect the architectural intent. Proposing the disposition in chat, getting confirmation, then executing kept v4 clean and surfaced the deferred work as backlog rows.

- **Ceiling enforcement.** L3-Spec-Trio Round 1 gut-check explicitly named the 5-file ceiling. This session honored it: 4 absorption files + 3A = 5. Pushing in 3B would have meant context-budget pressure on the most consequential 14-section spec of the four-node Layer 3. Better to ship 3A solidly and put 3B in its own session.

- **Resolving L3-Discovery's open questions inside 3A.** Both open items (self-report vs integration weighting, confidence floors) had explicit answers in 3A §6 backed by validator-enforced rules. The LLM proposes, the floor enforces. This is the right shape for downstream consumers — 3B / 3C / 3D / Layer 4 can rely on confidence tags meaning something.

- **The retention rule as policy, not deployment requirement.** Integration v2 §2.7 says explicitly: retain-indefinitely is the safe default; the both-conditions rule becomes operative only when per-table policy is specified AND a cron is scheduled. This avoids overcommitting to pruning logic the integration tables don't need yet.

**Risks.**

- **The fuzzy-match HITL workflow in Catalog Migration v2 §4 Phase 1 is spec'd but not tooled.** The actual rapidfuzz script is described, not written. When Phase 1 starts, the spec writer or executor needs to build the script + run it + sit through the review queue. The review effort could be hours-to-a-day depending on how many fuzzy-match candidates surface. If `public.exercise_inventory` has, say, 80 entries with no exact `layer0` match, that's 80 review decisions. Plan for it.

- **Layer3_3A_Spec §6.2 confidence floor rules are policy, not validated against data.** The thresholds (≥10 workouts last 28d for high confidence; ≥1 active provider in last 14d; etc.) are reasoned defaults, not measured against athlete population data. Post-launch we'll see whether the floors gate too aggressively (everyone shows medium) or too loosely (high confidence on sparse data). Iteration expected.

- **3A's ACWR consumption assumes `q_layer3A_combined_load` normalizes units.** The integration spec §10 signature notes "Polar's `cardio_load` is exposed as a cross-reference, not the primary number." Implementation needs to actually enforce this — if the query layer returns mixed units (hours + TRIMP + TSS), 3A's `combined` ratio is meaningless. Worth flagging during Layer 1 sourcing implementation.

- **Garmin reframe in Integration v2 may need PROVIDERS_SCHEMA.md update.** That doc lives in the Vercel-app codebase, not this project. The CC track owns that update. Worth a cross-reference in the next CC handoff to keep them in sync.

- **Pregnancy disclosure as UX-only.** The Onboarding v4 change moves pregnancy from "field with associated logic" to "static UI disclosure with no data capture." The disclosure language ("If you are pregnant or postpartum, training guidance from AIDSTATION should be reviewed with your healthcare provider") is in the spec but the actual UI implementation is unscoped. Worth a Plan Management or app-team item.

**What might be missing.**

- **Section 6 (in 3A spec) prompt-into-LLM mechanics.** §6.1 says "the LLM is told the rules explicitly in the system prompt." §5.2 shows the prompt structure abstractly but doesn't include the full §6 rule text verbatim. The implementer needs to know §6.1's table and §6.2's floor rules go into the system prompt verbatim. Could be made more explicit; for now it's implied by "[§6 of this spec — quoted in the prompt]" placeholder in §5.2.

- **3A → 3B handoff coherence test.** 3B's spec writer will need to know whether 3A's `recent_trajectory.short_term.direction = 'overreached'` should change 3B's viability assertion. The contract is implicit through `Layer3APayload`; explicit hooks (e.g., "if 3A trajectory == overreached, 3B viability for short-timeline goals downgrades by one tier") may be useful but belong in 3B's spec, not 3A's.

- **Plan Management spec (D-27) still unstarted.** Now consumed by 3A's data_density block (which Plan Management may surface as athlete-facing recommendations to connect providers), by 3B's hitl_surface, by 3D's HITL gate. Becoming a thicker dependency. Worth scoping soon.

- **No `Layer1_Spec_v3` standalone doc.** The §H.3 amendment landed in Onboarding v3 → v4, but Layer 1 itself doesn't have a dedicated spec at this point — Control_Spec v6 §3 has a "Layer 1 sourcing" subsection and Onboarding v4 is the data source, but the `q_layer1_payload` function spec is unwritten. May not need its own doc — could live as part of D-51 (Layer 1 field inventory) work. Decision deferred.

**Best argument against this session's scope.**

You could argue the absorption pass should have been its own session, and 3A should have been a clean fresh-start session. Counter: the absorption was 4 surgical files (3 small edits + 1 routine backlog update), well within a single session's quality budget. Combining with 3A meant the spec writer had the just-revised Onboarding v4 / Integration v2 fresh in mind when writing 3A's input contract — fewer cross-spec mental context switches. The 5-file ceiling held; quality didn't degrade visibly.

Alternatively, you could argue D-58 through D-61 should have been folded into Onboarding v4 rather than deferred. Counter: each item materially restructures a different section (§A flow, §B locales, §J equipment, §J + §G schedule), and three of them depend on architecture beyond onboarding (Google Maps integration, location-category schema, plan-gen session-locale assignment logic). Doing them inline would have produced a half-rewritten v4 that signaled "design in progress" rather than "current spec." Better to defer with full context captured in the backlog rows.

---

*End of L3-Spec-Trio Round 2 closing handoff.*
