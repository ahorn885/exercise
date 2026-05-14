# L3-Spec-Trio Closing Handoff — Layer 3 spec prerequisites + integration architecture + catalog migration plan

**Session:** L3-Spec-Trio (executed in same chat as L3-Discovery; expanded from 3 to 5 deliverables after pre-step inventory revealed catalog drift)
**Date:** 2026-05-13
**Predecessor handoff:** `L3_Discovery_Closing_Handoff_v1.md`
**Status:** ✅ All 5 deliverables shipped. Layer 3 spec writing now unblocked. **No deferred edits** — everything in scope landed this session.
**Time-on-task:** ~2 hours (one chat session, immediately following L3-Discovery in the same context window).

---

## 1. Session-start verification (rule #9)

**Verified in-chat at session start.** L3-Discovery handoff claimed "no files shipped" — confirmed by inspecting project file list. The handoff itself was the only artifact of that session. No on-disk drift to reconcile.

**Pre-step verification of inputs:**
- `Athlete_Onboarding_Data_Spec_v2.md` (v2.5, 2026-05-06) — read and confirmed §H.3 anchor text for the str_replace.
- `Control_Spec_v5.md` (2026-05-13, post-FC-4b) — read and confirmed C-1 through C-8 anchor locations.
- `Project_Backlog_v9.md` (2026-05-13, post-FC-4b) — read structure and existing D-NN row format.
- Pre-step inventory document (`L3-Discovery_Pre-Spec-Trio_Inventory`, pasted in chat by Andy) — substantive §A schema dump + §B planned integration tables + §C drift findings + §D observations. This was the source-of-truth input for the integration spec and the catalog migration plan.

---

## 2. Decisions made this session

L3-Discovery's "Spec-Trio" scope (3 files) expanded to 5 deliverables after the pre-step inventory revealed catalog drift not anticipated at L3-Discovery time. Decisions in order of consequence:

### 2.1 Catalog reconciliation: Option A (revamp app to read `layer0.*`)

L3-Discovery §2.3 had stated catalogs were "unified at `layer0.*`." The inventory's §C revealed this was false today — the app reads catalogs exclusively from `public.*`; `layer0.*` parallel catalogs exist but are not read by any application code path.

Three options offered (A: migrate app to `layer0`; B: sync ETL keeps `public.*` aligned; C: treat as separate domains). **Confirmed: Option A** — the goal is to revamp the existing database/app to use the AIDSTATION-grade data model. `public.*` catalogs are deprecated and eventually dropped.

This was a real fork; the other options would have produced different specs. Option A captured in new `Catalog_Migration_Plan.md` (D-52); referenced from Integration Spec §2.4 and Control_Spec_v6 §2 and §2 v6-changed bullet 3.

### 2.2 Heat acclim state: derived, not stored

L3-Discovery gut-check flagged that `heat_acclim_state` (referenced in Control_Spec §3 line 160 as a 2E input) didn't exist anywhere in the codebase. Three locations were offered in the inventory's §D.3.

**Confirmed: derived from conditions + integration ambient data + locale climate.** Not stored as a profile field. Owned by Layer 2E consumer or plan-gen. D-53 captures the derivation spec work.

### 2.3 PG-only — SQLite backend deprecated

Confirmed PG-only for the AIDSTATION pipeline; SQLite backend deprecated entirely (implicitly required by Option A since `layer0.*` uses `TEXT[]` arrays that SQLite cannot represent). D-54.

### 2.4 Legacy `garmin_auth` dropped — Garmin migrates onto `provider_auth`

PROVIDERS_SCHEMA.md had exempted Garmin from the new generic shape on the basis that `garth` uses username/password. **Reversed.** Garmin migrates onto `provider_auth` like every other provider. `garth` session JSON stashed in a new `session_blob TEXT` column on `provider_auth`.

Breaking change for existing Garmin-connected users (one-time re-auth). Accepted. D-55.

### 2.5 Integration deployment timing: "deploy whenever"

Andy confirmed integration deployment is ready in the CC track and can ship any time. Recommendation in Integration Spec: deploy after the spec lands (now). Captured as D-50.

### 2.6 `provider_auth.session_blob` column added (my call, surfaced to Andy in the wrap)

PROVIDERS_SCHEMA.md doesn't have this column. Option II (reuse `access_token` for non-OAuth session blobs) is uglier but smaller. I went with Option I (new column) for cleanliness. Flagged as overridable in the wrap message; Andy did not override.

---

## 3. Files shipped

All 5 files in `/mnt/user-data/outputs/` and presented via `present_files`.

| File | Lines | Status | Notes |
|---|---|---|---|
| `Athlete_Onboarding_Data_Spec_v3.md` | 1059 | ✅ Shipped | v2 + §H.3 Non-Event Goal Type field per L3-Discovery §6.1. Single-purpose backwards-compatible amendment. Header bumped v2.5 → v3.0 with "What changed in v3 vs v2" section. |
| `Athlete_Data_Integration_Spec.md` v1 | 735 | ✅ Shipped | New cross-cutting spec. 12 sections per L3-Discovery §6.3 outline, expanded for Option A target state + Garmin migration + heat acclim derivation + PG-only. §7 field-mapping table for Layer 1 §C/§D/§E/§F sourcing. §7.6 surfaces D-51 as larger than originally scoped. |
| `Catalog_Migration_Plan.md` v1 | 306 | ✅ Shipped | New cross-cutting spec. Owns D-52. 9 sections: purpose, schema/identity/FK issues, catalog-by-catalog scope, 5-phase migration plan, decisions to lock, risks, open items, forward refs, gut check. Strategy-level v1; per-phase execution detail to be added as each phase approaches. |
| `Control_Spec_v6.md` | 438 | ✅ Shipped | C-1 through C-8 surgical edits per L3-Discovery §6.2 applied: header bump + v6 changed section; §2 Layer 1 conceptual-aggregation paragraph; §2 Layer 3 4-node framing; §3 Layer 1 sourcing subsection + Layer 2→3 update; §7 HITL 3D row; §8.2 D-21 closed-out wording; §8.3 cross-cutting spec clarification; §9 doc map updates (Layer 1 v3, Layer 3 4-node, new cross-cutting entries, v6/v10 promotion). |
| `Project_Backlog_v10.md` | 277 | ✅ Shipped | Header bump v9 → v10 with milestone note. Two new closed-session blocks: L3-Discovery (no spec files) and L3-Spec-Trio (5 spec files). Stale "Session FC-5 (next): tentative scope" section removed (overtaken by L3-Discovery + L3-Spec-Trio). Nine new rows D-48 through D-56. |

**Working-directory cleanup:** all files copied from `/home/claude/` to `/mnt/user-data/outputs/` and verified. No drafts left in working state.

---

## 4. Session-end verification (rule #10)

Ran an explicit verification pass over all 5 files before composing this handoff. Captured in chat log; summary:

**`Control_Spec_v6.md`:** All 8 C-1 through C-8 anchor strings present at expected locations. Spot-checks (`grep`):
- C-1: v6 header line present; "What changed in v6 vs v5" section present (1 match).
- C-2: "Layer 1 as conceptual aggregation" appears twice (§2 paragraph + v6 changed bullet 2).
- C-3: "3A — Athlete state evaluation" present at §2 (1 match).
- C-4: "Layer 1 sourcing (cross-schema aggregation)" subsection heading present.
- C-5: "3D aggregates HITL items" present at §7 (2 matches: §7 row + v6 changed bullet 1).
- C-6: "closed-out D-21 standing rule" present at §8.2 (1 match).
- C-7: "Cross-cutting specs follow their own structure" present at §8.3 (1 match).
- C-8: `Athlete_Data_Integration_Spec` referenced in doc map (2 matches).

**`Project_Backlog_v10.md`:**
- Session L3-Discovery block present (1 match).
- Session L3-Spec-Trio block present (1 match).
- All 9 D-48 through D-56 rows present (9 matches on `^\| D-(48|49|50|51|52|53|54|55|56) \|`).
- Stale `Session FC-5 (next): tentative scope` section removed (0 matches).

**`Catalog_Migration_Plan.md`:** All 9 section headings present and in order.

**`Athlete_Data_Integration_Spec.md`:** All 12 section headings present (verified during shipping).

**`Athlete_Onboarding_Data_Spec_v3.md`:** v3 header bumped; §H.3 Non-Event Goal Type row + explanatory paragraph present at line 600+ (verified during shipping).

No drift between handoff narrative and on-disk state.

---

## 5. Mechanically-applicable instructions for next session (rule #11)

**N/A.** All in-scope spec work shipped this session. No deferred edits.

The work captured in D-48 through D-56 is forward design work, not deferred edits to existing specs. Each row is self-contained with enough context for a future session to scope and execute.

---

## 6. Next-session execution plan

### Primary forward move: Layer 3 spec writing

Per L3-Discovery handoff §8 and confirmed by this session's state:

**Recommended sequencing:**
1. **`Layer3_3A_Spec.md`** — first and most consequential. 3A is the data-intensive LLM node; its input contract is now locked by `Athlete_Data_Integration_Spec` §7 (field mapping) and §10 (query signatures). The depth-standard 14-section spec (§8.3) anchored to scope statements in `L3_Discovery_Closing_Handoff_v1.md` §5.1.
2. **`Layer3_3B_Spec.md`** — goal-timeline-viability evaluation. Input contract now stable because Layer 1 v3 shipped this session with `Non-Event Goal Type`. Scope in L3-Discovery handoff §5.2.
3. **`Layer3_3C_Spec.md`** and **`Layer3_3D_Spec.md`** — likely one session for both (smaller surfaces; query/rules nodes). Scopes in L3-Discovery handoff §5.3 / §5.4.

Per the existing project convention, each spec gets its own session in a fresh chat. Don't try to do 3A + 3B + 3C + 3D in one session.

### Independent tracks (can run in parallel)

- **D-50: Phase 1 integration deployment** — CC task. Schema migration for `provider_auth` (with `session_blob`), `webhook_events`, `polar_*`, `wahoo_*`, `coros_*`, plus new columns on `cardio_log` and `training_log`. Deploy whenever; non-blocking. Coordinate with `DATABASE.md` updates.

- **D-52.1 / D-52.2: Catalog Migration Plan Phase 1** — verification + mapping. Independent of pipeline work. Could be its own session: dump deployed `layer0.exercises` schema, diff field-by-field against `public.exercise_inventory`, output mapping table. Same for equipment. ~1-2 sessions of focused work.

- **D-55: Garmin migration onto `provider_auth`** — coordinates with D-50 (Phase 1 deployment). Should land in the same deployment window or immediately after.

### Dependencies between tracks

- Layer 3 spec writing does **not** depend on D-50 (integration deployment), D-51 (Layer 1 field inventory), or D-52 (catalog migration). The specs can be written against the future Layer 1 payload shape; implementation follows.
- `q_layer1_payload` *implementation* depends on D-51. So Layer 3 specs are unblocked; Layer 3 implementation against real data has implicit ordering: D-51 + D-50 + (some of) D-52 first.

---

## 7. Forward pointers

- **Next session: `Layer3_3A_Spec.md` writing** in a fresh chat. Pre-step: read `Athlete_Data_Integration_Spec.md` §7 + §10, `Control_Spec_v6.md` §2 Layer 3 4-node description, and `L3_Discovery_Closing_Handoff_v1.md` §5.1 scope statement.

- **After 3A: `Layer3_3B_Spec.md`** — reads §H.3 of `Athlete_Onboarding_Data_Spec_v3.md` for the no-event-mode input contract (Non-Event Goal Type field).

- **After 3A/3B: combined `Layer3_3C_Spec.md` + `Layer3_3D_Spec.md`** — smaller surfaces.

- **After Layer 3 specs: D-50 integration deployment** if not already done in parallel track.

- **After Layer 3 specs: Layer 4 design** — plan generation. Consumes 3A state + 3B periodization-shape + 5 Layer 2 payloads. Largest LLM workload in the pipeline.

- **D-51 Layer 1 field inventory** should run before full `q_layer1_payload` implementation. Probably worth its own dedicated session at some point — likely 2-3 sessions to design the new tables/columns given the gap surface in `Athlete_Data_Integration_Spec` §7.6.

- **D-52 Catalog Migration Plan execution** — separate ongoing track. Phase 1 (verification + mapping) can start anytime. Each phase needs its own execution spec before shipping.

**Rules in force, unchanged:**
- #9 session-start verification (verify prior handoff's claimed file updates actually landed)
- #10 session-end verification (verify each claimed file update on-disk before composing handoff)
- #11 mechanically-applicable deferred edits (str_replace blocks or verbatim content, never narrative summaries)
- #12 numeric version suffixes (revised files save as `_vN.md`; logical names cross-referenced via `view` on highest-N)

---

## 8. Gut check

**What this session got right.**

- **Catching catalog drift before drafting specs that would have inherited the wrong assumption.** The L3-Discovery handoff stated catalogs were unified at `layer0.*`; the pre-step inventory's §C revealed they weren't. Surfacing this *before* drafting Athlete_Data_Integration_Spec meant the spec was written against the correct architecture from the start. If we'd drafted on the L3-Discovery assumption and then discovered the drift in the next session, this session's outputs would have been wasted work.

- **Adding Catalog_Migration_Plan as a fifth deliverable rather than parking it.** Option A is a real multi-month commitment, not a sentence change. Capturing it as a strategy spec (D-52 placeholder) in the same session that decided it preserves context — the rationale, the schema-shape problems, the FK migration sequencing — that would be lost if it were deferred to a Backlog row and a future session.

- **Five files in one session is the max.** Quality stayed high because: (1) two of the five were pre-scoped (Onboarding v3 was a single str_replace; Backlog v10 was mechanical); (2) Control_Spec_v6 was eight surgical edits, not a rewrite; (3) Integration Spec and Catalog Migration Plan were the only substantively-new content. Anything more would have degraded.

**Risks.**

- **Catalog Migration Plan v1 is strategy-level, not execution-detail.** Phases 2-5 need their own sub-specs before shipping. If Phase 1's verification audit surfaces fundamental schema mismatches between `public.*` and `layer0.*` that the inventory didn't catch, the phase plan may need restructuring.

- **Integration Spec §7 field mapping inferences for Polar/COROS/Wahoo tables.** Some column shapes were inferred from PROVIDERS_SCHEMA.md descriptions rather than confirmed against actual API payloads. When Wave-1 deploys (D-50), some columns may need adjustment. Not a blocker for Layer 3 spec writing.

- **D-51 (Layer 1 field inventory) is genuinely big.** Onboarding spec §A through §L has dozens of fields with no `public.*` home. The work to design new tables/columns is real spec work, not just glue. Don't let it become a hidden blocker for Layer 3 *implementation*; specs can be written against the future shape.

- **Layer 3 specs will reveal whether the 4-node decomposition holds.** 3A and 3B as separate LLM calls is a clean cache-invalidation story but could harm output coherence. Spec writer should leave this as explicit open item in 3A/3B specs to revisit post-deployment (per L3-Discovery handoff §9 gut check).

**What might be missing.**

- **Plan Management spec (D-27)** is becoming more central — D-53 references it as the owner of heat acclim derivation; 3B references it for periodization shape consumption. Should be scoped soon, though not this session. Currently sits as 🟡 Deferred in the backlog.

- **2D/2E specs may need light updates** for the heat_acclim derivation reframing (D-53). Their §3 input contracts reference `heat_acclim_state` as a Plan Management state field; post-derivation the contract surface is the same but the rationale comment is wrong. Worth verifying when 2D/2E next gets touched.

- **Integration Spec §10 query layer signatures are signatures only.** Layer 3A spec writer will need to fully define the dataclass return types. Worth flagging upfront so 3A doesn't try to reuse the integration spec's level of detail.

- **No `Layer1_Sourcing_Spec` proper.** Control_Spec_v6 §3 has a brief "Layer 1 sourcing" subsection and Athlete_Data_Integration_Spec covers the consumer-side aggregation, but there's no dedicated spec for the `q_layer1_payload` function. May not need one — could live as part of the Layer 1 v4+ work when D-51 lands. Worth a decision later, not now.

**Best argument against this session's scope.**

You could argue Catalog_Migration_Plan deserved its own session. The strategy is consequential — Option A is a multi-month commitment — and v1 was drafted alongside four other docs. Counter: the plan is intentionally strategy-level; per-phase execution detail will need its own sub-specs anyway. Better to have v1 in writing than to defer it and lose the catalog-drift context that prompted it.

Alternatively, you could argue the Integration Spec's §7 field-mapping section is too provisional — half the fields are flagged as "needs new column/table per D-51." But this is honest reporting: D-51 *is* genuinely big, and surfacing the gaps in the spec is more useful than papering over them.

---

*End of L3-Spec-Trio closing handoff.*
